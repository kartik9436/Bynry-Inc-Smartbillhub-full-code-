# T4-06 — Active → Closed (the final-bill chain: move-out → immediate final bill → deposit apply → settlement)

---
id: T4-06
tier: 4
rules: [BR-CUS-030, BR-CUS-031, BR-CUS-056, BR-CUS-057, BR-BIL-013, BR-PAY-014, BR-MET-044, BR-MET-036, BR-REP-012, BR-LED-007]
stories: [US-CUS-005, US-BIL-011, US-PAY-011, US-LED-001, US-REP-008]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = Active tenancy; y = Closed (terminal per BR-CUS-055). The boundary matters because closing fires the longest ratified downstream chain in the product: final reads → immediate final bill billed THROUGH the move day (BR-CUS-056) → deposit+interest auto-applies FIRST → exactly ONE settlement path (BR-BIL-013) → ledger drains the deposit liability → unit derives Vacant keeping its plan → dunning stops → close-out documents queue → KPIs re-classify. Every link is asserted here with the frozen WE-7/LE-1 figures.

**Fixture.** Tenant brazos-bend · ACC-1042, Residential Standard · deposit **$150.00** held 14 months @ 2% simple → interest **$3.50** → deposit credit **$153.50** (WE-7) · move-out **Jul 18** with final reads committed · final charges **$142.30** (WE-7 Case A → refund path).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk runs the S20 Move-Out wizard for Jul 18: final reads committed per meter | Read lifecycle: committed final reads; `closed_at` = Jul 18; status → **Closed**; unit occupancy DERIVES Vacant (never manually set) and the unit KEEPS its plan as next-tenant prefill | audit rows; dunning stops for the account; close-out documents queued via notifications (outbound table, BR-NOT-005) | BR-CUS-030 · BR-MET-036 · BR-MET-044 |
| 2 | Final-bill handoff fires to billing (the BR-CUS-031 contract: account, move-out date, final reads, plan snapshot per service date, prior balance, deposit disposition, refund method) | Billing generates the final bill IMMEDIATELY (not at cycle time), prorated through the move day per B4.3 — the outgoing account pays the move day, an incoming same-day account would start next day from the same reading | final charges $142.30 issued as an immutable invoice; GL-stamped lines; balanced JE | BR-CUS-031 · BR-CUS-056 · BR-BIL-013 |
| 3 | Deposit settlement executes | **Deposit + interest $153.50 auto-applies FIRST** against $142.30 → excess **$11.20** → exactly ONE settlement path = refund (check/ACH, Admin approval, immutable row + receipt) | ledger: deposit-liability DR 153.50 / AR CR (LE-1 pattern); refund DR customer-credit / CR cash 11.20; deposit-liability GL for this account ends **0.00** — S36 tie-out exact, no drift | BR-BIL-013 · BR-CUS-057 · BR-PAY-014 · BR-LED-007 |
| 4 | Harness checks reports + queues after close | — | "Active accounts" KPI EXCLUDES the account (Closed excluded per BR-REP-012); "new & closed accounts" report shows the closure in period; final bill + refund receipt rows in the delivery queue; every money action audited | BR-REP-012 · BR-REP-001 |
| 5 | **INVARIANCE** — what must NOT have changed | All previously issued cycle bills byte-identical; the unit's plan assignment survives the close (prefill, not reverted); customer PII retained masked per the 7-yr window | no UPDATE touched any prior invoice/payment/JE; account status history append-only ending in the terminal Closed; reopening does not exist — a returning customer is a NEW account with deposit carry-forward per BR-CUS-024 | BR-BIL-004 · BR-CUS-065 · hard rule 4 |
