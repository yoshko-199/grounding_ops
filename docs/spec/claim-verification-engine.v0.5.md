# Claim Verification & Reconstruction Engine

**Specification v0.5**

Supersedes [v0.4](claim-verification-engine.v0.4.md), [v0.3](claim-verification-engine.v0.3.md), [v0.2](claim-verification-engine.v0.2.md) and [v0.1](claim-verification-engine.v0.1.md). Companion documents: [Acceptance Criteria](acceptance-criteria.md), [Custodian Pack Interface](custodian-pack-interface.md).

---

## 0a. What changed in v0.5

§10's third open question asked whether five derivation operations cover the implication patterns that actually occur in public claims, and noted that the answer was empirical and unmeasured. A single real claim answered it: *"When you look at the horizon you don't see a curve — therefore the earth is flat."*

| Area | v0.4 | v0.5 |
|---|---|---|
| Derivation operations | Five | Six — **`inferential-discharge`** added (§9.7.2) |
| §10 question 3 | Open, unmeasured | Narrowed: one gap found and closed; the question becomes *which further patterns occur*, not *whether any do* |

**Why this is a new operation rather than a widened one.** *"A, therefore B"* and *"B due to A"* are different assertions. The causal form claims A produced B; the inferential form claims B *follows from* A, which is a claim about entailment rather than about the world. Filing "therefore" under `causal-discharge` would have been one line of pack data and would have mislabelled the operation on every claim of this shape — and the operation is what a reader sees when the derived element renders. §9.7.2's list is versioned with this spec precisely so that extending it costs a version bump and a stated reason.

**Why the claim is worth recording.** Its entire rhetorical structure is the inference. The observation (*"you don't see a curve"*) and the conclusion (*"the earth is flat"*) both fall outside §2's scope — no custodian publishes either — so the pipeline correctly returns **Insufficient Data** and correctly refuses **False**, however obviously wrong the claim is. What the reader needs is not a verdict but the inference made explicit, which is exactly what §6.3's `implied-by-original-only` exists to provide. Under v0.4 that output was silently unavailable, for two independent reasons that v0.5 closes: the operation did not exist, and Stage 1 discarded derived elements entirely (§9.10).

---

## 0b. What changed in v0.4

v0.3 closed the last two design questions and was, on paper, complete. Building against it surfaced four gaps that only appear when something has to execute: three where a competent implementer would have to invent a rule the spec never states, and one where a stated guarantee did not hold.

