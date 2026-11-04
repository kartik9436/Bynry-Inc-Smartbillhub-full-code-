# J6 — Corrections
wrong bill → credit note/rebill → reversing entries → customer notice.
| # | Story | Handoff |
|---|---|---|
| 1 | US-BIL-** correction (wave 5) | original invoice UNTOUCHED; credit note references it (GT-6) |
| 2 | US-LED-** reversing entries 🔒 | balanced reversal, period rules per BR-TEN-038 |
| 3 | US-PAY-** reapply/refund | allocations rebuilt per BR-PAY-010; consequence messaging (BR-PAY-011) |

**Amended 2026-08-11 (PO correction statement → BR-BIL-041, PROPOSED).** The three rows above are the **class-R restatement** path and are correct for it. They are NOT the whole journey, and reading them as such is what would produce a credit note for a misspelt name:
- **class R** (wrong read · wrong rate/plan · wrong tax · missed charge · wrong period · theft-restated) — rows 1–3 exactly as written: credit note + rebill, ledger reversal, payment re-allocation.
- **class C** (goodwill/concession — the bill is RIGHT) — row 1 emits a **partial credit note and no rebill** (GT-6: $247.30 invoice, $25 credit, balance 222.30); row 2 posts, but **which account it debits is OQ-105**; row 3 applies.
- **class D** (name · address · premises label · template/language) — **rows 2 and 3 do not happen at all.** No journal entry, no allocation change, balance delta exactly $0.00. The journey ends at a reissued document (US-BIL-031, blocked by OQ-103) and never leaves billing.

Bulk is **J11**, unchanged in shape; its aggregate and partial-failure contract is BR-BIL-046/047 (US-BIL-016 §1a/§1b).
