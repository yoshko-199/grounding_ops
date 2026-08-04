"""AC-17 — Jurisdiction projection.

Constraint: spec §9.8.  Only a jurisdiction code crosses from provenance into
the verification path.

AC-17's note names the failure mode being prevented: "A default jurisdiction
fails in the worst available way. Every element would be genuinely Verified
against a real custodian with a real citation record, and the entire artifact
would be about the wrong country — an error with no internal symptom, because
nothing in the pipeline is malfunctioning."
"""

from __future__ import annotations

import dataclasses
import pathlib
import shutil
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.ingest.identity import ClaimantIdentity
from engine.ingest.split import RawProvenance, split
from engine.packs.registry import PackRegistry
from engine.verification.route import JurisdictionRule, RoutingFailure, route

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture" / "zz.toml"


def _two_pack_registry(tmp_path: pathlib.Path) -> PackRegistry:
    """ZZ plus a supranational pack, so §9.8.2 rule 3 has something to fire on."""
    shutil.copy(FIXTURE, tmp_path / "zz.toml")
    supranational = FIXTURE.read_text(encoding="utf-8").replace("ZZ", "OECD")
    (tmp_path / "oecd.toml").write_text(supranational, encoding="utf-8")
    return PackRegistry.from_directory(tmp_path)


# -- structural split -------------------------------------------------------


def test_context_and_identity_are_separate_records() -> None:
    """"Assert claim_context and claimant_identity are separate records
    populated at ingest, not a single provenance structure filtered at point
    of use"."""
    context, identity = split(
        RawProvenance(
            stated_at=date(2022, 1, 1),
            language="en",
            jurisdiction_hint="ZZ",
            claimant_name="A. Person",
            venue="speech at the party conference",
        )
    )
    assert isinstance(context, ClaimContext)
    assert isinstance(identity, ClaimantIdentity)
    assert not isinstance(context, ClaimantIdentity)

    context_fields = {f.name for f in dataclasses.fields(ClaimContext)}
    identity_fields = {f.name for f in dataclasses.fields(ClaimantIdentity)}
    assert not context_fields & identity_fields


def test_claim_context_carries_no_free_text() -> None:
    context, _ = split(
        RawProvenance(stated_at=date(2022, 1, 1), language="en", jurisdiction_hint="ZZ")
    )
    assert isinstance(context.jurisdiction, JurisdictionCode)
    assert isinstance(context.language, LanguageCode)
    assert isinstance(context.stated_at, date)


def test_a_venue_naming_a_party_cannot_become_a_jurisdiction() -> None:
    """§9.8: venue is "nominally a location and functionally an affiliation"."""
    for venue in ("speech at the ZZ party conference", "Freedom Party HQ", "ZZ"):
        context, identity = split(
            RawProvenance(
                stated_at=date(2022, 1, 1),
                language="en",
                jurisdiction_hint=None,
                venue=venue,
            )
        )
        assert context.jurisdiction is None, (
            "a venue string reached the jurisdiction, which is the smuggling route "
            "§9.8.1 closes"
        )
        assert identity.venue == venue


def test_a_malformed_hint_becomes_no_hint_rather_than_an_error() -> None:
    context, _ = split(
        RawProvenance(
            stated_at=date(2022, 1, 1), language="en", jurisdiction_hint="the party conference"
        )
    )
    assert context.jurisdiction is None


# -- resolution order, §9.8.2 ----------------------------------------------


def test_rule_1_explicit_in_the_claim_text(registry: PackRegistry) -> None:
    """Preferred, "because it needs no provenance at all"."""
    context = ClaimContext(None, LanguageCode("en"), date(2022, 1, 1))
    decision = route("prices in ZZ rose in 2021", context, registry)
    assert decision.jurisdiction_rule is JurisdictionRule.EXPLICIT_IN_TEXT
    assert decision.jurisdiction == JurisdictionCode("ZZ")


def test_rule_2_the_context_hint(registry: PackRegistry, context: ClaimContext) -> None:
    decision = route("prices rose in 2021", context, registry)
    assert decision.jurisdiction_rule is JurisdictionRule.CONTEXT_HINT
    assert decision.jurisdiction == JurisdictionCode("ZZ")


def test_rule_3_a_supranational_measure(tmp_path: pathlib.Path) -> None:
    registry = _two_pack_registry(tmp_path)
    context = ClaimContext(None, LanguageCode("en"), date(2022, 1, 1))
    decision = route("prices rose in 2021", context, registry)
    assert decision.jurisdiction_rule is JurisdictionRule.SUPRANATIONAL_MEASURE
    assert decision.jurisdiction == JurisdictionCode("OECD")


def test_rule_4_otherwise_insufficient_data(registry: PackRegistry) -> None:
    context = ClaimContext(None, LanguageCode("en"), date(2022, 1, 1))
    decision = route("badger population rose in 2021", context, registry)
    assert decision.jurisdiction_rule is JurisdictionRule.UNRESOLVED
    assert decision.failure is RoutingFailure.NO_JURISDICTION
    assert not decision.routed


def test_each_resolution_records_which_rule_fired(registry: PackRegistry) -> None:
    """"Assert each records which rule fired in routing_log"."""
    context = ClaimContext(None, LanguageCode("en"), date(2022, 1, 1))
    for claim in ("prices in ZZ rose in 2021", "badger population rose in 2021"):
        decision = route(claim, context, registry)
        assert isinstance(decision.jurisdiction_rule, JurisdictionRule)


# -- no default -------------------------------------------------------------


def test_no_default_jurisdiction_exists_anywhere(registry: PackRegistry) -> None:
    """Even with exactly one pack loaded, an unresolvable claim routes nowhere."""
    assert len(registry) == 1
    context = ClaimContext(None, LanguageCode("en"), date(2022, 1, 1))
    decision = route("badger population rose in 2021", context, registry)
    assert decision.jurisdiction is None
    assert decision.pack is None


def test_route_exposes_no_default_parameter() -> None:
    import inspect

    for parameter in inspect.signature(route).parameters:
        assert parameter not in ("default", "default_jurisdiction", "fallback")
