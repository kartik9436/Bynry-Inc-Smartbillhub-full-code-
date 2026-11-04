"""A service request can tell the applicant something (`DEF-CUS-5389`).

╔══════════════════════════════════════════════════════════════════════════╗
║  THE ABSENCE THESE CASES CLOSE, in the product's own words:              ║
║  *"'service_request' is not a source kind this platform queues (invoice, ║
║   payment, notice, plan, report, ledger, test, bulk_action, move,        ║
║   account, portal, appointment, message). … a row nothing recognises is  ║
║   a message nothing will ever send."*                                    ║
║  That sentence printed on the request's own History tab, at a clerk.     ║
╚══════════════════════════════════════════════════════════════════════════╝

The blueprint (`05-prototype/02 Accounts Menu Blueprint.pdf`, entry 06, drawings
10 and 11 on p084–p086, read AS IMAGES at scale 2 and 4) promises three things
and the product delivered none of them:

  * Refuse → *"A refusal letter is queued to the applicant"*, carrying the
    clerk's own `What to tell them` sentence, whose helper line is *"Goes into
    the refusal letter."*
  * Ask for more → *"A message is queued to them"*, carrying a typed `Message to
    the applicant`, *"Sent to them and kept on the request's history."*
  * Submit → *"submitting sends the customer an acknowledgement"* (p086).

────────────────────────────────────────────────────────────────────────────
HOW EACH CASE HERE WAS PROVED RED, IN PYTEST, BEFORE IT WAS TRUSTED GREEN
────────────────────────────────────────────────────────────────────────────
Each break was made one at a time and reverted before the next. The failures
are quoted in the lane's conformance record; the breaks were:

  1. `service_request` removed from `notifications.models.SOURCE_TYPES` →
        every queueing case fails, with the queue's own refusal naming the
        thirteen kinds it knows.
  2. `_tell_the_applicant`'s call removed from `refuse_request` →
        FAILED ...::test_refusing_queues_a_letter_carrying_the_clerks_own_words
  3. the occasion key changed from the timeline row to the REQUEST →
        FAILED ...::test_a_second_ask_writes_a_second_message_not_a_dedupe
  4. the fee class picked unconditionally →
        FAILED ...::test_a_fee_taken_pins_the_acknowledgement_that_states_it

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, asked of each one before it was
trusted** (hard-won law 7, habit 2). The dangerous false pass here is a case
that asserts a queue ROW exists and never looks at what is in it or who it is
addressed to — a row addressed to nobody, or carrying the wrong body, passes
that. So every case below reads the row back: its `recipient_address`, its
pinned template code and, where it matters, the clerk's words inside its render
context.
"""

import pytest

from core import errors

from apps.customers import service_request as rules
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.notifications import models as notification_models
from apps.notifications import service_request_events

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

APPLICANT_EMAIL = "sarah.miller@example.test"

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Miller, Sarah",
    "applicant_email": APPLICANT_EMAIL,
    "applicant_phone": "555-0142",
    "address_as_given": "212 Balcones Drive",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "I'm moving into somewhere",
}


def _new(actor, **overrides):
    return sr.create_request(actor, {**CAPTURE, **overrides})


def _decidable(actor, **overrides):
    """A request a clerk may refuse or ask more about — which is a SUBMITTED one.

    ⚠ **THIS HELPER CALLED `pick_up` AND THAT MOVE NO LONGER EXISTS.** The PO's
    ruling of 2026-09-19 left the service request five states and retired nine
    moves, `pick_up` among them — *"not required- you map this state when it is
    submitted - dont take seperate approval / or confirmation - it is confusion
    for user."* `REFUSE` and `REQUEST_INFO` both name `SUBMITTED` in
    `rules.TRANSITIONS` now, so a decision is taken straight from it and there
    is no step in between to walk.

    It was renamed rather than repointed: a helper called `_under_review` that
    leaves a request SUBMITTED is the hand-typed-copy-of-a-rule trap this same
    ruling produced three times in one day (`DEF-CUS-5874`), and the name is
    what the next reader believes.
    """
    request = _new(actor, **overrides)
    sr.submit(actor, request.id)
    return sr.request_row(request.id)


