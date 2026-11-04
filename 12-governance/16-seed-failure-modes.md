# 16 · The seed failure-mode map — what breaks if a seeded thing is missing, and what we do about it

**Deliverables (b) and (c) of CR-010 item 11.** The Product Owner's words, verbatim
from `11-change-requests.md`:

> *"Im looking for solution on seeding data and want to fix it permanantly; this is
> one of the importnat capabilities when you want to enable self service fucntion
> for Smaller utilities; without settingd ata correctly it will not work adnd it is
> very time consuming; … i would like to see the process also; what if some data
> does not get seed in does process down the line breaks down we need to be sure;
> what siwll be fall back"*

Two things are answered here, one row per seeded object:

* **(b) the failure mode** — what actually breaks downstream if the object is
  missing. Not asserted: **read out of the code that consumes it**, and where the
  live database disagreed with the code, the live database wins and says so.
* **(c) the fallback** — one of **refuse-with-reason**, **code-constant fallback**,
  or **repair command**, named per row. Where there is none, the row says *none*.

And the rule that makes it worth doing, which is the PO's own:
**any object whose absence fails SILENTLY is a defect by definition.**

---

## 0 · Read this first — the four numbers

| | |
|---|---|
| **Objects mapped** | **58** |
| **Loud** — the product refuses and names the missing thing | **28** |
| **Stated** — the product carries on, and says out loud that it did | **17** |
| **SILENT** — the product carries on and is wrong, and nothing says so | **13**, in **9** distinct findings |
| Measured at | build **2.19.0**, seed fixture **V2.18.0.0**, commit `dda3f84`, 2026-08-18 |
| Measured against | the running `sbh_e2e` database, tenant **Brazos Bend Utilities** (`brazosbend`) |

**The thirteen silent objects — nine distinct findings — are in Part 7.** They are the
whole reason this document exists; everything above them is the evidence that the
other 45 are fine.

---

## 1 · How this was measured, so the next person can re-run it

Three passes, in this order. Nothing here was taken from an earlier draft — an
artifact reviewed on 2026-08-17 carried an eight-row version of this analysis at
build 2.11.0 and seed fixture V1.0.0.1, and **every figure in it is now stale**
(charge codes were 6, they are 25; units of measure were 6, they are 26; the chart
of accounts was partial, it is now the full 33 for every tenant; four services had
a row, now all ten do). Re-measure; do not copy.

**Pass 1 — what provisioning actually writes.** Read `provision_tenant` and
`_provision_inside_context` in `06-backend/apps/tenancy/services.py` line by line
and write down every INSERT, in order. Then read `SAMPLE_MODULES` in
`06-backend/apps/tenancy/sample_data.py` for the sample set planted after the
transaction commits. **Count from the code, never from a document.**

**Pass 2 — find the consumer and read it.** For each object, grep the whole backend
for what reads it, open the reader, and answer one question: *when the row is
missing, does this function raise by name, substitute a constant, return an empty
list, or produce a number?* A function that returns `None` and lets its caller
carry on is the shape that hides.

**Pass 3 — ask the live database.** This is the pass that pays. A code branch can
look correct and never execute; the only way to know is to count rows. The queries
that found things here were all of this shape:

```sql
select coalesce(<the pointer column>::text,'NULL'), count(*) from <table> group by 1;
```

Run against `sbh_e2e` as role `smartbillhub`. **Read-only. SELECTs only** — other
work depends on that database. Every "live:" figure below came out of it.

---

## 2 · Before any tenant exists — the platform rows (6 objects)

These are planted by migration, once, for the whole installation. If one is missing,
signup itself fails.

