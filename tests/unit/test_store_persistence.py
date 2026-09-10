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
        found = second.fresh("ZZ-PRICE", "2021-12", custodian_id="zzstat", now=NOW + timedelta(hours=1))
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
        assert second.fresh("ZZ-PRICE", "2021-12", custodian_id="zzstat", now=NOW + timedelta(days=400)) is EXPIRED
    finally:
        second.close()


def test_a_second_verification_records_no_second_event(tmp_path) -> None:
    """Two runs inside the TTL leave one event per observation, with one id.

    Note what this does *not* claim. The custodian is still fetched on both
    runs: `retrieve.pull` calls `adapter.series` before the store is consulted
    at all, so the TTL de-duplicates the recorded *event*, not the *fetch*.
    An earlier version of this test asserted a row count and a docstring
    asserted "pulls once", which was false and untested in the same breath.

    What reuse does buy is the property §8 actually needs: a retrieval id that
    is stable across runs, so two verdicts inside one TTL pin to the same
    revision rather than to two rows that happen to agree.
    """
    path = str(tmp_path / "store.db")
    registry = PackRegistry.from_directory(PACKS)

    first = RetrievalStore(path)
    try:
        run = verify(CLAIM, _context(), registry, build_fixture_custodians(), first)
        after_first = first.count()
        first_ids = [str(r.id) for r in run.artifact.citations]
    finally:
        first.close()

    assert after_first > 0, "the first run recorded nothing"
    assert first_ids, "the first run cited nothing"

    second = RetrievalStore(path)
    try:
        again = verify(CLAIM, _context(), registry, build_fixture_custodians(), second)
        assert second.count() == after_first, (
            "the second run recorded fresh retrievals instead of reusing the stored "
            "ones, so the TTL is not being honoured across runs"
        )
        assert [str(r.id) for r in again.artifact.citations] == first_ids, (
            "the second run cited different retrieval ids for the same figures"
        )
    finally:
        second.close()


def test_a_revision_inside_the_ttl_is_not_papered_over(tmp_path) -> None:
    """The defect that made the store durable and the artifact untrustworthy.

    A fresh stored row was returned regardless of what the custodian had just
    said. Verdicts read `pull.observations` and citations read
    `pull.retrievals`, so a revision published inside the TTL left the
    artifact citing one figure while the verdict was computed from another.
    """
    from datetime import timedelta

    from engine.packs.schema import Custodian, Measure
    from engine.verification import continuity
    from engine.verification.retrieve import _record

    custodian = Custodian(
        id="zzstat",
        name="ZZ Statistics",
        mandate="fixture",
        cadence="monthly",
        revision_policy="fixture",
        access_method="fixture",
        integrity_annotation="fixture",
    )
    measure = Measure(
        id="price_index",
        name="ZZ Price Index",
        definition="fixture",
        custodian_id="zzstat",
        series_identifier="ZZ-PRICE",
        unit="index_points",
        published_precision=0.1,
        discrete=False,
        known_confusions=(),
        admissible_baselines=("prior_period",),
        admissible_windows=("annual",),
        admissible_source_ref="fixture",
    )

    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        provisional = Observation(
            series_id="ZZ-PRICE",
            reference_period="2021-12",
            value=Decimal("102.4"),
            revision_status=RevisionStatus.PROVISIONAL,
            observed_on=date(2021, 12, 1),
        )
        first = _record(store, provisional, custodian, measure,
                        continuity.not_applicable(), NOW)
        assert first.value == Decimal("102.4")

        revised = Observation(
            series_id="ZZ-PRICE",
            reference_period="2021-12",
            value=Decimal("101.1"),
            revision_status=RevisionStatus.FINAL,
            observed_on=date(2021, 12, 1),
        )
        second = _record(store, revised, custodian, measure,
                         continuity.not_applicable(), NOW + timedelta(days=1))

        assert second.value == Decimal("101.1"), (
            "the revised figure was discarded and the stored print served"
        )
        assert second.revision_status is RevisionStatus.FINAL
        assert second.id != first.id

        superseded = store.get(str(first.id))
        assert superseded is not None and superseded.superseded_at is not None, (
            "the provisional print stayed servable after its revision published"
        )
    finally:
        store.close()


