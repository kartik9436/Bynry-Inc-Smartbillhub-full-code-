# ── Trace ──────────────────────────────────────────────
# Change:   CR-056 W2b — IDENTITY IS PER KIND. A person keeps BR-CUS-089's
#           three-part test; a COMPANY is matched on its name and its Tax ID.
# Rules:    BR-CUS-1022 (identity is per kind — PO 2026-09-01, verbatim:
#           *"Customer can be person or company - in case of person , if we have
#           SSN, or DL or Phone number, we create the Customer ID and attached
#           these to custoemr ID ; if it is Company then we ask for Tax ID"*) ·
#           BR-CUS-089 (NAME + DATE OF BIRTH + ONE GOVERNMENT ID — signed
#           2026-08-25, NARROWED onto PERSONS by the decision log of
#           2026-09-01) · BR-CUS-092 / OQ-016 CLOSED (app-layer encryption,
#           LAST FOUR ONLY on every read path) · BR-CUS-019 (the duplicate
#           check is ADVISORY) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           hard rule 7 (every money action writes audit_log) · law 7 (prove a
#           guard RED first) · B14 rule 32 (no rule id in clerk copy)
# Impacts:  apps/customers/{identity_match,services,selectors}.py ·
#           apps/customers/models.Customer.tax_id · migration customers 0038
# ───────────────────────────────────────────────────────
"""**A company could not be recognised at all, and the signed rule is why.**

🔒 The paths under test are SENSITIVE ones (CLAUDE.md): app-layer encryption of
customer PII, and a verdict that gates whether a returning customer's deposit
moves. `HUMAN-REVIEW-PENDING`; the row naming what was shown to the PO in plain
English with a worked figure is in `12-governance/09-human-review-ledger.md`.

THE COLLISION, WHICH IS THE WHOLE REASON THIS FILE EXISTS
=========================================================
`BR-CUS-089` is signed and verbatim: a strong match is **name AND date of birth
AND one government identifier**, PO 2026-08-25. **A company has no date of
birth.** Read literally the signed rule made every company permanently
unmatchable — `tier_for` could not return `strong` for one however completely it
was identified — and the deposit carry-forward that rides on `strong` could
therefore never run for a business. Nobody intended that; the PO's ruling of
2026-09-01 exposed it, and the decision log narrows `BR-CUS-089` onto PERSONS
rather than reversing it.

THE WORKED CASE, one business followed end to end so a reader can hold it:

    **Silver Creek Duplex Holdings LLC** closed an account holding **$150.00**
    of deposit. It comes back. The same name and the same Tax ID
    **12-3456789** are given. Both agree → the match is `strong` → the
    deposit can follow the business.

    **Silver Creek Duplex Holdings LLC** — a DIFFERENT one, or a mistyped
    number — gives the same name and Tax ID **98-7654321**. One of two
    agrees → the match is `weak` → the new account opens under its OWN
    customer number, nothing is merged, **$150.00** stays exactly where it
    was, and the screen shows **no figure at all**.

Each case is written so it can only pass for the right reason:

  1 · **THE RAW COLUMN IS READ BACK THROUGH A SECOND CURSOR.** `.values()`
      would run `from_db_value` and decrypt, proving only that the accessor
      works rather than that anything was encrypted.
  2 · **THE PERSON'S TEST IS ASSERTED TO STILL REFUSE A COMPANY.** It is not
      enough that a company can now be strong; a company must NOT become strong
      on a person's evidence, or the narrowing has become a loosening.
  3 · **THE WEAK CASE IS ASSERTED ON THE MONEY, NOT ON A FLAG**, and on the
      ABSENCE of the figure in the refusal wording.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.db import connection

from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import crypto, errors
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

D = Decimal

# ── the worked case, one business and one number, followed end to end ───────
COMPANY = "Silver Creek Duplex Holdings LLC"
TAX_ID = "12-3456789"
TAX_ID_DIGITS = "123456789"
TAX_ID_LAST4 = "6789"
OTHER_TAX_ID = "98-7654321"
PERSON = "Alvarez, Rosa"
PERSON_DOB = "1974-03-02"
PERSON_SSN = "555-44-3333"
DEPOSIT_HELD = D("150.00")  # ❄️ WE-7 / GT-23

#: Every spelling of the identifier that must never appear in stored bytes, a
#: payload or an audit blob. `6789` alone is deliberately absent — the last four
#: is what BR-CUS-092(c) allows us to disclose.
#:
#: ⚠ **NOTHING SHORTER THAN SEVEN CHARACTERS IS LISTED, DELIBERATELY.** These
#: rows carry uuids, and a uuid is hex: a five-digit run like `12345` occurs in
#: one by chance often enough to turn this into a test that fails for a reason
#: that is not a leak, which is worse than one that never fails at all.
FORBIDDEN = (TAX_ID, TAX_ID_DIGITS, "12 3456789", "3456789", "12-345")


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


def _unit(actor, tenant, *, label="Unit A", service_code="electric"):
    premises = make_premises(actor, services_available=[service_code])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service_code=service_code).id)}
    )
    metering_services.ensure_service_point(unit["id"], service_code)
    return unit


#: ⛔ **AN ACCOUNT NEEDS AN IDENTIFIER FROM 2026-09-01 (`BR-CUS-1024`).** PO
#: verbatim: *"Without identifier we cannot create Customer ID or master account
#: ot regular account"*, superseding that morning's *"an account may still be
#: opened"*. Every case in this file is about what `link_customer` DOES with a
#: company's evidence, and none is about whether the door opens — so `_open`
#: carries an identifier for the ACCOUNT and each case then exercises the link
#: it actually means to test. `test_cr058_w1_one_customer_every_door.py::test_tc8`
#: is where the refusal itself is asserted.
#:
#: ⚠ **THE IDENTIFIER FOLLOWS THE KIND, BECAUSE THE RULE DOES.** A person is
#: opened on a PHONE — enough to create a number, never enough to make a match
#: `strong`, never enough to REUSE one — so it identifies the party at the door
#: and touches none of this file's assertions. **A COMPANY CANNOT USE A PHONE**
#: (`BR-CUS-1023`: a business is asked for its Tax ID and nothing else, because
#: a business's phone is answered by whoever is at the desk), so it is opened on
#: a Tax ID of its own — deliberately NOT `TAX_ID`, which is the value this
#: file's matching cases assert about.
OPENING_PHONE = "+1 (512) 555-0143"
OPENING_TAX_ID = "55-0001430"


def _open(actor, tenant, *, label, name=COMPANY, kind="company", identity=None, status="active"):
    """An account opened through the REAL door, with a `customer` block.

    Through `create_account` and never `Account.objects.create`: the claim under
    test is that THE DOOR captures per kind, and an ORM insert would prove the
    column and skip the rule.
    """
    unit = _unit(actor, tenant, label=label)
    block: dict[str, object] = {"display_name": name}
    if kind is not None:
        block["kind"] = kind
    if identity is not None:
        block["identity"] = identity
    elif kind == "company":
        # `BR-CUS-1024` — the door needs one, and for a business that is the Tax
        # ID and nothing else (`BR-CUS-1023`). See `OPENING_TAX_ID` above.
        block["identity"] = {"tax_id": OPENING_TAX_ID}
    elif kind is not None:
        # A person, opened on a phone; see `OPENING_PHONE` above. A case that
        # states NO kind still presents none, because that case is about exactly
        # that and must keep meeting the door's own refusal.
        block["identity"] = {"phone": OPENING_PHONE}
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            # `residential` because it is the category every test tenant seeds;
            # the account's category and the customer's KIND are two facts and
            # CR-033 §4 is explicit that collapsing them would lose one — a
            # residential account can be held by a business (a landlord).
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
    row that is right there — a false GREEN. And `CAST(... AS TEXT)` rather than
    `::text`, because this suite runs on SQLite as well as PostgreSQL.
    """
    key = getattr(customer_id, "hex", None) or str(customer_id).replace("-", "")
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT {column} FROM customers WHERE replace(CAST(id AS TEXT), '-', '') = %s",
            [key],
        )
        row = cur.fetchone()
    return row[0] if row else None


