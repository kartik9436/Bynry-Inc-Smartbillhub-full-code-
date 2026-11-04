# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-003 (IS-11 downloads ride the ONE export pipeline)
#           Screens: S46
# Rules:    BR-REP-018 (IS-11 downloads) · BR-SHL-016 (server-side, streamed,
#           capped, audited) · BR-TEN-031 (the OWNING module supplies the
#           column set, the selector call and the vocabulary)
# Tests:    06-backend/tests/test_us_rep_003_downloads.py
#           06-backend/tests/test_cr142_p4_schedules.py (the beat entry)
# Impacts:  apps/reports/exports.py (registered here) · apps/reports/schedules.py
#           (its beat entry is installed here; docker-compose.yml's celery-beat
#           service already exists and is NOT changed)
# ───────────────────────────────────────────────────────
"""reports AppConfig — registration only, no logic.

The four report viewers declare Download (S46's ↓ Export action), so this module
registers their exporters with the platform kernel exactly as metering, assets
and rating register theirs. Registration is the only thing that happens here.
"""

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = "apps.reports"
    label = "reports"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.reports import exports, schedules

        exports.register()
        # ── `CR-142-BRC07` `P4.2` · the schedule sweep ──────────────────────
        #
        # ⚠ **BUILT IS NOT WIRED (hard-won law 2), AND THIS IS THE WIRE.**
        # `schedules.beat_schedule()` returning the right dict and celery beat
        # actually ticking it are two claims. `install()` is the second one; it
        # is idempotent, it returns what it did, and **a missing broker is not
        # an error** — `manage.py check`, every migration and the whole test
        # suite run without one, and a product that refused to start because a
        # scheduler was absent would be worse than one whose sweeps start a
        # minute later.
        #
        # ⚠ **THE OTHER HALF IS `docker-compose.yml`, AND IT IS ALREADY
        # THERE.** The brief's `P4.2` says beat is not deployed; measured, it
        # is — a `celery-beat` service with `replicas: 1`, and three modules
        # (`notifications`, `work`, `runbooks`) already install entries from
        # their own `ready()`. So NO compose change ships with this phase, and
        # that was checked rather than assumed: a beat entry nothing ticks is a
        # schedule that never fires with every test green, the shape `DEF-320`
        # cost this product four job kinds of.
        schedules.install()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-003@c6c35b2 (EP-REP-01 §US-REP-003 · BR-REP-018 · apps/metering/apps.py, the precedent this copies)
# screens: S46
# generated: 2026-08-16 by story-coder (reports lane)
# checklist: A✔ B✔ C=deferred(registration only) D=deferred(no-API-half — registration only) E=deferred(no-frontend-half — registration only) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ pytest✔ run_gates✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
