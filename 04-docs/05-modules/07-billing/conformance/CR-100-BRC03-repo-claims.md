# Billing · step 1 · what the repository already claims, and whether it is still true

**Lane:** `CR-100-BRC03`, branch `claude/eager-johnson-r0k88b`, 2026-09-14.
**Scope:** the module's own record and the interfaces it describes — NOT the drawing.
Nothing was built, fixed or edited in product code by this lane.

**What this lane could NOT measure, said first rather than buried.**
* **The database.** No credentials are present in this lane's environment (`.env`
  does not exist; `DATABASE_URL`/`POSTGRES_*` are unset; `psql` as `postgres`
  refuses). So the briefing's *"`invoices` 0 · `invoice_lines` 0 · `bill_runs` 0
  against `meter_reads` 24"* is **carried forward unverified**, not confirmed.
* **The backend test suite.** For the same reason `DEF-BIL-5097`'s twenty reds
  were not re-run. They are reported as filed, not as re-measured.
* **No screen was walked in a browser by this lane.** The SPA answers 200 on
  `:8080` and the API 401 on `:8000`, so a walk is possible here — it was simply
  not this lane's job.

---

## 1 · The headline counts

| | Claimed | Measured today | |
|---|---|---|---|
| Claims re-checked | — | **18** | |
| Claims already **false** | — | **9** | half of them |
| Claims **stale but not false** | — | **1** | a line reference |
| Claims **confirmed true** | — | **6** | |
| Claims **not verifiable by this lane** | — | **2** | stated above |
| Billing endpoints | **36** across **8** url modules | **41** across **9** | **claim false** |
| Endpoints **served** (URL resolves) | — | **41 of 41** | probed |
| Endpoints reached by **no caller** | — | **3** | one already filed, two newly filed |
| Front-end route patterns under `/:tenant/` | **7** (`App.tsx:932–953`) | **7** (`App.tsx:1046–1066`) | **count true, line reference stale** |
| Golden — document self-consistency | 33 checks | **33 PASS, 0 FAIL** | true, re-run |
| Golden — **engine**-verified | 14 of 61 signed GTs | **14 of 61** | true, re-run |

**Defects filed by this lane: 4** — `DEF-BIL-5225`, `DEF-BIL-5226`,
`DEF-BIL-5227`, `DEF-BIL-5228`. Each was filed before its id is cited anywhere.

---

## 2 · The claim register — all eighteen, with the verdict and the evidence

Ordered by how much a step-2 lane would be hurt by believing the stale version.

### ❌ 1. *"36 endpoints across 8 url modules"* — **FALSE**

`06-backend/config/urls.py` mounts **nine** billing url modules (lines 165, 197,
198, 199, 200, 207, 219, 241, 262), and they declare **41** routes:

| url module | routes |
|---|---|
| `apps.billing.api` | 19 |
| `apps.billing.corrections_api` | 7 |
| `apps.billing.budget_api` | 7 |
| `apps.billing.documents_api` | 2 |
| `apps.billing.templates_api` | 2 |
| `apps.billing.layout_preview_api` | 1 |
| `apps.billing.print_api` | 1 |
| `apps.billing.credit_notes_api` | 1 |
| `apps.billing.statement_api` | 1 |
| **total** | **41** |

Read from the route tables, not inferred: `grep -n '^\s*path(' 06-backend/apps/billing/{api,corrections_api,budget_api,documents_api,templates_api,layout_preview_api,print_api,credit_notes_api,statement_api}.py`.

### ❌ 2. B14 has **30** rules (`1–21, 31–39`) — **FALSE TODAY**

Counted from B14's own status table, as `CLAUDE.md` instructs and as the brief
repeats: **33** — `1–21` and `31–42`. Rules **40, 41 and 42** were ratified
after the drawing was read and are binding on any build from it. The blueprint
index already flags this; it is re-counted here rather than taken on trust,
because the one thing `CLAUDE.md` says about this number is never to trust a
pointer to it.

### ❌ 3. `run_jobs.py`'s own rationale for the 25,000-account ceiling — **FALSE**

`06-backend/apps/billing/run_jobs.py:197–210`, verbatim:

> *"`CLAUDE.md`'s first line states the product's market: utilities and
> submetering **under 3,000 connections**. … 25,000 is therefore **eight times
> the largest utility the product is for**"*

