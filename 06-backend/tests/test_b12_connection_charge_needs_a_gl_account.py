# ── Trace ──────────────────────────────────────────────
# Task:    one-time bill build plan B12 — a first bill's connection charge is
#          checked for a GL account at DRAFT, as a fee bill's charge is.
# Code:    apps/billing/first_bill.py :: connection_charge_line_for
# Rules:   BR-BIL-010 (charge codes carry their own GL) · BR-BIL-012
# ───────────────────────────────────────────────────────
"""A connection charge on a code with no GL account refuses at draft, by name.

RED on the tip: the line was built, the draft was written with a bill number,
and the whole first bill would have died at ISSUE on `line_has_no_gl_account`.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import first_bill
from apps.billing.exceptions import BillingRuleError
from apps.ledger import models as ledger_models
from apps.rating import models as rating_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

DATA = SimpleNamespace(account_no="A-B12")


def _conn(tenant, code, *, gl):
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name="Connection charge",
        charge_type="one_time",
        amount_rule="flat",
        amount=Decimal("45.00"),
        # A real ledger account: on PostgreSQL `fk_charges_gl_account` refuses
        # a made-up id (SQLite does not enforce it — the first draft used one).
        gl_account_id=(
            ledger_models.LedgerAccount.objects.filter(tenant=tenant)
            .values_list("id", flat=True)
            .first()
            if gl
            else None
        ),
    )


def test_B12_a_connection_code_with_no_GL_account_refuses_at_draft(brazos):
    with tenant_ctx(brazos):
        _conn(brazos, "CONN-NOGL", gl=False)
        with pytest.raises(BillingRuleError) as refusal:
            first_bill.connection_charge_line_for(DATA, code="CONN-NOGL")

    assert refusal.value.message_key == "billing.oneTime.err.chargeCodeNoGl"
    assert refusal.value.params == {"code": "CONN-NOGL"}
    assert "no GL account" in str(refusal.value)


def test_B12_a_connection_code_WITH_a_GL_account_still_builds_its_line(brazos):
    with tenant_ctx(brazos):
        charge = _conn(brazos, "CONN-GL", gl=True)
        assert charge.gl_account_id is not None
        lines = first_bill.connection_charge_line_for(DATA, code="CONN-GL")

    assert [line.amount for line in lines.lines] == [Decimal("45.00")]
