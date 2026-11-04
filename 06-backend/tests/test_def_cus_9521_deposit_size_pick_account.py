# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-9521 — a vacant unit with no meter fitted could not open an
#          account on a plan whose deposit is priced by meter size.
# Ruling:  PO 2026-10-04 (decision log "THREE PO ANSWERS" item 3), verbatim:
#          *"(c) Let the clerk pick the size on the Deposit step."*
# Rules:   BR-CUS-025 (a deposit is a liability) · BR-CUS-037 (customers is the
#          entry point; payments records the money) · CLAUDE.md rule 7 (audit)
# Tests:   the CUSTOMERS half — the step offers the sizes, the commit takes the
#          picked size's figure, stores the pick on the account and audits it.
#          Rating's half (which figure a size asks) is
#          `test_def_cus_9521_deposit_size_pick.py`; rating's answer is stood
#          in for here so this file proves only what customers does with it.
# ───────────────────────────────────────────────────────
"""Rosa, 1408 Elm St · Unit A, no meter yet: the clerk picks 2" → **$600.00**."""

import uuid
from decimal import Decimal

import pytest

from apps.customers import deposit as customers_deposit
from apps.customers import services as customers_services
from apps.payments import models as payment_models
from apps.rating import selectors as rating_selectors
from core import errors
from tests.test_cr094_wh_deposit import MOVE_IN_DAY, _payload, _unit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

SIZES = {"W-58": ('Water 5/8"', Decimal("150.00")), "W-2": ('Water 2"', Decimal("600.00"))}


def _sized_rule(recorded=None):
    """rating's answer for a plan pricing DEP-SIZE at 5/8" $150.00 and 2"
    $600.00, on a unit whose recorded size is `recorded` (None: no meter)."""

    def answer(plan_id, account_type_id, *, unit_id=None, account_id=None, size_class=None):
        size = recorded or size_class
        if size is None:
            return {
                "amount": None,
                "currency": None,
                "refusal": "size_not_recorded",
                "code": "DEP-SIZE",
                "size_class": None,
                "sizes": [
                    {"size_class": code, "label": label, "amount": amount}
                    for code, (label, amount) in SIZES.items()
                ],
            }
        if size not in SIZES:
            return {"amount": None, "currency": None, "refusal": "size_not_priced",
                    "code": "DEP-SIZE", "size_class": size}
        out = {"amount": SIZES[size][1], "currency": "USD"}
        if recorded is None:
            out.update(size_class=size, size_label=SIZES[size][0], size_picked=True)
        return out

    return answer


def _block(**overrides):
    block = {
        "decision": "required",
        "take_now": True,
        "method_code": "cash",
        "posted_at": MOVE_IN_DAY,
        "idempotency_reference": str(uuid.uuid4()),
    }
    block.update(overrides)
    return block


def test_the_step_offers_the_sizes_when_no_meter_is_fitted(brazos, dana, monkeypatch):
    """Red before the fix: `GET /accounts/deposit-standard` refused with
    `customers.deposit.sizeNotPriced` and offered nothing."""
    monkeypatch.setattr(rating_selectors, "deposit_rule_for", _sized_rule())
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit A", asks=False)
        shown = customers_deposit.standard_for_unit(unit["id"], "residential")
        assert shown["asks"] is True
        assert shown["amount"] is None
        assert shown["pick_size"] is True
        assert {(s["size_class"], s["label"], s["amount"]) for s in shown["sizes"]} == {
            ("W-58", 'Water 5/8"', "150.0000"),
            ("W-2", 'Water 2"', "600.0000"),
        }
        picked = customers_deposit.standard_for_unit(unit["id"], "residential", size_class="W-2")
        assert picked["amount"] == "600.0000"
        assert picked["size_class"] == "W-2"


def test_a_meter_fitted_asks_its_own_size_and_offers_no_picker(brazos, dana, monkeypatch):
    monkeypatch.setattr(rating_selectors, "deposit_rule_for", _sized_rule(recorded="W-58"))
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit B", asks=False)
        shown = customers_deposit.standard_for_unit(unit["id"], "residential")
        assert shown["amount"] == "150.0000"
        assert not shown.get("pick_size")
        assert "sizes" not in shown


def test_the_clerk_picks_2_inch_600_is_taken_stored_and_audited(
    brazos, dana, monkeypatch, audit_rows
):
    """The ruling's worked case end to end on the customers side: $600.00 taken,
    the pick kept on the account, and an audit row naming the size and why."""
    monkeypatch.setattr(rating_selectors, "deposit_rule_for", _sized_rule())
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit C", asks=False)
        result = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit=_block(amount="600.00", size_class="W-2"))
        )
        assert Decimal(result["deposit"]["amount"]) == Decimal("600.00")
        assert result["deposit"]["size_class"] == "W-2"
        payments = list(
            payment_models.Payment.objects.filter(
                account_id=result["id"], purpose=payment_models.PURPOSE_DEPOSIT
            )
        )
        assert [p.amount for p in payments] == [Decimal("600.0000")]
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_assessed == Decimal("600.0000")
        assert account.deposit_size_class == "W-2"
        assert str(account.deposit_size_picked_by_id) == str(dana.id)
        assert account.deposit_size_picked_at is not None
        rows = [
            row
            for row in audit_rows
            if row["action"] == "deposit.size_picked" and str(row["entity_id"]) == str(result["id"])
        ]
        assert len(rows) == 1
        assert str(rows[0]["actor_user_id"]) == str(dana.id)
        assert rows[0]["after"]["size_class"] == "W-2"
        assert rows[0]["after"]["size"] == 'Water 2"'
        assert rows[0]["after"]["reason"] == "no_meter_fitted"


def test_no_pick_on_a_unit_with_no_meter_is_refused_by_name(brazos, dana, monkeypatch):
    """A hand-built request that sends no size cannot connect with no deposit."""
    monkeypatch.setattr(rating_selectors, "deposit_rule_for", _sized_rule())
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit D", asks=False)
        with pytest.raises(errors.ValidationError) as raised:
            customers_services.create_account(
                dana, _payload(unit_id=str(unit["id"]), deposit=_block())
            )
        assert raised.value.message_key == customers_deposit.SIZE_REQUIRED


def test_a_meter_fitted_takes_150_and_stores_no_pick(brazos, dana, monkeypatch):
    """A 5/8" meter: $150.00 as before; a stale 2" pick at $600.00 is refused
    as not the plan's figure, never silently re-priced."""
    monkeypatch.setattr(rating_selectors, "deposit_rule_for", _sized_rule(recorded="W-58"))
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit E", asks=False)
        result = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit=_block(amount="150.00"))
        )
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_assessed == Decimal("150.0000")
        assert account.deposit_size_class is None
        unit2, _p2 = _unit(dana, brazos, label="Unit F", asks=False)
        with pytest.raises(errors.ValidationError) as raised:
            customers_services.create_account(
                dana,
                _payload(unit_id=str(unit2["id"]), deposit=_block(amount="600.00", size_class="W-2")),
            )
        assert raised.value.message_key == customers_deposit.AMOUNT_NOT_PLAN


def test_the_block_accepts_a_size():
    """Red before the fix: `size_class` was an unknown field."""
    cleaned = customers_deposit.clean({"decision": "required", "size_class": "W-2"})
    assert cleaned.size_class == "W-2"
