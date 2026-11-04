# EP-INT-07 — Credentials have a lifecycle, not a moment

**Module:** integrations · **Wave:** phase 2 (`US-INT-024`, `025`, `026`) · phase 3 (`US-INT-027`, `028`) · **Screens:** S141 · S142 · S7 dashboard (the dated warning) · S8 Notifications (the sender card that folds in) · **Status:** draft (`CR-069`, 2026-09-03)

## Scope

**In:** P6 made concrete — versioned credentials with rotation and one-row rollback (`BR-INT-025`), disconnect that destroys the secret at once and keeps the runs (`BR-INT-016`, `BR-INT-042`), the fold of `notifications/sender_config.py`'s *name of a password* into a real encrypted credential (`C35`), the nightly expiry sweep that warns **eleven days ahead with the date in words**, and token exchange with a declared fetch plan so a ten-minute token survives a two-hour walk without writing 144 credential rows a day (`C11`, `C12`).

**Out:** machine credentials we ISSUE to a partner (`US-INT-040`, `EP-INT-11`) and the customer's consent (`US-INT-046`) — both are permissions, not our credentials.

⚠ **BEFORE THE FIRST REAL CREDENTIAL IS STORED (phase 2), TWO THINGS ARE OWED:** the deletion path (`US-INT-025` — *"write the deletion path before the first real credential is stored, not after"*), and the **human sign-off on `core/crypto.py`'s four self-made judgments** — where the key comes from, what happens when it is absent, how rotation works — recorded as awaiting review. Every credential in this design sits on top of them. This is a row in `12-governance/09-human-review-ledger.md`, not a question a lane may answer.

