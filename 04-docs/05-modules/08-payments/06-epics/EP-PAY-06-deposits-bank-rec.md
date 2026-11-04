# EP-PAY-06 — Deposit batches & bank reconciliation (S37 · S38 wizard · S39 detail · S40 modal)

**Module:** payments · **Wave:** W5 · **Screens:** S37, S38, S39, S40 · **Status:** draft (BR-PAY-001..031 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r12)

## Scope
**In:** the money-landed pipeline (model §7, PE-10/11; J5 step-1 contract: *batches matched/resolved, locked*): **deposit batches grouped day × method with tenant DEP- numbering** (BR-PAY-025, r12 #13), the **bank-statement import wizard S38** with auto-match on **amount + date ±3 days (finance setting)** (BR-PAY-019, r12 #10), the **S40 reconcile modal** (every exception explained with reason + GL; PE-11 −5.00), and the **S39 batch detail** with the reconciliation trail and the **reconciled lock / Unreconcile-only reversal** (BR-PAY-004). Bank rec lives in the **FINANCE area, Owner/Finance roles** (BR-PAY-019, S37–S40 per A1). Bank rec matches on the CLEARING side (BR-PAY-021). Batches group money; they post nothing (model §12 — rec differences post per reason via the posting service 🔒).
**Out:** NSF execution (US-PAY-009 — S40 triggers it) · direct bank feeds/Plaid connect (prototype S38 step-1 right card — integrations seam, no ratified rule v1; pack report) · QBO deposit posting (integrations) · month-end close/trial balance (ledger/tenancy, J5 steps 2–4).
**Tables (B2 + r12):** `deposit_batches`, `bank_lines`, bank statement imports + match-rule config (r12 #10), DEP- number series (r12 #13).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S37 · Deposits & Bank tab | batch #, date | status (in_transit/unmatched/matched/reconciled), method | deposited_on desc | date, batch, method, our total, difference | Date · Batch · Method · Payments · Our total · Bank shows · Difference · Status / +Reconciled by, Statement line, Bank account (IS-5) | View batch (→ S39) · Resolve (→ S40, unmatched only) | Import bank statement (→ S38) | CSV (IS-9, "Deposit slip for bookkeeper") |

*(S38 is a wizard, S39 a detail page, S40 a modal — wizard/detail tables follow IS-2/3/5 embedded.)*

## Stories

---
id: US-PAY-020
epic: EP-PAY-06
module: payments
screens: [S37]
wave: 5
status: draft
blocked_by: []
depends_on: [US-PAY-001, US-PAY-003]
journeys: [J5]
rules: [BR-PAY-025, BR-PAY-021, BR-PAY-004]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-020 — Deposit batches: day × method, DEP- numbering, S37 list

**1 · Details** — As Finance staff (Owner/Finance roles — BR-PAY-019 area), I want each day's receipts grouped into **deposit batches by day × method** (BR-PAY-025, PE-10), numbered from the tenant DEP- series (r12 #13, e.g. `DEP-260808-CHK`), carrying `recorded_total` = Σ member payments, listed on S37 with the KPI strip (Deposited this month / Matched to bank / Unmatched / In transit) and status per B2 `batch_status` (**in_transit → unmatched | matched → reconciled**). ⚠ **CORRECTED 2026-08-11 (DEF-065).** This sentence read *"Batch membership groups on the **clearing side** (BR-PAY-021 — bank rec and money-landed facts hang off cleared_at; the deposit day is the day the money goes to the bank)"* and it was STALE — written before the PO's ruling RQ-5. **Batch membership groups on the POSTING day — the physical drawer day** (BR-PAY-025: *"day = POSTING date per RQ-5/BR-REP-013"*; BR-REP-013: *"Deposit batch 'day' = POSTING date (physical drawer day); bank clears later"*; journey J14 step 4 says the same). BR-PAY-021 still governs the BANK side — the statement's own posting date is what the match compares against — and the ±3-day tolerance is exactly what absorbs the gap between the drawer day and the bank day (J14: money taken 8 Aug, statement 11 Aug). Batches group money and post nothing (model §12). Totals lock at reconciliation (BR-PAY-004 — US-PAY-023 owns the lock). Entry: automatic grouping as payments clear (+ manual day-close review). Exit: batches on S37 feeding the S38 match.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-025 | Deposit batches group day × method, numbered from tenant series (DEP-…). ⚠ **SUPERSEDED-IN-PART 2026-09-22 (`CR-135-BRC07` `P0.6`, `2.330.0`): a batch is one TILL × one TENDER**, keyed `UNIQUE (tenant, session, method) WHERE session_id IS NOT NULL`. Dana's `$1,240` of cheques and Sam's `$880` were one row for the whole utility and are now two; the day still ties to `$2,120`. **And the code is ALLOCATED from Settings → Numbering** (`DEP-260922-0001`) rather than composed — only the METHOD token left it; the year and the date of the 2026-08-12 ruling are both still there. Nothing is written to a batch already banked: a batch with no session is one banked the old way. | CONFIRMED — PO Lane B-4, 2026-08-08 (PE-10) · **SUPERSEDED-IN-PART — PO 2026-09-22** (`OQ-PAY-12575/12576/12577`) |
| BR-PAY-021 | Batch/bank-rec facts hang off the clearing date. | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-PAY-004 | Reconciled batches lock (executed in US-PAY-023). | CONFIRMED — A5 §Batch |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-10: Aug 8 receipts — checks 292.87 + 142.30 + 36.22, cash 105.36 + 16.42 | Two batches: **DEP-260808-CHK** recorded_total **471.39** (3 payments) · **DEP-260808-CSH** recorded_total **121.78** (2 payments); each payment row carries its `deposit_batch_id`; S33 batch column shows it |
| TC-2 | S37 list + KPI strip | Batches sorted deposited_on desc; KPI tiles (deposited MTD / matched / unmatched / in transit) tie to batch rows exactly; status filter segments work |
| TC-3 *(posting vs clearing)* | A check posted Aug 8, cleared Aug 9 | It joins the **Aug 8** check batch — grouping is by the POSTING day, the physical drawer day (BR-PAY-025 / BR-REP-013, PO ruling RQ-5). ⚠ **CORRECTED 2026-08-11 (DEF-065)**: this cell read *"It joins the **Aug 9** check batch — grouping is by clearing day (BR-PAY-021), not posting day"*, which contradicted the ruling and the rule that carries it. Asserted by `test_us_pay_020_tc3__the_batch_day_is_the_posting_day_not_the_clearing_day` |
| TC-4 | ACH day batch | Status in_transit while settling (prototype "pending" bank column); moves to unmatched/matched on statement import (US-PAY-021) |
| TC-5 *(negative)* | Attempt to hand-edit a batch total or move a payment between batches by editing rows | Rejected — totals are Σ members (system-derived); membership corrections are audited regroup events, not edits; reconciled batches fully locked (US-PAY-023) |
| TC-6 *(isolation)* | Lone Star Ridge batches | Its own DEP- series and rows only (RLS); Brazos Bend batch codes can repeat there without collision (per-tenant UNIQUE) |

**4 · Test Data** — PE-10's MONEY verbatim (❄️ frozen and unmoved): Aug 8, 2026 — checks 292.87 (ACC-1042 PE-1) + 142.30 (ACC-1103) + 36.22 (ACC-1310 installment) = **471.39**; cash 105.36 (ACC-1077) + 16.42 = **121.78**. **The CODES those two totals hang on are re-rendered**, because the PO ruled the year in on 2026-08-12 (OQ-162) and this §4 series format was superseded by it: **`DEP-260808-CHK`** and **`DEP-260808-CSH`**. Series `DEP-{YY}{MM}{DD}-{METHOD}` (tenant-adjustable, r12 #13) — ~~`DEP-{MMDD}-{METHOD}`~~ SUPERSEDED (PO 2026-08-12 → BR-PAY-025). PE-10's own text in `07-pre-session-model.md` §7 keeps the pre-ruling rendering, stamped: it is the record of what was signed, not a description of what the system does. Actors: Norma Reyes (Finance). Isolation: Lone Star Ridge DEP-260808-CHK (own series).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Batch row | S37 | prototype-extracted (table) | `deposit_batches` (code, method, deposited_on, recorded_total, status) | row | system-derived | day × method grouping (BR-PAY-025) |
| Batch code | S37/S39 | BR-PAY-025 + r12 #13 · **PO 2026-08-12 (OQ-162)** | `deposit_batches.code` from tenant DEP- series (UNIQUE per tenant) — **must be YEAR-BEARING** (*"Add the year"*); the year-less `DEP-{MMDD}-{METHOD}` default collides with itself twelve months on (DEF-066) | text | system-derived | tenant-adjustable format; **year token required** |
| Banking date | S37/S39 | **PO 2026-08-12 (OQ-162)** — *"Date is important"* | `deposit_batches.deposited_on` — a **first-class field in its own right**, never decoded out of the code (*a code is a label, never a data store*) | date | system-derived (from the posting day, BR-PAY-025) | always present and displayed independently of the code |
| Membership | S39/S33 | model §7 | `payments.deposit_batch_id` (WRITE-ONCE — payments 0005) | uuid | system-derived | CLEARED payments by **posted_at day** + method (BR-PAY-025 / RQ-5 — corrected 2026-08-11, DEF-065). Positive `payment`-type rows only: a reversal is not a deposit |
| Recorded total | S37/S39 | B2 DDL | `deposit_batches.recorded_total` = Σ member `payments.amount` | numeric(18,6) USD | system-derived | never hand-edited |
| Bank shows / difference | S37 | prototype-extracted | `deposit_batches.bank_total` (from US-PAY-021) + computed difference | numeric(18,6) | system-derived / computed-display | difference = bank − recorded |
| Status | S37 | B2 `batch_status` | in_transit\|unmatched\|matched\|reconciled | enum | system-derived | reconciled = locked (BR-PAY-004) |
| KPI strip | S37 | prototype-extracted | computed over batches (month) | $/counts | computed-display | ties to rows |
| Deposit-slip export | S37 | prototype-extracted + IS-9 | computed file over batches | file | computed-display | bookkeeper handoff |
| Audit | — | CLAUDE.md #7 | `audit_log` `deposit_batch.created/regrouped` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the PE-10 day, Then exactly the two batches exist with 471.39/121.78 recorded totals and correct membership, numbered from the tenant series.
- Given drawer-day grouping, Then a payment joins the batch of its **posted_at** day, not its cleared_at day (BR-PAY-025 / RQ-5 — corrected 2026-08-11, DEF-065).
- Given the list, Then KPIs, filters and export tie to the rows; given tenants, series and rows never cross.

**7 · Finance Calculation** — CONFIRMED (PE-10, model §7 verbatim). Checks 292.87 + 142.30 + 36.22 = **471.39** (DEP-260808-CHK) · cash 105.36 + 16.42 = **121.78** (DEP-260808-CSH). recorded_total = Σ member payments — an assertion, not a rounding event (members are finalized 2dp amounts).

**8 · Open Questions** — **OQ-162 — CLOSED 2026-08-12.** The PO ruled *"Add the year + Date is important"*: **the batch code becomes YEAR-BEARING**, and — the more important half — **the banking DATE is a first-class field on the batch in its own right**, not something a person decodes out of a code (*a code is a label, never a data store*). **This §4 series format is therefore SUPERSEDED**: the old `DEP-0805-CHK` rendered for 5 August this year and identically for 5 August next year — the same code twice in one utility's history against a UNIQUE-per-tenant constraint, which makes a bank query ambiguous forever (DEF-066). **SHIPPED 2026-08-15**: the default is `DEP-{YY}{MM}{DD}-{METHOD}`, so that day reads `DEP-260805-CHK` in 2026 and `DEP-270805-CHK` in 2027, and every worked code in this epic is re-rendered accordingly. **The money is untouched** — PE-10's 471.39 and 121.78 are ❄️ frozen and a label change cannot move them. ORIGINALLY (raised 2026-08-11, built to the boundary): the `DEP-{MMDD}-{METHOD}` default carried no YEAR, so `DEP-0808-CHK` rendered identically in 2026 and 2027 while B2 §2 makes the code UNIQUE per tenant — the second year was REFUSED by name. The same row records that the code cannot be minted from `number_series` at all: BR-TEN-035's grammar has no method token and requires a sequence token, and a batch code is not a counter. ⚠ **THAT HALF IS CLOSED AS OF 2026-09-22 AND IT CLOSED BY THE PREMISE GOING AWAY.** PO ruling of that date, verbatim: *"(b) Put it in Settings today — DEP-260922-0001 — Settings → Numbering, like every other number"*. The grammar objection was entirely correct **about a code containing the TENDER**, and the tender has left the code — it lives in the `method` column it always had. A batch code IS a counter now, because the re-key made two batches possible on one day in one tender. The `deposit_batch` series already existed on every seeded tenant and was simply ignored; `apps/payments/reconciliation._allocate_batch_code` allocates from it, and `batch_code` and `method_token` are deleted. **Nothing is owed here any more.**

---
id: US-PAY-021
epic: EP-PAY-06
module: payments
screens: [S38, S37]
wave: 5
status: draft
blocked_by: []
depends_on: [US-PAY-020]
journeys: [J5]
rules: [BR-PAY-019, BR-PAY-021, BR-PAY-004]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-021 — S38 bank import wizard: upload → auto-match (amount + date ±3d) → confirm & reconcile

**1 · Details** — As Finance/Owner staff, I want the three-step S38 wizard (BR-PAY-019 — bank rec lives in the FINANCE area): **1 Upload statement** (CSV/OFX/QBO/QFX per prototype; bank account + statement period; the "connect the bank" Plaid card = integrations seam, out of v1 — pack report), **2 Review the matches** — every bank line auto-matched to a deposit batch on **amount + date ±3 days (the tolerance is a finance setting, default ±3, r12 #10)** with the match table (Bank posting · Bank reference · Bank amount · Matched deposit · Our amount · Diff · Match state Auto/off-by) and KPI tiles (Bank lines / Matched / Need a look / Not in our system), exceptions routing to the S40 reconcile modal (US-PAY-022) — **3 Confirm & reconcile**: matched batches → **reconciled + locked** (BR-PAY-004, executed via US-PAY-023's lock), reconciled-by recorded for the trail, still-flagged batches stay open and are resolved separately. Match dates compare bank posting date ↔ batch deposited_on (clearing side, BR-PAY-021). `bank_lines` rows persist the statement; import is idempotent per statement file (BR-PAY-028 family). Entry: S37 "Import bank statement & reconcile". Exit: matched batches reconciled; exceptions flagged; toast "reconciled · N matched · N flagged".

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-019 | Bank reconciliation lives in FINANCE (S37–S40, Owner/Finance roles): statement import, auto-match amount + date ±3 days (finance setting), exceptions → reconcile modal with reason + GL. | CONFIRMED — PO PA-8 "okay but in finance", 2026-08-08 (r12 #10) |
| BR-PAY-021 | Matching runs on the clearing side (bank posting ↔ deposit day). | CONFIRMED — PO explicit ruling, 2026-08-08 |
| BR-PAY-004 | Confirm marks matched batches reconciled → locked; Unreconcile is the only reversal (US-PAY-023). | CONFIRMED — A5 §Batch |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Upload Chase statement Aug 1–6 (31 lines, prototype) | `bank_lines` written; step 2 KPIs: 31 lines / 28 matched / 3 need a look / 0 not in system; exact-amount+date rows matched Auto |
| TC-2 *(date tolerance)* | Bank line Aug 6 for a batch deposited Aug 4 (card settled 2 days late), amounts equal | Auto-matched — within ±3 days (BR-PAY-019); variant: 4-day gap → NOT auto-matched, listed for review; finance tolerance changed to ±1 → the 2-day case now needs review (setting, not constant) |
| TC-3 | Amount mismatch (DEP-260805-CHK: bank 2,740.00 vs ours 2,840.00) | Row flagged "Off by $100" → Resolve opens S40 (US-PAY-022); never auto-forced |
| TC-4 | Step 3 confirm | 28 matched batches → reconciled + locked; reconciled-by "Norma Reyes · Aug 6, 2026 10:14"-style trail on S39; 3 flagged stay open; audit `bank_rec.confirmed` |
| TC-5 *(negative)* | Same statement file re-imported | Blocked (file idempotency, BR-PAY-028 family) — who/when/link shown; no duplicate bank_lines |
| TC-6 *(negative)* | Malformed/oversized file; or a Staff-role user opens S38 | File rejected with parse errors; S38 is Owner/Finance-only (BR-PAY-019) — Staff blocked server-side |
| TC-7 *(isolation)* | Lone Star Ridge import | Matches only its batches; Brazos Bend bank lines/batches invisible (RLS) |

**4 · Test Data** — Prototype statement: Chase Operating ••4021, Aug 1–6, 2026, 31 lines $298,410; matched 28 ($291,240); flagged 3 ($7,170): DEP-260805-CHK −100.00 · DEP-260804-CARD −147.50 · DEP-260802-CASH −80.00. Tolerance setting: ±3 days default; variants ±1. Bank references: "ACH CREDIT BATCH 88213", "CHECK DEPOSIT 4410". Actors: Norma Reyes (Finance), Alex Reed (Owner). Isolation: J. Okafor (Lone Star Ridge Finance).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Statement file + period + bank account | S38 step 1 | prototype-extracted (CSV/OFX/QBO/QFX) | bank statement import record (r12 #10; file + idempotency per BR-PAY-028 family) | file/dates | user-input | supported formats; Owner/Finance only |
| Bank line | S38 step 2 | B2 DDL | `bank_lines` (posted_on, reference, amount, deposit_batch_id when matched) | numeric(18,6)/text | integration | one row per statement line |
| Auto-match rule | — | BR-PAY-019 | match on amount equal + |posted_on − deposited_on| ≤ tolerance (match-rule config, r12 #10) | rule | system-derived | tolerance = finance setting, default ±3d |
| Match state + diff | S38 step 2 | prototype-extracted | computed per row (Auto / off-by / unmatched); diff = bank − recorded | enum/numeric | computed-display | exceptions → S40 |
| KPI tiles | S38 step 2 | prototype-extracted | computed over lines | counts/$ | computed-display | tie to rows |
| Confirm & reconcile | S38 step 3 | BR-PAY-019 + BR-PAY-004 | `deposit_batches.status` → reconciled (+ lock, US-PAY-023); `bank_total` stamped | enum | user-input | matched batches only; reconciled-by recorded |
| Bank-fee posting election | S38 step 3 | prototype-extracted ("Post the $227.50 card/bank fees…") | reason-coded difference posting via S40 mechanics (US-PAY-022) — posting service 🔒 | numeric | user-input | reason + GL required (BR-PAY-019) |
| Plaid connect card | S38 step 1 | prototype-extracted — **no ratified rule** | NOT in v1 (integrations seam; pack report P-6) | — | — | excluded, not silently decided |
| Audit | — | CLAUDE.md #7 | `audit_log` `bank_statement.imported` / `bank_rec.confirmed` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a statement, Then every line persists, auto-match applies amount + ±tolerance-days exactly (and moves when the finance setting moves), and exceptions can only be resolved through S40 — never force-matched silently.
- Given confirm, Then matched batches reconcile + lock with the reconciled-by trail, and flagged batches remain open.
- Given a re-import or a non-finance role, Then nothing duplicates and access is refused.
- Given tenants, Then statements and matches never cross.

**7 · Finance Calculation** — CONFIRMED (PE-11 context; matching is comparison, not computation). `auto_match ⇔ bank_amount = recorded_total ∧ |bank_date − deposit_date| ≤ tolerance_days (default 3)`. Worked: DEP-260805-ACH 14,280.00 = 14,280.00, dates Aug 5 = Aug 5 → Auto; DEP-260805-CHK 2,740.00 ≠ 2,840.00 → exception (resolved in US-PAY-022). **⚠ THE CARDINALITY IS AMENDED (PO 2026-08-12, OQ-161): `recorded_total` may be the SUM OF A GROUP of batches, not one batch.** Worked: DEP-260805-CHK **2,840.00** + DEP-260805-ACH **14,280.00** = **17,120.00** against a single bank credit of **17,120.00** → Auto, one match over two batches. The test is unchanged; what it is applied to is.

**8 · Open Questions** — **OQ-161 — CLOSED 2026-08-12.** The PO ruled *"Build many-to-one matching"*: **many-to-one bank matching is IN SCOPE.** **Worked:** DEP-260805-CHK **$2,840.00** and DEP-260805-ACH **$14,280.00** banked the same afternoon and posted by the bank as **ONE credit of $17,120.00**. Without it those two batches can never be reconciled by anyone, ever — *"it is not an edge case, it is what banks do"*. **What changes is the CARDINALITY, not the test:** equal amount + date within the tenant tolerance (default ±3 days) still governs, applied to the GROUP; every difference still carries reason + GL and *"Force match anyway"* stays permanently superseded (BR-PAY-035). ORIGINALLY (raised 2026-08-11, built to the boundary): matching is ONE-TO-ONE, so a bank that COMBINES two of our deposits into one credit line (or splits one across two) leaves both permanently unmatched and no setting works around it; the PO's OQ-144 closure answered the FEE question and did not address this one; grouped matching is not built — **now ruled in, and still owed.**

---
id: US-PAY-022
epic: EP-PAY-06
module: payments
screens: [S40, S38, S37]
wave: 5
status: draft
blocked_by: []
depends_on: [US-PAY-021, US-PAY-009]
journeys: [J5]
rules: [BR-PAY-019, BR-PAY-004, BR-PAY-013]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-022 — S40 reconcile modal: explain every difference with reason + GL

**1 · Details** — As Finance/Owner staff, I want the S40 modal ("Why doesn't this match?") for every exception: the three-tile header (**We recorded / Bank shows / Difference**), the batch's member payments with per-item cleared state, the suggested explanation, and a resolution that ALWAYS carries a **reason + GL** (BR-PAY-019 — the prototype's "Force match anyway" is superseded by the reason requirement: no unexplained residual ever reconciles; recorded in the pack report). Resolution paths: (a) **reason-coded difference posting** — e.g. PE-11's **−5.00 bank fee** posted to the named GL via the posting service 🔒 (model §12: "rec differences post per reason"); (b) **bounced member check → NSF** — marking an item bounced triggers US-PAY-009 (reversal + fee + notify) and re-computes the batch to match (prototype DEP-260805-CHK #4021 case); (c) keyed-amount error → payment correction through reversal flows (US-PAY-010), never an edit. Audit note captured; resolved batch reconciles + locks (BR-PAY-004). Entry: Resolve on S37/S38/S39. Exit: difference explained to $0.00; batch reconciled; trail on S39/S40.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-019 | Exceptions are worked in the reconcile modal with reason + GL — every difference explained. | CONFIRMED — PO PA-8, 2026-08-08 (PE-11) |
| BR-PAY-004 | Resolution completes the reconcile; the batch locks; Unreconcile is the only reversal. | CONFIRMED — A5 §Batch |
| BR-PAY-013 | A bounced member check resolves via the NSF flow (reversing row + fee + reinstated AR). | CONFIRMED — PO PA-2, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-11: bank 588.17 vs batch 593.17 | Tiles: recorded 593.17 / bank 588.17 / difference **−5.00**; resolution = reason "bank fee" + GL (merchant/bank-fees account) → posting handoff for 5.00 per reason; difference explained to 0.00; batch reconciles; trail records reason + GL + actor |
| TC-2 | Bounced check path (DEP-260805-CHK: −100.00 = check #4021) | Modal suggests the exact-match explanation; marking #4021 "Bounced (NSF)" triggers US-PAY-009 (reversing row, allocations reversed, NSF fee, notify election); batch recorded_total recomputes to 2,740.00 = bank → reconciles |
| TC-3 | Card-fee case (DEP-260804-CARD −147.50) | **The PO's ruling of 2026-08-11 (OQ-144 → BR-PAY-040), verbatim: _"Match net with a fee line"_** — the batch reconciles against the bank's NET **4,972.90** and the **147.50** posts as its OWN line to **6800 Bank fees**: DR 1000 Cash 4,972.90 + DR 6800 Bank fees 147.50 / CR 1010 Undeposited funds 5,120.40. ⚠ **CORRECTED 2026-08-11 (DEF-067)**: this cell named *GL 6200 Merchant Fees*, a code that is in the PROTOTYPE and in NO signed chart — B5 line 74 (❄️) has **6800 Bank fees** and no 6200. Asserted by `test_us_pay_022_tc3__the_card_day_reconciles_net_with_its_fee_as_its_own_line` |
| TC-4 *(clearing linkage)* | NSF from TC-2 | The NSF event hangs off the clearing failure found at rec (BR-PAY-021); the reinstated AR keeps its ORIGINAL due date (BR-PAY-013) |
| TC-5 *(negative)* | Resolve attempted with no reason, or reason without GL for a posted difference | Blocked — reason + GL required (BR-PAY-019); no force-match path exists |
| TC-6 *(negative)* | Resolution amounts not summing to the difference (explain −80.00 of −100.00) | Blocked — the difference must be fully explained before reconcile |
| TC-7 *(isolation)* | Lone Star Ridge exception | Its batches/GL accounts only (RLS) |

**4 · Test Data** — PE-11 verbatim: bank **588.17** vs batch **593.17** → **−5.00** bank fee (Aug 8 statement line vs the PE-10 day's deposits). Prototype cases: DEP-260805-CHK 2,840.00/2,740.00/−100.00 (check #4021, Park, Jenna — NSF); DEP-260804-CARD 5,120.40/4,972.90/−147.50 (fees, GL 6200); DEP-260802-CASH 620.00/540.00/−80.00 (short, reason cash-shortage GL). Audit note: "Check #4021 returned NSF, confirmed with bank Aug 6". Actors: Norma Reyes; NSF consequence to Priya's queue. Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Three tiles | S40 | prototype-extracted | computed: recorded_total / bank_total / difference | numeric(18,6) | computed-display | difference = bank − recorded |
| Member items + cleared state | S40 | prototype-extracted | `payments` in batch + per-item cleared/bounced select | rows | computed-display (+user mark) | bounced → US-PAY-009 |
| Suggested explanation | S40 | prototype-extracted | computed heuristic (exact-amount item match) | text | computed-display | suggestion only — staff decide |
| Resolution reason + GL | S40 | BR-PAY-019 | reason-coded difference record + `ledger_accounts` ref (r12 #10 family); posting via service 🔒 | enum/uuid | user-input | required; Σ explanations = difference |
| NSF fee election | S40 | prototype-extracted ("Add $30.00 NSF fee") + BR-PAY-013 | US-PAY-009 flow (fee from the tenant NSF code) | boolean | user-input | fee amount from the code, never typed |
| Notify election | S40 | prototype-extracted + BR-NOT-005 | `outbound_messages` row | boolean | user-input | queue-write only |
| Audit note | S40 | prototype-extracted | audit payload | text | user-input | required |
| Reconcile completion | S37/S39 | BR-PAY-004 | `deposit_batches.status` → reconciled (locked, US-PAY-023) | enum | system-derived | only when difference fully explained |
| Audit | — | CLAUDE.md #7 | `audit_log` `bank_rec.resolved` (reason, GL, amounts) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given PE-11, Then the −5.00 resolves only with reason + GL, posts per reason via the handoff, and the batch reconciles with the trail complete.
- Given a bounced member item, Then the full NSF flow runs (US-PAY-009) and the batch re-ties to the bank.
- Given any unexplained residual, Then reconcile is impossible — no force-match exists.
- Given tenants, Then exceptions and GLs never cross.

**7 · Finance Calculation** — CONFIRMED (PE-11, model §7 verbatim). Bank **588.17** vs batch **593.17** → **−5.00** explained (bank fee) with reason + GL → trail on S39/S40. Invariant: Σ reason-coded explanations + Σ member corrections = difference, then difference = 0 at reconcile. NSF case figures per US-PAY-009 (fee from the tenant code).

**8 · Open Questions** — **OQ-160 — CLOSED 2026-08-12.** The PO ruled *"derived from shortfall"*: the fee MAY be derived from the difference ($5,120.40 taken, $4,972.90 credited, $147.50 fee), because most acquirers net silently and a stated-fee-only rule makes card reconciliation impossible in practice. `derive_processor_fee` builds the resolution and does NOT reconcile — the derived figure enters through the same door as a human's and meets the same tie-out — and it REFUSES a difference in the wrong direction, since a bank crediting MORE than we recorded has not charged a fee. The superseded reasoning is kept below because the hazard it names is real and is now guarded rather than avoided. ORIGINALLY: the PO's *"match net with a fee line"* settled the fee's LINE and its account (6800); it did NOT settle whether the fee's AMOUNT must be known in advance from the processor's settlement file or may be derived from the difference — *"that distinction decides whether a $10 customer chargeback hides inside a fee line"*. `apps/payments/reconciliation.auto_explain_expected_fee` raises `NotImplementedError("OQ-160")`; a human-stated fee reconciles today. · **OQ-134 (open):** a member cheque that bounces AFTER the batch was reconciled and LOCKED — TC-2's recompute is the UNLOCKED case only, and `reconciliation.assert_bounce_allowed` PERMITS it — **OQ-134 CLOSED 2026-08-12**: the lock holds, the batch total does not move (DEP-260805-CHK stays $2,840.00 when cheque #4021's $100.00 is returned), and the bounce is new rows plus the utility's bounce fee, recorded in payments. Re-totalling a signed-off batch would be the in-place edit hard rule 4 forbids, so `recompute_batch_total` still refuses — as the ruling, not as a leftover.

---
id: US-PAY-023
epic: EP-PAY-06
module: payments
screens: [S39, S37]
wave: 5
status: draft
blocked_by: []
depends_on: [US-PAY-020, US-PAY-021, US-PAY-022]
journeys: [J5]
rules: [BR-PAY-004, BR-PAY-019, BR-PAY-002]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-023 — S39 batch detail + the reconciled lock (Unreconcile is the only reversal)

**1 · Details** — As Finance/Owner staff, I want the S39 batch detail: header (batch code · method · date · payment count · recorded-by · status), KPI tiles (We recorded / Bank shows / Difference / Status), the **payments-in-batch table** (check # · account · customer · amount · cleared state), the **bank-side panel** (posting date · bank reference · bank account · amount posted · statement line), and the **reconciliation trail** (match confidence, exception, suggested action, dated event log — created / imported+matched / flagged / resolved / reconciled-by). And I want the **lock**: once reconciled (BR-PAY-004), the batch's totals and membership are immutable — **Unreconcile is the ONLY reversal** (audited event, Owner/Finance role, returns the batch to unmatched for rework; nothing is ever edited in place, BR-PAY-002 family). J5 step-1 contract satisfied: *batches matched/resolved, locked*. Entry: S37/S38 batch links. Exit: fully-trailed batch; lock enforced.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-004 | Reconciled deposit batches lock; Unreconcile is the only reversal. | CONFIRMED — A5 §Batch |
| BR-PAY-019 | S39 is a FINANCE-area surface (Owner/Finance roles). | CONFIRMED — PO PA-8, 2026-08-08 |
| BR-PAY-002 | Nothing in the money chain is edited in place — Unreconcile is a state reversal, not a rewrite. | CONFIRMED — B2 §payments (family) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open DEP-260805-CHK (prototype fixture) | Header + KPIs (2,840.00 / 2,740.00 / −100.00 / Unmatched); member table shows #4021 Bounced (NSF) highlighted + 7 cleared; bank panel (Aug 5 · CHECK DEPOSIT 4410 · Chase ••4021 · 2,740.00 · Aug 1–6 line 18); trail lists created → imported/matched → flagged −100 |
| TC-2 | After US-PAY-022 resolution | Trail appends the resolution (reason, GL, actor, when) and reconciled-by; status Reconciled |
| TC-3 | Lock enforcement | On the reconciled batch: no member add/remove, no total change, no resolve action; export still allowed; S37 row shows Reconciled |
| TC-4 | Unreconcile | Owner/Finance action with confirm (IS-6): status returns to unmatched, lock lifts for rework, trail appends `batch.unreconciled` (actor + reason) — the ONLY path back (BR-PAY-004); prior trail entries remain forever |
| TC-5 *(negative)* | API UPDATE on a reconciled batch's recorded_total; or Staff role calling Unreconcile | Both rejected — lock trigger + role gate server-side |
| TC-6 *(isolation)* | Lone Star Ridge batch detail | Its batches only; a Brazos Bend batch id 404s (RLS) |

**4 · Test Data** — DEP-260805-CHK per prototype: 8 checks, recorded 2,840.00, bank 2,740.00, difference −100.00; members #4021 Park $100.00 (bounced) · #8842 Miller $247.30 · #1204 Ridge Coffee $500.00 · #0912 Northwind $1,200.00 · #5521 Blueprint $328.60 · #7734 Kim $164.10 · #9902 Wong $180.00 · #2245 Alvarez $120.00. Trail dates Aug 5–6, 2026. Actors: Norma Reyes (Finance), Alex Reed (Owner, Unreconcile). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Header + KPI tiles | S39 | prototype-extracted | `deposit_batches` + computed difference | mixed | computed-display | ties to S37 row |
| Member table | S39 | prototype-extracted | `payments` where deposit_batch_id = batch (+cleared/bounced state) | rows | computed-display | Σ = recorded_total |
| Bank-side panel | S39 | prototype-extracted | matched `bank_lines` row (+ statement ref, r12 #10) | row | computed-display | — |
| Reconciliation trail | S39 | prototype-extracted | append-only batch events (created/matched/flagged/resolved/reconciled/unreconciled — r12 #10 family, DDL 🔒 #17) | rows | system-derived | never truncated |
| Lock | — | BR-PAY-004 | immutability on reconciled `deposit_batches` (+ membership) — trigger family B2 §3 | — | system-derived | totals + membership frozen |
| Unreconcile | S39 header | prototype-extracted + BR-PAY-004 | status reconciled → unmatched + trail event | enum | user-input | Owner/Finance only; confirm + reason; audited |
| Audit | — | CLAUDE.md #7 | `audit_log` `batch.reconciled/unreconciled` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the fixture batch, Then both sides and the full trail render, and every figure ties (members Σ = recorded; bank panel = bank_lines).
- Given reconciled, Then nothing about the batch can change except via Unreconcile — which is role-gated, audited, and preserves the whole trail.
- Given J5 step 1, Then month-end sees batches matched/resolved and locked.
- Given tenants, Then details never cross.

**7 · Finance Calculation** — CONFIRMED (assertion math only): member Σ 100.00 + 247.30 + 500.00 + 1,200.00 + 328.60 + 164.10 + 180.00 + 120.00 = recorded **2,840.00** (prototype figures verbatim); difference −100.00 = bank 2,740.00 − recorded 2,840.00, resolved per US-PAY-022 TC-2.

**8 · Open Questions** — **OQ-163 — CLOSED 2026-08-12, AGAINST WHAT WAS BUILT.** The PO ruled *"no keep it as it is - Utility will balance the books by manual journal entry - if required ; we dont have to do anything just show correct calculations"*: **Unreconcile does NOT take the cash back out of the books.** **Worked, on the PE-10 day:** a **$471.39** batch reconciles (cash up 471.39, undeposited down 471.39); un-reconciling **unlinks the batch and leaves those entries standing**. The product's job is to SHOW the position correctly, not to reverse it automatically; a utility that needs the entry undone posts a **manual journal entry**, which is the one lawful edit the books have (reverse + repost, BR-LED-003). ORIGINALLY (raised 2026-08-11, implemented not stubbed): Unreconcile also REVERSES the reconciliation entry (a NEW linked mirror, US-LED-003), because the PO's cash ruling makes reconciliation the event that realises cash — **that automatic reversal is what the ruling removes**, and the double-realisation hazard it named is now the utility's manual entry to manage. · **NOT BUILT AND REPORTED:** there is no S39/S37 screen and no endpoint — the engine is reachable only from tests (hard-won law 2).


---

## 9 · Build state (2026-08-16, payments SURFACE lane) — **SCREENS SHIPPED**

**The engine had been complete and unreachable since 2026-08-11.** `apps/payments/reconciliation.py` said so itself: *"NO HTTP SURFACE AND NO SCREEN. S37 … S38 … S39 … S40 … do not exist, and neither does an endpoint. Everything below is reachable only from a test or a shell today — built is not wired (hard-won law 2)."* All four screens and eight routes now exist and were driven end to end in a real browser.

**What a person can do, measured on a stack booted from an empty database:** open Finance → Deposits & Bank; see **DEP-260808-CHK $471.39**, **DEP-260808-CSH $121.78** and **DEP-260808-CARD $5,120.40**; cut a drawer day; import a statement; watch the cheque batch auto-match on the exact 471.39; pair the card line by hand; explain **−$147.50** as a processor fee against the `bank_fees` designation (**6800**); reconcile; and watch the batch LOCK with Unreconcile as the only way back.

### Four shapes this lane decided, none of them ruled elsewhere

1. **There is NO bulk "Confirm & reconcile" step 3.** The prototype's third step reconciles every matched batch at once. **BR-PAY-019 requires a reason AND a GL on every DIFFERENCE and a bulk confirm cannot collect one**, so each batch reconciles on its own S39/S40. The cost is real and is stated ON the wizard rather than hidden: batches that tie EXACTLY still need a person to open them. If the PO wants one-click confirmation of the zero-difference batches, that is a rule about what an unexplained-but-equal batch may do without a human, and it is not this lane's to take.
2. **S40 submits ONE explanation.** The engine accepts many; the design shows one difference with one explanation. A repeating-row editor is a bigger form than the ruled case needs and is REPORTED rather than half-built.
3. **The day-cut offers DAYS, not "today".** BR-TEN-043 forbids a server clock, so `bankrec_read.cuttable_days` computes the POSTING days that still hold cleared, unbanked money and the clerk picks one. An empty list is the honest *"everything is banked"*, which a "today" button could never say.
4. **A reconciled row offers View, never Resolve.** BR-PAY-004 locks it and the service refuses a second reconcile, so the control would fail on click (BR-SHL-025).

### Four prototype controls deliberately NOT drawn

| Prototype | Why it is absent |
|---|---|
| **"Force match anyway"** (line 5597) | BR-PAY-035 made it permanently SUPERSEDED. **Absent, not disabled** — `reconcile_batch` has no path that accepts a residual, so there is no body the form could POST; a disabled button would say the feature exists somewhere. |
| **GL picker "6200 · Merchant Fees" / "1020 · Undeposited Funds"** | Neither code is in ANY signed chart (DEF-067). B5 line 74 ❄️ has **1000 Cash · 1010 Undeposited funds · 6800 Bank fees**. The account is resolved by DESIGNATION server-side and no number is written on the screen. |
| **Per-member "Bounced (NSF)" + "$30.00 NSF fee" + "Notify by email"** | The bounce is `apps/payments/reversal.py`'s and the PO placed it on the PAYMENT (2026-08-12, OQ-134). **The same ruling holds the batch total still** — DEP-260805-CHK stays $2,840.00 when cheque #4021's $100.00 is returned — so a control here would imply the total moves. |
| **The Plaid "connect your bank" card** (S38 step 1) | §Scope puts direct bank feeds OUT of v1 as an integrations seam with no ratified rule. Not drawn at all rather than drawn dead. |

### §3 test cases added (browser-driven, on the running app)

| TC | Scenario | Expected |
|---|---|---|
| TC-8 *(US-PAY-020, DEF-127's shape)* | A freshly cut batch, before any statement | Bank shows and Difference BOTH render *"Pending — the bank has not shown this yet"*. **Neither renders `$0.00`** — a zero difference reads as a batch that reconciles perfectly against money nobody has confirmed. In-transit money is its own KPI tile and is never folded into a matched total. Asserted in `07-frontend/src/features/payments/depositsSurface.test.tsx` and on the browser walk |
| TC-9 *(US-PAY-021)* | A three-line statement over the PE-10 day: 4,972.90 · 471.39 · 1.07 | 471.39 auto-matches its cheque batch exactly; 4,972.90 is FLAGGED, not auto-linked (the amounts differ by the fee); 1.07 is *"Not in our system"* — counted, never turned into a payment (batch decision G3) |
| TC-10 *(US-PAY-022)* | The human pairing, then the explanation | Pairing reports what is STILL owed — *"Paired — -$147.50 still to explain"* — so "matched" never reads as "done". The reason and the GL are NOT pre-filled (BR-PAY-019 wants judgement); the DIFFERENCE is, because it is a served fact |
| TC-11 *(US-PAY-023)* | After the reconcile | The row and the detail both report LOCKED, Resolve disappears, Unreconcile appears, and the trail carries created → matched → flagged → resolved → reconciled, oldest first and never truncated |
