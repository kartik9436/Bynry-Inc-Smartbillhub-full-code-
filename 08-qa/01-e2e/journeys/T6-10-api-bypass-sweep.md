# T6-10 — The API-bypass sweep: every T6 denial re-attempted with a raw lower-role token — the server-enforcement proof

---
id: T6-10
tier: 6
roles: [Billing Clerk, Executive, System Admin]
gates: [BR-IDN-009, BR-IDN-013, BR-IDN-014, BR-MET-035, BR-AST-032, BR-BIL-023, BR-BIL-027, BR-BIL-014, BR-CUS-038, BR-PAY-011, BR-PAY-014, BR-PAY-020, BR-PAY-019, BR-PAY-004, BR-LED-003, BR-LED-006, BR-LED-017, BR-TEN-041, BR-TEN-042, BR-AUD-009, BR-AUD-014]
stories: [US-IDN-006, US-BIL-015, US-BIL-021, US-PAY-010, US-PAY-011, US-PAY-012, US-CUS-013, US-LED-011, US-LED-015, US-LED-016, US-AUD-004, US-AUD-006]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** "User management is System Admin only; SERVER-enforced (UI gating is convenience)" — BR-IDN-009 states the doctrine once and IS-6 generalizes it to every role-forbidden action. So every denial asserted anywhere in T6-01..T6-09 through the UI is re-attempted here with NOTHING but a bearer token of the lower role against the raw API: no rendered form, no disabled button, no client-side check in the path. Expected: role gates → 403-class permission-denied (IS-7 posture); state locks → 409/422-class naming the rule (they refuse even the top role); and ZERO writes from every attempt — the single ratified attempt-audit is the self-role-change denial (US-IDN-006 TC-6). The SC-3 security-event catalog beyond ratified BR-IDN rows is pending; no other denial row is asserted or invented.

**Fixture.** Tenant brazos-bend · three raw tokens minted by real sign-ins: `TOK-CLERK` (Priya) · `TOK-EXEC` (Marcus) · `TOK-ADMIN` (Dana, the last active System Admin) · entity fixtures as staged across T6-01..09 (COR-0091 pending, REF-0027 pending, WO-0032 pending, adjustment pending, PMT-3308 cross-period, template v4 draft + v2 pinned, DEP-0642 reconciled, 2026-06 closed, first financial record exists). After the sweep, a full-diff assertion: the database is byte-identical to its pre-sweep snapshot except session/telemetry rows and the ONE ratified attempt-audit row.

