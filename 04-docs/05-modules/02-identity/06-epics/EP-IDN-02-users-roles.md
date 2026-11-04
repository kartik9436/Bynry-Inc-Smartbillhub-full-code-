# EP-IDN-02 — Users & Roles

> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** identity · **Wave:** W0 · **Screens:** S8 (Settings → Users & roles tab) · **Status:** draft

## Scope
**In:** the Users & roles tab of Settings (S8): tenant-scoped user list, the add-a-user modal (reworked to **admin-set temporary passwords shown once on screen — no invite emails in v1**, BR-IDN-021/022), per-row actions (Edit role · Deactivate · Remove · **Reset temp password** — was "Resend invite"), first-sign-in activation via forced password change, and the read-only **Roles & permissions** matrix. Roles are the 3 predefined platform roles — System Admin / Billing Clerk / Executive (A4 addendum, settles O-5); **not tenant-editable**; new roles are provisioned by the platform provider (prototype copy).
**Out:** authentication (EP-IDN-01) · self-service profile/password (EP-IDN-03) · Security tab (EP-IDN-04) · role/permission catalog administration (platform/backend, no tenant UI) · SSO-based provisioning (B7 seam) · invite/verification emails (v2 — BR-IDN-021).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S8 · Users & roles | — (none in design; lists are 1–2 dozen users) | — (none in design) | Last active desc (prototype row order: Just now → 2 h → 3 d → Never) | Name, Email, Role, Last active, Status (IS-2) | default = available: Name · Email · Role · Last active · Status · Actions (no column chooser in design) | Active: Edit role · Deactivate · Remove — Invited: Reset temp password (was Resend invite — BR-IDN-021/022) · Edit role · Remove — Deactivated: Reactivate · Remove *(PROPOSED — state not shown in prototype; per IS-1)* | — | — |

## Stories

---
id: US-IDN-004
epic: EP-IDN-02
module: identity
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-001, US-SHL-006]
journeys: []
rules: [BR-IDN-008, BR-IDN-009, BR-IDN-010]
golden_tests: []
finance_calc: none
---
### US-IDN-004 — Tenant user list

**1 · Details** — As a System Admin, I want to see everyone who can access my utility — name, email, role, last active, status — so that I can manage my team's access from one place. Entry: Settings (S8) → **Users & roles** tab (second tab per A1 r7 tab order). Header copy: "Three predefined roles. New roles are provisioned by your platform provider." with **View roles & permissions** and **+ Invite user** buttons. Exit: row-action modals (US-IDN-005/006/007). The list renders the current tenant's users (tenant-scoped per BR-IDN-029, B2 r11) with their `roles` — a cross-tenant user list does not exist.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-009 | User management is System Admin only; Billing Clerk and Executive have no access (A4 matrix "User management: — / —"); enforcement is server-side, UI gating is convenience (IS-6). | CONFIRMED — A4 addendum 2026-08-07 |
| BR-IDN-010 | A user's presence in a tenant is exactly one tenant-scoped user row carrying the role (as-reworked by BR-IDN-029 + B2 r11: users are PER-TENANT, `UNIQUE(tenant_id, email)`; the same email in another tenant is a different user); the list shows only the current tenant's users. | CONFIRMED — as-reworked by BR-IDN-029 (B2 r11) |
| BR-IDN-008 | Roles shown are exactly the 3 predefined platform roles; no tenant role CRUD anywhere. | CONFIRMED — A4 addendum 2026-08-07 (settles O-5) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex opens Settings → Users & roles at Silver Creek | 5 rows (4 active/invited from prototype set + Carla deactivated); invited Marcus shows Name "—", Last active "Never", Status pill "Invited"; sorted Last active desc |
| TC-2 | List conformance | Server-side pagination per IS-2 (25/page default); header-click sort on declared columns with stable secondary sort by id |
| TC-3 *(negative)* | Priya (Billing Clerk) requests the tab / `GET` users endpoint | Permission-denied state (IS-7 / A18); server returns 403 regardless of UI |
| TC-4 *(negative)* | Diana (Executive) requests the same | 403 — Executive has "—" on user management (A4), unlike her View on other settings |
| TC-5 *(isolation)* | Jordan (Blue Mesa System Admin) lists users at `bluemesa` | Only Blue Mesa memberships returned; no Silver Creek member visible; RLS on `tenant_memberships` enforces even if app filter fails |
| TC-6 *(isolation)* | The email `marcus@silvercreek.example` exists in both tenants (two separate users, BR-IDN-029) | Silver Creek list shows its Marcus as Invited · Billing Clerk; Blue Mesa list shows its Marcus as Active · System Admin — two tenant-scoped user rows, no linkage or leakage between them |

