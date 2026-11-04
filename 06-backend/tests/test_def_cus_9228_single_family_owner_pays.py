# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-9228 — a single-family New Connection could not carry a
#           connection charge (step 4: "No master account to bill").
# Ruling:   decision log 2026-10-02, "SEVEN PO ANSWERS IN ONE MESSAGE", item 1:
#           *"A. The owner asked for the work, so the owner pays. With B, the
#           bill could land on a tenant who moves in later, or never go out at
#           all."* — at Create a single-family (Regular-type) build opens the
#           OWNER's own regular account, Pending → Active on activation, and the
#           connection charges are billed to it.
# Rules:    BR-MET-113 (charges tagged to the owner's account number) ·
#           BR-MET-1187 (the books entry and the payment in the Create act) ·
#           BR-CUS-1114 (no master account on a single-family home — unchanged) ·
#           BR-CUS-017 (one occupying account per unit) · CLAUDE.md hard rules
#           2, 4, 5, 7 · hard-won law 14 (the money cases run on PostgreSQL).
# ───────────────────────────────────────────────────────
"""**Maria, single-family at 14 Oak St: $90 connection + $30 inspection = $120,
billed to Maria's own account at Create.**

The worked case the PO was shown, built through the wizard's one press
(`commit_new_connect`) exactly as the browser sends it — a NEW address of type
`single_family`, one unit, the owner named, two charge lines and a card
payment. CONN is the tenant's seeded $45.00 counted on 2 meters; INSPECT is
$30.00 once per premise: 2 × 45 + 1 × 30 = **$120.00**.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * an invoice raised against SOME account — each case reads the invoice's
    `account_id` back and compares it with the build's `owner_account_id`, and
    that account's own row says `kind='regular'` on Maria's unit;
  * a payment that exists but met no bill — the allocation is read through
    `settled_against_bills`, the read the build record's *Taken* tile uses;
  * a pending account read from the RESPONSE — every status is read from its
    row;
  * activation passing because nothing was pending — the pending status is
    asserted first.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import connection_activation as activation
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import seams as metering_seams
from apps.payments import models as payment_models
from core import errors

from tests.isolation_helpers import requires_postgres
from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    EQUIPMENT_TYPE,
    SIZES,
    _ctx,
    _plan,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam
from tests.test_us_met_helpers import audit_rows, staff_actor  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db

MARIA = {
    "name": "Maria Alvarez",
    "email": "maria@oak.test",
    "phone": "(512) 555-0114",
    "party_kind": "person",
    "identity": {"ssn": "412-55-0114"},
    "account_type": "residential",
    # ⊕ `CR-164-BRC10` wave 4 (PO 2026-10-03, ruling C) — Maria LIVES at 14
    # Oak St in this file's worked case, so her account holds the home. With
    # no owner type the account would open billing only.
    "kind": "owner_occupier",
}
#: 2 × $45.00 + 1 × $30.00 — the seeded catalogue's prices, transcribed so a
#: catalogue that moves goes RED rather than agreeing with itself.
LINES = [
    {"charge_code": "CONN", "quantity": "2", "basis": "per meter"},
    {"charge_code": "INSPECT", "quantity": "1", "basis": "per premise"},
]
TOTAL = Decimal("120.0000")
POSTED = "2026-10-02"


def _maria_builds(clerk, tenant, *, address="14 Oak St", labels=("Unit 1",), owner=MARIA, **extra):
    plan = _plan(tenant)
    services = ("battery", "solar")
    payload = {
        "premises": {
            "id": None,
            "address": address,
            "city": "Austin",
            "state": "TX",
            "postal_code": "78701",
            "premise_type": "single_family",
            "parcel_ref": None,
            "read_route": None,
            "services_available": list(services),
        },
        "mode": "our_crew",
        "scope": "new_premise",
        "units_prefix": "Unit",
        "target_activation": None,
        "service_request_id": None,
        "units": [{"label": label, "is_common_area": False} for label in labels],
        "meters": [],
        "unit_services": [
            {
                "unit_label": label,
                "service": code,
                "equipment": [
                    {"type": EQUIPMENT_TYPE[code], "size_class": SIZES[code], "count": 1}
                ],
            }
            for label in labels
            for code in services
        ],
        "plan_assignments": [{"unit_label": label, "tariff_id": str(plan.id)} for label in labels],
        "create_owner_account": owner is not None,
        "owner": owner or {},
        "quote_total": None,
        "occupancy": "vacant_service_off",
        "work_orders": [],
        "quote_lines": LINES,
        "quote_payer": "owner_account",
        "quote_due_days": 30,
        "quote_posting_date": POSTED,
    }
    payload.update(extra)
    with _ctx(tenant):
        return w6.commit_new_connect(clerk, payload)


def _owner_account(tenant, connection_id):
    with _ctx(tenant):
        connection = work_tables.Connection.objects.get(pk=connection_id)
        if connection.owner_account_id is None:
            return None
        return customers_models.Account.objects.select_related("status").get(
            pk=connection.owner_account_id
        )


def _the_unit(tenant, connection_id, label="Unit 1"):
    with _ctx(tenant):
        connection = work_tables.Connection.objects.get(pk=connection_id)
        return metering_models.Unit.objects.get(premises_id=connection.premises_id, label=label)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · AT CREATE — the owner's own REGULAR account, Pending, billed $120.00
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_maria_is_billed_120_on_her_own_regular_account_at_create(cedar, clerk, audit_rows):
    built = _maria_builds(
        clerk,
        cedar,
        payment_method="card",
        payment_amount="120.0000",
        payment_date=POSTED,
        payment_cleared_date=POSTED,
        payment_reference="AUTH-0114",
    )
    account = _owner_account(cedar, built["id"])
    assert account is not None, "a single-family build with an owner opens the owner's account"
    assert account.kind == "regular"
    assert str(account.unit_id) == str(_the_unit(cedar, built["id"]).id)
    # Created PENDING, exactly as the master account is (CR-162-BRC10 Q1).
    assert account.status.code == customers_services.PENDING_STATUS_CODE
    with _ctx(cedar):
        # BR-CUS-1114 is untouched: a single-family home has NO master account.
        assert not customers_models.Account.objects.filter(kind="master").exists()
        invoice = billing_models.Invoice.objects.get(
            invoice_no=built["manifest"]["one_time_charge_invoice_no"]
        )
        assert str(invoice.account_id) == str(account.pk), "the charges went to Maria's account"
        assert invoice.total == TOTAL
        assert Decimal(built["manifest"]["one_time_charges"]) == TOTAL
        payment = payment_models.Payment.objects.get(
            payment_no=built["manifest"]["one_time_charge_payment_no"]
        )
        assert str(payment.account_id) == str(account.pk)
        assert payment.amount == TOTAL
        settled = metering_seams.settled_against_bills([invoice.pk])
        assert settled[str(invoice.pk)] == TOTAL, "the $120.00 met THIS bill"
        # Maria is a customer — the review's *Customer record 1* is now true.
        assert customers_models.CustomerAccount.objects.filter(account_id=account.pk).exists()
    assert built["manifest"]["customers"] == 1
    assert any(row.get("action") == "connection.owner_account_created" for row in audit_rows)


def test_without_charges_the_owners_account_still_opens_pending(cedar, clerk):
    """Any vendor: the account half needs no money to be proved."""
    built = _maria_builds(clerk, cedar, quote_lines=[], quote_due_days=None)
    account = _owner_account(cedar, built["id"])
    assert account is not None and account.kind == "regular"
    assert account.status.code == customers_services.PENDING_STATUS_CODE


def test_two_homes_on_a_single_family_type_still_get_no_master(cedar, clerk):
    """`BR-CUS-1114` is unchanged: the regular path is ONE home's. Two units on
    a single-family type with an owner are refused by the master rule, by name,
    exactly as before the ruling."""
    with pytest.raises(errors.BizError) as refusal:
        _maria_builds(
            clerk,
            cedar,
            address="7 Wren Lane",
            labels=("Unit 1", "Unit 2"),
            quote_lines=[],
            quote_due_days=None,
        )
    assert refusal.value.message_key == "customers.account.master_not_for_single_family"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · ON APPROVAL — Pending → Active, and Maria holds her home
# ═══════════════════════════════════════════════════════════════════════════
def test_approval_makes_marias_account_active(cedar, clerk):
    built = _maria_builds(clerk, cedar, quote_lines=[], quote_due_days=None)
    cid = built["id"]
    with _ctx(cedar):
        ready = [row["id"] for row in activation.activation_readiness(cid)["rows"]]
        answer = activation.activate(clerk, cid, service_ids=ready)
    account = _owner_account(cedar, cid)
    assert account.status.code == "active"
    assert answer["master_account"]["status"] == "active"
    with _ctx(cedar):
        from apps.customers import selectors as customers_selectors

        occupying = list(customers_selectors.occupying_accounts_for_unit(account.unit_id))
        assert [str(one.pk) for one in occupying] == [str(account.pk)]
        # A second approval writes nothing more.
        again = customers_services.activate_pending_master_account(clerk, account.pk)
        assert again["already_active"] is True


def test_an_occupant_who_moved_in_before_approval_keeps_the_home(cedar, clerk):
    """Move-in is unchanged: an occupant who moved in while the build was
    pending holds the unit, and approval leaves Maria's account Pending rather
    than refusing the whole activation (BR-CUS-017 — one occupying account)."""
    from tests.test_cr162_new_connection_lifecycle import _maria_moves_in

    built = _maria_builds(clerk, cedar, quote_lines=[], quote_due_days=None)
    cid = built["id"]
    unit = _the_unit(cedar, cid)
    moved = _maria_moves_in(cedar, clerk, unit.id, "2026-10-05")
    assert moved.status_code == 201, moved.data
    with _ctx(cedar):
        ready = [row["id"] for row in activation.activation_readiness(cid)["rows"]]
        answer = activation.activate(clerk, cid, service_ids=ready)
    owner = _owner_account(cedar, cid)
    assert owner.status.code == customers_services.PENDING_STATUS_CODE
    assert answer["master_account"]["left_pending"] is True
    with _ctx(cedar):
        occupant = customers_models.Account.objects.select_related("status").get(
            pk=moved.data["id"]
        )
        assert occupant.status.code == "active"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · ADD FEE LATER — the same door, the same payer as the master account's
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
# `DEF-MET-9217` FIXED (2.467.1): this was a STRICT xfail until the fee door
# could bill a Pending owner account; it flipped red on the fix, as designed.
def test_a_fee_added_after_create_goes_to_marias_account(cedar, clerk):
    from apps.metering import connection_fees as fees

    built = _maria_builds(clerk, cedar)
    account = _owner_account(cedar, built["id"])
    with _ctx(cedar):
        added = fees.add_connection_fee(
            clerk,
            built["id"],
            {
                "charge_code": "INSPECT",
                "quantity": "1",
                "basis": "per premise",
                "posting_date": "2026-10-03",
                "due_days": 30,
            },
        )
        invoice = billing_models.Invoice.objects.get(pk=added["invoice_id"])
        assert str(invoice.account_id) == str(account.pk)
        assert invoice.total == Decimal("30.0000")