def _assert_no_identifier_in(blob: object, where: str) -> None:
    text = json.dumps(blob, default=str)
    for spelling in FORBIDDEN:
        assert spelling not in text, f"{where} leaked {spelling!r}: {text[:400]}"


def _customer(name=COMPANY):
    return customers_models.Customer.objects.get(display_name=name)


# ═══════════════════════════════════════════════════════════════════════════
# THE COLUMN — a company's Tax ID is on the CUSTOMER, and it is encrypted
# ═══════════════════════════════════════════════════════════════════════════
def test_the_tax_id_lands_on_the_customer_and_the_raw_column_is_not_the_number(brazos, dana):
    """The Tax ID is stored, the accessor decrypts, and the BYTES are not it.

    ⚠ **AND IT IS NOT `tenancy.ein`.** That column is the UTILITY's own tax
    number on another module's table; this is a fact about a customer. The test
    reads `customers.tax_id` by name through a raw cursor, so it cannot pass by
    finding the tenant's.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="1408 Elm Street", identity={"tax_id": TAX_ID})
        customer = _customer()

        assert customer.kind == "company"
        assert customer.tax_id == TAX_ID  # the accessor decrypts

        raw = _raw_column(customer.id, "tax_id")
        assert raw, "no ciphertext was written at all"
        for spelling in FORBIDDEN:
            assert spelling not in raw, f"the stored bytes contain {spelling!r}"
        assert crypto.is_ciphertext(raw), raw[:40]


def test_the_blind_index_is_written_beside_the_ciphertext_and_folds_the_hyphen(brazos, dana):
    """A ciphertext with no token is unmatchable; a token with no ciphertext is
    an equality oracle. They are written together or not at all.

    And `12-3456789` typed on Tuesday must find `123456789` typed on Thursday —
    `crypto.normalise_identifier` folds the punctuation into the INDEX while the
    stored value keeps exactly what the clerk typed.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="12 Oak", identity={"tax_id": TAX_ID})
        customer = _customer()

        token = _raw_column(customer.id, "tax_id_bidx")
        assert token and token.startswith("bix1:"), token
        for spelling in FORBIDDEN:
            assert spelling not in token, f"the index token contains {spelling!r}"

        unpunctuated = crypto.blind_index_candidates(
            TAX_ID_DIGITS, context=identity_match.CRYPTO_CONTEXT["tax_id"]
        )
        assert token in unpunctuated, "the hyphen changed the token"


