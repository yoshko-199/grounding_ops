"""HTTP, behind a seam narrow enough to test without a network.

The whole package depends on exactly one operation — fetch a URL, get bytes
back or an error — so that is the whole protocol.  Everything above it is
parsing and bookkeeping and can be exercised against
:class:`RecordedTransport` with no sockets involved, which is why the harvest
tests are deterministic despite the subject matter being anything but.

Stdlib only.  The prior art reaches for ``httpx``; this repository has an
empty ``dependencies`` list in ``pyproject.toml`` and the value of keeping it
that way exceeds the value of async fetching for a job that runs occasionally
and is bounded by politeness delays rather than by throughput.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from urllib.parse import urlsplit

USER_AGENT = "grounding-ops-harvest/0.1 (claim intake; contact via repository)"

#: Minimum seconds between requests to the same host. Not configurable per
#: source on purpose: a source that wants to be scraped faster can say so by
#: publishing an API, and a harvester that lets its own config file overrule
#: politeness will eventually be pointed at something it should not hammer.
MIN_HOST_INTERVAL = 1.0

#: Statuses meaning "we got there, and there is nothing at this address".
#: Everything else non-2xx is a failure to arrive. The split matters because
#: the two produce different :class:`~plugins.harvest.outcome.Reach` values.
ABSENT_STATUSES = frozenset({404, 410})


class TransportError(Exception):
    """The request did not complete. Distinct from completing with a status."""


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    body: str
    url: str


@runtime_checkable
class Transport(Protocol):
    def get(self, url: str) -> Response:
        """Fetch ``url``.

        Returns a :class:`Response` for any completed request, including a
        4xx or 5xx. Raises :class:`TransportError` when the request did not
        complete at all — DNS failure, timeout, connection reset.
        """
        ...


class UrllibTransport:
    """The real one.

    Deliberately unclever: one request at a time, a fixed delay per host, a
    hard timeout, no redirect chasing beyond urllib's default, no cookie jar,
    and no authenticated mode.  The prior art offers an authenticated backend
    for logged-in access; that is a credential in a scraper aimed at a third
    party's site, and it is not reproduced here.
    """

    def __init__(self, *, timeout: float = 20.0, min_interval: float = MIN_HOST_INTERVAL) -> None:
        self._timeout = timeout
        self._min_interval = min_interval
        self._last_request_at: dict[str, float] = {}

    def get(self, url: str) -> Response:
        self._wait_for(urlsplit(url).netloc)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, application/xml, text/xml, text/html",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                return Response(response.status, body, response.geturl())
        except urllib.error.HTTPError as exc:
            # A status is an answer, even an unwelcome one. Only the caller
            # knows whether 404 means "nothing published" for this backend.
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - the status is what matters
                pass
            return Response(exc.code, body, url)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise TransportError(f"{url}: {exc}") from exc

    def _wait_for(self, host: str) -> None:
        last = self._last_request_at.get(host)
        now = time.monotonic()
        if last is not None:
            remaining = self._min_interval - (now - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[host] = time.monotonic()


class RecordedTransport:
    """A transport backed by a fixed map, for tests and dry runs.

    Values may be a :class:`Response` or an exception instance; an exception
    is raised rather than returned, so a test can exercise the unreachable
    path without depending on a host actually being down.  Unmapped URLs
    raise, because a test that silently fetches nothing passes for the wrong
    reason.
    """

    def __init__(self, responses: dict[str, Response | Exception]) -> None:
        self._responses = dict(responses)
        self.requested: list[str] = []

    def get(self, url: str) -> Response:
        self.requested.append(url)
        try:
            answer = self._responses[url]
        except KeyError:
            raise TransportError(f"{url}: not in the recorded set") from None
        if isinstance(answer, Exception):
            raise answer
        return answer
