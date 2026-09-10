"""The store outliving the process that wrote it.

§8 makes a retrieval an event carrying a TTL: served while fresh, re-pulled
once expired, "never served" after that. None of it is observable while the
store dies with the process — and `cli/verify.py` constructed
`RetrievalStore()` with no path, so every run began with an empty database and
re-pulled everything.

The schema was there, the TTL logic was there, the tests passed. What was
missing was a path.
"""

from __future__ import annotations

import pathlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.base import Observation, RevisionStatus
from engine.custodians.fixture import build_fixture_custodians
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import EXPIRED, RetrievalStore

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"
NOW = datetime(2022, 1, 1, 12, 0, tzinfo=timezone.utc)
CLAIM = "prices rose over the last three years"


def _observation() -> Observation:
    return Observation(
        series_id="ZZ-PRICE",
        reference_period="2021-12",
        value=Decimal("102.4"),
        revision_status=RevisionStatus.FINAL,
        observed_on=date(2021, 12, 1),
    )


def _record(store: RetrievalStore, now: datetime = NOW) -> None:
    store.record(
        _observation(),
        custodian_id="zzstat",
        cadence="monthly",
        unit="index_points",
        continuity_status="no_break_crossed",
        now=now,
    )


def _context() -> ClaimContext:
    return ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )


def test_a_retrieval_survives_the_process_that_made_it(tmp_path) -> None:
    """The whole point. A second connection sees the first one's work."""
    path = str(tmp_path / "store.db")

    first = RetrievalStore(path)
    _record(first)
    assert first.count() == 1
    first.close()

    second = RetrievalStore(path)
    try:
        assert second.count() == 1, "the retrieval did not outlive its connection"
        found = second.fresh("ZZ-PRICE", "2021-12", NOW + timedelta(hours=1))
        assert found is not None and found is not EXPIRED
        assert found.value == Decimal("102.4")
    finally:
        second.close()


def test_an_in_memory_store_deliberately_forgets(tmp_path) -> None:
    """The control. `:memory:` must stay available and must not persist."""
    first = RetrievalStore(":memory:")
    _record(first)
    assert first.count() == 1
    first.close()

    second = RetrievalStore(":memory:")
    try:
        assert second.count() == 0
    finally:
        second.close()


def test_the_ttl_still_expires_across_connections(tmp_path) -> None:
    """Persistence must not become a way to serve a stale figure.

    AC-8 forbids serving expired data under any condition, and a durable store
    is exactly where that temptation appears — the record is right there.
    """
    path = str(tmp_path / "store.db")
    first = RetrievalStore(path)
    _record(first)
    first.close()

    second = RetrievalStore(path)
    try:
        # A monthly cadence, read back long after its TTL.
        assert second.fresh("ZZ-PRICE", "2021-12", NOW + timedelta(days=400)) is EXPIRED
    finally:
        second.close()


def test_a_second_verification_reuses_the_stored_retrieval(tmp_path) -> None:
    """Two runs against one store pull once, which is what §8 asks for.

    Before the store had a path this was untestable: each run built its own
    empty database, so every claim re-pulled every series regardless of TTL.
    """
    path = str(tmp_path / "store.db")
    registry = PackRegistry.from_directory(PACKS)

    first = RetrievalStore(path)
    try:
        verify(CLAIM, _context(), registry, build_fixture_custodians(), first)
        after_first = first.count()
    finally:
        first.close()

    assert after_first > 0, "the first run recorded nothing"

    second = RetrievalStore(path)
    try:
        verify(CLAIM, _context(), registry, build_fixture_custodians(), second)
        assert second.count() == after_first, (
            "the second run recorded fresh retrievals instead of reusing the stored "
            "ones, so the TTL is not being honoured across runs"
        )
    finally:
        second.close()


def test_the_cli_defaults_to_a_durable_store(tmp_path, monkeypatch) -> None:
    """A run that remembers nothing is the behaviour this replaced."""
    from cli.verify import DEFAULT_STORE, main

    assert DEFAULT_STORE != ":memory:"

    monkeypatch.chdir(tmp_path)
    assert main([CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS)]) == 0

    written = tmp_path / DEFAULT_STORE
    assert written.exists(), f"no store at {DEFAULT_STORE}"

    store = RetrievalStore(str(written))
    try:
        assert store.count() > 0, "the CLI wrote a database and recorded nothing in it"
    finally:
        store.close()


def test_the_cli_can_be_asked_to_forget(tmp_path, monkeypatch) -> None:
    from cli.verify import DEFAULT_STORE, main

    monkeypatch.chdir(tmp_path)
    assert main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:"]
    ) == 0
    assert not (tmp_path / DEFAULT_STORE).exists()
