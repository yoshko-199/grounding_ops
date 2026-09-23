# Glossary

The terms this repository uses with a precise meaning. Where a term has a
closed set of values, every value is listed, in the form the code and the
output use. The authority for each is the
[specification](../spec/claim-verification-engine.v0.5.md); section
references point into it.

## A–C

**Acceptance criterion (AC-1 … AC-18).** One of the eighteen binary pass/fail
constraints in [acceptance criteria](../spec/acceptance-criteria.md), each
executed by `tests/conformance/test_acNN.py`. "A criterion fails" means that
file fails.

**Adapter (custodian adapter).** The code that fetches a series from one
custodian. It is the only boundary allowed to originate a figure. There is no
adapter that accepts a URL. See `engine/custodians/base.py`.

**Artifact.** Everything one verification emits, as one indivisible payload:
the original claim, the reconstruction with its discard ledger, the verdict,
the robustness sweep, the citations, the routing, and any derived elements. It
leaves only through `render()`, `render_html()` or `to_dict()`, and each
carries the ledger.

**Binding (measure binding).** Stage 3: tying an element to one specific
measure definition *before* any source is chosen, since two institutions can
both be right about different measures (§4, "Stage 3 is not optional").

**Capped verdict.** A claim-level verdict limited by rule regardless of the
elements. Where the robustness sweep cannot run, the verdict is capped at
*Indeterminate*, never *Accurate* (§9.3).

**Citation record.** What every retrieval records and every output shows:
the figure as published, custodian, series identifier, reference period,
retrieved-at time, revision status, and continuity status, plus a framing
caveat where the measure has a known trap (§5).

**Claim context / claimant identity.** The two halves of provenance after the
ingest split (§9.8.1). The *context* (a jurisdiction code, a language code,
the date the claim was made) crosses into verification. The *identity* (who
said it, where, to whom) is recorded and displayed and never reaches
verification. AC-6 asserts that statically.

**Claim-level verdict.** The label on the reconstructed claim as a whole
(§6.2). The values are `accurate`, `substantially_inaccurate`, `misleading`,
`false`, `indeterminate` and `insufficient_data`. It is always emitted as
*proposed*.

**Composition root.** `cli/`: where a durable store is opened, adapters are
wired, and a network primitive may exist, so that `engine/` stays unable to
reach one.

**Continuity status.** Whether a retrieved span crosses a series break (§9.5).
The values are `not_applicable` (the element does not compare across time),
`no_break_crossed`, `linked_series_used`, and `unlinked_break` (never
verified; the two sides are never spliced).

**Custodian (custodian of record).** The institution that publishes the
authoritative figure for a measure in a jurisdiction, such as a national
statistics office or a central bank. Declared in a pack. The fixture
jurisdiction's custodian is `zzstat`, and the Israel pack's is the Bank of
Israel (`boi`).

## D–I

**Derivation operation.** One of the closed list of ways a derived element
may be produced from an anchored trigger (§9.7.2): `causal-discharge`,
`inferential-discharge`, `superlative-discharge`, `comparative-discharge`,
`evaluative-discharge` and `scope-discharge`. The list is not configurable.

**Derived element.** A claim the original *invites* without stating, such as
"that the rise was caused by incompetence", extracted from a span of the
claim, never invented, and never verified (§9.7). Rendered as implication,
never as quotation.

**Derived-element tag.** A derived element's position relative to the two
versions of the claim (§6.3): `implied-by-original-only` (depends on
elements that did not survive), `implied-by-reconstructed`,
`contradicted-by-reconstructed`, or `independent`.

**Discard ledger.** The list of every element removed from the claim, with
its status and the reason. It is never shown apart from the reconstruction
(§7.1, AC-1).

**Element.** An atomic checkable piece of a claim, always anchored to a span
of the claim's own text (§9.7.1, AC-18). Kinds: `quantity`, `time_period`,
`superlative`, `direction`, `discrete_count` and `administrative`, plus the
out-of-scope kinds `opinion`, `prediction` and `causal`.

**Element status.** One per element, assigned automatically and final (§6.1):
`verified`, `contradicted`, `unverified` (the custodian was reached and
nothing covers the element), `unreachable` (the custodian could not be
reached), `contested_by_definition`, and `out_of_scope`.

**Element-set hash.** A hash of the verified element set a reconstruction was
derived from. Two reconstructions with the same hash must have identical text
(§8, AC-15).

