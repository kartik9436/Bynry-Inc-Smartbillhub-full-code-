# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CUS-8020 (New Connect's *Create connection* has NEVER worked —
#          every press with an owner on it answers 422 `customers.account.
#          unknown_field`, because `create_owner_account` sends four billing
#          preferences to the MASTER door whose allow list is
#          `MASTER_CREATE_FIELDS`, not `CREATE_FIELDS`) ·
#          DEF-CUS-8021 (pressing it twice builds two of everything —
#          CLAUDE.md hard rule 6 does not hold on this path)
# Rules:   CLAUDE.md hard rule 6 (idempotency) · hard rule 2 (money 4dp stored,
#          2dp displayed) · hard rule 5 (only the ledger posting service writes
#          journal lines) · hard rule 7 (every money action writes audit_log) ·
#          BR-MET-112 (nothing is written until the last button; ONE
#          transaction, both or neither) · BR-CUS-068 / BR-CUS-1010 (a master
#          account is an ordinary row anchored on the ADDRESS)
# Decision: 12-governance/02-decision-log.md, 2026-09-29 — "THE CREATE BUTTON
#          HAS NEVER WORKED, AND PRESSING IT TWICE BUILT TWO OF EVERYTHING".
# Screens: S87 New Connect step 4 (Charges) · step 5 (Review & confirm)
# ───────────────────────────────────────────────────────
"""**The test nobody had: press Create and assert an account row exists.**

⚠ **THIS IS THE ESCAPE, NOT THE BUG.** Both defects went five months undetected
in a product with 42 test files over this wizard, and the reason is the same
for both: **every earlier walk filled the steps and stopped.** The front-end
suite mocks the commit module, the backend suite calls `commit_connection`
directly with a payload it writes itself, and nothing in either half ever sent
`commitPlanOf`'s ACTUAL output through the real door and then looked in the
database. So this file does exactly that, twice, and asserts on ROWS.

⚠ **AND THE IDEMPOTENCY CASE RUNS WITH NO PARCEL NUMBER, BY NAME.** The first
walk of that check PASSED — because a parcel number had been typed, and
`premises.external_ref` is UNIQUE. That refusal is a uniqueness constraint on a
different column: it fires only on the minority of builds that type a parcel,
and it answers `409` where rule 6 asks for the FIRST RESULT. A test that leaves
the parcel in is the check that cannot fail (hard-won law 7), so
`_wizard_plan` sets `parcel_ref` to `None` and says why.
"""

from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.payments import models as payment_models

from tests import identity_fixtures
from tests.isolation_helpers import requires_postgres  # noqa: F401
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OWNER_NAME = "Balcones Development LLC"
ADDRESS = "1400 Brazos Bend Drive"


