# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-023 (the outbound delivery queue — one record per bill per
#           channel at issue) × US-NOT-017 (SET-12 / SET-12D, the rule)
#           CR-048 wave B, tasks B1 (billing half) + B2
#           Screens: S31 step 6 · S30 · S8 (SET-12 / SET-12D)
# Rules:    BR-BIL-016 (issue writes one delivery record per bill per channel;
#           mass sends are NEVER synchronous) · BR-BIL-036 (PRINT is the
#           primary channel and the FLOOR — a rule may never remove it) ·
#           BR-BIL-055 (a refusable bill is ONE named break, never a dead
#           batch) · BR-BIL-004 (issued bills are immutable; a correction is a
#           NEW bill carrying `corrects_invoice_id` — PO 2026-08-12, OQ-120) ·
#           BR-NOT-017 (ONE HOME for every notification rule) · BR-NOT-005
#           (queue only; nothing here sends) · BR-NOT-013 (no provider adapter
#           on any channel) · BR-TEN-043 (no wall clock; dates are parameters) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 6 (idempotency)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-048 wave B: the bill run fires its EVENT, so the settings screen works.

Wave A built the join — `services.queue_document(..., event_key=...)` reads the
utility's rule and intersects it with what the caller asked for. **Nothing fed
it.** Billing passed `source_type="invoice"` and no event, so `event_key` was
`None` on every bill in the product and switching *Bill ready — email* off on
SET-12 still queued the email. This file is that gap closed from billing's side,
and then held shut.

WHY A SOURCE TYPE COULD NOT SIMPLY BE MAPPED TO AN EVENT
--------------------------------------------------------
`invoice` is `bill_ready` **or** `bill_corrected` — two rows on SET-12 with two
sets of switches. `test_cr048_b2__a_corrected_bill_fires_bill_corrected` is the
case that proves billing tells them apart, and it tells them apart from a fact
it ALREADY HOLDS and did not invent for this change:
`invoices.corrects_invoice_id`, stamped on the REBILL by
`corrections.execute_restatement` before it calls `issue.issue_invoice` (PO
2026-08-12, closing OQ-120). No flag, no new parameter on `issue_invoice`, and
therefore no caller that can pass the wrong one.

FIVE THINGS THESE CASES DEFEND, one per requirement of the task:

  1. **A utility that switches *Bill ready — email* off gets no email row, and
     the bill still issues.** The headline, and the case that was RED.
  2. **The print floor still wins** (BR-BIL-036) — including when the utility
     switches the whole event off. A settings toggle does not cancel paper.
  3. **The rule read is two SELECTs and NO write**, per bill, so a
     five-hundred-bill run is not slowed to a crawl and a bill run never
     materialises rule rows as a side effect.
  4. **A refusable bill is one named break** (BR-BIL-055) — whatever the rule
     join raises is translated by the seam, so the other bills still issue.
  5. **A tenant whose rules have never been read issues exactly as today.**

