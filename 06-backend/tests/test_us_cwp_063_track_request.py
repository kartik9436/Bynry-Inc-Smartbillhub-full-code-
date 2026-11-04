# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-063 (EP-CWP-11) — track your request: the CUSTOMER-VISIBLE
#           half of a history that already exists. Screen: CWP-051
# Rules:    BR-CWP-078 (transitions plus notes flagged customer-visible, and
#           NEVER internal routing comments) · BR-CWP-079 (withdrawable until
#           approved, and withdrawing does not touch the account) · BR-CWP-024
#           (signed out it returns progress and never data) · BR-CWP-010 (both
#           halves in the query) · BR-CWP-077 (a refusal always carries its
#           reason) · B14 rule 31 (no database id is a visible value)
# Open:     OQ-CWP-1680 — a service request carries no account, so *mine* is
#           matched on the login's own contact phone. TC-7 is what holds it.
# Tests:    this file
# Impacts:  apps/portal/seams/customers_seam.py `_customer_visible_events` ·
#           apps/portal/selectors.py `my_request_detail` · apps/portal/api.py ·
#           apps/customers/service_request_service.py `withdraw_from_portal`
# ───────────────────────────────────────────────────────
"""`US-CWP-063`'s cases — and the one the whole screen exists for.

⚠ **TC-2 IS THE STORY.** A clerk's *"route to Tuesday crew, low priority"* must
appear NOWHERE in the response, and the assertion is over the **whole serialised
body** rather than over a named key — because a field that is served and merely
not drawn is still served, and the next lane to add a key to the projection
would sail past a three-key check.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from django.test import Client

from apps.customers import models as customers_models, service_request_service as writes
from apps.portal import selectors
from apps.portal.seams import customers_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: `US-CWP-063` §4 — the story's own fixture.
ROUTING_NOTE = "route to Tuesday crew, low priority"
CUSTOMER_NOTE = "We need proof of address and your landlord's consent."
REFUSAL_REASON = "The account at this address is in arrears."
MARIA_PHONE = "(512) 555-0134"


def portal_url(tenant, path: str) -> str:
    return f"/api/{tenant.subdomain}/portal/{path}"


def signed_in(tenant, *, email: str = MARIA_EMAIL, password: str = MARIA_PASSWORD):
    client = Client()
    answer = client.post(
        portal_url(tenant, "auth/sign-in"),
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    return client


def maria(tenant, actor):
    """Maria enrolled, holding `1408 Elm St · A`, with her phone on the contact."""
    switch_on(tenant, actor)
    credential = enrol_maria(tenant, actor)
    account = elm_street_account(tenant, actor)
    with tenant_context(tenant.id):
        customers_models.CustomerAccount.objects.get_or_create(
            tenant_id=tenant.id, customer_id=credential.customer_id, account=account
        )
    return credential, account


def a_portal_request(tenant, account, *, what: str = "Moving out on 17 September."):
    """One request raised THROUGH THE PORTAL's own door — never written by the
    test, because a row this test wrote itself would prove nothing about the
    door the product uses."""
    with tenant_context(tenant.id):
        return writes.create_from_portal(
            {
                "applicant_kind": "person",
                "applicant_name": "Maria Alvarez",
                "applicant_phone": MARIA_PHONE,
                "address_as_given": "1408 Elm St · A",
                "what_they_said": what,
            }
        )


def a_principal(tenant, credential):
    """The session's own principal, built through `portal_session.account_set`.

    ⚠ **`account_set` RETURNS `AccountEntry` ROWS AND `principal.account_ids`
    IS THE PROPERTY THAT NARROWS THEM TO IDS.** A test that passed the entries
    straight through would be exercising a shape the edge never sees.
    """
    from apps.portal import session as portal_session

    with tenant_context(tenant.id):
        entries = portal_session.account_set(
            tenant.id, customer_id=credential.customer_id, credential_id=credential.pk
        )

    class _Principal:
        tenant_id = tenant.id
        accounts = entries
        account_ids = tuple(entry.account_id for entry in entries)

    return _Principal


def detail(tenant, credential, reference, *, today=date(2026, 9, 3)):
    with tenant_context(tenant.id):
        return selectors.my_request_detail(
            a_principal(tenant, credential), reference=reference, today=today
        )


# ══ TC-1 · the six steps, with when each happened ══════════════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc1_the_timeline_is_six_steps_and_the_first_two_are_done(pine_hill, sarah):
    """TC-1 — *you sent it · we picked it up · we need something from you …*

    ⚠ **SIX STEPS, ALWAYS.** The screen draws a fixed ladder and marks where the
    request has reached; a timeline that grew and shrank would make *how far
    along am I* a different question on every request.
    """
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        # ⚠ **`pick_up` IS RETIRED (PO ruling 2026-09-19) AND PARKING IS WHAT
        # PICKS A REQUEST UP NOW.** The portal's ladder is unchanged — the
        # customer still sees *we picked it up* — because the step reads the
        # STATE, and park is the one control that still moves `submitted` to
        # `under_review`.
        writes.park(sarah, request.id, waiting_on="documents")

    found = detail(pine_hill, credential, request.request_no)

    assert found is not None
    steps = found["steps"]
    assert [step["key"] for step in steps] == [
        "sent",
        "picked_up",
        "we_need_something",
        "we_decide",
        "in_hand",
        "finished",
    ]
    assert steps[0]["state"] == "done"
    assert steps[1]["state"] == "current"
    assert steps[2]["state"] == "future"
    # ⚠ **THE DATES COME OFF THE TRANSITIONS** (`BR-CWP-078`'s first clause). A
    # first draft filtered EVERY row on `internal` and every step came back
    # dateless, because every state row this product writes is internal.
    assert steps[0]["at"] is not None
    assert steps[1]["at"] is not None
    assert steps[2]["at"] is None, "a step that has not happened has no date"
    # The reference is the identity on screen (B14 rule 31), and there is no id.
    # ⚠ Asserted on the KEY SET rather than on a substring: `"id" not in
    # json.dumps(...)` passes and fails for the wrong reasons — the letters
    # appear inside `what_they_said`, and it found this test rather than a bug.
    assert found["reference"] == request.request_no
    assert "id" not in found
    assert not [key for key in found if key.endswith("_id")], sorted(found)


# ══ TC-2 · THE CASE THE SCREEN EXISTS FOR ══════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc2_an_internal_routing_note_appears_NOWHERE_in_the_body(pine_hill, sarah):
    """⚠ **TC-2 — the negative that is the whole point** (`BR-CWP-078`).

    Asserted over the WHOLE serialised body, not over three named keys: the
    projection could grow a key tomorrow and a narrower check would not notice.
    """
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        writes.add_note(sarah, request.id, note=ROUTING_NOTE)

    body = json.dumps(detail(pine_hill, credential, request.request_no))

    assert ROUTING_NOTE not in body
    assert "Tuesday crew" not in body
    # And the staff read it came off DOES carry it — so this is a projection and
    # not an empty table (the assertion that stops the filter being vacuous).
    from apps.customers import service_request_reads

    with tenant_context(pine_hill.id):
        clerk_side = service_request_reads.history_tab(writes.request_row(request.id))
    assert any(row["note"] == ROUTING_NOTE for row in clerk_side)


@pytest.mark.django_db
def test_us_cwp_063_the_projection_drops_the_actor_and_the_id_by_name(pine_hill, sarah):
    """⚠ **READ THE KEY SET AS THE RULE.** Five keys survive; `id`, `actor`,
    `from_state` and `internal` do not, and each is dropped for a reason written
    into `customers_seam`'s own block comment."""
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        writes.note_from_portal(request.id, note=CUSTOMER_NOTE, customer_visible=True)

    rows = detail(pine_hill, credential, request.request_no)["timeline"]

    assert rows, "a customer-visible row must survive, or the filter is vacuous"
    for row in rows:
        assert set(row) == {"at", "kind", "to_state", "note", "note_type"}, row