| # | Token + call | Allowed? / Denied? | Expected outcome | Downstream assertions | Gate |
|---|---|---|---|---|---|
| 1 | TOK-CLERK `POST /api/users` (create user) | DENIED | 403 permission-denied | Zero identity rows | BR-IDN-009 |
| 2 | TOK-CLERK `PATCH /api/users/{priya}` role → System Admin (self-promotion) | DENIED | 403 — PLUS an audit row for the denied attempt (the one ratified attempt-audit) | Membership unchanged; audit row present | BR-IDN-009 · US-IDN-006 TC-6 |
| 3 | TOK-CLERK `PATCH /api/tenant/settings` + `PUT /api/reference-data/{list}` + `GET /api/tenant/settings` | DENIED (all three — read included) | Settings = "—" for Clerk: no read, no write | Zero writes; zero settings payload served | A4 grid (BR-IDN-014) · BR-TEN-041 |
| 4 | TOK-CLERK `POST /api/plans/{plan}/versions/{v}/publish` + `PATCH /api/plans/{plan}` | DENIED | Change tariff = Owner/Admin only | Zero rating writes | A4 change-tariff row · BR-RAT-030 |
| 5 | TOK-CLERK `PATCH /api/meters/{mtr-0512}/deactivate` + `POST /api/assets/{ast}/retire` + `DELETE /api/assets/{ast}` | DENIED (all) | Deactivate/delete = SysAdmin (metering); retire+delete = SysAdmin (assets) | Asset/meter states unchanged | BR-MET-035 · BR-AST-032 |
| 6 | TOK-CLERK `PATCH /api/bill-runs/RUN-2608-A/lines/{id} {amount: …}` (hand-edit a computed draft amount) | DENIED | 422-class: computed amounts never hand-editable (no UI path exists either — T5-19) | Draft line unchanged | BR-BIL-023 |
| 7 | TOK-CLERK `POST /api/templates/residential-bill/versions/v4/publish` | DENIED | Publish = System Admin only | Version stays draft | BR-BIL-027 |
| 8 | TOK-CLERK `POST /api/corrections/COR-0091/approve` + `/execute` | DENIED (both) | v1: all corrections approved by System Admin; no money before approval (T5-11) | Zero money-bearing rows | BR-BIL-014 |
| 9 | TOK-CLERK `POST /api/adjustments/{adj}/approve` + `PATCH …{requires_approval:false}` | DENIED (both) | Approver = SysAdmin/Executive; flag gated to Owner/Finance-mapped roles | Request still pending; flag still ON | BR-CUS-038 |
| 10 | TOK-CLERK `POST /api/write-offs/WO-0032/approve` | DENIED | Approve = SysAdmin/Executive (Finance side of BR-PAY-020) | No balance/ledger effect | BR-PAY-020 · A4 approval row |
| 11 | TOK-CLERK `POST /api/refunds/REF-0027/approve` | DENIED | Refund approval = Admin only | No execution/posting/receipt | BR-PAY-014 |
| 12 | TOK-CLERK `POST /api/payments/PMT-3308/reverse` (paid + cross-period, no approval record) | DENIED | 403 approval-required (T5-10) | Zero reversing rows | BR-PAY-011 |
| 13 | TOK-CLERK `POST /api/journal-entries` + `POST /api/periods/2026-07/close` + `POST /api/periods/2026-06/reopen` + `POST /api/exports` + `POST /api/deposit-batches/DEP-0642/unreconcile` | DENIED (all five) | The whole Finance plane is "—" for Clerk; reopen is doubly gated (SysAdmin only) | Zero ledger/period/export/batch writes | BR-LED-003 · BR-LED-006 · BR-LED-017 · BR-PAY-019/004 |
| 14 | TOK-CLERK `GET /api/audit-log` + `GET /api/audit-log/export` | DENIED (both) | S61 dataset = System Admin + Executive only | Zero rows served; zero export files | BR-AUD-009 · BR-AUD-014 |
| 15 | TOK-EXEC `POST /api/premises` + `PATCH /api/premises/P-00214` + `POST /api/assets` + `POST /api/meter-reads` + `POST /api/bill-runs` + `POST /api/payments` + `PATCH /api/accounts/ACC-1042` + `POST /api/accounts/ACC-1042/documents` (upload) | DENIED (all eight) | Executive is view-only across operational modules (T6-05 map) | Zero operational writes; zero stored artifacts | BR-MET-035 · BR-AST-032 · A4 grid · BR-SHL-031 |
| 16 | TOK-EXEC `POST /api/corrections/COR-0091/approve` + `POST /api/refunds/REF-0027/approve` + `POST /api/periods/2026-06/reopen` | DENIED (all three) | The three Admin-only rungs above the Executive seat | Case/refund still pending; period still closed | BR-BIL-014 · BR-PAY-014 · BR-LED-006 |
| 17 | TOK-EXEC `POST /api/users` + `GET /api/users` + `PATCH /api/tenant/settings` + `POST /api/templates/…/publish` | DENIED (all) | User management = no access (list included); settings view ≠ settings write; publish = Admin | Zero writes; user list not served | BR-IDN-009 · A4 grid · BR-BIL-027 |
| 18 | TOK-EXEC positive control — `POST /api/write-offs/WO-0032/approve` | ALLOWED | One deliberate allowed call proves TOK-EXEC is live and valid (the sweep's denials are gates, not a dead token) | Write-off approves exactly as in T6-04 step 9, fully audited | BR-PAY-020 |
| 19 | TOK-ADMIN state-lock trio — `PATCH /api/users/{dana}` (last-admin self-demote) + `PATCH /api/tenant/settings {currency:"CAD"}` + `DELETE /api/templates/residential-bill/versions/v2` (pinned) | DENIED (all three) | 409-class STATE locks naming their rules — the top role token proves these are not role gates: nobody crosses them (T5-26 · T5-03 · T5-02) | Admin count still 1; currency USD; v2 intact | BR-IDN-013 · BR-TEN-042 · BR-BIL-027 |
| 20 | FULL-DIFF — compare the post-sweep database to the pre-sweep snapshot | — | Identical except: session/telemetry rows, step-18's deliberate approval effects, and step-2's single ratified attempt-audit row | The sweep wrote nothing else anywhere: hidden buttons were never the security boundary — the server is | BR-IDN-009 doctrine · IS-6 |
