"""Persist sign-off decisions — a third composition-root writer.

`engine.signoff` computes a :class:`~engine.signoff.SignedVerdict` and stores
nothing (§9.1's whole point: the gate has no import path to evidence, and
that is enforced by keeping it away from persistence too, not only from the
store's other tables). Something still has to write the decision down, or
`cli/signoff.py` would be exactly the "demonstration, not a workflow" the
plan calls it — a reviewer's confirmation would vanish with the process the
same way a verdict used to.

This module is that something, on the same footing as `engine.store.writer`
and `engine.store.identity_writer`: outside `engine.verification`, outside
`engine.signoff` itself, importable only from a composition root.

`verdicts` is append-only (§8's "validity window, not a boolean" — a verdict
is "verified against series X, revision Y, as of date Z"). Signing off does
not edit the proposed row; it closes that row's validity window
(``valid_until``) and inserts a new one carrying the gate's decision. At most
one row per claim has ``valid_until IS NULL`` at any time — the current
state — which is what makes "list what is awaiting review" a plain query
rather than a second index to maintain.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from engine.elements import GateState
from engine.ids import ClaimId
from engine.signoff import SignedVerdict
from engine.store.events import RetrievalStore
from engine.verification.claim_verdict import ProposedVerdict, Verdict


class NoOpenVerdict(Exception):
    """Raised when a claim id names no currently-open verdict row."""


def list_proposed(store: RetrievalStore) -> list[sqlite3.Row]:
    """Every claim whose current verdict is still awaiting review.

    "Currently" means the row with ``valid_until IS NULL`` — the state a
    verdict occupies until something (a sign-off, a re-verification that
    supersedes it) closes its window.
    """
    return store.connection.execute(
        """
        SELECT claims.id AS claim_id, claims.text AS text,
               verdicts.label AS label, verdicts.rationale AS rationale,
               verdicts.proposed_at AS proposed_at
        FROM verdicts JOIN claims ON claims.id = verdicts.claim_id
        WHERE verdicts.state = ? AND verdicts.valid_until IS NULL
        ORDER BY verdicts.proposed_at
        """,
        (GateState.PROPOSED.value,),
    ).fetchall()


def load_proposed(store: RetrievalStore, claim_id: str) -> ProposedVerdict | None:
    """The claim's current verdict, as a :class:`ProposedVerdict` — only if
    it is actually still proposed. A claim already confirmed, amended, or
    rejected has no *proposed* verdict to load, whatever its current row
    says; sign-off is a one-way gate (§9.1: "a decided verdict cannot be
    revisited in place"), and this is where that is enforced for the
    store-backed path rather than only inside :func:`engine.signoff.confirm`.
    """
    row = store.connection.execute(
        "SELECT label, rationale, state FROM verdicts "
        "WHERE claim_id = ? AND valid_until IS NULL",
        (claim_id,),
    ).fetchone()
    if row is None or row["state"] != GateState.PROPOSED.value:
        return None
    return ProposedVerdict(Verdict(row["label"]), row["rationale"], state=GateState.PROPOSED)


def write_signoff(
    store: RetrievalStore,
    claim_id: ClaimId | str,
    signed: SignedVerdict,
    *,
    now: datetime | None = None,
) -> None:
    """Close the claim's open verdict row and append the signed decision.

    Raises :class:`NoOpenVerdict` rather than silently inserting an orphaned
    row if the claim has no open verdict — the caller (`cli/signoff.py`)
    already checked this via :func:`load_proposed` before calling any of
    `confirm`/`amend`/`reject`, so reaching this branch means the store
    changed underneath the CLI between the two calls, not that the CLI
    skipped the check.
    """
    now = now or datetime.now(timezone.utc)
    conn = store.connection
    claim_id = str(claim_id)

    current = conn.execute(
        "SELECT proposed_at, rationale FROM verdicts WHERE claim_id = ? AND valid_until IS NULL",
        (claim_id,),
    ).fetchone()
    if current is None:
        raise NoOpenVerdict(f"claim {claim_id!r} has no open verdict to sign off")

    conn.execute(
        "UPDATE verdicts SET valid_until = ? WHERE claim_id = ? AND valid_until IS NULL",
        (now.isoformat(), claim_id),
    )
    conn.execute(
        "INSERT INTO verdicts "
        "(id, claim_id, label, rationale, valid_from, valid_until, state, proposed_at, "
        "confirmed_by, confirmed_at, amended_from_label, amendment_rationale) "
        "VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()), claim_id, signed.label.value, current["rationale"],
            now.isoformat(), signed.state.value, current["proposed_at"],
            signed.confirmed_by or None,
            signed.confirmed_at.isoformat() if signed.confirmed_at else None,
            signed.amended_from_label.value if signed.amended_from_label else None,
            signed.amendment_rationale or None,
        ),
    )
    conn.commit()
