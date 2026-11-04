"""`CR-171-BRC10` P1.09 — the move-in's *Search customer ID*, and P1.11's read side.

THE RULING (decision log 2026-10-05, *"SEARCH CUSTOMER ID" ON THE CUSTOMER
STEP, USING THE MATCH RULES WE ALREADY HAVE*), PO verbatim: *"it will search
existing customer ID in system based on rules if found it will display it and
link it and if it si not found then it will show that new ID will be created;
If found show ID and name , link account and any outstanding"*.

THE WORKED CASE (images 34–37):

    **Rosa Alvarez**, born **1974-03-02**, SSN **123-45-6789**, is on file at
    Brazos Bend as **C-90001** and holds two accounts there (ACC-1042 at
    500 Main St · 200 and ACC-1051 at Oak Grove · 12), whose ledger balances
    are LE-1's own figures.

      * name + date of birth + SSN               → **found**
      * SSN under another name                   → **found** (Q5: SSN exact = match)
      * her name, birth date, a different SSN    → **possible** (Q5: name + DOB)
      * her name with a different birth date     → **new** — NOT SHOWN (Q5: name alone)
      * an SSN nobody holds                      → **new**
      * Lone Star Ridge's clerk, every fact      → **new** (hard rule 1)

    A company is **found** on its Tax ID and not shown on a name alone.

⚠ **AMENDED 2026-10-05 BY PO RULING** (decision log *"FOUR PO RULINGS IN ONE
REPLY"* (1), verbatim: *"if match based on our logic then we say match if it is
not then we dont say it"*). Until then FOUND was the money test and POSSIBLE was
every row `find_candidates` surfaced, a name-only hit included (image 35). The
search now uses New Connection's Q5 rule exactly; there is no wider tier.

The outstanding amount is SHOWN and NEVER MOVED: the search writes no row, and
the ledger reads the same before and after.

⚠ **THE NEW CONNECTION ANSWER IS UNCHANGED.** `POST /customers/match` without
`purpose` answers exactly `{"verdict", "candidates"}` under PO ruling Q5, which
`test_cr164_owner_lookup.py` pins. The search is the same door asked a
different question, so it is OPT-IN by `purpose: "search_customer_id"`.

PROVED RED FIRST (law 7): before `owner_lookup.search` existed every case here
failed on `KeyError: 'search'` at the response.

Run on PostgreSQL (the `requires_postgres` cases):

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      DATABASE_URL="postgres://postgres@127.0.0.1:55433/<your db>?sslmode=disable" \\
      pytest -q -p no:xdist --reuse-db tests/test_cr171_p109_search_customer_id.py
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.ledger_le_fixtures import make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, erin, lonestar, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

NAME = "Alvarez, Rosa"
DOB = "1974-03-02"
SSN = "123-45-6789"
LICENCE = "TX-DL-4417"
COMPANY = "Kestrel Holdings LLC"
EIN = "47-1234567"
PURPOSE = {"purpose": "search_customer_id"}  # the wire value, pinned


def _person(tenant, *, no="C-90001", name=NAME, ssn=SSN):
    customer = customers_models.Customer.objects.create(
        tenant=tenant, kind="person", display_name=name, customer_no=no
    )
    customer.date_of_birth = DOB
    identity_match.set_identifier(customer, "ssn", ssn)
    identity_match.set_identifier(customer, "driving_licence", LICENCE)
    customer.save()
    return customer


def _company(tenant, *, no="C-90002"):
    customer = customers_models.Customer.objects.create(
        tenant=tenant, kind="company", display_name=COMPANY, customer_no=no
    )
    identity_match.set_identifier(customer, "tax_id", EIN)
    customer.save()
    return customer


def _link(tenant, customer, account, tier="strong"):
    return customers_models.CustomerAccount.objects.create(
        tenant_id=tenant.id, customer=customer, account=account, match_tier=tier
    )


def _rosa_with_accounts(tenant, actor, service="electric"):
    """Rosa, her two accounts, and LE-1's month posted to the ledger."""
    with tenant_ctx(tenant):
        accounts = make_accounts(actor, tenant, {}, service=service)
        post_le1_month(tenant, accounts)
        rosa = _person(tenant)
        _link(tenant, rosa, accounts["ACC-1042"])
        _link(tenant, rosa, accounts["ACC-1051"])
    return rosa, accounts


