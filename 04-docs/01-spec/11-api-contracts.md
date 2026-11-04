# A11 — API Surface Implied by the UI

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Per-screen endpoints, params, response shape, pagination.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


| Screen | Purpose | Method + endpoint | Params | Response (needed) | Pg? | Notes |
|---|---|---|---|---|---|---|
| S6 | provision tenant | POST /tenants | signup payload | tenant, owner token | — | idempotency key |
| S7 | dashboard | GET /dashboard/summary | period | KPIs, activity | — | multi-entity read model |
| S17 | accounts list | GET /accounts | q, class, status, page | account rows | Y | large list |
| S21 | account detail | GET /accounts/{id} | — | account + services + plan + meters + balance | — | ≥3 entities → read model |
| S22 | record payment | POST /accounts/{id}/payments | amount, method, apply_to | payment, new balance | — | |
| S25 | reads list | GET /reads | cycle, route, flag, page | read rows | Y | large |
| S28 | upload reads | POST /reads/import | file, tags | job id, rule results | — | async job |
| S31 | run billing | POST /billing/runs | cycle, period_start, period_end, **bill_date**, **due_days**, scope_services | run id, exceptions | — | async; long. ⚠ **`due_days` ADDED BY CR-029 D9 (PO 2026-08-23):** *"when we configure Cycle we are provideing default values; mostly it wil remain as it is but user can over ride them during billing"*. The cycle carries the DEFAULT (`cycles.due_days`) and this is the RUN's override, stored on `bill_runs.due_days` (metering/billing migration 0022); `runs.effective_due_days` is the precedence, expressed once beside `effective_bill_date` which has held the other half of the same sentence since BR-BIL-070. **Absent, `null` and `""` are ONE answer and `0` is a DIFFERENT one** — `due_days = 0` is lawful (due ON the bill date; BR-MET-009 requires only ≥ 0), so a truthiness test here would hand every customer in the run the cycle's terms instead of the clerk's. Anything that is not a whole number ≥ 0 is REFUSED, not dropped, with `billing.run.due_days_invalid` (a due date decides when a late fee starts, BR-BIL-001, and a dropped override is a clerk watching their own number vanish). **Nothing already issued moves** (hard rule 4): every run created before that migration carries `due_days = NULL` and resolves to the cycle's value — the identical figure, proved case by case in `tests/test_cr029_rcw1_due_terms.py`. |
| S31.2 | run findings | GET /billing/runs/{id}/findings | tab | per-tab datasets | Y | multi-entity |
| S33 | payments ledger | GET /payments | type, method, page | payment rows | Y | |
| S34 | outstandings | GET /ar/outstanding | age, class, sort | account balances | Y | index on balance/age |
| S37 | deposits | GET /finance/deposits | period, status | batch rows | Y | |
| S38 | bank import | POST /finance/bank-imports | file/account | match preview | — | async |
| S39 | batch detail | GET /finance/deposits/{id} | — | payments + bank line + trail | — | ≥3 entities |
| S41 | tax remittance | GET /finance/taxes | period | by authority | — | |
| S42 | export | POST /finance/exports | period, target | journal entries | — | QBO/Xero adapters |
| S44/46 | reports | GET /reports/{key} | params | rows + totals | Y | |

**Read-model candidates (≥3 entities):** Dashboard, Account detail, Billing findings, Batch detail, Revenue&AR.
**Server-side pagination + indexing:** Accounts, Reads, Payments, Outstandings, Billing register, Bills.

---


## Addendum — Integration connect endpoints (2026-08-07)
Each connectable integration implies: `POST /integrations/{key}/connect` (method: oauth|apikey|sftp; env; sync cadence) → returns connection status; `POST /integrations/{key}/test` → test result; `DELETE /integrations/{key}` → disconnect; `GET /integrations` → per-tenant connection states. Keys: quickbooks, xero, stripe, plaid, itron, sensus, twilio, lob, sso, email(google|microsoft|smtp). Credentials stored as encrypted per-tenant secrets (see B3).

---

## Addendum r2 — PO-RATIFIED via the 11b conformance audit (2026-08-09)

