# T5-04 — Cross-tenant sweep (RLS zero-tolerance, executed against every other tier's flows)

---
id: T5-04
tier: 5
guards: [BR-AUD-007, BR-IDN-029, BR-SHL-016, NFR-10, NFR-11, NFR-30]
hard_rules: [1]
stories: [US-SHL-003, US-SHL-006, US-SHL-008, US-AUD-004, US-IDN-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
# This is the J23 isolation sweep folded into T5 (00-e2e-design.md §4): the steps below are a PARAMETERIZED
# sweep — the harness re-executes them against the fixtures of EVERY other tier (T1 J1–J6 spines, T2 feature
# journeys, T3 money-triple combinations, T4 transitions, T6 role-days, T7 config rides). Any single leak = FAIL.
---

**Intent.** Hard rule 1: no tenant table is ever touched without `app.tenant_id` set; RLS FORCE is on; there is no cross-tenant queryset — and NFR-10 makes the isolation suite a zero-tolerance RELEASE BLOCKER. This journey proves that a fully authenticated staff user of tenant A gets NOTHING of tenant B's — not a row, not an export line, not a search hit, not an audit entry, not even confirmation that B's records exist — across every read, write, export, and search surface exercised by the other tiers.

**Fixture.** Tenant A = brazos-bend (USD; account ACC-1042, bill BL-2607-0142, payment PMT-3308). Tenant B = maple-ridge (the T7 CAD sample tenant; account ACC-9001, bill BL-2607-9001). Actor: Dana, System Admin of tenant A, valid session on brazos-bend.smartbillhub.com.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Dana requests tenant B objects by direct id: `GET /api/accounts/ACC-9001`, `GET /api/bills/BL-2607-9001` (+ every entity of the tier under sweep: premises, units, assets, reads, plans, payments, JEs, notices) | RLS FORCE yields zero rows → not-found/empty posture (IS-7 empty / zero-results); never a response that confirms existence | Zero tenant-B bytes in any response body; tenant-B rows untouched | hard rule 1 · NFR-10 |
| 2 | Dana attempts WRITES against B's ids (record payment on ACC-9001, supersede a B read, post a JE with B dimensions) | Refused as not-found/zero-rows — the write target does not resolve under `app.tenant_id` = A | No row written in either tenant; tenant-B AR, ledger, queues byte-identical; A's audit gets no money row (nothing executed — BR-AUD-001 scope) | hard rule 1 · NFR-10 |
| 3 | Dana runs global search (US-SHL-003) for "ACC-9001" and B's customer name | IS-7 zero-results state | Search index/query is tenant-scoped; no hit, no count leak | hard rule 1 · NFR-30 |
| 4 | Dana exports CSVs from every list of the tier under sweep (bills S30, payments S33, reads S25, audit S61) | Export streams server-side under RLS per IS-9 — file contains ONLY tenant-A rows | Row counts equal A-only counts; money-table exports write audit_log (tenant A, BR-SHL-016) | BR-SHL-016 · hard rule 1 |
| 5 | Dana opens the audit viewer (S61) and entity Audit tabs hunting for tenant-B events; a platform-support operator tries the same | Tenant-scoped-only, NO cross-tenant view even for support | Zero B events rendered anywhere; BR-AUD-007 RLS FORCE on audit_log holds | BR-AUD-007 |
| 6 | Dana's email also exists as a user in tenant B (same address, separate user per BR-IDN-029); she presents her tenant-A password on maple-ridge.smartbillhub.com | Sign-in resolves the tenant from the subdomain FIRST; (tenant-B, email) credentials fail → invalid-credentials posture; her A session token is worthless on B's subdomain | Two separate user rows remain separate; no session created on B; failed attempt feeds B's lockout counter only | BR-IDN-029 · NFR-11 |
| 7 | SWEEP EXECUTION — the harness re-runs steps 1–6 parameterized over every T1–T3 flow (and T4/T6/T7 fixtures): each journey's endpoints called with a foreign-tenant session | Every probe returns the step-1..6 postures; ONE leak anywhere fails the suite | Release pipeline blocks on any failure (NFR-10 zero-tolerance = release blocker) | NFR-10 |
| 8 | RECOVERY — the correct path: operate on your OWN subdomain against your own tenant's data; cross-tenant support access does not exist in v1 | Dana performs the same actions on brazos-bend data; all succeed under normal role gates | Normal handoff contracts (J1–J6) hold; audit rows written in tenant A | hard rule 1 · BR-AUD-007 |
