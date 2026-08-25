"""Stage 8 — the robustness sweep.

Spec §9.3.  "Misleadingness is tested by a mechanical robustness sweep over
series already retrieved. The sweep introduces no new claims, performs no
open-ended reasoning about 'missing context,' and computes every cell from a
recorded retrieval."

That restriction is what makes this implementable, and §9.3 says why: "An
unbounded 'what context is missing?' search reintroduces exactly the advocacy
vector §2's fourth exclusion blocks: whoever chooses the missing context
chooses the verdict."

Every alternative comes from the pack's declared ``admissible_baselines`` and
``admissible_windows``.  None is chosen per claim — "If the comparison set
could be chosen per claim, the sweep would test only the alternatives that
flatter the claim, and would systematically clear exactly the cherry-picked
claims it exists to catch."

Every row cites the retrieval it was computed from.  §8: "a sweep cell
computed from anything other than a recorded retrieval is a fabricated
comparison."
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from engine.elements import Element
from engine.ids import RetrievalId
from engine.packs.schema import Measure
from engine.store.events import Retrieval

# Caveats naming incompleteness genuinely undermine a conclusion drawn from
# the series, as distinct from caveats that merely disambiguate a measure.
_INCOMPLETENESS_MARKERS = (
    "incomplete",
    "reporting lag",
    "coverage begins",
    "under-reporting",
    "partial publication",
    "revise upward",
)


class SweepTest(Enum):
    """§9.3's four tests."""

    BASELINE = "baseline"
    WINDOW = "window"
    LEVEL_VS_CHANGE = "level_vs_change"
    BOUNDED_OMISSION = "bounded_omission"


@dataclass(frozen=True, slots=True)
class FlipRow:
    """One row of the flip table.

    "One row per admissible alternative, recording whether the claim's
    qualitative conclusion (direction, magnitude class, superlative) holds
    under it."
    """

    test: SweepTest
    alternative: str
    conclusion_holds: bool
    computed_from_retrieval_id: RetrievalId
    detail: str = ""


@dataclass(frozen=True, slots=True)
class SweepResult:
    rows: tuple[FlipRow, ...] = ()
    ran: bool = False
    reason_not_run: str = ""

    @property
    def conclusion_flips(self) -> bool:
        return any(not row.conclusion_holds for row in self.rows)

    @property
    def flipped_rows(self) -> tuple[FlipRow, ...]:
        return tuple(row for row in self.rows if not row.conclusion_holds)


def run(
    measure: Measure,
    retrievals: tuple[Retrieval, ...],
    *,
    claimed_rise: bool | None,
    discarded: tuple[Element, ...] = (),
) -> SweepResult:
    """Run the sweep, or report why it could not.

    ``claimed_rise`` is ``None`` where the claim asserts no direction; the
    directional tests then have no conclusion to test and are skipped, which
    is a narrower sweep rather than a passing one.
    """
    if len(retrievals) < 2:
        return SweepResult(
            ran=False,
            reason_not_run=(
                "the retrieved series carries fewer than two observations, so no "
                "alternative baseline or window can be computed from it"
            ),
        )
    if not measure.sweep_can_run:
        return SweepResult(
            ran=False,
            reason_not_run=(
                f"the pack declares no admissible baselines or windows for "
                f"{measure.name}, so there is no fixed comparison set to sweep over"
            ),
        )
    if claimed_rise is None:
        return SweepResult(
            ran=False,
            reason_not_run=(
                "the claim asserts no direction, so there is no qualitative "
                "conclusion for the sweep to test"
            ),
        )

    rows: list[FlipRow] = []
    rows.extend(_baseline_sweep(measure, retrievals, claimed_rise))
    rows.extend(_window_sweep(measure, retrievals, claimed_rise))
    rows.extend(_level_vs_change(retrievals, claimed_rise))
    rows.extend(_bounded_omission(retrievals, discarded))

    if not rows:
        return SweepResult(
            ran=False,
            reason_not_run=(
                "no declared alternative could be computed against the retrieved series"
            ),
        )
    return SweepResult(rows=tuple(rows), ran=True)


def _holds(claimed_rise: bool, earlier: Decimal, later: Decimal) -> bool:
    if later == earlier:
        return False
    return (later > earlier) if claimed_rise else (later < earlier)


