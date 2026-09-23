# Documentation

Organised by the [Diátaxis](https://diataxis.fr/) framework. The four quadrants
answer different questions, and knowing which one you are in saves time:

|  | **Practical steps** | **Theoretical knowledge** |
|---|---|---|
| **Study** | [Tutorial](#tutorial) — a lesson | [Explanation](#explanation) — a discussion |
| **Work** | [How-to guides](#how-to-guides) — a recipe | [Reference](#reference) — a dictionary |

**New here?** Start with the [onboarding guide](onboarding.md). It sets out
the rules everyone works under and a reading path for your role: analyst,
reviewer, pack author or contributor. Then do the [tutorial](tutorial.md),
which takes about twenty minutes and needs nothing installed beyond Python.

---

## Tutorial

Learning-oriented. Follow it start to finish; it builds one understanding in
order and every step is meant to be typed.

| Document | You will |
|---|---|
| [Verify your first claim](tutorial.md) | Run a claim through the pipeline, read every section of the artifact, watch a claim get routed out, and see the system refuse to answer |
| [Your first change](tutorial-contributor.md) | For contributors: trace a claim through the stages, break two guarantees on purpose and watch the right tests catch them, then write a test and prove it can fail |

## How-to guides

Problem-oriented. Each assumes you know roughly what you are doing and want the
steps for one task.

| Guide | For when you need to |
|---|---|
| [Verify a claim](how-to/verify-a-claim.md) | Check a specific claim, control the jurisdiction and date, or get machine-readable output |
| [Read back a stored verification](how-to/read-back-a-stored-verification.md) | Look up a claim you verified earlier by its claim id, without re-verifying it |
| [Use the web UI](how-to/use-the-web-ui.md) | Verify claims and read them back in a browser instead of a terminal |
| [Add a jurisdiction pack](how-to/add-a-jurisdiction-pack.md) | Make the engine able to route claims in a country it does not yet cover |
| [Declare a harvest source](how-to/declare-a-harvest-source.md) | Point the claim harvester at a publication and its accounts |
| [Sign off a verdict](how-to/sign-off-a-verdict.md) | Confirm, amend, or reject a proposed claim-level verdict |
| [Fuzz claim shapes](how-to/fuzz-claim-shapes.md) | Find the defects the acceptance criteria cannot, after changing decomposition, derivation, verdicts, or rendering |
| [Run the full gate](how-to/run-the-full-gate.md) | Check a change before pushing: the suite, the document checks, the fuzzer, the regression claims and the harvester |
| [Contribute a change](how-to/contribute-a-change.md) | Know where a change belongs, what to update with it, and what to do when a criterion fails |
| [Add a regression test](how-to/add-a-regression-test.md) | Choose the right kind of test, write it with the shared fixtures, and prove it can fail |

## Reference

Information-oriented. Look things up here; do not read it through.

| Document | Describes |
|---|---|
| [CLI reference](reference/cli.md) | Every command, flag, output section, and exit code, and the web UI's routes |
| [Codebase reference](reference/codebase.md) | The layout, which module owns each stage, the import rules, where each guarantee is enforced, the store's tables, and the test suite |
| [Glossary](reference/glossary.md) | Every term used with a precise meaning, with the full set of values where there is one |
| [Pack schema](reference/pack-schema.md) | Every field of a custodian pack TOML file |
| [Source schema](reference/source-schema.md) | Every field of a harvest source TOML file |
| [Specification v0.5](spec/claim-verification-engine.v0.5.md) | The normative design: stages, taxonomies, persistence model, resolved decisions |
| [Acceptance criteria](spec/acceptance-criteria.md) | The anti-laundering constraints as binary pass/fail tests |
| [Custodian pack interface](spec/custodian-pack-interface.md) | The normative contract a pack must satisfy |

## Explanation

Understanding-oriented. Read these when you want to know *why*.

| Document | Discusses |
|---|---|
| [Overview](overview.md) | What the system does, how the pipeline hangs together, and why it cannot quietly become an advocacy tool |
| [Why the code is shaped this way](architecture.md) | Why each guarantee sits where it does: the composition root, the render boundary, the identity split, plugins outside, events not facts, and a narrow gate |
| [Validation run](validation.md) | Five claims against the prior art, three examined closely, and the two defects the conformance suite could not find |
| [Roadmap](plan.md) | What is settled, what is deliberately unfinished, and what gates a real deployment |
| [Israel pack draft](spec/packs/israel.md) | A real jurisdiction worked through the interface, and the seven blockers stopping its admission |
| [Source admission](../sources/README.md) | What a claim source must establish before it can be harvested |

---

## A note on what you will not find

There is no "getting a real answer about a real country" guide, because the
engine cannot yet do that. The Israel pack admits three Bank of Israel
exchange-rate measures, and they route. But live retrieval has never run from
the development environment, so a claim about them comes back *Unreachable*,
and every real claim returns **Insufficient Data**. That is the designed
answer rather than a missing feature. The [overview](overview.md) explains
why, and the [roadmap](plan.md) records what closing it requires.

Everything in the tutorial and the how-to guides therefore runs against `ZZ`, a
synthetic fixture jurisdiction that exists so the guarantees can be exercised
end to end without populating a real one from recollection.
