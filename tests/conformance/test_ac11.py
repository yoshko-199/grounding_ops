"""AC-11 — Sweep coverage.

Constraint: spec §9.3.  An unrunnable sweep never reads as a pass.

AC-11's note: "Without the cap, the weakest-evidence claims would receive the
strongest label — the sweep's silence would read as its endorsement."
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from engine.elements import Element, ElementKind, ElementStatus
from engine.ids import ClaimId, ElementId
from engine.spans import Span
from engine.verification import retrieve, sweep
from engine.verification.claim_verdict import Verdict, evaluate
from engine.verification.sweep import SweepResult, SweepTest

CLAIM = "prices rose over the last three years"


def _verified_element() -> Element:
    return Element(
        id=ElementId(),
        claim_id=ClaimId(),
        fragment="rose",
        span=Span(7, 11),
        kind=ElementKind.DIRECTION,
        status=ElementStatus.VERIFIED,
    )


def _pull(pack, adapters, store, measure_id: str):
    measure = pack.measure(measure_id)
    custodian = pack.custodian(measure.custodian_id)
    return measure, retrieve.pull(measure, custodian, adapters[measure.custodian_id], store)


# -- the cap ---------------------------------------------------------------


def test_a_single_observation_series_cannot_sweep(pack, adapters, store) -> None:
    measure, pull = _pull(pack, adapters, store, "sparse_gauge")
    result = sweep.run(measure, pull.retrievals, claimed_rise=True)
    assert not result.ran
    assert "fewer than two observations" in result.reason_not_run


def test_an_unrunnable_sweep_caps_at_indeterminate(pack, adapters, store) -> None:
    """The criterion's core. Every element verifies and the label is still capped."""
    measure, pull = _pull(pack, adapters, store, "sparse_gauge")
    result = sweep.run(measure, pull.retrievals, claimed_rise=True)

    verdict = evaluate(
        (_verified_element(),), result, routed=True, reconstructs=True
    )
    assert verdict.label is Verdict.INDETERMINATE
    assert verdict.label is not Verdict.ACCURATE
    assert verdict.capped
    assert verdict.cap_reason


def test_a_measure_with_no_declared_alternatives_cannot_sweep(pack, adapters, store) -> None:
    measure, pull = _pull(pack, adapters, store, "price_index")
    stripped = replace(measure, admissible_baselines=(), admissible_windows=())
    assert not stripped.sweep_can_run
    result = sweep.run(stripped, pull.retrievals, claimed_rise=True)
    assert not result.ran
    assert "no admissible baselines or windows" in result.reason_not_run


def test_a_claim_with_no_direction_does_not_silently_pass(pack, adapters, store) -> None:
    """A narrower sweep, reported as narrower rather than as clean."""
    measure, pull = _pull(pack, adapters, store, "price_index")
    result = sweep.run(measure, pull.retrievals, claimed_rise=None)
    assert not result.ran
    verdict = evaluate((_verified_element(),), result, routed=True, reconstructs=True)
    assert verdict.label is Verdict.INDETERMINATE


# -- the sweep when it does run --------------------------------------------


def test_the_sweep_runs_over_declared_alternatives_only(pack, adapters, store) -> None:
    """"the alternatives are declared once, per measure, in a versioned pack"."""
    measure, pull = _pull(pack, adapters, store, "price_index")
    result = sweep.run(measure, pull.retrievals, claimed_rise=True)
    assert result.ran

    baselines = {r.alternative for r in result.rows if r.test is SweepTest.BASELINE}
    windows = {r.alternative for r in result.rows if r.test is SweepTest.WINDOW}
    assert baselines <= set(measure.admissible_baselines)
    assert windows <= set(measure.admissible_windows)


def test_every_flip_table_cell_cites_a_retrieval(pack, adapters, store) -> None:
    """§8 — "a sweep cell computed from anything other than a recorded
    retrieval is a fabricated comparison"."""
    measure, pull = _pull(pack, adapters, store, "price_index")
    result = sweep.run(measure, pull.retrievals, claimed_rise=True)
    recorded = {r.id.value for r in pull.retrievals}
    assert result.rows
    for row in result.rows:
        assert row.computed_from_retrieval_id is not None
        assert row.computed_from_retrieval_id.value in recorded


def test_a_cherry_picked_window_flips_and_yields_misleading(pack, adapters, store) -> None:
    """The fixture price series rises over twelve months and falls over three.

    A claim of "prices rose" is true on the long window and false on the short
    one, which is the selective-window mechanism §9.3 exists to catch.
    """
    measure, pull = _pull(pack, adapters, store, "price_index")
    result = sweep.run(measure, pull.retrievals, claimed_rise=True)
    assert result.ran
    assert result.conclusion_flips

    flipped_windows = {
        r.alternative for r in result.flipped_rows if r.test is SweepTest.WINDOW
    }
    assert "3m" in flipped_windows

    verdict = evaluate((_verified_element(),), result, routed=True, reconstructs=True)
    assert verdict.label is Verdict.MISLEADING
    assert "flip table" in verdict.rationale


def test_bounded_omission_covers_only_discards_and_custodian_caveats(
    pack, adapters, store
) -> None:
    """§9.3 test 4 admits those two sources and "Nothing else"."""
    measure, pull = _pull(pack, adapters, store, "price_index")
    discarded = (
        Element(
            id=ElementId(),
            claim_id=ClaimId(),
            fragment="due to",
            span=Span(0, 6),
            kind=ElementKind.CAUSAL,
            status=ElementStatus.OUT_OF_SCOPE,
        ),
    )
    result = sweep.run(
        measure, pull.retrievals, claimed_rise=True, discarded=discarded
    )
    omission = [r for r in result.rows if r.test is SweepTest.BOUNDED_OMISSION]
    assert omission
    assert any("due to" in r.alternative for r in omission)
    for row in omission:
        assert "discarded element" in row.alternative or "custodian caveat" in row.alternative


def test_sweep_takes_no_per_claim_alternative_set() -> None:
    """The comparison set cannot be supplied by the caller.

    If it could, the sweep "would test only the alternatives that flatter the
    claim, and would systematically clear exactly the cherry-picked claims it
    exists to catch."
    """
    import inspect

    parameters = set(inspect.signature(sweep.run).parameters)
    for forbidden in ("baselines", "windows", "alternatives", "comparison_set"):
        assert forbidden not in parameters


# -- the other cap, §9.5 ----------------------------------------------------


def test_an_unlinked_break_blocks_accurate(pack, adapters, store) -> None:
    from engine.elements import ContinuityStatus

    element = replace(
        _verified_element(), continuity_status=ContinuityStatus.UNLINKED_BREAK
    )
    clean = SweepResult(rows=(), ran=True)
    verdict = evaluate((element,), clean, routed=True, reconstructs=True)
    assert verdict.label is Verdict.INDETERMINATE
    assert verdict.label is not Verdict.ACCURATE


def test_insufficient_data_is_not_an_error_state() -> None:
    """§7.5 — "a legitimate outcome, not an error state"."""
    verdict = evaluate((), SweepResult(), routed=False, reconstructs=False)
    assert verdict.label is Verdict.INSUFFICIENT_DATA
    assert "not a failure" in verdict.rationale


def test_a_verdict_leaves_the_pipeline_proposed_not_final() -> None:
    """§9.1 — the gate is on the claim-level verdict and only there."""
    verdict = evaluate((), SweepResult(), routed=False, reconstructs=False)
    assert not verdict.is_final
    assert not verdict.exportable
