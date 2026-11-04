# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-060 (EP-CWP-11) — *what do you need: six cards, named by
#           what the customer wants.* Screen: CWP-046
# Rules:    BR-CWP-075 (the customer makes four of the eleven transitions and
#           no more) · BR-CWP-076 (every row carries channel `customer_portal`)
#           · BR-CWP-080 (moving out and stopping service are DIFFERENT) ·
#           BR-CWP-026 (a portal form creates work and changes no account —
#           which is WHY the list is linked by a contact fact and not by an
#           account) ·
#           BR-CWP-093 (nothing empty ever appears) · BR-CWP-010 (tenant AND
#           identity, both IN THE QUERY) · B14 rule 31
# Open:     OQ-CWP-1680 — a service request carries no account and no customer,
#           so what makes one MINE when I am signed in? (the sibling lane's
#           question; this lane's near-duplicate was dropped into it — law 13)
# Tests:    this file
# Impacts:  apps/portal/selectors.py `request_errands` · `request_hub` ·
#           apps/portal/seams/customers_seam.py · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-060`'s cases, and the one fact the whole screen rests on.

⚠ **A PORTAL SERVICE REQUEST CARRIES NO ACCOUNT, BY RULE.**
`create_from_portal` refuses `account` and `customer` by name because
`BR-CWP-026` says *"a public form may create work and may never change an
account"*. So *"my requests"* cannot be an account-scoped read, and the link has
to be made out of what the row does carry: the channel, and a PHONE one of this
login's own accounts holds (`customers_seam.my_requests`). Every test below
either exercises that link or asserts what it cannot see.

⚠ **THE HUB HAD ITS OWN EMAIL-MATCHED READ FOR AN HOUR AND IT WAS DELETED AT
MERGE.** Two lanes in two worktrees each wrote *which requests are mine*, and
two reads of one fact are two answers (`12-reuse-map.md`). The sibling's landed
first and is the one this file exercises.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.test import Client

from apps.customers import models as customers_models
from apps.customers import service_request_service
from apps.portal import sample_data, selectors as portal_selectors, settings_service
from apps.portal.seams.customers_seam import CHANNEL_CUSTOMER_PORTAL
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: `US-CWP-060` §4's own fixture — one open move-out, raised 2 September 2026,
#: waiting on two documents.
RAISED_ON = datetime(2026, 9, 2, 9, 0, tzinfo=UTC)

#: The phone the wave-C fixture puts on `1408 Elm St · A`'s occupant, which is
#: what `contact_phones` finds and what `my_requests` filters on.
MARIA_PHONE = sample_data.OCCUPIER_PHONE


def _maria(tenant, actor):
    """A principal holding Maria's own account — tenant AND the account set."""
    account = elm_street_account(tenant, actor)
    return _Principal(tenant.id, [account.pk])


def a_portal_request(
    tenant,
    *,
    phone: str,
    said: str,
    state: str = customers_models.ServiceRequest.MORE_INFO,
    documents_wanted: int = 0,
    channel: str = CHANNEL_CUSTOMER_PORTAL,
):
    """One request as the portal's own write leaves it, then moved to `state`.

    ⚠ **THROUGH `create_from_portal`, WHICH IS THE ONE DOOR.** A test that wrote
    the row itself would prove nothing about the door the product uses — and in
    particular nothing about `channel` being FORCED, which is the fact the read
    filters on.
    """
    with tenant_context(tenant.id):
        row = service_request_service.create_from_portal(
            {
                "applicant_kind": customers_models.ServiceRequest.APPLICANT_PERSON,
                "applicant_name": "Maria Alvarez",
                "applicant_email": MARIA_EMAIL,
                "applicant_phone": phone,
                "address_as_given": "1408 Elm St · A",
                "what_they_said": said,
            }
        )
        # The state and the received date are a CLERK's world, moved directly
        # here: this file is about the READ, and driving eleven transitions
        # through the staff service would test somebody else's story.
        customers_models.ServiceRequest.objects.filter(pk=row.pk).update(
            state=state, channel=channel, received_at=RAISED_ON
        )
        for index in range(documents_wanted):
            customers_models.ServiceRequestDocument.objects.create(
                tenant=tenant,
                request=row,
                doc_type=customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY
                if index == 0
                else customers_models.ServiceRequestDocument.DOC_TENANCY_OR_DEED,
                required_flag=True,
            )
        return customers_models.ServiceRequest.objects.get(pk=row.pk)


class _Principal:
    """What `request_hub` reads off the session: the tenant AND the account set.

    ⚠ **BOTH, BECAUSE `my_requests` NEEDS BOTH.** The hub walks the login's
    accounts to their contact phones and filters on those — `BR-CWP-010`'s
    identity half — so a principal that carried only a tenant would silently
    return an empty list on every case in this file. The endpoint tests go
    through the real edge; this stands in for the selector-level ones so a read
    can be exercised without eleven HTTP calls.
    """

    def __init__(self, tenant_id, account_ids=()):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in account_ids)


