"""Stage 5 — retrieval, the citation record, and the continuity check.

Spec §5 fixes what every retrieval records, and §8 fixes how it is stored.
Two rules shape this module more than the rest:

* The **full series** is pulled, not a single point.  §5: "For any 'highest /
  lowest / first time in N years' element, a single current figure is
  insufficient [...] A remembered historical peak is a fabricated comparison."
* **Unreachable is not Unverified.**  §6.1 keeps them apart and AC-14 asserts
  neither collapses into the other.  A custodian that could not be reached
  today is a fact about the network; a custodian reached with nothing covering
  the element is a fact about the record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from engine.custodians.base import CustodianAdapter, CustodianUnreachable, Observation
from engine.elements import ContinuityStatus, ElementStatus
from engine.packs.schema import Custodian, Measure
from engine.store.events import EXPIRED, Retrieval, RetrievalStore
from engine.verification import continuity as continuity_check
from engine.verification.continuity import ContinuityOutcome


@dataclass(frozen=True, slots=True)
class PullOutcome:
    """Everything Stage 6 needs, and nothing it has to re-derive."""

    observations: tuple[Observation, ...] = ()
    retrievals: tuple[Retrieval, ...] = ()
    continuity: ContinuityOutcome = ContinuityOutcome(ContinuityStatus.NOT_APPLICABLE)
    blocked_status: ElementStatus | None = None
    detail: str = ""
    #: Technical text about *why* a pull failed — a status code, a timeout,
    #: a parse complaint. Deliberately separate from `detail`, which is
    #: rendered. An adapter's error message is not a figure from a
    #: retrieval, so any numeral in it fails AC-7's scan at the render
    #: boundary; interpolating it into the reason turned every unreachable
    #: custodian into a crash. This field keeps the diagnosis without
    #: putting it in the artifact, where a proxy's status code has no
    #: business appearing anyway.
    diagnostic: str = ""

    @property
    def has_data(self) -> bool:
        return bool(self.observations)

    @property
    def latest(self) -> Observation | None:
        return self.observations[-1] if self.observations else None


def pull(
    measure: Measure,
    custodian: Custodian,
    adapter: CustodianAdapter,
    store: RetrievalStore,
    *,
    now: datetime | None = None,
    compares_across_time: bool = False,
) -> PullOutcome:
    """Pull a measure's series and record it as retrieval events."""
    now = now or datetime.now(timezone.utc)

    series_id = measure.series_identifier
    try:
        observations = adapter.series(series_id)
    except CustodianUnreachable as exc:
        return PullOutcome(
            blocked_status=ElementStatus.UNREACHABLE,
            detail=(
                f"{custodian.name} could not be reached this session. This is "
                "distinct from the custodian having no figure for the element, and "
                "must not be reported as Unverified"
            ),
            diagnostic=str(exc),
        )

    if not observations:
        return PullOutcome(
            blocked_status=ElementStatus.UNVERIFIED,
            detail=(
                f"{custodian.name} was reached, and publishes no series {series_id!r} "
                "covering this element"
            ),
        )

    outcome = (
        continuity_check.check(
            measure, observations[0].observed_on, observations[-1].observed_on
        )
        if compares_across_time
        else continuity_check.not_applicable()
    )

    # Where a linked series spans the break, use it — and record which, in
    # `retrievals.linked_series_used` (§9.5). The unlinked case is not
    # substituted for: there is nothing to substitute, and splicing the two
    # sides would fabricate the comparison.
    if outcome.status is ContinuityStatus.LINKED_SERIES_USED and outcome.linked_series_used:
        try:
            linked = adapter.series(outcome.linked_series_used)
        except CustodianUnreachable as exc:
            return PullOutcome(
                blocked_status=ElementStatus.UNREACHABLE,
                detail=f"linked series unreachable: {exc}",
            )
        if linked:
            observations = linked
            series_id = outcome.linked_series_used

    retrievals = tuple(
        _record(store, observation, custodian, measure, outcome, now)
        for observation in observations
    )
    return PullOutcome(
        observations=observations,
        retrievals=retrievals,
        continuity=outcome,
    )


def _record(
    store: RetrievalStore,
    observation: Observation,
    custodian: Custodian,
    measure: Measure,
    outcome: ContinuityOutcome,
    now: datetime,
) -> Retrieval:
    """Record one observation, reusing a fresh prior retrieval if one exists.

    Reuse is bounded by the TTL and nothing else. §8: "Every retrieval carries
    a TTL derived from its custodian's publication cadence. Expired retrievals
    are re-pulled, never served." There is no branch here that serves an
    expired record under outage or rate limiting — AC-8 forbids it explicitly,
    and calls it standard engineering practice everywhere else.
    """
    existing = store.fresh(observation.series_id, observation.reference_period, now)
    if existing is not None and existing is not EXPIRED:
        return existing  # type: ignore[return-value]

    caveat_parts = [p for p in (outcome.caveat, _measure_caveat(measure)) if p]
    return store.record(
        observation,
        custodian_id=custodian.id,
        cadence=custodian.cadence,
        unit=measure.unit,
        continuity_status=outcome.status.value,
        now=now,
        caveat=" ".join(caveat_parts) or None,
        linked_series_used=outcome.linked_series_used,
    )


def _measure_caveat(measure: Measure) -> str | None:
    """§5's framing caveat, from the measure's declared confusions.

    Surfacing these is not decoration. The pack records them because the
    measure is "routinely mistaken" for its neighbours, and the mistake
    changes the answer while leaving the headline number recognisable.
    """
    real = [c for c in measure.known_confusions if c.strip().lower() != "none known"]
    return f"Framing: {real[0]}" if real else None
