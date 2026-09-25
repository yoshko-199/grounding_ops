"""The XD demo pack: the ten supplied claims, landing on every level.

packs/demo/xd.toml and engine/custodians/demo.py give the ten claims
(docs/validation-ten-claims.md) somewhere to be verified. The values are
invented and were chosen to land each claim on a named verification level. So
these tests pin the *data* as much as the engine: change a demo value and the
claim it serves moves.

Three things in here are engine behaviour the demo shows rather than hides.
Each is pinned as current behaviour and points at its requirement in
docs/spec/proposals/v0.6-requirements.md, so that closing a gap changes a
test on purpose rather than by accident:

* the unit gap: "212 degrees Fahrenheit" is compared against a Celsius series;
* the event-date gap: a year is a time period, so "in 1225" cannot be
  contradicted, only reached or not;
* the active-voice causal gap: "Vaccines cause autism" derives nothing.
"""

from __future__ import annotations

import pathlib
from datetime import date

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.demo import build_demo_custodians
from engine.custodians.fixture import build_fixture_custodians
from engine.elements import ElementStatus, ToleranceBand
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.render.figures import scan_prose
from engine.store.events import RetrievalStore
from engine.verdicts import Verdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEMO = ROOT / "packs" / "demo"
XD = JurisdictionCode("XD")


def _run(claim: str):
    context = ClaimContext(jurisdiction=XD, language=LanguageCode("en"), stated_at=date(2024, 1, 1))
    store = RetrievalStore(":memory:")
    try:
        return verify(claim, context, PackRegistry.from_directory(DEMO),
                      build_fixture_custodians(), store)
    finally:
        store.close()


def _statuses(run) -> dict[str, ElementStatus]:
    return {e.fragment.strip(): e.status for e in run.elements}


# id, claim, expected verdict, expected element statuses (a subset)
LEVELS = [
    ("1", "Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at sea level.",
     Verdict.SUBSTANTIALLY_INACCURATE,
     {"100": ElementStatus.VERIFIED, "212": ElementStatus.CONTRADICTED}),
    ("1v", "Water boils at 100 degrees Celsius at sea level.",
     Verdict.INDETERMINATE, {"100": ElementStatus.VERIFIED}),
    ("2", "Pizza is the most delicious food in the world.", Verdict.INSUFFICIENT_DATA, {}),
    ("3", "Humans are classified as mammals.", Verdict.INSUFFICIENT_DATA, {}),
    ("4", "King John of England signed the Magna Carta in 1225",
     Verdict.INSUFFICIENT_DATA, {"in 1225": ElementStatus.UNREACHABLE}),
    ("5", "Covid-19 epidemic originated from a Chinese research lab", Verdict.INSUFFICIENT_DATA, {}),
    ("6", "Vaccines cause Autism in children", Verdict.INSUFFICIENT_DATA, {}),
    ("7", "If you put two sheep in a field, and then another two, you’ve got four sheep "
          "in that field for ever.", Verdict.INSUFFICIENT_DATA, {}),
    ("8", "the density of steel is 7700 kg per cubic metre.",
     Verdict.INDETERMINATE, {"7700": ElementStatus.CONTESTED_BY_DEFINITION}),
    ("8v", "the density of carbon steel is 7700 kg per cubic metre.",
     Verdict.INDETERMINATE, {"7700": ElementStatus.VERIFIED}),
    ("8x", "the density of carbon steel is 9000 kg per cubic metre.",
     Verdict.FALSE, {"9000": ElementStatus.CONTRADICTED}),
    ("9", "The U.S. has a highly progressive tax-and-transfer system that redistributes "
          "massive sums of money.", Verdict.INSUFFICIENT_DATA, {}),
    ("10", "In the U.S gun violence is alien to most people's experiences and the nation's "
           "murder rate has been cut by more than half since 1991",
     Verdict.MISLEADING, {"cut": ElementStatus.VERIFIED, "since 1991": ElementStatus.VERIFIED}),
    ("10v", "the homicide rate fell since 1991",
     Verdict.ACCURATE, {"fell": ElementStatus.VERIFIED, "since 1991": ElementStatus.VERIFIED}),
]


