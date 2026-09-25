"""The bottom line: the verdict in plain words, above the full record.

Each demo claim lands on a known level (tests/unit/test_demo_pack.py), so the
bottom line for each is pinned here: what it calls true, false, unsettled,
not checked and not checkable, the closest version the sources support, the
disconfirmation check, and the sources it cites.
"""

from __future__ import annotations

import pathlib
from datetime import date

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.ids import RetrievalId
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.render import bottom_line
from engine.store.events import RetrievalStore
from tests.unit.test_demo_pack import LEVELS

DEMO = pathlib.Path(__file__).resolve().parents[2] / "packs" / "demo"


def _artifact(claim: str):
    context = ClaimContext(
        jurisdiction=JurisdictionCode("XD"), language=LanguageCode("en"),
        stated_at=date(2024, 1, 1),
    )
    store = RetrievalStore(":memory:")
    try:
        return verify(claim, context, PackRegistry.from_directory(DEMO),
                      build_fixture_custodians(), store).artifact
    finally:
        store.close()


def _section(claim: str) -> str:
    rendered = _artifact(claim).render()
    return rendered[rendered.index("BOTTOM LINE"):rendered.index("RECONSTRUCTED")]


def _claim(cid: str) -> str:
    return next(row[1] for row in LEVELS if row[0] == cid)


ORDER = [
    "Verdict", "Checked against", "Closest version the sources support",
    "Tested against other readings", "Sources", "Open to correction",
]


@pytest.mark.parametrize("cid", [row[0] for row in LEVELS])
def test_every_level_opens_with_its_label_and_keeps_the_order(cid: str) -> None:
    artifact = _artifact(_claim(cid))
    section = _section(_claim(cid))
    label = artifact.verdict.label.value.replace("_", " ").upper()
    assert f"  Verdict: {label}." in section
    positions = [section.index(f"  {name}:") for name in ORDER]
    assert positions == sorted(positions), section
    assert "not yet reviewed by a person" in section


def test_a_contradicted_figure_states_the_published_one() -> None:
    section = _section(_claim("1"))
    assert "True: “100” matches the published figure, 99.96" in section
    assert "False: “212” is contradicted. The published figure is 99.96" in section
    assert "xdstd / XD-BOIL" in section


def test_a_rounded_match_says_it_is_not_exact() -> None:
    section = _section(_claim("8v"))
    assert "“7700” is right to within rounding, not exactly" in section
    assert "7810" in section


def test_a_contested_claim_names_every_figure_it_could_mean() -> None:
    section = _section(_claim("8"))
    assert "Cannot be settled: “7700”" in section
    assert "7810" in section and "7950" in section
    assert "The claim does not say which it means." in section
    assert "Closest version the sources support: none." in section


def test_an_unreachable_source_is_not_checked_and_cites_nothing() -> None:
    section = _section(_claim("4"))
    assert "Not checked: “in 1225” — the source could not be reached" in section
    assert "Sources: none." in section
    assert "That says nothing about whether it is true." in section


def test_misleading_names_the_comparison_it_fails_under() -> None:
    section = _section(_claim("10"))
    assert "it reverses under baseline: prior_period" in section
    # The figure is the level at the end of the span, and says so; it was once
    # rendered bare after "cut", where it read as the size of the cut.
    assert "Murder rate cut, standing at 6.1 per_hundred_thousand in 2023." in section


def test_accurate_says_it_survived_every_comparison() -> None:
    section = _section(_claim("10v"))
    assert "holds under all of them" in section
    assert "Closest version the sources support: Since" in section


def test_an_opinion_is_not_checkable_and_not_called_false() -> None:
    section = _section(_claim("2"))
    assert "Not checkable: “Pizza is the most delicious food in the world.”" in section
    assert "not a finding that it is false" in section
    assert "not attempted" in section


def _basis(**overrides) -> bottom_line.Basis:
    base = dict(
        claim_text="prices rose", label="accurate", state="proposed",
        findings=(bottom_line.Finding("rose", "direction", "verified", "A"),),
        reconstruction=None, sources=(), sweep_ran=True, flips=(), sweep_reason="",
    )
    base.update(overrides)
    return bottom_line.Basis(**base)


def test_a_reviewed_verdict_says_so() -> None:
    text = bottom_line.as_text(_basis(state="confirmed"))
    assert "A person has reviewed this verdict" in text
    assert "not yet reviewed" not in text


def test_a_rejected_verdict_publishes_no_label() -> None:
    text = bottom_line.as_text(_basis(state="rejected"))
    assert "Verdict: none published." in text
    assert "ACCURATE" not in text


def test_a_figure_goes_out_only_with_its_retrieval() -> None:
    """A source's figure is emitted on the sourced channel, so the HTML links it."""
    source = bottom_line.Source(
        RetrievalId("r-one"), "zzstat", "ZZ-PRICE", "4.2", "percent", "2021",
        "final", "2026-01-01",
    )
    basis = _basis(
        claim_text="prices were 4.0",
        label="false",
        findings=(bottom_line.Finding("4.0", "quantity", "contradicted", "C"),),
        sources=(source,),
    )
    page = bottom_line.as_html(basis)
    assert '<a href="#retrieval-r-one">4.2 percent for 2021 (zzstat / ZZ-PRICE)</a>' in page
    assert "<q>4.0</q>" in page


def test_a_series_break_is_explained_as_one_not_as_two_measures() -> None:
    """Contested by definition has two causes; the sentence names the one that applies."""
    fixture = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"
    context = ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"), language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )
    store = RetrievalStore(":memory:")
    try:
        artifact = verify("output rose in 2019", context, PackRegistry.from_directory(fixture),
                          build_fixture_custodians(), store).artifact
    finally:
        store.close()
    text = artifact.render()
    assert "changed how the series is defined" in text
    assert "more than one measured thing" not in text
    assert "more than one measured thing" in _section(_claim("8"))
