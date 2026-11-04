# ── Trace ──────────────────────────────────────────────
# Change:   CR-181-BRC10 T1 (lane REOPEN, 2026-10-13)
# Rules:    PO rulings 2026-10-13 (decision log *"RETURNING CUSTOMER AT MOVE-IN
#           — FOUR PO RULINGS"*), verbatim: *"Q1 C both; Q2 - Reopen, for the
#           same unit only ; Q3 - give opton to use whether pay it now or carry
#           itr - Must pay first · Carry it onto the reopened account · Clerk
#           chooses"* and *"Q4 - keep 5 years right now"* · BR-CUS-017 ·
#           BR-CUS-056 · CLAUDE.md hard rules 1, 4, 7 · hard-won law 14 (run on
#           PostgreSQL too: `--ds=config.settings.pgtest --create-db`)
# ───────────────────────────────────────────────────────
"""**Viktor Valdez comes back to the same unit, owing money.**

THE WORKED CASE (the PO's own, from Silver Creek, re-cast on this suite's
fixtures): Viktor's customer record holds ONLY a name and a phone. He lived in
one unit on one account, moved out on 31 July 2026 and the books say he still
owes **$84.20**. On 1 September he moves back into the same unit.

  * Search with his name and phone           → **name_phone** (Q1 C)
  * His name and a NEW phone, on that unit    → **last_occupant** (Q1 C)
  * His name and a new phone, no unit         → nobody (a name alone, still)
  * Each answer offers **Reopen <his account>**, eligible, owing $84.20.
  * Complete with *Carry it*  → the SAME account number, active from 1 Sep,
    `closed_at` cleared, a NEW service agreement, the $84.20 still owed on
    the books, the choice and the figure on the move-in, two audit rows — and
    not one issued invoice, payment or journal line changed.
  * Complete with *Must pay first* → refused by name while $84.20 is owed;
    after an $84.20 payment through Payments' own `record_payment`, it opens.
  * Refused by name: another unit · someone else's account · closed more than
    5 years ago · somebody living in the unit · owing with no choice made.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): asserting the
response rather than the tables (every case reads rows back); a refusal that
passes because the call failed for another reason (each asserts its
`message_key`); an "unchanged" check over zero rows (the money case asserts
the journal holds the opening entry it then compares).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import move_in_reopen, moves
from apps.customers import services as customers_services
from apps.customers.move_in_reopen_models import MoveInReopening
from core import errors

from tests import identity_fixtures
from tests.test_br_cus_1077_move_in_job import _served_unit
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

VIKTOR = "Viktor Valdez"
PHONE = "512-555-0122"
NEW_PHONE = "512-555-0999"
OWED = Decimal("84.2000")


def _close(account_id, on_day):
    """The two writes a move-out makes that a reopen reads — the account's
    terminal status and `closed_at`, and every open agreement's `ended_on`
    (BR-CUS-030) — without the final-bill draft, which needs a priced read
    this fixture does not carry (`DEF-CUS-10093`) and is not what is tested."""
    account = customers_models.Account.objects.get(pk=account_id)
    account.status = customers_models.AccountStatus.objects.filter(
        tenant_id=account.tenant_id, behavior_class=customers_services.CLASS_TERMINAL
    ).first()
    account.closed_at = on_day
    account.save(update_fields=["status", "closed_at", "updated_at"])
    customers_services._end_service_agreements(account, on_day)


def _viktor_moved_out(actor, tenant, *, label="SCW-U-022", owed=OWED, opened="2026-03-01",
                      closed="2026-07-31"):
    """Viktor's account on one unit, closed by a move-out, owing `owed`."""
    from apps.ledger import opening_balances as ob

    _premises, unit = _served_unit(actor, tenant, label=label, address=f"22 {label} Way")
    account = customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened,
            "contact": {"full_name": VIKTOR, "phone": PHONE},
            "customer": identity_fixtures.customer_block(
                VIKTOR, account_type="residential", phone=PHONE
            ),
        },
    )
    if owed:
        # The debt as hard rule 4 freezes it: an ISSUED final bill, and its AR
        # debit on the books (posted as an opening balance — the fixture has
        # no priced read to issue a real bill from).
        from apps.billing import models as billing_models

        billing_models.Invoice.objects.create(
            tenant_id=tenant.id,
            account_id=account["id"],
            invoice_no=f"BL-CR181-{label}",
            bill_type="final",
            status="issued",
            period_start=date(2026, 7, 1),
            period_end=date.fromisoformat(closed),
            service_date=date.fromisoformat(closed),
            currency="USD",
            total=owed,
        )
        ob.post_opening_balance(
            ob.OpeningAccount(account_id=account["id"], balance=owed, account_ref=account["account_no"]),
            batch_id=f"cr181-{label}",
            cutover_on=date.fromisoformat(opened),
            imported_at=datetime(2026, 3, 1, 12, tzinfo=dt_timezone.utc),
            currency="USD",
            actor=actor,
        )
    _close(account["id"], date.fromisoformat(closed))
    viktor = customers_models.CustomerAccount.objects.get(account_id=account["id"]).customer
    return unit, account, viktor


