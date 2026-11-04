# EP-INT-06 — The run record, and what a clerk sees when it goes wrong

**Module:** integrations · **Wave:** phase 1 (`US-INT-020`, `021`) · phase 2 (`US-INT-022`, `023`) · **Screens:** S142 connection detail · S8 Notifications provider-status panel · the delivery dashboard (`US-NOT-013`) · **Status:** draft (`CR-069`, 2026-09-03)

## Scope

**In:** the append-only run record with its **five** counts and its outcome vocabulary (`BR-INT-018`, `BR-INT-039`), the connection detail screen **S142** — the observability answer, without which design §1.10's observability row has no home — the `unconfirmed` outcome that P4 exists for, the per-connection concurrency cap, hard timeouts and breaker that keep one tenant's outage one tenant's outage (`BR-INT-022`, `BR-INT-041`), and the email return path — delivery and bounce — that today reads *not reported* and must go on doing so until it exists (`C28`, `BR-INT-027`).

**Out:** the `indeterminate` outcome, which is a money-path story (`US-INT-045`, `EP-INT-13`); scheduling of runs (`EP-INT-08`); the file guards (`EP-INT-09`).

**The design's sentence for this epic:** *"The run record is the observability: counts, outcome, provider error, trace id, per connection, last twenty visible on the card. Metrics come from that table, not from a parallel system."*

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S142 · last runs | trace id | operation · outcome · trigger | `started_at` desc | started · outcome | when · operation · counts (*86 of 93 · 7 bad addresses*) · outcome · trace id / + trigger · artifact | open run (icon, B14 rule 15) | — | — |

The table type is B14 rule 20's one table (13.5 px / 12 px). Twenty rows by default; the existing pagination kernel beyond.

## Stories

---
id: US-INT-020
epic: EP-INT-06
module: integrations
screens: [S142]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-014, US-INT-016]
journeys: [J48, J49, J53, J54]
rules: [BR-INT-014, BR-INT-018, BR-INT-020, BR-INT-039]
golden_tests: []
finance_calc: none
---
### US-INT-020 — The run record and its five counts — and the connection detail screen (S142) that reads it

**1 · Details** — As **a support agent**, I want **every attempt to record attempted · succeeded · failed · skipped · changed, an outcome, a plain sentence and a trace id** — so that **"bills aren't going out" is a query and not a shell session**.

`integration_run` is append-only and partitioned yearly (720,000 rows a year for email alone at 60,000 accounts — which is why runs live apart from configuration). Every row carries `operation`, `direction` (`outbound · inbound · inbound_read`), `trigger` (`manual · scheduled · dispatcher · webhook · partner`), the five counts, `outcome` (`queued · running · succeeded · partial · failed · unconfirmed · indeterminate`), `summary` (plain language, no rule id), `provider_error` (**its own column — the one place another tenant's data can arrive, quoted from a provider's message, where RLS cannot see it**), `input_hash` (file in — computed before parse), `artifact_link` (`core.jobs.succeed(job_id, result_link)`), and `trace_id` — the eight characters a clerk reads down the phone that find the run, the connection, the provider's own error and the job in one query.

**S142 — the connection detail:** the `describe()` line · state in words · the dated expiry sentence · **the last twenty runs** with the counts written as a clerk reads them — *93 of 93* · *86 of 93 · 7 bad addresses* · *Unconfirmed · 93 sent, provider did not say* — grouped by operation, each row opening a run with its per-item results and artifact. `GET /integrations/{key}/runs` (paginated through the existing kernel) and `GET /integrations/{key}/runs/{run_id}`.

**The `provider_error` mitigation, PROPOSED here because the design names the risk and not the fix:** the adapter (P2, the anti-corruption layer) **scrubs** a provider message of email addresses, account numbers and postal addresses before it becomes `provider_error`, the column is rendered **only on S142 to the owning tenant**, and it never appears in a list payload, an audit row, or a notification.

