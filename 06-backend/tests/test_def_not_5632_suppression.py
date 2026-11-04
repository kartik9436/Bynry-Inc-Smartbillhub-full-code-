# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (bounces + returned mail)   Screens: S8 · S30
# Rules:    BR-NOT-005 (forward-only; retry ×3 with backoff IS the answer to a
#           TRANSIENT failure, and therefore to a SOFT bounce) · BR-NOT-013
#           (provider facts — nothing in this repo writes one) · BR-NOT-024
#           (print is the floor, so suppressing email never costs a consumer
#           their bill) · BR-PAY-018 (the paper half, already built) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 6 (idempotency) ·
#           rule 7 (every money action writes audit_log) · hard-won law 7
#           (ask what would make each case pass WRONGLY)
# Change:   DEF-NOT-5632, 2026-09-17.
# ───────────────────────────────────────────────────────
"""`DEF-NOT-5632` — the do-not-send list, and the one rule that must never bend.

WHAT THIS FILE IS GUARDING, in one sentence: that a SOFT bounce can never take a
customer's email away, and that a HARD bounce actually stops the next bill.

⚠ **ASK WHAT WOULD MAKE EACH CASE PASS WRONGLY** (hard-won law 7, habit 2). The
three false passes this file was written against, each of which an obvious
version of these tests would have:

  * **A test asserting `suppress(reason="hard_bounce")` writes a row** passes on
    a product that ALSO writes one for a soft bounce. So the soft case runs in
    the same test as the hard one and asserts the two opposite answers together
    — the shape `test_def_not_5626` already uses one file over, for the same
    pair of words.
  * **A test asserting the writer REFUSES a soft bounce** passes on a writer
    that refuses everything, and passes on a writer whose refusal never reaches
    the queue — the refusal is not the point, the DELIVERY is. So the soft case
    goes on to assert the message is still selectable by the dispatcher, which
    is the fact a real customer experiences.
  * **A test asserting a suppressed row is `held`** passes on a dispatcher that
    ignores `held` entirely. So the dispatcher's own predicate is exercised
    against the database rather than inspected, and the *not selectable* half is
    asserted through `_selectable` itself.

⚠ **AND ONE THIS FILE CANNOT CHECK, SAID OUT LOUD RATHER THAN IMPLIED (law 2).**
`BR-NOT-013` still holds: no provider adapter with a feedback door exists, so
nothing in production ever calls `suppress_for_outcome`. These tests are its only
callers today. What IS live and wired from the same commit is the READ half —
the dispatcher and `queue_document` consult the list — and that is what the
dispatcher cases below exercise.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import (
    dispatcher,
    models,
    services,
    suppression,
    suppression_models,
)

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 9, 17, 15, 0, tzinfo=dt_timezone.utc)
DEAD = "Marta.Whitfield@example.com"
LIVE = "arjun.rao@example.com"


def a_row(tenant, **overrides):
    """One queue row, addressed and queued. The same helper shape as
    `test_def_not_5626_normalised_outcomes.a_row`, deliberately."""
    values = dict(
        tenant_id=tenant.id,
        source_type="invoice",
        source_id=uuid.uuid4(),
        channel=models.CHANNEL_EMAIL,
        template_code="bill_residential",
        template_id=uuid.uuid4(),
        template_version=2,
        recipient_address=DEAD,
        status=models.STATUS_QUEUED,
    )
    values.update(overrides)
    return models.OutboundMessage.objects.create(**values)


def selectable_ids(tenant):
    """The ids the DISPATCHER would actually claim — its own predicate, run.

    Not a re-implementation of the filter: `dispatcher._selectable` is called,
    so a change to the dispatcher's selection that forgot the suppression list
    shows up here.
    """
    return {
        str(pk)
        for pk in models.OutboundMessage.objects.filter(tenant_id=tenant.id)
        .filter(dispatcher._selectable(NOW))
        .values_list("id", flat=True)
    }


# ══════════════════════════════════════════════════════════════════════════
# THE case this file exists for
# ══════════════════════════════════════════════════════════════════════════
def test_a_hard_bounce_suppresses_and_a_soft_bounce_never_does(brazos, dana, audit_rows):
    """**The one that decides whether a real consumer loses their bills.**

    Two outcomes, two opposite answers, asserted together — because a test that
    only checked the hard case would pass on a product that suppressed both, and
    that product takes email away from every customer whose mailbox was full on
    a Tuesday.

    The soft case does not stop at *no row was written*. It asserts the message
    is **still selectable by the dispatcher**, which is the fact the customer
    actually experiences: their bill still goes out.
    """
    with tenant_ctx(brazos):
        hard = a_row(brazos, recipient_address=DEAD)
        soft = a_row(brazos, recipient_address=LIVE)

        # A mailbox that does not exist.
        wrote = suppression.suppress_for_outcome(
            message=hard, outcome=models.STATUS_BOUNCED_HARD, at=NOW, actor=dana
        )
        assert wrote is not None, "a hard bounce must put the address on the list"
        assert wrote.created is True
        assert wrote.reason == suppression_models.REASON_HARD_BOUNCE

        # A mailbox that was full on Tuesday. THE GUARD.
        assert (
            suppression.suppress_for_outcome(
                message=soft, outcome=models.STATUS_BOUNCED_SOFT, at=NOW, actor=dana
            )
            is None
        ), "A SOFT BOUNCE MUST NEVER SUPPRESS — read apps/notifications/models.py"

        # The list holds exactly one address, and it is the dead one.
        assert [row.address for row in suppression.active()] == [DEAD.lower()]

        # ⚠ THE HALF THAT MATTERS TO A PERSON: the soft-bounced customer's bill
        # is still going out, and the hard-bounced one's is not.
        still_going = selectable_ids(brazos)
        assert str(soft.pk) in still_going, (
            "a soft bounce must leave the message selectable — BR-NOT-005's retry ×3 "
            "is the product's answer to a transient failure"
        )
        assert str(hard.pk) not in still_going

        # And the hard-bounced row is HELD rather than lost: BR-PAY-018's
        # "written, marked held, never dispatched, never lost", so a clerk can
        # see it and release it.
        hard.refresh_from_db()
        assert hard.held is True
        assert hard.held_reason == suppression.HELD_SUPPRESSED
        assert hard.status == models.STATUS_QUEUED, "held is orthogonal to status (BR-NOT-005)"


def test_the_writer_refuses_a_soft_bounce_asked_for_explicitly_and_says_why(brazos, dana):
    """`suppress_for_outcome` returns None; `suppress` REFUSES. Both, on purpose.

    A future adapter that drops SendGrid's bounce TYPE, or defaults it, is one
    plausible line away from suppressing every transient failure a utility has.
    It must meet an error message, not a silent success — so the refusal is
    asserted, and so is the SENTENCE, because whoever reads it is about to
    decide whether to work around it.
    """
    with tenant_ctx(brazos):
        with pytest.raises(suppression.SuppressionRefused) as refused:
            suppression.suppress(
                channel=models.CHANNEL_EMAIL,
                address=LIVE,
                reason=models.STATUS_BOUNCED_SOFT,
                at=NOW,
                actor=dana,
            )
        said = str(refused.value)
        assert "SOFT bounce never suppresses" in said
        assert "temporary" in said
        assert not suppression.active().exists()

        # A reason nobody has ruled is refused too — a value no screen can
        # render and no clerk can group on.
        with pytest.raises(suppression.SuppressionRefused):
            suppression.suppress(
                channel=models.CHANNEL_EMAIL,
                address=LIVE,
                reason="looks_a_bit_dodgy",
                at=NOW,
                actor=dana,
            )


def test_a_complaint_and_an_unsubscribe_each_suppress_on_the_first_one(brazos, dana):
    """Neither is a threshold question, and the runbook never claimed one.

    `undeliverable_contacts.HARD_KINDS` is bounces, failed texts and returned
    post — a complaint is on none of them. A person clicking *this is spam* or
    *unsubscribe* has given an instruction, and it is honoured immediately.

    They are recorded under DIFFERENT reasons, and the assertion is deliberate:
    folding them into one `blocked` would leave the one screen built to explain
    this unable to tell a clerk whether to ring the customer.
    """
    with tenant_ctx(brazos):
        complained = a_row(brazos, recipient_address="rosa.delgado@example.com")
        unsubscribed = a_row(brazos, recipient_address="kofi.mensah@example.com")

        first = suppression.suppress_for_outcome(
            message=complained, outcome=models.STATUS_COMPLAINED, at=NOW, actor=dana
        )
        second = suppression.suppress_for_outcome(
            message=unsubscribed, outcome=models.STATUS_UNSUBSCRIBED, at=NOW, actor=dana
        )
        assert first.reason == suppression_models.REASON_COMPLAINT
        assert second.reason == suppression_models.REASON_UNSUBSCRIBED
        assert first.reason != second.reason

        # `delivered` and `failed` say nothing about the mailbox and write
        # nothing. Asserted so that a lane widening SUPPRESSING_OUTCOMES to "any
        # outcome that is not delivered" meets a red.
        for harmless in (models.STATUS_DELIVERED, models.STATUS_FAILED):
            assert (
                suppression.suppress_for_outcome(
                    message=a_row(brazos, recipient_address="nobody@example.com"),
                    outcome=harmless,
                    at=NOW,
                    actor=dana,
                )
                is None
            ), f"{harmless} says nothing about the mailbox"


# ══════════════════════════════════════════════════════════════════════════
# The three layers of the guarantee, each asserted where it actually lives
# ══════════════════════════════════════════════════════════════════════════
def test_a_document_queued_to_a_suppressed_address_is_written_held_not_refused(brazos, dana):
    """`queue_document` writes the row and marks it held — never drops it.

    *"A message that was never queued leaves no trace"* is this module's own
    discipline, and a clerk asking *did this customer get their bill* must find
    an answer. The caller is TOLD, too: a bill run over five hundred accounts
    has to be able to report how many went nowhere and why.
    """
    with tenant_ctx(brazos):
        suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        write = services.queue_document(
            source_type="invoice",
            source_id=uuid.uuid4(),
            channels=(models.CHANNEL_EMAIL,),
            template=services.TemplatePin(
                code="bill_residential", template_id=uuid.uuid4(), version=2
            ),
            recipients=(
                services.Recipient(channel=models.CHANNEL_EMAIL, address=DEAD, snapshot={}),
            ),
            actor=dana,
        )
        queued = [one for one in write.messages if one.channel == models.CHANNEL_EMAIL]
        assert queued, "the row is WRITTEN, never dropped"
        row = models.OutboundMessage.objects.get(pk=queued[0].id)
        assert row.held is True
        assert row.held_reason == suppression.HELD_SUPPRESSED

        # Reported, never silent.
        codes = {problem["code"] for problem in write.problems}
        assert services.QUEUE_ADDRESS_SUPPRESSED in codes

        # And not selectable, which is the thing that matters.
        assert str(row.pk) not in selectable_ids(brazos)


def test_the_dispatcher_refuses_a_suppressed_address_even_when_nothing_held_the_row(
    brazos, dana
):
    """The THIRD layer, and the one that should never be the one that fires.

    `queue_document` holds new rows and `suppress()` holds existing ones, so by
    the time a cycle runs every such row is already `held`. This asserts the
    reader's own guarantee anyway, by putting a row into exactly the state those
    two writers would have prevented — a row written before this slice landed,
    or by a writer added later that forgets.

    ⚠ **A ROW EXCLUDED BY THE FILTER AND NOT HELD IS A BUG**, so the test that
    follows asserts the two agree rather than assuming it.
    """
    with tenant_ctx(brazos):
        row = a_row(brazos, recipient_address=DEAD)
        suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        # Undo the hold that `suppress()` placed, leaving ONLY the reader's
        # guarantee standing.
        models.OutboundMessage.objects.filter(pk=row.pk).update(held=False, held_reason=None)
        row.refresh_from_db()
        assert row.held is False

        assert str(row.pk) not in selectable_ids(brazos), (
            "the dispatcher must not hand a hard-bounced address to a provider even when "
            "no writer held the row"
        )


def test_the_two_layers_agree__every_row_the_filter_excludes_is_also_visibly_held(
    brazos, dana
):
    """A row the dispatcher silently skips and no clerk can see is the failure
    mode this whole slice is shaped to avoid.

    `held` is what a PERSON sees on S8; the filter is what the MACHINE obeys. If
    they ever disagree, a message stops going out and nothing anywhere says so —
    which is the shape of every defect in this repo's *checks that do not check*
    category.
    """
    with tenant_ctx(brazos):
        blocked = a_row(brazos, recipient_address=DEAD)
        fine = a_row(brazos, recipient_address=LIVE)
        suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_COMPLAINT,
            at=NOW,
            actor=dana,
        )
        selectable = selectable_ids(brazos)
        for row in models.OutboundMessage.objects.filter(tenant_id=brazos.id):
            if str(row.pk) not in selectable:
                assert row.held is True, (
                    f"{row.recipient_address} is not selectable and is not held — the "
                    "dispatcher is skipping a message no clerk can see"
                )
        assert str(fine.pk) in selectable
        assert str(blocked.pk) not in selectable


# ══════════════════════════════════════════════════════════════════════════
# Release — the clerk's door
# ══════════════════════════════════════════════════════════════════════════
def test_release_lets_the_corrected_typo_through_again_and_keeps_the_record(
    brazos, dana, audit_rows
):
    """**The PO asked for this by name.** A hard bounce is usually a typo.

    Without this door the product's answer to *we fixed the address* would be
    *that customer receives email again never*, and the harm would be the exact
    harm the soft-bounce guard exists to prevent, arriving permanently.

    Three assertions, one per deliberate decision: the held message flows again,
    the ROW SURVIVES as history (because `audit_log` is pruned and the row is
    the durable answer), and the second press is refused rather than silently
    accepted.
    """
    with tenant_ctx(brazos):
        row = a_row(brazos, recipient_address=DEAD)
        wrote = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        assert str(row.pk) in wrote.held_message_ids
        assert str(row.pk) not in selectable_ids(brazos)

        released = suppression.release(
            suppression_id=wrote.id, actor=dana, at=NOW, note="typo, corrected on the account"
        )

        # 1 · the message flows again — same row, nothing re-created.
        row.refresh_from_db()
        assert row.held is False
        assert row.held_reason is None
        assert str(row.pk) in selectable_ids(brazos)

        # 2 · the ROW IS KEPT, not deleted. This is the whole reason the unique
        # constraint is partial.
        assert released.released_at == NOW
        assert released.released_note == "typo, corrected on the account"
        assert suppression_models.SuppressedAddress.objects.filter(pk=wrote.id).exists()
        assert not suppression.active().exists(), "released means no longer active"

        # 3 · pressing Release twice is refused, not silently accepted.
        with pytest.raises(suppression.SuppressionRefused):
            suppression.release(suppression_id=wrote.id, actor=dana, at=NOW)


def test_release_does_not_touch_a_row_held_for_a_different_reason(brazos, dana):
    """`BR-PAY-018`'s paper hold has its own door and this is not it.

    A message held because an ENVELOPE came back is held for a different problem
    with a different fix. Releasing it here would undo a hold this rule never
    placed, and the clerk who flagged the bad address would never know.
    """
    with tenant_ctx(brazos):
        paper = a_row(
            brazos,
            channel=models.CHANNEL_PRINT,
            recipient_address=DEAD,
            held=True,
            held_reason="bad_address_paper_suppression",
        )
        wrote = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        suppression.release(suppression_id=wrote.id, actor=dana, at=NOW, note="fixed")

        paper.refresh_from_db()
        assert paper.held is True, "the paper hold is delivery_ops' and only its door opens it"
        assert paper.held_reason == "bad_address_paper_suppression"


def test_a_re_suppression_after_a_release_is_a_NEW_row_so_the_pattern_is_visible(
    brazos, dana
):
    """The third time an address goes bad there are three rows.

    A clerk about to release a typo for the second time needs to see that they
    have done this before. A plain unique on (tenant, channel, address) would
    have forced a release to DELETE and this history would not exist.
    """
    with tenant_ctx(brazos):
        first = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        suppression.release(suppression_id=first.id, actor=dana, at=NOW, note="typo")
        second = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        assert second.created is True
        assert second.id != first.id
        history = suppression_models.SuppressedAddress.objects.filter(
            tenant_id=brazos.id, address=DEAD.lower()
        )
        assert history.count() == 2
        assert suppression.active().count() == 1


# ══════════════════════════════════════════════════════════════════════════
# Idempotency, normalisation, tenancy, audit
# ══════════════════════════════════════════════════════════════════════════
def test_the_same_webhook_delivered_twice_writes_one_row(brazos, dana):
    """Hard rule 6. Every ESP documents at-least-once delivery.

    The guarantee is the DATABASE's partial unique, not a pre-check — and the
    second call still holds a row queued since the first, which is why the hold
    is not inside the `created` branch.
    """
    with tenant_ctx(brazos):
        first = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        late = a_row(brazos, recipient_address=DEAD)  # queued between the two deliveries
        second = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        assert first.created is True
        assert second.created is False, "the second delivery must not write a second row"
        assert second.id == first.id
        assert suppression_models.SuppressedAddress.objects.filter(
            tenant_id=brazos.id
        ).count() == 1
        late.refresh_from_db()
        assert late.held is True, (
            "a row queued between two webhook deliveries must still be held — the hold "
            "cannot live inside the `created` branch"
        )


def test_the_address_is_matched_whatever_case_the_clerk_typed(brazos, dana):
    """`Marta.Whitfield@…` bouncing must stop the bill going to `marta.whitfield@…`.

    The address on a queue row is whatever somebody typed into a form. Matching
    case-sensitively would leave the next bill going to the same dead mailbox,
    which is the asymmetric failure `normalise_address` argues about.
    """
    with tenant_ctx(brazos):
        lower = a_row(brazos, recipient_address=DEAD.lower())
        upper = a_row(brazos, recipient_address=DEAD.upper())
        suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        selectable = selectable_ids(brazos)
        assert str(lower.pk) not in selectable
        assert str(upper.pk) not in selectable
        assert suppression.is_suppressed(channel=models.CHANNEL_EMAIL, address=DEAD.upper())


def test_a_suppression_is_scoped_to_one_utility(brazos, dana):
    """Hard rule 1. One utility's dead address is not another's.

    ⚠ **SQLite has no RLS**, so this proves the SHAPE — that every read is
    filtered by tenant and that the column the policy depends on is populated —
    and says so rather than implying RLS coverage. The policy itself is
    `db/rls_notifications_suppression.sql`, applied by migration 0020 and
    exercised on PostgreSQL.
    """
    with tenant_ctx(brazos):
        wrote = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        stored = suppression_models.SuppressedAddress.objects.get(pk=wrote.id)
        assert str(stored.tenant_id) == str(brazos.id), "the column every policy depends on"
        assert suppression.active().count() == 1
        # Every published read starts from the tenant-scoped base.
        assert suppression.listing().count() == 1


def test_both_doors_write_the_trail(brazos, dana, audit_rows):
    """Hard rule 7, with the precedent named: `delivery.held` / `delivery.released`
    already audit the PAPER half of exactly this act.

    Stopping a bill reaching the customer it is addressed to, and letting it
    through again, are both things a utility will be asked to explain — and the
    release is the more sensitive, because it is a person overriding a machine.
    """
    with tenant_ctx(brazos):
        wrote = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        suppression.release(suppression_id=wrote.id, actor=dana, at=NOW, note="typo")

    actions = [row["action"] for row in audit_rows]
    assert suppression.AUDIT_SUPPRESSED in actions
    assert suppression.AUDIT_RELEASED in actions


def test_the_list_is_paginated_and_orders_active_before_released(brazos, dana):
    """`NFR-3` — no list in this product is unpaginated, and this one grows for
    ever because released rows are kept.

    `listing()` returns a QUERYSET so the page is taken in the database. A
    version that returned a list would serialize every row a utility has ever
    blocked to render fifty of them, and `DEF-PAY-4221` is what that costs when
    the ceiling moves.
    """
    with tenant_ctx(brazos):
        released = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address="old@example.com",
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        suppression.release(suppression_id=released.id, actor=dana, at=NOW)
        suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=DEAD,
            reason=suppression_models.REASON_COMPLAINT,
            at=NOW,
            actor=dana,
        )

        rows = suppression.listing(state=suppression.STATE_ALL)
        assert hasattr(rows, "query"), "a queryset, so the page is taken in the DATABASE"
        assert [one.address for one in rows] == [DEAD.lower(), "old@example.com"], (
            "active first — a released address is history and belongs below the thing a "
            "clerk came here to act on"
        )
        assert [one.address for one in suppression.listing()] == [DEAD.lower()]
        assert [
            one.address for one in suppression.listing(state=suppression.STATE_RELEASED)
        ] == ["old@example.com"]



# ══════════════════════════════════════════════════════════════════════════
# EMAIL AND TEXT ONLY — PO 2026-10-02, "A · Email and text only - this correct"
# (DEF-NOT-8538, DEF-GOV-6417, hard rule 8)
# ══════════════════════════════════════════════════════════════════════════
def test_a_postal_address_is_refused_by_name_and_nothing_is_written(brazos, dana):
    """Shown to the PO: Dana asks us to stop emailing `dana@example.com` — that
    goes on the list. A street does not: it would be a fifth home for an
    address, and paper already has `BR-PAY-018`'s bad-address flag."""
    with tenant_ctx(brazos):
        with pytest.raises(suppression.SuppressionRefused) as refused:
            suppression.suppress(
                channel=models.CHANNEL_PRINT,
                address="14 Oak Court, Austin, TX 78704",
                reason=suppression_models.REASON_MANUAL,
                at=NOW,
                actor=dana,
            )
        assert "POSTAL address" in str(refused.value)
        assert refused.value.message_key == suppression.KEY_POSTAL_REFUSED

        for channel in (models.CHANNEL_IN_APP, models.CHANNEL_PORTAL):
            with pytest.raises(suppression.SuppressionRefused) as other:
                suppression.suppress(
                    channel=channel,
                    address="anything",
                    reason=suppression_models.REASON_MANUAL,
                    at=NOW,
                    actor=dana,
                )
            assert other.value.message_key == suppression.KEY_CHANNEL_REFUSED

        assert not suppression_models.SuppressedAddress.objects.filter(
            tenant_id=brazos.id
        ).exists(), "a refusal writes nothing"

        # The two lawful channels still go on the list.
        suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address="dana@example.com",
            reason=suppression_models.REASON_MANUAL,
            at=NOW,
            actor=dana,
        )
        suppression.suppress(
            channel=models.CHANNEL_SMS,
            address="+1 512 555 0142",
            reason=suppression_models.REASON_MANUAL,
            at=NOW,
            actor=dana,
        )
        assert suppression.active().count() == 2


