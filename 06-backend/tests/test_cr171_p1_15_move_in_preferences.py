# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 P1.15 — Autopay from, discounts to claim, the tax
#          exemption with its certificate (images 41, 44), lane MVI-MONEY.
# Rules:   BR-CUS-059 (autopay capture-only) · BR-RAT-069/110 (a claim is an
#          enrolment, only for a discount the plan carries) · BR-RAT-105 (the
#          certificate row is rating's) · BR-CUS-036 (the file is an account
#          document) · hard-won law 14 (proved on PostgreSQL in
#          tests/test_cr171_p1_29_money_pg.py)
# ───────────────────────────────────────────────────────
"""**The three billing facts a move-in had no door for.**

⚖️ **A BILLING CLERK RECORDS THE CLAIM AND THE CERTIFICATE THEMSELVES** — PO
ruling 2026-10-05 (decision log *"FOUR PO RULINGS IN ONE REPLY"* (2), option
(b)), verbatim: *"Let billing clerks record it themselves. - we have set the
limits so clark can do it - its a day to day work"*. Until then rating's two
writers were `@require_role(SYSTEM_ADMIN)` and a clerk's claim was HELD for an
admin (lane MVI-MONEY, 2.529.0). Both are asserted with Marcus (a Billing
Clerk); the System Admin path with Dana.

**THE PO's FIGURE:** Marcus records the church's certificate against a 2.00%
city tax; on a $100.00 bill it pays **$0.00** tax, and an account with no
certificate pays **$2.00**.
"""

import base64
import uuid

import pytest

from apps.customers import discounts as customers_discounts
from apps.customers import move_in_preferences
from apps.customers import services as customers_services
from apps.customers.account_document_models import AccountDocument
from apps.payments import models as payment_models
from apps.rating import discount_services
from apps.rating import models as rating_models
from core import errors
from tests.test_cr013_p4_tax_model import a_tax
from tests.test_cr094_wh_deposit import _outgoing, _payload, _unit
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

SENIOR = str(uuid.uuid4())
PDF = base64.b64encode(b"%PDF-1.4 exemption certificate").decode()


def _vacated(actor, tenant):
    unit, plan = _unit(actor, tenant)
    outgoing = _outgoing(actor, tenant, unit)
    customers_services.move_out(actor, outgoing["id"], {"moved_out_on": "2026-08-14"})
    return unit, plan, outgoing


def _move_in(actor, outgoing, **extra):
    payload = _payload(deposit={"decision": "required", "take_now": False})
    payload.update(extra)
    return customers_services.move_in(actor, outgoing["id"], payload)


def _instrument(customer_id, tenant, **fields):
    row = dict(
        tenant=tenant,
        customer_id=customer_id,
        gateway_token=str(uuid.uuid4()),
        brand="Visa",
        last_four="4242",
        kind="card",
        expires_month=12,
        expires_year=2030,
    )
    row.update(fields)
    return payment_models.StoredPaymentInstrument.objects.create(**row)


# ── autopay from ───────────────────────────────────────────────────────────
def test_p1_15__autopay_from_the_customers_own_card_is_kept(brazos, dana):
    with tenant_ctx(brazos):
        _u, _p, outgoing = _vacated(dana, brazos)
        first = _move_in(dana, outgoing)  # opens the customer
        customer_id = customers_services.models.CustomerAccount.objects.get(
            account_id=first["id"]
        ).customer_id
        card = _instrument(customer_id, brazos)
        customers_services.move_out(dana, first["id"], {"moved_out_on": "2026-08-20"})
        second = _move_in(
            dana,
            first,
            opened_at="2026-08-21",
            customer={"customer_id": str(customer_id)},
            autopay=True,
            autopay_instrument_id=str(card.id),
        )
        account = customers_services.models.Account.objects.get(pk=second["id"])
    assert str(account.autopay_instrument_id) == str(card.id)
    assert second["billing_extras"]["autopay"]["last_four"] == "4242"


def test_p1_15__a_card_that_is_not_the_customers_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        _u, _p, outgoing = _vacated(dana, brazos)
        stranger = (
            customers_services.models.Customer.objects.exclude(
                id__in=customers_services.models.CustomerAccount.objects.values("customer_id")
            ).first()
            or customers_services.models.Customer.objects.first()
        )
        card = _instrument(stranger.id, brazos)
        before = customers_services.models.Account.objects.count()
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(dana, outgoing, autopay=True, autopay_instrument_id=str(card.id))
        assert customers_services.models.Account.objects.count() == before
    assert raised.value.message_key == move_in_preferences.INSTRUMENT_REFUSED