**4 · Test Data**
Silver Creek memberships: Alex Reed `alex@silvercreek.example` System Admin · Active · just now — Priya Menon `priya@silvercreek.example` Billing Clerk · Active · 2 h ago — Diana Chen `diana@silvercreek.example` Executive · Active · 3 d ago — (—) `marcus@silvercreek.example` Billing Clerk · Invited · never — Carla Ortiz `carla@silvercreek.example` Billing Clerk · Deactivated · 30 d ago.
Blue Mesa memberships: Jordan Ellis `jordan@bluemesa.example` System Admin · Active — Marcus Webb `marcus@silvercreek.example` System Admin · Active.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Name | S8 | prototype-extracted | `users.full_name` ("—" while invited) | text | reference-data | — |
| Email | S8 | prototype-extracted | `users.email` | citext | reference-data | — |
| Role | S8 | prototype-extracted | `roles.name` via `tenant_memberships.role_id` | text | reference-data | one of 3 |
| Last active | S8 | prototype-extracted ("Just now", "2 hours ago", "Never") | **PROPOSED-SCHEMA** `tenant_memberships.last_active_at` (per-tenant, touched on session activity) | timestamptz | system-derived | null = "Never" |
| Status | S8 | prototype-extracted (pills Active / Invited) | **PROPOSED-SCHEMA** `tenant_memberships.status` enum invited\|active\|deactivated | enum | system-derived | invited = temp password not yet changed (BR-IDN-011 as-reworked) |
| Actions | S8 | prototype-extracted (per-row select) | — (dispatch to US-IDN-005/006/007) | — | user-input | options vary by row status (IS-6) |

**6 · Acceptance**
- Given a System Admin at their tenant, When they open Users & roles, Then every membership of that tenant (and only that tenant) is listed with name/email/role/last-active/status, sorted last-active desc.
- Given a Billing Clerk or Executive, When they attempt the tab or its API, Then they get a permission-denied state and a server-side 403.
- Given the same email existing in two tenants (two separate users, BR-IDN-029), When each tenant's admin lists users, Then each sees only their own tenant's user row.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-IDN-005
epic: EP-IDN-02
module: identity
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-IDN-002, US-IDN-004, US-IDN-010]
journeys: []
rules: [BR-IDN-005, BR-IDN-008, BR-IDN-009, BR-IDN-010, BR-IDN-011, BR-IDN-021, BR-IDN-022, BR-IDN-025]
golden_tests: []
finance_calc: none
---
### US-IDN-005 — Add a user (admin-set temporary password — no-email v1)

