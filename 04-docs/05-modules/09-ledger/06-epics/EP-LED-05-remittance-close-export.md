# EP-LED-05 — Tax remittance, month close, export to accounting (S41 · S42 · S43)

**Module:** ledger · **Wave:** W5 · **Screens:** S41, S42, S43, S36 · **Status:** draft (BR-LED-001..016 + BR-REP-001..018 all CONFIRMED; schema B2 Addendum r13)

## Scope
**In:** the **dual-basis remittance surface S41** (BR-LED-002/013: BOTH bases always computed — billed = tax on issued bills, collected = tax inside cleared payments via allocation; per-authority remitting-basis setting; 4 columns billed · collected · remitted · outstanding + basis indicator per BR-REP-003; remittance payment = JE draining the authority's liability) · the **month close** (BR-LED-006: Finance/Owner closes per fiscal settings; close checklist — runs issued, batches reconciled, bank rec current, accruals posted, remittance recorded; closed periods lock; late-dated events auto-post forward per BR-TEN-038; SysAdmin reopens) · the **S42 export to accounting** (BR-LED-004: one summary JE per period per GL account to QBO/Xero/CSV/IIF using the mapping-page export codes; batches recorded + IDEMPOTENT; drill-back from every figure; dimension-level CSV extracts) with the **S43 send modal**. J5 steps 3–4 contracts.
**Out:** tax RATES/config (rating S13/S41 config, BR-TEN-037) · tax computation on bills (billing US-BIL-008, B4.2) · fiscal-settings storage (US-TEN-006) · export codes CRUD (US-LED-006) · live ERP API connections/OAuth (integrations module seam — see pack report) · dispatcher email of files (W6, BR-NOT-005).
**Tables (B2 + r13):** `tax_remittances` (r13 #3), `export_batches` (r13 #4), `tenant_settings.lock_closed_periods` (r12 #15); reads journal dimensions, allocations.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S41 · By authority | authority | period, status (due soon/accruing/overdue/current) | due date asc | authority, rate, billed, collected, outstanding, due | Authority · Tax type · Rate · Taxable base · Billed · Collected · Remitted · Outstanding · Basis · Filing period · Due · Status / +Filed by, Confirmation (IS-5; dual-basis per BR-REP-003) | Download report · Record remittance/Mark filed · View detail | — | Remittance report PDF+CSV per authority (IS-11, A14) |
| S41 · Filing history | authority, confirmation | period | filed_at desc | filed, authority, amount | Filed · Authority · Period · Amount · Confirmation · Filed by (IS-5) | Receipt ↓ | — | CSV (IS-9) |
| S42 · Export history | period, destination | target (QBO/Xero/CSV/IIF), status | sent_at desc | sent, period, destination | Sent · Period · Destination · Entries · By · Status / +Hash (IS-5) | View batch · Drill back · Download file | — | files are the export |

## Stories

---
id: US-LED-014
epic: EP-LED-05
module: ledger
screens: [S41]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-002, US-BIL-008, US-PAY-006]
journeys: [J5]
rules: [BR-LED-002, BR-LED-013, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-014 — Dual-basis remittance (S41): billed vs collected per authority + the remittance payment JE

**1 · Details** — As Finance/Owner staff, I want S41 Taxes & Remittance rebuilt to the ratified dual-basis law (BR-LED-002; A1 addendum: "S41 = dual-basis remittance" — supersedes the prototype's collected-only table): per authority and period, **BOTH bases always computed** — **billed** = tax on issued bills (tax-liability journal lines by `tax_authority_id`, posting basis) and **collected** = tax inside cleared payments **via allocation** (clearing basis) — with **4 columns: billed · collected · remitted · outstanding** plus the **per-authority remitting-basis indicator** (the tenant setting picks which basis the authority remits on) per BR-LED-013/BR-REP-003; each column basis-labeled (BR-REP-001). **Recording the remittance payment = a JE draining the authority's liability** (DR tax payable authority / CR cash), written by the posting service 🔒 and recorded in `tax_remittances` (r13 #3: authority, period, basis, amount, paid JE ref); the filing-history table (prototype: Filed · Authority · Period · Amount · Confirmation · Filed by · Receipt) persists the trail. Outstanding feeds the S36 tax tie-out (BR-LED-007). Remittance report download per authority: PDF+CSV (A14, IS-11). Entry: Finance → Taxes & Remittance. Exit: report + recorded remittance; liability drains to zero.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-002 | BOTH bases always computed (billed = tax on issued bills; collected = tax inside cleared payments via allocation); per-authority setting picks the remitting basis; remittance payment = JE draining the authority's liability. **AMENDED 2026-08-12 (PO, OQ-189): the per-authority basis is STORABLE — _"E Remit on what you BILLED, not what you collected - this is also correct"_. Both bases are legitimate and the choice is the CUSTOMER'S to set; the setting's home is Settings → Configure (BR-LED-014), beside the payment-allocation-order setting ruled the same day.** | CONFIRMED — PO LF-2, 2026-08-08 (LE-3); storable basis CONFIRMED — PO 2026-08-12 |
| BR-LED-013 | Remittance report per authority: billed vs collected vs remitted vs outstanding. | CONFIRMED — PO LB-5, 2026-08-08 (LE-3) |
| BR-REP-003 *(consumed)* | S41 = dual-basis 4 columns + basis indicator. | CONFIRMED — reports audit F-1, 2026-08-08 |
| BR-LED-007 *(consumed)* | Tax payable GL = remittance outstanding (tie-out). | CONFIRMED — PO LF-7, 2026-08-08 |
| BR-LED-015 | Recording a remittance (money action) audits. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-3 July | Billed basis **47.38** (all three bills) vs collected basis **20.97** (only WE-1's payment cleared; its allocation covered its tax lines in full) — both shown side by side per authority with basis labels |
| TC-2 | Per-authority basis setting | State = collected → remit-now figure **13.87**; County = billed → its billed-basis figure; the indicator names each authority's basis (BR-LED-002) |
| TC-3 *(balance)* | Record State remittance | JE: DR 2200 State **13.87** / CR cash **13.87** — balanced, posting service 🔒; `tax_remittances` row (authority, period, basis=collected, amount, paid JE ref); outstanding drops by 13.87; audit row |
| TC-4 | Tie-out + report | S36 tax tie-out = Σ outstanding across authorities (BR-LED-007); "Download report" produces PDF+CSV per authority per IS-11 (bases labeled, params echoed) |
| TC-5 | Filing history | Row appends (Filed date · authority · period · amount · confirmation ref · filed by); append-only |
| TC-6 *(negative)* | Record remittance without authority/period/amount, or by a Staff role | Refused — required fields + Owner/Finance gate server-side |
| TC-7 *(negative)* | The same remittance recorded twice for the same authority+period+amount | Second attempt surfaces the existing `tax_remittances` row — no silent double-drain (idempotent recording per DB-12 pattern) |
| TC-8 *(isolation)* | Lone Star Ridge S41 | Its authorities/liability only (RLS; tax_jurisdictions tenant-scoped per r6.5) |

**4 · Test Data** — LE-3 verbatim: July billed 47.38 (WE-1 20.97 + WE-3 1.42 + WE-7B 24.99) vs collected 20.97; per-authority billed split: State 13.87 · County 2.22 · City 4.44 · PUC 0.44. Authorities: TX Comptroller (collected basis) · Travis County (billed) · City of Austin franchise (billed) · TX PUC (billed). Remittance: State 13.87 recorded Aug 18, 2026, confirmation "TXC-2026-08-9012" (prototype pattern), filed by Alex Reed. Actors: Norma Reyes, Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Billed column | S41 | BR-LED-002 | Σ tax-liability lines by `tax_authority_id`, issued bills, period (posting basis) | numeric(18,6) | computed-display | basis-labeled |
| Collected column | S41 | BR-LED-002 | tax inside cleared payments via `allocations` (clearing basis) | numeric(18,6) | computed-display | basis-labeled |
| Remitted / Outstanding | S41 | BR-LED-013 | Σ `tax_remittances` / (remitting-basis figure − remitted) | numeric(18,6) | computed-display | outstanding = tie-out feed |
| Remitting-basis setting | S41 | BR-LED-002 | per-authority basis setting (r13 #3 `basis` family; DDL 🔒) | enum billed\|collected | user-input | one per authority; audited |
| Remittance record | S41 | BR-LED-002 / r13 #3 | `tax_remittances` (authority, period, basis, amount, paid JE ref) | row | user-input → system-derived | JE via posting service 🔒 |
| Remittance JE | S56 | BR-LED-002 | DR authority tax payable / CR cash | numeric(18,6) | system-derived | balanced; source_type `remittance` |
| Filing history row (confirmation, filed by, receipt) | S41 | prototype-extracted | `tax_remittances` trail columns (exact DDL 🔒 r13 #8) | text/uuid | user-input | append-only |
| Report download | S41 | A14 + IS-11 | streamed PDF+CSV per authority | file | computed-display | dual-basis labeled; audited |

**6 · Acceptance**
- Given LE-3, Then both bases render side by side (47.38 vs 20.97) with per-authority indicators, never a single-basis view.
- Given a recorded remittance, Then the balanced JE drains the liability, the row lands in tax_remittances + filing history, and the S36 tie-out follows.
- Given missing fields, roles, replays or tenants, Then the server refuses / dedupes exactly.

**7 · Finance Calculation** — CONFIRMED (LE-3 verbatim): billed basis **47.38** = 20.97 + 1.42 + 24.99 vs collected basis **20.97** (WE-1's cleared payment covered its tax lines in full). State (collected) remit-now = **13.87**; JE: DR 2200 State **13.87** / CR cash **13.87** ✔ balanced; outstanding(State, collected) = 13.87 − 13.87 = **0.00** after recording.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-11 (ledger reporting lane, on building §1).** Three columns of four are built; the fourth cannot be computed and is reported rather than filled.

**WHAT WORKS, AND WHY IT NEEDS NO DIMENSION.** §5 maps the billed column to *"Σ tax-liability lines by `tax_authority_id`"*, and **`journal_lines.tax_authority_id` is NULL on every line in the product** — rating publishes no `tax_authority_id_for_tax` and `apps/billing/posting_seam.py` reports the gap on every bill. The split resolves anyway, because the **PO's ruling of 2026-08-11 (BR-BIL-069)** — *"For each atheority have separate account and tagging"* — plus B5 line 74 ❄️ (*"2200-series Tax payable per authority (tenant authorities mint their own)"*) make **the authority's own 2200-nn account its identity in the books**. `apps/ledger/reporting.remittance_by_authority` groups by account and reproduces LE-3 exactly: State **13.87** · County **2.22** · City **4.44** · PUC **0.44** = **20.97**, and July's total **47.38**. What the missing dimension costs is the authority's name AS RATING KNOWS IT; the label shown is the ledger account's own name, typed by the tenant when they minted it.

**WHAT DOES NOT — the COLLECTED basis, and it is a money ruling (OQ-174).** BR-LED-002's *"tax inside cleared payments via allocation"* is not derivable: an `allocations` row names a payment, an invoice and an AMOUNT and carries **no line class** (`apps/payments/models.py`, OQ-129), and the journal's payment entry credits AR in one lump with no tax dimension. LE-3's signed **20.97** works only because it is a FULL-COVERAGE case (*"its allocation covered its tax lines in full"*). On a PARTIAL payment the same bill's collected tax is **0.00** (tax last), **12.69** (pro-rata) or **20.97** (tax first) — a 20.97 spread on one bill, filed monthly with four authorities. The column returns `None` with the reason attached; **it never shows the billed figure**, which would remit tax on 26.41 of money nobody has paid.

**AND "CLEARED" IS NOT "REALISED" (PO ruling 2026-08-11, OQ-143).** *"until bank record and reconcilaition confirm it it is not realised"* — a collected-basis figure must count what reconciliation confirmed, not what a clerk keyed. `apps/ledger/reporting.cash_position` keeps **realised** and **undeposited** separate and never sums them.

**OTHER GAPS, each carried on the result:** the **per-authority remitting-basis SETTING** has no home — `tax_remittances` (r13 #3) is not in the schema at all — so `remitting_basis` is `None`, BOTH bases are offered, and the report carries the live problem code **`per_authority_remitting_basis_is_not_stored`**; ANY default would be wrong for one of LE-3's authorities in its first month. **RULED 2026-08-12 (PO, OQ-189) AND BUILT 2026-08-15:** _"E Remit on what you BILLED, not what you collected - this is also correct"_, said alongside the ruling that the payment-allocation SEQUENCE becomes a tenant setting. **Both bases are legitimate and which applies is the customer's to set, not ours to pick** — exactly what BR-LED-002 already said — so what was missing was STORAGE, not computation. The choice now lives on **S71 Finance controls, under Settings → Configure** (BR-LED-014, OQ-106/OQ-151 — the same screen and the same shape of work as the allocation-order setting) under the key `tax_remitting_basis_by_authority`, **keyed by the authority's own 2200-nn account code** (BR-BIL-069 makes the account the authority's identity in the books). **The problem code narrows rather than disappearing: it now NAMES the authorities the tenant has not yet chosen for and clears only when every authority on the report has a basis** — LE-3 has four and TC-2 rules on two, so a code that went quiet on the first save would hide City and PUC. Nothing defaults: State files on COLLECTED and County on BILLED in the same month. Pro-rata remittance is not offered and nobody asked for it; the reading where the books and the tax report disagree on purpose is now firmly REJECTED, because the collected basis is derived from the allocation the tenant configured and the two cannot diverge by construction. The **filing-history TABLE** and BR-LED-019's **receipt attachment** have no home either: `apps/ledger/journal.record_tax_remittance` REQUIRES the confirmation ref (it lands on the immutable entry memo and in the append-only audit row) and **REFUSES a receipt file by name**, because accepting one and dropping it is worse — the clerk who attached it believes it was kept. The **REMITTED column is read back out of the books** (Σ remittance-sourced debits per 2200-nn account), not out of a register, which stays the right order after the table lands. **AMENDED 2026-08-15 (DEF-112 lane, on building the SCREEN and the WRITE endpoint).** S41 is REACHABLE: `07-frontend/src/features/ledger/RemittancePage.tsx` renders the dual-basis table at **Finance → Taxes & Remittance**, and `POST /finance/taxes/remittances` (`apps/ledger/finance_api.record_remittance`) records the payment. **What the screen does with each of the gaps above, so the next lane does not re-decide it:** the COLLECTED column and the collected-basis OUTSTANDING render ABSENT WITH THEIR REASON on every row AND in the footer — never the billed figure, which would remit tax on money nobody has paid; `remitting_basis` renders absent per authority until the tenant sets it on Settings → Configure; the filing-history TABLE is a stated absence rather than an empty table, because `tax_remittances` does not exist; and the form REFUSES a receipt file by name and says so where the picker would have been. **The amount is TYPED, never pre-filled from the outstanding figure** — a pre-filled amount makes the payment agree with the report by construction, which is the property that hides a wrong report. **NOT BUILT:** the prototype's four KPI tiles, its "Coming up" banner and its Tax type / Rate / Taxable base / Filing period / Due / Status columns — every one needs a filing DUE DATE or a rating dimension the ledger read model does not publish. `POST /finance/taxes/remittances` takes `posted_at` as a required body input (BR-TEN-043); nothing in the API layer reads a clock.

Who may record a remittance was **OQ-175** (the product has `system_admin`/`billing_clerk`/`executive`; BR-LED-002 says Finance/Owner). **CLOSED 2026-08-12 (PO):** _"System Admin, Billing Clerk"_ — those two may REVERSE a posted entry and **Executive may not** (BR-LED-003). ⚠ **What was put to the PO was the REVERSAL, and a signature covers only what was shown:** the decision-log row records that this *"unblocks every §2.10 ledger WRITE"*, and recording a remittance is one — but the PO was not separately asked about the remittance record or the month close (BR-LED-006), so the same two roles are carried here **as the reading, flagged, and not treated as separately ratified**.

⚠ **AMENDED 2026-09-24 — THIS FLAG NAMED TWO CARRIES AND ONE OF THEM IS NOW RULED. THE OTHER IS NOT, AND IT STAYS FLAGGED.**

**THE MONTH CLOSE IS RULED.** PO ruling 2026-09-24, verbatim: *"system admin and clark"*, and on the second half, verbatim: *"yes correct - Reopening a month  System Admin only — signed as BR-LED-006, in the code, with a reason required and audited"*. So **close = `system_admin` + `billing_clerk`** and **reopen = `system_admin` only**, both signed law; `BR-LED-006` is AMENDED, not superseded. **No behaviour moved** — `apps/ledger/close.py` was already gated at exactly those roles. What moved is that it stopped describing its own gate as a guess: `close.ROLE_GATE_IS_A_READING` is **RETIRED**, `close_checklist` and `close_period` carry an EMPTY `unavailable`, and the sentence that reached a clerk on the month-close panel is GONE from the screen rather than reworded (B14 rule 33 — rationale at zero words on screen). It is pinned by `tests/test_us_led_015_month_close.py::test_us_led_015_br_led_006_ratified__who_closes_and_who_reopens`, proved red on every assertion and green on SQLite and PostgreSQL.

⚠ **THE REMITTANCE RECORD IS *NOT* RULED AND RETURNS TO THE AGENDA.** Nobody put *who may hand money to a tax authority* to the PO — OQ-175 was about reversing an entry and 2026-09-24 was about closing a month. `finance_api.record_remittance` stays `AdminOrClerk` **as the reading**, flagged in its own docstring, which no longer says *"same as the close"* because that pointer would now read as *ratified*. **Two more carries hang off the same OQ-175 reading and are equally unruled:** the **EXPORT handover** (`exports.create_export_batch`, BR-LED-017 — an executive may not hand the books to an ERP) and **posting a PERIOD-END ACCRUAL** (depreciation, unbilled revenue, unpaid supplier cost), which now carry `close.ACCRUAL_ROLE_GATE_IS_A_READING` — their own marker, minted precisely so that ratifying the close did not silently clear three flags standing beside it (DEF-CUS-3653's shape: an absence no check in this repo can see). `manual_je.ROLE_GATE_IS_A_READING` is a separate constant for S57 and is likewise untouched.

---
id: US-LED-015
epic: EP-LED-05
module: ledger
screens: [S42, S36]
wave: 5
status: draft
blocked_by: []
depends_on: [US-TEN-006, US-PAY-023, US-LED-012, US-LED-014]
journeys: [J5]
rules: [BR-LED-006, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-015 — Month close: checklist, period lock, late-event auto-forward, SysAdmin reopen

**1 · Details** — As Finance/Owner staff, I want to **close the month per the tenant fiscal settings** (BR-LED-006; settings = US-TEN-006/BR-TEN-022, incl. `lock_closed_periods` r12 #15): the close surface renders the **ratified checklist** — all bill runs issued · payment batches reconciled · bank rec current · accruals posted · remittance recorded — each item COMPUTED live from its register (bill_runs states, deposit_batches statuses, US-LED-012 pending reversals, US-LED-014 records), then the close action (IS-6: modal listing the computed checklist → explicit confirm → toast → audit). A **closed period locks**: money events dated into it **auto-post forward to the earliest open period with an audit note** (BR-TEN-038 — LE-9), nothing silently lands in a closed month; **reopen = System Admin only, audit-logged**. Close state feeds S42 (the model §7 sequence: checklist → close → export). Entry: Finance (period header/S42 area). Exit: J5 step-3 contract — *period closed; late-dated events auto-post forward w/ audit*.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-006 | Finance/Owner closes the month per fiscal settings; closed periods lock; late-dated events auto-post forward w/ audit (BR-TEN-038); SysAdmin reopens; close checklist (runs issued, batches reconciled, bank rec current, accruals posted, remittance recorded). | CONFIRMED — PO LF-6, 2026-08-08 (LE-9) |
| BR-TEN-038 *(consumed)* | Closed-period money events auto-post to earliest open period + audit; reopen = System Admin, audit-logged. | CONFIRMED — PO Q&A R6 (OQ-033 closed) |
| BR-TEN-022/023 *(consumed)* | Fiscal calendar computed from settings; lock toggle storage = tenancy. | CONFIRMED — PO R2-B5 / R6 |
| IS-6 *(consumed)* | Money action = modal → explicit confirm → toast → audit_log. | CONFIRMED — B9 |
| BR-LED-015 | Close/reopen write audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Checklist renders for July | Five computed items with live states: runs issued ✓ (bill_runs) · batches reconciled ✓ (US-PAY-023 lock states) · bank rec current ✓ · accruals posted ✓ (no pending US-LED-012 reversal due) · remittance recorded ✓ (US-LED-014) — each links to its surface |
| TC-2 | Close July (Aug 5) | IS-6 confirm modal echoes the checklist; on confirm: period locked, toast, audit `period.closed` (actor Norma Reyes, Finance) |
| TC-3 *(balance)* | LE-9: Aug 7 a payment arrives dated Jul 30 | Posts into **August** automatically with the audit note ("period closed; auto-forwarded"); the entry is balanced as ever; July books unchanged — nothing silently lands in a closed month |
| TC-4 | Reopen | System Admin only; confirm + reason; audit `period.reopened`; the period accepts postings again; Finance/Owner reopen attempt refused |
| TC-5 *(negative)* | A manual JE (US-LED-011) dated into closed July; a posting-service handoff dated Jul 30 | Both follow BR-TEN-038 — auto-forward + audit note; no rejection-with-data-loss, no closed-period write |
| TC-6 *(negative)* | Close attempted by Staff role | Refused server-side — Finance/Owner action (BR-LED-006) |
| TC-7 *(isolation)* | Lone Star Ridge closes ITS July | Brazos Bend's period state untouched; each tenant's close is its own (RLS) |

**4 · Test Data** — LE-9 verbatim: July 2026 closed Aug 5; Aug 7 payment dated Jul 30 → posts into August + audit note. Checklist fixture states from the LE-1 month (runs issued; DEP batches reconciled per US-PAY-020..023; JE-201 accrual posted; State remittance recorded Aug 18 → for the Aug close). Fiscal settings: monthly close, close-by day 5, lock_closed_periods ON. Actors: Norma Reyes (close), Alex Reed (Owner), Dana Fox (SysAdmin reopen). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Checklist items | S42 area | BR-LED-006 (+ prototype "Before you send" panel layout) | computed from bill_runs · deposit_batches · JE reversal schedule · tax_remittances · bank rec state | flags | computed-display | live register states, never checkboxes typed by hand |
| Close action | S42 area | BR-LED-006 | period close state (fiscal periods computed per BR-TEN-022; storage mechanics 🔒) | date/enum | user-input | Finance/Owner; IS-6 confirm |
| Period lock | — | BR-TEN-023/038 | posting-time enforcement: closed-period dates auto-forward | — | system-derived | audit note on every forward |
| Reopen | S42 area | BR-LED-006 | close state reversal | enum | user-input | System Admin only; reason; audited |
| Close banner | S36/S42 | BR-LED-006 | current-period card (computed, BR-TEN-022) | text | computed-display | shows closed-through month |
| Audit | — | CLAUDE.md #7 | `audit_log` `period.closed`/`period.reopened`/`journal.auto_forwarded` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given July complete, Then the checklist computes from real registers, close is a confirmed Finance/Owner action, and the period locks.
- Given LE-9's late payment, Then it forwards to August with the audit note and July stays byte-identical.
- Given reopen, Then only a System Admin can, with reason + audit; given tenants, close states never cross.

**7 · Finance Calculation** — CONFIRMED (LE-9 verbatim; no arithmetic — a dating rule): event dated **Jul 30** arriving **Aug 7** with July closed → posts in **August** (earliest open period) + audit note "period closed; auto-forwarded"; July trial balance (598.69 = 598.69) is unchanged after the event.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-15 (close-the-books lane, on BUILDING §1).** `apps/ledger/close.py` + `fiscal_period_closes` (`ledger/0007`) ship the backend half. **LE-9 is green and it is the assertion this story turns on:** July's trial balance is captured, July closes on Aug 5, a Jul 30-dated event resolves to **Aug 1** with the note *"period closed; auto-forwarded"*, and July's rows and totals are IDENTICAL before and after. §7 reproduces verbatim. Five residues:

- **THE TABLE IS AN EXTENSION BEYOND B2 §2, TAKEN UNDER A SIGNED DELEGATION.** `apps/ledger/posting.py` said it in 2026-08-11: *"there is no record of which periods are closed — no fiscal period table exists anywhere in the schema"*. B2 defines none and §5 of this module's field map delegates it — *"fiscal period close state (**storage mechanics 🔒**)"* — so `fiscal_period_closes` is authored under B2 r13 #8, the same delegation that produced `journal_entries.posting_key`, and is REPORTED as an extension rather than presented as signed schema. One row per period holds STATE; `audit_log` holds the history (`period.closed` / `period.reopened`), which is exactly where §5 puts it.
- **THREE OF THE FIVE CHECKLIST ITEMS CANNOT BE COMPUTED.** *accruals posted* and *remittance recorded* are the ledger's own and really compute (an accrual whose day-1 mirror is overdue; a remittance-sourced entry in the window). *runs issued*, *batches reconciled* and *bank rec current* live in billing and payments and **no module publishes a read** — each reports `unknown` with the callable it wants named, and an `unknown` item counts as INCOMPLETE. That is the fail-closed choice: a green tick nobody derived is hard-won law 1 in a checklist. The close still happens (BR-LED-018 forbids a lockout) and demands a reason.
- **BR-LED-018 IS BUILT AS WARN + CONFIRM, PROVED RED FIRST.** Without a reason an incomplete close is REFUSED naming every incomplete item; with one it closes and the items are SNAPSHOTTED beside the reason (J19 step 1's *"reason + incomplete-item snapshot recorded on the close"*), because recomputing them later would answer a different question. With the reason check removed, an incomplete July closed silently — that is what the guard was written against.
- **THE AUTO-FORWARD IS IN THE CALLER, NOT IN `posting.py`, AND ONLY ONE CALLER USES IT.** The posting service's contract is that *"the dates are INPUTS, both of them"* (PO 2026-08-11, OQ-107), so a service that silently moved the date it was handed would break every caller at once — including the cutover importer, whose entries are deliberately dated before every open period. Instead a caller asks `resolve_entry_date()` and posts what it is told, with the note visible at the call site and in the trail. **Today the only caller is the manual JE (US-LED-011): a late-dated BILL or PAYMENT still lands where it was dated**, because `apps/billing/**` and `apps/payments/**` are other lanes' in this session. REPORTED, not assumed done. ⚠ Two readings are FLAGGED rather than chosen: `tenant_settings.lock_closed_periods` is NOT consulted (a closed period locks unconditionally — the fail-closed reading of BR-LED-006's *"closed periods lock"*, since OQ-033's closure is worded only for the toggle-ON case), and a forwarded entry takes the earliest OPEN period's **START date** (LE-9 fixes the month and no day; the arrival date is unavailable without reading a clock, and two callers would otherwise forward the same event to two different days).
- ⚠ **THE ROLE GATE IS A RULING FOR BOTH HALVES SINCE 2026-09-24 — THIS LINE SAID "A READING FOR CLOSE" UNTIL THEN.** Close is `system_admin` + `billing_clerk` **by PO ruling of 2026-09-24** (verbatim *"system admin and clark"*), not by the OQ-175 reading it was carried on for six weeks; `close_role_gate_is_a_reading_not_a_ruling` is RETIRED and no result carries it. **Reopen IS separately ruled** (*"SysAdmin reopens"*, BR-LED-006 and BR-TEN-038 both), so a Billing Clerk who may close may not reopen, and TC-4 asserts it. ~~**NOT BUILT:** the S42 close surface, IS-6's modal→confirm→toast, and the close banner.~~ **BUILT 2026-08-15 (DEF-112 lane) — both halves.** `apps/ledger/finance_api.py` serves `GET /finance/close-checklist`, `GET /finance/periods`, `POST /finance/periods/close` and `POST /finance/periods/reopen`; `07-frontend/src/features/ledger/CloseExportPage.tsx` renders them at **Finance → Export to accounting**. **THE SHAPE, so the next lane does not re-decide it:**

- **The period is a WINDOW (`from` + `to`), not 11b §2.10's `POST /finance/periods/{p}/close`.** BR-TEN-022 computes periods and stores none, so there is no `{p}` to put in a path; `fiscal_period_closes` is keyed on (tenant, period_start, period_end) because the period IS its own identity. A surrogate id would be a second name for something tenancy already names, and the first tenant to change their fiscal year would hold ids pointing at months that no longer exist.
- **`closed_at` and `reopened_at` are REQUIRED body inputs (BR-TEN-043).** The close form collects the date. A server that read its own clock would stamp a different instant on a retry and record two histories of one act.
- **BR-LED-018's WARN is a 422 `BIZ-APPROVAL` naming every incomplete item in `params.incomplete`**, and the SAME request with a reason succeeds. It is not a lockout, and the screen says so before the button rather than after it.
- **The three `unknown` items render as a THIRD state**, neither tick nor cross, with the callable each wants NAMED on screen. An `unknown` still counts as incomplete, so the close still demands a reason.
- **An already-closed month answers 409 `BIZ-LOCKED`**; closing twice would overwrite the FIRST close's reason and incomplete-item snapshot, which is the record J19 step 1 asks for.

**STILL NOT BUILT:** the close BANNER on S36 (the `closed-through` card renders on S42 only), and no lane has wired `resolve_entry_date` into billing or payments — a late-dated BILL or PAYMENT still lands where it was dated.

---
id: US-LED-016
epic: EP-LED-05
module: ledger
screens: [S42, S43]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-006, US-LED-008, US-LED-015]
journeys: [J5]
rules: [BR-LED-004, BR-LED-014, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-016 — S42 export: one summary JE per period per GL, idempotent recorded batches, drill-back, dimension CSVs

**1 · Details** — As Finance/Owner staff, I want the **handover to accounting** (S42 + S43 send modal) per BR-LED-004: the period's **GL summary** (columns GL account · What it is · Debit · Credit, balanced totals — A14 §Accounting exports) rendered as **one summary JE per period per GL account**, exportable to **QuickBooks Online · CSV (generic) · IIF (QuickBooks Desktop) · Xero journal CSV** using the **export codes from the Finance mapping page** (US-LED-006, BR-LED-014); every export creates a **recorded batch** (r13 #4: period, target, who/when, content hash) that is **IDEMPOTENT — re-running a period is blocked with a link to the existing batch** (no double-handover); **every exported figure drills back to its dimensioned lines** on demand (auditor question → answer in seconds), and **dimension-level CSV extracts** (by service / premises / authority) are available for ERPs that want detail. The S43 modal: period select → balanced preview (entries count, total debits = credits) → send/download. Detail stays here — the ERP gets clean totals. QBO/Xero live API connections = integrations seam (pack report); v1 records the batch + produces the file/payload. Entry: S42 (J5 step 4, after US-LED-015 close). Exit: J5 contract — *one summary JE per month; QBO/CSV/IIF/Xero*.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-004 | One summary JE per period per GL account (QBO/Xero/CSV/IIF) using mapping-page export codes; batches recorded + IDEMPOTENT; every figure drills back to dimensioned lines; dimension-level CSV extracts available. | CONFIRMED — PO LF-4, 2026-08-08 (LE-5) |
| BR-LED-014 *(consumed)* | Export codes live on the GL mapping page (US-LED-006), and **that page lives with LEDGER SETTINGS, under Settings → Configure — not a ninth top-level tab** (PO 2026-08-12, OQ-106 _"Confirm they belong with ledger settings"_ + OQ-151 _"Confirm: under Configure"_). | CONFIRMED — PO LB-6, 2026-08-08; placement CONFIRMED — PO 2026-08-12 |
| BR-REP-005 *(consumed)* | S42 = recorded idempotent batches, Finance-page export codes, drill-back, dimension CSVs. | CONFIRMED — reports audit F-6, 2026-08-08 |
| BR-LED-015 | Every export (money handover) writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-5: export July to QuickBooks | One summary JE — **8 GL rows from LE-1's period deltas**, each carrying its qbo_ref (US-LED-006); payload debits = credits = **598.69**; batch **EXP-2607-QBO** recorded (who/when/hash); audit row |
| TC-2 *(negative — idempotency)* | Re-run July to QBO | **Blocked with a link to the existing batch** EXP-2607-QBO (LE-5) — no double-handover; a DIFFERENT target (e.g. CSV) for the same period is its own recorded batch |
| TC-3 | Drill-back | Auditor asks "what is the 506.31?" → the revenue figure opens to every dimensioned line behind it (service/account/premises/source) — LE-5 verbatim |
| TC-4 | Dimension CSV extracts | By service / by premises / by authority files per IS-11 CSV contract (snake_case, 2dp, ISO dates, context in filename), each summing to the exported figures |
| TC-5 | IIF / Xero / CSV shapes | IIF + generic CSV address accounts by code+name; Xero journal CSV uses xero_ref; missing target ref → blocked naming the account (US-LED-006 TC-5 pair); export history lists Sent · Period · Destination · Entries · By · Status per prototype |
| TC-6 *(negative)* | Export attempted with the period's tie-out drifting (US-LED-004 red flag) | The drift is a release blocker (BR-LED-007) — surfaced on the export screen; no clean-looking handover over broken books |
| TC-7 *(isolation)* | Lone Star Ridge export | Its batches/codes/entries only (RLS); its EXP- series independent |

**4 · Test Data** — LE-5 verbatim: July 2026 → QuickBooks Online; summary rows = LE-1 TB (1000 Cash DR 442.87 · 1200 AR DR 152.32 · deposit interest exp DR 3.50 · revenue CR 506.31 · tax CR 47.38 · 2300 CR 0.00 · 3000 CR 45.00; presented per GL account with qbo_refs from US-LED-006); batch EXP-2607-QBO, sent Aug 5, 2026 by Norma Reyes, content hash recorded. Re-run attempt Aug 6 → blocked. Drill-back target: 506.31. Extract files: `brazos-bend_gl_by_service_2026-07_posting_20260805.csv`. Actors: Norma Reyes, Alex Reed. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| GL summary table | S42 | A14 §Accounting exports | Σ journal lines per GL account for the period | numeric(18,6) | computed-display | balanced totals footer; basis labeled (BR-REP-001) |
| Target + period | S43 | prototype-extracted | export request (QBO\|Xero\|CSV\|IIF, r13 #4) | enum/dates | user-input | closed-period sequence per model §7 (checklist → close → export) |
| Balanced preview | S43 | prototype-extracted | computed (entries, Σ DR, Σ CR, balanced ✓) | numeric(18,6) | computed-display | must balance before send |
| Export batch | S42 history | BR-LED-004 / r13 #4 | `export_batches` (period, target, idempotency, who/when, content hash) | row | system-derived | UNIQUE per period+target (DB-12); re-run blocked w/ link |
| Export codes in payload | — | BR-LED-014 | `ledger_accounts.qbo_ref`/`xero_ref` (US-LED-006) | text | reference-data | required per target; missing → atomic block |
| Drill-back | S42 | BR-LED-004 | figure → dimensioned `journal_lines` behind it | rows | computed-display | every figure, always |
| Dimension CSV extracts | S42 | BR-LED-004 + IS-11 | streamed CSVs by service/premises/authority | file | computed-display | sums tie to export; audited |
| S43 prototype-only options | S43 | prototype-extracted — **no ratified rule** | "One per week" granularity · "Email the bookkeeper" · "Lock after sending" — NOT built v1 (see field-map discrepancies D-3/D-4/D-5; close = US-LED-015's explicit action) | — | — | excluded, not silently decided |
| Audit | — | CLAUDE.md #7 | `audit_log` `export.batch_created` (target, hash) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given LE-5, Then July hands over as one summary JE per GL account with export codes, recorded as EXP-2607-QBO, and a re-run is blocked with the link.
- Given any exported figure, Then drill-back lists its dimensioned lines; given detail-hungry ERPs, the dimension CSVs tie to the summary.
- Given a missing ref, a drifting tie-out, or another tenant, Then the export refuses cleanly.

**7 · Finance Calculation** — CONFIRMED (LE-5 + LE-1 verbatim): payload Σ DR = 442.87 + 152.32 + 3.50 = **598.69** = Σ CR = 506.31 + 47.38 + 0.00 + 45.00 ✔; batch **EXP-2607-QBO** (who/when/hash); re-run July → blocked; drill-back on **506.31** = 226.90 (WE-1) + 15.00 (WE-3) + 264.41 (WE-7B) listed line by line with dimensions.

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-15 (close-the-books lane, on BUILDING §1).** `apps/ledger/exports.py` + `export_batches` (`ledger/0007`, B2 r13 #4 with DB-12's signed UNIQUE(period, target)) ship the backend half. TC-2's re-run block, TC-3's drill-back, TC-4's extracts, TC-5's missing-ref block and TC-6's drift block are all green and each was proved RED first. Five residues:

- **NO FILE IS PRODUCED AND NOTHING IS SENT.** BR-LED-020 makes v1 *"FILE/batch export"* and DIRECT CONNECT v2; what this lane builds is the RECORDED BATCH and its stored payload, which is what BR-LED-004 makes the durable artifact and what a file is rendered FROM. The S43 send modal, the IS-11 streamed downloads and the W6 bookkeeper email are other lanes'. Stated rather than implied (hard-won law 2).
- **THE PAYLOAD IS STORED, WHICH IS WHAT MAKES TC-4 OF US-LED-006 TRUE.** J19 step 7 wants the file re-generated from the batch to be identical; US-LED-006 TC-4 changes 4100's QBO ref AFTER July's batch and requires the recorded batch unchanged. A batch that regenerated itself from the books would silently start saying the new ref. So the rows that went are kept exactly as they went and `content_hash` is a SHA-256 over their canonical JSON.
- **IDEMPOTENCY IS PER COVERED WINDOW, AND BOTH HALVES ARE REAL.** The service refuses an overlapping window for the same target and LINKS the existing batch (T5-07's recovery is *re-DOWNLOAD, never re-export*); `uq_export_batches_period_target` catches the race the SELECT cannot. **Proved:** with the service check removed, the DATABASE refused the second July export. T5-07 step 3 — the OTHER granularity over the same window — is refused too, which is why `granularity` is a column and not a key part, and why the closed-period gate asks `window_is_closed` (every period the window touches) rather than exact-period equality: a weekly slice of a closed July is inside a closed period, not an unclosed period of its own.
- **BR-LED-017's CLOSED-PERIOD GATE IS THE FIRST GATE, AND THE FOOTING IS CHECKED ON THE PERIOD.** T5-08 green: an open July refuses, closing it lets the same call through. A single WEEK can lawfully not balance (an entry dated Monday against one the following Tuesday) and the books cannot, so BR-LED-007's blocker is asserted on the period rather than per slice.
- **THE `EXP-` NUMBER CANNOT BE ALLOCATED — LE-5's `EXP-2607-QBO` IS NOT REPRODUCED BY DEFAULT.** `core/numbering.EXPORT_BATCH` exists and the allocation is wired (given the series row, a batch numbers itself `EXP-2607-0001`), but no tenant HAS the row: `apps.tenancy.services.SERIES_DEFAULTS` seeds five and BR-TEN-041's DEP-/RCT-/EXP- are *"deliberately absent … their owning lanes seed them"*. The batch records with `batch_no = None` and reports `export_batch_number_series_is_not_seeded`; its identity in the database is (period, target), so nothing depends on the printed number. A number is never composed here, for BR-TEN-035's reason. **AMENDED 2026-08-15 (DEF-112 lane): the S42/S43 SCREENS AND THE API HALF ARE BUILT.** `apps/ledger/finance_api.py` serves `GET /finance/export/preview`, `GET`+`POST /finance/export/batches`, `GET /finance/export/batches/{id}/drill-back` and `GET /finance/export/extracts/{kind}`; `CloseExportPage.tsx` renders the GL summary, the four gates, the IS-6 confirm dialog, the export history and the drill-back. **THE SHAPE:** each of the four refusals carries a DIFFERENT catalog code so a screen can act on them differently — 409 `BIZ-LOCKED` (period still open), 409 `BIZ-IDEMPOTENT` **with the existing batch on `params`** (T5-07's recovery is re-DOWNLOAD, never re-export), 500 `SYS-DRIFT` (the books do not foot — a 500 on purpose, because unbalanced books mean a posting-service bypass and not a field a clerk can fix) and 422 `BIZ-COMPLETENESS` (an account has no export code, named). **`sendable` is the SERVER's answer and the button renders it; the screen never re-derives it from the four flags beside it.** `created_at` is a REQUIRED body input (BR-TEN-043) so a retried send stamps ONE moment. **Still NOT built:** the IIF/Xero/CSV FILE SHAPES (only the row set and its refs), and the by-premises dimension extract returns `available=False` — `journal_lines.premises_id` is NULL on every line in the product (US-LED-002 unbuilt) and `reporting.by_premises_summary` already names the figure it cannot attribute.
