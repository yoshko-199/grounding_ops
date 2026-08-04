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
