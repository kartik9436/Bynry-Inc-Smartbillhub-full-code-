# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-012 (S22 Record payment — the account-side entry point into
#           the payments service, and hard rule 7's audit row) ·
#           US-CUS-015 (S22 Add note — `account_notes`, BR-CUS-035; the
#           disconnect-notice half is NOT built and its refusal is asserted) ·
#           US-CUS-016 (S23 steps 1–2 — the plan picker and the proration
#           PREVIEW, which writes nothing) ·
#           US-CUS-017 (S23 step 3 — confirm, the unit assignment, the
#           notification and the audit row)
#           Screens: S21 · S22 · S23
# Rules:    BR-CUS-035 (notes) · BR-CUS-037 (S22 modals are ENTRY POINTS — they
#           validate, call the owning module's service and audit; customers
#           writes no financial table) · BR-CUS-041 (change plan: published +
#           service-compatible only; effective immediate/next-cycle/custom) ·
#           BR-CUS-042 vs BR-CUS-062 (the deposit-differential conflict —
#           OQ-179, refused by name here) · BR-CUS-011/013 (the history row
#           carries who/when/from→to/reason/source and snapshots the version) ·
#           BR-RAT-004 / B4.3 (proration is CALENDAR days and lives in the
#           rating engine — this suite proves customers never computes it) ·
#           BR-RAT-030 (drafts are not assignable) · BR-RAT-043 (eligibility is
#           advisory-with-audit) · BR-PAY-001 (the staff allocation choice) ·
#           CLAUDE.md rule 7 (every money action writes audit_log)
# ───────────────────────────────────────────────────────
"""W4/W8 customers ACTION lane — the S22 modals and the S23 wizard.

RED-PROVED FIRST (hard-won law 7). Every assertion below was written and run
against the tree as it stood before this lane, and the verbatim failures are in
the lane report. The two the brief names explicitly:

  * `test_us_cus_016_tc3__the_prorated_base_comes_from_the_rating_engine`
    fails with `AttributeError: module 'apps.customers.services' has no
    attribute 'preview_plan_change'` — there was no preview at all, so there
    was nothing to prove the arithmetic's home.
  * `test_us_cus_017_tc1__confirming_writes_plan_changed_to_audit_log` fails
    with `AttributeError: module 'apps.customers.services' has no attribute
    'change_plan'` — the wizard's exit did not exist, so no audit row could.

WHAT THIS FILE DELIBERATELY ASSERTS AS A REFUSAL, NOT A FEATURE
--------------------------------------------------------------
Three things the stories ask for cannot be built today, and each is asserted as
a NAMED refusal so that the day its blocker clears the test goes red and someone
comes back:

  1. The **deposit differential** (US-CUS-016 §7's −$50.00). BR-CUS-042 says
     compute it; BR-CUS-062 — the LATER PO ruling, corroborated by 11b §2.6 and
     by `apps/rating/proration.py`'s own docstring — says there is no recompute
     in v1. Two CONFIRMED rules, one customer-facing figure. OQ-179.
  2. The **usage half** of a mid-cycle preview. B4.3 prorates base AND usage,
     and pricing usage for a period that has not happened needs a forecast that
     exists nowhere in this repo. OQ-180.
  3. The **billing period** itself. Metering publishes no read of a unit's cycle
     window, so a mid-cycle split cannot even be located on a calendar. The seam
     is named and unwired; the preview refuses the prorated lines by name.
"""

