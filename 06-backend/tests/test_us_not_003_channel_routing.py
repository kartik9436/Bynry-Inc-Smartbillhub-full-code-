# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-003 (channel routing + the provider adapter seam — print/PDF
#           live v1 · email DEFERRED → W6 · SMS DEFERRED → v1.1)  Screens: S8
# Rules:    BR-NOT-005 (adapters behind ONE seam; the dispatcher sends at the
#           provider's pace) · BR-BIL-016 (rows for every channel are written
#           from day one; only the SEND defers) · BR-PAY-017 (email + SMS ride
#           the queue when their channels land) · BR-NOT-010 (v1 channels are
#           print/email/SMS — door-hanger is not one until v2) · BR-BIL-036
#           (print is the floor)
# ───────────────────────────────────────────────────────
"""The three states a channel can be in — and the zero provider calls in two.

US-NOT-003's whole claim is a NEGATIVE one: email rows are written from day one
and **nothing is sent** until W6, SMS until v1.1. A negative claim is exactly
what a docstring cannot be trusted for (hard-won law 1), so every case here
asserts on the adapter's call log rather than on the dispatcher's own account of
itself.

The three states, kept apart because a dispatch home counts them apart:
  DEFERRED           the platform has not shipped the channel (email → W6)
  PROVIDER MISSING   the channel is live and this tenant has no connection
  READY              hand it over

Collapsing the first two would tell a utility at W5 that its email is
misconfigured, when the truth is that the platform has not built it — and only
one of those is theirs to fix.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import dispatch_config, dispatcher, models, provider_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_cr049_t2_dispatch_freeze import provider_connected  # noqa: F401 — shared fixture

pytestmark = pytest.mark.django_db

INSIDE_WINDOW = datetime(2026, 8, 9, 15, 0, tzinfo=dt_timezone.utc)


def queue_row(tenant, *, channel, **overrides):
    values = dict(
        tenant_id=tenant.id,
        source_type="invoice",
        source_id=uuid.uuid4(),
        channel=channel,
        template_code="bill_residential",
        template_id=uuid.uuid4(),
        template_version=3,
        recipient_address="somebody@brazosbend.example",
        status=models.STATUS_QUEUED,
    )
    values.update(overrides)
    return models.OutboundMessage.objects.create(**values)


class RecordingAdapter:
    def __init__(self):
        self.calls = []

    def __call__(self, channel, messages):
        self.calls.append((channel, messages))
        return {m["id"]: {"status": "sent", "provider_reference": "ref"} for m in messages}


# ── TC-2 / TC-3 · the deferred channels ─────────────────────────────────────
def test_us_not_003_tc2__email_rows_rest_queued_pre_w6_with_the_wave_named(brazos):
    """US-NOT-003 TC-2: *"Email rows pre-W6 → Persist `queued` with the
    deferred-channel marker; NO mailbox/ESP call ever attempted; rows never
    lost."*

    The route names the WAVE (`W6`) and not merely "off", which is what lets
    US-NOT-004 TC-2 badge the channel honestly instead of implying the tenant
    switched something off.
    """
    with tenant_ctx(brazos):
        settings = dispatch_config.dispatch_settings()
        assert settings.email_dispatch_active is False  # ships off (law 3)

        route = provider_seam.channel_route(
            models.CHANNEL_EMAIL, active=settings.channel_is_active(models.CHANNEL_EMAIL)
        )
        assert route.dispatchable is False
        assert route.problem["code"] == provider_seam.ROUTE_CHANNEL_DEFERRED
        assert route.problem["deferred_until"] == "W6"


def test_us_not_003_tc3__sms_rows_rest_queued_pre_v1_1(brazos):
    """US-NOT-003 TC-3: *"SMS rows pre-v1.1 → Persist `queued` with the v1.1
    marker; no Twilio call; opt-in flag carried for activation day."*"""
    with tenant_ctx(brazos):
        settings = dispatch_config.dispatch_settings()
        route = provider_seam.channel_route(
            models.CHANNEL_SMS, active=settings.channel_is_active(models.CHANNEL_SMS)
        )
        assert route.dispatchable is False
        # `CR-198-BRC10` (2026-10-29): the v1.1 deferral is SUPERSEDED — texts ship
        # OFF per tenant, so the row still rests `queued`, now as switched off.
        assert route.problem["deferred_until"] is None