def _post(actor, tenant, body):
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().post("/api/x/customers/match", body, format="json")
    force_authenticate(request, user=actor.user)
    request.tenant_role = actor.role
    request.tenant_id = tenant.id
    with tenant_ctx(tenant):
        return customers_api.customers_match(request)


def _search(actor, tenant, body):
    response = _post(actor, tenant, {**body, **PURPOSE})
    assert response.status_code == 200, response.data
    return response.data["search"]


def _statement(tenant, customer):
    with tenant_ctx(tenant):
        return customers_selectors.customer_statement(str(customer.id))


# ═══════════════════════════════════════════════════════════════════════════
# FOUND — BR-CUS-089 for a person, with accounts, addresses, state, outstanding
# ═══════════════════════════════════════════════════════════════════════════
def test_name_dob_and_ssn_is_found_with_every_account_and_the_outstanding(brazos, dana):
    rosa, _accounts = _rosa_with_accounts(brazos, dana)
    search = _search(
        dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN}
    )

    assert search["result"] == "found"
    assert search["count"] == 1
    hit = search["customers"][0]
    assert hit["verdict"] == "found"
    assert hit["customer_no"] == "C-90001"
    assert hit["display_name"] == NAME
    assert hit["basis"] == "matched on name, date of birth and Social Security number"

    accounts = hit["accounts"]
    assert accounts["count"] == 2
    by_no = {row["account_no"]: row for row in accounts["rows"]}
    assert set(by_no) == {"ACC-1042", "ACC-1051"}
    # Hard rule 8 — the address is WALKED to the premises, the unit is a LABEL.
    assert by_no["ACC-1042"]["address"]["line1"] == "500 Main St"
    assert by_no["ACC-1042"]["address"]["unit_label"] == "200"
    assert by_no["ACC-1051"]["address"]["line1"] == "Oak Grove"
    assert by_no["ACC-1051"]["address"]["unit_label"] == "12"
    assert by_no["ACC-1042"]["status_code"] == "active"

    # The ledger's own figures — the statement's rows, one derivation.
    statement = {row["account_no"]: row for row in _statement(brazos, rosa)["rows"]}
    for no, row in by_no.items():
        assert row["balance"] == statement[no]["balance"], no
        assert isinstance(row["balance"], str)
        balance = Decimal(row["balance"])
        assert Decimal(row["outstanding"]) == max(balance, Decimal("0")), no
    expected = sum(
        (max(Decimal(statement[no]["balance"]), Decimal("0")) for no in by_no), Decimal("0")
    )
    assert Decimal(accounts["outstanding_total"]) == expected
    assert expected > 0, "the fixture must owe something or this proves nothing"
    assert accounts["available"] is True
    assert accounts["currency"] == brazos.currency


def test_a_closed_account_carries_its_closed_date(brazos, dana):
    """Image 34: *Closed 08/31/2026* — the STATE cell carries its date."""
    rosa, accounts = _rosa_with_accounts(brazos, dana)
    with tenant_ctx(brazos):
        closed = customers_models.AccountStatus.objects.filter(tenant=brazos, code="closed").first()
        assert closed is not None
        account = accounts["ACC-1051"]
        account.status = closed
        account.closed_at = "2026-08-31"
        account.save(update_fields=["status", "closed_at"])
    search = _search(
        dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN}
    )
    row = next(
        r for r in search["customers"][0]["accounts"]["rows"] if r["account_no"] == "ACC-1051"
    )
    assert row["status_code"] == "closed"
    assert row["closed_at"] == "2026-08-31"


def test_identifiers_are_last_four_only(brazos, dana):
    """BR-CUS-092 — no full identifier on any read path."""
    _rosa_with_accounts(brazos, dana)
    response = _post(
        dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN, **PURPOSE}
    )
    hit = response.data["search"]["customers"][0]
    assert hit["ssn_last4"] == "6789"
    assert hit["driving_licence_last4"] == "4417"
    text = str(response.data)
    for secret in (SSN, "123456789", LICENCE, "TXDL4417"):
        assert secret not in text, secret