# ══ TC-3 · a customer-visible note, in the clerk's words ═══════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc3_a_customer_visible_note_is_present_in_the_clerks_words(
    pine_hill, sarah
):
    """TC-3 — and it is the FIRST row in this product to carry `internal=False`
    (`DEF-CWP-3880`; the clerk's own `add_note` still cannot write one)."""
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        event = writes.note_from_portal(
            request.id, note=CUSTOMER_NOTE, customer_visible=True
        )
    assert event.internal is False

    notes = [row["note"] for row in detail(pine_hill, credential, request.request_no)["timeline"]]
    assert CUSTOMER_NOTE in notes


# ══ TC-4 · withdraw, and the account carries on as normal ══════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc4_withdrawing_ends_the_request_and_the_ACCOUNT_IS_UNTOUCHED(
    pine_hill, sarah
):
    """⚠⚠ **TC-4 SUPERSEDED IN PLACE — THERE IS NO CUSTOMER WITHDRAWAL ANY
    MORE (PO ruling 2026-09-19, `OQ-CUS-12486`).** It asserted a 200 and a
    request left `withdrawn`. The PO's words: *"if customer dont want it - they
    will call and clark will refuse it. thats'it . keep it simple"* — so
    `BR-CWP-079` is SUPERSEDED and `withdraw` is out of `TRANSITIONS`.

    **What TC-4 was really guarding survives and is still asserted FIELD BY
    FIELD: the account is untouched.** It now has to be untouched across a
    REFUSAL of the write rather than across the write, which is the stronger
    reading of *"withdrawing does not touch the account"* — a refused call must
    not half-do anything.

    ⚠ **AND THE REFUSAL MUST BE CLEAN.** The endpoint deliberately STAYS: a
    bookmarked tab or a replayed post still reaches it, and 404 would have
    nothing to say. It answers `BIZ-STATE` with a message key a customer can be
    shown, never a 500 — which is the whole reason the row was taken out of the
    table instead of the route out of the router.
    """
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)

    def account_snapshot():
        with tenant_context(pine_hill.id):
            row = customers_models.Account.objects.get(pk=account.pk)
            return {
                field.name: getattr(row, field.attname, None)
                for field in customers_models.Account._meta.fields
            }

    before = account_snapshot()
    client = signed_in(pine_hill)
    answer = client.post(
        portal_url(pine_hill, f"requests/{request.request_no}/withdraw"),
        data="{}",
        content_type="application/json",
    )

    assert answer.status_code == 409, answer.content
    body = answer.json()
    assert body["code"] == "BIZ-STATE"
    assert body["message_key"] == "customers.serviceRequest.transitionNotAllowed"
    # A refused write must not have half-happened.
    with tenant_context(pine_hill.id):
        assert writes.request_row(request.id).state == "submitted"
    assert account_snapshot() == before, "the account carries on as normal"
    # And the screen never offers the control — it reads the same table.
    assert detail(pine_hill, credential, request.request_no)["may_withdraw"] is False


