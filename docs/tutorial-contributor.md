# Tutorial — Your first change

In this tutorial you will follow one claim through the engine's stages, break
two of its guarantees on purpose and watch the right tests catch each break,
then write a regression test and prove it can fail. By the end you will know
where the code for each stage lives, what "a criterion fails" looks like, and
the habit this repository relies on most: a test that has never failed has
not yet shown it can.

You need the setup from the [analyst tutorial](tutorial.md): Python 3.11 or
later and a clean checkout. Do that one first if you haven't; this one assumes
you can read an artifact.

**About thirty minutes.** Every change you make here is reverted by the end,
so your checkout finishes exactly as it started.

---

## Step 1 — Start from green

From the repository root:

```
git status
python3 -m pytest tests/ -q
```

`git status` should report a clean tree, and the suite should end with every
test passed. You start every change from here: a red suite hides the failure
you are about to cause.

## Step 2 — Trace a claim through the stages

The command line shows the finished artifact. To see the stages, call the
pipeline directly. Save this as `/tmp/trace.py`, outside the repository so it
never gets committed:

```python
import sys
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore

claim = sys.argv[1]
context = ClaimContext(
    jurisdiction=JurisdictionCode("ZZ"),
    language=LanguageCode("en"),
    stated_at=date(2022, 1, 1),
)
store = RetrievalStore(":memory:")
run = verify(claim, context, PackRegistry.from_directory("packs/fixture"),
             build_fixture_custodians(), store)

print("Stage 2, decomposition, and Stage 6, element verdicts:")
for element in run.elements:
    status = element.status.value if element.status else "-"
    print(f"  {element.kind.value:14} {status:14} {element.fragment!r}")

decision = run.decision
if decision and decision.routed:
    print(f"Stage 4, routing: {decision.measure.name} -> {decision.custodian_id}")
else:
    print("Stage 4, routing: no route")

print(f"Stage 8, proposed verdict: {run.artifact.verdict.label.value}")
store.close()
```

Run it on the worked example:

```
PYTHONPATH=. python3 /tmp/trace.py "prices rose over the last three years due to governmental incompetence"
```

```
Stage 2, decomposition, and Stage 6, element verdicts:
  direction      verified       'rose'
  time_period    verified       'over the last three years'
  causal         out_of_scope   'due to'
  opinion        out_of_scope   'incompetence'
Stage 4, routing: ZZ Price Index -> zzstat
Stage 8, proposed verdict: misleading
```

Notice what happened. The claim was split into four elements, each anchored
to words the claimant actually used. The causal and evaluative ones were
marked out of scope before any custodian was asked, and they can never become
verified. The measure was bound, routed to its custodian, and the two
remaining elements verified. They still compose into a claim that doesn't
hold under every admissible baseline, which is why the proposal is
*misleading* rather than *accurate*.

Now run it on a claim no pack covers:

```
PYTHONPATH=. python3 /tmp/trace.py "the earth is flat"
```

```
Stage 2, decomposition, and Stage 6, element verdicts:
Stage 4, routing: no route
Stage 8, proposed verdict: insufficient_data
```

No elements, no route, and an answer rather than an error.

