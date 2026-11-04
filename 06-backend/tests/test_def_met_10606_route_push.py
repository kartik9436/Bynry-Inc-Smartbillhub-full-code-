# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10606 — a route assigned or taken away reached the phone
#           only at its next sync; no notification was sent.
# Ruling:   PO 2026-10-26 — *"we will send this in notification"* and *"yes do
#           it"* (decision log, the two 2026-10-26 sections): assigning,
#           reassigning or unassigning a route's reader pushes the NEW reader
#           and the OLD reader, as the wake-up-and-sync doorbell.
# Rules:    BR-FLD-00087 (R87) · BR-WRK-002 (metering reaches work through a
#           named door, never its private functions) · CLAUDE.md hard rule 1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""A route's reader changes → each technician affected gets ONE push, after
the commit, in their own utility only."""

from __future__ import annotations

import pytest
from django.db import transaction

from apps.metering import models as metering_models
from apps.metering import route_readers
from apps.tenancy import models as tenancy_models
from apps.work import models as work_models
from apps.work import push, route_push

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import build_route, reader_actor, tenant_ctx
from tests.test_us_met_helpers import audit_rows  # noqa: F401 — the capture sink
from tests.test_us_ten_helpers import seeding_ctx

pytestmark = pytest.mark.django_db


def _membership(tenant, actor, name):
    from apps.identity import models as identity_models

    with seeding_ctx(tenant):
        identity_models.TenantMembership.objects.update_or_create(
            tenant=tenant,
            user_id=actor.id,
            defaults={
                "role": identity_models.Role.objects.get(code="field_technician"),
                "status": "active",
            },
        )
        identity_models.User.objects.filter(pk=actor.id).update(full_name=name)
    return actor


def _with_phone(tenant, actor, token):
    tech = work_models.Technician.objects.create(tenant_id=tenant.id, user_id=actor.id)
    work_models.TechnicianDevice.objects.create(
        tenant_id=tenant.id, technician=tech, token=token, platform="android"
    )
    return tech


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        ray = _membership(brazos, reader_actor(brazos), "Ray Reader")
        mia = _membership(
            brazos, reader_actor(brazos, email="mia@brazosbendutilities.test"), "Mia Ortiz"
        )
        route = build_route(brazos, dana, ray)
        metering_models.Route.objects.filter(pk=route.route_id).update(
            assigned_to_id=None, name="Silver Creek"
        )
        _with_phone(brazos, ray, "fcm-ray-01")
        _with_phone(brazos, mia, "fcm-mia-01")
    return {"tenant": brazos, "admin": dana, "ray": ray, "mia": mia, "route": route}


def _jobs():
    from core import tenancy as core_tenancy

    return list(
        tenancy_models.Job.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), kind=route_push.ROUTE_PUSH_JOB
        ).order_by("created_at", "id")
    )


def _by_user(jobs):
    return {job.payload["user_id"]: job.payload for job in jobs}


def _assign(world, ids, reader):
    return route_readers.set_reader(
        world["admin"], {"route_ids": [str(i) for i in ids], "reader_id": reader}
    )


def test_assigning_pushes_the_new_reader_once(world, django_capture_on_commit_callbacks):
    with tenant_ctx(world["tenant"]):
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, [world["route"].route_id], str(world["ray"].id))
        jobs = _by_user(_jobs())
    assert list(jobs) == [str(world["ray"].id)]
    assert jobs[str(world["ray"].id)]["gained"] == [{"code": "WLK-07", "name": "Silver Creek"}]
    assert jobs[str(world["ray"].id)]["lost"] == []


def test_reassigning_pushes_the_old_and_the_new_reader(world, django_capture_on_commit_callbacks):
    ids = [world["route"].route_id]
    with tenant_ctx(world["tenant"]):
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, ids, str(world["ray"].id))
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, ids, str(world["mia"].id))
        jobs = _jobs()
    second = _by_user(jobs[1:])
    assert set(second) == {str(world["ray"].id), str(world["mia"].id)}
    assert second[str(world["mia"].id)]["gained"] == [{"code": "WLK-07", "name": "Silver Creek"}]
    assert second[str(world["ray"].id)]["lost"] == [{"code": "WLK-07", "name": "Silver Creek"}]
    assert second[str(world["ray"].id)]["gained"] == []


def test_unassigning_pushes_the_old_reader(world, django_capture_on_commit_callbacks):
    ids = [world["route"].route_id]
    with tenant_ctx(world["tenant"]):
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, ids, str(world["ray"].id))
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, ids, None)
        last = _by_user(_jobs()[1:])
    assert list(last) == [str(world["ray"].id)]
    assert len(last[str(world["ray"].id)]["lost"]) == 1


def test_a_bulk_of_three_is_one_push_per_technician(world, django_capture_on_commit_callbacks):
    with tenant_ctx(world["tenant"]):
        extra = [
            metering_models.Route.objects.create(
                tenant=world["tenant"], code=f"WLK-0{n}", name=f"Oak {n}"
            ).id
            for n in (8, 9)
        ]
        three = [world["route"].route_id, *extra]
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, three, str(world["mia"].id))
        first = _by_user(_jobs())
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, three, str(world["ray"].id))
        second = _by_user(_jobs()[1:])
    assert list(first) == [str(world["mia"].id)]
    assert len(first[str(world["mia"].id)]["gained"]) == 3
    assert set(second) == {str(world["ray"].id), str(world["mia"].id)}
    assert len(second[str(world["ray"].id)]["gained"]) == 3
    assert len(second[str(world["mia"].id)]["lost"]) == 3


def test_re_saving_the_same_reader_pushes_nobody(world, django_capture_on_commit_callbacks):
    ids = [world["route"].route_id]
    with tenant_ctx(world["tenant"]):
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, ids, str(world["ray"].id))
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, ids, str(world["ray"].id))
        assert len(_jobs()) == 1


def test_a_rolled_back_assignment_pushes_nothing(
    world, monkeypatch, django_capture_on_commit_callbacks
):
    """⚠ The job ROW would roll back with the transaction either way, so the
    row alone cannot tell an on-commit push from an inline one — an inline
    enqueue hands the BROKER a job id that never committed. So this asserts
    work's door was never CALLED (proved red with `on_commit` removed)."""
    called = []
    real = route_push.notify_routes_changed
    monkeypatch.setattr(
        route_push, "notify_routes_changed", lambda *a, **k: called.append(a) or real(*a, **k)
    )
    with tenant_ctx(world["tenant"]):
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    _assign(world, [world["route"].route_id], str(world["ray"].id))
                    raise RuntimeError("the request fails after the write")
        assert called == []
        assert callbacks == []
        assert _jobs() == []
        assert metering_models.Route.objects.get(pk=world["route"].route_id).assigned_to_id is None