def test_a_tax_id_cannot_be_lifted_into_another_column(brazos, dana):
    """The ciphertext is bound to the column it was written for.

    `core.crypto` binds additional authenticated data to `crypto_context`, so a
    value moved from `customers.tax_id` into `customers.ssn` RAISES instead of
    decrypting. Asserted on the TOKENS, which is the same binding one layer up:
    the same number indexes differently in the two columns, so a Tax ID can
    never be found by an SSN probe.
    """
    as_tax = crypto.blind_index(TAX_ID, context=identity_match.CRYPTO_CONTEXT["tax_id"])
    as_ssn = crypto.blind_index(TAX_ID, context=identity_match.CRYPTO_CONTEXT["ssn"])
    assert as_tax and as_ssn and as_tax != as_ssn


# ═══════════════════════════════════════════════════════════════════════════
# THE VERDICT — a company is strong on NAME + TAX ID, and on nothing else
# ═══════════════════════════════════════════════════════════════════════════
def test_a_company_is_strong_on_name_and_tax_id(brazos, dana):
    """The ruling, built: *"if it is Company then we ask for Tax ID"*.

    ⚠ **THIS IS THE CASE THAT COULD NOT PASS BEFORE CR-056 W2b**, and not
    because of a missing column: `tier_for` required a DATE OF BIRTH, so a
    company presenting a perfectly correct Tax ID scored `weak` for ever.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="8 Cedar", identity={"tax_id": TAX_ID})

        verdict = identity_match.recognise(
            identity_match.IdentityEvidence(name=COMPANY, kind="company", tax_id=TAX_ID)
        )
        assert verdict["tier"] == identity_match.TIER_STRONG
        assert verdict["matched"]
        assert verdict["agreed"] == [identity_match.FACT_NAME, identity_match.FACT_TAX_ID]
        # B14 rule 32 — clerk copy carries no rule id and no internal code.
        assert verdict["basis"] == "matched on name and Tax ID"


def test_every_near_miss_for_a_company_is_weak_each_for_its_own_reason(brazos, dana):
    """A company must fail for the RIGHT reason, one reason at a time."""
    with tenant_ctx(brazos):
        _open(dana, brazos, label="9 Cedar", identity={"tax_id": TAX_ID})

        cases = {
            "wrong tax id": identity_match.IdentityEvidence(
                name=COMPANY, kind="company", tax_id=OTHER_TAX_ID
            ),
            "no tax id at all": identity_match.IdentityEvidence(name=COMPANY, kind="company"),
            "wrong name": identity_match.IdentityEvidence(
                name="Silver Creek Duplex Holdings Ltd", kind="company", tax_id=TAX_ID
            ),
            # A phone is on both kinds' capture lists and is a government
            # identifier for neither. It SURFACES a candidate; it never makes
            # one strong.
            "phone is not a government id": identity_match.IdentityEvidence(
                name=COMPANY, kind="company", phone="512-555-0199"
            ),
        }
        for why, evidence in cases.items():
            verdict = identity_match.recognise(evidence)
            assert verdict["tier"] != identity_match.TIER_STRONG, why
            assert verdict["matched"] is None, why


def test_neither_kind_borrows_the_others_criteria(brazos, dana):
    """The narrowing must not become a loosening, in EITHER direction.

    A company may not become strong on a person's three facts, and a person may
    not become strong on a Tax ID. Asserted on `tier_for` directly, because that
    is the one function the rule lives in and a later edit that unions the two
    lists would pass every end-to-end case here.
    """
    person_facts = [
        identity_match.FACT_NAME,
        identity_match.FACT_DOB,
        identity_match.FACT_SSN,
    ]
    company_facts = [identity_match.FACT_NAME, identity_match.FACT_TAX_ID]

    assert identity_match.tier_for(person_facts, "person") == identity_match.TIER_STRONG
    assert identity_match.tier_for(person_facts, "company") == identity_match.TIER_WEAK
    assert identity_match.tier_for(company_facts, "company") == identity_match.TIER_STRONG
    assert identity_match.tier_for(company_facts, "person") == identity_match.TIER_WEAK
    # An unstated kind earns nothing, whatever agreed.
    assert identity_match.tier_for(person_facts, None) == identity_match.TIER_WEAK
    assert identity_match.tier_for(company_facts, None) == identity_match.TIER_WEAK


def test_a_person_and_a_company_of_the_same_name_are_never_one_party(brazos, dana):
    """A name agreeing across two kinds is the fact that would fool a human.

    The landlord and the limited company he trades through stay two rows, and
    the person is not even offered as a candidate for the company's evidence.
    """
    with tenant_ctx(brazos):
        # ⚠ **BOTH SIDES NOW CARRY AN IDENTIFIER (`BR-CUS-1023`, 2026-09-01).**
        # A name alone mints no number, so a case about TWO ROWS existing has
        # to give each row the evidence that creates it — the person a phone,
        # the business its Tax ID. The claim under test is unchanged: the two
        # kinds are never merged, whatever they are called.
        _open(
            dana, brazos, label="10 Cedar", name=COMPANY, kind="person",
            identity={"phone": "512-555-0142"},
        )
        _open(
            dana, brazos, label="11 Cedar", name=COMPANY, kind="company",
            identity={"tax_id": TAX_ID},
        )

        rows = customers_models.Customer.objects.filter(display_name=COMPANY)
        assert rows.count() == 2, "the two kinds were merged into one row"

        candidates = identity_match.find_candidates(
            identity_match.IdentityEvidence(name=COMPANY, kind="company", tax_id=TAX_ID)
        )
        assert all(row.kind == "company" for row in candidates), [r.kind for r in candidates]


# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE FOLLOWS THE KIND — and refuses BY NAME, never by dropping a value
# ═══════════════════════════════════════════════════════════════════════════
def test_a_company_is_not_asked_for_a_driving_licence(brazos, dana):
    """*"Asking for both and leaving one blank turns a rule into a habit."*

    Refused BY NAME rather than ignored: a dropped key means a clerk believes a
    licence was stored when it was not, which is DEF-632's shape one level up.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            _open(
                dana,
                brazos,
                label="12 Cedar",
                identity={"driving_licence": "TX-DL-4417"},
            )
        assert caught.value.message_key == "customers.customer.identity_not_asked_of_kind"
        assert customers_models.Customer.objects.filter(display_name=COMPANY).count() == 0