from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import seams as customers_seams
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
# CR-048 wave B task B11 — the plan-change letter's own row is now asserted
# rather than a dict shape, so this file reads the queue and the seed catalogue.
from apps.notifications import models as notification_models
from apps.notifications import seed_templates
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    audit_actions,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — every row through the service of the module that owns it
# ══════════════════════════════════════════════════════════════════════════
def _plan(tenant, *, name, code, services, base_charges, status="published"):
    """A rate plan with a base charge per service — EP-CUS-05 §4's shape.

    `base_charge` is what the preview compares, so it is set here rather than
    defaulted: US-CUS-016's worked example is RES-STD $30.50 (18.50 E + 12.00 W)
    against Senior $12.00, and a plan with no base charges would make the whole
    comparison read zero.
    """
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name, "status": status}
    )
    plan.status = status
    plan.name = name
    plan.save(update_fields=["status", "name"])
    for service_code, base in zip(services, base_charges, strict=True):
        service = tenancy_models.Service.objects.get(code=service_code)
        tariff, _ = rating_models.Tariff.objects.get_or_create(
            tenant=tenant, name=f"{name} — {service_code}", service=service
        )
        rating_models.PlanRateSchedule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
        )
        rating_models.PlanService.objects.update_or_create(
            tenant=tenant,
            rate_plan=plan,
            service=service,
            defaults={"base_charge": Decimal(base), "currency": "USD"},
        )
    return plan


def _account_on(actor, tenant, *, plan, services=("electric", "water")):
    """An ACTIVE account on a unit that holds `plan` — J2 steps 1–4."""
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label="Unit A")
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    for code in services:
        metering_services.ensure_service_point(unit["id"], code)
    created = customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": "2026-02-01",
            "contact": {"full_name": "Sarah Miller", "email": "sarah.miller@example.com"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                "Sarah Miller", account_type="residential"
            ),
        },
    )
    customers_services.activate_account(actor, created["id"])
    return created["id"], unit["id"]


def _world(actor, tenant):
    """The EP-CUS-05 §4 world: A-10432 on RES-STD, with Senior available."""
    res_std = _plan(
        tenant,
        name="Residential Standard",
        code="res-std",
        services=("electric", "water"),
        base_charges=("18.50", "12.00"),
    )
    senior = _plan(
        tenant,
        name="Senior / Low-income",
        code="senior",
        services=("electric",),
        base_charges=("12.00",),
    )
    draft = _plan(
        tenant,
        name="Vacant / Standby",
        code="vacant-standby",
        services=("electric",),
        base_charges=("5.00",),
        status="draft",
    )
    account_id, unit_id = _account_on(actor, tenant, plan=res_std)
    return {
        "account_id": account_id,
        "unit_id": unit_id,
        "res_std": res_std,
        "senior": senior,
        "draft": draft,
    }


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-012 — Record payment (S22). The MODAL is customers'; the payment,
# its allocations and its idempotency are the payments module's (BR-CUS-037).
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_012_tc1__the_account_page_records_through_the_payments_endpoint(
    brazos, marcus, audit_rows
):
    """TC-1: the S22 modal's exit is `POST /accounts/{id}/payments` — the SAME
    path S33's Record modal uses (BR-CUS-037: entry point, not a second money
    path) — and it lands hard rule 7's `payment.recorded` row.

    Driven through the REAL endpoint, because "the account page can take a
    customer's money" is the claim, and a service call would not prove that a
    route exists to reach it from S21.
    """
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        audit_rows.clear()
        response = api_call(
            __import__("apps.payments.api", fromlist=["x"]).account_payments,
            "post",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            data={
                "amount": "247.30",
                "posted_at": "2026-08-08",
                "cleared_at": "2026-08-08",
                "confirmation": "ACH-2028104",
                "apply_to": "oldest_first",
                "idempotency_key": "s22-modal-token-1",
            },
            account_id=str(world["account_id"]),
        )

    assert response.status_code == 201
    assert "payment.recorded" in audit_actions(audit_rows)


