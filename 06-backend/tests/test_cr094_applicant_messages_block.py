"""`What goes out to the applicant`, and the decision that never went (`BR-CUS-1076`).

╔══════════════════════════════════════════════════════════════════════════╗
║  THE ABSENCE THESE CASES CLOSE, and it is the PO's own question:         ║
║  *"at the time of approval we are also linking notification and          ║
║   templates to the modal - are you ensuring it will work?"*              ║
║  It did not. There was no table holding which messages a request would   ║
║  send, no template choice on a request at all, and **approving fired     ║
║  nothing** — somebody could apply for service, be approved, and never    ║
║  hear a word.                                                            ║
╚══════════════════════════════════════════════════════════════════════════╝

Blueprint `05-prototype/02 Accounts Menu Blueprint.pdf`, entry 06, capture step
6, read AS IMAGES (p080 at scale 2 and again at scale 4; p081 at scale 2 — B14
rule 42). p080 draws the block: five rows under `SEND · WHAT IT SAYS · TO ·
CHANNEL · TEMPLATE · WHEN`, three ticked, and beneath them a template picker.
p081 carries the four rules that govern it, above the page break.

────────────────────────────────────────────────────────────────────────────
HOW EACH CASE HERE WAS PROVED RED, IN PYTEST, BEFORE IT WAS TRUSTED GREEN
────────────────────────────────────────────────────────────────────────────
One break at a time, each reverted before the next. The failures are quoted in
the lane's conformance record; the breaks were:

  1. `applicant_messages.on_decision(...)` removed from `approve_and_raise` →
        the approval cases fail, naming an empty queue.
  2. the `fired_at` guard removed from `on_decision` →
        FAILED ...::test_approving_twice_queues_one_not_two
  3. `_pin`'s override branch made unconditional (ignoring the class check) →
        FAILED ...::test_a_pick_for_the_other_half_of_the_decision_stands_down
  4. `_refuse_unpickable`'s `pickable` check removed →
        FAILED ...::test_a_draft_version_is_listed_and_cannot_be_picked
  5. `refuse_request`'s `already=` argument dropped, so the refusal path queued
     its own second letter →
        FAILED ...::test_refusing_queues_one_letter_and_not_two

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, asked of each before it was trusted**
(hard-won law 7, habit 2). Three false passes are available here and each one is
closed deliberately:

  * **A case that asserts a queue ROW exists and never reads it.** A row
    addressed to nobody, or carrying the wrong class, satisfies that. So the
    approval cases read `recipient_address`, `template_code`, `template_id` and
    `template_version` back off the row.
  * **A case that counts rows for the whole tenant.** Every count here is
    filtered to ONE request's own `source_id`, because a sibling fixture
    queueing an acknowledgement would otherwise make *"exactly one"* true or
    false by accident.
  * **A case that proves idempotency by calling a door that refuses the second
    call anyway.** `approve` refuses a request that is already approved, so
    *"approving twice queues one"* proved through `approve` would be proving the
    state machine, not the key. The case below calls `on_decision` directly a
    second time — the path a retried HTTP call, a double-clicked button and a
    replayed job all reach.
"""

import pytest

from core import errors

from apps.customers import applicant_messages as block
from apps.customers import models as models_events
from apps.customers import service_request as rules
from apps.customers import service_request_service as sr
from apps.notifications import models as notification_models
from apps.notifications import service_request_events
from apps.notifications import template_models as tm
from apps.notifications import template_service

from apps.customers import service_request_api as api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

APPLICANT_EMAIL = "sarah.miller@example.test"

#: The same capture block lane C's cases use, so one fixture shape describes one
#: applicant across both files rather than two slightly different Sarahs.
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

DOC_ID = "proof_of_identity"