# ═══════════════════════════════════════════════════════════════════════════
# ONE RULE WITH NEW CONNECTION — PO ruling 2026-10-05 (decision log "FOUR PO
# RULINGS IN ONE REPLY" (1)), verbatim: *"if match based on our logic then we
# say match if it is not then we dont say it"*. The search's verdicts ARE Q5's
# (`owner_lookup.verdict_for`): an SSN, licence or Tax ID on file = FOUND; a
# person's name AND date of birth = POSSIBLE; anything less is NOT SHOWN.
# Image 35's *"Only the name matches."* is superseded and not built.
# ═══════════════════════════════════════════════════════════════════════════
def test_an_ssn_on_file_is_found_even_under_another_name(brazos, dana):
    """Q5: *"SSN or DL exact = match"* — the same answer New Connection gives."""
    _rosa_with_accounts(brazos, dana)
    search = _search(dana, brazos, {"kind": "person", "name": "Someone Else", "ssn": SSN})
    assert search["result"] == "found"
    hit = search["customers"][0]
    assert hit["verdict"] == "found"
    assert hit["agreed"] == ["ssn"]
    assert hit["accounts"]["count"] == 2


def test_name_and_date_of_birth_is_possible(brazos, dana):
    """Q5: *"name + DOB = possible match"* — our rule's own second answer."""
    _rosa_with_accounts(brazos, dana)
    search = _search(
        dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": "999-88-7777"}
    )
    assert search["result"] == "possible"
    assert search["count"] == 1
    assert search["customers"][0]["verdict"] == "possible"
    assert search["customers"][0]["agreed"] == ["name", "date_of_birth"]


def test_a_name_alone_is_not_shown(brazos, dana):
    """THE PO's CASE: Rosa typed with a different date of birth. New Connection
    says no match; so does this. Nobody is shown — not a weaker *possible*."""
    _rosa_with_accounts(brazos, dana)
    search = _search(
        dana,
        brazos,
        {"kind": "person", "name": NAME, "date_of_birth": "1980-01-01", "ssn": "999-88-7777"},
    )
    assert search == {"result": "new", "count": 0, "customers": []}


def test_a_date_of_birth_alone_is_not_shown(brazos, dana):
    """Q5: *"name alone or DOB alone = no match"* — a birth date alone shows nobody."""
    _rosa_with_accounts(brazos, dana)
    search = _search(dana, brazos, {"kind": "person", "name": "New Person", "date_of_birth": DOB})
    assert search == {"result": "new", "count": 0, "customers": []}


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN},
        {"kind": "person", "name": "Someone Else", "ssn": SSN},
        {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": "999-88-7777"},
        {"kind": "person", "name": NAME, "date_of_birth": "1980-01-01"},
        {"kind": "person", "name": "Someone Else", "driving_licence": LICENCE},
        {"kind": "company", "name": "Other Name LLC", "tax_id": EIN},
        {"kind": "company", "name": COMPANY},
    ],
)
def test_the_search_shows_exactly_whom_new_connection_shows(brazos, dana, body):
    """One rule, two screens: the same people, with the same answer each."""
    _rosa_with_accounts(brazos, dana)
    with tenant_ctx(brazos):
        _company(brazos)
    response = _post(dana, brazos, {**body, **PURPOSE})
    q5 = {row["customer_no"]: row["verdict"] for row in response.data["candidates"]}
    words = {"match": "found", "possible": "possible"}
    shown = {row["customer_no"]: row["verdict"] for row in response.data["search"]["customers"]}
    assert shown == {no: words[verdict] for no, verdict in q5.items()}
    assert response.data["search"]["count"] == len(q5)


def test_no_verdict_word_outside_the_rule_is_ever_served():
    """The contract WIZ-CUST draws from: four verdicts, five results, nothing else.

    ⚠ AMENDED 2026-10-13 BY PO RULING (`CR-181-BRC10`, *"Q1 C both"*): it read
    two verdicts until then. The two below Q5's are *same name and phone* and
    *lived here last* (`tests/test_cr181_returning_customer_reopen.py`)."""
    from apps.customers import owner_lookup

    assert owner_lookup.SEARCH_VERDICTS == ("found", "possible", "name_phone", "last_occupant")
    assert owner_lookup.SEARCH_RESULTS == (
        "found",
        "possible",
        "name_phone",
        "last_occupant",
        "new",
    )


