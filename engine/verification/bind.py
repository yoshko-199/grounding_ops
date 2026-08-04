"""Stage 3 — measure binding, before any source is chosen.

Spec §4: "Stage 3 is not optional. The most common way a true number becomes
a misleading claim is measure ambiguity."  And §3's framing: "'Primary
source' is not a sufficient category — **measure identity is the actual unit
of correctness**."

Binding precedes routing by construction, not by convention: this module
takes a pack and a claim and returns a measure, and it has no access to an
adapter, a custodian, or a series.  Nothing here *can* choose a source,
because choosing a source before deciding what is being measured is how
motivated reasoning enters looking like diligence.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.packs.schema import Measure, Pack
from engine.verification import patterns

# A name match is stronger evidence than a definition match. A measure whose
# published name appears in the claim is being named; one whose definition
# happens to share a word may only be adjacent.
_NAME_WEIGHT = 3
_DEFINITION_WEIGHT = 1


@dataclass(frozen=True, slots=True)
class Binding:
    """The outcome of binding a claim fragment to a measure."""

    measure: Measure | None
    contested: tuple[Measure, ...] = ()
    rationale: str = ""

    @property
    def is_contested(self) -> bool:
        """§6.1 — two custodians measuring different things.

        "Both reported, with the definitional gap explained."  Not an error,
        and not a tie to be broken: reporting one of them would be choosing
        an answer rather than reporting the record.
        """
        return len(self.contested) > 1

    @property
    def bound(self) -> bool:
        return self.measure is not None


def bind(claim_text: str, pack: Pack) -> Binding:
    """Bind a claim to a measure declared in the pack, or decline to."""
    claim_tokens = patterns.significant(claim_text)
    if not claim_tokens:
        return Binding(None, rationale="claim carries no bindable content")

    jurisdiction_token = patterns.stem(str(pack.jurisdiction).lower())
    scored: list[tuple[int, Measure]] = []

    for measure in pack.measures:
        name_tokens = patterns.significant(measure.name) - {jurisdiction_token}
        definition_tokens = patterns.significant(measure.definition) - {jurisdiction_token}
        score = (
            _NAME_WEIGHT * len(name_tokens & claim_tokens)
            + _DEFINITION_WEIGHT * len(definition_tokens & claim_tokens)
        )
        if score:
            scored.append((score, measure))

    if not scored:
        # Interface §4.1: pack exists, no measure matches the element.
        # Insufficient Data, never a nearest-neighbour guess.
        return Binding(
            None,
            rationale=(
                "no measure in the pack matches this claim. Binding to the nearest "
                "available measure would answer a different question than the one asked"
            ),
        )

    scored.sort(key=lambda pair: (-pair[0], pair[1].id))
    best_score = scored[0][0]
    leaders = [measure for score, measure in scored if score == best_score]

    if len(leaders) > 1 and _definitionally_distinct(leaders):
        return Binding(
            None,
            contested=tuple(leaders),
            rationale=(
                "two declared measures match this claim equally well and measure "
                "different things: "
                + "; ".join(f"{m.name} ({m.custodian_id})" for m in leaders)
            ),
        )

    winner = leaders[0]
    return Binding(
        winner,
        rationale=(
            f"bound to {winner.name} on the measure's published name and definition, "
            f"before any custodian was consulted"
        ),
    )


def _definitionally_distinct(measures: list[Measure]) -> bool:
    """Whether tied measures genuinely differ rather than duplicating.

    Two entries from the same custodian with the same unit are a pack defect
    to be reported as ambiguity; two from different custodians are the §6.1
    "Contested by definition" case the spec wants surfaced.
    """
    return len({m.custodian_id for m in measures}) > 1 or len({m.unit for m in measures}) > 1
