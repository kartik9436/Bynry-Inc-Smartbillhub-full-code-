# ── Trace ──────────────────────────────────────────────
# Change:   CR-084 — the customer portal becomes a notification channel. PO
#           2026-09-07, pointing at the greyed-out row on Settings →
#           Notifications → Bill ready: *"can you swithc on this now - Customer
#           portal"*.   Screens: S8 · CWP-027 · CWP-031
# Defect:   DEF-NOT-4532 — in-app, the platform's only working channel, has
#           reported NOT DISPATCHABLE on every tenant since `CR-069` wave E
#           (2026-09-04, `d471e868`) because it was asked for an integrations
#           connection that by design does not exist.
# Rules:    BR-NOT-1031 (the portal is a delivery channel; the PLATFORM is its
#           provider) · BR-NOT-010 AS AMENDED · BR-NOT-013 (no lane is to build
#           or fake an adapter for the OTHER channels to turn a test green) ·
#           BR-BIL-036 (print is the floor — the portal can only ever ADD a
#           route) · BR-CWP-083 / OQ-1399 (the portal is a convenience copy)
# ───────────────────────────────────────────────────────
"""THE SWITCH, AND WHAT IS ACTUALLY BEHIND IT.

The sentence this CR deletes warned about a specific failure — *"A 'Portal'
delivery flag would be a switch with nothing behind it"* — so the tests worth
reading first are the ones that would go red if that is what we shipped:

  * `test_cr084__the_portal_channel_is_offered_on_bill_ready` — the toggle
    exists at all, on the event the Product Owner opened;
  * `test_cr084__a_portal_row_with_no_kept_document_is_refused_by_name` — the
    adapter will not report a publication of nothing;
  * `test_cr084__print_is_still_the_floor_when_the_portal_is_switched_off` — the
    switch cannot take paper off a bill, in either position.

⚠ **AND THE HOLD-EXPIRY TEST CLAUDE.md ASKS FOR, WRITTEN IN THE SAME COMMIT AS
THE RELEASE.** *"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD
EXPIRES."* The old refusal had no such test, which is exactly why it survived
`CR-068` shipping seventy-five portal screens.
`test_cr084__no_refusal_sentence_still_claims_this_product_has_no_portal` is
that test, pointed at the sentence rather than at the feature: it fails if any
`UNAVAILABLE_CHANNELS` entry ever says the portal does not exist again.
"""

from __future__ import annotations

import pytest

from apps.notifications import (
    dispatch_config,
    models,
    portal_delivery,
    provider_seam,
    rule_catalog,
    rule_service,
    services,
)

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE CHANNEL EXISTS, AND IT IS OFFERED WHERE THE PO POINTED
# ══════════════════════════════════════════════════════════════════════════
def test_cr084__the_portal_is_the_fifth_channel() -> None:
    assert models.CHANNEL_PORTAL == "portal"
    assert models.CHANNEL_PORTAL in models.CHANNELS
    assert len(models.CHANNELS) == 5


def test_cr084__the_portal_channel_is_offered_on_bill_ready() -> None:
    """The row the Product Owner was looking at, asserted by NAME.

    Both halves matter and they are two different facts: the channel is now a
    TOGGLE, and it is no longer a REFUSAL. A change that added the first and
    left the second would draw the switch twice, once enabled and once greyed
    out with a sentence under it.
    """
    event = rule_catalog.event("bill_ready")
    assert models.CHANNEL_PORTAL in event.channels
    assert models.CHANNEL_PORTAL not in event.unavailable_channels
    wire = event.as_wire() if hasattr(event, "as_wire") else None
    if wire is not None:
        drawn = {row["channel"] for row in wire["unavailable_channels"]}
        assert models.CHANNEL_PORTAL not in drawn


def test_cr084__no_refusal_sentence_still_claims_this_product_has_no_portal() -> None:
    """THE HOLD-EXPIRY TEST — pointed at the sentence, not at the feature.

    The refusal it guards survived `CR-068` shipping the whole portal because
    nothing anywhere connected *"there is no customer portal in this product"*
    to the seventy-five screens that had arrived. This is what would have fired.
    """
    for channel, reason in rule_catalog.UNAVAILABLE_CHANNELS.items():
        assert "no customer portal" not in reason.lower(), (
            f"{channel!r} still refuses on the grounds that this product has no customer "
            "portal. It has had one since CR-068."
        )
    assert models.CHANNEL_PORTAL not in rule_catalog.UNAVAILABLE_CHANNELS


