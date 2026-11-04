# EP-INT-05 — The substrate under every connector: manifests, five tables, the adapter protocol, the queue, and the gate

**Module:** integrations · **Wave:** phase 1 of `CR-069` · **Screens:** S8 Integrations tab (the grid, changed by `C1`) · S141 connect/manage modal · **Status:** draft (`CR-069`, written 2026-09-03 from *The Integration Substrate*, read at `2.120.1`; product now `2.128.2`)

## Scope

**In:** everything phase 1 ships and nothing a provider needs — the manifest registry with **operations** as its unit (`BR-INT-028`, `BR-INT-037`), the **five tables** anchored in the schema brief before migration `0001` (`C34`), the adapter protocol with **four methods and only four** (`BR-INT-038`), job kinds on a **dedicated queue with its own consuming worker** (`BR-INT-041`), **server-side** refusal of a coming-soon key with zero secret persistence (`BR-INT-001`, `US-INT-017`), one card for a provider with several operations (`C1`), and the connect/manage modal generated from the manifest's field list with the three field kinds a plain field cannot express (`C2`, `T27`).

**Out:** every adapter (`EP-INT-07` onward ships SMTP first), the run record's behaviour (`EP-INT-06`), scheduling (`EP-INT-08`), mappings and codecs (`EP-INT-10`) — and the card grid's existing law, which is `US-INT-001` and is not rewritten here: this epic **changes** that grid (operations under a card) and does not replace it.

**Exit test of the phase, which is a demonstration and not an opinion (`CR-069` §12):** the Settings grid renders every card from the registry, every one reading **Not set up**, and a connect call to a coming-soon key is **refused by the API, not just the button**.

⚠ **PHASE 1 SHIPS NO PROVIDER, ON PURPOSE.** All four runners are built here, including the one with no connector behind it (the SERVE quadrant — a partner reading from us), because *"a runner with no connector is a few hundred lines and a conformance test; a missing runner discovered in a sales cycle is a schema migration on a signed finance table."*

## Capability matrix (list screens only — B9 conformance)

No B9 list screen in this epic. S8 Integrations is a card grid (`US-INT-001`); S141 is a modal; the run list is S142 (`EP-INT-06`).

## Stories

---
id: US-INT-013
epic: EP-INT-05
module: integrations
screens: [S8]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-001, US-INT-004]
journeys: [J48]
rules: [BR-INT-001, BR-INT-028, BR-INT-037, BR-INT-053]
golden_tests: []
finance_calc: none
---
### US-INT-013 — The manifest registry: a provider is one declarative object, and seven readers read it

**1 · Details** — As **an engineer adding a provider**, I want **to declare it as one manifest — its key, category, display name, disposition, auth mode and placement, network policy, fields with their kinds, conformance claim, and its operations, each with its own direction, initiative, transport, trigger, projection, codec, packaging, envelope status map, idempotency mode, reply position, completion mode, unknown-value policy and test action** — so that **adding a provider touches no screen, no endpoint and no migration**.

`apps/integrations/registry.py` is today one docstring line. It becomes THE registry: manifests are data in `apps/integrations/manifests/` (one file per provider), registered at `AppConfig.ready()`. **Seven readers, one source** — the card grid (category · name · disposition), the modal field slot (fields · field kinds), runner selection (direction × initiative), the projection, the scheduler (cadence policy · catch-up rule), the response envelope, and the auth mode. **Every arrow points inward: the registry reads nothing and calls nothing.** A coming-soon card is the same object with `disposition = COMING_SOON` and no adapter registered.

**Registration refuses, at load and never at run time:** an operation missing its idempotency mode or its completion mode (`CR-069` §13 gate 3) · a reply position before `authenticate` (`BR-INT-030`) · a codec name not in the codec registry (`BR-INT-033`) · a `certified` conformance claim with no certificate id (`BR-INT-053`) · a field of an unknown kind (`BR-INT-043`) · a provider with zero operations (`BR-INT-028`).

Entry: `AppConfig.ready()`. Exit: `GET /integrations` serves every manifest joined to this tenant's connection state, and S8 draws it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-037` | P1 — configuration is data, not code; adding a provider touches no screen, endpoint or migration | CONFIRMED — the requester's own sentence, `CR-069` §0 |
| `BR-INT-028` | A provider is a set of operations; one partner is one card, one credential | PROPOSED — design §2.13, `C1` |
| `BR-INT-001` | The v1 connector matrix decides `disposition`; nothing else may | CONFIRMED — PO CL-1, 2026-08-08 |
| `BR-INT-053` | A conformance claim carries its evidence; `certified` without a certificate id is refused | PROPOSED — design §2.16.2, `C7` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Brazos Bend has no connections; Alex Reed opens S8 Integrations | Every registered manifest renders as a card — **17** with the fixture below — and every card reads **Not set up** (doc TC-INT-01). No card shows a rule id or a database id |
| TC-2 · **negative** | A manifest registers an operation with no `idempotency.mode` | `AppConfig.ready()` raises naming the provider key and the operation; the process does not start. **Refused at load, not at run time** |
| TC-3 · **negative** | A manifest declares `respond_after = authenticate`'s predecessor (reply before authentication) | Refused at load with the operation named (`BR-INT-030`) |
| TC-4 · **negative** | A manifest declares `conformance = certified` and no `certificate_id` | Refused at load (`BR-INT-053`); the same manifest with `self_declared` loads |
| TC-5 · **gate** | `grep -rn "provider_key ==" 06-backend/apps --include=*.py` outside `apps/integrations/adapters/` and `manifests/` | Zero hits. The gate is first shown RED by adding `if provider_key == "email_smtp"` to `services.py` (law 7) |
| TC-6 | `payments_card` is `COMING_SOON(wave="W7")` with no adapter | The registry answers *no adapter registered* as a value; the grid draws the card; nothing raises |
| TC-7 · **tenant isolation** | J. Okafor (Lone Star Ridge) calls `GET /integrations` while Brazos Bend has a working mailbox | The same 17 manifests, every one **Not set up** — connection state is joined per tenant under RLS `FORCE`; Brazos Bend's row is not in the payload |

