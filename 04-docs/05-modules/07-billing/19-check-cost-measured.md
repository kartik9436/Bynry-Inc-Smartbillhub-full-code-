# Bulk Check — what one account costs, measured (B27 step 1, 2026-09-30)

Status: **BEFORE AND AFTER.** The "before" below is unchanged; **§8 is the after** (B27 built, `2.416.0`); §9 is B28; **§10 is the clerk's S1–S4 timed at 10,000 and 40,000** (2026-10-01). **§11 is S3 re-timed after the Send was batched (`2.426.0`).**
It was: **FINDINGS, NOT A PLAN.** Plan task B27 step 1 (`15-bulk-bill-run-build-plan.md`, changes row 55):
*"measure ms/account before and after"*. This is the **before**. No product code was changed to produce it.
Decision-log rows of 2026-09-30 it reads against: *"BULK CHECK BATCH SIZE = 500 ACCOUNTS"* and *"PRODUCTION
SCALES BILLING WORKERS THROUGH INFRASTRUCTURE"*.

## In one paragraph

Today the bulk Check costs **about 690 ms and 425 SQL statements per account** (683 ms at 100 accounts, 693 ms at 5,000; the statement count is flat at every size) on a realistic account
(electric, two water meters, sewer, a trash cart, readings, a previous bill and two payments), on real
PostgreSQL 16 with row-level security enforced. That is **five times** the 137 ms figure the PO was shown on
2026-09-30. On one worker it is **~11.6 minutes at 1,000 accounts, ~1.9 hours at 10,000 and ~7.7 hours at
40,000**. About **two thirds of the statements (291 of 425) ask exactly the same question for every account**
— taxes, rate tiers, charge codes, service lookups — and almost all the rest ask the same question about each
account's own rows. Loaded once per batch of 500, the Check would issue roughly **20 statements per account
instead of 425**, and an estimated **150–250 ms per account instead of ~690**. Two defects were found on the
way and filed: the meter-reading reads cannot use the monthly partitions (`DEF-BIL-8490`), and a payment
recorded while a batch runs is missed by the Check **and** never flagged stale (`DEF-BIL-8491`) — which must be
fixed before B27 batch-loads anything else.

## 1 · Method

| | |
|---|---|
| Script | `10-scripts/bbr_check_cost.py` (`seed`, `measure`, `profile`, `race`), modelled on `cr138_p4_debtor_cost.py` |
| Database | PostgreSQL 16.13, cluster `127.0.0.1:55433`, database `sbh_b27cost` (a copy of `sbh_j72_seeded`, migrated to the tip) |
| Role | `sbh_b27` — **NOSUPERUSER NOBYPASSRLS**; the script refuses a bypassing role (exit 2), so every figure is paid with RLS FORCE on |
| Tenant | `b27-cost`, provisioned through the real signup service with electric + water + sewer + trash and the sample plant (`cr081_seed_sewer_utility.py`'s path) |
| Template account | `AC-2026-00003` (plan `SCW-RES`): electric meter, water meter, trash cart, sewer service point, an August bill issued by the sample plant's real bill run, two payments. Given a **second water meter** and a Sep 30 reading on every meter through the J72 seed's helpers (`a_meter`, `commit_read`) |
| Population | The template's whole subtree cloned into cycle `B27-COST` (unit, 4 service points, 4 meters/carts and their assignments, plan assignment, account, 4 agreements, 12 readings, 2 issued bills with 24 lines, 2 payments with allocations). The priced world — plans, schedules, charge codes, taxes — is the tenant's own |
| Fidelity check | The template, checked in its own cycle, and the first clone, checked in `B27-COST`, both come back **Ready with no findings**, and every measured pass reports all accounts Ready |
| Run | One Sep 1 – Sep 30 run on `B27-COST`, bill date Oct 1, 21 days to pay |
| Timed | `check_store.check_run(run)` — the whole job body: scope, the engine on every account, each account's savepoint and saved result, the summary counts |
| Timing rule | One **discarded warm-up**, then the **median of 3**. For 5,000 the warm-up is one batch of 500 (a full warm-up pass is about an hour; the warm-up's job is the connection and plan cache, which one batch pays) |
| Statements | Counted by `connection.execute_wrapper` (no 9,000 cap), DEBUG off |
| Per-account profile | `profile --k 10`: one account, then ten; per-account = difference ÷ 9, so the pass's fixed cost is not charged to accounts. Each statement is attributed to the Check step and the owning read that issued it |
| Machine | 4 cores **shared with other lanes** (load 2–4 throughout). Statement counts do not depend on that; the wall clock does, so read the times as ±10% |

**What would make this pass wrongly, and how it is ruled out:** a bypassing role (refused); an empty cycle
(refused); a warm cache on one run only (warm-up discarded, median); fixed cost charged per account (the 1 vs
10 difference); a clone that checks differently from its template (compared, identical).

**Not measured:** HTTP, the job queue, concurrent batches, and account shapes other than this one. Every clone
shares one plan and one premises, which is how a real small utility looks for the plan-level reads (a handful
of plans) but means this does not measure a tenant with hundreds of plans. A lighter account (one or two
services, one meter) will cost less; the 137 ms figure was measured before the Check ran every check on every
service.

## 2 · The figures

| Accounts | Median | ms / account | Statements | Statements / account | Runs (s) | Result |
|---:|---:|---:|---:|---:|---|---|
| 100 | 68.3 s | **683** | 42,576 | **425.8** | 68.4 · 68.3 · 67.0 | 100 Ready |
| 1,000 | *(excluded)* | *(652–868)* | 425,080 | **425.1** | 764.2 · 652.7 · 868.1 | 1,000 Ready — **times excluded**, see below |
| 5,000 | 3,464.6 s | **693** | 2,117,112 · 2,125,112 | **423.4 · 425.0** | 3,250.9 · 3,678.3 | 5,000 checked — median of **2**, see below |

Profile of one account (`profile --k 10`): **425 statements per account, 75 fixed per pass**; about **300–345 ms
of the account's time is in the database**, the rest is Python (the engine, the ORM building 425 querysets and
model rows).

### Extrapolated — one worker, today's code

**Why two sizes carry a caveat, stated plainly.** *1,000:* a measuring process started before the first
container restart survived it unseen, and a second one was started after it, so two passes ran on the same run
at the same time and slowed each other (load 5–9 on 4 cores). The statement counts are exact and are kept; the
times are not a clean measurement and are left out of the fit. *5,000:* the warm-up was one batch of 500 (a full
warm-up pass is an hour) and the **third** timed run was killed by the second container restart, so the figure
is the median of two runs (their mean): 3,250.9 s and 3,678.3 s, 13% apart with the machine's load. Their
statement counts differ by 8,000 because the first pass wrote each result for the first time and the second
replaced one (~1.6 extra statements an account). No further run was taken: the per-account cost is the same at
100 and at 5,000 to within 2%, which is what the fit needs.

A straight line through the two clean sizes (68.3 s at 100, 3,464.6 s at 5,000) is **0.693 s per account and
no fixed cost worth naming** (about −1 s). So:

| Accounts | Today, one worker | Today, 8 workers in batches of 500 (ideal split) |
|---:|---:|---:|
| 1,000 | **~11.6 min** | 2 batches, so 2 workers busy: ~5.8 min |
| 10,000 | **~1.9 h** (115 min) | ~14 min |
| 40,000 | **~7.7 h** (462 min) | **~58 min** |

The 8-worker column assumes the database keeps up with eight passes at once, which was not measured (B28 is
where that is proved).

Against the acceptance criterion S1 (`20-bulk-run-clerk-acceptance.md`: ≤ 10 min at 10,000, ≤ 30 min at
40,000): today's code needs **~12 workers at 10,000 and ~16 at 40,000** even with perfect parallel batches —
the ruled plan of 80 batches on 8 workers gives **~58 minutes** at 40,000, not the ~12 minutes put to the PO,
because that figure was worked from 137 ms.

## 3 · Where the 425 statements go

Per account, grouped by the read that issued them. *Asks / distinct* is inside ONE account: 118 / 59 means
the account asks 59 different questions twice each. *Kind*: **same** = every account asked the identical
statement (a pass-wide answer); **own ids** = the same question about each account's own rows (one
`IN (...)` per batch answers it); **varies** = cannot be shared.

| / acct | DB ms | asks / distinct | kind | read (owning module) | table | asked from |
|---:|---:|---:|---|---|---|---|
| 118 | 57.5 | 118 / 59 | same | `rating.selectors._authority_tax` (via `plan_tax_rules`) | taxes | gather |
| 40 | 16.2 | 40 / 40 | same | `rating.resolution_catalogue._tier_prices` | rate_tiers | gather |
| 33 | 12.9 | 33, all distinct | same | `rating.resolution_catalogue.charge_code_facts` | charge_code_amounts | gather |
| 25 | 9.9 | 25 / 12 | own ids | `assets.selectors.asset_ids_for_service_point` | assets | gather, readings, disputes |
| 20 | 20.3 | 20 / 5 | own ids | `assets.selectors.assets_on_unit` | assets | gather |
| 16 | 1.8 | 16 / 16 | varies | the per-check savepoints (law 14) | — | every check |
| 16 | 81.8 | 16 / 16 | own ids | `metering.selectors._channel_quantities` (one per channel per meter) | meter_reads | readings |
| 12 + 12 | 10.0 | 24 / 8 | same | `rating.resolution_catalogue.base_code_sizes_for` | charges, charge_code_amounts | gather |
| 12 + 10 | 5.9 | 22 / 8 | same | `metering.selectors._service_code`, `metering.seams.service_ids_for_codes` | services | gather |
| 10 | 5.4 | 10 / 4 | own ids | `metering.selectors._service_point_for` | service_points | gather |
| 8 + 8 + 6 + 4 | 11.8 | 26 / 22 | same | `rating.resolution_catalogue.size_classes_for`, `schedule_version_facts` | rate_size_rows, rate_tiers, tariff_versions | gather |
| 4 + 4 + 4 | 7.6 | 12 / 10 | same | `rating.selectors.base_charge_from_charge_code`, `plan_tax_rules` | charges, charge_code_amounts, plan_tax_rules | gather |
| 4 | 23.1 | 4 / 4 | own ids | `metering.selectors.billing_reads_for_unit` | meter_reads | readings |
| 3 + 3 + 2 + 1 | 48.7 | 9 / 9 | own ids | `read_analysis_for_unit`, `_prior_head_day`, `billing_multiplier_for`, `dispute_holds_for_unit` | meter_reads | readings, gather, disputes |
| 5 | 2.4 | 5 / 2 | same | `tenancy.selectors.unmetered_service_codes` | tenant_services | gather, readings |
| 11 | ~7 | 11 / 11 | same | plan, schedule, discount and outside-city facts (`resolution_catalogue.*`), one each | rate_plans, plan_services, plan_rate_schedules, discount_versions, plan_discount_rules | gather |
| 30 | ~21 | 30 / 26 | own ids | unit row, service points, agreements, exemption, disconnects, discounts enrolled, contact, previous bill window (×2), last billed read ids, asset assignments, counts and sizes, plan history | units, service_points, service_agreements, tax_exemption_certificates, disconnect_cases, discount_enrolments, contacts, invoices, asset_assignments, unit_plan_assignments | gather, readings, period start, decisions, mid-period |
| 4 | 1.6 | 4 / 4 | varies | saving the account's result and findings | bill_run_account_checks, bill_run_findings | save |

