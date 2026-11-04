# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-024 (the twelve dispatch columns, the third axis, the
#           promise) · US-WRK-025 (the append-only assignment history) ·
#           US-WRK-026 (exactly six filters, a 400 on a seventh) ·
#           US-WRK-027 (bulk acts write one row PER ORDER) ·
#           US-WRK-011 (the Area filter is tenancy.Area, never a copy)
# Rules:    BR-WRK-018 · BR-WRK-022 · BR-WRK-023 · BR-WRK-024 · BR-WRK-025 ·
#           BR-WRK-026 · BR-WRK-027 · BR-WRK-029 · CLAUDE.md hard rule 1
#           (tenant isolation) · hard rule 7 (every act writes audit_log)
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-024 · 025 · 026 · 027 · 011 — the dispatcher.

⚠ **TWO THINGS THIS FILE CANNOT PROVE, AND BOTH HAVE A `_pg` SIBLING.**
`config/settings/test.py` hardcodes in-memory SQLite, which has

  * **no row-level security of any kind**, so an RLS assertion here would pass
    by vacuum; and
  * **no PL/pgSQL and no aborted-transaction state**, so the append-only
    TRIGGER never fires and the per-order savepoint in `bulk_act` is not
    exercised at all — the broken version of both passes everything here.

That is hard-won law 14 in its two shapes. The database-layer proofs are
`tests/test_us_wrk_025_dispatch_pg.py`, run under `config.settings.local`
against real PostgreSQL 16. What IS proved here is the application layer: the
axis, the promise, the filters, the per-order results and the isolation.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import resolve
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from apps.work import api as work_api
from apps.work import dispatch
from apps.work import models as work_models
from apps.work import services as work_services
from apps.work import workforce
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


# ── fixtures ────────────────────────────────────────────────────────────────


def _reference(actor):
    """The utility's own priorities and job types, in the ONE order that works.

    `seed_reference_list` records why: a seeded type names its default priority
    BY CODE, so priorities must be rows first or every type lands with a NULL
    default and `due_at` is never stamped.
    """
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")


def _tenant_id():
    """The tenant in context. ⚠ NOT `actor.tenant_id` — the `dana`/`erin`
    fixtures are `SimpleNamespace` actors in the B12 §6a shape (id + role) and
    carry no tenant at all; reading one is an `AttributeError` inside a
    `tenant_ctx` block, which reads like a missing row rather than a missing
    attribute."""
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


@pytest.fixture()
def real_audit_trail():
    """Put audit's REAL sink back for one test.

    `tests/test_us_met_helpers.py` installs an autouse sink that CAPTURES audit
    rows into a list, so no test in this family writes `audit_log` at all —
    right for every other case here and exactly wrong for the one that asks
    whether hard rule 7 is met. Copied from `test_us_wrk_020_021_workforce.py`
    for the reason stated there: the original lives in a third file and is not
    exported, and moving it is a change to files other lanes are in today.
    """
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


#: `DEF-WRK-5108` / `DEF-WRK-9602` — the job types these cases raise are LIVE
#: seed types (BR-WRK-058, PO 2026-09-07). Until 2026-10-05 the fixture named
#: *Leak investigation*, *Read verification* and *Reconnect after payment* —
#: three of the eight types `work/0023` RETIRED — so each resolved to nothing,
#: carried no priority and no promise, and three cases were red for a month
#: while reading like a broken filter. `test_the_fixture_names_only_live_types`
#: below fails the day one of these is retired too.
HIGH_TYPE = "Consumer Complaint"      # HIGH, 8 h (SEED_TYPE_SPINE)
LOW_TYPE = "Preventive Maintenance"   # LOW, 168 h
URGENT_TYPE = "No Water Supply"       # URGENT — beats its parent (URGENT_BEATS_ITS_PARENT)
FIXTURE_TYPES = (HIGH_TYPE, LOW_TYPE, URGENT_TYPE)


