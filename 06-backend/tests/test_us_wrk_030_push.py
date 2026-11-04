# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-030 (EP-WRK-05) TC-1..TC-6 — the push to the technician's
#           phone on assignment.  Screens: Work-007, Work-008 (Audit), Work-010
# Rules:    BR-WRK-034 (push on assignment; the audit line) · BR-WRK-025 (the
#           push is a consequence of the assign row, never a second act) ·
#           B12 r1 §3 (the job row before the broker message) · TD-17 ·
#           hard rule 1 (tenant scope) · hard rule 7 (audit_log)
# Defect:   DEF-WRK-4041 (the edit screen promised the phone updates and the
#           edit path never pushed) — `test_tc4_c` is its permanent guard
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-030 — the push, by TC. **Run with `JOBS_EAGER=false --reuse-db`.**

The story's TC-6 asks for that setting by name, and `DEF-567` records why:
`JOBS_EAGER` defaults to TRUE under the local settings and seeds a whole sample
utility per fixture — one lane measured a twelve-file run at an hour that took
four minutes with it off. Under the TEST settings (which is what this suite
runs) eager is already off, so what TC-6 is really asking is that these
assertions be made against the REAL queue shape — a job ROW that exists and is
`queued` — and not against a body that ran inline inside the request. Every
assertion below reads the row.

⚠ **THE HARDEST THING HERE IS THE AUDIT LINE, NOT THE QUEUE.** `BR-WRK-034`
gives the sentence *Dispatched · pushed to phone*; `US-WRK-030` TC-2 gives the
case that makes it hard — a technician with NO registered device — and requires
*Dispatched · waiting for the phone*, **never** *pushed* when it was not. The
choice is made from a COUNT of active device rows, so the tests assert the two
audit ACTIONS by name rather than trusting the intention behind them.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.audit import models as audit_models
from apps.tenancy import models as tenancy_models
from apps.work import dispatch, edit, mobile, push
from apps.work import models as work_models
from core import audit as core_audit
from core import jobs as core_jobs

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


# ── fixture: four jobs for D. Ortiz on Wed 15 Mar, and a device token ───────
#
# `US-WRK-030` §4: D. Ortiz's device token `fxtr-ortiz-01`; R. Patel's
# `fxtr-patel-01`; J. Kaur with none.
def _technician(tenant_id, email, name):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant_id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant_id, user=user)


def _device(tenant_id, technician, token):
    return work_models.TechnicianDevice.objects.create(
        tenant_id=tenant_id, technician=technician, token=token, platform="web"
    )


def _order(actor, address="221 Oak Ave", service="electric"):
    """One order on a premises.

    ⚠ **`service` IS A PARAMETER BECAUSE LONE STAR RIDGE IS WATER ONLY.** The
    isolation fixture's tenant has no electric service enabled, and
    `create_work_order` refuses a premises offering one it does not sell — so a
    hardcoded `electric` here would make TC-5 fail for a reason that has nothing
    to do with what it is testing.
    """
    premises = make_premises(actor, address_line=address, services_available=[service])
    return w6.create_work_order(
        actor, None, {"premises_id": str(premises["id"]), "type": "Meter exchange"}
    )


def _job_rows(kind=push.PUSH_JOB):
    """This TENANT's push jobs.

    ⚠ **THE TENANT FILTER IS EXPLICIT AND HAS TO BE.** `jobs` carries RLS FORCE
    on PostgreSQL, and the suite runs on SQLite, which has none — so a query
    with no tenant clause sees BOTH utilities' rows here and neither in
    production. TC-5 is the test that would have been silently meaningless.
    """
    from core import tenancy as core_tenancy

    return list(
        tenancy_models.Job.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), kind=kind
        ).order_by("created_at", "id")
    )


def _audit_actions(rows, entity_id):
    """The actions written for one entity, READ FROM THE CAPTURE SINK.

    ⚠ **NOT FROM `AuditLog.objects`, AND THIS COST A DEBUGGING ROUND.** The
    `audit_rows` fixture in `test_us_met_helpers` is AUTOUSE and replaces the
    audit sink with a list, so in these suites nothing reaches the table at all
    — a query against it answers *no row* for every row, which is a check that
    cannot tell pass from fail. `test_cr059_cs30_cheques.py` records the same
    trap for its own reason (the live table is month-partitioned and holds
    `entity_id` as a UUID this path carries as a string).
    """
    target = str(entity_id)
    return [row["action"] for row in rows if str(row.get("entity_id")) == target]


