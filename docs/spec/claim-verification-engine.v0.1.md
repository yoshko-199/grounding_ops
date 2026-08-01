# Claim Verification & Reconstruction Engine

**Draft specification v0.1**

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

---

## 3. Non-negotiable rule

> Every figure, date, amount, or ranking in any output MUST originate from a retrieval performed against a named custodian, recorded with its reference period. If no confirming retrieval exists, the output is **Insufficient Data**. No estimation, no inference from model priors, no "approximately."

A fabricated verification is worse than no verification, because it launders a guess into an authoritative-looking artifact. This rule has no exceptions and is not operator-configurable.

---

## 4. Pipeline

| # | Stage | Function |
|---|---|---|
| 0 | **Ingest** | Accept claim text + provenance (who said it, when, where) |
| 1 | **Scope gate** | Classify: quantitative/administrative → proceed. Opinion / prediction / causal / no-custodian → route out with explanation, no verdict |
| 2 | **Decompose** | Split into atomic elements: entity, quantity, unit, time period, comparison basis, ranking assertion |
| 3 | **Context recovery** | Establish baseline and disambiguate measure. Bind each element to a specific measure definition before choosing a source. Check the *most charitable correct reading*, not the easiest to retrieve |
| 4 | **Route** | Map each element's measure to its authoritative custodian. Log the routing decision and its rationale |
| 5 | **Retrieve** | Pull the figure. Record the citation quad + revision status (see §5) |
| 6 | **Element verdict** | Assign one status per element (see §6.1) |
| 7 | **Reconstruct** | Subtractive rebuild from surviving elements only. Emit discard ledger |
| 8 | **Claim-level evaluation** | Evaluate the *reconstructed* claim as a whole (see §6.2). Element-level truth does not imply claim-level honesty |
| 9 | **Derive** | Identify implied/adjacent claims; map each to original and reconstructed (see §6.3) |
| 10 | **Persist** | Store as retrieval events with validity windows, not as timeless facts |

### Stage 3 is not optional

The most common way a true number becomes a misleading claim is measure ambiguity. Before routing, every element must be bound to a specific measure definition:

- nominal vs. real
- planned vs. executed
- survey-based vs. registry-based
- monthly change vs. annualised
- asking price vs. recorded transaction
- provisional print vs. revised final

Two authoritative institutions can both be correct and disagree, because they measure different things. "Primary source" is not a sufficient category — **measure identity is the actual unit of correctness.**

### Stage 7 is subtractive by construction

Reconstruction removes; it never adds, rephrases toward a conclusion, or supplies connective claims. If the surviving elements do not compose into a coherent statement, the correct output is the element list plus "does not reconstruct," not a smoothed-over sentence.

### Stage 8 exists because verified parts can compose a false whole

A claim assembled entirely from verified elements can still create a false impression through omission, selective baseline, or cherry-picked window. This is the standard mechanism of sophisticated misinformation and the single largest gap in a naive design. The reconstructed claim gets its own evaluation, independent of its parts.

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

---

## 6. Taxonomies

### 6.1 Element status

| Status | Meaning |
|---|---|
| **Verified** | Custodian figure confirms the element within stated tolerance |
| **Contradicted** | Custodian figure conflicts with the element |
| **Unverified** | Custodian reached, no figure covers this element |
| **Unreachable** | Custodian could not be reached this session — operationally distinct from Unverified, and must not silently collapse into it |
| **Contested by definition** | Two authoritative custodians differ because they measure different things. Both reported, with the definitional gap explained |
| **Out of scope** | Opinion, prediction, or causal fragment |

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

---

## 8. Persistence model

The database stores **retrieval events, not facts.** This distinction is the whole design.

A cached figure reused without re-checking is functionally identical to a figure recalled from model memory — the exact failure mode §3 exists to prevent. Therefore:

- Every retrieval carries a **TTL derived from its custodian's publication cadence**. Expired retrievals are re-pulled, never served.
- **Provisional retrievals are invalidated when a revision publishes.** A claim true against the first print can be false against the revised figure; verdicts pin to a specific revision.
- Verdicts carry **validity windows**, not boolean flags. "Verified" is always "verified against series X, revision Y, as of date Z."
- Custodians carry an **integrity annotation**: is this source itself subject to contestation, adversarial editing, or coordinated manipulation? A verified fact drawn from a compromised custodian propagates the compromise with a verification stamp attached.

### Rough schema

```
custodians        id, name, mandate, cadence, integrity_notes
measures          id, name, definition, custodian_id, known_confusions[]
claims            id, text, source_attribution, stated_at, type (original|reconstructed|derived)
elements          id, claim_id, fragment, measure_id, status
retrievals        id, element_id, figure, series_id, reference_period,
                  revision_status, retrieved_at, ttl, caveat
verdicts          id, claim_id, label, rationale, valid_from, valid_until
discards          id, reconstructed_claim_id, element_id, reason
relationships     id, from_claim_id, to_claim_id, tag
routing_log       id, element_id, custodian_id, rationale, alternatives_considered
```

---

## 9. Open questions

1. **Human sign-off**: fully automated, or automated retrieval with human verdict confirmation? Automated verdicts on political claims carry reputational risk that a human-in-loop model avoids.
2. **Tolerance bands**: at what deviation does a rounded figure move from Verified to Substantially inaccurate? Needs to be a published, fixed rule, not a judgment call.
3. **Detecting Stage 8 misleadingness**: element verification is mechanical; "creates a false impression" is not. This is the hardest unsolved piece. Candidate approach: test the reconstructed claim against alternative baselines and windows from the same series, and flag when the conclusion flips.
4. **Geographic scope**: one country's custodian set first, or generalised routing from the start? A single jurisdiction gives a tighter, more defensible v1.
5. **Series-change handling**: methodology revisions, base-year changes, and definitional breaks fracture long series. Detection strategy needed.

---

## 10. Prior art reviewed

- **Israeli fact-checker methodology** — supplied the custodian-routing model, the citation quad, the insufficient-data fallback, the misleading category, and the catalogue of measure-confusion traps. Its key limitation relative to this design: it labels and stops, with no reconstruction, no derived-element mapping, and deliberate statelessness.
- **Here4Good / BrightMind AI** — the nearest live precedent, and a cautionary one. It pairs verification with a generation stack (meme generator, social post creator, thesis-first article writer) and operates primarily in historical-interpretive territory where no custodian exists. It is the reference case for why §2's fourth exclusion and all of §7 are load-bearing rather than decorative.