def test_us_not_003_tc3b__a_deferred_channel_produces_zero_provider_calls(brazos, monkeypatch):
    """The assertion that matters, made where it can actually fail.

    ⚠ BOTH doubles are needed and the reason is the whole point of the case.
    An earlier draft stubbed only the adapter, and it passed with the deferral
    DELETED — because the missing template store held every row before routing
    was ever reached, so the case was measuring the wrong guard. That is
    hard-won law 7 catching a test rather than a feature: a green assertion
    proves nothing until you have watched it go red for the reason you think it
    is there.

    With the renderer stubbed too, the deferral is the only thing standing
    between these rows and the provider.

    PROVED RED by neutering the `if not active:` branch in `channel_route`: the
    cycle then handed the email and SMS rows over and this failed with
    `AssertionError: assert [('email', ({...},)), ('sms', ({...},))] == []`.
    """
    from apps.integrations import services as integrations_services
    from apps.notifications import rendering

    adapter = RecordingAdapter()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    monkeypatch.setattr(
        rendering,
        "render_for_dispatch",
        lambda row: rendering.RenderedArtifact(
            template_code="receipt",
            template_version=1,
            language=None,
            channel=row.channel,
            body="body",
        ),
    )

    with tenant_ctx(brazos):
        queue_row(brazos, channel=models.CHANNEL_EMAIL)
        queue_row(brazos, channel=models.CHANNEL_SMS)
        result = dispatcher.dispatch_cycle(
            now=INSIDE_WINDOW, channels=(models.CHANNEL_EMAIL, models.CHANNEL_SMS)
        )

        assert adapter.calls == []
        assert result.dispatched is False
        assert {row.status for row in models.OutboundMessage.objects.all()} == {
            models.STATUS_QUEUED
        }
        assert {row.attempts for row in models.OutboundMessage.objects.all()} == {0}


# ── TC-5 · active channel, no provider ──────────────────────────────────────
def test_us_not_003_tc5__an_active_channel_with_no_provider_holds_its_rows(brazos, dana):
    """US-NOT-003 TC-5: *"Email channel activated but tenant has no connected
    mailbox/ESP → Rows stay `queued`; config-missing surfaced on the dispatch
    home — no crash, no loss, no fallback shared sender."*

    ⚠ **AMENDED 2026-09-30 — FOR EMAIL THE ANSWER IS NOW EXACTLY TC-5'S OWN
    WORDS.** This read that the reason was stronger than *"the tenant has not
    connected one"*, because `apps/integrations` published nothing and the route
    reported `provider_status_unknown`. `d471e8680` (2026-09-04, `CR-069` wave
    E) made a mailbox something a utility CAN connect (Custom SMTP, then
    Microsoft, Google, SendGrid, Postmark), and this case went red that day. For
    email the gap is now the tenant's, so `provider_not_connected` is right —
    and it is still not print, which no utility can connect and which stays
    `provider_status_unknown` (`DEF-NOT-8451`, tc1 below). The two codes exist
    so a screen never confuses them, and this pair of cases now proves both.
    """
    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(actor=dana, email_dispatch_active=True)
        route = provider_seam.channel_route(models.CHANNEL_EMAIL, active=True)

        assert route.dispatchable is False
        assert route.problem["code"] == provider_seam.ROUTE_PROVIDER_NOT_CONNECTED
        assert "shared sender" in route.problem["detail"]


def test_us_not_003_tc5b__the_provider_status_readout_answers_none_not_not_connected(brazos):
    """US-NOT-004 §5's readout. `None` means integrations cannot answer, which
    a screen must never render as "Not connected" — the same rule
    `apps/billing/release.py` states about mandate coverage: *"'0 of 1,122 hold
    an address' and 'we could not count' must never render the same."*

    ⚠ **AMENDED 2026-09-30.** This asserted that EMAIL answers `None`. Since
    `d471e8680` (2026-09-04) integrations CAN answer for email — a tenant with
    no mailbox is a real *"Not connected"*, and the readout says so — so the
    email half moved and went red that day. The rule itself is unchanged and is
    still asserted where `None` is still the answer: a channel integrations has
    no category for (`in_app`, delivered by this platform) must never be
    rendered as "Not connected".
    """
    with tenant_ctx(brazos):
        email = provider_seam.provider_status(models.CHANNEL_EMAIL)
        assert email is not None
        assert email["connected"] is False
        assert email["connectable"] is True
        assert provider_seam.provider_status(models.CHANNEL_IN_APP) is None


