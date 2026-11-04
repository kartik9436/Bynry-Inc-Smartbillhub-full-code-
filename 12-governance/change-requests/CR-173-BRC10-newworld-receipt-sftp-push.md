# CR-173-BRC10 — New World / Logos: the day's receipt file is pushed to the City's SFTP folder by a runbook

**Raised:** 2026-10-07 by the Product Owner, in chat.
**Status:** **DONE — 2.559.0 (`54583c831`) and 2.559.1 (`ade72c0db`), lane NW-SFTP, 2026-10-07.** 🔒 files HUMAN-REVIEW-PENDING (ledger row *NEW ROW 2026-10-07 · CR-173-BRC10*).
**Branch:** `claude/charming-pascal-k7i2lr` (`BRC10`, the suffix this branch has carried since `CR-171-BRC10`). `10-scripts/allocate.py cr` answered **173** against the remote and `--verify 173` reported it free on every branch at allocation.
**Classification (`13-change-process.md` §1):** a **CHANGE** — a utility cannot today have its receipts placed in the City's folder; it can only let New World dial `/partner/v1/receipts`. It touches no money rule and writes no money: the file is a projection of payments already posted. It does touch three 🔒 paths — an **idempotency key** (one successful file per utility per day), a **new tenant table with its RLS policy**, and the **credential store's one-active guard** — and every such file ships HUMAN-REVIEW-PENDING with a row in `12-governance/09-human-review-ledger.md`.

⚠ **THE SFTP PASSWORD WAS GIVEN IN CHAT. IT IS WRITTEN IN NO FILE, COMMIT, FIXTURE, TEST, LOG OR MESSAGE OF THIS CHANGE.** The utility types it on the screen this change builds; tests use `test-password-not-real`.

## 0 · What arrived, in the requester's words (verbatim)

From the three decision-log rows of 2026-10-07 (*"NEW WORLD / LOGOS RECEIPT FILE PUSHED TO THE CITY OF ANN ARBOR BY SFTP: SCOPE AND EIGHT ANSWERS"*, *"THE NEW WORLD SFTP SETTINGS ARE ENTERED ON SCREEN BY THE UTILITY, NEVER IN AN ENVIRONMENT FILE"*, *"PO APPROVED — THE SEND TO CITY FOLDER SECTION"*). Only the PO's own words are repeated here; the rows hold the full rulings.

| | The PO, verbatim |
|---|---|
| S1 — per utility | *"this path is specific for 1 tenant/utility and not common for everyone"* |
| S2 — a runbook | *"You already ruled that scheduled jobs run as runbooks - this is correct"* (re-confirming 2026-09-16, *"we are going to use runbooks to run the scheduled job"*) |
| Q1 — the password | *"if it is for SMTP then it will be in conenctor itself specific to that utility/tenent"* |
| Q2 — which day | *"(b) Ann Arbor's local day - we need to use date and time setting from Tenant - we have that setting"* |
| Q3 — an empty day | *"(a) send an empty file and alert"* |
| Q4 — run twice | *"(a) refuse if already sent"* |
| Q5 — who is alerted | *"System admin of Utility/tenant"* |
| Q6 — what time | *"User will configure this in runbook on thier own"* |
| Q7 — unmapped fees | *"(a)"* — sent flagged and counted, never guessed |
| Q8 — network | *"okay"* |
| Settings on screen | *"where we will save this - I dont want to go to developer and ask them to put it in env files this is tenant/utility data and should be handled from screen itself"* · the one-file example: *"thi si okay"* |
| The section | *"this is okay"* |

## 1 · What is reversed, and what is NOT (step 2)

- The request's *"prior UTC day"* is SUPERSEDED by Q2 (tenant-local day). Nothing signed is reversed.
- `/partner/v1/receipts` and `/partner/v1/ledger` are **unchanged**; the two existing operations on `erp_newworld` stay byte-identical.
- **Not built:** the Ledger/JV file (out of scope by the request itself).

## 2 · What is built (version 2.559.0)

| Surface | What | Where |
|---|---|---|
| SFTP client | `paramiko`, adapted to the existing `FolderWriter` shape, bound ONCE (`sftp.CLIENT`); timeouts 15 s connect / 15 s sign-in / 30 s channel; the server key is checked before the password is sent and never accepted silently; every refusal is one fixed ≤ 6-word sentence, the far end's own words scrubbed | `06-backend/apps/integrations/sftp.py` · `pyproject.toml` |
| Manifest | `erp_newworld` gains six OPTIONAL fields in group `send_file` (Server, Port 22, User name, Password → encrypted, Folder `/`, Server key) and a third operation **Send receipt file** (`out · us · sftp · scheduled`, idempotency `refuse` on `period_target`). The two partner operations are byte-identical | `apps/integrations/manifests/erp_newworld.py` |
| Adapter | `ErpNewWorldAdapter` — places already-built files, proves the folder is writable; passes the conformance kit | `apps/integrations/adapters/erp_newworld.py` |
| Credential slot | one active credential per (connection, slot); the password is slot `send_file`, the City's key stays `primary` | migration `integrations/0015` · `services.record_credential(slot=)` |
| Settings section | **Send to City folder** panel on Settings → Integrations → New World / Logos: the six items, **Save ✓**, **Test connection** (signs in, writes `SMART360-connection-test-<time>.txt`, deletes it if allowed, stores and shows the server key on first success), and **Send again ✓** (a day + a required reason) | `07-frontend/src/features/integrations/FieldGroupPanel.tsx` · `apps/integrations/file_drop.py` · `file_drop_api.py` (`/integrations/{key}/groups/{group}`, `/test`, `/resend`) |
| File builder | the utility's local day as two instants; the API's own filter, order and `newworld.emit` in batches of 1,000; ONE `newworld.render`; `Receipt_YYYYMMDD.xml` named for the data day; empty day = `<Receipts />` + alert; unbalanced and no-GL lines sent and counted | `apps/integrations/receipt_push.py` · `seams/payments.py` (`posted_from`/`posted_before`) |
| Once per day | `integration_file_delivery` + partial unique index (RLS FORCE in the same migration); claim in a SAVEPOINT; a resend is a person's row outside the index | `models.IntegrationFileDelivery` |
| Runbook | **New World receipt push** — Build → Upload → Record; `day` blank = yesterday local; today refused; dry builds and reports; port `send_partner_file` (the fifteenth, owned by integrations); first key on `LIVE_ENABLED_RUNBOOKS` | `apps/runbooks/definitions/newworld_receipt_push.py` · `ports/integrations_ports.py` · `engine/acts.py` |
| Run by hand | `POST /runbooks/{key}/runs` (`dry`/`live`, one-off text inputs); **Run ▶** on every runbook page opens a dialog (it said *Not connected yet.* until now) | `apps/runbooks/services.py::request_run` · `api.py` · `RunbookSetupPage.tsx` |
| Run log | every attempt (and every Test connection) is an `integration_run` row on the New World connection: receipts as the count, the file, the folder and the flagged counts in the summary | Settings → Integrations → New World / Logos → run history |
| Alerts | failure (cannot connect, sign-in refused, upload refused, build failed) and the empty day → one bell message to the System Admins (+ the person who pressed) | `seams/notifications.queue_staff_alert` |

