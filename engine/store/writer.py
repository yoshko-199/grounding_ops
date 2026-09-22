"""Persist a verification run — the composition root's job.

Spec §8 declares sixteen tables (`engine/store/schema.sql`).  Before this
module, exactly one of them was ever written: `retrievals`, from inside
`engine.verification.retrieve`.  The other fifteen — claims, elements,
discards, derived_elements, verdicts, reconstructions, sweeps, routing_log,
and the reference tables beneath them — had columns and nothing that wrote
them, so a claim's elements, verdict, reconstruction and sweep died with the
process that produced them.  This module is what writes them.

Deliberately not in `engine.verification`.  Persisting an artifact is
bookkeeping that happens *after* Stage 11, not a verification rule, and
keeping it out of that package means adding a table here can never touch the
reachability guarantees `tests/conformance/_graph.py` polices — see
`tests/conformance/test_store_writer_isolation.py`.

Claimant identity is not written here.  See `engine.store.identity_writer`
for why that is a separate module rather than one function among these.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from engine.elements import ElementStatus
from engine.packs.schema import Pack
from engine.pipeline import VerificationRun
from engine.store.events import RetrievalStore


def write_pack(store: RetrievalStore, pack: Pack, *, now: datetime | None = None) -> None:
    """Record the pack, its custodians, and its measures.

    Idempotent (`INSERT OR IGNORE`) because a pack is loaded once and cited by
    every claim routed to it — the table records that the pack existed at
    verification time, not a fact scoped to one claim, so re-verifying a
    hundred claims against the same pack must not attempt a hundred inserts of
    the same row.
    """
    now = now or datetime.now(timezone.utc)
    conn = store.connection
    pack_id = str(pack.jurisdiction)
    conn.execute(
        "INSERT OR IGNORE INTO packs (id, jurisdiction_id, version, maintainer, loaded_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (pack_id, str(pack.jurisdiction), pack.version, pack.header.maintainer, now.isoformat()),
    )
    for custodian in pack.custodians:
        conn.execute(
            "INSERT OR IGNORE INTO custodians "
            "(id, pack_id, name, mandate, cadence, revision_policy, access_method, integrity_notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                custodian.id, pack_id, custodian.name, custodian.mandate,
                custodian.cadence, custodian.revision_policy, custodian.access_method,
                custodian.integrity_annotation,
            ),
        )
    for measure in pack.measures:
        conn.execute(
            "INSERT OR IGNORE INTO measures "
            "(id, pack_id, name, definition, custodian_id, unit, published_precision, discrete) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                measure.id, pack_id, measure.name, measure.definition, measure.custodian_id,
                measure.unit, measure.published_precision, int(measure.discrete),
            ),
        )
    conn.commit()


def write_verification(
    store: RetrievalStore, run: VerificationRun, *, now: datetime | None = None
) -> None:
    """Persist everything one call to :func:`engine.pipeline.verify` produced.

    Writes `claim_context`, `claims`, `elements`, `discards`,
    `derived_elements`, `verdicts`, `reconstructions`, `sweeps`, `citations`
    and `routing_log`.  Does not write `claimant_identity` — see the module
    docstring — and does not write `packs`/`custodians`/`measures`; call
    :func:`write_pack` for those when a pack was actually loaded.

    One transaction.  A verification run is one indivisible unit exactly as
    its rendered artifact is (§7.1); a partial write on failure would leave a
    claim with elements but no verdict, which is a state nothing downstream
    expects to see.
    """
    now = now or datetime.now(timezone.utc)
    conn = store.connection
    claim_id = str(run.claim_id)
    context = run.context

    context_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO claim_context (id, jurisdiction_hint, language, stated_at) "
        "VALUES (?, ?, ?, ?)",
        (
            context_id,
            str(context.jurisdiction) if context.jurisdiction else None,
            str(context.language),
            context.stated_at.isoformat(),
        ),
    )
    conn.execute(
        "INSERT INTO claims (id, text, stated_at, type, claim_context_id, claimant_identity_id) "
        "VALUES (?, ?, ?, 'original', ?, NULL)",
        (claim_id, run.artifact.claim_text, context.stated_at.isoformat(), context_id),
    )

    # Every element on a run shares one measure_id, because routing binds the
    # *claim* to a measure (`engine.verification.route`), not each element
    # individually — `Element.measure_id` itself is never populated by the
    # pipeline today. `decision.measure` is where that binding actually
    # lives, so it is where this column's value comes from, for every row.
    bound_measure_id = (
        run.decision.measure.id if run.decision and run.decision.measure else None
    )
    for element in run.elements:
        conn.execute(
            "INSERT INTO elements "
            "(id, claim_id, fragment, kind, measure_id, status, tolerance_band, "
            "continuity_status, source_span_start, source_span_end) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(element.id), claim_id, element.fragment, element.kind.value,
                bound_measure_id,
                element.status.value if element.status else None,
                element.tolerance_band.value if element.tolerance_band else None,
                element.continuity_status.value if element.continuity_status else None,
                element.span.start, element.span.end,
            ),
        )
        if element.status is not None and element.status is not ElementStatus.VERIFIED:
            conn.execute(
                "INSERT INTO discards (id, reconstructed_claim_id, element_id, reason) "
                "VALUES (?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), claim_id, str(element.id),
                    run.discard_reasons.get(element.id.value, ""),
                ),
            )

    for derived in run.derived:
        conn.execute(
            "INSERT INTO derived_elements "
            "(id, from_claim_id, text, tag, state, source_span_start, source_span_end, "
            "derivation_operation, confirmed_by, confirmed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(derived.id), claim_id, derived.text, derived.tag.value, derived.state.value,
                derived.span.start, derived.span.end, derived.operation.value,
                derived.confirmed_by, derived.confirmed_at.isoformat() if derived.confirmed_at else None,
            ),
        )

    verdict = run.artifact.verdict
    conn.execute(
        "INSERT INTO verdicts "
        "(id, claim_id, label, rationale, valid_from, valid_until, state, proposed_at, "
        "confirmed_by, confirmed_at, amended_from_label, amendment_rationale) "
        "VALUES (?, ?, ?, ?, ?, NULL, ?, ?, NULL, NULL, NULL, NULL)",
        (
            str(uuid.uuid4()), claim_id, verdict.label.value, verdict.rationale,
            context.stated_at.isoformat(), verdict.state.value, now.isoformat(),
        ),
    )

    conn.execute(
        "INSERT INTO reconstructions "
        "(id, claim_id, revision, text, element_set_hash, derived_at, "
        "triggered_by_retrieval_id, does_reconstruct) "
        "VALUES (?, ?, 1, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()), claim_id,
            run.artifact.to_dict()["reconstruction"] or "",
            run.artifact.element_set_hash, now.isoformat(),
            str(run.artifact.citations[-1].id) if run.artifact.citations else None,
            int(run.artifact.does_reconstruct),
        ),
    )

    for position, retrieval in enumerate(run.artifact.citations):
        conn.execute(
            "INSERT OR IGNORE INTO citations (claim_id, retrieval_id, position) VALUES (?, ?, ?)",
            (claim_id, str(retrieval.id), position),
        )

    if run.artifact.sweep.ran:
        for row in run.artifact.sweep.rows:
            conn.execute(
                "INSERT INTO sweeps "
                "(id, claim_id, test, alternative, conclusion_holds, computed_from_retrieval_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), claim_id, row.test.value, row.alternative,
                    int(row.conclusion_holds), str(row.computed_from_retrieval_id),
                ),
            )

    decision = run.decision
    if decision is not None:
        for element in run.elements:
            conn.execute(
                "INSERT INTO routing_log "
                "(id, element_id, custodian_id, rationale, alternatives_considered, "
                "pack_id, pack_version, jurisdiction_rule) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), str(element.id), decision.custodian_id,
                    decision.rationale, json.dumps(list(decision.alternatives_considered)),
                    str(decision.jurisdiction) if decision.jurisdiction else None,
                    decision.pack_version, decision.jurisdiction_rule.value,
                ),
            )

    conn.commit()
