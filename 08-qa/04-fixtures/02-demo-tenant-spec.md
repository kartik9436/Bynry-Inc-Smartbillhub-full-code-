# The demo tenant — what a seeded utility must look like

**PO ruling 2026-08-16, amended the same day.** The Product Owner will **create a
NEW TENANT through signup**, load this, and drive the product themselves. That is
the acceptance test, and it is the first one in this project no gate can fake.

> *"I dont have to do this - Drop and recreate the database; I can create a new
> Tenant and test it"*

**That is the better route and it is non-destructive** — it exercises the real
path a customer takes, signup included, rather than a path only an engineer ever
walks.

⚠ **BUT IT LEAVES ONE THING TRUE, and it must be said before the PO is surprised
by it: EXISTING TENANTS STAY BROKEN.** Provisioning-time seeding reaches a tenant
at the moment it is created and never afterwards — the same law that means
editing `.env.example` fixes nothing already deployed. `silver-creek-water` has
no bill template and no sample data today, and a new tenant getting both changes
nothing about it. **So: test on a new tenant, and expect the old one to stay
empty until a repair is run against it.** A one-command repair exists for the
bill template; the sample-data equivalent must be built with the seeders, or
every tenant created before today is permanently un-demoable.

> *"if we are able to seed the data refernece as well as transaction data, then
> we can test the application end to end and see what are the issues; thiswill be
> human checking"*

**This file is the specification the eight `seed_sample_records` seams build to**
(DEF-153: the orchestrator, the panel and all eight seams exist and not one
module implements them, which is why a new tenant is empty today).

---

## The governing principle

**A tidy fixture proves nothing.** Ten clean accounts that all pay on time
exercise the happy path and hide every case a real clerk spends their day on.
The point of this data is to make problems VISIBLE — so it deliberately contains
the awkward states: an unreadable meter, a disputed read, a cheque that bounced,
a customer who paid half, one who moved out mid-cycle, one who is 70 days late.

**Equally: it must not pre-complete the product's own work.** July and August
are left UNBILLED on purpose (July READY-TO-RUN — amended 2026-08-17, CR-010
Part-10.4; it read "August" alone until then), so the PO can run a billing run
themselves and watch it work. A fixture that arrives with everything done
leaves nothing to evaluate.

---

## 1 · The utility

**Silver Creek Water** — a small municipal water utility. Three services, which
is the commonest real shape and exercises cross-service billing without needing
six:

| Service | Priced as | Note |
|---|---|---|
| **Water** | Tiered — 3 tiers | The engine has tiered; this works today |
| **Sewer** | **Percentage of water** | ✅ **AMENDED 2026-08-16 — IT LANDED, AND SEWER IS SEEDED AS A TRUE PERCENTAGE.** `apps/rating/pricing/models/percent_of_service.py` shipped the same day and the Product Owner ratified its figure: **sewer is 40% of the water USAGE charge — $15.80 on $39.50 — deliberately NOT counting the $8.00 base, which would give $19.00** (BR-RAT-015, GT-17 ❄️). The old sentence said *"until it lands, seed sewer FLAT and say so on the plan"*; it has landed, so it is not seeded flat |
| **Trash** | Flat monthly | Fixed charge, no meter |

**Why not electricity:** time-of-use pricing does not exist yet. Seeding an
electric plan the engine cannot price would produce a tenant that cannot be
billed — the exact failure this fixture exists to avoid.

## 2 · Reference data