**4 · Test Data** — Seventeen manifests, in the seed order the grid draws them: `email_microsoft` (Email · LIVE · OAuth redirect) · `email_google` (Email · LIVE · OAuth redirect) · `email_smtp` (Email · LIVE · password) · `email_bulk` (Email · LIVE · API key + sending domain; *"For 6,000 bills a cycle and up. A mailbox cannot send that many."*) · `bank_lockbox_file` (Banking · LIVE · upload or SFTP; codecs BAI2, CSV, OFX, QBO, QFX, camt.053) · `accounting_file` (Accounting · LIVE · no credential; codecs QBO, Xero, CSV, IIF) · `print_vendor` (Print · LIVE per `BR-INT-017`; format still the vendor's to state) · `payments_kiosk` (Payments · LIVE, phase 5 · three operations: Account lookup, Payments, Returns) · `payments_card` (Payments · COMING_SOON W7) · `meters_neptune360` (Meters · LIVE, phase 4 · sixteen operations, one credential) · `meters_mdm` (Meters · COMING_SOON v2 — Itron/Sensus, NFR-27 gate) · `gis_city` (Maps & addresses · LIVE, phase 4 · address search, nightly reconciliation, map tiles) · `map_tiles_public` (Maps & addresses · LIVE · executor `browser`, no secret — the Esri call the browser already makes) · `geocoder_census` (Maps & addresses · LIVE · the one outbound call the product makes today, moved onto the substrate) · `gl_partner` (Accounting · LIVE, GL track · initiative `them`, auth `they_hold_ours`) · `sms_twilio` (Messaging · COMING_SOON v1.1) · `sso` (Identity · COMING_SOON v2). Tenants: Brazos Bend Utilities (`seed_demo`), Lone Star Ridge WSC (isolation). Actor: Alex Reed, System Admin.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `key` · `category` · `display_name` · `disposition` | S8 card | design §1.5.1 revised manifest | none — code data in `manifests/` | text / enum | reference-data | key unique across the registry; `disposition ∈ {LIVE, COMING_SOON(wave)}` |
| `auth.mode` · `auth.placement` | S141 | §2.15.2 `C2` · §2.13.5 | none | enum | reference-data | `{we_hold_theirs, they_hold_ours, token_exchange, none}` × `{header, bearer, query, redirect}` |
| `network.allowlist` | S141 | §2.15.2 `C5` | `integration_connection.config.allowlist` (non-secret) | CIDR list | user-input | valid CIDR; empty = not enforced |
| `fields[]` (name · label · kind) | S141 field slot | §2.3.4 Figure 26 · `T27` | none; values land in `config` (non-secret) or `integration_credential.payload_enc` (secret kinds) | closed enum of kinds | reference-data | kind ∈ `{text, email, host, port, secret, select, redirect, mapping_editor, issued_secret}` |
| `operations[]` | S8 card rows · S142 | §1.5.1 · §2.13.2 | none; each run row names `operation` | list | reference-data | ≥ 1; each declares idempotency mode AND completion mode or the manifest is refused |
| `operation.envelope.status` | — | §2.15.2 `C3` | none | map | reference-data | e.g. `{ok: 200, duplicate: 409}` |
| `operation.respond_after` | — | §2.15.3 `C6` | none | enum | reference-data | `{authenticate, dedupe, persist, apply}`; inbound only; never before `authenticate` |
| `conformance` | S141 detail | §2.16.2 `C7` | none | struct | reference-data | `{standard, claim ∈ {self_declared, compatible, certified}, evidence}` |

**6 · Acceptance**
- Given the seventeen manifests, when S8 loads for a tenant with no connections, then seventeen cards render from the registry and each reads *Not set up*.
- Given a manifest that omits a required declared value, when the app starts, then it refuses to start and names the provider and the field.
- Given a new provider added as one manifest file and one adapter class, when the branch is diffed, then no file outside `manifests/` and `adapters/` changed — and the gate proves it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. (`OQ-INT-1483`, the words we may use about standards, blocks `US-INT-040`'s badge copy, not the registry.)

---
id: US-INT-014
epic: EP-INT-05
module: integrations
screens: [S8, S141, S142]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-013]
journeys: [J48, J49, J51]
rules: [BR-INT-003, BR-INT-014, BR-INT-025, BR-INT-026, BR-INT-032, BR-INT-036, BR-INT-039]
golden_tests: []
finance_calc: none
---
### US-INT-014 — The five tables, and why not one — anchored in the schema brief BEFORE the migration

**1 · Details** — As **a system administrator**, I want **my connection, its credential, every attempt, every foreign name for one of our things, and every permission a customer granted stored in five separate tables** — so that **a secret can be rolled back in one row, a run history survives a disconnect, a connection row is safe to read anywhere, a new partner costs rows and not a migration, and a customer can ask who could see their data last year**.

`integration_connection` (rarely changes — **no secret material, safe to `SELECT *`, to log and to put in an audit payload**) · `integration_credential` (versioned, never overwritten, exactly one active) · `integration_run` (constantly — append-only, partitioned yearly on `started_at` with `core/partitioning.py`, carries the trace id) · `integration_target_reference` (their word for our thing — UNIQUE on the external side) · `integration_consent` (CONDITIONAL on `OQ-INT-1482`; `revoked_at`, never a delete). All five under RLS `FORCE` in their own migration. The DDL is `03-field-map.md` §5.

⚠ **`C34` IS THE ORDERING, NOT A NICETY.** The field map's discrepancy **I-2** — the module claims to own tables the DDL registers never carried — is closed in the schema brief **before** `integrations/0001` is written, because *"the re-cut register begins at the migration."* The migration is written against a brief that names all five.

⚠ **THE CREDENTIAL TABLE IS SEPARATE ON PURPOSE.** *"Audit is a consumer of the connection table, never of the credential table."* A lane that merges them has made every audit read touch encrypted secrets.

Entry: schema brief row → `0001_initial` → `0002_rls_force`. Exit: `services.py` is the only write path (B1); `selectors.py` the reads.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-003` | Credentials never rendered back, never logged, never in audit payloads — masked refs only | CONFIRMED — B7 + A11 addenda |
| `BR-INT-025` | A credential is versioned, never updated; exactly one active, enforced by the database | PROPOSED — design §1.4, §2.8 |
| `BR-INT-026` | Production and sandbox are two rows — `UNIQUE (tenant_id, provider_key, environment)` | PROPOSED — design §1.10.5, §2.8 |
| `BR-INT-039` | P3 — every attempt is a durable, append-only record with a trace id | PROPOSED — design §1.2 |
| `BR-INT-032` | A foreign name is a row in `integration_target_reference`, never a column | PROPOSED; ledger half OPEN → `OQ-INT-1480` |
| `BR-INT-036` | A consent belongs to the customer; `revoked_at`, never a delete | **OPEN → `OQ-INT-1482`** — the table is in the brief; nothing writes it until ruled |
| CLAUDE.md hard rule 1 | RLS `FORCE` on every tenant table | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **PG** | Two `is_active = true` credential rows are written for one connection in one transaction | The database refuses the second — `EXCLUDE (connection_id WITH =) WHERE (is_active)` — below the application (doc TC-INT-07) |
| TC-2 · **PG · isolation probe** | With no `app.tenant_id` set, `SELECT count(*)` on each of the five tables | **Zero rows on all five** (doc TC-INT-09). RLS `FORCE` is in its own migration |
| TC-3 · **gate** | `10-scripts/gates/` asserts no column of `integration_connection` is an `EncryptedTextField` and no column name matches `secret|token|password|payload` | Passes; first shown RED by adding `api_key_enc` to the model (law 7) |
| TC-4 · **PG · negative** | `UPDATE integration_run SET succeeded = 93 WHERE finished_at IS NOT NULL` | Refused by trigger — append-only after finish; corrections are new rows (hard rule 4's shape) |
| TC-5 · **negative** | A second `production` row for `email_smtp` on Brazos Bend | Refused by the UNIQUE triple; a `sandbox` row for the same key is accepted — two connections, not two modes |
| TC-6 · **tenant isolation** | Lone Star Ridge requests Brazos Bend's connection by id | **404** with a body byte-identical to a genuinely absent row (doc TC-INT-08) |
| TC-7 · **ordering** | `git log` of `04-docs/02-decisions/02-*schema*` (the B2 brief) and `apps/integrations/migrations/0001_initial.py` | The brief names all five tables in a commit that **precedes** the migration; field map I-2 reads CLOSED in the same commit |

**4 · Test Data** — Brazos Bend · `email_smtp` · `production` · label *Billing mailbox* · status `working` · credential v1 (`••••3F9A`, no expiry). Sandbox twin: same key, `sandbox`, second row. Runs: `attempted 93 · succeeded 86 · failed 7 · skipped 0 · changed 0 · partial` (1 Aug 06:02) and `93 · 0 · 0 · 0 · 0 · unconfirmed` (1 Jul 06:03, provider returned 200 with no count). Target references for `accounting_file`/QBO: ledger account `4100` → `"4100"`; for `payments_kiosk`: tender `ACHCHECK` → *bank transfer*, `ACHSAVINGS` → *bank transfer*. No consent rows (blocked).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| connection: `provider_key` · `label` · `environment` · `status` · `enabled` · `cadence` · `next_run_at` · `config` (non-secret) · `last_test_at/ok/text` · `connected_by/at` | S8 · S141 · S142 | design §2.8 | `integration_connection` | text/enum/jsonb/ts | user-input · system-derived | `status ∈ {not_set_up, untested, working, not_working, off}`; `cadence ∈ {nightly, hourly, manual}`; `next_run_at` NULL when manual |
| credential: `version` · `is_active` · `payload_enc` · `masked_hint` · `expires_at` · `rotated_at` | S141 (hint only) · S142 (expiry) | §2.8 | `integration_credential` | int/bool/`core.crypto.EncryptedTextField`/text/ts | user-input → encrypted | UNIQUE `(connection_id, version)`; EXCLUDE one active |
| run: `operation` · `direction` · `trigger` · five counts · `outcome` · `summary` · `provider_error` · `input_hash` · `artifact_link` · `trace_id` · `started_at` · `finished_at` | S142 | §2.8 + revision | `integration_run` PARTITION BY RANGE (`started_at`) | enums/int/text | system-derived | `direction ∈ {outbound, inbound, inbound_read}`; `trigger ∈ {manual, scheduled, dispatcher, webhook, partner}`; `outcome ∈ {queued, running, succeeded, partial, failed, unconfirmed, indeterminate}` |
| target reference: `target_key` · `entity_type` · `entity_id` · `local_value` · `external_value` | S143 | §2.8.1 | `integration_target_reference` | text/uuid | user-input | UNIQUE `(tenant_id, target_key, entity_type, external_value)` — the EXTERNAL side |
| consent: `account_id` · `grantee` · `scope` · `granted_at/by` · `expires_at` · `revoked_at/by` | S145 · S146 | §2.8.1 | `integration_consent` | uuid/text/jsonb/ts | customer-input | `granted_by` is the CUSTOMER; rows never deleted; **OPEN `OQ-INT-1482`** |

**6 · Acceptance**
- Given the schema brief names five tables, when `0001_initial` and `0002_rls_force` run on PostgreSQL, then all five exist under RLS `FORCE` and a query with no tenant sees nothing.
- Given the connection table, then `SELECT *` on it can be logged and audited without leaking a secret, and a gate says so.
- Given credential v1 active, when v2 is written, then v1 is retained inactive and the database itself refuses a second active row.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1480` | Does a per-target reference row replace `ledger_accounts.qbo_ref` / `.xero_ref` (a migration on a signed finance table), and should the chart carry fund / department / object segments? | Retiring the two columns; nothing else — the table ships beside them | PO (finance) | OPEN |
| `OQ-INT-1482` | Is authorised third-party data access (a customer letting a company read their usage) in scope at all? | Any writer of `integration_consent` | PO (market) | OPEN |

---
id: US-INT-015
epic: EP-INT-05
module: integrations
screens: [S141, S142]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-013, US-INT-014]
journeys: [J48, J49]
rules: [BR-INT-004, BR-INT-019, BR-INT-038]
golden_tests: []
finance_calc: none
---
### US-INT-015 — The adapter protocol: validate, test, execute, describe — and nothing else

