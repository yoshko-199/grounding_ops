# Roadmap

Living document. Records what is settled, what is next, and what must be true before implementation begins.

Companion to the [specification](spec/claim-verification-engine.v0.2.md) and the [overview](overview.md).

---

## Context

A draft spec (v0.1) described a system that decomposes a public claim into atomic elements, verifies each against a named custodian of record, and rebuilds a grounded version of the claim inseparable from a ledger of what was discarded.

The draft was architecturally sound but ended with five open questions. Three were load-bearing: without a fixed tolerance rule, a concrete misleadingness procedure, and a jurisdiction model, two competent implementers would build materially different systems. Its anti-laundering constraints were also prose principles, which meant nothing could fail a build for violating them.

**This repository is specification work only.** No implementation is planned here until the spec settles.

Prior art: the `israeli-fact-checker` skill (installed at `~/.claude/skills/`, outside this repo) already implements claim isolation, measure disambiguation, custodian routing, the citation trail, and the anti-fabrication rule. It has no reconstruction step, no derived-element mapping, and is deliberately stateless. Its researched source map is the basis for the Israel pack. **This repository does not modify it.**

---

## Phase 1 — Close the spec ✅ Complete

| Delivered | Where |
|---|---|
| v0.2 with all five §9 questions resolved | [`spec/claim-verification-engine.v0.2.md`](spec/claim-verification-engine.v0.2.md) |
| §7 converted to 15 binary pass/fail criteria | [`spec/acceptance-criteria.md`](spec/acceptance-criteria.md) |
| Jurisdiction-pack contract | [`spec/custodian-pack-interface.md`](spec/custodian-pack-interface.md) |
| Israel pack, draft, explicitly not admitted | [`spec/packs/israel.md`](spec/packs/israel.md) |
| Versioned reconstruction + causal exclusion | v0.2 §4, §9.6, AC-15 |
| High-level explainer with diagrams | [`overview.md`](overview.md) |
| v0.1 archived verbatim for diffing | [`spec/claim-verification-engine.v0.1.md`](spec/claim-verification-engine.v0.1.md) |

**Decisions locked** (reopening requires a spec version bump): automated retrieval and element verdicts with a human confirm gate on the claim-level verdict only; tolerance derived from published precision; the robustness sweep as the misleadingness test; generalised routing via versioned packs; break register plus continuity check; reconstruction as a pure function of the element set.

---

## Phase 2 — Close the remaining gaps

Ordered by what blocks the most downstream work. Items 2.1 and 2.2 gate implementation; 2.3 gates any real-world trial.

### 2.1 Derived-element generation — the sharpest gap

**Problem.** §6.3 defines how derived claims are *tagged* but not how they are *generated*. Stage 9 must produce the claim *"the government caused this"* in order to tag it `implied-by-original-only`. That is a generative act inside a system whose entire design prevents generative acts, and it is currently unconstrained.

**Why it matters more than it looks.** The tag `implied-by-original-only` is described in the spec as the most analytically valuable output of the whole system. It is also the output most easily abused: a generator free to invent "implications" can attribute beliefs to a claimant that they never expressed, then present the attribution inside a verified-looking artifact. This is the same laundering shape §9.6 blocks in reconstruction, arriving through a door that is still open.

**Approach to specify:**
- Constrain generation to implications **syntactically present** in the original claim — the causal connective, the superlative, the comparison — rather than inferred from world knowledge.
- Require every derived element to cite the span of original text it derives from. A derived element with no anchoring span is inadmissible.
- Decide whether derived elements need their own confirm gate, given they are model-produced text rather than retrieved fact.
- Add an acceptance criterion mirroring AC-15's composition test.

**Output:** v0.3 §9.7 plus AC-16.

### 2.2 Jurisdiction detection

**Problem.** §9.4 assumes a claim's jurisdiction is known before pack lookup. Claims with implicit jurisdiction — *"inflation is up"* — have none.

