# J56 — The Thursday it went quiet (*9,980 of 10,000 requests used this week · resets Monday*, a collection needing 40 that declines to start, and nobody finding out from an estimated bill three weeks later)

---
id: J56
tier: 2
rules: [BR-INT-034, BR-INT-024, BR-INT-026, BR-INT-022, BR-INT-039]
stories: [US-INT-029, US-INT-030]
# Wiring: every story above cites `J56` in its own `journeys:` frontmatter.
# Activation authority = the GENERATED index (10-scripts/07-e2e-wiring-index.py);
# NOT ACTIVATED — no `07-frontend/e2e/J56.spec.ts`. Wave G task G5 writes it
# (`cr069-g-thursday-budget.mjs`). Phase 3.
# ⚠ FAILURE 10, THE FIRST OF THE FOUR SILENT ONES: a weekly request quota is
# spent on Thursday and readings simply stop arriving — nothing errors, the
# connection just goes quiet, and the first sign is an estimated bill three
# weeks later. A quota is NOT a rate limit: backoff does not help and a token
# bucket cannot see it, because a bucket paces requests and this is a total.
---

**Intent.** A connection declares its **allowance and reset** as data — `budget = {allowance:
10,000, period: week, resets: Monday 00:00 provider time}` — the runtime counts what each run
spends, and the due sweep **declines to start a run it cannot finish**: at **9,980 of
10,000** with a collection needing **40** calls it does not start, **records why**, and
**shows the figure on the screen** — *9,980 of 10,000 requests used this week · resets
Monday*. The card carries the same figure past 90 %. Underneath it, the scheduling model the
product never had: their night, spread not synchronised, skipped rather than doubled, never
replayed six times.

**Upstream leaves (handoff in).** Brazos Bend's `meters_neptune360` connection (J55),
manifest `budget = {allowance: 10,000, period: week, resets: Monday 00:00
America/New_York}`; `config.budget_spent = 9,980`, `period_started_at` = Monday 31 Aug 2026
00:00 New York. A collection **due Thursday 3 Sep** needing **40** calls. A 105-window
backfill (J55) for the atomic-spend case. A `manual` accounting target. A `payments_card`
charge operation (`catch_up_policy = never`) and a bank-file fetch (`latest_only`) for the
catch-up case. 300 synthetic connections across six US zones for the spread case. Brazos Bend
`America/Chicago`, Silver Creek `America/Denver`. DST dates **2026-11-01** and
**2027-03-14**. Actor **Alex Reed**.

**This journey leaves (handoff out).** ONE declined run row (`outcome = skipped`, summary
*declined — 40 requests needed, 20 left this week*); `config.budget_spent` unchanged at
9,980 until Monday; after the reset the deferred collection's run at its next due time;
`budget_spent = 105` after the backfill; a `skipped — the previous run is still going` row; a
*needs a person to start it* row for the money operation; sweep run rows nightly. The S8
card reading the figure; S142's `BudgetLine`.

**Fixture.** Frames `53.1` (*Water meter cloud · Not collecting · Calls used this week 10,000
of 10,000 · Readings stopped arriving on Thursday. The allowance resets on Monday, or your
meter supplier can raise it.* — *Without this the connection simply looks quiet, and the
first sign is an estimated bill three weeks later.*), `44.1` (`BudgetLine` *Calls used this
week 4,180 of 10,000 · Resets Monday. When it runs out, collection stops — so this is on the
screen rather than in a log.*).

