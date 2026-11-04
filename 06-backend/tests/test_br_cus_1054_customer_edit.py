# ── Trace ──────────────────────────────────────────────
# Change:   BR-CUS-1054 — a customer's own details can be corrected.
#           `CR-094-BRC01` wave R. PO 2026-09-13, verbatim: *"Start the customer
#           edit one also - we will need this"*.
# Rules:    BR-CUS-1054 · BR-CUS-054 (one customer, many accounts) ·
#           BR-CUS-092(c) (last four only; never a full identifier in an audit
#           blob) · BR-CUS-1020 (the blind index beside each identifier) ·
#           BR-CUS-1022 (identity is per KIND) · CLAUDE.md hard rule 1, 4, 7, 8
#           · hard-won law 7 (prove a guard RED first) · law 14 (a unique clash
#           must be proved on PostgreSQL, not on the SQLite suite)
# ───────────────────────────────────────────────────────
"""**The test that matters here is a SEARCH, not a read-back.**

The failure this wave was most likely to ship is a stale blind index: correct a
phone without recomputing `phone_bidx` and the stored value is right while the
customer stops being findable by the very number just corrected. **Every test
that reads the field back passes on that bug**, because the field IS correct.

So `test_corrected_phone_is_findable` does not read the phone. It corrects it
and then runs `selectors.customer_list` — the search a clerk actually uses —
for the NEW number, and again for the OLD one. It was proved RED before it was
trusted green: with `customer.phone = value` in place of
`identity_match.set_identifier(...)` in `customer_edit.update_customer`, the
new number finds NOBODY and the old number still finds Rosa. That failure is
quoted in the wave report.

The worked case, one person followed end to end:

    **Alvarez, Rosa** is on file with the phone **512-555-0142** and the
    Social Security number **123-45-6789**. A clerk mistyped the phone at the
    counter; the real number is **512-555-0199**. After the correction, a
    search for `512-555-0199` finds her and a search for `512-555-0142` finds
    nobody. Her SSN reaches `audit_log` as **•••••6789** and never as digits.
"""

from __future__ import annotations

import json

import pytest

from apps.customers import customer_edit, identity_match
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

NAME = "Alvarez, Rosa"
DOB = "1974-03-02"
SSN = "123-45-6789"
PHONE_WRONG = "512-555-0142"
PHONE_RIGHT = "512-555-0199"

#: Every spelling of the secret that must never reach an audit blob. `6789`
#: alone is deliberately absent — the last four is what BR-CUS-092(c) allows.
FORBIDDEN = (SSN, "123456789", "123 45 6789", "12345", "456789", "123-45", "45-6789")


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through the real doors (DEF-658: never the ORM)
# ═══════════════════════════════════════════════════════════════════════════
def _plan(tenant, name="Residential Standard", service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, *, label="Unit A", service_code="electric"):
    premises = make_premises(actor, services_available=[service_code])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service_code=service_code).id)}
    )
    metering_services.ensure_service_point(unit["id"], service_code)
    return unit


def _open(actor, tenant, *, label, customer):
    unit = _unit(actor, tenant, label=label)
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": customer["display_name"]},
            "customer": customer,
        },
    )


def _person(name=NAME, phone=PHONE_WRONG, **identity):
    """A person's `customer` block for `create_account`.

    ⚠ `phone` alone makes a customer but never makes a MATCH — `BR-CUS-089` is
    *name + date of birth + one government ID*. A case that needs two accounts
    to land on ONE customer must pass `ssn=` and `date_of_birth=` as well.
    """
    block = {"phone": phone, **identity}
    return {"display_name": name, "kind": "person", "identity": block}


def _customer_row(account_result):
    """The customer the door created, as a model row."""
    link = customers_models.CustomerAccount.objects.select_related("customer").get(
        account_id=account_result["id"]
    )
    return link.customer


def _search(term: str) -> list[dict]:
    return customers_selectors.customer_list(
        ListParams(q=term, page=1, per=25, sort="display_name", dir="asc", filters={})
    )


