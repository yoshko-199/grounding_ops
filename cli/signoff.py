#!/usr/bin/env python3
"""Sign off a proposed claim-level verdict.

§9.1 puts a person on the claim-level verdict and nowhere else. This command
mirrors that exactly: it takes a label and a rationale, and there is no flag
through which it could reach an element status, a retrieval, the discard
ledger, the flip table, or a pack.

Two ways to supply the proposal being decided:

* ``--proposed LABEL`` — the label as a bare string. No store is touched, and
  nothing is written anywhere. Useful for exercising the gate itself, or for
  a proposal that never went through ``cli/verify.py``.
* ``--claim-id ID`` — loads the claim's actual stored verdict from
  ``--store`` and, once decided, persists the decision back. This is the
  workflow: ``cli/verify.py`` prints a claim id, ``signoff.py list`` shows
  what is awaiting review, and ``signoff.py confirm --claim-id ID`` closes
  the loop.

Persistence lives in :mod:`engine.store.signoff_writer`, not here and not in
:mod:`engine.signoff` — the same composition-root pattern
:mod:`engine.store.writer` and :mod:`engine.store.identity_writer` already
use, and for the same reason: :mod:`engine.signoff` must never gain an import
path to the store (§9.1 rule 2, AC-10).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

from cli.verify import DEFAULT_STORE
from engine.signoff import GateViolation, amend, confirm, reject
from engine.store.events import RetrievalStore
from engine.store.signoff_writer import list_proposed, load_proposed, write_signoff
from engine.verification.claim_verdict import ProposedVerdict, Verdict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="signoff",
        description="List claims awaiting review, or confirm/amend/reject a proposed verdict.",
    )
    parser.add_argument("action", choices=["list", "confirm", "amend", "reject"])
    parser.add_argument("--reviewer", help="who is signing off (required except for list)")
    parser.add_argument(
        "--proposed", choices=[v.value for v in Verdict],
        help="the label the pipeline proposed, given directly rather than read from a store",
    )
    parser.add_argument(
        "--claim-id", metavar="ID",
        help="sign off a claim verified earlier, reading its verdict from --store "
        "and persisting the decision back into it",
    )
    parser.add_argument(
        "--store", default=DEFAULT_STORE, metavar="PATH",
        help="retrieval store to read from and write to; only consulted with --claim-id "
        "or list",
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

    if args.action == "list":
        return _list(args.store)

    if bool(args.claim_id) == bool(args.proposed):
        print("error: pass exactly one of --claim-id or --proposed", file=sys.stderr)
        return 2
    if not args.reviewer:
        print("error: --reviewer is required", file=sys.stderr)
        return 2

    store: RetrievalStore | None = None
    if args.claim_id:
        try:
            store = RetrievalStore(args.store)
        except (OSError, sqlite3.Error) as exc:
            print(f"error: cannot open retrieval store {args.store!r}: {exc}", file=sys.stderr)
            return 2
        proposal = load_proposed(store, args.claim_id)
        if proposal is None:
            store.close()
            print(
                f"error: no open proposed verdict for claim id {args.claim_id!r}. "
                "Either it was never verified into this store, or it has already been "
                "signed off",
                file=sys.stderr,
            )
            return 2
    else:
        # The ad-hoc path: a placeholder rationale, because none was
        # supplied. `--claim-id` is what carries the pipeline's actual
        # rationale into the gate.
        proposal = ProposedVerdict(Verdict(args.proposed), "proposed by the pipeline")

    try:
        if args.action == "confirm":
            signed = confirm(proposal, args.reviewer)
        elif args.action == "reject":
            signed = reject(proposal, args.reviewer)
        else:
            if not args.label:
                if store:
                    store.close()
                print("error: --label is required for amend", file=sys.stderr)
                return 2
            signed = amend(proposal, Verdict(args.label), args.rationale, args.reviewer)
    except GateViolation as exc:
        if store:
            store.close()
        print(f"gate refused: {exc}", file=sys.stderr)
        return 2

    if store is not None:
        try:
            write_signoff(store, args.claim_id, signed)
        finally:
            store.close()

    print(f"state:     {signed.state.value}")
    print(f"label:     {signed.label.value}")
    if signed.amended_from_label:
        print(f"amended from: {signed.amended_from_label.value}")
        print(f"rationale: {signed.amendment_rationale}")
    print(f"reviewer:  {signed.confirmed_by}")
    print(f"exportable: {signed.exportable}")
    if args.claim_id:
        print(f"claim id:  {args.claim_id}  (recorded in {args.store})")
    return 0


def _list(store_path: str) -> int:
    try:
        store = RetrievalStore(store_path)
    except (OSError, sqlite3.Error) as exc:
        print(f"error: cannot open retrieval store {store_path!r}: {exc}", file=sys.stderr)
        return 2
    try:
        rows = list_proposed(store)
    finally:
        store.close()

    if not rows:
        print("Nothing is awaiting review.")
        return 0
    for row in rows:
        text = row["text"]
        if len(text) > 72:
            text = text[:69] + "..."
        print(f"{row['claim_id']}  [{row['label']}]  \"{text}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
