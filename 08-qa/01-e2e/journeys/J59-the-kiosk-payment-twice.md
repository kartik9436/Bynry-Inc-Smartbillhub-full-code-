# J59 — The kiosk payment, twice (`K-88231 · $42.10 · CASH` for `ACC-1048`, applied once; the replay answered `409` before anything is posted; a return carrying the same id that reverses instead of being refused)

---
id: J59
tier: 2
rules: [BR-INT-020, BR-INT-021, BR-INT-028, BR-INT-030, BR-INT-031, BR-INT-032, BR-INT-044, BR-INT-045, BR-INT-053, BR-PAY-003, BR-PAY-036, BR-INT-037]
stories: [US-INT-018, US-INT-037, US-INT-038, US-INT-044]
# Wiring: every story above cites `J59` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J59.spec.ts`. Wave N task N6 writes it
# (`cr069-n-kiosk-twice.mjs`), driven by A REAL CAPTURED PAYLOAD, redacted, in
# `fixtures/payments_kiosk/`. Phase 5 LAUNCH — "a payment taken at a kiosk
# appears on the customer's account by itself" — and PHASE 5'S EXIT TEST is
# steps 3–5.
# 🔒 `inbound.py` and the kiosk key handling are a SENSITIVE PATH (webhook keys);
# HUMAN-REVIEW-PENDING with the ledger row: "$42.10 applied once; the replay
# answered 409 before anything is posted; a return with the same id reverses
# instead of being refused" (N5).
# ⚠ `payments/webhooks.py` IS NO LONGER A STUB — 577 lines, built 2026-09-03 as
# CR-060 C21, 15 tests, idempotent on `webhook_key`, savepoint proved on PG. The
# door REUSES its three guards and mints no second inbound path. `payments.channel`
# and `payments.external_ref` DO NOT EXIST at HEAD — payments' own migration (N1)
# adds them, run first and in parallel.
# ⚠ OQ-INT-1486 bounds the RISK FLAG only: the flag is kept on the persisted raw
# envelope and the run's summary says a flag arrived and a decision is awaited —
# no hold, no notification, none of the three options taken (step 9).
---

**Intent.** Shape D, built for a consumer that exists — a kiosk network with its own
duplicate semantics and return handling. The guard pipeline **in the order that is the
design**: **authenticate** the caller (credential header + source allowlist) **before the body
is read** → **dedupe** on the declared key — the kiosk's id **composite with the reversal
marker**, because a reversal carries the **same id** as the payment it reverses → **reply at
the declared position** — the kiosk requires **`409` for a duplicate**, which cannot be decided
after the reply has gone, so `respond_after = dedupe` and only the posting stays behind it →
**persist raw** → **process async** through **payments' one inbound write path**. The payment
records channel **`KIOSK`** and the kiosk's reference, so a report separates counter takings
from kiosk takings. And **a payment is always accepted** — a lesson a defect in August taught
this product, which turned out to satisfy the requirement the kiosk's specification marks
CRITICAL.

