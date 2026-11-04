# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-006 (the template registry + its append-only version rows —
#           this makes them visible to the app registry)   Screens: S8 · S67
# Rules:    CLAUDE.md rule 1 (every table registered here is tenant-scoped and
#           RLS-forced by migration 0006) · BR-BIL-026 (the version rows this
#           registers are what a document pins to)
# Change:   CR-048 wave B task B5 — `ready()` installs the dispatch schedule.
#           This is the WIRING half of it; `schedule.py` is the schedule.
# Tests:    06-backend/tests/test_us_not_006_template_lifecycle.py ·
#           06-backend/tests/test_cr048_b_engine_on.py (CR-048 B5)
# Impacts:  apps/notifications/migrations (which cannot see a model the app
#           registry has not loaded) · apps/notifications/schedule.py (installed
#           here, and dead code without this call) · docker-compose.yml's beat
#           service, which until now had nothing to fire
# ───────────────────────────────────────────────────────
"""notifications AppConfig — model registration only, no logic.

It exists for one reason, and `apps/payments/apps.py` exists for the same one:
Django imports `apps.notifications.models` and nothing else, and the US-NOT-006
tables are not in that file. They are in `template_models.py`, because
`models.py` carries US-NOT-001's Trace header and G10 reads a Trace US-ID as
"this file ships that story's test cases" — two stories in one models module
would make that claim false for both, and two lanes in one models module is how
a migration graph forks.

`ready()` imports the module, so the model classes register themselves exactly
as they would have from `models.py`. Folding them back in later is a move, not a
redesign.

⚠ **AMENDED 2026-08-29 (CR-048 wave B, task B5).** This paragraph used to read
*"Nothing else belongs here. Notifications registers no reference-data handler,
no exporter and no signal."* It still registers none of those three — and it now
installs ONE thing more: the dispatch schedule.

`ready()` is where a celery-beat entry has to be registered, because it is the
one hook that runs in every process that could be beat, once, after the app
registry is loaded. `schedule.install()` is a pure registration — it starts
nothing, contacts no broker, reads no clock and touches no table — and it is
what turns `dispatcher.dispatch_cycle` from a function an operator can type into
a cycle that actually runs. Before it, three separate files in this repo
recorded that nothing scheduled the dispatcher; hard-won law 2 is the reason
that sentence is not just left standing beside a correct schedule nobody calls.
"""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"  # unchanged from Django's default, so no migration moves
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Imported for its side effect: defining a model registers it.
        from apps.notifications import template_models  # noqa: F401

        # CR-009 (2026-08-17): the SET-12 event matrix's own tables, in
        # `rule_models.py` for the same reason `template_models.py` exists —
        # `models.py` carries US-NOT-001's Trace header and G10 reads any
        # US-ID inside that block as "this file ships that story's cases".
        from apps.notifications import rule_models  # noqa: F401

        # `CR-198-BRC10` — text-message delivery statuses and STOP replies,
        # landed once each (`sms_feedback_models.py`).
        from apps.notifications import sms_feedback_models  # noqa: F401

        # ⚠ CR-048 wave B task B5 — THIS LINE IS THE WIRING, and the docstring
        # above used to say "nothing else belongs here" (amended below).
        #
        # `schedule.py` registers the dispatch cycle with celery beat. Without
        # this call the schedule is a correct dict nobody reads: beat connects
        # to the broker and fires nothing, which is exactly the state
        # `docker-compose.yml`, `dispatcher.py` and `dispatch_outbound.py` each
        # recorded, and exactly the shape of hard-won law 2. `install()` never
        # raises — a deployment with no celery gets `installed: False` in the
        # log and an application that starts.
        from apps.notifications import schedule

        schedule.install()

        # CR-188-BRC10 — the immediate send's job body and its named queue
        # (`account_access`). Both halves of the routing; the consumer is
        # docker-compose.yml's `celery-account-access`.
        from apps.notifications import send_now

        send_now.register()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-006@9a4f21c (the four US-NOT-006 sources — EP-NOT-02 §1/§3/§5 · 10-notifications/02-business-rules.md · 04-flows.md §2 · J22/T4-08/T4-09/T5-02)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — the template store)
# checklist: A✔ B=deferred(plumbing — the guarded laws live in template_models.py and migrations 0005/0006) C✔ D=deferred(no API call — registration only) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check clean, which is what proves the registry sees the models · pytest tests/test_us_not_006_template_lifecycle.py
# exceptions: (0) [CR-048 B5, 2026-08-29] `ready()` NOW DOES ONE THING BESIDES MODEL REGISTRATION: it installs the celery-beat dispatch entry. Proved RED before green (hard-won law 7) — with the `schedule.install()` line removed, `app.conf.beat_schedule` read `{}` and neither task was registered. `install()` never raises: a deployment without celery logs `installed: False` and the application starts.
#         (1) this AppConfig exists ONLY so the US-NOT-006 models can live
#         outside `models.py` while that file carries US-NOT-001's Trace header —
#         the same reason `apps/payments/apps.py` gives. The fold-back is a move
#         rather than a redesign.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
