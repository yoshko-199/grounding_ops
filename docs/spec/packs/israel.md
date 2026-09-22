# Custodian Pack — Israel

**Pack version 0.1 (draft)** — reference instance of the [Custodian Pack Interface](../custodian-pack-interface.md).

> **Status: three measures admitted, the rest not.** A narrow pack carrying the Bank of Israel's representative rates for the US dollar, the euro and sterling now loads and routes, and ships as [`packs/live/il.toml`](../../../packs/live/il.toml). Every field in it was taken from the Bank's own current publications, read and quoted rather than recalled.
>
> Everything else in this document remains **not admitted**. Fields marked **[confirm]** were not present in the source material and must be confirmed against the custodian's own current publication before they can load. They are deliberately left unfilled rather than filled from memory — a pack populated from recollection is the failure mode the whole spec exists to prevent, and it would be self-refuting to introduce it here.
>
> **Two entries below were wrong, and reading the source is what showed it.** The `boi` row previously recorded the representative rate as "fixed per date and not revised" with integrity annotation "none known". The Bank's own explanatory notes say the rates *have no official or legal standing*, are not published in the Official Gazette, are indicative rather than transactional, and that the Bank reserves absolute discretion to change them and the process determining them without notice. Both corrections are now in the table. Neither was a careless error; both are what plausible recollection produces, which is the argument for the rule.

---

## Provenance

Custodians, mandates, cadences, routing, and `known_confusions[]` are carried over from the `israeli-fact-checker` skill's `references/source-map.md` and `references/domain-checklist.md`, which were compiled from the custodians' own publications and from The Whistle (המשרוקית) / IFCN methodology. That skill is prior art for this spec (v0.2 §11) and is not modified by this document.

`published_precision`, `admissible_baselines[]`, `admissible_windows[]`, `discrete`, and the series break registers are **new requirements introduced by the pack interface**. They have no counterpart in the source material and are therefore marked **[confirm]** throughout.

---

## 1. Jurisdiction header

| Field | Value |
|---|---|
| `jurisdiction_id` | `IL` |
| `languages` | Claims arrive in Hebrew, English, Arabic, Russian. Custodians publish primarily in Hebrew, some series in English. **The gap matters:** measure names translate loosely and the mistranslation is where measure identity is lost |
| `authority_basis` | Statutory. Statistics Ordinance (CBS), Bank of Israel Law (BoI), Basic Law: The State Economy and the annual Budget Law (budget execution), Basic Law: The Knesset and the Knesset Elections Law (elections and legislation), Amutot Law and Political Parties Financing Law (NGO disclosure) |
| `pack_version` | `0.1-draft` |
| `maintainer` | Unassigned — **[confirm]** before admission |

---

## 2. Custodians

| `id` | Name | `mandate` | `cadence` | `revision_policy` | `access_method` | `integrity_annotation` |
|---|---|---|---|---|---|---|
| `cbs` | Central Bureau of Statistics (הלשכה המרכזית לסטטיסטיקה) | Statutory national statistical office under the Statistics Ordinance | Monthly for price indices; monthly/quarterly for labour force; periodic for demographics | Publishes provisional prints and revises; index rebasing occurs periodically | API / bulk datasets / published tables | None known as to independence. Rebasing and basket revisions fracture long series — see break register §5 |
| `boi` | Bank of Israel (בנק ישראל) | Central bank; calculates and publishes the representative rate (שער יציג) once a day on foreign-currency business days, as a purely informational service | Daily, business days — none on Saturdays, Sundays, Israeli holidays, Christmas Day, New Year's Day or Easter | A rate is calculated once for a date; the series database is updated shortly after publication. The Bank reserves absolute and sole discretion to change the rates, the process determining them, and the means of publication, without notice | SDMX series database and a public XML endpoint | **Not "none known".** The rates have no official or legal standing and are not published in the Official Gazette. They are indicative — an average of buying and selling prices published by banks, not necessarily rates at which transactions occurred |
| `budgetkey` | BudgetKey / OpenBudget (obudget.org) | Publishes state budget allocation and execution derived from Ministry of Finance data | Updated through the fiscal cycle | Execution figures firm up over the year; provisional through the cycle | API / structured datasets | **Derived publisher, not the originating ministry.** Treat as authoritative for budget structure and execution while recording that the originating record is the Ministry of Finance. Procurement coverage begins only in recent years — verify the period claimed exists in the data |
| `knesset` | Knesset ParliamentInfo OData | Parliamentary record: bills, committees, member profiles | Continuous | Records amended as legislative status changes | OData service | Holds bills, committees, and members — **not** per-MK plenum votes |
| `knesset_votes` | Knesset plenum-votes dataset (הצבעות חברי הכנסת במליאה, via data.gov.il) | Roll-call record of plenum votes, published by the Knesset | Per sitting | — **[confirm]** | data.gov.il CKAN | Distinct custodian from `knesset` and from `elections`. Conflating the three is the most common routing error in this jurisdiction |
| `elections` | Central Elections Committee (via data.gov.il) | Statutory authority for conducting and certifying Knesset elections | Per election | Final certified results supersede provisional counts | data.gov.il CKAN | Holds ballot-box results only — not legislative votes |
| `nadlan` | Government real-estate registry (nadlan.gov.il) | Publishes recorded real-estate transaction prices | Continuous, with reporting lag | Late registrations backfill earlier periods | Published service | **Reporting lag means recent periods are systematically incomplete** and revise upward as registrations arrive. Records sold prices, never asking prices |
| `justice_amutot` | Ministry of Justice Corporations Authority (רשם העמותות) | Statutory registry of amutot; foreign political donation disclosure regime | Periodic disclosures | — **[confirm]** | Published registry | **Known under-reporting.** Absence of a disclosure is not evidence of no funding. Reporting thresholds mean sub-threshold funding is invisible by design — a verified "no disclosed donations" must never render as "no foreign funding" |
| `btl` | National Insurance Institute (ביטוח לאומי) | Publishes the statutory average wage used as a benefit base | Periodic | — **[confirm]** | Published tables | Publishes the *statutory* average wage, a benefit-indexation instrument. It is not the survey average wage and must not be routed to cost-of-living claims |
| `data_gov_il` | data.gov.il (national open-data catalogue) | Government open-data catalogue; CKAN router to ministry datasets | Varies by dataset | Varies by dataset | CKAN API | **Catch-all router, not itself a custodian.** The custodian is the publishing ministry. Dataset freshness varies wildly; the resource's last-updated metadata must be read every time, and a stale dataset must never be presented as current |