# ══════════════════════════════════════════════════════════════════════════
# TC-1 — the job ROW exists BEFORE the broker message, and the audit line
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_a_a_work_push_job_row_exists_after_assignment(dana, brazos):
    """TC-1 — assigning writes a `work.push` job row on the `work` queue.

    ⚠ **THE ROW, NOT THE MESSAGE.** `core.jobs.enqueue` saves the record and
    only then hands it to the dispatcher, so a broker that is down loses a
    MESSAGE and never a RECORD. The tempting shape — fire the message and write
    the row in the callback — loses work silently, which is why this asserts
    the row's existence rather than that something was dispatched.
    """
    with tenant_ctx(brazos):
        tid = brazos.id
        ortiz = _technician(tid, "ortiz@brazosbend.example", "D. Ortiz")
        _device(tid, ortiz, "fxtr-ortiz-01")
        order = _order(dana)
        result = dispatch.record_act(
            dana, order["id"], {"act": "assign", "technician_id": str(ortiz.id)}
        )
        rows = _job_rows()
        assert len(rows) == 1, "one assignment, one push job"
        assert rows[0].kind == "work.push"
        assert rows[0].status == "queued"
        assert result["push_job_id"] == str(rows[0].id)


def test_tc1_b_the_kind_is_routed_to_the_work_queue(dana, brazos):
    """TC-1 — the ROUTING half. `docker-compose.yml`'s `celery-work` is the
    consumer half and `G109` checks the two against each other; this asserts
    only that the kind carries a queue name at all, because a kind with none
    rides the default queue and the CPU cap bounds nothing."""
    assert core_jobs.job_queue(push.PUSH_JOB) == "work"
    assert core_jobs.job_handler(push.PUSH_JOB) is not None


def test_tc1_c_running_the_body_writes_dispatched_pushed(dana, brazos, audit_rows):
    """TC-1 — *Dispatched · pushed to phone*, written by the JOB.

    Not by the assignment: at assignment time nothing has counted the devices,
    so a line written there would say *pushed* over a technician whose phone was
    never addressed.
    """
    with tenant_ctx(brazos):
        tid = brazos.id
        ortiz = _technician(tid, "ortiz@brazosbend.example", "D. Ortiz")
        _device(tid, ortiz, "fxtr-ortiz-01")
        order = _order(dana)
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        push.run_push_job(_record())
        assert push.ACTION_PUSHED in _audit_actions(audit_rows, order["id"])


def _record():
    """The job record as the kernel hands it to a body — `{payload: {...}}`."""
    row = _job_rows()[0]
    return {"id": str(row.id), "payload": row.payload}


# ══════════════════════════════════════════════════════════════════════════
# TC-2 — no registered token: the audit line must NOT say "pushed"
# ══════════════════════════════════════════════════════════════════════════
def test_tc2_a_no_device_writes_waiting_for_the_phone_never_pushed(dana, brazos, audit_rows):
    """TC-2 · **negative** — J. Kaur has no device.

    `US-WRK-030` TC-2, verbatim: *"the audit line reads Dispatched · waiting for
    the phone — never* pushed *when it was not."* This is the assertion the
    whole two-action design exists for, so it checks BOTH directions: the
    waiting action is present AND the pushed action is absent.
    """
    with tenant_ctx(brazos):
        tid = brazos.id
        kaur = _technician(tid, "kaur@brazosbend.example", "J. Kaur")
        order = _order(dana)
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(kaur.id)})
        push.run_push_job(_record())
        actions = _audit_actions(audit_rows, order["id"])
        assert push.ACTION_WAITING in actions
        assert push.ACTION_PUSHED not in actions, "the audit tab must not claim a push"


def test_tc2_b_an_inactive_device_is_not_a_device(dana, brazos, audit_rows):
    """TC-2 — a retired handset must not make the line read *pushed*.

    A technician whose phone was replaced has a row with `active = False`. If
    that counted, the audit tab would say *pushed to phone* about a handset in a
    drawer — which is the same lie TC-2 forbids, arriving by a different route.
    """
    with tenant_ctx(brazos):
        tid = brazos.id
        ortiz = _technician(tid, "ortiz@brazosbend.example", "D. Ortiz")
        stale = _device(tid, ortiz, "fxtr-ortiz-old")
        stale.active = False
        stale.save(update_fields=["active"])
        order = _order(dana)
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        push.run_push_job(_record())
        assert push.ACTION_WAITING in _audit_actions(audit_rows, order["id"])


