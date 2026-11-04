# ── Trace ──────────────────────────────────────────────
# Change:   CR-056 waves W2 (tasks 11-14), W3 (tasks 15-18) and W5 (task 25).
# Rules:    BR-CUS-089 (the tier and its confirmer are STORED; money moves only
#           on `strong` — criteria NAME + DATE OF BIRTH + ONE GOVERNMENT ID, PO
#           2026-08-25 closing OQ-364) · BR-CUS-092 (SSN + driving licence
#           encrypted, LAST FOUR ONLY on every read path) · BR-CUS-019 (the
#           duplicate check is ADVISORY) · BR-CUS-054 (the entity and its link)
#           · BR-CUS-1020 · BR-CUS-1021 · BR-MET-1020 · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 7 (every money action writes audit_log)
#           · hard-won law 1 · law 7 (prove a guard RED first)
# Impacts:  apps/customers/{identity_match,services,selectors,discounts,api}.py
#           · apps/metering/{premises_owners,owner_selectors}.py
#           · migration customers 0036
# ───────────────────────────────────────────────────────
"""**A matcher is a money feature, so every case here is written to fail.**

🔒 The paths under test are SENSITIVE ones (CLAUDE.md): app-layer encryption of
customer PII, and a verdict that gates whether a returning customer's deposit
moves. `HUMAN-REVIEW-PENDING`; the row naming what was shown to the PO in plain
English with a worked figure is in `12-governance/09-human-review-ledger.md`.

THE WORKED CASE, one person followed end to end so a reader can hold it:

    **Rosa Alvarez** closed an account holding **$150.00** of deposit.
    She comes back. She gives the same name, the same date of birth
    **1974-03-02** and the same Social Security number **123-45-6789**.
    All three agree → the match is `strong` → the deposit can follow her.

    **Rosa Alvarez** — a DIFFERENT one — gives the same name and a different
    date of birth. Two of three agree → the match is `weak` → the new account
    opens under its OWN customer number, nothing is merged, and **$150.00**
    stays exactly where it was.

Each case is built so it can only pass for the right reason:

  1 · **THE RAW COLUMN IS READ BACK THROUGH A SECOND CURSOR.** `.values()`
      would run `from_db_value` and decrypt, proving only that the accessor
      works — the trap `test_br_cus_092_ssn_capture.py` names in its own words.
  2 · **THE WEAK CASE IS ASSERTED ON THE MONEY, NOT ON A FLAG.** It is not
      enough that `tier != "strong"`; the carry-forward itself must refuse and
      must show **no figure at all**.
  3 · **THE ABSENT-NEVER-AGREES RULE HAS ITS OWN CASE.** Two customers with no
      date of birth must not be found to agree about it. `None == None` is how
      an empty database becomes a room full of perfect matches.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.db import connection

from apps.customers import discounts, identity_match
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import owner_selectors, premises_owners
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import crypto, errors
from core.pagination import ListParams

from tests.br_cus_1114_fixtures import top_up_homes
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

D = Decimal

# ── the worked case, one number and one date, followed end to end ──────────
NAME = "Alvarez, Rosa"
DOB = "1974-03-02"
SSN = "123-45-6789"
SSN_DIGITS = "123456789"
SSN_LAST4 = "6789"
LICENCE = "TX-DL-4417"
PHONE = "512-555-0142"
DEPOSIT_HELD = D("150.00")  # ❄️ WE-7 / GT-23

#: Every spelling of the secret that must never appear in stored bytes, a
#: payload or an audit blob. `6789` alone is deliberately absent — the last four
#: is what BR-CUS-092(c) allows us to disclose.
FORBIDDEN = (SSN, SSN_DIGITS, "123 45 6789", "12345", "456789", "123-45", "45-6789")


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through real services (DEF-658: never the ORM)
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


def _unit(actor, tenant, *, label="Unit A", premises=None, service_code="electric"):
    premises = premises or make_premises(actor, services_available=[service_code])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service_code=service_code).id)}
    )
    metering_services.ensure_service_point(unit["id"], service_code)
    return unit


def _open(actor, tenant, *, label, name=NAME, identity=None, customer=None, status="active"):
    """An account opened through the REAL door, with a `customer` block.

    ⚠ Through `create_account` and never `Account.objects.create`: the whole
    claim under test is that THE DOOR writes the link, and an ORM insert would
    prove the column and skip the rule (CR-056 §4: *"exactly one function writes
    a customer-to-account link and it runs only inside an import"*).
    """
    unit = _unit(actor, tenant, label=label)
    # ⚠ **`kind` IS STATED, AND SINCE CR-056 W2b IT HAS TO BE.** Every case in
    # this file is about a PERSON — Rosa Alvarez — and until 2026-09-01 the
    # `person` fell out of the model's column default with nobody saying so.
    # `BR-CUS-1022` makes the kind decide which identifier is captured and which
    # test a match is judged on, so a door presenting identity against an
    # unstated kind is now refused by name. The company cases live in
    # `test_cr056_w2b_company_identity.py`.
    # ⚠ **AND SINCE `BR-CUS-1023` (PO 2026-09-01) THE DEFAULT BLOCK CARRIES AN
    # IDENTIFIER TOO.** *"Customer ID - minimum name and one ID - minimum."* A
    # name alone no longer mints a number, so every case in this file that is
    # ABOUT a customer number needs the evidence it always implicitly assumed:
    # Rosa Alvarez gives her phone, which is one of the three the PO named.
    # **The guard is not softened — the fixture now states what it meant.**
    block = (
        customer
        if customer is not None
        else {"display_name": name, "kind": "person", "identity": {"phone": PHONE}}
    )
    if identity is not None:
        block = {**block, "identity": identity}
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": status,
            "opened_at": "2026-07-01",
            "contact": {"full_name": name},
            "customer": block,
        },
    )


def _raw_column(customer_id, column) -> str | None:
    """The bytes actually in the column, with NO field accessor.

    ⚠ `id` is stored un-hyphenated (`uuid7_pk` over a 32-char column), so a
    `str(uuid)` bind matches NOTHING and this probe would report *no row* for a
    row that is right there — a false GREEN. And `CAST(... AS TEXT)` rather
    than `::text`, because this suite runs on SQLite as well as PostgreSQL.
    """
    key = getattr(customer_id, "hex", None) or str(customer_id).replace("-", "")
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT {column} FROM customers WHERE replace(CAST(id AS TEXT), '-', '') = %s",
            [key],
        )
        row = cur.fetchone()
    return row[0] if row else None


def _assert_no_secret_in(blob: object, where: str) -> None:
    text = json.dumps(blob, default=str)
    for spelling in FORBIDDEN:
        assert spelling not in text, f"{where} leaked {spelling!r}: {text[:400]}"


# ═══════════════════════════════════════════════════════════════════════════
# TASK 11 · IDENTITY IS ON THE CUSTOMER, AND IT IS ENCRYPTED
# ═══════════════════════════════════════════════════════════════════════════
def test_task11_the_customer_carries_identity_and_the_raw_column_is_not_the_number(brazos, dana):
    """The four facts land on the customer, and three of them are ciphertext.

    Read RAW through a second cursor, in every spelling — `.values()` would
    decrypt and prove the opposite of the guarantee.
    """
    with tenant_ctx(brazos):
        account = _open(
            dana,
            brazos,
            label="3450 Oak Ridge Dr",
            identity={"date_of_birth": DOB, "ssn": SSN, "driving_licence": LICENCE},
        )
        customer = customers_models.Customer.objects.get(
            id=customers_selectors.customer_for_account(account["id"])["id"]
        )

        # The date of birth is a plain `date` — comparable, and not one of the
        # two identifiers BR-CUS-092 legislates.
        assert customer.date_of_birth.isoformat() == DOB
        # The accessor decrypts.
        assert customer.ssn == SSN
        assert customer.driving_licence == LICENCE

        stored = _raw_column(customer.id, "ssn")

    assert stored, "nothing was stored: the write was dropped, not encrypted"
    for spelling in FORBIDDEN:
        assert spelling not in stored, f"raw column contains {spelling!r}"

    # A real envelope bound to THIS column — not merely something unreadable.
    scheme, kid, nonce, sealed = stored.split(":", 3)
    assert scheme == crypto.SCHEME
    assert kid == crypto.active_kid()
    assert nonce and sealed
    assert crypto.decrypt(stored, context="customers.ssn") == SSN

    # ⚠ The AAD binds it: the same bytes in another column RAISE.
    with pytest.raises(crypto.FieldDecryptionError):
        crypto.decrypt(stored, context="service_requests.ssn")


def test_task11_the_blind_index_is_written_beside_every_ciphertext(brazos, dana):
    """A ciphertext with no token is a customer the matcher cannot see.

    Both halves are asserted because they fail in opposite directions: a token
    with no ciphertext is an equality oracle over a value nobody can read, and a
    ciphertext with no token is an account that is simply unfindable while every
    test about *storage* still passes.
    """
    with tenant_ctx(brazos):
        account = _open(
            dana,
            brazos,
            label="12 Willow Bend",
            identity={"ssn": SSN, "driving_licence": LICENCE, "phone": PHONE},
        )
        customer = customers_models.Customer.objects.get(
            id=customers_selectors.customer_for_account(account["id"])["id"]
        )
        for field in ("ssn", "driving_licence", "phone"):
            token = getattr(customer, identity_match.BIDX_COLUMN[field])
            assert token, f"{field} has ciphertext and no blind index"
            assert token.startswith(crypto.INDEX_SCHEME + ":")
            assert token in crypto.blind_index_candidates(
                getattr(customer, field), context=identity_match.CRYPTO_CONTEXT[field]
            )


def test_task11_hyphens_and_spaces_are_one_identifier(brazos, dana):
    """`123-45-6789` on Tuesday and `123456789` on Thursday are one person.

    Normalisation applies to the INDEX only — what is stored keeps exactly what
    the customer typed, which is asserted here too so a later "tidy up" that
    normalised the stored value would go red.
    """
    with tenant_ctx(brazos):
        account = _open(dana, brazos, label="9 Cedar Ct", identity={"ssn": SSN})
        customer = customers_models.Customer.objects.get(
            id=customers_selectors.customer_for_account(account["id"])["id"]
        )
        assert customer.ssn == SSN, "the stored value was normalised; only the index may be"
        assert getattr(customer, "ssn_bidx") in crypto.blind_index_candidates(
            SSN_DIGITS, context="customers.ssn"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TASK 13 · THE SIGNED CRITERIA — NAME + DATE OF BIRTH + ONE GOVERNMENT ID
# ═══════════════════════════════════════════════════════════════════════════
def test_task13_all_three_agreeing_is_strong_and_nothing_less_is(brazos, dana):
    """`BR-CUS-089`, PO 2026-08-25: *"Name + date of birth + one government ID"*.

    Every combination that is NOT all three is asserted `weak` in the same case,
    because a rule written as three clauses fails by losing one of them and a
    test that only checks the happy path cannot see that.
    """
    with tenant_ctx(brazos):
        _open(
            dana,
            brazos,
            label="3450 Oak Ridge Dr",
            identity={"date_of_birth": DOB, "ssn": SSN, "phone": PHONE},
        )

        strong = identity_match.recognise(
            identity_match.IdentityEvidence(name=NAME, kind="person", date_of_birth=DOB, ssn=SSN)
        )
        assert strong["tier"] == identity_match.TIER_STRONG
        assert strong["matched"]
        assert strong["agreed"] == [
            identity_match.FACT_NAME,
            identity_match.FACT_DOB,
            identity_match.FACT_SSN,
        ]

        # ── and every near miss, each for its own reason ────────────────────
        cases = {
            "wrong date of birth": identity_match.IdentityEvidence(
                name=NAME, kind="person", date_of_birth="1980-01-01", ssn=SSN
            ),
            "no date of birth at all": identity_match.IdentityEvidence(
                name=NAME, kind="person", ssn=SSN
            ),
            "no government id": identity_match.IdentityEvidence(
                name=NAME, kind="person", date_of_birth=DOB
            ),
            "wrong name": identity_match.IdentityEvidence(
                name="Alvarez, Rosita", kind="person", date_of_birth=DOB, ssn=SSN
            ),
            # ⚠ CR-056's R3 names the phone as identity evidence and it is
            # indexed — but BR-CUS-089 says *one government ID*, and a telephone
            # number is not one. A phone hit SURFACES a candidate; it never
            # makes one strong.
            "phone is not a government id": identity_match.IdentityEvidence(
                name=NAME, kind="person", date_of_birth=DOB, phone=PHONE
            ),
        }
        for why, evidence in cases.items():
            verdict = identity_match.recognise(evidence)
            assert verdict["tier"] != identity_match.TIER_STRONG, why
            assert verdict["matched"] is None, why


def test_task13_absent_never_agrees_with_absent(brazos, dana):
    """Two customers with no date of birth do not agree about it.

    `None == None` is how an empty database becomes a room full of perfect
    matches, and it is the single most dangerous line a matcher can contain.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="1 Elm St", identity={"phone": PHONE})
        customer = customers_models.Customer.objects.get(display_name=NAME)
        assert customer.date_of_birth is None
        assert customer.ssn is None

        agreed = identity_match.agreed_facts(
            identity_match.IdentityEvidence(name=NAME, kind="person"), customer
        )
        assert agreed == [identity_match.FACT_NAME], agreed
        assert identity_match.tier_for(agreed, "person") == identity_match.TIER_WEAK


