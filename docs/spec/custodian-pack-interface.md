# Custodian Pack Interface

**Normative contract, v1.4** — companion to [`claim-verification-engine.v0.4.md`](claim-verification-engine.v0.4.md) §9.4.

> **v1.4** adds a required `surface_vocabulary` block to §3.6 `lexicons`, keyed by a new closed set (`rise`, `fall`, `prediction`). Direction and prediction detection used to reach `engine/verification/patterns.py`'s hardcoded English regexes from four call sites regardless of what any pack declared — exactly the "pipeline hardcodes one language" failure §9.4 forbids for everything else. Required, unlike `names[]` in v1.3: an optional field here would just add a second silent-under-fire mode instead of removing the one that existed. Every pack must now declare its own rise/fall/prediction vocabulary, with an empty list where a category genuinely does not apply — the same "declare it explicitly" discipline `derivation_triggers` already enforces. Note the one thing this migration does not preserve: the old `PREDICTION` pattern also matched "by 20XX" (a bare future year), which needed a digit wildcard no plain phrase list can express, and no test exercised it — dropped rather than faked.
>
> **v1.3** adds the optional `names[]` field to §3.6 `lexicons`. Spec §9.8.2's first jurisdiction-resolution rule binds a claim that names its own jurisdiction in the claim text — preferred "because it needs no provenance at all" — but the rule was implemented against the header's bare `jurisdiction_id`, which real claims almost never carry: *"inflation in Israel"* has no "IL" in it. `names[]` gives each declared language its own demonyms and short forms to match instead. Optional and empty by default, so a pack that declares none keeps exactly the pre-v1.3 behaviour rather than failing to load — the code check alone is conservative, not broken, and this is an addition to it, not a replacement.
>
> **v1.2** keys a sixth derivation operation (`inferential-discharge`, spec §9.7.2) and adds the optional `fuzzy_trigger_matching` flag to §3.6. Real claims carry typos, and a trigger phrase missed on a misspelling under-fires silently — the failure mode §3.6 already warns about. The flag is pack data, versioned and reviewable, and its blast radius is bounded by the §9.7.6 gate: a derived element is `proposed`, never verified, so a false trigger costs a reviewer's attention rather than a laundered fact.
>
> **v1.1** adds `admissible_source_ref` to §3.3 and §3.6 `lexicons`, a fifth required block. The first closes a checklist item that could not be checked: v1.0 required that admissible baselines and windows be "drawn only from windows the custodian itself publishes" while giving a validator nothing to test it against, which left the sweep's fixed comparison set resting on a maintainer's assurance. The second: Spec §9.7.2 triggers derivation on connective phrases and §9.9 composes reconstructions from connectives; both are language-specific, and v1.0 gave them nowhere to be declared. Without the block an implementation either hardcodes one language into the pipeline — which spec §9.4 forbids — or under-fires silently on every other language a pack declares. Packs at v1.0 do not load against v1.1.

---

## 1. Purpose

A **custodian pack** is the jurisdiction-specific data that makes routing work. The engine contains no knowledge of any particular country, institution, or dataset. Everything jurisdictional lives in a pack.

This exists so that generalising across jurisdictions does not dilute the standard. The temptation in a multi-jurisdiction design is a generic fallback: when no custodian is known, search the web and use what looks official. That fallback silently voids §3 of the spec, because "looks official" is not a custodian of record. The pack interface makes the absence of a custodian an explicit, structured fact — which is what allows the engine to return **Insufficient Data** rather than improvise.

A pack is **data, not code**. Adding a jurisdiction must never require changing the pipeline.

---

## 2. Pack lifecycle

Packs are versioned artifacts. They are inspectable, diffable, and **not operator-configurable at runtime** (spec §7.3).

- A pack has a semantic version and a changelog.
- Changing a routing rule, a measure definition, an admissible baseline, or an integrity annotation requires a **version bump**, recorded in `routing_log`.
- There is no runtime API, setting, or environment variable that mutates pack contents. Verified by AC-3.
- Packs may be reviewed and contested publicly. That is the intended mechanism for challenging source selection — partisanship enters most invisibly through source selection, so the selection must sit in the open where it can be argued with, not inside a configuration screen where it can be adjusted quietly.

---

## 3. Required declarations

A pack MUST declare all five blocks. A pack missing any block is invalid and MUST NOT load — a partial pack is worse than no pack, because it routes some claims and silently drops others.

### 3.1 Jurisdiction header

| Field | Required | Meaning |
|---|---|---|
| `jurisdiction_id` | yes | Stable identifier (ISO 3166 code, or a supranational identifier for bodies like the OECD or Eurostat) |
| `languages` | yes | Languages claims may arrive in, and the language the custodian publishes in — these differ, and the gap is where measure names get mistranslated |
| `authority_basis` | yes | What makes custodians in this pack authoritative: statute, constitutional mandate, treaty, or delegated regulation |
| `pack_version` | yes | Semantic version |
| `maintainer` | yes | Who is accountable for the contents |

### 3.2 Custodians