By family (statements · DB ms per account):

| Family | Statements | DB ms | Kind |
|---|---:|---:|---|
| Taxes | 124 | 60 | 122 same, 2 own ids |
| Plan / rate schedule | 78 | 36 | 76 same, 2 own ids |
| Charge codes | 66 | 28 | same |
| Meters (assets) | 54 | 40 | own ids |
| Service points / units | 46 | 18 | 27 same, 19 own ids |
| **Readings** | **29** | **118–154** | own ids — the costliest DB time per statement, see §5 |
| Savepoints | 16 | 2 | stays |
| Saving the result | 4 | 2 | stays |
| Previous bills | 4 | 2 | own ids |
| Agreements | 2 | 1 | own ids |
| Customer (contact, disconnects) | 2 | 1 | own ids |
| **Payments** | **0** | — | **already one read per 500** (`CheckContext.load_payment_facts`) |
| **Deposits** | **0** | — | read from the account row already in hand (C8) |
| **Audit** | **0** | — | the Check writes no audit rows |

**Repeats inside ONE account:** of 425 statements, 285 are distinct; **140 are the same account asking the
same thing again** — every tax row twice, each meter list four times, each service code three times.

## 4 · Candidate batch loads, in priority order

Ordered by statements removed per account, then by risk. "Same" reads are the cheapest to share: they
already have the pass-cache shape (`seam_batch.pass_cache()` memoises eight seams for the pass; these reads
are below those seams, inside the R1–R7 chain, and are not in it). Its rule applies unchanged — *a plural
seam asks the SAME question for many accounts and must not answer a different one*: a memo keyed on the exact
arguments, never a new rule.

| # | What is loaded once per batch | Removes / acct | DB ms saved / acct | Kind | Risk |
|---|---|---:|---:|---|---|
| 1 | **Taxes**: the plan's tax rules and each authority's tax rows, keyed by (jurisdiction, kind, service date) | ~122 | ~60 | same | Low. Money figure: key MUST include the service date (`DEF-RAT-8051`'s date window) |
| 2 | **Rate schedule facts**: versions, tiers, size rows, discount and outside-city facts, keyed by (plan, service, version, price date) | ~76 | ~35 | same | Low. Money figure; key by version id and price date |
| 3 | **Charge codes**: amounts, base codes and their sizes, keyed by (charge, customer class, size) | ~66 | ~28 | same | Low. Money figure |
| 4 | **Service lookups**: service codes/ids, unmetered services | ~27 | ~8 | same | None — reference data |
| 5 | **Meters**: assets on each unit, per service point, in service, counts and sizes — one query for the batch's units | ~54 | ~40 | own ids | Low. Must not cross a unit's assignment dates |
| 6 | **Readings**: the batch's meters' reads for the period and the prior anchor — one query, then split per meter and channel | ~29 | ~118–154 | own ids | **Medium.** Money-relevant; see risk (b). Fixing `DEF-BIL-8490` alone recovers most of the DB time without batching |
| 7 | **Service points, unit rows, agreements, previous-bill windows, exemptions, contacts, disconnects, discount enrolments, plan history** | ~23 | ~15 | own ids | Low |

Left per account after all seven: **the 16 per-check savepoints and the 4 saves (~20)**, plus each batch
load's few statements spread over 500 accounts (well under 1 per account).

## 5 · Estimated gain

Measured today: **~690 ms and 425 statements per account** (683 at 100, 693 at 5,000). DB time ~300–345 ms of that; the rest is Python.
The estimate below is arithmetic on the profile, **not a measurement** — B27 step 3 measures the "after".

| After | Statements / acct | Estimated ms / acct | 40,000 on 1 worker | 40,000 on 8 workers (80 batches) |
|---|---:|---:|---:|---:|
| Today | 425 | ~690 | ~7.7 h | ~58 min |
| `DEF-BIL-8490` fixed only (readings prune to one partition) | 426 | ~560–580 | ~6.3 h | ~48 min |
| Loads 1–4 ("same" reads, once per batch) | ~135 | ~400–460 | ~4.8 h | ~36 min |
| Loads 1–7 (all) | ~20 | **~150–250** | ~1.7–2.8 h | **~13–21 min** |

How the ms were estimated: the DB time of each removed group (measured, §3) plus the ORM cost of issuing
it, taken as 0.3–0.5 ms per statement, minus a few ms per account for the batch loads themselves. Only loads
1–7 together meet S1 (≤ 30 min at 40,000 on 8 workers); loads 1–4 alone do not.

**Meter-reading partitions (`DEF-BIL-8490`).** Every period-bounded `meter_reads` read filters
`read_at__date__gte / __lte`, which PostgreSQL receives as `(read_at AT TIME ZONE 'UTC')::date`, so it cannot
prune the 28 monthly partitions. The same statement, warm: **2.9 ms planning + 1.6–1.9 ms execution** as
issued, against **0.2–0.3 ms + 0.05–0.09 ms** on `read_at >= '2026-09-01T00:00Z' AND read_at < '2026-10-01T00:00Z'`.
It grows by 12 partitions a year whatever the tenant's size.

## 6 · Risks

**(a) Tenant scoping (hard rule 1, RLS FORCE).** A batch load is one `IN (...)` inside the job's
`tenant_context`, so RLS still filters every row. The cache must live on the batch (the `pass_cache()`
pattern: opened and closed by the pass, never module-global), because B28 runs batches of different utilities
in the same worker processes; a cache that outlived its batch would hand one utility's tax rows to the next.

**(b) Money reads must not go stale inside a batch — and one already does (`DEF-BIL-8491`).** Payment facts
are loaded once per 500 today, and each result is stamped `checked_at` when it is **saved**. The staleness
sweep re-checks an account only for a payment changed **after** that stamp. So a payment recorded after the
batch loaded and before the account was saved is in neither. Reproduced on PostgreSQL (`bbr_check_cost.py
race`): a $120.00 payment posted Oct 1 lands while account 1 of 3 is being saved; account 3 saves
`[service_not_connected]`, the sweep says **not stale**, and a fresh check finds
`[paid_after_cutoff, service_not_connected]`. The window is the batch's length — up to **~5.7 minutes** at
~690 ms × 500. Batch-loading readings or plans the same way would open the same hole for them. **The fix is a
precondition of B27:** stamp each result with the instant its facts were read (the batch load time), so a
change after the load is always newer than the stamp.

**(c) Rate, tax and charge facts inside one batch.** Today every account re-reads them, so a price edited
mid-pass reaches the next account. With a batch memo, a batch uses one answer throughout — the same
behaviour `pass_cache()` already has for the eight seams it covers, for the whole pass. With (b) fixed, a
plan or tariff edit after the load is newer than every stamp in the batch and the sweep re-checks them.

**(d) The savepoints stay.** Each check runs in its own savepoint (law 14); a batch load happens before the
first account and outside any account's savepoint, so a failed batch read is a batch-wide fault (B21's
utility-wide stop), not a per-account finding. Loading must not move inside an account's savepoint.

**(e) Memory.** A batch of 500 of these accounts is ~6,000 readings, ~2,000 meters and a few hundred
plan/tax rows — small. It must stay bounded by the batch, not grow with the tenant.

**(f) The estimate assumes this account shape.** A utility with many plans shares less of the "same" reads
per batch; one with one or two services per account starts cheaper than ~690 ms.

## 7 · Which code this measured, and what to re-take

Measured on branch `claude/upbeat-dirac-olttw0` at `8602c60b8` (the Check engine of 2026-09-30 before the bulk
lane's 2.413.0 merge, which split the Check's findings into categories). The **timings and the statement
totals stand as the "before"** for B27. The **per-read grouping in §3 should be re-taken on 2.413.0** before
anyone builds from it: it takes about 15 seconds on the seeded database —
`bbr_check_cost.py profile --k 10 --explain 4` — and a changed Check may have moved reads between steps. It
has not been re-taken here.

**Reproducing.** Database `sbh_b27cost` on the cluster at `127.0.0.1:55433` (data directory
`/tmp/pg16_a5c/data`) holds the tenant, the template and 5,000 clones in cycle `B27-COST`; the role is
`sbh_b27` (password `sbh_b27`, no superuser, no BYPASSRLS). The cycle can only grow — clones carry issued bills
and payments, which may not be deleted — so a smaller size is measured with `measure --subset`.

**Defects filed:** `DEF-BIL-8490` (meter-reading partitions not pruned), `DEF-BIL-8491` (a payment during a
batch is missed and never flagged stale — reproduced by `bbr_check_cost.py race`), `DEF-BIL-8492` (the 137 ms
figure the PO was shown).


## 8 · After — B27 built (`2.416.0`, 2026-09-30)

**In one paragraph.** Each batch of 500 now reads its data once. The Check costs **about 47–54 ms and
24–26 statements per account** (from ~690 ms and 425), measured the same way on the same database, role
and accounts. On one worker that is **~31 minutes at 40,000 accounts** (from ~7.7 hours). The engine's
answer is unchanged: every account's findings, status and gathered bill are compared both ways by
`06-backend/tests/test_b27_batch_reads.py` on a mixed seed, and on this PostgreSQL seed on 20 accounts
(identical).

### 8.1 · The profile re-taken on 2.413.0 before building (the category split)

