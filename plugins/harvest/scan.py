"""Scanning many sources and many accounts, and reporting honestly.

**Why an ordered fallback chain is allowed here and forbidden in the engine.**

``engine/verification/retrieve.py`` pulls from exactly one custodian and has
no fallback, because §9.4 forbids one: a second source consulted when the
first is unavailable is a source nobody declared as authoritative for that
measure, and AC-14 calls that "the criterion that keeps generalisation from
becoming dilution."

The chain in this module looks like the same thing and is not.  Its members
are alternative **transports to one account** — a mirror of a feed, a JSON
endpoint for the page you were already reading — not alternative authorities
for one question.  Whichever answers, the claimant is the same person and the
words are the same words.  Nothing here is deciding *what is true*; it is
deciding *how to reach text somebody already published*.

Two consequences, both enforced below rather than trusted:

* **The chain never crosses sources.**  :func:`scan` loops over sources
  independently and there is no branch in which one source's failure causes
  another to be consulted.  That would be substitution of authority, which is
  the thing §9.4 actually prohibits.
* **Every attempt is reported, not just the one that worked.**
  :class:`SourceReport` keeps the whole ladder.  A source whose first backend
  has been failing for a month while the second quietly carries it is a source
  about to go dark, and the only place that is visible is the attempt list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from plugins.harvest import backends as backend_module
from plugins.harvest.cache import EXPIRED, CacheEntry, HarvestCache
from plugins.harvest.outcome import FetchOutcome, Reach
from plugins.harvest.records import CandidateClaim
from plugins.harvest.sources import Source
from plugins.harvest.transport import Transport


class SourceDisabled(Exception):
    """A disabled source was scanned without being explicitly allowed."""


@dataclass(frozen=True, slots=True)
class Attempt:
    backend: str
    reach: Reach
    detail: str


@dataclass(frozen=True, slots=True)
class SourceReport:
    """What happened for one account of one source."""

    source_id: str
    account: str
    reach: Reach
    attempts: tuple[Attempt, ...]
    backend_used: str = ""
    served_from_cache: bool = False
    claims: tuple[CandidateClaim, ...] = ()

    @property
    def needs_retry(self) -> bool:
        """Whether this account should be tried again.

        ``REACHED_EMPTY`` is a finished job. ``UNREACHABLE`` is not, and the
        difference is the entire reason :class:`~plugins.harvest.outcome.Reach`
        has three values instead of a boolean.
        """
        return self.reach is Reach.UNREACHABLE


@dataclass(frozen=True, slots=True)
class ScanResult:
    reports: tuple[SourceReport, ...] = ()
    skipped: tuple[tuple[str, str], ...] = ()
    expired_cache_entries: int = 0

    @property
    def claims(self) -> tuple[CandidateClaim, ...]:
        """Every claim harvested, deduplicated across backends.

        Deduplication is by :attr:`~plugins.harvest.records.CandidateClaim
        .identity_key` and keeps the first record seen, which is the one from
        the earliest backend in the declared order — the source's own stated
        preference about which transport it trusts most.
        """
        seen: set[str] = set()
        out: list[CandidateClaim] = []
        for report in self.reports:
            for claim in report.claims:
                if claim.identity_key in seen:
                    continue
                seen.add(claim.identity_key)
                out.append(claim)
        return tuple(out)

    @property
    def unreachable(self) -> tuple[SourceReport, ...]:
        return tuple(r for r in self.reports if r.needs_retry)


@dataclass
class _Accumulator:
    reports: list[SourceReport] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def scan(
    sources: tuple[Source, ...],
    transport: Transport,
    cache: HarvestCache,
    *,
    now: datetime,
    limit_per_account: int | None = None,
    allow_disabled: frozenset[str] = frozenset(),
) -> ScanResult:
    """Scan every enabled source, account by account.

    ``allow_disabled`` names source ids the caller has explicitly decided to
    scan despite their declaration.  Disabled sources are skipped silently by
    default and never enabled by a flag that turns on all of them at once:
    the reason a source is off is specific to that source, and a blanket
    override is a way of not reading it.
    """
    acc = _Accumulator()

    for source in sources:
        if not source.enabled and source.id not in allow_disabled:
            acc.skipped.append((source.id, source.disabled_reason))
            continue
        for account in source.accounts:
            acc.reports.append(
                _scan_account(
                    source,
                    account,
                    transport,
                    cache,
                    now=now,
                    limit=limit_per_account,
                )
            )

    return ScanResult(
        reports=tuple(acc.reports),
        skipped=tuple(acc.skipped),
        expired_cache_entries=cache.expired_on_read,
    )


def _scan_account(
    source: Source,
    account: str,
    transport: Transport,
    cache: HarvestCache,
    *,
    now: datetime,
    limit: int | None,
) -> SourceReport:
    attempts: list[Attempt] = []

    for backend in source.backends:
        label = backend.kind.value
        key = HarvestCache.key(source.id, account, label)

        cached = cache.fresh(key, now)
        if isinstance(cached, CacheEntry):
            attempts.append(
                Attempt(label, Reach.REACHED, "served from cache within its TTL")
            )
            return SourceReport(
                source_id=source.id,
                account=account,
                reach=Reach.REACHED,
                attempts=tuple(attempts),
                backend_used=label,
                served_from_cache=True,
                claims=cached.claims[:limit] if limit else cached.claims,
            )
        # `cached is EXPIRED` needs no branch of its own: the only correct
        # response to an expired entry is to fetch, which is what happens
        # next. It is counted on the cache for reporting, never served.
        assert cached is None or cached is EXPIRED

        outcome: FetchOutcome = backend_module.fetch(
            source, account, backend, transport, now=now, limit=limit
        )
        attempts.append(Attempt(label, outcome.reach, outcome.detail))

        if outcome.usable:
            cache.record(
                key,
                backend=label,
                claims=outcome.items,
                cadence=source.cadence,
                now=now,
            )
            return SourceReport(
                source_id=source.id,
                account=account,
                reach=Reach.REACHED,
                attempts=tuple(attempts),
                backend_used=label,
                claims=outcome.items,
            )

    return SourceReport(
        source_id=source.id,
        account=account,
        reach=_overall(attempts),
        attempts=tuple(attempts),
    )


def _overall(attempts: list[Attempt]) -> Reach:
    """The account's verdict once every backend has been tried.

    If any backend got there and found nothing, the account has nothing:
    that is a real answer and re-running will not change it.  If none got
    there, the answer is unknown.  Reporting the second as the first is how a
    broken harvester looks like a quiet source.
    """
    if any(a.reach is Reach.REACHED_EMPTY for a in attempts):
        return Reach.REACHED_EMPTY
    return Reach.UNREACHABLE
