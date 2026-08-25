"""Tolerance bands — spec §9.2.

"Tolerance is computed from the custodian's own published precision. It is
never chosen per claim, per claimant, or per operator."

Every constant here is module-level and final.  AC-3 requires the bands to
load "exclusively from versioned pack files or the versioned spec constants",
and AC-13 requires the assigned band to be "a pure function of
``published_precision``, ``unit``, and ``discrete`` from the pack" with "no
per-claim, per-claimant, or per-session input".  The signature of
:func:`band_for` is the enforcement: there is no parameter through which a
session, a claimant, or an operator preference could arrive.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from engine.elements import ElementKind, ElementStatus, ToleranceBand

# Band A admits a half-step of the published precision, or half a percent
# relative, whichever is larger. Band B admits a full step, or two percent.
# These are the spec's numbers and are versioned with it.
BAND_A_RELATIVE: Final[Decimal] = Decimal("0.005")
BAND_B_RELATIVE: Final[Decimal] = Decimal("0.02")

# Element kinds that bypass the numeric bands entirely (§9.2, binary
# overrides). A tolerance on them is meaningless: a claim that something is
# the highest ever is not 97% correct when it is the third highest.
BINARY_KINDS: Final[frozenset[ElementKind]] = frozenset(
    {ElementKind.SUPERLATIVE, ElementKind.DIRECTION, ElementKind.DISCRETE_COUNT}
)


@dataclass(frozen=True, slots=True)
class ToleranceOutcome:
    """A band and the status it implies."""

    band: ToleranceBand
    status: ElementStatus
    rounded: bool = False

    @property
    def tag(self) -> str | None:
        """§9.2: the ``rounded`` tag surfaces in output.

        "A claim that is right to within a rounding step is not wrong, but the
        reader should be able to see that it was not exact."
        """
        return "rounded" if self.rounded else None


def band_for(
    claim_value: Decimal,
    published_value: Decimal,
    *,
    published_precision: Decimal,
    discrete: bool,
    kind: ElementKind,
) -> ToleranceOutcome:
    """Assign a band. A pure function of the claim figure and pack data.

    Note the keyword-only pack parameters: every input is either the pair of
    figures being compared or a declared property of the measure. Nothing
    about who made the claim, when it was checked, or how the operator is
    feeling can reach this function, because there is no parameter for it.
    """
    if discrete or kind is ElementKind.DISCRETE_COUNT:
        # Exact match. u = 1, tolerance zero (§9.2).
        exact = claim_value == published_value
        return ToleranceOutcome(
            band=ToleranceBand.A if exact else ToleranceBand.C,
            status=ElementStatus.VERIFIED if exact else ElementStatus.CONTRADICTED,
        )

    if kind in BINARY_KINDS:
        # Superlatives and directions are resolved by the caller against the
        # full series, not by comparing two numbers. Reaching here with one
        # means the caller tried to soften a binary element into a numeric
        # one, which §9.2 forbids outright.
        raise ValueError(
            f"{kind.value} elements are binary and must be resolved against the "
            "full series, not by numeric tolerance (§9.2)"
        )

    delta = abs(claim_value - published_value)
    u = abs(published_precision)
    relative = abs(published_value)

    band_a_allowance = max(u / 2, relative * BAND_A_RELATIVE)
    band_b_allowance = max(u, relative * BAND_B_RELATIVE)

    if _rounds_to(claim_value, published_value) or delta <= band_a_allowance:
        return ToleranceOutcome(ToleranceBand.A, ElementStatus.VERIFIED)
    if delta <= band_b_allowance:
        return ToleranceOutcome(ToleranceBand.B, ElementStatus.VERIFIED, rounded=True)
    return ToleranceOutcome(ToleranceBand.C, ElementStatus.CONTRADICTED)


def _rounds_to(claim_value: Decimal, published_value: Decimal) -> bool:
    """Whether the published figure rounds to the claim at the claim's precision.

    §9.2's first Band A condition. A claim of "four percent" against a
    published figure of four point two is correct at the precision the
    claimant used, and treating it as an error would penalise ordinary
    speech rather than inaccuracy.
    """
    places = -claim_value.as_tuple().exponent
    if places < 0:
        places = 0
    quantum = Decimal(1).scaleb(-places)
    return published_value.quantize(quantum) == claim_value


def direction_holds(claimed_rise: bool, first: Decimal, last: Decimal) -> bool:
    """§9.2 — direction elements are binary on sign.

    "A claim asserting the wrong direction is Contradicted at any magnitude."
    A flat series supports neither direction.
    """
    if last == first:
        return False
    return (last > first) if claimed_rise else (last < first)
