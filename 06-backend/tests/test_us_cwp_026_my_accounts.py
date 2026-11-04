# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-026 (EP-CWP-06) — all my accounts, four balances, totalled,
#           never merged. Screen: CWP-023
# Rules:    BR-CWP-013 (the set is FLAT; the master is one more entry and
#           confers nothing) · BR-CWP-014 (what makes a master different is
#           that it is BILLED to the landlord — a billing fact, not a
#           permission) · BR-CWP-015 (shown separately, totalled for
#           information, never merged) · BR-CWP-016 (a landlord sees the
#           accounts they hold and NEVER a tenant's — PO 2026-09-04, "(a) no")
#           · BR-CWP-010 (both halves in the query) · BR-CWP-047 (never cached)
# Tests:    this file
# Impacts:  apps/portal/selectors.py `my_accounts` · apps/portal/api.py
#           `my-accounts` · apps/portal/seams/customers_seam.py
# ───────────────────────────────────────────────────────
"""`US-CWP-026`'s eight cases, plus the two the build itself turned up.

⚠ **`OQ-1397` IS CLOSED AND THIS FILE IS WHERE THAT SHOWS.** The story's TC-8
used to demand `NotImplementedError("OQ-1397")` from the common-area
reconciliation. The question was answered **no** on 2026-09-04, so nothing here
may cite it as open — and the reconciliation is STILL unbuilt, for a reason
that has nothing to do with access: its arithmetic is `finance_calc: proposed`
and a lane implements signed law rather than inventing it. TC-8 asserts the
refusal names FINANCE and carries no `OQ-` id at all.

⚠ **NOT ONE FIGURE BELOW IS A CONSTANT THIS FILE COMPUTED.** `872.82` is the
sum of four bills the fixture wrote and the READ added up; the nineteen days
are the distance between a due date the fixture set and a date the test states.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client

from apps.customers import models as customers_models
from apps.portal import selectors
from apps.portal.seams import customers_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    LANDLORD_TOTAL,
    MARIA_EMAIL,
    MARIA_PASSWORD,
    an_issued_bill,
    elm_street_account,
    enrol_maria,
    switch_on,
)
from tests.test_us_cwp_024_balance import four_accounts

#: The day the screen is read. Every date below is stated relative to it, so a
#: reader can do the arithmetic without running anything.
TODAY = date(2026, 9, 2)
#: Three of the four are due in twelve days; `22 Palm Ct` was due nineteen days
#: ago, which is `US-CWP-026`'s own *OVERDUE 19 DAYS*.
DUE_SOON = date(2026, 9, 14)
DUE_PAST = date(2026, 8, 14)
OVERDUE_DAYS = 19
AUGUST = date(2026, 8, 26)

#: `US-CWP-026` §4 — 142.18 + 0.00 + 318.04 + 412.60 = 872.82, and the `0.00`
#: row is one of the four rather than an absence.
BILLS = ("142.1800", "0.0000", "318.0400", "412.6000")


def landlord(tenant, actor):
    """Maria holding FOUR accounts, one of them the common-areas master.

    ⚠ **THE LINK ROWS AND THE `kind` FLIP ARE WRITTEN THROUGH THE ORM**, the
    same posture and the same reason `an_issued_bill` states: `create_account`
    already built these four through its own door, and what this story is about
    is a READ over accounts a customer holds. `customer_accounts` has no
    service of its own in this product — every writer creates the row directly
    — so there is no door here to go through.
    """
    from apps.portal import models as portal_models

    credential = enrol_maria(tenant, actor)
    accounts = four_accounts(tenant, actor)
    mine = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        for account in accounts:
            customers_models.CustomerAccount.objects.get_or_create(
                tenant_id=tenant.id, customer_id=credential.customer_id, account=account
            )
        # `BR-CWP-014` — the master is the owner's row over the building's
        # common supply. `create_master_account` is the product's only door to
        # `kind`; this fixture is asserting how the READ words it.
        master = next(a for a in accounts if a.pk != mine.pk)
        master.kind = customers_seam.ACCOUNT_KIND_MASTER
        master.save(update_fields=["kind"])
        for account, total in zip(accounts, BILLS):
            if total == "0.0000":
                continue
            an_issued_bill(
                tenant,
                account,
                number=f"BL-2608-{str(account.account_no)[-4:]}",
                total=total,
                issued_on=AUGUST,
                due_on=DUE_PAST if total == "412.6000" else DUE_SOON,
            )
        assert portal_models.PortalCredential.objects.filter(pk=credential.pk).exists()
    return credential, accounts, master


def a_tenants_account(tenant, actor):
    """One account in this utility that Maria does NOT hold — TC-3 and TC-4.

    ⚠ **THE FIXTURE HAD TO GROW A UNIT, AND THAT IS WORTH SAYING.** The seeded
    street gives `1408 Elm St` three units and the landlord fixture consumes
    every one of them plus Palm Court, so a first draft of these two cases
    asserted over a tenant whose account did not exist and failed on its own
    guard rather than on the product. `1412 Elm St` is seeded with NO units
    precisely so a test can put one there; both doors below are the product's
    own (`metering.create_unit`, `customers.create_account`).
    """
    from apps.customers import services as customers_services
    from apps.metering import models as metering_models, services as metering_services
    from apps.portal import sample_data

    # ⚠ **OUTSIDE THE CONTEXT BLOCK, DELIBERATELY.** `elm_street_account` opens
    # a `tenant_context` of its own, and a nested one CLEARS the tenant when it
    # exits rather than restoring the outer value — so calling it from inside
    # the block below left `app.tenant_id` unset and the very next service call
    # refused with `AUTH-003 (BR-TEN-003)`. The refusal is correct and the
    # nesting was the bug; the plan id is read here, once, before the block.
    plan_id = elm_street_account(tenant, actor).unit.rate_plan_id

    with tenant_context(tenant.id):
        premises = metering_models.Premises.objects.get(address_line="1412 Elm St")
        neighbour = metering_models.Unit.objects.filter(premises_id=premises.pk, label="1").first()
        if neighbour is None:
            made = metering_services.create_unit(
                actor, {"premises_id": str(premises.pk), "label": "1"}
            )
            neighbour = metering_models.Unit.objects.get(pk=made["id"])
        existing = customers_models.Account.objects.filter(unit_id=neighbour.pk).first()
        if existing is not None:
            return existing
        if neighbour.rate_plan_id is None and plan_id is not None:
            sample_data._put_on_plan(actor, neighbour.pk, str(plan_id), ["water"])
        created = customers_services.create_account(
            actor,
            {
                "unit_id": str(neighbour.pk),
                "account_type": "residential",
                "opened_at": "2026-02-02",
                "contact": {"full_name": "A Tenant", "phone": "(512) 555-0144"},
                # ⚠ **A PERSON NEEDS AN IDENTIFIER, AND THE SET IS NARROWER
                # THAN IT LOOKS.** The first draft sent a name and a kind, and
                # `create_account` refused by name — `BIZ-COMPLETENESS
                # (customers.account.identity_required_person)`. The second
                # sent a date of birth and was refused again, because
                # `CREATE_IDENTIFIER_FIELDS[person]` is `ssn · driving_licence
                # · phone` and a date of birth is not on it — that belongs to
                # `tier_for`, a different question (`DEF-2587` is what reading
                # the wrong table cost). **A phone is the gentlest of the three
                # and is deliberately allowed to MINT a row while never being
                # enough to REUSE one:** minting a spare row on a shared
                # household line costs a merge later, reusing one hands a
                # stranger somebody's file. This tenant gives the phone that is
                # already on their contact, which is what actually happens at a
                # counter.
                "customer": {
                    "display_name": "A Tenant",
                    "kind": "person",
                    "identity": {"phone": "(512) 555-0144"},
                },
                # ⚠ **THE PLAN ASKS A DEPOSIT, SO THE ACCOUNT MUST ANSWER IT** —
                # `DEF-CWP-6424`'s refusal one fixture along. This unit is put
                # on the same priced plan two lines above and that plan prices a
                # `$150.00` residential deposit, so an open with no `deposit`
                # block is refused by `customers.deposit.planAsksDeposit`
                # (`OQ-CUS-12620` (a), *"No" only when the plan asks none*).
                # `required` without `take_now` ASSESSES the plan's figure and
                # leaves it for the first bill, so no money moves and the
                # neighbour is still an account Maria does NOT hold.
                "deposit": {"decision": "required"},
            },
        )
        customers_services.activate_account(actor, created["id"])
        return customers_models.Account.objects.get(pk=created["id"])


def _read(tenant, actor):
    from apps.portal import session as portal_session

    credential, accounts, master = landlord(tenant, actor)
    with tenant_context(tenant.id):
        entries = portal_session.account_set(
            tenant.id, customer_id=credential.customer_id, credential_id=credential.pk
        )

        class _Principal:
            tenant_id = tenant.id
            customer_id = credential.customer_id

            def __init__(self, accounts):
                self.accounts = accounts

            @property
            def account_ids(self):
                return tuple(entry.account_id for entry in self.accounts)

        return selectors.my_accounts(_Principal(entries), today=TODAY), accounts, master


@pytest.mark.django_db
def test_us_cwp_026_tc1_four_rows_total_872_82_and_stay_four_balances(pine_hill, sarah):
    """`BR-CWP-015` — totalled for information, and **never merged**."""
    switch_on(pine_hill, sarah)
    view, _, _ = _read(pine_hill, sarah)
    assert view["account_count"] == 4, view
    assert view["total_owing"] == LANDLORD_TOTAL, view["total_owing"]
    assert len(view["accounts"]) == 4
    assert sorted(row["owing"] for row in view["accounts"]) == sorted(BILLS), view["accounts"]
    # ⚠ There is no field in this body a payment could be posted against.
    assert not {"invoice", "invoice_no", "pay_reference", "amount_due"} & set(view)


@pytest.mark.django_db
def test_us_cwp_026_tc2_the_master_row_is_billed_to_the_owner_and_the_rest_are_not(
    pine_hill, sarah
):
    """`BR-CWP-014`. The label is a BILLING fact, and it reads the `kind`
    COLUMN — not the shape of the row, which is `DEF-CWP-3765`."""
    switch_on(pine_hill, sarah)
    view, _, master = _read(pine_hill, sarah)
    by_id = {row["id"]: row for row in view["accounts"]}
    assert by_id[str(master.pk)]["billed_to"] == "owner"
    assert by_id[str(master.pk)]["is_master"] is True
    others = [row for row in view["accounts"] if row["id"] != str(master.pk)]
    assert len(others) == 3
    assert {row["billed_to"] for row in others} == {"tenant"}


@pytest.mark.django_db
def test_us_cwp_026_tc3_the_body_names_four_ids_and_no_fifth(pine_hill, sarah):
    """`BR-CWP-016`, ruled 2026-09-04: a landlord never sees a tenant's.

    The tenants' own accounts exist in this tenant and are absent here **by
    construction** — every row is built from the session's set, so there is no
    query for a widened scope to reach.
    """
    switch_on(pine_hill, sarah)
    view, accounts, _ = _read(pine_hill, sarah)
    outsider = a_tenants_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        everything = set(
            str(pk) for pk in customers_models.Account.objects.values_list("pk", flat=True)
        )
    served = {row["id"] for row in view["accounts"]}
    assert served == {str(a.pk) for a in accounts}
    assert len(served) == 4
    assert str(outsider.pk) in everything - served, (
        "a tenant's own account exists in this utility and must not be in the body"
    )


@pytest.mark.django_db
def test_us_cwp_026_tc4_an_account_outside_the_set_is_refused_through_the_endpoint(
    pine_hill, sarah
):
    """`BR-CWP-010` — the master confers nothing, and the refusal is a 404."""
    switch_on(pine_hill, sarah)
    _read(pine_hill, sarah)
    outside = a_tenants_account(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    answer = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{outside.pk}/balance")
    assert answer.status_code == 404, answer.content


@pytest.mark.django_db
def test_us_cwp_026_tc5_a_householder_gets_one_row_and_no_total(pine_hill, sarah):
    """⚠ **A TOTAL OF ONE NUMBER IS NOISE**, and worse than noise: a `$142.18`
    row above a `$142.18` total invites the reading that `$284.36` is owed."""
    switch_on(pine_hill, sarah)
    credential = enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    from apps.portal import session as portal_session

    with tenant_context(pine_hill.id):
        customers_models.CustomerAccount.objects.get_or_create(
            tenant_id=pine_hill.id, customer_id=credential.customer_id, account=account
        )
        an_issued_bill(
            pine_hill,
            account,
            number="BL-2608-0141",
            total="142.1800",
            issued_on=AUGUST,
            due_on=DUE_SOON,
        )
        entries = portal_session.account_set(
            pine_hill.id, customer_id=credential.customer_id, credential_id=credential.pk
        )

        class _One:
            tenant_id = pine_hill.id
            accounts = entries
            account_ids = tuple(e.account_id for e in entries)

        view = selectors.my_accounts(_One(), today=TODAY)
    assert view["account_count"] == 1, view
    assert view["show_total"] is False, "a total of one number is noise (TC-5)"


@pytest.mark.django_db
def test_us_cwp_026_tc6_an_oak_ridge_session_reads_no_pine_hill_account(
    pine_hill, oak_ridge, sarah, elena
):
    """Isolation, in the query and not in the screen (hard rule 1)."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    view, accounts, _ = _read(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        theirs = set(
            str(pk)
            for pk in customers_models.Account.objects.filter(tenant_id=oak_ridge.id).values_list(
                "pk", flat=True
            )
        )
    assert not theirs & {row["id"] for row in view["accounts"]}