**Exit test of phase 2:** a wrong password produces *the mail server rejected the password* on screen, and the credential is **provably absent from the database, the logs and the audit trail** — three assertions, not one (Figure 14's three exits). **Exit test of phase 3:** an expiring token raises a **dated** warning before it lapses, and re-authorising **keeps the connection's entire run history**.

## Capability matrix (list screens only — B9 conformance)

No new list screen. Credential versions are shown on S142 as a short history under **Replace password**; the run list is `EP-INT-06`'s.

## Stories

---
id: US-INT-024
epic: EP-INT-07
module: integrations
screens: [S141, S142]
wave: 2
status: ready
blocked_by: []
depends_on: [US-INT-014, US-INT-019]
journeys: [J49]
rules: [BR-INT-003, BR-INT-025, BR-INT-014]
golden_tests: []
finance_calc: none
---
### US-INT-024 — Credential versioning, rotation and rollback: the wrong key pasted at 5 pm on a Friday is a one-row undo

**1 · Details** — As **a system administrator who pasted the wrong key**, I want **the previous credential still there** — so that **I can undo it without re-authorising from scratch**.

Rotation (**Replace password** on S141/S142 → `POST /integrations/{key}/credential`) writes version n+1 and deactivates n; **exactly one active per connection is enforced by the database** (`EXCLUDE … WHERE is_active`), not by application code. Rollback (`POST /integrations/{key}/credential/rollback`) re-activates the previous version — one row, no re-authorisation — refused when there is no previous version or it has expired. Every version keeps its `masked_hint` (`••••3F9A` → `••••A17C`), which is display only and never the secret; the audit trail gets a real before-and-after **without ever holding a plaintext value**. The connection row does not change — it holds no secret to change.

Entry: **Replace password** / **Roll back**. Exit: a new credential row; `test()` re-run; a run row; an audit row with masked hints.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-025` | Versioned, never updated; one active enforced by the database; rollback is one row | PROPOSED — design §1.4, §2.8 |
| `BR-INT-003` | Never rendered back, logged or audited — masked hints only | CONFIRMED |
| `BR-INT-014` | Rotation is a lifecycle event → `audit_log` with masked refs | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | v1 active; Alex replaces the password | v2 active, v1 retained inactive; `test()` runs on v2; audit row `integration.credential_rotated` with `••••3F9A → ••••A17C` and nothing else (doc TC-INT-06) |
| TC-2 | v2 fails its test (wrong key); Alex presses **Roll back** | v1 active again, v2 inactive and retained; sending resumes **without re-authorising**; audit row `integration.credential_rolled_back` |
| TC-3 · **PG** | Two rows with `is_active = true` for one connection | The database refuses the second (doc TC-INT-07) |
| TC-4 · **negative** | Roll back on a connection with one version | Refused *Nothing to roll back to* (≤ 6 words) |
| TC-5 · **negative** | Roll back to a version whose `expires_at` has passed | Refused *Previous credential has expired*; re-authorisation is the only path |
| TC-6 · **three exits** | After TC-1, search the database dump, captured logs and `audit_log` for the plaintext of both passwords | **Zero hits in all three** (Figure 14) |
| TC-7 · **tenant isolation** | Lone Star Ridge posts a rotation against Brazos Bend's connection id | 404 identical to absent; no row written |

**4 · Test Data** — Brazos Bend `email_smtp`: v1 `Ew3!kQ9-lockbox` (hint **`••••kbox`**), v2 `wrong-key-friday` (hint **`••••iday`**); an expired v0 fixture for TC-5. Actor Alex Reed, 5 pm Friday 28 Aug.

⚠ **THE HINTS WERE `••••3F9A` / `••••A17C` UNTIL 2026-09-04 AND THE CODE IS RIGHT, NOT THE DOCUMENT (CR-069 wave E build lane).** A hint is DERIVED — the mask plus the **last four characters of the secret** (`services._hint`; `services._masked` refuses anything longer, precisely so the payload cannot ride out through the one column a screen reads). `••••3F9A` is an API key's last four from another figure in the design and cannot be the hint of a password ending `lockbox`. **The plaintexts win because they are load-bearing** — TC-6 greps the database, the logs and the audit trail for exactly these two strings — so the hints follow from them. Wave B's shipped tests already asserted `••••kbox`, which is what settled it. Reasoning in the decision log for 2026-09-04.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `version` · `is_active` | S142 history | `BR-INT-025` | `integration_credential` | int/bool | system-derived | UNIQUE `(connection_id, version)`; EXCLUDE one active |
| `payload_enc` | — | `core/crypto.py` | `integration_credential.payload_enc` | `EncryptedTextField` | user-input | never selected into an API response |
| `masked_hint` | S141 · S142 · audit | Figure 3 | `integration_credential.masked_hint` | text | system-derived | last four of the secret, bulleted |
| `rotated_at` | S142 | §2.8 | `integration_credential.rotated_at` | ts | system-derived | set on the deactivated row |

**6 · Acceptance**
- Given a bad key replaces a good one, when the admin rolls back, then the good one is active again in one row and nobody re-authorises.
- Given any rotation, then the plaintext is in no table, no log and no audit row.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-025
epic: EP-INT-07
module: integrations
screens: [S141, S142]
wave: 2
status: ready
blocked_by: []
depends_on: [US-INT-003, US-INT-014, US-INT-024]
journeys: [J48]
rules: [BR-INT-016, BR-INT-042, BR-INT-014]
golden_tests: []
finance_calc: none
---
### US-INT-025 — Offboarding: disconnect destroys the credential immediately and keeps the run history

**1 · Details** — As **a compliance owner**, I want **disconnect to destroy the credential immediately while keeping the run history** — so that **a departed tenant's secret is not sitting in yesterday's backup with nobody holding a checklist**.

`US-INT-003` owns the IS-6 confirm and the consequence copy; this story is what the database does. `DELETE /integrations/{key}` destroys **every credential version** (rows deleted — a secret has a different retention from a record), sets the connection `off`, **keeps every run row**, and audits it with masked hints. Queued work is not lost (`BR-INT-016`): queue rows rest `queued`, and there is no shared-sender fallback. Reconnection requires fresh credentials. **The deletion path is written before the first real credential is stored, not after** — the design's own ordering.

Entry: **Disconnect** (danger tier) → IS-6 confirm. Exit: no credential rows; `status = off`; runs intact; audit row.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-016` | Disconnect destroys the secret; nothing queued or recorded is lost; reconnection needs fresh credentials | CONFIRMED — IS-6 + B7 addendum |
| `BR-INT-042` | P6 — a secret and a record have different retention | PROPOSED |
| `BR-INT-014` | Audited with masked refs | CONFIRMED |
| B14 rule 6 | Disconnect is a danger-tier commit | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Connection with 2 credential versions and 20 runs; Alex disconnects | `integration_credential` rows for it: **0**; `integration_run` rows: **20**, unchanged; `status = off`; audit row with `••••3F9A, ••••A17C destroyed` (doc TC-INT-10) |
| TC-2 | Queue rows `queued` for that mailbox at disconnect | They stay `queued` with the config-missing marker; **no shared-sender fallback** sends them |
| TC-3 · **negative** | Reconnect with **Roll back** | Refused — no version exists; only **Connect** with fresh credentials |
| TC-4 · **backup** | A database dump taken after TC-1 | Contains no ciphertext row for the connection; the run history is in it |
| TC-5 · **tenant isolation** | Lone Star Ridge calls `DELETE` on Brazos Bend's key by id | 404; Brazos Bend's credential untouched |
| TC-6 · **ordering gate** | Migration/test history | The disconnect test lands in the same PR as, or before, the first adapter that stores a credential (`US-INT-024`'s `POST …/credential` cannot merge without it) |

**4 · Test Data** — Brazos Bend `email_smtp` with v1 + v2 and the twenty runs of `US-INT-020`; 12 queued bill emails at the moment of disconnect.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `status = off` | S8 card (*Turned off*) · S142 | Figure 4 | `integration_connection.status` | enum | system-derived | reconnect → `untested` after a fresh connect |
| credential rows | — | `BR-INT-016` | `integration_credential` — DELETED | — | system-derived | zero rows after disconnect |
| runs | S142 | `BR-INT-042` | `integration_run` — retained | — | — | append-only, untouched |

**6 · Acceptance**
- Given a connected mailbox, when it is disconnected, then the secret is gone from every version and the run history is intact and readable.
- Given queued bills at disconnect, then nothing sends them through anything else.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-026
epic: EP-INT-07
module: integrations
screens: [S8, S141]
wave: 2
status: ready
blocked_by: []
depends_on: [US-INT-005, US-INT-014, US-INT-024, US-NOT-003]
journeys: [J48]
rules: [BR-INT-005, BR-INT-007, BR-INT-008, BR-INT-042]
golden_tests: []
finance_calc: none
---
### US-INT-026 — Fold the email sender card into the connection model: a mail password typed into the product, not the name of an environment variable (C35)

**1 · Details** — As **a system administrator**, I want **to type my mail password into the product rather than name an environment variable my hosting provider set** — so that **connecting email does not require a deployment**.

`notifications/sender_config.py` still reads *"`smtp_secret_ref` holds the NAME of a secret in the deployment's own store"*, on the stated grounds that no encryption existed. **Encryption has existed since 24 August** (`core/crypto.py`). This story absorbs that card into the connection model rather than building alongside it: the sender card on S8 Notifications becomes a read of the `email_*` connection (`US-INT-004`'s read-model), the host/port/from move into `integration_connection.config`, the password into `integration_credential` v1, and a **data migration** converts every existing `smtp_secret_ref` holder — reading the named secret **once, at migration time, in the deployment that holds it** — into a real encrypted credential. `smtp_secret_ref` stops naming an environment variable. **`US-INT-005` is re-scoped against this story** (the design's own instruction): it builds no second sender card.

Entry: the migration; then **Connect · Custom SMTP**. Exit: the dispatcher (`BR-NOT-005`, the only sender) reads the connection through the seam; S8 Notifications shows provider status from the read-model.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-005` | BYO mailbox; the tenant connects its OWN mailbox | CONFIRMED — B7 + A15 addenda. ⚠ Flagged with its 60,000 figure → `OQ-INT-1488`; not amended |
| `BR-INT-007` | Connection may be made from day one; SENDING activates W6 | CONFIRMED — OQ-073 |
| `BR-INT-008` | Integrations sends nothing; the dispatcher stays the only sender. ⚠ *AMENDED 2026-10-02 (PO, "B · Keep it and change the rule, because it only passes the job on."): the export door may hand an export job to the runner, carrying no figure and no file; sending is unchanged — see `02-business-rules.md` BR-INT-008.* | CONFIRMED |
| `BR-INT-042` | P6 — a real credential with a lifecycle replaces a name in a store | PROPOSED — design §1.13 correction, `C35` |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **migration** | A tenant with `smtp_secret_ref = "SMTP_PASSWORD_BRAZOS"` set in the environment | After the data migration: an `email_smtp` connection `working`-pending (`untested`), credential v1 encrypted, `smtp_secret_ref` NULL; the S8 Notifications card reads the connection |
| TC-2 · **migration · negative** | A tenant whose named secret is **absent** from the environment at migration time | The connection is created `not_set_up` with the sentence *Mail password needs entering* — **no guessed value, no empty credential row** |
| TC-3 | Alex types the password on S141 and presses Save and test | One real message to the typed recipient; card *Working*; **no deployment happened** |
| TC-4 · **negative** | `grep -rn "smtp_secret_ref" 06-backend/apps` after this story | Only the migration and a `# retired` comment; `sender_config.py` no longer reads it |
| TC-5 | The dispatcher sends a batch | It resolves the credential **inside the seam at use time** (`US-INT-004`); it never receives the plaintext in its own process outside the adapter call |
| TC-6 · **tenant isolation** | Two tenants both had `smtp_secret_ref` | Two connections, two credentials, each under its own tenant |

**4 · Test Data** — Brazos Bend `smtp_secret_ref = SMTP_PASSWORD_BRAZOS` (present); Silver Creek `smtp_secret_ref = SMTP_PASSWORD_SILVER` (absent at migration — TC-2). Host `smtp.brazosbend.example`, port 587, from `billing@brazosbend.example`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `smtp_host` · `smtp_port` · `send_from` | S141 · S8 Notifications (read) | `sender_config.py` today → `C35` | `integration_connection.config` | text/int/email | user-input (migrated) | port 1–65535; `send_from` required |
| mail password | S141 | `C35` | `integration_credential.payload_enc` v1 | encrypted | user-input (migrated once) | never `smtp_secret_ref` again |
| `smtp_secret_ref` | — | retired | `sender_config` column NULLed by migration | — | — | no reader after this story |

**6 · Acceptance**
- Given a deployment holding a named mail secret, when the migration runs, then it becomes an encrypted credential and the environment variable is never read again.
- Given a new tenant, then connecting email is a form and a test, not a deployment.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1488` | At 60,000 bills a cycle a mailbox capped at about 2,000 a day needs thirty days for one month's billing; should the bulk-email connector be **mandatory above a threshold**, said on the card in words, and what is the threshold? | Only the card copy and the threshold; the fold itself ships | PO | OPEN |

---
id: US-INT-027
epic: EP-INT-07
module: integrations
screens: [S142, S7]
wave: 3
status: ready
blocked_by: []
depends_on: [US-INT-014, US-INT-029]
journeys: [J50]
rules: [BR-INT-042, BR-INT-015]
golden_tests: []
finance_calc: none
---
### US-INT-027 — The expiry warning sweep: told eleven days before a token lapses, in words, with the date

**1 · Details** — As **a utility manager**, I want **to be told days before an OAuth token lapses — on the dashboard and by email** — so that **bills do not stop on a Tuesday and get noticed on the Friday**.

`expires_at` earns its column here: it is *"the difference between 'email stopped working last Tuesday and nobody knew' and a message on the dashboard eleven days beforehand."* The nightly `integration.sweep_expiry` (the second entry in the product's first beat schedule, `US-INT-029`) finds active credentials expiring within the manifest's warning window (default 14 days), writes a dated warning — ***Needs re-authorising by 12 September. After that, bills stop going out.*** — on S142, on the S7 dashboard attention strip, and by email to the System Admins through the notifications queue (never a direct send, `BR-INT-008`), once per day, never twice for the same day. **Re-authorising keeps the connection's entire run history** (phase 3's exit test): the OAuth return trip writes credential v(n+1) on the same connection row.

Entry: the beat tick. Exit: a dated sentence in three places; a run row for the sweep.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-042` | P6 — `expires_at` + a sweep that warns days ahead with the date in words | PROPOSED — design §1.4 red pen |
| `BR-INT-015` | Failures surface, never silently; provider health feeds the S8 panel | CONFIRMED |
| `BR-INT-008` | The warning email goes through the notifications queue, not a direct send. ⚠ *AMENDED 2026-10-02 (PO, "B · Keep it and change the rule, because it only passes the job on."): the export door may hand an export job to the runner, carrying no figure and no file; sending is unchanged — see `02-business-rules.md` BR-INT-008.* | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Silver Creek `email_microsoft` credential `expires_at = today + 11 days`; the sweep runs | S142 and S7 read **Needs re-authorising by 12 September. After that, bills stop going out.** — the date **in words**, and one queued email to the admins (doc TC-INT-24) |
| TC-2 | The sweep runs again the next night | One more warning (day 10), not two; the day-11 row is not repeated |
| TC-3 | Alex re-authorises via the OAuth return trip | Credential v2 on the **same** connection; S142 still lists every earlier run; the warning clears |
| TC-4 · **negative** | The token lapses un-renewed | Card *Not working · Microsoft needs re-authorising*; the next send run is skipped and recorded; bills rest `queued` |
| TC-5 · **negative** | A credential with `expires_at = NULL` (SMTP password) | Never warned; the sweep ignores it |
| TC-6 · **tenant isolation** | Two tenants each with an expiring credential | Each tenant's admins receive only their own warning |

**4 · Test Data** — Silver Creek Water `email_microsoft`, `expires_at = 2026-09-12` on sweep date 2026-09-01 (eleven days). Brazos Bend `email_smtp` no expiry. Warning window 14 days.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `expires_at` | S142 | design §1.4 | `integration_credential.expires_at` | ts | integration (OAuth response) | NULL for non-expiring kinds |
| warning sentence | S142 · S7 · email | Figure 25 | computed; queued notification row | text | computed-display | date in words; ≤ 2 sentences (B14 rule 32) |
| sweep run | S142 | `US-INT-029` | `integration_run` `trigger = scheduled`, `operation = expiry_sweep` | row | system-derived | one per night |

**6 · Acceptance**
- Given a credential eleven days from expiry, when the night's sweep runs, then the warning names the date in words in three places.
- Given re-authorisation, then the run history is unbroken.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-028
epic: EP-INT-07
module: integrations
screens: [S142]
wave: 4
status: ready
blocked_by: []
depends_on: [US-INT-024, US-INT-029]
journeys: [J55]
rules: [BR-INT-047, BR-INT-025]
golden_tests: []
finance_calc: none
---
### US-INT-028 — Token exchange and the fetch plan: a ten-minute token across a two-hour walk, and not one credential row for it (C11, C12)

**1 · Details** — As **an engineer**, I want **the long-lived secrets stored and the short-lived token minted in memory, re-minted mid-walk and never written to the credential table** — so that **a two-hour collection completes across a ten-minute token and the credential table still shows one version, not 144 a day**.

Failure 12 (a token that expires mid-run) and decision 6 (the window, which is theirs and not ours): the meter head-end issues a bearer token valid for ten minutes against a walk through two years of history in seven-day windows, paging at 100, 150 or 5,000 records depending on which service is asked. **`token_exchange` is an auth mode**: the stored credential is the long-lived pair; the runtime exchanges it for a token, caches it in memory for the call, re-mints when it ages out, and writes nothing. **A fetch plan is declared per operation** — `window = 7 days`, `page_size = {readings: 5000, meters: 150, routes: 100}` — and the FetchRunner walks time in the provider's chunks and pages within each chunk; a two-year backfill is about **105** windows, checkpointed by the job framework so a failure resumes at the window it reached. None of those numbers is in code.

Entry: a scheduled or manual collection. Exit: one run row with five counts; one credential version.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-047` | Token exchange never writes the credential table; window and page size are declared data | PROPOSED — design §1.7 failure 12, §1.9.2, §2.18.4 |
| `BR-INT-025` | Versions are written only by rotation | PROPOSED |
| `BR-INT-034` | The budget is spent by the walk; the sweep declines to start what it cannot finish | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Token fixture valid 10 min; a walk of 105 windows taking two hours | The token is re-minted **≥ 11** times mid-walk; `integration_credential` row count for the connection is **1** before and after (doc TC-INT-37) |
| TC-2 | Page sizes declared `5000 / 150 / 100` for three services | The runner requests exactly those; changing one in the manifest changes the request with no code change |
| TC-3 | The walk fails at window 61 | Resumes at window 61 from the job checkpoint; windows 1–60 are not re-fetched |
| TC-4 · **negative** | A manifest declares `window = 30 days` for a provider whose cap is 7 | The provider refuses; the run records the refusal **naming the parameter**; no silent narrowing |
| TC-5 · **secret handling** | Capture logs during TC-1 | Neither the long-lived pair nor any short-lived token appears |
| TC-6 · **tenant isolation** | Two tenants collecting from the same head-end vendor | Two token caches; neither can present the other's token |

**4 · Test Data** — `meters_neptune360` on Brazos Bend: long-lived pair (`••••N360`), token TTL 600 s, fetch plan `window 7d`, pages `readings 5000 · meters 150 · routes 100`; two-year backfill from 2024-09-01 → 105 windows; a fault injected at window 61.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `auth.mode = token_exchange` | — | `C11` | manifest | enum | reference-data | token cached in memory only |
| `fetch_plan.window` · `.page_size` | S142 run detail (*window 61 of 105*) | `C12` | manifest per operation | duration/int | reference-data | provider's caps |
| checkpoint | S142 progress | `core/jobs.py` `record_progress` | `jobs` | int | system-derived | resume at the reached window |

**6 · Acceptance**
- Given a ten-minute token and a two-hour walk, then the walk completes and the credential table holds one version.
- Given a failure part-way, then the walk resumes where it stopped.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None. (Whether hourly interval data is switched on — about half a billion rows a year — is `OQ-INT-1484` and blocks `US-INT-036`, not this walk of readings.)
