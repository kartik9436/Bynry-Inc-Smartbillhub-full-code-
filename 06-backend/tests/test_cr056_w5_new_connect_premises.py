# ── Trace ──────────────────────────────────────────────
# Rules:    BR-MET-1024 (New Connect may create the address it builds on, and
#           the owner's account comes through the ONE existing door) ·
#           BR-MET-1010 (a premises gets its owner an account) · BR-MET-112
#           (nothing is written until step 9) · BR-MET-116 (the BUILD account
#           for a multi-unit development — untouched here) · BR-MET-401 (an
#           address names an owner at CREATE) · BR-CUS-1011 (one owner account
#           per address)
# Defects:  DEF-2961 (the commit manifest reported a premises it did not create)
# Source:   CR-056 task 23 · PO ruling 2026-08-31 (CR-056 ruling 1)
# ───────────────────────────────────────────────────────
"""CR-056 task 23 — New Connect creates the premises instead of demanding one.

Until 2026-09-01 the wizard refused without an address already on file, for a
connection whose whole purpose is that the address is new — and its commit
manifest reported *"premises: 1"* anyway, derived from the presence of UNITS.

Three things are asserted: the door takes a premises block and creates the
address through S16's own service; naming both is refused; and the owner of
that new address can be given his account through `ensure_owner_master_account`
— the door `CR-056` W1 opened and left with no caller.
"""

import pytest

from apps.metering import connections as w6, models as metering_models
from apps.work import connection_models as work_tables
from apps.customers import models as customer_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import make_premises, owner_for, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _new_address(actor, address="77 Sycamore Rise", owner="Ajinkya Kulkarni"):
    return {
        "address_line": address,
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "premises_type": "apartment_complex",  # CR-162-BRC10: the TYPE decides the master account
        "services_available": ["electric"],
        "owner_manager": owner,
        "owner_id": owner_for(actor, owner),
    }


def test_cr056_w5_tc23a__new_connect_creates_the_address_it_builds_on(dana, brazos):
    """**`BR-MET-1024`.** A `premises` block creates the address through S16's
    own `create_premises` — same validator, same number series, same audit row,
    same mandatory owner — and the connection is drafted against it.

    RED BEFORE THE FIX: `metering.connection.premises_required`, because the
    door read only `premises_id`.
    """
    with tenant_ctx(brazos):
        before = metering_models.Premises.objects.count()
        created = w6.create_connection(dana, {"premises": _new_address(dana)})

        assert created["premises_created"] is True
        assert metering_models.Premises.objects.count() == before + 1
        row = metering_models.Premises.objects.get(pk=created["premises_id"])
        # S16's own service made it: a premise NUMBER was allocated and the
        # owner is a typed party, not a string (BR-MET-401).
        assert row.premise_no
        assert row.owner_id is not None
        assert row.address_line == "77 Sycamore Rise"
        connection = metering_models.__dict__ and work_tables.Connection.objects.get(pk=created["id"])
        assert str(connection.premises_id) == created["premises_id"]
        assert connection.state == work_tables.DRAFT


def test_cr056_w5_tc23b__an_existing_address_still_works_and_is_not_created(dana, brazos):
    """The path every caller takes today is unchanged, and it SAYS it created
    nothing — `premises_created` is a fact reported, never inferred."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        before = metering_models.Premises.objects.count()
        created = w6.create_connection(dana, {"premises_id": premises["id"]})

        assert created["premises_created"] is False
        assert created["premises_id"] == premises["id"]
        assert metering_models.Premises.objects.count() == before


def test_cr056_w5_tc23c__naming_both_is_refused_by_name(dana, brazos):
    """*"Build on this address"* and *"build on a new address"* are different
    intentions. A door that quietly preferred one would sometimes create an
    address a clerk believed they had chosen from a list."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        before = metering_models.Premises.objects.count()
        with pytest.raises(errors.ValidationError) as refusal:
            w6.create_connection(
                dana,
                {"premises_id": premises["id"], "premises": _new_address(dana, "9 Elsewhere St")},
            )
        assert "premises" in str(refusal.value)
        assert metering_models.Premises.objects.count() == before


def test_cr056_w5_tc23d__the_manifest_no_longer_claims_a_premises_it_did_not_make(dana, brazos):
    """**`DEF-2961`.** `made["premises"]` read `1 if units else 0` — a premises
    counted from the presence of UNITS, by a function that has never created
    one.

    It is `None` with a stated reason now, the posture `sub_meter_links` already
    takes: a zero reads as *"we made none"* where the truth is *"this count
    cannot be answered here"*.
    """
    with tenant_ctx(brazos):
        created = w6.create_connection(dana, {"premises": _new_address(dana, "3 Manifest Way")})
        committed = w6.commit_connection(
            dana,
            created["id"],
            {"units": [{"label": "Unit 1"}, {"label": "Lobby", "is_common_area": True}]},
        )
        assert committed["manifest"]["units"] == 2
        assert committed["manifest"]["premises"] is None
        stated = {entry["field"] for entry in committed["unavailable"]}
        assert "premises" in stated


def test_cr056_w5_tc23e__the_new_address_gets_its_owner_an_account(dana, brazos):
    """**The caller `ensure_owner_master_account` never had** (`CR-056` W1
    named tasks 23 and 24 as its owners).

    PO 2026-08-31: *every address gets its owner a Master Account, whether or
    not anything is shared*. Opt-in by name, because an account is a money
    object and `BR-MET-112` is the rule that says a wizard does not mint one
    because a field was filled in.
    """
    with tenant_ctx(brazos):
        block = _new_address(dana, "5 Owner Court", owner="Miller Property LLC")
        created = w6.create_connection(dana, {"premises": block})
        committed = w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [{"label": "Unit 1"}],
                "create_owner_master_account": True,
                "owner_account": {"account_type": "residential"},
            },
        )
        account_id = committed["manifest"].get("owner_master_account_id") or None
        # The manifest key rides beside the seven counts; read the link itself.
        owner = metering_models.Premises.objects.get(pk=created["premises_id"]).owner
        assert owner.master_account_id is not None
        account = customer_models.Account.objects.get(pk=owner.master_account_id)
        # `BR-CUS-1010` — it hangs off the ADDRESS and names no unit.
        assert str(account.premises_id) == created["premises_id"]
        assert account.unit_id is None
        if account_id:
            assert str(account_id) == str(owner.master_account_id)


def test_cr056_w5_tc23f__asking_twice_is_idempotent_and_opens_one_account(dana, brazos):
    """*ensure*, not *create a second one* — and `BR-CUS-1011` (one owner
    account per address) would refuse the second anyway."""
    with tenant_ctx(brazos):
        block = _new_address(dana, "8 Twice Lane", owner="Repeat Holdings LLC")
        created = w6.create_connection(dana, {"premises": block})
        w6.commit_connection(
            dana,
            created["id"],
            {
                "units": [{"label": "Unit 1"}],
                "create_owner_master_account": True,
                "owner_account": {"account_type": "residential"},
            },
        )
        owner = metering_models.Premises.objects.get(pk=created["premises_id"]).owner
        first = owner.master_account_id
        from apps.metering import premises_owners

        premises_owners.ensure_owner_master_account(dana, owner.id, created["premises_id"])
        owner.refresh_from_db()
        assert owner.master_account_id == first
        assert (
            customer_models.Account.objects.filter(premises_id=created["premises_id"]).count() == 1
        )
