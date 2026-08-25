# How to sign off a verdict

Every artifact is marked `UNCONFIRMED` until a person signs off the
claim-level verdict. Only the verdict — the gate cannot reach an element
status, a retrieval, the discard ledger, the flip table, or a pack.

For the full flag list, see the [CLI reference](../reference/cli.md).

## Confirm the proposed label

```
PYTHONPATH=. python3 cli/signoff.py confirm \
  --reviewer "A. Reviewer" --proposed misleading
```

Prints the signed verdict with `exportable: True`.

## Change the label

```
PYTHONPATH=. python3 cli/signoff.py amend \
  --reviewer "A. Reviewer" --proposed misleading --label indeterminate \
  --rationale "the flip table is ambiguous on the intended baseline"
```

`--rationale` is required for an amendment and the gate refuses without it. A
reviewer may overrule the pipeline; they may not do it silently.

The rationale is bound by the same anti-fabrication rule as any other output:
it may not introduce a figure that no retrieval supports.

## Reject the verdict

```
PYTHONPATH=. python3 cli/signoff.py reject \
  --reviewer "A. Reviewer" --proposed misleading
```

Nothing becomes exportable.

## Valid labels

`accurate`, `substantially_inaccurate`, `misleading`, `false`,
`indeterminate`, `insufficient_data`.

Pass them to `--proposed` and `--label`.

---

## Troubleshooting

### `gate refused: ...`

The gate rejected the action. Most often an amendment with no rationale, or one
whose rationale carries an unsourced figure.

### `error: --label is required for amend`

`amend` needs the new label. `confirm` and `reject` do not take one.

### I want to correct an element status, not the verdict

You cannot, and the omission is deliberate. A reviewer who could reach past the
verdict into the evidence could make the evidence agree with a conclusion they
had already reached, and the artifact would still look fully cited.

If an element status is wrong, the cause is the pack or the retrieval. Fix it
there and re-run, so the correction lands in the citation trail rather than on
top of it.
