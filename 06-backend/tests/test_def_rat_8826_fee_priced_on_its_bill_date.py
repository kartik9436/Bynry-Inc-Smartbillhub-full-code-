"""DEF-RAT-8826 — a fee bill prices its charge code on the BILL's date, for the account's class.

Found by the charge-code walk of 2026-10-01 (`10-scripts/charge_codes_walk33.mjs`):
`RE-READ` repriced **$20.00 → $21.00 from 11/01/2026** through the Edit screen,
then a one-time fee bill dated **11/15/2026** still billed **$20.00** — the
fee path asked `rating.charge_by_code(code)` with no date, which answers the
tenant's TODAY. A charge code's price is dated (`CR-156-BRC10`, PO 2026-10-01:
*"A past bill reads the row in force on its dates"*), and
`charge_prices.price_on_date` says it in as many words: *"a bill passes its own
dates and never today"*.

RED FIRST (law 7): on the tip before `fee_bill.py` changed, `tc1` failed with
`assert Decimal('20.0000') == Decimal('21.00')` (the 11/15 fee read today's
row) and `tc3` refused with *"charge code 'CLS-WALK' is priced as 'flat', which
needs a BASIS"* — a code priced only by customer class could not be raised at
all, because no class reached the read.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): a fee path that always
read the NEWEST row would pass `tc1` — `tc2` asks for the 10/15 bill and wants
the OLD $20.00. A path that read any class's row would pass `tc3` for one class
only — it asserts the figure for the account's OWN class.
"""

from datetime import date
from decimal import Decimal as D

import pytest
from django.db import transaction

from apps.billing import fee_bill
from apps.rating import charge_prices
from apps.rating import models as rating_models
from apps.rating.constants import ALL_SIZES

from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_us_bil_001_prepare import (  # noqa: F401
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

CHANGE_FROM = date(2026, 11, 1)


def _code(tenant, code, target, *, effective_from=charge_prices.PRICE_HISTORY_EPOCH):
    from apps.ledger import models as ledger_models

    gl = ledger_models.LedgerAccount.objects.filter(tenant=tenant, deleted_at__isnull=True).first()
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code=code,
        defaults={
            "name": f"{code} fee",
            "charge_type": "one_time",
            "amount_rule": "flat",
            "gl_account_id": gl.id,
            "taxable_default": False,
        },
    )
    with transaction.atomic():
        charge_prices.save_prices(row, target, effective_from=effective_from, effective_to=None)
    return row


def _fee(account, code, on):
    return fee_bill.price_charge_fee(account_id=str(account.id), charge_code=code, on_date=on).line.amount


def test_def_rat_8826_tc1__a_fee_dated_after_a_price_change_bills_the_new_price(brazos, dana):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-88261", asset_no="M-88261")
        charge = _code(brazos, "RR-WALK", {(ALL_SIZES, None): D("20.00")})
        with transaction.atomic():
            charge_prices.save_prices(
                charge, {(ALL_SIZES, None): D("21.00")}, effective_from=CHANGE_FROM, effective_to=None
            )
        assert _fee(account, "RR-WALK", date(2026, 11, 15)) == D("21.00")


def test_def_rat_8826_tc2__a_fee_dated_before_the_change_bills_the_old_price(brazos, dana):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-88262", asset_no="M-88262")
        charge = _code(brazos, "RR-WALK2", {(ALL_SIZES, None): D("20.00")})
        with transaction.atomic():
            charge_prices.save_prices(
                charge, {(ALL_SIZES, None): D("21.00")}, effective_from=CHANGE_FROM, effective_to=None
            )
        assert _fee(account, "RR-WALK2", date(2026, 10, 15)) == D("20.00")


def test_def_rat_8826_tc3__a_code_priced_by_class_bills_the_accounts_own_class(brazos, dana):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana, account_no="A-88263", asset_no="M-88263")
        own = account.account_type.code
        other = "commercial" if own != "commercial" else "residential"
        _code(brazos, "CLS-WALK", {(ALL_SIZES, own): D("30.00"), (ALL_SIZES, other): D("50.00")})
        assert _fee(account, "CLS-WALK", date(2026, 10, 15)) == D("30.00")
