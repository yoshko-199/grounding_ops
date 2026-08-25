# Custodian Pack — Israel

**Pack version 0.1 (draft)** — reference instance of the [Custodian Pack Interface](../custodian-pack-interface.md).

> **Status: not admitted.** This pack does not yet pass the [validation checklist](../custodian-pack-interface.md#6-pack-validation-checklist). Fields marked **[confirm]** were not present in the source material and must be confirmed against the custodian's own current publication before the pack loads. They are deliberately left unfilled rather than filled from memory — a pack populated from recollection is the failure mode the whole spec exists to prevent, and it would be self-refuting to introduce it here.

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
| `boi` | Bank of Israel (בנק ישראל) | Central bank; publishes the official representative rate (שער יציג) under the Bank of Israel Law | Daily, business days | Representative rates are fixed per date and not revised; macro series are revised | API / published rate tables | None known |
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
