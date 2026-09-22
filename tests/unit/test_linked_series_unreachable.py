"""The linked-series unreachable path, which used to crash the render.

`retrieve.pull` has two `CustodianUnreachable` handlers. The primary one put
the exception text in `diagnostic` and kept `detail` clean prose; the
linked-series one did the inverse, interpolating the exception into `detail`.

`detail` becomes the element's discard reason, discard reasons render as
prose, and `engine/render/figures.py` fails any numeral in prose that no
retrieval accounts for. A custodian's unreachable message routinely carries a
status code. So a linked-series outage crashed `Artifact.render()` with
`UnsourcedFigure` instead of degrading the element to Unreachable — on the
one path where a series break makes the linked series load-bearing, which is
to say the path a real deployment hits during exactly the kind of outage the
Unreachable status exists to describe.

Nothing exercised this branch before. Both halves are asserted here: that the
status code stays out of the artifact, and that it still reaches the operator
through `diagnostic`.
"""

from __future__ import annotations

import pathlib
from datetime import date, datetime, timezone
from decimal import Decimal

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.base import CustodianUnreachable, Observation, RevisionStatus
from engine.custodians.fixture import build_fixture_custodians
from engine.elements import ElementStatus
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore
from engine.verification import retrieve

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"
NOW = datetime(2022, 1, 1, tzinfo=timezone.utc)

#: A status code in the adapter's message is the whole point: it is what makes
#: the difference between a clean degrade and a crashed render observable.
UNREACHABLE_DETAIL = "proxy returned 503"

#: ZZ-PRICE breaks at 2020-01-01 with ZZ-PRICE-LINKED spanning it, so a span
#: either side of that date is what makes `pull` reach for the linked series.
SPANNING = (
    Observation("ZZ-PRICE", "2019-06", Decimal("95.0"), RevisionStatus.FINAL, date(2019, 6, 1)),
    Observation("ZZ-PRICE", "2021-06", Decimal("102.0"), RevisionStatus.FINAL, date(2021, 6, 1)),
)


class _LinkedSeriesUnreachable:
    """Serves the primary series across the break; the linked one is down."""

    custodian_id = "zzstat"

    def __init__(self) -> None:
        self._fallback = build_fixture_custodians()["zzstat"]

    def series(self, series_id: str) -> tuple[Observation, ...]:
        if series_id == "ZZ-PRICE-LINKED":
            raise CustodianUnreachable("zzstat", UNREACHABLE_DETAIL)
        if series_id == "ZZ-PRICE":
            return SPANNING
        return self._fallback.series(series_id)


def _pack():
    return PackRegistry.from_directory(PACKS).get(JurisdictionCode("ZZ"))


def test_the_linked_series_branch_is_actually_reached() -> None:
    """The control. Without a span crossing the break this test would pass
    while exercising the *primary* handler, which was never broken."""
    pack = _pack()
    store = RetrievalStore(":memory:")
    try:
        outcome = retrieve.pull(
            pack.measure("price_index"), pack.custodian("zzstat"),
            _LinkedSeriesUnreachable(), store, now=NOW, compares_across_time=True,
        )
        assert outcome.blocked_status is ElementStatus.UNREACHABLE
        assert "linked series" in outcome.detail
    finally:
        store.close()


def test_the_exception_text_goes_to_diagnostic_not_to_detail() -> None:
    pack = _pack()
    store = RetrievalStore(":memory:")
    try:
        outcome = retrieve.pull(
            pack.measure("price_index"), pack.custodian("zzstat"),
            _LinkedSeriesUnreachable(), store, now=NOW, compares_across_time=True,
        )
        assert UNREACHABLE_DETAIL in outcome.diagnostic, (
            "the technical detail was dropped; --diagnostics has nothing to show "
            "for a genuinely unreachable pull"
        )
        assert "503" not in outcome.detail, (
            "the adapter's status code reached the rendered detail, which is what "
            "crashed the render"
        )
    finally:
        store.close()


def test_a_linked_series_outage_renders_instead_of_crashing() -> None:
    """The end-to-end consequence, through the whole pipeline."""
    adapters = build_fixture_custodians()
    adapters["zzstat"] = _LinkedSeriesUnreachable()
    context = ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"), language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )
    store = RetrievalStore(":memory:")
    try:
        run = verify(
            "prices rose over the last three years",
            context, PackRegistry.from_directory(PACKS), adapters, store,
        )
        rendered = run.artifact.render()  # raised UnsourcedFigure before the fix
        assert "503" not in rendered
        assert run.diagnostic and UNREACHABLE_DETAIL in run.diagnostic
    finally:
        store.close()
