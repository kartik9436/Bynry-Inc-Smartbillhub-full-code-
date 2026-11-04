# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-nnnn — ⚠ `nnnn` IS A PLACEHOLDER, NOT A TYPO: this lane may
#           not write to the defect register, so the row is handed over in
#           `scratchpad/lane-NOTIF-defects.md` and its id is allocated at merge
#           (`10-scripts/allocate.py defect`). Fill it in here in the same diff.
#           The portal enrolment code is minted, queued and
#           readable by nobody, so a beta tenant with no provider cannot finish
#           an enrolment. PO, on the running product: *"Atleast show me 6 digit
#           code on this screen - so that I can copy and paste it during
#           enrolement"*.
# Ruling:   12-governance/02-decision-log.md 2026-09-05 §2 — the body shows on
#           the queue row ONLY while the tenant has no provider connected for
#           that channel, and the gate is self-disarming rather than a flag.
# Rules:    BR-CWP-033 · BR-NOT-005 · BR-BIL-026 · CLAUDE.md rule 1 · rule 7
#           (read for a credential) · hard-won law 3 · law 7 (prove RED first)
# ───────────────────────────────────────────────────────
"""Both directions of the gate, and the enrolment it exists to unblock.

⚠ **THE CLOSED DIRECTION IS PROVED BY CONNECTING A PROVIDER, NOT BY PATCHING
THE MODULE UNDER TEST.** Monkeypatching `channel_disclosure` would assert that
the branch works and prove nothing about the CONDITION, which is the whole
design — and the condition is a query across three integrations tables and a
registry lookup that a stub would quietly replace. So the email case connects
`email_smtp` through the real `POST /integrations/{key}/connect` +
`/credential` path and reads the door closing.

⚠ **RED PROOF (hard-won law 7), MEASURED — not asserted.** With both closing
branches of `channel_disclosure` inverted to `return True, OPEN_NO_PROVIDER`
and nothing else changed, **five of the eleven cases failed**, each on the
condition it exists to hold:

    test_connecting_a_provider_closes_the_door_by_itself
      AssertionError: connecting a provider must close the door — disclosable
      is True with email_smtp connected · assert True is False
    test_a_configured_smtp_sender_closes_email_with_no_connection_at_all
      assert True is False
    test_a_closed_gate_is_an_answer_and_never_content
      assert answer.data["disclosable"] is False · assert True is False
    test_a_closed_gate_writes_no_audit_row
      AssertionError: nothing was shown, so there is nothing to record
      · assert 1 == 0
    test_the_queue_list_says_which_channels_may_be_read
      AssertionError: assert 'email' not in ['pdf_print', 'email', 'sms']

Restored: `11 passed in 19.55s`.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.integrations import models as integration_models
from apps.notifications import api as notifications_api
from apps.notifications import models as notification_models
from apps.notifications import unsent_preview
from apps.portal import models as portal_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — pine_hill · sarah · pine_exec
from tests.test_us_cwp_helpers import elm_street_account, switch_on
from tests.test_us_int_helpers_b import (  # noqa: F401 — `smtp_adapter` is a FIXTURE
    SMTP_FIELDS,
    post_connect,
    post_credential,
    smtp_adapter,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

ACCOUNT_FACTS = {"postcode": "78702", "last_name": "Alvarez"}


def enrolment_code_row(tenant, actor):
    """Run the REAL enrolment step 1 and hand back the queue row it wrote.

    Nothing is planted: `POST /portal/enrol/find-account` mints the code,
    `credentials.queue_code` writes the outbound row through the seam, and this
    reads the row that call left behind — the same walk `PortalOneTimeCode.
    outbound_message_id` describes.
    """
    switch_on(tenant, actor)
    account = elm_street_account(tenant, actor)
    body = json.loads(
        Client()
        .post(
            f"/api/{tenant.subdomain}/portal/enrol/find-account",
            data=json.dumps({"account_number": account.account_no, **ACCOUNT_FACTS}),
            content_type="application/json",
        )
        .content
    )
    with tenant_context(tenant.id):
        code_row = portal_models.PortalOneTimeCode.objects.get(pk=body["account_ref"])
        queued = notification_models.OutboundMessage.objects.get(pk=code_row.outbound_message_id)
    return queued


def unsent(tenant, actor, message_id, role="system_admin"):
    return api_call(
        notifications_api.outbound_unsent,
        "get",
        user=actor.user,
        role=role,
        tenant=tenant,
        message_id=str(message_id),
    )


def queue_list(tenant, actor, role="system_admin"):
    return api_call(notifications_api.outbound, "get", user=actor.user, role=role, tenant=tenant)


# ══════════════════════════════════════════════════════════════════════════
# THE DEFECT ITSELF — the PO's sentence, as the case that would catch it
# ══════════════════════════════════════════════════════════════════════════


def test_the_six_digit_code_can_be_read_off_the_queue_row(pine_hill, sarah):
    """*"Atleast show me 6 digit code on this screen."* End to end.

    The code asserted here is the one `portal_one_time_code` will accept — it is
    read from the SAME queue row the enrolment screen is waiting on, not from a
    second copy this test made.
    """
    row = enrolment_code_row(pine_hill, sarah)
    answer = unsent(pine_hill, sarah, row.pk)

    assert answer.status_code == 200, answer.data
    assert answer.data["disclosable"] is True
    assert answer.data["reason"] == unsent_preview.OPEN_NO_PROVIDER
    # ⚠ **FACTS-ONLY UNTIL 2026-10-22.** `portal_enrolment_code` had no wording,
    # so the preview showed only what the writer stamped. `CR-189-BRC10`
    # (`DEF-CWP-10402`) seeded its wording, so the row now renders from the
    # pinned version — and the code is in that body as well as in the facts.
    assert answer.data["body_state"] == unsent_preview.BODY_RENDERED
    assert row.render_context["code"] in (answer.data["body"] or "")
    facts = {one["label"]: one["value"] for one in answer.data["facts"]}
    assert "Code" in facts, facts
    assert facts["Code"].isdigit() and len(facts["Code"]) == 6, facts
    assert facts["Code"] == row.render_context["code"]


def test_the_code_that_is_shown_is_the_code_the_enrolment_accepts(pine_hill, sarah):
    """The disclosure is worth nothing if it shows a code that does not work."""
    row = enrolment_code_row(pine_hill, sarah)
    shown = {one["label"]: one["value"] for one in unsent(pine_hill, sarah, row.pk).data["facts"]}[
        "Code"
    ]
    with tenant_context(pine_hill.id):
        code_row = portal_models.PortalOneTimeCode.objects.get(outbound_message_id=row.pk)
    verified = json.loads(
        Client()
        .post(
            f"/api/{pine_hill.subdomain}/portal/enrol/verify-code",
            data=json.dumps({"account_ref": str(code_row.pk), "code": shown}),
            content_type="application/json",
        )
        .content
    )
    assert verified["result"] == "ok", verified


# ══════════════════════════════════════════════════════════════════════════
# THE GATE, BOTH WAYS — and the closing one is proved by CONNECTING something
# ══════════════════════════════════════════════════════════════════════════


def test_with_nothing_connected_every_provider_channel_is_open(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        open_now = unsent_preview.disclosable_channels()
    assert notification_models.CHANNEL_SMS in open_now
    assert notification_models.CHANNEL_EMAIL in open_now
    # ⚠ NEVER in-app. Its provider is this platform, so its messages ARE
    # delivered and its recipient can already read them; `provider_status`
    # answers None for it and this module reads None as *cannot tell*.
    assert notification_models.CHANNEL_IN_APP not in open_now


def test_connecting_a_provider_closes_the_door_by_itself(pine_hill, sarah, smtp_adapter):
    """The self-disarming half of the ruling, exercised rather than asserted.

    No flag is flipped and this module is not patched: an `email_smtp`
    connection with a live credential is made through the product's own two
    endpoints, and the email channel stops answering.
    """
    with tenant_context(pine_hill.id):
        assert notification_models.CHANNEL_EMAIL in unsent_preview.disclosable_channels()

    assert post_connect(pine_hill, sarah, "email_smtp", SMTP_FIELDS).status_code == 201
    assert post_credential(
        pine_hill, sarah, "email_smtp", {"password": "s3cret-mailbox"}
    ).status_code in (200, 201)

    with tenant_context(pine_hill.id):
        assert integration_models.IntegrationCredential.objects.filter(is_active=True).exists()
        may, why = unsent_preview.channel_disclosure(notification_models.CHANNEL_EMAIL)
    assert (
        may is False
    ), "connecting a provider must close the door — disclosable is True with email_smtp connected"
    assert why == unsent_preview.CLOSED_PROVIDER_CONNECTED
    # And the SMS door is untouched: the gate is PER CHANNEL, which is what
    # lets a utility connect email first and still finish an enrolment.
    with tenant_context(pine_hill.id):
        assert unsent_preview.channel_disclosure(notification_models.CHANNEL_SMS)[0] is True


def test_a_broken_provider_read_closes_the_door_and_leaves_the_queue_standing(
    pine_hill, sarah, monkeypatch
):
    """*Cannot tell* is the same side as *connected*, and the LIST still draws.

    `disclosable_channels()` runs on every `GET /outbound`. If a raise from
    integrations escaped, it would take out the *Messages needing attention*
    list — the one screen a clerk opens BECAUSE something is wrong.
    """
    from apps.notifications import provider_seam

    def explode(channel):
        raise RuntimeError("integrations is having a day")

    monkeypatch.setattr(provider_seam, "provider_status", explode)
    with tenant_context(pine_hill.id):
        may, why = unsent_preview.channel_disclosure(notification_models.CHANNEL_SMS)
        assert may is False
        assert why == unsent_preview.CLOSED_PROVIDER_UNKNOWN
        assert unsent_preview.disclosable_channels() == ()
    listed = queue_list(pine_hill, sarah)
    assert listed.status_code == 200, listed.data
    assert listed.data["vocabulary"]["disclosable_channels"] == []


def test_a_configured_smtp_sender_closes_email_with_no_connection_at_all(pine_hill, sarah):
    """*"connect Twilio or an SMTP sender and the body stops showing"* — the
    sender card was the other door the ruling names.

    ⚠ AMENDED 2026-10-22 (`DEF-NOT-10534`): the sender card is gone — the mail
    server lives on Connectors only. The door it guarded is now a Custom SMTP
    connection that exists but CANNOT send yet (no password, *Not set up*):
    a mail server of the utility's own is recorded, so the body stays closed."""
    with tenant_context(pine_hill.id):
        assert unsent_preview.channel_disclosure(notification_models.CHANNEL_EMAIL)[0] is True
        integration_models.IntegrationConnection.objects.create(
            tenant_id=pine_hill.id,
            provider_key="email_smtp",
            environment="production",
            status="not_set_up",
            enabled=False,
            config={"host": "smtp.pinehill.example", "send_from": "billing@pinehillwp.test"},
        )
        may, why = unsent_preview.channel_disclosure(notification_models.CHANNEL_EMAIL)
    assert may is False
    assert why == unsent_preview.CLOSED_PROVIDER_CONNECTED


