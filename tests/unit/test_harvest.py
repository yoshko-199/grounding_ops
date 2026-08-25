"""The harvest plugin, and specifically the four places it diverges from the
prior art it was adapted from.

Each divergence gets a negative test as well as a positive one, on the
discipline the rest of this suite follows: a check that has never been seen to
fail is a check nobody has confirmed is running.
"""

from __future__ import annotations

import json
import pathlib
from datetime import date, datetime, timedelta, timezone

import pytest

from plugins.harvest import backends, corpus, scan
from plugins.harvest.cache import EXPIRED, HarvestCache, ttl_for
from plugins.harvest.outcome import FetchOutcome, Reach
from plugins.harvest.records import (
    CandidateClaim,
    DatePrecision,
    Provenance,
    TextTransform,
    UndatedClaim,
)
from plugins.harvest.sources import (
    Backend,
    BackendKind,
    InvalidSource,
    Source,
    load_source,
    load_sources,
)
from plugins.harvest.transport import RecordedTransport, Response, TransportError

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCES = ROOT / "sources"
NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def _provenance(**overrides) -> Provenance:
    fields = {
        "source_id": "fixture",
        "account": "alpha",
        "backend": "rss",
        "url": "https://feeds.example.invalid/alpha/1",
        "fetched_at": NOW,
    }
    fields.update(overrides)
    return Provenance(**fields)


def _source(**overrides) -> Source:
    fields = {
        "id": "fixture",
        "name": "Fixture",
        "accounts": ("alpha",),
        "backends": (
            Backend(kind=BackendKind.RSS, url_template="https://a.example.invalid/{account}/rss"),
        ),
        "cadence": "daily",
        "date_precision": DatePrecision.EXACT,
        "enabled": True,
    }
    fields.update(overrides)
    return Source(**fields)


# ---------------------------------------------------------------------------
# Divergence 1 — a failed scan returns a reason, never an empty list
# ---------------------------------------------------------------------------


def test_reached_with_no_items_cannot_be_constructed() -> None:
    """The state the prior art's ``[]`` return silently occupies."""
    with pytest.raises(ValueError, match="ambiguous state"):
        FetchOutcome(Reach.REACHED, "rss", items=())


def test_a_non_result_must_say_why() -> None:
    with pytest.raises(ValueError, match="must say why"):
        FetchOutcome(Reach.UNREACHABLE, "rss")


def test_a_non_result_cannot_carry_items() -> None:
    claim = CandidateClaim(text="prices rose", raw="prices rose", provenance=_provenance())
    with pytest.raises(ValueError, match="cannot carry items"):
        FetchOutcome(Reach.REACHED_EMPTY, "rss", items=(claim,), detail="x")


def test_transport_failure_is_unreachable_not_empty() -> None:
    transport = RecordedTransport(
        {"https://a.example.invalid/alpha/rss": TransportError("connection reset")}
    )
    outcome = backends.fetch(
        _source(), "alpha", _source().backends[0], transport, now=NOW
    )
    assert outcome.reach is Reach.UNREACHABLE
    assert "connection reset" in outcome.detail


def test_a_404_is_reached_empty_but_a_500_is_not() -> None:
    """The split that makes the tri-state worth having.

    Both answer with no items. One is the source saying there is nothing at
    that address; the other is the source saying nothing at all.
    """
    source = _source()
    absent = RecordedTransport(
        {"https://a.example.invalid/alpha/rss": Response(404, "", "u")}
    )
    broken = RecordedTransport(
        {"https://a.example.invalid/alpha/rss": Response(503, "", "u")}
    )
    assert (
        backends.fetch(source, "alpha", source.backends[0], absent, now=NOW).reach
        is Reach.REACHED_EMPTY
    )
    assert (
        backends.fetch(source, "alpha", source.backends[0], broken, now=NOW).reach
        is Reach.UNREACHABLE
    )


def test_an_unparseable_body_is_unreachable_not_empty() -> None:
    """A feed that changed format must not read as an account that went quiet."""
    source = _source()
    transport = RecordedTransport(
        {"https://a.example.invalid/alpha/rss": Response(200, "<html>nope", "u")}
    )
    outcome = backends.fetch(source, "alpha", source.backends[0], transport, now=NOW)
    assert outcome.reach is Reach.UNREACHABLE