# ══ TC-5 · withdrawing after approval is refused ═══════════════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc5_withdrawing_after_approval_is_REFUSED(pine_hill, sarah):
    """⚠⚠ **TC-5 REWRITTEN — IT IS NO LONGER *AFTER APPROVAL*, IT IS *EVER*
    (PO ruling 2026-09-19, `OQ-CUS-12486`).** The case read
    `TRANSITIONS[WITHDRAW]` and asserted four states could withdraw and
    `approved` could not. `withdraw` is not in the table at all now.

    **The sentence this case has always been for is unchanged:** the refusal
    comes out of `service_request.TRANSITIONS`, **not out of a second list in
    the portal edge**. That mattered more than anybody knew — `may_withdraw`
    carried a hand-typed copy of those four states under a comment claiming it
    read the table, and it would have gone on drawing a live **Withdraw**
    button over a write the server now refuses (`DEF-CUS-5874`).
    """
    from apps.customers import service_request as rules

    # ⚠ **ASSERTED AGAINST THE TABLE THAT DECIDES IT, AS BEFORE.** There is no
    # state left to name, so the assertion is the absence — and `RETIRED_ACTIONS`
    # is asked rather than the string, so a re-add cannot slip past by renaming.
    assert rules.WITHDRAW in rules.RETIRED_ACTIONS
    assert rules.WITHDRAW not in rules.TRANSITIONS

    # And the ENDPOINT refuses from a state outside those four, end to end.
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        # ⚠ `manual_close` is retired too, so there is no longer a closed state
        # to drive this from — and there no longer needs to be. A plain
        # `submitted` request is now outside the withdrawable set, because the
        # set is empty.
        assert writes.request_row(request.id).state == "submitted"

    client = signed_in(pine_hill)
    answer = client.post(
        portal_url(pine_hill, f"requests/{request.request_no}/withdraw"),
        data="{}",
        content_type="application/json",
    )

    assert answer.status_code >= 400, answer.content
    assert answer.json()["message_key"] == "customers.serviceRequest.transitionNotAllowed"
    with tenant_context(pine_hill.id):
        assert writes.request_row(request.id).state == "submitted"
    # And the screen never offers it — the control reads the same table.
    assert detail(pine_hill, credential, request.request_no)["may_withdraw"] is False