NOTHING HERE SENDS. Every row rests `queued` (BR-NOT-013), and
`test_cr048_b2__nothing_was_sent` asserts it as a VALUE rather than trusting a
docstring (hard-won law 1).
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.billing import delivery_seam, issue, models as billing_models
from apps.notifications import models as outbound, rule_models, rule_service
from apps.notifications import services as notification_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_005_issue import (
    ISSUED_AT,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    a_priced_draft,
    an_authorised_run,
    electric_gl_accounts,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


# ── the fixtures every case here needs ─────────────────────────────────────
def a_paperless_account(monkeypatch, channels=("email",)):
    """A customers module that HAS published the delivery-preference read.

    The same shape `test_us_bil_023_delivery_queue.an_election` uses, and for
    the reason that file gives: `accounts.paperless` is PROPOSED-SCHEMA and
    unbuilt, so on today's deployment `delivery_seam.elected_channels` names NO
    extra channel and every bill gets the print floor and nothing else. **A bill
    that asks for no email cannot demonstrate an email being suppressed**, so
    these cases drive the published-read case with a stub — which is also J17's
    finished shape (*"240 print/PDF rows + email rows for paperless accounts"*)
    proved ahead of the lane that lands it (hard-won law 2).
    """
    from apps.customers import selectors as customer_selectors

    monkeypatch.setattr(
        customer_selectors,
        delivery_seam.ELECTION_READ,
        lambda account_id: channels,
        raising=False,
    )


def switch(actor, event_key, *, channel=None, on=True, event_on=None):
    """Do to the rule exactly what a System Admin does on SET-12D.

    Through `rule_service.update_rule` — the ONE write path into the rule
    tables — rather than through the ORM, so these cases exercise the same
    stored state the screen produces and cannot drift from it.
    """
    payload: dict = {}
    if event_on is not None:
        payload["enabled"] = event_on
    if channel is not None:
        payload["channels"] = {channel: {"enabled": on}}
    return rule_service.update_rule(event_key=event_key, actor=actor, **payload)


def issue_one(
    brazos,
    dana,
    *,
    invoice_no="BL-2607-000101",
    account_no="A-1042",
    run_key="2026-06|cycle-1",
    **overrides,
):
    """One bill, issued the way `issue_run` issues it. Returns the issued row."""
    electric_gl_accounts()
    account = an_account(dana, brazos, account_no=account_no)
    run = an_authorised_run(brazos, dana, key=run_key)
    draft = a_priced_draft(brazos, account, run, invoice_no=invoice_no, **overrides)
    return issue.issue_invoice(
        draft,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=dana,
    )


def queued_channels(invoice):
    return set(
        outbound.OutboundMessage.objects.filter(
            source_type="invoice", source_id=invoice.pk
        ).values_list("channel", flat=True)
    )


# ── 1 · THE HEADLINE ───────────────────────────────────────────────────────
def test_cr048_b2__bill_ready_email_switched_off_queues_no_email_row(brazos, dana, monkeypatch):
    """CR-048's one sentence, from the bill run's own side.

    *"Switching 'Bill ready — email' off on the settings screen changes nothing
    at all."* It changes this. The account is paperless — so billing asks for
    email — and this utility has said it does not email bills.

    The bill STILL ISSUES and the paper row is still there: a notification
    preference is not a billing refusal (BR-BIL-055, BR-BIL-036).
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        switch(dana, "bill_ready", channel=outbound.CHANNEL_EMAIL, on=False)

        billed = issue_one(brazos, dana)

        assert billed.status == billing_models.INVOICE_ISSUED
        # AMENDED 2026-10-01 (billing red triage): + PORTAL. Since `CR-084`
        # (`5b6aaa823`, 2026-09-07, PO: *"can you swithc on this now - Customer
        # portal"*) the PLATFORM offers the portal on `bill_ready`, beside the
        # print floor, and only the rule takes it away. It is not offered on
        # `bill_corrected`, so the rebill's sets below are unchanged.
        assert queued_channels(billed) == {outbound.CHANNEL_PRINT, outbound.CHANNEL_PORTAL}
        assert outbound.CHANNEL_EMAIL not in billed.delivery.channels
        # Not silent: the run report can say WHY, in a clerk's words.
        codes = {problem["code"] for problem in billed.delivery.problems}
        assert notification_services.QUEUE_CHANNEL_SWITCHED_OFF in codes


def test_cr048_b2__the_same_bill_is_emailed_when_the_switch_is_on(brazos, dana, monkeypatch):
    """The other half, or the case above could pass by never queueing email at all."""
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        switch(dana, "bill_ready", channel=outbound.CHANNEL_EMAIL, on=True)

        billed = issue_one(brazos, dana)

        # AMENDED 2026-10-01 (billing red triage): + PORTAL. Since `CR-084`
        # (`5b6aaa823`, 2026-09-07, PO: *"can you swithc on this now - Customer
        # portal"*) the PLATFORM offers the portal on `bill_ready`, beside the
        # print floor, and only the rule takes it away. It is not offered on
        # `bill_corrected`, so the rebill's sets below are unchanged.
        assert queued_channels(billed) == {
            outbound.CHANNEL_PRINT,
            outbound.CHANNEL_EMAIL,
            outbound.CHANNEL_PORTAL,
        }


# ── 2 · THE PRINT FLOOR (BR-BIL-036) ───────────────────────────────────────
def test_cr048_b2__the_print_floor_survives_the_whole_event_being_switched_off(
    brazos, dana, monkeypatch
):
    """A bill's paper copy cannot be switched off — not per channel, not at all.

    The utility switches *Bill ready* off entirely. Every channel it controls is
    suppressed and the floor is not one of them: paper on a bill is a PLATFORM
    rule about what a bill IS, and SET-12D does not edit platform rules.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch, channels=("email", "sms"))
        switch(dana, "bill_ready", event_on=False)

        billed = issue_one(brazos, dana)

        assert billed.status == billing_models.INVOICE_ISSUED
        assert queued_channels(billed) == {outbound.CHANNEL_PRINT}
        codes = {problem["code"] for problem in billed.delivery.problems}
        assert notification_services.QUEUE_EVENT_SWITCHED_OFF in codes


