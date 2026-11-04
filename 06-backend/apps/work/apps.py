# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (EP-WRK-01) — `apps/work/` exists, as the eleventh code
#           module, with its boundary enforced from the first commit.
# Rules:    BR-WRK-001 (Work is its own module — PO 2026-09-03, verbatim *"it
#           will become the module itself"*) · BR-WRK-002 (Work writes no other
#           module's tables; one read-only seam file per module; a gate) ·
#           CLAUDE.md module map (amended 2026-09-03 in the commit that carries
#           `metering/0044`, per `CR-070` §2(a))
# Tests:    06-backend/tests/test_us_wrk_005_module.py (TC-1: the app is
#           installed and the module map names it)
# Impacts:  config/settings/base.py DOMAIN_APPS gains "apps.work" beside
#           "apps.integrations"
# ───────────────────────────────────────────────────────
"""work AppConfig — the module exists; `ready()` registers nothing yet.

⚠ AMENDED 2026-10-21 (CR-187-BRC10 T-43): the six tables below now live in
`apps/work/connection_models.py` and Work owns them in its migration state
(`work/0046`); the services that write them are still metering's
(`apps/metering/connections.py`), reached through `seams/metering_seam.py`.
The paragraph is kept as the record of phase 0.

Phase 0 of `CR-070` gives this module no table of its own: the six tables it
will own (`connections`, `connection_services`, `work_orders`,
`work_order_templates`, `connection_todos`, `service_characteristics`) live in
`apps/metering/connections.py` today, and where they eventually LIVE is
`04-docs/05-modules/16-work/03-field-map.md` §4 — a decision for the lane that
writes `work/0001` after reading the blueprint's §16. Until then Work reads
them through `seams/metering_seam.py` and writes `work_orders` through exactly
one named door there (`raise_work_order`, which is metering's own
`create_work_order`).

Wave J added the second thing: the phone's push job (`work.push`) and the named
queue it rides (`work`), registered together in this `ready()` and in the same
commit as the worker that consumes them (`celery-work` in `docker-compose.yml`)
— the G59 shape, because a queue with no consumer accepts work and never runs.
Wave M added the third: the nightly rules sweep (`work.rules_sweep`), on
the same named queue, with its beat entry installed here too.
"""

from django.apps import AppConfig


class WorkConfig(AppConfig):
    name = "apps.work"
    label = "work"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Register the five Reference-data handlers this module owns.

        WAVE C, and the reason it is HERE rather than at import time: tenancy's
        `LOOKUP_LISTS` is the registry and `register_lookup_handler` refuses a
        code it does not declare, so the registration has to happen after both
        apps are loaded. Every other owning module (`apps/assets/lookups.py`,
        `apps/customers/lookups.py`, `apps/metering/lookups.py`) does exactly
        this, and `lookups.register()` logs-and-skips an undeclared code so a
        registry that has not landed a list cannot break startup.

        AND, since wave J, THE PHONE'S PUSH JOB — its body and its named queue,
        registered together (`core/jobs.py`'s contract: the module that owns the
        work owns both statements, or a rename moves one and not the other).
        The CONSUMER half shipped in the same commit: `celery-work`, `-Q work`,
        in `docker-compose.yml`. `G109` fails if either half goes missing,
        because a routed queue nothing drains accepts every push, answers
        *queued*, and runs none of them — which is `DEF-320` exactly.

        AND, SINCE WAVE M, THE NIGHTLY RULES SWEEP — `work.rules_sweep` on
        the same `work` queue, plus its celery-beat entry.
        """
        from apps.work import lookups, photo_links, push, rules, search_sources

        lookups.register()
        # CR-073 — the four Work groups of universal search. Registered HERE
        # for the same reason the lookups are: `core.search` is a registry and
        # a source must be handed to it after both apps are loaded. The three
        # tables behind two of these groups still live in metering, which is
        # why the source reads them through `seams/metering_seam.py` and why
        # G78 stays green over it.
        search_sources.register()
        push.register()
        # CR-168-BRC10 §F — a photograph's bytes are filed in the background.
        photo_links.register()
        # WAVE M — the nightly rule engine. THREE statements and they are three
        # different claims: the job's BODY, the QUEUE it rides, and the BEAT
        # ENTRY that fires it. `register()` does the first two (the
        # `push.register` shape); `install()` does the third and is the same
        # `ready()`-time installer `apps/notifications/schedule.py` and
        # `apps/payments/collections_schedule.py` already use — this product has
        # no `CELERY_BEAT_SCHEDULE` settings constant and this wave does not
        # invent a second mechanism for one entry.
        #
        # `install()` NEVER RAISES: a deployment without celery logs
        # `installed: False` and the application starts, exactly as
        # notifications does. A Django app that refused to boot because a
        # scheduler was absent would be a worse product than one whose rules
        # fire when the beat comes back.
        rules.register()
        rules.install()
        # CR-168-BRC10 round 5 (lane SRV-4) — the HOURLY escalation sweep
        # (P3.57) and P3.59's reminders: same three statements, same queue.
        from apps.work import escalations

        escalations.register()
        escalations.install()
        # CR-187-BRC10 Phase 13 (T-34) — the money-change push and its
        # one-minute sweep: same three statements, same `work` queue.
        from apps.work import money

        money.register()
        money.install()

        # CR-187-BRC10 T-41 (lane S-FIND) — R28's five minutes: the per-minute
        # emergency sweep, the same three statements on the same queue. The
        # alert PUSH job is registered by `push.register()` above.
        from apps.work import field_alerts

        field_alerts.register()
        field_alerts.install()

        # DEF-WRK-10615 — End shift's morning half: the hourly per-utility
        # return to *on shift*, the same three statements on the same queue.
        from apps.work import shift_morning

        shift_morning.register()
        shift_morning.install()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-005@87b94265 (EP-WRK-01 story + BR-WRK-001/002 snapshot; CR-070 §10 folder)
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint of its own) E=n/a(no screen — stated in the story) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_wrk_005_module.py · G78 (the boundary gate, shown RED first)
# exceptions: no model, no migration — deliberate; see the docstring and 03-field-map.md §4
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
