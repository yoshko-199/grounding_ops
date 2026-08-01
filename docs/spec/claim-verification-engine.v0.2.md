# Claim Verification & Reconstruction Engine

**Specification v0.2**

Supersedes [v0.1](claim-verification-engine.v0.1.md). Companion documents: [Acceptance Criteria](acceptance-criteria.md), [Custodian Pack Interface](custodian-pack-interface.md).

---

## 0. What changed from v0.1

v0.1 was structurally complete but ended with five unresolved questions in its §9. Three of them were load-bearing: without a fixed tolerance rule, a concrete misleadingness procedure, and a jurisdiction model, two competent implementers would build materially different systems. v0.2 closes all five and converts the anti-laundering constraints from prose principles into testable criteria.

| Area | v0.1 | v0.2 |
|---|---|---|
| Human sign-off | Open question | Resolved — automated pipeline, **human confirmation gate on the claim-level verdict only** (§9.1) |
| Tolerance bands | Open question | Resolved — fixed rule derived from the custodian's published precision, with binary overrides (§9.2) |
| Stage 8 misleadingness | "Hardest unsolved piece" | Resolved — the **robustness sweep**, a mechanical four-test procedure emitting a flip table (§9.3) |
| Geographic scope | Open question | Resolved — **generalised from the start** via versioned custodian packs; jurisdictions are data, not code (§9.4) |
| Series changes | "Detection strategy needed" | Resolved — break register plus a mandatory continuity check; no verification by splicing (§9.5) |
| Anti-laundering constraints | Six prose principles | Twelve numbered acceptance criteria with pass/fail tests ([acceptance-criteria.md](acceptance-criteria.md)) |

Sections 1–8 are carried forward from v0.1 with amendments marked **[v0.2]**.

---

## 1. What it is

A system that takes a public claim, decomposes it into atomic checkable elements, verifies each element against an authoritative custodian of record, and reconstructs a grounded version of the claim containing only what survived verification — displayed inseparably from a ledger of what was removed and why.

It additionally surfaces *derived elements* — claims implied by or related to the original — and maps each one's relationship to both the original claim and the reconstructed claim.

**One-line framing:** not "is this true?" but "what part of this survives contact with the record, and what does the surviving part actually support?"

---

## 2. Scope

### In scope

Claims about **quantities and administrative facts that have an authoritative custodian** — a named institution with a mandate to publish the figure, a stated methodology, and a publication cadence.

Examples: price indices, budget allocation and execution, exchange rates, legislative votes and bill status, election results and turnout, registered transaction prices, labour statistics, licensing and registry records, official incident counts.

### Out of scope

| Excluded | Why |
|---|---|
| Opinions | No truth value to check |
| Predictions | No record exists yet |
| Causal claims | Data shows correlation; causation rarely provable from published series |
| Historical-interpretive claims | **No authoritative custodian exists.** Source selection determines the outcome, so "verification" would be argument wearing a verification badge |

The fourth exclusion is the load-bearing one. It is what separates this from an advocacy tool. See §7.

