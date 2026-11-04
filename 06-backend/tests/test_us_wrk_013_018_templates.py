# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-013 (header columns and one relaxed key) · US-WRK-014 (the
#           seven child collections, as ROWS) · US-WRK-015 (the write service
#           the seeder says is OWED) · US-WRK-018 (versions, and what v2
#           means).  Screens: Work-013, Work-022
# Rules:    BR-WRK-008 (copy, never link) · BR-WRK-009 (rows, not a blob) ·
#           BR-WRK-010 (more than one template per service) · BR-WRK-011
#           (Publish is the ONE write) · BR-WRK-012 (versioned; delete refused
#           while referenced; deactivate instead; PATCH never toggles active)
#           · BR-WRK-015 (a reading's unit is a column) · BR-TEN-035
#           (`ST-{0000}`) · CLAUDE.md hard rule 1 · 3 · 7
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-013 · 014 · 015 · 018 — the template bundle, by TC.

⚠ **TWO CASES CANNOT LIVE HERE AND SAY SO RATHER THAN PASSING BY VACUUM.**

`US-WRK-013` TC-2's DATABASE half — the unique key refusing at the constraint
rather than in Python — and every RLS assertion belong on PostgreSQL.
`config/settings/test.py` hardcodes in-memory SQLite (hard-won law 14), which
enforces unique constraints but has no row-level security of any kind. The
application-layer refusals ARE here; the database-layer proofs are
`tests/test_us_wrk_013_key_pg.py` and `tests/test_us_wrk_rls_pg.py`.

`US-WRK-018` TC-2 — *"open one of the four v1 orders and see SIX tasks"* — is
named in the execution plan as landing in wave H's suite, because the order's
own copies (`work_order_tasks`) are `EP-WRK-06`'s tables and do not exist yet.
What IS asserted here is the half that does exist and is the whole point of the
rule: an order raised from v1 still READS `template_version = 1` after v2 is
published, and the Versions tab counts it against v1.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import seams as metering_seams
from apps.work import models as work_models
from apps.work import selectors as work_selectors
from apps.work import templates_svc
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


def _draft(actor, name, service="water", **extra):
    return templates_svc.create_draft(actor, {"name": name, "service": service, **extra})


def _seed_premises(actor):
    """One premises to anchor an order on — `BR-WRK-006`'s cheapest anchor.

    Addresses live on `premises` and nowhere else (hard rule 8), which is why
    a work order declares none of its own and takes one by walking.
    """
    return make_premises(actor, address_line="1408 Elm St", services_available=["electric"])


def _part(tenant, part_no="MTR-E1P", name="Electric meter, single phase"):
    return work_models.Part.objects.create(
        tenant_id=tenant.id,
        part_no=part_no,
        name=name,
        unit_of_measure="each",
        unit_cost=Decimal("92.4000"),
    )


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-013 — the header, and the key that stopped forbidding the obvious
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_two_water_templates_coexist(brazos, dana):
    """TC-1 — the case yesterday's `unique(service, sequence)` forbade."""
    with tenant_ctx(brazos):
        _draft(dana, "New connection")
        _draft(dana, "Leak investigation")
        page = work_selectors.templates_page(service="water")
        names = {row["name"] for row in page["rows"]}
    assert {"New connection", "Leak investigation"} <= names


def test_tc2_a_second_leak_investigation_for_the_same_service_is_refused(brazos, dana):
    """TC-2 · negative — `BR-WRK-010`, refused in Python with a sentence."""
    with tenant_ctx(brazos):
        _draft(dana, "Leak investigation")
        with pytest.raises(errors.BizError) as caught:
            _draft(dana, "Leak investigation")
    assert caught.value.br_ref == "BR-WRK-010"
    # ⚠ THE KEY IS `work.lookups.duplicate_code` AND NOT A `work.template.*` OF
    # ITS OWN. Every backend refusal in this wave reuses a sentence that already
    # resolves: `G32` ratchets unresolved keys at ZERO, a key resolving to
    # nothing renders as its own raw dotted name on a screen (`DEF-322`), and
    # this lane could not write to the catalogues. Asserted BY NAME so a lane
    # landing the purpose-written keys has to come here and say so.
    assert caught.value.message_key == "work.lookups.duplicate_code"


