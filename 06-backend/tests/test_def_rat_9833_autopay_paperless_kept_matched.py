# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-9833 — PO rulings D2 (b) and 4 (2026-10-06) not built:
#          Autopay and Paperless were refused at move-in and on the account
#          door, the nightly sync ended a clerk's Paperless whose setting was
#          Off, and a setting switched On waited for the night.
# Rules:   PO D2 (b), verbatim: "Offer Autopay and Paperless at move-in as
#          drawn … Clark has to add those discounts. clark can add it later
#          also on account" · PO ruling 4, verbatim: "so when clark make it on
#          or adds it you ahve to set it up so that next billing cycle pick it"
#          (read as (b): kept matched to the setting) · BR-RAT-110 · CR-166 §7
#          item 7 (ended from the next bill) · hard rules 6, 7
# ───────────────────────────────────────────────────────
"""**Autopay and Paperless are added by a clerk and kept matched to the setting.**

The statement on the PENDING review-ledger row, which these tests pin:
*"At Harold's move-in the clerk ticks Paperless ($1.00 off); his Paperless bill
setting switches On, the discount is in place for his next bill, and the nightly
job keeps it. If he later switches back to paper, the discount ends that night.
The same happens when a clerk adds Paperless or Autopay on the account.
Municipal account stays automatic."*

Worked, on one plan carrying SENIOR (apply and approve), MUNI (automatic,
*Government or municipal account*), AUTOPAY (automatic, *Autopay is on*) and
PAPERLESS (automatic, *Paperless billing is on*, $1.00 off).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.customers import api as customers_api
from apps.customers import discounts as customers_discounts
from apps.customers import models as customers_models
from apps.customers import move_in_preferences
from apps.customers import portal_self_service
from apps.customers import services as customers_services
from apps.identity import models as identity_models
from apps.rating import discount_enrolment_job, discount_pricing, discount_services, move_in_fees
from apps.rating import discounts as dm
from apps.rating import seams as rating_seams
from apps.rating import selectors
from core import errors
from tests.test_cr166_discounts_round2 import _discount
from tests.test_def_cus_9779_automatic_discounts_not_claimable import (
    START,
    _move_in,
    _plan_with_three,
)
from tests.test_us_ten_helpers import api_call
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _plan_with_four(actor, tenant):
    unit, plan, outgoing, senior, muni, autopay = _plan_with_three(actor, tenant)
    paperless = _discount(
        actor,
        "PAPERLESS",
        value="1.00",
        start=START,
        mode=dm.ENROLMENT_AUTOMATIC,
        eligibility="paperless_on",
        discount_type=dm.DISCOUNT_FIXED_AMOUNT,
        currency="USD",
    )
    discount_services.attach_discount_to_plan(actor, plan.id, paperless.id)
    return plan, outgoing, senior, muni, autopay, paperless


def _open(discount, account_id):
    return dm.DiscountEnrolment.objects.filter(
        discount=discount, account_id=account_id, ended_on__isnull=True
    )


def _account(account_id):
    return customers_models.Account.objects.get(pk=account_id)


def _user(actor):
    return identity_models.User.objects.get(pk=actor.id)


# ── the move-in (D2 (b): "Offer Autopay and Paperless at move-in as drawn") ──
def test_harolds_move_in_paperless_switches_the_setting_on_and_is_kept_tonight(
    brazos, marcus, dana, audit_rows
):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, _autopay, paperless = _plan_with_four(dana, brazos)
        harold = _move_in(
            marcus, outgoing, paperless=False, discount_claims=[{"discount_id": str(paperless.id)}]
        )
        account = _account(harold["id"])
        enrolment = _open(paperless, harold["id"]).get()
        switched = [
            row["after"]
            for row in audit_rows
            if row["entity_type"] == "account"
            and str(row["entity_id"]) == str(harold["id"])
            and (row["after"] or {}).get("reason") == "discount_added"
        ]
        today = rating_seams.tenant_today()
        # Tonight's sync keeps it — the setting is On.
        discount_enrolment_job.sync_discount(paperless, today=today + timedelta(days=1))
        kept = _open(paperless, harold["id"]).exists()
        lines = (discount_pricing.BillLine(service="electric", kind="usage", amount=Decimal("60.00")),)
        priced = discount_services.price_account_discounts(harold["id"], lines, on_day=today)
    assert account.paperless is True
    assert enrolment.enrolled_on == today
    assert enrolment.verification_status == dm.VERIFICATION_NOT_REQUIRED
    assert switched == [{"paperless": True, "reason": "discount_added"}]
    assert kept is True
    assert priced.total_reduction().quantize(Decimal("0.01")) == Decimal("1.00")


def test_the_claim_list_offers_autopay_and_paperless_and_never_municipal(brazos, dana):
    with tenant_ctx(brazos):
        plan, _o, _senior, _muni, _autopay, _paperless = _plan_with_four(dana, brazos)
        sections = move_in_fees.narrowed_sections(
            plan.id, customer_class="residential", on_date=rating_seams.tenant_today()
        )
    pairs = {row["ref"]["code"]: row["pairs_with"] for row in sections["claimable_discounts"]}
    assert pairs == {"SENIOR": None, "AUTOPAY": "autopay", "PAPERLESS": "paperless"}


def test_a_move_in_claiming_municipal_is_still_refused(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, muni, _autopay, _paperless = _plan_with_four(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(marcus, outgoing, discount_claims=[{"discount_id": str(muni.id)}])
    assert raised.value.message_key == move_in_preferences.DISCOUNT_AUTOMATIC


def test_paperless_set_on_at_move_in_without_a_claim_is_enrolled_at_once(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, _autopay, paperless = _plan_with_four(dana, brazos)
        result = _move_in(marcus, outgoing, paperless=True)
        rows = list(_open(paperless, result["id"]))
        today = rating_seams.tenant_today()
    assert len(rows) == 1 and rows[0].enrolled_on == today


# ── the account (D2 (b): "clark can add it later also on account") ──────────
def test_a_clerk_adds_autopay_on_the_account_and_autopay_switches_on(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, autopay, _paperless = _plan_with_four(dana, brazos)
        account = _move_in(marcus, outgoing)
        assert _account(account["id"]).autopay is False
        row = customers_discounts.claim_assistance(marcus, account["id"], str(autopay.id))
        flags = _account(account["id"])
        discount_enrolment_job.sync_discount(autopay)
        kept = _open(autopay, account["id"]).exists()
    assert row["claimed"] is True and row["status"] == "not_required"
    assert flags.autopay is True
    assert kept is True


def test_the_enroll_endpoint_accepts_paperless_and_switches_the_setting(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, _autopay, paperless = _plan_with_four(dana, brazos)
        account = _move_in(marcus, outgoing)
    response = api_call(
        customers_api.account_claim_assistance,
        "post",
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        data={"programme_id": str(paperless.id)},
        account_id=account["id"],
    )
    assert response.status_code in (200, 201), response.data
    with tenant_ctx(brazos):
        assert _account(account["id"]).paperless is True
        assert _open(paperless, account["id"]).exists()


def test_autopay_on_a_cash_only_account_is_refused_and_nothing_changes(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, autopay, _paperless = _plan_with_four(dana, brazos)
        account = _move_in(marcus, outgoing)
        customers_models.Account.objects.filter(pk=account["id"]).update(cash_only_no_autopay=True)
        with pytest.raises(errors.ValidationError) as raised:
            customers_discounts.claim_assistance(marcus, account["id"], str(autopay.id))
        assert _account(account["id"]).autopay is False
        assert not _open(autopay, account["id"]).exists()
    assert raised.value.message_key == customers_discounts.DISCOUNT_CASH_ONLY


def test_a_plan_that_does_not_carry_paperless_refuses_and_rolls_the_setting_back(
    brazos, marcus, dana
):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, _autopay, _paperless = _plan_with_four(dana, brazos)
        loose = _discount(
            dana, "EBILL", value="2", start=START, mode=dm.ENROLMENT_AUTOMATIC,
            eligibility="paperless_on",
        )
        account = _move_in(marcus, outgoing)
        with pytest.raises(errors.BizError):
            customers_discounts.claim_assistance(marcus, account["id"], str(loose.id))
        assert _account(account["id"]).paperless is False


def test_municipal_by_hand_is_still_refused_and_the_page_hides_its_enroll(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, senior, muni, autopay, paperless = _plan_with_four(dana, brazos)
        account = _move_in(marcus, outgoing)
        with pytest.raises(errors.ValidationError) as raised:
            customers_discounts.claim_assistance(dana, account["id"], str(muni.id))
        rows = {one.code: selectors.discount_detail(one.id) for one in (senior, muni, autopay, paperless)}
    assert raised.value.message_key == move_in_preferences.DISCOUNT_AUTOMATIC
    assert {code: row["hand_enrolment_refused"] for code, row in rows.items()} == {
        "SENIOR": False,
        "MUNI": True,
        "AUTOPAY": False,
        "PAPERLESS": False,
    }


# ── the setting (ruling 4: "when clark make it on … next billing cycle pick it") ──
def test_paperless_switched_on_on_the_account_is_enrolled_now_and_off_ends_that_night(
    brazos, marcus, dana
):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, _autopay, paperless = _plan_with_four(dana, brazos)
        account = _move_in(marcus, outgoing)
        today = rating_seams.tenant_today()
        customers_services.update_account(marcus, account["id"], {"paperless": True})
        on_now = list(_open(paperless, account["id"]))
        customers_services.update_account(marcus, account["id"], {"paperless": False})
        # Switching back to paper ends nothing on the write …
        still_open = _open(paperless, account["id"]).exists()
        # … and that night's sync ends it, from the next bill.
        tonight = today + timedelta(days=1)
        discount_enrolment_job.sync_discount(paperless, today=tonight)
        ended = dm.DiscountEnrolment.objects.get(discount=paperless, account_id=account["id"])
    assert len(on_now) == 1 and on_now[0].enrolled_on == today
    assert still_open is True
    assert ended.ended_on == today
    assert ended.end_reason == discount_enrolment_job.END_REASON


def test_email_bills_switched_on_in_the_portal_enrols_paperless_now(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, _autopay, paperless = _plan_with_four(dana, brazos)
        account = _move_in(marcus, outgoing)
        portal_self_service.update_delivery_preferences(
            SimpleNamespace(customer_id=None, session_id=None),
            tenant_id=brazos.id,
            account_ids=[account["id"]],
            payload={"email_on": True},
        )
        rows = list(_open(paperless, account["id"]))
    assert len(rows) == 1 and rows[0].enrolled_by_id is None


def test_the_sync_keeps_a_clerks_paperless_on_an_account_pending_activation(brazos, marcus, dana):
    with tenant_ctx(brazos):
        _plan, outgoing, _senior, _muni, _autopay, paperless = _plan_with_four(dana, brazos)
        account = _move_in(marcus, outgoing)
        customers_discounts.claim_assistance(marcus, account["id"], str(paperless.id))
        pending = customers_models.AccountStatus.objects.filter(
            tenant_id=brazos.id, behavior_class="non_billable"
        ).first()
        assert pending is not None
        customers_models.Account.objects.filter(pk=account["id"]).update(status=pending)
        discount_enrolment_job.sync_discount(paperless)
        kept = _open(paperless, account["id"]).exists()
    assert kept is True


# ═══════════════════════════════════════════════════════════════════════════
# THE STATEMENT THE PO SIGNED ON 2026-10-06 ("S9–S13 approve", S10)
# ═══════════════════════════════════════════════════════════════════════════
def test_the_statement_the_po_signed_on_2026_10_06(brazos, marcus, dana):
    """**SIGNED 2026-10-06 (S10)** — review-ledger AMENDMENT row *"SIGN-OFF
    RECORDED (S10 of S9–S13)"* for `DEF-RAT-9833`; decision log *"S9–S13
    SIGNED"*.

    Shown to the PO, verbatim: *"At Harold's move-in the clerk ticks Paperless
    ($1.00 off); his Paperless bill setting switches On, the discount is in
    place for his next bill, and the nightly job keeps it. If he later switches
    back to paper, the discount ends that night. The same happens when a clerk
    adds Paperless or Autopay on the account. Municipal account stays
    automatic."* PO, verbatim: *"S9–S13 approve"*.

    Each sentence on the figure shown, so a drift goes RED. What the statement
    did NOT carry (the cash-only refusal, no autopay source required, an
    account pending activation, a plan move or closure ending it, the wizard
    and import doors) is listed in the ledger row and stays on the agenda.
    """
    lines = (discount_pricing.BillLine(service="electric", kind="usage", amount=Decimal("60.00")),)

    def off(account_id, on_day):
        outcome = discount_services.price_account_discounts(account_id, lines, on_day=on_day)
        return outcome.total_reduction().quantize(Decimal("0.01"))

    with tenant_ctx(brazos):
        _plan, outgoing, _senior, muni, autopay, paperless = _plan_with_four(dana, brazos)
        today = rating_seams.tenant_today()
        tonight = today + timedelta(days=1)
        later = today + timedelta(days=2)

        # ── "Municipal account stays automatic" — never claimed at move-in ──
        with pytest.raises(errors.ValidationError) as at_move_in:
            _move_in(marcus, outgoing, discount_claims=[{"discount_id": str(muni.id)}])

        # ── "At Harold's move-in the clerk ticks Paperless ($1.00 off)" ──
        harold = _move_in(
            marcus, outgoing, paperless=False, discount_claims=[{"discount_id": str(paperless.id)}]
        )
        account_id = harold["id"]
        # ── "his Paperless bill setting switches On" ──
        assert _account(account_id).paperless is True
        # ── "the discount is in place for his next bill" ──
        assert _open(paperless, account_id).get().enrolled_on == today
        assert off(account_id, today) == Decimal("1.00")
        # ── "and the nightly job keeps it" ──
        discount_enrolment_job.sync_discount(paperless, today=tonight)
        assert _open(paperless, account_id).exists()
        assert off(account_id, tonight) == Decimal("1.00")

        # ── "If he later switches back to paper, the discount ends that night" ──
        customers_services.update_account(marcus, account_id, {"paperless": False})
        assert _open(paperless, account_id).exists(), "nothing ends on the write itself"
        discount_enrolment_job.sync_discount(paperless, today=later)
        assert not _open(paperless, account_id).exists()
        ended = dm.DiscountEnrolment.objects.get(discount=paperless, account_id=account_id)
        assert ended.ended_on == tonight
        assert ended.end_reason == discount_enrolment_job.END_REASON
        assert off(account_id, later) == Decimal("0.00")

        # ── "The same happens when a clerk adds … Autopay on the account" ──
        assert _account(account_id).autopay is False
        row = customers_discounts.claim_assistance(marcus, account_id, str(autopay.id))
        assert row["claimed"] is True
        assert _account(account_id).autopay is True
        assert _open(autopay, account_id).get().enrolled_on == today
        discount_enrolment_job.sync_discount(autopay, today=tonight)
        assert _open(autopay, account_id).exists()
        customers_services.update_account(marcus, account_id, {"autopay": False})
        discount_enrolment_job.sync_discount(autopay, today=later)
        assert not _open(autopay, account_id).exists()

        # ── "… when a clerk adds Paperless … on the account" — the tick on the
        # account's own edit (PO 2026-10-06: "account details view - we already
        # have edit options and ticks") ──
        customers_services.update_account(marcus, account_id, {"paperless": True})
        assert _open(paperless, account_id).exists(), "a tick On enrols for the next bill"
        discount_enrolment_job.sync_discount(paperless, today=later)
        assert _open(paperless, account_id).exists()
        assert off(account_id, later) == Decimal("1.00")
        customers_services.update_account(marcus, account_id, {"paperless": False})
        discount_enrolment_job.sync_discount(paperless, today=later + timedelta(days=1))
        assert not _open(paperless, account_id).exists()

        # ── "Municipal account stays automatic" — never by hand, either door ──
        with pytest.raises(errors.ValidationError) as on_account:
            customers_discounts.claim_assistance(dana, account_id, str(muni.id))
        assert selectors.discount_detail(muni.id)["hand_enrolment_refused"] is True
        assert selectors.discount_detail(paperless.id)["hand_enrolment_refused"] is False
        assert selectors.discount_detail(autopay.id)["hand_enrolment_refused"] is False
    assert at_move_in.value.message_key == move_in_preferences.DISCOUNT_AUTOMATIC
    assert on_account.value.message_key == move_in_preferences.DISCOUNT_AUTOMATIC