**Upstream leaves (handoff in).** Brazos Bend's `payments_kiosk` connection: **one card, one
credential** (`X-Kiosk-Key`, hint `••••K1OS`), **three operations** — *Account lookup*
(`respond_after = authenticate`), *Payments* and *Returns* (`respond_after = dedupe`, status
map `{ok: 200, duplicate: 409}`); allowlist `198.51.100.0/24, 203.0.113.7`. Tender mapping
rows (J54's shape): `CASH → Cash`, `CHECK → Cheque`, `ACHCHECK → Bank transfer`,
`ACHSAVINGS → Bank transfer`, `CREDIT → Card`; `CASHAPP`, `CRYPTO`, `DRIVEUP` **unmapped**.
Reversal-reason rows `R01 → nsf`; `R02` unmapped (`OQ-INT-1487`). **The five accounts they
will ask for, seeded before the conversation, not during it:** `ACC-1048 · $142.18` (a
residential balance) · `ACC-2207 · −$18.50` (carrying a credit) · `ACC-9999` (unknown) ·
`ACC-3310` (payments disallowed) · `ACC-5002` (commercial). `payments.channel ∈ {KIOSK,
COUNTER, PORTAL, OTHER}` (default `COUNTER`) and `payments.external_ref` from payments'
migration N1. Callers `198.51.100.20` (allowed), `203.0.113.99` (not). Lone Star Ridge with
an account `ACC-1048` of its own. Clock **3 Sep 2026**.

**This journey leaves (handoff out).** ONE `payment` row on `ACC-1048` — `42.1000`, method
*Cash*, `channel = KIOSK`, `external_ref = K-88231`, cleared, allocated by the tenant's rule
(payments' `record_payment`, `SOURCE_WEBHOOK`), with its **balanced pair** written by the
posting service and its audit row; ONE **reversal row** (new, reason `nsf`); **three** inbound
run rows (*They send us payments* · *They send us a return* · the refused replay) plus the
lookups; the **raw envelopes** persisted (`payments.PaymentWebhookEvent`); `DRIVEUP` and
`CASHAPP` as red rows on S143; the payments report for 3 Sep with **counter and kiosk takings
on separate lines**.

**Fixture.** Payload `K-88231 · $42.10 · CASH · ACC-1048`; the identical replay; return
payload `K-88231 · RETURN · R01`; a payment naming channel `DRIVEUP`; a payment naming tender
`CASHAPP`; a two-payment batch whose second violates a constraint (PG). Frames `44.1` (the
kiosk detail — *Account lookup · they ask what is owed · They call us · Answering* / *Payments
· money taken at a machine · They send · Accepting* / *Returns · a payment bounced · They
send · Nothing yet*), `81.1` (*Payments · today, 09:41 · Accepting · 93 sent to us · 91
recorded · 0 refused · 2 already had* — *Two payments arrived twice — the kiosk retried after
a timeout. We answered both with a refusal that says so*), `45.1` (mappings, *2 of their 14
values are not mapped*).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (order · rows · status · books · isolation) | Rule |
|---|---|---|---|---|
| 1 | The kiosk — `Account lookup` for `ACC-1048`; then for `ACC-9999` | `ACC-1048`: balance **`$142.18`** in the **declared shape** (`respond_after = authenticate`). `ACC-9999` (unknown): **the declared answer — `200` with `status: not_found`**, the kiosk's contract — **not a 404** | The five accounts were seeded **before** the conversation, not during it. `ACC-2207` answers `−$18.50` (a credit); `ACC-3310` answers its declared status; `ACC-5002` the commercial balance | `US-INT-044` TC-7 · BR-INT-045 |
| 2 | The kiosk posts **`K-88231 · $42.10 · CASH`** for `ACC-1048` from `198.51.100.20` | **authenticate** (header + allowlist) → **dedupe** on `kiosk · K-88231 · payment` → **`200`** → the **raw envelope persisted** (`PaymentWebhookEvent`) → **async** `integration.inbound_process` → `record_payment` with **`channel = KIOSK`, `external_ref = K-88231`**. The payment is **on the account with no clerk keying it**, cleared and allocated by the tenant's rule | `42.1000` stored, `$42.10` displayed. Payments writes **no** journal lines — the posting service writes ONE balanced pair; ONE audit row. ONE inbound run row under the heading ***They send us payments***. **Integrations wrote no payment** — payments' one write path did, reusing `webhooks.py`'s guards (`PaymentWebhookEvent` UNIQUE, `uq_payments_webhook_key`) | BR-INT-021 · BR-INT-053 · BR-PAY-003 · hard rules 5 · 6 · 7 |
| 3 | **the exit test, first half** — the kiosk **replays** the identical notification | **`409`** — answered at `respond_after = dedupe`, **before anything is posted**; **exactly one** payment on `ACC-1048`; the run row shows the replay as a **refused duplicate**; frame `81.1`'s *already had* is the `skipped` count **with its sentence** | The status map `{ok: 200, duplicate: 409}` is a **declared value** — **the adapter contains neither number**; the same duplicate on a generic webhook would be answered `200` from its own declared map. *A duplicate must be answered, not ignored, or their machine keeps trying* | BR-INT-030 · BR-INT-045 · BR-INT-020 · `US-INT-044` TC-2 |
| 4 | **the exit test, second half** — a **return** arrives carrying **the same id** `K-88231 · RETURN · R01` | **Not a duplicate** — the composite key `kiosk · K-88231 · return` differs by the **reversal marker**. A **reversal row** is written (**a new row**, hard rule 4), reason **`nsf`** from the mapping row (`R01 → not enough money`), the raw `R01` kept on the payload; the payment is reversed and the bill it paid re-opens at **its own** due date | Their id alone is **not a sufficient key**. ONE inbound run row under ***They send us a return***. A return carrying **`R02`** would record `other`, keep the raw code, go red on S143, and the chooser raises `NotImplementedError("OQ-INT-1487")` (J51 step 7) | BR-INT-020 · hard rule 4 · `US-INT-044` TC-3 |
| 5 | **demonstrated on a real captured payload** | Steps 2–4 replayed from the redacted capture in `fixtures/payments_kiosk/`, not a hand-written body | The phase-5 exit test is a demonstration, not an opinion | `CR-069` §12 |
| 6 | **negative · authenticate before the body** — a call from `203.0.113.99`; a wrong `X-Kiosk-Key` from an allowlisted address; a manifest declaring a reply **before** `authenticate` | Outside the allowlist: **refused before the body is read — the body is never parsed**, and the refusal **reveals nothing about any account**. Wrong key: refused at `authenticate`, nothing persisted beyond the refusal record. The manifest: **refused at load, not at run time** — the reply may never sit before authentication | This provider carries **no signature** — the header and the allowlist are the authentication; a replay window is enforced | BR-INT-044 · BR-INT-021 · BR-INT-030 · `US-INT-044` TC-4/5/6 |
| 7 | **unknown values degrade inbound** — a payment naming channel `DRIVEUP`; a payment naming tender `CASHAPP` | Both **accepted**: `channel = OTHER`; tender **Other**; **a red row for each on S143** (frame `45.1` — *not set — will record as Other · Map it*), *last seen* stamped; **the money is not stopped** — refusing a real payment over a vocabulary is worse than misfiling it | Priya maps `CASHAPP → Cash` on S143 → green; `ACHCHECK → Cash` beside the existing `ACHCHECK → Bank transfer` → **refused by the UNIQUE on the external side**; `local_value = "Bitcoin"` → refused *not one of our values*. Their list can grow without warning **and it stops nothing** | BR-INT-031 · BR-INT-032 · `US-INT-037` TC-1/2/4/5 |
| 8 | **one card, one credential, three things it does** (frame `44.1`) | S8: **one** `payments_kiosk` card with three operation rows — *Account lookup · Answering · 2 min ago* / *Payments · Accepting · 18 min ago* / *Returns · Nothing yet* — **no aggregate word**; **one** credential row. S142 groups runs under three plain headings: ***They send us payments · They ask us about an account · They send us a return*** — never a quadrant name like `DELIVER` or `SERVE` | When *Returns* fails and *Payments* works, only the *Returns* row changes. A manifest with `operations = ()` is refused at load | BR-INT-028 · BR-INT-037 · `US-INT-018` TC-1/2/5 |
| 9 | **boundary · `OQ-INT-1486`** — a payment arrives carrying the kiosk network's **risk flag** | The payment is **accepted and recorded** (a payment is always accepted); the flag is **kept on the persisted raw envelope**; the run's summary says **a flag arrived and a decision is awaited** — **no hold, no notification, none of the three options taken** | The options are the PO's — show the flag for a clerk · hold allocation until cleared · notify the utility. **A lane may not choose** | BR-PAY-036 · `OQ-INT-1486` |
| 10 | **🔒 PostgreSQL · law 14** — a batch of two kiosk payments, the second refused by a constraint | The first **commits**; the second is **recorded refused** — a **savepoint per item**; the run's counts reconcile | The naive `try/except IntegrityError: continue` poisons the transaction and loses both — recorded as the red run (J52's shape) | law 14 · `US-INT-044` TC-9 |
| 11 | **tenant isolation** | The kiosk credential scoped to **Brazos Bend** posts for **Lone Star Ridge's** `ACC-1048` → answered **in the declared *not found* way**; **nothing written** to Lone Star Ridge. Lone Star Ridge's own kiosk card shows three operation rows all *Not set up* with no Brazos Bend last-run time | `app.tenant_id` from the credential's tenant, never from the payload; RLS `FORCE` | hard rule 1 · `US-INT-044` TC-10 · `US-INT-018` TC-6 |
| 12 | **the report** — payments for 3 Sep | **Counter takings and kiosk takings on separate lines by channel** — `KIOSK` `$42.10` less the `−$42.10` reversal; `COUNTER` the day's counter receipts | `C31`: the channel and the kiosk's own reference make the separation possible | BR-INT-053 · `US-INT-044` TC-11 |
| 13 | **INVARIANCE** | `$42.10` applied exactly once; the replay answered `409` before any posting; the return reversed instead of being refused; the raw envelope preceded every process step; the adapter held no status number; no payment was refused over a vocabulary; every money action wrote an audit row and a balanced pair; nothing was updated or deleted — the reversal was a new row | The door reused `payments/webhooks.py`'s guards — **no second inbound path** was minted | BR-INT-021 · BR-INT-045 · hard rules 4 · 5 · 6 · 7 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | What a **risk-flagged** payment does afterwards | `OQ-INT-1486` — the flag is kept; nothing acts on it |
| b | What `R02` maps to | `OQ-INT-1487` — the four signed reversal reasons are not widened |
| c | The **card-processor** door — a charge that times out reading *we do not know*, a key generated before the charge leaves, the fee line, chargebacks | `OQ-INT-1476` (unread — does the processor honour our idempotency key), `OQ-INT-1478` (signature or shared code), `OQ-INT-1473`/`1477` (the fee and chargeback halves), `OQ-INT-1474`/`1475`. Wave O builds the boundary; `T-9` does not start before `OQ-INT-1476` is read |
