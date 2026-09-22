"""Persist a claim's claimant identity — separately, on purpose.

Spec §9.8.1 splits provenance into a crossing half and a non-crossing half.
`engine.ingest.split` is where both halves exist at once, at Stage 0; nothing
downstream of it may import `engine.ingest.identity`, and AC-6 asserts that by
static analysis over every module under `engine.verification`.

`engine.store.writer` writes everything else a verification run produces, and
it is not that module.  If it imported :class:`~engine.ingest.identity.ClaimantIdentity`
to write this one table, it would become a second thing that must never be
reachable from verification — and unlike `engine.verification`, nobody
guards `engine.store` with a parametrised reachability test today.  Keeping
identity in a module of its own, imported by nothing but the CLI composition
root, means the guarantee holds by construction rather than by remembering
not to add an import to `writer.py` later.

See `tests/conformance/test_store_writer_isolation.py`, which asserts this
module is unreachable from `engine.verification` the same way
`engine.ingest.identity` itself is.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from engine.ids import ClaimId
from engine.ingest.identity import ClaimantIdentity
from engine.store.events import RetrievalStore


def write_identity(
    store: RetrievalStore,
    claim_id: ClaimId,
    identity: ClaimantIdentity,
    *,
    now: datetime | None = None,
) -> None:
    """Record ``identity`` and point the claim row at it.

    A no-op for an anonymous identity: there is nothing to retain, and an
    empty row would claim attribution was supplied when it was not.

    The claim row is expected to already exist — :func:`engine.store.writer.write_verification`
    creates it with ``claimant_identity_id`` left ``NULL`` — because identity
    is known at Stage 0, before verification runs, while the claim's own
    persistence happens after. Updating rather than inserting-with is what
    keeps the two writers independent instead of one needing the other's
    output as an argument.
    """
    if identity.is_anonymous:
        return
    now = now or datetime.now(timezone.utc)
    conn = store.connection
    identity_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO claimant_identity (id, name, affiliation, role, venue, audience) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (identity_id, identity.name, identity.affiliation, identity.role,
         identity.venue, identity.audience),
    )
    conn.execute(
        "UPDATE claims SET claimant_identity_id = ? WHERE id = ?",
        (identity_id, str(claim_id)),
    )
    conn.commit()
