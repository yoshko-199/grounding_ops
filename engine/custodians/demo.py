"""In-process custodians for the XD demo jurisdiction (packs/demo/xd.toml).

The values are invented. They exist to land the ten supplied claims
(docs/validation-ten-claims.md) on the full range of verification levels,
and each one was chosen for that and for nothing else. None of them is the
real boiling point of water, density of steel, or crime rate of anywhere,
and none may be quoted as such. The real-figures counterpart,
docs/spec/packs/demo-real.md, keeps every figure `[confirm]` until it is
fetched from the authority's own publication.

They reach the engine exactly as the ZZ fixture's do: through an adapter,
recorded as retrievals. The XD Demo Archive (`xdarch`) has no adapter here on
purpose, so its elements come back Unreachable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.custodians.base import Observation, RevisionStatus


def _annual(series_id: str, start_year: int, values: list[str]) -> tuple[Observation, ...]:
    """An annual series, oldest first, one final observation per year."""
    return tuple(
        Observation(
            series_id=series_id,
            reference_period=f"{start_year + offset:04d}",
            value=Decimal(raw),
            revision_status=RevisionStatus.FINAL,
            observed_on=date(start_year + offset, 12, 31),
        )
        for offset, raw in enumerate(values)
    )


# A level, published in Celsius only. Claim 1's "100" rounds to it at the
# claim's own precision (band A). Its "212", in Fahrenheit, is compared
# against the same Celsius series, because the engine does not read units:
# the unit gap, shown rather than hidden.
_XD_BOIL = _annual("XD-BOIL", 2021, ["99.96", "99.96", "99.96"])

# Two alloy families, published by two custodians. "The density of steel"
# names neither, so the claim matches both equally and is Contested. The
# carbon value sits within band B of the claim's 7700 (verified, `rounded`)
# and far from a claim of 9000 (band C).
_XD_STEEL_CARBON = _annual("XD-STEEL-CARBON", 2021, ["7810", "7810", "7810"])
_XD_STEEL_STAINLESS = _annual("XD-STEEL-STAINLESS", 2021, ["7950", "7950", "7950"])

# Falls by more than half from the first year, bottoms out, then climbs, and
# rises again in the latest year. "Cut since 1991" holds against the series
# start and fails against the prior year: the baseline choice the sweep is
# there to catch.
_XD_MURDER = _annual("XD-MURDER", 1991, [
    "10.0", "9.6", "9.3", "8.9", "8.4", "7.8", "7.2", "6.6", "6.1", "5.8",
    "5.6", "5.5", "5.4", "5.3", "5.2", "5.1", "4.9", "4.8", "4.6", "4.5",
    "4.4", "4.3", "4.2", "4.2", "4.6", "5.0", "5.2", "5.4", "5.6", "6.0",
    "6.2", "5.9", "6.1",
])

# Falls in every year, so every declared baseline agrees with the claim.
_XD_HOMICIDE = _annual("XD-HOMICIDE", 1991, [
    "9.0", "8.8", "8.6", "8.4", "8.2", "8.0", "7.8", "7.6", "7.4", "7.2",
    "7.0", "6.8", "6.6", "6.4", "6.2", "6.0", "5.8", "5.6", "5.4", "5.2",
    "5.0", "4.9", "4.8", "4.7", "4.6", "4.5", "4.4", "4.3", "4.2", "4.1",
    "4.0", "3.9", "3.8",
])


def build_demo_custodians() -> dict:
    """The XD demo adapters, keyed by custodian id. `xdarch` is left out on purpose."""
    from engine.custodians.fixture import FixtureCustodian

    return {
        "xdstd": FixtureCustodian("xdstd", {
            "XD-BOIL": _XD_BOIL,
            "XD-STEEL-CARBON": _XD_STEEL_CARBON,
        }),
        "xdmat": FixtureCustodian("xdmat", {"XD-STEEL-STAINLESS": _XD_STEEL_STAINLESS}),
        "xdcrime": FixtureCustodian("xdcrime", {
            "XD-MURDER": _XD_MURDER,
            "XD-HOMICIDE": _XD_HOMICIDE,
        }),
    }
