# integrations — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (candidate OQ in the pack report — routed to the Product Owner by the orchestrator).
Consolidated from US-INT-001..012 §5 (2026-08-09); verified against B2 (grep: NO integration-connections table itemized in the DDL/addenda — see discrepancy **I-2**; exact DDL/keys = Eng-Lead 🔒). Governing ruling: CL-1(a) connector matrix (PO 2026-08-08).

## 1. Connections core (EP-INT-01)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Card catalog (category · name · description · A11 key) | S8 | US-INT-001 §5 · prototype grid + A1/A11 addenda | platform reference catalog (keys quickbooks…email + esp/bank additions) | enum/text | reference-data | see I-3 for the two added keys | mapped |
| Per-card v1 disposition (real / coming-soon + wave label) | S8 | US-INT-001 §5 · CL-1 (BR-INT-001) | catalog disposition flags (platform-level) | enum | reference-data | v1_real \| coming_soon(W7\|v1.1\|v2) | mapped |
| Connection row (per tenant × key) | S8 | US-INT-002 §5 · A11 addendum | `integration_connections` — **DDL 🔒, see I-2** | row | system-derived | one active per key per tenant | mapped 🔒 |
| Method | S8 modal | US-INT-002 §5 · A1/A11 addenda | `.method` | enum | user-input | oauth \| apikey \| sftp per card | mapped |
| API key / token / OAuth grant / SMTP password | S8 modal | US-INT-002 §5 · A1 addendum + B7 addendum | **encrypted secret store; `secret_ref` pointer only** on the row | secret | user-input / integration | write-only; never echoed/logged/audited (BR-INT-003) | mapped 🔒 |
| Environment | S8 modal | US-INT-002 §5 · A1 addendum + B7 (sandbox creds) | `.environment` | enum | user-input | production \| sandbox; per-env credentials | mapped |
| Sync cadence | S8 modal | US-INT-002 §5 · A1 addendum + prototype (Nightly/Hourly/Manual) | `.sync_cadence` | enum | user-input | nightly \| hourly \| manual | mapped |
| Connection status | S8 cards | US-INT-002 §5 · A11 (connect returns status) + B7 (Failed · Retry) | `.status` | enum | system-derived | not_connected → connected \| failed | mapped |
| Test-connection result | S8 modal/card | US-INT-002 §5 · A1 addendum toggle + A11 `/test` | `.last_test_at` + `.last_test_result` | ts/enum | integration | pass \| fail + provider error | mapped |
| Connected-by/at | S8 Manage | US-INT-002 §5 · BR-TEN-016 family | `.connected_by`, `.connected_at` | uuid/ts | system-derived | stamped on save | mapped |
| Disconnect + consequence copy | S8 modal | US-INT-003 §5 · prototype (Disconnect + toast) + IS-6 + BR-NOT-005/B7 addendum | `.status` → not_connected; secret destroyed; history untouched | enum | user-input | IS-6 confirm; per-card-class consequences | mapped |
| Lifecycle audit events | — (S61 viewer) | US-INT-004 §5 · BR-TEN-016 + CLAUDE.md #7 | `audit_log` `integration.connected\|test_run\|updated\|disconnected` | jsonb | system-derived | append-only; masked payloads | mapped |
| Connection read-model (states per key) | S8 + consumer panels (S8 Notifications, S42, S38, S35) | US-INT-004 §5 · A11 `GET /integrations` + US-NOT-004 §5 + ledger D-7 | service-function view (B1 reads-only seam) | status set | computed-display | consumers never write | mapped |
| Subprocessor-register feed | — (platform ops) | US-INT-004 §5 · soc2-nist-mapping §5 | platform-side feed → register in audit-and-controls.md | rows | system-derived | §5 classes only (ESP/Twilio/print/e-sign); BYO mailbox excluded; DPAs = ops | mapped |