def _search(actor, tenant, body):
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().post(
        "/api/x/customers/match", {**body, "purpose": "search_customer_id"}, format="json"
    )
    force_authenticate(request, user=actor.user)
    request.tenant_role = actor.role
    request.tenant_id = tenant.id
    with tenant_ctx(tenant):
        response = customers_api.customers_match(request)
    assert response.status_code == 200, response.data
    return response.data["search"]


def _payload(viktor, **overrides):
    body = {
        "account_type": "residential",
        "opened_at": "2026-09-01",
        "contact": {"full_name": VIKTOR, "phone": PHONE},
        "customer": {"display_name": VIKTOR, "kind": "person", "customer_id": str(viktor.id)},
    }
    body.update(overrides)
    return body


def _money_rows(account_id):
    """Every issued money row naming the account — hard rule 4's subjects —
    as tuples of the columns a forbidden UPDATE would change."""
    from apps.billing import models as billing_models
    from apps.ledger import models as ledger_models
    from apps.payments import models as pay_models

    lines = sorted(
        (str(r.pk), str(r.amount), r.side, str(r.journal_entry_id))
        for r in ledger_models.JournalLine.objects.filter(account_id=account_id)
    )
    payments = sorted(
        (str(p.pk), str(p.amount), p.status)
        for p in pay_models.Payment.objects.filter(account_id=account_id)
    )
    invoices = sorted(
        (str(i.pk), str(i.total), i.status)
        for i in billing_models.Invoice.objects.filter(account_id=account_id)
    )
    return lines, payments, invoices


