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


def test_a_shared_caveat_is_stated_once_and_never_dropped(
    registry, context, adapters, store, pack
):
    """Consecutive citations sharing a framing caveat show it once, before
    them. That keeps the ledger and verdict readable instead of burying them
    under the same paragraph a dozen times. Every citation keeps its entry,
    the caveat is still present, and nothing sits behind a control."""
    artifact = _run(pack, registry, context, adapters, store).artifact
    # Scoped to the citations section: the same caveat text legitimately
    # appears elsewhere too, in the sweep's bounded-omission row.
    page = _section(artifact.render_html(), "citations")
    caveats = {r.caveat for r in artifact.citations if r.caveat}
    assert caveats, "the fixture series declares a framing caveat"
    for caveat in caveats:
        assert caveat in page
    for retrieval in artifact.citations:
        assert f'id="retrieval-{retrieval.id}"' in page
    if len(artifact.citations) > 1 and len(caveats) == 1:
        assert page.count(next(iter(caveats))) == 1


def test_a_changed_caveat_starts_its_own_group(registry, context, adapters, store, pack):
    """Grouping is by run, not by value: a caveat that changes mid-list is
    stated again before the citations it covers."""
    from dataclasses import replace

    artifact = _run(pack, registry, context, adapters, store).artifact
    first, *rest = artifact.citations
    altered = replace(first, caveat="Framing: a different caveat for the first figure only.")
    page = _section(replace(artifact, citations=(altered, *rest)).render_html(), "citations")
    different = page.index("a different caveat for the first figure only")
    assert different < page.index(f'id="retrieval-{altered.id}"')
    shared = rest[0].caveat
    assert shared and page.index(shared) > page.index(f'id="retrieval-{altered.id}"')
    assert page.index(shared) < page.index(f'id="retrieval-{rest[0].id}"')
