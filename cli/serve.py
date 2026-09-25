#!/usr/bin/env python3
"""A local web UI over the same pipeline, store and packs as the CLI.

This is a composition root, like `cli/verify.py`, and for the same reason: it
is where a network primitive is allowed to exist. `http.server` is imported
here and nowhere under `engine/`, so verification stays statically unable to
reach it.

What the page shows is `Artifact.render_html()`, which runs the text render
first as its gate. This module adds a page shell, a form and a read-back
view. It never builds artifact content of its own, so AC-1, AC-5 and AC-7 are
held by the method they already bind rather than re-argued here.

The server binds to `127.0.0.1` by default and refuses a cross-origin POST.
Without that check, any page open in the same browser could submit forms that
write to the local store, and once sign-off lands those forms would write
verdicts. It is a local tool, not a deployment: nothing here authenticates a
user.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from cli.compose import (
    DECISIONS,
    NoOpenProposal,
    OperatorError,
    load_registry,
    open_store,
    parse_stated_at,
    sign_off_stored,
    split_provenance,
    verify_and_persist,
)
from cli.show import _load, stored_bottom_line
from engine.render import bottom_line
from cli.verify import DEFAULT_PACKS, DEFAULT_STORE
from engine.custodians.fixture import build_fixture_custodians
from engine.custodians.live import build_live_custodians
from engine.ingest.split import RawProvenance
from engine.signoff import GateViolation
from engine.store.signoff_writer import list_proposed, load_proposed
from engine.verification.claim_verdict import Verdict

#: Largest form body accepted. A claim is a sentence or a paragraph; anything
#: near this size is not a claim.
MAX_BODY = 64 * 1024

_CLAIM_ID = re.compile(r"^[0-9a-fA-F-]{8,64}$")

_SECURITY_HEADERS = (
    # No scripts at all, no external requests: the page is markup and one
    # inline stylesheet, and forms may only post back here.
    ("Content-Security-Policy",
     "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
     "base-uri 'none'; frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    # Not `no-referrer`. Under that policy the Fetch standard serialises a
    # POST's Origin header as "null" even for a same-origin form, and the
    # cross-origin check below refuses "null": every form this UI served was
    # refused by a real browser. `same-origin` keeps the page's own origin on
    # its own posts, and still sends nothing to any other site.
    ("Referrer-Policy", "same-origin"),
)


@dataclass(frozen=True)
class Response:
    status: int
    body: str
    headers: tuple[tuple[str, str], ...] = ()


class App:
    """The web UI as a pure function of a request, so tests need no socket."""

    def __init__(self, packs: str, store_path: str, *, live: bool = False) -> None:
        if store_path == ":memory:":
            # Each request opens its own connection, and an in-memory database
            # dies with it: every read-back would find nothing.
            raise OperatorError(
                "the web UI needs a durable store; ':memory:' would forget every "
                "claim between one request and the next"
            )
        self.registry = load_registry(packs)
        self.store_path = store_path
        self.live = live

    # -- dispatch -------------------------------------------------------------

    def handle(self, method: str, target: str, headers: dict[str, str], body: bytes) -> Response:
        path = urlsplit(target).path
        if path == "/":
            if method != "GET":
                return _not_allowed("GET")
            return self._form_page()
        if path == "/verify":
            if method != "POST":
                return _not_allowed("POST")
            refused = _refuse_cross_origin(headers)
            if refused:
                return refused
            return self._verify(headers, body)
        if path.startswith("/claim/"):
            if method != "GET":
                return _not_allowed("GET")
            return self._read_back(path.removeprefix("/claim/"))
        if path == "/queue":
            if method != "GET":
                return _not_allowed("GET")
            return self._queue()
        if path == "/signoff":
            if method != "POST":
                return _not_allowed("POST")
            refused = _refuse_cross_origin(headers)
            if refused:
                return refused
            return self._sign_off(headers, body)
        return _page(404, "Not found", "<p>There is no page at this address.</p>")

    # -- routes ---------------------------------------------------------------

    def _form_page(self, values: dict[str, str] | None = None, problem: str = "",
                   status: int = 200) -> Response:
        values = values or {}
        e = html.escape
        options = ['<option value="">No hint: resolve from the claim</option>']
        for code in self.registry.jurisdictions:
            chosen = " selected" if values.get("jurisdiction") == code else ""
            options.append(f'<option value="{e(code)}"{chosen}>{e(code)}</option>')
        problem_html = (
            f'<p class="form-problem" role="status">Could not verify: {e(problem)}</p>'
            if problem else ""
        )
        form = f"""{problem_html}