def _queued(request, template_code=None):
    """The outbound rows THIS ONE request produced, by whichever key they ride.

    ⚠ **IT CANNOT FILTER ON `source_id` ALONE, AND FINDING OUT WHY IS THE
    STORY OF THIS FILE.** The acknowledgement keys on the REQUEST; the
    refusal, the ask and the approval each key on the append-only timeline row
    that records the act. So this walks both — the request's id and every one
    of its event ids — which is also what makes *"exactly one"* mean this
    request rather than this tenant (see the module docstring's second false
    pass).
    """
    ids = [str(request.id)] + [
        str(row.id)
        for row in models_events.ServiceRequestEvent.objects.filter(request_id=request.id)
    ]
    qs = notification_models.OutboundMessage.objects.filter(
        source_type=service_request_events.SOURCE_SERVICE_REQUEST,
        source_id__in=ids,
    )
    if template_code is not None:
        qs = qs.filter(template_code=template_code)
    return list(qs.order_by("-created_at", "-id"))


def _ready_to_approve(actor, **overrides):
    """A request walked to the point the drawn Approve modal opens on.

    Draft → submitted → under review → address resolved → customer searched →
    outcome picked → the one required document verified. Every guard the drawn
    modal insists on is CLEARED rather than skipped, so each case below runs
    through the real gate — including `arrearsNotSearched`, which is why the
    customer search is here and not omitted as plumbing.
    """
    request = sr.create_request(actor, {**CAPTURE, **overrides})
    doc = sr.attach_document(
        actor, request.id, doc_type=DOC_ID, name="driving-licence.pdf", storage_ref="s3://id"
    )
    sr.submit(actor, request.id)
    # `pick_up` is retired — PO 2026-09-19, and `transition` raises on it. The
    # decisions work straight from `submitted`. See
    # `test_cr094_approval_raises_the_job._request_ready_to_approve`.
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None)
    sr.decide_outcome(actor, request.id, outcome="new_connection")
    sr.verify_document(actor, doc.id)
    return sr.request_row(request.id)


