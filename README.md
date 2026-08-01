# grounding_ops

Specification work for a **Claim Verification & Reconstruction Engine** — a system that decomposes a public claim into atomic checkable elements, verifies each against an authoritative custodian of record, and reconstructs a grounded version of the claim containing only what survived verification, displayed inseparably from a ledger of what was removed and why.

The framing is not "is this true?" but *"what part of this survives contact with the record, and what does the surviving part actually support?"*

**Status: specification only.** No implementation exists in this repository, and none is planned here until the spec settles.

---

## Contents

| Document | What it is |
|---|---|
| [`docs/overview.md`](docs/overview.md) | **Start here.** High-level explanation with diagrams — what the system does, and why it cannot quietly become an advocacy tool |
| [`docs/spec/claim-verification-engine.v0.2.md`](docs/spec/claim-verification-engine.v0.2.md) | **Current spec.** Pipeline, taxonomies, persistence model, and the resolved design decisions |
| [`docs/spec/acceptance-criteria.md`](docs/spec/acceptance-criteria.md) | The anti-laundering constraints as fifteen numbered, binary pass/fail criteria |
| [`docs/spec/custodian-pack-interface.md`](docs/spec/custodian-pack-interface.md) | Normative contract for jurisdiction packs — how routing generalises without diluting |
| [`docs/spec/packs/israel.md`](docs/spec/packs/israel.md) | First pack instance, draft. Not yet admitted |
| [`docs/spec/claim-verification-engine.v0.1.md`](docs/spec/claim-verification-engine.v0.1.md) | The original draft, archived verbatim for diffing |
| [`docs/plan.md`](docs/plan.md) | Roadmap — what is settled, what is next, what gates implementation |

---

## What v0.2 settled

v0.1 was structurally complete but ended with five open questions, three of them load-bearing — without them, two competent implementers would build materially different systems. v0.2 closes all five:

- **Human sign-off** — automated retrieval and element verdicts; a human confirmation gate on the claim-level verdict *only*, which may change the label and nothing beneath it.
- **Tolerance bands** — a fixed rule derived from each custodian's published precision, with binary overrides for superlatives, directions, and discrete counts.
- **Stage 8 misleadingness** — the *robustness sweep*: four mechanical tests over already-retrieved series, emitting a flip table. Narrower than "detects false impressions," and narrow on purpose.
- **Geographic scope** — generalised from the start. Jurisdictions are versioned data packs, not code.
- **Series changes** — a break register plus a mandatory continuity check. No verification by splicing.
- **Reconstruction is versioned** — re-derived as a pure function of the verified element set every time an element changes, producing a trajectory that shows support accumulating *or eroding*. Never an edit of the previous text, which is what lets a reconstruction shrink correctly when a provisional figure revises.

It also converts §7's six prose principles into criteria that can fail a build. A principle that cannot fail a build is decoration.

## The two rules everything else rests on

**No unsourced figure.** Every figure, date, amount, or ranking in any output originates from a recorded retrieval against a named custodian. No estimation, no model priors, no "approximately." A fabricated verification is worse than no verification, because it launders a guess into an authoritative-looking artifact.

**No generic fallback.** Where no custodian covers a claim, the answer is *Insufficient Data* — never a web search, a news source, or a plausible-looking substitute. Generalising across jurisdictions must not become diluting what "custodian of record" means.

## Prior art

The `israeli-fact-checker` skill (installed at `~/.claude/skills/`, outside this repository) is the direct ancestor: it already implements claim isolation, measure disambiguation, custodian routing, the citation trail, and the anti-fabrication rule. It has no reconstruction step, no derived-element mapping, and is deliberately stateless. Its researched source map is the basis for the Israel pack. **This repository does not modify it.**

## Open questions

Four remain genuinely open and are listed in [v0.2 §10](docs/spec/claim-verification-engine.v0.2.md#10-remaining-open-questions): sweep cost against rate-limited APIs, jurisdiction detection for claims with implicit jurisdiction, sign-off throughput at volume, and how derived elements are *generated* (§6.3 defines only how they are tagged).
