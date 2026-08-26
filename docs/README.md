# Documentation

Organised by the [Diátaxis](https://diataxis.fr/) framework. The four quadrants
answer different questions, and knowing which one you are in saves time:

|  | **Practical steps** | **Theoretical knowledge** |
|---|---|---|
| **Study** | [Tutorial](#tutorial) — a lesson | [Explanation](#explanation) — a discussion |
| **Work** | [How-to guides](#how-to-guides) — a recipe | [Reference](#reference) — a dictionary |

**New here?** Start with the [tutorial](tutorial.md). It takes about twenty
minutes and needs nothing installed beyond Python.

---

## Tutorial

Learning-oriented. Follow it start to finish; it builds one understanding in
order and every step is meant to be typed.

| Document | You will |
|---|---|
| [Verify your first claim](tutorial.md) | Run a claim through the pipeline, read every section of the artifact, watch a claim get routed out, and see the system refuse to answer |

## How-to guides

Problem-oriented. Each assumes you know roughly what you are doing and want the
steps for one task.

| Guide | For when you need to |
|---|---|
| [Verify a claim](how-to/verify-a-claim.md) | Check a specific claim, control the jurisdiction and date, or get machine-readable output |
| [Add a jurisdiction pack](how-to/add-a-jurisdiction-pack.md) | Make the engine able to route claims in a country it does not yet cover |
| [Declare a harvest source](how-to/declare-a-harvest-source.md) | Point the claim harvester at a publication and its accounts |
| [Sign off a verdict](how-to/sign-off-a-verdict.md) | Confirm, amend, or reject a proposed claim-level verdict |

## Reference

Information-oriented. Look things up here; do not read it through.

| Document | Describes |
|---|---|
| [CLI reference](reference/cli.md) | Every command, flag, output section, and exit code |
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
| [Validation run](validation.md) | Five claims against the prior art, three examined closely, and the two defects the conformance suite could not find |
| [Roadmap](plan.md) | What is settled, what is deliberately unfinished, and what gates a real deployment |
| [Israel pack draft](spec/packs/israel.md) | A real jurisdiction worked through the interface, and the seven blockers stopping its admission |
| [Source admission](../sources/README.md) | What a claim source must establish before it can be harvested |

---

## A note on what you will not find

There is no "getting a real answer about a real country" guide, because the
engine cannot yet do that. No real custodian pack is admitted, so every real
claim returns **Insufficient Data**. That is the designed answer rather than a
missing feature — the [overview](overview.md) explains why — and the
[roadmap](plan.md) records what closing it requires.

Everything in the tutorial and the how-to guides therefore runs against `ZZ`, a
synthetic fixture jurisdiction that exists so the guarantees can be exercised
end to end without populating a real one from recollection.
