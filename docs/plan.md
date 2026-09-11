# Roadmap

Living document. Records what is settled, what is built, and what is still missing.

Companion to the [specification](spec/claim-verification-engine.v0.5.md) and the [overview](overview.md).

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

**Three measures are now admitted.** [`packs/live/il.toml`](../packs/live/il.toml) loads, declaring the Bank of Israel and its representative rates for the US dollar, the euro and sterling, with every field taken from the Bank's own current publications. A pack must be complete to load but need not be broad: confirmed measures route claims about themselves and return Insufficient Data for everything else, which is the correct answer for everything else. Twenty half-filled measures would not load at all.

An adapter for the Bank exists and is wired behind the CLI's `--live` flag. It has never run against the live endpoint, because this environment blocks the Bank's hosts, so a live run reports that the custodian could not be reached.

Three things that only became visible by doing it:

- **The hardest blocker was the easiest for this custodian.** Break registers were expected to be the worst of the seven. The Bank publishes a prose history of every change to how the representative rate is determined, with dates — a coverage change in 1986, methodology changes in 1990 and 1995, a sampling-window change in 2006. That *is* a break register; it simply had to be read. Whether other custodians publish the same is unknown and should not be assumed.
- **Two entries in the draft were wrong in the plausible direction.** It recorded the rate as "fixed per date and not revised" with integrity annotation "none known". The Bank's own notes say the rates have no official or legal standing, are not published in the Official Gazette, are indicative rather than transactional, and that it reserves absolute discretion to change them without notice. Neither error was careless; both are what confident recollection produces, which is the whole argument for the rule.
- **A real pack reaches a state no fixture can.** It names a custodian this deployment has no client for. That is recorded at 3.1 and was a live defect until admission surfaced it.
- **Sibling measures reach another.** Declaring three rates from one custodian exposed a scoring flaw in the binder that no single-measure pack could: a claim token appearing in both a measure's name and its definition was counted twice, so a definition echoing its own name outranked a sibling that said the same thing once. The contested set named the wrong pair. Fixed at the root rather than by rewording the pack, so which siblings get reported depends on measure identity rather than on whose prose repeats a word.