def _names(rows) -> list[str]:
    return [row["display_name"] for row in rows]


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE ONE THAT MATTERS — a corrected phone is FINDABLE by the new number
# ═══════════════════════════════════════════════════════════════════════════
def test_corrected_phone_is_findable_by_the_new_number(brazos, dana):
    """⚠ **THIS ASSERTS A SEARCH, NOT A READ-BACK.** A read-back passes on the
    stale-index bug; only the search sees it."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)
        assert _names(_search(PHONE_WRONG)) == [NAME], "the fixture must start findable"

        customer_edit.update_customer(dana, str(customer.id), {"phone": PHONE_RIGHT})

        assert _names(_search(PHONE_RIGHT)) == [NAME], (
            "the corrected number finds nobody — `phone_bidx` was not recomputed, "
            "and the value on the row is perfectly correct"
        )
        assert _names(_search(PHONE_WRONG)) == [], "the OLD number still finds her"


def test_corrected_phone_moves_the_blind_index_token(brazos, dana):
    """The mechanism behind the search, asserted directly: the stored token is
    the one `blind_index_candidates` computes for the NEW value."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)
        old_token = customer.phone_bidx

        customer_edit.update_customer(dana, str(customer.id), {"phone": PHONE_RIGHT})
        customer.refresh_from_db()

        expected = identity_match.crypto.blind_index_candidates(
            PHONE_RIGHT, context=identity_match.CRYPTO_CONTEXT["phone"]
        )
        assert customer.phone_bidx in expected
        assert customer.phone_bidx != old_token
        assert customer.phone == PHONE_RIGHT


def test_the_naive_write_hides_the_customer__the_red_proof_kept(brazos, dana):
    """⚠ **THE PROOF THAT THE CASE ABOVE CAN FAIL, KEPT AS A TEST RATHER THAN
    DONE ONCE BY HAND.**

    Hard-won law 7: *"ask what would make this check pass wrongly"* — a check
    you cannot describe a false pass for is a check you do not understand. So
    the obvious wrong implementation is performed HERE, on the row, and the
    search is asserted to go BLIND on it:

        customer.phone = the corrected number
        customer.save(update_fields=["phone"])

    That is the one-line version every lane reaches for, and it is what
    `update_customer` must never do. The value on the row is CORRECT afterwards
    — `customer.refresh_from_db().phone` reads the new number, so a read-back
    test passes — and the customer has silently stopped being findable by it.

    Doing the proof by hand once (edit the module, watch it go red, put it back)
    proves nothing a month from now; this fails the day somebody "simplifies"
    `set_identifier` out of `update_customer`.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)

        customer.phone = PHONE_RIGHT
        customer.save(update_fields=["phone", "updated_at"])
        customer.refresh_from_db()

        # The value IS right — which is exactly why this bug survives review.
        assert customer.phone == PHONE_RIGHT
        # And the customer is now unreachable by it, and still answers to the
        # number that was wrong.
        assert _names(_search(PHONE_RIGHT)) == []
        assert _names(_search(PHONE_WRONG)) == [NAME]


def test_clearing_an_identifier_clears_its_index(brazos, dana):
    """An absent identifier must index to NOTHING rather than to a constant that
    every absent identifier shares — `blind_index` passes `None` through."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)

        customer_edit.update_customer(dana, str(customer.id), {"phone": ""})
        customer.refresh_from_db()

        assert customer.phone is None
        assert customer.phone_bidx is None
        assert _names(_search(PHONE_WRONG)) == []


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE NAME, AND WHAT AN ISSUED BILL DOES NOT DO (hard rule 4)
# ═══════════════════════════════════════════════════════════════════════════
def test_a_misspelt_name_is_corrected(brazos, dana):
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person(name="Alvraez, Rosa"))
        customer = _customer_row(opened)

        result = customer_edit.update_customer(
            dana, str(customer.id), {"display_name": NAME}
        )

        assert result["display_name"] == NAME
        customer.refresh_from_db()
        assert customer.display_name == NAME