| Area | v0.3 | v0.4 |
|---|---|---|
| Pack lexicons | Derivation triggers given as English phrases; forbidden connectives specified "in each pack's declared languages" with no place to declare them | Resolved — a fifth required pack block, [Pack Interface §3.6](custodian-pack-interface.md#36-lexicons) |
| Element surface text | Stage 7 composes surviving elements; nothing said what text an element contributes | Resolved — the **element-surface grammar** (§9.9) |
| Stage 2 decomposition | Generation disciplined at Stages 7 and 9, unconstrained at Stage 2 | Resolved — anchoring extended to elements (§9.7.1), tested by [AC-18](acceptance-criteria.md#ac-18--element-anchoring) |
| `claim_context` language | Listed as "claim language"; [AC-17](acceptance-criteria.md#ac-17--jurisdiction-projection) asserts the structure carries no free text | Resolved — declared a language code (§9.8.1) |

The Stage 2 gap was the serious one, and it is the same shape as the two v0.3 closed. §9.7 shut the door on invented *derived* elements while leaving it open on invented *ordinary* elements — and an ordinary element is strictly more dangerous, because it can bind to a real measure, retrieve a real figure, reach **Verified**, and enter a reconstruction carrying the full citation apparatus. The fix is the one §9.7.1 already established: anchor it to a span.

The lexicon gap is smaller but would have been corrosive. With nowhere to declare trigger phrases, an implementer either hardcodes English into the pipeline — which §9.4 forbids outright — or silently under-fires on every other language a pack declares. The first violates the architecture; the second fails invisibly, which is worse.

---

## 0c. What changed in v0.3

v0.2 closed the design questions but left Stage 9 unimplementable and Stage 4 dependent on an input it had no rule for obtaining. Both are now closed, and both turned out to be safety questions rather than plumbing.

| Area | v0.2 | v0.3 |
|---|---|---|
| Derived-element generation | Tagging defined, generation unspecified — "a creative act inside a system built to prevent creative acts" | Resolved — **extraction, not invention**. Anchored spans, a closed operation list, no world knowledge, never verified, gated (§9.7) |
| Jurisdiction detection | Assumed known before pack lookup | Resolved — provenance **split at ingest**, only a jurisdiction *code* crosses into the verification path (§9.8) |
| Acceptance criteria | 15 | 17, plus an extended AC-6 covering the derived-jurisdiction path |

The jurisdiction fix is the more interesting of the two: §9.4 needed provenance and §7.6 forbade it, and the resolution was to narrow what crosses the boundary to something structurally incapable of carrying claimant identity.

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
| Reconstruction | Single subtractive pass | **Versioned** — re-derived as a pure function of the element set on every change, producing a revision trajectory. Causal clauses structurally excluded at every revision (§9.6) **[new in v0.2]** |
| Anti-laundering constraints | Six prose principles | Fifteen numbered acceptance criteria with pass/fail tests ([acceptance-criteria.md](acceptance-criteria.md)) |

Sections 1–8 are carried forward from v0.1 with amendments marked **[v0.2]** and **[v0.3]**.

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
| 7 | **Reconstruct** | Subtractive rebuild from surviving elements only. Emit discard ledger. Re-derived as a new revision whenever an element status changes **[v0.2]** |
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

### Stage 7 is versioned, not incremental **[v0.2]**

Reconstruction is not a one-shot pass. Element statuses change over time — an Unreachable custodian comes back, a provisional print revises, a newly-declared series break invalidates a comparison — and each change produces a **new reconstruction revision**.

The governing rule:

> A reconstruction is a **pure function of the current verified element set**. Every revision is re-derived from scratch from that set. No revision is ever produced by editing the text of a previous revision.

This distinction is the whole safety property, and it is easy to get wrong because the naive implementation looks equivalent. An append-based reconstructor — one that takes the previous sentence and adds a clause when a new element verifies — is a text generator that accretes. It cannot shrink correctly when an element regresses, and it accumulates connective phrasing that no element licenses. A re-derived reconstructor is a deterministic projection of evidence, and shrinking is just as natural to it as growing.

**Revisions are not monotone.** §8 invalidates verdicts pinned to a provisional print when a revision publishes, so an element can move from Verified to Contradicted and the reconstruction gets *smaller*. A shrinking revision is a first-class output, not an error state: a claim that gained support and then lost it is exactly the trajectory the system should make visible.

**The revision trajectory is itself an output.** The sequence of reconstructions, each with the element-set it derived from and the retrieval that triggered it, shows how a claim's support accumulated or eroded. This is the natural companion to §6.3's `implied-by-original-only` tag: one shows what people believed because of the unsupported parts, the other shows when those parts were and were not supported.

**What can never enter, at any revision.** Because every revision is composed only of surviving elements, and opinion, prediction, and causal fragments are marked Out of scope at Stage 1 and can never become Verified, no revision at any point in the trajectory can contain an evaluative or causal clause. This is a structural guarantee rather than a style rule — there is no code path by which such a clause reaches the reconstructor, because the reconstructor reads only the verified element set. See §9.6.

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
claims            id, text, stated_at, type (original|reconstructed|derived),
                  claim_context_id, claimant_identity_id                   [v0.3]
claim_context     id, jurisdiction_hint, language, stated_at              [v0.3]
claimant_identity id, name, affiliation, role, venue, audience            [v0.3]
elements          id, claim_id, fragment, measure_id, status,
                  tolerance_band, continuity_status,                       [v0.2]
                  source_span_start, source_span_end                       [v0.4]
derived_elements  id, from_claim_id, text, tag, state,                     [v0.3]
                  source_span_start, source_span_end, derivation_operation,
                  confirmed_by, confirmed_at
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

reconstructions   id, claim_id, revision, text, element_set_hash,          [v0.2]
                  derived_at, triggered_by_retrieval_id, does_reconstruct
packs             id, jurisdiction_id, version, maintainer, loaded_at      [v0.2]
series_breaks     id, measure_id, effective_date, kind,                    [v0.2]
                  custodian_notice_ref, linked_series_available,
                  linked_series_identifier
sweeps            id, claim_id, test, alternative, conclusion_holds,       [v0.2]
                  computed_from_retrieval_id
```

`sweeps` rows are the flip table (§9.3). Each row cites the retrieval it was computed from, so the sweep is bound by §3 exactly as the primary verification is: a sweep cell computed from anything other than a recorded retrieval is a fabricated comparison.

`reconstructions` rows are the revision trajectory (§4, Stage 7). `element_set_hash` is what makes the pure-function property checkable after the fact: two revisions with the same hash must have identical text, and a revision whose text does not re-derive from its recorded element set is evidence the reconstructor edited rather than re-derived. `does_reconstruct` carries the "does not reconstruct" outcome as a value rather than as an empty string, so a claim whose surviving elements do not compose is distinguishable from one with nothing left.

**[v0.3]** v0.2 held provenance in a single `source_attribution` field on `claims`, excluded from the verification path by convention. That is now a structural split: `claim_context` (a jurisdiction code, language, and date — crosses into verification) and `claimant_identity` (name, affiliation, role, venue, audience — never crosses). §9.8 explains why venue in particular had to move to the identity side. A single field excluded by convention passes AC-6 until someone adds a feature; two tables cannot be conflated by accident.

`derived_elements` is separated from `elements` deliberately (§9.7.4). Derived elements carry a relationship tag and never a status, never a retrieval, never a tolerance band — the absence of those columns is the guarantee, expressed in the schema rather than in a rule someone has to remember.

**[v0.4]** `elements` gains the same span columns `derived_elements` has carried since v0.3 (§9.7.1). The two tables now anchor identically and diverge only where they should: an element has a status, a retrieval, and a tolerance band; a derived element has a tag. That both are anchored to the claim text is the property; that only one is verifiable is the separation.

`claim_context.language` is a language code, not a label (§9.8.1). Every column on `claim_context` is now a code or a date, which is what makes AC-17's no-free-text assertion a statement about the schema rather than about current usage.

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

**Register entry**, persisted to `series_breaks` (per [Pack Interface §3.5](custodian-pack-interface.md#35-series-break-register)): effective date, kind (`base_year` | `methodology` | `definition` | `classification` | `coverage`), the custodian's own notice announcing it, and whether a linked or back-cast series spans it.

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

### 9.6 Can a reconstruction acquire a causal clause? — no, and the alternative

**The question.** If reconstruction is versioned (§4, Stage 7), a natural next step suggests itself: as more elements verify, the reconstruction grows back toward the original claim. Given *"inflation is up due to governmental incompetence over the last three years"*, verifying the price series yields *"over the last three years, inflation rose."* If a later step could establish that government action was the dominant driver, the reconstruction would become *"over the last three years, inflation rose, most likely due to government action or inaction."*

**Decision.** The first step is exactly right and is what §4's versioned reconstruction does. The second step is prohibited, and no configuration enables it.

**Why the causal clause cannot enter.** Three independent reasons, any one of which is sufficient:

1. **No custodian.** §3 requires every element to originate from a retrieval against a named institution with a mandate to publish the figure, a stated methodology, and a cadence. No institution publishes *the share of inflation attributable to government action*. There is nothing to retrieve, so there is no element, so there is nothing for the reconstructor to compose. This is not a coverage gap that a better pack would close — the figure does not exist as a published series anywhere.
2. **Attribution requires a model, and the model chooses the answer.** Establishing that policy drove a price series means running a counterfactual — a structural model, a synthetic control, a decomposition. Reasonable economists select different models and reach different attributions from identical data. That is §2's fourth exclusion with one word changed: *source* selection becomes *model* selection, and the outcome still follows from the choice rather than from the record. Verification would be argument wearing a verification badge.
3. **"More than other factors" is strictly harder.** Comparative attribution requires attributing *every* competing factor — global energy prices, exchange rates, supply conditions, monetary policy — and ranking them. Each carries its own model dependence, and the ranking amplifies rather than cancels them.

**Why this is the highest-stakes case in the spec.** A causal clause in a reconstruction would be the most valuable output the system could possibly produce for someone seeking to launder a conclusion. It would arrive wearing a citation trail, a custodian name, and a verification stamp — the full apparatus of §5 — attached to a sentence whose operative word was never verified by any of it. Every other constraint in §7 would still pass while the artifact as a whole became precisely the laundering device §7 exists to prevent. The mechanism is worth naming plainly: the verified elements would be doing evidentiary work for a proposition they do not support, and the reader would have no way to see the seam.

**What happens to the causal claim instead.** It is not discarded silently. It routes to §6.3 as a derived element tagged **`implied-by-original-only`** — it followed from the original, it depends on elements that did not survive, and it dies with them. §6.3 names this the most analytically valuable output of the whole system, and this is the case that shows why: the output records that people took away *"the government caused this"* from a claim whose only verified content was *"inflation rose."* That gap, made explicit and attached to the record, is a more useful artifact than a causal verdict would have been, and it is honest in a way a causal verdict could not be.

**What can legitimately verify near a causal claim.** Adjacent administrative facts are ordinary in-scope elements, each with a real custodian:

- *"Policy X took effect on date D"* — custodian: the official gazette or legislative record.
- *"The series moved in direction Y from date D onward"* — custodian: the statistical office.

Both can be Verified, and both can appear in a reconstruction. What the reconstructor may never do is **compose them into a causal connective**. "Policy X took effect in March, and prices rose from March" is two verified elements. "Prices rose because of policy X" is a third claim that neither element supports, and post-hoc composition is the oldest way to imply causation without asserting it. §7's rule that reconstruction "never supplies connective claims" is the operative constraint, and this is its most important application — not stylistic tidiness but the specific bar against assembling a causal implication out of non-causal parts.

Tested by [AC-15](acceptance-criteria.md#ac-15--reconstruction-determinism-and-composition).

### 9.7 Derived-element generation — extraction, not invention

**The problem.** §6.3 defines how derived claims are *tagged* but not how they are *produced*. Stage 9 has to generate the sentence *"the government caused this"* before it can tag it `implied-by-original-only`. That is a generative act inside a system whose entire architecture exists to prevent generative acts, and until now it was unconstrained.

It is also the highest-value output in the system and the most abusable. A generator free to invent "implications" can attribute to a claimant a belief they never expressed, and then present that attribution inside an artifact carrying custodian names, citation records, and a verification stamp. This is the §9.6 laundering shape arriving through a door that was still open.

**Decision.** Derived elements are **extracted from the claim's own text, never inferred from world knowledge.** Generation is a closed set of transformations applied to spans of the original.

#### 9.7.1 The anchoring rule

> Every derived element MUST cite a **span of the original claim text** it derives from. A derived element with no anchoring span is inadmissible and is not emitted.

This is the direct analogue of §3. Where §3 says every *figure* traces to a retrieval, §9.7 says every *derived claim* traces to a span. Both replace "the system produced this" with "here is where it came from."

**[v0.4] The rule extends to Stage 2 elements.** Anchoring was written for derived elements because those were the visible generative act. Ordinary elements are produced by a generative act too — Stage 2 reads claim text and emits structured elements — and that act was left unconstrained by v0.3 and untested by any criterion.

> Every element MUST cite a span of the claim text it was decomposed from, recorded in `elements.source_span_start` and `elements.source_span_end`. An element with no resolving span is inadmissible and is not emitted. No element may introduce an entity, quantity, unit, or time period absent from the claim text.

The asymmetry in the original design was backwards. A fabricated derived element is inert: §9.7.4 forbids it from carrying a status, a retrieval, or a place in any reconstruction, so the worst it can do is misattribute an implication — serious, and the reason §9.7.5 exists. A fabricated *ordinary* element is live. It binds to a real measure at Stage 3, routes to a real custodian at Stage 4, retrieves a real published figure at Stage 5, and can reach **Verified** at Stage 6. It then enters the reconstruction wearing a custodian name, a series identifier, a reference period, and a verification stamp — every component of §5's citation apparatus, attached to a proposition the claimant never made.

The mechanism is worth naming precisely, because it is subtle: nothing malfunctions. Every retrieval is genuine and every citation resolves. An element invented at Stage 2 — a time period the claim never stated, an entity it never named — produces an artifact in which each part is individually true and the whole is about something nobody said. That is §9.8.3's no-default-jurisdiction failure arriving through a different door, and it has the same signature: a confident, fully-cited verdict with no internal symptom.

Tested by [AC-18](acceptance-criteria.md#ac-18--element-anchoring), which mirrors AC-16's anchoring and no-new-entities tests over `elements`.

#### 9.7.2 Admissible derivation operations

A closed, versioned list. Generation applies one of these to an anchored span and nothing else:

| Operation | Trigger span | Produces |
|---|---|---|
| `causal-discharge` | A causal connective — "due to", "because of", "thanks to", "caused by" | The explicit causal claim linking the flanking elements |
| `inferential-discharge` **[v0.5]** | An inferential connective — "therefore", "hence", "which proves", "so" | The explicit entailment claim: that the conclusion follows from the premise |
| `superlative-discharge` | A superlative or ordinal — "highest ever", "first time in N years" | The explicit ranking claim |
| `comparative-discharge` | A comparison — "more than", "twice as", "worse than" | The explicit comparative claim |
| `evaluative-discharge` | A value judgment — "incompetence", "failure", "success" | The evaluative claim the wording invites |
| `scope-discharge` | A universal or scope quantifier — "all", "every", "always", "nobody" | The scope claim as stated |

The list is versioned with the spec and is **not operator-configurable**, on the same footing as the routing tables and the tolerance bands (§7.3). An operator who can add derivation operations can manufacture implications, which is the whole risk restated.

**[v0.5] On the distinction between the first two rows.** `causal-discharge` and `inferential-discharge` look adjacent and are not. *"Prices rose due to the reform"* asserts that the reform produced the rise — a claim about the world, which §9.6 establishes has no custodian. *"You see no curve, therefore the earth is flat"* asserts that the conclusion follows from the observation — a claim about entailment, which is not a claim about the world at all and has no custodian for a different reason. Both discharge to a derived element and neither is ever verified, so the operational consequence is identical; the *label* differs, and the label is what a reader sees. Collapsing them would tell every reader of an inferential claim that the claimant asserted a causal mechanism they may never have asserted, which is the harm §9.7.5 exists to prevent.

#### 9.7.3 The no-world-knowledge rule

> A derived element may not introduce an entity, quantity, time period, or relation that does not appear in the original claim.

This is the line that makes generation checkable. Working from *"inflation is up due to governmental incompetence"*:

| Candidate derived element | Admissible? | Why |
|---|---|---|
| "The government caused inflation to rise" | **Yes** | `causal-discharge` of the "due to" span. Every entity — government, inflation, rise — appears in the original |
| "The government's fiscal policy was expansionary" | **No** | Introduces *fiscal policy*, an entity absent from the claim. This is world knowledge, not extraction |
| "Inflation would have been lower under a different government" | **No** | Introduces a counterfactual the text does not contain |

The second and third are the kind of output that would make the system genuinely dangerous: fluent, plausible, apparently derived, and entirely invented.

#### 9.7.4 Derived elements are never verified

A derived element receives a §6.3 relationship tag and **nothing else**. It never gets an element status, never routes to a custodian, never produces a retrieval, and never enters a reconstruction. It is a record of what the claim invites a reader to conclude — not a proposition the system has checked.

This separation is load-bearing. A derived element that could carry Verified would be a mechanism for laundering an invented implication into a checked fact, defeating §9.6 by a different route.

#### 9.7.5 Rendered as implication, never as quotation

Derived elements render as *what the claim invites the reader to conclude*, never as *what the claimant asserted*. The claimant wrote "due to incompetence"; they did not necessarily assert the specific causal proposition the discharge produces. Presenting a discharged implication as a quotation would put words in a named person's mouth inside an authoritative-looking artifact — a serious harm, and an easy one to cause by accident through careless phrasing.

#### 9.7.6 Derived elements are gated

Because they are model-produced text rather than retrieved fact or a mechanical function of retrievals, derived elements are emitted as `proposed` and require human confirmation before publication, on the same footing as the claim-level verdict (§9.1). They are the only output in the system with this property, which is precisely why they are gated.

Tested by [AC-16](acceptance-criteria.md#ac-16--derived-element-anchoring-and-closure).

### 9.8 Jurisdiction detection — a projection, not a lookup

**The problem.** §9.4 resolves a claim to a pack by jurisdiction, but assumes the jurisdiction is known. Claims routinely arrive without one: *"inflation is up."*

The obvious fix is to read it from Stage 0 provenance — who said it, where, to what audience. That fix collides head-on with §7.6, which forbids claimant metadata from reaching the verification path. Venue text is the specific hazard: *"speech at the party conference"* is nominally venue metadata and functionally an identification of the claimant's affiliation. Passing provenance downstream with a convention that the pipeline "won't look at the name" fails AC-6 the moment anyone adds a feature.

**Decision.** Provenance is **split at ingest**, and only a jurisdiction code crosses into the verification path.

#### 9.8.1 The ingest split

Stage 0 divides provenance into two structures, at ingest rather than at point of use:

| Structure | Contents | Reaches verification path |
|---|---|---|
| `claim_context` | `jurisdiction_hint` — an ISO jurisdiction code or null. `language` — an ISO 639 language code **[v0.4]**. Stated-at date | **Yes** |
| `claimant_identity` | Name, party, affiliation, role, venue text, audience | **Never** |

The critical constraint: `claim_context.jurisdiction_hint` is **a code, not free text**. A code cannot smuggle claimant identity; a venue string can and eventually will. Splitting at ingest rather than filtering at use means there is no downstream code path that *could* read the identity, which is what makes AC-6's static-reachability assertion hold rather than merely pass today.

**[v0.4]** The same constraint governs `language`, which v0.3 named without typing. AC-17 asserts that `claim_context` carries no free-text field, so a free-text language label would have falsified the criterion on the structure it exists to protect — and a field accepting arbitrary text is a channel regardless of what anyone intends to put in it. Every field crossing into the verification path is a code or a date; that is the whole property, and it holds only if it holds without exception.

#### 9.8.2 Resolution order

1. **Explicit in the claim text** — *"inflation in Israel"* binds directly. Preferred, because it needs no provenance at all.
2. **`jurisdiction_hint`** from the ingest projection.
3. **Jurisdiction-invariant measure** — the claim concerns a supranational measure with its own custodian; route to that pack.
4. **Otherwise → Insufficient Data.**

Each resolution records which rule fired, in `routing_log`.

#### 9.8.3 No default jurisdiction, ever

There is no fallback jurisdiction, no "most likely" inference, and no operator-set default. A default is not a convenience — it is a silent assumption that systematically mis-routes every claim originating elsewhere, and it fails in the worst possible way: a confident, fully-cited verdict retrieved from the wrong country's custodian. Every element would be genuinely Verified, every citation genuinely real, and the whole artifact wrong.

Insufficient Data is the correct outcome for a claim whose jurisdiction cannot be established, and §7.5 already requires it to render as a first-class answer.

Tested by [AC-17](acceptance-criteria.md#ac-17--jurisdiction-projection) and by the extended [AC-6](acceptance-criteria.md#ac-6--claimant-blindness).

### 9.9 Element surface grammar **[v0.4]**

**The problem.** §4 Stage 7 requires reconstruction to compose surviving elements into text, and [AC-15](acceptance-criteria.md#ac-15--reconstruction-determinism-and-composition) requires that text to be byte-identical every time it is re-derived from the same element set. But Stage 2 produces *structured* elements — entity, quantity, unit, time period, comparison basis — and nothing in v0.3 said what text a structured element contributes. Two implementers reading v0.3 produce different reconstructions from an identical verified element set, and both satisfy every word of the spec.

That is not a cosmetic gap. AC-15's determinism test compares stored text against re-derived text; without a fixed grammar the test is comparing an implementation against itself, which it will always pass, while the property the criterion exists to guarantee — that a reconstruction is a projection of evidence rather than an authored sentence — goes untested.

**Decision.** Reconstruction text is produced by a **closed, versioned grammar**. Composition is deterministic template assembly over the verified element set. It is never a language model, and no configuration surface substitutes one.

#### 9.9.1 The grammar

Three parts, in order:

1. **Surface form per element.** Each verified element renders into a fixed slot order — time period, entity, measure name, direction or comparison basis, quantity with unit — declared per language in the pack ([Pack Interface §3.6](custodian-pack-interface.md#36-lexicons)). Slots with no bound value are omitted, never filled with a default. Quantities render at the custodian's published precision, from the retrieval, per §3.
2. **A total order over elements.** Elements sort by `source_span_start`, then by element id. The order is a property of the claim text and the element set, never of retrieval timing, insertion order, or hash iteration — each of which would make the same element set render differently across runs.
3. **Joining.** Surface forms join using **enumeration and sequencing connectives only**, drawn from the pack's declared `composition_connectives`. Nothing else is permitted between two elements.

#### 9.9.2 The connective allowlist is the safety property

The allowlist admits enumeration ("and", ", ") and sequencing ("then"). It admits nothing causal ("because", "due to", "as a result of"), nothing evaluative ("worryingly", "only"), nothing concessive ("although", "despite"), and nothing explanatory ("which shows", "meaning").

The distinction is not stylistic. Two verified elements — a policy effective date and a series movement — are two facts. Joined with "and" they remain two facts. Joined with "because" they become a third claim that neither element supports, asserted in a sentence carrying both elements' citation records. §9.6 works this case through in full and calls the composition bar its most important application; §9.9 is where that bar becomes a data structure rather than an instruction.

Before emission, the composed text is scanned against the pack's `forbidden_connectives` for the claim's language. A match fails the reconstruction rather than warning, on the same footing as an unsourced figure failing a render ([AC-7](acceptance-criteria.md#ac-7--no-unsourced-figure)). A connective may appear in output only where it originates inside a single verified element that already carries it.

#### 9.9.3 When the grammar cannot compose

If the surviving elements do not fill the grammar — no element carries a quantity, or the survivors share no time period and no entity — the reconstruction returns `does_reconstruct` false, carrying the element list. §4's Stage 7 already requires this: the correct output is the element list plus "does not reconstruct," never a smoothed-over sentence. The grammar makes it a return value rather than a judgment.

**Rationale.** A reconstructor built to produce fluent prose will reach for a connective to smooth two adjacent verified facts, and AC-15 names this the failure an implementation is most likely to commit by accident. The defence cannot be a review instruction, because the output will read well — that is precisely the problem. Fixing the grammar means the reconstructor has no vocabulary for the sentence it should not write. Declaring the surface strings per language in the pack keeps jurisdictional knowledge out of the pipeline (§9.4) while leaving the grammar's *structure* versioned with this spec and not operator-configurable ([AC-3](acceptance-criteria.md#ac-3--non-configurability)).

### 9.10 Out-of-scope claims still surface their derived elements **[v0.5]**

**The problem.** §4 Stage 1 routes opinion, prediction, causal, and no-custodian claims out "with explanation, no verdict." Read literally, a claim routed out at Stage 1 never reaches Stage 9, so it emits no derived elements at all. That silently discards §6.3's `implied-by-original-only` — which §6.3 calls "the most analytically valuable output of the whole system" — for precisely the claims where it carries the most information: those whose entire content is a rhetorical move.

The worked case is *"you don't see a curve, therefore the earth is flat."* Every fragment is out of scope, so under a literal reading the system returns Insufficient Data and nothing else. But the reader's actual question is not *"what does the record say?"* — the record says nothing, correctly. It is *"what is this claim doing?"* The inference, made explicit and attributed to no one, is the whole available answer.

**Decision.** A claim routed out at Stage 1 **still runs decomposition and derivation**. The artifact carries its discard ledger and its derived elements. It carries no verdict beyond the Stage 1 outcome, no reconstruction, and — critically — **no retrieval**.

The retrieval exclusion is not incidental. A claim that bound no measure has nothing to retrieve *for*, and pulling a series to display beside it would put a custodian's figure next to a proposition that figure does not address. That is §9.6's laundering shape reached by a different route, and it is the reason this decision stops short of the fuller treatment prior art adopts: the `israeli-fact-checker` skill's method presents baseline data alongside an out-of-scope claim, which is defensible for a human analyst exercising judgment about relevance and is not defensible for a pipeline that has no such judgment to exercise.

**Consequence for tagging.** Where no element in a claim reaches Verified, every derived element is tagged `implied-by-original-only`. §6.3 defines that tag as depending on elements that did not survive; on a wholly out-of-scope claim nothing survived, so the tag follows by definition rather than by inference.

**Rationale.** The alternative — silence — makes the system least informative exactly where a claim is most rhetorically constructed, and a fact-checking tool that says nothing about a structured false claim has failed at the thing it is for. Nothing about this weakens §2: the claim still receives no verdict, no figure, and no reconstruction. What it receives is a record of what it invites a reader to conclude, gated and unverified, which is what §9.7.6 already requires of every derived element.

---

## 10. Remaining open questions

Genuinely open, and deliberately not resolved here.

1. **Sweep cost.** The robustness sweep multiplies retrievals per claim by the size of the admissible alternative set. Whether that is affordable against rate-limited custodian APIs is an operational question that needs measurement against a real pack, not a design answer. Blocked on an admitted pack.
2. **Sign-off throughput.** §9.1 puts a person on every claim-level verdict, and §9.7.6 adds derived elements to the same gate. At volume this is the binding constraint. Whether a reviewed-sample model can preserve the guarantee is unresolved, and weakening it should not be done quietly.
3. **Derivation coverage.** §9.7.2 fixes a closed list of **six** derivation operations **[v0.5]**. Whether those six cover the implication patterns that actually occur in public claims is an empirical question, answerable only against a corpus. The failure mode is silent: an implication with no matching operation is simply never surfaced, so the system under-reports rather than misreports. That is the correct direction to fail, but the gap should be measured rather than assumed small.

   **[v0.5]** This question is now narrower than it was, and the narrowing is instructive. The first real claim tested against the engine exercised a pattern the list did not cover — an inferential connective rather than a causal one — which is one data point suggesting the gap is not negligible. Five operations were not chosen carelessly; they were simply chosen without a corpus. The remaining question is no longer *whether* patterns are missing but *which*, and that still needs measurement rather than another round of introspection.
4. **Anchoring across paraphrase.** §9.7.1 requires every derived element to cite a span of the original. Claims that arrive paraphrased — reported speech, translation, a screenshot transcribed — have spans that do not correspond to what the claimant said. Whether anchoring should attach to the received text or the original utterance is unresolved, and it matters for §9.7.5, since the two can diverge in ways that change who is responsible for the implication.

   **Narrower than it looks.** The implementation holds exactly one text buffer per claim — `claim_text`, the string passed to `verify()` — and `Span` (§9.7.1) resolves positionally against it and nothing else. "Anchor to the original utterance" is therefore not a choice between two mechanisms the system already has; it is a request for a second reference frame the type system does not contain. Adding one would mean carrying both a received string and a claimed-original string through ingest, an alignment between their character offsets wherever they diverge, and a rule for what a derived element cites when the two disagree — a data-model change on the order of the §9.8.1 provenance split, not a parameter to an existing function.

   What that narrows the question to: anchoring mechanically always attaches to the received text, because today it is the only text there is, and that much is not actually open. What remains open is a presentation question one level up — whether §9.7.5's bar ("never present a derived implication as something the claimant asserted") needs a further qualifier when the received text is itself known to be someone else's rendering of the claimant's words, e.g. "the article reports that X said prices rose" is already once-removed, and a derived implication from it is an implication of the *report*, not necessarily of what X said. The system has no flag today marking a claim as reported speech, translated, or transcribed, so there is nowhere to attach that qualifier even if the presentation rule were decided. Closing this needs, in order: (1) a decision on whether ingest should carry a provenance-of-text flag at all, given §9.4's resistance to any field whose contents could smuggle judgment into the pipeline; (2) if so, a decided second reference frame and its alignment rule; only then does §9.7.5's wording change. None of the three is attempted here.

---

## 11. Prior art reviewed

- **Israeli fact-checker methodology** — supplied the custodian-routing model, the citation record, the insufficient-data fallback, the misleading category, and the catalogue of measure-confusion traps. Its key limitation relative to this design: it labels and stops, with no reconstruction, no derived-element mapping, and deliberate statelessness. Its source map is the basis for [packs/israel.md](packs/israel.md).
- **Here4Good / BrightMind AI** — the nearest live precedent, and a cautionary one. It pairs verification with a generation stack (meme generator, social post creator, thesis-first article writer) and operates primarily in historical-interpretive territory where no custodian exists. It is the reference case for why §2's fourth exclusion and all of §7 are load-bearing rather than decorative.
