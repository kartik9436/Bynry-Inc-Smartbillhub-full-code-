# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10591 — no screen could assign a route's reader (MQ-033).
# Ruling:   PO 2026-10-24 — assign/reassign on Reads → cycle → Routes;
#           supersedes CR-029 D6 and OQ-343 for that tab only.
# Rules:    BR-FLD-00087 (R87 — one predicate, `field_routes.reader_routes`) ·
#           CLAUDE.md hard rules 1 and 7 · B14 rule 31 (the reader by NAME)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""Assigning a route's reader: who may be one, who may do it, what the phone
then lists, what the trail says — and nothing crosses a tenant."""

from __future__ import annotations

import pytest

from apps.metering import api, field_routes, route_readers, selectors
from apps.metering import models as metering_models
from core import errors

from tests.test_cr187_reads_helpers import *  # noqa: F401,F403
from tests.test_cr187_reads_helpers import build_route, reader_actor, tenant_ctx
from tests.test_us_met_helpers import audit_rows  # noqa: F401 — the capture sink
from tests.test_us_ten_helpers import api_call, seeding_ctx

pytestmark = pytest.mark.django_db


def _membership(tenant, actor, *, role="field_technician", status="active", name="Ray Reader"):
    """`staff_actor` writes a `users` row and no membership; the reader rule is
    about the MEMBERSHIP, so the test writes the one it means."""
    from apps.identity import models as identity_models

    with seeding_ctx(tenant):
        identity_models.TenantMembership.objects.update_or_create(
            tenant=tenant,
            user_id=actor.id,
            defaults={"role": identity_models.Role.objects.get(code=role), "status": status},
        )
        identity_models.User.objects.filter(pk=actor.id).update(full_name=name)
    return actor


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        ray = _membership(brazos, reader_actor(brazos))
        mia = _membership(
            brazos, reader_actor(brazos, email="mia@brazosbendutilities.test"), name="Mia Ortiz"
        )
        route = build_route(brazos, dana, ray)
        # Start from an UNASSIGNED route: the fixture assigns Ray directly,
        # which is the shortcut this defect is about.
        metering_models.Route.objects.filter(pk=route.route_id).update(assigned_to_id=None)
    return {"tenant": brazos, "admin": dana, "ray": ray, "mia": mia, "route": route}


def _route_ids(route):
    return [str(route.route_id)]


def test_assigning_a_reader_puts_the_route_on_their_phone(world):
    with tenant_ctx(world["tenant"]):
        assert field_routes.my_routes(world["ray"])["count"] == 0
        out = route_readers.set_reader(
            world["admin"], {"route_ids": _route_ids(world["route"]), "reader_id": str(world["ray"].id)}
        )
        assert (out["updated"], out["unchanged"]) == (1, 0)
        assert out["routes"][0]["reader"] == {"id": str(world["ray"].id), "name": "Ray Reader"}
        assert field_routes.my_routes(world["ray"])["count"] == 1


def test_the_routes_list_serves_the_reader_by_name(world):
    with tenant_ctx(world["tenant"]):
        route_readers.set_reader(
            world["admin"], {"route_ids": _route_ids(world["route"]), "reader_id": str(world["ray"].id)}
        )
        row = metering_models.Route.objects.get(pk=world["route"].route_id)
        single = selectors.route_dict(row)
        paged = selectors.route_dict(row, batch=selectors.RouteBatch([row]))
    assert single["reader"] == paged["reader"] == {"id": str(world["ray"].id), "name": "Ray Reader"}


def test_reassigning_moves_the_route_and_audits_old_and_new(world, audit_rows):
    with tenant_ctx(world["tenant"]):
        ids = _route_ids(world["route"])
        route_readers.set_reader(world["admin"], {"route_ids": ids, "reader_id": str(world["ray"].id)})
        route_readers.set_reader(world["admin"], {"route_ids": ids, "reader_id": str(world["mia"].id)})
        assert field_routes.my_routes(world["ray"])["count"] == 0
        assert field_routes.my_routes(world["mia"])["count"] == 1
    rows = [row for row in audit_rows if row["action"] == route_readers.AUDIT_ACTION]
    assert len(rows) == 2
    last = rows[-1]
    assert str(last["entity_id"]) == str(world["route"].route_id)
    assert last["before"]["assigned_to"] == str(world["ray"].id)
    assert last["before"]["reader"] == "Ray Reader"
    assert last["after"]["assigned_to"] == str(world["mia"].id)
    assert last["after"]["reader"] == "Mia Ortiz"
    assert last["before"]["route"] == "WLK-07"
    assert str(last["actor_user_id"]) == str(world["admin"].id)


def test_the_same_reader_again_is_not_an_event(world, audit_rows):
    with tenant_ctx(world["tenant"]):
        ids = _route_ids(world["route"])
        route_readers.set_reader(world["admin"], {"route_ids": ids, "reader_id": str(world["ray"].id)})
        out = route_readers.set_reader(
            world["admin"], {"route_ids": ids, "reader_id": str(world["ray"].id)}
        )
    count = len([row for row in audit_rows if row["action"] == route_readers.AUDIT_ACTION])
    assert (out["updated"], out["unchanged"]) == (0, 1)
    assert count == 1


def test_unassigning_takes_the_route_off_every_phone(world):
    with tenant_ctx(world["tenant"]):
        ids = _route_ids(world["route"])
        route_readers.set_reader(world["admin"], {"route_ids": ids, "reader_id": str(world["ray"].id)})
        out = route_readers.set_reader(world["admin"], {"route_ids": ids, "reader_id": None})
        assert out["routes"][0]["reader"] is None
        assert field_routes.my_routes(world["ray"])["count"] == 0
        assert metering_models.Route.objects.get(pk=world["route"].route_id).assigned_to_id is None


def test_many_routes_in_one_request(world, brazos, dana):
    with tenant_ctx(brazos):
        second = metering_models.Route.objects.create(tenant=brazos, code="WLK-08", name="Oak")
        out = route_readers.set_reader(
            dana,
            {
                "route_ids": [str(world["route"].route_id), str(second.id)],
                "reader_id": str(world["mia"].id),
            },
        )
        assert out["updated"] == 2
        assert field_routes.my_routes(world["mia"])["count"] == 2


@pytest.mark.parametrize(
    "kind",
    ["clerk", "invited_technician", "deactivated_technician", "unknown"],
)
def test_only_an_active_field_technician_may_be_the_reader(world, kind):
    tenant = world["tenant"]
    with tenant_ctx(tenant):
        if kind == "clerk":
            who = _membership(tenant, reader_actor(tenant, email="cl@b.test"), role="billing_clerk")
            reader_id = str(who.id)
        elif kind == "invited_technician":
            who = _membership(tenant, reader_actor(tenant, email="inv@b.test"), status="invited")
            reader_id = str(who.id)
        elif kind == "deactivated_technician":
            who = _membership(tenant, reader_actor(tenant, email="off@b.test"), status="deactivated")
            reader_id = str(who.id)
        else:
            reader_id = "00000000-0000-0000-0000-000000000001"
        with pytest.raises(errors.ValidationError) as caught:
            route_readers.set_reader(
                world["admin"], {"route_ids": _route_ids(world["route"]), "reader_id": reader_id}
            )
        assert caught.value.message_key == "metering.routeReader.notTechnician"
        assert metering_models.Route.objects.get(pk=world["route"].route_id).assigned_to_id is None


def test_no_route_named_is_refused(world):
    with tenant_ctx(world["tenant"]):
        with pytest.raises(errors.ValidationError) as caught:
            route_readers.set_reader(world["admin"], {"route_ids": [], "reader_id": None})
    assert caught.value.message_key == "metering.routeReader.noRoutes"


def test_another_tenants_route_is_a_404_and_nothing_moves(world, lonestar):
    """HR-1 — one foreign id refuses the WHOLE request, as not-found."""
    with tenant_ctx(lonestar):
        theirs = metering_models.Route.objects.create(
            tenant=lonestar, code="LS-01", name="Lone Star walk"
        )
    with tenant_ctx(world["tenant"]):
        with pytest.raises(errors.NotFoundError):
            route_readers.set_reader(
                world["admin"],
                {
                    "route_ids": [str(world["route"].route_id), str(theirs.id)],
                    "reader_id": str(world["ray"].id),
                },
            )
        assert metering_models.Route.objects.get(pk=world["route"].route_id).assigned_to_id is None


def test_another_tenants_technician_cannot_be_the_reader(world, lonestar):
    with tenant_ctx(lonestar):
        theirs = _membership(lonestar, reader_actor(lonestar, email="ls.reader@lsrwater.test"))
    with tenant_ctx(world["tenant"]):
        with pytest.raises(errors.ValidationError):
            route_readers.set_reader(
                world["admin"],
                {"route_ids": _route_ids(world["route"]), "reader_id": str(theirs.id)},
            )
        # …and the picker never lists them.
        names = [row.user.email for row in route_readers.reader_choices_queryset()]
    assert "ls.reader@lsrwater.test" not in names
    assert sorted(names) == ["mia@brazosbendutilities.test", "ray.reader@brazosbendutilities.test"]


@pytest.mark.parametrize("role, status", [("billing_clerk", 200), ("system_admin", 200), ("executive", 403), ("field_technician", 403)])
def test_the_door_is_for_the_office_roles_that_do_the_work(world, role, status):
    response = api_call(
        api.route_reader,
        "post",
        user=world["admin"].user,
        role=role,
        tenant=world["tenant"],
        data={"route_ids": _route_ids(world["route"]), "reader_id": str(world["ray"].id)},
    )
    assert response.status_code == status


def test_the_picker_door_pages_and_searches(world):
    response = api_call(
        api.route_reader_choices,
        "get",
        user=world["admin"].user,
        role="billing_clerk",
        tenant=world["tenant"],
        query={"q": "mia"},
    )
    assert response.status_code == 200
    assert response.data["count"] == 1
    row = response.data["results"][0]
    assert row["email"] == "mia@brazosbendutilities.test"
    assert set(row) == {"id", "name", "email"}