The PO ratified the full 11b batch (Lane A items A-1..A-8 individually · Lane B bloc · Lane C bloc). From this addendum forward, **A11 = this file + `11b-api-audit.md` as ratified below**; the typed client (FI-01) generates from this combined baseline and CI diffs the drf-spectacular schema against it (TD-19, gate G9).

1. **Contract preamble (11b §3, G1–G18) = LAW**, with one refinement: **pagination page-size options on screen = 50 / 100 / 200 / 500 / 1000, default 50** (PO 2026-08-09; IS-2 amended; `per` clamps to this set).
2. **The six STALE entries are superseded** by their 11b §1 regenerations (payments payload · reads import lifecycle · billing runs 202+idempotency · bank imports staged · finance exports closed-period file batches · integrations key list per BR-INT-001 matrix). Refinement on the payments payload (A-1): **posting/clearing dates are pre-filled with proposed defaults and always user-overridable — pre-fill logic always** (BR-PAY-033 as refined).
3. **The 11b §2 module tables are ADOPTED as the missing-endpoint inventory** — PO: *"okay with this for the time being; in case specific issues we can ratify later, directionally this is correct."* Status: **CONFIRMED-DIRECTIONAL** — individual endpoints re-open via the normal batch on real issues; the E2 stop path applies if implementation finds a contradiction.
4. **Non-endpoints are law (A-7):** no 2FA endpoints (v2) · no synchronous send endpoint anywhere (queue only, BR-NOT-005) · no QBO/Xero live-sync endpoint (v2) · no PUT/PATCH/DELETE on issued invoices/lines, payments out of processing, posted JEs, audit rows, committed reads. Minting any of these = G-fail.
5. **Subscription screens S107–S109 deferred to W8/R4 (A-8 confirmed).**
6. **Screen retags** (mirrors 13a): `POST /tenants` S6→S114 · `GET /reports/{key}` also serves S59/S60 · S4/S5 rows retired.

## Addendum r3 — endpoint additions found during W1 implementation (2026-08-09)

Build-time additions under the A11 r2 CONFIRMED-DIRECTIONAL clause ("specific issues we can ratify later"). Each backs a ratified TC or a capability-matrix row action that r2's inventory did not enumerate; none introduces new behavior, and each obeys the §3 preamble (envelope, 404-never-403, pagination grammar, audit side-effects).

| Endpoint | Why it exists | Anchor |
|---|---|---|
| `DELETE /plans/{id}` | S9 row action — delete a plan never used (guarded like every audit-locked delete: referenced → 409) | EP-RAT-01 capability row · BR-RAT-035 pattern |
| `POST /rate-schedules/{id}/archive` | S9/S11 lifecycle action mirroring plan archive (published schedules are never deleted) | BR-RAT-030/037 |
| `DELETE /charges/{id}` | S12 row action — delete an unreferenced charge code; referenced → 409 BIZ-LOCKED | BR-RAT-035 |
| `GET /tax-jurisdictions` | S13 needs the jurisdiction picker; r2 listed taxes but not their parent list | BR-TEN-037 · EP-RAT-03 §5 |
| `GET /rate-changes` | S9 History tab — the bulk-change batch list (write side `POST /rate-changes` was already ratified) | BR-RAT-040 · US-RAT-011 |

Status: **CONFIRMED-DIRECTIONAL** (same standing as the r2 inventory) — re-openable per item via the normal batch.

## Addendum r4 — the notifications surface, contracted (2026-08-16, DEF-128)

Build-time additions under the A11 r2 CONFIRMED-DIRECTIONAL clause, exactly as
r3 was. **Three of the seven are 11b's own rows, mounted for the first time**;
four are new and each backs a ratified TC or capability-matrix row that 11b's
inventory did not enumerate. None introduces new behaviour and each obeys the
§3 preamble (envelope, 404-never-403, pagination grammar, audit side-effects).

**Why an addendum at all:** `apps/notifications` held 7,084 lines of tested
engine behind an `api.py` of 72 bytes that no URLconf named, so nothing a
customer is ever sent could be triggered, listed or audited through the product
(DEF-128 — the fourth occurrence of "built is not wired" at whole-module scale
in this release).