def test_cr084__the_portal_ships_switched_on_and_carries_no_template() -> None:
    """*"can you swithc on this now"* — so the seeded row is ON, not merely drawn.

    And it carries no template class deliberately: email and SMS need wording,
    a published document does not, and `CWP-031` names each one from served
    facts in the reader's own language.
    """
    event = rule_catalog.event("bill_ready")
    assert event.template_classes.get(models.CHANNEL_PORTAL) is None
    assert rule_service._seeded_channel_enabled(event, models.CHANNEL_PORTAL) is True
    # …and the events that do NOT offer it are untouched, so nothing was widened
    # by accident: three staff events offer `in_app` with no template class
    # because they have nothing to render yet, and they must stay OFF.
    for other in rule_catalog.EVENTS:
        if models.CHANNEL_PORTAL in other.channels:
            continue
        for channel in other.channels:
            if channel in other.template_classes:
                continue
            assert rule_service._seeded_channel_enabled(other, channel) is False, (
                f"{other.key}/{channel} has no template class and would now ship ON — the "
                "portal default was widened past the channel CR-084 ruled on."
            )


# ══════════════════════════════════════════════════════════════════════════
# 2 · IT ROUTES — AND SO DOES THE CHANNEL THAT HAD SILENTLY STOPPED
# ══════════════════════════════════════════════════════════════════════════
def test_cr084__both_platform_channels_are_dispatchable(brazos, dana) -> None:
    """`DEF-NOT-4532`. A channel whose provider is this application is connected
    by definition, and asking integrations about it is what went wrong.

    In-app is asserted here beside the portal on purpose: it is the row that was
    red for three days, and a fix for the new channel that left the old one
    broken would be half a fix.
    """
    with tenant_ctx(brazos):
        settings = dispatch_config.dispatch_settings()
        assert settings.channel_is_active(models.CHANNEL_PORTAL) is True
        portal_route = provider_seam.channel_route(models.CHANNEL_PORTAL, active=True)
        in_app_route = provider_seam.channel_route(models.CHANNEL_IN_APP, active=True)

    assert portal_route.dispatchable is True, portal_route.problem
    assert in_app_route.dispatchable is True, in_app_route.problem


def test_cr084__the_other_three_channels_are_unchanged(brazos, dana) -> None:
    """BR-NOT-013, verbatim: *"no lane is to build or fake an adapter to turn a
    test green."* The portal must not have loosened anybody else's verdict, and
    the platform-adapter short-circuit is the obvious way it could have."""
    with tenant_ctx(brazos):
        print_route = provider_seam.channel_route(models.CHANNEL_PRINT, active=True)
        email_route = provider_seam.channel_route(models.CHANNEL_EMAIL, active=False)
        sms_route = provider_seam.channel_route(models.CHANNEL_SMS, active=False)

    assert print_route.dispatchable is False
    assert email_route.dispatchable is False
    assert email_route.problem["deferred_until"] == "W6"
    assert sms_route.dispatchable is False
    # `CR-198-BRC10` (2026-10-29): SMS is no longer deferred to v1.1 — a
    # switched-off text channel is simply off for this tenant, still not dispatchable.
    assert sms_route.problem["deferred_until"] is None


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE ADAPTER REFUSES TO REPORT A PUBLICATION OF NOTHING
# ══════════════════════════════════════════════════════════════════════════
def test_cr084__a_portal_row_with_no_kept_document_is_refused_by_name(brazos, dana) -> None:
    """The whole difference between this and a flag with nothing behind it.

    No document has been stored for this made-up source, so there is nothing for
    the customer to open, and the adapter says so rather than marking the row
    sent.
    """
    import uuid

    with tenant_ctx(brazos):
        answers = portal_delivery.deliver_batch(
            (
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "channel": models.CHANNEL_PORTAL,
                    "address": "AC-000141",
                    "source_type": "invoice",
                    "source_id": str(uuid.uuid4()),
                    "account_id": str(uuid.uuid4()),
                },
            )
        )
    answer = answers["11111111-1111-1111-1111-111111111111"]
    assert answer["status"] == models.STATUS_FAILED
    assert answer["response"]["reason"] == portal_delivery.REASON_NO_DOCUMENT
    assert answer["retryable"] is False


