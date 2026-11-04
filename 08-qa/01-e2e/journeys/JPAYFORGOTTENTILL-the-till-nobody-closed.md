# J-PAY-forgotten-till — Dana went home without closing: a System Admin force-closes it, it sits on *Not counted*, and Tuesday morning she declares the count with a reason

---
id: JPAYFORGOTTENTILL
tier: 1
rules: [BR-PAY-1160, BR-PAY-1184, BR-LED-796, BR-SHL-025, BR-TEN-043]
stories: [US-PAY-001, US-PAY-020]
---

<!-- `CR-136-BRC07` phase 2 `P2.18`, authored 2026-09-23 by LANE P2-TESTS.

     ⚠⚠ **THE BLUEPRINT DRAWS THIS JOURNEY AND THE PO STRUCK ITS MIDDLE STEP.**
     p018 commits it as *"Home without closing → **auto-close at midnight** →
     Not counted → declared next morning with a reason."* PO ruling 2026-09-23
     §3.1, verbatim: *"(a) Your ruling stands — **no auto-close**. A System
     Admin closes it. Dana cannot work Tuesday until someone is free to do
     that"*.

     **NO SCHEDULED JOB CLOSES A TILL. NOTHING IN THIS FILE MAY DESCRIBE ONE.**
     A journey is read by the next lane as a specification of what to build, and
     a midnight auto-close written here would be built. `CR-136-BRC07`'s
     *Explicitly NOT to be built* table names it first.

     The file is named for its id — `G12` check 3 matches a spec to a journey by
     FILENAME, and `J-PAY-forgotten-till` is not a journey id under that gate's
     grammar at all. `DEF-QAE-6208` is the eight files that got this wrong. -->

**Intent.** The forgotten drawer, end to end, **and the accepted cost of the
ruling.** A till nobody closed does not close itself; it waits for a supervisor,
and the clerk it belongs to **cannot take money the next morning until somebody
is free to do it**. The PO chose that explicitly. What survives from the drawing
is everything after that step: the till is *Not counted*, it is declared late,
the reason is required, the forced close **still stands**, and the difference
reaches the books on the day it is declared.

**Fixture.** Tenant brazos-bend · **Dana Whitfield** (Billing Clerk), till opened
**Monday 08:55** with a **$200.00** float at the Main office · takings left in
the drawer · Dana goes home at 17:40 without closing · **Marcus Vega is a Billing
Clerk and cannot help**; the supervisor is a **System Admin**. Tuesday Dana
counts **$1,228.00 against $1,240.00 expected — $12.00 short**, reason *"cheque
stuck to the bag"*.

