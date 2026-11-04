# J48 — Connect day (seventeen cards all *Not set up*, one real message to `alex@brazosbend.example`, a card that turns *Working* — and a password in no table, no log and no audit row)

---
id: J48
tier: 2
rules: [BR-INT-001, BR-INT-002, BR-INT-003, BR-INT-005, BR-INT-007, BR-INT-008, BR-INT-014, BR-INT-016, BR-INT-018, BR-INT-019, BR-INT-025, BR-INT-026, BR-INT-028, BR-INT-037, BR-INT-038, BR-INT-039, BR-INT-040, BR-INT-041, BR-INT-042, BR-INT-043, BR-INT-053]
stories: [US-INT-013, US-INT-014, US-INT-015, US-INT-016, US-INT-017, US-INT-019, US-INT-020, US-INT-021, US-INT-025, US-INT-026]
# Wiring: every story above cites `J48` in its own `journeys:` frontmatter
# (04-docs/05-modules/13-integrations/06-epics/). Activation authority = the
# GENERATED index (10-scripts/07-e2e-wiring-index.py); NOT ACTIVATED — no
# `07-frontend/e2e/J48.spec.ts`. Written by wave E task E8 (`10-execution-plan.md`),
# demo script `cr069-e-smtp-connect-day.mjs`; the phase-1 exit test (step 2) is
# wave B's. Phase 2 LAUNCH: "a utility connects its own mail server and sends
# real email through it".
# 🔒 `core/crypto.py`'s four self-made judgments (where the key comes from · what
# happens when it is absent · how rotation works · randomised not deterministic)
# are HUMAN-REVIEW-PENDING at 09-human-review-ledger.md:395 — NO REAL CREDENTIAL
# IS STORED BEFORE THAT SIGN-OFF (wave E1). Fixture credentials are fine.
# ⚠ THE DELETION PATH IS WRITTEN BEFORE THE FIRST REAL CREDENTIAL IS STORED
# (US-INT-025, wave E2 first) — step 10 is not an afterthought.
---

**Intent.** Alex types the mail password **into the product** — not the name of an
environment variable his hosting provider set — presses *Save and test*, one **real** message
arrives at an address he typed, the card turns *Working*, and its line reads
*billing@brazosbend.example · Custom SMTP*. Three exits, three assertions: the password is
**provably absent from the database dump, the captured logs and the audit trail**. Around
it, the substrate the connector rides on: seventeen manifests rendered from one registry, a
coming-soon key **refused by the API and not just the button**, a run row with **five counts**
and an outcome vocabulary that includes *unconfirmed*, a job row written **before** the
broker message and **before** the 202, and a dedicated queue **with its own consuming worker**.

**Upstream leaves (handoff in).** Phase 1 done (waves A–D): `apps/integrations/manifests/`
holds **seventeen** manifests in seed order — `email_microsoft` · `email_google` ·
`email_smtp` · `email_bulk` · `bank_lockbox_file` · `accounting_file` · `print_vendor` ·
`payments_kiosk` · `payments_card` (COMING_SOON W7) · `meters_neptune360` · `meters_mdm`
(COMING_SOON v2) · `gis_city` · `map_tiles_public` · `geocoder_census` · `gl_partner` ·
`sms_twilio` (COMING_SOON v1.1) · `sso` (COMING_SOON v2); the five tables under RLS `FORCE`
(`integration_connection` · `integration_credential` · `integration_run` ·
`integration_target_reference` · `integration_consent`) anchored in the B2 brief **before**
`0001`; the `integrations` queue routed in `config/celery_routes.py` **and** `celery-
integrations` in `docker-compose.yml`. **No connection rows.** Brazos Bend's
`notifications.NotificationSettings.smtp_secret_ref = "SMTP_PASSWORD_BRAZOS"` **present** in
the environment; Silver Creek's `SMTP_PASSWORD_SILVER` **absent**. Tenants **Brazos Bend
Utilities** (`seed_demo`), **Silver Creek Water**, **Lone Star Ridge WSC**. Actors **Alex
Reed** (System Admin), **Priya Menon** (Billing Clerk), **J. Okafor** (Lone Star Ridge).

