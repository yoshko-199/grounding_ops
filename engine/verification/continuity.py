"""The continuity check — spec §9.5.

"Joining two sides of an unlinked break to produce a comparison is a
fabricated comparison, in the same class as §5's remembered historical peak —
a number that never existed as a published figure, presented as one."

The check runs before the element verdict, not after.  The Israel pack's §5
explains why in the clearest available terms: a ministry line restructured
across fiscal years appears as a spending collapse, and a coverage onset
appears as explosive growth.  "Both would verify cleanly as arithmetic
against the published figures."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from engine.elements import ContinuityStatus
from engine.packs.schema import Measure, SeriesBreak


@dataclass(frozen=True, slots=True)
class ContinuityOutcome:
    status: ContinuityStatus
    crossed: tuple[SeriesBreak, ...] = ()
    linked_series_used: str | None = None

    @property
    def blocks_verification(self) -> bool:
        """Whether this outcome forbids a Verified status.

        §9.5: a span crossing a break with no linked series is "Contested by
        definition or Unverified. Never Verified."
        """
        return self.status is ContinuityStatus.UNLINKED_BREAK

    @property
    def caveat(self) -> str | None:
        if self.status is ContinuityStatus.LINKED_SERIES_USED:
            return (
                f"Comparison spans a declared series break; the custodian's linked "
                f"series {self.linked_series_used} was used."
            )
        if self.status is ContinuityStatus.UNLINKED_BREAK:
            kinds = ", ".join(sorted({b.kind.value for b in self.crossed}))
            return (
                f"Comparison spans a declared series break ({kinds}) that no linked "
                "series covers. The figures either side are not comparable."
            )
        return None


def check(measure: Measure, span_start: date, span_end: date) -> ContinuityOutcome:
    """Run the continuity check for an element comparing across time."""
    if span_end < span_start:
        span_start, span_end = span_end, span_start

    crossed = tuple(
        b for b in measure.series_breaks if span_start < b.effective_date <= span_end
    )
    if not crossed:
        return ContinuityOutcome(ContinuityStatus.NO_BREAK_CROSSED)

    # A linked series has to span every break crossed, not merely one of
    # them. Two breaks with a linked series covering only the later one still
    # leaves the earlier join fabricated.
    linked = [b for b in crossed if b.linked_series_available and b.linked_series_identifier]
    if len(linked) == len(crossed):
        identifiers = sorted({b.linked_series_identifier for b in linked if b.linked_series_identifier})
        return ContinuityOutcome(
            ContinuityStatus.LINKED_SERIES_USED,
            crossed=crossed,
            linked_series_used=identifiers[0] if len(identifiers) == 1 else ",".join(identifiers),
        )

    return ContinuityOutcome(ContinuityStatus.UNLINKED_BREAK, crossed=crossed)


def not_applicable() -> ContinuityOutcome:
    """For elements that do not compare across time."""
    return ContinuityOutcome(ContinuityStatus.NOT_APPLICABLE)
