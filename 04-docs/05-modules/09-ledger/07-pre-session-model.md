# ledger / Finance — Pre-Session Model (PM understanding for PO review)

> **STATUS: DRAFT — FOR PRODUCT OWNER REVIEW.** Open items carry LF-# (Lane A) / LB-# (Lane B). Registry rows at closure.
> PO directive (2026-08-08): Revenue & AR · bank reconciliation · general entries (edit/update) · tax remittances · export to accounting — manageable at utility / service / account / premises+unit / deposit / charges / taxes / refund / credit level, with GL mapping clean enough to HAND OVER to an ERP or accounting system. "This is meter-to-cash handover to accounting or ERP."

## 1. Position — the handover boundary

The ledger is where SMARTBillHub stops being a billing system and becomes auditable books. Rules already law: **posting service is the ONLY writer** (B1) · **balanced pairs always** (hard rule 5) · **journal entries append-only** (hard rule 4) · every upstream event's DR/CR contract is written (billing model §3, payments model §12) · GL stamped per line at issue (BR-BIL-010). Screens: S36 Revenue & AR · S37–S40 deposits/bank (payments-owned tables, Finance-surfaced per BR-PAY-019) · Finance GL tab (trial balance + account mapping, design r2) · Manual JE + Record refund modals (r2) · S42 export · reports (Account ledger, By-premises summary).

## 2. THE DIMENSION MODEL (LF-1) — every level the PO named, on every journal line

Every journal line carries, besides tenant (RLS) + GL account + side + amount:
| Dimension | Gives the PO | Source |
|---|---|---|
| `service` | utility-SERVICE-level P&L (electric vs water vs trash…) | invoice line's service |
| `account_id` | ACCOUNT-level ledger (S21 ledger, statements) | source document |
| `premises_id` + `unit_id` | PREMISES/UNIT-level reporting (r2/r3 by-premises reports; BR-MET-046 guarantees the chain never breaks) | account→unit→premises at posting time |
| `source_type` + `source_id` | DEPOSIT / CHARGES / TAXES / REFUND / CREDIT level — every line traces to its document (invoice line, payment, adjustment, refund, deposit, write-off, opening, remittance, manual JE) | posting service |
| `tax_authority_id` (tax lines) | per-authority remittance | invoice tax line |
Utility level = the tenant roll-up of everything. **One dimension set, every slice on your list — no side reports maintained by hand.**

## 3. Revenue & AR (S36) — worked LE-1/LE-2

Mini month (one account for clarity — fixture WE-1 bill + full payment):
| GL | DR | CR |
|---|---|---|
| 1000 Cash | 292.87 | |
| 1200 AR (45.00 opening + 247.87 billed − 292.87 paid) | 0.00 | |
| 4xxx Revenue by service (elec 100.60 · water 47.50 · sewer 15.80 · trash 18.00 · solar 40.00 · late 5.00) | | 226.90 |
| 2200-03 Tax payable (13.87/2.22/4.44/0.44) | | 20.97 |
| 3000 Opening balance equity | | 45.00 |
| **Totals** | **292.87** | **292.87** ✔ |
S36 renders revenue-by-service, billed-vs-collected, and aging straight from dimensions — never a separately maintained number.

## 4. Manual journal entries — "edit/update" under append-only (LF-3)

Three types (design r2): **standard** · **accrual** (auto-reverses on day 1 of the next period — LF-5) · **reversing**. Lifecycle: **draft** (editable, deletable, worthless) → **posted** (immutable forever). "Edit" of a posted JE = **reverse + repost**: one click generates the mirror entry, links both, opens a prefilled new draft — books stay append-only (hard rule 4 is never violated), and the trail shows exactly what happened. Balanced required at post; Finance/Owner role; reason required; audit row. Worked LE-4: Sep 30 accrue $500 unbilled revenue (DR 1210 Unbilled AR / CR 4100) → auto-reverses Oct 1 → October's real billing posts normally.

## 5. Tax remittances (LF-2) — worked LE-3

Tax payable accumulates per authority via dimensions. Remittance report per period: **billed basis** (tax on issued bills: July 20.97 = State 13.87 · County 2.22 · City 4.44 · PUC 0.44) and **collected basis** (tax inside cleared payments, via allocation) — authorities differ on which they demand, so BOTH are computed and a per-authority setting picks the remitting basis (LF-2). Recording the remittance payment = JE: DR 2200 State 13.87 / CR cash — liability drains to zero, the report shows remitted vs outstanding.

