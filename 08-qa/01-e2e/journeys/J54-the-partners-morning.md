# J54 — The partner's morning ⚠ blocked `OQ-INT-1481` (a finance system collects yesterday's 1,236 payments over three pages at 02:41, three rows a manager can read, and nothing of ours was scheduled)

---
id: J54
tier: 2
rules: [BR-INT-035, BR-INT-044, BR-INT-053, BR-INT-032, BR-INT-033, BR-INT-043, BR-INT-003, BR-INT-039]
stories: [US-INT-020, US-INT-037, US-INT-039, US-INT-040, US-INT-041]
# Wiring: every story above cites `J54` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J54.spec.ts`. Waves R (the issued key,
# `cr069-r-issued-key.mjs`) and S (`cr069-s-partner-morning.mjs`, task S4) write
# it. The GL track — "not a phase; a different project wearing the same word".
# ⚠ BLOCKED ON OQ-INT-1481 — who may authorise an outside system to read a
# utility's payments and bills, and how is that recorded? Every other connector
# is the tenant reaching outward; this one is a third party reaching in. The
# surface, the key, the record, the allowlist and the rate limit are built and
# run ONLY AGAINST THE TEST PARTNER; ENABLING the connection raises
# `NotImplementedError("OQ-INT-1481")` (step 10).
# ⚠ SEAM I-9: no machine authentication exists (`DEFAULT_AUTHENTICATION_CLASSES`
# is the session class only). `MachineCredentialAuthentication` is IDENTITY's to
# build — a companion US-IDN story is owed (wave R1); integrations declares the
# `issued_secret` field kind and the connection.
# ⚠ FIGURE NOTE: the exec plan's S142 line reads "412 records · page 1 of 3"
# while the story's envelope is `{total_records: 1236, page_size: 500,
# total_pages: 3}` — 1,236 over pages of 500 is 500 · 500 · 236, and 412 is
# 1,236 ÷ 3. This journey asserts the SUM (1,236) and the page size the envelope
# declares; filed as DEF-INT-3614 and the plan corrected 2026-09-03. Frame 46.2's
# amber row reads "98,204"
# where the story says 48,000 records — the story's figure is used.
---

**Intent.** The SERVE quadrant — the cell that was empty and nothing said so. **We are the
provider.** A finance system authenticates with a key **we issued**, scoped to **one tenant**,
**shown once and never again**; reads payments and bills on **its** schedule in **its declared
envelope**, with **its words** for our tenders and accounts coming from mapping rows; and
**every page it reads is a run** — `direction = inbound_read`, `trigger = partner`,
`attempted` = records handed over — so that *a partner with a valid key collecting two
years of history at two in the morning* is something a manager **sees**, because nothing else
in the product would show it. A read from outside the allowlist is refused **without
revealing whether the account exists**; revoking the key refuses **the very next call**.

**Upstream leaves (handoff in).** Brazos Bend's `gl_partner` connection ***Aclarian***
(`initiative = them`, `auth.mode = they_hold_ours`, allowlist `198.51.100.0/24, 203.0.113.7`,
rate limit **100/min**, *What they may read* **Payments · Bills**), **not enabled**. Mapping
rows (`integration_target_reference`, `target_key = aclarian`): ledger accounts `1200 →
001.100.11200`, `4100 → 001.100.44100`; tenders `ACHCHECK → Bank transfer`, `ACHSAVINGS →
Bank transfer` (two of theirs, one of ours). Projection `gl_payment_v1` with codecs `json`
**and** `xml`. Payment fixture `PAY-2609-0311 · $142.18 · 2026-09-01 · Bank transfer · account
4100`. **The partner's morning**: 2026-09-02's **1,236** payments. **The unusual read**:
2024-09-01 → 2026-09-01, **48,000** records, **105** pages at 02:41. Callers `198.51.100.12`
(allowed) and `203.0.113.99` (not). Actor **Alex Reed**; the **test partner** fixture. Lone
Star Ridge's route.

**This journey leaves (handoff out).** ONE issued credential (encrypted, **blind-indexed**
for lookup, `masked_hint = ••••7Q2F`, `config.last_used_at`); **three** `inbound_read` runs
(500 · 500 · 236 = **1,236** records) and, on the unusual morning, **105**; a refused read from
`203.0.113.99` recorded; a `429` recorded; the subprocessor register's **inward** row
*Aclarian — reads payments and bills*, **derived** from the live connection; S144 listing the
key *issued by Alex Reed, 3 Sep*. **Nothing written anywhere else** — reads only; the debits
and credits handed over already balance (hard rule 5).

