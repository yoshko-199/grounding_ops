"""Claim shapes, assembled from slots rather than written out.

A shape is a choice of fragment for each slot. Composing claims this way is
what makes the combinations nobody would write by hand appear on their own —
a period containing a year *and* a superlative *and* a causal tail is the
1,024th entry in a product, not something a test author thinks of.

The vocabulary is deliberately small and deliberately concrete: it names the
fixture jurisdiction's measures, because the point is to exercise the engine
against a pack that can actually retrieve, not to test the binder's tolerance
for nonsense.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import product

#: Each slot is (name, alternatives). The empty string means "omit this
#: slot", which is what lets one product cover claims of very different
#: lengths — and what makes shrinking possible later.
SLOTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "subject",
        (
            "prices",
            "unemployment",
            "registered job-seekers",
            "output",
            "seats",
        ),
    ),
    ("direction", ("rose", "fell")),
    (
        "period",
        (
            "",
            "in 2021",
            "since 2019",
            "between 2019 and 2021",
            "over the last three years",
            "last year",
            "in 1998",
        ),
    ),
    (
        "quantity",
        (
            "",
            "by 4.2 percent",
            "to 102.4 index_points",
            "by 28700",
        ),
    ),
    (
        "superlative",
        (
            "",
            "and is now the highest in years",
            "and is now the lowest in years",
        ),
    ),
    (
        "tail",
        (
            "",
            "due to governmental incompetence",
            "therefore the policy failed",
            "because of mismanagement",
        ),
    ),
)

#: Slots that may be dropped while shrinking a failing claim. ``subject`` and
#: ``direction`` are load-bearing: without them there is no claim left.
OPTIONAL = ("period", "quantity", "superlative", "tail")


@dataclass(frozen=True, slots=True)
class Shape:
    """One claim, and the slot choices that produced it."""

    parts: tuple[tuple[str, str], ...]

    @property
    def text(self) -> str:
        chosen = [value for _, value in self.parts if value]
        return " ".join(chosen)

    def without(self, slot: str) -> Shape:
        return Shape(
            tuple((name, "" if name == slot else value) for name, value in self.parts)
        )

    def filled(self) -> tuple[str, ...]:
        return tuple(name for name, value in self.parts if value)

    def __str__(self) -> str:  # pragma: no cover - reporting aid
        return self.text


def generate() -> list[Shape]:
    """Every combination the vocabulary admits, in a stable order."""
    names = [name for name, _ in SLOTS]
    return [
        Shape(tuple(zip(names, values)))
        for values in product(*[alternatives for _, alternatives in SLOTS])
    ]


def sample(count: int, seed: int) -> list[Shape]:
    """A deterministic subset.

    Seeded rather than arbitrary because a fuzzer whose failures cannot be
    reproduced is a fuzzer nobody acts on. The seed is reported with every
    run and reproduces the exact claim set.
    """
    everything = generate()
    if count >= len(everything):
        return everything
    return random.Random(seed).sample(everything, count)


def shrink(shape: Shape, still_fails) -> Shape:
    """Drop optional slots while the failure survives.

    A fuzzer that reports the claim it happened to generate hands over a
    twelve-word sentence with six things wrong with it. One that shrinks first
    hands over the shortest claim exhibiting the defect, which is usually the
    whole diagnosis — "unemployment fell in 2021" says what "prices rose in
    2021 by 4.2 percent and is now the highest in years due to governmental
    incompetence" does not.
    """
    current = shape
    changed = True
    while changed:
        changed = False
        for slot in OPTIONAL:
            if not dict(current.parts).get(slot):
                continue
            candidate = current.without(slot)
            if not candidate.text.strip():
                continue
            if still_fails(candidate):
                current = candidate
                changed = True
    return current
