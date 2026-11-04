# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-032 (the order's own copies — copied at raise, never read
#           through the template link) TC-1..TC-7 · US-WRK-028 TC-2 (the
#           wizard's template picker gives the order its copies) ·
#           US-WRK-018 TC-3 (named in D4 as landing HERE).  Screens: Work-008
# Rules:    BR-WRK-008 (COPY, NEVER LINK) · BR-WRK-015 (the copied reading
#           carries its unit) · BR-WRK-011 (0 is a draft, not a version) ·
#           CLAUDE.md hard rule 1 (tenant scope) · 3 (unit) · 7 (audit_log)
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-032 — the order takes its own copies, by TC.

⚠ **THE ONE PROPERTY THIS WHOLE FILE EXISTS TO PROVE:** change the template
after the order is raised, and the order does not move. TC-2 does it by editing
a task's title, TC-3 by publishing a whole new version with an extra task, and
TC-6 by reading the SCHEMA rather than the behaviour — because a behavioural
test passes for as long as nobody writes the join, and TC-6 fails the moment
somebody does.

⚠ **TC-5's RLS HALF IS NOT HERE AND SAYS SO RATHER THAN PASSING BY VACUUM.**
`config/settings/test.py` hardcodes in-memory SQLite (hard-won law 14), which
has no row-level security of any kind, so an isolation assertion here would be
green whether the policies exist or not. What IS here is the application-layer
404 (`_order_or_404` through the seam); the DATABASE's own refusal is
`tests/test_us_wrk_032_copies_pg.py`, run under `config.settings.local` against
real PostgreSQL as the `sbh_rls_probe` role.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import checklist
from apps.work import models as work_models
from apps.work import templates_svc
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# The fixture — `WO-4822 · Meter exchange` from *Meter exchange — residential*
# v2, with the drawing's seven tasks, three readings, three parts, three
# safety rows and three help rows (`10-execution-plan.md` H3).
# ══════════════════════════════════════════════════════════════════════════
SEVEN_TASKS = [
    {"title": "Confirm address and customer", "est_minutes": 3},
    {"title": "Isolate supply & remove old meter", "est_minutes": 12, "is_mandatory": True},
    {"title": "Record final read on old meter", "est_minutes": 4, "photo_required": True},
    {"title": "Fit new meter and seal", "est_minutes": 15, "photo_required": True},
    {"title": "Record opening read on new meter", "est_minutes": 4},
    {"title": "Restore supply and test", "est_minutes": 5},
    {"title": "Leave card and tidy site", "est_minutes": 2},
]

THREE_READINGS = [
    {"prompt": "Final read, old meter", "unit_of_measure": "kWh", "min": 0, "max": 99999,
     "photo_required": True, "posts_as_meter_read": True},
    {"prompt": "Opening read, new meter", "unit_of_measure": "kWh", "min": 0, "max": 999,
     "photo_required": True},
    {"prompt": "New meter serial", "unit_of_measure": "serial"},
]

THREE_SAFETY = [
    {"text": "Isolate at the main before opening the box", "is_mandatory": True},
    {"text": "Gloves and eye protection on", "is_mandatory": True},
    {"text": "Check for standing water", "is_mandatory": True},
]

THREE_HELP = [
    {"kind": "document", "label": "Meter exchange SOP", "ref": "SOP-114"},
    {"kind": "phone", "label": "Control room", "ref": "555-0142"},
    {"kind": "phone", "label": "Duty supervisor", "ref": "555-0188"},
]


def _parts(tenant):
    return [
        work_models.Part.objects.create(
            tenant_id=tenant.id, part_no=no, name=name,
            unit_of_measure=uom, unit_cost=Decimal(cost),
        )
        for no, name, uom, cost in (
            ("MTR-E1P", "Electric meter, single phase", "each", "92.4000"),
            ("SEAL-R", "Meter seal, red", "each", "0.2200"),
            ("TAIL-25", "Meter tail, 25mm", "metre", "3.1000"),
        )
    ]


def _published_template(actor, tenant, *, tasks=None, name="Meter exchange — residential"):
    """A template with all six collections, published TWICE so it reads v2 —
    which is what `WO-4822`'s fixture says it was raised from."""
    header = templates_svc.create_draft(actor, {"name": name, "service": "electric"})
    tid = header["id"]
    templates_svc.replace_collection(actor, tid, "tasks", tasks or SEVEN_TASKS)
    templates_svc.replace_collection(actor, tid, "readings", THREE_READINGS)
    templates_svc.replace_collection(actor, tid, "safety", THREE_SAFETY)
    templates_svc.replace_collection(actor, tid, "help", THREE_HELP)
    templates_svc.replace_collection(
        actor, tid, "materials",
        [{"part_id": str(p.id), "planned_qty": q} for p, q in zip(_parts(tenant), (1, 2, 3))],
    )
    templates_svc.replace_collection(actor, tid, "details", {"show_asset_card": False})
    templates_svc.publish(actor, tid)
    # A second publish needs a CHANGE to make a version (`templates_svc.publish`
    # returns the existing one otherwise), so touch a collection first.
    templates_svc.replace_collection(actor, tid, "help", THREE_HELP)
    published = templates_svc.publish(actor, tid)
    assert published["version"] == 2, published
    return tid


