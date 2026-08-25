"""The custodian adapter contract.

An adapter is the only thing in the system permitted to produce a number that
did not already come from a retrieval.  That makes this module the boundary
AC-14 guards: "assert by static analysis that no retrieval path can reach a
source that is not a declared custodian in a loaded pack — no web search, no
news source, no model prior, no operator-supplied URL."

Adapters are resolved by custodian id against a loaded pack.  There is no
adapter that accepts a URL, and no fallback adapter that answers when no
custodian is declared.  The absence is the guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Protocol, runtime_checkable


class RevisionStatus(Enum):
    """Spec §5, field 6.  Verdicts pin to a specific revision (§8)."""

    PROVISIONAL = "provisional"
    REVISED = "revised"
    FINAL = "final"


class CustodianUnreachable(Exception):
    """The custodian could not be reached this session.

    Distinct from "reached, and nothing covers this element".  §6.1 keeps
    Unreachable and Unverified apart and AC-14 asserts neither collapses into
    the other, because they mean different things to a reader: one is a fact
    about the record, the other is a fact about today's network.
    """

    def __init__(self, custodian_id: str, detail: str = "") -> None:
        self.custodian_id = custodian_id
        super().__init__(f"custodian {custodian_id!r} unreachable: {detail}".rstrip(": "))


@dataclass(frozen=True, slots=True)
class Observation:
    """One published data point, as the custodian publishes it.

    Not yet a :class:`~engine.figures.Figure` — it becomes one only once it
    has been recorded as a retrieval and carries that retrieval's id.  The
    two-step exists so that no code path can produce a figure without also
    producing the record that justifies it.
    """

    series_id: str
    reference_period: str
    value: Decimal
    revision_status: RevisionStatus
    observed_on: date


@runtime_checkable
class CustodianAdapter(Protocol):
    """What every custodian adapter must provide."""

    custodian_id: str

    def series(self, series_id: str) -> tuple[Observation, ...]:
        """The full series, oldest first.

        Full series rather than a single point, because §5 requires it: "For
        any 'highest / lowest / first time in N years' element, a single
        current figure is insufficient. The full series must be pulled, and
        the index base must be confirmed not to have changed mid-series. A
        remembered historical peak is a fabricated comparison."

        Raises :class:`CustodianUnreachable` if the custodian cannot be
        reached.  Returns an empty tuple if the custodian was reached and
        publishes no such series — the two are different answers.
        """
        ...