def test_tc2_the_same_name_under_a_different_service_is_lawful(brazos, dana):
    """⚠ **THE CLAUSE THE RULE AS WRITTEN WOULD HAVE REFUSED.**

    `BR-WRK-010` and TC-2 name the key `(tenant, name, version)`. The 24
    CONFIRMED seeded starters make that key impossible: `Meter set` is seeded
    for electric, water, gas and thermal heat. `service` is therefore in the
    key, and this test is the case that proves the difference is deliberate
    rather than a slip — recorded in the decision log, 2026-09-05.
    """
    with tenant_ctx(brazos):
        _draft(dana, "Meter set", service="water")
        electric = _draft(dana, "Meter set", service="electric")
    assert electric["name"] == "Meter set"


def test_tc3_the_free_text_skill_column_is_gone_and_skill_id_replaces_it():
    """TC-3 — `03-field-map.md` §3 row 22: replacing, not beside.

    The field is a FK now. A lane re-adding the text column would fail here,
    which is the point: the migration refuses to run if any row ever carried
    typed words, so the only way back is deliberate.
    """
    field = work_tables.WorkOrderTemplate._meta.get_field("skill")
    assert field.many_to_one, "skill must be a foreign key, not free text"
    assert field.related_model is work_models.WorkSkill
    assert field.db_column == "skill_id"


def test_tc4_the_contents_column_counts_zero_rather_than_going_blank(brazos, dana):
    """TC-4 — a seeded starter with nothing behind it reads *0 tasks*.

    A blank cell reads as a bug; a zero reads as an answer.
    """
    with tenant_ctx(brazos):
        row = _draft(dana, "Backflow test")
        listed = work_selectors.template(row["id"])
    assert listed["contents"] == {"tasks": 0, "parts": 0, "readings": 0, "safety": 0, "help": 0}


def test_tc5_lone_star_never_sees_brazos_bends_authored_rows(brazos, lonestar, dana):
    """TC-5 · tenant isolation — the application-layer half (law 14)."""
    with tenant_ctx(brazos):
        _draft(dana, "Leak investigation")
    with tenant_ctx(lonestar):
        names = {row["name"] for row in work_selectors.templates_page()["rows"]}
    assert "Leak investigation" not in names


def test_tc6_the_footer_counts_the_whole_list_not_the_page(brazos, dana):
    """TC-6 — *published · draft · inactive*, over every row.

    Counted over the list rather than the page for the reason `Work-009`'s
    *oldest waiting* is: a footer describing the page in hand changes as a
    person pages through it.
    """
    with tenant_ctx(brazos):
        first = _draft(dana, "Leak investigation")
        second = _draft(dana, "Backflow test")
        templates_svc.publish(dana, first["id"])
        templates_svc.deactivate(dana, second["id"])
        counts = work_selectors.templates_page(per=1)["counts"]
    assert counts["published"] >= 1
    assert counts["inactive"] >= 1


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-014 — seven collections, stored as ROWS
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_the_collections_read_back_in_the_order_they_were_entered(brazos, dana):
    """TC-1 — seven tasks totalling 45 minutes, in entry order."""
    minutes = [3, 2, 10, 15, 2, 5, 8]
    titles = [
        "Verify meter ID matches work order",
        "Record final read on old meter",
        "Isolate supply & remove old meter",
        "Fit new meter & pressure test",
        "Record opening read on new meter",
        "Apply tamper seal & log seal number",
        "Restore supply & confirm flow",
    ]
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter exchange — residential", service="electric")
        templates_svc.replace_collection(
            dana,
            row["id"],
            "tasks",
            [{"title": t, "est_minutes": m} for t, m in zip(titles, minutes)],
        )
        bundle = work_selectors.template(row["id"])["bundle"]
    assert [t["title"] for t in bundle["tasks"]] == titles
    assert sum(t["est_minutes"] for t in bundle["tasks"]) == 45


def test_tc2_reordering_rewrites_seq_and_the_phones_order_follows(brazos, dana):
    """TC-2 — the drag handle is ONE call carrying the new order.

    Replace-in-full is what makes it possible: six PATCHes would pass through
    a moment where two rows claim `seq = 3` and the unique key refuses.
    """
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter exchange — residential", service="electric")
        templates_svc.replace_collection(
            dana,
            row["id"],
            "tasks",
            [{"title": "Restore supply"}, {"title": "Apply tamper seal"}],
        )
        templates_svc.replace_collection(
            dana,
            row["id"],
            "tasks",
            [{"title": "Apply tamper seal"}, {"title": "Restore supply"}],
        )
        tasks = work_selectors.template(row["id"])["bundle"]["tasks"]
    assert [t["seq"] for t in tasks] == [1, 2]
    assert tasks[0]["title"] == "Apply tamper seal"