def test_a_well_formed_empty_feed_is_reached_empty() -> None:
    source = _source()
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": Response(
                200, "<rss><channel></channel></rss>", "u"
            )
        }
    )
    outcome = backends.fetch(source, "alpha", source.backends[0], transport, now=NOW)
    assert outcome.reach is Reach.REACHED_EMPTY


# ---------------------------------------------------------------------------
# Divergence 2 — the cache expires and never serves stale
# ---------------------------------------------------------------------------


def test_cache_serves_within_ttl_and_refuses_after() -> None:
    cache = HarvestCache(None)
    claim = CandidateClaim(text="prices rose", raw="prices rose", provenance=_provenance())
    key = HarvestCache.key("fixture", "alpha", "rss")
    cache.record(key, backend="rss", claims=(claim,), cadence="daily", now=NOW)

    assert cache.fresh(key, NOW + timedelta(hours=1)) is not EXPIRED
    assert cache.fresh(key, NOW + timedelta(days=2)) is EXPIRED
    assert cache.expired_on_read == 1


def test_expired_and_never_fetched_are_distinguishable() -> None:
    """They lead to the same action for different reasons.

    Collapsing them into ``None`` would make the TTL invisible in the code
    that depends on it, which is the argument ``engine/store/events.py`` makes
    for its own sentinel.
    """
    cache = HarvestCache(None)
    key = HarvestCache.key("fixture", "alpha", "rss")
    assert cache.fresh(key, NOW) is None

    claim = CandidateClaim(text="x", raw="x", provenance=_provenance())
    cache.record(key, backend="rss", claims=(claim,), cadence="daily", now=NOW)
    assert cache.fresh(key, NOW + timedelta(days=2)) is EXPIRED


def test_an_unknown_cadence_gets_the_shortest_ttl() -> None:
    """Erring short costs a re-fetch; erring long serves something stale."""
    assert ttl_for("every so often") == ttl_for("continuous") or ttl_for(
        "every so often"
    ) <= ttl_for("daily")
    assert ttl_for("") < ttl_for("monthly")


def test_an_expired_entry_is_refetched_rather_than_served(tmp_path) -> None:
    source = _source(cadence="daily")
    body = _rss("prices rose in 2021", "https://a.example.invalid/alpha/1")
    transport = RecordedTransport({"https://a.example.invalid/alpha/rss": Response(200, body, "u")})
    cache = HarvestCache(None)

    first = scan.scan((source,), transport, cache, now=NOW)
    assert first.reports[0].served_from_cache is False

    cached = scan.scan((source,), transport, cache, now=NOW + timedelta(hours=1))
    assert cached.reports[0].served_from_cache is True
    assert len(transport.requested) == 1

    later = scan.scan((source,), transport, cache, now=NOW + timedelta(days=3))
    assert later.reports[0].served_from_cache is False
    assert len(transport.requested) == 2


def test_cache_survives_a_round_trip_through_a_file(tmp_path) -> None:
    path = tmp_path / "cache.json"
    cache = HarvestCache(path)
    claim = CandidateClaim(
        text="prices rose",
        raw="prices rose",
        provenance=_provenance(),
        published_at=date(2021, 6, 1),
        date_precision=DatePrecision.EXACT,
    )
    key = HarvestCache.key("fixture", "alpha", "rss")
    cache.record(key, backend="rss", claims=(claim,), cadence="daily", now=NOW)
    cache.flush()

    reloaded = HarvestCache(path)
    entry = reloaded.fresh(key, NOW + timedelta(hours=1))
    assert entry is not None and entry is not EXPIRED
    assert entry.claims[0].text == "prices rose"


def test_an_unreadable_cache_is_an_empty_cache(tmp_path) -> None:
    path = tmp_path / "cache.json"
    path.write_text("{not json", encoding="utf-8")
    assert HarvestCache(path).fresh(HarvestCache.key("a", "b", "c"), NOW) is None