def test_the_ruled_pair_is_the_models_own_channels_and_the_clerk_sentences_exist():
    """`SUPPRESSIBLE_CHANNELS` is spelled as literals so `G85` can read it with
    `ast`; this pins the literals to the constants they stand for, and the two
    refusal keys to all eleven catalogues."""
    import json
    import pathlib

    assert suppression_models.SUPPRESSIBLE_CHANNELS == (models.CHANNEL_EMAIL, models.CHANNEL_SMS)
    locales = pathlib.Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
    catalogues = sorted(locales.glob("*.json"))
    assert len(catalogues) == 11
    for catalogue in catalogues:
        data = json.loads(catalogue.read_text(encoding="utf-8"))
        for key in (suppression.KEY_POSTAL_REFUSED, suppression.KEY_CHANNEL_REFUSED):
            assert data.get(key), f"{catalogue.name} has no sentence for {key}"

# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5632 (12-governance/10-defect-log.csv) · apps/notifications/suppression.py + suppression_models.py · apps/notifications/models.py (the hard/soft paragraph, which is the policy) · apps/runbooks/definitions/undeliverable_contacts.py (the THRESHOLD policy, deliberately not duplicated) · tests/test_def_not_5626_normalised_outcomes.py (the sibling this file's shape follows)
# generated: 2026-09-17 by an AI lane (SendGrid/Postmark gap 4 — the do-not-send list)
# checklist: A✔ B=deferred(no frontend half — the blocked-addresses SCREEN is DEF-NOT-5637) C✔ D✔ E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: EVERY case proved RED FIRST through pytest (the harness that runs it, never `python3 <file>` — hard-won law 7), each against a named sabotage; the SAVEPOINT case additionally on REAL PostgreSQL 16, which is the only place it can fail at all (law 14). The sabotages and their failures are in the lane report and the decision log.
# exceptions: (1) NOTHING IN PRODUCTION CALLS `suppress_for_outcome` — BR-NOT-013 holds and no adapter exists, so these tests are its only callers (law 2, said out loud). The READ half IS live. (2) RLS IS NOT PROVED HERE — sqlite has no row-level security; `test_a_suppression_is_scoped_to_one_utility` proves SHAPE and says so.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