def _order(actor, address, order_type=HIGH_TYPE, **payload):
    premises = make_premises(actor, address_line=address, services_available=["water"])  # noqa: F405
    body = {"type": order_type, "service": "water", "premises_id": premises["id"], **payload}
    return w6.create_work_order(actor, None, body)


def _list(tenant, actor, query=None, role="system_admin"):
    return api_call(
        work_api.work_orders,
        "get",
        f"/api/{tenant.subdomain}/work-orders",
        user=actor.user,
        role=role,
        tenant=tenant,
        query=query,
    )


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-024 — the third axis, and the promise
# ══════════════════════════════════════════════════════════════════════════


def test_us_wrk_024_tc1_assigning_moves_the_dispatch_state_and_leaves_state_alone(dana, brazos):
    """`BR-WRK-023` — the two axes move independently, and that is the point.

    A job that has been given to somebody is *scheduled* on the dispatch axis
    and still *planned* on the work axis, because nobody has done any work yet.
    A product that collapsed them could not express the ordinary state of half a
    dispatcher's morning.
    """
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.dispatch_state == "queued"
        assert order.state == "planned"

        dispatch.record_act(dana, order.id, {"act": "assign", "technician_id": str(tech.id)})

        order.refresh_from_db()
        assert order.dispatch_state == "scheduled"
        assert order.state == "planned", "the work axis must NOT move when somebody is assigned"


def test_us_wrk_024_tc2_the_axis_walks_queued_scheduled_en_route_on_site(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        for act, expected in (
            ("assign", "scheduled"),
            ("depart", "en_route"),
            ("arrive", "on_site"),
        ):
            body = {"act": act}
            if act == "assign":
                body["technician_id"] = str(tech.id)
            dispatch.record_act(dana, order.id, body)
            order.refresh_from_db()
            assert order.dispatch_state == expected
        # And `state` never moved once.
        assert order.state == "planned"


def test_us_wrk_024_tc3_due_at_is_the_raise_plus_the_priority_sla(dana, brazos):
    """`BR-WRK-018`, verbatim: *"`due_at` defaults to the raise time plus the
    SLA"*. *Consumer Complaint* seeds at HIGH, whose SLA is 8 hours."""
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.priority is not None and order.priority.code == "HIGH"
        assert order.priority.sla_hours == 8
        gap = order.due_at - order.created_at
        assert abs(gap - timedelta(hours=8)) < timedelta(seconds=5)


def test_us_wrk_024_tc4_the_promise_is_stamped_and_a_later_sla_change_does_not_move_it(
    dana, brazos
):
    """`US-WRK-008` TC-4 — moving Urgent from 4 h to 2 h must not move a job
    already in the field. STAMPED at the raise, never derived on read."""
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        was = order.due_at
        high = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="HIGH")
        high.sla_hours = 1
        high.save(update_fields=["sla_hours"])
        order.refresh_from_db()
        assert order.due_at == was, "a promise already made does not move when the rule changes"


def test_us_wrk_024_tc5_an_unmatched_job_type_gets_no_priority_and_no_promise(dana, brazos):
    """`US-WRK-007` TC-6 — nothing is guessed. A type that matches no catalogue
    row stays a string, carries no priority, and the DUE cell draws a dash
    rather than a date somebody could be held to."""
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct", order_type="Something nobody catalogued")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.type_ref_id is None
        assert order.priority_id is None
        assert order.due_at is None


def test_us_wrk_024_tc6_the_source_is_stamped_and_read_back_as_raised_by(dana, brazos):
    """`BR-WRK-024` — every order carries WHY it exists, and the list draws it."""
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct", source="dispatcher", source_ref="WO-manual")
        rows = dispatch.dispatch_page()["rows"]
        row = next(r for r in rows if r["order_no"] == raised["order_no"])
        assert row["source"] == "dispatcher"
        assert row["source_ref"] == "WO-manual"


