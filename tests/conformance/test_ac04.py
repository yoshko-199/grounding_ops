"""AC-4 — Routing rationale exposed.

Constraint: spec §7.4.  Why this custodian and not another, in the output.

AC-4's note: "A routing table showing only winners is indistinguishable from
one built backwards from preferred answers. The alternatives are the audit."
"""

from __future__ import annotations

import pytest

from engine.packs.registry import PackRegistry
from engine.verification.route import route

CLAIMS = [
    "prices rose in 2021",
    "unemployment fell in 2021",
    "output rose in 2019",
    "seats rose in 2023",
]


@pytest.mark.parametrize("claim", CLAIMS)
def test_every_routed_element_carries_custodian_rationale_and_alternatives(
    claim: str, registry: PackRegistry, context
) -> None:
    decision = route(claim, context, registry)
    if not decision.routed:
        pytest.skip(f"{claim!r} does not route; covered by AC-14")
    assert decision.custodian_id
    assert decision.rationale.strip()
    assert decision.alternatives_considered, (
        "alternatives_considered is empty. AC-4 admits emptiness only where the pack "
        "declares no alternative custodian exists, and the router renders that "
        "declaration explicitly rather than as a blank"
    )
    assert all(a.strip() for a in decision.alternatives_considered)


def test_emptiness_always_corresponds_to_a_pack_declaration(
    registry: PackRegistry, context
) -> None:
    """"assert that emptiness always corresponds to such a declaration"."""
    decision = route("prices rose in 2021", context, registry)
    rule = decision.pack.route_for(decision.measure.id)
    assert rule.no_alternative_custodian
    assert decision.alternatives_considered
    assert "no other custodian" in decision.alternatives_considered[0]


def test_a_failed_route_still_explains_itself(registry: PackRegistry, context) -> None:
    """Insufficient Data is an answer, and §7.5 requires it to read as one."""
    decision = route("badger population rose in 2021", context, registry)
    assert not decision.routed
    assert decision.rationale.strip()


def test_rationale_names_the_measure_before_the_custodian(
    registry: PackRegistry, context
) -> None:
    """Stage 3 precedes Stage 4, and the rationale should show it.

    "Choosing a source before deciding what is being measured is how a true
    figure becomes a misleading claim."
    """
    decision = route("prices rose in 2021", context, registry)
    assert "before any custodian was consulted" in decision.rationale


def test_pack_version_is_available_for_the_routing_log(
    registry: PackRegistry, context
) -> None:
    """AC-3 requires the bump to be recorded in routing_log.pack_version."""
    decision = route("prices rose in 2021", context, registry)
    assert decision.pack_version == "1.0.0-fixture"


# ---------------------------------------------------------------------------
# A contested binding must reach the reader with its reason intact.
#
# §6.1: two custodians measuring different things are "both reported, with the
# definitional gap explained". The gap is what the routing rationale holds —
# which measures matched equally well, and that they are not the same
# quantity. Reporting the generic "no custodian settles this" instead is true
# and useless: it hides that two custodians settle neighbouring questions and
# the claim never said which it meant.
#
# The path existed and was never taken. No fixture claim produces a tie, so it
# surfaced only when a real pack declared sibling measures.
# ---------------------------------------------------------------------------

import pathlib

LIVE_PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "live"

AMBIGUOUS = "the representative exchange rate fell in 2026"
SPECIFIC = "the euro representative rate fell in 2026"


def _il_context():
    from datetime import date

    from engine.codes import JurisdictionCode, LanguageCode
    from engine.context import ClaimContext

    return ClaimContext(
        jurisdiction=JurisdictionCode("IL"),
        language=LanguageCode("en"),
        stated_at=date(2026, 8, 26),
    )


def _live_registry():
    from engine.packs.registry import PackRegistry

    if not LIVE_PACKS.is_dir():
        pytest.skip("no live pack directory")
    return PackRegistry.from_directory(LIVE_PACKS)


def test_an_ambiguous_claim_over_sibling_measures_does_not_route() -> None:
    """Binding to the nearest sibling would answer a question nobody asked."""
    from engine.verification.route import RoutingFailure, route

    decision = route(AMBIGUOUS, _il_context(), _live_registry())
    assert not decision.routed
    assert decision.failure is RoutingFailure.CONTESTED_BY_DEFINITION

    # The member ids, not just the count. `len(contested) > 1` passed while the
    # set was (euro, sterling) and the dollar — the directly-sampled rate this
    # claim most plausibly means — was missing, because the euro and sterling
    # definitions echoed "representative" from their own names and outscored
    # it. A count assertion cannot see that.
    assert {m.id for m in decision.contested} == {
        "fx_representative_usd",
        "fx_representative_eur",
        "fx_representative_gbp",
    }


def test_the_contested_reason_reaches_the_artifact(adapters, store) -> None:
    """The regression: the rationale was computed, carried, and then dropped."""
    from engine.custodians.fixture import build_fixture_custodians
    from engine.pipeline import verify
    from engine.verdicts import Verdict

    run = verify(
        AMBIGUOUS, _il_context(), _live_registry(), build_fixture_custodians(), store
    )
    rationale = run.artifact.verdict.rationale

    assert run.artifact.verdict.label is Verdict.INSUFFICIENT_DATA
    assert "measure different things" in rationale, (
        f"the definitional gap was not explained; got {rationale!r}"
    )
    assert "No custodian of record settles this claim" not in rationale


def test_naming_the_currency_routes_cleanly(store) -> None:
    """The other half: disambiguating the claim must still bind."""
    from engine.custodians.fixture import build_fixture_custodians
    from engine.pipeline import verify

    run = verify(
        SPECIFIC, _il_context(), _live_registry(), build_fixture_custodians(), store
    )
    assert run.artifact.routing, "a claim naming its currency must route"
    assert "euro" in run.artifact.routing[0].measure.lower()
