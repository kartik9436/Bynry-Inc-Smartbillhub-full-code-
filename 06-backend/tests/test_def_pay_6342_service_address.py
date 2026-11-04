# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-6342 (part 1) — a letter to an account with no mailing
#           address was queued UNADDRESSED, while the recipient read's own
#           docstring said it fell back to the service address.
# Rules:    B2 §2 (`addresses` kind mailing; omitted = same as service) ·
#           CLAUDE.md hard rule 8 (an address lives on `premises`; a unit
#           refines it by LABEL; everything else walks to it) · BR-BIL-036 (a
#           fact about the PROPERTY and a fact about the PLATFORM are two
#           different absences) · BR-TEN-017 (the recipient is a SNAPSHOT) ·
#           PO ruling 2026-09-23, verbatim: "fx it - ensure you update correct
#           address - mailing or service"
# Tests:    this file
# ───────────────────────────────────────────────────────
"""A letter goes to the mailing address, or else to the SERVICE address — and
the snapshot says which.

Every case here goes through a ROUTE where one exists: `GET
/accounts/{id}/communication` is the screen that states, per channel, where a
message to this account would go, and `PATCH /accounts/{id}/mailing-address` is
the door that removes a mailing address. The two unit-level cases below them
drive the two absences that no fixture can reach through a route — metering
unpublished, and a premises with no street — because each is a different
answer and must never be spelled like the other.
"""

from __future__ import annotations

import pytest

from apps.customers import api as customers_api
from apps.customers import communication_api
from apps.customers import seams as customers_seams
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    api_call,
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _account(actor, *, street="1408 Bluestem Ln", label="Unit A", mailing=None):
    """An account on a unit at a premises, with or without a mailing row."""
    premises = make_premises(actor, address_line=street)
    unit = make_unit(actor, premises["id"], label=label)
    payload = {
        "unit_id": str(unit["id"]),
        "account_type": "residential",
        "opened_at": "2026-02-01",
        "contact": {"full_name": "Sarah Miller", "email": "sarah.miller@example.com"},
        "customer": identity_fixtures.customer_block("Sarah Miller", account_type="residential"),
    }
    if mailing is not None:
        payload["addresses"] = [{"kind": "mailing", **mailing}]
    created = customers_services.create_account(actor, payload)
    return created["id"], premises["id"], unit["id"]


def _print_row(tenant, user, account_id):
    """The pdf_print row of `GET /accounts/{id}/communication`."""
    response = api_call(
        communication_api.account_communication,
        "get",
        user=user,
        role="billing_clerk",
        tenant=tenant,
        account_id=str(account_id),
    )
    assert response.status_code == 200, response.data
    return next(row for row in response.data["channels"] if row["channel"] == "pdf_print")


def test_no_mailing_row_posts_to_the_premises_with_its_unit_label(brazos, marcus):
    """THE DEFECT. Before: `address` None, `recipient_not_resolvable`."""
    with tenant_ctx(brazos):
        account_id, _premises, _unit = _account(marcus)
        snapshot = customers_selectors.delivery_recipients_for_account(
            account_id, channels=("pdf_print",)
        )["pdf_print"]["snapshot"]
        row = _print_row(brazos, marcus.user, account_id)
    assert row["address"] == "1408 Bluestem Ln · Unit A"
    assert row["unavailable_reason"] is None
    assert snapshot == {
        "name": "Sarah Miller",
        "line1": "1408 Bluestem Ln",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "unit_label": "Unit A",
        "source": "service_address",
    }


def test_a_mailing_row_wins_and_says_so(brazos, marcus):
    with tenant_ctx(brazos):
        account_id, _premises, _unit = _account(
            marcus,
            mailing={
                "line1": "PO Box 77",
                "city": "Sugar Land",
                "state": "TX",
                "postal_code": "77478",
            },
        )
        snapshot = customers_selectors.delivery_recipients_for_account(
            account_id, channels=("pdf_print",)
        )["pdf_print"]["snapshot"]
        row = _print_row(brazos, marcus.user, account_id)
    assert row["address"] == "PO Box 77"
    assert snapshot["source"] == "mailing_address"
    assert snapshot["line1"] == "PO Box 77"


def test_removing_the_mailing_address_sends_post_to_the_service_address(brazos, marcus):
    """The door the returned-post clear step offers for a MAILING letter.

    An empty street through `PATCH /accounts/{id}/mailing-address` soft-deletes
    the row, which is how a clerk says *the bill goes to the service address*.
    The recipient read did not filter `deleted_at` and kept posting to the
    address the clerk had just removed — found while building this.
    """
    with tenant_ctx(brazos):
        account_id, _premises, _unit = _account(
            marcus,
            mailing={
                "line1": "PO Box 77",
                "city": "Sugar Land",
                "state": "TX",
                "postal_code": "77478",
            },
        )
        removed = api_call(
            customers_api.account_mailing_address,
            "patch",
            user=marcus.user,
            role="billing_clerk",
            tenant=brazos,
            data={"line1": ""},
            account_id=str(account_id),
        )
        assert removed.status_code == 200, removed.data
        row = _print_row(brazos, marcus.user, account_id)
    assert row["address"] == "1408 Bluestem Ln · Unit A"


def test_metering_unpublished_is_the_platforms_gap_not_the_customers(brazos, marcus, monkeypatch):
    """`recipient_not_resolvable`, never `no_postal_address` (BR-BIL-036)."""
    with tenant_ctx(brazos):
        account_id, _premises, _unit = _account(marcus)
        real = customers_seams.resolve

        def unpublished(module, attribute, kind="services"):
            if attribute == "envelope_addresses":
                return None
            return real(module, attribute, kind)

        monkeypatch.setattr(customers_seams, "resolve", unpublished)
        answer = customers_selectors.delivery_recipients_for_account(
            account_id, channels=("pdf_print",)
        )["pdf_print"]
    assert answer == {"unavailable_reason": "recipient_not_resolvable"}


def test_a_premises_with_no_street_is_a_fact_about_the_property(brazos, marcus):
    """`no_postal_address` — a place nobody gave a street. A legacy row only:
    `create_premises` requires the street, so the ORM writes it here."""
    with tenant_ctx(brazos):
        account_id, premises_id, _unit = _account(marcus)
        metering_models.Premises.objects.filter(pk=premises_id).update(address_line="  ")
        answer = customers_selectors.delivery_recipients_for_account(
            account_id, channels=("pdf_print",)
        )["pdf_print"]
    assert answer == {"unavailable_reason": "no_postal_address"}


def test_the_metering_read_is_two_statements_whatever_is_asked(
    brazos, marcus, django_assert_num_queries
):
    """`NFR-3` — five units and one premises, two statements, labels intact."""
    with tenant_ctx(brazos):
        premises = make_premises(marcus, address_line="412 Cypress Row")
        units = [make_unit(marcus, premises["id"], label=f"Unit {n}")["id"] for n in range(5)]
        with django_assert_num_queries(2):
            answered = metering_selectors.envelope_addresses(
                unit_ids=units, premises_ids=[premises["id"]]
            )
    assert sorted(env["unit_label"] for env in answered["units"].values()) == [
        f"Unit {n}" for n in range(5)
    ]
    assert {env["line1"] for env in answered["units"].values()} == {"412 Cypress Row"}
    assert answered["premises"][str(premises["id"])]["unit_label"] is None
