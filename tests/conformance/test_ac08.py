"""AC-8 — TTL enforcement.

Constraint: spec §8.  Expired retrievals are re-pulled, never served.

AC-8's note is the whole criterion: serving stale data under outage is
"standard, sane engineering practice everywhere else and is forbidden here. A
cached figure reused without re-checking is functionally identical to a figure
recalled from memory."  Every test below is therefore checking for the
*absence* of a convenience.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from engine.codes import LanguageCode
from engine.custodians.base import CustodianUnreachable
from engine.elements import ElementStatus
from engine.store.events import EXPIRED, ttl_for
from engine.verification import retrieve

NOW = datetime(2022, 1, 1, tzinfo=timezone.utc)


def test_ttl_is_derived_from_the_custodians_cadence() -> None:
    assert ttl_for("daily, business days") == timedelta(days=1)
    assert ttl_for("monthly") == timedelta(days=31)
    assert ttl_for("per election") == timedelta(days=366)


def test_unrecognised_cadence_errs_short_not_long() -> None:
    """Erring short costs a re-pull; erring long serves a stale figure."""
    assert ttl_for("whenever we get around to it") <= timedelta(hours=1)
    assert ttl_for("") <= timedelta(hours=1)


def test_expired_retrieval_is_not_served(pack, adapters, store) -> None:
    measure = pack.measure("price_index")
    custodian = pack.custodian("zzstat")
    retrieve.pull(measure, custodian, adapters["zzstat"], store, now=NOW)
    before = store.count()
    assert before > 0

    series_id = measure.series_identifier
    period = adapters["zzstat"].series(series_id)[-1].reference_period
    assert store.fresh(series_id, period, NOW) not in (None, EXPIRED)

    # Age past the monthly TTL.
    later = NOW + timedelta(days=40)
    assert store.fresh(series_id, period, later) is EXPIRED


def test_expired_retrieval_causes_a_re_pull(pack, adapters, store) -> None:
    measure = pack.measure("price_index")
    custodian = pack.custodian("zzstat")
    retrieve.pull(measure, custodian, adapters["zzstat"], store, now=NOW)
    first = store.count()

    # Within TTL: reused, no new events.
    retrieve.pull(measure, custodian, adapters["zzstat"], store, now=NOW + timedelta(days=1))
    assert store.count() == first

    # Past TTL: re-pulled, new events recorded.
    retrieve.pull(measure, custodian, adapters["zzstat"], store, now=NOW + timedelta(days=40))
    assert store.count() > first


def test_unreachable_custodian_degrades_rather_than_serving_stale(
    pack, adapters, store
) -> None:
    """The criterion's sharpest edge.

    "Assert that if the re-pull fails, the element degrades to Unreachable and
    the expired figure is not served."  A cache that answers when the source
    is down is the one behaviour §8 singles out as forbidden.
    """
    measure = pack.measure("price_index")
    custodian = pack.custodian("zzstat")
    retrieve.pull(measure, custodian, adapters["zzstat"], store, now=NOW)

    adapters["zzstat"].unreachable = True
    outcome = retrieve.pull(
        measure, custodian, adapters["zzstat"], store, now=NOW + timedelta(days=40)
    )

    assert outcome.blocked_status is ElementStatus.UNREACHABLE
    assert not outcome.observations, "an expired figure was served under outage"
    assert not outcome.retrievals


def test_store_exposes_no_force_or_grace_surface(store) -> None:
    """There is no parameter that relaxes the TTL."""
    import inspect

    signature = inspect.signature(store.fresh)
    for parameter in signature.parameters:
        assert parameter not in ("force", "allow_stale", "grace", "fallback", "max_age")


def test_superseded_provisional_is_not_fresh(pack, adapters, store) -> None:
    """AC-9's mechanism, exercised here because it shares the freshness path."""
    measure = pack.measure("unemployment_survey")
    custodian = pack.custodian("zzstat")
    retrieve.pull(measure, custodian, adapters["zzstat"], store, now=NOW)

    series_id = measure.series_identifier
    period = adapters["zzstat"].series(series_id)[-1].reference_period
    assert store.fresh(series_id, period, NOW) not in (None, EXPIRED)

    assert store.supersede_provisional(series_id, period, NOW) == 1
    assert store.fresh(series_id, period, NOW) is EXPIRED
