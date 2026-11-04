# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 (`outbound_messages` — the ONE write path) ×
#           US-NOT-017 (SET-12 / SET-12D, the rule the queue never read)
#           CR-048 wave A, task A1   Screens: S8 · SET-12 · SET-12D
# Rules:    BR-NOT-017 (ONE HOME for every notification rule) · BR-NOT-018 (an
#           event with no trigger is drawn and REFUSED by name) · BR-BIL-036
#           (PRINT is the primary channel and the FLOOR — a rule may never
#           remove it) · BR-BIL-016 (one delivery record per document per
#           channel) · BR-NOT-005 (queue only; nothing here sends) ·
#           BR-NOT-013 (no provider adapter on any channel) · BR-TEN-043 (no
#           wall clock is read; dates are parameters) · CLAUDE.md rule 1
#           (tenant scoping) · rule 6 (idempotency) · rule 7 (audited)
# ───────────────────────────────────────────────────────
"""CR-048's headline finding, as code: **the queue never read the rule.**

The CR states it in one sentence — *"switching 'Bill ready — email' off on the
settings screen changes nothing at all"* — and the mechanism was that
`services.queue_document` took its channel list from whichever module called it
and added only the print floor. `notification_rules` and
`notification_rule_channels` were written, editable, audited and **read by
nobody on the write path.**

FOUR THINGS THESE CASES DEFEND, and each is one of A1's four requirements:

  1. **A channel the rule switched OFF is not queued** even when the caller asks
     for it. That is the whole point of the task, and it is the case that was
     RED before the join existed.
  2. **The print floor still wins.** `CHANNEL_FLOOR_BY_SOURCE` is BR-BIL-036
     made structural; a tenant's rule may switch off what a tenant may switch
     off, and paper on a bill is not that.
  3. **A caller that names no event is byte-identically unaffected.** Most
     writers still pass a source type and no event (wiring them is CR-048 wave
     B), so the no-event path must be exactly what shipped. ⚠ Read
     `test_cr048_a1__a_caller_that_names_no_event_still_queues_a_switched_off_channel`
     twice: it asserts the DEFECT still happens, deliberately, because until
     wave B feeds an event key that IS today's behaviour and pretending
     otherwise would hide how much of the CR is still to come.
  4. **A channel with no published template cannot be switched on** — already
     enforced in `rule_service._apply_channel_changes` and NOT duplicated here;
     the case below proves that guard still fires and that the join cannot
     route around it, because the join only ever REMOVES channels.

NOTHING HERE SENDS. Every row rests `queued`; BR-NOT-013 is untouched.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.notifications import models, rule_service, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

A_PIN = services.TemplatePin(
    code="bill_residential", template_id=uuid4(), version=3, language="en-US"
)


def an_account(actor, tenant, *, account_no="ACC-4801"):
    """A minimal account — the same shape `test_us_not_001_queue_write.py` uses.

    Built through the ORM rather than through customers' activation path: these
    cases are about which CHANNELS a write path chooses, not about how an
    account comes to exist.
    """
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line="4801 Cedar Bayou Rd")
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    status = customer_models.AccountStatus.objects.filter(tenant=tenant).first()
    account_type = customer_models.AccountType.objects.first()
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=status,
        account_type=account_type,
        account_no=account_no,
    )


def switch_channel(actor, event_key, channel, *, on):
    """Do to the rule exactly what a System Admin does on SET-12D.

    Through `rule_service.update_rule` — the ONE write path into the rule
    tables — rather than through the ORM, so these cases exercise the same
    stored state the screen produces and cannot drift from it.
    """
    return rule_service.update_rule(
        event_key=event_key, actor=actor, channels={channel: {"enabled": on}}
    )


# ── 1 · THE POINT OF THE TASK ──────────────────────────────────────────────
def test_cr048_a1__a_channel_the_rule_switched_off_is_not_queued(brazos, dana):
    """CR-048's headline, reproduced and then closed.

    A System Admin switches *Bill ready — email* off. The bill run still asks
    for email, because billing asks for whatever the account elected — and the
    utility's answer is that this utility does not email bills.

    The SMS row is asserted alongside so the case cannot pass by suppressing
    everything: the rule is a per-channel switch, not an off button.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        switch_channel(dana, "bill_ready", models.CHANNEL_EMAIL, on=False)

        write = services.queue_document(
            source_type="invoice",
            source_id=uuid4(),
            channels=(models.CHANNEL_EMAIL, models.CHANNEL_SMS),
            template=A_PIN,
            account_id=account.pk,
            event_key="bill_ready",
            actor=dana,
        )

    assert models.CHANNEL_EMAIL not in write.channels
    assert models.CHANNEL_SMS in write.channels
    # …and the suppression is REPORTED, never silent: a bill run's report must
    # be able to say why a customer who has an email address got no email.
    suppressed = [
        problem
        for problem in write.problems
        if problem["code"] == services.QUEUE_CHANNEL_SWITCHED_OFF
    ]
    assert suppressed and suppressed[0]["channel"] == models.CHANNEL_EMAIL
    assert suppressed[0]["event_key"] == "bill_ready"
    # …and it says what to DO about it, in a sentence with no ids in it.
    assert "Settings → Notifications" in suppressed[0]["detail"]