<form method="post" action="/verify" class="verify-form">
<label for="claim">Claim</label>
<textarea id="claim" name="claim" rows="4" required>{e(values.get("claim", ""))}</textarea>
<div class="row">
<div><label for="jurisdiction">Jurisdiction</label>
<select id="jurisdiction" name="jurisdiction">{"".join(options)}</select></div>
<div><label for="language">Language</label>
<input id="language" name="language" value="{e(values.get("language", "en"))}"></div>
<div><label for="stated_at">Stated on</label>
<input id="stated_at" name="stated_at" type="date" value="{e(values.get("stated_at", ""))}"></div>
</div>
<div class="row">
<div><label for="claimant">Claimant <span class="hint">recorded, never routed</span></label>
<input id="claimant" name="claimant" value="{e(values.get("claimant", ""))}"></div>
<div><label for="venue">Venue <span class="hint">recorded, never routed</span></label>
<input id="venue" name="venue" value="{e(values.get("venue", ""))}"></div>
</div>
<button type="submit">Verify</button>
</form>"""
        return _page(status, "Verify a claim", form)

    def _verify(self, headers: dict[str, str], body: bytes) -> Response:
        fields = _form_fields(headers, body)
        if isinstance(fields, Response):
            return fields

        claim = fields.get("claim", "").strip()
        try:
            if not claim:
                raise OperatorError("the claim is empty")
            context, identity = split_provenance(
                RawProvenance(
                    stated_at=parse_stated_at(fields.get("stated_at") or None),
                    language=fields.get("language", "").strip() or "en",
                    jurisdiction_hint=fields.get("jurisdiction") or None,
                    claimant_name=fields.get("claimant") or None,
                    venue=fields.get("venue") or None,
                )
            )
            store = open_store(self.store_path)
        except OperatorError as exc:
            return self._form_page(fields, str(exc), status=400)

        adapters = build_fixture_custodians()
        if self.live:
            adapters.update(build_live_custodians())
        try:
            run = verify_and_persist(claim, context, identity, self.registry, store, adapters)
        finally:
            store.close()

        e = html.escape
        claim_id = e(str(run.claim_id))
        parts = [
            f'<p class="claim-id">Claim <code>{claim_id}</code> · '
            f'<a href="/claim/{claim_id}">read back the stored record</a> · '
            '<a href="/">verify another</a></p>',
            run.artifact.render_html(),
        ]
        if not identity.is_anonymous:
            parts.append(
                '<section class="attribution"><h2>Attribution (recorded, never routed)</h2>'
                f"<p>claimant: {e(identity.name or '-')}</p>"
                f"<p>venue: {e(identity.venue or '-')}</p></section>"
            )
        return _page(200, "Verification", "\n".join(parts))

    def _read_back(self, claim_id: str, *, problem: str = "",
                   values: dict[str, str] | None = None, status: int = 200) -> Response:
        if not _CLAIM_ID.match(claim_id):
            return _page(404, "Not found", "<p>That is not a claim id.</p>")
        try:
            store = open_store(self.store_path)
        except OperatorError as exc:
            return _page(503, "Store unavailable", f"<p>{html.escape(str(exc))}</p>")
        try:
            record = _load(store, claim_id)
            awaiting = record is not None and load_proposed(store, claim_id) is not None
        finally:
            store.close()
        if record is None:
            return _page(404, "Not found",
                         f"<p>No claim is recorded with id <code>{html.escape(claim_id)}</code>.</p>")
        content = record_html(record)
        if awaiting:
            content += "\n" + _sign_off_form(claim_id, record["verdict"]["label"], problem, values or {})
        elif problem:
            content = f'<p class="form-problem" role="status">{html.escape(problem)}</p>\n' + content
        return _page(status, "Stored record", content)

    def _queue(self) -> Response:
        try:
            store = open_store(self.store_path)
        except OperatorError as exc:
            return _page(503, "Store unavailable", f"<p>{html.escape(str(exc))}</p>")
        try:
            rows = list_proposed(store)
        finally:
            store.close()
        if not rows:
            return _page(200, "Sign-off queue", "<p>Nothing is awaiting review.</p>")
        e = html.escape
        items = []
        for row in rows:
            # The full claim text. The command line's list truncates to fit a
            # terminal row; a page has no such limit, and a reviewer choosing
            # what to open should see the claim as it was made.
            items.append(
                f'<li><a class="queue-claim" href="/claim/{e(row["claim_id"])}">{e(row["text"])}</a>'
                f'<p class="provenance">proposed <span class="status">'
                f'{e(row["label"].replace("_", " "))}</span> · {e(row["proposed_at"])} · '
                f'<code>{e(row["claim_id"])}</code></p></li>'
            )
        content = ('<p class="hint">Proposed verdicts, oldest first. Each is a label the '
                   "pipeline suggested; everything beneath it is already final.</p>"
                   f'<ul class="queue">{"".join(items)}</ul>')
        return _page(200, "Sign-off queue", content)

    def _sign_off(self, headers: dict[str, str], body: bytes) -> Response:
        fields = _form_fields(headers, body)
        if isinstance(fields, Response):
            return fields
        # Exactly these five fields are read. Anything else a request carries
        # is ignored: there is no parameter here, or in `sign_off_stored`, that
        # could reach an element, a retrieval, the ledger or the sweep (AC-10).
        claim_id = fields.get("claim_id", "")
        action = fields.get("action", "")
        reviewer = fields.get("reviewer", "").strip()
        label_value = fields.get("label", "")
        rationale = fields.get("rationale", "")
        kept = {"action": action, "reviewer": reviewer, "label": label_value,
                "rationale": rationale}

        if not _CLAIM_ID.match(claim_id):
            return _page(404, "Not found", "<p>That is not a claim id.</p>")
        try:
            label = Verdict(label_value) if action == "amend" and label_value else None
        except ValueError:
            return self._read_back(claim_id, problem=f"not a verdict label: {label_value!r}",
                                   values=kept, status=400)
        try:
            store = open_store(self.store_path)
        except OperatorError as exc:
            return _page(503, "Store unavailable", f"<p>{html.escape(str(exc))}</p>")
        try:
            sign_off_stored(store, claim_id, action, reviewer, label, rationale)
        except NoOpenProposal as exc:
            store.close()
            return self._read_back(claim_id, problem=str(exc), status=409)
        except (OperatorError, GateViolation) as exc:
            store.close()
            return self._read_back(claim_id, problem=str(exc), values=kept, status=400)
        store.close()
        # Post/redirect/get: reloading the record page never resubmits a decision.
        return Response(303, "", (("Location", f"/claim/{claim_id}"), *_SECURITY_HEADERS))


def record_html(record: dict) -> str:
    """A stored record as HTML: the sections `cli/show.py` prints, in its order.

    Like `show`, this re-renders stored rows with no retrieval and no
    re-routing. It emits only what those rows hold, so it can carry no numeral
    the stored text render lacks, and the ledger sits in the same section as
    the reconstruction.
    """
    e = html.escape
    out = ['<article class="artifact stored">',
           f'<p class="unconfirmed">Stored record: claim <code>{e(record["claim_id"])}</code></p>',
           '<section class="claim"><h2>Original claim</h2>',
           f'<blockquote>{e(record["text"])}</blockquote></section>']
    basis = stored_bottom_line(record)
    if basis is not None:
        out.append(bottom_line.as_html(basis))
    out.append('<section class="reconstruction-and-ledger"><h2>Reconstructed</h2>')
    recon = record["reconstruction"]
    if recon and recon["does_reconstruct"]:
        out.append(f'<p class="reconstruction">{e(recon["text"])}</p>')
        out.append(f'<p class="provenance">revision {e(str(recon["revision"]))}, '
                   f'hash {e(recon["element_set_hash"])}</p>')
    else:
        out.append('<p class="reconstruction">does not reconstruct</p>')
    out.append('<h3 class="ledger-heading">Discard ledger</h3>')
    if record["discards"]:
        out.append('<ul class="ledger">')
        for d in record["discards"]:
            out.append(f'<li><span class="fragment">{e(d["fragment"])}</span> '
                       f'<span class="status">{e(d["status"])}</span>'
                       f'<p class="reason">{e(d["reason"])}</p></li>')
        out.append("</ul>")
    elif not record["elements"]:
        out.append('<p class="ledger">Not decomposed: no elements were recorded for this claim, so nothing was kept or discarded.</p>')
    else:
        out.append('<p class="ledger">Nothing was discarded.</p>')
    out.append("</section>")

    out.append('<section class="verdict"><h2>Verdict</h2>')
    verdict = record["verdict"]
    if verdict:
        out.append(f'<p class="verdict-label">{e(verdict["label"].replace("_", " ").upper())}</p>')
        out.append(f'<p class="verdict-state">{e(verdict["state"])}</p>')
        out.append(f'<p class="verdict-rationale">{e(verdict["rationale"])}</p>')
        if verdict["confirmed_by"]:
            out.append(f'<p>signed off by {e(verdict["confirmed_by"])} at {e(verdict["confirmed_at"])}</p>')
        if verdict["amended_from_label"]:
            out.append(f'<p>amended from {e(verdict["amended_from_label"])}: '
                       f'{e(verdict["amendment_rationale"])}</p>')
    else:
        out.append('<p class="verdict-rationale">No verdict was recorded.</p>')
    out.append("</section>")

    out.append('<section class="citations"><h2>Citations</h2>')
    if record["citations"]:
        out.append('<ul class="citation-list">')
        for c in record["citations"]:
            out.append(
                f'<li id="retrieval-{e(str(c["id"]))}">'
                f'<span class="series">{e(c["custodian_id"])} / {e(c["series_id"])}</span> '
                f'<span class="figure">{e(str(c["figure"]))} {e(c["unit"])}</span> '
                f'<span class="period">for {e(c["reference_period"])}</span>'
                f'<p class="provenance">revision {e(c["revision_status"])}; '
                f'retrieved {e(c["retrieved_at"])}; continuity {e(c["continuity_status"])}</p>'
            )
            if c["superseded_at"]:
                out.append(f'<p class="caveat">superseded at {e(c["superseded_at"])}</p>')
            out.append("</li>")
        out.append("</ul>")
    else:
        out.append("<p>No retrieval was performed.</p>")
    out.append("</section>")

    if record["sweeps"]:
        out.append('<section class="sweep"><h2>Robustness sweep</h2><table class="flip-table">'
                   '<thead><tr><th scope="col">Result</th><th scope="col">Alternative</th></tr>'
                   "</thead><tbody>")
        for s in record["sweeps"]:
            result = "holds" if s["conclusion_holds"] else "flips"
            out.append(f'<tr class="{result}"><td>{result}</td>'
                       f'<td>{e(s["test"])}: {e(s["alternative"])}</td></tr>')
        out.append("</tbody></table></section>")

    if record["derived_elements"]:
        out.append('<section class="derived"><h2>Derived elements (proposed, not confirmed)</h2>')
        for d in record["derived_elements"]:
            out.append(f'<div class="derived-element"><span class="tag">{e(d["tag"])}</span>'
                       f'<p>{e(d["text"])}</p><p class="operation">operation: '
                       f'{e(d["derivation_operation"])}, state: {e(d["state"])}</p></div>')
        out.append("</section>")

    if record["identity"]:
        identity = record["identity"]
        out.append('<section class="attribution"><h2>Attribution (recorded, never routed)</h2>'
                   f"<p>claimant: {e(identity['name'] or '-')}</p>"
                   f"<p>venue: {e(identity['venue'] or '-')}</p></section>")
    out.append("</article>")
    return "\n".join(out)


def _form_fields(headers: dict[str, str], body: bytes) -> dict[str, str] | Response:
    content_type = headers.get("content-type", "").split(";")[0].strip()
    if content_type and content_type != "application/x-www-form-urlencoded":
        return _page(415, "Unsupported form", "<p>Submit the form on the page.</p>")
    if len(body) > MAX_BODY:
        return _too_large()
    try:
        return {k: v[0] for k, v in parse_qs(body.decode("utf-8")).items()}
    except UnicodeDecodeError:
        return _page(400, "Unreadable form", "<p>The form was not valid UTF-8.</p>")


def _sign_off_form(claim_id: str, proposed: str, problem: str, values: dict[str, str]) -> str:
    """§9.1's gate as a form: a decision, a name, and for an amendment a label
    and a reason. It has no field for anything beneath the claim-level label."""
    e = html.escape
    action = values.get("action") or "confirm"
    hints = {
        "confirm": "Accept the proposed label unchanged.",
        "amend": "Change the label, with a stated reason.",
        "reject": "Publish no label for this claim.",
    }
    decisions = "".join(
        f'<label class="decision"><input type="radio" name="action" value="{d}"'
        f'{" checked" if d == action else ""}> <span>{d.capitalize()}</span>'
        f'<span class="hint">{hints[d]}</span></label>'
        for d in DECISIONS
    )
    chosen = values.get("label", "")
    options = "".join(
        f'<option value="{e(v.value)}"{" selected" if v.value == chosen else ""}>'
        f'{e(v.value.replace("_", " "))}</option>'
        for v in Verdict if v.value != proposed
    )
    problem_html = (f'<p class="form-problem" role="status">Not signed off: {e(problem)}</p>'
                    if problem else "")
    return f"""<section class="sign-off"><h2>Sign off</h2>