**1 · Details** — As a System Admin, I want to add a teammate with a role and hand them a temporary password, so that they can sign in and start working — **v1 sends no staff auth emails** (BR-IDN-021; OQ-028 closed). Entry: **+ Invite user** on the Users & roles tab → modal (reworked from the prototype's email-invite copy): **Name**, **Email** (the sign-in identifier within this tenant — BR-IDN-017/029; no mail is sent), **Role** select (System Admin / Billing Clerk / Executive), system-generated **temporary password shown once on screen** (BR-IDN-022; replaces the prototype's "Send invitation email now" checkbox), **Create user ✓** / Cancel. Exit: confirmation toast (A1 addendum: all Settings modals fire one); list shows the new row as **Invited** — `invited` = temp password not yet changed (BR-IDN-011 as-reworked, R1 reconciliation). Row action **Reset temp password** (was "Resend invite") regenerates and re-displays a temp password, voiding the prior one. Activation: first sign-in forces a policy-compliant password change (US-IDN-002 flow); the membership then flips to `active`.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-022 | User creation v1: the System Admin sets (or the system generates) a temporary password shown once on screen; the user must change it at first sign-in. | CONFIRMED — PO Q&A R4 |
| BR-IDN-011 | `invited` = temp password not yet changed (Name renders "—" per prototype until first sign-in); the membership activates at the user's first sign-in after the forced change; **Reset temp password** voids the prior temp password. | CONFIRMED-REWORKED — R1 reconciliation |
| BR-IDN-021 | No invite emails in v1; email verification is v2. | CONFIRMED — PO Q&A R2 (closes OQ-028) |
| BR-IDN-025 | Temp passwords are valid 7 days; failed sign-ins lock after **5 attempts for 15 minutes**. | CONFIRMED — PO Q&A R4 (closes OQ-025) |
| BR-IDN-010 | As-reworked by BR-IDN-029 (B2 r11): an email that exists in ANOTHER tenant belongs to a different user there — adding it here creates a NEW tenant-scoped user with its own temp password, touching nothing elsewhere; a second add of an email already in THIS tenant is rejected (B2 `UNIQUE(tenant_id, email)`). | CONFIRMED — as-reworked by BR-IDN-029 |
| BR-IDN-005 | (as-reworked R2, no-email) No invite links/tokens in v1 — the 7-day temp password replaces them. | CONFIRMED-REWORKED — identity rules BR-IDN-005 |
| BR-IDN-009 / BR-IDN-008 | System Admin only; role options limited to the 3 predefined roles. | CONFIRMED — A4 addendum |

*Cross-tenant email case (as-reworked by BR-IDN-029): the same email in another tenant is a separate user — the add here ALWAYS creates a fresh tenant-scoped user with its own temp password; the other tenant's user, password, and sessions are never touched.*

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex creates Tom Nguyen `tom@silvercreek.example` as Billing Clerk | Tenant-scoped `users` row created (BR-IDN-029); temp password `Tq4v-Xm92-Lpr7` displayed exactly once to Alex — **no email sent** (BR-IDN-021); `must_change_password` set, expiry +7 days; membership `invited` with role; toast; `audit_log` row `user.invited` |
| TC-2 | Alex adds `jordan@bluemesa.example` as Executive | A NEW Silver Creek user row is created (BR-IDN-029 — the Blue Mesa Jordan is a different user); its own temp password is displayed once; Blue Mesa's user, password, and sessions untouched; the Silver Creek user flips `active` at first Silver Creek sign-in after the forced change |
| TC-3 *(negative)* | Alex adds `priya@silvercreek.example` (already an active member) | Rejected with "already a member" error; no duplicate membership (unique constraint) |
| TC-4 *(negative)* | Email `not-an-email` submitted | Inline validation error (IS-7); nothing created |
| TC-5 | **Reset temp password** on Marcus's row | New temp password generated + shown once on screen; the previous temp password is void immediately; no email; audit row `user.temp_password_reset` |
| TC-6 | Tom signs in with his temp password on day 3 and sets `Willow2026brook` at the forced-change screen | Password stored; `must_change_password` cleared; membership → `active`; row shows his name instead of "—"; audit `auth.password_reset` |
| TC-7 *(negative)* | Tom's original temp password tried after a TC-5-style reset (voided), or any temp password tried on day 8 (expired, BR-IDN-025) | Generic sign-in error (BR-IDN-002); no session; no change |
| TC-8 *(negative)* | Diana (Executive) calls the create-user endpoint directly | 403 server-side |
| TC-9 *(isolation)* | After TC-1, Jordan lists Blue Mesa users | Tom does not appear; the row exists only as a Silver Creek membership |
| TC-10 *(negative)* | 5 consecutive wrong temp-password attempts for Tom, then a 6th with the correct value | 6th attempt refused — **15-minute lock after 5 failures** (BR-IDN-025); generic error throughout; audit `auth.lockout` |

