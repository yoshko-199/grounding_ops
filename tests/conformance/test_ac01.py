"""AC-1 — Ledger inseparability.

Constraint: spec §7.1.  "The reconstructed claim never renders, exports, or
copies without its discard ledger. If it can be detached, the tool is a
laundering device."

AC-1's note fixes the standard: "'Present in the same payload' is the
operative phrase. A ledger fetched by a second call is detachable by anyone
who makes only the first call."
"""

from __future__ import annotations

import inspect
import json

from engine.render.artifact import Artifact


def _run(pack, registry, context, adapters, store):
    from engine.pipeline import verify

    return verify(
        "prices rose over the last three years due to governmental incompetence",
        context, registry, adapters, store,
    )


def test_every_public_emitter_carries_the_ledger(registry, context, adapters, store, pack):
    """Enumerate the emit paths and assert the ledger travels with each."""
    artifact = _run(pack, registry, context, adapters, store).artifact
    assert artifact.ledger, "fixture claim should discard the causal and evaluative parts"

    rendered = artifact.render()
    assert "DISCARD LEDGER" in rendered
    for entry in artifact.ledger:
        assert entry.fragment in rendered

    as_str = str(artifact)
    assert "DISCARD LEDGER" in as_str

    payload = artifact.to_dict()
    assert payload["discard_ledger"]
    assert len(payload["discard_ledger"]) == len(artifact.ledger)

    serialized = json.dumps(payload)
    assert "discard_ledger" in serialized


def test_the_reconstruction_has_no_public_accessor():
    """A detachable getter is a detachable ledger.

    The reconstruction is a private field, and every method that emits it also
    emits the ledger. There is no `.text`, `.reconstruction`, or `.summary`
    that would hand a caller the sentence on its own.
    """
    public = {
        name for name, _ in inspect.getmembers(Artifact)
        if not name.startswith("_")
    }
    for detachable in ("text", "reconstruction", "sentence", "summary", "headline"):
        assert detachable not in public


def test_to_dict_never_returns_a_reconstruction_without_a_ledger_key(
    registry, context, adapters, store, pack
):
    payload = _run(pack, registry, context, adapters, store).artifact.to_dict()
    assert "reconstruction" in payload
    assert "discard_ledger" in payload


def test_an_empty_ledger_is_stated_rather_than_omitted(registry, context, adapters, store, pack):
    """Silence would be indistinguishable from a detached ledger."""
    from engine.pipeline import verify

    artifact = verify("prices rose in 2021", context, registry, adapters, store).artifact
    rendered = artifact.render()
    assert "DISCARD LEDGER" in rendered
    if not artifact.ledger:
        assert "Nothing was discarded" in rendered


# -- the HTML page, one more emit path -----------------------------------------


def _section(html_text: str, css_class: str) -> str:
    start = html_text.index(f'<section class="{css_class}">')
    return html_text[start:html_text.index("</section>", start)]


def test_the_html_render_carries_the_ledger_in_the_same_section(
    registry, context, adapters, store, pack
):
    """AC-1 lists "UI render" first. The page puts the reconstruction and the
    ledger in one section, so neither can be lifted out without the other."""
    artifact = _run(pack, registry, context, adapters, store).artifact
    page = artifact.render_html()
    frame = _section(page, "reconstruction-and-ledger")
    assert 'class="reconstruction"' in frame
    assert 'class="ledger"' in frame
    for entry in artifact.ledger:
        assert entry.fragment in frame
        assert entry.reason.split(".")[0] in frame


def test_the_html_ledger_is_never_behind_a_control(registry, context, adapters, store, pack):
    """§7.1: not "behind a control, a second request, or a pagination boundary"."""
    page = _run(pack, registry, context, adapters, store).artifact.render_html()
    for control in ("<details", "<summary", " hidden", "display:none", "display: none",
                    "aria-hidden", "<button", "<template"):
        assert control not in page, f"{control!r} would put part of the artifact behind a control"


def test_an_empty_html_ledger_is_stated_rather_than_omitted(registry, context, adapters, store):
    from engine.pipeline import verify

    artifact = verify("prices rose in 2021", context, registry, adapters, store).artifact
    frame = _section(artifact.render_html(), "reconstruction-and-ledger")
    assert "Discard ledger" in frame
    if not artifact.ledger:
        assert "Nothing was discarded." in frame
