# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-9807 — an "Entered when used" code may carry an optional
#          default price (PO ruling 2026-10-06, option (a); BR-RAT-1054 AMENDED)
#          DEF-RAT-9805 — "Apply automatically: Yes" on a one-time code is refused
# Rules:   BR-RAT-1054 (as amended) · BR-RAT-1016 (a reprice of a code in use
#          needs a reason) · BR-BIL-020 (no typed figure beside a stated price)
#          · BR-RAT-117 / BR-RAT-730 (recurring AND auto_apply rides a bill)
# ───────────────────────────────────────────────────────
"""The two server halves of lane CHARGE-CODE-FIVE.

🔒 Money path (rating math + fee bills). The worked statement put on the review
ledger, and asserted below: *App-Fee is Entered when used with a default of
$10.00. When a clerk adds it, the amount starts at $10.00 and they may type
$25.00; the bill shows the amount they ended with. With no default, the clerk
types it every time, as today.*

The default reaches a clerk's screen as `default_amount` and NEVER as
`amount`: every door that charges a code's own fixed price (service-request
fees, the counter, the portal's quote, the bill run's fee reader) reads
`amount`, and none of them may start charging a per-case code at its default
with no clerk looking. The fee bill still takes the clerk's figure.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.billing import fee_bill
from apps.billing.exceptions import BillingRuleError
from apps.rating import models as rating_models
from apps.rating import move_in_fees
from apps.rating import selectors as rating_selectors
from apps.rating import services as rating_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, make_plan, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

FROM = dt.date(2026, 1, 1)


def _gl(tenant):
    return str(
        rating_models.Charge.objects.get(tenant=tenant, code="LATE", deleted_at__isnull=True).gl_account_id
    )


def _app_fee(tenant, actor, *, default=None, code="APP-X", charge_type="one_time"):
    payload = {
        "code": code,
        "name": "Application processing fee",
        "charge_type": charge_type,
        "kind": "other",
        "amount_rule": "per_case",
        "gl_account_id": _gl(tenant),
        "effective_from": FROM.isoformat(),
    }
    if default is not None:
        payload["amount"] = default
    with tenant_ctx(tenant):
        return rating_services.create_charge(actor, payload)


# ── DEF-RAT-9807 · the default ──────────────────────────────────────────────


def test_an_entered_when_used_code_saves_with_a_default_of_10(brazos, dana):
    row = _app_fee(brazos, dana, default="10.00")
    assert row["amount_rule"] == "per_case"
    assert row["amount_display"] == "10.00"


def test_with_no_default_it_saves_exactly_as_today(brazos, dana):
    row = _app_fee(brazos, dana)
    assert row["amount_rule"] == "per_case"
    assert row["amount"] is None and row["prices"] == []


def test_a_size_table_or_a_percent_beside_entered_when_used_is_still_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            rating_services.create_charge(
                dana,
                {
                    "code": "APP-S",
                    "name": "x",
                    "amount_rule": "per_case",
                    "size_amounts": [{"size_class": "W-1", "amount": "5.00"}],
                },
            )
        with pytest.raises(errors.ValidationError):
            rating_services.create_charge(
                dana, {"code": "APP-P", "name": "x", "amount_rule": "per_case", "percent": "0.0150"}
            )


def test_the_default_is_served_as_default_amount_and_never_as_amount(brazos, dana):
    _app_fee(brazos, dana, default="10.00")
    _app_fee(brazos, dana, code="APP-N")
    with tenant_ctx(brazos):
        read = rating_selectors.charge_by_code("APP-X")
        blank = rating_selectors.charge_by_code("APP-N")
    assert read["amount"] is None
    assert Decimal(read["default_amount"]) == Decimal("10.00")
    assert blank["amount"] is None and blank["default_amount"] is None


def test_the_clerk_types_25_and_the_bill_line_is_25(brazos, dana):
    _app_fee(brazos, dana, default="10.00")
    with tenant_ctx(brazos):
        assert fee_bill.charge_code_line("APP-X", entered_amount=Decimal("25.00")).amount == Decimal("25.00")
        # The screens start the box at the default; the clerk leaving it sends it.
        assert fee_bill.charge_code_line("APP-X", entered_amount=Decimal("10.00")).amount == Decimal("10.00")
        # Nothing on the server charges the default by itself — no clerk, no figure.
        with pytest.raises(BillingRuleError, match="no amount was entered"):
            fee_bill.charge_code_line("APP-X")


def test_the_move_in_quote_carries_the_default_for_the_fee_row(brazos, dana):
    _app_fee(brazos, dana, default="10.00")
    _app_fee(brazos, dana, code="APP-N")
    with tenant_ctx(brazos):
        row = move_in_fees.price_code("APP-X", customer_class=None)
        blank = move_in_fees.price_code("APP-N", customer_class=None)
    assert row["priced_by"] == "per_case" and row["amount"] is None
    assert row["default_amount"] == "10.0000"
    assert blank["default_amount"] is None


def test_the_bill_runs_fee_reader_never_charges_a_default(brazos, dana):
    """A recurring, auto-applied Other code priced per case: no clerk is there
    to type a figure, so the default is not a price the bill run may charge."""
    _app_fee(brazos, dana, default="10.00", code="APP-R", charge_type="recurring")
    with tenant_ctx(brazos):
        rating_models.Charge.objects.filter(tenant=brazos, code="APP-R").update(auto_apply=True)
        plan = make_plan(brazos, name="Plain plan", code="plain-plan")
    with tenant_ctx(brazos):
        rows = rating_selectors.billable_charge_codes(plan.id, dt.date(2026, 7, 1), customer_class=None)
    mine = [row for row in rows if row["code"] == "APP-R"]
    assert mine and mine[0]["amount"] is None


def test_changing_the_default_of_a_code_in_use_needs_a_reason(brazos, dana):
    row = _app_fee(brazos, dana, default="10.00")
    plan = make_plan(brazos, name="Fee plan", code="fee-plan")
    with tenant_ctx(brazos):
        rating_models.PlanChargeRule.objects.create(tenant=brazos, rate_plan=plan, charge_id=row["id"])
        with pytest.raises(errors.ValidationError) as caught:
            rating_services.update_charge(
                dana, row["id"], {"amount_rule": "per_case", "amount": "12.00", "effective_from": "2026-11-01"}
            )
        assert "reason" in str(caught.value.field_errors)
        after = rating_services.update_charge(
            dana,
            row["id"],
            {
                "amount_rule": "per_case",
                "amount": "12.00",
                "effective_from": "2026-11-01",
                "reason": "Application fee raised by council",
            },
        )
    assert after["amount_rule"] == "per_case"
    assert [p["amount_display"] for p in after["prices"] if not p["killed"]][-1] == "12.00"


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana):
    """**PO, verbatim, 2026-10-06: *"S1–S8 approve"*** — S2, shown as:
    *"App-Fee is Entered when used with a default of $10.00. When a clerk adds
    it, the amount starts at $10.00 and they may type $25.00; the bill shows
    the amount they ended with. With no default, the clerk types it every
    time, as today."*

    Clauses (1)–(3) of the review-ledger row were NOT in the statement and are
    asserted by their own tests above, not here.
    """
    saved = _app_fee(brazos, dana, default="10.00", code="APP-FEE")
    _app_fee(brazos, dana, code="APP-NONE")
    assert saved["amount_rule"] == "per_case"
    with tenant_ctx(brazos):
        with_default = rating_selectors.charge_by_code("APP-FEE")
        no_default = rating_selectors.charge_by_code("APP-NONE")
        # The amount starts at $10.00 …
        assert Decimal(with_default["default_amount"]) == Decimal("10.00")
        # … the clerk may type $25.00, and the bill shows what they ended with.
        assert fee_bill.charge_code_line("APP-FEE", entered_amount=Decimal("25.00")).amount == Decimal("25.00")
        assert fee_bill.charge_code_line("APP-FEE", entered_amount=Decimal("10.00")).amount == Decimal("10.00")
        # With no default there is nothing to start from: the clerk types it.
        assert no_default["default_amount"] is None
        with pytest.raises(BillingRuleError, match="no amount was entered"):
            fee_bill.charge_code_line("APP-NONE")
        assert fee_bill.charge_code_line("APP-NONE", entered_amount=Decimal("25.00")).amount == Decimal("25.00")


def test_the_four_actual_cost_codes_keep_no_default(brazos):
    with tenant_ctx(brazos):
        for code in ("TAP", "IMPACT", "DAMAGE", "BULK-WATER"):
            read = rating_selectors.charge_by_code(code)
            if read is None:
                continue  # not provisioned on this seed
            assert read["amount_rule"] == "per_case"
            assert read["default_amount"] is None, code


# ── DEF-RAT-9805 · Apply automatically on a one-time code ──────────────────


def test_apply_automatically_on_a_one_time_code_is_refused_by_field(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            rating_services.create_charge(
                dana,
                {
                    "code": "ONE-A",
                    "name": "One-time fee",
                    "charge_type": "one_time",
                    "kind": "other",
                    "amount_rule": "flat",
                    "amount": "20.00",
                    "auto_apply": True,
                    "gl_account_id": _gl(brazos),
                },
            )
    fields = {fe["field"]: fe["message_key"] for fe in caught.value.field_errors}
    assert fields.get("auto_apply") == "rating.charges.auto_apply_one_time"


def test_a_recurring_code_may_still_apply_automatically(brazos, dana):
    with tenant_ctx(brazos):
        row = rating_services.create_charge(
            dana,
            {
                "code": "REC-A",
                "name": "Paper bill fee",
                "charge_type": "recurring",
                "kind": "other",
                "amount_rule": "flat",
                "amount": "2.00",
                "auto_apply": True,
                "gl_account_id": _gl(brazos),
            },
        )
    assert row["auto_apply"] is True


def test_turning_a_recurring_auto_code_one_time_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        row = rating_services.create_charge(
            dana,
            {
                "code": "REC-B",
                "name": "Fee",
                "charge_type": "recurring",
                "kind": "other",
                "amount_rule": "flat",
                "amount": "2.00",
                "auto_apply": True,
                "gl_account_id": _gl(brazos),
            },
        )
        with pytest.raises(errors.ValidationError):
            rating_services.update_charge(dana, row["id"], {"charge_type": "one_time"})
        after = rating_services.update_charge(dana, row["id"], {"charge_type": "one_time", "auto_apply": False})
    assert after["charge_type"] == "one_time" and after["auto_apply"] is False