def test_a_person_is_not_asked_for_a_tax_id(brazos, dana):
    """The same rule, the other way round — a rule that only runs one way is
    half a rule."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            _open(
                dana,
                brazos,
                label="13 Cedar",
                name=PERSON,
                kind="person",
                identity={"date_of_birth": PERSON_DOB, "tax_id": TAX_ID},
            )
        assert caught.value.message_key == "customers.customer.identity_not_asked_of_kind"


def test_identity_without_a_kind_is_refused_and_the_account_is_not_opened(brazos, dana):
    """CR-056 W2b's judgment, asserted: **refuse the identity, never the account.**

    A government identifier filed under a party nobody has classified is stored
    where the matcher for the other kind never looks. So a door presenting one
    against an unstated kind is refused by name.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            _open(dana, brazos, label="14 Cedar", kind=None, identity={"tax_id": TAX_ID})
        assert caught.value.message_key == "customers.customer.kind_required_for_identity"


def test_a_door_with_no_identity_still_opens_and_records_that_nobody_stated_a_kind(brazos, dana):
    """The other half of the same judgment, and the PO's own reason for it.

    *A duplicate identifier refuses to LINK and never refuses to SAVE* — so
    refusing to open an account over a missing dropdown would be the same
    one-way door in a different coat. **The account opens.**

    ⚠ **AMENDED 2026-09-01 — `BR-CUS-1023` REPLACED THE SECOND HALF OF THIS
    CASE.** It used to assert that a door presenting no identity created a
    customer row and fell back to `person`, recorded as `kind_defaulted`. The
    PO then ruled that **a name alone no longer creates a Customer number at
    all**, so there is no row to carry a fallback: the door opens the account
    and names what was missing.

    `kind_defaulted` is NOT dead — it still fires wherever a row IS created
    without a stated kind, which today is the import path carrying a mapped
    identifier. The two halves of the original judgment survive intact: the
    account opens, and nothing is decided silently.
    """
    with tenant_ctx(brazos):
        # ⛔ `BR-CUS-1024` (2026-09-01) — a door stating no kind now cannot open
        # an account at all, so the account this case links against is opened
        # with a kind and a phone. **The claim under test is untouched**: it is
        # about what `link_customer` does with a name that states no kind, and
        # that is exercised directly below, which is also where it always lived.
        account = _open(dana, brazos, label="15 Cedar", name="Nobody Said")
        assert account["account_no"]
        link = customers_services.link_customer(
            account_id=account["id"], display_name="Also Nobody Said", actor=dana
        )
        # NO ROW. And the reason names the missing fact, not a rule id.
        assert link["id"] is None
        assert link["customer_no"] is None
        assert link["not_created"]["missing"] == "customer_kind_missing"
        assert link["kind_defaulted"] is False

        # Stating the kind is still not enough on its own — the identifier is
        # the other half of the minimum.
        stated = customers_services.link_customer(
            account_id=account["id"], display_name=COMPANY, kind="company", actor=dana
        )
        assert stated["id"] is None
        assert stated["not_created"]["missing"] == "customer_identifier_missing"
        assert stated["not_created"]["accepts"] == ["tax_id"]

        # With the Tax ID it creates, and the kind is the one that was stated.
        made = customers_services.link_customer(
            account_id=account["id"], display_name=COMPANY, kind="company",
            identity={"tax_id": TAX_ID}, actor=dana,
        )
        assert made["customer_no"]
        assert made["kind"] == "company"
        assert made["kind_defaulted"] is False