**4 · Test Data** — Invitees: Tom Nguyen `tom@silvercreek.example` (new platform user) · Jordan Ellis `jordan@bluemesa.example` (same email already exists at Blue Mesa — a separate user there, BR-IDN-029). Temp passwords (system-generated, shown once): Tom `Tq4v-Xm92-Lpr7` (issued Aug 8, 2026 → expires Aug 15, 2026, BR-IDN-025); Marcus reset value `Zn6h-Wc31-Qkd8`. Password set at activation: `Willow2026brook`. Silver Creek policy: min 8, upper/lower/number. Roles select: exactly the 3 predefined. Lockout: 5 failed → 15-min lock (BR-IDN-025).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Name | S8 add-user modal | prototype-extracted | `users.full_name` | text | user-input | required |
| Email | S8 add-user modal | prototype-extracted (identifier only — no mail sent, BR-IDN-021) | `users.email` (unique per tenant — BR-IDN-029) | citext | user-input | email format; not already a user of THIS tenant (same email may exist in other tenants as a different user) |
| Role | S8 add-user modal | prototype-extracted (3 options) | `tenant_memberships.role_id` → `roles` | uuid | user-input | one of 3 predefined |
| Temporary password (shown once) | S8 add-user modal (rework — prototype's "Send invitation email now" checkbox removed per BR-IDN-021/022) | BR-IDN-022 | `users.password_hash` (temp value) + **PROPOSED-SCHEMA** `users.must_change_password`, `users.temp_password_expires_at` | text (never stored raw) | system-derived | 7-day validity (BR-IDN-025); displayed once, never retrievable |
| Invite status / audit | S8 list | prototype-extracted | **PROPOSED-SCHEMA** `tenant_memberships.status`, `tenant_memberships.invited_at`, `tenant_memberships.invited_by` (uuid → users) | enum / timestamptz / uuid | system-derived | invited = temp password not yet changed (BR-IDN-011) |

**6 · Acceptance**
- Given a System Admin, When they create a user, Then an `invited` membership with the chosen role exists, a temporary password is displayed exactly once on screen, and no email is sent (BR-IDN-021/022).
- Given the new user signs in with an unexpired temp password and completes the forced change with a policy-compliant password, Then their membership becomes `active` and their row shows their name instead of "—".
- Given an email already belonging to this tenant, When submitted again, Then it is rejected with a clear error and no data changes.

**7 · Finance Calculation** — N/A

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-025 | Invite token lifetime (with policy defaults) | — (resolved) | Product Owner (chat session) | **CLOSED(→BR-IDN-025)** — temp password 7 days; lockout 5 → 15 min (PO Q&A R4) |
| OQ-028 | Sender for invite emails (platform sender vs tenant BYO mailbox) | — (resolved; story unblocked) | Product Owner (chat session) | **CLOSED(→BR-IDN-021..023)** — no staff auth emails v1; admin temp passwords shown on screen (PO Q&A R2) |

---
id: US-IDN-006
epic: EP-IDN-02
module: identity
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-IDN-003, US-IDN-004]
journeys: []
rules: [BR-IDN-008, BR-IDN-009, BR-IDN-012, BR-IDN-013]
golden_tests: []
finance_calc: none
---
### US-IDN-006 — Edit role · deactivate · reactivate

