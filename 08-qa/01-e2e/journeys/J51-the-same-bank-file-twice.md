# J51 — The same bank file twice — PostgreSQL (*refused duplicate — the same file as Tuesday 06:10*, a hash computed before parsing, and no payment applied twice)

---
id: J51
tier: 2
rules: [BR-INT-020, BR-INT-009, BR-INT-010, BR-INT-026, BR-INT-031, BR-INT-033, BR-INT-043, BR-INT-053, BR-PAY-028, BR-PAY-023, BR-LED-004]
stories: [US-INT-014, US-INT-033, US-INT-038]
# Wiring: every story above cites `J51` in its own `journeys:` frontmatter. The
# flow document's index-by-story also lists US-INT-020 for J51; its frontmatter
# does not cite J51 (it cites J48, J49, J53, J54) — the run-row rules it owns are
# asserted here through BR-INT-020 without adding the story. Filed as DEF-INT-3613;
# the index corrected 2026-09-03.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J51.spec.ts`. Wave I task I4 writes it
# with J52 (`cr069-i-same-file-twice.mjs`). Phase 4 LAUNCH — "files out and
# files in" — and phase 4's exit test is step 3, ON REAL POSTGRESQL (law 14).
# `J14` (lockbox day) GAINS ITS PROFILE LEG from this journey: the file arrives
# through a NAMED bank connection instead of a bare upload, and editing the
# connection afterwards does not restate history. J14's file is amended when the
# leg is built, not before.
---

**Intent.** The bank & lockbox profile of `EP-INT-03` becomes a **connection like any
other** — a run row, a test, a state and a history — and the file-in idempotency key is a
**content hash computed BEFORE parse**: *"by the time you have parsed it you have already
spent the work."* Priya uploads Tuesday's lockbox file through a **named** bank connection;
on Wednesday she uploads the byte-identical file by mistake and reads **refused duplicate —
the same file as Tuesday 06:10**, the second run naming the first **by date**, `input_hash`
equal on both rows, and **no payment applied twice**. The same connection imports a
**camt.053** statement with the codec **named, not coded**; an unknown format on the way
**out** is refused **by name with the list of what exists**; and a Nacha return code maps
onto our four signed reversal reasons **as a row** — except `R02`, which is the PO's.

**Upstream leaves (handoff in).** Phase 1–3 done; codecs registered in
`apps/integrations/codecs.py` — bank `bai2 · csv · ofx · qbo · qfx · camt053`, accounting
`qbo · xero · csv · iif` (the print-vendor format registry lifted into it). Brazos Bend's
`bank_lockbox_file` connection ***Chase lockbox*** (label *Chase operating*, format **CSV**
with its column mapping as the **second step** — `Column 1 — 20260901 → Date … Column 4 —
REF88214 → Ignore`, source *We upload it*). **J14's 40-row lockbox CSV** (Brazos Bend, 8
Aug; 38 good rows, 2 with failing account-match heuristics). `payment_import.py:344` already
hashes the file (`lockbox.file_sha256`) **before** `parse_remittance_file` and refuses a
duplicate naming the batch and its `committed_at` (`br_ref=BR-PAY-028`). A real-bank
**camt.053** fixture (redacted). Nacha returns `R01`, `R02`, `R03`. Brazos Bend's **four
signed reversal reasons** `nsf · bank_chargeback · duplicate · error`. Lone Star Ridge with a
file whose hash **equals** a Brazos Bend file. Actor **Priya Menon** (Billing Clerk).
**Tuesday 1 Sep 2026 06:10**, then **Wednesday 2 Sep**.

