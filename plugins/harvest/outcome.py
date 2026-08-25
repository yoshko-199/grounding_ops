"""The three answers a fetch can give, kept apart by construction.

The prior art this package adapts returns ``[]`` from its scraper whether
every mirror timed out or the account genuinely has nothing to show.  That is
the collapse §6.1 forbids on the evidence side, and AC-14 asserts explicitly
that "unreachable" and "reached, publishes nothing" do not become each other:
one is a fact about today's network, the other a fact about the record.

The same distinction matters on the intake side for a different reason.  An
empty scan that means *nothing published* is a finished job.  An empty scan
that means *every transport failed* is a job that must be retried, and a
harvester that cannot tell them apart will quietly stop collecting from a
source that broke, while its logs continue to look like a source that went
quiet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from plugins.harvest.records import CandidateClaim


class Reach(Enum):
    """What happened when a backend was tried."""

    #: The transport failed, or answered with something unparseable. Whether
    #: the account has anything to show is unknown, and "unknown" is not
    #: "nothing" — a body we cannot parse is not a statement that nothing was
    #: published, so the conservative reading is that we did not get there.
    UNREACHABLE = "unreachable"

    #: The transport answered, and the account has nothing matching. A
    #: finished job, not a failed one.
    REACHED_EMPTY = "reached-empty"

    #: The transport answered with items.
    REACHED = "reached"


@dataclass(frozen=True, slots=True)
class FetchOutcome:
    """One backend's answer for one account.

    ``REACHED`` with no items is unconstructible, which is the point: it is
    the exact state the prior art's ``[]`` return silently occupies.
    """

    reach: Reach
    backend: str
    items: tuple[CandidateClaim, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if self.reach is Reach.REACHED and not self.items:
            raise ValueError(
                "REACHED with no items is the ambiguous state this enum exists to "
                "remove; use REACHED_EMPTY, which says the source was reached and "
                "has nothing, or UNREACHABLE, which says we do not know"
            )
        if self.reach is not Reach.REACHED and self.items:
            raise ValueError(f"{self.reach.value} cannot carry items")
        if self.reach is not Reach.REACHED and not self.detail:
            raise ValueError(
                f"{self.reach.value} must say why; an unexplained non-result is "
                "indistinguishable from a bug in the harvester"
            )

    @property
    def usable(self) -> bool:
        return self.reach is Reach.REACHED

    @classmethod
    def unreachable(cls, backend: str, detail: str) -> FetchOutcome:
        return cls(Reach.UNREACHABLE, backend, detail=detail)

    @classmethod
    def reached_empty(cls, backend: str, detail: str) -> FetchOutcome:
        return cls(Reach.REACHED_EMPTY, backend, detail=detail)

    @classmethod
    def reached(cls, backend: str, items: tuple[CandidateClaim, ...]) -> FetchOutcome:
        return cls(Reach.REACHED, backend, items=items)
