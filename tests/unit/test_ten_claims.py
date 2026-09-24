"""Ten claims supplied by the user as a test set, and what they found.

They were pasted into the session for the loop's last milestone: general
English claims about physics, food, biology, history, epidemiology, vaccines,
arithmetic, materials and US policy, not harvested from any source. No
admitted pack covers any of them, so every one is Insufficient Data. That is
the designed answer whether a claim is true or false, and these tests do not
record which is which.

Running them found three defects the suite had not:

* "Covid-19" decomposed its "19" as a quantity, a figure the claim never
  asserted.
* Superlative triggers matched inside other words, so "ever" fired on
  "every", "never" and "however".
* A claim that never reached decomposition said "Nothing was discarded"
  beside "does not reconstruct", which reads as a whole claim dropped by a
  ledger claiming otherwise.

Each fix has a test here. See docs/validation-ten-claims.md for the full
results, including two gaps recorded rather than patched.
"""

from __future__ import annotations

import pathlib
from datetime import date

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.elements import ElementKind
from engine.ids import ClaimId
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore
from engine.verdicts import Verdict
from engine.verification import decompose

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "packs" / "fixture"
LIVE = ROOT / "packs" / "live"

CLAIMS = (
    "Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at sea level.",
    "Pizza is the most delicious food in the world.",
    "Humans are classified as mammals.",
    "King John of England signed the Magna Carta in 1225",
    "Covid-19 epidemic originated from a Chinese research lab",
    "Vaccines cause Autism in children",
    "If you put two sheep in a field, and then another two, you’ve got four sheep "
    "in that field for ever.",
    "the density of steel is 7700 kg per cubic metre.",
    "The U.S. has a highly progressive tax-and-transfer system that redistributes "
    "massive sums of money.",
    "In the U.S gun violence is alien to most people's experiences and the nation's "
    "murder rate has been cut by more than half since 1991",
)


def _run(claim: str, packs: pathlib.Path, jurisdiction: str | None):
    context = ClaimContext(
        jurisdiction=JurisdictionCode(jurisdiction) if jurisdiction else None,
        language=LanguageCode("en"),
        stated_at=date(2026, 9, 24),
    )
    store = RetrievalStore(":memory:")
    try:
        return verify(claim, context, PackRegistry.from_directory(packs),
                      build_fixture_custodians(), store)
    finally:
        store.close()


def _fixture_lexicon():
    return PackRegistry.from_directory(FIXTURE).get(JurisdictionCode("ZZ")).lexicon(
        LanguageCode("en")
    )


@pytest.mark.parametrize("claim", CLAIMS)
@pytest.mark.parametrize("packs,jurisdiction", [(LIVE, None), (FIXTURE, "ZZ")])
def test_every_claim_is_an_answer_and_renders(claim, packs, jurisdiction) -> None:
    """No admitted pack covers these subjects, so each is Insufficient Data,
    rendered in full, in both forms, without raising."""
    run = _run(claim, packs, jurisdiction)
    assert run.artifact.verdict.label is Verdict.INSUFFICIENT_DATA
    assert "INSUFFICIENT DATA" in run.artifact.render()
    assert "INSUFFICIENT DATA" in run.artifact.render_html()


# -- F1: a numeral inside a name is not a quantity -----------------------------


@pytest.mark.parametrize("name", ["Covid-19", "COVID‑19", "the F-35", "a G-7 summit"])
def test_a_digit_joined_to_a_word_is_not_a_quantity(name) -> None:
    elements = decompose.decompose(f"{name} was discussed", ClaimId(), _fixture_lexicon())
    assert not [e for e in elements if e.kind is ElementKind.QUANTITY], name


def test_a_number_standing_alone_still_is() -> None:
    elements = decompose.decompose("prices fell to -5 percent", ClaimId(), _fixture_lexicon())
    assert [e.fragment for e in elements if e.kind is ElementKind.QUANTITY] == ["5 percent"]


def test_the_covid_claim_lists_no_phantom_figure_in_its_ledger() -> None:
    run = _run(CLAIMS[4], FIXTURE, "ZZ")
    assert "19" not in [entry.fragment.strip() for entry in run.artifact.ledger]


# -- F2: an undecomposed claim says so ------------------------------------------


def test_an_undecomposed_claim_says_why_its_ledger_is_empty() -> None:
    run = _run(CLAIMS[0], LIVE, None)
    artifact = run.artifact
    assert not artifact.ledger and not artifact.decomposed
    for output in (artifact.render(), artifact.render_html()):
        assert "Not decomposed" in output
        assert "Nothing was discarded" not in output
    assert artifact.to_dict()["decomposed"] is False


def test_a_decomposed_claim_keeps_nothing_was_discarded() -> None:
    run = _run("prices rose in 2021", FIXTURE, "ZZ")
    assert run.artifact.decomposed
    if not run.artifact.ledger:
        assert "Nothing was discarded." in run.artifact.render()


def test_the_stored_read_back_says_not_decomposed_too(tmp_path, capsys) -> None:
    """The store has no decomposed flag. The read-back infers it from there
    being no element rows, and must not fall back to "Nothing was discarded"."""
    from cli.show import main as show_main
    from cli.verify import main as verify_main

    store = str(tmp_path / "store.db")
    assert verify_main([CLAIMS[0], "--packs", str(LIVE), "--store", store]) == 0
    claim_id = next(
        line.split()[2] for line in capsys.readouterr().out.splitlines()
        if line.startswith("claim id:")
    )
    assert show_main([claim_id, "--store", store]) == 0
    out = capsys.readouterr().out
    assert "Not decomposed" in out and "Nothing was discarded" not in out


# -- F3: superlative triggers are whole words -----------------------------------


@pytest.mark.parametrize("claim", [
    "prices rose every year", "prices never fell", "however prices rose in 2021",
    CLAIMS[6],
])
def test_no_phantom_superlative(claim) -> None:
    elements = decompose.decompose(claim, ClaimId(), _fixture_lexicon())
    assert not [e for e in elements if e.kind is ElementKind.SUPERLATIVE], claim


def test_for_ever_derives_no_superlative() -> None:
    run = _run(CLAIMS[6], FIXTURE, "ZZ")
    assert not [d for d in run.derived if d.operation.value == "superlative-discharge"]


@pytest.mark.parametrize("claim,fragment", [
    ("the highest ever", "highest"), ("the worst of all time", "of all time"),
    ("a record high", "record"),
])
def test_real_superlatives_still_decompose(claim, fragment) -> None:
    elements = decompose.decompose(claim, ClaimId(), _fixture_lexicon())
    assert fragment in [e.fragment for e in elements if e.kind is ElementKind.SUPERLATIVE]


@pytest.mark.parametrize("claim", [
    "the figures were recorded monthly", "honours were bestowed in 2021",
])
def test_a_trigger_inside_another_word_does_not_fire(claim) -> None:
    """The matching rule itself, independent of which words the pack
    declares: "record" inside "recorded" and "best" inside "bestowed" are not
    superlatives. Without this, dropping the bare "ever" from the fixture
    would hide a substring search coming back."""
    elements = decompose.decompose(claim, ClaimId(), _fixture_lexicon())
    assert not [e for e in elements if e.kind is ElementKind.SUPERLATIVE], claim