# ---------------------------------------------------------------------------
# Divergence 3 — every record carries its provenance and its transforms
# ---------------------------------------------------------------------------


def _rss(description: str, link: str, pub: str = "Tue, 01 Jun 2021 10:00:00 +0000") -> str:
    return (
        "<rss><channel>"
        f"<item><description>{description}</description>"
        f"<link>{link}</link><pubDate>{pub}</pubDate></item>"
        "</channel></rss>"
    )


def test_stripping_html_is_recorded_and_the_raw_body_kept() -> None:
    source = _source()
    body = _rss("&lt;b&gt;prices&lt;/b&gt;   rose", "https://a.example.invalid/alpha/1")
    transport = RecordedTransport({"https://a.example.invalid/alpha/rss": Response(200, body, "u")})
    claim = backends.fetch(source, "alpha", source.backends[0], transport, now=NOW).items[0]

    assert claim.text == "prices rose"
    assert claim.raw == "<b>prices</b>   rose"
    assert TextTransform.HTML_STRIPPED in claim.transforms
    assert TextTransform.WHITESPACE_COLLAPSED in claim.transforms


def test_entity_decoding_is_recorded_when_it_happens() -> None:
    """Separately from tag stripping, because they are different edits.

    An RSS body arrives already entity-decoded by the XML parser, so this
    needs a backend whose payload carries the entity through to ``_clean``.
    """
    backend = Backend(
        kind=BackendKind.JSON,
        url_template="https://a.example.invalid/{account}.json",
        items_path="items",
        text_field="body",
    )
    source = _source(backends=(backend,))
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha.json": Response(
                200, json.dumps({"items": [{"body": "wages &amp; prices rose"}]}), "u"
            )
        }
    )
    claim = backends.fetch(source, "alpha", backend, transport, now=NOW).items[0]
    assert claim.text == "wages & prices rose"
    assert claim.raw == "wages &amp; prices rose"
    assert TextTransform.ENTITIES_DECODED in claim.transforms


def test_text_that_needs_no_cleaning_records_no_transforms() -> None:
    """The negative control: transforms are recorded, not asserted by habit."""
    backend = Backend(
        kind=BackendKind.JSON,
        url_template="https://a.example.invalid/{account}.json",
        items_path="items",
        text_field="body",
    )
    source = _source(backends=(backend,))
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha.json": Response(
                200, json.dumps({"items": [{"body": "prices rose in 2021"}]}), "u"
            )
        }
    )
    claim = backends.fetch(source, "alpha", backend, transport, now=NOW).items[0]
    assert claim.transforms == ()
    assert claim.text == claim.raw


def test_every_claim_names_the_backend_that_produced_it() -> None:
    source = _source()
    body = _rss("prices rose", "https://a.example.invalid/alpha/1")
    transport = RecordedTransport({"https://a.example.invalid/alpha/rss": Response(200, body, "u")})
    claim = backends.fetch(source, "alpha", source.backends[0], transport, now=NOW).items[0]
    assert claim.provenance.backend == "rss"
    assert claim.provenance.account == "alpha"
    assert claim.provenance.source_id == "fixture"


def test_provenance_rejects_a_blank_field() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _provenance(backend="  ")


# ---------------------------------------------------------------------------
# Dating — the property the surveyed aggregator's own about page motivated
# ---------------------------------------------------------------------------


def test_an_approximate_date_refuses_to_become_a_stated_at() -> None:
    claim = CandidateClaim(
        text="prices rose",
        raw="prices rose",
        provenance=_provenance(),
        published_at=date(2021, 6, 1),
        date_precision=DatePrecision.APPROXIMATE,
    )
    with pytest.raises(UndatedClaim, match="different question"):
        claim.stated_at()


def test_an_exact_date_is_handed_over() -> None:
    claim = CandidateClaim(
        text="prices rose",
        raw="prices rose",
        provenance=_provenance(),
        published_at=date(2021, 6, 1),
        date_precision=DatePrecision.EXACT,
    )
    assert claim.stated_at() == date(2021, 6, 1)


