#!/usr/bin/env python3
"""Harvest candidate claims from declared sources into a corpus file.

    python3 scripts/harvest_corpus.py --dry-run
    python3 scripts/harvest_corpus.py --source fixture --allow-disabled fixture

The corpus this produces is a **test input** — it feeds
`docs/plan.md` §2.2, which asks whether the six derivation operations cover the
implication patterns that actually occur.  It is never read by the engine at
runtime, and the engine has no import path to the package that writes it.

Exit codes:
    0  every scanned account was reached, whether or not it had anything
    1  at least one account could not be reached
    2  the sources could not be loaded, or nothing was scanned

The distinction behind exit 1 is the one the prior art's scraper collapses.
An account that answered and has nothing is a finished job; an account nothing
could reach is a job to retry, and a harvester that exits 0 on both will run
for weeks against a dead feed while its logs look like a quiet one.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugins.harvest import corpus, scan  # noqa: E402
from plugins.harvest.cache import HarvestCache  # noqa: E402
from plugins.harvest.outcome import Reach  # noqa: E402
from plugins.harvest.records import DatePrecision  # noqa: E402
from plugins.harvest.sources import InvalidSource, load_sources  # noqa: E402
from plugins.harvest.transport import UrllibTransport  # noqa: E402

DEFAULT_SOURCES = ROOT / "sources"
DEFAULT_CORPUS = ROOT / "corpus" / "claims.jsonl"
DEFAULT_CACHE = ROOT / "corpus" / ".harvest-cache.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Harvest candidate claims from declared sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--sources", type=pathlib.Path, default=DEFAULT_SOURCES)
    parser.add_argument("--corpus", type=pathlib.Path, default=DEFAULT_CORPUS)
    parser.add_argument("--cache", type=pathlib.Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="ID",
        help="restrict to this source id; repeatable",
    )
    parser.add_argument(
        "--allow-disabled",
        action="append",
        default=[],
        metavar="ID",
        help=(
            "scan this source despite its declaration being disabled. Named one "
            "at a time on purpose: the reason a source is off is specific to it, "
            "and a blanket override is a way of not reading the reason"
        ),
    )
    parser.add_argument("--limit", type=int, default=None, metavar="N")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="scan and report, write nothing to the corpus or the cache",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.sources.is_dir():
        print(f"no source directory at {args.sources}", file=sys.stderr)
        return 2
    try:
        sources = load_sources(args.sources)
    except InvalidSource as exc:
        print(f"source declarations did not load: {exc}", file=sys.stderr)
        return 2

    if args.source:
        wanted = set(args.source)
        unknown = wanted - {s.id for s in sources}
        if unknown:
            print(f"no such source: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        sources = tuple(s for s in sources if s.id in wanted)

    cache = HarvestCache(None if args.dry_run else args.cache)
    result = scan.scan(
        sources,
        UrllibTransport(),
        cache,
        now=datetime.now(timezone.utc),
        limit_per_account=args.limit,
        allow_disabled=frozenset(args.allow_disabled),
    )

    _report(result)

    if not result.reports:
        print("\nnothing was scanned.", file=sys.stderr)
        return 2

    harvested = result.claims
    if args.dry_run:
        print(f"\ndry run — {len(harvested)} claim(s) harvested, nothing written.")
    else:
        merged = corpus.merge(corpus.read(args.corpus), harvested)
        written = corpus.write(args.corpus, merged)
        cache.flush()
        print(f"\n{len(harvested)} harvested, {written} in {args.corpus}.")

    return 1 if result.unreachable else 0


def _report(result: scan.ScanResult) -> None:
    for source_id, reason in result.skipped:
        first_line = reason.strip().splitlines()[0] if reason.strip() else ""
        print(f"  skipped  {source_id}: {first_line}")

    for report in result.reports:
        marker = {
            Reach.REACHED: "ok      ",
            Reach.REACHED_EMPTY: "empty   ",
            Reach.UNREACHABLE: "NO REACH",
        }[report.reach]
        suffix = " (cache)" if report.served_from_cache else ""
        print(
            f"  {marker} {report.source_id}/{report.account}"
            f" via {report.backend_used or '-'}{suffix}"
            f" — {len(report.claims)} claim(s)"
        )
        # Every rung of the ladder, not only the one that answered. A first
        # backend failing quietly for a month behind a working second one is a
        # source about to go dark, and this is the only place it shows.
        for attempt in report.attempts:
            if attempt.reach is not Reach.REACHED:
                print(f"             tried {attempt.backend}: {attempt.detail}")

    undated = sum(
        1
        for claim in result.claims
        if claim.date_precision is not DatePrecision.EXACT
    )
    if undated:
        print(
            f"\n  {undated} claim(s) carry no exact date and will refuse a "
            "stated_at. Anything indexed on when the claim was made — tolerance "
            "bands, continuity — cannot use them."
        )
    if result.expired_cache_entries:
        print(f"  {result.expired_cache_entries} cache entry/entries expired and were re-fetched.")


if __name__ == "__main__":
    sys.exit(main())