def _queued(request_id=None, template_code=None):
    """Every `service_request` row on the outbound queue, newest first."""
    qs = notification_models.OutboundMessage.objects.filter(
        source_type=service_request_events.SOURCE_SERVICE_REQUEST
    )
    if request_id is not None:
        qs = qs.filter(source_id=request_id)
    if template_code is not None:
        qs = qs.filter(template_code=template_code)
    return list(qs.order_by("-created_at", "-id"))


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE KIND ITSELF — the absence the History tab printed
# ═══════════════════════════════════════════════════════════════════════════
def test_service_request_is_a_source_kind_this_platform_queues():
    """The sentence a clerk read on the History tab is no longer true.

    Asserted on the CONSTANT rather than by queueing something, because the
    absence was in the vocabulary and a queue row proves only that one path
    works. The second edit — classifying the kind for the print floor — is held
    by `test_cr048_print_floor.py`, which fails NAMING any kind nobody
    classified.
    """
    assert "service_request" in notification_models.SOURCE_TYPES


def test_the_kind_carries_no_print_floor_and_the_reason_is_physical():
    """No mailing address for an applicant exists anywhere in this product.

    A request holds the address of the PROPERTY that wants service, never an
    address for the person asking — and the commonest drawn refusal reason is
    *Not our service area*, so a print floor would post a refusal to a street
    the utility has just said it does not serve. Widening `BR-NOT-024` is a PO
    question and never a dictionary edit (the `move` precedent).
    """
    from apps.notifications import services as notification_services

    assert "service_request" not in notification_services.CHANNEL_FLOOR_BY_SOURCE


# ═══════════════════════════════════════════════════════════════════════════
# 2 · REFUSING — the letter, and the three audiences of one act
# ═══════════════════════════════════════════════════════════════════════════
def test_refusing_queues_a_letter_carrying_the_clerks_own_words(brazos, dana):
    """*"A refusal letter is queued to the applicant"*, drawn on p085.

    ⚠ The assertion that matters is not that a row exists. It is that the row is
    ADDRESSED to the applicant and carries the clerk's sentence — a row with no
    recipient would satisfy a weaker test and would be a letter to nobody.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana)
        told = "212 Balcones Drive falls outside the Brazos Bend boundary."
        refused = sr.refuse_request(
            dana,
            request.id,
            reason="Outside the boundary",
            reason_code=rules.REFUSAL_NOT_OUR_AREA,
            message_to_applicant=told,
        )
        outcome = refused.applicant_message
        assert outcome["state"] == sr.ACK_QUEUED
        assert outcome["address"] == APPLICANT_EMAIL
        assert outcome["template_code"] == service_request_events.TEMPLATE_REFUSED

        rows = _queued(template_code=service_request_events.TEMPLATE_REFUSED)
        assert len(rows) == 1
        row = rows[0]
        assert row.recipient_address == APPLICANT_EMAIL
        assert row.account_id is None  # an applicant has no account
        assert row.channel == notification_models.CHANNEL_EMAIL
        assert row.render_context["message_body"] == told
        assert row.render_context["request_no"] == request.request_no


def test_the_three_things_a_refusal_records_go_to_three_different_places(brazos, dana):
    """`reason` is the register's, `reason_code` is the utility's, and only
    `message_to_applicant` reaches the person refused.

    ⚠ **NO REASON CODE IS IN THE LETTER.** B14 rule 32 keeps our vocabulary off
    a clerk's screen and the argument is stronger for a document that outlives
    the screen. A applicant reading *duplicate_of_another_request* is reading
    our database.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana)
        sr.refuse_request(
            dana,
            request.id,
            reason="Duplicate — see SR-26-0004",
            reason_code=rules.REFUSAL_DUPLICATE,
            message_to_applicant="We already have this request from you.",
        )
        row = sr.request_row(request.id)
        assert row.reason_code == rules.REFUSAL_DUPLICATE
        assert row.decision_reason == "Duplicate — see SR-26-0004"
        assert row.refusal_message == "We already have this request from you."

        letter = _queued(template_code=service_request_events.TEMPLATE_REFUSED)[0]
        body = " ".join(str(v) for v in letter.render_context.values())
        for code in rules.REFUSAL_REASONS:
            assert code not in body
        assert "Duplicate — see SR-26-0004" not in body

        stored = sr.request_row(request.id)
        decision = reads.decision_tab(stored, sr.evidence_for(stored), reads.conditions_for(stored))
        assert decision["refusal"]["reason_code"] == rules.REFUSAL_DUPLICATE
        assert decision["refusal"]["message"] == "We already have this request from you."


