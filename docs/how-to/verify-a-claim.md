# How to verify a claim

For the full list of flags, see the [CLI reference](../reference/cli.md). If you
have never run the engine before, do the [tutorial](../tutorial.md) first.

## Verify a claim

```
PYTHONPATH=. python3 cli/verify.py "<claim text>" --jurisdiction ZZ
```

The claim goes in quotes. `--jurisdiction` takes a two-letter code and is a
*hint*: the engine prefers a jurisdiction the claim names itself, and falls back
to the hint only when the text does not resolve.

## Set the date the claim was made

```
PYTHONPATH=. python3 cli/verify.py "<claim text>" \
  --jurisdiction ZZ --stated-at 2021-06-01
```

Defaults to today. Set it whenever you know it: tolerance bands and the
continuity check are both indexed on when the claim was made, so an
approximate date produces a confident answer to a different question.

## Get structured output

```
PYTHONPATH=. python3 cli/verify.py "<claim text>" --jurisdiction ZZ --json
```

Emits the artifact as JSON, including the discard ledger, the flip table, the
citations, and the derived elements.

## Record who said it

```
PYTHONPATH=. python3 cli/verify.py "<claim text>" \
  --jurisdiction ZZ --claimant "A. Person" --venue "A broadcast"
```

Attribution is displayed and stored, and **never** reaches routing. The
verification path has no import route to it, so who said something cannot
influence what the record says.

## Use a different pack directory

```
PYTHONPATH=. python3 cli/verify.py "<claim text>" \
  --jurisdiction ZZ --packs /path/to/packs
```

Defaults to `packs/fixture`.

## Verify a claim in another language

```
PYTHONPATH=. python3 cli/verify.py "<claim text>" \
  --jurisdiction ZZ --language en
```

The pack must declare a lexicon for that language. If it does not, the engine
falls back to English, and decomposition will under-fire silently on the actual
language — an under-decomposed claim looks exactly like a simpler claim.

---

## Troubleshooting

### The verdict is "Insufficient Data" and I expected a real answer

Read the rationale line under the verdict — it names which of these happened.

| Rationale mentions | Meaning | Fix |
|---|---|---|
| no jurisdiction could be established | No pack is loaded for that jurisdiction | [Add a pack](add-a-jurisdiction-pack.md), or check `--jurisdiction` |
| nearest available measure | The pack has no measure for what the claim is about | Add the measure to the pack |
| did not pass the scope gate | The claim is evaluative, predictive, or causal throughout | Nothing to fix; this is the designed answer |

Every real-world jurisdiction currently returns the first of these, because no
real pack is admitted. See the [roadmap](../plan.md).

### The verdict is "Indeterminate" and the sweep did not run

The measure declares no `admissible_baselines` or `admissible_windows`, so the
robustness sweep has nothing to vary. Verdicts on that measure cap at
Indeterminate until the pack declares them — from the custodian's own published
comparisons, not from a maintainer's judgement.

### The render fails with `UnsourcedFigure`

Output contains a numeral with no retrieval behind it. This fails the render
rather than warning, deliberately. Either the reconstruction carries a figure
that is not in any citation, or prose is quoting a number it should not be.

### The render fails with `NotQuotedFromClaim`

Something was passed as quoted from the claim but is not a verbatim span of it.
Only real spans of the claim under examination may carry a numeral without a
retrieval.

### Exit code 2 with `error: ...`

A malformed `--language` (ISO 639, lowercase) or `--stated-at` (ISO date).

### I passed `--jurisdiction` and still got "no jurisdiction could be established"

Check the case. Codes are two **uppercase** letters, and anything of another
shape — `zz`, a country name, a venue string — resolves to no jurisdiction at
all rather than erroring. The run then returns Insufficient Data and exits `0`,
which looks identical to a country the engine genuinely does not cover.

The strictness is what stops a venue string becoming a jurisdiction, so it is
worth the papercut. Check the code before concluding a pack is missing.