def test_cr048_b2__print_switched_off_in_the_table_is_queued_anyway(brazos, dana, monkeypatch):
    """The floor beats a rule that names print DIRECTLY, not only one that omits it.

    `bill_ready` carries no print toggle on SET-12, so a System Admin cannot
    switch paper off through the screen at all. This case reaches past the screen
    and writes the row anyway — the state a future catalogue change or a bad
    migration could produce — and requires the bill to be printed regardless.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        view = rule_service.rule("bill_ready")
        rule_models.NotificationRuleChannel.objects.update_or_create(
            tenant_id=brazos.id,
            rule_id=view.row.pk,
            channel=outbound.CHANNEL_PRINT,
            defaults={"enabled": False},
        )

        billed = issue_one(brazos, dana)

        assert outbound.CHANNEL_PRINT in queued_channels(billed)


# ── 3 · bill_ready VERSUS bill_corrected ───────────────────────────────────
def a_corrected_bill(brazos, dana):
    """A rebill in the shape `corrections.execute_restatement` leaves it.

    That function creates the replacement as a DRAFT, stamps
    `corrects_invoice_id` on it pointing back at the original (PO 2026-08-12,
    OQ-120 — the link lives on the NEW bill, because an issued bill is immutable
    and must not gain a column after issue), and only THEN calls
    `issue.issue_invoice`. This builds the same two rows without re-running the
    credit-note engine: what is under test is which EVENT the queue is told
    about, not how a correction is priced.
    """
    original = issue_one(brazos, dana, invoice_no="BL-2607-000101", account_no="A-1042")
    account = an_account(dana, brazos, account_no="A-1043")
    run = an_authorised_run(brazos, dana, key="2026-06|rebill-1")
    rebill = a_priced_draft(
        brazos, account, run, invoice_no="BL-2607-000102", corrects_invoice=original
    )
    issued = issue.issue_invoice(
        rebill,
        issued_at=ISSUED_AT,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=dana,
    )
    return original, issued


def test_cr048_b2__a_corrected_bill_fires_bill_corrected(brazos, dana, monkeypatch):
    """One source type, two events, and the bill itself says which.

    *Bill ready — email* is OFF and *Corrected bill — email* is ON. A rebill is a
    corrected bill: it must be emailed. If billing guessed the event from
    `source_type` it would suppress this — a customer who was overcharged never
    told their bill had been put right.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        switch(dana, "bill_ready", channel=outbound.CHANNEL_EMAIL, on=False)
        switch(dana, "bill_corrected", channel=outbound.CHANNEL_EMAIL, on=True)

        original, rebill = a_corrected_bill(brazos, dana)

        assert rebill.delivery.event_key == "bill_corrected"
        assert queued_channels(rebill) == {outbound.CHANNEL_PRINT, outbound.CHANNEL_EMAIL}
        # …and the ordinary bill obeyed the OTHER row.
        assert original.delivery.event_key == "bill_ready"
        # AMENDED 2026-10-01 (billing red triage): + PORTAL. Since `CR-084`
        # (`5b6aaa823`, 2026-09-07, PO: *"can you swithc on this now - Customer
        # portal"*) the PLATFORM offers the portal on `bill_ready`, beside the
        # print floor, and only the rule takes it away. It is not offered on
        # `bill_corrected`, so the rebill's sets below are unchanged.
        assert queued_channels(original) == {outbound.CHANNEL_PRINT, outbound.CHANNEL_PORTAL}


