# `CR-101-BRC03` · step 2 · §06 **Fix a bill** — lane B, the two backend gaps

**Lane:** B (backend) of the two-lane §06 wave. **Branch:** `claude/gifted-johnson-top7zn`.
**Date:** 2026-09-15. **Base:** worktree cut at `30e38bb4`; every push built from the pinned
tip (`9cda92e6`, then `5f426eb4`). **Commits:** `5f426eb4` (the code, the tests, the
schema, the record) · see §9 for the second.

**What this is.** The record of two commitments built end to end, so that lanes A and C–F
build the wizard from the repo and not from anybody's memory: **the exact payload shapes**
this lane published (§2 and §3, one worked JSON each), what was deliberately not built and
why (§6), every red with its date (§7) and the proof table (§8).

**What this is NOT.** It is not a screen. Lane A owns `07-frontend/src/features/billing/`
and nothing there was touched; the one front-end file this lane wrote is the endpoint
TYPES (`07-frontend/src/api/billingOpsEndpoints.ts`, §4), which lane A reads.

---

## 0 · The two gaps, in the drawing's words, and the rule checked against the code

The Billing blueprint (`05-prototype/04 Billing, As Built.pdf`, §06, p129–p144, read **as
images** per B14 rule 42 — p133 has no text layer at all) draws:

* **p129, the case table, DISCOUNTS column** — `26.1` one bill: *"On both bills" + which
  version* · `26.2` several months: *Each month on its own enrolment* · `26.3` a batch:
  *Accounts affected* · `26.4` goodwill: *Nothing is re-priced* · `26.5` the page only:
  *Unchanged* — and under it, *"An absent panel is drawn, never omitted."*
* **p133, the scope table** — `BILL · PERIOD · AMOUNT · PAID · STATE` (Paid / Part paid /
  Unpaid), a totals row *"Six bills · $1,454.10 · $904.50"*, and the sentence *"Only an
  issued or paid bill can be corrected."*