def test_cr048_a1__the_switched_off_channel_leaves_no_row_at_all(brazos, dana):
    """Not queued means NOT QUEUED — no row, not a row with a reason.

    The distinction matters because this module's whole discipline is that an
    absence is RECORDED (`unavailable_reason`) rather than skipped. That rule is
    about a recipient the platform could not address; this is a utility saying
    *do not send this*, and a row would be a message waiting for a dispatcher
    that must never pick it up.
    """
    invoice_id = uuid4()
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        switch_channel(dana, "bill_ready", models.CHANNEL_EMAIL, on=False)
        services.queue_document(
            source_type="invoice",
            source_id=invoice_id,
            channels=(models.CHANNEL_EMAIL,),
            template=A_PIN,
            account_id=account.pk,
            event_key="bill_ready",
            actor=dana,
        )
        rows = models.OutboundMessage.objects.filter(source_id=invoice_id)
        assert set(rows.values_list("channel", flat=True)) == {models.CHANNEL_PRINT}


# ── 2 · THE PRINT FLOOR STILL WINS ─────────────────────────────────────────
def test_cr048_a1__a_rule_can_never_remove_the_print_floor(brazos, dana):
    """BR-BIL-036 is not a tenant setting, and the join must not make it one.

    `disconnect_notice` is the one event in the catalogue that carries a
    `pdf_print` toggle at all, so it is the only way to ask this question
    today — and the disconnection letter is exactly the document that makes the
    answer matter, because it is a legal instrument before it is a message.

    ⚠ **THE PAIRING USED TO BE SYNTHETIC AND IS NOW THE REAL CASE.** This read
    `channel_decision("invoice", …, event_key="disconnect_notice")` with the
    docstring *"`invoice` is the only source kind with a floor, so it is the
    only way to put a rule's OFF switch and the floor on the same channel"* —
    true when it was written and false since BR-NOT-024 (PO 2026-08-29). A
    disconnect notice is a `notice`, `notice` now has the floor, and the case
    can be asked of the document it was always about. What is defended is
    unchanged: the ORDER of the two steps, intersect then floor.
    """
    with tenant_ctx(brazos):
        switch_channel(dana, "disconnect_notice", models.CHANNEL_PRINT, on=False)

        decision = services.channel_decision(
            "notice", (models.CHANNEL_PRINT,), event_key="disconnect_notice"
        )
    assert decision.channels == (models.CHANNEL_PRINT,), (
        "the floor is applied AFTER the rule, not before"
    )
    assert decision.suppressed == (models.CHANNEL_PRINT,)
    # The override is NAMED. A floor that silently outranked a utility's own
    # setting would be right and unexplainable, which is its own defect.
    assert decision.floor_overrode_rule == (models.CHANNEL_PRINT,)


