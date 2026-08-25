"""Stage 7 — the reconstructor.

Spec §4's governing rule:

    A reconstruction is a **pure function of the current verified element
    set**. Every revision is re-derived from scratch from that set. No
    revision is ever produced by editing the text of a previous revision.

The signature carries that guarantee.  There is no parameter through which a
previous revision, a draft, or a prior text can be passed, so an append-based
reconstructor is not merely discouraged — it is unexpressible.  AC-15 asks
for an assertion that "no code path produces revision *n* by taking revision
*n−1* as input"; here that is true by inspection of one line.

§4 explains why the distinction is easy to get wrong: "the naive
implementation looks equivalent. An append-based reconstructor — one that
takes the previous sentence and adds a clause when a new element verifies —
is a text generator that accretes. It cannot shrink correctly when an element
regresses."

Composition is deterministic template assembly over the §9.9 grammar.  It is
never a language model.  AC-15's note is explicit that "a reconstructor built
to produce fluent prose will reach for connectives to smooth two adjacent
verified facts into a sentence, and the resulting causal implication will
carry the full authority of the citation trail while resting on nothing."
The defence is not review; it is that the reconstructor has no vocabulary for
the sentence it should not write.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from engine.elements import ElementKind, VerifiedElement
from engine.packs.schema import Lexicon
from engine.verification import patterns


class ForbiddenConnective(Exception):
    """Raised when composed text carries a connective no element licenses.

    Raising rather than stripping. §9.9.2 puts this on the same footing as an
    unsourced figure failing a render: a reconstruction that has acquired a
    causal connective is not a reconstruction with a blemish, it is a
    different claim.
    """


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    """One revision. A projection of evidence, not an authored sentence."""

    text: str
    does_reconstruct: bool
    element_set_hash: str
    element_ids: tuple[str, ...] = ()
    clauses: tuple[str, ...] = field(default=())

    @property
    def is_empty(self) -> bool:
        return not self.element_ids


def element_set_hash(elements: frozenset[VerifiedElement]) -> str:
    """A stable hash of the verified element set.

    §8: "``element_set_hash`` is what makes the pure-function property
    checkable after the fact: two revisions with the same hash must have
    identical text, and a revision whose text does not re-derive from its
    recorded element set is evidence the reconstructor edited rather than
    re-derived."

    Canonical ordering and canonical JSON, so the hash depends on the set and
    not on how it happened to be assembled.
    """
    payload = [
        {
            "id": verified.element.id.value,
            "fragment": verified.element.fragment,
            "span": [verified.element.span.start, verified.element.span.end],
            "kind": verified.element.kind.value,
            "measure": verified.measure_name,
            "retrieval": getattr(verified.figure, "retrieval_id", None)
            and str(verified.figure.retrieval_id),  # type: ignore[union-attr]
        }
        for verified in sorted(elements, key=lambda v: v.sort_key)
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reconstruct(
    elements: frozenset[VerifiedElement], lexicon: Lexicon
) -> ReconstructionResult:
    """Derive a reconstruction from the current verified element set.

    Note the absence: no ``previous``, no ``prior_text``, no ``revision``.
    The reconstructor's only input is the element set and the grammar.
    """
    ordered = sorted(elements, key=lambda v: v.sort_key)
    digest = element_set_hash(elements)

    if not ordered:
        return ReconstructionResult(
            text="", does_reconstruct=False, element_set_hash=digest
        )

    clauses = _clauses(ordered, lexicon)
    if not clauses:
        # §4: "If the surviving elements do not compose into a coherent
        # statement, the correct output is the element list plus 'does not
        # reconstruct,' not a smoothed-over sentence."
        return ReconstructionResult(
            text="",
            does_reconstruct=False,
            element_set_hash=digest,
            element_ids=tuple(v.element.id.value for v in ordered),
        )

    text, fragment_ranges = _join(clauses, lexicon)
    _reject_unlicensed_connectives(text, fragment_ranges, lexicon)

    return ReconstructionResult(
        text=text,
        does_reconstruct=True,
        element_set_hash=digest,
        element_ids=tuple(v.element.id.value for v in ordered),
        clauses=tuple(clauses),
    )


def _clauses(ordered: list[VerifiedElement], lexicon: Lexicon) -> list[str]:
    """One clause per bound measure, slots filled in the pack's declared order.

    Grouping by measure rather than emitting one clause per element is what
    keeps a reconstruction from reading as a list of disconnected fragments.
    Elements sharing a measure describe the same thing and belong in the same
    clause; elements with different measures do not, and joining them with
    anything stronger than enumeration would assert a relationship the record
    does not carry.
    """
    grouped: dict[str, list[VerifiedElement]] = {}
    order: list[str] = []
    for verified in ordered:
        key = verified.measure_name
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(verified)

    clauses: list[str] = []
    for measure_name in order:
        members = grouped[measure_name]
        slots = _slots(members, measure_name)
        rendered = [slots[name] for name in lexicon.element_slot_order if slots.get(name)]
        # A clause needs more than a bare time period to say anything.
        if not any(slots.get(name) for name in ("direction", "quantity")):
            continue
        if rendered:
            clauses.append(" ".join(rendered))
    return clauses


def _slots(members: list[VerifiedElement], measure_name: str) -> dict[str, str]:
    """Fill the §9.9.1 slots from a measure's verified elements."""
    slots: dict[str, str] = {"measure": measure_name}
    ordered = sorted(members, key=lambda v: v.sort_key)

    for verified in ordered:
        fragment = verified.element.fragment.strip()
        if patterns.TIME_PERIOD.fullmatch(fragment):
            slots.setdefault("time_period", fragment)
        elif verified.element.kind in (ElementKind.DIRECTION, ElementKind.SUPERLATIVE):
            slots.setdefault("direction", fragment)

    # The quantity slot is filled from a retrieval and from nowhere else,
    # independently of which element triggered the pull. §3 admits no figure
    # that did not originate from a recorded retrieval, and a claim's own
    # numeral is not one — so an element carrying a number but no Figure
    # contributes no quantity, and the clause says only what the record says.
    for verified in ordered:
        if verified.figure is not None:
            slots.setdefault("quantity", verified.figure.render())  # type: ignore[union-attr]
            break

    return slots