def _tick_the_decision(actor, request, **extra):
    """Say yes to row five, the way the drawn block's PUT does."""
    return block.save_block(
        actor,
        request.id,
        [{"occasion": block.DECISION, "send": True, **extra}],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE BLOCK ITSELF — five rows, three ticked, three moments
# ═══════════════════════════════════════════════════════════════════════════
def test_the_block_answers_five_rows_in_the_drawings_order_with_every_row_ticked(brazos, dana):
    """p080's table, read as an image: five rows, and **every one ticked**.

    ⚠ **THE TICKS CHANGED ON 2026-09-16 AND THIS CASE'S OWN NAME SAID THE OLD
    RULE.** PO verbatim: *"tick all 6 as default"*. The drawing ticks three of
    five; the PO ruled that a utility should have to UNTICK a message it does
    not want rather than remember to tick one it does. The rows, their order and
    their `when` values are untouched — only the defaults moved.

    ⚠ **TWO OF THE FIVE STILL HAVE NO WORDING** (`documents_outstanding`,
    `balance_outstanding` — `DEF-CUS-5417`), so ticking them does not make them
    send: each still answers `available: false` on its own row. A tick is an
    INTENTION, and this ruling changes the intention rather than the capability.

    ⚠ **THE ORDER IS ASSERTED, NOT JUST THE SET.** Two clerks reading one block
    must see the same rows in the same places; a screen that sorted them itself
    would be a second opinion about a picture.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        answer = block.block_for(request.id)
        assert [row["occasion"] for row in answer["rows"]] == [
            "request_received",
            "documents_outstanding",
            "counter_receipt",
            "balance_outstanding",
            "decision",
        ]
        assert [row["send"] for row in answer["rows"]] == [True, True, True, True, True]
        assert sum(1 for row in answer["rows"] if row["send"]) == 5


def test_the_when_column_carries_its_three_values(brazos, dana):
    """`On submit` · `Already handed over` · `On approve or refuse`.

    The drawn `WHEN` column is what makes the block more than a set of
    checkboxes, and its three values are three different KINDS of thing — one
    fires now, one fired before the clerk got here, and one fires on a day
    nobody has reached yet.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        whens = {row["occasion"]: row["when"] for row in block.block_for(request.id)["rows"]}
        assert whens["request_received"] == "on_submit"
        assert whens["counter_receipt"] == "already_handed_over"
        assert whens["decision"] == "on_approve_or_refuse"
        assert set(whens.values()) == {"on_submit", "already_handed_over", "on_approve_or_refuse"}


def test_two_of_the_five_occasions_have_no_wording_and_every_row_says_which(brazos, dana):
    """⚠ **A DECLARED BLIND SPOT WITH A NUMBER ON IT** (hard-won law 7, shape 5).

    Two of the five drawn rows have no template class in this product:
    `documents_outstanding`, which the drawing itself calls the row that *"makes
    this submission useful"*, and `balance_outstanding`, which the drawing draws
    unticked with `— none chosen` in its template column.

    A tick over a row nothing can send is hard-won law 2's mirror — a
    live-looking control with a dead path behind it — and the only defence this
    repo has against it is saying the number out loud, per row, so a screen can
    render the absence instead of a promise.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        rows = block.block_for(request.id)["rows"]
        without = [row["occasion"] for row in rows if not row["available"]]
        assert without == ["documents_outstanding", "balance_outstanding"]
        assert len(without) == 2
        # ⚠ The counter receipt is NOT one of them, and that is the distinction
        # worth asserting: it has no class either, and it does not need one,
        # because its promise was kept at the counter before the clerk got to
        # this screen. `available` asks *can this row do what it says*, not
        # *is there a template*.
        receipt = next(r for r in rows if r["occasion"] == "counter_receipt")
        assert receipt["available"] is True
        assert receipt["queues"] is False
        # And the drawing's own default is kept even where nothing can send it:
        # changing what a picture shows because our product is behind would hide
        # the gap rather than report it.
        assert next(r for r in rows if r["occasion"] == "documents_outstanding")["send"] is True


def test_the_counter_receipt_never_queues_and_is_stamped_already_handed_over(brazos, dana):
    """p081, read as an image: *"The receipt is already in their hand."*

    It *"records what was given rather than queueing a second copy"*, so saving
    the block stamps the row as fired at the counter and no firing pass can ever
    pick it up.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        block.save_block(dana, request.id, [{"occasion": "counter_receipt", "send": True}])
        row = next(
            r for r in block.block_for(request.id)["rows"] if r["occasion"] == "counter_receipt"
        )
        assert row["fired_state"] == "already_handed_over"
        assert row["fired_at"] is not None
        assert row["queues"] is False
        assert _queued(request) == []


# ═══════════════════════════════════════════════════════════════════════════
# 2 · APPROVING — the PO's actual question
# ═══════════════════════════════════════════════════════════════════════════
def test_approving_queues_exactly_one_decision_message_to_the_applicants_own_address(brazos, dana):
    """**The case this whole lane exists for.**

    ⚠ The assertion that matters is not that a row exists. It is that ONE row
    exists, that it is addressed to the applicant's own email exactly as they
    typed it, and that it carries the approval class — a row addressed to nobody
    and a row carrying the refusal letter would both satisfy a weaker test.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        _tick_the_decision(dana, request)
        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        decision = out["applicant_message"]
        assert decision["state"] == "queued"
        assert decision["sent"] is False

        rows = _queued(request, service_request_events.TEMPLATE_APPROVED)
        assert len(rows) == 1
        assert rows[0].recipient_address == APPLICANT_EMAIL
        assert rows[0].template_code == "service_request_approved"
        # Pinned at queue time, `BR-BIL-026`: a version number, never a null.
        assert rows[0].template_version is not None


def test_approving_twice_queues_one_not_two(brazos, dana):
    """CLAUDE.md rule 6, with the REQUEST as the key.

    ⚠ **PROVED THROUGH `on_decision` AND NOT THROUGH `approve`, ON PURPOSE.**
    `approve` refuses a request that is already approved, so a second `approve`
    would prove the state machine rather than the idempotency key. A retried
    HTTP call, a double-clicked button and a replayed job all reach the inner
    door, and that is the one under test.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        _tick_the_decision(dana, request)
        sr.approve_and_raise(dana, request.id)
        again = block.on_decision(
            dana, sr.request_row(request.id), decision=block.DECISION_APPROVED
        )

        assert again["replayed"] is True
        assert len(_queued(request, service_request_events.TEMPLATE_APPROVED)) == 1


def test_a_decision_row_the_clerk_unticked_queues_nothing_and_says_why(brazos, dana):
    """The tick is a CHOICE, which is the whole reason the block is data.

    ⚠ **THE ROW IS NOW TICKED BY DEFAULT (PO 2026-09-16), SO THIS CASE UNTICKS
    IT EXPLICITLY.** That is the point rather than a workaround: what is being
    guarded is that a clerk who says *no letter* gets no letter AND a recorded
    reason, and that guarantee has to survive the default moving either way.
    Before this the case leaned on the default and would have gone green over a
    product that ignored the tick entirely.

    A clerk who unticks row five asked for no letter, and the product must
    record that it did not send one rather than leaving a silence a reader has
    to interpret.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        block.save_block(dana, request.id, [{"occasion": "decision", "send": False}])
        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        assert out["applicant_message"]["state"] == "not_sent"
        assert out["applicant_message"]["reason"] == block.REASON_NOT_TICKED
        assert _queued(request, service_request_events.TEMPLATE_APPROVED) == []


def test_an_applicant_with_no_email_is_named_rather_than_written_to(brazos, dana):
    """All five classes are email classes; a phone number cannot carry a letter.

    The approval still stands — a message that could not be queued must never
    undo the decision it describes — and the reason is on the row.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana, applicant_email=None)
        _tick_the_decision(dana, request)
        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        assert out["applicant_message"]["state"] == "not_sent"
        assert _queued(request, service_request_events.TEMPLATE_APPROVED) == []