**Fixture jurisdiction (`ZZ`).** A synthetic jurisdiction in
`packs/fixture/zz.toml`, built to exercise the hard paths. It carries no
figures of its own: values come from the fixture adapter through recorded
retrievals.

**Gate (sign-off gate).** Stage 11 (§9.1). A person confirms, amends or
rejects the proposed claim-level verdict, and can reach nothing beneath it
(AC-10). States: `proposed`, `confirmed`, `amended`, `rejected` and `expired`.

**Insufficient Data.** The claim-level verdict for a claim no custodian
settles. It is an answer, shown exactly like every other verdict, with exit
code `0` (§7.5, AC-5).

## J–R

**Jurisdiction resolution.** Stage 4's first step (§9.8.2). The rule that
fired is recorded: `explicit_in_text` (the claim names a pack's code or a
declared name), `context_hint`, `supranational_measure`, or `unresolved`.
There is no default jurisdiction.

**Known confusion.** A measure's declared neighbour that is routinely
mistaken for it, such as nominal against real. Declared in the pack, and
surfaced as the citation's framing caveat.

**Lexicon.** A pack's per-language vocabulary: jurisdiction names, and the
surface vocabulary for rises, falls and predictions that decomposition uses.

**Measure.** A precisely defined statistic, such as a named price index or a
representative exchange rate, with its definition, unit, precision and known
confusions. "Measure identity is the actual unit of correctness" (§4).

**Operator error.** A problem with what the operator supplied: a malformed
date, a value that is not a code, missing packs, an unopenable store. It
exits `2` on the command line and is a form problem in the web UI. It is never
a verdict, and never to be confused with Insufficient Data.

**Pack (custodian pack).** Versioned TOML data declaring, for one
jurisdiction, its custodians, measures, series breaks, tolerance inputs,
admissible baselines and windows, routing rules and lexicons. Generalising to
a new jurisdiction is a pack, never an engine change. See the
[pack schema](pack-schema.md).

**Proposed.** The state every claim-level verdict leaves the pipeline in, and
keeps until a person signs it off. A proposed artifact is marked
*UNCONFIRMED*.

**Provisional (revision status).** A first print a custodian may revise.
Revision statuses are `provisional`, `revised` and `final`. A published
revision invalidates the provisional retrieval without deleting it (AC-9).

**Reconstruction.** The claim rebuilt from verified elements only, a pure
function of the current verified element set. It is never edited, only
re-derived, and it can shrink (§4, "Stage 7"). When the survivors don't
compose, the output is "does not reconstruct".

**Retrieval (retrieval event).** One recorded observation from a custodian,
stored as an event with a TTL rather than as a timeless fact. Expired
retrievals are re-pulled, never served (§8, AC-8).

**Robustness sweep / flip table.** Stage 8's test for misleadingness (§9.3):
the claim's conclusion is recomputed under every admissible alternative
baseline and window the pack declares, and each row records whether it
*holds* or *flips*. A claim whose elements verify but whose conclusion flips
is *Misleading*.

**Routing.** Stage 4: jurisdiction → pack → measure → custodian, logged with
its rationale and the alternatives considered (§7.4, AC-4).

## S–Z

**Scope gate.** Stage 1: quantitative and administrative content proceeds.
Opinion, prediction and causal fragments are marked out of scope before any
custodian is asked, and can never become verified.

**Series break.** A point where a custodian changed a series' definition or
base. It is declared in the pack's break register, and any comparison across
it runs the continuity check.

**Source (harvest source).** A publication or account the harvester scans for
candidate *claims*. It is not a custodian and can never be evidence. See
[source admission](../../sources/README.md).

**Tolerance band.** How far a claimed figure may sit from the published one
and still verify, computed from the custodian's own published precision and
never chosen per claim (§9.2). Band A verifies, Band B verifies tagged
`rounded`, and Band C contradicts. Superlatives, directions and discrete
counts bypass the bands: they are right or wrong.

**TTL.** How long a retrieval stays fresh, derived from the custodian's
publication cadence. There is no grace period and no force flag.

**Unreachable vs Unverified.** Unreachable is a fact about today's network:
the custodian could not be reached. Unverified is a fact about the record:
the custodian was reached and publishes nothing covering the element. They
never collapse into each other (§6.1, AC-14).