<p class="hint">Proposed: {e(proposed.replace("_", " "))}. Element statuses, the
reconstruction, the ledger, the flip table, citations and routing are final and
out of reach here: sign-off changes the claim-level label and nothing beneath it.</p>
{problem_html}
<form method="post" action="/signoff" class="verify-form">
<input type="hidden" name="claim_id" value="{e(claim_id)}">
<fieldset class="decisions"><legend>Decision</legend>{decisions}</fieldset>
<div class="row">
<div><label for="label">New label <span class="hint">amend only</span></label>
<select id="label" name="label"><option value="">choose a label</option>{options}</select></div>
<div><label for="reviewer">Reviewer</label>
<input id="reviewer" name="reviewer" required value="{e(values.get("reviewer", ""))}"></div>
</div>
<label for="rationale">Why the label changes <span class="hint">amend only; state it in
words, since a figure with no retrieval behind it is refused</span></label>
<textarea id="rationale" name="rationale" rows="3">{e(values.get("rationale", ""))}</textarea>
<button type="submit">Record decision</button>
</form>
<p class="hint">The proposal is kept alongside your decision, never overwritten.</p>
</section>"""


# -- page shell ---------------------------------------------------------------

_STYLE = """
:root{--paper:#F5F3EC;--card:#FBFAF6;--ink:#1D1C1A;--muted:#5B5750;--rule:#D9D4C7;
--link:#1F4E79;--flips:#7A2121;--holds:#2F5D3A;--note-bg:#F3E6CF;--note-ink:#5A3A05}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font:16px/1.55 "IBM Plex Sans",-apple-system,"Segoe UI",system-ui,sans-serif}
a{color:var(--link)}
header.site{display:flex;align-items:center;gap:24px;padding:16px 32px;background:var(--card);
border-bottom:1px solid var(--rule)}
header.site .mark{font:600 22px/1 "Newsreader",Georgia,serif;color:var(--ink);text-decoration:none}
header.site nav{display:flex;gap:4px}
header.site nav a{color:var(--muted);text-decoration:none;padding:12px 8px;white-space:nowrap}
main{max-width:960px;margin:0 auto;padding:32px}
h1{font:600 30px/1.2 "Newsreader",Georgia,serif;margin:0 0 20px}
h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
h3{font-size:12px;letter-spacing:.12em;text-transform:uppercase;margin:16px 0 8px}
section{margin:0 0 32px}
.unconfirmed{background:var(--note-bg);color:var(--note-ink);padding:12px 16px;border-radius:8px;font-weight:600}
blockquote{margin:0;font:26px/1.35 "Newsreader",Georgia,serif}
.reconstruction-and-ledger{border:1px solid var(--rule);border-radius:12px;background:var(--card);padding:20px 24px}
.bottom-line{border-left:4px solid var(--ink);padding:4px 0 4px 20px}
.bottom-line p{margin:0 0 8px;font-size:17px;line-height:1.5}
.bottom-line .bottom-line-lead{color:var(--muted);font-size:14px}
.bottom-line q{font-style:italic}
.reconstruction{font:22px/1.45 "Newsreader",Georgia,serif;margin:0 0 8px}
.ledger{margin:0;padding:0;list-style:none}
.ledger li{padding:10px 0;border-top:1px dashed var(--rule)}
.fragment{font-family:"Newsreader",Georgia,serif;font-size:19px;text-decoration:line-through}
.status,.tag{font:12px "IBM Plex Mono",ui-monospace,monospace;padding:2px 8px;border-radius:999px;background:#ECE8DE}
.reason{margin:6px 0 0}
.verdict-label{font:600 40px/1.1 "Newsreader",Georgia,serif;margin:0 0 8px}
.flip-table{width:100%;border-collapse:collapse;font-size:14px}
.flip-table th,.flip-table td{text-align:left;padding:8px;border-bottom:1px solid var(--rule);vertical-align:top}
.flip-table tr.flips td:first-child{color:var(--flips);font-weight:600}
.flip-table tr.holds td:first-child{color:var(--holds);font-weight:600}
.citation-list{margin:0;padding:0;list-style:none;font-size:14px}
.citation-list li{padding:10px 0;border-bottom:1px solid var(--rule)}
.series,.figure,code{font-family:"IBM Plex Mono",ui-monospace,monospace}
.provenance,.caveat,.operation,.considered,.hint,.claim-id{color:var(--muted);font-size:14px;margin:4px 0 0}
.derived-element{border:1px dashed #B8B2A5;border-radius:10px;padding:14px 16px;margin:0 0 12px}
.verify-form{display:flex;flex-direction:column;gap:12px}
.verify-form .row{display:flex;gap:16px;flex-wrap:wrap}
.verify-form .row>div{flex:1 1 200px;display:flex;flex-direction:column;gap:4px}
label{font-weight:600;font-size:14px}
textarea,input,select{font:inherit;padding:10px 12px;border:1px solid #B8B2A5;border-radius:8px;
background:#fff;min-height:44px}
button{font:inherit;font-weight:600;min-height:48px;padding:0 24px;border:0;border-radius:10px;
background:var(--ink);color:var(--card);cursor:pointer;align-self:flex-start}
.form-problem{background:#EFD9D5;color:var(--flips);padding:12px 16px;border-radius:8px}
.citations>.caveat{background:#ECE8DE;color:#3A3732;padding:10px 14px;border-radius:8px;margin:8px 0}
@media (max-width:480px){
header.site{gap:12px;padding:12px 16px}
header.site nav a{padding:12px 6px}
main{padding:24px 16px}
h1{font-size:26px}
blockquote{font-size:21px}
.reconstruction{font-size:19px}
.reconstruction-and-ledger{padding:16px}
.verdict-label{font-size:32px}
.flip-table thead{display:none}
.flip-table tr{display:block;padding:8px 0;border-bottom:1px solid var(--rule)}
.flip-table td{display:block;border:0;padding:2px 0}
.flip-table td:nth-child(2){font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:13px}
.flip-table td:nth-child(3){color:var(--muted)}
}
.queue{margin:0;padding:0;list-style:none}
.queue li{padding:14px 0;border-bottom:1px solid var(--rule)}
.queue-claim{font:19px/1.4 "Newsreader",Georgia,serif}
.sign-off{border-top:2px solid var(--ink);padding-top:20px}
fieldset.decisions{border:0;padding:0;margin:0;display:flex;gap:12px;flex-wrap:wrap}
fieldset.decisions legend{font-weight:600;font-size:14px;padding:0 0 8px}
.decision{flex:1 1 180px;display:flex;flex-direction:column;gap:2px;padding:12px 14px;
border:1px solid var(--rule);border-radius:10px;background:var(--card);min-height:44px;font-weight:600}
"""


def _page(status: int, title: str, content: str) -> Response:
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · grounding</title>
<style>{_STYLE}</style>
</head>
<body>
<header class="site"><a class="mark" href="/">grounding</a>
<nav aria-label="Primary"><a href="/">Verify</a> <a href="/queue">Sign-off queue</a></nav></header>
<main>
<h1>{html.escape(title)}</h1>
{content}
</main>
</body>
</html>
"""
    return Response(status, body, (("Content-Type", "text/html; charset=utf-8"), *_SECURITY_HEADERS))


def _not_allowed(allowed: str) -> Response:
    page = _page(405, "Method not allowed", "<p>This page does not accept that request.</p>")
    return Response(page.status, page.body, (*page.headers, ("Allow", allowed)))


def _too_large() -> Response:
    return _page(413, "Too large", "<p>That form is larger than any claim.</p>")


def _refuse_cross_origin(headers: dict[str, str]) -> Response | None:
    """A POST from another site's page is refused, not processed.

    `Sec-Fetch-Site` decides when the browser sent it. It is set by the
    browser and cannot be set by page script, and it says directly whether the
    request came from this origin. Only `same-origin` passes: `same-site`
    (another port on this machine), `cross-site`, and `none` (not initiated by
    a page at all) are all refused.

    Without it, `Origin` decides, as it did before browsers sent the fetch
    metadata. A missing `Origin` is allowed, because non-browser clients send
    none and nothing then says the post is foreign. A different host is
    refused. So is `null`, the opaque origin of a sandboxed frame or a `file:`
    page, and also what a browser sends for a POST from a page whose referrer
    policy is `no-referrer`. That last case is why this UI no longer uses that
    policy.
    """
    refused = _page(403, "Refused", "<p>This form can only be submitted from this site.</p>")
    fetch_site = headers.get("sec-fetch-site")
    if fetch_site is not None:
        return None if fetch_site == "same-origin" else refused
    origin = headers.get("origin")
    if origin is None:
        return None
    if origin == "null" or urlsplit(origin).netloc != headers.get("host", ""):
        return refused
    return None


# -- the socket adapter -----------------------------------------------------------


def make_server(app: App, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "grounding"
        sys_version = ""

        def do_GET(self) -> None:  # noqa: N802 -- http.server's naming
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def _dispatch(self, method: str) -> None:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0:
                response = _page(400, "Bad request", "<p>Unreadable request length.</p>")
            elif length > MAX_BODY:
                response = _too_large()
            else:
                body = self.rfile.read(length) if length else b""
                headers = {k.lower(): v for k, v in self.headers.items()}
                response = app.handle(method, self.path, headers, body)
            payload = response.body.encode("utf-8")
            self.send_response(response.status)
            for name, value in response.headers:
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            if getattr(self.server, "quiet", False):
                return
            super().log_message(format, *args)

    return ThreadingHTTPServer((host, port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="serve", description="Serve the local web UI for verifying and reading back claims."
    )
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to bind; the default keeps the UI on this machine")
    parser.add_argument("--port", type=int, default=8000, help="port to listen on; 0 picks a free one")
    parser.add_argument("--packs", default=DEFAULT_PACKS, help="directory of pack files")
    parser.add_argument("--store", default=DEFAULT_STORE, metavar="PATH",
                        help="retrieval store; must be a file, since the UI reads claims back")
    parser.add_argument("--live", action="store_true",
                        help="also wire adapters for custodians this deployment can reach")
    args = parser.parse_args(argv)

    try:
        app = App(args.packs, args.store, live=args.live)
    except OperatorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        server = make_server(app, args.host, args.port)
    except OSError as exc:
        print(f"error: cannot listen on {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 2

    host, port = server.server_address[:2]
    print(f"grounding web UI on http://{host}:{port}/  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
