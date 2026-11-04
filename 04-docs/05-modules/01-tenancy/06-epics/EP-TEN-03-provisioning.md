# EP-TEN-03 — Tenant provisioning & reference-data seeding

**Module:** tenancy · **Wave:** W0 · **Screens:** S111 (load-defaults toggle), S114 (commit), S62 (post-signup checklist — OQ-034 CLOSED), S1 (public landing), S8 (Settings — sample-data removal surface, placement OQ-084) · **Status:** draft

## Scope
**In:** the server-side act of creating a tenant when the signup wizard commits ("Create utility & go live"): tenant row + subdomain, owner user + membership, trial subscription, enabled services, seeding of standard reference data from platform fixtures, and the post-signup checklist that surfaces the Company-profile gaps deliberately kept out of onboarding (legal name, EIN, state utility ID, mailing address, logo, brand, remittance — A1 addendum 2026-08-08). Failure/retry behavior so no half-seeded tenant ever goes active (BR-TEN-001). **Added 2026-08-10 (BR-TEN-056):** the background **sample-data job** that fills a new tenant with realistic, tagged, removable sample records across the modules, the reference-catalog completion DEF-017 exposed, and the honest S62 reporting DEF-016 exposed — US-TEN-019. **Added 2026-08-10 (US-TEN-020):** how an ALREADY-PROVISIONED tenant receives reference data shipped after it signed up — the fixture-version sweep over the existing `reference_seed_runs` ledger, its mandatory dry-run, the "which tenants are behind" read, and the version-bump policy.
**Out:** the onboarding wizard UI itself (S110–S114 — wave 8, EP-TEN onboarding epics), pricing (S1 plan catalogue), subscription/implementation invoicing (S107–S109, B10, wave 8), welcome email content (notifications module), Company-tab editing (EP-TEN-05), the Reference-data card grid and per-list CRUD (EP-TEN-07 — US-TEN-019 fills those lists, it does not render them), the bill run itself (EP-BIL).

## Capability matrix (list screens only — B9 conformance)
None — this epic has no list screens. The post-signup checklist is a fixed-item progress view, not a table.

## Stories

---
```yaml
id: US-TEN-001
epic: EP-TEN-03
module: tenancy
screens: [S114]
wave: 0
status: draft
blocked_by: []
depends_on: []
journeys: [J1]
rules: [BR-TEN-001, BR-TEN-003, BR-TEN-010, BR-TEN-011, BR-TEN-013, BR-TEN-014, BR-TEN-016]
golden_tests: []
finance_calc: none
```
### US-TEN-001 — Idempotent tenant provisioning at signup commit

**1 · Details** — As a self-signup Owner, I want my utility fully created the moment I click "Create utility & go live" (S114), so that I land on a working dashboard with my services, trial, and login in place. Entry: S114 commit. Exit: authenticated redirect to the post-signup checklist / dashboard. Provisioning creates, in one transaction: `tenants` row, owner `users` + `tenant_memberships` (role System Admin), `subscriptions` (trial), one `tenant_services` row per selected service.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-001 | Tenant provisioning is idempotent; no half-seeded tenant goes active | CONFIRMED — A11 (existing rule) |
| BR-TEN-010 | Provisioning is a single atomic transaction (tenant + owner + membership + trial subscription + services + seed); the natural idempotency key is the subdomain — a repeat request with the same subdomain + owner email returns the existing tenant, never a duplicate | PROPOSED — refines BR-TEN-001; derived from B2 `tenants.subdomain UNIQUE` + CLAUDE.md #6 idempotency pattern |
| BR-TEN-011 | Subdomain: lowercase DNS label `[a-z0-9-]`, 3–63 chars, no leading/trailing hyphen, globally unique, reserved names blocked (www, app, api, admin, mail, billing, support, status, help, bynry, smartbillhub) | PROPOSED — A2 marks charset/uniqueness UNKNOWN; derived from RFC-1035 label rules + B2 UNIQUE constraint |
| BR-TEN-014 | Provisioning creates the subscription with status `trial`, `trial_ends_at = provisioned_at + 14 days`, no payment method required | CONFIRMED — A1 addendum 2026-08-08 ("no card at signup") + B2 `trial_ends_at` comment (14-day real constant) |
| BR-TEN-003 | `tenant_id` comes from membership + subdomain server-side, never client input | CONFIRMED — B3 (existing rule) |
| BR-TEN-016 | Every provisioning and Settings write produces `audit_log` rows (`tenant.provisioned`, `reference.seeded`, `settings.updated` — with before/after) | PROPOSED — derived from S8 header copy "Changes are audit-logged" + CLAUDE.md #7 |
| BR-TEN-013 | Provisioning writes other modules' tables only via those modules' service functions, never directly | CONFIRMED — B1 boundary rule (module overview) |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Commit S114 for "Brazos Bend Utilities", subdomain `brazosbend`, services Electric + Water, Growth plan | One `tenants` row, owner user `dana@brazosbendutilities.com` with System Admin membership, subscription `trial` with `trial_ends_at` = now + 14 d, exactly 2 `tenant_services` rows; audit_log `tenant.provisioned` present |
| TC-2 | Same POST replayed (double-click / network retry) with identical subdomain + owner email | 200 with the SAME tenant id; row counts unchanged; no duplicate subscription or services |
| TC-3 (neg) | Subdomain `brazosbend` already owned by a different owner email | 409 conflict, "That web address is taken"; no rows written |
| TC-4 (neg) | Subdomain `-brazos_bend!` (bad charset) or `api` (reserved) | 422 validation error naming the rule; nothing created |
| TC-5 (isolation) | After provisioning, a session with `app.tenant_id` = Lone Star Ridge queries accounts/services | Sees zero Brazos Bend rows; RLS FORCE verified by the isolation suite |

**4 · Test Data** — Tenant: **Brazos Bend Utilities** (legal entity Brazos Bend Utility District No. 1), subdomain `brazosbend`, state Texas, services Electric + Water, plan Growth ($5,000/mo), owner Dana Whitfield · `dana@brazosbendutilities.com` · +1 (281) 555-0164. Second tenant for isolation: **Lone Star Ridge Water Co-op**, subdomain `lonestarridge`. Provisioned 2026-08-08 14:05 CT → `trial_ends_at` 2026-08-22.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Utility name | S110 | A1 addendum 2026-08-08 | tenants.name | text | user-input | required, ≤120 chars |
| Web address | S110 | A2 §S4 (subdomain) | tenants.subdomain | text | user-input | BR-TEN-011 |
| State | S110 | A2 §S4 | tenants.state | text | user-input | US state / DC / PR list |
| Services billed | S110 | A2 §S4 services[] | tenant_services.service | service_type enum | user-input | ≥1 of the 6 |
| Currency | S111 | A2 §S5 | tenants.currency | CHAR(3) | user-input (defaulted USD) | USD or CAD |
| Plan | S112 | A1 addendum 2026-08-08 | subscriptions.plan_id | uuid FK | user-input (Growth pre-selected) | one of 3 platform plans |
| Trial end | — | A1 addendum ("14-day trial") | subscriptions.trial_ends_at | timestamptz | system-derived | provisioned_at + 14 d |
| Owner name / email / password / mobile | S114 | A2 §S6 | users.full_name / users.email / users.password_hash / users.phone | text / citext / hash / text | user-input | email format; password policy per Security settings; mobile optional |
| Owner role | — | A4 addendum (3 predefined roles) | tenant_memberships.role_id | uuid FK | system-derived | = System Admin |
| Provisioned at | — | GAP (needed for trial + checklist) | **PROPOSED-SCHEMA:** tenants.provisioned_at | timestamptz | system-derived | set once |

**6 · Acceptance** — Given a completed S110–S114 wizard, When the owner clicks "Create utility & go live", Then within one transaction the tenant, owner login, System Admin membership, trial subscription (+14 d) and per-service rows exist, the owner is signed in to that tenant, an audit row records the provisioning — and replaying the same request changes nothing and returns the same tenant.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-034 | The post-signup checklist screen has no A1 screen ID (S110–S114 cover the wizard only) — assign one from the reserved S61–S90 range | ticket vocabulary for this epic's UI work | Product Owner (chat session) | OPEN |

---
```yaml
id: US-TEN-002
epic: EP-TEN-03
module: tenancy
screens: [S111]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-001]
journeys: [J1]
rules: [BR-TEN-012, BR-TEN-013, BR-TEN-016]
golden_tests: []
finance_calc: none
```
### US-TEN-002 — Seed standard reference data from platform fixtures

**1 · Details** — As a self-signup Owner, I want "Load standard charge codes & reference data (recommended)" (S111 toggle, default on) to fill my lookup lists with sensible US-utility defaults, so that every dropdown works on day one without manual data entry. Runs inside the provisioning transaction (US-TEN-001). Seeds: charge codes (LATE, CONN, DISC, NSF, DEPO-R, TAMPER), reason codes, UoM (kWh, kW, kgal, ccf, therm, month), payment methods, meter/asset types & statuses, tax jurisdictions for the selected state. Exit: lists visible in Settings → Reference data (EP-TEN-07).

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-012 | Seeding copies from **versioned platform fixtures** into tenant-scoped tables; per-list idempotent (upsert by code); runs only when the S111 toggle is on; later fixture versions NEVER overwrite rows the tenant has touched | PROPOSED — derived from A2 §S5 load_defaults ("seeds lookup tables") + A6 S6 row ("seeded lookups") + BR-TEN-001 idempotency |
| BR-TEN-013 | Cross-module seed writes (charges, taxes → rating; reason codes → billing; payment methods → payments; asset types/statuses → assets) go through the owning module's service functions only | CONFIRMED — B1 boundary rule |
| BR-TEN-016 | Each seeded list writes an `audit_log` row (`reference.seeded`, list + fixture version + row count) | PROPOSED — see US-TEN-001 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Provision Brazos Bend with toggle ON, state Texas | `charges` has the 6 standard codes; UoM list has 6 entries; TX jurisdiction entries present; `reference_seed_runs` records one row per list with fixture version `2026.08` |
| TC-2 | Provision with toggle OFF | All reference lists empty; Reference-data cards show 0 with empty-state per A18; no seed audit rows |
| TC-3 | Re-run seeding for the same tenant (retry after crash) | Row counts unchanged (upsert by code); single seed-run record per list per version |
| TC-4 (neg) | Fixture set for the selected state is missing/corrupt | Whole provisioning transaction rolls back (BR-TEN-001 — no half-seeded tenant); actionable error surfaced |
| TC-5 (neg) | Tenant renames seeded charge code LATE → "Late payment penalty", then platform ships fixture `2026.09` | Tenant's edited row untouched; only never-touched rows may receive fixture updates |
| TC-6 (isolation) | Seed Brazos Bend, then query charge codes as Lone Star Ridge | Lone Star Ridge sees only its own (or zero) rows |

