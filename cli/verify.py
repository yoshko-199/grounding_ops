#!/usr/bin/env python3
"""Verify a claim against a loaded custodian pack.

Exit code 0 for every verdict, including Insufficient Data. §7.5 requires it
to be "a first-class, prominently-rendered outcome — never styled as
failure", and a non-zero exit is exactly the error styling AC-5 forbids.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import sys
from datetime import date

from engine.codes import InvalidCode, LanguageCode
from engine.custodians.fixture import build_fixture_custodians
from engine.custodians.live import build_live_custodians
from engine.ingest.split import RawProvenance, split
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore
from engine.store.identity_writer import write_identity
from engine.store.writer import write_pack, write_verification

#: The repository root, so the default store is one database rather than one
#: per working directory. Resolved the same way `scripts/harvest_corpus.py`
#: resolves its own defaults.
ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Where retrievals live when the caller does not say. §8 makes a retrieval an
#: event carrying a TTL, re-pulled when it expires and served when it has not —
#: and none of that is observable while the store dies with the process, which
#: is what `RetrievalStore()` with no path had been doing on every run.
#:
#: Anchored to the root rather than left relative to the working directory. A
#: cwd-relative default silently creates a second empty database when the
#: command is run from a subdirectory, which restores exactly the re-pull-
#: everything behaviour the path was added to remove — and scatters databases
#: outside the repository while looking like it worked.
DEFAULT_STORE = str(ROOT / ".grounding" / "store.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify",
        description="Verify a claim against an authoritative custodian of record.",
    )
    parser.add_argument("claim", help="the claim text to verify")
    parser.add_argument("--packs", default="packs/fixture", help="directory of pack files")
    parser.add_argument("--jurisdiction", default=None, help="ISO jurisdiction code hint")
    parser.add_argument("--language", default="en", help="ISO 639 language code")
    parser.add_argument("--stated-at", default=None, help="ISO date the claim was made")
    parser.add_argument("--json", action="store_true", help="emit structured output")
    parser.add_argument(
        "--store",
        default=DEFAULT_STORE,
        metavar="PATH",
        help=(
            "retrieval store. Defaults to a database under the repository root "
            "so a retrieval outlives the process that made it, wherever the "
            "command was run from; pass ':memory:' for a run that remembers "
            "nothing. A relative path given here is relative to the working "
            "directory, which is what typing one means"
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "also wire adapters for custodians this deployment can reach. Off by "
            "default: a run that silently went to the network would make it "
            "impossible to tell a fixture answer from a real one"
        ),
    )
    # Attribution is accepted, retained, and displayed -- and never routed.
    parser.add_argument("--claimant", default=None, help="who said it (never routed)")
    parser.add_argument("--venue", default=None, help="where it was said (never routed)")
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help=(
            "also print the routing rationale and, if a custodian could not be "
            "reached, the technical detail behind it. Printed separately, after "
            "the artifact, never inside it: this is operator information about "
            "why a pull failed technically -- a status code, a timeout -- not "
            "part of the verified record, and a numeral in it must never be "
            "mistaken for one AC-7 would have to account for"
        ),
    )
    args = parser.parse_args(argv)

    try:
        stated_at = (
            date.fromisoformat(args.stated_at) if args.stated_at else date.today()
        )
    except ValueError:
        # A malformed date is an operator error, and it must not reach the
        # pipeline: every tolerance band and the continuity check are indexed
        # on when the claim was made. Reported like any other bad code rather
        # than raised, because a traceback here reads as a crash in the engine.
        print(
            f"error: not a date: {args.stated_at!r}. Expected ISO format, "
            "for example 2021-06-01",
            file=sys.stderr,
        )
        return 2

    try:
        context, identity = split(
            RawProvenance(
                stated_at=stated_at,
                language=args.language,
                jurisdiction_hint=args.jurisdiction,
                claimant_name=args.claimant,
                venue=args.venue,
            )
        )
    except InvalidCode as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    registry = PackRegistry.from_directory(args.packs)
    try:
        if args.store != ":memory:":
            pathlib.Path(args.store).parent.mkdir(parents=True, exist_ok=True)
        store = RetrievalStore(args.store)
    except (OSError, sqlite3.Error) as exc:
        # An unwritable directory, a path that is already a directory, a
        # corrupt database, or a concurrent run holding the lock. All are
        # operator errors and all reported the way this file reports the
        # others: a traceback out of the store constructor reads as a crash
        # in the engine, which is the one thing it is not.
        print(f"error: cannot open retrieval store {args.store!r}: {exc}", file=sys.stderr)
        return 2
    adapters = build_fixture_custodians()
    if args.live:
        adapters.update(build_live_custodians())
    try:
        run = verify(args.claim, context, registry, adapters, store)
        # §8's other fifteen tables, written here rather than inside `verify`
        # itself: persistence is composition-root bookkeeping, not a
        # verification rule, and `engine.store.writer` is not importable from
        # `engine.verification` for exactly that reason. Identity is written
        # by a second, separate module — see its docstring for why one
        # function among these would not do.
        if run.decision and run.decision.pack:
            write_pack(store, run.decision.pack)
        write_verification(store, run)
        write_identity(store, run.claim_id, identity)
    finally:
        # §8 keeps retrievals as events with a TTL. An event that dies with the
        # process is not an event, and the store's commits are only durable if
        # the connection closes cleanly.
        store.close()

    if args.json:
        payload = run.artifact.to_dict()
        payload["attribution"] = {"claimant": identity.name, "venue": identity.venue}
        payload["claim_id"] = str(run.claim_id)
        if args.diagnostics:
            # A sibling key, not nested under anything `to_dict()` produced --
            # this is not part of the artifact and must not be mistaken for it.
            payload["diagnostics"] = {
                "routing_rationale": run.decision.rationale if run.decision else "",
                "pull_diagnostic": run.diagnostic,
            }
        print(json.dumps(payload, indent=2))
    else:
        print(run.artifact.render())
        if not identity.is_anonymous:
            print("ATTRIBUTION (recorded, never routed)")
            print(f"  claimant: {identity.name or '-'}")
            print(f"  venue:    {identity.venue or '-'}")
        print(f"claim id: {run.claim_id}  (pass to cli/show.py to read this back)")
        if args.diagnostics:
            print()
            print("DIAGNOSTICS (operator information, not part of the verified record)")
            if run.decision and run.decision.rationale:
                print(f"  routing:  {run.decision.rationale}")
            else:
                print("  routing:  (no routing rationale recorded)")
            if run.diagnostic:
                print(f"  pull:     {run.diagnostic}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