One entry per institution. A custodian is not "a good source" — it is an institution with a **mandate to publish the figure**, a stated methodology, and a publication cadence. An outlet that reports a figure is not its custodian.

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable within the pack |
| `name` | yes | Institution name as it publishes |
| `mandate` | yes | The statutory or regulatory basis for publishing. Free text, but must name the instrument or role |
| `cadence` | yes | Publication frequency. Drives retrieval TTL (spec §8) |
| `revision_policy` | yes | Whether it publishes provisional prints, and how revisions are announced. Drives provisional invalidation |
| `access_method` | yes | How the figure is pulled: API, bulk dataset, structured service, or published page |
| `integrity_annotation` | yes | Is this custodian itself subject to contestation, adversarial editing, coordinated manipulation, known under-reporting, or partial publication? **May not be empty.** Write `none known` explicitly — the field is required so that its absence is a deliberate statement rather than an oversight |

`integrity_annotation` is the field most likely to be skipped and the one that matters most. A verified fact drawn from a compromised custodian propagates the compromise with a verification stamp attached.

### 3.3 Measures

The **measure**, not the source, is the unit of correctness. Two authoritative institutions can both be correct and disagree because they measure different things.

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable within the pack |
| `name` | yes | The measure as published |
| `definition` | yes | What it actually measures, in enough detail to distinguish it from its neighbours |
| `custodian_id` | yes | Who publishes it |
| `series_identifier` | yes | Dataset or series id used at retrieval |
| `unit` and `published_precision` | yes | Drives the tolerance bands (spec §9.2). Precision is the unit of the last published significant digit |
| `known_confusions[]` | yes | The measures this one is routinely mistaken for, and why the confusion changes the answer. **May not be empty** unless the measure genuinely has no near neighbour; write `none known` |
| `admissible_baselines[]` | yes | The baselines the robustness sweep may use (spec §9.3). Declared here so the sweep cannot be selected per claim |
| `admissible_windows[]` | yes | The comparison windows the sweep may use, drawn from the custodian's own standard reporting windows |
| `admissible_source_ref` | yes | **v1.1.** The custodian publication the admissible baselines and windows were taken from. Same role as `custodian_notice_ref` in §3.5: it is what makes the checklist item below a check rather than an assurance. An admissible set the maintainer chose is a comparison set selected by a person, which is the failure `admissible_baselines[]` exists to prevent |
| `series_breaks[]` | yes | Break register — see §3.5 |
| `discrete` | yes | Whether the measure counts discrete things (seats, votes, licences). Discrete measures take exact-match tolerance |

`admissible_baselines[]` and `admissible_windows[]` carry more weight than they look like they do. If a claim's author could choose the comparison set, the robustness sweep would test only the alternatives that flatter the claim. Fixing them in a versioned pack is what makes the sweep a test rather than a formality.

### 3.4 Routing rules

| Field | Required | Meaning |
|---|---|---|
| `measure_id` | yes | The bound measure |
| `custodian_id` | yes | Where it routes |
| `rationale` | yes | Why this custodian and not another. Surfaces in output (spec §7.4) |
| `alternatives_considered[]` | yes | Other custodians that could plausibly have served, and why they were not chosen. **May not be empty** where an alternative exists |

`alternatives_considered[]` is what makes routing auditable. A routing table showing only winners is indistinguishable from a routing table built backwards from preferred answers.

### 3.5 Series break register

Per measure. Methodology revisions, base-year changes, and definitional breaks fracture long series; a comparison spanning a break is not a comparison.

| Field | Required | Meaning |
|---|---|---|
| `effective_date` | yes | When the break takes effect in the series |
| `kind` | yes | `base_year` \| `methodology` \| `definition` \| `classification` \| `coverage` |
| `custodian_notice_ref` | yes | The custodian's own publication announcing it. A break the engine inferred but the custodian never announced is a *flag*, not a register entry |
| `linked_series_available` | yes | Whether the custodian publishes a back-cast or linked series spanning the break |
| `linked_series_identifier` | if available | Which series to use instead |

### 3.6 Lexicons

**New in v1.1.** One entry per language declared in `languages` — including the languages claims arrive in, not only the language custodians publish in. A pack declaring a language with no lexicon entry is invalid.

| Field | Required | Meaning |
|---|---|---|
| `language` | yes | ISO 639 code. Must appear in the header's `languages` |
| `derivation_triggers` | yes | Per derivation operation in spec §9.7.2, the trigger phrases in this language. All six operations must be keyed **[v1.2]**; an operation with no phrases in this language declares an empty list explicitly |
| `fuzzy_trigger_matching` | no | **v1.2.** Whether trigger phrases match at an edit distance of one. Applies only to single-token phrases of at least six characters. Below that, ordinary words sit one edit from declared triggers — *ever* is one insertion from *never* — and the matcher would fire an operation on unremarkable prose. Defaults to false |
| `names` | no | **v1.3.** The demonyms and short forms a claim in this language may use for the jurisdiction — *"Israel"*, not just the code. Matched word-boundary exact, case-insensitively (§9.8.2 rule 1). Defaults to empty, which falls through to rule 2 exactly as before v1.3 |
| `surface_vocabulary` | yes | **v1.4.** Rise, fall, and prediction phrases for this language, keyed `rise`/`fall`/`prediction`. All three keys must be present; declare an empty list explicitly where a category does not apply to this language. Matched word-boundary exact, case-insensitively |
| `composition_connectives` | yes | The enumeration and sequencing connectives the reconstructor may join elements with (spec §9.9). Enumeration and sequencing only |
| `forbidden_connectives` | yes | Causal, evaluative, concessive, and explanatory connectives. A reconstruction containing one fails before emission |
| `element_slot_order` | yes | The slot order an element renders into for this language (spec §9.9.1) |

