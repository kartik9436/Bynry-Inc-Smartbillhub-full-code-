# EP-INT-02 — Comms connections (BYO mailbox · transactional ESP · channel activation for the dispatcher)

**Module:** integrations · **Wave:** W5 (connections can be made early; email SENDING activates W6 — OQ-073 closure, CL-1 "connection can be made early, sending activates with the wave") · **Screens:** S8 Settings → Integrations (Email band + ESP card); consumer surfaces S8 Notifications tab (US-NOT-004/013) · **Status:** draft (BR-INT-005..008/015 CONFIRMED)

## Scope
**In:** **BYO mailbox connect** — Google OAuth / Microsoft 365 OAuth / custom SMTP (host/port/credentials), send-from address, test email on connect (A15 addendum + B7 addendum: NO shared email-sending service, ever); **transactional ESP connect** — API key + sending-domain checklist, the volume path per OQ-074 closure (BYO for small tenants; ESP as the tenant's integration for 6k–10k bills); **channel activation** — how a comms connection becomes the dispatcher's adapter binding (BR-NOT-005 seam, integrations-owned config read by US-NOT-002/003; email W6-gated per BR-INT-007) + the **health surface** (connection/test/send-failure states feeding US-NOT-004 provider status and the US-NOT-013 delivery dashboard, "Failed · Retry" per B7).
**Out:** the queue, dispatcher, batching, retry, statuses (EP-NOT-01 — notifications owns ALL sending) · template content/rendering/send-test previews (EP-NOT-02) · Twilio SMS connect (deferred v1.1 — EP-INT-04) · generic modal mechanics/secret storage/audit (EP-INT-01, consumed here).

## Capability matrix (list screens only — B9 conformance)
No B9 list screens in this epic (cards + modals + read-models).

## Stories

---
id: US-INT-005
epic: EP-INT-02
module: integrations
screens: [S8]
wave: 5
status: draft
blocked_by: []
depends_on: [US-INT-002, US-NOT-003]
journeys: [J2]
rules: [BR-INT-005, BR-INT-007, BR-INT-003]
golden_tests: []
finance_calc: none
---
### US-INT-005 — BYO mailbox connect: Google OAuth / Microsoft OAuth / custom SMTP — send from the utility's OWN address

**1 · Details** — As a System Admin, I want the **Connect your mailbox** modal (prototype-extracted; A1 Settings rework modal list): method **Google OAuth / Microsoft OAuth / Custom SMTP** (segmented), **send-from address**, SMTP host + port (custom only; credentials via the US-INT-002 secret path), and **"Send a test email after connecting"** — so that ALL customer email (bills, statements, reminders, receipts, notices) sends **from the utility's own address**, never a shared platform sender (A15 addendum + B7 addendum, confirmed 2026-08-07). OAuth methods authorize the mailbox and capture the authorized address; SMTP captures host/port/credentials (encrypted, BR-INT-003). The connect-time **test email verifies the mailbox by sending through it** (A15 addendum: "a test email offered on connect") — this is connection verification, distinct from CUSTOMER sending which stays W6-gated (BR-INT-007; the dispatcher's deferred-channel handling is US-NOT-003, unchanged). Three cards, one connection class: connecting any method makes the tenant's mailbox available to the seam; the Email band shows the connected card's address + method. Entry: Email band card (US-INT-001). Exit: mailbox connection available to the US-INT-007 binding.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-005 | No shared email-sending service exists; tenants connect their OWN mailbox (Google OAuth / M365 OAuth / custom SMTP); send-from configured + test email offered on connect; all customer email from the tenant's own address. | CONFIRMED — B7 addendum + A15 addendum, 2026-08-07 |
| BR-INT-007 | Email connection may be made from day one; customer email SENDING activates W6 with notifications (queue architecture stands). | CONFIRMED — OQ-073 CLOSED (PO F-round) + CL-1 ruling 2026-08-08 |
| BR-INT-003 | SMTP credentials / OAuth tokens = encrypted secrets, never rendered back. | CONFIRMED — see US-INT-002 §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex connects Google OAuth for billing@brazosbend.example, test toggle ON | OAuth grant stored as secret; card shows "billing@brazosbend.example · OAuth · Connected"; test email sends **through the connected mailbox** and the result stamps last-test; audit row (US-INT-004) |
| TC-2 | Custom SMTP connect: smtp.brazosbend.example:587 + credentials | Credentials encrypted; send-from billing@brazosbend.example; test send verifies; Connected |
| TC-3 | Pre-W6 after TC-1 | Customer email rows still rest `queued` with the deferred marker (US-NOT-003 TC-2) — connecting early NEVER starts customer sending before W6 (BR-INT-007); only the connect-time test email was sent |
| TC-4 *(negative)* | SMTP connect with wrong password | Provider auth failure → card **Failed · Retry** with the error (BR-INT-015 via US-INT-002 TC-4); no half-connected state; no customer path affected |
| TC-5 *(negative)* | Any code path attempts platform-sender fallback while no mailbox is connected | Does not exist — there is no shared sender to fall back to (B7 addendum); rows wait per US-NOT-003 TC-5 |
| TC-6 *(secret-handling)* | Reopen Manage on the SMTP card | Host/port/send-from visible; password field masked write-only; token/password in no payload, log, or audit row (BR-INT-003) |
| TC-7 *(isolation)* | Lone Star Ridge connects billing@lonestarridge.example | Two tenants, two mailboxes, two secrets; at W6 each sends exclusively from its OWN mailbox (US-NOT-003 TC-7 pair) |

