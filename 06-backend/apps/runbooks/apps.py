# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A3. `apps/runbooks/`
#           exists as the TWELFTH code module, with its boundary enforced from
#           the first commit.
# Rules:    BR-RBS-039 (a runbook reaches another module only through a seam
#           this module owns; never imports another module's models, never
#           calls the product's own HTTP endpoints) · BR-RBS-022 (a write is a
#           port; work items and audit rows are the ENGINE's) · CLAUDE.md hard
#           rule 1 (RLS FORCE on every tenant table — migrations/0002_rls_force)
# Tests:    06-backend/tests/test_us_rbs_041_module.py (TC-RBS-25 the census,
#           TC-RBS-7 the isolation probe on PostgreSQL)
# Impacts:  config/settings/base.py DOMAIN_APPS gains "apps.runbooks" after
#           "apps.work"
# ───────────────────────────────────────────────────────
"""runbooks AppConfig — `ready()` loads the runbook registry, and refuses a bad one.

WHY THE DIRECTORY IS `runbooks` AND THE NAV ROUTE IS `operations`
-----------------------------------------------------------------
Three names, all deliberate, none a typo (`17-runbooks/03-field-map.md` D-5):

  * the CODE module is `apps/runbooks` — the PO coined the product word on
    2026-09-06 (*"we coin the word Runbooks - we should make this industry
    standard"*);
  * the NAV ROUTE stays `/{tenant}/operations`, as all 75 wireframes draw it,
    until the section's on-screen name is settled — changing it moves 75 build
    sheets;
  * the SEAM FILES keep the source specification's `operations -> <module>`
    pair naming in their docstrings, so a reader of either document finds the
    same seam.

The specification says `apps/operations` in every one of its sections. That is
superseded for the CODE only, by the naming ruling above.

WHAT `ready()` DOES, AND WHAT IT STILL DELIBERATELY DOES NOT
------------------------------------------------------------
**It loads the runbook registry (`CR-075` wave B) and nothing else.** Every
runbook module in `apps/runbooks/definitions/` is registered here, and a module
that declares the contract wrongly raises `RunbookContractError` **during
startup** — the process does not start and the message names the runbook. That
is what `US-RBS-002` and `US-RBS-015` mean by *refused at load*: a Check with a
port bound is a build error, not a bad Monday.

⚠ **A FAILURE HERE IS MEANT TO BE LOUD AND IS NOT CAUGHT.** Swallowing it would
turn every refusal in `contract.py` into a runbook that silently does not exist,
which is the exact shape of hard-won law 2 — every check passes and the feature
is absent.

**AND FROM `CR-075` WAVE I IT ALSO REGISTERS THE SCHEDULER** — the two job
kinds `runbooks.check` and `runbooks.act` with the `runbooks` queue they ride
(one statement, both halves, because `core/jobs.py`'s contract is that the
module owning the work owns both), and the one-minute beat entry that sweeps
every utility's schedules. ⚠ **THIS PARAGRAPH SAID THE OPPOSITE UNTIL
2026-09-07** — the plan had recorded task `I1` as *already done* while nothing
implemented it, and this docstring was the only place in the repository saying
so (`DEF-RBS-4353`). The consuming half is `docker-compose.yml`'s
`celery-runbooks` service; `G117` refuses a tree with one half and not the
other, because a routed queue nothing drains accepts every job, answers
*queued*, and runs none of them (`DEF-320`).

Still not registered, and each waits on the thing that consumes it:

  * wave O — the event subscription (`batch.landed`, `feedback.landed`,
    `bill_run.completed`), which waits on the integrations substrate emitting
    them;
  * a lookup handler and a search source, which wait on wave D's endpoints.

⚠ THIS MODULE HAS NO SCREEN YET AND THE EXECUTION PLAN SAYS SO. Wave A is the
one wave in `CR-075` that admits it. Its outcome is a GATE THAT GOES RED:
`10-scripts/gates/g115_runbooks_import_census.py` fails a planted
`from apps.customers.models import Account` in this package by name and line.
"""

from django.apps import AppConfig


class RunbooksConfig(AppConfig):
    name = "apps.runbooks"
    label = "runbooks"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Load every declared runbook, then check the `requires` graph.

        ⚠ **THE ORDER IS LOAD-THEN-VALIDATE AND IT MATTERS.** `requires` names
        another runbook by key, and import order is not declaration order — a
        runbook may legitimately require a Check whose module is listed later.
        So membership is checked once everything is in
        (`registry.validate_requires`), and a dangling requirement still stops
        startup because that call is here.

        ⚠ **NOTHING IS CAUGHT.** A `RunbookContractError` from either call is
        the product refusing to start, which is `US-RBS-002`'s acceptance
        sentence word for word: *given a Check module declaring a port, when the
        app starts, then it refuses to start and names the runbook and the
        port.*

        The import is local to this method, as Django requires — models and
        their consumers are not importable at module-import time — and it names
        this module's own package, which is what `G115`'s census permits.

        ⚠ **THE SCHEDULER IS REGISTERED AFTER THE REGISTRY AND THAT ORDER
        MATTERS TOO** (`CR-075` wave I). A job body resolves its runbook through
        the registry, so a queue that accepted work before the registry loaded
        would answer *queued* to a message it could not run. `install()` never
        raises when celery is absent — `manage.py check`, every migration and
        the whole test suite run without a broker — and it says which of the two
        happened rather than looking identical either way.
        """
        from apps.runbooks import scheduler
        from apps.runbooks.registry import registry

        registry.load()
        registry.validate_requires()
        scheduler.register()
        scheduler.install()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-041 (EP-RBS-01 story + BR-RBS-022/039 snapshot; CR-075 §"Where it lives") · US-RBS-015 (CR-075 wave B task B2)
# generated: 2026-09-06 by the CR-075 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own before wave D) E=n/a(no screen — the renderers are wave C) F✔ G✔ H✔(0001 and 0002 are 🔒, HUMAN-REVIEW-PENDING, row in 12-governance/09-human-review-ledger.md)
# ⚠ THE CHECKLIST IS ONE LINE ON PURPOSE: G3 reads `checklist:(.*)` with no
#   MULTILINE flag, so a wrapped checklist loses every letter after the first
#   line and is reported as "missing letters F,G,H" — found on this very file
#   before it was pushed, hiding inside a gate that was already red for other
#   modules.
# gates: pytest tests/test_us_rbs_041_module.py · pytest tests/test_us_rbs_015_conformance.py
#        · G115 (the import census, shown RED first through run_gates.py) · G7 (the 🔒 ledger row)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
