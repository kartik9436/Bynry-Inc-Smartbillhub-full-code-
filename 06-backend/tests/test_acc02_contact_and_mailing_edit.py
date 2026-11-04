# ── Trace ──────────────────────────────────────────────
# Change:   The Product Owner drove the live account Overview on 2026-09-13 and
#           reported six faults. Fault 4, verbatim: *"I cannot edit Customer
#           details, Mailing address, Billing preferences, Portal access"*.
#           Two of those four had NO WRITE DOOR ON THE SERVER, and these are it.
# Rules:    BR-CUS-045 (every contact column is PII; `gov_id_last4` is the last
#           four ONLY) · CLAUDE.md hard rule 8 (an address lives on `premises`;
#           `customers.addresses kind='mailing'` is its FIRST named exception —
#           where the BILL goes) · BR-MET-1161 (`kind='service'` is RETIRED and
#           a write asking for it is refused BY NAME) · BR-SHL-025 (the
#           server-side guard is THE guard) · hard rule 7 / BR-AUD-003 (the
#           write is audited before→after).
# ───────────────────────────────────────────────────────
"""`PATCH /accounts/{id}/contact` and `PATCH /accounts/{id}/mailing-address`.

**WHY THESE EXIST AT ALL, BECAUSE THE OBVIOUS ANSWER WAS THE WRONG TABLE.**
The refusal on the Overview's CUSTOMER pencil read *"Customer details are not
editable yet."* and the brief that commissioned this fix said it was stale,
because `PATCH /customers/{id}` had just been built. It was checked before it
was built on:

  · `PATCH /customers/{id}` (`BR-CUS-1054`) writes the **`customers`** row —
    `display_name`, `external_ref`, `date_of_birth`, `phone`, `email` — reached
    through `customer_accounts`, and is mounted on the CUSTOMER's own screen.
  · The account Overview's CUSTOMER group renders **`contacts`**, a different
    table with its own FK to `accounts`, and `models.Contact` says so in as
    many words: *"`account_id` is B2 §2 verbatim"*.

They are not the same fact. Wiring the account's pencil to the customer route
would have saved a name the group does not display — a control that appears to
work and changes nothing on screen, which is worse than a refusal. So the
classification was *no endpoint, table exists*, and the door was built.

The mailing address is the same shape one exception over: `_validate_addresses`
has always existed and only `create_account` and the move-in wizard called it.

**WHAT EACH CASE GUARDS, and none of them is "the call returned".** The failure
this pair is most exposed to is `DEF-1661`'s — a write that validates, returns
200 and drops a field on the floor — so every case reads the value BACK.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

pytestmark = pytest.mark.django_db


def _account(brazos, marcus):
    unit = _unit_with_plan(marcus, brazos)
    return customers_services.create_account(marcus, _create_payload(unit["id"]))


def _contact(account_id):
    return (
        customers_models.Contact.objects.filter(account_id=account_id, deleted_at__isnull=True)
        .order_by("-is_primary", "created_at", "id")
        .first()
    )


# ══════════════════════════════════════════════════════════════════════════
# THE CONTACT DOOR
# ══════════════════════════════════════════════════════════════════════════
def test_contact_tc1__every_field_the_form_sends_is_written_and_read_back(brazos, marcus):
    """The four the dialog draws, one at a time. A form that submits and drops
    a field passes every other kind of test."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        out = customers_services.update_account_contact(
            marcus,
            created["id"],
            {
                "full_name": "Bramble Bakery Ltd",
                "email": "accounts@bramblebakery.example",
                "phone": "+1 (512) 555-0117",
                "dob": "1979-04-02",
            },
        )

    contact = out["contacts"][0]
    assert contact["full_name"] == "Bramble Bakery Ltd"
    assert contact["email"] == "accounts@bramblebakery.example"
    assert contact["phone"] == "+1 (512) 555-0117"
    assert contact["dob"] == "1979-04-02"