Seven blockers listed in [`spec/packs/israel.md`](spec/packs/israel.md#6-admission-blockers). Three are substantial research and **must be done with the custodians' publications open**, not from recollection — a pack populated from memory is the exact failure the spec exists to prevent, and it would be self-refuting to introduce it here:

- `published_precision`, `unit`, `discrete` per measure, confirmed against each custodian's current publication.
- `admissible_baselines[]` and `admissible_windows[]` per measure, drawn only from windows the custodian itself publishes. **Without these the robustness sweep cannot run and every verdict caps at Indeterminate** (AC-11).
- Series break registers, populated from custodian notices with references. **Without these no cross-time comparison can be Verified** (AC-12). The budget and procurement registers matter most: budget-line restructuring and coverage onset both produce breaks that look like findings, and both would verify cleanly as arithmetic against the published figures.

The remaining four are straightforward: assign a maintainer, give the ministries reached via `data.gov.il` their own custodian entries, complete the routing table, and confirm revision policies for three custodians.

**What admission would and would not buy.** The pack's measures are almost entirely economy, government, and property. Surveying an Israeli political-discourse aggregator's own topic index — see 2.2 below — its economy section holds about one claim in twelve of everything it has collected; security, law, and society together hold well over half. So a fully admitted pack binds a measure for roughly the smallest tenth of what actually circulates, and returns Insufficient Data for the rest. That is the correct answer for the rest, and it is worth knowing the ratio before the pack lands rather than reading it off a dashboard afterwards. It is an argument for 2.5 and for §9.10, not an argument against 2.1.

Reading that economy section rather than only its count makes the bound tighter still. Most of what it holds are **broken promises** — commitments about what a government would do, which Stage 1 routes out exactly as it routes out predictions. The checkable factual assertions are concentrated in the *rebuttals* rather than in the claims: the claim is "I will reduce the rate", and the figure lives in the finding that the rate went up. Whether the rebuttal is itself a claim worth routing is a real question and it is not obviously no — but it is a different intake decision from the one the harvester currently implements, and it should be taken deliberately rather than by accident of what a parser happens to pick up.

### 2.2 Derivation coverage — needs a corpus

§9.7.2 fixes six derivation operations **[v0.5]**. Whether they cover the implication patterns that actually occur is empirical, and answerable only against a corpus of real claims.

The first real claim tested against the built engine — *"you don't see a curve, therefore the earth is flat"* — exercised a pattern the original five did not cover, and `inferential-discharge` was added for it. That is one data point, and it points the wrong way for optimism: the list was not chosen carelessly, it was chosen without a corpus, and the very first claim found a hole. The remaining question is no longer *whether* patterns are missing but *which*.

The failure mode is silent and in the safe direction: an implication with no matching operation is never surfaced, so the system under-reports rather than misreports.

**Flank scope, found by a real claim carrying two triggers in sequence.** Comparing the engine against the prior-art skill on *"…fell below 3 and is now the lowest in years due to the government's economic management"* exposed two defects that no fixture claim can produce, because fixture claims carry one trigger. The right flank ran to the end of the claim while the left stopped at the previous trigger, so an early superlative swallowed the later causal clause; and bounding a causal discharge at the previous trigger made it attribute the wrong thing entirely, naming *"in years"* as the effect of a government policy. Causal and inferential connectives now take the claim's own bounds, the other four stop at the triggers either side, and both cases are pinned by tests.

**What was deliberately not fixed.** The superlative on that claim still reads *"…and is now the is asserted to be lowest in years"* — the claimant's own "is now the" abutting the scaffold. It is stiff and slightly ungrammatical, and it is not wrong: every word is theirs and the meaning is recoverable. Trimming for fluency was tried and rejected, because the obvious mechanism is the stopword list and that list contains `rate`, `index`, and `national` — trimming a trailing stopword would delete the *measure* from "the exchange **rate**". §9.7 already defends stiffness as the visible cost of not supplying words the claim does not contain; deleting the claimant's words to smooth a sentence is the same error facing the other way.

**A harvester now exists.** [`plugins/harvest`](../plugins/harvest/__init__.py) scans declared sources and accounts and writes candidate claims to a corpus file, driven by [`scripts/harvest_corpus.py`](../scripts/harvest_corpus.py). It is a plugin in the strict sense: nothing under `engine/` can reach it, and `tests/conformance/test_plugin_isolation.py` fails if that changes. It produces claims, never evidence — a harvested record has no field that could hold a figure, and no import path to the store or to a custodian adapter.

No source is admitted yet. [`sources/README.md`](../sources/README.md) records what a declaration must establish and why the first candidate surveyed does not yet meet it.

**What surveying that candidate established, before any claim was harvested.** Its own category scheme is the finding. It sorts collected statements into refuted claims, double standards, broken promises, incitement, and misleading forecasts — and four of those five are claim types Stage 1 routes out of verdict scope. Only the first is the factual lane.

That is external support for §9.10 arriving from a direction the spec did not anticipate. §9.10 was argued from a single constructed test claim; this says a real corpus of political discourse is *mostly* the out-of-scope kind, which means the pre-v0.5 behaviour — route out at Stage 1, emit nothing — would have left the engine silent on the majority of what it was handed. The change mattered considerably more than the claim that prompted it suggested.

It also sharpens what a corpus is for. A corpus assembled from such a source measures derivation coverage well, because derived elements are exactly what those four categories reduce to. It measures routing and retrieval coverage badly, because most of its claims bind no measure at all. Both numbers are worth having; reporting the first as though it were the second would overstate the engine's reach.

**Two properties the survey forced into the harvester**, both worth keeping regardless of which source is admitted first:

- **Approximate dates are refused, not rounded.** A source that displays an estimated date where it could not establish the real one — a common and openly stated practice — cannot supply a `stated_at`, because §9.2 bands and §9.5 continuity are both indexed on when the claim was made. An approximate date there does not degrade the answer; it produces a confident answer to a different question. `CandidateClaim.stated_at()` raises rather than guessing, and a source that says nothing about its dating has every record capped at approximate.
- **Text transforms are recorded.** §9.7.1 anchors derived elements to spans of the original, so text silently rewritten in transit — tags stripped, entities decoded — yields spans that resolve to the wrong words much later. Every edit between the received body and the stored text is named on the record, and the raw body is kept.

### 2.2a Divergence from the prior art, deliberately retained

The `israeli-fact-checker` skill's method (`SKILL.md` Step 1, `references/domain-checklist.md`) and this spec agree on almost everything — its eight-step workflow maps stage for stage onto the pipeline, and its verdict scale corresponds one-to-one with §6.2. Two differences are real and are kept:

- **Causal claims.** The skill rates them **לשיפוטכם** (Indeterminate) and presents the data. §9.6 refuses *any* label on a causal element and routes it to a derived element instead, arguing that a causal verdict is argument wearing a verification badge regardless of how it is hedged. Ours is stricter, and the argument for it is in §9.6 rather than in a preference.
- **Presenting baseline data beside an out-of-scope claim.** The skill does; §9.10 does not. A human analyst can judge whether a given series is relevant to a claim it does not address. A pipeline cannot, and a custodian's figure displayed next to a proposition it does not address is §9.6's shape reached by a different route.

Where the two agree and the engine was wrong, the engine changed: §9.10 exists because the skill is right that an out-of-scope claim should not produce silence.

### 2.2b Only the first known confusion ever renders

`retrieve._measure_caveat` takes `known_confusions[0]` and drops the rest, so a measure declaring four confusions surfaces one on its citations and hides three. The dollar rate declares four; readers see the first.

Interface §3.3 records confusions because the measure is "routinely mistaken" for its neighbours and the mistake changes the answer while leaving the headline number recognisable. Surfacing one of four is a partial defence, and which one is decided by pack ordering rather than by relevance to the claim in hand.

Left as it is deliberately. It is pre-existing, affects every pack including the fixture, and joining all of them would lengthen every citation line in every artifact — a change worth making on its own evidence rather than as a side-effect of a review that happened to notice it. Two directions are open and they are not the same: render all of them, or select the one relevant to the bound element. The second is better and needs a rule for relevance that does not yet exist.

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
4. **Sign-off tooling exists and now closes the loop.** `cli/signoff.py`
   remains narrowed to the claim-level label at the API boundary, and can now
   list what is awaiting review and sign off a specific claim by the id
   `cli/verify.py` printed — `engine.store.signoff_writer` persists the
   decision as a new, append-only `verdicts` row rather than editing the
   proposed one, and `engine.signoff` itself gained no import path to the
   store in the process (a dedicated test asserts that, the same way AC-6's
   own test asserts it of identity).

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

- **Retrievals persist, and now so does everything else `verify()` produces.**
  `--store` defaults to a durable database under the repository root, so a
  retrieval outlives its process and the TTL is honoured across runs —
  previously the CLI built an in-memory store per invocation, which made §8's
  whole event model unobservable. Note the limit: the TTL de-duplicates
  recorded events, not custodian fetches, because `pull()` asks the adapter
  for the series before consulting the store.

  `engine/store/writer.py` and `engine/store/identity_writer.py` write the
  remaining tables in `engine/store/schema.sql`: claims, `claim_context`,
  elements, discards, derived elements, verdicts, reconstructions, sweeps,
  routing_log, and the pack/custodian/measure reference rows. Both live
  outside `engine.verification` on purpose — persisting an artifact is
  composition-root bookkeeping, not a verification rule — and
  `identity_writer` is a second module rather than one function among the
  first, because it is the one that imports `engine.ingest.identity`;
  `tests/conformance/test_store_writer_isolation.py` asserts neither is
  reachable from verification, the same way AC-6 already asserts that of
  identity itself. `cli/show.py` is the read side: it looks a claim up by the
  id `cli/verify.py` now prints, and re-renders it from stored rows with no
  retrieval and no re-routing — see
  [how to read back a stored verification](how-to/read-back-a-stored-verification.md).

  What is still missing: `reconstructions` and `verdicts` are append-only
  tables in the schema, but nothing yet re-verifies an *existing* claim by id
  to add a second revision — every `verify()` call today starts from claim
  text and produces revision 1. That absence now reaches sign-off too:
  `cli/signoff.py` reads and closes the single open `verdicts` row for a
  claim, which is correct today because nothing yet produces a second one,
  but it means "confirm this claim, then a retrieval expires and the figure
  changes, then a reviewer sees the new proposal" is not a path that exists
  yet either — the pipeline has no notion of re-verifying a claim it has
  already seen. Citations are persisted as an ordered list per claim (a new
  `citations` table, not in the v0.5 spec's schema sketch, needed because a
  retrieval can be reused across many claims inside its TTL and so cannot
  carry a single owning claim as a column on itself) rather than linked to
  the specific element each one verified — the pipeline binds one measure per
  claim today, not per element, so that finer link has nothing to attach to
  yet.
- **One real measure is admitted**, and no more. Every claim outside it returns
  Insufficient Data. This is 2.1.
- **One real adapter exists**, for the Bank of Israel, wired only by the
  composition root behind `--live`. AC-14 still holds: the verification path
  reaches no network primitive by any static route, because nothing on it
  imports the adapter. It has **never been run against the live endpoint** —
  this environment blocks the Bank's hosts — so its tests prove the parsing
  and the error taxonomy, not the URL. Every other custodian is still a
  fixture or has no client at all.
- **A pack can name a custodian this deployment has no client for**, which no
  fixture jurisdiction can produce, because fixtures ship their own adapters.
  Until admission surfaced it, that case reported as *Unverified* — asserting
  the custodian publishes nothing covering the element, which nobody had
  checked. It is now *Unreachable*, a fact about what can be reached rather
  than about the record, which is the distinction §6.1 and AC-14 exist to
  keep. The engine therefore routes real claims to the Bank of Israel and
  verifies none of them, and says so in those words.
- **Two gaps found while building** are recorded at 2.4 and 2.5: packs declare
  no jurisdiction *names*, and directional vocabulary still sits in the pipeline
  rather than in a lexicon. Both under-fire silently, which is why they are
  written down rather than left to be rediscovered.
- **No source is admitted.** `plugins/harvest` runs, and the only declaration
  shipped is a fixture pointed at a reserved domain and disabled. The harvester
  is therefore exercised end to end and has collected nothing, which is the
  same posture as the pack: the machinery is finished, and admitting real
  input is a decision with its own checklist.

## Verification for spec changes

Any change to this repository should keep these true. All are mechanical:

1. **§9 closure** — every resolved question carries a decision and a rationale; none reads "open" or "needs a strategy."
2. **Constraint coverage** — every §7 constraint maps to at least one acceptance criterion, and every criterion states a pass/fail test rather than a principle.
3. **Schema completeness** — every field introduced in prose appears in the §8 schema sketch.
4. **Pack validity** — `packs/israel.md` walks against every required field in the pack interface; a gap means the interface is under-specified or the pack is incomplete.
5. **No fabricated figures** — the documents contain no statistic, index value, or dated figure of their own. Institution names, mandates, and measure definitions only. Numeric constants belonging to the tolerance rule itself are the sole exception, and worked examples must read unmistakably as hypothetical. *The spec violating its own §3 would be self-refuting.*
6. **Links resolve** — every relative link and anchor across the document set points at something that exists.

All six are implemented in [`scripts/check_spec.py`](../scripts/check_spec.py). Run it before every commit that touches the spec.
