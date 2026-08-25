"""AC-9 — Provisional invalidation.

Constraint: spec §8.  Provisional retrievals are invalidated when a revision
publishes.

"A claim true against the first print can be false against the revised
figure; verdicts pin to a specific revision."
"""

from __future__ import annotations

from datetime import datetime, timezone

from engine.custodians.base import RevisionStatus
from engine.store.events import EXPIRED, RetrievalStore
from engine.verification import retrieve

NOW = datetime(2022, 1, 1, tzinfo=timezone.utc)


def _record(pack, adapters, store: RetrievalStore, measure_id="unemployment_survey"):
    measure = pack.measure(measure_id)
    custodian = pack.custodian(measure.custodian_id)
    pull = retrieve.pull(measure, custodian, adapters[custodian.id], store, now=NOW)
    return measure, pull


def test_the_fixture_publishes_a_provisional_series(pack, adapters, store) -> None:
    _, pull = _record(pack, adapters, store)
    assert pull.retrievals
    assert all(r.revision_status is RevisionStatus.PROVISIONAL for r in pull.retrievals)


def test_a_publishing_revision_invalidates_the_provisional_retrieval(
    pack, adapters, store
) -> None:
    measure, pull = _record(pack, adapters, store)
    latest = pull.retrievals[-1]

    assert store.fresh(latest.series_id, latest.reference_period, NOW) is not EXPIRED
    assert store.supersede_provisional(latest.series_id, latest.reference_period, NOW) == 1
    assert store.fresh(latest.series_id, latest.reference_period, NOW) is EXPIRED


def test_invalidation_does_not_delete_the_record(pack, adapters, store) -> None:
    """The record of what was believed, and when, is the point of storing events."""
    measure, pull = _record(pack, adapters, store)
    latest = pull.retrievals[-1]
    before = store.count()

    store.supersede_provisional(latest.series_id, latest.reference_period, NOW)

    assert store.count() == before
    kept = store.get(str(latest.id))
    assert kept is not None
    assert kept.superseded_at is not None


def test_a_superseded_retrieval_is_not_served_and_triggers_a_re_pull(
    pack, adapters, store
) -> None:
    measure, pull = _record(pack, adapters, store)
    latest = pull.retrievals[-1]
    store.supersede_provisional(latest.series_id, latest.reference_period, NOW)
    before = store.count()

    retrieve.pull(measure, pack.custodian(measure.custodian_id),
                  adapters[measure.custodian_id], store, now=NOW)

    assert store.count() > before, "a superseded print was served instead of re-pulled"


def test_final_retrievals_are_not_swept_up_by_invalidation(pack, adapters, store) -> None:
    """Only provisional prints are invalidated; a final figure is not provisional."""
    measure, pull = _record(pack, adapters, store, "price_index")
    latest = pull.retrievals[-1]
    assert latest.revision_status is RevisionStatus.FINAL
    assert store.supersede_provisional(latest.series_id, latest.reference_period, NOW) == 0
    assert store.fresh(latest.series_id, latest.reference_period, NOW) is not EXPIRED