**This journey leaves (handoff out).** ONE committed `payment_import_batches` row (payments')
of **38** payments, recording its **producing connection**; **two** `integration_run` rows
for the file — the first `succeeded` (`38 / 2 / 0` in the receipt's terms), the second
**refused duplicate** — **sharing `input_hash`**; the batch's `committed_at` Tuesday 06:10;
`R01 → nsf` as an `integration_target_reference` row; `R02` **unmapped, red**. J52 continues
on the same connection; J14 records the batch's producing connection.

**Fixture.** S38 (`features/payments/BankImportWizard.tsx`) picks the connection; S35 shows
the batch; S142 the runs; S143 the *Why a payment bounced* tab; S141's bank variant (frame
`50.2`). `JOBS_EAGER=false --reuse-db`; PostgreSQL 16 job
`06-backend/tests/pg/test_us_int_033_duplicate_file_pg.py`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (hash · rows · batch · isolation) | Rule |
|---|---|---|---|---|
| 1 | Priya — S38 → *Chase lockbox* — **a connection, not a bare upload** | The picker names the connection by its **label**; S141's bank variant (frame `50.2`) shows *What to call it · File format BAI2 | camt.053 | CSV | OFX · Where it comes from We upload it | Fetch from a folder · How often Nightly | Manual*, and **the column mapping only once a file has been seen** — a second step, not a field | The format picker exists **only because** more than one codec is registered; `email_smtp` (one codec, `mime`) shows **no picker**. A `mapping_editor` is one of the three declared field kinds a plain field cannot express | BR-INT-043 · BR-INT-033 |
| 2 | **Tuesday 06:10** — uploads J14's 40-row file | `input_hash` (sha-256) **computed before any parsing** — asserted by **ordering** on the fixture — and written on the run row **first**; then the bytes handed to `apps.payments.payment_import.stage_import / commit_batch` through `seams/payments.py` — **the one inbound write path**. Run row `succeeded`; receipt artifact **38 ok / 2 named** (J14's numbers: the two account-match heuristics flagged for review, never auto-guessed) | The batch **records its producing connection** (`payment_import_batches` profile ref → connection id). Integrations **wrote no payment** — payments' service did. Money to 4 dp on payments' rows; the drawer day is the **posting** date (J14 step 4) | BR-INT-020 · BR-INT-009 · BR-PAY-023 |
| 3 | **Wednesday · the phase-4 exit test (PostgreSQL)** — the byte-identical file again | Second run: **refused duplicate — the same file as Tuesday 06:10**, naming the first **by date**; `input_hash` **equal on both rows**; **no payment applied twice** — payments' batch count and every payment row unchanged; refusal `br_ref = BR-PAY-028` | The hash was computed **before** parsing on the refused run too — no parse work spent. The idempotency record is **file + tags** (BR-PAY-028/OQ-044) and it **survives every profile edit, deactivate, reactivate and disconnect** — no lifecycle action launders a duplicate | BR-INT-020 · BR-PAY-028 · law 14 |
| 4 | Priya renames the connection *Chase lockbox* → *Chase operating account* | The batch on S35 **still reads the label it was produced under** — editing the connection afterwards **does not restate history** (J14's leg) | Forward-only edits; `US-INT-010`'s IS-1 lifecycle — deactivate-first when used-by > 0; hard delete only at used-by = 0 | `US-INT-033` TC-4 · BR-INT-016 |
| 5 | **the codec, not a connector** — a **camt.053** statement uploaded to the **same** bank connection | Imports through the same connection as BAI2; the run names **`codec = camt.053`**; the recorded, redacted real-bank fixture is in the repo. A codec registered **with no fixture** fails the conformance kit as *not a supported format* | Format is a **registered codec separate from the projection**; `camt053.py` with `fixtures/camt053/*.xml` absent → *not a supported format* | BR-INT-033 · `US-INT-038` TC-3/6 |
| 6 | **negative · outbound refuses by name** — an export requested as `codec = "xlsx"` | Refused **by name with the list of what exists**: *xlsx is not a registered format — QuickBooks, Xero, CSV, IIF*. A manifest naming `codec = "yaml"` is refused **at load** | Unknown values **degrade** inbound and **refuse** outbound — the same rule, opposite directions | BR-INT-031 · BR-INT-033 |
| 7 | **the return codes as rows** — a returned payment `R01`; then `R02` | `R01` → reversal reason **`nsf`** (*not enough money*), the raw `R01` kept on the payload. **`R02` (*account closed*) maps to none of the four signed reasons**: recorded as `other`, raw `R02` on the payload, **red on S143's *Why a payment bounced* tab** — and **the code path that would choose a reason raises `NotImplementedError("OQ-INT-1487")`** | The reversal-reason lookup still has **four** values — a third party's vocabulary does not widen a signed list. **MultiSpeak and Green Button are not claimed** (`OQ-INT-1483` bounds the words) | BR-INT-031 · BR-INT-053 · `OQ-INT-1487` |
| 8 | **negative · sandbox** | A `sandbox` bank connection handed a real file → refused *Sandbox connection — test only*; production and sandbox are **two rows** (`UNIQUE (tenant, key, environment)`) and the card shows the environment **in words** | `test()` on an **upload** source has no safe instance → the card reads *cannot be tested until first use*; on an **SFTP** source `test()` lists one directory and imports nothing | BR-INT-026 · BR-INT-019 |
| 9 | **tenant isolation** | Lone Star Ridge uploads a file whose hash **equals** a Brazos Bend file → **accepted** — the hash is scoped to the tenant, and nothing about Brazos Bend's run is revealed. Two tenants map `R01` differently → each sees its own row; the raw code is the same | RLS `FORCE` on `integration_run` and `integration_target_reference` | hard rule 1 · `US-INT-033` TC-6 |
| 10 | **INVARIANCE** | Money moved **once**; the second arrival was refused naming the first; the hash preceded the parse on both; the batch kept its producing label through a rename; no codec left the registry and none entered without a fixture; the four reversal reasons stayed four; `R02` chose nothing | Integrations imported nothing itself — payments' one write path did, through the seam (B1) | BR-INT-020 · BR-INT-008 · hard rule 6 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | What `R02` maps to | `OQ-INT-1487` — a fifth reason widens a signed list; `other` with the raw code is the boundary |
| b | A **scheduled** SFTP fetch — credentials, a poller, a failure nobody watches | The design's own scope call inside phase 4; upload is the working path and the connection records an SFTP source as `US-INT-008` does today |
| c | Bank matching beyond exact-amount, one-to-one | `OQ-144` CLOSED and relied on — a settlement file becomes a third input to reconciliation, not a change to the matching rule |
