"""The other fifteen §8 tables, exercised end to end.

Before this, `engine/store/schema.sql` declared claims, elements, discards,
derived_elements, verdicts, reconstructions, sweeps, routing_log and citations
and nothing wrote them. `test_store_persistence.py` covers `retrievals`,
which already had a writer; this file covers what `engine.store.writer` and
`engine.store.identity_writer` add.
"""

from __future__ import annotations

import pathlib
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.ingest.identity import ClaimantIdentity
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore
from engine.store.identity_writer import write_identity
from engine.store.writer import write_pack, write_verification

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"
CLAIM = "prices rose over the last three years due to governmental incompetence"


def _context() -> ClaimContext:
    return ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )


def _verify(store: RetrievalStore, claim: str = CLAIM):
    registry = PackRegistry.from_directory(PACKS)
    run = verify(claim, _context(), registry, build_fixture_custodians(), store)
    if run.decision and run.decision.pack:
        write_pack(store, run.decision.pack)
    write_verification(store, run)
    return run


def test_a_persisted_claim_round_trips_its_reconstruction(tmp_path) -> None:
    """The property §8 names: a stored reconstruction reads back unchanged."""
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store)
        conn = store.connection
        row = conn.execute(
            "SELECT text, element_set_hash, does_reconstruct, revision "
            "FROM reconstructions WHERE claim_id = ?",
            (str(run.claim_id),),
        ).fetchone()
        assert row is not None, "the reconstruction was not persisted"
        assert row[0] == run.artifact.to_dict()["reconstruction"]
        assert row[1] == run.artifact.element_set_hash
        assert bool(row[2]) == run.artifact.does_reconstruct
        assert row[3] == 1
    finally:
        store.close()


def test_element_set_hash_recomputes_from_persisted_rows(tmp_path) -> None:
    """§8: the hash "makes the pure-function property checkable after the
    fact". Checkable means re-derivable from stored columns alone, not just
    equal to a value the same process already computed in memory — the
    round-trip test above shows that much, and is not this property.

    Rebuilds the verified element set from nothing but `elements`, `measures`
    and `citations` rows and recomputes the hash the same way the pipeline
    did. `engine.verification.reconstruct.element_set_hash` folds in each
    element's id, span, kind, measure name and the retrieval id backing its
    figure (`reconstruct.py`) — every one of those is a column this test
    reads back rather than reuses from the in-memory run.
    """
    from decimal import Decimal

    from engine.elements import Element, ElementKind, ElementStatus, VerifiedElement
    from engine.figures import Figure
    from engine.ids import ClaimId, ElementId, RetrievalId
    from engine.spans import Span
    from engine.verification.reconstruct import element_set_hash

    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store)
        conn = store.connection

        stored_hash = conn.execute(
            "SELECT element_set_hash FROM reconstructions WHERE claim_id = ?",
            (str(run.claim_id),),
        ).fetchone()[0]

        element_rows = conn.execute(
            "SELECT id, fragment, kind, measure_id, source_span_start, source_span_end "
            "FROM elements WHERE claim_id = ? AND status = 'verified'",
            (str(run.claim_id),),
        ).fetchall()
        assert element_rows, "the claim used here must verify at least one element"

        last_retrieval_id = conn.execute(
            "SELECT retrieval_id FROM citations WHERE claim_id = ? ORDER BY position DESC LIMIT 1",
            (str(run.claim_id),),
        ).fetchone()[0]
        measure_name = conn.execute(
            "SELECT name FROM measures WHERE id = ?", (element_rows[0]["measure_id"],)
        ).fetchone()[0]

        figure = Figure(
            value=Decimal(0), unit="", reference_period="unused",
            retrieval_id=RetrievalId(last_retrieval_id),
        )
        rebuilt = frozenset(
            VerifiedElement(
                Element(
                    id=ElementId(row["id"]),
                    claim_id=ClaimId(str(run.claim_id)),
                    fragment=row["fragment"],
                    span=Span(row["source_span_start"], row["source_span_end"]),
                    kind=ElementKind(row["kind"]),
                    status=ElementStatus.VERIFIED,
                ),
                measure_name,
                figure,
            )
            for row in element_rows
        )
        assert element_set_hash(rebuilt) == stored_hash
    finally:
        store.close()


