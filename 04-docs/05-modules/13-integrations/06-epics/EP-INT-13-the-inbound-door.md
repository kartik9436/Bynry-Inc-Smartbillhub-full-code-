# EP-INT-13 — The inbound door, the third outcome, and the customer's consent

**Module:** integrations (+ payments for the one inbound write path) · **Wave:** phase 5 · **Screens:** S142 · the payment's own detail (payments module) · S145 consent (staff) · S146 consent (customer) · **Status:** draft (`CR-069`, 2026-09-03) — `US-INT-044` ready · `US-INT-045` contingent on `OQ-INT-1476` · `US-INT-046` conditional on `OQ-INT-1482`

## Scope

**In:** shape D — *"only when payment rails are actually being built — and they now are."* A kiosk network's specification has arrived with its duplicate semantics and its return handling, so the door is built for a consumer that exists: authenticate the caller before trusting the body, answer as soon as we know whether we have seen it before, persist raw, process asynchronously through **payments' one inbound write path** (`BR-INT-021`, `BR-INT-030`, `BR-INT-045`). The `indeterminate` outcome and the partner-issued idempotency key for a charge (`BR-INT-052`). The customer's consent — scoped, expiring, revocable, checked on every request (`BR-INT-036`).

**Out:** card refunds (`OQ-INT-1474`), autopay intentions being consumed (`OQ-INT-1475`), the derived-fee ruling whose premise moved (`OQ-INT-1473` — goes back to the PO, not reversed here), and the settlement file as reconciliation's third input (touches `OQ-144`, does not change it).

⚠ **THE KIOSK HALF IS NOT CONTINGENT; THE CARD-PROCESSOR HALF IS.** `T-9` (ten tasks) **must not start until `OQ-INT-1476` is read** — whether the processor accepts our idempotency key decides whether a timed-out charge can ever be retried.

⚠ **`payments/webhooks.py` IS NO LONGER A STUB.** 577 lines, built 2026-09-03 as `CR-060` `C21`, 15 tests, idempotent on `webhook_key`, savepoint proved on PostgreSQL. **`T-9.04` may be largely done — verify before building**, and this epic's door **reuses** that handler's three guards rather than minting a second inbound path.

**Exit test of phase 5:** a replayed notification is recognised and **applied exactly once**, answered with the conflict status the provider expects — and **a reversal carrying the same identifier as the payment it reverses is not mistaken for a duplicate of it**. Demonstrated by replaying a real captured payload.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S145 · consents (staff) | customer · grantee | state (active · expired · revoked) | granted desc | granted · expires | customer · allowed (grantee) · what · how much history · until · state | revoke (danger) · open customer | — | — |

## Stories

---
id: US-INT-044
epic: EP-INT-13
module: integrations
screens: [S142, S143]
wave: 5
status: ready
blocked_by: []
depends_on: [US-INT-013, US-INT-018, US-INT-020, US-INT-037, US-PAY-001]
journeys: [J59]
rules: [BR-INT-020, BR-INT-021, BR-INT-030, BR-INT-044, BR-INT-045, BR-INT-053, BR-PAY-003, BR-PAY-036]
golden_tests: []
finance_calc: none
---
### US-INT-044 — The inbound door: a kiosk payment appears on the account by itself, a replay is applied exactly once and answered 409, and a return is not mistaken for a duplicate (C3, C6, C31)

**1 · Details** — As **a utility**, I want **a payment taken at a kiosk to appear on the customer's account by itself — once — and a return to reverse it** — so that **counter and kiosk takings can be told apart and no notification is ever applied twice**.

