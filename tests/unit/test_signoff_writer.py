"""The sign-off workflow: list what is proposed, decide, and persist it.

Before this, `cli/signoff.py` took `--proposed LABEL` on the command line and
handed back a `SignedVerdict` nobody stored — a demonstration of the gate,
not a way to actually sign off a claim verified earlier. This exercises the
store-backed path end to end: `engine.store.writer` persists a proposal,
`engine.store.signoff_writer` lists and loads it, `engine.signoff` decides,
and the decision is written back.
"""

from __future__ import annotations

import pathlib
from datetime import date

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.elements import GateState
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.signoff import GateViolation, amend, confirm, reject
from engine.store.events import RetrievalStore
from engine.store.signoff_writer import NoOpenVerdict, list_proposed, load_proposed, write_signoff
from engine.store.writer import write_pack, write_verification
from engine.verification.claim_verdict import Verdict

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"
CLAIM = "prices rose over the last three years due to governmental incompetence"


def _context() -> ClaimContext:
    return ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"), language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )


def _verify_and_persist(store: RetrievalStore, claim: str = CLAIM):
    registry = PackRegistry.from_directory(PACKS)
    run = verify(claim, _context(), registry, build_fixture_custodians(), store)
    if run.decision and run.decision.pack:
        write_pack(store, run.decision.pack)
    write_verification(store, run)
    return run


@pytest.fixture
def store(tmp_path):
    s = RetrievalStore(str(tmp_path / "store.db"))
    yield s
    s.close()


def test_a_freshly_verified_claim_is_listed_as_proposed(store) -> None:
    run = _verify_and_persist(store)
    rows = list_proposed(store)
    assert [r["claim_id"] for r in rows] == [str(run.claim_id)]
    assert rows[0]["label"] == run.artifact.verdict.label.value


def test_load_proposed_matches_what_the_pipeline_actually_proposed(store) -> None:
    run = _verify_and_persist(store)
    loaded = load_proposed(store, str(run.claim_id))
    assert loaded is not None
    assert loaded.label is run.artifact.verdict.label
    assert loaded.rationale == run.artifact.verdict.rationale
    assert loaded.state is GateState.PROPOSED


def test_confirming_removes_the_claim_from_the_proposed_list(store) -> None:
    run = _verify_and_persist(store)
    claim_id = str(run.claim_id)
    proposal = load_proposed(store, claim_id)

    signed = confirm(proposal, "a reviewer")
    write_signoff(store, claim_id, signed)

    assert load_proposed(store, claim_id) is None
    assert list_proposed(store) == []


def test_confirming_persists_the_reviewer_and_state(store) -> None:
    run = _verify_and_persist(store)
    claim_id = str(run.claim_id)
    signed = confirm(load_proposed(store, claim_id), "a reviewer")
    write_signoff(store, claim_id, signed)

    row = store.connection.execute(
        "SELECT label, state, confirmed_by, confirmed_at, valid_until "
        "FROM verdicts WHERE claim_id = ? AND valid_until IS NULL",
        (claim_id,),
    ).fetchone()
    assert row["label"] == run.artifact.verdict.label.value
    assert row["state"] == "confirmed"
    assert row["confirmed_by"] == "a reviewer"
    assert row["confirmed_at"] is not None
    assert row["valid_until"] is None


def test_the_proposed_row_is_closed_not_deleted(store) -> None:
    """§8: verdicts are events with validity windows, not overwritten facts."""
    run = _verify_and_persist(store)
    claim_id = str(run.claim_id)
    signed = confirm(load_proposed(store, claim_id), "a reviewer")
    write_signoff(store, claim_id, signed)

    rows = store.connection.execute(
        "SELECT state, valid_until FROM verdicts WHERE claim_id = ? ORDER BY rowid", (claim_id,)
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["state"] == "proposed"
    assert rows[0]["valid_until"] is not None
    assert rows[1]["state"] == "confirmed"
    assert rows[1]["valid_until"] is None


def test_amending_records_the_original_label_and_rationale(store) -> None:
    run = _verify_and_persist(store)
    claim_id = str(run.claim_id)
    signed = amend(
        load_proposed(store, claim_id), Verdict.FALSE, "the sweep flips it", "a reviewer",
    )
    write_signoff(store, claim_id, signed)

    row = store.connection.execute(
        "SELECT label, amended_from_label, amendment_rationale, rationale "
        "FROM verdicts WHERE claim_id = ? AND valid_until IS NULL",
        (claim_id,),
    ).fetchone()
    assert row["label"] == "false"
    assert row["amended_from_label"] == run.artifact.verdict.label.value
    assert row["amendment_rationale"] == "the sweep flips it"
    # The underlying evidence rationale is retained, not replaced by the
    # amendment's reason -- they answer different questions (why the record
    # says what it says, versus why a human overrode the label).
    assert row["rationale"] == run.artifact.verdict.rationale


def test_a_decided_claim_cannot_be_signed_off_again(store) -> None:
    """§9.1: a decided verdict cannot be revisited in place."""
    run = _verify_and_persist(store)
    claim_id = str(run.claim_id)
    signed = confirm(load_proposed(store, claim_id), "a reviewer")
    write_signoff(store, claim_id, signed)

    assert load_proposed(store, claim_id) is None


def test_write_signoff_refuses_a_claim_with_no_open_verdict(store) -> None:
    with pytest.raises(NoOpenVerdict):
        write_signoff(store, "not-a-real-claim-id", confirm(
            load_proposed_dummy(), "a reviewer"
        ))


def load_proposed_dummy():
    from engine.verification.claim_verdict import ProposedVerdict
    return ProposedVerdict(Verdict.ACCURATE, "irrelevant")


def test_an_amendment_that_introduces_a_figure_still_fails_before_persistence(store) -> None:
    """AC-10: a reviewer cannot introduce a figure any more than the pipeline
    can. This must fail before write_signoff is ever called -- checked here
    by confirming the store gained no second row."""
    run = _verify_and_persist(store)
    claim_id = str(run.claim_id)
    with pytest.raises(GateViolation):
        amend(load_proposed(store, claim_id), Verdict.FALSE, "it is 12 percent higher", "reviewer")

    rows = store.connection.execute(
        "SELECT COUNT(*) FROM verdicts WHERE claim_id = ?", (claim_id,)
    ).fetchone()[0]
    assert rows == 1, "a rejected amendment must not have written a second row"


def test_rejecting_persists_no_label_change_but_a_terminal_state(store) -> None:
    run = _verify_and_persist(store)
    claim_id = str(run.claim_id)
    signed = reject(load_proposed(store, claim_id), "a reviewer")
    write_signoff(store, claim_id, signed)

    row = store.connection.execute(
        "SELECT state, label FROM verdicts WHERE claim_id = ? AND valid_until IS NULL",
        (claim_id,),
    ).fetchone()
    assert row["state"] == "rejected"
    assert row["label"] == run.artifact.verdict.label.value
