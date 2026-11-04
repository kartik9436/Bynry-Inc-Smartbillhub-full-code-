# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-4440 — the customer portal never applied a language. PO on
#           the running product 2026-09-07: *"Language setting does not work in
#           customer portal"*. `i18n.changeLanguage` was called in exactly ONE
#           place in the whole application and it was the STAFF shell; the
#           portal is that shell's sibling in the route tree and had zero i18n
#           references. This file is the BACKEND half: the two values, on the
#           two payloads, through the two doors.
# Rules:    BR-CWP-105 (the order, and whose language wins — PO ruling
#           2026-09-07) · BR-CUS-064 (`accounts.preferred_language`) ·
#           BR-SHL-030 (what the staff shell does with the tenant's) ·
#           BR-CWP-021 (never a person on the guest surface) ·
#           BR-CWP-005 / hard rule 1 (tenant scoping) · hard-won law 3
#           (defaults fail closed) · hard-won law 5 (one source, never a copy)
# ───────────────────────────────────────────────────────
"""Whose language the portal is served, and on which door.

⚠ **THE TWO PAYLOADS ARE THE WHOLE DESIGN AND HALF THIS FILE IS ABOUT THE
NEGATIVE.** The TENANT's language rides on the anonymous front payload because
the guest half of the portal has no other payload at all. The CUSTOMER's own
language must NOT follow it there: `GET /portal/public/front` is
`authentication_classes([])`, so anyone on the internet may call it with a
tenant slug, and *the account at this address prefers Spanish* is a fact about
a person (`BR-CWP-021`). A test that only checked the session payload carried
the right value would pass just as happily over a build that leaked it to every
visitor.

⚠ **AND EVERY CASE THAT ASSERTS A LANGUAGE SETS IT FIRST.** Reading a payload
once proves a key exists; it cannot tell a served setting from a hardcoded
string — and a hardcoded string is precisely what `DEF-SHL-3964` was.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.portal import guest_api
from apps.tenancy import models as tenancy_models
from apps.customers import models as customers_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)
from tests.test_us_ten_helpers import api_call


def _front(tenant):
    return api_call(
        guest_api.front, "get", f"/api/{tenant.subdomain}/portal/public/front", tenant=tenant
    ).data


def _set_language(tenant, language):
    """Write the column Settings → Regional writes, and nothing else."""
    row, _ = tenancy_models.TenantSettings.objects.get_or_create(tenant_id=tenant.id)
    row.language = language
    row.save(update_fields=["language"])
    return row


def _set_account_language(tenant, account, language):
    """Write the column `CWP-024`'s picker writes (`BR-CUS-064`)."""
    with tenant_context(tenant.id):
        customers_models.Account.objects.filter(tenant_id=tenant.id, pk=account.pk).update(
            preferred_language=language
        )


