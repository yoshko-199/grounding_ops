# Validation run — ten supplied claims

Ten claims, supplied as a test set, were run through the engine on the
command line and through the web UI in a real browser. This page records
what came back, the three defects the run found and fixed, and the two gaps
it recorded instead of patching. The [earlier validation run](validation.md)
compared the engine with its prior art. This one tests it on claims nobody
wrote to exercise it.

## The claims

They were pasted into a working session as a test set: general English
claims about physics, food, biology, history, epidemiology, vaccines,
arithmetic, materials and US policy. They were not harvested from any
source, and they are quoted here exactly as supplied.

| # | Claim |
|---|---|
| 1 | Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at sea level. |
| 2 | Pizza is the most delicious food in the world. |
| 3 | Humans are classified as mammals. |
| 4 | King John of England signed the Magna Carta in 1225 |
| 5 | Covid-19 epidemic originated from a Chinese research lab |
| 6 | Vaccines cause Autism in children |
| 7 | If you put two sheep in a field, and then another two, you’ve got four sheep in that field for ever. |
| 8 | the density of steel is 7700 kg per cubic metre. |
| 9 | The U.S. has a highly progressive tax-and-transfer system that redistributes massive sums of money. |
| 10 | In the U.S gun violence is alien to most people's experiences and the nation's murder rate has been cut by more than half since 1991 |

## What came back

**Every claim is Insufficient Data, and that is the right answer.** No
admitted pack covers boiling points, biology, history, epidemiology,
materials or US statistics. Where no custodian of record covers a claim, the
engine says so rather than reaching for a search result or a remembered
figure. It does that whether a claim is true or false, and this page does not
say which is which either: adjudicating these claims from memory is exactly
what the system exists to refuse.

Each claim was run two ways:

- **Against the Israel pack, with no jurisdiction hint.** None of the claims
  names a jurisdiction any pack declares, so none resolves one. Without a
  pack there is no vocabulary to decompose with, and the artifact now says so
  (see defect 2).
- **Against the fixture pack, with the `ZZ` hint.** This forces a pack and
  its English vocabulary, so decomposition, the scope gate and derivation all
  run. It is where the defects showed.

| # | Fixture ledger, after the fixes | Derived elements | Why Insufficient Data |
|---|---|---|---|
| 1 | `100` and `212`, unverified | none | No measure matches |
| 2 | the whole claim, out of scope | none | No quantity or administrative fact |
| 3 | the whole claim, out of scope | none | No quantity or administrative fact |
| 4 | `in 1225`, unverified | none | No measure matches |
| 5 | the whole claim, out of scope | none | No quantity or administrative fact |
| 6 | the whole claim, out of scope | none (see gap 1) | No quantity or administrative fact |
| 7 | the whole claim, out of scope | none | No quantity or administrative fact |
| 8 | `7700`, unverified | none | No measure matches |
| 9 | the whole claim, out of scope | none | No quantity or administrative fact |
| 10 | `since 1991`, unverified | `comparative-discharge` (see gap 2) | No measure matches |

Through the web UI, served with the Israel pack, all ten returned 200 with
INSUFFICIENT DATA in the shared verdict container, and none produced a form
problem.

## Three defects, fixed

1. **A digit inside a name became a figure.** "Covid-19" decomposed its
   "19" as a quantity, which then sat in the ledger as an unverified figure
   the claim never asserted. The number pattern now skips a digit joined to a
   word by a hyphen, as in "Covid-19", "F-35" and "G-7", including the Unicode
   hyphen and non-breaking hyphen. A number after a space, such as "fell to
   -5 percent", and ranges such as "2021-22" still decompose.
2. **An empty ledger that didn't say why.** With no jurisdiction, the
   artifact said "does not reconstruct" and "Nothing was discarded". Both
   were literally true, since nothing was decomposed, but a reader saw a
   whole claim dropped by a ledger claiming nothing was. The ledger now says
   the claim was not decomposed because no pack's vocabulary applies, and
   the verdict says why. The structured output gains a `decomposed` key, and
   the read-back infers the same case from there being no stored elements.
3. **Superlative triggers matched inside other words.** Decomposition
   searched for trigger phrases as bare substrings, so the fixture's
   superlative trigger "ever" fired inside "every", "never" and "however".
   A claim like "prices rose every year" gained a superlative element, and a
   superlative bypasses the tolerance bands. Triggers now match whole words,
   as derivation and the surface vocabulary already did. Separately, the
   fixture's bare "ever" also fired on claim 7's "for ever", so it was
   replaced with phrases that carry the ranking sense: "ever recorded" and
   "of all time".

Each fix has a regression test in `tests/unit/test_ten_claims.py`, and each
test was checked to fail with its fix reverted. One of them only exists
because the first version didn't: with the bare "ever" gone from the
fixture, reverting to substring matching passed every test until a case
using the remaining triggers ("record" inside "recorded") was added.

## Two gaps, recorded rather than patched

1. **Active-voice causal verbs are missed.** "Vaccines cause autism" derives
   no causal element. The triggers are connectives such as "due to" and
   "caused by", where the effect comes first. In "A causes B" the cause
   comes first, so adding "cause" as a trigger would state the relationship
   backwards. Covering it needs a derivation operation that knows which
   flank is the cause, a change to the closed list in
   [§9.7.2](spec/claim-verification-engine.v0.6.md#972-admissible-derivation-operations).
   It is recorded as evidence for the
   [derivation coverage question](spec/claim-verification-engine.v0.6.md#10-remaining-open-questions).
   The failure is in the safe direction: the implication is not surfaced,
   rather than surfaced wrongly.
2. **A two-part claim derives as one.** Claim 10 joins two assertions with
   "and". Its comparative derivation spans both and reads "…has been cut by
   is asserted to be more than half since 1991". That is the stiffness the
   [roadmap](plan.md#22-derivation-coverage--needs-a-corpus) already
   defends: every word is the claimant's own. Splitting compound claims
   into their assertions is a decomposition change the spec has not yet
   made.

## With demo sources

Every claim above is Insufficient Data because nothing covers it. The
[demo pack](how-to/try-the-demo-pack.md) gives them somewhere to be verified.
It is a synthetic jurisdiction whose invented values land each claim, and a
few labelled variants, on a chosen level. Between them they reach every
claim-level verdict the engine can produce: Accurate, Misleading,
Substantially inaccurate, False, Indeterminate and Insufficient Data. They
also reach every element status, including *contested by definition* on
claim 8, whose two steel measures are both cited.

Building it exposed more than missing data: eight gaps in the specification
and three places where the code diverged from it. The divergences were the
unreported contest on claim 8, the `rounded` tag never shown, and a sweep
baseline anchored at the middle of the series. All three are now fixed. Every
item is written up in the
[requirements for the next specification version](spec/proposals/v0.6-requirements.md),
with the fixes recorded beside their evidence.

Each result now also opens with a plain-words bottom line: what the record
supports and contradicts, the closest version the sources back, and which
sources. Claim 2 reads "neither confirmed nor refuted" rather than anything
suggesting it is false, which is what Insufficient Data means.
The real-figures counterpart is a [scaffold](spec/packs/demo-real.md). The
network allowlist blocks every authority's site, so every figure waits to be
fetched from the authority's own page.

## What this run establishes

Real claims find what fixture claims miss, and they did it three times from
ten claims. None of the defects changed a verdict here, since every claim
is Insufficient Data regardless. Each would have mattered on a claim a pack
did cover: a phantom figure in the ledger, a phantom superlative that
bypasses tolerance, and a ledger that looks like it hides something.