def test_discards_carry_the_element_they_belong_to(tmp_path) -> None:
    """The ledger's reason travels with a foreign key, not just prose."""
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store)
        rows = store.connection.execute(
            "SELECT discards.reason, elements.fragment, elements.status "
            "FROM discards JOIN elements ON elements.id = discards.element_id "
            "WHERE discards.reconstructed_claim_id = ?",
            (str(run.claim_id),),
        ).fetchall()
        assert len(rows) == len(run.artifact.ledger)
        assert {r[1] for r in rows} == {e.fragment for e in run.artifact.ledger}
        for reason, _fragment, status in rows:
            assert status != "verified"
            assert reason
    finally:
        store.close()


def test_sweep_rows_cite_a_retrieval_that_was_actually_stored(tmp_path) -> None:
    """§8: 'a sweep cell computed from anything other than a recorded
    retrieval is a fabricated comparison.' Persisted sweeps must keep citing
    one that exists."""
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store)
        assert run.artifact.sweep.ran
        conn = store.connection
        rows = conn.execute(
            "SELECT computed_from_retrieval_id FROM sweeps WHERE claim_id = ?",
            (str(run.claim_id),),
        ).fetchall()
        assert len(rows) == len(run.artifact.sweep.rows)
        for (retrieval_id,) in rows:
            assert conn.execute(
                "SELECT 1 FROM retrievals WHERE id = ?", (retrieval_id,)
            ).fetchone() is not None
    finally:
        store.close()


def test_citations_are_ordered_and_do_not_duplicate_a_reused_retrieval(tmp_path) -> None:
    """A claim's citation order is recorded; a shared retrieval is not two rows."""
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store)
        rows = store.connection.execute(
            "SELECT retrieval_id, position FROM citations WHERE claim_id = ? ORDER BY position",
            (str(run.claim_id),),
        ).fetchall()
        assert [r[0] for r in rows] == [str(c.id) for c in run.artifact.citations]
        assert [r[1] for r in rows] == list(range(len(rows)))
    finally:
        store.close()


def test_claimant_identity_is_absent_until_written_separately(tmp_path) -> None:
    """`write_verification` alone leaves `claimant_identity_id` NULL.

    The split is the point (§9.8.1): verification's own persistence has no
    way to populate this column, because it has no import path to
    :class:`~engine.ingest.identity.ClaimantIdentity` to construct one from.
    """
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store)
        row = store.connection.execute(
            "SELECT claimant_identity_id FROM claims WHERE id = ?", (str(run.claim_id),)
        ).fetchone()
        assert row[0] is None

        write_identity(store, run.claim_id, ClaimantIdentity(name="Jane Doe", venue="a rally"))
        row = store.connection.execute(
            "SELECT claimant_identity_id FROM claims WHERE id = ?", (str(run.claim_id),)
        ).fetchone()
        assert row[0] is not None
        identity_row = store.connection.execute(
            "SELECT name, venue FROM claimant_identity WHERE id = ?", (row[0],)
        ).fetchone()
        assert tuple(identity_row) == ("Jane Doe", "a rally")
    finally:
        store.close()


def test_an_anonymous_identity_writes_nothing(tmp_path) -> None:
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store)
        write_identity(store, run.claim_id, ClaimantIdentity())
        assert store.connection.execute("SELECT COUNT(*) FROM claimant_identity").fetchone()[0] == 0
        row = store.connection.execute(
            "SELECT claimant_identity_id FROM claims WHERE id = ?", (str(run.claim_id),)
        ).fetchone()
        assert row[0] is None
    finally:
        store.close()


def test_write_pack_is_idempotent_across_claims(tmp_path) -> None:
    """Many claims routed to one pack must not attempt to re-insert its rows."""
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        _verify(store, CLAIM)
        _verify(store, "prices are 3 percent")
        assert store.connection.execute("SELECT COUNT(*) FROM packs").fetchone()[0] == 1
        assert store.connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 2
    finally:
        store.close()


def test_an_unrouted_claim_still_persists_its_ledger(tmp_path) -> None:
    """§9.10: routed out is not gone silent, on disk any more than on screen."""
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        run = _verify(store, "you dont see a curve therfore the earth is flat")
        claim_row = store.connection.execute(
            "SELECT text FROM claims WHERE id = ?", (str(run.claim_id),)
        ).fetchone()
        assert claim_row is not None
        verdict_row = store.connection.execute(
            "SELECT label FROM verdicts WHERE claim_id = ?", (str(run.claim_id),)
        ).fetchone()
        assert verdict_row[0] == "insufficient_data"
        derived_rows = store.connection.execute(
            "SELECT text FROM derived_elements WHERE from_claim_id = ?", (str(run.claim_id),)
        ).fetchall()
        assert len(derived_rows) == len(run.artifact.derived)
    finally:
        store.close()