# ══ TC-6 · signed OUT, the same reference answers PROGRESS and never data ══


@pytest.mark.django_db
def test_us_cwp_063_tc6_signed_out_the_same_reference_is_progress_and_never_data(
    pine_hill, sarah
):
    """TC-6 — `BR-CWP-024`. The guest tracker (`CWP-012`) answers six keys and
    none of them is a name, a balance or another reference; the signed-in
    endpoint answers 403 with no session at all. (Eight keys since DEF-CWP-9049.)"""
    _, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)

    with tenant_context(pine_hill.id):
        progress = selectors.track(
            pine_hill.id, reference=request.request_no, second_fact=MARIA_PHONE
        )
    assert progress is not None
    assert set(progress) == {
        "series",
        "reference",
        "status",
        "reported_at",
        "submitted_at",
        "closed_at",
        # `DEF-CWP-9049` (2026-10-02) — may the applicant answer *Ask for more*
        # with a file, and how many more. A yes/no and a count of their OWN
        # files, declared in `guest_fields.py` beside the six; still no name,
        # no balance, no other reference.
        "can_add_document",
        "documents_left",
    }
    body = json.dumps(progress)
    assert "Alvarez" not in body and "Elm" not in body

    stranger = Client().get(portal_url(pine_hill, f"requests/{request.request_no}"))
    assert stranger.status_code in (401, 403), stranger.content


# ══ TC-7 · TENANT ISOLATION ════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc7_the_same_reference_with_an_oak_ridge_session_is_NOT_FOUND(
    pine_hill, sarah, oak_ridge, elena
):
    """⚠ **TC-7 — and it is the assertion `OQ-CWP-1680` rests on.**

    Both halves of the filter are IN THE QUERY (`BR-CWP-010`): the tenant, and a
    phone one of the reader's own accounts carries. This case holds the TENANT
    half with the phone deliberately held CONSTANT — Oak Ridge asking with
    Pine Hill's own number still finds nothing — because a test that changed
    both at once could pass on either.
    """
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    switch_on(oak_ridge, elena)

    with tenant_context(oak_ridge.id):
        theirs = customers_seam.my_request(
            oak_ridge.id, reference=request.request_no, phones=[MARIA_PHONE]
        )
    with tenant_context(pine_hill.id):
        mine = customers_seam.my_request(
            pine_hill.id, reference=request.request_no, phones=[MARIA_PHONE]
        )

    assert theirs is None
    assert mine is not None, "or the isolation assertion is vacuous"
    # And through the screen's own read, for the reader who does hold it.
    assert detail(pine_hill, credential, request.request_no) is not None


@pytest.mark.django_db
def test_us_cwp_063_a_phone_that_is_not_mine_finds_NOTHING(pine_hill, sarah):
    """⚠ **THE OTHER HALF OF THE FILTER, PROVED SEPARATELY.** A request raised
    on somebody else's telephone number is not this login's, and the seam's
    query — not the screen — is what says so (`BR-CWP-010`)."""
    credential, account = maria(pine_hill, sarah)
    mine = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        theirs = writes.create_from_portal(
            {
                "applicant_kind": "person",
                "applicant_name": "Someone Else",
                "applicant_phone": "(512) 555-0999",
                "address_as_given": "77 Nowhere Ln",
                "what_they_said": "Not Maria's request.",
            }
        )

    assert detail(pine_hill, credential, mine.request_no) is not None
    assert detail(pine_hill, credential, theirs.request_no) is None


