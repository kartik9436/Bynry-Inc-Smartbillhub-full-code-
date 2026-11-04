# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-023 (EP-INT-06) — delivery and bounce feedback, and the word
#           for a provider that will never send any. Screens: S8 · S142 ·
#           the delivery dashboard (US-NOT-013)
# Rules:    BR-INT-027 (delivery and bounce counts read *not reported* until a
#           feedback path exists; ZERO IS NEVER SUBSTITUTED) · BR-NOT-005 (one
#           seam) · CLAUDE.md hard-won law 1 (a claim that WAS true and is no
#           longer known to be)
# Tests:    this file — TC-6, the wave's second exit test
# Impacts:  apps/integrations/seams/notifications.py (`reports_feedback`) ·
#           apps/notifications/delivery_counts.py (which sentence is true)
# ───────────────────────────────────────────────────────
"""`BR-INT-027` — never a zero, and never a reason that has stopped being true.

The rule has two halves and only the first was ever enforced.

**The first half is structural and it holds:** nothing in this repository writes
`delivered` or `bounced` as a number at all, so a zero cannot be substituted by
accident. `delivery_counts.py`'s own docstring argues it — a delivered count
taken from queued rows *"would not be an approximation, it would be a different
fact"* — and the cases below assert the absence rather than trusting the essay.

**The second half is the one that broke, and nothing could see it.** The reason
served beside the absence said *there is no email provider connected*. That was
a plain fact about the product until 2026-09-04, when wave E shipped the SMTP
adapter — and from that day a utility could connect its own mail server, press
*Save and test*, watch a real message land, and then read on the dashboard that
no email provider was connected. The figure stayed correct; the sentence became
false. That is hard-won law 1 exactly, and no gate in this repository reads a
sentence for whether it is still true.

⚠ **THE MAILBOX CASE IS *FOR EVER*, NOT *NOT YET*, AND THAT IS WHY THE SENTENCE
HAD TO CHANGE RATHER THAN BE DELETED.** A mailbox cannot report a bounce — SMTP
hands a message to a server and a bounce returns hours later as an email to a
person. So the honest reading is neither *nobody is connected* nor a zero: it is
*your own mail server does not report back*, and it will say so for as long as
that connection is a mailbox.
"""

from __future__ import annotations

import pytest

from apps.integrations import models
from apps.integrations.registry import REGISTRY
from apps.integrations.seams import notifications as seam
from apps.notifications import delivery_counts
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar
from tests.test_us_met_helpers import tenant_ctx

SMTP = "email_smtp"
BULK = "sendgrid"  # was `email_bulk` until CR-115-BRC05 named the vendor


def _connection(tenant, provider, *, status=models.STATUS_WORKING, credential=True):
    """A connection the seam will actually count as CONNECTED.

    ⚠ **THE CREDENTIAL IS NOT OPTIONAL SCENERY AND THE FIRST DRAFT LEFT IT
    OUT.** `_connection_for_channel` requires `enabled` + production + a bound
    adapter + **an active credential**, and every one of those is a reason a
    batch could not go. A connection row with no credential is not a connected
    mailbox; it is a card somebody started filling in. Without it this file's
    central case passed by accident — the reason stayed *nothing is connected*
    and that was the correct answer to the question the fixture actually asked.
    """
    row = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=provider,
        label="billing@brazosbend.example",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=status,
        cadence=models.CADENCE_MANUAL,
        config={},
    )
    if credential:
        models.IntegrationCredential.objects.create(
            tenant=tenant,
            connection=row,
            version=1,
            is_active=True,
            payload_enc='{"password": "Ew3!kQ9-lockbox"}',
            masked_hint="••••kbox",
        )
    return row


# ═══════════════════════════════════════════════════════════════════════════
# The capability itself — read off the manifest, never off our own progress
# ═══════════════════════════════════════════════════════════════════════════


def test_a_mailbox_declares_no_feedback_operation_and_a_bulk_service_does():
    """The distinction is DATA in the manifests, so it cannot drift from what
    the provider can actually do (`BR-INT-037`)."""
    smtp = REGISTRY.require(SMTP)
    bulk = REGISTRY.require(BULK)

    assert not any(
        (one.direction, one.initiative) == ("in", "them") for one in smtp.operations
    ), "a mailbox cannot call us back; if this changes, BR-INT-027's sentence changes"
    assert any(
        one.name == "receive_feedback" for one in bulk.operations
    ), "the bulk service is the provider that DOES report — the contrast the rule rests on"