⚠ **THE LIST ABOVE IS THE WORLD OF WAVES A–D AND IT IS NO LONGER THE REPOSITORY'S
(amended 2026-09-16, `CR-110-BRC04` wave C).** It was already one short when it was
written — `payments_sandbox` made eighteen under `CR-068` phase 5 — and it is now ten
short and four keys wrong. **There are TWENTY-EIGHT manifests**, in the Integration
Blueprint's own catalogue order, and **four of the keys named above no longer exist**:
`payments_card` became five named processors, `gl_partner` became five named ERPs,
`meters_mdm` became `meters_itron` and `meters_sensus`, and `gis_city` was renamed
`gis_esri`.

**This journey's own assertions are unaffected** — it exercises the substrate (a
coming-soon key refused by the API, a run row with five counts, a job row written
before the broker message) and not the catalogue, and a coming-soon key still exists
to refuse. **What is amended is the handoff-in sentence a later lane would BUILD
from.** The live list is `06-backend/apps/integrations/manifests/__init__.py` and
`tests/test_cr110_connectors.py` asserts it; **read those, never this paragraph** —
a count written into prose is a count that rots, which is why this note says where
the number lives rather than repeating it a third time.

**This journey leaves (handoff out).** ONE `integration_connection` (Brazos Bend ·
`email_smtp` · `production` · label *Billing mailbox* · `status = working` · cadence
`nightly` · `config = {host, port, send_from}` — **no secret material**); ONE
`integration_credential` **v1** (`payload_enc` AES-256-GCM, `masked_hint = ••••3F9A`,
`expires_at` NULL, `is_active`); run rows: the migration's, one `trigger = manual`
`succeeded` (the test), one `unconfirmed` (step 8's fixture); `audit_log`
`integration.connected` with `••••3F9A` and **no payload field**. Silver Creek's `email_smtp`
row `not_set_up` with *Mail password needs entering*. After step 10 (a **twin**): zero
credential rows, twenty run rows, `status = off`. **J49 starts from the working connection;
J53 from it too.**

**Fixture.** SMTP fixture server (recorded, no network): host `smtp.brazosbend.example`,
port `587`, username `billing@brazosbend.example`, good password `Ew3!kQ9-lockbox`, *Send
bills from* `billing@brazosbend.example`, typed test recipient `alex@brazosbend.example`.
Bad password `hunter2 ` (trailing space — the day-one failure). A valid-looking key
`sk_live_51H…` for the coming-soon refusal. Adapter fixtures *no-count* (200, empty body) and
*bare True*. `JOBS_EAGER=false --reuse-db`. Frames `47.1` (grid), `25.1` (connect modal),
`52.1`/`52.2` (test outcomes), `51.2` (unconfirmed), `55.2` (refusal), `25.2` (detail).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (rows · logs · audit · queue · isolation) | Rule |
|---|---|---|---|---|
| 1 | Alex opens Settings → Integrations (S8, frame `47.1`) | **Seventeen** `ProviderCard`s from the registry, every one reading **Not set up**; kickers carry the direction in three words (*EMAIL · WE SEND* · *BANKING · WE COLLECT* · *ACCOUNTING · THEY READ* · *PAYMENTS · THEY SEND*); the `CategoryFilter` chips are **generated from the categories present**, never typed. The placeholder sentence *arrives with the Integrations feature* is **gone from all eleven catalogues** | No card shows a rule id or a database id. `payments_kiosk` lists **three** operation rows under **one** card; `meters_neptune360` sixteen. A coming-soon card's *Connect* is dashed and takes no press | BR-INT-037 · BR-INT-028 · BR-INT-001 |
| 2 | **negative · the phase-1 exit test** — `POST /integrations/payments_card/connect` with `sk_live_51H…` | **Refused by the API** — `RefusalLine` *this connection is not available yet · nothing was saved* (≤ 6 words, names the wave *Coming soon · W7*, `message_key` in all eleven catalogues). `integration_connection` and `integration_credential` counts **unchanged**; **no log line contains the key**. Same refusal on `/test`, `/run`, `PATCH`, `/credential` | ONE `audit_log` `integration.connect_refused` with the key **name** and **no payload**. `POST /integrations/nope/connect` → 404 identical to any absent resource. `POST /integrations/email_smtp/connect` with `port = "abc"` → `field_errors`, **no connection row and no credential row — not a partial one** | BR-INT-001 · BR-INT-003 · B14 rule 33 |
| 3 | **the fold (`C35`)** — the data migration runs | Brazos Bend: `smtp_secret_ref` read **once, at migration time, in the deployment that holds it** → an `email_smtp` connection `untested` with `config = {host, port, send_from}` and credential **v1 encrypted**; `smtp_secret_ref` **NULLed**. Silver Creek (secret absent): connection `not_set_up` with *Mail password needs entering* — **no guessed value, no empty credential row** | `grep -rn smtp_secret_ref 06-backend/apps` → only the migration and a `# retired` comment; `sender_config.py:50` no longer reads it. The S8 Notifications sender card is now a **read** of the connection. **No deployment happened** to connect email | BR-INT-042 · BR-INT-005 · `US-INT-026` TC-1/2/4 |
| 4 | *Connect* on Custom SMTP → S141 (frame `25.1`) | One frame: *How to sign in* **Password** (fixed by the manifest) · *Environment* **Production** | Sandbox · **the field slot** rendered from `manifest.fields` — *Mail server · Port · Username · Password · Send bills from* · *How often* **Nightly** | Hourly | Manual · footer *Save and test* · *Cancel* · *Testing sends one real message to an address you type.* | Opening *Connect · Microsoft 365* on the same component shows **one** field and *Sign in with Microsoft* — **no password field in the DOM** (frame `49.2`); *Connect · Payment kiosk* asks for a key and **nothing about bearer tokens**. `features/integrations/**` is on `route-b-migrated.txt` (rule 21) or every utility renders as nothing | BR-INT-002 · BR-INT-043 · B14 rule 21 |
| 5 | Alex types the five fields and the good password, *Save and test* | `202` + a poll url. **The `jobs` row exists before the broker message is published and before the reply** — asserted by ordering the two writes in the test double. The adapter call runs **in a different process** from the request, on `celery -Q integrations`. `test()` sends **one real message** to `alex@brazosbend.example` — the smallest real instance, **not a credential parse** | ONE `integration_connection` (`working`), ONE `integration_credential` v1 (`••••3F9A`), ONE run row `trigger = manual · 1/1/0/0/0 · succeeded`, summary *Sent one test message to alex@brazosbend.example*. Card → **Working**, line ***billing@brazosbend.example · Custom SMTP*** (`describe()`). Test outcome card `52.1`: *It works · Passed · A real message to a typed address. Not a credential check.* | BR-INT-019 · BR-INT-041 · BR-INT-038 |
| 6 | **the three exits** — dump the database, capture the logs, read `audit_log` | `Ew3!kQ9-lockbox` appears in **none of the three** — zero hits. `describe()` contains no secret; the audit row `integration.connected` carries `••••3F9A` and nothing else; **`integration_connection` holds no encrypted column** (a gate asserts no column named `secret|token|password|payload` and no `EncryptedTextField` on it — first shown RED by adding `api_key_enc`) | Audit is a consumer of the **connection** table, never of the credential table — the connection row is safe to `SELECT *`, log and put in a payload | BR-INT-003 · BR-INT-014 · `US-INT-014` TC-3 |
| 7 | **negative · the failing test** — a twin connect with `hunter2 ` (trailing space) | `TestOutcomeCard` `52.2`: ***The mail server rejected the password** · Failed · Check the username and password, then try again.* · `ProviderSaid` *THE SERVER SAID: 535 5.7.8 AUTHENTICATION FAILED* — our sentence first, their words underneath. Run row `failed` with that sentence and trace id `a7f3c9e1`; card **Not working** | `provider_error` is **scrubbed** by the adapter and rendered **only on S142 to the owning tenant** — never in a list payload, an audit row or a notification. Support finds the run from **eight characters** in one query | BR-INT-019 · BR-INT-039 · `US-INT-020` TC-2/6 |
| 8 | **negative · the run nobody designs for** — the *no-count* fixture on a 93-message batch; then the *bare True* adapter | Outcome **`unconfirmed`**, summary *93 sent, provider did not say*; frame `51.2` — **dashes, not zeroes** in the sent/refused/skipped tiles; the S8 panel shows attention, **never green**. The bare-`True` adapter is refused as success by the **runtime** and fails the conformance kit | **Red-first (law 7):** a stub runtime writing `succeeded` unconditionally turns TC-1 green — recorded as the proof the guard can go red. `succeeded` **only** when `attempted = succeeded + failed + skipped` **and** the far end confirmed a count; `partial` when some failed and the counts reconcile; a double-counted item (`93` succeeded of `92` attempted) → `unconfirmed` | BR-INT-018 · BR-INT-040 |
| 9 | S142 (frame `25.2` shape) — the connection detail | `DetailHead` *billing@brazosbend.example · Working · Production · connected by Alex Reed, 3 Sep*. `RunsTable` WHEN · WHAT RAN · RESULT · SUPPORT REF, newest first; the test run, the migration run. Buttons *Test it now · Replace password · Disconnect* (danger tier) | Every `summary` and every rendered string matches neither `BR-[A-Z]+-\d+` nor a UUID; the trace id is the **only** identifier and is labelled *Support reference* (rules 31, 32). A finished run cannot be `UPDATE`d — refused by trigger on PostgreSQL; corrections are new rows | BR-INT-039 · B14 rules 31 · 32 · hard rule 4's shape |
| 10 | **the deletion path (a twin with 2 credential versions, 20 runs, 12 queued bill emails)** — *Disconnect* → `ConfirmDialog` (destructive: the question · red *what happens straight away* · blue *what is kept* · **type the name**) → confirm | `integration_credential` rows for it: **0** (a secret's retention differs from a record's); `integration_run` rows: **20, unchanged**; `status = off`; card **Turned off**; audit `integration.disconnected` with `••••3F9A, ••••A17C destroyed`. The 12 queue rows **rest `queued`** with the config-missing marker — **no shared-sender fallback sends them** | A database dump after disconnect holds no ciphertext row for the connection and holds the run history. *Roll back* is **refused** — no version exists; only *Connect* with fresh credentials. **Ordering gate:** the disconnect test lands in the same PR as, or before, the first adapter that stores a credential | BR-INT-016 · BR-INT-042 · `US-INT-025` TC-1…4/6 |
| 11 | **tenant isolation** | J. Okafor (Lone Star Ridge) calls `GET /integrations`: the **same seventeen** manifests, every one **Not set up** — Brazos Bend's row is not in the payload. `GET /integrations/email_smtp/runs/<Brazos Bend run id>` → **404 byte-identical to a genuinely absent row**. `DELETE /integrations/email_smtp` by Brazos Bend's id from Lone Star Ridge → 404, credential untouched. With **no `app.tenant_id`** set, `SELECT count(*)` on each of the five tables → **zero rows on all five** (PostgreSQL) | Two tenants enqueue `integration.test` for the same key → two scope keys (`tenant_id` is part of it); neither dedupes the other. Silver Creek's migrated row is under Silver Creek | hard rule 1 · `US-INT-014` TC-2/6 · `US-INT-016` TC-6 |
| 12 | **INVARIANCE** | The plaintext existed at exactly one point — in memory, inside `test()`, for the length of one call. Integrations **sent nothing itself**: the dispatcher stays the only sender and **there is no `POST /integrations/{key}/send`** — a gate asserts no route matches `/integrations/*/send` (RED first by mounting one). Customer email **sending** stays the W6 flip: connection ≠ activation. Adding an eighteenth manifest touches no screen, no endpoint and no migration — a gate greps `provider_key ==` outside `adapters/` and `manifests/` and finds nothing | Every lifecycle event wrote `audit_log` with masked refs; the environment is shown on the card **in words** | BR-INT-008 · BR-INT-007 · BR-INT-037 · BR-INT-026 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | A **real** credential stored | Wave E1 — the human sign-off on `core/crypto.py`'s four judgments, recorded in `09-human-review-ledger.md` with the words shown. Fixture credentials until then |
| b | Customer bills **sent** through the mailbox | W6 — customer email SENDING activates with notifications (`BR-INT-007`, OQ-073). J17's leg and J53 cover the send half |
| c | The bulk-email card saying in words that a mailbox is not an option above a bill volume | `OQ-INT-1488` — the threshold (a mailbox capped at about 2,000 a day needs thirty days for one month's bills at 60,000 accounts). `BR-INT-005`/`006` flagged, not amended |
| d | A clerk pressing *Test it now* | `OQ-INT-1479` — Settings is System Admin only, a signed permission rule; the modal ships Admin-only |

## Where this journey is actually walked — appended 2026-09-04 by the CR-069 wave E build lane

**This section is the only thing the build lane can add that the design lane could not: which of the
rows above are now EXERCISED, by what, and where the walk stops.** Nothing above was rewritten.

| Row | Walked by | What it runs against |
|---|---|---|
| the connect and the test send | `10-scripts/render-checks/cr069-e-smtp-connect-day.mjs` steps 1–2 | a **real SMTP server** the script stands up on `127.0.0.1`, and the assertion is on **what the server received** — one message, from `billing@brazosbend.example`, to the typed address, carrying the subject a person will recognise |
| the wrong password | the same script, step 3, and `06-backend/tests/test_us_int_026_smtp_adapter.py` | a real `535 5.7.8 AUTHENTICATION FAILED` off a real socket, under our own six-word sentence |
| the per-item results | `test_us_int_026_smtp_adapter.py::…seven_bad_addresses…` | three addresses, one refused by the server by name: **2 sent, 1 failed**, and the two that went really went |
| the deletion path | `06-backend/tests/test_us_int_025_disconnect.py` (TC-1…6) and the script's step 5 | credential rows **0**, run rows unchanged, `status = off`, the audit summary, and the queue **untouched** |
| the three exits | `test_us_int_024_credentials.py::test_tc6…` and permanently `10-scripts/gates/g94_credential_three_exits.py` | the database read through a **second raw cursor**, the captured logs, and every audit row — for both plaintexts and two substrings of each |

⚠ **THE HINTS IN ROW 10 ABOVE READ `••••3F9A, ••••A17C` AND THE BUILT PRODUCT WRITES
`••••kbox, ••••iday`.** A hint is DERIVED — the mask plus the last four characters of the secret —
and the design's figures paired a password with an API key's last four from another drawing. The
plaintexts are load-bearing (the three exits grep for them), so the hints follow from them. The
journey's substance is unchanged: two versions destroyed, named by mask, never by value.

⚠ **ROW (a) OF *WHAT THIS JOURNEY CANNOT YET ASSERT* STILL STANDS AND IS STILL ROW (a).**
`core/crypto.py`'s four judgments have not been put to the Product Owner. The ledger row now carries
the mail-password figure a reviewer is owed — `Ew3!kQ9-lockbox` becoming 98 characters beginning
`sbh1:` — so the review can happen; it has not happened. Everything walked above uses a FIXTURE
credential against a mail server this repository started, which is what the wave's blocker permits.