def test_an_identifier_cannot_be_written_onto_the_wrong_kind_of_row(brazos, dana):
    """The second lock, for in-process callers that never meet the validator.

    `link_customer` can be called with an `IdentityEvidence` built by hand, so
    `set_identifier` refuses a column the row's kind is not asked for rather
    than storing a value the matcher for that kind will never read.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="16 Cedar", identity={"tax_id": TAX_ID})
        company = _customer()
        with pytest.raises(ValueError):
            identity_match.set_identifier(company, "driving_licence", "TX-DL-4417")


# ═══════════════════════════════════════════════════════════════════════════
# THE MONEY — a strong company match may carry a deposit; a weak one shows none
# ═══════════════════════════════════════════════════════════════════════════
def test_a_weak_company_match_refuses_by_name_and_shows_no_figure(brazos, dana):
    """`BR-CUS-019` is advisory so nothing is blocked; `BR-CUS-089` moves money
    only on `strong` so nothing is joined on a guess.

    ⚠ **AND THE REFUSAL CARRIES NO AMOUNT.** A refused offer that prints
    **$150.00** is an invitation to type it in by hand — the reason the person's
    wording carries none, and the hazard is identical for a business.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="17 Cedar", identity={"tax_id": TAX_ID})
        account = _open(dana, brazos, label="19 Cedar", name="Elsewhere Holdings LLC")
        result = customers_services.link_customer(
            account_id=account["id"],
            display_name=COMPANY,
            kind="company",
            identity={"tax_id": OTHER_TAX_ID},
            actor=dana,
        )
        match = result["match"]
        assert match["tier"] is None
        assert match["refusal"] == identity_match.REFUSAL_NOT_STRONG
        refusal = match["unavailable"][0]
        assert refusal["code"] == identity_match.REFUSAL_NOT_STRONG
        # The COMPANY wording, not the person's — a business has no date of
        # birth and must not be sent to find one.
        assert "Tax ID" in refusal["detail"]
        assert "date of birth" not in refusal["detail"]
        # No figure at all, in any spelling.
        for money in ("150", "150.00", "$150", "$150.00"):
            assert money not in refusal["detail"]


