# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (S19 Move-In) × US-CUS-005 (S20 Move-Out) ×
#           US-PAY-018 (plan notices) × US-NOT-017 (SET-12 / SET-12D)
#           CR-048 wave B tasks B6 (the per-event counts) and B10 (the three
#           real omissions)   Screens: S19 · S20 · S8
# Rules:    BR-NOT-013 (delivery is out of this release on EVERY channel — so
#           `delivered` and `bounced` stay NOT REPORTED) · BR-NOT-017 (the
#           utility's own rule, read on the way to the queue) · BR-NOT-024
#           (print is the floor on bills, receipts, notices, plan letters,
#           ACCOUNT letters and MOVE letters — and on NOTHING ELSE. ⚠ THIS LINE
#           READ "bills, receipts, notices and plan letters" until 2026-08-30,
#           when the PO confirmed the four-kind list was narrower than their
#           ruling and widened it to SIX. Every count in this file that moved
#           from 1 to 2, and both move cases, moved for that one reason: a move
#           letter is now queued on the email its writer asks for AND a paper
#           copy) · BR-PAY-016 (the plan-notice cadence as the
#           PO left it on 2026-08-11) · BR-CUS-150/151 (the move RECORD, whose
#           id keys the message) · BR-TEN-043 (no wall clock) ·
#           CLAUDE.md rule 1 · rule 6 (idempotency) · hard-won law 2 (built is
#           not wired) · hard-won law 7 (RED first) · hard-won law 14 (a failed
#           statement poisons the whole Postgres transaction)
# ───────────────────────────────────────────────────────
"""CR-048 B6 + B10 — the counters stop being zeros, and three silences end.

╔══════════════════════════════════════════════════════════════════════════╗
║  RED PROVED FIRST for every case here (hard-won law 7). The transcripts  ║
║  are in the lane report; the two that matter most:                       ║
║                                                                          ║
║    a completed move-in queued ZERO messages —                            ║
║      "a move-in queued 0 messages. The new occupant is told NOTHING."    ║
║    SET-12 had no row for any of the three —                              ║
║      "SET-12 has no row for ['move_in_welcome', 'move_out_final_bill',   ║
║       'payment_plan_instalment_missed']"                                 ║
╚══════════════════════════════════════════════════════════════════════════╝

FIVE THINGS THIS FILE HOLDS THE BUILD TO, and each is a way the work could be
finished, look finished, and not be:

**1 · A UTILITY THAT SWITCHES THE WELCOME OFF GETS NO ROW, and the move-in
still completes.** Both halves, because either alone passes on a broken build:
a lane that never queued anything satisfies the first, and a lane that ignores
the rule satisfies the second.

**2 · THE WORK SURVIVES A NOTIFICATION FAILURE — ON POSTGRESQL.** ⚠ Catching
the exception is NOT enough (hard-won law 14): a statement that errors inside a
Postgres transaction aborts the whole transaction, so the account, its reads and
its move record are already lost at COMMIT. The `@requires_postgres` cases drive
a REAL `SELECT 1/0` through each seam and then read the work back in a NEW
transaction. On SQLite they skip, which is exactly why they are marked — the
broken version passes the default suite, green, on every machine.

**3 · IDEMPOTENCY, AND THE TRAP IS NOT THE OBVIOUS ONE.** The queue key is
(tenant, source_type, source_id, channel, copy_no). Keying a new message on a
record that already owns a row for that channel makes it DEDUPE INTO the
existing one: no error, `created=False`, and the wrong message on file. Two
cases pin it — a move-out letter must not collide with that account's welcome,
and a missed-instalment letter must not collide with the plan's reminder.

**4 · B9's COVERAGE COUNT FALLS ON ITS OWN.** Adding three events must move the
"wording with no rule" figure from 16 to 13 with nobody editing a number. B9
built that as a derivation precisely so this would happen; this asserts it did.

**5 · THE COUNTS ARE COUNTS, AND THE ABSENCES ARE ABSENCES.** `delivered` and
`bounced` must NEVER be derived from queued rows (BR-NOT-013), and a suppression
that cannot be recorded must read as unavailable rather than as zero.

NOTHING HERE SENDS ANYTHING TO ANYBODY OUTSIDE THIS BUILDING: every message is a
queue row, and no dispatch cycle in this file leaves `in_app`.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection

from apps.customers import models as customers_models
from apps.customers import moves, notifications_seam
from apps.customers import services as customers_services
from apps.notifications import customer_events, delivery_counts
from apps.notifications import models as notification_models
from apps.notifications import rule_catalog, rule_service, seed_templates
from apps.notifications import services as notification_services
from apps.payments import notices as payments_notices
from apps.payments import plans
from apps.payments.collections_models import (
    NOTICE_PLAN_MISSED,
    NOTICE_PLAN_REMINDER,
    PaymentPlan,
    PaymentPlanInstallment,
)

from apps.notifications import rules_api

from tests import identity_fixtures
from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_w7_transfers import _mover

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — every BUSINESS date in this file is NAMED. Template seeding, the
#: plan schedule and every move date are fixed, so nothing here depends on when
#: the suite runs.
TODAY = date(2026, 8, 25)
PLAN_START = date(2026, 9, 1)


def _rail_today() -> date:
    """The day the rail's own window ends, asked of the rail rather than assumed.

    ⚠ **THIS IS NOT A BR-TEN-043 VIOLATION AND THE DISTINCTION MATTERS.** Every
    BUSINESS date above is named and fixed. What this returns is the VIEW's
    today, and it has to come from the same place the production window comes
    from — because `outbound_messages.created_at` is stamped by the DATABASE at
    INSERT (`auto_now_add`), not by any date this file chooses. A test that
    windowed on 2026-08-25 while the rows landed on the suite's real run date
    would count zero and read as a broken rail rather than a broken test.
    """
    return delivery_counts.window()[1]


#: The three keys under test, quoted from `rule_catalog` rather than retyped —
#: a test that spelled its own key would pass against a catalogue that spelled
#: the event differently, which is the failure `bulk_summary` records about
#: `billing_run_finished`.
EVENT_MOVE_IN = customer_events.EVENT_MOVE_IN
EVENT_MOVE_OUT = customer_events.EVENT_MOVE_OUT
EVENT_PLAN_MISSED = payments_notices.EVENT_PLAN_INSTALMENT_MISSED


# ── fixtures, in the shape each flow actually happens ───────────────────────
def _seeded(actor):
    seed_templates.seed_notice_templates(actor, on_date=TODAY)


def _queue(tenant, **filters):
    return notification_models.OutboundMessage.objects.filter(tenant=tenant, **filters)


def _codes(rows):
    return {row.get("code") for row in rows}


def _switch_off(event_key, actor, *, channel=None):
    """Turn an event (or one of its channels) off through the REAL service.

    Never `NotificationRule.objects.update(...)`: the thing under test is that
    the SETTINGS SCREEN reaches the queue, and a fixture that wrote the row
    itself would pass against a service that cannot save one.
    """
    if channel is None:
        return rule_service.update_rule(event_key=event_key, actor=actor, enabled=False)
    return rule_service.update_rule(
        event_key=event_key, actor=actor, channels={channel: {"enabled": False}}
    )


def _an_occupant(actor, tenant, *, label, name):
    """One account occupying its own unit, through the real create door."""
    _customer, account, unit = _mover(actor, tenant, label=label, name=name)
    return account, unit


def _move_out(actor, account):
    """S20 for real. Returns the wizard's own response."""
    return customers_services.move_out(
        actor, str(account.id), {"moved_out_on": account.opened_at.isoformat()}
    )


