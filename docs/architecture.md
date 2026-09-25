# Why the code is shaped this way

This is a discussion, not a reference. The [codebase reference](reference/codebase.md)
says where things are. This page explains why they are there. The short
version is that this system produces authoritative-looking text, and
authoritative-looking text is exactly what a bad actor, or a careless change,
would want to launder a conclusion through. So the important properties are
not left to good intentions. Each one is placed where the structure of the
code makes it hard to lose, and then asserted by a test that fails the build.
The [specification](spec/claim-verification-engine.v0.6.md) puts it plainly:
a principle that cannot fail a build is decoration.

The same idea runs through every section below: **put the guarantee where
getting around it would take a visible change, not a forgotten one.**

## The engine cannot reach the network

The rule is "no generic fallback": when no custodian covers a claim, the
answer is Insufficient Data, never a web search or a plausible substitute.
You could enforce that with a code review checklist. Here it is enforced by
making it impossible to express. Nothing under `engine/verification/` can
import a network primitive, directly or through anything it imports, and
`tests/conformance/test_ac14.py` checks that on the import graph.

Network access still has to exist somewhere, because a real custodian has to
be fetched. It lives at the **composition root**, `cli/`, and in the custodian
adapters. The adapters are the one boundary allowed to originate a figure, and
`engine/custodians/live.py` imports `urllib` lazily for exactly this reason.
The web UI's `http.server` lives in `cli/serve.py` for the same reason.

