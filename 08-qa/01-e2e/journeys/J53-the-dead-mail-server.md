# J53 — The dead mail server (Brazos Bend's provider hangs 90 seconds a call, Silver Creek's 240 bills go out on time, and nobody else notices)

---
id: J53
tier: 2
rules: [BR-INT-022, BR-INT-041, BR-INT-024, BR-INT-015, BR-INT-027, BR-INT-039]
stories: [US-INT-016, US-INT-020, US-INT-022]
# Wiring: every story above cites `J53` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J53.spec.ts`. Wave F task F5 writes it
# (`cr069-f-dead-mail-server.mjs`); `J17` (delivery life) GAINS ITS FIRST REAL
# LEG in the same task — the queue row reaches a provider through the adapter,
# delivery counts stop reading "not reported" for the SEND half, and STAY "not
# reported" for bounces until the feedback path exists (US-INT-023), never zero.
# Phase 2.
# ⚠ FIXTURE DISCIPLINE: the slow fixture must HANG (sleep 90 s then succeed),
# never raise — "a fixture that raises tests the wrong failure entirely".
---

**Intent.** The failure that turns a ticket into an incident and is invisible in testing,
because it only appears under a provider that is **slow** rather than **down**. Unbounded, one
dead mail server at 90 s a call fills all eight workers and tenant B's bill run queues.
Bounded — **a cap of 2 per connection** and **a breaker** that stops dialling a number that
is not answering — **six workers stay free and tenant B runs**. When the breaker is open the
card says why **in words** — *Not working · the mail server is not answering* — and the next
scheduled run is **skipped and recorded as skipped**. One tenant's outage is one tenant's
outage.

