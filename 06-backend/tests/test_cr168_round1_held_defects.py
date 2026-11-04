# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 1 (lane WORK-SRV) — the server half of the Work
#           back-office redesign, re-measured at the tip before anything is built
# Rules:    BR-WRK-029 as SUPERSEDED by ruling 2 (2026-09-23, "a guideline,
#           never a block") · BR-MET-110 + ruling 18 (2026-09-24, "back office
#           cannot complete the job it can only accept it") · US-WRK-042 TC-5 ·
#           BR-WRK-023 · BR-WRK-006 · NFR-5 (no hard caps) · BR-WRK-025
# Tests:    this file — one HELD case per defect, each `xfail(strict=True)`
# ───────────────────────────────────────────────────────
"""CR-168 round 1 — nine defects (DEF-WRK-9525..9533) the redesign's server half found at the tip,
each proved by a case that FAILS on today's code.

⚠ **EVERY CASE HERE IS `xfail(strict=True)` ON PURPOSE, AND THE STRICTNESS IS
THE POINT** (hard-won law 2's mirror: write the test that fires when the hold
expires, in the same commit as the hold). Round 1 builds nothing — the brief is
fact-finding and a contract — so each defect is proved red and HELD:

  * today the case fails, the `xfail` absorbs it, and the suite stays readable
    (law 7 habit 1 — a suite with a standing red is where a true one hides);
  * the day round 2 lands the fix the case PASSES, strict `xfail` turns that
    into a FAILURE naming the defect, and the lane removes the marker in the
    commit that closes the row. A held case nobody has to remember to release.

⚠ **NO CASE IS HELD ANY MORE (2026-10-04).** SRV-1 released `9525`, `9526`, `9529`,
`9530` and `9532` in `2.497.0`; SRV-2 released `9527`, `9528`, `9531` and `9533` in
`2.500.0`. Every case below is now an ordinary regression guard.

Each case's failure on the tip was run WITHOUT its marker and is quoted in its
docstring, so a reader can tell the case fails for the stated reason rather
than for a fixture fault (law 7 habit 2: what would make this pass wrongly).

SQLite is enough for every case here: none of them depends on a trigger, RLS
or an aborted transaction (law 14). The ones that will need PostgreSQL when
they are FIXED (bulk raise, the acceptance money path) are named in CR-168 §7.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import models as tenancy_models
from apps.work import dispatch
from apps.work import edit as work_edit
from apps.work import mobile as work_mobile
from apps.work import models as work_models
from apps.work import services as work_services
from apps.work.seams import customers_seam
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import make_premises, make_unit  # noqa: F401
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _reference():
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")


def _order(actor, address, **payload):
    premises = make_premises(actor, address_line=address, services_available=["water"])
    body = {"type": "Leak investigation", "service": "water", "premises_id": premises["id"], **payload}
    return w6.create_work_order(actor, None, body)


def _technician(email, name):
    from apps.identity import models as identity_models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    user = identity_models.User.objects.create(tenant_id=tenant_id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant_id, user=user)


@pytest.fixture()
def stored_audit():
    """The REAL trail — `apps.audit.services.store_row` — so a read of
    `audit_log` sees what the services wrote (`test_w6_connection_detail`'s
    fixture). Restored afterwards."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def _as_field(technician):
    """The technician's own login, in the service actor shape."""
    from types import SimpleNamespace

    return SimpleNamespace(id=technician.user_id, role="field_technician")


def _skilled_template(tenant):
    work_services.seed_reference_list("work_skills", [], "test")
    skill = work_models.WorkSkill.objects.filter(tenant_id=tenant.id).first()
    service = tenancy_models.Service.objects.filter(code="water").first()
    return work_tables.WorkOrderTemplate.objects.create(
        tenant_id=tenant.id, name="Meter exchange", skill_id=skill.id, service=service, version=1
    )


# ══════════════════════════════════════════════════════════════════════════
# P4.5 — ruling 2: the skill match ADVISES and never blocks
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9533_an_assignment_against_skill_advice_succeeds(dana, brazos):
    """Ruling 2 (2026-09-23): *"a guideline, never a block"* — `BR-WRK-029`'s
    write-time refusal is SUPERSEDED. A dispatcher who gives a meter exchange to
    somebody without the skill gets the assignment, and the override is
    recorded (P4.6).

    Fails on the tip with ``core.errors.ValidationError`` —
    ``message_key='work.dispatch.skill_mismatch'`` raised from
    ``dispatch._candidate_or_refuse`` (dispatch.py:756). The signed-old-rule
    twin is ``test_us_wrk_025_tc3_a_skill_mismatch_is_refused_by_name``, which
    goes red BY DESIGN in the commit that fixes this.
    """
    with tenant_ctx(brazos):
        _reference()
        template = _skilled_template(brazos)
        raised = _order(dana, "77 Cedar Ct", template_id=str(template.id))
        nobody = _technician("n-obody@brazos.test", "N. Obody")
        out = dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(nobody.id)})
        assert out["technician"]["name"] == "N. Obody"