The graph is built statically, from source, rather than by watching what a
test run imports. The failure this guards against is precisely an import on a
path no test happens to execute: the latent dependency that works until the
day it quietly becomes a fallback. A runtime check would miss it by
construction. The [contributor tutorial](tutorial-contributor.md#step-4--break-an-architectural-boundary-on-purpose)
shows a single unused import failing two tests, because the graph is
transitive.

## Guarantees live at the boundary, not at the call site

"No unsourced figure" could have been a rule every stage promised to follow.
Instead, it is checked once, where output actually happens:
`engine/render/figures.py` scans what is about to be emitted and raises
`UnsourcedFigure` for any numeral no retrieval accounts for. It raises rather
than warns because a warned figure still reaches a reader who assumes it was
checked, and the warning goes to a log nobody reads.

That choice has consequences worth understanding:

- **The scan cannot tell a harmless number from an invented one.** A section
  number, a version or a count of tests fails the render just as a made-up
  statistic would. That is deliberate: a rule that tried to tell them apart
  would be a rule with an exception, and the exception is where laundering
  would enter. So numbers that are not figures are kept out of output
  altogether.
- **Technical text needs its own channel.** A custodian's error message
  usually carries a status code, which is a numeral. It goes to
  `PullOutcome.diagnostic`, which is shown only by `--diagnostics`, outside
  the artifact, and never into a rendered reason.
- **Every new output path is a new boundary.** The HTML page
  (`Artifact.render_html()`) runs the text render first as its gate, because
  `to_dict()` is never scanned and a page built on it would have been the one
  path the rule did not reach.

The same reasoning puts the ledger rule in the artifact type itself. The
reconstruction is a private field with no public accessor, and every method
that emits it emits the ledger too. Nobody has to remember to include the
ledger; there is no way to get the reconstruction without it.

## Identity is split at the door

"Identical treatment regardless of claimant" is hard to promise and easy to
break: one helpful log line, one "context" field, and the claimant's name
reaches the verification path. So provenance is split at ingest, in
`engine/ingest/split.py`. Only a `ClaimContext`, holding a jurisdiction code, a
language code and a date, crosses into the pipeline. `verify()` takes a
`ClaimContext` and never a `ClaimantIdentity`, so the signature itself states
the rule. AC-6 asserts on the import graph that identity is unreachable from
verification.

Even persisting identity is kept apart. `engine/store/identity_writer.py` is
a separate module precisely because it is the one that imports identity, so
the writer that stores everything else cannot carry an identity import path
into the store's other tables.

## Plugins sit outside

The claim harvester, `plugins/harvest/`, does what the adapter contract
forbids: it reaches the network, reads publications and accounts, and fetches
from addresses an operator declares. That is fine on the claim-*input* side,
where the question is "what was said?", and fatal anywhere near evidence,
where the question is "what is on the record?". So it sits outside the
engine, and the separation is asserted, not agreed. No engine module may reach
a plugin, and no harvest module may reach the adapters, the retrieval layer
or the store.

The fuzzer, `plugins/shapes/`, is outside for a different reason: it drives
the engine, so the engine must not depend on it.

## A reconstruction is a projection, not an edit

The obvious way to update a reconstruction when an element's status changes
is to edit the previous sentence. That produces a text generator that
accretes. It cannot shrink correctly when support is lost, and it collects
connective phrasing no element licenses. Instead, every reconstruction is
re-derived from scratch as a pure function of the current verified element
set (§4, "Stage 7"). The reconstructor is not given the previous revision, so
it cannot edit it. Shrinking is then as natural as growing, and "equal
element-set hash implies identical text" becomes checkable after the fact.

The same structure answers "can a reconstruction acquire a causal clause?"
It cannot, because causal and evaluative fragments are marked out of scope
at the first stage and the reconstructor reads only verified elements. There
is no path for such a clause to arrive by (§9.6).

## Retrievals are events, not facts

A retrieved figure is true *as of when it was retrieved*, for *that
revision*. So the store keeps retrieval events with a TTL derived from the
custodian's publication cadence, not timeless facts. Expired events are
re-pulled, never served, and there is no grace period, degraded mode or force
flag, because each of those is a way to serve a stale figure under pressure.
`engine/store/events.py` returns an `EXPIRED` sentinel rather than `None`, so
"never fetched" and "fetched but expired" cannot be confused at a call site.

Two consequences follow. A published revision *invalidates* a provisional
retrieval rather than deleting it, because the record of what was believed
and when is the point. And reusing a stored retrieval is only ever
deduplication of an identical event: every field that would be written must
match. Reuse that substituted a stored figure for a freshly pulled one would
let an artifact cite a figure its verdict was not computed from.

## The gate is narrow by signature

Human sign-off is the most credible place to launder a conclusion, because it
arrives wearing the authority of review. So the gate's authority is narrowed
where it cannot be argued with, at the API. `engine/signoff.py`'s
`confirm`, `amend` and `reject` take a label and a rationale and have no
parameter that could reach an element status, a retrieval, the ledger, the
sweep or a pack. The rationale is scanned for figures exactly as pipeline
output is. The web UI restates the same boundary: its sign-off form reads five
named fields and nothing else, and a test asserts that every row beneath the
verdict is byte-identical after a sign-off.

## Jurisdictions are data

A new country is a new pack, never an engine change. Custodians, measures,
series breaks, tolerance inputs, admissible baselines and even the
vocabulary for "rose" and "fell" are pack data, versioned and frozen once
loaded. There are three reasons. It keeps jurisdictional judgment inspectable
in one place. It makes thresholds and routing non-configurable by an
operator, since partisanship enters most invisibly through source selection.
And it confines the one kind of error this system exists to prevent,
plausible but unconfirmed data, to a place where the rule against it is
simple to state: every field from the custodian's own publication, or
`[confirm]`.

## One composition, two front ends

The command line and the web UI both go through `cli/compose.py`. Two front
ends that each composed the pipeline themselves would be two places for the
same rules to drift apart: which directory counts as having packs, what an
unopenable store looks like, in which order an artifact's tables are written,
what a reviewer may pass to the gate. Sharing the composition means a fix in
one is a fix in both, and the command line's existing tests pin the behaviour
of each.

## Tests that have failed

The last habit is cultural, not structural. The suite has tests for each
criterion, a static import graph, and a claim-shape fuzzer that has found
defects the criteria could not, because real claims are shaped differently
from the ones a test author invents. On top of that, a test here earns trust
by failing once. When a guard is added, someone breaks the code it protects
and watches it fail for the right reason before relying on it. A green suite
of tests that could never have failed is the same trap the whole system is
built to avoid: something that looks checked and is not.