def test_a_level_claims_row_is_not_reused_by_a_cross_time_claim(tmp_path) -> None:
    """Continuity status is per-claim, and the row freezes it.

    A claim that compares nothing records `not_applicable`. Reusing that row
    for a claim that compares across time reports the wrong continuity in the
    citation block and costs the sweep a flip row, which can change a verdict
    rather than only its prose.
    """
    from engine.elements import ContinuityStatus
    from engine.packs.schema import Custodian, Measure
    from engine.verification import continuity
    from engine.verification.continuity import ContinuityOutcome
    from engine.verification.retrieve import _record

    custodian = Custodian(
        id="zzstat", name="ZZ Statistics", mandate="fixture", cadence="monthly",
        revision_policy="fixture", access_method="fixture",
        integrity_annotation="fixture",
    )
    measure = Measure(
        id="price_index", name="ZZ Price Index", definition="fixture",
        custodian_id="zzstat", series_identifier="ZZ-PRICE", unit="index_points",
        published_precision=0.1, discrete=False, known_confusions=(),
        admissible_baselines=("prior_period",), admissible_windows=("annual",),
        admissible_source_ref="fixture",
    )

    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        level = _record(store, _observation(), custodian, measure,
                        continuity.not_applicable(), NOW)
        assert level.continuity_status == ContinuityStatus.NOT_APPLICABLE.value

        crossed = _record(store, _observation(), custodian, measure,
                          ContinuityOutcome(ContinuityStatus.NO_BREAK_CROSSED), NOW)

        assert crossed.id != level.id, "a not_applicable row was served to a cross-time claim"
        assert crossed.continuity_status == ContinuityStatus.NO_BREAK_CROSSED.value
    finally:
        store.close()


def test_two_custodians_sharing_a_series_name_do_not_read_each_other(tmp_path) -> None:
    """A series identifier is unique within a custodian and nowhere else."""
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        store.record(
            _observation(), custodian_id="zzstat", cadence="monthly",
            unit="index_points", continuity_status="not_applicable", now=NOW,
        )
        assert store.fresh("ZZ-PRICE", "2021-12", custodian_id="zzstat", now=NOW)
        assert store.fresh("ZZ-PRICE", "2021-12", custodian_id="other", now=NOW) is None
        assert store.supersede_provisional(
            "ZZ-PRICE", "2021-12", custodian_id="other", now=NOW
        ) == 0
    finally:
        store.close()


def test_the_cli_defaults_to_a_durable_store(tmp_path, monkeypatch) -> None:
    """A run that remembers nothing is the behaviour this replaced."""
    import cli.verify

    assert cli.verify.DEFAULT_STORE != ":memory:"

    target = tmp_path / "nested" / "store.db"
    monkeypatch.setattr(cli.verify, "DEFAULT_STORE", str(target))
    assert cli.verify.main([CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS)]) == 0
    assert target.exists(), "the CLI did not create its default store"

    store = RetrievalStore(str(target))
    try:
        assert store.count() > 0, "the CLI wrote a database and recorded nothing in it"
    finally:
        store.close()


def test_the_default_store_does_not_follow_the_working_directory(monkeypatch, tmp_path) -> None:
    """One database for the repository, not one per directory it is run from.

    A cwd-relative default quietly creates a second empty store when the
    command runs from a subdirectory, which restores the re-pull-everything
    behaviour the path was added to remove.
    """
    import cli.verify

    default = pathlib.Path(cli.verify.DEFAULT_STORE)
    assert default.is_absolute(), "the default store path is relative to the cwd"
    assert default.is_relative_to(cli.verify.ROOT), (
        "the default store lands outside the repository"
    )

    monkeypatch.chdir(tmp_path)
    assert pathlib.Path(cli.verify.DEFAULT_STORE) == default


def test_the_cli_can_be_asked_to_forget(tmp_path, monkeypatch) -> None:
    import cli.verify

    target = tmp_path / "store.db"
    monkeypatch.setattr(cli.verify, "DEFAULT_STORE", str(target))
    assert cli.verify.main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:"]
    ) == 0
    assert not target.exists()


def test_an_unopenable_store_is_reported_rather_than_raised(tmp_path, capsys) -> None:
    """An operator error, reported the way this CLI reports the others.

    A traceback out of the store constructor reads as a crash in the engine,
    which is the one thing it is not.
    """
    from cli.verify import main

    blocked = tmp_path / "occupied"
    blocked.mkdir()

    # The store path is itself a directory: mkdir succeeds, connect cannot.
    assert main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", str(blocked)]
    ) == 2
    assert "cannot open retrieval store" in capsys.readouterr().err
