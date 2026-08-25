"""AC-10 — Gate integrity.

Constraint: spec §9.1.  Sign-off changes the claim-level label and nothing
else.

AC-10's note: "An unconstrained human gate is itself a laundering vector, and
a more credible one than the pipeline — it arrives wearing the authority of
review."
"""

from __future__ import annotations

import inspect

import pytest

from engine import signoff
from engine.elements import GateState
from engine.signoff import GateViolation, amend, confirm, expire, reject
from engine.verification.claim_verdict import ProposedVerdict, Verdict

PROPOSAL = ProposedVerdict(Verdict.MISLEADING, "the flip table records where it fails")


def test_the_gate_has_no_parameter_reaching_the_evidence() -> None:
    """"Attempt, as a signing-off reviewer, to modify: an element status, a
    retrieval record, the discard ledger, a flip-table row, a routing
    decision, and a pack. Assert every attempt fails."

    Here there is nothing to attempt: the API accepts a label and a rationale
    and exposes no route to anything beneath the verdict.
    """
    reachable = set()
    for fn in (confirm, amend, reject, expire):
        reachable |= set(inspect.signature(fn).parameters)
    for forbidden in (
        "element", "elements", "status", "retrieval", "retrievals", "ledger",
        "discard", "flip_table", "sweep", "routing", "pack", "custodian",
    ):
        assert forbidden not in reachable, f"the gate can reach {forbidden!r}"


def test_the_signoff_module_cannot_reach_the_store_or_the_packs() -> None:
    from tests.conformance._graph import reachable

    reached = reachable("engine.signoff")
    for module in ("engine.store.events", "engine.packs.loader", "engine.packs.registry"):
        assert module not in reached, (
            f"engine.signoff can reach {module}, so a reviewer could reach past the "
            "verdict to the evidence beneath it (§9.1 rule 2)"
        )


def test_confirming_keeps_the_proposed_label() -> None:
    signed = confirm(PROPOSAL, "reviewer")
    assert signed.label is PROPOSAL.label
    assert signed.state is GateState.CONFIRMED
    assert signed.exportable


def test_amending_retains_the_proposal() -> None:
    """§9.1 rule 1 — "a gate whose history can be edited is not a gate"."""
    signed = amend(PROPOSAL, Verdict.INDETERMINATE, "the sweep is thinner than it looks", "reviewer")
    assert signed.label is Verdict.INDETERMINATE
    assert signed.proposal is PROPOSAL
    assert signed.amended_from_label is Verdict.MISLEADING
    assert signed.amendment_rationale


def test_amending_requires_a_rationale() -> None:
    with pytest.raises(GateViolation, match="amendment_rationale"):
        amend(PROPOSAL, Verdict.INDETERMINATE, "   ", "reviewer")


def test_a_rationale_introducing_a_figure_fails_exactly_as_pipeline_output_would() -> None:
    """§9.1 rule 3 — §3 binds the reviewer exactly as it binds the pipeline."""
    with pytest.raises(GateViolation, match="figure"):
        amend(
            PROPOSAL,
            Verdict.ACCURATE,
            "the series actually rose 4.2 percent over the period",
            "reviewer",
        )


def test_a_proposed_verdict_cannot_export_as_final() -> None:
    assert not PROPOSAL.exportable
    assert not PROPOSAL.is_final


def test_a_proposed_verdict_renders_visibly_marked(registry, context, adapters, store) -> None:
    from engine.pipeline import verify

    artifact = verify("prices rose in 2021", context, registry, adapters, store).artifact
    assert "UNCONFIRMED" in artifact.render()
    assert artifact.to_dict()["unconfirmed"] is True


def test_a_decided_verdict_cannot_be_revisited_in_place() -> None:
    signed = confirm(PROPOSAL, "reviewer")
    already = ProposedVerdict(signed.label, PROPOSAL.rationale, state=GateState.CONFIRMED)
    with pytest.raises(GateViolation, match="already"):
        confirm(already, "another reviewer")


def test_signoff_requires_a_named_reviewer() -> None:
    with pytest.raises(GateViolation, match="named reviewer"):
        confirm(PROPOSAL, "  ")


def test_amend_refuses_a_no_op() -> None:
    with pytest.raises(GateViolation, match="use confirm"):
        amend(PROPOSAL, Verdict.MISLEADING, "no change", "reviewer")


def test_expiry_is_not_a_failure_state() -> None:
    """§9.1 rule 5 — "the record moved on before a person got to it"."""
    expired = expire(PROPOSAL)
    assert expired.state is GateState.EXPIRED
    assert not expired.exportable


def test_rejecting_publishes_no_label() -> None:
    rejected = reject(PROPOSAL, "reviewer")
    assert rejected.state is GateState.REJECTED
    assert not rejected.exportable


def test_the_gate_cannot_alter_element_statuses() -> None:
    """§6.1 — element statuses "are not subject to the sign-off gate"."""
    public = {name for name in dir(signoff) if not name.startswith("_")}
    for mutator in ("set_status", "update_element", "override", "force"):
        assert mutator not in public