def test_the_read_path_serves_the_last_four_and_never_the_number(brazos, dana):
    """BR-CUS-092(c) — *"every read path renders last four only"*.

    Applied to the Tax ID by the same rule and the same reasoning: a number that
    reaches the browser is in devtools, in a proxy log and in the HAR file
    attached to a ticket, whatever the screen chooses to draw.
    """
    with tenant_ctx(brazos):
        _open(dana, brazos, label="20 Cedar", identity={"tax_id": TAX_ID})
        rows = customers_selectors.customer_list(ListParams(q="Silver Creek"))
        assert rows, "the company was not listed at all"
        identity = rows[0]["identity"]
        assert identity["tax_id_held"] is True
        assert identity["tax_id_last4"] == TAX_ID_LAST4
        _assert_no_identifier_in(rows, "the customers list")


def test_the_search_finds_a_company_by_its_tax_id(brazos, dana):
    """Without this leg a business could be matched by the machine and never
    FOUND by a person — the number on the letter in their hand would be the one
    field the box could not read. Exact, because the probe is an equality test
    over an HMAC: half a number finds nobody."""
    with tenant_ctx(brazos):
        _open(dana, brazos, label="21 Cedar", identity={"tax_id": TAX_ID})
        punctuated = customers_selectors.customer_list(ListParams(q=TAX_ID))
        assert [row["display_name"] for row in punctuated] == [COMPANY]
        bare = customers_selectors.customer_list(ListParams(q=TAX_ID_DIGITS))
        assert [row["display_name"] for row in bare] == [COMPANY]
        assert customers_selectors.customer_list(ListParams(q="12-345")) == []