def test_a_name_may_not_be_emptied(brazos, dana):
    """A customer with no name is not a correction; it is the deletion of the
    one fact every screen in the product prints."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)

        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(dana, str(customer.id), {"display_name": "   "})

        assert caught.value.message_key == "customers.customer.edit.name_required"
        customer.refresh_from_db()
        assert customer.display_name == NAME


# ═══════════════════════════════════════════════════════════════════════════
# 3 · REFUSED BY NAME, WITH THE RULE THAT OWNS THE FIELD — never dropped
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("field", "value", "br_ref"),
    [
        ("kind", "company", "BR-CUS-1022"),
        ("customer_no", "C-99999", "BR-CUS-1023"),
        ("postal", {"line1": "9 Elm St"}, "BR-CUS-1054"),
        ("portal_email", "rosa@example.test", "BR-CWP-004"),
        ("match_tier", "strong", "BR-CUS-089"),
        ("phone_bidx", "bix1:k1:zzz", "BR-CUS-1020"),
        ("is_sample", True, "BR-TEN-057"),
    ],
)
def test_a_field_this_door_does_not_own_is_refused_by_name(
    brazos, dana, field, value, br_ref
):
    """`DEF-632`'s lesson: a silently dropped field is a screen that says
    *saved* over a value that went nowhere."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)
        before = customers_models.Customer.objects.get(pk=customer.pk)

        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(dana, str(customer.id), {field: value})

        error = caught.value
        assert error.message_key == "customers.customer.edit.field_not_writable"
        assert error.field_errors[0]["field"] == field
        assert error.field_errors[0]["params"]["br_ref"] == br_ref
        assert error.field_errors[0]["params"]["reason"]

        after = customers_models.Customer.objects.get(pk=customer.pk)
        assert after.kind == before.kind
        assert after.customer_no == before.customer_no
        assert after.phone_bidx == before.phone_bidx


def test_a_field_no_customer_has_is_unknown_rather_than_refused(brazos, dana):
    """The two answers are different and must stay different: *the field exists
    and something else writes it* is not *there is no such field*."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)

        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(dana, str(customer.id), {"favourite_colour": "blue"})

        assert caught.value.message_key == "customers.customer.edit.unknown_field"


def test_a_refusal_fires_before_anything_is_written(brazos, dana):
    """⚠ The ORDER is the one thing to get right: a refusal that fired after the
    name was saved would leave the row half-edited while the response read
    *refused*."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)

        with pytest.raises(errors.ValidationError):
            customer_edit.update_customer(
                dana, str(customer.id), {"display_name": "Changed", "kind": "company"}
            )

        customer.refresh_from_db()
        assert customer.display_name == NAME


# ═══════════════════════════════════════════════════════════════════════════
# 4 · IDENTITY IS PER KIND — BR-CUS-1022, and neither borrows the other's
# ═══════════════════════════════════════════════════════════════════════════
def test_a_person_is_not_asked_for_a_tax_id(brazos, dana):
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)

        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(dana, str(customer.id), {"tax_id": "74-1234567"})

        assert caught.value.message_key == "customers.customer.edit.identifier_wrong_kind"
        customer.refresh_from_db()
        assert customer.tax_id is None
        assert customer.tax_id_bidx is None


def test_a_company_is_not_asked_for_a_driving_licence(brazos, dana):
    with tenant_ctx(brazos):
        opened = _open(
            dana,
            brazos,
            label="Unit A",
            customer={
                "display_name": "Kulkarni Holdings LLC",
                "kind": "company",
                "identity": {"tax_id": "74-1234567"},
            },
        )
        customer = _customer_row(opened)

        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(
                dana, str(customer.id), {"driving_licence": "TX-DL-4417"}
            )

        assert caught.value.message_key == "customers.customer.edit.identifier_wrong_kind"


def test_a_company_has_no_date_of_birth(brazos, dana):
    """`BR-CUS-1022` — the whole collision the rule resolves. Whether a company
    gets an incorporation date is `OQ-1241`, open."""
    with tenant_ctx(brazos):
        opened = _open(
            dana,
            brazos,
            label="Unit A",
            customer={
                "display_name": "Kulkarni Holdings LLC",
                "kind": "company",
                "identity": {"tax_id": "74-1234567"},
            },
        )
        customer = _customer_row(opened)

        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(dana, str(customer.id), {"date_of_birth": DOB})

        assert caught.value.message_key == "customers.customer.edit.dob_not_for_company"