# ══════════════════════════════════════════════════════════════════════════
# P1.34 — ruling 18: the office never completes a job
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9525_the_office_cannot_close_a_job_it_does_not_hold(dana, brazos):
    """`BR-MET-110` + ruling 18: the technician completes, the office accepts.
    A job held by D. Ortiz is closed by Dana — a System Admin at a desk — and
    must be refused; the door's own decorator comment says *"the FIELD
    reports"* and admits ``AnyTenantRole`` (metering/api.py:3116).

    Fails on the tip with ``DID NOT RAISE``: ``submit_field_result`` writes
    ``state='completed'`` for any caller (connections.py:7202).
    """
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana, "77 Cedar Ct")
        tech = _technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        with pytest.raises((errors.ValidationError, errors.AuthError)) as caught:
            w6.submit_field_result(dana, raised["id"], field_data={"ok": True}, outcome="passed")
        assert caught.value.message_key == "work.order.closed_by_field_only"


def test_def_wrk_9525_the_edit_page_cannot_set_complete(dana, brazos):
    """The second office door: ``PATCH /work-orders/{id}/edit`` accepts any
    dispatch token, ``complete`` included (edit.py:217-227), so the Status
    list's *Complete* is a completion the server takes from a desk.

    Fails on the tip with ``DID NOT RAISE``.
    """
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana, "77 Cedar Ct")
        with pytest.raises(errors.ValidationError) as caught:
            work_edit.save_order_edit(dana, raised["id"], {"dispatch_state": "complete"})
        assert caught.value.message_key == "work.order.closed_by_field_only"


# ══════════════════════════════════════════════════════════════════════════
# P1.31 — closing a job leaves the dispatch axis on "Scheduled"
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9526_a_closed_job_reads_complete_on_the_dispatch_axis(dana, brazos):
    """`BR-WRK-023` has seven dispatch tokens and ``complete`` is one of them,
    but the close writes ``state`` and never ``dispatch_state``
    (connections.py:7202-7217), so a finished job reads *Scheduled* (or
    *Queued*) on the dispatcher's list and on the phone's done count.

    Fails on the tip with ``AssertionError: assert 'scheduled' == 'complete'``.
    """
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana, "77 Cedar Ct")
        tech = _technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        # Closed by D. Ortiz, the technician it was given to — since P1.34
        # (ruling 18) nobody else may close it, which the case above proves.
        w6.submit_field_result(
            _as_field(tech), raised["id"], field_data={"ok": True}, outcome="passed"
        )
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.state == "completed"
        assert order.dispatch_state == "complete"


# ══════════════════════════════════════════════════════════════════════════
# P2.13 — a unit of another building is accepted without a word
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9527_a_unit_of_another_building_is_refused(dana, brazos):
    """``create_work_order`` compares a picked unit with the CONNECTION's
    premises only (connections.py:2700, ``work.order.unit_not_on_build``); a
    job raised on a premises names any unit of any building.

    Fails on the tip with ``DID NOT RAISE``.
    """
    with tenant_ctx(brazos):
        _reference()
        here = make_premises(dana, address_line="12 Kestrel Park", services_available=["water"])
        there = make_premises(dana, address_line="500 Main St", services_available=["water"])
        unit_there = make_unit(dana, there["id"], label="Unit 205")
        with pytest.raises(errors.ValidationError) as caught:
            w6.create_work_order(
                dana,
                None,
                {"type": "Leak investigation", "service": "water",
                 "premises_id": here["id"], "unit_id": unit_there["id"]},
            )
        assert caught.value.message_key == "work.order.unit_not_on_premises"


# ══════════════════════════════════════════════════════════════════════════
# P2.14 — the template's scope and service do not reach the job
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9528_a_per_unit_water_template_raises_a_per_unit_water_job(dana, brazos):
    """``scope`` comes from the request and defaults to ``per_premise``
    (connections.py:2684); ``service`` likewise. A *per unit, water* template
    raised with neither in the payload lands per premises with no service.

    Fails on the tip with ``AssertionError: assert 'per_premise' == 'per_unit'``.
    """
    with tenant_ctx(brazos):
        _reference()
        service = tenancy_models.Service.objects.filter(code="water").first()
        template = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id, name="Tap and service line", scope="per_unit",
            service=service, version=1,
        )
        premises = make_premises(dana, address_line="500 Main St", services_available=["water"])
        unit = make_unit(dana, premises["id"], label="Unit 205")
        raised = w6.create_work_order(
            dana, None,
            {"type": "Tap and service line", "premises_id": premises["id"],
             "unit_id": unit["id"], "template_id": str(template.id)},
        )
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.scope == "per_unit"
        assert order.service_id == service.id


