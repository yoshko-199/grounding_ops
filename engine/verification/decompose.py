"""Stage 2 — decomposition into span-anchored atomic elements.

Spec §9.7.1 as extended in v0.4:

    Every element MUST cite a span of the claim text it was decomposed from
    [...] No element may introduce an entity, quantity, unit, or time period
    absent from the claim text.

The construction here is what makes AC-18 hold rather than merely pass.
Every element's span comes from a match position on the claim text, and its
fragment is that span resolved.  There is no code path that composes an
element's text and then searches the claim for somewhere to attach it — the
span exists before the fragment does.  AC-18 tests exactly this distinction,
because "a span found by searching for text the system generated proves only
that the system is self-consistent."

Directional and predictive surface forms come from the lexicon's
``surface_vocabulary`` (interface v1.4), not from a hardcoded English list —
see :mod:`engine.verification.patterns` for why that migration happened and
what is still language-general.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.elements import Element, ElementKind
from engine.ids import ClaimId, ElementId
from engine.packs.schema import Lexicon, SurfaceCategory
from engine.spans import Span
from engine.verification import patterns


@dataclass(frozen=True, slots=True)
class _Candidate:
    start: int
    end: int
    kind: ElementKind


def decompose(claim_text: str, claim_id: ClaimId, lexicon: Lexicon) -> tuple[Element, ...]:
    """Split a claim into atomic, anchored elements.

    Returns elements ordered by span start — the total order §9.9.1 requires
    for reconstruction determinism, established here so that no later stage
    has to impose it.
    """
    candidates: list[_Candidate] = []

    for match in patterns.TIME_PERIOD.finditer(claim_text):
        candidates.append(_Candidate(match.start(), match.end(), ElementKind.TIME_PERIOD))

    for match in patterns.finditer_any(claim_text, lexicon.surface_vocabulary[SurfaceCategory.RISE]):
        candidates.append(_Candidate(match.start(), match.end(), ElementKind.DIRECTION))
    for match in patterns.finditer_any(claim_text, lexicon.surface_vocabulary[SurfaceCategory.FALL]):
        candidates.append(_Candidate(match.start(), match.end(), ElementKind.DIRECTION))

    for match in patterns.NUMBER.finditer(claim_text):
        candidates.append(_Candidate(match.start(), match.end(), ElementKind.QUANTITY))

    for match in patterns.finditer_any(
        claim_text, lexicon.surface_vocabulary[SurfaceCategory.PREDICTION]
    ):
        candidates.append(_Candidate(match.start(), match.end(), ElementKind.PREDICTION))

    # Out-of-scope fragments are elements too. They are decomposed, marked,
    # and carried into the discard ledger rather than dropped — §7.1 makes
    # the ledger inseparable from the reconstruction, and a fragment silently
    # discarded at Stage 2 would never reach it.
    candidates.extend(
        _lexicon_matches(claim_text, lexicon, "causal", ElementKind.CAUSAL)
    )
    candidates.extend(
        _lexicon_matches(claim_text, lexicon, "evaluative", ElementKind.OPINION)
    )
    candidates.extend(
        _lexicon_matches(claim_text, lexicon, "superlative", ElementKind.SUPERLATIVE)
    )

    elements: list[Element] = []
    for candidate in _resolve_overlaps(candidates):
        span = Span(candidate.start, candidate.end)
        fragment = span.resolve(claim_text)
        if not fragment.strip():
            continue
        elements.append(
            Element(
                id=ElementId(),
                claim_id=claim_id,
                fragment=fragment,
                span=span,
                kind=candidate.kind,
            )
        )
    return tuple(elements)


def _lexicon_matches(
    claim_text: str, lexicon: Lexicon, operation_prefix: str, kind: ElementKind
) -> list[_Candidate]:
    """Find pack-declared trigger phrases, as literal spans of the claim."""
    out: list[_Candidate] = []
    for operation, phrases in lexicon.derivation_triggers.items():
        if not operation.value.startswith(operation_prefix):
            continue
        for phrase in phrases:
            for match in re.finditer(re.escape(phrase), claim_text, re.I):
                out.append(_Candidate(match.start(), match.end(), kind))
    return out


def _resolve_overlaps(candidates: list[_Candidate]) -> list[_Candidate]:
    """Keep the longest match where spans overlap; order by position.

    Overlap is common and mostly benign — "in 2021" matches both the time
    pattern and the numeral pattern. Preferring the longer span keeps the
    more specific reading, so "in 2021" stays a time period rather than
    decomposing into a bare quantity that means nothing on its own.
    """
    ordered = sorted(candidates, key=lambda c: (c.start, -(c.end - c.start)))
    kept: list[_Candidate] = []
    for candidate in ordered:
        if any(candidate.start < k.end and k.start < candidate.end for k in kept):
            continue
        kept.append(candidate)
    return sorted(kept, key=lambda c: c.start)


def verify_anchoring(elements: tuple[Element, ...], claim_text: str) -> list[str]:
    """Re-check the anchoring invariant. AC-18's test, callable in-process.

    Cheap, and worth running at the stage boundary rather than only in tests:
    an element whose fragment has drifted from its span is the exact
    signature of a retrofitted anchor.
    """
    failures: list[str] = []
    for element in elements:
        try:
            resolved = element.span.resolve(claim_text)
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            failures.append(f"element {element.id}: span does not resolve ({exc})")
            continue
        if resolved != element.fragment:
            failures.append(
                f"element {element.id}: fragment {element.fragment!r} does not match "
                f"the text at its span ({resolved!r}). An element whose text was "
                "generated and then anchored is invention, not decomposition"
            )
    return failures