| # | Object | Live today | What breaks if absent | Class | Fallback |
|---|---|---|---|---|---|
| 1 | **The ten utility services** (Electric, Water, Gas, Sewer, Trash, Storm water, Solar, Broadband, Thermal/Heat, Battery) | 10, all active | Signup cannot validate the services the operator picked; a service the catalogue does not carry is refused as not-found and no tenant service row is created for it | **Loud** | Repair: re-run migrations. It is a closed catalogue — a tenant can never add to it |
| 2 | **The four account types** (Residential, Commercial, Industrial, Municipal/Government) | 4 | `accounts.account_type_id` cannot be null — no account can be created at all | **Loud** (the database refuses) | Repair command: `seed_demo --tenant <sub>` restores a deleted row |
| 3 | **The three subscription plans** | 3 | Every signup fails; this once took a live deployment down | **Loud** — the demo seeder raises and names the migration | Repair: re-run migrations |
| 4 | **The three staff roles** | 3 | The owner's membership row cannot be written, so the whole provisioning transaction rolls back and no half-tenant exists | **Loud** | Repair: re-run migrations |
| 5 | **The nine permissions** | 9 | The permissions matrix screen renders empty. Enforcement itself does **not** break — the guard on every service function reads a code constant, not this table | **Stated** | Code-constant fallback (enforcement); the screen is cosmetic |
| 6 | **The platform seed file** (`lookup_defaults.json`, version V2.18.0.0) | present | Missing or corrupt → the **entire provisioning transaction rolls back**. Deliberate: half a vocabulary is worse than none | **Loud** | None needed — it ships in the image |

---

## 3 · What one signup writes — the provisioning transaction (16 objects)

All of this is **one atomic transaction**. If any of it fails, no tenant exists at
all — there is no half-provisioned state to clean up. That is the single most
important safety property in this whole map.

