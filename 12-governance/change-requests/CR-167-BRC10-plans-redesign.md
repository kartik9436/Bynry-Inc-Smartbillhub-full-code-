# CR-167-BRC10 — Plans & Rates › Plans redesigned end to end: list, New plan form in five steps, details in six tabs and Edit with three choices, built from 44 desktop images

**Raised:** 2026-10-03, by the Product Owner, in chat, over the review of the mock-up (artifact
`GYbqQEdpgxKZCm9Mp3MY3d`, approved at v10 plus two late removals), ending in a GO. The rulings are
the two decision-log rows of 2026-10-03 headed *"PLANS REDESIGN — DRAWING APPROVED, NOT A GO TO
BUILD …"* and *"GO ON THE PLANS REDESIGN (`CR-167-BRC10`) …"* (commit `ed47eaddc`); nothing they
settle is put back to the PO (hard-won law 13).
**The drawing:** `05-prototype/plans-2026-10-03/` — `README.md` (the 15 rulings, the checks, the
10-task plan and the index of 44 images), `images/01…44`, `plans-mockup.html` (an index, never the
specification — B14 rule 42), `web-walk.md` (task 10).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in
`12-governance/14-id-reservations.md`). The number is the one the PO's GO row already carries;
`10-scripts/allocate.py cr --verify 167` answers TAKEN only because of that row and its commit
subject — on 2026-10-03 `git log --grep CR-167` over every origin ref finds only `ed47eaddc`, and
`git grep CR-167` over every origin ref finds only this branch's decision log.
**Classification:** **MAINTENANCE** (`12-governance/22-product-maintenance-process.md`) — a user can
create, view and edit a plan today, so a live screen redrawn end to end is maintenance, borrowing
only the drawing step from Build; REPRODUCE comes before any fix (§6). Screen problems are defects.
The parts the product never did — deposits named on a plan from a charge code, a version and
from-date on every referenced item, "Priced as of" a date, a Units tab with search and CSV, an Audit
that opens to before → after — are change and are carried here.
**Touches 🔒 rating** (plan versions, the price read billing uses, migrations): HUMAN-REVIEW-PENDING
regime; golden tests must not move.
**Out of scope by ruling:** *"Move units to another plan"* — PO: *"not now"* (ruling 15). It is not
planned, drawn or built here.

Shape copied from `CR-165-BRC10` (taxes & fees) and `CR-166-BRC10` (discounts), the same round.

