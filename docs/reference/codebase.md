# Codebase reference

Where things are, which module owns which rule, what may import what, and
which test would fail if a guarantee broke. For why it is arranged this way,
read [why the code is shaped this way](../architecture.md). For the words
used here, see the [glossary](glossary.md).

## Top-level layout

| Path | Holds |
|---|---|
| `engine/` | The pipeline, Stages 0–11. No network client, and no source it did not get from a loaded pack |
| `packs/` | Custodian packs as versioned TOML: `packs/fixture/` (the synthetic `ZZ` jurisdiction), `packs/demo/` (the synthetic `XD` demo), and `packs/live/` (Israel). `packs/demo-real/` holds only a fill-in template, not a pack |
| `cli/` | The composition root: the four trial-facing commands, the web UI, and the composition they share |
| `plugins/` | Code that runs beside the engine and is never part of it: the claim harvester and the claim-shape fuzzer |
| `sources/` | Harvest source declarations, all disabled as shipped |
| `scripts/` | Development tooling: `check_spec.py`, `fuzz_shapes.py`, `harvest_corpus.py` |
| `tests/` | `tests/conformance/` (one file per acceptance criterion, plus import-graph assertions) and `tests/unit/` |
| `docs/` | This documentation, and the specification under `docs/spec/` |

## Stages and the modules that own them