| # | Object | Live today | What breaks if absent | Class | Fallback |
|---|---|---|---|---|---|
| 7 | **The tenant row** | 1 | Nothing else can exist | **Loud** | — |
| 8 | **Owner login + membership** | 3 users, 3 memberships (owner + 2 sample staff) | Written **first**, on purpose: if the login cannot be created the tenant must not exist | **Loud** | — |
| 9 | **Owner session** | — | Optional. No session means the owner signs in at their own address instead of landing signed-in | **Stated** | Code fallback: sign in normally |
| 10 | **Trial subscription** (14 days) | 1 | No trial end date; billing-for-us questions unanswerable | **Loud** | — |
| 11 | **Regional settings** — timezone, country, language, date format, number format, 12-hour clock, week starts Sunday, fiscal year 1 Jan, monthly close on the last day | 1 row | Until 2026-08-17 eleven of these were left blank and a month could not be closed until a human opened the tab. Now seeded. If the row were absent, closing a fiscal period refuses by name | **Loud** | Repair by **screen**: Settings → Company → Regional |
| 12 | **Number series** — 22 of them (bill, payment, receipt, account, premises, unit, journal entry, deposit batch, export batch, and 13 more) | 22 | The thing being numbered **cannot be created**. This was real: manual journal entries posted with **no number at all** on every tenant, because the journal series was missing from a hand-typed list. The list is now derived from one source so a series cannot go missing again | **Loud** — allocation refuses naming the series | Repair command: `seed_demo --tenant <sub>` (insert-missing; an edited format is never overwritten) |
| 13 | **Holiday calendar** — this year and next | 22 dates: 11 in 2026, 11 in 2027 | Business-day grace stops skipping holidays. A bill due Thu 24 Dec with 5 business days' grace charges the late fee on Mon 4 Jan — a day early and **on New Year's Day** | **SILENT · see 7.3** | **No repair command exists.** Only a human adding dates on the holiday screen |
| 14 | **Chart of accounts** — the full 33 rows for every tenant | 35 (33 seeded + 2 tax-payable accounts the tax setup minted) | Any bill line, payment or deposit that cannot find its account refuses, and the **whole bill** refuses rather than issuing half-stamped. Correct: the account is frozen onto the line at issue and can never be added afterwards | **Loud** | Repair by **screen**: Ledger → Chart of accounts (create + designate). Note: `seed_demo --tenant` does **not** re-plant the chart |
| 15 | **The thirteen GL designations** (cash, undeposited funds, accounts receivable, unbilled AR, deposit liability, customer credit balances, opening balance clearing, budget billing variance, minimum-bill adjustment, bank fees, bad debt, deposit interest expense, **customer discounts (contra-revenue)** — the thirteenth, PO ruling 2026-08-28 closing DEF-536, seeded as 4300) | all 13 present | Every money path resolves its account by **designation, never by account number**, so an un-designated chart stops payments, deposits, budget billing, **every bill carrying a discount** and tax remittance — each refusing by name and telling the clerk which page to fix | **Loud** | Repair by **screen**: GL mapping |
| 16 | **A row for all ten services** — signup's picks on, the rest present-but-off | 10 rows; electric + water enabled | Without a row a service has no units and no revenue account, so its bill line refuses | **Loud** | Repair by **screen**: Settings → Services (the toggle creates the row) |
| 17 | **Per-service units of measure** | electric kWh, water kgal, gas therm, trash month, storm water kgal, broadband month; sewer, solar, thermal, battery have none | A consumption never travels without its unit — the code refuses rather than defaulting. The four blanks are deliberate: no signed design names units for them | **Loud** | Repair by **screen**: Settings → Services |
| 18 | **Per-service revenue accounts** | all ten pointed (4100 electric, 4110 water, … 4170 thermal); base-revenue split on electric and water only | Base charges on a service with no split correctly fall back to that service's own revenue account — that is the rule, not an accident | **Loud** if the account is missing; **stated fallback** for the base split | Repair by **screen**: GL mapping |
| 19 | **Bill template + published version** | 1 + 1 | **No bill can be issued at all.** For one day this was the state of every tenant on every deployment: the template engine was complete and correct and nothing ever wrote a row | **Loud** | Repair command: `seed_demo --tenant <sub>` |
| 20 | **Notice and notification templates** — 33 classes, each with a published body | 33 classes, 33 published versions (the live database also holds 7 stray QA "receipt" rows from test runs) | With no published body a dunning letter or disconnection notice **cannot be generated and nothing is queued**. Five classes are deliberately unplanted and each carries its written reason on screen: the legacy single disconnect notice (replaced by three tier notices, all of which now seed) and the four contracts, whose wording exists and is offered on the designer but which only a human can date into effect | **Loud** | Repair command: `seed_demo --tenant <sub>` |
| 21 | **Notification dispatch settings** — batch size, quiet hours, email off, SMS off | 1 row | Before 2026-08-17 the row was created on first read, so "which tenants have configured notifications?" was unanswerable. Absent, the dispatch screen materialises it on open | **Stated** | Code fallback: created on first read |
| 22 | **The provisioning audit row** | present | The record that a tenant was created, by whom, with what | **Loud** | — |

---

## 4 · The twenty reference lists (20 objects)

All twenty are seeded inside the same transaction. Eight of them are **structural** —
they seed whether or not the operator ticks "load standard reference data", because
an account cannot exist without a status and a premises cannot be created without a
type. The other twelve are governed by that tick.

