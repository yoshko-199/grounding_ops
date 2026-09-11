"""AC-10, extended to the persistence side of sign-off.

`engine.signoff` must not reach the store, the packs, or the sweep
(`tests/conformance/test_ac10.py::test_the_signoff_module_cannot_reach_the_store_or_the_packs`).
`engine.store.signoff_writer` is the new module that closes the gap that
constraint leaves open: something has to persist a `SignedVerdict`, and if
that something lived inside `engine.signoff`, the module would gain exactly
the import path AC-10 forbids, just to do bookkeeping.

Two things are worth checking rather than assuming: that the writer itself
stays out of `engine.verification`'s reach, on the same footing as the other
two composition-root writers (`tests/conformance/test_store_writer_isolation.py`),
and that adding it did not — as a side effect of importing
`engine.signoff.SignedVerdict` for its type — give `engine.signoff` a path
back into the store. Import graphs are directed; importing A from B says
nothing about whether B is reachable from A, and that is exactly the
direction this second check is for.
"""

from __future__ import annotations

import pytest

from tests.conformance._graph import modules_under, reachable

SIGNOFF_WRITER_MODULE = "engine.store.signoff_writer"


@pytest.mark.parametrize("module", modules_under("engine.verification"))
def test_no_verification_module_reaches_the_signoff_writer(module: str) -> None:
    reached = reachable(module)
    assert SIGNOFF_WRITER_MODULE not in reached, (
        f"{module} can reach {SIGNOFF_WRITER_MODULE}. Persisting a sign-off "
        "decision is composition-root bookkeeping, and a verification module "
        "able to reach it is one bug away from writing a decision instead of "
        "only computing one."
    )


def test_the_signoff_module_still_cannot_reach_the_store() -> None:
    """The direction that matters: signoff_writer imports engine.signoff for
    its SignedVerdict type, not the other way round."""
    reached = reachable("engine.signoff")
    for module in ("engine.store.events", "engine.store.writer", SIGNOFF_WRITER_MODULE):
        assert module not in reached, (
            f"engine.signoff can now reach {module}. Adding the sign-off "
            "writer must not have given the gate itself a path to persistence "
            "— that is precisely the reachability AC-10 forbids."
        )