def test_us_cus_012_tc5__a_zero_amount_is_refused_before_any_row_exists(brazos, marcus):
    """TC-5 (negative): amount must be > 0. The SERVER refuses — the modal's
    inline error is UX only (B8 forms), and this is the half that holds."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        response = api_call(
            __import__("apps.payments.api", fromlist=["x"]).account_payments,
            "post",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            data={
                "amount": "0",
                "posted_at": "2026-08-08",
                "idempotency_key": "s22-modal-token-zero",
            },
            account_id=str(world["account_id"]),
        )
    # B12 §3 maps the whole BIZ class to 422; the sentence a clerk reads travels
    # in `params.detail` and the rule id in `br_ref` (BR-PAY-002).
    assert response.status_code == 422


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-015 — Add note (BUILT) and Disconnect notice (REFUSED, by name)
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_015_tc4__a_pinned_note_is_written_ordered_first_and_audited(
    brazos, marcus, audit_rows
):
    """TC-4 / US-CUS-011 TC-3: "Customer called about leak", pinned, renders
    first and lands `note.created` (BR-CUS-035, IS-1 audited)."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        customers_services.create_account_note(
            marcus, world["account_id"], {"title": "Move-in complete", "body": "Keys handed over."}
        )
        audit_rows.clear()
        pinned = customers_services.create_account_note(
            marcus,
            world["account_id"],
            {
                "title": "Customer called about leak",
                "body": "Meter reading twice normal.",
                "pinned": True,
            },
        )
        rows = customers_selectors.account_notes(world["account_id"])

    assert pinned["pinned"] is True
    assert pinned["customer_visible"] is False  # BR-CUS-035: captured, inert in v1
    assert [row["title"] for row in rows][0] == "Customer called about leak"
    assert "note.created" in audit_actions(audit_rows)


def test_us_cus_011_tc3__the_notes_tab_orders_pinned_first_then_newest(brazos, marcus):
    """US-CUS-011 TC-3 + the EP-CUS-03 capability row: "pinned first, then date
    desc". Asserted on the SELECTOR, because the order is the index's (migration
    0007) and a screen that re-sorted in Python would be a second definition of
    it — and would be the one that ran on the tenant with four hundred notes."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        customers_services.create_account_note(marcus, world["account_id"], {"title": "First"})
        customers_services.create_account_note(marcus, world["account_id"], {"title": "Second"})
        customers_services.create_account_note(
            marcus, world["account_id"], {"title": "Pinned", "pinned": True}
        )
        titles = [row["title"] for row in customers_selectors.account_notes(world["account_id"])]
    assert titles == ["Pinned", "Second", "First"]


def test_us_cus_011_tc3__editing_a_note_is_audited_with_the_whole_row(brazos, marcus, audit_rows):
    """The audited EDIT (IS-1 / BR-AUD-003). Driven through the SERVICE and not
    a screen, deliberately: `PATCH /accounts/{id}/notes/{noteId}` is served and
    the shared frontend client has no PATCH verb (get/post/put/del only), so no
    screen reaches it yet and that gap is REPORTED rather than papered over by
    re-pointing a contracted route at PUT."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        note = customers_services.create_account_note(
            marcus, world["account_id"], {"title": "Customer called about leak"}
        )
        audit_rows.clear()
        updated = customers_services.update_account_note(
            marcus, world["account_id"], note["id"], {"pinned": True}
        )
    assert updated["pinned"] is True
    assert "note.updated" in audit_actions(audit_rows)
    row = next(r for r in audit_rows if r.get("action") == "note.updated")
    # The whole row, before and after — that is what makes an edit reviewable
    # rather than a timestamp saying something changed.
    assert row["before"]["pinned"] is False
    assert row["after"]["pinned"] is True


