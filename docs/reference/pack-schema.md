# Pack schema

Every field of a custodian pack TOML file. One file per jurisdiction.

This is the descriptive reference; the normative contract is the
[custodian pack interface](../spec/custodian-pack-interface.md), currently
v1.2. To write one, follow
[add a jurisdiction pack](../how-to/add-a-jurisdiction-pack.md).
[`packs/fixture/zz.toml`](../../packs/fixture/zz.toml) is a complete worked
example.

**Required blocks:** `header`, `custodians`, `measures`, `routing_rules`,
`lexicons`. A pack missing any of them does not load.

**Packs carry no figures.** `published_precision` is the sole numeric field,
and it describes the custodian's reporting precision rather than a value of the
series. The loader rejects a pack whose free-text fields contain a statistic.

---

## `[header]`

| Field | Type | Required | Description |
|---|---|---|---|
| `jurisdiction_id` | string | yes | Two-letter jurisdiction code |
| `languages` | list of string | yes | ISO 639 codes this pack covers. Each needs a lexicon |
| `authority_basis` | string | yes | What gives these bodies their mandate — the statutes, or an explicit statement that there is none |
| `pack_version` | string | yes | Version of this pack's data |
| `maintainer` | string | yes | Who is responsible for it |

## `[[custodians]]`

One per institution. A custodian has a **mandate to publish the figure**; an
outlet that reports a figure is not its custodian.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Referenced by measures and routing rules |
| `name` | string | yes | Official name |
| `mandate` | string | yes | What it is responsible for publishing |
| `cadence` | string | yes | Publication frequency. Drives the retrieval TTL |
| `revision_policy` | string | yes | Whether and how it revises |
| `access_method` | string | yes | API, bulk dataset, published tables |
| `integrity_annotation` | string | yes | Known limits, or `none known` |

### `cadence` values that map to a TTL

`continuous`, `daily`, `business`, `weekly`, `monthly`, `quarterly`, `annual`,
`yearly`, `per election`, `per sitting`, `periodic`.

The match is a substring test, so `monthly for price indices` resolves. An
unrecognised cadence gets the **shortest** TTL: erring short costs a re-pull,
erring long serves a stale figure.

### `integrity_annotation`

Renders alongside the citation. Use it for anything a reader needs in order not
to misread a verified figure — an administrative count that undercounts by
design, a registry with a reporting lag, a derived publisher that is not the
originating record.

## `[[measures]]`

The measure, not the source, is the unit of correctness.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Referenced by routing rules |
| `name` | string | yes | The custodian's published name for the series |
| `definition` | string | yes | The custodian's own definition |
| `custodian_id` | string | yes | Must name a declared custodian |
| `series_identifier` | string | yes | The custodian's series code |
| `unit` | string | yes | e.g. `index_points`, `percent`, `seats`, `persons` |
| `published_precision` | float | yes | The custodian's reporting precision |
| `discrete` | bool | yes | `true` for counts, which match exactly |
| `known_confusions` | list of string | yes | Measures this is routinely mistaken for. `["none known"]` if genuinely none |
| `admissible_baselines` | list of string | yes | Comparison bases the sweep will vary |
| `admissible_windows` | list of string | yes | Time windows the sweep will vary |
| `admissible_source_ref` | string | yes | The publication the two admissible lists were taken from |
| `series_breaks` | table array | no | See below |

### `published_precision` and tolerance

Drives the tolerance band. A relative floor applies alongside the absolute
half-step, and at index scale the relative floor dominates. `discrete = true`
overrides the band entirely with exact match, as do superlative and direction
elements, which are binary regardless of precision.

### `admissible_baselines` and `admissible_windows`

The comparisons the robustness sweep varies to produce the flip table. They
must be comparisons **the custodian itself publishes**, cited by
`admissible_source_ref` — a set the maintainer chose is a comparison set
selected by a person.

A measure declaring neither has nothing to vary, and every verdict on it caps
at **Indeterminate**.