`profile --k 10 --explain 4` on `a7621aa0c` (2.413.0): **429 statements and 747 ms per account** (the
recorder's stack walk included; load 2.1). The grouping in §3 held: the same reads, in the same order of
cost — `_authority_tax` 118, `_tier_prices` 40, `charge_code_facts` 33, `assets_on_unit` 20+4,
`_channel_quantities` 16, `asset_ids_for_service_point` 25, … The category split moved no read between
steps that mattered here.

### 8.2 · What was built

| # (§4) | Loaded once per batch | Where (the owning module's own read) |
|---|---|---|
| 1–4 | Taxes, rate schedule facts, charge codes, service lookups — memoised per batch on every argument (the service date included) | `rating.selectors`, `rating.resolution_catalogue`, `metering.selectors`, `metering.seams`, `tenancy.selectors` (`@batch_reads.memoised`) |
| 5 | Meters on each point and unit, in-service meters, counts and sizes | `assets.selectors.prime_check_batch` (4 queries) |
| 6 | Readings: every meter's heads from the earliest last-bill start in the batch onward, the prior head of each undated read, open disputes | `metering.selectors.prime_check_batch` (6 queries) |
| 7 | Units, service points; agreements, contact names, dark days; plan history, exemption certificates, discount enrolments; the last issued bill | `metering`, `customers.selectors.prime_check_batch` (3), `rating.selectors.prime_check_batch` (3), `billing.batch_seams.prime_billing_history` (4) |

The mechanism is `06-backend/core/batch_reads.py`: one memo per batch, bound to the tenant it was opened
for (it answers nothing while another tenant is current) and discarded in a `finally` when the batch ends,
so nothing outlives the batch (the `seam_batch` ruling). A batch read that fails is skipped and logged;
each account then asks for itself, as before — slower, never different.

**`DEF-BIL-8491` fixed first:** every saved result is stamped with the batch's READ time (taken before its
first read). `bbr_check_cost.py race` on PostgreSQL: before the fix *"RACE REPRODUCED … sweep says stale:
False"*; after, *"sweep says stale: True"* and the re-check finds `paid_after_cutoff`.

**`DEF-BIL-8490` fixed:** metering's selectors filter a `read_at` range. EXPLAIN (ANALYZE) of a period
read on one meter, the statement Django issues, warm:

| | Partitions in the plan | Planning | Execution |
|---|---:|---:|---:|
| Before (`read_at__date__gte/lte`) | **28** | 2.853 ms | 0.975 ms |
| After (`read_at >= day start AND < next day start`) | **1** (`meter_reads_2026_09`) | 0.189 ms | 0.033 ms |

Twelve `__date` uses outside `metering/selectors.py`, not on the bill run's path, remain (`DEF-BIL-8602`).

### 8.3 · The figures

Same method as §1 (`measure --subset`, one discarded warm-up, median of 3). The machine was shared and
**loaded 10–12 on 4 cores** throughout (the "before" ran at 2–4), so the times are, if anything, high.

| Accounts | Median | ms / account | Statements | Statements / account | Runs (s) |
|---:|---:|---:|---:|---:|---|
| 100 | 5.4 s | **54** | 2,588 | **25.9** | 5.2 · 5.7 · 5.4 |
| 1,000 | 46.9 s | **47** | 23,501 | **23.5** | 49.9 · 46.9 · 37.9 |

Profile (`profile --k 10`): **23 statements per account** — the 16 per-check savepoints and 2 of the plan
notice (law 14, they stay), and 5 to save the result (one of them the read-time stamp). No read is left
per account on this account shape.

### 8.4 · Extrapolated

A straight line through the two sizes is **0.8 s fixed + 46 ms per account**.

| Accounts | Before, one worker | After, one worker | After, 8 workers in batches of 500 (ideal split) |
|---:|---:|---:|---:|
| 1,000 | ~11.6 min | **~0.8 min** | 2 batches: ~0.4 min |
| 10,000 | ~1.9 h | **~7.7 min** | ~1 min |
| 40,000 | ~7.7 h | **~31 min** | **~4 min** (80 batches, 10 per worker) |

Against S1 (≤ 10 min at 10,000, ≤ 30 min at 40,000): met at 10,000 on one worker; at 40,000 it needs two
workers, or the 8 of B28. The 8-worker column assumes the database keeps up with eight batches at once,
which is **not measured here** — B28 proves it at 40,000.

**What this does not measure:** other account shapes (a master account's other units, an account whose
last bill is more than 92 days back, an account with a discount enrolment each read their own rows, as
before — correct, a little slower); B28's parallel batches.

## 9 · B28 — the Check in parallel batches of 500 (`2.418.0`, 2026-10-01)

**In one paragraph.** On the J73 world at **40,015 accounts** (real PostgreSQL 16, role `sbh_b27`, no
BYPASSRLS, real Celery workers on the `billing` queue), the batched Check is **correct at scale** — 81
batches, never more than the cap running at once, every account saved exactly once, the totals counted
once — but **on this machine it was not faster**: the old one-pass Check took **8.0 min** and the batched
one **9.1 min** with two batches at a time. The reason is the machine, not the design, and it is
measured rather than assumed: during the batched runs four other lanes' test processes held the four
cores at 50–100 % each (load 5.6–6.0), so a second batch had no core to run on; the one-pass run had
the machine at load 2–3. **The speed-up at 8 workers is therefore an ESTIMATE below, not a measurement.**

### 9.1 · Method

| | |
|---|---|
| Script | `10-scripts/b28_parallel_check_proof.py` — `before` (the Check in one process, `check_store.check_run`) and `after --slots N --cap K` (a private redis, ONE Celery worker with `--concurrency N` on `-Q billing`, the Check enqueued through `run_jobs.enqueue_check` as `POST …/check` does, the job records polled every 2 s) |
| Database | `sbh_b28_40k` — a copy of the J73 `sbh_j73_40k` world, migrated to the tip and topped up to 40,000 `J73S-` accounts by `manage.py seed_j72_bulk_run --accounts 40000` (7,000 clones 34 s, 4,000 payments 248 s), plus J72's 15 |
| Account shape | J73's: water on 1–2 meters, electric, trash 1–2 carts, sewer; one in ten with a payment. **Lighter than §1's** (12 ms/account here against 47–54 ms there), which is why every figure here is smaller than §8's |
| "Before" | the tip at `da1ba0a90` (`2.417.0`, B27 built, B28 not) in its own worktree, same database |
| Timing | one pass each — a 40,000-account pass is 8–11 minutes on a shared machine and no warm-up was discarded; read the times as ±15 % |

### 9.2 · The figures

| Run | Code | Workers · cap | Load (start → end) | Wall | ms / account | Batches | Most batches running at once | Saved once each |
|---|---|---|---|---:|---:|---:|---:|---|
| Before | `2.417.0` one pass | 1 process | 2.1 → 3.1 | **479.1 s (8.0 min)** | 12.0 | — | — | 40,015 · 0 twice |
| After, first build | `2.418.0` | 4 slots · cap 2 (the ruled half) | 3.2 → 6.0 | 678.7 s (11.3 min) | 17.0 | 81 | **2** | 40,015 · 0 twice |
| After, scope read once | `2.418.4` | 4 slots · cap 2 | 5.6 → 5.6 | **544.1 s (9.1 min)** | 13.6 | 81 | **2** | 40,015 · 0 twice |

Every "after" run: the coordinator ended `succeeded`, *n of N* read **40,015 of 40,015**, every saved
row carries the Check's own job id, `findings_summary` names that job, and the per-utility cap held — the
most batch jobs ever queued or running for the utility was **2**, the cap.

**What the first build cost, found by profiling one batch, and fixed:** each batch asked Meter Reads for
the cycle's 40,000 units twice (~1 s a call) and its pass re-ran the 40,000-unit scope query on each of
its three walks. A batch now resolves the units once and reads its 500 accounts once
(`runs.open_scope_units`): one 500-account batch measured **5.9 s** of work afterwards. The fixed cost
of the whole Check outside the batches is **plan 1.7 s** (the 40,015 account numbers) and **≈ 8 s at the
end** (the units nobody bills, 7.9 s, then the tiles) — paid once.

### 9.3 · Eight workers — an ESTIMATE, labelled as one

Not measured: this machine has four cores, and other lanes held them. Worked from the figures above:
80 batches at **~6 s** each (5.9 s measured for one batch on the loaded machine), 8 workers → **cap 4**,
so 20 rounds of 4: **~2 minutes**, plus ~10 s of plan and final count → **≈ 2–2.5 minutes at 40,000**,
against 8.0 minutes on one process. That assumes each worker has a core of its own and that PostgreSQL
keeps up with four batches at once; the four-core run above shows what happens when neither is true
(no gain). It is well inside S1 (≤ 30 minutes at 40,000) either way — so is the one-process figure on
this account shape.

**What this does not measure:** a quiet machine; two utilities' Checks side by side (S4 — the cap's
point; the cross-utility behaviour is proved by `test_b28_5__one_utility_never_runs_more_batches_than_its_cap`,
not timed); §1's heavier account shape at 40,000.

**Run audit afterwards:** `10-scripts/verify_bulk_run.py RUN-0002` on `sbh_b28_40k` (stage CHECK):
**PASS**, 40,015 accounts, every one PASS on every applicable check, no red row. (Run as the owning role:
under `sbh_b27` the script found the run as *0 rows* — its run lookup reads before it sets the tenant.)

## 10 · S1–S4 at 10,000 and 40,000 — the clerk's scale checks timed (2026-10-01)

**In one paragraph.** The Check meets S1 with room to spare: **70 s at 10,015 accounts and 5.6 min at
40,015** on four worker slots, 13.1 min on two. A second utility's run starts within a second while a
40,000-account Check runs (S4). The screens and the Send do not hold at 40,000: **Sign off's summary read
takes 4–6.5 minutes**, so behind a production web worker (killed at 60 s) Sign off never shows its
figures; a tag's account list takes **3.3 s**, almost all of it a whole-run sweep run before every read;
and **Send issues about 1.9 bills a second — about 5.8 hours for 40,000** — and a Send whose worker dies
does not carry on by itself. What Send writes at 40,000 is right: every authorised bill once, no number
twice, every journal balanced, a second Send writing nothing.

### 10.1 · Method