def test_us_cus_015_tc7__a_note_with_no_title_and_no_body_writes_nothing(brazos, marcus):
    """US-CUS-011 TC-7: title OR body is required; an empty note is refused and
    no row is created."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        before = customers_models.AccountNote.objects.count()
        with pytest.raises(errors.ValidationError):
            customers_services.create_account_note(
                marcus, world["account_id"], {"title": "  ", "body": ""}
            )
        assert customers_models.AccountNote.objects.count() == before


def test_us_cus_015_tc1__the_disconnect_notice_names_the_door_that_works(brazos, marcus):
    """⚠ **REWRITTEN 2026-09-07 (`DEF-CUS-4631`), AND THE OLD VERSION IS THE
    REASON THE DEFECT LIVED FOR THREE WEEKS.**

    This test used to assert `"OQ-133" in str(refusal.value)`, with a docstring
    saying *"the medical-hold flag (TC-5) has no column; and WHERE the ladder
    resumes is OQ-133/136/137, unruled … This test exists so that the day any of
    those lands, the refusal has to be revisited deliberately."*

    **Every one of those things landed and the test never noticed**, because
    what it actually asserted was that the SENTENCE still contained `OQ-133` —
    which stays true no matter how stale the sentence gets. A test written to
    fire when a hold expires fires only if it asks about the HOLD; asking about
    the refusal's wording pins the refusal instead. `OQ-133`, `OQ-136` and
    `OQ-137` all closed on 2026-08-12; `notice_history` is a real table
    (`payments.collections_models.NoticeHistory`) and `medical_hold_for` is a
    real read.

    So the assertion is inverted: the refusal must NOT name an open question,
    and must point at the mounted disconnect-case path. The day somebody makes
    this function do the work, it stops raising and this test says so.
    """
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        with pytest.raises(NotImplementedError) as refusal:
            customers_services.send_disconnect_notice(
                marcus, world["account_id"], {"tier": "second_5_day", "cut_date": "2026-08-18"}
            )
    sentence = str(refusal.value)
    # No OQ id at all: nothing here waits on a decision any more.
    assert "OQ-" not in sentence
    # And it names where the work actually happens, so a caller is redirected
    # rather than stopped.
    assert "disconnect-case" in sentence


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-016 — steps 1–2. THE PREVIEW WRITES NOTHING AND COMPUTES NO MONEY
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_016_tc1__step_one_offers_published_service_compatible_plans_only(brazos, marcus):
    """TC-1 + TC-5: the picker lists PUBLISHED plans whose services are a
    subset of the unit's (BR-RAT-030 / BR-CUS-041), names the current plan for
    contrast, and carries the "Drops water service" note per row."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        options = customers_services.plan_change_options(world["account_id"])

    codes = {row["code"] for row in options["plans"]}
    assert "senior" in codes
    assert "vacant-standby" not in codes  # BR-RAT-030 — a draft is not assignable
    assert options["current_plan"]["code"] == "res-std"
    senior = next(row for row in options["plans"] if row["code"] == "senior")
    assert senior["drops_services"] == ["water"]


