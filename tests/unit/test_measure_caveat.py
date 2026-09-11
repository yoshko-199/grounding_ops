"""§5's framing caveat surfaces every declared confusion, not just the first.

docs/plan.md §2.2b: `_measure_caveat` used to take `known_confusions[0]` and
drop the rest, so a measure declaring four confusions — the Bank of Israel's
dollar rate does — surfaced one in its citations and hid three, chosen by
pack ordering rather than by anything about the claim being checked.

No test exercised this before; the bug shipped invisibly because a
conformance suite exercising only single-confusion fixture measures could
not see it, and the fixture pack's own multi-confusion measure
(`price_index`, three confusions) was never checked against its caveat
output either.
"""

from __future__ import annotations

import pathlib

from engine.packs.registry import PackRegistry
from engine.packs.schema import Measure
from engine.verification.retrieve import _measure_caveat

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"


def _measure(confusions: tuple[str, ...]) -> Measure:
    return Measure(
        id="m", name="M", definition="d", custodian_id="c", series_identifier="X",
        unit="u", published_precision=0.1, discrete=False,
        known_confusions=confusions,
        admissible_baselines=(), admissible_windows=(), admissible_source_ref="ref",
    )


def test_a_single_confusion_still_renders() -> None:
    caveat = _measure_caveat(_measure(("Only one confusion here.",)))
    assert caveat == "Framing: Only one confusion here."


def test_every_declared_confusion_renders_not_just_the_first() -> None:
    caveat = _measure_caveat(_measure(("First.", "Second.", "Third.", "Fourth.")))
    assert caveat is not None
    for confusion in ("First.", "Second.", "Third.", "Fourth."):
        assert confusion in caveat, (
            f"{confusion!r} was dropped -- only some declared confusions rendered"
        )


def test_none_known_renders_no_caveat() -> None:
    assert _measure_caveat(_measure(("none known",))) is None
    assert _measure_caveat(_measure(("None Known",))) is None  # case-insensitive


def test_none_known_mixed_with_real_confusions_drops_only_the_placeholder() -> None:
    caveat = _measure_caveat(_measure(("none known", "A real confusion.")))
    assert caveat == "Framing: A real confusion."


def test_the_fixture_pricindex_measure_surfaces_all_three_confusions() -> None:
    """The one fixture measure declaring more than one confusion, checked
    against the pack as loaded rather than a hand-built Measure."""
    registry = PackRegistry.from_directory(PACKS)
    from engine.codes import JurisdictionCode

    pack = registry.get(JurisdictionCode("ZZ"))
    assert pack is not None
    measure = pack.measure("price_index")
    assert measure is not None
    assert len(measure.known_confusions) == 3, (
        "this test relies on price_index declaring three confusions; update it "
        "if the fixture changes"
    )
    caveat = _measure_caveat(measure)
    assert caveat is not None
    for confusion in measure.known_confusions:
        assert confusion in caveat
