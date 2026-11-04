# J18 — Returned-mail Tuesday (bulk mark ×14 → needs-attention workdown)

---
id: J18
tier: 2
rules: [BR-PAY-018, BR-NOT-005, BR-REP-007, BR-REP-015, BR-BIL-001]
stories: [US-PAY-016, US-NOT-014, US-REP-009, US-REP-017]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The chore journey — BR-PAY-018's own words: "a returned-mail stack is a Tuesday chore." Fourteen envelopes come back from the Sep 1 run; bulk-mark turns them into fourteen flagged accounts in one action, the needs-attention queue drives the workdown, and the one thing that must NOT happen — money behavior changing because the post office failed — is asserted at every step.

**Fixture.** Tenant brazos-bend · **Tuesday Sep 8, 2026** · 14 returned envelopes from the Sep 1 cycle (14 distinct accounts) · workdown outcome: 9 addresses corrected · 3 verified-current (mail carrier error) · 2 unresolved, stay flagged.

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Sep 8 09:00** — S35 **bulk-mark returned ×14** (single action over the stack) | 14 delivery records → status returned; 14 accounts flagged **bad-address**; paper suppressed on all 14 until verified (config); needs-attention queue gains 14 rows | S32 returned-mail chip = 14 (BR-REP-015); one audit row per account (who/when), plus the bulk action itself audited | **BR-PAY-018** |
| 2 | **Sep 8 09:05** — money-invariance probe before any workdown | — | All 14 balances, due dates, aging buckets and late-fee eligibility BYTE-IDENTICAL to Sep 8 08:00 — "balances continue normally"; dunning ladder positions unchanged; late fees still assess per BR-BIL-001 on schedule | BR-PAY-018 |
| 3 | **Sep 8 10:00–15:00** — workdown from the queue: phone calls; **9 addresses corrected + verified** → flags clear, suppression lifts; held documents re-queue to the fixed addresses | 9 clean accounts; their queued paper dispatches (BR-NOT-005) | Chip 14 → 5; per-account audit rows for edit + verify + clear; address history append-only | BR-PAY-018 |
| 4 | **Sep 8 15:30** — **3 verified-current** (address was right; carrier error) → flag cleared with reason, no address change | 3 clean accounts, reason-coded clears | Chip 5 → 2; reason recorded per clear; audit | BR-PAY-018 |
| 5 | **Sep 8 17:00** — **2 unresolved**: remain flagged, paper stays suppressed, rows stay in the queue with aging | 2 open needs-attention rows that will age visibly — the queue never silently drops them | Returned-mail report shows the day: 14 marked / 12 cleared / 2 open (US-REP-009, BR-REP-007); chip = 2 at close of day | BR-PAY-018 · BR-REP-015 |
| 6 | **INVARIANCE** — zero money rows written or changed by the entire day's work; the 14 bill documents themselves untouched (returned ≠ reissued); flag/clear history reconstructs the whole Tuesday per account | — | No invoice/payment/JE row created or altered; queue + audit trails complete (hard rule 7); tie-outs hold (BR-LED-007) | hard rule 4 · BR-PAY-018 |

**Build state (2026-08-16, returned-mail surface lane).** **Step 1 has a screen now** — it did not
this morning, which is why this journey could not run at all. Step 1's bulk mark opens from the
returned-mail chip on S32; the SINGLE mark §1 also names lives on S30's delivery rows. Both are
`07-frontend/src/features/payments/returnedMail.tsx`; the write is `POST /deliveries/returned`.

**Step 2's invariance probe is ASSERTED, not assumed:** `06-backend/tests/test_us_pay_016_surface.py`
counts `invoices`, `invoice_lines`, `payments` and `journal_lines` either side of a fourteen-piece
bulk mark and fails on any movement, and the endpoint answers `balances_affected: false` which the
screen prints rather than paraphrases.

**Steps 3, 4 and 5 are NOT automated yet and the reason is a rule, not a gap:** the workdown
resolves through `returned_mail.resolve_return` (built, tested) but its SCREEN is the S21 account
banner's clear action, which is customers-owned and unbuilt — and the *"held documents re-queue"*
half of step 3 needs a dispatcher, which is out of this release by PO ruling (US-NOT-002). Step 5's
chip figures are live today; step 3's release is not, and nothing on any screen claims it is.

**What a browser proves today** (`07-frontend/e2e/US-PAY-016-returned-mail.spec.ts`, 20 assertions
against a real Django and Postgres): an envelope is marked from the bill's own delivery row, the
date the CLERK typed comes back on the row, the second mark on the same envelope is refused by
name, and the bulk stack lists ONLY the post still to work.