| # | Actor · action | Expected outcome (contract) | Downstream assertions (spend · row · figure · isolation) | Rule |
|---|---|---|---|---|
| 1 | Alex — S142 on Wednesday | `BudgetLine` ***Calls used this week 9,980 of 10,000*** · *Resets Monday. When it runs out, collection stops — so this is on the screen rather than in a log.* The S8 card carries the same figure under its state word — **above 90 %** it appears on the card; below, the card is silent and S142 still shows it | The spend is `config.budget_spent` (non-secret), incremented **with each run row**; the allowance and reset are **manifest data, overridable in `config`**, never code | BR-INT-034 · `US-INT-030` TC-5 |
| 2 | **Thursday's due sweep** — the collection needing 40 falls due | **It does not start.** A run row `outcome = skipped`, summary ***declined — 40 requests needed, 20 left this week***. S142 reads ***9,980 of 10,000 requests used this week · resets Monday***; the S8 panel shows attention | `9,980 + 40 = 10,020 > 10,000` — the sweep declines what it cannot **finish**, not what has already failed. **Nothing errored; the connection would otherwise simply look quiet** (frame `53.1`) | BR-INT-034 · BR-INT-024 |
| 3 | **Monday 00:00 New York** — the reset | `budget_spent` → 0, `period_started_at` moves; the deferred collection **starts at its next due time** | The counter resets **at the provider's time** (`America/New_York`), not the tenant's (`America/Chicago`) | `US-INT-030` TC-2 |
| 4 | The 105-window backfill runs | The spend increments by **105, once, atomically with the run row** — a crash mid-walk cannot double-count | Checkpointed windows (J55 step 8) do not re-spend | `US-INT-030` TC-3 |
| 5 | **negative · a budget must be declared** | A manifest that **omits** `budget` fails the gate — the manifest declares a budget **or declares `budget = none` explicitly**; for `budget = none` no figure is shown and nothing is declined | An absence that is a decision, not a default | `US-INT-030` TC-4 |
| 6 | **the scheduler · whose clock** — the nightly cadence evaluated on **2026-11-01** (DST ends) and **2027-03-14** (DST starts) for `America/Chicago` | The due time is **their midnight on both days — one run each night, not two and not zero** | A cadence stored in UTC arrives at 6 pm local in summer and 7 pm in winter, and twice or never on the two days the clocks move | BR-INT-024 · `US-INT-029` TC-1 |
| 7 | **spread, not synchronise** — 300 connections all `nightly`, six zones | Start times **spread across the window** by a deterministic per-connection offset (hash of the id modulo the window) — and **identical across two sweeps** | 300 tenants computed from midnight is a self-inflicted thundering herd; the fix costs one line | BR-INT-024 · `US-INT-029` TC-2 |
| 8 | **overlap** — a run still `running` when the next window is due | **No second run.** A row `outcome = skipped`, *skipped — the previous run is still going*. **Write down that you skipped.** | The content-hash guard would have caught a double import — *but relying on the guard rather than not starting the run is the wrong order* | BR-INT-024 · `US-INT-029` TC-3 |
| 9 | **negative · catch-up** — workers down six hours; six windows missed on the bank-file fetch **and** six on the card-charge operation | **One** run for the file fetch (`latest_only`); **zero** for the money-moving operation (`never`) — it appears on S142 and the S8 panel as ***needs a person to start it*** | Never auto-catch-up for anything that moves money; surface it and let a human press the button | BR-INT-024 · `US-INT-029` TC-4 |
| 10 | **negative · manual, cron, sandbox, breaker** | `manual` → `next_run_at` **NULL**, never swept, **nothing recorded as skipped** — *manual is a choice, not an absence*. `PATCH … cadence = "*/5 * * * *"` → **refused**; the vocabulary is `nightly · hourly · manual`. A **sandbox** connection is never handed real work by the sweep. A connection with an **open breaker** is skipped **and the skip recorded** | Coarse cadences only — never a free-text cron a user can type every minute into | BR-INT-024 · BR-INT-026 · BR-INT-022 |
| 11 | **tenant isolation** | Two tenants with the same vendor → **two budgets**; one tenant's spend never counts against the other's. Brazos Bend (Chicago) and Silver Creek (Denver) both `nightly` run at **their own** midnights; the scope key carries the tenant | RLS `FORCE`; per-connection `config` | hard rule 1 · `US-INT-030` TC-6 · `US-INT-029` TC-7 |
| 12 | **INVARIANCE** | The figure was on the screen before anything stopped; the decline was recorded with both numbers; nothing errored silently; one run per night across the clock change; a skip was always a row; money never caught itself up | The beat schedule has exactly two entries — `integration.sweep_due` every minute and `integration.sweep_expiry` nightly — and the sweep is the only scheduler | BR-INT-034 · BR-INT-024 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | *How to raise it* with the supplier | Outside the product — the screen names the route; the allowance is the supplier's |