def test_a_refusal_reason_outside_the_five_is_refused_by_name(brazos, dana):
    """Five values group; five hundred typed sentences do not.

    The column has been accepted since CR-031 and no screen ever set it, so it
    was free text in practice — a register of refusals that answers no question
    about why this utility turns people down.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana)
        with pytest.raises(errors.ValidationError) as caught:
            sr.refuse_request(
                dana,
                request.id,
                reason="Because",
                reason_code="they_looked_shifty",
                message_to_applicant="No.",
            )
        assert caught.value.message_key == "customers.serviceRequest.refusalReasonUnknown"
        assert sr.request_row(request.id).state == rules.SUBMITTED


def test_refusing_with_no_message_queues_nothing_and_says_so(brazos, dana):
    """A letter with nothing in it tells an applicant no and nothing about why.

    ⚠ **AND IT DOES NOT BLOCK THE REFUSAL.** Not being able to write to somebody
    is not a reason to leave a request open — the decision stands, the timeline
    carries it, and the outcome names what was not done instead of the screen
    inferring silence from a 200.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana)
        refused = sr.refuse_request(dana, request.id, reason="Outside the boundary")
        assert refused.state == rules.REFUSED
        outcome = refused.applicant_message
        assert outcome["state"] == sr.ACK_NOT_SENT
        assert outcome["reason"] == sr.APPLICANT_NO_REFUSAL_MESSAGE
        assert _queued(template_code=service_request_events.TEMPLATE_REFUSED) == []


def test_an_applicant_with_no_email_is_a_named_absence_not_a_silence(brazos, dana):
    """All four classes are EMAIL classes; an SMS carries 160 characters.

    A phone number alone therefore cannot carry any of these letters, and the
    honest answer is to record which fact is true — *they left no way to reach
    them* and *they left a way we have not written wording for* are different
    things and only the second one is ours to fix.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana, applicant_email=None)
        refused = sr.refuse_request(
            dana,
            request.id,
            reason="Outside the boundary",
            message_to_applicant="It falls outside our boundary.",
        )
        assert refused.state == rules.REFUSED
        assert refused.applicant_message["state"] == sr.ACK_NOT_SENT
        assert refused.applicant_message["reason"] == sr.APPLICANT_NO_EMAIL
        assert _queued(template_code=service_request_events.TEMPLATE_REFUSED) == []


# ═══════════════════════════════════════════════════════════════════════════
# 3 · ASKING FOR MORE — the tick list, and the end of one fixed sentence
# ═══════════════════════════════════════════════════════════════════════════
def test_asking_for_more_queues_what_the_clerk_actually_typed(brazos, dana):
    """Until this wave the product sent *"More information is needed before this
    can be reviewed."* to every request alike, and nothing to the applicant."""
    with tenant_ctx(brazos):
        request = _decidable(dana)
        typed = "The site plan you sent will not open. Please send it again as a PDF."
        asked = sr.ask_for_more(
            dana,
            request.id,
            reason="Site plan unreadable",
            info_needed=[rules.NEEDS_SITE_PLAN, rules.NEEDS_IDENTITY_PROOF],
            message_to_applicant=typed,
        )
        assert asked.state == rules.MORE_INFO
        assert asked.applicant_message["state"] == sr.ACK_QUEUED

        row = _queued(template_code=service_request_events.TEMPLATE_MORE_INFO)[0]
        assert row.render_context["message_body"] == typed
        assert row.recipient_address == APPLICANT_EMAIL

        stored = sr.request_row(request.id)
        assert stored.info_needed == [rules.NEEDS_SITE_PLAN, rules.NEEDS_IDENTITY_PROOF]
        assert stored.info_message == typed