def test_a_company_tax_id_is_corrected_and_stays_findable(brazos, dana):
    with tenant_ctx(brazos):
        opened = _open(
            dana,
            brazos,
            label="Unit A",
            customer={
                "display_name": "Kulkarni Holdings LLC",
                "kind": "company",
                "identity": {"tax_id": "74-1234560"},
            },
        )
        customer = _customer_row(opened)

        customer_edit.update_customer(dana, str(customer.id), {"tax_id": "74-1234567"})

        assert _names(_search("74-1234567")) == ["Kulkarni Holdings LLC"]
        assert _names(_search("74-1234560")) == []


# ═══════════════════════════════════════════════════════════════════════════
# 5 · HARD RULE 7 AND PII — the trail exists and it is MASKED
# ═══════════════════════════════════════════════════════════════════════════
def test_every_correction_writes_a_before_after_row(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person(ssn=SSN))
        customer = _customer_row(opened)
        audit_rows.clear()

        customer_edit.update_customer(
            dana, str(customer.id), {"display_name": NAME.upper(), "phone": PHONE_RIGHT}
        )

        rows = [row for row in audit_rows if row["action"] == "customer.updated"]
        assert len(rows) == 1, [row["action"] for row in audit_rows]
        assert rows[0]["before"]["display_name"] == NAME
        assert rows[0]["after"]["display_name"] == NAME.upper()
        assert rows[0]["before"]["phone"] == PHONE_WRONG
        assert rows[0]["after"]["phone"] == PHONE_RIGHT


