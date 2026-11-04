# ── Trace ──────────────────────────────────────────────
# Change:   CR-164-BRC10 wave 4 — a single-family owner's account holds the home
#           after approval ONLY when the owner lives there.
# Ruling:   decision log 2026-10-03, "TWO PO ANSWERS", item 1, verbatim:
#           *"C By owner type: an owner who lives there holds it; a landlord or
#           builder doesn't"*. Shown: Maria owns 14 Oak St; if she is a
#           (Then *"B"*, then *"i dont know yet"* — the owner-occupier half is `OQ-CUS-12785`, OPEN.)
#           landlord, her tenant Jose cannot move in until her account is moved
#           out.
# Rules:    DEF-CUS-9228 (the owner pays the build's charges — unchanged) ·
#           BR-CUS-017 (one occupying account per unit) · BR-CUS-1114 (no master
#           account on a single-family home — unchanged) · CLAUDE.md hard rules
#           2, 4, 7 · hard-won law 14 (money and constraint cases on PostgreSQL).
# ───────────────────────────────────────────────────────
"""**Maria at 14 Oak St, twice: as the owner-occupier and as the landlord.**

Owner-occupier → her account holds Unit 1 after approval (as 2.467.0).
Landlord → her account is BILLING ONLY: it is billed the build's $120.00, names
the premises and no unit, is Active after approval, and Unit 1 stays vacant so
Jose's Move-in opens his own account with nobody moved out.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * a billing-only account that still names the unit but sits Pending — each
    case asserts `unit_id IS NULL` AND `status = active` from the ROW;
  * Jose's Move-in passing because Maria was never activated — her Active
    status is asserted before he moves in;
  * "no base/usage" passing because the run saw no unit at all — the bill-run
    scope is asked for the unit Jose then occupies, and must name Jose alone.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.metering import connection_activation as activation
from apps.metering import connection_record
from apps.metering import connections as w6

from tests.isolation_helpers import requires_postgres
from tests.test_def_cus_9228_single_family_owner_pays import (
    MARIA,
    POSTED,
    TOTAL,
    _maria_builds,
    _owner_account,
    _the_unit,
)
from tests.test_portal_request_to_active import _ctx, cedar, clerk  # noqa: F401 — fixtures
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam
from tests.test_us_met_helpers import audit_rows, staff_actor  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db

OCCUPIER = {**MARIA, "kind": "owner_occupier"}
LANDLORD = {**MARIA, "kind": "landlord"}


def _approve(tenant, clerk, connection_id):
    with _ctx(tenant):
        ready = [row["id"] for row in activation.activation_readiness(connection_id)["rows"]]
        return activation.activate(clerk, connection_id, service_ids=ready)


def _jose_moves_in(tenant, clerk, unit_id):
    from tests.test_portal_request_to_active import _unit_move_in

    return _unit_move_in(
        tenant,
        clerk,
        unit_id,
        {
            "opened_at": "2026-10-10",
            "account_type": "residential",
            "contact": {
                "full_name": "Jose Ruiz",
                "email": "jose@oak.test",
                "phone": "(512) 555-0177",
            },
            "customer": {
                "display_name": "Jose Ruiz",
                "kind": "person",
                "identity": {"phone": "(512) 555-0177"},
            },
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# 0 · THE MAPPING — only an owner who lives there holds the home
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("owner_type", "lives"),
    [
        ("owner_occupier", True),
        ("occupier", True),  # the code builds were stored under before DEF-CUS-9192
        ("Owner_Occupier", True),
        ("landlord", False),
        ("builder", False),
        ("builder_developer", False),
        ("property_manager", False),
        ("hoa", False),
        ("property_owner", False),
        ("our_own_code", False),  # a code the utility added itself
        ("", False),
        (None, False),  # nobody asked — the cheaper mistake is a vacant home
    ],
)
def test_owner_lives_there_by_type(owner_type, lives):
    assert w6.owner_lives_there(owner_type) is lives


# ═══════════════════════════════════════════════════════════════════════════
# 1 · OWNER-OCCUPIER — holds the home (unchanged from 2.467.0)
# ═══════════════════════════════════════════════════════════════════════════
def test_an_owner_occupier_holds_the_home_after_approval(cedar, clerk):
    built = _maria_builds(clerk, cedar, owner=OCCUPIER, quote_lines=[], quote_due_days=None)
    unit = _the_unit(cedar, built["id"])
    account = _owner_account(cedar, built["id"])
    assert str(account.unit_id) == str(unit.id)
    assert account.billing_only is False
    _approve(cedar, clerk, built["id"])
    account = _owner_account(cedar, built["id"])
    assert account.status.code == "active"
    with _ctx(cedar):
        occupying = list(customers_selectors.occupying_accounts_for_unit(unit.id))
        assert [str(one.pk) for one in occupying] == [str(account.pk)]
        role = connection_record._owner_account_role(account.pk)
    assert role == "lives_there"


# ═══════════════════════════════════════════════════════════════════════════
# 2 · LANDLORD — billing only, the home stays vacant, Jose moves straight in
# ═══════════════════════════════════════════════════════════════════════════
def test_a_landlords_account_is_billing_only_and_the_home_stays_vacant(cedar, clerk, audit_rows):
    built = _maria_builds(clerk, cedar, owner=LANDLORD, quote_lines=[], quote_due_days=None)
    unit = _the_unit(cedar, built["id"])
    account = _owner_account(cedar, built["id"])
    assert account is not None and account.kind == "regular"
    assert account.billing_only is True
    assert account.unit_id is None, "a billing-only account holds no unit"
    assert str(account.premises_id) == str(unit.premises_id)
    with _ctx(cedar):
        assert not customers_models.ServiceAgreement.objects.filter(account_id=account.pk).exists()
        assert not customers_models.Account.objects.filter(kind="master").exists()

    answer = _approve(cedar, clerk, built["id"])
    account = _owner_account(cedar, built["id"])
    assert account.status.code == "active"
    assert answer["master_account"]["status"] == "active"
    assert not answer["master_account"].get("left_pending")
    with _ctx(cedar):
        assert list(customers_selectors.occupying_accounts_for_unit(unit.id)) == []
        assert connection_record._owner_account_role(account.pk) == "billing_only"
    created = [
        row for row in audit_rows if row.get("action") == "connection.owner_account_created"
    ]
    assert created and created[-1]["after"]["holds_home"] is False

    # Jose's Move-in: nobody is moved out first.
    moved = _jose_moves_in(cedar, clerk, unit.id)
    assert moved.status_code == 201, moved.data
    # Maria's account stays Active and is never in a bill run's scope for the
    # home — no base, no usage (bill runs scope by unit).
    assert _owner_account(cedar, built["id"]).status.code == "active"
    with _ctx(cedar):
        occupying = list(customers_selectors.occupying_accounts_for_unit(unit.id))
        assert [str(one.pk) for one in occupying] == [str(moved.data["id"])]
        scoped = [str(a.pk) for a in customers_selectors.accounts_for_bill_run([str(unit.id)])]
        assert scoped == [str(moved.data["id"])]


@requires_postgres
def test_a_landlord_is_billed_120_on_the_billing_only_account(cedar, clerk):
    built = _maria_builds(
        clerk,
        cedar,
        owner=LANDLORD,
        payment_method="card",
        payment_amount="120.0000",
        payment_date=POSTED,
        payment_cleared_date=POSTED,
        payment_reference="AUTH-0115",
    )
    account = _owner_account(cedar, built["id"])
    assert account.billing_only is True and account.unit_id is None
    with _ctx(cedar):
        invoice = billing_models.Invoice.objects.get(
            invoice_no=built["manifest"]["one_time_charge_invoice_no"]
        )
        assert str(invoice.account_id) == str(account.pk)
        assert invoice.total == TOTAL == Decimal("120.0000")


@requires_postgres
def test_the_database_refuses_a_billing_only_account_that_names_a_unit(cedar, clerk):
    built = _maria_builds(clerk, cedar, owner=LANDLORD, quote_lines=[], quote_due_days=None)
    unit = _the_unit(cedar, built["id"])
    account = _owner_account(cedar, built["id"])
    with _ctx(cedar):
        with pytest.raises(IntegrityError), transaction.atomic():
            customers_models.Account.objects.filter(pk=account.pk).update(unit_id=unit.id)
        with pytest.raises(IntegrityError), transaction.atomic():
            # …and an ORDINARY regular account still must name a unit.
            customers_models.Account.objects.filter(pk=account.pk).update(billing_only=False)
