"""AC-16 — Derived-element anchoring and closure.

Constraint: spec §9.7.  Derived elements are extracted from the claim's text,
never inferred from world knowledge.

The structural half lands with the type.  Spec §8 is explicit that the
absence of a status column *is* the guarantee — "expressed in the schema
rather than in a rule someone has to remember" — so the test introspects the
class rather than exercising a code path.  The extraction tests (anchoring,
closed operations, no new entities, framing, gate) arrive with Stage 9.
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.elements import (
    DerivationOperation,
    DerivedElement,
    Element,
    RelationshipTag,
)

# Everything a derived element must never be able to carry.  A derived
# element able to hold any of these is a mechanism for laundering an invented
# implication into a checked fact (§9.7.4).
FORBIDDEN_FIELDS = frozenset(
    {
        "status",
        "tolerance_band",
        "continuity_status",
        "retrieval_id",
        "retrieval",
        "measure_id",
        "figure",
        "custodian_id",
    }
)


def _field_names(cls: type) -> frozenset[str]:
    return frozenset(f.name for f in dataclasses.fields(cls))


def test_derived_element_cannot_carry_verification() -> None:
    """§9.7.4 — a derived element receives a tag and nothing else."""
    overlap = _field_names(DerivedElement) & FORBIDDEN_FIELDS
    assert not overlap, (
        f"DerivedElement carries {sorted(overlap)}. A derived element that could "
        "hold a status or a retrieval defeats §9.6 by a different route: it "
        "would let an invented implication be laundered into a checked fact."
    )


def test_derived_element_has_no_retrieval_foreign_key() -> None:
    """AC-16: "assert derived_elements has no foreign key by which a retrieval could attach"."""
    hints = {f.name: str(f.type) for f in dataclasses.fields(DerivedElement)}
    for name, hint in hints.items():
        assert "RetrievalId" not in hint, (
            f"DerivedElement.{name} is typed to hold a retrieval id."
        )


def test_derived_element_is_anchored_and_required_to_be() -> None:
    """A derived element with no span is unconstructable, not merely invalid."""
    span_field = next(f for f in dataclasses.fields(DerivedElement) if f.name == "span")
    assert span_field.default is dataclasses.MISSING
    assert span_field.default_factory is dataclasses.MISSING  # type: ignore[misc]


def test_derivation_operations_are_the_closed_versioned_list() -> None:
    """§9.7.2 — a closed list, not operator-configurable.

    An operator who can add derivation operations can manufacture
    implications, which is the whole risk restated.
    """
    assert {op.value for op in DerivationOperation} == {
        "causal-discharge",
        "superlative-discharge",
        "comparative-discharge",
        "evaluative-discharge",
        "scope-discharge",
    }


def test_derivation_operations_cannot_be_extended_at_runtime() -> None:
    """AC-3 applies to the operation list identically.

    Note what the real guarantee is.  Python permits setting a new *attribute*
    on an enum class, so an assertion that assignment raises would be testing
    the wrong thing and passing for the wrong reason.  What cannot happen is
    the thing that matters: a value that was not declared at class definition
    can never become a member, so it can never be looked up, never round-trip
    through persistence, and never reach a code path that dispatches on the
    operation.
    """
    before = list(DerivationOperation)

    with pytest.raises(ValueError):
        DerivationOperation("invented-discharge")

    assert list(DerivationOperation) == before

    # Declared members are themselves immutable.
    with pytest.raises(AttributeError):
        DerivationOperation.CAUSAL_DISCHARGE = "something-else"  # type: ignore[misc]


def test_relationship_tags_match_the_spec() -> None:
    assert {t.value for t in RelationshipTag} == {
        "implied-by-original-only",
        "implied-by-reconstructed",
        "contradicted-by-reconstructed",
        "independent",
    }


def test_element_and_derived_element_are_distinct_types() -> None:
    """§9.7.4 — the separation is expressed as two types, not one type with a flag.

    A flag would put the guarantee back into the category of rules someone
    has to remember to check.
    """
    assert not issubclass(DerivedElement, Element)
    assert not issubclass(Element, DerivedElement)


# ---------------------------------------------------------------------------
# Extraction (Stage 9). The structural tests above constrain the type; these
# constrain what the extractor is allowed to produce.
# ---------------------------------------------------------------------------

from engine.codes import LanguageCode  # noqa: E402
from engine.ids import ClaimId  # noqa: E402
from engine.packs.schema import Lexicon  # noqa: E402
from engine.verification.derive import (  # noqa: E402
    IMPLICATION_PREFIX,
    InadmissibleDerivation,
    SCAFFOLD,
    derive,
    render_as_implication,
)
from engine.elements import GateState  # noqa: E402

CLAIM = "prices rose due to governmental incompetence"

LEXICON = Lexicon(
    language=LanguageCode("en"),
    derivation_triggers={
        DerivationOperation.CAUSAL_DISCHARGE: ("due to", "because of"),
        DerivationOperation.SUPERLATIVE_DISCHARGE: ("highest", "lowest"),
        DerivationOperation.COMPARATIVE_DISCHARGE: ("more than",),
        DerivationOperation.EVALUATIVE_DISCHARGE: ("incompetence", "failure"),
        DerivationOperation.SCOPE_DISCHARGE: ("every", "all"),
    },
    composition_connectives=("and", ", "),
    forbidden_connectives=("because", "due to"),
    element_slot_order=("time_period", "entity", "measure", "direction", "quantity"),
)


def test_every_derived_element_is_anchored_to_a_resolving_span() -> None:
    """AC-16: the substring must occur verbatim in the claim at that position."""
    derived = derive(CLAIM, ClaimId(), LEXICON)
    assert derived
    for element in derived:
        assert element.span.resolve(CLAIM) == CLAIM[element.span.start : element.span.end]
        assert element.span.resolve(CLAIM).strip()


def test_the_worked_example_from_the_spec_is_produced() -> None:
    """§9.7.3's admissible row: every entity traces to the original."""
    derived = derive(CLAIM, ClaimId(), LEXICON)
    causal = [d for d in derived if d.operation is DerivationOperation.CAUSAL_DISCHARGE]
    assert causal
    text = causal[0].text.lower()
    assert "prices rose" in text
    assert "governmental incompetence" in text