def test_task13_a_name_alone_finds_nobody(brazos, dana):
    """CR-056 §4's whole complaint: a NAME is not identity.

    *"A. Kulkarni and Ajinkya Kulkarni are two landlords and nothing objects."*
    An evidence set holding only a name has nothing to match ON, so it produces
    no candidates at all rather than every namesake in the tenant.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="2 Elm St", identity={"date_of_birth": DOB, "ssn": SSN})
        verdict = identity_match.recognise(
            identity_match.IdentityEvidence(name=NAME, kind="person")
        )
        assert verdict["candidates"] == []
        assert verdict["refusal"] == identity_match.REFUSAL_NO_EVIDENCE


def test_task13_the_matcher_never_emits_probable(brazos, dana):
    """`BR-CUS-089` defines what earns `strong` and says nothing about
    `probable`. A machine handing one out would be minting a threshold nobody
    ruled, so the vocabulary this file can produce is exactly two words."""
    assert identity_match.MATCH_TIERS == discounts.MATCH_TIERS
    assert "probable" in identity_match.MATCH_TIERS
    for agreed in (
        [],
        [identity_match.FACT_NAME],
        [identity_match.FACT_NAME, identity_match.FACT_DOB],
        [identity_match.FACT_NAME, identity_match.FACT_SSN],
        [identity_match.FACT_PHONE],
    ):
        assert identity_match.tier_for(agreed, "person") == identity_match.TIER_WEAK
    assert (
        identity_match.tier_for(
            [identity_match.FACT_NAME, identity_match.FACT_DOB, identity_match.FACT_LICENCE],
            "person",
        )
        == identity_match.TIER_STRONG
    )


def test_task13_two_strong_matches_refuse_rather_than_pick(brazos, dana):
    """If the evidence is strong against TWO customers the database is telling
    us two people share a name, a date of birth and a government identifier.
    Choosing the older row would move a deposit on a coin toss."""
    with tenant_ctx(brazos):
        _open(dana, brazos, label="7 Oak", identity={"date_of_birth": DOB, "ssn": SSN})
        # A second customer with the same three facts. Written through the ORM
        # ON PURPOSE: the service layer would recognise and link instead, and
        # the state under test is the one no constraint forbids (see migration
        # 0036 on why there is no unique index on `ssn_bidx`).
        twin = customers_models.Customer.objects.create(
            tenant_id=brazos.id,
            customer_no="C-99999",
            display_name=NAME,
            date_of_birth=customers_models.Customer.objects.get(display_name=NAME).date_of_birth,
        )
        identity_match.set_identifier(twin, "ssn", SSN)
        twin.save()

        verdict = identity_match.recognise(
            identity_match.IdentityEvidence(name=NAME, kind="person", date_of_birth=DOB, ssn=SSN)
        )
        assert verdict["matched"] is None
        assert verdict["refusal"] == identity_match.REFUSAL_NOT_STRONG
        assert len([c for c in verdict["candidates"] if c["tier"] == "strong"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# TASK 14 · THE DEPOSIT MOVES ON `strong` AND ON NOTHING ELSE
# ═══════════════════════════════════════════════════════════════════════════
def _returning(actor, tenant, *, identity, label="3450 Oak Ridge Dr"):
    """A prior account holding the frozen $150.00, closed through the real
    move-out flow, whose customer carries the identity given."""
    prior = _open(actor, tenant, label=label, identity=identity)
    customers_models.Account.objects.filter(id=prior["id"]).update(deposit_on_file=DEPOSIT_HELD)
    customers_services.move_out(actor, prior["id"], {"moved_out_on": "2026-08-15"})
    return prior


def test_task14_a_strong_match_at_the_counter_can_carry_the_deposit(brazos, dana, audit_rows):
    """**$150.00 follows Rosa Alvarez, and the door she came through is a
    counter rather than an application form.**

    This is the hole CR-056 W3 closes. `discounts._stored_match` read
    `service_requests.match_tier` and NOTHING else, so an account opened at the
    counter had no stored tier at all and the carry-forward refused — however
    well the clerk had identified the person in front of them.
    """
    with tenant_ctx(brazos):
        _returning(dana, brazos, identity={"date_of_birth": DOB, "ssn": SSN})
        new_account = _open(
            dana,
            brazos,
            label="88 Maple Ave",
            identity={"date_of_birth": DOB, "ssn": SSN},
        )
        customer = customers_selectors.customer_for_account(new_account["id"])

        # The link records HOW, with a human confirmer (BR-CUS-089).
        link = customers_models.CustomerAccount.objects.get(
            customer_id=customer["id"], account_id=new_account["id"]
        )
        assert link.match_tier == identity_match.TIER_STRONG
        assert link.match_confirmed_by_id == dana.id
        assert link.match_confirmed_at is not None
        assert "date of birth" in link.match_basis

        offer = discounts.carry_forward_offer(dana, customer["id"])

    assert offer["refused"] is None
    assert offer["offered"] is True
    assert offer["match"]["source"] == "account_link"
    assert offer["match"]["tier"] == "strong"


def test_task14_a_weak_match_refuses_and_shows_no_figure(brazos, dana):
    """**TC-MVI-3, reached from the counter: money never moves on a weak match.**

    Asserted on the MONEY and not on a flag: it is not enough that the tier is
    not `strong` — the offer must refuse, and it must show **no figure at all**,
    because a refused offer that still printed `$150.00` is an invitation to
    type it in by hand.
    """
    with tenant_ctx(brazos):
        _returning(dana, brazos, identity={"date_of_birth": DOB, "ssn": SSN})
        # A DIFFERENT Rosa Alvarez: same name, different date of birth.
        other = _open(
            dana,
            brazos,
            label="14 Birch Way",
            identity={"date_of_birth": "1991-11-30", "ssn": "987-65-4321"},
        )
        customer = customers_selectors.customer_for_account(other["id"])
        link = customers_models.CustomerAccount.objects.get(
            customer_id=customer["id"], account_id=other["id"]
        )
        assert link.match_tier is None, "a weak match must not store a tier"

        offer = discounts.carry_forward_offer(dana, customer["id"])

    assert offer["offered"] is False
    assert offer["refused"]["code"] == discounts.REFUSAL_NO_STORED_MATCH
    assert offer["amount"]["stored"] is None
    assert offer["amount"]["display"] is None
    assert "150" not in json.dumps(offer, default=str)


def test_task14_an_import_link_can_never_earn_a_tier(brazos, dana):
    """A spreadsheet column may not move a deposit.

    The import matches on `external_ref` — the LEGACY system's id, a
    reconciliation key. `link_customer` called without identity evidence and
    without an actor stores no tier, which refuses the carry-forward.

    ⚠ **AMENDED 2026-09-01 (`BR-CUS-1023`) — THE CLAIM IS UNCHANGED AND THE
    SETUP IS STRONGER.** A row carrying a name and a legacy reference and
    nothing else no longer creates a customer at all, so this case now proves
    the tier rule on the harder input: an import mapping that DOES carry an
    identifier creates the row and STILL earns no tier, because a spreadsheet
    column is not a human confirming an identity. The weaker input is asserted
    beneath it.
    """
    with tenant_ctx(brazos):
        account = _open(dana, brazos, label="4 Pine")
        linked = customers_services.link_customer(
            account_id=account["id"],
            external_ref="CUST-118",
            display_name=NAME,
            kind="person",
            identity={"phone": PHONE},
        )
        link = customers_models.CustomerAccount.objects.get(
            customer_id=linked["id"], account_id=account["id"]
        )
        assert link.match_tier is None
        assert link.match_confirmed_by_id is None

        # And the ordinary import row — a name, a legacy ref, no identity —
        # now creates NOBODY, which is the same rule one step stronger.
        nothing = customers_services.link_customer(
            account_id=account["id"], external_ref="CUST-999", display_name="Ref Only"
        )
        assert nothing["id"] is None
        assert nothing["not_created"]["missing"] == "customer_kind_missing"


# ═══════════════════════════════════════════════════════════════════════════
# TASK 15/16/17 · EVERY DOOR WRITES THE LINK
# ═══════════════════════════════════════════════════════════════════════════
def test_task16_an_account_opened_at_the_counter_gets_a_customer_number(brazos, dana):
    """CR-056 §4: *"an account opened at the counter shows a dash where its
    number should be."* It does not any more, and the number is allocated
    INSIDE the create so one can never exist unnumbered."""
    with tenant_ctx(brazos):
        account = _open(dana, brazos, label="21 Ash Ln")
        customer = customers_selectors.customer_for_account(account["id"])
        assert customer is not None
        row = customers_models.Customer.objects.get(id=customer["id"])
        assert row.customer_no, "a customer exists with no number"
        assert row.customer_no.startswith("C-")


def test_task17_the_master_account_door_links_its_customer(brazos, dana):
    """CR-056 §4, measured: *"Every Master Account in the product has a blank
    customer column."* The master door links the owner where the payload names
    one WITH an identifier.

    ⚠ **AMENDED 2026-09-01 — `BR-CUS-1023` SUPERSEDES THE FALLBACK THIS CASE
    USED TO ASSERT.** It read the premises' `owner_manager` free-text name and
    asserted a customer row appeared from it. The PO ruled that a name alone no
    longer creates a Customer number, and a premises' owner name is exactly the
    thing that ruling is about: free text that may name a person or a limited
    company, with nothing in it saying which. So the door now opens the account
    and mints NOTHING, and says which fact was missing.

    **The account still opens** — that is the half that must never move, and it
    is asserted here rather than assumed.
    """
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, services_available=["electric"], owner_manager="Kulkarni, Ajinkya"
        )
        common = make_unit(dana, premises["id"], label="Hallway", is_common_area=True)
        metering_services.assign_unit_plan(dana, common["id"], {"tariff_id": str(_plan(brazos).id)})
        metering_services.ensure_service_point(common["id"], "electric")
        # ⛔ **AMENDED AGAIN 2026-09-01 — `BR-CUS-1024`.** The paragraph above
        # is still true about the free-text owner name; what changed within the
        # hour is that such a door no longer opens an account either. PO
        # verbatim: *"Without identifier we cannot create Customer ID or master
        # account ot regular account"*. So this case does what its own NAME
        # says — it proves the master door LINKS ITS CUSTOMER — by giving the
        # owner the identifier the rule now requires.
        # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
        top_up_homes(dana, premises["id"])
        master = customers_services.create_master_account(
            dana,
            {
                "premises_id": str(premises["id"]),
                "account_type": "residential",
                "opened_at": "2026-07-01",
                "customer": {
                    "display_name": "Kulkarni, Ajinkya",
                    "kind": "person",
                    "identity": {"ssn": "555-01-9987"},
                },
            },
        )
        customer = customers_selectors.customer_for_account(master["id"])
        assert customers_models.Account.objects.filter(pk=master["id"]).exists()

        # AND WITH AN IDENTIFIER THE DOOR LINKS, which is what CR-056 §4's
        # *"every Master Account in the product has a blank customer column"*
        # was measured against.
        assert customer is not None
        assert master["customer_no"]
        assert master["customer_outcome"] == "created"
        assert (
            customers_models.Customer.objects.filter(display_name="Kulkarni, Ajinkya").count()
            == 1
        )

    # AND A FREE-TEXT OWNER NAME ALONE STILL MINTS NOTHING — it is now refused
    # at the door rather than skipped past, and that is asserted where the
    # refusal lives (`test_cr058_w1_one_customer_every_door.py::test_tc8`).
    # `.get` because the key is ABSENT rather than null when nothing failed —
    # `_customer_match_payload`'s own posture: *"a key that is always there and
    # usually null reads as a feature that is always failing."*
    assert master.get("customer_not_created") is None


def test_task15_an_unknown_key_inside_the_customer_block_is_refused_by_name(brazos, dana):
    """This block carries government identifiers, so a typo'd key that is
    silently dropped means a clerk believes an SSN was stored when it was not —
    `DEF-632`'s exact shape, one level up."""
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, label="5 Spruce")
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.create_account(
                dana,
                {
                    "unit_id": str(unit["id"]),
                    "account_type": "residential",
                    "opened_at": "2026-07-01",
                    "customer": {"display_name": NAME, "identity": {"social_security": SSN}},
                },
            )
        assert "identity.social_security" in str(caught.value.field_errors)


