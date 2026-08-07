"""Stages 0-11, wired.

This module orchestrates; it decides nothing.  Every rule lives in the stage
that owns it, and the sequence here is the one §4 fixes.

Note what this function does *not* take: a :class:`ClaimantIdentity`.  It
takes a :class:`~engine.context.ClaimContext` and the claim text, which is
the whole of §9.8.1's split expressed as a signature.  Attribution reaches
presentation by another route and never passes through here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from engine.codes import LanguageCode
from engine.context import ClaimContext
from engine.custodians.base import CustodianAdapter
from engine.elements import (
    DerivedElement,
    Element,
    ElementKind,
    ElementStatus,
    VerifiedElement,
)
from engine.ids import ClaimId
from engine.packs.registry import PackRegistry
from engine.render.artifact import Artifact, DiscardEntry, RoutingNote
from engine.store.events import RetrievalStore
from engine.verification import (
    claim_verdict,
    decompose,
    derive,
    element_verdict,
    patterns,
    reconstruct,
    retrieve,
    route,
    scope_gate,
    sweep,
)
from engine.verification.claim_verdict import ProposedVerdict, Verdict
from engine.verification.sweep import SweepResult

# Kinds that compare figures across time, and therefore run the §9.5
# continuity check before any verdict is assigned.
_CROSS_TIME = frozenset({ElementKind.DIRECTION, ElementKind.SUPERLATIVE})


@dataclass(frozen=True, slots=True)
class VerificationRun:
    artifact: Artifact
    elements: tuple[Element, ...]
    derived: tuple[DerivedElement, ...]


def verify(
    claim_text: str,
    context: ClaimContext,
    registry: PackRegistry,
    adapters: dict[str, CustodianAdapter],
    store: RetrievalStore,
    *,
    now: datetime | None = None,
) -> VerificationRun:
    """Run a claim through the pipeline and return one indivisible artifact."""
    claim_id = ClaimId()

    decision = route.route(claim_text, context, registry)
    pack = decision.pack

    # Without a pack there is no lexicon, so nothing can be decomposed and
    # nothing derived. Interface §4.1 makes that Insufficient Data, and §7.5
    # requires it to render as an answer rather than as a failure.
    if pack is None:
        return _unrouted(claim_text, decision)

    lexicon = pack.lexicon(context.language) or pack.lexicon(LanguageCode("en"))
    if lexicon is None:
        return _unrouted(claim_text, decision)

    gate = scope_gate.classify(
        claim_text,
        lexicon.derivation_triggers.get(_evaluative(), ()),
        lexicon.derivation_triggers.get(_causal(), ()),
    )
    if not gate.in_scope:
        return _out_of_scope(claim_text, gate)

    elements = decompose.decompose(claim_text, claim_id, lexicon)
    anchoring_failures = decompose.verify_anchoring(elements, claim_text)
    if anchoring_failures:
        # §9.7.1 as extended: an element with no resolving span is
        # inadmissible and must not reach Stage 3.
        raise ValueError("; ".join(anchoring_failures))

    pull = None
    if decision.routed and decision.custodian_id in adapters:
        pull = retrieve.pull(
            decision.measure,
            pack.custodian(decision.custodian_id),
            adapters[decision.custodian_id],
            store,
            now=now,
            compares_across_time=any(e.kind in _CROSS_TIME for e in elements),
        )

    assigned: list[Element] = []
    reasons: dict[str, str] = {}
    for element in elements:
        outcome = element_verdict.assign(element, decision.measure, pull, claim_text)
        assigned.append(outcome.element)
        reasons[outcome.element.id.value] = outcome.reason

    figure = pull.retrievals[-1].as_figure() if pull and pull.retrievals else None
    measure_name = decision.measure.name if decision.measure else ""
    verified = frozenset(
        VerifiedElement(e, measure_name, figure)
        for e in assigned
        if e.status is ElementStatus.VERIFIED
    )
    rebuilt = reconstruct.reconstruct(verified, lexicon)

    discarded = tuple(e for e in assigned if e.status is not ElementStatus.VERIFIED)
    sweep_result = (
        sweep.run(
            decision.measure,
            pull.retrievals,
            claimed_rise=_claimed_rise(claim_text),
            discarded=discarded,
        )
        if pull and pull.retrievals and decision.measure
        else SweepResult(ran=False, reason_not_run="no series was retrieved")
    )

    proposed = claim_verdict.evaluate(
        tuple(assigned),
        sweep_result,
        routed=decision.routed,
        reconstructs=rebuilt.does_reconstruct,
    )

    derived_elements = derive.derive(claim_text, claim_id, lexicon, tuple(assigned))

    artifact = Artifact(
        claim_text=claim_text,
        _reconstruction=rebuilt.text,
        does_reconstruct=rebuilt.does_reconstruct,
        element_set_hash=rebuilt.element_set_hash,
        ledger=tuple(
            DiscardEntry(
                fragment=e.fragment,
                status=e.status.value if e.status else "unresolved",
                reason=reasons.get(e.id.value, ""),
            )
            for e in discarded
        ),
        verdict=proposed,
        sweep=sweep_result,
        citations=pull.retrievals if pull else (),
        routing=(
            (
                RoutingNote(
                    measure=decision.measure.name,
                    custodian=decision.custodian_id or "",
                    rationale=decision.rationale,
                    alternatives_considered=decision.alternatives_considered,
                ),
            )
            if decision.routed and decision.measure
            else ()
        ),
        derived=derived_elements,
        unconfirmed_marker="UNCONFIRMED — proposed, not signed off",
    )
    return VerificationRun(artifact, tuple(assigned), derived_elements)


def _claimed_rise(claim_text: str) -> bool | None:
    if patterns.RISE.search(claim_text):
        return True
    if patterns.FALL.search(claim_text):
        return False
    return None


def _causal():
    from engine.elements import DerivationOperation

    return DerivationOperation.CAUSAL_DISCHARGE


def _evaluative():
    from engine.elements import DerivationOperation

    return DerivationOperation.EVALUATIVE_DISCHARGE


def _unrouted(claim_text: str, decision: route.RoutingDecision) -> VerificationRun:
    verdict = ProposedVerdict(
        Verdict.INSUFFICIENT_DATA,
        decision.rationale
        or "No custodian of record settles this claim. This is an answer, not a "
        "failure to produce one.",
    )
    return VerificationRun(
        Artifact(
            claim_text=claim_text,
            _reconstruction="",
            does_reconstruct=False,
            element_set_hash="",
            ledger=(),
            verdict=verdict,
            sweep=SweepResult(ran=False, reason_not_run="no series was retrieved"),
            unconfirmed_marker="UNCONFIRMED — proposed, not signed off",
        ),
        (),
        (),
    )


def _out_of_scope(claim_text: str, gate: scope_gate.ScopeOutcome) -> VerificationRun:
    """§4 Stage 1 — routed out with an explanation, and no verdict."""
    verdict = ProposedVerdict(Verdict.INSUFFICIENT_DATA, gate.explanation)
    return VerificationRun(
        Artifact(
            claim_text=claim_text,
            _reconstruction="",
            does_reconstruct=False,
            element_set_hash="",
            ledger=(
                DiscardEntry(
                    fragment=claim_text,
                    status="out_of_scope",
                    reason=gate.explanation,
                ),
            ),
            verdict=verdict,
            sweep=SweepResult(
                ran=False, reason_not_run="the claim did not pass the scope gate"
            ),
            unconfirmed_marker="UNCONFIRMED — proposed, not signed off",
        ),
        (),
        (),
    )
