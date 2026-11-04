# B3 — Tenancy & Security

> **Part B — human/finance judgment.** Drafted from the prototype as a starting point. Every line marked **PLACEHOLDER** must be confirmed by a human before it is authoritative. Nothing here is extracted fact unless it cites the UI.


## Tenancy model (from design + B2)
- Shared-schema multi-tenancy; every tenant table carries `tenant_id` (B2). Platform tables enumerated in B2 §1.
- **RLS is the isolation boundary** (B2 §3): `ENABLE` + `FORCE` + policy on `current_setting('app.tenant_id')`.

## Session context propagation (PLACEHOLDER — confirm)
- On each request, after auth, resolve the tenant from the user's membership + subdomain and `SET app.tenant_id = <uuid>` on the DB session/transaction. Never take tenant_id from client input.
- Background jobs must set `app.tenant_id` explicitly per tenant before touching tenant tables.

## "Enterprise grade" in v1 — scope decisions (PLACEHOLDER, one per line)
- **RBAC:** roles Owner/Admin/Staff/Finance/(Platform Admin) + End Customer portal (A4). Custom tenant roles? PLACEHOLDER.
- **SSO:** in v1? provider? (B7) — `sso_links` table exists but no UI. PLACEHOLDER.
- **Audit:** append-only `audit_log` (B2), who/what/before/after — required for money actions (A6). Retention PLACEHOLDER (see B6).
- **Encryption at rest:** PII columns flagged in B2 (email, name, phone, DOB, gov-id, bank/card last4). Approach: column-level (pgcrypto) vs app-layer vs disk-only — PLACEHOLDER.
- **Data residency:** US assumed (TX authorities in UI) — confirm. PLACEHOLDER.
- **Approvals:** adjustments/write-offs require supervisor (Owner/Finance) per A4/A6 — enforce server-side.

## Cross-tenant rule
No tenant-scoped entity is ever visible cross-tenant. Only Platform Admin, only for support, only if in scope (PLACEHOLDER).

## Status roll-up (Eng-Lead, 2026-08-08) — every PLACEHOLDER above is RESOLVED by rulings
Session propagation → TD-4 as-built (subdomain → tenant → SET app.tenant_id server-side; RLS FORCE). RBAC roles line above is STALE — the ratified model is **3 fixed platform roles** (BR-IDN-008; no Owner/Staff/customer-portal roles in v1; "Owner/Finance" duties map onto System Admin + Executive per the T6 matrix). SSO → v2 (BR-INT-013). Encryption at rest → OQ-016 closure (app-layer high-sensitivity, disk rest; NFR-13). Data residency → US CONFIRMED (B6/NFR). Newest-wins: this roll-up governs.

## Addendum 2026-10-21 — the native field app: two credentials, and the tenant taken from the credential (`CR-187-BRC10`)

⚠ **NEEDS A SERVER ENDPOINT THAT DOES NOT EXIST YET.** Everything below is the agreed DESIGN for the native field app (`field-app/`, ADR-006). The server half — issuing, renewing and checking the capture credential — is **not built**: `TechnicianDevice` (tenant, technician, token, platform, label, active, registered, last seen) exists in `06-backend/apps/work`, and the capture credential needs one or two more columns on it, an issue/renew endpoint and a per-item signature check. Until that lands, no part of this addendum is enforced anywhere. Sign-off of the model and its 36-hour figure is **`OQ-FLD-12798` (OPEN)**. Source: the *SMART360 Next Field App* design canvas, page *Security* (version of 2026-10-21); ADR-026 (AD-21), ADR-029 (AD-24); field-app rules R113, R115, R127, R131–R134. Recorded under the PO ruling of 2026-10-21, decision log *"Where the field-app design lives in the repo"* (*"security → `12-security.md` + an addendum to `04-docs/02-decisions/03-tenancy-and-security.md`"*). The module's full security page is `04-docs/05-modules/18-field-app/12-security.md`.

**Why it exists.** A handset carries a day of a utility's customer data, is used by several people, is left in a van, and is offline for eight hours at a time. **Worked:** Dana signs in at 07:30 on depot wi-fi and drives into a valley. Her access token expires at 08:30, with nine hours of work left and no signal. An app that treats expiry as *signed out* loses the day; one that stretches the token over the shift leaves a server credential on a handset for twelve hours. Neither is acceptable.

### 1 · Two credentials doing two different jobs