def _signed_in(tenant):
    client = Client()
    answer = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data=json.dumps({"email": MARIA_EMAIL, "password": MARIA_PASSWORD}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


# ══ The utility's own language, on the guest door ═════════════════════════


@pytest.mark.django_db
def test_the_front_payload_carries_the_tenants_own_language(pine_hill, sarah):
    """The half of the defect a guest experiences.

    A utility that chose *Español (México)* on Settings → Regional got a
    Spanish staff app and an English portal, because this value had no way to
    reach the portal at all.
    """
    switch_on(pine_hill, sarah)
    _set_language(pine_hill, "es-MX")
    assert _front(pine_hill)["regional"]["language"] == "es-MX"


@pytest.mark.django_db
def test_a_language_changed_in_settings_follows_to_the_portal_immediately(pine_hill, sarah):
    """Read, change, read again — the two answers differ, with no sync between.

    A single read cannot tell a served setting from a constant; this is the
    only shape that can.
    """
    switch_on(pine_hill, sarah)
    _set_language(pine_hill, "en")
    assert _front(pine_hill)["regional"]["language"] == "en"
    _set_language(pine_hill, "de")
    assert _front(pine_hill)["regional"]["language"] == "de"


@pytest.mark.django_db
def test_an_unset_language_travels_as_an_absence_and_never_as_english(pine_hill, sarah):
    """hard-won law 3, and it is the sibling defect's own lesson.

    `DEF-SHL-3964` was made entirely of a plausible default. A caller that
    cannot tell *not set* from *the tenant says English* would pin English over
    a utility whose setting simply has not been chosen, and the front end could
    never fall through to the reader's own browser.
    """
    switch_on(pine_hill, sarah)
    _set_language(pine_hill, None)
    assert _front(pine_hill)["regional"]["language"] is None


@pytest.mark.django_db
def test_an_empty_string_is_not_a_choice(pine_hill, sarah):
    """`tenant_settings.language` is a bare TEXT column.

    `""` reaching the front end is `changeLanguage("")`, which i18next treats
    as a language to switch to. An empty string is an absence and is served as
    one.
    """
    switch_on(pine_hill, sarah)
    _set_language(pine_hill, "")
    assert _front(pine_hill)["regional"]["language"] is None


@pytest.mark.django_db
def test_the_holding_page_carries_it_too(pine_hill):
    """A switched-off portal still serves the holding page and the payload
    shape does not change with the switch — the same posture the date format
    takes one field over."""
    _set_language(pine_hill, "de")
    body = _front(pine_hill)
    assert body["is_live"] is False
    assert body["regional"]["language"] == "de"


@pytest.mark.django_db
def test_one_tenants_language_never_reaches_another(pine_hill, sarah, oak_ridge, elena):
    """`BR-CWP-005` / hard rule 1 — the read is scoped to the tenant on the
    path. This is the case that would catch a seam reading the context tenant
    while answering for another."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _set_language(pine_hill, "es-MX")
    _set_language(oak_ridge, "hi")
    assert _front(pine_hill)["regional"]["language"] == "es-MX"
    assert _front(oak_ridge)["regional"]["language"] == "hi"


# ══ The customer's own language, on the signed-in door — and ONLY there ═══


@pytest.mark.django_db
def test_the_session_payload_carries_this_customers_own_language(pine_hill, sarah):
    """PO ruling 2026-09-07: *"a signed-in customer will get their account's
    own preferred language."*"""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    _set_account_language(pine_hill, account, "de")
    body = _signed_in(pine_hill).get(f"/api/{pine_hill.subdomain}/portal/session").json()
    assert body["language"] == "de"


@pytest.mark.django_db
def test_the_customers_language_is_independent_of_the_utilitys(pine_hill, sarah):
    """*"Signed customer should get their own references"* — the two values are
    carried separately so the front end can rank them. A build that overwrote
    one with the other would pass a test that only ever set one."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    _set_language(pine_hill, "es-MX")
    _set_account_language(pine_hill, account, "de")
    client = _signed_in(pine_hill)
    assert client.get(f"/api/{pine_hill.subdomain}/portal/session").json()["language"] == "de"
    assert _front(pine_hill)["regional"]["language"] == "es-MX"


@pytest.mark.django_db
def test_a_customer_who_has_stated_nothing_answers_nothing(pine_hill, sarah):
    """`None`, not the tenant's value. The ranking is the FRONT END's job
    (`BR-CWP-105`); a server that helpfully substituted the tenant default here
    would make the customer's silence indistinguishable from their agreement,
    and the guest dropdown's choice could never sit between them."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    _set_language(pine_hill, "es-MX")
    _set_account_language(pine_hill, account, None)
    body = _signed_in(pine_hill).get(f"/api/{pine_hill.subdomain}/portal/session").json()
    assert body["language"] is None


@pytest.mark.django_db
def test_the_customers_language_is_on_NO_guest_route(pine_hill, sarah):
    """⚠ **THE NEGATIVE, AND IT IS THE ONE THAT PROTECTS A PERSON.**

    `BR-CWP-021` — never a person on the guest surface. The front payload is
    anonymous and anyone may call it with a slug; *the account at this address
    prefers German* is a fact about somebody. This asserts the value the
    session serves does not appear ANYWHERE in the guest body, rather than
    checking three named keys, because the next lane's convenience field is
    exactly what a named-key check does not see.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    _set_language(pine_hill, "es-MX")
    _set_account_language(pine_hill, account, "ko-KR")
    body = _front(pine_hill)
    assert body["regional"]["language"] == "es-MX"
    assert "ko-KR" not in json.dumps(body), body


@pytest.mark.django_db
def test_the_shell_and_the_picker_read_ONE_function(pine_hill, sarah):
    """hard-won law 5, asserted rather than commented.

    `selectors.account_language` opens the picker on `CWP-024` AND answers the
    shell. Two folds over one column is how the language a customer CHOOSES and
    the language they READ come to disagree, and nothing would go red when they
    did — so this compares the two answers directly.
    """
    from apps.portal import selectors

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    _set_account_language(pine_hill, account, "it-IT")
    client = _signed_in(pine_hill)
    served = client.get(f"/api/{pine_hill.subdomain}/portal/session").json()["language"]
    picker = client.get(f"/api/{pine_hill.subdomain}/portal/my-details").json()["locale"]
    assert served == picker == "it-IT"
    assert selectors.account_language.__module__ == "apps.portal.selectors"


# ══ What the portal may OFFER — DEF-CWP-4442 ══════════════════════════════
#
# ⚠ **A DIFFERENT QUESTION FROM EVERY CASE ABOVE, AND `BR-CWP-105` SAYS SO IN
# ITS OWN WORDS: *do not fold the two registries*.** Everything above asks
# *what language is this person READING* — the chain, its four sources, and
# which door each value travels through. These ask *what may the picker
# OFFER*, which the Product Owner ruled on 2026-09-07: *"currently in drop
# down show only 2 elnglish and spanish"*. Narrowing the OFFER must not move
# the RESOLUTION, and the case below asserts exactly that on a German account.


@pytest.mark.django_db
def test_the_guest_payload_carries_the_two_languages_the_portal_offers(pine_hill, sarah):
    """The guest dropdown had NO list from the server and drew the eleven
    catalogues instead — the fold `BR-CWP-105` forbids, shipped.

    It rides on the FRONT payload for the same reason the tenant's own
    language does: the guest half of the portal has no other payload at all.
    """
    switch_on(pine_hill, sarah)
    assert _front(pine_hill)["locales"] == ["en", "es"]


@pytest.mark.django_db
def test_the_offer_travels_on_the_holding_page_too(pine_hill):
    """⚠ **NOT BECAUSE THE HOLDING PAGE DRAWS A PICKER — IT DRAWS NO NAV AT
    ALL** (`US-CWP-001` TC-3). It travels because `PortalFront.locales` is a
    REQUIRED field on the front end, and a field present on one branch and
    absent on the other is the optional-prop trap `regional` carries its own
    note about one field over: a screen that may forget to handle an absence
    eventually does.
    """
    body = _front(pine_hill)
    assert body["is_live"] is False
    assert body["locales"] == ["en", "es"]


@pytest.mark.django_db
def test_narrowing_the_OFFER_does_not_change_what_a_GERMAN_customer_READS(
    pine_hill, sarah
):
    """**THE CASE THE WHOLE RULING TURNS ON.** Nobody's stored choice is
    reset: a customer whose account says German keeps reading German until
    they change it themselves.

    So the two registries are asserted apart here — the OFFER is two, and the
    same customer's served language is still `de`. A lane that "tidied" this
    by validating `preferred_language` against `PORTAL_LOCALES` would take a
    setting away from a person who chose it, and this case is what goes red.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    _set_account_language(pine_hill, account, "de")
    client = _signed_in(pine_hill)
    served = client.get(f"/api/{pine_hill.subdomain}/portal/session").json()["language"]
    details = client.get(f"/api/{pine_hill.subdomain}/portal/my-details").json()
    assert served == "de", "the resolution moved when only the offer was narrowed"
    assert details["locale"] == "de", "the stored choice was reset"
    # The OFFER stays two. The third option a German reader sees is added by
    # the picker itself, from the value it is opening on — see
    # `offeredLocales` in `07-frontend/src/portal/components/language.ts`.
    assert details["locales"] == ["en", "es"]