def test_a_government_identifier_reaches_the_audit_masked(brazos, dana, audit_rows):
    """`BR-CUS-092(c)`: *"the full value is never in a list response, an export,
    a log line or an audit `details` blob"*."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person(ssn=SSN))
        customer = _customer_row(opened)
        audit_rows.clear()

        customer_edit.update_customer(dana, str(customer.id), {"ssn": "987-65-4321"})

        rows = [row for row in audit_rows if row["action"] == "customer.updated"]
        assert rows, "no audit row for an identity correction"
        text = json.dumps(rows, default=str)
        for spelling in FORBIDDEN:
            assert spelling not in text, f"audit blob leaked {spelling!r}: {text[:400]}"
        assert rows[0]["before"]["ssn"] == "•••••6789"
        assert rows[0]["after"]["ssn"] == "•••••4321"


def test_nothing_changed_writes_no_audit_row(brazos, dana, audit_rows):
    """A `PATCH` that restates what is already on file is not an event."""
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)
        audit_rows.clear()

        customer_edit.update_customer(dana, str(customer.id), {"display_name": NAME})

        assert [row for row in audit_rows if row["action"] == "customer.updated"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 6 · THE EMAIL — one save reaches every account (BR-CUS-054's landlord case)
# ═══════════════════════════════════════════════════════════════════════════
def test_one_email_correction_reaches_every_account(brazos, dana):
    """`contacts` hangs off the ACCOUNT, so a landlord with two accounts has two
    contact rows; a save that fixed one would leave the other bill going to the
    old address and nobody could tell which."""
    # ⚠ **THE SECOND ACCOUNT MUST PRESENT A `strong` IDENTITY OR IT IS A SECOND
    # PERSON, AND THE FIRST DRAFT OF THIS FIXTURE GOT THAT WRONG.** `BR-CUS-089`
    # is *name + date of birth + one government ID*; a matching NAME AND PHONE
    # is `weak` on purpose (`BR-CUS-1020`: *"a telephone number is not a
    # government ID"*), so two accounts opened on those alone are two customers
    # and this test would have asserted nothing about a landlord.
    strong = {"ssn": SSN, "date_of_birth": DOB, "phone": PHONE_WRONG}
    with tenant_ctx(brazos):
        first = _open(dana, brazos, label="Unit A", customer=_person(**strong))
        customer = _customer_row(first)
        second = _open(dana, brazos, label="Unit B", customer=_person(**strong))
        # The second account links to the SAME customer — that is BR-CUS-054's
        # whole point and the reason this test is worth writing.
        assert str(_customer_row(second).id) == str(customer.id), (
            "the fixture did not reproduce the landlord case"
        )

        result = customer_edit.update_customer(
            dana, str(customer.id), {"email": "rosa@example.test"}
        )

        assert result["accounts_updated"] == 2
        emails = set(
            customers_models.Contact.objects.filter(
                tenant_id=brazos.id, account_id__in=[first["id"], second["id"]]
            ).values_list("email", flat=True)
        )
        assert emails == {"rosa@example.test"}


def test_correcting_the_email_does_not_move_the_portal_sign_in(brazos, dana):
    """⚠ **`apps/portal` holds its own `email` and it is the SIGN-IN
    identifier.** Moving it here would be a cross-module write (B2 §2) and would
    either lock a customer out or hand their account to a new address.
    `OQ-CUS-12350` is CLOSED (PO 2026-10-22): the two follow each other only
    when the clerk ticks *"Also use this as the portal sign-in email"*
    (`portal_sign_in: true`, `tests/test_cr189_signin_email.py`). This is the
    UNTICKED case, and it must stay exactly as it was."""
    from apps.portal import models as portal_models

    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)
        credential = portal_models.PortalCredential.objects.create(
            tenant_id=brazos.id,
            customer_id=customer.id,
            email="rosa.old@example.test",
            password_hash="x",
        )

        customer_edit.update_customer(dana, str(customer.id), {"email": "rosa.new@example.test"})

        credential.refresh_from_db()
        assert credential.email == "rosa.old@example.test"


# ═══════════════════════════════════════════════════════════════════════════
# 7 · THE LEGACY REFERENCE — a clash is a sentence, not a 500 (law 14)
# ═══════════════════════════════════════════════════════════════════════════
def test_a_taken_legacy_reference_is_refused_by_name(brazos, dana):
    """⚠ `uq_customers_tenant_external_ref_ci` is asked as a QUESTION and the
    save still runs inside a SAVEPOINT, because on PostgreSQL a failed statement
    aborts the whole transaction and SQLite would never show it (law 14)."""
    with tenant_ctx(brazos):
        first = _open(dana, brazos, label="Unit A", customer=_person(name="Alvarez, Rosa"))
        second = _open(dana, brazos, label="Unit B", customer=_person(name="Whitfield, Dana"))
        one, two = _customer_row(first), _customer_row(second)
        customer_edit.update_customer(dana, str(one.id), {"external_ref": "CUST-118"})

        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(dana, str(two.id), {"external_ref": "cust-118"})

        assert caught.value.message_key == "customers.customer.edit.ref_taken"
        two.refresh_from_db()
        assert two.external_ref is None


def test_the_legacy_reference_can_be_cleared(brazos, dana):
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)
        customer_edit.update_customer(dana, str(customer.id), {"external_ref": "CUST-118"})

        customer_edit.update_customer(dana, str(customer.id), {"external_ref": ""})

        customer.refresh_from_db()
        assert customer.external_ref is None


# ═══════════════════════════════════════════════════════════════════════════
# 8 · HARD RULE 1 — a customer of another tenant is NOT FOUND, never forbidden
# ═══════════════════════════════════════════════════════════════════════════
def test_another_tenants_customer_is_not_found(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit A", customer=_person())
        customer = _customer_row(opened)

    erin = None
    from tests.test_us_met_helpers import staff_actor

    erin = staff_actor(lonestar, "system_admin", "erin@lonestarridge.test")
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            customer_edit.update_customer(erin, str(customer.id), {"display_name": "Taken"})

    with tenant_ctx(brazos):
        customer.refresh_from_db()
        assert customer.display_name == NAME


def test_a_malformed_id_is_not_found(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            customer_edit.update_customer(dana, "not-a-uuid", {"display_name": "Taken"})