| | Count | Shape |
|---|---|---|
| Streets | **5** | Named, so the premises list is navigable and by-premises grouping means something |
| Premises | **44** | Mixed: 36 single-family, 2 duplexes, 1 small apartment block of 6 units, 2 commercial, **and 3 newly platted with no unit yet**. ⚠ **THE ARITHMETIC, WRITTEN DOWN 2026-08-16 so the next reader does not rediscover it:** 44 premises and 48 units means units exceed premises by 4. One 6-unit block contributes +5 on its own and two duplexes +1 each, which is +7 — so with the stated mix the two headline counts cannot both hold. Three premises are therefore seeded with NO unit yet, which is a real state of a growing utility and makes both numbers true |
| Units | **48** | The apartment block is why units exceed premises |
| Meters | **48 + 1** ⚠ *was 96* | **AMENDED 2026-08-16, and the reason is the sewer amendment above.** 96 was *"water + sewer per unit"*, written while sewer was still going to be FLAT and therefore metered. A sewer line priced as 40% of the water usage charge **reads no register at all** — it derives from water. 48 sewer meters nobody ever reads would put 48 phantom missing-reads into every bill run and bury the THREE deliberately unreadable meters this spec asks for, which is acceptance item 8. So: **one water meter per unit (48), plus the one replacement** case 3 needs, and trash has none. One meter **replaced** mid-history, so a read chain crosses two serials |
| Sub-meters | **6** ⚠ *added 2026-08-17* | **CR-010 Part-10.4 (PO: *"please add sub meter and few bhend the meter devices"*)** — one per apartment unit, each parented on that unit's own water meter (BR-AST-003), so the S49 `Sub-meters` tab has rows. Deliberately NEVER READ: they share the unit's existing water service point, so the parent's committed read keeps satisfying the bill run and the ready-to-run July gains no phantom missing-reads |
| BTM devices | **3** ⚠ *added 2026-08-17* | Same ruling — a **backflow preventer** on the laundromat's connection (12-month test interval, BR-AST-027), a **solar inverter** and an **EV charger** on two houses, from the seeded `asset_types`/`device_types` vocabulary. Non-measuring: no service, no UoM, so a water-only tenant holds them lawfully |
| Sample staff users | **2** ⚠ *added 2026-08-17* | **CR-010 new mandate 1 (PO: *"along with member login i will create 2 new sample users"*)** — a Billing Clerk and an Executive, invited and UNCREDENTIALED (temp passwords discarded unread; the owner stays the only login), on the clearly-sample `@sample.test` domain |
| Payment plan | **1, LIVE** ⚠ *added 2026-08-17* | **CR-010 Part-10.4 amendment 3 (PO: *"you did not cover outstanding repcrds, payment plans"*)** — case 6 stops being narrative: the plan account's June bill is left wholly unpaid, the S24 wizard path spreads it (20% down, 4 biweekly instalments — schedule math is BR-CUS-043's/GT-47's), the customer's e-signature activates it, 2 instalments are PAID on their due dates and the next is due — genuinely mid-schedule against the mid-August "today" |
| Rate plans | **2 of 3** ⚠ | Residential · Commercial. **The SENIOR plan is NOT seeded and that is OQ-240, minted 2026-08-16:** no signed figure states its discount, anywhere, and rule 7 below forbids choosing one (*"the seeder stubs and mints a question rather than choosing a number that then looks official"*). The two that DO seed are structurally different from each other — inclining tiers against a flat rate — which is what a third plan was there to give: something to compare |
| Tax authorities | **2** | State + city, at different rates, so the remittance report has more than one row |

**Chart of accounts, number series, holidays** already seed at provisioning —
this fixture must not duplicate them.

## 3 · Transaction data — three months

