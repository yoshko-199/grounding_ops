# Sources

Declarations for [`plugins/harvest`](../plugins/harvest/__init__.py) — the
publications and accounts the harvester scans for **candidate claims**.

A source is not a custodian. Nothing declared here can become evidence: the
harvester has no import path to the custodian adapters, the retrieval layer, or
the event store, and `tests/conformance/test_plugin_isolation.py` fails if one
ever appears. Sources answer *what was claimed*; custodians answer *what is on
the record*. Keeping the two apart is the point of the separation.

## Declaring a source

See [`fixture.toml`](fixture.toml) for a fully commented example. Every
declaration states its accounts, an ordered list of backends, a cadence (which
becomes the fetch TTL), and — the field most often got wrong — a
`date_precision`.

Omitting `date_precision` is safe: every record is then capped at
`approximate`, because a well-formed timestamp whose provenance the source does
not state is not an exact date. Declaring `exact` is a claim that the source
establishes the time of the original utterance, and it should be made only
against the source's own statement about its dating.

A source ships `enabled = false` until someone has decided it is appropriate to
collect from. Disabling requires a `disabled_reason`; a source switched off
without a recorded reason gets switched back on by the next person who notices
it is off.

---

## Not admitted: true.org.il

**Status: declared here, not shipped as a source.** Investigated as a candidate
claim corpus for [`docs/plan.md` §2.2](../docs/plan.md#22-derivation-coverage--needs-a-corpus)
and not admitted. The fields a declaration needs were not present in what could
be observed, and they are left unfilled rather than filled from inference —
guessing a feed's shape is the same error as populating a pack from
recollection, one layer out.

### What it is

An aggregation portal over other people's fact-checks. Per its own about page,
it presents problematic statements by politicians and influencers, scanned from
the web, social networks and television, and credits the investigators who
originated each finding — The Whistle (המשרוקית), FakeReporter, Shomrim,
HaBodkim, Meday'kim, The Seventh Eye, and named journalists. It does not
originate checks itself, which places it one level above the prior art
`israeli-fact-checker` already draws on.

### Why it is interesting anyway

Its own taxonomy is the finding, and it is recorded at
[`docs/plan.md` §2.2](../docs/plan.md#22-derivation-coverage--needs-a-corpus).
Four of its five categories are claim types Stage 1 routes out of verdict
scope, which makes a corpus of real political discourse mostly the out-of-scope
kind — external support for §9.10 from a direction the spec did not anticipate.

### Blockers

| # | Blocker |
|---|---|
| 1 | **The site's own notice.** Its about page states that it is an experimental site for academic purposes, not yet launched, and asks that it not be entered until further notice. That is the publisher's stated wish about access to their own material, and it settles the question until it changes. **Confirm the notice has been withdrawn before anything else on this list matters.** |
| 2 | **No confirmed machine-readable surface.** No feed, endpoint, or payload shape has been verified. `items_path`, `text_field`, `url_field`, and `date_field` cannot be declared without that, and inventing them would produce a declaration that looks admitted and silently harvests nothing. |
| 3 | **Dating.** The about page states that where an exact date could not be found, an approximate one is displayed, without marking which records those are. A source that cannot distinguish its exact dates from its approximate ones can only be declared `date_precision = "approximate"`, and every record it yields is then refused a `stated_at` by `CandidateClaim.stated_at`. That is correct behaviour and it makes the corpus unusable for anything indexed on when the claim was made — §9.2 bands and §9.5 continuity both are. |
| 4 | **Text provenance.** Records are presented as statements by named people. Whether the displayed text is the utterance or a summary of it is not stated, and §9.7.1 anchors derived elements to spans of the original — a summary would anchor spans to words the claimant did not say, which §9.7.5 forbids presenting as theirs. |
| 5 | **Language.** Claims are in Hebrew. The lexicon carries no Hebrew derivation triggers, and directional vocabulary still sits in `engine/verification/patterns.py` rather than in a pack — [`docs/plan.md` §2.5](../docs/plan.md#25-language-vocabularies-outside-the-lexicon). Harvesting the corpus before that is closed produces a corpus the engine under-decomposes silently. |
| 6 | **Reachability from this environment.** The domain is blocked by the network egress policy of the environment this repository is developed in. Any harvest would need that changed deliberately, which is the right place for the decision to sit. |

Blockers 3, 4 and 5 are the substantial ones, and none is a defect in the
site — it is built for browsing, and it is good at that. They are the distance
between something built for reading and something usable as a verification
input.