def test_cr084__a_portal_row_with_no_account_is_refused_by_name(brazos, dana) -> None:
    """A portal document is shown to whoever holds the account it belongs to, so
    a row naming no account has nobody to be published to."""
    with tenant_ctx(brazos):
        answers = portal_delivery.deliver_batch(
            (
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "channel": models.CHANNEL_PORTAL,
                    "source_type": "invoice",
                    "source_id": "33333333-3333-3333-3333-333333333333",
                    "account_id": None,
                },
            )
        )
    answer = answers["22222222-2222-2222-2222-222222222222"]
    assert answer["status"] == models.STATUS_FAILED
    assert answer["response"]["reason"] == portal_delivery.REASON_NO_ACCOUNT


def test_cr084__the_adapter_never_reports_delivered(brazos, dana) -> None:
    """`OQ-1399` closed with the portal as a CONVENIENCE COPY, so this channel in
    particular may never claim a customer read anything (`BR-CWP-083`)."""
    import inspect

    source = inspect.getsource(portal_delivery)
    assert "STATUS_DELIVERED" not in source
    assert models.STATUS_SENT == "sent"


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE PLATFORM OFFERS IT; THE RULE ONLY EVER REMOVES; PRINT IS THE FLOOR
# ══════════════════════════════════════════════════════════════════════════
def test_cr084__the_platform_offers_the_portal_even_when_the_caller_does_not(brazos, dana) -> None:
    """Billing asks for what the CUSTOMER elected, and the portal is not an
    election — it needs no address the customer had to give us and costs
    nothing. So the platform offers it on the events whose catalogue lists it,
    and the tenant's switch removes it."""
    with tenant_ctx(brazos):
        rule_service.seed_rules()
        decision = services.channel_decision("invoice", (), event_key="bill_ready")

    assert models.CHANNEL_PORTAL in decision.channels
    # …and it is in the no-rule baseline too, so a reader comparing the two
    # lists cannot conclude the RULE added it.
    assert models.CHANNEL_PORTAL in decision.without_rule


def test_cr084__print_is_still_the_floor_when_the_portal_is_switched_off(brazos, dana) -> None:
    """BR-BIL-036 / BR-NOT-024 — the switch adds a route and can never take
    paper away, in either position. The bill goes out on paper whatever this
    utility does on the settings screen."""
    with tenant_ctx(brazos):
        rule_service.seed_rules()
        on = services.channel_decision("invoice", (), event_key="bill_ready")
        rule_service.update_rule(
            event_key="bill_ready",
            actor=dana,
            channels={models.CHANNEL_PORTAL: {"enabled": False}},
        )
        off = services.channel_decision("invoice", (), event_key="bill_ready")

    assert models.CHANNEL_PRINT in on.channels
    assert models.CHANNEL_PORTAL in on.channels
    # The switch really did something…
    assert models.CHANNEL_PORTAL not in off.channels
    assert models.CHANNEL_PORTAL in off.suppressed
    # …and paper is untouched by it, which is the assertion this test is for.
    assert models.CHANNEL_PRINT in off.channels


def test_cr084__a_portal_row_is_exempt_from_quiet_hours(brazos, dana) -> None:
    """BR-NOT-009's harm is *"a utility texting late-payment reminders at
    23:00"* — a message that wakes somebody. Publishing to a portal wakes
    nobody, which is print's own reason for being exempt from the first day."""
    from apps.notifications import dispatcher

    assert models.CHANNEL_PORTAL in dispatcher.QUIET_HOURS_EXEMPT_CHANNELS
    assert models.CHANNEL_EMAIL not in dispatcher.QUIET_HOURS_EXEMPT_CHANNELS
    assert models.CHANNEL_SMS not in dispatcher.QUIET_HOURS_EXEMPT_CHANNELS


