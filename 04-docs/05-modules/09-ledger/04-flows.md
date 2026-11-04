# ledger — Flows & States

Screens: S36 Revenue & AR · S41–S43 Taxes/Export · S56 GL tab · S57 Manual JE · S59/S60 reports · **S73 Cost of service · S74 Bought-vs-billed reconciliation** (details: A1 screen inventory + addenda, A9 navigation map; S73/S74 are PROVISIONAL from the reserved S61–S90 block — OQ-204). Extracted from the ratified model (07-pre-session-model.md, BR-LED-001..016) at pack authoring, 2026-08-08; §7–§8 added 2026-08-15 for EP-LED-06.

## 1. Posting flow (US-LED-001/002 — service 🔒)
```
upstream event (invoice issue · payment · NSF · refund · write-off · transfer ·
opening · deposit take/apply/interest · adjustment · rec difference · remittance · manual JE)
  → posting service 🔒 (SOLE writer, CLAUDE.md #5)
     → journal_entries + journal_lines: balanced (hard rule 5, deferred trigger)
     → dimensions stamped per line: service · account · premises+unit · source_type+id · tax_authority (BR-LED-001)
     → audit_log (hard rule 7)
  → read-models: S36 KPIs/panels · S56 TB · S59/S60 · S41 · S42 — same rows, regrouped (BR-REP-002)
```
Events dated into a closed period auto-forward to the earliest open period + audit note (BR-TEN-038).
⚠ **A captured supplier invoice is NOT in the event list above, and that is not an omission** — whether a capture posts at all is **OQ-200, OPEN** (see §7).

## 2. Journal entry lifecycle (US-LED-011/012/013)
```
draft (editable · deletable · worthless · NO JE- number)
  --Post (balanced + memo + System Admin | Billing Clerk)--> posted (IMMUTABLE, hard rule 4)
                                                             + JE- number stamped here (BR-LED-021)
posted --Reverse+repost (one click, reason)--> mirror entry (linked reversal_of) + prefilled new draft   [LE-8]
posted(type=accrual) --day 1 next period (auto)--> mirror entry (auto_reverse link, both ways)           [LE-4]
```
No UPDATE/DELETE on posted rows, ever. An entry reverses once.
**Amended 2026-08-12 (PO):** the actor was written *"Finance/Owner"*, which names roles this product does not have — **System Admin and Billing Clerk may reverse a posted entry; Executive may NOT** (BR-LED-003, OQ-175: _"System Admin, Billing Clerk"_). The `JE-` number is allocated per tenant and stamped **at POST**, so a draft has none (BR-LED-021, OQ-176). `reversed` is a **link between two entries, never a status value** (OQ-184). Elsewhere in this file "Finance/Owner" still stands where the PO has not separately ruled (the close of §3, the remittance of §4, the capture of §7) — flagged there, not silently rewritten.

## 3. Close cycle (US-LED-015 — J5 step 3)
```
checklist computed live (BR-LED-006): runs issued · batches reconciled · bank rec current ·
accruals posted · remittance recorded
  → Close (Finance/Owner, IS-6 confirm) → period LOCKED
       late-dated events → auto-post forward + audit (BR-TEN-038, LE-9)
       late-dated CAPTURES → same rule, same audit note (BR-LED-034, LE-13)
  → Reopen = System Admin only, reason + audit
```

## 4. Remittance flow (US-LED-014 — S41)
```
tax-liability lines by authority (dimension) → BOTH bases computed always:
  billed (tax on issued bills, posting basis) | collected (tax inside cleared payments via allocation, clearing basis)
→ per-authority basis setting picks the remitting figure (BR-LED-002) — PO 2026-08-12 confirmed BOTH bases are legitimate and the choice is the CUSTOMER'S; the setting lives on **S71 Finance controls (Settings → Configure)**, keyed by the authority's 2200-nn account. An authority nobody has chosen for reports `remitting_basis=None` and is named by `per_authority_remitting_basis_is_not_stored` — never defaulted
→ Record remittance = JE: DR authority tax payable / CR cash (posting service 🔒)
→ tax_remittances row + filing history; outstanding → S36 tax tie-out (BR-LED-007)
```

