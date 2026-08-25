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