**4 · Test Data** — Brazos Bend: Google OAuth billing@brazosbend.example (connected Aug 9 2026, test pass); SMTP variant smtp.brazosbend.example:587. Failure fixture: SMTP auth 535 bad credentials. Isolation: Lone Star Ridge Google OAuth billing@lonestarridge.example. Actors: Alex Reed; J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Method | S8 email modal | A15 addendum + prototype (3 segments) | `integration_connections.method` (email_google\|email_microsoft\|email_smtp per A11 keys) | enum | user-input | one active mailbox class per tenant surfaced on the band |
| Send-from address | S8 email modal | A15 addendum ("a send-from address is configured") + prototype field | non-secret config column | text | user-input / integration (OAuth-authorized address) | required; shown on card |
| SMTP host / port | S8 email modal | prototype (custom only; 587 placeholder) | non-secret config columns | text/int | user-input | required for smtp method only |
| SMTP credentials / OAuth token | — | B7 addendum (secrets) | encrypted secret store (US-INT-002) | secret | user-input / integration | never echoed (BR-INT-003) |
| Test email on connect | S8 email modal | A15 addendum + prototype checkbox | send THROUGH the connected mailbox; result → last_test | flag/enum | user-input / integration | verification send only; recipient handling = field-map I-6 (cosmetic) |
| Deferred customer sending | — | OQ-073 closure | channel gating stays with US-NOT-003 config | flag | reference-data | connection ≠ activation |

**6 · Acceptance**
- Given any of the three methods, Then the tenant's own mailbox connects, its address shows on the band, and its credential is encrypted and irretrievable.
- Given a connection pre-W6, Then no customer email sends; the connect-time test send is the only traffic.
- Given failure, Then Failed · Retry with the provider error; given tenants, mailboxes never cross.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-INT-006
epic: EP-INT-02
module: integrations
screens: [S8]
wave: 5
status: draft
blocked_by: []
depends_on: [US-INT-002, US-NOT-002]
journeys: [J2]
rules: [BR-INT-006, BR-INT-004, BR-INT-003]
golden_tests: []
finance_calc: none
---
### US-INT-006 — Transactional ESP connect: API key + sending-domain checklist (the 6k–10k volume path)