def test_a_date_with_unstated_precision_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="how precisely"):
        CandidateClaim(
            text="x",
            raw="x",
            provenance=_provenance(),
            published_at=date(2021, 6, 1),
            date_precision=DatePrecision.UNKNOWN,
        )


def test_a_precision_claim_about_no_date_is_rejected() -> None:
    with pytest.raises(ValueError, match="precision claim about nothing"):
        CandidateClaim(
            text="x", raw="x", provenance=_provenance(), date_precision=DatePrecision.EXACT
        )


def test_a_source_that_states_no_precision_caps_its_records_at_approximate() -> None:
    """A well-formed timestamp of unstated provenance is not an exact date."""
    source = _source(date_precision=DatePrecision.UNKNOWN)
    body = _rss("prices rose", "https://a.example.invalid/alpha/1")
    transport = RecordedTransport({"https://a.example.invalid/alpha/rss": Response(200, body, "u")})
    claim = backends.fetch(source, "alpha", source.backends[0], transport, now=NOW).items[0]
    assert claim.date_precision is DatePrecision.APPROXIMATE
    with pytest.raises(UndatedClaim):
        claim.stated_at()


def test_an_item_with_no_date_is_unknown_rather_than_guessed() -> None:
    source = _source()
    body = (
        "<rss><channel><item><description>prices rose</description>"
        "<link>https://a.example.invalid/alpha/1</link></item></channel></rss>"
    )
    transport = RecordedTransport({"https://a.example.invalid/alpha/rss": Response(200, body, "u")})
    claim = backends.fetch(source, "alpha", source.backends[0], transport, now=NOW).items[0]
    assert claim.date_precision is DatePrecision.UNKNOWN
    assert claim.published_at is None


# ---------------------------------------------------------------------------
# Backends — the three shapes, and the one that is absent
# ---------------------------------------------------------------------------


def test_json_backend_walks_a_dotted_path() -> None:
    backend = Backend(
        kind=BackendKind.JSON,
        url_template="https://a.example.invalid/{account}.json",
        items_path="data.items",
        text_field="body",
        url_field="permalink",
        date_field="published",
    )
    source = _source(backends=(backend,))
    payload = json.dumps(
        {
            "data": {
                "items": [
                    {
                        "body": "unemployment fell in 2021",
                        "permalink": "https://a.example.invalid/x/1",
                        "published": "2021-06-01T09:00:00Z",
                    }
                ]
            }
        }
    )
    transport = RecordedTransport(
        {"https://a.example.invalid/alpha.json": Response(200, payload, "u")}
    )
    outcome = backends.fetch(source, "alpha", backend, transport, now=NOW)
    assert outcome.items[0].text == "unemployment fell in 2021"
    assert outcome.items[0].published_at == date(2021, 6, 1)


def test_embedded_json_backend_reads_a_script_tag() -> None:
    backend = Backend(
        kind=BackendKind.EMBEDDED_JSON,
        url_template="https://a.example.invalid/{account}",
        script_id="__NEXT_DATA__",
        items_path="props.pageProps.items",
        text_field="statement",
        url_field="href",
        date_field="statedOn",
        date_format="%d/%m/%Y",
    )
    source = _source(backends=(backend,))
    embedded = json.dumps(
        {
            "props": {
                "pageProps": {
                    "items": [
                        {
                            "statement": "seats rose in 2023",
                            "href": "/c/1",
                            "statedOn": "01/06/2021",
                        }
                    ]
                }
            }
        }
    )
    page = f'<html><script id="__NEXT_DATA__" type="application/json">{embedded}</script></html>'
    transport = RecordedTransport(
        {"https://a.example.invalid/alpha": Response(200, page, "u")}
    )
    outcome = backends.fetch(source, "alpha", backend, transport, now=NOW)
    assert outcome.items[0].text == "seats rose in 2023"
    assert outcome.items[0].published_at == date(2021, 6, 1)


