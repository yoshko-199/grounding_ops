# Tutorial — Verify your first claim

In this tutorial you will run four claims through the engine and read what
comes back. By the end you will have seen the system verify a claim, refuse to
verify part of one, decline to answer at all, and surface an implication it
will not put a label on.

You need Python 3.11 or later and a checkout of this repository. Nothing else —
there are no dependencies to install. Every command below runs with
`PYTHONPATH=.` and needs nothing more; if you would rather install the
commands once and drop that prefix, see
[installing the three CLIs](reference/cli.md#installing-the-three-clis).

**About twenty minutes.** Type the commands rather than skimming them; each one
shows you something the next one builds on.

---

## Step 1 — Check your setup

From the repository root:

```
python3 -m pytest tests/ -q
```

You should see a line ending in `passed`. If you do, the engine works and you
can continue.

Now run the consistency checks over the documents:

```
python3 scripts/check_spec.py
```

You should see `All checks passed`.

---

## Step 2 — Verify a claim

Run this:

```
PYTHONPATH=. python3 cli/verify.py \
  "prices rose over the last three years due to governmental incompetence" \
  --jurisdiction ZZ --packs packs/fixture
```

A lot comes back. We will go through it section by section, so do not worry
about reading it all yet.

`ZZ` is a synthetic jurisdiction that ships with the repository. It is not a
country, and its custodians are not real institutions. It exists so you can
exercise the whole pipeline without any real data being involved.

---

## Step 3 — Read the artifact, one section at a time

Look at the top of the output first:

```
[UNCONFIRMED — proposed, not signed off]

ORIGINAL CLAIM
  prices rose over the last three years due to governmental incompetence
```

Everything the engine produces is marked unconfirmed until a person signs it
off. You will do that yourself in step 7.

### The reconstruction

```
RECONSTRUCTED
  Over the last three years ZZ Price Index rose 102.4 index_points.
```

This is the claim rebuilt from **only the parts that survived checking**. Notice
what is gone: there is no "due to", and no "incompetence".

### The discard ledger

```
DISCARD LEDGER
  - due to [out_of_scope]
      a causal link. No institution publishes the share of an outcome
      attributable to a cause, so there is no figure to retrieve...
  - incompetence [out_of_scope]
      evaluative language; no truth value to check against a record
```

The ledger is the other half of the reconstruction, and the two are always
shown together. A reconstruction on its own would be a quiet edit of what
somebody said. Shown next to the ledger, it is a visible one.

Read those two reasons carefully — they are the heart of the design. The engine
did not decide the government was competent. It decided that *no record exists*
which could settle the question, and said so.

### The verdict

```
VERDICT
  MISLEADING
```

Every element of the claim checked out against the record. The verdict is still
*Misleading*, and the next section is why.

### The robustness sweep

```
ROBUSTNESS SWEEP
  [FLIPS] baseline: prior_period
      2021-11 (103.1) to 2021-12 (102.4)
  [holds] baseline: prior_year
      2021-01 (100.0) to 2021-12 (102.4)
  ...
```

The engine re-ran the claim against every comparison the pack declares
legitimate for this measure. Against the previous year, prices rose. Against
the previous month, they *fell*.

Both figures are real and both come from the same custodian. The claim is true
under one comparison and false under another, and it did not say which it meant.
That is what *Misleading* means here, and the table is the evidence for the
label rather than an opinion about it.

### Citations and routing

Below that you will find one citation per retrieved data point, and a routing
note saying which custodian was consulted and why. Skim them. The point to
notice is that **every number in the reconstruction appears in a citation** —
the engine cannot render a figure it did not retrieve.

### Derived elements

```
DERIVED ELEMENTS (proposed, not confirmed)
  [implied-by-original-only] This claim invites the conclusion that prices rose
  over the last three years is asserted to be caused by governmental
  incompetence.
      operation: causal-discharge
```

The causal claim did not vanish. It was extracted, made explicit, and shown
separately — labelled as something the claim *invites you to conclude*, not
something the engine checked.

Notice how stiff that sentence is. That is deliberate: every content word in it
comes from the original claim, so the engine cannot smooth it into fluent prose
without supplying words the claimant never used.

---

## Step 4 — Watch the engine decline to answer

Try a country the engine knows nothing about:

```
PYTHONPATH=. python3 cli/verify.py "inflation rose in 2021" \
  --jurisdiction QQ --packs packs/fixture
```

You get:

```
VERDICT
  INSUFFICIENT DATA
  no jurisdiction could be established from the claim text or the ingest
  context. There is no default jurisdiction: a default would produce a
  confident, fully-cited verdict against the wrong country's custodian, with
  nothing malfunctioning to reveal it
```

Now check the exit code:

```
echo $?
```

It is `0`. Not an error.

This is worth pausing on. *Insufficient Data* is an answer the system is proud
of, rendered in the same place and the same weight as any other verdict. The
alternative — falling back to some other source when the right one is missing —
is the single failure this whole system is built to prevent.

---

## Step 5 — Watch a claim get routed out

```
PYTHONPATH=. python3 cli/verify.py \
  "you dont see a curve therfore the earth is flat" \
  --jurisdiction ZZ --packs packs/fixture
```

Two things happened.

First, the verdict is *Insufficient Data* — **not** *False*. No custodian
publishes a figure that settles this, so the engine has nothing to check it
against and does not pretend otherwise.

Second, look at the bottom:

```
DERIVED ELEMENTS (proposed, not confirmed)
  [implied-by-original-only] This claim invites the conclusion that the earth
  is flat is asserted to follow from you dont see a curve.
      operation: inferential-discharge
```

The engine could not rate the claim, but it could still show you its structure:
this is an *inference*, and here is the premise it rests on.

Notice that `therfore` is misspelled and it still fired. Real claims carry
typos, and a trigger that misses one under-fires silently.

---

## Step 6 — Get machine-readable output

Add `--json`:

```
PYTHONPATH=. python3 cli/verify.py \
  "prices rose over the last three years due to governmental incompetence" \
  --jurisdiction ZZ --packs packs/fixture --json
```

Same artifact, structured. This is what you would use to feed another system.

---

## Step 7 — Sign off the verdict

Everything so far was marked `UNCONFIRMED`. A person has to sign off the
claim-level verdict before it can be exported:

```
PYTHONPATH=. python3 cli/signoff.py confirm \
  --reviewer "your name" --proposed misleading
```

You get back a signed verdict with `exportable: True`.

Now try changing the label — a reviewer is allowed to do that:

```
PYTHONPATH=. python3 cli/signoff.py amend \
  --reviewer "your name" --proposed misleading --label indeterminate \
  --rationale "the flip table is ambiguous on the intended baseline"
```

Finally, try amending *without* a reason:

```
PYTHONPATH=. python3 cli/signoff.py amend \
  --reviewer "your name" --proposed misleading --label accurate
```

The gate refuses. A reviewer may change the label, but never silently.

There is deliberately no flag on this command that could reach an element
status, a retrieval, or the discard ledger. A reviewer can change what the
system *concluded*; they cannot change what it *found*.

This used `--proposed` to try the gate on a label typed by hand. The real
workflow signs off a claim you actually verified, by the id `cli/verify.py`
printed: `cli/signoff.py list` shows what is awaiting review, and
`cli/signoff.py confirm --claim-id <ID> --reviewer "..."` reads the real
rationale from the store and writes the decision back into it. See
[how to sign off a verdict](how-to/sign-off-a-verdict.md).

---

## What you learned

- The engine rebuilds a claim from only what survived, and always shows the
  ledger of what it removed.
- A claim can be entirely true and still *Misleading*, and the flip table is
  the evidence.
- *Insufficient Data* is a real answer, not a failure — exit code and all.
- Causal and evaluative content is extracted and shown, never rated.
- A person signs off the verdict, and only the verdict.

## Where to go next

- **To do a specific task:** the [how-to guides](README.md#how-to-guides).
- **To understand why it is built this way:** the [overview](overview.md).
- **To look something up:** the [CLI reference](reference/cli.md).
- **To make it work on a real country:** [add a jurisdiction pack](how-to/add-a-jurisdiction-pack.md) — and read the [roadmap](plan.md) first, because that is the hardest job in the repository and it is unfinished on purpose.