# ══ TC-9 · *open for* is computed ══════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc9_open_for_is_COMPUTED_and_never_stored(pine_hill, sarah):
    """TC-9 — *1 day*, from `now − raised`. A stored age is wrong by one every
    midnight, which is why no column holds it."""
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        raised_on = writes.request_row(request.id).received_at.date()

    one_day_later = date.fromordinal(raised_on.toordinal() + 1)
    found = detail(pine_hill, credential, request.request_no, today=one_day_later)
    assert found["open_for_days"] == 1

    six_days_later = date.fromordinal(raised_on.toordinal() + 6)
    later = detail(pine_hill, credential, request.request_no, today=six_days_later)
    assert later["open_for_days"] == 6, "the same row, a different day, a different answer"


# ══ TC-10 · a refusal ALWAYS carries its reason ════════════════════════════


@pytest.mark.django_db
def test_us_cwp_063_tc10_a_refused_request_shows_the_refusal_AND_ITS_REASON(
    pine_hill, sarah
):
    """TC-10 — `BR-CWP-077`, and the reason is the clerk's own sentence."""
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        # ⚠ **`pick_up` IS RETIRED (PO ruling 2026-09-19) AND PARKING IS WHAT
        # PICKS A REQUEST UP NOW.** The portal's ladder is unchanged — the
        # customer still sees *we picked it up* — because the step reads the
        # STATE, and park is the one control that still moves `submitted` to
        # `under_review`.
        writes.park(sarah, request.id, waiting_on="documents")
        writes.refuse_request(sarah, request.id, reason=REFUSAL_REASON)

    found = detail(pine_hill, credential, request.request_no)

    assert found["status"] == "refused"
    assert found["refusal_reason"] == REFUSAL_REASON
    assert found["is_open"] is False
    assert found["may_withdraw"] is False


@pytest.mark.django_db
def test_us_cwp_063_the_customer_can_answer_the_clerks_question(pine_hill, sarah):
    """`BR-CWP-075`'s third transition — *answer a question* — end to end
    through the endpoint, and the answer lands on the customer's own timeline."""
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)

    client = signed_in(pine_hill)
    answer = client.post(
        portal_url(pine_hill, f"requests/{request.request_no}/notes"),
        data=json.dumps({"note": "I have posted the tenancy agreement today."}),
        content_type="application/json",
    )

    assert answer.status_code == 201, answer.content
    assert answer.json()["customer_visible"] is True
    notes = [row["note"] for row in detail(pine_hill, credential, request.request_no)["timeline"]]
    assert "I have posted the tenancy agreement today." in notes


@pytest.mark.django_db
def test_us_cwp_063_a_note_with_no_words_is_refused_naming_the_field(pine_hill, sarah):
    """Hard-won law 3 — the empty case refuses rather than writing a blank row."""
    _, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)

    client = signed_in(pine_hill)
    answer = client.post(
        portal_url(pine_hill, f"requests/{request.request_no}/notes"),
        data=json.dumps({"note": "   "}),
        content_type="application/json",
    )

    assert answer.status_code >= 400, answer.content


@pytest.mark.django_db
def test_us_cwp_063_the_seam_projects_the_read_that_already_exists(pine_hill, sarah):
    """⚠ **THE REUSE ASSERTION** (`12-reuse-map.md`). The portal's timeline is
    `service_request_reads.history_tab` FILTERED — never a second walk of
    `service_request_events` — so a clerk and a customer cannot be handed two
    different histories. Patching the staff read empties the customer's."""
    credential, account = maria(pine_hill, sarah)
    request = a_portal_request(pine_hill, account)
    with tenant_context(pine_hill.id):
        writes.note_from_portal(request.id, note=CUSTOMER_NOTE, customer_visible=True)
        row = writes.request_row(request.id)
        assert customers_seam._customer_visible_events(row), "the projection must not be empty"

    from apps.customers import service_request_reads

    original = service_request_reads.history_tab
    try:
        service_request_reads.history_tab = lambda request: []
        with tenant_context(pine_hill.id):
            assert customers_seam._customer_visible_events(row) == []
    finally:
        service_request_reads.history_tab = original
