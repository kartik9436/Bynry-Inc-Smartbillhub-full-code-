"""ONE CHEQUE, SEVERAL BILLS — the tester's own accounts, through the two DOORS.

Lane PAY-H · `DEF-PAY-10706` (tester L1-08) · `DEF-PAY-7642` · `DEF-PAY-6322` ·
BR-PAY-1126..1130 · PO ruling 2026-09-01 (a master may always pay a unit's
bill on its own premises) · PO ruling 2026-10-30 (*"Rest we will fix"*, L1-08
*"with the till check"*).

WHAT THIS FILE PINS
-------------------
The service has been right since 2026-09-03 (`test_cr059_cs12_*`,
`test_cr059_cs27_*`). What was wrong is that nobody could REACH it, and the two
doors that reach it took a cheque with no till open. So every case here goes
through `POST /accounts/{id}/premises-payments` or `POST /customers/{id}/payments`
— the routes the new *Pay for…* mode of Record a payment calls — with the
tester's own account numbers:

  * **Raccoon River** (master `AC-2026-00621`) pays `AC-2026-00622`'s $96.40
    bill → the bill is paid, the master's balance does not move.
  * **Grand Vista** (master `AC-2026-00618`) pays units 101–108 in one cheque
    of $1,003.60 → eight payments, eight balanced entries.
  * **Boulder Creek Dental** — one cheque of $1,234.50 split across ten
    accounts, summing exactly → posts; **$0.01 off → the whole cheque refused**
    and nothing written.
  * **A leftover is the MASTER's credit**, never a tenant's.
  * **No open till → a cheque is refused** at both doors, exactly as on the
    single-account form; a card is not; a cheque WITH a till names that till on
    every part (`DEF-PAY-6322` — the drawer is counted by payment rows).

WHAT WOULD MAKE THESE PASS WRONGLY (hard-won law 7, habit 2)
-----------------------------------------------------------
* *No till → refused* passes on a door that refuses everything — so a card with
  no till, and a cheque WITH a till, are asserted to succeed.
* *The till is named* passes if only the first part carries it — so EVERY part
  is asserted.
* *Balanced* passes on a ledger whose debits and credits both sum to the cheque
  while one entry is lopsided — so each entry is balanced on its own.

RED FIRST: with the two `_open_till` calls removed from `tenders_api.py` the
three till cases fail (201 where 422 is expected, and `counter_session_id`
None on every part). Recorded in the lane report.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone as django_timezone

from apps.customers import models as customer_models
from apps.customers import services as customer_services
from apps.metering import services as metering_services
from apps.payments import counters, models, tender_models, tenders_api
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_us_pay_020_023_bank_rec import an_account_of
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

ISSUED_ON = date(2026, 10, 9)
OPENED = date(2026, 10, 1)
POSTED = "2026-10-21"

#: Grand Vista's eight flats, 101–108, and what each owes. Sum 1,003.60.
GRAND_VISTA = (
    ("101", Decimal("112.40")),
    ("102", Decimal("98.75")),
    ("103", Decimal("140.10")),
    ("104", Decimal("87.35")),
    ("105", Decimal("131.00")),
    ("106", Decimal("119.90")),
    ("107", Decimal("176.60")),
    ("108", Decimal("137.50")),
)
GRAND_VISTA_TOTAL = sum((owed for _, owed in GRAND_VISTA), Decimal("0"))

#: Boulder Creek Dental's ten accounts. Sum 1,234.50.
BOULDER_CREEK = (
    Decimal("101.10"),
    Decimal("99.90"),
    Decimal("150.00"),
    Decimal("75.25"),
    Decimal("130.75"),
    Decimal("88.40"),
    Decimal("142.60"),
    Decimal("110.00"),
    Decimal("204.30"),
    Decimal("132.20"),
)
BOULDER_CREEK_TOTAL = sum(BOULDER_CREEK, Decimal("0"))


# ── the world ──────────────────────────────────────────────────────────────


@pytest.fixture()
def centre(brazos):
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos, slug="pay-h-window", name="Main office", address="1 Bend Rd"
        )


def _open_till(actor, centre):
    with tenant_ctx(centre.tenant):
        return counters.open_counter(
            actor,
            service_centre_id=centre.pk,
            opening_float=Decimal("0.0000"),
            opened_at=django_timezone.now(),
        )


def _renumber(account, account_no):
    account.account_no = account_no
    account.save(update_fields=["account_no"])
    return account


def _tenant_on(actor, unit, *, name, phone):
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": name},
            "customer": {"display_name": name, "kind": "person", "identity": {"phone": phone}},
            "addresses": [{"kind": "mailing", "line1": "1 Elm", "city": "Katy", "state": "TX"}],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


def a_master_with_let_units(actor, tenant, *, name, master_no, tax_id, units):
    """A premises, its declared owner-master, and one let unit per `units` row.

    `units` is `(label, account_no, owed)`; every unit's tenant has one issued
    bill for `owed`. Built exactly as `test_cr059_cs27` builds CS-27's block —
    homes first (BR-CUS-1114), then the master, then the owner link.
    """
    from apps.metering import premises_owners

    plan = make_plan(tenant, name=f"{name} water", services=["water"])
    premises = make_premises(
        actor,
        address_line=f"{name} 6405",
        premises_type="apartment_complex",
        owner_manager=name,
        services_available=["water"],
    )
    homes = []
    labels = [label for label, _no, _owed in units]
    if len(labels) < 2:  # BR-CUS-1114 — a master needs a building of two homes
        labels = labels + ["Vacant"]
    for label in labels:
        home = make_unit(actor, premises["id"], label=label, services=["water"])
        metering_services.assign_unit_plan(
            actor, home["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        homes.append(home)
    created = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            "customer": {"display_name": name, "kind": "company", "identity": {"tax_id": tax_id}},
        },
    )
    master = _renumber(customer_models.Account.objects.get(pk=created["id"]), master_no)
    premises_owners.link_owner_master_account(actor, premises["owner"]["id"], master.id)
    tenants = []
    for index, (label, account_no, owed) in enumerate(units):
        account = _tenant_on(
            actor, homes[index], name=f"Tenant {label}", phone=f"+1 (515) 555-{1000 + index:04d}"
        )
        _renumber(account, account_no)
        an_issued_bill(
            tenant, account, number=f"BL-2610-{account_no[-5:]}", total=owed, issued_on=ISSUED_ON
        )
        tenants.append(account)
    return master, tenants


def boulder_creek_dental(actor, tenant):
    """One customer holding ten accounts, one open bill each."""
    accounts = [an_account(actor, tenant, account_no="AC-2026-00700")] + [
        an_account_of(actor, tenant, service="water") for _ in range(9)
    ]
    for index, account in enumerate(accounts[1:], start=1):
        _renumber(account, f"AC-2026-{700 + index:05d}")
    customer = customer_models.Customer.objects.create(
        tenant=tenant, customer_no="C-00700", display_name="Boulder Creek Dental"
    )
    for account, owed in zip(accounts, BOULDER_CREEK, strict=True):
        customer_models.CustomerAccount.objects.create(
            tenant=tenant, customer=customer, account=account
        )
        an_issued_bill(
            tenant,
            account,
            number=f"BL-2610-{account.account_no[-5:]}",
            total=owed,
            issued_on=ISSUED_ON,
        )
    return customer, accounts


# ── the doors ──────────────────────────────────────────────────────────────


def _body(parts, *, total, method="check", reference="9001"):
    return {
        "amount": str(total),
        "posted_at": POSTED,
        "method": method,
        "reference": reference,
        "idempotency_key": str(uuid.uuid4()),
        "parts": [
            {"account_id": str(account.pk), "amount": str(amount)} for account, amount in parts
        ],
    }


def pay_for_units(actor, tenant, master, parts, **kwargs):
    return api_call(
        tenders_api.premises_payments,
        "post",
        f"/api/brazos/accounts/{master.pk}/premises-payments",
        user=actor.user,
        role=actor.role,
        tenant=tenant,
        data=_body(parts, **kwargs),
        account_id=str(master.pk),
    )


def pay_for_customer(actor, tenant, customer, parts, **kwargs):
    return api_call(
        tenders_api.customer_payments,
        "post",
        f"/api/brazos/customers/{customer.pk}/payments",
        user=actor.user,
        role=actor.role,
        tenant=tenant,
        data=_body(parts, **kwargs),
        customer_id=str(customer.pk),
    )


def _balance_owed(account):
    from apps.payments import billing_seam

    return sum(
        (i.balance for i in billing_seam.open_invoices_for_account(account.id).invoices),
        Decimal("0"),
    )


def _each_entry_is_balanced(tenant):
    """Per JOURNAL ENTRY, debits == credits — not merely in total."""
    from apps.ledger import models as ledger_models

    sums: dict = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for entry_id, side, amount in ledger_models.JournalLine.objects.filter(
        tenant=tenant, journal_entry__status=ledger_models.JE_POSTED
    ).values_list("journal_entry_id", "side", "amount"):
        sums[entry_id][0 if side == "debit" else 1] += amount
    for entry_id, (debit, credit) in sums.items():
        assert debit == credit, f"journal entry {entry_id}: {debit} debit vs {credit} credit"
    return len(sums)


# ── the cases ──────────────────────────────────────────────────────────────


def test_raccoon_river_pays_its_tenants_bill_and_the_bill_is_paid(brazos, dana, centre):
    """L1-08's own screenshot: the master could not be offered the tenant's bill."""
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        master, (tenant,) = a_master_with_let_units(
            dana,
            brazos,
            name="Raccoon River Holdings",
            master_no="AC-2026-00621",
            tax_id="42-1000621",
            units=(("1A", "AC-2026-00622", Decimal("96.40")),),
        )
    response = pay_for_units(dana, brazos, master, [(tenant, Decimal("96.40"))], total="96.40")
    assert response.status_code == 201, response.data
    assert response.data["scope"] == tender_models.TENDER_SCOPE_PREMISES
    with tenant_ctx(brazos):
        assert _balance_owed(tenant) == Decimal("0")
        assert not models.Payment.objects.filter(account_id=master.id).exists()
        assert _each_entry_is_balanced(brazos) == 1


def test_grand_vista_pays_units_101_to_108_in_one_cheque(brazos, dana, centre):
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        master, tenants = a_master_with_let_units(
            dana,
            brazos,
            name="Grand Vista Properties LLC",
            master_no="AC-2026-00618",
            tax_id="42-1000618",
            units=tuple(
                (label, f"AC-2026-{619 + i + 100:05d}", owed)
                for i, (label, owed) in enumerate(GRAND_VISTA)
            ),
        )
    parts = [(t, owed) for t, (_label, owed) in zip(tenants, GRAND_VISTA, strict=True)]
    response = pay_for_units(dana, brazos, master, parts, total=GRAND_VISTA_TOTAL)
    assert response.status_code == 201, response.data
    assert response.data["part_count"] == 8
    assert Decimal(response.data["amount"]) == Decimal("1003.60")
    with tenant_ctx(brazos):
        assert all(_balance_owed(t) == Decimal("0") for t in tenants)
        assert models.Payment.objects.filter(tender_id=response.data["tender_id"]).count() == 8
        # One balanced pair per account paid — eight entries, each balanced.
        assert _each_entry_is_balanced(brazos) == 8


def test_boulder_creek_dental_one_cheque_across_ten_accounts_posts(brazos, dana, centre):
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        customer, accounts = boulder_creek_dental(dana, brazos)
    parts = list(zip(accounts, BOULDER_CREEK, strict=True))
    response = pay_for_customer(dana, brazos, customer, parts, total=BOULDER_CREEK_TOTAL)
    assert response.status_code == 201, response.data
    assert response.data["part_count"] == 10
    with tenant_ctx(brazos):
        recorded = models.Payment.objects.filter(tender_id=response.data["tender_id"])
        assert sum(p.amount for p in recorded) == Decimal("1234.50")
        assert all(_balance_owed(a) == Decimal("0") for a in accounts)
        assert _each_entry_is_balanced(brazos) == 10


def test_a_cent_off_and_the_whole_cheque_is_refused(brazos, dana, centre):
    """$1,234.49 of rows under a $1,234.50 cheque: nothing is written at all."""
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        customer, accounts = boulder_creek_dental(dana, brazos)
    amounts = list(BOULDER_CREEK)
    amounts[-1] -= Decimal("0.01")
    response = pay_for_customer(
        dana, brazos, customer, list(zip(accounts, amounts, strict=True)), total="1234.50"
    )
    assert response.status_code == 422, response.data
    assert response.data["message_key"] == "payments.tender.refused"
    assert "0.01" in str(response.data)
    with tenant_ctx(brazos):
        assert models.Payment.objects.count() == 0
        assert tender_models.PaymentTender.objects.count() == 0


def test_the_leftover_is_the_masters_credit_never_a_tenants(brazos, dana, centre):
    """$120.00 for a $96.40 bill: $23.60 lands on the MASTER, and the same
    $23.60 typed onto the tenant is refused whole (BR-PAY-1130)."""
    _open_till(dana, centre)
    with tenant_ctx(brazos):
        master, (tenant,) = a_master_with_let_units(
            dana,
            brazos,
            name="Raccoon River Holdings",
            master_no="AC-2026-00621",
            tax_id="42-1000621",
            units=(("1A", "AC-2026-00622", Decimal("96.40")),),
        )
    refused = pay_for_units(dana, brazos, master, [(tenant, Decimal("120.00"))], total="120.00")
    assert refused.status_code == 422, refused.data
    assert "23.60" in str(refused.data)

    response = pay_for_units(
        dana,
        brazos,
        master,
        [(tenant, Decimal("96.40")), (master, Decimal("23.60"))],
        total="120.00",
    )
    assert response.status_code == 201, response.data
    with tenant_ctx(brazos):
        on_master = models.Payment.objects.get(account_id=master.id)
        assert on_master.amount == Decimal("23.60")
        assert _balance_owed(tenant) == Decimal("0")
    assert Decimal(response.data["payments"][1]["credit_carried"]) == Decimal("23.60")


@pytest.mark.parametrize("door", ["premises", "customer"])
def test_a_cheque_with_no_open_till_is_refused_at_both_doors(brazos, dana, door):
    """DEF-PAY-7642 — the same sentence as the single-account form."""
    with tenant_ctx(brazos):
        if door == "premises":
            master, (tenant,) = a_master_with_let_units(
                dana,
                brazos,
                name="Raccoon River Holdings",
                master_no="AC-2026-00621",
                tax_id="42-1000621",
                units=(("1A", "AC-2026-00622", Decimal("96.40")),),
            )
        else:
            customer, accounts = boulder_creek_dental(dana, brazos)
    if door == "premises":
        response = pay_for_units(dana, brazos, master, [(tenant, Decimal("96.40"))], total="96.40")
    else:
        response = pay_for_customer(
            dana,
            brazos,
            customer,
            list(zip(accounts, BOULDER_CREEK, strict=True)),
            total=BOULDER_CREEK_TOTAL,
        )
    assert response.status_code == 422, response.data
    assert response.data["message_key"] == "payments.counter.till_required"
    with tenant_ctx(brazos):
        assert models.Payment.objects.count() == 0
        assert tender_models.PaymentTender.objects.count() == 0


def test_a_card_needs_no_till_and_a_cheque_names_the_till_on_every_part(brazos, dana, centre):
    """The false-pass guards: the door does not refuse everything, and the till
    reaches EVERY part (DEF-PAY-6322), not only the first."""
    with tenant_ctx(brazos):
        customer, accounts = boulder_creek_dental(dana, brazos)
    parts = list(zip(accounts[:2], BOULDER_CREEK[:2], strict=True))
    card = pay_for_customer(dana, brazos, customer, parts, total="201.00", method="card")
    assert card.status_code == 201, card.data

    till = _open_till(dana, centre)
    rest = list(zip(accounts[2:], BOULDER_CREEK[2:], strict=True))
    cheque = pay_for_customer(
        dana, brazos, customer, rest, total=str(BOULDER_CREEK_TOTAL - Decimal("201.00"))
    )
    assert cheque.status_code == 201, cheque.data
    with tenant_ctx(brazos):
        named = set(
            models.Payment.objects.filter(tender_id=cheque.data["tender_id"]).values_list(
                "counter_session_id", flat=True
            )
        )
        assert named == {till.session.pk}
