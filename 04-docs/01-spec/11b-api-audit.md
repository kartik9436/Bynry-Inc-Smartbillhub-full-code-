# 11b — A11 API Conformance Audit (W0 entry task, 2026-08-09)

> **STATUS: PO-RATIFIED 2026-08-09** (A11 Addendum r2: Lane A A-1..A-8 individually · Lane B bloc CONFIRMED-DIRECTIONAL · Lane C bloc + page sizes 50/100/200/500/1000 default 50). §2 paths are no longer merely proposed — they are the adopted inventory, re-openable per-item via the normal batch.
> Verdict-first: **22 existing A11 entries audited → 16 OK · 6 STALE · 0 REMOVE**; **~120 endpoints** cover the 75 GAP screens (13a). The typed frontend client is generated only from **A11-as-amended-by-this-audit** (TD-19: drf-spectacular schema CI-diffed against audited A11). Every path in §2 is **PROPOSED** — ratification happens via the normal PO daily batch; nothing here is law until the A11 addendum lands.
>
> Audit basis: A11 (`11-api-contracts.md`) · 13a screen map · B12 §3 + Addendum r1 (error catalog + full HTTP-series contract) · module `02-business-rules.md` ×14 · epic field maps · key rulings BR-IDN-029, BR-PAY-021, BR-NOT-005, BR-BIL-016, TD-19, BR-TEN-043, HR-4 immutability.

---

## 1. Existing A11 entries — verdicts

OK = usable as written (amendments noted are shape/param tightening, not contradictions) · STALE = contradicts a named ruling · REMOVE = endpoint shouldn't exist under current law.