# ═══════════════════════════════════════════════════════════════════════════
# TASK 18 · THE OWNER→CUSTOMER SHORTCUT IS RULED OUT
# ═══════════════════════════════════════════════════════════════════════════
def test_task18_the_owner_door_refuses_customer_id_by_name(brazos, dana):
    """`BR-MET-1020`. Two paths reached the same person and one skipped the
    account — the only row that holds a balance. The refusal names the path
    that works, because a refusal that only says *no* leaves the clerk with the
    same job and no way to do it."""
    with tenant_ctx(brazos):
        account = _open(dana, brazos, label="6 Fir")
        customer = customers_selectors.customer_for_account(account["id"])
        category = tenancy_models.PremisesOwnerCategory.objects.filter(
            tenant_id=brazos.id, active=True
        ).first()
        with pytest.raises(errors.ValidationError) as caught:
            premises_owners.create_premises_owner(
                dana,
                {
                    "name": "Kulkarni, Ajinkya",
                    "category_code": category.code,
                    "customer_id": customer["id"],
                },
            )
        detail = str(caught.value.field_errors)
        assert "customer_id" in detail
        assert "master account" in detail, "the refusal does not name the path that works"


def test_task18_the_owner_read_reaches_the_customer_through_the_account(brazos, dana):
    """The answer comes from the ACCOUNT, and a value left in the retired
    column is STATED rather than silently dropped."""
    with tenant_ctx(brazos):
        account = _open(dana, brazos, label="8 Holly")
        customer = customers_selectors.customer_for_account(account["id"])
        category = tenancy_models.PremisesOwnerCategory.objects.filter(
            tenant_id=brazos.id, active=True
        ).first()
        owner = premises_owners.create_premises_owner(
            dana, {"name": "Kulkarni, Ajinkya", "category_code": category.code}
        )
        row = models_owner(owner["id"], brazos)
        row.master_account_id = account["id"]
        row.save(update_fields=["master_account_id"])

        served = owner_selectors.owner_detail_dict(row)
        assert served["customer_id"] == customer["id"]
        assert served["customer_no"]
        assert served["customer_expanded"] is True
        assert served["customer_link_column_ignored"] is False

        # The LIST does not expand, and says so rather than serving a null that
        # reads as "this owner has nobody".
        listed = owner_selectors.owner_detail_dict(row, with_account=False)
        assert listed["customer_id"] is None
        assert listed["customer_expanded"] is False