def test_cr084__nothing_is_frozen_on_the_portal_channel() -> None:
    """The portal SERVES the artefact another route already froze
    (`BR-CWP-045`), and `stored_documents` holds one artefact per
    (source, channel, content type) — a portal freeze would be a second copy of
    one document. Asserted rather than left to the absence of code."""
    from apps.notifications import frozen_documents

    assert models.CHANNEL_PORTAL not in frozen_documents.FREEZE_CHANNELS


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE ADDRESS IS A HUMAN REFERENCE, NEVER A DATABASE ID
# ══════════════════════════════════════════════════════════════════════════
def test_cr084__the_portal_address_is_the_account_number(brazos, dana) -> None:
    """B14 rule 31 — no database id is ever a visible value, and
    `recipient_address` is drawn on the staff dispatch home."""
    import uuid

    from apps.customers import models as customer_models
    from apps.customers import selectors as customer_selectors

    with tenant_ctx(brazos):
        # ⚠ AN ACCOUNT IS MADE HERE RATHER THAN LOOKED FOR. The first draft read
        # `Account.objects.exclude(account_no="").first()` and SKIPPED when the
        # fixture had none — a skip that reads exactly like a pass in the run
        # summary, which is hard-won law 7's *incapable of failing* shape. The
        # assertion below is the whole point of this test, so it always runs.
        account = customer_models.Account.objects.exclude(account_no="").first()
        if account is None:
            status = customer_models.AccountStatus.objects.filter(
                tenant=brazos, code="active"
            ).first()
            account_type = customer_models.AccountType.objects.filter(code="residential").first()
            assert status is not None and account_type is not None, (
                "this tenant is not provisioned — the seeded account statuses and the "
                "platform account types are both missing, so nothing here is measurable."
            )
            # `ck_accounts_anchored` requires a unit or a premises, and this
            # test is about neither — the portal branch reads `account_no` and
            # nothing else — so the anchor is a bare uuid rather than a whole
            # premises tree. It is the deferred-FK shape `premises_id` already
            # has (`BR-CUS-1010`), and no read here follows it.
            account = customer_models.Account.objects.create(
                tenant=brazos,
                # `kind="master"` and not `"regular"`, for the same reason:
                # `ck_accounts_regular_has_unit` requires an occupying account
                # to name a unit, and `BR-CUS-1010`'s owner account is exactly
                # the shape that names a premises and no unit.
                kind="master",
                premises_id=uuid.uuid4(),
                account_no="AC-CR083-0001",
                status=status,
                account_type=account_type,
            )
        answer = customer_selectors.delivery_recipients_for_account(
            account.pk, channels=(models.CHANNEL_PORTAL,)
        )[models.CHANNEL_PORTAL]

    assert answer.get("unavailable_reason") is None
    assert answer["address"] == account.account_no
    assert str(account.pk) not in str(answer["address"])


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-084 (12-governance/11-change-requests.md → CR-084 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-010 as amended + BR-NOT-1031 · apps/notifications/in_app.py and tests/test_cr_009_in_app_channel.py, the precedent this follows · apps/portal/selectors.py `documents` · apps/notifications/correspondence_reads.py)
# generated: 2026-09-07 by story-coder (CR-084 portal channel lane)
# checklist: A✔ B✔ C✔ D=n/a E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest 06-backend/tests/test_cr084_portal_channel.py
#   RED PROVED FIRST, through pytest and never through `python3 <file>`:
#     1 · at the pinned tip, `test_cr084__the_portal_is_the_fifth_channel` failed on `len(models.CHANNELS) == 4`.
#     2 · at the pinned tip, `test_cr084__the_portal_channel_is_offered_on_bill_ready` failed — `portal` was in
#         `unavailable_channels` and not in `channels`.
#     3 · at the pinned tip, `test_cr084__no_refusal_sentence_still_claims_this_product_has_no_portal` failed
#         quoting the refusal verbatim — THE HOLD-EXPIRY TEST, red on the very sentence the PO found.
#     4 · at the pinned tip, `test_cr084__both_platform_channels_are_dispatchable` failed on the IN-APP row
#         (`provider_status_unknown`), which is `DEF-NOT-4532` and was red before this lane started —
#         dated with `git log -S "connected = bool(status.get" -- provider_seam.py` → `d471e868`, 2026-09-04.
#     5 · with the document-store check removed from the adapter, `…refused_by_name` failed: the row came back `sent`.
# exceptions: (1) `test_cr084__print_is_still_the_floor_when_the_portal_is_switched_off` drives the REAL write (`rule_service.update_rule`) rather than asserting the floor over an unchanged rule — a floor test that never moved the switch is a check that cannot fail, and it asserts the switch moved (`suppressed`) before it asserts what survived it. (2) `test_cr084__the_adapter_never_reports_delivered` reads the module's SOURCE. That is unusual and deliberate: the rule is about a status this adapter must never be able to write, and a behavioural test could only ever cover the paths it happened to exercise. (3) NO END-TO-END DISPATCH TEST HERE — `tests/test_cr_009_in_app_channel.py` already drains the real dispatcher end to end and this channel travels the identical path; a second copy of that fixture would be a second thing to keep true.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