## 6. Export to accounting / ERP (LF-4) — worked LE-5

The handover: **one summary JE per period per GL account** (J5 contract) to QuickBooks Online / Xero / CSV / IIF, using **export codes on the GL mapping page** (each SMARTBillHub GL account carries the target system's account ref). Detail stays here: the ERP gets clean totals; every exported figure drills back to dimensioned lines on demand (auditor question → answer in seconds). Export batches are recorded (what, when, where, by whom) and idempotent — re-running a period cannot double-hand-over. Dimension-level CSV extracts (by service / premises / authority) available for ERPs that want detail.

## 7. Close & period lock (LF-6)

Monthly close per fiscal settings (S8): Finance/Owner closes; closed period locks (BR-TEN-038 already law: late-dated events auto-post forward with audit; SysAdmin reopens). Close checklist: all bill runs issued · payment batches reconciled · bank rec current · accruals posted · remittance recorded → close → export.

## 8. Subledger reconciliations (LF-7) — worked LE-7

Control accounts must equal their operational registers, shown side by side: **deposit liability GL = Σ deposits held per account** (e.g. 153.50 after interest) · **AR GL = Σ account balances** · **tax payable = remittance report outstanding**. Any drift = red flag on S36 (it can only mean a bypass of the posting service — release blocker).

## 9. Bank reconciliation

Already ruled (BR-PAY-019, PA-8): Finance-surfaced S37–S40, auto-match ±3 days on CLEARING dates (BR-PAY-021), differences explained with reason + GL. Ledger consumes the explained differences as postings (bank fee example: DR 6800 Bank fees 5.00 / CR cash).

## 10. Write-offs / bad debt (LF-8)

Direct write-off method (right-sized for <3,000 connections): DR 6900 Bad debt / CR AR at approval (BR-PAY-020). Allowance method = v2 if a tenant's auditor demands it.

## 11. Scenario catalog

LE-1 balanced mini trial balance · LE-2 revenue-by-service slice · LE-3 remittance both bases + payment JE · LE-4 accrual auto-reverse · LE-5 QBO export + idempotent re-run + drill-back · LE-6 by-premises billed/collected/owed via the unit chain · LE-7 subledger-vs-control tie-outs · LE-8 posted-JE reverse+repost · LE-9 close with late-dated event auto-forward · LE-10 opening-balance JEs tie to GT-16.

## 12. Lanes

**Lane A:** LF-1 the dimension set (§2 table) · LF-2 remittance basis per authority (billed vs collected, both computed) · LF-3 posted-JE edit = reverse+repost only (hard rule 4 stands) · LF-4 export shape (summary JE + export codes + detail drill-back, idempotent batches) · LF-5 accrual JEs auto-reverse day 1 next period · LF-6 close roles (Finance/Owner close, SysAdmin reopen) · LF-7 subledger tie-outs on S36 with drift = red flag · LF-8 direct write-off method v1.
**Lane B:** LB-1 trial balance screen (period + premises filter, expand to dimensions, export) · LB-2 Account ledger report (account + premises + range, PDF/CSV) · LB-3 By-premises summary (billed/collected/owed, collection %) · LB-4 JE list capability row per IS-5 · LB-5 remittance report layout per authority · LB-6 GL mapping page carries export codes · LB-7 every finance action audited · LB-8 S36 KPI strip (revenue, collected, AR, aging buckets).
**Lane C (batch #6 preview):** journal_lines dimension columns (service, account, premises, unit, source_type/id, tax_authority) · JE type enum + auto-reverse link + draft state · tax_remittances table · export_batches (idempotent) · ledger_accounts export-code columns (QBO/Xero refs) · subledger tie-out views · seeded chart finalization (closes B2 O-14, with finance) · mechanics Eng-Lead 🔒.

## Addendum r1 — SESSION CLOSED (2026-08-08)
Lane A LF-1..8 ALL CONFIRMED → BR-LED-001..008 · Lane B LB-1..8 ALL CONFIRMED → BR-LED-009..016 · Lane C batch #6 APPROVED → B2 Addendum r13. Workbook of examples/variations: 08-worked-examples.md (PO directive: keep on file). Ledger pack authoring queued behind the payments pack (single writer on the traceability matrix).