Entry: any adapter call. Exit: one run row; S142 draws it.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-039` | P3 — every attempt is a durable, append-only record with a trace id | PROPOSED — design §1.2, §1.4 |
| `BR-INT-018` | `succeeded` only when the counts reconcile and the far end confirmed; otherwise `unconfirmed` | PROPOSED |
| `BR-INT-020` | The idempotency key per shape; `input_hash` for a file, before parse | PROPOSED |
| `BR-INT-014` | Every lifecycle event writes `audit_log` with masked refs | CONFIRMED |
| B14 rules 15 · 20 · 31 · 32 | Icon row actions · one table type · no database id on screen · one sentence | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Alex opens S142 for the Billing mailbox | Twenty rows newest first; the 1 Aug row reads **86 of 93 · 7 bad addresses**; opening it lists the seven addresses with the mailbox's own sentence for each |
| TC-2 | Support is read trace id `a7f3c9e1` over the phone | One query on `integration_run.trace_id` returns the run, its connection, `provider_error` and `job_id` |
| TC-3 · **PG · negative** | `UPDATE integration_run SET outcome = 'succeeded' WHERE id = <finished run>` | Refused by trigger; the audit trail shows the attempt |
| TC-4 · **copy** | Every `summary` written by the runtime and every string rendered on S142 | Matches neither `BR-[A-Z]+-\d+` nor a UUID (rules 31, 32); the trace id is the only identifier and is labelled *Support reference* |
| TC-5 · **tenant isolation** | Lone Star Ridge calls `GET /integrations/email_smtp/runs` | Only its runs; `GET …/runs/<Brazos Bend run id>` → 404 identical to absent |
| TC-6 · **leak path** | Fixture run whose provider message quotes *"…for account 4471-0021 at 1408 Pecan St, Lone Star Ridge"* | `provider_error` is stored **scrubbed** (`account ••••, address ••••`), absent from `GET …/runs` list payload, absent from the audit row, present only on the run detail to Brazos Bend |
| TC-7 | A reconciling collection run | Five counts shown — *1,240 read · 6 revised* — the `changed` count rendered only when the operation's idempotency mode is `reconcile` |

**4 · Test Data** — Brazos Bend `email_smtp` runs: 1 Sep 06:02 `93/93/0/0/0 succeeded` · 1 Aug 06:02 `93/86/7/0/0 partial` (seven bad addresses named: `j.ortiz@example.invalid` …) · 1 Jul 06:03 `93/0/0/0/0 unconfirmed` (200, no count) · a manual test run `failed` *the mail server rejected the password*, trace `a7f3c9e1`. Cross-tenant error text fixture (TC-6) seeded deliberately. Neptune collection run `1,240/1,240/0/0/6 succeeded` (TC-7).

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `attempted` · `succeeded` · `failed` · `skipped` · `changed` | S142 | design §1.4 · §2.8 (+ `changed`, §2.18.3) | `integration_run` | int | system-derived | `attempted = succeeded + failed + skipped` or outcome is `unconfirmed` |
| `outcome` | S142 · S8 card | Figure 4 (+ `indeterminate`, `C26`) | `integration_run.outcome` | enum | system-derived | seven values; the word shown is the clerk's word |
| `summary` | S142 | P3 | `integration_run.summary` | text | system-derived | plain language, no rule id |
| `provider_error` | S142 run detail only | §2.8 design table | `integration_run.provider_error` | text | integration (scrubbed) | never in list/audit/notification payloads |
| `trace_id` | S142 · S141 | `core/errors.py` | `integration_run.trace_id` NOT NULL | text(8) | system-derived | the only identifier on screen; labelled *Support reference* |
| `input_hash` | S142 run detail | `BR-INT-020` (C) | `integration_run.input_hash` | sha-256 hex | system-derived | computed before parse |
| `artifact_link` | S142 | `core.jobs.succeed(result_link)` | `integration_run.artifact_link` | url | system-derived | export file or import receipt |

**6 · Acceptance**
- Given a partial send, when S142 opens, then the clerk reads how many of how many and which ones, and support can find the run from eight characters.
- Given a finished run, then it cannot be changed; a correction is a new row.
- Given a provider message quoting another utility's customer, then no other tenant and no list, audit or notification can read it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-021
epic: EP-INT-06
module: integrations
screens: [S142, S8]
wave: 1
status: ready
blocked_by: []
depends_on: [US-INT-020, US-INT-015]
journeys: [J48]
rules: [BR-INT-018, BR-INT-040]
golden_tests: []
finance_calc: none
---
### US-INT-021 — The unconfirmed outcome: a run whose numbers cannot be reconciled says so

**1 · Details** — As **a billing clerk**, I want **a run whose numbers cannot be reconciled to say so** — so that **a silent partial delivery is never reported to me as success**.

Four outcomes were never enough (Figure 4): `queued → running → succeeded · partial · failed · unconfirmed`. **`unconfirmed` = the counts could not be reconciled — never reported as success.** A provider that returns 200 but will not say how many it accepted has not succeeded; it has left us unable to say. The runtime writes `succeeded` only when `attempted = succeeded + failed + skipped` **and** the far end confirmed a count; `partial` when some items failed and the counts reconcile; `unconfirmed` otherwise. S142 shows it as its own thing — *Unconfirmed · 93 sent, provider did not say* — and the S8 provider-status panel treats it as needing attention, never as green.

⚠ **THE RED RUN THIS STORY NEEDS FIRST (law 7):** `TC-INT-11` *"is trivially satisfied by a stub that always writes `succeeded`"*, so the proof is the provider fixture that returns 200 with no count, shown turning a naive implementation green — and then this one `unconfirmed`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-018` | `succeeded` only when counts reconcile AND the far end confirmed; else `unconfirmed`, never succeeded | PROPOSED — design §1.4, §1.7 |
| `BR-INT-040` | P4 — a run that cannot state its numbers has failed; per-item results, never a batch boolean | PROPOSED |
| `BR-INT-015` | Failures surface *Failed · Retry*, never silently; provider health feeds the S8 panel | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Provider fixture returns 200 and no accepted count for a 93-message batch | Outcome **`unconfirmed`**; summary *93 sent, provider did not say*; the S8 panel shows attention, not green (doc TC-INT-11) |
| TC-2 · **red-first** | A stub runtime that writes `succeeded` unconditionally | TC-1 fails against it — recorded in the test as the proof the guard can go red |
| TC-3 | Counts `93 attempted · 86 succeeded · 7 failed · 0 skipped`, far end confirmed 86 | `partial`, and the seven are named |
| TC-4 · **negative** | Adapter reports `succeeded = 93` but `attempted = 92` (an item was counted twice) | `unconfirmed` — the arithmetic does not reconcile — and the mismatch is in the summary |
| TC-5 | Far end confirms 93 of 93 | `succeeded`; the card reads *Working · 93 of 93* |
| TC-6 | Delivery dashboard reads the run | The send half counts 86 sent; bounces still **not reported** (`BR-INT-027`); nothing reads zero |