def test_the_tick_list_is_stored_in_the_drawings_order_not_the_callers(brazos, dana):
    """Two clerks ticking the same two boxes store the same list, so a report
    can group on it."""
    with tenant_ctx(brazos):
        request = _decidable(dana)
        sr.ask_for_more(
            dana,
            request.id,
            reason="Two things missing",
            info_needed=[rules.NEEDS_CONNECTION_DATE, rules.NEEDS_SITE_PLAN],
            message_to_applicant="We need two things from you.",
        )
        assert sr.request_row(request.id).info_needed == [
            rules.NEEDS_SITE_PLAN,
            rules.NEEDS_CONNECTION_DATE,
        ]


def test_a_tick_the_product_does_not_have_is_refused_by_name(brazos, dana):
    """A code this server does not know is the screen and the server disagreeing
    about what can be waited for. Silently dropping it would leave a clerk
    believing they had recorded something."""
    with tenant_ctx(brazos):
        request = _decidable(dana)
        with pytest.raises(errors.ValidationError) as caught:
            sr.ask_for_more(
                dana,
                request.id,
                reason="Something",
                info_needed=["a_notarised_letter_from_your_mother"],
                message_to_applicant="Please send it.",
            )
        assert caught.value.message_key == "customers.serviceRequest.infoNeededUnknown"
        assert sr.request_row(request.id).state == rules.SUBMITTED


def test_the_tick_list_is_not_in_the_letter(brazos, dana):
    """The drawing attaches *Sent to them* to the message box alone.

    Composing the list into English here would put untranslated prose inside a
    customer-facing document, which is what the language axis (`BR-NOT-006`)
    exists to prevent.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana)
        sr.ask_for_more(
            dana,
            request.id,
            reason="Site plan unreadable",
            info_needed=[rules.NEEDS_SITE_PLAN],
            message_to_applicant="Please send the site plan again as a PDF.",
        )
        row = _queued(template_code=service_request_events.TEMPLATE_MORE_INFO)[0]
        body = " ".join(str(v) for v in row.render_context.values())
        for code in rules.INFO_NEEDED_KINDS:
            assert code not in body


def test_the_old_transitions_door_still_works_and_now_carries_the_message(brazos, dana):
    """⚠ **HARD-WON LAW 2'S MIRROR: a live control doing quietly less than a new
    one.** Every screen in the product asks for more through `transitions`. A
    new endpoint beside `refuse` would have left that door moving the state and
    telling the applicant nothing, so `transitions` gained the two fields and
    hands the act to `ask_for_more`.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana)
        moved = sr.transition(
            dana,
            request.id,
            rules.REQUEST_INFO,
            reason="Site plan unreadable",
            info_needed=[rules.NEEDS_SITE_PLAN],
            message_to_applicant="Please send the site plan again as a PDF.",
        )
        assert moved.state == rules.MORE_INFO
        assert moved.applicant_message["state"] == sr.ACK_QUEUED
        assert len(_queued(template_code=service_request_events.TEMPLATE_MORE_INFO)) == 1


def test_the_old_transitions_door_with_no_message_behaves_exactly_as_before(brazos, dana):
    """A caller that passes neither new field gets yesterday's behaviour."""
    with tenant_ctx(brazos):
        request = _decidable(dana)
        moved = sr.transition(dana, request.id, rules.REQUEST_INFO, reason="Need more")
        assert moved.state == rules.MORE_INFO
        assert moved.applicant_message["reason"] == sr.APPLICANT_NO_INFO_MESSAGE
        assert _queued(template_code=service_request_events.TEMPLATE_MORE_INFO) == []