# ── TC-1 · RE-SCOPED BY PO RULING 2026-08-15 ────────────────────────────────
def test_us_not_003_tc1__print_is_the_one_channel_v1_activates(brazos):
    """US-NOT-003 TC-1 — **RE-SCOPED, not deleted. Read this before "fixing" it.**

    ⚠ **SUPERSESSION (Product Owner ruling, 2026-08-15).** TC-1 as written in
    `EP-NOT-01-outbound-queue.md` reads: *"Print batch (142 rows) dispatched v1
    → PDF batch rendered from pinned template versions; print-vendor seam
    invoked; rows → sent → delivered."* **That outcome is unsatisfiable in this
    release BY DECISION, not by omission.** The PO ruled that ISSUING a bill does
    not mean the customer RECEIVES one: delivery is OUT of this release, and no
    provider adapter exists or is coming on any channel, print included. The
    chain ends at a RENDERED DOCUMENT.

    So a dispatch cycle that reports the adapter absent is now **CORRECT
    OUTPUT** and this case asserts exactly that, keeping its name so the story's
    test mapping still resolves (G10 reads the TC id out of it):

      * the batch reaches the boundary — the cycle runs, the tenant's print
        channel is ACTIVE (BR-BIL-036's floor: print is never switchable off,
        because that switch would stop bills reaching customers who have no
        other channel);
      * and it reports the adapter's absence **BY NAME** —
        `apps.integrations.services.dispatch_outbound_batch`, the one seam
        US-NOT-003 §5 puts every provider behind (TD-8, B7's no-hardcoded-
        provider rule);
      * nothing is sent, nothing is lost, and every row keeps its place.

    What must NOT be done to make this "pass": build or fake an adapter. The two
    parked seams in `10-scripts/gates/seam_known_gaps.txt` are ACCEPTED under
    this ruling, not owed.

    The half of TC-1 that IS satisfied today and was not before this lane: the
    rows are *"rendered from pinned template versions"* — the pin is resolved at
    queue-write and `rendering.render_for_dispatch` loads its body (US-NOT-006).

    ⚠ **RED FROM 2026-09-04 (`d471e8680`) TO 2026-09-30, AND IT WAS RIGHT.**
    Publishing the generic hand-off seam made print report
    `provider_not_connected` — telling a utility to connect a print vendor that
    no utility can connect (the card answers *Cannot be connected yet.*). That
    is `DEF-NOT-8451`, fixed 2026-09-30: integrations now says whether a
    channel's kind can be connected at all, and print is the platform's gap
    again. Nothing below was changed to make it pass.
    """
    with tenant_ctx(brazos):
        settings = dispatch_config.dispatch_settings()
        assert settings.channel_is_active(models.CHANNEL_PRINT) is True

        route = provider_seam.channel_route(models.CHANNEL_PRINT, active=True)
        assert route.dispatchable is False
        assert route.problem["code"] == provider_seam.ROUTE_PROVIDER_STATUS_UNKNOWN

        for _index in range(3):
            queue_row(brazos, channel=models.CHANNEL_PRINT)
        result = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_PRINT,))

    # The batch reached the boundary and stopped there, by ruling.
    assert result.dispatched is False
    assert result.sent == 0
    absence = [
        problem
        for problem in result.problems
        if problem["code"] == provider_seam.ROUTE_PROVIDER_STATUS_UNKNOWN
    ]
    assert absence, "the cycle must NAME the missing adapter, never fall silent"
    # By name — the seam, not a vague "unavailable".
    assert (
        f"apps.{provider_seam.PROVIDER_MODULE}.services.{provider_seam.DISPATCH_ADAPTER}"
        in absence[0]["detail"]
    )
    # Nothing lost: every row keeps its place in the queue.
    assert (
        models.OutboundMessage.objects.filter(
            tenant_id=brazos.id, channel=models.CHANNEL_PRINT, status=models.STATUS_QUEUED
        ).count()
        == 3
    )


