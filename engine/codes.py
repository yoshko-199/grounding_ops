"""Closed code types for values that cross into the verification path.

Spec §9.8.1 splits provenance at ingest and lets only a jurisdiction code
cross into verification; §9.8.1 as amended in v0.4 does the same for the
claim's language.  AC-17 asserts that ``claim_context`` carries no free-text
field, and AC-6 asserts that a venue string cannot influence routing.

The types here are what make those assertions structural rather than
conventional.  A venue string cannot be constructed into a
:class:`JurisdictionCode`, so the smuggling route §9.8 describes is closed at
the type level rather than by a filter someone has to remember to apply
downstream.  Two letters cannot carry a name, an affiliation, or an audience.

On unassigned codes: shape validation admits well-formed codes that no
standards body has assigned.  That is deliberate and safe.  An unassigned
code resolves to no loaded pack, and interface §4.1 makes that
**Insufficient Data** — the correct outcome per §9.8.3, which forbids any
fallback or "most likely" inference.  Validating shape rather than
membership keeps this module free of a jurisdiction registry that would
have to be maintained in step with the world.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# Supranational bodies publish harmonised measures and are declared as packs
# in their own right (interface §5).  They are enumerated rather than
# shape-checked because they have no standard code form.
SUPRANATIONAL: Final[frozenset[str]] = frozenset(
    {"OECD", "EUROSTAT", "EU", "UN", "IMF", "WORLDBANK", "WHO", "ILO"}
)

_NATIONAL: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2}$")
_LANGUAGE: Final[re.Pattern[str]] = re.compile(r"^[a-z]{2,3}$")


class InvalidCode(ValueError):
    """Raised when a value cannot be a code.

    Raising rather than coercing is the point.  A caller handing free text to
    a code constructor has made a category error, and silently normalising it
    would reintroduce exactly the channel §9.8.1 closes.
    """


@dataclass(frozen=True, slots=True)
class JurisdictionCode:
    """An ISO 3166-1 alpha-2 code, or a declared supranational identifier."""

    value: str

    def __post_init__(self) -> None:
        v = self.value
        if not isinstance(v, str) or not (_NATIONAL.match(v) or v in SUPRANATIONAL):
            raise InvalidCode(
                f"not a jurisdiction code: {v!r}. "
                "Expected two uppercase letters or a declared supranational identifier."
            )

    @property
    def is_supranational(self) -> bool:
        return self.value in SUPRANATIONAL

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class LanguageCode:
    """An ISO 639 language code.

    Claims arrive in languages custodians do not publish in, and the gap is
    where measure names get mistranslated (interface §3.1).  The code is
    carried so a pack can select the right lexicon (interface §3.6), never so
    that anything about the claimant can be inferred from it.
    """

    value: str

    def __post_init__(self) -> None:
        v = self.value
        if not isinstance(v, str) or not _LANGUAGE.match(v):
            raise InvalidCode(
                f"not a language code: {v!r}. Expected an ISO 639 code, lowercase."
            )

    def __str__(self) -> str:
        return self.value