# ══════════════════════════════════════════════════════════════════════════
# P1.15 — the customer's name and phone never reach the job
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9529_the_job_names_the_holder_and_their_phone(brazos, marcus):
    """`US-WRK-042` TC-5: *Miller, Sarah · (512) 555-0114*. ``mobile.
    _customer_contact`` asks ``customers_seam.account()`` for ``name`` and
    ``phone`` (mobile.py:345-346) and the seam serves id, number, status and
    unit only (customers_seam.py:42-51), so both are ``None`` on every job.

    Fails on the tip with ``AssertionError: assert None == 'Sarah Miller'``.
    """
    from apps.customers import services as customers_services
    from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

    with tenant_ctx(brazos):
        _reference()
        unit = _unit_with_plan(marcus, brazos)
        account = customers_services.create_account(marcus, _create_payload(unit["id"]))
        customers_services.update_account_contact(
            marcus, account["id"], {"full_name": "Sarah Miller", "phone": "(512) 555-0114"}
        )
        served = customers_seam.account(account["id"])
        assert served.get("name") == "Sarah Miller"
        assert served.get("phone") == "(512) 555-0114"
        order = w6.create_work_order(
            marcus, None, {"type": "Leak investigation", "service": "water", "account_id": account["id"]}
        )
        row = work_tables.WorkOrder.objects.get(pk=order["id"])
        contact = work_mobile._customer_contact(row)
        assert contact["name"] == "Sarah Miller"


# ══════════════════════════════════════════════════════════════════════════
# P1.25 — the edit page cannot select the technician it opens with
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9530_the_edit_form_serves_the_holders_id(dana, brazos):
    """``form_values`` sends ``dispatch._holder(order)`` — kind, name, slug and
    NO id (edit.py:193) — while the form posts back ``technician_id``. So the
    picker opens on *Nobody yet* and a Save that touches only the slot can
    unassign the job.

    Fails on the tip with ``KeyError: 'id'``.
    """
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana, "77 Cedar Ct")
        tech = _technician("d-ortiz@brazos.test", "D. Ortiz")
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        values = work_edit.form_values(raised["id"])
        assert values["technician"]["id"] == str(tech.id)


# ══════════════════════════════════════════════════════════════════════════
# NFR-5 — the "anybody can take this" list stops at 200
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9531_a_job_needing_no_skill_offers_every_holder(dana, brazos, settings):
    """``assign_candidates`` for a template naming no skill reads
    ``workforce.crews_page(per=workforce.MAX_PAGE_SIZE)["rows"]``
    (dispatch.py:681) — ONE page of at most 200 — and calls it the whole list.
    NFR-5: no hard caps anywhere; at the 201st crew or technician a dispatcher
    is silently not offered somebody. The cap is lowered here only so the
    case runs in a second; the arithmetic is the same at 200.

    Fails on the tip with ``AssertionError: assert 3 == 4``.
    """
    from apps.work import workforce

    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana, "77 Cedar Ct")
        for n in range(4):
            work_models.Crew.objects.create(tenant_id=brazos.id, name=f"Field crew {n}")
        was = workforce.MAX_PAGE_SIZE
        workforce.MAX_PAGE_SIZE = 3
        try:
            offered = dispatch.assign_candidates(raised["id"])
        finally:
            workforce.MAX_PAGE_SIZE = was
        assert len(offered["rows"]) == 4


# ══════════════════════════════════════════════════════════════════════════
# P4.11 — a hold never reaches the order's own history
# ══════════════════════════════════════════════════════════════════════════


def test_def_wrk_9532_a_hold_appears_on_the_orders_audit(dana, brazos, stored_audit):
    """``GET /work-orders/{id}/audit`` reads ``work_order_assignments`` only
    (dispatch.py:614-658); a hold and a cancel write ``audit_log`` and the
    order's Audit tab never shows them.

    Fails on the tip with ``AssertionError: assert 'hold' in []``.
    """
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana, "77 Cedar Ct")
        work_services.seed_reference_list("work_hold_reasons", [], "test")
        # Through the hold door the screen uses (`POST …/hold`, which since
        # P0.3 takes a reason); round 1 called `set_dispatch_state` with an
        # action name no door writes.
        dispatch.hold(dana, raised["id"], {"reason_code": "WEATHER"})
        rows = dispatch.order_audit(raised["id"])["rows"]
        acts = [row["act"] for row in rows]
        assert "hold" in acts
        assert rows[-1]["after_display"] == "Weather"