| | |
|---|---|
| Code | `2.418.6` for S1 and the first S2 reads; `2.418.7`–`2.418.8` for Calculate, the browser and the start of the Send; `2.421.x` for the resumed Send; `2.423.0` for S4 and the S2 re-read after `DEF-BIL-8682`'s batching. Each row says which |
| Database | PostgreSQL 16 at `127.0.0.1:55433`, role `sbh_b27` (no superuser, no BYPASSRLS) for every timed figure. **40,000:** `sbh_s14_40k`, a copy of B28's `sbh_b28_40k` (40,015 accounts) with a second utility, `perf-utility-1` (199 accounts), provisioned through the signup service by `10-scripts/cr051_provision_utilities.py` (with `SBH_FIXTURE_TODAY=2026-09-30`: on the 1st of a month its sample plant lands short, `DEF-MET-8693`). **10,000:** `sbh_s14_10k`, a copy of `sbh_j73_10k` migrated to the tip. `sbh_s14_40k` is kept, sent, for reproduction |
| Workers | ONE real Celery worker on `-Q billing`, a private redis. **S1 and the first S4: `--concurrency 4` → `BILLING_WORKERS=4`, cap 2** (the ruled half). Second S4 (and a second 40,000 Check inside it): 2 slots → cap 1, the `docker-compose.yml` default |
| Scripts | S1: `10-scripts/b28_parallel_check_proof.py after --slots 4 --cap 0`. S2 server, Calculate, Sign off, Send, the database checks, S4: `10-scripts/j73_scale_proof.py` (`s2-server`, `calculate`, `sign-off`, `send`, `send-resume`, `db-verify`, `s4`). S2 browser: `07-frontend/e2e/J73-s2-screen-timing.spec.ts` (Chromium 1194 at 1440, the browser's own `performance.now()` from the click or the navigation's start to the first frame the data is on the page) |
| Load | Every timed run waited for a 1-minute load average under 2 (up to 30 min) and records the load before, during (every 10 s) and after. Two other lanes ran tests through the afternoon; **the machine never stayed quiet** — "during" includes our own workers and PostgreSQL. Read every time with its load beside it |
| Web server for the browser | gunicorn, 3 workers, `--timeout 60` — the production entrypoint's own settings (`docker-entrypoint.sh`). A first pass behind `runserver` (no timeout) is quoted where it shows the full length of a read |

### 10.2 · S1 — the Check

| Accounts | Code | Slots · cap | Load before · during (median / max) · after | Wall | ms / account | Batches | Most running at once | Saved once each |
|---:|---|---|---|---:|---:|---:|---:|---|
| 10,015 | 2.418.6 | 4 · 2 | 1.83 · 3.09 / 3.74 · 3.74 | **70.3 s** | 7.0 | 21 | 2 | 10,015 · 0 twice |
| 40,015 | 2.418.6 | 4 · 2 | 1.80 · 3.48 / 4.04 · 3.10 | **337.1 s (5.6 min)** | 8.4 | 81 | 2 | 40,015 · 0 twice |
| 40,015 | 2.423.0 (inside S4) | 4 · 2 | 1.85 · 2.69 / 2.99 · 2.72 | 395.2 s (6.6 min) | 9.9 | 81 | 2 | 40,015 |
| 40,015 | 2.423.0 (inside S4) | 2 · 1 | 1.86 · 1.70 / 1.95 · 1.80 | 785.1 s (13.1 min) | 19.6 | 81 | 1 | 40,015 |

Against S1 (≤ 10 min at 10,000, ≤ 30 min at 40,000): **met at both sizes on every worker count measured.**
B28's 9.1 min at load 5.6 (§9) was the saturated figure; at load ~3 the same code takes 5.6 min.

### 10.3 · Calculate (not an S-criterion; S3 needs it)

| Accounts | Code | Load before · during (median / max) · after | Wall | Drafts | Breaks |
|---:|---|---|---:|---:|---:|
| 40,008 | 2.418.7 | 1.46 · 2.24 / 3.91 · 2.51 | **1,341.8 s (22.4 min)** | 40,008 | 0 |

About 6 minutes of it is the prepare pass, during which the job shows no total and no movement; the
pricing then runs at ~42 accounts a second with *n of 40,008* moving. **The default deployment refuses this
run:** `BILLING_MAX_ACCOUNTS_PER_RUN` is 25,000 and the PO kept it there (`DEF-BIL-4224`); the operator's
override (`0`) was typed for this measurement, and a 40,000-account utility needs it typed in production
too. A niced front-end build ran during part of it.

### 10.4 · S2 — the three screens

**The server's reads, in-process through the real views** (`j73_scale_proof.py s2-server`, 5 samples):

| Read | 40,015 checked, no drafts (2.418.6, load 1.8–2.1) | 40,008 drafts (2.418.7, load 1.0–2.3) | 40,008 drafts (2.423.0, load 1.8–2.1) |
|---|---:|---:|---:|
| A tag's accounts (`check/findings?tag=`, a 2-account tag) | 3.20 s p50 (3.60 max) | 2.90 s | 3.50 s |
| The categories (`check/findings`) | 3.41 s | — | — |
| Ready (`check/findings?list=ready`, 40,008 rows, page of 50) | 3.83 s | — | — |
| Sign off (`sign-off-summary`) | 2.14 s | **395.9 s** | **258.7 s · 250.3 s** |
| Sign off's other read (`summary`, Send's count and total) | — | 11.2 s | 11.8 s |
| Not in this run (`not-in-run`, page 1 of 50) | 0.65 s | 0.83 s | 1.11 s |

Where the time goes, profiled: every `check/findings` read first runs `check_staleness.sweep` over the whole
run — **3.08 s at 40,015**, three of its nine queries carrying a 40,000-id `IN` list — and the tag's page
itself is **0.02 s** (`DEF-BIL-8694`). Sign off's `_payments_and_balances` asked three questions per account
(~120,000 queries, 396 s); `2.422.3`'s batching (`DEF-BIL-8682`) took it to ~255 s, still far over the bar
(`DEF-BIL-8696`). `summary` is 22 queries and 11 s of Python over every draft (`DEF-BIL-8697`).

**Paged (NFR-3):** each list asked for 100,000 rows in one page answers at most **1,000** — the Ready list
1,000 of 40,008 (496 KB, 4.8 s), the tag list and Not in this run their whole (small) count — with the
total served beside the page. No list serves 40,000 rows.

**In the browser** (Chromium at 1440, gunicorn 3 × 60 s):

| Screen | Measured | Its read | Load | Note |
|---|---:|---:|---|---|
| Sign off (open the run) | **never** — figures still `—` | `sign-off-summary` **500 after 66 s** (worker killed at 60 s) | 3.0–3.5 | behind `runserver` (no timeout) the figures painted after **311 s** |
| A tag's account list (click → first row) | **3.3 s** | 3.2 s | 2.5 | the run at Check, no Sign off read in flight; with one in flight the same click took 45–60 s, the Sign off read holding the workers |
| Not in this run (navigation start → first row) | **2.5 s** | 1.2 s | 3.0 | a cold page load (bundle, run, Sign off reads beside it) |
| Ready (click) | 0.08 s | none | 3.5 | already loaded with the Check screen |

### 10.5 · S3 — Send 40,000 bills, with the worker killed part-way

