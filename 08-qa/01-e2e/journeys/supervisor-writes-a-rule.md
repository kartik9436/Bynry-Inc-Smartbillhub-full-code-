# supervisor-writes-a-rule — a supervisor writes a rule in three steps, sees what it will raise tonight, and the overnight sweep (or a clerk's screen) raises exactly that, under the rule's own label

---
id: supervisor-writes-a-rule
tier: 2
change: CR-168-BRC10 P3.21 (written in round 9 by lane FIN-T, `2.520.3`)
rules: [BR-WRK-024, BR-WRK-033, BR-WRK-055, BR-WRK-029, BR-NOT-017, CLAUDE.md hard rule 3]
tasks: [P3.16, P3.17, P3.18, P3.19, P3.30, P3.31, P3.32, P3.34, P3.36, P3.38, P3.39, P3.40, P3.42, P3.57, P3.61, P3.62, P3.63, P3.64, P3.65]
modules: [work, notifications, payments, billing, assets, metering, customers]
spec: 07-frontend/src/features/work/rules/cr168Rules.dom.test.tsx (the list, the builder, one rule's page) ·
      06-backend/tests/test_cr168_srv4_rules.py (SQLite) ·
      06-backend/tests/test_cr168_srv4_rules_pg.py + test_cr168_fint_processes_pg.py (PostgreSQL 16 — P3.40, one case per process, red first)
walk: 10-scripts/cr168_rules_after_walk.mjs (browser, 1440)
---

**Intent.** Images 56–64. Ruling 10: a rule is a PROCESS, a template and who hears — and it
raises under the process's own label, never the module's (`DEF-WRK-4096`, the reason no
seeded rule had ever raised a job).

**Upstream leaves (preconditions).** A published template for the job (`raise-a-job`'s
precondition); for an overnight process, its subjects — an expired final notice, a billing
exception, an asset past its certification date, a water meter in continuous flow (in ITS
unit), a meter at its estimate limit, a certification due; for a screen moment, a clerk
about to finish a move-in, move-out, transfer, reconnect or new connection.

| # | Who | Does | Sees | Record |
|---|---|---|---|---|
| 1 | Supervisor | Work › Rules | *+ New rule* top right whatever the list holds; a search that asks the server (name, template, process words); 👁 ✎ ⧉ on every row; *Last fired* and *Jobs raised* | `GET /work/rules?q=` |
| 2 | Supervisor | *+ New rule* → step 1 *Trigger* | Twelve processes; several triggers per rule, each with its own settings — a quantity WITH its unit, a service's own units (hard rule 3); a missing required setting is named | `GET /work/rules/processes` |
| 3 | Supervisor | Step 2 *Notify* | *Give the job to* (a technician, a crew, the best skill fit, whoever covers the area, nobody); *Who hears* rows from Notifications' catalogue; *When it stalls* rows — the seven kinds, hours, *Also tell* | — |
| 4 | Supervisor | Step 3 *Review* | The same summary the rule's page draws, and *Tonight it raises N jobs* | `POST /work/rules/preview` — writes nothing |
| 5 | Supervisor | Activates | The rule's page `/work/rules/{id}` — Overview, Jobs, Audit; Edit · Duplicate · Turn off | `POST /work/rules` (`triggers[]`) |
| 6 | Overnight sweep | Runs | One job per subject per template — a subject with an open job of that template is counted `already_open`, never raised twice (P3.38); a subject refused is refused INSIDE its savepoint and the night goes on (law 14) | `work_orders.source` = the PROCESS label (`dunning_auto`, `billing_exception`, `asset_age_rule`, `high_usage_alert`, `compliance_calendar`, `meter_read`), `rule_id`, `work_order_rule_raises` |
| 7 | — | The job arrives as step 2 said | Assigned to the named holder, the skill's best fit, the area's — or unassigned with the reason (P3.36) | the rule's priority sets `due_at` |
| 8 | Clerk | Finishes a move-in on a SCREEN moment the rule names | The rule's job is ALREADY in the *Field visit* table, labelled with the rule's name, and may be removed (*No visit needed* stays a recorded choice, `BR-WRK-055`) — nothing is raised overnight for a screen moment (P3.34, P3.42) | raised at the save with the rule's priority and assignee, `rule_id` stamped |
| 9 | Supervisor | Opens the rule's Jobs tab | The jobs it raised, paged in SQL | `GET /work/rules/{id}/jobs` |
| 10 | — | A job it raised stalls past an escalation's hours | Whoever sent it, every System Admin and the row's *Also tell* hear once (`sla-breach`) | `escalations` (P3.57) |

**Rules the journey holds.**
* **A rule's job carries its process's label** — the order table's own vocabulary; a module
  name is refused by the table (`DEF-WRK-4096`).
* **Each process raises on PostgreSQL** (P3.40): one case per process, each seen red first.
* **A screen moment never raises by itself** — the clerk sees it ticked and decides
  (`BR-WRK-055`); the overnight sweep does not read screen moments.
* **Reminders live in Notifications**, not on a rule (`work.rules.reminders_live_in_notifications`).
* **Continuous flow compares readings only in its own unit** (hard rule 3).

**Leaves (for downstream).** Rule-raised jobs on Work › Orders under the process's label
with `rule_id`; the rule's *Last fired* and *Jobs raised*; `sla-breach` picks up a stalled one.
