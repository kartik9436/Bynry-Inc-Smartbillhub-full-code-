# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-012 (BE-06 series-sink registration — the SELECT-FOR-UPDATE
#           allocator, core/numbering.py documented contract) · US-TEN-001
#           (subdomain → tenant resolution feeding BE-01) · US-TEN-010 (UoM
#           lookup handler registration, BR-TEN-031) · US-TEN-009 (the
#           reason_codes / payment_methods cards — declared with no handler
#           since W0, registered here 2026-08-09)   Screens: S8, S110–S114
# Rules:    BR-TEN-003 (resolver: subdomain server-side) · BR-TEN-035 (allocation
#           inside the issuing transaction) · BR-TEN-031 (tenancy owns UoM content;
#           hosts reason_codes/payment_methods until their lanes land) ·
#           BR-TEN-036 (seeded, tenant-extensible vocabularies)
# Tests:    06-backend/tests/test_us_ten_012_numbering.py (sink through the kernel)
# Impacts:  core.tenancy.TenantContextMiddleware (BE-01) · core.numbering.next_number
#           (every issuing module) · /lookups/uoms
# ───────────────────────────────────────────────────────
"""tenancy AppConfig — the wiring point the W0 kernels documented:

- core.tenancy.set_tenant_resolver(selectors.tenant_id_for_subdomain)  (BE-01)
- core.numbering.set_series_sink(services.allocate_series_number)      (BE-06)
- core.jobs.set_job_store(services.JobStore())                         (BE-07)
- core.jobs.set_job_dispatcher(services.dispatch_job)                  (BE-07)
- services.register_lookup_handler("uoms", ...)                        (EP-TEN-07)

Registration only — no logic lives here.
"""

from django.apps import AppConfig