def _baseline_sweep(
    measure: Measure, retrievals: tuple[Retrieval, ...], claimed_rise: bool
) -> list[FlipRow]:
    """Test 1 — recompute against every baseline the pack declares admissible."""
    latest = retrievals[-1]
    rows: list[FlipRow] = []

    anchors: dict[str, Retrieval | None] = {
        "prior_period": retrievals[-2] if len(retrievals) >= 2 else None,
        "prior_year": retrievals[-13] if len(retrievals) >= 13 else retrievals[0],
        "series_start": retrievals[0],
        "last_break": retrievals[len(retrievals) // 2],
    }

    for baseline in measure.admissible_baselines:
        anchor = anchors.get(baseline)
        if anchor is None or anchor is latest:
            continue
        rows.append(
            FlipRow(
                test=SweepTest.BASELINE,
                alternative=baseline,
                conclusion_holds=_holds(claimed_rise, anchor.value, latest.value),
                computed_from_retrieval_id=anchor.id,
                detail=(
                    f"{anchor.reference_period} ({anchor.value}) to "
                    f"{latest.reference_period} ({latest.value})"
                ),
            )
        )
    return rows


def _window_sweep(
    measure: Measure, retrievals: tuple[Retrieval, ...], claimed_rise: bool
) -> list[FlipRow]:
    """Test 2 — vary the window across the custodian's own reporting windows.

    This is the test that catches a cherry-picked window, which §9.3 calls
    part of "the dominant mechanism" of sophisticated misinformation.
    """
    latest = retrievals[-1]
    rows: list[FlipRow] = []
    for window in measure.admissible_windows:
        periods = _window_length(window)
        if periods is None or periods >= len(retrievals):
            continue
        anchor = retrievals[-(periods + 1)]
        rows.append(
            FlipRow(
                test=SweepTest.WINDOW,
                alternative=window,
                conclusion_holds=_holds(claimed_rise, anchor.value, latest.value),
                computed_from_retrieval_id=anchor.id,
                detail=(
                    f"{anchor.reference_period} ({anchor.value}) to "
                    f"{latest.reference_period} ({latest.value})"
                ),
            )
        )
    return rows


def _window_length(window: str) -> int | None:
    """Interpret a declared window as a number of observations."""
    token = window.strip().lower()
    if token.endswith("m") and token[:-1].isdigit():
        return int(token[:-1])
    if token.endswith("y") and token[:-1].isdigit():
        return int(token[:-1]) * 12
    return None


def _level_vs_change(
    retrievals: tuple[Retrieval, ...], claimed_rise: bool
) -> list[FlipRow]:
    """Test 3 — if the claim asserts a change, check whether the level opposes it.

    §9.3: "Catches 'fastest growth' on a negligible base."  A series that has
    risen recently while sitting at the bottom of its own range supports a
    change claim and undercuts the impression the change claim creates.
    """
    values = [r.value for r in retrievals]
    latest = retrievals[-1]
    lowest, highest = min(values), max(values)
    if highest == lowest:
        return []

    midpoint = (highest + lowest) / 2
    level_agrees = (latest.value >= midpoint) if claimed_rise else (latest.value <= midpoint)
    position = "above" if latest.value >= midpoint else "below"

    return [
        FlipRow(
            test=SweepTest.LEVEL_VS_CHANGE,
            alternative="level within the retrieved range",
            conclusion_holds=level_agrees,
            computed_from_retrieval_id=latest.id,
            detail=(
                f"latest level {latest.value} sits {position} the midpoint of the "
                f"retrieved range [{lowest}, {highest}]"
            ),
        )
    ]


def _bounded_omission(
    retrievals: tuple[Retrieval, ...], discarded: tuple[Element, ...]
) -> list[FlipRow]:
    """Test 4 — bounded, and bounded is the point.

    §9.3 admits only "(a) elements the decomposition already produced but that
    were discarded, and (b) the custodian's own published caveats attached to
    the series. Nothing else."  There is no search here for context the
    decomposition did not already find, because whoever chooses that context
    chooses the verdict.
    """
    latest = retrievals[-1]
    rows: list[FlipRow] = []

    for element in discarded:
        rows.append(
            FlipRow(
                test=SweepTest.BOUNDED_OMISSION,
                alternative=f"discarded element: {element.fragment!r}",
                # A discarded element did not verify, so it cannot itself
                # oppose the conclusion. It is recorded so the omission is
                # visible rather than silent.
                conclusion_holds=True,
                computed_from_retrieval_id=latest.id,
                detail=(
                    f"removed as {element.status.value if element.status else 'unresolved'}; "
                    "recorded so the omission is visible"
                ),
            )
        )

    seen: set[str] = set()
    for retrieval in retrievals:
        caveat = (retrieval.caveat or "").strip()
        if not caveat or caveat in seen:
            continue
        seen.add(caveat)
        undermines = any(marker in caveat.lower() for marker in _INCOMPLETENESS_MARKERS)
        rows.append(
            FlipRow(
                test=SweepTest.BOUNDED_OMISSION,
                alternative="custodian caveat on the series",
                conclusion_holds=not undermines,
                computed_from_retrieval_id=retrieval.id,
                detail=caveat,
            )
        )
    return rows
