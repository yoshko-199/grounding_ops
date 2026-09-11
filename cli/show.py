#!/usr/bin/env python3
"""Read back a stored verification artifact by claim id.

`cli/verify.py` persists every claim it verifies (`engine.store.writer`).
This is the read side, and the reason it needs to exist: §8's claim that
`element_set_hash` "makes the pure-function property checkable after the
fact" is untestable without something that reads a stored reconstruction
back and lets a caller compare it against another run. Before this command,
"after the fact" had no meaning — a verdict died with the process that
produced it, and the schema's own comment (`engine/store/schema.sql`) was
describing a property nothing could check.

This is not `cli/verify.py` run again. It performs no retrieval, resolves no
route, and recomputes nothing — it prints exactly the rows a prior `verify`
call wrote, which is the only way to know the writer and the schema agree
with what was actually persisted.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from cli.verify import DEFAULT_STORE
from engine.store.events import RetrievalStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="show",
        description="Read back a stored verification artifact by claim id.",
    )
    parser.add_argument("claim_id", help="the id printed by cli/verify.py")
    parser.add_argument("--store", default=DEFAULT_STORE, metavar="PATH")
    parser.add_argument("--json", action="store_true", help="emit structured output")
    args = parser.parse_args(argv)

    try:
        store = RetrievalStore(args.store)
    except (OSError, sqlite3.Error) as exc:
        print(f"error: cannot open retrieval store {args.store!r}: {exc}", file=sys.stderr)
        return 2

    try:
        record = _load(store, args.claim_id)
    finally:
        store.close()

    if record is None:
        print(f"error: no claim recorded with id {args.claim_id!r}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(_render(record))
    return 0


def _load(store: RetrievalStore, claim_id: str) -> dict | None:
    """Everything persisted about one claim, or ``None`` if it was never seen."""
    conn = store.connection
    conn.row_factory = sqlite3.Row

    claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        return None

    context = conn.execute(
        "SELECT * FROM claim_context WHERE id = ?", (claim["claim_context_id"],)
    ).fetchone()
    identity = (
        conn.execute(
            "SELECT * FROM claimant_identity WHERE id = ?", (claim["claimant_identity_id"],)
        ).fetchone()
        if claim["claimant_identity_id"]
        else None
    )

    elements = conn.execute(
        "SELECT * FROM elements WHERE claim_id = ? ORDER BY source_span_start", (claim_id,)
    ).fetchall()
    discards = conn.execute(
        """
        SELECT discards.*, elements.fragment AS fragment, elements.status AS status
        FROM discards JOIN elements ON elements.id = discards.element_id
        WHERE discards.reconstructed_claim_id = ?
        """,
        (claim_id,),
    ).fetchall()
    derived = conn.execute(
        "SELECT * FROM derived_elements WHERE from_claim_id = ? ORDER BY source_span_start",
        (claim_id,),
    ).fetchall()

    # The latest reconstruction and the latest verdict. `reconstructions` and
    # `verdicts` are append-only trajectories (§4 Stage 7, §9.1); the most
    # recent row is the current state, and the earlier rows are the history a
    # future `cli/show.py --history` would read, not this one.
    reconstruction = conn.execute(
        "SELECT * FROM reconstructions WHERE claim_id = ? ORDER BY revision DESC LIMIT 1",
        (claim_id,),
    ).fetchone()
    verdict = conn.execute(
        "SELECT * FROM verdicts WHERE claim_id = ? ORDER BY proposed_at DESC LIMIT 1",
        (claim_id,),
    ).fetchone()

    citations = conn.execute(
        """
        SELECT retrievals.* FROM citations
        JOIN retrievals ON retrievals.id = citations.retrieval_id
        WHERE citations.claim_id = ?
        ORDER BY citations.position
        """,
        (claim_id,),
    ).fetchall()
    sweeps = conn.execute(
        "SELECT * FROM sweeps WHERE claim_id = ?", (claim_id,)
    ).fetchall()

    return {
        "claim_id": claim_id,
        "text": claim["text"],
        "stated_at": claim["stated_at"],
        "context": dict(context) if context else None,
        "identity": dict(identity) if identity else None,
        "elements": [dict(e) for e in elements],
        "discards": [
            {"fragment": d["fragment"], "status": d["status"], "reason": d["reason"]}
            for d in discards
        ],
        "derived_elements": [dict(d) for d in derived],
        "reconstruction": dict(reconstruction) if reconstruction else None,
        "verdict": dict(verdict) if verdict else None,
        "citations": [dict(c) for c in citations],
        "sweeps": [dict(s) for s in sweeps],
    }


def _render(record: dict) -> str:
    lines: list[str] = []
    lines.append(f"[STORED — claim {record['claim_id']}]")
    lines.append("")
    lines.append("ORIGINAL CLAIM")
    lines.append(f'  "{record["text"]}"')
    lines.append("")

    lines.append("RECONSTRUCTED")
    recon = record["reconstruction"]
    if recon and recon["does_reconstruct"]:
        lines.append(f"  {recon['text']}")
        lines.append(f"  revision {recon['revision']}, hash {recon['element_set_hash']}")
    else:
        lines.append("  does not reconstruct")
    lines.append("")

    lines.append("DISCARD LEDGER")
    if record["discards"]:
        for d in record["discards"]:
            lines.append(f'  - "{d["fragment"]}" [{d["status"]}]')
            lines.append(f"      {d['reason']}")
    else:
        lines.append("  Nothing was discarded.")
    lines.append("")

    lines.append("VERDICT")
    verdict = record["verdict"]
    if verdict:
        lines.append(f"  {verdict['label'].replace('_', ' ').upper()}  [{verdict['state']}]")
        lines.append(f"  {verdict['rationale']}")
        if verdict["confirmed_by"]:
            lines.append(f"  signed off by {verdict['confirmed_by']} at {verdict['confirmed_at']}")
        if verdict["amended_from_label"]:
            lines.append(f"  amended from {verdict['amended_from_label']}: {verdict['amendment_rationale']}")
    else:
        lines.append("  No verdict was recorded.")
    lines.append("")

    lines.append("CITATIONS")
    if record["citations"]:
        for c in record["citations"]:
            lines.append(f"  {c['custodian_id']} / {c['series_id']}")
            lines.append(
                f"      figure {c['figure']} {c['unit']} for {c['reference_period']}"
            )
            lines.append(
                f"      revision {c['revision_status']}; retrieved {c['retrieved_at']}; "
                f"continuity {c['continuity_status']}"
            )
            if c["superseded_at"]:
                lines.append(f"      superseded at {c['superseded_at']}")
    else:
        lines.append("  No retrieval was performed.")
    lines.append("")

    if record["sweeps"]:
        lines.append("ROBUSTNESS SWEEP")
        for s in record["sweeps"]:
            verdict_word = "holds" if s["conclusion_holds"] else "FLIPS"
            lines.append(f"  [{verdict_word}] {s['test']}: {s['alternative']}")
        lines.append("")

    if record["derived_elements"]:
        lines.append("DERIVED ELEMENTS (proposed, not confirmed)")
        for d in record["derived_elements"]:
            lines.append(f"  [{d['tag']}] {d['text']}")
            lines.append(f"      operation: {d['derivation_operation']}, state: {d['state']}")
        lines.append("")

    if record["identity"]:
        identity = record["identity"]
        lines.append("ATTRIBUTION (recorded, never routed)")
        lines.append(f"  claimant: {identity['name'] or '-'}")
        lines.append(f"  venue:    {identity['venue'] or '-'}")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