**Measured before building (the skill's §0 second act):**

| Claim in the repo | Measured 2026-09-15 |
|---|---|
| The preview publishes discounts | **Zero** mentions of `discount` in `BillImpact.as_dict`, `nine_sections`, `AggregatePanel` — the engine re-prices with them (`DEF-537`, `BR-BIL-792`) and the preview says nothing |
| `BR-BIL-792` / `corrections.recompute`: *"`discount_grants` stamps `discount_version_id`"* | **False.** `record_grant` is the only writer of `discount_grants` and **nothing calls it** — `grep -rn "record_grant(" apps/` returns its definition alone. No issued bill carries a discount version id anywhere. Filed **`DEF-BIL-5341`**; `BR-BIL-792` amended, dated |
| `resolve_scope` serves PAID and STATE | It returned a bare `tuple[Invoice, ...]` — every bill, no paid figure, no state, no totals, and **no endpoint** served it before a case existed: resolution happened only inside `POST /corrections` |
| The seam the brief named, `apps/billing/seams/payments_seam.py` | Does not exist; billing's payments seam is **`apps/billing/payments_seam.py`** (flat, like every billing seam). Extended there |
| `openapi/schema.json` is the generated contract | **175 paths behind the code** (513 committed, 688 generated). Filed **`DEF-GOV-5342`**; regenerated in full by `manage.py export_openapi` |

**Classified:** an **API** commitment on a **🔒 money path** — the preview is the artifact
approval binds and the scope table is what a clerk picks bills from before a credit note
issues. Every file touched already carries `HUMAN-OWNED · HUMAN-REVIEW-PENDING`; the
review-ledger row is `12-governance/09-human-review-ledger.md`, NEW ROW 2026-09-15.

---

## 1 · Five judgments where the rules ran out — decided, recorded, not asked (law 13)

Grepped `02-decision-log.md` and `01-open-questions.md` first: nothing rules on discounts in
the correction preview or on PAID/STATE for a scope. All five are in the decision log of
2026-09-15 (*"FIVE JUDGMENTS WHERE THE RULES RAN OUT"*); summarised here:

1. **The discounts panel lives INSIDE section 3 of nine, not in a tenth.** `BR-BIL-044` is
   nine sections and none may be added; section 3 is already the money, and a reduction is
   money on the same two bills. Same reasoning that put CS-36's settlement panel inside
   section 6. **Nothing about tax was added** — the PO has not ruled on the step-3 tax
   panel and this lane did not decide it.
2. **A discount's identity on a bill is its LABEL; the version is the one IN FORCE on the
   bill's own service date.** No FK, no code, no stamp exists (`DEF-BIL-5341`), so the
   panel resolves the label through a new rating read at `BR-RAT-007`'s pivot and says
   `version_basis: "in_force_on_service_date"` on every panel. **A reconstruction, and the
   payload says so.** A label naming no programme, or two (`Discount.name` is not unique),
   or one with no version that day comes back with a NAMED `reason` and null version
   fields — never dropped.
3. **AMOUNT is what the bill ASKED** (`BR-BIL-072`, `amount_due_for`), `total` beside it.
   The SQL twin `amount_asked_expression` is tied to the one rule by a test on a budget
   bill (asked `242.00` / total `292.87`) and an ordinary one.
4. **STATE is derived from MONEY, never from `invoices.status`** — paid ≥ asked → `paid`;
   0 < paid < asked → `part_paid`; else `unpaid`. The lifecycle value travels beside it as
   `bill_status`.
5. **Payments unreachable is `null` plus a problem, never `unpaid` or `0.00`** — the
   seam's own rule at page and totals grain.

---

## 2 · Gap 1 — the DISCOUNTS panel: exact shape

**Where it rides.** On every persisted per-bill impact (`correction_case_bills.impact`
→ `bills_detail[i].impact.discounts`), inside the content hash approval binds; on a
single case also at `sections.the_money.discounts`; on a bulk case additionally as
`aggregate.discounts` (the batch cell).

### 2.1 Per-bill panel — `impact.discounts` / `sections.the_money.discounts`

| Field | Type | Meaning |
|---|---|---|
| `outcome` | code | one of `on_both_bills` · `on_the_original_only` · `on_the_corrected_bill_only` · `none_on_either` (class R) · `nothing_is_repriced` (class C) · `unchanged` (class D) · `not_in_this_preview` (an artifact stored before 2026-09-15; never recomputed, because approval binds the stored artifact) |
| `original[]` | list | one entry per `discount` line on the ORIGINAL bill |
| `corrected[]` | list | one entry per `discount` line on the CORRECTED bill (class R: the engine's; classes C and D: identical to `original`, because the bill is not re-priced) |
| `original[].label` / `corrected[].label` | string | the bill line label (`Discount.name`) |
| `…amount` | decimal string | the line's own amount, **negative** (a reduction), finalized once |
| `…code` | string \| null | the programme code the label resolved to |
| `…version_id` / `…version_no` / `…effective_from` | string \| null / int \| null / ISO date \| null | the version in force on the bill's service date |
| `…reason` | code \| null | why there is no version: `no_programme_carries_this_label` · `label_names_several_programmes` · `no_version_in_force_on_that_day` |
| `original_total` / `corrected_total` / `delta` | decimal string | Σ of each side, and corrected − original |
| `currency` | CHAR(3) | the bill's |
| `service_date` | ISO date | the pivot the versions were resolved on |
| `version_basis` | code | `in_force_on_service_date` — the only basis there is today |
| `problems[]` | list | `discount_versions_unavailable` when rating has not published the read; amounts unaffected |

**26.1 · one bill (class R), the reduction on both sides** — WE-9's bill with a `$10.00`
senior reduction, corrected in the same month:

```json
"discounts": {
  "outcome": "on_both_bills",
  "original":  [{"label": "Senior discount", "amount": "-10.00", "code": "SENIOR",
                 "version_id": "0199…", "version_no": 1, "effective_from": "2026-01-01", "reason": null}],
  "corrected": [{"label": "Senior discount", "amount": "-10.00", "code": "SENIOR",
                 "version_id": "0199…", "version_no": 1, "effective_from": "2026-01-01", "reason": null}],
  "original_total": "-10.00", "corrected_total": "-10.00", "delta": "0.00",
  "currency": "USD", "service_date": "2026-07-31",
  "version_basis": "in_force_on_service_date", "problems": []
}
```

A recomputation that DROPS the reduction reads `"outcome": "on_the_original_only"`,
`"corrected": []`, `"corrected_total": "0.00"`, `"delta": "10.00"` — the money leaving the
customer's pocket is shown, never netted away.

**26.2 · several months** — a `date_range` scope over one account: the panel above, **once
per pinned bill** on `bills_detail[i].impact.discounts`, each resolved at ITS bill's
service date — so a July bill and an August bill can name two versions of one programme
(*"each month on its own enrolment"*).

**26.4 · goodwill (class C)** — drawn, with the code saying nothing moved:

```json
"discounts": {"outcome": "nothing_is_repriced",
  "original":  [{"label": "Senior discount", "amount": "-10.00", "code": "SENIOR", "version_no": 1, …}],
  "corrected": [{"label": "Senior discount", "amount": "-10.00", "code": "SENIOR", "version_no": 1, …}],
  "original_total": "-10.00", "corrected_total": "-10.00", "delta": "0.00", …}
```

**26.5 · the page only (class D)** — identical shape with `"outcome": "unchanged"`.

**A bill with no reduction at all** — `"outcome": "none_on_either"`, both lists empty,
totals `"0.00"`. The panel exists on every class; the CODE is what the screen renders in
the clerk's language (the `warnings` pattern; `DEF-BIL-5267` is what a server-composed
sentence on the approval surface costs).

### 2.2 The batch cell — `aggregate.discounts` (26.3, *"Accounts affected"*)

| Field | Type | Meaning |
|---|---|---|
| `outcome` | code | `re_priced_on_every_bill` (class R) · `nothing_is_repriced` (C) · `unchanged` (D) |
| `bills` | int | pinned bills carrying a reduction on either side |
| `accounts_affected` | int | DISTINCT accounts among them |
| `original_total` / `corrected_total` / `delta` | decimal string | Σ over those bills' panels |
| `currency` | CHAR(3) | the case's |
| `by_label[]` | list | per label: `label`, `code`, `bills`, `original_total`, `corrected_total`, `delta` |

```json
"discounts": {"outcome": "re_priced_on_every_bill", "bills": 3, "accounts_affected": 2,
  "original_total": "-20.00", "corrected_total": "-30.00", "delta": "-10.00", "currency": "USD",
  "by_label": [{"label": "Senior discount", "code": "SENIOR", "bills": 3,
                "original_total": "-20.00", "corrected_total": "-30.00", "delta": "-10.00"}]}
```

A display sum over the per-bill panels and nothing else — the discipline `aggregate` keeps
for every other figure. A case whose bills carry no reduction is `bills: 0` with empty
lists, drawn rather than omitted.

---

## 3 · Gap 2 — the scope table: `GET /corrections/resolve`

**Verb and path.** `GET /api/{tenant}/corrections/resolve` · `AnyTenantRole` (a read; an
Executive may look). Registered BEFORE `corrections/<case_id>` so `resolve` is never read
as a case id (a test holds that). **Writes nothing** — not even a case row.

**Query.** The POST's selector vocabulary, minus the reason: `scope_kind` (`single` ·
`run` · `cycle` · `plan` · `service` · `date_range`) + `invoice_id` / `invoice_ids` ·
`bill_run_id` · `cycle_id` · `plan_id` · `service_code` · `period_start` + `period_end`;
`page` / `per` (the standard envelope, 50 · 100 · 200 · 500 · 1000).

