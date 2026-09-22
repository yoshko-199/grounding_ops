"""Stage 4 — jurisdiction resolution and routing.

Spec §9.8.2 fixes the resolution order and §9.8.3 forbids a default at every
level.  Interface §4.1 fixes what happens when resolution fails, and the
answer is always Insufficient Data — never a web search, a news source, or a
model prior.

Every routing decision records which resolution rule fired, per §9.8.2, and
carries its rationale and rejected alternatives into output, per §7.4.  AC-4
states the reason plainly: "A routing table showing only winners is
indistinguishable from one built backwards from preferred answers. The
alternatives are the audit."
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from engine.codes import JurisdictionCode
from engine.context import ClaimContext
from engine.packs.registry import PackRegistry
from engine.packs.schema import Measure, Pack
from engine.verification.bind import Binding, bind


class JurisdictionRule(Enum):
    """§9.8.2's resolution order. Which rule fired is recorded in routing_log."""

    EXPLICIT_IN_TEXT = "explicit_in_text"
    CONTEXT_HINT = "context_hint"
    SUPRANATIONAL_MEASURE = "supranational_measure"
    UNRESOLVED = "unresolved"


class RoutingFailure(Enum):
    """Interface §4.1's failure table. All but the last are Insufficient Data."""

    NO_JURISDICTION = "no_jurisdiction"
    NO_PACK = "no_pack"
    NO_MEASURE = "no_measure"
    NO_ROUTING_RULE = "no_routing_rule"
    CONTESTED_BY_DEFINITION = "contested_by_definition"


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Where an element routes, and why — including where it does not."""

    jurisdiction: JurisdictionCode | None
    jurisdiction_rule: JurisdictionRule
    pack: Pack | None = None
    measure: Measure | None = None
    custodian_id: str | None = None
    rationale: str = ""
    alternatives_considered: tuple[str, ...] = ()
    failure: RoutingFailure | None = None
    contested: tuple[Measure, ...] = ()

    @property
    def routed(self) -> bool:
        return self.custodian_id is not None and self.measure is not None

    @property
    def pack_version(self) -> str | None:
        return self.pack.version if self.pack else None


def resolve_jurisdiction(
    claim_text: str, context: ClaimContext, registry: PackRegistry
) -> tuple[JurisdictionCode | None, JurisdictionRule]:
    """Apply §9.8.2's four rules in order.

    Rule 1 is preferred "because it needs no provenance at all" — a claim that
    names its own jurisdiction has told the pipeline what it needs without
    anything crossing the ingest boundary.

    Real claims say "Israel", not "IL", so the code check alone used to leave
    rule 1 firing on almost nothing — see the note this replaced, still true
    of the code check by itself: matching only the bare code is exact but
    rare. Interface v1.3 gives a lexicon an optional ``names`` field for
    exactly this — the demonyms and short forms a claim in that language may
    use — and a declared name is checked with the same word-boundary
    exactness as the code, case-insensitively, because a proper noun a
    claimant typed is not guaranteed to carry the maintainer's capitalisation.

    A pack that declares no names for a language falls straight through to
    rule 2, which is the pre-v1.3 behaviour exactly — nothing about this rule
    changes for a pack that opts out, and the failure stays conservative: an
    unresolved jurisdiction is Insufficient Data, never a guess.
    """
    for code in registry.jurisdictions:
        if re.search(rf"\b{re.escape(code)}\b", claim_text):
            return JurisdictionCode(code), JurisdictionRule.EXPLICIT_IN_TEXT

    for code in registry.jurisdictions:
        pack = registry.get(JurisdictionCode(code))
        if pack is None:
            continue
        for lexicon in pack.lexicons:
            for name in lexicon.names:
                if re.search(rf"\b{re.escape(name)}\b", claim_text, re.I):
                    return JurisdictionCode(code), JurisdictionRule.EXPLICIT_IN_TEXT

    if context.jurisdiction is not None and registry.covers(context.jurisdiction):
        return context.jurisdiction, JurisdictionRule.CONTEXT_HINT

    for code in registry.jurisdictions:
        candidate = JurisdictionCode(code)
        if candidate.is_supranational:
            pack = registry.get(candidate)
            if pack and bind(claim_text, pack).bound:
                return candidate, JurisdictionRule.SUPRANATIONAL_MEASURE

    return None, JurisdictionRule.UNRESOLVED


def route(claim_text: str, context: ClaimContext, registry: PackRegistry) -> RoutingDecision:
    """Resolve jurisdiction, bind the measure, then choose the custodian."""
    jurisdiction, rule = resolve_jurisdiction(claim_text, context, registry)

    if jurisdiction is None:
        return RoutingDecision(
            jurisdiction=None,
            jurisdiction_rule=rule,
            failure=RoutingFailure.NO_JURISDICTION,
            rationale=(
                "no jurisdiction could be established from the claim text or the "
                "ingest context. There is no default jurisdiction: a default would "
                "produce a confident, fully-cited verdict against the wrong country's "
                "custodian, with nothing malfunctioning to reveal it"
            ),
        )

    pack = registry.get(jurisdiction)
    if pack is None:
        return RoutingDecision(
            jurisdiction=jurisdiction,
            jurisdiction_rule=rule,
            failure=RoutingFailure.NO_PACK,
            rationale=(
                f"no custodian pack covers {jurisdiction}. A jurisdiction with no pack "
                "yields Insufficient Data rather than a fallback to a non-custodial "
                "source"
            ),
        )

    binding: Binding = bind(claim_text, pack)

    if binding.is_contested:
        return RoutingDecision(
            jurisdiction=jurisdiction,
            jurisdiction_rule=rule,
            pack=pack,
            failure=RoutingFailure.CONTESTED_BY_DEFINITION,
            rationale=binding.rationale,
            contested=binding.contested,
        )

    if not binding.bound:
        return RoutingDecision(
            jurisdiction=jurisdiction,
            jurisdiction_rule=rule,
            pack=pack,
            failure=RoutingFailure.NO_MEASURE,
            rationale=binding.rationale,
        )

    measure = binding.measure
    assert measure is not None
    rule_entry = pack.route_for(measure.id)
    if rule_entry is None:
        return RoutingDecision(
            jurisdiction=jurisdiction,
            jurisdiction_rule=rule,
            pack=pack,
            measure=measure,
            failure=RoutingFailure.NO_ROUTING_RULE,
            rationale=(
                f"measure {measure.id!r} has no routing rule in the loaded pack. "
                "This is Insufficient Data, and a pack defect to be filed"
            ),
        )

    alternatives = rule_entry.alternatives_considered
    if not alternatives and rule_entry.no_alternative_custodian:
        alternatives = (
            "None. The pack declares that no other custodian in this jurisdiction "
            "publishes this measure.",
        )

    return RoutingDecision(
        jurisdiction=jurisdiction,
        jurisdiction_rule=rule,
        pack=pack,
        measure=measure,
        custodian_id=rule_entry.custodian_id,
        rationale=f"{binding.rationale}. {rule_entry.rationale}",
        alternatives_considered=alternatives,
    )