**That first line moved on 2026-09-06.** The ICP ceiling is **40,000** (T5), so
25,000 is **0.625×** the largest tenant the product is now for, not 8×. The code
argues from a superseded sentence and `print_set.py:352` repeats the same
reasoning for `MAX_BILLS_PER_PRINT_SET_DEFAULT = 25_000`.

**Already filed** as `DEF-BIL-4224` (open, high) — *"THE BILL-RUN CEILING IS
25,000 ACCOUNTS AND THE ICP IS NOW 40,000 — a T5 tenant billing one cycle is
REFUSED"*. Not duplicated here. **What `DEF-BIL-4224` does not say, and this
pass adds:** the *justification text* in two files is itself the stale artefact,
so a lane raising the constant without rewriting the rationale leaves an
argument-from-3,000 in the money path. It also sits against `NFR-5` (no hard
caps anywhere).

### ❌ 4. `issue.py` tells every caller the paperless/SMS election *"cannot be read"* — **FALSE**

`06-backend/apps/billing/issue.py:504–505`, verbatim:

> *"ELECTION (`accounts.paperless` / `.sms_reminders`, PROPOSED-SCHEMA and
> unbuilt) cannot be read, so every bill gets the BR-BIL-036 print floor and no
> email or SMS"*

**Both columns exist.** `06-backend/apps/customers/models.py:482–483` declares
`paperless` and `sms_reminders`, added by migration
`customers/0034_cr052_delivery_election_and_template_override.py` on
**2026-08-31**. The decision log of 2026-09-13 states the same thing
independently (`DEF-CUS-5184`: both landed 2026-08-31, `CR-052` task 14).
The comment also survives at `issue.py:153` and `:2807`.

**Already filed** as `DEF-2819` (open) — *"THE BILL-ISSUE API STILL TELLS EVERY
CALLER THAT THE PAPERLESS/SMS ELECTION 'CANNOT BE READ', AND IT HAS BEEN
READABLE SINCE 2026-08-31."* Not duplicated. ⚠ **Its severity is `low` and the
behaviour it describes is a money-path delivery decision** — every bill forced to
the print floor, no email and no SMS. Step 2 should look at that grading rather
than inherit it.

### ❌ 5. `DEF-2843` — *"the catch-up run AND the pricing comparison each have a route and a client function and no screen calls either"* — **HALF FALSE**

* **Pricing comparison: now wired.** `getBillRunPricingShadow` is imported at
  `BillRunWizard.tsx:92`, queried at `:620–621`, and `PricingShadowPanel` is
  rendered at `:1999`.
* **Catch-up: still unwired.** `startCatchUpRun`
  (`billingOpsEndpoints.ts:785`) appears **exactly once** in all of
  `07-frontend/src` — its own definition.

The row still reads `open` with both halves in its title. A step-2 lane sizing
from the title would budget for two wirings and find one.

### ❌ 6. `DEF-2421` (open, high) — *"The Billing screen's primary action was disabled … no clerk could start a billing run"* — **MECHANISM GONE**

`BillsListPage.tsx:1044–1050` now renders the primary action as a
`GuardedButton` with `onClick={openRunWizard}` and `reason={runReason}` — the
ordinary `BR-SHL-025` permission guard. The hardcoded, comment-driven disable
the row describes is not in the file. The row still reads `open`.

### ❌ 7. `DEF-2450` (open, high) — *"THE ONE LINK ON THE BILL'S DOCUMENT PANEL WENT TO A ROUTE THAT DOES NOT EXIST"* — **MECHANISM GONE**

`BillDetailPage.tsx:863` now uses `<InlineLinkTo to={tenantPath(billDocumentPath(detail.id))}>`
and the route exists (`App.tsx:1046`, `billing/bills/:invoiceId/document`).
Lines 847–848 record the old broken `href={detail.document_url}` form as
history. The row still reads `open`.

### ❌ 8. `DEF-2451` (open, high) — *"PRINT BILL WAS A DISABLED BUTTON WHOSE REASON SAID THE ENDPOINT DID NOT EXIST"* — **MECHANISM GONE**

`BillDetailPage.tsx:434` renders a `ButtonLink` to `billDocumentPath(detail.id)`;
`:346` builds the PDF address from the served document read. The row still reads
`open`.

