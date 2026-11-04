# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-003 · US-RBS-018 (EP-RBS-01) — CR-075 wave D task D1: the
#           data the wave-D walkthrough drives the eight routes against.
# Rules:    CLAUDE.md hard rule 1 (tenant context is a PostgreSQL GUC and these
#           seven tables are RLS-forced) · hard-won law 6 (diff the running app;
#           no gate looks at rendered output) · BR-RBS-020 (the report is frozen
#           at close) · OQ-RBS-1737 (nothing here composes an idempotency key)
# Tests:    10-scripts/render-checks/rbs-d-endpoints.mjs (the consumer)
# Impacts:  apps/runbooks/services.py (the runs are written through the REAL
#           open_run/close_run, so `started_at` and the frozen report are the
#           product's own and never typed)
# ───────────────────────────────────────────────────────
"""seed_runbook_runs — "Can we bill?" on a tenant, and 51 runs of it.

    DATABASE_URL=… python manage.py seed_runbook_runs [--tenant brazosbend]
                                                      [--runs 51]

⚠ **THE RUNS ARE WRITTEN THROUGH `services.open_run` / `close_run`, NOT
INSERTED.** A fixture that wrote `RunbookRun` rows directly would let the
walkthrough pass over a broken `open_run` — and `open_run` is exactly where
`DEF-RBS-4291` was hiding (`started_at` never stamped, every run's *Started* and
*Took* column blank for ever, nothing red). The walkthrough's job is to catch
that class, so the seed uses the product's own write path and the timestamps and
the frozen report are COMPUTED rather than typed.

**51 runs on purpose.** The walkthrough asks for `per=5` and must see **50**
rows and a page 2 with **one** on it; at 50 or fewer there is no page 2 and the
paging assertion cannot fail, which is law 7's *incapable of failing* shape.

⚠ **IT WRITES NO `runbook_run_records` AND THAT IS NOT AN OVERSIGHT.**
`runbook_run_records.idempotency_key` is `NOT NULL` and how it is composed is
`OQ-RBS-1737`, OPEN — the documents contradict each other (`DEF-RBS-4246`) and
the cost of guessing is *496 notices instead of 248, and no test that can see
it*. So the two result files stream a header and no rows against this seed,
which is the truth about the product today and is what the walkthrough asserts.

PostgreSQL only, like `seed_demo`, `seed_portal_demo` and
`seed_integration_runs`: tenant context is a GUC and all seven tables are
RLS-forced. Idempotent in the sense that matters — it reuses the runbook row if
it is there and appends runs, so a replay does not duplicate the catalogue.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection as db_connection

from apps.runbooks import models, services
from apps.runbooks.definitions import configuration_check
from apps.runbooks.engine.executor import RunResult
from core.tenancy import tenant_context, tenant_id_for_slug

#: The runbook the walkthrough opens. It is the ONE the registry ships today
#: (`definitions/DEFINITION_MODULES`), so the template library's *Added* state
#: and the catalogue's row are the same object a clerk would see.
KEY = "configuration_check"

#: The frozen report the walkthrough re-reads twice and diffs. **One block**,
#: where `configuration_check.report()` composes six — the gap is what lets the
#: check tell *served from the column* from *recomputed from the definition*
#: (`BR-RBS-020`, `07-endpoints.md` E-5).
FROZEN = [
    {
        "block": "verdict",
        "payload": {"word": "No-go", "tone": "bad", "count": "3 things stop billing"},
    }
]


class Command(BaseCommand):
    help = 'Seed "Can we bill?" and its runs for the CR-075 wave D walkthrough.'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")
        parser.add_argument("--runs", type=int, default=51, help="how many runs to append")

    def handle(self, *args: Any, **options: Any) -> None:
        if db_connection.vendor != "postgresql":
            raise CommandError(
                "seed_runbook_runs needs PostgreSQL — tenant context is a GUC and all "
                "seven runbooks tables are RLS-forced; nothing was written."
            )
        subdomain = options["tenant"]
        # ⚠ The slug is resolved through `core.tenancy`'s registered seam and not
        # by importing `apps.tenancy.models`: a cross-module model import is what
        # B2 §2 forbids, `G6` refuses and `G115` fails BY FILE AND LINE for this
        # module in particular.
        tenant_id = tenant_id_for_slug(subdomain)
        if tenant_id is None:
            raise CommandError(f"no tenant with subdomain {subdomain!r} — run seed_demo first.")

        with tenant_context(tenant_id):
            runbook, created = models.Runbook.objects.get_or_create(
                tenant_id=tenant_id,
                key=KEY,
                defaults={
                    "name": "Can we bill?",
                    "kind": models.KIND_CHECK,
                    "category": "platform",
                    "subject_type": "tenant",
                    "unit_of_work": "config graph",
                    "template_key": KEY,
                    "timezone": "America/Chicago",
                    "gate_mode": "approve_each_run",
                    # `OQ-RBS-1731` closed 2026-09-06: the default cap is 100
                    # ("1731 … (b) ship 100"). Wave `L4` makes it the column's
                    # default; a fixture types it rather than pre-empting that.
                    "cap": 100,
                },
            )
            written = 0
            for _ in range(max(int(options["runs"]), 1)):
                run = services.open_run(runbook, configuration_check.RUNBOOK)
                services.close_run(
                    run,
                    RunResult(
                        runbook_key=KEY,
                        subjects=(),
                        scope_fingerprint="0" * 64,
                        guarded=(),
                        set_results={},
                        records=(),
                        counts={"blockers": 3, "warnings": 6},
                        report=list(FROZEN),
                        step_runs={},
                    ),
                )
                written += 1

        self.stdout.write(f"  runbook {'created' if created else 'reused'}: {KEY}")
        self.stdout.write(
            self.style.SUCCESS(
                f"{written} run(s) closed for {subdomain}. Each carries a started_at, a "
                f"finished_at and a ONE-block frozen report; no run record rows were "
                f"written (OQ-RBS-1737 is open — nothing composes an idempotency key)."
            )
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-003 · US-RBS-018 (EP-RBS-01; CR-075 wave D task D1)
# generated: 2026-09-06 by the CR-075 wave D build lane
# checklist: A✔ B✔ C✔ D=n/a(a management command, not an endpoint) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path — it composes no idempotency key)
# gates: 10-scripts/render-checks/rbs-d-endpoints.mjs · G115 (the import census)
# exceptions: it writes no runbook_run_records — OQ-RBS-1737 is OPEN and the reason is in the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