**Approach:** resolve from Stage 0 provenance where available (where it was said, to what audience). Where genuinely absent, return **Insufficient Data** rather than guessing. A default jurisdiction is a silent assumption that would systematically mis-route claims from everywhere else.

**Watch for:** provenance includes claimant identity, and §7.6 forbids claimant metadata reaching the verification path. Jurisdiction must be derived from provenance *without* leaking the claimant into routing, or AC-6 fails. This tension needs an explicit resolution, not a footnote — it is the one place where two locked decisions pull against each other.

**Output:** v0.3 §9.8, plus an AC-6 amendment covering the derived-jurisdiction path.

### 2.3 Admit the Israel pack

Seven blockers listed in [`spec/packs/israel.md`](spec/packs/israel.md#6-admission-blockers). Three are substantial research:

- `published_precision`, `unit`, `discrete` per measure — confirmed against each custodian's current publication.
- `admissible_baselines[]` and `admissible_windows[]` per measure, drawn only from windows the custodian itself publishes. **Without these the robustness sweep cannot run and every verdict caps at Indeterminate** (AC-11).
- Series break registers, populated from custodian notices with references. **Without these no cross-time comparison can be Verified** (AC-12). The budget and procurement registers matter most: budget-line restructuring and coverage onset both produce breaks that look like findings, and both would verify cleanly as arithmetic against the published figures.

The remaining four are straightforward: assign a maintainer, give the ministries reached via `data.gov.il` their own custodian entries, complete the routing table, and confirm revision policies for three custodians.

### 2.4 Sweep cost

The robustness sweep multiplies retrievals per claim by the size of the admissible alternative set. Whether that is affordable against rate-limited custodian APIs needs measurement against a real pack, which makes it dependent on 2.3. Not a design answer, and it should not be guessed at now.

### 2.5 Sign-off throughput

§9.1 puts a person on every claim-level verdict. At volume this becomes the binding constraint. Whether a reviewed-sample model preserves the guarantee is unresolved. Flagged explicitly because it is the constraint most likely to be weakened quietly under operational pressure — and weakening it silently would hollow out §9.1 while leaving the documentation intact.

---

## Phase 3 — Implementation readiness

Not started, and deliberately gated. Before any code:

1. Phases 2.1–2.3 complete — at least one admitted pack, or there is nothing to verify against.
2. Every acceptance criterion has a written test, including the ones testing *absence* (AC-2, AC-3, AC-14 need static analysis, not just runtime assertions).
3. AC-6 (claimant blindness) has a harness before the first verification path is written.
4. A decision on human sign-off tooling, since §9.1 makes it part of the critical path rather than an add-on.

**Sequencing note.** AC-6 and AC-15 should be built as tests *before* the code they constrain. Both check structural properties — that data never reaches a place, that output is a pure function of its input — and both are far cheaper to enforce from the start than to establish after the fact.

---

## Verification for spec changes

Any change to this repository should keep these true. All are mechanical:

1. **§9 closure** — every resolved question carries a decision and a rationale; none reads "open" or "needs a strategy."
2. **Constraint coverage** — every §7 constraint maps to at least one acceptance criterion, and every criterion states a pass/fail test rather than a principle.
3. **Schema completeness** — every field introduced in prose appears in the §8 schema sketch.
4. **Pack validity** — `packs/israel.md` walks against every required field in the pack interface; a gap means the interface is under-specified or the pack is incomplete.
5. **No fabricated figures** — the documents contain no statistic, index value, or dated figure of their own. Institution names, mandates, and measure definitions only. Numeric constants belonging to the tolerance rule itself are the sole exception, and worked examples must read unmistakably as hypothetical. *The spec violating its own §3 would be self-refuting.*
6. **Links resolve** — every relative link and anchor across the document set points at something that exists.

Checks 1, 2, 3, 5, and 6 are greppable and should be scripted before Phase 3.