def test_cr048_b2__an_ordinary_bill_is_unaffected_by_the_correction_switch(
    brazos, dana, monkeypatch
):
    """The mirror image, so the discrimination cannot pass by firing one event.

    *Corrected bill — email* is OFF and *Bill ready — email* is ON. The ordinary
    bill is emailed; the rebill is not.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        switch(dana, "bill_ready", channel=outbound.CHANNEL_EMAIL, on=True)
        switch(dana, "bill_corrected", channel=outbound.CHANNEL_EMAIL, on=False)

        original, rebill = a_corrected_bill(brazos, dana)

        # AMENDED 2026-10-01 (billing red triage): + PORTAL. Since `CR-084`
        # (`5b6aaa823`, 2026-09-07, PO: *"can you swithc on this now - Customer
        # portal"*) the PLATFORM offers the portal on `bill_ready`, beside the
        # print floor, and only the rule takes it away. It is not offered on
        # `bill_corrected`, so the rebill's sets below are unchanged.
        assert queued_channels(original) == {
            outbound.CHANNEL_PRINT,
            outbound.CHANNEL_EMAIL,
            outbound.CHANNEL_PORTAL,
        }
        assert queued_channels(rebill) == {outbound.CHANNEL_PRINT}


def test_cr048_b2__the_event_is_read_from_the_bill_and_not_from_a_new_flag(brazos, dana):
    """`event_for_bill` reads `corrects_invoice_id` — the fact billing already holds.

    Asserted directly as well as through a run, because this is the whole of B2's
    judgment and it must be greppable: no parameter was added to `issue_invoice`,
    no column was added to `invoices`, and no caller can pass the wrong event.
    """
    from apps.notifications import rule_catalog

    class _Bill:
        corrects_invoice_id = None

    class _Rebill:
        corrects_invoice_id = "0000-original"

    assert delivery_seam.event_for_bill(_Bill()) == delivery_seam.EVENT_BILL_READY
    assert delivery_seam.event_for_bill(_Rebill()) == delivery_seam.EVENT_BILL_CORRECTED
    # The keys are the CATALOGUE's, never invented here (CR-048 wave B packet).
    assert delivery_seam.EVENT_BILL_READY in rule_catalog.EVENT_KEYS
    assert delivery_seam.EVENT_BILL_CORRECTED in rule_catalog.EVENT_KEYS


# ── 4 · WHAT THE RULE READ COSTS A FIVE-HUNDRED-BILL RUN ───────────────────
def test_cr048_b2__the_rule_read_is_two_selects_and_writes_nothing(brazos, dana, monkeypatch):
    """Requirement 3: a per-bill rule READ is fine; a per-bill WRITE is not.

    Wave A added `rule_service.channel_switches` precisely so the queue does not
    use `rule_service.rule()` — the SCREEN's read, which issues up to forty-five
    `get_or_create` WRITES over fifteen events, and which inside an issue
    transaction would put a write amplification on every bill in a run. This
    case measures what a bill actually costs: the queries the join adds, and
    that not one of them writes.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        switch(dana, "bill_ready", channel=outbound.CHANNEL_EMAIL, on=True)
        rules_before = rule_models.NotificationRule.objects.count()
        channels_before = rule_models.NotificationRuleChannel.objects.count()

        with CaptureQueriesContext(connection) as captured:
            issue_one(brazos, dana)

        rule_sql = [
            query["sql"]
            for query in captured.captured_queries
            if "notification_rule" in query["sql"]
        ]
        # Two SELECTs — the rule row, then its channel rows. Nothing more.
        assert len(rule_sql) == 2, rule_sql
        assert all(sql.lstrip().upper().startswith("SELECT") for sql in rule_sql), rule_sql
        # And no row was materialised as a side effect of billing.
        assert rule_models.NotificationRule.objects.count() == rules_before
        assert rule_models.NotificationRuleChannel.objects.count() == channels_before


