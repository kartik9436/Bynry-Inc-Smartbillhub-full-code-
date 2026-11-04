# CR-166-BRC10 — Plans & Rates › Discounts redesigned end to end: list, New discount form, details (with an Accounts tab) and edit, built from 36 desktop images, plus the four lifecycle rulings

**Raised:** 2026-10-03, by the Product Owner, in chat, over the review of the mock-up (artifact
`JmwhY7nnzCWXjSkyGwHiLY`, approved at v5, kept as v6), ending in a GO. The rulings are the four
decision-log rows of 2026-10-03 headed *"DISCOUNTS REDESIGN, UNDERSTANDING STAGE …"* (two),
*"DISCOUNTS REDESIGN — THE DRAWING IS APPROVED …"* and *"GO ON THE DISCOUNTS REDESIGN — ALL FOUR
LIFECYCLE ANSWERS AS RECOMMENDED …"* (commit `aeea9050e`); nothing they settle is put back to the
PO (hard-won law 13).
**The drawing:** `05-prototype/discounts-2026-10-03/` (commit `b2b6f1002`) — `README.md` (the eight
ruled points and the index of 36 images), `images/01…36`, `discounts-mockup.html` (an index, never
the specification — B14 rule 42), `web-walk.md` (task 9).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed by `CR-156-BRC10` in
`12-governance/14-id-reservations.md`). `10-scripts/allocate.py cr` answered **166** against the
remote and `--verify 166` reported it free on every branch, at allocation and again at push time.
**Classification:** **MAINTENANCE** (`12-governance/22-product-maintenance-process.md`) — a user can
create, view and edit a discount today, so a live screen redrawn end to end is maintenance,
borrowing only the drawing step from Build; REPRODUCE comes before any fix (§4). Screen problems are
defects (§5). The parts the product never did — an Accounts tab, per-utility lists, automatic
enrollment, a dated Retire, approval as the last act — are change and are carried here.
**Touches 🔒 rating** (discount pricing, enrollment, versions, migrations): HUMAN-REVIEW-PENDING
regime; golden tests must not move.

Shape copied from `CR-165-BRC10` (taxes & fees, the same round the day before).

---

## 0 · What arrived, in the requester's words

Quoted from the decision-log rows of 2026-10-03, in the PO's order:

> *"now we look at discounts and redesign it; dont start any changes yet - list view - text to be
> reduced … there are 5 steps we need to reduce them to 3 … dont loose any information on screen …
> Currency - utility currenyc to be choosen - as default … can you tell me how you will range this
> in 3 steps"* · *"1 word steps"* · *"Im okay with this"* (the 31-box map) · *"this si correct"*
> (Details · Eligibility · Review) · *"okay with this"* (the list page) · *"when you create HTML
> artifact use this as sample - https://claude.ai/artifact/Gv7YJoQbydd1aj42te9cRk"* · *"Program
> owner - make this drop down - give it values"* · *"Currency - it is default of utility - user
> cannot change it"* · *"Exclusivity group - can you make this drop down"* · *"Who qualifies * -
> drop down"* · *"al changes in drawinga re good now - what all task you will do; i want images to be
> used to create prodict screens ; dont use text to create product screens, and how you will do end
> end web walk - similar to tax"* · *"can youa dd tab and show the list of accounts who are getting
> this discount?"* · **GO:** *"all as recommended - all good - you understood it correctly"*.

The four lifecycle rulings, in the GO row's own words:
1. **An approved discount goes live by itself on its start date** — approval is the last act; the
   separate Activate goes.
2. **Only accounts whose plan carries the discount can get it, and taking it off a plan stops it
   from the next bill.**
3. **"Automatic" enrolls every account on a plan carrying it that meets a condition the system can
   check** (Everyone on the plan · Autopay is on · Paperless billing is on · Government or municipal
   account). A "customer shows proof" condition cannot be Automatic.
4. **Retire asks for an end date, and after it nobody gets the discount, accounts already enrolled
   included** — the same as Retire on taxes.

## 1 · Classified

**MAINTENANCE, with change carried.** Screen problems are defects (`DEF-RAT-9289`–`9292`). The four
lifecycle facts are filed as defects too (`DEF-RAT-9293`–`9296`) because each is the product doing
something other than what is now ruled; what each needs built (a job, a dated retire, list tables)
is change and is carried in §6. Fast path does **not** apply: it touches rating (🔒), money (who is
discounted, from when) and stored rows (versions, enrollments, list values).

## 2 · What signed statements it touches

* **`BR-RAT-069`** (CONFIRMED 2026-08-19): *"AVAILABLE ≠ GRANTED. A plan attachment discounts
  NOBODY. … The plan says which discounts CAN apply; the ACCOUNT'S ENROLMENT says which DO, and the
  bill run reads enrolments."* → **NARROWED by ruling 3 for Automatic discounts only.** The two
  tables stay and the bill still reads enrollments; what changes is that for an Automatic discount
  the product WRITES the enrollment for every account on a carrying plan that meets a system-checked
  condition. A plan attachment still discounts nobody by itself; an Apply-and-approve discount is
  unchanged. Ruling 2 makes the plan a REQUIRED gate at enrollment too (today it is a gate only on the
  bill path, §4 (b)).
* **`BR-RAT-110`** (closes `OQ-300`, built 2026-08-21): *"A PLAN BINDS DISCOUNTS FROM THE CATALOGUE;
  ENROLMENT STILL DECIDES WHO ACTUALLY GETS ONE. BOTH GATES, NOT ONE REPLACING THE OTHER."* and
  *"⚠ UNBINDING IS NOT RULED — see `OQ-322`"*. → **STANDS, and ruling 2 completes it:** both gates
  now apply at enrollment as well as at billing, and unbinding is ruled — *"taking it off a plan
  stops it from the next bill"*. **`OQ-322` (OPEN, *"MAY A PLAN UNBIND A DISCOUNT WHILE ACCOUNTS ARE
  STILL ENROLLED ON IT"*) is answered by ruling 2 and must be closed as a fan-out** (register row,
  its body, `BR-RAT-110`, `services._refuse_unruled_discount_unbind`'s stub) in the commit that builds
  it — not here, because this round changes no code and the stub must not be removed before its
  replacement exists.
* **`BR-RAT-077`** (CONFIRMED, amended 2026-08-21) — the second approval: *"MEASURED AGAINST THE
  DISCOUNT'S OWN BUDGET CAP — AND NO BUDGET ALWAYS REQUIRES IT."* → **STANDS.** Ruling 1 makes
  approval the last act; where a second approval is required, the LAST required approval is that act.
* **`BR-RAT-109`** (PO 2026-08-21): *"ACTIVATING A NEVER-SUBMITTED DISCOUNT IS ALLOWED, WARNED, AND
  RECORDED — NOT REFUSED."* → **SUPERSEDED by ruling 1.** With Activate gone there is no door through
  which a never-submitted draft goes live; the drawing's Draft offers *Edit · Submit for approval*
  only (image 24). The warn-and-allow recording (`activated_without_submission`) has nothing left to
  record. Stamp the rule in the building commit.
* **`BR-RAT-078`** (CONFIRMED 2026-08-19): *"ENROLMENTS SURVIVE VERSIONING, AND DELETION IS REFUSED
  ONCE BILLED OR EVER ENROLLED. Part 3's shared rules: 'enrolments survive versioning; retiring
  blocks new enrolment and lists affected accounts before confirming …'"* → the versioning and
  deletion halves **STAND**; the retire half is **SUPERSEDED by ruling 4** (retire ends the discount
  for everyone on a date, not merely new enrollments). Note §4 (d): today's code already stops
  existing enrollments — immediately and backwards in time — so the signed sentence was never what
  the bill did.
* **`BR-RAT-068`** (CONFIRMED): *"A DISCOUNT IS AN OVERLAY, NEVER A RATE … the bill shows the full
  tariff amount and the reduction as its own line."* → **STANDS.** Only the word *overlay* leaves the
  screen (D2, D14, D20); the rule is unchanged.
* **`BR-RAT-075`** (caps trim, a budget trims, an exhausted budget raises — ⚖️ **"suspend" SUPERSEDED 2026-10-04**: an exhausted budget gives $0.00 and the bill goes out, PO *"we cannot stop the billing"*; see §17) and **`BR-RAT-076`**
  (verification, proof and recertification are the discount's own; automatic + mandatory proof
  refused) → **STAND.** Ruling 3's *"a 'customer shows proof' condition cannot be Automatic"* is
  `BR-RAT-076`'s refused combination restated in the new vocabulary.
* **`BR-RAT-1016`** (PO 2026-09-17): *"THE THREE VERBS ARE THE SAME FOR EVERY PRICED OBJECT: EDIT
  while it has priced nothing · CORRECT over the SAME window when the figure recorded was wrong ·
  CHANGE over a NEW window when prices move."* → **STANDS; the drawing obeys it.** Image 27–36's
  three Edit choices (*Name and details · New value from a date · Fix a mistake*) are these verbs.
* **`BR-RAT-1011`** (late fee from the plan's charge code) — named in the brief; it **does not touch
  discounts** and nothing here moves it. Recorded so a reader does not go looking.
* **`BR-BIL-020`** (CONFIRMED-AS-AMENDED 2026-10-01): *"lines come ONLY from rules and charge codes —
  free-typed amounts never exist on any bill … a one-time Fee bill with a charge code priced entered
  when used (CR-010 A2 — TAP, IMPACT, DAMAGE, BULK-WATER) takes the clerk's typed amount"*. →
  **STANDS.** A discount line is a rule-derived line; the drawing adds no typed amount to any bill.
* **No ❄️ B4/B5 figure moves.** The pricing arithmetic (`discount_pricing.py`) is untouched by the
  drawing; what changes is WHO is enrolled and WHICH version is in force on a date.

## 3 · The ten tasks, as put to the PO

1 images · 2 record + reproduce every problem on today's screen and file it · 3 back end (the three
per-utility lists editable in Settings, currency fixed to the utility, the four lifecycle rulings,
the accounts read, plans with accounts, audit, versions, new value from a date, fix a mistake) ·
4 New form · 5 list · 6 details incl. the Accounts tab · 7 edit as the same form · 8 eleven
languages · 9 full web walk and fix · 10 close. **Four rounds**, run by the coordinator; **round 1**
is tasks 1 (the 36 images, commit `b2b6f1002`) and 2 (this file), plus the read-only fact-finding for
task 3 (§6). Each later round appends its record here.

## 4 · Problems on today's screen (task 2 — REPRODUCED before anything is fixed)

**How:** build **`2.469.0`** (branch tip `b2b6f1002`; front end built `vite build --mode wolocal`; API
`runserver` on a private PostgreSQL 16 database `sbh_discr1`, `migrate` + `seed_demo` +
`load_sample_data --tenant brazosbend`; signed in as Dana, System Admin), Chromium at 1440 wide.
Script `10-scripts/cr166_discounts_before_walk.mjs`; its full printed output is
`08-qa/discounts-2026-10-03/before/walk-output.txt`; **25 screenshots** in
`08-qa/discounts-2026-10-03/before/`, each opened and checked not blank. The tip moved to `8494f0ef8`
while this was written; what moved is taxes & fees work and none of it changes a discount line
(§6 head). Sample data: six discounts (AUTOPAY, CAP, MILITARY draft, MUNICIPAL, PAPERLESS,
SENIOR), three of them on *Sample — Residential* (75 units, 68 accounts), one enrollment
(MUNICIPAL, the government building).

D-numbers follow the mock-up's `FIX` arrays in order: `wiz` → D1–D13 (form), `list` → D14–D18,
`detail` → D19–D34, `edit` → D35–D38. *"Today"* is the drawing's wording.