**1 · Details** — As a System Admin, I want to change a teammate's role or switch off their access without deleting their history, so that access always matches responsibilities. Entry: row actions **Edit role** (all rows) and **Deactivate** (active rows) on the Users & roles tab; **Reactivate** on deactivated rows (PROPOSED — state not rendered in prototype; implied by IS-1 deactivate-first). Edit role opens a modal with the 3-role select; Deactivate is a destructive action → confirm modal → toast → audit (IS-6). Exit: list refreshes with the new role/status.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-012 | Deactivate-first (IS-1): deactivation immediately blocks sign-in for that tenant and revokes that tenant's sessions for the user; the membership row and all history are kept. | CONFIRMED — PO R1-B12 |
| BR-IDN-013 | A tenant always retains ≥ 1 active System Admin: the last one cannot be demoted or deactivated (or removed — US-IDN-007). | CONFIRMED — PO R1-A4 |
| BR-IDN-009 | System Admin only; server-enforced. | CONFIRMED — A4 addendum |
| BR-IDN-008 | Role change chooses among the 3 predefined roles only. | CONFIRMED — A4 addendum |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex changes Priya: Billing Clerk → Executive | Membership `role_id` updated; Priya's next request carries Executive permissions (e.g. Finance now full, record-payment now view-only per A4); `audit_log` row `user.role_changed` with before/after |
| TC-2 | Alex deactivates Priya (confirm modal → confirm) | Status → `deactivated`; her active sessions at Silver Creek revoked at once (in-flight request → 401); sign-in denied per US-IDN-001/TC-4; toast + audit row `user.deactivated` |
| TC-3 | Alex reactivates Carla | Status → `active`; she can sign in again with her existing password; audit row `user.reactivated` |
| TC-4 *(negative)* | Alex is the only active System Admin; he tries to demote himself to Billing Clerk | Blocked with reason "a tenant needs at least one active System Admin" (disabled-with-reason per IS-6 and server-side 409/422) |
| TC-5 *(negative)* | Same guard on Deactivate for the last active System Admin | Blocked with the same reason |
| TC-6 *(negative)* | Priya (Billing Clerk) calls the role-change endpoint for her own membership → System Admin | 403 server-side; audit row for the denied attempt |
| TC-7 *(isolation)* | Jordan (Blue Mesa) calls edit-role/deactivate with the id of Priya's Silver Creek membership | 404 — the row is invisible under Blue Mesa's `app.tenant_id` (RLS); nothing changes |
| TC-8 *(isolation)* | Alex deactivates Marcus at Silver Creek | Only the Silver Creek membership is deactivated; Marcus's Blue Mesa membership and sessions unaffected |

**4 · Test Data** — Membership set from US-IDN-004. Second active System Admin case: promote Diana first when a test needs Alex demotable. Session fixtures: Priya holds 2 active Silver Creek sessions (desktop + laptop) before TC-2.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Role (edit modal) | S8 | prototype-extracted (row action "Edit role") | `tenant_memberships.role_id` | uuid → `roles` | user-input | one of 3; last-admin guard |
| Status transitions | S8 | prototype-extracted ("Deactivate"); Reactivate GAP/PROPOSED | **PROPOSED-SCHEMA** `tenant_memberships.status` | enum | user-input → system-derived | active↔deactivated; last-admin guard |
| Session revocation on deactivate | — | BR-IDN-012 | **PROPOSED-SCHEMA** `sessions.revoked_at` (rows where user+tenant match) | timestamptz | system-derived | tenant-scoped revocation |
| Audit rows | — | S8 Security panel copy | `audit_log` (`user.role_changed` / `user.deactivated` / `user.reactivated`, before/after jsonb) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an active member, When their role is changed, Then the new permissions apply to their very next request and an audit row records before/after.
- Given an active member with live sessions, When deactivated, Then those sessions die immediately, sign-in is refused, and the row remains visible as Deactivated.
- Given the last active System Admin, When demotion/deactivation is attempted, Then it is refused with an explicit reason.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-IDN-007
epic: EP-IDN-02
module: identity
screens: [S8]
wave: 0
status: draft
blocked_by: []
depends_on: [US-IDN-004, US-IDN-005]
journeys: []
rules: [BR-IDN-008, BR-IDN-009, BR-IDN-012, BR-IDN-013, BR-IDN-014]
golden_tests: []
finance_calc: none
---
### US-IDN-007 — Remove a user · read-only roles & permissions matrix

