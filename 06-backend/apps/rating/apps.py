# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (the S8 Reference-data card grid — rating's two cards) ·
#           US-TEN-010/011 (per-list add/edit · deactivate/delete lock) ·
#           US-RAT-008 (charge codes) · US-RAT-009 (tax jurisdictions) ·
#           US-RAT-011 (BE-07 job-body registration for the bulk rate update —
#           added by the job-runner lane 2026-08-10)
#           Screens: S8 (Settings → Reference data) · S9 (bulk update)
# Rules:    BR-TEN-031 (the OWNING module registers the handler for its
#           reference lists; tenancy renders and routes) · BR-TEN-036 (seeded +
#           tenant-extensible) · BR-TEN-037 (tax jurisdictions are tenant-entered) ·
#           BR-RAT-040 (bulk = one atomic all-or-none batch, never re-run)
# Tests:    06-backend/tests/test_us_rat_charges_taxes.py ·
#           06-backend/tests/test_be07_job_runner.py (the registered batch body)
# Impacts:  apps.tenancy LOOKUP_LISTS (`charge_codes`, `tax_jurisdictions` —
#           declared with owner "rating", handler=None until this ready() runs) ·
#           /lookups/{list} endpoints · the S8 card grid
# ───────────────────────────────────────────────────────
"""rating AppConfig — registration only, no logic.

INSTALLED_APPS lists `apps.rating`, so Django picks this single AppConfig
subclass up automatically; the app kept the implicit default config until the
reference-data handlers needed a `ready()` hook. Nothing else moves: label,
name and auto-field are the values the implicit config already produced.

BR-TEN-031: tenancy owns the reference-data FRAMEWORK, the owning module owns
its lists' content and validation. Registration is defensive — a tenancy
registry that does not know a list code must not break app startup for a
deployment that has not landed that lane.
"""

from django.apps import AppConfig


class RatingConfig(AppConfig):
    name = "apps.rating"
    label = "rating"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.rating import exports, lookups, search_sources, services
        from core import jobs as core_jobs

        lookups.register()
        # CR-073 — `plans` and `charges` in universal search. Two catalogue
        # columns each, no money and no rating MATH: see the source's docstring
        # for why this is deliberately not a 🔒 path.
        search_sources.register()
        # US-SHL-008: the four S9 lists that declare CSV (plans · charge codes ·
        # taxes & fees · rate-change history). All four are money-bearing, so
        # their exports write an audit row (BR-SHL-016) — the flag lives with
        # the resource, not in the endpoint's guesswork.
        exports.register()
        # BE-07 (US-RAT-011): POST /rate-changes answers 202 and hands the apply
        # to a job. The BODY is this module's — `apply_rate_change_batch` — so
        # this module registers it; the runner looks it up by the record's kind.
        # Idempotence is the body's own (BR-RAT-040: the batch fingerprint
        # refuses a second apply), so a re-delivered task cannot double-apply.
        core_jobs.set_job_handler(services.RATE_CHANGE_JOB, services.apply_rate_change_batch)
        # CR-166-BRC10 ruling 3 — the nightly automatic-enrolment sweep. A
        # missing celery is not an error (`discount_enrolment_job.install`).
        from apps.rating import discount_enrolment_job

        discount_enrolment_job.install()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-009@178c282 (EP-TEN-07 reference-data epic — the grid this registration makes live; also US-RAT-008/009@7d1a8ef for the content law — hash = sha256/7 of each source epic)
# generated: 2026-08-09 by story-coder v1 (API-gap lane — the two declared-but-unhandled Reference-data lists) · AMENDED 2026-08-10 by story-coder (job-runner lane: rate-change job body registration)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — registration only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [list-export lane 2026-08-10] ruff✔ black✔ py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · frontend tsc✔ eslint✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 baseline) · [job-runner lane 2026-08-10] ruff✔ black✔ py_compile✔ · Django check clean · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · ruff✔(E4/E7/E9/F) black✔ py_compile✔ · Django check clean · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (green at handoff in a SHARED tree — concurrent tenancy/settings + billing/payments lanes landed work during this lane; 594 was the baseline when this lane started, this lane adds 26 active TCs + 2 isolation halves) · run_gates 11-PASS/0-FAIL/1-SKIP✔ (this lane adds no migration and no 🔒 guarded file; a transient G7 FAIL seen mid-lane was a CONCURRENT lane's un-ledgered migration and cleared when they landed its row) · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: none — registration only (the handlers' own dispositions are recorded in apps/rating/lookups.py and, for the batch body, in apps/rating/services.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