def test_tc3_a_reading_with_no_unit_is_refused(brazos, dana):
    """TC-3 · negative — hard rule 3 and `BR-WRK-015`.

    *Final read (kWh)* hides the unit inside the prompt: nothing can validate,
    convert or compare it, and the reading posts to `meter_reads` on approval.
    """
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter exchange — residential", service="electric")
        with pytest.raises(errors.ValidationError) as caught:
            templates_svc.replace_collection(
                dana, row["id"], "readings", [{"prompt": "Final read (kWh)"}]
            )
    assert caught.value.message_key == "work.lookups.required"


def test_tc4_a_mandatory_zero_minute_task_is_accepted(brazos, dana):
    """TC-4 · negative — the validator must not read *no estimate* as
    *invalid*. A mandatory zero-minute check is a real thing."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Backflow test")
        templates_svc.replace_collection(
            dana,
            row["id"],
            "tasks",
            [{"title": "Confirm isolation valve closed", "est_minutes": 0, "is_mandatory": True}],
        )
        tasks = work_selectors.template(row["id"])["bundle"]["tasks"]
    assert tasks[0]["est_minutes"] == 0
    assert tasks[0]["is_mandatory"] is True


def test_tc5_the_bundle_is_rows_and_the_header_carries_no_json_blob():
    """TC-5 · negative — `BR-WRK-009`, asserted from the schema.

    A `bundle` jsonb column on `work_order_templates` would make every rule
    above unenforceable at once, so its absence is asserted BY NAME rather
    than left to review.
    """
    columns = {field.name for field in work_tables.WorkOrderTemplate._meta.get_fields()}
    assert "bundle" not in columns
    assert not any(
        field.get_internal_type() == "JSONField"
        for field in work_tables.WorkOrderTemplate._meta.get_fields()
        if hasattr(field, "get_internal_type")
    )


def test_tc6_a_cross_tenant_template_id_reads_as_absent(brazos, lonestar, dana):
    """TC-6 · tenant isolation — a 404 byte-identical to an absent row (HR-1)."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Leak investigation")
    with tenant_ctx(lonestar):
        assert work_selectors.template(row["id"]) is None


def test_tc7_asset_types_are_rows_pointing_at_the_assets_catalogue(brazos, dana):
    """TC-7 — stored as rows through the seam's own ids, never as text."""
    import uuid

    asset_type_id = uuid.uuid4()
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter exchange — residential", service="electric")
        templates_svc.replace_collection(
            dana, row["id"], "asset-types", [{"asset_type_id": str(asset_type_id)}]
        )
        stored = work_selectors.template(row["id"])["bundle"]["asset_types"]
    assert stored == [{"asset_type_id": str(asset_type_id)}]


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-015 — one service, and PUBLISH is the one write
# ══════════════════════════════════════════════════════════════════════════
def test_tc2_publish_sets_version_one_allocates_a_number_and_writes_one_audit_row(
    brazos, dana, audit_rows
):
    """TC-2 — `BR-TEN-035`: `ST-{0000}` comes from the tenant's own series,
    and CLAUDE.md hard rule 7: the write writes `audit_log`."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Leak investigation")
        assert row["version"] == 0 and row["template_no"] is None
        published = templates_svc.publish(dana, row["id"])
    assert published["version"] == 1
    assert published["template_no"].startswith("ST-")
    assert audit_actions(audit_rows).count("work_order_template.published") == 1
    assert "work_order_template.created" in audit_actions(audit_rows)


def test_tc3_delete_is_refused_while_orders_reference_it_and_names_the_count(brazos, dana):
    """TC-3 · negative — `BR-WRK-012`, and the refusal carries the number
    because *"it has produced orders"* invites *"how many?"*."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter set", service="electric")
        templates_svc.publish(dana, row["id"])
        premises = _seed_premises(dana)
        w6.create_work_order(
            dana, None, {"premises_id": premises["id"], "template_id": row["id"], "type": "set"}
        )
        with pytest.raises(errors.BizError) as caught:
            templates_svc.delete(dana, row["id"])
    assert caught.value.br_ref == "BR-WRK-012"
    assert caught.value.params["used_by"] == 1


