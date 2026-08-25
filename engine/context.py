"""The half of ingest provenance that crosses into verification.

Spec §9.8.1 splits Stage 0 provenance into two structures.  This is the one
that crosses.  It lives in its own module, imported by nothing that also
imports :mod:`engine.ingest.identity`, so that AC-6's static-reachability
assertion is a property of the import graph rather than a convention.

Every field here is a code or a date.  AC-17 asserts that in so many words,
and it holds only if it holds without exception — a single free-text field
is a channel regardless of what anyone intends to put in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode


@dataclass(frozen=True, slots=True)
class ClaimContext:
    """Jurisdiction hint, language, and stated-at date.

    ``jurisdiction`` is a hint, not an answer.  §9.8.2 resolves jurisdiction
    in a fixed order and prefers an explicit mention in the claim text over
    this field, precisely because the claim text needs no provenance at all.
    """

    jurisdiction: JurisdictionCode | None
    language: LanguageCode
    stated_at: date
