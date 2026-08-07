"""Every artifact-producing path must survive its own render.

These are regression tests for a class of AC-7 false positives found by
running a real claim through the CLI rather than through the suite.

The bug: several user-facing strings carried numerals that were not figures —
a stage number ("the claim did not pass Stage 1"), spec citations ("§9.8.3",
"§9.4"), and a pack version interpolated into a rationale. AC-7's scanner
correctly refused to render any of them, because it cannot tell a section
reference from a statistic and should not try. The fix was to keep spec
citations in the code, where they already live in docstrings, and out of the
artifact, where a reader needs plain language instead.

The deeper gap those tests missed: **no test rendered an out-of-scope or
unrouted artifact.** Every existing AC test either rendered a claim that
routed successfully or exercised `evaluate()` directly, so three whole
branches of `Artifact.render()` had never executed. A criterion enforced only
on the paths a suite happens to walk is not enforced.
"""

from __future__ import annotations

from datetime import date

import pytest

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.pipeline import verify
from engine.verdicts import Verdict

# One claim per artifact-producing branch, named for the branch it covers.
CLAIMS = {
    "out_of_scope_at_the_scope_gate": (
        "When you look at the horizon you dont see a curve - therfore the earth is flat"
    ),
    "no_jurisdiction_resolvable": "the earth is flat",
    "routed_but_no_measure_matches": "badger population rose in 2021",
    "routed_and_verified": "prices rose over the last three years",
    "routed_with_out_of_scope_fragments": (
        "prices rose over the last three years due to governmental incompetence"
    ),
}


@pytest.fixture
def zz_context() -> ClaimContext:
    return ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )


@pytest.mark.parametrize("name,claim", sorted(CLAIMS.items()))
def test_every_branch_renders(name, claim, zz_context, registry, adapters, store) -> None:
    """The render must not raise on any path that can produce an artifact.

    AC-7 makes an unsourced numeral fail the render, which is correct — and it
    means an untested branch is a branch that can crash a user's verification
    the first time it is taken.
    """
    artifact = verify(claim, zz_context, registry, adapters, store).artifact
    rendered = artifact.render()
    assert rendered
    assert "ORIGINAL CLAIM" in rendered
    assert "DISCARD LEDGER" in rendered
    assert "VERDICT" in rendered


@pytest.mark.parametrize("name,claim", sorted(CLAIMS.items()))
def test_every_branch_serialises(name, claim, zz_context, registry, adapters, store) -> None:
    artifact = verify(claim, zz_context, registry, adapters, store).artifact
    payload = artifact.to_dict()
    assert "discard_ledger" in payload
    assert payload["verdict"]["label"] in {v.value for v in Verdict}


def test_no_jurisdiction_path_renders_without_a_hint(registry, adapters, store) -> None:
    """The unrouted branch, reached with no jurisdiction hint at all."""
    context = ClaimContext(None, LanguageCode("en"), date(2022, 1, 1))
    artifact = verify("the earth is flat", context, registry, adapters, store).artifact
    rendered = artifact.render()
    assert artifact.verdict.label is Verdict.INSUFFICIENT_DATA
    assert "no default jurisdiction" in rendered


def test_unknown_jurisdiction_path_renders(registry, adapters, store) -> None:
    context = ClaimContext(
        JurisdictionCode("QQ"), LanguageCode("en"), date(2022, 1, 1)
    )
    artifact = verify("prices rose in 2021", context, registry, adapters, store).artifact
    assert artifact.render()
    assert artifact.verdict.label is Verdict.INSUFFICIENT_DATA


def test_a_claim_with_no_custodian_is_insufficient_data_not_false(
    zz_context, registry, adapters, store
) -> None:
    """The point of the flat-earth case, and it is not a technicality.

    The engine must not answer "False" here. It has no custodian for the
    shape of the earth, and §2's fourth exclusion is explicit that where no
    authoritative custodian exists, a verdict would be "argument wearing a
    verification badge" — however obviously wrong the claim happens to be.
    Being right for the wrong reason is the failure mode the whole design
    refuses, and a claim everyone knows the answer to is exactly where that
    refusal is most tempting to break.
    """
    artifact = verify(
        CLAIMS["out_of_scope_at_the_scope_gate"], zz_context, registry, adapters, store
    ).artifact
    assert artifact.verdict.label is Verdict.INSUFFICIENT_DATA
    assert artifact.verdict.label is not Verdict.FALSE
    assert not artifact.does_reconstruct
    assert not artifact.citations


def test_out_of_scope_claims_carry_the_reason_into_the_ledger(
    zz_context, registry, adapters, store
) -> None:
    """§7.1 — the ledger travels even when nothing survived to reconstruct."""
    artifact = verify(
        CLAIMS["out_of_scope_at_the_scope_gate"], zz_context, registry, adapters, store
    ).artifact
    assert artifact.ledger
    assert artifact.ledger[0].status == "out_of_scope"
    assert artifact.ledger[0].reason.strip()
    assert artifact.ledger[0].fragment in artifact.render()


def test_no_user_facing_string_carries_a_spec_citation(
    zz_context, registry, adapters, store
) -> None:
    """Spec citations belong in the code, not in the artifact.

    They are developer-facing, they mean nothing to a reader of a
    verification, and — because they contain digits — AC-7's scanner
    correctly refuses to render them. Keeping them out is what stops that
    scanner from having to distinguish a section number from a statistic.
    """
    import re

    for claim in CLAIMS.values():
        rendered = verify(claim, zz_context, registry, adapters, store).artifact.render()
        assert "§" not in rendered, f"a spec citation reached output for {claim!r}"
        assert not re.search(r"\bStage \d", rendered)
