# CLI reference

Four commands. All are stdlib-only and run from the repository root.

| Command | Purpose |
|---|---|
| [`cli/verify.py`](#cliverifypy) | Verify a claim against a loaded pack |
| [`cli/show.py`](#clishowpy) | Read back a stored verification by claim id, without re-verifying it |
| [`cli/signoff.py`](#clisignoffpy) | Confirm, amend, or reject a proposed verdict |
| [`scripts/harvest_corpus.py`](#scriptsharvest_corpuspy) | Harvest candidate claims from declared sources |

Two checking commands are also available:

| Command | Purpose |
|---|---|
| `python3 scripts/check_spec.py [-v]` | Document consistency checks; `-v` lists what passed |
| `python3 -m pytest tests/` | Conformance and unit suites |

---

## cli/verify.py

```
PYTHONPATH=. python3 cli/verify.py CLAIM [options]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `CLAIM` | yes | The claim text, quoted |

### Options

| Option | Default | Description |
|---|---|---|
| `--packs DIR` | `packs/fixture` | Directory of pack TOML files |
| `--jurisdiction CODE` | none | Two-letter uppercase jurisdiction hint. Used only when the claim text does not resolve one itself |
| `--language CODE` | `en` | ISO 639 code, lowercase. Selects the pack lexicon; falls back to English |
| `--stated-at DATE` | today | ISO date the claim was made |
| `--json` | off | Emit the artifact as JSON instead of text |
| `--store PATH` | `<repo>/.grounding/store.db` | Retrieval store. Durable by default, and anchored to the repository root rather than the working directory. A relative path given here is relative to the working directory. `:memory:` for a run that remembers nothing |
| `--live` | off | Also wire adapters for custodians this deployment can reach. Off by default so a fixture answer is never mistaken for a real one |
| `--claimant NAME` | none | Who said it. Displayed and stored, never routed |
| `--venue NAME` | none | Where it was said. Displayed and stored, never routed |

### What persists, and what does not

Retrievals are written to `--store` and re-read on the next run. The database
is a local artefact rather than a source of truth — every figure in it came
from a custodian and can be pulled again.

**The TTL de-duplicates records, not fetches.** A claim verified twice inside a
series' TTL still calls the custodian twice: `pull()` asks the adapter for the
series before the store is consulted at all. What the second run does *not* do
is record a second event. It reuses the stored retrieval, and therefore its
id, so both verdicts pin to the same revision — which is the §8 property that
matters. Avoiding the fetch as well would need the store to return a whole
series by identifier, and freshness is keyed on reference period, which is not
known until after the pull. That is a design change rather than a wording one,
and it has not been made.

Reuse requires an **exact** match. Every field a retrieval records — figure,
revision status, unit, custodian, continuity status, caveat, linked series — is
compared against what the pull would write, and any difference records a new
event instead. So a revision published inside the TTL supersedes the
provisional print rather than being discarded, and a cross-time claim does not
inherit the `not_applicable` continuity of an earlier level claim.

**The artifact itself is not yet stored.** `engine/store/schema.sql` declares
tables for claims, elements, verdicts, discards, reconstructions and sweeps,
and nothing writes them. A verdict still dies with the process that produced
it, so `element_set_hash` cannot yet be checked after the fact the way §8
intends.

### Case sensitivity of `--jurisdiction`

Jurisdiction codes are shape-validated: **two uppercase letters**. A value of
any other shape — `zz`, `not-a-code` — is not an error. It yields no
jurisdiction, and the run returns **Insufficient Data** with exit code `0`.

This is deliberate rather than lenient. The shape check is what stops a venue
string becoming a jurisdiction, and an unresolvable jurisdiction is a verdict
rather than a crash. The practical consequence is worth knowing: a mistyped
code and a genuinely uncovered country produce the *same* output. If you expect
a route and get Insufficient Data, check the case of the code first.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | An artifact was produced — **including Insufficient Data**, which is a verdict rather than a failure |
| `2` | A malformed `--language` or `--stated-at`, or a `--store` that cannot be opened |

A malformed `--jurisdiction` does **not** exit non-zero; see above.

An unhandled `UnsourcedFigure` or `NotQuotedFromClaim` propagates as a
traceback. Both mean output carried a numeral with nothing behind it, and both
fail the render rather than warning.

### Output sections

Emitted in this order. Sections with nothing to report say so rather than
disappearing.

| Section | Contents |
|---|---|
| `[UNCONFIRMED — ...]` | Present until a person signs the verdict off |
| `ORIGINAL CLAIM` | The claim as submitted, verbatim |
| `RECONSTRUCTED` | The claim rebuilt from verified elements only, or `does not reconstruct` |
| `DISCARD LEDGER` | Every element removed, with its status and the reason |
| `VERDICT` | The label and its rationale |
| `ROBUSTNESS SWEEP` | The flip table: each admissible alternative, and whether the conclusion holds under it |
| `CITATIONS` | One entry per retrieval: custodian, series, figure, reference period, revision status, continuity status, caveat |
| `ROUTING` | Measure, custodian, rationale, alternatives considered |
| `DERIVED ELEMENTS` | Implications extracted from the claim, tagged and marked proposed |
| `ATTRIBUTION` | Only when `--claimant` or `--venue` was given |

### Verdict labels

| Label | Meaning |
|---|---|
| `ACCURATE` | Elements verify and the conclusion holds under every admissible alternative |
| `SUBSTANTIALLY INACCURATE` | Elements fail against the record by more than tolerance |
| `MISLEADING` | Elements verify; the conclusion flips under at least one admissible alternative |
| `FALSE` | Contradicted by the record |
| `INDETERMINATE` | The sweep could not run, so robustness is unestablished |
| `INSUFFICIENT DATA` | No custodian of record settles this claim |

### Element statuses

Seen in the discard ledger.

| Status | Meaning |
|---|---|
| `verified` | Matches the retrieved figure within tolerance |
| `unverified` | The custodian was reached and publishes nothing covering the element |
| `unreachable` | The custodian could not be reached this session. A fact about the network, not the record |
| `contested_by_definition` | Two custodians publish definitionally different figures, or a break bars the comparison |
| `out_of_scope` | Causal, evaluative, or predictive content, which no record settles |

`unverified` and `unreachable` never collapse into each other.

### Derived-element tags

| Tag | Meaning |
|---|---|
| `implied-by-original-only` | Rests on elements that did not survive; it dies with them |
| `implied-by-reconstructed` | Rests on elements that verified |
| `independent` | Anchored on a span independent of the verified set |

### Derivation operations

`causal-discharge`, `inferential-discharge`, `superlative-discharge`,
`comparative-discharge`, `evaluative-discharge`, `scope-discharge`.

A closed set, versioned with the specification.

---

## cli/show.py

```
PYTHONPATH=. python3 cli/show.py CLAIM_ID [options]
```

Reads back a verification `cli/verify.py` already persisted — the claim, its
elements, its discard ledger, its latest verdict, its latest reconstruction,
its citations, its sweep rows, and its derived elements. Performs no
retrieval and resolves no route; every value comes from the store.

### Arguments

| Argument | Required | Description |
|---|---|---|
| `CLAIM_ID` | yes | The id `cli/verify.py` printed after the run to read back |

### Options

| Option | Default | Description |
|---|---|---|
| `--store PATH` | `<repo>/.grounding/store.db` | The database to read. Must match the `--store` the claim was verified against — a claim verified into `:memory:` cannot be read back at all, because nothing survived the process |
| `--json` | off | Emit the stored record as JSON instead of text |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | The claim was found and printed |
| `2` | The store could not be opened, or no claim with that id was ever recorded |

### What it does not do

`reconstructions` and `verdicts` are append-only tables (§4 Stage 7, §9.1);
this command reads only the latest row of each, not the trajectory. There is
no `--revision` flag yet. Citations are read back as an ordered list of what
a claim's artifact cited — not linked to which specific element each
retrieval verified, because a retrieval can be reused across claims inside
its TTL and the schema does not yet carry that finer relationship.

---

## cli/signoff.py

```
PYTHONPATH=. python3 cli/signoff.py ACTION --reviewer NAME --proposed LABEL [options]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `ACTION` | yes | `confirm`, `amend`, or `reject` |

### Options

| Option | Required | Description |
|---|---|---|
| `--reviewer NAME` | yes | Who is signing off |
| `--proposed LABEL` | yes | The label the pipeline proposed |
| `--label LABEL` | `amend` only | The amended label |
| `--rationale TEXT` | `amend` only | Why the label changed. The gate refuses an amendment without it |

`LABEL` is one of `accurate`, `substantially_inaccurate`, `misleading`,
`false`, `indeterminate`, `insufficient_data`.

There is deliberately no option that reaches an element status, a retrieval,
the discard ledger, the flip table, or a pack.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | The action was accepted |
| `2` | The gate refused it, or `--label` was missing for `amend` |

### Output

`state`, `label`, `reviewer`, `exportable`, plus `amended from` and
`rationale` when the label changed.

---

## scripts/harvest_corpus.py

```
python3 scripts/harvest_corpus.py [options]
```

Needs no `PYTHONPATH`; it resolves the repository root itself.

### Options

| Option | Default | Description |
|---|---|---|
| `--sources DIR` | `sources` | Directory of source TOML files |
| `--corpus PATH` | `corpus/claims.jsonl` | Corpus file to merge into |
| `--cache PATH` | `corpus/.harvest-cache.json` | Fetch cache |
| `--source ID` | all | Restrict to this source. Repeatable |
| `--allow-disabled ID` | none | Scan this source despite its declaration being disabled. Repeatable, and deliberately one at a time |
| `--limit N` | unlimited | Maximum claims per account |
| `--dry-run` | off | Scan and report; write nothing to the corpus or the cache |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Every scanned account was reached, whether or not it had anything |
| `1` | At least one account could not be reached |
| `2` | The sources could not be loaded, or nothing was scanned |

The `0` / `1` split is the distinction between *reached and empty* and *could
not reach*. A harvester that exits `0` on both runs for weeks against a dead
feed while its logs look like a quiet one.

### Report markers

| Marker | Meaning |
|---|---|
| `ok` | Reached, with claims. `(cache)` if served within TTL |
| `empty` | Reached, and the account has nothing. A finished job |
| `NO REACH` | No backend got there. A job to retry |
| `skipped` | The source is disabled; the first line of its reason follows |

Every backend attempt that did not succeed is listed beneath its account,
including the ones tried before a later backend answered.