Ministries reached through `data_gov_il` (Israel Police, Ministry of Health, Ministry of Transport, Ministry of Education, PIBA) are custodians in their own right and require their own entries before the measures routing to them can be admitted. **[confirm]**

---

## 3. Measures

`published_precision`, `admissible_baselines[]`, `admissible_windows[]`, and `discrete` are new interface requirements with no counterpart in the source material. All are **[confirm]**.

### Economy and prices

| `id` | Name | `definition` | `custodian_id` | `known_confusions[]` |
|---|---|---|---|---|
| `cpi` | Consumer Price Index (מדד המחירים לצרכן) | Index of consumer prices against a fixed basket and base year | `cbs` | Month-over-month vs year-over-year; nominal vs real; base year and basket composition. All three change the answer while leaving the headline number recognisable |
| `price_specific` | Specific price series | Price index for a named basket component | `cbs` | A component series is not the headline index. A claim about "prices" is ambiguous between them and must bind at Stage 3 |
| `fx_representative` | Representative exchange rate (שער יציג) | Official daily reference rate set by the central bank | `boi` | **Market spot rate is not the representative rate.** A rate quoted from a finance site is not the official figure. The rate is date-specific |
| `unemployment_survey` | Labour-force survey unemployment rate | Survey-based unemployment rate | `cbs` | **Not** the count of registered job-seekers at the Employment Service. Two different measures of two different populations; quoting one as the other is the archetypal misleading-but-numerically-true claim in this jurisdiction |
| `wage_survey` | Survey average wage | Average wage from the labour-force / earnings survey | `cbs` | Not the statutory average wage (`wage_statutory`). Cost-of-living claims bind here |
| `wage_statutory` | Statutory average wage (שכר ממוצע במשק) | Benefit-indexation base | `btl` | Not the survey average. A benefit-base instrument, not a measure of what people earn |

### Government and politics

| `id` | Name | `definition` | `custodian_id` | `known_confusions[]` |
|---|---|---|---|---|
| `budget_planned` | Original planned budget (תקציב מקורי) | Budget as legislated | `budgetkey` | **Not execution.** They diverge, and citing the wrong one flips the verdict |
| `budget_executed` | Executed budget (ביצוע) | Actual spending | `budgetkey` | Claims about what "was spent" bind here, not to `budget_planned`. Also distinct from mid-year revised allocation |
| `procurement` | Government procurement records | Recorded contracts and support payments | `budgetkey` | Coverage begins only in recent years. Absence in an early period is missing coverage, not absence of spending |
| `bill_status` | Bill / legislative status | Status of a bill through readings and committees | `knesset` | Not per-MK votes. "The Knesset passed X" binds here; "MK Y voted for X" binds to `mk_vote` |
| `mk_vote` | Per-MK plenum vote | Roll-call record of an individual member's vote | `knesset_votes` | **Not in the ParliamentInfo OData, and not in the Central Elections Committee data.** Both are plausible-looking wrong routes for the same claim |
| `election_result` | Election results / seats | Certified ballot-box results and seat allocation | `elections` | Final certified results, not exit polls. `discrete` — exact match |
| `turnout` | Election turnout | Share of eligible voters who voted | `elections` | Denominator is *eligible voters*, not registered or resident population |
| `ngo_foreign_donations` | Foreign political donation disclosures | Disclosures filed under the statutory regime | `justice_amutot` | A disclosure record is not a funding total. Sub-threshold and undisclosed funding is invisible; a nil return means "nothing disclosed," never "nothing received" |

