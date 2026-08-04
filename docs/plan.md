# Roadmap

Living document. Records what is settled, what is built, and what is still missing.

Companion to the [specification](spec/claim-verification-engine.v0.4.md) and the [overview](overview.md).

---

## Context

A draft spec (v0.1) described a system that decomposes a public claim into atomic elements, verifies each against a named custodian of record, and rebuilds a grounded version of the claim inseparable from a ledger of what was discarded.

The draft was architecturally sound but ended with five open questions. Three were load-bearing: without a fixed tolerance rule, a concrete misleadingness procedure, and a jurisdiction model, two competent implementers would build materially different systems. Its anti-laundering constraints were also prose principles, which meant nothing could fail a build for violating them.

**The spec is closed at v0.4 and the engine is built.** Stages 0–11 run end to end and all eighteen acceptance criteria execute as tests, against a synthetic fixture jurisdiction rather than a real one. The gate in Phase 3 below was never a bar on writing the engine — it exists to stop custodian data being invented from recollection, and that constraint is intact: no real pack is admitted, and the fixture carries no figures of its own.

Prior art: the `israeli-fact-checker` skill (installed at `~/.claude/skills/`, outside this repo) already implements claim isolation, measure disambiguation, custodian routing, the citation trail, and the anti-fabrication rule. It has no reconstruction step, no derived-element mapping, and is deliberately stateless. Its researched source map is the basis for the Israel pack. **This repository does not modify it.**

---

## Phase 1 — Close the spec ✅ Complete

| Delivered | Where |
|---|---|
| v0.2 with all five §9 questions resolved | [`spec/claim-verification-engine.v0.2.md`](spec/claim-verification-engine.v0.2.md) |
| v0.3 closing derived-element generation and jurisdiction detection | [`spec/claim-verification-engine.v0.3.md`](spec/claim-verification-engine.v0.3.md) |
| v0.4 closing the four gaps implementation surfaced | [`spec/claim-verification-engine.v0.4.md`](spec/claim-verification-engine.v0.4.md) |
| §7 converted to 17 binary pass/fail criteria | [`spec/acceptance-criteria.md`](spec/acceptance-criteria.md) |
| Jurisdiction-pack contract | [`spec/custodian-pack-interface.md`](spec/custodian-pack-interface.md) |
| Israel pack, draft, explicitly not admitted | [`spec/packs/israel.md`](spec/packs/israel.md) |
| Versioned reconstruction + causal exclusion | v0.2 §4, §9.6, AC-15 |
| Derived-element generation constrained | v0.3 §9.7, AC-16 |
| Jurisdiction projection resolved | v0.3 §9.8, AC-17, extended AC-6 |
| High-level explainer with diagrams | [`overview.md`](overview.md) |
| Mechanical consistency checks | [`../scripts/check_spec.py`](../scripts/check_spec.py) |
| v0.1 archived verbatim for diffing | [`spec/claim-verification-engine.v0.1.md`](spec/claim-verification-engine.v0.1.md) |

**Decisions locked** (reopening requires a spec version bump): automated retrieval and element verdicts with a human confirm gate on the claim-level verdict only; tolerance derived from published precision; the robustness sweep as the misleadingness test; generalised routing via versioned packs; break register plus continuity check; reconstruction as a pure function of the element set; derived elements extracted rather than invented; jurisdiction resolved from a code-only projection of provenance.

---

## Phase 2 — Close the remaining gaps

Everything that can be settled on paper is settled. What remains needs either sources open or a corpus to measure against.

### 2.1 Admit the Israel pack — the only thing blocking a trial