**4 · Test Data** — Fixture set `us-tx · 2026.08`. Charge codes: LATE (1.5% · $5 min), CONN $45, DISC $45, NSF $30, DEPO-R, TAMPER (amounts pending OQ-fee ratification — A17 #9, seeded as fixture values). UoM: kWh, kW (demand), kgal, ccf, therm, month. Tax: Texas State 6.25% + Local 2.00% (TX Comptroller). Payment methods: ACH, card, check, cash, lockbox, wire.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Load defaults toggle | S111 | A2 §S5 load_defaults | (drives behavior; not stored) | boolean | user-input | — |
| Charge codes | — | prototype-extracted (S8 lookup card) | charges.code/name/amount/percent/min_amount | text / NUMERIC(18,6) | reference-data (seeded) | unique (tenant_id, code) |
| Tax jurisdiction + rate | — | A2 §S5 tax_region · B2 taxes | taxes.name/rate (+ jurisdiction link — OQ-032) | NUMERIC(18,6) | reference-data (seeded) | rate ≥ 0 |
| UoM entries | — | prototype-extracted (S8 UoM card) | **PROPOSED-SCHEMA:** uoms(tenant_id, code, name, active) | text | reference-data (seeded) | unique (tenant_id, lower(code)) |
| Reason codes | — | prototype-extracted (S22 Adjust reasons) | **PROPOSED-SCHEMA:** reason_codes(tenant_id, code, name, default_gl_account_id, active) | text | reference-data (seeded) | unique (tenant_id, code) |
| Seed run record | — | GAP (idempotency evidence) | **PROPOSED-SCHEMA:** reference_seed_runs(tenant_id, list_code, fixture_version, seeded_count, seeded_at) | — | system-derived | UNIQUE (tenant_id, list_code, fixture_version) |

**6 · Acceptance** — Given the toggle is on at S111, When provisioning commits, Then every reference list holds the fixture rows for the tenant's state, a seed-run record exists per list, re-running changes nothing, and with the toggle off every list is empty with a valid empty state.

**7 · Finance Calculation** — N/A (seeded charge amounts are fixture values; the money rules that consume them live in B4, not here).

**8 · Open Questions** — None minted here (jurisdiction scoping is OQ-032, minted in EP-TEN-07 where the conflict is managed).

---
```yaml
id: US-TEN-003
epic: EP-TEN-03
module: tenancy
screens: [S62]
wave: 0
status: draft
blocked_by: []   # OQ-034 CLOSED → S62 assigned (PO R6); entry remains automatic after S114
depends_on: [US-TEN-002, US-TEN-005]
journeys: [J1]
rules: [BR-TEN-015, BR-TEN-016]
golden_tests: []
finance_calc: none
```
### US-TEN-003 — Post-signup checklist surfacing Company gaps

**1 · Details** — As a new Owner, I want a "Get set up" checklist right after signup, so that the identity data deliberately kept out of onboarding (legal name, EIN, state utility ID, mailing address, logo, brand, remittance — A1 addendum) gets filled before my first real bill. Entry: automatic after S114; re-entry from the dashboard until complete. Items (prototype): Company profile · Services & UoM · Rate templates & taxes · Fiscal calendar & billing cycles · Numbering & documents · Invite your team. Each deep-links to its Settings tab. Exits: "Continue setup →" or "Finish later — open the app".

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-015 | Checklist state is **computed from live data**, not a stored to-do: an item shows complete when its underlying fields are filled (e.g. Company profile = legal name + EIN + mailing address + remit-to present); manual mark-done is allowed for advisory items and recorded; "Finish later" dismisses but the checklist stays reachable until all items complete | PROPOSED — derived from prototype checklist (toggleable items, progress meta) + A1 addendum "prompted by the post-signup checklist" |
| BR-TEN-016 | Mark-done and dismiss actions are audit-logged | PROPOSED — see US-TEN-001 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Fresh Brazos Bend tenant opens the checklist | Company profile item INCOMPLETE (no EIN/legal name yet); Services item complete (Electric + Water enabled at signup); progress reads "1 of 6 complete" |
| TC-2 | Owner fills Company profile via EP-TEN-05 and returns | Company item now complete without any manual toggle; progress count advanced |
| TC-3 | Owner clicks "Finish later — open the app" | Lands on dashboard; checklist entry point still visible; state persisted across sessions |
| TC-4 (neg) | Billing Clerk (Marcus Vega) tries to open the checklist's Settings deep-links | Settings items render disabled-with-reason (IS-6); server rejects writes (A4: Settings = System Admin only) |
| TC-5 (isolation) | Lone Star Ridge admin opens their checklist | Sees only Lone Star Ridge completion state; Brazos Bend's manual mark-dones invisible |

**4 · Test Data** — Brazos Bend immediately post-signup: name + subdomain + 2 services + trial present; legal name, EIN 74-3182640, state utility ID "TX CCN 13148", mailing address "9410 FM 1093 Rd, Katy, TX 77494", logo, remit-to all absent → Company item incomplete. Users: Dana Whitfield (System Admin), Marcus Vega (Billing Clerk, invited later).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Item completion (computed) | checklist (OQ-034) | prototype-extracted (chk-items) | derived from tenants.* / tenant_services / number_series | boolean per item | computed-display | per-item predicate in BR-TEN-015 |
| Manual mark-done + dismissed flags | checklist | prototype-extracted (toggle behavior) | **PROPOSED-SCHEMA:** tenants.checklist_state jsonb | jsonb | user-input | keys limited to known item codes |
| Progress meter / est. minutes | checklist | prototype-extracted ("2 of 6 · 8 minutes") | — | computed | computed-display | — |

**6 · Acceptance** — Given a freshly provisioned tenant, When the owner completes signup, Then the checklist appears with per-item state computed from real data, deep-links land on the right Settings tab, completing data (not clicking) completes items, and dismissal persists without blocking later re-entry.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-034 | (minted in US-TEN-001) checklist screen needs an A1 ID | UI ticket vocabulary only — behavior above is buildable | Product Owner (chat session) | OPEN |

---
```yaml
id: US-TEN-004
epic: EP-TEN-03
module: tenancy
screens: [S114]
wave: 0
status: draft
blocked_by: []
depends_on: [US-TEN-001, US-TEN-002]
journeys: []
rules: [BR-TEN-001, BR-TEN-010, BR-TEN-011, BR-TEN-016]
golden_tests: []
finance_calc: none
```
### US-TEN-004 — Provisioning failure handling, retry, and conflict paths

**1 · Details** — As the platform, I must guarantee a failed provisioning attempt leaves nothing behind and a retry succeeds cleanly, so that no half-seeded tenant ever goes active (BR-TEN-001) and no prospect is stranded. Covers: mid-transaction crash, duplicate-subdomain conflict, owner email already registered on another tenant, and post-failure retry. Exit: either a fully provisioned tenant or a clean, explained failure at S114.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-001 / BR-TEN-010 | Atomic + idempotent (see US-TEN-001); a crashed attempt is invisible — rollback, not cleanup | CONFIRMED / PROPOSED |
| BR-TEN-011 | Subdomain conflicts are detected server-side at commit even if the S110 live availability check passed earlier (race) | PROPOSED — derived from B2 UNIQUE + A1 addendum friction-controls (live availability check) |
| BR-TEN-016 | Failed attempts write an audit/ops trace (`tenant.provision_failed`, no PII in the reason) | PROPOSED |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 (neg) | Kill the transaction after `tenants` insert but before seeding (fault injection) | Zero rows remain for that subdomain; sign-in with the attempted owner email fails; retry from S114 succeeds fully |
| TC-2 (neg) | Two prospects submit subdomain `brazosbend` within the same second | Exactly one tenant created; the loser gets 409 with "That web address is taken — pick another"; wizard returns to S110 field with value preserved |
| TC-3 | Owner email `dana@brazosbendutilities.com` already exists as a user on another tenant | Provisioning succeeds: a NEW tenant-scoped user is created on the new tenant with its own credentials (BR-IDN-029, B2 r11 — same email in two tenants = two separate users); the other tenant's user, password, and sessions are never touched |
| TC-4 (neg) | Same email + same subdomain replay after success | Idempotent 200 (US-TEN-001 TC-2), not a duplicate-email error |
| TC-5 (isolation) | After TC-2's failed attempt, Lone Star Ridge queries `tenants`-scoped data | No orphan rows visible anywhere; isolation suite green |

**4 · Test Data** — Conflicting signups: Dana Whitfield (`dana@brazosbendutilities.com`) vs. J. Okafor (`j.okafor@lsrwater.coop`) both requesting `brazosbend` at 2026-08-08 14:05:31 CT. Existing-user case: Dana already a Billing Clerk on `lonestarridge` before creating Brazos Bend.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Subdomain availability (live check) | S110 | A1 addendum (friction controls) | reads tenants.subdomain | boolean | computed-display | advisory only; commit re-checks |
| Conflict error copy | S114 | GAP — A13 notes no error strings designed | — | text | computed-display | A18 failed-with-retry pattern |
| Failure trace | — | BR-TEN-016 | audit_log (action=`tenant.provision_failed`) | jsonb | system-derived | no password/PII in payload |

**6 · Acceptance** — Given any provisioning failure mode above, When it occurs, Then the database shows either a complete tenant or nothing, the user gets an A18-pattern error with a retry path, a retry succeeds without manual cleanup, and an owner email that exists on another tenant yields a new, separate tenant-scoped user (BR-IDN-029) with the other tenant untouched.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
```yaml
id: US-TEN-018
epic: EP-TEN-03
module: tenancy
screens: [S1]
wave: 1
status: draft
blocked_by: []
depends_on: [US-TEN-001]
journeys: []
rules: [BR-TEN-002, BR-TEN-054, BR-TEN-055]
golden_tests: []
finance_calc: none
```
### US-TEN-018 — S1 public landing page (the whole page, not just the plan cards)

**1 · Details** — As a prospective utility, I want the landing page to tell me what this product is before it asks me to choose a plan, so that I can decide whether it is for me. Entry: `smartbillhub.bynry.com/`. Contents, in the prototype's order: nav (Pricing · Features · Docs · Sign in · Start free) → hero → the three plan cards → "Every plan includes" → the advisory footnote.

**Why this story exists.** A1 has listed S1 since the inventory was written and **no story ever owned it**. The page was therefore built to the ratified `GET /public/pricing-plans` contract and nothing else — plan cards and an advisory line — and that gap was recorded in the file's own trace header as `E1` and never picked up. The PO found it on the first live deployment (2026-08-10) by comparing the deployed page against `05-prototype/UtilityBilling.html`, which is the ratified source for layout and copy. Everything in this story already exists in the prototype; none of it is invented here.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-002 | Connection ranges are **advisory sizing, never a contractual cap** — the footnote saying so stays on the page, and no card implies billing stops at the range | CONFIRMED (existing) |
| BR-TEN-054 | **Prices, names and ranges come from the API; the surrounding marketing copy does not.** `GET /public/pricing-plans` returns `code · name · price_month · currency · min_accounts · max_accounts` and no marketing text, so per-plan blurbs and feature bullets are page copy keyed by plan `code`. A plan whose code has no copy still renders — name, price and range from the API, bullets omitted — because a new plan in the catalogue must never produce a blank card or a crash | PROPOSED — derives from the endpoint's actual shape (11b §2.1) + prototype copy |
| BR-TEN-055 | Nav items with no destination in v1 (**Features**, **Docs**) are **not rendered** rather than rendered dead. A link that goes nowhere on a prospect-facing page is worse than an absent one, and inventing those pages is out of this story's scope | PROPOSED — Eng-Lead; the prototype's nav is design reference, not a commitment that every target exists |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Load `/` with the API serving three plans | Hero headline "Billing that fits your one-person office." and its sub-paragraph render above the cards |
| TC-2 | Same | Three cards: Starter $1,000, Growth $5,000, Scale $8,000 — each with its blurb and five bullets, prices from the API through MoneyCell (BR-SHL-023) |
| TC-3 | Same | "Every plan includes" renders four columns: Services · Meter-to-cash · Multi-tenant · Compliance |
| TC-4 | Same | Both hero CTAs present: "Start free — 14 days" → `/signup`, "Book a walkthrough" |
| TC-5 | API returns a plan with code `enterprise`, unknown to the copy table | Card renders with API name, price and range; no bullets; no crash and no empty bullet list (BR-TEN-054) |
| TC-6 (neg) | API down (the live 502 of 2026-08-10) | Hero, "Every plan includes" and the footnote still render — only the cards are replaced by the failed state, which now shows `HTTP 502` (US-IDN-011's diagnostic). A prospect still learns what the product is |
| TC-7 (neg) | Nav | No "Features" or "Docs" link is rendered while those pages do not exist (BR-TEN-055) |
| TC-8 | Money rendering | Every price goes through MoneyCell; no price string is concatenated or formatted in this file (CLAUDE.md #2) |

**4 · Test Data** — The seeded catalogue (tenancy migration 0005): `starter` $1,000 / 0–300 · `growth` $5,000 / 300–1,000 · `scale` $8,000 / 1,000–3,000, all USD. Plus a synthetic `enterprise` $12,000 / 3,000–null for TC-5.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Hero headline, sub-paragraph, CTA labels | S1 | prototype-extracted | none — page copy | text | reference-data | i18n keys; no server prose (TD-16) |
| Plan name · price · currency · range | S1 cards | 11b §2.1 | `subscription_plans` | text · NUMERIC(18,6) · CHAR(3) · int | integration (API) | rendered by MoneyCell; never recomputed |
| Plan blurb + feature bullets | S1 cards | prototype-extracted | none — page copy keyed by `code` | text | reference-data | absent code ⇒ omit bullets, still render the card |
| "Every plan includes" four columns | S1 | prototype-extracted | none — page copy | text | reference-data | — |
| Advisory footnote | S1 | BR-TEN-002 | none | text | reference-data | must not be removed |

**6 · Acceptance** — **Given** the public catalogue is served, **when** a prospect opens `/`, **then** they see the hero, three priced cards with blurbs and bullets, the four "Every plan includes" columns and the advisory footnote — matching `05-prototype/UtilityBilling.html`; **and when** the API is down, **then** everything except the cards still renders and the failure names its status code.

**7 · Finance Calculation** — N/A. Prices are displayed exactly as the API sends them; nothing on this page computes money.

**8 · Open Questions** — None. (Features and Docs pages are out of scope by BR-TEN-055, not open questions.)

---
```yaml
id: US-TEN-019
epic: EP-TEN-03
module: tenancy
screens: [S8, S62]
wave: 2
status: partial          # 2026-08-15 — the REPORT half only; see the AMENDMENT under §8
blocked_by: []           # was [OQ-084]; fully CLOSED 2026-08-10 (placement + the marker)
depends_on: [US-TEN-001, US-TEN-002, US-TEN-003, US-TEN-009, US-RAT-002, US-MET-003, US-MET-010, US-AST-002, US-CUS-003]
journeys: [J1]
rules: [BR-TEN-001, BR-TEN-010, BR-TEN-012, BR-TEN-013, BR-TEN-015, BR-TEN-016, BR-TEN-034, BR-TEN-036, BR-TEN-056, BR-TEN-057, BR-TEN-058, BR-TEN-059, BR-TEN-060, BR-TEN-061, BR-TEN-062, BR-TEN-063, BR-TEN-064]
golden_tests: []
finance_calc: none
```
### US-TEN-019 — Tenant sample data: seed it, tag it, report it, remove it

**1 · Details** — As a new Owner who has just finished signup, I want my utility to open with realistic records already in it — a couple of premises, their units and meters, a handful of accounts and two cycles of reads — and one place in Settings to sweep all of it away, so that I can learn the product on data that looks like my own instead of on eleven empty states, and start clean the day I import the real thing. Entry: the tenant is provisioned (US-TEN-001 commit). The job runs **after** that transaction commits, never inside it (BR-TEN-056 clause 3), and its progress and honesty report render on **S62**. Exit: the operator either keeps the sample set or removes it from **S8 Settings** (placement OQ-084), which deletes the whole tagged set in one transaction.

The story has four parts and they are deliberately in one story because they are one failure:
1. **Catalogue completion (DEF-017).** Seven reference lists that every module needs — meter types, read methods, asset types, asset lifecycle stages, account statuses, premises types, plus the platform `account_types` — are in no fixture and no seeder today. They are *not* sample data; they are the operator's real vocabulary (BR-TEN-058), so they join the **BR-TEN-012** fixture path, not the sample job.
2. **The sample records.** Premises → units → service points → assets → accounts (+ customer, contacts, addresses, service agreements) → meter reads, every row tagged `is_sample` (BR-TEN-057). It **stops at reads** — nothing reaches `invoices`, `invoice_lines`, `payments` or `journal_entries` (BR-TEN-056 clause 1 / DB-4).
3. **The honest report (DEF-016).** A module whose seeding seam is not wired is *named on S62*, not silently skipped into a summary nobody reads (BR-TEN-060).
4. **Removal.** One transaction, `is_sample = true` only, in a fixed reverse-dependency order because B2 declares **no `ON DELETE CASCADE`** on any of these FKs (BR-TEN-061).

**Why this story exists.** On 2026-08-10 the PO opened Settings → Reference data on the live deployment and found empty cards. The decision-log entry for that day reframes it as **two** defects, not one: **DEF-016** — the fixture covered four lists and `charge_codes` *silently skipped* because rating's seeding seam was never written, with the skip reported into a summary nobody reads (BR-TEN-013 skip-until-wired working exactly as designed, and invisible); **DEF-017** — six lists were never in the fixture or the seeder at all, and neither were plans or rate schedules. The PO's ruling that day (**OQ-079 → BR-TEN-056**) is the prevention for both. This story implements that ruling; it decides nothing the ruling left open.

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-056 | **Tenant sample data.** (1) It **stops at reads** — never `invoices`, `invoice_lines`, `payments`, `journal_entries`, because those are append-only (DB-4) and a sample row there could never be removed and would have to be excluded from every financial report forever; running the first bill is the operator's own act. (2) **Every sample row is tagged**, so Settings can remove the whole set in one transaction. (3) The job runs in the **BACKGROUND**, never inline in signup, and **reports honestly on the S62 checklist** when a module's seam is not wired | CONFIRMED — Product Owner 2026-08-10 (OQ-079 closure); tenancy 02-business-rules.md |
| BR-TEN-057 | **The tag is a column on the owning row**, not a registry: `is_sample boolean NOT NULL DEFAULT false` on each sampled table, written **only** by that module's own service function on the sample path, never by tenancy directly. No central `sample_rows(table, pk)` index exists — building one would make every sample insert a cross-module write | PROPOSED — derived from BR-TEN-013 (cross-module writes forbidden) + B2 r17.1/DB-16, which rejected a shared value table for custom fields for the identical reason and put the column on the owning row + BR-TEN-056 (2) |
| BR-TEN-058 | **Reference vocabulary is not sample data.** The catalogues seeded by BR-TEN-012 (UoM, charge codes, reason codes, payment methods, tax jurisdictions, and the seven of BR-TEN-059) carry **no** `is_sample` column and removal never touches them. They arrive by a different mechanism (the S111-gated fixture copy), they are the operator's own vocabulary once touched, and seeded reference rows are `is_system` — "deactivatable, never deletable" | PROPOSED — derived from BR-TEN-012 (separate, versioned, S111-gated path) + BR-TEN-036 (seeded + tenant-extensible) + BR-AST-031 (seeded stages `is_system`, never deletable) + BR-TEN-034 (Used-by > 0 blocks hard delete) |
| BR-TEN-065 | **Sample accounts are seeded NON-BILLABLE (PO ruling 2026-08-10, OQ-080).** Every sample account is created in the `Pending activation` status, whose behaviour class is `non_billable` (BR-CUS-055). This closes the gap between BR-TEN-056's *seed* boundary and its *run* boundary: the bill run's existing account selector already skips non-billable statuses, so no new exclusion predicate, no `is_sample` check in billing, and no change to the bill run is required — sample data cannot become an append-only invoice by accident. **Accepted consequence, stated rather than buried:** the sample set therefore cannot demonstrate a bill run. An operator who wants to see one activates an account first, which is their own act and drops that account out of the removable set by their choice, not by surprise | **CONFIRMED** |
| BR-TEN-066 | **Removal is partial-and-named, not all-or-nothing (PO 2026-08-10, OQ-081).** One transaction deletes every sample row nothing real references, and returns the survivors BY NAME with the reason each was kept. Refusing the whole removal would let a single attachment strand the entire set; detaching would silently edit the operator's own data. BR-TEN-034 holds — a referenced row is not deleted | **CONFIRMED** |
| BR-TEN-067 | **Structural catalogues are exempt from the S111 toggle (PO 2026-08-10, OQ-082).** Meter types, read methods, asset types, asset lifecycle stages, account statuses and premises types ALWAYS seed: they are vocabulary the schema requires, not sample content — an account cannot exist without a status. The toggle governs sample RECORDS only. Narrows US-TEN-002 TC-2 | **CONFIRMED** |
| BR-TEN-068 | **Sample plans and rate schedules are tagged, and PROMOTED on first real attachment (PO 2026-08-10, OQ-083).** They carry `is_sample` and go with the set; when a non-sample account references one, the tag is dropped and it becomes the operator's own. Avoids both failure modes: removal orphaning a real service agreement, and demo pricing surviving removal unnoticed. Promotion is a write and is audited (CLAUDE.md rule 7) | **CONFIRMED** |
| BR-TEN-069 | **Both sample-data actions live on Settings → Company profile (PO 2026-08-10, OQ-084).** `Fill my tenant with sample data` (BR-TEN-064) and `Remove sample data` (BR-TEN-056 clause 2) sit on the same tab. **The visible sample MARKER is NOT ruled** and stays open under OQ-084 | **CONFIRMED** (placement only) |
| BR-TEN-059 | **DEF-017 fix — seven catalogues join the BR-TEN-012 fixture** with their already-ratified values: meter types 5 (AMI · AMR · walk-by · sub-meter · master) · read methods **8** (AMI · AMR · walk-by · Manual · Mobile · Drive-by · Self-read · Field visit — ⚠ **this read *"5 (AMI · AMR · walk-by · Manual · Mobile)"* until 2026-08-27**; BR-MET-142, the PO ruling closing OQ-392, added the last three, and BR-AST-043 is the owning rule. Fixture serial V2.48.0.2) · asset types 12 (meter · net_meter · sub_meter · backflow · comms · pv · battery · ev_charger · transformer · generator, + Container/Cart · Modem/CPE) · asset lifecycle stages 5 (Inventory/Spare · Installed/Active · Needs repair · In repair · Retired, each mapped to a behavior class) · account statuses 5 with behavior classes (Pending activation non-billable · Active billable · Marked disconnect billable · Vacation hold/Suspended billable-base-only · Closed terminal) · premises types 5 (Apartment complex · Commercial building · Single-family · Mixed-use · Mobile-home park). **`account_types` is different**: B2 r5 #12 makes it a PLATFORM table (residential/commercial/industrial/government, no `tenant_id`, RLS-excluded), so it is seeded by a **platform migration**, not by the per-tenant fixture | VALUES CONFIRMED per list — BR-AST-043 · BR-AST-004 + BR-AST-042 · BR-AST-031 · BR-CUS-055 (incl. OQ-064 class seed) · BR-MET-034 · B2 r5 #12 + D5. PROPOSED — that they belong in the BR-TEN-012 fixture (derived: BR-TEN-036 calls them seeded, and BR-TEN-012 is the only seeding mechanism that exists) |
| BR-TEN-060 | **DEF-016 fix — an unwired seam is a named line on S62, not a skip.** For every module in the sample set the job records a `sample_data_runs` row with an explicit outcome (`seeded` / `skipped` + machine-readable reason / `failed`), and S62 renders every non-`seeded` outcome by name ("Charge codes — not loaded: rating seeding seam not wired"). A run with any skip **does not report success**. The line is **advisory and does not count toward BR-TEN-015 progress**: the operator cannot fix an unwired seam, and BR-TEN-015's completion predicate is "the underlying fields are filled", which no operator action can satisfy here | CONFIRMED (clause 3) — BR-TEN-056 (3). PROPOSED (the non-counting, advisory shape) — derived from BR-TEN-015's completion predicate + A18 empty/partial-state patterns |
| BR-TEN-061 | **Removal is one transaction, `is_sample = true` only, in a fixed reverse-dependency order.** B2 declares **no `ON DELETE CASCADE` on any** premises/units/service_points/assets/accounts FK, so order is not an optimisation, it is the only thing that makes the delete possible: `meter_reads → service_agreements → addresses → contacts → customer_accounts → customers → accounts → asset_assignments → assets (sub-meters before their parents, self-FK) → service_points → units → premises`. It is a **hard** DELETE, not `deleted_at`: a soft-deleted sample row keeps occupying `UNIQUE (tenant_id, premises_id, label)` and `UNIQUE (tenant_id, account_no)`, so the operator could never reuse "Unit A" or their own `A-10001`. Any FK violation rolls the whole transaction back — nothing partial | PROPOSED — derived from B2 §metering/§customers DDL (FKs declared with no ON DELETE clause = NO ACTION) + B2 UNIQUE constraints + BR-TEN-056 (2) "in one transaction" + BR-TEN-034 (hard delete is the sanctioned verb when nothing references the row) |
| BR-TEN-062 | **Sample reads are the one deletion path in metering.** BR-MET-016/017/024 immutability ("posted reads append-only", corrections append a superseding row) governs the **operator's own** reads. A read with `is_sample = true` is removable, which is precisely what BR-TEN-056 (1) presumes when it names reads as *inside* the sample boundary and names invoices/lines/payments/JEs as the append-only exclusion. The metering service exposes exactly one delete entry point and its predicate is `is_sample = true`; there is no other DELETE on `meter_reads` | PROPOSED — derived from BR-TEN-056 (1) (reads are sampled AND the whole set is removable) + B2, whose immutability trigger list names `invoice_lines`, `payments`, `journal_entries`, `journal_lines` and **not** `meter_reads` |
| BR-TEN-063 | **Background, atomic-per-module, idempotent, audited.** The job is enqueued by provisioning and runs after that transaction commits; its failure **never** fails provisioning (BR-TEN-001/010 stay atomic over the tenant itself, which is why the job cannot be inside them). Each module's sample block is its own transaction so one unwired module cannot roll back the rest. It is idempotent per tenant — a replay creates nothing and changes no count — and it writes `audit_log` rows `sample.seeded` and `sample.removed` with counts | PROPOSED — derived from BR-TEN-056 (3) "BACKGROUND, never inline in signup" + BR-TEN-001 + BR-TEN-010 idempotency posture + BR-TEN-016 / CLAUDE.md #7 |
| BR-TEN-064 | **Environment guard, and the trigger (PO ruling 2026-08-10).** The sample-data job **runs under production settings** — BR-TEN-056's beneficiary is a real new operator on the live system, so a production refusal would mean the ruling never executes where it was written for. It is **never triggered automatically**: a human asks for it, either by a checkbox at signup or by a `Fill my tenant with sample data` action in Settings. The job never creates a tenant, user, credential or subscription. `seed_demo` KEEPS its production refusal — it mints a fixture tenant with a published owner password, which this job does not do; two code paths, asserted separately (TC-12). **Amends BR-TEN-056 clause 3**: the job stays background, but its trigger is `on request`, not `at provisioning` | **CONFIRMED** |
| BR-TEN-012 | The sample job **does not seed reference data**; it consumes what BR-TEN-012 seeded. If a catalogue it needs is empty (S111 toggle off — see OQ-082), the affected module is reported per BR-TEN-060, not filled with invented rows | CONFIRMED (existing rule), applied |
| BR-TEN-013 | Every sample write goes through the owning module's service function (premises/units → metering, assets → assets, accounts/customers → customers, reads → metering). Tenancy orchestrates and owns nothing but the run record | CONFIRMED (existing rule) |
| BR-TEN-016 | `sample.seeded` and `sample.removed` audit rows with before/after counts; removal names the row counts per table | CONFIRMED (existing rule) |
| BR-TEN-034 | Removal never becomes a back door around the audit-lock: a sample row that has acquired a real reference is not deletable by this path either — behaviour pending OQ-081 | CONFIRMED (existing rule), boundary OPEN |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | Provision `pecangrove` at S114 | The provisioning response returns without waiting on sample data; at commit time **zero** `is_sample` rows exist; exactly one queued sample-data job for that tenant (BR-TEN-056 (3), BR-TEN-063) |
| TC-2 | Job completes for `pecangrove` | 2 premises · 4 units · 4 service points · 4 assets · 4 accounts · 4 customers · 4 contacts · 4 addresses · 4 service agreements · 8 meter reads, **every one** `is_sample = true`; `sample_data_runs` has one `seeded` row per module |
| TC-3 (neg) | Same tenant, after TC-2, count `invoices` + `invoice_lines` + `payments` + `journal_entries` | **0 rows in all four**, and no code path in the job imports those modules' write services at all (BR-TEN-056 (1)) |
| TC-4 (DEF-017) | Open Settings → Reference data on `pecangrove` | Meter types 5 · Read methods 5 · Asset types 12 · Asset lifecycle stages 5 · Account statuses 5 (each showing its behavior class) · Premises types 5 — alongside UoM 6 · Charge codes 6 · Reason codes 5 · Payment methods 7 · Tax jurisdictions 2. **None** of these rows carries `is_sample` (BR-TEN-058/059) |
| TC-5 (neg, DEF-016) | Run the job with rating's `seed_reference_list` seam deliberately unregistered | `sample_data_runs(module='rating')` = `skipped` with reason `seam_not_wired`; **S62 renders the line by name** ("Charge codes — not loaded: rating seeding seam not wired"); the run's overall outcome is NOT success; the S62 progress counter is unchanged by that line (BR-TEN-060) |
| TC-6 | "Remove sample data" from S8 | All 38 tagged rows deleted in one transaction in the BR-TEN-061 order; reference catalogues untouched (TC-4 counts identical after); `audit_log` `sample.removed` records 38 with the per-table breakdown |
| TC-7 (neg) | Force the removal to run premises-first (fault injection / wrong order) | `ForeignKeyViolation` and the **whole transaction rolls back** — 38 rows still present, none partially deleted. Proves the order is load-bearing and that no FK silently cascades (BR-TEN-061) |
| TC-8 (neg) | Call the removal service against a premises the operator created themselves (`is_sample = false`), by API and by direct service call | Refused; the delete predicate is `is_sample = true` and nothing else; row untouched; no audit `sample.removed` written |
| TC-9 (neg) | Re-run the job for a tenant that already holds its sample set | Creates nothing, changes no count, writes no duplicate `sample_data_runs` row (BR-TEN-063 idempotency, BR-TEN-010 posture) |
| TC-10 (neg) | Kill the job after the assets module and before accounts | Tenant, owner, subscription and reference data unaffected; the partial rows written so far are still tagged, so a re-run completes the set **and** a removal issued in the partial state still takes everything that exists (BR-TEN-063) |
| TC-11 (isolation) | Provision `pecangrove` and `lonestarridge`; run the job for both; remove `pecangrove`'s set | Lone Star Ridge's counts are unchanged to the row; the removal statement executes under `app.tenant_id` = pecangrove with RLS FORCE, so `is_sample = true` can never select another tenant's rows; a probe that sets no `app.tenant_id` and calls removal is refused, not run globally (CLAUDE.md #1, BR-TEN-003) |
| TC-12 (neg) | Boot under `settings.production` and (a) provision a tenant with no one asking for sample data, (b) have an operator invoke the sample action, (c) run `manage.py seed_demo` | (a) **nothing is seeded** — the job is opt-in and provisioning alone does not fire it (BR-TEN-064); (b) **runs** and seeds the tagged set, creating no tenant, user, credential or subscription; (c) **refuses**, as it must. Three assertions, not one — the guard differs per path |
| TC-13 (neg) | Operator opens the bill run (S31) with the four sample accounts present | No sample account is selected. They are seeded **Pending activation**, whose `behavior_class` is `non_billable` (BR-CUS-055), so the EXISTING bill-run selector already skips them — the sample set cannot reach an append-only `invoices` row without the operator first activating an account themselves, which is their own act (BR-TEN-065) |
| TC-14 (blocked — OQ-081) | Operator moves a real account onto the sample premises, then clicks Remove sample data | Pending OQ-081 (refuse-whole / partial-and-report / detach). Implementation raises `NotImplementedError("OQ-081")` at the branch and the UI states the branch is unavailable |
| TC-15 (neg, blocked — OQ-085) | Platform operator targets the job at `brazosbend`, a tenant provisioned before this job existed and already holding real records | Pending OQ-085. Today there is no path at all: `seed_demo` accepts only `--check` and hardcodes the Brazos Bend payload, so a targeting argument does not exist |

**4 · Test Data** — Target tenant **Pecan Grove Water Supply Corp**, subdomain `pecangrove`, state Texas, services Electric + Water, owner Rosa Delgado · `rosa@pecangrovewsc.com`, provisioned 2026-08-10 09:12 CT. Isolation partner: **Lone Star Ridge Water Co-op** (`lonestarridge`), the established second tenant of US-TEN-001/002.

The sample set the job writes (38 rows):

| Table | Rows | Values |
|---|---|---|
| premises | 2 | `104 Cypress Bend Dr, Katy, TX 77494` (single_family, owner "Delgado Family Trust") · `820 Cane Island Pkwy, Katy, TX 77494` (apartment_complex, owner "Cane Island Residential LP") |
| units | 4 | `Unit 1` · `Apt 101` · `Apt 102` · `Apt 103` |
| service_points | 4 | one electric point per unit; `route_id`/`cycle_id` NULL (both nullable in B2 §metering) |
| assets | 4 | `M-9001`…`M-9004`, asset type `meter`, meter type `ami`, read method `ami`, unit `kWh`, multiplier 1, install 2026-01-05 |
| accounts | 4 | `A-1001`…`A-1004` from the tenant's own `account` number series (BR-TEN-035); status **Pending activation** — `behavior_class = non_billable` (BR-TEN-065, PO 2026-08-10) |
| customers + contacts + addresses | 4 + 4 + 4 | Jorge Alvarez · Thi Nguyen · Ada Okonkwo · Ray Boyd, each with a mailing address at their unit |
| service_agreements | 4 | each account ↔ its service point ↔ the tenant's first published electric plan; started 2026-06-01 |
| meter_reads | 8 | two per meter, `2026-06-30` and `2026-07-31`; M-9001 41,208 → 42,146 kWh (938 kWh) · M-9002 12,884 → 13,301 (417) · M-9003 9,455 → 9,846 (391) · M-9004 15,020 → 15,663 (643); `unit = 'kWh'` explicit on every row (CLAUDE.md #3) |

Removal arithmetic (TC-6): 8 reads + 4 agreements + 4 addresses + 4 contacts + 4 customers + 4 accounts + 4 assets + 4 service points + 4 units + 2 premises = **38 rows**, deleted in that order.

Reference catalogue expectations after seeding (TC-4) come from the ratified BRs, not from this story: BR-AST-043 (5 + 5) · BR-AST-004 + BR-AST-042 (10 + 2) · BR-AST-031 (5) · BR-CUS-055 (5) · BR-MET-034 (5) · the existing `lookup_defaults.json` `2026.08` fixture (6 UoM · 6 charge codes · 5 reason codes · 7 payment methods · 2 TX jurisdictions).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Sample tag | — (not a form field) | GAP → BR-TEN-057 (BR-TEN-056 clause 2 names the tag, no doc names the column) | **PROPOSED-SCHEMA:** `is_sample boolean NOT NULL DEFAULT false` on `premises`, `units`, `service_points`, `assets` (B2 r4; `meters` in the base DDL), `asset_assignments`, `accounts`, `customers`, `customer_accounts`, `contacts`, `addresses`, `service_agreements`, `meter_reads` | boolean | system-derived | set only on the sample write path; never user-editable; never settable to `false` (that would strand the row outside removal) |
| Sample tag on plans / rate schedules | — | GAP → **OQ-083** (OQ-079 lists them as sampled; they are also what a real account attaches to) | **BLOCKED** — `rate_plans`, `plan_services`, `tariffs` | boolean | system-derived | blocked pending OQ-083 |
| Sample-run record | S62 | GAP (idempotency + BR-TEN-060 reporting evidence) | **PROPOSED-SCHEMA:** `sample_data_runs(tenant_id, module, outcome, seeded_count, reason_code, started_at, finished_at)`; UNIQUE `(tenant_id, module)` | enum + int + timestamptz | system-derived | `outcome ∈ {seeded, skipped, failed}`; `reason_code` required when not `seeded` |
| Honesty report line | S62 | BR-TEN-056 clause 3 | reads `sample_data_runs` | computed-display | computed-display | advisory; excluded from the BR-TEN-015 progress count (BR-TEN-060) |
| "Remove sample data" action | S8 (tab **GAP → OQ-084**) | BR-TEN-056 clause 2 ("remove the whole set from Settings") | deletes tagged rows; writes `audit_log` `sample.removed` | — | user-input | System Admin only (A4: Settings is System Admin-only); confirm modal per IS-1/BR-TEN-034 pattern |
| Visible "sample" marker on module list screens | S14/S15/S17/S25 (**GAP → OQ-084**) | GAP — no ratified source marks a row as sample on any list screen | — | computed-display | computed-display | blocked |
| Meter types (5) | S8 Reference data | BR-AST-043 | `meter_types(tenant_id, code, name, is_system, active)` — PROPOSED-SCHEMA per BR-TEN-036 | text | reference-data (fixture) | UNIQUE (tenant_id, lower(code)); `is_system` rows deactivatable, never deletable |
| Read methods (5) | S8 Reference data | BR-AST-043 | `read_methods(...)` — PROPOSED-SCHEMA | text | reference-data (fixture) | as above |
| Asset types (12) | S8 Reference data | BR-AST-004 + BR-AST-042 | `asset_types(... , default_test_interval_months)` — PROPOSED-SCHEMA | text + int | reference-data (fixture) | as above |
| Asset lifecycle stages (5) | S8 Reference data | BR-AST-031 | `asset_lifecycle_stages(..., behavior_class)` — PROPOSED-SCHEMA | text + enum | reference-data (fixture) | `behavior_class ∈ {available, in_service, out_of_service, terminal}` |
| Account statuses (5) | S8 Reference data | BR-CUS-055 (+ OQ-064 class seed) | `account_statuses(..., behavior_class)` — PROPOSED-SCHEMA | text + enum | reference-data (fixture) | `behavior_class ∈ {billable, billable_base_only, non_billable, terminal}` |
| Premises types (5) | S8 Reference data | BR-MET-034 | `premises_types(...)` — PROPOSED-SCHEMA | text | reference-data (fixture) | as above |
| Account types (4) | S65 | B2 r5 #12 + D5 | ~~`account_types` — **PLATFORM table, no `tenant_id`, RLS-excluded**; seeded by migration, not by the tenant fixture~~ ⚠ **AMENDED 2026-09-17 — `account_types` IS NO LONGER A PLATFORM TABLE.** PO ruling, verbatim: *"utility can get their own account types"* (`BR-CUS-1079`), superseding `BR-CUS-094`'s platform half and B2 r5 #12 [D5]. It is tenant-scoped with RLS `FORCE` (`customers.0054`/`0055`); the seven are the SEED and a utility adds its own. **The sentence beside this stamp is history.** Eight rows seed PER TENANT from the fixture (`V2.48.0.12`) through `customers.ensure_account_types()`, and the list is STRUCTURAL — `accounts.account_type_id` is NOT NULL. | text | reference-data (platform migration) | closed platform set; tenant extends via `account_subtypes` only |
| Structural-catalogue behaviour when S111 is OFF | S111 | GAP → **OQ-082** | — | — | — | blocked: an account cannot be created without an account status, so "all lists empty" (US-TEN-002 TC-2) may not be a legal state for these six |

**6 · Acceptance** — **Given** a tenant provisioned at S114 with the S111 defaults toggle on, **when** the sample-data job runs after that transaction commits, **then** Settings → Reference data shows every catalogue populated with its ratified values, the operator's premises, units, assets, accounts and reads screens each show realistic records, every one of those records carries `is_sample = true`, and `invoices`/`invoice_lines`/`payments`/`journal_entries` are empty; **and** any module whose seam is not wired is named on S62 by list, with the run not reported as successful; **and when** the operator chooses Remove sample data in Settings, **then** all 38 tagged rows disappear in one transaction in the BR-TEN-061 order, the reference catalogues are untouched, an audit row records the removal with counts, and a second tenant's data is unchanged to the row.

**7 · Finance Calculation** — **N/A**, and the N/A is the point of the story rather than an absence of one. BR-TEN-056 clause 1 places the entire sample set *before* every money table: no sample row exists in `invoices`, `invoice_lines`, `payments` or `journal_entries`, no sample row is priced, and nothing in this job reads a rate, a tier, a tax or a charge amount. The reads it writes carry `prior_value`, `current_value`, `consumption` and an explicit `unit` (CLAUDE.md #3) as **data**, and the consumption values in §4 are subtraction with multiplier 1 (e.g. 42,146 − 41,208 = 938 kWh) — not a B4 formula, not a rating decision, and not a golden test. The first money in this tenant is created by the operator's own bill run, which is exactly what clause 1 preserves. GT ref: none; `finance_calc: none`.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-080 | **Sample accounts and the first bill run.** | — | Product Owner, 2026-08-10 | **CLOSED(→BR-TEN-065)** — sample accounts are seeded non-billable (`Pending activation`). Option (b): it needs no new mechanism, and the accepted cost is that the sample set cannot demonstrate a bill run |
| OQ-081 | **Removal when a sample row has acquired a REAL dependent** — the operator moves their own account onto the sample premises, posts their own read on the sample meter, or attaches a real account to a sample plan. BR-TEN-056 (2) says remove the whole set in one transaction; BR-TEN-034 says a referenced row cannot be hard-deleted. Which wins: (a) refuse the whole removal and list the blocking rows, (b) remove everything unreferenced and report by name what was retained and why, (c) detach the real dependents first? | the removal service's failure semantics + the S8 confirm/result copy | Product Owner (chat session) | OPEN — Eng recommends (b): an operator who cannot remove *anything* because of one row will abandon the feature |
| OQ-082 | **Structural catalogues vs. the S111 toggle.** BR-TEN-012 seeds only when the toggle is on, and US-TEN-002 TC-2 asserts "all reference lists empty" when it is off. Six of BR-TEN-059's lists are not optional vocabulary — an account cannot be created without an account status, an asset without a type and lifecycle stage, a read without a read method. Are these exempt from the toggle (always seeded), leaving the toggle to govern only the discretionary lists (charge codes, reason codes, tax jurisdictions, payment methods)? | the toggle-OFF branch of the extended fixture; US-TEN-002 TC-2's assertion | Product Owner (chat session) | OPEN — Eng recommends exempting the six; a tenant that cannot create an account is not a configuration choice |
| OQ-083 | **Do rate plans and rate schedules carry the sample tag?** OQ-079's enumeration lists "plans, rate schedules" among what is sampled, but a plan is also what a real account attaches to and what the operator edits into their own tariff. If tagged and removed, an operator who attached a real account to the sample plan loses their rating basis; if untagged, "remove the whole set" leaves priced objects behind that were never theirs | which tables get the `is_sample` column (§5 row 2); the removal manifest | Product Owner (chat session) | OPEN — Eng notes this interacts with OQ-081: if plans are tagged, the real-dependent case becomes the *common* case, not the edge |
| OQ-084 | **Where the sample-data controls live, and whether a sample row is visibly marked.** (a) Which S8 tab hosts "Remove sample data" — Company, Reference data, or a new tab — and does it need an A1 screen ID at all (BR-TEN-047 set the precedent that custom fields got none)? (b) Does a sample row carry a visible marker on the module list screens (S14 premises, S15 assets, S17 accounts, S25 reads), or is it indistinguishable from real data until removal? A marker makes the set knowable; no marker makes the tenant "look alive" as the ruling intends. Nothing ratified answers either | the S8 UI ticket; every module list screen's row renderer | Product Owner (chat session) | OPEN |
| OQ-085 | **Targeting a tenant that already exists.** | Product Owner, 2026-08-10 | **CLOSED(→BR-TEN-064)** — the same operator-triggered action serves both cases: a `Fill my tenant with sample data` action in Settings, available to a tenant provisioned before this job existed. Not a platform CLI. It stays idempotent by natural-key lookup (BR-TEN-010 posture), so running it where the operator already has real records adds the sample set without colliding with their data |

> **AMENDMENT 2026-08-15 (build lane) — ONE OF THE FOUR PARTS IS BUILT, AND THE OTHER THREE CANNOT BE BUILT FROM THIS MODULE.** Every OQ above is now CLOSED, including **OQ-084 in full** — the PO ruled the marker on 2026-08-10, **option (a), BADGE THEM**: a sample premise/unit/account/read renders a `Sample` pill on S14/S15/S17/S25, the same treatment `Active`/`Vacant` already get, because BR-TEN-066 removes only the UNATTACHED rows and the operator must see which rows are sample before and after. BR-TEN-069's "the MARKER is NOT ruled" clause is SUPERSEDED and `01-tenancy/02-business-rules.md` is stamped accordingly.
>
> **What was built (part 3, the honest report):** `sample_data_runs` (+ its RLS policy), `06-backend/apps/tenancy/sample_data.py` and `tests/test_us_ten_019_sample_data.py` (16 tests). A run records one row per module with an explicit outcome and a machine-readable `reason_code`; a CHECK constraint refuses a skip that carries no reason; `run_summary()` answers `succeeded = False` whenever any module is non-`seeded` (BR-TEN-056 clause 3, as one boolean); and the S62 line is ADVISORY — `counts_toward_progress` is False, because BR-TEN-015's predicate is "the underlying fields are filled" and no operator can wire a seam.
>
> **What was NOT built, and why it is structural rather than unfinished (parts 1, 2 and 4):** BR-TEN-057 puts `is_sample boolean NOT NULL DEFAULT false` **on the owning row**, and every table it names — `premises`, `units`, `service_points`, `assets`, `asset_assignments`, `meter_reads` — belongs to `apps/metering` or `apps/assets`. B1's boundary rule and BR-TEN-013 forbid tenancy adding a column there, and BR-TEN-057 says the same from the other side: the tag is written *"only by that module's own service function on the sample path, never by tenancy directly"*. **So the job seeds NOTHING today**, every module reports `skipped / seam_not_wired`, and TC-2's 38 rows, TC-6's removal and TC-13's bill-run exclusion cannot yet be exercised. That is reported in the model docstring, the migration docstring, the module docstring and in every run the ledger records — never as a success.
>
> **The five missing seams are PARKED IN A GATE, not merely mentioned**: `10-scripts/gates/seam_known_gaps.txt` carries a row per seam with an `absent=` guard naming the exact column (`absent=metering.Premises.is_sample`, `absent=metering.MeterRead.is_sample`, …), so **G20 goes RED the minute one of those columns arrives** and the park expires. That is BR-TEN-057's arrival signal, mechanised — nothing else was watching for it.

> **Note on the production guard — RESOLVED by the PO on 2026-08-10 (BR-TEN-064).** This story originally recorded a conflict rather than obeying either reading of it: the brief said "same guard as `seed_demo`", but `seed_demo` refuses in production because it mints a fixture tenant with a published owner password, and BR-TEN-056's beneficiary is a real operator on the live system. The PO's ruling: the job runs in production, **opt-in only** — a signup checkbox or a Settings action, never automatic — and `seed_demo` keeps its refusal. That also settles OQ-085: the same action backfills a tenant provisioned before the job existed.

> **Consequence for an existing story, flagged not fixed:** US-TEN-009 TC-1 asserts "Asset types 10", a count taken from BR-AST-004 before BR-AST-042 added Container/Cart and Modem/CPE the same day. BR-TEN-059 seeds 12. EP-TEN-07's TC needs the count updated when this story lands; changing another epic's ratified test data is not this story's to do.

---
```yaml
id: US-TEN-020
epic: EP-TEN-03
module: tenancy
screens: [S8]
wave: 2
status: built            # 2026-08-15 — see the AMENDMENT note under §8
blocked_by: []           # was [OQ-086, OQ-087, OQ-088]; all three CLOSED 2026-08-10
depends_on: [US-TEN-001, US-TEN-002, US-TEN-009, US-TEN-019]
journeys: []
rules: [BR-TEN-001, BR-TEN-003, BR-TEN-010, BR-TEN-012, BR-TEN-013, BR-TEN-016, BR-TEN-034, BR-TEN-036, BR-TEN-043, BR-TEN-059, BR-TEN-064, BR-TEN-067, BR-TEN-070, BR-TEN-071, BR-TEN-072, BR-TEN-073, BR-TEN-074, BR-TEN-075, BR-TEN-076, BR-TEN-077, BR-TEN-078, BR-TEN-079]
golden_tests: []
finance_calc: none
```
### US-TEN-020 — Keeping existing tenants current as seed data evolves

**1 · Details** — As the platform, I need a tenant provisioned in August to receive the reference vocabulary we ship in September, so that a utility that signed up early is not permanently missing the account statuses, asset types and premises types every later tenant gets for free. Entry: a change lands in `apps/tenancy/fixtures/lookup_defaults.json`. Exit: every existing tenant either holds the new rows, or is **named** — with a reason — as still behind. No screen owns this story: A1 declares no cross-tenant surface, A4 §"See other tenants' data" records that no UI exposes cross-tenant data, and the Bynry admin console is **v2** (04-docs/11-roadmap.md "Bynry admin console (all tenants, subscriptions, pricing, invoices) — v2, PO R8"; ADR-003). Its only tenant-visible effect is on **S8 → Reference data** (EP-TEN-07), where the new rows appear in the existing cards.

**Why this story exists.** DEF-017 added six reference lists on 2026-08-10; BR-AST-042 added two asset types on 2026-08-08. **A tenant provisioned before either change never receives it.** Two obvious answers were rejected on analysis before this story was written: a one-time script per change leaves **no record** — six changes later nobody can answer "did `brazosbend` get the 2026.09 lists?"; and a Settings button alone is wrong for structural vocabulary, because **BR-TEN-067** (CONFIRMED) makes those lists schema-required — a tenant cannot create an account without an account status — and a 1–2 staff utility will never notice a button telling them their vocabulary is stale.

**The mechanism already exists — this story finishes it and invents nothing.** `reference_seed_runs` (US-TEN-002 §5, built) carries **UNIQUE (tenant_id, list_code, fixture_version)**; `_seed_reference_data` skips any list that already has a row for the current fixture version; each owning module's seeder looks its entry up by natural key before every create; `seed_reference_data_for_tenant()` backfills ONE tenant; `reference_data_report()` is the per-list seeded/empty/UNEXPLAINED read; `UNSEEDABLE_REFERENCE_LISTS` makes an empty list carry a written reason. That is a **seed-migration ledger in the same shape as Django migrations** (BR-TEN-070). What is missing, and is all this story adds: **nothing walks all tenants**, there is **no policy** on when the version is bumped, there is **no "which tenants are behind" read**, and there is **no dry-run**.

**Three categories, three update paths** (BR-TEN-073):

| Category | Lists | Update path |
|---|---|---|
| Structural vocabulary | meter types · read methods · asset types · asset lifecycle stages · account statuses · premises types | **Automatic sweep**, every tenant, one transaction per tenant, failures isolated and recorded (BR-TEN-067) |
| Tenant-owned reference data | charge codes · tax jurisdictions (+ UoM, reason codes, payment methods) | Same sweep, **additive only — never UPDATE an existing row** (BR-TEN-012/013, BR-RAT-035) |
| Sample records | premises · units · accounts · reads | Stays the **opt-in operator button** on Settings → Company profile (BR-TEN-064/069) — out of scope here |

**The sweep command** — `manage.py sweep_reference_data`, with the posture `seed_demo` already has (Postgres-only, honest reporting, non-zero on an unexplained gap) and one deliberate difference: it **runs under production settings**, because that is where the tenants are, and it mints no tenant, user, credential or subscription. `seed_demo` keeps its blanket production refusal — including on its `--tenant` backfill path, which therefore **cannot run in production at all today** (`seed_demo.handle()` refuses when the settings module ends in `production`, before it looks at `--tenant`). That, not preference, is why this is a new command rather than another flag on `seed_demo`; the split follows the precedent BR-TEN-064 set for the sample job.

* `--dry-run` — compute the plan, print it per tenant per list, **write nothing**: no reference rows, no `reference_seed_runs` rows, no audit rows. Required before the first run of any new fixture version (BR-TEN-076). Always exits 0 — it is a report, exactly like `seed_demo --check`.
* `--report` — the "which tenants are behind" read only (BR-TEN-079); read-only, exits 0.
* `--tenant <subdomain>` (repeatable) — restrict to named tenants. Default: every tenant in `tenants`.
* `--limit N` — stop after N tenants. Blast-radius control for a first live run, same motive as `--dry-run`.
* `--allow-empty-reference-lists` — the named escape hatch, identical in meaning and wording to `seed_demo`'s (DEF-016: the unsafe option is the one you type).

**Exit codes.** `0` every targeted tenant swept (or nothing to do) with no UNEXPLAINED empty list · `1` refused **before any tenant was touched** — non-Postgres vendor, missing/corrupt fixture, no BE-03 audit sink registered, unknown `--tenant` · `2` the sweep ran and ≥1 tenant FAILED (failed subdomains named; the tenants that succeeded keep their writes — BR-TEN-074) · `3` the sweep completed but ≥1 list is EMPTY with no recorded reason, unless `--allow-empty-reference-lists`. Django's `CommandError` exits 1, so 2 and 3 need explicit exits — said out loud because this is exactly the detail that silently degrades to "always 1".

**Output**, per tenant, then the closing report:
```
brazosbend ......... 2026.08 → 2026.09 · seeded {asset_types: 2, premises_types: 5} · skipped {account_statuses: registered reason}
lonestarridge ...... 2026.08 → 2026.09 · seeded {premises_types: 5} · BLOCKED {charge_codes, tax_jurisdictions: OQ-088}
pecangrove ......... already at 2026.09 · seeded {} (idempotent)
```

**The honest wrinkle: `fixture_version` is ONE string for the whole file.** A bump therefore makes **every** list eligible again, not just the changed one. That is harmless — the re-processed lists are insert-if-absent and write zero rows (BR-TEN-071) — and the **per-list ledger row is the thing that carries the fact**: after the sweep `brazosbend` holds a `reference_seed_runs` row per list at `2026.09`, which is precisely the evidence "tenant X was swept at 2026.09" that a one-time script would never have left. The corollary is sharper, and is the actual bump rule: eligibility is keyed *(list, version)*, so a **wholly new list is delivered without a bump** (no row exists for it at any version) while a **new entry inside a list that already shipped needs one** (BR-TEN-077).

**2 · Business Rules**
| BR-ID | Statement | Status |
|---|---|---|
| BR-TEN-070 | **The seed ledger IS the update mechanism; a fixture-version bump is the delivery event.** `reference_seed_runs` UNIQUE (tenant_id, list_code, fixture_version) already makes every tenant eligible again when the version changes, and each owning module's natural-key lookup means only genuinely NEW rows are inserted — a seed-migration ledger in the same shape as Django migrations. **No second mechanism is built**: the sweep walks tenants and calls the existing `seed_reference_data_for_tenant()`; it adds no new seeding path, no new table and no new audit action | PROPOSED — derived from US-TEN-002 §5 (`reference_seed_runs` + its UNIQUE key, built) + BR-TEN-012 CONFIRMED (versioned platform fixtures, per-list idempotent) + BR-TEN-010 idempotency posture |
| BR-TEN-071 | **Insert-if-absent; never UPDATE, never DELETE.** A sweep may ADD a row; it may never change or remove one — the tenant may have renamed it, re-priced it or deactivated it. **Stated consequence, because it is not obvious and it is the reason OQ-086 exists:** shipping a *corrected* value does NOT propagate; a tenant already holding the wrong row keeps it | PROPOSED — derived from BR-TEN-012 CONFIRMED ("tenant-touched rows are never overwritten by later fixture versions") + BR-RAT-035 CONFIRMED ("prototype amounts … are seeds never constants" — the amount is tenant DATA) + BR-TEN-036 (tenant may edit/deactivate seeded rows) |
| BR-TEN-072 | **Renames are forbidden in seed data: add the new code, deactivate the old.** Changing the `code` of a shipped entry makes the natural-key lookup miss and inserts a duplicate alongside the tenant's row; changing only the `name` reaches nobody (BR-TEN-071). A seeded row is `is_system` — deactivatable, never deletable — so a deactivated old code stays visible in history and no later sweep can resurrect it | PROPOSED — derived from BR-AST-031 CONFIRMED ("seeded stages are is_system, deactivatable never deletable") + BR-TEN-036 + BR-TEN-034 (audit-lock) + BR-TEN-071's natural-key lookup |
| BR-TEN-073 | **Three categories, three update paths.** (1) Structural vocabulary — meter types, read methods, asset types, asset lifecycle stages, account statuses, premises types — updates by **automatic sweep**, all tenants, per-tenant transaction. (2) Tenant-owned reference data — charge codes, tax jurisdictions, UoM, reason codes, payment methods — rides the **same sweep, additive only**. (3) Sample records — premises, units, accounts, reads — stay the **opt-in operator action** and are never swept | (1) CONFIRMED — BR-TEN-067 (PO 2026-08-10, OQ-082: schema-required, exempt from the S111 toggle). (3) CONFIRMED — BR-TEN-064 (PO 2026-08-10: never automatic, a human asks). (2) PROPOSED — derived from BR-TEN-012/013 + BR-RAT-035 (amounts are tenant data, not shipped constants) |
| BR-TEN-074 | **Per-tenant context, per-tenant transaction, failures isolated and recorded.** The sweep enumerates the platform table `tenants` (RLS-exempt per B2 §3) and does everything else **inside `tenant_context(tenant.id)`** — it never issues a cross-tenant queryset against a tenant-scoped table, `reference_seed_runs` included, which is RLS FORCE. Each tenant is one transaction: a failure rolls that tenant back whole, is recorded, and the sweep **continues to the next tenant**; the command exits 2 naming every failed subdomain | PROPOSED — derived from CLAUDE.md #1 (RLS FORCE, no cross-tenant queryset) + BR-TEN-003 (tenant_id is server-resolved) + BR-TEN-001 (no half-seeded state) + BR-TEN-063's atomic-per-module posture |
| BR-TEN-075 | **Audited, with no new action name.** Each list a sweep actually seeds writes the EXISTING `reference.seeded` audit row (list + fixture version + count) — charge codes and tax jurisdictions are money config, so this is mandatory, not best-effort (CLAUDE.md #7), and a run that cannot write audit rows is refused up front rather than half-run. A tenant failure writes `reference.sweep_failed` with the tenant, the list and the exception class and **no PII**. The actor is the tenant's own owner resolved through the identity seam, falling back to `actor_user_id = NULL` (a system action) rather than an invented id | PROPOSED — derived from BR-TEN-016 CONFIRMED (per-write audit rows) + CLAUDE.md #7 + the `tenant.provision_failed` trace of US-TEN-004 and the owner-resolution fallback `seed_demo._backfill_actor` already uses |
| BR-TEN-076 | **A dry-run must exist and must write nothing.** `--dry-run` prints the exact per-tenant, per-list plan and performs no INSERT of any kind — no reference rows, no `reference_seed_runs` rows, no audit rows. Without it a single bad fixture edit reaches every tenant at once, and unlike a Django migration there is no `sqlmigrate` to read first | PROPOSED — Eng-Lead; derived from CLAUDE.md hard-won law 3 (defaults fail closed) + law 7 (prove a guard before trusting it) + the `seed_demo --check` precedent (a report: write-free, always exit 0) |
| BR-TEN-077 | **Version-bump policy.** The lane that edits `lookup_defaults.json` bumps `version` **in the same commit** — a fixture change with no bump is an incomplete change, not a small one. A bump is REQUIRED when a list that already ships gains, re-prices or re-labels an entry (BR-AST-042's two asset types are the worked case). A bump is NOT required when a wholly new list joins the file: eligibility is keyed *(list, version)*, so a list with no row at any version is delivered by the next sweep at the current version (DEF-017's six lists are the worked case). Grammar `YYYY.MM` with an optional `.N` serial for the second and later change inside one month — DEF-017 and BR-AST-042 both landed inside `2026.08`, so month granularity has already collided once. A guard test pins the fixture's content to its declared version and must be proved RED on an unbumped edit before it is trusted | PROPOSED — Eng-Lead; derived from the built `_seed_reference_data` skip predicate (per list, per version), the fixture's own `"version": "2026.08"` spanning two content changes, and CLAUDE.md hard-won laws 1 + 7 |
| BR-TEN-078 | **A sweep needs no bill-run interlock.** A newly inserted charge code or tax jurisdiction is **unattached** — it prices nothing until a plan references it through `plan_charge_rules` / `plan_tax_rules` (BR-RAT-036 + the D7/D8 attachment shape) — and config is event-time forward (BR-TEN-043 CONFIRMED, blanket). Combined with BR-TEN-071 (no UPDATE ever), a sweep running while a bill run is in flight cannot change an in-flight total, so the sweep neither blocks on nor is blocked by billing | PROPOSED — derived from BR-TEN-043 CONFIRMED + BR-RAT-036 + BR-TEN-071. Written down explicitly so a reviewer can veto it rather than discover it |
| BR-TEN-079 | **"Which tenants are behind" is a read over `reference_seed_runs`, and it has NO screen.** Per tenant, per list: the highest `fixture_version` present versus the fixture's current version; a list with no row at all is "never seeded" and is reported distinctly from "seeded at an older version". Because the table is RLS FORCE the read is a per-tenant loop under each tenant's own context (BR-TEN-074), never one cross-tenant SELECT. **No A1 screen hosts it** — A4 records that no UI exposes cross-tenant data and the Bynry admin console is v2 — so its surface is the command's own stdout (`--report`). Inventing a screen ID for it is out of scope | PROPOSED — derived from the built `reference_seed_runs` UNIQUE key + `06-backend/db/rls_tenancy_w0.sql` (FORCE + isolation policy on that table) + A4 §"See other tenants' data" + 04-docs/11-roadmap.md (admin console v2) + ADR-003 |

**3 · Test Cases**
| TC-# | Scenario | Expected |
|---|---|---|
| TC-1 | `--dry-run` across all three fixture tenants with `2026.09` staged | The plan prints per tenant per list (`brazosbend: asset_types +2, premises_types +5`); **zero** rows written — reference tables, `reference_seed_runs` and `audit_log` all have identical counts before and after; exit 0 (BR-TEN-076) |
| TC-2 | New list, no bump: add `premises_types` to the fixture and to `LOOKUP_LISTS`/`SEED_LIST_OWNERS`, leave `version` at `2026.08`, sweep | All three tenants gain the 5 BR-MET-034 types; each gets one `reference_seed_runs(list_code='premises_types', fixture_version='2026.08')` row; every other list writes nothing (BR-TEN-077) |
| TC-3 | Existing list, with bump: `asset_types` gains BR-AST-042's Container/Cart + Modem/CPE, `version` → `2026.09`, sweep | `brazosbend` goes 10 → 12 asset types; the 10 it already held are unchanged field-for-field; a `2026.09` row is written for every list, including the unchanged ones, each with `seeded_count = 0` (BR-TEN-070/071) |
| TC-4 | Replay: sweep again immediately | Creates nothing, changes no count, writes no duplicate `reference_seed_runs` row (UNIQUE (tenant, list, version) holds) and no `reference.seeded` audit row; exit 0 |
| TC-5 (neg) | `brazosbend` renamed seeded meter type `ami` "AMI" → "AMI (Itron 100G)" and deactivated `walk_by`; sweep at `2026.09` | Both rows are exactly as the tenant left them — name unchanged, `active = false` unchanged, no duplicate `ami` row created; asserted on the statements actually issued: **no UPDATE and no DELETE reaches `meter_types`** (BR-TEN-071/072) |
| TC-6 (neg, blocked — OQ-086) | Fixture `2026.09` ships a CORRECTED value — TX Local tax 2.00 % → 1.75 % — to a tenant already holding 2.00 % | The held row is NOT changed (BR-TEN-071). The correction branch raises `NotImplementedError("OQ-086")`, and the run reports the divergence by name (`tax_jurisdictions/Local: fixture 1.75 %, tenant holds 2.00 % — not applied, OQ-086`) rather than silently doing nothing (DEF-016 posture) |
| TC-7 (neg) | Fault injection: the rating seam raises mid-sweep on tenant 2 of 3 | Tenant 2 rolls back whole — no partial list, no `reference_seed_runs` row, one `reference.sweep_failed` audit row naming the list and the exception class with no PII; tenants 1 and 3 keep their writes; exit **2** naming `lonestarridge` (BR-TEN-074) |
| TC-8 (isolation) | Sweep all three tenants and probe the context | Every read and write happens under `app.tenant_id` for exactly one tenant; the `--report` read over `reference_seed_runs` is a per-tenant loop, never one cross-tenant SELECT; a probe that calls the sweep step with **no** tenant context is refused (RLS FORCE deny-by-default), not run globally; `brazosbend`'s counts are unchanged by `pecangrove`'s sweep, to the row (CLAUDE.md #1, BR-TEN-003) |
| TC-9 (neg) | No BE-03 audit sink registered | Refused **before any tenant is touched**, exit 1 — a charge-code/tax write that cannot be audited must not happen (CLAUDE.md #7); identical posture to `seed_demo._blockers` |
| TC-10 (neg) | `DATABASE_URL` points at sqlite | Refused up front, exit 1, naming the reason (tenant context is a Postgres GUC); no tenant table read or written |
| TC-11 | `--report` on a mixed estate: `brazosbend` at `2026.08`, `pecangrove` at `2026.09`, `lonestarridge` with no `charge_codes` row at any version | Read-only, exit 0; each tenant lists its per-list current version; `lonestarridge/charge_codes` reads **never seeded**, reported distinctly from `brazosbend/asset_types` = **behind (2026.08 < 2026.09)** (BR-TEN-079) |
| TC-12 (neg) | After a sweep, a declared list is EMPTY with no row in `UNSEEDABLE_REFERENCE_LISTS` | Exit **3** naming the list — unless `--allow-empty-reference-lists` was typed, in which case exit 0 with a WARNING line (DEF-016) |
| TC-13 (neg, blocked — OQ-088) | `lonestarridge` provisioned with the S111 toggle OFF; sweep at `2026.09` | The structural six are delivered regardless (BR-TEN-067). For the discretionary lists (charge codes, tax jurisdictions, reason codes, payment methods, UoM) the implementation raises `NotImplementedError("OQ-088")` and the run prints `BLOCKED {charge_codes, tax_jurisdictions: OQ-088}` — the toggle was never persisted (US-TEN-002 §5: "drives behavior; not stored"), so "no seed-run row" cannot be told apart from "declined at signup" |
| TC-14 | Sweep concurrent with an in-flight bill run on the same tenant | The bill run completes; its invoice totals are identical to a control run without the sweep; the newly inserted charge code appears on no invoice line because no plan references it (BR-TEN-078) |
| TC-15 (neg) | Boot under `settings.production` and run (a) `manage.py sweep_reference_data`, (b) `manage.py seed_demo --tenant lonestarridge` | (a) **runs** — it mints no tenant, user, credential or subscription; (b) **refuses**, because `seed_demo` guards on the settings module before it parses `--tenant`. Two code paths, asserted separately (the BR-TEN-064 split applied to reference data) |

**4 · Test Data** — Three tenants, all from the signed corpus: **Brazos Bend Utilities** (`brazosbend`, TX, provisioned 2026-08-08, seeded at fixture `2026.08` **before** DEF-017 — holds UoM 6 · charge codes 6 · reason codes 5 · payment methods 7 · TX jurisdictions 2 · asset types 10, and no meter types, read methods, asset statuses or premises types); **Lone Star Ridge Water Co-op** (`lonestarridge`, provisioned with the S111 toggle **OFF** — every discretionary list empty); **Pecan Grove Water Supply Corp** (`pecangrove`, provisioned 2026-08-10 after DEF-017, at `2026.08`).

The staged fixture change, both halves taken from ratified values — nothing invented:

| Change | List | Rows | Needs a bump? |
|---|---|---|---|
| A | `premises_types` — **a wholly new list** | 5: apartment_complex · commercial_building · single_family · mixed_use · mobile_home_park (BR-MET-034, BR-TEN-059) | **No** — no tenant has a row for it at any version |
| B | `asset_types` — an existing list gains entries | +2: Container/Cart · Modem/CPE (BR-AST-042), taking 10 → 12 (BR-TEN-059) | **Yes** — `2026.08` → `2026.09` |
| C (negative only) | `tax_jurisdictions.TX` — a corrected value | TX Local 2.00 % → 1.75 % | Bump irrelevant: it never applies — OQ-086 (TC-6) |

Expected `reference_seed_runs` for `brazosbend` after the sweep: one row per declared list at `2026.09`, with `seeded_count` = 2 for `asset_types`, 5 for `premises_types`, 0 for the rest. Audit: two `reference.seeded` rows — the two lists that actually inserted.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Fixture version | — (no screen) | `apps/tenancy/fixtures/lookup_defaults.json` `version` (built) | copied into `reference_seed_runs.fixture_version` | text | reference-data (platform fixture) | BR-TEN-077 grammar `YYYY.MM[.N]`; required — a fixture without it is already refused (`_load_seed_fixture`) |
| Seed-run ledger row | — | US-TEN-002 §5 (**built**, not proposed) | `reference_seed_runs(tenant_id, list_code, fixture_version, seeded_count, seeded_at)`; UNIQUE (tenant_id, list_code, fixture_version); RLS FORCE | text + int + timestamptz | system-derived | one row per list per version; inserted, never updated |
| "Behind" report row | — **GAP: no A1 screen** (A4: no cross-tenant UI; admin console v2 per 11-roadmap + ADR-003) | BR-TEN-079 | reads `reference_seed_runs` per tenant, under that tenant's context | computed-display | computed-display | states `current` / `behind (X < Y)` / `never seeded` distinctly |
| Sweep failure trace | — | BR-TEN-075 (US-TEN-004 `tenant.provision_failed` precedent) | `audit_log` (action = `reference.sweep_failed`) | jsonb | system-derived | tenant + list + exception class only; **no PII**, no fixture payload |
| Seeded-list audit row | — | BR-TEN-016 (existing action `reference.seeded`) | `audit_log` | jsonb | system-derived | list + fixture_version + count; written only when the count is > 0 |
| `--dry-run` | — | BR-TEN-076 | none — writes nothing | flag | user-input (operator CLI) | mutually exclusive with `--report`; never combined with a write path |
| `--tenant <subdomain>` / `--limit N` / `--allow-empty-reference-lists` | — | BR-TEN-074/076 + `seed_demo` precedent | reads `tenants.subdomain` (platform table, RLS-exempt) | text / int / flag | user-input (operator CLI) | unknown subdomain ⇒ exit 1 naming the known set, as `seed_demo --tenant` already does |
| `premises_types` registry entry | S8 Reference data | BR-MET-034 + BR-TEN-059 | **GAP — named by BR-TEN-059, present in NEITHER `LOOKUP_LISTS` NOR `SEED_LIST_OWNERS`.** The metering seam already handles the list code and the table exists, so today it is seeded only as a side effect of `ensure_reference_catalogs()` on a premises write — no ledger row, no S8 card | text | reference-data (fixture) | adding the two registry entries is Change A of §4; until then the sweep cannot report on this list |
| Persisted "load defaults" choice | S111 | **GAP → OQ-088** — US-TEN-002 §5 records the toggle as "drives behavior; not stored" | **PROPOSED-SCHEMA (blocked):** `tenants.reference_defaults_opted_in boolean NOT NULL DEFAULT true` | boolean | system-derived | blocked pending OQ-088 — and it cannot answer for tenants provisioned before the column exists, which is the half the PO must rule |
| Correction set | — | **GAP → OQ-086** | **BLOCKED** — it would be the only thing in this story that UPDATEs a tenant row | — | — | blocked; `NotImplementedError("OQ-086")` at the branch |
| Sweep trigger / schedule | — | **GAP → OQ-087** | — | — | — | blocked: nothing in 09-infra names a production post-migrate seed step (§5 step 4 is demo/staging and NEVER prod) |

**6 · Acceptance** — **Given** a tenant provisioned at fixture version `2026.08` and a fixture change that adds a new list and extends an existing one at `2026.09`, **when** an operator runs `manage.py sweep_reference_data --dry-run`, **then** the exact per-tenant, per-list plan prints and not one row is written; **and when** the sweep runs for real, **then** every tenant gains only the genuinely new rows, every row the tenant had renamed, re-priced or deactivated is untouched, each tenant is swept in its own transaction under its own `app.tenant_id` with one `reference_seed_runs` row per list at `2026.09`, a failing tenant is rolled back whole and named while the others keep their writes, and `--report` afterwards shows every tenant current; **and** a corrected value in the fixture reaches nobody and is reported as such, pending OQ-086.

**7 · Finance Calculation** — **N/A**, with the boundary stated rather than assumed. The sweep writes money **configuration** (charge-code amounts, tax rates) but computes nothing: it evaluates no formula, applies no rounding, reads no meter and touches no `invoices`, `invoice_lines`, `payments` or `journal_entries`. Its only arithmetic is a row count — for `brazosbend` at Change B, `asset_types` = 12 in the fixture − 10 already held = **2 inserted, 10 skipped**; at Change A, 5 in the fixture − 0 held = **5 inserted** — which is set difference by natural key, not a B4 formula. The one place money math could have entered is a corrected rate, and BR-TEN-071 forbids it from landing at all (OQ-086). GT ref: none; `finance_calc: none`.

**8 · Open Questions**
| OQ-ID | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-086 | **How does a CORRECTED value reach a tenant that already holds the wrong row?** BR-TEN-071 makes seeding insert-if-absent, so if we ship a bad tax rate or a mistyped fee (say TX Local at 2.00 % where it should be 1.75 %), every tenant seeded before the fix keeps the wrong number forever and no sweep will ever touch it. Roughly: (a) **never** — a correction is the tenant's own edit and we notify them, naming the rows; (b) an explicit, **audited, opt-in "apply correction"** action that names each affected row with its before/after value and is accepted per row; (c) a **forced UPDATE** for a declared correction set, which risks clobbering a deliberate tenant edit. This is money configuration, so it is not Eng's to choose | the correction branch of the sweep; any future fixture fix to an amount or a rate; whether a per-row "has the tenant touched this?" signal must be added to tell a pristine seeded row from an edited one | Product Owner (chat session) | **OPEN** — Eng notes (c) is unbuildable as stated without amending BR-TEN-012 CONFIRMED ("tenant-touched rows are never overwritten"), and that (a) and (b) both need a per-row provenance signal the schema does not carry today |
| OQ-087 | **Who runs the sweep, and when?** Options: (a) **automatic on deploy** — a post-migrate step, so a fixture change reaches every tenant the moment it ships and no tenant is ever behind; (b) a **released command an operator schedules**, run deliberately after reading a `--dry-run`; (c) **on demand only**, per tenant, from support. 09-infra §5 step 4's post-migrate seed step is explicitly demo/staging and NEVER prod, so nothing today authorises (a) in production — and nothing authorises anything else either. The choice also decides **who is accountable** when a tenant is left behind, which is the failure this story exists to end | the command's release wiring (deploy hook vs. runbook entry); the SLA implied by "tenant X is behind"; whether `--limit`/staged rollout is the norm or the exception | Product Owner (chat session) | **OPEN** — Eng recommends (b) for the first two releases with `--dry-run` mandatory, moving to (a) once a version bump has been proved harmless twice; CLAUDE.md hard-won law 4 ("a template change never reaches a host that already has a `.env`") is the same failure in a different file |
| OQ-088 | **Does a version bump deliver the DISCRETIONARY lists to a tenant that turned the S111 toggle OFF?** BR-TEN-012 (CONFIRMED) says seeding runs only when the toggle is on; BR-TEN-067 (CONFIRMED) exempts the structural six, so those always sweep. But the toggle is **never persisted** — US-TEN-002 §5 records it as "drives behavior; not stored" — and the absence of a `reference_seed_runs` row is ambiguous between "the tenant declined" and "this list did not exist yet", which is the very case this story exists to fix. So: (a) sweep discretionary lists only where the tenant already has a seed-run row for that list (declined stays declined — but a NEW discretionary list then reaches nobody who declined, ever); (b) add a persisted per-tenant opt-in flag and sweep by it — which still leaves every already-provisioned tenant needing a backfilled value the PO must choose; (c) sweep everything and treat charge codes and tax jurisdictions as vocabulary like the structural six. Charge codes and tax rates arriving in a tenant that asked for none is money configuration, so this is routed, not decided | the discretionary half of the sweep for any toggle-OFF tenant; the default for the PROPOSED `tenants.reference_defaults_opted_in` column; US-TEN-002 TC-2's assertion, already narrowed once by BR-TEN-067 | Product Owner (chat session) | **OPEN** — Eng recommends (b) with the backfill value ruled explicitly rather than inferred, because inferring it from an empty list is the ambiguity itself |

> **AMENDMENT 2026-08-15 (build lane) — THE THREE OQs ABOVE ARE CLOSED AND THE ROWS ABOVE ARE THE STALE VERSION.** All three were answered by the PO on **2026-08-10** (`12-governance/01-open-questions.md` is the live registry; these rows were never updated). The story was built to the CLOSURES, and two of its test cases were amended because they instructed a stub that would now fail G8 — *a `NotImplementedError` citing a CLOSED question is a stale stub by definition*, which is the same trap US-TEN-017 still carries.
>
> * **OQ-086 → CLOSED, option (b):** an **audited, opt-in "apply correction" that NAMES each affected row**; never a silent forced UPDATE. **TC-6 is amended**: the sweep must NOT raise `NotImplementedError("OQ-086")`. It reports every divergence by name (`meter_types/ami.name: fixture 'AMI (corrected)', tenant holds 'AMI' — NOT applied`) and applies none (BR-TEN-071). **Built and asserted.** ⚠ The APPLY half is NOT built and is owed: it needs a per-row "has the tenant touched this?" signal no table carries, plus an UPDATE path through each owning module. ⚠ Further, the story's own worked case — a corrected TX Local rate **2.00 % → 1.75 %** — is **invisible to the detector**: the only sanctioned cross-module read is the registered lookup handler's `serialize()`, and rating's charge-code handler deliberately omits `amount`/`percent`/`min_amount` ("a fee's MONEY is rating law, not reference-data plumbing" — its own docstring) while no handler exposes a tax rate. So a corrected NAME is caught and a corrected RATE is not; the run names every such list under `not checkable at all` on every run rather than reporting them clean. Closing that needs a `reference_seed_divergences` read seam published by each owning module.
> * **OQ-087 → CLOSED, option (b):** **automatic post-migrate, across all tenants.** Wired in `06-backend/docker-entrypoint.sh` immediately after `migrate`, and it may not stop the boot (BR-TEN-074 isolates per-tenant failures). `09-infra/01 §5` gained **step 4b** saying so — the ruling's own closure note required that amendment, and step 4's "NEVER prod" is now explicitly scoped to the demo fixture.
> * **OQ-088 → CLOSED, option (a):** **persist the S111 toggle first, then honour it** — *"until that column exists the sweep delivers STRUCTURAL lists only, never discretionary ones."* `tenants.reference_defaults_opted_in` does NOT exist, so **the sweep passes `structural_only=True` unconditionally** and names every discretionary list DEFERRED. **TC-13 is amended** the same way as TC-6: no stub, the ruled behaviour, asserted. **The column is NOT added here**, because the ruling did not settle what value it carries for the tenants that already exist — that residue is **OQ-216**, minted 2026-08-15 and cited in the code at `reference_sweep.DISCRETIONARY_DEFERRAL_OQ`.
>
> **TC-3 is narrowed by the same ruling**: it expects "a `2026.09` row for EVERY list including the unchanged ones". Discretionary lists now get no row at all, because they are not delivered at all. Structural lists behave exactly as TC-3 describes.
>
> **REPORTED, NOT CHANGED — one §5 row already diverges from shipped behaviour.** §5 says the `reference.seeded` audit row is *"written only when the count is > 0"*. The built `_seed_reference_data` writes one for **every** list it processes, count or no count, and has since US-TEN-002 — so the live sweep of `brazosbend` at `2026.09` wrote **6 audit rows for 6 lists that inserted 0 rows**. BR-TEN-070 forbids this lane inventing a second seeding path or a new audit action, and narrowing an existing write that provisioning also uses is not a sweep decision, so it was left alone and written down instead. Arguably the shipped behaviour is the better one — the row is the evidence that the sweep REACHED that list — but that is a call for whoever owns US-TEN-002, not this lane.
>
> **Built:** `06-backend/apps/tenancy/reference_sweep.py` · `apps/tenancy/management/commands/sweep_reference_data.py` · `tests/test_us_ten_020_sweep.py` (26 tests) · the `seed_reference_data_for_tenant(..., structural_only=)` narrowing · BR-TEN-070..079 landed in `01-tenancy/02-business-rules.md`, where they had never been copied from this epic. **BR-TEN-077's guard is a REFUSAL, not a warning**: `RATIFIED_FIXTURE_DIGESTS` pins the fixture's content to its declared version and the command exits 1 naming both digests — proved RED by adding one asset type to `lookup_defaults.json` without a bump.

> **Reported, not fixed — `premises_types` is DEF-017's seventh list and it is still missing.** BR-TEN-059 names seven catalogues; the fixture and `SEED_LIST_OWNERS` carry six. `apps/metering/services.py` already handles the `premises_types` list code in its `seed_reference_list` seam and says so in its own module docstring ("tenancy's `LOOKUP_LISTS` registry has no 'premises_types' key … Reported"), so the list is seeded today only as a side effect of `ensure_reference_catalogs()` firing on a premises write. Consequence for this story: a tenant that has never created a premises has no premises types, no `reference_seed_runs` row for them, and no S8 card — so the sweep cannot report on the one list whose absence is invisible. Change A of §4 is the two-entry registry fix; making it is EP-TEN-07's call, not this story's.

---

## Story added 2026-08-16 — S113 had no owner (DEF-137)

`04-docs/02-decisions/13a-screen-component-map.md` has carried S113 as *"unclaimed — flag (W8)"* since 2026-08-09 and nothing acted on it. It is **hard-won law 8 for the third time**, after DEF-006 (the S1 landing page, half-missing for a week) and DEF-129 (the tenant dashboard, rendering a developer string on the first screen after every sign-in). The story below is authored from the spec — A1's own S113 row, `01-tenancy/04-flows.md`, 13a's component row and `05-prototype/UtilityBilling.html` lines 441–479 — and from nothing else. It is written BEFORE the screen is built, which is the whole point of the law.

---
id: US-TEN-021
epic: EP-TEN-03
module: tenancy
screens: [S113]
wave: 8
status: ready
blocked_by: []
depends_on: [US-TEN-001, US-TEN-002, US-SHL-010, US-SHL-009]
journeys: [J1]
rules: [BR-TEN-014, BR-TEN-010, BR-TEN-045, BR-SHL-010, BR-SHL-023, BR-SHL-044]
golden_tests: []
finance_calc: none
---
### US-TEN-021 — S113 signup step 4: review what you are about to create, and change any of it before it exists

**1 · Details** — As a **prospect on step 4 of 5 of the signup wizard**, I want a read-only summary of everything I have chosen so far with an **Edit link on each block**, so that I can check and correct my utility before it is created — because after step 5 the tenant EXISTS and several of these choices become expensive to change (BR-TEN-042 locks the currency the moment a financial record appears). A1's own row: *"4 · Review — Read-only summary of steps 1–3 with per-block Edit links, and a due-today / then-monthly panel."*

**Three blocks, mirroring the three steps** (prototype lines 446–474): **Your utility** (name · web address · location · services billed → Edit returns to S110) · **How you bill** (rate style · cycle · tax region · currency, each defaulted value marked as a default so the prospect can see what they did not choose → Edit returns to S111) · **Plan & setup** (subscription · implementation package · trial · go-live → Edit returns to S112). An Edit link returns to that STEP with every entered value preserved and returns forward to this one; it is a wizard step, not a new screen, so it reuses the US-SHL-010 wizard frame and its step rail (BR-SHL-010).

**The money panel** (prototype line 476) reads **Due today** and the recurring amount. Both come from the plan catalogue, which is real published data (`GET /public/pricing-plans`, the three ratified SKUs seeded by tenancy migration 0005 and priced by the A13 addendum of 2026-08-07) — **nothing on this screen computes a price**. Due today is **$0.00** because BR-TEN-014 creates the subscription as `trial`, `trial_ends_at = provisioned_at + 14 days`, with no payment method required. **The date the recurring amount first falls due is NOT drawn: OQ-224.** BR-TEN-014 fixes the trial's end and OQ-015's closure introduced Net-7/15 payment terms, so trial-end and first-charge are two different days and no signed document says which one the panel names. The screen states the trial end AS a trial end and says plainly that no charge date is set yet.

**Nothing on this screen writes anything.** The tenant does not exist until step 5 commits (`POST /api/tenants`, US-TEN-001), so every value here is wizard state and every Edit is a navigation. Entry: step 3 → *Looks right →*. Exit: → S114, or back into any step.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-TEN-014 | Provisioning creates the subscription as `trial`, `trial_ends_at = provisioned_at + 14 days`, no payment method required — which is why *Due today* is 0.00. | CONFIRMED — A1 addendum 2026-08-08 + B2 |
| BR-SHL-010 *(consumed)* | The wizard frame: step rail, Back/Continue, confirm. This screen is a STEP and mints no frame of its own. | CONFIRMED |
| BR-SHL-023 *(consumed)* | One money formatting path; every amount renders with its currency. | CONFIRMED |
| BR-SHL-044 *(consumed)* | One page header. | CONFIRMED |
| BR-TEN-010 *(consumed)* | The commit that follows is idempotent — a prospect who edits, returns and submits twice creates one tenant. | CONFIRMED |
| BR-TEN-042 *(consumed)* | The currency this screen shows becomes LOCKED once a financial record exists — the reason a review step is worth a screen at all. | CONFIRMED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Silver Creek Water completes steps 1–3 and lands on step 4 | All three blocks render the values entered, and the defaulted ones are marked as defaults (prototype: *"Flat rate `default`"*, *"Monthly, 1st `default`"*) |
| TC-2 | Click Edit on **How you bill** | Returns to S111 with every entered value preserved; Continue returns to step 4 with the edit applied — no value is lost in either direction |
| TC-3 | Growth plan selected, self-serve implementation | *Due today* renders **$0.00 USD** and the recurring amount renders the catalogue's own figure with its currency; neither is computed on this screen |
| TC-4 *(negative — OQ-224)* | The panel's second line | States the **trial end** (provisioning day + 14) and states that no first-charge date is set. **No date is drawn as a first-charge date**, and the screen does not imply one |
| TC-5 *(negative)* | A prospect who has skipped step 2 entirely (S111 offers *Skip — use defaults*) | Every "How you bill" row still renders, each marked as a default — an empty block would let a prospect create a utility whose billing settings they never saw |
| TC-6 *(negative)* | Nothing on the screen writes | No request is made on render or on any Edit; the tenant does not exist until S114 commits (US-TEN-001) |
| TC-7 | Back from step 5 | Returns here with everything intact, including choices made after the first visit |

**4 · Test Data** — Prototype's own: **Silver Creek Water**, `silvercreek.smartbillhub.app`, Texas · United States, Electric + Water; Flat rate (default), Monthly 1st (default), Texas 8.25%, USD; **Growth** subscription, Self-serve implementation, 14-day trial, go live today. Actor: the signup prospect (no session yet — this screen is public).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Utility name · web address · location · services | S113 | A1 §S113 · prototype 448–454 | wizard state → `tenants.*` / `tenant_services` at S114 commit | text | user-input (echoed) | read-only here; Edit → S110 |
| Rate style · cycle · tax region · currency | S113 | A1 §S113 · prototype 456–463 | wizard state → tenant settings at commit | text | user-input or DEFAULT (marked) | read-only here; Edit → S111 |
| Subscription · implementation · trial · go-live | S113 | A1 §S113 · prototype 465–472 | wizard state → `subscriptions` at commit | text | user-input (pre-selected) | read-only here; Edit → S112 |
| Due today | S113 | prototype 476 + BR-TEN-014 | plan catalogue (`GET /public/pricing-plans`) | numeric(18,6) + CHAR(3) | reference-data | 0.00 while the trial takes no card; rendered with its currency |
| Recurring amount | S113 | prototype 477 + A13 addendum | plan catalogue | numeric(18,6) + CHAR(3) | reference-data | catalogue figure, never computed here |
| First-charge date | S113 | prototype 477 | — | date | **UNAVAILABLE — OQ-224** | not drawn; the trial end is stated as a trial end |

**6 · Acceptance**
- Given steps 1–3 are complete, Then step 4 shows every choice, marks the defaults, and each block's Edit returns to its step with values preserved.
- Given the plan catalogue, Then Due today and the recurring amount render with their currency and neither is computed on this screen.
- Given OQ-224, Then no first-charge date is drawn and the screen says a charge date is not set yet.
- Given any interaction here, Then nothing is written — the tenant exists only after S114.

**7 · Finance Calculation** — **N/A.** Every figure is the plan catalogue's own; this screen performs no arithmetic. *Due today* is 0.00 by BR-TEN-014's rule, not by a subtraction.

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-224 | Which day does the recurring amount first fall due — trial end, or trial end plus the OQ-015 Net-7/15 term? | The first-charge DATE only; Due today, the amount and the trial end all ship | Product Owner | OPEN — non-blocking |