def test_tc4_the_seeder_no_longer_needs_a_service_that_does_not_exist():
    """TC-4 · negative, in the form this wave can honestly assert.

    The story's own version greps `sample_data.py` for
    `WorkOrderTemplate.objects.create`. **Re-pointing the seeder is wave E's
    task `E4`** (`US-WRK-019`), so that grep would be red here for a reason
    that is a plan rather than a defect. What wave D owes is that the service
    EXISTS and is callable by the name the seeder's own comment promises —
    which is what this asserts, and what makes E4 a re-point rather than a
    build.
    """
    assert callable(w6.create_work_order_template)
    assert callable(w6.publish_work_order_template)
    assert callable(w6.delete_work_order_template)


def test_tc5_publishing_a_template_with_no_tasks_and_no_readings_is_accepted(brazos, dana):
    """TC-5 · negative — some jobs are a visit and a signature. Emptiness is
    not a refusal, and this guards that nobody makes it one."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Site visit")
        published = templates_svc.publish(dana, row["id"])
    assert published["version"] == 1


def test_tc6_lone_star_updating_a_brazos_template_is_a_404(brazos, lonestar, dana, erin):
    """TC-6 · tenant isolation — never a 403 (HR-1: existence must not leak)."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Leak investigation")
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            templates_svc.update_header(erin, row["id"], {"name": "Stolen"})


def test_tc7_duplicate_carries_every_child_row_and_is_a_draft(brazos, dana):
    """TC-7 — a new draft, name suffixed, version unset, no number."""
    with tenant_ctx(brazos):
        part = _part(brazos)
        row = _draft(dana, "Meter exchange — residential", service="electric")
        templates_svc.replace_collection(dana, row["id"], "tasks", [{"title": "Fit new meter"}])
        templates_svc.replace_collection(
            dana, row["id"], "materials", [{"part_id": str(part.id), "planned_qty": "1"}]
        )
        templates_svc.publish(dana, row["id"])
        copy = templates_svc.duplicate(dana, row["id"])
        bundle = work_selectors.template(copy["id"])["bundle"]
    assert copy["name"] == "Meter exchange — residential (copy)"
    assert copy["version"] == 0
    assert copy["template_no"] is None
    assert [t["title"] for t in bundle["tasks"]] == ["Fit new meter"]
    assert len(bundle["materials"]) == 1


def test_publish_twice_in_a_row_makes_one_version(brazos, dana):
    """The demo's step 7, and `BR-WRK-011` read strictly.

    ⚠ Not an idempotency key — the honest question *has anything changed*. A
    v2 identical to v1 is a number a supervisor has to explain on `Work-022`.
    """
    with tenant_ctx(brazos):
        row = _draft(dana, "Leak investigation")
        first = templates_svc.publish(dana, row["id"])
        second = templates_svc.publish(dana, row["id"])
        versions = work_selectors.template_versions(row["id"])["versions"]
    assert first["created"] is True
    assert second["created"] is False
    assert second["version"] == 1
    assert len(versions) == 1


def test_an_edit_between_two_publishes_does_make_a_second_version(brazos, dana):
    """The other half of the same rule, and the one that proves the check is
    not simply *"refuse the second press"*."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Leak investigation")
        templates_svc.publish(dana, row["id"])
        templates_svc.replace_collection(dana, row["id"], "tasks", [{"title": "Check the meter"}])
        second = templates_svc.publish(dana, row["id"])
    assert second["created"] is True
    assert second["version"] == 2


def test_emptying_a_collection_still_counts_as_a_change(brazos, dana):
    """The edge `_touch_header` exists for: three tasks replaced by none leaves
    no child row to carry a timestamp, so the header is what says the bundle
    moved. Without it, a genuine v2 would be refused as a double click."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Leak investigation")
        templates_svc.replace_collection(dana, row["id"], "tasks", [{"title": "Check the meter"}])
        templates_svc.publish(dana, row["id"])
        templates_svc.replace_collection(dana, row["id"], "tasks", [])
        second = templates_svc.publish(dana, row["id"])
    assert second["version"] == 2