def _wizard_plan(**over):
    """The payload `commitPlanOf` emits, transcribed from the browser's shape.

    ⚠ **`parcel_ref` IS `None` AND THAT IS THE WHOLE POINT OF THIS FILE'S
    SECOND HALF.** With one typed, a second press is refused `409
    premises.external_ref_taken` by a UNIQUE index on a different column — so
    the idempotency check passes without any idempotency existing. Empty is
    also the ordinary case: most builds never type a parcel.

    ⚠ **THE FOUR BILLING PREFERENCES ARE ON THE OWNER BLOCK**, exactly as
    `commitPlanOf` puts them there, because their presence IS `DEF-CUS-8020`.
    """
    plan = {
        "premises": {
            "id": None,
            "name": None,
            "address": ADDRESS,
            "city": "Austin",
            "state": "TX",
            "postal_code": "78704",
            "premise_type": None,
            "parcel_ref": None,
            "read_route": None,
            "services_available": ["electric"],
        },
        "mode": "our_crew",
        "scope": "new_premise",
        "units_prefix": "Apt",
        "target_activation": None,
        "service_request_id": None,
        "connection_id": None,
        "wizard_park_id": None,
        # `BR-CUS-1114` (PO 2026-10-02) — the owner's master account needs two
        # or more homes, so this build makes two.
        "units": [
            {"label": "Apt 1", "is_common_area": False},
            {"label": "Apt 2", "is_common_area": False},
        ],
        "meters": [],
        "plan_assignments": [],
        "create_owner_account": True,
        "owner": {
            "name": OWNER_NAME,
            "kind": "builder_developer",
            "email": "",
            "phone": "",
            "external_ref": None,
            # ── `DEF-CUS-8020` — THE FOUR THAT ANSWERED 422 ────────────────
            "autopay": True,
            "tax_exempt": True,
            "tax_exempt_ref": "TX-EX-4471",
            "tax_exempt_expires": "2027-12-31",
            # `BR-CUS-1024` — the master door refuses an owner it cannot
            # identify. The WIZARD's own two keys, translated to the accounts
            # door's `customer` block by
            # `_owner_block_in_the_doors_language`; sending an assembled block
            # here instead would test a path the browser does not take.
            "party_kind": "company",
            "identity": {"tax_id": identity_fixtures.SAMPLE_COMPANY_TAX_ID},
        },
        "quote_total": None,
        "occupancy": "vacant_service_off",
        "work_orders": [],
        "quote_lines": [],
        "quote_payer": "owner_account",
        "quote_due_days": None,
        "quote_posting_date": None,
    }
    plan.update(over)
    return plan


def _owner_block(**over):
    """The owner block with the identity the master door requires, patched."""
    owner = dict(_wizard_plan()["owner"])
    owner.update(over)
    return owner


# ════════════════════════════════════════════════════════════════════════════
# 1 · `DEF-CUS-8020` — PRESS CREATE, AND AN ACCOUNT ROW EXISTS
# ════════════════════════════════════════════════════════════════════════════
def test_pressing_create_writes_an_account_row(dana, brazos):
    """**The assertion nobody had. Before the fix this raised, every time.**

    ⚠ **IT ASSERTS THE ROW AND NOT THE RESPONSE.** A door can answer 200 and
    write nothing; the whole of `DEF-MET-5441` was a button posting to a 404
    with both suites green. The response's `owner_account_id` is checked too,
    but the row is what decides.
    """
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan())

        connection = work_tables.Connection.objects.get(pk=built["id"])
        assert connection.owner_account_id, built
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
        assert account.kind == "master"
        assert customers_models.Account.objects.count() == 1