def test_us_wrk_024_tc7_the_list_sorts_by_priority_rank_then_due_time(dana, brazos):
    """`BR-WRK-018`'s second sentence, and `Work-007`'s footer says so in words.

    ⚠ An order with NO priority sorts LAST, not first. A job nobody prioritised
    is not more urgent than one somebody marked Urgent, and the two databases
    disagree about NULL ordering by default — PostgreSQL last, SQLite first — so
    it is spelled explicitly.
    """
    with tenant_ctx(brazos):
        _reference(dana)
        _order(dana, "1 Low St", order_type=LOW_TYPE)        # LOW, rank 4
        _order(dana, "2 Urgent St", order_type=URGENT_TYPE)  # URGENT, rank 1
        _order(dana, "3 None St", order_type="Uncatalogued")  # no priority at all
        _order(dana, "4 High St", order_type=HIGH_TYPE)      # HIGH, rank 2

        rows = dispatch.dispatch_page()["rows"]
        codes = [r["priority"]["code"] if r["priority"] else None for r in rows]
        assert codes == ["URGENT", "HIGH", "LOW", None]


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-025 — the append-only history
# ══════════════════════════════════════════════════════════════════════════


def _a_technician(actor, email, name, skills=()):
    """A login, the technician profile beside it, and any skills it holds."""
    from apps.identity import models as identity_models

    tenant_id = _tenant_id()
    user = identity_models.User.objects.create(
        tenant_id=tenant_id, email=email, full_name=name
    )
    tech = work_models.Technician.objects.create(tenant_id=tenant_id, user=user)
    for skill_id in skills:
        work_models.TechnicianSkill.objects.create(
            tenant_id=tenant_id, technician=tech, skill_id=skill_id, proficiency="trained"
        )
    return tech


def test_us_wrk_025_tc1_each_act_appends_a_row_and_the_cache_follows_it(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])

        dispatch.record_act(dana, order.id, {"act": "assign", "technician_id": str(tech.id)})
        dispatch.record_act(dana, order.id, {"act": "unassign"})
        dispatch.record_act(dana, order.id, {"act": "assign", "technician_id": str(tech.id)})

        rows = work_models.WorkOrderAssignment.objects.filter(work_order=order).order_by("at", "id")
        assert [r.act for r in rows] == ["assign", "unassign", "assign"]
        # ⚠ THE HISTORY IS THREE ROWS AND THE ORDER CARRIES ONE ANSWER. A
        # correction is a NEW ROW (hard rule 4's shape), so "who has it now" and
        # "who has had it" are two different questions with two different homes.
        order.refresh_from_db()
        assert order.assignee_technician_id == tech.id