def test_no_derived_element_introduces_an_absent_entity() -> None:
    """§9.7.3's inadmissible rows — "fiscal policy", a counterfactual.

    AC-16's note: the invented output "is the more dangerous output precisely
    because it is fluent, plausible, and looks derived."
    """
    claim_tokens = {t for t in CLAIM.lower().split()}
    scaffold_words = {w for phrase in SCAFFOLD.values() for w in phrase.split()}
    for element in derive(CLAIM, ClaimId(), LEXICON):
        for word in element.text.lower().split():
            assert word in claim_tokens or word in scaffold_words, (
                f"derived text introduced {word!r}, absent from the claim"
            )
        assert "fiscal" not in element.text.lower()
        assert "would have been" not in element.text.lower()


def test_the_no_new_entities_check_actually_fires() -> None:
    """Negative test of the guard, not of the templates that satisfy it."""
    from engine.verification.derive import _reject_new_entities

    _reject_new_entities("prices rose is asserted to be caused by governmental", CLAIM)

    # §9.7.3's second inadmissible row. Note "governmental" rather than
    # "government": the stemmer is deliberately crude and does not unify them,
    # which errs toward rejecting more than it must. That is the safe
    # direction here — a stemmer that collapsed distinct words would let
    # invented content through, and §3 makes measure identity the unit of
    # correctness precisely because near-misses are not misses.
    with pytest.raises(InadmissibleDerivation, match="fiscal"):
        _reject_new_entities("the governmental fiscal policy was expansionary", CLAIM)

    # §9.7.3's third: a counterfactual the text does not contain.
    with pytest.raises(InadmissibleDerivation):
        _reject_new_entities("prices would have been lower under a different cabinet", CLAIM)


def test_every_operation_is_from_the_closed_list() -> None:
    for element in derive(CLAIM, ClaimId(), LEXICON):
        assert element.operation in set(DerivationOperation)


def test_derived_elements_are_emitted_proposed() -> None:
    """§9.7.6 — gated on the same footing as the claim-level verdict."""
    for element in derive(CLAIM, ClaimId(), LEXICON):
        assert element.state is GateState.PROPOSED
        assert element.confirmed_by is None
        assert element.confirmed_at is None


def test_derived_elements_render_as_implication_never_as_quotation() -> None:
    """§9.7.5 — never "what the claimant asserted"."""
    for element in derive(CLAIM, ClaimId(), LEXICON):
        rendered = render_as_implication(element)
        assert rendered.startswith(IMPLICATION_PREFIX)
        for attribution in ("said", "stated", "claimed", "wrote", "according to"):
            assert attribution not in rendered.lower()
        assert '"' not in rendered


def test_a_causal_discharge_carries_the_implied_by_original_only_tag() -> None:
    """§9.6 — the causal claim "is not discarded silently".

    It "routes to §6.3 as a derived element tagged implied-by-original-only —
    it followed from the original, it depends on elements that did not
    survive, and it dies with them."
    """
    from engine.elements import Element, ElementKind, ElementStatus
    from engine.ids import ElementId
    from engine.spans import Span as _Span

    start = CLAIM.index("due to")
    causal_element = Element(
        id=ElementId(),
        claim_id=ClaimId(),
        fragment="due to",
        span=_Span(start, start + 6),
        kind=ElementKind.CAUSAL,
        status=ElementStatus.OUT_OF_SCOPE,
    )
    derived = derive(CLAIM, ClaimId(), LEXICON, elements=(causal_element,))
    causal = [d for d in derived if d.operation is DerivationOperation.CAUSAL_DISCHARGE]
    assert causal
    assert causal[0].tag is RelationshipTag.IMPLIED_BY_ORIGINAL_ONLY


def test_a_claim_with_no_trigger_yields_nothing() -> None:
    """Under-reporting is the correct direction to fail (§10, question 3)."""
    assert derive("prices rose in 2021", ClaimId(), LEXICON) == ()


def test_derived_elements_never_enter_a_reconstruction() -> None:
    """"Assert no derived element appears in any reconstruction at any revision."."""
    from engine.elements import VerifiedElement

    for element in derive(CLAIM, ClaimId(), LEXICON):
        with pytest.raises((ValueError, AttributeError, TypeError)):
            VerifiedElement(element, "ZZ Price Index")  # type: ignore[arg-type]
