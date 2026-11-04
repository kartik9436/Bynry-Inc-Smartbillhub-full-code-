# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W5 — payment custom fields, captured at entry only
# Rules:    BR-TEN-046 (as amended 2026-10-02 — `payments` joins the list) ·
#           BR-TEN-048 (unchanged — never allocation) · BR-TEN-052 (required
#           only where typed in) · CLAUDE.md hard rules 1 and 4 · law 14
# ───────────────────────────────────────────────────────
"""W5's guards, each one the PO's sentence turned into an assertion.

PO 2026-10-02, Part 2 row 14: *"Record payment (at entry only) · Payment detail
· Can't be corrected afterwards; never used to apply the payment to bills"*.

The worked example used throughout is the one put to the PO: a cashier records
**Drawer = 2** on a **$120.00** cheque.

* **Entered once** — the INSERT stores the answer; Payment detail serves it.
* **Can't be corrected afterwards** — an UPDATE of the column is refused by
  `payments_payment_immutable()` (PostgreSQL only — law 14; the SQLite tier
  records its blindness rather than passing).
* **Never used to apply the payment** — the allocation of $120.00 is identical
  with and without the answer.
* **One utility only** — another utility sees neither the field nor the answer.
* **Required only where typed in** — a required field blank refuses Record
  payment (S35) with `custom_data.<key>`, and does not touch a door that never
  drew it; a utility with no payment fields records exactly as before.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from apps.payments import api as payments_api
from apps.payments import detail_api, models, services
from apps.tenancy import custom_fields as cf_law
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from tests.isolation_helpers import requires_postgres, rls, rls_probe_role  # noqa: F401 — fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 10, 2, 10, 30, tzinfo=UTC)
CHEQUE = Decimal("120.00")


def _drawer_field(actor, *, required=False, placement=None):
    field = tenancy_services.create_custom_field(
        actor,
        {"label": "Drawer", "entity": "payments", "data_type": "text", "is_required": required},
    )
    tenancy_services.save_custom_field_placement(
        actor, field["id"], placement if placement is not None else {"S35": "input", "S33": "view"}
    )
    return field


def _account_with_bills(actor, tenant):
    """Two open bills, so an allocation has an ORDER to get wrong."""
    account = an_account_of(actor, tenant)
    an_issued_bill(tenant, account, number=f"BL-A-{uuid.uuid4().hex[:6]}", total=Decimal("80.00"), issued_on=date(2026, 8, 1))
    an_issued_bill(tenant, account, number=f"BL-B-{uuid.uuid4().hex[:6]}", total=Decimal("75.00"), issued_on=date(2026, 9, 1))
    return account


def _record(actor, account, **extra):
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=CHEQUE,
        method_code="ach",
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        idempotency_reference=uuid.uuid4(),
        **extra,
    )


def _post(tenant, account, body):
    payload = {
        "amount": "120.00",
        "posted_at": "2026-10-02",
        "cleared_at": "2026-10-02",
        "method": "ach",
        "idempotency_key": str(uuid.uuid4()),
        **body,
    }
    return api_call(
        payments_api.account_payments,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        data=payload,
        account_id=str(account.pk),
    )


def _allocation_shape(recorded, account):
    """What the money DID, with every identity that differs between two runs
    replaced by the bill's position on its account."""
    from apps.billing import models as billing_models

    order = {
        str(pk): i
        for i, pk in enumerate(
            billing_models.Invoice.objects.filter(account=account).order_by("issued_at").values_list("pk", flat=True)
        )
    }
    shape = []
    for row in recorded.allocations:
        row = dict(row)
        invoice = str(row.pop("invoice_id", "")) or None
        shape.append(
            (
                order.get(invoice),
                str(row.get("charge_class", "")),
                str(row.get("amount", "")),
            )
        )
    return recorded.applied, recorded.credit_carried, tuple(shape)


# ── 1 · the slot list and the entity ─────────────────────────────────────────
def test_w5__payments_is_a_record_type_with_exactly_two_rendered_screens():
    assert "payments" in cf_law.ENTITIES
    slots = {(s.key, s.screen, s.modes, s.rendered) for s in cf_law.declared_slots("payments")}
    assert slots == {
        ("S35", "record_payment", ("input",), True),
        ("S33", "payment_detail", ("view",), True),
    }


def test_w5__no_payment_slot_offers_an_edit_screen():
    """*"Can't be corrected afterwards"* — there is no Input slot except the entry."""
    inputs = [s.key for s in cf_law.declared_slots("payments") if "input" in s.modes]
    assert inputs == ["S35"]


