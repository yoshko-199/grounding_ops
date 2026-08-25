"""AC-18 — Element anchoring.

Constraint: spec §9.7.1 as extended in v0.4.  Stage 2 elements are decomposed
from the claim's text, never invented.

This criterion closes the door AC-16 left open on the other side of the wall.
A fabricated *derived* element is inert — §9.7.4 denies it a status, a
retrieval, and a place in any reconstruction.  A fabricated *ordinary*
element is live: it binds a real measure, retrieves a real published figure,
reaches Verified, and enters the reconstruction carrying a custodian name and
a reference period, with nothing malfunctioning anywhere.

The structural half lands with the type.  The decomposition tests arrive with
Stage 2.
"""

from __future__ import annotations

import dataclasses

import pytest

from engine.elements import Element, ElementKind, ElementStatus
from engine.ids import ClaimId, ElementId
from engine.spans import Span, UnresolvableSpan

CLAIM = "inflation is up due to governmental incompetence over the last three years"


def test_element_span_is_required() -> None:
    """An unanchored element is unconstructable.

    AC-18 requires the check to run "before Stage 3, not at render". A type
    that cannot hold the invalid state runs it at construction, which is
    earlier than any stage.
    """
    span_field = next(f for f in dataclasses.fields(Element) if f.name == "span")
    assert span_field.default is dataclasses.MISSING
    assert span_field.default_factory is dataclasses.MISSING  # type: ignore[misc]

    with pytest.raises(TypeError):
        Element(  # type: ignore[call-arg]
            id=ElementId(),
            claim_id=ClaimId(),
            fragment="inflation is up",
            kind=ElementKind.DIRECTION,
        )


def test_span_resolves_positionally_not_by_search() -> None:
    """AC-18: the substring must occur "at that position".

    A span that merely finds its text somewhere else in the claim has not
    been verified, it has been searched for — and searching is exactly what a
    retrofitted span does.
    """
    start = CLAIM.index("inflation is up")
    span = Span(start, start + len("inflation is up"))
    assert span.resolve(CLAIM) == "inflation is up"

    # The same text, claimed at the wrong offset, must not resolve to itself.
    wrong = Span(start + 10, start + 10 + len("inflation is up"))
    assert wrong.resolve(CLAIM) != "inflation is up"


def test_span_past_end_of_claim_is_unresolvable() -> None:
    span = Span(0, len(CLAIM) + 5)
    with pytest.raises(UnresolvableSpan):
        span.resolve(CLAIM)


def test_empty_and_inverted_spans_are_rejected() -> None:
    with pytest.raises(UnresolvableSpan):
        Span(5, 5)
    with pytest.raises(UnresolvableSpan):
        Span(9, 4)
    with pytest.raises(UnresolvableSpan):
        Span(-1, 4)


def test_element_fragment_matches_its_span() -> None:
    """The stored fragment and the span must agree.

    Storing both is redundant by design: the redundancy is what makes a
    retrofitted span detectable, because a fragment the system generated will
    not match the text at the offset it claims.
    """
    start = CLAIM.index("over the last three years")
    element = Element(
        id=ElementId(),
        claim_id=ClaimId(),
        fragment="over the last three years",
        span=Span(start, start + len("over the last three years")),
        kind=ElementKind.QUANTITY,
    )
    assert element.span.resolve(CLAIM) == element.fragment


def test_out_of_scope_kinds_are_identified() -> None:
    """AC-15 scope closure depends on these never reaching Verified."""
    for kind in (ElementKind.OPINION, ElementKind.PREDICTION, ElementKind.CAUSAL):
        element = Element(
            id=ElementId(),
            claim_id=ClaimId(),
            fragment="due to",
            span=Span(0, 6),
            kind=kind,
        )
        assert element.is_out_of_scope

    quantitative = Element(
        id=ElementId(),
        claim_id=ClaimId(),
        fragment="inflation is up",
        span=Span(0, 15),
        kind=ElementKind.DIRECTION,
    )
    assert not quantitative.is_out_of_scope


def test_element_statuses_match_the_spec_taxonomy() -> None:
    """§6.1 — six statuses, and Unreachable distinct from Unverified.

    AC-14 requires the two never collapse into one another: a custodian that
    could not be reached this session is operationally different from one
    that was reached and had nothing covering the element.
    """
    assert {s.value for s in ElementStatus} == {
        "verified",
        "contradicted",
        "unverified",
        "unreachable",
        "contested_by_definition",
        "out_of_scope",
    }
    assert ElementStatus.UNREACHABLE is not ElementStatus.UNVERIFIED
