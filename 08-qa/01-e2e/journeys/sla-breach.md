# sla-breach — a job's promise is set, comes close, is paused by a hold, and is broken; the board, the office and the rule's escalation each see it once

---
id: sla-breach
tier: 2
change: CR-168-BRC10 P5.7 (written in round 6 by lane SRV-5, `2.517.0`)
rules: [BR-WRK-018, BR-NOT-021, BR-NOT-017]
tasks: [P5.1, P5.2, P5.3, P5.8, P5.9, P5.10, P3.57, P6.2]
modules: [work, notifications]
spec: 06-backend/tests/test_cr168_srv4_escalations.py (past due, held time) ·
      06-backend/tests/test_cr168_srv5_messages.py (at risk)
---

**Intent.** The promise a job carries — its due time, from the job type's hours, else
its priority's, else the utility's default (72 h for an undated job, PO answer (1),
2026-10-04) — and what the product does as that promise approaches and breaks.

**Upstream leaves (preconditions).** A job raised with a priority or a typed job type,
so `due_at` is stamped (`BR-WRK-018`); the utility's at-risk window set on Settings →
Work (`work_settings.at_risk_window_hours`); a Work rule carrying a *Past due* row if
the office wants the escalation.

| # | When | What happens | Seen where |
|---|---|---|---|
| 1 | Raise | `due_at` stamped from the hours that apply | the order page; the Performance board's target |
| 2 | Hold | the clock PAUSES — `held_at` set; the promise moves out by the time held (P5.2) | order page *On hold*; office told **on hold** once (`work_job_blocked`) |
| 3 | Resume | held time added to `held_seconds`; the promise is due later by exactly that | the at-risk board's count-down |
| 4 | The promise comes within the at-risk window | the hourly sweep tells the office **at risk**, once per promise (`work_job_at_risk`) — never when no window is set | the bell; the at-risk board (P5.3) |
| 5 | The promise passes | a rule's *Past due* row fires `sla_breach` once per job (P3.57) — whoever sent it + every System Admin + the row's *Also tell* | the bell |
| 6 | Closed late | the job counts as *missed* on Performance; the headline agrees with its rows (P5.1, P5.9) | Performance |

**Invariants.**
* A job held for 12 h whose promise was 10 h ago is **not** past due (held time added back).
* Each notice is ONCE: per job per kind for an escalation, per promise for at risk, per
  hold for on hold. A sweep that runs every hour writes nothing the second time.
* Each is its own switch on Settings → Notifications; switched off, nothing is written.
* Without an at-risk window there is no *before*: a passed promise is the escalation's,
  not a flood of at-risk notices on the first sweep after `2.517.0`.

**Leaves (for downstream).** In-app rows of kind `field_work` with `event_code`
`office_at_risk` / `office_blocked` / `escalation_overdue`; a
`work_order_rule_escalation_fires` row per escalation; Performance's missed count.
