# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-012 (EP-CWP-04) — can I get service here: availability, fees
#           and deposits, read publicly. Screens: CWP-008
# Rules:    BR-CWP-021 (⚠ availability names the SERVICES, never the current
#           occupier — asserted on the RESPONSE BODY, which is the wave's own
#           exit test) · BR-CWP-026 (a public read may never change an account)
#           · BR-CWP-093's reading in TC-2 (an unknown address is not a
#           refusal) · CLAUDE.md hard rule 2 (four stored, two displayed)
# Tests:    this file — TC-1..TC-6 of the story's §3, one test each
# Impacts:  apps/portal/availability.py · seams/metering_seam.py ·
#           seams/rating_seam.py · money.py · guest_api.py
# ───────────────────────────────────────────────────────
"""US-CWP-012 on the SQLite suite. Every figure here is the story's §4 test
data quoted, and every one is seeded by `apps/portal/sample_data.py` — the same
code the demo fixture runs, so the number a walkthrough shows and the number a
test asserts cannot come from two different seeders."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.portal import availability, guest_api, sample_data
from apps.portal.seams import metering_seam, rating_seam
from apps.rating import models as rating_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call


def _availability(tenant, address):
    """The guest call: NO user, NO role — a visitor holding nothing."""
    return api_call(
        guest_api.availability,
        "get",
        f"/api/{tenant.subdomain}/portal/public/premises/availability?address={address}",
        tenant=tenant,
        query={"address": address},
    )


def _row(body, code):
    return next(row for row in body["rows"] if row["service_code"] == code)


@pytest.fixture()
def pine_addresses(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    return pine_hill


@pytest.mark.django_db
def test_tc1_thirty_one_palm_court_reads_the_four_rows_and_the_if_you_apply_box(pine_addresses):
    """TC-1 — the wave's demonstration, in one assertion set."""
    body = _availability(pine_addresses, "31 Palm Ct").data
    assert body["matched"] is True
    # The utility's OWN order, which is the wireframe's: Water · Sewer · Trash ·
    # Electric — neither the platform seed order nor alphabetical.
    assert [row["service_code"] for row in body["rows"]] == ["water", "sewer", "trash", "electric"]

    water = _row(body, "water")
    assert water["available"] is True
    # ⚠ HARD RULE 2 IN ONE LINE: four decimals stored, two displayed, and BOTH
    # travel so the pair can be checked against each other.
    assert water["to_connect"]["amount"] == "185.0000"
    assert water["to_connect"]["display"] == "$185.00"
    assert water["deposit"]["amount"] == "150.0000"
    assert water["deposit"]["display"] == "$150.00"

    # `Included` is not `$0.00`: no separate connection charge is attached, so
    # the screen names it in its own language and no figure travels.
    sewer = _row(body, "sewer")
    assert sewer["available"] is True and sewer["to_connect"]["kind"] == "included"
    assert sewer["to_connect"]["amount"] is None

    # `$0.00` IS a figure — a charge the utility configured and priced at zero.
    trash = _row(body, "trash")
    assert trash["to_connect"]["kind"] == "amount"
    assert trash["to_connect"]["amount"] == "0.0000"
    assert trash["to_connect"]["display"] == "$0.00"

    assert body["if_you_apply"]["before_we_start"]["display"] == "$185.00"
    assert body["if_you_apply"]["on_first_bill"]["display"] == "$150.00"
    assert body["if_you_apply"]["working_days"] == 3


@pytest.mark.django_db
def test_tc2_an_address_we_do_not_hold_is_not_a_refusal(pine_addresses):
    """TC-2 — *"a person will look at it"*, and the *Apply* route stays open.

    ⚠ **THE STATUS IS 200.** A 404 here would lose an applicant at the first
    box — *"they may never become a customer if we refuse them"* — and would
    also tell a stranger which addresses this utility holds, one probe at a time.
    """
    response = _availability(pine_addresses, "77 Nowhere Ln")
    assert response.status_code == 200
    assert response.data["matched"] is False
    assert response.data["rows"] == []          # not an empty TABLE either
    assert response.data["if_you_apply"] is None