> ⚠ **AMENDED 2026-08-17 — CR-010 Part-10.4 (PO verbatim: *"do 1 month billed
> na dkeep other month ready"*).** The table below SUPERSEDES the 2026-08-16
> one, which read "June and July are BILLED and mostly PAID". One month is
> billed; the next is **READY-TO-RUN** — reads staged and committed, nothing
> billed — so the trial's FIRST bill run is July on prepared data, and August
> waits behind it for a second. The superseded "July ~80% collected" clause
> fell with July's billing. The 70-day past-due case (§4 #8) is unchanged: its
> ageing always came from the unpaid JUNE bill.

> ⚠ **REVERSED AGAIN 2026-08-27 — CR-040 (PO verbatim: *"I want you to complete
> 2 billing cycle and create data for 3rd billing cycle"*).** The 2026-08-17
> amendment above is SUPERSEDED: **two months are billed, the third is staged.**
> Both banners are left standing because a reader needs to see that the count
> moved twice and by whose instruction — the first ruling and this one have the
> same author.
>
> ⚠ **THE INTENT OF THE OLD RULING SURVIVES INTACT.** *"everything done leaves
> nothing to evaluate"* is why a period was left unbilled, and acceptance item 4
> is *"run the August billing run"*. **August is still the PO's own run.** What
> changed is that the estate reaching it now carries a real financial history —
> a credit, a refund and a correction written BETWEEN the two runs — instead of
> one billed month and a blank.

> ⚠⚠ **THE MONTH NAMES BECAME A SHAPE ON 2026-09-25 — `DEF-LED-6640`. NOTHING
> IN THIS SECTION CHANGES EXCEPT WHICH MONTHS IT LANDS ON.** `core/sample_fixture.py`
> held this calendar as `date()` CONSTANTS, so from 1 September every
> period-scoped Finance screen read **`$0.00`** on a database holding 80
> invoices, 66 payments and 167 journal entries. The screens show the CURRENT
> accounting period (`BR-TEN-022`, computed never stored) and there is **no
> period picker** to move off it, so nothing was broken and nothing was lying:
> the money was in a month the screen cannot show. **A demo fixture pinned to
> fixed months has an expiry date nobody wrote down.**
>
> **So read the table below as three positions, not three months** — the whole
> calendar is shifted by a whole number of months at seed time so that **today
> always falls inside the third one**:
>
> | position | canonically | what it is |
> |---|---|---|
> | **M-2** | June | billed, ~95% collected, period closed |
> | **M-1** | July | billed, uncollected — the refund, the credit, the correction |
> | **M** | August | **READ AND UNBILLED — the PO's own run. Today is in here.** |
>
> ⚠ **THE UNBILLED MONTH SURVIVES, AND THAT IS THE POINT OF SAYING THIS HERE.**
> Travelling the calendar bills **nothing** new — the third position is still
> unbilled, and acceptance item 4 is still *"run the August billing run"*, now
> meaning *this month's*. *"Everything done leaves nothing to evaluate"* is
> untouched.
>
> ⚠⚠ **THE INVARIANT IS THE SERVICE PERIOD, NOT THE `BILLED THIS MONTH` TILE —
> THIS BANNER SAID *"BILLED THIS MONTH is still `$0.00` on purpose"* AND IT IS
> WRONG.** Measured in a browser on the first tenant seeded this way
> (2026-09-25, `2.351.86`): the tile reads **`$15,734.17`**, over its own words
> *"Posted between 2026-09-01 and 2026-09-30"*. It counts by **posting date**;
> the acceptance test is about the **service period**. On the same tenant,
> **0** bills cover a September service period, **45** posted in September and
> every one of them covers 2026-08-01 to 2026-08-31 — bill run 2 going out on
> the 2nd, as this fixture has always issued it — and **117** September reads
> sit committed, waiting for the run the Product Owner makes. The `$0.00` was a
> symptom of the defect, not a property of the design.
>
> ⚠ **THE KEYS ARE STILL `june` / `july` / `august` AND THEY ARE IDENTIFIERS,
> NOT MONTH NAMES.** 37 files ask the fixture for `august` meaning *the open
> one*; renaming them would move every citation at once for no gain. A reader
> meeting `august` in code on a tenant seeded in February is looking at
> February.
>
> ⚠ **AN ALREADY-SEEDED TENANT DOES NOT MOVE AND CANNOT.** Hard rule 4 makes
> issued invoices, payments and journal entries append-only, so the calendar
> travels for a tenant seeded **from now on**; an old one is re-dated by
> re-seeding a fresh tenant, never by mutation. `10-scripts/seed_finance_current_period.py`
> remains the tool for putting cash into the open period of a tenant that
> already exists.

**JUNE and JULY are BILLED. June is mostly PAID. AUGUST is READ and READY-TO-RUN
— it is the PO's own first run and it is left undone on purpose.**

✅ **BUILT — 2026-08-27.** This paragraph said *"NOT YET BUILT — CR-040 is
CAPTURED, not sized … `_periods_to_bill()` still returns June alone"* and was
true when it was written. It is stamped rather than deleted, because a reader
arriving at a table that used to be a TARGET is entitled to know which it is
now. **Wave C** split the billing block in two, so `_periods_to_bill()` returns
the FIRST cycle and `seed_sample_second_cycle` bills July. **Wave D** wrote the
refund and the overcharge correction into the gap between them (cases 14 and 15
below). What is still owed on this CR is **wave B** — opening balances on
several accounts, and the master account's sub-accounts — which the table's
`Payments` row does not depend on.

| | June | July | August |
|---|---|---|---|
| Reads | complete | complete | **complete — awaiting billing** |
| Billing run | **issued** | **issued** | **none — the PO runs this** |
| Payments | ~95% collected | partial — and it is where the refund, the credit and the overcharge correction live | — |
| Period | **closed** | open | open |

⚠ **THE ORDER IS THE REQUIREMENT, not the contents.** The PO's own sequence:
*"first you will run first billing, then you will create payment record,
refunds, credit over charges records, add meter reading for second month and
then again run the billing"*. A refund written after both runs is a row; a
refund written between them is a **history**, and only the second one bills
differently. An overcharge correction cannot exist before run 1 at all — it
corrects a bill that has issued.

⚠ **NO CRON, NO SECOND WORKER.** A bill run is an inline service call
(`apps/billing/runs.py`: *"It runs INLINE. There is no job runner in this
project"*), and the seeder already drives all five phases through the doors S31
uses. Two cycles is a second pass of a loop that exists — one background job,
two sequential runs. Celery's job here is the seed itself (CR-017), so signup
returns immediately; beat is deliberately unconfigured.

## 4 · The awkward cases — the reason this fixture exists

Every one of these is a real thing a clerk deals with, and each exercises a
different part of the product. **Roughly one account in four is interesting;**
the rest are ordinary on purpose, so the interesting ones stand out.

| # | Case | What it proves |
|---|---|---|
| 1 | **3 unreadable meters** in August | Estimation — the screen built today |
| 2 | **1 disputed read** | The dispute flag actually renders, instead of a counter stuck at zero |
| 3 | **1 meter replaced** mid-history | A read chain that crosses two serials still totals correctly |
| 4 | **2 partial payments** | Allocation order: usage+base → tax → fees last |
| 5 | **1 bounced cheque (NSF)** | Reversal, the fee, and the account flag |
| 6 | **1 account on a payment plan** | Instalments reach the plan first — the ruling of 12 Aug |
| 7 | **1 write-off awaiting approval** | The approval queue has something in it |
| 8 | **1 account 70 days past due** | The collections ladder shows a real tier, and 60+ ageing is non-zero |
| 9 | **1 final bill** — moved out mid-July | Proration, deposit settlement, closing balance |
| 10 | **1 new account** — moved in mid-July | Proration the other way |
| 11 | **1 credit balance** from an overpayment | A negative-owing account renders sanely. ⚠ **NOT TRUE OF THE SEEDED TENANT SINCE 2026-08-27 — DEF-931.** Measured block by block: the account holds **$17.08** immediately before the second billing block and **$0.00** after the load. Nothing is broken — `apply_credit_at_issue` (BR-PAY-010) spends a carried credit on the next bill that issues, and wave C made July a bill that issues — but the fixture no longer demonstrates this case. The fix is this case's own overpayment figure (about 2.2× rather than 1.25×, so it clears July as well as June), which moves the stated ~95% collection rate and is a demo-shape judgment rather than a lane's call. Pinned as an `xfail(strict=True)` in `tests/test_cr040_wave_d_money_between_cycles.py` so it cannot be quietly fixed either |
| 12 | **1 goodwill credit** | The concession path |
| 13 | **1 account with 2 units** (landlord) | One customer, several accounts |
| 14 | **1 refund** ✅ *built 2026-08-27, CR-040 task D12* | Money going OUT. Every case above moves money in or holds it; **nothing in this fixture had ever paid a customer back**. Now one account overpays its June bill and asks for the surplus, and all four steps run through `apps/payments/refunds.py` — requested, approved, issued (the only one that posts: DR customer credit / CR cash) and cleared at the bank. ⚠ **It is NOT case 11's account.** A refund CONSUMES a credit and case 11 exists to show one being CARRIED, so refunding case 11 would have replaced a case rather than added one. The AMOUNT is the allocator's own credit figure read back after the overpayment — never a number typed here |
| 15 | **1 overcharge, corrected** ✅ *built 2026-08-27, CR-040 task D13* | The corrections engine (`EP-BIL-04`) runs against a bill that has already issued: `open_case` → `approve` → `execute`, mechanism **restatement**, so the June bill is credited in full and a rebill is issued for the corrected amount. Written between the two runs, so the second cycle bills an account that has been corrected. ⚠ **`BILLERR` IS NOT THE REASON THIS USES, and this cell said it was.** There are TWO unrelated reason vocabularies: `BILLERR` is a tenancy `reason_codes` row and the corrections engine never consults it — the engine carries its own in `apps/billing/correction_reasons.py`, and this case is `wrong_read` (class R). BILLERR's own unused-ness is real and belongs to DEF-891. ⚠ **The READING is corrected first**, through metering's `correct_billed_read` (BR-MET-053's only door for a billed read): a restatement RE-PRICES from today's inputs, so a case with nothing changed underneath it moves $0.00 |
| 16 | **Opening balances on SEVERAL accounts** ⚠ *added 2026-08-27, CR-040* | Today exactly one account of 48 carries one (`A-12103`, 267.30 across four aged buckets). A utility that migrated last month has a page of them, and the ageing report needs more than one row to be a report |
| 17 | **1 master account WITH its sub-accounts, on one consolidated bill** ⚠ *added 2026-08-27, CR-040* | A master exists (`500 Main Street`, 25 units) and has **no children**, so the `Master` pill renders over nothing. ⚠ **Its sub-accounts must be CURRENT** — `OQ-366` (does the ladder chase the departed tenant or the master?) is open, and a seeded sub-account carrying unpayable residue would answer it by existing. The structure is unruled only where the ARREARS are |

## 5 · Money in — so the finance screens have work

**One busy day (8 August) with mixed methods**, so deposit batches and bank
reconciliation have something real to group:

- cheques · cash · card · ACH, several payments each
- **a bank statement to import**, in which:
  - the cheque batch matches exactly,
  - **the card day does NOT match** — the processor kept a fee, which is the
    exception a clerk must explain against the bank-fee account,
  - one line is bank interest belonging to nobody.

## 6 · Finance state

- June **closed**; July and August open.
- A trial balance that **foots** in every open period.
- Journal entries posted for every issued bill and every payment.
- One accrual, so its reversal has something to reverse.
- **Nothing exported yet** — the PO should be able to run the first export.

---

## 6a · The customer portal — added 2026-09-07 by PO ruling (`CR-082`)

PO verbatim: *"before step 29 this - you ahve to set all the self service data
in settings -> configure -> Customer portal - {overview, branding, Help &
Answer, Tips  + service centers }"*, where step 29 is *"a customer who can sign
into the portal"*. **The order is part of the ruling** — a customer who signs in
to an unconfigured portal sees branding that is not there, no answers, no tips
and no counter to walk into.

What a seeded tenant carries, and every figure is checkable by hand:

- **The portal is LIVE**, with Quick Pay, Plans, Requests and Outage reporting
  on and **Self-read off** — the one switch that is deliberately off.
- **Branded**: a strapline, the utility's OWN services as front-page chips
  (whichever it ticked at sign-up, so a water-only utility gets one chip and a
  four-service utility gets four), office hours and an emergency number.
- **8 help answers**, six published, one draft, one not shown, in eleven
  languages — **88 variants**, one of them deliberately untranslated so the
  fallback is demonstrable.
- **4,365 `help_answer_feedback` rows**, because *read this month* is a real
  `COUNT(*)` and not a stored number.
- **6 tips on six screens**, one of them off AND out of season, so the portal
  home correctly shows no tip container at all.
- **3 service centres**, one hidden from customers, with **21 rows of opening
  hours** between them — a counter with no hours is not a counter a person can
  walk into.
- **1 portal login**, on the lowest-numbered SAMPLE account that is linked to a
  customer and holds an email. ⚠ **It is never a real customer's account**: the
  chooser requires `is_sample = true`, which is what lets the demo password be
  written in the open in `apps/portal/sample_data.py`.

⚠ **THE SETTINGS ROW IS WRITTEN ONLY WHEN THERE IS NONE.** A utility that has
opened Settings → Configure → Customer portal once owns that row, and a replay
or a per-block retry leaves every value it typed alone.

---

## Rules the seeder must obey

1. **Every figure obeys signed money law.** B4 and B5 are ❄️ frozen. If a
   worked figure here would contradict one, the FIXTURE changes, never the law.
2. **Money is `NUMERIC(18,6)` + `CHAR(3)`.** Every seeded amount carries its
   currency.
3. **Consumption always carries its unit.** Water in kgal, never a bare number.
4. **Seed through the services a clerk's click uses**, never by writing rows
   directly. A fixture built by direct insert proves the tables exist and proves
   nothing about the product. This is how a lane once seeded every unit onto a
   *water-only Small Commercial* plan — a wrong-cohort fixture that would have
   passed.
5. **Remove must work as cleanly as load.** A demo a utility cannot clear is a
   demo they will run once.
6. **Idempotent.** Loading twice does not double anything.
7. **Nothing is invented.** Where a rule is unsigned, the seeder stubs and mints
   a question rather than choosing a number that then looks official.

## What the PO should be able to do, unaided, when this loads

1. Sign in and see a dashboard with **real figures** — not zeroes, not dashes.
2. Open Accounts and see 48, with balances, ageing, and the past-due one obvious.
3. Open a bill and read it — lines, tax, total due, previous balance.
4. **Run the August billing run** and issue it.
5. Record a payment against it.
6. Cut 8 August's takings into deposit batches, import the statement, explain the
   card fee, reconcile.
7. Open Finance and see a trial balance that foots, then close July.
8. Find the disputed read, the estimated reads, the account in collections.

**If any of those eight cannot be done, the fixture is not finished** —
regardless of how many rows it wrote.

---

## MEASURED AGAINST THAT LIST — 2026-08-16, on a live Postgres (seedfix lane)

Clean database → `migrate` → `seed_demo` → the S8 Services toggle for sewer and
trash → `manage.py load_sample_data --tenant brazosbend`. **557 rows, every block
loaded.** Counted with SQL afterwards, not read off the panel:

| | |
|---|---|
| `invoices` | **93 issued**, zero draft |
| `payments` | **80**, across cheque · cash · card · ACH |
| `journal_entries` | **173** (626 lines, debits − credits = **0.00**) |
| August reads | **45 committed and NOT billed** — 0 billed |
| a second load | **0 rows written** |
| `--remove` | **56 rows removed**, the rest RETAINED BY NAME (issued bills and payments are append-only, hard rule 4) |

**The first bill, in full:** water base 8.00 · water usage 5 kgal × 4.00 = 20.00
· 3 kgal × 6.50 = 19.50 · **sewer 15.80 (40% of 39.50 — B5 GT-17 ❄️)** · tax
3.96 + 1.27 → **subtotal 63.30, tax 5.23, total 68.53 USD.**

### The eight items, one by one

| # | | State |
|---|---|---|
| 1 | dashboard with real figures | ✅ **the figures exist** — 48 accounts, 93 issued bills, 80 payments, a balanced ledger. Whether each dashboard tile reads them is the surface lanes' question, not the fixture's |
| 2 | 48 accounts with balances and ageing | ✅ 48 accounts, **47 carrying bills**; one is held from billing by its disputed read (case 2, working as the rule says) |
| 3 | open a bill and read it | ✅ lines, tax, total — quoted above |
| 4 | **run the August billing run** | ✅ **left undone on purpose** — August is read and unbilled, 45 reads waiting |
| 5 | record a payment | ✅ 80 already recorded through `record_payment`, so the screen has real bills to pay against |
| 6 | deposit batches, statement import, the card fee, reconcile | ⚠️ **HALF, since 2026-09-23 (`DEF-PAY-6321`) — the BATCHES are seeded and the STATEMENT is not.** The busy day's cash and cheques are taken into a counter till that opens, takes the money and is counted and sealed, so Finance → Deposits holds real `DEP-` batches footed at their members' sum, grouped one till × one tender (`BR-PAY-025` as amended 2026-09-22). **Card and ACH money is deliberately in NO batch** — only a hand tender reaches a drawer (PO 2026-09-23 §3.4) — so the Payments list shows both answers instead of one. The statement, its card fee and the reconcile step are still ❌, named in `apps/payments/sample_data.py::NOT_SEEDED` |
| 7 | trial balance that foots, then close July | ⚠️ **the journal foots (0.00 across 626 lines)**; closing July is the ledger surface's, untested by this lane |
| 8 | the disputed read, the estimated reads, collections | ⚠️ **the disputed read is real and holds its account**; the 3 unreadable August meters are absent rather than estimated (45 reads on 48 units), which is what the estimation screen is FOR |

### Still not true, and each is filed rather than left to be discovered

* **Trash never reaches a bill** — $18.00/account/month, **$1,728.00** across the
  demo. Its tariff prices consumption and its service point has no meter, and no
  signed rule covers that: **OQ-246**.
* **`bill_runs.status` still reads `draft`** after every bill on the run issued —
  **DEF-171**.
* **Sample reads cannot be removed** — the immutability trigger has no
  `is_sample` exception — **DEF-162**.
* Five of spec §4's money cases (bounced cheque, payment plan, write-off,
  goodwill credit) and all of §5 are named in `NOT_SEEDED`, not silently absent.

---

## 7 · THE SECOND TENANT — a sub-metering company (CR-060 T3, added 2026-09-01)

**Everything above describes ONE demo tenant and it is a utility.** `CR-060` §11
names that as the gap that blocks two of its three "must" changes, in its own
words: *"C8 and C9 are the sub-metering variants and nothing in the fixtures can
exercise them. Before either can be tested, the demo spec needs a second tenant
that is a sub-metering company: a master account, several buildings, member
accounts under each, and a supplier invoice per building."*

**HALF OF THIS IS BUILT AND HALF IS SPECIFIED.** The pytest fixture exists —
`06-backend/tests/sub_metering_fixtures.py` — and it is what unblocked C9's
tests. **The SEEDER's second tenant, the one a person clicks through, is
this section and is NOT built**: building it means the eight
`seed_sample_records` seams (`DEF-153`), which is not a fixture task.

### 7.1 · The company

**Bayou Bend Submetering LLC** — a sub-metering company reselling water inside
apartment buildings it does not own the supply for. **Water only**, which is
what a sub-metering company usually resells, and enough to make the point
without needing three tariffs.

Its organisation type is **`sub_metering`** (BR-TEN-1050), set through Settings →
Company → Profile like a human would set it — never by writing the column. That
one field is what C8's tiles and C9's grouping read.

### 7.2 · Why its shape is different from Silver Creek's, and it is not size

**A utility asks "how much did we sell and who owes us".** A sub-metering
company asks **"I already paid the city for this building's water — did I get it
back from the members?"** Same books, different question, and the fixture has to
make the SECOND one answerable:

| | Silver Creek (§1) | Bayou Bend |
|---|---|---|
| Buys from | nobody — it IS the utility | the city, **per building**, at a master meter |
| The figure that matters | collection rate, DSO | **recovery per building** |
| A missing volume costs | one service's figure | **one BUILDING's figure, and nothing else** |

### 7.3 · The data, and every figure is checkable by hand

Water is bought at **$3.10 per kgal** — LE-11's own bulk-water price, reused so
no rate is invented here.

| Building | Bought | Cost | Billed | Unaccounted for |
|---|---|---|---|---|
| **1400 Cypress Court** | 600,000 gal (2 invoices) | $1,860.00 | 570,000 gal | **5.00%** |
| **88 Magnolia Row** | 400,000 gal (1 invoice) | $1,240.00 | 320,000 gal | **20.00%** |
| **3 Sabine Lofts** | 250,000 gal (2 invoices, **one with no volume**) | $775.00 | 237,500 gal | **ABSENT** |
| | | **$3,875.00** | | |

    Cypress:  (600,000 − 570,000) / 600,000 = 30,000 / 600,000 = 0.05 → 5.00%
    Magnolia: (400,000 − 320,000) / 400,000 = 80,000 / 400,000 = 0.20 → 20.00%

Two member accounts inside each building, billed an even share of that
building's water, plus **one master account** for the owner/manager carrying no
usage of its own — a master is an ordinary account with `kind='master'`
(BR-CUS-068), not a parent, so nothing rolls up into it and a master carrying
volume would double-count the building's billed side.

### 7.4 · The two awkward cases, and they are the reason the fixture exists

**MAGNOLIA ROW IS A LEAK AND IT MUST BE FINDABLE.** Blended across the three
buildings the same month reads **9.80%** — a figure that describes none of them
and points at no address anyone can go to. Per building, Magnolia is **20.00%**
and is the first row. That difference is the whole of `CR-060` C9.

**SABINE LOFTS IS MISSING A VOLUME ON PURPOSE.** Its second invoice
(`SB-2607-0038`, $310.00) is captured with no quantity, so the all-or-nothing
rule suppresses Sabine's percentage and names the count — *"no volume captured
for 1 of 2 water purchases this period"*. **It protects two numbers.** Sabine's
partial denominator would read `(150,000 − 237,500) / 150,000 = −58.33%`, a
building that delivered more water than it bought. And under the OLD
tenant-wide rule that one missing figure suppressed water for **all three
buildings at once** — which is exactly the scope BR-LED-031 moved on
2026-09-01.

### 7.5 · What this section deliberately does NOT ask the seeder for

* **No `paid_on` and no posting.** Capture still posts nothing (BR-LED-028,
  `OQ-200` ruled 2026-08-16). `CR-060` C1 / T6 changes that and needs a recorded
  ruling first; seeding data that anticipates it would answer a question the
  Product Owner holds.
* **No second bill run.** The billed side is what a run leaves behind, and the
  fixture builds it the same way `tests/test_us_led_020_reconciliation.py`
  already does, for the reason written there: driving a full run makes a failure
  in the LEDGER's reconciliation indistinguishable from a failure in billing.
* **No forty buildings.** Three is what proves a per-building denominator, an
  absent case and an ordering. Forty proves nothing three does not and makes the
  arithmetic above uncheckable by hand, which is rule 7's *"nothing is
  invented"* one step out: a fixture nobody can verify is a fixture nobody
  trusts.