def models_owner(owner_id, tenant):
    from apps.metering import models as metering_models

    return metering_models.PremisesOwner.objects.get(tenant_id=tenant.id, id=owner_id)


# ═══════════════════════════════════════════════════════════════════════════
# TASK 25 · THE CUSTOMERS LIST — AND WHAT IT MAY NOT SEND TO A BROWSER
# ═══════════════════════════════════════════════════════════════════════════
def test_task25_the_list_finds_a_person_by_number_name_and_phone(brazos, dana):
    """One box, and a clerk holding a scrap of paper does not know which of
    those the marks on it are."""
    with tenant_ctx(brazos):
        account = _open(
            dana,
            brazos,
            label="10 Juniper",
            identity={"date_of_birth": DOB, "ssn": SSN, "phone": PHONE},
        )
        customer = customers_selectors.customer_for_account(account["id"])
        number = customers_models.Customer.objects.get(id=customer["id"]).customer_no

        by_name = customers_selectors.customer_list(ListParams(q="Alvarez"))
        by_number = customers_selectors.customer_list(ListParams(q=number))
        by_phone = customers_selectors.customer_list(ListParams(q=PHONE))
        # ⚠ The phone leg goes through the BLIND INDEX, so it is an EQUALITY
        # probe. Half a number finds nobody, and that is a property of the
        # encryption rather than a bug in the search box.
        by_half = customers_selectors.customer_list(ListParams(q="512-555"))

    assert [row["id"] for row in by_name] == [customer["id"]]
    assert [row["id"] for row in by_number] == [customer["id"]]
    assert [row["id"] for row in by_phone] == [customer["id"]]
    assert by_half == []