**1 · Details** — As **an engineer**, I want **the only code that knows a provider exists to be one class with four methods** — `validate(config) → FieldErrors` (shape only, cheap, no network, runs before anything is stored) · `test(conn) → TestResult` (the smallest REAL instance of the operation, answered in one sentence a clerk can read) · `execute(conn, work) → RunResult` (do the thing once, for a batch; **per-item outcomes, never a boolean**; the runtime owns retry, this owns one attempt) · `describe(conn) → str` (the masked summary line on the card, never a secret) — so that **a provider's API change is one file and never a schema migration**.

`apps/integrations/adapters/` — one file per provider; a registry binds a key to a class. The adapter owns **translation and nothing else**: no retry, no scheduling, no persistence (`BR-INT-038`). **The plaintext credential exists at exactly one point — in memory, inside `test()` or `execute()`, for the length of one call** (design Figure 14). Adapters test against recorded fixtures; the provider-sandbox contract test is a separate scheduled run, never CI.

⚠ **ON `test()` — the red pen the design underlines twice.** *"I have seen this method built as 'does the API key parse' more times than any other mistake in this space… A test that cannot fail the way production fails is worse than no test, because someone trusted it."* Send one message. List one directory. Write one empty file. If the provider offers no safe instance, the manifest says so and the card reads *cannot be tested until first use*.