def test_two_customers_holding_one_ssn_are_both_found(brazos, dana):
    """Q5 calls both a match, so both are shown as found; the clerk picks one
    with *Use this customer*, exactly as on New Connection."""
    with tenant_ctx(brazos):
        _person(brazos, no="C-90001")
        _person(brazos, no="C-90009")
    search = _search(
        dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN}
    )
    assert search["result"] == "found"
    assert [c["verdict"] for c in search["customers"]] == ["found", "found"]


def test_nobody_on_file_is_new(brazos, dana):
    _rosa_with_accounts(brazos, dana)
    search = _search(dana, brazos, {"kind": "person", "name": "New Person", "ssn": "999-88-7777"})
    assert search == {"result": "new", "count": 0, "customers": []}


def test_no_evidence_is_no_answer(brazos, dana):
    search = _search(dana, brazos, {"name": NAME})
    assert search == {"result": None, "count": 0, "customers": []}


# ═══════════════════════════════════════════════════════════════════════════
# COMPANY — BR-CUS-1022, and P1.11's read side
# ═══════════════════════════════════════════════════════════════════════════
def test_a_company_is_found_on_name_and_tax_id_with_its_contact_and_bills_address(brazos, dana):
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        company = _company(brazos)
        company.trading_as = "Kestrel Bakery"
        company.business_type = "LLC"
        company.registered_in = "IA"
        company.save()
        _link(brazos, company, accounts["ACC-1042"])
        account = accounts["ACC-1042"]
        account.po_number = "PO-7781"
        account.bills_go_to = "contact_person"
        account.save(update_fields=["po_number", "bills_go_to"])
        customers_models.Contact.objects.create(
            tenant=brazos,
            account=accounts["ACC-1042"],
            full_name="Nilesh G",
            email="nilesh@example.test",
            phone="(732) 630-0285",
            job_title="Owner",
            contact_by="email",
            is_primary=True,
        )
        customers_models.Address.objects.create(
            tenant=brazos,
            account=accounts["ACC-1042"],
            kind="mailing",
            line1="PO Box 12",
            city="Ottumwa",
            state="IA",
            postal_code="52501",
        )
    search = _search(dana, brazos, {"kind": "company", "name": COMPANY, "tax_id": EIN})
    assert search["result"] == "found"
    hit = search["customers"][0]
    assert hit["tax_id_last4"] == "4567"
    assert EIN not in str(search) and "471234567" not in str(search)
    company_block = hit["company"]
    assert company_block["legal_name"] == COMPANY
    # P1.11 — the 0080 columns (CR-171 §9.1).
    assert company_block["trading_as"] == "Kestrel Bakery"
    assert company_block["business_type"] == "LLC"
    assert company_block["registered_in"] == "IA"
    assert company_block["po_number"] == "PO-7781"
    assert company_block["bills_go_to"] == "contact_person"
    assert company_block["contact_person"] == {
        "full_name": "Nilesh G",
        "job_title": "Owner",
        "contact_by": "email",
        "email": "nilesh@example.test",
        "phone": "(732) 630-0285",
        "account_no": "ACC-1042",
    }
    assert company_block["bills_go_to_address"] == {
        "line1": "PO Box 12",
        "line2": None,
        "city": "Ottumwa",
        "state": "IA",
        "postal_code": "52501",
        "country": None,
        "account_no": "ACC-1042",
    }


def test_a_tax_id_on_file_is_found_and_a_company_name_alone_is_not_shown(brazos, dana):
    """Q5 for a company: the Tax ID decides (`REUSE_ID_FIELDS`); a name alone
    shows nobody, so a stranger's contact is never served on a name."""
    with tenant_ctx(brazos):
        _company(brazos)
    search = _search(dana, brazos, {"kind": "company", "name": "Other Name LLC", "tax_id": EIN})
    assert search["result"] == "found"
    assert search["customers"][0]["verdict"] == "found"
    # A name is nothing to judge on (`has_any`): no answer, nobody shown.
    assert _search(dana, brazos, {"kind": "company", "name": COMPANY}) == {
        "result": None,
        "count": 0,
        "customers": [],
    }


def test_a_person_carries_no_company_block(brazos, dana):
    _rosa_with_accounts(brazos, dana)
    search = _search(
        dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN}
    )
    assert search["customers"][0]["company"] is None


