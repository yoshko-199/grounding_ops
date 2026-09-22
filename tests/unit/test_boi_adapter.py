"""The Bank of Israel adapter, driven offline.

Every test here injects a fetcher. The environment blocks the Bank's hosts, so
none of this proves the URL is right — it proves the parsing and, more
importantly, the error taxonomy are. The taxonomy is what the rest of the
system depends on: §6.1 and AC-14 require *unreachable* and *reached, nothing
there* never to collapse into each other, and an adapter is where that
distinction is either made or lost.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from engine.custodians.base import CustodianUnreachable, RevisionStatus
from engine.custodians.boi import (
    BankOfIsraelAdapter,
    Response,
    build_url,
    parse_series_id,
)

SERIES = "BOI.STATISTICS/EXR/1.0:DATA_TYPE=OF00,CURRENCY=USD"

CSV = """TIME_PERIOD,OBS_VALUE,DATA_TYPE,CURRENCY
2026-08-24,2.9940,OF00,USD
2026-08-25,2.9860,OF00,USD
2026-08-21,3.0010,OF00,USD
"""


def _adapter(answer, **kwargs) -> BankOfIsraelAdapter:
    def fetch(url: str) -> Response:
        if isinstance(answer, Exception):
            raise answer
        return answer

    kwargs.setdefault("today", date(2026, 8, 26))
    return BankOfIsraelAdapter(fetch=fetch, **kwargs)


# ---------------------------------------------------------------------------
# The series key comes from the pack, not from the adapter
# ---------------------------------------------------------------------------


def test_the_series_key_is_parsed_from_the_pack_declaration() -> None:
    dataflow, params = parse_series_id(SERIES)
    assert dataflow == "BOI.STATISTICS/EXR/1.0"
    assert params == {"DATA_TYPE": "OF00", "CURRENCY": "USD"}


def test_the_url_carries_the_declared_filters() -> None:
    url = build_url(SERIES)
    assert "BOI.STATISTICS/EXR/1.0" in url
    assert "c%5BDATA_TYPE%5D=OF00" in url
    assert "c%5BCURRENCY%5D=USD" in url
    assert "format=csv" in url


def test_the_adapter_hardcodes_no_measure() -> None:
    """A currency baked into the adapter would be a measure baked into it."""
    other = "BOI.STATISTICS/EXR/1.0:DATA_TYPE=OF00,CURRENCY=EUR"
    assert "CURRENCY%5D=EUR" in build_url(other)


def test_a_malformed_series_id_is_unreachable_not_empty() -> None:
    adapter = _adapter(Response(200, CSV))
    with pytest.raises(CustodianUnreachable):
        adapter.series(":DATA_TYPE=OF00")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_observations_are_returned_oldest_first() -> None:
    """§5 wants the full series, and the sweep assumes an ordering."""
    observations = _adapter(Response(200, CSV)).series(SERIES)
    assert [o.reference_period for o in observations] == [
        "2026-08-21",
        "2026-08-24",
        "2026-08-25",
    ]
    assert observations[-1].value == Decimal("2.9860")


def test_values_are_decimals_not_floats() -> None:
    """A rate quoted to four places must not go through binary floating point."""
    observations = _adapter(Response(200, CSV)).series(SERIES)
    assert all(isinstance(o.value, Decimal) for o in observations)
    assert observations[0].value == Decimal("3.0010")


def test_todays_rate_is_provisional_and_earlier_ones_are_final() -> None:
    """Erring provisional costs a re-pull; erring final pins a verdict to a
    figure the Bank reserves the right to change."""
    observations = _adapter(Response(200, CSV), today=date(2026, 8, 25)).series(SERIES)
    by_period = {o.reference_period: o.revision_status for o in observations}
    assert by_period["2026-08-25"] is RevisionStatus.PROVISIONAL
    assert by_period["2026-08-24"] is RevisionStatus.FINAL


def test_standard_sdmx_aliases_are_accepted() -> None:
    """The column names are the standard's; this server's have not been seen."""
    body = "TIME,VALUE\n2026-08-25,2.9860\n"
    observations = _adapter(Response(200, body)).series(SERIES)
    assert observations[0].value == Decimal("2.9860")


def test_monthly_and_annual_periods_parse() -> None:
    body = "TIME_PERIOD,OBS_VALUE\n2025,3.5000\n2026-07,3.1000\n"
    observations = _adapter(Response(200, body)).series(SERIES)
    assert [o.reference_period for o in observations] == ["2025", "2026-07"]


def test_rows_with_no_value_are_skipped_not_fatal() -> None:
    body = "TIME_PERIOD,OBS_VALUE\n2026-08-24,\n2026-08-25,2.9860\n"
    observations = _adapter(Response(200, body)).series(SERIES)
    assert len(observations) == 1


# ---------------------------------------------------------------------------
# The error taxonomy — the part the rest of the system depends on
# ---------------------------------------------------------------------------


def test_a_transport_failure_is_unreachable() -> None:
    adapter = _adapter(CustodianUnreachable("boi", "connection reset"))
    with pytest.raises(CustodianUnreachable):
        adapter.series(SERIES)


def test_a_404_is_an_empty_series_not_an_error() -> None:
    """Reached, and the custodian publishes no such series."""
    assert _adapter(Response(404, "")).series(SERIES) == ()


def test_a_500_is_unreachable_not_an_empty_series() -> None:
    """The contract's central distinction. A 500 says nothing about the record."""
    with pytest.raises(CustodianUnreachable, match="unknown"):
        _adapter(Response(503, "")).series(SERIES)


