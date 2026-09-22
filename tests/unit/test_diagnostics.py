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

import json
import pathlib
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.base import CustodianUnreachable, Observation
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
    from cli.verify import main

    assert main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:", "--json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "diagnostics" not in payload


# -- the AC-7 carve-out, pinned as policy rather than left as an accident ----

#: The real BoI adapter reports status codes, and this environment's proxy
#: answers 403. A numeral is the whole point: it is what AC-7's render-time
#: scan would reject, so it is what makes a leak observable.
UNREACHABLE_DETAIL = "edge.boi.gov.il answered 403"

#: What a leak would look like. Not the bare "403": the artifact and the CLI
#: output both carry uuids (the claim id at least), and about one uuid in a
#: hundred and forty contains those three digits, which would make every
#: absence assertion below flaky.
LEAK = "answered 403"


class _Unreachable403:
    """A custodian whose outage message carries a status code."""

    custodian_id = "zzstat"

    def series(self, series_id: str) -> tuple[Observation, ...]:
        raise CustodianUnreachable(self.custodian_id, UNREACHABLE_DETAIL)


def _adapters_with_a_403():
    adapters = build_fixture_custodians()
    adapters["zzstat"] = _Unreachable403()
    return adapters


def test_a_numeral_bearing_diagnostic_never_enters_the_artifact() -> None:
    """`--diagnostics` is the one output surface that does not go through
    `engine/render/figures.py`'s numeral-sourcing scan, and it has to be: a
    custodian's unreachable message is usually *only* interesting because of
    the status code in it, and routing it through a scan that fails on
    unsourced numerals would either strip it or crash.

    That carve-out is safe exactly because the text never reaches the
    artifact. The numeral here comes out of the real pipeline -- the adapter
    raises it, `retrieve.pull` catches it -- so a leak anywhere between that
    handler and the artifact fails this test. An earlier version attached the
    diagnostic with `dataclasses.replace` after `verify()` had already built
    the artifact, which made the assertion true whatever the pipeline did.
    """
    registry = PackRegistry.from_directory(PACKS)
    store = RetrievalStore(":memory:")
    try:
        run = verify(CLAIM, _context(), registry, _adapters_with_a_403(), store)
    finally:
        store.close()

    # The operator still sees it...
    assert LEAK in run.diagnostic

    # ...and the reader never does. `render()` would itself raise
    # UnsourcedFigure on a leak; `to_dict()` is not scanned, so it is asserted
    # directly rather than trusted to the render boundary.
    rendered = run.artifact.render()
    assert LEAK not in rendered, "a diagnostic numeral reached the artifact"
    payload = run.artifact.to_dict()
    assert LEAK not in json.dumps(payload), "a diagnostic numeral reached the structured artifact"


def test_the_cli_prints_the_numeral_only_under_the_diagnostics_header(monkeypatch, capsys) -> None:
    """The printing half of the carve-out, through the composition root."""
    import cli.verify

    monkeypatch.setattr(cli.verify, "build_fixture_custodians", _adapters_with_a_403)
    assert cli.verify.main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:",
         "--diagnostics"]
    ) == 0
    out = capsys.readouterr().out
    artifact, header, diagnostics = out.partition(
        "DIAGNOSTICS (operator information, not part of the verified record)"
    )
    assert header, "the diagnostics block was not printed"
    assert LEAK not in artifact, "the status code was printed as part of the artifact"
    assert UNREACHABLE_DETAIL in diagnostics


def test_the_json_payload_carries_the_numeral_only_in_its_diagnostics_key(monkeypatch, capsys) -> None:
    import cli.verify

    monkeypatch.setattr(cli.verify, "build_fixture_custodians", _adapters_with_a_403)
    assert cli.verify.main(
        [CLAIM, "--jurisdiction", "ZZ", "--packs", str(PACKS), "--store", ":memory:",
         "--json", "--diagnostics"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    diagnostics = payload.pop("diagnostics")
    assert UNREACHABLE_DETAIL in diagnostics["pull_diagnostic"]
    assert LEAK not in json.dumps(payload), "the status code reached the artifact payload"
