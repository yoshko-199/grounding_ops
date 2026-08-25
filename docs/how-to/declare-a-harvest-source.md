# How to declare a harvest source

The harvester collects **candidate claims** — things people said that somebody
might want checked. It never collects evidence. Nothing under `engine/` can
reach it, and the conformance suite fails if that ever changes.

For every field, see the [source schema](../reference/source-schema.md). For
what a source must establish before you collect from it at all, see
[source admission](../../sources/README.md).

## 1. Create the file

One TOML file per publication, in `sources/`:

```
sources/example.toml
```

## 2. Declare the source

```toml
[source]
id = "example"
name = "Example publication"
accounts = ["alpha", "beta"]
cadence = "daily"
languages = ["en"]
date_precision = "exact"

enabled = false
disabled_reason = """
Not yet reviewed for collection.
"""
```

`accounts` are the handles, feeds, or sections to scan. One source, many
accounts.

`cadence` becomes the fetch TTL. Expired entries are re-fetched, never served.

**`date_precision` is the field most often got wrong.** Omitting it is safe:
every record is then capped at `approximate`, because a well-formed timestamp
whose provenance the source does not state is not an exact date. Declare
`exact` only against the source's own statement that it establishes the time of
the original utterance.

A record that is not `exact` will refuse to supply a `stated_at`. That is
correct — tolerance bands and continuity are indexed on when the claim was
made, and an approximate date there answers a different question confidently.

## 3. Declare the backends, in preference order

Backends are alternative **transports to the same account** — a mirror, a JSON
endpoint for a page you were already reading. They are tried in order until one
answers, and the first record wins on deduplication.

A JSON endpoint:

```toml
[[backend]]
kind = "json"
url_template = "https://feeds.example.com/{account}/claims.json"
items_path = "data.items"
text_field = "body"
url_field = "permalink"
date_field = "published"
```

An RSS feed — no parse fields needed, the element names are fixed:

```toml
[[backend]]
kind = "rss"
url_template = "https://feeds.example.com/{account}/rss"
```

A server-rendered page with its payload in a script tag:

```toml
[[backend]]
kind = "embedded-json"
url_template = "https://www.example.com/{account}"
script_id = "__NEXT_DATA__"
items_path = "props.pageProps.items"
text_field = "statement"
url_field = "href"
date_field = "statedOn"
date_format = "%d/%m/%Y"
```

`{account}` is substituted per account. `items_path` is a dotted path to the
list; `text_field` and friends are dotted paths within each item.

## 4. Check what you are allowed to fetch

Read the publication's `robots.txt` before enabling anything. A site commonly
permits its pages and disallows its data endpoints — in which case there is no
admissible machine-readable surface, and the answer is not to scrape the pages
instead.

## 5. Dry-run it

```
python3 scripts/harvest_corpus.py --dry-run --source example \
  --allow-disabled example
```

Nothing is written. You get one line per account with the backend that
answered, and every rung of the ladder that did not:

```
  ok       example/alpha via json — 12 claim(s)
  NO REACH example/beta via - — 0 claim(s)
             tried json: transport failed: ...
             tried rss: ... answered 503; whether anything is there is unknown
```

Read the failed rungs even when a later one succeeded. A first backend failing
quietly behind a working second one is a source about to go dark.

## 6. Enable it and harvest

Once you have decided collection is appropriate:

```toml
enabled = true
```

Then:

```
python3 scripts/harvest_corpus.py --source example
```

Records merge into `corpus/claims.jsonl` by identity, so a re-harvest updates a
corrected claim rather than adding a second copy of it.

---

## Troubleshooting

### `source declarations did not load`

The message names the file and the problem.

| Message mentions | Cause |
|---|---|
| gives no reason | `enabled = false` with no `disabled_reason` |
| unknown kind | `kind` is not `rss`, `json`, or `embedded-json` |
| needs an items_path / text_field | A JSON-shaped backend is missing its parse fields |
| declares no accounts / no backends | An empty list |
| duplicate source id | Two files claim the same `id` |

### Exit code 2, "nothing was scanned"

Every selected source is disabled. Name it in `--allow-disabled`, one at a
time — the reason a source is off is specific to it, and a blanket override is
a way of not reading the reason.

### Exit code 1

At least one account could not be reached. Distinct from an account that
answered and has nothing, which exits 0. A harvester that treated both alike
would run for weeks against a dead feed while its logs looked like a quiet one.

### Everything is `NO REACH` with `403`

Your network policy is blocking the host, not the site refusing you. Check
whether outbound access is allowlisted before assuming the source is at fault.

### A backend reports `reached-empty` but the page clearly has content

The parse fields do not match the payload. `items_path` resolving to nothing or
to a non-list reports as *unreachable*; resolving to an empty list, or to items
with no text at the `text_field`, reports as *reached-empty*.

### Claims appear twice

Deduplication is by URL where one exists. If the backend supplies no
`url_field`, records fall back to a text hash, and a page that renders each item
twice — a carousel, for instance — will yield duplicates that differ in
whitespace.