@pytest.mark.django_db
def test_def_cwp_4930_an_unknown_address_offers_the_utilitys_services_to_tick(pine_addresses):
    """`DEF-CWP-4930` — an application for an address we do not hold could never
    be SENT: there were no rows, so the draft carried no services and the submit
    was refused on a step the applicant was never shown.

    The answer now OFFERS the utility's own services, in its own order, as names
    to tick — and nothing priced: no fee, no deposit, no *available* verdict,
    because nobody has looked at the address yet (TC-2 still holds: `rows` is
    empty and `if_you_apply` is absent)."""
    body = _availability(pine_addresses, "77 Nowhere Ln").data
    assert body["matched"] is False
    assert body["rows"] == [] and body["if_you_apply"] is None
    assert [one["service_code"] for one in body["offered"]] == ["water", "sewer", "trash", "electric"]
    assert all(set(one) == {"service_code", "service_name"} for one in body["offered"])
    # A matched address answers its rows as before and offers nothing to tick —
    # there, the address decides and there is nothing to choose.
    assert _availability(pine_addresses, "31 Palm Ct").data["offered"] == []


@pytest.mark.django_db
def test_tc3_an_occupied_address_is_a_move_in_and_names_nobody(pine_addresses):
    """TC-3 — *"the panel says this is a move-in, not a new connection. ⚠ It
    does not name the current occupier."*

    The second half is the wave's exit test and is asserted on the BODY: no
    name, no email, no phone, no account number, no customer id, anywhere.
    """
    # ⊕ `CR-200-BRC10` / `DEF-CWP-10680` (PO 2A, 2026-10-29): 1408 Elm St holds
    # several units, so the job is judged for the APARTMENT named — this read
    # `"1408 Elm St"` alone and asserted `move_in` for the whole building,
    # which was the defect's own output (B empty beside occupied A read
    # move-in too). Unit A is the occupied one; B is
    # `test_cr200_portal_address_suggestions.py` T4.
    body = api_call(
        guest_api.availability,
        "get",
        f"/api/{pine_addresses.subdomain}/portal/public/premises/availability",
        tenant=pine_addresses,
        query={"address": "1408 Elm St", "unit": "A"},
    ).data
    assert body["matched"] is True
    assert body["job"] == "move_in"
    # ⊕ `DEF-CWP-10690` (PO 2026-10-30, ruling A: *"A, move-in"*) — this line
    # asserted `new_connection` for the EMPTY house at 31 Palm Ct. An address
    # already in Premises is a move-in whether anybody lives there or not; a
    # new connection is only an address NOT in Premises (the staff Approve
    # window's 2026-09-23 / 2026-10-11 rule). An unknown address has no job.
    assert _availability(pine_addresses, "31 Palm Ct").data["job"] == "move_in"
    assert _availability(pine_addresses, "77 Nowhere Ln").data["job"] is None

    flat = str(body)
    for forbidden in (sample_data.OCCUPIER_NAME, sample_data.OCCUPIER_PHONE, "Alvarez", "@"):
        assert forbidden not in flat, f"BR-CWP-021: the body names {forbidden!r}"
    for key in ("customer", "account", "occupier", "name", "email", "phone"):
        assert key not in body, f"BR-CWP-021: the body carries a {key!r} member"


@pytest.mark.django_db
def test_tc4_a_service_not_carried_here_reads_not_here_and_never_zero(pine_addresses):
    """TC-4 — *"Reads **Not here** with no fee and no deposit — ⚠ not `$0.00`,
    which means free."*"""
    electric = _row(_availability(pine_addresses, "31 Palm Ct").data, "electric")
    assert electric["available"] is False
    assert electric["to_connect"]["kind"] == "none"
    assert electric["to_connect"]["amount"] is None
    assert electric["to_connect"]["display"] is None  # the screen draws an em dash
    assert electric["deposit"]["kind"] == "none"