def test_p1_15__a_source_with_autopay_off_is_refused_before_anything_is_written():
    with pytest.raises(errors.ValidationError) as raised:
        move_in_preferences.clean({"autopay": False, "autopay_instrument_id": str(uuid.uuid4())})
    assert raised.value.message_key == move_in_preferences.AUTOPAY_OFF


# ── discounts to claim ─────────────────────────────────────────────────────
@pytest.fixture()
def carried(monkeypatch):
    """The plan carries SENIOR on the day (rating's own gate is tested in
    rating's files; this asserts the move-in ASKS it)."""
    monkeypatch.setattr(
        discount_services, "discount_ids_carried", lambda account_id, on_day: {SENIOR}
    )


def test_p1_15__a_clerks_claim_is_enrolled_by_the_clerk_with_no_admin(
    brazos, marcus, dana, monkeypatch
):
    """The PO's (b): the clerk's own claim reaches rating's ONE grant table,
    enrolled by the clerk, as *pending* because the programme asks for proof
    (BR-RAT-076) — and nothing is parked for a System Admin."""
    from apps.rating import discounts as discount_models
    from tests.test_cr166_discounts_round2 import _discount

    with tenant_ctx(brazos):
        senior = _discount(dana)
        monkeypatch.setattr(
            discount_services, "discount_ids_carried", lambda account_id, on_day: {senior.id}
        )
        _u, _p, outgoing = _vacated(marcus, brazos)
        result = _move_in(
            marcus,
            outgoing,
            discount_claims=[{"discount_id": str(senior.id), "note": "Senior — ID seen"}],
        )
        account = customers_services.models.Account.objects.get(pk=result["id"])
        enrolments = discount_models.DiscountEnrolment.objects.filter(account_id=account.id)
        assert [(str(row.discount_id), str(row.enrolled_by_id)) for row in enrolments] == [
            (str(senior.id), str(marcus.id))
        ]
    assert result["billing_extras"]["discounts"] == [
        {"discount_id": str(senior.id), "status": "pending"}
    ]
    assert account.eligibility_claimed is False
    assert not hasattr(move_in_preferences, "HELD_FOR_SYSTEM_ADMIN")


def test_p1_15__an_admins_claim_is_enrolled_through_rating(brazos, dana, carried, monkeypatch):
    calls = []

    def enrol(actor, account_id, programme_id, household_size=None):
        calls.append(programme_id)
        return {"claimed": True, "status": "pending"}

    monkeypatch.setattr(customers_discounts, "claim_assistance", enrol)
    with tenant_ctx(brazos):
        _u, _p, outgoing = _vacated(dana, brazos)
        result = _move_in(dana, outgoing, discount_claims=[{"discount_id": SENIOR}])
    assert calls == [SENIOR]
    assert result["billing_extras"]["discounts"] == [{"discount_id": SENIOR, "status": "pending"}]


