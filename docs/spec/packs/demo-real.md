# Custodian pack — real figures for the ten claims (scaffold)

**Status: scaffold, not loadable.** This is the real-figures counterpart to
the synthetic [demo pack](../../how-to/try-the-demo-pack.md). It names, for
each of the [ten supplied claims](../../validation-ten-claims.md), the
authority that would be its custodian of record and the publication that
would hold the figure. **Every figure and every pack field that the authority
itself must confirm is `[confirm]`.** None was filled in, because none could
be fetched from the authority's own publication in the environment this was
built in.

> **Why nothing is filled in.** The repository's first working rule is that
> no pack field is populated from recollection, and a search engine's summary
> of a page is not the page. The development environment's network allowlist
> refuses every host below, and routing around it is out of bounds. So the
> scaffold is filled only by fetching each page, either by adding the hosts
> to the environment's allowed domains, or by a local session that can reach
> them. See [how to fill it](#how-to-fill-it). Until then, a claim that needs
> a `[confirm]` field cannot verify, which is the rule working as intended.

The links below were identified from search listings, and they are where the
figure *should* be read. Nothing on this page reports what those pages say.

## The claims with a figure to check

| # | Claim's figure | Measure | Authority (custodian of record) | Where the figure would be read | Host to allow |
|---|---|---|---|---|---|
| 1 | Boiling point of water, in Celsius and Fahrenheit | Normal boiling point of water | US National Institute of Standards and Technology, Chemistry WebBook (Standard Reference Data) | [NIST WebBook: water, boiling point](https://webbook.nist.gov/cgi/cbook.cgi?ID=C7732185&Type=TBOIL) | `webbook.nist.gov` |
| 4 | The year the charter was sealed | Date of the charter's first sealing, and of its reissues | The National Archives (UK) | [Magna Carta — The National Archives](https://www.nationalarchives.gov.uk/explore-the-collection/explore-by-time-period/medieval/magna-carta/), [Magna Carta 1214–1225](https://www.nationalarchives.gov.uk/education/teaching-resources/magna-carta-1214-1225/) | `www.nationalarchives.gov.uk` |
| 8 | Density of steel | Design density (unit weight) of structural steel | European Committee for Standardization (CEN): EN 1991-1-1, Table A.4 | The standard is sold rather than freely published. A licensed copy is the only first-hand source, so this may stay `[confirm]` permanently | none freely available |
| 10 | Murder rate, 1991 to the latest year | Murder and nonnegligent manslaughter rate per hundred thousand inhabitants | FBI, Uniform Crime Reporting Program | [Crime in the U.S. 2010, tables](https://ucr.fbi.gov/crime-in-the-u.s/2010/crime-in-the-u.s.-2010/tables-by-title) (Table 1 spans 1991–2010), [2019 Table 1](https://ucr.fbi.gov/crime-in-the-u.s/2019/crime-in-the-u.s.-2019/tables/table-1), [Crime Data Explorer](https://cde.ucr.cjis.gov/) for later years | `ucr.fbi.gov`, `cde.ucr.cjis.gov` |

Fields each measure needs, all `[confirm]` until read from the authority:

| Field | 1 (boiling point) | 4 (charter) | 8 (steel) | 10 (murder rate) |
|---|---|---|---|---|
| Figure(s) | `[confirm]` | `[confirm]` | `[confirm]` | `[confirm]` per year |
| Unit as published | `[confirm]` | `[confirm]` | `[confirm]` | `[confirm]` |
| Published precision | `[confirm]` | `[confirm]` | `[confirm]` | `[confirm]` |
| Cadence and revision policy | `[confirm]` | `[confirm]` | `[confirm]` | `[confirm]` |
| Known confusions | Pressure and altitude; Celsius and Fahrenheit (see [R1](../proposals/v0.6-requirements.md#r1-units)) | First sealing against later reissues (see [R2](../proposals/v0.6-requirements.md#r2-event-dates)) | Structural steel against stainless and other alloys | The FBI's offence-based murder rate against the death-registration homicide rate other bodies publish |

Even filled in, claims 1 and 4 would meet the engine limits the demo pack
shows: the unit gap (R1) and the event-date gap (R2). A real figure doesn't
remove a missing element kind.

## The claims no figure settles

The engine routes these out of scope, and would still do so with every
authority below in a pack. Each is causal, evaluative, a classification or
arithmetic, not a quantity a custodian publishes. The body a reader would
consult is named here for completeness only.

| # | Claim | Why the engine routes it out | Where a reader would look |
|---|---|---|---|
| 2 | Pizza is the most delicious food | Opinion | Nowhere; there is no custodian of taste |
| 3 | Humans are classified as mammals | Classification, with no quantity (see [R5](../proposals/v0.6-requirements.md#r5-classification-facts)) | A taxonomic register |
| 5 | Covid-19 originated from a research lab | Causal and provenance, with no quantity | [WHO Scientific Advisory Group for the Origins of Novel Pathogens: independent assessment](https://www.who.int/publications/m/item/independent-assessment-of-the-origins-of-sars-cov-2-from-the-scientific-advisory-group-for-the-origins-of-novel-pathogens) |
| 6 | Vaccines cause autism | Causal (and see [R3](../proposals/v0.6-requirements.md#r3-active-voice-causal-verbs)) | [CDC: Autism and vaccines](https://www.cdc.gov/vaccine-safety/about/autism.html) |
| 7 | Two sheep and two more make four | Arithmetic, which needs no custodian | Not applicable |
| 9 | The US tax-and-transfer system is highly progressive | Evaluative ("highly", "massive"), with no quantity | [CBO: income distribution](https://www.cbo.gov/topics/income-distribution) |

## How to fill it

1. **Reach the hosts.** Either add the hosts in the table above to the cloud
   environment's allowed domains (the environment menu in the session's
   title bar, then **Edit**, then **Network access**), or work from a local
   Claude Code session with Claude in Chrome, which uses your own network.
2. **Copy the template** `packs/demo-real/figures.template` to
   `packs/demo-real/figures.toml`, and fill one entry per figure. Every entry
   records the page's `url`, the `table` or section, the date it was
   `fetched_on`, and the `quoted_text` the figure was read from, verbatim. An
   entry without all four is not filled in.
3. **Leave blanks blank.** A figure that can't be read from the authority's
   own page stays `[confirm]`. Don't fill it from another site, a search
   summary, or memory.
4. **Then make it a pack.** Once every field a measure needs is confirmed,
   the measure moves into a loadable `packs/demo-real/` pack with an adapter
   serving the recorded figures. That adapter must say, in its custodian
   name, that it serves a recorded copy, with the fetch date, and not a live
   retrieval. Measures still `[confirm]` stay out, following the same rule as
   the Israel pack: a pack must be complete to load, but need not be broad.