def _move_in(actor, account, *, name="Newcomer, Bea"):
    """S19 for real, chained onto an account that has just moved out.

    `opened_at` is the day AFTER the outgoing tenancy ended — BR-CUS-056, which
    `_occupancy_guards` enforces by name (`customers.account
    .start_on_prior_move_day`). Two tenancies cannot share a boundary day.
    """
    return customers_services.move_in(
        actor,
        str(account.id),
        {
            "account_type": "residential",
            "status": "active",
            "opened_at": (account.opened_at + timedelta(days=1)).isoformat(),
            "contact": {"full_name": name, "email": "bea@example.test"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _a_moved_out_then_in(actor, tenant, *, label="9 Cardamom Walk", name="Probe, A"):
    """The whole chain S20 → S19, which is how a move-in actually reaches the
    product: the outgoing tenancy ends and the next occupant takes the unit."""
    account, _unit = _an_occupant(actor, tenant, label=label, name=name)
    out = _move_out(actor, account)
    incoming = _move_in(actor, account)
    return account, out, incoming


def _a_plan_with_a_missed_instalment(tenant, account, *, seqs=3):
    """A live plan whose FIRST instalment came and went unpaid.

    Written through the ORM on purpose and stated as such: `payment_plan
    .build_schedule` is a 🔒 money path and this file is not testing it. What is
    under test is which MESSAGE a missed instalment sends and what it is keyed
    on, and a schedule assembled here reaches `plan_notices_due` by the same
    route a real one does.
    """
    plan = PaymentPlan.objects.create(
        tenant=tenant,
        account_id=account.id,
        status="active",
        currency="USD",
        total_amount=Decimal("300.0000"),
        down_payment=Decimal("0.0000"),
        installment_count=seqs,
        cadence="monthly",
        proposed_on=PLAN_START - timedelta(days=7),
        signed_on=PLAN_START - timedelta(days=7),
    )
    for seq in range(1, seqs + 1):
        PaymentPlanInstallment.objects.create(
            tenant=tenant,
            plan=plan,
            seq=seq,
            due_date=PLAN_START + timedelta(days=30 * (seq - 1)),
            amount=Decimal("100.0000"),
            currency="USD",
        )
    return plan


def _send_plan_notices(plan, *, on, actor, channels=("pdf_print",)):
    """The real writer, on the day after instalment 1 fell due.

    `channels` is the CALLER's ask and defaults to paper, exactly as
    `send_plan_notices` does. The suppression cases pass email as well, because
    a rule can only ever REMOVE (`services.channel_decision` step 2): a switch
    over a channel nobody asked for has nothing to take away, and a case that
    forgot to ask would "prove" a suppression that never happened.
    """
    return payments_notices.send_plan_notices(plan, as_of=on, actor=actor, channels=channels)


# ══════════════════════════════════════════════════════════════════════════
# B10 · 1 — THE THREE EVENTS EXIST AND NAME THE WORDING THAT WAS ALREADY THERE
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b10__the_three_events_are_rows_on_set_12():
    """The vocabulary is a CONSTANT, so a mistyped key is a refusal at run time
    inside a committed move. This is that check, moved to build time."""
    missing = {EVENT_MOVE_IN, EVENT_MOVE_OUT, EVENT_PLAN_MISSED} - set(rule_catalog.EVENT_KEYS)
    assert not missing, (
        f"SET-12 has no row for {sorted(missing)}. A writer naming an event this "
        "platform cannot fire is refused by `queue_document` — at the END of the "
        "job it was reporting on."
    )


def test_cr048_b10__each_event_names_the_wording_that_was_already_seeded():
    """⛔ **THE OMISSION WAS NEVER THE WORDING.** All three bodies have been
    planted on every tenant since 2026-08-16; what was missing was a rule that
    could send them. An event naming a class nobody seeds would look identical on
    the settings screen and render as nothing anybody wrote."""
    seeded = {seed.code for seed in seed_templates.SEEDABLE}
    for event_key, expected in (
        (EVENT_MOVE_IN, customer_events.TEMPLATE_MOVE_IN),
        (EVENT_MOVE_OUT, customer_events.TEMPLATE_MOVE_OUT),
        (EVENT_PLAN_MISSED, payments_notices.MISSED_TEMPLATE_CODE),
    ):
        event = rule_catalog.event(event_key)
        assert expected in event.template_classes.values(), (
            f"{event_key} does not name {expected!r} on any channel, so adopting it "
            "takes nothing out of B9's coverage count."
        )
        assert expected in seeded, (
            f"{expected!r} is not a class this platform seeds wording for. An event "
            "pinned to it queues rows that render as nothing anybody wrote."
        )


def test_cr048_b10__the_seams_reach_real_functions():
    """Hard-won law 1 — a docstring claiming a seam is wired is not the wiring.

    Both seams resolve their entry point BY NAME at call time (B1: customers and
    payments may not import notifications), so nothing type-checks the contract
    and an entry point renamed one side of the boundary fails silently on the
    other."""
    resolved = notifications_seam.entry_points()
    # ⚠ TWO ENTRY POINTS UNTIL 2026-08-30; CR-048 wave B task B11 added the
    # account-closed and rate-plan-change letters to the same seam. Every one
    # of them is asserted, because a seam that resolves three of four is
    # exactly as broken as one that resolves none — and reads as working.
    for name, entry in resolved.items():
        assert callable(entry), (
            f"{name!r} does not resolve to a callable on the notifications side, "
            "so this seam is a string that names nothing. Renaming an entry point "
            "one side of a by-name boundary fails silently on the other."
        )
    # ⚠ **FOUR UNTIL 2026-09-12, AND IT IS SEVEN FOR TWO DIFFERENT REASONS.**
    # `CR-094-BRC01` wave K added a fifth WRITE — the message a clerk types on
    # an account — and, beside it, the two READS its dialog needs (which kinds
    # may be composed, and whether a channel actually delivers). The reads are
    # resolved by name exactly as the writes are, for the same reason: a name
    # that stops resolving is a control that silently does nothing.
    # ⚠ **TEN SINCE 2026-10-05.** Two READS arrived without moving this count
    # (`READ_MESSAGE_TEMPLATES`, `READ_MOVE_IN_MESSAGE_PLAN` — it read 9 == 7 on
    # 381948c90, a red dated to `dcc883047`'s figure), and `DEF-CUS-9743` added
    # the move-in's SERVICE AGREEMENT write. Named, so the next one moves it.
    assert set(resolved) == {
        notifications_seam.WRITE_MOVE_IN,
        notifications_seam.WRITE_SERVICE_AGREEMENT,
        notifications_seam.WRITE_MOVE_OUT,
        notifications_seam.WRITE_ACCOUNT_CLOSED,
        notifications_seam.WRITE_RATE_PLAN_CHANGE,
        # DEF-NOT-10649 (2026-10-29) — the cut and the restoration tell the customer.
        notifications_seam.WRITE_SERVICE_DISCONNECTED,
        notifications_seam.WRITE_SERVICE_RESTORED,
        notifications_seam.WRITE_ACCOUNT_MESSAGE,
        notifications_seam.READ_MESSAGE_KINDS,
        notifications_seam.READ_CHANNEL_REACHABILITY,
        notifications_seam.READ_MESSAGE_TEMPLATES,
        notifications_seam.READ_MOVE_IN_MESSAGE_PLAN,
    }
    # And the keys those entry points name are real rows, checked from the
    # catalogue itself rather than from this file's own spelling. B11's three
    # are included: `declared_events()` raises `KeyError` on a key that is not
    # a row on SET-12, which is the failure a mistyped key would otherwise show
    # as a refusal at the end of a committed move, close-out or payment.
    assert {event.key for event in customer_events.declared_events()} == {
        EVENT_MOVE_IN,
        EVENT_MOVE_OUT,
        customer_events.EVENT_ACCOUNT_CLOSED,
        customer_events.EVENT_DEPOSIT_RECEIVED,
        customer_events.EVENT_RATE_PLAN_CHANGED,
        customer_events.EVENT_SERVICE_DISCONNECTED,
        customer_events.EVENT_SERVICE_RESTORED,
    }


# ══════════════════════════════════════════════════════════════════════════
# B10 · 2 — THE MOVE-IN AND THE MOVE-OUT ACTUALLY SEND SOMETHING
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b10__a_move_out_and_a_move_in_each_queue_exactly_one_document(brazos, dana):
    """**THE HEADLINE CASE.** The teardown's sentence was *"a customer moving in
    is told NOTHING"*; this is the whole chain, for real, ending in two letters.

    ⚠ **THE COUNT MOVED FROM TWO ROWS TO FOUR ON 2026-08-30, AND THE SUBJECT OF
    THIS CASE DID NOT MOVE AT ALL.** It was called
    `..._each_queue_exactly_one_message` and asserted `rows.count() == 2` with
    the message *"one move-out and one move-in queued {n} messages; each sends
    exactly one, on email."* Then BR-NOT-024's print floor widened from four
    source kinds to six and `move` became one of them, so each letter is now
    queued on TWO channels — the email the writer asks for, plus the paper copy
    the floor adds. Two letters, four rows.

    **The arithmetic is what changed; the promise is not.** So the case now
    counts DOCUMENTS, which is the number the teardown's sentence was ever
    about — a customer moving in is told something, once — and asserts the row
    count underneath it so a floor that silently stopped applying is still
    caught.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        assert _queue(brazos, source_type="move").count() == 0

        account, out, incoming = _a_moved_out_then_in(dana, brazos)

        assert notifications_seam.MOVE_MESSAGE_QUEUED in _codes(
            out["move_message"]
        ), f"the move-out queued nothing: {out['move_message']}"
        assert notifications_seam.MOVE_MESSAGE_QUEUED in _codes(
            incoming["move_message"]
        ), f"the move-in queued nothing: {incoming['move_message']}"
        # `DEF-CUS-9743` — the move-in's SERVICE AGREEMENT is a third move
        # document (its own key, on paper, no event); it is asserted on its own
        # below so the welcome/final-bill arithmetic here is unchanged.
        agreement = _queue(brazos, source_type="move", template_code="contract_service_agreement")
        assert {row.channel for row in agreement} == {notification_models.CHANNEL_PRINT}
        assert {str(row.account_id) for row in agreement} == {str(incoming["id"])}
        rows = _queue(brazos, source_type="move").exclude(template_code="contract_service_agreement")
        documents = {(row.source_id, row.copy_no) for row in rows}
        assert len(documents) == 2, (
            f"one move-out and one move-in produced {len(documents)} letters; each "
            "sends exactly one."
        )
        assert rows.count() == 4, (
            f"two letters on two channels each is four rows and this queued "
            f"{rows.count()}. Since 2026-08-30 a move message is queued on the "
            "email the writer asks for AND the paper copy BR-NOT-024's floor "
            "adds; a count of two here means the floor stopped applying."
        )
        assert {row.event_key for row in rows} == {EVENT_MOVE_IN, EVENT_MOVE_OUT}
        assert {row.template_code for row in rows} == {
            customer_events.TEMPLATE_MOVE_IN,
            customer_events.TEMPLATE_MOVE_OUT,
        }
        # Both channels on BOTH letters, named rather than counted — four rows
        # would also be two letters on one channel and two on another.
        for event_key in (EVENT_MOVE_IN, EVENT_MOVE_OUT):
            assert {row.channel for row in rows.filter(event_key=event_key)} == {
                notification_models.CHANNEL_EMAIL,
                notification_models.CHANNEL_PRINT,
            }, f"{event_key} did not go out on both the asked channel and the floor"
        # And the move-in message belongs to the NEW account, not the outgoing
        # one — the letter goes to the person who arrived. Asked of every row of
        # that letter, because the floor's copy is the same letter.
        welcome_rows = rows.filter(event_key=EVENT_MOVE_IN)
        assert welcome_rows.count() == 2
        for welcome in welcome_rows:
            assert str(welcome.account_id) == str(incoming["id"])
            assert str(welcome.account_id) != str(account.id)


def test_cr048_b10__the_message_is_keyed_on_the_move_record_not_the_account(brazos, dana):
    """⛔ **THE TRAP THE CR NAMES, PINNED FROM BOTH SIDES.**

    Key a move message on the ACCOUNT and the move-out letter finds the welcome
    letter's row — same tenant, same source kind, same account, same channel,
    same copy number — and dedupes into it. `created=False`, no error, the
    move-out completes, and the customer is never told their final bill is
    coming. Nothing about that looks like a failure.

    So this asserts the KEY itself: each message's `source_id` is its own move
    record's id, and the two ids differ.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        account, out, incoming = _a_moved_out_then_in(dana, brazos, label="4 Ember Row")

        rows = {row.event_key: row for row in _queue(brazos, source_type="move")}
        assert str(rows[EVENT_MOVE_OUT].source_id) == out["move_record_id"]
        assert str(rows[EVENT_MOVE_IN].source_id) == incoming["move_record_id"]
        assert rows[EVENT_MOVE_OUT].source_id != rows[EVENT_MOVE_IN].source_id, (
            "both move messages share one source id, so the second one dedupes "
            "into the first. Key them on the MOVE RECORD, never the account."
        )
        # The ids are real move records, both of them, and each is the right kind.
        by_id = {str(row.id): row for row in moves.MoveRecord.objects.all()}
        assert by_id[out["move_record_id"]].kind == moves.KIND_MOVE_OUT
        assert by_id[incoming["move_record_id"]].kind == moves.KIND_MOVE_IN


def test_cr048_b10__a_replayed_move_message_writes_nothing_twice(brazos, dana):
    """CLAUDE.md rule 6. The DATABASE does the refusing, which is the only
    guarantee that survives a retry that never called the function twice."""
    with tenant_ctx(brazos):
        _seeded(dana)
        _account, out, _incoming = _a_moved_out_then_in(dana, brazos, label="12 Quill Lane")
        before = _queue(brazos, source_type="move").count()

        again = customer_events.queue_move_out_final(
            move_record_id=out["move_record_id"],
            account_id=out["id"],
            effective_on=date.fromisoformat(str(out["closed_at"])[:10]),
            actor=dana,
        )
        assert again.created is False
        assert again.message_id is not None
        assert _queue(brazos, source_type="move").count() == before


# ══════════════════════════════════════════════════════════════════════════
# B10 · 3 — THE SWITCH WORKS, AND THE MOVE STILL COMPLETES
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b10__switching_the_welcome_off_stops_the_email_and_not_the_letter(brazos, dana):
    """**CR-048's first acceptance case, and BOTH halves are still asserted.**

    Either half alone passes on a broken build: a lane that never queues anything
    satisfies "the switch worked", and a lane that ignores the rule satisfies
    "the move-in completes". The pair is the test.

    ⚠ **THE CONSEQUENCE WAS REVERSED ON 2026-08-30, NOT SOFTENED, AND THE OLD
    ONE IS QUOTED RATHER THAN DELETED.** This case was called
    `..._a_utility_that_switches_the_welcome_off_gets_no_row` and its docstring
    read: *"And the row's absence is REAL rather than a floor being invisible: a
    move message has no print floor (BR-NOT-024 names four source kinds and a
    move is none of them), so switching the event off leaves nothing at all."*
    It asserted::

        assert _queue(brazos, source_type="move", event_key=EVENT_MOVE_IN).count() == 0
        assert notifications_seam.MOVE_MESSAGE_SUPPRESSED in _codes(incoming["move_message"])
        assert _queue(brazos, source_type="move", event_key=EVENT_MOVE_OUT).count() == 1

    The PO widened the floor from four source kinds to six that day, and `move`
    is one of them — **not separately ruled, but taken under the principle the
    ruling settled**, because the floor is per SOURCE KIND and that kind carries
    the letter announcing a customer's final bill. So the welcome is still
    POSTED when the event is switched off. That is the floor doing exactly what
    the disconnection letter made it for: a platform rule about what a document
    is, which the notifications screen does not edit.

    **What this case is FOR did not change — only the shape of the evidence.**
    The switch must reach the queue and it does: the email is gone. The absence
    must be visible and it is, on `problems`. And the letter that survives is
    the floor's, which the assertions name so that a floor quietly ceasing to
    apply reads as a failure here rather than as a tidier number.

    ⚠ **THE GENERIC PROPERTY — an event switched off with NO floor queues
    nothing at all — did not lose its test.** It moved, in
    `test_cr048_a1_rule_at_queue_time.py`, to `bulk_action`, which is one of the
    four kinds that genuinely have no floor. It cannot be asked of a move any
    more without asserting the opposite of the rule.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        _switch_off(EVENT_MOVE_IN, dana)

        account, _unit = _an_occupant(dana, brazos, label="7 Larkin Way", name="Off, Sam")
        _move_out(dana, account)
        incoming = _move_in(dana, account)

        welcome_rows = _queue(brazos, source_type="move", event_key=EVENT_MOVE_IN)
        # THE SWITCH REACHED THE QUEUE. This is the half CR-048 was raised for,
        # and it is the email — the only channel the utility controls here.
        assert (
            welcome_rows.filter(channel=notification_models.CHANNEL_EMAIL).count() == 0
        ), (
            "the welcome event is switched OFF on this utility's settings screen "
            "and an EMAIL was queued anyway. CR-048's headline is that the "
            "settings screen reaches the queue."
        )
        # …and what is left is the floor's copy, exactly one, on paper.
        assert [row.channel for row in welcome_rows] == [notification_models.CHANNEL_PRINT], (
            "switching the welcome off must leave the printed letter and nothing "
            "else. BR-NOT-024's floor covers `move` since 2026-08-30 and a floor "
            "channel is not a tenant setting; a count of zero here means the "
            "floor stopped applying, and more than one means the switch did not "
            "reach the queue."
        )
        # THE SUPPRESSION IS NOT SILENT. It is no longer reported as
        # MOVE_MESSAGE_SUPPRESSED — that code fires only when the write is
        # EMPTY, and the floor now means it never is for a move — so the reason
        # travels on the write's own problems, which the seam passes through
        # verbatim. A message nobody can see was suppressed is the same defect in
        # the other direction, whichever code carries it.
        codes = _codes(incoming["move_message"])
        assert notification_services.QUEUE_EVENT_SWITCHED_OFF in codes, (
            f"the suppression was silent: {incoming['move_message']}."
        )
        assert notifications_seam.MOVE_MESSAGE_QUEUED in codes, (
            "the printed letter was queued, so the seam must say so rather than "
            "reporting the whole message suppressed."
        )
        # THE MOVE-IN STILL COMPLETED. A real account, occupying a real unit.
        created = customers_models.Account.objects.get(id=incoming["id"])
        assert created.unit_id == account.unit_id
        assert created.opened_at == account.opened_at + timedelta(days=1)
        # And the move-out message, whose own event is still ON, went as normal
        # on BOTH channels — so the switch is per EVENT and not a blanket mute.
        # Two rows here where the superseded version expected one, for the same
        # reason as everywhere else in this file: the floor widened.
        assert {
            row.channel
            for row in _queue(brazos, source_type="move", event_key=EVENT_MOVE_OUT)
        } == {notification_models.CHANNEL_EMAIL, notification_models.CHANNEL_PRINT}


# ══════════════════════════════════════════════════════════════════════════
# B10 · 4 — THE WORK SURVIVES A NOTIFICATION FAILURE.  ⚠ POSTGRESQL ONLY.
# ══════════════════════════════════════════════════════════════════════════
def _explodes(**_kwargs):
    """A REAL database error, not a mock. `SELECT 1/0` aborts the surrounding
    Postgres transaction exactly as a refused INSERT does — which is the state a
    `try/except` cannot recover from and a SAVEPOINT can."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 / 0")


@requires_postgres
def test_cr048_b10__a_database_error_in_the_welcome_cannot_lose_the_move_in(
    brazos, dana, monkeypatch
):
    """⚠ **THIS CASE ONLY MEANS ANYTHING ON POSTGRESQL, and that is the finding**
    (hard-won law 14).

    A statement that errors inside a Postgres transaction ABORTS the whole
    transaction: the `except` catches the exception, the new account and its move
    record are already doomed, and the COMMIT fails afterwards with *"current
    transaction is aborted"*. SQLite has no such state, so a `try/except` alone
    passes there and loses a customer's account here.

    This drives a REAL database error through the seam and then reads the account
    back in a NEW transaction — the only way to prove the SAVEPOINT is doing the
    work rather than the `except`.
    """
    monkeypatch.setattr(customer_events, "queue_move_in_welcome", _explodes)
    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="21 Ash Bend", name="Boom, Kit")
        _move_out(dana, account)
        incoming = _move_in(dana, account)

    with tenant_ctx(brazos):
        # A NEW transaction. The point is that the move-in COMMITTED.
        created = customers_models.Account.objects.filter(id=incoming["id"]).first()
        assert created is not None, (
            "the new account did not survive a failed notification. Without the "
            "savepoint the aborted transaction takes the whole move-in with it at "
            "COMMIT — the account, its opening reads and its move record."
        )
        assert moves.MoveRecord.objects.filter(id=incoming["move_record_id"]).exists()
    assert notifications_seam.MOVE_MESSAGE_ERROR in _codes(incoming["move_message"])


@requires_postgres
def test_cr048_b10__a_database_error_in_the_final_letter_cannot_lose_the_move_out(
    brazos, dana, monkeypatch
):
    """The same law on the other wizard. A move-out writes `closed_at`, ends every
    open service agreement and frees the unit; all of it is lost at COMMIT if the
    notification's failure is merely caught."""
    monkeypatch.setattr(customer_events, "queue_move_out_final", _explodes)
    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="5 Vetch Close", name="Boom, Lee")
        out = _move_out(dana, account)

    with tenant_ctx(brazos):
        closed = customers_models.Account.objects.get(id=account.id)
        assert closed.closed_at == account.opened_at, (
            "the move-out did not survive a failed notification: `closed_at` is "
            f"{closed.closed_at!r}."
        )
        assert moves.MoveRecord.objects.filter(id=out["move_record_id"]).exists()
    assert notifications_seam.MOVE_MESSAGE_ERROR in _codes(out["move_message"])


