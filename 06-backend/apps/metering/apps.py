# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (BR-MET-034 premises types are Reference data) ·
#           US-MET-003 (the wizard cannot resolve a type without them)
#           Screens: S14, S16, S8
# Rules:    BR-MET-034 (premises types seeded + tenant-extensible) ·
#           BR-TEN-031 (owning module supplies reference-list content) ·
#           BR-TEN-013 (cross-module writes go through service functions)
# Tests:    06-backend/tests/test_us_met_001_002_lists.py
# Impacts:  apps.tenancy reference-data seeding seam (seed_reference_list) ·
#           apps.assets (asset list routing)
# ───────────────────────────────────────────────────────
"""metering AppConfig — registration only, no logic.

The tenancy seeding seam resolves `apps.metering.services.seed_reference_list`
at CALL time (apps/tenancy/seams.py), so there is nothing to register for it
here. The sentence that stood here until 2026-08-17 — "tenancy's LOOKUP_LISTS
declares no `premises_types` key" — went stale on 2026-08-10 when DEF-026
declared the key, and the handler it was waiting for was never written: that is
DEF-236, seven days of a seeded list with no screen. `lookups.register()` in
ready() below is its fix (CR-010 item 2).
"""

from django.apps import AppConfig


class MeteringConfig(AppConfig):
    name = "apps.metering"
    label = "metering"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # US-SHL-008: this module owns four lists that declare Download (S14 ·
        # S15 · S26 · S27), so it registers their exporters — the column set,
        # the selector call and the param vocabulary are the OWNING module's,
        # exactly as reference-list handlers and job bodies are (BR-TEN-031).
        from apps.metering import exports, import_runs, lookups, search_sources
        from core import jobs as core_jobs

        exports.register()
        # DEF-236 / CR-010 item 2: the premises_types /lookups handler — the
        # missing quarter of DEF-026's fix, seven days late.
        lookups.register()
        # CR-026 — the three import stages that measured over a request timeout
        # (transform 77.9s · validate 50.8s · load 101.5s at 50,000 rows) run as
        # BE-07 jobs for files over `ASYNC_ROW_BAR`. Registered HERE because the
        # module that owns the work owns its body (core/jobs.py's contract), and
        # a kind with no registered handler is a job that fails at the worker
        # with "no handler registered" — which is why this is three lines beside
        # the enqueue rather than a step anyone can forget.
        core_jobs.set_job_handler(import_runs.TRANSFORM_JOB, import_runs.run_transform_job)
        core_jobs.set_job_handler(import_runs.VALIDATE_JOB, import_runs.run_validate_job)
        core_jobs.set_job_handler(import_runs.LOAD_JOB, import_runs.run_load_job)
        # DEF-MET-8106 / DEF-MET-8108 — a read batch over the post bar posts in
        # a worker, and the monthly-usage rebuild after every post runs as its
        # own resumable job. Same reason as the three above: an unregistered
        # kind fails at the worker with "no handler registered".
        from apps.metering import services

        core_jobs.set_job_handler(services.READ_POST_JOB, services.run_read_batch_post_job)
        core_jobs.set_job_handler(services.USAGE_REFRESH_JOB, services.run_usage_refresh_job)
        # US-SHL-003 — the `premises` and `units` groups of universal search.
        # Same posture as the job handlers above and for the same stated reason:
        # the module that owns the table owns its query. ⚠ An unregistered group
        # does not error, it is simply ABSENT from the popover — hard-won law 2
        # wearing a search box.
        search_sources.register()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-001@d76f5b4 (story+rules snapshot hash — EP-MET-01 lead story)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — registration only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [list-export lane 2026-08-10] ruff✔ black✔ py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · frontend tsc✔ eslint✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 baseline) · ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: premises_types has no tenancy LOOKUP_LISTS key to register against — reported, served by GET /premises/types instead
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