Two of these fields carry far more weight than a translation table normally would.

`forbidden_connectives` is the executable form of the single most important bar in the spec. Spec §9.6 establishes that a reconstruction may never compose a causal connective out of non-causal parts, and [AC-15](acceptance-criteria.md#ac-15--reconstruction-determinism-and-composition) tests exactly that — "and their equivalents in each pack's declared languages." This is where those equivalents live. A pack that lists English causal connectives and leaves Hebrew empty passes every test the English fixtures exercise and provides no protection at all on Hebrew claims.

`derivation_triggers` sets what the system can see. Spec §9.7.2's operations are a closed list, but the phrases that fire them are language-specific, and an implication whose trigger phrase is undeclared is never surfaced. The failure is silent and in the safe direction — under-reporting rather than misreporting — but it is invisible from the output, so an incompletely lexicon'd pack looks identical to a claim that simply had no implications.

Both fields are pack data and therefore versioned, publicly reviewable, and non-configurable at runtime (§2). Neither is a place for a maintainer's judgment about which implications are worth surfacing: the operations are fixed by the spec, and the lexicon supplies only their surface forms.

---

## 4. Resolution order

```
claim
  → jurisdiction detection
  → pack lookup
  → measure binding          (Stage 3 — before any source is chosen)
  → routing rule
  → custodian
  → retrieval
```

Measure binding precedes routing. Choosing a source before deciding what is being measured is how a true figure becomes a misleading claim.

### 4.1 When resolution fails

| Failure | Outcome |
|---|---|
| No pack covers the jurisdiction | **Insufficient Data** |
| Pack exists, no measure matches the element | **Insufficient Data** |
| Measure matches, no routing rule | **Insufficient Data** — and a pack defect to be filed |
| Routing rule exists, custodian unreachable this session | **Unreachable** — distinct from Unverified, and it must not silently collapse into it |

There is **no generic fallback**. Not a web search, not a news source, not a model prior. This is the single most important rule in this document: it is what stops generalisation from becoming dilution.

---

## 5. Cross-jurisdiction claims

Claims comparing jurisdictions ("X's inflation is above the regional average") resolve against two or more packs and require a **comparability check** before any comparison is computed:

1. Bind the measure in each jurisdiction independently.
2. Compare the two `definition` fields.
3. If the definitions are equivalent → proceed.
4. If they differ → look for a **supranational custodian** that publishes a harmonised measure covering both jurisdictions, and route to it.
5. If no harmonised measure exists → the element is **Contested by definition**. Report both figures with the definitional gap explained. Do not compute a comparison.

Step 5 is a real outcome, not a degraded one. Nationally-defined unemployment rates, price indices, and poverty lines routinely differ enough that a cross-country comparison of the national figures is arithmetic performed on incommensurable quantities.

Supranational bodies are declared as packs in their own right, with `jurisdiction_id` set to the body and `authority_basis` set to the treaty or agreement under which they publish.

---

## 6. Pack validation checklist

Run before a pack is admitted. Every item is pass/fail.

- [ ] All five required blocks present.
- [ ] Every custodian has a non-empty `mandate`, `cadence`, `revision_policy`, and `integrity_annotation`.
- [ ] Every measure resolves to a declared custodian.
- [ ] Every measure has non-empty `known_confusions[]`, `admissible_baselines[]`, `admissible_windows[]`, `unit`, and `published_precision`.
- [ ] Every routing rule has a non-empty `rationale`, and `alternatives_considered[]` wherever an alternative custodian exists in the pack.
- [ ] Every series-break entry cites a `custodian_notice_ref`.
- [ ] No routing rule points at a source that is not a declared custodian.
- [ ] No measure declares an admissible baseline or window the custodian does not itself publish, and every measure cites the `admissible_source_ref` establishing it.
- [ ] Every language in `languages` has a lexicon entry, and every lexicon entry names a declared language.
- [ ] Every lexicon keys all six derivation operations, declares a non-empty `forbidden_connectives`, and declares `composition_connectives` containing no causal, evaluative, concessive, or explanatory term.
- [ ] The pack contains **no figures** — definitions, identifiers, mandates, and cadences only. A pack carrying a cached statistic is a pack serving figures from memory.

The last item deserves emphasis. A pack describes *where a figure comes from and what it means*. The moment it contains the figure, it becomes exactly what spec §8 exists to prevent: a fact stored as timeless, reused without re-checking.
