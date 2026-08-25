# Source schema

Every field of a harvest source TOML file. One file per publication, in
`sources/`.

Sources feed the [harvest plugin](../../plugins/harvest/__init__.py), which
collects **candidate claims** and never evidence. To write one, follow
[declare a harvest source](../how-to/declare-a-harvest-source.md).
[`sources/fixture.toml`](../../sources/fixture.toml) is a commented example.

---

## `[source]`

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string | yes | — | Unique across the directory |
| `name` | string | no | `""` | Human-readable name |
| `accounts` | list of string | yes | — | Handles, feeds, or sections to scan. Must be non-empty |
| `cadence` | string | no | `daily` | Publication frequency. Becomes the fetch TTL |
| `languages` | list of string | no | `[]` | ISO 639 codes the source publishes in |
| `date_precision` | string | no | `unknown` | `exact`, `approximate`, or `unknown` |
| `enabled` | bool | no | `false` | Whether a plain run will scan it |
| `disabled_reason` | string | conditional | `""` | Required when `enabled = false` |
| `notice` | string | no | `""` | Free text; anything a reader should know |
| `metadata` | table | no | `{}` | Free-form |

### `date_precision`

Caps the precision of every record the source yields, applied at parse time
rather than trusted to the parser — a feed emits a well-formed timestamp
whether or not the publisher established it from the original utterance, and
only the declaration knows which.

| Value | Effect |
|---|---|
| `exact` | Records keep their parsed date and can supply a `stated_at` |
| `approximate` | Records keep their date; `stated_at()` raises |
| `unknown` | Records with a parsed date are downgraded to `approximate`; records without one keep no date at all |

Omitting the field is the safe default. A record that is not `exact` refuses to
supply a `stated_at`, because tolerance bands and continuity are indexed on
when the claim was made and an approximate date there answers a different
question confidently.

### `disabled_reason`

Required whenever `enabled = false`. A source switched off without a recorded
reason gets switched back on by the next person who notices it is off.

### `cadence` values that map to a TTL

`continuous`, `hourly`, `daily`, `weekly`, `monthly`. Substring match; an
unrecognised cadence gets the shortest TTL.

## `[[backend]]`

Ordered. Backends are alternative transports **to the same account**, tried in
sequence until one answers. At least one is required.

| Field | Type | Required | Description |
|---|---|---|---|
| `kind` | string | yes | `rss`, `json`, or `embedded-json` |
| `url_template` | string | yes | `{account}` is substituted per account |
| `items_path` | string | conditional | Dotted path to the item list. Required for `json` and `embedded-json` |
| `text_field` | string | conditional | Dotted path to the claim text within an item. Required for `json` and `embedded-json` |
| `url_field` | string | no | Dotted path to the item's permalink |
| `date_field` | string | no | Dotted path to the item's date |
| `date_format` | string | no | `strptime` format. ISO is tried when absent |
| `script_id` | string | conditional | `id` of the script tag holding the payload. Required for `embedded-json` |

### `kind`

| Value | Reads |
|---|---|
| `rss` | An RSS feed. Element names are fixed (`item`, `description`, `title`, `link`, `pubDate`), so no parse fields are needed |
| `json` | A JSON endpoint, navigated by `items_path` and the field paths |
| `embedded-json` | A rendered page with a JSON payload in a `<script id="...">` tag |

The set is closed. There is deliberately no model- or search-backed transport:
that would put a model prior on the intake path, and intake feeds claims that
are later quoted verbatim in an artifact carrying custodian names.

### Dotted paths

`items_path` and the field paths resolve through nested objects, and through
list indices given as digits: `props.pageProps.items`, `data.0.body`. A path
resolving to nothing yields no value for that field; an `items_path` resolving
to nothing or to a non-list fails the parse.

---

## Fetch outcomes

Each backend attempt yields one of three, and they never collapse into each
other.

| Outcome | Meaning | Caused by |
|---|---|---|
| `reached` | The account has claims | A parsed response with usable items |
| `reached-empty` | The account has nothing. A finished job | `404` or `410`; a well-formed response with an empty list; items carrying no text |
| `unreachable` | Whether the account has anything is unknown | Transport failure; any other non-2xx; a body that will not parse |

A body that will not parse reads as *unreachable* rather than empty. It is not
a statement by the source that nothing was published, so a feed that silently
changed format cannot look like an account that went quiet.

An account's overall outcome is `reached-empty` if any backend got there and
found nothing, and `unreachable` only if none got there at all.

## Harvested records

| Field | Description |
|---|---|
| `text` | The cleaned claim text |
| `raw` | The body as received, before cleaning |
| `transforms` | Every edit between `raw` and `text` |
| `published_at` | The parsed date, subject to the precision cap |
| `date_precision` | `exact`, `approximate`, or `unknown` |
| `provenance.source_id` | Which source |
| `provenance.account` | Which account |
| `provenance.backend` | **Which transport produced it** — backends disagree about formatting |
| `provenance.url` | The item's permalink, where one exists |
| `provenance.fetched_at` | When it was retrieved |

### `transforms`

`html-stripped`, `entities-decoded`, `whitespace-collapsed`.

Recorded rather than performed silently: derived elements anchor to spans of
the original, so text quietly rewritten in transit yields spans that resolve to
the wrong words much later.

### Identity and merging

Records are keyed by `provenance.url` where one exists, and by a hash of the
text otherwise. Merging into a corpus updates a record in place rather than
appending, so a corrected claim does not become two claims — which would
inflate the denominator of anything measured against the corpus.

## Cache

Written to `corpus/.harvest-cache.json`, keyed by source, account, and backend.

Entries carry a TTL derived from the source's cadence. Expired entries are
re-fetched and **never** served — there is no `force`, no grace period, and no
serve-stale-on-failure branch. An unreadable cache file is treated as an empty
cache rather than salvaged.