| D | Area | Today (drawing's words) | Result | Evidence and what was seen |
|---|---|---|---|---|
| D1 | Form | Five steps | **REPRODUCED** | `w01` — *Basics & type · Value · Eligibility & verification · Effective & approval · Review*, *STEP 1 OF 5* |
| D2 | Form | Title "Define an overlay." | **REPRODUCED** | `w01` — *NEW DISCOUNT / Define an overlay.* |
| D3 | Form | "Type the amount exactly as it should be stored…" under four boxes | **REPRODUCED** | `w02` under Cap per bill, Cap per year, Lifetime cap; `w08` also under Amount off — four |
| D4 | Form | Currency typed as three letters | **REPRODUCED** | `w08`/`w09` — a fixed amount shows a free text *Currency — Three letters, the bill's currency.*; **CAD** typed on a USD utility is accepted (no max length, no list) |
| D5 | Form | Caps and stacking spread over a long page | **REPRODUCED** | `w02` — CAPS block (4 boxes) and a stacking block (3 controls), always open |
| D6 | Form | "Blank means uncapped. Zero grants nothing." | **REPRODUCED** | `w02` — under CAPS |
| D7 | Form | "Available, not granted. Saving enrolls nobody." | **REPRODUCED** | `w05` — under the step-4 heading *Dates & approval* |
| D8 | Form | "Uppercased on save. Example: SENIOR." | **REPRODUCED** | `w01` — under Code |
| D9 | Form | Review lists a few fields, no example | **REPRODUCED** | `w06` — 8 fields (Stacking precedence printed empty), no Edit link per row, no $60.00 bill; Submit for approval and Activate drawn greyed |
| D10 | Form | Long explanations under headings | **REPRODUCED** | `w02`/`w05` — *"What the reduction is taken from. It never changes the rate itself."*, *"Only Suspend changes the status automatically."*; `w06` *"Nothing here reduces a bill yet. This saves a draft."* |
| D11 | Form | Who qualifies typed as free text | **REPRODUCED** | `w04` — `#discount-eligibility-summary` is a `textarea` |
| D12 | Form | Exclusivity group typed as free text | **REPRODUCED** | `w02` — `#discount-exclusivity` is a text input |
| D13 | Form | Program owner typed as free text | **REPRODUCED** | `w01` — `#discount-owner` is a text input |
| D14 | List | Overlay paragraph above the table | **REPRODUCED** | `l01` — *"A discount is an overlay: it reduces what a customer pays …"* |
| D15 | List | Value 25.00 and 1.00 with no $ | **REPRODUCED** | `l01` — CAP *25.00*, PAPERLESS *1.00* |
| D16 | List | Pencil on every row | **REPRODUCED** | `l01` — every row's only action is a pencil labelled *New version* |
| D17 | List | No dates | **REPRODUCED** | `l01` — columns Code · Discount · Type · Value · Eligibility · Verification · Plans · Enrolled · Status · Actions |
| D18 | List | Filters | **NOT A SCREEN PROBLEM** | the drawing KEEPS them (*"Kept: our standard toolbar"*); `l01` shows Search · All · + Filter · Columns |
| D19 | Details | Kicker "DISCOUNT · AUTOPAY · PERCENTAGE · V1" | **REPRODUCED** | `d01` — exactly that |
| D20 | Details | Overlay paragraph under the title | **REPRODUCED** | `d01` — *"Effective from: 08/01/2026 · A discount is an overlay, not a cloned rate …"* |
| D21 | Details | Dates as 01-Aug-26 | **NOT REPRODUCED** | `d01` header and `d03` Audit both read **08/01/2026** |
| D22 | Details | Four buttons; Duplicate greyed out | **REPRODUCED** | Active `d01`: *Fix this version · Duplicate [disabled] · Edit · Retire [disabled]*; Draft `d06`: five — *Submit for approval · Activate · Duplicate [disabled] · Edit · Retire [disabled]* |
| D23 | Details | Tiles repeat on every tab | **REPRODUCED** | `d02`, `d03` — the four tiles above Plans and Audit |
| D24 | Details | Type tile wraps on three lines | **REPRODUCED** | `d01` — *Percentage · / Subtotal before / taxes* |
| D25 | Details | "75 · 75 units on a plan carrying it" | **REPRODUCED** | `d01` — OFFERED TO *75* / *75 units on a plan carrying it* |
| D26 | Details | "Nothing works out a month's subsidy…" | **REPRODUCED** | `d01` — under WHO QUALIFIES |
| D27 | Details | Money without $ | **REPRODUCED** | `d01` Budget cap *2383.00*, Granted *0.00*; `d04` CAP value *25.00*, budget *11400.00* |
| D28 | Details | Red kickers over grey labels | **REPRODUCED** | `d01` — red *WHAT IT IS*, *WHAT IT IS WORTH*, *WHO QUALIFIES* |
| D29 | Details | Plans tab empty | **REPRODUCED** | `d02` — *"The tile above counts the plans that carry this definition. Naming them one by one needs a read that does not exist yet."* |
| D30 | Details | No way to see who gets it | **REPRODUCED** | `d05` — MUNICIPAL *Enrolled 1*, the account named nowhere; tabs are Overview · Plans · Audit |
| D31 | Details | Audit shows versions only; stray "Discard draft" heading | **REPRODUCED** (versions only) | `d03` — one table *Version · Effective · Value · Why it changed*; *DISCARD DRAFT* is read in the table head by `walk-output.txt` but is not visible in the photo (an off-screen column heading) |
| D32 | Details | "DATED" note box | **REPRODUCED** | `d03` — *DATED / Bills always use the version in force on the usage date.* |
| D33 | Details | 12 entered values never shown | **REPRODUCED** | `d01`/`d07` — never shown: assistance filing, currency, stacks with others, exclusivity group, recertification notice, grace, *if recertification lapses*, proof before first reduction, budget period, budget runs out, reason for change (11; the code only in the kicker) |
| D34 | Details | Effective to under Who qualifies | **REPRODUCED** | `d01` — *EFFECTIVE TO* is the last item of WHO QUALIFIES; *Effective from* only in the header sentence |
| D35 | Edit | "Fix this version" and "Edit" as two buttons | **REPRODUCED** | `d01`; Edit → `/edit` (`e01`), Fix → `/edit?correct=1` (`e05`) |
| D36 | Edit | Value editable on a live discount | **REPRODUCED** | `e02` — Edit opens a full new-version form, `#discount-value` enabled, 0.50 → 0.75 typed; there is no *name and details only* choice |
| D37 | Edit | New value: old version's end typed by hand | **NOT REPRODUCED** (as drawn) | `e03` — nothing is typed for the OLD version: the server ends it the day before the new start, but only when the new version is Activated (`discount_services._close_open_windows_before`, DEF-RAT-8050). What IS wrong: the start box is pre-filled with the OLD start 08/01/2026 and no screen says the old version will end (`e04`) — that is D38's review, and image 33's line |
| D38 | Edit | Fix with no before and after | **REPRODUCED** (in part) | `e08` — Review shows *Value 0.05* and *In force now 0.50%* (a value before/after) but no bill example and no other field compared; and the Fix door is headed *"Draft a new version of AUTOPAY."* with a *Save new version* button — the correction is labelled as the other verb |

**Count: 35 reproduced (D31 versions-only, D38 in part) · 2 not reproduced (D21, D37) · 1 not a
screen problem (D18).** The two not reproduced are already the drawn behaviour (dates) or are done by
the server rather than typed (the old version's end); the build still follows the drawing for them,
but no defect claims them.

### The four lifecycle facts (ruled 2026-10-03), reproduced on PostgreSQL 16

**How:** `10-scripts/cr166_discount_lifecycle_facts.py`, run against `sbh_discr1` (PostgreSQL
16.0013, tenant today 10/03/2026) through the product's own services, inside one transaction rolled
back at the end. "Discounted" is asked of BOTH reads: `discount_rules_for_account` (the R6 door the
enrollment counts and `price_account_discounts` use) and `selectors.billable_discount_rules` (what
`billing/gather.py::_discounts_for` hands the bill run, BR-RAT-110's plan gate applied).

| Fact (decision row's words) | Result | What the code answered |
|---|---|---|
| **(a)** an approved discount does not go live on its start date without Activate | **REPRODUCED** | FACTA, start 09/23/2026 (10 days past), submitted and approved → version `scheduled`, discount `draft`; `active_version(today)` = **None**; enrolling an account is REFUSED `rating.discounts.no_active_version`. Only after Activate: version `active`, v1 in force. Nothing in the code reads `scheduled` except Activate. |
| **(b)** an account whose plan does not carry the discount can still be enrolled and discounted, and removing a discount from a plan stops nobody | **REPRODUCED (enrolled), PARTLY (discounted), DIFFERENTLY (removal)** | *Sample — Residential* carries AUTOPAY, MUNICIPAL, PAPERLESS, not SENIOR. `enrol_account(SENIOR, A-10432)` → **ACCEPTED**; SENIOR's Enrolled count → **1**; `price_account_discounts` takes **$9.00 off a $60.00 bill**; but the bill run's read returns **[]** — so the screen says enrolled and the bill is full price. Removal: with A-10432 enrolled in AUTOPAY, saving the plan without AUTOPAY is **REFUSED** — `NotImplementedError: OQ-322: unbinding a discount with live enrolments is unruled` — the plan keeps AUTOPAY and the enrollment stays open. So removal does not "stop nobody"; it cannot be done at all while anyone is enrolled (and unbinding a discount nobody is enrolled in deletes the row). |
| **(c)** an Automatic discount enrolls nobody | **REPRODUCED** | AUTOPAY and PAPERLESS are `automatic`, offered to 75 units, **0** enrolled; 6 of the plan's 68 accounts have autopay on, 1 paperless. A new Automatic discount created, approved, activated and attached to the plan: **0 of 68** enrolled. Screen: `d01` *Enrolled 0* beside *Offered to 75*. |
| **(d)** after Retire, already-enrolled accounts keep the discount | **NOT REPRODUCED — the opposite, and worse** | Before: MUNICIPAL priced for AC-2026-00049 on 09/15/2026 by both reads. `retire_discount(MUNICIPAL)` takes **no date**; afterwards **both reads return nothing for 08/15, 09/15 and 12/15/2026** — the discount stops at once for the enrolled account and **backwards in time**, so a re-bill or late bill of August loses a 20% reduction it was owed. The enrollment stays open (`ended_on` null) and Enrolled still reads **1**. New enrollments are refused. Retire has no HTTP route (`d01`: Retire greyed). |

### Found while reproducing, outside the 38

* **`DEF-RAT-9297` — the only HTTP route that enrolls an account answers 500.** `POST
  /accounts/{id}/discounts` (`customers/api.py:1761`) passes the whole request body to
  `claim_assistance(actor, account_id, programme_id)`, so `{"programme_id": "<SENIOR id>"}` reaches
  `_discount_or_404` as a dict: *"… is not a valid UUID"* (`walk-output.txt`, last line). The
  drawing's *+ Enroll an account* (image 20) needs a working door. (Filed with module `customers`
  under the `RAT` id, because the defect is about discount enrollment.)
* **Already open, not re-filed:** `DEF-478` (enrollment, plan attachment, verify and retire have no
  route), `DEF-2430` and `DEF-BIL-5341` (no `discount_grants` row is written at issue, so caps per
  year, lifetime caps and budgets never deplete from real bills, and *Granted to date* is always
  `0.00`). All three are open and all three block parts of tasks 3 and 6 (§6 e).

## 5 · Defects filed (before anything is fixed)

| Defect | Area | Problems |
|---|---|---|
| `DEF-RAT-9289` | New discount form | D1–D13 |
| `DEF-RAT-9290` | List | D14–D17 |
| `DEF-RAT-9291` | Details | D19–D34 (except D21) |
| `DEF-RAT-9292` | Edit | D35, D36, D38 |
| `DEF-RAT-9293` | Lifecycle (a) — approved is not live without Activate | ruling 1 |
| `DEF-RAT-9294` | Lifecycle (b) — off-plan enrollment; unbind refused | ruling 2 |
| `DEF-RAT-9295` | Lifecycle (c) — Automatic enrolls nobody | ruling 3 |
| `DEF-RAT-9296` | Lifecycle (d) — Retire has no date and is retroactive | ruling 4 |
| `DEF-RAT-9297` | Enrollment HTTP door returns 500 | outside the 38 |

## 6 · Back end: what exists and what is missing (task 3 fact-finding, read only)

Line numbers at branch tip `8494f0ef8`. Between the walk's build (`b2b6f1002`) and this tip,
`rating/selectors.py`, `services.py`, `api.py` and `models.py` moved for taxes (`CR-165` rounds 2–3,
migrations `0056`–`0058`); their diff changes no line about discounts and no discount screen file
changed, so the reproduction stands.

| | Question | What exists (file:line) | What is missing |
|---|---|---|---|
| a | Program owner, funding source, exclusivity group, who qualifies | All **free text**. `Discount.programme_owner` / `funding_source` (`apps/rating/discounts.py:339–340`, written by `create_discount` `discount_services.py:678–679`, edited in place by `update_discount` `:846`). `DiscountVersion.exclusivity_group` (`discounts.py:474`) — a passthrough (`discount_services.py:349`) compared by string equality in `discount_pricing._resolve_exclusivity` (`discount_pricing.py:420`). Who qualifies = `eligibility_summary` free text (`discounts.py:487`) plus `eligibility_rule` JSON that nothing evaluates (`:484`). Seeded values: owners *Billing*, *Customer service*, *City assistance programme*; funding *Rate-payer funded*, *City programme*; exclusivity *assistance* (CAP, SENIOR) or blank. | **Per-utility editable lists** fit the existing Settings › Reference data framework: `tenancy/services.py:4179` `LOOKUP_LISTS` + `register_lookup_handler` (`:4266`), the handler contract rating already implements twice (`apps/rating/lookups.py:381–389`; BR-TEN-036 shape code · name · is_system · active, seeded defaults, tenant-extensible). Needs: three lists (owner, exclusivity, who-qualifies), each row a code + label; **who-qualifies also needs a `kind` (system checks / customer shows proof) and, for the four system kinds, a fixed check key** so ruling 3 can evaluate it; a migration (🔒 migration ordering, RLS FORCE on new tables) that seeds the drawn values and maps existing free text (open item 2, 3). Funding source stays free text (not drawn as a dropdown). |
| b | The tenant's currency | `tenancy.Tenant.currency` (`apps/tenancy/models.py:210`, *"BR-TEN-021 forward-only"*). Five modules publish a `tenant_currency()` seam (`customers/seams.py:295`, `assets/seams.py:399`, `metering/seams.py:1064`, `ledger/tenancy_seam.py:346`, `payments/settings_seam.py:499`); **rating has none**. A discount version stores its own `currency` (`discounts.py:416`, default `USD`), accepted as typed (`discount_services.py:347`, passthrough — the walk saved CAD on a USD utility). Pricing refuses a mismatch at bill time (`DiscountCurrencyMismatch`, `discount_pricing.py:180`). | A `tenant_currency()` seam in `apps/rating/seams.py`; the server SETS `currency` from it on every version write and refuses any other value by name; the form shows it read-only. Existing rows are all `USD` on a USD tenant (no back-fill risk on the demo; a migration should report, not rewrite, any mismatch elsewhere). |
| c | Version number | **Stored**: `discount_versions.version_no` (`discounts.py:410`), unique per discount (`uq_discount_versions_discount_no`). A new version takes `max + 1` (`discount_services.py:758–778`); a correction ALSO takes `max + 1` and links `corrects` / `superseded_by` (`:1051–1060`, `discounts.py:585–606`); one draft at a time (`uq_discount_versions_one_draft`). Served on the detail as `version_no`. | Nothing to add for a number. Note for task 7 / image 36: a *Fix a mistake* row is a new version number today (v1 → v2 corrected), so the drawing's "same version, old row kept" has to read the correction link, not the number. |
| d | Plans with accounts | **Counts only**: `selectors.discount_plan_count` (`selectors.py:6055`) and `discount_offered_unit_count` (`:6073`, UNITS on a carrying plan — its docstring says why not accounts). The Plans tab says the read does not exist (`d02`). The other direction exists: `selectors.plan_discount_rules(plan)` (`:1576`). | `GET /discounts/{id}/plans` → `{plan, available_from, available_to, units, accounts}`, paged (NFR-3). Accounts per plan need the customers seam (`discount_enrolments.account_id` is a deferred FK and rating may not join accounts — `services.py:1427–1432`). + *Add to a plan* needs a route for `attach_discount_to_plan` (`discount_services.py:1496`; `DEF-478`). |
| e | The Accounts tab (account, customer and address, plan, enrolled, renew by, this month's amount, status; end with a date and reason; + Enroll) | `discount_enrolments_read.discount_enrolments` (`discount_enrolments_read.py:42`) serves the R27 report: ALL discounts, SQL `LIMIT` but no offset, no filter by discount, no customer, address, plan or amount. `enrolment_row` (`discount_services.py:2178`). Renew-by = `recertification_due_on` (`discounts.py:805`). Status inputs: `verification_status` (`:791`) — `verified`/`not_required` → *Receiving*, `pending` → *Proof pending*; *Renewal due* = renew-by within `recertification_notice_days`. End: `end_enrolment(actor, id, reason, ended_on)` (`discount_services.py:1674`) already takes a date and a reason. | `GET /discounts/{id}/enrollments` paged and sorted in SQL, with search and status filter and CSV; customer, account number and address through the customers seam (address by walking to the premises — hard rule 8); plan from `unit_plan_assignments` (rating's own). **This month's amount cannot be read today:** no `discount_grants` row is written at issue (`record_grant` has no caller — `DEF-2430`, `DEF-BIL-5341`, open) and an invoice line carries only the discount's label (`selectors.py:5880–5892`). Either close `DEF-2430` first or compute the expected reduction for this month from the R6 door (open item 5). Routes for enroll / end / verify (`DEF-478`) and the broken customers door (`DEF-RAT-9297`). |
| f | A per-discount audit | Versions only: `discount_version_chain` (`discount_services.py:1273`) served as `GET /discounts/{id}/versions` (`api.py:1160`). Every write already lands in `audit_log` (actions `discount.*` on entity types `discount`, `discount_version`, `discount_enrolment`, `plan_discount_rule`), filterable by ONE entity id through the general audit read (`apps/audit/selectors.py:69–90`). | `GET /discounts/{id}/audit` → `{at, actor, action, before, after, reason}` across the discount, all its versions, its plan bindings and (summarised) its enrollments, newest first, paged. `audit_log` is pruned on retention (hard rule 4, PO 2026-09-23), so the version rows remain the permanent part; the screen claims no permanence. |
| g | Activation today, and ruling 1 | draft → `submit_discount_version` (`:1183`, → `pending_approval`) → `approve_discount_version` (`:1306`, → `scheduled`; self-approval allowed and recorded) → `activate_discount_version` (`:1348`, → `active`; closes predecessor windows `:1861`; flips the discount `draft → active`). `active_version` (`:1812`) reads `status = active` only. The no-overlap constraint `ex_discount_versions_no_overlap` (rating/0049) covers `status = 'active'` only. | Ruling 1: approval (the last required one, BR-RAT-077) becomes the act that puts a version in force from its start date. Either approval writes `active` with the future start (the window does the scheduling — `active_version` already filters `effective_from <= day`) and closes the predecessor's window at that moment, or `active_version` also reads `scheduled`; the first keeps one status meaning "priced" and needs no job. Either way the **exclusion constraint must cover every version that can price** (🔒 migration). `activate_discount_version` and its route retire; BR-RAT-109 is superseded (§2). A future-dated approved version must show as *Scheduled* on the list without being a separate stored state. |
| h | Enrollment and ruling 2 | `enrol_account` (`:1541`) checks only *retired* and *has an active version*; it never reads `plan_discount_rules`. `discount_rules_for_account` (`:1933`) has no plan gate; `selectors.billable_discount_rules` (`selectors.py:9762`) has it (`:9801–9817`, binding window applied). Unbind: `services._refuse_unruled_discount_unbind` (`services.py:1408`) raises `NotImplementedError("OQ-322")` when any open enrollment exists tenant-wide; otherwise `_apply_plan_children` DELETES the binding rows (`services.py:1521–1532`). | Refuse an off-plan enrollment by name (account → unit through a customers seam, unit → plan from `unit_plan_assignments`). Put the plan gate in ONE resolver every reader uses, so the Enrolled count, the Accounts tab and the bill agree. Replace the OQ-322 stub with the ruled behaviour: removing a discount from a plan sets the binding's `available_to` to the day before (instead of deleting it), which the bill path's existing window check already honours — *"stops it from the next bill"*. Ending the affected enrollments on the same date is our judgment (open item 4). Close `OQ-322` (fan-out, §2). |
| i | Automatic and ruling 3 | `ENROLMENT_AUTOMATIC` (`discounts.py:216`) is stored and read only by validation (GATE 1, `discount_services.py:459`, which already refuses automatic + mandatory proof). Nothing writes an enrollment for it. Conditions the system can check exist as data: `Account.autopay` (`customers/models.py:620`), `Account.paperless` (`:695`), account type code `municipal` (+ legacy `government`, `customers/models.py:241–252`), and plan membership (`unit_plan_assignments`). | An idempotent enrollment job (uniqueness already held by `uq_discount_enrolments_current`) that enrolls every account on a carrying plan meeting the discount's system condition, and ends the enrollment when the account leaves the plan or the condition stops holding; run on approval, on plan attach, and when an account's plan, autopay, paperless or type changes (plus a nightly sweep). Through the customers seam, never the customers ORM (B1). The who-qualifies list (a) must mark which values are system checks; the form must refuse Automatic with a proof value. |
| j | Retire and ruling 4 | `retire_discount(actor, id)` (`:1442`) takes no date and sets `Discount.status = retired`; `discount_rules_for_account` skips by CURRENT status (`:1957–1961`), so pricing stops at once and for past service dates too (§4 (d)); enrollments stay open. No route (`DEF-478`). | `retire(end_date, reason)`: set the in-force version's `effective_to = end_date` (the window, which every pricing read already honours by date), end every open enrollment on that date, refuse a date before today (issued bills are immutable; a re-bill of an earlier period must still see the discount), and decide status by date (*Retired* once the date has passed, *Retiring 12/31/2026* before). Pricing must never read the current status to decide a past date. |
| k | How billing picks a version for a date, and can it return more than one | `billable_discount_rules` → `discount_rules_for_account` → `active_version(discount, service_date)` (`discount_services.py:1812`): `status = active`, `effective_from <= day`, `effective_to` null or `>= day`; **two rows refuse** with `rating.discounts.two_versions_in_force` (BR-RAT-1016) rather than pick; on PostgreSQL `ex_discount_versions_no_overlap` (deferrable) makes two overlapping ACTIVE windows impossible. **It cannot return more than one.** | The guarantee holds only for `status = active`. Once ruling 1 lets an approved version price, the constraint and `active_version` must cover it in the same commit, or two versions can be in force on one date again (`DEF-RAT-8050`'s shape). |
| l | 🔒 files the rulings touch | `apps/rating/discount_services.py` (lifecycle, enrollment, retire — `human_owned.txt:185`), `apps/rating/selectors.py` (reads, the bill-path gate — `:16`), `apps/rating/services.py` (unbind — `:265`), `apps/customers/discounts.py` + `customers/api.py` (the enrollment door — `:213`), a rating migration after `0058` (constraint, list tables, binding dates — 🔒 migration ordering, RLS FORCE on new tables). `apps/rating/discount_pricing.py` (`:184`) — the arithmetic — is **not** expected to change. | Each change ships HUMAN-REVIEW-PENDING with a ledger row; golden tests must not move; every rule above proved on PostgreSQL (hard-won law 14), not only on the default suite. |

## 7 · Open items (none asked by this lane; each written so it can be put in one sentence)

1. **For the PO — the existing exclusivity group splits in two and that changes bills.** Today CAP
   and SENIOR share the free-text group *assistance*, so a customer on both gets one of them. The
   drawn list has no *assistance*: CAP belongs in *Low-income programs* and SENIOR in *Age-based*,
   which puts them in different groups, and then they STACK. *Question:* "When we move today's
   discounts onto the new lists, should a senior on the low-income credit keep getting only one of
   the two, or both?" *Worked example:* a senior on CAP with a $60.00 bill gets $25.00 off today; in
   two groups they would get $25.00 plus the 15% senior discount (up to $9.00 more, depending on
   stacking order). Keeping one-of-the-two means putting both in *Low-income programs*.
2. **Our judgment (task 3) — free-text owners not in the drawn list.** CAP's owner reads *City
   assistance programme*; the list has *City or county agency*. Because the lists are editable per
   utility, the migration ADDS any existing value that matches none of the drawn ones to that
   utility's own list rather than rewriting it, so no recorded fact changes. Same for funding source,
   which stays free text.
3. **Our judgment (task 3) — today's who-qualifies text.** *Autopay enrolled* → *Autopay is on*,
   *E-bill on* → *Paperless billing is on*, *Government account* → *Government or municipal
   account*, *Age 65+* → *Age 65 or over*, *Veteran ID* → *Veteran or active military*, *Program
   enrolment* → *In a state assistance program*; anything else is added to the utility's list as a
   *customer shows proof* value. Recorded in the decision log when task 3 builds it.
4. **Our judgment (task 3) — taking a discount off a plan.** The binding gets an end date (the day
   before) instead of being deleted, and every open enrollment on that discount for accounts on that
   plan is ended on the same date with the reason *"Removed from plan <name>"*. *Example:* SENIOR
   taken off Residential Standard on 10/15/2026 → an October bill with service to 10/14 keeps the
   15%; the November bill has none. Billing already decides by service date (BR-RAT-007).
5. **Our judgment (task 6) — "this month's amount" on the Accounts tab.** Until `DEF-2430` writes a
   grant at issue, the tab shows the reduction the R6 door computes for the account's current
   month's bill (labelled as expected), not a recorded figure. If `DEF-2430` lands first, it shows
   the recorded grant instead.
6. **Our judgment (task 3) — Retire dates.** The end date may not be before today; a Retire with a
   future date shows *Retiring 12/31/2026* until then. *Example:* retire SENIOR on 12/31/2026 → the
   December bill keeps $9.00 off a $60.00 bill, January's has none, enrolled accounts included.
7. **Our judgment (task 3) — Automatic keeps itself current.** An account that joins a carrying
   plan, or turns autopay on, is enrolled from the next bill; one that leaves, or turns it off, is
   ended from the next bill. *Example:* 6 of the 68 accounts on *Sample — Residential* have autopay
   on today, so AUTOPAY enrolls 6 (0.5%: $0.30 off a $60.00 bill each). Note:
   `customers/models.py:620` still comments `autopay` as *"CAPTURE-ONLY in v1"*; task 3 must confirm
   whether the tick drives collection today before the discount reads it, and file the comment if it
   is stale.

## 8 · Version and rollback

Round 1 ships **no product code** — this file, two scripts, 25 screenshots and nine defect rows — so
it carries no version. **Rollback for round 1:** none needed (records only). Each later round states
its version (`allocate.py version --bump change`) and its rollback before shipping: redeploy the
previous build; any migration added by task 3 must name its down path and what happens to rows
written under it (list values, enrollments the automatic job wrote, binding end dates, version
windows closed by a dated Retire).

## 9 · Round 2 API contract

Copied verbatim from the round-2 coordinator brief on 2026-10-03, before any round-2 code was written. Task 3 (back end) implements it; tasks 4 and 5 (front end) code against it. **Field names are fixed: none is ever renamed.** A field added by any lane is appended to this section (*Fields added*, below) with the lane and the reason, in the same commit as the code that serves it.

### THE API CONTRACT (task 3 implements; tasks 4 and 5 consume — names fixed; task 3 copies this into CR-166 §9 as its FIRST push)
- Per-utility lists, editable in Settings (the existing Settings › Reference data mechanism): `GET /discounts/form-options` → `{ program_owners:[{value,label}], exclusivity_groups:[{value,label}], eligibility:[{value,label,checked_by:"system"|"proof"}], enrollment_modes:[{value,label}], verification:[{value,label}], lapse:[{value,label}], budget_periods:[{value,label}], budget_out:[{value,label}], types:[{value,label}], applies_to:[{value,label}] }`. Seeded values are the README's (program owner 8, exclusivity group 6 incl. "None", who qualifies 11 in two groups). The form NEVER hard-codes them.
- `currency`: the utility's own (`Tenant.currency`), returned read-only; a write carrying a different currency is refused by name.
- Discount read (list rows and `GET /discounts/{id}`) adds: `version` (int), `status` (`draft|waiting_approval|scheduled|active|ended|retired`), `program_owner`, `exclusivity_group`, `eligibility` (each `{value,label}`; eligibility also `checked_by`), `value_display` with `$` or `%`, `effective_from`, `effective_to`, `offered_to` (units on its plans), `receiving` (accounts), `granted_this_month` (null until DEF-2430 is fixed — never 0 pretending), `scheduled_next` (`{value_display, effective_from}`|null).
- Write takes `program_owner`, `exclusivity_group`, `eligibility` codes. `POST /discounts` saves a draft.
- Lifecycle (PO rulings 2026-10-03): `POST /discounts/{id}/submit` · `POST /discounts/{id}/approve` (LAST act — the version goes live BY ITSELF on its start date; no Activate) · `POST /discounts/{id}/send-back {note}`.
- Edit: `PATCH /discounts/{id}` name and details only on a live discount (value, limits, start refused by name) · `POST /discounts/{id}/new-value {value fields…, effective_from}` (old version ends the day before) · `POST /discounts/{id}/corrections {…, reason}` (same window; old kept, superseded).
- `POST /discounts/{id}/retire {effective_to}` — after that date NOBODY gets it, enrolled accounts included; nothing changes before it.
- `GET /discounts/{id}/plans` → rows with `accounts` and `units`. `GET /discounts/{id}/accounts` → paged in SQL: `{account_id, account_number, customer_name, premises_address, plan, enrolled_on, renew_by, this_month|null, status: receiving|proof_pending|renewal_due}` + filters `f.status`, `f.plan`, search. `POST /discount-enrolments/{id}/end {ended_on, reason}`.
- `GET /discounts/{id}/audit` → every change across the discount, its versions, plan links and enrollments: `{at, actor, action, before, after, reason}`, newest first, paged, NAMES not ids.
- Enrollment: only accounts whose plan carries the discount (on the enrollment date) can be enrolled; removing a discount from a plan ends its enrollments from the next bill (replaces the `OQ-322` refusal). Automatic: every account on a plan carrying it that meets a `checked_by: system` condition is enrolled (and un-enrolled when it stops meeting it) by a job; a `proof` condition cannot be Automatic.
- List `GET /discounts` adds the fields above and server-side filters `f.status`, `f.type`.

### Fields added

Added by task 3 (back end), 2026-10-03, in the commit that serves them. Nothing in the contract above was renamed.

| Where | Field | Why |
|---|---|---|
| `GET /discounts/form-options` | `currency` | The contract says the utility's currency is *returned read-only* without saying where; the form reads it here. |
| `GET /discounts/{id}/accounts` rows | `enrolment_id` | `POST /discount-enrolments/{id}/end` needs it; an identifier the screen acts on and never shows (B14 rule 31). |
| `GET /discounts/{id}/plans` rows | `plan_id`, `plan`, `plan_code`, `available_from`, `available_to` | The contract said only *rows with `accounts` and `units`*; these name the plan and when it offers the discount. |
| list rows and `GET /discounts/{id}` | `stored_status` | `status` is now the DERIVED six-value status; the stored discount status stays readable beside it. |
| `GET /discounts/form-options` `eligibility[]` and the Settings card | `checked_by` on each value | Already in the contract for `eligibility`; noted because the Settings list serves it too. |
| `GET /discounts/{id}/versions` rows | `effective_to` | Added by task 6 (round 3): image 19's versions table reads *08/01/2026 – 12/31/2026*. |
| `GET /discounts/{id}/plans` rows | `services` (codes), `customer_classes` (names; `[]` = every class) | Added by task 6: image 21's *Services* and *Customer classes* columns. |
| `GET /discounts/{id}` | `money_display` `{cap_per_bill, cap_per_year, cap_lifetime, bill_floor_amount, budget_cap, budget_remaining}` | Added by task 6: money WITH the utility's symbol (`$4.00`, D27). The bare `*_display` keys are unchanged for the screens that read them. |
| `GET /discounts/{id}/audit` rows | a plan link's `plan` (name) in place of `rate_plan` (id) | Fixed by task 6 (`DEF-RAT-9309`): image 22's *Added to plan · Residential Standard*; no id is served. |

**Two answers to the New form's asks (§11):** a *customer shows proof* condition no longer needs `accepted_proof_kinds` from the form — the server derives it from `eligibility` (decision log *"A PROOF CONDITION'S ACCEPTED DOCUMENTS ARE DERIVED"*); and **no `funding_sources` list was added** — funding source stays free text, so the form's text box is right.

⚠ **Two existing row keys changed SHAPE by the contract**, which old screens must not read as strings: `eligibility` and `exclusivity_group` are `{value, label}` objects now, and `status` is derived. The current `DiscountsTab`/`definitionDetail` screens read the old shapes until tasks 4–6 replace them.

## 10 · Round 2 · back end (task 3)

**Version 2.478.0.** Built against §9; every PO lifecycle ruling of 2026-10-03 is in the code, each mechanism recorded as a judgment in the decision log (rows *"THE FOUR DISCOUNT LIFECYCLE RULINGS, BUILT"*, *"DISCOUNT EDITS AND LISTS"*, *"`DEF-2430` / `DEF-BIL-5341` STAY OPEN"*).

| What | Where | Proof |
|---|---|---|
| **Ruling 1** — approval is the last act; live from its start date; Activate gone (answers `activate_retired`) | `approve_discount_version`, `_put_in_force`; `rating/0061` lock over `active`+`scheduled`; `rating/0060` put left-over `scheduled` versions in force | sqlite: past start prices with no Activate; future start reads *Scheduled*. PG: two approved versions on one date refused by the lock (both statuses); approval refuses an overlap by name |
| **Ruling 2** — plan gate; removal stops it from the next bill; **`OQ-322` CLOSED** | `discount_ids_carried` (one resolver: enrolment, R6 door, bill); `services._close_dropped_discounts`; PlanWizard step 6 hold released | SENIOR on no plan refused (`plan_does_not_carry`); off Residential Standard on 10/15 → binding and enrolment end 10/14; −$9.00 on 10/14, $0.00 on 10/15 (sqlite and PG) |
| **Ruling 3** — Automatic enrolment by a system check | `discount_enrolment_job.py` (on approval, plan save, detail change, nightly 02:40) | AUTOPAY enrols exactly the autopay account; re-run writes nothing; autopay off → ended the day before the sweep |
| **Ruling 4** — dated retire | `retire_discount`, `discounts.retire_on`; pricing decides by date | 12/31/2026: December −$9.00 off $60.00, January $0.00; a past date refused (sqlite and PG) |
| **One version per discount per date** | `billable_discount_rules` → `discount_rules_for_account` → `active_version` | **PostgreSQL 16, every day 12/25/2026–01/05/2027: exactly 1 SENIOR row; 15% → −$9.00 through 12/31, 12% → −$7.20 from 01/01** |
| Per-utility lists (8 · 6 · 11), Settings › Reference data | `discount_lists.py`, three handlers, `rating/0059`/`0060`; three cards | `GET /discounts/form-options`; `assistance` → ONE shared group *Assistance programs* (PO 2026-10-03, *"A Keep them excluding each other"*) — a senior on CAP gets $25.00 off $60.00, never $34.00 |
| Currency fixed to the utility | `seams.tenant_currency`; `_validate_version` | CAD on a USD utility refused `currency_not_utility`; stored `USD` |
| `DEF-RAT-9297` — the enrolment door | `customers/api.account_claim_assistance` reads `programme_id` | RED first with Django's *"… is not a valid UUID"*; now 200 with the enrolment; missing id → 422 on `programme_id` |
| §9 reads | `discount_reads.py`: status, form options, plans, accounts (SQL-paged, `f.status`, `f.plan`, search), audit (names not ids) | sqlite cases |
| §9 writes | `submit`, `approve`, `send-back`, `new-value`, `corrections`, `retire`, `PATCH` (name and details; locked fields refused by name), `discount-enrolments/<built-in function id>/end` | sqlite cases |

**Question C (DEF-2430 / DEF-BIL-5341): NOT fixed — both stay OPEN.** Recording a grant at issue needs the discount's identity on rating's priced line, billing's rated line and a new `invoice_lines` column, plus a rating write from issue — not contained in the bill-issue path. `granted_this_month` and each account's `this_month` are therefore served **`null`**, and §7 item 5's *expected* figure is withdrawn. **Web-walk step 9 should expect blanks in both places.**

**F (autopay):** still capture-only — `BR-CUS-059` and `BR-PAY-015` (CONFIRMED): enrollment and method are stored and shown, issue records an intent, no money is collected by the product. The comment at `customers/models.py:620` is **accurate, not stale**. The Autopay condition therefore means *the customer has elected autopay and is not under the NSF cash-only sanction* — the pair `payments.autopay.is_enrolled` reads — not *autopay collected the bill*.

**Defects:** closed `DEF-RAT-9293`, `9294`, `9295`, `9296`, `9297`. Filed `DEF-RAT-9303` (a discount needing a second approval goes live on one approval — `BR-RAT-077`'s second act was never built; threshold OFF by default). Left open: `DEF-478` (attach-to-plan still has no route of its own — the plan wizard's step 6 is the door), `DEF-2430`, `DEF-BIL-5341`.

**Golden tests:** `tests/golden` **25 passed + 1 xfailed before and after** (unchanged). `discount_pricing.py` (the arithmetic) is untouched.

**Rollback:** redeploy 2.477.1 after `manage.py migrate rating 0058_cr165_tax_chain_constraints_and_rls`. `0061` down: drops RLS on `discount_list_values` and re-creates the lock over `active` only. `0060` down: no-op — the codes stay in the free-text columns as readable words and versions put in force stay in force. `0059` down: drops `discount_list_values` (values a utility added or renamed are LOST), `eligibility_code` (the label stays in `eligibility_summary`) and `retire_on` (a retirement already written onto version windows and enrolments STAYS; reopen by hand if meant). Enrolments the automatic job wrote stay — they are ordinary enrolments with an audit row; end them on the Accounts tab if wanted.

## 11 · Round 2 task 4 — the New discount form (built 2026-10-03, `2.475.0`)

**What was built.** The New door (`plans-rates/discounts/new`) opens a three-step form — **Details ·
Eligibility · Review** — with a *This discount* panel on the right and a saved state, built from
images 05–18 of `05-prototype/discounts-2026-10-03/images/` (B14 rules 42, 44, 37, 43, 21, 33). It
is components in `07-frontend/src/features/rating/discountForm/`: each step (and each SECTION of
step 1 and 2 — Basics, Value, Limits, Who qualifies, Dates and budget) is a component taking a
`locked` set, and the steps are an array (`NEW_DISCOUNT_STEPS`), so round 3's *Name and details*,
*New value from a date* and *Fix a mistake* mount the same pieces. The kit's `CheckDropdown` and
`AffixField` (built for taxes) are reused; `CheckDropdown` gained an opt-in `mode="pick"` (no "all"
row — an empty list is an unfinished form here, `CR-091-BRC01`) and `SelectField` an opt-in
`groups` (the two *Who qualifies* groups) under B14 rule 36. `DiscountWizard.tsx` still serves the
EDIT door (`…/:definitionId/edit`) and is imported by four test files; round 3 retires it.
`DiscountsTab.tsx` and the details files are untouched.

Every list is `GET /discounts/form-options` (CR-166 §9) — nothing is typed out in the front end.
A route that is not served is an empty dropdown and the form keeps working. Platform codes (type,
applies to, enrollment, verification, lapse, budget period, budget runs out) read in the
catalogue's words keyed on the value; program owner, exclusivity group and who qualifies are each
utility's own lists and show the utility's labels. Copy: 130 keys in all eleven catalogues
(`10-scripts/i18n_fanin.py`).

### D1–D13 (`DEF-RAT-9289`)

| D | Today (drawing's words) | Now | Fixed in |
|---|---|---|---|
| D1 | Five steps | Three steps, one word each: Details · Eligibility · Review | `2.475.0` |
| D2 | Title "Define an overlay." | Title *New discount*, back link *← Discounts* | `2.475.0` |
| D3 | "Type the amount exactly as it should be stored…" under four boxes | Each money box carries `$` in the box; one short help line where the drawing has one | `2.475.0` |
| D4 | Currency typed as three letters | The utility's currency shown read-only (*USD · US dollar*, from the shell's own read); the body carries that code or no currency key at all — never a typed one | `2.475.0` (server-side refusal by name: task 3) |
| D5 | Caps and stacking spread over a long page | One *Limits* section, closed by default, reading *No limits* or *N set*; a marked box opens it | `2.475.0` |
| D6 | "Blank means uncapped. Zero grants nothing." | *Empty means no cap.* under each cap | `2.475.0` |
| D7 | "Available, not granted. Saving enrolls nobody." | Gone (B14 rule 33 — rationale is zero words) | `2.475.0` |
| D8 | "Uppercased on save. Example: SENIOR." | *Example: SENIOR.* | `2.475.0` |
| D9 | Review lists a few fields, no example | Every value, one row each, with an *Edit* link to its step; the discount on a $60.00 bill; *Saves as a draft.* | `2.475.0` |
| D10 | Long explanations under headings | None under any heading | `2.475.0` |
| D11 | Who qualifies typed as free text | A dropdown in two groups by `checked_by` (*The system checks* / *The customer shows proof*); sends the code as `eligibility` | `2.475.0` — empty until task 3 serves `form-options`; today's server refuses the code as `rating.unknown_field` |
| D12 | Exclusivity group typed as free text | A dropdown; sends the code as `exclusivity_group` | `2.475.0` — empty until task 3 serves `form-options`; today's server refuses the code as `rating.unknown_field` |
| D13 | Program owner typed as free text | A dropdown; sends the code as `program_owner` | `2.475.0` — empty until task 3 serves `form-options`; today's server refuses the code as `rating.unknown_field` |

**Ruling 3 on the form.** Enrollment offers the server's modes; under a *customer shows proof*
condition **Automatic is drawn disabled**, and a draft that already holds Automatic when a proof
condition is chosen is marked on the Enrollment box (*Automatic needs a system check.*) rather than
silently changed — nothing typed is lost. `proof_required` is SENT DERIVED from the chosen
condition's `checked_by`; no box sets it.

**What the API stores for a percentage, checked.** `discount_versions.value` holds percentage
POINTS (`selectors.discount_value_display`: *"`15` -> `15.00%`"*, BR-RAT-087). The form sends
exactly what was typed: `15` → `"value": "15"`. It does NOT reuse the tax form's
`percentToFraction` — that would store `0.15`, a 0.15 % discount. Seen on the wire against PostgreSQL 16 (private database `sbh_t4form`): the walk's real save sent `"value":"15"` and `"currency":"USD"` (`08-qa/discounts-2026-10-03/after/new-form-walk-output-real-save.txt`). That a stored `15.000000` prices 15 % is task 3's to prove once its server accepts the write.

### Our judgments where the drawing and the contract do not meet (recorded, not asked — law 13)

1. **Funding source is a text box, though image 05 draws a dropdown.** The contract (§9) has no
   funding list and §6 (a) keeps it free text, so a dropdown would have nothing to list or a
   hard-coded list. *Example:* CAP's *State grant* is typed. If a funding list is added to
   `form-options`, the box becomes a `SelectField` with no other change.
2. **Rate override's *Bill from schedule* is drawn and cannot act.** `BR-RAT-961` (PO 2026-08-31)
   ruled the schedule-swap mechanism away and no column holds a schedule, so the box is disabled
   (BR-SHL-025) and nothing is sent; offering a choice nothing keeps would be a live control over
   nothing (hard-won law 2's mirror). Saving a rate override stores the type only, as today.
3. **Named charge codes and specific services are one dropdown with ticks (`CheckDropdown`),
   though image 12 draws four checkboxes in a row.** B14 rule 44 (our UI standard decides how it is
   built) and rule 9 (never a wall of checkboxes): a utility with 60 charge codes would get 60
   boxes. Same choices, same required mark.
4. **"Proof needed before approval" is `proof_before_first_reduction`, shown only under a proof
   condition** — the decision-log map's *Proof before approval* is today's *Proof before reduction*,
   which "only some types show". Under a system condition there is no proof to wait for.
5. **The stacking order and the stacks-with tick are not counted in *N set*.** Both always hold a
   value; counting them would make *No limits* impossible. The count is caps, floor and an
   exclusivity group other than *None*.
6. **Usage allowance's unit comes from the chosen service** (`BR-RAT-960`): with *One service*
   chosen the box reads that service's billed unit (water → *kgal*); otherwise *units*.
7. **The $60.00 example** is a percentage of $60.00, a fixed amount, or the whole scope for a
   waiver ($60.00 subtotal, $20.00 base, $40.00 usage), trimmed by the cap per bill and stopped by
   the floor; a rate override, a usage allowance, or a scope naming services or codes shows *—*
   rather than a figure the example cannot know.

### Open for the back end (task 3), found while building

* **`accepted_proof_kinds`.** The server's GATE 2 (`discount_services._validate_version`) refuses
  `proof_required` with no accepted documents (`rating.discounts.proof_kinds_required`). The drawing
  has no *Documents accepted* box and the 31-box map does not keep one, so a discount whose *Who
  qualifies* is a proof condition is refused today with `rating.discounts.proof_kinds_required` (seen on the real save, same file). The form maps that refusal onto the *Who
  qualifies* box so the clerk sees it there. Task 3 decides whether a proof condition carries its
  own accepted documents or GATE 2 is relaxed for a draft.
* **`currency` on `form-options`.** The form reads the utility's currency from `GET /shell/display`
  (open to every role) because §9 says currency is "returned read-only" without naming where. If task
  3 adds it to `form-options`, nothing on screen changes.

### Tests (each shown RED first)

* `discountForm/discountFormModel.test.ts` (17) and `discountForm/NewDiscountWizard.dom.test.tsx`
  (14, mounted under the real `/:tenant/plans-rates/discounts/new` route).
* RED proofs, by breaking the code and running the suite: sending `Number(value) / 100` →
  `expected '0.15' to be '15'`; sending `ctx.currency ?? "USD"` → *leaves the key out … rather than
  guessing USD* fails `expected true to be false`; `automaticRefused` returning `false` → *Automatic
  with a proof condition is a gap* fails `expected false to be true`; the Enrollment option never
  disabled → `expect(element).toBeDisabled()` fails.
* `tsc`, `eslint` (changed files), the rating tests (144 of 146 files green across rating, components and i18n) and
  `vite build --mode wolocal` clean. **The one red is not this lane's and is dated:**
  `src/i18n/usEnglishCatalogue.test.ts` refuses `rating.taxForm.gap.taxed = "Tick"` (British) —
  added by `17e0be69d` (CR-165 task 4, 07:17 today); and `components/ConfirmDialogTier.dom.test.tsx`'s
  census, which does not list `billing/bulkRun/BulkRunPage.tsx` — its ConfirmDialog arrived in
  `8b7aee258` (03:22 today). `git log -S` names both commits.

### Screenshots

`08-qa/discounts-2026-10-03/after/05…18-*.png` and each beside its drawing as
`…-side-by-side.png`, at 1440 wide, by `10-scripts/cr166_new_discount_form_walk.mjs` on a private
PostgreSQL 16 database (`seed_demo` + `load_sample_data --tenant brazosbend`, signed in as Dana).
**Task 3's back end had not landed when these were taken.** The walk answered `GET /discounts/form-options` in the browser with the README's seeded values (`STUB_FORM_OPTIONS=1`) and image 18's save with a browser-answered `POST` (`STUB_SAVE=1`); `new-form-walk-output.txt` says so on its first lines. The same walk with the REAL save (`new-form-walk-output-real-save.txt`) shows today's server answering **422**, refusing `eligibility` and `program_owner` as `rating.unknown_field` — expected until task 3 lands. Images 19–22 are the details page (task 6) and are not this form's.

### Version and rollback

`2.475.0` (`allocate.py version --bump change`, verified at push). **Rollback:** redeploy the
previous build; the New door then opens `DiscountWizard.tsx` again (one line in `App.tsx`). No
migration and no stored row is added by this task.

### `DEF-RAT-9289` stays OPEN

D1–D10 are fixed in `2.475.0`. D11–D13 are fixed on the screen and are NOT yet working in the
product: their three lists are empty and a save carrying their codes is refused until task 3 serves
`form-options` and accepts `program_owner`, `exclusivity_group` and `eligibility` (§9). The row
closes when that lands and a real save succeeds.

## 12 · Round 2 task 5 — the list, built from images 01–04 (`2.473.0`)

**Built:** `07-frontend/src/features/rating/DiscountsTab.tsx` (rewritten) and
`discountListParts.tsx` (new, the row's cells — B14 rule 43), from images 01–04 opened as
images (rule 42); our kit decides spacing and type (rule 44). Columns, in the drawn order:
Code · Discount · Type · Value · Eligibility · Verification · From · To · Plans · Enrolled ·
Status · open. Toolbar: search (*Search code or name*) · All · `+ Filter ▾` with removable
chips (Status: Active, Draft, Waiting approval, Ended, Retired; Type: the five types) ·
columns. Both filters and the search go to the server as `f.status`, `f.type`, `q`, and the
list stays server-paged (NFR-3) — nothing filters the page. The contract's new fields are
read where served and a dash where not; nothing on screen invents them.

| D | What the drawing asks | Done | Proof |
|---|---|---|---|
| D14 | No overlay paragraph above the table | **FIXED** — the tab's explainer is gone and `rating.explainer.discounts` is retired from all eleven catalogues | `discountsList.dom.test.tsx` *D14*; `a01-list-all.png` |
| D15 | `$25.00` on a fixed value, `%` on a percentage | **SCREEN DONE, WAITING ON THE BACK END** — the cell prints the server's `value_display` and nothing else (BR-RAT-087); today's server still sends `25.00`, so the walk shows `25.00` until task 3 lands the contract's *"`value_display` with `$` or `%`"* | test *D15* (a contract row reads `$31.00`); `a01-list-all.png` shows `25.00` |
| D16 | Open to details, no pencil per row | **FIXED** — one eye icon *Open* to the details page; the pencil to the edit door and its key `rating.discounts.editAction` are gone | test *D16*; `a01`–`a03` |
| D17 | From and To columns, *No end* | **FIXED on screen** — From reads `effective_from`; To reads `effective_to` and *No end* when the server says null. Today's server does not send `effective_to` at all, so To reads `—` until task 3 lands it (a dash, never a promise of forever) | test *D17*; `a01` shows `08/01/2026` and `—` |
| D18 | The standard toolbar | **KEPT** (not a screen problem in round 1) — search, All, `+ Filter ▾`, chips, columns. **No CSV button**: `POST /exports` registers no `discounts` resource (`DEF-1005`, open), so a button would be wired to a 404 | test *D18*; `a02`, `a03` |

**Also:** Enrolled reads `receiving` once served (today's `enrolled` before); Eligibility and
Verification read the contract's `{value,label}` labels (an older server's text or code still
reads as words — a live crash the moment the contract landed, caught by the new tests); the
five status words are in all eleven catalogues (`waiting_approval`, `scheduled`, `ended`
added; `scheduled` renders but is not offered as a filter because image 02 does not offer it).
No-match (image 04) is the kit's *No results for 'zzz'* with *Clear filters*, as on every list,
not a sentence of our own.

**Tests:** `discountsList.dom.test.tsx`, 11 cases, written first and watched fail on the old
screen (8 for their own reason; D15 and the type filter already held); `Discounts.test.tsx`
amended in three cases that pinned the old nine columns, three filters and the pencil door.
`tsc` (shown able to fail), eslint, `vitest src/features/rating` (51 files, all green) and
`vite build` clean. Reds not caused here, dated: `usEnglishCatalogue.test.ts` (*Tick* in
`rating.taxForm.gap.taxed`, from `17e0be69d`); G13, G15, G18, G33, G37, G45 fail on files this
lane did not touch.

**Photographs:** `08-qa/discounts-2026-10-03/after/` — `a01`–`a04` at 1440 and each beside its
image (`a0Nside-…png`); `list-walk-output.txt` is what each state read;
`10-scripts/cr166_discounts_list_after_walk.mjs` re-runs it.

**Found on the way, filed:** `DEF-RAT-9298` — on `2.472.0` a fresh tenant's sample data
plants NO rating records (the taxes step now refuses the liability account it sets, and the
block stops before discounts). The photographs were taken with that one step skipped in a
scratch script; no product file was changed for it.

**DEF-RAT-9290 stays open**, on D15 and D17's back-end half: the screen is built for both and
the server does not yet send `$` or `effective_to`. Close it when task 3's list fields land
and the walk shows `$25.00` and *No end*.

**Rollback:** redeploy `2.472.0`. No data is written by this change.

## 13 · Round 3 task 6 — the details page, with the Accounts tab (built 2026-10-03, `2.480.0`)

**What was built.** `…/plans-rates/discounts/:id` now mounts `discountDetail/DiscountDetailPage`
(as the tax route mounts `TaxDetailPage`), built from images 19–26 opened as images (B14 rule 42),
our kit deciding spacing, type and components (rule 44), each piece a component (rule 43), Tailwind
only and every file on `route-b-migrated.txt` (rule 21). Files: `DiscountDetailPage.tsx`,
`DiscountDetailHeader.tsx`, `DiscountMoreMenu.tsx`, `DiscountLifecycleDialogs.tsx`,
`DiscountOverviewTab.tsx`, `DiscountAccountsTab.tsx`, `DiscountPlansTab.tsx`,
`DiscountAuditTab.tsx`, `discountDetailModel.ts` (the pure half) and
`07-frontend/src/api/discountDetailEndpoints.ts` (the §9 reads and acts, its own file so
`endpoints.ts` is not touched).

* **Header** — name and code; status pill · version · *Type · window* · *Next: 0.75% from
  01/01/2027* when a later value is approved; buttons by status: **Active/Scheduled** *Edit* ·
  More ▾ (Duplicate, Retire); **Draft** *Edit* · *Submit for approval* · More ▾ (Duplicate,
  Delete draft, Retire disabled *Not in force*); **Waiting approval** *Send back* · *Approve* ·
  More ▾; **Ended/Retired** More ▾ only.
* **Overview** — four tiles (Value · Offered to · Receiving it · Granted), *Details* (13 facts)
  and *Eligibility* (12 facts) — every value the New form takes — then the versions table and
  *See every change in Audit*.
* **Accounts** (new) — `GET /discounts/{id}/accounts`, paged, searched and filtered by the server
  (`q`, `f.status`, `f.plan`; list state in the URL under `acc.`), Account (a link, the number,
  never the id) · Customer and address · Plan · Enrolled · Renew by · This month · Status
  (*Receiving*, *Proof pending*, *Renewal due*); **×** ends ONE enrolment with a date and a
  reason (`POST /discount-enrolments/{id}/end`); **+ Enroll an account** searches accounts (2+
  letters) and posts `POST /accounts/{id}/discounts {programme_id}` — the server refuses an
  account whose plan does not carry it (ruling 2) and the refusal shows in the dialog.
* **Plans** — Plan (link) · Services · Customer classes · Accounts · Since.
* **Audit** — `GET /discounts/{id}/audit`, When · Who · What · Change (*Notice: 0 → 30*) ·
  Reason, names never ids, paged.
* **Acts** — Submit (`/submit`), Approve (confirm *It goes live on 11/01/2026.*, `/approve`),
  Send back (note required, `/send-back`), Retire (last day, today or later, optional reason,
  `/retire`), Delete draft (the draft version's `/discard`). Every refusal is the server's own
  sentence (BR-SHL-020).
* **Edit** routes to `/plans-rates/discounts/:id/edit?change=info` — task 7's door (§13 judgment 9).

### D19–D34 (`DEF-RAT-9291`)

| D | Today | Now |
|---|---|---|
| D19 | Kicker *DISCOUNT · AUTOPAY · PERCENTAGE · V1* | No kicker; name, code beside it, facts line |
| D20 | Overlay paragraph under the title | Gone (rule 33) |
| D22 | Four buttons; Duplicate greyed | Buttons by status + More ▾; Duplicate held (`DEF-RAT-9310`) |
| D23 | Tiles on every tab | Tiles on Overview only |
| D24 | Type tile on three lines | Value tile: *0.50% / off subtotal before taxes* |
| D25 | *75 · 75 units on a plan carrying it* | *Offered to 75 / units on its plans* |
| D26 | *"Nothing works out a month's subsidy…"* | Gone; Granted is a bare dash |
| D27 | Money without $ | `$` from the server (`money_display`, `value_display`) |
| D28 | Red kickers over grey labels | The kit's `FactBlock` labels |
| D29 | Plans tab empty | Plans named, with services, classes, accounts, since |
| D30 | No way to see who gets it | The Accounts tab |
| D31 | Audit = versions only, stray *Discard draft* | Audit = every change; versions on Overview; discard is *Delete draft* in More ▾ |
| D32 | *DATED* note box | Gone |
| D33 | 12 entered values never shown | All shown (25 facts) |
| D34 | Effective to under Who qualifies | Starts and Ends together under Eligibility |

**`DEF-RAT-9291` is closed** by this build. D22's Duplicate is split out as `DEF-RAT-9310` (open).

### Our judgments where drawing, kit and contract do not meet (recorded, not asked — law 13)

Decision log row *"DISCOUNT DETAILS PAGE BUILT FROM IMAGES 19–26"* holds all eleven with a worked
figure: Approve is the primary on Waiting approval (image 26 paints Send back red); Approve
confirms first; image 25's empty table is the kit's empty block (BR-SHL-012); no ⤓ on Accounts or
Audit (`DEF-1005`); *+ Add to a plan* and × held with *Change it on the plan.* (`DEF-478`);
Duplicate held (`DEF-RAT-9310`); *Delete draft* in More ▾ replaces the old Audit tab's discard and
`discountDetailTabs.tsx` is deleted; Granted / This month a bare dash (`DEF-2430`,
`DEF-BIL-5341`); the edit door address; three read additions (§9 *Fields added*); two server
reads fixed (`DEF-RAT-9308`, `DEF-RAT-9309`).

### The list (task 5) on the 2.478.0 shapes — checked, not broken

`DiscountsTab` already reads `eligibility` as `{value,label}` and `status` as the derived word;
`exclusivity_group` is not a list column. The walk's `d00-list-on-new-shapes.png` against the
real 2.478.0 server shows every row in words — *Autopay is on*, *Automatic*, `0.50%`, `$25.00` —
and no `[object Object]` cell. No change was needed.

### Tests (each shown RED first)

* `discountDetail/discountDetail.dom.test.tsx` — 30 cases under the real route; **26 of 30 failed
  on the old shell** before `DefinitionDetailPage` mounted the new page. The `money_display` case
  was re-proved red by breaking `money()` (`expect(element).toHaveTextContent()` on `$4.00`).
* Backend `tests/test_cr166_discounts_round2.py` +5 (29 pass): plan rows' services and classes,
  version rows' end date (both RED first, `KeyError`), money with its symbol, the customer name
  without a link (`DEF-RAT-9308`, RED: `None == 'Alvarez, Rosa'`), the audit names the plan
  (`DEF-RAT-9309`, RED: `KeyError: 'plan'`).
* Retired, not rewritten (each fact is asserted on the new page): three discount-render cases removed and three narrowed in
  `DefinitionDetail.test.tsx`, eight in `DiscountLifecycle.test.tsx` (Activate is gone; BR-RAT-109
  superseded), the five DEF-RAT-5817 Audit-tab cases in `discountDraftAndProof.dom.test.tsx`.
* `ConfirmDialogTier` census: `discountDetailTabs.tsx` out, `DiscountDetailPage.tsx`
  `["primary","danger"]` in (44 → 45, primary 5 → 6).
* `tsc` clean, eslint clean on every changed file, `vitest src/features/rating src/i18n
  src/components src/styles` — 1 red, not ours and dated: the census omits
  `billing/bulkRun/BulkRunPage.tsx`, whose ConfirmDialog arrived in `8b7aee258` (2026-10-03).
* Gates: none of the 43 reds names a file this change touched. G15 counts the **68 new keys in
  ten catalogues as English** — deliberate: they are placeholders for task 8, the eleven-language
  pass (the brief: English only). G35 is satisfied by this commit's CHANGELOG entry.

### Screenshots

`08-qa/discounts-2026-10-03/details/` — `d19`–`d26` (the built page, full height, 1440 wide, each
opened and checked not blank) and `d19-side`–`d26-side` (drawing left, built right), plus
`d00-list-on-new-shapes.png`; `details-walk-output.txt` is what each state read. Re-run:
`10-scripts/cr166_discount_detail_walk_prep.py` then `10-scripts/cr166_discount_detail_walk.mjs`,
on a private PostgreSQL 16 database (`sbh_disc_det`, `seed_demo` + `load_sample_data --tenant
brazosbend`, signed in as Dana). The prep runs the automatic enrolment for AUTOPAY (5 accounts),
saves a new value 0.75% from 01/01/2027, and creates and submits LIFELINE ($10.00 from
11/01/2026).

### Version and rollback

`2.480.0` (`allocate.py version --bump change`, verified at push). **Rollback:** redeploy
`2.479.0`. No migration and no stored row; the read additions are new keys older screens ignore.
`discountDetailTabs.tsx` comes back with the redeploy.

### Open

`DEF-RAT-9310` (Duplicate), `DEF-478` (plan add/remove from the discount), `DEF-2430` /
`DEF-BIL-5341` (Granted, This month), task 7 (the edit form behind *Edit*), task 8 (the 68 keys
in ten languages).

## 14 · Round 3 task 7 — Edit a discount, the same form as New with three choices (built 2026-10-03, `2.481.0`)

**What was built.** `…/plans-rates/discounts/:definitionId/edit` mounts
`discountForm/EditDiscountForm.tsx`, built from images 27–36 opened as images (B14 rule 42), our kit
deciding spacing, type and components (rule 44), each piece a component (rule 43), Tailwind only and
every new file on `route-b-migrated.txt` (rule 21). It is the New form's own sections over a draft read
back from the discount (`discountEditModel.discountDraftFromRow`), with *What to change* on top
(`EditDiscountChoiceCards`) choosing the step list and the LOCKED fields. The lists are loaded by
`useDiscountFormLists`, lifted out of `NewDiscountWizard.tsx` so both pages read them one way (the tax
form's `useTaxFormLists` precedent). `DiscountWizard.tsx`, its test file and **101** catalogue keys only
it read are retired; its wizard-reading cases in `discountVerbs`/`discountDraftAndProof` went with it.

| Choice (`?change=`) | Steps | Locked | Save → |
|---|---|---|---|
| **Name and details** (`info`) | Details · Eligibility · Review | code and type (facts), *Value and limits* (a fact strip, *🔒 Change with a new value.*), the start | `PATCH /discounts/{id}` — the CHANGED keys only (a cleared box is `null`) |
| **New value from a date** (`change`) | New value · Review | everything but Value, Limits and the dates | `POST /discounts/{id}/new-value` — the value, any changed scope/limit, `effective_from`, `effective_to` if typed |
| **Fix a mistake** (`correct`) | Fix the value · Review | the dates (*🔒 Same dates as today.*) | `POST /discounts/{id}/corrections` — the CHANGED keys + `reason` |

Errors as drawn: image 32 *Must be after 08/01/2026.* and image 35 *Enter the reason.*, each with *Fix 1
thing first.*; a refusal from the server is marked on its box (or the strip when the choice draws no
such box). Review (29/33/36): *What changes* before → after, *On a $60.00 bill* before → after (not on
29), *How it is saved* with the version rows and the note (*Bills before 01/01/2027 keep 15%.* /
*Issued bills keep 15%. Correct those bills separately.*). Saved (30): *Senior discount saved* and one
sentence (*Saved on this version.* / *v2 starts 01/01/2027.* / *v2 replaces v1.* — *Logged in Audit.*).

**Route, agreed with task 6 by reading the tip:** the details page's Edit links to
`/plans-rates/discounts/:id/edit?change=info` (`discountDetailModel.discountEditPath`) and this lane's
`discountEditPath` spells the same three addresses; clicked through in the browser, it lands on
*Name and details*. The pre-redesign `?correct=1` lands on *Fix a mistake*.

**The New form and the §9 shapes.** The New form writes codes (`program_owner`, `exclusivity_group`,
`eligibility`) and reads no discount row, so nothing in it read the changed shapes; a real
`POST /discounts` with those codes answers 201 on PostgreSQL. The edit form reads `eligibility`,
`exclusivity_group` and `program_owner` as `{value,label}` objects by CODE (`optionCode`), never as
strings (`discountEditEndpoints.DiscountEditRow`).

### Our judgments (recorded, not asked — law 13)

1. **A draft has one choice and locks nothing.** `PATCH` edits a never-submitted draft in place
   (BR-RAT-1016 verb 1); *New value* and *Fix a mistake* need a version in force and are drawn
   disabled, whatever `?change=` asked for.
2. **Switching cards starts that flow again from the discount as saved** (the tax edit's judgment 3).
3. **Save is held until something changed** on *Name and details* and *Fix a mistake* (the server
   refuses an empty correction anyway).
4. **A zero floor reads as no floor** (the stored default, BR-RAT-074), so an untouched discount reads
   *No limits* as image 31 draws; a floor cleared on a save is sent as `0`, never `null`.
5. **The scope travels as one group**: a discount moved off *One service* sends its service as `null`
   and both lists empty, so no stale target stays behind.
6. **The two undrawn saved states** (after *Save new value* and *Save correction*) reuse image 30's
   layout with their own sentence.

### Server, found while building (filed before fixing)

* **`DEF-RAT-9313`** — `new_discount_value` stripped `effective_to`: 12% from 01/01/2027 to
  06/30/2027 answered 201 and stored v2 with no end (PostgreSQL, `PRB48613`). Now a typed end is v2's
  end; before its start → `window_inverted`, past a recorded retire date → `ends_after_retire` (new key,
  *It ends after the retire date.*). Re-proved on PostgreSQL: v1 08/01/2026–12/31/2026, v2
  01/01/2027–06/30/2027.
* **`DEF-RAT-9314`** — a new value on a discount retiring later was refused *Dates overlap version 1*:
  the overlap check ran before v1's stated end was moved. The trim now runs first, in the same
  transaction. Red on the unchanged code.
* `06-backend/tests/test_cr166_discount_edit_r3.py` (5 cases, 3+1 red first); round-2 suites green
  (sqlite 24, PostgreSQL 7).

### One version per date, on PostgreSQL 16

`10-scripts/cr166_edit_one_version_per_date.py`, over the two discounts the walk saved through the
screen (`08-qa/discounts-2026-10-03/edit/one-version-per-date.txt`): **new value** — every day
12/25–12/31/2026 exactly 1 version in force, billing reads v1 15% → −$9.00 off $60.00; 01/01–01/05/2027
exactly 1, v2 12% → −$7.20. **Fix a mistake** — v1 superseded and kept, every day exactly 1, v2 1.5% →
−$0.90.

### Tests and checks

* `discountForm/EditDiscountForm.dom.test.tsx` (17, under the real route) — **15 of 17 red** against
  `DiscountWizard` mounted at the same route; the 2 that passed read `App.tsx` and the address helper.
  `discountForm/discountEditModel.test.ts` (15). The New form's hold-expiry case (*"leaves edit on
  DiscountWizard until round 3"*) fired as written and now asserts `EditDiscountForm`.
* `tsc` (shown able to fail), eslint (shown able to fail), `vitest src/features/rating src/i18n
  src/components` 1949 passed. **The one red is not this lane's, dated:** `ConfirmDialogTier` census
  over `billing/bulkRun/BulkRunPage.tsx`, from `8b7aee258`.
* Gates (`run_gates.py --changed`, and the doubtful ones re-run on a `git archive` extract of the tip
  to date them): G34, G44, G15 (811 → this lane's 56 keys × 10 English placeholders, task 8 translates),
  G13 and G40 were red on the tip. **G38** fell 39 → 37 (the wizard's stated absence, and one more with task 6's deletions on the tip) — baseline
  lowered. **G18** gained 101 dead keys when the wizard went — retired through `i18n_fanin.retire`.
  **G40 +1 / G13 +1** are `RateScheduleWizard.tsx`'s `EffectiveStep`, unmounted all along and masked
  by the retired wizard's same-named local component — filed **`DEF-RAT-9315`** (both gates match by
  bare name).

### Coordinator's two details-page defects (on the tip, fixed here)

* **`DEF-RAT-9311`** — Overview money had no thousands separator: `money()` now formats the stored
  amount with the row's currency through the shared `formatMoney` → `$2,383.00` (the server's
  `money_display` is the fallback). Red first: `expected '$2383.00' to be '$2,383.00'`.
* **`DEF-RAT-9312`** — 13 facts in three columns left a dark-grey block: in a fixed-column strip the
  last fact now takes `col-span-<cells left>` (`FactBlock.lastFactSpan`). A first try with
  `grid-column-end: -1` moved the cell instead and was caught in the browser. Both seen fixed:
  `08-qa/discounts-2026-10-03/edit/def-rat-9311-9312-overview.png`.

### Photographs

`08-qa/discounts-2026-10-03/edit/27…36-*.png` at 1440 and each beside its image (`…-side-by-side.png`),
plus `33b`/`36b` (the undrawn saves, beside image 30), by `10-scripts/cr166_edit_discount_walk.mjs` on a
private PostgreSQL 16 database (`seed_demo` + `load_sample_data`, signed in as Dana) — each checked not
blank; `walk-output.txt` is what each state read and what the three saves wrote. Figures differ from
the drawing where the data does (rule 37: the code is `SRA…`, the owner list is the utility's).

### Version and rollback

`2.481.0`. **Rollback:** redeploy `2.480.0`. No migration and no stored row is added by this task; the
server change only accepts an end date and orders two writes inside one transaction.

### Open

Task 8 — the 56 keys in ten languages (English placeholders today). `DEF-RAT-9315` (the two gates and
the unmounted `EffectiveStep`). `DEF-RAT-9310` (Duplicate) still holds.

## 15 · Round 3 task 8 — the eleven languages on the four discount screens (2.481.1 → 2.481.3)

**Scope.** Every key the four discount screens render: the list, *New discount*, the details page
(Overview, Accounts, Plans, Audit, and the Retire, Approve, Send back, End enrolment, Enroll an
account and Delete draft dialogs) and *Edit* with its three choices. That is **376 keys** read by
`DiscountsTab.tsx`, `discountListParts.tsx`, `discountForm/*` and `discountDetail/*` (static keys
and every key under a dynamic prefix), plus **7 new keys** (below): **383 keys × 10 catalogues**.
Of these, **123 were English placeholders** left by task 6 (68) and task 7 (55); the rest were
reviewed against B14 rules 33–35 and the words the same catalogue uses elsewhere. Every change went
through `10-scripts/i18n_fanin.py` (`apply` with `allow_overwrite`); no catalogue was round-tripped.
Defect `DEF-RAT-9316`.

**The rule applied (B14 rule 35), as on the tax screens (§15 of `CR-165-BRC10`).** One word per idea
per catalogue, the word that catalogue already uses most:

* **de** *Sparte* for a service (95 rating keys against 30 for *Leistung*, which also means demand),
  *Freigabe* for approval (61 against 38), *Fassung*, *Kundenkonto*, *Anmeldung*, *Nachweisprüfung*.
* **es** one voice, *tú*, as the tax screens and es-MX (the form mixed *usted* and *tú*);
  *importe* not *monto* (316 against 3); *justificante* for a proof document (*prueba* is a test
  here); *alta* / *dar de alta* for enrolment; *Elegibilidad* (13 against 5); *Quién tiene derecho*
  (the form's *Quién califica* is a calque in Spain; es-MX keeps *califica*, which is natural there);
  *Subtotal antes de impuestos* (was *Base imponible antes de impuestos*).
* **es-MX** *recibo* for a bill, *importe* (199 against 91), *inscripción*, *comprobante*, *Estado*
  for status (246 against 14 for *Estatus*).
* **fr** *codes de facturation* (38 against 29 for *codes de frais*), *forfait* for a plan; *frais*
  is plural, so *Tout le frais* reads *Tous les frais*.
* **pt** *fatura* for a bill (the form said *conta*, which is an account); *inscrição* not *adesão*;
  *Estado* for status (117 against 103).
* **hi / ko** *Edit* is the details page's word (hi बदलें, ko 수정). **hi** *grace* is रियायती अवधि:
  छूट is the word for a discount, so छूट अवधि read as "discount period".
* **ja / ko** units are ユニット / 세대, as the premises screens say.
* Every "see it in Audit" names the tab as the tab reads (de *Prüfspur*, fr *Suivi*, it *Storico*,
  id *Jejak audit*, ja 履歴, ko 이력); *No end* reads as on the list; the versions table names a
  version the way the header's pill on the same page does (de *Fassung 2*, ja 第2版).

**The English nit, and why it took code.** The form's right panel read *off Subtotal before taxes*:
it dropped the capitalised list label into `summary.off`. The details page's Value tile lowercased
the same label, which reads right in English and wrong in German (*zwischensumme vor steuern*). Each
platform scope now has its own in-sentence phrase, `rating.discountForm.offScope.<code>` (7 keys ×
11), read through `offScopePhrase` in `discountFormShared.tsx` by both the panel and the tile. A
service or charge codes a draft names are the utility's words and still go into `summary.off`. The
New form's test asserts *off subtotal before taxes* and was red first
(`expected … to have text content "off subtotal before taxes"`, received *off Subtotal before taxes*).

| Language | Keys reviewed | Placeholders written | Older values changed | New keys | Could not resolve |
|---|---|---|---|---|---|
| de | 383 | 123 | 9 | 7 | — |
| es | 383 | 123 | 38 | 7 | — |
| es-MX | 383 | 123 | 43 | 7 | Shell nav *Work* (shell, not this CR) |
| fr-FR | 383 | 120 (3 are French already: *Version*, *Note*) | 7 | 7 | Shell nav *Lit* for Reads (shell) |
| hi | 383 | 123 | 45 | 7 | Shell nav *Work* (shell) |
| id-ID | 383 | 123 | 40 | 7 | Shell nav *Work* (shell) |
| it-IT | 383 | 123 | 3 | 7 | Shell nav *Legge* for Reads (shell) |
| ja-JP | 383 | 123 | 40 | 7 | Shell nav *Work* (shell); list *種類* column wraps 定率 one character a line at 1440 |
| ko-KR | 383 | 123 | 41 | 7 | Shell nav *Work* (shell); list *유형* column wraps the same way |
| pt-BR | 383 | 123 | 13 | 7 | Shell nav *Lê* for Reads (shell) |

**Left as they are, on purpose.**
- The exclusivity group's *None*, program owner (*Billing*, *Customer service*), who qualifies
  (*Autopay is on*), funding source and every discount name are the utility's own list values
  (`discount_list_values`), not catalogue text. The *None* row is renameable in Settings.
- G15 still names five values identical to English in scope, all written by task 4 (`32fe0d799`)
  and all the right word: *Budget* (de, fr, it), *Services* (fr), *Label* (id). Allowing them is a
  change to a ratified gate's list, so it is reported, not made.
- The list is twelve columns; at 1440 it scrolls sideways in its own box in **every** language,
  English included, and *Status* sits under the pinned open icon until scrolled (the kit's
  `DEF-SHL-5378` behaviour). That is the list's layout (task 5), not copy.
- The dialogs (Retire, Approve, Send back, End enrolment, Enroll an account, Delete draft) were
  reviewed as text; they were not photographed.

**Checks.**
- Placeholders (`{{…}}`) identical to English in every changed value; every `_one` has its `_other`.
- G15 scoped to these 383 keys: **0 new English paste-ins**; overall fresh **2,047 → 820** against
  the tip, none added (the 5 above predate this lane).
- G33: none of the 10 reds is a discount key (they are `rating.schedules.*` from `ebe088db2`,
  2026-09-19, and five other modules).
- `usEnglishCatalogue.test.ts` green; `vitest src/i18n src/features/rating` **62 files, 1,076 passed**;
  `tsc` (local install) clean.
- `run_gates.py --changed c179688b5`: no red names a file or key this lane touched (G13 is
  `RateScheduleWizard`'s `props.correcting`, `DEF-RAT-9315`; G44 is `SelectionRowPreview.tsx` from
  `67cb9e0c7`, 2026-09-22).

**Photographs.** `08-qa/discounts-2026-10-03/i18n/{list,new,detail-overview,detail-accounts,edit-review}-<lang>.png`,
**55 at 1440** on a private PostgreSQL 16 database (`sbh_disc_i18n`: `seed_demo` + `load_sample_data`
+ `cr166_discount_detail_walk_prep.py`, signed in as Dana), by `10-scripts/cr166_discounts_i18n_walk.mjs`
(it drives each screen in English, switches the language and photographs; *Edit* is *New value from a
date* › Review, 16% from 03/01/2027). Each was opened and looked at: none is blank, no English is
left in the screens' own words, nothing overflows the page sideways.

**Version:** 2.481.1 (first pass, `7ce626c5a`), 2.481.3 (screenshot pass and this record; 2.481.2 is a sibling lane's).
**Rollback:** redeploy 2.481.0. Catalogue text and one display helper; no migration and no data.

## 16 · Round 4 task 9 — the full web walk, and what it fixed (2.481.6–2.481.11)

The walk the PO asked for (*"how you will do end end web walk - similar to tax"*), to the plan
`05-prototype/discounts-2026-10-03/web-walk.md`: one of every kind of discount created through the
New form, checked, viewed, put live, bound to plans, enrolled, edited three ways, billed on REAL
ISSUED runs, retired on a date, and looked at from a second utility and in eleven languages.
Walked on PostgreSQL 16 through the built screens at 1440, signed in as Dana, in three sessions
(the checkpoint, lane DISC-FIX, lane DISC-WALK). Scripts `10-scripts/cr166_discwalk.mjs`,
`cr166_discwalk_world.py`, `cr166_discwalk_step9.mjs`. **The record, with every check, every
photograph and the bill lines as stored: `08-qa/discounts-2026-10-03/walk-report.md`.**

**The world.** Water only: `BASE-W` $8.00 + 0–10 kgal at $4.20 + above at $5.00, so a residential
account using 12 kgal bills **$60.00** (the municipal account has no base and bills $52.00). Seven
accounts on four walk plans; Utility B (Riverbend Water) has no discounts.

| Step | What was checked | Result |
|---|---|---|
| 1 | One of every kind through the New form, plus a draft saved half way, reopened and finished | **24 of 24** — nine discounts, one row each; Review on $60.00: Senior −$9.00, CAP −$10.00, Autopay −$0.30, Municipal −$5.00 (after `DEF-RAT-9318`) |
| 2 | Form mistakes | **8 of 8** — each on its own box, nothing typed lost, currency USD read-only, CAD refused by name |
| 3 | View | **27 of 27** — every value served as entered; blank boxes store the server defaults |
| 4 | Going live | **28 of 30** — Submit → Approve, live with no Activate; *Paperless* (11/01) reads *Scheduled*. The 2 fails are known: **Garden** (usage allowance) cannot go live (`BR-RAT-962`, with the PO, §17) and Lifeline goes live on ONE approval with the threshold on (`DEF-RAT-9303`) |
| 5 | Plans and enrollment | **10 of 10** — Automatic enrolled exactly the autopay account and exactly the municipal one (ruling 3); an off-plan account refused *"Their plan doesn't offer this discount."* (ruling 2); Senior off the plan → enrollment ended *Removed from plan …*; put back, re-enrolled |
| 6 | Accounts tab | **10 of 10** — Verify proof, Enroll and End work and close; tab count = rows = Overview *Receiving it*; Granted / This month a dash (`DEF-2430`) (after `DEF-RAT-9325`, `9326`) |
| — | List width (`DEF-RAT-9319`) | **11 of 11 languages** — 1,120px, no sideways scroll, Status in view, Type never one character a line |
| 7 | Edit three ways | **12 of 13** (the 13th is `DEF-RAT-9338`'s red run) — a rename keeps the row and v1; Senior 15 % → 12 % from 01/01/2027 makes v1 end 12/31/2026 and v2 start 01/01/2027, nothing deleted; Veteran *Fix a mistake* 1.5 → 15 keeps v1 *superseded*, same dates |
| 8 | Billing gets exactly one version | **12 of 12** — one Senior row every day 12/25/2026–01/15/2027; Ruth's issued December bill **−$9.00 → $50.74**, January **−$7.20 → $52.54**; December unchanged afterwards (after `DEF-BIL-9339`) |
| 9 | Limits on real, ISSUED bills (Oct 2026 – Jan 2027) | **5 of 7, 1 pending** — Senior then Autopay on what is left (−$9.00, −$0.26 → **$50.74**); CAP and Lifeline never both (CAP −$10.00, the $50.00 floor); Veteran −$0.90; Municipal capped −$5.00 → $47.00; Lead line waiver −$8.00 → **$52.00** (after `DEF-RAT-9327`); a FEE-code waiver refused at Approve. **9.3** *CAP stops after $300.00* fails on `DEF-2430` (no grant is written at issue); **9.4** Garden pending with the PO |
| 10 | Retire on a date | **2 of 3** (the 3rd is `DEF-RAT-9340`'s red run) — Senior retired 01/31/2027: Ruth's enrollment ended that day; her February bill has **no Senior line**, Autopay −$0.30 → $59.70; December and January unchanged |
| 11 | Utility B and eleven languages | **60 of 60** — B sees nothing of A on screen (*0 discounts*), through the API (404 on read, accounts, audit and a retire write) or in the database (RLS: 0 discounts, 0 versions, 0 enrollments under B); four screens × 11 languages, no English left, nothing overflowing (after `DEF-RAT-9341`) |
| | **Total** | **215 checks: 209 pass, 5 fail, 1 pending.** Two fails are red runs of defects fixed in the walk; three are known and open (Garden, `DEF-RAT-9303`, `DEF-2430`) |

**Every defect the walk found, and where it is fixed:**

| Defect | Found at | What the user saw | Fixed in |
|---|---|---|---|
| `DEF-RAT-9318` | 1.6 | a charge waiver could never be saved — *Fix 1 thing first.* with nothing marked | **2.481.6** (`d74d243c6`) — the form sends value 0 for a type with no value box |
| `DEF-RAT-9319` | task 8 photos | the list scrolled sideways at 1440; ja/ko *Type* one character a line | **2.481.6** — *Verification* off by default in ▦ Columns; Type/Status keep their words whole |
| `DEF-RAT-9325` | 6 | a *Proof pending* enrollment could never be verified, so the bill took $0.00 off, not −$9.00 | **2.481.6** — `POST /discount-enrolments/{id}/verify` and ✓ *Verify proof* |
| `DEF-RAT-9326` | 5 | Enroll and End stayed open after they worked | **2.481.6** |
| `DEF-RAT-9327` | 9 (October preview) | an approved waiver on a named charge code stopped every enrolled account's whole bill (*"rating refused to price this bill"*) | **2.481.11** (`f722c6c3c`) — the base line carries its charge code; a FEE code is refused at Approve |
| `DEF-RAT-9338` | 7 | a rename left no trace in the discount's Audit | **2.481.7** (`b7172350c`) |
| `DEF-BIL-9339` | 8 | a bill's discounts listed under *Taxes & fees* on a bill with no tax | **2.481.8** (`40ea3d0b4`) — their own *Discounts* group |
| `DEF-RAT-9340` | 10 | Retire (and Send back) stayed open after it worked | **2.481.9** (`6b10c77ab`) |
| `DEF-RAT-9341` | 11 | ja/ko list headers broken inside a word (プラ/ン, 요금/제) | **2.481.10** (`d647df5f2`) |
| `DEF-RAT-9289` | 1, 3 | New form D11–D13 (the three lists) not yet working at round 2 | **closed** — stored through the New form in steps 1 and 3 |

**Our judgments made in the walk (recorded, not asked — law 13; decision-log rows
*"DISCOUNTS WEB WALK, STEPS 7, 8, 10, 11 — FOUR JUDGMENTS"*, *"A CHARGE WAIVER ON A NAMED CHARGE
CODE"* and *"THE DISCOUNTS REDESIGN IS CLOSED"*):**
1. **The *Verification* column is off by default** in the list's ▦ Columns (`DEF-RAT-9319`): twelve
   columns needed 1,196px in a 1,120px box; it is the least-read column and stays one tick away.
2. **Plans were bound through the plan wizard's own save** (`PATCH /plans/{id} {discounts, reason}`)
   — the walk's fixture plans carry no service the wizard's step 2 reads, so it could not be
   clicked; the PATCH is the exact request the wizard sends. Add/remove from the discount page is
   `DEF-478` (§17).
3. **A box left blank takes the server's default**: notice 60 days, grace 0, stacking 100, group
   *None* — stored and shown as those values, never as blank.
4. **`DEF-RAT-9327`: the base line carries its charge code** through the engine, so a named-codes
   waiver takes exactly that line off (Mia: $8.00 `BASE-W` → −$8.00, **$60.00 → $52.00**); a code
   that can never be on a priced line (a fee) is refused at **Approve**, never at the bill run.
5. **A bill's whole-bill discounts have their own *Discounts* group**, after the services and
   before *Taxes & fees* (`DEF-BIL-9339`).
6. **The ja/ko header fix is scoped to the discount list**, not the shared table (`DEF-RAT-9341`).
7. **The walk world reads to 02/15/2027** and creates the February read partition, so Retire is
   proved on an ISSUED bill rather than a preview.
8. **Retire is decided by the bill's service date** (BR-RAT-007): a 01/16–02/15/2027 bill has no
   Senior although sixteen of its days are before 01/31 — the existing rule, not a proration miss.

**Evidence.** `08-qa/discounts-2026-10-03/walk-report.md`; `walk/results.json` (208 rows),
`walk/state.json`, `walk/world.json`, `walk/steps-8-10-11-server.txt`; photographs
`walk/discwalk_<step>_<n>.png` (each opened by the lane that took it; none blank) — e.g.
`discwalk_9_1.png` (Ruth's October bill), `discwalk_9_5.png` (the waiver), `discwalk_8_bill_*_fixed.png`,
`discwalk_10_1.png` (Retire), `discwalk_11_b_list.png` (Utility B), `discwalk_11_list_<lang>.png`.

**Golden** (`06-backend/tests/golden`): **25 passed, 1 xfailed** before (tip `a8327b1ab`) and after
every fix. No ❄️ figure or signed rule moved; `discount_pricing.py` (the arithmetic) untouched; every
🔒 file the walk's fixes touched (the engine path for `DEF-RAT-9327`, `discount_services.py` for
`9327` and `9338`) carries a review-ledger row, HUMAN-REVIEW-PENDING.

**Version:** 2.481.6 → 2.481.11. **Rollback:** redeploy the build before each (2.481.5 … 2.481.10);
none of them adds a migration or changes stored data. Bills issued under them keep their lines.

## 17 · Round 4 task 10 — the close (2.481.11)

### What was delivered against the PO's rulings

| The PO said (decision log 2026-10-03) | Delivered | Proof |
|---|---|---|
| *"there are 5 steps we need to reduce them to 3"*, *"1 word steps"*, Details · Eligibility · Review, all 31 boxes kept | the New discount form | §11, 2.475.0; walk steps 1–3 |
| *"list view - text to be reduced"*, the list page approved | the list from images 01–04 | §12, 2.473.0; walk step 11 |
| *"Program owner - make this drop down - give it values"*, exclusivity group and who qualifies dropdowns, **editable per utility** | three Settings › Reference data lists (8 · 6 · 11) | §10, 2.478.0 |
| *"Currency - it is default of utility - user cannot change it"* | currency fixed to the utility, CAD refused by name | §10; walk step 2 |
| *"can youa dd tab and show the list of accounts who are getting this discount?"* | the details page with an Accounts tab | §13, 2.480.0; walk step 6 |
| Edit as the same form | Edit with three choices (Name and details · New value from a date · Fix a mistake) | §14, 2.481.0; walk step 7 |
| Ruling 1 — approved goes live by itself on its start date | approval is the last act; Activate gone | §10; walk step 4 |
| Ruling 2 — only accounts whose plan carries it; removal stops it from the next bill | one plan gate for enrolment, the R6 door and the bill | §10; walk step 5 |
| Ruling 3 — Automatic enrolls every qualifying account | the enrolment job | §10; walk step 5 |
| Ruling 4 — Retire asks for an end date; after it nobody gets it | dated retire | §10; walk step 10 (Feb bill, no Senior) |
| CAP and Senior *"A Keep them excluding each other"* | one group *Assistance programs* | walk step 9: CAP −$10.00 only, never $19/$34 |
| *"i want images to be used to create prodict screens"* | every screen built from images 01–36 | §11–§14 |
| eleven languages | 383 keys × 10 catalogues | §15, 2.481.1/2.481.3; walk step 11 |
| *"end end web walk - similar to tax"* | 215 checks, 209 pass | §16 |

### Checks re-run for the close (2026-10-03, tip `8475eafa0`)

| | Result |
|---|---|
| Golden `06-backend/tests/golden` | **25 passed, 1 xfailed** (unchanged since round 1) |
| `10-scripts/03-golden-verify.py` | **33 PASS, 0 FAIL** (document self-consistency — it runs no engine code) |
| The six discount test files named red before this round | 14 failed, 66 passed — every red dated and owned (below) |

### Reds in the discount test files, read and dated (law 7 habit 1)

The step-9 lane saw **14 backend tests** red in six discount files before its own change and
reported them unfiled. Each was re-run on the tip, read, and dated with `git log -S` / `-L`.
**None is a product regression and none was caused by this CR's rounds 2–4 except one half of
`test_def2803`.** Two pre-redesign rows already existed for most; the rest are filed now.

| Test(s) | Red since | Cause | Row | Here |
|---|---|---|---|---|
| `test_cr013_discount_reads.py` ×6 | `d5b6fecc2`, 2026-09-02 (CR-062 J2) | the sample fixture seeds a sixth discount, MUNICIPAL; the tests assert five | `DEF-RAT-4670` (dup `DEF-RAT-4828`) | not fixed — not the redesign |
| `test_cr013_discount_writes.py` ×1 | `c656deea1`, 2026-09-19 | `GET /discounts/{id}/versions` added on purpose (`DEF-RAT-5817`); the guard asserts POST only | **`DEF-RAT-9343`** (new) | not fixed — not the redesign |
| `test_cr048_b_engine_on.py::b8` | `28dee3b8b`, 2026-09-11 | `pdf_print` now has an adapter | `DEF-NOT-6267` (b) | not fixed — notifications |
| `test_cr048_b_engine_on.py::b9` three counts | `aff5f079d`, 2026-09-27 (P4.10) | 32 built events, the test says 31 | **`DEF-NOT-9344`** (new) | not fixed — notifications |
| `test_cr048_b_engine_on.py::b9` third count | 2026-09-20 | ten seeded wordings with no event row | `DEF-NOT-6267` (c), `DEF-NOT-6275` | not fixed — notifications |
| `test_def2803_discount_row_parity.py` ×1 | `7d95ce22f` 2026-09-02 / `0ff76cb08` 2026-09-17, **and** `c4c276685` 2026-10-03 (this CR) | `gl_account_*` on the read row only; **and** §9's nine read-only fields | `DEF-RAT-4837`; **`DEF-RAT-9345`** (new) | **the redesign half FIXED** (`8475eafa0`): the guard names §9's read keys as a second pinned set, quoting the contract. Before: red naming 15 keys. After: still red, naming only `gl_account_code`, `gl_account_id`, `gl_account_name` — `DEF-RAT-4837`'s, left to rating |
| `test_po_2026_08_31_discount_rulings.py` ×2 | `c7485bebc`, 2026-09-08 | sewer gained kgal, so BR-RAT-960's unitless case has no fixture | `DEF-RAT-6450` | not fixed — needs a unitless service in the fixture |
| `test_rep_p6w4_plans_and_discounts.py` ×1 | `4f9f8a71a` (first run; born red) | a $2,419.00 payment plan over 6 instalments reads $2,419.0002 remaining | `DEF-REP-8707` | not fixed — payments/reports money display, its owner's |

**Front-end reds the handover carried as "long-standing", re-run 2026-10-03 — all three still red,
none had a row; filed, not fixed (none is a discount screen):**
`ConfirmDialogTier.dom.test.tsx` — 39 dialogs against 38 audited, the extra is `BulkRunPage.tsx`
(*Discard run*, `8b7aee258`) → **`DEF-SHL-9347`** · `wizardRailCensus.test.ts` — the TAX edit form's
three step lists (`taxEditModel.ts`, `b71588e74`, CR-165 task 7) reach no WizardFrame → **`DEF-RAT-9348`**
· `runbooks/blocks/blocks.test.tsx` expects a rate `$8.2900`; since the PO's 2026-10-02 unit-price
ruling (`565e6a831`) it prints `$8.29`, which is now right → **`DEF-RBS-9349`**.

### Every defect this CR filed

| Defect | State |
|---|---|
| `DEF-RAT-9289` New form · `9290` list · `9291` details · `9292` edit | fixed (2.475.0 / 2.478.0 · 2.473.0 + 2.478.0 · 2.480.0 · 2.481.0). **`9290` closed at this close**: it was held open on D15/D17's server half, which 2.478.0 delivered — the built list shows `$25.00`, `15.00%`, *To* `12/31/2026` / *No end* (`walk/discwalk_11_list_en.png`) |
| `DEF-RAT-9293`–`9297` the four lifecycle rulings and the enrolment door | fixed 2.478.0 |
| `DEF-RAT-9308`, `9309`, `9311`–`9314`, `9316` | fixed (2.480.0, 2.481.0, 2.481.3) |
| `DEF-RAT-9318`, `9319`, `9325`, `9326`, `9327`, `9338`, `DEF-BIL-9339`, `DEF-RAT-9340`, `9341` | fixed in the walk (§16) |
| `DEF-RAT-9345` (this task) | fixed, test only |
| `DEF-RAT-9303` second approval · `9310` Duplicate · `9315` unmounted EffectiveStep | **open**, below |
| `DEF-BIL-9346` (this task) | **open, low** — below |

### Still open — each in one sentence, with who has it

1. **Garden: ruled (b), built in 2.488.0 (2026-10-03).** ~~a usage allowance can be created but
   never go live — with the PO~~. The signed rule `BR-RAT-962` keeps a usage allowance
   unpriceable ($2.00 off the money where free units before pricing give $14.40). PO verbatim:
   *"recommend (b) - this is correct"* (decision log 2026-10-03). Built: the New form's *Type* list
   no longer offers *Usage allowance*; the server refuses a NEW one by name
   (`rating.discounts.usage_allowance_not_offered`, eleven languages) — create, a new version, or
   an edit turning a draft into one; a draft already saved stays on the list and its page, opens on
   Edit with the type read-only, and cannot be submitted (details page offers *Edit* only). Nothing
   is priced differently. (a) — building the step — stays a later money change needing a re-sign.
   The walk's *Garden suspends* check is withdrawn (`web-walk.md`, dated note). Photographs:
   `08-qa/discounts-2026-10-03/garden/`. Our three judgments are the decision-log row of the same
   date.
2. **May a waiver take a FEE off? — with the PO.** DEF-388's own example is *"waive the $45.00
   connection fee"* ($104.00 → $59.00). Fees are never discounted today (no signed rule), so such a
   waiver is **refused at Approve** — never silently $0.00 off. **Recommended: keep refusing** until
   a rule is signed.
3. **"Granted this month", an account's "This month" and every yearly cap or budget** —
   `DEF-2430` / `DEF-BIL-5341`, open: no grant is written at issue, so both show a dash and no cap
   or budget ever runs down on real bills (walk 9.3: 0 grant rows after four issued runs; the
   engine half was proved by hand — a $295.00 grant trims Carl's CAP to −$5.00). ⚠ **The walk plan's
   *CAP stops after $300.00* cannot be reached on its own world even after the fix:** the $50.00
   floor holds CAP at $10.00 a month on a $60.00 bill, so a year gives $120.00. The re-walk needs a
   bigger test bill — e.g. $80.00, where CAP gives its full $25.00 and the twelfth month reaches
   $300.00.
4. ~~**Duplicate a discount** — `DEF-RAT-9310`: the button is held~~ **BUILT 2.490.0 (§18).**
5. ~~**Add to / remove from a plan on the discount's own page** — `DEF-478`: held~~ **BUILT 2.490.0 (§18).**
6. **A second approval** — `DEF-RAT-9303`: a discount over the approval threshold still goes live
   on ONE approval (`BR-RAT-077`'s second act was never built; the threshold is off by default).
7. ~~**No CSV on the Accounts and Audit tabs** — `DEF-1005`~~ **BUILT 2.490.0 (§18)** — `?format=csv` on the tabs' own reads.
8. ~~**The bill's *Document* tab** reads *Charged to the bill*~~ — `DEF-BIL-9346` **FIXED 2.490.0 (§18).**
9. **`DEF-RAT-9315`** — `RateScheduleWizard`'s unmounted `EffectiveStep` (rate schedules, not a
   discount screen; G13 names it).
10. **The reds above** that belong to other owners (`DEF-RAT-4670`, `9343`, `4837`, `6450`,
    `DEF-NOT-6267`, `6275`, `9344`, `DEF-REP-8707`, `DEF-SHL-9347`, `DEF-RAT-9348`, `DEF-RBS-9349`).

**Surface debt:** this CR added and removed no story, so no `surface_debt.txt` line moves.

**Version.** The last product build of this CR is **2.481.11** (`f722c6c3c`). This close ships
records and one test file only, so it takes **no version**.

**Rollback.** Each round's own rollback stands as written in its section; nothing in this close
needs one (records and a test). To take the whole redesign out: redeploy **2.477.1** after
`manage.py migrate rating 0058_cr165_tax_chain_constraints_and_rls` (§10 — values a utility added
to the three lists are lost; retirements, enrolments and versions already written stay). ⚠ The
builds between 2.477.1 and 2.481.11 also carry `CR-165-BRC10`'s last fixes (2.479.0, 2.481.2) and
the frame and size-name fixes (2.481.4, 2.481.5), so a whole-CR rollback by build takes those out
too; the narrower route is to redeploy 2.481.10 (undoes only the waiver fix) or each round's own
predecessor.

**`CR-166-BRC10` is CLOSED** at **2.481.11**, with the Garden and fee-waiver questions with the PO
and `DEF-2430`/`DEF-BIL-5341`, `DEF-RAT-9310`, `DEF-478`, `DEF-RAT-9303`, `DEF-1005` and
`DEF-BIL-9346` open against this surface.

## 18 · Follow-up — the four small things (lane DISC-SMALLS, 2026-10-03, `2.490.0`)

PO, of the discounts pending-work table: *"complete these and fix busg"* (decision log *"COMPLETE THESE
AND FIX BUGS"*). Built from images 19–26 (B14 rule 42), our kit deciding the build (rule 44); the second
approval (`DEF-RAT-9303`) stays later, as ruled, and yearly caps/grants are lane DISC-CAPS's.

| Defect | What a clerk sees now | Server |
|---|---|---|
| `DEF-RAT-9310` | More ▾ *Duplicate* (image 23) opens *Duplicate Senior discount*: *Copies every value and condition. No plans, no accounts.*, **Code** and **Bill line label** (both required), *Duplicate* → lands on the new **Draft** | `POST /discounts/{id}/duplicate {code, name}` → `discount_services.duplicate_discount`: the version IN FORCE (else the newest not set aside) through `create_discount`; no dates; GL account copied; no enrolment, grant, plan link or history; Audit *Copied from SENIOR* on the copy |
| `DEF-478` | Plans tab (image 21): *+ Add to a plan* (plan search + **Reason**) and × (danger: *Stops from the next bill. Enrollments on this plan end.* + **Reason**) | `POST /discounts/{id}/plans {plan, reason}`, `DELETE /discounts/{id}/plans/{plan} {reason}` → `services.add_discount_to_plan` / `remove_discount_from_plan`, both through `update_plan` (BR-RAT-037, ruling 2); added from today; reason required; the discount's Audit names the plan and the reason |
| `DEF-1005` | ⤓ on Accounts (toolbar, image 20) and Audit (heading, image 22) | `?format=csv` on `GET /discounts/{id}/accounts` (the same `q`, `f.status`, `f.plan`, sort; the WHOLE set, never a page) and `…/audit` (every row); streamed 500 at a time, no cap (NFR-3, NFR-5) |
| `DEF-BIL-9346` | a bill's Document tab: *Water $60.00 · Discounts −$9.00*; Charges › By service: a *Discounts* row — never *Charged to the bill* | `charges_by_service.bill_level` gains `discounts` and `others` (Σ of the same finalized lines; the bucket unchanged) |

**Found on the walk and fixed: `DEF-RAT-9512`** — SENIOR added to a plan on 10/03 and removed the
same day was DELETED as "never started": Ruth stayed *Receiving* and neither act reached the
discount's Audit. Both branches now end the enrollments of accounts on the plan, and the removal is
written on the discount itself. Red first: `assert None == date(2026, 10, 15)`.

**Closed:** `DEF-RAT-9310`, `DEF-478`, `DEF-BIL-9346`, `DEF-RAT-9512` (fixed in `4bc097773`).
**`DEF-1005` stays OPEN, deliberately:** it is the row for EIGHT lists with no export (disconnects,
move-ins, move-outs, transfers, connections, service requests, templates, and the discounts LIST), and
six of them cite it as their stated absence, so closing it on the strength of the discount page's two
tabs would expire notes that are still true. The two tabs this CR drew a ⤓ for now have one.

**Filed, not fixed:** `DEF-RAT-9513` (low) — an account removed and re-enrolled the same day lists
twice on the Accounts tab, because an enrollment ending today is still current and re-enrolment
looks only for an open one (recommended: re-enrolling reopens that row). `DEF-BIL-9511` (low) —
`test_us_bil_026_tc1` red since `f4257fae8` (2026-10-01): it freezes a bill line's whole key set.

**Our judgments** — decision log *"CR-166 FOLLOW-UP · THE FOUR SMALL THINGS BUILT"* (six, each with
its figure): Duplicate is a server act with two boxes; the copy has no dates; add/remove through the
plan's own save with a reason on both; added from today (Ruth's 11/16–12/15 bill $60.00 − $9.00 =
$51.00); the same-day removal; the bill-level split.

**Tests, each RED on the base first.** Backend `tests/test_cr166_disc_smalls.py` 8 cases (red: no
route — `AttributeError`/405; the CSV — 404; `KeyError: 'discounts'`; `assert None ==
date(2026, 10, 15)`). Front end: `discountDetail.dom.test.tsx` 6 new (the two HOLD cases — *Duplicate
is drawn disabled* and the New-form source check, and *the plan controls are HELD* — are RETIRED,
their holds expired: Duplicate posts and lands on the copy by address; Add/× post their bodies; ⤓
asks for `format=csv` with the table's filters and no page), `CR105DocumentGroups.dom.test.tsx` +2,
`BillChargesTab.test.tsx` +1 (3 red on the base page). `test_def400`'s note for
`attach_discount_to_plan` no longer says DEF-478 is unbuilt. `tsc` clean; vitest rating, billing,
i18n, components, styles: 1 red, dated and owned (`ConfirmDialogTier` — `BulkRunPage`,
`DEF-SHL-9347`). Golden 25 passed 1 xfailed, unchanged. Gates: no red names a file this change
touched (G38's 37→36 is the same on the base).

**Browser walk, PostgreSQL 16, 1440, Dana** — `10-scripts/cr166_disc_smalls_walk.mjs`, **17 of 17
PASS** (`08-qa/discounts-2026-10-03/smalls/results.json`); photographs `s01`–`s13` in the same
folder, each opened; the two CSVs as downloaded (`accounts.csv.txt`, `audit.csv.txt`) and the bill
run (`bill-run.txt`). Ruth's issued bill BL-2612-000115 (11/16–12/15/2026): Water $60.00, Senior
−$9.00, **$51.00**; after the removal it keeps its −$9.00 (hard rule 4).

**Keys:** 11 new in all eleven catalogues (written in each language, B14 rule 35) through
`10-scripts/i18n_fanin.py`; `rating.discountDetail.plans.onThePlan` retired (its hold is gone).

**Version and rollback.** `2.490.0`. Redeploy `2.489.5` to roll back: no migration; the routes and
the two read keys are additive; discounts already duplicated and plan links already changed stay.


## 19 · Follow-up — yearly caps and budgets count down; a bill is never held for a discount (lane DISC-CAPS, 2026-10-04, `2.491.0`)

**The PO's two rulings (decision log 2026-10-04 *"THREE PO ANSWERS"*):** (1) a yearly cap counts the
**calendar year** of the bill's period end — PO *"this is correct 0- $35.00 a month to August ($280.00),
$20.00 in September (the cap is reached), $0.00 Oct–Dec, then $35.00 again from January"*; (2) **a bill is
never held for a discount** — PO *"We cannot hold the bill; we need to make discount value to 0 and move on
- we cannot stop the billing"* — so `BR-RAT-075` "suspend" is SUPERSEDED (stamped in
`06-rating/02-business-rules.md`). This closes §17's open item 3 (`DEF-2430` / `DEF-BIL-5341`).

**Built.** Each discount line carries its programme code from the engine to `invoice_lines.discount_code`
(`billing/0040`); issue asks rating to record one `discount_grants` row per enrolment, against the version
in force on the service date (`rating_seam.record_discount_grants` → `discount_services.record_grants_for_invoice`).
A correction writes a reversing row per grant BEFORE the rebill is priced (`rating/0065`: `reverses_grant`,
one reversal per grant; a PostgreSQL trigger refuses any edit or delete of a grant), and its preview prices as
if the bill had granted nothing. A spent budget is a $0.00 discount for every setting. *Granted this month* and
an account's *This month* read the recorded grants.

**Worked, on PostgreSQL 16, 14 issued runs, an $80.00 bill** (`10-scripts/def2430_caps_world.py`;
outputs in `08-qa/discounts-2026-10-03/caps/`):

| | $25.00 credit, $300.00 cap | $35.00 credit, $300.00 cap | $10.00 credit, $45.00 shared yearly budget (2 accounts) |
|---|---|---|---|
| Dec 2026 | −$25.00 (2026) | −$35.00 (2026) | −$10.00 each (2026) |
| Jan–Feb 2027 | −$25.00 | −$35.00 | −$10.00 each ($40.00) |
| Mar 2027 | −$25.00 | −$35.00 | **−$5.00 each** (what is left) |
| Apr–Aug 2027 | −$25.00 | −$35.00 (Aug: $280.00) | **$0.00, billed in full, nothing held** |
| Sep 2027 | −$25.00 | **−$20.00** | $0.00 |
| Oct–Dec 2027 | −$25.00 (Dec: exactly $300.00) | **$0.00** | $0.00 |
| Jan 2028 | −$25.00 (new year) | −$35.00 (new year) | −$10.00 each (new year) |

All 84 bills issued; the 42 with no cap reached (no discount, Senior 10%, the $25.00 credit) are identical to
the build before. Corrected Dec 2027 ($25.00) and Sep 2027 ($20.00) rebill at the same figures, the
original's grant reversed. The budget overspend in March ($50.00 granted against $45.00, two accounts in one
run) was `DEF-RAT-9367`; **fixed in 2.492.1** — the run shares the budget across its accounts, so March reads
−$5.00 for the first account and $0.00 for the second ($45.00), and both bills go out
(`08-qa/discounts-2026-10-03/caps/after-2.492.1.txt`, which also shows Carl's December bill issuing after his
enrolment was ended back-dated between draft and issue).

**Our judgments (recorded, not asked — law 13):** the exhaustion option *Suspend the discount* stays on the
form and in stored rows — its words already describe the new behaviour (the discount stops, the bill goes
out); a discount line drafted before this build (no programme code) issues and is not counted, reported on the
issue outcome rather than refused; ~~a bill naming a programme the account no longer holds on its service date
stays a draft~~ **reversed in 2.492.1 (`DEF-RAT-9522`): it issues as priced, the grant is counted against
the enrolment that priced it and audited — no discount ever stops a bill**; "this month" is the month of the
bill's period end. Also found and fixed:
`DEF-RAT-9366` (the cap year had no end) and `DEF-BIL-9501` (a discounted bill could never be corrected).

**Version and rollback.** `2.491.0`. Redeploy `2.490.6` and roll back `rating 0065` / `billing 0040`; after any
correction has reversed a grant, leave the migrations applied and roll back the code only.