def test_cr048_b2__the_run_report_says_which_event_suppressed_the_email(brazos, dana, monkeypatch):
    """Hard-won law 2 — built is not wired, so this asserts the last hop.

    The suppression is only useful if a clerk staring at a finished bill run can
    see it. `issue_run` folds the seam's `problems` into `delivery_problems` with
    a `bills` count per distinct code, and wave A's problem dict carries the
    `event_key` and the `channel` — so the run says *"channel switched off by
    rule · bill_ready · email · 2 bills"* rather than 480 identical lines or
    nothing at all.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        switch(dana, "bill_ready", channel=outbound.CHANNEL_EMAIL, on=False)
        electric_gl_accounts()
        run = an_authorised_run(brazos, dana)
        for index in range(2):
            a_priced_draft(
                brazos,
                an_account(dana, brazos, account_no=f"A-300{index}"),
                run,
                invoice_no=f"BL-2607-00030{index}",
            )

        outcome = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        assert len(outcome.issued) == 2
        suppressed = [
            problem
            for problem in outcome.delivery_problems
            if problem["code"] == notification_services.QUEUE_CHANNEL_SWITCHED_OFF
        ]
        assert len(suppressed) == 1, outcome.delivery_problems
        assert suppressed[0]["event_key"] == "bill_ready"
        assert suppressed[0]["channel"] == outbound.CHANNEL_EMAIL
        assert suppressed[0]["bills"] == 2


# ── 5 · BR-BIL-055 — ONE NAMED BREAK, NEVER A DEAD BATCH ───────────────────
def test_cr048_b2__an_unknown_event_is_one_named_break_and_the_run_carries_on(
    brazos, dana, monkeypatch
):
    """Requirement 4: whatever the rule join raises must cost ONE bill.

    `channel_decision` raises `QueueWriteRefused` for an event this platform
    cannot fire. That is NOTIFICATIONS' vocabulary, and `issue_run` catches
    `BillingRuleError` and nothing else, so an untranslated refusal would kill
    the whole run (DEF-047's lesson). The seam translates it — this case drives
    a bad event key onto the SECOND of three drafts and requires the other two
    to issue.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        electric_gl_accounts()
        run = an_authorised_run(brazos, dana)
        drafts = [
            a_priced_draft(
                brazos,
                an_account(dana, brazos, account_no=f"A-200{index}"),
                run,
                invoice_no=f"BL-2607-00020{index}",
            )
            for index in range(3)
        ]
        doomed = str(drafts[1].pk)
        real = delivery_seam.event_for_bill

        def _one_bad_event(invoice):
            if str(invoice.pk) == doomed:
                return "not_an_event_this_platform_can_fire"
            return real(invoice)

        monkeypatch.setattr(delivery_seam, "event_for_bill", _one_bad_event)

        outcome = issue.issue_run(
            run,
            issued_at=ISSUED_AT,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            actor=dana,
        )

        assert len(outcome.issued) == 2
        assert len(outcome.broken) == 1
        assert outcome.broken[0].invoice_id == doomed
        assert "not_an_event_this_platform_can_fire" in outcome.broken[0].detail
        # The refused bill is still a DRAFT — the transaction took it back — and
        # it left no half-written queue row behind.
        drafts[1].refresh_from_db()
        assert drafts[1].status == billing_models.INVOICE_DRAFT
        assert not outbound.OutboundMessage.objects.filter(source_id=drafts[1].pk).exists()


# ── 6 · A TENANT WHOSE RULES HAVE NEVER BEEN READ ──────────────────────────
def test_cr048_b2__a_tenant_with_no_stored_rule_issues_exactly_as_today(brazos, dana, monkeypatch):
    """Requirement 5: nothing changes for a utility whose rules were never read.

    Provisioning seeds the fifteen rule rows today (`seed_notification_settings`
    → `seed_rules`), but **that landed with DEF-258 and tenants provisioned
    before it have none** — which is precisely the tenant this case is about, so
    the rows are deleted rather than assumed absent.

    `channel_switches` then falls back to the catalogue's own seeded defaults —
    `_seeded_rule_kwargs` / `_seeded_channel_enabled`, the same two expressions
    `_ensure_rules` would have written — so a tenant with no rows and a tenant
    who visited the screen and saved nothing behave identically, and neither
    loses an email.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        rule_models.NotificationRuleChannel.objects.all().delete()
        rule_models.NotificationRule.objects.all().delete()

        billed = issue_one(brazos, dana)

        assert billed.status == billing_models.INVOICE_ISSUED
        # AMENDED 2026-10-01 (billing red triage): + PORTAL. Since `CR-084`
        # (`5b6aaa823`, 2026-09-07, PO: *"can you swithc on this now - Customer
        # portal"*) the PLATFORM offers the portal on `bill_ready`, beside the
        # print floor, and only the rule takes it away. It is not offered on
        # `bill_corrected`, so the rebill's sets below are unchanged.
        assert queued_channels(billed) == {
            outbound.CHANNEL_PRINT,
            outbound.CHANNEL_EMAIL,
            outbound.CHANNEL_PORTAL,
        }
        # Reading a rule must not CREATE one: a read path that writes is a read
        # path that turns a bill run into fifteen extra inserts per bill.
        assert not rule_models.NotificationRule.objects.exists()


def test_cr048_b2__nothing_was_sent(brazos, dana, monkeypatch):
    """BR-NOT-013 — every row still rests `queued`, asserted as a value.

    The join can only ever REMOVE a channel, so it cannot turn a queue write
    into a send; this case says so where a future change would trip over it.
    """
    with tenant_ctx(brazos):
        a_paperless_account(monkeypatch)
        billed = issue_one(brazos, dana)

        assert billed.delivery.dispatched is False
        rows = outbound.OutboundMessage.objects.filter(source_id=billed.pk)
        assert rows.exists()
        for row in rows:
            assert row.status == outbound.STATUS_QUEUED
            assert row.sent_at is None
