# How to run the full gate

Run this before every push. The test suite alone is not the gate: two
regression claims and a harvester assertion have caught defects the suite
missed. CI (`.github/workflows/checks.yml`) runs all of it again on every
push, but finding a failure locally costs minutes and finding it in CI costs a
round trip.

Run everything from the repository root.

## 1. The test suite

```
python3 -m pytest tests/ -q
```

This covers the conformance suite (one file per acceptance criterion, plus the
static import-graph assertions) and the unit tests. **Pass means** every test
passed, and the summary line mentions nothing skipped. A few tests can skip
themselves, for example when `packs/live` is absent or a test claim stops
routing. None does in a full checkout today, so a skip in the summary means
something changed that you need to explain. Adding a skip
or an expected-failure marker to get green is weakening a test.

## 2. Document consistency

```
python3 scripts/check_spec.py -v
```

**Pass means** the last line reads `All checks passed (6 groups).` It fails on
a broken link or anchor, an acceptance criterion without a test, a statistic
embedded in prose, or an entry-point document that doesn't point at the
current spec version. If you changed any document, this is the check most
likely to catch you.

## 3. Every claim shape

```
python3 scripts/fuzz_shapes.py --all
```

**Pass means** `<N> shapes checked, no violations`. On a violation it prints
the shortest claim that still reproduces it. See
[fuzz claim shapes](fuzz-claim-shapes.md) for how to read one.

## 4. The two regression claims

```
PYTHONPATH=. python3 cli/verify.py "prices rose over the last three years due to governmental incompetence" --jurisdiction ZZ --packs packs/fixture --store :memory:
PYTHONPATH=. python3 cli/verify.py "you dont see a curve therfore the earth is flat" --jurisdiction ZZ --packs packs/fixture --store :memory:
```

**Pass means:**

- The first claim is **MISLEADING**, with a reconstruction ("Over the last
  three years ZZ Price Index rose …") and the ledger showing *due to* and
  *incompetence* removed.
- The second is **INSUFFICIENT DATA**, with a derived element whose operation
  is `inferential-discharge`.

`--store :memory:` keeps these runs out of your local store.

## 5. The harvester reaches nothing by default

```
python3 scripts/harvest_corpus.py --dry-run; echo "exit $?"
```

**Pass means** `exit 2`: the shipped configuration has every source
disabled, so nothing was scanned. An exit of `0` means a source acquired a live
default, and that is a failure even though nothing crashed.

## All at once

```
python3 -m pytest tests/ -q \
 && python3 scripts/check_spec.py -v \
 && python3 scripts/fuzz_shapes.py --all \
 && PYTHONPATH=. python3 cli/verify.py "prices rose over the last three years due to governmental incompetence" --jurisdiction ZZ --packs packs/fixture --store :memory: | grep -A1 '^VERDICT' \
 && PYTHONPATH=. python3 cli/verify.py "you dont see a curve therfore the earth is flat" --jurisdiction ZZ --packs packs/fixture --store :memory: | grep -E 'INSUFFICIENT|inferential' \
 ; python3 scripts/harvest_corpus.py --dry-run >/dev/null 2>&1; echo "harvester exit $? (must be 2)"
```

Read the two regression outputs yourself. A `grep` that matched only proves
the word appeared, not that the artifact is right.

## If something fails

Don't push, and don't adjust the check. Read
[when a criterion fails](contribute-a-change.md#when-a-criterion-fails).