**4 · Test Data** — Adapter fixtures: *no-count* (200, empty body) · *double-count* (TC-4) · *confirmed 93* · *86 + 7 named*. Brazos Bend Billing mailbox.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `outcome = unconfirmed` | S142 · S8 panel | Figure 4 | `integration_run.outcome` | enum | system-derived | set by the reconciliation in `services.py`, never by an adapter |
| far-end confirmed count | run detail | P4 | run artifact / `summary` | int or absent | integration | absent ⇒ `unconfirmed` |

**6 · Acceptance**
- Given a provider that will not say, then the run is unconfirmed and nobody sees green.
- Given the counts reconcile and the far end confirms, then and only then is the run succeeded.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-022
epic: EP-INT-06
module: integrations
screens: [S8, S142]
wave: 2
status: ready
blocked_by: []
depends_on: [US-INT-016, US-INT-020]
journeys: [J53]
rules: [BR-INT-022, BR-INT-041]
golden_tests: []
finance_calc: none
---
### US-INT-022 — Per-connection concurrency cap, hard timeouts and the breaker: one tenant's dead mail server stays one tenant's problem

**1 · Details** — As **a tenant**, I want **another utility's dead mail server to be their problem** — so that **my bill run still runs**.

Figure 7, the failure that turns a ticket into an incident and is invisible in testing because it only appears under a provider that is *slow* rather than *down*: unbounded, one dead mail server at 90 s a call fills all eight workers and tenant B's bill run queues; **bounded — a cap of 2 per connection and a breaker that stops dialling a number that is not answering — six workers stay free and tenant B runs.** `apps/integrations/runtime.py`: a hard timeout on every call (manifest default 30 s, per operation), a concurrency cap per connection (default 2), a breaker that opens after three consecutive timeouts and half-opens with one probe, exponential backoff **with jitter** (a hundred tenants retrying on the same schedule is a self-inflicted denial of service), `Retry-After` honoured, and a token bucket per connection in front of a `429` — retrying through a 429 turns a delay into a ban. **When the breaker is open the card reads *Not working* with the reason in words — *the mail server is not answering* — and the next scheduled run is skipped and recorded as skipped.**