# ═══════════════════════════════════════════════════════════════════════════
# B1 · THE TWO NEW LEVELS AND THE OFFER
# ═══════════════════════════════════════════════════════════════════════════
def test_name_and_phone_is_the_third_level_with_what_he_owes(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
    search = _search(dana, brazos, {"kind": "person", "name": VIKTOR, "phone": PHONE})
    assert search["result"] == "name_phone"
    (row,) = search["customers"]
    assert row["customer_no"] == viktor.customer_no
    assert row["verdict"] == "name_phone"
    assert sorted(row["agreed"]) == ["name", "phone"]
    assert Decimal(row["accounts"]["outstanding_total"]) == OWED
    assert row["accounts"]["rows"][0]["account_no"] == account["account_no"]
    assert row["reopen"] is None  # no unit named, no offer


def test_the_units_last_occupant_is_found_on_his_name_alone(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
    body = {"kind": "person", "name": VIKTOR, "phone": NEW_PHONE}
    # Without the unit, a name alone is still nobody (the 2026-10-05 rule).
    assert _search(dana, brazos, body)["result"] == "new"

    search = _search(dana, brazos, {**body, "unit_id": str(unit["id"])})
    assert search["result"] == "last_occupant"
    (row,) = search["customers"]
    assert row["verdict"] == "last_occupant"
    assert row["last_occupant"] is True
    assert row["agreed"] == ["name"]
    offer = row["reopen"]
    assert offer["account_no"] == account["account_no"]
    assert offer["eligible"] is True and offer["reason"] is None
    assert offer["closed_at"] == "2026-07-31"
    assert offer["outstanding"] == "84.2000"
    assert offer["within_years"] == 5


def test_step_one_history_shows_what_the_last_account_owes(brazos, dana):
    """F1 — the unit card's History names the last account and what it owes."""
    from apps.customers import move_in_unit_read

    with tenant_ctx(brazos):
        unit, account, _viktor = _viktor_moved_out(dana, brazos)
        previous = move_in_unit_read.unit_facts(unit["id"])["history"]["previous"]
    assert previous["account_no"] == account["account_no"]
    assert previous["closed_at"] == "2026-07-31"
    assert previous["outstanding"] == "84.2000"
    assert previous["currency"] == "USD"


def test_a_stranger_on_the_unit_is_not_the_last_occupant(brazos, dana):
    with tenant_ctx(brazos):
        unit, _account, _viktor = _viktor_moved_out(dana, brazos)
    search = _search(
        dana, brazos, {"kind": "person", "name": "Someone Else", "unit_id": str(unit["id"])}
    )
    assert search["result"] is None  # a name alone that matches nobody is no question


# ═══════════════════════════════════════════════════════════════════════════
# B2 + B3 · REOPEN AT COMPLETE
# ═══════════════════════════════════════════════════════════════════════════
def test_carry_reopens_the_same_account_and_leaves_the_balance_on_it(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
        old_agreements = list(
            customers_models.ServiceAgreement.objects.filter(account_id=account["id"]).values_list(
                "id", "started_on", "ended_on"
            )
        )
        assert old_agreements and all(row[2] is not None for row in old_agreements)
        before_money = _money_rows(account["id"])
        assert before_money[0], "the opening entry must be there to compare"
        accounts_before = customers_models.Account.objects.count()
        audit_rows.clear()

        result = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            _payload(viktor, reopen_account_id=account["id"], reopen_balance="carry"),
        )

        assert result["id"] == str(account["id"])
        assert result["account_no"] == account["account_no"]
        assert customers_models.Account.objects.count() == accounts_before  # no new row
        row = customers_models.Account.objects.select_related("status").get(pk=account["id"])
        assert row.closed_at is None
        assert row.opened_at == date(2026, 9, 1)
        assert row.status.code == "active"
        # Old agreements untouched; one NEW agreement from the move-in date.
        for pk, started, ended in old_agreements:
            again = customers_models.ServiceAgreement.objects.get(pk=pk)
            assert (again.started_on, again.ended_on) == (started, ended)
        new = customers_models.ServiceAgreement.objects.filter(
            account_id=account["id"], ended_on__isnull=True
        )
        assert [a.started_on for a in new] == [date(2026, 9, 1)]
        # The balance is still the account's, on the books.
        assert move_in_reopen.outstanding(account["id"])[0] == OWED
        assert _money_rows(account["id"]) == before_money
        # The choice and the figure on the move-in.
        reopening = MoveInReopening.objects.get(move_record_id=result["move_record_id"])
        assert reopening.balance_choice == "carry"
        assert reopening.balance_at_complete == OWED
        assert reopening.previous_closed_at == date(2026, 7, 31)
        assert result["reopened"]["balance_choice"] == "carry"
        assert result["reopened"]["balance_at_complete"] == "84.2000"
        record = moves.MoveRecord.objects.get(pk=result["move_record_id"])
        assert str(record.account_id) == str(account["id"])
        mine = [r for r in audit_rows if str(r.get("entity_id")) == str(account["id"])]
        actions = {r.get("action") for r in mine}
        assert {"account.reopened", "move_in.reopen_balance", "account.moved_in"} <= actions
        (reopened_audit,) = [r for r in mine if r.get("action") == "account.reopened"]
        assert reopened_audit["before"]["closed_at"] == "2026-07-31"
        assert reopened_audit["after"]["closed_at"] is None
        (choice_audit,) = [r for r in mine if r.get("action") == "move_in.reopen_balance"]
        assert choice_audit["after"]["balance_choice"] == "carry"
        assert choice_audit["after"]["balance_at_complete"] == "84.2000"


def test_pay_first_refuses_until_the_balance_is_paid(brazos, dana):
    from apps.payments import services as payments_services

    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana,
                unit["id"],
                _payload(viktor, reopen_account_id=account["id"], reopen_balance="pay_first"),
            )
        assert refused.value.message_key == "customers.moveIn.reopen.payFirst"
        assert refused.value.params["amount"] == "84.2000"
        assert customers_models.Account.objects.get(pk=account["id"]).closed_at is not None

        paid = payments_services.record_payment(
            dana,
            account_id=account["id"],
            amount=Decimal("84.20"),
            posted_at=datetime(2026, 8, 30, 15, tzinfo=dt_timezone.utc),
            cleared_at=datetime(2026, 8, 30, 15, tzinfo=dt_timezone.utc),
            method_code="check",
            confirmation="2207",
            idempotency_reference=uuid.uuid4(),
        )
        # The fixture bill has no lines the allocator can class, so the $84.20
        # is CARRIED as credit and AR stays $84.20 — what is owed is net of it
        # (decision log 2026-10-13, REOPEN judgment (b)).
        assert paid.posted_to_ledger is True
        assert move_in_reopen.outstanding(account["id"])[0] == Decimal("0")

        result = customers_services.move_in_to_unit(
            dana,
            unit["id"],
            _payload(viktor, reopen_account_id=account["id"], reopen_balance="pay_first"),
        )
        assert result["account_no"] == account["account_no"]
        reopening = MoveInReopening.objects.get(move_record_id=result["move_record_id"])
        assert reopening.balance_choice == "pay_first"
        assert reopening.balance_at_complete == Decimal("0")


def test_owing_with_no_choice_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos)
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana, unit["id"], _payload(viktor, reopen_account_id=account["id"])
            )
        assert refused.value.message_key == "customers.moveIn.reopen.choiceRequired"