# ══════════════════════════════════════════════════════════════════════════
# B10 · 5 — THE MISSED PAYMENT-PLAN INSTALMENT
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b10__a_missed_instalment_sends_the_wording_that_exists(brazos, dana):
    """⛔ **THE TRIGGER WAS NEVER MISSING — WHAT IT POINTED AT WAS.**

    `send_plan_notices` has queued a missed-instalment message since 2026-08-11,
    pinned to `plan_installment_missed`. That string is a NOTICE-HISTORY type;
    no row in `catalogs.LISTINGS` or `seed_templates.SEEDABLE` has ever declared
    it, so every one of those messages was queued against wording that does not
    exist. The seeded body is `plan_notice_missed`, and this asserts the queue
    row now names it.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="88 Sorrel Road", name="Plan, Dee")
        plan = _a_plan_with_a_missed_instalment(brazos, account)
        day_after = PLAN_START + timedelta(days=1)

        result = _send_plan_notices(plan, on=day_after, actor=dana)

        rows = _queue(brazos, source_type="plan", event_key=EVENT_PLAN_MISSED)
        assert rows.count() == 1, (
            f"a missed instalment queued {rows.count()} messages; problems=" f"{result.problems}"
        )
        row = rows.first()
        assert row.template_code == payments_notices.MISSED_TEMPLATE_CODE
        assert row.template_code != NOTICE_PLAN_MISSED, (
            "the queue row is pinned to a NOTICE-HISTORY type, not a template "
            "class. Nothing seeds that code, so the letter renders as nothing "
            "anybody wrote."
        )
        assert row.template_code in {seed.code for seed in seed_templates.SEEDABLE}


def test_cr048_b10__the_missed_notice_is_keyed_on_the_instalment_not_the_plan(brazos, dana):
    """⛔ **THE SAME TRAP, ONE MODULE OVER, AND IT WAS ALREADY LIVE.**

    Every plan notice was keyed on (tenant, "plan", plan_id, channel, copy_no) —
    the same tuple for the reminder, the missed notice, the second notice, and
    every instalment of a twelve-month plan. The second write finds the first
    row and returns `created=False`: no error, no gap in the trail, and a
    customer chased once and never again.

    This sends the reminder for instalment 2 AND the missed notice for
    instalment 1 on days that really produce both, and asserts they are two
    rows rather than one.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="3 Bracken Hill", name="Key, Ivo")
        plan = _a_plan_with_a_missed_instalment(brazos, account)

        # Instalment 1 fell due on PLAN_START and was not met → missed notice on
        # PLAN_START + 1. Instalment 2 is due 30 days later → reminder 3 days
        # before it. Two different notices, two different instalments.
        _send_plan_notices(plan, on=PLAN_START + timedelta(days=1), actor=dana)
        _send_plan_notices(plan, on=PLAN_START + timedelta(days=27), actor=dana)

        rows = list(_queue(brazos, source_type="plan"))
        assert len(rows) == 2, (
            f"two plan notices produced {len(rows)} queue rows. Keyed on the PLAN "
            "they share one idempotency tuple and the second silently dedupes into "
            f"the first: {[(r.template_code, str(r.source_id)) for r in rows]}"
        )
        missed = [row for row in rows if row.event_key == EVENT_PLAN_MISSED]
        assert len(missed) == 1
        first_instalment = plans.PaymentPlanInstallment.objects.get(plan=plan, seq=1)
        assert str(missed[0].source_id) == str(first_instalment.pk), (
            "the missed notice is not keyed on the instalment it is about, so the "
            "letter about instalment 3 will collide with the letter about "
            "instalment 4."
        )
        # And the trail records both, which is what a regulator reads.
        assert {row["notice_type"] for row in payments_notices.notice_history_for(limit=50)} >= {
            NOTICE_PLAN_MISSED,
            NOTICE_PLAN_REMINDER,
        }