Entry: any adapter call through the runtime. Exit: a run row; the breaker state on S142.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-022` | Hard timeout · cap · breaker · backoff with jitter · `Retry-After` · token bucket; slow degrades to a queue, never an outage | PROPOSED — design §1.7, Figure 7 |
| `BR-INT-041` | P5 — one tenant's outage is one tenant's outage | PROPOSED |
| `BR-INT-024` | A skipped window is recorded as skipped | PROPOSED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 · **integration** | Tenant A's adapter fixture **hangs 90 s then succeeds**; cap 2; pool 8; tenant B enqueues a job | Six workers stay free; tenant B's job completes in normal time; tenant A's run finishes when the fixture returns (doc TC-INT-17) |
| TC-2 · **fixture discipline** | The slow fixture | Asserted to **sleep, not raise** — *"a fixture that raises tests the wrong failure entirely"* |
| TC-3 | Three consecutive timeouts on one connection | Breaker **open**; card *Not working · the mail server is not answering*; the next due run is **skipped and recorded** with that reason; after the half-open probe succeeds the card returns to *Working* |
| TC-4 | Provider answers `429 Retry-After: 120` | No call for 120 s; the token bucket paces the batch afterwards; the run is not marked failed |
| TC-5 · **negative** | Two retries scheduled for identical fixtures at the same backoff step | Their next-attempt times differ (jitter) |
| TC-6 · **tenant isolation** | Tenant A's breaker is open | Tenant B's connection to the **same provider key** is unaffected — the breaker is per connection, not per provider |

**4 · Test Data** — Fixture *slow*: `sleep 90` then `93/93`. Tenant A Brazos Bend, tenant B Silver Creek Water with a 240-bill run (J17). Manifest defaults: `timeout_s = 30`, `concurrency = 2`, `breaker_after = 3`, `half_open_after_s = 300`. `429` fixture with `Retry-After: 120`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `timeout_s` · `concurrency` · `breaker_after` | — | design §1.7 | manifest operation defaults; overridable in `config` (non-secret) | int | reference-data / user-input | cap ≥ 1; timeout ≥ 5 s |
| breaker state | S8 card · S142 | Figure 7 | in-memory + `integration_connection.status = not_working` with `last_test_text` reason | enum | system-derived | reason in words |
| skipped window | S142 | `BR-INT-024` | `integration_run` `outcome = skipped`-shaped row (`attempted 0`, summary names the reason) | row | system-derived | never silent |

**6 · Acceptance**
- Given one tenant's provider hangs, then another tenant's work completes on time and the hanging connection shows *Not working* with the reason.
- Given a 429, then the provider is not retried through it.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None.

---
id: US-INT-023
epic: EP-INT-06
module: integrations
screens: [S142, S8]
wave: 2
status: ready
blocked_by: []
depends_on: [US-INT-020, US-INT-007, US-NOT-013]
journeys: [J17]
rules: [BR-INT-027, BR-INT-020, BR-INT-021]
golden_tests: []
finance_calc: none
---
### US-INT-023 — Email feedback — delivery and bounce — and the *not reported* that stays until it exists (C28)

**1 · Details** — As **a billing clerk**, I want **a bill emailed on the 1st to show *delivered* on the connection's run, and a bad address to show *bounced* with the provider's own sentence** — so that **the delivery dashboard stops reading *not reported* for bounces — and until it does, keeps saying *not reported* and never zero**.

The half most designs forget (Figure 8): an email provider tells you what happened **afterwards**, over a webhook, and until that path exists the product genuinely does not know whether a bill arrived. **The product is already honest** — delivery and bounce counts are served as *not reported* rather than as zero — but *"honesty is not delivery"*, and no task in the ninety-four claimed this path. Two halves: **(a) the send half, phase 2** — per-item accepted/rejected from the adapter's `execute()` become `sent` / `rejected` on each queue row and the dashboard's send counts; **(b) the feedback half, when a provider offers it** — a shape-D operation `email_feedback` on `email_bulk` (`POST /integrations/webhooks/email_bulk`): verify, persist raw, answer, then mark queue rows `delivered` / `bounced` with the provider's sentence and maintain the suppression list `J17` already expects. **A mailbox (SMTP, Microsoft, Google) offers no feedback path, and for those connections bounces stay *not reported* — in words, forever, and never as 0.** Domain verification is the provider's verdict, never computed here.

Entry: a run's per-item results; a provider's feedback callback. Exit: queue-row states the delivery dashboard (`US-NOT-013`) reads through the read-model — consumers never write.

⚠ **BOUNDED 2026-09-06 — THIS STORY CAN NO LONGER BE COMPLETED IN THIS MODULE, AND THAT IS A RULING RATHER THAN A DEFERRAL BY A LANE (`OQ-INT-1729`, PO option (a); `BR-INT-054`(6)).** Half (a), **the send half, is BUILT**. Of half (b): **the feedback DOOR — `POST /integrations/webhooks/{key}`, *authenticate → dedupe → reply at the declared position → persist raw* — is integrations' work, stays here, and is still to be built here.** But **marking the queue rows `delivered` / `bounced` with the provider's sentence, and maintaining the suppression list `J17` expects, are record updates on another module's rows and WAIT FOR RUNBOOKS. Do not build them.** ⚠ **Deferred is not blocked**, and nothing was wasted, because that half had never been started. The acceptance criteria and test cases below are unchanged and still correct — **what changed is WHEN and WHERE the marking half is delivered**, and TC-2, TC-3's *applied once* half and the suppression-list row of §5 are the parts that travel. `BR-INT-027` keeps the dashboard honest in the meantime: bounces read *not reported*, in words, for ever, and never `0`.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-027` | Delivery and bounce read *not reported* until a feedback path exists; zero never substituted | CONFIRMED — already enforced in notifications |
| `BR-INT-020` | Inbound call key = provider event id | PROPOSED |
| `BR-INT-021` | Authenticate before trusting the body; persist raw; answer before processing | PROPOSED |
| `BR-INT-008` | Integrations sends nothing; the dispatcher is the only sender. ⚠ *AMENDED 2026-10-02 (PO, "B · Keep it and change the rule, because it only passes the job on."): the export door may hand an export job to the runner, carrying no figure and no file; sending is unchanged — see `02-business-rules.md` BR-INT-008.* | CONFIRMED |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | SMTP connection sends 93; mailbox accepts 86, rejects 7 | Dashboard reads *86 sent · 7 rejected*; bounces read **not reported** — the string, not `0` |
| TC-2 | `email_bulk` feedback callback: `{event: bounce, ref: <queue row>, reason: "550 mailbox does not exist"}` | The row reads **bounced · *mailbox does not exist*** (the provider's own sentence); the address joins the suppression list; the dashboard's bounce count becomes a number |
| TC-3 | The same feedback event id delivered twice | Applied once; the second answers the declared status and writes nothing |
| TC-4 · **negative** | Callback with a bad signature | Body never parsed; nothing beyond the raw envelope persisted; the refusal recorded |
| TC-5 · **negative** | A feedback event naming a queue row of another tenant | Ignored with 404-shaped silence; no cross-tenant write |
| TC-6 | Microsoft 365 connection, a month of sends | Bounces read *not reported* in words every month; a gate asserts no code path writes `0` for a mailbox connection |

**4 · Test Data** — J17's fixture (Brazos Bend, 240 bills, 1 Aug). `email_bulk` feedback fixture: `delivered` ×230, `bounce` ×7 with reasons, one duplicate event id. Bad-signature fixture. Lone Star Ridge queue row id for TC-5.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| per-item send result | S142 · dashboard | P4 | notification queue row state (`sent` / `rejected`) via the notifications service function — not written by integrations | enum | integration | consumers never write (B1); integrations hands results to the owning module's service |
| feedback event | — | Figure 8 · `C28` | raw envelope persisted (`integration_run` inbound + artifact); queue row `delivered` / `bounced` + `provider_text` | jsonb/enum | integration | event id key; signature first |
| suppression list entry | dashboard | J17 | notifications-owned | row | integration | via service function |
| *not reported* | dashboard | `BR-INT-027` | computed | string | computed-display | never `0` for a connection with no feedback operation |

**6 · Acceptance**
- Given a mailbox connection, then bounces read *not reported* and never zero.
- Given a bulk provider's bounce callback, then the row reads bounced with the provider's sentence and a replay changes nothing.

**7 · Finance Calculation** — N/A.

**8 · Open Questions** — None open. ⚠ **`OQ-INT-1729` was RULED on 2026-09-06 (option (a)) and bounds this story**: the feedback door is built here, the row-marking and the suppression list wait for Runbooks. See §1 above, `BR-INT-054`(6), and the decision log of 2026-09-06.