def test_rule7_the_company_verdict_writes_audit_log_with_the_kind_and_no_number(
    brazos, dana, audit_rows
):
    """CLAUDE.md rule 7 — a recognition decision GATES a deposit, so both the
    recognition and the refusal write `audit_log`. The blob names the KIND, so a
    `weak` verdict is readable a month later, and carries no identifier."""
    with tenant_ctx(brazos):
        _open(dana, brazos, label="22 Cedar", identity={"tax_id": TAX_ID})
        account = _open(dana, brazos, label="23 Cedar", name="Another Holdings LLC")
        customers_services.link_customer(
            account_id=account["id"],
            display_name=COMPANY,
            kind="company",
            identity={"tax_id": TAX_ID},
            actor=dana,
        )
        rows = [
            row
            for row in audit_rows
            if row["action"] in ("customer.identity_recognised", "customer.identity_not_recognised")
        ]
        assert rows, "no audit row was written for the recognition decision"
        blob = rows[-1]["after"]
        assert blob["kind"] == "company"
        assert blob["kind_defaulted"] is False
        _assert_no_identifier_in(blob, "the audit blob")


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO THINGS THIS WAVE DID NOT DECIDE — stubbed, never chosen
# ═══════════════════════════════════════════════════════════════════════════
def test_an_incorporation_date_raises_the_open_question_rather_than_being_dropped(brazos, dana):
    """`OQ-1241` — whether a company gets a date-of-birth equivalent is OPEN.

    Recognised and refused rather than ignored: a silently dropped value looks
    exactly like a stored fact that never matches anything.
    """
    with pytest.raises(NotImplementedError) as caught:
        identity_match.from_payload({"incorporation_date": "2011-04-02"}, kind="company")
    assert "OQ-1241" in str(caught.value)


def test_a_sole_trader_raises_the_open_question_rather_than_being_folded_in(brazos, dana):
    """`OQ-1242` — whether a sole trader is a person or a company is OPEN.

    They trade as a business and are a natural person, so the two readings ask
    for different evidence — a Tax ID under one, an SSN or a licence under the
    other. Choosing here would resolve an open question by writing a value into
    a customer's row, which the prime directive forbids.
    """
    for spelling in ("sole trader", "sole_trader", "Sole Trader", "sole proprietor"):
        with pytest.raises(NotImplementedError) as caught:
            identity_match.normalise_kind(spelling)
        assert "OQ-1242" in str(caught.value), spelling


def test_an_unknown_kind_is_a_named_field_error_and_not_a_silent_person(brazos, dana):
    """A value outside the two lawful kinds reaches a clerk as a field error.

    Folding it into `person` would be the silent default this wave exists to
    end, one level further down.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            _open(dana, brazos, label="24 Cedar", kind="charity")
        assert caught.value.message_key == "customers.customer.kind_unknown"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-056 W2b (12-governance/11-change-requests.md §CR-056) + BR-CUS-1022
#         + BR-CUS-089 (PO 2026-08-25, NARROWED onto persons 2026-09-01)
#         + BR-CUS-092 + OQ-016 (CLOSED, PO R6) + B2 §6
#         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-056` allocates no story ids, and minting one to satisfy `G01`'s regex would put a citation in the tree that resolves to nothing. Same posture as `apps/customers/identity_match.py`
# generated: 2026-09-01 by the CR-056 W2b lane
# checklist: A✔ B✔ C✔ D✔(GET /customers) E✔(CustomersListPage.tsx identity cell) F✔ G✔ H=OWED(🔒 human-review-ledger row is OPEN)
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
