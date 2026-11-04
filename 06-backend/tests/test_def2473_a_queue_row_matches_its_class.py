# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-025 × US-PAY-009 TC-4 (the returned-payment letter) ×
#           US-NOT-001 (the queue write)   Screens: S22 · S33 · SET-09 · SET-12D
# Rules:    BR-NOT-024 (PRINT IS THE FLOOR on every customer document — PO
#           2026-08-29, *"don't switch of print for any document it is awayls
#           on"*) · BR-NOT-015 (an unauthored class REFUSES rather than printing
#           wording nobody wrote) · BR-NOT-027 (the document freeze — a message
#           that reaches `sent` is kept write-once under the kind its class
#           names) · BR-PAY-013 (the bounce and the customer's letter) ·
#           CLAUDE.md rule 6 (idempotency)
# Defect:   DEF-2473
# ───────────────────────────────────────────────────────
"""A queue row is never pinned to a template class of a different channel.

**THIS IS THE GUARD NOTHING HAD, AND ITS ABSENCE IS THE WHOLE OF `DEF-2473`.**

A queue write carries ONE template pin for every channel it names, and
BR-NOT-024's print floor ADDS a channel to writes the caller never asked to
widen. Put those two facts together and a caller asking for `email` on a floored
source kind silently queues a `pdf_print` row pinned to an EMAIL class. Measured
on the branch tip with *Payment failed — email* switched off: one row, channel
`pdf_print`, template_code `email_payment_failed`, status `queued` — a printed
letter pinned to an email body.

**Why nothing caught it, which is the part worth keeping.** Every existing
assertion in this repo names the class it expects (`assert row.template_code ==
receipts.FAILED_PAYMENT_TEMPLATE_CODE`) and is therefore satisfied by exactly the
wrong row. No check ever asked the one question that separates right from wrong
here: *is this class a form for this row's channel?* That question had no answer
in code at all — `kind` was prose on a catalog row that only ever reached a
screen — so `catalogs.channels_for_kind` was written to give it one, and this
file is what asks it.

────────────────────────────────────────────────────────────────────────────
WHY IT IS WORTH MORE THAN THE ONE ROW IT WAS WRITTEN FOR
────────────────────────────────────────────────────────────────────────────
Nothing reaches a customer today — no print, email or SMS provider is connected
(BR-NOT-013). But the document freeze shipped on 2026-08-30: from now on a
message that reaches `sent` has its rendered artefact stored **write-once, for
seven years, under the kind the pinned class names**
(`frozen_documents.DOCUMENT_KIND_BY_TEMPLATE_CLASS`). So the moment print is
switched on, this stops being a mislabelled queue row and starts being a
permanent legal record filed under the wrong document class — which is precisely
the sanity BR-NOT-027 exists to protect. The cost of the defect grows the day
somebody plugs in a printer; the cost of this file does not.

────────────────────────────────────────────────────────────────────────────
PROVED RED FIRST (hard-won law 7)
────────────────────────────────────────────────────────────────────────────
Both behavioural cases below were run against the pre-fix `receipts.py` — one
write naming `email`, pinned to `email_payment_failed` — and both failed on the
floor's print row:

    AssertionError: a `pdf_print` row is pinned to 'email_payment_failed',
    which is a form for ('email', 'sms') and not for print.

The structural case was proved red by deleting the `payment_failed_letter` entry
from `CHANNELS_BY_KIND`'s `"Print"` mapping, which is the shape a future lane's
new kind string will arrive in.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.notifications import catalogs
from apps.notifications import models as notification_models
from apps.notifications import services as notification_services
from apps.payments import models as payment_models
from apps.payments import receipts, reversal
from apps.payments import services as payment_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 18, 10, 30, tzinfo=UTC)
RETURNED_ON = datetime(2026, 8, 29, 11, 15, tzinfo=UTC)
AMOUNT = Decimal("247.30")

EMAIL = notification_models.CHANNEL_EMAIL
PRINT = notification_models.CHANNEL_PRINT


def _record(actor, account):
    return payment_services.record_payment(
        actor,
        account_id=account.pk,
        amount=AMOUNT,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        method_code="check",
    )


def _switch(actor, event_key, channel, *, on):
    """Do to the rule exactly what a System Admin does on SET-12D.

    Through `rule_service.update_rule` — the ONE write path into the rule tables
    — never through the ORM, so these cases exercise the same stored state the
    screen produces and cannot drift from it. Same helper as
    `test_cr048_b3_payments_fires_its_events.py`, deliberately spelled the same.
    """
    from apps.notifications import rule_service

    return rule_service.update_rule(
        event_key=event_key, actor=actor, channels={channel: {"enabled": on}}
    )


def _assert_every_row_matches_its_class(tenant):
    """THE INVARIANT, over every row the scenario left on the queue.

    Deliberately NOT scoped to the rows a case expects: the defect was an EXTRA
    row nobody had named, so a check that only looks at the rows it went looking
    for cannot see it. This reads the whole table for the tenant.
    """
    rows = notification_models.OutboundMessage.objects.filter(tenant_id=tenant.pk)
    seen = 0
    for row in rows:
        serves = catalogs.class_serves_channel(row.template_code or "", row.channel)
        if serves is None:
            # Billing's own classes have their own registry and no SET-09 row
            # (`catalogs.listing_for` documents both correct absences). Not a
            # violation, and not silently counted as a pass either.
            continue
        seen += 1
        assert serves is True, (
            f"a {row.channel!r} row is pinned to {row.template_code!r}, which is a form "
            f"for {catalogs.channels_for_kind(catalogs.LISTINGS[row.template_code].kind)} "
            f"and not for {row.channel!r}. A queue write carries ONE template pin for "
            "every channel it names, so a document going out on two channels is two "
            "writes — see `queue_receipt_for_recorded_payment`, which has always done "
            "this, and DEF-2473, which is what happens when a path does not."
        )
    assert seen, "no queue row was checked — the scenario queued nothing, so it proves nothing"


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE STRUCTURAL HALF — every listed class states which channels it serves
# ══════════════════════════════════════════════════════════════════════════
def test_def2473__every_listed_class_states_which_channels_it_is_a_form_for():
    """`kind` stopped being decoration on 2026-08-30.

    Every SET-09 row carries a `kind` — *"Print"*, *"Email + SMS"*, *"Certified
    print + email"* — and until this defect nothing in code could read one. The
    mapping FAILS CLOSED, so a lane adding a new kind string lands here rather
    than getting a guess: `channels_for_kind` raises instead of inferring from
    the words in the name, which is the same posture hard-won law 3 asks for.
    """
    for code, listing in catalogs.LISTINGS.items():
        channels = catalogs.channels_for_kind(listing.kind)
        assert channels, f"{code} has kind {listing.kind!r} and serves no channel at all"
        for channel in channels:
            assert catalogs.class_serves_channel(code, channel) is True


def test_def2473__an_unmapped_kind_raises_rather_than_guessing():
    """The fail-closed half, asserted rather than described.

    A kind nobody has ruled on must not resolve to "no channels" — that reads as
    a class that serves nothing and passes every check above by being empty.
    """
    with pytest.raises(catalogs.UnknownTemplateKind):
        catalogs.channels_for_kind("Hologram")


def test_def2473__the_returned_payment_letter_has_a_print_class_and_a_seeded_body():
    """The class `DEF-2473`'s fix turns on: a PRINT form, never an email one.

    ⚠ AMENDED 2026-10-30 (`DEF-PAY-10744`). This asserted the class was blank —
    BR-NOT-015, *no lane invents a letter about somebody's returned money*. The
    PO then ruled the payments audit's L2-04 fixed (*"Rest we will fix"*: a
    proper NSF email and letter), so it is seeded as a default the utility
    edits. The print/email split this defect is about is unchanged.
    """
    from apps.notifications import seed_templates

    code = receipts.FAILED_PAYMENT_LETTER_TEMPLATE_CODE
    assert catalogs.class_serves_channel(code, PRINT) is True
    assert catalogs.class_serves_channel(code, EMAIL) is False
    assert code in {entry.code for entry in seed_templates.SEEDABLE}
    assert seed_templates.absent_reason(code) is None


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE BEHAVIOURAL HALF — the rows a real bounce actually leaves
# ══════════════════════════════════════════════════════════════════════════
def test_def2473__a_bounce_queues_a_print_letter_pinned_to_the_print_class(brazos, marcus, dana):
    """The default path, with every switch left alone.

    Two rows for one bounce — the printed letter and the emailed one — each
    pinned to its OWN class, and the outcome names both separately because S22's
    result panel groups on these codes and *"we posted them a letter"* and
    *"we emailed them"* are two different things for a clerk reading it.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        recorded = _record(marcus, account)
        bounce = reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=RETURNED_ON,
            reason=payment_models.REVERSAL_REASON_NSF,
            idempotency_reference=str(uuid.uuid4()),
        )

        letter = notification_models.OutboundMessage.objects.get(
            tenant_id=brazos.pk,
            source_type="payment",
            source_id=bounce.reversal_id,
            channel=PRINT,
        )
        emailed = notification_models.OutboundMessage.objects.get(
            tenant_id=brazos.pk,
            source_type="payment",
            source_id=bounce.reversal_id,
            channel=EMAIL,
        )
        _assert_every_row_matches_its_class(brazos)

    # THE DEFECT, ASSERTED BY NAME so a regression reads as itself.
    assert letter.template_code == receipts.FAILED_PAYMENT_LETTER_TEMPLATE_CODE
    assert letter.template_code != receipts.FAILED_PAYMENT_TEMPLATE_CODE
    assert emailed.template_code == receipts.FAILED_PAYMENT_TEMPLATE_CODE

    codes = {problem["code"] for problem in bounce.problems}
    assert receipts.FAILED_NOTICE_LETTER_QUEUED in codes
    assert receipts.FAILED_NOTICE_QUEUED in codes