| A11 entry (verbatim path) | Verdict | Why / which ruling |
|---|---|---|
| `POST /tenants` (S6) | **OK** | Endpoint survives; screen ref stale — S6 superseded, commit happens at **S114** (13a). Amend: idempotent on subdomain natural key, repeat returns existing tenant (BR-TEN-010); 201 + Location; public/unauthenticated. |
| `GET /dashboard/summary` (S7) | **OK** | Amend response: every money KPI carries a **basis label** (BR-REP-001; "Cash today" = CLEARING per BR-REP-010); add ops chips — delivery health, pending billing, returned mail, corrections pending, tie-out drift (BR-REP-015). |
| `GET /accounts` (S17) | **OK** | Amend params to the ratified capability row: search acct#/name/address/meter#; filters status·category·plan·autopay·balance>0 (BR-CUS-053); URL grammar `q/sort/dir/page/per/f.‹name›` (BR-SHL-011). |
| `GET /accounts/{id}` (S21) | **OK** | Read-model stands (BR-CUS-033/034). Cross-tenant id → **404 never 403** (B12 r1, HR-1). Plan block = account snapshot, not unit plan (BR-CUS-014). |
| `POST /accounts/{id}/payments` (S22) | **STALE** | Params `amount, method, apply_to` contradict **BR-PAY-021** (posting date ≠ clearing date — BOTH always required), **BR-PAY-033** (posting date USER-ENTERED, never system timestamp), **BR-PAY-012** (every payment carries a purpose: bill\|deposit\|plan-down\|prepay), BR-PAY-022 (reference + allocation choice). Entry-point placement is fine (BR-CUS-037) — payload must be regenerated. **SERVED 2026-08-11 with the payload REGENERATED — see §2.9b for the body that was chosen and why.** In one line: `amount` (decimal string) · `posted_at` **required**, the user's, never a clock · `cleared_at` absent = still processing · `method` (tenant lookup code) · `confirmation` · `memo` · `purpose` (default `bill`; the other three refused BY NAME) · `apply_to` + `targets[]` · `currency` · **`idempotency_key` REQUIRED**. A duplicate submit answers **200 + `created:false`**, not G7's 409 — see §2.9b. |
| `GET /reads` (S25) | **OK** | Amend: `channel` param + explicit unit on every row (BR-MET-059, CLAUDE.md #3); hot-window default 2yr + explicit `archive` param, no unbounded endpoint (BR-MET-055); default view = Needs-attention (BR-MET-060). |
| `POST /reads/import` (S28) | **STALE** | Single fire-and-forget shape contradicts the **staged batch lifecycle** — no `meter_reads` row before commit, per-row severity dispositions between upload and post (**BR-MET-012/015/016**), and the **202 + job_id** async law (B12 r1: poll `/jobs/{id}`, "rule results" are not a synchronous response). Replace with the batch resource set in §2 (Meter Reads). Idempotency key = file+tags, mechanics Eng-Lead 🔒 (BR-MET-018/OQ-044). |
| `POST /billing/runs` (S31) | **STALE** | Response `run id, exceptions` contradicts **B12 r1** (202 + job_id for EVERY async op — exceptions arrive via the findings/exceptions GETs, never inline) and omits **BR-BIL-005** idempotency (unique tenant+cycle+period → repeat = 409 BIZ-IDEMPOTENT with who/when/link) and **BR-BIL-015** catch-up sub-runs (parent-linked, scope-keyed). Path + method stay. **SERVED 2026-08-11 — see §2.8b for the shape that was chosen and why.** In one line: the row is created SYNCHRONOUSLY (201 with `id` inline, `job_id: null`), because B12 r1's 202+job_id law is about ASYNC operations and creating a `bill_runs` row queues no work — and there is no job runner on this deployment to queue it to (TD-17). The BR-BIL-005 half of the criticism IS implemented: a repeat is 409 BIZ-IDEMPOTENT carrying `run_id`, `ran_by` and `ran_at`. Catch-up sub-runs (`parent_run`) remain unserved — US-BIL-006, its own story. |
| `GET /billing/runs/{id}/findings` (S31.2) | **OK** | Per-tab datasets, paginated — matches EP-BIL-01. **SERVED 2026-08-11 (§2.8b), with ONE stated deviation: it is NOT paginated.** `runs.PreparedRun` is not a queryset — it is one in-memory pass over the run's accounts, and its three lists are the DENOMINATOR the S31.2 KPI strip counts ("480 of 500"). A page of it would make `ready.length` a page size and the screen would confidently report the wrong number of accounts. The set is bounded by the cycle's own size. |
| `GET /payments` (S33) | **OK** | Amend: posting-date AND clearing-date filters (BR-PAY-021), `purpose` filter (BR-PAY-012), full IS-5 capability row (BR-PAY-027). **SERVED 2026-08-11 with every amendment honoured** — `f.posted_from/to`, `f.cleared_from/to`, `f.purpose`, `f.type`, `f.method`, `f.status`, `f.account_id` (the S21 Payments tab); sorts `posted_at`/`cleared_at`/`amount`/`account`/`status`, default `posted_at desc`; search on account #, customer, confirmation #. **TWO members ride beside the DRF envelope** — `totals` (the capability row's filter total, null-with-a-reason when it cannot be stated honestly) and `methods` (the tenant's live BR-PAY-026 list, served here because `GET /lookups/payment_methods` 404s — payments owns that list's CONTENT under BR-TEN-031 and registers no handler). See §2.9b. |
| `GET /ar/outstanding` (S34) | **OK** | Amend: "days late" = today − oldest unpaid invoice due date, server-derived (BR-PAY-032); AR high→low default (BR-PAY-029). |
| `GET /finance/deposits` (S37) | **OK** | Amend: batch "day" = POSTING date (BR-PAY-025, BR-REP-013); batch numbers from tenant DEP- series. |
| `POST /finance/bank-imports` (S38) | **STALE** | "match preview" synchronous response contradicts **B12 r1** (202 + job_id) and the **staged import standard** (BR-PAY-023: batch → per-row validation → preview → commit). Matching runs on **CLEARING date ±3 days** (BR-PAY-019/021); "Force match anyway" permanently superseded — every difference carries reason + GL (BR-PAY-035). Replace with batch lifecycle in §2 (Finance). |
| `GET /finance/deposits/{id}` (S39) | **OK** | Read model stands (payments + bank line + trail). |
| `GET /finance/taxes` (S41) | **OK** | Amend response: **dual-basis always** — billed AND collected per authority + basis indicator + remitted/outstanding columns (BR-LED-002/013, BR-REP-003). |
| `POST /finance/exports` (S42) | **STALE** | Response "journal entries" + note "QBO/Xero adapters" contradict **BR-LED-020/BR-INT-010** (v1 = FILE/batch export targets only; QBO/Xero live OAuth sync = v2), **BR-LED-017** (export requires the covered period CLOSED → open period = 409 BIZ-LOCKED; granularity per-export: period summary or weekly), **BR-LED-004** (export = recorded IDEMPOTENT batch resource with drill-back — no double-handover). Async file generation → 202 + export-batch id. |
| `GET /reports/{key}` (S44/46) | **OK** | Also serves S59/S60 (13a). Amend: basis label in every header (BR-REP-001); filters enumerate LIVE vocabularies, never hardcoded (BR-REP-006); downloads per IS-11 (BR-REP-018). |
| `GET /integrations` (addendum) | **OK** | Per-tenant connection states (BR-INT-002); later-wave cards render "Coming soon" state (BR-INT-001). |
| `POST /integrations/{key}/connect` (addendum) | **OK** | Modal contract confirmed verbatim by BR-INT-002. Secrets: encrypted per-tenant, never echoed back, masked refs only (BR-INT-003). |
| `POST /integrations/{key}/test` (addendum) | **OK** | BR-INT-002; failures surface "Failed · Retry", never silent (BR-INT-015). |
| `DELETE /integrations/{key}` (addendum) | **OK** | Disconnect semantics per BR-INT-016: secret destroyed, queue rows rest `queued`, batches + idempotency records survive; consequence messaging; audit row (BR-INT-014). |
| Addendum **key list** (`quickbooks, xero, stripe, plaid, itron, sensus, twilio, lob, sso, email(…)`) | **STALE** | Contradicts the **BR-INT-001 v1 connector matrix**: Stripe/Plaid (W7), Twilio (v1.1), QBO/Xero live sync, Itron/Sensus MDM, SSO (v2) are VISIBLE-BUT-LATER — Connect **disabled at UI AND API** (attempt → 409 BIZ-STATE + BR-AUD-018 attempt row). Missing v1-REAL keys: transactional **ESP** (BR-INT-006), **print vendor** (BR-INT-017), and bank/lockbox + accounting-file connections — which are per-tenant **profile collections**, not single-key connects (BR-INT-009/010) → profile CRUD in §2 (Integrations). MDM enablement additionally gated by BR-INT-012 capacity sign-off. |

**§1 count: 16 OK · 6 STALE (S22 payments · S28 reads/import · S31 billing/runs · S38 bank-imports · S42 finance/exports · addendum key list) · 0 REMOVE.**

---

## 2. Missing endpoint inventory (per module, from the 13a GAP list + story field maps)

Every path below is **PROPOSED** (style-consistent with A11's existing REST conventions: plural nouns, tenant-implicit via subdomain, nesting for entry-points). Async ops return **202 + job_id**, polled at `GET /jobs/{id}` (§3-G3). All 75 GAP screens appear; the two partial screens (S8, S22) appear for their uncovered parts. Screens needing no endpoint are listed with "none" so the worklist closes.

### 2.1 Public & onboarding — tenancy · identity (S1–S5, S110–S113)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S1 · S112 | Pricing/package cards (public + wizard step 3) | `GET /public/pricing-plans` | — | B10 subscription catalog; unauthenticated; ETag/304; rate-limited 429 |
| S2 | Welcome fork (first-time / sign-in) | none — static route | — | no data call |
| S4 · S5 | superseded by S110–S114 | none — retire/retag in A1 (13a finding) | — | no endpoints minted for retired screens |
| S3 | Sign-in | `POST /auth/session` | — | BR-IDN-001/029: subdomain resolves tenant FIRST, then (tenant,email); BR-IDN-002 one generic failure msg; BR-IDN-025 5-fail→15-min lock; 429 throttle |
| S3 · S48 | Sign-out | `DELETE /auth/session` | — | BR-IDN-007, BR-SHL-009 (clears tenant context/caches) |
| S110 | Subdomain availability check | `GET /public/subdomain-check?subdomain=` | — | BR-TEN-011 charset/uniqueness/reserved; re-checked server-side at commit; public, throttled |
| S110–S113 | Wizard step staging | none — client-side state; single transactional commit = existing `POST /tenants` at S114 | — | BR-SHL-019 (one commit call, double-click safe); BR-TEN-010 atomic + idempotent |

### 2.2 Platform shell & dashboard (S48, S62 + shell-wide)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| all authed | Global search | `GET /search?q=` | — | Already flagged PROPOSED in BR-SHL-005/028; ≤5 per group; RLS + role-scoped (BR-SHL-006). **FIFTEEN groups as of 2026-09-05 (`CR-073`)** — premises · units · assets · master accounts · accounts · customers · bills · payments · service requests · work orders · work order templates · parts · workforce · plans · charge codes. SERVED by `apps/tenancy/search_api.py`; still a PROPOSED A11 addition |
| all authed | Notifications bell | `GET /notifications` · `POST /notifications/{id}/read` · `POST /notifications/read-all` | — | BR-SHL-007/026 v1 event set; tenant-scoped |
| all authed | User preferences (sidebar, column sets, saved mappings) | `GET /me/preferences` · `PUT /me/preferences/{key}` | — | BR-SHL-024/027: server-side ALWAYS, never localStorage-only; jsonb ≤32KB, last-write-wins |
| S48 | My profile view/edit | `GET /me` · `PATCH /me` | — | BR-IDN-015/027; email change = SysAdmin-only via users endpoint (BR-IDN-017); role never editable |
| S48 | Change password | `POST /me/password` | — | BR-IDN-016 current-pw required + policy; "sign out other sessions" flag default on |
| S48 | 2FA enrollment | **none in v1** | — | BR-IDN-028: 2FA entirely v2 — mint no endpoint |
| S62 | Post-signup checklist | `GET /tenants/checklist` · `POST /tenants/checklist/{item}/dismiss` | — | BR-TEN-015: computed from live data; manual mark-done advisory items only |
| all authed | **The app shell's boot read — the branding and the formats every screen needs to DRAW itself** | `GET /shell/display` | — | **`BR-SHL-252`. Read-only; ANY signed-in tenant role; `core.permissions.ShellDisplayRead` refuses every mutating verb for every role including the System Admin.** Serves `regional` = country · timezone · language · first_day_of_week · currency · number_format · date_format · time_format, `company` = legal_name · dba_name · has_logo · mark · brand_primary_hex, and — **added 2026-09-06, `DEF-SHL-4283`** — `period` = fy_label · period · start · end · status, the computed accounting period card (`BR-TEN-022`), or `null` where no fiscal year start is set. ⚠ **IT CARRIES NO FINANCE POLICY** — `accounting_method`, `close_cadence`, `close_day`, `lock_closed_periods`, `fy_start_*` and the card's own `close_by` stay on `GET /settings/regional`, which stays Admin/Executive. **The period WINDOW is what a screen needs to draw itself; the CLOSE DEADLINE is not**, and withholding the window locked a Billing Clerk out of `Reports → By premises` and put a false sentence on `Payments → Refunds`. ⚠ **DELIBERATELY OUTSIDE THE `settings/…` FAMILY**: the whole rule is that these values are not settings administration, and a path filed under `settings` would invite the next lane to gate them like settings again — which is `DEF-SHL-4272`, sixteen days of a Billing Clerk seeing *"We couldn't load your regional settings."* on every screen in the product. The Settings SCREENS keep reading `GET /settings/company` / `GET /settings/regional`; only the shell moved |

### 2.3 Settings — tenancy · identity · metering · notifications (S8 nine GAP tabs, S63–S66, S69–S71)

Every Settings write: staged per-tab atomic save + ONE audit row (BR-TEN-024/016); all config changes EVENT-TIME forward, never retroactive (**BR-TEN-043**).

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S8·Company | Read/save company identity, brand, remittance | `GET /settings/company` · `PUT /settings/company` | — | BR-TEN-017 stamped at issue-time only; BR-TEN-018 EIN format-only |
| S8·Company | Logo upload | `POST /settings/company/logo` | — | BR-TEN-019 SVG/PNG ≤2MB, sanitized; 413/415 per B12 r1 |
| S8·Regional | Regional & formats | `GET /settings/regional` · `PUT /settings/regional` | — | BR-TEN-020 display-time only; currency LOCKED once financial records exist → 409 BIZ-LOCKED (BR-TEN-021/042) |
| S8·Services & UoM | Toggle services, per-service UoM | `GET /settings/services` · `PUT /settings/services/{service}` | — | BR-TEN-025 closed catalog; guarded disable w/ reference counts → 409 BIZ-STATE (BR-TEN-026); UoM forward-only (BR-TEN-027) |
| S8·Users | User CRUD (per-tenant identity) | `GET /users` · `POST /users` · `PATCH /users/{id}` · `POST /users/{id}/deactivate` · `POST /users/{id}/reactivate` · `DELETE /users/{id}` · `POST /users/{id}/temp-password` | — | **BR-IDN-029** per-tenant users; BR-IDN-008/009 SysAdmin-only, server-enforced; BR-IDN-022/023 temp-password flow (NO auth emails v1, BR-IDN-021); last-admin guard → 409 BIZ-STATE (BR-IDN-013); remove blocked while referenced (BR-IDN-012) |
| S8·Users | Roles & permissions matrix | `GET /roles` | — | BR-IDN-014 read-only platform catalog; ETag/304 |
| S8·Security | Security policy | `GET /settings/security-policy` · `PUT /settings/security-policy` | — | BR-IDN-019/025/026; IP allowlist self-lockout guard → 422 BIZ-STATE (BR-IDN-020); no 2FA section v1 (BR-IDN-028) |
| S8·Reference data · S65 | Lookup-list CRUD (payment methods, statuses, types, reason codes, account types/sub-types, tax jurisdictions…) | `GET /lookups/{list}` · `POST /lookups/{list}` · `PATCH /lookups/{list}/{id}` · `POST /lookups/{list}/{id}/deactivate` · `DELETE /lookups/{list}/{id}` | — | BR-TEN-036 seeded + tenant-extensible; BR-TEN-029 used-by live; BR-TEN-030 code immutable once used; BR-TEN-034 audit-lock delete → 409; writes route through owning-module services (BR-TEN-031); ETag/304 on GET (B12 r1 3xx row) |
| S8·Routes & Cycles | Route/cycle CRUD | `GET /routes` · `POST /routes` · `PATCH /routes/{id}` · `POST /routes/{id}/deactivate` · `DELETE /routes/{id}` · `GET /cycles` · `POST /cycles` · `PATCH /cycles/{id}` · `DELETE /cycles/{id}` | — | BR-MET-008/009/010; route membership = selected premises+units w/ optional walk order (**BR-MET-033**, supersedes sequence ranges). ⚠ **CR-029 D7 (2026-08-23):** both list GETs answer the `{count, next, previous, results}` envelope to EVERY caller — `q/sort/dir/page/per/f.<name>` honoured server-side (BR-SHL-011). The transitional bare-array branch retired with RC-W5-T6 |
| S8·Routes & Cycles | **Code preview** (CR-029 D5) | `GET /routes/next-code` · `GET /cycles/next-code` | — | BR-MET-073/077 — the wizard's editable pre-fill. A PREVIEW: it renders and allocates NOTHING, so opening a wizard and cancelling does not burn a number. The allocated code may differ from the previewed one when two admins open at once, and that is stated rather than reserved |
| S8·SET-06.2/06.3 | **Route wizard pickers** (CR-029) | `GET /routes/premises-picker` · `GET /routes/meter-picker` | — | Step 2's premises list with its "moves from RT-002" badges (BR-MET-074) and step 3's expandable premises→unit→meter sub-table with each exclusion's two-word reason (BR-MET-075) |
| **SET-06D** | **Route detail** (CR-029 D3/D11/D12) | `GET /routes/{id}` · `PUT /routes/{id}/premises-order` · `GET /routes/{id}/read-windows` · `GET /routes/{id}/accounts` | — | `premises-order` is `walk_order`'s FIRST writer since the column was created (gap G5), at **per-premises** grain (D11 — one stop, one number, however many units); idempotent and audited (BR-MET-048). `read-windows` is SET-06D's Read history, a bounded HISTORY: `limit` clamps 1…200, **no `page`** — a history grows at the top, so page 2 of it serves duplicates and skips (RC-W5-T6 asked and ruled it stays). `accounts` is STATUS ONLY — **no Balance column** (D12), asserted absent by test, and one batched read for the whole route rather than `GET /accounts?unit_id=` per unit (D7) |
| **SET-07D** | **Cycle detail** (CR-029 D13) | `GET /cycles/{id}` · `GET /cycles/coverage` | — | The id route was PATCH+DELETE only, so the detail fetched EVERY cycle and picked its row out of the array; it serves the same `cycle_dict` the list serves, schedule proposal included. `coverage` is the KPI trio + the bounded uncovered list beside its FULL count (`truncated` says when the rows were cut, so a KPI computed from `uncovered.length` cannot silently stop growing). **No account-level cycle assignment exists** (D13) — an account's cycle derives account → unit → route → cycle at BILL-RUN time; uncovered accounts are shown with what they lack (a route) |
| **SET-07D·Runs** | **Bill-run history** (CR-029) | `GET /billing/runs` | — | Run · Period · Issued · Accounts · Status, newest first, scoped by `f.cycle_id`. Bounded HISTORY like `read-windows`: `limit` 1…200, **no `page`**, same reason. **No money of any kind** (BR-MET-078 as hardened by CR-029); `run_no` is served NULL because no bill-run number series exists — **OQ-342** is open and a test HOLDS it null so no lane quietly fills it in |
| S8·Numbering | Number series formats | `GET /settings/number-series` · `PUT /settings/number-series/{series}` | — | BR-TEN-035 forward-only, issued numbers never renumbered; PMT/DEP/RCT/EXP series (BR-TEN-041) |
| S8·Notifications | Delivery/dispatch home | see §2.13 queue endpoints + `GET /integrations` provider status | — | BR-TEN-041 #8; BR-INT-015 provider health |
| S63 | Holiday calendar CRUD | `GET /settings/holidays` · `POST /settings/holidays` · `PATCH /settings/holidays/{id}` · `DELETE /settings/holidays/{id}` | — | BR-TEN-039; feeds TOU day-typing (BR-RAT-021/033 — holidays bill off-peak) |
| S64 | Read validation & estimation rules | `GET /settings/read-validation` · `PUT /settings/read-validation` | — | BR-MET-020 per-service thresholds, never hardcoded; BR-MET-026/027 estimation params |
| S66 | Billing defaults | `GET /settings/billing-defaults` · `PUT /settings/billing-defaults` | — | BR-BIL-021 seeded config family (late %/min/grace, minimum-bill, guardrail %, allocation order…) |
| S69 | Budget billing rules | `GET /settings/budget-billing` · `PUT /settings/budget-billing` | — | BR-BIL-017 every parameter tenant-set |
| S70 | Collections & notices rules | `GET /settings/collections` · `PUT /settings/collections` | — | BR-PAY-016/017 cadence; ladders finish under in-force intervals (BR-TEN-043) |
| S71 | Finance controls | `GET /settings/finance-controls` · `PUT /settings/finance-controls` | — | bank-match ±3d (BR-PAY-019), small-balance write-off bounds (BR-BIL-013), DSO target (BR-REP-022), correction threshold (BR-BIL-014) |

### 2.4 Plans & Rates — rating (S9–S13)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S9 (tab 1) | Plans list/detail | `GET /plans` · `GET /plans/{id}` | — | BR-RAT-030 lifecycle filter; published-only for assignment pickers |
| S10 | New Plan wizard | `POST /plans` (draft) · `PATCH /plans/{id}` · `POST /plans/{id}/publish` · `POST /plans/{id}/archive` | — | draft→published→archived (BR-RAT-030); staff-assignment-only v1 (BR-RAT-039); plan-as-bundle deposit/charge/tax rules (BR-RAT-023/025) |
| S9 (tab 2) · S11 | Rate schedules + versions | `GET /rate-schedules` · `POST /rate-schedules` (draft, resumable) · `PATCH /rate-schedules/{id}` · `POST /rate-schedules/{id}/activate` · `POST /rate-schedules/{id}/versions` | — | BR-RAT-031 (approval workflow REMOVED — no approve endpoint); tier/TOU/season validation → 422 VAL (BR-RAT-032/033/034); versions append-only + `rate_change_log` (BR-RAT-037) |
| S12 · S9 (tab 3) | Charge codes | `GET /charges` · `POST /charges` · `PATCH /charges/{id}` · `POST /charges/{id}/deactivate` | — | BR-RAT-035 audit-lock while referenced; amount rules flat/percent/percent-min (BR-RAT-041) |
| S13 · S9 (tab 4) | Taxes & fees | `GET /taxes` · `POST /taxes` · `PATCH /taxes/{id}` · `POST /taxes/{id}/deactivate` | — | BR-RAT-036 forms (Fees/tax-on-tax checkboxes REMOVED — B4.2 wins); marginal per-unit threshold (BR-RAT-042); jurisdictions tenant-entered (BR-TEN-037) |
| S9 (bulk) | Bulk rate update | `POST /rate-changes` | 202 | BR-RAT-040 one atomic all-or-none batch, append-only, never re-run |

### 2.5 Premises & Units — metering (S14–S16)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S14 | Premises list/detail | `GET /premises` · `GET /premises/{id}` · `POST /premises` · `PATCH /premises/{id}` · `POST /premises/{id}/deactivate` | — | BR-MET-001/034/037/047; detail tabs Units/Assets/Accounts/Audit (BR-MET-045) |
| S15 | Units list/detail | `GET /units` · `GET /units/{id}` · `PATCH /units/{id}` · `POST /units/{id}/deactivate` | — | BR-MET-002; occupancy DERIVED, never settable (BR-MET-036); no cross-premises moves (BR-MET-046) |
| S16 | Add premises + units + meters (single) | `POST /premises` with nested units/assets · `POST /units` | — | asset auto-create both directions (BR-AST-028); ≤1 meter/service/unit (BR-MET-006) |
| S16 (bulk) | Pattern generator + CSV import | `POST /premises/imports` → `GET /premises/imports/{id}` → `POST /premises/imports/{id}/commit` | 202 | BR-MET-005/031/038: both paths; ≤3,000/run pattern, 10,000-row CSV cap → 422 BIZ-CAP; staged, skip-errors ON |
| S16 · S15 | Unit plan assignment (+ bulk, + correction override) | `POST /units/{id}/plan-assignments` · `POST /units/plan-assignments/bulk` | — | BR-MET-040/041/042 (override = warning + audit, no proration); syncs account snapshot (BR-CUS-014) |

### 2.6 Accounts — customers (S18–S24, S68 + S22 uncovered modals)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S18 | New Account wizard (draft + commit) | `POST /accounts` (status pending, save-draft/resume) · `PATCH /accounts/{id}` (pending only) · `POST /accounts/{id}/activate` | — | BR-CUS-018 draft never billed, doesn't reserve unit; plan REQUIRED at activation (BR-MET-040) |
| S18 step 1 | Customer duplicate check (advisory) | `GET /customers/duplicate-check` | — | BR-CUS-019 advisory; resolve by LINKING (BR-CUS-054) |
| S18 · S21 | Customer entity (first-class) | `GET /customers` · `POST /customers` · `PATCH /customers/{id}` · `GET /customers/{id}/accounts` | — | **BR-CUS-054** one customer ↔ many accounts; PII masked display (BR-CUS-045) |
| S19 | Move-In wizard | `POST /accounts/{id}/move-in` | — | vacant/reserved units only (BR-CUS-020); initial reads via metering service (BR-CUS-021); deposit carry-forward (BR-CUS-024) |
| S20 | Move-Out wizard + final-bill preview | `POST /accounts/{id}/move-out/preview` · `POST /accounts/{id}/move-out` | — | BR-CUS-030/031 final-bill handoff; same-day boundary (BR-CUS-056); settlement paths (BR-BIL-013) |
| S21 (tabs) | Tab read-models (Bills/Payments/Usage/Meters/Audit) | reuse module lists with `f.account_id` filter (`GET /invoices` · `GET /payments` · `GET /reads` · `GET /assets` · `GET /audit-log`) | — | BR-CUS-034 read via owning-module services; avoids duplicate per-tab paths |
| S21 | Notes | `GET /accounts/{id}/notes` · `POST /accounts/{id}/notes` · `PATCH /accounts/{id}/notes/{noteId}` | — | BR-CUS-035 |
| S21 | Documents | `GET /accounts/{id}/documents` · `POST /accounts/{id}/documents` | — | BR-CUS-036; upload guards 413/415 and the allowlist (BR-SHL-031) — ~~malware scan~~ SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347`; system/contract docs audit-locked |
| S22 (modal 2) | Adjustment (credit/debit) | `POST /accounts/{id}/adjustments` | — | BR-CUS-038 approval-gated → 409 BIZ-APPROVAL when gate unsatisfied; BR-PAY-037 same-user approve OK v1 |
| S22 (modal 3) | Generate statement | `POST /accounts/{id}/statements` | — | statement ≠ bill, range ledger + disclaimer (BR-CUS-040) |
| S22 (modal 4) | Print/re-render issued bill | `GET /invoices/{id}/document` | — | renders PINNED template version forever (BR-BIL-026, BR-CUS-040) — never recomputes |
| S22 (modal 5) | Disconnect notice | `POST /accounts/{id}/notices` | — | BR-CUS-039 tiers per A19; queue-based (BR-NOT-005); medical-hold excluded |
| S22 (modals 6–7) | Note / flag account | covered by notes + `PATCH /accounts/{id}` | — | status changes explicit + audited (BR-PAY-036) |
| S23 | Change Plan wizard + proration preview | `POST /accounts/{id}/plan-changes/preview` · `POST /accounts/{id}/plan-changes` | — | BR-CUS-041 B4.3 proration server-computed; deposit NO recompute v1 (BR-CUS-062); W8 wave per B12 |
| S24 | Payment Plan wizard | `POST /accounts/{id}/payment-plans` · `GET /accounts/{id}/payment-plans` · `PATCH /payment-plans/{id}` (proposed state only) · `POST /payment-plans/{id}/void` | — | BR-CUS-043 schedule math server-side (B4.4); activation ONLY on e-signature (BR-CUS-044, DocuSign seam); one live plan/account |
| S68 | Account onboarding import (brownfield) | `POST /accounts/imports` → `GET /accounts/imports/{id}` → `PUT /accounts/imports/{id}/mappings` → `POST /accounts/imports/{id}/commit` | 202 | BR-CUS-046..052: staged, value-mapping step (BR-CUS-052), aged-bucket opening balances → opening JEs (BR-CUS-048/049), 10k cap, per-row errors |

### 2.7 Meter Reads — metering (S26–S29 + S28 replacement)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S26 | Routes operational view | `GET /routes` (+ derived progress) | — | BR-MET-011 read-only; CRUD lives in Settings (§2.3) |
| S27 | Cycles operational view | `GET /cycles` (+ completeness per window) | — | BR-MET-057 completeness bar + chase list |
| S25 | Single manual read entry | `POST /reads` | — | BR-MET-054; channel model (BR-MET-059); VEE runs at commit (BR-MET-022) |
| S29 | Read detail drawer | `GET /reads/{id}` | — | BR-MET-056 full chain, math, flag reason WITH threshold values, supersession history |
| S29 | Supersede/override read | `POST /reads/{id}/supersede` | — | BR-MET-024/053 append-only correction; billed-read fix links J6 path |
| S29 | Dispute read | `POST /reads/{id}/dispute` | — | BR-MET-024 marker + reason |
| S28 (replaces stale `POST /reads/import`) | Staged import lifecycle | `POST /reads/imports` → `GET /reads/imports/{id}` (rows + rule results) → `POST /reads/imports/{id}/rows/{rowId}/resolve` → `POST /reads/imports/{id}/commit` → `DELETE /reads/imports/{id}` (discard staged) | 202 (upload + commit) | BR-MET-012..018: staged, severity dispositions, duplicate-vs-committed handling, compliance stamp, idempotency file+tags (🔒 OQ-044 mechanics) |

### 2.8 Billing (S30, S31.3 + run actions)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S30 | Bills list + detail | `GET /invoices` · `GET /invoices/{id}` | — | A11 already names "Bills" for pagination, row was missing; **no PUT/PATCH/DELETE exist** on issued invoices (HR-4, BR-BIL-004) |
| S30 | Bill document | `GET /invoices/{id}/document` | — | pinned template render (BR-BIL-026) |
| S30 | Void bill | `POST /invoices/{id}/void` | — | consequence message before confirm (BR-BIL-009); correction = new rows |
| S30 | Pending-billing queue chip | `GET /billing/pending` | — | BR-BIL-015 held accounts, aging, escalation |
| S30 | Delivery status per bill | `GET /invoices/{id}/deliveries` | — | BR-BIL-016 queue records per channel |
| S31.3 | Exception cases + per-case fix | `GET /billing/runs/{id}/exceptions` · `POST /billing/runs/{id}/exceptions/{caseId}/resolve` | — | BR-BIL-015 estimate/hold/bill-without-service; fix vocab per BR-MET-023 |
| S31 (draft powers) | Exclude / re-rate / add charge line | `POST /billing/runs/{id}/invoices/{invId}/exclude` · `POST /billing/runs/{id}/invoices/{invId}/re-rate` · `POST /billing/runs/{id}/invoices/{invId}/lines` | — | BR-BIL-023: computed amounts NEVER hand-editable; charge-code lines only (BR-BIL-019/020) |
| S31 | Issue drafts (all/subset) | `POST /billing/runs/{id}/issue` | 202 | BR-BIL-011 (one JE via posting service 🔒) + BR-BIL-016 delivery queue; **the bill already HAS its number** — BR-BIL-063 (PO 2026-08-11) allocates it when the draft is created, so issue mints nothing. Was "numbering in-txn (BR-BIL-022)", a timing BR-BIL-022 never stated |
| S30 | Corrections workflow (single + bulk) | `POST /billing/corrections` (draft w/ impact preview) · `POST /billing/corrections/{id}/approve` · `POST /billing/corrections/{id}/execute` | 202 (execute) | BR-BIL-014: NO money write before approval; staged idempotent execution; reason codes from reference data |
| S30 | Back-bill / ad-hoc / penalty | existing `POST /billing/runs` with `scope=account` + `bill_type` | 202 | BR-BIL-018/019/020 single-account mode of the same wizard; window cap + approval gates |

#### 2.8a Response BODIES for the two read endpoints — ENG-PROPOSED 2026-08-11

> **SERVED as of 2026-08-11.** `GET /invoices` and `GET /invoices/{id}` are
> implemented in `06-backend/apps/billing/api.py` and included by
> `06-backend/config/urls.py`, against the bodies below field for field
> (`06-backend/tests/test_us_bil_025_026_bills_read.py` asserts the exact key
> sets, and `06-backend/openapi/schema.json` carries both paths). The **paths**
> keep their PO adoption of 2026-08-09; these **bodies** are still ENG-PROPOSED
> and unratified — implementing them does not ratify them. Seven fields are
> served `null` under their contracted names because nothing in the database can
> answer them yet (`past_due`, `rollup.billed_this_cycle`/`billed_currency`,
> `document_url`, `deliveries`, `lines[].gl_account_code`,
> `lines[].tariff_version_label`, `rebill_of_invoice_id` /
> `corrected_by_invoice_id`), and one filter VALUE — `f.status=past_due` —
> refuses rather than guessing: **OQ-113** and **OQ-114** carry both to the PO.

The PATHS above are ratified; the bodies were not written anywhere, and the S30
screens had to be built against something. They were built against the shapes
below and the shapes are recorded HERE so the backend lane building
`apps/billing/api.py` reads them before naming fields — otherwise two lanes
pick two names for one column and the drift is discovered by a broken screen.
The machine-diffable copy lives in `07-frontend/src/api/endpoints.ts`
(`InvoiceRow` · `InvoicesPage` · `InvoiceLineRow` · `InvoiceDetail` ·
`InvoiceSummary`) with a field-by-field prose version, each field naming its
`apps/billing/models.py` column, in `07-frontend/src/features/billing/README.md`.

Status **ENG-PROPOSED, not ratified**: the paths carry the PO's 2026-08-09
adoption and these bodies do not. Four points a reviewer should look at rather
than take:

1. **`past_due` is SERVED, never derived on the client.** Whether a bill is
   past due depends on the unpaid balance (payments/ledger) and on today in the
   TENANT's timezone (BR-TEN-020/043); a browser has neither. It is a nullable
   boolean, and `null` renders as "unknown" with the reason instead of a
   confident "no".
2. ~~**A draft carries `invoice_no: null`**~~ **SUPERSEDED (BR-BIL-063, PO ruling
   2026-08-11 → the number is allocated when the DRAFT is created).** Verbatim:
   *"Give a running number always even for Draft; if not use thats okay we will
   lose it."* BR-BIL-022 is unchanged — it names the SOURCE and FORMAT of a
   number and was always silent on timing; "minted at issue" was an
   implementer's reading, recorded here and in `03-field-map.md`, and DEF-033 is
   reversed with it. **A draft therefore carries its number, and `GET /invoices`
   serves it.** The row's identity for linking is still the invoice **id** (a
   number can be lost when BR-BIL-023 replaces a draft), and B2's uniqueness
   constraint stays PARTIAL — now merely harmless rather than load-bearing, kept
   so two numberless rows could never collide if one ever occurred.
   *Stale copies still to be corrected by their owning lane (2026-08-11):*
   `07-frontend/src/api/endpoints.ts` (`InvoiceRow.invoice_no`'s doc comment)
   and `07-frontend/src/features/billing/README.md` (the `invoice_no` row of the
   `GET /invoices` table) both still say "null on a draft"; their FIXTURES were
   already updated, so only the prose is stale.
3. **The inside of `bill_payload` is deliberately NOT specified.** BR-BIL-030
   says what it must contain and BR-BIL-031 versions it, but no signed document
   names its JSON keys, and BR-BIL-026 puts the render on the SERVER anyway. So
   the detail exposes `has_payload` as a boolean and links
   `GET /invoices/{id}/document`; there is no payload parser on the client. Two
   lanes guessing one JSON schema is DEF-014 (the duplicated OpenAPI copy)
   wearing a different hat.
4. **`deliveries: null` ≠ `[]`.** Null means the delivery history was not
   served; empty means it was served and this bill has none. Collapsing them
   would tell a clerk a bill was never sent when nobody had looked.

#### 2.8b The S31 BILL-RUN routes — SERVED 2026-08-11, bodies ENG-PROPOSED

> Recorded here because the S31 wizard shipped on 2026-08-11 calling five
> `/billing/runs…` paths that no route served, and this is what four of them
> now answer. The **paths** carry the PO's adoption of 2026-08-09; these
> **bodies** are ENG-PROPOSED and unratified — implementing them does not
> ratify them. The machine-diffable copy is `06-backend/openapi/schema.json`
> and the typed copy is `07-frontend/src/api/endpoints.ts`; the exact key sets
> are asserted in `06-backend/tests/test_us_bil_001_003_run_api.py`, so a
> rename on either side is a red test rather than a blank panel.

| Route | Answers | Body |
|---|---|---|
| `POST /billing/runs` | **201** | `{id, job_id, status}`. `id` inline (11b §1 marks this row STALE against B12 r1's 202+job_id; that law is about ASYNC operations and this queues no work). `job_id` is **null** — served under its contracted name because there IS no job, never invented. `run_id` is deliberately NOT also served: `billRunIdOf()` reads `id ?? run_id`, and two names for one value is the drift DEF-014 is made of. Refusals: **409 BIZ-IDEMPOTENT** `br_ref: BR-BIL-005` with `params {run_id, ran_by, ran_at}` (who/when/link) · **404** for an unknown, malformed or cross-tenant cycle, one answer (HR-1) · **422** for a backwards period |
| `GET /billing/runs/{id}/findings` | **200** | `runs.PreparedRun` field for field: `{cycle_id, period_start, period_end, service_date, cycle_days, scope_services, account_count, ready[], blocked[], decisions[]}`. `ready[]` = the `contracts.AccountBillingData` members S31.2 renders (`account_id, account_no, behavior_class, currency, rate_plan_id, rate_plan_name, rate_plan_version, service_days, cycle_days, readings[]`); `readings[]` = `contracts.ServiceReading` (`service_code, service_id, consumption{amount,unit}\|null, estimated, absent_reason`). `blocked[]`/`decisions[]` = `runs.AccountProblem` **plus `stage`** (added to the dataclass this day — see below). NOT paginated, deliberately |
| `GET /billing/runs/{id}/exceptions` | **200** | `{rows[], counts, totals}`. A row is `{id, case, account_id, account_no, customer_name, service_code, detail, choices[], amount, currency, quantity, unit, chosen}`. `id` is the decision's NATURAL KEY — `case\|account_id\|service_id` — because a case row is computed, not stored, and that triple is what `current_decision` resolves on. `choices[]` is the SERVER's vocabulary (`decisions.CHOICES_BY_CASE`), never a client list |
| `POST /billing/runs/{id}/exceptions/{caseId}/resolve` | **201** | `{bulk_action_id, decision_ids[]}`. `case_ids` in the request body is BR-BIL-060's bulk: N rows sharing ONE server-minted `bulk_action_id`, each keeping its own `bill_run_decisions` row. `bulk_action_id` is null for a single decision |

**Five fields and one map are null/empty and each names its reason** — the same
posture §2.8a takes, and for the same rule (a value with no source is served
under its contracted name, never invented, never dropped):

1. `job_id: null` on the create — there is no job runner (TD-17), so no job was
   started. An id here would point at a `/jobs/{id}` poll answering nothing.
2. `amount` · `currency` · `quantity` · `unit`: **null on every case row**, and
   `totals: {}` on the envelope. `prepare_run` computes **no money at all** —
   the late-fee assessment, the guardrail average and the unallocated credits
   are US-BIL-002 surfaces nothing serves. `bulkSelectionSummary` renders the
   empty map as "the total is not served"; a zero would be a money claim.
3. `customer_name: null` on every case row. The only published customers read is
   `primary_contact_name(account)` and it takes an Account INSTANCE, which
   billing cannot build without importing another module's model (B1 / G6).
   **REPORTED**: a by-id read in `apps/customers/selectors.py` closes it. Null
   means "not read", never "no name".

**One refusal, stated so it is not discovered.** The findings pass answers
**422 BIZ-COMPLETENESS `br_ref: BR-BIL-024`** when the run's cycle carries no
`bill_date`. The run's SERVICE date — BR-RAT-007's pricing pivot — is the
cycle's bill date, because `apps/billing/issue.derive_due_date` already ruled
and ships that *"the only bill date in the schema is `cycles.bill_date`"*.
There is no clock in this path to fall back to (BR-TEN-043, gate G6) and the
period's end is not a bill date. ~~**The bill date the clerk types on S31 step 1
has no column and cannot reach the run at all — OQ-122.**~~
⚠ **SUPERSEDED 2026-08-11 (PO ruling, OQ-122 CLOSED option A → BR-BIL-070).**
Verbatim: *"A Store what they type and use it"*. `bill_runs.bill_date` exists
(migration 0011), `POST /billing/runs` stores what the wizard already POSTs, and
**the run's SERVICE date is that typed date** — the cycle's `bill_date` only
when nobody typed one, and a refusal (422 / BR-BIL-024) when neither is present.
Worked: cycle dated 1 Aug, clerk types 3 Aug, a tariff version effective 2 Aug —
the run prices against the 2-Aug version. Absent, `null` and `""` are one answer
on the create body ("nobody typed one"); a PRESENT value is parsed strictly and
a malformed one is 422 VAL-002 naming `bill_date`. ⚠ **The DUE-DATE half of the
ruling is NOT yet built:** `issue._due_terms_for` still reads `cycle__bill_date`,
so a typed run prices at the typed date and derives its due date from the cycle's
— named here rather than implied (hard-won law 1).

**`runs.AccountProblem` gained `stage`** (one of the seven BR-BIL-037 names, or
null when the finding is not a stage failure). BR-BIL-040 places a finding in
the tab that owns its stage's inputs, `runs.Break` had carried its stage since
it was written, and the screen was therefore keeping a SECOND copy of
`runs.STAGE_BY_REASON` to place the other half. The copy
(`FINDING_TAB_BY_REASON`, fourteen reason codes) is deleted; what remains in the
client is stage→tab, which is the only half that was ever the screen's.

~~**THE FIFTH ROUTE IS NOT SERVED, and not stubbed.** `POST /billing/runs/{id}/issue`
needs three inputs this API cannot honestly supply: the **template pin**
(BR-BIL-026 pins it at issue and `issue_invoice` refuses without it — BR-BIL-025's
assignment has no table, r10 #4), an **event time** (`issued_at` is the caller's
by BR-TEN-043 and there is no clock in a money path — G6), and an **authorised
release row** (whose `confirmed_at` is the same event-time problem one step
earlier).~~
⚠ **SUPERSEDED 2026-08-15 — BOTH ROUTES ARE SERVED (DEF-116).** The wizard sat
at *READY TO BILL 0* for four days on that paragraph, and every one of its three
clauses has since become answerable:

| Blocker as written | What answers it now |
|---|---|
| the **template pin** has no table | `bill_templates` / `bill_template_versions` landed 2026-08-15 and `templates_service.resolve_for` implements BR-BIL-025's own order (account override → category default → fallback). `_template_pin_for` asks for it; a tenant with no template is **refused with that rule's sentence**, never issued against an invented uuid — which is what the objection was really protecting |
| the **event time** is the caller's and there is no clock here | `issued_at` and `confirmed_at` are REQUIRED body fields, offset-bearing, and a naive timestamp is refused rather than assumed UTC. Not reading a clock (G6) and not having a time are different problems |
| the **authorised release row** does not exist | `POST /billing/runs/{id}/release` writes it, from the same five confirmations the S31 gate already collects |

**THE TWO ROUTES, AND WHY THEY ARE TWO.** Phase 4 RECORDS the authorisation and
issues nothing; phase 5 RELEASES against that record. A crash between them
leaves the authorised-but-unreleased run US-BIL-005 TC-13 requires a resume to
CONTINUE rather than re-authorise, and that state can only exist because the two
are separate events.

| Route | Story | Answers |
|---|---|---|
| `POST /billing/runs/{id}/release` | US-BIL-005 (phase 4) | **201** `{id, created:true, confirmations{5}, confirmed_by, confirmed_at, released_at:null, account_count, bill_count, total_amount, currency, summary, unavailable[]}` · **200 `created:false`** with the existing row when the run already holds an authorised-but-unreleased release (TC-13) · **422 BIZ-COMPLETENESS/BR-BIL-058** naming every untaken confirmation (TC-10) |
| `POST /billing/runs/{id}/issue` | US-BIL-005 (phase 5) | **201** `{created:true, bill_run_id, release_id, released_at, issued{…}, handoffs[], unavailable[]}` · **200 `created:false`** on a replayed Send · **422 BIZ-COMPLETENESS/BR-BIL-058** with no release row at all (TC-14) |

**THE 202 ROW ABOVE IS STALE AND THIS ANSWERS 201.** §2.8 contracts `202`
against BR-BIL-051's *"run the batches in background"*; there is no worker
(TD-17), the issue pass runs INLINE and the response is the FINISHED result. A
202 would promise an asynchrony nothing keeps. Served in the response's own
`unavailable` list rather than left to this paragraph.

**THREE THINGS THE ROUTES CANNOT DO, served on every response:** one template
pin for the whole run where BR-BIL-025 resolves per account (harmless while no
tenant holds more than one template, wrong the day one does); the stored summary
is the SERVER's own recomputation at confirm time rather than a payload the
screen echoed back, so nothing binds the signature to the figures the clerk read
a minute earlier; and the release is not a background batch.

Also unserved, each for a stated
reason rather than an oversight: the **break list** (`runs.CalculatedRun.breaks`
exists only in memory — nothing persists it, and computing it inside a GET
would write drafts), the **phase-4 summary as a GET** and the **release record
as a screen** (OQ-112 CLOSED: *"B An export only"* — the authorisation record
gets an export and deliberately no screen; the summary IS computed and stored by
the release WRITE, which the ruling never spoke about, and travels back in that
response because it is what the caller just authorised), and
`GET /billing/runs/{id}` (the BR-BIL-051 poll exists to watch a background
batch, and there is no background batch).

### 2.9 Payments (S32, S35, S58 + S34 bulk actions)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S32 | Payments summary KPIs | `GET /payments/summary` | — | "Today total" = posting, "Method mix MTD" = clearing — each KPI basis-labeled (BR-REP-010/001) |
| S32 | Autopay-scheduled panel | `GET /autopay/intents` | — | BR-PAY-015 capture-intent v1; fulfilled = computed (BR-PAY-034) |
| S35 | Record NSF | `POST /payments/{id}/nsf` | — | BR-PAY-013: reversing row, AR at ORIGINAL due date, NSF charge auto-added, nsf_count++ |
| S35 | Reverse payment | `POST /payments/{id}/reverse` | — | BR-PAY-011 windows → 409 BIZ-WINDOW; approval cross-period; consequence msg (BR-PAY-030) |
| S35 | Reapply/reallocate | `POST /payments/{id}/reallocate` | — | BR-PAY-031 reversing allocation rows + new rows, never edits |
| S58 | Record refund | `POST /refunds` | — | BR-PAY-014: real credit balance only, Admin approval, check/ACH v1 |
| S34 · S35 | Write-off (initiate → approve) | `POST /write-offs` · `POST /write-offs/{id}/approve` | — | BR-PAY-020 initiated in Payments, approved in Finance; direct method (BR-LED-008) |
| S35 | Re-send receipt | `POST /payments/{id}/receipt` | — | BR-PAY-024 via delivery queue |
| S34 | Bulk reminders/notices/plan/write-off | `POST /collections/notices` (bulk, by selection) | 202 | **BR-NOT-005**: written to outbound table, dispatcher paces — never synchronous mass send; tone→template tiers (BR-PAY-035) |
| S33 (bulk) | Lockbox/CSV payment import | `POST /payments/imports` → `GET /payments/imports/{id}` → `POST /payments/imports/{id}/commit` | 202 | BR-PAY-023 staged; file+SHA-256 stamp; heuristic matches flag for review, never auto-guess |
| S32 · S35 | Returned mail (single/bulk) | `POST /deliveries/returned` | — | BR-PAY-018 bad-address flag + paper suppression |

#### 2.9b What the payments API actually serves, and what it deliberately does not (2026-08-11)

Recorded here, in the contract, for the same reason §2.8b exists: the next agent
reads what WAS served rather than re-deriving it from the code.

**Served, both mounted in `config/urls.py` and proved reachable over real HTTP**
(`tests/test_us_pay_004_payments_api.py` resolves each path through the real
root URLconf AND makes an unauthenticated request asserting **401**, because a
404 is what both answered before this lane):

| Route | Story | Shape |
|---|---|---|
| `POST /accounts/{id}/payments` | US-PAY-001 | **201** on a new payment with the ALLOCATION INLINE — `applied`, `credit_carried` and one entry per bill the money met, plus `posted_to_ledger` / `journal_entry_id` and a `problems[]` list of what did NOT happen. **200 + `created:false`** on an idempotent replay |
| `GET /payments` | US-PAY-004 | the DRF page envelope + `totals` + `methods` |

**THE 409 DEVIATION, STATED WHERE IT IS ASKED.** §3 G7 makes a duplicate a 409
BIZ-IDEMPOTENT for the four operations it ENUMERATES — bill runs, read/payment
**imports**, webhooks, tenant provisioning. A staff double-click on the S22
Record button is none of them: BR-PAY-028's own field-map row reads *"duplicate
submit → single row"*, US-PAY-001 TC-6's expected outcome is "One row only", and
G7's own list already contains this exact shape (`POST /tenants` — *"repeat
returns existing tenant"*). So a replay is a RESULT, not an error: same body,
`created:false`, and a `duplicate_submit_ignored` problem code the screen shows.
A 409 toast for a button that worked is a wrong answer a clerk would act on.

**`idempotency_key` IS REQUIRED** and a missing one is 422 VAL-001 naming the
field. `record_payment` stores no key when the caller names none and a double
submit then records two payments; a key generated server-side would differ on
the second submit and dedupe nothing while looking as though it had.

**NOT SERVED, each with its blocker rather than an oversight.** None is stubbed
— a route that answers 501 is a promise:

* `POST /payments/{id}/nsf` · `/reverse` · `/reallocate` · `/receipt`,
  `POST /refunds`, `POST /write-offs`, `POST /collections/notices` (§2.9) —
  EP-PAY-03/04 and US-PAY-025. Several are additionally **blocked on PO
  decisions that have not been made**: OQ-132/133/134 (bounce), OQ-135
  (refund across accounts), OQ-136/137 (partial payment and a collection
  floor), all in `12-governance/12-payments-decision-batch.md`.
* `POST /payments/imports…` (US-PAY-003) — its posting-date semantics are
  **OQ-131, blocking**.
* `GET /payments/summary` · `GET /autopay/intents` (S32) — US-PAY-005 and
  US-PAY-024.
* **`GET /payments/{id}` — NOT MINTED.** No row of A11 or of §2.9 contracts a
  payment detail, and the one thing a detail would add over the list row — what
  the payment paid — is on the row as `applied_to`.
* **An account's OPEN BILL POSITION.** `specific` and `split` (BR-PAY-001) are
  executed by the allocator and accepted by the endpoint, and the S22 form
  cannot drive them because nothing serves what each open bill still OWES:
  `GET /invoices` serves the ISSUED total, which after a part payment is a
  different figure (PE-2: issued $247.87, still open $47.87). **OQ-154** —
  the two controls render disabled with that reason.

**Served null under their contracted names**, never dropped and never filled:
`receipt_no` (BR-PAY-024's queue is US-PAY-025's) and `deposit_batch_id`
(`deposit_batches` is EP-PAY-06's). `totals.amount` is null with
`totals.amount_unavailable` naming the case when the filter matched nothing,
when the rows span more than one currency, or when any signed credit/adjustment
row is present (B2's own O-4 residue leaves that sign open).

**One open question this lane raised at the boundary: OQ-153** — the S22 field
collects a calendar DAY and `payments.posted_at` is a timestamp; a bare date is
anchored at midnight UTC and which instant it should be, in whose timezone, is
unsettled.

### 2.10 Finance — payments · ledger (S36, S40, S43, S56, S57)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S36 | Revenue & AR read-model | `GET /finance/revenue-ar` | — | KPI strip + aging + **tie-out panel** (BR-LED-007/016); drift = red flag; all dimension-derived (BR-LED-001, BR-REP-002); basis labels |
| S38 (replaces stale `POST /finance/bank-imports`) | Staged bank statement import | `POST /finance/bank-imports` → `GET /finance/bank-imports/{id}` (match preview) → `POST /finance/bank-imports/{id}/commit` | 202 | BR-PAY-019/023; auto-match amount + CLEARING date ±3d |
| S40 | Reconcile exception line | `POST /finance/bank-imports/{id}/lines/{lineId}/reconcile` | — | reason + GL required — no force-match (BR-PAY-035); unreconcile = only reversal (BR-PAY-004) |
| S56 | Journal list + detail | `GET /ledger/journal-entries` · `GET /ledger/journal-entries/{id}` | — | BR-LED-012 full IS-5 row; lines expand to dimensions |
| S56 | Chart of accounts + GL mapping (+ export codes) | `GET /ledger/accounts` · `GET /ledger/gl-mappings` · `PUT /ledger/gl-mappings` | — | BR-LED-014; mapping edits never re-map history (BR-BIL-010 stamp-at-issue) |
| S56 | Trial balance | `GET /ledger/trial-balance` | — | BR-LED-009 period + premises filters, dimension expand, export |
| S57 | Manual JE (draft → post → reverse) | `POST /ledger/journal-entries` (draft) · `PATCH /ledger/journal-entries/{id}` (draft only) · `DELETE /ledger/journal-entries/{id}` (draft only) · `POST /ledger/journal-entries/{id}/post` · `POST /ledger/journal-entries/{id}/reverse` | — | BR-LED-003: posted = IMMUTABLE, edit = reverse+repost; unbalanced post → 422; accrual auto-reverse (BR-LED-005); posting service sole writer 🔒 |
| S36 · S71 | Month close / reopen | `POST /finance/periods/{period}/close` · `POST /finance/periods/{period}/reopen` | — | BR-LED-018 warn+confirm w/ checklist, close-anyway needs reason; reopen SysAdmin (BR-TEN-038/BR-LED-006) |
| S41 | Record remittance payment | `POST /finance/taxes/remittances` | — | BR-LED-002 JE drains authority liability; filing confirmation ref + receipt file (BR-LED-019) |
| S43 | QuickBooks sync modal | v1: **no live-sync endpoint** — file-export targets via §2.14 profiles + S42 batch download | — | BR-LED-020/BR-INT-010: direct connect = v2; minting a sync endpoint now would violate the matrix |

### 2.11 Reports (S45, S47 + exports)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S45 | Report schedules CRUD | `GET /reports/schedules` · `POST /reports/schedules` · `PATCH /reports/schedules/{id}` · `DELETE /reports/schedules/{id}` | — | BR-REP-017 v1 = PDF download, email W6; recipients INTERNAL-only v1 (BR-REP-020) |
| S45 | Run history + files | `GET /reports/history` · `GET /reports/history/{id}/file` | — | retention 3 days default, tenant-config (BR-REP-018) |
| S47 | Dataset catalog + saved custom reports | `GET /reports/datasets` · `POST /reports/custom` · `PATCH /reports/custom/{id}` · `DELETE /reports/custom/{id}` · `POST /reports/custom/{id}/run` | — | BR-REP-019 creator-private + share toggle; column-unratified reports use generic viewer (BR-REP-021) |
| S44/46/59/60 + every DataTable | Export (CSV/PDF) | `POST /reports/{key}/export` and table-level `POST /exports` | 202 | IS-9/IS-11 server-streamed under RLS; >50,000 rows → 422 BIZ-CAP (BR-SHL-016/029); money exports write audit_log |

### 2.12 Assets (S49–S55)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S49 | Assets list (3 type tabs) | `GET /assets` | — | tab partition by type (BR-AST-004); filters + search per capability row (BR-AST-041, BR-AST-005) |
| S50 | Asset detail (5 tabs) | `GET /assets/{id}` · `GET /assets/{id}/reads` · `GET /assets/{id}/assignments` · `GET /assets/{id}/maintenance` (+ audit via `GET /audit-log?f.entity=asset:{id}`) | — | BR-AST-016..019; billing chain in header (BR-AST-039); explicit units always |
| S51 | Add asset | `POST /assets` | — | 3-identifier model (BR-AST-026); dup serial warn / dup asset# hard 409 (BR-AST-033); assign-on-create (BR-AST-011) |
| S50 | Edit asset | `PATCH /assets/{id}` | — | billing-affecting fields forward-only once reads exist (BR-AST-012) |
| S50 | Delete (inventory-only) | `DELETE /assets/{id}` | — | BR-AST-013: inventory + never-referenced only, else 409 → retire pointer |
| S53 | Log repair/maintenance/test | `POST /assets/{id}/maintenance` | — | BR-AST-018 append-only; test updates last_test_date; lifecycle transitions per BR-AST-020 |
| S54 | Retire asset | `POST /assets/{id}/retire` | — | terminal, no un-retire (BR-AST-030/021); closes assignment |
| S55 | Reassign asset | `POST /assets/{id}/reassign` | — | BR-AST-022 final read captured; sub-meter move prompts (BR-AST-037) |
| S49 | Bulk assign inventory→units | `POST /assets/bulk-assign` | — | BR-AST-036 |
| S52 | Asset bulk import | `POST /assets/imports` → `GET /assets/imports/{id}` → `POST /assets/imports/{id}/commit` | 202 | BR-AST-023/034: staged, 10k cap, premises/units must exist, re-upload updates SPEC fields only |

### 2.13 Audit (S61) + outbound queue — audit · notifications

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S61 | Audit log list + drawer | `GET /audit-log` · `GET /audit-log/{id}` | — | BR-AUD-009 filter vocabulary; BR-AUD-013 hot-window 2yr default + explicit `archive` param, never unbounded; read-only — **no write verbs exist** (BR-AUD-002) |
| S61 | CSV export | `POST /audit-log/export` | 202 | BR-AUD-014: 50k cap, caller-RLS streamed, export itself writes an audit row |
| S8·Notifications · S30 | Outbound queue dashboard + re-queue | `GET /outbound` · `GET /outbound/summary` · `POST /outbound/{id}/requeue` | — | **BR-NOT-005** platform-wide queue; statuses queued→sent→delivered/failed/bounced; quiet hours (BR-NOT-009); dispatcher-only sending — no "send now" endpoint may exist |
| S8·Notifications | Read a message nothing can send | `GET /outbound/{id}/unsent` | — | ⊕ **BUILT 2026-09-05** (decision log of that date, `2.165.1`). Answers what is WAITING on a channel with **no provider connected for this tenant**, and answers `disclosable: false` with no content the moment one is — a gate that disarms itself rather than a flag somebody must remember to turn off (hard-won law 3). `AdminOrClerk`, not the list's `AnyTenantRole`: a portal one-time code is a credential. Every disclosure writes `audit_log` (`outbound_message.body_disclosed`) and the code itself is never in that row. ⚠ **NOT `GET /outbound/{id}/document`**, which serves the SEALED copy of a message that WAS sent and may never render (`BR-NOT-027`, CR-049 task 3) — two different facts, two routes, and merging them would put a re-render where a legal original belongs |

### 2.14 Templates & designers — notifications · billing (S67, S91–S106)

One resource family serves all 9 designer rows (17 screens) — matches the 13a TemplateDesigner promotion.

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S67 · S91–S96 · S97–S102 · S103–S106 | Template catalog + detail | `GET /templates?class=&type=` · `GET /templates/{id}` | — | classes: bill/statement/notice/receipt/email/sms/contract; variants per type × category × language (BR-NOT-001/006, BR-BIL-025) |
| same | Draft create/edit | `POST /templates` · `PATCH /templates/{id}` (draft versions only) | — | BR-BIL-027 Clerk drafts; effective-dated versions (BR-NOT-002) |
| same | Publish version | `POST /templates/{id}/publish` | — | SysAdmin only (BR-BIL-027); publishing affects future documents only (BR-BIL-026) |
| same | Delete version | `DELETE /templates/{id}/versions/{v}` | — | pinned-by-any-bill → 409 BIZ-LOCKED, never deletable (BR-BIL-026/027) |
| same | Test render / test print | `POST /templates/{id}/test-render` | — | returns rendered document; no customer send |
| S97–S106 | Send-test (email/SMS designers) | `POST /templates/{id}/send-test` | 202 | rides the outbound queue (BR-NOT-005); email activation W6, SMS v1.1 (BR-NOT-010/BR-INT-007) — gated keys refuse 409 BIZ-STATE until wave |

### 2.15 Integrations — beyond the addendum (feeds S8 Integrations tab, S38, S42/S43)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| S8·Integrations | Add v1-REAL keys | extend `{key}` set: `esp`, `print-vendor` | — | BR-INT-006 (ESP for 6k–10k volume) · BR-INT-017 (print vendor v1-REAL) |
| S8·Integrations | Gate later-wave keys | connect/test on `stripe·plaid·twilio·quickbooks·xero·itron·sensus·sso` → 409 BIZ-STATE | — | BR-INT-001 visible-but-later, disabled at UI AND API; refusal writes BR-AUD-018 attempt row |
| S8 · S38 | Bank/lockbox connection profiles (many per tenant) | `GET /integrations/bank-profiles` · `POST /integrations/bank-profiles` · `PATCH /integrations/bank-profiles/{id}` · `DELETE /integrations/bank-profiles/{id}` | — | BR-INT-009: label · format (BAI2/CSV/OFX/QBO/QFX) · CSV mapping · upload-or-SFTP; single-`{key}` connect shape doesn't fit — profiles are a collection |
| S8 · S42 · S43 | Accounting export targets | `GET /integrations/accounting-targets` · `POST /integrations/accounting-targets` · `PATCH /integrations/accounting-targets/{id}` · `DELETE /integrations/accounting-targets/{id}` | — | BR-INT-010 file targets (QBO-file/Xero-file/CSV/IIF) addressed by export codes (BR-LED-014); handover itself = ledger law |

### 2.16 Billing plan (subscription to Bynry) — tenancy · B10 (S107–S109) — W8-DEFERRED

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED — deferred W8) | Async? | Notes/rules |
|---|---|---|---|---|
| S107 | Plan + entitlement counters | `GET /subscription` | — | B10; trial from provisioning (BR-TEN-014); counters commercial-only, never enforced technically (BR-TEN-002) |
| S108 | Subscription invoices | `GET /subscription/invoices` · `GET /subscription/invoices/{id}/file` | — | as-at-issue plan/method rendering (immutability law) |
| S109 | Manage payment method | `PUT /subscription/payment-method` | — | card/ACH capture — needs rails; W8 per 13a/B10 |

### 2.17 Jobs — the shared async resource (required by every 202 above)

| Screen(s) | Operation needed | Proposed endpoint (PROPOSED) | Async? | Notes/rules |
|---|---|---|---|---|
| all wizards/imports/runs | Poll job status + progress | `GET /jobs/{id}` | — | B12 r1: "202 + job_id for EVERY async op … poll `/jobs/{id}`" — the resource itself was never added to A11; progress rows for wizards (B12 §1); terminal payload links the result resource |

**GAP coverage check (75 screens):** S1–S5 ✓ · S110–S113 ✓ (§2.1) · S48, S62 ✓ (§2.2) · S8 nine tabs, S63–S66, S69–S71 ✓ (§2.3) · S9–S13 ✓ (§2.4) · S14–S16 ✓ (§2.5) · S18–S20, S23, S24, S68 + S22 remainder ✓ (§2.6) · S26, S27, S29 ✓ (§2.7) · S30, S31.3 ✓ (§2.8) · S32, S35 ✓ + S58 (§2.9) · S36, S40, S43, S56, S57 ✓ (§2.10) · S45, S47 ✓ (§2.11) · S49–S55 ✓ (§2.12) · S61 ✓ (§2.13) · S67, S91–S106 ✓ (§2.14) · S107–S109 ✓ (§2.16). All 75 accounted; S2/S4/S5 close as "no endpoint" rows.

---

## 3. Cross-cutting contract gaps (what A11 lacks as a document)

A11 is a per-screen extraction table; the generated client needs a **contract preamble**. None of the following exists in A11 today — each is already ratified law elsewhere and must be stated once, document-level, in the regenerated A11:

| # | Gap | Governing law |
|---|---|---|
| G1 | **Error envelope** — `{code, message_key, params, field_errors[], br_ref, trace_id}`; codes ONLY from the B12 §3 catalog (AUTH/VAL/BIZ/SYS); no endpoint invents a code | B12 §3 |
| G2 | **Full HTTP-series table** — 200/201+Location/202/204 · 304 · 400/401/403/404/405/408/409/413/415/422/429+Retry-After · 500/502/503/504; "a response outside this table = a bug by definition" | B12 r1 §3-expanded |
| G3 | **202 async-job pattern** — every async op returns 202 + job_id; `GET /jobs/{id}` (§2.17) is the poll target; client retries idempotent GETs w/ backoff | B12 r1 |
| G4 | **Tenant scoping statement** — tenant from subdomain middleware, never client input; RLS FORCE; **cross-tenant resource = 404, never 403** (existence must not leak) | HR-1, BR-TEN-003, B12 r1 |
| G5 | **Pagination/filter/sort grammar** — `q/sort/dir/page/per/f.‹name›`, shareable, invalid values clamp; pagination mandatory on every list (checklist D) | BR-SHL-011, B12 §5-D |
| G6 | **ETag/304** on lookup/reference-data GETs (`/lookups/*`, `/roles`, `/settings/*` reads, `/public/pricing-plans`) | B12 r1 3xx row |
| G7 | **Idempotency-key conventions** — bill runs (tenant+cycle+period), read/payment imports (file+tags), webhooks (`webhook_key`), tenant provisioning (subdomain); duplicate → 409 BIZ-IDEMPOTENT with who/when/link; **key mechanics Eng-Lead 🔒** — A11 states the requirement, never the scheme | CLAUDE.md #6, BR-BIL-005, BR-MET-018, BR-PAY-028 |
| G8 | **Method ban on immutable resources** — no PUT/PATCH/DELETE routes exist for issued invoices/lines, payments out of processing, posted JEs, audit rows, committed reads; corrections are POSTs creating new rows → attempted edit = 409 BIZ-IMMUTABLE | HR-4, BR-BIL-004, BR-PAY-002, BR-LED-003, BR-AUD-002, BR-MET-053 |
| G9 | **Money serialization** — decimal-as-string NUMERIC(18,6) + CHAR(3) currency; server-rounded 2dp only at finalization/display; **basis label (posting/clearing) on every money figure returned** | CLAUDE.md #2, B4, BR-PAY-021, BR-REP-001, checklist D |
| G10 | **Consumption serialization** — explicit `unit` on every quantity; `channel` on every read | CLAUDE.md #3, BR-MET-059 |
| G11 | **Upload contract** — 413 size cap (10MB tenant-config), 415 outside allowlist (PDF/PNG/JPG/CSV) — ~~malware scan pre-acceptance~~ SUPERSEDED (PO 2026-09-22 / 2026-09-23 → no malware scan on upload), `DEF-SHL-6347`; import caps (10,000 rows; 3,000 pattern; 50,000 export) → 422 BIZ-CAP | NFR-34, BR-SHL-031/016, B12 r1 |
| G12 | **Rate limiting** — per-tenant API throttles, 429 + Retry-After (DRF throttling per TD-19); tighter on public endpoints (§2.1) | B12 r1, TD-19 |
| G13 | **AuthN/AuthZ statement** — server-side session (user, tenant-scoped per BR-IDN-029); RBAC server-enforced on every mutating call, UI gating is convenience; denials = 403 AUTH-002 (except cross-tenant → 404) | BR-IDN-001/006/029, BR-SHL-025 |
| G14 | **i18n contract** — server sends `message_key` + params (codes, never prose); UI renders language; document rendering picks account language variant | TD-16, BR-SHL-030, BR-CUS-064 |
| G15 | **Audit side-effects** — every money action writes audit_log; every REFUSAL writes a BR-AUD-018 attempt row; both are part of each endpoint's contract, not optional behavior | HR-7, BR-AUD-001/018 |
| G16 | **Queue-based delivery statement** — NO endpoint performs a synchronous customer send; anything that "sends" enqueues (BR-NOT-005) and returns the queue record(s) | BR-NOT-005, BR-BIL-016 |
| G17 | **OpenAPI generation clause** — drf-spectacular emits the schema; CI diffs it against audited A11 so contract drift is loud; A11-as-amended is the diff baseline | TD-19, G9 gate (B12 r2) |
| G18 | **Public vs authenticated surface split** — `/public/*` + `POST /tenants` + `POST /auth/session` are the only unauthenticated routes | derived; BR-TEN-011, BR-IDN-001 |

---

## 4. Audit summary

**Existing entries:** 22 audited → **16 OK · 6 STALE · 0 REMOVE**. The six stale: `POST /accounts/{id}/payments` (BR-PAY-021/012/033) · `POST /reads/import` (BR-MET-012/015 + 202 law) · `POST /billing/runs` (202 law + BR-BIL-005/015) · `POST /finance/bank-imports` (202 law + BR-PAY-019/023/035) · `POST /finance/exports` (BR-LED-020/017/004) · integrations key list (BR-INT-001/009/010/017).

**Missing (all PROPOSED), per §2 module tables:** public/onboarding 5 · shell 10 · settings ~40 · rating 15 · premises/units 15 · customers ~30 · reads 10 · billing 13 · payments 13 · finance 16 · reports 11 · assets 12 · audit+queue 6 · templates 6 · integrations 10 · subscription 4 (W8) · jobs 1 — **~120 proposed endpoints / operations** covering all 75 GAP screens (S2/S4/S5 close with "no endpoint").

**Ordered fix list for regenerating A11** (feeds the A11 addendum authored after PO review):

1. **Add the §3 contract preamble** (G1–G18) — without it every generated client type is wrong regardless of paths; the error envelope, 202/jobs, 404-not-403, pagination grammar and money/unit serialization rules gate everything else.
2. **Regenerate the 6 STALE entries** per §1 — payments payload (posting+clearing+purpose) and finance/exports (closed-period file batches) are the two that would produce financially wrong behavior, not just wrong shapes.
3. **Add the shared `GET /jobs/{id}` resource** (§2.17) and re-express every async row (runs, imports, issue, corrections, exports, bulk sends) as 202 + job.
4. **Adopt §2 module tables as the A11 additions**, PROPOSED → ratified via the normal PO batch; group order = build waves: Settings/lookups + identity (W0) → rating/premises/assets (W1) → customers/reads (W2) → billing (W3) → payments (W4) → finance/reports (W5); subscription screens stay deferred (W8).
5. **Re-tag screen references**: `POST /tenants` S6→S114; `GET /reports/{key}` add S59/S60; retire S4/S5 rows (mirrors the 13a A1 retag finding).
6. **Record the non-endpoints as law**: no 2FA endpoints (BR-IDN-028), no synchronous send endpoints (BR-NOT-005), no QBO/Xero live-sync endpoint (BR-LED-020), no write verbs on audit/issued/posted resources (HR-4) — the audit found these are as important to state as the endpoints themselves, or later agents will mint them.
7. **CI baseline swap** (TD-19/G9): once the addendum ratifies, the drf-spectacular diff target becomes A11-as-amended; until then, client generation stays blocked.

*Authored by the Eng-Lead's API auditor, 2026-08-09. No other file modified; A11 itself untouched. All §2 paths are PROPOSED — none are law until PO ratification.*