def test_cr048_a1__the_floor_survives_an_event_switched_off_entirely(brazos, dana):
    """An event switched off suppresses every channel the tenant controls, and
    the floor is not one of them.

    A utility that switches *Bill ready* off has said "stop notifying customers
    that a bill is ready". It has not said "stop billing", and it cannot say
    "stop printing" here — BR-BIL-036 is a platform rule about bills, and this
    screen does not edit platform rules.
    """
    invoice_id = uuid4()
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        rule_service.update_rule(event_key="bill_ready", actor=dana, enabled=False)

        write = services.queue_document(
            source_type="invoice",
            source_id=invoice_id,
            channels=(models.CHANNEL_EMAIL, models.CHANNEL_SMS),
            template=A_PIN,
            account_id=account.pk,
            event_key="bill_ready",
            actor=dana,
        )

    assert write.channels == (models.CHANNEL_PRINT,)
    assert any(problem["code"] == services.QUEUE_EVENT_SWITCHED_OFF for problem in write.problems)


def test_cr048_a1__an_event_switched_off_with_no_floor_queues_nothing_and_says_so(brazos, dana):
    """The other half of the same ruling, and the one that had to be decided.

    A source kind with no floor has nothing left when the event is switched
    off, so the answer is an EMPTY write carrying the reason — not a
    `QueueWriteRefused`, because a tenant switching a setting off is not
    something a human must be asked to repair, and a refusal inside a five
    hundred bill run is a named break per bill (BR-BIL-055).

    It is not silent either, which is the property that makes an empty write
    honest here: the reason travels on `problems`, so a run report can say the
    utility turned this off rather than leaving a reader to infer it from a
    missing row.

    ⚠ **THE KIND HAS MOVED TWICE NOW, AND BOTH SUPERSEDED VERSIONS ARE QUOTED
    RATHER THAN DELETED** — a case that keeps changing its example is the case
    most worth being able to read backwards.

    **It was `notice` first**, and the docstring read: *"a `notice` has no floor
    (`CHANNEL_FLOOR_BY_SOURCE` is BR-BIL-036 and BR-BIL-036 rules on BILLS)"*.
    The ruling of 2026-08-29 gave `notice` the floor — it carries the
    disconnection letter — so the question could no longer be asked of one.

    **Then it was `move`**, and that docstring read: *"`move` is the kind that
    carries it now: its source is a MOVE RECORD rather than a document,
    `models.SOURCE_TYPES` gives it no floor entry deliberately (CR-048 wave B
    task B10), and a utility that switches Move-in welcome off therefore gets no
    row — which is what switching a courtesy message off means"*, with the
    assertion `assert "move" not in services.CHANNEL_FLOOR_BY_SOURCE`.
    **That lasted one day.** On 2026-08-30 the PO confirmed the floor had been
    written down more narrowly than what they had said — their words are *"don't
    switch of print for any document it is awayls on"* — and the deciding case
    was that a deposit-received confirmation acknowledges money received and is
    a receipt by any reading. So the floor went from four kinds to **six**:
    bills, receipts, notices, plan letters, account letters and move letters.
    ⚠ `move` itself was **not separately ruled**. It was taken under the
    principle the ruling settled, because the floor is per SOURCE KIND and that
    kind carries the letter announcing a customer's final bill.

    **So the example is `bulk_action` now** — the staff summary of a finished
    bill run. It is one of the four kinds that genuinely have no floor
    (`report`, `ledger`, `bulk_action`, `test`), and unlike the two that have
    just left that list its absence is a physical fact rather than a judgment: a
    summary for the clerk who ran a job has no envelope to go in. **The property
    under test never moved.** Only the kind that can still demonstrate it did.
    """
    with tenant_ctx(brazos):
        rule_service.update_rule(event_key="billing_run_completed", actor=dana, enabled=False)

        # ⚠ **THE CHANNEL HAS TO BE `in_app` AND THAT IS NOT COSMETIC.** This
        # event names a template class on in-app ONLY, and
        # `rule_service._seeded_channel_enabled` ships a channel OFF when the
        # platform can render nothing on it — so an email ask is suppressed by
        # the CHANNEL's own default and the write would come back empty with the
        # event still switched ON. The case would pass while proving nothing.
        # Measured, not assumed: with the event left on, in-app queues a row and
        # email does not.
        #
        # No `account_id` either: a bulk summary is addressed to the staff who
        # ran the job, not to a customer — `bulk_summary.queue_bulk_summary`'s
        # own shape. The empty write returns before any recipient is resolved.
        write = services.queue_document(
            source_type="bulk_action",
            source_id=uuid4(),
            channels=(models.CHANNEL_IN_APP,),
            template=services.TemplatePin(code="staff_bulk_summary"),
            event_key="billing_run_completed",
            actor=dana,
        )

    assert write.messages == ()
    assert write.dispatched is False
    off = [
        problem
        for problem in write.problems
        if problem["code"] == services.QUEUE_EVENT_SWITCHED_OFF
    ]
    assert off, "an empty write must carry its reason or it is a silently-dropped message"
    assert "billing_run_completed" in off[0]["event_key"]
    # …and the reason it is empty is the SWITCH, not a missing floor entry
    # nobody meant: a kind BR-NOT-024 covers could not have got here.
    assert "bulk_action" not in services.CHANNEL_FLOOR_BY_SOURCE
    # The floor is SIX kinds since 2026-08-30 and this is not one of them. Named
    # in full so that a kind gaining a floor tomorrow takes this case red BY
    # NAME, rather than leaving it quietly asking a question that now has an
    # answer — which is exactly how it came to be asked of `notice` and then of
    # `move` and be wrong both times.
    assert set(services.CHANNEL_FLOOR_BY_SOURCE) == {
        "invoice",
        "payment",
        "notice",
        "plan",
        "account",
        "move",
    }