# ── 2 · entered once, shown on Payment detail ────────────────────────────────
def test_w5__the_insert_stores_the_answer_and_payment_detail_serves_it(brazos, dana):
    with tenant_ctx(brazos):
        _drawer_field(dana)
        account = _account_with_bills(dana, brazos)
        response = _post(brazos, account, {"custom_data": {"drawer": "2"}})
        assert response.status_code == 201, response.data
        payment = models.Payment.objects.get(pk=response.data["id"])
        assert payment.custom_data == {"drawer": "2"}
        detail = api_call(
            detail_api.payment, "get", user=FakeUser(), role="billing_clerk", tenant=brazos,
            payment_id=str(payment.pk),
        )
    assert detail.status_code == 200
    assert detail.data["custom_data"] == {"drawer": "2"}


def test_w5__a_door_that_draws_no_fields_stores_nothing(brazos, dana):
    with tenant_ctx(brazos):
        _drawer_field(dana)
        account = _account_with_bills(dana, brazos)
        response = _post(brazos, account, {})
        assert response.status_code == 201, response.data
        assert models.Payment.objects.get(pk=response.data["id"]).custom_data == {}


def test_w5__an_unknown_key_is_refused_and_nothing_is_written(brazos, dana):
    with tenant_ctx(brazos):
        _drawer_field(dana)
        account = _account_with_bills(dana, brazos)
        before = models.Payment.objects.count()
        response = _post(brazos, account, {"custom_data": {"till_colour": "red"}})
        after = models.Payment.objects.count()
    assert response.status_code == 422, response.data
    assert before == after


# ── 3 · required only where typed in ─────────────────────────────────────────
def test_w5__a_required_field_left_blank_refuses_record_payment_by_name(brazos, dana):
    with tenant_ctx(brazos):
        _drawer_field(dana, required=True)
        account = _account_with_bills(dana, brazos)
        before = models.Payment.objects.count()
        response = _post(brazos, account, {"custom_data": {"drawer": ""}})
        after = models.Payment.objects.count()
    assert response.status_code == 422, response.data
    fields = [fe["field"] for fe in response.data.get("field_errors", [])]
    assert fields == ["custom_data.drawer"]
    assert before == after, "a refused payment must burn nothing"


def test_w5__a_required_field_does_not_block_a_door_that_never_drew_it(brazos, dana):
    """Take payment on the account, the build dialogs and Add correction share
    this endpoint and draw no custom fields — *"A required field never blocks a
    screen that doesn't show it"*."""
    with tenant_ctx(brazos):
        _drawer_field(dana, required=True)
        account = _account_with_bills(dana, brazos)
        response = _post(brazos, account, {})
    assert response.status_code == 201, response.data


def test_w5__a_utility_with_no_payment_fields_records_exactly_as_before(brazos, dana):
    with tenant_ctx(brazos):
        assert tenancy_selectors.custom_field_registry("payments", screen="S35", mode="input") == []
        account = _account_with_bills(dana, brazos)
        response = _post(brazos, account, {"custom_data": {}})
        assert response.status_code == 201, response.data
        assert models.Payment.objects.get(pk=response.data["id"]).custom_data == {}


# ── 4 · never used to apply the payment (BR-TEN-048) ─────────────────────────
def test_w5__allocation_is_identical_with_and_without_the_answer(brazos, dana):
    with tenant_ctx(brazos):
        _drawer_field(dana)
        plain_account = _account_with_bills(dana, brazos)
        tagged_account = _account_with_bills(dana, brazos)
        plain = _record(dana, plain_account)
        tagged = _record(
            dana, tagged_account, custom_data={"drawer": "2"}, custom_data_screen="S35"
        )
        assert models.Payment.objects.get(pk=tagged.payment_id).custom_data == {"drawer": "2"}
        plain_shape = _allocation_shape(plain, plain_account)
        tagged_shape = _allocation_shape(tagged, tagged_account)
    assert plain_shape == tagged_shape
    # And the money did something, so the comparison is not of two empties.
    assert plain_shape[0] == CHEQUE
    assert len(plain_shape[2]) >= 2