def test_embedded_json_with_a_missing_script_is_unreachable() -> None:
    backend = Backend(
        kind=BackendKind.EMBEDDED_JSON,
        url_template="https://a.example.invalid/{account}",
        script_id="__NEXT_DATA__",
        items_path="props.items",
        text_field="statement",
    )
    source = _source(backends=(backend,))
    transport = RecordedTransport(
        {"https://a.example.invalid/alpha": Response(200, "<html></html>", "u")}
    )
    outcome = backends.fetch(source, "alpha", backend, transport, now=NOW)
    assert outcome.reach is Reach.UNREACHABLE
    assert "__NEXT_DATA__" in outcome.detail


def test_an_items_path_resolving_to_a_non_list_is_unreachable() -> None:
    backend = Backend(
        kind=BackendKind.JSON,
        url_template="https://a.example.invalid/{account}.json",
        items_path="data.items",
        text_field="body",
    )
    source = _source(backends=(backend,))
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha.json": Response(
                200, json.dumps({"data": {"items": {"body": "x"}}}), "u"
            )
        }
    )
    assert (
        backends.fetch(source, "alpha", backend, transport, now=NOW).reach
        is Reach.UNREACHABLE
    )


def test_backend_kinds_are_a_closed_set() -> None:
    with pytest.raises(ValueError):
        BackendKind("claude-agent")


# ---------------------------------------------------------------------------
# Scanning — the fallback ladder, and the ladder that does not exist
# ---------------------------------------------------------------------------


def test_the_ladder_falls_through_to_the_next_backend_of_the_same_account() -> None:
    source = _source(
        backends=(
            Backend(kind=BackendKind.RSS, url_template="https://a.example.invalid/{account}/rss"),
            Backend(
                kind=BackendKind.JSON,
                url_template="https://b.example.invalid/{account}.json",
                items_path="items",
                text_field="body",
            ),
        )
    )
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": TransportError("down"),
            "https://b.example.invalid/alpha.json": Response(
                200, json.dumps({"items": [{"body": "prices rose in 2021"}]}), "u"
            ),
        }
    )
    result = scan.scan((source,), transport, HarvestCache(None), now=NOW)
    report = result.reports[0]
    assert report.reach is Reach.REACHED
    assert report.backend_used == "json"
    assert [a.backend for a in report.attempts] == ["rss", "json"]
    assert report.attempts[0].reach is Reach.UNREACHABLE


def test_a_failed_ladder_reports_every_rung() -> None:
    """A first backend failing quietly behind a working second one is a source
    about to go dark, and the attempt list is the only place it shows."""
    source = _source(
        backends=(
            Backend(kind=BackendKind.RSS, url_template="https://a.example.invalid/{account}/rss"),
            Backend(
                kind=BackendKind.JSON,
                url_template="https://b.example.invalid/{account}.json",
                items_path="items",
                text_field="body",
            ),
        )
    )
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": TransportError("down"),
            "https://b.example.invalid/alpha.json": TransportError("also down"),
        }
    )
    report = scan.scan((source,), transport, HarvestCache(None), now=NOW).reports[0]
    assert report.reach is Reach.UNREACHABLE
    assert report.needs_retry
    assert len(report.attempts) == 2


def test_a_reached_empty_rung_makes_the_account_finished_not_broken() -> None:
    source = _source(
        backends=(
            Backend(kind=BackendKind.RSS, url_template="https://a.example.invalid/{account}/rss"),
        )
    )
    transport = RecordedTransport(
        {"https://a.example.invalid/alpha/rss": Response(404, "", "u")}
    )
    report = scan.scan((source,), transport, HarvestCache(None), now=NOW).reports[0]
    assert report.reach is Reach.REACHED_EMPTY
    assert not report.needs_retry


