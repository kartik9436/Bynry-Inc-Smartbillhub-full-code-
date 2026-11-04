# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 (bulk corrections) · US-BIL-031 (document-only
#           correction)   Screens: S30
# Rules:    CLAUDE.md rule 1 (every table this registers is tenant-scoped and
#           RLS-forced by migrations/0015)
# Tests:    06-backend/tests/test_us_bil_016_bulk_corrections.py
# Impacts:  apps/billing/correction_models.py (the three model classes this
#           makes visible to the app registry) · apps/billing/migrations
#           (which cannot see a model the registry has not loaded)
# ───────────────────────────────────────────────────────
"""billing AppConfig — model registration only, no logic.

It exists for one reason, stated plainly because a reader will otherwise wonder
why billing suddenly needs an AppConfig when it never did: Django imports
`apps.billing.models` and nothing else, and **the three corrections tables are
not in that file**. They are in `correction_models.py`, because `models.py` is
the busiest file in this repo and two lanes in one models module is how a
migration graph forks — the reason `apps/payments/apps.py` already exists,
recorded there in the same words.

`ready()` imports the module, so the model classes register themselves exactly
as they would have from `models.py`. Folding them back in later is a move, not
a redesign — and until then this import is what makes `makemigrations` see them
at all.

⚠ **THIS DOCSTRING ENDED "Nothing else belongs here. Billing registers no
reference-data handler, no exporter and no signal." AND THAT IS NO LONGER TRUE
— corrected rather than left standing (CLAUDE.md hard-won law 1).** CR-051
tasks 8–10 make billing the FIFTH module to register BE-07 job bodies, and
`core/jobs.py`'s contract puts the registration in the app that owns the work:
*"a kind with no registered handler is a job that fails at the worker with 'no
handler registered'"*. `apps/metering/apps.py` says the same in the same place.

So `ready()` now does two things and only two: it imports the two out-of-file
model modules for their registration side effect, and it registers billing's
job bodies. Billing still registers no reference-data handler and no signal.

⚠ **AND "no exporter" STOPPED BEING TRUE ON 2026-09-01 (`DEF-2842`) — corrected
here rather than left standing, which is the same law this docstring already
invokes once.** Billing now registers ONE export resource,
`apps/billing/exports.py`: the release AUTHORISATION RECORD. It is not a screen
and never becomes one — `BR-BIL-065` is the PO's own ruling of 2026-08-11 in two
words, *"B An export only"* — and until that registration line existed the
ruling's chosen half was unbuilt while its declined half was faithfully
honoured, which reads exactly like compliance. Billing still registers no
reference-data handler and no signal.

⚠ **AND "the three bill-run job bodies" IS NOW FOUR (CR-053 task 13,
2026-08-31).** `apps/billing/print_set.py` registers the print hand-over's body
on the same billing queue, and declares that kind downloadable at the platform's
`GET /api/exports/{job_id}/file`. That last line is the only thing in this repo
that makes a finished print set fetchable, so it is stated here rather than left
to be discovered: without it the archive is written and no route will serve it,
which is hard-won law 2 in one line.
"""

from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = "apps.billing"
    label = "billing"  # unchanged from Django's default, so no migration moves
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Imported for its side effect: defining a model registers it.
        from apps.billing import correction_models  # noqa: F401
        from apps.billing import template_models  # noqa: F401
        from apps.billing import check_models  # noqa: F401 — bulk Check store (OQ-843 option C)
        from apps.billing import bill_link_models  # noqa: F401 — DEF-BIL-10531, the bill email link

        # CR-051 tasks 8–10 — the three verbs that used to hold the browser
        # (BR-BIL-051: *"run the billing in batch process in background"*).
        # Registered HERE because `core/jobs.py`'s contract is that the module
        # owning the WORK owns its body, and a kind with no registered handler
        # is a job that fails at the worker with "no handler registered" —
        # which is why this is one line beside the models rather than a step
        # anyone can forget. `apps/metering/apps.py` says the same, above the
        # three import stages, for the same reason.
        from apps.billing import run_jobs

        run_jobs.register()
        # DEF-BIL-10091 — bulk Fix a bill's preview, Send and approve-and-issue
        # run in the background, on billing's queue, for the same reason.
        from apps.billing import correction_jobs

        correction_jobs.register()
        # OQ-843 re-ruled 2026-09-30 (option C) — the beat entry that re-checks
        # an account whose plan, reading, meter or payment moved. `install()`
        # never raises: without celery the findings read still sweeps.
        from apps.billing import check_staleness

        check_staleness.install()

        # US-SHL-003 — the `bills` group of universal search. Same posture as
        # the job handler above: the module that owns the table owns its query
        # (core/search.py's BE-08 contract). ⚠ An unregistered group does not
        # error, it is simply ABSENT from the popover.
        from apps.billing import search_sources

        search_sources.register()

        # CR-053 task 13 — the print hand-over's job body and its queue, on the
        # SAME billing queue as the three run verbs (PO ruling 2026-08-31:
        # *"billing will need its own named workers"*). It also declares itself
        # downloadable at the platform's `GET /api/exports/{job_id}/file`,
        # because the module that owns the WORK owns that statement too.
        from apps.billing import print_set

        print_set.register()

        # DEF-2842 / BR-BIL-065 — the release AUTHORISATION RECORD as an export,
        # which is the option the Product Owner chose on 2026-08-11 (*"B An
        # export only"*) and the one thing that answers *"what did I approve on
        # 1 July?"* now that the phase-4 panel recalculates (BR-BIL-056).
        #
        # ⚠ **THIS LINE IS THE WHOLE OF hard-won law 2 FOR THAT RULING.**
        # `apps/billing/exports.py` can exist in full and be unreachable: with
        # no registration `POST /exports` answers 404 for the name, and the
        # ruling stays unbuilt while the file implementing it sits in the tree.
        # That is the same shape as DEF-2842 itself, one layer along.
        #
        # It also makes the docstring above wrong in its last clause — billing
        # DOES register an exporter now — corrected there rather than left
        # standing (hard-won law 1).
        from apps.billing import exports as billing_exports

        billing_exports.register()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-016@c41f9a2 (ships with apps/billing/correction_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — registration only) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean is what proves the registry sees the models — see the lane report
# exceptions: this AppConfig exists ONLY so the corrections models could be
#         written outside apps/billing/models.py; the fold-back is a move rather
#         than a redesign. REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