> ⚠ **Rows 6, 7 and 8 are one pattern and it is the finding, not three
> footnotes.** Three high-severity rows describe a product state that no longer
> exists, and a step-2 lane reading the register — which is what the register is
> for — would plan three fixes that are already made. **This pass did not close
> them**: closing is a fan-out, the body and the status must move together
> (`DEF-WRK-4030`), and a status edit from a measuring lane is exactly the
> half-act that caused the problem. They are routed to step 2 with the evidence
> above.

### ❌ 9. The pending queue's own copy — *"open the bill run and use its catch-up step"* — **FALSE**

`en.json:1366` (`billing.pending.awaits`). A case-insensitive search for
`catch-up` across all of `07-frontend/src` returns **zero** hits in
`BillRunWizard.tsx`: there is no catch-up step. `PendingQueuePage.tsx:250`
states the absence correctly in its own engineering trailer — *"no catch-up
BUTTON … named rather than guessed"* — so the note and the sentence a clerk
reads say opposite things.
**Filed by this lane: `DEF-BIL-5228`.**

### ⚠ 10. *"Route patterns mounted: 7 (`App.tsx:932–953`)"* — **COUNT TRUE, REFERENCE STALE**

Seven, resolved through the constants rather than pattern-matched:

| # | resolved path under `/:tenant/` | element | constant |
|---|---|---|---|
| 1 | `billing/bills/:invoiceId/document` | `BillDocumentPage` | `BILLING_ROUTE` |
| 2 | `billing/bills/:invoiceId` | `BillDetailPage` | `BILLING_ROUTE` |
| 3 | `billing/pending` | `PendingQueuePage` | `BILLING_PENDING_ROUTE` = `/billing/pending` |
| 4 | `billing/print` | `PrintBillsPage` | `BILLING_PRINT_ROUTE` = `/billing/print` |
| 5 | `billing/run` | `BillRunWizard` (S31) | `BILL_RUN_ROUTE` = `/billing/run` |
| 6 | `billing` | `BillsListPage` | `BILLING_ROUTE` = `/billing` |
| 7 | `billing/:tab` | `BillsListPage` | `BILLING_ROUTE` |

They live at **`App.tsx:1046–1066`** today, not `932–953`. Ordering is
load-bearing and still correct: the four-segment document route is declared above
`bills/:invoiceId`, and `pending`/`print` above `billing/:tab` so neither is read
as a seventh tab.

### ✅ 11. Every billing endpoint is actually served — **TRUE, 41 of 41**

Probed against the running API. An unauthenticated request to a mounted path
answers **401**; a control path (`/api/brazosbend/nonexistent-xyz`) answers
**404**, so the two are distinguishable. All 41 answered **401**. This is a
routing proof only — it says nothing about what any of them returns.

### ✅ 12. `10-scripts/03-golden-verify.py` reports 33 **document** checks — **TRUE**

Re-run today: `golden-verify: 33 PASS, 0 FAIL | ruling-derived (part 3, NOT
frozen): 6 PASS, 0 FAIL | CR-081 not-yet-re-signed (part 4): 9 PASS, 0 FAIL |
GT-1..16 self-consistency: 12 PASS, 0 FAIL, 4 NOT-CHECKABLE | self-test: 8/8
guards bite`. It imports no application code.

### ✅ 13. `06-backend/tests/golden/` is engine-verified on 14 of the 61 signed GTs — **TRUE**

`G64 --report`, today, verbatim:

> *"document self-consistency: 33 checks … ENGINE-VERIFIED: 14 of 61 GTs, in 14
> test file(s) under `06-backend/tests/golden/` — GT-1, GT-2, GT-3, GT-4, GT-5,
> GT-6, GT-7, GT-8, GT-9, GT-10, GT-11, GT-16, GT-24, GT-47. The second number
> is the one that protects a customer's bill, and it is the smaller one."*

Checked against the directory rather than the pointer: **14** `test_gt*.py` files,
matching `g64_engine_verified_gts.txt` name for name. See §4.

### ✅ 14. The blueprint was read at `2.235.0` and the product has moved — **TRUE**

`07-frontend/package.json` reads **`2.261.4`**. **26 versions** later.

### ✅ 15. S30 carries six tabs — **TRUE**

`billingShared.tsx:106–113`: `all · run · one-time · budget · fix · history`,
which is `01-overview.md`'s list (*All bills · Run bills · One-time bill ·
Budget Bills · Fix a bill · Past billing runs*).

