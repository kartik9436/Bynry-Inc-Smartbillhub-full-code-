# J49 — Wrong key Friday (a bad password pasted at 5 pm, *the mail server rejected the password*, and a one-row roll back that resumes sending without re-authorising)

---
id: J49
tier: 2
rules: [BR-INT-003, BR-INT-014, BR-INT-019, BR-INT-025, BR-INT-038, BR-INT-039, BR-INT-043]
stories: [US-INT-014, US-INT-015, US-INT-019, US-INT-020, US-INT-024]
# Wiring: every story above cites `J49` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J49.spec.ts`. Wave E task E8 writes it
# alongside J48 (`cr069-e-smtp-connect-day.mjs`, steps 3–4). Phase 2.
# ⚠ PROVED ON POSTGRESQL: the "exactly one active credential" rule is enforced
# by the database (`EXCLUDE (connection_id WITH =) WHERE (is_active)`), not by
# application code, and SQLite has no EXCLUDE constraint (law 14).
---

**Intent.** A credential is **versioned, never updated in place**. Alex replaces the working
password with the wrong one at 5 pm on a Friday; `test()` fails with the mail server's own
verdict; the card goes *Not working*; he presses *Roll back* and **sending resumes without
re-authorising**. Both versions are on the record — v1 active again, v2 retained inactive —
the audit trail has a real before-and-after **without ever holding a plaintext**, and the
plaintext of **neither** password is anywhere.

**Upstream leaves (handoff in).** J48's working Brazos Bend `email_smtp` connection with
credential **v1** `Ew3!kQ9-lockbox` (hint `••••3F9A`), `is_active`, `expires_at` NULL; its
run history. An **expired v0** fixture on a twin connection (for the refused roll back).
Actor **Alex Reed**, **Friday 28 Aug 2026, 5:00 pm**. Tenant **Lone Star Ridge WSC**.

**This journey leaves (handoff out).** **Two** `integration_credential` rows for the
connection — v1 `is_active = true` (re-activated), v2 `is_active = false`, `rotated_at` set on
whichever was deactivated at each step; **the connection row unchanged** (it holds no secret
to change); **two** run rows (`failed` for v2's test, `succeeded` for v1's re-test); **two**
audit rows — `integration.credential_rotated` carrying `••••3F9A → ••••A17C` and nothing
else, `integration.credential_rolled_back`; the card **Working**. J50 reuses the same
versioning on the OAuth return trip.

**Fixture.** v2 password `wrong-key-friday` (hint `••••A17C`). Frames `54.2` (keys table
*In use ••••A17C · Added today, 17:04 · active* / *Previous ••••3F9A · Added 12 Aug · Go back
to this*), `52.2` (test failed). Refusal sentences *Nothing to roll back to* · *Previous
credential has expired*.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (rows · constraint · exits · isolation) | Rule |
|---|---|---|---|---|
| 1 | Alex — S142 → *Replace password* → types `wrong-key-friday` → save (`POST /integrations/email_smtp/credential`) | Credential **v2** written (`••••A17C`), v1 **deactivated** with `rotated_at`; `test()` re-runs **on v2** automatically | **The connection row does not change** — assert `updated_at` and every column unchanged; it holds no secret. Audit `integration.credential_rotated` carries **`••••3F9A → ••••A17C` and nothing else** | BR-INT-025 · BR-INT-014 |
| 2 | The test fails | `TestOutcomeCard` `52.2`: ***The mail server rejected the password** · Failed*, `ProviderSaid` *535 5.7.8 AUTHENTICATION FAILED*, buttons *Try again · Edit*. Run row `trigger = manual · failed` with that sentence and a trace id. Card → **Not working · tested just now** | The sentence is the mail server's **verdict in words**, from a **real** attempt — not a credential parse. `provider_error` rendered only here, to Brazos Bend | BR-INT-019 · BR-INT-039 |
| 3 | S142 → the keys table (frame `54.2`) | *KEYS ON THIS CONNECTION*: **In use `••••A17C` · Added today, 17:04 · active** / **Previous `••••3F9A` · Added 12 Aug · Go back to this**. Note: *Pasted the wrong one? Go back to the previous key and sending resumes. You do not have to ask the provider for anything.* · *Only the last four characters are ever shown. Neither key can be read back, by anyone, including us.* | The hint is **display only** and is never the secret. Nothing on the screen is a database id | BR-INT-003 · B14 rule 31 |
| 4 | *Go back to this* (`POST /integrations/email_smtp/credential/rollback`) | **v1 active again in one row**, v2 retained **inactive**; `test()` re-runs on v1 → `succeeded`; card **Working**; **no re-authorisation** — Alex asked the provider for nothing. Audit `integration.credential_rolled_back` | Two credential rows remain — **nothing was deleted**. The dispatcher's next batch resolves **v1 inside the seam at use time** (`seams/notifications.py`) and sends | BR-INT-025 · BR-INT-038 |
| 5 | **🔒 PostgreSQL · the database refuses** — a fixture writes two `is_active = true` rows for one connection in one transaction | **Refused by the database** — `EXCLUDE (connection_id WITH =) WHERE (is_active)` — below the application. `UNIQUE (connection_id, version)` refuses a second v2 | ⚠ The SQLite suite passes this **with or without** the constraint; the proof is the PG job (`06-backend/tests/pg/`) | BR-INT-025 · law 14 |
| 6 | **negative · the refusals** — *Roll back* on a connection with **one** version; *Roll back* onto the **expired v0** twin | *Nothing to roll back to* · *Previous credential has expired* — each ≤ 6 words, `message_key` in all eleven catalogues; re-authorisation is the only path for the expired one | Neither refusal writes a credential row | `US-INT-024` TC-4/5 · B14 rule 33 |
| 7 | **the three exits** — dump the database, capture the logs, read `audit_log`; search for **both** plaintexts | `Ew3!kQ9-lockbox` and `wrong-key-friday`: **zero hits in all three**. The conformance kit runs the three-exits assertion for **every** adapter (wave E7's gate — RED first by logging the password inside the fixture adapter) | `payload_enc` is never selected into an API response; `GET /integrations` and S141's Manage view carry the hint only | BR-INT-003 · `US-INT-024` TC-6 |
| 8 | **tenant isolation** | Lone Star Ridge posts a rotation against Brazos Bend's connection id → **404 identical to absent; no row written**. A roll back from Lone Star Ridge → the same | RLS `FORCE` on `integration_credential`; the credential is scoped by the connection's tenant | hard rule 1 · `US-INT-024` TC-7 |
| 9 | **INVARIANCE** | The connection row never changed; every version is still on the record; exactly one was active at every instant, and the **database** guaranteed it; the audit trail shows the before-and-after as hints and never as secrets; the run history is unbroken across the rotation and the roll back | Sending resumed with the good key and nobody re-authorised | BR-INT-025 · BR-INT-003 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | A **real** password rotated | Wave E1 — `core/crypto.py`'s sign-off before the first real credential is stored |
| b | A clerk (not an admin) pressing *Test it now* after the roll back | `OQ-INT-1479` |

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