# ══════════════════════════════════════════════════════════════════════════
# TC-3 — the push failing must not undo the assignment
# ══════════════════════════════════════════════════════════════════════════
def test_tc3_a_a_broker_failure_leaves_the_assignment_standing(dana, brazos, monkeypatch):
    """TC-3 · **negative** — *"the assignment stands; nothing is lost."*

    A dispatcher must not see *could not assign* because a broker was
    restarting. The assignment row, the cache and the audit row are all
    committed before the push is attempted, so a raise here costs the doorbell
    and never the job.
    """
    with tenant_ctx(brazos):
        tid = brazos.id
        ortiz = _technician(tid, "ortiz@brazosbend.example", "D. Ortiz")
        _device(tid, ortiz, "fxtr-ortiz-01")
        order = _order(dana)

        def _broker_is_down(*a, **k):
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(core_jobs, "enqueue", _broker_is_down)
        result = dispatch.record_act(
            dana, order["id"], {"act": "assign", "technician_id": str(ortiz.id)}
        )
        assert result["push_job_id"] is None
        assert result["dispatch_state"] == "scheduled"
        row = work_tables.WorkOrder.objects.get(pk=order["id"])
        assert row.assignee_technician_id == ortiz.id, "the assignment must stand"
        assert work_models.WorkOrderAssignment.objects.filter(work_order_id=row.id).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# TC-4 — reassignment pushes AGAIN, from BOTH doors (DEF-WRK-4041)
# ══════════════════════════════════════════════════════════════════════════
def test_tc4_a_reassignment_is_a_second_push_not_a_folded_one(dana, brazos):
    """TC-4 — *"D. Ortiz's phone drops the job; R. Patel's gains it; TWO audit
    lines."*

    ⚠ **THE SCOPE KEY IS PER ASSIGNMENT ROW AND THIS IS WHY.** An order-scoped
    key would fold the second push into the first — `core.jobs.enqueue` returns
    the existing active record for a repeated scope key (NFR-16) — and R. Patel
    would never be told.
    """
    with tenant_ctx(brazos):
        tid = brazos.id
        ortiz = _technician(tid, "ortiz@brazosbend.example", "D. Ortiz")
        patel = _technician(tid, "patel@brazosbend.example", "R. Patel")
        _device(tid, ortiz, "fxtr-ortiz-01")
        _device(tid, patel, "fxtr-patel-01")
        order = _order(dana)
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        dispatch.record_act(dana, order["id"], {"act": "unassign"})
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(patel.id)})
        assert len(_job_rows()) == 2, "two assigns → two pushes; unassign pushes nothing"


def test_tc4_b_unassign_pushes_nothing(dana, brazos):
    """TC-4 — the phone that LOST the job needs no push: the day list simply
    stops containing it on the next sync."""
    with tenant_ctx(brazos):
        tid = brazos.id
        ortiz = _technician(tid, "ortiz@brazosbend.example", "D. Ortiz")
        _device(tid, ortiz, "fxtr-ortiz-01")
        order = _order(dana)
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        before = len(_job_rows())
        dispatch.record_act(dana, order["id"], {"act": "unassign"})
        assert len(_job_rows()) == before


def test_tc4_c_the_edit_screen_pushes_too(dana, brazos):
    """TC-4 · **`DEF-WRK-4041`'s permanent guard** — the OTHER assignment door.

    `Work-021`'s Change effects box says *"Technician phone — job updates
    immediately"*. It said so from the day the screen shipped and the edit path
    pushed nothing: `record_act` was the only door that enqueued, and
    `edit.save_order_edit` reassigns through `dispatch.append_act`, which
    appends the row and the cache and enqueues nothing. R. Patel still got the
    job on his next ordinary sync, so **nothing anywhere looked wrong** — which
    is why it would have survived.

    ⚠ **THIS TEST IS THE DURABLE FIX, NOT THE ONE-LINE CALL.** A fourth
    assignment door that forgets goes red here, naming itself, rather than
    shipping a screen that promises a buzz nobody sends.
    """
    with tenant_ctx(brazos):
        tid = brazos.id
        ortiz = _technician(tid, "ortiz@brazosbend.example", "D. Ortiz")
        patel = _technician(tid, "patel@brazosbend.example", "R. Patel")
        _device(tid, ortiz, "fxtr-ortiz-01")
        _device(tid, patel, "fxtr-patel-01")
        order = _order(dana)
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        pushed_after_assign = len(_job_rows())

        # `CR-168-BRC10` P4.4 — a move off D. Ortiz now says why (lane ASSIGN,
        # image 13); without it the save is refused `work.dispatch.reason_required`.
        saved = edit.save_order_edit(
            dana, order["id"], {"technician_id": str(patel.id), "reason": "Closer to the site"}
        )
        assert saved["push_job_id"] is not None, (
            "the edit screen promises the phone updates immediately — DEF-WRK-4041"
        )
        assert len(_job_rows()) == pushed_after_assign + 1


