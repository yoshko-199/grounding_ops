"""Stage 6 — element verdicts.

Spec §4: "Assign one status per element (see §6.1), applying the tolerance
bands (§9.2). Automated and final."  §6.1 adds: "Element statuses are
assigned automatically and are final on retrieval. They are not subject to
the sign-off gate, and sign-off cannot alter them."

The ordering below is not incidental.  Continuity is checked before the
numeric comparison, because a spliced comparison "would verify cleanly as
arithmetic against the published figures" — the arithmetic is not what is
wrong with it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from engine.elements import Element, ElementKind, ElementStatus, ToleranceBand
from engine.packs.schema import Measure
from engine.verification import patterns, tolerance
from engine.verification.retrieve import PullOutcome


@dataclass(frozen=True, slots=True)
class ElementOutcome:
    element: Element
    reason: str
    rounded: bool = False


def assign(
    element: Element,
    measure: Measure | None,
    pull: PullOutcome | None,
    claim_text: str,
) -> ElementOutcome:
    """Assign a final status to one element."""
    if element.is_out_of_scope:
        return _out_of_scope(element)

    if pull is None or measure is None:
        return _settled(
            element,
            ElementStatus.UNVERIFIED,
            "no measure was bound for this element, so no custodian was consulted",
        )

    if pull.blocked_status is not None:
        return _settled(element, pull.blocked_status, pull.detail,
                        continuity=pull.continuity.status)

    if not pull.has_data:
        return _settled(element, ElementStatus.UNVERIFIED,
                        "the custodian was reached and publishes no covering figure",
                        continuity=pull.continuity.status)

    # §9.5 — never Verified across an unlinked break. Checked before the
    # comparison, because the comparison would succeed.
    if pull.continuity.blocks_verification:
        return _settled(
            element,
            ElementStatus.CONTESTED_BY_DEFINITION,
            pull.continuity.caveat or "comparison spans an unlinked series break",
            continuity=pull.continuity.status,
        )

    if element.kind is ElementKind.DIRECTION:
        return _direction(element, pull, claim_text)
    if element.kind is ElementKind.SUPERLATIVE:
        return _superlative(element, pull)
    return _quantity(element, measure, pull)


def _out_of_scope(element: Element) -> ElementOutcome:
    """§2's exclusions, and the reason each one exists.

    These fragments are not discarded silently. They carry into the discard
    ledger, and §9.6 routes the causal one to Stage 9 as a derived element
    tagged `implied-by-original-only` — which §6.3 calls the most
    analytically valuable output of the whole system.
    """
    reasons = {
        ElementKind.OPINION: (
            "evaluative language; no truth value to check against a record"
        ),
        ElementKind.PREDICTION: "a claim about the future; no record exists yet",
        ElementKind.CAUSAL: (
            "a causal link. No institution publishes the share of an outcome "
            "attributable to a cause, so there is no figure to retrieve. Establishing "
            "it would require a model, and the choice of model would choose the answer"
        ),
    }
    return ElementOutcome(
        replace(element, status=ElementStatus.OUT_OF_SCOPE),
        reasons.get(element.kind, "outside the scope of custodial verification"),
    )


def _direction(element: Element, pull: PullOutcome, claim_text: str) -> ElementOutcome:
    """§9.2 — binary on sign, at any magnitude."""
    claimed_rise = bool(patterns.RISE.search(element.fragment))
    if not claimed_rise and not patterns.FALL.search(element.fragment):
        claimed_rise = bool(patterns.RISE.search(claim_text))

    first = pull.observations[0].value
    last = pull.observations[-1].value
    holds = tolerance.direction_holds(claimed_rise, first, last)
    direction = "a rise" if claimed_rise else "a fall"
    movement = "rose" if last > first else ("fell" if last < first else "did not move")

    return _settled(
        element,
        ElementStatus.VERIFIED if holds else ElementStatus.CONTRADICTED,
        f"the claim asserts {direction}; over the retrieved span the series {movement}",
        band=ToleranceBand.A if holds else ToleranceBand.C,
        continuity=pull.continuity.status,
    )


def _superlative(element: Element, pull: PullOutcome) -> ElementOutcome:
    """§9.2 — binary against the full series. No tolerance.

    "A claim that something is the highest ever is not 97% correct when it is
    the third highest."
    """
    values = [o.value for o in pull.observations]
    latest = values[-1]
    fragment = element.fragment.lower()

    if any(word in fragment for word in ("lowest", "worst", "least")):
        holds = latest == min(values)
        target = "lowest"
    else:
        holds = latest == max(values)
        target = "highest"

    return _settled(
        element,
        ElementStatus.VERIFIED if holds else ElementStatus.CONTRADICTED,
        (
            f"checked against the full retrieved series: the most recent observation "
            f"{'is' if holds else 'is not'} the {target} in it"
        ),
        band=ToleranceBand.A if holds else ToleranceBand.C,
        continuity=pull.continuity.status,
    )


def _quantity(element: Element, measure: Measure, pull: PullOutcome) -> ElementOutcome:
    """§9.2's numeric bands, or Unverified where the fragment states no figure."""
    claimed = _claimed_value(element.fragment)
    if claimed is None:
        # A time period or an unquantified fragment. It anchors the retrieval
        # but asserts no figure of its own to compare.
        return _settled(
            element,
            ElementStatus.VERIFIED,
            "the period is covered by the retrieved series",
            band=ToleranceBand.A,
            continuity=pull.continuity.status,
        )

    latest = pull.observations[-1]
    outcome = tolerance.band_for(
        claimed,
        latest.value,
        published_precision=Decimal(str(measure.published_precision)),
        discrete=measure.discrete,
        kind=element.kind,
    )
    return ElementOutcome(
        replace(
            element,
            status=outcome.status,
            tolerance_band=outcome.band,
            continuity_status=pull.continuity.status,
        ),
        (
            f"claim states {claimed}; {measure.name} published {latest.value} for "
            f"{latest.reference_period} (band {outcome.band.value})"
        ),
        rounded=outcome.rounded,
    )


def _claimed_value(fragment: str) -> Decimal | None:
    match = patterns.NUMBER.search(fragment)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None


def _settled(
    element: Element,
    status: ElementStatus,
    reason: str,
    *,
    band: ToleranceBand | None = None,
    continuity=None,
) -> ElementOutcome:
    return ElementOutcome(
        replace(element, status=status, tolerance_band=band, continuity_status=continuity),
        reason,
    )