class TenancyConfig(AppConfig):
    name = "apps.tenancy"
    label = "tenancy"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # CR-049 task 1 — the document store's model lives in its own file,
        # for the reason `apps/notifications/template_models.py` and
        # `apps/billing/template_models.py` exist: `models.py` is 28 tables
        # long and shared by every lane in this module, and a table with its
        # own 200-line argument about ownership belongs beside that argument.
        # Imported HERE because Django registers a model when the module
        # defining it is imported during app loading, and nothing else imports
        # this one.
        from apps.tenancy import document_models  # noqa: F401
        # CR-068 wave D (2026-09-04): the six published-content tables —
        # help answers, their language variants, the read/vote counter,
        # tips and service centres with their weekly hours. Same reason as
        # the line above: Django registers a model when the module defining
        # it is imported, and nothing else imports this one.
        from apps.tenancy import published_content_models  # noqa: F401
        # 2026-10-02 (PO, exports move to S3): `job_artifacts`, the record of
        # one export file — what replaced the disk path on the job. Same reason.
        from apps.tenancy import export_models  # noqa: F401
        from apps.tenancy import exports, selectors, services
        from core import jobs as core_jobs
        from core import numbering as core_numbering
        from core import tenancy as core_tenancy

        core_tenancy.set_tenant_resolver(selectors.tenant_id_for_subdomain)
        core_numbering.set_series_sink(services.allocate_series_number)
        # BE-07: this module hosts the `jobs` table (models.Job), so it owns the
        # store the kernel persists through and the transport that starts work.
        # Without the store, every 202 endpoint fails loudly by design — that is
        # the gap this registration closes. The dispatcher reads JOBS_EAGER at
        # call time (services.dispatch_job): eager in dev/demo, broker in prod.
        core_jobs.set_job_store(services.JobStore())
        core_jobs.set_job_dispatcher(services.dispatch_job)
        # DEF-2487 — and the dispatcher's own honest answer to *"will anything
        # actually run this"*. The transport swallows a broker failure on
        # purpose, so without this a caller cannot tell a queue with a worker on
        # it from a queue with none, and an import handed to the second one
        # disappears in silence. Registered beside the dispatcher because it is
        # about the same transport.
        core_jobs.set_dispatch_probe(services.job_dispatch_ready)
        # DEF-BIL-8511 — and whether a worker is executing a given job NOW, so
        # a Resume can tell a dead worker's job from a live one in a second.
        core_jobs.set_liveness_probe(services.job_active_on_worker)
        # US-SHL-008: the ONE body behind every table-level export. The nine
        # exportable lists register THEMSELVES from their own AppConfig.ready()
        # (apps/{metering,assets,rating}/exports.py) — this module supplies the
        # endpoint, the job and the IS-9 writer, never another module's query.
        core_jobs.set_job_handler(exports.LIST_EXPORT_JOB, exports.run_list_export_job)
        # CR-010 new mandate 1 (PO 2026-08-17): the sample-data PLANT a new
        # tenant's provisioning enqueues after commit. The body is the SAME
        # seed_sample_data the S8 panel and load_sample_data call — never a
        # second seeder (apps/tenancy/sample_data.py argues the whole posture).
        from apps.tenancy import sample_data as tenancy_sample_data

        core_jobs.set_job_handler(
            tenancy_sample_data.PLANT_JOB_KIND, tenancy_sample_data.run_provisioning_plant
        )
        services.register_lookup_handler("uoms", services.UomLookupHandler())
        # The two lists tenancy HOSTS for owner lanes that have no tables yet
        # (BR-TEN-031 content owners: billing / payments — see the model
        # docstrings). Their LOOKUP_LISTS entries have always existed with no
        # handler behind them, so both cards 404'd; registering here makes them
        # render. When the owning lane lands, it calls the same registration
        # function and its handler replaces this one.
        for list_code, handler_class in services.HOSTED_LOOKUP_HANDLERS.items():
            services.register_lookup_handler(list_code, handler_class())
        # DEF-2717 — does THIS process's own connection actually obey RLS?
        # Registered from tenancy because tenancy owns tenant scoping (BE-01,
        # core.tenancy above). Tagged `database` because that is the KIND of
        # check it is; the tag groups it, it does NOT narrow when it runs —
        # Django filters by tag only when a caller passes `tags`, and
        # `BaseCommand.check()` passes none, so this runs with every management
        # command including the `migrate` the entrypoint runs on every boot.
        # core/rls_guard.py argues the whole posture; it is a 🔒 RLS path.
        from django.core.checks import Tags as CheckTags
        from django.core.checks import register as register_check

        from core import rls_guard

        register_check(CheckTags.database)(rls_guard.check_runtime_rls_enforcement)

        # DEF-2379 — can this process file a document at all? Registered beside
        # the RLS guard because it answers the same KIND of question at the same
        # moment: is this deployment able to do the thing it will be asked to do,
        # asked at boot rather than at the first attempt.
        #
        # The PO created a utility on 2026-09-02 and watched seven steps go green
        # before step 8 stopped on an unset DOCUMENT_STORAGE_BUCKET. Nothing was
        # wrong with the code — two environment variables were missing, and the
        # only witness was a tenant creation. core/storage_guard.py argues the
        # whole posture, including why it makes no network call.
        #
        # UNTAGGED on purpose: Django filters by tag only when a caller passes
        # one, and the entrypoint's `migrate`, `runserver` and gunicorn all pass
        # none. A tag could group it and could never narrow when it runs.
        from core import storage_guard

        register_check(storage_guard.check_document_storage)

        # CR-067 task A3 — WHICH SETTINGS EXPLAIN A `StorageNotConfigured`.
        #
        # A capture site knows what it was doing; it does not know that a
        # document-store refusal is reproduced from three settings, and it
        # should not have to. The module that OWNS the exception says so, from
        # here, the way this file already registers every other seam — and that
        # is what makes CR-067 §5's acceptance test writable from the record of
        # a failure the seeding plant knew nothing about:
        #
        #     settings.DOCUMENT_STORAGE_BACKEND          = "aws_s3"
        #     settings.DOCUMENT_STORAGE_BUCKET           = ""
        #     settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
        #     with pytest.raises(StorageNotConfigured):
        #         document_storage.backend()
        #
        # ⚠ THE LIST IS THE ONE `document_storage.backend()` ACTUALLY READS —
        # `DOCUMENT_STORAGE_DIR` and `_SSE` included, because "the filesystem
        # backend was allowed but no directory was set" is a different failure
        # from "no bucket" and a record that could not tell them apart would
        # send somebody to the wrong setting.
        from apps.tenancy import document_storage
        from core import diagnostics as core_diagnostics

        core_diagnostics.register_settings_for(
            document_storage.StorageNotConfigured,
            (
                "DOCUMENT_STORAGE_BACKEND",
                "DOCUMENT_STORAGE_BUCKET",
                "DOCUMENT_STORAGE_ALLOW_FILESYSTEM",
                "DOCUMENT_STORAGE_DIR",
                "DOCUMENT_STORAGE_REGION",
                "DOCUMENT_STORAGE_ENDPOINT_URL",
                "DOCUMENT_STORAGE_SSE",
            ),
        )

        # PO 2026-10-02 (exports move to S3): the DAILY per-utility export
        # clean-up, in place of "delete on the next export". A pure
        # registration — no broker, no clock, no table; never raises.
        from apps.tenancy import export_sweep

        export_sweep.install()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-012@80cdedf (story+rules snapshot hash — EP-TEN-08; co-packets US-TEN-001@d5f8c32 · US-TEN-009@178c282)
# generated: 2026-08-09 by story-coder v1 (W0 tenancy provisioning + settings lane) · AMENDED 2026-08-09 by story-coder (reference-data gap lane — hosted-list handler registration)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [list-export lane 2026-08-10] ruff✔ black✔ py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · frontend tsc✔ eslint✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 baseline) · ruff✔(E4/E7/E9/F select, same bar the baseline passes) black✔ pytest tests/test_us_ten_*: 86 passed / 2 skipped (logo lane · identity-seam skip-until-wired) / 2 isolation→G5✔ · suite 335 passed, 7 skipped, 20 deselected✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently) · [gap lane 2026-08-09 FINAL] ruff --select E4,E7,E9,F✔ black✔ · migrate from empty✔ makemigrations --check --dry-run✔ · suite `pytest tests -m "not golden and not isolation"` 682 passed / 7 skipped / 47 deselected (594 was the baseline when this lane started; 62 of the new tests are this lane's, the rest arrived from the concurrent audit-viewer / identity / rating lanes) · `-m isolation` 14 passed / 22 postgres-only skipped
# exceptions: registration only · [gap lane 2026-08-09] the two hosted handlers are registered by TENANCY though BR-TEN-031 names billing/payments as their content owners — hosting disposition, re-homing path documented on the models; apps/assets keeps registering meter_types/read_methods/asset_* as before
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
