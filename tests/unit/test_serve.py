"""The local web UI (`cli/serve.py`).

Most of these call `App.handle` directly, since the app is a pure function of
a request. One test goes through a real socket, because the adapter between
`http.server` and `handle` is code too.

The artifact rules are asserted where they are enforced, on
`Artifact.render_html()` in the conformance suite. What is asserted here is
that the web UI serves that render and nothing in place of it: the ledger
arrives with the reconstruction, Insufficient Data is a 200 in the same
container, and an operator error is never presented as a verdict.
"""

from __future__ import annotations

import pathlib
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from cli.compose import OperatorError
from cli.serve import MAX_BODY, App, make_server, record_html
from engine.render.figures import _NUMERAL

PACKS = str(pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture")
WORKED = "prices rose over the last three years due to governmental incompetence"
FLAT = "you dont see a curve therfore the earth is flat"
FORM = {"content-type": "application/x-www-form-urlencoded", "host": "127.0.0.1:8000"}


@pytest.fixture
def app(tmp_path) -> App:
    return App(PACKS, str(tmp_path / "store.db"))


def _post(app: App, headers=FORM, **fields):
    body = urllib.parse.urlencode(fields).encode("utf-8")
    return app.handle("POST", "/verify", dict(headers), body)


def _claim_id(page: str) -> str:
    return re.search(r"Claim <code>([0-9a-f-]+)</code>", page).group(1)


def _section(page: str, css_class: str) -> str:
    start = page.index(f'<section class="{css_class}">')
    return page[start:page.index("</section>", start)]


# -- the form -------------------------------------------------------------------


def test_the_form_lists_the_loaded_jurisdictions(app) -> None:
    response = app.handle("GET", "/", {}, b"")
    assert response.status == 200
    assert '<option value="ZZ">ZZ</option>' in response.body
    assert 'action="/verify"' in response.body


def test_every_page_carries_a_restrictive_content_security_policy(app) -> None:
    headers = dict(app.handle("GET", "/", {}, b"").headers)
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert "form-action 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"


# -- verifying ------------------------------------------------------------------


def test_the_worked_example_serves_the_artifact_with_its_ledger(app) -> None:
    response = _post(app, claim=WORKED, jurisdiction="ZZ", language="en", stated_at="2022-01-01")
    assert response.status == 200
    assert "MISLEADING" in _section(response.body, "verdict")
    frame = _section(response.body, "reconstruction-and-ledger")
    assert 'class="reconstruction"' in frame
    for fragment in ("due to", "incompetence"):
        assert fragment in frame


def test_insufficient_data_is_a_200_in_the_verdict_container(app) -> None:
    """§7.5: an answer, not a failure. No error status and no error page."""
    response = _post(app, claim=FLAT, jurisdiction="ZZ", language="en")
    assert response.status == 200
    assert "INSUFFICIENT DATA" in _section(response.body, "verdict")
    assert 'class="form-problem"' not in response.body


def test_an_operator_error_is_a_form_problem_never_a_verdict(app) -> None:
    response = _post(app, claim=WORKED, jurisdiction="ZZ", language="not a code")
    assert response.status == 400
    assert 'class="form-problem"' in response.body
    assert '<section class="verdict">' not in response.body
    # The operator's input survives, so it can be corrected rather than retyped.
    assert WORKED in response.body


def test_a_malformed_date_is_a_form_problem(app) -> None:
    response = _post(app, claim=WORKED, stated_at="yesterday")
    assert response.status == 400
    assert "not a date" in response.body


def test_an_empty_claim_is_a_form_problem(app) -> None:
    response = _post(app, claim="   ")
    assert response.status == 400
    assert "the claim is empty" in response.body


def test_claim_text_is_escaped(app) -> None:
    response = _post(app, claim="<script>alert(1)</script> prices rose", jurisdiction="ZZ")
    assert response.status == 200
    assert "<script>" not in response.body
    assert "&lt;script&gt;" in response.body


def test_attribution_is_shown_after_the_artifact_and_never_routed(app) -> None:
    response = _post(app, claim=WORKED, jurisdiction="ZZ", claimant="A. Speaker", venue="Radio")
    assert response.status == 200
    assert response.body.index('<section class="attribution">') > response.body.index("</article>")
    assert "A. Speaker" in _section(response.body, "attribution")


# -- reading back ---------------------------------------------------------------


def test_a_verified_claim_reads_back_from_the_store(app) -> None:
    claim_id = _claim_id(_post(app, claim=WORKED, jurisdiction="ZZ", stated_at="2022-01-01").body)
    response = app.handle("GET", f"/claim/{claim_id}", {}, b"")
    assert response.status == 200
    assert "Stored record" in response.body
    frame = _section(response.body, "reconstruction-and-ledger")
    assert "due to" in frame and "incompetence" in frame
    assert "MISLEADING" in _section(response.body, "verdict")


def test_the_read_back_page_adds_no_numeral_the_stored_text_render_lacks(app, tmp_path) -> None:
    """The M1 rule, applied to the stored path: `record_html` may show only
    what `cli/show.py` would print from the same rows."""
    from html.parser import HTMLParser

    from cli.show import _load, _render
    from engine.store.events import RetrievalStore

    claim_id = _claim_id(_post(app, claim=WORKED, jurisdiction="ZZ", stated_at="2022-01-01").body)
    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        record = _load(store, claim_id)
    finally:
        store.close()

    class _Text(HTMLParser):
        parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    parser = _Text()
    parser.parts = []
    parser.feed(record_html(record))
    shown = set(_NUMERAL.findall(" ".join(parser.parts)))
    allowed = set(_NUMERAL.findall(_render(record)))
    assert shown <= allowed, sorted(shown - allowed)


def test_an_unknown_claim_is_a_404(app) -> None:
    response = app.handle("GET", "/claim/00000000-0000-0000-0000-000000000000", {}, b"")
    assert response.status == 404


def test_a_malformed_claim_id_is_a_404_not_a_query(app) -> None:
    response = app.handle("GET", "/claim/' OR 1=1 --", {}, b"")
    assert response.status == 404


# -- what is refused ----------------------------------------------------------


def test_unknown_paths_and_wrong_methods(app) -> None:
    assert app.handle("GET", "/nope", {}, b"").status == 404
    assert app.handle("GET", "/verify", {}, b"").status == 405
    assert app.handle("POST", "/", {}, b"").status == 405


def test_a_cross_origin_post_is_refused(app) -> None:
    headers = dict(FORM, origin="https://elsewhere.example")
    assert _post(app, headers=headers, claim=WORKED).status == 403
    assert _post(app, headers=dict(FORM, origin="null"), claim=WORKED).status == 403


def test_a_same_origin_post_is_accepted(app) -> None:
    headers = dict(FORM, origin="http://127.0.0.1:8000")
    assert _post(app, headers=headers, claim=WORKED, jurisdiction="ZZ").status == 200


def test_an_oversized_form_is_refused(app) -> None:
    response = app.handle("POST", "/verify", dict(FORM), b"claim=" + b"x" * MAX_BODY)
    assert response.status == 413


def test_a_non_form_body_is_refused(app) -> None:
    headers = dict(FORM, **{"content-type": "application/json"})
    assert app.handle("POST", "/verify", headers, b"{}").status == 415


def test_an_in_memory_store_is_refused_at_startup() -> None:
    with pytest.raises(OperatorError, match="durable store"):
        App(PACKS, ":memory:")


def test_missing_packs_are_refused_at_startup(tmp_path) -> None:
    with pytest.raises(OperatorError, match="no pack directory"):
        App(str(tmp_path / "none"), str(tmp_path / "store.db"))


# -- through a real socket --------------------------------------------------------


def test_the_server_round_trip_over_a_socket(app) -> None:
    server = make_server(app, "127.0.0.1", 0)
    server.quiet = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    # Loopback only: an explicit empty proxy map keeps urllib off any proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{base}/", timeout=10) as response:
            assert response.status == 200
            assert b'action="/verify"' in response.read()

        data = urllib.parse.urlencode(
            {"claim": WORKED, "jurisdiction": "ZZ", "stated_at": "2022-01-01"}
        ).encode()
        with opener.open(f"{base}/verify", data=data, timeout=30) as response:
            page = response.read().decode("utf-8")
            assert "MISLEADING" in page
        claim_id = _claim_id(page)

        with opener.open(f"{base}/claim/{claim_id}", timeout=10) as response:
            assert b"Stored record" in response.read()

        with pytest.raises(urllib.error.HTTPError) as refused:
            opener.open(f"{base}/nope", timeout=10)
        assert refused.value.code == 404
    finally:
        server.shutdown()
        server.server_close()


# -- the sign-off queue (§9.1) ----------------------------------------------------


def _verified(app, claim=WORKED) -> str:
    return _claim_id(_post(app, claim=claim, jurisdiction="ZZ", stated_at="2022-01-01").body)


def _sign(app, claim_id, headers=FORM, **fields):
    body = urllib.parse.urlencode({"claim_id": claim_id, **fields}).encode("utf-8")
    return app.handle("POST", "/signoff", dict(headers), body)


def _rows(tmp_path, claim_id) -> dict[str, list[tuple]]:
    """Every row beneath the claim-level verdict, for before/after comparison."""
    from engine.store.events import RetrievalStore

    store = RetrievalStore(str(tmp_path / "store.db"))
    try:
        conn = store.connection
        return {
            "elements": conn.execute(
                "SELECT * FROM elements WHERE claim_id = ? ORDER BY id", (claim_id,)).fetchall(),
            "discards": conn.execute(
                "SELECT * FROM discards WHERE reconstructed_claim_id = ? ORDER BY element_id",
                (claim_id,)).fetchall(),
            "citations": conn.execute(
                "SELECT * FROM citations WHERE claim_id = ? ORDER BY position", (claim_id,)).fetchall(),
            "retrievals": conn.execute("SELECT * FROM retrievals ORDER BY id").fetchall(),
            "sweeps": conn.execute(
                "SELECT * FROM sweeps WHERE claim_id = ? ORDER BY test, alternative",
                (claim_id,)).fetchall(),
            "reconstructions": conn.execute(
                "SELECT * FROM reconstructions WHERE claim_id = ?", (claim_id,)).fetchall(),
        }
    finally:
        store.close()


def test_the_queue_lists_a_fresh_verification_with_its_full_text(app) -> None:
    long_claim = WORKED + " and this sentence runs on well past any terminal column width"
    claim_id = _verified(app, long_claim)
    page = app.handle("GET", "/queue", {}, b"").body
    assert claim_id in page
    assert long_claim in page, "the web queue must not truncate the claim"


def test_an_empty_queue_says_so(app) -> None:
    assert "Nothing is awaiting review." in app.handle("GET", "/queue", {}, b"").body


def test_a_proposed_record_offers_the_sign_off_form_and_a_decided_one_does_not(app) -> None:
    claim_id = _verified(app)
    page = app.handle("GET", f"/claim/{claim_id}", {}, b"").body
    assert '<section class="sign-off">' in page
    # The form comes after the whole record, never inside the artifact.
    assert page.index('<section class="sign-off">') > page.index("</article>")

    assert _sign(app, claim_id, action="confirm", reviewer="R. Viewer").status == 303
    page = app.handle("GET", f"/claim/{claim_id}", {}, b"").body
    assert '<section class="sign-off">' not in page


def test_confirm_round_trip(app) -> None:
    claim_id = _verified(app)
    response = _sign(app, claim_id, action="confirm", reviewer="R. Viewer")
    assert response.status == 303
    assert dict(response.headers)["Location"] == f"/claim/{claim_id}"
    page = app.handle("GET", f"/claim/{claim_id}", {}, b"").body
    assert "signed off by R. Viewer" in page
    assert "confirmed" in _section(page, "verdict")
    assert claim_id not in app.handle("GET", "/queue", {}, b"").body


def test_reject_is_recorded(app) -> None:
    claim_id = _verified(app)
    assert _sign(app, claim_id, action="reject", reviewer="R. Viewer").status == 303
    assert "rejected" in _section(app.handle("GET", f"/claim/{claim_id}", {}, b"").body, "verdict")


def test_amend_is_recorded_with_the_proposal_kept(app) -> None:
    claim_id = _verified(app)
    response = _sign(app, claim_id, action="amend", reviewer="R. Viewer",
                     label="indeterminate", rationale="the baseline choice is contested")
    assert response.status == 303
    verdict = _section(app.handle("GET", f"/claim/{claim_id}", {}, b"").body, "verdict")
    assert "INDETERMINATE" in verdict
    assert "amended from misleading: the baseline choice is contested" in verdict


def test_the_gate_refusals_are_form_problems_and_write_nothing(app) -> None:
    claim_id = _verified(app)
    refusals = [
        dict(action="amend", reviewer="R", label="indeterminate", rationale=""),
        dict(action="amend", reviewer="R", label="indeterminate", rationale="it fell 3 points"),
        dict(action="amend", reviewer="R", label="", rationale="no label chosen"),
        dict(action="amend", reviewer="R", label="misleading", rationale="unchanged label"),
        dict(action="confirm", reviewer=""),
        dict(action="publish", reviewer="R"),
        dict(action="amend", reviewer="R", label="not-a-label", rationale="x"),
    ]
    for fields in refusals:
        response = _sign(app, claim_id, **fields)
        assert response.status == 400, fields
        assert 'class="form-problem"' in response.body, fields
    # Still awaiting review: nothing was decided by any refused attempt.
    assert claim_id in app.handle("GET", "/queue", {}, b"").body


def test_a_second_decision_is_a_409_and_writes_nothing(app) -> None:
    claim_id = _verified(app)
    assert _sign(app, claim_id, action="confirm", reviewer="First").status == 303
    response = _sign(app, claim_id, action="reject", reviewer="Second")
    assert response.status == 409
    page = app.handle("GET", f"/claim/{claim_id}", {}, b"").body
    assert "signed off by First" in page
    assert "Second" not in page


def test_sign_off_changes_the_verdict_and_nothing_beneath_it(app, tmp_path) -> None:
    """AC-10 at the UI. The request also carries fields naming what lies beneath
    the verdict; they are ignored, and every row beneath is byte-identical."""
    claim_id = _verified(app)
    before = _rows(tmp_path, claim_id)
    response = _sign(
        app, claim_id, action="confirm", reviewer="R. Viewer",
        element_status="verified", retrieval_id="00000000-0000-0000-0000-000000000000",
        ledger="", discard="due to", reconstruction="Prices fell.", sweep="holds",
    )
    assert response.status == 303
    after = _rows(tmp_path, claim_id)
    assert {k: [tuple(r) for r in v] for k, v in after.items()} == {
        k: [tuple(r) for r in v] for k, v in before.items()
    }


def test_a_cross_origin_sign_off_is_refused(app) -> None:
    claim_id = _verified(app)
    headers = dict(FORM, origin="https://elsewhere.example")
    assert _sign(app, claim_id, headers=headers, action="confirm", reviewer="R").status == 403
    assert claim_id in app.handle("GET", "/queue", {}, b"").body


def test_sign_off_with_a_malformed_id_is_a_404(app) -> None:
    assert _sign(app, "not an id!", action="confirm", reviewer="R").status == 404


def test_sign_off_round_trip_over_a_socket(app) -> None:
    """The 303 is followed by a real client to the updated record."""
    server = make_server(app, "127.0.0.1", 0)
    server.quiet = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    base = f"http://{host}:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        claim_id = _verified(app)
        with opener.open(f"{base}/queue", timeout=10) as response:
            assert claim_id in response.read().decode("utf-8")
        data = urllib.parse.urlencode(
            {"claim_id": claim_id, "action": "confirm", "reviewer": "R. Viewer"}
        ).encode()
        with opener.open(f"{base}/signoff", data=data, timeout=10) as response:
            assert response.url.endswith(f"/claim/{claim_id}")
            assert "signed off by R. Viewer" in response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()


# -- what a real browser sends ------------------------------------------------------
#
# Found by driving the UI in Chrome, not by this file. Every test above built
# its request headers by hand, which tests the headers one imagines a browser
# sends. A real one, on a page whose referrer policy was `no-referrer`, sent
# `Origin: null` on the UI's own form posts, and every one was refused.


def test_pages_use_a_referrer_policy_that_keeps_the_origin_on_own_posts(app) -> None:
    """Under `no-referrer`, the Fetch standard serialises a POST's Origin as
    "null" even for a same-origin form, and the cross-origin check refuses
    "null". `same-origin` sends the real origin to this UI and nothing to any
    other site."""
    for response in (app.handle("GET", "/", {}, b""), app.handle("GET", "/queue", {}, b"")):
        assert dict(response.headers)["Referrer-Policy"] == "same-origin"


def test_sec_fetch_site_same_origin_is_accepted_even_with_an_opaque_origin(app) -> None:
    """The browser's own statement decides when it is present. Page script
    cannot set it, so it holds even if some setting forces an opaque origin."""
    headers = dict(FORM, origin="null", **{"sec-fetch-site": "same-origin"})
    assert _post(app, headers=headers, claim=WORKED, jurisdiction="ZZ").status == 200


def test_sec_fetch_site_other_than_same_origin_is_refused(app) -> None:
    for fetch_site in ("cross-site", "same-site", "none"):
        # An Origin that looks right does not rescue a request the browser
        # itself says came from elsewhere.
        headers = dict(FORM, origin="http://127.0.0.1:8000", **{"sec-fetch-site": fetch_site})
        assert _post(app, headers=headers, claim=WORKED).status == 403, fetch_site
        claim_id = "00000000-0000-0000-0000-000000000000"
        assert _sign(app, claim_id, headers=headers, action="confirm", reviewer="R").status == 403