| Step | Code | Load | Figure |
|---|---|---|---|
| Sign off (`POST …/release`, five confirmations) | 2.418.8 | 2.0–2.3 | 11.6 s; **40,008 bills, $7,371,531.12** authorised |
| Send, product code | 2.418.8 | ~3.2 | **1,527 bills in 13.3 min — 1.9 a second; 40,008 would take ~5.8 hours** |
| Worker SIGKILLed at 1,527 issued; a fresh worker; 180 s watched | 2.421.x | 1.8–2.3 | nothing moved: the job still `running`, *1,525 of 40,008* frozen, already judged abandoned |
| Send pressed again while stuck | | | **202 with the same stuck job** — it re-attaches, it does not restart |
| Handed back by hand (`run_jobs.resume_job`, the Check's Resume path; the Send has no door to it) | | 3.5–5.9 | carried on from the next draft: 1,097 more in 601.8 s (**1.82 a second**); issue audits = bills issued; its progress restarted at *0 of 38,481* |
| Worker SIGKILLed again at 2,624; **an experimental index** `(tenant_id, id)` on `invoice_lines`, in this test database only and dropped afterwards; handed back | | 1.65–10.8 (median 4.5) | the GL-stamp update fell from **68 ms to 2.1 ms**; the remaining **37,384 bills in 5,726 s (6.5 a second)** |

Why 1.9 a second: issue stamps each line's GL account with `UPDATE invoice_lines … WHERE id = X`, and the
partitioned `invoice_lines` has primary key `(tenant_id, created_at, id)` and no index leading with `id`, so
each update scans the partition — **300,695 rows removed by filter, 68 ms, ~7.5 lines a bill**
(`DEF-BIL-8708`). It grows with every month of lines the utility keeps. Not measured, worked from these
figures: a Send task is given `CELERY_TASK_TIME_LIMIT` = 8,520 s, which at 1.9 a second is ~16,000 bills, so
on the product code a 40,000-bill Send would be stopped part-way by its own time limit.

**The database afterwards** (`j73_scale_proof.py db-verify`, RLS-enforced):

| Check | Result |
|---|---|
| Bills in the run · issued · still draft | 40,008 · **40,008** · 0 |
| Authorised in the release · releases · released | 40,008 · 1 · 1 |
| Invoice numbers used twice (whole utility) · accounts issued twice in the run | **0** · **0** |
| Issue audit rows · bills with two | 40,008 · **0** |
| Issued bills with no journal · with two · journals unbalanced | 0 · 0 · **0** |
| Journal debits · credits · issued bills' total | $7,371,531.12 · $7,371,531.12 · $7,371,531.12 |
| Send breaks | 0 |
| A second Send | **200, `created: false`**; issued, drafts and audits unchanged |

**Run audit** (`10-scripts/verify_bulk_run.py`, as the owning role — `DEF-BIL-8692` — by run id, because the
second utility also has a RUN-0002): stage SENT, **40,014 of 40,015 accounts PASS every applicable check**
(issued, numbered, bill = draft, journal balanced, delivery queued — 80,016 rows, reads locked, one audit,
second Send wrote nothing, no job left pending). One red row: AC-2026-00003, an unanswered *No reading*
held in Not in this run as `DEF-BIL-8650` ruled, which the audit counts as should-bill (`DEF-BIL-8722`).

### 10.6 · S4 — another utility's run while one runs 40,000

`j73_scale_proof.py s4`: Brazos Bend's 40,015-account Check enqueued; when it reached 5,000, utility B's
(199 accounts) enqueued; both polled every second.

| Slots · cap | Load before · during (median / max) · after | A when B pressed | B running | B's first progress | B done | A meanwhile | A's whole Check |
|---|---|---|---:|---:|---:|---|---:|
| 4 · 2 | 1.85 · 2.69 / 2.99 · 2.72 | 5,000 of 40,015, 2 batches | **≤ 1 s** | 2 s | **4 s** | kept its 2 batches | 395.2 s |
| 2 · 1 | 1.86 · 1.70 / 1.95 · 1.80 | 5,000 of 40,015, 1 batch | **≤ 1 s** | 2 s | **4 s** | kept its 1 batch | 785.1 s |

The cap held both ways: A never ran more than its half, and B's coordinator and batch took the free slots.
"≤ 1 s" is the poll's resolution.

### 10.7 · What this does not measure

A quiet machine (it never stayed under load 2 for a whole run); 1280 in the browser (S2 was walked at 1440
only); the Send on the product code to the end (killed at 1,527 and 2,624 on purpose, then finished with an
experimental index — the 5.8 hours is worked from 1.9 a second, not watched); the broker's own re-delivery
after 8,820 s (the private redis did not run that long); gunicorn under several clerks at once; eight
workers.

## 11 · S3 re-timed — the Send in batches of 500, an index on the line id, and a dead worker handed back (2026-10-01)

**In one paragraph.** Send now runs at **about 11–12 bills a second** at 40,000 (it was 1.9), so **a
40,008-bill Send takes about an hour instead of about 5.8 hours**, and it is cut into 81 batches of at most 500,
so no task comes near its 8,520-second limit. **Every time a worker was killed, the Send carried on by itself.**
The Send screen's own read handed it back **16–19 seconds** after a fresh worker was up, reading the bills
already sent and never 0. Pressing Send again on a dead Send did the same. Afterwards, from the database:
**40,008 of 40,008 issued, no invoice number twice, one issue audit and one balanced journal each
($7,371,531.12 both sides), and a second Send wrote nothing.** On the way, two new defects were filed and one
was fixed. A kill left **985 bills that had gone out still listed as not sent** (`DEF-BIL-8746`, fixed). And
a deployment whose code was one migration ahead of its database **failed 22,640 bills one by one** instead of
stopping the Send (`DEF-BIL-8747`, open; *Retry failed* recovered every one).

### 11.1 · Method

| | |
|---|---|
| Code | `2.426.0` (batched Send, `DEF-BIL-8726` / `8710`) on `2.424.0` (billing 0037, `ix_invoice_lines_id`, `DEF-BIL-8708`); the open-break sweep (`DEF-BIL-8746`) is `2.428.2` and was applied to this world after the Send |
| Database | **`sbh_send40k`**, a fresh J73 world built for this: `sbh_j73` copied, migrated, `seed_j72_bulk_run --accounts 40000` (644 s), Checked (`b28_parallel_check_proof.py`, 4 slots), Calculated (2,118.6 s, 40,008 drafts, 0 breaks), Signed off (**40,008 bills, $7,371,531.12**, the same figures as `sbh_s14_40k`). RLS-enforced role `sbh_b27` for every timed figure. PostgreSQL 16 at `127.0.0.1:55433` |
| Workers | ONE real Celery worker, `-Q billing --concurrency 4` (`BILLING_WORKERS=4`), a private redis on 6431. The Send cap per phase as stated: **1** (one batch at a time, the old single task's parallelism) or **2** (the ruled half of 4) |
| Script | `10-scripts/j73_scale_proof.py send-scale --phases …`. Each phase but the last ends in a SIGKILL of the whole worker group. **Nothing hands the Send back except the Send screen's own poll** (`GET …/issue/progress`, every 2 s, as `BulkRunPage.send()` polls). `noindex` drops `ix_invoice_lines_id` for its phase, which stands for the code before `2.424.0` on the same world |
| Load | Each run waited for a 1-minute load under 2. The load is recorded at every 10 s sample. Another lane's browser walk and test runs shared the machine, so "during" is not quiet |

### 11.2 · Bills a second

| Phase | Index | Cap | Load start · median / max | Seconds | Bills | **Bills a second** |
|---|---|---|---|---:|---:|---:|
| Before (§10.5, `2.418.8`, one task) | no | (1) | ~3.2 | 798 | 1,527 | **1.9** |
| A1 · no index, one batch at a time | no | 1 | 2.05 · 2.27 / 3.61 | 240.4 | 966 | **4.0** |
| A2 · index, one batch at a time | yes | 1 | 1.37 · 2.09 / 3.89 | 301.8 | 1,705 | **5.7** |
| A3 · index, two batches at a time | yes | 2 | 2.23 · 2.89 / 5.50 | 512.0 | 5,731 | **11.2** |
| B1 · *Retry failed* Send, index, cap 2 | yes | 2 | 2.07 · 4.24 / 5.35 | 241.6 | 2,984 | **12.4** |
| B2 · the same Send after a kill, to the end | yes | 2 | 4.71 · 5.40 / 6.90 | 1,808.2 | 19,655 | **10.9** |

A1 and A2 each include the 16–20 s before the hand-back, when nothing is issued, so they understate. The
index alone is worth about 1.4× here, against 32× on the one statement it fixes (68 ms → 2.1 ms, §10.5):
the rest of a bill's work is now the larger part, and A1's 4.0 (against §10.5's 1.9 at a higher load) already
shows that half of the old figure was the machine. Two batches side by side doubled it again. **At ~11 a second, 40,008 bills are
about 61 minutes on 4 worker slots (cap 2). This is worked from the measured rate: no single run went from
0 to 40,008 without being killed (11.4).** A batch of 500 at that rate is ~90 s of work, against
`CELERY_TASK_TIME_LIMIT` = 8,520 s.

Sampled during A3 (`pg_stat_activity`, 300 samples): the GL stamp `UPDATE invoice_lines … WHERE id = …` was
still the most frequent statement, at 17 of ~140 active samples. Most samples found the connections idle,
which means the time is in Python. `meter_reads` locking did not appear (32 ms + 16 ms of planning per read
when measured by hand on `sbh_s14_40k`, without an `id` index; not a hot spot at this rate).

### 11.3 · A dead worker, handed back by the screen

| Kill | Issued at the kill | How it came back | After | Progress read at the hand-back |
|---|---:|---|---|---|
| The session's own restart (~10:22), every worker gone | 8,966 | **Send pressed again** → `202`, `resumed: true`, the same job (before: `202` with the stuck job, nothing moved — §10.5) | — | counted from the bills |
| A1 → A2, SIGKILL | 9,932 | the Send screen's poll, **16.1 s** after a fresh worker started | `resumed: true` | **9,916 of 40,008** |
| A2 → A3, SIGKILL | 11,637 | the poll, **16.1 s** | `resumed: true` | **11,616 of 40,008** |
| B1 → B2, SIGKILL | 20,352 | the poll, **19.2 s** | `resumed: true` | **20,318 of 40,008** |

The progress read is the coordinator's last heartbeat, a few bills behind the database. The resumed
coordinator re-counts from the bills at once. It never reads 0: §10.5's hand-back by hand read *0 of 38,481*.

### 11.4 · What happened between, said plainly

1. **Code one migration ahead of the database (`DEF-BIL-8747`, open, medium).** While the Send was handed
   back after the restart, this worktree had taken the tip, which carries billing 0039. `sbh_send40k` was
   still at 0038. Every bill then failed at issue with `column invoice_lines.pricing_trace does not exist`.
   B11's one-bill-one-break rule filed each as a send break (`issue_failed_unexpectedly`): **22,640 in about
   five minutes.** Then the batches "succeeded", and the release was completed with 22,640 drafts left. No
   bill went out wrongly. After `migrate`, a second Sign off and Send (*Retry failed*, runs B1–B2) issued all
   22,640. A system fault should stop the Send, not be reported as 22,640 bill failures.
2. **985 bills that went out stayed listed as not sent (`DEF-BIL-8746`, fixed in `2.428.2`).** The B1 kill
   landed after two batches had issued 985 bills that carried B-run's send breaks, and before those batches
   filed their result. The re-dispatched batches re-select only drafts, so no pass listed those 985 as sent.
   `send_batches.close_breaks_of_sent_bills` now asks the bills at completion. Run on this world after the
   Send, it closed **985**, leaving **0** open. Its case was red first (`assert 1 == 0`).
3. **So the 40,008 were issued by two releases (the original and the *Retry failed* one).** This is the
   product's own path for failed bills. `db-verify`'s *authorised 80,016* is the two rows' `bill_count`
   added together.

### 11.5 · The database afterwards

`j73_scale_proof.py db-verify`, RLS-enforced:

| Check | Result |
|---|---|
| Bills in the run · issued · still draft | 40,008 · **40,008** · 0 |
| Invoice numbers used twice (whole utility) · accounts issued twice | **0** · **0** |
| Issue audit rows · bills with two | 40,008 · **0** |
| Issued bills with no journal · with two · unbalanced journals | 0 · 0 · **0** |
| Journal debits · credits · issued bills' total | $7,371,531.12 · $7,371,531.12 · $7,371,531.12 |
| Releases · released | 2 · 2 (the second is *Retry failed*) |
| Send breaks | 22,640 filed by the fault in 11.4 (1); **all closed `issued`** after the 11.4 (2) sweep |
| A second Send | **200, `created: false`**; issued, drafts and audits unchanged |

**Run audit** (`10-scripts/verify_bulk_run.py`, run by id as the owning role, `DEF-BIL-8692`): see 11.6.

### 11.6 · Run audit

Stage SENT. **40,014 of 40,015 accounts PASS every applicable check**: issued and numbered, the bill
equal to its draft, the journal balanced, delivery queued (80,016 rows), reads locked, one issue audit
each, and a second Send wrote nothing. Every job is done: of 221 job records, the 10 a killed worker or the
column fault left `failed` were each superseded by a later success under the same scope key. The one red
row is AC-2026-00003, the unanswered *No reading* held in Not in this run (`DEF-BIL-8722`, the audit's own).
Two run-level reds come from *Retry failed* and are expected: **2 release rows** and **2 `bill_run.released`
rows**, one each for the original release and the retry. Each authorised 40,008 bills / $7,371,531.12, and
the issued total is the same.

**The audit was wrong twice on a resumed Send (`DEF-BIL-8745`, fixed here).** Before the fix it failed
**22,641 accounts** as *issued + failed*, counting a send break closed `issued` as a failure. It also failed
**every account** on S5.jobs, because a killed worker's reclaimed record still read `failed`. Both runs, red
and then green, are on this world.

### 11.7 · What this does not measure

- One uninterrupted 0 → 40,008 Send. The hour is worked from the measured rates.
- A quiet machine: B2 ran at load 5.4 median.
- Eight workers.
- The broker's own redelivery after 8,820 s.
- The index's effect on a partition holding a year of lines.

## 12 · S2 re-timed — Sign off, its summary and the Check's reads after `DEF-BIL-8696`, `8697`, `8694`, `8720` (2026-10-01)

*(§11 is the Send lane's — `DEF-BIL-8708`'s re-timing of Send cites it.)*

**In one paragraph.** Every S2 read now answers in well under 2 s at 40,000 accounts on the server, and the
figures are the old ones to the last stored place. Sign off's summary went from **250–396 s** (killed at
60 s in production) to **0.50 s**: every module is asked once for the whole run instead of three times per
bill, and the summary is saved on the run under a key of every row it reads, built at the end of
Calculate and rebuilt by the first read after any of those rows is written. Sign off's other read
(`/summary`) went from **11.2 s to 1.0 s**, a tag's account list from **3.2 s to 0.03–0.06 s**, the Ready
list from **3.8 s to 0.26 s**. In the browser the screens' own reads are under 1.3 s, but a **cold** open
of the bulk run page is still 3.3–7.2 s at 10,000, because two side reads the page makes on open —
`/settings/services` (13.6 s) and `/cycles` (2.8 s) — hold two of the three web workers (`DEF-TEN-8731`,
`DEF-MET-8732`); at 40,000 `/settings/services` is killed at 60 s.

### 12.1 · Method

| | |
|---|---|
| Code | `2.426.x` + this lane (`signoff.py`, `core/row_versions.py`, billing `0038`). The "before" column is §10's (`2.418.6`–`2.423.0`) and, where marked, the old code run beside the new on the same database |
| Database | PostgreSQL 16 at `127.0.0.1:55433`, role `sbh_b27` (RLS enforced). **40,000:** `sbh_s14_40k`, the SENT run (40,008 bills) — kept for reproduction, no second 40k copy made. **10,000 at Sign off:** `sbh_d8696_10k`, a copy of `sbh_s14_10k` Calculated by `j73_scale_proof.py calculate` (10,008 drafts, run open). **J72:** `sbh_d8696_j72` (J72 world + `--month-two`'s payment plan, Checked, five tags answered, Calculated; 7 drafts) |
| Scripts | `10-scripts/j73_scale_proof.py s2-server` (5 samples, the real views); `10-scripts/d8696_signoff_parity.py dump / diff / send-compare` (both Sign off reads, old code and new, compared key by key); `07-frontend/e2e/J73-s2-screen-timing.spec.ts` (new `J73_SENT=1`: on a sent run Sign off and Not in this run are timed from the click on step 3) behind gunicorn 3 × 60 s and `server.mjs` |
| Load | every timing waited for a 1-minute load under 2; the load is beside each figure. Two other lanes ran through the afternoon |

### 12.2 · The server's reads (in-process, real views)

| Read | Before (§10) | After · 10,008 at Sign off (open run, load 1.86–1.93) | After · 40,008 sent (load 1.86–1.96) |
|---|---:|---:|---:|
| Sign off (`sign-off-summary`), saved copy | 250–396 s | **0.125 s** p50 (0.155 max) | **0.50 s** p50 (0.505 max) |
| Sign off, the stale path — built afresh in the request | 250–396 s | 1.6–1.8 s | 7.9–8.1 s |
| Sign off's other read (`/summary`) | 11.2 s (29.5 s at load 7, old code) | 0.38 s (load 7) | **0.95–1.0 s** (load 1.86) |
| A tag's accounts (`check/findings?tag=`) | 3.20 s p50 (3.60 max) | **0.062 s** (0.077), the sweep included | **0.034 s** (sent run: no sweep) |
| The staleness sweep's own read (`stale_categories`) | 3.08 s (5.70 s old code, load 7) | inside the 0.062 s above | **0.128 s** p50 (0.197) |
| Ready (`list=ready`, page of 50) | 3.83 s | 0.127 s (0.208) | **0.263 s** (0.274) |
| The categories (`check/findings`) | 3.41 s | 0.175 s | 0.44 s |
| Not in this run (page 1 of 50) | 0.65–1.11 s | 0.249 s | 0.907 s |
| The key the saved copy is checked against (`inputs_key`) | — | 0.11 s | 0.33 s |

**Paged (NFR-3), asked for 100,000 a page:** the Ready list answers 1,000 of 40,008 (0.67 s) and 1,000 of
10,008; the tag list and Not in this run their whole small count.

**Where the time went, and what changed.** (1) Sign off asked payments' open bills, billing's prior totals
and customers' opening balance per bill — ~120,000 statements. Each is now one batched read, and the run's
accounts cross every seam as a SUBQUERY: profiled, binding 40,000 ids as parameters cost ~30 µs of Python
each, 7 s for one read, before PostgreSQL saw the statement. Batched alone, the build is ~8–10 s at 40,000
— five times the bar, because it still reads every bill, line, Check row and payment — so it is saved
(`bill_runs.sign_off_snapshot`, billing `0038`). (2) `release.current_position_bills` loaded every bill as
a model and answered `pk IN (<40,008 ids>)`, carried by every statement after it; it now walks only
superseded bills and answers a filter. (3) The sweep handed metering and payments every unit and account
id of the run; it now asks what changed since the run's oldest check for the whole utility and reads back
only the rows those changes can touch. (4) The Ready list bound 40,008 ready ids twice; it now binds
whichever of the two lists is shorter.

### 12.3 · When the saved summary is stale

The key is, per set of rows, the count and the sums of PostgreSQL's `xmin` and `cmin` (`core/row_versions.py`)
— an insert, an update (a queryset `.update()` that never touches `updated_at` included), a delete, and a
second write inside the transaction that created the row each move it. `cmin` was added after the first
version was **proved blind** by its own case: a draft created and then re-priced in one transaction kept its
`xmin`. The sets: billing — the run's columns, every bill of the run and of its accounts, its lines, Check
rows, findings, decisions, standing answers, Pending-billing rows, release, its accounts' credit notes and
level-pay status; payments — the accounts' payments, refunds, plans, instalments and allocations; customers
— the accounts and their opening buckets; metering — the cycle and the utility's routes, service points,
units and premises. **Not keyed:** the tenancy catalogues (service codes, account types, areas).
`tests/test_d8696_signoff_snapshot_pg.py` writes one row of each kind (a decision, a draft re-priced in
place, a payment, an opening bucket, a discarded draft, a Check row) and asserts the next read is a fresh
build equal to the live one.

### 12.4 · The figures are the old ones

| World | Figures compared | Differ | What differs |
|---|---:|---:|---|
| 40,008 sent | 40,191 | 1 | the new `plan_not_yet_due` key (null) |
| 10,008 at Sign off | 192 | 1 | the new `plan_not_yet_due` key (0) |
| J72 at Sign off (7 bills) | 152 | 4 | `DEF-BIL-8720`, on purpose: amount due **$675.78 → $563.83**, the plan bucket $223.90 → $111.95, `plan_not_yet_due` $111.95 |

**Against the bills:** the J72 world copied and sent through Send (`send-compare`): previous balance
$302.95, payments $0.00, plan not yet due $111.95 and amount due **$563.83** on Sign off each equal the sum
of the seven bills' stamped balance forward to the cent. The old Sign off read $675.78 for the same run.
`tests/test_d8696_signoff_batched.py` holds the same on five shapes (a plan, overpaid, ❄️ WE-1, nothing
before, ❄️ GT-16's migrated $267.30): **$688.42** on Sign off, $688.42 on the bills.

### 12.5 · In the browser (Chromium, gunicorn 3 × 60 s)

| Screen | 10,008 at Sign off · 1440 | 10,008 · 1280 | Its read |
|---|---:|---:|---|
| Sign off (cold open of the run → figures) | 7.2 s (load 2.6) | 3.3 s (load 1.9) | 1.2 s / 0.9 s |
| Not in this run (cold open → first row) | 4.0 s (load 2.9) | 3.5 s (load 2.7) | 0.45 s / 0.19 s |
| A tag's account list (click → first row) | **0.26 s** (load 3.5) | **0.16 s** (load 2.9) | 0.17 s / 0.12 s |

A cold open's waterfall (`10k`, load 2.1–2.8, twice): `/settings/services` **13.6–14.0 s** and
`/cycles?per=1000` **2.7–2.9 s** start with the page and hold two of three workers while Sign off's reads
queue (`sign-off-summary` answers 1.4–1.6 s after the page starts). Profiled, `/settings/services` counts
active accounts once per service, each count walking every service point (21 s in-process) —
`DEF-TEN-8731`; `/cycles` is `DEF-MET-8732`. **At 40,000 `/settings/services` is killed at 60 s**
(gunicorn `WORKER TIMEOUT`), so a cold open of the bulk run page at the top of the ICP loses a worker for a
minute whatever Sign off does. 40,000 in the browser: §12.6.

### 12.6 · 40,000 in the browser

**Not yet timed under the bar.** Behind gunicorn 3 × 60 s on `sbh_s14_40k`, the first cold open of the
bulk run page logged `WORKER TIMEOUT` on `GET /settings/services` at 60 s (`DEF-TEN-8731`), and the
machine's load did not fall under 2 again while this section was written (two other lanes at 5–6). The
harness for it is ready: `J73-s2-screen-timing.spec.ts` with `J73_SENT=1` (Sign off and Not in this run
timed from the click on step 3 of the sent run). Until it is run, the 40,000 figures are the server's
(§12.2), and the cold-open verdict is §12.5's.

### 12.7 · What this does not measure

A 40,000-account run stopped at Sign off (the only 40k world is sent, and no second copy was made — the
build at 40,000 is timed on the sent run, where every bill's balance forward is withheld (`DEF-BIL-8727`)
and the per-bill window arithmetic is skipped, so a run at Sign off builds somewhat slower than 8 s);
several clerks at once; the first read after a payment batch at 40,000 in the browser (the stale path,
~8–10 s, inside the 60 s worker).

## 13 · S2's cold open at 40,000 — the page's own reads after `DEF-TEN-8731`, `DEF-MET-8732`, `DEF-BIL-8758`, and Sign off after Send (`DEF-BIL-8727`) (2026-10-01)

**In one paragraph.** At 40,008 accounts the bulk run page no longer loses a web worker on open:
`/settings/services` went from **52–63 s** (killed at 60 s in production) to **0.6 s**, `/cycles` from
**7.6–8.2 s** to **1.0–1.3 s**, and the page's first read, the run itself (`GET /billing/runs/{id}`), which
turned out to be the largest of all on a sent run (**18.3 s** in the browser — it counted the 90,014
meter reads its bills priced one bound list at a time), to **1.2–1.5 s**. A COLD open of the sent 40,000 run now
shows its data in **4.3–7.9 s** (Not in this run's first row) and **5.5–8.7 s** (the Sent card's total)
at 1440 and 1280 — **far inside the 60 s worker, but still over S2's 2 s**: the page asks for its eight
screen reads only after the run read answers (~2.5 s), and eight reads on three workers queue. Every
response is byte-identical to the old code's. Sign off after Send now shows the bills' own figures
(**$7,371,758.07** due) where it showed `—`.

### 13.1 · Method

| | |
|---|---|
| Code | `2.433.2` (this lane: `df89738cb`, `b4d326353`, `f8a86bd53`); "old" is `a3c61a4de`, run beside it on the same database from a second worktree |
| Database | PostgreSQL 16 at `127.0.0.1:55433`, role `sbh_b27` (RLS enforced), `sbh_s14_40k` — the SENT run, 40,008 bills, 40,008 accounts, 160,032 open service agreements, 90,014 priced reads |
| Server reads | in-process through the real views (`j73_scale_proof._Api`, as a System Admin for S8 and a Billing Clerk for the run), 3–4 samples each, `DEBUG` off |
| Browser | `07-frontend/e2e/J73-s2-screen-timing.spec.ts` with **`J73_SENT=1 J73_COLD=1`** (new): navigation start → first paint of the data, every `/api/` request recorded with its start (the waterfall). Chromium, gunicorn **3 workers × 60 s** (`DEBUG` off) behind `server.mjs`, the built bundle |
| Load | every timing STARTED at a 1-minute load under 3 (a waiter held each run until it was); load rose to 3.2–4.4 during the old code's 52–63 s reads and to 3.2–3.7 during the browser opens — beside each figure. Three other lanes shared the four CPUs all afternoon |

### 13.2 · The server's reads at 40,008 (in-process)

| Read | Old code | New code | Same answer? |
|---|---:|---:|---|
| `GET /settings/services` (S8; asked by every bulk run page open) | **52.8–62.8 s** p50 54.3 (load 2.9 → 4.4) — 69 statements | **0.56–0.61 s** p50 0.59 (load 2.95) — 38 statements | byte-identical (11 rows) |
| `GET /cycles?per=1000` | **7.6–8.2 s** p50 7.95 (load 3.2–3.4) | **0.95–1.26 s** p50 1.23 (load 2.95) | byte-identical |
| `GET /billing/runs/{id}`, sent run | **6.9–7.6 s** p50 7.35 (load 3.2–3.9) — 31 statements | **1.24–1.53 s** p50 1.45 (load 2.95–3.1) — 13 statements | byte-identical (90,014 reads, 90,014 locked) |
| `GET …/sign-off-summary`, sent run | 0.55 s, every money figure null | 8.0 s once (the saved summary is rebuilt by the new build), then the saved copy | 40,192 figures: the 10 that moved are the payments section, null → the stamps' sums |

**Where the time went.** (1) S8 counted active accounts once PER SERVICE — eleven passes, each reading
every open agreement (160,032) and binding every service point id as a parameter. Now one grouped
statement: each agreement's point's service is correlated through a lazy queryset metering hands
customers (the `premises_ids_matching` precedent — no customers code imports a metering model), counted
per service in PostgreSQL, eleven rows back. (2) `/cycles` counted each cycle's accounts by loading every
account as a model with every primary contact's NAME (18.5 s of 21 s, profiled at load 7.7); now the
unit → account ids only (same occupying set, same tie-break), and a unit's per-service points folded with
`DISTINCT` in SQL. (3) The run read counted the Sent card's *Meter reads: Locked* by decoding every bill's
`services` snapshot in Python and binding the 90,014 read ids 5,000 at a time; now the ids are taken off
the bills in SQL and counted in ONE statement with one array parameter — `IN (SELECT unnest(…))`, a hash
semi join (0.28 s). ⚠ **`= ANY(…)` is the obvious spelling and is a trap here:** on the partitioned
`meter_reads` it compared every row of every partition with the whole array — **72 s** in `EXPLAIN
ANALYZE`. Above 2,000 ids both batched readers read the tenant's rows without binding them (no cap —
both branches answer every row, NFR-5).

### 13.3 · In the browser at 40,008 — a cold open of the sent run (gunicorn 3 × 60 s)

| Open | 1440 | 1280 |
|---|---:|---:|
| Navigation → Not in this run's first row | **4.6 s** (load 2.75 → 3.25) · **7.9 s** (2.80 → 3.65) | **4.3 s** (2.88 → 3.22) · **5.1 s** (3.00 → 3.62) |
| Navigation → the Sent card's total ($7,371,531.12) | **5.7 s** · **8.7 s** | **5.5 s** · **6.5 s** |
| Was (old code) | `/settings/services` killed at 60 s (`WORKER TIMEOUT`, §12.6); under load 9, `GET /billing/runs/{id}` 18.3 s with every screen read queued behind it | — |

The first 1440 open's waterfall (ms from navigation start · duration): `/settings/services` 676 · **813**,
`/cycles` 673 · **1,286**, `/billing/runs/{id}` 677 · **2,529**, then — only once the run has answered —
`not-in-run` 3,241 · 1,348, `check` 3,246 · 724, `check/findings` 3,247 · 1,241, `breaks` 3,251 · 1,402,
`sign-off-summary` 3,252 · 1,896, `summary` 3,248 · **2,448**. **Verdict: inside 60 s with a wide margin
— no worker is lost — and still FAIL against S2's 2 s on a cold open.** What is left is the page's shape
rather than one read: the screen reads wait for the run read, and eight of them share three workers.
Filed as `DEF-BIL-8809`. **The page half is fixed in `2.436.1` (§14): the reads now start beside the run read;
S2 still fails on the server's time.**

### 13.4 · Sign off after Send (`DEF-BIL-8727`)

A sent bill is in payments' open set while billing's prior totals leave the bill out, so every one of the
40,008 bills came back *unanswered* and Sign off printed `—` for previous balance, payments, plan and
amount due. A sent bill now answers with the balance forward issue stamped on it (`bill_payload ->
'balance_forward'`, read in SQL); a draft is computed exactly as before. **Against the bills:** Σ the
40,008 stamps (SQL, as the database owner) — previous balance **$226.95**, payments **$0.00**, this run
**$7,371,531.12**, amount due **$7,371,758.07**, no stamp null — equal Sign off's figures to the cent; on
the five-shape test run Sign off reads **$688.42** before Send and after. The payments/credits SPLIT is not
on the stamp and is null on a sent run. A summary saved by the old build is rebuilt once (the build's
version joined the saved summary's key), so a run sent before this fix shows the figures on its next read.
⚠ **The screen does not show Sign off on a sent run any more** (every rail step is locked after Send), so
these figures reach a clerk only through the read; `J73_SENT=1`'s old click on step 3 can no longer run,
which is why the cold-open mode times the Send screen.

### 13.5 · What this does not measure

A load under 2 (the machine did not fall under 3 for most of the afternoon; each figure says what it was
started and ended at); a 40,000-account run open at Sign off (no such world is kept); several clerks at
once.

## 14 · S2's cold open after `DEF-BIL-8809` — the screen's reads start beside the run read (`2.436.1`, 2026-10-01)

**In one paragraph.** The bulk run page no longer waits for the run read before asking for anything
else. On a cold open of the sent 40,008-bill run every read the Send screen draws now starts **0.84 s**
after navigation, where it started at **3.37 s**, and the page stopped asking for three reads Send never
shows (`/settings/services`, Sign off's figures, the Check job's state): **eleven reads became eight**.
Not in this run's first row now lands in **2.8–5.1 s** (was **5.2–6.3 s**) and the Sent card's total in
**3.9–7.6 s** (was **6.1–8.0 s**), old and new opened alternately on the same server and database. **Still
FAIL against S2's 2 s.** The page shape is no longer the cause: the reads now all run at once and the
time is the server's. Two figures put the floor above 2 s on this machine: the browser makes its first
API call **0.84 s** after navigation, and the Sent card's total needs `/summary`, which took **3.1 s**
here with the other reads running beside it. `DEF-BIL-8809` stays open for that server half. Every figure
on the screen is unchanged — **$7,371,531.12**, due 10/22/2026, in all eight opens.

### 14.1 · What changed in the page

| Read | Before (`2.433.2`) | After (`2.436.1`) |
|---|---|---|
| `GET /billing/runs/{id}` | at open | at open — first |
| `…/not-in-run` (page 1 of 50, `as_of` today) | after the run read, from the list once Send mounted | **at open**, beside the run read; the list finds it answered |
| `…/summary` | after the run read (`step ≥ 3`) | **at open** |
| `…/breaks` | after the run read (`step ≥ 3`) | **at open** |
| `…/check/findings` (the tiles) | after the run read (`step ≥ 2`) | **at open** |
| `…/sign-off-summary` | after the run read, on a sent run too | after the run read, **only on Sign off and an unsent Send** — a sent run never asks it |
| `…/check` (the job's n of N) | after the run read, on every step past Scope | after the run read, **on Check only** |
| `/settings/services` | at open | **only on Scope** — the services filter is drawn nowhere else |
| `/cycles`, `scope-templates`, `presence` | at open | at open, after the run's own reads |

**One request for both lists.** Not in this run asked with `as_of` on Send and without it on Sign off, so
the page could not ask before it knew which. It now always sends `as_of`. The server only adds each held
row's age (`not_in_run.py`), which Send shows and Sign off does not, so Sign off's screen is unchanged.

**The judgment, recorded in the decision log.** Before the run read answers, the page does not know the
phase. So it asks for the reads that **Sign off and Send both** draw. A read only one phase draws (Sign
off's figures, the Check job's state) still waits for the phase. A run still at Check therefore asks for
summary, breaks and Not in this run, which Check does not draw. With no drafts yet those are small
reads. A run at Check also draws its findings only once the job's state has answered, as it did when the
two were asked together. Otherwise the Check results showed with *Check again* briefly disabled.

### 14.2 · Method

Exactly §13.1's, except as here. Code: `2.433.2` (`6bf72cf89`, "old") against this change, two built
bundles behind two `server.mjs` on one gunicorn (3 workers × 60 s, `DEBUG` off, role `sbh_b27`, RLS
enforced) on `sbh_s14_40k`. Chromium 1194, `J73_SENT=1 J73_COLD=1`, opens alternated new/old at 1440 then
1280, twice. **Every open was started only at a 1-minute load under 3** (a waiter held each one; starts
2.66–2.95). The load at the end of each open is beside each figure: **3.0–4.2**, because the open itself
and three other lanes' test suites share the four CPUs.

### 14.3 · In the browser at 40,008 — a cold open of the sent run

| Open | Not in this run's first row | Sent card's total | Load (start → end) |
|---|---:|---:|---|
| **New 1440** #1 | 5.14 s | 7.64 s | 2.66 → 3.92 |
| **New 1440** #2 | **2.80 s** | **3.96 s** | 2.74 → 2.99 |
| **New 1280** #1 | 4.34 s | 4.88 s | 2.91 → 3.79 |
| **New 1280** #2 | **2.79 s** | **3.91 s** | 2.71 → 3.21 |
| Old 1440 #1 | 5.86 s | 6.89 s | 2.95 → 3.27 |
| Old 1440 #2 | 6.30 s | 8.04 s | 2.82 → 4.15 |
| Old 1280 #1 | 5.22 s | 6.13 s | 2.93 → 3.26 |
| Old 1280 #2 | 5.74 s | 7.04 s | 2.89 → 3.60 |

**The waterfall, best new open (1440 #2), ms from navigation · duration:** `me/permissions` 834 · 83, then
at 835–885 `not-in-run` · **1,845**, the run · **1,916**, `summary` · **3,112**, `breaks` · 2,013,
`cycles` · 2,594, `scope-templates` · 2,285, `check/findings` · 2,866, `presence` · 2,620. Old 1280 #2 for
comparison: the run 660 · 2,675, then **at 3,371** `check` 752, `check/findings` 2,153, `not-in-run`
2,358, `breaks` 2,441, `summary` 3,650, `sign-off-summary` 3,012.

**Where the time goes now.** Each list appears when its own read and the run read have both answered,
because Send is drawn only once the run says it is sent. In the best opens that is **2.7 s** for Not in
this run and **4.0 s** for the total. Each read is slower here than alone: the run read 1.9 s (1.45 s
alone, §13.2), and `/summary` 3.1 s. Eight reads share three web workers and four CPUs, so even a
small read like `presence` takes 2.6 s. **The 2 s bar is out of the page's reach on this machine:**
0.84 s before the first API call, plus a run read that has never been under 1.2 s alone, is already
over 2 s for both screens.

### 14.4 · A tag's account list

**Not re-timed cold.** A sent run's rail is locked (§13.4), and the only 40,000 world kept is sent. This
change does not touch the tag list's read; its last figures stand: click → first row **0.16–0.26 s** at
10,008 in the browser, **0.03 s** on the server at 40,008 (§12). A cold open of a 40,000 run still at
Check now asks three reads that Check does not draw (§14.1). That cost is not measured; no such world
is kept.

### 14.5 · What is left for S2, and whose it is

Server work, not page shape. Three ways forward, each measured against the clerk's screen:
(a) make `/summary` (3.1 s here, 1.0 s alone at load under 2) and the run read (1.45 s alone) cheaper at
40,008 without changing an answer; (b) fold the Sent card's facts into one read, as `DEF-BIL-8809`'s
own fix line offered; (c) more web workers than three. `DEF-BIL-8809` stays **open** for this. Its
page half is fixed in `2.436.1`.

**Update (`2.437.2`, §15):** (a) and (b) were done; (c) was not needed. S2 now passes on a cold open.

## 15 · S2's cold open after `DEF-BIL-8809`'s server half — PASS (`2.437.2`, 2026-10-01)

**In one paragraph.** The three reads the Send screen waits for are now cheap at 40,008 bills, and every
figure is unchanged. On a cold open of the sent run, Not in this run's first row lands in **1.08–1.40 s**
(old code on the same server and database: **2.55–4.46 s**) and the Sent card's total in **1.02–1.59 s**
(old: **3.60–5.94 s**), in seven clean opens of each build, alternated, at 1440 and 1280. **PASS against
S2's 2 s.** The total reads **$7,371,531.12**, due **10/22/2026**, and *Meter reads: Locked* in every open.
The web server stays at **3 workers × 60 s**; no worker change was needed.

### 15.1 · What changed on the server

| Read | Before (`2.436.3`) | After (`2.437.2`) | Same answer? |
|---|---|---|---|
| `GET /billing/runs/{id}` (every screen waits for it: it says which step the run is on) | **1.34 s**, 13 statements | **0.063 s**, 9 statements | byte-identical except `meter_reads`, which moved |
| `GET …/read-lock` (**new**; the Sent card's *Meter reads* row) | — (inside the run read) | **1.50 s**, asked only by a sent run's Send screen, after the run read | `{locked 90,014, reads 90,014, state locked}`, as before |
| `GET …/totals` (**new**; the summary's headline: bills, amount, currency) | — (the page read all of `/summary`: **1.09 s**, 22 statements) | **0.113 s**, 11 statements | bills 40,008, amount `7371531.120000`, the same functions as `/summary` |
| `GET …/not-in-run` (page 1 of 50) | **0.95 s**, 29 statements | **0.16 s**, 22 statements | byte-identical |
| `GET …/summary` (no longer asked by the page) | 1.09 s | 1.00 s, byte-identical | untouched |

In-process through the real views as a Billing Clerk, role `sbh_b27` (RLS enforced), median of 3, each
set started at a 1-minute load under 3 (2.85–2.94).

**Where the time went, and what was done.**
1. **The run read** decoded every sent bill's frozen `services` snapshot (90,014 read ids off 40,008
   bills, ~0.6 s of detoasting in PostgreSQL) and counted those reads in Meter Reads (~0.47 s). Both are
   unavoidable for that one fact; a single combined statement measured **2.1 s**, worse. So the fact left
   the read every screen waits for: `GET …/read-lock` answers it with the same code, and only the Sent
   card asks, once the run is known to be sent. The row appears ~3 s after the rest of the card.
2. **The Sent card's total** came from `/summary`, the whole Sign off panel: consumption per service,
   three category axes, coverage, the waived list. The service axis alone was ~0.45 s, counting each
   service's bills over 300,059 bill lines. The page draws only *bills* and *amount*. `GET …/totals`
   answers those two with the same three release functions (`current_position_bills`,
   `_amount_and_currency`, `_credit_adjustment_for`), live, with the same refusals.
3. **Not in this run** decided the status of every saved account of the run, twice in Python (once for
   the statuses, once for the pricing partition), and then skipped every account the run billed: 40,015
   decided twice to show 7. It now reads only the accounts the run holds no bill for (an anti-join in
   SQL) and decides both in one pass.

### 15.2 · In the browser at 40,008 — a cold open of the sent run

Method exactly §14.2's: `J73_SENT=1 J73_COLD=1`, Chromium 1194, gunicorn **3 × 60 s** (`DEBUG` off) behind
`server.mjs`, the built bundle. Old = `7e49784e4` (`2.436.3`, the code before this change) and new = this
change, each with its own gunicorn and bundle on one database (`s2srv_40k`, a copy of `sbh_s14_40k`).
Opens alternated new/old, 1440 then 1280; **every open started at a 1-minute load under 3** (2.78–2.99).

| Open | New: Not in this run | New: Sent total | Old: Not in this run | Old: Sent total |
|---|---:|---:|---:|---:|
| 1440 #1 | 1.38 s | 1.59 s | — | — |
| 1280 #1 | 1.32 s | 1.17 s | — | — |
| 1440 #2 | 1.19 s | 1.16 s | 3.71 s | 4.58 s |
| 1280 #2 | (1.66 s)* | (1.51 s)* | 2.55 s | 3.88 s |
| 1440 #3 | 1.39 s | 1.59 s | 3.98 s | 5.04 s |
| 1280 #3 | 1.34 s | 1.31 s | 4.46 s | 5.94 s |
| 1440 #4 | 1.40 s | 1.41 s | 2.58 s | 3.60 s |
| 1280 #4 | 1.08 s | 1.02 s | 3.24 s | 4.22 s |

\* Another lane's name-matching kill stopped web servers on this machine between 18:30 and 19:10; this
open's waterfall is missing three reads, so it is shown and not counted. The two old opens of round 1
were skipped for the same reason (the old build's `server.mjs` had been killed) and were re-run as rounds 3
and 4. Load at the end of each open: 2.87–3.95.

**The waterfall, new 1280 #4, ms from navigation · duration:** `me/permissions` 701 · 52, the run 702 ·
**141**, `totals` 703 · **304**, `not-in-run` 703 · **364**, `breaks` 704 · 408, `scope-templates` 706 · 460,
`check/findings` 706 · 1,154, `presence` 706 · 1,345, `cycles` 705 · 2,347, then `read-lock` 866 · 2,875.
Old 1280 #4: the run 727 · **2,112**, `not-in-run` 733 · 2,483, `summary` 733 · **3,476**, `cycles` 4,515.

**Verdict: PASS.** Both screens draw inside 2 s on a cold open at the top of the ICP, on three workers.
The floor is now the browser's own 0.6–1.1 s before its first API call; the three reads the screens wait
for take 0.14–0.6 s together. `DEF-BIL-8809` is closed.

### 15.3 · What this does not measure

A load under 2 (opens started at 2.78–2.99 and ended at up to 3.95); a 40,000 run still at Check (no such
world is kept; this change does not touch Check's reads); several clerks opening the page at once; the
`read-lock` read under contention beyond what the opens show (2.9–3.0 s, after the card's total).
