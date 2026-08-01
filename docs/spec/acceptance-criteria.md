# Acceptance Criteria

**v1.0** — companion to [`claim-verification-engine.v0.2.md`](claim-verification-engine.v0.2.md).

---

## Why this document exists

Spec §7 states six anti-laundering constraints as prose principles. A principle that cannot fail a build is decoration. This document converts each into a numbered criterion with a stated pass/fail test, and adds criteria for the §3 non-negotiable rule and the §9 resolutions.

Every criterion below is **binary**. There is no "partially satisfied." A system that fails any one of these is not a constrained implementation of the spec — it is an unconstrained system that resembles one, which is the specific failure mode §7 exists to prevent.

These criteria are versioned with the spec and are **not operator-configurable**. AC-3 tests that claim about itself.

### Coverage map

| Source | Criteria |
|---|---|
| §3 non-negotiable rule | AC-7 |
| §7.1 ledger inseparability | AC-1 |
| §7.2 no platform formatting | AC-2 |
| §7.3 non-configurability | AC-3 |
| §7.4 routing rationale exposed | AC-4 |
| §7.5 Insufficient Data first-class | AC-5 |
| §7.6 claimant blindness | AC-6 |
| §8 persistence model | AC-8, AC-9 |
| §9.1 sign-off gate | AC-10 |
| §9.2 tolerance bands | AC-3 (non-configurability), AC-13 |
| §9.3 robustness sweep | AC-11 |
| §9.4 pack routing | AC-14 |
| §9.5 series breaks | AC-12 |
| §9.6 reconstruction trajectory and causal exclusion | AC-15 |

---

## AC-1 — Ledger inseparability

**Constraint:** §7.1. The reconstructed claim never renders, exports, or copies without its discard ledger.

**Test.** Enumerate every code path that emits reconstructed claim text — UI render, API response, export format, clipboard payload, print view, log line, error message, notification body. For each, assert the discard ledger is present in the same payload.

**Fails if:** any path emits reconstructed text without the ledger, or emits it with the ledger behind a collapsed-by-default control, a separate request, a pagination boundary, or a second file in an archive.

**Note.** "Present in the same payload" is the operative phrase. A ledger fetched by a second call is detachable by anyone who makes only the first call.

---

## AC-2 — No platform formatting

**Constraint:** §7.2. Output is never optimised for distribution.

**Test.** Assert that no output path applies a character-count target, a platform-specific template, an image card renderer, or a share affordance. Assert no output is truncated to fit a length budget.

**Fails if:** any share, post, or copy-formatted-for affordance exists; if any output path takes a max-length parameter that truncates rather than paginates; or if a template named for a platform exists in the codebase.

---

## AC-3 — Non-configurability

**Constraint:** §7.3. Tolerance thresholds and routing tables are inspectable and versioned, not operator-configurable.

**Test.** Assert the tolerance bands (§9.2) and all routing rules load exclusively from versioned pack files or the versioned spec constants. Then attempt mutation through every configuration surface — runtime API, admin endpoint, settings file, environment variable, feature flag, database write, CLI argument. Assert every attempt fails.

Assert that a legitimate change requires a pack version bump, and that the bump is recorded in `routing_log.pack_version`.

**Fails if:** any surface mutates a threshold or a routing rule without a version bump; if a pack loads without a version; or if two verifications run against different rule sets without a recorded version difference.

---

## AC-4 — Routing rationale exposed

**Constraint:** §7.4. Why this custodian and not another, in the output.

**Test.** For every element in every output, assert `custodian`, `rationale`, and `alternatives_considered` are present and non-empty. `alternatives_considered` may be empty only where the pack declares no alternative custodian exists for that measure — assert that emptiness always corresponds to such a declaration.

**Fails if:** any element renders without its routing rationale, or `alternatives_considered` is empty without a corresponding pack declaration.

**Note.** A routing table showing only winners is indistinguishable from one built backwards from preferred answers. The alternatives are the audit.

---

## AC-5 — Insufficient Data is first-class

**Constraint:** §7.5. Never styled as failure.

**Test.** Render an Insufficient Data outcome and any other verdict. Assert identical prominence: same typographic hierarchy, same container, same position in the layout. Assert the outcome carries no error styling, no warning iconography, no non-2xx HTTP status, no error-level log line, and no retry affordance implying the result is provisional.

