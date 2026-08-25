"""Fetching and parsing one account through one backend.

Three shapes, ported from the prior art's three working transports and
generalised so they are configuration rather than code:

* :attr:`~plugins.harvest.sources.BackendKind.EMBEDDED_JSON` — a rendered page
  with its data in a ``<script>`` tag.  The prior art hardcodes
  ``__NEXT_DATA__`` and one path into it; here the script id and the path are
  declared per backend, which is what makes the same code work against any
  server-rendered app rather than one specific site.
* :attr:`~plugins.harvest.sources.BackendKind.RSS` — the mirror case.
* :attr:`~plugins.harvest.sources.BackendKind.JSON` — a plain endpoint.

The fourth transport in the prior art — a model with web search, asked to
return JSON — is not ported.  ``engine/custodians/base.py`` names it directly:
"no web search, no news source, no model prior, no operator-supplied URL."

**On parse failures.**  A body that will not parse produces ``UNREACHABLE``,
not ``REACHED_EMPTY``.  This is the one classification decision in the module
worth arguing: a malformed body is evidence that something is wrong with the
transport or with our assumptions about it, and it is *not* a statement by the
source that the account published nothing.  Reading it as "nothing published"
would let a feed that silently changed format look like an account that went
quiet, which is precisely the failure mode :mod:`plugins.harvest.outcome`
exists to prevent.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime
from typing import Any
from xml.etree import ElementTree

from plugins.harvest.outcome import FetchOutcome
from plugins.harvest.records import (
    CandidateClaim,
    DatePrecision,
    Provenance,
    TextTransform,
)
from plugins.harvest.sources import Backend, BackendKind, Source
from plugins.harvest.transport import ABSENT_STATUSES, Response, Transport, TransportError

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")

# RSS date formats, in the order they are tried. RFC 822 with a numeric offset
# first because it is the one that carries real timezone information; the
# named-zone variant is accepted because feeds emit it and rejecting the item
# over its date stamp would lose the claim.
_RSS_DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d %b %Y %H:%M:%S",
    "%d %b %Y %H:%M:%S %z",
)


def fetch(
    source: Source,
    account: str,
    backend: Backend,
    transport: Transport,
    *,
    now: datetime,
    limit: int | None = None,
) -> FetchOutcome:
    """Try one backend for one account, and say what happened."""
    label = backend.kind.value
    url = backend.url_for(account)

    try:
        response = transport.get(url)
    except TransportError as exc:
        return FetchOutcome.unreachable(label, f"transport failed: {exc}")

    if response.status in ABSENT_STATUSES:
        return FetchOutcome.reached_empty(
            label, f"{url} answered {response.status}: nothing published at this address"
        )
    if not 200 <= response.status < 300:
        return FetchOutcome.unreachable(
            label, f"{url} answered {response.status}; whether anything is there is unknown"
        )

    try:
        rows = _parse(backend, response)
    except _ParseFailure as exc:
        return FetchOutcome.unreachable(label, f"{url}: {exc}")

    if not rows:
        return FetchOutcome.reached_empty(
            label, f"{url} answered {response.status} and lists no items"
        )

    claims = []
    for row in rows:
        claim = _to_claim(row, source, account, label, now)
        if claim is not None:
            claims.append(claim)
        if limit is not None and len(claims) >= limit:
            break

    if not claims:
        return FetchOutcome.reached_empty(
            label, f"{url} listed items, none of which carried usable text"
        )
    return FetchOutcome.reached(label, tuple(claims))


class _ParseFailure(Exception):
    """The body did not have the shape the backend declares."""


class _Row:
    """One parsed item, before it becomes a claim."""

    __slots__ = ("raw", "text", "url", "published_at", "transforms")

    def __init__(
        self,
        raw: str,
        text: str,
        url: str,
        published_at: date | None,
        transforms: tuple[TextTransform, ...],
    ) -> None:
        self.raw = raw
        self.text = text
        self.url = url
        self.published_at = published_at
        self.transforms = transforms


def _parse(backend: Backend, response: Response) -> list[_Row]:
    if backend.kind is BackendKind.RSS:
        return _parse_rss(response.body)
    if backend.kind is BackendKind.JSON:
        return _parse_json(backend, response.body)
    return _parse_embedded_json(backend, response.body)


def _parse_rss(body: str) -> list[_Row]:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise _ParseFailure(f"not parseable as XML: {exc}") from exc

    channel = root.find("channel")
    items = (channel.findall("item") if channel is not None else root.findall(".//item"))

    rows: list[_Row] = []
    for item in items:
        raw = (item.findtext("description") or item.findtext("title") or "").strip()
        if not raw:
            continue
        text, transforms = _clean(raw)
        rows.append(
            _Row(
                raw=raw,
                text=text,
                url=(item.findtext("link") or "").strip(),
                published_at=_rss_date(item.findtext("pubDate")),
                transforms=transforms,
            )
        )
    return rows


def _parse_json(backend: Backend, body: str) -> list[_Row]:
    try:
        document = json.loads(body)
    except json.JSONDecodeError as exc:
        raise _ParseFailure(f"not parseable as JSON: {exc}") from exc
    return _rows_from(backend, document)


def _parse_embedded_json(backend: Backend, body: str) -> list[_Row]:
    """Pull a JSON payload out of a ``<script>`` tag by its id.

    The prior art's syndication backend does exactly this against a fixed
    script id.  Making the id configuration is what turns one site's scraper
    into a backend, and it costs nothing but a field.
    """
    pattern = re.compile(
        rf'<script[^>]*\bid=["\']{re.escape(backend.script_id)}["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(body)
    if not match:
        raise _ParseFailure(f"no <script id={backend.script_id!r}> in the response")
    try:
        document = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise _ParseFailure(f"script {backend.script_id!r} is not JSON: {exc}") from exc
    return _rows_from(backend, document)


def _rows_from(backend: Backend, document: Any) -> list[_Row]:
    node = _walk(document, backend.items_path)
    if node is None:
        raise _ParseFailure(f"items_path {backend.items_path!r} resolves to nothing")
    if not isinstance(node, list):
        raise _ParseFailure(
            f"items_path {backend.items_path!r} resolves to {type(node).__name__}, not a list"
        )

    rows: list[_Row] = []
    for entry in node:
        if not isinstance(entry, dict):
            continue
        raw = _walk(entry, backend.text_field)
        if not isinstance(raw, str) or not raw.strip():
            continue
        text, transforms = _clean(raw)
        link = _walk(entry, backend.url_field) if backend.url_field else ""
        stamp = _walk(entry, backend.date_field) if backend.date_field else None
        rows.append(
            _Row(
                raw=raw,
                text=text,
                url=link if isinstance(link, str) else "",
                published_at=_parse_date(stamp, backend.date_format),
                transforms=transforms,
            )
        )
    return rows


def _walk(document: Any, path: str) -> Any:
    """Resolve a dotted path, returning ``None`` where it does not exist."""
    if not path:
        return None
    node = document
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        elif isinstance(node, list) and part.isdigit():
            index = int(part)
            node = node[index] if index < len(node) else None
        else:
            return None
        if node is None:
            return None
    return node


def _clean(raw: str) -> tuple[str, tuple[TextTransform, ...]]:
    """Normalise a body for reading, and say exactly what was changed.

    Every branch here records itself.  The prior art strips tags with a bare
    ``re.sub`` and keeps only the result, which means a record's text may
    differ from what the claimant wrote with nothing in the record saying so.
    Since §9.7.1 anchors derived elements to spans of the original, that
    difference surfaces much later as a span that resolves to the wrong words.
    """
    transforms: list[TextTransform] = []
    text = raw

    stripped = _TAG.sub(" ", text)
    if stripped != text:
        transforms.append(TextTransform.HTML_STRIPPED)
        text = stripped

    unescaped = html.unescape(text)
    if unescaped != text:
        transforms.append(TextTransform.ENTITIES_DECODED)
        text = unescaped

    collapsed = _WHITESPACE.sub(" ", text).strip()
    if collapsed != text:
        transforms.append(TextTransform.WHITESPACE_COLLAPSED)
        text = collapsed

    return text, tuple(transforms)


def _rss_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in _RSS_DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_date(value: Any, fmt: str) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    if fmt:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return _rss_date(value)


def _to_claim(
    row: _Row,
    source: Source,
    account: str,
    backend_label: str,
    now: datetime,
) -> CandidateClaim | None:
    """Build the record, applying the source's declared precision cap.

    The cap is applied here rather than trusted to the parser, because the
    parser cannot know it.  A feed emits a well-formed timestamp whether or
    not the publisher established that timestamp from the original utterance;
    only the source declaration knows which of those is true, and a source
    that admits to displaying approximate dates makes every timestamp it emits
    approximate no matter how precise it looks.
    """
    if not row.text.strip():
        return None

    if row.published_at is None:
        precision = DatePrecision.UNKNOWN
    elif source.date_precision is DatePrecision.UNKNOWN:
        # The source says nothing about its dating. A timestamp of unstated
        # provenance is not an exact date, and calling it one is the whole
        # error this field exists to prevent.
        precision = DatePrecision.APPROXIMATE
    else:
        precision = source.date_precision

    published = row.published_at if precision is not DatePrecision.UNKNOWN else None

    return CandidateClaim(
        text=row.text,
        raw=row.raw,
        provenance=Provenance(
            source_id=source.id,
            account=account,
            backend=backend_label,
            url=row.url,
            fetched_at=now,
        ),
        transforms=row.transforms,
        published_at=published,
        date_precision=precision,
    )
