"""AC-13 — Tolerance determinism.

Constraint: spec §9.2.  Tolerance is derived, never chosen.

"Assert the assigned band is a pure function of ``published_precision``,
``unit``, and ``discrete`` from the pack. Assert no per-claim, per-claimant,
or per-session input affects the band."
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from engine.elements import ElementKind, ElementStatus, ToleranceBand
from engine.verification.tolerance import band_for, direction_holds

PRECISION = Decimal("0.1")


def _band(claim: str, published: str, **kwargs) -> ToleranceBand:
    return band_for(
        Decimal(claim),
        Decimal(published),
        published_precision=kwargs.get("precision", PRECISION),
        discrete=kwargs.get("discrete", False),
        kind=kwargs.get("kind", ElementKind.QUANTITY),
    ).band


def test_band_is_a_pure_function_of_pack_data() -> None:
    """No parameter admits a claimant, a session, or an operator preference."""
    parameters = set(inspect.signature(band_for).parameters)
    assert parameters == {
        "claim_value",
        "published_value",
        "published_precision",
        "discrete",
        "kind",
    }


def test_same_figures_yield_the_same_band_every_time() -> None:
    """Determinism, and a worked reading of §9.2's arithmetic.

    Against a published 103.8 at precision 0.1, the relative floor dominates:
    Band A admits max(0.05, 0.519) and Band B admits max(0.1, 2.076). That is
    the rule adapting to the measure's scale rather than to a chosen
    threshold, which is the whole point of deriving the band from published
    precision instead of picking round numbers.
    """
    for _ in range(5):
        assert _band("103.8", "103.8") is ToleranceBand.A
        assert _band("104.0", "103.8") is ToleranceBand.A  # inside 0.5% relative
        assert _band("104.8", "103.8") is ToleranceBand.B  # inside 2%, outside 0.5%
        assert _band("120.0", "103.8") is ToleranceBand.C


def test_band_a_admits_a_half_step_of_published_precision() -> None:
    assert _band("103.85", "103.8") is ToleranceBand.A
    assert band_for(
        Decimal("103.85"), Decimal("103.8"),
        published_precision=PRECISION, discrete=False, kind=ElementKind.QUANTITY,
    ).status is ElementStatus.VERIFIED


def test_band_b_verifies_but_carries_the_rounded_tag() -> None:
    """§9.2: "A claim that is right to within a rounding step is not wrong,
    but the reader should be able to see that it was not exact."."""
    outcome = band_for(
        Decimal("104.8"), Decimal("103.8"),
        published_precision=PRECISION, discrete=False, kind=ElementKind.QUANTITY,
    )
    assert outcome.band is ToleranceBand.B
    assert outcome.status is ElementStatus.VERIFIED
    assert outcome.rounded
    assert outcome.tag == "rounded"


def test_band_a_admits_a_claim_stated_at_coarser_precision() -> None:
    """"Four percent" against a published four point two is correct at the
    precision the claimant used."""
    assert _band("104", "103.8") is ToleranceBand.A


def test_band_c_contradicts() -> None:
    outcome = band_for(
        Decimal("150.0"), Decimal("103.8"),
        published_precision=PRECISION, discrete=False, kind=ElementKind.QUANTITY,
    )
    assert outcome.band is ToleranceBand.C
    assert outcome.status is ElementStatus.CONTRADICTED
    assert not outcome.rounded


# -- binary overrides -------------------------------------------------------


def test_discrete_counts_take_exact_match() -> None:
    """§9.2 — u = 1, tolerance zero. Off by one is Contradicted."""
    exact = band_for(
        Decimal("61"), Decimal("61"),
        published_precision=Decimal("1"), discrete=True, kind=ElementKind.DISCRETE_COUNT,
    )
    assert exact.status is ElementStatus.VERIFIED

    off_by_one = band_for(
        Decimal("60"), Decimal("61"),
        published_precision=Decimal("1"), discrete=True, kind=ElementKind.DISCRETE_COUNT,
    )
    assert off_by_one.status is ElementStatus.CONTRADICTED
    assert off_by_one.band is ToleranceBand.C


def test_superlative_and_direction_cannot_be_softened_into_a_band() -> None:
    """A near miss on a superlative is not a near miss.

    "A claim that something is the highest ever is not 97% correct when it is
    the third highest."  Passing one here is a caller error, and raising is
    what stops it becoming a quiet Band B.
    """
    for kind in (ElementKind.SUPERLATIVE, ElementKind.DIRECTION):
        with pytest.raises(ValueError, match="binary"):
            band_for(
                Decimal("103.8"), Decimal("103.7"),
                published_precision=PRECISION, discrete=False, kind=kind,
            )


def test_direction_is_binary_on_sign_at_any_magnitude() -> None:
    assert direction_holds(True, Decimal("100"), Decimal("100.01"))
    assert not direction_holds(True, Decimal("100"), Decimal("1.0"))
    assert direction_holds(False, Decimal("100"), Decimal("99.99"))
    assert not direction_holds(False, Decimal("100"), Decimal("500"))


def test_a_flat_series_supports_neither_direction() -> None:
    assert not direction_holds(True, Decimal("100"), Decimal("100"))
    assert not direction_holds(False, Decimal("100"), Decimal("100"))


def test_precision_drives_the_band_rather_than_a_fixed_threshold() -> None:
    """The rule adapts to each measure without anyone choosing anything.

    Shown on a small published value, where the absolute half-step governs
    rather than the relative floor. The same figure pair lands in Band A
    against a coarsely-published measure and Band C against a finely-published
    one, which is precisely "the custodian's own reporting precision sets the
    scale".
    """
    coarse = band_for(
        Decimal("7.0"), Decimal("2.0"),
        published_precision=Decimal("10"), discrete=False, kind=ElementKind.QUANTITY,
    )
    fine = band_for(
        Decimal("7.0"), Decimal("2.0"),
        published_precision=Decimal("0.01"), discrete=False, kind=ElementKind.QUANTITY,
    )
    assert coarse.band is ToleranceBand.A
    assert fine.band is ToleranceBand.C
