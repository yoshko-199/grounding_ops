"""Claim-level verdict labels and the proposal that carries one.

Split out of :mod:`engine.verification.claim_verdict` so that the sign-off
gate can name a verdict without importing its way to the evidence.

That is not tidiness. §9.1 rule 2 restricts the gate to the claim-level label
and nothing beneath it, and AC-10 tests that a reviewer cannot "reach past the
verdict to the evidence underneath". Reachability is the enforceable form of
that restriction: this module imports only :mod:`engine.elements`, so
:mod:`engine.signoff` has no import path to a retrieval store, a pack, or a
sweep — and therefore no route to mutate any of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from engine.elements import GateState


class Verdict(Enum):
    """§6.2, applied to the reconstructed claim."""

    ACCURATE = "accurate"
    SUBSTANTIALLY_INACCURATE = "substantially_inaccurate"
    MISLEADING = "misleading"
    FALSE = "false"
    INDETERMINATE = "indeterminate"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class ProposedVerdict:
    """A verdict as it leaves the pipeline: proposed, never final.

    §9.1: "A ``proposed`` verdict renders visibly marked as unconfirmed and
    cannot export."  The state is carried on the value rather than tracked
    beside it, so nothing can render a verdict without also holding its state.
    """

    label: Verdict
    rationale: str
    state: GateState = GateState.PROPOSED
    capped: bool = False
    cap_reason: str = ""

    @property
    def is_final(self) -> bool:
        return self.state in (GateState.CONFIRMED, GateState.AMENDED)

    @property
    def exportable(self) -> bool:
        return self.state in (GateState.CONFIRMED, GateState.AMENDED)