**Refusals** (422, `billing.correction.refused`, the sentence in `params.detail`): a scope
kind outside the six; a `run` / `cycle` / `plan` / `single` scope naming no id; an id that
is not uuid-shaped; a `service` scope naming no service; a `date_range` with one open end.
Before this change a `run` scope with no id filtered on `bill_run_id IS NULL` and refused a
step later with the wrong sentence; a non-uuid id reached the database as a 500. **The
same door serves `POST /corrections`**, so the POST is tightened identically.

**Response** — the standard list envelope plus four keys:

| Field | Type | Meaning |
|---|---|---|
| `count` / `next` / `previous` / `results` | envelope | `StandardPagination` |
| `results[].invoice_id` / `invoice_no` / `account_id` | ids / string | the bill |
| `results[].period_start` / `period_end` | ISO dates | PERIOD |
| `results[].amount` | decimal string | AMOUNT — what the bill ASKED (`amount_due_for`) |
| `results[].total` | decimal string | what it totals (differs only on a budget bill) |
| `results[].paid` | decimal string \| null | payments' net allocation against it; `null` when unreachable |
| `results[].state` | `paid` · `part_paid` · `unpaid` · null | STATE, money-derived |
| `results[].bill_status` | `issued` · `paid` | the lifecycle column, a different fact |
| `results[].currency` | CHAR(3) | |
| `totals.bills` | int | every bill in the scope, **not the page** |
| `totals.amount` | decimal string | Σ asked over the whole scope, in SQL |
| `totals.paid` | decimal string \| null | Σ payments' allocations over the whole scope, one statement (a subquery, never an id list) |
| `totals.currency` | CHAR(3) \| null | null when the scope spans two currencies (a problem names it) |
| `correctable_statuses` | `["issued", "paid"]` | p133's closing sentence as a FACT |
| `problems[]` | list | `payments_could_not_be_asked` · `scope_spans_more_than_one_currency` |
| `scope_kind` | string | echoed |

