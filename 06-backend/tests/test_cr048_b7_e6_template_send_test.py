# ── Trace ──────────────────────────────────────────────
# Story:    CR-048 task B7 (send test) + task E6 (the two controls on SET-10)
#           Screens: SET-10 (template detail)
# Rules:    BR-NOT-005 (queue only; NO synchronous send endpoint anywhere) ·
#           BR-NOT-013 (delivery is out of this release on every channel) ·
#           BR-NOT-024 (print is the floor on the four CUSTOMER documents, and
#           `test` is deliberately not one of them) · BR-NOT-027 (a sent legal
#           document is frozen as the document — and a rehearsal is not one) ·
#           BR-SHL-025 (a control that cannot act renders DISABLED WITH ITS
#           REASON, never hidden and never enabled over a route that refuses) ·
#           BR-BIL-026 (the version is pinned at queue time) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 6 (idempotency) ·
#           rule 7 (every queue write is audited)
# ───────────────────────────────────────────────────────
"""SET-10's "Send test to me", from the button's own screen.

**WHAT WAS ACTUALLY WRONG, AND IT WAS A SENTENCE RATHER THAN A GAP.** The send
test itself has worked since CR-009 — on the NOTIFICATION RULES screen, keyed on
an event. The TEMPLATE screen served `can_test_send: false` beside the sentence
*"No test send in this release, on any channel"*, and that sentence stopped
being true the day the rules screen shipped one. A utility reading it was told
the product cannot do something the product does.

So these cases pin the two halves that must stay joined:

* `…_offers_the_test_when_it_can_actually_be_queued` — the button is enabled
  only where a real row can really be written, which for the signed-in user
  means a channel this platform holds an address for;
* `…_a_printed_template_is_refused_in_a_sentence_about_paper` — and where it
  cannot, the control still RENDERS, disabled, with the reason (BR-SHL-025).
  There is no way to post a test letter to yourself, and that is a different
  refusal from "no provider is connected" with a different fix.

Read `…_pressing_the_button_twice_writes_two_rows` next. It is the OPPOSITE of
the usual idempotency case and getting it backwards is `DEF-2512`, filed on this
CR: every payment-plan notice shared one key, so a customer was chased once and
never again, and `created=False` is indistinguishable from a replay. A person
pressing "Send test" a second time is asking for a second rehearsal.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.urls import Resolver404, resolve

from apps.notifications import in_app, models, rule_service, seed_templates, templates_api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_actions, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: An EMAIL class with a body the platform actually seeds. Chosen rather than
#: invented: a test that registered its own wording would be testing a string
#: this lane wrote instead of the one a utility would really rehearse.
EMAIL_CODE = "email_bill_ready"
#: A PRINT class. `dunning` is the reminder A13 writes and `seed_templates`
#: plants verbatim, so it resolves without this file authoring anything.
PRINT_CODE = "dunning"
#: The IN-APP class — the one channel with a real adapter (BR-NOT-019), and
#: therefore the one where a send test proves the whole pipeline.
IN_APP_CODE = "staff_bulk_summary"


#: The seeder takes the generation date as an ARGUMENT and never reads a clock
#: (BR-TEN-043), so the contract classes resolve deterministically.
SEED_DATE = date(2026, 8, 30)


def _seeded(actor):
    seed_templates.seed_notice_templates(actor, on_date=SEED_DATE)


def _get(view, tenant, actor, role="system_admin", **kwargs):
    return api_call(
        view, "get", user=getattr(actor, "user", None), role=role, tenant=tenant, **kwargs
    )


def _post(view, tenant, actor, data=None, role="system_admin", **kwargs):
    return api_call(
        view,
        "post",
        user=getattr(actor, "user", None),
        role=role,
        tenant=tenant,
        data=data or {},
        **kwargs,
    )


def _test_rows():
    return list(
        models.OutboundMessage.objects.filter(source_type=rule_service.TEST_SOURCE_TYPE)
    )


# ══════════════════════════════════════════════════════════════════════════
# E6 · WHAT THE SCREEN SAYS BEFORE ANYBODY PRESSES ANYTHING
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_e6__the_screen_offers_the_test_when_it_can_actually_be_queued(brazos, dana):
    """`can_test_send` is TRUE on an email template, and the sentence beside it
    is about DELIVERY rather than about the button.

    ⚠ **THIS ASSERTED `is False` UNTIL CR-048 B7.** The old sentence read *"No
    test send in this release, on any channel"* and it was accurate when it was
    written and false by the time it was read — the notification-rules screen
    had shipped a working one. The reason a control is disabled is drawn on a
    utility's screen, so it decays like any other claim about the product.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        detail = _get(templates_api.template_detail, brazos, dana, code=EMAIL_CODE)
    assert detail.status_code == 200
    assert detail.data["can_test_send"] is True
    reason = detail.data["test_send_reason"]
    assert dana.user.email in reason, (
        "a person about to send themselves a test must be told WHICH address it "
        f"goes to before they press it: {reason!r}"
    )
    assert "No test send in this release" not in reason


