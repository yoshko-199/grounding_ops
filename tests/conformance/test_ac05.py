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

    assert main([INSUFFICIENT, "--jurisdiction", "ZZ", "--packs", "packs/fixture"]) == 0
    assert main([ORDINARY, "--jurisdiction", "ZZ", "--packs", "packs/fixture"]) == 0


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

    assert main([ORDINARY, "--stated-at", "2021-13-99", "--packs", "packs/fixture"]) == 2
    assert "not a date" in capsys.readouterr().err


def test_an_unresolvable_jurisdiction_is_an_answer_not_an_error(capsys) -> None:
    """A hint of the wrong shape yields Insufficient Data, never a non-zero exit.

    §9.8.3 forbids defaulting or inferring a jurisdiction, so an unusable hint
    resolves to none at all. That is a verdict, and AC-5 requires it to exit
    zero like any other.
    """
    from cli.verify import main

    assert main([ORDINARY, "--jurisdiction", "zz", "--packs", "packs/fixture"]) == 0
    assert main([ORDINARY, "--jurisdiction", "not-a-code", "--packs", "packs/fixture"]) == 0