`engine/pipeline.py` wires the stages in the order
[§4 of the specification](../spec/claim-verification-engine.v0.5.md#4-pipeline)
fixes, and decides nothing itself.

| Stage | Name | Module |
|---|---|---|
| 0 | Ingest and the provenance split | `engine/ingest/split.py` (identity half: `engine/ingest/identity.py`) |
| 1 | Scope gate | `engine/verification/scope_gate.py` |
| 2 | Decompose into span-anchored elements | `engine/verification/decompose.py`, with surface vocabulary via `engine/verification/patterns.py` |
| 3 | Context recovery: measure binding | `engine/verification/bind.py` |
| 4 | Jurisdiction resolution and routing | `engine/verification/route.py` |
| 5 | Retrieval, the citation record, the continuity check | `engine/verification/retrieve.py`, `engine/verification/continuity.py` |
| 6 | Element verdicts, with tolerance bands | `engine/verification/element_verdict.py`, `engine/verification/tolerance.py` |
| 7 | Reconstruction | `engine/verification/reconstruct.py` |
| 8 | Robustness sweep, then the claim-level verdict | `engine/verification/sweep.py`, `engine/verification/claim_verdict.py` |
| 9 | Derived elements | `engine/verification/derive.py` |
| 10 | Persistence | `engine/store/events.py` (retrieval events); the other tables by `engine/store/writer.py` and `engine/store/identity_writer.py`, called from `cli/` |
| 11 | Sign-off | `engine/signoff.py`; persisted by `engine/store/signoff_writer.py` |

## Other engine modules

| Module | Owns |
|---|---|
| `engine/render/artifact.py` | The artifact and its only ways out: `render()`, `render_html()`, `to_dict()` |
| `engine/render/figures.py` | `Payload`, where every output numeral is checked against a retrieval |
| `engine/custodians/base.py` | The adapter contract, and `CustodianUnreachable` |
| `engine/custodians/fixture.py` | Deterministic adapters for the `ZZ` fixture jurisdiction, merged with the demo adapters |
| `engine/custodians/demo.py` | Adapters for the synthetic `XD` demo pack (`packs/demo/`). The values are invented to land the ten supplied claims on every level. One custodian has no adapter on purpose |
| `engine/custodians/boi.py` | The Bank of Israel adapter. Written and tested, and has never run live from the development environment |
| `engine/custodians/live.py` | Wiring real adapters, lazily, for the composition root |
| `engine/packs/schema.py`, `loader.py`, `registry.py` | Pack structures, parsing and validation, and the loaded set |
| `engine/elements.py`, `verdicts.py`, `figures.py`, `spans.py`, `ids.py`, `codes.py`, `context.py` | The core types. Most are frozen dataclasses; a code type rejects anything that isn't a code |

## The composition root

| Module | Does |
|---|---|
| `cli/compose.py` | The composition every front end shares: parse the date, split provenance, load packs, open the store, verify and persist, sign off a stored claim. Raises `OperatorError` for anything that is the operator's input rather than a verdict |
| `cli/verify.py` | Verify a claim. Owns `DEFAULT_STORE` and `DEFAULT_PACKS`, both anchored to the repository root |
| `cli/show.py` | Read a stored claim back, with no retrieval and no re-routing |
| `cli/signoff.py` | List proposed verdicts; confirm, amend or reject one |
| `cli/serve.py` | The local web UI on `http.server` |

Flags, routes and exit codes: [CLI reference](cli.md).

## Import rules

These are asserted on a static import graph built from source by
`tests/conformance/_graph.py`. The graph is transitive, and a path no test
happens to execute still counts.

| Rule | Asserted by |
|---|---|
| No engine module reaches a plugin | `tests/conformance/test_plugin_isolation.py` |
| No harvest module reaches the custodian adapters, the retrieval layer or the event store, and none imports the engine at all | `tests/conformance/test_plugin_isolation.py` |
| No verification module reaches a network primitive | `tests/conformance/test_ac14.py` |
| Claimant identity is unreachable from verification | `tests/conformance/test_ac06.py` |
| No verification module reaches the artifact writer or the sign-off writer, and the identity writer is the only new importer of identity | `tests/conformance/test_store_writer_isolation.py`, `tests/conformance/test_signoff_writer_isolation.py` |
| The sign-off gate reaches neither the store nor the packs | `tests/conformance/test_ac10.py`, `tests/conformance/test_signoff_writer_isolation.py` |

`cli/` is outside the analysed packages on purpose: it is where a network
primitive and a durable store are allowed to exist. Both guard families
include a test that the guard itself would catch a violation, so neither can
pass vacuously.

## Where each guarantee is enforced

| Guarantee | Specification | Enforced in | Asserted by |
|---|---|---|---|
| The reconstruction never leaves without its ledger | §7.1 | `engine/render/artifact.py`: the reconstruction is private, and every emitter carries the ledger | `test_ac01.py` |
| No platform formatting, summary or truncation | §7.2 | By absence in `engine/render/` and `cli/` | `test_ac02.py` |
| Thresholds and routing are not configurable | §7.3 | Pack data, frozen once loaded; no environment or flag surface | `test_ac03.py` |
| The routing decision is logged with its rationale and alternatives | §7.4 | `engine/verification/route.py` | `test_ac04.py` |
| Insufficient Data is first-class | §7.5 | `engine/render/artifact.py` (one verdict container); `cli/` exits `0` | `test_ac05.py` |
| No claimant metadata reaches verification | §7, §9.8.1 | `engine/ingest/split.py`; `verify()` takes a `ClaimContext` | `test_ac06.py` |
| No unsourced figure | §3 | `engine/render/figures.py`; the reconstruction check and the HTML gate in `artifact.py`; the amendment scan in `engine/signoff.py` | `test_ac07.py` |
| Expired retrievals are re-pulled, never served | §8 | `engine/store/events.py` (the `EXPIRED` sentinel), `engine/verification/retrieve.py` | `test_ac08.py` |
| A published revision invalidates a provisional retrieval | §8 | `engine/store/events.py`, `engine/verification/retrieve.py` | `test_ac09.py` |
| Sign-off changes the claim-level label and nothing beneath it | §9.1 | `engine/signoff.py`; `cli/compose.sign_off_stored` | `test_ac10.py`, and the byte-identity test in `tests/unit/test_serve.py` |
| An unrunnable sweep caps the verdict | §9.3 | `engine/verification/sweep.py`, `engine/verification/claim_verdict.py` | `test_ac11.py` |
| No verification across an unlinked series break | §9.5 | `engine/verification/continuity.py` | `test_ac12.py` |
| Tolerance is a pure function of pack data | §9.2 | `engine/verification/tolerance.py` | `test_ac13.py` |
| No generic fallback; Unreachable and Unverified never collapse | §6.1, §7 | `engine/verification/route.py`, `engine/verification/retrieve.py`, `engine/custodians/base.py` | `test_ac14.py` |
| A reconstruction is a pure function of the verified element set | §4, §9.6 | `engine/verification/reconstruct.py` | `test_ac15.py` |
| Derived elements are anchored, closed-list, and never verified | §9.7 | `engine/verification/derive.py` | `test_ac16.py` |
| Only a jurisdiction code crosses into verification, by declared rules | §9.8.2 | `engine/ingest/split.py`, `engine/verification/route.py` | `test_ac17.py` |
| Every element is anchored to a span of the claim | §9.7.1 | `engine/elements.py` (the span is required), `engine/verification/decompose.py` | `test_ac18.py` |

All `test_acNN.py` files are in `tests/conformance/`. The criteria themselves
are in [acceptance criteria](../spec/acceptance-criteria.md).

## Persistence

`engine/store/schema.sql` declares the tables, in one SQLite database that
defaults to `.grounding/store.db` under the repository root:

| Group | Tables |
|---|---|
| Reference | `packs`, `custodians`, `measures`, `series_breaks` |
| The claim | `claims`, `claim_context`, `claimant_identity` (written only by the identity writer) |
| What verification produced | `elements`, `discards`, `derived_elements`, `relationships`, `reconstructions`, `sweeps`, `routing_log` |
| Evidence | `retrievals` (events with a TTL), `citations` (a claim's ordered retrievals) |
| The decision | `verdicts`, append-only. A sign-off closes the open row's validity window and appends a new row |

## The test suite

| Location | Contains |
|---|---|
| `tests/conformance/test_acNN.py` | One file per acceptance criterion |
| `tests/conformance/_graph.py` | The static import-graph analyser |
| `tests/conformance/test_plugin_isolation.py`, `test_store_writer_isolation.py`, `test_signoff_writer_isolation.py` | Boundary assertions beyond the numbered criteria |
| `tests/conformance/test_render_paths.py` | One claim per artifact-producing branch, each rendered |
| `tests/conformance/test_shape_invariants.py` | A bounded sample of the claim-shape fuzzer, inside the suite |
| `tests/conformance/conftest.py` | Shared fixtures (listed in [add a regression test](../how-to/add-a-regression-test.md#write-it)) |
| `tests/unit/` | Module behaviour: the pack loader, stores and writers, the command line, the web UI, packaging, the harvester, the Bank of Israel adapter's parsing |

## The document checks

`python3 scripts/check_spec.py -v` runs six groups:

| Check | Fails when |
|---|---|
| Resolved decisions | A resolved decision in the specification lacks a rationale |
| Criteria | An acceptance criterion lacks a constraint, a test or a failure condition |
| Schema | The specification's schema sketch and its prose disagree on a field |
| No embedded figures | A statistic appears in prose outside a code span |
| Links | A relative link or anchor in any document does not resolve |
| Current version | An entry-point document does not point at the current specification |