**Not built (by the request):** the Ledger/JV file.

## 3 · What the build decided rather than asked (law 13)

Six decision-log rows of 2026-10-07, each headed *"CR-173-BRC10 (LANE JUDGMENT)"*: the credential slot; the server key (never silently accepted); how the runbook becomes live for one utility; the fifteenth port and the *not done* answer; one file per day + the resend + today refused; what the file holds, the run-history counts and what is not changed. Nothing was put to the PO.

## 4 · Build record

- 2026-10-07 — lane NW-SFTP. Version **2.559.0** (`allocate.py version --bump change`).
- Tests: `tests/test_cr173_newworld_sftp.py` (31) · `tests/test_cr173_newworld_sftp_pg.py` (PostgreSQL 16) · `FieldGroupPanel.dom.test.tsx` (5) · existing suites moved where this change moved a counted fact (ports 14→15, live set, adapters 10→11, the setupWire export set, the integrations key count).
- 🔒 ledger row: `12-governance/09-human-review-ledger.md`, *NEW ROW 2026-10-07 · CR-173-BRC10*.
- Pushed `54583c831` (2.559.0). The browser walk then found **`DEF-INT-10000`** — once a City server was saved, the two read rows showed it as their address (`addressing.host_fallback_field` counted the grouped field). Fixed in **2.559.1** with a regression test.
- **Proved red before trusted green (law 7), in the harness that runs them:** savepoint deleted → the PostgreSQL racing case raises `TransactionManagementError`; pages glued instead of one render → 2 cases red; the UTC day instead of the utility's → red; the already-sent check and the index bypassed → red; the grouped-field fix reverted → red. *(A first savepoint probe stayed GREEN because the polite already-sent read answered before the INSERT was reached — a check looking at the wrong thing; the racing case was written to reach the INSERT.)*
- Results: SQLite 32/32; PostgreSQL 16 7/7; vitest `FieldGroupPanel` 5/5 and the runbook page 8/8 + `src/features/integrations` all green; `tsc` clean (proved able to fail). Walk `10-scripts/cr173_newworld_sftp_walkthrough.mjs` 10/10 at 1440 against a local API, the local SPA and the in-process fake SFTP server; the 5 Oct file held 3 receipts, including the 21:05 Chicago payment (02:05 UTC on the 6th).
- Photos (scratchpad `po-shots/newworld-sftp/`): `01` empty section · `02` saved, password masked · `03` test OK, key captured · `04` wrong password · `05` the Run dialog · `06` the runbook after a live run · `run2/07–09` the connection and its run history.

## 5 · What a System Admin does to set it up and test it

1. Settings → Integrations → **New World / Logos** → *Set up*. Scroll to **Send to City folder**.
2. Type **Server** `sftp.a2gov.org`, **Port** `22`, **User name** `Bynry-SMART360`, the **Password** the City gave, **Folder** `/` (change it when the City confirms its folder). Leave **Server key** empty, or paste the fingerprint the City sends. Press **Save ✓**. The password now shows only as `••••` and its last four.
3. Press **Test connection**. Success reads *Signed in and wrote a file.* and shows *Server key saved: SHA256:…* — compare that with the City's fingerprint. A wrong password reads *User name or password refused.*
4. Runbooks → add **New World receipt push** → **Run ▶** → *Dry run* (optionally type a day, e.g. `2026-10-05`). The result shows the file name, receipt count and flags; nothing is sent.
5. **Run ▶** → *Run for real*. The file lands in the City's folder; the run shows on the connection's run history.
6. When happy: the runbook's schedule — set the time (the runbook's own schedule) and in *Change limits* choose *Approved up front*, so the nightly run sends for real.

## 6 · What DevOps must still do

- Allow outbound TCP **22** from our servers to `sftp.a2gov.org` (PO Q8).
- Get the server's **host-key fingerprint** from the City and check it against the one shown after the first Test connection.
- Rebuild the image (new dependency `paramiko`) and run migrations (`integrations/0015`).
- After the password is stored, ask the City to rotate it (it was given in chat).

## 7 · Rollback

Redeploy 2.558.4 after `migrate integrations 0014`; the reverse refuses while a connection holds both a key and a City password — delete the password first.