Values are pack-defined strings. The fixture uses `prior_period`,
`prior_year`, `series_start`, `last_break` for baselines and `1m`, `3m`, `12m`,
`1_election` for windows.

### `[[measures.series_breaks]]`

A declared fracture in the series. Without a register, no cross-time comparison
on the measure can be Verified.

| Field | Type | Required | Description |
|---|---|---|---|
| `effective_date` | date | yes | When the break takes effect. Unquoted TOML date |
| `kind` | string | yes | See below |
| `custodian_notice_ref` | string | yes | The custodian's own announcement. May not be empty |
| `linked_series_available` | bool | yes | Whether a spliced series spans the break |
| `linked_series_identifier` | string | no | Required when the previous field is `true` |

`kind` is one of `base_year`, `methodology`, `definition`, `classification`,
`coverage`.

`custodian_notice_ref` is mandatory because a break the engine inferred but the
custodian never announced is a *flag*, not a register entry. Where no linked
series exists, the engine refuses to verify across the break rather than
splicing the two sides itself.

## `[[routing_rules]]`

| Field | Type | Required | Description |
|---|---|---|---|
| `measure_id` | string | yes | Must name a declared measure |
| `custodian_id` | string | yes | Must name a declared custodian |
| `rationale` | string | yes | Why this body and not another |
| `alternatives_considered` | list of string | conditional | Other plausible sources, and why each is wrong for this measure |
| `no_alternative_custodian` | bool | conditional | `true` where genuinely none exists |

One of the last two is required. A routing table showing only winners is
indistinguishable from one built backwards from preferred answers.

## `[[lexicons]]`

One per declared language. A language without a lexicon under-fires silently on
every claim in it.

| Field | Type | Required | Description |
|---|---|---|---|
| `language` | string | yes | ISO 639 code |
| `composition_connectives` | list of string | yes | Allowlist for joining verified elements |
| `forbidden_connectives` | list of string | yes | Connectives that may never appear in a reconstruction |
| `element_slot_order` | list of string | yes | The order element surfaces compose in |
| `fuzzy_trigger_matching` | bool | no | Default `false`. See below |
| `derivation_triggers` | table | yes | See below |

### `composition_connectives`

An allowlist admitting enumeration and sequencing and **nothing** causal,
evaluative, concessive, or explanatory. The loader rejects a pack that includes
one of those — this is what stops a reconstructor from smoothing two adjacent
verified facts into an implication neither supports.

### `fuzzy_trigger_matching`

When `true`, a single-token trigger phrase also matches a word one edit away,
so a misspelled connective still fires. Restricted to tokens of six characters
or more: below that, ordinary words sit one edit from declared triggers.

Spans are still taken from the position of the word in the claim, never from
the declared phrase, so anchoring is unaffected.

### `[lexicons.derivation_triggers]`

Keys are the six derivation operations; values are the phrases that trigger
each in this language.

| Key | Discharges |
|---|---|
| `causal-discharge` | "B due to A" — A produced B |
| `inferential-discharge` | "A therefore B" — B follows from A |
| `superlative-discharge` | highest, lowest, first time in N years |
| `comparative-discharge` | more than, twice as |
| `evaluative-discharge` | characterisations carrying no truth value |
| `scope-discharge` | all, every, never |

The key set is closed and versioned with the specification. An unknown key
fails the load.

---

## Loader validation

The loader runs the interface's checklist and refuses the **whole pack** on any
failure. A partial pack is worse than no pack: it routes some claims and
silently drops others, so it looks like it is working.

| Check | Fails when |
|---|---|
| Required blocks | Any of the five is missing |
| Referential integrity | A measure or rule names an undeclared custodian or measure |
| No figures | A statistic appears in any free-text field |
| Composition allowlist | A forbidden connective appears in `composition_connectives` |
| Operation keys | A `derivation_triggers` key is not one of the six operations |
| Routing declaration | A rule has neither alternatives nor `no_alternative_custodian` |
| Break references | A break has an empty `custodian_notice_ref`, or claims a linked series without naming it |
| Admissible source | A measure declares baselines or windows without `admissible_source_ref` |