def _join(clauses: list[str], lexicon: Lexicon) -> tuple[str, list[tuple[int, int]]]:
    """Join clauses with allowlist connectives only.

    Returns the text and the character ranges the clauses occupy, so that the
    connective scan can distinguish a connective the reconstructor inserted
    from one carried inside an element's own fragment.
    """
    separator = _separator(lexicon)
    parts: list[str] = []
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for index, clause in enumerate(clauses):
        if index:
            parts.append(separator)
            cursor += len(separator)
        parts.append(clause)
        ranges.append((cursor, cursor + len(clause)))
        cursor += len(clause)

    text = "".join(parts)
    if text:
        text = text[0].upper() + text[1:]
        if not text.endswith("."):
            text += "."
    return text, ranges


def _separator(lexicon: Lexicon) -> str:
    """Pick the joining connective deterministically.

    Longest-first among the pack's declared connectives, so the choice is a
    property of the pack rather than of iteration order. Enumeration only —
    the loader has already rejected any causal or evaluative term in this
    list (interface §3.6).
    """
    candidates = [c for c in lexicon.composition_connectives if c.strip()]
    if not candidates:
        return " "
    chosen = sorted(candidates, key=lambda c: (-len(c), c))[0]
    return chosen if chosen.startswith((" ", ",", ";")) else f" {chosen} "


def _reject_unlicensed_connectives(
    text: str, fragment_ranges: list[tuple[int, int]], lexicon: Lexicon
) -> None:
    """§9.9.2's pre-emission scan.

    A forbidden connective is permitted only where it "originates in a single
    Verified element that itself carries it" — that is, inside one clause,
    not between two. A match spanning a join is the reconstructor supplying a
    connective the elements do not license, which is exactly the composition
    §9.6 prohibits.
    """
    lowered = text.lower()
    for connective in lexicon.forbidden_connectives:
        for match in re.finditer(rf"\b{re.escape(connective.lower())}\b", lowered):
            if not _inside_one_clause(match.start(), match.end(), fragment_ranges):
                raise ForbiddenConnective(
                    f"reconstruction composed the connective {connective!r} between "
                    "elements. Two verified facts joined by a causal connective assert "
                    "a third claim that neither supports, carrying both elements' "
                    "citation records (§9.6)"
                )


def _inside_one_clause(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(low <= start and end <= high for low, high in ranges)