def test_us_wrk_025_tc2_unassign_clears_the_cache_and_keeps_the_history(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        dispatch.record_act(dana, order.id, {"act": "assign", "technician_id": str(tech.id)})
        dispatch.record_act(dana, order.id, {"act": "unassign"})
        order.refresh_from_db()
        assert order.assignee_technician_id is None
        assert order.dispatch_state == "queued"
        assert work_models.WorkOrderAssignment.objects.filter(work_order=order).count() == 2


def test_us_wrk_025_tc3_a_skill_mismatch_is_ADVICE_and_the_override_is_recorded(dana, brazos):
    """⚠ **REWRITTEN TO THE RULING, 2026-10-04 (`CR-168-BRC10` P4.5,
    `DEF-WRK-9533`).** This case asserted `BR-WRK-029`'s write-time refusal
    (`work.dispatch.skill_mismatch`). Ruling 2 of 2026-09-23 SUPERSEDES that
    rule, verbatim *"a guideline, never a block"* (decision log *"WORK BACK
    OFFICE — 36 PO RULINGS"*, ruling 2), and PO answer 2 of 2026-10-04 did the
    same for a lapsed certification. So the assignment STANDS, and the override
    is recorded — one `work.order.assigned_against_advice` audit row naming the
    missing skill (P4.6 🔒) — and the order's history marks that line."""
    with tenant_ctx(brazos):
        _reference(dana)
        work_services.seed_reference_list("work_skills", [], "test")
        skill = work_models.WorkSkill.objects.filter(tenant_id=brazos.id).first()
        # ⚠ `Service` IS A PLATFORM TABLE AND HAS NO `tenant_id` — the eleven
        # services are the product's, and `tenant_services` is what a utility
        # switches on. Filtering it by tenant is a `FieldError`, not an empty set.
        service = tenancy_models.Service.objects.filter(code="water").first()
        # ⚠ **`version=1`, BECAUSE WAVE H MADE A DRAFT UNRAISEABLE WHILE THIS
        # LANE WORKED.** `BR-WRK-008` / `US-WRK-032` TC-4: version 0 IS the
        # draft state and a draft has no settled bundle to copy, so
        # `create_work_order` now refuses one with
        # `work.order.template_not_published`. This fixture published nothing
        # and was green in this lane's own tree and RED at the branch tip —
        # which is the whole argument for verifying against the tip rather than
        # against the tree you built in.
        template = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id,
            name="Meter exchange",
            skill_id=skill.id,
            service=service,
            version=1,
        )
        raised = _order(dana, "77 Cedar Ct", template_id=str(template.id))
        # A technician who holds NO skill at all cannot be offered this job.
        nobody = _a_technician(dana, "n-obody@brazos.test", "N. Obody")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        out = dispatch.record_act(
            dana, order.id, {"act": "assign", "technician_id": str(nobody.id)}
        )
        assert out["technician"]["name"] == "N. Obody"
        assert out["against_advice"] == {"missing_skill": skill.name, "lapsed": []}
        assert work_models.WorkOrderAssignment.objects.filter(work_order=order).count() == 1