**Worked, p133's shape at three bills** (asked 241.80 / 239.90 / 247.20; paid 241.80 /
180.00 / 0):

```json
{"count": 3, "next": null, "previous": null,
 "results": [
   {"invoice_id": "…", "invoice_no": "BL-2607-000401", "account_id": "…",
    "period_start": "2026-07-01", "period_end": "2026-07-31",
    "amount": "241.800000", "total": "241.800000", "paid": "241.800000", "state": "paid",
    "bill_status": "issued", "currency": "USD"},
   {"invoice_no": "BL-2607-000402", "amount": "239.900000", "paid": "180.000000", "state": "part_paid", …},
   {"invoice_no": "BL-2607-000403", "amount": "247.200000", "paid": "0", "state": "unpaid", …}],
 "totals": {"bills": 3, "amount": "728.900000", "paid": "421.800000", "currency": "USD"},
 "correctable_statuses": ["issued", "paid"], "problems": [], "scope_kind": "run"}
```

Money is served at STORED precision as strings (rule 2); two-decimal display is the
client's. At fifty-five bills the page is 50 + 5 and `totals` reads 55 on both pages.

**`NFR-3` at T5.** `resolve_scope_queryset` is the ONE filter; `resolve_scope` (what
`open_case` pins) is that queryset materialised; the table pages it. Per page: one
statement for the bills, one for their allocations (grouped). Per scope: `COUNT` + `SUM`
in one aggregate, and the paid total as one aggregate over a **subquery** of the scope's
ids — no 40,000-id list crosses the seam. No cap anywhere.

---

## 4 · The seams — what crossed which boundary, and how

| Read | Published by | Named on billing's side | Shape |
|---|---|---|---|
| `allocated_for_invoices(ids)` | `apps/payments/billing_seam.py` | `payments_seam.ALLOCATED_MANY_READ` | `{str(invoice_id): Decimal}`; absent = nothing paid; **`None`** if unpublished |
| `allocated_total_for_invoices(ids_or_subquery)` | `apps/payments/billing_seam.py` | `payments_seam.ALLOCATED_TOTAL_READ` | `Decimal`; **`None`** if unpublished |
| `discount_versions_for_labels(labels, on_day)` | `apps/rating/selectors.py` | `rating_seam.DISCOUNT_VERSIONS_READ` | `{label: {code, discount_id, version_id, version_no, effective_from, effective_to, reason}}`; **`None`** if unpublished |

All three are resolved BY NAME at call time (B1; the idiom every seam here uses), tenant-
scoped explicitly on the publisher's side (rule 1) with RLS as the second guarantee, and
READS only — billing writes nothing in payments or rating. An unpublished read is `None`
and the caller publishes a `problems[]` entry, never a zero.

