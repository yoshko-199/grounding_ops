# How to contribute a change

The workflow for any change to code, packs or documents, and what to do when
the gate says no. If you haven't yet, do the
[contributor tutorial](../tutorial-contributor.md) first; it shows each of
these steps once, on purpose.

## 1. Start green, on a branch

```
git switch -c <your-branch>
python3 -m pytest tests/ -q
```

Never start from a red suite. It hides the failure your change is about to
cause.

## 2. Put the change where it belongs

Where a change lives is as much a part of it as what it does, because the
boundaries are what the tests assert. Use this table:

| You are changing | It goes in | Because |
|---|---|---|
| A rule of one pipeline stage | That stage's module under `engine/verification/` (see the [stage map](../reference/codebase.md#stages-and-the-modules-that-own-them)) | `engine/pipeline.py` orchestrates and decides nothing |
| Who is authoritative for a measure, a series break, a tolerance input, vocabulary | A pack under `packs/`, never engine code | Generalising to a jurisdiction is a pack. See [add a jurisdiction pack](add-a-jurisdiction-pack.md) |
| What the artifact shows | `engine/render/artifact.py` | The render boundary is where AC-1, AC-2, AC-5 and AC-7 are enforced |
| What gets stored after a run | The writers in `engine/store/` | Persistence is composition-root bookkeeping, unreachable from verification |
| Anything that needs the network | A custodian adapter, or `cli/`, imported lazily | Verification must stay statically unable to reach a network primitive |
| A command-line option or a web UI page | `cli/`, sharing `cli/compose.py` | The command line and the web UI must not drift apart |
| Where candidate claims come from | `plugins/harvest/` and `sources/` | Claim intake is outside the engine, and nothing in the engine may reach it |

## 3. Write the test with the change, and watch it fail

Add or extend a test in the same change, and prove it fails without your
change: revert the code, run the test, see it fail for the reason you meant,
then restore. A test that has never failed has not shown it can.
[Add a regression test](add-a-regression-test.md) covers which kind of test
goes where.

## 4. Change the documents in the same commit

A stale document is a defect here, and every one found so far was one commit
old. Update whichever applies:

| If you changed | Update |
|---|---|
| A flag, output section, exit code, route or status | [CLI reference](../reference/cli.md) |
| A pack field | [Pack schema](../reference/pack-schema.md), and the [pack interface](../spec/custodian-pack-interface.md) with a version note |
| A workflow a person follows | The how-to guide for it |
| A module, stage or boundary | [Codebase reference](../reference/codebase.md) |
| What is done or deliberately not done | [Roadmap](../plan.md) |
| The test count | The comment in the `README.md` command block |

Then run `python3 scripts/check_spec.py -v`.

## 5. Run the full gate

[Run the full gate](run-the-full-gate.md). All five parts, every time.

## 6. Commit

Match the history: an imperative subject line that names the change, then a
body that says **why**. Say what was wrong or missing, what the change does
about it, and how you proved the test can fail. Mention anything you
deliberately did not do.

Push to your branch. A pull request is opened when someone asks for one.

---

## When a criterion fails

The rule is that **the change is wrong until proven otherwise.** Never skip,
weaken or quarantine a test, and never widen an acceptance criterion so a
change fits.

1. **Read the criterion.** Each conformance file is named for one:
   `tests/conformance/test_ac07.py` is
   [AC-7](../spec/acceptance-criteria.md#ac-7--no-unsourced-figure). The
   criterion states what it protects and why.
2. **Find what your change did to it.** These fixes have come up more than
   once:

| Failure | Usual cause | Fix |
|---|---|---|
| `UnsourcedFigure` from a render | A numeral in prose that no retrieval accounts for: a count, a section number, a version, an adapter's error text | Take the numeral out of the output. Technical text goes to `PullOutcome.diagnostic`, which is printed only by `--diagnostics`, outside the artifact |
| An import-graph test in `test_ac06.py`, `test_ac14.py`, `test_plugin_isolation.py` or the writer-isolation tests | A new import reaches something across a boundary, directly or transitively | Move the import to the composition root, or make it lazy there. Never relax the graph |
| AC-5 | Insufficient Data rendered or styled differently from other verdicts, or a non-zero exit for it | It is an answer: same container, same weight, exit `0` |
| AC-10 | Sign-off can reach something beneath the claim-level label | Remove the path. The gate takes a label and a rationale and nothing else |
| A pack fails to load | A required field is missing | Fill it from the custodian's own publication, or leave the measure out. Never fill it from memory |

3. **If you still believe the criterion itself is wrong**, that is a
   specification change, not a test change. Write down why, propose it
   against the [specification](../spec/claim-verification-engine.v0.6.md),
   and leave the test as it is until that is decided.
