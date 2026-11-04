# EP-INT-01 — The connections surface (Settings → Integrations: card grid + connect/test/manage/disconnect lifecycle)

**Module:** integrations · **Wave:** W4 (read-model consumed from W3 by US-NOT-004; comms/file consumers W5–W6) · **Screens:** S8 Settings → Integrations tab · **Status:** draft (rule set consolidated BY CITATION — BR-INT-001..016; governing ruling PO CL-1 option a, 2026-08-08 decision log "CL battery CLOSED")

## Scope
**In:** the **S8 Integrations card grid** (prototype-extracted categories + the two v1-REAL additions per CL-1/OQ-074) with per-card connection state — **v1-REAL** cards connect for real, **VISIBLE-BUT-LATER** cards render "Coming soon" with their wave label and a disabled Connect (BR-INT-001); the **connect modal lifecycle** per the A1/A11 addenda — method (OAuth sign-in / API key / SFTP-file), environment (Production/Sandbox), sync cadence, test-connection, Manage-when-connected, Disconnect (BR-INT-002); **encrypted per-tenant secret storage** — credentials never rendered back after save, never logged, never in audit payloads; masked refs only (BR-INT-003, NFR-13 posture); **disconnect consequences** per IS-6 with nothing-queued-is-lost semantics (BR-INT-016); **connection events → audit_log + the per-tenant connection read-model** feeding US-NOT-004 provider status and the soc2 §5 subprocessor register (BR-INT-014).
**Out:** provider-specific connect content — BYO mailbox / ESP (EP-INT-02), bank/lockbox + accounting profiles (EP-INT-03), coming-soon card law (EP-INT-04) · every SEND/IMPORT/EXPORT flow (BR-NOT-005 dispatcher = US-NOT-002/003; lockbox/bank = US-PAY-003/021; accounting handover = US-LED-016) · exact DDL/keys (Eng-Lead 🔒 — field-map discrepancy I-2) · OAuth broker mechanics + secret-vault implementation (Eng-Lead 🔒).

## Capability matrix (list screens only — B9 conformance)
No B9 list screens in this epic — S8 Integrations is a card grid + modals (prototype-extracted), not a table. The file-channel profile management lists are declared in EP-INT-03's matrix.

## Stories

---
id: US-INT-001
epic: EP-INT-01
module: integrations
screens: [S8]
wave: 4
status: draft
blocked_by: []
depends_on: [US-TEN-010]
journeys: []
rules: [BR-INT-001, BR-INT-002, BR-INT-004]
golden_tests: []
finance_calc: none
---
### US-INT-001 — S8 Integrations tab: the card grid — v1-REAL vs coming-soon per the CL-1 connector matrix

