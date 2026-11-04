# 17 · Runbooks — the selector inventory

**`CR-075` wave A task `A5`, written 2026-09-06 against product `2.201.1`.** Every read a defined
runbook needs **that no module exposes today**, with the **owning module** named for each.

> **Why this is done NOW and not discovered in phase 5.** The execution plan says so in one line —
> *"the owning module adds the selector and this module never reaches past a seam"* — and the cost of
> finding out late is not a delay, it is a **boundary breach under time pressure**. A lane in wave Q
> that needs a meter's own 90-day average, on the day, with a screen to ship, will reach into
> `apps.metering.models` because it is four lines and asking metering is a conversation. That single
> line is `BR-RBS-039` gone and `G115` red, and the pressure to switch the gate off arrives with it.
> **Inventoried in advance, each of these is a small piece of work in the module that owns the
> table.** Found late, each is a temptation.

---

## 0 · How to read this, and what it is NOT

**This is an inventory, not a build.** Nothing here is implemented by `CR-075` wave A, and nothing
here is implemented by this module at all, ever. Each row is a request the owning module fulfils in
its own `selectors.py`, in the wave that first needs it.

**The seam files name NO selector today, and that is deliberate.** Naming one that does not exist
fails `G20` — whose R2 rule refuses a documented seam nobody has authored, the guard that caught
`DEF-075` (billing's half of a currency-lock probe resolved to `None`, `None` was read as *"this
module has nothing"* when it meant *"this module cannot answer"*, and a tenant re-denominated its
books over an issued bill of `108.88 USD` with 1,961 tests green). Naming one that exists but that
nothing calls is hard-won law 2's dead code. **So a seam gains a by-name row in `B2` Addendum r25
in the wave that makes the call**, and this file is the list of what those waves will be asking for.

### What was checked, and the number that goes with the blind spot

**Source:** the 21 fully defined runbooks in [`11-catalogue/`](11-catalogue/) — every `read` step of
every one, plus each runbook's scope function. The 5 reserved (23–27) and 8 named-only (28–35)
runbooks are **NOT** inventoried here, because their steps are drafted or absent and an inventory
built on a draft would be a list of guesses. **That is 21 of 34 runbooks — 62% — and the remaining
13 are a declared gap with a number on it rather than an implied zero.**

⚠ **TWO OF THE THIRTEEN CLOSED THEMSELVES ON 2026-09-07 AND THE GAP IS NOW ELEVEN.** Runbooks 28 and
33 were built from their one-sentence commitments (`US-RBS-043`, `US-RBS-044`), so their reads are
no longer guesses — and they are no longer REQUESTS either, because the owning modules added them in
the same commit, which is what this file exists to make happen. **Three selectors and three seam
reads landed, none of them in `apps/runbooks`:**

| Read | Owning module | Where it landed |
|---|---|---|
| Every measuring asset with its age, its expected life and its last test | `assets` | `apps/assets/selectors.py` · `meter_lifecycle_census` |
| The same, joined to the service point, the unit and the service code | `metering` | `apps/metering/selectors.py` · `meter_lifecycle_census` (metering owns assets, B2 r4) |
| Every enrolled budget account **with the tenant's own S69 rules, in one read** | `billing` | `apps/billing/selectors.py` · `budget_programme_overview` |

The seam reads that resolve them — `metering_seam.meter_lifecycle_census` and
`billing_seam.budget_programme` / `budget_trailing_actuals` — name a selector that exists, which is
what `G20`'s R2 rule asks for, and none is a new SEAM so none needs a new `B2` Addendum r25 row.

⚠ **A THIRD SEAM READ EXISTS BECAUSE `G115` REFUSED THE OBVIOUS BUILD, AND IT IS THE ONE WORTH
COPYING.** `billing_seam.budget_level_decision` answers *what level do these actuals support, and
does `BR-BIL-017` move it*. The first build of runbook 33 did `from apps.billing import budget`
inside a step and called `compute_level`, `drift_fraction` and `relevel_due` itself — a foreign
import outside the two lawful doors, refused by file and by line. **The fix is not to move the
import; it is to move the QUESTION.** A runbook assembling those three calls would have been holding
billing's rule on this side of the seam, where the next lane could reorder its two gates without
billing noticing — which is exactly the temptation the header of this file describes, met in
practice.

**The remaining eleven un-inventoried runbooks are 29 · 30 · 31 · 32 · 34 · 35 and the five reserved
23–27**, and that number is stated here rather than left as an implied zero.

