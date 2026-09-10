# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Python 3.11+, standard library only. `pyproject.toml` declares no runtime
dependencies and `pytest` is the sole dev dependency; keep it that way, since a
conformance test asserts no harvest module imports anything undeclared.

```bash
python3 -m pytest tests/ -q                      # whole suite
python3 -m pytest tests/conformance/test_ac07.py # one acceptance criterion
python3 -m pytest tests/ -k unsourced            # by name
python3 scripts/check_spec.py -v                 # document consistency, 6 groups
python3 scripts/fuzz_shapes.py --all             # every generated claim shape
python3 scripts/fuzz_shapes.py --seed 7          # a different bounded sample
```

`pyproject.toml` sets `pythonpath = ["."]`, so pytest needs no prefix. The CLIs
do:

```bash
PYTHONPATH=. python3 cli/verify.py "CLAIM" --jurisdiction ZZ --packs packs/fixture
PYTHONPATH=. python3 cli/signoff.py confirm --reviewer NAME --proposed accurate
python3 scripts/harvest_corpus.py --dry-run      # resolves the root itself
```

The full gate before any push is the three commands above plus two regression
claims that have caught more than the suite has:

```bash
PYTHONPATH=. python3 cli/verify.py "prices rose over the last three years due to governmental incompetence" --jurisdiction ZZ --packs packs/fixture
PYTHONPATH=. python3 cli/verify.py "you dont see a curve therfore the earth is flat" --jurisdiction ZZ --packs packs/fixture
```

The first must stay **Misleading** with its reconstruction intact, the second
**Insufficient Data** with its inferential discharge. CI (`.github/workflows/checks.yml`)
runs all of this, plus an assertion that the shipped harvester configuration
reaches nothing: `harvest_corpus.py --dry-run` must exit **2**, never 0.

## What this is

An implementation of `docs/spec/claim-verification-engine.v0.5.md`. A claim is
decomposed into atomic elements, each verified against a custodian of record,
and a grounded version is rebuilt from only what survived — displayed
inseparably from a ledger of what was removed and why.

The specification is the authority. Section references in code comments
(§3, §7.5, §9.6) point into it, and `docs/spec/acceptance-criteria.md` numbers
eighteen constraints AC-1…AC-18 that exist as executable tests, one file per
criterion in `tests/conformance/`. When behaviour and spec disagree, one of
them is wrong and the question is which — not which to bend.

## Architecture

**`engine/`** is the pipeline and holds no network client. `engine/pipeline.py`
orchestrates Stages 0–11 and decides nothing; every rule lives in the stage
module that owns it under `engine/verification/`. Routing binds a claim to a
measure (`route.py`, `bind.py`), retrieval records events (`retrieve.py`),
element and claim verdicts are separate stages, and the robustness sweep
produces the flip table.

**`packs/`** are versioned TOML data, not code. A pack declares who is
authoritative for which measure in which jurisdiction, plus series breaks,
tolerance inputs, admissible baselines and windows, and a per-language lexicon.
Generalising to a new jurisdiction is a pack, never an engine change.
`packs/fixture/zz.toml` is a synthetic jurisdiction whose measures are chosen
to exercise the hard paths (an unlinked break that can never verify, a discrete
count, a single-observation series, two definitionally distinct measures that
contest). It carries no figures — values live in the fixture adapter and reach
the engine only through recorded retrievals.

**`plugins/`** sits outside the engine and is the boundary worth knowing.
`plugins/harvest/` scans declared sources for candidate *claims* and may reach
the network; `plugins/shapes/` is the claim-shape fuzzer, a harness that drives
the engine. Nothing in `engine/` may reach either.

**`cli/`** is the composition root. It is where a durable store is opened and
where live adapters are wired (`engine/custodians/live.py` imports urllib
lazily for exactly this reason), so that verification can stay statically
unable to reach a network primitive.

## Invariants that shape the code

These are not style preferences. Each is asserted somewhere, and each has been
violated at least once by a change that looked correct.

**No unsourced figure.** Every numeral in every output resolves to a
`retrievals.id`. `engine/render/figures.py` scans at the render boundary and
**raises** — warning was never an option, because a warned figure still reaches
a reader who assumes it was checked. A numeral in prose fails the render, which
is why an adapter's error text goes to `PullOutcome.diagnostic` and never into
a rendered reason.

**No generic fallback.** Where no custodian covers a claim the answer is
Insufficient Data. There is no fallback pack, no fallback adapter, and no
adapter that accepts a URL. The absence is the guarantee.

**Insufficient Data is an answer, not a failure.** It exits 0 and renders as a
verdict. A non-zero exit is the error styling AC-5 forbids.

**Unverified and Unreachable never collapse.** Reached-with-nothing is a fact
about the record; could-not-reach is a fact about today's network.

**Identity never reaches verification.** `engine/ingest/split.py` splits
provenance at ingest and only a jurisdiction *code* crosses into the pipeline.
`verify()` takes a `ClaimContext`, never a `ClaimantIdentity`, and AC-6 asserts
that by static analysis.

**Retrievals are events with a TTL.** Expired records are re-pulled, never
served — no degraded mode, no grace period, no force flag. `engine/store/events.py`
returns an `EXPIRED` sentinel rather than `None` so the two reasons to re-pull
cannot be confused at a call site.

**Sign-off touches the claim-level verdict and nothing beneath it.**
`engine.signoff` can reach neither the store, the packs, nor the sweep, and
AC-10 asserts it.

## The static import graph

`tests/conformance/_graph.py` builds a transitive import closure from source
rather than at runtime, because a path never taken in a passing test is exactly
the latent failure being guarded against. It analyses `engine` and `plugins`,
and the rules asserted are: no engine module reaches a plugin; no harvest
module reaches the custodian adapters, the retrieval layer, or the event store;
no verification module reaches a network primitive; identity is unreachable
from verification. Both `test_plugin_isolation.py` and `test_ac06.py` include a
test that the guard itself would catch a violation, so the assertion cannot
pass vacuously.

Practical consequence: adding an import in `engine/verification/` can fail a
criterion rather than a unit test, and the fix is a lazy import at the
composition root, not a relaxed assertion.

## Working rules

- **Never populate pack data from recollection.** A field that cannot be
  confirmed from the custodian's own publication stays `[confirm]` and that
  thread stops. Plausible-sounding pack entries are the exact failure this
  system exists to prevent, and two have been caught already.
- **Never weaken, skip, or quarantine a test, and never widen a criterion** to
  accommodate a change. When a criterion fails, the change is wrong until
  proven otherwise.
- **Docs change in the same commit as the code.** `docs/` follows Diátaxis:
  `tutorial.md`, `how-to/`, `reference/`, and the explanatory `overview.md`.
  `scripts/check_spec.py` enforces cross-document consistency and will fail on
  a broken anchor or a statistic embedded in prose.
- The fuzzer is worth running on any change to decomposition, derivation, or
  rendering. Several defects invisible to a green conformance suite came from
  it, and it shrinks failures to the shortest claim that still reproduces.

## Environment

Outbound egress is a strict allowlist and blocks `edge.boi.gov.il` and
`boi.org.il`, so `engine/custodians/boi.py` has never run live: its tests prove
its SDMX-CSV parsing and error taxonomy, not its URL. Report a proxy 403/407
rather than routing around it, and never disable TLS verification.

`~/.claude/skills/israeli-fact-checker` is prior art and the basis for the
Israel pack's source map. **This repository does not modify it.**