# ══════════════════════════════════════════════════════════════════════════
# TC-5 — two tenants' pushes do not dedupe each other
# ══════════════════════════════════════════════════════════════════════════
def test_tc5_a_two_tenants_pushes_have_their_own_scope(dana, erin, brazos, lonestar):
    """TC-5 · **tenant isolation** — *"two scope keys; neither dedupes the
    other."*

    `core.jobs.enqueue` looks an active job up by `(tenant_id, kind,
    scope_key)`, so the tenant is already part of the identity; this asserts the
    consequence rather than the mechanism, because the consequence is what would
    be noticed — a utility whose technician never got told about a job because
    another utility had pushed one first.
    """
    with tenant_ctx(brazos):
        ortiz = _technician(brazos.id, "ortiz@brazosbend.example", "D. Ortiz")
        _device(brazos.id, ortiz, "fxtr-ortiz-01")
        order_b = _order(dana)
        dispatch.record_act(dana, order_b["id"], {"act": "assign", "technician_id": str(ortiz.id)})
        assert len(_job_rows()) == 1

    with tenant_ctx(lonestar):
        kaur = _technician(lonestar.id, "kaur@lonestar.example", "J. Kaur")
        _device(lonestar.id, kaur, "fxtr-kaur-01")
        order_l = _order(erin, service="water")
        dispatch.record_act(erin, order_l["id"], {"act": "assign", "technician_id": str(kaur.id)})
        # Lone Star sees exactly its own — the queryset runs under its tenant.
        assert len(_job_rows()) == 1


# ══════════════════════════════════════════════════════════════════════════
# The device register — the token is never handed back
# ══════════════════════════════════════════════════════════════════════════
def test_register_device_never_returns_the_token(dana, brazos):
    """The token is a bearer credential for a third-party service.

    The answer carries `device_id` and `last_four` — enough for a technician to
    recognise their own phone, useless to anybody who intercepts it. Asserted by
    scanning the whole response, because the failure mode is somebody adding a
    convenient `"token": token` to help the client debug.
    """
    with tenant_ctx(brazos):
        from apps.identity import models as identity_models

        ortiz = work_models.Technician.objects.create(
            tenant_id=brazos.id,
            user=identity_models.User.objects.create(
                tenant_id=brazos.id, email="ortiz2@brazosbend.example", full_name="D. Ortiz"
            ),
        )
        # Registering as the technician's OWN login is the real path; this
        # exercises the service directly with that login as the actor.
        actor = type("A", (), {"id": ortiz.user_id, "pk": ortiz.user_id})()
        body = mobile.register_device(actor, {"token": "fxtr-ortiz-01", "platform": "web"})
        assert body["last_four"] == "z-01"
        assert "fxtr-ortiz-01" not in str(body)


def test_register_device_twice_is_one_row(dana, brazos):
    """A service worker re-subscribes on every install and browser update, so
    *register* happens dozens of times per handset. Two rows for one phone would
    push the same job twice."""
    with tenant_ctx(brazos):
        from apps.identity import models as identity_models

        ortiz = work_models.Technician.objects.create(
            tenant_id=brazos.id,
            user=identity_models.User.objects.create(
                tenant_id=brazos.id, email="ortiz3@brazosbend.example", full_name="D. Ortiz"
            ),
        )
        actor = type("A", (), {"id": ortiz.user_id, "pk": ortiz.user_id})()
        first = mobile.register_device(actor, {"token": "fxtr-ortiz-01"})
        second = mobile.register_device(actor, {"token": "fxtr-ortiz-01"})
        assert first["device_id"] == second["device_id"]
        assert first["created"] is True and second["created"] is False
        assert work_models.TechnicianDevice.objects.filter(technician=ortiz).count() == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-030 (EP-WRK-05) · BR-WRK-034 · 10-execution-plan.md wave J task J4
# generated: 2026-09-05 by the CR-070 wave J build lane
# gates: pytest tests/test_us_wrk_030_push.py · G109 (the queue pair)
# exceptions: TC-6 asks for JOBS_EAGER=false --reuse-db; the TEST settings are already non-eager, so every assertion reads the job ROW rather than a body that ran inline — see the module docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