# ── 3 · A CALLER THAT NAMES NO EVENT IS UNCHANGED ──────────────────────────
def test_cr048_a1__a_caller_that_names_no_event_still_queues_a_switched_off_channel(brazos, dana):
    """⚠ THIS ASSERTS THE DEFECT, ON PURPOSE, AND IT IS REQUIREMENT 3.

    Billing, payments and customers all still call `queue_document` with a
    SOURCE TYPE and no event key; wiring them is CR-048 wave B (B1/B2/B3) and
    belongs to another lane. Until then the rule cannot be found for their
    writes, and this case pins that: switching email off changes nothing for a
    caller that names no event.

    It is written as a passing assertion rather than an xfail because it is the
    contract this task promised — the no-event path is byte-identical to what
    shipped — and because it is the honest measure of how much of the CR is
    still ahead. **When wave B lands, this case is the one that must change.**
    """
    invoice_id = uuid4()
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        switch_channel(dana, "bill_ready", models.CHANNEL_EMAIL, on=False)

        write = services.queue_document(
            source_type="invoice",
            source_id=invoice_id,
            channels=(models.CHANNEL_EMAIL,),
            template=A_PIN,
            account_id=account.pk,
            actor=dana,
        )

    assert models.CHANNEL_EMAIL in write.channels
    assert models.CHANNEL_PRINT in write.channels
    assert not [
        problem
        for problem in write.problems
        if problem["code"]
        in (services.QUEUE_CHANNEL_SWITCHED_OFF, services.QUEUE_EVENT_SWITCHED_OFF)
    ]


