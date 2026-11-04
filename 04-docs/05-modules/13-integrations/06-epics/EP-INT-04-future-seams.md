# EP-INT-04 — Future seams (the VISIBLE-BUT-LATER cards: real stories, deferred activation)

**Module:** integrations · **Wave:** W7 (rails) / post-v1 v1.1–v2 (per-card labels below) · **Screens:** S8 Settings → Integrations (coming-soon cards) · **Status:** draft epic, stories **deferred** (dispositions all CONFIRMED — PO CL-1 option a, 2026-08-08; per-card law cited per story)

## Scope
**In:** the coming-soon cards as REAL stories — card copy, gating behavior (Connect disabled at UI AND API, wave label rendered), and **what "unlock" requires** per card: **Stripe + Plaid → W7 rails** (OQ-015 as modified/TD-9; BR-PAY-015 capture-intent; webhook_key schema already provisioned) · **Twilio SMS → v1.1** (BR-PAY-017/NFR-21; SMS rows already queue per US-NOT-003) · **QBO/Xero LIVE sync → v2** (BR-LED-020) · **Itron/Sensus MDM → v2 with the NFR-27 AMI capacity gate** (v1 reads = CSV per B7) · **Okta/Azure AD SSO → v2** (BR-IDN-029 no cross-tenant SSO v1; consistent with 2FA v2, BR-IDN-028).
**Out:** the rails/SMS/sync/MDM/SSO implementations themselves (their owning modules' future epics) · v1-REAL cards (EP-INT-01..03) · the Lob/DocPrint card (CL-1-silent — field-map discrepancy I-1, candidate note; NOT silently decided into either column here).

## Capability matrix (list screens only — B9 conformance)
No B9 list screens in this epic.

## Stories

---
id: US-INT-011
epic: EP-INT-04
module: integrations
screens: [S8]
wave: 7
status: deferred
blocked_by: []
depends_on: [US-INT-001, US-INT-002]
journeys: []
rules: [BR-INT-001, BR-INT-011, BR-INT-003]
golden_tests: []
finance_calc: none
---
### US-INT-011 — Payment rails cards: Stripe + Plaid — "Coming soon · W7", gating, and what unlock requires *(deferred → W7)*

**1 · Details** — **Deferred-wave note: the CARD STATE below renders in v1 via US-INT-001's grid; this story's connect behavior activates at W7 with the rails.** As a System Admin, I see the **Stripe** card ("Card + ACH", prototype copy — its "Connected" pill is superseded, field map I-5) and the **Plaid ACH** card ("Bank verification") rendered **"Coming soon · W7"** with Connect disabled at UI and API (BR-INT-001; US-INT-001 TC-5) — because v1 ships **no tenant-side payment processor** (OQ-015 as modified: "NO Stripe… no payment processor in v1"; TD-9: "Plaid/payment rails = W7"; BR-PAY-015 capture-intent-only; autopay capture-only per BR-CUS-059/OQ-059). **Unlock at W7 requires:** the PO rails go-decision executed in payments/customers (charge execution, webhook consumption — `payments.webhook_key` idempotency is ALREADY provisioned in B2 and human-owned 🔒), a PCI scope decision (soc2 mapping §2: "rails W7 = PCI scope decision then"), and this card flipping to v1-REAL behavior through the EXISTING US-INT-002 modal (method OAuth/API-key per A11 keys stripe/plaid) — no new surface, only the gate lifts. Until then the cards are honest signage. Entry: S8 grid. Exit (W7): connectable via US-INT-002.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-011 | No Stripe tenant-side v1; no payment processor v1; Plaid/payment rails = W7; autopay/capture flows are capture-only until rails. | CONFIRMED — OQ-015 CLOSED as modified (PO R8) + TD-9 + BR-PAY-015 + BR-CUS-059 (OQ-059 closure) |
| BR-INT-001 | Stripe/Plaid render VISIBLE-BUT-LATER: coming-soon + W7 label, connect disabled. | CONFIRMED — PO CL-1 option a, 2026-08-08 |
| BR-INT-003 | Even for disabled cards, no credential is ever accepted/stored/logged. | CONFIRMED — see US-INT-002 §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | v1 grid renders the Payments category | Stripe + Plaid cards visible with "Coming soon · W7" + disabled Connect; prototype "Connected · Card + ACH" pill NOT rendered (I-5 supersession) |
| TC-2 | Card click in v1 | Explains the gate (rails ship W7; capture-intent only today per BR-PAY-015) — honest copy, no modal, no dead-end error |
| TC-3 *(negative)* | `POST /integrations/stripe/connect` or `/plaid/connect` in v1 | Rejected server-side with the W7 gate — UI disabling is convenience, enforcement is server-side (IS-6 principle) |
| TC-4 *(secret-handling)* | A key/token posted to the disabled endpoints anyway | Never persisted, never logged, never audited-with-payload — the request is refused before any secret path runs (BR-INT-003) |
| TC-5 *(isolation)* | Any per-tenant flag manipulation attempting an early unlock for one tenant | No such flag exists v1 — the gate is platform-level (CL-1); tenant config cannot open a W7 card (and tenants never see each other's config regardless, RLS) |
| TC-6 | W7 unlock (forward-looking contract) | Gate lifts → cards use the standard US-INT-002 lifecycle; `payments.webhook_key` idempotency (B2, 🔒) and the PCI scope decision are prerequisites, not this surface's inventions |

**4 · Test Data** — v1 grid fixture (Brazos Bend + Lone Star Ridge — identical coming-soon states, platform gate); rejected-connect fixture: Alex posts a Stripe test key sk_test_...4242 → refused, zero persistence. W7 fixture (contract only): rails ruling executed, cards flip.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Coming-soon state + wave label | S8 cards | CL-1 matrix (BR-INT-001) | catalog disposition flags (US-INT-001) | enum | reference-data | coming_soon(W7); platform-level, not tenant |
| Gate enforcement | — | OQ-015/TD-9 + IS-6 server-side principle | connect/test endpoints refuse for gated keys | — | system-derived | UI + API both |
| Webhook idempotency provision | — | B2 (`payments.webhook_key` UNIQUE) — human-owned 🔒 | already in schema; consumed at W7 | text | integration | NOT touched by this pack (CLAUDE.md do-not-touch) |
| Unlock prerequisites note | S8 card copy | soc2 §2 (PCI scope decision at rails) + BR-PAY-015 | rendered copy | text | computed-display | signage only |

**6 · Acceptance**
- Given v1, Then both rails cards are visible, honestly labeled W7, and refuse connection at every layer with zero secret persistence.
- Given W7, Then unlock is a gate-lift into the existing connect lifecycle — no new surface, no schema change here.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.

---
id: US-INT-012
epic: EP-INT-04
module: integrations
screens: [S8]
wave: 8   # post-v1 unlocks govern: Twilio v1.1 · live sync/MDM/SSO v2 (CL-1 labels; matrix row says v1.1/v2)
status: deferred
blocked_by: []
depends_on: [US-INT-001, US-INT-002]
journeys: []
rules: [BR-INT-001, BR-INT-012, BR-INT-013, BR-INT-010, BR-INT-003]
golden_tests: []
finance_calc: none
---
### US-INT-012 — v1.1/v2 seams: Twilio SMS (v1.1) · QBO/Xero live sync (v2) · Itron/Sensus MDM (v2 + NFR-27 gate) · Okta/Azure AD SSO (v2) *(deferred → post-v1)*

**1 · Details** — **Deferred-wave note: card states render in v1 via US-INT-001; connect behavior activates per card at its labeled release (Twilio v1.1 · the rest v2).** As a System Admin, I see four coming-soon groups with per-card unlock law: **Twilio SMS** ("Outbound + short codes", prototype) — "Coming soon · v1.1"; SMS queue rows already accumulate with the v1.1 marker (US-NOT-003 TC-3) and opt-in flags carried; unlock = the Twilio seam activation (BR-PAY-017 text-to-pay rides it; NFR-21; SMS 2FA stays per BR-IDN-024/OQ-027). **QuickBooks Online / Xero live sync** — badge "Live sync — v2" on the v1 file-target cards (US-INT-009); unlock = BR-LED-020's direct-connect v2 (OAuth per A11 keys), riding the SAME recorded-batch idempotency (BR-LED-004 — live sync never bypasses batch records). **Itron MDM / Sensus FlexNet** ("AMI reads via SFTP" / "API integration", prototype) — "Coming soon · v2"; v1 read intake = CSV (B7 "v1 = CSV"); **unlock REQUIRES the NFR-27 AMI gate: re-run the B6 capacity math + Eng-Lead partition sign-off (30–60× read volume) BEFORE any tenant enablement**. **Okta / Azure AD SSO** — "Coming soon · v2"; v1 has per-tenant identity with NO cross-tenant SSO (BR-IDN-029/NFR-11) and 2FA itself is v2 (BR-IDN-028) — SSO sequencing is consistent with that; `sso_links` exists platform-side (B2) as provision only; the prototype's "Available on Scale plan" tier copy is not rendered (plan-gating law = B10/platform territory — CL-1's wave label is the card's v1 copy). All four refuse connection at UI + API in v1 exactly like US-INT-011. Entry: S8 grid. Exit (per release): gate-lift into US-INT-002.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-INT-001 | Twilio v1.1; QBO/Xero live sync v2; Itron/Sensus v2; Okta/Azure AD v2 — all VISIBLE-BUT-LATER with wave labels. | CONFIRMED — PO CL-1 option a, 2026-08-08 |
| BR-INT-012 | MDM/AMI enablement for any tenant requires re-running capacity math + Eng-Lead partition sign-off; v1 read intake = CSV. | CONFIRMED — NFR-27 (B6) + B7 ("AMI… v1 = CSV") |
| BR-INT-013 | SSO = v2; no cross-tenant SSO v1; consistent with 2FA v2. | CONFIRMED — CL-1 + BR-IDN-029/NFR-11 + BR-IDN-028/NFR-12 |
| BR-INT-010 *(consumed)* | Live accounting sync = v2 and rides recorded-batch idempotency when it lands. | CONFIRMED — BR-LED-020 + BR-LED-004 |
| BR-INT-003 | No credential accepted/stored/logged for any gated card. | CONFIRMED — see US-INT-002 §2 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | v1 grid | Twilio "Coming soon · v1.1"; Itron/Sensus/SSO "Coming soon · v2"; QBO/Xero cards = v1-REAL file targets + "Live sync — v2" badge; SSO tier copy absent (wave label instead) |
| TC-2 | SMS rows meanwhile | 47 opt-in SMS reminder rows rest `queued` with the v1.1 marker (US-NOT-003 TC-3) — the card state and the queue state tell the same story |
| TC-3 | MDM unlock request (v2, forward-looking) | Blocked until the NFR-27 gate artifacts exist (capacity re-run + Eng-Lead sign-off recorded) — the gate is a precondition of ENABLEMENT, per tenant, not just a release flag |
| TC-4 *(negative)* | `POST /integrations/twilio/connect`, `/itron/connect`, `/sso/connect` in v1 | All rejected server-side with the card's wave label (US-INT-011 TC-3 pattern) |
| TC-5 *(negative)* | v2 live-sync attempt imagined to bypass export batches | Contract states it CANNOT: live sync rides BR-LED-004 recorded-batch idempotency — no unrecorded handover path will exist |
| TC-6 *(secret-handling)* | Credentials posted to any gated endpoint | Refused pre-secret-path; zero persistence/logging (BR-INT-003) |
| TC-7 *(isolation)* | Per-tenant early-unlock attempt / cross-tenant visibility | Platform gate (CL-1) — no tenant flag opens it; tenant configs mutually invisible (RLS); `sso_links` platform table carries no tenant credential material v1 |

**4 · Test Data** — Brazos Bend: 47 queued SMS rows (US-NOT-003 fixture); QBO file target live + v2 badge; MDM gate fixture (v2 contract): capacity re-run doc + Eng-Lead sign-off ref required before Itron enablement for the 40k-account tenant class (B6 math). Rejected-connect fixtures: Twilio SID/token, Okta client secret → refused, zero persistence.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Wave labels per card | S8 | CL-1 matrix (BR-INT-001) | catalog disposition flags (US-INT-001) | enum | reference-data | v1.1 \| v2 rendered on card |
| SMS deferred marker linkage | S8 + Notifications tab | US-NOT-003 §5 (v1.1 marker) | channel-config flags | flag | reference-data | card + channel states agree |
| AMI gate artifacts (v2) | — | NFR-27 (B6) | enablement precondition records (v2 design) | refs | system-derived | REQUIRED before tenant MDM enablement |
| Live-sync-rides-batches contract (v2) | — | BR-LED-020 + BR-LED-004 | `export_batches` idempotency (existing) | — | system-derived | no unrecorded handover, ever |
| `sso_links` provision | — | B2 identity tables (platform, no RLS) | exists; unused v1 (BR-IDN-029) | rows | system-derived | no UI v1 |
| Gate enforcement | — | IS-6 server-side principle | connect/test refuse for gated keys | — | system-derived | UI + API |

**6 · Acceptance**
- Given v1, Then all four groups are visible with their true labels, refuse connection at every layer, and hold zero credentials.
- Given their releases, Then each unlocks through the existing lifecycle under its cited law — Twilio into the dispatcher seam, live sync onto recorded batches, MDM only past the NFR-27 gate, SSO under the v2 identity rules.

**7 · Finance Calculation** — N/A — no money math.

**8 · Open Questions** — None.
