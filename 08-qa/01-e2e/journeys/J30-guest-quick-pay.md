# J30 — Guest pays a bill they are holding (two facts off the paper, a masked name, `$142.18`, a reference — and no account)

---
id: J30
tier: 2
rules: [BR-CWP-018, BR-CWP-019, BR-CWP-020, BR-CWP-021, BR-CWP-022, BR-CWP-023, BR-CWP-025, BR-CWP-026, BR-CWP-028, BR-CWP-029, BR-CWP-040, BR-CWP-056, BR-CWP-057, BR-CWP-058, BR-CWP-059, BR-CWP-061, BR-CWP-093, BR-CWP-007]
stories: [US-CWP-001, US-CWP-002, US-CWP-003, US-CWP-004, US-CWP-005, US-CWP-006, US-CWP-022, US-CWP-045, US-CWP-046, US-CWP-069]
# Wiring: every story above cites `J30` in its own `journeys:` frontmatter
# (04-docs/05-modules/15-portal/06-epics/). The activation authority is the
# GENERATED index (10-scripts/07-e2e-wiring-index.py) — NOT ACTIVATED: no
# `07-frontend/e2e/J30.spec.ts` exists and none may until rails land (release 5).
# ⚠ RELEASE 5, NOT 1. Every screen in this journey ships in release 1 HELD —
# the Pay control in its normal place, disabled, carrying its reason (CR-068 R3).
# Steps 1–5, 9 and 11 are runnable in release 1; steps 6–8 and 10 need rails.
---

**Intent.** The widest door in the portal, walked by somebody who is not a customer of
anything: a person holding a paper bill. Two facts printed on it find the bill; the screen
tells them the **amount** and a **masked name** and nothing else about the account; the
payment lands, is allocated by the utility's own rule, is receipted, and ends on a
**reference** — and at the end **no account exists** and nothing about the customer record
has changed. This is `BR-CWP-018` made concrete: *a bill number proves someone is holding
the bill; it does not prove who they are.*

**What this journey is really proving:** that a public form can **create work and take
money against a bill** while never being able to **change an account** (`BR-CWP-026`), and
that the guard in front of it — sixty a minute, five wrong pairs then fifteen minutes — is
the reason a short sequential bill number is safe to accept from a stranger.

