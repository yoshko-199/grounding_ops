"""The retrieval-event store.

Spec §8.  Retrievals are events with expiry, not facts.  Two rules from that
section are enforced here rather than left to callers:

* **TTL.** "Every retrieval carries a TTL derived from its custodian's
  publication cadence. Expired retrievals are re-pulled, never served."
* **Provisional invalidation.** "Provisional retrievals are invalidated when
  a revision publishes. A claim true against the first print can be false
  against the revised figure; verdicts pin to a specific revision."

AC-8's note is worth keeping in view while reading this module: serving stale
data under outage is "standard, sane engineering practice everywhere else and
is forbidden here."  There is deliberately no degraded mode, no grace period,
and no force flag.  A caller that cannot get a fresh figure gets
:data:`EXPIRED` and must degrade the element to Unreachable.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Final

from engine.custodians.base import Observation, RevisionStatus
from engine.figures import Figure
from engine.ids import ElementId, RetrievalId

SCHEMA = Path(__file__).with_name("schema.sql")


class _Expired:
    """Sentinel for "a record exists but may not be served".

    A distinct type rather than ``None`` so that "expired" and "never
    retrieved" cannot be confused at a call site.  They lead to the same
    action — re-pull — but for different reasons, and collapsing them makes
    the TTL invisible in the code that depends on it.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "EXPIRED"

    def __bool__(self) -> bool:
        return False


EXPIRED: Final = _Expired()

# Cadence strings are pack free text (interface §3.2), so the mapping is
# tolerant: an unrecognised cadence gets the shortest TTL rather than the
# longest.  Erring short costs a re-pull; erring long serves a stale figure,
# which is the failure §8 exists to prevent.
_CADENCE_TTL: Final[tuple[tuple[str, timedelta], ...]] = (
    ("continuous", timedelta(hours=1)),
    ("daily", timedelta(days=1)),
    ("business", timedelta(days=1)),
    ("weekly", timedelta(days=7)),
    ("monthly", timedelta(days=31)),
    ("quarterly", timedelta(days=92)),
    ("annual", timedelta(days=366)),
    ("yearly", timedelta(days=366)),
    ("per election", timedelta(days=366)),
    ("per sitting", timedelta(days=7)),
    ("periodic", timedelta(days=31)),
)

_DEFAULT_TTL: Final = timedelta(hours=1)


def ttl_for(cadence: str) -> timedelta:
    """Derive a retrieval TTL from a custodian's publication cadence."""
    lowered = (cadence or "").lower()
    for token, ttl in _CADENCE_TTL:
        if token in lowered:
            return ttl
    return _DEFAULT_TTL


@dataclass(frozen=True, slots=True)
class Retrieval:
    """A recorded pull, with everything §5 requires in output."""

    id: RetrievalId
    custodian_id: str
    series_id: str
    reference_period: str
    value: Decimal
    unit: str
    revision_status: RevisionStatus
    retrieved_at: datetime
    ttl_expires_at: datetime
    continuity_status: str
    element_id: ElementId | None = None
    caveat: str | None = None
    linked_series_used: str | None = None
    superseded_at: datetime | None = None

    def is_fresh(self, now: datetime) -> bool:
        return self.superseded_at is None and now < self.ttl_expires_at

    def as_figure(self) -> Figure:
        """Promote to a sourced figure.

        The only route by which a number acquires a :class:`Figure`, which is
        what makes §3 hold: a figure cannot exist without the retrieval that
        justifies it.
        """
        return Figure(
            value=self.value,
            unit=self.unit,
            retrieval_id=self.id,
            reference_period=self.reference_period,
        )