# ═══════════════════════════════════════════════════════════════════════════
# 3 · REFUSING — row five is the letter the clerk already typed
# ═══════════════════════════════════════════════════════════════════════════
def test_refusing_queues_one_letter_and_not_two(brazos, dana):
    """⚠ **THE JUDGMENT THIS LANE MADE, ASSERTED.**

    The Refuse dialog's `What to tell them` box is captioned *"Goes into the
    refusal letter."*, so what the clerk types there IS the decision message.
    Queueing row five as well would send one applicant two letters about one
    decision, one of them generic. The row is RECORDED against the same queue
    row instead.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        _tick_the_decision(dana, request)
        refused = sr.refuse_request(
            dana,
            request.id,
            reason="Duplicate — see SR-26-0004",
            reason_code="duplicate_of_another_request",
            message_to_applicant="We already have this request from you.",
        )

        letters = _queued(request, "service_request_refused")
        assert len(letters) == 1
        assert letters[0].recipient_address == APPLICANT_EMAIL
        # And no approval letter went out beside it — one decision, one letter.
        assert _queued(request, service_request_events.TEMPLATE_APPROVED) == []

        row = next(
            r for r in block.block_for(request.id)["rows"] if r["occasion"] == block.DECISION
        )
        assert row["fired_state"] == "queued"
        assert row["fired_ref"] == refused.applicant_message["ref"]
        assert row["fired_template_code"] == "service_request_refused"


def test_a_refusal_with_no_letter_records_that_nothing_went(brazos, dana):
    """Passing no message refuses nothing and queues nothing — and says so.

    The clerk is the one who decides whether to write; what the product owes
    them afterwards is an honest row rather than a silence.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        _tick_the_decision(dana, request)
        sr.refuse_request(dana, request.id, reason="No service in that area")

        row = next(
            r for r in block.block_for(request.id)["rows"] if r["occasion"] == block.DECISION
        )
        assert row["fired_state"] == "not_sent"
        assert row["fired_ref"] is None


