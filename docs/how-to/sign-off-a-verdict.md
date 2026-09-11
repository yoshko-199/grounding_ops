# How to sign off a verdict

Every artifact is marked `UNCONFIRMED` until a person signs off the
claim-level verdict. Only the verdict — the gate cannot reach an element
status, a retrieval, the discard ledger, the flip table, or a pack.

For the full flag list, see the [CLI reference](../reference/cli.md).

## The real workflow: sign off a claim you verified earlier

`cli/verify.py` persists every claim it verifies and prints a claim id.
`cli/signoff.py` reads that claim's proposed verdict from the same store,
and writes the decision back — this is what actually closes the loop, rather
than exercising the gate on a label typed by hand.

### See what is awaiting review

```
PYTHONPATH=. python3 cli/signoff.py list
```

Prints one line per claim whose current verdict is still proposed: its id,
its label, and the start of its text. Nothing is awaiting review after you
have signed off everything currently open.

### Confirm one by id

```
PYTHONPATH=. python3 cli/signoff.py confirm \
  --claim-id <ID> --reviewer "A. Reviewer"
```

The rationale in the output is the pipeline's own — not a placeholder —
because it was read from the stored verdict rather than typed on the command
line. `cli/show.py <ID>` afterwards shows the verdict's state as `confirmed`.

### Amend one by id

```
PYTHONPATH=. python3 cli/signoff.py amend \
  --claim-id <ID> --reviewer "A. Reviewer" --label indeterminate \
  --rationale "the flip table is ambiguous on the intended baseline"
```

`--rationale` is required and the gate refuses without it. A reviewer may
overrule the pipeline; they may not do it silently, and the rationale is
bound by the same anti-fabrication rule as any other output — it may not
introduce a figure that no retrieval supports.

### A claim already signed off cannot be signed off again

```
PYTHONPATH=. python3 cli/signoff.py confirm --claim-id <ID> --reviewer "A. Reviewer"
error: no open proposed verdict for claim id '<ID>'. Either it was never
verified into this store, or it has already been signed off
```

§9.1: a decided verdict cannot be revisited in place. The stored row from
the first decision is not overwritten — see
[the CLI reference](../reference/cli.md#clisignoffpy) for what
persists and why it is a new row rather than an edit.

### Point at a different store

`--claim-id` and `list` both take `--store PATH`, matching whatever
`cli/verify.py --store` the claim was verified against. A claim verified into
`:memory:` cannot be signed off this way — nothing survived the process to
read back.

## The ad-hoc path: exercise the gate without a store

```
PYTHONPATH=. python3 cli/signoff.py confirm \
  --reviewer "A. Reviewer" --proposed misleading
```

`--proposed LABEL` supplies the label directly, with a placeholder rationale,
and writes nothing anywhere. Useful for trying the gate's rules — an
amendment with no reason, a rationale that smuggles in a figure — without
verifying a claim first. `amend` and `reject` take the same flag:

```
PYTHONPATH=. python3 cli/signoff.py amend \
  --reviewer "A. Reviewer" --proposed misleading --label indeterminate \
  --rationale "the flip table is ambiguous on the intended baseline"

PYTHONPATH=. python3 cli/signoff.py reject \
  --reviewer "A. Reviewer" --proposed misleading
```

Pass exactly one of `--claim-id` or `--proposed` — never both, and never
neither.

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

### `error: pass exactly one of --claim-id or --proposed`

The two ways of naming a proposal are mutually exclusive. Use `--claim-id`
for a claim you actually verified; use `--proposed` only to exercise the
gate in isolation.

### `error: no open proposed verdict for claim id ...`

Either the id is wrong, the claim was verified into a different `--store`
(or `:memory:`), or it has already been signed off — `list` shows what is
still open.

### I want to correct an element status, not the verdict

You cannot, and the omission is deliberate. A reviewer who could reach past the
verdict into the evidence could make the evidence agree with a conclusion they
had already reached, and the artifact would still look fully cited.

If an element status is wrong, the cause is the pack or the retrieval. Fix it
there and re-run, so the correction lands in the citation trail rather than on
top of it.
