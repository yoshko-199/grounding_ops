"""Stage 1 — the scope gate.

Spec §4: "Classify: quantitative/administrative → proceed. Opinion /
prediction / causal / no-custodian → route out with explanation, no verdict."

The gate operates on the claim, not on its fragments.  A claim with a
verifiable core and a causal wrapper proceeds — the wrapper becomes an
out-of-scope element at Stage 2 and a derived element at Stage 9, which is
§9.6's whole worked example.  A claim with no verifiable core at all does not
proceed, and receives an explanation rather than a verdict.

§2's fourth exclusion is the load-bearing one and the reason this stage is
not merely a filter: historical-interpretive claims have no authoritative
custodian, so "verification" of them "would be argument wearing a
verification badge".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from engine.elements import DerivationOperation
from engine.packs.schema import Lexicon, SurfaceCategory
from engine.verification import patterns


class OutOfScopeReason(Enum):
    OPINION = "opinion"
    PREDICTION = "prediction"
    CAUSAL_ONLY = "causal_only"
    NO_QUANTITATIVE_CONTENT = "no_quantitative_content"


@dataclass(frozen=True, slots=True)
class ScopeOutcome:
    in_scope: bool
    reason: OutOfScopeReason | None = None
    explanation: str = ""


_EXPLANATIONS = {
    OutOfScopeReason.OPINION: (
        "This is an evaluative statement. It has no truth value to check against a "
        "record, so no verdict is issued."
    ),
    OutOfScopeReason.PREDICTION: (
        "This is a claim about the future. No record exists yet, so there is nothing "
        "to verify it against."
    ),
    OutOfScopeReason.CAUSAL_ONLY: (
        "This is a causal claim. No institution publishes the share of an outcome "
        "attributable to a given cause, so there is no figure to retrieve. Adjacent "
        "administrative facts may be checkable; the attribution is not."
    ),
    OutOfScopeReason.NO_QUANTITATIVE_CONTENT: (
        "This claim contains no quantity or administrative fact with an authoritative "
        "custodian, so there is nothing for the pipeline to bind to a measure."
    ),
}


def classify(claim_text: str, lexicon: Lexicon) -> ScopeOutcome:
    """Classify a claim for scope.

    Evaluative and causal triggers, and the rise/fall/prediction vocabulary
    below, all come from the pack lexicon (interface §3.6) rather than from
    this module, so that adding a language is adding pack data rather than
    changing this function.
    """
    lowered = claim_text.lower()
    vocabulary = lexicon.surface_vocabulary
    rise = vocabulary[SurfaceCategory.RISE]
    fall = vocabulary[SurfaceCategory.FALL]

    has_quantity = bool(patterns.NUMBER.search(claim_text))
    has_direction = patterns.matches_any(claim_text, rise) or patterns.matches_any(claim_text, fall)
    has_period = bool(patterns.TIME_PERIOD.search(claim_text))
    quantitative = has_quantity or has_direction or has_period

    if patterns.matches_any(
        claim_text, vocabulary[SurfaceCategory.PREDICTION]
    ) and not _has_past_anchor(claim_text, rise, fall):
        return _out(OutOfScopeReason.PREDICTION)

    if not quantitative:
        causal_triggers = lexicon.derivation_triggers.get(DerivationOperation.CAUSAL_DISCHARGE, ())
        evaluative_triggers = lexicon.derivation_triggers.get(
            DerivationOperation.EVALUATIVE_DISCHARGE, ()
        )
        causal = any(t in lowered for t in causal_triggers)
        evaluative = any(t in lowered for t in evaluative_triggers)
        if causal:
            return _out(OutOfScopeReason.CAUSAL_ONLY)
        if evaluative:
            return _out(OutOfScopeReason.OPINION)
        return _out(OutOfScopeReason.NO_QUANTITATIVE_CONTENT)

    return ScopeOutcome(in_scope=True)


def _has_past_anchor(
    claim_text: str, rise: tuple[str, ...], fall: tuple[str, ...]
) -> bool:
    """Whether the claim also asserts something about the record.

    "Inflation rose last year and will rise again" contains a checkable
    element and a prediction. Routing the whole claim out because of the
    second half would discard a verifiable assertion; the prediction becomes
    an out-of-scope element at Stage 2 instead.
    """
    return bool(patterns.TIME_PERIOD.search(claim_text)) and (
        patterns.matches_any(claim_text, rise) or patterns.matches_any(claim_text, fall)
    )


def _out(reason: OutOfScopeReason) -> ScopeOutcome:
    return ScopeOutcome(in_scope=False, reason=reason, explanation=_EXPLANATIONS[reason])
