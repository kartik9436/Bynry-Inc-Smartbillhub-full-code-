# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-PAY-10765 (W1 — a Finance Executive offered Match to payment on
#           a returned statement line, refused 403 after filling the form) ·
#           DEF-PAY-10766 (W2 — the match form's NSF fee quote must be readable
#           by the same Executive)
# Ruling:   decision log 2026-10-30 "Final-walk questions W1–W4 answered (PO)"
#           — W1 = A, verbatim *"W1-A -Allow Finance Executive"*. Scope as put
#           to the PO: the statement-line match of a returned item only. "Any
#           other reversal path keeps its current roles unless ruled."
# Rules:    BR-PAY-1070 (reversal is System Admin only — NARROWED for this one
#           door) · BR-SHL-025 (the service's gate is THE gate) · CLAUDE.md
#           rules 5 (only the ledger posts) and 7 (audit on every money action)
# ───────────────────────────────────────────────────────
"""W1 — an Executive reverses a bounce from the statement; nowhere else.

The tester's day (`test_lbx05_09_statement_lines_post`): cheque **4103**,
**154.00**, comes back on line **RET1029-02**. Erin (Executive) matches it:
the cheque is reversed, reason *Returned by the bank*, the line's text is the
Bank memo, and 154.00 moves holding → cash. The same Erin pressing Reverse on
the Payments list is still refused, and a Billing Clerk is refused at the
statement door too.
"""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.payments import api as payments_api
from apps.payments import models, reconciliation, reversal, reversal_api
from core import errors