**1 · Details** — As a System Admin of a volume tenant, I want the **Transactional ESP card** (added to the grid per OQ-074 closure: "transactional ESP connected as the tenant's integration for 6k–10k volume"; CL-1 v1-REAL) to connect via the US-INT-002 modal — method **API key**, environment, cadence n/a-manual — plus an ESP-specific **sending-domain checklist**: sending domain entered · send-from address · **domain verification status as reported by the ESP** (the connection surfaces the provider's own verification result; the platform invents no DNS rules) — so that a tenant issuing 6k–10k bills has a provider that can absorb the volume (BR-NOT-005 pacing rationale: "ESP/Twilio will not send such emails quickly" — the dispatcher paces, the ESP absorbs). The connection is provider-agnostic (BR-INT-004 — "transactional ESP" is a seam class, no vendor hardcoded; B7 suggested SendGrid/SES remain suggestions). An unverified domain leaves the connection `connected` but the checklist visibly incomplete — the health surface (US-INT-007) carries it; sending remains W6-gated regardless (BR-INT-007). Entry: ESP card. Exit: ESP connection + checklist state available to US-INT-007.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-006 | Volume split: BYO mailbox for small tenants; transactional ESP connected AS THE TENANT'S INTEGRATION for 6k–10k bill volume. | CONFIRMED — OQ-074 CLOSED (PO F-round) + CL-1 v1-REAL |
| BR-INT-004 | ESP = provider-agnostic seam class; per-tenant config; no vendor hardcoded. | CONFIRMED — B7 design rule + NFR-21 ("transactional ESP (volume)") |
| BR-INT-003 | ESP API key = encrypted secret, masked ref display. | CONFIRMED — see US-INT-002 §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex connects the ESP: key pasted, sending domain brazosbend.example, send-from billing@brazosbend.example | Key encrypted (••••3F9A masked ref); checklist shows domain + provider-reported verification status; card Connected |
| TC-2 | Domain not yet verified at the provider | Connection `connected`, checklist item "Domain verification — pending (provider)"; health surface shows the incomplete item (US-INT-007); no invented DNS instructions — the provider's own checklist is linked/surfaced |
| TC-3 | W6 activation for a volume tenant | Dispatcher drains the backlog in tenant-config batches THROUGH the ESP binding (US-NOT-003 TC-4 pair — Brazos Bend = ESP tenant fixture); pacing rule holds |
| TC-4 *(negative)* | Key revoked at the provider after connect | Next test/send attempt fails → **Failed · Retry** with provider error (B7); dispatcher rows rest queued/failed per BR-NOT-005 — never lost |
| TC-5 *(negative)* | Connect attempt with an empty key | Blocked at validation (US-INT-002 TC-5 pattern) |
| TC-6 *(secret-handling)* | Manage reopened; logs + audit inspected | Masked ref only ("••••3F9A"); zero key material in payloads/logs/audit (BR-INT-003) |
| TC-7 *(isolation)* | Both tenants connect ESPs | Independent keys, domains, checklists; W6 dispatch uses each tenant's OWN binding (US-NOT-003 TC-7) |

**4 · Test Data** — Brazos Bend (volume tenant, 6k+ bills — US-NOT-003 W6 fixture): ESP key ••••3F9A, domain brazosbend.example verified, send-from billing@brazosbend.example. Pending fixture: domain status "pending" first hour. Revoked fixture: provider 401 on Aug 15 test. Isolation: Lone Star Ridge = BYO-mailbox tenant (no ESP) — the OQ-074 small-tenant path.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| ESP connection (key=esp) | S8 card | OQ-074 closure + CL-1 (card added — field map I-3) | `integration_connections` row, method=apikey (🔒 I-2) | row | user-input | v1-REAL |
| API key | S8 modal | A1 addendum key/token field | encrypted secret store | secret | user-input | write-only, masked ref |
| Sending domain + send-from | S8 modal | CL-1 pack directive (ESP = key + sending-domain checklist) | non-secret config columns | text | user-input | domain required for ESP class |
| Domain verification status | S8 checklist | provider-reported (seam contract, B7) | config column updated on test/webhook | enum | integration | verified \| pending \| failed — provider's verdict, never computed locally |
| Volume-path binding | — | OQ-074 closure | US-INT-007 active-provider binding | config | reference-data | ESP absorbs 6k–10k dispatch |

**6 · Acceptance**
- Given a volume tenant, Then the ESP connects with key + domain checklist, and at W6 its backlog drains through the ESP at dispatcher pacing.
- Given an unverified domain or revoked key, Then the state is visible (checklist / Failed · Retry) and nothing is silently lost.
- Given tenants, Then keys, domains and bindings never cross.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-INT-007
epic: EP-INT-02
module: integrations
screens: [S8]
wave: 5
status: draft
blocked_by: []
depends_on: [US-INT-005, US-INT-006, US-NOT-002, US-NOT-003, US-NOT-013]
journeys: [J2]
rules: [BR-INT-008, BR-INT-006, BR-INT-007, BR-INT-015]
golden_tests: []
finance_calc: none
---
### US-INT-007 — Channel activation: the adapter binding the dispatcher reads + provider health feeding the delivery dashboard

**1 · Details** — As the system, I want comms connections to ACTIVATE the email channel for the BR-NOT-005 dispatcher through one **integrations-owned adapter binding** (US-NOT-003 §5: "per-tenant provider config (integrations-owned read)"): a tenant with exactly ONE comms connection (mailbox OR ESP) binds to it by default; a tenant with BOTH connected makes an **explicit active-email-provider selection** on the ESP/mailbox Manage surface (per-tenant enable/config, B7 design rule; OQ-074's small-vs-volume split rendered as the selector's guidance copy) — with no connection, the binding is empty and the dispatch home shows config-missing (US-NOT-003 TC-5). The binding NEVER sends — US-NOT-002 drains queues through it at W6 (BR-INT-007); integrations exposes config only (BR-INT-008). And I want the **health surface**: per-provider status (connected/failed + last test + last provider send-error from dispatcher attempts, "Failed · Retry" per B7) exposed on the read-model so **US-NOT-004** (provider status panel) and **US-NOT-013** (delivery dashboard failures view) render provider truth without owning it. Entry: connection events / dispatcher error reports. Exit: binding + health consumed by notifications surfaces.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-008 | The dispatcher READS the integrations binding; integrations sends nothing (queue = only send path). ⚠ *AMENDED 2026-10-02 (PO, "B · Keep it and change the rule, because it only passes the job on."): the export door may hand an export job to the runner, carrying no figure and no file; sending is unchanged — see `02-business-rules.md` BR-INT-008.* | CONFIRMED — BR-NOT-005 + B2 r12 #16 ("provider adapters behind one seam") + TD-8 |
| BR-INT-006 | BYO for small tenants / ESP for volume — the split governs which binding a tenant runs. | CONFIRMED — OQ-074 CLOSED |
| BR-INT-007 | Binding exists from connect day; email dispatch through it activates W6. | CONFIRMED — OQ-073 CLOSED + CL-1 |
| BR-INT-015 | Provider failures surface "Failed · Retry"; health states feed the delivery dashboard. | CONFIRMED — B7 design rule + BR-TEN-041 #8 (provider status on the dispatch home) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Lone Star Ridge: only the Google mailbox connected | Binding defaults to the mailbox — no selection step needed; US-NOT-004 panel shows it as THE email provider |
| TC-2 | Brazos Bend: mailbox AND ESP connected | Explicit active-provider selection required (guidance copy = the OQ-074 split); until selected, dispatch home shows the choice pending — the system never auto-picks between two providers |
| TC-3 | W6: Brazos Bend selects ESP | Dispatcher drains 982-row backlog through the ESP in tenant-config batches (US-NOT-003 TC-4); binding change is audited (US-INT-004) |
| TC-4 | Dispatcher hits provider timeouts on 6 rows | Rows retry ×3 → failed per BR-NOT-005 (notifications owns row status); the provider's error ALSO stamps the health surface — US-NOT-013 failures view shows rows, US-NOT-004 shows provider "Failed · Retry" |
| TC-5 *(negative)* | Binding manipulated to a disconnected provider (stale config) | Rejected/emptied — a binding must reference a `connected` connection; dispatch home falls back to config-missing, rows wait (US-NOT-003 TC-5) |
| TC-6 *(secret-handling)* | Health/read-model payloads consumed by US-NOT-004/013 | Status + masked summary + error text only — adapter credentials resolved server-side inside the seam at send time, never handed to consumers (BR-INT-003) |
| TC-7 *(isolation)* | Both tenants dispatch at W6 | Each binding resolves within its tenant; Brazos Bend's ESP session never carries a Lone Star Ridge row (US-NOT-002 TC-7 pair) |

**4 · Test Data** — Brazos Bend: mailbox + ESP both connected → selects ESP (volume tenant); 982-row W6 backlog. Lone Star Ridge: mailbox only → default binding. Failure fixture: 6-row timeout Aug 9 (US-NOT-002 TC-3 pair). Stale fixture: ESP disconnected while selected. Actors: Alex Reed, J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Active email-provider binding | S8 (Manage surface) | US-NOT-003 §5 (integrations-owned per-tenant provider config) + B7 per-tenant config rule | binding config on/beside `integration_connections` (🔒 I-2) | ref | user-input / system-derived (sole-connection default) | must reference a connected row; two connected → explicit choice |
| Selection guidance copy | S8 | OQ-074 closure (small=BYO, 6k–10k=ESP) | rendered copy | text | computed-display | guidance, not enforcement |
| Provider health (status/last test/last send error) | S8 Notifications + dashboard | BR-TEN-041 #8 + B7 (Failed · Retry) | read-model columns (last_test_*, last_provider_error) | enum/text/ts | integration / system-derived | dispatcher reports errors in; consumers read-only |
| Channel activation gate | — | OQ-073 closure | channel-config flags (US-NOT-003) | flag | reference-data | email W6 — binding ready ≠ sending |
| Binding audit | — | BR-TEN-016 family | `audit_log` `integration.updated` (binding before/after) | jsonb | system-derived | masked |

**6 · Acceptance**
- Given one comms connection, Then it is the binding; given two, an explicit audited choice is required and nothing auto-picks.
- Given W6, Then the dispatcher drains through the tenant's OWN binding at normal pacing; given no/stale binding, rows wait visibly.
- Given provider failures, Then health reads Failed · Retry on the dispatch home and the dashboard shows the affected rows — credentials never leave the seam.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.