def test_def2473__with_the_email_switched_off_the_letter_is_print_and_says_so(brazos, marcus, dana):
    """`DEF-2473`'s measured case, now asserting the opposite of what it found.

    Measured on the branch tip before the fix: **one row, channel `pdf_print`,
    template_code `email_payment_failed`, status `queued`** — and the outcome
    reported `payment_failed_notice_queued channel=email` beside
    `channel_switched_off_by_rule channel=email`, with no email row in the table.

    Both halves are asserted here: the surviving row is a PRINT row pinned to the
    PRINT class (BR-NOT-024's floor doing its job with the right document), and
    the outcome no longer claims an email that was never written.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        recorded = _record(marcus, account)
        _switch(dana, receipts.EVENT_PAYMENT_FAILED, EMAIL, on=False)

        bounce = reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=RETURNED_ON,
            reason=payment_models.REVERSAL_REASON_NSF,
            idempotency_reference=str(uuid.uuid4()),
        )

        rows = notification_models.OutboundMessage.objects.filter(
            tenant_id=brazos.pk, source_type="payment", source_id=bounce.reversal_id
        )
        assert rows.filter(channel=EMAIL).count() == 0, "the utility switched the email off"
        letter = rows.get(channel=PRINT)
        _assert_every_row_matches_its_class(brazos)

    # The floor still posts the letter — that is BR-NOT-024 — and it is now the
    # PRINTED letter rather than an email body on paper.
    assert letter.template_code == receipts.FAILED_PAYMENT_LETTER_TEMPLATE_CODE

    codes = {problem["code"] for problem in bounce.problems}
    assert notification_services.QUEUE_CHANNEL_SWITCHED_OFF in codes
    # THE FALSE STATEMENT, asserted gone. A screen must never be told a document
    # was queued on a channel that has no row.
    assert receipts.FAILED_NOTICE_QUEUED not in codes
    assert receipts.FAILED_NOTICE_LETTER_QUEUED in codes


def test_def2473__a_recorded_payments_three_receipts_each_match_their_own_channel(brazos, marcus):
    """The path that was already RIGHT, asserted so it stays right.

    `queue_receipt_for_recorded_payment` writes three times for one payment —
    print, email, SMS — each with its own class, and its docstring has carried
    the reason since the email half landed: *"a queue write carries ONE template
    pin for every channel it names, and an email row pinned to the print class
    would render the wrong document"*. That reasoning was correct and simply
    never reached the bounce path. Nothing asserted it as an INVARIANT, though —
    the existing cases name the class they expect — so this is that assertion.
    """
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        recorded = _record(marcus, account)
        rows = {
            row.channel: row
            for row in notification_models.OutboundMessage.objects.filter(
                tenant_id=brazos.pk, source_type="payment", source_id=recorded.payment_id
            )
        }
        _assert_every_row_matches_its_class(brazos)

    assert rows[PRINT].template_code == receipts.RECEIPT_TEMPLATE_CODE
    assert rows[EMAIL].template_code == receipts.EMAIL_RECEIPT_TEMPLATE_CODE


def test_def2473__the_print_floor_never_widens_a_write_onto_a_class_that_cannot_serve_it(
    brazos, marcus, dana
):
    """The general statement, over the source kinds payments actually writes.

    The floor is a PLATFORM rule that adds a channel the caller did not ask for
    (BR-NOT-024, and SET-12D cannot edit it). This asserts the consequence that
    has to hold for that to be safe: for every floored source kind payments
    writes on, every row it leaves is pinned to a class that is a form for that
    row's own channel — with the master toggle off, which is the widest the floor
    ever reaches, since it survives even that.
    """
    floor = notification_services.CHANNEL_FLOOR_BY_SOURCE
    assert "payment" in floor, "this case is about the floor; without it it proves nothing"

    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        _switch(dana, receipts.EVENT_PAYMENT_FAILED, EMAIL, on=False)
        _switch(dana, receipts.EVENT_PAYMENT_RECEIVED, EMAIL, on=False)
        recorded = _record(marcus, account)
        reversal.reverse_payment(
            dana,
            payment_id=recorded.payment_id,
            returned_on=RETURNED_ON,
            reason=payment_models.REVERSAL_REASON_NSF,
            idempotency_reference=str(uuid.uuid4()),
        )
        _assert_every_row_matches_its_class(brazos)

        # …and the floor did what it is for: a printed copy of both documents
        # survives a utility switching every electronic channel off.
        printed = notification_models.OutboundMessage.objects.filter(
            tenant_id=brazos.pk, source_type="payment", channel=PRINT
        )
        assert printed.count() >= 2, "BR-NOT-024: print is the floor, on both documents"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2473 (12-governance/10-defect-log.csv) · BR-NOT-024 (PO ruling
#   2026-08-29, apps/notifications/services.CHANNEL_FLOOR_BY_SOURCE) ·
#   BR-NOT-015 · BR-NOT-027 (apps/notifications/frozen_documents.py)
# generated: 2026-08-30 by the DEF-2473 lane
# checklist: A✔ B=n/a(no new HTTP surface) C✔ D=n/a E=n/a(the codes reach S22's
#   existing result panel, which already groups on them) F✔ G✔ H=deferred
# gates: PROVED RED FIRST — both behavioural cases were run against the pre-fix
#   single-write `queue_failed_payment_notice` and failed on the floor's print
#   row pinned to 'email_payment_failed'; the structural case by removing the
#   "Print" entry from CHANNELS_BY_KIND.
# exceptions: (1) `class_serves_channel` returns None for billing's own classes
#   and `_assert_every_row_matches_its_class` SKIPS them — B2 r10 #4 gives
#   bill_residential / bill_commercial / statement their own registry, so their
#   absence from LISTINGS is correct and not a violation. The skip is counted,
#   and the helper refuses a scenario that checked nothing. (2) This file asserts
#   the invariant over PAYMENTS' writers only. The same shape is open on three
#   other floored source kinds — see the defect filed alongside this one; fixing
#   those needs print classes nobody has written wording for, which is a
#   template-library decision and not this lane's to take.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