def test_cr048_a1__channels_for_without_an_event_answers_exactly_what_it_did(brazos):
    """The four assertions `test_us_not_001_queue_write.py` TC-7b already makes,
    re-made here against the extended signature.

    They are quoted rather than referenced because the promise is *byte
    identical*, and a promise asserted in one file and changed in another is how
    a signature grows a behaviour nobody meant. No tenant context is needed and
    none is entered: the no-event path reads no rule and therefore touches no
    tenant table — which is itself the assertion (hard rule 1 the other way
    round).
    """
    assert services.channels_for("invoice", ()) == (models.CHANNEL_PRINT,)
    assert services.channels_for("invoice", (models.CHANNEL_EMAIL,)) == (
        models.CHANNEL_PRINT,
        models.CHANNEL_EMAIL,
    )
    assert services.channels_for("invoice", (models.CHANNEL_PRINT,)) == (models.CHANNEL_PRINT,)
    # ⚠ THE LAST TWO WERE SUPERSEDED BY BR-NOT-024 (PO 2026-08-29), and the
    # superseded values are quoted rather than deleted because this case exists
    # to pin a promise and a silently-rewritten pin proves nothing:
    #   assert channels_for("payment", (EMAIL,)) == (EMAIL,)   # no floor then
    #   assert channels_for("notice", ())        == ()         # no floor then
    # The floor now covers every customer document, so a payment receipt keeps
    # its paper copy and a notice with no channel named still gets one. The
    # PROMISE this case defends is unchanged and is the reason the first three
    # lines above did not move: extending the signature with `event_key`
    # changes nothing for a caller that omits it.
    assert services.channels_for("payment", (models.CHANNEL_EMAIL,)) == (
        models.CHANNEL_PRINT,
        models.CHANNEL_EMAIL,
    )
    assert services.channels_for("notice", ()) == (models.CHANNEL_PRINT,)
    # …and a kind with no postal surface is still exactly what it was, which is
    # what keeps the line above a RULING rather than a blanket.
    assert services.channels_for("report", ()) == ()


# ── 4 · A CHANNEL WITH NO TEMPLATE CANNOT BE SWITCHED ON ───────────────────
def test_cr048_a1__a_channel_with_no_template_is_refused_by_the_rule_service(brazos, dana):
    """Requirement 4, and the guard is NOT duplicated — it is located and proved.

    `rule_service._apply_channel_changes` refuses `enabled=True` on a channel
    whose `template_code` is NULL (*"a channel can't be enabled if its variant
    is deactivated"*). `daily_digest` is the case in the live catalogue: no
    writer fires it, it has no in-app template class, so its channel row seeds
    OFF with a NULL template. (⚠ This case used `sla_breach` until 2026-10-04,
    when `CR-168-BRC10` P3.58 gave it a writer and FIELD-2's in-app class —
    lane SRV-4; the property is unchanged, only the example moved.)

    The join adds no second copy of this rule because it does not need one — it
    can only ever REMOVE channels from what a caller asked for, so there is no
    path through it that switches a template-less channel on. The next
    assertion is that property, stated as a test rather than as a docstring
    claim (hard-won law 1).
    """
    with tenant_ctx(brazos), pytest.raises(rule_service.RuleRefused) as refusal:
        switch_channel(dana, "daily_digest", models.CHANNEL_IN_APP, on=True)
    assert "no template" in str(refusal.value)

    with tenant_ctx(brazos):
        # The join is subtractive: the kept set is a subset of what was asked
        # for, whatever the rule says. A channel nobody asked for cannot appear
        # through it — only the floor may add, and the floor is BR-BIL-036's.
        kept = services.channels_for(
            "notice", (models.CHANNEL_EMAIL,), event_key="past_due_reminder"
        )
    # ⚠ THIS READ `assert set(kept) <= {EMAIL}` until BR-NOT-024 (PO
    # 2026-08-29) gave `notice` a floor. Written that way it was TWO claims in
    # one — "the join adds nothing" and "this kind has no floor" — and only the
    # first is what the case is about. Subtracting the floor states the claim
    # the test actually makes, so it survives the next kind that gains one.
    floor = set(services.CHANNEL_FLOOR_BY_SOURCE.get("notice", ()))
    assert set(kept) - floor <= {models.CHANNEL_EMAIL}, (
        "the join may only REMOVE channels; anything in the kept set that the "
        "caller did not ask for and the floor did not add is invented"
    )
    assert floor <= set(kept), "and the floor is still applied after the rule"