**1 · Details** — As a System Admin, I want to remove someone who should no longer appear in my team list (typically a never-activated add or a departed employee with no history), and I want to review exactly what each role can do, so that access decisions are transparent. Entry: row action **Remove** (all row states in prototype) with confirm modal → toast → audit; and the **View roles & permissions** button, which toggles an inline read-only matrix titled "Roles & permissions (predefined · read-only)" — 9 permission rows × 3 role columns, exactly the A4 addendum grid. Exit: list refreshes; matrix collapses on second click.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-IDN-012 | Remove deletes only the tenant membership — never the platform `users` row; it is blocked (🔒 audit-lock, IS-1) when the member is referenced by tenant records (`meter_reads.imported_by`, `bill_runs.run_by`, `tariff_versions.approved_by`, `adjustments.approved_by`, `audit_log.actor_user_id`, …) — deactivate instead. | CONFIRMED — PO R1-B12 (IS-1 delete-deactivate pattern) |
| BR-IDN-014 | The matrix is read-only, rendered from the `roles` / `permissions` / `role_permissions` catalog, and must match the A4 addendum grid verbatim (9 rows: Settings & lookup tables · User management · Plans & Rates · Premises/Accounts · Reads & Billing runs · Payments (record) · Adjustment/write-off approval · Finance/reconcile/export · Reports). | CONFIRMED — A4 addendum 2026-08-07 |
| BR-IDN-013 | The last active System Admin cannot be removed. | CONFIRMED — PO R1-A4 (with US-IDN-006) |
| BR-IDN-009 / BR-IDN-008 | System Admin only; roles are platform-defined. | CONFIRMED — A4 addendum |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex removes invited Marcus (never signed in, zero activity) | Silver Creek membership row deleted; his pending temp password voided (BR-IDN-011 as-reworked); toast; audit row `user.removed`; Marcus's platform `users` row and Blue Mesa membership untouched |
| TC-2 *(negative)* | Alex removes Priya, who has imported reads and recorded payments | Blocked with audit-lock reason ("referenced by N records — deactivate instead", 🔒 per IS-1); no change |
| TC-3 | Alex opens View roles & permissions | Matrix renders exactly the A4 addendum grid — spot-check: User management row = Full / — / —; Adjustment/write-off approval = Approve / Request / Approve |
| TC-4 *(negative)* | Any write against the roles/permissions catalog from the tenant app (e.g. PATCH a role name) | 403/405 — no tenant-facing mutation endpoint exists; matrix has no edit affordance |
| TC-5 *(negative)* | Alex attempts to remove himself as last active System Admin | Blocked with the BR-IDN-013 reason |
| TC-6 *(isolation)* | Jordan (Blue Mesa) calls remove with the id of Marcus's **Silver Creek** membership | 404 under Blue Mesa's `app.tenant_id` (RLS); the Silver Creek membership survives |

**4 · Test Data** — Membership set from US-IDN-004. Activity fixtures for TC-2: Priya has 3 `meter_reads` rows with `imported_by = priya`, 1 `bill_runs.run_by`, 12 `audit_log` actor rows. Marcus (Silver Creek): zero references. Matrix expectation = the 9×3 grid in A4 addendum (single source; not copied here).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Remove (row action) | S8 | prototype-extracted | DELETE on `tenant_memberships` row | — | user-input | audit-lock when referenced (BR-IDN-012); last-admin guard |
| Reference count (audit-lock) | S8 confirm modal | IS-1 "Used-by" pattern | computed across referencing tables (read-only service query) | integer | computed-display | ≥1 ⇒ block hard delete |
| Matrix — permission rows | S8 | prototype-extracted + A4 addendum | `permissions.code`, `permissions.description` | text | reference-data | platform catalog, no RLS (B2) |
| Matrix — role columns/cells | S8 | prototype-extracted + A4 addendum | `roles.name` + `role_permissions` (cell = Full/View/Run/Approve/Request/—) | text/enum | reference-data | read-only |

**6 · Acceptance**
- Given an invited or activity-free member, When removed, Then only that tenant's membership disappears (platform user and other-tenant memberships intact) and the action is audited.
- Given a member referenced by any tenant record, When removal is attempted, Then it is blocked with the audit-lock reason and deactivation is offered.
- Given the matrix view, When opened, Then it matches the A4 addendum grid exactly and offers no edit controls.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.
