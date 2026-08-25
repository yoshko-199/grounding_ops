"""AC-15 — Reconstruction determinism and composition.

Constraint: spec §4 Stage 7, §7.1, §9.6.  Reconstruction is a pure function
of the verified element set, and never composes a claim its elements do not
support.

AC-15's note: "The composition test is the one that matters most and the one
an implementation is most likely to fail by accident."
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from decimal import Decimal

import pytest

from engine.elements import (
    Element,
    ElementKind,
    ElementStatus,
    VerifiedElement,
)
from engine.figures import Figure
from engine.ids import ClaimId, ElementId, RetrievalId
from engine.packs.schema import Lexicon
from engine.spans import Span
from engine.verification.reconstruct import (
    ForbiddenConnective,
    element_set_hash,
    reconstruct,
)

CLAIM = "prices rose over the last three years due to governmental incompetence"
CLAIM_ID = ClaimId()
MEASURE = "ZZ Price Index"


def _element(fragment: str, kind: ElementKind, status=ElementStatus.VERIFIED) -> Element:
    start = CLAIM.index(fragment)
    return Element(
        id=ElementId(f"el-{fragment.replace(' ', '-')}"),
        claim_id=CLAIM_ID,
        fragment=fragment,
        span=Span(start, start + len(fragment)),
        kind=kind,
        status=status,
    )


def _verified(fragment: str, kind: ElementKind, figure: Figure | None = None) -> VerifiedElement:
    return VerifiedElement(_element(fragment, kind), MEASURE, figure)


@pytest.fixture
def element_set() -> frozenset[VerifiedElement]:
    return frozenset(
        {
            _verified("rose", ElementKind.DIRECTION),
            _verified("over the last three years", ElementKind.QUANTITY),
        }
    )


# -- determinism ------------------------------------------------------------


def test_the_same_element_set_yields_byte_identical_text(element_set) -> None:
    first = reconstruct(element_set, LEXICON)
    second = reconstruct(element_set, LEXICON)
    assert first.text == second.text
    assert first.element_set_hash == second.element_set_hash
    assert first.text


def test_equal_hashes_imply_equal_text(element_set) -> None:
    """§8 — "two revisions with the same hash must have identical text"."""
    rebuilt = frozenset(dict.fromkeys(element_set))
    assert element_set_hash(rebuilt) == element_set_hash(element_set)
    assert reconstruct(rebuilt, LEXICON).text == reconstruct(element_set, LEXICON).text


def test_order_of_assembly_does_not_affect_the_result(element_set) -> None:
    """§9.9.1's total order, tested against the ways it could leak.

    Element order must be a function of span position and id alone — never of
    insertion order, retrieval timing, or hash iteration.
    """
    members = list(element_set)
    baseline = reconstruct(frozenset(members), LEXICON).text
    for permutation in ([*reversed(members)], [members[-1], *members[:-1]]):
        assert reconstruct(frozenset(permutation), LEXICON).text == baseline


# -- re-derivation, not editing --------------------------------------------


def test_the_reconstructor_cannot_receive_a_previous_revision() -> None:
    """AC-15: "no code path produces revision n by taking revision n−1 as input".

    True by signature rather than by audit: there is no parameter for it.
    """
    parameters = set(inspect.signature(reconstruct).parameters)
    assert parameters == {"elements", "lexicon"}
    for forbidden in ("previous", "prior", "revision", "text", "draft", "base"):
        assert forbidden not in parameters


def test_every_revision_re_derives_from_its_recorded_element_set(element_set) -> None:
    stored = reconstruct(element_set, LEXICON)
    re_derived = reconstruct(element_set, LEXICON)
    assert re_derived.text == stored.text
    assert re_derived.element_set_hash == stored.element_set_hash


# -- regression -------------------------------------------------------------


def test_a_regressing_element_produces_a_smaller_reconstruction(element_set) -> None:
    """§4: "A shrinking revision is a first-class output, not an error state."

    An element moving Verified to Contradicted leaves the set, and the next
    revision is re-derived from what remains. An append-based reconstructor
    "can grow, but it cannot correctly shrink".
    """
    before = reconstruct(element_set, LEXICON)

    smaller = frozenset(
        v for v in element_set if v.element.kind is not ElementKind.QUANTITY
    )
    after = reconstruct(smaller, LEXICON)

    assert after.does_reconstruct
    assert len(after.text) < len(before.text)
    assert after.element_set_hash != before.element_set_hash


def test_an_emptied_element_set_does_not_reconstruct() -> None:
    result = reconstruct(frozenset(), LEXICON)
    assert not result.does_reconstruct
    assert result.text == ""
    assert result.element_set_hash


def test_surviving_elements_that_do_not_compose_return_does_not_reconstruct() -> None:
    """§4: the element list plus "does not reconstruct", never a smoothed sentence."""
    only_a_period = frozenset({_verified("over the last three years", ElementKind.QUANTITY)})
    result = reconstruct(only_a_period, LEXICON)
    assert not result.does_reconstruct
    assert result.text == ""
    assert result.element_ids, "the surviving elements are still reported"


# -- composition ------------------------------------------------------------


def test_no_causal_connective_is_composed_between_elements(element_set) -> None:
    text = reconstruct(element_set, LEXICON).text.lower()
    for connective in LEXICON.forbidden_connectives:
        assert connective not in text


def test_composing_a_forbidden_connective_raises(element_set) -> None:
    """The guard, negative-tested.

    A scan that never fires is indistinguishable from no scan. This lexicon
    would be rejected by the loader — interface §3.6 forbids exactly it — so
    it is built directly to prove the reconstructor refuses independently.
    """
    poisoned = Lexicon(
        language=LEXICON.language,
        derivation_triggers=LEXICON.derivation_triggers,
        composition_connectives=("because",),
        forbidden_connectives=("because",),
        element_slot_order=LEXICON.element_slot_order,
    )
    # Two measures, so there is a join for the connective to occupy. A single
    # clause has no seam and would pass for the wrong reason.
    two_clauses = frozenset(
        element_set | {VerifiedElement(_element("rose", ElementKind.DIRECTION), "ZZ Output Index")}
    )
    with pytest.raises(ForbiddenConnective, match="because"):
        reconstruct(two_clauses, poisoned)


def test_a_connective_carried_inside_one_element_is_permitted() -> None:
    """§9.9.2: permitted "where it originates inside a single verified element".

    The bar is on the reconstructor supplying a connective, not on a claim
    containing one.
    """
    claim = "spending rose because of the reform and prices rose"
    start = claim.index("rose because of the reform")
    element = Element(
        id=ElementId("carried"),
        claim_id=CLAIM_ID,
        fragment="rose because of the reform",
        span=Span(start, start + len("rose because of the reform")),
        kind=ElementKind.DIRECTION,
        status=ElementStatus.VERIFIED,
    )
    result = reconstruct(frozenset({VerifiedElement(element, MEASURE)}), LEXICON)
    assert "because of" in result.text.lower()


def test_two_measures_join_by_enumeration_only(element_set) -> None:
    """The §9.6 case: a policy date and a series movement never compose causally."""
    other = VerifiedElement(
        _element("rose", ElementKind.DIRECTION), "ZZ Output Index"
    )
    combined = frozenset(element_set | {other})
    text = reconstruct(combined, LEXICON).text.lower()
    for connective in ("because", "due to", "as a result of", "therefore", "which shows"):
        assert connective not in text


# -- scope closure ----------------------------------------------------------


@pytest.mark.parametrize(
    "kind", [ElementKind.OPINION, ElementKind.PREDICTION, ElementKind.CAUSAL]
)
def test_out_of_scope_elements_cannot_reach_the_reconstructor(kind) -> None:
    """"assert that elements marked Out of scope at Stage 1 [...] are
    therefore structurally unreachable by the reconstructor"."""
    element = replace(_element("rose", ElementKind.DIRECTION), kind=kind)
    with pytest.raises(ValueError, match="excludes|out_of_scope|not verified"):
        VerifiedElement(element, MEASURE)