@pytest.mark.django_db
def test_us_cwp_026_tc7_the_states_are_what_the_owing_filter_reads(pine_hill, sarah):
    """TC-7 — *Owing* drops `· B` at `$0.00`, and `22 Palm Ct` reads OVERDUE.

    ⚠ **THE SCREEN FILTERS ON `state`, NOT ON A SENTENCE.** The server sends
    `clear · due · overdue` and a day count; the eleven catalogues write the
    words (B14 rule 35), so *19 days overdue* is composed where the language is
    known rather than shipped as English from here.
    """
    switch_on(pine_hill, sarah)
    view, _, _ = _read(pine_hill, sarah)
    states = {row["owing"]: row for row in view["accounts"]}
    assert states["0.0000"]["state"] == "clear"
    assert states["0.0000"]["days_overdue"] is None
    assert states["142.1800"]["state"] == "due"
    overdue = states["412.6000"]
    assert overdue["state"] == "overdue"
    assert overdue["days_overdue"] == OVERDUE_DAYS, (
        f"{DUE_PAST} to {TODAY} is {OVERDUE_DAYS} days — US-CWP-026 §4's own figure"
    )
    owing_filter = [row for row in view["accounts"] if row["state"] != "clear"]
    assert len(owing_filter) == 3


@pytest.mark.django_db
def test_us_cwp_026_tc8_the_reconciliation_refuses_on_FINANCE_and_names_no_open_question():
    """⚠ **THE CASE `OQ-1397`'s CLOSURE CHANGED.**

    The story asked for `NotImplementedError("OQ-1397")` here. The question was
    answered *no* on 2026-09-04, so a stub citing it would be stale the moment
    it was written (G8 clause A). What actually stops this read is that its
    arithmetic is `finance_calc: proposed` — *the difference the landlord is
    billed for* decides what somebody pays, and B4's rule is that a lane
    implements signed law and never invents it.
    """
    with pytest.raises(NotImplementedError) as refused:
        selectors.common_area_reconciliation("any-account")
    message = str(refused.value)
    assert "finance-signed" in message
    assert "OQ-" not in message, f"a closed question may not be cited as a blocker: {message}"


def test_us_cwp_026_the_seam_spells_master_the_way_customers_does():
    """⚠ **A RE-EXPORTED CONSTANT IS A SECOND COPY UNTIL SOMETHING COMPARES
    THEM** (hard-won law 1). The seam names `"master"` so the portal reads one
    spelling; this is what stops the two drifting in silence."""
    from apps.customers import services as customers_services

    assert customers_seam.ACCOUNT_KIND_MASTER == customers_services.ACCOUNT_KIND_MASTER


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-026@this-commit (EP-CWP-06 story + BR-CWP-013/014/015/016 verbatim)
# generated: 2026-09-04 by the CR-068 wave F build lane
# checklist: A✔ B✔ C✔ D✔(api.py my-accounts) E=wave F 2b(CWP-023) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_026_my_accounts.py · G81 (no ORM write in selectors.py)
# exceptions: the `kind` flip and the link rows are ORM fixture writes — customer_accounts has no service in this product, and this story is a READ
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