def test_contact_tc2__a_partial_body_keeps_every_field_it_does_not_name(brazos, marcus):
    """**IT IS A PATCH, NOT A PUT, AND `_validate_contact` REQUIRES A NAME.**
    Handing the validator a body carrying only a phone number would refuse on
    `full_name`; the service merges the stored row first. Without this the
    dialog would have to resend every field to change one, which is how one
    clerk's edit silently reverts another's."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        before = _contact(created["id"]).full_name
        out = customers_services.update_account_contact(
            marcus, created["id"], {"phone": "+1 (512) 555-0199"}
        )

    assert out["contacts"][0]["phone"] == "+1 (512) 555-0199"
    assert out["contacts"][0]["full_name"] == before


def test_contact_tc3__the_write_is_audited_before_and_after(brazos, marcus, audit_rows):
    """Hard rule 7 / `BR-AUD-003` — a PII edit is reviewable or it is silent."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        audit_rows.clear()
        customers_services.update_account_contact(
            marcus, created["id"], {"phone": "+1 (512) 555-0199"}
        )

    assert "account.contact.updated" in audit_actions(audit_rows)
    row = next(r for r in audit_rows if r.get("action") == "account.contact.updated")
    assert row["before"]["contacts"][0]["phone"] != "+1 (512) 555-0199"
    assert row["after"]["contacts"][0]["phone"] == "+1 (512) 555-0199"


def test_contact_tc3b__a_patch_that_changes_nothing_writes_no_audit_row(
    brazos, marcus, audit_rows
):
    """The service builds `fields` by COMPARING. An audit log that records
    every SUBMIT rather than every CHANGE is one nobody reads."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        same = _contact(created["id"]).full_name
        audit_rows.clear()
        customers_services.update_account_contact(marcus, created["id"], {"full_name": same})

    assert "account.contact.updated" not in audit_actions(audit_rows)


def test_contact_tc4__a_government_id_is_truncated_to_its_last_four(brazos, marcus):
    """`BR-CUS-045`: a full government id cannot enter the database through this
    path either. The dialog does not offer the field; the DOOR still refuses to
    widen it, because a door is what a future caller reaches."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        customers_services.update_account_contact(
            marcus, created["id"], {"gov_id_last4": "123-45-6789"}
        )
        stored = _contact(created["id"]).gov_id_last4

    assert stored == "6789"


def test_contact_tc5__an_unknown_key_is_refused_by_name(brazos, marcus):
    """The door's vocabulary is `CONTACT_FIELDS` and nothing else. A key it does
    not know is a caller's bug, and answering 200 to it is how a field quietly
    stops being saved."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        with pytest.raises(errors.ValidationError):
            customers_services.update_account_contact(
                marcus, created["id"], {"credit_tier": "gold"}
            )


# ══════════════════════════════════════════════════════════════════════════
# THE MAILING-ADDRESS DOOR
# ══════════════════════════════════════════════════════════════════════════
def test_mailing_tc1__an_account_with_no_mailing_row_gains_one(brazos, marcus):
    """`create_account` leaves no mailing row when none was given, and B2 §2
    reads that as *the bill goes to the service address*. Adding one later was
    impossible until this door existed."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        out = customers_services.update_account_mailing_address(
            marcus,
            created["id"],
            {
                "line1": "18 Cedar Ridge Way",
                "city": "Silver Creek",
                "state": "TX",
                "postal_code": "78611",
            },
        )

    mailing = [a for a in out["addresses"] if a["kind"] == "mailing"]
    assert len(mailing) == 1
    assert mailing[0]["line1"] == "18 Cedar Ridge Way"
    assert mailing[0]["city"] == "Silver Creek"
    assert mailing[0]["postal_code"] == "78611"


def test_mailing_tc2__a_second_call_corrects_the_same_row_rather_than_adding_one(
    brazos, marcus
):
    """Two mailing rows on one account is a state no screen can render and no
    bill run can choose between."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": "18 Cedar Ridge Way"}
        )
        out = customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": "20 Cedar Ridge Way"}
        )

    mailing = [a for a in out["addresses"] if a["kind"] == "mailing"]
    assert len(mailing) == 1
    assert mailing[0]["line1"] == "20 Cedar Ridge Way"


def test_mailing_tc3__clearing_the_street_removes_the_row(brazos, marcus):
    """**AN EMPTY `line1` IS A DELETE AND IT IS THE CORRECT MODEL.** No mailing
    row means *the bill goes to the service address*, which the screen already
    says in those words; a second `Remove` control would be two ways to state
    one fact."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": "18 Cedar Ridge Way"}
        )
        out = customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": ""}
        )

    assert [a for a in out["addresses"] if a["kind"] == "mailing"] == []