def test_us_not_003_tc4__once_a_provider_exists_the_backlog_drains_in_batches(
    brazos, dana, monkeypatch, provider_connected
):
    """US-NOT-003 TC-4: *"W6 email activation → Dispatcher drains deferred email
    rows IN TENANT-CONFIG BATCHES (pacing rule holds on the backlog)."*

    Activation is a flag plus an adapter, and neither changes the pacing: the
    backlog goes out 500 at a time like everything else.

    ⚠ `provider_connected` ADDED 2026-09-30: since `d471e8680` (2026-09-04)
    "a provider exists" means a tenant has CONNECTED one, not merely that an
    adapter function is importable; red from that commit until this fixture.
    """
    from apps.integrations import services as integrations_services
    from apps.notifications import rendering

    adapter = RecordingAdapter()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    monkeypatch.setattr(
        rendering,
        "render_for_dispatch",
        lambda row: rendering.RenderedArtifact(
            template_code="receipt",
            template_version=1,
            language=None,
            channel=row.channel,
            body="body",
        ),
    )

    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(
            actor=dana, email_dispatch_active=True, dispatch_batch_size=2
        )
        for _index in range(5):
            queue_row(brazos, channel=models.CHANNEL_EMAIL)

        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_EMAIL,))
        assert [len(messages) for _channel, messages in adapter.calls] == [2]


# ── TC-6 · the negative that has no writer ──────────────────────────────────
def test_us_not_003_tc6__there_is_no_channel_outside_the_v1_vocabulary(brazos):
    """US-NOT-003 §4 / BR-NOT-010: the channels are pdf_print · email · sms, and
    *"door-hanger is NOT a channel until v2"*. A cycle asked for one is refused
    rather than quietly doing nothing."""
    with tenant_ctx(brazos):
        with pytest.raises(ValueError, match="door_hanger"):
            dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=("door_hanger",))


def test_us_not_003_the_adapter_is_never_called_per_message(
    brazos, dana, monkeypatch, provider_connected
):
    """T5-24 step 2: pacing is about HAND-OFFS. Five messages in one call and
    five calls of one message are the same number of messages and opposite
    compliance with BR-NOT-005, so the count that matters is the call count.

    ⚠ `provider_connected` ADDED 2026-09-30 — red from `d471e8680` (2026-09-04)
    for the reason tc4 gives."""
    from apps.integrations import services as integrations_services
    from apps.notifications import rendering

    adapter = RecordingAdapter()
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    monkeypatch.setattr(
        rendering,
        "render_for_dispatch",
        lambda row: rendering.RenderedArtifact(
            template_code="receipt",
            template_version=1,
            language=None,
            channel=row.channel,
            body="body",
        ),
    )

    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(actor=dana, email_dispatch_active=True)
        for _index in range(5):
            queue_row(brazos, channel=models.CHANNEL_EMAIL)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_EMAIL,))

    assert len(adapter.calls) == 1
    assert len(adapter.calls[0][1]) == 5


def test_us_not_003_handing_a_batch_over_with_no_adapter_raises_rather_than_answering_empty(
    monkeypatch,
):
    """An empty result and "the provider sent nothing" are the same value and
    opposite facts. `dispatch_batch` refuses rather than fabricating the one a
    delivery system must never claim.

    ⚠ AMENDED 2026-09-30: the adapter has been published since `d471e8680`
    (2026-09-04), so "no adapter" no longer describes this deployment and the
    case went red that day. The refusal is still the property, so the adapter
    is REMOVED for this one case and the same refusal is asserted.
    """
    from apps.integrations import services as integrations_services

    monkeypatch.delattr(integrations_services, provider_seam.DISPATCH_ADAPTER, raising=False)
    with pytest.raises(RuntimeError, match="not published"):
        provider_seam.dispatch_batch(models.CHANNEL_EMAIL, ())
