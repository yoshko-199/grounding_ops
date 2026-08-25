"""Sources and accounts, declared as data rather than written in code.

The same argument that puts custodians in packs puts sources here.  A source
list embedded in the harvester is a source list that changes by code review
and ships by release; a source list in ``sources/*.toml`` is auditable in one
place and can be read by someone who does not read Python.

What a source declares:

* **Accounts** — the handles, feeds, or sections to scan.  One source, many
  accounts, which is the multi-account requirement.
* **Backends** — ordered transports for the *same* account.  Ordering matters
  and the ordering is a fallback chain; see :mod:`plugins.harvest.scan` for
  why that is legitimate here and forbidden in the engine.
* **Cadence** — how often the source publishes, which becomes the cache TTL.
* **Date precision** — the best precision any record from this source can
  claim.  A source that admits to displaying approximate dates caps every
  record it produces, and the cap is applied here rather than trusted to the
  parser.
* **Enabled**, with a reason when it is not.  A source may be declared and
  switched off — because its own terms say not to scrape it, because it is
  unlaunched, because nobody has confirmed it is appropriate to collect from.
  Declaring it disabled keeps the reason next to the target instead of in a
  commit message nobody will find.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from plugins.harvest.records import DatePrecision


class InvalidSource(Exception):
    """A source declaration that does not load. Partial sources do not load."""


class BackendKind(Enum):
    """The transports this harvester knows how to parse.

    A closed set, and short on purpose.  It covers the three shapes the prior
    art actually used — a syndication page with JSON embedded in a script tag,
    an RSS mirror, and a plain JSON endpoint — and stops there.  The fourth
    backend in the prior art asks a model with web search to return JSON that
    becomes data; that one is absent by design, and its absence is asserted
    in the tests rather than left to memory.
    """

    RSS = "rss"
    JSON = "json"
    EMBEDDED_JSON = "embedded-json"


@dataclass(frozen=True, slots=True)
class Backend:
    """One transport for one account.

    ``url_template`` is formatted with ``account``.  The remaining fields are
    the parse shape: which node holds the list, and which keys inside it hold
    the text, the link, and the date.  Keeping them as data means a new feed
    of a known shape is a TOML edit rather than a new parser.
    """

    kind: BackendKind
    url_template: str
    items_path: str = ""
    text_field: str = ""
    url_field: str = ""
    date_field: str = ""
    date_format: str = ""
    script_id: str = ""

    def __post_init__(self) -> None:
        if not self.url_template.strip():
            raise InvalidSource("a backend needs a url_template")
        if self.kind in (BackendKind.JSON, BackendKind.EMBEDDED_JSON):
            if not self.items_path:
                raise InvalidSource(f"{self.kind.value} backend needs an items_path")
            if not self.text_field:
                raise InvalidSource(f"{self.kind.value} backend needs a text_field")
        if self.kind is BackendKind.EMBEDDED_JSON and not self.script_id:
            raise InvalidSource("embedded-json backend needs a script_id")

    def url_for(self, account: str) -> str:
        try:
            return self.url_template.format(account=account)
        except (KeyError, IndexError) as exc:
            raise InvalidSource(
                f"url_template {self.url_template!r} uses an unknown placeholder: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True)
class Source:
    """One publication to scan, and the accounts within it."""

    id: str
    name: str
    accounts: tuple[str, ...]
    backends: tuple[Backend, ...]
    cadence: str = "daily"
    date_precision: DatePrecision = DatePrecision.UNKNOWN
    enabled: bool = False
    disabled_reason: str = ""
    notice: str = ""
    languages: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidSource("a source needs an id")
        if not self.accounts:
            raise InvalidSource(f"source {self.id!r} declares no accounts")
        if not self.backends:
            raise InvalidSource(f"source {self.id!r} declares no backends")
        if not self.enabled and not self.disabled_reason.strip():
            raise InvalidSource(
                f"source {self.id!r} is disabled and gives no reason. A source "
                "switched off without a recorded reason gets switched back on by "
                "the next person who notices it is off"
            )


def load_source(path: Path) -> Source:
    """Parse one ``sources/*.toml`` declaration."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise InvalidSource(f"{path.name}: {exc}") from exc

    block = raw.get("source")
    if not isinstance(block, dict):
        raise InvalidSource(f"{path.name}: no [source] block")

    backends: list[Backend] = []
    for index, entry in enumerate(raw.get("backend", ()), 1):
        if not isinstance(entry, dict):
            raise InvalidSource(f"{path.name}: backend {index} is not a table")
        try:
            kind = BackendKind(entry.get("kind", ""))
        except ValueError:
            raise InvalidSource(
                f"{path.name}: backend {index} declares unknown kind "
                f"{entry.get('kind')!r}; known kinds are "
                f"{sorted(k.value for k in BackendKind)}"
            ) from None
        backends.append(
            Backend(
                kind=kind,
                url_template=str(entry.get("url_template", "")),
                items_path=str(entry.get("items_path", "")),
                text_field=str(entry.get("text_field", "")),
                url_field=str(entry.get("url_field", "")),
                date_field=str(entry.get("date_field", "")),
                date_format=str(entry.get("date_format", "")),
                script_id=str(entry.get("script_id", "")),
            )
        )

    try:
        precision = DatePrecision(block.get("date_precision", "unknown"))
    except ValueError:
        raise InvalidSource(
            f"{path.name}: unknown date_precision {block.get('date_precision')!r}"
        ) from None

    return Source(
        id=str(block.get("id", "")),
        name=str(block.get("name", "")),
        accounts=tuple(str(a) for a in block.get("accounts", ())),
        backends=tuple(backends),
        cadence=str(block.get("cadence", "daily")),
        date_precision=precision,
        enabled=bool(block.get("enabled", False)),
        disabled_reason=str(block.get("disabled_reason", "")),
        notice=str(block.get("notice", "")),
        languages=tuple(str(code) for code in block.get("languages", ())),
        metadata=dict(block.get("metadata", {})),
    )


def load_sources(directory: Path) -> tuple[Source, ...]:
    """Load every declaration in ``directory``, sorted by id.

    One bad file fails the load rather than being skipped, on the same
    argument the pack loader makes: a set that silently drops one member
    looks like it is working and is not.
    """
    sources = [load_source(path) for path in sorted(directory.glob("*.toml"))]
    seen: set[str] = set()
    for source in sources:
        if source.id in seen:
            raise InvalidSource(f"duplicate source id {source.id!r}")
        seen.add(source.id)
    return tuple(sorted(sources, key=lambda s: s.id))