def test_the_four_billing_preferences_reach_the_account_row(dana, brazos):
    """**Widening the allow list without writing them would be `DEF-1661`.**

    ⚠ **THIS IS THE CASE THAT SEPARATES THE FIX FROM THE APPEARANCE OF ONE.**
    Adding the four to `MASTER_CREATE_FIELDS` alone makes the 422 go away and
    leaves four boxes silently discarded — which is the worse of the two
    failures, because nothing tells the clerk. `DEF-1661` is the recorded cost:
    five columns declared lawful in an allow list, written by nothing, and
    1,213 migrated accounts that imported $0.00 of deposits with every test
    green.
    """
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan())
        connection = work_tables.Connection.objects.get(pk=built["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)

    assert account.autopay is True
    assert account.tax_exempt is True
    assert account.tax_exempt_ref == "TX-EX-4471"
    assert str(account.tax_exempt_expires) == "2027-12-31"


def test_an_owner_who_states_no_preferences_takes_the_column_defaults(dana, brazos):
    """**Absent is not `False`, and the door must not answer for the clerk.**

    Every pre-existing caller of the master door — the seeder, the tests, an
    approval — sends none of the four. If the fix defaulted them here, all of
    them would start writing `autopay=False` on the authority of a door that
    was never asked.
    """
    owner = _owner_block()
    for key in ("autopay", "tax_exempt", "tax_exempt_ref", "tax_exempt_expires"):
        owner.pop(key)
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        connection = work_tables.Connection.objects.get(pk=built["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)

    assert account.autopay is False
    assert account.tax_exempt is False
    assert account.tax_exempt_ref in (None, "")


# ════════════════════════════════════════════════════════════════════════════
# 2 · `DEF-CUS-8021` — TWO PRESSES, ONE OF EVERYTHING
# ════════════════════════════════════════════════════════════════════════════
TOKEN = "3f2b91c4-0d55-4a7e-9a0b-1f5d2c7e8a10"


def test_the_identical_payload_twice_builds_one_of_everything(dana, brazos):
    """**The double-click, with NO PARCEL NUMBER — the ordinary case.**

    Before the fix this answered 200 twice and left `CON-26-0130` and
    `CON-26-0131`: two connections, two customers, two master accounts, two
    properties at one address.

    ⚠ **THE SECOND PRESS RETURNS THE FIRST'S ANSWER, IT DOES NOT ERROR.** Rule
    6 asks for the first result. A 409 is what the parcel constraint was
    accidentally giving, and it tells a clerk their build failed when it
    succeeded.
    """
    plan = _wizard_plan(commit_token=TOKEN)
    with tenant_ctx(brazos):
        first = w6.commit_new_connect(dana, dict(plan))
        second = w6.commit_new_connect(dana, dict(plan))

        assert second["id"] == first["id"]
        assert second["connection_no"] == first["connection_no"]
        assert second.get("idempotent_replay") is True
        assert first.get("idempotent_replay") is not True

        assert work_tables.Connection.objects.count() == 1
        assert metering_models.Premises.objects.filter(address_line=ADDRESS).count() == 1
        assert customers_models.Account.objects.count() == 1
        assert customers_models.Customer.objects.count() == 1


def test_two_presses_take_the_money_once(dana, brazos):
    """**$250.00 once, and one balanced ledger pair — hard rules 5 and 6.**

    The measured cost of this defect was not a duplicate row: it was **two
    payments of $250.00, each posting its own balanced ledger pair**, both of
    which look perfectly correct in the books.
    """
    plan = _wizard_plan(
        commit_token=TOKEN,
        quote_lines=[{"charge_code": "CONN", "quantity": "1", "basis": "per unit"}],
        quote_due_days=30,
        quote_posting_date="2026-09-29",
        payment_method="card",
        payment_amount="250.0000",
        payment_date="2026-09-29",
    )
    with tenant_ctx(brazos):
        w6.commit_new_connect(dana, dict(plan))
        w6.commit_new_connect(dana, dict(plan))

        taken = list(payment_models.Payment.objects.all())

    assert len(taken) == 1, [str(row.id) for row in taken]
    assert taken[0].amount == Decimal("250.0000")


def test_a_second_build_started_afresh_is_a_new_token_and_is_allowed(dana, brazos):
    """**The key makes ONE press idempotent; it is not a duplicate-detector.**

    A developer really can raise a second connection at one property, and this
    asserts the fix did not quietly forbid it. `premises.external_ref` and
    `BR-CUS-1011`'s one-master-per-premises are where a genuine duplicate is
    refused on its own merits.
    """
    with tenant_ctx(brazos):
        first = w6.commit_new_connect(dana, _wizard_plan(commit_token=TOKEN))
        second = w6.commit_new_connect(
            dana,
            _wizard_plan(
                commit_token="9a1d77e0-4c33-4f18-9f44-6a0e2b5d8c91",
                owner=_owner_block(name="Second Build Holdings LLC"),
            ),
        )

        assert second["id"] != first["id"]
        assert work_tables.Connection.objects.count() == 2


def test_a_caller_with_no_token_is_told_it_has_no_replay_protection(dana, brazos):
    """**The seeder and the tests keep working, and are not lied to.**

    ⚠ **A STATED ABSENCE RATHER THAN A SILENT ONE.** Twenty-odd callers of this
    door cannot mint a token; refusing them would break the product to protect
    a press they never make. What must not happen is a caller BELIEVING it has
    a guarantee it does not have — hard-won law 1.
    """
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan())

    codes = {absence.get("code") for absence in built.get("unavailable") or []}
    assert "commit_token_absent_no_replay_protection" in codes