| # | Time · action | Handoff contract (what this step leaves) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | **Mon 08:55** — Dana starts her counter (3·3a) | the session and its cash batch, one transaction | `closed_at` NULL — the till is OPEN and stays open | BR-PAY-1184 |
| 2 | **Mon 17:40** — Dana goes home | **nothing happens.** No job runs. No status moves | ⚠ **THE ASSERTION IS AN ABSENCE, AND IT IS THE POINT OF THE RULING.** At 00:00 the till is still open; at 03:00 it is still open. Any row showing `close_kind = 'system'` for a PERSON's till is this journey failing | **§3.1** |
| 3 | **Tue 08:05** — Dana tries to start today's counter | **REFUSED**, naming the till still open from Monday and the date it was started | `uq_counter_sessions_open_owner` allows one open till per person. ⚠ **THIS IS THE ACCEPTED COST**: *"Dana cannot work Tuesday until someone is free to do that"* | BR-PAY-1160 · §3.1 |
| 4 | **Tue 08:20** — a **System Admin** opens **Counters** (3·1), finds Dana's row and force-closes it with a reason (3·3c) | `close_kind` **`forced`** · `closed_by` = **the supervisor** · `owner` = **Dana**, for ever · `counted_totals` NULL · `difference` **NULL, not zero** | A Billing Clerk attempting the same act is refused — the role check is on the SERVICE, so no endpoint can skip it. The reason is REQUIRED: a forced close with no reason is indistinguishable from a mistake | **BR-SHL-025** · §3.1 |
| 5 | **Tue 08:21** — the till lands on **Not counted** | one derived expression, four readers: 3·1's list, its filter chip, `P2.11`'s notice and the phase's own *done when*. It is `close_kind = 'forced' AND declared_at IS NULL` | ⚠ **`difference` IS NULL AND NOT ZERO.** Nobody counted. A screen that rendered the two alike would report every unclosed till as balanced | §3.2 |
| 6 | **Tue 08:25** — Dana can now start today's till | the refusal at step 3 is gone the moment Monday's till closes | The partial index asks `closed_at IS NULL`, so a CLOSED till lets the next one open | BR-PAY-1160 |
| 7 | **Tue 09:10** — Dana declares Monday's count (3·3d): `$1,228.00`, reason *"cheque stuck to the bag"* | `counted_totals`, `difference` **−12.0000**, `note`, **`declared_at`** and **`declared_by` = Dana** — and **`close_kind` DOES NOT MOVE** | ⚠ **§3.2, verbatim: *"(a) Keep it as a forced close and add the late count beside it"*.** The row says BOTH: force-closed Monday by the supervisor, declared Tuesday by Dana, $12.00 short. A fourth `close_kind` was put to the PO the same day and **declined** | **§3.2** |
| 8 | **Tue 09:10** — the books take the shortfall | **DR `6850 Cash over and short` $12.0000 / CR `1010 Undeposited funds` $12.0000**, dated the day it was DECLARED | ⚠ **AND NOTHING WAS POSTED AT STEP 4.** A forced close counted nothing, so it posts nothing; the LATE COUNT is what posts. That is what makes the PO's *"the day it is declared"* true of both paths | **BR-LED-796** · §3.3 |
| 9 | **Tue 09:11** — the till leaves *Not counted* | `declared_at` is set, so the derived expression no longer matches it | ⚠ **THE CLAUSE THAT BITES.** An expression that forgot `declared_at` would leave Dana's Tuesday count on the supervisor's list for ever — the screen telling her she has work she has already done | §3.2 |
| 10 | **INVARIANCE** — a drawer is counted ONCE | a second declare on the same till is refused, naming the date it was already declared; a declare aimed at a **counted** close is refused because *"a counted till was already counted"* | A declare always needs a reason, where a counted close needs one only when it does not balance — *"a declared difference is the only number nobody watched happen"* (p058 ②) | §3.2 · hard rule 6 |

---

## What a browser can actually drive, as of 2026-09-23

Every step above has a control and an endpoint behind it. `P2.6` landed the six
Counter screens and `P2.2` the three closing endpoints, so this journey is
walkable today — with the one gap named below.

| # | Where | The control | What the server does |
|---|---|---|---|
| 3 | Any payments screen → the page head | **`Start counter →`** | `POST /counters` → **422**, `BIZ-COMPLETENESS`, the sentence *"you already have a counter open…"* with the date it was started. ⚠ Under a genuine RACE — two terminals in the same millisecond — the loser gets a **500 carrying a constraint name** instead (`DEF-PAY-6262`). The money is safe either way: the atomic block holds and the race leaves one till and no orphan batch |
| 4 | Payments → **Counter** (3·1) → the row's action → **Force close** (3·3c) | a **Why** field, required | `POST /counters/{id}/force-close` → **200**. `SystemAdminOnly` on the endpoint AND `@require_role(SYSTEM_ADMIN)` on the service; deleting the decorator leaves the rule standing, deleting the service's does not |
| 5 | Payments → **Counter** (3·1) | the ***Not counted*** filter chip | `GET /counters?f.state=not_counted` |
| 7 | 3·1 → the row → **Declare count** (3·3d) | the countable tenders, and a **Why** that is always required here | `POST /counters/{id}/declare` → **200**, with `posted: true` in the body |
| 8 | Finance → **General ledger** | the trial balance | the pair is visible as `source_type = counter_session`; debits equal credits |
| — | Settings → **Notifications** | *Counter left open · Staff · In-app alert · "When the banking day has ended"* · ON | `manage.py sweep_open_counters` queues it, and `payments.counter_watch` fires the same sweep at 06:00 on this utility's own clock (2026-09-23) — see below |

