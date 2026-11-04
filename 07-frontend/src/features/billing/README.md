# features/billing — bill runs, invoices, corrections

Docs: `04-docs/05-modules/07-billing/`.

Shipped here today: **S30 · All bills** (US-BIL-025), **S30 · bill detail**
(US-BIL-026), the account's Bills tab (US-CUS-010) which reuses the same list
scoped to one account, and **S31 · the bill run** (US-BIL-001..005) at
`/{tenant}/billing/run`. `One-time bill`, `Budget Bills`, `Fix a bill` and
`Past billing runs` are the remaining four tabs of the prototype's Billing page
and are named on screen as arriving with their own epics.

> **Status note, 2026-08-11.** The "contracted, NOT SERVED" paragraph below is
> STALE for the two invoice reads: `apps/billing/api.py` now exports
> `urlpatterns` for `invoices` and `invoices/{id}` and `config/urls.py` includes
> it. Everything the paragraph says about the OTHER four rows of the table (the
> document, the deliveries and the void) still holds, and everything it says
> about the run holds in full — see the S31 section at the foot of this file.

---

## The S30 read API — contract, written down here because nothing else states it

**Status on 2026-08-11: contracted, NOT SERVED.** `06-backend/apps/billing/api.py`
is a one-line docstring with no `urlpatterns`, and `06-backend/config/urls.py`
has no `apps.billing.api` include. The tables landed the same day
(`apps/billing/models.py`, migrations `0001`+) with no way to read them.

The PATHS below are not invented here — they are the ratified surface in
`04-docs/01-spec/11b-api-audit.md` §2.8 (adopted CONFIRMED-DIRECTIONAL by the PO,
2026-08-09, A11 Addendum r2 item 3) plus §2.6's S21-tab row:

| Route | Screen | 11b row |
|---|---|---|
| `GET /invoices` | S30 list · S21 Bills tab (`f.account_id`) | §2.8 · §2.6 (S21 tabs) |
| `GET /invoices/{id}` | S30 detail | §2.8 |
| `GET /invoices/{id}/document` | S30 detail — the pinned render | §2.8 |
| `GET /invoices/{id}/deliveries` | S30 detail — per-channel history | §2.8 |
| `POST /invoices/{id}/void` | S30 void (US-BIL-027, W5) | §2.8 |

**No PUT/PATCH/DELETE exists on an issued invoice or line** — 11b G8 / HR-4 /
BR-BIL-004. Minting one is a gate failure.

### What is specified here, and what deliberately is not

**Specified: the two READ shapes the shipped screens consume.** Every field below
names the `apps/billing/models.py` column it carries, so the backend lane and this
lane cannot pick two different names for one column. They are the types in
`src/api/endpoints.ts` — that file is the machine-readable half of this table.

**NOT specified: the inside of `bill_payload`.** BR-BIL-030 says what the payload
must CONTAIN (tenant identity, customer name, service address, premises/unit,
account number, each meter with prior/current read and unit, lines grouped by
service, taxes, totals, messages) and BR-BIL-031 versions it, but no signed
document names its JSON keys, and stage 6 (`assemble-document`, BR-BIL-037) is
being authored right now in `apps/billing/`. **The frontend never opens the
payload**: BR-BIL-026 makes the SERVER render the pinned template, so S30's
document panel is an `GET /invoices/{id}/document` embed, not a client-side
renderer. Inventing payload keys here would be two lanes guessing one schema —
the exact shape of the OpenAPI-copy defect (hard-won law 5).

### `GET /invoices` — the S30 list

Request params are BR-SHL-011's grammar, unchanged: `q`, `sort`, `dir`, `page`,
`per`, `f.<name>`. Response is the standard DRF page envelope
(`count`/`next`/`previous`/`results`) plus a `rollup` object, exactly as
`GET /accounts` already answers.