def test_a_second_ask_writes_a_second_message_not_a_dedupe(brazos, dana):
    """⚠ **THE KEY IS THE OCCASION AND THE OBVIOUS CHOICE IS A TRAP.**

    The queue's key is (tenant, source kind, source id, channel, copy no).
    Keying on the REQUEST would mean the second ask meets the key, the queue
    reports `created=False`, the clerk is told it was queued, and the applicant
    is sent the FIRST message's contents and never the second's. Nothing about
    that looks like a failure — there is a row, it is just the wrong message.
    """
    with tenant_ctx(brazos):
        request = _decidable(dana)
        sr.ask_for_more(
            dana,
            request.id,
            reason="First",
            message_to_applicant="Please send the site plan again as a PDF.",
        )
        # ⚠ **`info_received` STOOD HERE AND IS RETIRED (PO ruling 2026-09-19).**
        # It existed to walk the request back out of `more_info` so a second ask
        # was lawful. The ruling made that step unnecessary rather than
        # impossible: `REQUEST_INFO` names `MORE_INFO` among its own from-states
        # *on purpose*, so a clerk who has asked for a site plan and then needs
        # the identity document too can ask again with nothing in between. The
        # second ask is therefore made straight from `more_info`, which is the
        # walk a clerk actually has, and the assertion below is unchanged.
        sr.ask_for_more(
            dana,
            request.id,
            reason="Second",
            message_to_applicant="We also need a connection date.",
        )
        rows = _queued(template_code=service_request_events.TEMPLATE_MORE_INFO)
        assert len(rows) == 2
        bodies = {row.render_context["message_body"] for row in rows}
        assert bodies == {
            "Please send the site plan again as a PDF.",
            "We also need a connection date.",
        }


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE ACKNOWLEDGEMENT — already wired, blocked only by the vocabulary
# ═══════════════════════════════════════════════════════════════════════════
def test_submitting_now_queues_the_acknowledgement_it_always_promised(brazos, dana):
    """`BR-CUS-079` was CONFIRMED on 2026-08-24, wired the same week, and every
    call refused on the source kind for three weeks."""
    with tenant_ctx(brazos):
        request = _new(dana)
        result = sr.submit(dana, request.id)
        ack = result["acknowledgement"]
        assert ack["state"] == sr.ACK_QUEUED
        assert ack["sent"] is False  # BR-NOT-013 — no adapter on any channel
        assert ack["address"] == APPLICANT_EMAIL

        rows = _queued(request_id=request.id)
        assert len(rows) == 1
        assert rows[0].template_code == service_request_events.TEMPLATE_ACKNOWLEDGEMENT
        assert rows[0].recipient_address == APPLICANT_EMAIL