def test_task25_the_list_row_never_carries_a_full_identifier(brazos, dana):
    """`BR-CUS-092(c)` — *"the full value is never in a list response"*.

    A number that reaches the browser is in devtools, in a proxy log and in the
    HAR file attached to a ticket, whatever the screen chooses to draw.
    """
    with tenant_ctx(brazos):
        _open(
            dana,
            brazos,
            label="11 Laurel",
            identity={"date_of_birth": DOB, "ssn": SSN, "driving_licence": LICENCE},
        )
        rows = customers_selectors.customer_list(ListParams())

    _assert_no_secret_in(rows, "the customers list")
    row = rows[0]
    assert row["identity"]["ssn_held"] is True
    assert row["identity"]["ssn_last4"] == SSN_LAST4
    assert row["identity"]["driving_licence_last4"] == "4417"


def test_task25_the_list_shows_every_account_one_person_holds(brazos, dana):
    """The landlord case, which is the whole reason `customer_accounts` is N:M
    (BR-CUS-054, US-CUS-019 TC-2: one ref on three rows → ONE customer row)."""
    with tenant_ctx(brazos):
        first = _open(dana, brazos, label="A1 Duplex", identity={"ssn": SSN, "date_of_birth": DOB})
        second = _open(dana, brazos, label="A2 Duplex", identity={"ssn": SSN, "date_of_birth": DOB})
        rows = customers_selectors.customer_list(ListParams(q="Alvarez"))

    assert len(rows) == 1, "one person, not two"
    assert rows[0]["account_count"] == 2
    numbers = {entry["account_no"] for entry in rows[0]["accounts"]}
    assert numbers == {first["account_no"], second["account_no"]}