### THE GAP BETWEEN STEP 2 AND STEP 4: A SUPERVISOR IS TOLD, IF SOMEBODY RUNS IT

⚠ **THIS SECTION SAID `P2.11` WAS *NOT STARTED* UNTIL IT LANDED TWO COMMITS
LATER (`7611d80d2`).** Amended by its own author the same day, because a journey
is read as a specification and one that names a closed gap sends a lane to build
it twice.

**What landed.** SET-12 event `counter_left_open`, staff and system, in-app and
email, timing `end_of_banking_day`, live from its first commit. It fires on
**still open** (`closed_at IS NULL`) and not on *Not counted* — the two are a day
and a person apart, and §3.1 is why: a System Admin's force close is now the only
way an unclosed till gets sealed, so the notice is what PROMPTS step 4 rather
than reporting on it. The expression is written once as
`counter_session_models.STILL_OPEN`, beside `NOT_COUNTED`.

⚠ **IT TELLS AND IT NEVER CLOSES.** `counter_watch.py` contains no write to
`counter_sessions`, and that ABSENCE is the deliverable — `CR-136-BRC07`'s
*Explicitly NOT to be built* table is where the temptation to make it act is
refused. The till's columns are read back field by field after a sweep.

✅ **AND IT IS SCHEDULED — AMENDED 2026-09-23 BY LANE P2-SCHEDULE (`DEF-PAY-6268`).**
This section read: *"⛔ AND IT IS NOT SCHEDULED. `manage.py sweep_open_counters`
is a command, and this repository runs no beat schedule — its own docstring says
so. So step 3's cost still has no upper bound unless somebody runs it."* The
first clause was true and **the second was false when it was written** — five
beat entries were already installed from five `AppConfig.ready()` methods, one
of them in payments itself. Nothing fired the notice, so on a Tuesday when
nobody swept and nobody opened 3·1, Dana could not take money and no one had
been told why.

`apps/payments/counter_watch_schedule.py` now fires the same sweep **at 06:00 on
each utility's own clock** — beat fires a fan-out every 900 seconds and each
firing asks each live utility whether it is that utility's hour, so Houston and
Honolulu are told five hours apart. **Nothing about what this journey ASSERTS
changes**: it still performs the sweep itself rather than waiting on a clock,
because a journey may not assert a job nothing starts *in the process running
it* — the deployed host still runs no beat (`09-infra` §4.1), and the sweep is
idempotent on (utility, banking day), so a journey's own run and the schedule's
cannot double up.

### What this journey deliberately does NOT contain

| | Why |
|---|---|
| A midnight auto-close | §3.1 — the PO struck it. *"(a) Your ruling stands — no auto-close."* |
| A fourth `close_kind` called `declared` | §3.2 — proposed and **declined**; `close_kind` holds exactly `counted`, `forced`, `system` |
| A declare that turns the forced close into a counted one | §3.2 — rejected: it erases who counted what |
| A scheduled job that CLOSES a till | §3.1 — *"(a) Your ruling stands — no auto-close."* ⚠ **AMENDED 2026-09-23 (`DEF-PAY-6268`): this row read *"A scheduled job of any kind"*, which is narrower than the ruling and is what kept `P2.11`'s notice unfired for a day.** The ruling's own recorded words are that, with the auto-close struck, *"`P2.11`'s notice to the supervisor is **the only thing that fires overnight** and it TELLS rather than CLOSES"* — and a notice nothing schedules fires never. What is forbidden is a job that SEALS a till; `apps/payments/counter_watch_schedule.py` seals nothing and a test asserts that from its source. |
