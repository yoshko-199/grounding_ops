# How to read back a stored verification

For the full list of flags, see the [CLI reference](../reference/cli.md).

## Find the claim id

`cli/verify.py` prints one after every run, unless the store is `:memory:`:

```
PYTHONPATH=. python3 cli/verify.py "<claim text>" --jurisdiction ZZ
...
claim id: 5b2bf3c6-6e30-42f7-baf2-771806b558ff  (pass to cli/show.py to read this back)
```

`--json` output carries the same value under `"claim_id"`.

## Read it back

```
PYTHONPATH=. python3 cli/show.py 5b2bf3c6-6e30-42f7-baf2-771806b558ff
```

Reads the claim, its elements, its discard ledger, its latest verdict, its
latest reconstruction, its citations, its sweep rows, and its derived
elements — from the store, not from a fresh run. Nothing is re-verified: no
custodian is contacted, no route is resolved, no figure is recomputed. If the
writer and the schema disagree about what a verification produces, this
command is what would show it, because it has no other way to get the answer
right.

Add `--json` for the same content as structured data, or `--store PATH` to
point at a database other than the default.

## Why this exists

Every verification is written to the store by default (`cli/verify.py`'s
`--store`, documented in the [CLI reference](../reference/cli.md)). Before
this command, that data had no reader: a claim's elements, verdict,
reconstruction and sweep rows accumulated in the database and nothing ever
looked at them again. §8 of the specification calls `element_set_hash` the
thing that makes "the pure-function property checkable after the fact" —
that two reconstructions sharing a hash must share their text. "Checkable
after the fact" needs an "after the fact" to check, which is what reading
the claim back on a later run, from a different process, is for.

## What is not yet true

This is a read of the *current* state, not a history. `reconstructions` and
`verdicts` are append-only tables — a claim re-verified against updated
retrievals would add rows rather than overwrite them — and `cli/show.py`
prints only the latest of each. There is no `--revision` flag yet, and no
command re-verifies an existing claim by id rather than starting over from
its text. Both are natural next steps; neither exists today.

Citations are read back too, but only as much as the schema currently
records: which retrievals a claim's artifact cited, in order, not which
specific element each one verified. A retrieval can be reused by many claims
inside its TTL (`docs/spec/claim-verification-engine.v0.5.md` §8), so that
finer link is a many-to-many relationship the schema does not yet carry.
