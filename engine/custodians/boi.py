"""Bank of Israel — the first adapter against a real custodian.

**This has not been executed against the live endpoint.** The environment this
was written in blocks ``boi.org.il`` and ``edge.boi.gov.il`` at the egress
policy, so every test below drives it through an injected fetcher. What is
grounded and what is inferred:

* The endpoint shape, the dataflow code ``EXR``, the ``DATA_TYPE=OF00``
  filter that selects representative rates rather than any other rate the
  Bank publishes, the date-range parameters and the ``format=csv`` option all
  come from the Bank's own guide, *Extracting representative exchange rates
  from the new series database*.
* The column names come from the SDMX-CSV standard, which fixes
  ``TIME_PERIOD`` and ``OBS_VALUE``. They are not guesses, but neither have
  they been confirmed against a response from this particular server, so the
  reader below accepts the standard's aliases rather than one spelling.

Until someone runs it against the live service, treat a green test run as
evidence the parsing and the error taxonomy are right, and not as evidence
the URL is.

**On revision status.** The Bank's extraction guide notes that exchange-rate
data in the series database is updated shortly after the rates are published.
Combined with its statement that it "reserves absolute and sole discretion to
make any changes it sees fit in the representative rates", today's rate is
treated as :attr:`~engine.custodians.base.RevisionStatus.PROVISIONAL` and
earlier dates as final. Erring provisional costs a re-pull; erring final pins
a verdict to a figure that could still move, which §8 exists to prevent.
"""

from __future__ import annotations

import csv
import io
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Callable

from engine.custodians.base import CustodianUnreachable, Observation, RevisionStatus

CUSTODIAN_ID = "boi"

#: The SDMX v2 data endpoint named in the Bank's extraction guide.
DEFAULT_BASE = "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow"

USER_AGENT = "grounding-ops/0.5 (claim verification; contact via repository)"

#: Reached, and nothing published at this address. Distinct from failing to
#: arrive, which the adapter contract requires be kept apart.
ABSENT_STATUSES = frozenset({404, 410})

#: SDMX-CSV fixes these names. Aliases are accepted because this adapter has
#: never seen a response from this server, and a column-name mismatch would
#: otherwise read as "the custodian publishes nothing".
_TIME_COLUMNS = ("TIME_PERIOD", "TIME", "OBS_PERIOD")
_VALUE_COLUMNS = ("OBS_VALUE", "VALUE", "OBSERVATION")

Fetcher = Callable[[str], "Response"]


class Response:
    """The minimum an adapter needs from a completed request."""

    __slots__ = ("status", "body")

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body