# ── the edges of the join ──────────────────────────────────────────────────
def test_cr048_a1__a_channel_the_event_has_no_toggle_for_is_passed_through(brazos, dana):
    """An event's channel set is the CATALOGUE's, and it is narrower than the
    platform's. `disconnect_notice` draws print and email — SMS is not a toggle
    on it, even though the catalogue names an SMS template class for it.

    A channel with no toggle is passed through and REPORTED rather than
    dropped: dropping it would suppress a message no utility could switch back
    on, which is the settings screen lying in the other direction — the exact
    failure CR-048 was raised for.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        write = services.queue_document(
            source_type="notice",
            source_id=uuid4(),
            channels=(models.CHANNEL_SMS,),
            template=services.TemplatePin(code="sms_disconnect"),
            account_id=account.pk,
            event_key="disconnect_notice",
            actor=dana,
        )
    assert models.CHANNEL_SMS in write.channels
    unruled = [
        problem for problem in write.problems if problem["code"] == services.QUEUE_CHANNEL_UNRULED
    ]
    assert unruled and unruled[0]["channel"] == models.CHANNEL_SMS
    assert "no sms switch" in unruled[0]["detail"].lower()


def test_cr048_a1__an_event_this_platform_cannot_fire_is_refused_in_plain_words(brazos, dana):
    """BR-NOT-018's shape at the write path: an event nothing can fire is named,
    never guessed at and never quietly ignored.

    Ignoring an unknown key would be the worst of the three: the caller would
    believe a rule had been consulted, the queue would behave as though no rule
    existed, and the settings screen would go back to being decoration for that
    one writer only.
    """
    with tenant_ctx(brazos), pytest.raises(services.QueueWriteRefused) as refusal:
        services.channels_for("invoice", (models.CHANNEL_EMAIL,), event_key="bill_is_ready")
    sentence = str(refusal.value)
    assert "bill_is_ready" in sentence
    assert "bill_ready" in sentence, "the refusal names the vocabulary a caller may use"


def test_cr048_a1__the_rule_is_read_inside_the_tenants_own_context(brazos, dana, lonestar, erin):
    """Hard rule 1. Two utilities, one event, opposite settings — and neither
    can see the other's.

    This is the case that would go quietly wrong if the join read the rule
    tables without a tenant filter: a shared catalogue key (`bill_ready` is a
    platform constant) over a per-tenant table is exactly the shape that reads
    across a boundary without anything looking odd.
    """
    with tenant_ctx(brazos):
        switch_channel(dana, "bill_ready", models.CHANNEL_EMAIL, on=False)
        brazos_channels = services.channels_for(
            "invoice", (models.CHANNEL_EMAIL,), event_key="bill_ready"
        )
    with tenant_ctx(lonestar):
        lonestar_channels = services.channels_for(
            "invoice", (models.CHANNEL_EMAIL,), event_key="bill_ready"
        )
    assert models.CHANNEL_EMAIL not in brazos_channels
    assert models.CHANNEL_EMAIL in lonestar_channels


def test_cr048_a1__the_join_reads_no_clock(brazos):
    """BR-TEN-043. Nothing in this module reads a wall clock and G6 greps for
    it; the join added no exception. Asserted over the SOURCE rather than by
    inspection, because the grep is the guard and a test that agrees with it
    keeps the two from drifting.
    """
    import inspect

    source = inspect.getsource(services)
    for banned in ("datetime.now(", "datetime.today(", "timezone.now(", "date.today("):
        assert banned not in source, f"{banned} is a clock read (BR-TEN-043)"