⚠ **TWO OF THE THIRTEEN CLOSED THEMSELVES ON 2026-09-07 AND THE GAP IS NOW ELEVEN.** Runbooks 28 and
33 were built from their one-sentence commitments (`US-RBS-043`, `US-RBS-044`), so their reads are
no longer guesses — and they are no longer REQUESTS either, because the owning modules added them in
the same commit, which is what this file exists to make happen. **Three selectors and two seam reads
landed, none of them in `apps/runbooks`:**

| Read | Owning module | Where it landed |
|---|---|---|
| Every measuring asset with its age, its expected life and its last test | `assets` | `apps/assets/selectors.py` · `meter_lifecycle_census` |
| The same, joined to the service point, the unit and the service code | `metering` | `apps/metering/selectors.py` · `meter_lifecycle_census` (metering owns assets, B2 r4) |
| Every enrolled budget account **with the tenant's own S69 rules, in one read** | `billing` | `apps/billing/selectors.py` · `budget_programme_overview` |

The two seam reads that resolve them — `metering_seam.meter_lifecycle_census` and
`billing_seam.budget_programme` / `budget_trailing_actuals` — name a selector that exists, which is
what `G20`'s R2 rule asks for, and neither is a new SEAM so neither needs a new `B2` Addendum r25
row. **The remaining eleven un-inventoried runbooks are 29 · 30 · 31 · 32 · 34 · 35 and the five
reserved 23–27**, and that number is stated here rather than left as an implied zero.

**Method:** each distinct read was matched against the owning module's `selectors.py` by name and by
what it returns. Counted at `2.201.1`: `customers` 76 · `metering` 129 · `rating` 115 · `billing` 74
· `payments` 41 · `ledger` 18 · `notifications` 15 · `tenancy` 69 · `integrations` 13 — **550
selectors in total**, and the great majority of what these runbooks need is already among them. This
file lists only what is **not**.

**Three verdicts, and the middle one is the one that bites:**

| Verdict | What it means | Count |
|---|---|---|
| **ABSENT** | Nothing in the owning module answers this question. The module writes a new selector. | **14** |
| **WRONG DOOR** | The answer exists, but **not in `selectors.py`** — so a seam resolving `apps.<module>.selectors.<name>` gets `None`, which `G20` reads as *no implementer*. The module re-exports or moves it. | **3** |
| **NOT OURS** | Nothing in this product holds the fact at all. It is a question for the Product Owner or a third party, not a selector. | **2** |

⚠ **WRONG DOOR IS `DEF-035`'S SHAPE AND IT IS WORSE THAN ABSENT**, because it looks answered. A seam
that resolves the wrong KIND returns `None` on every call, and `None` reads like *"nothing to
report"* — which is how `US-CUS-005`'s move-out guard recorded
`move_out_date_not_checked_against_issued_bills` on **every move-out, since the day the guard was
written**. An absent selector fails loudly at the seam; a wrong-door one answers *no findings* for
ever.

---

## 1 · ABSENT — fourteen selectors that must be written