| # | List | Live rows | What breaks if absent | Class | Fallback |
|---|---|---|---|---|---|
| 23 | **Units of measure** | 26 | No unit for a service, so no consumption and no bill line | **Loud** | `seed_demo --tenant`, or the post-deploy sweep |
| 24 | **Charge codes** | 23 of the 25 in the fixture | The two missing ones are **deliberate and reported by name**: the residential and commercial deposit codes carry no amount because deposits are now priced per consumer category on the plan, not by one platform figure. A charge code that is genuinely absent means that fee cannot be raised | **Stated** | `seed_demo --tenant`; the omission report names both codes and the ruling |
| 25 | **Tax jurisdictions** | 5 — two Texas rows plus a County/City/Special-district scaffold with no rates | See **7.4**. The scaffold shows the levels without pre-filling a single figure, which is right; what is missing is any signal that a rate was never set | **SILENT · see 7.4** | Repair by **screen**: Taxes & fees |
| 26 | **Reason codes** | 5 | Adjustment and correction screens have an empty picker; nothing can be raised | **Loud** at the picker | `seed_demo --tenant` |
| 27 | **Payment methods** | 7 (cash, check, card, ACH, wire, money order, lockbox) | Recording a payment under an unknown or retired method is **refused**, so a payment cannot be blank-methoded | **Loud** | `seed_demo --tenant` |
| 28 | **Meter types** | 5 | Display and export only; nothing branches on it | **Stated** (field stays empty) | `seed_demo --tenant` |
| 29 | **Read methods** | 5 | Display and export only | **Stated** | `seed_demo --tenant` |
| 30 | **Asset types** | 12 | A meter's type cannot be null — **no meter can be created** | **Loud** (the database refuses) | `seed_demo --tenant` |
| 31 | **Asset statuses** | 5 | A meter's status cannot be null — **no meter can be created** | **Loud** | `seed_demo --tenant` |
| 32 | **Premises types** | 6 | The new-premises wizard cannot resolve a type and refuses by name. This list is also **self-healing**: any premises write plants it if it is empty | **Loud** + repair-on-write | `seed_demo --tenant` |
| 33 | **Account statuses** | 5 | Every account needs one; the code refuses rather than picking whichever billable status sorts first | **Loud** | `seed_demo --tenant` |
| 34 | **Account sub-types** | 12 seeded — and **used by 0 of the 49 live accounts** | See **7.7**. Nothing breaks; the two-level account tree the PO asked for is planted and the demo data does not use it | **SILENT · see 7.7** | `seed_demo --tenant` |
| 35 | **Unit types** | 5 | A unit type unknown to both the tenant's rows and the built-in list is refused with the allowed set named | **Loud**, with a **code-constant fallback** to the built-in five so an older tenant keeps working | `seed_demo --tenant` |
| 36 | **Areas** | 4 seeded — and **attached to 0 of 50 premises and 0 of 7 routes** | See **7.6** | **SILENT · see 7.6** | `seed_demo --tenant` |
| 37 | **Meter size classes** | 9 seeded — **no column anywhere in the database holds one** | See **7.5** | **SILENT · see 7.5** | `seed_demo --tenant` |
| 38 | **Occupancy statuses** | 5 seeded, declared *structural* on the grounds that a unit without one has undefined billing behaviour — and **no column anywhere holds one** | See **7.5** | **SILENT · see 7.5** | `seed_demo --tenant` |
| 39 | **Device types** | 6 seeded — **no column anywhere holds one** | See **7.5** | **SILENT · see 7.5** | `seed_demo --tenant` |
| 40 | **Certification types** | 6 seeded — **no column anywhere holds one** | See **7.5** | **SILENT · see 7.5** | `seed_demo --tenant` |
| 41 | **Import mappings** | 0, **deliberately** | A saved import mapping describes *this* utility's own spreadsheet columns. Seeding one would describe a file layout the tenant does not have. The screen says so | **Stated** — the emptiness is registered with its written reason | None; the tenant creates their own |
| 42 | **Account types (per tenant)** | 0 created per tenant, by design — the four rows are platform-wide | A backfill restores a deleted platform row; a normal run creates nothing, and the report explains the zero so nobody reads it as "empty" | **Stated** | `seed_demo --tenant` |

**How a change to any of these reaches a tenant that already exists.** The seed
ledger records, per tenant per list, which fixture version was applied. Bumping the
fixture version makes every list eligible again; the post-deploy sweep then walks
every tenant and inserts only rows they do not have. **A tenant-edited row is never
overwritten and nothing is ever deleted.** This is the mechanism that makes "we
improved the standard list" reach existing customers, and it is the reason a
content change without a version bump is refused by a guard.

---

## 5 · The sample set — what a new tenant is planted with (10 objects)

Since 2026-08-17 a brand-new tenant is planted with a **working utility**, not an
empty one, so a trial customer can see the product work on day one. Ten blocks run
after the provisioning transaction commits. **A block failing never fails the
signup** — the tenant still opens, and the failure is named on the setup checklist.