def _raise(actor, tenant, template_id, **extra):
    premises = make_premises(actor, address_line="221 Oak Ave", services_available=["electric"])
    return w6.create_work_order(
        actor, None,
        {"premises_id": str(premises["id"]), "type": "Meter exchange",
         "template_id": str(template_id) if template_id else None, **extra},
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-1 — raise from v2: six collections land, and the version is stamped
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_a_raise_from_v2_lands_all_six_collections(brazos, dana):
    """TC-1 — 7 tasks, 3 readings, 3 materials, 3 safety, 3 help, 1 details;
    `template_version = 2`."""
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        order = _raise(dana, brazos, tid)
        oid = order["id"]
        assert work_models.WorkOrderTask.objects.filter(work_order_id=oid).count() == 7
        assert work_models.WorkOrderReading.objects.filter(work_order_id=oid).count() == 3
        assert work_models.WorkOrderMaterial.objects.filter(work_order_id=oid).count() == 3
        assert work_models.WorkOrderSafety.objects.filter(work_order_id=oid).count() == 3
        assert work_models.WorkOrderHelp.objects.filter(work_order_id=oid).count() == 3
        assert work_models.WorkOrderDetail.objects.filter(work_order_id=oid).count() == 1
        assert work_tables.WorkOrder.objects.get(pk=oid).template_version == 2


def test_tc1_b_the_copied_reading_carries_its_unit(brazos, dana):
    """TC-1 · `BR-WRK-015` + hard rule 3 — the unit is a COLUMN on the copy,
    not a word inside the prompt."""
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
        rows = list(
            work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq")
        )
        assert [r.unit_of_measure for r in rows] == ["kWh", "kWh", "serial"]
        assert rows[0].min_value == Decimal("0.0000")
        assert rows[0].max_value == Decimal("99999.0000")
        # The RULE and the FILE are two columns (`US-WRK-049`): the template
        # asked for a photograph and none has been taken.
        assert rows[0].photo_required is True
        assert rows[0].photo_attachment_id is None
        assert rows[0].in_range is None


def test_tc1_c_details_copies_the_flags_and_leaves_the_address_facts_absent(brazos, dana):
    """TC-1 — the four `show_*` flags come from the template; `gate_code`,
    `access_notes` and `hazards` are NULL because `metering.Premises` carries
    none of them at this tip. An absence, never a guess."""
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
        row = work_models.WorkOrderDetail.objects.get(work_order_id=oid)
        assert row.show_asset_card is False        # the template said so
        assert row.show_account_summary is True
        assert (row.gate_code, row.access_notes, row.hazards) == (None, None, None)


# ══════════════════════════════════════════════════════════════════════════
# TC-2 / TC-3 — **the property this wave is about**: the template moves and
# the order does not
# ══════════════════════════════════════════════════════════════════════════
def test_tc2_renaming_a_task_on_the_template_does_not_move_a_raised_order(brazos, dana):
    """TC-2 · negative — rename task 3, then read the order: unchanged."""
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
        renamed = [dict(t) for t in SEVEN_TASKS]
        renamed[1]["title"] = "RENAMED ON THE TEMPLATE"
        templates_svc.replace_collection(dana, tid, "tasks", renamed)
        templates_svc.publish(dana, tid)

        task = work_models.WorkOrderTask.objects.get(work_order_id=oid, seq=2)
        assert task.title == "Isolate supply & remove old meter"
        # And the template really did change — otherwise this test proves
        # nothing at all (a check that cannot fail is worse than no check).
        assert work_models.WorkOrderTemplateTask.objects.get(
            template_id=tid, seq=2
        ).title == "RENAMED ON THE TEMPLATE"


def test_tc3_publishing_v3_with_eight_tasks_leaves_the_v2_order_at_seven(brazos, dana):
    """TC-3 · negative — the exit test of wave H, and the demo's step 7."""
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
        templates_svc.replace_collection(
            dana, tid, "tasks", [*SEVEN_TASKS, {"title": "Apply tamper seal", "est_minutes": 2}]
        )
        v3 = templates_svc.publish(dana, tid)
        assert v3["version"] == 3

        assert work_models.WorkOrderTask.objects.filter(work_order_id=oid).count() == 7
        assert work_models.WorkOrderTemplateTask.objects.filter(template_id=tid).count() == 8
        # `US-WRK-018` TC-3, named in D4 as landing here: the order still reads
        # the version it was raised from.
        assert work_tables.WorkOrder.objects.get(pk=oid).template_version == 2


def test_tc3_b_a_deleted_template_collection_leaves_the_order_whole(brazos, dana):
    """TC-3 · the harder half — emptying a collection on the template is the
    edit most likely to reach through a link, because a link would return
    nothing rather than something wrong."""
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
        templates_svc.replace_collection(dana, tid, "safety", [])
        templates_svc.publish(dana, tid)
        assert work_models.WorkOrderSafety.objects.filter(work_order_id=oid).count() == 3


# ══════════════════════════════════════════════════════════════════════════
# TC-4 — a draft has no published version to copy
# ══════════════════════════════════════════════════════════════════════════
def test_tc4_raising_from_a_draft_template_is_refused(brazos, dana):
    """TC-4 · negative — `version` 0 IS the draft state (`BR-WRK-011`), so
    there is nothing settled to copy and nothing to stamp."""
    with tenant_ctx(brazos):
        header = templates_svc.create_draft(dana, {"name": "Leak investigation", "service": "water"})
        templates_svc.replace_collection(dana, header["id"], "tasks", SEVEN_TASKS[:4])
        with pytest.raises(errors.BizError) as refused:
            _raise(dana, brazos, header["id"])
        assert refused.value.message_key == "work.order.template_not_published"
        assert refused.value.br_ref == "BR-WRK-008"


def test_tc4_b_the_refusal_writes_no_order_at_all(brazos, dana):
    """TC-4 — refused BEFORE the row, so there is no order stamped
    `template_version = 0` pointing at a bundle that can still change."""
    with tenant_ctx(brazos):
        header = templates_svc.create_draft(dana, {"name": "Backflow test", "service": "water"})
        before = work_tables.WorkOrder.objects.count()
        with pytest.raises(errors.BizError):
            _raise(dana, brazos, header["id"])
        assert work_tables.WorkOrder.objects.count() == before


# ══════════════════════════════════════════════════════════════════════════
# TC-5 — tenant isolation, application layer (the DATABASE half is the _pg file)
# ══════════════════════════════════════════════════════════════════════════
def test_tc5_another_utility_reading_the_checklist_gets_a_404(brazos, lonestar, dana, erin):
    """TC-5 — a 404 and never a 403: a 403 would confirm the order exists."""
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            checklist.checklist(oid)


# ══════════════════════════════════════════════════════════════════════════
# TC-6 — **the schema test**: no FK joins an order's copy to a template row
# ══════════════════════════════════════════════════════════════════════════
def test_tc6_no_copy_table_has_a_foreign_key_to_any_wot_table():
    """TC-6 — `BR-WRK-008` asserted against the SCHEMA, not the behaviour.

    ⚠ **THIS IS THE TEST THAT SURVIVES A HELPFUL REFACTOR.** TC-2 and TC-3
    pass for exactly as long as nobody writes the join; the day somebody adds
    `template_task = FK(WorkOrderTemplateTask)` "so we can show which step this
    came from", they keep passing — the copies are still there — and the rule
    is broken anyway, because the next reader uses the link.

    The only template reference an order is allowed is `template_id` +
    `template_version`, and both of those are on `work_orders` itself.
    """
    wot_tables = {
        "wot_details", "wot_safety", "wot_tasks", "wot_materials",
        "wot_readings", "wot_help", "wot_asset_types",
        "work_order_template_versions",
    }
    copies = (
        work_models.WorkOrderDetail, work_models.WorkOrderSafety, work_models.WorkOrderTask,
        work_models.WorkOrderMaterial, work_models.WorkOrderReading, work_models.WorkOrderHelp,
    )
    for model in copies:
        for field in model._meta.get_fields():
            if not getattr(field, "many_to_one", False) and not getattr(field, "one_to_one", False):
                continue
            target = field.related_model._meta.db_table
            assert target not in wot_tables, (
                f"{model._meta.db_table}.{field.name} points at {target} — "
                "BR-WRK-008 says copy, never link"
            )
        # And no plain uuid column smuggling the same link in under a name.
        names = {f.name for f in model._meta.get_fields()}
        assert not (names & {"template", "template_id", "wot_task", "wot_task_id"}), (
            f"{model._meta.db_table} names a template column"
        )


def test_tc6_b_the_order_keeps_exactly_two_template_references():
    """TC-6 — and they are both on `work_orders`: which template, which
    version. Nothing else may point back."""
    names = {f.name for f in work_tables.WorkOrder._meta.get_fields()}
    assert "template" in names and "template_version" in names


# ══════════════════════════════════════════════════════════════════════════
# TC-7 — a one-off job with no template
# ══════════════════════════════════════════════════════════════════════════
def test_tc7_an_order_with_no_template_copies_nothing_and_is_not_an_error(brazos, dana):
    """TC-7 — zero child rows, and the Checklist tab shows its empty state
    (B14 rule 17) rather than a failure."""
    with tenant_ctx(brazos):
        order = _raise(dana, brazos, None, type="Leak investigation")
        oid = order["id"]
        for model in (
            work_models.WorkOrderTask, work_models.WorkOrderReading,
            work_models.WorkOrderMaterial, work_models.WorkOrderSafety,
            work_models.WorkOrderHelp, work_models.WorkOrderDetail,
        ):
            assert model.objects.filter(work_order_id=oid).count() == 0
        body = checklist.checklist(oid)
        assert body["tasks"] == [] and body["details"] is None
        assert body["safety_lock"]["locked"] is False
        assert body["template_version"] is None