def test_asking_for_more_fires_nothing_on_the_decision_row(brazos, dana):
    """It is not a decision — the request stays open.

    The same posture the PO ruled for the money on 2026-09-15: asking for more
    changes nothing. Its own message still goes (that is `BR-CUS-1075` and is
    lane C's); what must not happen is row five firing on a request nobody has
    decided.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        _tick_the_decision(dana, request)
        sr.ask_for_more(
            dana,
            request.id,
            reason="Site plan unreadable",
            message_to_applicant="The site plan you sent will not open.",
        )

        row = next(
            r for r in block.block_for(request.id)["rows"] if r["occasion"] == block.DECISION
        )
        assert row["fired_at"] is None
        assert row["fired_state"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE PICKER — p081's four rules, against the tenant's REAL registry
# ═══════════════════════════════════════════════════════════════════════════
def test_the_picker_lists_the_decision_classes_with_their_live_version(brazos, dana):
    """`TEMPLATE · GROUP · CHANNEL · VARIANT · VERSION`, drawn on p080.

    ⚠ **THE NAME IS A HUMAN'S AND THE CODE IS NEVER THE VISIBLE VALUE** (B14
    rule 31), so the row carries both and the screen renders the name.
    """
    with tenant_ctx(brazos):
        answer = block.templates_for(block.DECISION)
        assert answer["available"] is True
        names = {row["code"]: row for row in answer["rows"]}
        assert "service_request_approved" in names
        assert names["service_request_approved"]["name"] == "Service request approved"
        assert names["service_request_approved"]["version"] >= 1
        assert names["service_request_approved"]["pickable"] is True
        assert names["service_request_approved"]["channel"] == "email"


def test_the_search_box_matches_the_name_a_human_gave_it(brazos, dana):
    """The drawn helper line under the search box, in one assertion.

    It matches the NAME and never the class code — a clerk cannot be expected to
    search by a database value they are never shown.
    """
    with tenant_ctx(brazos):
        assert block.templates_for(block.DECISION, search="approved")["rows"]
        assert block.templates_for(block.DECISION, search="refused")["rows"]
        assert block.templates_for(block.DECISION, search="service_request_")["rows"] == []


def test_a_draft_version_is_listed_and_cannot_be_picked(brazos, dana):
    """p081: *"The draft version is listed and cannot be picked."*

    ⚠ **LISTED, NOT FILTERED OUT — the rule says why in its own words:**
    *"Hiding it sends a clerk looking for something they can see exists;
    offering it would queue a letter nobody has approved."* So the row comes
    back with `pickable: false` and a reason, and picking it anyway is refused.
    """
    with tenant_ctx(brazos):
        variant, _ = template_service.register(
            code="service_request_approved",
            name="Service request approved · large print",
            actor=dana,
            category="commercial",
        )
        template_service.save_draft(
            template=variant,
            body="{applicant_name}, your request {request_no} is approved.\n\n{utility_name}",
            subject="Approved",
            actor=dana,
        )
        rows = {row["template_id"]: row for row in block.templates_for(block.DECISION)["rows"]}
        drafted = rows[str(variant.pk)]
        assert drafted["status"] == "draft"
        assert drafted["pickable"] is False
        assert drafted["not_pickable_reason"] == "nobody_has_published_this_version"

        request = sr.create_request(dana, CAPTURE)
        with pytest.raises(errors.ValidationError) as refusal:
            block.save_block(
                dana,
                request.id,
                [
                    {
                        "occasion": block.DECISION,
                        "send": True,
                        "template_code": "service_request_approved",
                        "template_id": str(variant.pk),
                    }
                ],
            )
        assert refusal.value.message_key == ("customers.serviceRequest.messageTemplateNotPickable")


def test_a_text_can_never_carry_the_decision_on_its_own(brazos, dana):
    """p081: *"A text never replaces a posted notice."*

    Where a decision has to be put in writing the SMS is *"a courtesy alongside
    it and never instead of it"*. This product has no SMS wording for any of
    these classes, so the courtesy half is ABSENT — and the guard is what stops
    that absence quietly becoming a SUBSTITUTION the day a tenant publishes an
    SMS variant of a decision class.
    """
    with tenant_ctx(brazos):
        texted = tm.NotificationTemplate.objects.create(
            tenant_id=brazos.id,
            code="service_request_approved",
            name="Service request approved · text",
            group="sms",
            channel="sms",
            category="default",
            language="es",
        )
        version = tm.NotificationTemplateVersion.objects.create(
            tenant_id=brazos.id,
            template=texted,
            version=1,
            status=tm.VERSION_PUBLISHED,
            body="Your request is approved.",
        )
        assert version.status == "published"

        listed = {row["template_id"]: row for row in block.templates_for(block.DECISION)["rows"]}
        assert listed[str(texted.pk)]["is_writing"] is False
        assert listed[str(texted.pk)]["pickable"] is False
        assert listed[str(texted.pk)]["not_pickable_reason"] == (
            "a_text_never_replaces_a_posted_notice"
        )

        request = sr.create_request(dana, CAPTURE)
        with pytest.raises(errors.ValidationError) as refusal:
            block.save_block(
                dana,
                request.id,
                [
                    {
                        "occasion": block.DECISION,
                        "send": True,
                        "template_code": "service_request_approved",
                        "template_id": str(texted.pk),
                    }
                ],
            )
        assert refusal.value.message_key == ("customers.serviceRequest.messageTemplateNotInWriting")


def test_a_template_that_is_not_this_occasions_is_refused_by_name(brazos, dana):
    """A request carrying wording nothing will ever pin is a choice a clerk
    believes they made. Refused rather than stored."""
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        with pytest.raises(errors.ValidationError) as refusal:
            block.save_block(
                dana,
                request.id,
                [
                    {
                        "occasion": block.DECISION,
                        "send": True,
                        "template_code": "service_request_acknowledgement",
                    }
                ],
            )
        assert refusal.value.message_key == (
            "customers.serviceRequest.messageTemplateNotForOccasion"
        )


def test_an_occasion_with_no_wording_answers_an_honest_absence(brazos, dana):
    """Not an empty picker a clerk reads as a broken screen — a stated absence,
    which is the posture `channel_reachability` already takes for an unknown
    route."""
    with tenant_ctx(brazos):
        answer = block.templates_for("balance_outstanding")
        assert answer["rows"] == []
        assert answer["available"] is False
        assert answer["reason"] == block.REASON_NO_WORDING


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE PICK IS HONOURED, AND WHERE IT IS NOT THE ROW SAYS SO
# ═══════════════════════════════════════════════════════════════════════════
def test_the_variant_a_clerk_picked_is_the_one_that_renders(brazos, dana):
    """p081: *"A template resolves on three axes and falls back on two."*

    A pick travels as `BR-BIL-025`'s own `override_template_id`, so the exact
    variant the clerk chose on the drawn picker is the one pinned onto the queue
    row — not the category default that happens to match.
    """
    with tenant_ctx(brazos):
        variant, _ = template_service.register(
            code="service_request_approved",
            name="Service request approved · commercial",
            actor=dana,
            category="commercial",
        )
        draft = template_service.save_draft(
            template=variant,
            body="{applicant_name}, request {request_no} is approved.\n\n{utility_name}",
            subject="Approved",
            actor=dana,
        )
        template_service.publish(version_row=draft, actor=dana)

        request = _ready_to_approve(dana)
        _tick_the_decision(
            dana,
            request,
            template_code="service_request_approved",
            template_id=str(variant.pk),
            template_version_seen=draft.version,
        )
        sr.approve_and_raise(dana, request.id)

        rows = _queued(request, service_request_events.TEMPLATE_APPROVED)
        assert len(rows) == 1
        assert str(rows[0].template_id) == str(variant.pk)
        assert rows[0].template_version == draft.version


def test_a_pick_for_the_other_half_of_the_decision_stands_down(brazos, dana):
    """⚠ **THE CLASS IS THE OUTCOME'S TO DECIDE AND THE PICK IS A VARIANT.**

    A clerk picks row five's wording at the counter, BEFORE anybody knows
    whether the request will be approved or refused. `resolve` honours an
    override outright and reads the CODE off the override row, so obeying a pick
    of the refusal variant would send *"we are not able to go ahead"* to
    somebody whose request was approved.

    The pick stands down, and the row records BOTH — what was picked and what
    rendered — so the difference is visible rather than silent.
    """
    with tenant_ctx(brazos):
        refused_variant = tm.NotificationTemplate.objects.filter(
            tenant_id=brazos.id, code="service_request_refused"
        ).first()
        assert refused_variant is not None

        request = _ready_to_approve(dana)
        _tick_the_decision(
            dana,
            request,
            template_code="service_request_refused",
            template_id=str(refused_variant.pk),
        )
        sr.approve_and_raise(dana, request.id)

        rows = _queued(request, service_request_events.TEMPLATE_APPROVED)
        assert len(rows) == 1
        assert _queued(request, "service_request_refused") == []
        # ⚠ **THE ASSERTION THAT ACTUALLY HOLDS THIS IS THE `template_id`, AND
        # THE FIRST DRAFT OF THIS CASE ASSERTED THE `template_code` — WHICH
        # CANNOT MOVE.** `_pin` stamps the code it was ASKED for and takes the
        # id and the version from what resolved, so a row pinned to the refusal
        # variant still reads `service_request_approved` in its code column.
        # Proved: with the guard removed this case stayed GREEN (law 7, shape 4
        # — a check looking at the wrong thing), and it goes red on the id.
        assert str(rows[0].template_id) != str(refused_variant.pk)
        approved_default = tm.NotificationTemplate.objects.get(
            tenant_id=brazos.id,
            code="service_request_approved",
            category="default",
            language="default",
        )
        assert str(rows[0].template_id) == str(approved_default.pk)

        row = next(
            r for r in block.block_for(request.id)["rows"] if r["occasion"] == block.DECISION
        )
        assert row["template_code"] == "service_request_refused"
        assert row["fired_template_code"] == "service_request_approved"


def test_a_row_that_has_fired_is_not_rewritten_by_a_later_save(brazos, dana):
    """Its choices are evidence of what was chosen when it went.

    Changing the template on a letter already sitting on the queue would make
    the record disagree with the letter.
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        _tick_the_decision(dana, request)
        sr.approve_and_raise(dana, request.id)
        block.save_block(dana, request.id, [{"occasion": block.DECISION, "send": False}])

        row = next(
            r for r in block.block_for(request.id)["rows"] if r["occasion"] == block.DECISION
        )
        assert row["send"] is True
        assert row["fired_state"] == "queued"