Live, for Brazos Bend: **all seven modules report "seeded", none skipped, none
failed.**

| # | Block | Live rows | What breaks if this block does not run | Class | Fallback |
|---|---|---|---|---|---|
| 43 | Sample staff users (a Billing Clerk and an Executive, invited, no password) | 2 users | Nothing downstream; the owner is still the only login | **Stated** | Repair: Settings → Sample data → Load |
| 44 | Plans & rates | 5 plans, 6 tariffs, 25 plan tax rules | **Everything downstream stops.** No plan means no service agreement, no bill | **Stated** (the panel names it) | Repair: Settings → Sample data → Load |
| 45 | Premises, units & service points | 50 premises, 58 units, 68 service points | No meters, no accounts, no reads | **Stated** | Same |
| 46 | Meters | 68 assets | No reads | **Stated** | Same |
| 47 | Accounts, customers & agreements | 49 accounts, 47 customers, 48 agreements | No bills | **Stated** | Same |
| 48 | Meter reads | 1,674 reads | A bill run has nothing to bill | **Stated** | Same |
| 49 | Bills (June billed, July staged for the operator to run) | 48 invoices, 246 lines, 2 bill runs | **No payments can be seeded either**, because there is nothing to pay — and the payments block now says exactly that instead of reporting "0 rows, OK" | **Loud** — the refusal names the upstream block | Same |
| 50 | Payments, deposits **and the bank statement** | 45 payments, 45 allocations — but **0 bank accounts, 0 bank statements, 0 bank lines, 0 deposit batches** | See **7.2**. The block reports success under a label that promises three things and delivers one | **SILENT · see 7.2** | Same |
| 51 | Payment plan (live, mid-schedule) | 1 plan, 4 instalments | The collections screens have nothing real to show | **Stated** | Same |
| 52 | Payment-plan money | included in the 45 | — | **Stated** | Same |

The books tie: **93 journal entries, 331 journal lines**, and every bill line carries
a GL account, because a bill that cannot resolve one for **any** line refuses whole.

---

## 6 · Required by the code, seeded by nothing (6 objects)

These are the ones that do not appear in any seeding document because nothing seeds
them. They matter most.

| # | Object | Live | What breaks | Class | Fallback |
|---|---|---|---|---|---|
| 53 | **Read-validation settings** — every threshold the meter-read checker uses | **0 rows** | See **7.1**. A function exists whose own description says provisioning calls it. **Nothing calls it, anywhere in the product.** | **SILENT · see 7.1** | Estimation refuses by name; the bulk-import screen shows a banner; the single-read paths show nothing |
| 54 | **Security policy** — password length, expiry, session timeout, IP allowlist | 0 rows | Nothing. Every read falls back to the ratified column defaults and never writes a row | **Stated · code-constant fallback** | The security settings screen writes the row on first save |
| 55 | **Notification rule matrix** — which events send, on which channel, quiet hours, "skip customers on a payment plan" | **0 rows** | See **7.8**. Rows appear the first time somebody opens the notifications settings screen — and **nothing in the sending path ever reads them** | **SILENT · see 7.8** | Materialised on first read of the settings screen |
| 56 | **Billing cycles** | 3 (from the sample plant only) | A bill run against an unknown cycle is refused as not-found. A tenant who declined the sample data has **no cycle and therefore no bill run**, with an empty picker as the only clue | **Loud** at the run; **Stated** at the picker | Repair by **screen**: Meter reads → Cycles |
| 57 | **Routes and read schedules** | 7 routes, **0 read schedules** | See **7.9**. Every route on the running product has no service and no area | **SILENT · see 7.9** | Repair by **screen**: Meter reads → Routes |
| 58 | **Tax rates** | 2 (from the sample plant only) | See **7.4**. Jurisdictions are seeded; the rates that make them charge anything are not | **SILENT · see 7.4** | Repair by **screen**: Taxes & fees |

---

## 7 · THE SILENT ONES — thirteen objects, nine findings

