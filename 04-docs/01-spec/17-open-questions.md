# A17 — Consolidated Open Questions

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Every UNKNOWN, ranked blocking/important/deferrable.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


**Blocking**
1. Rule-engine thresholds (high/low/zero/days/estimation math) — Doc 2/7 — product+finance.
2. Rating math per tariff type incl. meter-factor order, tier boundaries, rounding — Doc 7 — finance.
3. Billed water unit (kgal vs gallons) and register-to-billed conversion — Doc 2/7 — product.
4. Money-affecting transition rules: void vs reversing entry, reversibility windows, approval gating — Doc 5/6 — finance.
5. Exact role list + full CRUD permission matrix — Doc 4 — product.
6. Timezone for all dates/timestamps — Doc 2 — product.
7. Proration formula (change plan, mid-cycle, deposit differential) — Doc 7 — finance.

**Important**
8. Bill status vocabulary (Issued/Open/Overdue/Void) and lifecycle — Doc 5.
9. Which fees are real constants vs samples (NSF $30, reconnect $45) — Doc 9 — finance.
10. Email/SMS/print/e-sign/autopay/QBO/Xero integration contracts — Doc 6/10 — product+eng.
11. Customer vs Account entity separation — Doc 3.
12. Authority & GL: global vs tenant-scoped — Doc 3 — security.
13. Multi-tenant user membership + "switch tenant" — Doc 3/4.
14. Settings sub-tab field definitions — Doc 2.
15. Exact design tokens (hex) from styles.css — Doc 11.

**Deferrable**
16. Pagination sizes / default sorts per list — Doc 7/10.
17. Empty/loading/error state designs — Doc 11.
18. User menu (S48) final scope — Doc 1.
19. Routes/Cycles tab detail — Doc 1.
20. Subscription past_due/cancel states — Doc 5.

---
*End of specification. Generated from the design prototype only; every `UNKNOWN`/`INFERRED` must be resolved by a human before implementation.*

## Scoreboard v2 — status after design v4 sync (2026-08-08)
Kept current by the PM. The original extracted list above is preserved verbatim. This scoreboard is superseded by `12-governance/01-open-questions.md` (the OQ registry) once that lands; until then it is the live view.

**Blocking (original seven)**
| # | Item | Status |
|---|---|---|
| 1 | Rule-engine thresholds + estimation math | **DERIVED-PROPOSED** — US-market defaults drafted (PM 2026-08-08); finance to ratify |
| 2 | Rating math per tariff | **PARTIAL** — B4 confirmations stand; TOU/demand depth, minimum bill, sewer %-basis, rollover now DERIVED-PROPOSED; finance to ratify |
| 3 | Billed water unit | **DERIVED-PROPOSED** — raw gallons stored, kgal billed default, per-service config |
| 4 | Money-affecting transitions | **PARTIAL** — void/reversal windows DERIVED-PROPOSED (ACH 60d / card 120d / approval gates) |
| 5 | Role list + permission matrix | **RESOLVED** — A4 addendum (3 predefined roles) |
| 6 | Timezone | **RESOLVED** — UTC storage; display per tenant Regional settings |
| 7 | Proration formula | **PARTIAL** — calendar-days confirmed; deposit differential DERIVED-PROPOSED (2× avg monthly) |

**New blocking items from v4 (r2–r9 + 2026-08-08)**
| # | Item | Status |
|---|---|---|
| 21 | Net-metering credit math (rate, rollover, true-up, cash-out) | **DERIVED-PROPOSED** — monthly kWh netting + annual true-up drafted; finance to ratify |
| 22 | Subscription-billing data model + Bynry payment provider | **DERIVED-PROPOSED** — platform tables + Stripe Billing drafted (B10 pending); eng/founder to ratify |
| 23 | Implementation-package invoicing & refund policy | **DERIVED-PROPOSED** — milestone schedule drafted; founder to ratify |
| 24 | Provisional screen IDs S49–S60 | **PROPOSED** — design session to ratify |
| 25 | Dynamic-columns pattern (IS-5) | **OPEN** — new platform requirement, needs design pattern |

**Important/deferrable:** #8 bill statuses, #9 fees, #15 tokens, #17 empty states, #18 user menu all RESOLVED (see addenda in A5/A10/A12/A18/A1); #10–14, #16, #19, #20 open; grace-days number DERIVED-PROPOSED (5 calendar days).

**Gate before billing code (wave 3):** ratification of items 1, 2-remainder, 3, 21 and the B5 golden-test freeze.
