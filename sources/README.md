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

A harvest was attempted. It did not run, and each of the first three blockers
below would have stopped it independently. Items marked **confirmed** were
checked against the site rather than inferred.

| # | Blocker |
|---|---|
| 1 | **The site's own notice.** Its about page states that it is an experimental site for academic purposes, not yet launched, and asks that it not be entered until further notice. That is the publisher's stated wish about access to their own material, and it settles the question until it changes. |
| 2 | **The machine-readable surface is disallowed — confirmed.** `robots.txt` reads `Allow: /` with a single `Disallow: /bff/`. That backend-for-frontend path is exactly where a JSON API would live, so the site permits crawling its pages and specifically excludes its data endpoint. The pages are server-rendered and do carry the claims, but this harvester has no HTML-scraping backend and deliberately will not gain one: its backend kinds are a closed set, and screen-scraping rendered markup is how text arrives silently reshaped. |
| 3 | **Egress — confirmed, and not specific to this site.** The environment this repository is developed in enforces a strict allowlist; unrelated public domains are refused identically. Routing around it is explicitly out of bounds, so a harvest needs the policy changed, which is the right place for that decision to sit. |
| 4 | **Dating is worse than imprecise — confirmed.** Each record pairs *two* dates: the date of the claim and the date of the check that refuted it. On a page sampled, claims dated 2006, 2009 and 2015 sit beside check dates from the last fortnight. A parser taking "the date near the text" attaches the check date to the claim, producing a record that is confidently wrong about when the claim was made rather than merely vague. Combined with the about page's admission that approximate dates are displayed unmarked, this source can only ever be `date_precision = "approximate"` — and `CandidateClaim.stated_at()` will then refuse every record, which is correct and makes the corpus unusable for anything indexed on when the claim was made. |
| 5 | **Rendered items are duplicated — confirmed.** Every claim appeared twice in the extracted page, consistent with a carousel rendering each slide twice. Deduplication by `identity_key` handles this only where a per-item URL is present; a text-keyed fallback would merge genuinely distinct records that happen to share wording. |
| 6 | **Text provenance.** Records are presented as statements by named people, and some are clearly summarised rather than quoted — several begin "promised that…" rather than reproducing words. §9.7.1 anchors derived elements to spans of the original, so a summary anchors spans to words the claimant did not say, which §9.7.5 forbids presenting as theirs. Distinguishing the quoted records from the summarised ones is a per-record judgement the harvester cannot make. |
| 7 | **Language.** Claims are in Hebrew. The lexicon carries no Hebrew derivation triggers, and directional vocabulary still sits in `engine/verification/patterns.py` rather than in a pack — [`docs/plan.md` §2.5](../docs/plan.md#25-language-vocabularies-outside-the-lexicon). Harvesting before that is closed produces a corpus the engine under-decomposes silently. |

Blockers 4, 6 and 7 are the substantial ones, and none is a defect in the
site — it is built for browsing, and it is good at that. They are the distance
between something built for reading and something usable as a verification
input.

### What the attempt was worth anyway

Reading real records from the site surfaced a **crash-level defect in the
engine**, now fixed: a claim carrying both a figure and a connective — the
commonest shape in political discourse — failed the render. The figure was the
claimant's own, quoted verbatim into a derived element by §9.7's construction,
but it reached output through the prose channel and AC-7 correctly refused it.
See `Payload.derived` and the regression tests in
`tests/conformance/test_ac07.py`.

The fixture corpus could never have found this. It carries no claim that pairs
a numeral with a connective, because it was written to exercise the criteria
rather than to resemble anything. That is the argument for the corpus in one
line: not that real claims are more numerous, but that they are shaped
differently from the ones a test author invents.