def test_mailing_tc4__the_retired_service_kind_cannot_arrive_through_this_door(
    brazos, marcus
):
    """`BR-MET-1161` retired `kind='service'` and `G85` fails a fourth home for
    an address. This route does not read `kind` from the body AT ALL, so the
    retired value cannot arrive even as a typo — asserted rather than assumed,
    because *the caller cannot send it* and *the caller's value is ignored* are
    different guarantees and only one of them survives a refactor."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        with pytest.raises(errors.ValidationError):
            customers_services.update_account_mailing_address(
                marcus, created["id"], {"line1": "1 Any St", "kind": "service"}
            )


def test_mailing_tc5__the_write_is_audited_before_and_after(brazos, marcus, audit_rows):
    """Hard rule 7 / `BR-AUD-003`. Where the bill goes is a money-facing fact:
    an address changed without a trail is an unexplained missing bill."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        audit_rows.clear()
        customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": "18 Cedar Ridge Way"}
        )

    assert "account.mailing_address.updated" in audit_actions(audit_rows)
    row = next(r for r in audit_rows if r.get("action") == "account.mailing_address.updated")
    # ⚠ **`_create_payload` ALREADY CARRIES A MAILING ADDRESS**, so "before" is
    # a row rather than an absence — the first draft of this case asserted an
    # empty list and went red, which is the fixture telling the truth. What the
    # case is about is the LINE moving, before→after.
    before = [a for a in row["before"]["addresses"] if a["kind"] == "mailing"]
    after = [a for a in row["after"]["addresses"] if a["kind"] == "mailing"]
    assert before[0]["line1"] != "18 Cedar Ridge Way"
    assert after[0]["line1"] == "18 Cedar Ridge Way"


def test_mailing_tc6__removing_the_row_is_audited_under_its_own_action(
    brazos, marcus, audit_rows
):
    """A removal and a correction are different events, so they carry different
    action names. One name for both would make *the bill stopped arriving*
    unsearchable."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        customers_services.update_account_mailing_address(
            marcus, created["id"], {"line1": "18 Cedar Ridge Way"}
        )
        audit_rows.clear()
        customers_services.update_account_mailing_address(marcus, created["id"], {"line1": ""})

    assert "account.mailing_address.removed" in audit_actions(audit_rows)


# ══════════════════════════════════════════════════════════════════════════
# BOTH DOORS · BR-SHL-025 — the SERVICE carries the guard, not only the view
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture()
def priya(brazos):
    """Brazos Bend's EXECUTIVE — A4 gives the role VIEW on accounts and no write.

    ⚠ **THE FIRST DRAFT OF TC-7 USED `erin` AND PASSED FOR THE WRONG REASON —
    it did not pass at all, it raised the WRONG EXCEPTION.** `erin` is the
    ISOLATION tenant's System Admin, so the role guard let her through and the
    call died on `unknown_field` instead. A guard proved by an exception you did
    not name is not proved (law 7: *ask what would make this check pass
    wrongly*). This fixture is the role A4 actually withholds the write from.
    """
    from tests.test_us_met_helpers import staff_actor

    return staff_actor(brazos, "executive", "priya@brazosbendutilities.test")


@pytest.mark.parametrize(
    ("call", "body"),
    [
        (customers_services.update_account_contact, {"full_name": "Nope"}),
        (customers_services.update_account_mailing_address, {"line1": "1 Any St"}),
    ],
)
def test_both_tc7__a_role_without_write_is_refused_at_the_service(brazos, priya, marcus, call, body):
    """`BR-SHL-025` — *the server-side guard is THE guard*. The view carries
    `AdminOrClerk`; this asserts the SERVICE refuses too, so a future caller
    that forgets the permission class cannot write through it.

    ⚠ **THE BODY IS A VALID ONE ON PURPOSE.** A body the validator would reject
    lets the case pass on a `ValidationError` and say nothing at all about the
    guard — which is exactly how the first draft of this case failed."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        with pytest.raises(errors.AuthError):
            call(priya, created["id"], body)
