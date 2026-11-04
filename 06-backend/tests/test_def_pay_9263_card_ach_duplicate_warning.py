"""DEF-PAY-9263 — "Looks like a duplicate" on a card or ACH payment (BR-PAY-1199).

PO ruling 2026-10-03, verbatim: *"Same card or ACH payment entered twice - B
Warn "Looks like a duplicate", and let the clerk confirm"*.

THE CASE IT WAS RULED ON: account AC-2026-00060 holds two $30.00 card payments,
same day, both reference `AUTH-S8-0030` (PY-261002-0093 and -0094) — a request
page walked twice, both saved with no word to the clerk. Below, the same
$30.00 / `AUTH-S8-0030` pair is recorded through the real door: the second is
answered with the first one named and is NOT saved; *Record anyway* saves it and
the audit row says the warning was overridden and which payment it resembled.

RED FIRST (hard-won law 7): run against the tree before `duplicates.py` and the
two flags existed, `test_the_second_matching_card_payment_is_warned_not_saved`
and the API case failed — `record_payment()` took no `warn_on_possible_duplicate`
argument, and the door answered 201 twice for the same `AUTH-S8-0030`.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from apps.payments import duplicates, models, reversal, services
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)
THIRTY = Decimal("30.00")
AUTH = "AUTH-S8-0030"


def _card(actor, account, *, warn=True, confirmed=False, **overrides):
    fields = {
        "account_id": account.pk,
        "amount": THIRTY,
        "posted_at": POSTED_AT,
        "cleared_at": POSTED_AT,
        "method_code": "card",
        "confirmation": AUTH,
        "idempotency_reference": uuid.uuid4(),
    }
    fields.update(overrides)
    return services.record_payment(
        actor, warn_on_possible_duplicate=warn, duplicate_confirmed=confirmed, **fields
    )


def _count(account):
    return models.Payment.objects.filter(account_id=account.pk).count()


def _record_via_door(dana, brazos, account, **body):
    from apps.payments import api

    dana.is_authenticated = True
    return api_call(
        api.account_payments,
        "post",
        path=f"/api/accounts/{account.pk}/payments",
        user=dana,
        role="system_admin",
        tenant=brazos,
        data={"idempotency_key": str(uuid.uuid4()), **body},
        account_id=str(account.pk),
    )


# ══ THE RULED CASE ═════════════════════════════════════════════════════════


def test_the_second_matching_card_payment_is_warned_not_saved(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        first = _card(dana, account)
        before = _count(account)
        with pytest.raises(duplicates.PossibleDuplicatePayment) as caught:
            _card(dana, account)
        earlier = caught.value.earlier
        assert earlier["payment_no"] == first.payment_no
        assert earlier["posted_on"] == "2026-10-02"
        assert Decimal(earlier["amount"]) == THIRTY
        assert earlier["confirmation"] == AUTH
        assert caught.value.br_ref == "BR-PAY-1199"
        assert _count(account) == before, "a warned payment writes nothing"


def test_record_anyway_saves_it_and_the_audit_row_names_the_earlier_payment(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        first = _card(dana, account)
        second = _card(dana, account, confirmed=True)
        assert second.created is True
        assert second.payment_no != first.payment_no
        row = models.Payment.objects.get(pk=second.payment_id)
        assert row.amount == THIRTY and row.confirmation == AUTH
        recorded = [
            r
            for r in audit_rows
            if r["action"] == services.AUDIT_RECORDED
            and r["after"]["payment_no"] == second.payment_no
        ]
        assert len(recorded) == 1
        after = recorded[0]["after"]
        assert after["duplicate_warning_overridden"] is True
        assert after["possible_duplicate_of"]["payment_no"] == first.payment_no
        assert after["possible_duplicate_of"]["payment_id"] == str(first.payment_id)
        # The FIRST payment's own audit row carries no override.
        first_row = [
            r
            for r in audit_rows
            if r["action"] == services.AUDIT_RECORDED
            and r["after"]["payment_no"] == first.payment_no
        ]
        assert "duplicate_warning_overridden" not in first_row[0]["after"]


def test_ach_is_warned_and_the_reference_is_compared_case_blind(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _card(dana, account, method_code="ach", confirmation="TRACE-771")
        with pytest.raises(duplicates.PossibleDuplicatePayment):
            _card(dana, account, method_code="ach", confirmation="  trace-771 ")


# ══ WHAT IS NOT A DUPLICATE ════════════════════════════════════════════════


# ⛔ SUPERSEDED IN SCOPE 2026-10-30 (Q1 = A): `other-reference`, `no-reference`
# and `cash-not-warned` were "not a duplicate" under the card/ACH ruling and are
# now WARNED — every tender, matched on account + amount + day alone. They moved
# to `test_any_tender_and_any_reference_is_warned_since_q1` below rather than
# being deleted, so the supersession is visible in the suite.
# ⛔ SUPERSEDED IN SCOPE 2026-10-31 (P8 = A, `DEF-PAY-10782`): `other-amount`
# kept the same `AUTH-S8-0030` and changed only the amount. The PO's P8 words
# are *"same card/ACH reference repeats on the same account and day"* — the
# amount is not one of them — so it is WARNED now and moved to
# `test_the_same_authorisation_for_another_amount_is_warned_since_p8` below.
@pytest.mark.parametrize(
    "change",
    [
        {"posted_at": POSTED_AT + timedelta(days=1), "cleared_at": POSTED_AT + timedelta(days=1)},
    ],
    ids=["other-day"],
)
def test_a_payment_that_differs_in_one_fact_is_saved_without_a_warning(brazos, dana, change):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _card(dana, account)
        before = _count(account)
        result = _card(dana, account, **change)
        assert result.created is True
        assert _count(account) == before + 1


@pytest.mark.parametrize(
    "change",
    [
        {"confirmation": "AUTH-S8-0031"},
        {"confirmation": None},
        {"method_code": "cash", "confirmation": None},
    ],
    ids=["other-reference", "no-reference", "cash"],
)
def test_any_tender_and_any_reference_is_warned_since_q1(brazos, dana, change):
    """Q1 = A (PO 2026-10-30) — account + amount + day, whatever the tender."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _card(dana, account)
        before = _count(account)
        with pytest.raises(duplicates.PossibleDuplicatePayment):
            _card(dana, account, **change)
        assert _count(account) == before