| Endpoint | Why it exists | Anchor |
|---|---|---|
| `GET /outbound` | 11b §2.13's own row, mounted. The S8/S30 delivery queue with the capability matrix's search, filters, five sortable columns and its ratified default sort — *"failed+bounced first, then queued_at"* | 11b §2.13 · EP-NOT-04 capability matrix · US-NOT-013 |
| `GET /outbound/summary` | 11b §2.13's own row, mounted. Counts by type × channel × status, the held/returned/retry-exhausted totals and the queued backlog per channel. **Serves `unpopulated_statuses`**: `delivered` and `bounced` are provider facts and no adapter exists on any channel, so a screen renders NOT REPORTED rather than a zero that reads as a delivery failure | 11b §2.13 · US-NOT-013 TC-1 · US-NOT-015 TC-1 |
| `POST /outbound/{id}/requeue` | 11b §2.13's own row, mounted. Clears `batch_id` as well as the status — without that a crashed hand-off's rows are invisible to the dispatcher forever while every screen says re-queued | 11b §2.13 · US-NOT-013 TC-3/TC-4 |
| `POST /outbound/requeue` | **NEW.** The BULK half. 11b lists the single-row form only; US-NOT-013 §1 ratifies both (*"a re-queue action (row + bulk)"*) and EP-NOT-04's capability matrix names *"Re-queue selected"* as a bulk action. Per-row results, never one boolean | US-NOT-013 §1 · EP-NOT-04 capability matrix |
| `POST /outbound/{id}/resend` | **NEW.** The staff re-send US-NOT-011 §5 ratifies — *"creates new queue rows, audited"* — and US-BIL-024 TC-4 repeats for a bill. **`copy_no` is REQUIRED in the body**: it is the fifth column of the `outbound_messages` idempotency key, so a repeated submit collides with its own row and answers 200 `created:false` instead of posting a second letter (CLAUDE.md rule 6). A HELD row is refused 409/BIZ-STATE | US-NOT-011 §5 · US-BIL-024 TC-4 · BR-BIL-016 |
| `POST /deliveries/returned` | 11b §2.9's own row, mounted — and it now completes BR-PAY-018 end to end: the queue row is stamped AND payments' own writer sets the account's bad-address flag. `returned_on` is REQUIRED and is the caller's business date (BR-TEN-043) | 11b §2.9 · US-NOT-014 TC-1/TC-2/TC-6 · US-PAY-016 |
| `GET /notices` | **NEW.** The `notice_history` record (r12 #7) — the trail a utility shows a regulator — with `f.account_id`, `f.notice_type`, `f.tier`, `f.outcome` and **`f.certified=true`, which is the CERTIFIED-MAIL REGISTER** (BR-CUS-039 makes certified mail a property of the 48-hour final tier and of no other). Sends AND skips. Money members carry the tenant's CHAR(3) currency | US-NOT-009 §5 · BR-CUS-039 · r12 #7 |

**Deliberately NOT minted, and each for a stated reason:**

1. **No send endpoint of any kind.** Addendum r2 §4 already makes this law —
   *"no synchronous send endpoint anywhere (queue only, BR-NOT-005)"* — and
   `06-backend/tests/test_def_128_notifications_api.py` asserts it as a property
   of the exported routes rather than leaving it to review.
2. **No notice-GENERATION endpoint.** `POST /accounts/{id}/notices` (§2.6, S22
   modal 5) and `POST /collections/notices` (§2.9, S34 bulk) are CUSTOMERS' and
   PAYMENTS' doors to `apps/notifications/notices.py`, and
   `apps/customers/services.send_disconnect_notice` refuses today naming
   OQ-133/136/137. Where an account stands on the collection ladder is unruled;
   a second door here would be this module deciding it.
3. **No export route.** The S8 capability row's CSV rides the platform
   `POST /api/exports` (US-SHL-008 / IS-9) and `outbound` is not yet a registered
   exportable resource — REPORTED (DEF-135 names the same gap for invoices,
   payments, reads and audit) rather than mounted as a second download pipeline.

Status: **CONFIRMED-DIRECTIONAL** (same standing as the r2 inventory and the r3
additions) — re-openable per item via the normal batch.

## Addendum r5 — the sub-meter reconciliation read (CR-038 W6, 2026-08-26)

Build-time addition under the A11 r2 CONFIRMED-DIRECTIONAL clause, exactly as
r3 and r4 were. One endpoint, read-only, backing a rule the PO ruled this week.

| Endpoint | Why it exists | Anchor |
|---|---|---|
| `GET /premises/{id}/submeter-reconciliation` | BR-MET-125's report half. The PO ruled on the master-vs-subs gap: *"(a) store + report"* (2026-08-26, Open 9) — so the gap is a stored row and this is the route that shows it. `?period=YYYY-MM` narrows to one reading month; without it every stored period answers newest-first, with `periods` listing the months that have a row. | BR-MET-125 · CR-038 W6 task 1 |

**Three properties worth contracting, not just listing:**

1. **It serves STORED rows and recomputes nothing.** A report that re-derived
   the gap on each request would answer a different number than the one written
   at reconciliation time as soon as a read was superseded — and the stored
   figure is the one somebody was asked about. The recompute door is the
   reconciliation write, not this read.
2. **It carries CONSUMPTION, never money.** The worked figure: master
   **12,400 kWh** − Σ subs **11,940 kWh** = **460 kWh (3.71%)** against a **3%**
   tolerance. What a gap COSTS is the bill run's judgment and no part of this
   payload.
3. **Permission is `AnyTenantRole`** — an ops read, the same standing as the
   S26/S27 progress views, not a System-Admin-only lookup (DEF-800 is the
   defect that shape causes).

House URL grammar: resource, then subpath. Status: **CONFIRMED-DIRECTIONAL**
(same standing as the r2 inventory) — re-openable in the normal batch. The
endpoint's own docstring REPORTED this row as owed rather than writing it,
04-docs/ being outside that lane's territory; this addendum closes it.

## Addendum r6 — the premises owner's CHECK and its ACCOUNT link (DEF-650, 2026-08-27)

Build-time addition under the A11 r2 CONFIRMED-DIRECTIONAL clause, exactly as r3,
r4 and r5 were. Two endpoints, behind the PO ruling of 2026-08-27: *"so premises
owner is master accountin system … Bascially Premises -> owner = Master account -
it can be existing master account also so at the time of premises creation we
should check - how you will handle this"*.

| Endpoint | Why it exists | Anchor |
|---|---|---|
| `GET /premises-owners/resolve?name=` | **The check the PO asks for, and the reason it is a GET.** It reports and never decides: `{"match":"exact","owner":{…}}` reuses the party that exists — the key is the database's own `uq_premises_owners_tenant_name_ci`, so a hit is a fact — `{"match":"near","owner":null,"candidates":[…]}` OFFERS and resolves nothing (PO decision 3: *"offer the match, clerk decides"*), and `{"match":"none"}` says nobody by that name. The clerk takes the decision; this makes that structural rather than promised in a comment. | BR-MET-401 · DEF-650 |
| `POST /premises-owners/{id}/master-account` | Declares the ACCOUNT an owner is billed through — `{"account_id": "<uuid>"}`, or `null` to clear. **It never creates an account:** `accounts` is customers' table (B1/B2 §2), the id is validated through `apps.metering.seams`, and the PO's own case is an account that already exists. | BR-MET-400 · DEF-650 |

**Two properties worth contracting, not just listing:**

1. **`resolve` may not be given a WRITE variant.** The moment it could create the
   party it found nothing for, the near-match branch stops being an offer — and
   an auto-merge is the one thing PO decision 3 rules out, because *"two
   landlords with similar names are two parties, and merging them bills the wrong
   one"*.

2. **`GET /premises-owners` does NOT expand each owner's account, and says so on
   the row.** Expanding costs one account read plus one ledger derivation each
   and the picker asks for 200 at a time — DEF-324's measured N+1. So the list
   serves `master_account_id` (a column) with `master_account_expanded: false`,
   and the detail and `resolve` serve `true`. Without that flag a `null` would
   mean both *no account is linked* and *this row did not ask*, which is DEF-762's
   shape.

⚠ **A STANDING GAP THIS ADDENDUM DOES NOT CLOSE AND SHOULD NOT BE READ AS
CLOSING.** The four CR-039 wave C owner endpoints that shipped on 2026-08-27 —
`GET|POST /premises-owners`, `GET|PATCH /premises-owners/{id}`,
`POST /premises-owners/{id}/deactivate`, `GET /premises-owners/unmatched` and
`POST /premises/{id}/match-owner` — are in **no** A11 addendum and in **no**
committed OpenAPI path (`06-backend/openapi/schema.json` holds 339 paths and not
one `premises-owner`). That is pre-existing and is REPORTED rather than
back-filled here: writing six rows for another lane's endpoints from the outside
is how a contract comes to describe what a reader guessed rather than what the
code does.

House URL grammar: resource, then subpath — and `resolve` is declared ABOVE the
`<uuid:owner_id>` route so a reader does not have to reason about converters.
Status: **CONFIRMED-DIRECTIONAL** (same standing as the r2 inventory).

## Addendum r7 — paging inside an asset, and the last three unpaged registry reads (CR-092-BRC01 step 2 wave C lane 3, 2026-09-12)

Build-time addition under the A11 r2 CONFIRMED-DIRECTIONAL clause, exactly as r3
through r6 were. **No new endpoint.** Six that already exist gain a page
parameter, because `NFR-3` says there are no unbounded list endpoints and these
six were.

**Why it is a contract change and not an implementation detail:** three of them
change the SHAPE of what they answer, and a shape a client cannot see coming is
the whole of `DEF-AST-4120`. Anchors: `AST-B-24` (CR-092 §6d, PO-approved
2026-09-12) · `DEF-MET-4995` · `DEF-MET-4962`.

### 1 · The three lists inside an asset answer the ONE envelope

| Endpoint | Params | Answers |
|---|---|---|
| `GET /assets/{id}/reads` | `page` · `per` | `{count, next, previous, results}` |
| `GET /assets/{id}/assignments` | `page` · `per` | `{count, next, previous, results}` |
| `GET /assets/{id}/maintenance` | `page` · `per` | `{count, next, previous, results, lifetime_cost, currency}` |

⚠ **THIS IS A BREAKING SHAPE CHANGE ON ALL THREE, STATED HERE RATHER THAN LEFT
TO BE DISCOVERED.** `/reads` and `/assignments` used to answer a BARE ARRAY and
`/maintenance` an object keyed `rows`. A client that does `data.map(…)` now gets
an object; a client that reads `data.rows` now gets `undefined`, and
`undefined ?? []` is a legal empty array that renders as *no results* with total
confidence — which is `DEF-WRK-4098`'s exact failure and the reason
`07-frontend/src/api/paginated.ts` exists. **The four shipped consumers are named
in the lane's handoff and none is this lane's to edit.**

**The four names are not negotiable and are not re-described anywhere.** `count`
· `next` · `previous` · `results`, built by `core.pagination.StandardPagination`,
declared once on the client in `paginated.ts`, and policed by `G114`. They are
the same four `GET /assets`, `GET /work-orders` and `GET /assets/{id}/work-orders`
already answer with, so an asset detail screen now reads ONE convention across
all four of its lists instead of the three it read before.

**`per` clamps to `50 / 100 / 200 / 500 / 1000`, default 50** (IS-2 as amended,
PO 2026-08-09). `page` clamps into `[1, last]`. Neither ever 4xx (`BR-SHL-011`).

⚠ **ON `/reads`, `count` IS THE NUMBER OF READ DATES AND A PAGE'S LENGTH VARIES.**
The tab draws one row per read date — `BR-AST-029`'s typed pair folded into the
Import and Export columns of a single row — so a three-register meter yields
three rows for one date. Paging the ROWS would cut a reading event across a page
boundary, half a meter's registers on page 1 and half on page 2, which is a
worse answer than a page that is sometimes 50 rows and sometimes 150. The paging
unit is therefore the DATE, and this paragraph is the contract for it.

⚠ **`lifetime_cost` AND `currency` ARE SIBLINGS OF THE ENVELOPE, NOT MEMBERS OF
IT, AND THE TOTAL IS OVER EVERY ENTRY RATHER THAN OVER THE PAGE.** A total that
changed when you turned the page would be a different and wrong number each
time. `null` — never `$0.00` — when no entry carries a cost. Money serves at its
stored 4 dp beside its `CHAR(3)` (hard rule 2); the screen trims to 2.

### 2 · The three composite registry reads carry a WINDOW

| Endpoint | Params | Gains |
|---|---|---|
| `GET /assets/stock` | `page` · `per` | `rows_window: {total, page, per, pages}` beside `rows` |
| `GET /assets/lifecycle` | `page` · `per` | `certifications_window: {…}` beside `certifications` |
| `GET /assets/geo` | `page` · `per` | `assets_window: {…}` beside `assets` |

**These three are ADDITIVE and break nothing.** Every existing key keeps its name
and its shape; a client that ignores the window reads what it always read, only
bounded. **That is why they are not in the envelope:** each is a COMPOSITE
payload — a list beside KPI figures, or three lists beside a value panel — and
there is no way for one of the lists to take `count`/`results` without stealing
those names from the others. The window is the shape `GET /imports/{id}` has
served since `DEF-766` (`rejects_window`), chosen for the same reason.

**A figure beside a window describes the WHOLE TENANT, never the page.**
`stock.kpis`, `lifecycle.asset_value` and `lifecycle.age_forecast.programme` do
not move when you turn the page; a KPI that followed the page would be a
different number on every page.

**`warranty_groups` and `age_forecast.rows` are served WHOLE, deliberately.**
Both key off the type catalogue — (type, supplier) and type — so they are bounded
by how many kinds of thing a utility buys rather than by how many it owns. A
page over a four-row roll-up is furniture.

⚠ **`GET /assets/geo` IS NOW A PAGE AND IS STILL NOT A VIEWPORT, AND
`DEF-MET-4301` STAYS OPEN.** That row says what a map actually wants — *"the
server takes the bounds it is drawing and answers what is inside them, with a
count of what it left outside"* — and it is right: a map of page 1 of 3 is a map
of the wrong day. Bounding the payload is not that change and does not pretend to
be; it stops the tab handing a browser the whole estate in the meantime, and
`assets_window.total` is exactly the figure an *"and 38,400 more, zoom in"* line
needs. The viewport read belongs with the map screen.

### 3 · What this does NOT change

Nothing about `POST /assets/{id}/maintenance`, `POST .../retire` or
`POST .../reassign`. No stored column moves, so B2 is untouched and there is no
migration. `apps.metering.selectors.typed_reads_for_asset` — the read **rating**
consumes (`US-AST-012` TC-3) — is deliberately left exactly as it was, for the
reason `DEF-MET-4101` already recorded: *narrowing a shared money-path contract
to fix a display is how a money path acquires a defect*. The paged read is a
second, display-only pair of functions beside it.

Status: **CONFIRMED-DIRECTIONAL** (same standing as the r2 inventory).

## Addendum r8 — the debtor list is paged, and its tiles are not (CR-138-BRC07 `P4.1`, 2026-09-23)

Build-time addition under the A11 r2 CONFIRMED-DIRECTIONAL clause, exactly as r3
through r7 were. **No new endpoint.** `GET /outstandings` gains the standard list
grammar, because `NFR-3` says there are no unbounded list endpoints and this was
the one `CLAUDE.md` names by name — *"Unpaginated ON PURPOSE … one row per DEBTOR
at a utility under 3,000 connections"*, and it sorted in Python (`DEF-PAY-4221`).

**Why it is a contract change and not an implementation detail:** the BODY grows
four keys and `rows` stops being everything. A shape a client cannot see coming
is the whole of `DEF-AST-4120`, and r7 was written for the same reason.

### 1 · What it takes and what it answers

| Endpoint | Params | Answers |
|---|---|---|
| `GET /outstandings` | `as_of` · `page` · `per` · `sort` · `dir` · `f.bucket` · `f.bad_address` | `{as_of, rows, totals, ageing, problems, debtors_window: {page, per, count, pages}, currency}` |

⚠ **THE PAGE FACTS ARE NESTED UNDER `debtors_window` AND THAT IS `G114`'s
RULE RATHER THAN A PREFERENCE.** A reply that declares `rows` beside a
top-level `per`/`pages` is the selector's page dict transcribed onto the wire,
and it reads as the standard list envelope `{count, next, previous, results}` —
which this body is not, because it also carries `totals`, `ageing` and
`problems`. `<key>_window` is the shape r7 already gave the paged asset reads.

⚠ **A PAGE IS CUT ONLY WHEN THE CALLER ASKS FOR ONE — `page` OR `per` ON THE
QUERY STRING — AND `per` COMES BACK `null` WHEN NOBODY DID.** That is not the
end state and it is not a cap (`NFR-5`): it is the state `DEF-PAY-4221` is left
in, because screen 7·1 declares **ten sortable columns, a search over account
number and customer name and four filters** and this read honours **three sorts
and two filters** — the rest live on customers' and on the collection-state and
plan tables that a billing-composed queryset does not join. Paging by default
under those controls would give a clerk a search box that searches fifty rows of
forty thousand. **`DEF-PAY-6271` sizes the join that switches it on**, after
which `page`/`per` become the default and this paragraph goes.

`sort` is one of `balance` (default, `desc` — BR-PAY-029's AR high→low),
`days_late`, `open_bills`. ⚠ **The set is short ON PURPOSE and the absences are
named:** `account_no` and `customer_name` live on customers' table, which this
query does not join, so sorting on them would either reach across a module
boundary inside billing's queryset or sort a page in Python — and the second is
the defect being fixed. Adding one is a change to `billing_seam.OUTSTANDINGS_SORTS`
and to the join, never a `rows.sort`.

BR-SHL-011 throughout: an unknown `sort`, an out-of-range `page` and an
unrecognised `per` all **clamp or fall back, never error** — and the CLAMPED page
comes back on the body, because a client told it is on page 9,999 of 2 has no way
to recover but to guess.

### 2 · `rows` is a page · `totals` and `ageing` are the WHOLE filtered list

⚠ **THIS IS THE CLAUSE A CLIENT MUST READ.** US-PAY-013 TC-1 requires the KPI
strip to tie to the DEBT, and the argument for leaving this list unbounded for
seventeen days after the ICP moved was that a fold over the rows was the only way
to guarantee it. It is not: `totals.accounts`, `totals.owed` and every `ageing`
tile are SQL aggregates over the same filtered set the page is cut from. **A
screen that recomputes either from `rows` silently starts describing a page.**

`debtors_window.count` is how many debtors match — **a COUNT and never a cap (`NFR-5`)**. There
is no maximum row count, no `[:N]` and no per-tenant ceiling; `per` clamps to
`core.pagination.PAGE_SIZES` like every other list, and page 800 of a 40,000-row
list is a legal request that is answered.

### 3 · What this does NOT change

`rows`, `totals`, `ageing` and `problems` keep every key and every meaning they
had. No stored column moves, so B2 is untouched by `P4.1`; the only schema change
in the task group is one index (`payments/0040`). `billing_seam.outstanding_positions`
— the UNPAGED read that `ladder.run_ladder`, `notices.py` and the cutover
comparison consume — is deliberately left exactly as it was: two of its three
callers are batch jobs with no page to cut to, and narrowing a shared money-path
read to fix a screen is how a money path acquires a defect (`DEF-MET-4101`). The
paged read is a second function beside it, and a test compares the two debtor by
debtor.

⚠ **`GET /collections/ladder` IS STILL UNPAGED AND THAT IS `P4.9`, NOT THIS
ADDENDUM.** `P4.2` removed its two N+1s — 244,195 statements to 20 at 40,046
debtors — so its STATEMENT count no longer grows with the tenant. Its ROW count
still does: it built 40,030 rows in 12.405 s. Said here rather than left to read
as done.

Status: **CONFIRMED-DIRECTIONAL** (same standing as the r2 inventory).