*(numbered 7.1–7.9; two of them cover more than one object)*

Every one of these has the same shape: the product carries on, produces an answer,
passes its tests, and the answer is wrong or absent — **and nothing anywhere says
so.** By the PO's own rule each is a defect. Proposed defect rows have been written
up for filing.

### 7.1 · The meter-read validation settings have a seeder that nothing calls

The function that creates this row describes itself as *"Provisioning entry point …
Tenancy owns provisioning, so it calls this"*. Searching the whole repository, the
only callers are **two test files**. Provisioning does not call it. The live database
confirms it: **zero rows, for the only tenant on the system.**

What that costs: every read-validation rule that needs a threshold — the high-usage
check, the zero-usage check, the meter-mismatch check — reports *"not evaluated:
validation config missing"* instead of running. Estimation refuses outright and says
why, which is right. The bulk read-import wizard shows a banner. **The single-read
correction and supersede paths compute the same "not evaluated" outcomes and their
result carries no summary line naming the missing configuration** — so a clerk
correcting one read sees no errors and no explanation that no rule ran.

This is the exact pattern the hard-won laws call out: *a comment claiming a guarantee
is not the guarantee.*

**Fallback today:** none. **Proposed:** provisioning calls the seeder, and the repair
command calls it too.

### 7.2 · The sample-data panel reports success over work it did not do

The payments block is labelled **"Payments, deposits and the bank statement"** and
reports **seeded, 45 rows**. Live: 45 payments — and **0 bank accounts, 0 bank
statement imports, 0 bank lines, 0 deposit batches.**

The payments module keeps an honest internal register of the four things it
deliberately does not seed (the bounced cheque and its fee, the write-off awaiting
approval, the goodwill credit, and the whole deposit-batch/bank-statement block).
The rating module keeps one too (the discounted Senior plan, because no signed figure
prices it). **Neither register is read by anything.** The panel has no way to ask a
module what it left out, and the code comment in the payments file says *"which the
Sample data panel renders"* — it does not.

Five named, deliberate, well-reasoned omissions are invisible to the person reading
the panel, under a label that promises them.

**Fallback today:** none. **Proposed:** the orchestrator asks each module for its
omissions and the panel prints them under the block, the same way the notice-template
seeder already prints every class it has no body for.

### 7.3 · Nothing renews the holiday calendar

Provisioning seeds this year **and next** — live, 11 dates in 2026 and 11 in 2027.
That fixed a real defect: with one year seeded, on 1 January every business-day grace
calculation silently went back to skipping weekends only, and a late fee due Tue 5 Jan
landed Mon 4 Jan, *on New Year's Day*, for every customer of that tenant.

There is a function to top the calendar up to any horizon. **It has no caller in the
product** — only tests and the check that excludes its own definition. So the calendar
runs to the end of 2027 and stops. The failure returns in January 2028, in exactly
the same silence, and the code's own docstring says so: *"the gap this leaves is real
and is stated rather than implied."*

A build-time check exists and will go red **if it is run against a live database.**
That is a detector, not a fallback.

**Fallback today:** none — the repair command does not touch holidays, and by design
an empty calendar is never re-seeded (a utility outside the US is entitled to delete
every date). **Proposed:** the repair command tops up a non-empty calendar, and the
top-up runs on the deployment sweep.

### 7.4 · Tax jurisdictions are seeded; tax rates are not

Live: **5 jurisdictions** — the two Texas rows plus the County / City / Special
district scaffold that every state gets. The scaffold has **no rates**, and that is a
deliberate PO ruling: a wrong tax rate charges real customers real money.

But the rates themselves — the rows that make a bill carry tax — are created by the
**sample-data plant**, not by provisioning. A tenant who declines the sample data
gets five jurisdiction names, zero rates, and **every bill they issue carries no
tax**. Nothing warns them. The bill run only complains about a tax line that already
exists and cannot find its account; a bill with **no** tax line raises nothing at all.