@pytest.mark.django_db
def test_us_cwp_060_tc1_six_cards_in_the_customers_own_words(pine_hill, sarah):
    """TC-1 — six cards, and `BR-CWP-080`'s two are separate cards."""
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        cards = portal_selectors.request_errands(pine_hill.id)
    assert [row["code"] for row in cards] == [
        "move_out",
        "move_home",
        "add_service",
        "stop_for_a_while",
        "report_problem",
        "something_else",
    ]
    # ⚠ BR-CWP-080 — *moving out* and *stopping service for a while* are two
    # different things and the cards say which. One list with five would be the
    # rule broken silently.
    assert cards[0]["code"] != cards[3]["code"]


@pytest.mark.django_db
def test_us_cwp_060_tc1_a_card_either_leads_somewhere_or_says_why_not(pine_hill, sarah):
    """Hard-won law 2 — a card never links to a screen that does not exist.

    Exactly one of `to` and `held_reason` is set on every card, and the SERVER
    decides which, so the wave that builds `CWP-048` moves one map rather than
    two.

    ⚠ **`something_else` JOINED THE LIVE THREE ON 2026-09-05 AND HAD BEEN
    ELIGIBLE SINCE THE DAY BEFORE.** `CWP-054` landed 73 minutes after the card
    was held and the card stayed grey — *"Not online yet — ring us"* over a
    routed screen headed ASK US SOMETHING. What now goes red on the day a
    held card's screen arrives is `tests/test_cwp_holds_expire.py`; this
    assertion pins today's answer, and that one pins the RULE.
    """
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        cards = portal_selectors.request_errands(pine_hill.id)
    for card in cards:
        assert bool(card["to"]) != bool(card["held_reason"]), card
    live = {card["code"]: card["to"] for card in cards if card["to"]}
    assert live == {
        "stop_for_a_while": "/stop-or-restart",
        "report_problem": "/report",
        "something_else": "/ask-a-question",
    }


@pytest.mark.django_db
def test_us_cwp_060_tc4_an_open_request_shows_its_reference_and_what_is_wanted(
    pine_hill, sarah
):
    """TC-4 — `SR-26-0056 · Move out · 2 Sep · we need TWO documents`.

    ⚠ **THE COUNT IS THE SERVER'S AND THE WORDS ARE THE CATALOGUE'S.** A number
    travels; *we need two documents* is written eleven times in eleven
    languages, once each (B14 rule 35).
    """
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    row = a_portal_request(pine_hill, phone=MARIA_PHONE, said="Move out", documents_wanted=2)
    with tenant_context(pine_hill.id):
        hub = portal_selectors.request_hub(_maria(pine_hill, sarah))
    assert len(hub["open_requests"]) == 1
    asked = hub["open_requests"][0]
    assert asked["reference"] == row.request_no
    assert asked["what"] == "Move out"
    assert asked["raised_on"] == "2026-09-02"
    assert asked["documents_wanted"] == 2
    # ⚠ B14 rule 31 — no row id crosses this wire, not even part of one.
    assert "id" not in asked and str(row.pk) not in repr(asked)


@pytest.mark.django_db
def test_us_cwp_060_tc4_a_document_already_verified_is_no_longer_wanted(pine_hill, sarah):
    """*Attaching a file is not the same as verifying it* — the model's own
    line, applied in the direction the customer reads it: a document we have
    CHECKED stops being something we are waiting for."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    row = a_portal_request(pine_hill, phone=MARIA_PHONE, said="Move out", documents_wanted=2)
    with tenant_context(pine_hill.id):
        one = customers_models.ServiceRequestDocument.objects.filter(request=row).first()
        customers_models.ServiceRequestDocument.objects.filter(pk=one.pk).update(
            verification_state=customers_models.ServiceRequestDocument.VERIFIED
        )
        hub = portal_selectors.request_hub(_maria(pine_hill, sarah))
    assert hub["open_requests"][0]["documents_wanted"] == 1


@pytest.mark.django_db
def test_us_cwp_060_tc6_no_open_requests_is_an_empty_list_and_the_cards_remain(
    pine_hill, sarah
):
    """TC-6 — the hub is reachable with nothing on it; the screen writes the
    sentence that names what will fill it (`BR-CWP-093`)."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        hub = portal_selectors.request_hub(_maria(pine_hill, sarah))
    assert hub["open_requests"] == []
    assert len(hub["errands"]) == 6


