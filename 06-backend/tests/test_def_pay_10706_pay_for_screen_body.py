# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10706 (tester L1-08) — the "Pay for…" screen
# Ruling:   PO 2026-10-30 Q4 = A (build as the approved mock-up) ·
#           BR-PAY-1126..1130
# Tests:    this file (the server half of the SCREEN's body); the DOM half is
#           07-frontend/src/features/payments/payForSeveral.dom.test.tsx
# ───────────────────────────────────────────────────────
"""The EXACT body the *Pay for: Several accounts* screen sends, through the
premises door, on the mock-up's own figures.

`test_pay_h_pay_for_others.py` proved the door with one part per account and no
allocation choice. The screen sends something more specific, and these cases
pin THAT shape: one part per ACCOUNT, `apply_to: "split"`, one target per BILL
(Grand Vista's unit 103 carries two — September's $40.00 left over and
October's $92.10), and the landlord's leftover as a `carry_credit` part on the
MASTER's own account.

  * $1,003.60 across units 101–108 → 8 payments, all 9 bills paid, 8 entries,
    each balanced; the master gets no payment.
  * $0.01 short → refused whole, nothing written.
  * $1,023.60 with $20.00 on the master → 9 payments; the master's is $20.00,
    meets no bill and carries $20.00 as credit.

Run on SQLite and on PostgreSQL 16 (non-superuser, NOBYPASSRLS role).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.payments import models, tender_models

from tests.test_pay_h_pay_for_others import (  # noqa: F401 — the `centre` fixture
    _balance_owed,
    _each_entry_is_balanced,
    _open_till,
    a_master_with_let_units,
    centre,
    pay_for_units,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: The mock-up's eight units and what each owes on October's bill. Unit 103 also
#: owes $40.00 on September's — nine bills, $1,003.60.
OCTOBER = (
    ("Unit 101", Decimal("121.40")),
    ("Unit 102", Decimal("118.75")),
    ("Unit 103", Decimal("92.10")),
    ("Unit 104", Decimal("109.80")),
    ("Unit 105", Decimal("127.35")),
    ("Unit 106", Decimal("115.20")),
    ("Unit 107", Decimal("141.60")),
    ("Unit 108", Decimal("137.40")),
)
SEPTEMBER_103 = Decimal("40.00")


def _grand_vista(actor, tenant):
    master, tenants = a_master_with_let_units(
        actor,
        tenant,
        name="Grand Vista Properties",
        master_no="AC-2026-00618",
        tax_id="42-1000618",
        units=tuple(
            (label, f"AC-2026-{622 + i:05d}", owed) for i, (label, owed) in enumerate(OCTOBER)
        ),
    )
    older = an_issued_bill(
        tenant, tenants[2], number="BL-2609-000377", total=SEPTEMBER_103, issued_on=date(2026, 9, 1)
    )
    return master, tenants, older


def _screen_body(tenants, older, *, amount, credit_on=None, credit="0", short=Decimal("0")):
    """What `partsFor` in PayForSeveral.tsx builds: one part per account, its
    bills as `split` targets; a leftover as `carry_credit` on the master."""
    parts = []
    for index, (account, (_label, owed)) in enumerate(zip(tenants, OCTOBER, strict=True)):
        october = f"BL-2610-{account.account_no[-5:]}"
        targets = [{"invoice_number": october, "amount": str(owed)}]
        total = owed
        if index == 2:
            targets.insert(0, {"invoice_number": older.invoice_no, "amount": str(SEPTEMBER_103)})
            total += SEPTEMBER_103
        if index == len(tenants) - 1 and short:
            targets[-1]["amount"] = str(owed - short)
            total -= short
        parts.append(
            {"account_id": str(account.pk), "amount": str(total), "apply_to": "split", "targets": targets}
        )
    if credit_on is not None:
        parts.append({"account_id": str(credit_on.pk), "amount": credit, "apply_to": "carry_credit"})
    return {
        "amount": amount,
        "posted_at": "2026-10-31",
        "method": "check",
        "reference": "5521",
        "memo": "October bills, units 101-108",
        "idempotency_key": str(uuid.uuid4()),
        "parts": parts,
    }


def _post(actor, tenant, master, body):
    from apps.payments import tenders_api

    return api_call(
        tenders_api.premises_payments,
        "post",
        f"/api/brazos/accounts/{master.pk}/premises-payments",
        user=actor.user,
        role=actor.role,
        tenant=tenant,
        data=body,
        account_id=str(master.pk),
    )


def test_grand_vista_1003_60_across_units_101_to_108_as_the_screen_sends_it(brazos, dana, centre):
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        master, tenants, older = _grand_vista(dana, brazos)
    response = _post(dana, brazos, master, _screen_body(tenants, older, amount="1003.60"))
    assert response.status_code == 201, response.data
    assert response.data["part_count"] == 8
    assert Decimal(response.data["amount"]) == Decimal("1003.60")
    with tenant_ctx(brazos):
        assert all(_balance_owed(t) == Decimal("0") for t in tenants)
        assert not models.Payment.objects.filter(account_id=master.id).exists()
        unit_103 = models.Payment.objects.get(account_id=tenants[2].id)
        assert unit_103.amount == Decimal("132.10")
        assert _each_entry_is_balanced(brazos) == 8


def test_a_cent_short_is_refused_whole_and_writes_nothing(brazos, dana, centre):
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        master, tenants, older = _grand_vista(dana, brazos)
    body = _screen_body(tenants, older, amount="1003.60", short=Decimal("0.01"))
    response = _post(dana, brazos, master, body)
    assert response.status_code == 422, response.data
    assert response.data["message_key"] == "payments.tender.refused"
    with tenant_ctx(brazos):
        assert models.Payment.objects.count() == 0
        assert tender_models.PaymentTender.objects.count() == 0


def test_the_leftover_on_the_masters_row_is_the_masters_credit(brazos, dana, centre):
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        master, tenants, older = _grand_vista(dana, brazos)
    body = _screen_body(tenants, older, amount="1023.60", credit_on=master, credit="20.00")
    response = _post(dana, brazos, master, body)
    assert response.status_code == 201, response.data
    assert response.data["part_count"] == 9
    on_master = response.data["payments"][8]
    assert Decimal(on_master["amount"]) == Decimal("20.00")
    assert Decimal(on_master["credit_carried"]) == Decimal("20.00")
    assert on_master["allocations"] == []
    with tenant_ctx(brazos):
        assert all(_balance_owed(t) == Decimal("0") for t in tenants)
        assert models.Payment.objects.get(account_id=master.id).amount == Decimal("20.00")
        assert _each_entry_is_balanced(brazos) == 9