@pytest.mark.parametrize(
    "status",
    [
        ElementStatus.CONTRADICTED,
        ElementStatus.UNVERIFIED,
        ElementStatus.UNREACHABLE,
        ElementStatus.CONTESTED_BY_DEFINITION,
        ElementStatus.OUT_OF_SCOPE,
        None,
    ],
)
def test_only_verified_elements_can_be_wrapped(status) -> None:
    element = replace(_element("rose", ElementKind.DIRECTION), status=status)
    with pytest.raises(ValueError):
        VerifiedElement(element, MEASURE)


# -- figures ----------------------------------------------------------------


def test_a_claims_own_number_never_renders_without_a_retrieval() -> None:
    """§3 — no figure reaches output except from a recorded retrieval."""
    claim_number = VerifiedElement(
        Element(
            id=ElementId("num"),
            claim_id=CLAIM_ID,
            fragment="104.8",
            span=Span(0, 5),
            kind=ElementKind.QUANTITY,
            status=ElementStatus.VERIFIED,
        ),
        MEASURE,
        figure=None,
    )
    result = reconstruct(frozenset({claim_number}), LEXICON)
    assert "104.8" not in result.text


def test_a_sourced_figure_renders(element_set) -> None:
    figure = Figure(
        value=Decimal("102.4"),
        unit="index_points",
        retrieval_id=RetrievalId("r-1"),
        reference_period="2021-12",
    )
    sourced = VerifiedElement(
        _element("rose", ElementKind.DIRECTION), MEASURE, figure=figure
    )
    quantity_element = VerifiedElement(
        Element(
            id=ElementId("q"),
            claim_id=CLAIM_ID,
            fragment="over the last three years",
            span=Span(CLAIM.index("over the last three years"),
                      CLAIM.index("over the last three years") + 25),
            kind=ElementKind.QUANTITY,
            status=ElementStatus.VERIFIED,
        ),
        MEASURE,
        figure=figure,
    )
    result = reconstruct(frozenset({sourced, quantity_element}), LEXICON)
    assert "102.4" in result.text


# -- the lexicon under test -------------------------------------------------

from engine.codes import LanguageCode  # noqa: E402
from engine.elements import DerivationOperation  # noqa: E402

LEXICON = Lexicon(
    language=LanguageCode("en"),
    derivation_triggers={op: () for op in DerivationOperation},
    composition_connectives=("and", ", ", "; ", "then"),
    forbidden_connectives=(
        "because", "because of", "due to", "caused by", "as a result of",
        "therefore", "which shows",
    ),
    element_slot_order=("time_period", "entity", "measure", "direction", "quantity"),
)