# ── 5 · one utility only ─────────────────────────────────────────────────────
@pytest.mark.isolation
def test_w5__another_utility_sees_neither_the_field_nor_the_answer(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        _drawer_field(dana)
        account = _account_with_bills(dana, brazos)
        recorded = _record(dana, account, custom_data={"drawer": "2"}, custom_data_screen="S35")
    with tenant_ctx(lonestar):
        assert tenancy_selectors.custom_field_registry("payments", screen="S33", mode="view") == []
        detail = api_call(
            detail_api.payment, "get", user=FakeUser(), role="billing_clerk", tenant=lonestar,
            payment_id=str(recorded.payment_id),
        )
    assert detail.status_code == 404


@requires_postgres
@pytest.mark.isolation
def test_w5__rls_hides_the_answer_from_another_utility(brazos, lonestar, dana, rls):
    """Through the DATABASE, as `sbh_rls_probe` (NOSUPERUSER NOBYPASSRLS) — the
    app filter is not in the path."""
    with tenant_ctx(brazos):
        _drawer_field(dana)
        account = _account_with_bills(dana, brazos)
        recorded = _record(dana, account, custom_data={"drawer": "2"}, custom_data_screen="S35")
    sql = "SELECT count(*) FROM payments WHERE custom_data ->> 'drawer' = '2' AND id = %s"
    with rls.under(brazos):
        assert rls.scalar(sql, [str(recorded.payment_id)]) == 1
    with rls.under(lonestar):
        assert rls.scalar(sql, [str(recorded.payment_id)]) == 0


# ── 6 · can't be corrected afterwards (hard rule 4, PostgreSQL) ──────────────
def test_w5__sqlite_cannot_see_the_trigger_and_says_so(brazos, dana):
    if connection.vendor == "postgresql":
        pytest.skip("documents the SQLite tier; the PostgreSQL cases follow")
    with tenant_ctx(brazos):
        _drawer_field(dana)
        recorded = _record(dana, _account_with_bills(dana, brazos), custom_data={"drawer": "2"}, custom_data_screen="S35")
        models.Payment.objects.filter(pk=recorded.payment_id).update(custom_data={"drawer": "9"})
        assert models.Payment.objects.get(pk=recorded.payment_id).custom_data == {"drawer": "9"}, (
            "SQLite has no trigger — this tier proves nothing about hard rule 4 (law 14)"
        )


@requires_postgres
@pytest.mark.parametrize("cleared", [True, False], ids=["cleared", "processing"])
def test_w5__the_trigger_refuses_an_update_of_the_answers(brazos, dana, cleared):
    """Both branches of `payments_payment_immutable()`: a cleared payment (the
    append-only branch) and a processing one (the clearing-transition branch).
    `payments/0014`'s allow list does not name the column, so both refuse."""
    with tenant_ctx(brazos):
        _drawer_field(dana)
        account = _account_with_bills(dana, brazos)
        recorded = services.record_payment(
            dana,
            account_id=account.pk,
            amount=CHEQUE,
            method_code="ach",
            posted_at=POSTED_AT,
            cleared_at=POSTED_AT if cleared else None,
            idempotency_reference=uuid.uuid4(),
            custom_data={"drawer": "2"},
            custom_data_screen="S35",
        )
        with pytest.raises(DatabaseError) as refused, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE payments SET custom_data = '{\"drawer\": \"9\"}'::jsonb WHERE id = %s",
                    [str(recorded.payment_id)],
                )
        assert "hard rule 4" in str(refused.value)
        assert "custom_data" in str(refused.value)
        assert models.Payment.objects.get(pk=recorded.payment_id).custom_data == {"drawer": "2"}


@requires_postgres
def test_w5__the_column_defaults_to_an_empty_object_in_the_database(brazos, dana):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_default, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'payments' AND column_name = 'custom_data'"
        )
        default, nullable = cursor.fetchone()
    assert default.startswith("'{}'::jsonb")
    assert nullable == "NO"


def test_w5__the_correction_door_refuses_the_answers_by_name(brazos, dana):
    """The one door that edits a payment (`POST /payments/{id}/correct-reference`,
    `payments/0014`) takes three named fields; the answers are not one of them
    and are refused rather than silently dropped."""
    from apps.payments import amendments
    from apps.payments.exceptions import PaymentRuleError

    assert "custom_data" not in amendments.AMENDABLE_FIELDS
    with tenant_ctx(brazos):
        _drawer_field(dana)
        recorded = _record(
            dana, _account_with_bills(dana, brazos), custom_data={"drawer": "2"}, custom_data_screen="S35"
        )
        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=recorded.payment_id,
                note="wrong drawer",
                memo="x",
                body={"memo": "x", "note": "wrong drawer", "custom_data": {"drawer": "9"}},
            )
        assert "custom_data" in str(refusal.value)
        assert models.Payment.objects.get(pk=recorded.payment_id).custom_data == {"drawer": "2"}
