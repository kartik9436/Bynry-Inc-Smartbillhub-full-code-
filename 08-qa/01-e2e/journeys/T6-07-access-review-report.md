# T6-07 — Quarterly access-review report (SC-2): users · roles · last sign-in, exportable per IS-11

---
id: T6-07
tier: 6
roles: [System Admin, Executive]
gates: [BR-IDN-010, BR-IDN-014, BR-AUD-014]
stories: [US-REP-001, US-REP-002, US-REP-003, US-REP-013, US-REP-014, US-IDN-004]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** SC-2 is CONFIRMED in the compliance battery (soc2-nist-mapping: "Periodic access reviews — COVERED: quarterly access-review report v1 (users, roles, last sign-in, exportable per IS-11)"). This journey proves the report renders exactly its three ratified data facets from the identity tables, matches the Users & roles surface it reviews, exports under the IS-11 contract, and can be SCHEDULED quarterly so the review actually happens. Ratified content = users · roles · last sign-in — nothing beyond that is asserted (no invented columns).

**Fixture.** Tenant brazos-bend · Dana = System Admin · Marcus = Executive · Priya = Billing Clerk · Tom = Billing Clerk, DEACTIVATED yesterday (T6-06 step 9 state) with a role-change + deactivation audit history · last sign-ins staggered across the quarter (Dana today · Marcus −2d · Priya −1d · Tom −9d, before deactivation).

| # | Actor + action | Allowed? / Denied? | Expected outcome | Downstream assertions | Gate |
|---|---|---|---|---|---|
| 1 | Dana opens the report library (S44), Compliance group → Access review, runs it for the current quarter | ALLOWED (Reports Full) | One row per current-tenant membership: user · role (one of the 3 predefined) · last sign-in (tenant TZ per IS-8) | Row set = exactly the S8 Users & roles tab's membership list (BR-IDN-010: current-tenant memberships only; platform `users` never exposed cross-tenant); roles render from the platform catalog vocabulary (BR-IDN-014) | SC-2 · BR-IDN-010 |
| 2 | Dana cross-checks against S8 Users & roles side by side | ALLOWED | Report and screen agree user-for-user, role-for-role — the review reviews reality | Priya shows role Billing Clerk (current state post-T6-06 demotion); role-change HISTORY is not a report claim — it lives in audit (`user.role_changed`, S61) | SC-2 · BR-IDN-014 |
| 3 | Dana checks Tom's row | ALLOWED | Tom's last sign-in (−9d) renders; his sign-in ability is dead (deactivated) — exactly the stale-access signal a quarterly review exists to catch | Last sign-in sourced from session records (BR-IDN-006 server-side sessions); no invented "status" columns asserted beyond the three ratified facets | SC-2 · BR-IDN-012 |
| 4 | Dana downloads CSV, then PDF (compliance report → formatted layout warranted) | ALLOWED | IS-11 contract: CSV UTF-8, ONE header row, stable snake_case columns, ISO dates, tenant-TZ timestamps w/ offset, no metadata rows, filename `{tenant}_{report}_{period}_{basis}_{generated}.csv`; PDF skeleton with letterhead · period · filters echoed · generated-at + by whom · page X/Y | Files stream under Dana's RLS, 50k cap (BR-SHL-016 guard set); generation recorded per the US-REP-003 guard/audit set | IS-11 · BR-AUD-014 (guard family) |
| 5 | Marcus (Executive) runs the same report + export | ALLOWED | Reports = Full for Executive; the reviewer role most likely to sign the quarterly review can produce it independently | Same row set under his own RLS session; same IS-11 files | SC-2 · A4 Reports row |
| 6 | Dana schedules it QUARTERLY (US-REP-013: cadence, IS-11 formats CSV+PDF, recipients) | ALLOWED | Schedule row with next-run computed; scheduled execution produces IDENTICAL files (US-REP-014) | Generated files retained 3 days default, tenant-config (NFR-9); email delivery of the file rides the outbound queue when W6 lands (US-REP-015 — rows written now, dispatch later) | SC-2 · IS-11 |
| 7 | ISOLATION — the report NEVER includes another tenant's memberships | ALLOWED (assertion) | Per-tenant identity (BR-IDN-029): a same-email user in another tenant is a DIFFERENT user and never appears | Automated assert: no foreign tenant membership id in any run/export permutation (RLS) | BR-IDN-010 · BR-IDN-029 |

**Note (reported, not asserted):** whether Billing Clerk's "Reports: Run" right extends to THIS report is unratified — the access-review dataset is user-management data, which the Clerk role cannot otherwise see (BR-IDN-009). No Clerk step appears above; the question is flagged to the PO in the pack report rather than decided here.
