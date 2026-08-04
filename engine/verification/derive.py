"""Stage 9 — derived elements, by extraction rather than invention.

Spec §9.7.  "Derived elements are extracted from the claim's own text, never
inferred from world knowledge. Generation is a closed set of transformations
applied to spans of the original."

§9.7 also states the stakes, and they are the highest in the spec after §9.6:
"A generator free to invent 'implications' can attribute to a claimant a
belief they never expressed, and then present that attribution inside an
artifact carrying custodian names, citation records, and a verification
stamp."

Three properties make that impossible here rather than merely discouraged:

1. Every derived element's text is assembled from **verbatim spans of the
   claim** plus a fixed scaffold phrase per operation. No content word can
   enter that the claim did not already contain.
2. The operation list is closed and versioned (:class:`DerivationOperation`).
3. Nothing produced here can carry a status, a retrieval, or a tolerance
   band, because :class:`DerivedElement` has no such fields.

**On fluency.**  The propositions read stiffly — "prices rose is asserted to
be caused by governmental incompetence" rather than something smoother.  That
is deliberate and worth defending.  AC-16's note observes that the dangerous
output is "fluent, plausible, and looks derived"; smoothing these into
natural prose would require supplying words the claim does not contain, which
is exactly the line §9.7.3 draws.  Stiffness is the visible cost of not
crossing it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.elements import (
    DerivationOperation,
    DerivedElement,
    Element,
    ElementStatus,
    GateState,
    RelationshipTag,
)
from engine.ids import ClaimId, DerivedElementId
from engine.packs.schema import Lexicon
from engine.spans import Span
from engine.verification import patterns

# The scaffold each operation contributes. Closed, versioned with the spec,
# and deliberately drab. These are the only words a derived element may
# contain that the claim does not.
SCAFFOLD: dict[DerivationOperation, str] = {
    DerivationOperation.CAUSAL_DISCHARGE: "is asserted to be caused by",
    DerivationOperation.SUPERLATIVE_DISCHARGE: "is asserted to be",
    DerivationOperation.COMPARATIVE_DISCHARGE: "is asserted to be",
    DerivationOperation.EVALUATIVE_DISCHARGE: "is characterised as",
    DerivationOperation.SCOPE_DISCHARGE: "is asserted to hold for",
}

_SCAFFOLD_TOKENS = frozenset(
    token
    for phrase in SCAFFOLD.values()
    for token in patterns.tokens(phrase)
)

IMPLICATION_PREFIX = "This claim invites the conclusion that"


class InadmissibleDerivation(Exception):
    """Raised when a candidate fails §9.7's admissibility rules."""


@dataclass(frozen=True, slots=True)
class _Trigger:
    start: int
    end: int
    operation: DerivationOperation
    phrase: str


def derive(
    claim_text: str,
    claim_id: ClaimId,
    lexicon: Lexicon,
    elements: tuple[Element, ...] = (),
) -> tuple[DerivedElement, ...]:
    """Extract derived elements from a claim's own text.

    Returns them ``proposed`` (§9.7.6).  They are "the only output in the
    system with this property, which is precisely why they are gated": unlike
    a retrieval or an element status, a derived element is model-produced text
    rather than a mechanical function of retrievals.
    """
    triggers = _triggers(claim_text, lexicon)
    if not triggers:
        return ()

    derived: list[DerivedElement] = []
    for index, trigger in enumerate(triggers):
        previous_end = triggers[index - 1].end if index else 0
        left = claim_text[previous_end : trigger.start].strip(" ,;.")
        right = claim_text[trigger.end :].strip(" ,;.")

        text = _proposition(trigger, left, right)
        if not text:
            continue

        span = Span(trigger.start, trigger.end)
        _reject_new_entities(text, claim_text)

        derived.append(
            DerivedElement(
                id=DerivedElementId(),
                from_claim_id=claim_id,
                text=text,
                span=span,
                operation=trigger.operation,
                tag=_tag(trigger, elements),
                state=GateState.PROPOSED,
            )
        )
    return tuple(derived)