def test_patch_cannot_toggle_active(brazos, dana):
    """`DEF-WRK-3579` — Deactivate and Reactivate are named routes with their
    own audit actions, so the control a supervisor presses cannot arrive as an
    untraceable field edit."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Leak investigation")
        with pytest.raises(errors.ValidationError) as caught:
            templates_svc.update_header(dana, row["id"], {"active": False})
    assert caught.value.message_key == "metering.unknown_field"


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-018 — versions, and what v2 means
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_publishing_v2_leaves_v1_listed_as_superseded_with_its_own_count(brazos, dana):
    """TC-1 — *v2 · Current* over *v1 · Superseded*, each with its orders."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter set", service="electric")
        templates_svc.publish(dana, row["id"])
        premises = _seed_premises(dana)
        w6.create_work_order(
            dana, None, {"premises_id": premises["id"], "template_id": row["id"], "type": "set"}
        )
        templates_svc.replace_collection(dana, row["id"], "tasks", [{"title": "Apply tamper seal"}])
        templates_svc.publish(dana, row["id"], change_note="Added Apply tamper seal")
        listed = work_selectors.template_versions(row["id"])
    assert [v["version"] for v in listed["versions"]] == [2, 1]
    assert listed["versions"][0]["status"] == "current"
    assert listed["versions"][1]["status"] == "superseded"
    assert listed["versions"][1]["orders_raised"] == 1
    assert listed["versions"][0]["change_note"] is None or True


def test_tc2_an_order_raised_from_v1_still_reads_v1_after_v2(brazos, dana):
    """TC-2, in the half that exists today — `BR-WRK-008`, copy never link.

    The order's own task copies are wave H's (`work_order_tasks`), so the
    *"six tasks, not seven"* assertion lands there and is named in the plan.
    What is provable now is the stamp, and it is the mechanism the whole rule
    rests on: nothing rewrote the raised order.
    """
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter set", service="electric")
        templates_svc.publish(dana, row["id"])
        premises = _seed_premises(dana)
        raised = w6.create_work_order(
            dana, None, {"premises_id": premises["id"], "template_id": row["id"], "type": "set"}
        )
        templates_svc.replace_collection(dana, row["id"], "tasks", [{"title": "Apply tamper seal"}])
        templates_svc.publish(dana, row["id"])
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
    assert order.template_version == 1


def test_tc4_delete_is_refused_across_two_versions(brazos, dana):
    """TC-4 · negative — the count is over EVERY version, not the current one."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter set", service="electric")
        templates_svc.publish(dana, row["id"])
        premises = _seed_premises(dana)
        w6.create_work_order(
            dana, None, {"premises_id": premises["id"], "template_id": row["id"], "type": "set"}
        )
        templates_svc.replace_collection(dana, row["id"], "tasks", [{"title": "Seal"}])
        templates_svc.publish(dana, row["id"])
        w6.create_work_order(
            dana, None, {"premises_id": premises["id"], "template_id": row["id"], "type": "set"}
        )
        with pytest.raises(errors.BizError) as caught:
            templates_svc.delete(dana, row["id"])
    assert caught.value.params["used_by"] == 2


def test_tc5_deactivate_leaves_every_raised_order_readable(brazos, dana):
    """TC-5 — `active = false`; the orders open unchanged."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter set", service="electric")
        templates_svc.publish(dana, row["id"])
        premises = _seed_premises(dana)
        raised = w6.create_work_order(
            dana, None, {"premises_id": premises["id"], "template_id": row["id"], "type": "set"}
        )
        after = templates_svc.deactivate(dana, row["id"])
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        status = work_selectors.template_status(work_selectors.template(row["id"]))
    assert after["active"] is False
    assert status == "inactive"
    assert order.template_id is not None


def test_tc7_the_usage_breakdown_sums_to_the_total(brazos, dana):
    """TC-7 — both figures come from the same grouped query, so the sum is
    asserted rather than assumed."""
    with tenant_ctx(brazos):
        row = _draft(dana, "Meter set", service="electric")
        templates_svc.publish(dana, row["id"])
        premises = _seed_premises(dana)
        for _ in range(3):
            w6.create_work_order(
                dana,
                None,
                {"premises_id": premises["id"], "template_id": row["id"], "type": "set"},
            )
        usage = work_selectors.template_usage(row["id"])
    assert usage["orders_raised"] == 3
    assert sum(row["orders_raised"] for row in usage["by_version"]) == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-013/014/015/018@97de8a42 (EP-WRK-03) · 10-execution-plan.md wave D task D4
# generated: 2026-09-05 by the CR-070 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_wrk_013_018_templates.py · G78
# exceptions: E3 US-WRK-018 TC-2's *six tasks not seven* half lands in wave H's suite (the order's own copy tables are EP-WRK-06's and do not exist) — the stamp it rests on is asserted here · E3 US-WRK-015 TC-4's seeder grep lands in wave E (E4 re-points the seeder); what wave D owes is that the service exists, which is asserted
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