def test_a_replayed_submit_does_not_acknowledge_twice(brazos, dana):
    """The request itself is the acknowledgement's key (rule 6), which is what
    `submit`'s own docstring says its idempotency key is."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        again = sr.submit(dana, request.id)
        assert again["idempotent_replay"] is True
        assert len(_queued(request_id=request.id)) == 1


def test_a_fee_taken_pins_the_acknowledgement_that_states_it(brazos, dana):
    """**`BR-CUS-090` clause (3), made unreachable-by-construction.**

    *"THE ACKNOWLEDGEMENT MAY NOT SAY 'Nothing is charged' WHEN MONEY WAS TAKEN
    … It is the FIRST thing an applicant receives and it is customer-facing, so
    a false sentence there is a money defect, not a copy nit."* A template body
    has no conditional, so one class could only ever carry one of the two
    sentences. Two classes, picked by whether a receipt exists, is the ruling as
    a mechanism instead of a thing to remember.
    """
    from decimal import Decimal

    with tenant_ctx(brazos):
        request = _new(dana)
        request.fee_collected = Decimal("25.0000")
        request.fee_currency = "USD"
        request.fee_method = "cash"
        request.fee_receipt_no = "RCP-26-4471"
        request.save()

        sr.submit(dana, request.id)
        row = _queued(request_id=request.id)[0]
        assert row.template_code == service_request_events.TEMPLATE_ACKNOWLEDGEMENT_FEE
        # Hard rule 2 — four decimals stored, TWO displayed, and the currency
        # travels because this platform is not only in dollars.
        # CR-190-BRC10 — a VALUE with its currency now, never a pre-written string.
        assert row.render_context["fee_amount"] == {"__money_ccy__": {"amount": "25.0000", "currency": "USD"}}
        assert row.render_context["receipt_no"] == "RCP-26-4471"


def test_the_no_fee_acknowledgement_never_carries_a_money_token(brazos, dana):
    """The mirror of the case above, and the one that makes it a guarantee
    rather than a habit: the class a request with no receipt is acknowledged on
    has no amount in its palette at all, so a tenant cannot edit one in."""
    from apps.notifications import catalogs

    palette = catalogs.catalog_for(service_request_events.TEMPLATE_ACKNOWLEDGEMENT)
    assert palette is not None
    assert "fee_amount" not in palette.tokens
    assert "receipt_no" not in palette.tokens


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE SEAM, AND THE BOUNDARY IT KEEPS
# ═══════════════════════════════════════════════════════════════════════════
def test_the_seam_reaches_every_published_name(brazos, dana):
    """Hard-won law 1 — a docstring claiming a seam is wired is not the wiring.

    The entry points are resolved BY NAME at call time, so a rename on the
    notifications side would turn the letters off with every test still green.
    This is the case that goes red instead.

    ⚠ **RENAMED 2026-09-15 — IT WAS `…_three_real_functions` AND THE NUMBER WAS
    IN THE NAME** (`CR-094-BRC01` lane J). The approval letter and the template
    picker's read joined the seam that day, so a name carrying a count went
    stale the first time the seam grew, which is B14's rule-count rot in a test.
    The assertion still names every member, so the case is exactly as strict.
    """
    from apps.customers import notifications_seam

    published = notifications_seam.service_request_entry_points()
    assert set(published) == {
        "queue_request_acknowledgement",
        "queue_request_refused",
        "queue_request_more_info",
        # `CR-094-BRC01` lane J — the approval an applicant was never told about,
        # and the read the drawn template picker lists from.
        "queue_request_approved",
        "applicant_templates",
    }
    assert all(callable(fn) for fn in published.values())


def test_a_queue_failure_never_undoes_the_decision(brazos, dana, monkeypatch):
    """*"A failed message must never undo the act it describes."*

    ⚠ **THE SAVEPOINT IS WHAT MAKES THIS TRUE ON POSTGRESQL AND THIS CASE
    CANNOT PROVE IT** (hard-won law 14). SQLite has no aborted-transaction
    state, so the version without a savepoint passes here. What this case holds
    is the OTHER half — the seam swallows the failure, reports it as an outcome
    a clerk can read, and leaves the refusal standing. The savepoint itself is
    proved by driving a real `SELECT 1/0` through the seam on PostgreSQL; the
    transcript is in the lane's conformance record.
    """
    from apps.notifications import service_request_events as writer

    def explode(**_kwargs):
        raise RuntimeError("the queue is on fire")

    monkeypatch.setattr(writer, "queue_request_refused", explode)
    with tenant_ctx(brazos):
        request = _decidable(dana)
        refused = sr.refuse_request(
            dana,
            request.id,
            reason="Outside the boundary",
            message_to_applicant="It falls outside our boundary.",
        )
        assert refused.state == rules.REFUSED
        assert sr.request_row(request.id).state == rules.REFUSED
        outcome = refused.applicant_message
        assert outcome["state"] == sr.ACK_NOT_SENT
        assert outcome["reason"] == "applicant_message_error"