**The conformance kit:** one suite that EVERY adapter runs unchanged, driven off the manifest. **If a new connector requires the suite to change, that is the signal — a design review, not a merge.**

Entry: a registered manifest naming an adapter class. Exit: the runtime calls the four methods and records a run row (`US-INT-020`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-004` | Provider-agnostic seam; no provider hardcoded into business logic | CONFIRMED — B7 |
| `BR-INT-038` | P2 — the adapter is the anti-corruption layer; translation only | PROPOSED — design §1.2, §1.5.2 |
| `BR-INT-019` | `test()` performs the smallest real instance; a provider with no safe instance declares it | PROPOSED — design §1.5.2 |
| `BR-INT-003` | `describe()` never contains a secret | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex presses **Test it now** on the SMTP connection with a correct password and a typed recipient | `test()` sends **one real message** to the typed address; result *Sent one test message to alex@brazosbend.example*; card turns **Working** |
| TC-2 | Same, password `hunter2 ` with a trailing space | Screen reads **the mail server rejected the password**; the run row records `failed` with that sentence and a trace id (doc TC-INT-04) |
| TC-3 · **negative** | An adapter's `execute()` returns `True` instead of per-item results | The runtime refuses to record it as success — outcome `unconfirmed`, summary *the provider did not say how many* — and the conformance kit fails the adapter |
| TC-4 | `describe()` on the working SMTP connection | *billing@brazosbend.example · Custom SMTP* — assert the fixture password appears in neither `describe()` nor any log line captured during the call |
| TC-5 | A manifest declares `test_action = None` (no safe instance) | The card reads **cannot be tested until first use**; `POST /integrations/{key}/test` is refused with that sentence; status stays `untested` until the first real run |
| TC-6 · **conformance kit** | The 37-case suite runs against every registered adapter, driven off the manifest | Every LIVE adapter passes unchanged; adding `adapters/kiosk.py` requires **no edit** to the suite. If it does, the CI step reports *design review needed* |
| TC-7 · **gate** | `grep -rn "import smtplib\|import requests\|paramiko" 06-backend/apps --include=*.py` | Hits only inside `apps/integrations/adapters/` and `core/` — the only code that knows a protocol exists |

**4 · Test Data** — SMTP fixture server (recorded, no network): host `smtp.brazosbend.example`, port `587`, user `billing@brazosbend.example`; good password `Ew3!kQ9-lockbox`; bad password `hunter2 ` (trailing space — the day-one failure). Typed test recipient `alex@brazosbend.example`. Adapter fixture that returns a bare `True` (TC-3). Adapter fixture that **sleeps 90 s then succeeds** (used by `US-INT-022`).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `TestResult.ok` · `TestResult.sentence` | S141 · S142 | design §1.5.2 | `integration_connection.last_test_ok` · `.last_test_text` · a run row `trigger = manual` | bool/text | integration | sentence ≤ one clause, no rule id, no provider status code |
| `RunResult.items[]` (`ref`, `outcome`, `provider_text`) | S142 detail | §1.5.2 · P4 | `integration_run` counts; per-item detail in the run artifact | list | integration | never a bare boolean |
| `describe()` line | S8 card | §1.5.2 | computed | text | computed-display | contains no secret; masked hint only |

**6 · Acceptance**
- Given a wrong password, when Test it now is pressed, then the clerk reads the mail server's own verdict in words and the credential appears in no log, no audit row and no response.
- Given a new provider, when its adapter is added, then the conformance kit runs against it with no change to the kit.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. (Encryption key management — where the key comes from, what happens when it is absent, how rotation works — is a HUMAN-REVIEW item on `core/crypto.py`, to be signed **before phase 2 stores the first real credential**; it is not a question this story may answer.)

---
id: US-INT-016
epic: EP-INT-05
module: integrations
screens: [S141, S142]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-014]
journeys: [J48, J53]
rules: [BR-INT-041, BR-INT-022]
golden_tests: []
finance_calc: none
---
### US-INT-016 — Job kinds and a dedicated queue — and the consuming worker, or neither

**1 · Details** — As **an operator**, I want **integration work on its own worker queue** — so that **a hanging mail server cannot stall a bill run**.

`apps/integrations/apps.py` registers the job kinds — `integration.run`, `integration.test`, `integration.sweep_due`, `integration.sweep_expiry`, `integration.inbound_process` — and the queue name `integrations` with `core.jobs.job_queue()`, which `config/celery_routes.py` already reads. **And `docker-compose.yml` gains the consuming worker `celery-integrations` in the same commit** — `DEF-320` is what a route with no consumer looks like: the work is accepted, 202 is answered, and nothing ever runs. **Both halves ship or neither does.**

The two orderings that carry the design (Figure 16): **the job ROW is written before the broker message and before the 202**, so a broker that loses the message loses nothing durable; and **the adapter call happens in a different process from the request**, which is why a ninety-second provider cannot hold a web worker. Retry is the framework's — backoff with jitter, **never a new job**. The soft time limit (8,220 s, shipped `2.119.0`) is inherited, not written.

Entry: `services.py` calls `core.jobs.enqueue(kind, scope_key, …)`. Exit: `celery -Q integrations` runs `core.jobs.run_job`; a run row is written (`US-INT-020`).

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-041` | P5 — its own named queue WITH its own consuming worker; a route with no consumer accepts work and never runs | PROPOSED — design §1.2, `DEF-320` |
| `BR-INT-022` | Hard timeout on every call; a slow provider degrades to a queue, never to an outage | PROPOSED — design §1.7 |
| B12 r1 §3 · TD-17 | Async = Celery on Redis; 202 + job id | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `POST /integrations/email_smtp/test` | `202` with a poll url; **the `jobs` row exists before the broker message is published**, asserted by ordering the two writes in the test double |
| TC-2 · **gate** | `config/celery_routes.py` routes `integration.*` to `integrations` and `docker-compose.yml` lists no `celery-integrations` service | Gate `g59`'s pattern fails the build naming the queue. First shown RED by deleting the compose service (law 7) |
| TC-3 | Tenant A's SMTP adapter fixture hangs 90 s on the `integrations` queue while tenant B's bill run is enqueued on `billing` | Tenant B's run starts within its normal latency; the integrations worker alone is busy |
| TC-4 | A provider returns 503 twice then succeeds | One job id throughout; three attempts recorded on the same job with backoff **and jitter** (two identical fixtures do not retry at the same instant) |
| TC-5 · **negative** | The broker drops the message after the 202 | The job row is `queued` with no worker pickup; the due sweep re-enqueues by scope key idempotently — **no second job row** |
| TC-6 · **tenant isolation** | Two tenants enqueue `integration.test` for the same provider key | Two scope keys (`tenant_id` is part of the key); neither dedupes the other |

**4 · Test Data** — `JOBS_EAGER=false --reuse-db` (design §2.10, `DEF-567`). Compose services after this story: `celery-billing` (exists) + `celery-integrations` (new). Fixture adapter *slow*: sleeps 90 s then succeeds. Brazos Bend bill run of 240 bills (J17's fixture) on the billing queue.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| job kind · queue | — | design Figure 16 · `config/celery_routes.py` | `jobs.kind` · router | text | reference-data | kind registered in `AppConfig.ready()`; queue `integrations` |
| scope key | — | `core/jobs.py` enqueue | `jobs.scope_key` UNIQUE-ish (idempotent enqueue) | text | system-derived | `tenant_id · connection_id · operation · window` |
| poll url | S141 progress band | B12 r1 §3 | — | url | computed-display | returned with 202 |

**6 · Acceptance**
- Given a test is requested, then the durable job row exists before anything is published and before the reply.
- Given a dead mail server on one tenant, then another tenant's bill run completes on time.
- Given the queue is registered, then the compose file names its worker, and a gate refuses the build otherwise.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-017
epic: EP-INT-05
module: integrations
screens: [S8, S141]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-011, US-INT-012, US-INT-013]
journeys: [J48]
rules: [BR-INT-001, BR-INT-003, BR-INT-037]
golden_tests: []
finance_calc: none
---
### US-INT-017 — Server-side gating of coming-soon providers: refused by the API, with zero secret persistence

**1 · Details** — As **a security reviewer**, I want **a connect call to a coming-soon key refused by the API with zero secret persistence** — so that **a disabled button is not the only thing standing between a gated provider and a stored credential**.

`US-INT-011`/`012` own the card's *Coming soon · W7* copy and the disabled button; this story is the **server half** and phase 1's exit test. `POST /integrations/{key}/connect`, `/test`, `/run`, `PATCH /integrations/{key}` and `POST …/credential` on a manifest whose `disposition` is `COMING_SOON` answer a catalogue refusal — **no connection row, no credential row, no partial anything**. The refusal names the wave in words a clerk reads (*Coming soon · W7*), is at most six words (B14 rule 33), and its `message_key` is in all eleven locale catalogues (`g15`, `g32` baseline 0). A malformed field on a LIVE key likewise stores nothing — not the connection, not a partial credential (`BR-INT-003`).

Entry: any write route with a coming-soon key. Exit: refusal envelope `{code, message_key, params, field_errors, br_ref, trace_id}` — the existing shape, no new one.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-001` | Coming-soon = Connect disabled at UI **and API** | CONFIRMED — PO CL-1, 2026-08-08 |
| `BR-INT-003` | Zero secret persistence on refusal | CONFIRMED |
| `BR-INT-037` | A coming-soon card is the same manifest object with no adapter | CONFIRMED — P1 |
| B14 rule 33 | A refusal sentence caps at five or six words | CONFIRMED — PO 2026-08-30 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `POST /integrations/payments_card/connect` with a valid-looking key | Refused; `integration_connection` and `integration_credential` row counts unchanged; no log line contains the key (doc TC-INT-02) |
| TC-2 | `/test`, `/run`, `PATCH`, `/credential` on `payments_card` | Each refused with the same catalogue code; nothing written |
| TC-3 · **copy** | The refusal sentence | ≤ 6 words, names the wave (*Coming soon · W7*), no `BR-` and no rule id; `message_key` present in all 11 catalogues |
| TC-4 · **negative** | `POST /integrations/email_smtp/connect` with `port = "abc"` on a LIVE key | `field_errors` returned; **no connection row and no credential row** — not a partial one (doc TC-INT-03) |
| TC-5 · **negative** | `POST /integrations/nope/connect` (unknown key) | `404` with a body identical to any absent resource |
| TC-6 · **audit** | After TC-1 | One `audit_log` row `integration.connect_refused` with the key name and **no payload field** — a refusal is a lifecycle event (`BR-INT-014`) and carries no secret |

**4 · Test Data** — `payments_card` (`COMING_SOON`, wave W7), `sms_twilio` (v1.1), `sso` (v2), `meters_mdm` (v2). A valid-looking key `sk_live_51H…` that must appear in no table and no log. Actor: Alex Reed; negative actor Priya Menon (Billing Clerk — Settings denied server-side regardless, A1).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| refusal envelope | S141 | `core/errors.py` catalogue | — | struct | system-derived | existing shape; new catalogue codes `INT_COMING_SOON`, `INT_UNKNOWN_KEY` |
| audit row `integration.connect_refused` | S61 viewer | `BR-INT-014` | `audit_log` | jsonb | system-derived | no payload; key name and wave only |

**6 · Acceptance**
- Given a coming-soon key, when any write route is called, then it is refused and the database is byte-for-byte unchanged.
- Given a malformed connect on a live key, then nothing is stored — not even the connection row.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-018
epic: EP-INT-05
module: integrations
screens: [S8, S142]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-013, US-INT-001]
journeys: [J59]
rules: [BR-INT-028, BR-INT-037]
golden_tests: []
finance_calc: none
---
### US-INT-018 — Operations, not providers, are the unit: one card, one credential, several things it does

**1 · Details** — As **a system administrator connecting a provider that both answers questions and sends us payments**, I want **one card, one credential and one onboarding — with each thing it does listed separately** — so that **a single partner does not appear on my screen as two**.

`C1`, the correction that did not survive contact: *"a provider is not a shape. It is a set of operations, each with its own."* The kiosk card lists **Account lookup · Payments · Returns**, each with its own state and last-run time — **not three cards, and not one word averaging them**. Neptune 360 lists sixteen. `GET /integrations` serves `operations[]` per connection; S8 draws them as rows under the card; S142 groups runs by operation. Two exhaustive axes replace the old four verbs — **which way does the data move, and who starts it** — so the runner is chosen from `direction × initiative` and there is no fifth cell to be surprised by.

Entry: a manifest with more than one operation. Exit: the card and the detail show each operation's own state.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-028` | A provider is a set of operations; one partner is one card, one credential, one onboarding | PROPOSED — design §2.13, §2.14.1, `C1` |
| `BR-INT-037` | P1 — the card renders from the registry; adding an operation adds no React | CONFIRMED |
| B14 rule 32 | One sentence per card; no rule id or internal code | CONFIRMED — PO 2026-09-02 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | `payments_kiosk` connected; Alex opens S8 | **One** card; under it three rows — *Account lookup*, *Payments*, *Returns* — each with its own state word and *last run* time; **one** credential row (doc TC-INT-27) |
| TC-2 | *Returns* last failed; *Payments* working | The two rows read differently; the card shows **no aggregate word** — a provider with more than one operation carries no headline state |
| TC-3 · **negative** | A manifest with `operations = ()` | Refused at load naming the provider |
| TC-4 | `GET /integrations` | Each connection carries `operations[]` with `{name, direction, initiative, state, last_run_at, last_outcome}`; a single-operation provider carries one entry and its card shows that state as the card state |
| TC-5 | S142 for the kiosk | Runs grouped by operation, three groups; each group header says which way in words — *They send us payments* · *They ask us about an account* · *They send us a return* — never a quadrant name like `DELIVER` or `SERVE` |
| TC-6 · **tenant isolation** | Lone Star Ridge has no kiosk connection | Its card shows three operation rows all *Not set up*; no last-run time from Brazos Bend |

**4 · Test Data** — `payments_kiosk` manifest: `Account lookup` (`in · them` — they call us, we answer; respond_after `authenticate`), `Payments` (`in · them`; respond_after `dedupe`, status map `{ok: 200, duplicate: 409}`), `Returns` (`in · them`; same, reversal marker in the key). Runs: lookup 02:41 today succeeded 12 · payments 06:15 succeeded 41 · returns 06:15 **failed** *the return named a payment we do not hold*. One credential (`••••K1OS`).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `operations[].name` · `.direction` · `.initiative` | S8 card rows · S142 group headers | design §2.13.1 Figure 27 | manifest; `integration_run.operation` | text/enum | reference-data | `direction ∈ {out, in}` × `initiative ∈ {us, them}` |
| per-operation state · last run | S8 · S142 | `C1` | computed from the latest `integration_run` per `(connection_id, operation)` | enum/ts | computed-display | in words: *Working · Not working · Not tested yet · Not set up* |

**6 · Acceptance**
- Given a kiosk connection, when the grid renders, then one card lists three operations with three states, and the database holds one credential.
- Given one operation fails, then only its row changes.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-019
epic: EP-INT-05
module: integrations
screens: [S141, S147]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-002, US-INT-013, US-INT-014]
journeys: [J48, J49, J50]
rules: [BR-INT-002, BR-INT-019, BR-INT-026, BR-INT-043]
golden_tests: []
finance_calc: none
---
### US-INT-019 — The connect/manage modal (S141): one frame written once, a field slot rendered from the manifest, and the three field kinds a plain field cannot express