**Fails if:** Insufficient Data is visually de-emphasised relative to any other verdict, is returned with an error status, or is presented as something to be resolved rather than an answer.

---

## AC-6 — Claimant blindness

**Constraint:** §7.6. No claimant metadata reaches the verification path.

**Test.** Take a fixed claim text. Run it N times, varying only `source_attribution` — different named individuals, different affiliations, no attribution at all. Assert that the routing decisions, retrievals, element statuses, flip table, and proposed claim-level verdict are **byte-identical** across all N runs, after normalising timestamps and record ids.

Additionally, assert by static analysis that `claims.source_attribution` is not reachable from any Stage 1–9 input.

**Fails if:** any of those outputs differ across runs, or attribution is reachable from the verification path even if currently unused.

**Note.** This is the sharpest criterion in the set. It converts "we are non-partisan" — an unfalsifiable claim about intent — into a differential test that either passes or does not. Reachability is tested alongside behaviour because an unused pathway is a latent failure, not a passing one.

---

## AC-7 — No unsourced figure

**Constraint:** §3. Every figure originates from a recorded retrieval.

**Test.** For every numeric literal in every output — figures, dates, amounts, rankings, percentages, flip-table cells — assert it resolves to a `retrievals.id`. Assert the retrieval's `reference_period` renders alongside it.

**Fails if:** any figure in any output lacks a retrieval id. This must fail the render, not warn.

**Extended surfaces**, each tested separately because each is a real bypass route:
- Flip-table cells (`sweeps.computed_from_retrieval_id` non-null on every row).
- Human-entered text in `amendment_rationale` (AC-10).
- Custodian pack contents (assert packs contain no numeric literals other than version numbers, dates, and identifiers).

---

## AC-8 — TTL enforcement

**Constraint:** §8. Expired retrievals are re-pulled, never served.

**Test.** Age a retrieval past the TTL derived from its custodian's cadence. Request a verification depending on it. Assert the system re-pulls. Assert that if the re-pull fails, the element degrades to **Unreachable** and the expired figure is not served.

**Fails if:** an expired retrieval is served from cache in any circumstance, including under custodian outage, rate limiting, or degraded mode.

**Note.** "Serve stale under outage" is standard, sane engineering practice everywhere else and is forbidden here. A cached figure reused without re-checking is functionally identical to a figure recalled from memory.

---

## AC-9 — Provisional invalidation

**Constraint:** §8. Provisional retrievals are invalidated when a revision publishes.

**Test.** Record a verdict pinned to a provisional print. Publish a revision. Assert the verdict is invalidated rather than silently carried forward, and that the invalidation is visible on any surface where the verdict was previously shown.

**Fails if:** a verdict pinned to a superseded revision continues to render as current, or is updated in place without a new validity window.

---

## AC-10 — Gate integrity

**Constraint:** §9.1. Sign-off changes the claim-level label and nothing else.

**Test.** Attempt, as a signing-off reviewer, to modify: an element status, a retrieval record, the discard ledger, a flip-table row, a routing decision, and a pack. Assert every attempt fails. Assert the only permitted mutation is the claim-level label, accompanied by a non-empty `amendment_rationale`.

Assert a `proposed` verdict cannot export as final and renders visibly marked as unconfirmed.

Assert that `amendment_rationale` introducing a figure fails AC-7 exactly as pipeline output would.

**Fails if:** a reviewer can reach past the verdict to the evidence beneath it; if a `proposed` verdict exports as final; or if the original proposal is overwritten rather than retained alongside the amendment.

**Note.** An unconstrained human gate is itself a laundering vector, and a more credible one than the pipeline — it arrives wearing the authority of review.

---

## AC-11 — Sweep coverage

**Constraint:** §9.3. An unrunnable sweep never reads as a pass.

**Test.** Construct a claim whose measure has too short a series, or no declared admissible alternatives, so the robustness sweep cannot run. Assert the proposed claim-level verdict is capped at **Indeterminate** and is never *Accurate*.

Assert that where the sweep does run, the flip table renders with the verdict and every cell cites its retrieval.

**Fails if:** an unrunnable sweep produces an *Accurate* verdict, or the flip table is omitted from any surface rendering a Misleading verdict.

**Note.** Without the cap, the weakest-evidence claims would receive the strongest label — the sweep's silence would read as its endorsement.