| # | The question | Owning module | Needed by | First wave |
|---|---|---|---|---|
| S-1 | **A meter's own 90-day average**, per meter, not a fleet number | `metering` | RB-111 step 2 (leak alert) · RB-121 step 4 (gap estimation by policy) | Q — ✅ **BUILT 2026-09-07** (`CR-075` wave R′). `metering.selectors.meter_normals(asset_ids, as_of=…, days=90)`, one query for the whole set, carrying **the unit** (hard rule 3) and answering **S-4** in the same pass. ⚠ **`average_per_day` is `None` where there is no history and NEVER `0`** — a zero makes every reading infinitely above its own normal and puts that on a customer's phone at 07:30. `as_of` is STATED, never a clock (`BR-TEN-043`, `G6`). |
| S-2 | **A meter's own median over twelve periods**, with actual and estimated marked | `metering` | RB-105 steps 1–3 (spikes above 300% of the meter's own median; drops below 20%) | P |
| S-3 | **A meter's same-month history** — this September against its own Septembers | `metering` | RB-105 step 7 (out of season) | P |
| S-4 | **A meter's last good day** — the most recent day with a complete, validated set | `metering` | RB-121 step 6 (every exception carries it) | Q — ✅ **BUILT 2026-09-07** (`CR-075` wave R′), inside `meter_normals` above rather than as a second query: it is the most recent day carrying a committed read at status `ok`. ⚠ **`None` means *never reported*, which is a different fact from *reported long ago*** and the screen says so in words rather than printing a date it does not have. |
| S-5 | **Interval gaps inside a day**, and meters silent all day | `metering` | RB-121 step 3 | Q — ✅ **BUILT 2026-09-07** (`CR-075` wave R′), and **NOT as a selector, which is the part worth reading.** `metering.selectors.interval_batch()` returns the batch **already rolled up to the meter-day** with `intervals` · `zero_intervals` · `nonzero_intervals` · `first_at` · `last_at` per row, and the runbook reads the gap from the SPACING of the timestamps. ⚠ **The cadence is MEASURED, never assumed** — `RB-121` says *96 intervals* in one place and *"reads arrive hourly"* in another, and assuming either reports a full day as 75% missing or a quarter-day as complete. ⚠ **Every rolled-up total carries its unit and a meter-day whose own intervals disagree carries NO total** (hard rule 3): this is the one read in the module where six figures of readings are added together. |
| S-6 | **A premise's usage over a window with no active account against the unit** — vacancy with flow | `metering` | RB-118 steps 1–2 | R |
| S-7 | **Three consecutive zero reads on an active account's meter** — the mirror of S-6 | `metering` | RB-118 step 3 · RB-105 step 3 | P · R |
| S-8 | **Addresses that failed standardisation**, on `premises` | `metering` | RB-119 step 6 (post will not arrive) | R |
| S-9 | **Duplicate customers by phone, tax id or email under two names** | `customers` | RB-119 step 1 | R |
| S-10 | **Accounts with no contact channel at all** — nobody can be told anything | `customers` | RB-119 step 5 | R — ✅ **ANSWERED EARLY, 2026-09-06.** `customers.selectors.contact_channels_for(account_ids)` was added for `RB-122` step 4 (*email → text → post → none*) and answers this too: an account whose entry has all three false is one. It is a BULK read — one query for a whole morning's feedback — so `RB-119` reads it the same way. ⚠ *Present* means ON FILE and never *working*: nothing in `customers` records that a channel stopped working or when, which is why `suppress_channel` binds no writer (`DEF-RBS-4331`). |
| S-11 | **Deposits held longer than a stated period, with twelve months of on-time payment behind them** | `payments` | RB-115 steps 1–3 | S |
| S-12 | **Prior returned-payment count for an account**, against the privilege limit | `payments` | RB-126 step 3 | S |
| S-13 | **Sub-ledger receivables against the control account**, and **billed totals against posted totals per service** | `ledger` | RB-109 steps 4–5 (the month-end tie-out — the two tie-outs the whole runbook exists for) | K |
| S-14 | **Rate blocks against the highest usage ever seen**, per service | `rating` (asks `metering` for the maximum) | RB-101 step 5 · RB-103 step 4 | C |

### Two of these are bigger than they look, and the plan should know which

**S-13 is the month-end tie-out and it is `ledger`'s largest single ask.** `apps/ledger/selectors.py`
holds **18** selectors, all of them about *which account* rather than *what the totals are*: it can
answer `revenue_account_id_for_service` and `entry_debit_totals` for a list of entries, and it has
nothing that sums a period. Wave K cannot start until this exists, and it is the one row here that
is a piece of finance work rather than a query.

**S-1 through S-5 are one body of work, not five.** Every one of them is *this meter's own history,
summarised* — the average, the median, the same-month comparison, the last complete day, the gaps.
A module that adds them one at a time will write the same window query five times. **Metering should
be asked for a meter-history selector with a stated window and a stated summary**, and the five rows
are its callers. They are listed separately because each has a different caller and a different
wave, not because each is a different query.

---

## 2 · WRONG DOOR — three answers that exist somewhere else

| # | The question | Where it lives today | Why the seam cannot use it | Owning module's job |
|---|---|---|---|---|
| W-1 | **An account's collections-ladder tier and when it was last sent** | `apps/payments/collections_read.py::account_position(account_id, as_of)` — real, tested, correct | A seam resolves `apps.<module>.selectors.<name>` or `apps.<module>.services.<name>`; `collections_read` is a **third kind** that no resolver looks in, so the lookup returns `None` and `G20` reads it as *no implementer* | `payments` re-exports it from `selectors.py`, or the seam's resolver learns the third kind — **the re-export is the smaller change and the one that keeps `G20`'s rule intact** |
| W-2 | **The ladder board and its per-tier counts** | `apps/payments/collections_read.py::ladder_board(...)` | same | same |
| W-3 | **Whether a notice was actually DELIVERED, not merely queued** | `apps/notifications/selectors.py::deliveries_for_source(source_type, source_id)` — exists, and is keyed by SOURCE | RB-112 step 2 asks the opposite direction — *for this account, was the tier-3 letter delivered* — and there is no selector that starts from an account | ✅ **ANSWERED 2026-09-07 BY `CR-075` WAVE S, AND NOT THE WAY THIS ROW EXPECTED.** `notifications` was NOT asked for an account-first form, because it could not answer it either way: `delivered` and `bounced` are PROVIDER facts and **no provider adapter exists on any channel, print included**, so the account-first read would have returned NOT REPORTED on every row for ever. The question runbook 12 actually needs is *was this household lawfully told*, and `BR-CUS-100` answers it — a person's **proof of service** with the channel, the reference and the date. `customers` publishes it as `runbook_reads.final_notice_board`, and the delivery blind spot travels on the same answer as a number rather than as a silence. |