def test_cr048_b10__the_print_letter_still_goes_when_the_email_is_switched_off(brazos, dana):
    """**BR-NOT-024, demonstrated where it actually bites.**

    A plan notice rides `plan`, which the PO's ruling of 2026-08-29 names as one
    of the kinds print is the floor on. So a utility that switches the
    missed-instalment EMAIL off still prints the letter — and the suppression is
    recorded on the surviving row rather than vanishing.

    ⚠ **THE CONTRAST THIS CASE WAS PAIRED WITH IS GONE, AND SAYING SO IS THE
    POINT OF THIS PARAGRAPH.** It ended: *"This is the deliberate contrast with
    the move-in case above, where there is no floor and switching off really
    does mean nothing."* On 2026-08-30 the PO widened the floor from four source
    kinds to six and `move` became one of them, so the move-in case above now
    demonstrates the SAME behaviour this one does rather than its opposite. The
    contrast still exists — it is just no longer a customer letter that carries
    it. `test_cr048_b6__a_suppression_is_counted_where_it_can_be_and_named_where
    _it_cannot` holds it now, with a staff bulk summary, which rides one of the
    four kinds that genuinely have no floor.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        _switch_off(EVENT_PLAN_MISSED, dana, channel=notification_models.CHANNEL_EMAIL)
        account, _unit = _an_occupant(dana, brazos, label="14 Teasel Row", name="Floor, Nia")
        plan = _a_plan_with_a_missed_instalment(brazos, account)

        _send_plan_notices(
            plan,
            on=PLAN_START + timedelta(days=1),
            actor=dana,
            channels=(notification_models.CHANNEL_PRINT, notification_models.CHANNEL_EMAIL),
        )

        rows = list(_queue(brazos, source_type="plan", event_key=EVENT_PLAN_MISSED))
        assert [row.channel for row in rows] == [notification_models.CHANNEL_PRINT], (
            "BR-NOT-024 makes print the floor on a plan letter and no toggle "
            f"removes it; the queue holds {[row.channel for row in rows]}."
        )
        assert rows[0].rule_suppressed_channels == notification_models.CHANNEL_EMAIL, (
            "the email suppression left no trace on the surviving row, so the "
            '"Last 30 days" rail cannot say the switch did anything.'
        )


# ══════════════════════════════════════════════════════════════════════════
# B10 · 6 — B9's COVERAGE COUNT FALLS ON ITS OWN
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b10__the_coverage_count_falls_from_16_to_13_with_nobody_editing_it():
    """**CR-048's fourth acceptance case, and the reason B9 built a derivation.**

    Three events adopted three seeded classes, so the "wording with no rule"
    figure must drop by exactly three — computed, never typed. The classes must
    be GONE from the list, not merely fewer in number: a count that fell because
    some unrelated class dropped out would pass a bare number.

    ⚠ **THE EXPECTED FIGURE MOVED 13 → 0 ON 2026-08-30 (CR-048 wave B task
    B11), AND THE ASSERTION CHANGED SHAPE WITH IT.** B10 could assert a literal
    13 because it knew exactly which three it had adopted. B11 adopted the
    remaining thirteen and closed the gap completely, and a literal `== 0` here
    would go red the day somebody seeds a new wording — which is the ordinary
    way this platform grows and NOT a regression. So the property asserted is
    the one that actually matters and holds at every size: **every class this
    platform seeds is either named by an event, reached by a live writer, or
    not a message at all.** The count is reported in the failure message so a
    reader still sees the figure, and it is 0 today.
    """
    coverage = rule_catalog.coverage()
    gap = set(coverage["seeded_wording_without_rule"])
    assert coverage["seeded_wording_without_rule_count"] == 0, (
        f"the gap is {coverage['seeded_wording_without_rule_count']}, not 0 — "
        f"{sorted(gap)} have wording seeded on every tenant and no rule that "
        "could ever send them. Wave B11 closed this to zero on 2026-08-30; a "
        "class that arrives after it needs an event row (a LIVE one, or one "
        "DRAWN AND REFUSED by name with the question that owns its absence — "
        "BR-NOT-018), and its class appended to ADOPTED_SINCE_TEARDOWN."
    )
    for adopted in rule_catalog.ADOPTED_SINCE_TEARDOWN:
        assert adopted not in gap, (
            f"{adopted!r} is still counted as wording with no rule, so the event "
            "that names it is not naming it on any channel."
        )


def test_cr048_b10__the_teardown_figure_still_reconciles():
    """⚠ **THE TWO COUNTS PARTED COMPANY ON PURPOSE, AND THE BRIDGE IS CODE.**

    B9 kept `TEARDOWN_CLAIMS_UNRULED_COUNT = 16` beside the derived figure and
    said in as many words that *"a typed-in 16 goes stale on the day it stops
    being true, which is the day wave B10/B11 lands"*. This IS that day.

    What must never happen is the two disagreeing with no stated reason. So the
    arithmetic is asserted rather than the equality.

    ⚠ **B11 TOOK IT TO THE BOUNDARY THE SAME DAY: 0 derived + 16 adopted = 16
    counted.** That is the first time this bridge has been tested at either end,
    and it is the strongest form of the check — every one of the teardown's
    sixteen is accounted for by name, and no class left the gap by a route
    nobody wrote down. A RENAMED or DROPPED wording would break it, which is
    exactly what it is for.
    """
    reconciliation = rule_catalog.coverage()["teardown_reconciliation"]
    assert reconciliation["reconciles"], reconciliation
    assert (
        reconciliation["derived_count_now"] + reconciliation["adopted_since_teardown_count"]
        == reconciliation["teardown_count"]
    )
    adopted = set(reconciliation["adopted_since_teardown"])
    # B10's three, still named through the constants their writers publish, so a
    # renamed template code fails here rather than drifting.
    assert {
        customer_events.TEMPLATE_MOVE_IN,
        customer_events.TEMPLATE_MOVE_OUT,
        payments_notices.MISSED_TEMPLATE_CODE,
    } <= adopted
    # B11's thirteen, and the count is what makes "all sixteen" checkable.
    assert payments_notices.UPCOMING_TEMPLATE_CODE in adopted
    assert len(adopted) == 16, (
        f"{len(adopted)} classes are recorded as adopted since the 2026-08-29 "
        "teardown and its figure was 16. B10 took three and B11 took thirteen; "
        f"the set is {sorted(adopted)}."
    )


def test_cr048_b10__email_account_closed_was_left_for_b11_and_b11_took_it():
    """⛔ **THIS CASE WAS A NEGATIVE AND IT IS NOW A POSITIVE — deliberately.**

    B10 wrote it to prove it had NOT widened its own lane: *"`email_account_
    closed` is the FOURTH seeded message in the same module and adding it would
    have been one more line. It is B11's."* The assertion was that the class was
    still in the gap, and it went red on 2026-08-30 when B11 adopted it — which
    is the guard doing its job, not breaking.

    Deleting it would throw away the only place the handover is written down, so
    it is INVERTED instead: the class B10 left is now named by `account_closed`,
    and the event that names it has a LIVE writer rather than a blocker. Both
    halves matter — a row that merely exists is what CR-048 calls decoration.
    """
    assert "email_account_closed" not in rule_catalog.seeded_wording_without_rule(), (
        "`email_account_closed` is back in the gap. B11 adopted it on 2026-08-30 "
        "with the `account_closed` event; if that row was removed, the coverage "
        "figure and ADOPTED_SINCE_TEARDOWN move with it."
    )
    closed = rule_catalog.event("account_closed")
    assert closed.template_classes == {notification_models.CHANNEL_EMAIL: "email_account_closed"}
    assert closed.trigger_blocked_by is None, (
        "the account-closed event carries a blocker, so nothing fires it — which "
        "is a switch on the settings screen that changes nothing, the exact "
        "defect CR-048 exists to fix. Its writer is customers.close_out."
    )
    assert closed.source_type == "account"


# ══════════════════════════════════════════════════════════════════════════
# B6 · THE PER-EVENT COUNTS
# ══════════════════════════════════════════════════════════════════════════
def test_cr048_b6__the_rail_counts_what_was_actually_queued(brazos, dana):
    """**Real numbers instead of zeroes**, measured against work this test did.

    The window ends on a NAMED date (BR-TEN-043), so this cannot pass in August
    and fail in September.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        today = _rail_today()
        before = delivery_counts.for_event(EVENT_MOVE_IN, today)
        assert before["queued"] == 0
        assert before["ever_attributed"] is False, (
            "a zero here means two different things — a quiet month, and a writer "
            "that has never fired. `ever_attributed` is what separates them."
        )

        _a_moved_out_then_in(dana, brazos, label="30 Fennel Gate")

        rail = delivery_counts.for_event(EVENT_MOVE_IN, today)
        # ⚠ **THE COUNT MOVED FROM 1 TO 2 ON 2026-08-30 AND NOTHING ABOUT THIS
        # CASE'S SUBJECT MOVED.** `queued` counts ROWS (BR-BIL-016 — one
        # delivery record per document per channel), and BR-NOT-024's print
        # floor widened from four source kinds to six, so a move-in welcome is
        # now queued on the email the writer asks for AND the paper copy the
        # floor adds. `documents` is still 1, which is the number a screen
        # showing "how many customers heard from us" reads — and the fact that
        # the two now differ is exactly why the rail reports both.
        assert rail["queued"] == 2
        assert rail["documents"] == 1
        assert rail["held"] == 0
        assert rail["ever_attributed"] is True
        assert rail["by_channel"][notification_models.CHANNEL_EMAIL]["queued"] == 1
        # Named per channel as well as totalled, so a total of 2 that was really
        # two emails, or two letters, would still fail here.
        assert rail["by_channel"][notification_models.CHANNEL_PRINT]["queued"] == 1
        # The window the response STATES is the window it measured — a rail
        # labelled with one month and counted over another is worse than none.
        assert rail["window_days"] == delivery_counts.WINDOW_DAYS == 30
        assert rail["since"] == (today - timedelta(days=29)).isoformat()
        assert rail["until"] == today.isoformat()
        # And the arithmetic itself, on a NAMED date, so the window function is
        # pinned independently of when the suite runs.
        start_date, end_date, start_at, end_at = delivery_counts.window(TODAY)
        assert (start_date, end_date) == (TODAY - timedelta(days=29), TODAY)
        assert start_at.date() == start_date
        assert end_at.date() == TODAY + timedelta(days=1), (
            "the window must be half-open at the far end, or a message written at "
            "23:59 on the last day falls outside the thirty days it belongs to."
        )


def test_cr048_b6__a_message_outside_the_window_is_not_counted(brazos, dana):
    """The window is a WINDOW. A rail that counted everything ever would read the
    same on the day a utility went live and a year later."""
    with tenant_ctx(brazos):
        _seeded(dana)
        _a_moved_out_then_in(dana, brazos, label="2 Yarrow Path")

        today = _rail_today()
        inside = delivery_counts.for_event(EVENT_MOVE_IN, today)
        outside = delivery_counts.for_event(EVENT_MOVE_IN, today + timedelta(days=90))
        # 2, not 1: one welcome letter on two channels. The count moved on
        # 2026-08-30 when BR-NOT-024's print floor widened to cover `move`, so
        # the email the writer asks for is now joined by a paper copy. What this
        # case is about — that the window is a window — is untouched; the number
        # inside it is simply larger.
        assert inside["queued"] == 2
        assert outside["queued"] == 0, (
            "a message from ninety days ago is still being counted in the last " "thirty days."
        )
        # …and it is still an event this platform HAS fired, which is a different
        # fact from "nothing happened this month".
        assert outside["ever_attributed"] is True


def test_cr048_b6__delivered_and_bounced_are_never_derived_from_queued_rows(brazos, dana):
    """⛔ **THE SINGLE MOST TEMPTING LIE IN THIS MODULE.**

    Every row counted here is a row on a QUEUE. BR-NOT-013 puts delivery out of
    this release on every channel and nothing in this repo writes `delivered` or
    `bounced`. A `delivered` count taken from queued rows would say "one customer
    received this" about a letter sitting in a table.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        _a_moved_out_then_in(dana, brazos, label="11 Comfrey Lane")
        rail = delivery_counts.for_event(EVENT_MOVE_IN, _rail_today())

    # 2, not 1: one welcome letter on two channels since BR-NOT-024's print
    # floor widened to cover `move` on 2026-08-30. The number is here only to
    # prove rows WERE counted, so that the absences asserted below are absences
    # of a figure this rail could otherwise have invented — a `delivered` count
    # derived from queued rows would have moved from 1 to 2 with it.
    assert rail["queued"] == 2
    assert "delivered" not in rail and "bounced" not in rail, (
        "a delivered/bounced figure has appeared on the rail. Neither can be "
        "computed here: both are PROVIDER facts and no adapter exists on any "
        "channel (BR-NOT-013)."
    )
    assert set(rail["not_reported"]) == {"delivered", "bounced"}
    for reason in rail["not_reported"].values():
        assert reason and not reason.isdigit()


def test_cr048_b6__a_suppression_is_counted_where_it_can_be_and_named_where_it_cannot(brazos, dana):
    """**The honest half of B6, in both directions.**

    * A PLAN letter has a print floor, so a suppressed email still leaves a row
      to record it on and the count is exact.
    * A STAFF BULK SUMMARY has none, so an event switched off entirely leaves
      nothing at all — and the rail says *unavailable* rather than *0*, because
      a zero would tell a System Admin who just switched it off that their
      switch does nothing.

    ⚠ **THE SECOND EXAMPLE WAS A MOVE LETTER AND IS NOW A STAFF SUMMARY
    (2026-08-30).** The bullet read: *"A MOVE letter has none, so an event
    switched off entirely leaves nothing at all"*, and the assertion was::

        unrecordable = delivery_counts.for_event(EVENT_MOVE_IN, _rail_today())
        assert unrecordable["suppressed"] is None, (
            "a move message has no print floor, so an event switched off leaves no "
            "row to count. Reporting 0 would say the switch did nothing."
        )

    That went red on its own, with no test edited and no production line
    changed, because `delivery_counts._floorless_source_types()` DERIVES the
    floorless set from the floor map rather than listing it — so when the PO
    widened the floor from four source kinds to six, `move` left the set on the
    same commit and its suppression became recordable. **That is the derivation
    working exactly as its comment promised**, and it is the reason this case
    could be re-pointed instead of debugged.

    `billing_run_completed` carries it now — a summary for the clerk who ran a
    bill run, which rides `bulk_action`, one of the four kinds that genuinely
    have no floor. Its absence is a physical fact rather than a judgment: a
    staff alert has no envelope to go in.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        _switch_off(EVENT_PLAN_MISSED, dana, channel=notification_models.CHANNEL_EMAIL)
        account, _unit = _an_occupant(dana, brazos, label="6 Mallow Rise", name="Count, Rae")
        plan = _a_plan_with_a_missed_instalment(brazos, account)
        _send_plan_notices(
            plan,
            on=PLAN_START + timedelta(days=1),
            actor=dana,
            channels=(notification_models.CHANNEL_PRINT, notification_models.CHANNEL_EMAIL),
        )

        counted = delivery_counts.for_event(EVENT_PLAN_MISSED, _rail_today())
        assert counted["suppressed"] == 1, (
            "the email switch stopped a channel on one letter and the rail counts "
            f"{counted['suppressed']} suppressions."
        )
        assert counted["by_channel"][notification_models.CHANNEL_EMAIL]["suppressed"] == 1
        assert counted["by_channel"][notification_models.CHANNEL_PRINT]["queued"] == 1
        assert counted["suppressed_unavailable_reason"] is None

        unrecordable = delivery_counts.for_event("billing_run_completed", _rail_today())
        assert unrecordable["suppressed"] is None, (
            "a staff bulk summary has no print floor, so an event switched off "
            "leaves no row to count. Reporting 0 would say the switch did nothing."
        )
        assert unrecordable["suppressed_unavailable_reason"]
        # …and the OTHER direction of the same pair, which is what stops this
        # from passing on a rail that reports `None` for everything: a move
        # letter used to sit on this side and moved to the recordable side when
        # the floor widened on 2026-08-30. It must now read as a NUMBER.
        recordable_now = delivery_counts.for_event(EVENT_MOVE_IN, _rail_today())
        assert recordable_now["suppressed"] == 0, (
            "a move letter has carried the print floor since 2026-08-30, so a "
            "suppression on one WOULD leave a row to count and the rail must say "
            "zero rather than unavailable. `None` here means the floorless set is "
            "being listed somewhere instead of derived from the floor map."
        )
        assert recordable_now["suppressed_unavailable_reason"] is None


def test_cr048_b6__one_documents_suppression_is_counted_once_not_once_per_channel(brazos, dana):
    """⛔ The arithmetic bug a shape assertion cannot see.

    The suppression stamp rides EVERY surviving row of a document. Counting rows
    instead of documents multiplies one suppression by the number of channels
    that survived it — a rail that reads "2" for one switched-off email.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        _switch_off(EVENT_PLAN_MISSED, dana, channel=notification_models.CHANNEL_EMAIL)
        account, _unit = _an_occupant(dana, brazos, label="9 Sedge Court", name="Once, Tal")
        plan = _a_plan_with_a_missed_instalment(brazos, account)
        # THREE channels asked for, so TWO survive the switched-off email and
        # both carry the same stamp. At one surviving row the bug is invisible.
        _send_plan_notices(
            plan,
            on=PLAN_START + timedelta(days=1),
            actor=dana,
            channels=(
                notification_models.CHANNEL_PRINT,
                notification_models.CHANNEL_EMAIL,
                notification_models.CHANNEL_SMS,
            ),
        )
        stamped = _queue(brazos, source_type="plan", rule_suppressed_channels__isnull=False).count()
        assert stamped == 2, (
            f"{stamped} surviving rows carry the suppression stamp; at fewer than "
            "two this case cannot tell row-counting from document-counting."
        )
        assert delivery_counts.for_event(EVENT_PLAN_MISSED, _rail_today())["suppressed"] == 1, (
            "one switched-off email on one letter counted more than once — the "
            "stamp rides every surviving row, so the count must be by DOCUMENT."
        )


def test_cr048_b6__every_event_gets_a_rail_and_an_unknown_key_is_refused(brazos, dana):
    """Hard-won law 2 in the other direction: a rail the screen cannot find for
    an event is a rail that renders as nothing. Every row on SET-12 has one."""
    with tenant_ctx(brazos):
        _seeded(dana)
        rails = delivery_counts.for_events(_rail_today())
        assert set(rails) == set(rule_catalog.EVENT_KEYS)
        for key, rail in rails.items():
            event = rule_catalog.event(key)
            assert set(rail["by_channel"]) >= set(event.channels), (
                f"{key} offers {event.channels} and the rail names "
                f"{set(rail['by_channel'])}; a channel with no counter draws blank."
            )
        with pytest.raises(KeyError):
            delivery_counts.for_event("not_an_event", _rail_today())


def test_cr048_b6__an_unattributed_row_is_never_counted_against_an_event(brazos, dana):
    """Every row written before CR-048 wave B carries no event, and so does every
    writer still un-wired. Those rows must not be swept into some event's count
    by a fallback — which is what a `source_type`-based derivation would have
    done, and why the attribution is a stamped column instead."""
    with tenant_ctx(brazos):
        _seeded(dana)
        account, _unit = _an_occupant(dana, brazos, label="17 Tansy Mews", name="Null, Wren")
        plan = _a_plan_with_a_missed_instalment(brazos, account)
        # ⚠ **RE-POINTED 2026-08-30 BY THIS CASE'S OWN INSTRUCTION.** It used
        # the plan REMINDER, which was un-wired when B10 landed and said so:
        # *"if it now carries an event this case needs re-pointing at a writer
        # that does not."* Wave B11 wired the reminder (`plan_notice_upcoming`
        # was one of its thirteen), so the case moved to the S35 manual
        # collections reminder — `payments.notices.send_reminders`, which queues
        # under `notice` and passes no event key. There is nothing wrong with
        # that: BR-NOT-017 gives the ladder ONE rule and this is the manual
        # send inside it. What must stay true is that its rows belong to no
        # event's rail.
        # ⚠ RE-POINTED AGAIN 2026-10-29 (`DEF-PAY-10651`): the reminder now
        # reads its own rule (`past_due_reminder`, PO ruling 1A) and queues
        # under `reminder`, so it carries an event. The 10-day disconnect
        # notice still queues under `notice` with no event key — sent to a
        # SECOND occupant, because the first one's plan (BR-CUS-043) rightly
        # pauses a disconnect notice and would queue nothing.
        other, _other_unit = _an_occupant(dana, brazos, label="18 Tansy Mews", name="Null, Ash")
        payments_notices.send_disconnect_notices(
            account_ids=(other.pk,),
            tier="first_10_day",
            cut_date=PLAN_START + timedelta(days=10),
            on_date=PLAN_START,
            actor=dana,
        )

        unattributed = _queue(brazos, source_type="notice", event_key__isnull=True)
        assert unattributed.count() >= 1, (
            "the manual collections reminder is expected to be un-wired here; if "
            "it now carries an event this case needs re-pointing at a writer "
            "that does not."
        )
        rails = delivery_counts.for_events(_rail_today())
        assert sum(rail["queued"] for rail in rails.values()) == 0, (
            "an un-attributed queue row was counted against an event. A row this "
            "platform cannot attribute belongs to no event's rail."
        )


# ══════════════════════════════════════════════════════════════════════════
# B6 · THE FIELD IS ON THE WIRE.  ⚠ HARD-WON LAW 2 — BUILT IS NOT WIRED.
# ══════════════════════════════════════════════════════════════════════════
def _get(view, tenant, actor, **kwargs):
    return api_call(view, "get", user=actor.user, role="system_admin", tenant=tenant, **kwargs)


def test_cr048_b6__both_settings_responses_actually_carry_the_rail(brazos, dana):
    """**A frontend lane is building this rail right now and renders NOTHING
    where the number is absent.** A counts service nothing serves is dead code
    with a passing unit test — the exact shape hard-won law 2 was written from
    (four defects in one day, every one a prop nothing passed).

    So this asserts the FIELD, on BOTH responses, through the real views.
    """
    with tenant_ctx(brazos):
        _seeded(dana)
        _a_moved_out_then_in(dana, brazos, label="44 Lovage Court")

        listing = _get(rules_api.notification_rules, brazos, dana)
        detail = _get(rules_api.notification_rule, brazos, dana, event_key=EVENT_MOVE_IN)

    rows = {row["key"]: row for row in listing.data["results"]}
    assert set(rows) == set(rule_catalog.EVENT_KEYS)
    for key, row in rows.items():
        assert row.get("last_30_days") is not None, (
            f"{key} reaches the settings screen with no `last_30_days` block, so the "
            "rail draws nothing for it."
        )
    # 2, not 1: one welcome letter on two channels since BR-NOT-024's print
    # floor widened to cover `move` on 2026-08-30. The figure is asserted at all
    # only so that "the field is present" cannot pass on a field serving zero —
    # which is this case's whole subject, and is unaffected by the count moving.
    assert rows[EVENT_MOVE_IN]["last_30_days"]["queued"] == 2
    assert detail.data["last_30_days"]["queued"] == 2
    assert (
        detail.data["last_30_days"]["until"] == rows[EVENT_MOVE_IN]["last_30_days"]["until"]
    ), "the list and the rule page are measuring two different windows."

    # The two posture flags answer DIFFERENT questions and must not be read as
    # one: provider delivery is still unavailable (BR-NOT-013), queue counts are
    # now available. One flag for both is how "we cannot know" and "nothing
    # happened" came to render the same.
    assert listing.data["delivery_counts_available"] is False
    assert listing.data["queue_counts_available"] is True
    assert listing.data["queue_counts_window_days"] == 30
    assert detail.data["queue_counts_available"] is True


def test_cr048_b6__the_new_category_is_served_so_the_screen_can_group_it(brazos, dana):
    """The two move events belong to a SIXTH category that the PO's own
    requirement list does not contain. A screen groups by `categories`, so an
    event in a category the response never names is an event that renders in no
    group at all — visible in the data, invisible on the page."""
    with tenant_ctx(brazos):
        _seeded(dana)
        listing = _get(rules_api.notification_rules, brazos, dana)

    assert rule_catalog.CATEGORY_ACCOUNT_LIFECYCLE in listing.data["categories"]
    assert listing.data["categories"][:5] == [
        rule_catalog.CATEGORY_BILLING,
        rule_catalog.CATEGORY_PAYMENTS,
        rule_catalog.CATEGORY_COLLECTIONS,
        rule_catalog.CATEGORY_FIELD_WORK,
        rule_catalog.CATEGORY_STAFF_SYSTEM,
    ], (
        "the PO's five categories moved. They are ruled, and their ORDER is the "
        "requirement's own; the sixth goes last."
    )
    rows = {row["key"]: row for row in listing.data["results"]}
    assert rows[EVENT_MOVE_IN]["category"] == rule_catalog.CATEGORY_ACCOUNT_LIFECYCLE
    assert rows[EVENT_MOVE_OUT]["category"] == rule_catalog.CATEGORY_ACCOUNT_LIFECYCLE
