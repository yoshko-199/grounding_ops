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