def test_one_source_failing_never_causes_another_to_be_consulted() -> None:
    """The distinction from §9.4's forbidden fallback, asserted.

    Backends within a source are transports to the same account. Sources are
    different publications, and substituting one for another is the move the
    engine's retrieval path is not allowed to make.
    """
    broken = _source(
        id="broken",
        backends=(
            Backend(kind=BackendKind.RSS, url_template="https://a.example.invalid/{account}/rss"),
        ),
    )
    healthy = _source(
        id="healthy",
        backends=(
            Backend(kind=BackendKind.RSS, url_template="https://c.example.invalid/{account}/rss"),
        ),
    )
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": TransportError("down"),
            "https://c.example.invalid/alpha/rss": Response(
                200, _rss("prices rose", "https://c.example.invalid/alpha/1"), "u"
            ),
        }
    )
    result = scan.scan((broken, healthy), transport, HarvestCache(None), now=NOW)

    by_source = {r.source_id: r for r in result.reports}
    assert by_source["broken"].reach is Reach.UNREACHABLE
    assert by_source["broken"].claims == ()
    assert by_source["healthy"].reach is Reach.REACHED
    # The broken source's report is not backfilled from the healthy one.
    assert all(
        claim.provenance.source_id == "healthy" for claim in result.claims
    )


def test_every_account_of_a_source_is_scanned() -> None:
    source = _source(accounts=("alpha", "beta"))
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": Response(
                200, _rss("prices rose", "https://a.example.invalid/alpha/1"), "u"
            ),
            "https://a.example.invalid/beta/rss": Response(
                200, _rss("wages fell", "https://a.example.invalid/beta/1"), "u"
            ),
        }
    )
    result = scan.scan((source,), transport, HarvestCache(None), now=NOW)
    assert {r.account for r in result.reports} == {"alpha", "beta"}
    assert len(result.claims) == 2


def test_claims_are_deduplicated_across_accounts_by_url() -> None:
    source = _source(accounts=("alpha", "beta"))
    shared = _rss("prices rose", "https://a.example.invalid/shared/1")
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": Response(200, shared, "u"),
            "https://a.example.invalid/beta/rss": Response(200, shared, "u"),
        }
    )
    result = scan.scan((source,), transport, HarvestCache(None), now=NOW)
    assert len(result.reports) == 2
    assert len(result.claims) == 1


def test_a_disabled_source_is_skipped_with_its_reason() -> None:
    source = _source(enabled=False, disabled_reason="not launched")
    transport = RecordedTransport({})
    result = scan.scan((source,), transport, HarvestCache(None), now=NOW)
    assert result.reports == ()
    assert result.skipped == (("fixture", "not launched"),)
    assert transport.requested == []


def test_a_disabled_source_is_scanned_only_when_named() -> None:
    source = _source(enabled=False, disabled_reason="not launched")
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": Response(
                200, _rss("prices rose", "https://a.example.invalid/alpha/1"), "u"
            )
        }
    )
    result = scan.scan(
        (source,),
        transport,
        HarvestCache(None),
        now=NOW,
        allow_disabled=frozenset({"fixture"}),
    )
    assert len(result.reports) == 1
    assert result.reports[0].reach is Reach.REACHED


def test_limit_bounds_what_one_account_yields() -> None:
    items = "".join(
        f"<item><description>claim {n}</description>"
        f"<link>https://a.example.invalid/alpha/{n}</link></item>"
        for n in range(5)
    )
    source = _source()
    transport = RecordedTransport(
        {
            "https://a.example.invalid/alpha/rss": Response(
                200, f"<rss><channel>{items}</channel></rss>", "u"
            )
        }
    )
    result = scan.scan(
        (source,), transport, HarvestCache(None), now=NOW, limit_per_account=2
    )
    assert len(result.reports[0].claims) == 2


# ---------------------------------------------------------------------------
# Source declarations
# ---------------------------------------------------------------------------


def test_the_shipped_fixture_declaration_loads() -> None:
    sources = load_sources(SOURCES)
    assert [s.id for s in sources] == ["fixture"]
    fixture = sources[0]
    assert fixture.accounts == ("alpha", "beta")
    assert [b.kind.value for b in fixture.backends] == ["json", "rss", "embedded-json"]


def test_the_shipped_fixture_is_disabled() -> None:
    """It points at a reserved domain, and a stray run must reach nothing."""
    fixture = load_sources(SOURCES)[0]
    assert fixture.enabled is False
    assert fixture.disabled_reason.strip()
    assert all("example.invalid" in b.url_template for b in fixture.backends)