from tests.test_lbx05_09_statement_lines_post import (
    HAND_REVERSED_AT,
    WORKED_AT,
    import_the_statement,
    line,
    the_lockbox_day,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _person(tenant, role, email):
    """A real `users` row, signed in, carrying the role the service guards read."""
    actor = staff_actor(tenant, role, email)
    return SimpleNamespace(
        id=actor.id, pk=actor.id, role=role, user=actor.user, is_authenticated=True
    )


@pytest.fixture()
def erin_exec(brazos):
    return _person(brazos, "executive", "erin@brazosbendutilities.test")


@pytest.fixture()
def carl_clerk(brazos):
    return _person(brazos, "billing_clerk", "carl@brazosbendutilities.test")


def _the_day(dana, brazos):
    payments, _batch = the_lockbox_day(dana, brazos)
    statement_id = import_the_statement(dana, brazos).statement_import_id
    return payments, statement_id


# ── W1: the one door that widens ────────────────────────────────────────────
def test_w1__an_executive_matches_a_returned_line_and_the_cheque_is_reversed(
    brazos, dana, erin_exec, audit_rows
):
    with tenant_ctx(brazos):
        payments, statement_id = _the_day(dana, brazos)
        ret2 = line(statement_id, "RET1029-02")

        result = reconciliation.match_returned_line(
            actor=erin_exec,
            bank_line_id=ret2.pk,
            payment_id=payments["4103"].pk,
            occurred_at=WORKED_AT,
            nsf_fee_waived=True,
            nsf_fee_waive_reason="Account closed, not the customer's fault",
        )

        assert result.reversed_now is True
        assert result.amount == Decimal("-154.00")
        reversing = models.Payment.objects.get(pk=result.reversal_payment_id)
        assert reversing.reverses_payment_id == payments["4103"].pk
        assert reversing.reversal_reason == models.REVERSAL_REASON_NSF  # Returned by the bank
        assert reversing.memo == "RET1029-02"  # the Bank memo
        assert result.nsf_fee_status is not None
    # audited, as Erin, with the untick reason on the row
    matched = [row for row in audit_rows if row["action"] == reconciliation.AUDIT_LINE_RETURN_MATCHED]
    assert len(matched) == 1
    assert str(matched[0]["actor_user_id"]) == str(erin_exec.id)
    assert matched[0]["after"]["nsf_fee_waive_reason"] == "Account closed, not the customer's fault"


def test_w1__the_executive_match_over_http_is_created(brazos, dana, erin_exec):
    with tenant_ctx(brazos):
        payments, statement_id = _the_day(dana, brazos)
        ret2 = line(statement_id, "RET1029-02")
    response = api_call(
        payments_api.bank_line_match_return,
        "post",
        user=erin_exec,
        role="executive",
        tenant=brazos,
        data={"payment_id": str(payments["4103"].pk), "occurred_at": WORKED_AT.isoformat()},
        bank_line_id=str(ret2.pk),
    )
    assert response.status_code == 201, response.data
    assert response.data["reversed_now"] is True


# ── every other reversal path keeps its roles ───────────────────────────────
def test_w1__the_executive_is_still_refused_the_payments_list_reverse(brazos, dana, erin_exec):
    with tenant_ctx(brazos):
        payments, _statement_id = _the_day(dana, brazos)
        with pytest.raises(errors.AuthError):
            reversal.reverse_payment(
                erin_exec,
                payment_id=payments["4102"].pk,
                returned_on=HAND_REVERSED_AT,
                reason=models.REVERSAL_REASON_NSF,
                idempotency_reference=uuid.uuid4(),
            )
        assert not models.Payment.objects.filter(reverses_payment=payments["4102"]).exists()
    response = api_call(
        reversal_api.payment_reverse,
        "post",
        user=erin_exec,
        role="executive",
        tenant=brazos,
        data={
            "returned_on": HAND_REVERSED_AT.isoformat(),
            "reason": "nsf",
            "idempotency_reference": str(uuid.uuid4()),
        },
        payment_id=str(payments["4102"].pk),
    )
    assert response.status_code == 403


def test_w1__the_bank_return_door_refuses_a_reason_other_than_returned_by_the_bank(
    brazos, dana, erin_exec
):
    """The widened service takes no `reason` at all — it cannot be used as a
    back door to a staff reversal ("entered in error", "chargeback")."""
    import inspect

    assert "reason" not in inspect.signature(reversal.reverse_returned_by_bank.__wrapped__).parameters
    with tenant_ctx(brazos):
        payments, _statement_id = _the_day(dana, brazos)
        with pytest.raises(TypeError):
            reversal.reverse_returned_by_bank(
                erin_exec,
                payment_id=payments["4102"].pk,
                returned_on=HAND_REVERSED_AT,
                reason="error",
            )


def test_w1__a_billing_clerk_is_refused_at_the_statement_door(brazos, dana, carl_clerk):
    with tenant_ctx(brazos):
        payments, statement_id = _the_day(dana, brazos)
        ret2 = line(statement_id, "RET1029-02")
        with pytest.raises(errors.AuthError):
            reconciliation.match_returned_line(
                actor=carl_clerk,
                bank_line_id=ret2.pk,
                payment_id=payments["4103"].pk,
                occurred_at=WORKED_AT,
            )
        assert not models.Payment.objects.filter(reverses_payment=payments["4103"]).exists()
    response = api_call(
        payments_api.bank_line_match_return,
        "post",
        user=carl_clerk,
        role="billing_clerk",
        tenant=brazos,
        data={"payment_id": str(payments["4103"].pk), "occurred_at": WORKED_AT.isoformat()},
        bank_line_id=str(ret2.pk),
    )
    assert response.status_code == 403


# ── W2: the Executive can read the fee the match will charge ────────────────
def test_w2__an_executive_reads_the_nsf_fee_quote_before_confirm(brazos, dana, erin_exec):
    with tenant_ctx(brazos):
        payments, _statement_id = _the_day(dana, brazos)
    response = api_call(
        reversal_api.payment_nsf_fee,
        "get",
        user=erin_exec,
        role="executive",
        tenant=brazos,
        query={"on": "2026-10-29"},
        payment_id=str(payments["4103"].pk),
    )
    assert response.status_code == 200, response.data
    assert response.data["status"] in {
        "charged",
        "nsf_fee_not_set_on_plan",
        "nsf_fee_no_plan",
        "nsf_fee_ambiguous_on_plan",
        "nsf_fee_cannot_be_priced",
    }
