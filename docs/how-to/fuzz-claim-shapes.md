# How to fuzz claim shapes

Run this after touching decomposition, derivation, element verdicts, or
rendering. It finds the defects the acceptance criteria cannot, because it asks
a different question: not *does this guarantee hold*, but *does the engine stay
coherent on a claim nobody wrote down*.

Three defects have been found this way or by the hand-run that motivated it,
each with the conformance suite green.

## Run it

```
python3 scripts/fuzz_shapes.py             # a bounded sample
python3 scripts/fuzz_shapes.py --all       # every shape, a few seconds
python3 scripts/fuzz_shapes.py --seed 7    # a different sample
```

Exit `0` if nothing was violated, `1` otherwise. CI runs `--all`.

## Read a failure

```
[period-never-contradicted] 'unemployment fell in 2021'
    period 'in 2021' came back contradicted, which means it was compared
    as a figure
```

The claim shown is **already shrunk** — the shortest one still exhibiting the
defect, with irrelevant slots removed. That is usually the diagnosis: *"unemployment
fell in 2021"* says what a twelve-word claim with six things in it does not.

Reproduce with the `--count` and `--seed` printed at the end of a failing run.

## What it checks

Properties that hold for every claim whatever the verdict. It has no ground
truth and does not judge whether a verdict is *right* — pretending otherwise
would make it a second, worse implementation of the thing it tests.

| Invariant | Catches |
|---|---|
| `render-survives` | A claim whose own figures crash the renderer |
| `verdict-present` | An artifact with no answer |
| `period-never-contradicted` | A time period compared as if it were a figure |
| `ledger-agrees-with-routing` | An artifact contradicting itself about its own process |
| `spans-resolve` | An element whose span does not resolve to its fragment |
| `derived-spans-resolve` | A derived element anchored to nothing |
| `derived-introduces-no-new-word` | World knowledge entering a derived element |
| `derived-texts-are-distinct` | Two operations collapsing onto the same span |
| `discarded-content-stays-out` | Removed content reappearing in the reconstruction |
| `determinism` | The same claim rendering differently twice |

## Add an invariant

Put it in `plugins/shapes/invariants.py`, returning a reason string or `None`,
and add it to `INVARIANTS`.

**Give it a failure story.** An invariant with no defect behind it tends to
encode what the implementation happens to do rather than what the spec
requires, and then fails on every correct change. That is not hypothetical: the
first determinism check asserted `element_set_hash` was stable across runs. It
is not, by design — the hash covers element ids, which are fresh per run — so
the check reported every claim as a violation and buried the two real findings
underneath itself.

**Then plant the defect and watch it catch it.** `tests/conformance/test_shape_invariants.py`
has a negative control per invariant. A fuzzer that has never been seen to fail
is indistinguishable from one whose checks all return `None`.

## Add a claim shape

`plugins/shapes/shapes.py` holds the slots. Adding an alternative multiplies
the space rather than adding one case, which is the point — a period containing
a year *and* a superlative *and* a causal tail is a combination nobody writes
by hand.

Keep new fragments concrete and tied to the fixture pack's measures. The goal
is to exercise the engine against a pack that can actually retrieve, not to
test the binder's tolerance for nonsense.