## 2. Comms connections (EP-INT-02)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Mailbox method (Google/Microsoft/SMTP) | S8 email modal | US-INT-005 §5 · A15 addendum + prototype 3-segment | `.method` (keys email_google\|email_microsoft\|email_smtp) | enum | user-input | one mailbox class surfaced on the band | mapped |
| Send-from address | S8 email modal | US-INT-005 §5 · A15 addendum + prototype field | non-secret config column | text | user-input / integration (OAuth-authorized) | required; shown on card | mapped |
| SMTP host / port | S8 email modal | US-INT-005 §5 · prototype (custom only) | non-secret config columns | text/int | user-input | smtp method only | mapped |
| Test email on connect | S8 email modal | US-INT-005 §5 · A15 addendum ("test email offered on connect") + prototype checkbox | verification send through the connected mailbox → last_test | flag/enum | user-input / integration | connection verification only — customer sending stays W6 (BR-INT-007); recipient = I-6 | mapped (see I-6) |
| ESP connection (key + domain + send-from) | S8 ESP card | US-INT-006 §5 · OQ-074 closure + CL-1 (card added, I-3) | connection row + non-secret domain/send-from config | row/text | user-input | v1-REAL; key = secret | mapped |
| Domain verification status | S8 checklist | US-INT-006 §5 · provider-reported (B7 seam contract) | config column | enum | integration | verified \| pending \| failed — provider's verdict, never computed locally | mapped |
| Active email-provider binding | S8 Manage | US-INT-007 §5 · US-NOT-003 §5 ("integrations-owned per-tenant provider config") + B7 per-tenant config | binding config (🔒 I-2) | ref | user-input / system-derived | sole connection = default; two connected = explicit audited choice | mapped |
| Provider health (status · last test · last send error) | S8 Notifications + delivery dashboard | US-INT-007 §5 · BR-TEN-041 #8 + B7 (Failed · Retry) | read-model columns (`last_provider_error` family) | enum/text/ts | integration / system-derived | dispatcher reports in; consumers read-only | mapped |
| Email channel gate (connection ≠ activation) | S8 badges | US-INT-005/007 §5 · OQ-073 closure | channel-config flags (US-NOT-003) | flag | reference-data | sending W6 | mapped |