# ═══════════════════════════════════════════════════════════════════════════
# 6 · NOTHING IS SENT, ON EVERY PATH
# ═══════════════════════════════════════════════════════════════════════════
def test_nothing_this_block_publishes_ever_claims_a_message_was_sent(brazos, dana):
    """The drawing's own last line: *"Everything here is queued, and nothing is
    sent. This product writes a row per message and no sender picks it up — no
    email, no text, no print file."*

    `BR-NOT-013` — no provider adapter exists on any channel — so `sent` is
    False on every path and is not a field anybody sets. The fact travels on the
    payload so no screen has to remember it (hard-won law 1: here a comment
    claiming a guarantee would be a promise to a customer).
    """
    with tenant_ctx(brazos):
        request = _ready_to_approve(dana)
        answer = block.block_for(request.id)
        assert answer["delivery"] == {
            "queued_only": True,
            "delivers": False,
            "br_ref": "BR-NOT-013",
        }
        assert all(row["sent"] is False for row in answer["rows"])

        _tick_the_decision(dana, request)
        out = sr.approve_and_raise(dana, request.id)
        assert out["applicant_message"]["sent"] is False
        assert out["applicant_message"]["delivery"]["delivers"] is False

        # And the queue row itself has never been through a sender.
        letter = _queued(request, service_request_events.TEMPLATE_APPROVED)[0]
        assert letter.status == "queued"
        assert letter.sent_at is None


