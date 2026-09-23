# How to add a regression test

Where a new test belongs, how to write it with what already exists, and how to
prove it can fail. For the lesson version, see
[step 5 of the contributor tutorial](../tutorial-contributor.md#step-5--write-a-regression-test-and-prove-it-can-fail).

## Choose the kind of test

| You are protecting | Put it in | Notes |
|---|---|---|
| One module's behaviour: a writer, a CLI flag, a web route, the pack loader | `tests/unit/test_<area>.py` | Build what you need in the test, or copy the helpers at the top of a neighbouring file. Unit tests have no shared fixtures |
| An acceptance criterion, on a path it didn't cover before | The criterion's own file, `tests/conformance/test_acNN.py` | Add assertions to the existing file. Never create a new criterion file without a specification change that numbers it |
| A new branch that produces an artifact | `tests/conformance/test_render_paths.py` | Add a claim to `CLAIMS`, named for the branch it covers, so every branch is rendered at least once |
| A property that should hold for every claim of some shape | A fuzz invariant or shape in `plugins/shapes/` | See [fuzz claim shapes](fuzz-claim-shapes.md). This is how you cover a class of claims rather than one |
| A defect found by a real claim | A unit or conformance test on the **shortest** claim that reproduces it | The fuzzer shrinks failures for you. Record where the claim came from in the docstring |

## Write it

Conformance tests get these fixtures from `tests/conformance/conftest.py`:

| Fixture | Is |
|---|---|
| `registry` | A `PackRegistry` loaded from `packs/fixture` |
| `pack` | The `ZZ` pack from that registry |
| `lexicon` | The pack's English lexicon |
| `adapters` | The fixture custodian adapters |
| `store` | An in-memory `RetrievalStore`, closed after the test |
| `context` | A `ClaimContext` for `ZZ`, English, stated on `2022-01-01` |

```python
from engine.pipeline import verify


def test_the_thing_you_are_protecting(registry, context, adapters, store) -> None:
    run = verify("prices rose in 2021", context, registry, adapters, store)
    assert ...
```

Write the docstring for the next reader. Say what would go wrong without the
test and, if a real defect prompted it, what that defect was. Most test
docstrings in this repository explain the failure mode, not the assertion.

A rule about what a browser sends needs a real browser to check it, not
only a unit test. A test that builds request headers by hand tests the
headers you imagine a browser sends. The web UI's cross-origin check passed
every such test while refusing every form a real Chrome posted, because the
page's referrer policy made the browser send `Origin: null`. Keep the unit
test, and also drive the page once in a browser.

Assert on what a reader would see, not on incidentals. A bare number such as
`"403"` in a rendered page can match inside a uuid, and a CSS class name can
match inside the stylesheet. Assert on a phrase, or on an element such as
`class="form-problem"`, not on a substring that could appear by accident.

## Prove it can fail

Before you commit, break the code the test protects and watch the test fail
for the reason you meant:

1. Change the code under test so the defect is back: remove the check,
   re-introduce the bug, or point the test at a claim that shouldn't pass.
2. Run just your test, for example
   `python3 -m pytest tests/unit/test_serve.py -q -k cross_origin`, and read
   the failure. It should name the property you're protecting, not some
   unrelated error.
3. Restore the code (`git checkout <file>`) and run it again: green.

If you can't make it fail, it isn't testing what you think. Reshape it until
it can. Mention in the commit message how you proved it.

## Then

[Run the full gate](run-the-full-gate.md) before pushing.
