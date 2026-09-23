# Use the web UI

For when you would rather verify claims and read them back in a browser than
in a terminal. The web UI runs the same pipeline, packs and store as
[`cli/verify.py`](../reference/cli.md#cliverifypy), so a claim verified in one
can be read back in the other.

## Start it

From the repository root:

```
PYTHONPATH=. python3 cli/serve.py
```

or, after `pip install -e .`, just `grounding-serve`. It prints the address:

```
grounding web UI on http://127.0.0.1:8000/  (Ctrl-C to stop)
```

Open that address. It listens on this machine only. Pass `--port 0` if `8000`
is taken; the startup line then prints the port it picked.

To verify against the Israel pack instead of the fixture jurisdiction, point
it at that directory:

```
PYTHONPATH=. python3 cli/serve.py --packs packs/live
```

## Verify a claim

1. Type or paste the claim into **Claim**, exactly as it was made. Do not
   correct it first: a corrected claim is a different claim.
2. Choose a **Jurisdiction**, or leave it on *No hint* to let the engine
   resolve one from the claim text.
3. Set **Language** (an ISO code, `en` by default) and, if you know it,
   **Stated on**, the date the claim was made. Tolerance bands and the
   continuity check are indexed on that date, so an unknown date defaults to
   today.
4. **Claimant** and **Venue** are optional. They are recorded and displayed,
   and never reach verification.
5. Press **Verify**.

The page shows the full artifact: the original claim, the reconstruction and
its discard ledger in one frame, the verdict, the robustness sweep, the
citations, the routing, and any derived elements. The sections and their order
match the text output, because both come from the same artifact.

**Insufficient Data is an answer.** It appears in the same verdict container as
every other label, with no warning styling, because it means no custodian of
record covers the claim, not that something went wrong.

A problem with what you submitted, such as a date that is not a date or a
language that is not a code, is shown above the form, with your input kept,
and never as a verdict.

## Read a claim back

Each result page shows its claim id and a **read back the stored record** link.
The read-back page re-renders what the store holds for that claim, with no
retrieval and no re-routing, like
[`cli/show.py`](read-back-a-stored-verification.md). Bookmark it, or reach any
stored claim at `/claim/<id>`.

## What it will not do

- **It is not a server for other people.** It binds to `127.0.0.1` and has no
  login. `--host` can widen that, and nothing then authenticates anyone.
- **It refuses forms posted from other sites.** Otherwise any web page open
  in the same browser could write to your local store.
- **It will not run on `--store :memory:`.** Each request opens its own
  connection, so an in-memory store would forget every claim before you could
  read it back.
- **It adds nothing to the artifact.** There are no summaries, counts or share
  buttons, and nothing is truncated or collapsed. The reconstruction is never
  shown without its ledger.
