"""Shape fuzzing as a gate, and the negative controls that make it one.

The conformance suite asks whether each stated guarantee holds. This file asks
whether the engine stays coherent on claims nobody wrote down, which is a
different question and — on the evidence — a more productive one. Three
defects have now been found this way or by the hand-run that motivated it,
with the suite green each time.

The bounded sample here is a gate, not the whole search. `scripts/fuzz_shapes
.py --all` covers every shape in a few seconds and is the thing to run after
touching decomposition, derivation, verdicts, or rendering.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from engine.elements import ElementKind, ElementStatus
from plugins.shapes.invariants import (
    INVARIANTS,
    _ledger_agrees_with_routing,
    _period_never_contradicted,
    _render_survives,
)
from plugins.shapes.run import fuzz
from plugins.shapes.shapes import Shape, generate, sample, shrink

# Bounded so the suite stays fast. The seed is fixed so a failure here is
# reproducible from the CLI with the same arguments.
GATE_COUNT = 250
GATE_SEED = 0


def test_the_engine_holds_its_invariants_across_generated_shapes() -> None:
    report = fuzz(count=GATE_COUNT, seed=GATE_SEED)
    assert report.checked >= GATE_COUNT // 2, "the generator produced almost nothing"
    assert report.clean, "\n\n".join(
        [str(v) for v in report.violations]
        + [f"crash on {c!r}: {d}" for c, d in report.crashed]
    )


# ---------------------------------------------------------------------------
# Negative controls.
#
# A fuzzer that has never been seen to fail is indistinguishable from one whose
# invariants are all returning None. Each check below plants the defect its
# invariant exists to catch and asserts it is caught.
# ---------------------------------------------------------------------------


@dataclass
class _Element:
    fragment: str
    kind: ElementKind
    status: ElementStatus


@dataclass
class _Entry:
    fragment: str
    reason: str


@dataclass
class _Routing:
    measure: str


@dataclass
class _Artifact:
    routing: tuple = ()
    ledger: tuple = ()


@dataclass
class _Run:
    elements: tuple = ()
    derived: tuple = ()
    artifact: _Artifact = None  # type: ignore[assignment]


def test_the_render_check_catches_a_crash() -> None:
    assert _render_survives("any claim", _Run(), None) is not None
    assert _render_survives("any claim", _Run(), "rendered fine") is None


def test_the_period_check_catches_a_contradicted_period() -> None:
    """The defect that labelled a true claim Substantially Inaccurate."""
    planted = _Run(
        elements=(
            _Element("in 2021", ElementKind.TIME_PERIOD, ElementStatus.CONTRADICTED),
        )
    )
    detail = _period_never_contradicted("unemployment fell in 2021", planted, "x")
    assert detail and "in 2021" in detail

    innocent = _Run(
        elements=(_Element("in 2021", ElementKind.TIME_PERIOD, ElementStatus.VERIFIED),)
    )
    assert _period_never_contradicted("unemployment fell in 2021", innocent, "x") is None


def test_the_ledger_check_catches_a_self_contradicting_artifact() -> None:
    """Routing naming a bound measure while the ledger says none was bound."""
    planted = _Run(
        artifact=_Artifact(
            routing=(_Routing("Some Measure"),),
            ledger=(_Entry("rose", "no measure was bound for this element"),),
        )
    )
    assert _ledger_agrees_with_routing("a claim", planted, "x") is not None

    consistent = _Run(
        artifact=_Artifact(
            routing=(_Routing("Some Measure"),),
            ledger=(_Entry("rose", "the custodian was reached"),),
        )
    )
    assert _ledger_agrees_with_routing("a claim", consistent, "x") is None


def test_every_invariant_is_wired_in() -> None:
    """A check that exists but is not in the list runs on nothing."""
    names = {name for name, _ in INVARIANTS}
    assert {
        "render-survives",
        "period-never-contradicted",
        "ledger-agrees-with-routing",
    } <= names
    assert len(names) == len(INVARIANTS), "duplicate invariant name"


# ---------------------------------------------------------------------------
# The generator and the shrinker.
# ---------------------------------------------------------------------------


def test_generation_is_deterministic() -> None:
    assert [s.text for s in generate()] == [s.text for s in generate()]
    assert [s.text for s in sample(50, 3)] == [s.text for s in sample(50, 3)]
    assert [s.text for s in sample(50, 3)] != [s.text for s in sample(50, 4)]


def test_shapes_cover_the_combinations_hand_written_claims_miss() -> None:
    """The whole reason for generating rather than writing claims out."""
    texts = [s.text for s in generate()]
    assert any("in 2021" in t and "due to" in t for t in texts), "period plus cause"
    assert any(
        "highest" in t and "therefore" in t for t in texts
    ), "two triggers in sequence"
    assert any("in 1998" in t for t in texts), "a period outside every series"


def test_shrinking_reaches_the_smallest_failing_claim() -> None:
    """A twelve-word claim with one defect is a bad bug report."""
    full = next(
        s
        for s in generate()
        if "in 2021" in s.text and "due to governmental incompetence" in s.text
    )

    def fails(shape: Shape) -> bool:
        return "in 2021" in shape.text

    smallest = shrink(full, fails)
    assert "in 2021" in smallest.text
    assert "due to" not in smallest.text, "shrinking left an irrelevant slot in place"
    assert len(smallest.text) < len(full.text)
