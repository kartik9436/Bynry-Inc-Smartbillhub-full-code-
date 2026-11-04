# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (bounces + returned mail — the statuses the bad-address
#           flow feeds on)   Screens: S8 · S30
# Rules:    BR-NOT-005 (forward-only lifecycle; retry ×3 with backoff — which is
#           the product's own answer to a TRANSIENT failure and therefore to a
#           SOFT bounce) · BR-NOT-013 (`delivered` and `bounced` are provider
#           facts and nothing in this repo writes one) · BR-NOT-024 (print is
#           the floor on every customer document, so suppressing email never
#           costs a consumer their bill) · CLAUDE.md rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""`DEF-NOT-5626` — the four normalised outcomes, and the split that matters.

WHAT THIS FILE IS ACTUALLY GUARDING, in one sentence: that a HARD bounce and a
SOFT bounce cannot be treated the same way by accident.

SendGrid says `delivered · bounce · deferred · dropped · spamreport ·
unsubscribe`. Postmark says `Delivery · Bounce (with a hard/soft Type on the one
event) · SpamComplaint · SubscriptionChange`. Neither vocabulary may escape its
adapter, so the product sees exactly six words and this file pins them.

⚠ **ASK WHAT WOULD MAKE EACH CASE PASS WRONGLY** (hard-won law 7, habit 2).

  * A test that only asserted `bounced_hard in models.STATUSES` would pass on a
    product that then re-queued it — the STRING existing proves nothing. So the
    cases below exercise `delivery_ops.requeue` and read what it REFUSED.
  * A test that asserted "requeue refused" without checking the sibling would
    pass on a product that refused EVERYTHING. So the soft case runs in the same
    test and asserts the row actually moved back to `queued`.
  * A test that asserted a refusal CODE would pass on a refusal whose sentence
    is empty or wrong. The clerk reads the sentence, so the sentence is
    asserted.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import delivery_ops, dispatcher, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 9, 17, 15, 0, tzinfo=dt_timezone.utc)


def a_row(tenant, **overrides):
    values = dict(
        tenant_id=tenant.id,
        source_type="invoice",
        source_id=uuid.uuid4(),
        channel=models.CHANNEL_EMAIL,
        template_code="bill_residential",
        template_id=uuid.uuid4(),
        template_version=2,
        recipient_address="marta.whitfield@example.com",
        status=models.STATUS_QUEUED,
    )
    values.update(overrides)
    return models.OutboundMessage.objects.create(**values)


# ── the vocabulary itself ───────────────────────────────────────────────────
def test_the_six_normalised_outcomes_are_the_contract_an_adapter_maps_onto():
    """Six words, and every one of them a word the PRODUCT chose.

    `queued` and `sent` are not on this tuple because no provider reports them
    to us, and `bounced` is not on it because it is legacy and is never written
    again — see `apps/notifications/migrations/0018_…` for why no row was
    rewritten into one of the new values.
    """
    assert models.PROVIDER_OUTCOME_STATUSES == (
        "delivered",
        "bounced_hard",
        "bounced_soft",
        "complained",
        "failed",
        "unsubscribed",
    )
    for outcome in models.PROVIDER_OUTCOME_STATUSES:
        assert outcome in models.STATUSES, outcome
    # LEGACY, and deliberately still lawful.
    assert "bounced" in models.STATUSES
    assert "bounced" not in models.PROVIDER_OUTCOME_STATUSES


def test_a_choice_is_not_a_failure__unsubscribed_is_off_the_clerks_failure_list():
    """`unsubscribed` is the one outcome of the six that is not a fault.

    Putting it on a list headed *failures* invites a clerk to undo a consumer's
    own decision. The partial index `ix_outbound_msgs_failed`,
    `selectors._apply_order` and `delivery_ops.failures` all read
    `ATTENTION_STATUSES`, so this one assertion covers all three.
    """
    assert models.STATUS_UNSUBSCRIBED not in models.ATTENTION_STATUSES
    for attention in (
        models.STATUS_FAILED,
        models.STATUS_BOUNCED,
        models.STATUS_BOUNCED_HARD,
        models.STATUS_BOUNCED_SOFT,
        models.STATUS_COMPLAINED,
    ):
        assert attention in models.ATTENTION_STATUSES


