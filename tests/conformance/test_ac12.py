"""AC-12 — Break integrity.

Constraint: spec §9.5.  No verification by splicing.

The Israel pack's §5 explains why this runs before the element verdict rather
than after: a restructured budget line "appears as a spending collapse or
explosion, and a coverage onset appears as explosive growth. Both would verify
cleanly as arithmetic against the published figures."  The arithmetic is not
what is wrong with a spliced comparison.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from engine.elements import ContinuityStatus, Element, ElementKind, ElementStatus
from engine.ids import ClaimId, ElementId
from engine.packs.schema import SeriesBreak, BreakKind
from engine.spans import Span
from engine.verification import continuity, element_verdict, retrieve

CLAIM = "output rose over the last three years"


def _element(kind: ElementKind = ElementKind.DIRECTION) -> Element:
    start = CLAIM.index("rose")
    return Element(
        id=ElementId(),
        claim_id=ClaimId(),
        fragment="rose",
        span=Span(start, start + 4),
        kind=kind,
    )


def test_span_crossing_no_break_proceeds(pack) -> None:
    measure = pack.measure("price_index")
    outcome = continuity.check(measure, date(2021, 1, 1), date(2021, 12, 1))
    assert outcome.status is ContinuityStatus.NO_BREAK_CROSSED
    assert not outcome.blocks_verification


def test_span_crossing_a_break_with_a_linked_series_uses_it(pack) -> None:
    measure = pack.measure("price_index")
    outcome = continuity.check(measure, date(2019, 6, 1), date(2020, 6, 1))
    assert outcome.status is ContinuityStatus.LINKED_SERIES_USED
    assert outcome.linked_series_used == "ZZ-PRICE-LINKED"
    assert not outcome.blocks_verification


def test_span_crossing_an_unlinked_break_never_verifies(pack) -> None:
    measure = pack.measure("output_index")
    outcome = continuity.check(measure, date(2019, 1, 1), date(2019, 12, 1))
    assert outcome.status is ContinuityStatus.UNLINKED_BREAK
    assert outcome.blocks_verification
    assert "not comparable" in (outcome.caveat or "")


def test_element_across_an_unlinked_break_is_not_verified(pack, adapters, store) -> None:
    """The integration path. The arithmetic would have succeeded."""
    measure = pack.measure("output_index")
    custodian = pack.custodian("zzstat")
    pull = retrieve.pull(
        measure, custodian, adapters["zzstat"], store, compares_across_time=True
    )
    assert pull.continuity.status is ContinuityStatus.UNLINKED_BREAK

    outcome = element_verdict.assign(_element(), measure, pull, CLAIM)
    assert outcome.element.status is ElementStatus.CONTESTED_BY_DEFINITION
    assert outcome.element.status is not ElementStatus.VERIFIED

    # And the series genuinely does rise across the break, so a naive
    # implementation would have Verified it.
    assert pull.observations[-1].value > pull.observations[0].value


def test_linked_series_is_used_and_recorded(pack, adapters, store) -> None:
    """"Use the linked series; record which, in retrievals.linked_series_used"."""
    measure = replace(
        pack.measure("price_index"),
        series_breaks=(
            SeriesBreak(
                effective_date=date(2021, 6, 1),
                kind=BreakKind.BASE_YEAR,
                custodian_notice_ref="ZZ Statistical Office, Fixture Notice on Rebasing",
                linked_series_available=True,
                linked_series_identifier="ZZ-PRICE-LINKED",
            ),
        ),
    )
    pull = retrieve.pull(
        measure, pack.custodian("zzstat"), adapters["zzstat"], store,
        compares_across_time=True,
    )
    assert pull.continuity.status is ContinuityStatus.LINKED_SERIES_USED
    assert all(r.linked_series_used == "ZZ-PRICE-LINKED" for r in pull.retrievals)
    assert all(o.series_id == "ZZ-PRICE-LINKED" for o in pull.observations)


def test_a_partially_linked_span_is_still_unlinked(pack) -> None:
    """A linked series covering one of two breaks still leaves a fabricated join."""
    measure = replace(
        pack.measure("price_index"),
        series_breaks=(
            SeriesBreak(
                effective_date=date(2021, 3, 1),
                kind=BreakKind.BASE_YEAR,
                custodian_notice_ref="notice A",
                linked_series_available=True,
                linked_series_identifier="ZZ-PRICE-LINKED",
            ),
            SeriesBreak(
                effective_date=date(2021, 9, 1),
                kind=BreakKind.METHODOLOGY,
                custodian_notice_ref="notice B",
                linked_series_available=False,
            ),
        ),
    )
    outcome = continuity.check(measure, date(2021, 1, 1), date(2021, 12, 1))
    assert outcome.status is ContinuityStatus.UNLINKED_BREAK
    assert outcome.blocks_verification


def test_every_declared_break_cites_a_custodian_notice(pack) -> None:
    """A heuristic-detected break may flag for review; it may not enter the register."""
    for measure in pack.measures:
        for entry in measure.series_breaks:
            assert entry.custodian_notice_ref.strip(), (
                f"{measure.id}: a register entry without a custodian notice is a "
                "suspicion, not a fact about the series (§9.5)"
            )