def test_us_wrk_025_tc4_an_unknown_act_is_refused_and_the_set_is_five(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        with pytest.raises(errors.ValidationError) as caught:
            dispatch.record_act(dana, order.id, {"act": "teleport"})
        assert caught.value.message_key == "work.dispatch.act_unknown"
    assert work_models.WorkOrderAssignment.ACTS == (
        "assign",
        "unassign",
        "schedule",
        "depart",
        "arrive",
    )


def test_us_wrk_025_tc5_a_backwards_window_is_refused(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        with pytest.raises(errors.ValidationError) as caught:
            dispatch.record_act(
                dana,
                order.id,
                {
                    "act": "schedule",
                    "scheduled_for": "2026-09-10T08:00:00Z",
                    "window_start": "2026-09-10T12:00:00Z",
                    "window_end": "2026-09-10T08:00:00Z",
                },
            )
        assert caught.value.message_key == "work.dispatch.window_backwards"


def test_us_wrk_025_tc6_hard_rule_7_every_act_writes_an_audit_row(dana, brazos, real_audit_trail):
    from apps.audit import models as audit_models

    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        dispatch.record_act(dana, order.id, {"act": "assign", "technician_id": str(tech.id)})
        actions = set(
            audit_models.AuditLog.objects.filter(entity_id=order.id).values_list(
                "action", flat=True
            )
        )
    assert "work.order.assign" in actions


def test_us_wrk_025_tc7_the_audit_read_is_oldest_first_and_names_who(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        raised = _order(dana, "77 Cedar Ct")
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        dispatch.record_act(dana, order.id, {"act": "assign", "technician_id": str(tech.id)})
        dispatch.record_act(dana, order.id, {"act": "depart"})
        trail = dispatch.order_audit(order.id)
        assert [r["act"] for r in trail["rows"]] == ["assign", "depart"]
        assert trail["rows"][0]["who"]["name"] == "D. Ortiz"


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-026 — six filters, and no seventh
# ══════════════════════════════════════════════════════════════════════════


def test_us_wrk_026_tc1_the_declared_filter_set_is_exactly_six(dana, brazos):
    assert dispatch.FILTER_PARAMS == ("q", "type", "status", "priority", "technician", "area")
    assert len(dispatch.FILTER_PARAMS) == 6


def test_us_wrk_026_tc2_a_seventh_bare_filter_is_refused_by_name(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        _order(dana, "77 Cedar Ct")
    answer = _list(brazos, dana, {"assignee": "somebody"})
    # ⚠ **422, NOT THE `400` `07-endpoints.md` ROW 61 WRITES, AND THE DOC IS
    # AMENDED RATHER THAN THE CODE.** Every VAL refusal in this product answers
    # 422 by law IS-7 / `OQ-004`'s closure (`core/errors.py`'s status table), and
    # one route answering 400 for a validation error would be the second error
    # shape the B12 §3 envelope exists to prevent. What row 61 is signing is
    # *refused rather than silently ignored*, and that is what this asserts.
    # Recorded in the decision log 2026-09-05; the row now reads 422.
    assert answer.status_code == 422
    # THE REFUSAL NAMES THE PARAMETER, not the rule (B14 rule 32).
    assert "assignee" in str(answer.data)


def test_us_wrk_026_tc3_the_house_f_grammar_is_still_ignored_never_refused(dana, brazos):
    """⚠ **THE COLLISION WAVE G HAD TO RECONCILE, ASSERTED FROM BOTH SIDES.**

    `07-endpoints.md` row 61 says *400 on a seventh*; `BR-SHL-011` says an
    undeclared parameter is IGNORED; and wave O shipped
    `test_wave_o_br_wrk_026_did_not_move_the_dispatcher_still_takes_six`
    asserting the second on this very route. They govern two name spaces: the
    six are BARE parameters and a seventh bare name is refused, while `f.<name>`
    is the shared table framework's grammar, which this route declares nothing
    in. Neither signed statement moved.
    """
    with tenant_ctx(brazos):
        _reference(dana)
        _order(dana, "77 Cedar Ct")
    answer = _list(brazos, dana, {"f.premises_id": "anything"})
    assert answer.status_code == 200
    assert answer.data["count"] == 1


def test_us_wrk_026_tc4_each_of_the_five_chips_narrows_the_list(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        area = tenancy_models.Area.objects.create(tenant_id=brazos.id, code="ZN", name="North")
        leak = _order(dana, "77 Cedar Ct", area_id=str(area.id))
        _order(dana, "1 Low St", order_type=LOW_TYPE)
        high = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="HIGH")

        assert dispatch.dispatch_page(filters={"priority": str(high.id)})["total"] == 1
        assert dispatch.dispatch_page(filters={"area": str(area.id)})["total"] == 1
        assert dispatch.dispatch_page(filters={"status": "queued"})["total"] == 2
        assert dispatch.dispatch_page(filters={"status": "on_site"})["total"] == 0
        assert dispatch.dispatch_page(filters={"technician": "none"})["total"] == 2
        assert dispatch.dispatch_page(q="Cedar")["total"] == 1
        rows = dispatch.dispatch_page(filters={"priority": str(high.id)})["rows"]
        assert rows[0]["order_no"] == leak["order_no"]


def test_us_wrk_026_tc5_the_footer_counts_the_utility_not_the_page(dana, brazos):
    """*Showing 8 of 10 open orders* is TWO facts. The 10 comes from the KPI
    read, because a denominator that changed when somebody typed in the search
    box would be a fact about the search box."""
    with tenant_ctx(brazos):
        _reference(dana)
        _order(dana, "77 Cedar Ct")
        _order(dana, "1 Low St", order_type=LOW_TYPE)
        narrowed = dispatch.dispatch_page(q="Cedar")
        assert narrowed["total"] == 1
        assert dispatch.kpis()["open_total"] == 2


def test_us_wrk_026_tc6_the_list_envelope_is_the_one_the_product_answers(dana, brazos):
    """A11 — one list shape. `open_total` lives on `/work/kpis` and NOT here;
    `test_us_wrk_004` asserts this key set and caught the first attempt."""
    with tenant_ctx(brazos):
        _reference(dana)
        _order(dana, "77 Cedar Ct")
    answer = _list(brazos, dana)
    assert set(answer.data) == {"count", "next", "previous", "results"}


def test_us_wrk_026_tc7_hard_rule_1_one_utility_never_sees_the_other(dana, erin, brazos, lonestar):
    with tenant_ctx(brazos):
        _reference(dana)
        _order(dana, "77 Cedar Ct")
    with tenant_ctx(lonestar):
        _reference(erin)
        _order(erin, "9 Anvil Ct")
        assert dispatch.dispatch_page()["total"] == 1
        assert dispatch.dispatch_page()["rows"][0]["premise"]["address"] == "9 Anvil Ct"
        assert dispatch.kpis()["open_total"] == 1


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-027 — a bulk act writes one row PER ORDER
# ══════════════════════════════════════════════════════════════════════════


def test_us_wrk_027_tc1_bulk_assign_of_three_writes_three_rows_never_one(dana, brazos):
    """`BR-WRK-027`, verbatim: *"Each writes one assignment or audit row PER
    ORDER — never one row for the batch."*"""
    with tenant_ctx(brazos):
        _reference(dana)
        ids = [_order(dana, f"{n} Cedar Ct")["id"] for n in range(1, 4)]
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")

        outcome = dispatch.bulk_act(
            dana, {"act": "assign", "ids": ids, "technician_id": str(tech.id)}
        )
        assert outcome["done"] == 3 and outcome["failed"] == 0
        assert work_models.WorkOrderAssignment.objects.count() == 3
        # One row per ORDER — every order has exactly one, and no order has two.
        for order_id in ids:
            assert (
                work_models.WorkOrderAssignment.objects.filter(work_order_id=order_id).count() == 1
            )


def test_us_wrk_027_tc2_the_answer_is_per_order_and_never_a_boolean(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        ids = [_order(dana, f"{n} Cedar Ct")["id"] for n in range(1, 3)]
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        outcome = dispatch.bulk_act(
            dana, {"act": "assign", "ids": ids, "technician_id": str(tech.id)}
        )
    assert [r["id"] for r in outcome["results"]] == [str(i) for i in ids]
    assert all(r["ok"] for r in outcome["results"])
    assert all("order_no" in r for r in outcome["results"])


def test_us_wrk_027_tc3_one_refused_order_does_not_take_the_others_down(dana, brazos):
    """⚠ **PROVED PROPERLY ONLY ON POSTGRESQL** (`test_us_wrk_025_dispatch_pg`).
    SQLite has no aborted-transaction state, so the version of `bulk_act` that
    catches and carries on inside ONE transaction passes this case and loses the
    whole batch in production. What this asserts is the SHAPE of the answer; the
    savepoint is proved where a failed statement actually poisons a transaction.
    """
    with tenant_ctx(brazos):
        _reference(dana)
        good = _order(dana, "77 Cedar Ct")["id"]
        tech = _a_technician(dana, "d-ortiz@brazos.test", "D. Ortiz")
        outcome = dispatch.bulk_act(
            dana,
            {
                "act": "assign",
                "ids": [good, "00000000-0000-0000-0000-000000000000"],
                "technician_id": str(tech.id),
            },
        )
    assert outcome["done"] == 1 and outcome["failed"] == 1
    assert outcome["results"][0]["ok"] is True
    assert outcome["results"][1]["ok"] is False
    assert outcome["results"][1]["reason"] == "work.dispatch.not_found"


def test_us_wrk_027_tc4_bulk_priority_moves_due_at_with_the_priority(dana, brazos):
    """A priority in this product is a PROMISE, not a colour. Raising a job to
    Urgent and leaving it due next Tuesday would put the pill and the date in
    flat contradiction on one row, and the pill is what people act on."""
    with tenant_ctx(brazos):
        _reference(dana)
        order_id = _order(dana, "77 Cedar Ct")["id"]  # HIGH, 8 h
        urgent = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="URGENT")
        dispatch.bulk_act(
            dana, {"act": "priority", "ids": [order_id], "priority_id": str(urgent.id)}
        )
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        assert order.priority_id == urgent.id
        # ⚠ RE-DATED FROM THE RAISE, NOT FROM NOW — measuring the new SLA from
        # the moment somebody noticed would forgive the lateness every time.
        assert abs((order.due_at - order.created_at) - timedelta(hours=4)) < timedelta(seconds=5)


def test_us_wrk_027_tc5_an_unknown_bulk_act_and_an_empty_selection_are_refused(dana, brazos):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as unknown:
            dispatch.bulk_act(dana, {"act": "delete", "ids": ["x"]})
        assert unknown.value.message_key == "work.dispatch.bulk_act_unknown"
        with pytest.raises(errors.ValidationError) as empty:
            dispatch.bulk_act(dana, {"act": "assign", "ids": []})
        assert empty.value.message_key == "work.dispatch.selection_empty"
    assert dispatch.BULK_ACTS == ("assign", "reschedule", "priority")


def test_us_wrk_027_tc6_hold_and_cancel_move_the_axis_and_delete_nothing(dana, brazos):
    with tenant_ctx(brazos):
        _reference(dana)
        order_id = _order(dana, "77 Cedar Ct")["id"]
        dispatch.set_dispatch_state(dana, order_id, "on_hold", "work.order.held")
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        assert order.dispatch_state == "on_hold"
        dispatch.set_dispatch_state(dana, order_id, "cancelled", "work.order.cancelled")
        order.refresh_from_db()
        assert order.dispatch_state == "cancelled"
        # NOTHING DELETED — the order keeps its number and its history.
        assert work_tables.WorkOrder.objects.filter(pk=order_id).exists()
        assert order.order_no is not None


def test_us_wrk_027_tc7_a_held_order_stays_held_when_the_phone_reports_in(dana, brazos):
    """*On hold* is a state a person put the job into deliberately. A `depart`
    arriving from a phone must not quietly take it off hold — that would be the
    product overruling the dispatcher. The act is still RECORDED."""
    with tenant_ctx(brazos):
        _reference(dana)
        order_id = _order(dana, "77 Cedar Ct")["id"]
        dispatch.set_dispatch_state(dana, order_id, "on_hold", "work.order.held")
        dispatch.record_act(dana, order_id, {"act": "depart"})
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        assert order.dispatch_state == "on_hold"
        assert work_models.WorkOrderAssignment.objects.filter(work_order_id=order_id).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-011 — the Area filter IS tenancy's list
# ══════════════════════════════════════════════════════════════════════════


def test_us_wrk_011_tc1_the_area_options_are_tenancy_areas_and_work_keeps_no_copy(dana, brazos):
    """`BR-WRK-022`, verbatim: *"Areas are `tenancy.Area` … it never duplicates
    it."* A tenant adding an area in Settings sees it here with no Work-side
    write of any kind."""
    with tenant_ctx(brazos):
        before = {o["code"] for o in dispatch.area_options()}
        tenancy_models.Area.objects.create(tenant_id=brazos.id, code="ZN", name="North")
        tenancy_models.Area.objects.create(tenant_id=brazos.id, code="ZR1", name="Route 1")
        options = dispatch.area_options()
    # ⚠ ASSERTED AS A DIFFERENCE, NOT AS A WHOLE LIST. A provisioned tenant is
    # SEEDED with areas (Downtown, East district, …), so an equality assertion
    # here would be a test of the seed rather than of this read — and would go
    # red the day somebody adds a ninth seeded district.
    assert {o["code"] for o in options} - before == {"ZN", "ZR1"}
    assert [o["name"] for o in options if o["code"] in ("ZN", "ZR1")] == ["North", "Route 1"]
    # There is no Work-owned area table to have copied them into.
    assert not any(m._meta.db_table == "work_areas" for m in work_models.__dict__.values()
                   if hasattr(m, "_meta"))


def test_us_wrk_011_tc2_an_order_points_at_the_area_and_stores_no_address(dana, brazos):
    """Hard rule 8 — an address lives on `premises` and every other entity walks
    to it. The order carries an area POINTER and no address column."""
    with tenant_ctx(brazos):
        _reference(dana)
        area = tenancy_models.Area.objects.create(tenant_id=brazos.id, code="ZN", name="North")
        raised = _order(dana, "77 Cedar Ct", area_id=str(area.id))
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.area_id == area.id
    columns = {f.name for f in work_tables.WorkOrder._meta.get_fields() if hasattr(f, "attname")}
    assert not any("address" in name for name in columns)


def test_us_wrk_011_tc3_an_unknown_area_is_a_404_never_a_403(dana, erin, brazos, lonestar):
    """HR-1 — existence must not leak. The OTHER utility's area is refused
    exactly as an area that does not exist is."""
    with tenant_ctx(lonestar):
        theirs = tenancy_models.Area.objects.create(tenant_id=lonestar.id, code="ZS", name="South")
    with tenant_ctx(brazos):
        _reference(dana)
        with pytest.raises(errors.NotFoundError):
            _order(dana, "77 Cedar Ct", area_id=str(theirs.id))


def test_us_wrk_011_tc4_the_area_options_are_this_utilitys_own(dana, erin, brazos, lonestar):
    with tenant_ctx(lonestar):
        tenancy_models.Area.objects.create(tenant_id=lonestar.id, code="ZS", name="South")
    with tenant_ctx(brazos):
        tenancy_models.Area.objects.create(tenant_id=brazos.id, code="ZN", name="North")
        codes = {o["code"] for o in dispatch.area_options()}
    assert "ZN" in codes
    assert "ZS" not in codes, "the other utility's area must not be offered here"


def test_us_wrk_011_tc5_the_route_table_mounts_every_dispatch_endpoint(dana, brazos):
    """A future lane cannot lose an include silently (config/urls.py's rule)."""
    assert resolve("/api/brazosbend/work/kpis").func is work_api.work_kpis
    assert resolve("/api/brazosbend/work/areas").func is work_api.work_areas
    assert resolve("/api/brazosbend/work-orders/bulk").func is work_api.work_orders_bulk
    one = "00000000-0000-0000-0000-000000000000"
    assert resolve(f"/api/brazosbend/work-orders/{one}").func is work_api.work_order_detail
    assert (
        resolve(f"/api/brazosbend/work-orders/{one}/assignments").func
        is work_api.work_order_assignments
    )
    assert resolve(f"/api/brazosbend/work-orders/{one}/audit").func is work_api.work_order_audit
    assert resolve(f"/api/brazosbend/work-orders/{one}/hold").func is work_api.work_order_hold
    assert resolve(f"/api/brazosbend/work-orders/{one}/cancel").func is work_api.work_order_cancel
    # ⚠ AND THE TWO METERING STILL OWNS ARE NOT SHADOWED BY THEM.
    assert resolve(f"/api/brazosbend/work-orders/{one}/accept").func is not None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-024/025/026/027/011 (EP-WRK-05) · 08-screen-layouts.md Work-007 · 07-endpoints.md §5 · 10-execution-plan.md wave G task G4
# generated: 2026-09-05 by the CR-070 wave G build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: RED PROVED FIRST — with `check_filters` removed, tc2 passes 200 instead of 400; with ACT_MOVES_TO also writing `state`, tc1 fails on "the work axis must NOT move"; quoted in the lane report
# exceptions: the append-only TRIGGER and the per-order SAVEPOINT are not provable on SQLite and live in tests/test_us_wrk_025_dispatch_pg.py (hard-won law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


def test_the_fixture_names_only_live_types(dana, brazos):
    """`DEF-WRK-5108`'s prevention: a case that raises a RETIRED type gets no
    priority and no promise, and its failure reads as a broken filter. This
    one names the cause instead."""
    retired = {name for _code, name in work_models.RETIRED_SEED_TYPES}
    with tenant_ctx(brazos):
        _reference(dana)
        for name in FIXTURE_TYPES:
            assert name not in retired, name
            row = work_models.WorkOrderType.objects.get(tenant_id=brazos.id, name=name)
            assert row.active, name
