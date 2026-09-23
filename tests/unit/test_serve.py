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