**1 · Details** — As a System Admin, I want the Settings → Integrations tab (S8 tab 8, A1 Settings rework) to render the integration card grid — the featured **Email band** (Google Workspace/Gmail · Microsoft 365/Outlook · Custom SMTP, prototype-extracted) plus category cards — so that every provider seam (B7) is visible and its v1 disposition is honest. Per-card state per the **CL-1 connector matrix (BR-INT-001)**: **v1-REAL** — BYO email (3 cards), **Transactional ESP** (card added per OQ-074 closure: "connected as the tenant's integration"), **Bank & lockbox import profiles** (added per CL-1; flows live in payments), **QuickBooks Online / Xero as FILE export targets** (BR-LED-020 file-v1; card carries a "Live sync — v2" sub-badge); **VISIBLE-BUT-LATER** — Stripe (W7), Plaid ACH (W7), Twilio SMS (v1.1), QBO/Xero live sync (v2), Itron MDM (v2), Sensus FlexNet (v2), Okta/Azure AD SSO (v2) — card renders with "Coming soon" + wave label, Connect disabled (EP-INT-04 owns the gating law). Lob/DocPrint renders connectable per the A1 addendum; its matrix placement is a flagged discrepancy (field map I-1), not decided here. Connected cards show status pill + summary line + **Manage**; unconnected v1-REAL cards show **Connect** (prototype pills: Connected / Not connected). Entry: Settings → Integrations. Exit: card action opens US-INT-002's modal.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-001 | v1 connector matrix: v1-REAL = BYO email (Google/Microsoft OAuth + SMTP), transactional ESP, bank/lockbox file-import profiles, accounting FILE export targets; VISIBLE-BUT-LATER = Stripe/Plaid (W7), Twilio (v1.1), QBO/Xero live sync (v2), Itron/Sensus MDM (v2), Okta/Azure AD SSO (v2). | CONFIRMED — PO CL-1 option a, 2026-08-08 (decision log) |
| BR-INT-002 | Every card opens the connect modal (Connect / Manage-when-connected + Disconnect) per the A1 + A11 addenda. | CONFIRMED — A1 addendum "Integrations are connectable" + A11 addendum, 2026-08-07 |
| BR-INT-004 | Every integration sits behind a provider-agnostic seam with per-tenant enable/config; no provider hardcoded into business logic. | CONFIRMED — B7 design rule (2026-08-07) + NFR-21 + TD-8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex (Admin) opens S8 Integrations | Email band (3 cards) + category grid render with per-card state; v1-REAL cards actionable; Google card shows "billing@brazosbend.example · OAuth · Connected" |
| TC-2 | Coming-soon cards | Stripe/Plaid show "Coming soon · W7"; Twilio "v1.1"; Itron/Sensus/SSO + QBO-live-sync badge "v2" — Connect disabled with the wave label (BR-INT-001); no modal opens |
| TC-3 | QBO card duality | Card is v1-REAL as a FILE export target (opens US-INT-009 profile) AND carries "Live sync — v2" (BR-LED-020); prototype copy "Auto-syncs GL nightly" NOT rendered (superseded — field map I-4) |
| TC-4 *(negative)* | Priya (Billing Clerk) opens Settings → Integrations | Settings are System-Admin-gated (A1); tab absent/denied; direct API calls rejected server-side (IS-6 principle: UI gating is convenience) |
| TC-5 *(negative)* | Direct `POST /integrations/stripe/connect` in v1 | Rejected server-side — coming-soon cards are disabled at the API too, not just in the UI (BR-INT-001; OQ-015 no-Stripe-v1) |
| TC-6 *(secret-handling)* | `GET /integrations` (grid data source, A11 addendum) | Returns per-card state + masked refs only (e.g. mailbox address, "key ••••3F9A") — NO credential material in any grid/API payload (BR-INT-003) |
| TC-7 *(isolation)* | J. Okafor (Lone Star Ridge) opens the grid | Only Lone Star Ridge connection states; Brazos Bend's connected mailbox/ESP invisible (RLS FORCE, NFR-10) |

**4 · Test Data** — Brazos Bend MUD: Google mailbox Connected (billing@brazosbend.example), ESP Connected (key ••••3F9A), bank profile "Chase Operating ••4021 · BAI2" active, QBO file target set (EXP-2607-QBO history exists), all coming-soon cards unconnected. Lone Star Ridge WSC: everything Not connected. Actors: Alex Reed (System Admin), Priya Menon (Billing Clerk, negative), J. Okafor (Lone Star Ridge admin).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Card catalog (category · name · description) | S8 | prototype-extracted grid + A1 addendum card list | reference catalog (platform-seeded; connection keys per A11 addendum) | enum/text | reference-data | keys: quickbooks, xero, stripe, plaid, itron, sensus, twilio, lob, sso, email(google\|microsoft\|smtp) + esp, bank profiles (I-3) |
| Per-card v1 disposition (real / coming-soon + wave label) | S8 | CL-1 matrix (BR-INT-001) | catalog disposition flags (platform, not tenant) | enum | reference-data | v1_real \| coming_soon(W7\|v1.1\|v2) |
| Connection state per card | S8 | A11 addendum (`GET /integrations`) | `integration_connections.status` (module-owned; DDL 🔒 I-2) | enum | system-derived | not_connected \| connected \| failed |
| Connected summary line | S8 | prototype-extracted ("billing@silvercreek.example · OAuth") | non-secret config columns (send-from, env, cadence) | text | computed-display | masked refs only (BR-INT-003) |
| Card actions Connect/Manage | S8 | A1 addendum | opens US-INT-002 modal | — | user-input | Admin-only; disabled+label on coming-soon |

**6 · Acceptance**
- Given the grid, Then every B7 seam renders as a card with its CL-1 disposition — real cards connect, later cards say Coming soon + wave and refuse Connect at UI AND API.
- Given a connected card, Then it shows a masked summary + Manage; no payload anywhere contains credential material.
- Given a non-admin or another tenant, Then the surface denies server-side / shows only that tenant's states.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-INT-002
epic: EP-INT-01
module: integrations
screens: [S8]
wave: 4
status: draft
blocked_by: []
depends_on: [US-INT-001]
journeys: []
rules: [BR-INT-002, BR-INT-003, BR-INT-004, BR-INT-015]
golden_tests: []
finance_calc: none
---
### US-INT-002 — The connect modal: method / environment / cadence → save encrypts, test-connection verifies, failures surface "Failed · Retry"