### ✅ 16. The blueprint saw 4 of 15 screens with no backend — **TRUE OF THAT DOCUMENT, AND NO LONGER BINDING HERE**

This container has a live API (§11) and a live SPA. The constraint that produced
the document's biggest gap does not apply to step 2.

### ❔ 17. `DEF-BIL-5097` — twenty backend tests red across six billing suites — **NOT RE-MEASURED**

Filed 2026-09-12, status `open`, severity high. Named suites:
`test_cr052_w0_disconnected_at_the_cut.py` (5),
`test_us_bil_001_003_run_api.py` (5), `test_us_bil_003_decisions.py` (3),
`test_def_2856_break_actions_api.py` (4), `test_us_bil_004_run_loop.py` (2),
`test_us_bil_005_release.py` (1). **Fifteen of the twenty are in billing's own
run/release/decision path.** The filing lane dated them by measurement, in a
worktree at `397306ad6` without its change, and named the likely cause (the
plan-minimum move of 2026-09-10, `34137861d`) while recording that a bisect is
**impossible** on this history: a worktree at `34137861d^` cannot build a test
database because `rating/0032_tax_corrected_by` depends on
`rating/0031_plan_service_minimum_removed`, which lands one commit later.
**Step 2 must not read a green local run as disagreement with this row** —
`config/settings/test.py` hardcodes in-memory SQLite (`CLAUDE.md` law 14).

### ❔ 18. *"Billing has no seeded data — `invoices` 0, `invoice_lines` 0, `bill_runs` 0"* — **NOT VERIFIABLE BY THIS LANE**

No database credentials (see the preamble). Carried forward as the briefing's
measurement, not as this lane's.

---

## 3 · Endpoints reached by nothing — law 2's mirror

**Method, stated so it can be re-run and disputed.** Every exported front-end
function whose body issues a `client.<verb>` to a billing path was extracted,
then every other file under `07-frontend/src` was searched for that function's
name — **whole file, never piped through `head`**. 44 such functions; four have
no caller outside their own definition.

| function | endpoint | callers | verdict |
|---|---|---|---|
| `startCatchUpRun` | `POST /billing/runs/{id}/catch-up` | **0** | endpoint unreachable — `DEF-2843`, open |
| `queueAccountStatement` | `POST /accounts/{id}/statement` | **0** | endpoint unreachable — **`DEF-BIL-5225`** |
| `getBudgetAccount` | `GET /budget-billing/{account_id}` | **0** | endpoint unreachable — **`DEF-BIL-5227`** |
| `calculateBillRun` | `POST /billing/runs/{id}/calculate` | **0** | **dead duplicate, not a dead endpoint** — `calculateBillRunMaybeBackground` (`billRunEndpoints.ts:455`) reaches the same route and is wired |

⚠ **The fourth row is the distinction that matters and it is why the count is
three and not four.** `calculateBillRun` (`api/endpoints.ts:12248`) is dead
*code* over a *live* endpoint. Counting it as an unreachable endpoint would
overstate the gap; not noticing it at all would leave a second spelling of a
money verb for a later lane to pick up by accident.

### The statement case, in full, because it is the worst of the three