def test_the_same_authorisation_for_another_amount_is_warned_since_p8(brazos, dana):
    """P8 = A (PO 2026-10-31) — one authorisation on one account and day is one
    payment, whatever amount was typed the second time."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _card(dana, account)
        before = _count(account)
        with pytest.raises(duplicates.PossibleDuplicatePayment):
            _card(dana, account, amount=Decimal("30.01"))
        assert _count(account) == before


def test_another_accounts_payment_is_not_a_duplicate(brazos, dana):
    with tenant_ctx(brazos):
        _card(dana, an_account(dana, brazos))
        other = an_account(dana, brazos, account_no="A-10433")
        assert _card(dana, other).created is True


def test_a_reversed_payment_is_not_a_duplicate(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        first = _card(dana, account)
        reversal.reverse_payment(
            dana,
            payment_id=first.payment_id,
            returned_on=POSTED_AT + timedelta(hours=1),
            idempotency_reference=uuid.uuid4(),
        )
        assert _card(dana, account).created is True


def test_doors_that_do_not_ask_are_unchanged(brazos, dana):
    """Portal, webhooks, imports and batch callers pass no flag: saved, silently."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        _card(dana, account, warn=False)
        assert _card(dana, account, warn=False).created is True


def test_one_form_pressed_twice_is_a_replay_not_a_duplicate(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        key = uuid.uuid4()
        first = _card(dana, account, idempotency_reference=key)
        again = _card(dana, account, idempotency_reference=key)
        assert again.created is False and again.payment_id == first.payment_id


# ══ CHEQUES ARE UNCHANGED (BR-PAY-880) ═════════════════════════════════════


def test_a_repeated_cheque_is_still_refused_by_the_cheque_rule(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        cheque = {
            "method_code": "check",
            "confirmation": "8842",
            "cheque_date": POSTED_AT.date(),
            "drawer_bank": "First National",
        }
        _card(dana, account, **cheque)
        with pytest.raises(PaymentRuleError) as caught:
            _card(dana, account, confirmed=True, **cheque)
        assert not isinstance(caught.value, duplicates.PossibleDuplicatePayment)
        assert caught.value.br_ref == "BR-PAY-880"


# ══ THROUGH THE DOOR — Take payment / Record payment ═══════════════════════


def test_the_door_answers_the_warning_then_records_on_confirm(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        body = {
            "amount": "30.00",
            "posted_at": "2026-10-02",
            "cleared_at": "2026-10-02",
            "method": "card",
            "confirmation": AUTH,
        }
        first = _record_via_door(dana, brazos, account, **body)
        assert first.status_code == 201, first.data
        warned = _record_via_door(dana, brazos, account, **body)
        assert warned.status_code == 409, warned.data
        assert warned.data["code"] == "BIZ-IDEMPOTENT"
        assert warned.data["message_key"] == "payments.record.possible_duplicate"
        assert warned.data["br_ref"] == "BR-PAY-1199"
        assert warned.data["params"]["payment_no"] == first.data["payment_no"]
        assert warned.data["params"]["possible_duplicate"] is True
        assert _count(account) == 1
        # Only a literal `true` confirms.
        assert (
            _record_via_door(dana, brazos, account, confirm_duplicate="yes", **body).status_code
            == 409
        )
        saved = _record_via_door(dana, brazos, account, confirm_duplicate=True, **body)
        assert saved.status_code == 201, saved.data
        assert _count(account) == 2


# ══ NEW CONNECTION STEP 4 ══════════════════════════════════════════════════


def test_new_connection_step_4_reads_the_confirm_flag():
    from apps.metering import connections

    data = {"payment_method": "card", "payment_amount": "30.00", "payment_reference": AUTH}
    taken = connections._payment_taken_at_the_counter(data, on_date=POSTED_AT.date())
    assert taken["duplicate_confirmed"] is False
    data["payment_duplicate_confirmed"] = True
    taken = connections._payment_taken_at_the_counter(data, on_date=POSTED_AT.date())
    assert taken["duplicate_confirmed"] is True


def test_new_connection_step_4_asks_and_answers_the_warning_on_its_step(monkeypatch):
    from apps.metering import connections, seams

    seen = {}

    def door(actor, **kwargs):
        seen.update(kwargs)
        raise duplicates.PossibleDuplicatePayment(
            {
                "payment_id": "x",
                "payment_no": "PY-261002-0093",
                "posted_on": "2026-10-02",
                "amount": "30.0000",
                "currency": "USD",
                "confirmation": AUTH,
                "method": "card",
            }
        )

    monkeypatch.setattr(seams, "payment_door", lambda: door)
    # The seams below need a tenant context; this test is about the door's
    # ARGUMENTS and the step-4 answer, so they are stood in for.
    monkeypatch.setattr(
        seams,
        "payment_against_one_bill",
        lambda invoice_no: {"order": "specific", "targets": ({"invoice_number": invoice_no},)},
    )
    monkeypatch.setattr(seams, "payment_entry_source", lambda: "entry")
    monkeypatch.setattr(connections, "_moment_of", lambda on_date: POSTED_AT)

    class _Conn:
        id = uuid.uuid4()
        connection_no = "NC-1"

    taken = {
        "amount": THIRTY,
        "on_date": POSTED_AT.date(),
        "cleared_on": None,
        "method_code": "card",
        "confirmation": AUTH,
        "memo": None,
        "duplicate_confirmed": False,
    }
    with pytest.raises(duplicates.PossibleDuplicatePayment) as caught:
        connections._record_the_payment_taken(
            None, _Conn(), taken, {"invoice_no": "INV-1", "account_id": uuid.uuid4()}
        )
    assert seen["warn_on_possible_duplicate"] is True
    assert seen["duplicate_confirmed"] is False
    answer = connections._payment_refused_on_the_charges_step(caught.value)
    assert answer.code == "BIZ-IDEMPOTENT"
    assert answer.message_key == "payments.record.possible_duplicate"
    assert answer.params["payment_no"] == "PY-261002-0093"
    assert answer.params["step"] == connections.STEP_OF_THE_CHARGES
    # Every other payments refusal is still the ordinary step-4 refusal.
    other = connections._payment_refused_on_the_charges_step(
        PaymentRuleError("no", br_ref="BR-PAY-026")
    )
    assert other.message_key == "metering.connection_payment_refused"