def test_cr048_e6__a_printed_template_is_refused_in_a_sentence_about_paper(brazos, dana):
    """BR-SHL-025. The control still renders; the reason is the true one.

    A print template's test cannot go anywhere because the platform holds an
    email address and a mobile number for a user and no postal address — which
    is a DIFFERENT refusal from "no provider is connected", with a different
    fix, so it must not be spelled the same way.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        detail = _get(templates_api.template_detail, brazos, dana, code=PRINT_CODE)
    assert detail.data["can_test_send"] is False
    assert "post a test letter to yourself" in detail.data["test_send_reason"]


def test_cr048_e6__the_reason_is_a_sentence_a_clerk_can_read(brazos, dana):
    """No ids, no codes, on either side of the offer. G28's rule, asserted here
    because this string is drawn on a live screen (DEF-335)."""
    with tenant_ctx(brazos):
        _seeded(dana)
        reasons = [
            _get(templates_api.template_detail, brazos, dana, code=code).data[
                "test_send_reason"
            ]
            for code in (EMAIL_CODE, PRINT_CODE)
        ]
    for reason in reasons:
        for forbidden in ("BR-", "OQ-", "DEF-", "CR-", "A11", "_"):
            assert forbidden not in reason, (
                f"found {forbidden!r} in a sentence a utility reads: {reason!r}"
            )


def test_cr048_e6__the_sample_pdf_stays_refused_and_for_its_own_reason(brazos, dana):
    """E6 asks for two controls and only ONE of them became true. The page
    writer is still billing's and still writes bills, so this half is enabled by
    nothing here — enabling it alongside would be the *"enabled over a route
    that refuses"* BR-SHL-025 forbids."""
    with tenant_ctx(brazos):
        _seeded(dana)
        detail = _get(templates_api.template_detail, brazos, dana, code=EMAIL_CODE)
    assert detail.data["can_download_pdf"] is False
    assert detail.data["download_pdf_reason"]
    assert detail.data["download_pdf_reason"] != detail.data["test_send_reason"]


# ══════════════════════════════════════════════════════════════════════════
# B7 · WHAT THE BUTTON DOES
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b7__the_route_writes_one_real_queue_row_to_the_signed_in_user(brazos, dana):
    """CR-048's own words: *"writes one real queue row addressed to the
    signed-in user"*.

    A REHEARSAL, and the row is the whole point — a fake one proves nothing
    about the machinery. It goes through `services.queue_document`, the one
    write path, so the template pin, the transaction and the audit row are the
    real ones and not a second copy that could disagree.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        response = _post(templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE)
        rows = _test_rows()
    assert response.status_code == 200
    assert response.data["queued"] is True
    assert response.data["template_code"] == EMAIL_CODE
    assert len(rows) == 1
    row = rows[0]
    assert row.recipient_address == dana.user.email
    assert row.status == models.STATUS_QUEUED
    assert row.channel == models.CHANNEL_EMAIL
    assert row.template_version, "BR-BIL-026 — the version is pinned at queue time"


def test_cr048_b7__it_reports_that_it_will_not_be_delivered_and_why(brazos, dana):
    """*"…and reports that it will not be delivered, and why."*

    The verdict is `provider_seam`'s own and is passed through unchanged. A
    result reading only *"queued: true"* tells the person who just clicked that
    a test email is on its way, which is exactly what BR-NOT-013 forbids.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        wire = _post(templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE).data
    assert wire["will_be_delivered"] is False
    assert wire["dispatchable"] is False
    assert wire["problem"] is not None
    assert wire["problem"]["detail"], "a refusal with no reason is not a refusal"