### Property, demographics, catch-all

| `id` | Name | `definition` | `custodian_id` | `known_confusions[]` |
|---|---|---|---|---|
| `house_price_index` | House Price Index | Index of dwelling prices | `cbs` | The national-trend measure. Not an average of individual deals |
| `recorded_deals` | Recorded transaction prices | Registered sale prices of specific properties | `nadlan` | Recorded sold prices, not asking prices. Recent periods are incomplete by reporting lag — an apparent recent decline is often unregistered volume |
| `population` | Resident population | CBS population estimates | `cbs` | CBS counts resident population; PIBA counts legal status and entries; aliyah figures sit elsewhere again. Merging the three is a definitional error, not an arithmetic one |
| `crime_recorded` | Recorded crime counts | Offences recorded by police, selected categories | `data_gov_il` → Israel Police **[confirm]** | Recorded-crime counts are not victimisation rates. Published coverage is selected categories only |
| `road_fatalities` | Road fatalities | Deaths from road collisions | `data_gov_il` → Ministry of Transport **[confirm]** | Counts vary by definition — at-scene vs within-30-days. The definition must be cited or the figure is not comparable across sources |
| `mortality` | Mortality / health indicators | Deaths and health outcomes | `data_gov_il` → Ministry of Health **[confirm]** | Crude vs age-standardised rates differ substantially. Denominator must be bound at Stage 3 |
| `education_outcomes` | Bagrut / international assessment | Matriculation and comparative assessment results | `data_gov_il` → Ministry of Education; OECD for PISA **[confirm]** | PISA is triennial — an old cycle cited as current is a stale-data error. National averages mask large subgroup gaps |

---

## 4. Routing rules