# ═══════════════════════════════════════════════════════════════════════════
# 7 · THE DOORS — built is not wired, and a service call is not a door
# ═══════════════════════════════════════════════════════════════════════════
def test_the_two_routes_resolve_at_their_real_tenant_addresses(brazos, dana):
    """⚠ **CHECKED FROM THE OUTSIDE, WHERE THE SCREEN STARTS** (hard-won law 2).

    Every case above calls the service layer. That proves the capability and
    proves nothing at all about whether a screen can reach it — this repo has
    shipped screens that were routed, tested and translated into eleven
    languages with no door, and `service_request_api.py` exists in the first
    place because ~2,700 lines of this module landed with no route naming any of
    it.
    """
    from django.urls import resolve

    for path, view in (
        (
            "/api/brazos/service-requests/abc/applicant-messages",
            api.service_request_applicant_messages,
        ),
        (
            "/api/brazos/service-requests/abc/applicant-message-templates",
            api.service_request_message_templates,
        ),
    ):
        assert resolve(path).func is view, path


def test_the_block_round_trips_through_its_own_route(brazos, dana):
    """`GET` then `PUT` then `GET`, as HTTP, with the body a screen would send.

    ⚠ **A TEST WITH ITS OWN FIXTURE PROVES THE FIXTURE.** This one goes through
    the view, the permission class and the tenant context, which is the only
    path that can tell a working door from a service function nobody can call.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)

    first = api_call(
        api.service_request_applicant_messages,
        "get",
        f"/api/brazos/service-requests/{request.id}/applicant-messages",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        request_id=str(request.id),
    )
    assert first.status_code == 200
    assert len(first.data["rows"]) == 5
    assert first.data["delivery"]["delivers"] is False

    saved = api_call(
        api.service_request_applicant_messages,
        "put",
        f"/api/brazos/service-requests/{request.id}/applicant-messages",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"rows": [{"occasion": "decision", "send": True}]},
        request_id=str(request.id),
    )
    assert saved.status_code == 200
    decision = next(r for r in saved.data["rows"] if r["occasion"] == "decision")
    assert decision["send"] is True
    assert decision["send_is_default"] is False


def test_the_picker_answers_over_http_with_the_draft_row_in_it(brazos, dana):
    """The drawn picker, through its own door — draft row included.

    p081 again: the draft is LISTED and not pickable. A screen that never
    receives it cannot render it, so the door has to carry it.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, CAPTURE)
        variant, _ = template_service.register(
            code="service_request_approved",
            name="Service request approved · commercial",
            actor=dana,
            category="commercial",
        )
        template_service.save_draft(
            template=variant,
            body="{applicant_name}, request {request_no} is approved.\n\n{utility_name}",
            subject="Approved",
            actor=dana,
        )

    answer = api_call(
        api.service_request_message_templates,
        "get",
        f"/api/brazos/service-requests/{request.id}/applicant-message-templates",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"occasion": "decision"},
        request_id=str(request.id),
    )
    assert answer.status_code == 200
    drafted = [row for row in answer.data["rows"] if row["status"] == "draft"]
    assert len(drafted) == 1
    assert drafted[0]["pickable"] is False
    assert answer.data["delivery"]["delivers"] is False