## 3. File channels (EP-INT-03)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Bank/lockbox profile (label · bank/source) | S8 list / S38 select | US-INT-008 §5 · prototype S38 "Chase Operating ••4021" (payments P-10) | bank profile row (r12 #10 family — anchoring I-2/P-10) | text | user-input | unique per tenant; masked ••last4 display | mapped 🔒 |
| File format | S8 list | US-INT-008 §5 · B7 (BAI2/CSV/OFX/QBO/QFX) + prototype S35/S38 | `.format` | enum | user-input | one per profile | mapped |
| CSV mapping choice | S8 modal | US-INT-008 §5 · OQ-040 closure pattern | mapping config jsonb | jsonb | user-input | CSV-format profiles only | mapped |
| Source (upload / SFTP) | S8 modal | US-INT-008 §5 · A1 addendum (SFTP-file method) + prototype upload zones | `.source` + SFTP host/path (creds → secret store) | enum/text | user-input | upload = v1 live; SFTP pull execution = provision (I-8) | mapped |
| Batch ↔ profile consumption ref | S35/S38 | US-INT-008 §5 · US-PAY-003/021 §5 | `payment_import_batches` profile ref (r12 #3/#10) | uuid | system-derived | batch records its producing profile | mapped |
| Export target profile (type · label) | S8 list / S43 | US-INT-009 §5 · BR-LED-004 four targets + prototype S43 | target profile row (anchoring I-2) | enum/text | user-input | QBO-file \| Xero-file \| CSV \| IIF | mapped |
| Export-code readiness readout | S8 | US-INT-009 §5 · BR-LED-014 + r13 #5 | computed over `ledger_accounts.qbo_ref/.xero_ref` | count | computed-display | pointer to Finance mapping page — codes NEVER edited here (ledger D-2) | mapped |
| S42 Connections-panel state | S42 | US-INT-009 §5 · ledger D-7 | US-INT-004 read-model | status | computed-display | file-target truth; no live sync v1 | mapped |
| Profile status + used-by lock | S8 lists | US-INT-010 §5 · IS-1 + A1 Settings item 4 | `.status` + computed used-by | enum/int | user-input / computed-display | deactivate-first; delete only used-by = 0 | mapped |
| Producing-profile ref on history | S35/S42 histories | US-INT-010 §5 · NFR-15 | batch rows keep profile ref/version | uuid | system-derived | edits never restate history | mapped |
| Idempotency survival | — | US-INT-010 §5 · NFR-16 (BR-PAY-028, BR-LED-004, OQ-044) | flows' unique keys — untouched by this module | — | system-derived | survive all profile lifecycle | mapped |

## 4. Deferred cards (EP-INT-04)
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Coming-soon states + wave labels (Stripe/Plaid W7 · Twilio v1.1 · live-sync/MDM/SSO v2) | S8 cards | US-INT-011/012 §5 · CL-1 (BR-INT-001) | catalog disposition flags | enum | reference-data | platform-level gate; no tenant unlock flag | mapped |
| Gate enforcement (UI + API) | — | US-INT-011/012 §5 · IS-6 server-side principle + OQ-015/TD-9 | connect/test endpoints refuse gated keys; zero secret persistence | — | system-derived | secret-handling TCs | mapped |
| Webhook idempotency provision | — | US-INT-011 §5 · B2 `payments.webhook_key` (human-owned 🔒) | already in schema; consumed at W7 | text | integration | NOT touched by this pack | mapped 🔒 |
| AMI-gate artifacts (v2 precondition) | — | US-INT-012 §5 · NFR-27 | capacity re-run + Eng-Lead sign-off records (v2 design) | refs | system-derived | required per tenant enablement | mapped (v2) |
| `sso_links` provision | — | US-INT-012 §5 · B2 identity (platform, no RLS) | exists; unused v1 (BR-IDN-029) | rows | system-derived | no UI v1 | mapped |

## Discrepancies & seams (verified vs B2 + prototype, 2026-08-09)
| # | Where | Finding | Disposition |
|---|---|---|---|
| I-1 | US-INT-001 | **Lob/DocPrint print-vendor card**: prototype card + A1 addendum give it a working Connect; the CL-1 matrix names it in NEITHER column (print/PDF channel is v1 per OQ-073, and TD-8/NFR-21 list "print vendor" behind the seam — but the mail-VENDOR connection's activation wave is unplaced) | **Candidate OQ (pack report)** — card renders connectable per the A1 addendum; matrix placement not silently decided |
| I-2 | all epics | **No `integration_connections` (or profile) table is itemized in B2** — the module overview claims ownership ("integration connections, per-tenant, encrypted credentials") but the DDL/addenda registers carry no such table (grep verified) | **CLOSED 2026-09-03 — see I-2 (update) in Part 2 below; B2 Addendum r22.** Was: Schema anchoring → next Eng anchoring batch (pattern of payments P-10 / reports R-1); behavior fully specified; DDL/keys = Eng-Lead 🔒 |
| I-3 | US-INT-001/006/008 | **Transactional ESP card + Bank & lockbox profile card are absent from the prototype grid AND from the A11 key list** (quickbooks…email) — both are v1-REAL per CL-1 (+OQ-074 "connected as the tenant's integration") | Mechanical A1/A11 addendum candidates for the spec owner (extraction lag behind the CL-1 ruling) — pack report |
| I-4 | US-INT-001/009 | Prototype QBO card copy "**Auto-syncs GL nightly**" + S42 history "Accepted" imply LIVE sync | **SUPERSEDED** by BR-LED-020 (file v1 · direct v2) — matches ledger D-7; v1 card = file target + "Live sync — v2" badge |
| I-5 | US-INT-011 | Prototype Stripe card "**Connected · Card + ACH**" | **SUPERSEDED** by OQ-015-as-modified/TD-9 (no tenant-side processor v1); renders "Coming soon · W7" per CL-1 |
| I-6 | US-INT-005 | Mailbox connect-time **test-email recipient** unspecified (A15 addendum offers "a test email"; prototype checkbox only) | Cosmetic — candidate note (pack report); test send itself is ratified |
| I-7 | US-INT-012 | Prototype SSO card copy "**Available on Scale plan**" ties SSO to a commercial tier — no tenant-side plan-gating rule exists (plan tiers = commercial per B6/B10) | CL-1's wave label ("Coming soon · v2") is the v1 card copy; tier-gating law = B10/platform territory — candidate note |
| I-8 | US-INT-008 (+ Itron card copy "AMI reads via SFTP") | **SFTP scheduled-pull execution**: the A1 addendum method set + cadence field let a profile RECORD an SFTP source, but no ratified rule defines the pull job | Seam provision — upload is the working v1 path; pull mechanics = candidate note (pack report) / Eng at activation |

---

# Part 2 · The five tables of the substrate, and the seams (`CR-069`, 2026-09-03)

**Every table below is tenant-scoped and every one carries RLS `FORCE` in its own migration** (hard rule 1).
**Money is `NUMERIC(18,4)`, displayed 2** (hard rule 2) — the only money here is in payloads the owning
modules write; this module stores none. **All owned by `apps.integrations`; `services.py` is the only write
path; `selectors.py` the reads** (B1).

⚠ **`C34` — ANCHOR THESE IN THE SCHEMA BRIEF (B2) BEFORE `integrations/0001` IS WRITTEN.** Discrepancy
**I-2** below records that the module claims tables the DDL registers never carried. **This documentation
pass does NOT edit B2** — that is the build lane's first task (`US-INT-014` TC-7), and I-2 closes in the
same commit as the brief, not here. Until then I-2 reads *OPEN — anchoring specified, brief not yet edited*.

⚠ **THE CREDENTIAL TABLE IS SEPARATE FROM THE CONNECTION TABLE ON PURPOSE** — *"audit is a consumer of the
connection table, never of the credential table."* The connection row **must stay safe to `SELECT *`**, to
log and to put in an audit payload; a gate asserts it holds no encrypted column (`US-INT-014` TC-3).

## 5 · The DDL — design §2.8 as revised by three real specifications

```sql
-- migration 0001 · apps/integrations · after tenancy, before nothing
CREATE TABLE integration_connection (
  id             uuid PRIMARY KEY,
  tenant_id      uuid NOT NULL REFERENCES tenants(id),
  provider_key   text NOT NULL,                   -- manifest key: "email_microsoft"
  label          text,
  environment    text NOT NULL,                   -- production | sandbox
  status         text NOT NULL,                   -- not_set_up | untested | working | not_working | off
  enabled        boolean NOT NULL DEFAULT true,
  cadence        text NOT NULL DEFAULT 'manual',  -- nightly | hourly | manual
  next_run_at    timestamptz,                     -- NULL when cadence = manual
  config         jsonb NOT NULL DEFAULT '{}',     -- NON-SECRET fields only (host, port, send_from,
                                                  -- allowlist, budget override, authority grants…)
  last_test_at   timestamptz,
  last_test_ok   boolean,
  last_test_text text,                            -- one sentence a clerk can read
  connected_by   uuid REFERENCES users(id),
  connected_at   timestamptz,
  created_at     timestamptz NOT NULL,
  updated_at     timestamptz NOT NULL,
  UNIQUE (tenant_id, provider_key, environment)   -- production and sandbox are two connections
);
-- ⚠ NO SECRET MATERIAL IN THIS TABLE. A gate asserts it.

CREATE TABLE integration_credential (
  id            uuid PRIMARY KEY,
  tenant_id     uuid NOT NULL REFERENCES tenants(id),
  connection_id uuid NOT NULL REFERENCES integration_connection(id),
  version       integer NOT NULL,
  is_active     boolean NOT NULL,
  payload_enc   text NOT NULL,                    -- core.crypto EncryptedTextField (AES-256-GCM, kid in ciphertext)
  blind_index   text,                             -- issued secrets only: lookup without decrypting (US-INT-040)
  masked_hint   text NOT NULL,                    -- "••••3F9A" — display only
  expires_at    timestamptz,                      -- the column §1.4 argues for
  rotated_at    timestamptz,
  created_at    timestamptz NOT NULL,
  UNIQUE (connection_id, version),
  EXCLUDE (connection_id WITH =) WHERE (is_active) -- exactly one active, enforced by the database
);

CREATE TABLE integration_run (
  id             uuid NOT NULL,                   -- part of the composite PK below (B2 r22)
  tenant_id      uuid NOT NULL REFERENCES tenants(id),
  connection_id  uuid NOT NULL REFERENCES integration_connection(id),
  operation      text NOT NULL,                   -- C1: which of the provider's operations
  job_id         uuid,                            -- the core/jobs record
  direction      text NOT NULL,                   -- outbound | inbound | inbound_read   (revised: +inbound_read)
  trigger        text NOT NULL,                   -- manual | scheduled | dispatcher | webhook | partner (revised: +partner)
  attempted      integer NOT NULL DEFAULT 0,
  succeeded      integer NOT NULL DEFAULT 0,
  failed         integer NOT NULL DEFAULT 0,
  skipped        integer NOT NULL DEFAULT 0,
  changed        integer NOT NULL DEFAULT 0,      -- the fifth count: "1,240 read, 6 revised" (revised, §2.18.3)
  outcome        text,                            -- queued|running|succeeded|partial|failed|unconfirmed|indeterminate (C26)
  summary        text,                            -- plain language, no rule id
  provider_error text,                            -- ⚠ another tenant's data can arrive here — scrubbed by the adapter,
                                                  --   rendered only on S142 to the owning tenant
  input_hash     text,                            -- file in: the content hash, computed BEFORE parse
  artifact_link  text,                            -- core.jobs.succeed(job_id, result_link)
  items          jsonb NOT NULL DEFAULT '[]',    -- ⚠ ADDED 2026-09-04 (CR-069 wave C, migration 0003):
                                                 --   the items the run COULD NOT do — [{ref, detail, outcome,
                                                 --   provider_text}], failed and skipped only, capped at 200.
                                                 --   NOT the ones it could: those are the notification queue's
                                                 --   per-item rows (US-INT-023), and at 720,000 runs a year ×
                                                 --   93 items a per-item TABLE would be ~67M rows a year to
                                                 --   record that a message went out fine. `failed + skipped -
                                                 --   length(items)` is what the cap left out, said in words.
  trace_id       text NOT NULL,                   -- the eight characters support searches by
  started_at     timestamptz NOT NULL DEFAULT now(), -- ⚠ AMENDED 2026-09-03 (B2 r22): NOT NULL — it is the
                                                  --   partition key, and a NULL key routes to no partition
  finished_at    timestamptz,
  PRIMARY KEY (tenant_id, started_at, id)         -- ⚠ AMENDED 2026-09-03 (B2 r22): PostgreSQL requires the
                                                  --   partition key inside the PK, as audit_log already has
) PARTITION BY RANGE (started_at);                -- core/partitioning.py, yearly, as bill lines already are
-- APPEND-ONLY. No UPDATE after finish, no DELETE. Corrections are new rows. A trigger refuses.

-- Replaces ledger_accounts.qbo_ref, .xero_ref and every column like them — ADDED BESIDE THEM until OQ-INT-1480.
CREATE TABLE integration_target_reference (
  id             uuid PRIMARY KEY,
  tenant_id      uuid NOT NULL REFERENCES tenants(id),
  target_key     text NOT NULL,                   -- which outside system: "qbo" | "xero" | "aclarian" | "kiosk"
  entity_type    text NOT NULL,                   -- ledger_account | tender | route | reversal_reason | meter_type | service
  entity_id      uuid,                            -- NULL when the mapping is to an enum value…
  local_value    text,                            -- …in which case OUR value goes here
  external_value text NOT NULL,                   -- "001.100.51200" | "ACHCHECK" | "R01"
  UNIQUE (tenant_id, target_key, entity_type, external_value)
);
-- The UNIQUE is on the EXTERNAL side on purpose: one of their words maps to exactly one of ours,
-- and two of theirs may share one of ours. Never the other way round.

-- CONDITIONAL on OQ-INT-1482. In the brief so that the feature, if ruled in, is rung 5 already paid for.
CREATE TABLE integration_consent (
  id          uuid PRIMARY KEY,
  tenant_id   uuid NOT NULL REFERENCES tenants(id),
  account_id  uuid NOT NULL REFERENCES accounts(id),
  grantee     text NOT NULL,                      -- who the customer allowed
  scope       jsonb NOT NULL,                     -- what, and how much history
  granted_at  timestamptz NOT NULL,
  granted_by  uuid,                               -- the CUSTOMER, not a member of staff
  expires_at  timestamptz,
  revoked_at  timestamptz,                        -- set, never deleted
  revoked_by  uuid
);
-- Checked on EVERY request, not on the next scheduled run. Rows are kept after revocation.

-- migration 0002 · RLS FORCE on all five, in its own migration
```

| Design decision | Why, in one line | What it costs to skip |
|---|---|---|
| `UNIQUE (tenant, key, environment)` | Production and sandbox are two connections, not two modes of one | The sandbox/production mix-up that ranks first in §1.10 |
| `EXCLUDE … WHERE (is_active)` | Exactly one active credential, enforced by the database | Two active keys and a coin-flip about which one signs |
| `PARTITION BY RANGE (started_at)` | 720,000 rows a year for email alone at 60,000 accounts; the yearly machinery exists | A support query contending with a screen read, forever |
| `provider_error` is its own column | The one column that can carry another tenant's data out of a provider's message | A cross-tenant leak with no tenant boundary crossed — RLS cannot see it |
| UNIQUE on the **external** side | One of their words means exactly one of ours; two of theirs may share one of ours | A mapping that silently multiplies rows |
| `revoked_at`, never a delete | *Who could see my data last year* is a question a customer may ask | A consent history that cannot answer the one question it exists for |
| `input_hash` on the run | *Which runs used that broken mapping* becomes a query | A three-day bad import with no way to enumerate what it touched |
| `changed` as a fifth count | *1,240 read* is not an answer; *1,240 read, 6 revised* is | A reconciling feed whose effect is invisible |

## 6 · Fields the stories add to the substrate (US-INT-013 … 046 §5, consolidated)

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Manifest: key · category · display name · disposition · auth (mode, placement) · network · fields (kinds) · conformance · operations[] | S8 · S141 | design §1.5.1, §2.13.5 · `C1`, `C2`, `C5`, `C7` | **code data** in `apps/integrations/manifests/` — no table | struct | reference-data | refused at load when a declared value is missing (`US-INT-013`) | mapped |
| Operation: direction · initiative · transport · trigger · projection · codec · packaging · envelope status map · idempotency (mode, source, natural key) · respond_after · completion · poll · result_delivery · unknown_value_policy · executor · latency budget · result disposition · fetch plan · budget · safety_parameters · mutates_partner_state · must_not_skip · catch_up_policy · timeout · concurrency · breaker | — | `C1`–`C36` | manifest; each run row names `operation` | struct | reference-data | every operation names idempotency mode AND completion mode | mapped |
| Per-operation state · last run | S8 card rows · S142 | `C1` | computed from the latest `integration_run` per `(connection_id, operation)` | enum/ts | computed-display | words: *Working · Not working · Not tested yet · Not set up* | mapped |
| Environment (in words) · cadence · `next_run_at` · per-connection offset | S8 · S141 · S142 | `BR-INT-024`, `026` | `integration_connection.environment` · `.cadence` · `.next_run_at`; offset derived from id | enum/ts | user-input / system-derived | tenant's timezone; `manual` → NULL | mapped |
| Allowlist · budget spend · authority grants · issued-key last used | S141 · S142 · S143 · S144 | `C5`, `BR-INT-034`, `C22`, `C30` | `integration_connection.config` (non-secret) | jsonb | user-input / system-derived | never a secret in `config` | mapped |
| Five counts · outcome · summary · `provider_error` (scrubbed) · `input_hash` · artifact · trace id | S142 | `BR-INT-018`, `039`, `020` | `integration_run` | int/enum/text | system-derived | append-only; `attempted = succeeded + failed + skipped` or `unconfirmed` | mapped |
| The items a run could not do (`ref` · `detail` · `outcome` · `provider_text`) | S142 run detail only | `BR-INT-040` (P4 — per-item results, never a batch boolean) | `integration_run.items` | jsonb | integration (scrubbed) | unsuccessful items only, capped at 200; `ref` is the customer's own number and never a database id (B14 rule 31) | mapped 2026-09-04 |
| Credential version · active · hint · `expires_at` | S141 (hint) · S142 | `BR-INT-025`, `042` | `integration_credential` | int/bool/text/ts | user-input → encrypted / system-derived | one active (EXCLUDE) | mapped 🔒 |
| Their word → our value (accounts · tenders · return codes · routes · meter types) | S143 | `BR-INT-032` | `integration_target_reference` | text/uuid | user-input / integration | UNIQUE external side | mapped |
| GIS difference queue (premises · field · we hold · the city says · class · night) | S143 tab 2 | `C22`–`C25` | run artifact rows (queued items) — writes to `premises` only through metering's service, **stubbed `OQ-INT-1470`** | struct | system-derived | seven classes; money-path columns `never` | mapped 🔒 |
| Consent: grantee · scope · until · revoked | S145 · S146 | `BR-INT-036` | `integration_consent` | text/jsonb/ts | customer-input | **conditional `OQ-INT-1482`** | mapped (conditional) |
| Channel (`KIOSK`) · kiosk reference on a payment | payment detail · report | `C31` | `payments.channel` · `payments.external_ref` — **payments' columns, written by payments' service** | enum/text | integration → service | unknown channel → `OTHER` | seam (I-11) |
| Sender card: host · port · send-from · password | S8 Notifications · S141 | `C35` | `integration_connection.config` · `integration_credential` v1 — **`smtp_secret_ref` retired by data migration** | text/int/encrypted | migrated once | no reader after `US-INT-026` | mapped |

## 7 · Seams — where this module hands over, and never writes (B1)

| Seam | File | What crosses | Direction |
|---|---|---|---|
| notifications | `seams/notifications.py` | per-item send results → queue-row states; bounce feedback; the read-model the dispatcher and the S8 panel read | integrations → notifications' service (`BR-NOT-005`) |
| payments | `seams/payments.py` | inbound payment/return payloads → `record_payment` (the ONE inbound write path); lockbox rows; channel + reference | integrations → payments' service (`BR-PAY-003`, `036`) |
| ledger | `seams/ledger.py` | the export file's period and target; readiness *N unmapped*; account strings through mapping rows — **reads only** | integrations ← ledger (reads) |
| metering | `seams/metering.py` | readings (reconcile → supersede / correction); premises fields under authority grants; the money-path column list | integrations → metering's service — **stubbed `OQ-INT-1470`, `OQ-INT-1485`** |
| assets | `seams/assets.py` | register sync (size · type · route) | integrations → assets' service — **stubbed `OQ-INT-1485`** |
| identity | `apps/identity` | `MachineCredentialAuthentication` for partners — **identity's to build** | identity → integrations (auth class) |
| portal | `apps/portal/api.py` | the customer's consent screens | portal → integrations' service (conditional) |

## Discrepancies & seams — Part 2 additions (verified vs code at `2.128.2`, 2026-09-03)

| # | Where | Finding | Disposition |
|---|---|---|---|
| I-2 (update) | all epics | The five tables are specified in full above; **B2 still carries none of them** | **CLOSED 2026-09-03 (`CR-069` wave A, task A1)** — `04-docs/02-decisions/02-database-design-brief.md` §2 now carries `### Module: integrations` with all five tables, §3 lists them for RLS, §5 carries `integration_run` (yearly), and **Addendum r22** records the two PostgreSQL-forced amendments to the DDL below (`started_at NOT NULL`, composite primary key) and the two cross-module FKs owed review. The commit precedes `integrations/0001` (`US-INT-014` TC-7). |
| I-9 | US-INT-040 · 041 | **No machine authentication exists** — `DEFAULT_AUTHENTICATION_CLASSES` is `IdentitySessionAuthentication` only. The partner surface is specified; its authentication is identity's | Cross-module seam: a companion identity story is owed; integrations declares the `issued_secret` field kind and the connection only |
| I-10 | US-INT-042 · 043 | `premises` carries `external_ref`, `lat`, `lng`, `city`, `state`, `postal_code`, `inside_city_limits` (`metering/models.py:264+`) — every column the GIS feed names exists; **the flag *confirmed by the city* does not** | `premises.custom_data.gis_confirmed_on` via metering's service, stubbed `OQ-INT-1470` |
| I-11 | US-INT-044 | `payments/webhooks.py` is **577 lines, built 2026-09-03 (`CR-060` `C21`)**, idempotent on `webhook_key` — the design's *"one docstring line"* is stale; **`payments.channel` does not exist** | The door reuses the handler's guards; `channel` + `external_ref` are payments' columns and payments' migration |
| I-12 | US-INT-026 | `notifications/sender_config.py:50` still reads *"`smtp_secret_ref` holds the NAME of a secret"*; `core/crypto.py` (583 lines) has existed since 24 Aug | Fold by data migration (`C35`); `smtp_secret_ref` retired |
| I-13 | US-INT-037 | `ledger_accounts.qbo_ref` / `.xero_ref` (`ledger/models.py:348-349`) — two vendor-named columns on a signed finance table | Table added BESIDE them; retiring them is `OQ-INT-1480`; **no third column is ever added** |
| I-14 | US-INT-029 | **No `beat_schedule` anywhere in `06-backend/config/`** — the scheduler process runs and schedules nothing | The two entries of `US-INT-029` are the product's first |
| I-15 | US-INT-013 | Two live third-party calls have no connection record: the Census geocoder (`geocode_premises`, `CR-028` D6) and the Esri tiles the browser fetches | **Defects, not changes** (`CR-069` §0.3) — filed by the build lane; both become manifests (`geocoder_census`, `map_tiles_public`) |
| I-16 | US-INT-033 | The accounting export's `target` column mixes a destination with a format — two values are places, two are file shapes | **Defect, not a change** — becomes `destination × codec` on the substrate |
