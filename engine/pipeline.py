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
        # Its own reason, not the routing decision's. Routing may well have
        # *succeeded* by this point, so reusing its rationale made the verdict
        # say "bound to <measure> on the measure's published name" for a claim
        # that failed because the pack declares no lexicon for its language —
        # a confident sentence about the wrong thing entirely.
        return _unrouted(
            claim_text,
            decision,
            reason=(
                f"the pack for {decision.jurisdiction} declares no lexicon for "
                f"{context.language} and no English fallback, so the claim could not "
                "be decomposed. Interface §3.6: a language declared without a lexicon "
                "under-fires silently, and under-firing invisibly is worse than "
                "declining visibly"
            ),
        )

    # Decomposition precedes the scope gate's branch. §9.10: a claim routed out
    # at Stage 1 still surfaces its derived elements, so the elements they are
    # tagged against have to exist before that branch is taken.
    elements = decompose.decompose(claim_text, claim_id, lexicon)
    anchoring_failures = decompose.verify_anchoring(elements, claim_text)
    if anchoring_failures:
        # §9.7.1 as extended: an element with no resolving span is
        # inadmissible and must not reach Stage 3.
        raise ValueError("; ".join(anchoring_failures))

    gate = scope_gate.classify(
        claim_text,
        lexicon.derivation_triggers.get(_evaluative(), ()),
        lexicon.derivation_triggers.get(_causal(), ()),
    )
    if not gate.in_scope:
        return _out_of_scope(claim_text, claim_id, gate, elements, lexicon)

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

    # Where routing failed for a reason it can state, say that reason rather
    # than the generic one. §6.1 requires a contested binding to be reported
    # with "the definitional gap explained", and the gap is precisely what the
    # routing rationale holds — which two measures matched equally well, and
    # that they measure different things. Reporting "no custodian settles
    # this" instead is true and useless: it hides that two custodians settle
    # neighbouring questions and the claim did not say which it meant.
    #
    # The path existed and was never taken. No fixture claim produces a tie,
    # so this surfaced only once a real pack declared sibling measures.
    if (
        decision.failure in _READER_FACING
        and decision.rationale
        and proposed.label is Verdict.INSUFFICIENT_DATA
    ):
        proposed = ProposedVerdict(proposed.label, _as_answer(decision.rationale))

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


#: Routing failures whose rationale is written for a reader, and may
#: therefore replace the generic verdict sentence. The others are operator
#: diagnostics: NO_ROUTING_RULE's rationale ends "a pack defect to be filed",
#: which is true, useful in a log, and not something to hand someone asking
#: whether a claim checks out. Same split as PullOutcome.diagnostic — the text
#: stays on the decision, it just does not render.
_READER_FACING = frozenset(
    {
        route.RoutingFailure.CONTESTED_BY_DEFINITION,
        route.RoutingFailure.NO_MEASURE,
    }
)

#: §7.5's framing, which every Insufficient Data rationale keeps whatever
#: else it says. AC-5 caught this being dropped: replacing the generic
#: rationale with a specific one explained the gap and stopped calling the
#: outcome an answer, and the criterion is about exactly that framing.
_ANSWER_NOT_FAILURE = "This is an answer, not a failure to produce one."


def _as_answer(rationale: str) -> str:
    """A specific reason, still framed as an answer rather than a failure."""
    reason = rationale.strip()
    if not reason.endswith("."):
        reason += "."
    if "not a failure" in reason:
        return reason
    return f"{reason} {_ANSWER_NOT_FAILURE}"


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


def _unrouted(
    claim_text: str,
    decision: route.RoutingDecision,
    reason: str | None = None,
) -> VerificationRun:
    """Insufficient Data before a pack or a lexicon was available.

    The rationale goes through :func:`_as_answer` like every other one. It did
    not, and so the no-jurisdiction and no-pack verdicts silently lost §7.5's
    framing — the exact regression AC-5 exists to catch, one function away
    from the helper written to prevent it.
    """
    verdict = ProposedVerdict(
        Verdict.INSUFFICIENT_DATA,
        _as_answer(
            reason
            or decision.rationale
            or "No custodian of record settles this claim"
        ),
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


def _out_of_scope(
    claim_text: str,
    claim_id: ClaimId,
    gate: scope_gate.ScopeOutcome,
    elements: tuple[Element, ...],
    lexicon,
) -> VerificationRun:
    """§4 Stage 1 — routed out with an explanation, and no verdict.

    §9.10: routed out is not the same as gone silent. Decomposition and
    derivation still run, so the artifact carries its discard ledger and the
    implications the claim invites a reader to draw. §6.3 calls
    `implied-by-original-only` the most analytically valuable output in the
    system, and a claim whose entire content is a rhetorical move is exactly
    where that is true.

    No retrieval is attempted, and that restraint is the point. The claim bound
    no measure; a series pulled to display beside it would put a custodian's
    figure next to a proposition the figure does not address, which is §9.6's
    shape reached by a different route. The prior art this design draws on
    presents baseline data here — defensible for an analyst exercising
    judgment about relevance, and not for a pipeline with no such judgment.
    """
    assigned: list[Element] = []
    reasons: dict[str, str] = {}
    for element in elements:
        outcome = element_verdict.assign(element, None, None, claim_text)
        assigned.append(outcome.element)
        reasons[outcome.element.id.value] = outcome.reason

    derived_elements = derive.derive(claim_text, claim_id, lexicon, tuple(assigned))

    ledger = tuple(
        DiscardEntry(
            fragment=element.fragment,
            status=element.status.value if element.status else "unresolved",
            reason=reasons.get(element.id.value, ""),
        )
        for element in assigned
    )
    if not ledger:
        # Nothing decomposed. The claim itself is the discarded unit, and an
        # empty ledger would read as "nothing was removed" when everything was.
        ledger = (
            DiscardEntry(
                fragment=claim_text, status="out_of_scope", reason=gate.explanation
            ),
        )

    return VerificationRun(
        Artifact(
            claim_text=claim_text,
            _reconstruction="",
            does_reconstruct=False,
            element_set_hash="",
            ledger=ledger,
            verdict=ProposedVerdict(Verdict.INSUFFICIENT_DATA, gate.explanation),
            sweep=SweepResult(
                ran=False, reason_not_run="the claim did not pass the scope gate"
            ),
            derived=derived_elements,
            unconfirmed_marker="UNCONFIRMED — proposed, not signed off",
        ),
        tuple(assigned),
        derived_elements,
    )
