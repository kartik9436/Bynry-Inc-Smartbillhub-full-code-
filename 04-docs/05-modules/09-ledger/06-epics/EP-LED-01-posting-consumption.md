# EP-LED-01 — Posting consumption: source-event contracts, dimensions, reversal pairs, tie-outs

**Module:** ledger · **Wave:** W5 · **Screens:** S36, S56 (service-layer boundary; results surface) · **Status:** draft (BR-LED-001..016 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r13)

## Scope
**In:** everything on the CONSUMING side of the ledger posting service 🔒 (B1/CLAUDE.md #5 — the service itself is HUMAN-OWNED; these stories describe what it is handed, what it must leave behind, and how the result is verified): the **per-source-event DR/CR handoff contracts** (billing model §3, payments model §12, BR-CUS-049 opening JEs), **dimension stamping on every journal line** (BR-LED-001, B2 r13 #1), **reversal pairs** for corrections/NSF/void (J6 step 2, BR-LED-003 family, BR-TEN-038 period rules), and the **subledger tie-out views + drift red flag on S36** (BR-LED-007, r13 #6).
**Out:** posting-service internals, entry_date mechanics, idempotency keys, exact DDL — all Eng-Lead 🔒 (r13 #8, CLAUDE.md "Do NOT touch") · manual JE authoring (EP-LED-04) · remittance/close/export (EP-LED-05) · rating math (B4 🔒) · S36 KPI strip rendering (EP-LED-03).
**Tables (B2 + r13):** `journal_entries`, `journal_lines` (+ dimension columns r13 #1), tie-out views (r13 #6); reads (never writes) invoices/lines, payments/allocations, refunds, write_offs, credit_notes, account_opening_buckets, deposit registers.

## Capability matrix (list screens only — B9 conformance)
None — this epic is the posting-consumption boundary (service layer) plus the S36 tie-out panel (a fixed 3-row detail panel, not an IS-2/5 list). List rows for the GL tab live in EP-LED-03/EP-LED-04.

## Stories

---
id: US-LED-001
epic: EP-LED-01
module: ledger
screens: [S56, S36]
wave: 5
status: draft
blocked_by: []
depends_on: [US-BIL-005, US-BIL-007, US-BIL-009, US-BIL-011, US-PAY-001, US-PAY-009, US-PAY-011, US-PAY-012, US-CUS-022]
journeys: [J2, J5]
rules: [BR-LED-001, BR-LED-008, BR-LED-015]
golden_tests: [GT-16]
finance_calc: confirmed
---
### US-LED-001 — Source-event posting contracts: every money event becomes one balanced entry via the posting service 🔒

**1 · Details** — As Finance staff (Owner/Finance roles), I want every upstream money event to reach the books through exactly one channel — the ledger posting service 🔒 (sole writer, CLAUDE.md #5; balanced pairs, hard rule 5; append-only, hard rule 4) — under the DR/CR contracts already ratified in the billing model §3 and payments model §12, so that the J2 step-11 handoff (*balanced journal pair via posting service ONLY*) and the J5 trial balance hold by construction. The contract table (all sources cited; amounts are the upstream document's finalized 2dp figures — posting asserts, never recomputes):

| Source event | DR | CR | Source of contract |
|---|---|---|---|
| Invoice issued (cycle/first/final/rebill/backbill/penalty) | 1200 AR invoice total | per-GL buckets from stamped lines (revenue GLs, tax liability per authority, fee GLs) | billing §3 / BR-BIL-011, BR-BIL-010 (WE-1) |
| First-bill deposit line | (within issue entry) | deposit liability — never revenue | BR-BIL-012 (WE-6) |
| Cash deposit taken (payment purpose=deposit) | cash | deposit liability | LE-1 · BR-PAY-012 |
| Deposit interest accrual (final bill) | deposit interest expense | deposit liability | LE-1 (3.50) · BR-CUS-050/057 |
| Deposit application at final bill | deposit liability | AR | LE-1 (153.50) · BR-BIL-013 |
| Payment cleared | cash/undeposited | AR | payments §12 (PE-1) |
| NSF | reversing pair + fee line | — | payments §12 · BR-PAY-013 (US-LED-003) |
| Reversal / void | reversing pair | — | payments §12 · BR-PAY-011 (US-LED-003) |
| Refund executed | customer credit | cash | BR-PAY-014 (PE-9, 57.13) |
| Write-off approved (**uncollectable debt**) | 6900 bad debt | AR | BR-LED-008 (direct method v1) · BR-PAY-020 (V-5) |
| **Goodwill / concession credit** (PO 2026-08-12) | **its OWN write-off/concession account — NEVER a reversal of service revenue** | customer credit balance | **BR-LED-022** (OQ-105/OQ-168/OQ-187; GT-6: a **$25.00** concession on a **$247.30** invoice leaves the customer owing **$222.30** and the month's revenue unmoved). ⚠ The separate account needs a **finance re-sign** of the chart; until then the posting seam resolves the existing bad-debt designation |
| Credit / adjustment | per direction | per reason-code GL | payments §12 · B2 adjustments.gl_account_id |
| Credit note + rebill (correction) | full GL reversal + new stamps | — | BR-BIL-014 (WE-9; US-LED-003) |
| Master-account balance transfer — **incl. "Balance to owner" at move-out** | AR (master / owner account) | AR (final / tenant account) — same control account, account dimension differs; AR total unchanged | BR-BIL-013 (LE-1, 135.90) · **BR-CUS-097 · PO 2026-10-14 D5, `OQ-1250` CLOSED → (a)** (*"option 1; property is always under landload agreement"*; worked $1,053.78 AC-2026-00041 → owner AC-2026-00053). Caller: `apps/ledger/balance_transfer.py` (source type `transfer`, key `transfer\|<tenant account>\|balance_to_owner`) from `move_out_settlement.shortfall_decision`, `CR-185-BRC10`, 🔒 HUMAN-REVIEW-PENDING |
| Opening balance (cutover batch) | 1200 AR | opening-balance clearing | BR-CUS-049 (GT-16, LE-10) |
| Bank-rec explained difference | per reason GL (e.g. 6800 bank fees) | cash | BR-PAY-019 (PE-11, −5.00) |
| Tax remittance payment | tax payable (authority) | cash | BR-LED-002 (LE-3; US-LED-014) |
| Manual JE | user-authored, balanced at post | — | BR-LED-003 (EP-LED-04) |

Deposit batches and bank rec themselves post NOTHING (grouping only — payments §12); plan activation posts nothing. **And UN-RECONCILING POSTS NOTHING EITHER (BR-LED-024, PO 2026-08-12):** _"no keep it as it is - Utility will balance the books by manual journal entry - if required ; we dont have to do anything just show correct calculations"_ — on the PE-10 day a **$471.39** batch reconciles (cash up **471.39**, undeposited down **471.39**); un-reconciling unlinks the batch and **leaves those entries standing.** A utility that needs them undone posts a manual JE (BR-LED-003), which is the one lawful edit the books have. Every event writes `audit_log` (BR-LED-015, hard rule 7). Idempotency per source document + entry-date mechanics = Eng-Lead 🔒 (r13 #8). Entry: upstream modules hand off (US-BIL-009 contract shape; W3-persisted unposted handoffs post now). Exit: balanced entries visible on S56; S36/S21 read them live.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-001 | Every journal line carries source_type + source_id — every contract row above traces to its document. | CONFIRMED — PO LF-1, 2026-08-08 (LE-2/6) |
| BR-LED-008 | Bad debt = DIRECT write-off v1: DR bad debt / CR AR at approval (BR-PAY-020); allowance method v2. **Narrowed 2026-08-12 to UNCOLLECTABLE debt only — a concession is BR-LED-022's own account.** | CONFIRMED — PO LF-8, 2026-08-08; narrowed PO 2026-08-12 (OQ-187) |
| BR-LED-022 | A goodwill/concession credit debits a SEPARATE write-off account — **DR write-off / CR customer credit balance** — and never reverses the billed revenue. | CONFIRMED — PO 2026-08-12 (OQ-105/OQ-168/OQ-187); the account itself awaits a finance re-sign of the chart |
| BR-LED-025 | The posting service **REFUSES an amount carrying more than two decimals** and names the amount and the caller — rounding is the caller's job, once, at finalization (B4 ❄️). | CONFIRMED — PO 2026-08-12 (OQ-126) _"Refuse and make the caller round"_ |
| BR-LED-026 | A bill whose **GL bucket sums below zero REFUSES to issue** — the posting side never flips the sign onto the other side. | CONFIRMED — PO 2026-08-12 (OQ-152) _"refuse the bill"_; billing half = BR-BIL-010 |
| BR-LED-015 | Every finance action writes audit_log (hard rule 7). | CONFIRMED — PO LB-7, 2026-08-08 |
| BR-BIL-011 *(consumed)* | One bill = one balanced JE (DR AR / CR per-GL buckets); posting service sole writer. | CONFIRMED — PO directive 2026-08-08 · B1/B2 |
| BR-CUS-049 *(consumed)* | Opening balances post as balanced opening JEs (AR ↔ clearing), dated at cutover, immutable. | CONFIRMED — PO AC-4 (GT-16) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-1 month posts end to end (opening 45.00 · deposit 150.00 · interest 3.50 · three bills 553.69 · deposit application 153.50 · transfer 135.90 · payment 292.87) | Every entry balanced; period trial balance totals **598.69 = 598.69** ✔ (LE-1 verbatim); AR total unchanged by the transfer |
| TC-2 | WE-1 issue handoff consumed | One JE: DR 1200 AR **247.87** / CR 4100 88.60 · 4105 12.00 · 4110 39.50 · 4115 8.00 · 4120 15.80 · 4130 18.00 · 4150 40.00 · 2200–03 20.97 · 4200 5.00 (US-BIL-009 TC-4 pair) |
| TC-3 | GT-16 cutover batch (1,213 accounts) | Opening JEs balanced per account; Σ clearing credit = **184,320.55** = Σ imported buckets; re-posting the batch is idempotent — no second JE set (LE-10) |
| TC-4 | Refund PE-9 + write-off V-5 | DR customer credit / CR cash **57.13**; DR 6900 / CR AR **135.90** — each only AFTER its approval event (BR-PAY-014/020); audit rows present |
| TC-5 *(negative)* | A billing/payments code path INSERTs into `journal_lines` directly; an unbalanced handoff | Insert forbidden (sole writer); unbalanced entry rejected by the B2 §3 constraint trigger — nothing partial lands |
| TC-5b *(negative — PO 2026-08-12)* | A caller hands the posting service **8.2985** (three or more decimals); a bill arrives whose GL bucket sums **below zero** | Both REFUSED: the posting names the amount and the caller (BR-LED-025 — the ledger never becomes a second rounding site), and the bill does not issue (BR-LED-026 — a negative bucket means the bill's own lines contradict each other; it is never posted as a debit of the absolute value on the other side) |
| TC-6 *(negative)* | The same issue handoff replayed twice | Second replay no-ops on the per-source posting guard (mechanics 🔒) — one entry, ever |
| TC-7 *(isolation)* | Lone Star Ridge posts its own month | Its entries only; Brazos Bend journal rows invisible under RLS; a forged source_id from the other tenant posts nothing |

**4 · Test Data** — LE-1 fixture verbatim: WE-1 (ACC-1042, 247.87 billed, 292.87 paid incl. 45.00 prior) · WE-3 minimum bill 16.42 unpaid · WE-7B final bill 289.40, deposit 153.50 applied, remainder 135.90 transferred ACC-1055 → master ACC-0009. GT-16: A-12103 buckets 84.20/62.10/0.00/121.00 = 267.30; batch total 184,320.55, cutover 2026-08-31. PE-9 refund 57.13; V-5 write-off 135.90. Actors: system (posting), Norma Reyes (Finance, verification). Isolation: Lone Star Ridge (J. Okafor).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Journal entry | S56 | billing §3 / payments §12 | `journal_entries` (entry_date, source_type, source_id, memo) | row | system-derived | posting service sole writer 🔒 |
| Journal line | S56 | B2 DDL | `journal_lines` (ledger_account_id, side, amount) | numeric(18,6) USD | system-derived | amount ≥ 0; Σ debit = Σ credit per entry (deferred trigger) |
| Source reference | S56 | BR-LED-001 | `journal_lines.source_type` + `source_id` (r13 #1) | enum/uuid | system-derived | every line traces to its document |
| Contract amounts | — | upstream documents | asserted from finalized 2dp figures (invoices, payments, refunds, write_offs, buckets) | numeric(18,6) | system-derived | never recomputed at posting |
| Opening JE | S56 | BR-CUS-049 / GT-16 | `journal_entries.source_type='opening_balance'` (r9 #3) | row | system-derived | dated at cutover; idempotent per (batch, account) |
| Posting guard | — | CLAUDE.md #6 family | per-source idempotency (mechanics Eng-Lead 🔒, r13 #8) | — | system-derived | replay no-ops |
| Audit | — | CLAUDE.md #7 | `audit_log` `journal.posted` (source ref) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the LE-1 month, Then every contract row above produces exactly its DR/CR shape, every entry balances, and the period foots 598.69 = 598.69.
- Given any attempted write outside the posting service, or any unbalanced handoff, Then the database refuses it.
- Given a replayed handoff, Then no duplicate entry ever exists; given tenants, books never cross.

**7 · Finance Calculation** — CONFIRMED (LE-1 verbatim, machine-computed): 1000 Cash DR **442.87** (150.00 + 292.87) · 1200 AR DR **152.32** · deposit interest expense DR **3.50** · revenue CR **506.31** (226.90 + 15.00 + 264.41) · tax payable CR **47.38** (20.97 + 1.42 + 24.99) · 2300 deposit liability CR **0.00** (150.00 + 3.50 − 153.50) · 3000 opening balance equity CR **45.00** → totals **598.69 = 598.69** ✔. Opening batch: GT-16 — DR 1200 AR **184,320.55** / CR opening clearing **184,320.55** (LE-10).

**8 · Open Questions** — None.

---
id: US-LED-002
epic: EP-LED-01
module: ledger
screens: [S56, S36]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-001]
journeys: [J2, J5]
rules: [BR-LED-001, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-002 — Dimension stamping: service · account · premises+unit · source · tax authority on every line

**1 · Details** — As the Product Owner's reporting model requires (LF-1 directive: Revenue & AR, remittances, exports "manageable at utility / service / account / premises+unit / deposit / charges / taxes / refund / credit level"), I want every journal line stamped at posting with the full dimension set (BR-LED-001, B2 r13 #1): `service` (from the invoice line's service) · `account_id` (source document) · `premises_id` + `unit_id` (resolved account→unit→premises AT POSTING TIME; the chain never breaks per BR-MET-046 — units never move between premises) · `source_type` + `source_id` (deposit/charges/taxes/refund/credit levels) · `tax_authority_id` on tax lines — so that S36, the trial balance expansion, remittance, by-premises and export drill-back are ALL the same query grouped differently, and no side-maintained number exists anywhere (BR-REP-002). Utility level = tenant roll-up. Entry: US-LED-001 contracts. Exit: dimensioned lines feeding EP-LED-03/05 read-models.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-001 | Every journal line carries service · account_id · premises_id+unit_id (resolved at posting) · source_type+source_id · tax_authority_id (tax lines) — all PO-named levels computed from the books, never side-maintained. | CONFIRMED — PO LF-1, 2026-08-08 (LE-2/6) |
| BR-MET-046 *(consumed)* | Units never move between premises — by-premises money traceability guaranteed. | CONFIRMED — PO PU-19 |
| BR-REP-002 *(consumed)* | Reports/dashboards are read-models over journal-line dimensions; never a side-maintained number. | CONFIRMED — reports audit 2026-08-08 |
| BR-LED-015 | Stamping is system posting work; consuming finance actions audit. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | WE-1 issue entry lines | Revenue lines carry service (electric/water/sewer/trash/solar), ACC-1042, premises 500 Main St + unit, source_type `invoice_line` + line id; tax lines carry tax_authority_id (State/County/City/PUC) |
| TC-2 *(balance)* | LE-2 slice: revenue lines grouped by service | Electric **100.60** (88.60 usage + 12.00 base) · Water **47.50** · Sewer **15.80** · Trash **18.00** · Solar **40.00** · Late fee **5.00** = **226.90** ✔ — Σ of the slice = the revenue CR total, to the cent |
| TC-3 | Same lines, regrouped | By premises reproduces LE-6; by authority reproduces LE-3's 20.97 split (13.87/2.22/4.44/0.44) — one dimension set, every slice |
| TC-4 | Unit deactivated + recreated after posting (BR-MET-046 lifecycle) | Historical lines keep their stamped premises_id/unit_id forever — reporting on old periods is unchanged |
| TC-5 *(negative)* | A posting handoff whose account has no resolvable unit→premises chain; a tax line without tax_authority_id | Posting fails atomically naming the gap — no undimensioned money line ever lands |
| TC-6 *(isolation)* | Lone Star Ridge dimension query | Its lines only (RLS); grouping never sees Brazos Bend premises |

**4 · Test Data** — WE-1/LE-2 verbatim (ACC-1042 · 500 Main St). Authorities: TX Comptroller 13.87 · Travis County 2.22 · City franchise 4.44 · TX PUC 0.44. Regroup fixtures: LE-6 premises rows (500 Main St / Oak Grove / Marina Bay). Isolation: Lone Star Ridge premises "Cedar Flats".

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| service | S56 expansion / S36 | BR-LED-001 | `journal_lines.service` (r13 #1) | enum | system-derived | from invoice line's service; null on non-service lines |
| account_id | S56 / S21 ledger | BR-LED-001 | `journal_lines.account_id` (r13 #1) | uuid | system-derived | from source document |
| premises_id + unit_id | S56 / S59 / S60 | BR-LED-001 | `journal_lines.premises_id`, `unit_id` (r13 #1) | uuid | system-derived | resolved account→unit→premises at posting time (BR-MET-046) |
| source_type + source_id | S56 / S59 | BR-LED-001 | `journal_lines.source_type`, `source_id` (r13 #1) | enum/uuid | system-derived | required on every line |
| tax_authority_id | S41 | BR-LED-001 | `journal_lines.tax_authority_id` (r13 #1) | uuid | system-derived | required on tax-liability lines |
| Audit | — | CLAUDE.md #7 | `audit_log` (posting events carry dimension payload) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given any posted line, Then all applicable dimensions are present and immutable with the line.
- Given the LE-2 query, Then grouping by service / premises / authority reproduces LE-2 / LE-6 / LE-3 from the SAME rows.
- Given a resolution gap, Then posting fails loudly; given tenants, dimensions never cross.

**7 · Finance Calculation** — CONFIRMED (LE-2 verbatim): Electric 100.60 + Water 47.50 + Sewer 15.80 + Trash 18.00 + Solar 40.00 + Late 5.00 = **226.90** ✔ = WE-1 current charges. Same rows by authority: 13.87 + 2.22 + 4.44 + 0.44 = **20.97** ✔.

**8 · Open Questions** — None.

---
id: US-LED-003
epic: EP-LED-01
module: ledger
screens: [S56]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-001, US-BIL-015, US-PAY-009, US-PAY-010]
journeys: [J6, J5]
rules: [BR-LED-003, BR-LED-015]
golden_tests: [GT-6]
finance_calc: confirmed
---
### US-LED-003 — Reversal pairs: corrections, NSF, void — linked mirror entries under append-only books

**1 · Details** — As Finance staff, I want every correction-shaped upstream event to reach the books as a **linked reversal pair, never an edit** (hard rule 4; BR-LED-003 family — posted rows immutable, "corrections are new rows"), satisfying the J6 step-2 contract (*balanced reversal, period rules per BR-TEN-038*): (a) **bill correction** (US-BIL-015, BR-BIL-014): credit note = full GL reversal of the original entry, rebill = fresh entry with its own stamps — original entry untouched (GT-6); (b) **NSF** (US-PAY-009, BR-PAY-013): reversing pair for the payment entry + the NSF fee line from the tenant charge code; (c) **payment reversal/void** (US-PAY-010): reversing pair per payments §12. Every reversal entry links to the entry it mirrors (r13 #2 `reversal_of`); events dated into a closed period auto-post forward with audit (BR-TEN-038 — LE-9 mechanics in US-LED-015). Entry: upstream approval events. Exit: mirrored, linked, balanced history — net effect correct, trail complete.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-003 | Posted journal entries are IMMUTABLE (hard rule 4); correction = mirror entry linked, never an edit. | CONFIRMED — PO LF-3, 2026-08-08 (LE-8) |
| BR-TEN-038 *(consumed)* | Closed-period money events auto-post to earliest open period with audit note. | CONFIRMED — PO Q&A R6 (OQ-033 closed) |
| BR-BIL-014 *(consumed)* | Correction workflow: credit note + rebill with GL reversals, approval-gated. | CONFIRMED — PO A-5, 2026-08-08 (WE-9) |
| BR-PAY-013 *(consumed)* | NSF = reversing row + fee + reinstated AR at original due date. | CONFIRMED — PO PA-2, 2026-08-08 (PE-7) |
| BR-LED-015 | Every reversal writes audit_log. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | WE-9 correction executes (V-3) | Credit-note entry mirrors the original in full (**−247.87** across the same GLs); rebill entry posts **+227.95** with its own stamps; both balanced; net revenue+tax effect **−19.92**; original entry byte-identical after |
| TC-2 | NSF PE-7 (V-2) | Payment entry mirrored (**322.87** reversing pair), NSF fee line posts from the tenant charge code; trial balance shows both pair legs + fee — nothing netted away |
| TC-3 | Reversal links | Each mirror entry carries `reversal_of` → original; original resolves forward to its mirror; S56 renders the linkage both ways |
| TC-4 | Correction event dated into closed July (arrives Aug 7) | Entry auto-posts into August with the BR-TEN-038 audit note — closed books stay closed (LE-9 pattern) |
| TC-5 *(negative)* | UPDATE/DELETE attempted on any posted `journal_entries`/`journal_lines` row | Rejected outright by the append-only triggers (B2 §3) — the ONLY correction path is a mirror entry |
| TC-6 *(negative)* | A reversal handoff arrives without its upstream approval event (correction not approved) | Nothing posts — no money-bearing write before approval (BR-BIL-014) |
| TC-7 *(isolation)* | Lone Star Ridge correction | Mirrors only its own entries; a Brazos Bend entry id in the handoff posts nothing (RLS) |

**4 · Test Data** — WE-9 verbatim: water 8→6 kgal; original 247.87, corrected 227.95, customer credit 19.92 (credit note full reversal + rebill with own stamps). PE-7 NSF 322.87 + $30.00 NSF fee (tenant code, never typed). GT-6 shape: invoice 247.30 · credit 25 · original immutable · balanced reversing entry. Dates: correction approved Aug 12, 2026; late-dated case Jul 30 arriving Aug 7. Actors: Priya Shah (Billing, initiates), Alex Reed (Admin approval), posting service (writes). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Mirror entry | S56 | BR-LED-003 / payments §12 | `journal_entries` + `journal_lines` (same GLs, sides swapped) | rows | system-derived | balanced; posting service only |
| Reversal link | S56 | B2 r13 #2 | `journal_entries.reversal_of` | uuid | system-derived | mirror ↔ original, both ways |
| Correction sources | S56 | BR-BIL-014 | source_type `credit_note` / rebill invoice refs | enum/uuid | system-derived | posts only after approval |
| NSF fee line | S56 | BR-PAY-013 | fee line to the charge code's GL | numeric(18,6) | system-derived | amount from tenant code |
| Closed-period dating | S56 | BR-TEN-038 | entry lands in earliest open period + audit note | date | system-derived | never into a locked period |
| Audit | — | CLAUDE.md #7 | `audit_log` `journal.reversed` (link, reason, source) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an approved correction, Then the books show original + mirror + rebill — all balanced, all linked, original untouched (GT-6).
- Given an NSF, Then the pair + fee are separate visible legs, never a net.
- Given a closed period, Then the event forwards with audit; given no approval, nothing posts; given tenants, mirrors never cross.

**7 · Finance Calculation** — CONFIRMED (V-3 verbatim, machine-computed): credit note −247.87 (full GL reversal: revenue −226.90, tax −20.97... per original stamps) + rebill +227.95 (water 26.50, sewer 10.60, taxable 203.70, tax 19.25) → **net revenue/tax −19.92** = 247.87 − 227.95. NSF V-2: reversing pair **322.87** + fee **30.00**, all legs visible in the TB.

**8 · Open Questions** — None.

---
id: US-LED-004
epic: EP-LED-01
module: ledger
screens: [S36]
wave: 5
status: draft
blocked_by: []
depends_on: [US-LED-001, US-LED-002, US-PAY-020]
journeys: [J5]
rules: [BR-LED-007, BR-LED-015]
golden_tests: []
finance_calc: confirmed
---
### US-LED-004 — Subledger tie-out views + drift red flag on S36 (release blocker)

**1 · Details** — As Finance/Owner staff, I want the three **control-vs-register tie-outs rendered side by side on S36** (BR-LED-007, A1 addendum 2026-08-08: "S36 adds tie-out panel"; views per B2 r13 #6): **deposit-liability GL = Σ deposits held per account** · **AR GL = Σ account balances** · **tax payable GL = remittance report outstanding** — and I want ANY drift to render a **red flag naming the delta and the subledger**, treated as a **release blocker** (drift can only mean a bypass of the posting service). Basis labels per BR-REP-001 on each side (billing-side registers = posting basis). The panel is computed live from journal-line dimensions vs the operational registers — never cached independently (BR-REP-002; `accounts.balance` is a cache, the ledger is the source of truth per B2). Entry: S36 Finance tab. Exit: three green equalities, or a named red flag.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-LED-007 | Tie-outs on S36: deposit-liability GL = Σ deposits held · AR GL = Σ account balances · tax payable = remittance outstanding; ANY drift = red flag + release blocker. | CONFIRMED — PO LF-7, 2026-08-08 (LE-7) |
| BR-REP-001 *(consumed)* | Every money number labels its date basis. | CONFIRMED — PO ruling 2026-08-08 |
| BR-REP-002 *(consumed)* | Panel = read-model over dimensions; never side-maintained. | CONFIRMED — reports audit 2026-08-08 |
| BR-LED-015 | Tie-out inspection/acknowledgement events audit. | CONFIRMED — PO LB-7, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(balance)* | LE-1 month, correct state | AR tie-out: GL **152.32** = register 135.90 (master-held transfer) + 16.42 (unpaid WE-3) ✔; deposit tie-out **0.00 = 0.00** after application ✔; tax payable **47.38** = remittance outstanding ✔ — all three green |
| TC-2 | LE-7 fault simulation: deposit register 153.50, GL 150.00 | Red flag: drift **−3.50**, subledger named ("Deposit liability"), cause class "missed interest posting"; flagged as release blocker until explained |
| TC-3 | Basis labels | AR/deposit/tax sides labeled POSTING basis per BR-REP-001 — no unlabeled money number on the panel |
| TC-4 | Ops chip | Tie-out drift surfaces on the S7/S32 ops chips (BR-REP-015) linking back to the S36 panel |
| TC-5 *(negative)* | Attempt to dismiss/acknowledge-away a drift, or hand-adjust a register to force equality | No dismiss path exists — drift clears only when the explaining entry posts through the service; register edits are upstream-owned and audited |
| TC-6 *(isolation)* | Lone Star Ridge S36 | Its registers and GL only; drift in one tenant never flags the other (RLS) |

**4 · Test Data** — LE-1/LE-7 verbatim: AR 152.32 = 135.90 + 16.42; deposit 0.00/0.00 (after 150.00 + 3.50 − 153.50); tax 47.38. Fault fixture: deposit register 153.50 vs GL 150.00 → −3.50. Actors: Norma Reyes (Finance), Alex Reed (Owner). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Deposit tie-out row | S36 panel | BR-LED-007 | tie-out view (r13 #6): deposit-liability GL vs Σ deposits held (accounts.deposit_on_file + interest) | numeric(18,6) | computed-display | equality or red flag |
| AR tie-out row | S36 panel | BR-LED-007 | tie-out view: AR GL vs Σ account balances | numeric(18,6) | computed-display | equality or red flag |
| Tax tie-out row | S36 panel | BR-LED-007 | tie-out view: tax payable GL vs remittance outstanding (US-LED-014) | numeric(18,6) | computed-display | equality or red flag |
| Drift flag | S36 / S7·S32 chips | BR-LED-007 + BR-REP-015 | computed (delta + subledger name) | numeric/text | computed-display | release blocker; no dismiss |
| Basis label | S36 panel | BR-REP-001 | rendered label | text | computed-display | required on every money number |
| Audit | — | CLAUDE.md #7 | `audit_log` `tieout.drift_detected` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the LE-1 state, Then all three tie-outs render equal to the cent with basis labels.
- Given the LE-7 fault, Then the red flag names −3.50 and the deposit subledger, blocks release, and cannot be dismissed — only explained through the posting service.
- Given tenants, Then panels never cross.

**7 · Finance Calculation** — CONFIRMED (LE-1/LE-7 verbatim): AR tie-out **152.32 = 135.90 + 16.42** ✔ · deposit **0.00 = 0.00** (150.00 + 3.50 − 153.50) ✔ · drift case **150.00 − 153.50 = −3.50** → red flag. Invariant: GL control = Σ register, per subledger, always.

**8 · Open Questions** — None.