**Fixture.** Frames `50.1` (a key we issue — *THE KEY FOR THEM TO USE · Copy · Copy it now.
This is the only time it is shown.* · *Nothing to test — the connection starts when they
first call.*), `46.1` (the card *Reading from us · 06:14 today*), `46.2`/`80.2` (S144 access
log with the amber row). Endpoints `GET /api/v1/payments` · `GET /api/v1/billing` · `GET
/api/v1/openapi.json`.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (key · runs · refusal · isolation) | Rule |
|---|---|---|---|---|
| 1 | Alex — *Connect · Third-party GL* (S141, frame `50.1`) → *Issue key* | The key `sbh_live_7Q2F…` is shown **once**, in mono, with **Copy** and *Copy it now. This is the only time it is shown.*; footer **Done** · *Nothing to test — the connection starts when they first call.* Reopening shows **`••••7Q2F` only**. S144 lists it: partner · hint · scope (Brazos Bend) · *issued by Alex Reed, 3 Sep* · *never used* · active | `issued_secret` is a **declared field kind** — the opposite of every other card (**we** give **them** a key). The plaintext appears in **no log, no audit row, no API response** after the one display (the three exits). *Replace key* shows a new one once; the old refuses from that moment; both on S144 (old *revoked*) | BR-INT-053 · BR-INT-043 · BR-INT-003 |
| 2 | **02:41** — the test partner, from `198.51.100.12`, `GET /api/v1/payments?date=2026-09-02` over three pages | Authenticated **as the partner for Brazos Bend only** (`MachineCredentialAuthentication`, identity's class, resolving the key through `blind_index_candidates`). Envelope **`partner_paged`**: `{total_records: 1236, page: 1, page_size: 500, total_pages: 3}` — **not** the DRF `{count, next}` shape. Each record `id · paymentDate · amount` (4-dp money, displayed 2) · `tenderType` **`ACHCHECK`** through the mapping row · `projectType` the constant ***Utility Billing*** · `accountString` **`001.100.44100`** from the row (else `ledger_accounts.code`) | **Every page is a run**: three `integration_run` rows `direction = inbound_read · trigger = partner · attempted = 500 / 500 / 236`, the key hint as *who*. S144's `last_used_at` moves. The three attempted counts **sum to 1,236 and match what we hold** | BR-INT-035 · BR-INT-032 · BR-INT-033 |
| 3 | S142 → *Who has read* (S144, frame `46.2`) | `AccessLog` WHEN · WHAT THEY TOOK · ROWS: *Today, 02:41 · Payments, 2 Sep · 500* · *… · 500* · *… · 236*, each with the key hint. Note: ***This is not a run history.** We did not start any of it.* | The card on S8 reads ***Reading from us · 02:41 today*** — a **computed display state** for a connection whose operations are all *they read* and that has an `inbound_read` run — **not** a sixth value of `integration_connection.status`. *State 6 is not a synonym for working: nothing of ours ran* | `US-INT-041` TC-1 · `08-screen-layouts.md` S8 |
| 4 | **the unusual read** — 2024-09-01 → 2026-09-01 at 02:41 | **Every request authorised**; **105** `inbound_read` runs, **48,000** records, the total in the header; the row is **bold** with an `AmberBox` beneath: *A partner taking two years of history at two in the morning is either a migration somebody arranged, or it is not. Every request was authorised. **Nothing else in the product would show it.*** | The access log is the only place it shows — failure 13, the last of the silent four | BR-INT-035 · `US-INT-041` TC-2 |
| 5 | **negative · the allowlist** — a read from `203.0.113.99` for a **real** account, then for an **unknown** one | **Refused before the body is read**, and **the two refusal bodies are byte-identical** — the refusal reveals **nothing about whether the account exists**. Recorded as a refused read | The allowlist is a property of the **connection** (`config.allowlist`); it is also the mitigation for the enumeration oracle | BR-INT-044 · `US-INT-041` TC-3 |
| 6 | **negative · the rate limit** — the 101st request in a minute | **`429` with `Retry-After`**; recorded as a refused read; the partner's later requests proceed | A per-partner rate limit on the connection | `US-INT-041` TC-4 |
| 7 | **their words, and one shape twice** — a *Bank transfer* payment; an unmapped tender; the same payment as JSON and as XML | `tenderType` serves **`ACHCHECK`** from the row; an unmapped tender serves ***Other*** and the row goes **red on S143**. `PUT …/mappings` with `ACHCHECK → Cash` beside the existing row → **refused by the UNIQUE on the external side** (one of their words means exactly one of ours). The same payment emits as **JSON to one partner and XML to another from one projection**, both parsing back to identical field sets; `codec = "yaml"` in a manifest is refused **at load** with the registered list | A fourth accounting partner costs **rows, not a migration** — `ledger_accounts` unchanged; `qbo_ref` / `xero_ref` are **read, never widened**, and **no third vendor column is ever added** (`OQ-INT-1480` decides whether the rows replace them) | BR-INT-032 · BR-INT-033 · `US-INT-037` TC-2/3 · `US-INT-039` TC-1/2 |
| 8 | `GET /api/v1/openapi.json` | The published specification of the surface — *described by a published specification rather than a bespoke document* | The three endpoints are the smallest set that satisfies the finance partner's own document | `US-INT-041` |
| 9 | **the register** | The subprocessor register gains ***Aclarian — reads payments and bills — authorised by … on …*** as an **inward** relationship, **derived from the live connection** (`initiative = them`), never typed | `C33`: the register records the relationship in the inbound direction | BR-INT-035 |
| 10 | **boundary · `OQ-INT-1481`** — Alex sets the connection `enabled = true` | **`NotImplementedError("OQ-INT-1481")`**; the screen reads *Waiting for a decision on who may allow this* — in words. **No real partner is served**; the test partner is the only caller | The options are the PO's — an audited admin grant plus a register row · the owner role only · a signed DPA reference first. **A lane may not choose** | BR-INT-035 · `OQ-INT-1481` |
| 11 | **negative · revoke** — Alex presses **Revoke the key**; the partner calls one second later | **Refused — the very next call, not the next collection**; the refusal reveals nothing about any account. S144 shows the key *revoked* | Revocation is effective on the next request | BR-INT-053 · `US-INT-040` TC-3 |
| 12 | **tenant isolation** | The key presented against **Lone Star Ridge's** route → **unknown caller**, body identical to a wrong key. `GET /api/v1/payments?company_id=<Lone Star Ridge>` with the Brazos Bend key → answered **as if the company were unknown, in the declared way** — which may not be 404 | A machine credential is scoped to `tenant_id`; RLS `FORCE` on the runs | hard rule 1 · `US-INT-040` TC-5 · `US-INT-041` TC-7 |
| 13 | **INVARIANCE** | Nothing of ours was scheduled; nothing was written outside `integration_run`, `integration_credential` and the refusal records; every page read is a row a manager can read; the debits and credits handed over **already balanced** — the posting service refuses anything else; the key was shown once; the refusals learned nothing | The `accountString` beyond the flat code (fund · department · object) waits on `OQ-INT-1480` | hard rule 5 · BR-INT-035 |

⚠ **DATED AMENDMENT, 2026-09-17 — STEP 12's `?company_id=<Lone Star Ridge>` LEG IS SUPERSEDED (`CR-111-BRC04`, `BR-INT-070`).** PO verbatim: *"you will ahve to remove company ID filter from all Apis - we cannot tell tenant ID outside our system"*. **`company_id` is no longer required, refuses nothing, is still accepted and ignored, and what was sent is recorded on the run row.** `403 COMPANY_MISMATCH` disappears from every partner route.

⚠ **STEP 12 IS REWRITTEN, NOT DROPPED, AND THE DISTINCTION IS THE WHOLE POINT.** Its first leg — **the key presented against another utility's route answers exactly as a wrong key does** — is untouched and is the real isolation proof: a machine credential is scoped to one `tenant_id`, and RLS `FORCE` is what hides everything else (hard rule 1). **Only the second leg changes:** the Brazos Bend key sent with Lone Star Ridge's `company_id` must now be **served Brazos Bend's own data, normally**, with the value they sent **recorded** — never refused. **`company_id` never isolated anything**; deleting the step because the parameter left would delete the proof of the thing that does.

Full record: `12-governance/02-decision-log.md` 2026-09-17 · `12-governance/change-requests/CR-111-BRC04-invoice-cloud-partner-api.md` §2 · `BR-INT-070`.

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Serving a **real** partner | `OQ-INT-1481` — who may authorise a third party reaching in. The enable path raises |
| b | `MachineCredentialAuthentication` itself | Identity's companion story (seam I-9, wave R1) — a `US-IDN-` id allocated from that module's register |
| c | `accountString` in `Fund.Department.Account` form, and retiring `qbo_ref` / `xero_ref` | `OQ-INT-1480` — a migration on a signed finance table |
| d | The words on the conformance badge | `OQ-INT-1483` — *supports*, *compatible with* or *certified*; MultiSpeak and Green Button are not claimed |
