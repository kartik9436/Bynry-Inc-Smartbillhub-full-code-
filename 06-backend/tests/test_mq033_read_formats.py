# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 read formats: definitions, versions,
#           pointers, resolution, the Settings → Reads API and the handset's
#           copy on the route.
# Rules:    BR-MET-1210 … BR-MET-1214 · BR-MET-1218 (filter) · NFR-3
# Tests:    this file (SQLite) · test_mq033_read_answers.py ·
#           test_mq033_read_answers_pg.py
# ───────────────────────────────────────────────────────
"""Settings → Reads, end to end through the services and the routes.

RED FIRST (hard-won law 7): at `baf29dbca` (the branch tip before this lane)
every case here fails on `ImportError: cannot import name 'read_formats'`.

The worked example is the PO's own illustration (*"Water monthly walk v1"*,
B14 rule 37 — an illustration, used here as TEST DATA only): a seal check, a
follow-up photo when the seal is broken, and a job raised for it.
"""

from __future__ import annotations

import pytest

from apps.metering import field_routes, read_formats
from apps.metering import models as metering_models
from apps.metering.read_format_models import (
    ReadFormat,
    ReadFormatDefault,
    ReadFormatQuestion,
    ReadFormatVersion,
)
from core import errors

from tests.test_cr187_order_helpers import template
from tests.test_cr187_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_cr187_reads_helpers import build_route, reader_actor, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db


def _field_keys(exc):
    return {(fe["field"], fe["message_key"]) for fe in (exc.value.field_errors or [])}


def _seal_format(admin, *, name="Electric walk", publish=True, raise_template=None):
    fmt = read_formats.create_format(admin, {"name": name, "service": "electric"})
    fid = fmt["id"]
    read_formats.add_question(
        admin,
        fid,
        {"label": "Seal intact?", "data_type": "boolean", "is_required": True},
    )
    read_formats.add_question(
        admin,
        fid,
        {
            "label": "Photo of the seal",
            "data_type": "photo",
            "is_required": True,
            "show_if": {"question_key": "seal_intact", "answer": False},
        },
    )
    read_formats.add_question(
        admin,
        fid,
        {
            "label": "Meter condition",
            "data_type": "select",
            "options": ["Good", "Damaged", "Missing"],
            "asked_when": "every_reading",
            **(
                {"raise_work": {"on_answer": "Damaged", "template_id": str(raise_template)}}
                if raise_template
                else {}
            ),
        },
    )
    read_formats.add_question(
        admin, fid, {"label": "Why not read", "data_type": "text", "asked_when": "cant_read"}
    )
    if publish:
        read_formats.publish(admin, fid, {"change_note": "First"})
    return fid


@pytest.fixture()
def world(brazos, dana):
    with tenant_ctx(brazos):
        reader = reader_actor(brazos)
        route = build_route(brazos, dana, reader, history=False)
    return {"tenant": brazos, "admin": dana, "reader": reader, "route": route}


# ══════════════════════════════════════════════════════════════════════════
# Nothing seeded (BR-MET-1210)
# ══════════════════════════════════════════════════════════════════════════
def test_nothing_is_seeded_and_a_route_resolves_to_no_format(world):
    """*"we dont have to provide anything readymade"* — a tenant has no
    format, no question, no default; its route reads as it always did."""
    with tenant_ctx(world["tenant"]):
        assert ReadFormat.objects.count() == 0
        assert ReadFormatQuestion.objects.count() == 0
        assert ReadFormatDefault.objects.count() == 0
        route = metering_models.Route.objects.get(pk=world["route"].route_id)
        assert read_formats.resolve_read_format(route) is None
        page = field_routes.route_page(world["reader"], route.id)
        assert page["route"]["read_formats"] == [
            {"service": "electric", "source": None, "read_format": None}
        ]
        assert page["read_format_versions"] == []


# ══════════════════════════════════════════════════════════════════════════
# Defined like a custom field, plus Photo (BR-MET-1211)
# ══════════════════════════════════════════════════════════════════════════
def test_question_types_are_the_custom_field_types_plus_photo(world):
    from apps.tenancy.models import CUSTOM_FIELD_DATA_TYPES

    assert read_formats.data_types() == (*CUSTOM_FIELD_DATA_TYPES, "photo")