def test_a_header_only_response_is_an_empty_series() -> None:
    """No rows is a real answer: reached, nothing published."""
    assert _adapter(Response(200, "TIME_PERIOD,OBS_VALUE\n")).series(SERIES) == ()


def test_an_unrecognised_shape_is_unreachable_not_empty() -> None:
    """A column-name mismatch must not read as "the custodian has nothing".

    This adapter has never seen a response from this server. If the shape
    differs from the standard, that is a fact about our assumptions, and
    reporting it as an empty series would turn it into a false claim about
    the record.
    """
    body = "date,rate\n2026-08-25,2.9860\n"
    with pytest.raises(CustodianUnreachable, match="does not read"):
        _adapter(Response(200, body)).series(SERIES)


def test_rows_that_all_fail_to_parse_are_unreachable_not_empty() -> None:
    body = "TIME_PERIOD,OBS_VALUE\nnot-a-date,not-a-number\n"
    with pytest.raises(CustodianUnreachable, match="parse failure"):
        _adapter(Response(200, body)).series(SERIES)


def test_no_csv_header_at_all_is_unreachable() -> None:
    with pytest.raises(CustodianUnreachable, match="no CSV header"):
        _adapter(Response(200, "")).series(SERIES)


# ---------------------------------------------------------------------------
# Contract conformance
# ---------------------------------------------------------------------------


def test_the_adapter_satisfies_the_custodian_protocol() -> None:
    from engine.custodians.base import CustodianAdapter

    assert isinstance(_adapter(Response(200, CSV)), CustodianAdapter)
    assert _adapter(Response(200, CSV)).custodian_id == "boi"


def test_the_adapter_accepts_no_source_url() -> None:
    """AC-14: an operator-supplied source is a custodian nobody declared.

    `base` selects an endpoint of the same custodian, the way a harvest
    backend selects a transport to one account. It is not a source parameter,
    and the names AC-14 checks for are absent.
    """
    import inspect

    parameters = inspect.signature(BankOfIsraelAdapter.__init__).parameters
    for forbidden in ("url", "endpoint", "uri", "source", "fallback_url"):
        assert forbidden not in parameters

    series_parameters = inspect.signature(BankOfIsraelAdapter.series).parameters
    assert list(series_parameters) == ["self", "series_id"]


def test_the_live_wiring_returns_the_declared_custodian() -> None:
    from engine.custodians.live import build_live_custodians

    adapters = build_live_custodians()
    assert set(adapters) == {"boi"}
    assert adapters["boi"].custodian_id == "boi"
