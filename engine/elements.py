"""Element taxonomies and the two element types.

The separation between :class:`Element` and :class:`DerivedElement` is
load-bearing and is expressed here as two types rather than one type with a
flag.  Spec §8 says it plainly: derived elements "carry a relationship tag
and never a status, never a retrieval, never a tolerance band — the absence
of those columns is the guarantee, expressed in the schema rather than in a
rule someone has to remember."

A single type with an ``is_derived`` flag would put that guarantee back into
the category of rules someone has to remember, and §9.7.4 explains what it
would cost: a derived element able to carry Verified is a mechanism for
laundering an invented implication into a checked fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from engine.ids import ClaimId, DerivedElementId, ElementId, MeasureId
from engine.spans import Span


class ElementStatus(Enum):
    """Spec §6.1.  Assigned automatically, final on retrieval."""

    VERIFIED = "verified"
    CONTRADICTED = "contradicted"
    UNVERIFIED = "unverified"
    UNREACHABLE = "unreachable"
    CONTESTED_BY_DEFINITION = "contested_by_definition"
    OUT_OF_SCOPE = "out_of_scope"


class ElementKind(Enum):
    """What sort of assertion an element makes.

    The kind selects the tolerance rule (§9.2).  Superlatives, directions,
    and discrete counts bypass the numeric bands entirely, because a claim
    that something is the highest ever is not 97% correct when it is the
    third highest.
    """

    QUANTITY = "quantity"
    SUPERLATIVE = "superlative"
    DIRECTION = "direction"
    DISCRETE_COUNT = "discrete_count"
    ADMINISTRATIVE = "administrative"
    # Out-of-scope kinds.  Stage 1 routes these out; they can never reach
    # VERIFIED by any path, which is what makes them structurally
    # unreachable by the reconstructor (AC-15 scope closure).
    OPINION = "opinion"
    PREDICTION = "prediction"
    CAUSAL = "causal"


OUT_OF_SCOPE_KINDS: frozenset[ElementKind] = frozenset(
    {ElementKind.OPINION, ElementKind.PREDICTION, ElementKind.CAUSAL}
)


class ToleranceBand(Enum):
    """Spec §9.2.  Derived from published precision, never chosen."""

    A = "A"
    B = "B"  # Verified, tagged `rounded`
    C = "C"  # Contradicted


class ContinuityStatus(Enum):
    """Spec §9.5.  Whether a retrieved span crosses a series break."""

    NOT_APPLICABLE = "not_applicable"  # element does not compare across time
    NO_BREAK_CROSSED = "no_break_crossed"
    LINKED_SERIES_USED = "linked_series_used"
    UNLINKED_BREAK = "unlinked_break"  # never Verified — no splicing


class DerivationOperation(Enum):
    """Spec §9.7.2.  A closed, versioned list.

    Not operator-configurable, on the same footing as the routing tables and
    the tolerance bands.  An operator who can add derivation operations can
    manufacture implications, which is the whole risk restated.
    """

    CAUSAL_DISCHARGE = "causal-discharge"
    SUPERLATIVE_DISCHARGE = "superlative-discharge"
    COMPARATIVE_DISCHARGE = "comparative-discharge"
    EVALUATIVE_DISCHARGE = "evaluative-discharge"
    SCOPE_DISCHARGE = "scope-discharge"


class RelationshipTag(Enum):
    """Spec §6.3.  A derived element's position relative to both versions."""

    IMPLIED_BY_ORIGINAL_ONLY = "implied-by-original-only"
    IMPLIED_BY_RECONSTRUCTED = "implied-by-reconstructed"
    CONTRADICTED_BY_RECONSTRUCTED = "contradicted-by-reconstructed"
    INDEPENDENT = "independent"


class GateState(Enum):
    """Spec §9.1.  The sign-off state machine."""

    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    AMENDED = "amended"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class Element:
    """An atomic checkable element, anchored to a span of the claim text.

    ``span`` has no default and is not optional.  An element with no
    anchoring span is inadmissible under §9.7.1 as extended in v0.4, and
    making it unconstructable is cheaper than checking for it later — AC-18
    requires the check to run before Stage 3, and a type that cannot hold the
    invalid state runs it at construction.
    """

    id: ElementId
    claim_id: ClaimId
    fragment: str
    span: Span
    kind: ElementKind
    measure_id: MeasureId | None = None
    status: ElementStatus | None = None
    tolerance_band: ToleranceBand | None = None
    continuity_status: ContinuityStatus | None = None

    @property
    def is_out_of_scope(self) -> bool:
        return self.kind in OUT_OF_SCOPE_KINDS


@dataclass(frozen=True, slots=True)
class VerifiedElement:
    """An element that has survived verification, with what it contributes.

    The reconstructor's only input type (§9.9).  Spec §4 Stage 7 says the
    structural guarantee in as many words: "there is no code path by which
    such a clause reaches the reconstructor, because the reconstructor reads
    only the verified element set."  This type is that sentence.

    Construction fails for anything not Verified, so an out-of-scope element
    cannot be handed to the reconstructor even by mistake — AC-15's scope
    closure test is enforced at the type boundary rather than checked inside
    the composition loop.
    """

    element: Element
    measure_name: str
    figure: object | None = None  # engine.figures.Figure; typed loosely to avoid a cycle

    def __post_init__(self) -> None:
        if self.element.status is not ElementStatus.VERIFIED:
            raise ValueError(
                f"element {self.element.id} has status "
                f"{self.element.status.value if self.element.status else 'unassigned'}, "
                "not verified. Only verified elements reach the reconstructor (§4 Stage 7)"
            )
        if self.element.is_out_of_scope:
            raise ValueError(
                f"element {self.element.id} is kind {self.element.kind.value}, which "
                "§2 excludes. An out-of-scope element can never be Verified, and this "
                "guard exists so that a bug upstream cannot make it so downstream"
            )

    @property
    def span_start(self) -> int:
        return self.element.span.start

    @property
    def sort_key(self) -> tuple[int, str]:
        """§9.9.1's total order: span position, then element id.

        A property of the claim text and the element set, never of retrieval
        timing, insertion order, or hash iteration — each of which would make
        the same element set render differently across runs.
        """
        return (self.element.span.start, self.element.id.value)


@dataclass(frozen=True, slots=True)
class DerivedElement:
    """A claim the original invites the reader to conclude.

    Note what is absent: no status, no tolerance band, no continuity status,
    no retrieval id.  Those absences are the guarantee (§9.7.4), and AC-16
    asserts them by introspecting this class's fields.  Adding any of them
    here would defeat §9.6 by a different route.
    """

    id: DerivedElementId
    from_claim_id: ClaimId
    text: str
    span: Span
    operation: DerivationOperation
    tag: RelationshipTag
    state: GateState = GateState.PROPOSED
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
