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
import sys

from cli.compose import (
    OperatorError,
    load_registry,
    open_store,
    parse_stated_at,
    split_provenance,
    verify_and_persist,
)
from engine.custodians.fixture import build_fixture_custodians
from engine.custodians.live import build_live_custodians
from engine.ingest.split import RawProvenance

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

#: Anchored to the root for the same reason `DEFAULT_STORE` is, and it became
#: load-bearing the moment `pip install -e .` made `grounding-verify` runnable
#: from anywhere. A cwd-relative default resolves to nothing outside the
#: checkout, and an empty pack set is not an error the engine can report: no
#: pack covers the jurisdiction, so every claim returns Insufficient Data —
#: a confident answer produced because the packs were never found. Interface
#: §3.6's rule applies to the operator surface too: under-firing invisibly is
#: worse than declining visibly.
DEFAULT_PACKS = str(ROOT / "packs" / "fixture")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify",
        description="Verify a claim against an authoritative custodian of record.",
    )
    parser.add_argument("claim", help="the claim text to verify")
    parser.add_argument(
        "--packs",
        default=DEFAULT_PACKS,
        help=(
            "directory of pack files. Defaults to the fixture packs under the "
            "repository root, so the installed command works from any working "
            "directory; a relative path given here is relative to the working "
            "directory, matching --store"
        ),
    )
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
        stated_at = parse_stated_at(args.stated_at)
        context, identity = split_provenance(
            RawProvenance(
                stated_at=stated_at,
                language=args.language,
                jurisdiction_hint=args.jurisdiction,
                claimant_name=args.claimant,
                venue=args.venue,
            )
        )
        registry = load_registry(args.packs)
        store = open_store(args.store)
    except OperatorError as exc:
        # Every one of these is the operator's input, reported as such.
        # Exit 2, never a traceback, and never a verdict: see cli/compose.py.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    adapters = build_fixture_custodians()
    if args.live:
        adapters.update(build_live_custodians())
    try:
        run = verify_and_persist(args.claim, context, identity, registry, store, adapters)
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