⚠ **`S147` ADDED TO `screens:` 2026-10-02 (`DEF-INT-8539`).** `BR-INT-002`'s *Connect* half was superseded on 2026-09-16 (`DEF-INT-5513`): a card's **Connect** now opens the connector set-up SCREEN `S147`, and the screen inventory's `S147` addendum names this epic as its owner (`CR-110-BRC04` wave A, `EP-INT-05`). It is this story's frame given an address — one form rendered from the manifest — so the story claims it rather than leaving it unowned (hard-won law 8). **The modal prose below describes the frame before `S147`; the blueprint's `CFG-` frames own its layout.**

**1 · Details** — As **a system administrator**, I want **one modal for every provider — how to sign in, environment, the fields the manifest declares, how often, Save and test — with the four states and Disconnect** — so that **nine providers never become nine screens, and connecting the kiosk asks me for a key and nothing about bearer tokens**.

**The frame is identical and written once** (Figure 26): *Connect · <display_name>* · **How to sign in** from the manifest (OAuth · Password · SFTP key) · **Environment** (Production · Sandbox, shown in words on the card afterwards) · **the field slot** — the only part that varies, rendered from `manifest.fields` · **How often** (Nightly · Hourly · Manual) · **Save and test** · *Testing sends one real message to an address you type.* The **Manage** view of the same modal shows the `describe()` line, *connected by Alex Reed, 12 Aug*, the state, the dated expiry warning (*Needs re-authorising by 12 September. After that, bills stop going out.*), the last runs, and three buttons — **Test it now · Replace password · Disconnect** (danger tier, B14 rule 6).

