# T6-05 — Executive operational read-only sweep (every operational mutation denied server-side; every view and export works)

---
id: T6-05
tier: 6
roles: [Executive]
gates: [BR-IDN-009, BR-IDN-014, BR-MET-035, BR-AST-032, BR-BIL-023, BR-BIL-027, BR-BIL-014, BR-PAY-014, BR-SHL-031, BR-TEN-016]
stories: [US-IDN-004, US-MET-001, US-AST-002, US-BIL-004, US-BIL-021, US-PAY-001, US-CUS-013, US-REP-002, US-REP-003]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Across the OPERATIONAL modules the Executive is view-only (A4 addendum: Premises/Accounts View · Reads & Billing View · Payments record View · Plans & Rates View · Settings View · User management none). This sweep attempts a mutation on EVERY operational surface and asserts the server refusal each time — while proving the matching VIEW and IS-9 export still work, because a view-only role that cannot see is as broken as one that can write. Scope note: the Executive's REAL powers (Finance Full, Reports Full, adjustment/write-off/reversal approvals) are deliberately out of scope here — they are proven in T6-03, T6-04 and T6-09; this file is the pure ceiling map.

**Fixture.** Tenant brazos-bend · Marcus = Executive · standard operational data present (premises P-00214, asset MTR-0512, run RUN-2607-A issued, ACC-1042 with BL-2607-0142 $97.41 — money-triples `flat,cycle,full`) · template draft v4 exists · every denial row asserts: 403-class server response · zero rows written · zero audit rows (attempt-logging not ratified, BR-AUD-001 covers EXECUTED actions; the SC-3 security-event catalog beyond ratified BR-IDN rows is pending and nothing is invented here).

| # | Actor + action (UI, then the same via API) | Allowed? / Denied? | Expected outcome | Downstream assertions | Gate |
|---|---|---|---|---|---|
| 1 | View S14 premises list + export CSV | ALLOWED (view/export) | Full render under his RLS; export = visible columns + filters | File per IS-9; no writes | A4 grid · IS-9 |
| 2 | Create/edit a premise; add a unit | DENIED | Create/edit = System Admin + Billing Clerk only | Zero premises/unit rows | BR-MET-035 |
| 3 | View S49 assets + S50 detail (reads/audit tabs render) | ALLOWED (view) | Tabs render read-only; explicit units on reads | No writes | A4 grid · BR-AST-016 |
| 4 | Register/edit/retire an asset | DENIED | Create/edit = Admin + Clerk; retire/delete = Admin — Executive holds neither | Zero asset/assignment/maintenance rows | BR-AST-032 |
| 5 | View S25 reads list | ALLOWED (view) | Renders with explicit units | No writes | A4 grid |
| 6 | Enter a manual read; upload a reads import file | DENIED | Reads = View for Executive; upload also fails the surface's role rule before BR-SHL-031 guards even run | Zero meter_reads, zero staged batches, zero stored files | A4 Reads row · BR-SHL-031 |
| 7 | View S31 run history + drill into a draft | ALLOWED (view) | Draft renders read-only | No writes | A4 grid |
| 8 | Start a bill run; exclude an account; re-rate; add a charge line; issue | DENIED (all five) | Billing runs = View; the three draft powers are Clerk/Admin powers | Zero bill_runs/exclusions/draft mutations/invoices | A4 grid · BR-BIL-023 |
| 9 | Open the correction workflow on BL-2607-0142 (create a case) | DENIED | Case CREATION is an operational billing write — view-only role refused (the Executive's ceiling on APPROVING corrections is T6-03 step 5) | Zero correction_cases rows | BR-BIL-014 · A4 grid |
| 10 | View S33 payments + S35 payment detail | ALLOWED (view) | Full render; posting/clearing dates visible (BR-PAY-021) | No writes | A4 grid |
| 11 | Record a payment; import a lockbox file; record an NSF | DENIED (all) | Payments record = View for Executive | Zero payment/batch/reversal rows | A4 Payments row |
| 12 | Edit a customer account (contact/address/status) | DENIED | Premises/Accounts = View for Executive | Zero account writes | A4 grid |
| 13 | Upload a document to an account's files | DENIED | Staff-mediated uploads follow the surface's edit right, which Executive lacks | Zero stored artifacts | BR-SHL-031 · A4 grid |
| 14 | View S9 Plans & Rates (all tabs) | ALLOWED (view) | Published + draft plans render read-only | No writes | A4 grid |
| 15 | Edit a plan / publish a draft version / edit a charge code | DENIED (all) | Change tariff = Owner/Admin only (A4 explicit); Plans & Rates = View | Zero rating writes; rate history unchanged | A4 change-tariff row |
| 16 | Edit template draft v4; test-print; publish | DENIED (all three) | Drafts + test-print = Clerk/Admin; publish = Admin; Executive = view | Zero template writes; no rendered-preview session state persisted | BR-BIL-027 |
| 17 | View Settings tabs (company, regional, reference data) | ALLOWED (view) | Settings = View for Executive — every tab renders | No writes | A4 grid (BR-IDN-014) |
| 18 | Save any Settings tab; add/edit/deactivate a lookup entry | DENIED | Edit = System Admin only; server enforces regardless of the rendered form | Zero settings/lookup writes; zero audit rows (BR-TEN-016 audits WRITES, and none happened) | A4 grid · BR-TEN-016 |
| 19 | Open Users & roles; create/edit/deactivate/remove a user | DENIED (all — including the LIST view) | User management = "—" for Executive: no access at all, not even read | Zero identity writes; membership list not served | BR-IDN-009 |
| 20 | Run any canned report + download CSV/PDF; open S61 audit viewer | ALLOWED | Reports Full + S61 (System Admin + Executive) — the Executive's read plane is fully intact after 19 denials | Files per IS-11; S61 export self-audits (BR-AUD-014); the day's denials left no trace anywhere | A4 Reports row · BR-AUD-009 |
