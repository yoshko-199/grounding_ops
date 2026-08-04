"""Stage 11 — the sign-off gate.

Spec §9.1.  Retrieval and element verdicts are automated and final; the
claim-level verdict is a proposal requiring explicit human confirmation.

The gate's authority is narrowed at the API boundary rather than checked
inside it.  :func:`confirm`, :func:`amend`, :func:`reject` accept a label and
a rationale and have no parameter reaching an element status, a retrieval,
the discard ledger, the flip table, a routing decision, or a pack.  AC-10
asks that every such attempt fail; here there is nothing to attempt.

§9.1 explains why this restriction is the load-bearing part: "an
unconstrained human sign-off would let a reviewer reach past the verdict and
adjust the evidence beneath it."  AC-10's note is blunter — "An unconstrained
human gate is itself a laundering vector, and a more credible one than the
pipeline — it arrives wearing the authority of review."
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from engine.elements import GateState
from engine.render.figures import scan_prose
from engine.verdicts import ProposedVerdict, Verdict


class GateViolation(Exception):
    """Raised when sign-off is asked to do something it may not."""


@dataclass(frozen=True, slots=True)
class SignedVerdict:
    """A verdict after the gate, retaining the proposal it came from.

    §9.1 rule 1: "An amendment never overwrites the proposal. Both are
    retained, with a required ``amendment_rationale``. The audit trail is the
    point — a gate whose history can be edited is not a gate."
    """

    proposal: ProposedVerdict
    label: Verdict
    state: GateState
    confirmed_by: str
    confirmed_at: datetime
    amendment_rationale: str = ""

    @property
    def amended_from_label(self) -> Verdict | None:
        return self.proposal.label if self.state is GateState.AMENDED else None

    @property
    def exportable(self) -> bool:
        return self.state in (GateState.CONFIRMED, GateState.AMENDED)

    @property
    def unconfirmed_marker(self) -> str:
        """§9.1 rule 4 — a proposed verdict renders visibly marked."""
        return "" if self.exportable else "UNCONFIRMED — proposed, not signed off"


def confirm(proposal: ProposedVerdict, reviewer: str,
            now: datetime | None = None) -> SignedVerdict:
    """Accept the proposed label unchanged."""
    _require_reviewer(reviewer)
    _require_open(proposal)
    return SignedVerdict(
        proposal=proposal,
        label=proposal.label,
        state=GateState.CONFIRMED,
        confirmed_by=reviewer,
        confirmed_at=now or datetime.now(timezone.utc),
    )


def amend(
    proposal: ProposedVerdict,
    new_label: Verdict,
    rationale: str,
    reviewer: str,
    now: datetime | None = None,
) -> SignedVerdict:
    """Change the claim-level label, and nothing beneath it."""
    _require_reviewer(reviewer)
    _require_open(proposal)

    if not rationale.strip():
        raise GateViolation(
            "an amendment requires a non-empty amendment_rationale. A label changed "
            "without a stated reason is a gate whose history says nothing (§9.1)"
        )

    # §9.1 rule 3, and AC-10: "a human confirming or amending a verdict cannot
    # introduce a figure". §3 binds the reviewer exactly as it binds the
    # pipeline, and the rationale is output like any other.
    numerals = scan_prose(rationale)
    if numerals:
        raise GateViolation(
            f"amendment_rationale introduces the figure(s) {sorted(set(numerals))}, "
            "which originate from no retrieval. §3 binds the reviewer exactly as it "
            "binds the pipeline (AC-10)"
        )

    if new_label is proposal.label:
        raise GateViolation(
            "amend() was called with the proposed label unchanged; use confirm()"
        )

    return SignedVerdict(
        proposal=proposal,
        label=new_label,
        state=GateState.AMENDED,
        confirmed_by=reviewer,
        confirmed_at=now or datetime.now(timezone.utc),
        amendment_rationale=rationale,
    )


def reject(proposal: ProposedVerdict, reviewer: str,
           now: datetime | None = None) -> SignedVerdict:
    """Publish no label. §9.1's `rejected` state."""
    _require_reviewer(reviewer)
    _require_open(proposal)
    return SignedVerdict(
        proposal=proposal,
        label=proposal.label,
        state=GateState.REJECTED,
        confirmed_by=reviewer,
        confirmed_at=now or datetime.now(timezone.utc),
    )


def expire(proposal: ProposedVerdict, now: datetime | None = None) -> SignedVerdict:
    """§9.1 rule 5 — not a failure state.

    "It means the record moved on before a person got to it, and it re-enters
    the pipeline as a fresh retrieval."
    """
    return SignedVerdict(
        proposal=proposal,
        label=proposal.label,
        state=GateState.EXPIRED,
        confirmed_by="",
        confirmed_at=now or datetime.now(timezone.utc),
    )


def mark_unconfirmed(proposal: ProposedVerdict) -> ProposedVerdict:
    """Keep a proposal explicitly unconfirmed, for rendering."""
    return replace(proposal, state=GateState.PROPOSED)


def _require_reviewer(reviewer: str) -> None:
    if not reviewer.strip():
        raise GateViolation("sign-off requires a named reviewer")


def _require_open(proposal: ProposedVerdict) -> None:
    if proposal.state is not GateState.PROPOSED:
        raise GateViolation(
            f"verdict is already {proposal.state.value}; a gate whose decisions can be "
            "revisited in place is not a gate (§9.1)"
        )