# ═══════════════════════════════════════════════════════════════════════════
# HARD RULE 7 · A RECOGNITION DECISION IS A DECISION ABOUT MONEY
# ═══════════════════════════════════════════════════════════════════════════
def test_rule7_both_the_recognition_and_the_refusal_write_audit_log(brazos, dana, audit_rows):
    """A refusal is the decision that a returning customer's **$150.00** stayed
    where it was. A refusal that leaves no trace is a figure nobody can
    reconcile — and the blob carries the number and the last four, never the
    identifier."""
    with tenant_ctx(brazos):
        _open(dana, brazos, label="12 Rowan", identity={"date_of_birth": DOB, "ssn": SSN})
        _open(
            dana,
            brazos,
            label="13 Rowan",
            identity={"date_of_birth": DOB, "ssn": SSN},
        )
        _open(
            dana,
            brazos,
            label="14 Rowan",
            identity={"date_of_birth": "1991-11-30", "ssn": "987-65-4321"},
        )

    actions = audit_actions(audit_rows)
    assert "customer.identity_recognised" in actions
    assert "customer.identity_not_recognised" in actions
    _assert_no_secret_in([row.get("details") for row in audit_rows], "the audit trail")


def test_hard_rule1_a_customer_of_another_tenant_is_never_a_candidate(brazos, dana, lonestar):
    """Hard rule 1 — no cross-tenant queryset. The matcher's probes are the
    newest queries in this module and the easiest place to forget it."""
    with tenant_ctx(lonestar):
        customers_models.Customer.objects.create(
            tenant_id=lonestar.id,
            customer_no="C-70001",
            display_name=NAME,
            date_of_birth="1974-03-02",
        )
        foreign = customers_models.Customer.objects.get(customer_no="C-70001")
        identity_match.set_identifier(foreign, "ssn", SSN)
        foreign.save()

    with tenant_ctx(brazos):
        verdict = identity_match.recognise(
            identity_match.IdentityEvidence(name=NAME, kind="person", date_of_birth=DOB, ssn=SSN)
        )
        assert verdict["candidates"] == []
        assert customers_selectors.customer_list(ListParams(q="Alvarez")) == []