# ═══════════════════════════════════════════════════════════════════════════
# SHOWN, NEVER MOVED — and the New Connection answer unchanged
# ═══════════════════════════════════════════════════════════════════════════
def test_the_search_writes_nothing_and_moves_no_money(brazos, dana):
    from apps.ledger import models as ledger_models

    rosa, _accounts = _rosa_with_accounts(brazos, dana)
    with tenant_ctx(brazos):
        before = (
            ledger_models.JournalLine.objects.count(),
            customers_models.CustomerAccount.objects.count(),
            customers_models.Customer.objects.count(),
        )
        statement_before = customers_selectors.customer_statement(str(rosa.id))
    _search(dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN})
    with tenant_ctx(brazos):
        after = (
            ledger_models.JournalLine.objects.count(),
            customers_models.CustomerAccount.objects.count(),
            customers_models.Customer.objects.count(),
        )
        statement_after = customers_selectors.customer_statement(str(rosa.id))
    assert before == after
    assert statement_before["total"] == statement_after["total"]


def test_without_a_purpose_the_new_connection_answer_is_unchanged(brazos, dana):
    _rosa_with_accounts(brazos, dana)
    response = _post(
        dana, brazos, {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN}
    )
    assert set(response.data) == {"verdict", "candidates"}
    assert response.data["verdict"] == "match"
    assert "accounts" not in response.data["candidates"][0]


# ═══════════════════════════════════════════════════════════════════════════
# TENANT ISOLATION — a match never crosses utilities (hard rule 1)
# ═══════════════════════════════════════════════════════════════════════════
def _twins(brazos, lonestar, dana, erin):
    """Rosa at Brazos Bend with two accounts; a same-facts Rosa at Lone Star
    Ridge with one account of her own (Lone Star sells water only)."""
    rosa_b, _ = _rosa_with_accounts(brazos, dana)
    with tenant_ctx(lonestar):
        accounts = make_accounts(erin, lonestar, {}, service="water")
        rosa_l = _person(lonestar, no="C-50001")
        _link(lonestar, rosa_l, accounts["ACC-1055"])
    return rosa_b, rosa_l


FULL = {"kind": "person", "name": NAME, "date_of_birth": DOB, "ssn": SSN}


def test_another_utility_never_finds_her(brazos, lonestar, dana, erin):
    _rosa_with_accounts(brazos, dana)
    assert _search(erin, lonestar, FULL)["result"] == "new"


def test_twins_in_two_utilities_each_see_only_their_own(brazos, lonestar, dana, erin):
    _twins(brazos, lonestar, dana, erin)
    at_brazos = _search(dana, brazos, FULL)
    at_lonestar = _search(erin, lonestar, FULL)
    assert [c["customer_no"] for c in at_brazos["customers"]] == ["C-90001"]
    assert [c["customer_no"] for c in at_lonestar["customers"]] == ["C-50001"]
    assert {r["account_no"] for r in at_brazos["customers"][0]["accounts"]["rows"]} == {
        "ACC-1042",
        "ACC-1051",
    }
    assert {r["account_no"] for r in at_lonestar["customers"][0]["accounts"]["rows"]} == {
        "ACC-1055"
    }


@requires_postgres
@pytest.mark.isolation
def test_pg_the_search_and_its_tables_are_tenant_scoped(brazos, lonestar, dana, erin, rls):
    """The PostgreSQL proof, both halves.

    (1) The app layer: on PostgreSQL, through the view, each utility finds its
        own Rosa and only her accounts — the case above, on the real vendor.
    (2) The database: under the non-superuser probe role, every table the
        search reads (`customers`, `customer_accounts`, `accounts`,
        `journal_lines`) hides one utility's rows from the other.
    """
    rosa_b, rosa_l = _twins(brazos, lonestar, dana, erin)
    at_brazos = _search(dana, brazos, FULL)
    at_lonestar = _search(erin, lonestar, FULL)
    assert at_brazos["result"] == "found" and at_lonestar["result"] == "found"
    assert at_brazos["customers"][0]["id"] == str(rosa_b.id)
    assert at_lonestar["customers"][0]["id"] == str(rosa_l.id)
    assert Decimal(at_brazos["customers"][0]["accounts"]["outstanding_total"]) > 0

    assert_rls_scoped(rls, "customers", owner=brazos, intruder=lonestar, owner_ids={rosa_b.id})
    assert_rls_scoped(rls, "customers", owner=lonestar, intruder=brazos, owner_ids={rosa_l.id})
    for table in ("customer_accounts", "accounts", "journal_lines"):
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
