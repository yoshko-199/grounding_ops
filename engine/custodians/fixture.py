"""Deterministic in-process custodians for the ZZ fixture jurisdiction.

The series live here rather than in the pack, and that placement is the whole
point.  Interface §6 forbids a pack from carrying figures: "A pack describes
*where a figure comes from and what it means*. The moment it contains the
figure, it becomes exactly what spec §8 exists to prevent."  A test rig that
put its canned numbers in the pack would have introduced that failure while
testing for it.

These values reach the engine the same way a real custodian's would — through
an adapter, recorded as a retrieval, with a reference period and a revision
status.  Nothing downstream can tell the difference, which is what makes the
conformance suite meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from engine.custodians.base import CustodianUnreachable, Observation, RevisionStatus


def _monthly(
    series_id: str,
    start_year: int,
    values: list[str],
    revision: RevisionStatus = RevisionStatus.FINAL,
) -> tuple[Observation, ...]:
    """Build a monthly series, oldest first, one observation per month."""
    out: list[Observation] = []
    year, month = start_year, 1
    for raw in values:
        out.append(
            Observation(
                series_id=series_id,
                reference_period=f"{year:04d}-{month:02d}",
                value=Decimal(raw),
                revision_status=revision,
                observed_on=date(year, month, 1),
            )
        )
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return tuple(out)


# ZZ-PRICE rises steadily, then falls back in the final months.  The shape
# matters: a claim of "prices rose" is true against the twelve-month window
# and false against the three-month one, which is exactly the cherry-picked
# window the robustness sweep exists to catch (§9.3, test 2).
_ZZ_PRICE = _monthly(
    "ZZ-PRICE",
    2021,
    ["100.0", "100.4", "100.9", "101.5", "102.0", "102.6",
     "103.1", "103.8", "104.2", "103.7", "103.1", "102.4"],
)

# The linked series spanning the 2020 base-year break.
_ZZ_PRICE_LINKED = _monthly(
    "ZZ-PRICE-LINKED",
    2019,
    ["94.1", "94.6", "95.0", "95.4", "95.9", "96.3",
     "96.8", "97.2", "97.7", "98.1", "98.6", "99.0"],
)

# ZZ-OUTPUT spans a methodology break with no linked series.  Any element
# comparing across 2019-06 must never be Verified (§9.5, AC-12).
_ZZ_OUTPUT = _monthly(
    "ZZ-OUTPUT",
    2019,
    ["80.0", "80.5", "81.1", "81.6", "82.0", "97.4",
     "97.9", "98.3", "98.8", "99.2", "99.7", "100.1"],
)

# A single observation, so no admissible alternative can be computed and the
# sweep cannot run.  AC-11 requires the verdict to cap at Indeterminate.
_ZZ_SPARSE = (
    Observation(
        series_id="ZZ-SPARSE",
        reference_period="2021-06",
        value=Decimal("42.0"),
        revision_status=RevisionStatus.FINAL,
        observed_on=date(2021, 6, 1),
    ),
)

# Provisional, so AC-9 has something to invalidate.
_ZZ_UNEMP_SURVEY = _monthly(
    "ZZ-UNEMP-SURVEY",
    2021,
    ["5.4", "5.3", "5.1", "5.0", "4.8", "4.7",
     "4.6", "4.5", "4.5", "4.4", "4.3", "4.2"],
    revision=RevisionStatus.PROVISIONAL,
)

_ZZ_UNEMP_REG = _monthly(
    "ZZ-UNEMP-REG",
    2021,
    ["31000", "30800", "30500", "30200", "29900", "29700",
     "29500", "29300", "29200", "29000", "28900", "28700"],
)

_ZZ_SEATS = (
    Observation(
        series_id="ZZ-SEATS",
        reference_period="2019-election",
        value=Decimal("54"),
        revision_status=RevisionStatus.FINAL,
        observed_on=date(2019, 11, 5),
    ),
    Observation(
        series_id="ZZ-SEATS",
        reference_period="2023-election",
        value=Decimal("61"),
        revision_status=RevisionStatus.FINAL,
        observed_on=date(2023, 11, 7),
    ),
)


@dataclass(slots=True)
class FixtureCustodian:
    """An in-process custodian serving a fixed set of series."""

    custodian_id: str
    _series: dict[str, tuple[Observation, ...]] = field(default_factory=dict)
    unreachable: bool = False

    def series(self, series_id: str) -> tuple[Observation, ...]:
        if self.unreachable:
            raise CustodianUnreachable(self.custodian_id, "fixture set to unreachable")
        return self._series.get(series_id, ())


def build_fixture_custodians() -> dict[str, FixtureCustodian]:
    """The adapters backing the ZZ pack, keyed by custodian id."""
    return {
        "zzstat": FixtureCustodian(
            "zzstat",
            {
                "ZZ-PRICE": _ZZ_PRICE,
                "ZZ-PRICE-LINKED": _ZZ_PRICE_LINKED,
                "ZZ-OUTPUT": _ZZ_OUTPUT,
                "ZZ-SPARSE": _ZZ_SPARSE,
                "ZZ-UNEMP-SURVEY": _ZZ_UNEMP_SURVEY,
            },
        ),
        "zzelect": FixtureCustodian("zzelect", {"ZZ-SEATS": _ZZ_SEATS}),
        "zzlabour": FixtureCustodian("zzlabour", {"ZZ-UNEMP-REG": _ZZ_UNEMP_REG}),
    }