On this tenant the sample plant did run, so 96 tax lines totalling $336.63 exist and
the mechanism demonstrably works. The silence is for the tenant who turns the sample
data off — which is the self-serve utility this whole capability is for.

**Fallback today:** the tax screen. **Proposed:** the setup checklist names
"jurisdictions seeded, no rates set" as an open item, and the bill run reports it.

### 7.5 · Four seeded lists have nowhere in the database to be used (26 rows per tenant)

Every new tenant receives **9 meter size classes, 5 occupancy statuses, 6 device types
and 6 certification types** — 26 rows. Searching every column in the live database for
anything that could hold one of them returns **nothing**. No table references them.

They render on the Settings reference-data cards and go no further. Their absence
would produce no signal of any kind, because nothing asks for them.

One of the four is worse than merely inert. **Occupancy status is classified as
structural** — it seeds even when the operator declines the standard data — on the
stated grounds that *"a unit that cannot be given an occupancy status has undefined
billing behaviour — tenant-billed / owner-billed / base-only / no-billing."* That is a
statement about how bills are produced, and **the units table has no occupancy
column.** The claim is unbacked today.

**Fallback today:** not applicable — nothing consumes them. **Proposed:** either the
consuming columns get built, or the four cards are marked on screen as vocabulary
awaiting its feature, so nobody configures them believing they do something.

### 7.6 · Areas are seeded and attached to nothing

Live: **4 areas seeded. `premises.area_id` is NULL on all 50 premises. `routes.area_id`
is NULL on all 7 routes.** The columns exist — unlike 7.5, this one is wired — and the
sample plant never sets them.

So the Settings card shows four districts, and every premises and every route in the
demo utility reads "—". A PO reviewing the seeded product sees an area vocabulary that
appears configured and is used by nothing.

**Fallback today:** the premises and route screens. **Proposed:** the sample plant
assigns areas, so the demo shows the feature working.

### 7.7 · Account sub-types are seeded and attached to nothing

Live: **12 sub-types seeded. `accounts.account_subtype_id` is NULL on all 49 sample
accounts.** The two-level account tree the PO asked for in CR-010 exists as data and
the demo utility does not demonstrate it. Same shape as 7.6, one module along.

**Fallback today:** the account screen. **Proposed:** the sample plant sets a sub-type
on each sample account.

### 7.8 · The notification rule matrix is read by nothing that sends

Live: **0 rows**, for a tenant that has been running bills, payments and 93 outbound
messages. The rows are created the first time somebody opens the notifications
settings screen — so "zero" here means "nobody has opened it".

That would be acceptable on its own. What is not: searching the whole backend, the
rule rows are read by **the settings screen and its API, and by nothing in the sending
path.** So a utility that switches an event off still gets it, and one that switches an
event on gets nothing new. The protective filter the CR specifically called for —
past-due reminders skipping customers who are on a payment plan — is stored and never
consulted.

CR-010 item 7 asked for these rows to be written at provisioning alongside the dispatch
settings. The dispatch settings row landed; the rule rows did not.

**Fallback today:** created on first read. **Proposed:** seed them at provisioning as
the CR asked, **and** file the fact that nothing enforces them — that second half is
the larger problem and it is not a seeding problem.

### 7.9 · Every route on the running product has no service and no area

Live: `select coalesce(service_id::text,'NULL'), count(*) from routes group by 1`
returns **NULL for all 7 rows**, and the same for `area_id`. This confirms and extends
an existing finding (a route's service was already known to be always null; the area is
new here). Any code that branches on a route's service never executes in reality, and
**0 read schedules** exist, so nothing is scheduled to be read.

**Fallback today:** the route screen. **Proposed:** the sample plant sets a service and
an area on each route it creates.

---

## 8 · The repair paths, in one place

There are exactly **four** ways a missing seeded object gets replaced. Anything not on
this list has no repair path.

