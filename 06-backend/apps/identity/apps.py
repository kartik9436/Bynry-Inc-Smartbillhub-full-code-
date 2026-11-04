# ── Trace ──────────────────────────────────────────────
# Change:   CR-145-BRC08 task B10 — `ready()` installs the session-cleanup
#           beat entry. This is the WIRING half; `session_cleanup.py` is the
#           job.
# Rules:    CLAUDE.md hard-won law 2 (built is not wired — a beat entry that
#           is correct and one that is INSTALLED are two claims) · G132
#           (every module declaring a `BEAT_ENTRY` must call `install()` from
#           its own `ready()`)
# Tests:    06-backend/tests/test_cr145_session_settings.py (the four `test_t9_*`
#           cases). This line named a separate "session cleanup" test file that
#           never existed, until the backend lane checked it on 2026-09-28.
# Impacts:  docker-compose.yml's beat service, which until now had nothing
#           from this module to fire
# ───────────────────────────────────────────────────────
"""identity AppConfig — registration only, no logic.

⚠ **THIS FILE DID NOT EXIST BEFORE 2026-09-28 AND ITS ARRIVAL MOVES NOTHING.**
`INSTALLED_APPS` has always carried the string `"apps.identity"`, so Django
built a default `AppConfig` for it with `label = "identity"`. This class
declares the same label explicitly, which is the point: a label change would
rewrite every migration dependency in the product, and stating it means a
future edit to this file cannot cause one by accident.

It exists for one reason — `ready()` is where a celery-beat entry has to be
registered. It is the one hook that runs in every process that could be beat,
once, after the app registry is loaded.
"""

from django.apps import AppConfig


class IdentityConfig(AppConfig):
    name = "apps.identity"
    label = "identity"  # unchanged from Django's default, so no migration moves
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # ⚠ **`CR-145-BRC08` — THIS LINE IS THE ONLY THING THAT MAKES THE
        # NIGHTLY SWEEP REAL.** `session_cleanup.beat_schedule()` being
        # CORRECT and the entry being INSTALLED are two different claims, and
        # hard-won law 2 is about exactly that gap: without this call the
        # schedule is a well-tested dict nobody reads, beat connects to the
        # broker and fires nothing, and `sessions` goes on growing forever
        # with every test passing.
        #
        # `install()` is a pure registration — it starts nothing, contacts no
        # broker, reads no clock and touches no table — and it never raises. A
        # deployment with no celery gets `installed: False` in the log and an
        # application that starts.
        from apps.identity import session_cleanup

        session_cleanup.install()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-145-BRC08 task B10
# generated: 2026-09-28 by lane SESS-BACKEND
# checklist: A✔ B=n/a(registration only) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G132 · makemigrations --check clean (the label is unchanged, so the migration graph does not move)
# exceptions: none — this AppConfig adds a `ready()` and changes no label, no model and no migration.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