def test_a_disabled_source_without_a_reason_does_not_load(tmp_path) -> None:
    path = tmp_path / "s.toml"
    path.write_text(
        '[source]\nid="x"\nname="X"\naccounts=["a"]\nenabled=false\n'
        '[[backend]]\nkind="rss"\nurl_template="https://x.example.invalid/{account}"\n',
        encoding="utf-8",
    )
    with pytest.raises(InvalidSource, match="gives no reason"):
        load_source(path)


def test_an_unknown_backend_kind_does_not_load(tmp_path) -> None:
    path = tmp_path / "s.toml"
    path.write_text(
        '[source]\nid="x"\nname="X"\naccounts=["a"]\nenabled=true\n'
        '[[backend]]\nkind="claude-agent"\nurl_template="https://x.example.invalid/"\n',
        encoding="utf-8",
    )
    with pytest.raises(InvalidSource, match="unknown kind"):
        load_source(path)


def test_a_source_with_no_backends_does_not_load(tmp_path) -> None:
    path = tmp_path / "s.toml"
    path.write_text(
        '[source]\nid="x"\nname="X"\naccounts=["a"]\nenabled=true\n', encoding="utf-8"
    )
    with pytest.raises(InvalidSource, match="no backends"):
        load_source(path)


def test_a_json_backend_without_a_text_field_does_not_load(tmp_path) -> None:
    path = tmp_path / "s.toml"
    path.write_text(
        '[source]\nid="x"\nname="X"\naccounts=["a"]\nenabled=true\n'
        '[[backend]]\nkind="json"\nurl_template="https://x.example.invalid/"\n'
        'items_path="items"\n',
        encoding="utf-8",
    )
    with pytest.raises(InvalidSource, match="text_field"):
        load_source(path)


def test_duplicate_source_ids_do_not_load(tmp_path) -> None:
    body = (
        '[source]\nid="dup"\nname="D"\naccounts=["a"]\nenabled=true\n'
        '[[backend]]\nkind="rss"\nurl_template="https://x.example.invalid/{account}"\n'
    )
    (tmp_path / "a.toml").write_text(body, encoding="utf-8")
    (tmp_path / "b.toml").write_text(body, encoding="utf-8")
    with pytest.raises(InvalidSource, match="duplicate source id"):
        load_sources(tmp_path)


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


def _claim(text: str, url: str) -> CandidateClaim:
    return CandidateClaim(text=text, raw=text, provenance=_provenance(url=url))


def test_corpus_round_trips(tmp_path) -> None:
    path = tmp_path / "claims.jsonl"
    claims = (_claim("prices rose", "u/1"), _claim("wages fell", "u/2"))
    assert corpus.write(path, claims) == 2
    assert tuple(c.text for c in corpus.read(path)) == ("prices rose", "wages fell")


def test_a_missing_corpus_is_empty_rather_than_an_error(tmp_path) -> None:
    assert corpus.read(tmp_path / "nothing.jsonl") == ()


def test_merging_updates_in_place_rather_than_appending(tmp_path) -> None:
    """Two records for one claim would inflate the denominator of any coverage
    measurement taken against the corpus."""
    existing = (_claim("prices rose", "u/1"), _claim("wages fell", "u/2"))
    revised = (_claim("prices rose sharply", "u/1"), _claim("seats rose", "u/3"))
    merged = corpus.merge(existing, revised)
    assert [c.text for c in merged] == ["prices rose sharply", "wages fell", "seats rose"]


def test_a_corrupt_corpus_line_names_itself(tmp_path) -> None:
    path = tmp_path / "claims.jsonl"
    path.write_text('{"text": "ok"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="claims.jsonl:1"):
        corpus.read(path)


def test_a_claim_round_trips_through_its_dict_form() -> None:
    original = CandidateClaim(
        text="prices rose",
        raw="<b>prices</b> rose",
        provenance=_provenance(),
        transforms=(TextTransform.HTML_STRIPPED,),
        published_at=date(2021, 6, 1),
        date_precision=DatePrecision.EXACT,
    )
    restored = CandidateClaim.from_dict(original.to_dict())
    assert restored == original
