"""Sourced figures.

Spec §3, the non-negotiable rule: "Every figure, date, amount, or ranking in
any output MUST originate from a retrieval performed against a named
custodian, recorded with its reference period."

:class:`Figure` is that rule as a type.  A figure cannot be constructed
without the retrieval it came from, so a number reaching output without
provenance is not a validation failure to be caught later — it is a value
that could not be built.  AC-7 requires the render to *fail* rather than
warn; making the invalid state unrepresentable is the same guarantee moved
earlier.

Decimal rather than float throughout.  Tolerance bands (§9.2) compare a claim
figure against a published one at the custodian's stated precision, and
binary floating point would make that comparison depend on representation
error rather than on the rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from engine.ids import RetrievalId


@dataclass(frozen=True, slots=True)
class Figure:
    """A number that knows where it came from."""

    value: Decimal
    unit: str
    retrieval_id: RetrievalId
    reference_period: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError(
                f"Figure.value must be Decimal, got {type(self.value).__name__}. "
                "Float arithmetic would make §9.2's bands depend on representation "
                "error rather than on the custodian's published precision."
            )
        if not self.reference_period:
            raise ValueError(
                "Figure.reference_period may not be empty. §5 requires the reference "
                "period to render alongside the figure, and AC-7 tests it."
            )

    def render(self) -> str:
        """The figure as it should appear, with its unit."""
        return f"{self.value} {self.unit}".strip()
