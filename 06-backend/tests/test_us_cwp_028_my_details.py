# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-028 (EP-CWP-06) — my details: what a customer may edit, and
#           what they may not. Screen: CWP-024
# Rules:    BR-CWP-001 kind ⑤ `contact_detail` (PO ruling 2026-09-04,
#           OQ-CWP-1562 — the portal may CHANGE a record in the utility's own
#           books) · BR-CWP-103 (the security is at the door) · BR-CWP-026 (the
#           legal name and the account holder are refused, with a request
#           route) · BR-CWP-086 (returned post shows above the address field
#           and correcting the address clears it) · BR-CWP-010 (the account set
#           is intersected in the query) · CLAUDE.md hard rule 1 · rule 7
# Tests:    this file
# Impacts:  apps/customers/portal_self_service.py · apps/portal/services.py
#           `update_own_contact_details` · apps/portal/selectors.py `my_details`
# ───────────────────────────────────────────────────────
"""`US-CWP-028`'s cases — and the one the whole screen turns on.

⚠ **ONE SAVE REACHES FOUR ACCOUNTS** (TC-10). `contacts` hangs off the ACCOUNT,
so Maria Alvarez holding four has four contact rows. A screen that fixed one of
them would leave three bills going to an old email address and give her no way
to find out which — so the fix is *the change reaches every account you hold*,
stated on the screen and asserted here.

⚠ **AND WHAT IS REFUSED IS REFUSED BEFORE ANYTHING IS WRITTEN** (TC-2). A
refusal that fired after the email had already been saved would leave the
account half-edited while the response still read *refused*.

**WHAT IS NOT IN THIS FILE, AND WHERE IT WENT.** The story's TC-3, TC-4, TC-5
and TC-9 are `CWP-025` — the channel grid, the paperless withdrawal and the
language picker — and they are in `tests/test_us_cwp_028_preferences.py`.

⚠ **THIS PARAGRAPH SAID THEY BELONGED TO `US-CWP-030` IN WAVE H UNTIL
2026-09-05, AND THAT WAS WRONG (`DEF-CWP-3861`).** It was repeating
`write_points.py`'s own comment, which named a story that is *accept an
invitation* (`CWP-021`) and is `status: deferred` — `OQ-1396` ruled delegate
access out of the release. So a wrong pointer had propagated to a second file
and was being used to justify a gap: a reader would have gone looking for a
deferred delegate story and concluded the preferences grid was somebody
else's problem. **A story id in prose is a pointer nothing dereferences**, and
the cheapest guard is to open the story before citing it as a reason not to
build something.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.customers import models as customers_models
from apps.customers import portal_self_service
from apps.portal import selectors, services, session as portal_session
from apps.portal.seams import customers_seam
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    elm_street_account,
    enrol_maria,
    switch_on,
)
from tests.test_us_cwp_026_my_accounts import four_accounts

TODAY = date(2026, 9, 4)

#: `US-CWP-028` §4 — Maria's own figures.
OLD_EMAIL = "m.alvarez@example.com"
NEW_EMAIL = "maria.alvarez@newmail.example"
OLD_PHONE = "(512) 555-4218"
NEW_PHONE = "(512) 555-9911"
LEGAL_NAME = "Maria Alvarez"


def maria_with_four(tenant, actor):
    """Maria, her credential, and the four accounts each carrying her contact.

    ⚠ **THE CONTACT ROWS ARE UPDATED, NOT CREATED, AND THE FIRST DRAFT GOT
    THIS WRONG IN A WAY WORTH KEEPING.** `create_account` already writes a
    primary contact per account, so a fixture that ADDED one left two primaries
    per account — and `_primary_contact` takes the oldest, so the product
    correctly edited the row the fixture was not looking at. Four assertions
    failed on a fixture bug that looked exactly like a product bug. **A fixture
    that creates a second row of something the product creates one of is
    testing a shape the product never produces.**
    """
    credential = enrol_maria(tenant, actor)
    accounts = four_accounts(tenant, actor)
    with tenant_context(tenant.id):
        for account in accounts:
            customers_models.CustomerAccount.objects.get_or_create(
                tenant_id=tenant.id, customer_id=credential.customer_id, account=account
            )
            row = (
                customers_models.Contact.objects.filter(
                    tenant_id=tenant.id, account=account, is_primary=True
                )
                .order_by("created_at")
                .first()
            )
            if row is None:
                row = customers_models.Contact(
                    tenant_id=tenant.id, account=account, is_primary=True
                )
            row.full_name = LEGAL_NAME
            row.email = OLD_EMAIL
            row.phone = OLD_PHONE
            row.save()
    return credential, accounts


def principal_for(tenant, credential):
    with tenant_context(tenant.id):
        entries = portal_session.account_set(
            tenant.id, customer_id=credential.customer_id, credential_id=credential.pk
        )
    return portal_session.PortalPrincipal(
        session_id="test-session",
        credential_id=str(credential.pk),
        customer_id=str(credential.customer_id),
        tenant_id=tenant.id,
        accounts=entries,
    )


@pytest.mark.django_db
def test_us_cwp_028_tc10_one_save_reaches_every_account_this_login_holds(pine_hill, sarah):
    """⚠ **THE CASE THE SCREEN EXISTS FOR.** Four accounts, one new mobile,
    four rows updated — because three bills still going to the old number is
    not a state a customer can see or fix."""
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        result = services.update_own_contact_details(
            pine_hill.id,
            actor=principal,
            account_ids=list(principal.account_ids),
            payload={"phone": NEW_PHONE},
        )
        assert result["accounts_updated"] == 4, result
        held = set(
            customers_models.Contact.objects.filter(
                tenant_id=pine_hill.id, account__in=accounts
            ).values_list("phone", flat=True)
        )
    assert held == {NEW_PHONE}, held


@pytest.mark.django_db
def test_us_cwp_028_tc1_the_new_value_is_there_on_reload_and_the_audit_names_maria(
    pine_hill, sarah, audit_rows
):
    """TC-1 — and hard rule 7's row, which names the CUSTOMER rather than a
    staff user because a portal customer is not one (`BR-CWP-004`)."""
    switch_on(pine_hill, sarah)
    credential, _ = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        services.update_own_contact_details(
            pine_hill.id,
            actor=principal,
            account_ids=list(principal.account_ids),
            payload={"phone": NEW_PHONE},
        )
        view = selectors.my_details(principal, today=TODAY)
    assert view["phone"] == NEW_PHONE, "the value a reload reads"
    assert view["phone_varies"] is False

    written = [row for row in audit_rows if row["action"] == "portal.contact_detail.updated"]
    assert written, [row["action"] for row in audit_rows]
    actor = written[0]["after"]["actor"]
    assert actor["portal_customer_id"] == str(credential.customer_id)
    assert actor["channel"] == "customer_portal"
    # ⚠ NOT a staff user id, and that is the assertion. A customer's edit and a
    # clerk's must be distinguishable in the one record that exists to tell
    # them apart.
    assert written[0]["actor_user_id"] is None


@pytest.mark.django_db
def test_us_cwp_028_tc2_a_new_legal_name_is_REFUSED_and_the_stored_name_is_UNCHANGED(
    pine_hill, sarah
):
    """`BR-CWP-026` — refused **at the endpoint's service**, by name, and
    before anything at all is written."""
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.BizError) as raised:
            services.update_own_contact_details(
                pine_hill.id,
                actor=principal,
                account_ids=list(principal.account_ids),
                # ⚠ The email rides along on purpose: it is the field that
                # WOULD have been written if the refusal came second.
                payload={"email": NEW_EMAIL, "full_name": "Maria Alvarez-Ruiz"},
            )
        assert raised.value.message_key == "portal.myDetails.refused.name"
        assert raised.value.br_ref == "BR-CWP-026"
        names = set(
            customers_models.Contact.objects.filter(
                tenant_id=pine_hill.id, account__in=accounts
            ).values_list("full_name", flat=True)
        )
        emails = set(
            customers_models.Contact.objects.filter(
                tenant_id=pine_hill.id, account__in=accounts
            ).values_list("email", flat=True)
        )
    assert names == {LEGAL_NAME}, names
    assert emails == {OLD_EMAIL}, "nothing was written before the refusal"


@pytest.mark.django_db
def test_us_cwp_028_the_account_holder_is_refused_with_its_OWN_message(pine_hill, sarah):
    """Two refusals, two sentences. *We cannot change your name here* and *we
    cannot change who holds this account* are different asks with different
    routes, and one shared message would send both to the wrong form."""
    switch_on(pine_hill, sarah)
    credential, _ = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.BizError) as raised:
            services.update_own_contact_details(
                pine_hill.id,
                actor=principal,
                account_ids=list(principal.account_ids),
                payload={"account_holder": "Someone Else"},
            )
    assert raised.value.message_key == "portal.myDetails.refused.holder"


@pytest.mark.django_db
def test_the_word_the_CONTRACT_publishes_as_refused_gets_the_name_sentence(pine_hill, sarah):
    """⚠ **THE READ SERVES `legal_name` AND THE REFUSAL MAP HELD ONLY
    `full_name`** (CR-085 group I, found on the running product 2026-09-08).

    `GET portal/my-details` answers `refused: ["legal_name", "account_holder"]`
    — those two words ARE the contract — and a client posting the word it was
    given fell through to *"We cannot change that here."* while the sentence
    written for exactly this case, *"We cannot change your name here."*, sat
    unused. The test above proves the map for `full_name`, which is the MODEL's
    column and a word no client is ever handed.
    """
    switch_on(pine_hill, sarah)
    credential, _ = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        view = selectors.my_details(principal_for(pine_hill, credential), today=TODAY)
    for field in view["refused"]:
        with tenant_context(pine_hill.id):
            with pytest.raises(errors.BizError) as raised:
                services.update_own_contact_details(
                    pine_hill.id,
                    actor=principal,
                    account_ids=list(principal.account_ids),
                    payload={field: "Someone Else"},
                )
        assert raised.value.message_key != "portal.myDetails.refused.unknown", field
        assert raised.value.params["field"] == field


@pytest.mark.django_db
def test_us_cwp_028_tc8_returned_post_is_counted_and_correcting_the_address_clears_it(
    pine_hill, sarah
):
    """`BR-CWP-086`. Two letters came back; the customer fixes the address; the
    flag goes. Leaving it up after the one thing it asked for teaches a
    customer to ignore the next one."""
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    principal = principal_for(pine_hill, credential)
    with tenant_context(pine_hill.id):
        for account in accounts[:2]:
            customers_models.Address.objects.create(
                tenant_id=pine_hill.id,
                account=account,
                kind=portal_self_service.MAILING,
                line1="1408 Elm St",
                city="Austin",
                state="TX",
                postal_code="78704",
            )
            account.bad_address = True
            account.save(update_fields=["bad_address"])
        before = selectors.my_details(principal, today=TODAY)
        assert before["returned_post_accounts"] == 2, before

        services.update_own_contact_details(
            pine_hill.id,
            actor=principal,
            account_ids=list(principal.account_ids),
            payload={"postal": {"line1": "22 Palm Ct", "city": "Austin", "state": "TX",
                                "postal_code": "78702"}},
        )
        after = selectors.my_details(principal, today=TODAY)
    assert after["returned_post_accounts"] == 0, after
    assert after["postal"]["line1"] == "22 Palm Ct"


@pytest.mark.django_db
def test_us_cwp_028_tc7_the_tenant_filter_is_in_the_QUERY_and_not_a_check_after_it(
    pine_hill, oak_ridge, sarah, elena
):
    """Isolation the way hard rule 1 means it.

    ⚠ **THE ASSERTION IS DELIBERATELY THE OTHER WAY ROUND FROM THE OBVIOUS
    ONE.** Rather than seeding a second utility's account and hoping this
    function ignores it, this drives the function with **Oak Ridge's tenant id
    and Pine Hill's account ids** — the exact shape a confused caller produces
    — and asserts that NOTHING was written and no refusal was needed. The
    account simply does not come back from `filter(tenant_id=…, id=…)`.

    That is a stronger statement than *the other tenant's row is unchanged*: it
    proves the filter is IN the query. A version that filtered afterwards would
    have to raise, and raising would tell an Oak Ridge caller that a Pine Hill
    account exists.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    credential, accounts = maria_with_four(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        result = services.update_own_contact_details(
            oak_ridge.id,
            actor=principal_for(pine_hill, credential),
            account_ids=[str(one.pk) for one in accounts],
            payload={"email": NEW_EMAIL},
        )
    assert result["accounts_updated"] == 0, result
    with tenant_context(pine_hill.id):
        held = set(
            customers_models.Contact.objects.filter(
                tenant_id=pine_hill.id, account__in=accounts, is_primary=True
            ).values_list("email", flat=True)
        )
    assert held == {OLD_EMAIL}, held


@pytest.mark.django_db
def test_us_cwp_028_the_screen_is_told_when_the_four_accounts_DISAGREE(pine_hill, sarah):
    """⚠ **A MISSING VALUE IS A DISAGREEMENT, NOT A BLANK.** Three accounts
    with an email and one without is one bill going nowhere; showing the
    majority silently would tell a customer their email is right where it is
    not."""
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        row = customers_models.Contact.objects.filter(
            tenant_id=pine_hill.id, account=accounts[0]
        ).first()
        row.email = None
        row.save(update_fields=["email"])
        view = selectors.my_details(
            principal_for(pine_hill, credential), today=TODAY
        )
    assert view["email_varies"] is True, view
    assert view["email"] == OLD_EMAIL, "the majority is shown, and flagged"


@pytest.mark.django_db
def test_us_cwp_028_the_body_names_what_it_REFUSES_so_the_screen_can_show_it(
    pine_hill, sarah
):
    """`BR-CWP-026` again, from the read side. The legal name is IN the body —
    a field left out reads as an oversight, a field shown read-only with *ask
    us to change this* reads as a rule."""
    switch_on(pine_hill, sarah)
    credential, _ = maria_with_four(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        view = selectors.my_details(principal_for(pine_hill, credential), today=TODAY)
    assert view["legal_name"] == LEGAL_NAME
    assert set(view["refused"]) == {"legal_name", "account_holder"}
    assert view["security"]["devices_signed_in"] >= 0
    assert view["account_count"] == 4


@pytest.mark.django_db
def test_us_cwp_028_tc9_the_picker_offers_ENGLISH_AND_SPANISH_AND_NOTHING_ELSE(
    pine_hill, sarah
):
    """**PO ruling 2026-09-07, verbatim: *"currently in drop down show only 2
    elnglish and spanish"*** — `DEF-CWP-4442`, building the ruling of
    2026-09-05 that the constant carried unbuilt for two days.

    ⚠ **THIS CASE ASSERTED ELEVEN UNTIL 2026-09-07 AND IT WAS ASKING THE WRONG
    QUESTION, NOT MERELY THE WRONG NUMBER.** It compared the wire list to the
    catalogue FOLDER for equality, which folds the two registries `BR-CWP-105`
    says must never be folded: `LOCALE_CODES` answers *can this build DRAW it*
    and `PORTAL_LOCALES` answers *may the portal OFFER it*. Equality made the
    second question un-askable — the day a catalogue was added the offer had to
    grow with it or this test went red, which is exactly the coupling the
    Product Owner's ruling breaks.

    The drift guard it was written for survives as the **subset** below: an
    offered code with no catalogue behind it is still a picker offering a
    language nothing renders, and that is what this now refuses."""
    from pathlib import Path

    switch_on(pine_hill, sarah)
    credential, _ = maria_with_four(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        view = selectors.my_details(principal_for(pine_hill, credential), today=TODAY)
    assert view["locales"] == ["en", "es"], view["locales"]
    # ⚠ **THE SPANISH IS `es` AND NOT `es-MX`, AND THAT IS THE RULING READ
    # LITERALLY.** The Product Owner said TWO — *English and Spanish* — and
    # `es` is the code whose own name is *Español*. `es-MX` remains a
    # catalogue this build draws (`BR-SHL-041`) and a lawful stored value; it
    # is simply not one of the two the portal OFFERS, and a reader already on
    # it keeps it as the third option their own picker adds.
    assert "es-MX" not in view["locales"] and "de" not in view["locales"]

    locales_dir = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    on_disk = {path.stem for path in locales_dir.glob("*.json")} if locales_dir.is_dir() else set()
    if on_disk:
        assert set(view["locales"]) <= on_disk, (
            f"the portal offers a language no catalogue draws: wire={sorted(view['locales'])} "
            f"disk={sorted(on_disk)}"
        )


@pytest.mark.django_db
def test_us_cwp_028_the_seam_reads_the_MAILING_address_and_never_the_retired_kind(
    pine_hill, sarah
):
    """Hard rule 8 — `kind='service'` is RETIRED and a fourth home for an
    address fails `G85`. This asserts the seam looks at `mailing` and at
    nothing else, so a lane restoring the retired value cannot make this screen
    quietly start reading it."""
    assert customers_seam.ADDRESS_MAILING == "mailing"
    assert portal_self_service.MAILING == "mailing"
    switch_on(pine_hill, sarah)
    credential, accounts = maria_with_four(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        customers_models.Address.objects.create(
            tenant_id=pine_hill.id, account=accounts[0], kind="service",
            line1="NEVER READ", city="Austin",
        )
        view = selectors.my_details(principal_for(pine_hill, credential), today=TODAY)
    assert view["postal"] is None, "a retired kind is not a postal address"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-028@this-commit (EP-CWP-06 story + BR-CWP-026/086/010 verbatim + OQ-CWP-1562's closure + BR-CWP-103)
# generated: 2026-09-04 by the CR-068 wave G build lane
# checklist: A✔ B✔ C✔ D✔(api.py my-details) E✔(CWP-024) F✔ G✔ H=n/a(no money column is written)
# gates: pytest tests/test_us_cwp_028_my_details.py · G81 · G84
# exceptions: TC-3/4/5/9's CWP-025 half is US-CWP-030's (wave H) — write_points.py assigned the preference kind's second function there before this wave started; see the module docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
