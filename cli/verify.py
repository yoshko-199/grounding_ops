#!/usr/bin/env python3
"""Verify a claim against a loaded custodian pack.

Exit code 0 for every verdict, including Insufficient Data. §7.5 requires it
to be "a first-class, prominently-rendered outcome — never styled as
failure", and a non-zero exit is exactly the error styling AC-5 forbids.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from engine.codes import InvalidCode, LanguageCode
from engine.custodians.fixture import build_fixture_custodians
from engine.custodians.live import build_live_custodians
from engine.ingest.split import RawProvenance, split
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore


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
    store = RetrievalStore()
    adapters = build_fixture_custodians()
    if args.live:
        adapters.update(build_live_custodians())
    run = verify(args.claim, context, registry, adapters, store)

    if args.json:
        payload = run.artifact.to_dict()
        payload["attribution"] = {"claimant": identity.name, "venue": identity.venue}
        print(json.dumps(payload, indent=2))
    else:
        print(run.artifact.render())
        if not identity.is_anonymous:
            print("ATTRIBUTION (recorded, never routed)")
            print(f"  claimant: {identity.name or '-'}")
            print(f"  venue:    {identity.venue or '-'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