Open `engine/pipeline.py` and find `verify`. It calls one module per stage and
decides nothing itself. The
[stage-to-module table](reference/codebase.md#stages-and-the-modules-that-own-them)
tells you which file owns each rule you just watched.

## Step 3 — Break the figure rule on purpose

Every number in every output must come from a retrieval. You're going to put
one in that didn't. Open `engine/render/artifact.py`, find the line

```python
        payload.line("ROBUSTNESS SWEEP")
```

and change it to

```python
        payload.line("ROBUSTNESS SWEEP (10 tests)")
```

It looks harmless. Now verify a claim:

```
PYTHONPATH=. python3 cli/verify.py "prices rose in 2021" --jurisdiction ZZ --store :memory:
```

The command does not print an artifact with a warning. It raises:

```
engine.render.figures.UnsourcedFigure: output contains 1 numeric literal(s) with no retrieval behind them: ['10']. Every figure in any output must originate from a recorded retrieval against a named custodian (§3)
```

A count of tests is computed, not retrieved, and the render cannot tell a
harmless count from an invented statistic, so it refuses both. Run the
criterion that owns this rule:

```
python3 -m pytest tests/conformance/test_ac07.py -q
```

It fails. This is what "a criterion fails" means here: the change is wrong,
and the fix is to take the numeral out, never to loosen the scan. Restore the
file:

```
git checkout engine/render/artifact.py
```

## Step 4 — Break an architectural boundary on purpose

Verification must be statically unable to reach the network. Open
`engine/verification/tolerance.py` and add this line directly under
`from __future__ import annotations`:

```python
import urllib.request
```

Nothing calls it. Run the conformance suite anyway:

```
python3 -m pytest tests/conformance -q
```

Two tests fail, not one:

```
FAILED tests/conformance/test_ac14.py::test_no_verification_module_can_reach_a_network_primitive[engine.verification.element_verdict]
FAILED tests/conformance/test_ac14.py::test_no_verification_module_can_reach_a_network_primitive[engine.verification.tolerance]
```

The import graph is built from source, not from what happened to run, and it
is transitive: `element_verdict` imports `tolerance`, so it now reaches the
network too. An import that no test exercises is exactly the latent failure
this guards against. Restore the file:

```
git checkout engine/verification/tolerance.py
```

When a real change needs a network client, it goes in the composition root
(`cli/`) or in a custodian adapter, imported lazily. Never relax the graph.
[Why the code is shaped this way](architecture.md#the-engine-cannot-reach-the-network)
explains the reasoning.

## Step 5 — Write a regression test, and prove it can fail

Create `tests/unit/test_my_first_regression.py`:

```python
"""My first regression test: a plain price claim routes, and loses nothing."""

import pathlib
from datetime import date

from engine.codes import JurisdictionCode, LanguageCode
from engine.context import ClaimContext
from engine.custodians.fixture import build_fixture_custodians
from engine.packs.registry import PackRegistry
from engine.pipeline import verify
from engine.store.events import RetrievalStore

PACKS = pathlib.Path(__file__).resolve().parents[2] / "packs" / "fixture"
CLAIM = "prices rose in 2021"


def test_a_plain_price_claim_routes_to_the_price_index() -> None:
    context = ClaimContext(
        jurisdiction=JurisdictionCode("ZZ"),
        language=LanguageCode("en"),
        stated_at=date(2022, 1, 1),
    )
    store = RetrievalStore(":memory:")
    try:
        run = verify(CLAIM, context, PackRegistry.from_directory(PACKS),
                     build_fixture_custodians(), store)
    finally:
        store.close()

    assert run.decision is not None and run.decision.routed
    assert run.decision.measure.name == "ZZ Price Index"
    assert "Nothing was discarded." in run.artifact.render()
```

Run it:

```
python3 -m pytest tests/unit/test_my_first_regression.py -q
```

It passes. That alone proves little, since a test that asserts nothing
passes too. Change `CLAIM` to `"badger population rose in 2021"`, a claim with
no measure in the fixture pack, and run it again. It fails on
`run.decision.routed`, which is the assertion you meant it to make. Now you
know it can fail, and for the right reason.

This was practice, so delete the file:

```
rm tests/unit/test_my_first_regression.py
```

In real work you'd keep the test and restore the passing claim.
[Add a regression test](how-to/add-a-regression-test.md) covers where each
kind of test belongs.

## Step 6 — Finish green

```
git status
python3 -m pytest tests/ -q
```

The tree is clean and the suite is green, exactly as you started. Before any
real push you run more than the suite. [Run the full gate](how-to/run-the-full-gate.md)
lists all of it.

---

## What you learned

- `engine/pipeline.py` orchestrates, and each rule lives in the stage module
  that owns it.
- The figure rule raises at the render boundary, so a harmless-looking count
  crashes the render rather than slipping through.
- Architectural boundaries are asserted on the static import graph, which is
  transitive and doesn't care what your tests happen to run.
- A test earns trust by failing once, for the right reason.

## Where to go next

- [Contribute a change](how-to/contribute-a-change.md): the workflow for real
  changes, and what to do when a criterion fails.
- [Codebase reference](reference/codebase.md): layout, stage map, import
  rules and test suite.
- [Why the code is shaped this way](architecture.md).
- [Fuzz claim shapes](how-to/fuzz-claim-shapes.md), which is worth running on
  any change to decomposition, derivation or rendering.
