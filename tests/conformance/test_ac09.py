"""AC-9 — Provisional invalidation.

Constraint: spec §8.  Provisional retrievals are invalidated when a revision
publishes.

"A claim true against the first print can be false against the revised
figure; verdicts pin to a specific revision."
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

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

    assert store.fresh(latest.series_id, latest.reference_period,
                    custodian_id=latest.custodian_id, now=NOW) is not EXPIRED
    assert store.supersede_provisional(latest.series_id, latest.reference_period,
                                custodian_id=latest.custodian_id, now=NOW) == 1
    assert store.fresh(latest.series_id, latest.reference_period,
                    custodian_id=latest.custodian_id, now=NOW) is EXPIRED


def test_invalidation_does_not_delete_the_record(pack, adapters, store) -> None:
    """The record of what was believed, and when, is the point of storing events."""
    measure, pull = _record(pack, adapters, store)
    latest = pull.retrievals[-1]
    before = store.count()

    store.supersede_provisional(latest.series_id, latest.reference_period,
                                custodian_id=latest.custodian_id, now=NOW)

    assert store.count() == before
    kept = store.get(str(latest.id))
    assert kept is not None
    assert kept.superseded_at is not None


def test_a_superseded_retrieval_is_not_served_and_triggers_a_re_pull(
    pack, adapters, store
) -> None:
    measure, pull = _record(pack, adapters, store)
    latest = pull.retrievals[-1]
    store.supersede_provisional(latest.series_id, latest.reference_period,
                                custodian_id=latest.custodian_id, now=NOW)
    before = store.count()

    retrieve.pull(measure, pack.custodian(measure.custodian_id),
                  adapters[measure.custodian_id], store, now=NOW)

    assert store.count() > before, "a superseded print was served instead of re-pulled"


def test_final_retrievals_are_not_swept_up_by_invalidation(pack, adapters, store) -> None:
    """Only provisional prints are invalidated; a final figure is not provisional."""
    measure, pull = _record(pack, adapters, store, "price_index")
    latest = pull.retrievals[-1]
    assert latest.revision_status is RevisionStatus.FINAL
    assert store.supersede_provisional(latest.series_id, latest.reference_period,
                                custodian_id=latest.custodian_id, now=NOW) == 0
    assert store.fresh(latest.series_id, latest.reference_period,
                    custodian_id=latest.custodian_id, now=NOW) is not EXPIRED


def test_a_revision_inside_the_ttl_is_recorded_rather_than_reused(
    pack, adapters, store
) -> None:
    """The clause this criterion turns on: "verdicts pin to a specific revision".

    A retrieval that is still inside its TTL was returned regardless of what
    the custodian had just published. Nothing invalidated the provisional
    print, because `supersede_provisional` had no caller outside this file, so
    the first print stayed servable for the whole TTL — a month here, a year
    on an annual cadence.

    The suite could not see it. Every process began with an empty store, so
    the reuse branch never crossed a process boundary and never met a revised
    figure.
    """
    measure, first = _record(pack, adapters, store)
    custodian = pack.custodian(measure.custodian_id)
    original = first.retrievals[-1]
    assert original.revision_status is RevisionStatus.PROVISIONAL

    # The custodian publishes the revision, inside the TTL of the print above.
    adapter = adapters[custodian.id]
    series = list(adapter.series(measure.series_identifier))
    latest = series[-1]
    series[-1] = replace(
        latest,
        value=latest.value + Decimal("0.9"),
        revision_status=RevisionStatus.FINAL,
    )
    adapter._series[measure.series_identifier] = tuple(series)

    second = retrieve.pull(measure, custodian, adapter, store, now=NOW)
    revised = second.retrievals[-1]

    assert revised.id != original.id, "the revised figure was discarded"
    assert revised.value == series[-1].value
    assert revised.revision_status is RevisionStatus.FINAL

    superseded = store.get(str(original.id))
    assert superseded is not None and superseded.superseded_at is not None, (
        "the provisional print stayed servable after its revision published"
    )


def test_what_is_cited_is_what_was_judged(pack, adapters, store) -> None:
    """Verdicts read observations; citations read retrievals. They must agree.

    Nothing in the pipeline compares the two, so a reuse path that returned a
    stored row silently produced an artifact whose citation block disagreed
    with the verdict above it — the one failure mode a reader cannot detect,
    because both halves look authoritative.
    """
    measure, first = _record(pack, adapters, store)
    custodian = pack.custodian(measure.custodian_id)
    adapter = adapters[custodian.id]

    series = list(adapter.series(measure.series_identifier))
    series[-1] = replace(series[-1], value=series[-1].value + Decimal("1.3"))
    adapter._series[measure.series_identifier] = tuple(series)

    outcome = retrieve.pull(measure, custodian, adapter, store, now=NOW)

    assert len(outcome.observations) == len(outcome.retrievals)
    for observation, retrieval in zip(outcome.observations, outcome.retrievals):
        assert retrieval.value == observation.value, (
            "the artifact would cite a figure the verdict was not computed from"
        )
        assert retrieval.revision_status is observation.revision_status
        assert retrieval.reference_period == observation.reference_period
