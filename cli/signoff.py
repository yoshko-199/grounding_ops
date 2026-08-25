#!/usr/bin/env python3
"""Sign off a proposed claim-level verdict.

§9.1 puts a person on the claim-level verdict and nowhere else. This command
mirrors that exactly: it takes a label and a rationale, and there is no flag
through which it could reach an element status, a retrieval, the discard
ledger, the flip table, or a pack.
"""

from __future__ import annotations

import argparse
import sys

from engine.signoff import GateViolation, amend, confirm, reject
from engine.verdicts import ProposedVerdict, Verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="signoff",
        description="Confirm, amend, or reject a proposed claim-level verdict.",
    )
    parser.add_argument("action", choices=["confirm", "amend", "reject"])
    parser.add_argument("--reviewer", required=True, help="who is signing off")
    parser.add_argument(
        "--proposed", required=True, choices=[v.value for v in Verdict],
        help="the label the pipeline proposed",
    )
    parser.add_argument(
        "--label", choices=[v.value for v in Verdict],
        help="the amended label (amend only)",
    )
    parser.add_argument(
        "--rationale", default="",
        help="why the label was changed (amend only, required, and bound by §3)",
    )
    args = parser.parse_args(argv)

    proposal = ProposedVerdict(Verdict(args.proposed), "proposed by the pipeline")

    try:
        if args.action == "confirm":
            signed = confirm(proposal, args.reviewer)
        elif args.action == "reject":
            signed = reject(proposal, args.reviewer)
        else:
            if not args.label:
                print("error: --label is required for amend", file=sys.stderr)
                return 2
            signed = amend(proposal, Verdict(args.label), args.rationale, args.reviewer)
    except GateViolation as exc:
        print(f"gate refused: {exc}", file=sys.stderr)
        return 2

    print(f"state:     {signed.state.value}")
    print(f"label:     {signed.label.value}")
    if signed.amended_from_label:
        print(f"amended from: {signed.amended_from_label.value}")
        print(f"rationale: {signed.amendment_rationale}")
    print(f"reviewer:  {signed.confirmed_by}")
    print(f"exportable: {signed.exportable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