| Credential | Lifetime | Authorises | Where it lives |
|---|---|---|---|
| **Access token** | **1 hour**, refreshed whenever there is a signal | Talking to the server, and nothing else. Expiring is normal and uneventful | Platform secure storage |
| **Capture credential** | **36 hours**, device-bound, renewed on every successful contact | Writing to the local store; it **signs each captured item**. It never reaches the server as an authorisation — the server checks each item's signature against the device registration | Keystore / Secure Enclave — hardware-backed, non-exportable, never in the database |

- **Expiry blocks SENDING, never CAPTURE.** Sending is already asynchronous, so the outbox fills exactly as it would have and goes up after the next sign-in.
- **If both expire** (a handset off for days): every unsent item is kept; the app asks for a password before anything more is captured; the queue is untouched.
- **Never:** a silent sign-out that discards work. There is no state in which captured work is thrown away to resolve an auth problem (R113). A remote sign-out drops the mirrored data and keeps the outbox — unsent work sends on next contact, then goes (R115).

### 2 · The tenant comes from the credential, never from the payload

This is B3's existing rule — *"Never take tenant_id from client input"* (session context propagation, TD-4) — carried to the handset's sync. **The server resolves the tenant from the credential that signed the request and never reads a tenant id from the request body** (R127). A tenant id in a body is an attack surface; a tenant-bound capture credential means a handset cannot send to the wrong utility. The server then sets `app.tenant_id` exactly as it does for every request, and RLS `FORCE` applies unchanged (CLAUDE.md hard rule 1).

**Who captured it** is written at capture from the capture credential (`captured_by`), **never read from the current session**. That one line is what makes a shared handset honest: Dana signs out with 62 unsent items, Marco signs in and works, and when the handset reaches wi-fi Dana's items send under Dana's name and Marco's under his (Walkthrough E2E-21, `08-qa/01-e2e/journeys/J-FLD-21-shared-handset-handover.md`).

### 3 · On the handset: the tenant is the FILE

⚠ **The design's Security page §3 reads *"Every table carries tenant_id and every query names it"* (rule R114). That sentence is SUPERSEDED by ADR-029 / R131 (PO ruled)** — no table in the design's inventory ever carried the column. The handset keeps **one SQLite file per tenant**, `field-<tenant>.sqlite`, chosen at sign-in, so a cross-tenant read is impossible rather than unlikely — the server's forced-RLS reasoning, applied to a file. Between technicians on one handset, ten work tables carry `technician_id NOT NULL`, every read of them goes through one scoped-query helper, and a test fails any statement that bypasses it (R132, R133). The sync watermark is per technician per table (R134).

### 4 · The rest of the handset's posture (the design's figures; not separately ruled)

SQLCipher on the database (key in the platform keystore); photograph files encrypted with the same key and deleted on confirmed receipt; MMKV preferences encrypted; map tiles plain. Biometric unlock returns you to your own session only — **switching technician always takes a password**. Auto-lock after 5 minutes idle and after 5 minutes away (amended 2026-10-26, `MQ-019` in the decision log — it read *"immediately on backgrounding"* until then; the app's own permission dialogs, settings visit and fingerprint prompt never count as leaving). Screenshots blocked on screens showing a name, an account or a balance. Rooted or jailbroken: detected, reported, **warned not blocked**. Transport: TLS 1.3 with **two certificate pins** and a written rotation — **`OQ-FLD-12797` (OPEN)**. No MDM requirement — whether the utility's own policy needs one is **`OQ-FLD-12795` (OPEN)**. Handset retention (7 days sent, 14 days closed, 200 MB documents; unsent never purged) against the utility's data policy is **`OQ-FLD-12796` (OPEN)**. A lost handset exposes at most one day's jobs for one tenant, behind the device passcode and an encrypted store — and no card or payment data, because the app reads money and never takes it.

### 5 · What must be true before field-app code relies on this
1. The two-credential model agreed with whoever owns server authentication, and the endpoint built (`OQ-FLD-12798`; decision log 2026-10-21 conflict 6: *"new endpoints (device login, capture credential) go in their own small PRs"*).
2. The certificate pin rotation written down before the first pin ships (`OQ-FLD-12797`).
3. A test that proves the telemetry scrubber by breaking it — a forced crash on FF-25 Customer with a real account on screen, asserting the report carries no name, address, account or balance (ADR-024).
