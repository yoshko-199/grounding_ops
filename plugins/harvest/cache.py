"""A fetch cache that expires, and has no way not to.

The prior art keeps a ``seen.json`` set so a watch loop does not reprocess the
same item.  It never expires, which is fine for its purpose and wrong for
ours: a source that edits or retracts a claim would be invisible behind a
permanent set, and a harvest that has run once would never see the correction.

§8 states the rule this module follows — "every retrieval carries a TTL
derived from its custodian's publication cadence; expired retrievals are
re-pulled, never served" — and AC-8's note states the temptation: serving
stale data under outage is "standard, sane engineering practice everywhere
else and is forbidden here."  The engine's store is not importable from this
package by design, so the semantics are reimplemented rather than shared, and
the sentinel below exists for the same reason :data:`engine.store.events
.EXPIRED` does: "expired" and "never fetched" lead to the same action for
different reasons, and collapsing them makes the TTL invisible in the code
that depends on it.

There is deliberately no ``force``, no grace period, and no serve-on-failure
branch.  A caller that cannot fetch gets an unreachable outcome and reports it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

from plugins.harvest.records import CandidateClaim


class _Expired:
    """Sentinel for "cached, and no longer servable"."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "EXPIRED"

    def __bool__(self) -> bool:
        return False


EXPIRED: Final = _Expired()

# Source cadence to TTL. An unrecognised cadence gets the shortest TTL rather
# than the longest, on the same argument the engine's table makes: erring
# short costs a re-fetch, erring long serves something stale.
_CADENCE_TTL: Final[tuple[tuple[str, timedelta], ...]] = (
    ("continuous", timedelta(minutes=15)),
    ("hourly", timedelta(hours=1)),
    ("daily", timedelta(days=1)),
    ("weekly", timedelta(days=7)),
    ("monthly", timedelta(days=31)),
)

_DEFAULT_TTL: Final = timedelta(minutes=15)


def ttl_for(cadence: str) -> timedelta:
    lowered = (cadence or "").lower()
    for token, ttl in _CADENCE_TTL:
        if token in lowered:
            return ttl
    return _DEFAULT_TTL


@dataclass(frozen=True, slots=True)
class CacheEntry:
    fetched_at: datetime
    expires_at: datetime
    backend: str
    claims: tuple[CandidateClaim, ...]


class HarvestCache:
    """A JSON-file cache keyed by source, account, and backend.

    In-memory when ``path`` is ``None``, which is what the tests use.  The
    file format is deliberately plain: a harvest cache that cannot be read
    with ``cat`` is a harvest cache nobody audits.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._entries: dict[str, CacheEntry] = {}
        self.expired_on_read = 0
        if path is not None and path.exists():
            self._load(path)

    @staticmethod
    def key(source_id: str, account: str, backend: str) -> str:
        return f"{source_id}\x1f{account}\x1f{backend}"

    def fresh(self, key: str, now: datetime) -> CacheEntry | _Expired | None:
        """The entry if it is still servable, :data:`EXPIRED`, or ``None``."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            self.expired_on_read += 1
            return EXPIRED
        return entry

    def record(
        self,
        key: str,
        *,
        backend: str,
        claims: tuple[CandidateClaim, ...],
        cadence: str,
        now: datetime,
    ) -> CacheEntry:
        entry = CacheEntry(
            fetched_at=now,
            expires_at=now + ttl_for(cadence),
            backend=backend,
            claims=claims,
        )
        self._entries[key] = entry
        return entry

    def flush(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            key: {
                "fetched_at": entry.fetched_at.isoformat(),
                "expires_at": entry.expires_at.isoformat(),
                "backend": entry.backend,
                "claims": [claim.to_dict() for claim in entry.claims],
            }
            for key, entry in sorted(self._entries.items())
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # An unreadable cache is an empty cache. Never a reason to fail a
            # harvest, and never a reason to serve whatever could be salvaged.
            return
        for key, entry in payload.items():
            try:
                self._entries[key] = CacheEntry(
                    fetched_at=_moment(entry["fetched_at"]),
                    expires_at=_moment(entry["expires_at"]),
                    backend=entry.get("backend", ""),
                    claims=tuple(
                        CandidateClaim.from_dict(c) for c in entry.get("claims", ())
                    ),
                )
            except (KeyError, ValueError, TypeError):
                continue


def _moment(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
