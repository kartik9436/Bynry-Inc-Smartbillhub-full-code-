# Taxes & fees — the full web walk (task 9), results

`CR-165-BRC10` round 4 task 9 · walked 2026-10-03 · builds **2.477.0** and **2.479.0** ·
plan `05-prototype/taxes-fees-2026-10-03/web-walk.md` (as amended by the PO: no *Outside city
limits* and no *named place* for taxes, so 1.4 and 1.7 are not created as taxes and 1.5 is
*Everywhere*).

**How it was run.** The built front end (`vite build --mode wolocal`, served by
`07-frontend/server.mjs`) on the Django back end over a scratch **PostgreSQL 16** database
(`migrate` + `seed_demo` + `10-scripts/cr165_taxwalk_world.py setup`). Chromium at 1440 wide,
clicking as Dana (System Admin). Every step has a screenshot `walk/taxwalk_<phase>_<step>.png`
(92 files, each opened; none blank). Every *must be true* was checked on the screen, against the
API and in the database — the script is `10-scripts/cr165_taxwalk.mjs`, its raw output
`walk/results.json`, the tax ids it carried `walk/state.json`.

**The world.** Utility A is **Brazos Bend** (the demo utility): water, sewer, trash and storm
water switched on through the Settings act — and electric, which the demo utility also runs, so
the Services list shows five, not the plan's four (it is *this utility's switched-on services*
either way). Three authority accounts (TX Comptroller, Wapello County Treasurer, City of Ottumwa
Finance). Utility B is **Riverbend Water**, provisioned through sign-up's own service, no taxes.
The billed account is **AC-2026-00054** (Riverside Diner, commercial, inside city limits, one water
meter) on plan *Tax walk · Commercial water*: base **$15.00** + usage 10 kgal × $3.50 + 2 kgal ×
$5.00 = **$60.00** for **12 kgal**. (The plan's *$40.00 + $20.00* split is not reproducible on the
demo's sized commercial base code; only the $60.00 the taxes are charged on is the walk's figure.)

**Order.** Phases 0 → 2 → 1 → 3, then the **October bill run**, then phase 4 (the edits), then
phase 5 (lookups and the **November bill run**), 6 and 7 — so the October bill is issued at the
typed 150% before it is fixed (5.6).

## Phase by phase

| Phase | What | Result |
|---|---|---|
| 0 Setup | 4 services on, 8 classes, 3 authority accounts, plans with accounts, Utility B | **PASS** (4 of 4) |
| 1 Create | 5 taxes through the form (state, county, city, special district, state board; all / several / one service; every / several / one class; percent, per meter, per unit) + a draft | **PASS** (16 of 16) — after fixing `DEF-RAT-9305` (a draft could not be finished) and `DEF-RAT-9306` (panel said $0.00) |
| 2 Refuse & warn | empty form, lists, 62.5%, liability and email | **PASS** (8 of 8) |
| 3 View | every value on details and in the API; list banner, pill, dates; Duplicate | **PASS** (14 of 14) — Duplicate walked after `DEF-RAT-9299` |
| 4 Edit | name & filing (same row), new rate from 11/01/2026, fix 150% → 3%, early start refused, versions & audit | **PASS** (15 of 15) — the new-rate boxes walked after `DEF-RAT-9301` |
| 5 Billing | one row per tax per date; real runs 10/15 and 11/15; October keeps $3.75 and $90.00 | **PASS** (7 of 7) |
| 6 Plans & audit | real account counts, add and remove in Audit | **PASS** (8 of 8) — after `DEF-RAT-9304` (tab count) |
| 7 Isolation & languages | B sees nothing of A's, on screen or from the server; es-MX and ja-JP spot check | **PASS** (7 of 7) |

**79 checks, 79 pass.** Two checks were wrong rather than the product and were corrected, said
so in `results.json`: 2.2 first demanded exactly four services (Brazos Bend runs five), and 4.4
first demanded HTTP 400 (this API answers a refused value with 422, naming
`rating.taxes.new_rate_too_early`).