`rationale` and `alternatives_considered[]` are required for every rule ([interface §3.4](../custodian-pack-interface.md#34-routing-rules)). Representative entries; the full table must be completed before admission. **[confirm]**

| `measure_id` | `custodian_id` | `rationale` | `alternatives_considered[]` |
|---|---|---|---|
| `cpi` | `cbs` | Sole statutory compiler of the national price index under the Statistics Ordinance | Bank of Israel publishes inflation analysis but does not compile the index; news outlets report it but do not publish it |
| `fx_representative` | `boi` | The representative rate is defined by the central bank; no other body sets an official rate | Commercial banks and finance portals publish spot rates — these are market prices, not the official reference rate |
| `budget_executed` | `budgetkey` | Publishes execution data in queryable structured form | Ministry of Finance is the originating record; routed to BudgetKey for structured access, with the originating record noted. Any divergence resolves to the Ministry |
| `mk_vote` | `knesset_votes` | The plenum-votes dataset is the only published roll-call record | ParliamentInfo OData (holds bills and members, not votes); Central Elections Committee (ballot-box results, not legislative votes). Both are commonly and wrongly used for this |
| `house_price_index` | `cbs` | National-trend claims require an index, not an aggregation of transactions | Nadlan recorded deals — correct for a *specific property*, wrong for a national trend, since incomplete recent registration biases any aggregate |
| `unemployment_survey` | `cbs` | The survey rate is the defined national unemployment measure | Employment Service registered job-seeker counts — a different population, not an alternative source for the same measure |

---

## 5. Series break registers

Every entry requires a `custodian_notice_ref` — the custodian's own announcement. **None are populated.** Each register below must be built from the custodian's published notices before any cross-time element on that measure can be Verified (spec §9.5, [AC-12](../acceptance-criteria.md#ac-12--break-integrity)).

| `measure_id` | Break kinds expected | Status |
|---|---|---|
| `cpi` | `base_year` (periodic rebasing), `definition` (basket revisions), `methodology` | **[confirm]** — empty register. Until populated, long-run CPI comparisons cannot be Verified |
| `house_price_index` | `base_year`, `methodology` | **[confirm]** — empty |
| `unemployment_survey` | `methodology`, `definition` (survey redesigns and definitional changes) | **[confirm]** — empty |
| `budget_executed` | `classification` (budget-line restructuring across fiscal years), `coverage` | **[confirm]** — empty. Cross-year ministry-spending comparisons are the most break-prone claims in this pack, since restructuring renames and merges lines |
| `election_result` | `definition` (electoral threshold changes), `coverage` | **[confirm]** — empty |
| `procurement` | `coverage` (publication begins mid-series) | **[confirm]** — empty. Coverage onset is a break, and comparisons spanning it will otherwise read as growth from near-zero |

The `budget_executed` and `procurement` rows deserve attention: both produce breaks that look like findings. A ministry line restructured across fiscal years appears as a spending collapse or explosion, and a coverage onset appears as explosive growth. Both would verify cleanly as arithmetic against the published figures — which is exactly why the continuity check runs before the element verdict, not after.

---

## 6. Admission blockers

### What is now admitted

[`packs/live/il.toml`](../../../packs/live/il.toml) loads. It declares one custodian (`boi`) and three measures — `fx_representative_usd`, `fx_representative_eur`, `fx_representative_gbp` — and every blocker below is closed **for those three only**:

| Blocker | How it was closed |
|---|---|
| 1 maintainer | Recorded as unassigned, pointing here. Honest rather than closed |
| 3 precision, unit, discrete | Precision observed from the Bank's own published rate table, which quotes every currency to four decimal places. The Bank states no precision policy in prose, so this is confirmed by reading the publication rather than by being told, and the pack says so |
| 4 admissible baselines and windows | The daily change published beside the rate, and the monthly and annual average extracts offered on the same page. `admissible_source_ref` cites them |
| 5 routing | One rule, with three alternatives considered — commercial bank rates, vendor spot rates, and other central banks' own representative rates |
| 6 break register | Four entries, all from the Bank's Explanatory Notes, which narrate every change to how the rate is determined: a coverage change in 1986, methodology changes in 1990 and 1995, and a sampling-window change in 2006. **None has a linked series**, so any comparison spanning one cannot be Verified |
| 7 revision policy | Confirmed for `boi`. Still open for `knesset_votes`, `justice_amutot`, `btl` |

The break register is worth dwelling on, because it was the blocker expected to be hardest and turned out to be the easiest for this custodian. The Bank publishes a prose history of its own methodology changes with dates. That is exactly what a break register is, and it was already written — it simply had to be read.

**Languages: English only.** Claims about Israel mostly arrive in Hebrew, there is no Hebrew lexicon, and directional vocabulary still sits in the pipeline rather than in a pack ([plan §2.5](../../plan.md#25-language-vocabularies-outside-the-lexicon)). Declaring Hebrew without a Hebrew lexicon would under-fire silently on every Hebrew claim; declaring English only makes Hebrew claims return Insufficient Data, which is visible.

**It routes and verifies nothing.** An adapter exists ([`engine/custodians/boi.py`](../../../engine/custodians/boi.py)), wired behind the CLI's `--live` flag, but it has never run against the live endpoint: the environment this was written in blocks the Bank's hosts. A covered claim binds the measure, names the custodian and its rationale, and returns Insufficient Data because the Bank could not be reached. That is a better answer than "no jurisdiction could be established" and it is still not a verified claim.

**Declaring sibling measures is what surfaced the binder's scoring flaw.** A claim naming no currency now matches all three equally and routes nowhere, which is the measure-identity rule working. Getting there required fixing a bug no single-measure pack could expose: a claim token appearing in both a measure's name and its definition was scored twice, so a definition echoing its own name outranked a sibling that said the same thing once.

### Still blocked, for every other measure

This pack cannot load until:

1. `maintainer` assigned.
2. Ministry custodians reached via `data_gov_il` given their own entries with mandate, cadence, revision policy, and integrity annotation.
3. `published_precision`, `unit`, and `discrete` confirmed per measure against the custodian's current publication.
4. `admissible_baselines[]` and `admissible_windows[]` declared per measure, drawn only from windows the custodian itself publishes.
5. Routing table completed for every declared measure, each with rationale and alternatives.
6. Series break registers populated from custodian notices, with references.
7. Revision policies confirmed for `knesset_votes`, `justice_amutot`, and `btl`.

Items 3, 4, and 6 are the substantial work. Items 4 and 6 in particular gate real guarantees rather than paperwork: without declared admissible alternatives the robustness sweep cannot run and every verdict caps at Indeterminate ([AC-11](../acceptance-criteria.md#ac-11--sweep-coverage)), and without break registers no cross-time comparison can be Verified ([AC-12](../acceptance-criteria.md#ac-12--break-integrity)).

This is the pack interface behaving as designed. An incomplete pack degrades to conservative outcomes instead of routing confidently on partial knowledge.