## 5. Export flow (US-LED-016 + US-LED-021 — S42/S43, J5 step 4 · J25 step 10)
```
closed period → GL summary (one summary JE per period per GL account, balanced)
              + COST-OF-SERVICE SECTION (one summary row per period per cost GL account, BR-LED-039)
→ target QBO | Xero | CSV | IIF, addressed by mapping-page export codes (BR-LED-014)
→ ONE export_batches row (period, target, who/when, content hash) — IDEMPOTENT: re-run blocked w/ link (LE-5)
   **Built 2026-08-15 (backend only)** — `apps/ledger/exports.py`, four gates in this order:
   **closed** (BR-LED-017, asked as *is every period this window touches shut*, so a weekly slice
   of a closed month passes) → **not already covered** (per WINDOW, whichever granularity; the DB's
   UNIQUE(period,target) is the other half) → **foots** (BR-LED-007, asserted on the PERIOD, since
   a single week may lawfully not balance) → **every row carries the target's ref** (QBO/Xero only;
   CSV/IIF address by code+name). The PAYLOAD is stored and hashed, so a later ref edit cannot
   rewrite a sent batch. **No file is written and nothing is sent** (BR-LED-020 v1 = file/batch;
   the S43 modal and IS-11 downloads are another lane's), and the `EXP-` number cannot be allocated
   because no tenant has that `number_series` row — the batch records `batch_no = None` and says so.
     the payable side rides the SAME batch; a second July batch would be the double-handover BR-LED-004 prevents
→ drill-back: every figure → its dimensioned lines / its supplier invoice · dimension CSVs (service/premises/authority/supplier)
```
⚠ Whether the cost rows are **journal-derived** or a **labelled register extract** depends on **OQ-200**; a register-derived section is never summed into a trial-balance footer that does not contain it.

## 6. Tie-out states (US-LED-004 — S36)
```
GREEN: deposit-liability GL = Σ deposits held · AR GL = Σ account balances · tax payable = remittance outstanding
DRIFT: any inequality → red flag naming delta + subledger → RELEASE BLOCKER (BR-LED-007, LE-7)
  — no dismiss path; clears only when the explaining entry posts through the service
```

## 7. Cost-of-service CAPTURE flow (US-LED-018/019 — S73, J25 steps 2–3 · 6 · 8–9)
```
supplier's invoice arrives on paper/PDF (outside the product)
  → CAPTURE (S73, IS-6 modal → confirm → toast → audit):
       date · service|O&M|Infrastructure · supplier name FREE TEXT · amount NUMERIC(18,6)+CHAR(3)
       · volume OPTIONAL + its explicit unit · GL account · period · reference · memo   (BR-LED-029/030/033)
  → supplier_invoices row (PROPOSED table; B2 addendum owed)  + audit_log supplier_invoice.captured
  → dated into a CLOSED period? → auto-forward to the earliest open period + audit note (BR-LED-034 / BR-TEN-038)
  → ⚠ POST a journal entry? — OQ-200 OPEN. The boundary raises NotImplementedError("OQ-200"); nothing guesses.

register (S73): list · search supplier/reference/memo · filter period/service/status/volume-captured
  --Edit (period OPEN, before/after audit)--> updated          (BR-LED-034)
  --Void (reason REQUIRED, IS-6 confirm)---> voided, ROW STAYS VISIBLE, leaves every aggregate  (BR-LED-035)
  --Delete--------------------------------> NO SUCH PATH, at any layer (hard rule 4 · IS-1)
  --Approve | Pay | Schedule | Vendor page-> NO SUCH PATH, BY RULE (BR-LED-028), not as an unbuilt feature
  --Edit after the period CLOSES----------> OQ-203 OPEN, stubbed
```
**States:** `captured → voided`. There is no `approved`, no `paid`, no `overdue` — those would be the processing BR-LED-028 forbids.

## 8. Bought-vs-billed RECONCILIATION flow (US-LED-020 — S74, J25 steps 4–5)
```
per SERVICE, per PERIOD:
  bought_volume = Σ supplier_invoices.volume  (live rows only; voided excluded)
  billed_volume = Σ invoice_lines.quantity for that service  ← published billing SELECTOR SEAM,
                    never an import of billing into the ledger read model (v5.1 law, BR-REP-002)

  ALL-OR-NOTHING GATE (BR-LED-031):
    every live purchase of that service in that period carries a volume?  ── no ──► ABSENT + reason,
                                                                                    naming the count
    units of bought and billed identical?                                ── no ──► ABSENT + reason
                                                                                    (BR-LED-033, OQ-201)
                        │ yes
                        ▼
    unaccounted_for = (bought_volume − billed_volume) ÷ bought_volume    (BR-LED-032, 2dp, basis labeled)
                        e.g. (1,000,000 − 910,000) ÷ 1,000,000 = 9.00%
                        partial denominator would read −13.75% and NEVER prints

  O&M and Infrastructure carry no volume → no denominator → no percentage, and they suppress nothing
  drill-back both ways: the row → its S73 purchases · the row → the billed lines behind it
```
⚠ The PERIOD BASIS of `billed_volume` (bills ISSUED in the period vs bills whose SERVICE PERIOD lies in it) is **OQ-202, OPEN** — issued-basis reads **11.55%** where service-period reads **9.00%** on the same month.

State machines relevant here: A5 (+ r13 #2 JE draft state; deposit-batch states = payments A5 §Batch; **`supplier_invoices` captured|voided per BR-LED-035 — a new two-value state owed to A5 at the schema route**).