Seven blockers listed in [`spec/packs/israel.md`](spec/packs/israel.md#6-admission-blockers). Three are substantial research and **must be done with the custodians' publications open**, not from recollection — a pack populated from memory is the exact failure the spec exists to prevent, and it would be self-refuting to introduce it here:

- `published_precision`, `unit`, `discrete` per measure, confirmed against each custodian's current publication.
- `admissible_baselines[]` and `admissible_windows[]` per measure, drawn only from windows the custodian itself publishes. **Without these the robustness sweep cannot run and every verdict caps at Indeterminate** (AC-11).
- Series break registers, populated from custodian notices with references. **Without these no cross-time comparison can be Verified** (AC-12). The budget and procurement registers matter most: budget-line restructuring and coverage onset both produce breaks that look like findings, and both would verify cleanly as arithmetic against the published figures.

The remaining four are straightforward: assign a maintainer, give the ministries reached via `data.gov.il` their own custodian entries, complete the routing table, and confirm revision policies for three custodians.

### 2.2 Derivation coverage — needs a corpus

§9.7.2 fixes five derivation operations. Whether they cover the implication patterns that actually occur is empirical, and answerable only against a corpus of real claims.

The failure mode is silent and in the safe direction: an implication with no matching operation is never surfaced, so the system under-reports rather than misreports. That is the right way to fail, but the size of the gap should be measured rather than assumed small — the whole value of `implied-by-original-only` depends on it catching the implications that matter.

### 2.3 Anchoring across paraphrase

§9.7.1 anchors every derived element to a span of the original. Claims that arrive paraphrased — reported speech, translation, a transcribed screenshot — have spans that do not correspond to what the claimant actually said.

Whether anchoring attaches to the received text or the original utterance is unresolved, and it is not a technicality: §9.7.5 forbids presenting a derived implication as something the claimant asserted, and under paraphrase the two can diverge enough to change who is responsible for the implication. Needs a decision before Stage 9 ships.

### 2.4 Pack-declared jurisdiction names

Surfaced by implementation, not by review. §9.8.2's first resolution rule binds a claim that names its own jurisdiction — *"inflation in Israel"* — and it is the preferred rule precisely because it needs no provenance at all. But a pack declares a `jurisdiction_id` and no names, so the pipeline has nothing to match *"Israel"* against without embedding country knowledge, which §9.4 forbids outright.

The implementation matches the jurisdiction **code** as a standalone token, which works for a fixture and almost never for a real claim. Rule 1 therefore rarely fires, and claims fall through to the `jurisdiction_hint`. The failure is conservative — an unresolved jurisdiction is Insufficient Data, never a guess — but it silently disables the one rule that needs no provenance, which is the opposite of the intended ordering.

Closing it means a `names[]` field on the jurisdiction header, per declared language: the demonyms and short forms a claim may use. Small, and it belongs to the pack rather than the pipeline.

### 2.5 Language vocabularies outside the lexicon

Directional and predictive surface forms — *rose*, *fell*, *will*, *expected to* — currently live in the pipeline (`engine/verification/patterns.py`) rather than in a pack. They are properties of a language rather than of a jurisdiction, which is why they are not obviously pack data, and the fixture declares one language so nothing yet forces the question.

A second language forces it. Interface §3.6 already declares derivation triggers and connectives per language; these belong in the same block. Until they are there, decomposition under-fires on any language but English, and §3.6's own warning applies — the failure is invisible from the output, because an under-decomposed claim looks exactly like a simpler claim.

### 2.6 Sweep cost

The robustness sweep multiplies retrievals per claim by the size of the admissible alternative set. Whether that is affordable against rate-limited custodian APIs needs measurement against a real pack, which makes it dependent on 2.1. Not a design answer, and it should not be guessed at now.

### 2.7 Sign-off throughput

§9.1 puts a person on every claim-level verdict, and §9.7.6 adds derived elements to the same gate. At volume this becomes the binding constraint. Whether a reviewed-sample model preserves the guarantee is unresolved. Flagged explicitly because it is the constraint most likely to be weakened quietly under operational pressure — and weakening it silently would hollow out §9.1 while leaving the documentation intact.

---

## Phase 3 — Implementation ✅ Built, against a fixture jurisdiction

| Delivered | Where |
|---|---|
| Stages 0–11, end to end | [`engine/`](../engine) |
| All 18 acceptance criteria as executable tests | [`tests/conformance/`](../tests/conformance) |
| Custodian pack loader and the §6 validation checklist | [`engine/packs/`](../engine/packs) |
| Synthetic fixture jurisdiction, carrying no figures | [`packs/fixture/zz.toml`](../packs/fixture/zz.toml) |
| Retrieval-event store with TTL and provisional invalidation | [`engine/store/`](../engine/store) |
| CLI: verify, and the §9.1 sign-off gate | [`cli/`](../cli) |
| CI running both suites | [`.github/workflows/checks.yml`](../.github/workflows/checks.yml) |

The four preconditions this phase originally set have been met in substance
rather than skipped:

1. **An admitted pack.** Substituted, deliberately. The engine is exercised
   against a synthetic jurisdiction whose custodians are declared fictional,
   which tests every path without inventing a real institution's data. Admitting
   a real pack (2.1) remains what unblocks verifying real claims.
2. **A written test for every criterion**, including the ones testing *absence*
   — AC-2, AC-3, AC-6 and AC-14 are enforced by static analysis over the AST,
   not only by runtime assertions.
3. **AC-6 has a harness, and it was built before the verification path.** The
   import-graph assertion that `engine.verification` cannot reach
   `engine.ingest.identity` landed in the first code commit.
4. **Sign-off tooling exists** as `cli/signoff.py`, narrowed to the claim-level
   label at the API boundary.

**What the structural properties cost, and where they are enforced.** Each is a
property of a signature or an import graph rather than a rule to remember:

- `reconstruct(elements, lexicon)` has no parameter for a previous revision, so
  an append-based reconstructor is unexpressible (AC-15).
- `VerifiedElement` refuses to construct around anything not Verified, so an
  out-of-scope element cannot reach the reconstructor (AC-15 scope closure).
- `Figure` cannot be built without its retrieval, and the renderer rejects raw
  numerals, so an unsourced figure fails the render rather than warning (AC-7).
- `engine.signoff` has no import path to the store, the packs, or the sweep, so
  a reviewer cannot reach past the verdict to the evidence (AC-10).
- `ClaimContext` has no `str`-typed field, so a venue string cannot become a
  jurisdiction (AC-6, AC-17).

### 3.1 What is not done

- **No real pack is admitted**, so every real claim returns Insufficient Data.
  This is 2.1, and it is the only thing between here and a trial.
- **Custodian adapters are fixtures.** No network client exists, and AC-14
  asserts none can be reached from the verification path. A real pack needs a
  real adapter, written against that same contract.
- **Two gaps found while building** are recorded at 2.4 and 2.5: packs declare
  no jurisdiction *names*, and directional vocabulary still sits in the pipeline
  rather than in a lexicon. Both under-fire silently, which is why they are
  written down rather than left to be rediscovered.

## Verification for spec changes

Any change to this repository should keep these true. All are mechanical:

1. **§9 closure** — every resolved question carries a decision and a rationale; none reads "open" or "needs a strategy."
2. **Constraint coverage** — every §7 constraint maps to at least one acceptance criterion, and every criterion states a pass/fail test rather than a principle.
3. **Schema completeness** — every field introduced in prose appears in the §8 schema sketch.
4. **Pack validity** — `packs/israel.md` walks against every required field in the pack interface; a gap means the interface is under-specified or the pack is incomplete.
5. **No fabricated figures** — the documents contain no statistic, index value, or dated figure of their own. Institution names, mandates, and measure definitions only. Numeric constants belonging to the tolerance rule itself are the sole exception, and worked examples must read unmistakably as hypothetical. *The spec violating its own §3 would be self-refuting.*
6. **Links resolve** — every relative link and anchor across the document set points at something that exists.

All six are implemented in [`scripts/check_spec.py`](../scripts/check_spec.py). Run it before every commit that touches the spec.