def test_nothing_owed_reopens_with_no_choice(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos, owed=None)
        result = customers_services.move_in_to_unit(
            dana, unit["id"], _payload(viktor, reopen_account_id=account["id"])
        )
        reopening = MoveInReopening.objects.get(move_record_id=result["move_record_id"])
        assert reopening.balance_choice is None
        assert reopening.balance_at_complete == Decimal("0")


def test_another_unit_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        _unit, account, viktor = _viktor_moved_out(dana, brazos)
        _p, other = _served_unit(dana, brazos, label="SCW-U-099", address="99 Other Way")
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana,
                other["id"],
                _payload(viktor, reopen_account_id=account["id"], reopen_balance="carry"),
            )
        assert refused.value.message_key == "customers.moveIn.reopen.otherUnit"
        assert customers_models.Account.objects.get(pk=account["id"]).closed_at is not None


def test_someone_elses_account_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, _viktor = _viktor_moved_out(dana, brazos)
        stranger = customers_models.Customer.objects.create(
            tenant=brazos, kind="person", display_name="Other Person", customer_no="C-99901"
        )
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana,
                unit["id"],
                _payload(stranger, reopen_account_id=account["id"], reopen_balance="carry"),
            )
        assert refused.value.message_key == "customers.moveIn.reopen.otherCustomer"


def test_closed_more_than_five_years_ago_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(
            dana, brazos, owed=None, opened="2019-06-01", closed="2020-01-31"
        )
        assert move_in_reopen.offer_for(unit["id"], viktor.id)["reason"] == "too_old"
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana, unit["id"], _payload(viktor, reopen_account_id=account["id"])
            )
        assert refused.value.message_key == "customers.moveIn.reopen.tooOld"


def test_the_setting_moves_the_window(brazos, dana):
    """Q4 — *"keep 5 years right now"*: a tenant setting, read live."""
    from apps.tenancy import services as tenancy_services

    with tenant_ctx(brazos):
        unit, _account, viktor = _viktor_moved_out(
            dana, brazos, owed=None, opened="2019-06-01", closed="2020-01-31"
        )
        assert move_in_reopen.within_years() == 5
        tenancy_services.save_settings_family(dana, "billing-defaults", {"reopen_within_years": 10})
        assert move_in_reopen.within_years() == 10
        assert move_in_reopen.offer_for(unit["id"], viktor.id)["eligible"] is True


def test_an_occupied_unit_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos, owed=None)
        customers_services.move_in_to_unit(
            dana,
            unit["id"],
            {
                "account_type": "residential",
                "opened_at": "2026-08-15",
                "contact": {"full_name": "Next, Tenant"},
                "customer": identity_fixtures.customer_block(
                    "Next, Tenant", account_type="residential", phone="512-555-0177"
                ),
            },
        )
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana, unit["id"], _payload(viktor, reopen_account_id=account["id"])
            )
        assert refused.value.message_key == "customers.account.unit_already_occupied"


def test_a_start_on_the_day_it_closed_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        unit, account, viktor = _viktor_moved_out(dana, brazos, owed=None)
        with pytest.raises(errors.BizError) as refused:
            customers_services.move_in_to_unit(
                dana,
                unit["id"],
                _payload(viktor, opened_at="2026-07-31", reopen_account_id=account["id"]),
            )
        assert refused.value.message_key == "customers.account.start_on_prior_move_day"


def test_a_choice_without_an_account_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        unit, _account, viktor = _viktor_moved_out(dana, brazos, owed=None)
        with pytest.raises(errors.ValidationError):
            customers_services.move_in_to_unit(
                dana, unit["id"], _payload(viktor, reopen_balance="carry")
            )
