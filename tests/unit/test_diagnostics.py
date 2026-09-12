"""Diagnostics surfacing — docs/plan.md's trial-hardening milestone.

`PullOutcome.diagnostic` existed, was populated, and nothing ever printed
it. `decision.rationale` is already visible for a routed claim (the ROUTING
section) and for the two routing failures that fold it into the verdict
(`CONTESTED_BY_DEFINITION`, `NO_MEASURE`) -- but `NO_ROUTING_RULE`'s
rationale ("a pack defect to be filed") was, by design, kept out of the
verdict and had nowhere else to go. `--diagnostics` is the somewhere else,
and it must never be the artifact itself: a proxy status code or exception
text has no business inside a verified record, and a numeral in it would
fail AC-7's render-time scan if it ever reached `Artifact.render()`.
"""

from __future__ import annotations

import pathlib
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"
CLAIM = "prices rose over the last three years due to governmental incompetence"


def _context() -> ClaimContext:
    return ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"), language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )


def test_a_routed_claim_carries_no_pull_diagnostic() -> None:
    """The common case: nothing went wrong, so there is nothing to surface."""
    store = RetrievalStore(":memory:")
    try:
        registry = PackRegistry.from_directory(PACKS)
        run = verify(CLAIM, _context(), registry, build_fixture_custodians(), store)
        assert run.diagnostic == ""
        assert run.decision is not None and run.decision.rationale
    finally:
        store.close()


def test_an_unreachable_custodian_s_diagnostic_survives_to_verificationrun() -> None:
    """The technical detail behind CustodianUnreachable reaches VerificationRun
    -- where it did not exist as a field until this milestone -- without ever
    reaching the artifact."""
    store = RetrievalStore(":memory:")
    try:
        registry = PackRegistry.from_directory(PACKS)
        adapters = build_fixture_custodians()
        adapters["zzstat"].unreachable = True

        run = verify(CLAIM, _context(), registry, adapters, store)

        assert run.diagnostic == "custodian 'zzstat' unreachable: fixture set to unreachable"
        # The artifact itself must still carry nothing from it: no numeral,
        # and not even the diagnostic's own prose.
        rendered = run.artifact.render()
        assert "fixture set to unreachable" not in rendered
    finally:
        store.close()


def test_an_unrouted_claim_carries_no_pull_diagnostic_either() -> None:
    """No pull was ever attempted for a claim that never routed, so there is
    nothing to surface -- diagnostic stays the type's own default."""
    store = RetrievalStore(":memory:")
    try:
        registry = PackRegistry.from_directory(PACKS)
        run = verify("the earth is flat", _context(), registry, build_fixture_custodians(), store)
        assert run.diagnostic == ""
    finally:
        store.close()


# -- cli/verify.py --diagnostics --------------------------------------------


def test_diagnostics_flag_prints_the_routing_rationale(tmp_path, capsys) -> None:
    from cli.verify import main

    assert main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:",
         "--diagnostics"]
    ) == 0
    out = capsys.readouterr().out
    assert "DIAGNOSTICS (operator information, not part of the verified record)" in out
    assert "routing:" in out


def test_diagnostics_flag_is_silent_by_default(tmp_path, capsys) -> None:
    from cli.verify import main

    assert main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:"]
    ) == 0
    assert "DIAGNOSTICS" not in capsys.readouterr().out


def test_diagnostics_reach_the_json_payload_as_a_sibling_key(tmp_path, capsys) -> None:
    import json

    from cli.verify import main

    assert main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:",
         "--json", "--diagnostics"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "diagnostics" in payload
    assert "routing_rationale" in payload["diagnostics"]
    assert "pull_diagnostic" in payload["diagnostics"]
    # Not nested inside anything Artifact.to_dict() produced.
    assert "diagnostics" not in payload.get("verdict", {})


def test_json_payload_carries_no_diagnostics_key_by_default(tmp_path, capsys) -> None:
    import json

    from cli.verify import main

    assert main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:", "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "diagnostics" not in payload