def _triggers(claim_text: str, lexicon: Lexicon) -> list[_Trigger]:
    """Find pack-declared trigger phrases as literal spans.

    Longest match wins where phrases overlap, so "because of" is not
    decomposed into a shorter trigger that would discharge differently.
    """
    found: list[_Trigger] = []
    for operation, phrases in lexicon.derivation_triggers.items():
        for phrase in phrases:
            for match in re.finditer(rf"\b{re.escape(phrase)}\b", claim_text, re.I):
                found.append(_Trigger(match.start(), match.end(), operation, phrase))

    found.sort(key=lambda t: (t.start, -(t.end - t.start)))
    kept: list[_Trigger] = []
    for trigger in found:
        if any(trigger.start < k.end and k.start < trigger.end for k in kept):
            continue
        kept.append(trigger)
    return sorted(kept, key=lambda t: t.start)


def _proposition(trigger: _Trigger, left: str, right: str) -> str:
    """Compose the explicit claim the trigger discharges.

    Every content word comes from ``left``, ``right``, or the trigger itself —
    all three verbatim from the claim. The scaffold is the only addition.
    """
    scaffold = SCAFFOLD[trigger.operation]
    surface = trigger.phrase

    if trigger.operation is DerivationOperation.CAUSAL_DISCHARGE:
        if not left or not right:
            return ""
        return f"{left} {scaffold} {right}"

    if trigger.operation is DerivationOperation.EVALUATIVE_DISCHARGE:
        subject = left or right
        if not subject:
            return ""
        return f"{subject} {scaffold} {surface}"

    if trigger.operation is DerivationOperation.SCOPE_DISCHARGE:
        if not right:
            return ""
        return f"{surface} {scaffold} {right}"

    # Superlative and comparative discharge.
    if not left:
        return ""
    tail = f" {right}" if right else ""
    return f"{left} {scaffold} {surface}{tail}"


def _reject_new_entities(text: str, claim_text: str) -> None:
    """§9.7.3 — the no-world-knowledge rule, checked rather than trusted.

    "A derived element may not introduce an entity, quantity, time period, or
    relation that does not appear in the original claim."

    The construction above already guarantees this, so the check is defence in
    depth. It stays because AC-16 tests it and because the guarantee lives in
    a template that a later edit could quietly widen — the check would then
    fail loudly instead of the system inventing quietly.
    """
    claim_tokens = {patterns.stem(t) for t in patterns.tokens(claim_text)}
    for token in patterns.tokens(text):
        if token in _SCAFFOLD_TOKENS or token in patterns.STOPWORDS:
            continue
        if patterns.stem(token) not in claim_tokens:
            raise InadmissibleDerivation(
                f"derived text introduces {token!r}, which appears nowhere in the "
                "claim. That is world knowledge, not extraction (§9.7.3)"
            )


def _tag(trigger: _Trigger, elements: tuple[Element, ...]) -> RelationshipTag:
    """§6.3 — the derived element's position relative to both versions.

    A discharge anchored on a fragment that did not survive "followed from the
    original, it depends on elements that did not survive, and it dies with
    them". §6.3 calls this "the most analytically valuable output of the whole
    system", and §9.6 shows why: it records that readers took away "the
    government caused this" from a claim whose only verified content was
    "inflation rose".
    """
    overlapping = [
        element
        for element in elements
        if element.span.start < trigger.end and trigger.start < element.span.end
    ]
    if any(element.status is not ElementStatus.VERIFIED for element in overlapping):
        return RelationshipTag.IMPLIED_BY_ORIGINAL_ONLY
    if overlapping:
        return RelationshipTag.IMPLIED_BY_RECONSTRUCTED
    return RelationshipTag.INDEPENDENT


def render_as_implication(derived: DerivedElement) -> str:
    """§9.7.5 — rendered as implication, never as attributed quotation.

    "The claimant wrote 'due to incompetence'; they did not necessarily assert
    the specific causal proposition the discharge produces. Presenting a
    discharged implication as a quotation would put words in a named person's
    mouth inside an authoritative-looking artifact — a serious harm, and an
    easy one to cause by accident through careless phrasing."
    """
    return f"{IMPLICATION_PREFIX} {derived.text}."