class RetrievalStore:
    """SQLite-backed retrieval events."""

    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA.read_text(encoding="utf-8"))

    def close(self) -> None:
        self._db.close()

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying connection, for composition-root persistence code.

        Not for verification. Every module under `engine.verification` uses
        only the typed methods above; the artifact writer at the composition
        root (`engine.store.writer`, `engine.store.identity_writer`) needs the
        raw connection because §8's other fifteen tables have no typed API of
        their own, and duplicating one here would be schema drift waiting to
        happen. Exposing the connection is safe precisely because nothing that
        must not reach the store's *tables* is the thing this property
        restricts — AC-14 and AC-10 restrict which modules import this class
        at all, not which of its methods they call once they have.
        """
        return self._db

    def record(
        self,
        observation: Observation,
        *,
        custodian_id: str,
        cadence: str,
        unit: str,
        continuity_status: str,
        now: datetime | None = None,
        element_id: ElementId | None = None,
        caveat: str | None = None,
        linked_series_used: str | None = None,
    ) -> Retrieval:
        """Record a pull as an event, deriving its TTL from the cadence."""
        now = now or datetime.now(timezone.utc)
        retrieval = Retrieval(
            id=RetrievalId(),
            custodian_id=custodian_id,
            series_id=observation.series_id,
            reference_period=observation.reference_period,
            value=observation.value,
            unit=unit,
            revision_status=observation.revision_status,
            retrieved_at=now,
            ttl_expires_at=now + ttl_for(cadence),
            continuity_status=continuity_status,
            element_id=element_id,
            caveat=caveat,
            linked_series_used=linked_series_used,
        )
        self._db.execute(
            """
            INSERT INTO retrievals (
                id, element_id, custodian_id, figure, unit, series_id,
                reference_period, revision_status, retrieved_at,
                ttl_expires_at, caveat, continuity_status, linked_series_used,
                superseded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                str(retrieval.id),
                str(element_id) if element_id else None,
                custodian_id,
                str(observation.value),
                unit,
                observation.series_id,
                observation.reference_period,
                observation.revision_status.value,
                now.isoformat(),
                retrieval.ttl_expires_at.isoformat(),
                caveat,
                continuity_status,
                linked_series_used,
            ),
        )
        self._db.commit()
        return retrieval

    def fresh(
        self,
        series_id: str,
        reference_period: str,
        *,
        custodian_id: str,
        now: datetime | None = None,
    ) -> Retrieval | _Expired | None:
        """The most recent usable retrieval, or a reason there is none.

        Returns ``None`` when nothing was ever retrieved, :data:`EXPIRED`
        when a record exists but has aged past its TTL or been superseded.
        There is no argument that relaxes either condition.

        ``custodian_id`` is required, and keyword-only so it cannot be passed
        by accident. A series identifier is unique *within* a custodian and
        nowhere else: two packs are free to name a series the same way, and
        the column was already stored while the lookup ignored it. Making it
        optional would leave the collision one forgetful call site away.
        """
        now = now or datetime.now(timezone.utc)
        row = self._db.execute(
            """
            SELECT * FROM retrievals
            WHERE series_id = ? AND reference_period = ? AND custodian_id = ?
            ORDER BY retrieved_at DESC LIMIT 1
            """,
            (series_id, reference_period, custodian_id),
        ).fetchone()
        if row is None:
            return None
        retrieval = _row_to_retrieval(row)
        return retrieval if retrieval.is_fresh(now) else EXPIRED

    def supersede_provisional(
        self,
        series_id: str,
        reference_period: str,
        *,
        custodian_id: str,
        now: datetime | None = None,
    ) -> int:
        """Invalidate provisional retrievals when a revision publishes (AC-9).

        Invalidation rather than deletion.  The record of what was believed,
        and when, is the point of storing events; a verdict pinned to a
        superseded print must become visibly invalid rather than quietly
        disappear.

        Scoped by custodian for the same reason :meth:`fresh` is: invalidating
        another custodian's identically-named series would be a silent data
        loss rather than a collision anyone would notice.
        """
        now = now or datetime.now(timezone.utc)
        cursor = self._db.execute(
            """
            UPDATE retrievals SET superseded_at = ?
            WHERE series_id = ? AND reference_period = ? AND custodian_id = ?
              AND revision_status = ? AND superseded_at IS NULL
            """,
            (now.isoformat(), series_id, reference_period, custodian_id,
             RevisionStatus.PROVISIONAL.value),
        )
        self._db.commit()
        return cursor.rowcount

    def get(self, retrieval_id: str) -> Retrieval | None:
        row = self._db.execute(
            "SELECT * FROM retrievals WHERE id = ?", (retrieval_id,)
        ).fetchone()
        return _row_to_retrieval(row) if row else None

    def count(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM retrievals").fetchone()[0])


def _row_to_retrieval(row: sqlite3.Row) -> Retrieval:
    return Retrieval(
        id=RetrievalId(row["id"]),
        custodian_id=row["custodian_id"],
        series_id=row["series_id"],
        reference_period=row["reference_period"],
        value=Decimal(row["figure"]),
        unit=row["unit"],
        revision_status=RevisionStatus(row["revision_status"]),
        retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
        ttl_expires_at=datetime.fromisoformat(row["ttl_expires_at"]),
        continuity_status=row["continuity_status"],
        element_id=ElementId(row["element_id"]) if row["element_id"] else None,
        caveat=row["caveat"],
        linked_series_used=row["linked_series_used"],
        superseded_at=(
            datetime.fromisoformat(row["superseded_at"]) if row["superseded_at"] else None
        ),
    )
