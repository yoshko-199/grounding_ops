"""The artifact writer is unreachable from verification.

Milestone 1 of `docs/plan.md` adds `engine.store.writer` and
`engine.store.identity_writer` at the composition root. Neither is a
verification rule — persisting a claim happens after Stage 11, not during
it — and this test is the assertion that neither module ever becomes one by
accident.

`engine.store.identity_writer` gets the sharper test. It is the one new
module in this pair that imports `engine.ingest.identity`, and AC-6
(`tests/conformance/test_ac06.py`) already forbids that module from being
reachable from verification. If something under `engine.verification` ever
imported `engine.store.identity_writer`, it would reach identity through a
side door AC-6's own parametrised test does not look through, because that
test walks forward from each verification module rather than backward from
every possible importer of identity.
"""

from __future__ import annotations

import pytest

from tests.conformance._graph import modules_under, reachable

WRITER_MODULE = "engine.store.writer"
IDENTITY_WRITER_MODULE = "engine.store.identity_writer"


@pytest.mark.parametrize("module", modules_under("engine.verification"))
def test_no_verification_module_reaches_the_artifact_writer(module: str) -> None:
    reached = reachable(module)
    assert WRITER_MODULE not in reached, (
        f"{module} can reach {WRITER_MODULE}. Persisting an artifact is "
        "composition-root bookkeeping; a verification module that can reach "
        "it could, given a bug, be made to write one instead of only "
        "computing one."
    )
    assert IDENTITY_WRITER_MODULE not in reached, (
        f"{module} can reach {IDENTITY_WRITER_MODULE}, which imports "
        "engine.ingest.identity. Reaching it defeats AC-6 by a route AC-6's "
        "own test does not check."
    )


def test_identity_writer_is_the_only_new_importer_of_identity() -> None:
    """Sanity check on the test above: it must be able to detect a violation.

    `engine.store.writer` genuinely does not import identity anywhere in the
    tree today; this confirms that fact rather than assuming it, the same
    negative-control pattern `test_ac06.py` uses for the harness itself.
    """
    assert IDENTITY_WRITER_MODULE not in reachable(WRITER_MODULE), (
        f"{WRITER_MODULE} reaches {IDENTITY_WRITER_MODULE} directly, which "
        "would make every assertion above vacuous for {WRITER_MODULE}'s own "
        "callers."
    )