def test_us_cus_016_tc2__the_next_cycle_preview_states_the_base_delta_and_nothing_it_cannot(
    brazos, marcus
):
    """TC-2 §7's first half, and ONLY that half.

    The §4 fixture's next-cycle date is Sep 1 2026, given here as an explicit
    date because the "Next cycle start" OPTION cannot be resolved to a day —
    see the next test. Base delta next bill = 12.00 − 30.50 = **−18.50** — plan
    facts, full periods, no proration involved.

    The −$50.00 deposit differential and the −$68.50 net that §7 also states are
    NOT produced: BR-CUS-062 forbids the recompute BR-CUS-042 requires
    (OQ-179), so the line is refused BY NAME and the net impact says which lines
    it excludes rather than quietly summing a shorter list.
    """
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        preview = customers_services.preview_plan_change(
            world["account_id"],
            {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-09-01"},
        )

    assert preview["base"]["current_total"] == "30.500000"
    assert preview["base"]["new_total"] == "12.000000"
    assert preview["base"]["delta"] == "-18.500000"
    assert preview["deposit_differential"] is None
    assert preview["deposit_differential_unavailable"]["oq_ref"] == "OQ-179"
    assert "deposit_differential" in preview["net_impact"]["excludes"]
    assert "usage" in preview["net_impact"]["excludes"]


def test_us_cus_016_tc2__the_next_cycle_option_refuses_rather_than_guessing_a_month(brazos, marcus):
    """ "Next cycle start" is a DATE, and nobody can name it. The cycle window
    lives in metering (`cycles.window_start/_end` through `service_points`) and
    metering publishes no read of it, so the option refuses with that reason.

    The alternative — "next month, same day" — would be a date invented from a
    calendar nobody configured, and it is the date the whole change hangs on."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        with pytest.raises(errors.ApiError) as refusal:
            customers_services.preview_plan_change(
                world["account_id"],
                {"rate_plan_id": str(world["senior"].id), "effective": "next_cycle"},
            )
    assert refusal.value.br_ref == "BR-MET-009"


def test_us_cus_016_tc3__the_prorated_base_comes_from_the_rating_engine(
    brazos, marcus, monkeypatch
):
    """TC-3 — THE test the brief asks for: a proration figure computed anywhere
    but the engine is a defect.

    B4.3 prorates on service days ÷ cycle days and that rule lives in exactly
    one place, `apps.rating.engine.prorate_base_charge`. Here the engine is
    replaced by a sentinel: if the preview's prorated line still reports the
    real ratio, customers computed it itself and the test fails. Nothing about
    the sentinel's value is meaningful — only its provenance is.
    """
    calls: list[dict] = []

    def _sentinel(*, base_charge, period):
        calls.append({"base": base_charge, "days": (period.service_days, period.cycle_days)})
        return Decimal("999.99")

    monkeypatch.setattr(customers_seams, "prorate_base_charge", _sentinel)
    monkeypatch.setattr(
        customers_seams,
        "billing_period_for_unit",
        # ⚠ `**_as_of` since `DEF-2708`: the preview now asks for the period the
        # EFFECTIVE date falls in rather than the one today falls in
        # (BR-TEN-043), so the seam is called with a keyword. The dates are
        # unchanged — 6 August is inside this August either way, so the split
        # this test asserts (5 / 26 of 31) is the same split.
        lambda unit_id, **_as_of: {"start": "2026-08-01", "end": "2026-08-31"},
    )
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        preview = customers_services.preview_plan_change(
            world["account_id"],
            {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-08-06"},
        )

    assert calls, "the preview must ask the rating engine — it may not prorate anything itself"
    # 5 days on the old plan (Aug 1–5), 26 on the new (Aug 6–31), 31-day cycle.
    assert calls[0]["days"] == (5, 31)
    assert calls[1]["days"] == (26, 31)
    assert preview["proration"]["current_plan_line"]["amount"] == "999.99"


def test_us_cus_016_tc3__without_a_billing_period_the_prorated_lines_refuse_by_name(brazos, marcus):
    """The mid-cycle split needs to know where the cycle starts and ends, and
    metering publishes no read of a unit's cycle window. So the preview says
    so, names the contract it wants, and states no prorated figure at all —
    rather than assuming a 30-day month, which would be money invented from a
    calendar nobody configured."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        preview = customers_services.preview_plan_change(
            world["account_id"],
            {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-08-06"},
        )

    assert preview["proration"] is None
    assert preview["proration_unavailable"]["code"] == "billing_period_unpublished"


def test_us_cus_016_tc4__a_date_behind_an_issued_bill_is_blocked(brazos, marcus, monkeypatch):
    """TC-4: issued bills are untouched (BR-BIL-004) — the earliest allowed
    effective date is the day after the last issued bill's period end, and the
    refusal points at the correction path (J6) rather than silently clamping."""
    monkeypatch.setattr(customers_seams, "last_issued_invoice_period_end", lambda _id: "2026-07-31")
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        with pytest.raises(errors.ApiError) as refusal:
            customers_services.preview_plan_change(
                world["account_id"],
                {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-07-15"},
            )
    assert refusal.value.br_ref == "BR-BIL-004"


def test_us_cus_016_tc5__a_draft_plan_forged_into_the_request_is_rejected(brazos, marcus):
    """TC-5 (negative): published-only (BR-RAT-030). Nothing previewed."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        with pytest.raises(errors.ApiError):
            customers_services.preview_plan_change(
                world["account_id"],
                {"rate_plan_id": str(world["draft"].id), "effective_on": "2026-09-01"},
            )


def test_us_cus_016_tc1__the_preview_writes_nothing(brazos, marcus):
    """US-CUS-016 §1, verbatim: "this story computes nothing itself and WRITES
    NOTHING". Asserted against the two tables a plan change would touch."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        before = rating_models.UnitPlanAssignment.objects.count()
        customers_services.preview_plan_change(
            world["account_id"],
            {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-09-01"},
        )
        assert rating_models.UnitPlanAssignment.objects.count() == before


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-017 — step 3: confirm, sync the unit, notify, audit
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_017_tc1__confirming_writes_plan_changed_to_audit_log(brazos, marcus, audit_rows):
    """TC-1 — the second test the brief asks for: an action that changes what a
    customer will be charged and leaves no audit row is a defect.

    One transaction: the unit's plan moves, the append-only history row lands
    with source `change_plan` and the actor, and `plan.changed` is written."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        audit_rows.clear()
        result = customers_services.change_plan(
            marcus,
            world["account_id"],
            {
                "rate_plan_id": str(world["senior"].id),
                "effective_on": "2026-09-01",
                "reason": "customer qualified — CAP",
                "notify": False,
            },
        )
        rows = rating_models.UnitPlanAssignment.objects.filter(unit_id=world["unit_id"]).order_by(
            "assigned_from"
        )

    assert result["assignment"]["source"] == "change_plan"
    assert result["assignment"]["assigned_from"] == "2026-09-01"
    assert [str(row.assigned_to) for row in rows][
        0
    ] == "2026-08-31"  # prior row closed the day before
    assert "plan.changed" in audit_actions(audit_rows)


def test_us_cus_017_tc1__the_deposit_differential_instruction_is_refused_by_name(brazos, marcus):
    """US-CUS-017 §1 (c) asks for a deposit-differential instruction. It is not
    registered and the result says why: BR-CUS-042 and BR-CUS-062 disagree
    (OQ-179), and customers may not pick between two CONFIRMED rules."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        result = customers_services.change_plan(
            marcus,
            world["account_id"],
            {
                "rate_plan_id": str(world["senior"].id),
                "effective_on": "2026-09-01",
                "notify": False,
            },
        )
    codes = {problem["code"] for problem in result["problems"]}
    assert "deposit_differential_not_registered" in codes
    assert any(problem.get("oq_ref") == "OQ-179" for problem in result["problems"])


def test_us_cus_017_tc4__notification_off_still_changes_the_plan_and_queues_nothing(brazos, marcus):
    """TC-4: the election is the customer's contact, not the change itself."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        result = customers_services.change_plan(
            marcus,
            world["account_id"],
            {
                "rate_plan_id": str(world["senior"].id),
                "effective_on": "2026-09-01",
                "notify": False,
            },
        )
    assert result["notification"] is None
    assert result["assignment"]["rate_plan_id"] == str(world["senior"].id)


def test_us_cus_017_tc1__electing_the_email_queues_it_through_notifications(brazos, marcus):
    """TC-1's notification half. The queue is the notifications module's and is
    reached BY NAME (BR-NOT-005: every message is WRITTEN, never sent inline) —
    customers writes no row in `outbound_messages` itself.

    ⚠ **STRENGTHENED 2026-08-30 · CR-048 wave B task B11, AND IT USED TO PASS
    OVER A LETTER THAT COULD NOT RENDER.** It asserted only that a notification
    dict came back with a non-empty `channels` list. That was true of the old
    trigger and told nobody that the row it wrote was pinned to `plan_change` —
    a code no catalogue declares — keyed on the ACCOUNT so a second change
    deduped into the first, riding the PAYMENT-plan source kind, and carrying
    no event so the settings switch did nothing.

    So the assertions are now about the ROW, which is the only thing a customer
    ever receives, and each one is a fault this wave closed.

    ⚠ **AND IT IS TWO ROWS SINCE 2026-08-30, NOT ONE.** The PO widened
    BR-NOT-024's print floor from four source kinds to six that day and
    `account` — the kind this very case moved the letter onto — is one of them,
    because it carries the deposit-received confirmation and that acknowledges
    money received. So a rate-plan-change letter is queued on the elected email
    AND on paper. The read below was `objects.get(...)`, which now raises
    `MultipleObjectsReturned`; it asks for the EMAIL row by name instead, and
    the paper row is asserted separately rather than filtered away silently.
    """
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        result = customers_services.change_plan(
            marcus,
            world["account_id"],
            {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-09-01", "notify": True},
        )
        assert result["notification"] is not None
        codes = {row["code"] for row in result["notification"]["outcome"]}
        assert "move_message_queued" in codes, (
            f"the plan-change email was elected and nothing was queued: {codes}"
        )
        account_rows = notification_models.OutboundMessage.objects.filter(
            tenant_id=brazos.id, source_type="account"
        )
        # One LETTER, on two channels: the elected email plus BR-NOT-024's
        # paper copy, which `account` has carried since 2026-08-30. Named
        # rather than counted, so two emails or two letters would still fail.
        assert {item.channel for item in account_rows} == {"email", "pdf_print"}
        assert len({(item.source_id, item.copy_no) for item in account_rows}) == 1
        row = account_rows.get(channel="email")

    # 1 · the wording exists. `plan_change` was declared by nothing.
    assert row.template_code == "email_plan_change"
    assert row.template_code in {seed.code for seed in seed_templates.SEEDABLE}, (
        "the pinned code is not a class this platform seeds, so the letter "
        "renders from wording that does not exist (DEF-2511)."
    )

    # 2 · the settings switch reaches it (CR-048 wave A's join).
    assert row.event_key == "rate_plan_changed"

    # 3 · the source kind is the ACCOUNT-lifecycle one, not the payment-plan
    #     kind.
    #     ⚠ THIS COMMENT USED TO END "— whose print floor was putting this
    #     email on paper", AND THAT REASON NO LONGER HOLDS: `account` gained a
    #     print floor of its own on 2026-08-30, so the letter is printed either
    #     way and the two kinds no longer differ on paper at all. The other two
    #     reasons the kind exists are untouched and are what assertions 2 and 4
    #     check — the letter names its OWN event, so the settings switch reaches
    #     it, and it is keyed on its OWN row, so a second change is a second
    #     letter. Those were always the load-bearing halves.
    assert row.source_type == "account"
    assert row.channel == "email"

    # 4 · it is keyed on the ASSIGNMENT row, so a second change to a different
    #     plan is a second letter rather than a silent dedupe into the first.
    assert str(row.source_id) == str(
        rating_models.UnitPlanAssignment.objects.get(
            unit_id=world["unit_id"], rate_plan_id=world["senior"].id
        ).pk
    )


def test_cr048_b11__a_second_rate_change_is_a_second_letter(brazos, marcus):
    """**DEF-2512, from the direction that proves it — the SECOND thing.**

    A test that queues the same change twice proves the wrong half: it would
    pass on the broken account-keyed version, because the second write is
    SUPPOSED to find the first row. What the account key loses is a DIFFERENT
    message, and the only way to see that is to send one.

    So this moves the account onto one plan, then onto another, and asserts two
    LETTERS. On the pre-2026-08-30 trigger the second letter deduped into the
    first with `created=False`, no error and no gap in any trail, and the
    customer was told about their first rate change and never about their
    second.

    ⚠ **TWO LETTERS ARE FOUR ROWS SINCE 2026-08-30, AND THE CASE COUNTS LETTERS
    NOW BECAUSE THAT IS WHAT IT WAS EVER ABOUT.** It asserted `len(rows) == 2`
    with the message *"two rate changes produced {n} letter(s)"* — row and
    letter were the same thing, so counting either worked. Then the PO widened
    BR-NOT-024's print floor from four source kinds to six and `account` became
    one of them, so each letter is queued on the elected email AND on paper. The
    distinct-source-id assertion below was always the one carrying the meaning;
    it is now the headline, with the row count kept underneath it so a floor
    that silently stopped applying still fails here.
    """
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        customers_services.change_plan(
            marcus,
            world["account_id"],
            {"rate_plan_id": str(world["senior"].id), "effective_on": "2026-09-01", "notify": True},
        )
        customers_services.change_plan(
            marcus,
            world["account_id"],
            {
                "rate_plan_id": str(world["res_std"].id),
                "effective_on": "2026-10-01",
                "notify": True,
            },
        )
        rows = list(
            notification_models.OutboundMessage.objects.filter(
                tenant_id=brazos.id, source_type="account"
            )
        )
    letters = {(str(row.source_id), row.copy_no) for row in rows}
    assert len(letters) == 2, (
        f"two rate changes produced {len(letters)} letter(s). Keyed on the "
        "ACCOUNT they share one idempotency tuple and the second silently "
        "dedupes into the first: "
        f"{[(r.template_code, str(r.source_id)) for r in rows]}"
    )
    assert len(rows) == 4, (
        f"two letters on two channels each is four rows and this queued "
        f"{len(rows)}. Since 2026-08-30 an account letter is queued on the "
        "elected email AND the paper copy BR-NOT-024's floor adds; a count of "
        "two here means the floor stopped applying."
    )
    # Both channels on BOTH letters — four rows would also be two emails for one
    # change and two printed copies of the other.
    for source_id, _copy_no in letters:
        assert {row.channel for row in rows if str(row.source_id) == source_id} == {
            "email",
            "pdf_print",
        }


def test_us_cus_017_tc5__a_double_submit_lands_one_history_row(brazos, marcus):
    """TC-5 (negative): the same plan from the same date, twice, is ONE change
    — the effective-dated append is idempotent on its natural key."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        payload = {
            "rate_plan_id": str(world["senior"].id),
            "effective_on": "2026-09-01",
            "notify": False,
        }
        customers_services.change_plan(marcus, world["account_id"], payload)
        customers_services.change_plan(marcus, world["account_id"], payload)
        rows = rating_models.UnitPlanAssignment.objects.filter(
            unit_id=world["unit_id"], rate_plan_id=world["senior"].id
        )
    assert rows.count() == 1


def test_us_cus_017_tc7__the_wizard_endpoints_are_reachable_and_tenant_scoped(brazos, marcus):
    """TC-7 (isolation) + hard-won law 2: the two S23 routes exist and are
    served. A service nothing can reach is not a feature."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        preview = api_call(
            customers_api.account_plan_change_preview,
            "post",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            data={"rate_plan_id": str(world["senior"].id), "effective_on": "2026-09-01"},
            account_id=str(world["account_id"]),
        )
        assert preview.status_code == 200
        confirmed = api_call(
            customers_api.account_plan_changes,
            "post",
            user=marcus.user,
            role="billing_clerk",
            tenant=brazos,
            data={
                "rate_plan_id": str(world["senior"].id),
                "effective_on": "2026-09-01",
                "notify": False,
            },
            account_id=str(world["account_id"]),
        )
        assert confirmed.status_code == 201


# ══════════════════════════════════════════════════════════════════════════
# The recipient read notifications has been asking for since W3 (law 2)
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_017_tc1__customers_publishes_the_recipient_read_notifications_names(brazos, marcus):
    """`apps/notifications/services.py` names `delivery_recipients_for_account`
    as the customers read it resolves BY NAME, and until now customers
    published nothing of the sort — so every queued message recorded
    `recipient_not_resolvable`, meaning "nobody could look". It can look now."""
    with tenant_ctx(brazos):
        world = _world(marcus, brazos)
        resolved = customers_selectors.delivery_recipients_for_account(
            world["account_id"], channels=("email", "pdf_print", "sms")
        )
    assert resolved["email"]["address"] == "sarah.miller@example.com"
    # ⚠ AMENDED 2026-10-05 (`DEF-NOT-9669`, lane FIX-7). This asserted
    # `recipient_not_resolvable` ("no SMS column exists anywhere"). The read now
    # answers the customer's own choice first: this account never chose texts,
    # so the answer is `no_sms_opt_in`, never an address.
    assert resolved["sms"] == {"unavailable_reason": "no_sms_opt_in"}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-016@f7c1a20 (sha1[:7] of the four sources this suite was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-04-account-actions.md · 04-docs/05-modules/03-customers/06-epics/EP-CUS-05-change-plan.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.6; co-packets US-CUS-012 · US-CUS-015 · US-CUS-017, same four sources)
# generated: 2026-08-11 by story-coder (W4/W8 customers ACTION lane — the S22 modals and the S23 wizard)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — RED-PROVED FIRST, verbatim failures quoted there
# exceptions: US-CUS-013 and US-CUS-014 have NO tests here and no code anywhere: the billing write paths they hand off to (`issue_credit_note`, an adjustment writer, a statement renderer, `GET /invoices/{id}/document`) do not exist, and three of their rules are unruled (OQ-105 reduced form, OQ-103 sub-question, OQ-121). Their controls render disabled WITH those reasons on S21; a test asserting a refusal we authored would be a test of our own stub, not of the story
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
