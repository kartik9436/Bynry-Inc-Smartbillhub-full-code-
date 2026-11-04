# Re-walk on 2.494.0 → 2.495.2 — 210 of 210

Lane PLAN-REWALK, 2026-10-04, after the deposit size pick landed (the PO: *"re-run the plans walk after
deposit lands"*). Same plan (`05-prototype/plans-2026-10-03/web-walk.md`, 9 phases), same scripts
(`10-scripts/cr167_planwalk.mjs`, `10-scripts/cr167_planwalk_world.py`), same world and figures, on a
fresh PostgreSQL 16 database `sbh_planrewalk` (`migrate` + `seed_demo` + world `setup`). **The API ran as
`sbh_planrewalk_app`, NOSUPERUSER NOBYPASSRLS**, so RLS alone kept the two utilities apart. Chromium at
1440 as Dana. Results: `rewalk-2.494.0/results.json` (210 rows), `state.json`, `phase7-lookup.txt`,
`phase8-runs.txt`; 114 photographs in `rewalk-2.494.0/`, **the 44 drawn states under the images' own file
names** (all 98 of the first walk's names again, plus `rw-*` and `dep-*`). None blank; the new ones and
21, 24 were opened by eye.

**Builds.** Every phase was walked on **2.494.0**. After the one fix (`DEF-CUS-9524`, **2.495.2**) the
read-only phases — list, 4 (tabs), the new `rw`, 9 (Utility B) — and the deposit phase were walked again
on **2.495.2**; those photographs carry 2.495.2 in the frame, the rest 2.494.0. Between the two builds
nothing on the plan or account screens changed except the fix (the other commits were Work screens and
the map tiles' page policy).

## Phase table

| Phase | What | Checks | Pass | First walk (2.490.5) | Diff |
|---|---|---|---|---|---|
| 1 | Create 4 plans (Residential, Commercial, Fire, a draft finished) | 19 | 19 | 19/19 | none |
| 2 | Each step empty; each table with an empty row | 11 | 11 | 11/11 | none |
| 3 | Review shows every value | 11 | 11 | 11/11 | Review now marks TX State *Not charged to this plan's classes* and reads **2.00% combined** (was 8.25 %) — 2.490.6 |
| 4 | Six tabs (+ Units) | 26 | 26 | 26/26 | Charges tab / Taxes tile **2.00 %** (was 8.25 %) |
| 5 | Water schedule v2 from 01/01/2027 | 4 | 4 | 4/4 | none |
| 6 | Edit three ways, Publish a saved v2, Audit | 10 | 10 | 10/10 | none (the *Cancel* of the Publish v2 confirm still reads *Cancel* after the kit's new `cancelLabel`, CR-168) |
| 7 | Billing gets ONE version a day | 3 | 3 | 3/3 | identical lookups |
| 8 | Issued December and January bills | 9 | 9 | 9/9 | **identical figures** — Ruth $94.35 / $98.38, Carl $117.94 / $122.97, café $103.63; January now in ONE run (the world script's v2 carries the size rows), no `recycle` |
| 9 | Utility B; ten languages × nine screens | 97 | 97 | 97/97 | none |
| — | List search, Duplicate | 5 | 5 | 5/5 | none |
| **rw** | **New:** tax mark + combined (Review, Charges, Overview, API); Billing › Discounts after the grants | 7 | 7 | — | new |
| **dep** | **New:** deposit size pick on THIS walk's plan (`DEF-CUS-9521`) and `DEF-CUS-9524` | 8 | 8 | — | new; red on 2.494.0, green on 2.495.2 |
| **Total** | | **210** | **210** | **195/195** | 195 re-run, 15 new |

**Red runs (each filed first, red test, fix, walked again):**

| Where | What went red on 2.494.0 | Defect | Fixed in |
|---|---|---|---|
| dep, New account and Move-in | *Amount taken* read **600.0000** (photo `dep-02-new-2in-taken.png`; `dep-02-new-2in-taken-after.png` reads **600.00**) | **`DEF-CUS-9524`** (filed by DEP-PICK) | **2.495.2** `aa8c91904` |

**Walk-script errors (not product), corrected and re-read:** the first `rw` discounts comparison cut the
Billing tab's text from *SENIOR*, but the tab lists AUTOPAY first; the first `dep` Review check looked for
*$600.00* where New account's Review prints *Currency not known here* (`DEF-CUS-5114`, below).

## The new checks

**`rw` — 2.490.6 and the discount grants.** Review, Charges tab and Overview: TX State Utility Tax listed,
*Not charged to this plan's classes*, **2.00% combined** (photo `rw-detail-charges-tax-not-charged.png`); the
API serves `reaches_plan_classes` TX State `none`, Bexar `all`. Billing › Discounts (photo
`rw-detail-billing-discounts.png`): AUTOPAY 0.50 % 11/01/2026 – 10/31/2027, SENIOR 15.00 % 11/01/2026 – No
end, GL 4760, the same codes, values and dates as Review. *Enrolled* reads **5** for Autopay on the tab and
**0** on Review: it is the discount's own take-up across the utility (CR-167 §5.5 item 9), and the
automatic-enrolment sync ran when the plan was saved and enrolled the five seeded autopay accounts on the
sample plans. As specified, not a defect.

**`dep` — the deposit size pick on *Plan walk · Residential*** (`DEP-SIZE` 5/8" $150.00 · 2" $600.00).
New world command `cr167_planwalk_world.py vacant PW-RES <n> [size]` makes a vacant unit on the plan with
no meter. On 2.495.2:

| Check | Result |
|---|---|
| New account, U-00011 (no meter): *Meter size* offers *Water 5/8"*, *Water 2"*, smallest first, nothing picked | pass |
| 2" picked → Amount **600.00** | pass |
| Taken today → *Amount taken* **600.00** (`DEF-CUS-9524`) | pass (red on 2.494.0: *600.0000*) |
| Review names *Meter size Water 2"*, no 4-place figure | pass |
| Created: account deposit **$600.0000**, `deposit_size_class` **W-2** with who picked it, **$600.00** payment taken, audit `deposit.size_picked` | pass (AC-2026-00059) |
| Move-in, U-00012 (no meter): picker offered; 2" → **600.00**, *Amount taken* **600.00** | pass |
| New account, U-00010 (5/8" meter fitted): **$150.00**, no picker | pass |

Note: the `dep` units are extra units on PW-RES, so the plan's Units count reads **10** in the 2.495.2
photographs (3 in the first walk's phase 4 run, which was walked before they were made).

## Known, not re-reported

* **`DEF-CUS-5114`** (open) — New account's Review and the Deposit step's totals print *Currency not known
  here* for the deposit; on a VACANT unit the Move-in does the same (no outgoing account to read the
  currency from). The DEP-PICK lane's photo `deposit-pick/04-review-2in-600.png` shows the same sentence
  under a file name that says $600.
* **`DEF-RAT-9348`** (open) — the wizard-rail census (`wizardRailCensus.test.ts`) red on the Edit-a-tax
  step lists, red since `b71588e74` (2026-10-03); not ours.

## Golden

`06-backend/tests/golden`: **25 passed, 1 xfailed** before and after; `10-scripts/03-golden-verify.py`:
**33 PASS, 0 FAIL** before and after (both are document/engine checks this change does not touch — the
fix is the front end only).

---

# Plans — the full web walk (task 10) — COMPLETE, phases 1–9

`CR-167-BRC10` round 4 task 10 · walked 2026-10-03 on builds **2.490.1 → 2.490.5** · plan
`05-prototype/plans-2026-10-03/web-walk.md` · lane PLAN-WALK. Closed in `CR-167-BRC10` §18 (this walk)
and §19 (the close).

## How it was run

* **Database:** a fresh PostgreSQL 16 database `sbh_planwalk` (`migrate` + `seed_demo` +
  `10-scripts/cr167_planwalk_world.py setup`). **The API ran as a non-superuser, non-BYPASSRLS role**
  (`sbh_planwalk_app`, grants on the walk database only) — a superuser connection bypasses RLS, and on
  the first probe it showed the second utility's charge codes in the first one's form options. As the
  app role, RLS alone keeps the two utilities apart, as in production (`09-infra/02-aws-runbook.md`).
* **Front end:** `vite build --mode wolocal`, served by `07-frontend/server.mjs` (:5381 → API :8281);
  Chromium at **1440**, signed in as **Dana** (System Admin, Brazos Bend).
* **Scripts:** `10-scripts/cr167_planwalk.mjs` (phases `1`, `2re`, `1draft`, `1com`, `1fire`, `list`,
  `3`, `4`, `units`, `5`, `6`, `6pub`, `dup`, `bills`, `9b`, `9lang`, `20re`) clicks every screen and
  checks each "must be true" on screen, through the API and in the database;
  `10-scripts/cr167_planwalk_world.py` builds the world and does the back-office half (`assign`,
  `schedule_v2`, `lookup`, `run`, `recycle`). Raw results: `walk/results.json` (195 rows),
  `walk/state.json`, `walk/phase7-lookup.txt`, `walk/phase8-runs.txt`. 98 photographs in `walk/`,
  the 44 drawn states under the images' own file names; **every one opened, none blank.**

**The world (the walk's own figures, never signed law).** *Utility A* = Brazos Bend: water, sewer, trash
and fire switched on through the Settings act, then the product's own sample data (the four sample
schedules — water inclining tiers $4.00 · $6.50 · $8.00 per kgal, sewer 90 % of water at $5.00/kgal,
trash $15.00 per cart, fire capacity in six line sizes — base codes `BASE-W` $8.00, `BASE-S` $9.00,
`BASE-T`, `BASE-FIRE`, two taxes, six discounts), the seed's eight customer classes, and three codes
the walk names: `DEPOSIT` (by class: Residential $150.00, Commercial $300.00), `DEP-SIZE` (by size:
5/8" $150.00, 2" $600.00) and `LATE-CL` (by class: Residential 1.5 % min $5.00, Commercial 2 % min
$10.00). Utility A also sells electric (the seed's), so its form offers five services. *Utility B* =
Riverbend Water, provisioned with no plans. Accounts on the walk plans: Ruth Alvarez (11 Pecan Walk Way,
inside the city), Carl Jensen (13, **outside** — the plan's 25 % surcharge), a vacant unit (15), and
Riverside Cafe (31, commercial). 5/8" meters read 8 kgal a month.

## Final count

| Phase | What | Checks | Pass | Fail | Notes |
|---|---|---|---|---|---|
| 1 | Create 4 plans (Residential, Commercial, Fire, a draft saved half way and finished) | 19 | 19 | 0 | one DB row per plan throughout; list rows show version, from, to; only A's five services offered |
| 2 | Each step empty; each table with an empty row | 11 | 11 | 0 | each problem named; nothing typed lost; *All added.*; an abandoned form stores nothing |
| 3 | Review shows every value exactly | 11 | 11 | 0 | services, surcharge, codes, taxes, deposits by size and by class, discounts, minimum, version + from-date, start |
| 4 | Six tabs (+ Units) | 26 | 26 | 0 | tabs match Review; links open the right page; fold / Expand all / Collapse all; tiles; section Edit; tab in address; ← → |
| 5 | Water schedule v2 from 01/01/2027 | 4 | 4 | 0 | banner with the new rates; Priced as of 01/15/2027 new, today old — after **`DEF-RAT-9515`** |
| 6 | Edit three ways, Publish a saved v2, Audit | 10 | 10 | 0 | after **`DEF-RAT-9516`** (Fix a mistake corrected v2 on its first run) |
| 7 | Billing gets ONE version on 12/31/2026 and 01/01/2027 | 3 | 3 | 0 | PW-RES / PW-COM v1 then v2, PW-FIRE v1 both days |
| 8 | Issued bill runs, December and January | 9 | 9 | 0 | on screen, API and DB; base once per service; deposit assessed once, billed on neither |
| 9 | Utility B; ten languages | 97 | 97 | 0 | B: screen, API (404 on read/units/audit/write), form options, RLS; 10 languages × 9 screens, 0 English — after **`DEF-RAT-9518`** |
| — | List search, Duplicate | 5 | 5 | 0 | Duplicate makes one draft from the version it starts with (after `DEF-RAT-9516`); `DEF-RAT-9506` holds |
| **Total** | | **195** | **195** | **0** | rows replaced on a re-run hold the latest result; the red runs are listed below |

**Red runs before a fix (each is a defect filed first, then fixed, then walked again):**

| Phase | What went red | Defect | Fixed in |
|---|---|---|---|
| 1 draft | *Save as draft* on a reopened draft: `PATCH … → 422 rating.unknown_field (taxes)`, the walk timed out waiting for the saved panel | **`DEF-RAT-9514`** | 2.490.2 |
| 5 | the banner named only *This plan's v1 starts 11/01/2026*; water v2 from 01/01/2027 appeared nowhere | **`DEF-RAT-9515`** | 2.490.3 |
| 6 | *Fix a mistake* corrected **v2** and called it *v2 · today*; Audit named the edit *v2*; the tabs showed v2's $12.00 minimum today | **`DEF-RAT-9516`** | 2.490.4 |
| 9 (by eye, then by probe) | a corrected water v2 vanished from the banner; Japanese *Water, Sewerに25.00%*, *$4.00 – $8.00 per kgal* | **`DEF-RAT-9517`**, **`DEF-RAT-9518`** | 2.490.5 |
| 6 (brief) | `POST /plans/{draft}/versions/1/publish` | **`DEF-RAT-9510`** | 2.490.1 — walked: 409 `version_of_draft`, the plan stays a draft |

**Walk-script errors (not product), each corrected and re-read:** the step-2 version regex expected a
lower-case *v*; the empty-row check looked for an element id where the screen shows a sentence under the
table; the Commercial step-3 check looked for per-class figures that step 3 draws as *by customer class*
(as image 13 does — the figures are Review's); the language probe counted *Fire* inside the plan name
*Plan walk · Fire*; the January run first refused Ruth's and Carl's bills because **the world script's**
water v2 omitted the schedule's size rows (R3, rightly) — the version was corrected through the
product's correction act, and their January was billed on a second cycle because BR-BIL-005 refuses a
second run over the same cycle and period (said so in `cr167_planwalk_world.py recycle`).

## Phase by phase

**1 · Create.** *Plan walk · Residential* (`PW-RES`, Residential, owner-occupied, a class note; water
*Residential Water — Inclining tiers*, sewer, trash; 25 % outside-city on water and sewer; LATE + RECON;
TX State + Bexar; `DEP-SIZE`; Senior from 11/01/2026, Autopay 11/01/2026 – 10/31/2027; minimum $10.00;
from 11/01/2026) published — **one row, v1**. *Plan walk · Commercial* (`PW-COM`, water flat + sewer,
`LATE-CL` by class, Bexar, `DEPOSIT` by class, minimum $25.00) — one row. *Plan walk · Fire* (`PW-FIRE`,
Commercial + Industrial, *Sample — Fire capacity*: **2", 4", 6", 8", 10", 12" lines, per line per
month**) saved as a draft from the New form (image 23), reopened and published — one row throughout.
*Plan walk · Municipal* (`PW-MUNI`) **saved half way** with *Save draft & exit* on step 2, reopened by
Edit with name, code and the water row intact, a tax added, *Save as draft*, then *Publish plan* — one row
throughout (after `DEF-RAT-9514`). The list shows each with *V1 · 11/01/2026 · No end*.

**2 · Refusals.** Step 1 empty: *Enter the plan name.* / *Enter a code.* on their boxes and *Fix 2 things
first.*; step 2 empty row: *Choose a service in each row.*; step 3: *Choose a code, or remove it.*;
step 4: *Choose a deposit, or remove it.*; every typed value kept; *All added.* with *+ Add* disabled when
every service, both taxes and both deposit codes are in.

**3 · Review** matched every value entered, with a version pill and *from* date on each item (the seed's
taxes and LATE carry no start date, so they show the pill alone — data, rule 37).

**4 · Tabs.** Overview tiles open Charges/Units/Services; ← → and the address follow; the schedule name
opens that rate schedule; Services/Charges/Billing read the same sections and figures as Review; *Edit
Charge codes* opens `…/edit?change=change&step=2` on Charges. Units: 3 units (two occupied, one vacant),
search `u.q=`, *Vacant* = the one with no account, CSV = the whole filtered set.

**5 · Water v2 from 01/01/2027** (×1.10: $4.40 · $7.15 · $8.80 per kgal): two banner lines — the plan's
own start and *Water rate schedule v2 starts 01/01/2027. Usage charges $4.40 · $7.15 · $8.80 per kgal.*;
*Priced as of 01/15/2027* shows the new rates; today the old; the API the same.

**6 · Edit.** *Name and details*: description changed, same row, same version. *Change from a date*
01/01/2027, minimum $10.00 → $12.00: v1 ends 12/31/2026, v2 from 01/01/2027, nothing deleted, *3 units move
to v2*. *Fix a mistake* (budget billing on, reason typed): v1 corrected over **11/01/2026 – 12/31/2026**, the
old v1 row kept (superseded). Audit lists each with before → after; the opened edit reads *Plan v1 from
11/01/2026*. Commercial: *Save new version* (v2 draft, minimum $30.00) → details *v2 not published yet ·
Publish v2* → confirm *v1 ends 12/31/2026.* → published.

**7 · Billing's lookup** (`plan_versioning.version_on` and R1's candidates): PW-RES 12/31/2026 → v1
($10.00), 01/01/2027 → v2 ($12.00), **one candidate each**; PW-COM v1 ($25.00) / v2 ($30.00); PW-FIRE v1 both.

**8 · Issued runs** (`RUN-0003` December, `RUN-0004`/`RUN-0005` January):

| Bill | Water tier 1 | Water tier 2 | Water base | Sewer | Bexar 2 % | Total |
|---|---|---|---|---|---|---|
| Ruth, December `BL-2612-000101` | 5 × $4.00 = $20.00 | 3 × $6.50 = $19.50 | $8.00 | $9.00 + $36.00 | $1.85 | **$94.35** |
| Ruth, January `BL-2701-000105` | 5 × $4.40 = **$22.00** | 3 × $7.15 = **$21.45** | $8.00 | $9.00 + $36.00 | $1.93 | **$98.38** |
| Carl (outside, ×1.25), December `BL-2612-000102` | $25.00 | $24.38 | $10.00 | $11.25 + $45.00 | $2.31 | **$117.94** |
| Carl, January `BL-2701-000106` | **$27.50** | **$26.81** | $10.00 | $11.25 + $45.00 | $2.41 | **$122.97** |

December keeps the old figures after January was issued; January uses the new. One base line per service
on every bill; **no deposit line on any bill** and `deposit_assessed` stays **$150.00** per account (the café
**$300.00**, by class). The minimum bill ($10.00 / $12.00) is below every total, so it adds nothing here —
billing reads it per version (phase 7). TX State tax is not charged: it applies to commercial and
industrial only (`DEF-RAT-9519`, below).

**9 · Utility B and languages.** B's list: *0 plans*; API `?q=PW-` 0 rows; A's plan id → **404** on read,
units, audit and PATCH (A's description unchanged); B's form options carry none of A's codes or taxes; A's
address in B's browser: *This plan could not be loaded*. RLS (throwaway NOSUPERUSER NOBYPASSRLS role,
rolled back): no tenant 0 plans; as B 0 of A's plans and 0 versions; as A 5 walk plans. Ten languages ×
nine plan screens (list, New step 1, Overview, Services, Charges, Billing, Units, Audit, Edit): no English
probe word (the catalogue's words **and** the server's — *Water, Sewer, Trash, Fire, per kgal, per cart*),
no sideways scroll — **90/90**.

**Duplicate** (More ▾ on PW-RES): one new draft `PW-RES-2`, the source untouched, sewer/trash/water, no
units, no *Publish v1* banner on the draft (`DEF-RAT-9506` holds).

## The 44 images beside the photographs

Build in the frame: 2.490.1 (01–23), 2.490.2–2.490.4 (24–44) — each photograph is of the build named in
its own frame. Figures differ from the images everywhere by rule 37 (the images' figures are
illustrations); differences below are only those of shape.

| # | Image ↔ photo `walk/<same name>` | Verdict |
|---|---|---|
| 01 | List · all plans | **match** — columns Plan · Version · Services · Schedules · Base charges · Units · From · To · Status. Differs: the row action is the kit's eye icon (B14 rows-as-icons), not a › button; ten plans (the seed's six + four of the walk) |
| 02 | List · searched "water" | **match** — the image itself finds no plan named *water*. Differs: the kit's empty state *No results for 'water'. Clear filters* in place of an empty table with *No plan matches.* |
| 03 | List · no results | **match** (same empty state) |
| 04 | New · Details empty | **match** — Plan, classes (*Every customer class*), description, Intended for (three ticks + notes), THIS PLAN panel |
| 05 | Details errors | **match** — each box named, *Fix 2 things first.* (customer classes default to *Every*, so two boxes, not three) |
| 06 | Classes dropdown | **match** — *Every customer class* first, then the utility's eight |
| 07 | Details filled | **match** |
| 08 | Services filled | **match** — schedule, base $ + code, minimum, surcharge tick, V1 + from on schedule and base; monthly base total under the table |
| 09 | Row added | **match** |
| 10 | Row refused | **match** — *Choose a service in each row.* |
| 11 | All added | **match** — five services (A sells electric too) where the image has four |
| 12 | Surcharge on | **match** — 25 %, ticks on water and sewer |
| 13 | Charges filled | **match** — LATE pre-filled, RECON; taxes with rate, GL, what is taxed; the seed's taxes have no start date, so *V1* without *from* |
| 14 | Tax added | **match** — *All added.* after both of A's taxes (image: three) |
| 15 | Charge row refused | **match** — *Choose a code, or remove it.* |
| 16 | Row removed | **match** |
| 17 | Billing filled | **match** — `DEP-SIZE` priced by **Size** (5/8" $150.00 · 2" $600.00), Senior, minimum $10 |
| 18 | Discount added | **match** — offered from / until |
| 19 | Deposit row refused | **match** — *Choose a deposit, or remove it.* |
| 20 | Review top | **match** — re-taken (`20re`, an unsaved form) because the first shot had scrolled to the Starts box |
| 21 | Review full | **match** — plan facts, per-service base/minimum and usage tables, codes, taxes, deposits by size, discounts, billing terms, dates, *Save as draft · Publish plan* |
| 22 | Published | **match** — *Plan walk · Residential published · Live from 11/01/2026.* |
| 23 | Saved as draft | **match** — the Fire plan from the New form's *Save as draft* |
| 24 | Overview | **match** — tiles open tabs, intended for, versions table; **two** banner lines (`DEF-RAT-9515`: one per upcoming item) where the image draws one; the versions table also lists the superseded rows *Corrected* |
| 25 | More ▾ | **match** — Duplicate (live since 2.489.0), Retire |
| 26 | Services folded | **match** — one line per service, *Show sizes and blocks*, Expand all |
| 27 | Expand all | **match** — flat *Every size* base on this data |
| 28 | Priced as of 01/15/2027 | **match** — water **V2 from 01/01/2027**, $4.40 · $7.15 · $8.80 |
| 29 | Charges | **match** — codes by class/size, taxes with authority (CR-167 §5.5) |
| 30 | Billing | **match** — deposits by size, discounts with *Enrolled*, billing terms |
| 31 | Units | **match** — search, All · Occupied · Vacant, CSV; kit pager and column chooser |
| 32 | Units searched | **match** |
| 33 | Vacant only | **match** — the one unit with no account |
| 34 | Audit | **match** — filters, ▸ · When · Who · What · Change · Reason, words not ids |
| 35 | Changes underneath | **match** — the water schedule's new version, discounts, taxes |
| 36 | Row opened | **match** — Before · After · Version (*Plan v1 from 11/01/2026*) |
| 37 | Section Edit | **match** — Charge codes › Edit → *Change from a date*, step Charges |
| 38 | Edit · Name and details | **match** — code a fact, priced fields locked under *Services, charges and billing* |
| 39 | Name and details Review | **match** — *What changes* Description before → after, same version, *Save changes* |
| 40 | Change from a date · first step | **match** |
| 41 | Change from a date Review | **match** — *v1 · today 11/01/2026 – 12/31/2026 Gets an end date · v2 · new 01/01/2027 – No end*, *3 units move to v2 on 01/01/2027.* |
| 42 | New version published | **match** — *v2 starts 01/01/2027. Logged in Audit.* (the refused-reason state is CR-167 §14.2 j7's; not re-photographed) |
| 43 | Fix a mistake · first step | **match** |
| 44 | Fix a mistake Review | **match** — re-taken after `DEF-RAT-9516`: *v1 · today 11/01/2026 – 12/31/2026 Superseded, kept · v1 · correction … Replaces v1*, *Issued bills keep v1.* |

**44 of 44 match in shape**; the differences are the kit's (rule 44), the data's (rule 37), and one
deliberate change of ours (24: one banner line per upcoming item, `DEF-RAT-9515`).

## Defects

| Defect | Where | What the user saw | State |
|---|---|---|---|
| `DEF-RAT-9510` | brief (server gap) | publishing a draft plan's v1 through `…/versions/1/publish` failed with a server error | **fixed 2.490.1** (`efb80b41d`) — refused by name |
| `DEF-RAT-9514` | phase 1 draft | a draft edited only on a priced step could not be saved (*The plan was not saved*) | **fixed 2.490.2** (`d17337843`) |
| `DEF-RAT-9515` | phase 5 | a plan starting later never announced its schedule's new version | **fixed 2.490.3** (`de77848ff`) |
| `DEF-RAT-9516` | phase 6 | a plan not yet started read as its NEWEST version (tabs $12.00, Fix a mistake on v2, Audit *v2*, Duplicate $12.00) | **fixed 2.490.4** (`fbdd6d8ba`) |
| `DEF-RAT-9517` | phase 9 photo | a corrected upcoming schedule version vanished from the plan | **fixed 2.490.5** (`10d41e1ae`) |
| `DEF-RAT-9518` | phase 9 photo | English on the plan pages in other languages (folded line, banner rates, outside-city line) | **fixed 2.490.5** (`10d41e1ae`) |
| `DEF-RAT-9519` | phases 1, 8 | a Residential plan lists TX State tax (commercial/industrial only) and *8.25 % combined*; its bills charge 2.00 % | **filed, open (low)** — needs our choice of refuse-or-mark (CR §19) |

**Known and not re-reported (by the brief):** the deposit amount on New account until `DEF-CUS-5114`;
*Move units to another plan* — ruled NOT NOW.

**Seen, not filed:** a bill's Charges tab prints a water tier rate with four places (*$8.9375*, Carl's
January ×1.25) — Billing's display, outside the plan screens; the *v1 · today* label on Edit's *How it is
saved* for a plan that has not started (it is the version being edited; harmless).