def _urlopen(url: str, timeout: float = 20.0) -> Response:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return Response(response.status, response.read().decode(charset, "replace"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - the status is what matters
            pass
        return Response(exc.code, body)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise CustodianUnreachable(CUSTODIAN_ID, str(exc)) from exc


def parse_series_id(series_id: str) -> tuple[str, dict[str, str]]:
    """Split ``dataflow:KEY=VALUE,KEY=VALUE`` as the pack declares it.

    The pack carries the whole SDMX key in ``series_identifier`` rather than
    the adapter hardcoding a currency, because which series a measure means is
    the pack's business. An adapter that knew "the dollar rate" would be an
    adapter with a measure baked into it.
    """
    dataflow, _, filters = series_id.partition(":")
    dataflow = dataflow.strip().strip("/")
    if not dataflow:
        raise ValueError(f"no dataflow in series identifier {series_id!r}")

    params: dict[str, str] = {}
    for pair in filters.split(",") if filters else []:
        key, _, value = pair.partition("=")
        if key.strip() and value.strip():
            params[key.strip()] = value.strip()
    return dataflow, params


def build_url(series_id: str, base: str = DEFAULT_BASE) -> str:
    dataflow, params = parse_series_id(series_id)
    query = [(f"c[{key}]", value) for key, value in sorted(params.items())]
    query.append(("format", "csv"))
    return f"{base}/{dataflow}/?{urllib.parse.urlencode(query)}"


class BankOfIsraelAdapter:
    """Pulls a declared series from the Bank's SDMX database.

    Conforms to :class:`~engine.custodians.base.CustodianAdapter`: no
    constructor parameter accepts a URL for a *source*, only a base for the
    Bank's own service and a fetcher for testing. AC-14 turns on there being
    no way to point an adapter at somewhere else, and ``base`` does not
    provide one — it selects an endpoint of the same custodian, the way the
    harvest backends select a transport to one account.
    """

    custodian_id = CUSTODIAN_ID

    def __init__(
        self,
        *,
        fetch: Fetcher | None = None,
        base: str = DEFAULT_BASE,
        timeout: float = 20.0,
        today: date | None = None,
    ) -> None:
        self._fetch = fetch or (lambda url: _urlopen(url, timeout))
        self._base = base
        self._today = today

    def series(self, series_id: str) -> tuple[Observation, ...]:
        """The full series, oldest first.

        Full series rather than a latest point, because §5 requires it: a
        superlative cannot be settled against one current figure plus a
        remembered peak.
        """
        try:
            url = build_url(series_id, self._base)
        except ValueError as exc:
            raise CustodianUnreachable(CUSTODIAN_ID, str(exc)) from exc

        response = self._fetch(url)

        if response.status in ABSENT_STATUSES:
            return ()
        if not 200 <= response.status < 300:
            raise CustodianUnreachable(
                CUSTODIAN_ID,
                f"{url} answered {response.status}; whether the series exists is unknown",
            )

        return self._read(series_id, response.body, url)

    def _read(self, series_id: str, body: str, url: str) -> tuple[Observation, ...]:
        """Parse SDMX-CSV into observations.

        A body that will not parse raises rather than returning empty. Empty
        means "the custodian publishes no such series", which is a statement
        about the record; a shape we do not recognise is a statement about our
        assumptions, and collapsing the two is what §6.1 forbids.
        """
        reader = csv.DictReader(io.StringIO(body))
        if reader.fieldnames is None:
            raise CustodianUnreachable(CUSTODIAN_ID, f"{url} returned no CSV header")

        columns = {name.strip().upper(): name for name in reader.fieldnames}
        time_column = next((columns[c] for c in _TIME_COLUMNS if c in columns), None)
        value_column = next((columns[c] for c in _VALUE_COLUMNS if c in columns), None)
        if time_column is None or value_column is None:
            raise CustodianUnreachable(
                CUSTODIAN_ID,
                f"{url} returned columns {sorted(columns)}, which carry no recognisable "
                "SDMX time and value fields. The series may exist in a shape this "
                "adapter does not read",
            )

        rows = 0
        observations: list[Observation] = []
        for row in reader:
            rows += 1
            observation = self._observation(series_id, row, time_column, value_column)
            if observation is not None:
                observations.append(observation)

        if rows and not observations:
            raise CustodianUnreachable(
                CUSTODIAN_ID,
                f"{url} returned rows, none of which carried a readable period and "
                "value. This is a parse failure, not an empty series",
            )

        observations.sort(key=lambda o: (o.observed_on, o.reference_period))
        return tuple(observations)

    def _observation(
        self, series_id: str, row: dict[str, str], time_column: str, value_column: str
    ) -> Observation | None:
        period = (row.get(time_column) or "").strip()
        raw = (row.get(value_column) or "").strip()
        if not period or not raw:
            return None

        observed_on = _as_date(period)
        if observed_on is None:
            return None
        try:
            value = Decimal(raw)
        except (InvalidOperation, ValueError):
            return None

        today = self._today or date.today()
        return Observation(
            series_id=series_id,
            reference_period=period,
            value=value,
            revision_status=(
                RevisionStatus.PROVISIONAL
                if observed_on >= today
                else RevisionStatus.FINAL
            ),
            observed_on=observed_on,
        )


def _as_date(period: str) -> date | None:
    """Read an SDMX time period. Daily, monthly, and annual forms."""
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(period, fmt).date()
        except ValueError:
            continue
    return None