`POST /integrations/webhooks/{key}` — the DeliverRunner's door, one per shape-D connector. The guard pipeline in the order that is the design: **authenticate** the caller (the kiosk's credential header + the source-IP allowlist `BR-INT-044` — this provider carries no signature) → **dedupe** on the declared key — the kiosk's id **composite with the reversal marker**, because *"their id alone is not a sufficient key: a reversal carries the same one as the payment it reverses"* → **reply**, at the declared position: the kiosk requires **`409` for a duplicate**, *"which cannot be decided after the reply has gone"*, so `respond_after = dedupe` and only the posting stays behind it (`BR-INT-030`; the status map `{ok: 200, duplicate: 409}` is a declared value and the adapter contains neither number, `BR-INT-045`) → **persist raw** → **process async** through `apps.payments.services.record_payment`, **the one inbound write path**, reusing `payments/webhooks.py`'s guards. **`C31`:** the payment records channel **`KIOSK`** and the kiosk's own reference, so a report separates counter takings from kiosk takings; an unrecognised channel records as *Other* and stops nothing (`BR-INT-031`). The **Account lookup** operation answers the kiosk's question about an account with the balance — and an unknown account answers **in the operation's declared way, which may not be 404**. *"The requirement the specification flags as CRITICAL turned out to be already satisfied by the code, because a defect in August taught this product the lesson it depends on"* — a payment is ALWAYS accepted (`BR-PAY-036`).