def test_a_closed_gate_is_an_answer_and_never_content(pine_hill, sarah, smtp_adapter):
    """A closed door answers 200 and says why — it does not refuse, and it does
    not leak the body in a field a screen might read anyway."""
    row = enrolment_code_row(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        notification_models.OutboundMessage.objects.filter(pk=row.pk).update(
            channel=notification_models.CHANNEL_EMAIL
        )
    post_connect(pine_hill, sarah, "email_smtp", SMTP_FIELDS)
    post_credential(pine_hill, sarah, "email_smtp", {"password": "s3cret-mailbox"})

    answer = unsent(pine_hill, sarah, row.pk)
    assert answer.status_code == 200
    assert answer.data["disclosable"] is False
    assert answer.data["reason"] == unsent_preview.CLOSED_PROVIDER_CONNECTED
    assert answer.data["body"] is None
    assert answer.data["subject"] is None
    assert answer.data["facts"] == []
    # The whole body, not three named keys: a later field carrying the code
    # would pass a check that only looked at `body`.
    assert row.render_context["code"] not in json.dumps(answer.data, default=str)


# ══════════════════════════════════════════════════════════════════════════
# RULE 7, READ FOR A CREDENTIAL
# ══════════════════════════════════════════════════════════════════════════


def test_every_disclosure_writes_an_audit_row_and_the_code_is_not_in_it(
    pine_hill, sarah, audit_rows
):
    row = enrolment_code_row(pine_hill, sarah)
    before = len([one for one in audit_rows if one["action"] == unsent_preview.AUDIT_ACTION])

    unsent(pine_hill, sarah, row.pk)
    unsent(pine_hill, sarah, row.pk)

    written = [one for one in audit_rows if one["action"] == unsent_preview.AUDIT_ACTION]
    assert len(written) == before + 2, "each disclosure is its own row — one read, one row"
    assert written[-1]["entity_type"] == unsent_preview.AUDIT_ENTITY
    assert written[-1]["entity_id"] == str(row.pk)
    assert written[-1]["after"]["channel"] == notification_models.CHANNEL_SMS
    # ⚠ THE CODE IS NEVER IN THE TRAIL. `audit_log` outlives a ten-minute code
    # by years; a copy there would be a second, longer-lived secret.
    assert row.render_context["code"] not in json.dumps(audit_rows, default=str)
    # And the recipient is masked, not repeated (BR-AUD-006).
    assert written[-1]["after"]["recipient"].startswith("•••")


def test_a_closed_gate_writes_no_audit_row(pine_hill, sarah, audit_rows, smtp_adapter):
    row = enrolment_code_row(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        notification_models.OutboundMessage.objects.filter(pk=row.pk).update(
            channel=notification_models.CHANNEL_EMAIL
        )
    post_connect(pine_hill, sarah, "email_smtp", SMTP_FIELDS)
    post_credential(pine_hill, sarah, "email_smtp", {"password": "s3cret-mailbox"})
    before = len([one for one in audit_rows if one["action"] == unsent_preview.AUDIT_ACTION])

    unsent(pine_hill, sarah, row.pk)

    after = len([one for one in audit_rows if one["action"] == unsent_preview.AUDIT_ACTION])
    assert after == before, "nothing was shown, so there is nothing to record"


# ══════════════════════════════════════════════════════════════════════════
# WHO MAY ASK, AND WHOSE ROW
# ══════════════════════════════════════════════════════════════════════════


def test_an_executive_may_read_the_queue_and_may_not_read_a_code(pine_hill, sarah, pine_exec):
    """A4: Settings is View for an Executive. A one-time code is a credential."""
    row = enrolment_code_row(pine_hill, sarah)
    assert queue_list(pine_hill, pine_exec, role="executive").status_code == 200
    refused = unsent(pine_hill, pine_exec, row.pk, role="executive")
    assert refused.status_code in (401, 403), refused.data


def test_another_tenants_row_answers_as_an_unknown_id(pine_hill, sarah, oak_ridge, elena):
    row = enrolment_code_row(pine_hill, sarah)
    refused = unsent(oak_ridge, elena, row.pk)
    unknown = unsent(oak_ridge, elena, "00000000-0000-0000-0000-000000000000")
    assert refused.status_code == unknown.status_code == 404
    strip = lambda body: {k: v for k, v in body.items() if k != "trace_id"}  # noqa: E731
    assert strip(refused.data) == strip(unknown.data)


# ══════════════════════════════════════════════════════════════════════════
# THE SCREEN'S HALF OF THE CONTRACT
# ══════════════════════════════════════════════════════════════════════════


def test_the_queue_list_says_which_channels_may_be_read(pine_hill, sarah, smtp_adapter):
    """The screen offers the control from THIS list rather than guessing from a
    status — a row can be `queued` on a channel that is perfectly connected."""
    enrolment_code_row(pine_hill, sarah)
    open_now = queue_list(pine_hill, sarah).data["vocabulary"]["disclosable_channels"]
    assert notification_models.CHANNEL_SMS in open_now

    post_connect(pine_hill, sarah, "email_smtp", SMTP_FIELDS)
    post_credential(pine_hill, sarah, "email_smtp", {"password": "s3cret-mailbox"})
    after = queue_list(pine_hill, sarah).data["vocabulary"]["disclosable_channels"]
    assert notification_models.CHANNEL_EMAIL not in after
    assert notification_models.CHANNEL_SMS in after