def test_a_question_is_validated_like_a_custom_field(world):
    admin = world["admin"]
    with tenant_ctx(world["tenant"]):
        fid = read_formats.create_format(admin, {"name": "Walk", "service": "electric"})["id"]
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(admin, fid, {"label": "Colour", "data_type": "select"})
        assert ("options", "errors.val-001") in _field_keys(exc)
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(admin, fid, {"label": "Colour", "data_type": "colour"})
        assert ("data_type", "settings.customFields.data_type_unknown") in _field_keys(exc)
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(
                admin, fid, {"label": "Seal", "data_type": "boolean", "asked_when": "sometimes"}
            )
        assert ("asked_when", "errors.val-005") in _field_keys(exc)
        out = read_formats.add_question(admin, fid, {"label": "Seal intact?", "data_type": "boolean"})
        # The key is DERIVED from the label exactly as a custom field's is.
        assert [q["key"] for q in out["draft"]["questions"]] == ["seal_intact"]
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(admin, fid, {"label": "Seal intact", "data_type": "text"})
        assert ("key", "metering.readFormats.key_taken") in _field_keys(exc)


def test_a_follow_up_must_point_at_an_earlier_question(world):
    """`show_if` names an EARLIER question of the same version, with an answer
    that question can receive — so no cycle can ever be written."""
    admin = world["admin"]
    with tenant_ctx(world["tenant"]):
        fid = read_formats.create_format(admin, {"name": "Walk", "service": "electric"})["id"]
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(
                admin, fid,
                {"label": "Photo", "data_type": "photo",
                 "show_if": {"question_key": "seal_intact", "answer": False}},
            )
        assert ("show_if", "metering.readFormats.show_if_earlier") in _field_keys(exc)
        read_formats.add_question(admin, fid, {"label": "Seal intact?", "data_type": "boolean"})
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(
                admin, fid,
                {"label": "Photo", "data_type": "photo",
                 "show_if": {"question_key": "seal_intact", "answer": "maybe"}},
            )
        assert ("show_if", "errors.val-002") in _field_keys(exc)
        read_formats.add_question(
            admin, fid,
            {"label": "Photo", "data_type": "photo",
             "show_if": {"question_key": "seal_intact", "answer": False}},
        )
        # Moving the follow-up above its parent would be a forward reference.
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.reorder_questions(admin, fid, {"keys": ["photo", "seal_intact"]})
        assert ("keys", "metering.readFormats.show_if_earlier") in _field_keys(exc)
        # A question another follows up on cannot be deleted from under it.
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.delete_question(admin, fid, "seal_intact")
        assert ("key", "metering.readFormats.question_in_use") in _field_keys(exc)
        # ...and the follow-up itself can be.
        out = read_formats.delete_question(admin, fid, "photo")
        assert [q["key"] for q in out["draft"]["questions"]] == ["seal_intact"]


def test_raise_work_must_name_a_published_job_template(world):
    admin, tenant = world["admin"], world["tenant"]
    with tenant_ctx(tenant):
        fid = read_formats.create_format(admin, {"name": "Walk", "service": "electric"})["id"]
        bogus = "019a0000-0000-7000-8000-000000000000"
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(
                admin, fid,
                {"label": "Condition", "data_type": "select", "options": ["Good", "Damaged"],
                 "raise_work": {"on_answer": "Damaged", "template_id": bogus}},
            )
        assert ("raise_work", "metering.readFormats.template_unpublished") in _field_keys(exc)
        tid = template(admin, tenant, "Meter repair")
        with pytest.raises(errors.ValidationError) as exc:
            read_formats.add_question(
                admin, fid,
                {"label": "Condition", "data_type": "select", "options": ["Good", "Damaged"],
                 "raise_work": {"on_answer": "Broken", "template_id": str(tid)}},
            )
        assert ("raise_work", "errors.val-002") in _field_keys(exc)
        out = read_formats.add_question(
            admin, fid,
            {"label": "Condition", "data_type": "select", "options": ["Good", "Damaged"],
             "raise_work": {"on_answer": "Damaged", "template_id": str(tid)}},
        )
        rw = out["draft"]["questions"][0]["raise_work"]
        assert rw["on_answer"] == "Damaged" and rw["template"]["name"] == "Meter repair"


# ══════════════════════════════════════════════════════════════════════════
# Versioned; a published version never changes (BR-MET-1213)
# ══════════════════════════════════════════════════════════════════════════
def test_publish_numbers_the_version_and_freezes_it(world):
    admin = world["admin"]
    with tenant_ctx(world["tenant"]):
        fid = read_formats.create_format(admin, {"name": "Walk", "service": "electric"})["id"]
        with pytest.raises(errors.BizError) as exc:
            read_formats.publish(admin, fid)
        assert exc.value.message_key == "metering.readFormats.no_questions"
        read_formats.add_question(admin, fid, {"label": "Seal intact?", "data_type": "boolean"})
        out = read_formats.publish(admin, fid, {"change_note": "First"})
        assert out["status"] == "published"
        assert out["current_version"]["version_no"] == 1
        assert out["draft_version_id"] is None
        v1 = out["current_version"]["id"]
        # No draft: editing is refused by name, never applied to v1.
        with pytest.raises(errors.BizError) as exc:
            read_formats.add_question(admin, fid, {"label": "Dog?", "data_type": "boolean"})
        assert exc.value.message_key == "metering.readFormats.published_locked"
        # Editing a published format opens a NEW draft, a copy of v1.
        draft = read_formats.new_draft(admin, fid)
        assert [q["key"] for q in draft["draft"]["questions"]] == ["seal_intact"]
        assert read_formats.new_draft(admin, fid)["draft_version_id"] == draft["draft_version_id"]
        read_formats.update_question(admin, fid, "seal_intact", {"label": "Is the seal intact?"})
        read_formats.add_question(admin, fid, {"label": "Dog on site?", "data_type": "boolean"})
        # v1 is exactly as it was published.
        assert [
            (q.key, q.label)
            for q in ReadFormatQuestion.objects.filter(version_id=v1).order_by("seq")
        ] == [("seal_intact", "Seal intact?")]
        out = read_formats.publish(admin, fid)
        assert out["current_version"]["version_no"] == 2
        assert ReadFormatVersion.objects.filter(read_format_id=fid).count() == 2


