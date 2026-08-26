# Validation run — five claims, against the prior art

A record of the engine run against five claims chosen to span the verdict
space, each compared with the method of the `israeli-fact-checker` skill
(v0.2 §11 prior art). The point is not that the two agree — they diverge
deliberately in two places — but that where they disagree, the reason is
identifiable and defensible.

**Both defects found here were invisible to the conformance suite.** It was at
376 tests when the more serious of the two was found. Fixture claims are
written to exercise criteria; real claims are shaped differently.

---

## The five

| # | Claim | Engine | Skill | Agree? |
|---|---|---|---|---|
| 1 | unemployment fell in 2021 | **Accurate** | **נכון** | yes |
| 2 | prices rose over the last three years due to governmental incompetence | **Misleading** | **מטעה** + **לשיפוטכם** on the cause | on the label; not on the cause |
| 3 | registered job-seekers fell in 2021 | **Accurate**, with the confusion caveat | **נכון**, if the analyst catches the trap | yes, by different means |
| 4 | output rose between 2019 and 2021 | **Indeterminate** — break | **לשיפוטכם** or a missed error | yes, if the analyst checks the break |
| 5 | the representative exchange rate fell below 3 in 2026 | **Insufficient Data** — unreachable | **נכון**, cited | **no — the skill wins** |

Claims 1–4 run against the fixture jurisdiction `ZZ`, where retrieval is real
and the whole pipeline executes. Claim 5 runs against the admitted Israel
pack, where routing is real and retrieval is not.

---

## Deeper: claim 1 — the defect that made this run worthwhile

`unemployment fell in 2021` returned **Substantially Inaccurate**.

Unemployment fell. The series runs from `5.4` to `4.2`, every admissible
alternative holds, and the engine still reported the claim as conflicting with
the record — with a complete citation trail behind it.

The period had been decomposed as a `QUANTITY`, so the *year* was extracted as
the claimant's figure and compared against the rate. Two thousand and
twenty-one is not four point two, so the element came back `contradicted`.

This is the worst error the system can make, and the one every other guarantee
exists to prevent: a confident, fully-sourced, wrong verdict on a true claim,
with nothing malfunctioning to reveal it. It bit any claim whose period named
a year — *in 2021*, *since 2019*, *between 2019 and 2021*, *March 2021*. That
is a large fraction of all checkable claims.

`ElementKind` now has `TIME_PERIOD`, and element verdicts give it a branch. A
period *scopes* a comparison; it is not a figure to compare. Coverage is what
it can be checked for, and still is — a period the series does not span is
Unverified, which is a real finding rather than an arithmetic accident.

After the fix:

```
RECONSTRUCTED
  In 2021 ZZ survey unemployment rate fell 4.2 percent.
VERDICT
  ACCURATE
```

The period now fills its declared slot too, so it survives into the
reconstruction instead of being dropped.

**Against the skill:** the skill would never have made this error, because a
person reading "in 2021" does not mistake it for a quantity. This is a class of
failure mechanical decomposition is uniquely prone to, and the reason the
element kinds have to be right rather than approximately right.

## Deeper: claim 3 — measure identity, the skill's first gotcha

`registered job-seekers fell in 2021` binds to `unemployment_registered`
(custodian `zzlabour`), **not** to `unemployment_survey` (custodian `zzstat`).
Two measures, two custodians, two populations.

The skill lists this as its own archetypal error: *"Confusing the two
unemployment figures… Quoting one as the other is a classic מטעה."* It is
handled there by an analyst remembering to check. Here it is handled by the
pack declaring both measures separately, binding on published name and
definition before any custodian is consulted, and carrying the confusion into
the output as a caveat on the citation:

```
Framing: Not the survey unemployment rate. Quoting one as the other is
the archetypal misleading-but-numerically-true claim in this fixture.
```

**This is the engine's clearest advantage.** The skill relies on the checker
knowing the trap. The engine cannot route to the wrong measure without the
pack declaring it, and cannot report the right one without surfacing why it is
easy to confuse. The knowledge lives in versioned data rather than in the
attention of whoever is checking today.

The cost is exactly proportional: the engine only knows the confusions a pack
author wrote down. An undeclared confusion is invisible, whereas a good analyst
might still catch it.

## Deeper: claim 4 — the break register earning its place

`output rose between 2019 and 2021` returns **Indeterminate**, and nothing
reconstructs:

```
- rose [contested_by_definition]
    Comparison spans a declared series break (methodology) that no linked
    series covers. The figures either side are not comparable.
```

`output_index` carries a methodology break at 2019-06 with
`linked_series_available = false`. The comparison spans it, so no element can
reach Verified, however cleanly the arithmetic works.

That last clause is the whole point, and it is why continuity is checked
*before* the numeric comparison rather than after. Both figures are real and
published. Subtracting one from the other produces a number. The number means
nothing, and a pipeline that compared first and checked continuity second
would emit a verified figure with a caveat nobody reads.

**Against the skill:** the skill warns about base-year changes and revisions in
prose, and depends on the checker looking. The engine cannot proceed without a
register, and where a register is empty it degrades to Indeterminate rather
than guessing. That is the same trade as claim 3 — declared knowledge beats
remembered knowledge, and declares its own absence.

---

## Where the two genuinely diverge

**Causal claims (claim 2).** The skill rates them **לשיפוטכם** and presents the
data. The engine refuses *any* label and routes the clause to a derived element
tagged `implied-by-original-only`. Ours is stricter, and §9.6 argues the case:
a causal verdict is argument wearing a verification badge, however hedged.
Recorded at [`plan.md` §2.2a](plan.md#22a-divergence-from-the-prior-art-deliberately-retained).

**Claim 5, where the skill simply wins.** It produced a correct, cited verdict
— the rate stood at `2.9860` on the day checked — and the engine produced
Insufficient Data. The entire difference is that a person can fetch
`boi.org.il` and the engine has no client for it. The pack routes correctly and
then has nowhere to go:

```
- fell [unreachable]
    Representative exchange rate, US dollar was bound, and no client is
    configured for its custodian in this deployment, so the record was
    never consulted.
```

That is the honest scoreboard on the one claim the real pack was built for.
The engine's answer is *correct* — it does not know — but the skill's answer is
*better*, and no amount of design fixes that. It needs an adapter.

---

## What this run establishes

- The pipeline works end to end on real retrieval: binding, routing, retrieval,
  continuity, tolerance, sweep, reconstruction, ledger, derivation, verdict.
- Two of the three verdicts that differ from the skill differ **by design**,
  and the design is written down.
- The third difference is a missing network client, not a disagreement.
- **Mechanical decomposition has failure modes a human checker does not**, and
  the conformance suite does not find them. Claim 1 is the proof: 376 tests
  green, and a true claim labelled Substantially Inaccurate.