## Every check

| Step | What must be true | Result | Evidence (screen · API · database) |
|---|---|---|---|
| 0.1 | water, sewer, storm water and trash are on | PASS | on: electric, water, sewer, trash, storm_water |
| 0.1 | three authority accounts in Settings › Accounting | PASS | listed on the Authorities sub-tab |
| 0.2 | plans carry real accounts | PASS | Industrial: 0 · Residential Standard: 0 · Sample — Commercial: 2 · Sample — Industrial: 1 · Sample — Residential: 67 · Small Commercial: 0 · Tax walk · Commercial wate… |
| 0.3 | Utility B exists with no taxes | PASS | riverbend taxes: 0 |
| 1.1 | State sales tax: exactly one row in the database | PASS | [["01a10140-e360-718c-ae48-3cd2615d766c","1","0.062500","","","","2026-01-01","","f","","State sales tax",""]] |
| 1.1 | State sales tax: list row with v1, From, To, GL, premises | PASS | v1 · 2026-01-01 → No end · GL 2200-01 Tax payable — Local · Bexar County · premises 9 of 80 |
| 1.2 | County utility tax: exactly one row in the database | PASS | [["01a10140-fe14-7449-91c2-bc3a34a12a06","1","0.020000","","","","2026-01-01","","f","","County utility tax",""]] |
| 1.2 | County utility tax: list row with v1, From, To, GL, premises | PASS | v1 · 2026-01-01 → No end · GL 2200-01 Tax payable — Local · Bexar County · premises 72 of 80 |
| 1.3 | 150% typed warns, does not refuse | PASS | New tax or fee Save draft & exit ✓ What it is 2 How much 3 Filing 4 Review & save Rate Charged as A percentage of the bill A fixed amount per bill An amount per unit u… |
| 1.3 | City franchise fee: exactly one row in the database | PASS | [["01a10141-18c8-7cbd-835b-6105e852d264","1","1.500000","","","","2026-09-01","","f","","City franchise fee",""]] |
| 1.3 | City franchise fee: list row with v1, From, To, GL, premises | PASS | v1 · 2026-09-01 → No end · GL 2200-01 Tax payable — Local · Bexar County · premises 72 of 80 |
| 1.5 | Riverside storm fee: exactly one row in the database | PASS | [["01a10141-32a7-735f-96a4-194c048f55b2","1","","","","1.250000","2026-01-01","","f","","Riverside storm fee",""]] |
| 1.5 | Riverside storm fee: list row with v1, From, To, GL, premises | PASS | v1 · 2026-01-01 → No end · GL 2200-01 Tax payable — Local · Bexar County · premises 0 of 80 |
| 1.5 | THIS TAX panel reads a dash, not $0.00, for a per-meter tax (DEF-RAT-9306) | PASS | — |
| 1.6 | Water conservation fee: exactly one row in the database | PASS | [["01a10141-4d3c-7828-ad11-46a7f23a85be","1","","","0.050000","","2026-01-01","","f","","Water conservation fee",""]] |
| 1.6 | Water conservation fee: list row with v1, From, To, GL, premises | PASS | v1 · 2026-01-01 → No end · GL 2200-01 Tax payable — Local · Bexar County · premises 58 of 80 |
| 1.8 | Save draft & exit stores a DRAFT (DEF-RAT-9275) | PASS | [["01a10141-5a72-7505-b684-ddac3ecf1432","t","City permit fee (draft)"]] |
| 1.8 | Edit on a draft reopens it filled (DEF-RAT-9305) | PASS | http://127.0.0.1:8792/brazosbend/plans-rates/taxes-fees/new?draft=01a10141-5a72-7505-b684-ddac3ecf1432 |
| 1.8 | nothing typed before the draft was saved is lost | PASS | 3.00 |
| 1.8 | the SAME row, no longer a draft, one row | PASS | [["01a10141-5a72-7505-b684-ddac3ecf1432","f","City permit fee","CITY-PERMIT","2026-11-01"]] |
| 2.1 | each missing box says what is wrong | PASS | ["Enter the name on the bill.","Choose an authority."] |
| 2.1 | nothing typed is lost | PASS | Typed then refused |
| 2.2 | only the utility's switched-on services, All services first | PASS | ["All services","Electric","Water","Sewer","Trash","Storm water"] · switched on: 5 |
| 2.3 | Every customer class first, then the 8 classes | PASS | ["Every customer class","Residential","Commercial","Industrial","Agricultural","Institutional","Municipal","Builder or developer","Government"] |
| 2.4 | 62.5% and 'check the rate' on step 2 | PASS | New tax or fee Save draft & exit ✓ What it is 2 How much 3 Filing 4 Review & save Rate Charged as A percentage of the bill A fixed amount per bill An amount per unit u… |
| 2.4 | 62.5% and the warning on Review | PASS | New tax or fee Save draft & exit ✓ What it is ✓ How much ✓ Filing 4 Review & save 62.5% is high. |
| 2.5 | liability and email refused by name | PASS | ["tax-liability-error:Choose the liability account.","tax-reminder-error:Enter a valid email."] |
| 2.6 | named-place boundary: not offered (PO ruling — dropped) | PASS | boundaries served: everywhere, city_limits |
| 3.1 | State sales tax: header and sections show what was entered | PASS | shown: State sales tax · ST-SALES · v1 · State sales tax · TX Comptroller |
| 3.1 | State sales tax: API read equals what was entered | PASS | code ST-SALES · filed monthly · due 20th_next_month · boundary everywhere · services [] · classes ["commercial","industrial"] · rate 0.062500 |
| 3.1 | County utility tax: header and sections show what was entered | PASS | shown: County utility tax · CNTY-UTIL · v1 · County tax · Wapello |
| 3.1 | County utility tax: API read equals what was entered | PASS | code CNTY-UTIL · filed quarterly · due last_day_next_month · boundary everywhere · services ["water","sewer"] · classes [] · rate 0.020000 |
| 3.1 | City franchise fee: header and sections show what was entered | PASS | shown: City franchise fee · CITY-FRAN · v1 · City franchise fee · Ottumwa · Over 20% |
| 3.1 | City franchise fee: API read equals what was entered | PASS | code CITY-FRAN · filed monthly · due 15th_next_month · boundary city_limits · services [] · classes [] · rate 1.500000 |
| 3.1 | Riverside storm fee: header and sections show what was entered | PASS | shown: Riverside storm fee · SD-STORM · v1 · Storm fee |
| 3.1 | Riverside storm fee: API read equals what was entered | PASS | code SD-STORM · filed monthly · due 25th_next_month · boundary everywhere · services ["storm_water"] · classes ["residential"] · rate 1.250000 |
| 3.1 | Water conservation fee: header and sections show what was entered | PASS | shown: Water conservation fee · ST-CONS · v1 · Conservation fee · TX Comptroller |
| 3.1 | Water conservation fee: API read equals what was entered | PASS | code ST-CONS · filed quarterly · due 30_days_after_quarter · boundary everywhere · services ["water"] · classes ["residential","commercial"] · rate 0.050000 |
| 3.2 | Over 20% banner counts 1.3; pill shows; MM/DD/YYYY dates | PASS | 8 taxes & fees · effective 10/01/2026 History + New tax or fee Plans Rate schedules Charge codes Discounts Taxes & fees 1 tax charges over 20%. |
| 3.dup | Duplicate opens the New form filled from the tax | PASS | Wapello County utility tax · http://127.0.0.1:8792/brazosbend/plans-rates/taxes-fees/new?duplicate=01a10140-fe14-7449-91c2-bc3a34a12a06 |
| 3.dup | the code is cleared (one code names one tax) | PASS |  |
| 3.dup | a NEW tax: its own row, v1, its own chain; the original untouched | PASS | [["01a1014e-df40-7301-aded-8d815c59c9cd","1","t","0.020000","[\"water\", \"sewer\"]"]] |
| 4.1 | same row updated, still v1, rate and reach locked | PASS | rows 1, id same true, v1, name Wapello County utility tax; locked note: Rate and reach |
| 4.1 | Audit: before → after for the change | PASS | [{"before":{"name":"County utility tax","due_date_rule":"last_day_next_month","filing_reminder_recipient":"county@brazosbend.example"},"after":{"name":"Wapello County … |
| 4.2 | What is taxed, Discounts and Rounding are open (image 28, DEF-RAT-9301) | PASS | discounts true · rounding true |
| 4.2 | v1 ends 10/31/2026, v2 starts 11/01/2026, two rows, nothing deleted | PASS | [["1","0.062500","2026-01-01","2026-10-31"],["2","0.065000","2026-11-01",""]] |
| 4.2 | header shows Next: 6.50% from 11/01/2026 | PASS | Next: 6.50% from 11/01/2026 Edit More ▾ Overview Plans7 Audit RATE 6.25% of the taxed amount PREMISES 9 of 80 PLANS 7 using it COLLECTED — Not counted yet Rate and sco… |
| 4.2 | a new rate saves a changed rounding on v2 only (DEF-RAT-9301) | PASS | [["1","0.050000","half_up","2026-01-01","2026-12-31"],["2","0.060000","half_even","2027-01-01",""]] · review lists rounding: true |
| 4.3 | reason required | PASS | Enter the reason. |
| 4.3 | v1 superseded and kept, v2 the same dates at 3% | PASS | [["1","1.500000","2026-09-01","","superseded"],["2","0.030000","2026-09-01","","live"]] |
| 4.3 | Over 20% banner and pill gone | PASS | none |
| 4.4 | a new rate before the version's start is refused by name | PASS | Must be after 01/01/2026. |
| 4.4 | the server refuses it too, by name | PASS | 422 rating.taxes.new_rate_too_early (422 is this API's validation status; the check first asked for 400 — the check was wrong, not the product) |
| 4.5 | county: versions table and Audit carry every version and change, with who | PASS | versions v1 2.00% · audit names Dana: true |
| 4.5 | sales: versions table and Audit carry every version and change, with who | PASS | versions v2 6.50%, v1 6.25% · audit names Dana: true |
| 4.5 | city: versions table and Audit carry every version and change, with who | PASS | versions v2 3.00%, v1 150.00% · audit names Dana: true |
| 4.5 | Audit shows the correction's reason | PASS | Typed as 150% |
| 5.1 | 1.1 on 10/31/2026 and 11/01/2026: one live row each | PASS | 10/31 1 · 11/01 1 |
| 5.2 | 1.3 after the fix: one live row (the 3%) | PASS | rows 1 |
| 5.3 | 1.2 after the rename: one row, the same row | PASS | rows 1 |
| 5.4 | BL-2610-000101: one line per tax, State sales tax $3.75, County utility tax $1.20, City franchise fee $90.00, Water conservation fee $0.60 | PASS | Tax City franchise fee 90.00 · Tax County utility tax 1.20 · Tax State sales tax 3.75 · Tax Water conservation fee 0.60 · total 155.55 |
| 5.5 | BL-2611-000102: one line per tax, State sales tax $3.90, County utility tax $1.20, City franchise fee $1.80, Water conservation fee $0.60 | PASS | Tax City franchise fee 1.80 · Tax State sales tax 3.90 · Tax Wapello County utility tax 1.20 · Tax Water conservation fee 0.60 · total 67.50 |
| 5.5_october_again | BL-2610-000101: one line per tax, State sales tax $3.75 | PASS | Tax City franchise fee 90.00 · Tax County utility tax 1.20 · Tax State sales tax 3.75 · Tax Water conservation fee 0.60 · total 155.55 |
| 5.6 | BL-2610-000101: one line per tax, City franchise fee $90.00 | PASS | Tax City franchise fee 90.00 · Tax County utility tax 1.20 · Tax State sales tax 3.75 · Tax Water conservation fee 0.60 · total 155.55 |
| 6.1 | State sales tax: Plans tab rows with real account counts | PASS | Industrial: 0 accounts / 1 units · Residential Standard: 0 accounts / 7 units · Sample — Commercial: 2 accounts / 2 units · Sample — Industrial: 1 accounts / 1 units ·… |
| 6.1 | County utility tax: Plans tab rows with real account counts | PASS | Industrial: 0 accounts / 1 units · Residential Standard: 0 accounts / 7 units · Sample — Commercial: 2 accounts / 2 units · Sample — Industrial: 1 accounts / 1 units ·… |
| 6.1 | City franchise fee: Plans tab rows with real account counts | PASS | Industrial: 0 accounts / 1 units · Residential Standard: 0 accounts / 7 units · Sample — Commercial: 2 accounts / 2 units · Sample — Industrial: 1 accounts / 1 units ·… |
| 6.1 | Riverside storm fee: Plans tab rows with real account counts | PASS | Industrial: 0 accounts / 1 units · Residential Standard: 0 accounts / 7 units · Sample — Commercial: 2 accounts / 2 units · Sample — Industrial: 1 accounts / 1 units ·… |
| 6.1 | Water conservation fee: Plans tab rows with real account counts | PASS | Industrial: 0 accounts / 1 units · Residential Standard: 0 accounts / 7 units · Sample — Commercial: 2 accounts / 2 units · Sample — Industrial: 1 accounts / 1 units ·… |
| 6.2 | Plans tab count equals the plans listed (DEF-RAT-9304) | PASS | tab 7 · foot 7 |
| 6.2 | add and remove both in Audit | PASS | tax.detached_from_plan, tax.attached_to_plan, tax.detached_from_plan, tax.attached_to_plan, tax.attached_to_plan, tax.created |
| 6.3 | Audit after phase 4: who, when, what, before → after, reason | PASS | 2026-10-03T10:17 Dana Whitfield tax.new_rate_created / 2026-10-03T10:17 Dana Whitfield tax.ended_for_new_rate / 2026-10-03T10:14 Dana Whitfield tax.attached_to_plan / … |
| 7.1 | Utility B sees none of A's taxes on screen | PASS | none shown |
| 7.1 | the server returns none of A's taxes to B | PASS | status 200, rows 0 |
| 7.1 | opening A's tax by id from B gives nothing | PASS | GET taxes/{A} → 404 · audit → 404 |
| 7.1 | A's tax address on B shows nothing of A's | PASS | Failed We couldn't load this definition. We could not find that. It may have been removed, or the address may be wrong. Retry Download error report Cancel |
| 7.1 | B's authority accounts list none of A's | PASS | rows 0 |
| 7.2 | es-MX: no English left on list and details (spot check) | PASS | none of the probe words |
| 7.2 | ja-JP: no English left on list and details (spot check) | PASS | none of the probe words |

## Phase 5 in numbers

**The billing lookup itself** (`rating.selectors.plan_tax_rules`, the seam billing calls), for
the walk plan, a commercial water account inside city limits — after every edit of phase 4:

```
LOOKUP 2026-10-15 CITY-FRAN rows=1 v2 0.030000
LOOKUP 2026-10-15 CNTY-UTIL rows=1 v1 0.020000
LOOKUP 2026-10-15 ST-CONS rows=1 v1 0.050000
LOOKUP 2026-10-15 ST-SALES rows=1 v1 0.062500
LOOKUP 2026-10-31 CITY-FRAN rows=1 v2 0.030000
LOOKUP 2026-10-31 CNTY-UTIL rows=1 v1 0.020000
LOOKUP 2026-10-31 ST-CONS rows=1 v1 0.050000
LOOKUP 2026-10-31 ST-SALES rows=1 v1 0.062500
LOOKUP 2026-11-01 CITY-FRAN rows=1 v2 0.030000
LOOKUP 2026-11-01 CNTY-UTIL rows=1 v1 0.020000
LOOKUP 2026-11-01 ST-CONS rows=1 v1 0.050000
LOOKUP 2026-11-01 ST-SALES rows=1 v2 0.065000
LOOKUP 2026-11-15 CITY-FRAN rows=1 v2 0.030000
LOOKUP 2026-11-15 CNTY-UTIL rows=1 v1 0.020000
LOOKUP 2026-11-15 ST-CONS rows=1 v1 0.050000
LOOKUP 2026-11-15 ST-SALES rows=1 v2 0.065000
```

**A draft never prices** — the lookup on *Sample — Residential*, a plan that binds the City
authority, on 10/15/2026 while *City permit fee* was still a draft:

```
PLANLOOKUP 2026-10-15 Sample — Residential · City franchise fee · draft=False
PLANLOOKUP 2026-10-15 Sample — Residential · Wapello County utility tax · draft=False
PLANLOOKUP 2026-10-15 Sample — Residential · Local · Bexar County · draft=False
PLANLOOKUP 2026-10-15 Sample — Residential · Riverside storm fee · draft=False
PLANLOOKUP 2026-10-15 Sample — Residential · Water conservation fee · draft=False
```

**The two real bill runs** (`10-scripts/cr165_taxwalk_world.py run`, through `billing.runs`,
`decisions` and `issue`), as stored:

```
run RUN-0004 2026-10-16..2026-11-15
BILL BL-2610-000101 · 2026-09-16..2026-10-15 · status issued · total 155.550000
   base       water base charge                                qty=None 15.000000 · tax_id=None
   tax        Tax City franchise fee                           qty=None 90.000000 · tax_id=01a10141-18c8-7cbd-835b-6105e852d264
   tax        Tax County utility tax                           qty=None 1.200000 · tax_id=01a10140-fe14-7449-91c2-bc3a34a12a06
   tax        Tax Water conservation fee                       qty=12.000000 0.600000 · tax_id=01a10141-4d3c-7828-ad11-46a7f23a85be
   tax        Tax State sales tax                              qty=None 3.750000 · tax_id=01a10140-e360-718c-ae48-3cd2615d766c
   usage      water usage tier 2 (10+ kgal)                    qty=2.000000 10.000000 · tax_id=None
   usage      water usage tier 1 (0-10 kgal)                   qty=10.000000 35.000000 · tax_id=None
BILL BL-2611-000102 · 2026-10-16..2026-11-15 · status issued · total 67.500000
   base       water base charge                                qty=None 15.000000 · tax_id=None
   tax        Tax State sales tax                              qty=None 3.900000 · tax_id=01a10144-ad6f-7f89-a4f3-7e72a2a1cfd5
   tax        Tax Wapello County utility tax                   qty=None 1.200000 · tax_id=01a10140-fe14-7449-91c2-bc3a34a12a06
   tax        Tax City franchise fee                           qty=None 1.800000 · tax_id=01a10144-ce00-7a3e-ab2a-0e81286f6745
   tax        Tax Water conservation fee                       qty=12.000000 0.600000 · tax_id=01a10141-4d3c-7828-ad11-46a7f23a85be
   usage      water usage tier 2 (10+ kgal)                    qty=2.000000 10.000000 · tax_id=None
   usage      water usage tier 1 (0-10 kgal)                   qty=10.000000 35.000000 · tax_id=None
```

October (`RUN-0003`, issued before phase 4): State sales tax **$3.75**, City **$90.00** (the
150% as typed). November (`RUN-0004`, after phase 4): State **$3.90** (v2, 6.5%), County **$1.20**
on the **same tax row** (renamed in place), City **$1.80** (the 3% correction, v2). The October
bill still reads $3.75 and $90.00 — correcting a bill already issued is separate (`OQ-310`).

## Bugs found, and what happened to each

| Defect | Where found | What the user saw | Fixed in |
|---|---|---|---|
| `DEF-RAT-9301` | 4.2, Edit › *New rate from a date* (known before the walk) | *What is taxed*, *Discounts* and *Rounding* greyed out, though image 28 draws them open; the server refused them as unknown fields | **2.477.0** (`7b999fd48`). Walked again: 1.6 given $0.06 from 01/01/2027 with rounding *Half to even* → v2 stores `half_even`, v1 keeps `half_up` and ends 12/31/2026 |
| `DEF-RAT-9275` | 1.8, *Save draft & exit* (known) | — confirmed end to end: stored as a Draft, never returned by the billing lookup | fixed earlier (2.470.0 screen, 2.472.0 server); **closed** after this walk |
| `DEF-RAT-9299` | 3, details › More › Duplicate (known) | Duplicate greyed out | **2.477.0** (`7b999fd48`). Walked: the New form opened filled from 1.2, code cleared; saved as a new tax with its own chain |
| `DEF-RAT-9305` | 1.8, reopening the draft | A draft's **Edit** opened the live-tax variations (rate and dates locked; the other two refuse a draft) and nothing could put it into force — a saved draft was a dead end | **2.479.0** (`31b0b468c`). Walked: Edit → the New form filled from the draft → Save tax → the same row, no longer a draft |
| `DEF-RAT-9306` | 1.5 / 1.6 / 4.2, the right-hand THIS TAX panel | *On a $60.00 bill $0.00* for a per-meter or per-unit tax — a confident wrong figure | **2.479.0**. Walked: the panel reads a dash |
| `DEF-RAT-9304` | 6.2, Plans tab | Tab read **Plans 9** over a table of **7 plans** | **2.479.0**. Walked: tab 7, foot 7 |
| `DEF-RAT-9307` | 5.4, the issued October bill | The clerk typed Bill label *County tax*; the bill line reads *Tax County utility tax*. The bill label never reaches a bill | **FIXED 2.481.2** after the PO ruled *"Okay"* (CR §17; the issued November bill reads *County tax $1.20*). At the walk: **NOT FIXED — needs the PO.** The two files that write the line (`rating/selectors.py` `plan_tax_rules`, `rating/pricing/stages/compute_tax.py`) are on the human-owned money-path list, and every issued and frozen bill's wording depends on them |

## Noticed, not filed

* **An attachment on a plan that already binds the tax's authority is folded into the binding
  row and has no ×.** Adding 1.6 to *Small Commercial* (which binds the Texas Water Development
  Board) succeeded and changed nothing visible, and that attachment cannot be removed from the
  screen. `selectors.tax_plans` does this on purpose (its docstring: the binding is the fact that
  survives) and pricing de-duplicates, so no bill moves. 6.2 was walked on the walk plan, which
  binds no authority.
* **Every new tax reaches most plans on the day it is saved**, because the demo plans bind all
  seven authorities and a binding carries every tax that authority levies (`BR-RAT-113`). True to
  the rule; worth knowing before a real utility saves a 150% typo.
* The walk picked the first liability account offered (2200-01) for every tax; the account is the
  clerk's choice and was saved and shown as chosen.

## Golden tests (❄️ B4/B5)

`06-backend/tests/golden`: **before** (the walk's starting commit `ee308b443`) **25 passed, 1 xfailed**;
**after** (2.479.0) **25 passed, 1 xfailed**. No ❄️ figure was touched; no signed rule changed;
no RLS file was opened.
