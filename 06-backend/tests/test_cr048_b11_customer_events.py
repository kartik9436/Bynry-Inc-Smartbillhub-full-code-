# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 — the rule the queue reads) × the seven writers
#           this wave fed an event key to
#           Screens: S8 (Settings → Notifications)
# Rules:    BR-NOT-017 (ONE HOME — every notification rule on one screen) ·
#           BR-NOT-018 (an event with no trigger is DRAWN and REFUSED by name,
#           never silently enabled) · BR-NOT-024 (print is the floor on
#           `invoice`, `payment`, `notice`, `plan`, `account` and `move` — and
#           on NOTHING else. ⚠ THIS LINE READ "`invoice`, `payment`, `notice`,
#           `plan` — and on NOTHING else" until 2026-08-30, when the PO
#           confirmed the four-kind list was narrower than their ruling and
#           widened it to SIX. `account` — this file's own kind — is the case
#           that decided it, because it carries the deposit-received
#           confirmation) ·
#           BR-NOT-005 (queue only; nothing sends) · BR-NOT-013 (no adapter on
#           any channel) · CLAUDE.md rule 6 (idempotency) · rule 2 (money)
# Change:   CR-048 wave B task B11 — *"The remaining thirteen customer events —
#           statement, credit, refund, write-off, deposit, autopay, plan change,
#           two more plan notices, outage, and the rest"*.
# Tests:    this file
# Impacts:  apps/notifications/rule_catalog.py · customer_events.py ·
#           apps/payments/notices.py · receipts.py · refunds.py · writeoffs.py ·
#           services.py · apps/customers/close_out.py · services.py ·
#           notifications_seam.py · apps/billing/delivery_seam.py ·
#           corrections.py
# ───────────────────────────────────────────────────────
"""CR-048 B11 — the last thirteen wordings get a rule, and seven get a sender.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE TWO FAULTS THIS WAVE KEEPS FINDING, AND WHY EACH NEEDS ITS OWN      ║
║  KIND OF TEST.                                                           ║
╚══════════════════════════════════════════════════════════════════════════╝

**DEF-2511 — a template code is not a document type.** Three separate writers
pinned a string that no catalogue declares: `plan_installment_missed` (fixed by
B10), `plan_installment_reminder` and `plan_change` (both fixed here). Every one
of them queued a row that would render from wording that does not exist, and
every one passed its own tests, because a `template_code` column takes any
string. **So this file asserts the codes MECHANICALLY, over the whole catalogue,
rather than eyeballing them** — the constraint CR-048 states in as many words:
*"assert it in a test, do not eyeball it."*

**DEF-2512 — an idempotency key that swallows the SECOND message.** Keyed on
something too coarse — the plan, the account, the payment — the second write
finds the first row and returns `created=False`. There is no error, no gap in
any trail, and a customer is chased once and never again.

⚠ **A TEST THAT QUEUES THE SAME THING TWICE PROVES THE WRONG HALF.** It passes
on the broken version, because the second write is SUPPOSED to find the first
row. What a coarse key loses is a DIFFERENT message, so every idempotency case
below **queues the second THING** — a second deposit, a second write-off, a
second refund, the missed notice after the reminder — and asserts two rows.

────────────────────────────────────────────────────────────────────────────
WHAT "CLOSED" MEANS HERE, STATED SO THE COUNT IS NOT READ AS A PROMISE
────────────────────────────────────────────────────────────────────────────
Thirteen classes left B9's coverage gap on this commit and the gap is now ZERO.
**That is not thirteen messages a utility will receive.** Seven have a live
writer; five are DRAWN AND REFUSED by name with the open question that owns each
absence; one needed no new event because it is the SMS face of a receipt
`payment_received` already governs. Both facts are asserted below, because the
first one alone would read as a promise.

NOTHING HERE SENDS ANYTHING: every message is a queue row (BR-NOT-005), and no
adapter exists on any channel (BR-NOT-013).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.notifications import catalogs, customer_events
from apps.notifications import models as notification_models
from apps.notifications import rule_catalog, seed_templates, services
from apps.payments import notices as payments_notices
from apps.payments import receipts as payments_receipts
from apps.payments import refunds as payments_refunds
from apps.payments import writeoffs as payments_writeoffs
from apps.billing import delivery_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — every business date in this file is NAMED.
TODAY = date(2026, 8, 25)
RECEIVED_AT = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)

#: The thirteen classes B11 owns, quoted from the CR's own task row rather than
#: recomputed, so a catalogue that quietly renamed one fails here rather than
#: agreeing with itself.
B11_CLASSES: tuple[str, ...] = (
    "email_account_closed",
    "email_autopay",
    "email_credit_issued",
    "email_deposit",
    "email_plan_change",
    "email_refund_issued",
    "email_statement",
    "plan_notice_upcoming",
    "plan_notice_void",
    "service_door_hanger",
    "service_outage_notice",
    "sms_payment_received",
    "writeoff_notice",
)

#: The five that have no writer, and the question that owns each absence. A row
#: moving off this list is a lane wiring something, which is good and must be
#: deliberate; a row moving ONTO it is a trigger that stopped working.
B11_DRAWN_AND_REFUSED: dict[str, str] = {
    "statement_ready": "OQ-1160",
    "planned_outage_notice": "OQ-1161",
    "autopay_enrolled": "OQ-1162",
    "payment_plan_voided": "OQ-1163",
    "door_hanger_left": "OQ-249",
}

#: The seven with a live writer, and the module that fires each. Named rather
#: than derived: *"a live trigger"* is a claim about code somewhere else, and a
#: derivation would only ever agree with whatever the catalogue happened to say.
B11_LIVE: dict[str, str] = {
    "payment_plan_instalment_upcoming": "apps.payments.notices.send_plan_notices",
    "refund_issued": "apps.payments.refunds.issue_refund",
    "credit_issued": "apps.billing.corrections.execute_credit_only",
    "write_off_approved": "apps.payments.writeoffs.approve_write_off",
    "account_closed": "apps.customers.close_out.close_out",
    "deposit_received": "apps.payments.services.record_payment",
    "rate_plan_changed": "apps.customers.services.change_plan",
}


def _seeded(actor):
    seed_templates.seed_notice_templates(actor, on_date=TODAY)


def _queue(tenant, **filters):
    return notification_models.OutboundMessage.objects.filter(tenant=tenant, **filters)


# ══════════════════════════════════════════════════════════════════════════
# 1 · DEF-2511 — EVERY PINNED CODE IS A CLASS THIS PLATFORM SEEDS
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b11__every_template_code_a_writer_pins_is_a_class_we_seed():
    """**The check DEF-2511 needed and nobody had.**

    Three writers have pinned a string no catalogue declares — two payment-plan
    NOTICE TYPES and the bare word `plan_change` — and each survived because the
    column takes any string and every surrounding test asserted a shape rather
    than a code. This asserts every code every writer pins, in one place, by
    membership in the seeded set rather than by reading them.

    The codes are collected from the WRITERS' own published constants, not from
    a list retyped here: a list would agree with itself the day somebody changed
    a constant and forgot this file.
    """
    seeded = {seed.code for seed in seed_templates.SEEDABLE}
    pinned = {
        "payments.notices (missed / second notice)": payments_notices.MISSED_TEMPLATE_CODE,
        "payments.notices (instalment reminder)": payments_notices.UPCOMING_TEMPLATE_CODE,
        "payments.receipts (print receipt)": payments_receipts.RECEIPT_TEMPLATE_CODE,
        "payments.receipts (email receipt)": payments_receipts.EMAIL_RECEIPT_TEMPLATE_CODE,
        "payments.receipts (SMS receipt)": payments_receipts.SMS_RECEIPT_TEMPLATE_CODE,
        "payments.receipts (returned payment)": payments_receipts.FAILED_PAYMENT_TEMPLATE_CODE,
        "payments.refunds": payments_refunds.REFUND_TEMPLATE_CODE,
        "payments.writeoffs": payments_writeoffs.WRITE_OFF_TEMPLATE_CODE,
        "billing.delivery_seam (goodwill credit)": delivery_seam.CREDIT_TEMPLATE_CODE,
        "notifications.customer_events (move-in)": customer_events.TEMPLATE_MOVE_IN,
        "notifications.customer_events (move-out)": customer_events.TEMPLATE_MOVE_OUT,
        "notifications.customer_events (account closed)": (customer_events.TEMPLATE_ACCOUNT_CLOSED),
        "notifications.customer_events (deposit)": customer_events.TEMPLATE_DEPOSIT,
        "notifications.customer_events (rate plan)": (customer_events.TEMPLATE_RATE_PLAN_CHANGE),
    }
    undeclared = {where: code for where, code in pinned.items() if code not in seeded}
    assert undeclared == {}, (
        f"these writers pin a template code no catalogue declares: {undeclared}. "
        "A queue row pinned to a class nothing seeds renders as nothing anybody "
        "wrote, and no test downstream can see it — DEF-2511, three times."
    )
    # And each has a token whitelist to render against, which is the other half
    # of the same guarantee: `rendering` refuses a body it cannot check.
    for where, code in pinned.items():
        assert catalogs.catalog_for(code) is not None, (
            f"{where} pins {code!r}, which this platform seeds but has no "
            "merge-variable catalogue for — so a body would be saved against no "
            "whitelist at all."
        )


def test_cr048_b11__every_event_key_a_writer_names_is_a_row_on_set_12():
    """B1 forbids payments, customers and billing from importing notifications,
    so every event key in those modules is a STRING. `queue_document` refuses an
    unknown one — and the refusal would land after the money had moved, at the
    end of a committed close-out, or inside a nightly plan-notice run.

    So the strings are checked HERE, where the failure is a red test rather than
    a support call. `rule_catalog.event()` raises `KeyError` naming the whole
    vocabulary, which is the shape this asserts.
    """
    for where, key in {
        "payments.notices (missed)": payments_notices.EVENT_PLAN_INSTALMENT_MISSED,
        "payments.notices (reminder)": payments_notices.EVENT_PLAN_INSTALMENT_UPCOMING,
        "payments.receipts (received)": payments_receipts.EVENT_PAYMENT_RECEIVED,
        "payments.receipts (failed)": payments_receipts.EVENT_PAYMENT_FAILED,
        "payments.refunds": payments_refunds.EVENT_REFUND_ISSUED,
        "payments.writeoffs": payments_writeoffs.EVENT_WRITE_OFF_APPROVED,
        "billing.delivery_seam (credit)": delivery_seam.EVENT_CREDIT_ISSUED,
        "notifications.customer_events (closed)": customer_events.EVENT_ACCOUNT_CLOSED,
        "notifications.customer_events (deposit)": customer_events.EVENT_DEPOSIT_RECEIVED,
        "notifications.customer_events (rate plan)": (customer_events.EVENT_RATE_PLAN_CHANGED),
    }.items():
        assert rule_catalog.event(key).key == key, where


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE THIRTEEN, AND WHAT "CLOSED" MEANS
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b11__all_thirteen_classes_now_have_a_rule():
    """CR-048's own task row, asserted class by class rather than as a count.

    A bare `gap == 0` would pass if thirteen unrelated classes had been dropped
    from the seed catalogue, which is the failure `ADOPTED_SINCE_TEARDOWN`'s
    reconciliation exists to make visible. This asserts the NAMES.
    """
    gap = set(rule_catalog.seeded_wording_without_rule())
    ruled = rule_catalog.ruled_template_classes()
    still_unruled = [code for code in B11_CLASSES if code in gap]
    assert still_unruled == [], (
        f"{still_unruled} still have wording seeded on every tenant and no rule "
        "that could send them — they are B11's own thirteen."
    )
    for code in B11_CLASSES:
        assert code in ruled, (
            f"{code!r} is not named by any event on any channel, so no switch on "
            "Settings → Notifications governs it."
        )
        assert code in {seed.code for seed in seed_templates.SEEDABLE}, (
            f"{code!r} left the gap because it stopped being SEEDED, not because "
            "a rule adopted it. That is a wording being dropped, which is a "
            "different thing entirely and worth stopping for."
        )


def test_cr048_b11__zero_in_the_gap_is_not_thirteen_new_messages():
    """⚠ **THE COUNT MUST NOT BE READ AS A PROMISE, so both halves are here.**

    Seven of the thirteen have a live writer. Five have none and are DRAWN AND
    REFUSED by name (BR-NOT-018) — the honest form for a message nothing can
    send, and a strict improvement on what they were before, which was
    INVISIBLE: a body in the template library that no screen mentioned. Each
    carries the open question that owns its absence, and the five absences are
    five different absences rather than one.
    """
    for key, question in B11_DRAWN_AND_REFUSED.items():
        event = rule_catalog.event(key)
        assert event.trigger_blocked_by == question, (
            f"{key!r} names {event.trigger_blocked_by!r} as its blocker and the "
            f"question that owns its absence is {question}. A row that quietly "
            "stopped saying nothing fires it is a switch that promises something."
        )
    for key in B11_LIVE:
        event = rule_catalog.event(key)
        assert event.trigger_blocked_by is None, (
            f"{key!r} carries a blocker, so nothing fires it — and the settings "
            f"screen offers a switch that changes nothing. Its writer is "
            f"{B11_LIVE[key]}."
        )
        assert event.template_classes, (
            f"{key!r} names no template class on any channel, so there is nothing "
            "for its writer to pin."
        )


def test_cr048_b11__the_account_kind_carries_the_print_floor():
    """⛔ **THIS CASE WAS A NEGATIVE AND IT IS NOW A POSITIVE — the PO reversed
    it, and this is the kind that decided the whole question.**

    It was called `test_cr048_b11__no_fifth_print_floor_was_invented` and its
    docstring read: *"BR-NOT-024 (PO 2026-08-29, verbatim: 'this is correct -
    don't switch of print for any document it is awayls on') names FOUR source
    kinds. This wave added a fifth KIND — `account`, for the three
    account-lifecycle letters — and deliberately gave it no floor, because
    adding one would be a lane writing signed law. The visible consequence is
    asserted with it, so nobody later reads the absence as an oversight: a
    utility that switches Account closed off gets NO row at all."* Its
    assertions were::

        assert set(services.CHANNEL_FLOOR_BY_SOURCE) == {
            "invoice", "payment", "notice", "plan"
        }
        assert "account" not in services.CHANNEL_FLOOR_BY_SOURCE
        decision = services.channel_decision("account", ("email",))
        assert decision.floor_added == ()

    **It was right about the process and wrong about the rule, and the right
    half is why it changed correctly.** A lane may not widen a signed rule by
    editing a dictionary — so on 2026-08-30 the merge lane put it to the PO
    instead, saying the four-kind list was narrower than what they had actually
    said. **The deciding case is this very kind:** `account` carries the
    DEPOSIT-RECEIVED confirmation, which acknowledges money received and is a
    receipt by any reading, and the ruling's own words are *"don't switch of
    print for any document it is awayls on"*. The PO confirmed, verbatim: *"Im
    okay with your suggestions, you are correct"*.

    So the floor names **six** kinds now — bills, receipts, notices, plan
    letters, account letters and move letters. ⚠ `move` was **not separately
    ruled**: it was taken under the principle the ruling settled, because the
    floor is per SOURCE KIND and that kind carries the letter announcing a
    customer's final bill. **And the arithmetic put to the PO was wrong and is
    corrected here rather than repeated** — it said the rule would widen to
    seven, counting the three account letters as three kinds when they are three
    events inside one. Four plus `account` is five; `move` makes six.

    The visible consequence is asserted with the rule, as it was before and now
    the other way round: a utility that switches *Account closed* off still
    posts the letter.
    """
    assert set(services.CHANNEL_FLOOR_BY_SOURCE) == {
        "invoice",
        "payment",
        "notice",
        "plan",
        "account",
        "move",
    }
    assert "account" in notification_models.SOURCE_TYPES
    assert "account" in services.CHANNEL_FLOOR_BY_SOURCE
    # A caller that asks for email alone gets paper added to it — which is the
    # whole of the reversal, stated as the thing a customer would notice.
    decision = services.channel_decision("account", ("email",))
    assert decision.floor_added == (notification_models.CHANNEL_PRINT,)
    assert decision.channels == (
        notification_models.CHANNEL_PRINT,
        notification_models.CHANNEL_EMAIL,
    )
    # And the kinds that genuinely keep no floor are named one by one, so this
    # case fails BY NAME if a later wave widens the rule without a ruling.
    # Together the two sets are every member of `SOURCE_TYPES`.
    #
    # ⚠ **THIS ASSERTION WAS RED FOR ELEVEN DAYS AND FOUR KINDS WALKED PAST IT
    # (2026-09-15).** It read *"the four kinds that genuinely keep no floor are
    # still exactly four"* and listed `report · ledger · bulk_action · test`.
    # `portal` joined `SOURCE_TYPES` on 2026-09-04, `appointment` on 2026-09-05
    # and `message` on 2026-09-12 — each correctly given no floor, each with its
    # reasoning written out beside the value, and **none of them added here**,
    # so this case had been failing since 2026-09-04 naming a kind nobody
    # classified. `service_request` (2026-09-15) was the fourth. That is exactly
    # the shape hard-won law 7 names first: a guard proved red at birth and then
    # never read again, with a suite busy enough for a true red to hide in. It
    # is repaired rather than deleted, and the count is gone from the prose
    # because a sentence carrying a number goes stale the next time the number
    # moves — the list itself is the assertion now.
    #
    # The four that keep no floor for a PHYSICAL reason are the first four; the
    # four below them are JUDGMENTS with their reasoning in
    # `models.SOURCE_TYPES` and in `test_cr048_print_floor.py`'s buckets.
    #
    # ⚠ **A NINTH JOINED ON 2026-09-20 — `transfer` (`DEF-CUS-5949`), AND IT IS
    # ADDED IN THE SAME COMMIT AS THE KIND**, which is the whole point of the
    # paragraph above: the four that walked past this assertion did so because
    # adding a kind and classifying it are two acts and only the first felt
    # like the work. A property sale queues three messages on commit — two
    # letters and a text — and `BR-NOT-024` names SIX kinds print is the floor
    # on, none of them a transfer. **The consequence is stated rather than
    # hidden: a utility gets an email and a text and no posted letter.** If one
    # is asked for, that is a `BR-NOT-024` amendment for the PO and never an
    # edit to a dictionary — the `move` precedent, one paragraph up.
    assert set(notification_models.SOURCE_TYPES) - set(services.CHANNEL_FLOOR_BY_SOURCE) == {
        "report",
        "ledger",
        "bulk_action",
        "test",
        "portal",
        "appointment",
        "message",
        "service_request",
        "transfer",
        # ⚠ **RED AGAIN FROM 2026-10-02 UNTIL 2026-10-29, THE SAME SHAPE A
        # SECOND TIME** — `connection` (CR-163-BRC10), `field_work` (CR-168),
        # `usage_alert` (CR-182), `agreement` (CR-190) and `staff_access`
        # (CR-188) each joined `SOURCE_TYPES` with no floor and were classified
        # in `test_cr048_print_floor.py` but not here. Repaired by the lane that
        # added the next one, `service_state` (DEF-NOT-10649), in its commit.
        "connection",
        "field_work",
        "usage_alert",
        "agreement",
        "staff_access",
        "service_state",
        # DEF-PAY-10651 (2026-10-29), the friendly past-due reminder off `notice`.
        "reminder",
    }


# ══════════════════════════════════════════════════════════════════════════
# 3 · DEF-2512 — THE SECOND THING, WHICH IS THE HALF THAT MATTERS
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b11__the_reminder_and_the_missed_notice_are_two_rows(brazos, dana):
    """**Two documents about ONE instalment, four days apart.**

    The reminder goes three days before an instalment is due and the missed
    notice the day after it is unmet — so keying both on the instalment's own id
    would put them on one idempotency tuple, and the missed notice would find
    the reminder's row and return `created=False`. The customer would be
    reminded and then never chased, with no error anywhere.

    This is the one case a "queue it twice" test cannot see, because the two
    writes are different documents rather than a replay.
    """
    from tests.test_cr048_b6_b10 import (  # noqa: PLC0415 — one shared world
        _a_plan_with_a_missed_instalment,
        _an_occupant,
    )

    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="9 Rowan Way", name="Twice, Tam")
        plan = _a_plan_with_a_missed_instalment(brazos, account)
        first = plan.installments.order_by("seq").first()

        # −3 days: the reminder for instalment 1. +1 day: its missed notice.
        payments_notices.send_plan_notices(
            plan, as_of=first.due_date - timedelta(days=3), actor=dana
        )
        payments_notices.send_plan_notices(
            plan, as_of=first.due_date + timedelta(days=1), actor=dana
        )

        rows = list(_queue(brazos, source_type="plan"))

    codes = sorted(row.template_code for row in rows)
    assert codes == ["plan_notice_missed", "plan_notice_upcoming"], (
        "the reminder and the missed notice about ONE instalment did not both "
        f"reach the queue: {[(r.template_code, str(r.source_id)) for r in rows]}. "
        "Sharing an idempotency tuple, the second silently dedupes into the "
        "first and the customer is reminded but never chased."
    )
    assert len({str(row.source_id) for row in rows}) == 2, (
        "both letters carry the same source id, so they are two rows only by "
        "accident of some other column."
    )
    # And the reminder no longer pins a NOTICE TYPE (DEF-2511): the code it
    # carries is the wording this platform actually seeds.
    reminder = next(row for row in rows if row.template_code == "plan_notice_upcoming")
    assert reminder.event_key == payments_notices.EVENT_PLAN_INSTALMENT_UPCOMING


def test_cr048_b11__the_reminder_is_keyed_per_instalment(brazos, dana):
    """Twelve instalments are twelve reminders, not one.

    Keyed on the PLAN — as this writer was from 2026-08-11 until 2026-08-30 —
    every reminder after the first found the same row and wrote nothing, so a
    customer on a twelve-month plan was reminded once. This sends the reminders
    for two DIFFERENT instalments and asserts two rows.
    """
    from tests.test_cr048_b6_b10 import (  # noqa: PLC0415
        _a_plan_with_a_missed_instalment,
        _an_occupant,
    )

    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="11 Rowan Way", name="Many, Mo")
        plan = _a_plan_with_a_missed_instalment(brazos, account)
        instalments = list(plan.installments.order_by("seq"))
        assert len(instalments) >= 2, "this case needs a plan with at least two instalments"

        for instalment in instalments[:2]:
            payments_notices.send_plan_notices(
                plan, as_of=instalment.due_date - timedelta(days=3), actor=dana
            )

        reminders = list(_queue(brazos, source_type="plan", template_code="plan_notice_upcoming"))

    assert len(reminders) == 2, (
        f"two instalments produced {len(reminders)} reminder(s). Keyed on the "
        "PLAN they share one tuple and every reminder after the first is "
        "silently discarded."
    )


def test_cr048_b11__the_receipt_goes_out_on_three_surfaces_of_one_payment(brazos, dana):
    """Print, email and SMS about ONE payment are three rows.

    The CHANNEL is a column in the idempotency key, so the three cannot collide
    by construction — which is exactly what the returned-payment letter does NOT
    have, and why that one keys on the reversing row instead of the original.
    """
    from tests.test_cr048_b6_b10 import _an_occupant  # noqa: PLC0415

    from apps.payments import services as payments_services

    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="2 Sedge Lane", name="Three, Tia")
        recorded = payments_services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("40.00"),
            # BR-TEN-043 — both moments are ARGUMENTS, never a wall clock.
            posted_at=RECEIVED_AT,
            cleared_at=RECEIVED_AT,
            method_code="cash",
        )
        assert recorded.created
        rows = list(_queue(brazos, source_type="payment", source_id=recorded.payment_id))

    by_channel = {row.channel: row.template_code for row in rows}
    assert by_channel == {
        "pdf_print": "receipt",
        "email": "email_payment_receipt",
        "sms": "sms_payment_received",
    }, (
        f"one payment produced {by_channel}. Three documents on three surfaces "
        "are three rows, each pinned to its OWN class — an SMS row pinned to the "
        "print class would render the wrong document."
    )
    for row in rows:
        assert row.event_key == payments_receipts.EVENT_PAYMENT_RECEIVED, (
            "every surface of one receipt names the SAME event, so a utility "
            "switching *Payment received* off stops being in touch about the "
            "payment rather than having to find three rows that mean one thing."
        )