def test_only_a_published_format_can_be_pointed_at_and_retire_needs_it_unused(world):
    admin = world["admin"]
    with tenant_ctx(world["tenant"]):
        draft_id = read_formats.create_format(admin, {"name": "Draft", "service": "electric"})["id"]
        with pytest.raises(errors.BizError) as exc:
            read_formats.set_service_default(admin, "electric", {"read_format_id": draft_id})
        assert exc.value.message_key == "metering.readFormats.not_published"
        fid = _seal_format(admin)
        read_formats.set_service_default(admin, "electric", {"read_format_id": fid})
        with pytest.raises(errors.BizError) as exc:
            read_formats.retire(admin, fid)
        assert exc.value.message_key == "metering.readFormats.in_use"
        assert exc.value.params == {"routes": 0, "cycles": 0, "services": 1}
        read_formats.set_service_default(admin, "electric", {"read_format_id": None})
        assert read_formats.retire(admin, fid)["status"] == "retired"


def test_a_format_of_another_service_cannot_be_put_on_a_route(world):
    admin = world["admin"]
    with tenant_ctx(world["tenant"]):
        seeded_water = "water" in read_formats.seams.enabled_service_codes()
        if not seeded_water:
            pytest.skip("this fixture tenant does not sell water")
        fid = read_formats.create_format(admin, {"name": "Water", "service": "water"})["id"]
        read_formats.add_question(admin, fid, {"label": "Leak?", "data_type": "boolean"})
        read_formats.publish(admin, fid)
        with pytest.raises(errors.BizError) as exc:
            read_formats.set_route_formats(
                admin, {"route_ids": [world["route"].route_id], "read_format_id": fid}
            )
        assert exc.value.message_key == "metering.readFormats.service_mismatch"


# ══════════════════════════════════════════════════════════════════════════
# route → cycle → service → none (BR-MET-1212)
# ══════════════════════════════════════════════════════════════════════════
def test_resolution_route_over_cycle_over_service_and_replace_moves_the_pointer(world):
    """*"A route can override its cycle, and a cycle its service … we can
    create another format for same service and replace it later"*."""
    admin, w = world["admin"], world["route"]
    with tenant_ctx(world["tenant"]):
        service_fid = _seal_format(admin, name="Service default")
        cycle_fid = _seal_format(admin, name="Cycle format")
        route_fid = _seal_format(admin, name="Route format")
        route = lambda: metering_models.Route.objects.get(pk=w.route_id)  # noqa: E731

        read_formats.set_service_default(admin, "electric", {"read_format_id": service_fid})
        version, source = read_formats.resolve_with_source(route())
        assert (str(version.read_format_id), source) == (service_fid, "service")

        read_formats.set_cycle_format(admin, w.cycle_id, {"read_format_id": cycle_fid})
        version, source = read_formats.resolve_with_source(route())
        assert (str(version.read_format_id), source) == (cycle_fid, "cycle")

        read_formats.set_route_formats(admin, {"route_ids": [w.route_id], "read_format_id": route_fid})
        version, source = read_formats.resolve_with_source(route())
        assert (str(version.read_format_id), source) == (route_fid, "route")

        # Replace = move a pointer: the route's own pointer cleared falls back.
        read_formats.set_route_formats(admin, {"route_ids": [w.route_id], "read_format_id": None})
        assert str(read_formats.resolve_read_format(route()).read_format_id) == cycle_fid
        read_formats.set_cycle_format(admin, w.cycle_id, {"read_format_id": None})
        assert str(read_formats.resolve_read_format(route()).read_format_id) == service_fid

        # A new version moves the reading that comes AFTER it.
        read_formats.new_draft(admin, service_fid)
        read_formats.add_question(admin, service_fid, {"label": "Dog?", "data_type": "boolean"})
        read_formats.publish(admin, service_fid)
        assert read_formats.resolve_read_format(route()).version_no == 2