@pytest.mark.django_db
def test_reports_feedback_is_false_for_a_mailbox_and_true_for_a_bulk_service(brazos):
    with tenant_ctx(brazos):
        assert seam.reports_feedback(_connection(brazos, SMTP)) is False
        # a second tenant, so the two rows do not collide on the UNIQUE
        assert seam.reports_feedback(
            models.IntegrationConnection(provider_key=BULK)
        ) is True


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 · the exit test: no code path writes 0 for a connection that cannot report
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_023_tc6_no_zero_is_ever_served_for_delivered_or_bounced(brazos):
    """⚠ **THE ASSERTION IS ABOUT THE WHOLE PAYLOAD, NOT ONE FIELD.** A rule
    that says *never substitute zero* is only as good as the narrowest place
    somebody could put one, so this walks every event's row and every channel
    slot inside it rather than checking the two keys it expects.
    """
    with tenant_ctx(brazos):
        _connection(brazos, SMTP)
        rows = delivery_counts.for_events()

    assert rows, "the rail served nothing at all"
    for key, row in rows.items():
        assert "delivered" not in row, f"{key} carries a delivered figure"
        assert "bounced" not in row, f"{key} carries a bounced figure"
        assert set(row["not_reported"]) == {"delivered", "bounced"}, key
        for name, sentence in row["not_reported"].items():
            assert sentence and not sentence.strip().isdigit(), f"{key}.{name}"
        for channel, slot in row["by_channel"].items():
            assert "delivered" not in slot, f"{key}/{channel}"
            assert "bounced" not in slot, f"{key}/{channel}"


@pytest.mark.django_db
def test_us_int_023_the_reason_says_what_is_true_once_a_mailbox_is_connected(brazos):
    """Hard-won law 1, caught at the one moment it is catchable.

    With nothing connected the original sentence is right. The moment a utility
    connects its own mail server it becomes false — and the figure is unchanged,
    so nothing else in the product can tell.
    """
    with tenant_ctx(brazos):
        before = delivery_counts.for_events()
        any_before = next(iter(before.values()))["not_reported"]
        assert "no email provider connected" in any_before["bounced"]

        _connection(brazos, SMTP)

        after = delivery_counts.for_events()
        any_after = next(iter(after.values()))["not_reported"]
        assert "no email provider connected" not in any_after["bounced"], (
            "the dashboard still says nothing is connected while the utility's "
            "own mail server is connected and sending"
        )
        assert "your own mail server" in any_after["bounced"].lower()
        # …and it is still NOT a number, which is the half that must not move
        assert not any_after["bounced"].strip().isdigit()
        assert "delivered" not in after[next(iter(after))]


@pytest.mark.django_db
def test_us_int_023_a_connection_that_is_off_does_not_change_the_reason(brazos):
    """A disconnected mailbox is *nothing connected* again, not a mailbox that
    has gone quiet — `_connection_for_channel` already requires `enabled` and an
    active credential, and this pins that the sentence follows it."""
    with tenant_ctx(brazos):
        connection = _connection(brazos, SMTP)   # credential and all
        connection.enabled = False
        connection.save(update_fields=["enabled"])
        rows = delivery_counts.for_events()
    reason = next(iter(rows.values()))["not_reported"]["bounced"]
    assert "no email provider connected" in reason


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-023@93356954 (EP-INT-06 + BR-INT-027 verbatim from 02-business-rules.md)
# generated: 2026-09-05 by the CR-069 wave F build lane
# checklist: A✔ B✔ C✔ D✔(delivery_counts.for_events is what US-NOT-013 serves) E=F3's(the dashboard's own copy) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_023_not_reported.py
# exceptions: US-INT-023's OTHER half — the inbound feedback door (POST /integrations/webhooks/{key}) — is NOT built by this lane and the execution plan's wave F stamp says why; these cases cover BR-INT-027 only
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