⚠ **W-1 AND W-2 ARE THE SAME FIX AND IT IS FIVE MINUTES.** They are listed because a lane that does
not know will spend an afternoon writing a second `account_position` inside a seam — which is a
cross-module read reimplemented in this module, the exact thing `BR-RBS-039` forbids, arrived at
honestly.

⚠ **W-3 IS THE ONE THAT COULD SHIP WRONG.** *Queued* and *delivered* are different facts, and
`RB-112`'s step 2 says so in six words: **a returned letter is not a served notice**. A disconnect
list built from *queued* would put people on it whose letter came back. There is no selector that
can tell the difference from an account today, and the run would look perfectly healthy.

---

## 3 · NOT OURS — two facts this product does not hold

| # | The question | Runbook | What it actually is |
|---|---|---|---|
| N-1 | **The weather moratorium** — is today inside a cold-weather rule for this service area? | RB-112 step 6 | **Not a selector.** Nothing in this product holds a forecast or a state moratorium calendar. It is either a tenant setting a person maintains, or a third-party feed, and which one is a **Product Owner question that has not been asked**. ⚠ It is NOT minted as an `OQ-RBS-` here, because `RB-112` is a phase-5 runbook and law 13 says a question reaches the PO when we need the answer, not when we notice the gap. **The lane that builds `RB-112` mints it.** ✅ **MINTED 2026-09-07 as `OQ-RBS-1757` by `CR-075` wave S, and the question got SHARPER on the way.** It is not only *nobody holds a forecast*: this product DOES hold a `weather_moratorium`, as a per-ACCOUNT date window a person records (B18 §5.8.3, `disconnects.PROTECTION_MORATORIUM`), and the card asks for an AREA-WIDE temperature rule. Two different objects wearing one name, which is a collision with a signed rule rather than a gap — CLAUDE.md law 13's own reason for reaching the PO at all. **Built meanwhile:** the per-account window is checked and REMOVES; the area-wide half reads *Not checked* on the tile and never the card's green *No*. |
| N-2 | **Is today a working day, in the tenant's timezone?** | RB-112 step 7 | **Half ours.** `apps/tenancy/selectors.py::holidays()` exists and `G24` guards the holiday horizon, so the calendar is real; what does not exist is *is this date a working day for this tenant* as one call. Closer to an ABSENT row than to this table, and it is put here because the answer may be that the runbook composes it from `holidays()` and never needs a selector at all. **Decided by the wave that builds it.** |

---

## 4 · What this inventory does NOT cover, stated with its number

* **13 of the 34 runbooks** — the 5 reserved (23–27) and the 8 named-only (28–35). Their steps are
  drafted or absent; an inventory over them would be a list of guesses wearing a table.
* **Selectors that exist but are not paginated.** `NFR-3` binds every list this module adds and
  `NFR-5` forbids a per-tenant cap. A selector that returns every past-due account unpaginated is
  correct at 3,000 accounts and **13× short at 40,000** — `DEF-PAY-4221`'s shape. **Nothing here
  audits that**, and it is the audit the wave that first walks a large set must do.
* **Write paths.** Every write is a port, all thirteen are declared in `apps/runbooks/ports/`, and
  **not one has a writer bound**. Binding them is wave `L` and is not a selector question.
* **Whether an existing selector is FAST enough** over the top of the ICP. Read validation walks
  **1,840 meter-days** where the raw data is **176,640 intervals** (`BR-RBS-019`), so the rollup —
  not the selector — is what keeps it cheap; but nothing here has been measured.

---

## 5 · The rule this file exists to protect

> **A selector that does not exist yet is added by the module that OWNS the table, never by this
> module reaching past it.** — `BR-RBS-039`, spec B2b

**Enforced, not asserted.** `10-scripts/gates/g115_runbooks_import_census.py` fails any
`apps.<other>` import outside `apps/runbooks/seams/` **by file and line number**, and was shown red
on planted violations through `run_gates.py` before it was trusted green. This file is what makes
obeying that rule cheap: the fourteen absent selectors are known before any wave needs them, so
asking the owning module is a planned task rather than an obstacle discovered at the worst moment.

---

*Written by the `CR-075` wave A build lane, 2026-09-06. Every row above was checked against the
module's actual `selectors.py` at product `2.201.1`; the counts in §0 are `grep -c '^def '` on each.*