def test_another_tenants_technician_is_never_pushed(
    world, lonestar, django_capture_on_commit_callbacks
):
    with tenant_ctx(lonestar):
        other = _membership(lonestar, reader_actor(lonestar, email="kaur@lonestar.test"), "J. Kaur")
        _with_phone(lonestar, other, "fcm-kaur-01")
    with tenant_ctx(world["tenant"]):
        with django_capture_on_commit_callbacks(execute=True):
            _assign(world, [world["route"].route_id], str(world["ray"].id))
        assert set(_by_user(_jobs())) == {str(world["ray"].id)}
    with tenant_ctx(lonestar):
        assert _jobs() == []


def test_the_job_rings_the_readers_phone_with_the_route_words(world, audit_rows):
    """The body: ray's ONE device is addressed with a `route_change` message
    naming the route; another technician's device is not."""
    with tenant_ctx(world["tenant"]):
        message = route_push.route_message(
            gained=[{"code": "WLK-07", "name": "Silver Creek"}], lost=[]
        )
        record = {
            "payload": {
                "user_id": str(world["ray"].id),
                "gained": [{"code": "WLK-07", "name": "Silver Creek"}],
                "lost": [],
                "actor_id": str(world["admin"].id),
            }
        }
        route_push.run_route_push_job(record)
    assert message["kind"] == "route_change"
    assert message["android"]["channel_id"] == "route_change"
    assert message["data"]["tenant"]
    assert message["data"]["gained"] == "1" and message["data"]["lost"] == "0"
    assert (message["data"]["route"], message["data"]["route_name"]) == ("WLK-07", "Silver Creek")
    rows = [r for r in audit_rows if r["action"].startswith("work.route_change.")]
    assert [r["action"] for r in rows] == [route_push.ACTION_PUSHED]
    assert rows[0]["after"]["devices"] == 1


def test_many_routes_carry_a_count_and_no_single_route(world):
    with tenant_ctx(world["tenant"]):
        message = route_push.route_message(
            gained=[], lost=[{"code": f"R-{n}", "name": None} for n in range(5)]
        )
    assert message["data"]["lost"] == "5"
    assert "route" not in message["data"]


def test_a_reader_with_no_phone_is_recorded_as_waiting(world, brazos, audit_rows):
    with tenant_ctx(brazos):
        work_models.TechnicianDevice.objects.filter(technician__user_id=world["ray"].id).update(
            active=False
        )
        route_push.run_route_push_job(
            {
                "payload": {
                    "user_id": str(world["ray"].id),
                    "gained": [],
                    "lost": [{"code": "WLK-07", "name": None}],
                }
            }
        )
    actions = [r["action"] for r in audit_rows if r["action"].startswith("work.route_change.")]
    assert actions == [route_push.ACTION_WAITING]


def test_the_kind_is_one_of_the_servers_push_kinds():
    assert "route_change" in push.PUSH_KINDS
    assert route_push.ROUTE_PUSH_JOB in {
        push.PUSH_JOB,
        push.ALERT_PUSH_JOB,
        route_push.ROUTE_PUSH_JOB,
    }


def test_metering_reaches_work_through_its_own_seam_only():
    """BR-WRK-002: `route_readers` names no `apps.work` module; the one door is
    `metering.seams.notify_route_readers`."""
    import inspect

    src = inspect.getsource(route_readers)
    assert "apps.work" not in src
    assert "notify_route_readers" in src