# ── THE case this file exists for ───────────────────────────────────────────
def test_a_soft_bounce_retries_and_a_hard_bounce_is_refused_in_the_same_breath(
    brazos, dana, audit_rows
):
    """**The money-adjacent one.** Two rows, two opposite answers, one call.

    A soft bounce is a full mailbox on a Tuesday — `BR-NOT-005`'s retry ×3 is
    the product's own answer to it, so a clerk may put the row back on the
    queue. A hard bounce is a mailbox that does not exist — sending again cannot
    succeed and degrades the reputation every utility on this platform shares.

    ⚠ **PROVED RED FIRST** (hard-won law 7) by putting `STATUS_BOUNCED_HARD`
    back on `delivery_ops.REQUEUEABLE_STATUSES`, which is what a lane
    "simplifying" the two values back into one would do. Run against real
    PostgreSQL 16, the transcript read, verbatim:

        __ test_a_soft_bounce_retries_and_a_hard_bounce_is_refused_in_the_same_breath __
        E   AssertionError: assert ('01a0af5f-aa...f7cce995920f') == ('01a0af5f-aa...8fd3a9cf9ec',)
        E     Left contains one more item: '01a0af5f-aaa3-7e32-ad69-f7cce995920f'
        1 failed, 5 passed, 4 warnings in 192.46s

    — **both rows re-queued**, the hard bounce among them, no refusal raised,
    and the other five cases in this file went green over it. That is the whole
    point: the vocabulary assertions above CANNOT see this. Only a case that
    actually calls `requeue` and reads what came back can.
    """
    with tenant_ctx(brazos):
        soft = a_row(brazos, status=models.STATUS_BOUNCED_SOFT, attempts=1)
        hard = a_row(brazos, status=models.STATUS_BOUNCED_HARD, attempts=1)

        outcome = delivery_ops.requeue(message_ids=(soft.pk, hard.pk), actor=dana)

        assert outcome.requeued == (str(soft.pk),)
        assert len(outcome.refused) == 1

        refusal = outcome.refused[0]
        assert refusal["message_id"] == str(hard.pk)
        assert refusal["code"] == "status_not_requeueable"
        # The sentence a CLERK reads, not a log line. It has to say why sending
        # again is not merely pointless, and it has to say the customer is not
        # losing their bill.
        assert "HARD bounced" in refusal["detail"]
        assert "does not exist" in refusal["detail"]
        assert "print is the floor" in refusal["detail"]

        soft.refresh_from_db()
        hard.refresh_from_db()
        assert soft.status == models.STATUS_QUEUED
        assert soft.batch_id is None
        # UNTOUCHED. A refused row must not be half-moved.
        assert hard.status == models.STATUS_BOUNCED_HARD


def test_a_complaint_and_an_unsubscribe_are_refused_too_and_each_says_its_own_reason(
    brazos, dana, audit_rows
):
    """Three statuses cannot re-queue, for three different reasons.

    A clerk who is told *"status 'complained' cannot re-queue"* learns nothing;
    a clerk who is told that sending again is the fastest way to get a sender
    blocked learns what to do instead. ⚠ Asserting the CODE alone would pass on
    the generic sentence this branch used to carry.
    """
    with tenant_ctx(brazos):
        complained = a_row(brazos, status=models.STATUS_COMPLAINED)
        unsubscribed = a_row(brazos, status=models.STATUS_UNSUBSCRIBED)

        outcome = delivery_ops.requeue(message_ids=(complained.pk, unsubscribed.pk), actor=dana)

    assert outcome.requeued == ()
    by_id = {refusal["message_id"]: refusal["detail"] for refusal in outcome.refused}
    assert "marked our email as spam" in by_id[str(complained.pk)]
    assert "used the unsubscribe link" in by_id[str(unsubscribed.pk)]
    # Neither sentence may be the other's, and neither may be the generic one.
    assert by_id[str(complained.pk)] != by_id[str(unsubscribed.pk)]
    for detail in by_id.values():
        assert "cannot re-queue." not in detail


def test_the_lifecycle_lets_a_complaint_arrive_after_a_delivery_and_a_bounce_never_does(
    brazos,
):
    """A person must OPEN the mail to mark it spam, so `delivered → complained`
    is the ordinary order of events and refusing it would leave a real report
    with nowhere to go.

    A mailbox cannot both accept and refuse the same message, so
    `delivered → bounced_hard` stays refused: a provider telling us both is a
    provider we have misread, and the refusal is how we find out instead of
    overwriting a delivery.
    """
    dispatcher.forward_only(models.STATUS_DELIVERED, models.STATUS_COMPLAINED)
    dispatcher.forward_only(models.STATUS_DELIVERED, models.STATUS_UNSUBSCRIBED)
    with pytest.raises(dispatcher.ForwardOnlyViolation):
        dispatcher.forward_only(models.STATUS_DELIVERED, models.STATUS_BOUNCED_HARD)


def test_the_failures_list_shows_a_hard_bounce_and_hides_an_unsubscribe(brazos):
    """`delivery_ops.failures` reads `ATTENTION_STATUSES`, so this is the screen
    half of the two vocabulary assertions above — a clerk sees the bounce and is
    not invited to undo the choice.
    """
    with tenant_ctx(brazos):
        hard = a_row(brazos, status=models.STATUS_BOUNCED_HARD)
        unsubscribed = a_row(brazos, status=models.STATUS_UNSUBSCRIBED)
        shown = {str(row.pk) for row in delivery_ops.failures()}

    assert str(hard.pk) in shown
    assert str(unsubscribed.pk) not in shown


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5626 (12-governance/10-defect-log.csv) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-005 + BR-NOT-013 + BR-NOT-024 · apps/notifications/models.py (STATUSES, PROVIDER_OUTCOME_STATUSES, ATTENTION_STATUSES) · apps/notifications/delivery_ops.py REQUEUEABLE_STATUSES · apps/notifications/dispatcher.py ALLOWED_TRANSITIONS
# generated: 2026-09-17 by an AI lane (SendGrid/Postmark gap 3)
# checklist: A✔ B=deferred(no frontend half in this slice) C✔ D=deferred(no API call) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST on real PostgreSQL 16 — `bounced_hard` put back on REQUEUEABLE_STATUSES; `1 failed, 5 passed` with `AssertionError: ... Left contains one more item`, i.e. BOTH rows re-queued. Transcript quoted verbatim in the case's own docstring and in the lane report.
# exceptions: NOTHING WRITES THE FOUR VALUES ON THIS DEPLOYMENT (BR-NOT-013 — no email adapter with a feedback door exists), so every row above is CONSTRUCTED. That is stated rather than implied: these cases prove the product's ANSWER to an outcome, never that an outcome can arrive.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