@pytest.mark.parametrize("cid,claim,verdict,statuses", LEVELS, ids=[row[0] for row in LEVELS])
def test_each_claim_lands_on_its_level(cid, claim, verdict, statuses) -> None:
    run = _run(claim)
    assert run.artifact.verdict.label is verdict, (cid, run.artifact.verdict.rationale)
    got = _statuses(run)
    for fragment, status in statuses.items():
        assert got.get(fragment) is status, (cid, fragment, got)
    # Every level renders, in both forms, without raising.
    run.artifact.render()
    run.artifact.render_html()


def test_the_demo_covers_every_claim_level_the_engine_can_reach() -> None:
    reached = {row[2] for row in LEVELS}
    assert reached == {
        Verdict.ACCURATE, Verdict.MISLEADING, Verdict.SUBSTANTIALLY_INACCURATE,
        Verdict.FALSE, Verdict.INDETERMINATE, Verdict.INSUFFICIENT_DATA,
    }


def test_band_b_is_verified_and_recorded_as_band_b() -> None:
    """7700 against a published 7810 is within band B: verified, rounded."""
    run = _run("the density of carbon steel is 7700 kg per cubic metre.")
    element = next(e for e in run.elements if e.fragment.strip() == "7700")
    assert element.status is ElementStatus.VERIFIED
    assert element.tolerance_band is ToleranceBand.B


def test_misleading_flips_on_a_declared_baseline_only() -> None:
    """The murder series flips against the prior year. The demo declares no
    last_break baseline, whose anchor the sweep places at the middle of the
    series whatever breaks exist, so the verdict cannot rest on it."""
    run = _run(LEVELS[12][1])
    flipped = [row for row in run.artifact.sweep.rows if not row.conclusion_holds]
    assert [row.alternative for row in flipped] == ["prior_period"]


# -- the gaps, pinned as current behaviour ---------------------------------------


def test_unit_gap_fahrenheit_is_compared_against_celsius() -> None:
    """Requirement R1 (units). When units are read, this element should become
    unverified for a unit mismatch rather than contradicted."""
    assert _statuses(_run(LEVELS[0][1]))["212"] is ElementStatus.CONTRADICTED


def test_event_date_gap_a_year_is_a_period() -> None:
    """Requirement R2 (event dates). The year is decomposed as a time period."""
    run = _run(LEVELS[4][1])
    assert [e.kind.value for e in run.elements] == ["time_period"]


def test_active_causal_gap_derives_nothing() -> None:
    """Requirement R3 (active-voice causal verbs)."""
    assert _run(LEVELS[6][1]).derived == ()


# -- the pack itself ------------------------------------------------------------


def test_the_demo_pack_loads_and_declares_no_real_name() -> None:
    pack = PackRegistry.from_directory(DEMO).get(XD)
    assert pack is not None
    names = [n for lexicon in pack.lexicons for n in lexicon.names]
    assert names == ["Demoland"]


def test_every_demo_custodian_says_demo() -> None:
    pack = PackRegistry.from_directory(DEMO).get(XD)
    for custodian in pack.custodians:
        assert "Demo" in custodian.name, custodian.name


def test_the_demo_pack_carries_no_numerals() -> None:
    """The same rule as the fixture: values live in the adapter, never the pack."""
    pack = PackRegistry.from_directory(DEMO).get(XD)
    for measure in pack.measures:
        assert not scan_prose(measure.definition), measure.id
        for confusion in measure.known_confusions:
            assert not scan_prose(confusion), measure.id


def test_the_archive_has_no_adapter_on_purpose() -> None:
    assert "xdarch" not in build_demo_custodians()


def test_the_demo_adapters_do_not_touch_zz() -> None:
    adapters = build_fixture_custodians()
    assert {"zzstat", "zzelect", "zzlabour"} <= set(adapters)
    assert not set(build_demo_custodians()) & {"zzstat", "zzelect", "zzlabour"}
