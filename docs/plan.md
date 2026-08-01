# Plan: Claim Verification & Reconstruction Engine — spec v0.2

## Context

`grounding_ops` is an empty repository (no commits). A draft spec v0.1 for a **Claim Verification & Reconstruction Engine** was uploaded: a system that decomposes a public claim into atomic elements, verifies each against a named custodian of record, and rebuilds a grounded version of the claim inseparable from a ledger of what was discarded and why.

The draft is architecturally sound but ends with §9: five open questions it explicitly refuses to answer. Three of them are load-bearing — without a fixed tolerance rule, a concrete misleadingness procedure, and a jurisdiction model, the spec cannot be implemented consistently by two different people. And §7's anti-laundering constraints are written as prose principles, which means nothing can fail a build for violating them.

Prior art exists and is already researched: the `israeli-fact-checker` skill in `~/.claude/skills/israeli-fact-checker/` (outside this repo). It already implements the draft's Stages 1–6: claim isolation, measure disambiguation, custodian routing (`references/source-map.md`), the four-field citation trail, the Whistle verdict scale plus an anti-fabrication fallback, and the "never invent a figure" rule. It does **not** have Stage 7 reconstruction, Stage 9 derived elements, or Stage 10 retrieval-event persistence. Its `references/source-map.md` and `references/domain-checklist.md` are the source material for the Israel custodian pack.

**Deliverable:** documents only — no code, no skill, no runtime. Resolve all five §9 questions, tighten the draft into v0.2, and convert §7 into testable acceptance criteria.

**Decisions already made by the user** (do not re-open):
- §9.1 Human sign-off → automated retrieval and element verdicts, **human confirmation gate on the claim-level verdict**.
- §9.4 Geographic scope → **generalised custodian routing from the start**, with Israel as the first populated pack.

---

## Files to create

All new; the repo is empty.

| Path | What it is |
|---|---|
| `README.md` | What `grounding_ops` is, what's in `docs/`, status (spec stage, no implementation) |
| `docs/spec/claim-verification-engine.v0.1.md` | The uploaded draft, verbatim, archived for diffing |
| `docs/spec/claim-verification-engine.v0.2.md` | **The main deliverable** |
| `docs/spec/acceptance-criteria.md` | §7 + §3 as numbered, testable ACs |
| `docs/spec/custodian-pack-interface.md` | Normative contract a jurisdiction pack must satisfy |
| `docs/spec/packs/israel.md` | Reference pack instance, ported from the existing skill's `source-map.md` |

Archive v0.1 verbatim from `/root/.claude/uploads/b2f599db-bcde-5834-be3b-cd010764ecec/83612b78-claimverificationenginespec.md`. Versioning the spec in-repo is the spec practising its own §7.3 ("inspectable and versioned").

---

## Substance: what v0.2 must resolve

### §9.1 Human sign-off → resolved: automated pipeline, gated claim verdict

- Element verdicts (§6.1) are automated and final on retrieval. No gate.
- The claim-level verdict (§6.2) is emitted as `proposed` and requires explicit human confirmation to become `confirmed`. States: `proposed → confirmed | amended | rejected | expired`.
- An amendment never overwrites the proposal — both are retained with an amendment rationale.
- **The gate may only change the claim-level label.** Sign-off cannot mutate element statuses, retrievals, or the discard ledger. An unconstrained human gate is itself a laundering vector; this restriction is what stops it from becoming one.
- A `proposed` verdict renders visibly marked as unconfirmed and cannot export.
- Schema delta on `verdicts`: `state`, `proposed_at`, `confirmed_by`, `confirmed_at`, `amended_from_label`, `amendment_rationale`.

### §9.2 Tolerance bands → resolved: a fixed rule derived from published precision

Tolerance is computed from the custodian's own published precision, never chosen per claim. Let `u` = the unit of the last published significant digit (CPI published as `3.2%` → `u = 0.1pp`).

| Band | Condition | Element status |
|---|---|---|
| A | claim rounds to the published figure at the claim's stated precision, **or** \|Δ\| ≤ max(`u`/2, 0.5% relative) | Verified |
| B | \|Δ\| ≤ max(`u`, 2% relative) | Verified, tagged `rounded` |
| C | beyond Band B | Contradicted → feeds *Substantially inaccurate* |