**What fills the slot is different every time, and three kinds are not fields at all** (`T27` — declared in phase 1 so one modal stays one modal): `redirect` — OAuth has no credential field; the body is a button and a return trip · `mapping_editor` — CSV headers are unknown until a file is seen, so the mapping is a **second step**, not a field · `issued_secret` — a key WE give a partner, shown **once**, copyable, never re-displayed; the opposite of every other card. Auth **placement** is declared per operation (`header · bearer · query · redirect`), so the kiosk asks for a key and the GL partner for a client id, and **no code branched to make that true**.

**UI law this surface obeys:** rule 21 — `features/integrations/` is added to `route-b-migrated.txt` in its first commit or every utility renders as nothing · rule 31 — the trace id is the only identifier on the screen and it is a support reference, not a row id · rule 32 — one sentence per card, no `BR-INT-003` anywhere a clerk reads · rule 33 — refusals in five or six words · rule 5 — two button sizes · rule 6 — Disconnect is danger-tier.

Entry: **Connect** or **Manage** on an S8 card. Exit: `POST /integrations/{key}/connect` (`US-INT-002`'s four ratified endpoints), then `US-INT-015`'s `test()`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-002` | Every card opens the connect modal — method, environment, cadence, test, manage, disconnect | CONFIRMED — A1 + A11 addenda |
| `BR-INT-043` | Auth placement and mode declared per operation; closed vocabulary of field kinds incl. redirect, mapping editor, issued secret | PROPOSED — design §2.3.4, `C2`, `T27` |
| `BR-INT-026` | Environment shown in words; sandbox never handed a real batch | PROPOSED |
| `BR-INT-019` | Testing sends one real message to a typed address | PROPOSED |
| B14 rules 5 · 6 · 21 · 31 · 32 · 33 | Two button sizes · danger tier · Tailwind-only via the migrated list · no DB id · one sentence · six-word refusals | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Open **Connect · Custom SMTP** | Five typed fields — Mail server · Port · Username · Password · Send bills from — plus Environment and How often; footer *Testing sends one real message to an address you type.* |
| TC-2 | Open **Connect · Microsoft 365** | **One** field (Send bills from) and a **Sign in with Microsoft** button; no password field exists in the DOM |
| TC-3 | Open **Connect · Payment kiosk** | A **Key** field and the allowlist; **no** bearer/token field. Open **Connect · Third-party GL**: a *Key for them to use* the product **issues** — shown once with Copy; reopening shows `••••7Q2F` only |
| TC-4 | Open **Connect · Bank & lockbox file**, choose CSV | Bank label · File format · Source; the **column mapping is a second step** offered after a file is seen — not a field on this modal |
| TC-5 · **negative** | A manifest declares `kind = "wizard"` | Refused at load (`BR-INT-043`); the modal renderer has no fallback branch |
| TC-6 | Save a `sandbox` SMTP connection | Card reads **Sandbox** in words beside the state; `POST /integrations/email_smtp/run` with a real batch is refused *Sandbox connection — test only* (doc TC-INT-23) |
| TC-7 · **UI law** | `features/integrations/**` | Every file listed in `07-frontend/src/styles/route-b-migrated.txt` (g31); Disconnect renders `data-variant="danger"`; no `BR-` string in any rendered copy; every refusal ≤ 6 words |
| TC-8 · **tenant isolation** | Lone Star Ridge opens Manage on its own SMTP card | Its `describe()` line, its connected-by; Brazos Bend's runs absent |

**4 · Test Data** — Brazos Bend: `email_smtp` production (`smtp.brazosbend.example`, 587, `billing@brazosbend.example`, Nightly) connected by Alex Reed 12 Aug; `email_microsoft` with `expires_at = 12 Sep` (eleven days out — the warning sentence); `payments_kiosk` allowlist `198.51.100.0/24, 203.0.113.7`; `gl_partner` issued key hint `••••7Q2F`. Locale: the eleven catalogues carry `integrations.modal.testing_sends_one` and the state words.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| How to sign in | S141 | design Figure 25–26 · `BR-INT-043` | manifest `auth.mode` (not stored per tenant) | enum | reference-data | rendered, not chosen, when the manifest declares one mode |
| Environment | S141 · S8 card (words) | `BR-INT-026` | `integration_connection.environment` | enum | user-input | `production \| sandbox`; part of the UNIQUE triple |
| Field slot values (non-secret kinds) | S141 | `manifest.fields` | `integration_connection.config` jsonb | per kind | user-input | validated by `adapter.validate()` before anything is stored |
| Field slot values (`secret`, `issued_secret`) | S141 | `manifest.fields` | `integration_credential.payload_enc` (+ `masked_hint`) | encrypted | user-input / system-issued | never echoed; hint only |
| How often | S141 | `BR-INT-024` | `integration_connection.cadence` · `next_run_at` | enum/ts | user-input | `nightly \| hourly \| manual`; manual → NULL |
| Test recipient | S141 | `BR-INT-026` | not stored | email | user-input | typed, never a customer list |
| Manage: describe line · state · expiry sentence · last runs | S141 Manage · S142 | Figure 25 | computed | text | computed-display | date in words; no row id |

**6 · Acceptance**
- Given any two providers, when their modals open, then the frame is the same component and only the field slot differs, and neither modal has a field the other needs.
- Given an OAuth provider, then the body is a button and a return trip and no credential field exists.
- Given the issued key, then it is shown once and never again.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1479` | May a clerk press **Test it now** without being able to change a credential? Settings is System Admin only today, so this reverses a signed permission rule | Only the permission on the Test button; the modal ships Admin-only meanwhile | PO | OPEN |