**1 · Details** — As a System Admin, I want the **Connect integration modal** (prototype-extracted; A1 addendum spec) for every v1-REAL card: **How to connect** — OAuth sign-in / API key / SFTP-file (segmented, per card's supported methods) · **API key / token** field (write-only) · **Environment** — Production / Sandbox (B7: sandbox creds per seam) · **Sync cadence** — Nightly / Hourly / Manual · **"Run a test connection after saving"** toggle — so that connecting is one consistent flow (`POST /integrations/{key}/connect`, A11 addendum). On save: credentials go to **encrypted per-tenant secret storage** (B7 addendum + A11 addendum; app-layer posture per NFR-13/OQ-016 closure) and the form NEVER echoes them back — reopening Manage shows masked refs only (BR-INT-003); the connection row records method, environment, cadence, connected-by/at. **Test-connection** (`POST /integrations/{key}/test`) runs on the toggle or on demand from Manage and stamps last-test result. A failed connect/test rests the card at **Failed · Retry** (B7 failure-surfacing rule) with the provider error — never a silent half-state. OAuth methods redirect-and-return per the modal copy ("You'll be redirected to sign in, then returned here"); broker mechanics = Eng-Lead 🔒. Entry: card Connect/Manage (US-INT-001). Exit: connection `connected` (or `failed`), events audited (US-INT-004).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-002 | Connect modal = method (oauth\|apikey\|sftp) · key/token · environment (Production/Sandbox) · sync cadence · test-connection · Disconnect; endpoints connect/test/disconnect/GET-states. | CONFIRMED — A1 addendum + A11 addendum, 2026-08-07 |
| BR-INT-003 | Credentials/tokens = encrypted per-tenant secrets; never rendered back after save, never logged, never in audit payloads — masked refs only, always. | CONFIRMED — B7 addendum + A11 addendum ("stored as encrypted per-tenant secrets") + NFR-13/OQ-016 encryption posture + BR-CUS-045 masked-display-always principle |
| BR-INT-015 | Failures surface "Failed · Retry" in the UI (never silent); per-seam sandbox creds + retry policy are part of the seam contract. | CONFIRMED — B7 design rule, 2026-08-07 |
| BR-INT-004 | No provider hardcoded; per-tenant enable/config behind the seam. | CONFIRMED — B7 + NFR-21 + TD-8 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex connects the ESP: API key pasted, Production, Nightly, test-toggle ON | Secret encrypted + stored; test runs; card → Connected; connection row carries method=apikey, env=production, cadence=nightly, connected_by=Alex, last_test=pass |
| TC-2 *(secret-handling — the rule's reason to exist)* | Alex reopens Manage after TC-1 | Key field shows masked ref "••••3F9A" (write-only field, empty-unless-replacing); the secret appears in NO response, NO log line, NO audit payload (BR-INT-003); replacing = paste-new-overwrite, never read-back |
| TC-3 | Sandbox first, then promote | Env=Sandbox connects + tests against sandbox creds (B7); switching to Production requires its own credential entry + test — no cross-environment secret reuse |
| TC-4 *(negative)* | Test-connection fails (bad key / provider 401) | Card → **Failed · Retry** with the provider error surfaced (BR-INT-015); nothing downstream consumes a failed connection; Retry re-runs test without re-entering the key |
| TC-5 *(negative)* | Save with method=apikey and an empty key field on first connect | Validation blocks — a first connect must carry a credential; no empty secret row is created |
| TC-6 | OAuth method (Google card) | Redirect-out/return-per modal copy; on return the connection stores the token as a secret + shows the authorized address — token itself never displayed (pairs US-INT-005) |
| TC-7 *(isolation)* | Two tenants connect the same provider key (both use QBO) | Two independent connection rows + two independent secrets; RLS scopes both; J. Okafor's test never touches Brazos Bend's credentials |

**4 · Test Data** — Brazos Bend: ESP key ending 3F9A (Production/Nightly, test pass); failure fixture: key ending 9Z11 → provider 401 "invalid api key" → Failed · Retry; sandbox fixture: Xero file-target profile in Sandbox. OAuth fixture: billing@brazosbend.example (Google). Actors: Alex Reed; isolation: J. Okafor connects QBO for Lone Star Ridge same hour.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Method | S8 modal | A1/A11 addenda | `integration_connections.method` (DDL 🔒 I-2) | enum | user-input | oauth \| apikey \| sftp, per card's supported set |
| API key / token | S8 modal | A1 addendum ("key/token field") | encrypted secret store — **secret_ref pointer only** on the row (🔒) | secret | user-input | write-only; required on first apikey/sftp connect; never echoed (BR-INT-003) |
| Environment | S8 modal | A1 addendum + B7 ("sandbox creds") | `.environment` | enum | user-input | production \| sandbox; per-env credentials |
| Sync cadence | S8 modal | A1 addendum + prototype (Nightly/Hourly/Manual) | `.sync_cadence` | enum | user-input | nightly \| hourly \| manual |
| Test-connection toggle + result | S8 modal | A1 addendum + A11 (`/test`) | `.last_test_at` + `.last_test_result` | ts/enum | user-input / integration | pass \| fail + provider error text |
| Connection status | S8 card | A11 (`connect` returns status) + B7 (Failed · Retry) | `.status` | enum | system-derived | not_connected → connected \| failed; failed shows Retry |
| Connected-by/at | S8 Manage | BR-TEN-016 family (who/when on Settings writes) | `.connected_by`, `.connected_at` | uuid/ts | system-derived | stamped on save |

**6 · Acceptance**
- Given a v1-REAL card, Then connect captures method/env/cadence + credential, encrypts the credential, and optionally test-verifies — and the credential is never retrievable by any actor thereafter.
- Given a provider failure, Then the card reads Failed · Retry with the provider error; given success, Connected with a masked summary.
- Given environments, Then sandbox and production credentials are separate; given tenants, secrets and connections never cross.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-INT-003
epic: EP-INT-01
module: integrations
screens: [S8]
wave: 4
status: draft
blocked_by: []
depends_on: [US-INT-002, US-NOT-003]
journeys: [J2]
rules: [BR-INT-016, BR-INT-003, BR-NOT-005]
golden_tests: []
finance_calc: none
---
### US-INT-003 — Disconnect: IS-6 confirm with per-card consequence messaging; nothing queued or recorded is ever lost

**1 · Details** — As a System Admin, I want **Disconnect** (modal footer action, prototype; `DELETE /integrations/{key}`, A11 addendum) to follow **IS-6**: confirmation modal → explicit confirm → toast ("Integration disconnected", prototype) → audit row — with **consequence messaging** stating exactly what stops: mailbox/ESP → "queued email will wait; nothing sends until a mailbox or ESP is reconnected — there is no fallback shared sender" (BR-NOT-005/US-NOT-003 TC-5 semantics + B7 addendum shared-sender ban); bank/lockbox profile → "recorded import batches and payments are untouched; new imports for this profile are unavailable"; accounting target → "recorded export batches (EXP- history) are untouched; new handovers to this target are unavailable until reconnected". Disconnect **revokes/destroys the stored secret** and sets status `not_connected`; it NEVER deletes history — connection events, audit rows, queue rows, `payment_import_batches`, `export_batches` all survive (append-only law, NFR-15/16 families). Consumers react per their own ratified behavior: dispatcher rows rest `queued` with config-missing surfaced on the dispatch home (US-NOT-003/004) — no crash, no loss. Entry: Manage modal → Disconnect. Exit: card Not connected; consumers waiting visibly.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-016 | Disconnect = IS-6 destructive flow (modal → explicit confirm → toast → audit_log) WITH consequence messaging; secret destroyed; no queued/recorded data is lost — dependent flows wait visibly. | CONFIRMED — IS-6 (B9) + BR-NOT-005 queue semantics + B7 addendum (no shared sender); consequence-messaging pattern per OQ-012 closure precedent |
| BR-NOT-005 *(consumed)* | Rows rest `queued` when the channel's provider config is missing; the queue is the only send path — rows are never lost. | CONFIRMED — PO ruling 2026-08-08 (US-NOT-003 TC-5) |
| BR-INT-003 | Disconnect audit payload carries masked refs only — never the (now destroyed) credential. | CONFIRMED — see US-INT-002 §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex disconnects the Google mailbox (982 email rows queued for W6) | IS-6 modal states the consequence verbatim (queued mail waits; no fallback sender); on confirm: secret destroyed, status not_connected, toast, `audit_log` `integration.disconnected`; all 982 rows still `queued`; dispatch home shows config-missing (US-NOT-004) |
| TC-2 | Disconnect the QBO file target after EXP-2607-QBO exists | Export history + batches untouched (BR-LED-004 idempotency record survives); S42 Connections panel reads "Set up"; a new July re-run is STILL blocked by the recorded batch — disconnect never resets idempotency |
| TC-3 | Reconnect after TC-1 | Fresh credential entry required (old secret is gone — no resurrect); on connect the deferred rows drain normally at W6 in tenant-config batches (US-NOT-003 TC-4) |
| TC-4 *(negative)* | Priya attempts `DELETE /integrations/email_google` | Rejected server-side — Admin-only; disabled-with-reason in UI (IS-6) |
| TC-5 *(negative)* | Confirm modal dismissed (Esc/Cancel) | Nothing changes — no partial disconnect state; connection still `connected` |
| TC-6 *(secret-handling)* | Inspect the disconnect audit row + server logs for TC-1 | Payload = key, masked summary ("billing@brazosbend.example", "OAuth"), actor, when — zero token/credential material anywhere (BR-INT-003) |
| TC-7 *(isolation)* | Alex disconnects Brazos Bend's ESP | Lone Star Ridge's ESP connection untouched; its rows/dispatch unaffected (RLS) |

**4 · Test Data** — Brazos Bend: Google mailbox connected + 982 deferred email rows (US-NOT-003 fixture); QBO target with batch EXP-2607-QBO (US-LED-016 fixture); ESP key ••••3F9A. Reconnect fixture: new Google OAuth grant next day. Actors: Alex Reed, Priya Menon (negative), J. Okafor (isolation).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Disconnect action | S8 modal footer | prototype ("Disconnect" ghost button + toast) + A11 (`DELETE`) | `.status` → not_connected; secret destroyed (🔒) | enum | user-input | IS-6 modal-confirm-toast-audit; Admin-only |
| Consequence copy per card class | S8 confirm modal | BR-NOT-005 (rows wait) + B7 addendum (no shared sender) + BR-LED-004/BR-PAY-028 (recorded batches survive) | rendered copy (no storage) | text | computed-display | states what stops + what survives |
| Config-missing surface | S8 Notifications tab | US-NOT-003 TC-5 / US-NOT-004 | dispatch-home readout over connections read-model | status | computed-display | rows queued + "no mailbox/ESP connected" |
| History survival | S8/S42/S35 | NFR-15/16 (append-only, idempotency records) | audit_log, outbound_messages, payment_import_batches, export_batches — untouched | rows | system-derived | disconnect touches ONLY the connection row + secret |

**6 · Acceptance**
- Given Disconnect, Then IS-6 confirm shows the true consequences, the secret is destroyed, and the card reads Not connected — audited with masked refs.
- Given queued/recorded downstream data, Then nothing is deleted, re-sent, or re-runnable that idempotency had blocked; consumers wait visibly.
- Given reconnection, Then fresh credentials are required and waiting work resumes under normal pacing.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-INT-004
epic: EP-INT-01
module: integrations
screens: [S8]
wave: 4
status: draft
blocked_by: []
depends_on: [US-INT-002]
journeys: []
rules: [BR-INT-014, BR-INT-003, BR-INT-008]
golden_tests: []
finance_calc: none
---
### US-INT-004 — Connection events → audit_log (masked) + the read-model for consumers + the subprocessor-register feed

**1 · Details** — As the system, I want every connection lifecycle event — connect, test run, config change (env/cadence/send-from), disconnect — written to `audit_log` (BR-TEN-016: every Settings write, with before/after; payloads masked per BR-INT-003), and a **read-only connection read-model** (`GET /integrations` states, A11 addendum) exposed via service function (B1 boundary) so consumers never touch this module's tables: **US-NOT-004** provider-status readout + **US-NOT-002/003** adapter binding (BR-NOT-005 seam) read it; **S42 Connections panel** (ledger D-7) reads QBO/Xero target state; **S38/S35** read bank-profile state. The read-model also feeds the **subprocessor register** (soc2-nist-mapping §5, register kept in audit-and-controls.md): connecting a provider-class integration (ESP · Twilio v1.1 · print vendor · e-sign — the §5 enumeration) surfaces on the platform-side register feed; **BYO mailboxes are the tenant's own accounts** and are NOT in the §5 subprocessor enumeration. Contracts/DPAs stay ops-owned (§5). Entry: any US-INT-002/003 event. Exit: audit truth + consumer read-model current.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-014 | Every connection lifecycle event writes audit_log (who/what/before-after, masked refs); connection states feed the soc2 §5 subprocessor register. | CONFIRMED — BR-TEN-016 (every Settings write audited) + CLAUDE.md #7 principle + soc2-nist-mapping §5 (RECORDED 2026-08-08) |
| BR-INT-008 | Integrations SENDS/IMPORTS/EXPORTS nothing itself — connections are config READ by the owning flows (dispatcher BR-NOT-005; payments BR-PAY-019/023; ledger BR-LED-004); cross-module access = service-function reads only. ⚠ *AMENDED 2026-10-02 (PO, "B · Keep it and change the rule, because it only passes the job on."): the export door may hand an export job to the runner, carrying no figure and no file; sending is unchanged — see `02-business-rules.md` BR-INT-008.* | CONFIRMED — BR-NOT-005 + B1 boundary rule + TD-8 |
| BR-INT-003 | Audit payloads: masked refs only, never credentials. | CONFIRMED — see US-INT-002 §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Full lifecycle: connect ESP → test → cadence Nightly→Hourly → disconnect | Four audit rows (`integration.connected` / `.test_run` / `.updated` with before/after cadence / `.disconnected`), each with actor + masked summary; append-only |
| TC-2 | US-NOT-004 provider-status panel | Reads this read-model: "Mailbox: Connected (Google, billing@brazosbend.example) · ESP: Connected · Twilio: Not connected" — exactly the US-NOT-004 TC-3 contract, no connect UI there |
| TC-3 | S42 Connections panel (ledger D-7) | QBO reads Connected-as-file-target / Xero "Set up" from this read-model — no ledger-side connection storage |
| TC-4 | Subprocessor feed | Brazos Bend connects the ESP → the platform register feed lists the ESP engagement (soc2 §5 class); connecting the Google BYO mailbox adds NOTHING to the §5 feed (tenant-own account, outside the enumeration) |
| TC-5 *(negative)* | A consumer module attempts a direct SQL read/write on `integration_connections` | Forbidden — B1: cross-module access via service functions only; module writers never touch integrations tables |
| TC-6 *(secret-handling)* | Dump every audit row + read-model response from TC-1 | Zero credential bytes anywhere; secrets exist only in the encrypted store, referenced by pointer (BR-INT-003) |
| TC-7 *(isolation)* | Read-model queried under Lone Star Ridge | Its connections only; the platform-side register feed is Bynry-scoped ops surface, not tenant-visible (RLS + platform split per B10 boundary pattern) |

**4 · Test Data** — Brazos Bend lifecycle fixture per TC-1 (Alex Reed, Aug 9 2026, 14:02–14:11); consumer fixtures: US-NOT-004 panel, S42 panel (QBO connected / Xero not); register fixture: ESP engagement dated Aug 9. Isolation: Lone Star Ridge empty states.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Audit events | — (S61 viewer) | BR-TEN-016 + CLAUDE.md #7 | `audit_log` `integration.connected\|test_run\|updated\|disconnected` | jsonb | system-derived | append-only; masked payloads |
| Read-model (states per key) | S8 + consumer panels | A11 addendum (`GET /integrations`) | service-function view over `integration_connections` (🔒 I-2) | status set | computed-display | read-only; RLS-scoped |
| Consumer bindings | S8 Notifications / S42 / S38 / S35 | US-NOT-004 §5 ("read-model over integrations connections") + ledger D-7 + payments P-6/P-10 | reads via the same service seam | config | integration | consumers never write |
| Subprocessor feed | — (platform ops) | soc2 §5 (ESP, Twilio, print vendor, e-sign enumeration) | platform-side register feed → audit-and-controls.md register | rows | system-derived | §5 classes only; BYO mailbox excluded; DPAs = ops |

**6 · Acceptance**
- Given any lifecycle event, Then an append-only audit row exists with masked refs; given the register classes, the platform feed reflects the engagement.
- Given consumers, Then all of them read one service-function read-model and none store or touch connection rows.
- Given tenants, Then read-models never cross and the register feed is platform-scoped.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.
