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
from engine.packs.schema import Lexicon, Measure, SurfaceCategory
from engine.verification import patterns, tolerance
from engine.verification.retrieve import PullOutcome


#: The reason an element carries when the claim states its figure in a unit
#: other than the one its measure is published in. A fixed string, because the
#: bottom line recognises it to say the same thing in plain words.
UNIT_MISMATCH = (
    "the claim states this figure in a different unit from the one the custodian "
    "publishes it in. It is not converted, because a converted figure is one no "
    "retrieval supports, so it was not compared"
)


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
    lexicon: Lexicon,
) -> ElementOutcome:
    """Assign a final status to one element."""
    if element.is_out_of_scope:
        return _out_of_scope(element)

    if measure is None:
        return _settled(
            element,
            ElementStatus.UNVERIFIED,
            "no measure was bound for this element, so no custodian was consulted",
        )

    if pull is None:
        # A measure bound and a custodian named, but no retrieval happened —
        # this deployment has no adapter for that custodian. That is a fact
        # about what this session can reach, not about what the record holds,
        # so it is Unreachable. §6.1 keeps the two apart and AC-14 asserts
        # neither collapses into the other; reporting it as Unverified would
        # say the custodian publishes nothing covering the element, which is
        # a claim about the world that nobody checked.
        #
        # Found by admitting the first real pack: a pack can name a custodian
        # the code has no client for, which no fixture jurisdiction could
        # produce because fixtures ship their own adapters.
        return _settled(
            element,
            ElementStatus.UNREACHABLE,
            (
                f"{measure.name} was bound, and no client is configured for its "
                "custodian in this deployment, so the record was never consulted. "
                "This is a gap in what can be reached, not a finding about what "
                "is published"
            ),
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

    if element.kind is ElementKind.TIME_PERIOD:
        return _time_period(element, pull)

    if element.kind is ElementKind.DIRECTION:
        return _direction(element, pull, claim_text, lexicon)
    if element.kind is ElementKind.SUPERLATIVE:
        return _superlative(element, pull)
    return _quantity(element, measure, pull, lexicon)


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


def _direction(
    element: Element, pull: PullOutcome, claim_text: str, lexicon: Lexicon
) -> ElementOutcome:
    """§9.2 — binary on sign, at any magnitude."""
    vocabulary = lexicon.surface_vocabulary
    rise, fall = vocabulary[SurfaceCategory.RISE], vocabulary[SurfaceCategory.FALL]
    claimed_rise = patterns.matches_any(element.fragment, rise)
    if not claimed_rise and not patterns.matches_any(element.fragment, fall):
        claimed_rise = patterns.matches_any(claim_text, rise)

    first = pull.observations[0].value
    last = pull.observations[-1].value
    holds = tolerance.direction_holds(claimed_rise, first, last)
    direction = "a rise" if claimed_rise else "a fall"
    movement = "rose" if last > first else ("fell" if last < first else "did not move")

    return _settled(
        element,
        ElementStatus.VERIFIED if holds else ElementStatus.CONTRADICTED,
        f"the claim asserts {direction}; over the retrieved span the series {movement}. "
        "The figures are in the citation record",
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


def _quantity(
    element: Element, measure: Measure, pull: PullOutcome, lexicon: Lexicon
) -> ElementOutcome:
    """§9.2's numeric bands, or Unverified where the fragment states no figure."""
    claimed, stated = _claimed(element.fragment, lexicon)
    if claimed is not None and any(unit != measure.unit for unit in stated):
        # Interface v1.6, and v1.7 for a unit written before the numeral.
        # Every unit the claim states must be the measure's: "£4.2 percent"
        # names two, and comparing it would mean choosing which one the
        # claimant meant. Checked before the bands, because the bands would
        # answer: 212 against a Celsius series is far outside tolerance, and a
        # true statement would come back contradicted. Converting is not an
        # option either — the converted figure would be one nobody published.
        # So the element is not compared, and says why.
        return _settled(
            element, ElementStatus.UNVERIFIED, UNIT_MISMATCH,
            continuity=pull.continuity.status,
        )
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

    # Both sides at the same scale (interface v1.8). The claim's figure was
    # already scaled by its scale word; the published figure and its precision
    # are scaled by the measure's declared published_scale. Exact powers of
    # ten, and internal: neither scaled figure is ever rendered. The output
    # quotes the claim as written and cites the figure as published.
    scale = measure.published_scale.exponent
    latest = pull.observations[-1]
    outcome = tolerance.band_for(
        claimed,
        latest.value.scaleb(scale),
        published_precision=Decimal(str(measure.published_precision)).scaleb(scale),
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
            f"the claim's figure was compared against {measure.name} as published, and "
            f"falls in band {outcome.band.value}. Both figures and the reference period "
            "are in the citation record"
        ),
        rounded=outcome.rounded,
    )


def _claimed(fragment: str, lexicon: Lexicon) -> tuple[Decimal | None, tuple[str, ...]]:
    """The claim's figure at its stated scale, and every unit it names.

    Read exactly as decomposition read it (``patterns.read_quantity``): a
    unit before the numeral (v1.7), a scale word after it (v1.8), a unit
    after that (v1.6). "£5bn" is five times ten to the ninth, in pounds.
    The scaled value keeps the precision the claimant used: five billion is
    "to the nearest billion", which is what §9.2's rounding test reads.
    """
    match = patterns.NUMBER.search(fragment)
    if not match:
        return None, ()
    reading = patterns.read_quantity(fragment, match, lexicon)
    try:
        value = Decimal(match.group(1).replace(",", "")).scaleb(reading.exponent)
    except InvalidOperation:
        return None, reading.units
    return value, reading.units


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


def _time_period(element: Element, pull: PullOutcome) -> ElementOutcome:
    """A period scopes the comparison; it is not a figure to compare.

    This branch exists because its absence produced the worst class of error
    the system can make. A time period was decomposed as a
    :attr:`~engine.elements.ElementKind.QUANTITY`, so a claim like
    "unemployment fell in 2021" had the *year* pulled out as the claimant's
    figure and compared against the unemployment rate. Two thousand and
    twenty-one does not equal four point two, so the element came back
    Contradicted and the claim was labelled Substantially Inaccurate — with a
    full citation trail behind it, on a claim the record supports.

    That is a confident, fully-sourced, wrong answer about a true statement,
    which is precisely what §3 and the whole verdict apparatus exist to
    prevent. It bit any claim whose period named a year.

    What a period *can* be checked for is coverage: whether the retrieved
    series actually spans the period the claim scopes itself to. A claim about
    a year the custodian does not cover is Unverified, and that is a real
    finding rather than an arithmetic accident.
    """
    named = {m.group(0) for m in patterns.YEAR.finditer(element.fragment)}
    if not named:
        return _settled(
            element,
            ElementStatus.VERIFIED,
            "a relative period, carried as the scope of the comparison rather than "
            "as a figure to check",
            continuity=pull.continuity.status,
        )

    covered = {
        observation.reference_period[:4]
        for observation in pull.observations
        if observation.reference_period
    }
    missing = sorted(named - covered)
    if missing:
        return _settled(
            element,
            ElementStatus.UNVERIFIED,
            # The year is deliberately not interpolated. A reason is prose, and
            # §3 admits no figure into prose that no retrieval supports — AC-7
            # caught three such leaks during the original build and this was a
            # fourth, added by the fix above and found by shape fuzzing. The
            # ledger already shows the fragment beside this reason, quoted from
            # the claim, so naming the year here adds nothing but a crash.
            "the custodian was reached and the retrieved series does not cover the "
            "period this claim names. A period the record does not span cannot "
            "scope a comparison",
            continuity=pull.continuity.status,
        )

    return _settled(
        element,
        ElementStatus.VERIFIED,
        "the retrieved series covers this period. A period scopes the comparison "
        "and is not itself compared against a figure",
        continuity=pull.continuity.status,
    )
