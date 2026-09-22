"""Interface v1.4 — rise/fall/prediction vocabulary comes from the pack.

Before this, ``engine.verification.patterns.RISE``/``FALL``/``PREDICTION``
were hardcoded English regexes reached from four call sites regardless of
what any pack declared. A lexicon-based test that only exercises the fixture
pack's English vocabulary cannot tell the difference between "reads the pack"
and "reads the pack, which happens to say the same words `patterns.py` used
to hardcode" — the two would pass identically. Every test here builds a
lexicon with *different* words than the old hardcoded lists, so a call site
that quietly still consulted ``patterns.RISE`` would fail loudly.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.codes import LanguageCode
from engine.custodians.base import Observation, RevisionStatus
from engine.elements import (
    ContinuityStatus,
    DerivationOperation,
    Element,
    ElementId,
    ElementKind,
    ElementStatus,
)
from engine.ids import ClaimId
from engine.packs.schema import Lexicon, Measure, SurfaceCategory
from engine.spans import Span
from engine.verification import decompose, element_verdict, scope_gate
from engine.verification.retrieve import PullOutcome
from engine.verification.continuity import ContinuityOutcome


def _lexicon(vocabulary: dict[SurfaceCategory, tuple[str, ...]] | None = None) -> Lexicon:
    """A minimal lexicon, with a made-up surface vocabulary that shares no
    words with the old hardcoded English lists."""
    surface = {
        SurfaceCategory.RISE: (),
        SurfaceCategory.FALL: (),
        SurfaceCategory.PREDICTION: (),
    }
    surface.update(vocabulary or {})
    return Lexicon(
        language=LanguageCode("en"),
        derivation_triggers={op: () for op in DerivationOperation},
        composition_connectives=("and",),
        forbidden_connectives=("because",),
        element_slot_order=("time_period", "entity", "measure", "direction", "quantity"),
        surface_vocabulary=surface,
    )


INVENTED_RISE = ("zoomed",)
INVENTED_FALL = ("cratered",)
INVENTED_PREDICTION = ("prophesied",)


# -- decompose ---------------------------------------------------------------


def test_decompose_finds_direction_from_an_invented_rise_word() -> None:
    lexicon = _lexicon({SurfaceCategory.RISE: INVENTED_RISE})
    claim = "output zoomed last year"
    elements = decompose.decompose(claim, ClaimId(), lexicon)
    assert any(
        e.kind is ElementKind.DIRECTION and e.fragment == "zoomed" for e in elements
    )


def test_decompose_ignores_the_old_hardcoded_english_word_when_not_declared() -> None:
    """The word that used to be hardcoded is now just prose unless the pack
    says otherwise."""
    lexicon = _lexicon()  # declares no rise/fall vocabulary at all
    claim = "output rose last year"
    elements = decompose.decompose(claim, ClaimId(), lexicon)
    assert not any(e.kind is ElementKind.DIRECTION for e in elements)


def test_decompose_finds_a_prediction_from_an_invented_word() -> None:
    lexicon = _lexicon({SurfaceCategory.PREDICTION: INVENTED_PREDICTION})
    claim = "output prophesied to rise"
    elements = decompose.decompose(claim, ClaimId(), lexicon)
    assert any(e.kind is ElementKind.PREDICTION for e in elements)


# -- scope_gate ---------------------------------------------------------------


def test_scope_gate_treats_an_invented_rise_word_as_quantitative() -> None:
    lexicon = _lexicon({SurfaceCategory.RISE: INVENTED_RISE})
    outcome = scope_gate.classify("output zoomed", lexicon)
    assert outcome.in_scope


def test_scope_gate_does_not_recognise_the_old_hardcoded_word_unless_declared() -> None:
    lexicon = _lexicon()
    outcome = scope_gate.classify("output rose", lexicon)
    assert not outcome.in_scope, (
        "'rose' triggered the scope gate's direction check without being "
        "declared in the lexicon -- a hardcoded fallback survived the migration"
    )


def test_scope_gate_routes_out_an_invented_prediction_word_with_no_past_anchor() -> None:
    lexicon = _lexicon({SurfaceCategory.PREDICTION: INVENTED_PREDICTION})
    outcome = scope_gate.classify("output is prophesied to rise", lexicon)
    assert not outcome.in_scope
    assert outcome.reason is scope_gate.OutOfScopeReason.PREDICTION


def test_scope_gate_past_anchor_recognises_invented_direction_words() -> None:
    """A prediction alongside a checkable past claim proceeds -- §9.10's
    'prices rose last year and will rise again' case, restated with invented
    vocabulary so the anchor check is proven pack-driven too."""
    lexicon = _lexicon({
        SurfaceCategory.RISE: INVENTED_RISE,
        SurfaceCategory.PREDICTION: INVENTED_PREDICTION,
    })
    outcome = scope_gate.classify("output zoomed in 2021 and is prophesied to zoom again", lexicon)
    assert outcome.in_scope


# -- element_verdict -----------------------------------------------------------


def _pull(value_first: str, value_last: str) -> PullOutcome:
    observations = (
        Observation("X", "2020", Decimal(value_first), RevisionStatus.FINAL, date(2020, 1, 1)),
        Observation("X", "2021", Decimal(value_last), RevisionStatus.FINAL, date(2021, 1, 1)),
    )
    return PullOutcome(
        observations=observations,
        retrievals=(),
        continuity=ContinuityOutcome(ContinuityStatus.NOT_APPLICABLE),
    )


def test_direction_element_verdict_uses_the_declared_rise_word() -> None:
    lexicon = _lexicon({SurfaceCategory.RISE: INVENTED_RISE, SurfaceCategory.FALL: INVENTED_FALL})
    element = Element(
        id=ElementId(), claim_id=ClaimId(), fragment="zoomed",
        span=Span(0, 6), kind=ElementKind.DIRECTION,
    )
    measure = Measure(
        id="m", name="M", definition="d", custodian_id="c", series_identifier="X",
        unit="u", published_precision=0.1, discrete=False, known_confusions=(),
        admissible_baselines=(), admissible_windows=(), admissible_source_ref="ref",
    )
    pull = _pull("100", "110")  # a genuine rise
    outcome = element_verdict.assign(element, measure, pull, "output zoomed", lexicon)
    assert outcome.element.status is ElementStatus.VERIFIED, (
        "the invented rise word was not recognised as claiming a rise"
    )


def test_direction_element_verdict_ignores_the_hardcoded_word_when_undeclared() -> None:
    """'rose' with no declared rise/fall vocabulary falls back to "not a
    rise", so a series that fell is (wrongly, if the fallback were live)
    reported as verified -- this asserts the fallback is gone, by checking
    the claim is judged as asserting a FALL (the default) rather than a rise."""
    lexicon = _lexicon()
    element = Element(
        id=ElementId(), claim_id=ClaimId(), fragment="rose",
        span=Span(0, 4), kind=ElementKind.DIRECTION,
    )
    measure = Measure(
        id="m", name="M", definition="d", custodian_id="c", series_identifier="X",
        unit="u", published_precision=0.1, discrete=False, known_confusions=(),
        admissible_baselines=(), admissible_windows=(), admissible_source_ref="ref",
    )
    pull = _pull("100", "110")  # a genuine rise
    outcome = element_verdict.assign(element, measure, pull, "output rose", lexicon)
    assert outcome.element.status is ElementStatus.CONTRADICTED, (
        "'rose' was still read as claiming a rise with no declared vocabulary -- "
        "a hardcoded fallback survived the migration"
    )
