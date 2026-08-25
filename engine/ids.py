"""Typed opaque identifiers.

Distinct types rather than bare strings, because several acceptance criteria
are assertions about which identifier a structure is *able* to hold.  AC-16
requires that ``derived_elements`` have "no foreign key by which a retrieval
could attach"; that is checkable by introspection only if a retrieval id is
distinguishable from any other id at the type level.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class _Id:
    value: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ClaimId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class ElementId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class DerivedElementId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class RetrievalId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class MeasureId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class CustodianId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class PackId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class VerdictId(_Id):
    pass


@dataclass(frozen=True, slots=True)
class ReconstructionId(_Id):
    pass