| Field | Column / derivation | Notes |
|---|---|---|
| `id` | `invoices.id` | uuid7 |
| `invoice_no` | `invoices.invoice_no` | **null on a draft** — BR-BIL-022 mints at issue only, and a draft that already held a number would have consumed one the customer never sees |
| `bill_type` | `invoices.bill_type` | `cycle`\|`first`\|`final`\|`rebill`\|`backbill`\|`penalty` (r10 #12) |
| `status` | `invoices.status` | `draft`\|`issued`\|`paid`\|`void`\|`corrected` — the five, and only the five |
| `past_due` | **derived**, never stored | `status == issued` ∧ unpaid ∧ `due_date < today`. The server derives it because "today" is the server's clock and the payment position is the ledger's — see below |
| `account_id` / `account_no` / `customer_name` | `invoices.account_id` + the customers read (B1 service fn) | `customer_name` is the primary CONTACT's until BR-CUS-054's table exists |
| `cycle_label` | `bill_runs.cycle_id` → metering (B1) | e.g. `08-A`; null for a single/ad-hoc bill with no run |
| `bill_run_id` | `invoices.bill_run_id` | null on a single bill |
| `service_date` | `invoices.service_date` | the date that selects the tariff version |
| `period_start` / `period_end` | same columns | calendar dates |
| `issued_at` | `invoices.issued_at` | ISO timestamp; **null on a draft** |
| `due_date` | `invoices.due_date` | **null on a draft** — BR-BIL-024 derives it at issue, never typed |
| `subtotal` / `tax_total` / `total` | same columns | NUMERIC(18,6) **decimal strings**, never numbers (CLAUDE.md #2) |
| `currency` | `invoices.currency` | CHAR(3), travels WITH every amount |
| `template_version` | `invoices.template_version` | the pin (r10 #3 / BR-BIL-026); null before issue |

`rollup`: `{ bills, billed_this_cycle, billed_currency, unresolved_from_last_run }`
— the prototype's "7,240 bills lifetime · $342,180 out this cycle · 3 unresolved
from the last run". Every member is nullable and a null means **not computed**,
never zero (the `past_due_60_plus` precedent on `GET /accounts`).

**Sorts** (`INVOICE_SORTS`): `invoice_no`, `issue_date`, `due_date`, `total`,
`status` — the US-BIL-025 capability row verbatim. Default `issue_date` desc.

**Filters** (`INVOICE_FILTERS`): `status` (the segment strip, plus the derived
`past_due` pseudo-value), `bill_type`, `cycle_id`, `bill_run_id`, `issued_from`,
`issued_to`, `account_id`. **Search** (IS-3): bill #, account #, customer name.

**Why `past_due` is served and not computed on the client.** It is
`issued ∧ unpaid ∧ due_date < today`. The client knows `due_date`, but *unpaid*
is the payments/ledger position (which this lane may not read, B1) and *today* is
the server's clock in the tenant's timezone (BR-TEN-043 event-time law). Deriving
it from `due_date` alone in the browser would call a paid bill past-due. So the
list SEGMENT is a filter value the server resolves, and the row flag is a served
boolean — and when the server sends neither, the screen shows the stored status
and says the derived one is not available. It is never stored (US-BIL-025 §5).

### `GET /invoices/{id}` — the bill detail

Everything in the row, plus:

| Field | Column / derivation | Notes |
|---|---|---|
| `lines[]` | `invoice_lines.*` | one row per charge component (US-BIL-007) |
| `lines[].kind` | `invoice_lines.kind` | `usage`\|`base`\|`fee`\|`tax`\|`adjustment`\|`minimum` |
| `lines[].description` | same | the engine's own text |
| `lines[].quantity` / `.unit` | same | **the unit is explicit whenever there is a quantity** (CLAUDE.md #3) |
| `lines[].unit_price` / `.amount` | same | decimal strings |
| `lines[].taxable` | `invoice_lines.taxable` | B4.2's flag — display only; the ENGINE also selects by kind |
| `lines[].gl_account_id` / `.gl_account_code` | `invoice_lines.gl_account_id` | the **stamp** (BR-BIL-010) — issue-time truth, never re-resolved against today's mapping. `gl_account_code` is the human-readable code (`4100`) resolved from the ledger when W5 exists; null until then |
| `lines[].tariff_version_id` / `.tariff_version_label` | `invoice_lines.tariff_version_id` | the version in force at `service_date` |
| `lines[].service` / `.period_start` / `.period_end` | same columns | grouping + back-bill sub-periods |
| `payload_version` | `invoices.payload_version` | the DATA contract version (BR-BIL-031). The screen shows it beside the template version because the two are different axes |
| `has_payload` | `invoices.bill_payload IS NOT NULL` | a BOOLEAN, not the payload. A draft has none (the trigger requires it at issue) |
| `document_url` | — | where `GET /invoices/{id}/document` lives for this bill; null when nothing was pinned |
| `summary` | computed, A19 | `{previous_balance, payments_credits, current_charges, total_due}` — all decimal strings. WE-1: `45.00 − 0.00 + 247.87 = 292.87` |
| `credit_notes[]` / `rebill_of_invoice_id` / `corrected_by_invoice_id` | `credit_notes.original_invoice_id` + the rebill citation | the correction chain, navigable both ways (BR-BIL-004/014) |
| `adjustments[]` | `adjustments.*` for this invoice | signed rows, never an edit of the invoice |
| `deliveries[]` | the outbound queue (r10 #8) | absent until BR-BIL-016's queue exists — an EMPTY ARRAY would claim "never sent" |

`summary` is served rather than summed here: the A19 figures include the previous
balance and the payments received, which are ledger/payments positions this lane
may not read (B1), and BR-BIL-035 stamps them into the payload at issue so a
reprint shows the arrears as they stood on the bill date.

### What the screens do while none of this is served

`GET /invoices` is a COLLECTION route: a served list endpoint never answers 404.
So a 404 from it means the API does not serve a bills list, and the list screen
says exactly that — **derived from the response, so it stops saying it the moment
the route lands**. No flag, no hardcoded "not built yet" that goes stale (law 1).
The detail's 404 is genuinely ambiguous (unknown id · cross-tenant · route
absent — HR-1 makes the first two one answer) and its message names both.

---

## Screens

| File | Screen | Story |
|---|---|---|
| `BillsListPage.tsx` | S30 · Billing (six tabs; All bills is built) | US-BIL-025 |
| `BillDetailPage.tsx` | S30 · bill detail | US-BIL-026 (+ US-BIL-027 void, gated) |
| `billingShared.tsx` | routes, vocabularies, the honest cells | all three |

---

## S31 — the bill run (2026-08-11)

`BillRunWizard.tsx` + `billRunShared.tsx` + `billRun.css`. Route
`/{tenant}/billing/run`, which is the Billing page's own **Run bills** TAB id —
so the existing tab strip lands on the wizard and `BillsListPage` needed no
edit. The segment is all-static, so React Router ranks it above `billing/:tab`.

### The three axes, and why the screen names two of them

**Seven pipeline stages** (BR-BIL-037) are the computation. **Six wizard steps**
are the UI over it — the prototype's own stepper: Pick the cycle · Check what we
found · Review customers · See the totals · Confirm & sign off · Send them out.
**Five phases** (BR-BIL-050) are the operating model the PO ruled on 2026-08-11:
prepare · calculate · breaks · summary+gate · release. None renumbers another,
and `BillRunWizard.test.tsx` asserts all three counts and the step→phase map —
because the epic itself once wrote "the five S31 wizard steps" when the wizard
has six (hard-won law 1).

| Wizard step | Phase | What it renders |
|---|---|---|
| 1 Pick the cycle | prepare | `GET /cycles` + `GET /settings/services`, **both served** |
| 2 Check what we found | prepare | `GET /billing/runs/{id}/findings` — contracted, unserved |
| 3 Review customers | prepare | `GET /billing/runs/{id}/exceptions` — contracted, unserved |
| 4 See the totals | breaks | the BREAK list first (BR-BIL-053), then the drafts from `GET /invoices?f.bill_run_id=` (**served**) |
| 5 Confirm & sign off | summary+gate | the live summary (BR-BIL-056) + the five-fact gate (BR-BIL-058) |
| 6 Send them out | release | `POST /billing/runs/{id}/issue` — contracted, unserved |

### What the backend owes this screen

**Updated 2026-08-11 — four of these landed.** `apps/billing/api.py` now serves
the create, the findings, the exceptions and the resolve, and `AccountProblem`
carries its `stage`. The rows still marked ✗ are unchanged and each now has a
STATED BLOCKER rather than a silence — see 11b §2.8b, which records what was
served and why the rest was not.

| Needed by | Route / shape | State |
|---|---|---|
| step 1 exit | `POST /billing/runs` | ✅ **SERVED.** 201 `{id, job_id, status}` — `id` inline (11b marks the row STALE against B12 r1's 202+job; that law is about ASYNC ops and this queues no work), `job_id` **null** because there is no job runner (TD-17). A repeat is 409 with `params {run_id, ran_by, ran_at}` (BR-BIL-005), which `runIsDuplicate` already recognises |
| step 2 | `GET /billing/runs/{id}/findings` | ✅ **SERVED** — `runs.PreparedRun` field for field, NOT paginated (its lists are the KPI strip's denominator). Refuses 422 when the run's cycle has no `bill_date`: the service date is the CYCLE's bill date and no clock may substitute (BR-TEN-043) |
| step 3 | `GET /billing/runs/{id}/exceptions` + `.../exceptions/{caseId}/resolve` | ✅ **SERVED.** A case row's `id` is its decision's natural key (`case\|account\|service`), so the id this screen selects still names the same case on the next viewing. `choices[]` comes WITH the row from `decisions.CHOICES_BY_CASE` |
| step 3 | an ESTIMATE's quantity | ✗ **this screen's gap, not the server's.** BR-BIL-015's *estimate* needs a quantity AND its unit (CLAUDE.md rule 3) and the server accepts `amount` + `unit` on the resolve body — `BillRunResolveBody` sends neither and no control collects them, so choosing *estimate* is refused server-side today |
| step 4 | **the break list** | ✗ `runs.CalculatedRun.breaks` exists only IN MEMORY — `calculate_run` returns it and nothing persists it, so no GET can read it and computing it inside one would write drafts |
| step 4 | the three draft powers (exclude · re-rate · add line) | ✗ contracted (11b §2.8); unserved |
| step 4 | run STATUS to poll (BR-BIL-051) | ✗ the poll exists to watch a BACKGROUND batch and there is no background batch (TD-17); a status that cannot change while you watch is a promise of asynchrony |
| step 5 | the live summary (BR-BIL-056) | ✗ `release.summary_for` computes it, and OQ-112 CLOSED (*"B An export only"*) — the authorisation record gets an export and deliberately no screen |
| step 5 | the release record (BR-BIL-058) | ✗ same ruling; `release.authorise_release` also needs `confirmed_at`, an event time no clock in this path may supply |
| step 6 | `POST /billing/runs/{id}/issue` | ✗ **NOT SERVED and not stubbed.** Issue needs a template pin (BR-BIL-026 refuses without one; BR-BIL-025's assignment has no table), an event time (BR-TEN-043 / G6), and an authorised release. A route answering 501 is a promise |
| step 5 | mandate coverage counts (BR-BIL-059) | ✗ no endpoint |
| step 2 | `stage` on `runs.AccountProblem` | ✅ **DONE 2026-08-11.** The dataclass carries `stage` (one of the seven BR-BIL-037 names, or null when the finding is not a stage failure) and **`FINDING_TAB_BY_REASON` was deleted**. What is left here is `FINDING_TAB_BY_STAGE` — three entries, the only half that was ever this screen's |
| step 2 | Balances · Credits · Overcharges findings | ✗ `prepare_run` returns no money at all; three of the six tabs therefore have nothing to show, and the exceptions envelope's `totals` is `{}` for the same reason |
| step 3 | `customer_name` on a case row | ✗ served **null**: the only published customers read takes an Account instance, which billing may not import (B1). Null means "not read", never "no name" |
| step 3 | three prototype categories with no `DECISION_CASES` value | ✗ "Reading was estimated", "Owes a lot", "Way past due" — a choice made on any of them has no column to land in (`CASES_WITHOUT_A_RECORD`) |

**Nothing above is faked.** Where a route is contracted the screen calls it and
DERIVES its absence from the 404 (`runRouteAbsent`), so the panel stops
apologising the day the route lands — which is exactly what happened to steps 2
and 3 on 2026-08-11, with nothing in those panels edited. Where no route is
contracted the screen names the gap and calls nothing, because calling an
unratified path would be the frontend inventing an API.
