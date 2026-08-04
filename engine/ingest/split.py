"""Stage 0 — the ingest split.

Spec §9.8.1.  This module is where both halves of provenance exist at once,
and it is deliberately the only one.  Everything downstream receives a
:class:`~engine.context.ClaimContext`; nothing downstream receives, or can
import its way to, a :class:`~engine.ingest.identity.ClaimantIdentity`.

Splitting here rather than filtering at point of use is the whole point.  A
filter is a rule that holds while everyone remembers it.  A split means
there is no downstream code path that *could* read the identity, which is
what makes AC-6's static-reachability assertion hold rather than merely pass
today.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from engine.codes import InvalidCode, JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.ingest.identity import ClaimantIdentity


@dataclass(frozen=True, slots=True)
class RawProvenance:
    """What a caller supplies at Stage 0, before the split.

    ``jurisdiction_hint`` arrives as a string because callers hold strings;
    it is validated into a code here, at the boundary, and a value that is
    not a code is rejected rather than coerced.  Every other free-text field
    on this structure routes to the identity side.
    """

    stated_at: date
    language: str
    jurisdiction_hint: str | None = None
    claimant_name: str | None = None
    claimant_affiliation: str | None = None
    claimant_role: str | None = None
    venue: str | None = None
    audience: str | None = None


def split(raw: RawProvenance) -> tuple[ClaimContext, ClaimantIdentity]:
    """Divide provenance into the crossing half and the non-crossing half.

    The jurisdiction hint is derived from ``raw.jurisdiction_hint`` and from
    nothing else.  Venue and audience are not consulted, not normalised into
    a code, and not used as a fallback when the hint is absent — §9.8.3
    forbids any default or "most likely" inference, and an unresolvable
    jurisdiction is **Insufficient Data**, which §7.5 requires to render as a
    first-class answer.
    """
    context = ClaimContext(
        jurisdiction=_as_jurisdiction(raw.jurisdiction_hint),
        language=LanguageCode(raw.language),
        stated_at=raw.stated_at,
    )
    identity = ClaimantIdentity(
        name=raw.claimant_name,
        affiliation=raw.claimant_affiliation,
        role=raw.claimant_role,
        venue=raw.venue,
        audience=raw.audience,
    )
    return context, identity


def _as_jurisdiction(hint: str | None) -> JurisdictionCode | None:
    """Validate a hint into a code, or None.

    A malformed hint becomes None rather than raising.  The caller supplied
    something that is not a jurisdiction, and the correct response is to
    proceed with no hint — §9.8.2 has three further resolution rules, and the
    fourth outcome is Insufficient Data.  Raising here would make a bad hint
    louder than a missing one, which inverts the intended failure mode.
    """
    if hint is None:
        return None
    try:
        return JurisdictionCode(hint)
    except InvalidCode:
        return None