@pytest.mark.django_db
def test_us_cwp_060_a_finished_request_leaves_the_open_list(pine_hill, sarah):
    """`TERMINAL_STATES` is read from the model and never copied — a completed
    move-out is history, and this list is what is still running."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    a_portal_request(
        pine_hill,
        phone=MARIA_PHONE,
        said="Move out",
        state=customers_models.ServiceRequest.COMPLETED,
    )
    with tenant_context(pine_hill.id):
        hub = portal_selectors.request_hub(_maria(pine_hill, sarah))
    assert hub["open_requests"] == []


@pytest.mark.django_db
def test_us_cwp_060_a_counter_raised_request_is_not_in_the_list(pine_hill, sarah):
    """⚠ **THE COST OF THE CONTACT LINK, ASSERTED RATHER THAN LEFT IMPLICIT**
    (`OQ-CWP-1680`).

    A request carrying a different channel is invisible here even with the same
    applicant phone, because the read filters on both. That is deliberate — the
    body says `lists_only_portal_requests` and the screen says so in words — and
    this test is what stops a later lane widening the filter without noticing
    that the screen's sentence then becomes false.
    """
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    a_portal_request(pine_hill, phone=MARIA_PHONE, said="Asked at the counter", channel="counter")
    with tenant_context(pine_hill.id):
        hub = portal_selectors.request_hub(_maria(pine_hill, sarah))
    assert hub["open_requests"] == []
    assert hub["lists_only_portal_requests"] is True


@pytest.mark.django_db
def test_us_cwp_060_another_customers_request_is_not_in_the_list(pine_hill, sarah):
    """`BR-CWP-010`'s identity half, in the query. A request raised by somebody
    else at the same utility is not this login's."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    a_portal_request(pine_hill, phone="512-555-9999", said="Move out")
    with tenant_context(pine_hill.id):
        hub = portal_selectors.request_hub(_maria(pine_hill, sarah))
    assert hub["open_requests"] == []


@pytest.mark.django_db
def test_us_cwp_060_tc7_a_request_at_another_utility_is_not_in_the_list(
    pine_hill, sarah, oak_ridge, elena
):
    """TC-7 · tenant isolation — Pine Hill's session sees Pine Hill's requests.

    ⚠ **THE TENANT IS IN THE QUERY AND NOT ONLY IN THE DATABASE** (`G96`,
    `BR-CWP-010`). This suite runs on SQLite, which has no row-level security
    at all, so a read that leant on RLS alone would pass this test forever
    while leaking on PostgreSQL the day a `.using()` appeared.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    enrol_maria(pine_hill, sarah)
    a_portal_request(oak_ridge, phone=MARIA_PHONE, said="Move out")
    with tenant_context(pine_hill.id):
        hub = portal_selectors.request_hub(_maria(pine_hill, sarah))
    assert hub["open_requests"] == []


@pytest.mark.django_db
def test_us_cwp_060_tc5_a_utility_with_requests_switched_off_has_no_hub(pine_hill, sarah):
    """TC-5 — the cards are ABSENT and the endpoint REFUSES.

    ⚠ **BOTH HALVES, BECAUSE ONE ALONE IS A SCREEN A CUSTOMER CAN STILL
    REACH.** An endpoint that answered an empty hub would draw a page reading
    *this utility takes no requests online*, which is a different sentence from
    *this page is not here* (`BR-CWP-093`).
    """
    switch_on(pine_hill, sarah, requests_enabled=False)
    enrol_maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        assert portal_selectors.request_errands(pine_hill.id) == []
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    refused = client.get(f"/api/{pine_hill.subdomain}/portal/requests")
    assert refused.status_code == 404, refused.content


@pytest.mark.django_db
def test_us_cwp_060_tc8_a_renamed_card_shows_the_new_label(pine_hill, sarah):
    """TC-8 — read from configuration, never a hardcoded list.

    The tenant's own three-card list replaces the seeded six entirely; nothing
    merges the defaults back in, because a default that survives a
    configuration is a card the utility did not choose to offer.
    """
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        settings_service.save_branding(
            sarah,
            pine_hill.id,
            {
                "request_errands": [
                    {
                        "code": "move_out",
                        "label": "Leaving the property",
                        "hint": "We will close your account",
                        "screen": None,
                    },
                    {
                        "code": "stop_for_a_while",
                        "label": "Turn it off for the winter",
                        "hint": None,
                        "screen": "CWP-052",
                    },
                ]
            },
        )
        cards = portal_selectors.request_errands(pine_hill.id)
    assert [row["label"] for row in cards] == [
        "Leaving the property",
        "Turn it off for the winter",
    ]
    assert cards[1]["to"] == "/stop-or-restart"


@pytest.mark.django_db
def test_us_cwp_060_a_card_naming_a_screen_this_product_does_not_serve_is_refused(
    pine_hill, sarah
):
    """A configured `screen` this product does not serve would render a card
    with no destination AND no reason — a control that neither works nor says
    why, which is the shape `BR-CWP-056` exists to forbid. `None` is the lawful
    way to say *this errand has no screen yet*."""
    from core import errors

    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError):
            settings_service.save_branding(
                sarah,
                pine_hill.id,
                {"request_errands": [{"code": "move_out", "label": "x", "screen": "CWP-999"}]},
            )


@pytest.mark.django_db
def test_us_cwp_060_the_hub_is_never_cached(pine_hill, sarah):
    """`BR-CWP-047` — the body names what this customer has asked the utility
    for, which is theirs and nobody else's."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    response = client.get(f"/api/{pine_hill.subdomain}/portal/requests")
    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"]
    assert len(response.json()["errands"]) == 6


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-060@b50adaa0 (EP-CWP-11)
# generated: 2026-09-04 by the CR-068 ending lane
# checklist: A✔ B✔ C✔ D✔(api.request_hub) E✔(portal/requests/Requests.tsx) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_060_request_hub.py · G81 · G84 · G96 · G82
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
