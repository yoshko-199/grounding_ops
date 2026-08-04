"""AC-14 — No generic fallback.

Constraint: spec §9.4.  Absence of a custodian yields Insufficient Data.

AC-14's note names the stakes: "This is the criterion that keeps
generalisation from becoming dilution. Every other guarantee in the spec
rests on 'custodian of record' meaning something narrower than 'source that
looks official,' and a fallback path — however well-intentioned, however
rarely taken — dissolves that distinction at exactly the moments it matters
most."
"""

from __future__ import annotations

from datetime import date

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.elements import ElementStatus
from engine.packs.registry import PackRegistry
from engine.verification import retrieve
from engine.verification.route import RoutingFailure, route
from tests.conformance._graph import modules_under, reachable

# Anything that could originate a figure from outside a declared custodian.
NETWORK_MODULES = frozenset(
    {
        "urllib", "urllib.request", "http", "http.client", "socket",
        "requests", "httpx", "aiohttp", "ftplib", "telnetlib", "webbrowser",
        "subprocess",
    }
)


@pytest.mark.parametrize("module", modules_under("engine.verification"))
def test_no_verification_module_can_reach_a_network_primitive(module: str) -> None:
    """The static half of AC-14.

    "Assert by static analysis that no retrieval path can reach a source that
    is not a declared custodian in a loaded pack — no web search, no news
    source, no model prior, no operator-supplied URL."
    """
    reached = reachable(module)
    offenders = sorted(reached & NETWORK_MODULES)
    assert not offenders, (
        f"{module} can reach {offenders}. A retrieval path able to reach the network "
        "outside a declared custodian adapter is the generic fallback §9.4 forbids."
    )


def test_no_adapter_accepts_a_url() -> None:
    """An operator-supplied URL is a custodian nobody declared."""
    import inspect

    from engine.custodians.base import CustodianAdapter

    signature = inspect.signature(CustodianAdapter.series)
    for parameter in signature.parameters:
        assert parameter not in ("url", "endpoint", "uri", "source", "fallback_url")


def test_claim_in_a_jurisdiction_with_no_pack_is_insufficient_data(
    registry: PackRegistry,
) -> None:
    context = ClaimContext(
        jurisdiction=JurisdictionCode("QQ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )
    decision = route("prices rose in 2021", context, registry)
    assert not decision.routed
    assert decision.failure is RoutingFailure.NO_JURISDICTION
    assert decision.rationale


def test_claim_whose_measure_has_no_pack_entry_is_insufficient_data(
    registry: PackRegistry, context: ClaimContext
) -> None:
    decision = route("badger population rose in 2021", context, registry)
    assert not decision.routed
    assert decision.failure is RoutingFailure.NO_MEASURE
    assert "nearest available measure" in decision.rationale


def test_no_route_falls_back_to_another_custodian(
    registry: PackRegistry, context: ClaimContext
) -> None:
    """Every routed decision lands on a custodian the pack declared."""
    pack = registry.get(JurisdictionCode("ZZ"))
    declared = {c.id for c in pack.custodians}
    for claim in ("prices rose in 2021", "unemployment fell in 2021", "seats rose in 2023"):
        decision = route(claim, context, registry)
        if decision.routed:
            assert decision.custodian_id in declared


def test_unreachable_and_unverified_do_not_collapse(pack, adapters, store) -> None:
    """§6.1 keeps them apart; AC-14 asserts neither becomes the other.

    One is a fact about today's network, the other a fact about the record,
    and a reader needs to be able to tell which they are looking at.
    """
    measure = pack.measure("price_index")
    custodian = pack.custodian("zzstat")

    adapters["zzstat"].unreachable = True
    unreachable = retrieve.pull(measure, custodian, adapters["zzstat"], store)
    assert unreachable.blocked_status is ElementStatus.UNREACHABLE

    adapters["zzstat"].unreachable = False
    adapters["zzstat"]._series.pop(measure.series_identifier)
    unverified = retrieve.pull(measure, custodian, adapters["zzstat"], store)
    assert unverified.blocked_status is ElementStatus.UNVERIFIED

    assert unreachable.blocked_status is not unverified.blocked_status
    assert "not be reported as Unverified" in unreachable.detail


def test_registry_has_no_fallback_pack(registry: PackRegistry) -> None:
    assert registry.get(JurisdictionCode("QQ")) is None
    assert registry.get(None) is None