**Upstream leaves (handoff in).** Tenant `pine-hill` (*Pine Hill Water & Power*, brand
`#EC3013`) is live with `quick_pay_enabled = true`. Customer **Maria Alvarez**, account
`ACC-10432-A` at `1408 Elm St · A`, service postcode `78702`. An **issued** bill
`BL-2608-0141`, period 1–31 Aug 2026, issued 30 Aug, due 14 Sep, total `$142.18`, nothing
allocated → owing `$142.18`. A paid bill `BL-2607-0139` (`$138.44`, owing `$0.00`). A
corrected pair `BL-2606-0137` (`$154.90`) → replaced by `BL-2606-0147` (`$129.02`). Second
tenant `oak-ridge`. Today is **2 Sep 2026** (the blueprint's clock).

**This journey leaves (handoff out).** ONE `payment` row (`$142.18`, allocated to
`BL-2608-0141` by the tenant's rule, `portal_credential_id` NULL, channel guest), ONE
balanced journal pair written by the posting service, ONE `audit_log` row naming the guest
channel, ONE receipt `document`, reference `PAY-26-08841` — and **zero** `portal_credential`
rows, **zero** changes to `customer`, `account`, `customer_contact`. `BL-2608-0141` reads
owing `$0.00` on `CWP-027`/`CWP-041` for J36.

**Fixture.** Correct pair `BL-2608-0141` + `78702`. Wrong pairs `BL-2608-0142`…`0146` +
`78702`. Source address `198.51.100.10`; second address `203.0.113.7`. Card `Visa
••••8812 · expires 11/27`. Receipt email `d.okafor@example.com` (⚠ deliberately **not** the
customer's — a guest may be a neighbour). Settlement `STL-2609-0031`, idempotency key
`pay_26_08841`; replay = the identical body; reversal `STL-2609-0032` carrying the same
`pay_26_08841` with a reversal flag. Screens `CWP-001` → `CWP-002` → `CWP-003` → `CWP-004`
(`wireframes/CWP-001…004.png`, layouts in `08-screen-layouts.md`).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (record · queue · books · audit) | Rule |
|---|---|---|---|---|
| 1 | Guest opens `/pine-hill` (`CWP-001`) | Six `ErrandCard`s, *Pay a bill* among them, **reachable in one click with no password field**. `app.tenant_id` set from the first path segment before any content query | No session row, no credential row. With `quick_pay_enabled = false` the card is **absent** and `POST /public/bills/lookup` refuses — not a 200 with an empty body | BR-CWP-007 · BR-CWP-093 |
| 2 | `CWP-002` — types `BL-2608-0141` + `78702`, *Continue →* | Step 2 opens. The response carries **amount owing `$142.18`** and **`Billed to M. A••••••`** and no other field of the customer record — asserted on the body, not the page | The mask is applied **server-side**; the full name never leaves the server. Money stored to 4 dp, displayed 2 (`142.1800` → `$142.18`). Re-read on every load — never cached | BR-CWP-018 · BR-CWP-019 · BR-CWP-020 |
| 3 | **negative** — `BL-2608-0141` + `78704` (wrong postcode); then `BL-9999-9999` + `78702` (no such bill) | Both refused. The two refusals are **byte-identical** — a different message would confirm the bill number exists | The refusal sentence is five or six words (B14 rule 33) and names no internal code. No row written; the lockout counter is a cache entry keyed tenant + form + address — **not a table**, hard rule 4 does not reach it | BR-CWP-025 · BR-CWP-023 |
| 4 | **negative · the lockout** — from `198.51.100.10`, five wrong pairs, then a sixth; then the **correct** pair from the same address in minute 14; then the same five from `203.0.113.7` | The sixth reads *"locked for fifteen minutes"*; the correct pair inside the window is **still refused**; `203.0.113.7` is **not** locked — per address. After 15 minutes a correct pair is accepted and the counter resets | Lock on `POST /public/track` is **independent** — locking quick pay does not lock track. The 61st request of any kind in one minute is refused by the anonymous throttle regardless | BR-CWP-023 · BR-CWP-022 |
| 5 | `CWP-003` — check and pay. Rails absent (today) | `KVList` Bill / Service address `1408 Elm St · A` / **Billed to `M. A••••••`** / Due 14 September → `TotalRow` *Owing $142.18*. The `ConsequenceBox` reads *Pays $142.18 against this bill · Does not create an account · Shows you a reference to keep*. **The Pay control renders in its normal place, disabled, with its reason** — never hidden, never live-but-inert | Forcing a click on the disabled control writes **no payment row, no audit row, no gateway call** — assert all three counts unchanged. A one-character surname (*M. O*) masks at fixed width, not one dot per letter | BR-CWP-056 · BR-CWP-021 |
| 6 | **release 5** — rails present: *Pay $142.18 ✓* | ONE `payment` row `$142.18`; allocated to `BL-2608-0141` by **the tenant's rule** (oldest first by default) — the same rule that previewed it; ONE `audit_log` row naming the **guest channel**; ONE receipt `document`; reference `PAY-26-08841`. **No account created, no `portal_credential` row.** Card number, expiry and CVC are **never stored** — posted to the gateway, which returns a token | Payments writes **no** journal lines: the posting service is the sole writer and writes ONE balanced pair (DR cash / CR AR `142.1800`). `BL-2608-0141` now reads owing `$0.00`. The `customer` row is **byte-identical** before and after | BR-CWP-058 · BR-CWP-026 · hard rules 4 · 5 · 7 |
| 7 | **release 5 · negative** — the gateway **times out** on a second attempt | The screen says so and **no payment row is written on an unknown outcome** — a zero is a claim nobody can make. The retry carries the **same** idempotency key generated **before** the first request left | Zero rows. Assert the key existed in the store before the HTTP call (ordering on the fixture) | BR-CWP-059 · hard rule 6 |
| 8 | **release 5 · the webhook** — settlement `STL-2609-0031` for `$142.18`, then the **identical body again**, then the two **concurrently**, then reversal `STL-2609-0032` carrying the same `pay_26_08841` with the reversal flag | One payment of `$142.18` after the first; **still one** after the replay; **one** after the concurrent pair — proved by the unique constraint, not a read-then-write. The reversal is **not** mistaken for a duplicate: a **second, negative row** above the payment, reason `bank_chargeback` (one of the four signed reasons) | `CWP-041` shows one row, then two on the reversal. ⚠ **Proved on PostgreSQL** (`DJANGO_SETTINGS_MODULE=config.settings.local`): a batch where row 2 of 3 violates a constraint commits rows 1 and 3 inside a nested `transaction.atomic()` — hard-won law 14. A settlement for an unknown reference is refused **without revealing whether it exists**. `payments/webhooks.py` is 577 lines with 15 tests as of 2026-09-03 — **verify before building** | BR-CWP-059 · BR-CWP-061 · hard rule 6 |
| 9 | `CWP-004` — done | Kicker **PAID**, *$142.18 received, thank you*, `KVList` Reference `PAY-26-08841` / Paid 2 Sep 2026 9:47am / Against `BL-2608-0141` / Method *Card ending 8812*. *↓ Receipt* works **without** an email; *✉ Email it to me* prompts for one if none was given. The enrolment offer is one card — **it does not create a login silently and does not withhold the receipt** | Reference looked up later on `CWP-012` with `78702` returns **status and date, never the amount** (the amount is account data). Not taking the offer and reloading: the receipt is still reachable by reference and **no credential row exists** | BR-CWP-028 · BR-CWP-024 |
| 10 | **release 5 · negative** — the guest takes *Set up a login →* | Routes to `CWP-017` — *prove it is you* — and **does not skip the one-time code** because a payment just succeeded. Enrolment attaches a password to the person already on file; it never creates one. A later change to a **stored** method needs a **fresh** step-up code, not the session's | Any card-fee computation on `CWP-003`/`CWP-039` raises `NotImplementedError("OQ-1394")` — **no fee line is drawn** until who pays the fee is ruled (absorbed, surcharged or bank-only; regulated in some states). A stored method row holds **a gateway token, a brand and four digits and nothing else** | BR-CWP-029 · BR-CWP-040 · BR-CWP-057 · `OQ-1394` |
| 11 | **tenant isolation** — Pine Hill's `BL-2608-0141` + `78702` submitted on `/oak-ridge`; `PAY-26-08841` looked up under `/oak-ridge` | Both **refused / not found**. The tenant is resolved from the path and `app.tenant_id` set **before** any bill or customer row is read; bill numbers are per tenant | RLS `FORCE` on every table touched; a Pine Hill lock does not lock Oak Ridge's form (per tenant, per form). `/portal` with no tenant named `portal` resolves as a **reserved segment**, never as a tenant, and does not 500 | BR-CWP-005 · BR-CWP-006 · hard rule 1 |
| 12 | **INVARIANCE** | Across every step: the guest saw an amount and a status, never a person. A **paid** bill (`BL-2607-0139`) opens showing `$0.00` owing and **no Pay control** — not a refusal, the holder is entitled to know it is paid. A **voided** bill reads *cancelled*. A **corrected** bill (`BL-2606-0137`) reads *replaced by BL-2606-0147* and directs payment at the replacement | Issued invoice immutable; the payment row is never updated or deleted (a bounce is a new negative row); every money action has an audit row; the customer record is unchanged from step 1 to step 12 | BR-CWP-021 · BR-CWP-042 · hard rule 4 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Steps 6–8 and 10 as passing tests | **Rails — release 5** (`CR-068` `R2`). Every control is held per `R3`; the contract is written now so the run is built against it |
| b | A fee line on `CWP-003` | `OQ-1394` — who pays the card fee. The computation raises with the id in the code |
| c | The exact webhook signing (a signature over the body vs a shared code in the payload) | `CR-069` `OQ-INT-1478` — answered only in part (*"there will be some code"*). Do not trust `payments.webhook_key` as provisioned until it is read |