`POST /accounts/{id}/statement` is served (401 on probe).
`queueAccountStatement` is written. **No file imports `statementEndpoints.ts`
at all.** Meanwhile `accountRailReadiness.ts:238–239` still renders
`✉ Send statement` with a refusal, and the rail's own comment at `:215–227`
says, verbatim, *"**AND THE SERVER HALF EXISTS NOW** — `POST
/accounts/{id}/statement` (`apps/billing/statement.py`) gathers the period and
QUEUES the document"* and then describes the exact wiring that was never done.
**The knowledge was present in the file and the act was not** — a live screen
behind a dead control, which is the half of law 2 that `G13` cannot see.

**And the guard written to catch precisely this could not fire.**
`accountRailReadiness.ts:82` names its own safety net: *"`accountRailHoldExpiry.test.ts`
fails the day a statement route appears. A hold with no such test is a promise
nobody is keeping."* That test reads **one hand-named file** —
`ENDPOINTS = join(SRC, "api", "endpoints.ts")` at line 66 — and scans it for
`/export async function (\w*[Ss]tatement\w*)/`. `queueAccountStatement` landed
in `src/features/billing/statementEndpoints.ts`, which the test never opens. The
match list is empty, `toEqual([])` passes, and the failure message it would
print begins *"THAT IS GOOD NEWS"*.

This is `CLAUDE.md` law 7's **looking at the wrong thing**: the check is not
lying, it is reporting truthfully over a scope that excludes the file the thing
landed in. **Filed as `DEF-BIL-5226`.** It is also the answer to law 7's habit
(2) — *ask what would make this check pass wrongly* — which nobody asked of a
test whose whole purpose was to fail.

---

## 4 · The golden position, stated with both numbers

**Never write `33/33` as if it were engine proof, and never quote one number
alone.** For Billing specifically:

| | number | what it is |
|---|---|---|
| `10-scripts/03-golden-verify.py` | **33 checks, 33 PASS** | **document self-consistency.** It recomputes B4/B5's own figures from fixtures and **imports no application code**. It goes red when a document contradicts itself and **can never go red when the engine drifts.** |
| `06-backend/tests/golden/` | **14 of the 61 signed GTs** | **engine-verified.** These hand inputs to `apps.billing.rating_seam` and assert B5's frozen outputs. |

**So roughly three quarters of Billing's signed arithmetic — 47 of 61 GTs — has
no test that runs the engine.** That is the honest measure of this module's
money-path coverage and it is the number step 2 should size against.

Engine-verified, by name: **GT-1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 24, 47.**
Every other signed GT — including **GT-12, 13, 14, 15** and the whole of
**GT-17…GT-61** bar 24 and 47 — is checked only as a document.

`g64_engine_verified_gts.txt` records why the 47 are deliberately *not* listed
as a baseline: *"A baseline would turn 'three quarters of the signed billing
figures are not checked against the engine' into a number that looks handled. It
is open work and it stays visible in `DEF-2846`."*

⚠ **B4 and B5 are ❄️ FROZEN and finance-signed.** Both still open with
*"harness green (33/33)"*. That is TRUE of the harness; correcting it is a
finance **re-sign** (HUMAN-GUIDE §6), never an inline edit — `DEF-2846` holds
it deliberately. **Nothing in this pass may move a figure in either file.**

---

## 5 · Defects filed by this lane

| id | severity | category | what |
|---|---|---|---|
| `DEF-BIL-5225` | high | `built-not-wired` | `POST /accounts/{id}/statement` served, client function written, **nothing imports it**; the `✉ Send statement` glyph still refuses over a working server |
| `DEF-BIL-5226` | high | `check-that-does-not-check` | the hold-expiry test for that glyph scans only `api/endpoints.ts`; the function landed in `features/billing/statementEndpoints.ts`, so it **passes green over an expired hold** |
| `DEF-BIL-5227` | medium | `built-not-wired` | `GET /budget-billing/{account_id}` served, `getBudgetAccount` has **no caller anywhere** — its six path siblings are all wired, which is how it hid |
| `DEF-BIL-5228` | medium | `copy-i18n` | the pending queue tells a clerk to *"use its catch-up step"*; **the bill run wizard has no catch-up step** |

**Existing rows this pass re-checked and did NOT duplicate:** `DEF-2843`
(half-false today), `DEF-2819` (true, and under-graded), `DEF-BIL-4224` (true,
and its rationale text is stale in two files), `DEF-2421` / `DEF-2450` /
`DEF-2451` (mechanisms gone, rows still `open`), `DEF-BIL-5097` (open, not
re-measured).

## 6 · Questions for the PO

**None.** Nothing measured here contradicts a signed rule or moves a ❄️ FROZEN
B4/B5 figure. Every judgment above is ours and is recorded rather than asked
(`CLAUDE.md` law 13).

## 7 · What a step-2 lane should distrust

1. **The register's `open` column is not a statement about today.** Three
   high-severity rows describe a product that has moved (§2.6–2.8). Re-read the
   code before planning a fix from a title.
2. **A count in any pointer.** The endpoint count was wrong by five, the url
   module count by one, the B14 count by three, and the App.tsx line reference by
   114 lines. Every one of them was cheap to re-derive from the route table, the
   status table or the constants.
3. **A green check on a hold.** `DEF-BIL-5226` is a test written *specifically*
   to fire, that cannot. Ask of every guard in this module what would make it
   pass wrongly.
4. **A local green backend run.** `config/settings/test.py` hardcodes in-memory
   SQLite, so `DEF-BIL-5097`'s twenty reds and every `IntegrityError`-and-continue
   path need real PostgreSQL (`CLAUDE.md` law 14).
