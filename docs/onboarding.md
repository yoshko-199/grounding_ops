# Onboarding guide

Welcome. This page gets you from a fresh checkout to working confidently in
this repository. It links out to the rest of the documentation, which follows
[Diátaxis](https://diataxis.fr/): tutorials to learn, how-to guides to get a
task done, reference to look things up, and explanation to understand why.
It doesn't repeat them.

Start with the section for your role. Everyone should read
[the five rules](#the-five-rules-everyone-works-under) first; they are short
and they are not negotiable.

---

## What this project is, in one paragraph

A claim, such as "prices rose over the last three years due to governmental
incompetence", is split into atomic elements. Each checkable element is
verified against the custodian of record for its measure: the institution that
publishes the official figure. A grounded version of the claim is rebuilt from
only the elements that survived, and it is always displayed with a ledger of
what was removed and why. The question the system answers is not "is this
true?" but "what part of this survives contact with the record, and what does
the surviving part actually support?" For the longer version, read the
[overview](overview.md).

## The five rules everyone works under

1. **No unsourced figure.** Every number in every output comes from a recorded
   retrieval against a named custodian. The render raises rather than warns.
2. **No generic fallback.** Where no custodian covers a claim, the answer is
   *Insufficient Data*: never a web search, a news source, or a plausible
   substitute.
3. **Insufficient Data is an answer, not a failure.** It is shown exactly like
   every other verdict, and the commands exit `0` for it.
4. **Never populate pack data from recollection.** A pack field that cannot be
   confirmed from the custodian's own publication stays `[confirm]`, and that
   thread stops there.
5. **Never weaken a test to get green.** When an acceptance criterion fails,
   the change is wrong until proven otherwise.

The [invariants table](reference/codebase.md#where-each-guarantee-is-enforced)
lists where each rule is enforced in code, and which test would fail if it
broke.

## Day one: for everyone

1. **Check your setup.** You need Python 3.11 or later and this checkout. There
   are no dependencies beyond `pytest` for the tests.

   ```
   python3 --version
   python3 -m pytest tests/ -q
   ```

   The suite should end with every test passed. If it doesn't, stop there and
   ask; nothing below assumes a red suite.
2. **Do the [tutorial](tutorial.md).** Run four claims through the engine and
   read every section of what comes back. It takes about twenty minutes.
3. **Open the web UI** and verify the same claim in a browser. Follow
   [use the web UI](how-to/use-the-web-ui.md).
4. **Skim the [glossary](reference/glossary.md).** Words like *custodian*,
   *measure*, *discard ledger* and *flip table* have precise meanings here, and
   the rest of the documentation uses them without defining them.

## Then pick your path

### Analyst: you verify claims

| Step | Read or do |
|---|---|
| Learn | [Tutorial: verify your first claim](tutorial.md) |
| Everyday tasks | [Verify a claim](how-to/verify-a-claim.md) · [Use the web UI](how-to/use-the-web-ui.md) · [Read back a stored verification](how-to/read-back-a-stored-verification.md) |
| Look up | [CLI reference](reference/cli.md): every flag, output section, verdict label and exit code |
| Understand | [Overview](overview.md), especially "Why it can't quietly become an advocacy tool" |

Expect *Insufficient Data* often. The only real jurisdiction with admitted
measures is Israel, with three Bank of Israel exchange rates, and no live
retrieval runs from the development environment. That is the designed answer
for everything no custodian covers, not a gap to work around. The
[roadmap](plan.md) records what widening coverage requires.

### Reviewer: you sign off verdicts

Every verdict is *proposed* until a person confirms, amends or rejects it. A
reviewer can change the claim-level label and nothing beneath it.

| Step | Read or do |
|---|---|
| Learn | [Tutorial, step 7: sign off the verdict](tutorial.md#step-7--sign-off-the-verdict) |
| Everyday tasks | [Sign off a verdict](how-to/sign-off-a-verdict.md) on the command line, or [sign off in the browser](how-to/use-the-web-ui.md#sign-off-in-the-browser) |
| Look up | [CLI reference: `cli/signoff.py`](reference/cli.md#clisignoffpy) |
| Understand | [Acceptance criterion AC-10, gate integrity](spec/acceptance-criteria.md#ac-10--gate-integrity) |

An amendment needs a reason in words. A figure in it is refused, for the same
reason the pipeline refuses one.

### Pack author: you add a jurisdiction

A pack is versioned data that declares who is authoritative for which measure.
It is never code.

| Step | Read or do |
|---|---|
| Everyday tasks | [Add a jurisdiction pack](how-to/add-a-jurisdiction-pack.md) |
| Look up | [Pack schema](reference/pack-schema.md) · [Custodian pack interface](spec/custodian-pack-interface.md) |
| Understand | [Israel pack draft](spec/packs/israel.md): a real jurisdiction worked through the interface, and what still blocks it |

Rule 4 applies to you more than anyone. Every field comes from the
custodian's own publication, cited, or it stays `[confirm]`.

### Contributor: you change the code

| Step | Read or do |
|---|---|
| Learn | [Tutorial: your first change](tutorial-contributor.md): trace a claim through the stages, break a guarantee on purpose, and add a test |
| Everyday tasks | [Run the full gate](how-to/run-the-full-gate.md) · [Contribute a change](how-to/contribute-a-change.md) · [Add a regression test](how-to/add-a-regression-test.md) · [Fuzz claim shapes](how-to/fuzz-claim-shapes.md) |
| Look up | [Codebase reference](reference/codebase.md): layout, stage-to-module map, import rules, test suite · [Acceptance criteria](spec/acceptance-criteria.md) |
| Understand | [Why the code is shaped this way](architecture.md) · [Specification v0.6](spec/claim-verification-engine.v0.6.md) |

The specification is the authority. When behaviour and the spec disagree, one
of them is wrong, and the question is which, not which one to bend.

## Week one: you are onboarded when you can

- [ ] Verify a claim on the command line and in the browser, and explain every
      section of the result.
- [ ] Say why *Unreachable* and *Unverified* are different statuses, and why
      *Insufficient Data* is not an error.
- [ ] Sign off a stored claim by id, and say what sign-off cannot change.
- [ ] Run the [full gate](how-to/run-the-full-gate.md) and read its output.
- [ ] For contributors: break a guarantee on purpose, watch the right
      criterion fail, and restore it.
      [The contributor tutorial](tutorial-contributor.md) walks you through it.
- [ ] Find, for any rule above, the module that enforces it and the test that
      asserts it, using the [codebase reference](reference/codebase.md).

## Where everything is

The full index, by quadrant, is the [documentation index](README.md).