@pytest.mark.django_db
def test_tc5_the_same_address_on_another_utility_never_shows_pine_hills_fees(
    pine_addresses, oak_ridge, elena
):
    """TC-5 — *"Oak Ridge's own premises and prices, or 'a person will look at
    it'. **Never Pine Hill's fees**."*"""
    switch_on(oak_ridge, elena)
    brand_fully(oak_ridge, elena, sample_data.OAK_RIDGE)
    body = _availability(oak_ridge, "31 Palm Ct").data
    assert body["matched"] is False
    assert "185" not in str(body) and "150" not in str(body)


@pytest.mark.django_db
def test_tc6_a_fee_priced_for_next_quarter_is_never_quoted_today(pine_addresses, sarah):
    """TC-6 — *"The **currently effective** version. A price read must not quote
    next quarter's fee."*

    ⚠ **BUILT HERE RATHER THAN IN THE FIXTURE, AND THE REASON IS THE PRODUCT
    REFUSING CORRECTLY.** `metering.services._apply_unit_plan` will not put a
    unit on a plan whose window has not opened — it resolves through
    `seams.plan_ref`, which answers None, and refuses with
    `metering.plan.tariff_unknown`. That refusal is the first line of defence.
    This case moves an ALREADY-ASSIGNED plan's window forward, which is the way
    the state can genuinely arise, and asserts the seam quotes nothing.
    """
    with tenant_context(pine_addresses.id):
        plan = rating_models.RatePlan.objects.get(code="PORTAL-RES")
        before = rating_seam.connection_fees(pine_addresses.id, plan.id, on=date.today())
        assert before["water"] == Decimal("185.0000")

        plan.effective_from = date.today() + timedelta(days=90)
        plan.save(update_fields=["effective_from"])
        after = rating_seam.connection_fees(pine_addresses.id, plan.id, on=date.today())
    # ⚠ None, not an empty dict: an empty dict would read as "free for
    # everything", which is the same class of wrong as quoting the future price.
    assert after is None

    body = _availability(pine_addresses, "31 Palm Ct").data
    assert body["matched"] is True
    assert _row(body, "water")["to_connect"]["kind"] == "none"
    assert "220" not in str(body)


@pytest.mark.django_db
def test_a_public_read_changes_no_account_row(pine_addresses):
    """BR-CWP-026 — *"A public read may never change an account."*

    Asserted the way `US-CWP-015` TC-3 asks for it: the account rows are
    byte-identical afterwards.
    """
    with tenant_context(pine_addresses.id):
        before = sorted(
            (str(row.id), row.status_id, row.updated_at.isoformat())
            for row in customers_models.Account.objects.all()
        )
    for address in ("31 Palm Ct", "1408 Elm St", "77 Nowhere Ln"):
        _availability(pine_addresses, address)
    with tenant_context(pine_addresses.id):
        after = sorted(
            (str(row.id), row.status_id, row.updated_at.isoformat())
            for row in customers_models.Account.objects.all()
        )
    assert before == after and before != []


@pytest.mark.django_db
def test_a_typed_address_matches_however_a_person_writes_it(pine_addresses):
    """`US-CWP-012` §5: *"Fuzzy; a miss is not a refusal."* The normaliser folds
    case, punctuation and the street words people shorten — and it does NOT
    guess a house number, which is the line between forgiving and wrong."""
    for typed in ("31 Palm Ct", "31 palm court, austin tx 78702", "31  PALM  CT."):
        assert _availability(pine_addresses, typed).data["matched"] is True, typed
    # A different number is a different house, and nothing pretends otherwise.
    assert _availability(pine_addresses, "33 Palm Ct").data["matched"] is False
    assert metering_seam.normalise_address("31 Palm Court.") == "31 palm ct"


@pytest.mark.django_db
def test_two_addresses_that_both_match_are_no_answer_at_all(pine_addresses):
    """A lookup that picks one of two addresses is the confident-and-wrong
    resolver `metering_seam` refuses to be. `1408 Elm` prefixes exactly one
    premises today; `Palm` on its own prefixes none, because a match is a
    PREFIX in one direction or the other and never a substring."""
    assert _availability(pine_addresses, "Palm Ct").data["matched"] is False