def test_p1_15__a_discount_the_plan_does_not_carry_refuses_the_move_in(brazos, dana, carried):
    with tenant_ctx(brazos):
        _u, _p, outgoing = _vacated(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(dana, outgoing, discount_claims=[{"discount_id": str(uuid.uuid4())}])
    assert raised.value.message_key == move_in_preferences.DISCOUNT_NOT_OFFERED


def test_p1_15__the_same_discount_twice_is_refused():
    with pytest.raises(errors.ValidationError) as raised:
        move_in_preferences.clean(
            {"discount_claims": [{"discount_id": SENIOR}, {"discount_id": SENIOR}]}
        )
    assert raised.value.message_key == move_in_preferences.DISCOUNT_TWICE


# ── the tax exemption ──────────────────────────────────────────────────────
def _category(tenant):
    tax, _jurisdiction = a_tax(tenant, "City", name="City utility tax", kind="percent")
    return rating_models.TaxExemptionCategory.objects.create(
        tenant=tenant, tax=tax, code="CHURCH", name="Religious organisation"
    )


def _exemption(category, **extra):
    block = {
        "category_id": str(category.id),
        "certificate_ref": "IA-EX-2231",
        "issued_on": "2026-01-15",
        "expires_on": "2027-01-15",
        "certificate": {
            "name": "exemption.pdf",
            "content_type": "application/pdf",
            "content_base64": PDF,
        },
    }
    block.update(extra)
    return block


def test_p1_15__an_admin_records_the_certificate_row_and_the_file_not_the_blanket_columns(brazos, dana):
    with tenant_ctx(brazos):
        _u, _p, outgoing = _vacated(dana, brazos)
        category = _category(brazos)
        result = _move_in(dana, outgoing, tax_exemption=_exemption(category))
        account = customers_services.models.Account.objects.get(pk=result["id"])
        certificates = rating_models.TaxExemptionCertificate.objects.filter(account_id=account.id)
        documents = AccountDocument.objects.filter(account_id=account.id, doc_type="kyc")
        assert [(row.certificate_ref, str(row.issued_on)) for row in certificates] == [
            ("IA-EX-2231", "2026-01-15")
        ]
        assert documents.count() == 1
    # DEF-CUS-9724 (PO 2026-10-05): the certificate is per tax; the account's
    # BLANKET columns are no longer set by it (they read True / the ref / the
    # expiry until 2.546). Priced in money in
    # tests/test_def_cus_9724_exemption_removes_only_its_own_tax.py.
    assert (account.tax_exempt, account.tax_exempt_ref, account.tax_exempt_expires) == (
        False,
        None,
        None,
    )
    assert result["billing_extras"]["tax_exemption"]["status"] == "recorded"


def test_p1_15__marcus_records_the_churchs_certificate_and_it_pays_no_city_tax(brazos, marcus):
    """THE PO's FIGURE. A 2.00% city tax on a $100.00 bill: the church Marcus
    (a Billing Clerk) recorded the certificate for pays **$0.00**; an account
    with no certificate pays **$2.00**. The certificate row is rating's own —
    the row a bill run reads (BR-RAT-105) — and the file is filed beside it."""
    from decimal import Decimal

    from apps.rating import selectors as rating_selectors
    from tests.test_cr013_p4_tax_model import INSIDE_CITY, attach, bill, today_of

    today = today_of(brazos)
    with tenant_ctx(brazos):
        _u, plan, outgoing = _vacated(marcus, brazos)
        tax, jurisdiction = a_tax(
            brazos, "City", name="City utility tax", kind="percent", rate=Decimal("0.020000")
        )
        attach(brazos, plan, jurisdiction)
        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=brazos, tax=tax, code="CHURCH", name="Religious organisation"
        )
        result = _move_in(marcus, outgoing, tax_exemption=_exemption(category))
        account_id = result["id"]
        certificates = rating_models.TaxExemptionCertificate.objects.filter(account_id=account_id)
        assert [row.certificate_ref for row in certificates] == ["IA-EX-2231"]
        assert AccountDocument.objects.filter(account_id=account_id).count() == 1

        def city_tax(account):
            rules = rating_selectors.plan_tax_rules(
                plan.id,
                today,
                customer_class="commercial",
                premises=INSIDE_CITY,
                services=("electric",),
                account_id=account,
            )
            return bill(rules).tax_total

        church = city_tax(account_id)
        ordinary = city_tax(str(uuid.uuid4()))
    assert result["billing_extras"]["tax_exemption"]["status"] == "recorded"
    assert church == Decimal("0.00")
    assert ordinary == Decimal("2.00")


def test_p1_15__the_plans_and_rates_certificate_door_stays_a_system_admins(brazos, marcus):
    """A4: Plans & Rates is View for a Billing Clerk. The ruling lets the clerk
    record a certificate from the ACCOUNT side (the move-in); the Plans & Rates
    POST that reaches the same writer still refuses the clerk."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.rating import api as rating_api

    with tenant_ctx(brazos):
        category = _category(brazos)
        request = APIRequestFactory().post(
            "/api/x/exemption-categories/c/certificates",
            {"account_id": str(uuid.uuid4()), "certificate_ref": "X-1"},
            format="json",
        )
        force_authenticate(request, user=marcus.user)
        request.tenant_role = marcus.role
        request.tenant_id = brazos.id
        response = rating_api.tax_exemption_certificates(request, str(category.id))
        assert response.status_code == 403
        assert not rating_models.TaxExemptionCertificate.objects.filter(category=category).exists()


def test_p1_15__an_unreadable_certificate_is_refused_before_anything_is_written():
    with pytest.raises(errors.ValidationError) as raised:
        move_in_preferences.clean(
            {"tax_exemption": {"certificate": {"name": "x.pdf", "content_base64": "@@not base64"}}}
        )
    assert raised.value.message_key == move_in_preferences.CERTIFICATE_UNREADABLE
