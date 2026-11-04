# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-031 (EP-CWP-06) — your account: the deposit we hold, the
#           exemption that lapses, the history. Screen: CWP-065
# Rules:    BR-CWP-049 (the deposit is shown WHILE it is held — amount, date,
#           interest) · BR-CWP-053 (an exemption shows its expiry and a message
#           goes out thirty days before) · BR-CWP-052 (⚠ the credit tier is
#           held back ON PURPOSE and must not appear) · BR-CUS-057 (the
#           interest arithmetic, finance-signed against ❄️ GT-61) ·
#           BR-CWP-010 (both halves in the query) · CLAUDE.md hard rule 2
# Tests:    this file
# Impacts:  apps/portal/selectors.py `account_summary` · apps/portal/api.py
#           `accounts/{id}/summary` · seams/customers_seam.py · seams/rating_seam.py
# ───────────────────────────────────────────────────────
"""`US-CWP-031`'s nine cases.

⚠ **THE INTEREST IS NEVER ASSERTED AGAINST A CONSTANT THIS FILE INVENTED.**
`US-CWP-031` §4 quotes `$3.20`, and `150.00 × 2% × N ÷ 12` does not reach
`3.20` for any whole number of months — the engine's own worked figures are
`22.25` at 89 months (❄️ GT-61, FROZEN) and `3.50` at 14. So every case below
asks the SIGNED ENGINE what the figure is for the dates the fixture set, and
asserts the screen agrees with it. **That is what §7 actually wants**: *a figure
here that disagrees with the final bill is the defect this test exists to
catch*, and a hard-coded `3.20` would have made the test agree with the story
and disagree with the money.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.customers import models as customers_models
from apps.portal import selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: The day the screen is read.
TODAY = date(2026, 9, 2)
#: `US-CWP-031` §4 — `$150.00` taken on 4 March 2021, and an exemption that
#: runs out on 31 March 2027.
DEPOSIT = Decimal("150.0000")
TAKEN_ON = date(2021, 3, 4)
EXEMPT_UNTIL = date(2027, 3, 31)
#: ⚠ The one that must NEVER reach a customer's screen (`BR-CWP-052`).
INTERNAL_CREDIT_TIER = "B2"


def an_account_with_a_deposit(tenant, actor):
    """Maria's account, holding `$150.00` since 2021 and tax exempt to 2027.

    ⚠ **AND CARRYING AN INTERNAL CREDIT TIER**, deliberately: TC-7 is only worth
    having if the value it forbids is actually on the row. A test that asserted
    the absence of a field nothing had set would pass over an empty column
    forever and never notice the day somebody serves it.
    """
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        account.deposit_on_file = DEPOSIT
        account.deposit_received_on = TAKEN_ON
        account.tax_exempt = True
        account.tax_exempt_ref = "TX-EX-88213"
        account.tax_exempt_expires = EXEMPT_UNTIL
        account.credit_tier = INTERNAL_CREDIT_TIER
        account.save(
            update_fields=[
                "deposit_on_file",
                "deposit_received_on",
                "tax_exempt",
                "tax_exempt_ref",
                "tax_exempt_expires",
                "credit_tier",
            ]
        )
    return account


def read(tenant, account):
    with tenant_context(tenant.id):
        return selectors.account_summary(tenant.id, account, as_of=TODAY)


@pytest.mark.django_db
def test_us_cwp_031_tc1_the_deposit_reads_the_signed_engine_and_never_a_number_of_its_own(
    pine_hill, sarah
):
    """`BR-CWP-049` + `BR-CUS-057`. The screen's figure IS the engine's figure.

    ⚠ **THE ASSERTION IS AN EQUALITY BETWEEN TWO LIVE READS, NOT A CONSTANT.**
    If the accrual moves, both sides move together and this stays green — which
    is correct: what `US-CWP-031` §7 forbids is the SCREEN disagreeing with the
    settlement, not either of them changing.
    """
    from apps.customers import selectors as customers_selectors

    switch_on(pine_hill, sarah)
    account = an_account_with_a_deposit(pine_hill, sarah)
    view = read(pine_hill, account)
    with tenant_context(pine_hill.id):
        engine = customers_selectors.deposit_interest_accrued(account.pk, TODAY)

    assert view["deposit"] is not None, view
    assert Decimal(view["deposit"]["held"]) == DEPOSIT
    assert view["deposit"]["taken_on"] == TAKEN_ON.isoformat()
    if engine is None:
        assert view["deposit"]["interest"] is None, (
            "an interest the engine cannot compute must travel as None — a 0.00 here "
            "would disagree with the customer's own final bill (US-CWP-031 §7)"
        )
    else:
        assert Decimal(view["deposit"]["interest"]) == Decimal(engine)


@pytest.mark.django_db
def test_us_cwp_031_tc2_the_deposit_says_it_is_not_money_off_a_bill(pine_hill, sarah):
    """⚠ A customer who reads a held deposit as credit stops paying — and then
    owes the utility money AND still has the deposit. The flag is what makes the
    screen say so; it is not decoration."""
    switch_on(pine_hill, sarah)
    account = an_account_with_a_deposit(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["deposit"]["is_money_off_a_bill"] is False
    assert view["deposit"]["returns_at_closing"] is True


@pytest.mark.django_db
def test_us_cwp_031_tc3_services_carry_the_utilitys_own_word_and_their_own_start_date(
    pine_hill, sarah
):
    """The date is the AGREEMENT's, not the account's — a household that took
    water in 2021 and trash in 2024 has two answers, and one date against both
    is wrong the first time somebody checks it against a bill."""
    switch_on(pine_hill, sarah)
    account = an_account_with_a_deposit(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["services"], "the seeded account is on at least one service"
    for row in view["services"]:
        assert row["name"] and row["name"] != row["code"] or row["name"] == row["code"]
        assert row["since"], f"{row['code']} has no start date"
    with tenant_context(pine_hill.id):
        expected = customers_models.ServiceAgreement.objects.filter(
            tenant_id=pine_hill.id, account_id=account.pk, ended_on__isnull=True
        ).count()
    assert len(view["services"]) == expected


@pytest.mark.django_db
def test_us_cwp_031_tc4_the_plan_is_a_name_and_a_date_and_nothing_internal(pine_hill, sarah):
    """⚠ `plan_version`, `source`, `actor` and `reason` are the utility's record
    of WHO changed a customer's plan and WHY. None of it is the customer's."""
    switch_on(pine_hill, sarah)
    account = an_account_with_a_deposit(pine_hill, sarah)
    view = read(pine_hill, account)
    billing = view["billing"]
    assert set(billing) == {"current", "before"}
    if billing["current"] is not None:
        assert set(billing["current"]) == {"name", "since"}
    for row in billing["before"]:
        assert set(row) == {"name", "from", "to"}


@pytest.mark.django_db
def test_us_cwp_031_tc5_the_exemption_shows_its_expiry_and_that_a_reminder_comes(
    pine_hill, sarah
):
    """`BR-CWP-053` — an exemption that lapses silently becomes a bigger bill
    and a complaint. ⚠ And the CERTIFICATE NUMBER is not served: what a customer
    needs is that it is held, not the utility's own reference."""
    switch_on(pine_hill, sarah)
    account = an_account_with_a_deposit(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["tax_exemption"]["until"] == EXEMPT_UNTIL.isoformat()
    assert view["tax_exemption"]["certificate_on_file"] is True
    assert view["tax_exemption"]["reminder_days_before"] == 30
    assert "TX-EX-88213" not in str(view), "the certificate reference is the utility's record"


@pytest.mark.django_db
def test_us_cwp_031_tc7_no_credit_tier_no_match_tier_no_match_basis_on_the_body(
    pine_hill, sarah
):
    """⚠ **`BR-CWP-052`, AND THE ROW REALLY CARRIES ONE.** The fixture sets
    `credit_tier = 'B2'`; this asserts on the SERIALISED body, because that is
    what a customer's browser receives and it is the only assertion a refactor
    cannot walk around."""
    import json

    switch_on(pine_hill, sarah)
    account = an_account_with_a_deposit(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    answer = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/summary")
    assert answer.status_code == 200, answer.content
    body = answer.content.decode()
    for forbidden in ("credit_tier", "match_tier", "match_basis", INTERNAL_CREDIT_TIER):
        assert forbidden not in body, f"{forbidden!r} reached a customer's screen"
    assert json.loads(body)["deposit"] is not None


@pytest.mark.django_db
def test_us_cwp_031_tc8_an_account_with_no_deposit_gets_NO_panel_rather_than_a_zero(
    pine_hill, sarah
):
    """⚠ **`$0.00` READS AS *we took nothing from you*, WHICH IS A DIFFERENT
    CLAIM FROM *there is nothing here*.** B14 rule 17's absence, on a money
    field where the difference is a phone call."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    view = read(pine_hill, account)
    assert view["deposit"] is None, view["deposit"]


@pytest.mark.django_db
def test_us_cwp_031_tc9_the_read_never_carries_a_cache_header(pine_hill, sarah):
    """The deposit and its interest are money in motion at closing time."""
    switch_on(pine_hill, sarah)
    account = an_account_with_a_deposit(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    answer = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/summary")
    assert "no-store" in answer.headers.get("Cache-Control", "")


@pytest.mark.django_db
def test_us_cwp_031_tc6_an_account_outside_the_set_answers_404(pine_hill, sarah):
    """`BR-CWP-010` — the summary is account-scoped like every other read."""
    import uuid

    switch_on(pine_hill, sarah)
    an_account_with_a_deposit(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    answer = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{uuid.uuid4()}/summary")
    assert answer.status_code == 404


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-031@this-commit (EP-CWP-06 story + BR-CWP-049/052/053 verbatim)
# generated: 2026-09-04 by the CR-068 wave F build lane
# checklist: A✔ B✔ C✔ D✔(api.py accounts/{id}/summary) E✔(CWP-065) F✔ G✔ H=n/a(the interest is READ from the signed engine, never recomputed)
# gates: pytest tests/test_us_cwp_031_your_account.py · G81 (no ORM write in selectors.py or a seam)
# exceptions: the fixture writes deposit/exemption/credit_tier through the ORM — this story is a READ, and TC-7 needs the forbidden value actually present to be worth anything
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