def test_the_route_carries_the_resolved_version_and_its_questions_to_the_phone(world):
    admin, w, reader = world["admin"], world["route"], world["reader"]
    with tenant_ctx(world["tenant"]):
        fid = _seal_format(admin)
        read_formats.set_cycle_format(admin, w.cycle_id, {"read_format_id": fid})
        mine = field_routes.my_routes(reader)["results"][0]
        entry = mine["read_formats"][0]
        assert entry["service"] == "electric" and entry["source"] == "cycle"
        assert entry["read_format"]["version_no"] == 1
        page = field_routes.route_page(reader, w.route_id)
        (version,) = page["read_format_versions"]
        assert version["id"] == entry["read_format"]["version_id"]
        assert [q["key"] for q in version["questions"]] == [
            "seal_intact", "photo_of_the_seal", "meter_condition", "why_not_read",
        ]
        follow = version["questions"][1]
        assert follow["show_if"] == {"question_key": "seal_intact", "answer": False}
        assert version["questions"][3]["asked_when"] == "cant_read"


# ══════════════════════════════════════════════════════════════════════════
# The API — paged, permissioned, the handset's door
# ══════════════════════════════════════════════════════════════════════════
def _call(view, tenant, actor, role, *, method="get", data=None, query="", **kwargs):
    """A request straight to a view, signed in as `actor` with `role` (the
    `test_cr187_gaps._call` shape)."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.identity import models as identity_models

    factory = APIRequestFactory()
    url = "/api/brazosbend/x" + (f"?{query}" if query else "")
    request = getattr(factory, method)(url, data, format="json") if data is not None else getattr(
        factory, method
    )(url)
    force_authenticate(request, user=identity_models.User.objects.get(pk=actor.id))
    request.tenant_role = role
    request.tenant_id = tenant.id
    with tenant_ctx(tenant):
        return view(request, **kwargs)


def test_the_api_lists_paged_and_an_executive_may_look_but_not_write(world, brazos):
    from apps.metering import read_formats_api as api

    admin = world["admin"]
    with tenant_ctx(brazos):
        _seal_format(admin, name="One")
        _seal_format(admin, name="Two", publish=False)
        executive = staff_actor(brazos, "executive", "ella.exec@brazosbendutilities.test")
    body = _call(api.formats, brazos, admin, "system_admin", query="per=50&status=published").data
    assert body["count"] == 1 and body["results"][0]["name"] == "One"
    assert set(body) >= {"count", "next", "previous", "results"}
    created = _call(
        api.formats, brazos, admin, "system_admin", method="post",
        data={"name": "Three", "service": "electric"},
    )
    assert created.status_code == 201, created.data
    assert _call(api.formats, brazos, executive, "executive").status_code == 200
    refused = _call(
        api.formats, brazos, executive, "executive", method="post",
        data={"name": "Four", "service": "electric"},
    )
    assert refused.status_code == 403


def test_the_handset_fetches_a_published_version_and_never_a_draft(world, brazos):
    from apps.metering import read_formats_api as api

    admin, reader = world["admin"], world["reader"]
    with tenant_ctx(brazos):
        fid = _seal_format(admin)
        version_id = ReadFormat.objects.get(pk=fid).current_version_id
        draft_id = read_formats.new_draft(admin, fid)["draft_version_id"]
    ok = _call(api.mobile_version, brazos, reader, "field_technician", version_id=version_id)
    assert ok.status_code == 200, ok.data
    assert ok.data["version_no"] == 1 and len(ok.data["questions"]) == 4
    missing = _call(api.mobile_version, brazos, reader, "field_technician", version_id=draft_id)
    assert missing.status_code == 404


def test_the_cycle_screen_reads_the_pointer_it_edits(world, brazos):
    """MQ-033 task 11 — `GET cycles/{id}/read-format` answers the format the
    cycle itself names (None until one is set), so the Settings cycle page can
    show the pointer beside its picker. RED before task 11: PUT-only (405)."""
    from apps.metering import read_formats_api as api

    admin, w = world["admin"], world["route"]
    empty = _call(api.cycle_read_format, brazos, admin, "system_admin", cycle_id=w.cycle_id)
    assert empty.status_code == 200, empty.data
    assert empty.data == {"cycle_id": str(w.cycle_id), "read_format": None}
    with tenant_ctx(brazos):
        fid = _seal_format(admin, name="Cycle format")
        read_formats.set_cycle_format(admin, w.cycle_id, {"read_format_id": fid})
    named = _call(api.cycle_read_format, brazos, admin, "system_admin", cycle_id=w.cycle_id)
    assert named.data["read_format"] == {"id": fid, "name": "Cycle format"}
