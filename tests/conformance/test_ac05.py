"""AC-5 — Insufficient Data is first-class.

Constraint: spec §7.5.  Never styled as failure.

"Assert identical prominence: same typographic hierarchy, same container,
same position in the layout."  In a CLI that means the same section, the same
label formatting, and an exit code of zero.
"""

from __future__ import annotations

import re

from engine.pipeline import verify
from engine.verification.claim_verdict import Verdict

INSUFFICIENT = "badger population rose in 2021"
ORDINARY = "prices rose over the last three years"


def _render(claim, context, registry, adapters, store):
    return verify(claim, context, registry, adapters, store).artifact


def test_insufficient_data_renders_in_the_same_container(
    registry, context, adapters, store
) -> None:
    insufficient = _render(INSUFFICIENT, context, registry, adapters, store)
    ordinary = _render(ORDINARY, context, registry, adapters, store)

    assert insufficient.verdict.label is Verdict.INSUFFICIENT_DATA
    for artifact in (insufficient, ordinary):
        rendered = artifact.render()
        assert "VERDICT" in rendered
        # Same position: the verdict section follows the ledger in both.
        assert rendered.index("DISCARD LEDGER") < rendered.index("VERDICT")


def test_insufficient_data_carries_no_error_styling(
    registry, context, adapters, store
) -> None:
    rendered = _render(INSUFFICIENT, context, registry, adapters, store).render()
    for marker in ("ERROR", "WARNING", "FAILED", "⚠", "✗", "!!", "Retry", "retry"):
        assert marker not in rendered


def test_the_label_is_formatted_like_any_other(registry, context, adapters, store) -> None:
    insufficient = _render(INSUFFICIENT, context, registry, adapters, store).render()
    ordinary = _render(ORDINARY, context, registry, adapters, store).render()
    pattern = re.compile(r"^VERDICT\n  ([A-Z ]+)$", re.M)
    assert pattern.search(insufficient)
    assert pattern.search(ordinary)


def test_insufficient_data_is_described_as_an_answer(
    registry, context, adapters, store
) -> None:
    artifact = _render(INSUFFICIENT, context, registry, adapters, store)
    assert "not a failure" in artifact.verdict.rationale or "Insufficient" in artifact.render()


def test_the_cli_exits_zero_for_insufficient_data(capsys) -> None:
    """A non-zero exit is exactly the error styling this criterion forbids."""
    from cli.verify import main

    assert main([INSUFFICIENT, "--jurisdiction", "ZZ", "--packs", "packs/fixture", "--store", ":memory:"]) == 0
    assert main([ORDINARY, "--jurisdiction", "ZZ", "--packs", "packs/fixture", "--store", ":memory:"]) == 0


def test_no_non_2xx_equivalent_in_the_structured_payload(
    registry, context, adapters, store
) -> None:
    payload = _render(INSUFFICIENT, context, registry, adapters, store).to_dict()
    assert "error" not in payload
    assert payload["verdict"]["label"] == "insufficient_data"


def test_a_malformed_date_is_reported_rather_than_raised(capsys) -> None:
    """An operator error must not surface as an engine crash.

    Found while documenting the CLI: `--stated-at 2021-13-99` propagated a
    bare ValueError as a traceback. AC-5 is about Insufficient Data rendering
    as an answer, and the same reasoning applies one step earlier — a
    traceback reads as the machinery breaking, which is exactly the error
    styling this criterion refuses for a non-failure.

    The date is refused rather than defaulted because every tolerance band and
    the continuity check are indexed on when the claim was made.
    """
    from cli.verify import main

    assert main([ORDINARY, "--stated-at", "2021-13-99", "--packs", "packs/fixture", "--store", ":memory:"]) == 2
    assert "not a date" in capsys.readouterr().err


def test_an_unresolvable_jurisdiction_is_an_answer_not_an_error(capsys) -> None:
    """A hint of the wrong shape yields Insufficient Data, never a non-zero exit.

    §9.8.3 forbids defaulting or inferring a jurisdiction, so an unusable hint
    resolves to none at all. That is a verdict, and AC-5 requires it to exit
    zero like any other.
    """
    from cli.verify import main

    assert main([ORDINARY, "--jurisdiction", "zz", "--packs", "packs/fixture", "--store", ":memory:"]) == 0
    assert main([ORDINARY, "--jurisdiction", "not-a-code", "--packs", "packs/fixture", "--store", ":memory:"]) == 0


# ---------------------------------------------------------------------------
# §7.5's framing survives on every Insufficient Data path.
#
# A helper was added to guarantee it, and then one function was left calling
# the old code — so the no-jurisdiction and no-pack verdicts lost the framing
# while the criterion's own test still passed on a different path.
# ---------------------------------------------------------------------------


def test_no_jurisdiction_keeps_the_framing(registry, adapters, store) -> None:
    from datetime import date

    from engine.codes import JurisdictionCode, LanguageCode
    from engine.context import ClaimContext
    from engine.pipeline import verify

    context = ClaimContext(
        jurisdiction=JurisdictionCode("QQ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )
    run = verify("inflation rose in 2021", context, registry, adapters, store)
    rationale = run.artifact.verdict.rationale

    assert "no jurisdiction could be established" in rationale
    assert "not a failure" in rationale, (
        "the specific reason replaced §7.5's framing instead of carrying it"
    )


def test_no_measure_keeps_both_the_reason_and_the_framing(
    registry, context, adapters, store
) -> None:
    from engine.pipeline import verify

    run = verify(INSUFFICIENT, context, registry, adapters, store)
    rationale = run.artifact.verdict.rationale
    assert "no measure in the pack matches this claim" in rationale
    assert "not a failure" in rationale


def test_an_operator_diagnostic_is_not_reader_facing() -> None:
    """A pack defect is worth logging and not worth telling a reader.

    NO_ROUTING_RULE's rationale ends "a pack defect to be filed". The override
    that surfaces a routing reason must not surface that one; it stays on the
    decision for logs, the same split PullOutcome.diagnostic already makes.
    """
    from engine.pipeline import _READER_FACING
    from engine.verification.route import RoutingFailure

    assert RoutingFailure.CONTESTED_BY_DEFINITION in _READER_FACING
    assert RoutingFailure.NO_MEASURE in _READER_FACING
    assert RoutingFailure.NO_ROUTING_RULE not in _READER_FACING


def test_a_missing_lexicon_says_so_rather_than_echoing_the_routing_text() -> None:
    """Routing may have *succeeded* when the lexicon lookup fails.

    Reusing the decision's rationale therefore made the verdict say "bound to
    <measure> on the measure's published name" for a claim that failed because
    the pack declares no lexicon for its language — a confident sentence about
    the wrong thing.
    """
    from engine.codes import JurisdictionCode
    from engine.pipeline import _unrouted
    from engine.verification.route import JurisdictionRule, RoutingDecision

    routed_fine = RoutingDecision(
        jurisdiction=JurisdictionCode("IL"),
        jurisdiction_rule=JurisdictionRule.CONTEXT_HINT,
        rationale="bound to Representative exchange rate, euro on the measure's name",
    )
    run = _unrouted(
        "a claim",
        routed_fine,
        reason="the pack declares no lexicon for this language and no English fallback",
    )
    rationale = run.artifact.verdict.rationale

    assert "lexicon" in rationale
    assert "bound to" not in rationale
    assert "not a failure" in rationale