---

## AC-12 — Break integrity

**Constraint:** §9.5. No verification by splicing.

**Test.** Construct an element comparing figures across a declared series break with no linked series. Assert the element is **Contested by definition** or **Unverified**, never Verified.

Assert that where a linked series exists, it is used and recorded in `retrievals.linked_series_used`.

Assert that a break detected by heuristic — without a `custodian_notice_ref` — flags for review and does not auto-populate the register.

**Fails if:** any element is Verified across an unlinked break; if a heuristic-detected break enters the register without a custodian notice; or if a spliced comparison renders as a published figure.

---

## AC-13 — Tolerance determinism

**Constraint:** §9.2. Tolerance is derived, never chosen.

**Test.** For a fixed claim figure and published figure, assert the assigned band is a pure function of `published_precision`, `unit`, and `discrete` from the pack. Assert no per-claim, per-claimant, or per-session input affects the band.

Assert the binary overrides bypass the numeric bands: a superlative element with a near-miss series, a direction element with the wrong sign, and a discrete-count element off by one all resolve to **Contradicted**, not Verified.

Assert Band B assignments render their `rounded` tag.

**Fails if:** the same figure pair yields different bands across runs; if a superlative, direction, or discrete element is Verified by a numeric tolerance; or if a `rounded` tag is assigned but not rendered.

---

## AC-14 — No generic fallback

**Constraint:** §9.4. Absence of a custodian yields Insufficient Data.

**Test.** Submit a claim in a jurisdiction with no loaded pack. Submit a claim whose measure has no pack entry. Submit a claim whose measure has no routing rule. Assert all three return **Insufficient Data**.

Assert by static analysis that no retrieval path can reach a source that is not a declared custodian in a loaded pack — no web search, no news source, no model prior, no operator-supplied URL.

Assert **Unreachable** and **Unverified** are distinct outcomes and that neither collapses into the other.

**Fails if:** any verification retrieves from a non-custodian source under any circumstance; if a missing pack produces anything other than Insufficient Data; or if Unreachable is reported as Unverified.

**Note.** This is the criterion that keeps generalisation from becoming dilution. Every other guarantee in the spec rests on "custodian of record" meaning something narrower than "source that looks official," and a fallback path — however well-intentioned, however rarely taken — dissolves that distinction at exactly the moments it matters most.

---

## AC-15 — Reconstruction determinism and composition

**Constraint:** §4 Stage 7, §7.1, §9.6. Reconstruction is a pure function of the verified element set, and never composes a claim its elements do not support.

**Test — determinism.** Take a verified element set. Derive a reconstruction. Derive it again from the same set. Assert byte-identical text. Assert two `reconstructions` rows sharing an `element_set_hash` always share their text.

**Test — re-derivation, not editing.** For every revision in a claim's trajectory, re-derive from that revision's recorded element set and assert the result matches the stored text. Assert no code path produces revision *n* by taking revision *n−1* as input; the reconstructor's only input is the current element set.

**Test — regression.** Flip an element from Verified to Contradicted, as a publishing revision would (AC-9). Assert the next reconstruction is *smaller*, is stored as a new revision rather than replacing its predecessor, and is not treated as an error.

**Test — composition.** Assert no reconstruction, at any revision, contains a causal or evaluative connective ("because", "due to", "caused by", "thanks to", "as a result of", and their equivalents in each pack's declared languages) unless that connective originates in a single Verified element that itself carries it. Assert that two verified elements adjacent in time — a policy effective date and a series movement — never compose into a causal statement.

**Test — scope closure.** Assert that elements marked Out of scope at Stage 1 (opinion, prediction, causal) can never reach a Verified status by any path, and are therefore structurally unreachable by the reconstructor.

**Fails if:** the same element set yields different text across derivations; any revision is produced by editing its predecessor; a regressing element produces an error rather than a smaller revision; a reconstruction contains a causal connective not carried by a single verified element; or an out-of-scope element can attain Verified status.

**Note.** The composition test is the one that matters most and the one an implementation is most likely to fail by accident. A reconstructor built to produce fluent prose will reach for connectives to smooth two adjacent verified facts into a sentence, and the resulting causal implication will carry the full authority of the citation trail while resting on nothing. §9.6 works through the worked example in full.