| Repair path | What it re-plants | What it does **not** touch |
|---|---|---|
| **`manage.py seed_demo --tenant <subdomain>`** — safe in production; creates no tenant, user or credential | All 20 reference lists · the 22 number series · the bill template · the notice templates. Insert-missing, so a row the tenant edited is never overwritten, and a replay writes nothing | The chart of accounts · the ten service rows · the holiday calendar · the notification dispatch settings · the read-validation settings · any sample records |
| **The post-deploy sweep** — runs automatically after every migration, across every tenant | The reference lists and number series for every tenant whose seed version is behind. Only delivers the **structural** vocabulary on a version bump, because a tenant who declined the standard data must not receive it because we shipped a release | Everything in the right-hand column above |
| **Settings → Sample data → Load** | All ten sample blocks | Nothing structural |
| **The screens themselves** | Chart of accounts · GL mapping · Services · Regional settings · Taxes & fees · Holidays · Cycles · Routes · Premises types (also self-heals on any premises write) · Security policy (on first save) · Notification dispatch settings and rules (on first open) | — |

**The rule underneath all four, and it is the one that keeps catching us:** *a change
to provisioning never reaches a tenant that already exists.* Every time provisioning
learns to seed something new, a repair door has to be built for the tenants already
running — or that improvement reaches nobody who has already signed up.

---

## 9 · What I could not determine, and why

Stated plainly rather than glossed, because a map that hides its own edges is worse
than no map.

1. **One tenant, one shape.** The live database has exactly **one** tenant, provisioned
   today at the current build with the standard-data toggle **on** and Texas as its
   state. So every figure here is that path. **Not measured:** a tenant with the toggle
   **off** (which is the self-serve utility this capability exists for), a non-Texas
   tenant, and any tenant provisioned at an older build. The toggle-off path is the one
   most likely to hold further silent gaps — 7.4 and 7.6 were both found by reasoning
   about it rather than by measuring it.

2. **Whether the single-read correction screens show the "no validation config"
   state.** The bulk import wizard demonstrably does (the front end renders a banner off
   an explicit flag). The single-read correction and supersede paths compute the same
   "not evaluated" outcomes, and I did not trace those outcomes all the way to a
   rendered screen. Stated as unknown rather than assumed either way.

3. **Whether the eight seeded structural lists behave correctly with the toggle off.**
   The code says they always seed; no tenant on this system has the toggle off, so this
   is read, not measured.

4. **The 7 stray "QA" receipt templates** in the live database are residue from
   automated test runs against this database, not seed output. They are excluded from
   every count above. It does mean the live database is not a pristine provisioning
   result and anyone re-measuring should expect similar noise.

5. **Whether any of the four unusable lists in 7.5 has a consumer planned.** I looked
   for a column, not for a story. The finding is "nothing in the database can hold one
   today"; whether a feature is scheduled that would use them is a product question, not
   a code one.

6. **Blast radius on a tenant with real data.** Every "what breaks" here is measured
   against a fresh tenant. What happens if an object goes missing on a tenant that has
   already issued bills — a deactivated GL account, a deleted number series — is
   partially covered by the refusals above but was not tested.

---

## 10 · What this document is for

It is the answer to *"what if some data does not get seeded — does the process down the
line break down?"*

For **45 of 58 objects**: yes it breaks, and it breaks **loudly**, naming what is
missing and which screen fixes it. That is the design working. The strongest example is
bill issue: if any single line on a bill cannot find its GL account, the **whole bill
refuses** rather than issuing half-stamped — because that stamp is frozen at issue and
could never be repaired afterwards.

For **13 of 58**: it does not break. It carries on and is quietly wrong, or quietly
absent. Those thirteen — nine distinct findings, because two of them cover more than
one object — are Part 7. Each is a defect by the PO's own rule, and each has a
proposed fix that is small.

---

*Measured 2026-08-18 against build 2.19.0, seed fixture V2.18.0.0, commit `dda3f84`,
and the running `sbh_e2e` database (tenant `brazosbend`). Re-run the three passes in
Part 1 before trusting any figure here; every figure in this document's predecessor
was stale within twenty-four hours.*