**Upstream leaves (handoff in).** Tenant A **Brazos Bend** with J48's working `email_smtp`
connection; the adapter fixture switched to ***slow*** — `sleep 90` then `93/93`. Tenant B
**Silver Creek Water** with a **240-bill run queued** (J17's fixture, 1 Aug) on the
`billing` queue and its own working mailbox. Manifest defaults `timeout_s = 30`,
`concurrency = 2`, `breaker_after = 3`, `half_open_after_s = 300`. Worker pool **8**. A `429`
fixture with `Retry-After: 120`. Two identical fixtures for the jitter case. A provider
message fixture quoting *"…for account 4471-0021 at 1408 Pecan St, Lone Star Ridge"*.

**This journey leaves (handoff out).** Silver Creek's **240 bills issued on time**; Brazos
Bend's connection `status = not_working` with `last_test_text = the mail server is not
answering`; ONE skipped-window run row for Brazos Bend (`attempted 0`, the reason in words);
the delivery dashboard reading a **send count as a number** and **bounces as *not
reported***; Brazos Bend's card back to **Working** after the half-open probe. J17's step 2
now has a real provider behind it.

**Fixture.** Frames `52.3` (*It cannot be tested* / the breaker note shape), `47.1` (the
*Not working · tested 2 h ago* card), `51.1` (a partial send). The delivery dashboard
(`US-NOT-013`) and the S8 Notifications provider-status panel.

| # | Actor · action | Expected outcome (contract) | Downstream assertions (workers · rows · words · isolation) | Rule |
|---|---|---|---|---|
| 1 | Silver Creek's 240-bill run is enqueued on `billing`; Brazos Bend's mail server is made to hang; the nightly sweep runs | Brazos Bend's send runs on the **`integrations`** queue, cap **2** per connection, pool **8** — **six workers stay free**. Silver Creek's run starts within its normal latency and **finishes on time**; Brazos Bend's run finishes when the fixture returns 90 s later | The integrations worker alone is busy; the billing worker never waited. **Both halves ship or neither**: `config/celery_routes.py` routes `integration.*` to `integrations` **and** `docker-compose.yml` lists `celery-integrations` — gate `g59`'s pattern fails the build otherwise (RED first by deleting the compose service) | BR-INT-041 · BR-INT-022 · `US-INT-016` TC-2/3 |
| 2 | **fixture discipline** | The slow fixture is asserted to **sleep, not raise** | A fixture that raises tests the wrong failure entirely | `US-INT-022` TC-2 |
| 3 | Three consecutive timeouts on Brazos Bend's connection | Breaker **open**. Card: ***Not working · the mail server is not answering*** — the reason in words. `integration_connection.status = not_working`, `last_test_text` set. The **next due run is skipped and recorded** — a run row `attempted 0`, summary *skipped — the mail server is not answering* | Every call had a **hard timeout** (30 s). A slow provider degraded to a **queue**, never to an outage; bills rest `queued` | BR-INT-022 · BR-INT-024 · BR-INT-015 |
| 4 | After 300 s the half-open probe succeeds | Card returns to **Working**; the next due run proceeds | The breaker is **per connection**, not per provider key | BR-INT-022 · `US-INT-022` TC-3 |
| 5 | **negative · the 429** — the provider answers `429 Retry-After: 120` | **No call for 120 s**; the token bucket paces the batch afterwards; the run is **not marked failed** — retrying through a 429 turns a delay into a ban | Exponential backoff **with jitter**: two identical fixtures at the same backoff step get **different** next-attempt times — a hundred tenants retrying on one schedule is a self-inflicted denial of service. Retry is the framework's, **never a new job**; three attempts on one job id | BR-INT-022 · `US-INT-016` TC-4 · `US-INT-022` TC-4/5 |
| 6 | **the send half, J17's leg** — the fixture returns: mailbox accepts 86, rejects 7 | Per-item `execute()` results become `sent` / `rejected` on each queue row **through notifications' service function** — consumers never write. The delivery dashboard reads ***86 sent · 7 rejected***; the run row `93/86/7/0/0 · partial`; frame `51.1` names the seven with the mailbox's own sentence (*No such mailbox*) and the addresses **masked at the adapter** | **Bounces read *not reported*** — the string, **never `0`** — a mailbox offers no feedback path. A gate asserts no code path writes `0` for a connection with no feedback operation (`delivery_counts.py:328` already serves the string) | BR-INT-027 · BR-INT-039 · `US-INT-023` TC-1/6 |
| 7 | **negative · the leak path** — the run whose provider message quotes *"…account 4471-0021 at 1408 Pecan St, Lone Star Ridge"* | `provider_error` is stored **scrubbed** (`account ••••, address ••••`), **absent** from the `GET …/runs` list payload, **absent** from the audit row, present **only** on the run detail **to Brazos Bend** | The one column that can carry another tenant's data out of a provider's message — RLS cannot see it, the adapter (P2) scrubs it | `US-INT-020` TC-6 · BR-INT-038 |
| 8 | **tenant isolation** | Brazos Bend's breaker is open; **Silver Creek's connection to the same provider key is unaffected**. Silver Creek's runs list holds no Brazos Bend row; `GET /integrations/email_smtp/runs/<Brazos Bend run>` from Silver Creek → 404 identical to absent | Two tenants, two scope keys, two breakers | hard rule 1 · `US-INT-022` TC-6 |
| 9 | **INVARIANCE** | Tenant B's 240 bills issued while tenant A's server hung; six of eight workers were free throughout; every timeout was hard; the skipped window was written down; the card said why in words; bounces never read zero; the job row preceded the broker message and the 202 on every enqueue | Integrations sent nothing itself — the dispatcher stays the only sender | BR-INT-041 · BR-INT-008 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | Bounce counts as **numbers** | `US-INT-023`'s feedback half — an `email_feedback` operation on `email_bulk`. A mailbox has none, and for it bounces stay *not reported* **forever, in words** |
| b | Customer bills actually leaving for **customers** | W6 — the customer-sending flip (`BR-INT-007`). The queue row reaching a provider is asserted; the flip is notifications' |
