# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-028 (EP-CWP-06) — the PREFERENCES half. Screen: CWP-025
# Rules:    BR-CWP-087 (paperless is a RECORDED CONSENT — a timestamp, the
#           wording version and a way to withdraw; withdrawal WRITES and never
#           deletes) · BR-NOT-024 / CR-068 R4 (print is the FLOOR on every
#           customer document — PO 2026-08-30, *"don't switch of print for any
#           document it is awayls on"*) · BR-CWP-010 (the account set is
#           intersected in the query, never taken from a body) · BR-CWP-002
#           (the refusal is at the EDGE, not at the screen) · BR-CUS-064 (the
#           language a document renders in) · CLAUDE.md hard rule 7 (audit)
# Tests:    this file — TC-3 (post cannot be switched off), TC-4 (email can),
#           TC-5 (withdrawal writes `withdrawn_on` and does not delete),
#           TC-7 (tenant isolation), TC-9 (eleven locales), TC-10 (one save,
#           four accounts)
# Impacts:  apps/portal/selectors.contact_preferences · services.record_preference
#           · apps/customers/portal_self_service.update_delivery_preferences
# ───────────────────────────────────────────────────────
"""`CWP-025`, and the one thing about it that is not what the drawing shows.

⚠ **THE GRID IS DRAWN PER EVENT AND THE STORE IS NOT.** `08-screen-layouts.md`
draws WHAT WE SEND × POST / EMAIL / TEXT / IN THE PORTAL with a cell per event
per channel; this product holds `accounts.paperless`, `accounts.sms_reminders`
and the print floor — **three facts, not forty-eight**. `US-CWP-028` §5 points
the per-event cell at the *"notification rule catalogue"*, which is
`notification_rules`: one row per event per TENANT, by unique constraint. A
customer saving there would change what every other customer receives.

**So the assertions below are written against the store that exists** — one
answer, applied to every document, stated as such — and the divergence is filed
as `DEF-CWP-3860` with `OQ-CWP-1660` asking where a per-event customer
preference should live. **What is NOT done here is invent a table**, which is
what a lane reading the drawing alone would have done.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.customers import models as customers_models
from apps.portal import models as portal_models
from apps.portal import selectors, services
from apps.portal.seams import notifications_seam
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_cwp_028_my_details import maria_with_four, principal_for

TODAY = date(2026, 9, 5)


def ready(tenant, actor):
    switch_on(tenant, actor)
    credential, accounts = maria_with_four(tenant, actor)
    return principal_for(tenant, credential), accounts


def a_consent(tenant, account, *, agreed_on=None, screen="CWP-009"):
    """One recorded paperless consent, through the write point that ships."""
    with tenant_context(tenant.id):
        row = services.record_preference(
            tenant.id,
            shape=services.SHAPE_PAPERLESS_CONSENT,
            payload={
                "service_request_id": None,
                "taken_on_screen": screen,
                "account_id": str(account.pk),
            },
        )
        if agreed_on is not None:
            row.agreed_on = agreed_on
            row.save(update_fields=["agreed_on"])
    return row


# ══ the grid reads the FLOOR from notifications, never its own copy ════════


@pytest.mark.django_db
def test_post_reads_always_on_every_kind_the_floor_names(pine_hill, sarah):
    """TC-3's first half — the grid renders `ALWAYS` and offers no control.

    ⚠ **THE LIST IS `notifications`' OWN.** This case asserts the two agree
    rather than typing the six kinds out: a tuple copied into the portal would
    go stale the next time the PO widens the floor, and the screen would then
    offer an off switch over a queue that prints anyway.
    """
    principal, _ = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        grid = selectors.contact_preferences(principal, today=TODAY)
    floor = notifications_seam.print_floor_kinds()
    assert floor, "the floor must be readable or the grid must not be drawn"
    assert grid["floor_readable"] is True
    assert [row["kind"] for row in grid["rows"]] == list(floor)
    assert {row["post"] for row in grid["rows"]} == {selectors.CELL_ALWAYS}
    #: The fourth column is a fact rather than a policy: a customer cannot hide
    #: a document from their own documents screen.
    assert {row["portal"] for row in grid["rows"]} == {selectors.CELL_ALWAYS}


@pytest.mark.django_db
def test_the_grid_says_out_loud_that_one_answer_covers_every_document(pine_hill, sarah):
    """⚠ **THE SENTENCE IS THE HONESTY.** Forty-eight switches over two columns
    would look per-row and behave account-wide, which is hard-won law 2 with
    better manners. The read states it so the screen can print it."""
    principal, _ = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        grid = selectors.contact_preferences(principal, today=TODAY)
    assert grid["applies_to_every_document"] is True
    assert grid["account_count"] == 4


# ══ TC-3 — post is refused BY NAME, at the edge ════════════════════════════


@pytest.mark.django_db
def test_tc3_switching_post_off_is_refused_by_name_and_writes_nothing(pine_hill, sarah):
    principal, accounts = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        before = list(
            customers_models.Account.objects.filter(
                tenant_id=pine_hill.id, id__in=[str(a.pk) for a in accounts]
            ).values_list("paperless", "sms_reminders")
        )
        with pytest.raises(errors.BizError) as raised:
            services.record_preference(
                pine_hill.id,
                shape=services.SHAPE_DELIVERY,
                payload={
                    "actor": principal,
                    "account_ids": list(principal.account_ids),
                    "fields": {"post_on": False, "email_on": True},
                },
            )
        #: ⚠ **REFUSED, NOT IGNORED.** A silently dropped field is a screen
        #: that says *saved* over a value that went nowhere.
        assert "post" in str(raised.value.message_key)
        after = list(
            customers_models.Account.objects.filter(
                tenant_id=pine_hill.id, id__in=[str(a.pk) for a in accounts]
            ).values_list("paperless", "sms_reminders")
        )
    #: And the refusal fired BEFORE anything was written — `email_on` was in
    #: the same body and did not land.
    assert after == before


# ══ TC-4 — email genuinely can be switched off ═════════════════════════════


@pytest.mark.django_db
def test_tc4_email_can_be_switched_on_and_off_and_the_grid_reads_it_back(pine_hill, sarah):
    principal, _ = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_DELIVERY,
            payload={
                "actor": principal,
                "account_ids": list(principal.account_ids),
                "fields": {"email_on": True},
            },
        )
        on = selectors.contact_preferences(principal, today=TODAY)
        services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_DELIVERY,
            payload={
                "actor": principal,
                "account_ids": list(principal.account_ids),
                "fields": {"email_on": False},
            },
        )
        off = selectors.contact_preferences(principal, today=TODAY)
    assert on["email_on"] is True
    assert {row["email"] for row in on["rows"]} == {selectors.CELL_ON}
    assert off["email_on"] is False
    assert {row["email"] for row in off["rows"]} == {selectors.CELL_OFF}
    #: ⚠ **AND POST DID NOT MOVE.** These columns only ever ADD a channel
    #: (`BR-BIL-036`); switching email off stops the email, not the letter.
    assert {row["post"] for row in off["rows"]} == {selectors.CELL_ALWAYS}


@pytest.mark.django_db
def test_tc10_one_save_reaches_every_account_this_login_holds(pine_hill, sarah):
    principal, accounts = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        result = services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_DELIVERY,
            payload={
                "actor": principal,
                "account_ids": list(principal.account_ids),
                "fields": {"email_on": True, "text_on": True},
            },
        )
        assert result["accounts_updated"] == 4, result
        held = set(
            customers_models.Account.objects.filter(
                tenant_id=pine_hill.id, id__in=[str(a.pk) for a in accounts]
            ).values_list("paperless", "sms_reminders")
        )
    assert held == {(True, True)}


@pytest.mark.django_db
def test_hard_rule_7_a_preference_change_writes_an_audit_row_naming_the_customer(
    pine_hill, sarah, audit_rows
):
    principal, _ = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_DELIVERY,
            payload={
                "actor": principal,
                "account_ids": list(principal.account_ids),
                "fields": {"text_on": True},
            },
        )
    rows = [row for row in audit_rows if row["action"] == "portal.preference.updated"]
    #: One row per account the save reached — four, the same number the screen
    #: reports back to the customer.
    assert len(rows) == 4, [row["action"] for row in audit_rows]
    #: ⚠ **THE ACTOR IS THE CUSTOMER, NOT A CLERK, AND `actor_user_id` IS NULL**
    #: — `BR-CWP-004` keeps the two apart and a portal customer is not a `User`.
    assert (rows[-1]["after"] or {}).get("actor", {}).get("channel") == "customer_portal"
    assert rows[-1]["actor_user_id"] is None
    #: The trail carries the change and not just the fact of it.
    assert rows[-1]["after"]["sms_reminders"] is True
    assert rows[-1]["before"]["sms_reminders"] is False


# ══ TC-9 — the language picker, eleven catalogues ══════════════════════════


@pytest.mark.django_db
def test_tc9_the_picker_offers_eleven_locales_and_the_choice_is_read_back(pine_hill, sarah):
    principal, accounts = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        grid = selectors.contact_preferences(principal, today=TODAY)
        assert len(grid["locales"]) == 11, grid["locales"]
        assert "es-MX" in grid["locales"]
        services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_DELIVERY,
            payload={
                "actor": principal,
                "account_ids": list(principal.account_ids),
                "fields": {"locale": "es-MX"},
            },
        )
        after = selectors.contact_preferences(principal, today=TODAY)
        #: ⚠ **IT IS THE ACCOUNT'S `preferred_language`** — the column the
        #: document renderer already reads (`BR-CUS-064`), so the choice
        #: changes the language of the NEXT LETTER rather than only the screen.
        held = set(
            customers_models.Account.objects.filter(
                tenant_id=pine_hill.id, id__in=[str(a.pk) for a in accounts]
            ).values_list("preferred_language", flat=True)
        )
    assert after["locale"] == "es-MX"
    assert held == {"es-MX"}


# ══ TC-5 — withdrawal WRITES, and never deletes ════════════════════════════


@pytest.mark.django_db
def test_tc5_withdrawing_paperless_stamps_the_row_and_does_not_delete_it(pine_hill, sarah):
    principal, accounts = ready(pine_hill, sarah)
    a_consent(pine_hill, accounts[0], agreed_on=timezone.now() - timedelta(days=349))
    with tenant_context(pine_hill.id):
        before = selectors.contact_preferences(principal, today=TODAY)["paperless"]
        assert before is not None
        assert before["withdrawn_on"] is None
        assert before["wording_version"], "a consent without its version is not a consent"

        result = services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_WITHDRAW_PAPERLESS,
            payload={"account_ids": list(principal.account_ids)},
        )
        assert result["withdrawn"] == 1
        rows = list(
            portal_models.PortalConsent.objects.filter(
                tenant_id=pine_hill.id, account_id=str(accounts[0].pk)
            )
        )
        after = selectors.contact_preferences(principal, today=TODAY)["paperless"]
    #: ⚠ **THE ROW IS STILL THERE.** A consent given and then withdrawn is a
    #: different fact from no consent at all, and the wording version is the
    #: only evidence of what the person was shown.
    assert len(rows) == 1
    assert rows[0].withdrawn_on is not None
    assert after["withdrawn_on"] is not None
    assert after["wording_version"] == before["wording_version"]


@pytest.mark.django_db
def test_withdrawing_twice_does_not_move_the_date(pine_hill, sarah):
    """The first withdrawal is when they changed their mind; a second stamp
    would quietly rewrite that."""
    principal, accounts = ready(pine_hill, sarah)
    a_consent(pine_hill, accounts[0])
    with tenant_context(pine_hill.id):
        services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_WITHDRAW_PAPERLESS,
            payload={"account_ids": list(principal.account_ids)},
        )
        first = portal_models.PortalConsent.objects.get(
            tenant_id=pine_hill.id, account_id=str(accounts[0].pk)
        ).withdrawn_on
        again = services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_WITHDRAW_PAPERLESS,
            payload={"account_ids": list(principal.account_ids)},
        )
        second = portal_models.PortalConsent.objects.get(
            tenant_id=pine_hill.id, account_id=str(accounts[0].pk)
        ).withdrawn_on
    assert again["withdrawn"] == 0
    assert first == second


@pytest.mark.django_db
def test_an_absent_consent_is_not_a_withdrawn_one(pine_hill, sarah):
    """`US-CWP-014` TC-2, read from the other end: a customer who was never
    asked sees `None`, which the screen must not draw as *you withdrew this*."""
    principal, _ = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        assert selectors.contact_preferences(principal, today=TODAY)["paperless"] is None


# ══ TC-7 — tenant isolation ════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc7_a_pine_hill_session_touches_only_pine_hills_rows(
    pine_hill, sarah, oak_ridge, elena
):
    principal, accounts = ready(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    with tenant_context(oak_ridge.id):
        oak_before = list(
            customers_models.Account.objects.filter(tenant_id=oak_ridge.id).values_list(
                "paperless", flat=True
            )
        )
    with tenant_context(pine_hill.id):
        services.record_preference(
            pine_hill.id,
            shape=services.SHAPE_DELIVERY,
            payload={
                "actor": principal,
                "account_ids": list(principal.account_ids),
                "fields": {"email_on": True},
            },
        )
    with tenant_context(oak_ridge.id):
        oak_after = list(
            customers_models.Account.objects.filter(tenant_id=oak_ridge.id).values_list(
                "paperless", flat=True
            )
        )
    assert oak_after == oak_before


@pytest.mark.django_db
def test_a_field_outside_the_three_is_refused_by_name(pine_hill, sarah):
    """A body naming something this path cannot write is told so rather than
    being dropped — the same posture `update_contact_details` takes."""
    principal, _ = ready(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError):
            services.record_preference(
                pine_hill.id,
                shape=services.SHAPE_DELIVERY,
                payload={
                    "actor": principal,
                    "account_ids": list(principal.account_ids),
                    "fields": {"quiet_hours": "22:00"},
                },
            )