**[v0.2]** Generalising across jurisdictions (§9.4) does not widen this scope. A jurisdiction with no custodian for a given measure yields **Insufficient Data**, never a fallback to a non-custodial source. See [Custodian Pack Interface §4.1](custodian-pack-interface.md#41-when-resolution-fails).

---

## 3. Non-negotiable rule

> Every figure, date, amount, or ranking in any output MUST originate from a retrieval performed against a named custodian, recorded with its reference period. If no confirming retrieval exists, the output is **Insufficient Data**. No estimation, no inference from model priors, no "approximately."

A fabricated verification is worse than no verification, because it launders a guess into an authoritative-looking artifact. This rule has no exceptions and is not operator-configurable.

**[v0.2]** Tested by [AC-7](acceptance-criteria.md#ac-7--no-unsourced-figure). Two corollaries added in v0.2, each with its own criterion:
- A human confirming a verdict cannot introduce a figure (§9.1, [AC-10](acceptance-criteria.md#ac-10--gate-integrity)).
- A custodian pack may not contain figures, only definitions and identifiers ([Pack Interface §6](custodian-pack-interface.md#6-pack-validation-checklist)).

---

## 4. Pipeline

| # | Stage | Function |
|---|---|---|
| 0 | **Ingest** | Accept claim text + provenance (who said it, when, where) |
| 1 | **Scope gate** | Classify: quantitative/administrative → proceed. Opinion / prediction / causal / no-custodian → route out with explanation, no verdict |
| 2 | **Decompose** | Split into atomic elements: entity, quantity, unit, time period, comparison basis, ranking assertion |
| 3 | **Context recovery** | Establish baseline and disambiguate measure. Bind each element to a specific measure definition before choosing a source. Check the *most charitable correct reading*, not the easiest to retrieve |
| 4 | **Route** | Resolve jurisdiction → pack → measure → custodian. Log the routing decision, its rationale, and the alternatives considered **[v0.2]** |
| 5 | **Retrieve** | Pull the figure. Record the citation record + revision status (see §5). Run the continuity check against the series break register **[v0.2]** |
| 6 | **Element verdict** | Assign one status per element (see §6.1), applying the tolerance bands (§9.2). Automated and final **[v0.2]** |
| 7 | **Reconstruct** | Subtractive rebuild from surviving elements only. Emit discard ledger |
| 8 | **Claim-level evaluation** | Run the robustness sweep (§9.3), then evaluate the *reconstructed* claim as a whole (see §6.2). Element-level truth does not imply claim-level honesty |
| 9 | **Derive** | Identify implied/adjacent claims; map each to original and reconstructed (see §6.3) |
| 10 | **Persist** | Store as retrieval events with validity windows, not as timeless facts |
| 11 | **Sign-off** | Claim-level verdict is emitted as `proposed`; human confirmation promotes it to `confirmed` (§9.1) **[v0.2]** |

### Stage 3 is not optional

The most common way a true number becomes a misleading claim is measure ambiguity. Before routing, every element must be bound to a specific measure definition:

- nominal vs. real
- planned vs. executed
- survey-based vs. registry-based
- monthly change vs. annualised
- asking price vs. recorded transaction
- provisional print vs. revised final

Two authoritative institutions can both be correct and disagree, because they measure different things. "Primary source" is not a sufficient category — **measure identity is the actual unit of correctness.**

**[v0.2]** Binding precedes routing in Stage 4 by construction: the pack's resolution order is jurisdiction → measure → custodian, never source-first. A measure whose neighbours are known is declared with `known_confusions[]` in its pack entry, so the traps above become data rather than institutional memory.

### Stage 7 is subtractive by construction

Reconstruction removes; it never adds, rephrases toward a conclusion, or supplies connective claims. If the surviving elements do not compose into a coherent statement, the correct output is the element list plus "does not reconstruct," not a smoothed-over sentence.

### Stage 8 exists because verified parts can compose a false whole

A claim assembled entirely from verified elements can still create a false impression through omission, selective baseline, or cherry-picked window. This is the standard mechanism of sophisticated misinformation and the single largest gap in a naive design. The reconstructed claim gets its own evaluation, independent of its parts.

**[v0.2]** v0.1 named this the hardest unsolved piece. §9.3 resolves it into the robustness sweep — a mechanical procedure over already-retrieved series, not a judgment call.

---

## 5. The citation record

Every retrieval records six fields, all of which appear in output:

1. **Figure as published** — verbatim, including units
2. **Custodian** — the institution, named
3. **Dataset / series identifier**
4. **Reference period** — what the figure describes
5. **Retrieved at** — when the pull happened
6. **Revision status** — provisional / revised / final

Plus a **framing caveat** field where the measure has a known trap (nominal/real, planned/executed, etc.).

For any "highest / lowest / first time in N years" element, a single current figure is insufficient. The full series must be pulled, and the index base must be confirmed not to have changed mid-series. A remembered historical peak is a fabricated comparison.

**[v0.2]** A seventh field is added: **continuity status** — whether the retrieved span crosses a series break, and if so, whether a custodian-published linked series was used (§9.5). The base-year check above is the narrow case of the general continuity check.

---

## 6. Taxonomies

### 6.1 Element status

| Status | Meaning |
|---|---|
| **Verified** | Custodian figure confirms the element within the tolerance bands of §9.2 **[v0.2]** |
| **Contradicted** | Custodian figure conflicts with the element |
| **Unverified** | Custodian reached, no figure covers this element |
| **Unreachable** | Custodian could not be reached this session — operationally distinct from Unverified, and must not silently collapse into it |
| **Contested by definition** | Two authoritative custodians differ because they measure different things. Both reported, with the definitional gap explained |
| **Out of scope** | Opinion, prediction, or causal fragment |

**[v0.2]** Element statuses are assigned automatically and are final on retrieval. They are not subject to the sign-off gate, and sign-off cannot alter them ([AC-10](acceptance-criteria.md#ac-10--gate-integrity)).

### 6.2 Claim-level verdict

Applied to the reconstructed claim, after Stage 8:

| Verdict | Meaning |
|---|---|
| **Accurate** | True in near-entirety |
| **Substantially inaccurate** | Significant parts wrong |
| **Misleading** | Elements verify, but the composition creates a false impression — wrong baseline, selective window, omitted context |
| **False** | The claim is not supported |
| **Indeterminate** | Too complex or definitionally contested for a single label. Data presented, judgment left to reader |
| **Insufficient data** | No custodian settles it. The anti-fabrication fallback — a legitimate outcome, not an error state |

Compound claims receive one verdict per atomic assertion, plus an optional one-line overall read.

**[v0.2]** Claim-level verdicts are emitted as `proposed` and require human confirmation (§9.1). Two hard caps apply regardless of element results:
- Where the robustness sweep cannot run, the verdict is capped at **Indeterminate** — never *Accurate* (§9.3).
- Where a comparison spans an unlinked series break, the underlying element cannot be Verified, so the claim cannot be *Accurate* on that element (§9.5).

### 6.3 Derived element relationships

Each derived claim is tagged by its position relative to both versions:

| Tag | Meaning |
|---|---|
| `implied-by-original-only` | Followed from the original, but depends on elements that did not survive — dies with them |
| `implied-by-reconstructed` | Follows from the verified subset — genuinely supported |
| `contradicted-by-reconstructed` | The verified subset argues against it |
| `independent` | Related but neither supported nor contradicted |

The first category is the most analytically valuable output of the whole system: it shows what people believed *because of* the unsupported parts of a claim.

---

## 7. Anti-laundering constraints

A reconstruction step is a generative act. It produces new, authoritative-sounding text. Without hard constraints it becomes a mechanism for laundering a preferred conclusion into a verified-looking artifact. These constraints are architectural, not stylistic:

1. **The reconstructed claim never renders, exports, or copies without its discard ledger.** If it can be detached, the tool is a laundering device.
2. **No platform-formatted output.** No share buttons, no post-ready formatting, no character-count targets. The moment output is optimised for distribution, users will run verifications selectively until one produces the answer they wanted.
3. **Verification thresholds and the source-routing table are not operator-configurable.** They are inspectable and versioned. Partisanship enters most invisibly through source selection.
4. **The routing decision is logged with rationale** and exposed in output: why this custodian and not another.
5. **Insufficient Data is a first-class, prominently-rendered outcome** — never styled as failure.
6. **Identical treatment regardless of claimant.** No claimant metadata reaches the verification path.

**[v0.2]** Each constraint above now has at least one numbered acceptance criterion with a stated pass/fail test — see [acceptance-criteria.md](acceptance-criteria.md). A principle that cannot fail a build is decoration. Constraint 6 in particular becomes mechanically falsifiable via [AC-6](acceptance-criteria.md#ac-6--claimant-blindness): run the same claim text under several attributions and require byte-identical routing, retrievals, element statuses, and proposed verdict.

---

## 8. Persistence model

The database stores **retrieval events, not facts.** This distinction is the whole design.

A cached figure reused without re-checking is functionally identical to a figure recalled from model memory — the exact failure mode §3 exists to prevent. Therefore:

- Every retrieval carries a **TTL derived from its custodian's publication cadence**. Expired retrievals are re-pulled, never served.
- **Provisional retrievals are invalidated when a revision publishes.** A claim true against the first print can be false against the revised figure; verdicts pin to a specific revision.
- Verdicts carry **validity windows**, not boolean flags. "Verified" is always "verified against series X, revision Y, as of date Z."
- Custodians carry an **integrity annotation**: is this source itself subject to contestation, adversarial editing, or coordinated manipulation? A verified fact drawn from a compromised custodian propagates the compromise with a verification stamp attached.

### Rough schema

**[v0.2]** additions marked. This remains a design sketch, not a migration.

```
custodians        id, name, mandate, cadence, integrity_notes,
                  pack_id, revision_policy, access_method                  [v0.2]
measures          id, name, definition, custodian_id, known_confusions[],
                  unit, published_precision, discrete,                     [v0.2]
                  admissible_baselines[], admissible_windows[]             [v0.2]
claims            id, text, source_attribution, stated_at, type (original|reconstructed|derived)
elements          id, claim_id, fragment, measure_id, status,
                  tolerance_band, continuity_status                        [v0.2]
retrievals        id, element_id, figure, series_id, reference_period,
                  revision_status, retrieved_at, ttl, caveat,
                  continuity_status, linked_series_used                    [v0.2]
verdicts          id, claim_id, label, rationale, valid_from, valid_until,
                  state, proposed_at, confirmed_by, confirmed_at,          [v0.2]
                  amended_from_label, amendment_rationale                  [v0.2]
discards          id, reconstructed_claim_id, element_id, reason
relationships     id, from_claim_id, to_claim_id, tag
routing_log       id, element_id, custodian_id, rationale,
                  alternatives_considered, pack_id, pack_version           [v0.2]

packs             id, jurisdiction_id, version, maintainer, loaded_at      [v0.2]
series_breaks     id, measure_id, effective_date, kind,                    [v0.2]
                  custodian_notice_ref, linked_series_available,
                  linked_series_identifier
sweeps            id, claim_id, test, alternative, conclusion_holds,       [v0.2]
                  computed_from_retrieval_id
```

`sweeps` rows are the flip table (§9.3). Each row cites the retrieval it was computed from, so the sweep is bound by §3 exactly as the primary verification is: a sweep cell computed from anything other than a recorded retrieval is a fabricated comparison.

`source_attribution` on `claims` is stored for provenance and display but is **structurally excluded from the verification path** (§7.6, [AC-6](acceptance-criteria.md#ac-6--claimant-blindness)).

---

## 9. Resolved decisions

v0.1 listed these as open. Each is resolved below with its rationale. Reopening any of them requires a version bump on this spec.

### 9.1 Human sign-off — automated pipeline, gated claim verdict

**Decision.** Retrieval and element verdicts are fully automated and final. The claim-level verdict is emitted as a **proposal** requiring explicit human confirmation before it counts as final.

**Verdict state machine:**

```
proposed ──confirm──→ confirmed
    │
    ├────amend────→ amended     (new label + amendment_rationale; proposal retained)
    ├────reject───→ rejected    (no label published)
    └────expire───→ expired     (underlying retrieval TTL lapsed before sign-off)
```

**Rules:**

1. An amendment never overwrites the proposal. Both are retained, with a required `amendment_rationale`. The audit trail is the point — a gate whose history can be edited is not a gate.
2. **The gate may only change the claim-level label.** Sign-off cannot mutate element statuses, retrievals, the discard ledger, the flip table, or routing decisions. This restriction is what keeps the gate from becoming the laundering vector the rest of §7 exists to close: an unconstrained human sign-off would let a reviewer reach past the verdict and adjust the evidence beneath it.
3. A human confirming or amending a verdict **cannot introduce a figure**. §3 binds the reviewer exactly as it binds the pipeline.
4. A `proposed` verdict renders visibly marked as unconfirmed and cannot export.
5. `expired` is not a failure state. It means the record moved on before a person got to it, and it re-enters the pipeline as a fresh retrieval.

**Rationale.** Element verification is mechanical and benefits nothing from a person in the loop; gating it would add latency and a false sense of scrutiny. Claim-level judgment on political claims is where the reputational and accuracy risk concentrates, and it is the one output that is genuinely a judgment. Gating exactly there — and nothing else — puts the human where they add signal rather than throughput cost.

Tested by [AC-10](acceptance-criteria.md#ac-10--gate-integrity).

### 9.2 Tolerance bands — a fixed rule from published precision

**Decision.** Tolerance is computed from the custodian's own published precision. It is never chosen per claim, per claimant, or per operator.

Let `u` = the unit of the last published significant digit. Illustratively — these are worked examples of the arithmetic, not figures about any real series — an index published to one decimal place as a percentage has `u = 0.1pp`, and a budget line published to one decimal place in billions has `u = 0.1bn`.

Let `Δ` = |claim figure − published figure|.

| Band | Condition | Element status |
|---|---|---|
| **A** | The claim figure rounds to the published figure at the claim's own stated precision, **or** `Δ ≤ max(u/2, 0.5% relative)` | **Verified** |
| **B** | `Δ ≤ max(u, 2% relative)` | **Verified**, tagged `rounded` |
| **C** | Beyond Band B | **Contradicted** — feeds *Substantially inaccurate* at claim level |

The `rounded` tag on Band B surfaces in output. A claim that is right to within a rounding step is not wrong, but the reader should be able to see that it was not exact.

**Binary overrides.** These bypass the numeric bands entirely, because a tolerance on them is meaningless:

| Element kind | Rule |
|---|---|
| Superlative / ordinal ("highest in N years", "first ever") | Binary. The full series supports it or the element is **Contradicted**. No tolerance. |
| Direction ("rose", "fell", "doubled") | Binary on sign. A claim asserting the wrong direction is **Contradicted** at any magnitude. |
| Discrete counts (seats, votes, licences, recorded incidents) | Exact match. `u = 1`, tolerance zero. Declared per measure via `discrete` in the pack. |

**Not tolerance questions.** Two failure modes look numeric but are measure-identity failures, and must route back to Stage 3 rather than being absorbed into a band:

- **Percent vs percentage point.** A claim of "rose 3%" against a rate series that moved from ten to thirteen percent describes a three-point move and a thirty percent relative move at the same time. Whichever the claimant meant, this is a binding question, not a rounding question. If genuinely ambiguous after applying the most-charitable-reading rule, the element is **Contested by definition**.
- **Nominal vs real.** A nominal figure differing from a real one by an inflation adjustment is not "within tolerance" of it. Bind at Stage 3.

**Rationale.** v0.1 required this be "a published, fixed rule, not a judgment call." Deriving the band from published precision rather than picking round numbers means the rule adapts to each measure without anyone choosing anything: the custodian's own reporting precision sets the scale. The binary overrides exist because superlatives and directions have no near-miss — a claim that something is the highest ever is not 97% correct when it is the third highest.

This table is versioned with the spec and is not operator-configurable ([AC-3](acceptance-criteria.md#ac-3--non-configurability)).

### 9.3 Detecting Stage 8 misleadingness — the robustness sweep

**Decision.** Misleadingness is tested by a mechanical **robustness sweep** over series already retrieved. The sweep introduces no new claims, performs no open-ended reasoning about "missing context," and computes every cell from a recorded retrieval.

That restriction is deliberate and is the reason this is implementable. An unbounded "what context is missing?" search reintroduces exactly the advocacy vector §2's fourth exclusion blocks: whoever chooses the missing context chooses the verdict.

**The four tests**, run against the reconstructed claim:

| # | Test | What it varies |
|---|---|---|
| 1 | **Baseline sweep** | Recompute the claim's comparison against every baseline the pack declares admissible for that measure — prior period, prior year, series start, last methodological break, custodian-marked reference points |
| 2 | **Window sweep** | Vary the comparison window across the custodian's own standard reporting windows (as declared: e.g. 1m / 3m / 12m / YTD / 5y) |
| 3 | **Level-vs-change** | If the claim asserts a change, check whether the level tells an opposing story; if it asserts a level, check the change. Catches "fastest growth" on a negligible base |
| 4 | **Bounded omission** | Only over (a) elements the decomposition already produced but that were discarded, and (b) the custodian's own published caveats attached to the series. Nothing else |

**Output — the flip table.** One row per admissible alternative, recording whether the claim's qualitative conclusion (direction, magnitude class, superlative) holds under it. Persisted to `sweeps`, and rendered with the verdict.

**Verdict rules:**

| Sweep result | Claim-level effect |
|---|---|
| Conclusion holds under all admissible alternatives | Not misleading on these axes |
| Conclusion flips under ≥1 admissible alternative | **Misleading** proposed, flip table attached as the evidence |
| Sweep cannot run — series too short, no admissible alternatives declared, single-observation measure | Verdict **capped at Indeterminate**. Never *Accurate* |

The third row is the one that keeps the sweep honest. Without it, an unrunnable sweep would read as a clean pass, and the weakest-evidence claims would receive the strongest label.

**Why "admissible" is fixed by the pack.** If the comparison set could be chosen per claim, the sweep would test only the alternatives that flatter the claim, and would systematically clear exactly the cherry-picked claims it exists to catch. The alternatives are declared once, per measure, in a versioned pack ([Pack Interface §3.3](custodian-pack-interface.md#33-measures)).

**Known limit, stated plainly.** The sweep catches misleadingness that lives in baseline and window selection — the dominant mechanism, and a mechanical one. It does not catch misleadingness that lives entirely outside the series, such as a true, robust figure presented alongside a false causal implication. Those route out at Stage 1 as causal claims. This is a narrower guarantee than "detects false impressions," and the narrowing is intentional: a narrow test that actually holds is worth more than a broad one that resolves to a judgment call.

### 9.4 Geographic scope — generalised from the start, via custodian packs

**Decision.** Routing is jurisdiction-agnostic from day one. All jurisdictional knowledge lives in versioned **custodian packs**; the pipeline contains no country-specific logic. Full contract: [custodian-pack-interface.md](custodian-pack-interface.md). First populated pack: [packs/israel.md](packs/israel.md).

**Resolution order:** claim → jurisdiction detection → pack lookup → measure binding → routing rule → custodian → retrieval. Measure binding precedes source selection, per Stage 3.

**The guardrail.** If no pack covers the jurisdiction, or the pack has no measure matching the element, or no routing rule exists for that measure, the outcome is **Insufficient Data**. There is no generic fallback — not a web search, not a news source, not a model prior. Generalising must never become diluting: the whole value of the design rests on "custodian of record" meaning something narrower than "source that looks official."

**Cross-jurisdiction comparisons** require a comparability check before any comparison is computed: bind each measure independently, compare definitions, route to a supranational custodian publishing a harmonised measure if one exists, and otherwise return **Contested by definition** with both figures and the definitional gap explained. Nationally-defined unemployment rates, price indices, and poverty lines differ enough that comparing the national figures directly is arithmetic on incommensurable quantities.

**Rationale.** v0.1 favoured a single jurisdiction for a tighter v1. The decision here goes the other way, for a structural reason: jurisdiction-specific routing written into the pipeline is very hard to extract later, and the extraction pressure arrives precisely when the second jurisdiction is added under deadline. Declaring the pack boundary up front costs one interface document now and is close to free thereafter. Depth is not sacrificed — Israel is fully populated first, and a pack that does not exist yet simply returns Insufficient Data, which is a correct answer rather than a gap.

### 9.5 Series-change handling — break register and continuity check

**Decision.** Methodology revisions, base-year changes, and definitional breaks are declared per measure in a **break register**, and every cross-time element runs a mandatory **continuity check** against it.

**Register entry** (per [Pack Interface §3.5](custodian-pack-interface.md#35-series-break-register)): effective date, kind (`base_year` | `methodology` | `definition` | `classification` | `coverage`), the custodian's own notice announcing it, and whether a linked or back-cast series spans it.

**Continuity check.** Any element comparing figures across time:

| Case | Outcome |
|---|---|
| Span crosses no break | Proceed normally |
| Span crosses a break, custodian publishes a linked/back-cast series | Use the linked series; record which, in `retrievals.linked_series_used` |
| Span crosses a break, no linked series | **Contested by definition** or **Unverified**. Never Verified |

**No verification by splicing.** Joining two sides of an unlinked break to produce a comparison is a fabricated comparison, in the same class as §5's remembered historical peak — a number that never existed as a published figure, presented as one.

**Detection, because registers will always be incomplete.** Three supplementary signals:

1. Custodian metadata or footnote flags attached to the series.
2. A base-year or methodology field that changed between two retrievals of the same series.
3. A step-discontinuity heuristic over the series.

All three **flag for review only**. None may auto-verify, and none may auto-populate the register — a register entry requires a `custodian_notice_ref`, because a break the engine inferred but the custodian never announced is a suspicion, not a fact about the series. Signal 2 is the strongest of the three and is cheap: it falls out of storing retrievals as events rather than facts (§8).

Tested by [AC-12](acceptance-criteria.md#ac-12--break-integrity).

---

## 10. Remaining open questions

Genuinely open, and deliberately not resolved here.

1. **Sweep cost.** The robustness sweep multiplies retrievals per claim by the size of the admissible alternative set. Whether that is affordable against rate-limited custodian APIs is an operational question that needs measurement against a real pack, not a design answer.
2. **Jurisdiction detection.** §9.4 assumes a claim's jurisdiction can be identified before pack lookup. Claims with implicit jurisdiction ("inflation is up") need a resolution rule — probably explicit context from Stage 0 provenance, with **Insufficient Data** where it is genuinely absent. Needs specification before implementation.
3. **Sign-off throughput.** §9.1 puts a person on every claim-level verdict. At volume this is the binding constraint. Whether a reviewed-sample model can preserve the guarantee is unresolved, and weakening it should not be done quietly.
4. **Derived-element generation.** §6.3 defines how derived claims are *tagged* but not how they are *generated*. Generation is a creative act inside a system otherwise built to prevent creative acts, and needs its own constraints before Stage 9 is implementable.

---

## 11. Prior art reviewed

- **Israeli fact-checker methodology** — supplied the custodian-routing model, the citation record, the insufficient-data fallback, the misleading category, and the catalogue of measure-confusion traps. Its key limitation relative to this design: it labels and stops, with no reconstruction, no derived-element mapping, and deliberate statelessness. Its source map is the basis for [packs/israel.md](packs/israel.md).
- **Here4Good / BrightMind AI** — the nearest live precedent, and a cautionary one. It pairs verification with a generation stack (meme generator, social post creator, thesis-first article writer) and operates primarily in historical-interpretive territory where no custodian exists. It is the reference case for why §2's fourth exclusion and all of §7 are load-bearing rather than decorative.