Overrides that bypass the numeric bands entirely:
- **Superlative / ordinal** elements ("highest in N years") — binary. The full series supports it or the element is Contradicted. No tolerance.
- **Direction** elements ("rose", "fell") — binary on sign. Wrong direction is Contradicted at any magnitude.
- **Discrete counts** (seats, votes, licences) — exact match, tolerance zero.
- **Percent vs percentage-point** confusion is not a tolerance question — it is a measure-identity failure and routes back to Stage 3 binding; if genuinely ambiguous, `Contested by definition`.
- **Nominal vs real** likewise: bound at Stage 3, never absorbed into tolerance.

The table is versioned and not operator-configurable (see AC-3).

### §9.3 Stage 8 misleadingness → resolved: the robustness sweep

A mechanical procedure over series already retrieved. It introduces no new claims and performs no new reasoning about "missing context" — that would reintroduce exactly the advocacy vector §2's fourth exclusion exists to block.

Four tests, all run against the reconstructed claim:
1. **Baseline sweep** — recompute the comparison against every *admissible* baseline the pack declares for that measure (prior period, prior year, series start, last methodological break, custodian-marked reference points).
2. **Window sweep** — vary window length across the custodian's own standard reporting windows (1m / 3m / 12m / YTD / 5y as the pack declares).
3. **Level-vs-change test** — if the claim asserts a change, check whether the level tells an opposing story, and the reverse.
4. **Bounded omission test** — only over (a) elements the decomposition already produced but that were discarded, and (b) the custodian's own published caveats attached to the series. Explicitly *not* an open-ended search for missing context.

Output is a **flip table**: every admissible alternative and whether the claim's qualitative conclusion holds under it.

Verdict rules:
- Conclusion holds under all admissible alternatives → not misleading on this axis.
- Flips under ≥1 → **Misleading** proposed, flip table attached as the evidence.
- Sweep cannot run (series too short, no admissible alternatives) → claim-level verdict is **capped at Indeterminate**. Never *Accurate*.

"Admissible" is declared by the custodian pack, not chosen per claim — otherwise the sweep itself becomes selectable and the whole test is defeated.

### §9.4 Geographic scope → resolved: generalised, via custodian packs

Routing becomes jurisdiction-agnostic; jurisdictions are data, not code. Full contract in `custodian-pack-interface.md`; the spec references it.

A pack declares: jurisdiction id and languages; **custodians** (name, statutory mandate, cadence, revision policy, integrity annotation, access method); **measures** (definition, custodian, `known_confusions[]`, admissible baselines and windows for the sweep, series-break register); **routing rules** (measure → custodian with `alternatives_considered`).

Resolution order: claim → jurisdiction detection → pack lookup → measure binding → custodian.

The critical guardrail: **if no pack covers the jurisdiction or measure, the outcome is Insufficient Data.** Generalising must never mean "when there's no custodian, fall back to a web search." That fallback would silently void §3.

Cross-jurisdiction comparisons ("X's inflation is above the OECD average") require a comparability check: if the two packs' measure definitions differ, the element is `Contested by definition` unless a supranational custodian publishes a harmonised measure covering both.

### §9.5 Series-change handling → resolved: break register + continuity check

- Every measure carries a **break register**: base-year changes, methodology revisions, definitional and classification changes, each with an effective date sourced from the custodian's own publication.
- **Continuity check** is mandatory for any element comparing figures across time. If the span crosses a break:
  - custodian publishes a linked/back-cast series → use it, record which;
  - it does not → `Contested by definition` or `Unverified`. **Never Verified by splicing.** Splicing across a break to manufacture a comparison belongs to the same class of error as §5's remembered historical peak.
- Because packs will always be incomplete, three detection signals supplement the declared register: custodian metadata/footnote flags on the series, a base-year field that changed between retrievals, and a step-discontinuity heuristic. All three **flag for review only** — they can never auto-verify.
- Schema delta: `series_breaks` table (`measure_id`, `effective_date`, `kind`, `custodian_notice_ref`, `linked_series_available`).

---

## `acceptance-criteria.md`

Each of §7's six constraints, plus the §3 non-negotiable rule and the new §9 resolutions, becomes a numbered AC with a stated pass/fail test. Sketch:

- **AC-1 Ledger inseparability** — enumerate every render/export/copy path; any path emitting reconstructed text without its discard ledger fails.
- **AC-2 No platform formatting** — no output path produces character-limited or share-formatted text; no share affordance exists.
- **AC-3 Non-configurability** — tolerance table and routing tables load from versioned pack files; no runtime setting mutates them; a change requires a pack version bump recorded in `routing_log`.
- **AC-4 Routing rationale exposed** — every element's output carries custodian, rationale, and `alternatives_considered`, all non-empty.
- **AC-5 Insufficient Data is first-class** — renders at the same prominence as any other verdict; carries no error styling or failure status.
- **AC-6 Claimant blindness** — run the same claim text under N different attributions; element statuses, retrievals, routing decisions, and the proposed verdict must be byte-identical. *(This is the sharpest of the set — it makes §7.6 mechanically falsifiable.)*
- **AC-7 No unsourced figure (§3)** — every figure in output resolves to a retrieval id; a figure without one fails render.
- **AC-8 TTL enforcement** — an expired retrieval is never served; it is re-pulled or the element degrades to Unverified.
- **AC-9 Provisional invalidation** — publishing a revision invalidates verdicts pinned to the provisional print.
- **AC-10 Gate integrity** — a `proposed` verdict cannot export as final; sign-off cannot mutate element statuses, retrievals, or the ledger.
- **AC-11 Sweep coverage** — where the robustness sweep cannot run, the claim-level verdict is capped at Indeterminate.
- **AC-12 Break integrity** — no element is Verified across a series break without a custodian-published linked series.

---

## `packs/israel.md`

Reference instance proving the interface is populatable. Ported from `~/.claude/skills/israeli-fact-checker/references/source-map.md` and `domain-checklist.md`:

- **Custodians:** CBS, Bank of Israel, BudgetKey/OpenBudget, Knesset ParliamentInfo OData, Central Elections Committee, Nadlan, Ministry of Justice Corporations Authority, Bituach Leumi, data.gov.il (CKAN catch-all).
- **Measures with `known_confusions[]`** — carried over directly from the skill's already-researched pitfalls: planned (תקציב מקורי) vs executed (ביצוע) budget; representative rate (שער יציג) vs market spot; CBS survey unemployment vs Sherut HaTaasuka registered job-seekers; statutory vs survey average wage; Nadlan recorded deals vs asking prices vs the CBS House Price Index; per-MK plenum votes living in the data.gov.il plenum-votes dataset and **not** in ParliamentInfo OData.
- **Integrity annotations** — e.g. known under-reporting in the amutot foreign-donation registry; partial publication of defence budget lines.
- Documentation only. No change is made to the installed skill in `~/.claude/skills/`.

---

## Out of scope for this change

No code, no schema migrations, no skill files, no modification to `israeli-fact-checker`. §8's schema appears in v0.2 only as an updated design sketch with the new tables and columns marked.

---

## Verification

Doc deliverable, so verification is a cross-reference audit rather than a test run:

1. **§9 closure** — all five questions carry a resolution and a rationale; none still reads "open" or "needs a strategy."
2. **§7 coverage** — every one of the six constraints maps to ≥1 AC, and every AC states a concrete pass/fail test, not a principle. Check by grepping AC ids back to their §7 clause.
3. **Schema completeness** — every field introduced in prose (`state`, `confirmed_by`, `amendment_rationale`, `series_breaks.*`) appears in the §8 schema sketch. Grep each name across the two files.
4. **Pack validation by hand** — walk `packs/israel.md` against every required field in `custodian-pack-interface.md`; a missing field means the interface is under-specified or the pack is incomplete. Either way, fix before commit.
5. **No fabricated figures** — the spec must contain no statistic, index value, or dated figure of its own. Institution names, mandates, and measure definitions only. The spec violating §3 in its own body would be self-refuting; read the diff specifically for this.
6. **Internal links resolve** — every relative link between the six files points at a file that exists.

## Git

Initial commit on the existing unborn branch `claude/reload-skills-vlw05p`, then `git push -u origin claude/reload-skills-vlw05p` (retry on network failure: 2s, 4s, 8s, 16s). No PR unless asked.
