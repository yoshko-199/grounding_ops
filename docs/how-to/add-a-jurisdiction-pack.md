# How to add a jurisdiction pack

A pack is data, not code. Adding a country never requires changing the
pipeline. For every field, see the [pack schema](../reference/pack-schema.md);
for the normative contract, the
[custodian pack interface](../spec/custodian-pack-interface.md).

**Before you start.** Every value in a pack must come from the custodian's own
current publication, open in front of you. A pack populated from recollection
is the exact failure this system exists to prevent, and it would be
self-refuting to introduce one here. Fields you cannot confirm are left
unfilled — the pack then does not load, which is the correct outcome.

## 1. Create the file

One TOML file per jurisdiction, in your pack directory:

```
packs/live/gb.toml
```

## 2. Write the header

```toml
[header]
jurisdiction_id = "GB"
languages = ["en"]
authority_basis = "Statutory. <the laws establishing these bodies>"
pack_version = "0.1.0"
maintainer = "<a named person or team>"
```

## 3. Declare the custodians

A custodian is an institution with a **mandate to publish the figure** — not "a
good source". An outlet that reports a figure is not its custodian.

```toml
[[custodians]]
id = "stat_office"
name = "<official name>"
mandate = "<what it is statutorily responsible for publishing>"
cadence = "monthly"
revision_policy = "<whether and how it revises>"
access_method = "<API, bulk download, published tables>"
integrity_annotation = "<known limits, or: none known>"
```

Use `integrity_annotation` for anything a reader must know to avoid
misreading a verified figure — an administrative count that undercounts by
design, a registry with a reporting lag, a derived publisher that is not the
originating record. It renders alongside the citation.

## 4. Declare the measures

The measure, not the source, is the unit of correctness.

```toml
[[measures]]
id = "cpi"
name = "<published name of the series>"
definition = "<the custodian's own definition>"
custodian_id = "stat_office"
series_identifier = "<the custodian's series code>"
unit = "index_points"
published_precision = 0.1
discrete = false
known_confusions = [
  "<a measure this is routinely mistaken for, and why it changes the answer>",
]
admissible_baselines = ["prior_period", "prior_year", "series_start"]
admissible_windows = ["1m", "3m", "12m"]
admissible_source_ref = "<the publication these comparisons were taken from>"
```

Three of these decide how the engine behaves and are worth care:

- **`published_precision`** drives the tolerance bands. It is the custodian's
  *reporting* precision, not a value of the series — the one numeric field a
  pack legitimately carries.
- **`admissible_baselines` / `admissible_windows`** are the comparisons the
  robustness sweep will vary. They must be comparisons the custodian itself
  publishes, cited by `admissible_source_ref`. A set the maintainer chose is a
  comparison set selected by a person, which is what the field exists to
  prevent. **Leave them out and every verdict on the measure caps at
  Indeterminate.**
- **`discrete`** switches the measure to exact match. Use it for counts —
  seats, people — where a tolerance band is meaningless.

## 5. Register the series breaks

A break is a fracture in a series: a rebasing, a redefinition, a methodology
change. Without a register, no cross-time comparison on that measure can be
Verified.

```toml
  [[measures.series_breaks]]
  effective_date = 2020-01-01
  kind = "base_year"
  custodian_notice_ref = "<the custodian's own announcement>"
  linked_series_available = true
  linked_series_identifier = "<the spliced series the custodian publishes>"
```

`custodian_notice_ref` is required and may not be empty. A break the engine
inferred but the custodian never announced is a *flag*, not a register entry.

Where no linked series spans the break, set `linked_series_available = false`.
The engine will then refuse to verify across it rather than splicing the two
sides itself.

## 6. Write the routing rules

```toml
[[routing_rules]]
measure_id = "cpi"
custodian_id = "stat_office"
rationale = "<why this body and not another>"
alternatives_considered = [
  "<another plausible source, and why it is wrong for this measure>",
]
```

Where genuinely no alternative exists, say so explicitly instead:

```toml
no_alternative_custodian = true
```

One of the two is required. A routing table showing only winners is
indistinguishable from one built backwards from preferred answers.

## 7. Declare a lexicon per language

```toml
[[lexicons]]
language = "en"
composition_connectives = ["and", ", ", "; ", "then"]
forbidden_connectives = ["because", "due to", "therefore", "although"]
element_slot_order = ["time_period", "entity", "measure", "direction", "quantity"]
fuzzy_trigger_matching = true

  [lexicons.derivation_triggers]
  "causal-discharge" = ["due to", "because of"]
  "inferential-discharge" = ["therefore", "hence"]
  "superlative-discharge" = ["highest", "lowest", "record"]
  "comparative-discharge" = ["more than", "less than"]
  "evaluative-discharge" = ["failure", "mismanagement"]
  "scope-discharge" = ["all", "every", "never"]
```

`composition_connectives` is an allowlist for joining verified elements back
into a sentence. It admits enumeration and sequencing and nothing causal,
evaluative, concessive, or explanatory — the loader rejects a pack that tries.
This is what stops the reconstructor from smoothing two adjacent verified facts
into an implication neither supports.

A pack that declares a language without a lexicon for it under-fires silently
on every claim in that language.

## 8. Load it

```
PYTHONPATH=. python3 cli/verify.py "<a claim>" \
  --jurisdiction GB --packs packs/live
```

The loader runs the interface's validation checklist and refuses the whole pack
on any failure. That is intentional: a partial pack is worse than no pack,
because it routes some claims and silently drops others.

---

## Troubleshooting

### The pack does not load

The error names the field. Common causes:

| Message mentions | Cause |
|---|---|
| a required block | One of `header`, `custodians`, `measures`, `routing_rules`, `lexicons` is missing |
| a numeric literal | A figure appears in a definition, mandate, or confusion — packs carry no statistics except `published_precision` |
| composition connective | A causal or concessive word is in the allowlist |
| unknown operation | A derivation trigger key is not one of the six operations |
| routing rule | A rule has neither `alternatives_considered` nor `no_alternative_custodian` |

### Claims name the country but do not route to it

Packs declare a `jurisdiction_id` and no *names*, so the engine has nothing to
match "Britain" against without embedding country knowledge, which it must not
do. Claims fall through to `--jurisdiction`. This is a known gap; see the
[roadmap](../plan.md).

### Everything caps at Indeterminate

The measure declares no admissible baselines or windows. See step 4.

### Cross-time claims are never Verified

The measure's break register is empty, or a break has no linked series. See
step 5.
