# EP-SHL-06 — Role-based UI gating

**Module:** platform-shell · **Wave:** W0 · **Screens:** no own S-number — gating applies across shell chrome and every screen; role matrix authored read-only in Settings → Users & roles (S8) · **Status:** draft

## Scope
**In:** the shared gating layer for the three predefined tenant roles (System Admin · Billing Clerk · Executive — A4 addendum 2026-08-07): hiding nav/modules a role cannot access (with A18 §6 on direct access), rendering visible-but-forbidden actions as **disabled-with-reason** (IS-6), and the shell-level plumbing that reads the role's permission set once and exposes it to all components. Server-side enforcement is the authority; UI gating is convenience only (IS-6, A4).
**Out:** the permission catalog and role definitions themselves (platform-level `roles`/`permissions`/`role_permissions` per B2 — identity module; roles are predefined, not tenant-editable), the Settings → Users & roles screen (tenancy/identity epics), per-action approval workflows (e.g. adjustment approval — consuming modules; void/reverse gating windows are OQ-012, payments/billing scope).

## Capability matrix (list screens only — B9 conformance)
N/A — no list screens. Row-action availability per role appears in each consuming screen's "Row actions" matrix column; the framework renders forbidden ones disabled-with-reason via this epic's layer.

## Stories

---
id: US-SHL-014
epic: EP-SHL-06
module: platform-shell
screens: [S8, S17, S33, S34, S36]
wave: 0
status: draft
blocked_by: []
depends_on: [US-SHL-001]
journeys: []
rules: [BR-SHL-003, BR-SHL-025]
golden_tests: []
finance_calc: none
---
### US-SHL-014 — Role-based UI gating with disabled-with-reason

**1 · Details** — As a staff user in any of the three roles, I want the UI to show me what I can do, grey out (with a reason) what I can see but not do, and hide what I cannot access at all, so that I neither hunt for missing features nor discover permissions by error message. Gating derives from the A4 addendum matrix: e.g. Billing Clerk — no Settings/User management/Finance, View-only Plans & Rates, Request-only on approvals; Executive — View-only operational modules, Full Finance/Reports, Approves adjustments/write-offs. Three treatments: **(a)** no access to a module → nav hidden + A18 §6 block on direct URL (BR-SHL-003, built in US-SHL-001 — referenced here for the action layer's consistency); **(b)** visible screen, forbidden action → control renders disabled with an explanatory reason (IS-6 "disabled-with-reason"), reason pattern per A18 §6 copy voice; **(c)** permitted → normal. The shell exposes one `can(permission)` facility reading the membership's `role_permissions` set (B2 identity tables) so every module gates identically. **Server-side enforcement note (normative):** every mutating endpoint re-checks the permission server-side; the UI state is never the security boundary (IS-6: "enforcement is server-side (UI gating is convenience, A4)") — a forged request from a gated user must 403 and write no data.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-SHL-003 | *(shared with US-SHL-001)* Inaccessible modules: nav hidden; direct URL → A18 §6 permission-denied block, no data behind. | CONFIRMED — A18 §6, A4 addendum |
| BR-SHL-025 | Action gating: on screens a role can view, actions the role lacks render **disabled with a reason** (never hidden — hiding actions on visible screens breeds "where did it go" tickets; never enabled-then-error); the reason names the role and the needed escalation in A18 §6 voice (pattern: "‹Role›s can't ‹action›. Ask a System Admin if you need this."); the disabled control is keyboard-focusable so the reason is reachable by assistive tech (IS-10); UI gating decisions come only from the server-provided permission set (`roles`/`role_permissions` via the current `tenant_memberships` row) — never client-side role-name string checks; and the server independently enforces every permission on every mutating call. | CONFIRMED — B9 IS-6 ("Role-forbidden actions render disabled-with-reason; enforcement is server-side"), A4 addendum matrix, A18 §6 (reason-copy pattern and focusability PROPOSED — derived from A18 §6 voice + IS-10) |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya Nair (Executive) opens S33 Record payments | Page renders (Executive: View on Payments); "Record payment", "Post adjustment", "Issue credit" header actions are disabled with reason "Executives can't record payments. Ask a System Admin if you need this." |
| TC-2 | Jordan Blake (Billing Clerk) opens S34 and selects rows for Write off | Write off opens the request path only; the approve control is disabled with reason (Clerk = Request per A4 matrix); approval controls active for Priya and Alex |
| TC-3 | Jordan's sidebar and URLs | Settings and Finance hidden; /finance and /settings show the A18 §6 block (regression of US-SHL-001 TC-4/TC-5 through the same `can()` layer) |
| TC-4 | Alex (System Admin) across S8/S17/S33/S36 | No disabled-with-reason controls anywhere (Full on all per A4 matrix) |
| TC-5 (negative — server enforcement) | Jordan crafts a direct `POST /finance/exports` (bypassing the UI) | 403; no export produced, no `audit_log` mutation beyond the denied-attempt record if the platform logs denials; response body leaks no data |
| TC-6 (negative) | A disabled action is triggered via devtools (removing the `disabled` attribute) and submitted | Server 403s; UI surfaces the A18-voice error; no write occurs — proving the UI was never the boundary |
| TC-7 (isolation) | Alex is System Admin in Silver Creek and Billing Clerk in Harbor Point | In the Harbor Point session his sidebar/actions gate as Billing Clerk (membership-scoped, not user-global); automated test asserts the permission set served per tenant context differs accordingly |

**4 · Test Data** — Silver Creek memberships: alex.reed@… → System Admin; jordan.blake@… → Billing Clerk; priya.nair@silvercreekutilities.com → Executive. Harbor Point membership: alex.reed@… → Billing Clerk. Permission codes exercised (B2 `permissions.code` style): `payments.record`, `writeoff.approve`, `finance.export`, `settings.manage`. Gated targets: S33 header actions, S34 write-off approval, `POST /finance/exports`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Current role + permission set | shell (all screens) | A4 addendum; B2 identity | `tenant_memberships.role_id` → `role_permissions` → `permissions.code` | codes | reference-data | served per tenant context; cached per session; refreshed on membership change |
| Disabled-with-reason state | gated actions | B9 IS-6 | none (derived from permission set) | — | computed-display | reason names role + escalation (A18 §6 voice); control focusable |
| Permission-denied route block | gated modules | A18 §6 | none | — | computed-display | no gated data in DOM |
| Denied-request response (pattern) | all mutating endpoints | B9 IS-6 (server-side enforcement) | none (HTTP 403; consuming module's service enforces) | — | system-derived | no partial writes on denial |

**6 · Acceptance** — Given the §4 memberships, When Priya opens S33, Then she can view the ledger but every record/adjust/credit control is disabled with the named reason; When any gated user submits the same action directly to the API, Then the server returns 403 and writes nothing; And Alex's permissions in Harbor Point are a Billing Clerk's, not a System Admin's — proven by the automated per-tenant permission-set test.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.