Entry: the kiosk calls us. Exit: one payment row (payments'), one inbound run row, the raw envelope persisted.

⚠ **SPLIT AND HALF-BUILT — 2026-09-06 (`BR-INT-058`, PO ruling; `OQ-INT-1729` option (a); `CR-069` §20.4 wave `N`). READ THIS BEFORE BUILDING FROM THE PARAGRAPH ABOVE, WHICH DESCRIBES THE WHOLE STORY AND NOT WHAT IS IN THE PRODUCT.** The exit line's *one payment row* is **NOT built and is not this module's**. Integrations KEEPS and has BUILT: **authenticate** (the `X-Kiosk-Key` header and the source allowlist, before the body is read), **dedupe** on the composite key, **reply** with the manifest's number, **persist raw** — `apps/integrations/inbound.py`, live at `POST /api/{utility}/integrations/inbound/{key}/{operation}`. Runbooks TAKES, and none of it is built: `record_payment` with channel `KIOSK`, the reversal row a return produces, `DRIVEUP → OTHER`, and showing the risk flag to a clerk. **So today's exit is: one inbound run row, the raw envelope persisted, and ZERO payments** — `inbound.runbooks_apply()` is the named seam and `test_us_int_044_inbound_door.py::test_tc_boundary_the_door_applies_nothing` asserts the absence, so this paragraph cannot go stale silently. **TC-8 and TC-11 below are on the Runbooks side** and are not built; TC-1's *one payment row* reads *one delivery row* until it is.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-021` | Authenticate before the body; persist raw; reply before the work (refined: reply at the declared position) | PROPOSED |
| `BR-INT-030` | `respond_after` is declared; never before `authenticate`; kiosk = `dedupe` | PROPOSED — `C6` |
| `BR-INT-045` | Status map declared; adapter has no status number | PROPOSED — `C3` |
| `BR-INT-020` | Key = provider event id composite with the reversal marker | PROPOSED |
| `BR-INT-044` | Allowlist; refusal reveals nothing | PROPOSED — `C5` |
| `BR-INT-053` | Channel `KIOSK` + kiosk reference on the payment | PROPOSED — `C31` |
| `BR-PAY-003` · `BR-PAY-036` | Dedupe on `webhook_key` UNIQUE; a payment is always accepted | CONFIRMED |
| CLAUDE.md hard rule 6 · law 14 | Inbound webhooks idempotent; per-row error handling proved on PostgreSQL | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Kiosk posts payment `K-88231 · $42.10 · ACC-1048 · CASH` | `200`; raw envelope persisted first; one payment row on `ACC-1048`, channel **KIOSK**, reference `K-88231`, cleared and allocated; one inbound run row (doc TC-INT-15) |
| TC-2 | The same notification replayed | **`409`** — returned **before** any posting; **exactly one** payment; the run row shows the replay as a refused duplicate (doc TC-INT-28) |
| TC-3 · **the exit test** | A **return** arrives carrying the same id `K-88231` | **Not** a duplicate — the composite key differs by the reversal marker; a reversal row is written (a new row, hard rule 4); the payment's reversal reason from the mapping rows |
| TC-4 · **negative** | A call from `203.0.113.99`, outside the allowlist | Refused before the body is read; the body is never parsed; the refusal reveals nothing about any account |
| TC-5 · **negative** | Wrong credential header from an allowlisted address | Refused at `authenticate`; nothing persisted beyond the refusal record |
| TC-6 · **load-time** | A manifest declaring `respond_after = authenticate`'s predecessor | Refused at load — the reply may never sit before authentication |
| TC-7 | Account lookup for `ACC-1048` | Balance `$142.18` in the declared shape; for an unknown account, the declared answer (`200` with `status: not_found` — the kiosk's contract), **not** a 404 |
| TC-8 | Payment naming channel `DRIVEUP` (unmapped) | Recorded as *Other*; a red row on S143; the payment is not stopped |
| TC-9 · **PG** | Two kiosk payments in one batch, the second refused by a constraint | The first commits; the second is recorded refused — a savepoint per item (law 14) |
| TC-10 · **tenant isolation** | A kiosk credential scoped to Brazos Bend posts for a Lone Star Ridge account | Answered in the declared *not found* way; nothing written to Lone Star Ridge |
| TC-11 · **report** | Payments report for 3 Sep | Counter takings and kiosk takings on separate lines by channel |

**4 · Test Data** — *The five they will ask for* (seeded before the conversation, not during it): a residential account with a balance (`ACC-1048 · $142.18`), one carrying a credit (`ACC-2207 · −$18.50`), an unknown one (`ACC-9999`), one with payments disallowed (`ACC-3310`), a commercial one (`ACC-5002`). Kiosk credential header `X-Kiosk-Key` (`••••K1OS`); allowlist `198.51.100.0/24, 203.0.113.7`; payload `K-88231 · $42.10 · CASH`; return payload `K-88231 · RETURN · R01`; a real captured payload for the demonstration.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| raw envelope | run detail | `BR-INT-021` | `payments.PaymentWebhookEvent` (exists, `payments/0020`) + inbound run artifact | jsonb | integration | persisted before processing |
| composite key | — | `BR-INT-020` (D) | `payments.webhook_key` UNIQUE (exists) — `kiosk · K-88231 · payment` vs `… · return` | text | system-derived | reversal marker in the key |
| `respond_after` · status map | — | `C6` · `C3` | manifest per operation | enum / map | reference-data | `dedupe`; `{ok: 200, duplicate: 409}` |
| channel · kiosk reference | payment detail · report | `C31` | `payments.channel` (`KIOSK · COUNTER · PORTAL · OTHER`) · `payments.external_ref` | enum/text | integration | unknown channel → `OTHER` |
| allowlist · credential header | S141 | `C5` · `C2` | `integration_connection.config.allowlist` · `integration_credential` | CIDR / encrypted | user-input | — |

**6 · Acceptance**
- Given a kiosk payment, then it is on the account with no clerk keying it, marked with its channel and reference.
- Given the same notification twice, then one payment and a 409 before anything is posted.
- Given a return with the same id, then it reverses and is not refused — demonstrated on a real captured payload.

**7 · Finance Calculation** — N/A — recording and allocation are payments' (`US-PAY-001`); the ledger legs are `BR-PAY-004`'s. ⚠ The design's warning stands for the card half: *a receipt that debits a clearing account which reconciliation never credits will silently unbalance the books — both legs ship together or neither ships.*

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1486` | What happens to a payment the kiosk network flags as risky — show the flag, hold allocation until a clerk clears it, or notify? A payment is always accepted (`BR-PAY-036`); the question is what the flag does afterwards | The risk-flag handling only (`T-6` group); recording the payment is not blocked | PO | ⚠ **CLOSED 2026-09-04 — option (a), accept and SHOW the flag.** This table said **OPEN** until 2026-09-06, two days after the ruling, which is `DEF-WRK-4030`'s shape: the register's status column moved and the document a lane actually builds from did not. **Allocation is NOT held and no notification fires.** The half that is BUILT (2026-09-06, wave `N`) is that the flag arrives intact on the persisted raw envelope and provokes nothing; the clerk-visible half needs a payment, and `record_payment` is Runbooks' under `BR-INT-058`. |

(Whether the nightly settlement file's chargeback half exists — `OQ-INT-1477` — and what the webhook *code* is — `OQ-INT-1478` — are the card processor's, `US-INT-045`.)

---
id: US-INT-045
epic: EP-INT-13
module: integrations
screens: [S142]
wave: 5
status: blocked
blocked_by: [OQ-INT-1476, OQ-INT-1478]
depends_on: [US-INT-044, US-INT-020, US-INT-011]
journeys: []
rules: [BR-INT-052, BR-INT-018, BR-INT-020]
golden_tests: []
finance_calc: none
---
### US-INT-045 — Indeterminate — a third outcome — and the idempotency key generated before the charge leaves (C26, C27) 🔒 ⚠ contingent

**1 · Details** — As **a billing clerk**, I want **a charge that times out to read *we do not know* — not failed — with a button to go and ask the processor, and a blind retry refused** — so that **a debit that already left a customer's account is never taken twice, and a zero is never claimed by anyone**.

`C26`: a charge that times out is neither succeeded nor failed, and a blind retry charges the customer twice. **`indeterminate`** is the seventh outcome (`BR-INT-052`): S142 and the payment's own detail read **we do not know**, with **Ask the processor** — a companion outcome query — and the retry button is **refused**. `C27`: the idempotency key for a charge is **generated and stored before the request leaves**, and the same key is sent on every retry. ⚠ **WHETHER THE PROCESSOR HONOURS THAT KEY IS `OQ-INT-1476` — STILL UNREAD** (`R-8 q1`): *"if yes, a timeout is recoverable by replaying the same key; if no, every timeout needs an outcome query and the charge operation needs a companion."* Until read, the operation is designed **with** the companion query, and `T-9` does not start. The card page is the processor's (`browser, credentialed` — PO *"they are on Spruce page"*), so the card number never reaches our servers. The webhook carries *"some code"* (PO) — **which** code, a signature over the body or a shared secret in the payload, is `OQ-INT-1478` and decides whether `payments.webhook_key` as provisioned suffices. The nightly settlement report exists (PO *"Yes Night ly batch"*); **whether it breaks out chargebacks per transaction is `OQ-INT-1477`**, and `OQ-INT-1473` — the derived-fee ruling of 2026-08-12 whose premise that changed — goes back to the PO with its figure and is not reversed here.

🔒 **Sensitive path** — idempotency keys and webhook keys on the money path. `HUMAN-REVIEW-PENDING`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-052` | `indeterminate` is a third outcome; key before the call; blind retry refused | PROPOSED — `C26`, `C27`; 🔒; contingent `OQ-INT-1476` |
| `BR-INT-018` | Never rounded to succeeded or failed | PROPOSED |
| `BR-INT-020` | Key shape for the charge — ours, generated before the call | PROPOSED |
| `OQ-160` | Fee derived from shortfall — **CLOSED, premise changed → `OQ-INT-1473`**; not reversed here | relied on as written until the PO rules again |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | A charge of `$142.18` times out after 30 s | Outcome **`indeterminate`**; the screen reads **we do not know** with **Ask the processor**; no `$0.00` anywhere; the S8 panel shows attention |
| TC-2 · **negative** | Press **Retry** on TC-1 | **Refused** — *ask the processor first* (≤ 6 words) |
| TC-3 | Press **Ask the processor**; the outcome query says *captured* | The payment is recorded once with the processor's reference; the run becomes `succeeded` by a **new** row (append-only) |
| TC-4 | The outcome query says *not found* | The run becomes `failed` by a new row; retry is now allowed and **sends the same key** stored before the first attempt |
| TC-5 · **key ordering** | Inspect the store before the first request leaves | The key row exists **before** the HTTP call (asserted by ordering on the fixture) |
| TC-6 · **boundary** | Start the charge operation with `OQ-INT-1476` open | `NotImplementedError("OQ-INT-1476")` at the charge call; the companion query and the outcome vocabulary are testable against a fixture |
| TC-7 · **tenant isolation** | Two tenants' charges | Keys carry the tenant; a processor reference from one tenant never resolves on the other |

**4 · Test Data** — `payments_card` (W7) sandbox connection; charge `$142.18` on `ACC-1048`; fixtures *timeout*, *captured*, *not found*; a generated key `chg_brazos_9f2e…`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `outcome = indeterminate` | S142 · payment detail | `C26` | `integration_run.outcome` | enum | system-derived | never succeeded/failed by inference |
| our idempotency key | — | `C27` | `payments` idempotency record, written **before** the call | text | system-derived | same key on every retry |
| companion outcome query | S142 button | `C26` | manifest operation `charge_status` | operation | reference-data | required while `OQ-INT-1476` is open |
| `executor = browser_credentialed` | — | PO 2026-09-03 | manifest | enum | reference-data | card number never reaches our servers |

**6 · Acceptance**
- Given a timed-out charge, then the clerk reads *we do not know*, cannot blindly retry, and can ask the processor.
- Given the answer, then the payment is recorded once or the charge is retried with the same key.

**7 · Finance Calculation** — N/A here; the fee line and the chargeback separation are `OQ-INT-1473`'s and `OQ-INT-1477`'s — a card day taking `$5,120.40` against a bank credit of `$4,972.90` gives a `$147.50` gap that a `$137.50` fee plus a `$10.00` chargeback also gives.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1476` | Does the processor accept an idempotency key we supply and replay it rather than charging again? | Every `T-9` task; the charge call | Processor documentation (a reading) → PO | OPEN — unread |
| `OQ-INT-1477` | Does the nightly settlement file break out **chargebacks** per transaction, not only fees? | Separating the `$137.50 + $10.00` case | Processor documentation → PO | OPEN — half read |
| `OQ-INT-1478` | Is the webhook *code* a cryptographic signature over the body or a shared secret in the payload? | Whether `payments.webhook_key` as provisioned suffices | Processor documentation → PO | OPEN — answered in part |
| `OQ-INT-1473` | The derived-fee ruling (`OQ-160`, 2026-08-12) — its premise changed; does it stand? | `T-9.05` — the fee line | PO (finance) | OPEN — premise changed |
| `OQ-INT-1474` | Do card refunds open with the rails, or later? | `T-9.06` | PO | OPEN |
| `OQ-INT-1475` | When charging arrives, are recorded autopay intentions consumed as they stand? | `T-9.08` | PO | OPEN |

---
id: US-INT-046
epic: EP-INT-13
module: integrations
screens: [S145, S146]
wave: 5
status: deferred            # OQ-INT-1482 ruled 2026-09-04 — customer-authorised third-party access is OUT OF SCOPE, not later
blocked_by: []
depends_on: [US-INT-014, US-INT-041, US-INT-020]
journeys: [J58]
rules: [BR-INT-036, BR-INT-035]
golden_tests: []
finance_calc: none
---
### US-INT-046 — A customer letting someone else see their usage: a consent that is scoped, expires, can be stopped, and is checked on every request (C9) ⚠ conditional

**1 · Details** — As **a customer**, I want **to allow a company I trust to collect my meter readings, choose how much and for how long, and stop it whenever I like** — so that **the installer's very next request after I stop it is refused — not their next nightly collection**.

*"Nothing in this product has ever held a permission that its owner can revoke, and a revocation that takes effect on the next scheduled run rather than the next request is the classic way it is built wrong."* `integration_consent`: `account_id`, `grantee`, `scope` (what, and how much history — *twelve months of usage*), `granted_at`, `granted_by` (**the customer, not a member of staff**), `expires_at`, `revoked_at` / `revoked_by` (set, never deleted — *who could see my data last year* is a question a customer is entitled to ask). **Checked on every request** by the SERVE runner. **S146** — the customer's own view (grant, see, stop; drawn in the portal when built, where it takes the next `CWP` id); **S145** — the staff view, *because the customer will ring up rather than log in*: a clerk revokes on the customer's behalf and the ended row stays on the record. It is a consent feature wearing a standard's name (Green Button's), and **not claiming the standard** (`BR-INT-053`).

⚠ **CONDITIONAL ON `OQ-INT-1482` — whether authorised third-party data access is in scope at all. A market decision.** Nothing here is built until it is ruled; the table is in the brief (`US-INT-014`) so that, if it is, this is *"rung 5 rather than rung 1"* already paid for. Being an OAuth **server** — issuing tokens to strangers on a customer's say-so — is a larger thing than the OAuth-broker refusal of design §1.11 ever considered, and does not inherit that refusal.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-036` | Scoped, expiring, revocable, kept after revocation, checked on every request | **OPEN → `OQ-INT-1482`** |
| `BR-INT-035` | The grantee's reads are recorded like any partner's | PROPOSED |
| `BR-INT-053` | The standard is not claimed | PROPOSED |
| B14 rule 6 | *Stop sharing* is a danger-tier commit | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | The customer allows *SunPath Installers* twelve months of usage on S146 | A consent row `granted_by = the customer`, `scope = {usage, months: 12}`, `expires_at = +12 months`; the installer's first read succeeds and is recorded |
| TC-2 | Two months later the customer rings; Priya presses **Stop sharing** on S145 | `revoked_at` set, `revoked_by = Priya`; **the installer's very next request is refused** — one second later, not at the next nightly collection — and the run record says why (doc TC-INT-36, J58) |
| TC-3 | The customer asks *who could see my data last year* | S146 lists the ended consent with its dates; the row was never deleted |
| TC-4 · **negative** | The installer requests bills, not usage | Refused — outside the granted scope |
| TC-5 · **negative** | A request one second after `expires_at` | Refused; no run |
| TC-6 · **boundary** | Any consent write with `OQ-INT-1482` open | `NotImplementedError("OQ-INT-1482")`; S145/S146 are not mounted |
| TC-7 · **tenant isolation** | A grantee key valid for a Brazos Bend customer used against Lone Star Ridge | Unknown, in the declared way |

**4 · Test Data** — Customer *Maria Alvarez*, `ACC-1048`; grantee *SunPath Installers*; scope twelve months of water usage; granted 2026-09-03; revoked 2026-11-03 by Priya Menon; a request at 2026-11-03 09:00:01. ⚠ **Name collision, recorded not resolved (2026-09-03, `DEF-INT-3615`):** *Maria Alvarez* is the portal's fixture customer at **Pine Hill** on `ACC-10432-A` (`1408 Elm St · A`, all eighteen journeys `J30`–`J47`), and this story makes her a **Brazos Bend** customer on `ACC-1048`. Two tenants cannot share one fixture person without a spec that reads one tenant's name asserting against the other's. This story is blocked on `OQ-INT-1482`; the lane that builds it picks ONE name — the portal's use is the older and wider, so the choice that moves least is a different Brazos Bend customer here, written once in this row — and records the choice as a decision-log line, not as a guess in a test.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `grantee` · `scope` · `expires_at` | S146 · S145 | `C9` · §2.8.1 | `integration_consent` | text/jsonb/ts | customer-input | `granted_by` is the customer |
| `revoked_at` · `revoked_by` | S145 · S146 | `BR-INT-036` | `integration_consent` | ts/uuid | user-input (customer or staff) | set, never deleted |
| check on every request | — | `BR-INT-036` | SERVE runner reads the consent before each page | — | system-derived | revocation effective immediately |

**6 · Acceptance**
- Given a consent, then the grantee reads within its scope and time; given it is stopped, then the next request fails and the record remains.
- Given the ruling is open, then nothing of this is mounted.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1482` | Is authorised third-party data access in scope at all? | This whole story | PO (market) | OPEN |
| `OQ-INT-1481` | Who may authorise a partner to read | The grantee's read surface | PO | OPEN |