def test_cr048_b7__pressing_the_button_twice_writes_two_rows(brazos, dana):
    """CLAUDE.md rule 6, INVERTED, and deliberately.

    The idempotency tuple is `(tenant, source_type, source_id, channel,
    copy_no)`. Two clicks land on copy 0 and copy 1, so they are two rows and
    not one row and a silent `already_queued`. `DEF-2512` is what the other
    answer costs: a customer chased once and never again, with `created=False`
    indistinguishable from a replay.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        first = _post(templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE)
        second = _post(templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE)
        rows = _test_rows()
    assert first.data["message_id"] != second.data["message_id"]
    assert len(rows) == 2
    assert sorted(row.copy_no for row in rows) == [0, 1]


def test_cr048_b7__the_row_is_audited_as_a_test(brazos, dana, audit_rows):
    """Hard rule 7 audits the queue WRITE. The trail must say TEST **and must
    say which screen queued it**, so nobody reading it later takes the row for a
    message sent to a customer, and so the template button and the rule button
    stay tellable apart."""
    with tenant_ctx(brazos):
        _seeded(dana)
        _post(templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE)
    actions = set(audit_actions(audit_rows))
    assert rule_service.AUDIT_ACTION_TEMPLATE_TEST in actions, actions
    assert rule_service.AUDIT_ACTION_TEMPLATE_TEST != rule_service.AUDIT_ACTION_TEST


def test_cr048_b7__it_writes_no_delivery_row_against_any_customer(brazos, dana):
    """E6: *"writes no delivery row and no money event"*.

    ⚠ **AND BR-NOT-027 IS THE SECOND REASON THIS ROW IS DIFFERENT, ON TOP OF
    THE PRINT FLOOR.** A sent legal document is frozen as the document a
    customer read; a rehearsal addressed to the signed-in user is not a legal
    document and no regulator will ever ask to see it. A later lane sweeping
    "freeze every outbound row" through this module must fail here.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        _post(templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE)
        rows = _test_rows()
    assert rows[0].account_id is None, (
        "a rehearsal is addressed to the person who pressed the button and is "
        "attached to no customer at all"
    )


def test_cr048_b7__the_one_channel_that_really_delivers_is_testable_here_too(brazos, dana):
    """**DEF-265's shape, checked on the new surface before it can repeat.**

    In-app is the ONLY channel this product can actually deliver on
    (BR-NOT-019), so it is the one where a send test proves something end to
    end — and on the rules screen it was, for a while, the one channel the test
    button REFUSED, because it fell through to the "there is no way to post a
    test letter to yourself" branch. A button whose whole job is to prove the
    pipeline, refusing on the only pipeline that runs.

    The address is the signed-in user's own id, resolved through
    `in_app.address_for` rather than re-derived — `str(actor.id)` reads the
    MEMBERSHIP's id on one call path and the USER's on the other, and a message
    queued to the wrong one sits in an inbox nobody opens. This case exists
    because the ACTOR SHAPE differs between calling the service directly and
    calling it through HTTP, and only the HTTP path is exercised here.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        detail = _get(templates_api.template_detail, brazos, dana, code=IN_APP_CODE)
        assert detail.data["can_test_send"] is True, detail.data["test_send_reason"]
        response = _post(templates_api.queue_template_test, brazos, dana, code=IN_APP_CODE)
        rows = _test_rows()
    assert response.status_code == 200
    assert response.data["channel"] == models.CHANNEL_IN_APP
    assert len(rows) == 1
    assert rows[0].recipient_address == in_app.address_for(dana.user)
    # ⚠ AND IT IS STILL ONLY QUEUED. In-app has a real adapter, so this is the
    # one channel where "queued" could quietly become "delivered" — it does not.
    assert rows[0].status == models.STATUS_QUEUED


def test_cr048_b7__a_test_row_gains_no_print_floor(brazos, dana):
    """BR-NOT-024 names FOUR customer documents print is the floor on and `test`
    is deliberately not one of them — *"posting it would spend a stamp to prove
    nothing"*. One click on an email template is one email row and no letter."""
    with tenant_ctx(brazos):
        _seeded(dana)
        _post(templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE)
        channels = {row.channel for row in _test_rows()}
    assert channels == {models.CHANNEL_EMAIL}
    assert models.CHANNEL_PRINT not in channels


# ══════════════════════════════════════════════════════════════════════════
# THE GATES ON THE DOOR
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b7__the_route_resolves_and_no_send_route_is_minted_beside_it(brazos):
    """DEF-112 / DEF-128 — an `api.py` exporting `urlpatterns` is not an
    endpoint until `config/urls.py` includes it. And BR-NOT-005 makes the
    ABSENCE as load-bearing as the presence: the route is `queue-test` because
    it QUEUES, and a name is a contract here."""
    base = f"/api/{brazos.subdomain}/template-catalog/{EMAIL_CODE}"
    assert resolve(f"{base}/queue-test").func is templates_api.queue_template_test
    for forbidden in ("send", "test-send", "send-test"):
        with pytest.raises(Resolver404):
            resolve(f"{base}/{forbidden}")


@pytest.mark.parametrize("role", ["billing_clerk", "executive"])
def test_cr048_b7__only_a_system_admin_may_queue_a_test(brazos, dana, role):
    """A4: Settings & lookup tables are System Admin FULL, Executive VIEW.
    Queueing a row is not viewing.

    ⚠ **THE GATE IS ON THE ROUTE (DEF-2515).** A role check inside a service a
    background worker can reach refuses the worker, because `_JobActor` carries
    no role by design. Nothing schedules a send test — it exists only because a
    person pressed a button — so the door is the right and only place.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        response = _post(
            templates_api.queue_template_test, brazos, dana, code=EMAIL_CODE, role=role
        )
        rows = _test_rows()
    assert response.status_code == 403
    assert rows == [], "a refused click must leave nothing on the queue"