**Two lanes write this file in round 1, each owning only its sections:** lane PLAN-CR owns §0–§6
and §8; lane PLAN-SRV owns §7 (the server's answers and the API contract).

---

## 0 · What arrived, in the requester's words

The request, from the two decision-log rows of 2026-10-03:

> *"dont start the work on plan - im just given you details so that we can build redesign - we have
> to reduce 3 of steps in plan create"* · *"I want you to write details of plan redesign to repo and
> complete 1 · Prepare 1 Drawing images … They go into the repo as the official drawing."* ·
> **GO:** *"GO: build the plans redesign now."* · *"conitnue to build discount and plans"*.

The fifteen rulings, verbatim from `05-prototype/plans-2026-10-03/README.md` (the drawing column is
what the approved images do):

| # | PO said | What the drawing does |
|---|---|---|
| 1 | *"dont start the work on plan … we have to reduce 3 of steps in plan create"* | 8 steps become 5 one-word steps: **Details · Services · Charges · Billing · Review**. Edit uses the same form, with three "What to change" cards: **Name and details** (same version), **Change from a date** (new version), **Fix a mistake** (same dates, with a reason). |
| 2 | *"i dont want to loose any details from Create, edit or list or view"* | Every input in today's 8 steps has a home: Details = basics + classes + intended-for + eligibility notes; Services = services + rate schedule per service + surcharge; Charges = charge codes + taxes; Billing = deposits + discounts + budget billing + minimum bill; Review = dates + publish. The details tabs are **Overview · Services · Charges · Billing · Units · Audit** — Units, not Accounts, because a plan attaches to units. |
| 3 | *"in create we use Table array for selections, at many palces we want to keep that behaviou"* | Services, charge codes, taxes, discounts, deposits and notes are each a table array. |
| 4 | *"Customer classes * - Drop down - all or multiple selections"* | One tick dropdown, with "Every customer class" first. |
| 5 | Intended for: *"B Keep both exactly as today (reminders only)"* | The three ticks AND the notes stay. They are reminders only and never enforced. |
| 6 | *"unable to add utility services … this table UI should imporve Drop down size add behaviour etc - it should be table array"* | Full-size controls in the row, a red × to remove, "+ Add …" under the table, disabled with "All added." when nothing is left. An empty row is refused by name. |
| 7 | *"Why dont we show base charges and code with rate schedule itself … base and minimum from rate schedule - update step 2"* | The step-2 service row shows the base ($ and base code) and the minimum from the picked schedule, with the monthly base total under the table. There is no base section on Charges. |
| 8 | *"on rate schedules, Base charges, charge codes, discounts, tax - on all show version and effective date"* | Every referenced item shows a version pill and "from MM/DD/YYYY" in the form rows, on Review and on the details tabs. |
| 9 | *"base code based on sizes, rate schedule based on sizes or tiered or charges based on customer class or sizes, we did not add dposites anywhere … table format … improve how it will be displayed at review"* | Review is tables: plan facts; per service, the base and minimum by size and the usage blocks or per-size rates; charge codes by class or size; taxes; **deposits** by class or size (a new table array on Billing); discounts; billing terms. |
| 10 | *"on last page of review youa re not giving publish plan option"* | Review ends with **Save as draft** and **Publish plan**. When editing, these are **Save new version** and **Publish new version**. |
| 11 | *"similar to review page of add plan - in details view this service field does not help - how you will align this"* | The details Services, Charges and Billing tabs render the SAME sections as Review. **Build note: one shared component for both.** |
| 12 | *"can we use base charges and usage charges vocabalary - to keep in line with rate schedule"* | "Base charges" and "Usage charges" everywhere, including "Monthly base charges". |
| 13 | *"update teh artifact - How I'd improve the plan details page"* | Every name is a link. Services fold to one line, with Expand all. A banner names an upcoming version. "Priced as of" a date. Tiles open their tab. A section's Edit opens that step. The header is sticky. The tab is kept in the address. Units has search, an occupancy filter and CSV. Audit has filters and rows that open to before → after. Arrow keys move between tabs. |
| 14 | *"remove Try a bill"* | Removed. |
| 15 | Move units to another plan: *"not now"* | Taken out: no selection column and no Move button on Units. It is a later item. |

## 1 · Classified

**MAINTENANCE, with change carried.** Problems on today's screens are defects, filed in §6 before
anything is fixed. What the product never did (deposits named on a plan, item versions on every
reference, priced-as-of, the Units tab's search/filter/CSV, Audit before → after, the three Edit
choices on one form) is change. **Fast path does not apply:** it touches rating (🔒), money (which
plan version and which item versions price a bill on a date) and stored rows (plan versions,
deposit bindings).

## 2 · What signed statements it touches

* **The 2026-09-08 ruling `CR-087` §5 — *"please note in plan - we dont need these - we have added
  them in charge code"*** (the late-fee and deposit blocks left the plan; decision log line
  ~51763: *"a plan names charge codes; the charge code carries the money and everything that varies
  it"*). → **STANDS, and ruling 9 completes it rather than reversing it.** The drawing's Deposits
  table (images 17, 19, 21, 30) PICKS a deposit CHARGE CODE (`DEPOSIT · Security deposit`, `V2`,
  *Priced by Customer class*, Residential $150.00 / Commercial $300.00) — it does not bring back a
  typed amount per class. *"We did not add deposits anywhere"* is the PO observing that after
  2026-09-08 a plan could no longer NAME its deposit code at all; Billing gives it that place. The
  late fee stays where `CR-087` put it: a charge code on Charges (image 13's `LATE`, *by customer
  class*). How a deposit charge code is bound to a plan, and what happens to the stored
  `plan_deposit_rules` rows, is the server's answer (§7).
* **`BR-RAT-020` / `BR-RAT-023`** (CONFIRMED; deposits v1 = fixed $ per consumer category, schedule
  PLAN-level in `plan_deposit_rules`, built 2026-08-28 `DEF-202`). → **The plan-level placement
  STANDS** (the plan still names its deposit); **where the dollar figure lives moved to the charge
  code on 2026-09-08** and this CR builds the naming half. No figure changes: a $150.00 Residential
  deposit stays $150.00. Whether `plan_deposit_rules` stays the store the customers lane reads
  (`BR-CUS-023`) or is fed from the named code is §7's question and must not be assumed.
* **`BR-RAT-1011`** (CONFIRMED, finance re-signed 2026-09-07; the late fee comes from the charge
  code the plan names, none named = zero). → **STANDS.** The drawing names `LATE` on Charges only.
* **`BR-RAT-1016`** (PO 2026-09-17: *"EDIT while it has priced nothing · CORRECT over the SAME
  window … · CHANGE over a NEW window when prices move"*). → **STANDS; the drawing obeys it.**
  Images 38–44's three cards (*Name and details · Change from a date · Fix a mistake*) are these
  verbs. Today the wizard carries them as a two-value `edit_intent` select on step 8 (§5).
* **`BR-RAT-037`** (CONFIRMED; every change to an in-force plan is a new version with a required
  reason). → **STANDS.** *Fix a mistake* asks for a reason (image 44); *Change from a date* makes a
  new version (images 40–42). Whether *Name and details* on a published plan writes a version row
  is §7's to confirm against this rule — the drawing says *"Saved on this version"* (image 38).
* **`BR-RAT-043`** (CONFIRMED; eligibility is ADVISORY) and **`BR-RAT-097`** (eligibility authored
  as Attribute · Operator · Value rules; whether a rule blocks is unruled, `OQ-304`). → **STAND;
  ruling 5 restates them** — *"reminders only"*. The drawing's *Intended for* panel (image 7) shows
  the three ticks AND a notes table array (Attribute · Operator · Value). ⚠ **The three ticks were
  REMOVED as controls by `BR-RAT-097`** (their stored values are preserved and re-posted,
  `legacyEligibilityFlags`); ruling 5's *"keep both exactly as today"* was given on the mock-up,
  which drew them. **Our reading (law 13, recorded here, not asked):** the PO chose option B over a
  drawing that showed the ticks, so the ticks come back as controls writing the SAME three stored
  keys (`cap_proof`, `min_demand_25kw`, `owner_occupied`) the blob already carries — nothing new is
  stored and nothing is enforced. See §6 for what today's screen actually shows.
* **`BR-RAT-088`** (amended 2026-09-30; a service with no base charge bills $0.00 with a warning) and
  the 2026-09-08 *"we might have multiple base charges so in review we will show the correct
  ones"*. → **STAND.** Ruling 7 moves the base display into the step-2 service row; the base still
  comes from the schedule / charge code, never typed on the plan (`base_charge` stays preserved,
  never edited).
* **`BR-RAT-102`** (the plan decides whether an outside-city surcharge applies and how much). →
  **STANDS.** Image 12: the yes/no and the percent stay on Services, and the per-service exemption
  becomes a *Surcharge* tick in each row.
* **`BR-RAT-890`** (a plan cannot be published without a start date). → **STANDS.** The dates move
  to Review (image 21, *Starts \** required).
* **`BR-RAT-031`** (a draft may be saved half-typed). → **STANDS.** *Save draft & exit* stays in the
  header of every step (images 4–21) and *Save as draft* ends Review.
* **No ❄️ B4/B5 figure moves.** The drawing changes where things are set and shown, not any
  arithmetic. The two checks the README raises about money on a BILL (BASE-S / BASE-FIRE possibly
  counted twice; four base codes resolving on one residential water base) are lane PLAN-SRV's, in
  §7; if either proves to change a bill, it goes to the PO with a figure before anything is fixed.

## 3 · Impact across the ten surfaces

| # | Surface | Impact |
|---|---|---|
| 1 | Screens | `PlanWizard.tsx` (New and Edit, 5,407 lines), `PlanDetail.tsx` (1,864), `PlansTab.tsx` (list), `PlanSummaryCard.tsx` (1,130, today's shared summary). New: one shared plan-sections component (ruling 11), used by Review and by the Services / Charges / Billing tabs. |
| 2 | API | Plan read/write (deposits named on a plan; version + from-date on each referenced schedule, base code, charge code, tax, discount, deposit); a "priced as of" read; units-on-plan paged with search, occupancy filter and CSV; plan audit as before → after with names. **Contract: §7 (PLAN-SRV).** |
| 3 | Data | Possibly a binding of deposit charge codes to a plan (or reuse of `plan_charge_rules`); nothing else is expected to need a column. 🔒 migration ordering if one is added. §7 decides. |
| 4 | Business rules | §2: none reversed. `BR-RAT-023`'s Built-in cell and `CR-087` §5's Review clause get a dated note when task 3 lands the deposit binding. |
| 5 | Billing / money | One plan version per date (README task 3 and web-walk phase 7); the BASE-S/BASE-FIRE and four-base-code checks. No signed figure is expected to move; if one does, it stops for the PO. |
| 6 | Tests | `PlanWizard.test.tsx`, `cr087PlanWizard.dom.test.tsx`, `planWizardBetaWalk.dom.test.tsx`, `planWizardBoundBase.dom.test.tsx`, `planWizardTables.dom.test.tsx`, `planUntouchedSave.dom.test.tsx`, `PlanDetail.test.tsx`, `PlanSummaryCard.test.tsx`, `PlansRatesPage.test.tsx` all assert the 8-step shape or today's detail page and will be rewritten, not deleted, case by case (§8). Back-end plan tests in `06-backend/apps/rating/tests/`. |
| 7 | Languages | All eleven catalogues: the `rating.plan.*` keys for five steps, six tabs, the Edit cards and Review (task 9). Keys retired through `10-scripts/i18n_fanin.py`. |
| 8 | Open questions | Both directions. `OQ-304` (does an eligibility rule block) stays OPEN and is not touched — ruling 5 says *reminders only*. No question is answered by this CR; none is created by round 1 (judgments are ours, §2, §5). |
| 9 | Demo fixture | `seed_demo` / `load_sample_data --tenant brazosbend` plans (Sample — Residential, etc.) must show deposits and item versions once task 3 lands; the walk (task 10) needs a deposit charge code and a schedule with a future version. |
| 10 | Other modules | Customers reads a plan's deposit (`BR-CUS-023`, `plan_deposit_rules`); billing reads the plan version for a service date; the New Connection wizard and account Change plan pick plans. None of their screens changes; their reads must keep answering the same (task 3). |

## 4 · What is built today and becomes wrong

Measured on build **`2.481.6`** (branch tip `e7998c960`), the files actually mounted — `App.tsx`
routes `plans-rates/plans/new` and `plans-rates/plans/:planId/edit` to `PlanWizard`, and
`plans-rates/plans/:planId` to `PlanDetail`; the list is the Plans tab of `PlansRatesPage`.

| What | File (lines) | Today | Becomes |
|---|---|---|---|
| New / Edit form | `07-frontend/src/features/rating/PlanWizard.tsx` (5,407) | **Eight steps** — `PLAN_WIZARD_STEPS = basics · services · schedules · charges · taxes · discounts · eligibility · review` (line 211), labelled *Basics · Services · Rate schedules · Charges · Taxes · Discounts & billing · Eligibility · Review & activate*; *"Eight steps · takes about 5 minutes."* under the title. Edit carries a *Change the plan / Fix an error* radio on step 1 (`edit_intent`) and one *Publish plan ✓* at the end. | **Five one-word steps** *Details · Services · Charges · Billing · Review* (ruling 1, images 04–23); Edit opens on *What to change* with three cards, and *Change from a date* / *Fix a mistake* drop the Details step (images 38–44). Every selection a kit `TableArray` (ruling 3). |
| Shared summary | `PlanSummaryCard.tsx` (1,130) — *"The price"*, Charge codes, Discounts, Taxes, Other terms; used by step 8 and by the details Overview | One read for both, but drawn as the r10-era summary, money without `$`, a garbage row when no late fee (`DEF-RAT-9328`) | Replaced by the **one shared plan-sections component** (ruling 11): Plan · per-service sections · Charge codes · Taxes · Deposits · Discounts · Billing terms — used by Review (21) and the Services / Charges / Billing tabs (26–30). |
| Details | `PlanDetail.tsx` (1,864) | **Three tabs** `PLAN_DETAIL_TABS = overview · units · audit` (line 268, `CR-087` D5 cut eight to three); Duplicate (disabled) · Edit · Retire as three buttons; four KPI tiles of which two state an absence; `?tab=` kept in the address with retired names mapped (`RETIRED_PLAN_TABS`). | **Six tabs** *Overview · Services · Charges · Billing · Units · Audit* (ruling 2); *Edit* + *More ▾* (Duplicate, Retire) (image 25); tiles open their tab; banner for an upcoming version; *Priced as of*; sticky header; arrow keys (ruling 13). `RETIRED_PLAN_TABS` must keep old bookmarks working — `?tab=charges` etc. now land on real tabs. |
| List | `PlansTab.tsx` | Columns *Plan · Services included · Rate schedules · Base charges · Accounts · Status · Actions* (+ hidden *Code*, *Effective from*); a paragraph above; row actions pencil *New version* and *Archive* (+ *Publish*, *Delete* on drafts) | Image 01: *Plan (name, code · class) · Version · Services · Schedules · Base charges · Units · From · To · Status · ›*. |
| Tests that assert today's shape | `PlanWizard.test.tsx`, `cr087PlanWizard.dom.test.tsx`, `planWizardBetaWalk.dom.test.tsx`, `planWizardBoundBase.dom.test.tsx`, `planWizardTables.dom.test.tsx`, `planUntouchedSave.dom.test.tsx`, `PlanDetail.test.tsx`, `PlanSummaryCard.test.tsx`, `PlansRatesPage.test.tsx` | Assert eight steps, three tabs, today's copy | Rewritten case by case in the task that replaces the screen; **a case that guards a stored fact** (`planUntouchedSave` — a rename must not clear preserved fields, DEF-422) **is kept and re-pointed, never deleted.** |
| Server facts the screen leans on | `apps/rating/services.py` | `default_late_fee_charge()` (line 1073) writes `LATE` onto every new plan; `PLAN_PENALTY_FIELDS` and `plan_deposit_rules` are stored and re-posted unchanged; `plan_tax_rules` binds jurisdictions OR attaches taxes (`PLAN_TAX_RULE_FIELDS`) | Unchanged by the screen work; how deposits, item versions and *priced as of* are served is §7. |

**Data already written that the new screens must read correctly:** plans whose `late_fee_charge`
was set by default (every plan since `CR-078`), plans whose eligibility blob carries the three
retired flags or `rules` whose values are class **ids** (`DEF-RAT-9285`), `plan_deposit_rules` rows
typed per class before 2026-09-08, and `plan_tax_rules` bindings to jurisdictions with no tax under
them (`DEF-RAT-9329`). **Lanes building right now:** the discounts walk (`CR-166-BRC10`) on the
same branch; it touches no plan file.

## 5 · The field map — every input today → its new home

**How it was built:** every control on today's screens was read off the running app by
`10-scripts/cr167_plans_before_walk.mjs` (its `CONTROLS …` lines in
`08-qa/plans-2026-10-03/before/walk-output.txt` and `walk-output-new.txt`), not from the source;
fields the server stores with no control were read from `PlanDraft` and `rate_plans`. The home is
taken from the IMAGE named (B14 rule 42). **F** = form (New and Edit), **L** = list, **V** = details
page, **S** = stored with no control today.

### 5.1 The form (today's 8 steps)

| # | Today (step · control) | New home | Image |
|---|---|---|---|
| F1 | 1 · *Change the plan / Fix an error* radio (Edit only) | Edit · *What to change* cards: *Change from a date* / *Fix a mistake*, plus the new *Name and details* | 38, 40, 43 |
| F2 | 1 · Plan name (customer-facing) * | Details · Plan name * | 07 |
| F3 | 1 · Plan code (internal) * | Details · Code * | 07 |
| F4 | 1 · Customer class — *Add a class…* select + chips with × (empty = *Every customer class*) | Details · Customer classes * — one tick dropdown, *Every customer class* first | 06, 07 |
| F5 | 1 · Description shown to customer | Details · Description for customers | 07 |
| F6 | 2 · *Add a service…* select + chips with × | Services · table array, Service column, red ×, *+ Add service*, *All added.* | 08–11 |
| F7 | 2 · Do outside-city premises pay more? (No / Yes) | Services · Outside city limits · *Outside-city premises pay more* | 12 |
| F8 | 2 · How much more (%) | Services · Surcharge * (%) | 12 |
| F9 | 2 · Services surcharged — chips with × | Services · *Surcharge* tick in each service row | 08, 12 |
| F10 | 3 · Rate schedule for <service> (one select per service) | Services · Rate schedule column of the same row, with version pill and *from* date | 08 |
| F11 | 4 · Charge code — type-ahead + *+ Add* | Charges · Charge codes table array, *+ Add charge code* | 13, 15 |
| F12 | 4 · × on a charge row | Charges · red × | 16 |
| F13 | 5 · Tax or authority — type-ahead + *+ Add* | Charges · Taxes table array, *+ Add tax* | 13, 14 |
| F14 | 5 · × on a tax / authority row | Charges · red × | 14 |
| F15 | 6 · Discount — type-ahead + *+ Add* | Billing · Discounts offered table array, *+ Add discount* | 17, 18 |
| F16 | 6 · Offered from — <discount> | Billing · Discounts · Offered from | 17, 18 |
| F17 | 6 · Offered until — <discount> | Billing · Discounts · Offered until | 17, 18 |
| F18 | 6 · × on a discount row | Billing · red × | 18 |
| F19 | 6 · Offer budget billing on this plan | Billing · Billing terms · Offer budget billing | 17 |
| F20 | 6 · Minimum bill for the whole plan | Billing · Billing terms · Minimum bill ($ prefix, 2 places) | 17 |
| F21 | 7 · Note · Attribute | Details · Intended for · notes table array, Attribute | 07 |
| F22 | 7 · Note · Operator | Details · notes · Operator | 07 |
| F23 | 7 · Note · Value | Details · notes · Value | 07 |
| F24 | 7 · *+ Add a note* | Details · *+ Add note* | 07 |
| F25 | 7 · × on a note | Details · red × | 07 |
| F26 | 7 · Effective from * | Review · Dates · Starts * (Edit › Change: *New version starts* *) | 21, 41 |
| F27 | 7 · Effective to | Review · Dates · Ends | 21, 41 |
| F28 | 8 · Reason for this change * (published plan) | Review · Reason * on *Change from a date* and *Fix a mistake* | 41, 44 |
| F29 | 8 · *Edit Basics … Edit Eligibility* (7 links) and *Edit Effective from* | Review · *Edit* on each section; details · a section's *Edit* opens that step | 21, 37 |
| F30 | 8 · *Publish plan ✓* | Review · *Publish plan* (New) / *Publish new version* (Edit › Change) / *Save correction* (Fix) | 21, 41, 44 |
| F31 | header · *Save draft & exit* | header · *Save draft & exit*, and Review · *Save as draft* / *Save new version* | 04–21, 23, 41 |
| F32 | header · *Archive* (Edit only) | details · *More ▾* · Retire | 25 |
| F33 | footer · Cancel / Back / Continue | the same | 07, 08 |
| F34 | 2 · *Switch more services on in Settings* | Services · *Switch more services on ↗* | 08 |
| F35 | 4 · *Not listed? Define it in Charge codes →* | Charges · *Not listed? Define it ↗* | 13 |
| F36 | 3 · *Open Accounting settings* (under the GL column) | **no drawn home** — the GL itself moves under the service (*GL 4110*) | 08 |

### 5.2 Stored on a plan with no control today

| # | Stored | New home | Image |
|---|---|---|---|
| S1 | `late_fee_charge` — set to `LATE` by `default_late_fee_charge()` on create; no control since `CR-087` D3 (`DEF-RAT-9328`) | Charges · Charge codes table array, a row like any other (removable — `BR-RAT-1011` *settable AND clearable*) | 13, 21, 29 |
| S2 | `deposit_rules` — typed $ per customer class (`plan_deposit_rules`), no control since 2026-09-08 | Billing · **Deposits** table array, picking a deposit **charge code** priced by class or size (ruling 9; §2). What becomes of the typed rows is §7's. | 17, 19, 21, 30 |
| S3 | `penalty_rule` — `late_fee_min`, `late_fee_pct`, `grace_days`, `grace_mode` (`plan_penalty_rules`) | **No drawn home, and none today** — `CR-087` §5 moved the late fee's terms to the charge code; carried unchanged on save (DEF-422) | — |
| S4 | eligibility's three retired flags `cap_proof`, `min_demand_25kw`, `owner_occupied` (shown read-only on details as *No*) | Details · Intended for · the three ticks, as controls again (ruling 5; §2 records our reading) | 07 |
| S5 | `base_charge`, `amount_override`, `rate_override` — preserved, never edited (DEF-422, BR-RAT-094) | Not shown; carried unchanged on save | — |
| S6 | `account_subtype_id` | Not shown; carried unchanged on save | — |

### 5.3 The list

| # | Today | New home | Image |
|---|---|---|---|
| L1 | Search plan name or code | Search | 02, 03 |
| L2 | *All* chip | *All* | 01 |
| L3 | + Filter · Status (Draft · Published · Archived) | + Filter ▾ | 01 |
| L4 | + Filter · Service | + Filter ▾ | 01 |
| L5 | Column chooser (show/hide, ↑↓, Reset table) | ▦ | 01 |
| L6 | Download CSV | ↓ | 01 |
| L7 | Sort by Plan / Accounts / Status | sortable heads (kit) | 01 |
| L8 | Rows per page + ‹ › | *1–5 of 5* pager (kit) | 01 |
| L9 | Plan name link | Plan name link | 01 |
| L10 | Row pencil *New version* | row › → details → Edit | 01, 24, 38–44 |
| L11 | Row *Archive* | details · More ▾ · Retire | 25 |
| L12 | Row *Publish* (draft) | the draft's Review · *Publish plan* | 21 |
| L13 | Row *Delete* (draft) | **no drawn home** | — |
| L14 | History | History | 01 |
| L15 | + New plan | + New plan | 01 |
| L16 | Tabs Plans · Rate schedules · Charge codes · Discounts · Taxes & fees | the same | 01 |

### 5.4 The details page

| # | Today (control) | New home | Image |
|---|---|---|---|
| V1 | ← Plans & Rates | ← Plans | 24 |
| V2 | Duplicate (disabled) | More ▾ · Duplicate | 25 |
| V3 | Edit | Edit | 24 |
| V4 | Retire | More ▾ · Retire | 25 |
| V5 | Tabs Overview · Units · Audit | Overview · Services · Charges · Billing · Units · Audit | 24 |
| V6 | *Open Accounting settings* (one per service) | **no drawn home** — GL shown under each service | 27 |
| V7 | Units pager | Units pager *1–5 of 5 · Page 1 of 1* | 31 |
| V8 | Audit · Changes underneath · rows per page + pager | Audit · *All · Plan changes · Changes underneath* + From/To + ↓ | 34, 35 |

**Facts the details page SHOWS today, and where each is shown after** (ruling 2 covers "view"):
code and version (header pill, 24) · status (24) · effective from/to (header, Overview Starts/Ends, 24) ·
customer class (header and Overview, 24 — today unnamed, `DEF-RAT-9331`) · Units tile (24) · Services
tile (24) · Change already dated (banner, 24) · plan name, code, budget billing, minimum bill, base
charges, description (Overview grid and Billing terms, 24, 30) · per service: base, base codes,
schedule, usage model and rates (Services tab, 27) · GL per service (27) · charge codes: code, name,
amount, when (Charges tab, 29) · taxes: rate, applies to, combined (29) · discounts: code, name,
value (30) · outside-city surcharge (27, *Outside-city surcharge 25% on Water, Sewer*) · intended-for
flags (Overview, 24) · units: unit, premises, services, account, since, vacant (31) · versions:
version, who, when, reason, changes, status (Overview versions table and Audit, 24, 34–36) · changes
underneath: what, when, who, why (35).
**Removed by the drawing as text, not data** (README's own list): Revenue tile, Exceptions tile,
*Not recorded on a plan yet* (7), *How a plan works*, *Sample bill*, *Splitting by city limits…*, the
draft-schedule note, the softer-state note, *Cycle and due date — not settable per plan*.

### 5.5 Count, and every item with no home

**Controls today: 60** (form 36 · list 16 · details 8): **57 homed, 3 with no drawn home** (L13, F36,
V6). **Stored with no control: 6**: 3 gain a home (S1, S2, S4), 3 are neither shown today nor after
and are carried unchanged (S3, S5, S6). **Facts the details page shows today: 2 not drawn** (discount
take-up, tax authority). L12 and L13 are read from the source (`PlansTab.tsx`, draft rows only); no
draft was listed when the walk ran.

| Item | What we do (our judgment, law 13; recorded in the decision log row *"PLANS REDESIGN FIELD MAP"*) |
|---|---|
| **L13** Delete a draft (list) | A **draft's** *More ▾* offers *Delete draft* beside Duplicate (the drawn More ▾ is a published plan's). Delete stays refused for any plan ever billed (`BR-RAT-030`). |
| **F36 / V6** *Open Accounting settings* link | Dropped. The GL number stays under each service (images 08, 27); the GL is set on Settings › Accounting, which is not a plan detail. |
| **Discount take-up** (*Enrolled*, shown today on the form row and the details Overview) | Shown on the form row as drawn (image 17); the shared Discounts section keeps an *Enrolled* column on the details Billing tab too, so the details page loses no number. |
| **Tax authority** (*Texas Comptroller of Public Accounts — TX State Utility Tax*, *Level: State*) | The shared Taxes section shows the tax name as a link (image 29) with its authority in small text under it, so the authority is not lost. |

S3, S5 and S6 have no home and need none: they have no control today, are not shown today, and are
re-posted unchanged on every save, which `planUntouchedSave.dom.test.tsx` already guards and must
keep guarding.

## 6 · Today's problems, reproduced on PostgreSQL 16 and filed

**How:** build **`2.481.6`** (tip `e7998c960`); API `runserver 127.0.0.1:8131` on a private
PostgreSQL 16 database `sbh_plancr` (`migrate` + `seed_demo` + `load_sample_data --tenant
brazosbend`); SPA `vite build --mode wolocal` served on `5231`; signed in as Dana, System Admin;
Chromium at 1440 wide. Three scripts: `10-scripts/cr167_plans_before_walk.mjs` (list, details, Edit
steps 1–8 of *Sample — Residential*, New steps 1–2), `cr167_plans_before_walk_new.mjs` (a New plan
*Walk — Residential City* through all 8 steps, saved as a draft, reopened, published, changed),
`cr167_plans_before_walk_publish.mjs` (Publish on a changed published plan). Their full printed output
is `08-qa/plans-2026-10-03/before/walk-output*.txt`; **30 screenshots** in that folder, each opened and
checked not blank. Sample data: six published plans; *Sample — Residential* has Electric and Water,
75 units, LATE by default, three discounts, seven tax bindings (two taxes, 8.25%).

| # | Check (README / ruling) | Result | Evidence |
|---|---|---|---|
| P1 | **The view lists LATE as a charge code while edit step 4 lists other codes** | **REPRODUCED (same cause, this data)** — Overview and Review list `LATE · Late payment fee · 1.50% · 5.00`; step 4 reads *ON THIS PLAN · 0*, no LATE row, nothing to remove. Step 4 reads `plan_charge_rules` (0 rows); the view reads `rate_plans.late_fee_charge_id`, which `default_late_fee_charge()` set at create. On a NEW plan, Review prints *none · Charge codes · none · after the due date* / *No charge code names one*, and the saved plan then names LATE. (BASE-S / BASE-FIRE are not on this tenant — no sewer or fire service — so the second half cannot be photographed here.) → **`DEF-RAT-9328`** (high) | `d-overview`, `e4-edit-step4`, `e8-edit-step8`, `p8-new-step8-review`, `c9-…` |
| P2 | **Review counts contradict** (`DEF-RAT-9286`) | **STILL TRUE — referenced, not re-filed.** Review reads *Charges · 0 charge codes* above a LATE row, and *Taxes · 7 tax authorities* above two taxes (8.25%). | `e8-edit-step8` |
| P3 | **Minimum bill shown as 10.000000** (`DEF-RAT-9287`) | **STILL TRUE — referenced.** A draft saved with 10 reopens with `10.000000` in the box. | `r6-reopen-step6-minimum` |
| P4 | **Audit shows raw ids and JSON** (`DEF-RAT-9288`) | **STILL TRUE — referenced.** v2's change reads `account_type_ids[1]: — → 01a1023a-e195-7b10-…`, `base_charges_unavailable: — → differs_by_customer_class`, `minimum_bill_amount: 10.000000 → 12.000000`. (The JSON-blob form needs a discount change; not exercised.) | `v2-audit-after-change` |
| P5 | **Database id on eligibility** (`DEF-RAT-9285`) | **NOT REPRODUCED on 2.481.6 in step 7** — the note reads *Customer class is Residential* (`r7`). **But the stored value IS the id** (`rate_plans.eligibility = {"rules":[{"attribute":"customer_class","operator":"is","value":"01a1023a-e194-…"}]}`), so any reader without the class list prints the id — the Audit diff does; and the details page shows no notes at all (P7). Left OPEN, untouched; task 5 stores and shows names. | `r7-reopen-step7-notes`, `walk-output-new.txt` |
| P6 | **"Unable to add utility services … drop down size, add behaviour"** (ruling 6) | **PARTLY.** On this build and data, adding works: picking *Water* from the full-width *Add a service…* select makes a chip (`p2`). What the ruling asks for is absent: no table array, no *+ Add*, no *All added.*, no schedule, base or minimum in the row, and Continue on no service says only *"This step isn't finished. Fill in what's marked above"* — no box named (`n4`). The PO's *unable* was on 2.455.0 with four services; it is not reproduced here. → **`DEF-RAT-9332`** | `n3`, `p2`, `n4` |
| P7 | Details never names the class or shows notes | **REPRODUCED** — header and *Intended for* read *"Customer class Set, but the class cannot be named here yet — customer classes are kept with accounts."* though `GET lookups/account_types` serves eight classes; the stored note appears nowhere. → **`DEF-RAT-9331`** | `d-overview`, `v1-published-overview` |
| P8 | Step 5 Taxes | **REPRODUCED** — nine rows for seven bindings, five reading *No authority recorded* (two of those jurisdictions DO carry an authority name), head *ON THIS PLAN · 7*. → **`DEF-RAT-9329`** | `e5-edit-step5` |
| P9 | Publish after changing a published plan | **REPRODUCED** — the version IS written (v2 → v3, minimum 12.00 → 13.00, published) and the screen says *"We couldn't publish this plan. Only a draft plan can be published. This one is published."* with Retry. → **`DEF-RAT-9330`** (high) | `c9-change-publish-refused`, `walk-output-publish.txt` |
| P10 | Base shown two ways for one plan | **REPRODUCED** — step 4 *ELECTRIC 12.00 · from BASE-E*, Review and Overview *12.00 · 180.00 from BASE-E · BASE-E-COM · BASE-E-IND*, on a Residential plan; money without `$`. The screen half of the README's *four base codes* question, which PLAN-SRV traced to the card listing every active base code of the service in the catalogue and filed as **`DEF-RAT-9336`** (§7.1 (b)) — referenced here, not re-filed; `$` is in `DEF-RAT-9332` / `9334`. | `e4-edit-step4`, `e8-edit-step8` |
| P11 | Review ends in Publish only (ruling 10) | **The opposite of the words, the same gap:** *Publish plan ✓* IS on Review; *Save as draft* is not (only the header's *Save draft & exit*). → in **`DEF-RAT-9332`** | `p8-new-step8-review` |
| P12 | Form, list, details against the drawing | **REPRODUCED** → **`DEF-RAT-9332`** (form), **`9333`** (list), **`9334`** (details) | `e1`–`e8`, `n1`–`n4`, `l01`, `d-*` |

### Defects

| Defect | What | Task that fixes it |
|---|---|---|
| `DEF-RAT-9328` | Late fee invisible and unclearable on step 4; Review says none, plan charges LATE | 3 (one list of the plan's codes) + 4/5 |
| `DEF-RAT-9329` | Tax step: seven bindings drawn as nine rows, *No authority recorded* | 4/5 |
| `DEF-RAT-9330` | Publish on a changed published plan reports failure after writing the version | 3 + 8 |
| `DEF-RAT-9331` | Details never names the class, never shows notes | 7 |
| `DEF-RAT-9332` | The form against the drawing (8 steps, unnamed refusals, chips, no versions, no deposits, no ticks, no Save as draft) | 4, 5, 8 |
| `DEF-RAT-9333` | The list against the drawing | 6 |
| `DEF-RAT-9334` | The details page against the drawing (incl. 9288's raw diff) | 4, 7 |
| `DEF-RAT-9285`–`9288` | Already open (PO, 2026-10-03); 9286–9288 still true, 9285 latent — referenced, not re-filed | 5, 7, 8 |
| `DEF-RAT-9335`–`9337` | Filed by PLAN-SRV (§7.1): a named base code's bill stopped by another sized base code; the card listing every base code; base codes accepted as plan charge codes | 3, 4 (see §7) |

**Not this lane's, by the brief:** BASE-S / BASE-FIRE counted twice on a bill (answered NO, §7.1 (a)),
and four base codes resolving on one residential water base (§7.1 (b)) — lane PLAN-SRV.

## 7 Server answers and the API contract — PLAN-SRV

*(Owned by lane PLAN-SRV. Lane PLAN-CR writes nothing in this section.)* Round 1, 2026-10-03. Read
only, except two held tests that prove defects (§7.1). Line numbers at tip `e7998c960`.
Measured on PostgreSQL 16 (`sbh_plansrv`, `seed_demo` + `load_sample_data` + a probe utility with
water, sewer, trash and fire) with `10-scripts/cr167_plan_facts_pg.py` and
`10-scripts/cr167_base_checks_pg.py`.

### 7.1 · The README's two checks, on real bills

**Where it was measured.** The PO's beta utility is not reachable from a lane, and neither seeded
tenant holds four water base codes, so the checks were run on a throwaway probe utility,
`plansrv-rcp`, provisioned through the real signup service with water, sewer, trash and fire and
filled by the product's own sample data (49 accounts, two issued cycles). The plan is
*Sample — Residential* (`SCW-RES`), the same shape as the PO's *Residential City Plan*: water,
sewer, trash and fire. Two probe shortcuts are stated in the script's docstring: the four water
base codes are created through `create_charge` and then widened to every class with a column write
(the 2026-10-01 overlap guard, `rating.charges.base_already_covered`, refuses a NEW overlapping
base code and touches nothing already stored — which is how the PO's utility can hold four), and
the schedule's named base code is set with a column write.

**(a) BASE-S and BASE-FIRE listed as base AND as charge codes — counted twice? NO.**

The real issued bill, account `AC-2026-00025` on `SCW-RES`, September 2026, bill `BL-2610-000075`:

| Service | Line | Amount |
|---|---|---|
| Fire | 2 × 2" line, 1 × 6" line | $84.00 |
| Sewer | Base charge | $9.00 |
| Sewer | Usage — 90% of water volume | $27.00 |
| Water | Base charge | $8.00 |
| Water | Usage, tier 1 (0–5 kgal) | $20.00 |
| Water | Usage, tier 2 (5–15 kgal) | $6.50 |
| | **Total** | **$154.50** |

Then `BASE-S` and `BASE-FIRE` were attached to the plan as ordinary charge codes through
`services.update_plan` (accepted — nothing refuses it) and the same account and period priced again
with the bill engine (one-time preview): **the same six lines, $154.50. Sewer's $9.00 base appears
once; fire's base ($0.00 — fire is priced per line) adds no line.** The reason is in the code:
`billable_charge_codes` drops every `is_base` code from the fee route (`selectors.py:7838`; its docstring at `:7805`: *"letting it in here would bill $12.00 twice"*), and the base reaches the bill only through the
rate schedule. **No money moves.** What is wrong is the record and the screens: the plan stores a
base code as a charge code, Edit step 4 lists it and the plan's page hides it (`DEF-RAT-9286`,
already filed by the PO). Filed: **`DEF-RAT-9337`** (low) — refuse an `is_base` code in the plan's
charge codes by name and remove existing ones in round 2's migration.

**(b) "8.00 · 10.00 · 8.00 from BASE-W · BASE-W1 · BASE-W-COM · BASE-W-FIRE" — why four, and which
one does the bill charge?**

*Why four:* the plan screen does not ask the server which base the plan charges. The shared card
(`PlanSummaryCard.tsx:712–725`) filters the tenant's WHOLE charge catalogue for every active
`is_base` code of the service — so it lists every water base code the utility has, whatever its
class and whether or not the plan's schedule uses it. It also drops a code with no single figure
(BASE-W-FIRE is priced by size) from the amounts but not from the codes, so three figures sit
beside four codes. The server has served the right answer all along — the schedule's named code
per service (`plan_detail` `services[].base_charge_code`, `selectors.py:982`) and the base the
live path resolves (`_plan_base_total`, `:640`) — and `planSummaryFromDetail` drops it. Shown red
with the PO's own figure: `AssertionError: expected '8.00 · 10.00 · 8.00' to be '10.00'`. Filed:
**`DEF-RAT-9336`** (medium), held as `it.fails` in
`07-frontend/src/features/rating/planSummaryBaseCode.defRat9336.test.ts`.

*Which one the bill charges* — measured on the residential 5/8" account above, with BASE-W (8.00,
residential), BASE-W-COM (commercial, by size), BASE-W1 (10.00, every class) and BASE-W-FIRE
(every class, priced only for 1" and 2"):

| The water schedule … | What the bill does |
|---|---|
| names nothing | **REFUSED** — *"3 base charge codes for water. Scope them on Charge codes."* (BASE-W, BASE-W1 and BASE-W-FIRE all reach a residential account; `DEF-468`'s rule refuses rather than pick by catalogue order). |
| names BASE-W1 | should bill **$10.00** from BASE-W1 (`BR-RAT-1025`; the server's base read answers exactly that). **It is REFUSED instead** — *"R4: charge code 'BASE-W-FIRE' applies to this account and states no amount for connection size 'W-58'"*. |

The second row is a real defect on the money path: R4 (`resolution.resolve_charge_codes`,
`:2231`) prices EVERY applicable base code before `resolve_base_charge` narrows to the named one
(`:2471`), so a code the bill would never charge can stop it. Filed: **`DEF-RAT-9335`** (high),
held as `xfail(strict=True)` in
`06-backend/tests/test_def_rat_9335_unnamed_sized_base_code_does_not_stop_the_bill.py`.
⚠ **NOT FIXED, and it is for the PO in one line (7.5 B1)** because the fix turns refused bills into
billed ones: on the worked account the bill goes from *refused* to a $10.00 water base
($146.50 + $10.00 = $156.50 for September). It charges what the utility configured, and nothing
billed today changes.

**So, plainly:** four codes "resolve" only on the screen. A bill charges one code — the one the
rate schedule names — and when the schedule names none and more than one code reaches the
customer's class, the bill stops rather than guess. On the PO's Residential City Plan the bill charges
whichever code its water schedule names; if the schedule names none and two or more of those four
codes cover residential customers, every residential water bill on that plan is refused today.

### 7.2 · What the server does today, and what is missing

| | Question | What exists (file:line) | What is missing |
|---|---|---|---|
| a | **Is there a plan version a bill can be priced from?** | `plan_versions` (`apps/rating/models.py:2195`) is a FILING RECORD: number, reason, submitter, a JSON `snapshot`, and the correction chain (`OQ-RAT-12409` A). Its own docstring: *"`snapshot` IS THE CONTENT AND `plan_versions` IS INERT. Nothing that prices a bill reads this table"* (`:2226`) and *"THERE IS NO `effective_from`, DELIBERATELY"* (`:2233`, citing `OQ-324`). The bindings live ONCE per plan, in `plan_services`, `plan_rate_schedules`, `plan_charge_rules`, `plan_deposit_rules`, `plan_tax_rules`, `plan_discount_rules`, plus `rate_plans.minimum_bill_amount`, `outside_city_factor`, `budget_billing`, `late_fee_charge`, `effective_from/to`. | A dated plan version that OWNS its bindings. Today there is one set of bindings per plan and nowhere to put a second set that starts later. |
| b | **What does billing read for a plan, and on what date?** | R1 `resolution.resolve_plan` (`resolution.py:1131`) already picks *"the plan version in force on the service-period end date"* and refuses two (`rating.refusal.plansAmbiguous`) — but its candidates come from `resolution_catalogue.plan_version_facts` (`:193`), which returns exactly ONE candidate built from the `rate_plans` row. The live reads billing calls take **no date** for the plan's own bindings: `plan_rate_schedules(plan_id)` (`selectors.py:7466`), `plan_jurisdiction_pricing(plan_id)` (`:7610`, surcharge factor and exempt services), `deposit_rule_for(plan, class)` (`:9560`), `plan_ref` (`:6689`), `pricing_inputs` (`:6815`, the plan floor `:7544`). Reads that DO take a date: `billable_charge_codes(plan, date)` (`:7728`), `plan_tax_rules(plan, date)` (`:8612`), `plan_late_fee_terms(plan, class, date)` (`:9615`), `billable_discount_rules(account, plan, day)` (`:9845`) — but they date the CHARGE CODE's, TAX's or DISCOUNT's own version, never which of the plan's bindings applied. | Every plan-binding read above takes the service date and reads the plan version in force on it. R1's candidates become every non-draft version of the plan with its window. |
| c | **Can billing get two plan versions for one date?** | Not today, because there is only one. `update_plan` (`services.py:1709`) changes a published plan IN PLACE and LIVE on save (`version += 1`, `:1773`), and `_apply_plan_children` DELETES and re-creates the child rows (`services.py:1502`, `1503`, `1522`, `1533`). So a plan edit today re-prices every unbilled period of every unit on the plan, including periods that ended before the edit — which `OQ-323`'s ruling (2026-09-18: *"if we generate bill for 1 feb, it will take R1 rate"*) says must not happen for rates. | A database lock (exclusion constraint, `btree_gist` exists since `rating/0045`) over each plan's version windows for every version that can price, as `ex_discount_versions_no_overlap` does for discounts (`rating/0049`, `0061`). R1's existing two-version refusal stays as the second guard. |
| d | **Edit, three ways (BR-RAT-1016)** | Verb 1 (draft edits freely): `PATCH /plans/{id}` on a draft. Verb 2 (fix a mistake, same version number, reason): `POST /plans/{id}/corrections` → `correct_plan_version` (`services.py:1824`, route `api.py:339`) — built 2026-09-18; restates `version_no`, writes a `plan_versions` row with `corrects`/`superseded_by`, `rate_plans.version` does not move. Verb 3 (change): `PATCH` on a published plan with a reason → new version number, **live immediately**, no date. | *Name and details* on a live plan without a new version (today ANY field on a published plan bumps the version, `services.py:1723`). *Change from a date* with a start date, a draft state (*Save new version*) and a publish (*Publish new version*). |
| e | **Deposits on a plan** | `plan_deposit_rules` (`models.py:2057`): plan × customer class → one amount, **no charge code, no size, no version, no date**. Read by `deposit_rule_for` (`selectors.py:9560`) for the first bill (`billing/first_bill.py`) and by the counter deposit (`customers/deposit.py:526` `plan_standard_for`, ruled 2026-09-23). The charge code side already exists: `DEPO-R`/`DEPO-C` with `charge_type = refundable` are PLAN codes (`constants.py:74`), and a plan code can be priced by class or by size (`charge_prices`, PO 2026-10-01). | A way for a plan to NAME its deposit code (the drawing's Deposits table), and one read that answers the deposit for an account from that code. See 7.4 (A2) — this is where a PO confirmation is needed. |
| f | **A version pill and a from-date on every referenced item** | **Tax** — `taxes.version_no` + `effective_from` stored (`models.py:1751`, `:1778`). **Discount** — `discount_versions.version_no` + `effective_from` stored (`discounts.py:410`), the plan's offer window is `plan_discount_rules.available_from/to` (`discounts.py:846`). **Charge code (base, plan charges, deposits)** — no code-level number: each PRICE ROW (code × size × class) is counted v1, v2… in date order on read (`charge_prices._versions`, `charge_prices.py:220`). **Rate schedule** — NO number at all, deliberately: *"There is no ordinal — and there is no need for one"* (`selectors.tariff_version_labels`, `:1965`); a utility may store a free-text `version_label` (`models.py:483`) and the rate-schedule screen falls back to a derived ordinal (`:2566`). | One shape for every reference, `ref` (7.3), served by the server so no screen counts. Two numbering judgments (7.4 J3, J4): a schedule's number and a charge code's number. |
| g | **"Priced as of" a date** | `plan_detail(plan_id, as_of)` (`selectors.py:908`) already accepts `as_of` and uses it for the schedule minimum, charge-code size tables and discount terms — but `GET /plans/{id}` never passes it (`api.py:239`). The base total uses TODAY (`_plan_base_total`, `:640`). | `GET /plans/{id}?as_of=YYYY-MM-DD` picks the plan version in force on that date AND every referenced item's version in force on it. |
| h | **Base charge per service (ruling 7)** | The server already resolves the base the BILL will use: `_plan_base_total` (`selectors.py:640`) walks *plan → schedule → named code → `base_charge_from_charge_code`* — the live path — and `plan_detail` serves the schedule's NAMED code per service (`base_charge_code`, `:982`). The screens do not use it: `PlanSummaryCard.tsx:712–725` lists every active `is_base` code of the service in the tenant's catalogue. | Per service: the base code the bill will charge, its amount by size, its version and from-date, and the schedule minimum by size (7.3 `services[]`). |
| i | **Units tab (search, occupancy, CSV)** | `GET /plans/{id}/units` (`api.py:242`) pages in SQL (`plan_units_queryset`, `selectors.py:1317`) and already serves unit, premises, services, account, `vacant`, `assigned_from` (`:1356`). Its docstring: *"NO FILTERS, NO SORT, DELIBERATELY"*. | `q` (unit or premises), `f.occupancy=occupied|vacant`, `format=csv`. Occupancy is a customers fact, so the filter asks a customers seam for the occupied unit ids among this plan's units and filters in SQL. |
| j | **Audit as before → after, with names** | Two halves exist: the plan's own versions (`plan_versions(plan)`, `selectors.py:1779`, inside the detail) and *what moved underneath* (`GET /plans/{id}/bound-changes`, `api.py:287`, paged), which covers only schedules and charge codes (`BOUND_CHANGE_KINDS_UNCOVERED = ("tax", "discount")`, `selectors.py:1449`; `DEF-RAT-5738`). `DEF-RAT-9288` (raw ids and JSON on today's Audit). | One paged read, `GET /plans/{id}/audit`, with `kind=plan|underneath|all` and a date range, rows already in words. |
| k | **List columns (image 01)** | `GET /plans` rows carry `version`, `effective_from/to`, `services`, `base_charges` (+ `_display`, `_unavailable`), `accounts` (`selectors.py:738`). Sorts `name, accounts, status`; filters `status, service, customer_class` (`:119`). | `schedules` (count), `units` (count, the same number the Units tab counts), sorts `version, from, to, base_charges, units`. |
| l | **Upcoming-change banner (ruling 13)** | Nothing reads "the next version of anything this plan binds". | `upcoming[]` on the detail: the earliest future version of the plan or of any referenced item, with what changes. |
| m | 🔒 files the change touches | `apps/rating/models.py`, `services.py`, `selectors.py`, `resolution_catalogue.py` (R1 candidates — rating math), a rating migration after `0061` (🔒 migration ordering, RLS FORCE on any new table), `apps/customers/deposit.py` and `billing/first_bill.py` (deposit read, if A2 is confirmed). | Each ships HUMAN-REVIEW-PENDING with a ledger row; golden tests must not move; the one-version-per-date rule proved on PostgreSQL (law 14). |

### 7.3 · The proposed API contract (round 2 implements; names fixed once agreed)

**One reference shape, used everywhere a plan names something** (form rows, Review, details tabs):

```
ref = { id, kind: "schedule"|"base_code"|"charge_code"|"deposit_code"|"tax"|"discount",
        code, name,
        version: int|null,          // the pill; null only for a draft item
        version_label: str|null,    // a schedule's filed label, when the utility typed one
        effective_from: date|null,  // "from MM/DD/YYYY"
        effective_to: date|null,
        next: { version, effective_from } | null }   // a later version already filed
```

**Reads**

| Endpoint | Returns | Notes |
|---|---|---|
| `GET /plans` | rows add `schedules`, `units`, `version`, `effective_from`, `effective_to`, `upcoming_version` (`{version, effective_from}`\|null); sorts add `version`, `effective_from`, `effective_to`, `base_charges`, `units`; filters unchanged | `units` counts current unit assignments (the Units tab's number). Paged in SQL as today. |
| `GET /plans/{id}?as_of=` | as today, plus `as_of` (the date answered; default the utility's today), `plan_version` `{version, status, effective_from, effective_to, reason}`, `versions[]` (every version with its window and status: `draft · scheduled · in_force · ended · corrected`), `upcoming[]`, and the sections below | Every section is read AS OF `as_of`: the plan version in force on that date, and each item's version in force on that date. Image 28. |
| — `details` | `name, code, customer_classes[{value,label}] ([] = every class), description, intended_for {cap_proof, min_demand_25kw, owner_occupied}, notes[{attribute, operator, value}], minimum_bill_display, budget_billing` | Labels, never ids (`DEF-RAT-9285`). |
| — `services[]` | `{service, name, gl {code,name}\|null, schedule: ref + model, base: {code: ref\|null, by_size: [{size_class, size_label, amount_display}], flat_display\|null, state: "ok"|"none"|"ambiguous"|"refused", codes: [code] }, minimum: {by_size:[…], flat_display\|null}, usage: {kind: "blocks"|"per_size"|"flat"|"percent"|…, rows:[{label, rate_display}]}, outside_city: {surcharged: bool, percent_display\|null} }` | `base.code` is THE code a bill charges (the schedule's named code, else the class-narrowed `is_base` code), resolved by `base_charge_from_charge_code` — the live path. `ambiguous` lists the codes and shows no figure. Images 8, 20, 27, 28. |
| — `base_total` | `{amount_display\|null, unavailable: reason\|null}` | The existing `_plan_base_total`, read as of `as_of` (7.4 J5 for a sized base). |
| — `charge_codes[]` | `{ref, priced_by: "class"|"size"|"one_amount"|"percent", rows:[{class_or_size_label, amount_display, percent_display, min_display}], gl {code,name}, type_label, when_label}` | The late-fee code is listed here once (`BR-RAT-1011`), never twice. Base codes are never listed here (`BR-RAT-088`). Image 13, 29. |
| — `taxes[]` | `{ref, rate_display, what_is_taxed_label, gl {code,name}, brought_by: "jurisdiction"\|"attached"}`, `combined_rate_display` | Image 13, 29. |
| — `deposits[]` | `{ref, priced_by, rows:[{class_or_size_label, amount_display}], gl {code,name}}` | Images 17, 21, 30. Depends on A2. |
| — `discounts[]` | `{ref, value_display, gl {code,name}, enrolled, offered_from, offered_until}` | Images 18, 21, 30. |
| `GET /plans/{id}/units` | rows as today plus `customer_name`; params `q`, `f.occupancy=occupied|vacant`, `format=csv` (the CSV is the whole filtered set, streamed) | Images 31–33. |
| `GET /plans/{id}/audit` | paged `{at, actor {name}, what {kind, name}, change: "created"|"edited"|"new_version"|"correction"|"added"|"removed"|"published", reason, before_display, after_display, version {kind, version, effective_from}}`; params `f.kind=plan|underneath`, `f.from`, `f.to`, `format=csv` | Names and words, never ids or JSON (`DEF-RAT-9288`). *Underneath* adds taxes and discounts (closes `DEF-RAT-5738`'s gap). Images 34–36. |
| `GET /plans/form-options` | `services[]` (enabled, with GL), `schedules[]` per service as `ref` + `model` + base and minimum preview, `charge_codes[]`, `taxes[]`, `discounts[]`, `deposit_codes[]` (each as `ref` plus what the row shows), `customer_classes[]` (*Every customer class* first), `currency` | So every form row shows version and from-date without a second fetch. Only what is offered on the date the version starts (`?on=`). |

**Writes**

| Endpoint | Body | What it does |
|---|---|---|
| `POST /plans` | the whole plan: `details`, `services[{service, schedule, surcharged}]`, `outside_city_percent`, `charge_codes[{charge}]`, `taxes[{tax}]`, `deposits[{charge}]`, `discounts[{discount, offered_from, offered_until}]`, `budget_billing`, `minimum_bill_amount`, `effective_from`, `effective_to`, `publish: bool` | *Save as draft* (`publish:false`) or *Publish plan*. v1 is created with the plan's window. |
| `PATCH /plans/{id}` | draft: anything. Live: **only** `name, code, description, customer_classes, intended_for, notes` | *Name and details* — same version, an audit row with before → after. Any pricing field on a live plan is refused by name. |
| `POST /plans/{id}/versions` | everything a new version can change + `effective_from` (required), `effective_to`, `reason` (required), `publish: bool` | *Change from a date*. Draft → *Save new version*; publish → *Publish new version*: the version in force ends the day before `effective_from`, units stay on the plan and are priced by v2 from that date. |
| `POST /plans/{id}/versions/{version}/publish` | — | Publishes a saved new version (same checks as above). |
| `POST /plans/{id}/corrections` | as today plus `version` (which one), `reason` (required) | *Fix a mistake* — same window, same number, old row kept and marked corrected. Exists (`correct_plan_version`); widened to target a named version and to restate that version's bindings. |
| `POST /plans/{id}/publish` · `/archive` · `DELETE` | as today | Unchanged. |

**Refusals (message keys; each sentence is rule-33 short, the key is what the screen translates)**

| Key | When |
|---|---|
| `rating.plans.field_needs_new_version` (params `field`) | A pricing field sent to `PATCH` on a live plan. |
| `rating.plans.version_start_required` | `POST …/versions` with no `effective_from`. |
| `rating.plans.version_start_not_after_current` | The new version would start on or before the start of the version in force. |
| `rating.plans.version_start_in_past` | The new version would start before the utility's today (issued bills are never re-priced — hard rule 4). |
| `rating.plans.versions_overlap` | Two versions that can price would share a date (the database lock's name, translated). |
| `rating.plans.one_draft_version` | A second unpublished new version while one is open. |
| `rating.reason_required` (exists) | `POST …/versions` or `…/corrections` without a reason. |
| `rating.plans.row_empty` (params `table`, `row`) | An empty table-array row (*"An empty row is refused by name"*, ruling 6). |
| `rating.plans.service_listed_twice` · `rating.plans.charge_listed_twice` · `rating.plans.tax_listed_twice` · `rating.plans.deposit_listed_twice` · `rating.plans.discount_listed_twice` | The same item twice in one table. |
| `rating.plans.schedule_wrong_service` | A schedule picked for a service it does not price. |
| `rating.plans.base_code_on_charges` | An `is_base` code sent in `charge_codes` (it reaches the bill through the schedule, `BR-RAT-088`). |
| `rating.plans.deposit_code_not_deposit` | A code in `deposits` whose `charge_type` is not `refundable`. |
| `rating.plans.offer_window_backwards` | A discount's *offered until* before its *offered from*. |
| `rating.plans.effective_from_required` (exists, `BR-RAT-890`) | Publish with no start date. |

**Migrations (all 🔒 migration ordering, HUMAN-REVIEW-PENDING, RLS FORCE on new tables)**

1. `rating/0062` — `plan_versions` gains `effective_from`, `effective_to`, `status` (`draft|in_force|ended`) and the version-scoped scalars (`minimum_bill_amount`, `outside_city_factor`, `budget_billing`, `late_fee_charge_id`); every binding table (`plan_services`, `plan_rate_schedules`, `plan_charge_rules`, `plan_tax_rules`, `plan_discount_rules`, and the deposit binding of A2) gains `plan_version_id`. Unique keys move from `(rate_plan, X)` to `(plan_version, X)`.
2. `rating/0063` — data: for every plan, the CURRENT content becomes its in-force version (number = `rate_plans.version`, window = the plan's `effective_from/to`), every existing child row points at it. A plan with no stored window keeps none (the live path's dateless reading, `DEF-438`, is not decided here). **No figure moves** — proved by a before/after bill preview of every account on the seeded tenants.
3. `rating/0064` — the lock: `EXCLUDE USING gist (rate_plan_id WITH =, daterange(effective_from, effective_to, '[]') WITH &&) WHERE (status <> 'draft' AND superseded_by_version_id IS NULL)`.
4. If A2 is confirmed: deposits named on a plan — either `plan_charge_rules` rows whose code is `refundable` (no new table; the screen splits Charges and Deposits by the code's type), recommended, or a `plan_deposit_codes` table. `plan_deposit_rules` is kept read-only for history and its rows are mapped (A2).

`rate_plans` keeps identity only (`code, name, description, account_type_ids, eligibility, status`), and its old scalar columns stay as lawful containers read by nothing new (the `base_charge` precedent).

### 7.4 · Judgments that are ours (recorded in the decision log, not asked)

Each is the narrowest reading of a signed rule or of the approved drawing, with its figure. They go
into the decision log in the same push as this section (row *"CR-167 ROUND 1 · THE PLAN SERVER'S
ANSWERS"*). Round 2 builds them unless the coordinator or the PO says otherwise.

| # | Judgment | Why, and the figure |
|---|---|---|
| J1 | **A plan version OWNS its bindings and has a window.** Every binding (services, schedules, charge codes, taxes, discounts, deposits) and the plan-level terms (minimum bill, outside-city percent, budget billing, late-fee code) belong to ONE plan version with `effective_from`/`effective_to`; `rate_plans` keeps the identity (name, code, description, customer classes, intended-for, notes). | The approved drawing rules it: ruling 1's *"Change from a date (new version)"* and image 41's *"v1 · 09/01/2026 – 12/31/2026 · gets an end date; v2 · new · 01/01/2027 – No end; 5 units move to v2 on 01/01/2027"*. That is `OQ-324`'s option (B), which the lane that opened it said *"needs the PO"* — the PO has now drawn and approved it, so it is answered, not re-asked (law 13). It also avoids the cost `OQ-324` named for (B) — *"two homes for the same fact"* — because the content moves to the version instead of waiting beside the plan. **Closing `OQ-324` is a fan-out and is round 2's first commit, beside the migration.** |
| J2 | **The service date picks the plan version, exactly as it picks a rate version.** R1 keeps its rule (*"the plan version in force on the service-period end date"*) and refuses two; a bill whose period crosses a plan-version start SPLITS there. | `BR-RAT-114` (CONFIRMED) already says *"AN ORDINARY BILL SPLITS AT A MID-PERIOD RATE OR PLAN CHANGE"*, and `OQ-323`'s answer (2026-09-18) says the service date decides, never the wall clock. Worked: v1 surcharges outside-city water 25%, v2 (from 01/16/2027) does not; an outside-city January bill with $40.00 of water usage spread evenly prices $40.00 + 25% × $40.00 × 15/31 = **$44.84**, never $50.00 or $40.00. The plan floor on a split bill follows what `midperiod.py` already does at a plan change; nothing new is invented there. |
| J3 | **Units stay on the PLAN; nothing is written to move them.** *"5 units move to v2"* happens because the date picks v2; no `unit_plan_assignments` row changes. `unit_plan_assignments.plan_version` stays the historical snapshot (`BR-CUS-013`) and is never a price input. | `OQ-323`'s answer removes the snapshot's money meaning. Writing 75 assignment rows for a version change (the seeded `SCW-RES`) would make a version change a bulk move, which ruling 15 put off (*"not now"*). |
| J4 | **A new version may not start before the utility's today, nor on or before the start of the version in force.** A past mistake is fixed with *Fix a mistake* (same window), never a back-dated version. | Hard rule 4: issued bills are never re-priced, and a back-dated version would re-price every unbilled period behind it silently. Same rule the discount lane applied (`CR-166` §10, *"a past date refused"*). |
| J5 | ***Name and details* on a live plan saves on the same version** with an audit row (before → after, in words); every other field is refused by name on `PATCH` and needs *Change from a date* or *Fix a mistake*. | Ruling 1 (*"Name and details (same version)"*). These six fields price nothing — the model says so of customer classes (`models.py:126–130`, *"NOTHING PRICES A BILL FROM THIS AND THAT WAS CHECKED"*), and intended-for and notes are advisory (`BR-RAT-043`). It is the discount's split (identity on the discount, money on the version) applied to the plan. ⚠ It narrows `BR-RAT-037`'s *"every change = new version"* for these six fields — stated for the PO in 7.5 B2, not asked. |
| J6 | **A rate schedule's version number is counted, not stored**: the n-th dated version of the schedule in start-date order; a correction keeps the number of the version it corrects; a draft has none. The utility's own filed label (`version_label`) is served beside it. | The drawing puts *V4* on every schedule; `tariff_version_labels` says no ordinal is stored and none should be (`selectors.py:1975`). Counting is what `charge_prices._versions` already does for prices, for the same reason: a back-dated version would make a stored number contradict the date order. |
| J7 | **A charge code's version number (base, plan charge, deposit) is the number of times its prices changed up to the date shown**, and its from-date is the latest of those changes. | Prices are stored per size and class (`ChargeCodeAmount`), each numbered on its own; the drawing shows ONE pill per code (*BASE-W1 V2 from 09/01/2026*). Worked: a base code started 08/01/2026 and re-priced on 09/01/2026 for two sizes reads **V2 from 09/01/2026** on 10/03/2026, and **V1 from 08/01/2026** when priced as of 08/15/2026. |
| J8 | ***Monthly base charges* on a plan = the sum, over its services, of each service's base at its smallest size.** | It is a display figure that moves no money. Today `_plan_base_total` answers *unavailable* as soon as one base is priced by size, which is every water plan; the drawing's $19.00 is water 5/8" $10.00 + sewer $9.00 + trash $0.00 + fire $0.00. Rule 33: the figure carries no explanation on screen. |
| J9 | **A deposit is named on a plan as a plan charge code whose type is *refundable*, stored as a `plan_charge_rules` row** (no new table); the screen splits Charges and Deposits by the code's type. The amount is read from that code, by customer class (or by size, only if 7.5 B3 says yes). Existing `plan_deposit_rules` figures are carried over without changing a cent: a plan's rows that match an existing refundable code's class prices bind that code; otherwise a code is created for that plan's figures. | The PO ruled the source twice — 2026-09-08 (*"a plan names charge codes; the charge code carries the money"*) and 2026-09-23 (*"plan will have deposite chanrge code as per customer categoris; so that value should be atken as by default"*) — and the drawing names `DEPOSIT · Security deposit V2`. `CR-087` §5 left *"what reads a deposit once it is a charge code"* open; this answers it. **Measured: no seeded tenant holds a single `plan_deposit_rules` row**, so the carry-over is about the PO's beta utility only, and the migration reports what it did plan by plan. |
| J10 | **The audit is one paged read in words** across the plan, its versions and what it binds, with *underneath* covering taxes and discounts too. | Ruling 13 and `DEF-RAT-9288`. |
| J11 | **The Units tab's occupancy filter asks customers which of this plan's units are occupied** (one seam call returning a queryset, used as a SQL sub-select), so the page, the count and the CSV still come from one SQL query. | `NFR-3`; rating may not join customers' tables (B1). |

### 7.5 · For the PO (each in one sentence with a figure)

Grep of `02-decision-log.md` and `01-open-questions.md` first (law 13): none of these is ruled.

| # | What to put to the PO, in plain English | Our recommendation |
|---|---|---|
| B1 | ⚖️ **ANSWERED 2026-10-03 — PO *"(a) Fix it: use the base the schedule names. Bills refused today start going out; bills already issued don't change."* Built §15 (`DEF-RAT-9335` closed).** **A bill that is refused today would start billing.** When a utility's water rate schedule names its base charge code, a different water base code that is priced only for some meter sizes still stops the bill of every customer whose size it does not price. Fixing it lets the bill charge the code the schedule names. *Worked:* a residential 5/8" customer whose schedule names a $10.00 base: September is refused today; after the fix it bills **$10.00** water base (bill **$156.50**). No bill already issued changes. *"Fix it so the bill charges the code the rate schedule names?"* | **Yes.** It is what `BR-RAT-1025` already says; the refusal is about a code the bill never charges (`DEF-RAT-9335`). |
| B2 | **Renaming a live plan will not make a new version.** Changing a live plan's name, code, description, customer classes, intended-for ticks or notes is saved on the same version with a before → after line in Audit; anything that changes a price still makes a new version or a correction. This narrows the signed rule *"every change to an in-force plan is a new version"* to the things that price. *Worked:* renaming *Residential City Plan* to *Residential — City* keeps it **v1**; changing its minimum bill from $10.00 to $12.00 from 01/01/2027 makes **v2**. | Confirm as drawn (ruling 1 already says *"Name and details — same version"*); recorded as `BR-RAT-037` narrowed, not reversed. |
| B3 | ⚖️ **ANSWERED 2026-10-03 — PO *"(a) Class or size: the deposit table gets a size column, like charge codes have."* Built §15.** **May a deposit be priced by meter size?** The signed rule says a deposit is *one fixed amount per customer class* (`BR-RAT-020`). On 2026-10-01 you said plan charges, deposits included, *"can be saved either on customer class or asset class"*. If yes, a 2" commercial connection could be asked, say, **$600.00** where a 5/8" one is asked **$150.00**, and a customer with several services is asked by the size of the service the deposit code names (for example water). | Yes, as you said on 2026-10-01, with the size taken from the service the deposit code names. Until answered, round 2 builds deposits by customer class only (what `BR-RAT-020` already signs) and the *by size* choice is not offered for a deposit code. |

### 7.6 · Fields the form reads that §7.3 did not name (added by lane PLAN-FORM, round 2, 2026-10-03)

Appended under §8's rule (*"a field added by any lane is appended to §7 with the lane and the
reason"*). Nothing in §7.3 is renamed; each line below is an ADDITION the New plan form
(`07-frontend/src/api/planFormEndpoints.ts`) reads, and reads defensively — a missing field is a
dash or an empty list, never a broken step. **The server lane is asked to serve them; the form
works without them, only less fully.**

| Field | Where | Why the form needs it |
|---|---|---|
| `schedules[].base`, `.minimum`, `.usage` | `GET /plans/form-options` | §7.3 says *"base and minimum preview"*; the form reads the SAME `base` / `minimum` / `usage` objects as the detail's `services[]`, so Review builds `PlanSections` from the options without a second shape (ruling 11). |
| `base.monthly_amount` (4-place decimal string) | form-options schedules, detail `services[]` | J8's figure per service (flat base, else the smallest size). The form SUMS it exactly (`moneyMath`, `BigInt`) for *Monthly base charges* on step 2 and *This plan*; it never adds display strings. |
| `base.sized_by_label` | same | The base table's heading — *Base charges by meter size / cart size / fire line size* (images 20, 27). `null` → *Base charges*. |
| `usage.kind_label` | same | The usage table's heading — *Usage charges · Block (per month)* (images 20, 27). |
| `taxes[].rate_percent` (6-place percentage POINTS) | form-options, detail | The form's *8.25% combined* while taxes are picked (images 13, 14), summed exactly and shown to two places. The detail keeps `combined_tax_rate_display`. |
| `taxes[].authority` | form-options, detail | The authority under the tax name (CR-167 §5.5 — the details page loses no fact). |
| `charge_codes[].default_on_new_plan` | form-options | **`DEF-RAT-9328`, form side.** The utility's default late-fee code arrives as a visible, removable ROW on a new plan. |
| `outside_city_surcharge {percent_display, service_names[]}` | detail | The Services tab's strip *25% on Water, Sewer* (image 27), drawn in each catalogue's own words. |
| `customer_classes[]`, `services[].gl` | form-options | Already §7.3; restated because the notes table's value lists are built from them (a class note stores the class NAME, `DEF-RAT-9285`). |

**One behaviour asked of `POST /plans` (and `PATCH`/versions in round 3):** the body ALWAYS carries
`charge_codes`, `[]` included. The server binds exactly those codes, takes the late fee from the
penalty-type code among them, and **never fills an absent or empty list with `LATE`** — the empty
list is the clerk's answer *"this plan charges no late fee"* (`BR-RAT-1011`'s ruled zero). Today's
silent default (`services.default_late_fee_charge`) is what `DEF-RAT-9328` is about; the form side
of that fix is the visible row above, the server side is task 3's.

## 8 · The ten tasks, lanes and rounds, versions and rollback

| # | Task | Round | Lane | Depends on | Fixes |
|---|---|---|---|---|---|
| 1 | Drawing images | done | — | — | — |
| 2 | Contract and record: this CR — rulings, field map (§5), today's problems reproduced and filed (§6), server answers and the API contract (§7) | **R1** | PLAN-CR (§0–§6, §8) · PLAN-SRV (§7) | — | — |
| 3 | Back end: deposits named on a plan (charge codes priced by class or size); version + from-date on every referenced schedule, base code, charge code, tax, discount and deposit; *Priced as of* a date; exactly one plan version per date for billing; the plan's charge codes as ONE list including the late fee; Publish of a changed published plan as one act; units on a plan paged with search, occupancy and CSV; plan audit as before → after with names | **R2** | SRV | §7 agreed | 9328 (server half), 9330, 9288 (server half) |
| 4 | One shared plan-sections component — Plan · per service · Charge codes · Taxes · Deposits · Discounts · Billing terms — used by Review and the details Services / Charges / Billing tabs (ruling 11) | **R2** | FORM | §7 contract | 9334 (sections), 9286, 9329 (display) |
| 5 | New plan form, five steps, table arrays, refusals that name the box, *Save as draft* + *Publish plan* | **R2** | FORM | 4 | 9332, 9328, 9329, 9287, 9285 |
| 6 | List (images 01–03) | **R2** | LIST | §7 list fields | 9333 |
| 7 | Details: six tabs and ruling 13's improvements (links, folding, Expand all, banner, Priced as of, tiles open tabs, section Edit, sticky header, tab in the address with `RETIRED_PLAN_TABS` re-mapped, Units search/filter/CSV, Audit filters and before → after, arrow keys); More ▾ with Duplicate, Retire (and *Delete draft* on a draft) | **R3** | DETAIL | 3, 4 | 9334, 9331, 9288 |
| 8 | Edit — *What to change*: Name and details · Change from a date · Fix a mistake, each with its Review (images 38–44) | **R3** | EDIT | 3, 5 | 9330, 9332 (edit half) |
| 9 | Eleven languages for the five screens; retired keys through `10-scripts/i18n_fanin.py` | **R3** | I18N | 5–8's English settled | — |
| 10 | Full web walk (`web-walk.md`), the 44 states photographed beside the images, then close | **R4** | WALK | 3–9 | whatever the walk finds, filed first |

**R2 starts only after §7's contract is written and agreed**, then SRV, FORM and LIST run in
parallel against it — the CR-165/CR-166 pattern (field names fixed; a field added by any lane is
appended to §7 with the lane and the reason, in the commit that serves it). FORM owns task 4 because
Review is its first consumer; DETAIL consumes the component in R3 without forking it.

**Rules every lane follows here:** build from the images (rule 42), our UI standard for spacing and
components (rule 44), every selection a kit `TableArray`; a defect is filed before it is fixed and its
test shown RED first; the 🔒 rating files ship HUMAN-REVIEW-PENDING with a ledger row and the
golden tests do not move; anything that moves a signed money figure stops for the PO with a dollar
example. *Move units to another plan* is not built by any task (ruling 15).

**Versions.** Round 1 ships no product code — this file, three walk scripts, 30 screenshots and
seven defect rows — so it carries **no version**. Each later task takes its own number at push time
with `10-scripts/allocate.py version --bump change` (a fix-only push `--bump fix`) and
`--verify`, records it in `CHANGELOG.md` and the version source of truth as the `CR-165`/`CR-166`
commits did, and appends its record to this file as a new section (§9 onward), with the version and
the defects it closes.

**Rollback.** Round 1: none needed (records only). Screens (tasks 4–9): redeploy the previous build;
no stored fact changes from a screen alone, and the preserved fields (S3, S5, S6) keep being
re-posted unchanged. Back end (task 3): any migration names its down path and what happens to rows
written under it — deposit charge codes bound to plans, and any plan version rows written by
*Change from a date* — before it ships.

## 10 · Round 2 task 4 — the one shared plan-sections component (built 2026-10-03, `2.482.0`, lane PLAN-FORM)

**What was built.** `07-frontend/src/features/rating/planSections/PlanSections.tsx` — ONE component
that draws a plan as the approved images draw it (ruling 11's build note: *"one shared component
for both"*). It takes `PlanSections` (the §7.3 detail shape, normalised in
`07-frontend/src/api/planFormEndpoints.ts`) and a `show` list, and draws, always in this order:
**Plan** (name, code, customer classes, description, intended for, notes) · **one section per
service** (Rate schedule · Base charges · Outside city as a three-cell strip; then *Base charges by
meter size* with Base charge and Minimum per size, beside *Usage charges · Block (per month)*) ·
**services totals** (Monthly base charges · Outside-city surcharge — details Services tab) ·
**Charge codes** (Code · Priced by · Class or size · Amount · GL · When) · **Taxes** (Tax with its
authority under it · Rate · What is taxed · GL; *N% combined* beside the heading) · **Deposits** ·
**Discounts** (with an **Enrolled** column — §5.5) · **Billing terms** (Monthly base charges ·
Minimum bill · Budget billing). Every referenced item carries a **version pill and *from
MM/DD/YYYY*** (ruling 8). Vocabulary is ruling 12's: *Base charges*, *Usage charges*, *Monthly base
charges*. With `links` on (the details page) every name is a link to its own page (ruling 13); Review
passes `links={false}` because following one would leave an unsaved form. A section's **Edit** calls
`onEdit(section)` — Review opens that step; round 3's details page opens that step of Edit (image 37).

**Who mounts it.** Review (task 5) with `REVIEW_SECTIONS` today. Round 3's details tabs mount it
with `["services","servicesTotals"]` (images 26–28), `["charges","taxes"]` (29) and
`["deposits","discounts","billingTerms"]` (30), reading `getPlanSections(planId, asOf)`.
**Not built here, for round 3 (task 7):** folding a service to one line with *Show sizes and
blocks* / *Expand all* (images 26–27), the upcoming-version banner and *Priced as of*.

**`DEF-RAT-9336` — FIXED and its hold released.** The new component draws the base the SERVER
resolved (`services[].base.code`, the schedule's named code), never the catalogue; an ambiguous base
names its codes and shows no figure. And the old card the details Overview still mounts
(`PlanSummaryCard.tsx`) now reads the served `base_charge_code` and lists only that code: the held
test `planSummaryBaseCode.defRat9336.test.ts` was turned from `it.fails` to `it`, shown red first
(*"expected '8.00 · 10.00 · 8.00' to be '10.00'"*) and is green.
**`DEF-RAT-9286` (Review counts contradict):** no count is drawn above a section any more, so none
can contradict its rows (task 7 closes it with the details page). **`DEF-RAT-9329` (display):**
one row per tax, named, with its authority — the server half (seven bindings → nine rows) is task 3's.

**Tests.** `planSections/PlanSections.dom.test.tsx` — 9 cases: drawn order; class and note in words
(`DEF-RAT-9285`); one billed base code with V2 and *from 09/01/2026*; an ambiguous base; a pill on
every referenced row; Enrolled and *No end*; billing terms; the details subset with links to the
schedule and the base code by address; Review's text names and *Edit Taxes*.

## 11 · Round 2 task 5 — the New plan form, five steps (built 2026-10-03, `2.482.0`, lane PLAN-FORM)

**What was built.** `plans-rates/plans/new` opens `07-frontend/src/features/rating/planForm/NewPlanForm.tsx`
— **Details · Services · Charges · Billing · Review** (ruling 1, images 04–23) with *This plan* on the
right, *Fix N things first.* beside Continue, and the published and saved-draft states (images 22,
23). The structure is the discount and tax forms', copied: a page, one component per step
(`DetailsStep`, `ServicesStep`, `ChargesStep`, `BillingStep`, `ReviewStep`, each made of SECTION
components), `PlanSummaryPanel`, `PlanSavedPanel`, a pure model (`planFormModel.ts`), a lists hook
(`usePlanFormLists.ts`) and `planFormShared.tsx` with `PlanStepProps` carrying a `locked` set, so
round 3's three Edit choices mount the same steps. **`PlanWizard.tsx` still serves the EDIT route**
(`plans-rates/plans/:planId/edit`) and is imported by its own tests; round 3's task 8 retires it.
No *Try a bill* (ruling 14).

Every selection is the kit `TableArray` (ruling 3): notes, services, charge codes, taxes, deposits,
discounts — full-size controls in the row, a red × to remove, *+ Add …* under the table, **disabled
with *All added.* beside it** when nothing is left, and an empty row **refused by name** (ruling 6).
The kit gained two opt-ins under B14 rule 36, each landing with this caller: `TableArrayAction.
showReason` (the reason drawn beside the greyed button) and `TableArray.lead` (the three intended-for
ticks above the notes table, image 07); and `WizardFrame.commitCompanion` puts *Save as draft*
beside *Publish plan* on the right with *Back* alone on the left (images 20–21). Customer classes are the kit `CheckDropdown`, *Every customer
class* first (ruling 4). The step-2 row shows the picked schedule's version and from-date, the base
($, base code, its version and from-date) and the minimum, with **Monthly base charges** under the
table (ruling 7). Step 3 has no base section. Step 4 has **Deposits** (a deposit charge code priced
by customer class — §7.3, `BR-RAT-020`), **Discounts offered** (offered from/until, Enrolled),
budget billing and a `$` minimum bill. Review is the task-4 component plus **Dates** (Starts *, Ends)
and ends **Back · Save as draft · Publish plan** (ruling 10) — both ONE `POST /plans` with
`publish` false/true (BR-SHL-019).

**Defects.** **`DEF-RAT-9328` (form side):** the utility's default late-fee code arrives as a ROW of
the Charge codes table (`default_on_new_plan`), visible, removable and listed on Review; the body
ALWAYS carries `charge_codes`, `[]` included (§7.6). Proved red first by switching the row off:
*"Unable to find an accessible element with the role "combobox" and name "Charge code""* and
*"expected [] to deeply equal [ { charge: 'cc-late' } ]"*. Stays OPEN for the server half (task 3:
never bind LATE silently). **`DEF-RAT-9332` (form, New half):** five steps, refusals that name the
box, table arrays, versions and from-dates, deposits, the three ticks, *Save as draft* — the Edit
half is round 3's, so it stays OPEN. **`DEF-RAT-9287`:** the minimum bill is a `$` box shown to two
places. **`DEF-RAT-9285`:** a note naming a class stores and shows its NAME.

**Copy.** 194 keys under `rating.planForm.*` and `rating.planSections.*`, in all eleven catalogues
through `10-scripts/i18n_fanin.py` — **G15 refuses an English paste-in** (its untranslated baseline
may only shrink), so the ten other languages are written now, many by reusing the catalogues' own
words for the same idea (e.g. *Save draft & exit*, *Every customer class*); round 3 (task 9) reviews
them on screen.

### Our judgments where the drawing, the rules and the contract do not meet (recorded, not asked — law 13)

1. **Rule 33 over the drawing's words in five strings** (B14 rule 44: our UI standard wins). The
   drawn *"Choose a code in each row, or remove it."* (9 words) reads **"Choose a code, or remove it."**
   (6), the same for tax, deposit and discount; *"Assign it to units from the plan."* reads
   **"Assign units from the plan."** *"Choose a service in each row."* is 6 and kept. The label
   *Outside-city premises pay more* (4 words, one over a label's cap) is KEPT as drawn: no 3-word
   wording says the same fact, and a shorter one would make a reader guess.
2. **A red × on every discount row**, though images 17–18 draw none (the row is cut at 1440):
   ruling 6 makes every table array removable.
3. **A schedule is required in every service row before Continue** (*"Choose a schedule in each
   row."*) — not drawn; a service with no schedule cannot be published (`rating.plans.
   service_without_schedule`), so the clerk is told on the step that can fix it.
4. **The surcharge tick is disabled until *Yes, a surcharge*** is chosen, with its reason in the
   tooltip (BR-SHL-025); image 08 draws ticks beside a *Yes*.
5. **The row's base and minimum figures** are the flat figure, else the smallest size's (J8's
   reading); Review and the details tabs draw every size.
6. ***Monthly base charges* and *N% combined* are added up in the browser** from the server's 4- and
   6-place figures with `moneyMath`'s exact `BigInt` sum and one half-up rounding to two places —
   never float, never display strings (hard rule 2). The details page keeps the server's own totals.
7. ***Save draft & exit* is hidden once the plan is saved** (images 22–23 still draw it): a second
   press would create a second plan.
8. **Plan facts on Review are a label | value list**, not a table with a header row — image 20 draws
   no header and the kit table always has one.
9. **The shared Discounts section carries *Enrolled*** although Review's image 21 does not (§5.5:
   the details page loses no number). On a new plan it is the discount's own take-up.
10. **A note may be about a customer class or a service** (the lists the old step 7 offered), each
    a dropdown of served values; operators are r10's five.

### 11.1 · Photographed beside the images (`2.482.1` code; the frame still reads v2.482.0 because the number moved after the build)

`10-scripts/cr167_plan_form_walk.mjs`, Chromium at 1440, PostgreSQL 16 (`sbh_planform`), signed in as
Dana. **26 photographs** in `08-qa/plans-2026-10-03/form/`, each opened; the side-by-side notes are
`08-qa/plans-2026-10-03/form/side-by-side.md`. **Two sets:** `…-server.png` is the real server end to
end — `GET /plans/form-options` answers **404** on this build, so the dropdowns are empty and
Continue refuses by name (*Add at least one service.*); `…-contract.png` answers ONLY
`form-options` and `POST /plans` from the agreed §7.3/§7.6 shape filled with the images' own figures
(the two posted bodies are printed in `walk-output-contract.txt`). **Task 10 re-runs it without
`CONTRACT=1` once task 3 lands.** What the photographs found, fixed in `2.482.1`: Review's *Save as
draft* sat left of *Back* (now beside *Publish plan*, `WizardFrame.commitCompanion`, red first:
*expected [ 'Save as draft', 'Back', … ] to deeply equal [ 'Back', 'Save as draft', … ]*); the
version tag was invisible on the grey panel and its date wrapped; the row counts included an empty
row. Differences left as they are: the boxes are not pink-filled on a refusal and an empty notes table
has no header (kit, B14 rule 44); *Save draft & exit* hidden after saving (judgment 7).

### 11.2 · Against the real server (`2.484.1`–`2.484.3`, lane PLAN-FORMFIX, 2026-10-03)

**The form now asks `GET /plans/form-options?classes=` with step 1's ticks** (*Every customer class* =
every class the server serves), and asks again when they change; the previous answer stays on screen
meanwhile, so a chosen row never blanks. Before: a *Residential* water row read *Several base codes* and
*Monthly base charges* **$0.00**. After, on PostgreSQL (`sbh_planformfix`, API `:8191`, SPA `:5291`,
Dana, 1440): water **$8.00 · BASE-W**, water + electric **$20.00** on Services, *This plan* and Review's
*Billing terms* — the figure the plan's own read gives (§9). A picked schedule whose base the classes do
not settle keeps its row, names its codes (*Several base codes · BASE-W, BASE-W-COM*) and the totals read
**—**, never $0.00 (`08b-…-every-class-unresolved-server.png`; the plan read's own `base_total` makes the
same call). `DEF-RAT-9351`, `2.484.1`.

Photographing all twenty states beside images 04–23 found three more, each filed first and fixed in
`2.484.3`: *This plan* scrolled away on Review where images 19–20 draw it following the page
(`DEF-RAT-9355`, now `sticky`, as the rate-schedule and charge-code wizards are); the Charge codes Type
column printed the stored type `one_time`/`penalty` (`DEF-RAT-9356`, now the catalogue's word); the
surcharge help read *Check* where the drawing says *Tick* (`DEF-RAT-9357`). Photographs:
`08-qa/plans-2026-10-03/form/04…23-*-server.png` re-taken on `2.484.3`, each opened; printed output
`walk-output-server.txt`. The lane database needed two refundable codes the sample does not seed
(`DEPOSIT` $150.00, `DEPO-C` $300.00) for steps 17–19. Differences left, all data or rule 37: two
services and two taxes where the images draw four and three; `LATE` has no *from* date because its price
is not held as a dated row; the base heading names the code and its name (`BASE-W · Water base service —
residential`) where the drawing shows the code alone — the shared `PlanSections`, task 7's to judge.

### What is left (round 3 and the server)

| Item | Who |
|---|---|
| `GET /plans/form-options`, the §7.3 `POST /plans` body and §7.6's fields served | **DONE** — PLAN-API `2.484.0`; the form asks with the plan's classes from `2.484.1` (§11.2) |
| Edit — *What to change*, the three choices on these steps; retire `PlanWizard.tsx` | task 8 |
| Details tabs mounting `PlanSections` with folding, *Priced as of*, banner | task 7 |
| Ten languages reviewed on screen | task 9 |

## 12 · Round 2 task 6 — the list, built from images 01–03 (`2.483.0`, lane PLAN-LIST)

**Built:** `07-frontend/src/features/rating/PlansTab.tsx` (rewritten) and `planListParts.tsx` (new, the
row's cells — B14 rule 43), from images 01–03 opened as images (rule 42); our kit decides spacing, type
and components (rule 44); both files on the route-B ledger (rule 21). Columns, in the drawn order:
Plan (the name, a link, with `CODE · Class` under it) · Version · Services · Schedules · Base charges ·
Units · From · To · Status · Open. Toolbar: *Search plan name or code* · All · `+ Filter ▾` (Status,
Service) · download · columns. Search, both filters and every sort go to the server (`q`, `f.status`,
`f.service`, `sort`) and the list stays server-paged (NFR-3) — nothing filters or sorts the page; no
cap anywhere (NFR-5: the class list is read whole, page after page).

| L (§5.3) | Today | Done | Proof |
|---|---|---|---|
| L1–L6, L14–L16 | search, All, filters, columns, CSV, History, + New plan, tabs | **KEPT**, search placeholder without the `…` as image 02 draws | `plansList.dom.test.tsx` (search, filters to server); `01`–`03` |
| L7 | Sort Plan / Accounts / Status | **Plan · Version · Units · From · To · Status** sort on the server (`PLAN_SORTS`). Base charges is NOT sortable — `BR-RAT-1040` overrules §7.3's contract row that lists it | test *every sortable head …*; `PlansRatesPage.test.tsx` TC-4 |
| L8 | Rows per page + ‹ › | the kit's pager | `01` |
| L9 | Plan name link | **KEPT**, with `CODE · Class` under it, never an id (rule 31) | test *Plan: the name opens …* |
| L10 | Row *New version* | gone from the row; the plan's page has *Edit* | test *the row's one action OPENS …* |
| L11 | Row *Archive* | gone from the row; the plan's page has *Retire* (task 7 moves it into More ▾) | same |
| L12 | Row *Publish* (draft) | gone from the row; the draft's Review has *Publish plan* (task 5) | same |
| L13 | Row *Delete* (draft) | **a draft's own page has *Delete draft*** (header button until task 7 draws More ▾); the server's `BR-RAT-030` lock unchanged | `PlanDetail.test.tsx` *CR-167 §5.5 L13* |

**DEF-RAT-9333, item by item:** the paragraph above the table is gone (`rating.explainer.plans` retired
from all eleven catalogues; G14 stops asking for it) · Units replaces Accounts · Version, From and To are
columns, To reads *No end* · the row's pencil, publish, archive and delete icons and their confirm are gone;
one *Open* icon · base charges `—` on five of seven sample plans is **the server stating it cannot give one
figure** (`BR-RAT-1040`: three plans name every class while the codes are priced per class; one prices
electric by size; one has no industrial water base — read on PostgreSQL with
`base_charge_from_charge_code`), which a drawn figure does not overrule (rule 37).

**The server fields — WIRED and checked on PostgreSQL at `2.484.0`** (PLAN-API, `6bea16fcd`): the list
reads §7.3's `schedules`, `units`, `version`, `effective_from`, `effective_to` and `upcoming_version`
(the drawing shows no upcoming column, so it is read by nothing here yet — task 7's banner). The walk
asks the server for each new sort and checks the order: Units descending reads 75 · 7 · 2 · 2 · 1 · 1 · 0,
and clicking the Units head twice puts the screen in that order (`sort=units&dir=desc`). On this sample
every plan is V1 and open-ended, so the Version and To sorts are checked only as not breaking. A server
that predates the fields still renders: Schedules counts the row's own `rate_schedules` and Units reads
`accounts` (the current unit-assignment count). **Asked of PLAN-API (list only, not in §7.3):**
`customer_classes: [{value, label}]` on each list row, as the details read serves it — until then the
list names classes from the tenant's class list, a second read. **Served and wired in `2.484.2`
(`DEF-RAT-9354`, follow-up below); the second read is gone.**

**Tests:** `plansList.dom.test.tsx`, 12 cases, written first and watched fail on the old list (10 for their
own reason; *base charges is the server's figure* and *search/filters/paging to the server* already held);
`PlanDetail.test.tsx` gains the L13 case, watched fail on the old page; `PlansRatesPage.test.tsx` amended
in four cases that pinned the old columns, sorts and row actions; `ConfirmDialogTier.dom.test.tsx` census
moved (the list's polymorphic dialog left, the draft page's danger dialog arrived). `tsc` (shown able to
fail), eslint, `vitest src/features/rating src/styles src/i18n` green except the census's two cases, red
since `17c2e4ea4` and already filed as `DEF-SHL-9347` (not this lane's). `ArchiveIcon` removed with its last
caller (G40 back to its pre-lane 44).

**Photographs:** `08-qa/plans-2026-10-03/list/` — `01-list-all`, `02-list-search`, `03-list-no-results`
at 1440 on PostgreSQL 16 on build `2.484.0` (the server fields served), `lang-de`, `lang-ja-JP`, `lang-ko-KR`; `notes.md` sets each beside its image
and lists every difference with its reason; `walk-output.txt` is what each state read;
`10-scripts/cr167_plans_list_after_walk.mjs` re-runs it. **Width:** 1,120 px in a 1,120 px box in all
eleven languages, no sideways scroll, no word split (the per-word check proved red with `FORCE_SQUEEZE=1`).

**`DEF-RAT-9333` CLOSED** on `6f107d0a7` (screen, `2.483.0`) with the server half seen on `2.484.0`.

**Follow-up (`2.484.2`, lane PLAN-FORMFIX, `DEF-RAT-9354`):** `GET /plans` rows now serve
`customer_classes: [{value, label}]` (`[]` = every class), named by ONE read for the page in
`plan_reads.list_additions` (bounded by `per`, NFR-3). The list words its classes from them and its
second read of the class list (`getAllPlanClasses`, every page of `lookups/account_types`) is removed; a
row without the field names no class it cannot word, never an id. Red first: pytest *KeyError:
'customer_classes'*; vitest *Unable to find an element with the text: OLD* (the row read *OLD ·
Commercial* through the second read).

**Rollback:** redeploy `2.482.1`. No data is written by this change.

## 9 · Round 2 task 3 — the plan server (built 2026-10-03, `2.484.0`, lane PLAN-API)

Built against §7.3 as agreed, with the coordinator's four adjustments (decision log *"OQ-324 CLOSED (B)"*) and §7.6's fields; every judgment of ours is in the decision log row *"CR-167 TASK 3 · THE PLAN SERVER, BUILT"*. First commit: `OQ-324` closed as (B) and fanned out (`070415cf7`).

| What | Where | Proof |
|---|---|---|
| **A plan version has dates and owns its bindings (`BR-RAT-1066`)** | `rating/0062` (window, status, terms on `plan_versions`; `plan_version_id` on five binding tables; `role` on `plan_charge_rules`; `rate_plans.head_version_id`) · `0063` (every plan's current content → its head; other filing rows → `history`) · `0064` (NOT NULL + `ex_plan_versions_no_overlap`) · `plan_versioning.py` (the default manager reads the version in force on the day, else the head) | PostgreSQL: every day 12/25/2026–01/05/2027 reads exactly one version and R1's candidates cover each once; a raw overlapping published row is refused by the lock (`tests/test_cr167_plan_versions_pg.py`) |
| **Billing gets exactly one version per date** | `gather.gather_account` opens `pricing_day(period_end)`; `midperiod.split_plan` cuts at a version start; `resolution_catalogue.plan_version_facts` = one candidate per priceable version; the floor, outside-city factor and late-fee code read the version's terms (`terms_on`); memo keys carry the day | v1 floor $10.00 on 12/31/2026, v2 $12.00 on 01/01/2027 |
| **No figure moved** | — | golden `tests/golden` **25 passed + 1 xfailed before and after**; `10-scripts/03-golden-verify.py` unchanged (document harness); **124 account-periods of `brazosbend` priced before and after `0062–0064` on PostgreSQL: $39,721.23 both, 0 differences** (`10-scripts/cr167_task3_bill_compare_pg.py`) |
| **Reads (§7.3 + §7.6)** | `plan_reads.py`: `ref` on every schedule, base code, charge code, deposit code, tax, discount (J6, J7); `GET /plans/{id}?as_of=` sections (`details`, `services[]` with base/minimum/usage and `monthly_amount`, `sized_by_label`, `kind_label`, `base_total`, `charge_codes[]`, `taxes[]` with `rate_percent`/`authority`, `deposits[]`, `discounts[]`, `outside_city_surcharge`, `currency`, `plan_version`, `versions[]` with states, `upcoming[]`); `GET /plans` + `schedules`, `units`, `upcoming_version`, sorts `version`/`effective_from`/`effective_to`/`units`; `/units` `q`, `f.occupancy`, `format=csv`, `customer_name`; `/audit` (SQL UNION of `audit_log` and `rate_change_log`, words); `GET /plans/form-options` in the form's own section shapes with `default_on_new_plan` | `tests/test_cr167_plans_round2.py`; on PostgreSQL `SCW-RES` reads electric $12.00 + water $8.00 = monthly base $20.00, 75 units (67 occupied, 8 vacant), taxes 8.25% |
| **Writes (§7.3)** | `plan_writes.py`: `POST /plans` (contract body, `publish` in the same transaction), `PATCH` (live: details only, same version — `BR-RAT-1067`), `POST /plans/{id}/versions` + `/versions/{n}/publish` (start ≥ today, after the version it replaces; the old version ends the day before), `POST /plans/{id}/corrections` with `version`; the 8-step form's old body still served | 21 cases, every refusal asserted by field and key |
| **Refusals** | 20 keys in all eleven catalogues (`10-scripts/i18n_fanin.py`): §7.3's fifteen plus `deposit_code_priced_by_size` (`OQ-RAT-12786` — *retired 2026-10-03, §15: the PO allowed deposits by size*), `version_of_draft`, `no_version_to_publish`, `rating.not_a_date` | runtime catalogue assertion passes |
| **Deposits (ruling 9, class only)** | `_validate_plan_deposit_codes`; `selectors.plan_deposit_for` (typed rows still first; *(until §15, 2026-10-03)* size raises `NotImplementedError("OQ-RAT-12786")`) | DEPOSIT $150.00 for Residential |

**Defects, red first** (each test was run against the tip `00d29d43f`'s code in a second worktree before the fix, then green): **`DEF-RAT-9337`** — RED: the base code was stored (`services.update_plan` accepted it); now `rating.plans.base_code_on_charges`, and `0063` removed stored rows (none on the seeded tenants). **`DEF-RAT-9330`** — RED: `BizError rating.plans.not_publishable`; now `already_published: true`. **`DEF-RAT-9328`** (server half) — one list with the late fee once; `charge_codes: []` charges no late fee. `9328`'s Edit half stays with task 8. **`DEF-RAT-9335` NOT fixed** (with the PO; its strict xfail is in place).

**Existing tests amended to the rulings, not deleted:** `test_wave_g_plan_versions.py` — a rename no longer makes v2 (`BR-RAT-1067`), so the cases that used a rename as "a change" use the minimum bill; `test_oq_314` now asserts the ruled window. Two cases there were already red at the tip (`the_diff_names_the_COMPONENT_that_moved`, `a_long_diff_is_CAPPED…` — `minimum_amount` refused and `base_charges` no longer moving, both since `BR-RAT-1040`/0031) and are untouched.

**Not built / left:** the `base_charges` list sort (a walk, `BR-RAT-1040`); `OQ-RAT-12786` (deposit by size — *CLOSED and built 2026-10-03, §15*); the period split at a version start is built but has met no real two-version bill; `plan_versioning.py` and `plan_writes.py` are not matched by a `human_owned.txt` glob — adding one is the PO's act (that file's own rule), ledger rows written.

**Rollback:** redeploy 2.482.1 after `manage.py migrate rating 0061_cr166_discount_lock_and_rls`. `0064` down drops the lock and the NOT NULL; `0063` down is a no-op (removed base-code rows are not restored — they billed nothing); `0062` down drops the columns and FAILS while a plan holds two versions' rows for one service — retire the extra version first; versions written by *Change from a date* lose their dates.

**The New plan form against this server (coordinator's request, 2026-10-03).** `10-scripts/cr167_plan_form_walk.mjs` now runs the WHOLE flow in server mode too (it stopped at step 2 without `CONTRACT=1`): option values are read from the `GET /plans/form-options` the page itself made. Run on PostgreSQL (`sbh_planapi`, API `:8151`, SPA `:5251`, Dana, 1440): **20 photographs `08-qa/plans-2026-10-03/form/04…23-*-server.png`**, each opened. *Publish plan* → `POST /plans` 201, stored `RCP` published from 11/01/2026 with late fee `LATE`, `RECON` as a charge, `DEPOSIT` as its deposit, floor $10.00, surcharge 25 %; *Save as draft* → `RCP-D` draft. Brazos Bend sells electric and water and holds two taxes, so the photographs show two services and two taxes where the images draw four and three (rule 37: figures are illustrations). **One thing the form should send:** `GET /plans/form-options?classes=<id>,…` (added) narrows each schedule's base to the ticked classes — without it a Residential plan's water row reads *Several base codes · BASE-W, BASE-W-COM* (photo 08, 21) where the plan's own read resolves `BASE-W` $8.00. Task for lane PLAN-FORM.

## 13 · Round 3 task 7 — the details page, six tabs (built 2026-10-03, `2.485.0`, photographed and fixed `2.485.1`, lane PLAN-DETAIL)

**What was built.** `…/plans-rates/plans/:planId` now mounts `planDetail/PlanDetailPage` (App.tsx);
the old `PlanDetail.tsx` (eight, then three tabs) and its 1,490-line test are retired. Built from
images 24–37 opened as images (B14 rule 42), our kit deciding spacing, type and components (rule 44),
each piece a component (rule 43), Tailwind only and every file on `route-b-migrated.txt` (rule 21).
Files: `PlanDetailPage.tsx`, `PlanDetailHeader.tsx`, `PlanMoreMenu.tsx`, `PlanUpcomingBanner.tsx`,
`PlanPricedAsOf.tsx`, `PlanPricedTab.tsx`, `PlanOverviewTab.tsx`, `PlanUnitsTab.tsx`,
`PlanAuditTab.tsx`, `saveCsv.ts`, `planDetailModel.ts` (the pure half) and
`07-frontend/src/api/planDetailEndpoints.ts` (the §7.3 reads in their own file).

* **Header** — ← Plans; name and code; *status · V1 · Residential · 08/01/2026 – 12/31/2026*; **Edit**
  (primary) and **More ▾**; six tabs **Overview · Services · Charges · Billing · Units · Audit** (ruling 2)
  with counts on Services and Units. **Sticky**; the tab and *Priced as of* live in the address
  (`?tab=`, `?as_of=`); old tab names land where their content is (`versions`→Audit, `accounts`→Units,
  `taxes`→Charges, `discounts`→Billing); **← / → / Home / End move between tabs** (ruling 13).
* **More ▾** — Duplicate (**held**, `DEF-RAT-9352`, hold-expiry test reads `NewPlanForm.tsx` and
  `endpoints.ts`), Retire (published; `POST /plans/{id}/archive`), and on a draft **Delete draft**
  (moved from the list lane's stopgap header button; confirm *"The draft is removed for good."*).
* **Banner** — the earliest `upcoming[]` item: *Water rate schedule v3 starts 03/01/2027. Usage charges
  $4.50 · $7.31 · $9.00 per kgal. See it* — the rates are read from the page AS OF that date, and *See
  it* opens Services at that date.
* **Overview** — tiles Units · Monthly base charges · Services · Taxes, each detail line a link to its
  tab; Details (plan name, code, customer classes · description, intended for, notes · starts, ends,
  minimum bill); the versions table (version, dates, status); *See every change in Audit*.
* **Services / Charges / Billing** — MOUNT the shared `PlanSections` (ruling 11) with `links` on:
  `["services","servicesTotals"]`, `["charges","taxes"]`, `["deposits","discounts","billingTerms"]`.
  `PlanSections` gained ONE opt-in, `fold` (B14 rule 36; Review unchanged): a service folds to its
  strip and one line *Base charges $… · Usage charges $… – $… per kgal* with *Show sizes and blocks*;
  *Expand all / Collapse all* beside *Priced as of*. A section's **Edit** opens that step of Edit.
* **Units** — `GET /plans/{id}/units`: *Search unit or premises*, *All · Occupied · Vacant* (one
  dimension declared in the table config, drawn as the kit's chips), ⤓ CSV of the whole filtered set,
  Unit · Premises · Services (*No service point*) · Account · Occupancy · On this plan since; unit,
  premises and account are links. No selection column, no Move (ruling 15).
* **Audit** — `GET /plans/{id}/audit`: *All · Plan changes · Changes underneath*, From / To, ⤓ CSV;
  ▸ · When · Who · What · Change · Reason; a row opens to **Before · After · Version**.

**The edit door (agreed with lane PLAN-EDIT, sent through the coordinator 2026-10-03).** Header *Edit*
→ `…/plans/<id>/edit?change=info`. A section's *Edit* on a published plan →
`…/edit?change=change&step=<n>`, n = 1 Services · 2 Charges · 3 Billing (Change from a date's own four
steps, image 37); on a draft → `…/edit?step=<n>`, n = 2 Services · 3 Charges · 4 Billing (the five-step
form). Asserted by literal address in `planDetail.dom.test.tsx`. Today that route still mounts
`PlanWizard`, which ignores the parameters, until task 8 lands.

**Defects.**

| Defect | What | Status |
|---|---|---|
| `DEF-RAT-9334` | The details page against the drawing | **fixed** 2.485.0 |
| `DEF-RAT-9331` | Class never named, notes never shown | **fixed** 2.485.0 |
| `DEF-RAT-9288` | Audit showed raw ids and JSON | **fixed** 2.485.0 (words from the server); three wordings left → `DEF-RAT-9360` |
| `DEF-RAT-9353` | Units premises / account cannot link | **fixed** 2.485.0 + 2.485.1 (the first fix served `account_id` empty — found by the walk) |
| `DEF-RAT-9359` | Units / Audit CSV answered 404 (`?format=csv`) | filed and **fixed** 2.485.1 |
| `DEF-RAT-9285` | A class note shown as its id | details half fixed (the page draws `value_label`); stays OPEN for the Edit half (task 8) |
| `DEF-RAT-9286` | Review counts contradict | no count is drawn on the details tabs; stays OPEN for the Edit Review (task 8) |
| `DEF-RAT-9287` | Minimum bill 10.000000 | the details page shows `$` and two places; the box is Edit's (task 8) — OPEN |
| `DEF-RAT-9352` | Duplicate has no copy act | filed, **held** with its expiry test |
| `DEF-RAT-9360` | Three Audit wordings read like data | filed, OPEN (server, `plan_reads.words_diff`) |
| `DEF-RAT-9361` | Vacant filter and row disagree on *occupied* | filed, OPEN (server, two definitions) |

**Tests.** `planDetail/planDetail.dom.test.tsx` — **26 cases**, written before the page was mounted:
run against the old `PlanDetail.tsx` (restored into the tree for the run) **21 of 25 failed** (*Unable to
find role="heading" and name /Lakeside Homes/*, *Unable to find role="button" and name "Edit Taxes"*,
*Unable to find role="link" and name "Cabin 4"*, *no banner yet* … — the old page could not render the
§7.3 body at all, crashing in `pendingScheduleChanges`), the four that passed being pure model and
hold checks; all 26 green. The blank-code banner case was red (*expected 'water' to be 'sewer'*) then
green. Server: `test_cr087_plan_summary_and_units.py` gains three cases — premises reference (red
*KeyError: 'premises_id'*), the occupied row's account (red *assert None == '01a10309-…'*), and
`?format=csv` through both views (red *assert 404 == 200*); 13 green; `test_cr167_plans_round2.py` 21
green. `tsc` (shown able to fail with a planted error), eslint, and `vitest src/features/rating
src/styles src/i18n src/components/ConfirmDialogTier` green except the census's two cases, red since
`17c2e4ea4` for `BulkRunPage` and already filed as `DEF-SHL-9347` (not this lane's; the census row
for the plan page moved to `planDetail/PlanDetailPage.tsx`, two danger dialogs as before).

**Copy.** 56 new keys in all eleven catalogues through `10-scripts/i18n_fanin.py` (written in each
language now so G15 holds; round 3's language lane reviews them); **136 dead keys retired**
(`rating.planDetail.*` of the old page and `rating.planBound.*` of its bound-changes panel — G18 found
no call site for any) and their **573** lines dropped from `g15_untranslated_baseline.txt`. G15 is red
at the tip on 812 English paste-ins that are not this lane's; it was red on 3 of mine (French
*Services*, *Vacant*) and those were translated.

**Photographs.** `08-qa/plans-2026-10-03/details/` — `24`…`37` at 1440 on PostgreSQL 16
(`sbh_plandetail`), each opened; `side-by-side.md` sets each beside its image; `walk-output.txt` is the
script's own checks (all PASS); `10-scripts/cr167_plan_detail_walk.mjs` re-runs it.

### Our judgments where drawing, kit and contract do not meet (recorded, not asked — law 13)

Decision-log row *"CR-167 TASK 7 · THE PLAN DETAILS PAGE …"* holds them:

1. **The edit door** above, agreed rather than waited for.
2. ***Delete draft* on a draft's More ▾ and Retire hidden there** — image 25 is a published plan's menu;
   a draft has nothing to retire.
3. **The banner names the EARLIEST upcoming item only** (image 24 draws one line); a rate schedule's
   second sentence is read from the page as of that date, and other kinds show the first sentence
   only — nothing is guessed.
4. **The folded line is first – last of the served order** (*$0.11 – $0.16 per kWh*), the words after
   the figure said once — no money is added or compared in the browser (hard rule 2).
5. ***Priced as of* is the kit's date field** (label above, calendar button, *Today* beside — rule 44)
   where the drawing puts the label beside the box.
6. **The header sticks through a wrapper and the arrow keys are handled on that wrapper**, so the kit's
   `PageHeader` and every other tab strip are untouched.
7. **Units' All · Occupied · Vacant are chips over ONE declared filter**, no `+ Filter` (one dimension
   only); the kit table keeps its column chooser and pager.
8. **Audit From / To start empty** — the drawing's 09/01/2026 – 10/03/2026 is an illustration (rule 37).
9. **A note stored as a class id is drawn by the server's `value_label` on the page**, not in the shared
   normaliser — the form posts `value` back unchanged.
10. **The version status *in_force* reads *Active*** as drawn; the plan's own status keeps the product's
    *Published*.
11. **Retire's consequence is one sentence** — *"It is no longer offered."* (rule 33).

### What is left

| Item | Who |
|---|---|
| Edit reading `?change=` and `?step=` (image 37 opens that step) | task 8 (PLAN-EDIT) |
| Duplicate — a copy act and `?duplicate=` on the New form | `DEF-RAT-9352` |
| Audit wordings; one definition of *occupied* | `DEF-RAT-9360`, `DEF-RAT-9361` (server) |
| Ten languages reviewed on screen | task 9 |
| The full 44-state walk | task 10 |

**Rollback:** redeploy 2.484.4. No data is written by this change (the two server changes add fields
to a read and a renderer to two reads).

## 14 · Round 3 task 8 — Edit a plan, the New form with three choices (built 2026-10-03, `2.486.0`, lane PLAN-EDIT)

**What was built.** `…/plans-rates/plans/:planId/edit` mounts `planForm/EditPlanForm.tsx`, built from
images 37–44 opened as images (B14 rule 42), our kit deciding spacing, type and components (rule 44),
each piece a component (rule 43), Tailwind only and every new file on `route-b-migrated.txt` (rule 21).
It is the New form's own steps (`PlanStep` · `DetailsStep` · `ServicesStep` · `ChargesStep` ·
`BillingStep`, §11) over a draft read back from the plan (`planEditModel.planDraftFromRow`), with
*What to change* on top (`EditPlanChoiceCards`) choosing the step list and the LOCKED fields — the
`locked` set §11 built for exactly this. The lists are `usePlanFormLists` (§11) with the plan's own
items joined in (`withPlanItems`), so a row whose code is no longer offered to a NEW plan still opens
on its value. Reads and writes are `api/planEditEndpoints.ts` against the server as built at
`2.484.0` (§9). **`PlanWizard.tsx` is retired** (§14.3).

| Choice (`?change=`) | Steps | Locked | Save → |
|---|---|---|---|
| **Name and details** (`info`, image 38–39) | Details · Review | the code (a fact), every priced field (*Services, charges and billing* as a fact strip, *🔒 Change from a date.*), the dates (facts on Review) | `PATCH /plans/{id}` — `details` with the MOVED keys only, same version (`BR-RAT-1067`); *Save changes*, held until something moved |
| **Change from a date** (`change`, images 37, 40–42) | Services · Charges · Billing · Review | the six detail fields | `POST /plans/{id}/versions` — the MOVED content + `effective_from` + `effective_to` if typed + `reason` + `publish`; *Save new version* (`false`) · *Publish new version* (`true`), ruling 10 — ONE call, so `DEF-RAT-9330` cannot recur |
| **Fix a mistake** (`correct`, images 43–44) | Services · Charges · Billing · Review | the detail fields and the dates (facts) | `POST /plans/{id}/corrections` — the MOVED content + `reason` + `version` (the one in force today); *Save correction*, held until something moved |
| *(a draft — no cards)* | Details · Services · Charges · Billing · Review | nothing | `PATCH /plans/{id}` with the moved keys, then *Publish plan* → `POST /plans/{id}/publish`; *Save as draft* is the PATCH alone |

Review (39, 41, 44): *What changes* before → after (or *Nothing changed yet.*), the shared
`PlanSections` with *Edit* only where the choice can change something (39: Plan only; 41, 44: every
priced section, not Plan), *Dates* (facts, or *New version starts* * with *Today's version ends
12/31/2026.*), *Reason* * (*Shown in Audit.*), and *How it is saved* (41: *v1 · today 08/01/2026 –
12/31/2026 Gets an end date · v2 · new 01/01/2027 – No end New version* and *N units move to v2 on
01/01/2027.*; 44: *v1 · today … Superseded, kept · v1 · correction … Replaces v1* and *Issued bills
keep v1. Correct those bills separately.*). Saved: *<name> saved* and one sentence (*Saved on this
version. Logged in Audit.* · *v2 starts 01/01/2027. Logged in Audit.* · *v2 saved. Not published
yet.* · *v1 corrected. Logged in Audit.*).

### 14.1 · The addresses, agreed with lane PLAN-DETAIL (coordinator relay, 2026-10-03)

| From | Address | Opens |
|---|---|---|
| Header *Edit* | `/plans-rates/plans/{id}/edit?change=info` | *Name and details*, step 1 |
| A section's *Edit* on a PUBLISHED plan | `…/edit?change=change&step=<n>` — 1 Services · 2 Charges · 3 Billing (image 37) | that step of *Change from a date* |
| A section's *Edit* on a DRAFT | `…/edit?step=<n>` — 2 Services · 3 Charges · 4 Billing | that step of the five |
| No or unknown `change` | `…/edit`, `?change=banana` | *Name and details* |

`planEditModel.planEditPath(planId, mode|null, step?)` spells them; `?step=` outside the choice's list
opens step 1. Proved: `EditPlanForm.dom.test.tsx` *?change=change&step=2 opens Charges*, and in the
browser `37-detail-section-edit.png`.

### 14.2 · Our judgments (recorded, not asked — law 13; decision log *"CR-167 TASK 8 · EDIT A PLAN"*)

1. **Only what moved travels.** Each choice sends the keys whose value changed and nothing else; a
   cleared minimum bill is sent as `null`. The server copies the version's bindings and replaces a set
   only when its key is present, so an untouched table is kept EXACTLY as filed — which matters on
   real data: both of Brazos Bend's taxes reach `SCW-RES` through its JURISDICTION and read back as
   two taxes; re-sent as `{tax}` they would become attachments. `planUntouchedSave.dom.test.tsx`
   (`DEF-RAT-5780`, ported from the wizard as §5.5 requires) now asserts an untouched *Publish new
   version* sends `effective_from`, `reason`, `publish` and nothing else.
2. **A re-ordered table is not a change** (lists compared order-free).
3. **The late fee is a row, read back as one (`DEF-RAT-9328`, Edit half).** The draft opens with
   `charge_codes_touched`, so the New form's default LATE row is never added to a plan someone already
   chose for; a plan with no charge code opens with none.
4. **The figures the boxes open on are the VERSION's, read from the sections** — never the top-level
   `minimum_bill_amount` / `outside_city_percent`, which are `rate_plans` columns mirroring the HEAD.
   Found on the walk before shipping: after a v2 from 01/01/2027 at $12.00, *Fix a mistake* on v1
   opened with *Minimum bill $12.00* where v1 has none (`44-…` was re-photographed after the fix). The
   minimum is read at two places (the section's display); a stored 4-place figure is never re-sent
   unless the clerk moves it.
5. **Change from a date builds on the LATEST version.** With a later version already filed, the form
   reads the plan `?as_of=` that version's start (the server copies the version in force on the new
   start) and the next number is one past the highest (*v3 · new*).
6. **A correction keeps its number — the drawing's *v2 · correction* is an illustration (B14 rule
   37).** `services.correct_plan_version` copies `version_no` (`DEF-RAT-5710`, `OQ-RAT-12409` A), so
   the rows read *v1 · correction — Replaces v1*, the figure the server writes.
7. **Image 42 is named *new version published* but draws *Enter the reason.* with *Fix 1 thing
   first.*** Both states are photographed (`42-edit-change-refused.png`, `42-edit-change-published.png`).
   A refusal by the FORM routes to its step (`refusedOnStep`) and never shows the frame's failure card
   (`DEF-RAT-9362`, fixed in the New form too).
8. **Switching cards starts that flow again from the plan as saved** (the tax and discount edits'
   judgment).
9. **The section heading *Services, charges and billing* is kept as drawn (4 words, one over a
   label's cap)** — no three-word heading names the three steps it locks.

### 14.3 · `PlanWizard.tsx` retired — blast radius both ways

| What | Done |
|---|---|
| `PlanWizard.tsx` (5,407 lines) | deleted; `App.tsx` mounts `EditPlanForm` (hold test in `NewPlanForm.dom.test.tsx` flipped to assert it) |
| Its last product caller: `PlanSummaryCard.tsx` (1,145 lines; the old Overview card, superseded by `PlanSections`) | deleted with it — PLAN-DETAIL had already retired `PlanDetail.tsx`, its other caller |
| `ACCOUNT_TYPES_LIST`, read by `RateScheduleThreeStep.tsx` and `ChargeCodeWizard.tsx` | moved unchanged to `ratingShared.tsx` |
| Tests that only exercised the wizard or the card: `PlanWizard.test.tsx`, `cr087PlanWizard.dom.test.tsx`, `planWizardBetaWalk.dom.test.tsx`, `planWizardBoundBase.dom.test.tsx`, `planWizardTables.dom.test.tsx`, `baseChargeNotAddable.test.ts`, `archivedSchedulePicker.test.ts`, `PlanSummaryCard.test.tsx`, `planSummaryBaseCode.defRat9336.test.ts` | deleted. What they guarded now lives in the new form's tests and the server: the base-code refusal (`rating.plans.base_code_on_charges`, §9), schedules without an activated version (`plan_builder_queryset`, read by `form-options`), the billed base code (`PlanSections.dom.test.tsx`, `DEF-RAT-9336`) |
| Tests that read the wizard in passing | `planUntouchedSave.dom.test.tsx` PORTED (above); `PlansRatesPage.test.tsx` lost one `selectableSchedules` line (the rule is the server's); `cr087ClassSizeGrid.dom.test.tsx` lost its two card cases; `ConfirmDialogTier.dom.test.tsx` census lost the wizard's archive confirm (total 45 → 44) and its `computed` figure was corrected 4 → 3 (stale since `6f107d0a7`) |
| Catalogue keys only those two files read | **274** retired from all eleven catalogues through `10-scripts/i18n_fanin.py retire` (found as G18's *dead* set after minus before; list in `08-qa/plans-2026-10-03/edit/retired-keys.txt`), and their **257** untranslated-baseline lines dropped (CR-166's precedent) |
| `route-b-migrated.txt` | both files' lines removed (the card's left as a dated comment) |

**Copy.** 56 keys under `rating.planEdit.*` in all eleven catalogues (`i18n_fanin.py`); 33 reuse the
catalogues' own words for the same idea (the discount edit's cards, columns, versions; *No end*), 23
are new and written per language — task 9 reviews them on screen. French *Version* → *N° de version*
so G15 is not handed a value identical to English.

### 14.4 · Proved on PostgreSQL 16 in the browser at 1440

`10-scripts/cr167_plan_edit_walk.mjs` (API `:8211`, SPA `:5311`, `sbh_planedit`: `migrate` +
`seed_demo` + `load_sample_data --tenant brazosbend`, Dana) does the three ways on ONE published plan;
`10-scripts/cr167_plan_edit_db_check.sh` reads what they wrote. Photographs, each opened:
`08-qa/plans-2026-10-03/edit/` — `37`, `38`, `39`, `39-…-unchanged`, `39b`, `40`, `41`,
`42-…-refused`, `42-…-published`, `43`, `44-…-noreason`, `44`, `44b`, `audit-after-three-ways`;
side-by-side notes in `side-by-side.md`; `db-before.txt` / `db-after.txt`; `audit-csv.txt`.

**What the database says** (`SCW-IND`, `db-before.txt` → `db-after.txt`; an earlier run on `SCW-COM` wrote the same): ONE `rate_plans` row
throughout (same id); *Name and details* → description changed, version still 1, audit
`plan.details_updated`; *Change from a date* → v1 `2026-08-01 – 2026-12-31`, v2 `2027-01-01 – (no
end)` at minimum `12.000000`, both `published`, nothing deleted, audit `plan.version_saved` +
`plan.version_published`; *Fix a mistake* on v1 → a NEW row `v1`, `2026-08-01 – 2026-12-31`,
budget billing on, `is_correction`, the old v1 row KEPT and marked superseded (its bindings moved to
the correction: 2 services · 2 schedules · 7 tax rules), audit `plan.version_corrected`. Audit
(`GET /plans/{id}/audit`, `audit-csv.txt`) lists each: *edited* (description before → after),
*new_version* and *published* (*Starts: 01/01/2027*, the reason), *correction* (the reason).

**Defects.** `DEF-RAT-9328` (Edit half) and `DEF-RAT-9332` (Edit half) fixed here — red first: the
App route test *expected … to match /…edit", element: <EditPlanForm \/>/* against `532df04e9`, and the
new test files failed to import there. Filed and fixed: **`DEF-RAT-9362`** (a form-side refusal shown
as the frame's *The plan was not saved.* card — red: *expected <p class="state-failed-title"> to be
null*). Filed, NOT fixed (server, 🔒 rating): **`DEF-RAT-9363`** — Audit's correction row does not
say what a Fix a mistake changed, and the old tab's diff lists a rename and v2's minimum it did not
touch.

**Left.** *Save new version* files a draft v2 that nothing on screen publishes yet: the server has
`POST /plans/{id}/versions/{n}/publish`, and the details page (task 7) is the place to offer it — with
one open, another *Change from a date* is refused `rating.plans.one_draft_version` on its start box.
Ten languages reviewed on screen (task 9).

**Rollback:** redeploy `2.485.1`. No stored fact changes from this screen alone; `PlanWizard.tsx`
comes back with the redeploy.

## 15 · Two PO answers built — a bill charges the base its schedule names; a deposit priced by class or size (lane PLAN-MONEY, 2026-10-03)

Decision log *"FOUR PO ANSWERS"* items (1) and (2), and their *Pending propagation* list. Measured on
PostgreSQL 16 (`sbh_planmoney`: `seed_demo` + `load_sample_data` on `brazosbend`, and the §7.1 probe
utility `plansrv-rcp` rebuilt by the new `10-scripts/cr167_money_world.py` — §7.1 named the recipe in
prose and no script).

### 15.1 · `DEF-RAT-9335` — the base the schedule names (`2.487.0`)

**PO verbatim:** *"(a) Fix it: use the base the schedule names. Bills refused today start going
out; bills already issued don't change."*

**The fix (🔒 `apps/rating/resolution.py`, R4):** `resolve_charge_codes` takes the base code each
rate schedule NAMES (`named_base`, built in `resolve` from `tariff_versions.base_charge_code`) and
skips every OTHER `is_base` code of that service before pricing it — so an un-named code that does
not price the customer's size can no longer stop the bill. A schedule that names nothing is narrowed
exactly as before (`DEF-468` still refuses two inferred base codes); the named code itself is still
priced at the size and still refuses a size it does not price. Nothing that billed before can move:
the skipped codes were read only by `resolve_base_charge`, whose named arm ignores them, and
`Resolution.charge_codes` prices no line of its own. The live gather path
(`selectors.base_charge_from_charge_code`) already narrowed to the named code before pricing and
was not touched.

**Red first.** The strict-xfail test
`tests/test_def_rat_9335_unnamed_sized_base_code_does_not_stop_the_bill.py` ran `1 xfailed` before
the edit; the marker is removed and two guard cases added (schedule names nothing → still refused by
the sized code; the named code still refuses an unpriced size). Against tip `8cfa7ab19` the
un-marked case fails with *"R4: charge code 'BASE-W-FIRE' applies to this account and states no
amount for connection size 'W-58' on service 'water'"*; after, 3 passed.

**The worked bill, on PostgreSQL** (`10-scripts/cr167_def_rat_9335_probe_pg.py plansrv-rcp
AC-2026-00025` — names `BASE-W1` on `SCW-RES`'s water schedule and dates the two probe codes'
prices 2026-01-01, both stated probe shortcuts; run once from a worktree at the tip and once with the
fix):

| | Tip `8cfa7ab19` | With the fix |
|---|---|---|
| AC-2026-00025, September 2026, 5/8" water | **BLOCKED** — *"R4: charge code 'BASE-W-FIRE' applies to this account and states no amount for connection size 'W-58'"* | Fire $84.00 · Sewer base $9.00 · Sewer usage $27.00 · **Water base $10.00** · Water tier 1 $20.00 · Water tier 2 $6.50 = **$156.50** before tax (+ $3.13 local tax on this seed) |

$146.50 + $10.00 = **$156.50**, the PO's figure.

**Before / after re-pricing of every seeded account** (`10-scripts/cr167_task3_bill_compare_pg.py`
snap — the bill engine's preview, rolled back — of each account's last issued period and October
2026; *before* run from the tip worktree, *after* with the fix, same database):

| Tenant | Account-periods | Differences | What differed |
|---|---|---|---|
| `brazosbend` | 124 | **0** | — (sum of lines $39,721.23 both ways) |
| `plansrv-rcp` | 124 | **50** | **all 50 were blocked before** (no lines) and bill after — 47 SCW-RES accounts' Aug/Sep/Oct periods, each now with a $10.00 water base from `BASE-W1`; **no priced period changed** |

No issued bill is touched: the preview writes nothing, and issued bills are never re-priced (hard
rule 4). Golden: `pytest -m golden` **25 passed, 1 xfailed** and `03-golden-verify.py` **33 PASS,
0 FAIL** — unchanged.

### 15.2 · `OQ-RAT-12786` CLOSED — a deposit priced by class or size (`2.487.0`)

**PO verbatim:** *"(a) Class or size: the deposit table gets a size column, like charge codes
have."* `BR-RAT-020` stamped **SUPERSEDED in part** (dated, with the ruling); `BR-RAT-023`'s *"By
size is NOT built"* amended; the register row's status AND body rewritten (the old body's three
claims — class only, refused by name, `NotImplementedError` — are now false and say so); §7.5 B1/B3
and §9's three citations stamped.

**What was built (server):**

| Where | Before | After |
|---|---|---|
| 🔒 `services._validate_plan_deposit_codes` (plan write) | a sized deposit code refused, `rating.plans.deposit_code_priced_by_size` | accepted; the key is **retired** from all eleven catalogues (`i18n_fanin.py`) |
| `plan_reads.form_options` (`deposit_codes[]`) | a sized code dropped | offered, `priced_by: "size"`, rows `Water 5/8" 150.00 · Water 2" 600.00` |
| `plan_reads._deposits` (`GET /plans/{id}?as_of=`) | — | unchanged code path; serves `priced_by: "size"` and one row per size (the *Class or size* column) |
| 🔒 `selectors.deposit_rule_for` / `plan_deposit_for` | a sized code raised `NotImplementedError("OQ-RAT-12786")` | priced by `charge_prices.answer_from_rows` at the **connection size of the service the code names** on this unit — new 🔒 seam `rating.seams.connection_size_for` → `metering.selectors.connection_size_for`, the same seam billing sizes a base from. Callers say which connection: `unit_id` (customers) or `account_id` (first bill) |
| 🔒 `billing/first_bill.deposit_line_for` | — | passes the account; an unpriced size **refuses the first bill by name** (never billed as no deposit) |
| `customers/seams.deposit_rule_for_account` · `customers/deposit.plan_asks_deposit` · `move_record_reads` | — | the unit travels; an unpriced size is refused **`customers.deposit.sizeNotPriced`** (*"No deposit priced for this size."*, eleven catalogues) on the Deposit step and at commit; the move record reads it as no standard instead of crashing on `Decimal("None")` |

**Judgments of ours (decision log row *"`OQ-RAT-12786` BUILT"*):** (1) the size is the one of the
service the deposit code names — the lane recommendation the PO was shown in §7.5 B3; (2) a size the
code does not price, or no recorded size, is a **named refusal**, never `None` — `None` means *this
plan asks no deposit* and would let a customer connect with none taken; (3) a code that prices
nothing for this customer's CLASS is still skipped, as before; (4) class beats every-class per size,
the one rule every charge code already follows (`charge_prices.resolve_for_class`).

**The front end needed one change, and it was on the customers side.** The form's step-4 Deposits
table and the shared `PlanSections` Deposits section already draw *Priced by* and the *Class or
size* rows from the server (images 17, 21, 30); a sized case is now asserted in
`PlanSections.dom.test.tsx`. But the New account / Move-in **Deposit step** read ANY failure of
`GET /accounts/deposit-standard` as *"plan unreadable"*, so the new refusal would have reached the
clerk as the wrong sentence: `depositCapability.tsx` now shows `customers.deposit.sizeNotPriced`
when the server names it (red first against the tip's step: *expected … to contain
'customers.deposit.sizeNotPriced'*; 35/35 after).

**Red first** — `tests/test_oq_rat_12786_deposit_by_class_or_size.py` (8 cases) against tip
`8cfa7ab19`: **7 failed** — `VAL-002 (rating.plans.deposit_code_priced_by_size)` on the four plan
cases, form-options without the code, *"DID NOT RAISE ValidationError"* on the customers case — and
the class-priced guard passed; after, **8 passed**. The first green run found two faults in this
lane's own new code before it shipped (a `code=` keyword colliding with `_fe`'s own parameter, and a
fixture leaving its tenant context) — both fixed in the same file.

### 15.3 · Proved through the screen on PostgreSQL 16 at 1440 (`2.487.0`, size order fixed `2.488.1`)

`10-scripts/cr167_plan_money_walk.mjs` on `sbh_planmoney` (`brazosbend`), data from
`10-scripts/cr167_plan_money_walk_prep.py` — `DEP-SIZE` (refundable, water, 5/8" **$150.00**, 2"
**$600.00**) through `services.create_charge`, and, **as a stated probe shortcut**, water meters
copied onto three VACANT `SCW-RES` units (New account offers only vacant units, and every vacant
seeded unit has a water service point and no meter, so none has a size). Photographs in
`08-qa/plans-2026-10-03/money/`, each opened.

| Step | What the screen did | Photo |
|---|---|---|
| Edit `SCW-RES` › *Fix a mistake* › Billing › *+ Add deposit* | the list offers `DEP-SIZE · Security deposit by meter size`; the row reads *Priced by* **Size**, *Amounts* **Water 5/8" $150.00 · Water 2" $600.00** (image 17) | `17-res-step4-deposit-by-size.png` |
| Review › reason › *Save correction* | *What changes: Deposits None → DEP-SIZE*; `POST …/corrections → 200`; *saved v1 corrected* (image 21) | `21-res-review-deposit-by-size.png` |
| Details › Billing | Deposits: *Priced by* Size · *Class or size* Water 5/8" / Water 2" · *Amount* $150.00 / $600.00 (image 30) | `30-res-details-billing-deposit-by-size.png` |
| the same on `SCW-COM` | identical | `17-com-…`, `21-com-…`, `30-com-…` |
| New account › Deposit, unit `SCW-U-207` (5/8") | *Amount* **150.00**, *Set by the plan.* | `deposit-step-58-SCW-U-207.png` |
| … unit `SCW-U-351` (2") | *Amount* **600.00** | `deposit-step-2-SCW-U-351.png` |
| … unit `SCW-U-353` (3/4", a size `DEP-SIZE` does not price) | `GET …/deposit-standard → 422`; *"No deposit priced for this size."* — nothing offered to take or waive | `deposit-step-34-SCW-U-353.png` |
| … unit `SCW-U-355` (no meter, no size recorded) | the same refusal | `deposit-step-none-SCW-U-355.png` |
| **End to end:** `SCW-U-207`, deposit taken in cash today, *Create & activate* | `POST accounts → 201`, **`AC-2026-00054`**, deposit `required` **$150.0000** taken, payment `PY-261003-0084` cleared; database: `accounts.deposit_assessed` 150.0000, `deposit_on_file` 150.00, `payments` purpose `deposit` 150.00, journal **DR 1010 $150.00 / CR 2300 $150.00** | `deposit-58-review.png`, `deposit-58-created.png` |

**Found by the photographs and fixed — `DEF-RAT-9503` (low, `2.488.1`):** the sizes read in CODE
order — *Water 2" $600.00* above *Water 5/8" $150.00* — because the server serves price rows by
`size_class` code (`W-2` < `W-58`). Red first in `PlanSections.dom.test.tsx` (*expected [ 'Water
2"', 'Water 5/8"' ] to deeply equal [ 'Water 5/8"', 'Water 2"' ]*), fixed with one helper
(`PlanSections.pricedRowsInOrder`, `sizeOrder.sortBySize`) used by the Deposits and Charge codes
sections and step 4's *Amounts*. The `17-` and `30-` photographs are re-taken after the fix; the
two `21-` Review photographs were taken before it (they show 2" first) and are kept as taken.

**Left for the PO, not built (rules, not ours):** a NEW connection whose meter is not yet fitted has
no size, so a plan whose deposit is priced by size refuses its Deposit step until the meter (with
its size) is recorded — see the lane's report for the plain-English question. **ANSWERED 2026-10-04 — PO *"(c) Let the clerk pick the size on the Deposit step."*; built §21 (`DEF-CUS-9521`, `2.492.0`).**
## 16 · Follow-up — "complete these and fix bugs" (built 2026-10-03, `2.489.0`, lane PLAN-FIXES)

PO, of the plans pending-work table: *"complete these - and fix bugs"*. Every item below was filed
first (or already filed), written as a test that FAILED against `789fbf0e9`, fixed, and walked in a
browser at 1440 on PostgreSQL 16 (`sbh_planfixes`: `migrate` + `seed_demo` + `load_sample_data
--tenant brazosbend`, Dana). Money items (`DEF-RAT-9335`, deposits by size) are lane PLAN-MONEY's
and are not touched here.

| Defect | What | Fix | Status |
|---|---|---|---|
| `DEF-RAT-9352` | Duplicate had no copy act (held, image 25) | `POST /plans/{id}/duplicate {name, code}` → a new DRAFT from the version in force today; More ▾ *Duplicate* opens a two-box dialog, then the copy | **fixed** — hold released, its expiry test replaced by the act's test |
| `DEF-RAT-9364` (new) | *Save new version* left a v2 nothing on screen could publish | details page: *v2 not published yet. Starts 01/01/2027.* **Publish v2** → confirm *v1 ends 12/31/2026.* → `POST …/versions/2/publish` | **fixed** |
| `DEF-RAT-9365` (new, coordinator) | Edit Review *Minimum bill None → 12.00* | `fieldWords` formats through `moneyShown` — *$12.00*, Change from a date and Fix a mistake alike | **fixed** |
| `DEF-RAT-9360` | Audit words read like data | `$`-money, *None* for an empty list, list facts by name, status words, reason not repeated, a same-version edit names the version in force that day | **fixed** (🔒, review row) |
| `DEF-RAT-9363` | A correction's Audit row did not say what changed | before and after read with the corrected VERSION's terms (`_version_terms_view`) | **fixed** (🔒, review row) |
| `DEF-RAT-9361` | *Vacant* listed Apt 102 under a row reading *Occupied* | one definition: an account whose status is not terminal (`seams.ACCOUNT_CLOSED_CLASS`); the row's `vacant`, the filter and the CSV read it; an open account wins over a newer closed one | **fixed** (🔒 `selectors.py`, review row) |
| `DEF-RAT-9285` | A class note shown as its id (Edit half) | verified: reopened draft shows *Residential* (`9285-draft-details-note.png`) | **closed** with evidence |
| `DEF-RAT-9286` | Review counts contradict | verified: Review's panel says 2 services · 1 charge code · 8.25% · 3 discounts beside sections listing exactly those (`9286-draft-review.png`) | **closed** with evidence |
| `DEF-RAT-9287` | Minimum bill box *10.000000* | verified: the box reads *10.00* on reopen (`9287-draft-billing-minimum.png`) | **closed** with evidence |
| `DEF-RAT-9329` | Taxes step: nine rows, *No authority recorded* | verified on `SCW-RES`: two taxes, one row each, 8.25% combined (`9329-charges-taxes.png`) | **closed** with evidence |

**Red first (quoted).** Server, against `789fbf0e9` (`pf-red` worktree, default suite):
`AttributeError: module 'apps.rating.plan_writes' has no attribute 'duplicate'` (3 cases);
`assert 'Charge rules: — · Reason: x' == 'Charge codes: None'`; `assert 2 == 1` (the same-version
edit named v2); `assert 'Reason: — · Version terms: —' == 'Budget billing: No'` and
`… == 'Minimum bill: $10.00'`; `assert False is True` (Apt 102's row under Vacant);
`['Unit 1,…,AC-9361,,Occupied,06/01/2026', …]` (the CSV). Front end: *More ▾ … Duplicate* expected
enabled; the duplicate dialog, the draft banner (2 cases) — 4 failed of 30;
`EditPlanForm.dom.test.tsx` *expected "Minimum bill10.0012.00" to equal "Minimum bill$10.00$12.00"*.
**Green:** `test_cr167_plan_fixes.py` 12 + `test_cr087_plan_summary_and_units.py` 16 on SQLite and
PostgreSQL; with `test_cr167_plans_round2.py` and `test_cr167_plan_versions_pg.py`, 49 green on
PostgreSQL. `planDetail.dom.test.tsx` 29, `EditPlanForm.dom.test.tsx` 17.

**Walk.** `10-scripts/cr167_plan_fixes_walk.mjs` — photographs in `08-qa/plans-2026-10-03/fixes/`,
each opened; 16 checks PASS (one first read FAIL was the walk's own pattern — the row reads *Fixed a
mistake*, not *correct* — fixed and re-read with `AUDIT_ONLY=1`).

### Judgments (decision log *"CR-167 FOLLOW-UP · PLAN FIXES …"*; law 13)

1. **Duplicate is a server copy with a new name and code**, not `?duplicate=` on the New form — one
   act, one transaction, and the source is never written. **From the version in force today**, a
   draft, **no units, no history, no dates**; discounts whose offer already ended are not copied.
2. **The dialog's boxes start empty** — a pre-filled *(copy)* name is a near-duplicate a clerk must
   notice; the server refuses a name or code in use under its box.
3. **A saved new version is published from the details page** (not drawn): an info strip above the
   upcoming banner with **Publish v2**, and a confirm whose consequence names what ends.
4. **Occupied = an account whose status is not terminal** (the filter's definition); the row names
   a closed account and reads *Vacant*.
5. **Audit reads stored rows differently, rewrites none** — the fix is in the reader, so rows already
   written read correctly.

**Copy.** 12 new keys (`rating.planDetail.duplicate.*`, `draftVersion.*`,
`confirm.publishVersion.*`, two toasts) written in all eleven languages through `i18n_fanin.py`.

### 16.1 · Two more, reported by lane PLAN-MONEY (`2.489.1`)

| Defect | What | Fix | Status |
|---|---|---|---|
| `DEF-RAT-9504` (new) | *Several base codes · BASE-W, BASE-W-COM* and *Monthly base charges —* on `RES-STD` / `COM-SM` (electric on `IND`) | **Honest data** — those plans name no class, the bill picks by the account's class; `_base_block`'s ambiguous state now serves `options` (each code with its classes by name) and the base cell draws *BASE-W · Residential* per line; no single figure | **fixed** |
| `DEF-CUS-9505` (new) | New account Review showed no deposit rows | `ReviewStep` gets the Deposit step's form and draws `DepositReviewRows` under a *Deposit* block (step 4) | **fixed** |

Red first: server `KeyError: 'options'` at `789fbf0e9`; `PlanSections.dom.test.tsx` *Unable to find an element with the text: BASE-S · Residential*; `NewAccountWizard.test.tsx` *Element type is invalid … got: undefined* (the review took no deposit). Green: the three files, `tsc`, eslint.

### 16.2 · Found on our own walk (`2.489.4`)

| Defect | What | Fix | Status |
|---|---|---|---|
| `DEF-RAT-9506` (new) | A DRAFT plan (the duplicated copy) showed *v1 not published yet. Publish v1* — a second door beside Edit's *Publish plan* that would publish the version and leave the plan a draft | the banner shows on a PUBLISHED plan only | **fixed** |

Red first: *expected null* for `plan-draft-version` on a draft plan. **Walk:** `08-qa/plans-2026-10-03/fixes/` re-taken on a fresh database at `2.489.1` (the copy's overview at this build) — `walk-output.txt`, **17/17 PASS**, then the copy re-read: 9506 PASS; each photograph opened.

### 16.3 · Three seen on the Japanese Services tab (coordinator, from lane PLAN-LANG's `detail-3-services-ja-JP.png`; `2.489.5`)

| Defect | What | Fix | Status |
|---|---|---|---|
| `DEF-RAT-9507` (new) | Base sizes in code order (*1", 1½", 2", 3", 3/4" … 5/8"*) | `baseLines` and per-size usage rows (`usageRowsInOrder`) sort with `sortBySize`, as `DEF-RAT-9503` did for priced rows; the form's Services step reads the smallest size's base and minimum | **fixed** |
| `DEF-RAT-9508` (new) | *Rate* read as a TAX rate: ja 税率, ko 세율, it *Aliquota*, pt-BR *Alíquota* | `rating.planSections.service.rate` worded as a unit price in eight catalogues (ours to choose, law 13): de *Preis*, es / es-MX *Tarifa*, fr *Tarif*, it *Tariffa*, ja 単価, ko 단가, pt-BR *Tarifa*; hi *दर* and id *Tarif* kept | **fixed** |
| `DEF-RAT-9509` (new) | Service headings in English on every language | `serviceWord(code, name, t)` — the catalogue's `rating.service.<code>`, the server's name only as fallback — on the section heading and its Edit label, the Services tile and the upcoming banner | **fixed** |

Red first: *expected [ 'Water 1"', 'Water 1½"', … ] to deeply equal [ 'Water 5/8"', 'Water 3/4"', … ]*; *it-IT: Aliquota: expected true to be false*; the Japanese heading test failed on *Water*. Green: `PlanSections.dom.test.tsx` 18, planDetail 30, planForm; tsc, eslint.

**Rollback:** redeploy `2.488.2`. A copy made with Duplicate is an ordinary draft plan (delete it
with *Delete draft*); a version published from the banner is published exactly as *Publish new
version* would have.

## 17 · Round 4 task 9 — the plan screens in eleven languages (`2.486.1`, `2.488.2`, `2.489.2`, lane PLAN-LANG)

**Scope.** Every key the plan screens render: the Plans list, *New plan* (five steps and the saved
panel), the details page (six tabs, *More ▾*, the upcoming-version banner, the Retire and Delete
dialogs) and *Edit* with its three choices. That is **545 keys** — every key under
`rating.plan.*`, `rating.plans.*` (the list and the server's refusals), `rating.planForm.*`,
`rating.planDetail.*`, `rating.planSections.*`, `rating.planEdit.*`, `rating.planUnits.*`,
`rating.planSummary.*`, and the 22 keys of other families these files read (`rating.taxDetail.*`
audit columns, `rating.denied`, `rating.readOnlyReason`, …) — **× 10 catalogues**, plus **50 new
keys** (below) and the **12 keys** lane PLAN-FIXES added for Duplicate and Publish-version while
this lane worked. Defects `DEF-RAT-9368` (the copy) and `DEF-RAT-9502` (the server's English).
Every catalogue change went through `10-scripts/i18n_fanin.py` (`apply`, `allow_overwrite`); no
catalogue was round-tripped by hand.

**The rule applied (B14 rule 35), as on the tax and discount screens (§15 of `CR-165-BRC10` and
`CR-166-BRC10`).** One word per idea per catalogue — the word that catalogue already uses most,
counted across the whole catalogue (and across `rating.*` where a word means something else
elsewhere):

* **de** *Tarif* (plan), *Sparte* (service, as the discount screens), *Fassung* (version — *Neue
  Version* → *Neue Fassung*), *Preisliste* (rate schedule, 60 against 10 *Preisblatt* and 4
  *Tarifblatt*), *Gebührencode* (49 against 7 *Entgeltcode*), *Kundenklasse* (23 against 13
  *Kundengruppe*), *Grundgebühr*, *Konto* (not *Vertragskonto*), *Anschluss* for a service point;
  the audit tab is *Prüfspur* as `rating.definition.tab.audit` reads; **one voice, *Sie***
  (1,577 against 11 *du*) — the plan screens mixed *Lege sie an* with *Geben Sie*.
* **es** *tú* everywhere (as the tax and discount screens); *inmueble* (107 against 45 *predio*),
  *depósito* (not *fianza*), *añadir* (194 against 32 *agregar*), *cargo base* (not *cuota fija*,
  which is this catalogue's word for budget billing), *alcantarillado*, *autoridad* (not
  *jurisdicción*), *justificante*.
* **es-MX** *recibo* for a bill, *predio* (96 against 49), *agregar*, *pago nivelado*, *clase de
  cliente* (the form said *tipo de cliente*), *cargo base*; 34 English values written.
* **fr** *forfait* for a plan — the catalogue had it as *forfait*, *offre*, *formule*, *tarif*,
  *plan* and the machine's *Planifier* on one screen; *grille tarifaire* (not *barème*), *code de
  facturation* (not *code de frais*), *site* (as the tax lane), *unité* (not *logement*/*lot*),
  *abonnement* for a base charge (27 against 18 *frais fixes*), *dépôt*, *catégorie de client*;
  the machine's *Taper* (Type), *Coder* (Code), *Plan d'archivage*, *Pas encore de projets* gone.
* **hi** *प्लान* (205 against 199 *योजना*), *दर-सूची*, *आधार शुल्क* (40 against 24 *मूल शुल्क*),
  *इकाई* (not *यूनिट*), *ड्राफ़्ट*, *सेवामुक्त करें*, *प्राधिकरण*, *खपत शुल्क*; *ग्राहक वर्ग*
  for a customer CLASS (8 = 8 against *श्रेणी*, chosen because *श्रेणी* is this catalogue's word
  for a deposit CATEGORY on the same form); grace is *रियायती अवधि* as the discount lane ruled.
* **id** *Paket* (not *Rencana*), *Jejak audit*, *otoritas*, *kode biaya*, *terbitkan* (not
  *publikasikan*), *Deposit* (the form said *Deposito*, a time deposit).
* **it** *Storico* for the audit tab, *tariffario*, *quota fissa*, *imposta* (104 against 30
  *tassa* in `rating.*`), *bolletta*, *conto*, *immobile*; *Orari tariffari* and *Piano di
  archiviazione* gone.
* **ja** *プラン* (342 against 73 — the list's *計画* column was the machine's), *版*, *ユニット*
  and *物件* (as the premises screens), *保証金* (not *預金*/*預り金*), *顧客区分*, *料金コード* (not
  *チャージコード*/*課金コード*), *廃止*, *当局*, *使用料*, *状態*, *履歴*; 34 English values written.
* **ko** *요금제* (not *계획*/*플랜*), *세대* and *건물*, *보증금* (not *예금*), *기본요금*, *요금
  코드*, *고객 등급*, *폐기*, *수정* (as the discount lane), *이력*, *과세 당국*; *게시 계획* gone.
* **pt** *tabela de tarifas* (not *Cronograma de taxas*/*Programações de taxas*), *tarifa fixa*
  (14 in `rating.*`), *fatura* for a bill, *imóvel*, *depósito* (not *caução*), *Estado* as the
  discount lane ruled; *Plano de arquivo* gone.
* French plural **Services** is drawn as *Prestations* where it is a standalone label and
  *service(s)* inside a sentence: that is the catalogue's own split (22 against 16 for the bare
  label, 48 against 8 for the singular), and the bare English spelling *Services* is the one value
  G15 cannot tell from a paste-in.

**The server's English, and why it took code (`DEF-RAT-9502`).** CR-167 §7.6 has the server send
finished English words, and no catalogue held them, so every check passed while a German clerk read
*Block (per month)*, *Over 500 kWh*, *$0.14 per kWh*, *Base charges by meter size*, *Tiered*,
*After the due date*, *Usage and base charges*, *Everyone* and the whole Audit *Change* column
(*Starts: 01/01/2027 · Status: draft → Status: published*). The fix is additive: the server
**also** sends the code behind each word — usage rows' `label_key`/`label_args`, `season`,
`rate_amount`/`rate_unit`; price rows' `everyone`; taxes' `what_is_taxed`; audit rows'
`before_facts`/`after_facts` (`key`, English `label`, `kind` = `bool`/`date`/`status`/`none`/`text`,
`raw`) and `facts_more` — and `PlanSections`, `ChargesStep`, `BillingStep`, `ServicesStep` and
`PlanAuditTab` word them from the catalogue, falling back to the English only for a code no
catalogue names. The English fields stay (the audit CSV reads them). Words that ARE the utility's
data stay as served: size names, window and season names, schedule, charge, tax and discount
names, GL account names, the audit *Reason*.

| Language | Plan keys reviewed | English written | Older values changed | New keys | Sibling keys aligned |
|---|---|---|---|---|---|
| de | 545 | 1 (*Details* → *Angaben*) | 74 + 0 + 6 | 50 | 6 |
| es | 545 | 0 | 43 + 0 + 1 | 50 | 1 |
| es-MX | 545 | 34 | 32 + 0 + 5 | 50 | 5 |
| fr-FR | 545 | 1 | 129 + 3 + 8 | 50 | 8 |
| hi | 545 | 34 | 65 + 0 + 1 | 50 | 1 |
| id-ID | 545 | 33 | 64 + 3 + 1 | 50 | 1 |
| it-IT | 545 | 1 (*Audit* → *Storico*) | 80 + 5 | 50 | — |
| ja-JP | 545 | 34 | 96 + 5 | 50 | — |
| ko-KR | 545 | 34 | 77 + 3 | 50 | — |
| pt-BR | 545 | 0 | 69 + 4 | 50 | — |

(The three figures in *Older values changed* are the three pushes, `2.486.1`, `2.488.2`, `2.489.2`;
the second and third include `rating.model.*` — *Plat*, *Piatto*, *フラット*, *Plano* for a flat
rate — and it *SÌ* → *Sì*, pt *Toda conta* → *Toda fatura*, which the plan screens now render.)

**New keys (50 × 11):** `rating.planSections.usageKind.*` (10), `.sizedBy.*` (3), `.usageRow.*`
(9), `.when.*` (4), `.taxed.both`; `rating.planDetail.audit.field.*` (22 — each copied from the
catalogue's own word for the same field where one exists) and `.more`.

**Left as they are, on purpose.**
- 61 `rating.plan.*` keys (the old builder's penalty, surcharge, taxes, discounts and deposits
  copy) and the 19 `rating.planUnits.*` / `rating.planSummary.*` keys have no reader left in `src/` after
  `PlanWizard` was retired; they were translated (so G15's plan lines reach zero) rather than
  retired, because retiring is a separate act with its own grep, and the `rating.plans.*`
  refusal keys are read by the SERVER's message keys, which a front-end grep cannot see.
- *Status* (de, id), *Code* (de, fr), *Name* (de), *Version*/*Service*/*Structure*/*Type* (fr),
  *Unit* (id) are the language's own word and are on G15's per-language allow list.
- The probes the walk prints on these photographs and are not catalogue text: the audit *Reason*
  *Minimum bill rises with the new year* (a clerk's words); *After* in step 3 is a charge-code NAME
  inside the select's option list; fr *Taxes*, *Description*, *Services* are French.
- Japanese *ペナルティ* wraps to two lines in step 3's narrow *Type* column; it is two lines, not one
  character a line, and no column was resized for it.

**Checks.**
- G15 (through its `run()`): plan untranslated **169 → 0**; plan baseline lines **273 → 0**
  (retired in the same diff); fresh **803 → 802**, none a plan key (the other 802 were red at
  `0ec7004cd` before this lane). Key parity 0 missing, 0 extra.
- G33: 10 fresh, none a plan key (red at `0ec7004cd`, English copy of other modules).
- Placeholders identical to English in every value written (`check.py`), every `_one` with its
  `_other`.
- Red first: `tests/test_def_rat_9502_plan_words_have_codes.py` — 5 failed at `ed076e6c7`
  (`KeyError: 'label_key'`, no `words_facts`, no `_taxed_codes`), and the sixth case at `8530f7406`
  (`assert ('text' == 'none'`); 6 passed. `serverWords.test.ts` — 4 failed at `ed076e6c7`
  (`usageKindWord is not a function`; *expected 'Status: draft → Budget billing: Yes …' to be
  'Status: Entwurf → Abschlagszahlung: Ja …'*); 4 passed.
- vitest `planSections`, `planForm`, `planDetail`, plans list, `planUntouchedSave`, `src/i18n`
  (catalogue parity, `usEnglishCatalogue`, retired words): **206 passed** at `2.488.2`, **194** of
  the narrower set at `2.489.2`; `tsc` clean. PostgreSQL 16: `test_cr167_plans_round2`,
  `test_cr167_plan_versions_pg` and the new file **30 passed**.

**Photographs.** `08-qa/plans-2026-10-03/i18n/<screen>-<lang>.png`, **187 at 1440** (17 screens ×
11 languages) on a private PostgreSQL 16 database (`sbh_planlang`: `migrate` + `seed_demo` +
`load_sample_data --tenant brazosbend`; `SCW-RES` given a published v2 from 01/01/2027 at $12.00),
signed in as Dana, build `2.489.2`, by `10-scripts/cr167_plans_i18n_walk.mjs`: `list`,
`new-1-details` … `new-5-review`, `new-6-saved`, `detail-1-overview`, `detail-2-more`,
`detail-3-services` (expanded), `detail-4-charges`, `detail-5-billing`, `detail-6-units`,
`detail-7-audit`, `detail-8-retire-dialog`, `edit-1-choose`, `edit-2-change-review`. The walk
prints, per photograph, its characters (blank fails), the page's sideways overflow (**0 px on all
187**), text boxes wrapping one character a line (**none**), the list's table width in its box
(**1,120 px in 1,120 px**, every language) and every English probe word found. Each photograph
was looked at through one contact sheet per screen (eleven languages side by side, made in the
lane's scratch space and not committed, so the folder holds the 187 originals only).

**After the photographs (`2.489.3`, with this record):** the Plans & Rates tab bar above the list
read ja *チャージコード* and ko *청구 코드* (10 uses each) where every plan screen reads *料金コード* /
*요금 코드* (62 and 61); id *Daftar tarif* and it *Listini tariffari* where the screens read *Jadwal
tarif* / *Tariffari*. Four values in `rating.tab.chargeCodes` / `rating.tab.rates`; the
photographs show the tab bar as it was.

**Version:** `2.486.1` (copy, `e9c7c695c`), `2.488.2` (server words, `5f5945dfd`), `2.489.2` (form
steps, audit view, sibling keys, `9e62c5bf6`), `2.489.3` (tab words, this record, the photographs).
**Rollback:** redeploy `2.486.0` for the copy, `2.488.1` / `2.489.1` for the two fixes — catalogue
text, additive response fields and screen helpers; no migration and no data.

## 18 · Round 4 task 10 — the full web walk, and what it fixed (`2.490.1`–`2.490.5`, lane PLAN-WALK)

The nine phases of `05-prototype/plans-2026-10-03/web-walk.md`, clicked at 1440 as Dana on a fresh
PostgreSQL 16 database (`sbh_planwalk`: `migrate` + `seed_demo` + `10-scripts/cr167_planwalk_world.py
setup`), the built front end (`vite build --mode wolocal` + `server.mjs`), every "must be true" checked
on the screen, through the API and in the database. **The API ran as a NOSUPERUSER NOBYPASSRLS role**:
on the first probe a superuser connection showed Utility B's charge codes in Utility A's form options —
RLS is bypassed by a superuser, so only an app role walks what production runs. Scripts
`10-scripts/cr167_planwalk.mjs` and `cr167_planwalk_world.py`; report, final count and the 44-image
side-by-side in `08-qa/plans-2026-10-03/walk-report.md`; 98 photographs in
`08-qa/plans-2026-10-03/walk/`, each opened, none blank.

**Result: 195 checks, 195 pass** after the fixes below (each red run is listed in the report). Utility A
= Brazos Bend with water, sewer, trash and fire on and the product's sample data, eight classes, and
three walk codes (`DEPOSIT` by class $150.00 / $300.00, `DEP-SIZE` by size $150.00 / $600.00, `LATE-CL`
by class 1.5 % min $5.00 / 2 % min $10.00); Utility B = Riverbend Water. Plans made through the screen:
**Residential** (water, sewer, trash; 25 % outside-city on water and sewer; deposit by size), **Commercial**
(class-priced late fee and deposit), **Fire** (six line sizes, per line per month; saved as a draft from
New, then published) and **Municipal** (saved half way with *Save draft & exit*, reopened, finished) — one
`rate_plans` row each throughout.

| Phase | Must be true | Result |
|---|---|---|
| 1 | each list row shows version, from, to; one DB row per plan; only A's services | **PASS** 19/19 |
| 2 | each problem named; nothing lost; *All added.* | **PASS** 11/11 |
| 3 | Review shows every value exactly, with version + from-date | **PASS** 11/11 (the seed's taxes and LATE carry no start date — pill only) |
| 4 | tabs match Review; links; folding; Expand all; tiles; section Edit; tab in address; arrow keys | **PASS** 26/26 (+ Units: 3 units, search, Vacant, CSV) |
| 5 | water v2 from 01/01/2027: banner; Priced as of 01/15/2027 new ($4.40 · $7.15 · $8.80), today old | **PASS** 4/4 after `DEF-RAT-9515` |
| 6 | three ways, Audit before → after; Publish a saved v2 | **PASS** 10/10 after `DEF-RAT-9516` |
| 7 | ONE plan version for billing on 12/31/2026 and on 01/01/2027 | **PASS** 3/3 (PW-RES v1 $10.00 → v2 $12.00; PW-COM $25.00 → $30.00; PW-FIRE v1) |
| 8 | December old figures, January new; deposit and base never counted twice | **PASS** 9/9 — Ruth **$94.35 → $98.38** (water tier 1 $20.00 → $22.00, tier 2 $19.50 → $21.45), Carl outside ×1.25 **$117.94 → $122.97**; one base line per service; no deposit line, `deposit_assessed` $150.00 once |
| 9 | Utility B sees none of A's plans (screen, API, RLS); no English in ten languages | **PASS** 97/97 after `DEF-RAT-9518` |
| — | Duplicate (2.489.0); Publish a saved v2; deposits by class AND by size (2.487.0); the base the schedule names (`DEF-RAT-9335`) | **PASS** — the copy is one draft from the version the plan starts with; v2 published from the banner; both deposit kinds on the form, Review, tabs and accounts; no bill refused across three issued runs |

**Defects — each filed first, a test shown RED first, fixed, walked again:**

| Defect | What | Red first | Fix | Build |
|---|---|---|---|---|
| `DEF-RAT-9510` (brief) | `POST /plans/{id}/versions/{n}/publish` on a DRAFT plan's v1 | `IntegrityError: CHECK constraint failed: ck_plan_versions_window` (it tried to publish v1) | 🔒 `plan_writes.publish_version` refuses a plan not published, `rating.plans.version_of_draft` | 2.490.1 `efb80b41d` |
| `DEF-RAT-9514` | a draft edited only on a priced step never saved — the PATCH carried no `details`, the server read it as the OLD 8-step body, `422 rating.unknown_field (taxes)` | `expected undefined to deeply equal {}` | `planEditModel.patchPayload` always sends `details` (the contract's marker) | 2.490.2 `d17337843` |
| `DEF-RAT-9515` | a plan starting 11/01/2026 never named its water schedule's v2 (the banner showed `upcoming[0]` only) | `expected … to have a length of 2 but got 1` | one banner line per upcoming item; replaces §13 judgment 3 | 2.490.3 `de77848ff` |
| `DEF-RAT-9516` | a plan not yet started read as its NEWEST version: today's tabs showed v2's $12.00, *Fix a mistake* corrected v2 as *v2 · today*, Audit named an edit *v2*, Duplicate copied $12.00 | `assert 2 == 1`, `assert [2] == [1]` | 🔒 `plan_reads._read_day` (a day no window covers reads the first version after it) for the sections, list, Audit and Duplicate; billing's `version_on` untouched | 2.490.4 `fbdd6d8ba` |
| `DEF-RAT-9517` | a corrected upcoming schedule version vanished from the plan (originals only) | `assert None == {'version': 2, …}` | 🔒 `plan_reads.schedule_ref` reads corrections too | 2.490.5 `10d41e1ae` |
| `DEF-RAT-9518` | English in other languages: the folded line and banner (*per kgal*), the outside-city line (*Water, Sewerに*) | `… not to contain 'per'`, `… to contain '水'` | `usageRowRate` / `serviceWord` | 2.490.5 `10d41e1ae` |
| `DEF-RAT-9519` | a Residential plan lists TX State tax (commercial/industrial only) and *8.25 % combined*; its bills charge 2.00 % | — | **filed, open (low)**, §19 | — |

The three 🔒 files ship HUMAN-REVIEW-PENDING with review-ledger rows (2026-10-03, `DEF-RAT-9510`,
`9516`, `9517`). PostgreSQL 16: the plan suites **40 passed** (`test_cr167_plan_versions_pg`, round2,
fixes, 9510, 9516); SQLite 58 + 42; front end planDetail, planForm, planSections, planUntouchedSave
**132 passed**; `tsc`, eslint clean.

**Two things the walk had to do that are said, not hidden:** the world script's own water v2 first
omitted the schedule's size rows, so January refused Ruth's and Carl's 5/8" bills (R3, rightly) — it was
corrected through the product's correction act and their January was billed on a second cycle, because
BR-BIL-005 refuses a second run over one cycle and period; and the plans begin 11/01/2026 (after the
utility's today), which is what exposed `DEF-RAT-9515` and `9516` — every earlier walk used a plan
already in force.

## 19 · The close (`2.490.5`)

> **Re-walked on 2.494.0 → 2.495.2 (2026-10-04, lane PLAN-REWALK): 210/210** — the first walk's 195 checks again, plus 15 for what landed since (2.490.6 tax mark, 2.491.0/2.492.1 discounts, 2.492.0 deposit size pick); one bug fixed on the way, `DEF-CUS-9524` (2.495.2). `08-qa/plans-2026-10-03/walk-report.md` § *Re-walk*.

### What was delivered against the PO's fifteen rulings

| # | The PO said | Delivered | Walked |
|---|---|---|---|
| 1 | five one-word steps; Edit the same form with three choices | Details · Services · Charges · Billing · Review; Name and details · Change from a date · Fix a mistake | phases 1, 6; images 04–23, 38–44 |
| 2 | lose no detail; tabs Overview · Services · Charges · Billing · Units · Audit | §5 field map, every input homed; six tabs | phases 3, 4 |
| 3 | table arrays for selections | services, codes, taxes, deposits, discounts, notes | phase 2 |
| 4 | classes one tick dropdown, *Every customer class* first | built | image 06 |
| 5 | intended-for ticks and notes kept, reminders only | built | images 07, 24 |
| 6 | full-size row controls, red ×, *+ Add*, *All added.*, empty row refused by name | built | phase 2 |
| 7 | base and minimum shown with the schedule on step 2 | built, monthly base total under the table | image 08 |
| 8 | version + from-date on every reference | built (a seed item with no start date shows the pill alone) | phase 3 |
| 9 | Review in tables incl. deposits by class or size | built; deposits by size added by the PO's later answer (2.487.0) | phases 3, 8 |
| 10 | Review ends *Save as draft* · *Publish plan* (*Save/Publish new version* on edit) | built | images 21, 23, 41 |
| 11 | details tabs = Review's sections, one component | `PlanSections` | phase 4 |
| 12 | *Base charges* / *Usage charges* everywhere | built | photos |
| 13 | links, folding, Expand all, banner, Priced as of, tiles, section Edit, sticky header, tab in address, Units search/filter/CSV, Audit filters and before → after, arrow keys | built; the banner now one line per upcoming item (`DEF-RAT-9515`) | phases 4, 5, 6 |
| 14 | remove *Try a bill* | removed | — |
| 15 | *Move units to another plan* — not now | not built (no selection column, no Move) | image 31 |

Plus the PO's four later answers: the base the schedule names (`DEF-RAT-9335`, 2.487.0 — no bill refused
in the walk's three issued runs), deposits by class or size (`OQ-RAT-12786`, 2.487.0), and *"complete
these and fix bugs"* (§16, 2.489.0–2.489.5: Duplicate, Publish a saved version, audit words, occupancy).

### Checks re-run for the close

| | Before (tip `a2b38bfc9`, this lane's start) | After (`10d41e1ae`, 2.490.5) |
|---|---|---|
| Golden `06-backend/tests/golden` (`pytest -m golden`) | **25 passed, 1 xfailed** | **25 passed, 1 xfailed** |
| `10-scripts/03-golden-verify.py` (document self-consistency; runs no engine code) | **33 PASS, 0 FAIL** | **33 PASS, 0 FAIL** |

No ❄️ figure moved; no signed rule changed; nothing went to the PO.

### Still open — each in one sentence, with who has it

1. **`DEF-RAT-9519`** (low) — a plan can carry a tax that applies to none of its classes and count it in
   *combined*: ours to decide (law 13) whether the form refuses such a tax or marks it *not charged to
   this plan's classes* and leaves it out of the combined rate; **recommended: mark it and leave it out of
   *combined*** (refusing would block a plan that later adds a class). Rating lane.
2. *Move units to another plan* — ruled NOT NOW (ruling 15).
3. The deposit amount on New account reads *currency not available* until `DEF-CUS-5114` (known, by the
   brief).
4. The 🔒 files of this CR (`plan_writes.py`, `plan_reads.py`, `plan_versioning.py`, `services.py`,
   `selectors.py`, `resolution.py`, the deposit seams) wait for a recorded human review — review-ledger
   rows of 2026-10-03.

**Version.** The last product build of this CR is **2.490.5** (`10d41e1ae`); the close ships records
only and takes no version.

**Rollback.** Each fix's own: redeploy **2.490.4** (9517, 9518), **2.490.3** (9516), **2.490.2** (9515),
**2.490.1** (9514), **2.489.5** (9510) — no migration and no data in any of them; a correction a clerk
saved against the newer version before 2.490.4 stays as saved. The whole redesign's rollback is §8 and
each round's own section (§9: redeploy 2.482.1 after `manage.py migrate rating 0061_…`).

**`CR-167-BRC10` is CLOSED** at **2.490.5**, with `DEF-RAT-9519` open (low) and *Move units to another
plan* ruled not now.

## 20 · After close — the walk's open finding, and one seen but not filed (`2.490.6`, lane PLAN-TAIL, 2026-10-04)

> **Re-walked on 2.494.0 → 2.495.2: 210/210.** `DEF-RAT-9519` holds on Review, Charges and Overview (*Not charged to this plan's classes*, *2.00% combined*, the API's `reaches_plan_classes` none/all).

PO: *"complete these and fix bugs"*. Two items, each filed first and proved red first.

**1 · `DEF-RAT-9519` — FIXED.** A Residential plan carrying TX State Utility Tax (6.25 %, commercial and
industrial only) and Bexar County (2.00 %) read *8.25 % combined* everywhere, while its bills charge 2.00 %.
Our judgment (decision log *"A TAX THE PLAN'S CLASSES DO NOT PAY"*): the tax is **listed, marked
*Not charged to this plan's classes*, never refused**, and left out of *combined*; where the plan's classes
pay **different** taxes there is **no** combined figure (the base total's *differs by customer class*
answer). The server serves `reaches_plan_classes` (`all` / `some` / `none`) on each tax of the plan read and
of `form-options` (from the ticked classes), using the bill's own class test; the form's *combined*, the
Review, the Charges tab and the Overview tile all follow it.
- Red at `106a74ec4`: `assert '8.25%' == '2.00%'` (Residential), `assert '8.25%' is None` (every-class and
  Residential + Commercial); front end `expected '8.25%' to be '2.00%'` and *Unable to find an element with
  the text: Not charged to this plan's classes*. Green: the new 6 server cases with the plan suites (53),
  rating/api/i18n front-end suites 1,087 (one red not ours: `adminOnlyReads.test.ts` names
  `NewConnectPremiseStep.tsx`, red since `ad3bec69d`, 2.463.0), `tsc`.
- **PostgreSQL 16, real issued bills** (`10-scripts/cr167_plantail_taxes_pg.py`, output
  `08-qa/plans-2026-10-03/tail/pg-proof.txt`): Residential plan *2.00 % combined* — Ruth's and Carl's
  November bills taxable $94.87, Bexar $1.90 = 2.00 %; Commercial plan *8.25 % combined* — the café's bill
  taxable $101.60, State $6.35 + Bexar $2.03 = 8.25 %.
- Photographs at 1440 (`08-qa/plans-2026-10-03/tail/`, `10-scripts/cr167_plantail_photos.mjs`, 9/9 checks):
  `res-1-overview`, `res-2-charges-tab`, `com-1-overview`, `com-2-charges-tab`, `new-3-charges-taxes`,
  `new-5-review`, `new-5-review-taxes`.
- Not weighed into *combined*: a tax's premises scope (inside city limits) and its service list.

**2 · `DEF-BIL-9520` — NOT A DEFECT.** Carl's January 2027 bill prints water tier 2 at *$8.9375* per kgal
($7.15 + the 25 % outside-city surcharge) beside the amount *$26.81*. The PO ruled on 2026-10-02: *"Show unit
prices with up to 4 decimals and keep every total at 2."* A unit price at four places is that ruling; the
amount is at two. Filed and closed `invalid` with the citation. CLAUDE.md hard rule 2 still read *"both
DISPLAY 2"* without the narrowing — that is why it looked like a breach — and now names it.

**Golden** unchanged: engine 25 passed + 1 xfailed; `03-golden-verify.py` 33 PASS.

**Version 2.490.6. Rollback:** redeploy 2.490.5; no data is written.

## 21 · A PO answer built — a size-priced deposit where no meter is fitted: the clerk picks the size (`2.492.0`, lane DEP-PICK, 2026-10-04)

**PO verbatim** (decision log *"THREE PO ANSWERS"*, item 3): *"(c) Let the clerk pick the size on the Deposit
step."* It answers §15.3's *Left for the PO*: a new connection with no meter has no size, so a plan whose
deposit is priced by size refused its Deposit step (*"No deposit priced for this size."*). Filed first as
**`DEF-CUS-9521`** (the old refusal is now wrong for that case), red tests next, then built.

**What was built**

| Where | Before | After |
|---|---|---|
| 🔒 `rating.selectors.plan_deposit_for` (+ `_deposit_from_rules`, `_deposit_size_choices`) | no recorded size → refusal `size_not_recorded` | the refusal carries `sizes` — each size the code prices for this class, with the TOTAL the commit would take; a `size_class` (the clerk's pick) prices the code when no size is recorded and the answer says `size_picked` |
| 🔒 `rating.selectors.deposit_rule_for` · 🔒 `rating.seams.account_deposit_size_class` | billing asks by account → `size_not_recorded` → first bill refused | billing asks by account → the account's kept pick prices the deposit |
| 🔒 `customers 0078` | — | `accounts.deposit_size_class` · `deposit_size_picked_at` · `deposit_size_picked_by` (nullable, additive) |
| `customers/deposit.py` | 422 `customers.deposit.sizeNotPriced` | `GET /accounts/deposit-standard` answers `pick_size` + `sizes` (and `size_class=` prices one); the commit takes the picked size's figure, keeps the pick on the account and writes `audit_log` `deposit.size_picked` (who, `size_class`, *Water 2"*, $600.0000, reason `no_meter_fitted`); a request with no pick is refused `customers.deposit.sizeRequired` |
| `depositCapability.tsx` (New account step 4, Move-in step 6) | the refusal sentence, nothing to take | **Meter size** select, by name, smallest first (`sizeOrder`), help *No meter fitted. Pick the size.*; the amount follows the pick; Review shows *Meter size* |

**Judgments of ours (decision log row *"DEF-CUS-9521 BUILT"*):** (1) a RECORDED meter size always wins over a
pick — a stale 2" pick at $600.00 against a unit that now has a 5/8" meter is refused as not the plan's figure
(`amountNotPlan`), never silently re-priced; (2) only sizes that would actually price are offered, each with
the figure the commit takes; (3) the pick is kept on the account, not only in `audit_log` (pruned, `OQ-1340`),
because the first bill must read it back; (4) a waive or a first-bill deferral on a picked size keeps the pick
too, because each assessed a figure from it; (5) a recorded size the code does not price (3/4") is still
*"No deposit priced for this size."* — the ruling covers only *no size recorded*.

**Red first** — at `afab7d192`: server 10 failed (`KeyError: 'sizes'`, `deposit_rule_for() got an unexpected
keyword argument 'size_class'`, `'Account' object has no attribute 'deposit_size_class'`, `VAL-002
(customers.account.unknown_field)`, `VAL-003 (customers.deposit.sizeNotPriced)`) and vitest 3 failed
(`expected null to be truthy` for `#deposit_size_class`). After: 12/12 server
(`tests/test_def_cus_9521_deposit_size_pick*.py`), 63 with the deposit, size-deposit and first-bill suites;
vitest 38/38 in `depositCapability.test.tsx`, customers folder 2,246 passed, 1 red not ours (below).

**Proved on PostgreSQL 16 at 1440** (`sbh_deppick`, `10-scripts/dep_pick_walk_prep.py` → `dep_pick_walk.mjs`
→ `dep_pick_first_bill_pg.py`; photographs in `08-qa/plans-2026-10-03/deposit-pick/`, each opened):

| Step | What happened | Photo |
|---|---|---|
| New account › Deposit, `SCW-U-355` (no meter) | *Meter size* offered: *Water 5/8"*, *Water 2"*; Amount empty, Continue held | `01-no-meter-pick-a-size.png` |
| pick 2" | Amount **600.00** | `02-no-meter-2in-picked-600.png` |
| taken today, cash | | `03-no-meter-2in-taken-today.png` |
| Review | *Meter size* Water 2" | `04-review-2in-600.png` |
| *Create & activate* | `POST accounts → 201` **AC-2026-00054**; payment `PY-261004-0084` $600.00 cleared; `deposit_assessed` 600.0000, `deposit_on_file` 600.00, `deposit_size_class` W-2 + who/when; journal `JE-100426-0205` **DR 1010 $600.00 / CR 2300 $600.00**; `audit_log` `deposit.size_picked` `{size: Water 2", amount 600.0000, reason no_meter_fitted}` by Dana | `05-created-2in-600.png` |
| New account › Deposit, `SCW-U-207` (5/8" meter) | Amount **150.00**, no *Meter size* | `06-meter-58-150-no-picker.png` |
| Move-in › Deposit (step 6), a vacant unit with no meter | the same picker; 2" → **600.00** | `07-…`, `08-move-in-2in-picked-600.png` |
| First bill (`first_bill.deposit_line_for`) | **AC-2026-00055** (no meter, 2" picked, deferred): one deposit line **$600.00**; AC-2026-00054 (taken at the counter): no line, $600.00 already paid | `pg-proof.txt` |

**Found on the walk, filed, not fixed here:** `DEF-CUS-9524` (low) — *Amount taken* reads `600.0000` once
*Taken today* is ticked (it defaults to the stored four-place string; it is the same for a fitted meter).

**Red not ours, dated:** `wizardRailCensus.test.ts` (DEF-CUS-5071 census) names the tax edit flow's
`EDIT_*_STEPS` — red since `b71588e74` (CR-165, 2026-10-03), untouched here.

**Version 2.492.0. Rollback:** redeploy 2.491.0 and reverse `customers 0078`; accounts opened on a picked size
lose the pick and their first bill is refused by name rather than billed without the deposit.