**TypeScript** — `07-frontend/src/api/billingOpsEndpoints.ts` gained
`CorrectionScopeBill`, `CorrectionScopeTotals`, `ResolveCorrectionScopeQuery`,
`CorrectionScopeResolution` and `resolveCorrectionScope(query)`. The discounts panel needs
no new type: `sections`, `aggregate` and `impact` are typed as records and the server owns
the shape. `tsc` clean, and proved capable of failing first (a planted `TS2322`).

---

## 5 · The walk — `GET /corrections/resolve` against PostgreSQL 16 and the seeded demo tenant

**How.** The sibling lane's `runserver` on port 8000 serves ITS worktree, which does not
carry this code, so this lane started its own on **127.0.0.1:8001** from its worktree
(`config.settings.local`, `JOBS_EAGER=false`, the same PostgreSQL 16 the orchestrator
provisioned — 347 migrations, RLS FORCE on 283 tables). Signed in through the real
door (`POST /auth/session` → 201) as `dana@brazosbendutilities.com` on `brazosbend`;
the session sets `app.tenant_id`, so every read below ran under RLS as the app role.
Bodies saved beside the walk script in the scratchpad (`walk/*.json`).

⚠ **Read as the app role WITHOUT `app.tenant_id`, the database shows one tenant and
nothing else — 0 accounts, 0 invoices.** That is RLS FORCE doing its job, not an empty
seed; this lane misread it as a dead seed for twenty minutes and told the orchestrator so.
Recorded because the next lane will do the same: count as the superuser, or `SET
app.tenant_id` first.

### 5.1 The scope table — the June bill run, 39 issued bills

`GET /corrections/resolve?scope_kind=run&bill_run_id=01a0a445-0dd3-…&per=50` → **200**:

```json
{"count": 39, "next": null, "previous": null,
 "totals": {"bills": 39, "amount": "11496.170000", "paid": "10802.570000", "currency": "USD"},
 "correctable_statuses": ["issued", "paid"], "problems": [], "scope_kind": "run",
 "results": [
  {"invoice_no": "BL-2607-000001", "period_start": "2026-06-01", "period_end": "2026-06-30",
   "amount": "158.100000", "total": "158.100000", "paid": "158.100000", "state": "paid",
   "bill_status": "issued", "currency": "USD", "invoice_id": "01a0a445-8633-…", "account_id": "01a0a444-7fbf-…"},
  {"invoice_no": "BL-2607-000002", "amount": "338.130000", "paid": "338.130000", "state": "paid", …},
  {"invoice_no": "BL-2607-000003", "amount": "501.330000", "paid": "0", "state": "unpaid", …},
  … 36 more]}
```

**37 `paid` · 2 `unpaid` · 0 `part_paid`** on this run (the seed pays in full or not at
all). **The SQL totals tie to the rows:** Σ `amount` over the 39 rows = `11,496.17`, Σ
`paid` = `10,802.57` — the same two figures the aggregate query returned, computed
independently. `bill_status` reads `issued` on every row **including the 37 that are
paid in full** — which is the whole reason STATE is money-derived (judgment 4).

### 5.2 The refusals, through the real door

* `GET /corrections/resolve?scope_kind=run` → **422** `BIZ-COMPLETENESS` ·
  `billing.correction.refused` · *"a run scope names the bill_run_id it is about
  (BR-BIL-014)."*
* `GET /corrections/resolve?scope_kind=cycle&cycle_id=not-an-id` → **422** · *"cycle_id
  'not-an-id' is not an id this product issues."*

### 5.3 The discounts panel — two previews opened, quoted, and ABANDONED

⚠ **The seed carries no discounted issued bill** (0 `invoice_lines` of kind `discount`
under the tenant), so the `on_both_bills` shape is quoted from the test fixture in §2 and
the two live previews below show the panel DRAWN over a bill with no reduction — which is
p129's *"an absent panel is drawn, never omitted"* proved on real data. Both cases were
opened (201, no money written), read, and closed with `POST …/abandon` and a stated
reason, so the bills are free for lane A.

**Class C, goodwill `$25.00` on `BL-2608-000052` (total `435.05`)** → `sections.the_money`:

```json
{"original_total": "435.05", "corrected_total": "435.05", "delta": "0",
 "tax_by_authority": [{"authority": "Tax Local", "original": "8.53", "corrected": "8.53", "delta": "0"}],
 "discounts": {"outcome": "nothing_is_repriced", "original": [], "corrected": [],
               "original_total": "0.00", "corrected_total": "0.00", "delta": "0.00",
               "currency": "USD", "service_date": "2026-08-02",
               "version_basis": "in_force_on_service_date", "problems": []},
 "open_question": {"oq": "OQ-215", …}}
```

The same panel rides on `bills_detail[0].impact.discounts`, byte-identical. The nine
sections came back in the server's order and there are still nine.

**Class R, `wrong_read` on `BL-2608-000071` (total `551.25`)** — the engine really
re-priced through rating on PostgreSQL: `original_total 551.25 · corrected_total 551.25
· delta 0.00`, and

```json
"discounts": {"outcome": "none_on_either", "original": [], "corrected": [],
              "original_total": "0.00", "corrected_total": "0.00", "delta": "0.00",
              "currency": "USD", "service_date": "2026-08-02",
              "version_basis": "in_force_on_service_date", "problems": []}
```

### 5.4 The same SQL on the real engine — the two test files under `config.settings.local`

`DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false pytest --reuse-db
tests/test_cr101_lane_b_scope_resolve.py tests/test_cr101_lane_b_discount_panel.py`
against the local PostgreSQL 16 (a fresh `test_sbh_agent_…` database, all 347 migrations):
**21 passed in 219.94s.** That is the proof that matters for `amount_asked_expression`
(a JSON key transform cast to numeric inside `COALESCE`), the paid total's `IN (subquery)`
over a `DISTINCT` scope, and the two grouped aggregates — every one of which the default
suite only ever runs on SQLite (hard-won law 14's blind spot). Both engines: **21/21**.

---

## 6 · What was NOT built, and why

| Not built | Why |
|---|---|
| A tenth preview section, or any tax field | `BR-BIL-044` forbids a tenth. **Ruled 2026-09-15, after this record was written:** the step-3 tax panel is section 3's tax-by-authority figures shown again, from the bills' own tax lines (decision log 2026-09-15) — a wave-2 SCREEN, no payload change, so this row stays true |
| The stamp itself — writing `discount_grants` at issue | `DEF-BIL-5341`'s fix; a write into rating's table from billing's issue path is a seam WRITE and a separate commitment. Until then the version is reconstructed and labelled |
| PAID / STATE on `bills_detail` (the case's pinned rows) | Not drawn there; the case shows the impact. The scope table is the step-1 surface |
| A sentence for the refusals | None new: every refusal reuses `billing.correction.refused` with its detail, so no catalogue key was added (G32 unchanged) |
| Any front-end screen | Lane A's |
| A version bump / `CHANGELOG` line | The orchestrator lands one for both lanes. The line this lane would have written, at the next `<change>` number above whatever the tip carries when it lands (the tip read `2.275.0` during the gate run): **`2.276.0` — Fix a bill: the step-2 preview shows the discounts on both bills with the programme version each names, and step 1 lists the bills a scope resolves to with what each asked, what was paid and a totals row (`GET /corrections/resolve`)** |

---

## 7 · Reds — every one dated, none this lane's

| Red | Where | Dated how |
|---|---|---|
| `test_cr059_cs36_settlement_preview.py::tc5` — `NOT NULL constraint failed: refunds.account_id` | neighbour suite | **Fails identically at the base tip `9cda92e6`** in the scratch extraction, before any change of this lane; the refund column landed with `payments/0018_cr059_cs7_refund_account.py`, whose history on this branch is the 2026-09-04 merge `d6d31c46` |
| `test_def_536_discount_gl.py::tc6` — `assert 17 == 13` designations | neighbour suite | **Fails identically at `9cda92e6`**; `ledger/chart.py`'s designation tuple grew past thirteen in history that reaches this branch through `d6d31c46` (2026-09-04) |
| `ruff F401` — `corrections` imported but unused in `corrections_api.py` | lint | Present at `9cda92e6` (1 error, same file); left, because removing another lane's import is not this lane's hunk |
| `black --check` on `corrections_api.py`, `payments/billing_seam.py`, `rating/selectors.py` | format | All three already non-black at `9cda92e6`; only files this lane made non-black were reformatted (`bulk_corrections.py` + the two new tests) |
| Gates: 48 FAIL of 125 run under `--changed 9cda92e6` (75 PASS · 2 SKIP · 1 not run) | tier 2 | **None names a file, id, register or symbol of this lane** — the full 228-line output was grepped for all nine changed paths, both new test files, both defect ids, the three registers and this file: zero hits. The gates whose SUBJECT includes this lane's files read: `G9` error-envelope PASS · `G20` seam-impl PASS (393 contracts, every new one resolves) · `G27` PASS · `G30` register PASS · `G31` PASS · `G35` version-lockstep PASS · `G46` PASS; `G1`, `G6`, `G7`, `G10`, `G17`, `G32`, `G33`, `G64`, `G95`, `G106`, `G116` are FAIL on OTHER files (`assets/equipment_reads.py`, `billing/api.py`, two migrations, `DEF-6440`/`DEF-MET-4497`, `billing.templates.layout_preview_refused`, `integrations.field.site_id`, `CR-100-BRC03-billing-step1.md`, …). The runner's own comparison against its previous record says **"0 newly failing, 0 newly fixed"** across this lane's change |

The two settlement/designation reds are **failing checks, not a broken build** — the
product starts (G120 PASS), so §9 of the skill applies (date and say so), not §10.

---

## 8 · Proof

| Check | Result |
|---|---|
| `tests/test_cr101_lane_b_discount_panel.py` | **12/12** — RED first against `9cda92e6` (all twelve on `KeyError: 'discounts'`), in `pytest`, the harness that runs them |
| `tests/test_cr101_lane_b_scope_resolve.py` | **9/9** — RED first against `9cda92e6` (`AttributeError … 'correction_scope_resolve'`; `resolve_scope_queryset` absent) |
| Neighbours: `test_us_bil_015/016/031`, `test_us_bil_surface_apis`, the four `cr059_cs36/37` files, `test_def_536_discount_gl`, `test_cr101_fix_a_bill_sections`, `test_us_pay_001/013`, `tests/golden` | **179 passed, 7 skipped, 1 xfailed, 2 failed** — both failures pre-exist at `9cda92e6` (§7) |
| `tests/golden` (14 engine-verified GTs) | green; WE-9's `247.87 / 227.95 / −19.92` untouched — this lane computes no new money |
| **The same 21 on PostgreSQL 16** (`config.settings.local`, fresh test database) | **21 passed in 219.94s** — the JSON key transform, the subquery `IN` and the aggregates proved on the engine that runs in production (§5.4) |
| `tsc --noEmit` | clean; a planted `TS2322` was seen to fail first |
| `ruff` on every touched Python file | clean except the one pre-existing F401 (§7) |
| `manage.py export_openapi` | regenerated; `/api/{tenant}/corrections/resolve` present |
| `run_gates.py --changed 9cda92e6` | 75 PASS · 48 FAIL · 2 SKIP of 125 run; no failure names this lane, and the runner's own comparison reports 0 newly failing (§7) |
| The walk (§5) | `GET /corrections/resolve` on a 39-bill run, two previews and two refusals, all through the real door on PostgreSQL 16 under RLS as the app role; the SQL totals tie to the rows |
| Push | `push_paths.sh` from pinned tip `9cda92e6` → `5f426eb4`; register guard `0 lines lost` on all three registers; `git diff --numstat` read as arithmetic (deletions only in the four files this lane edited in place); hunks of the four shared files read — all this lane's |

---

## 9 · Commits

| Commit | What |
|---|---|
| `5f426eb4` | the code (9 files), the two tests, the regenerated schema, the endpoint types, `BR-BIL-044`/`BR-BIL-792` amended, three decision-log rows, one review-ledger row, `DEF-BIL-5341` + `DEF-GOV-5342` |
| *(second)* | this file, with §5 filled in from the walk |
