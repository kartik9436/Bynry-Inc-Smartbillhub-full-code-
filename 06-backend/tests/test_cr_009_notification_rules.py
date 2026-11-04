# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
#           rule page — CR-009)   Screens: S8
# Rules:    BR-NOT-017 (ONE HOME for every notification rule — PO 2026-08-17) ·
#           BR-NOT-018 (an event with no trigger is drawn and refused by name) ·
#           BR-NOT-005 (queue only; NO synchronous send endpoint anywhere) ·
#           BR-NOT-013 (delivery is out of this release on every channel) ·
#           BR-NOT-010 (v1 channels: print · email · SMS, and no fourth) ·
#           BR-IDN-009 / BR-SHL-025 (server-enforced RBAC IS the gating) ·
#           BR-PAY-017 (the collections ladder) · CLAUDE.md rule 7 (audited)
# ───────────────────────────────────────────────────────
"""US-NOT-017 §3, as code. Every case below predates the implementation.

Two are the ones to read first.

`test_cr_009_tc12__no_send_endpoint_is_minted_by_this_surface` is the rule the
PO's own ruling could have been read as reversing and does not. *"lets build the
infra and capabilities; the moment we take the decison on ESP or SMTP … we just
need to plug it"* asked for the INFRASTRUCTURE, and BR-NOT-005's *"queue only,
no synchronous send endpoint"* is untouched: "Send test" writes a queue row. So
this asserts an ABSENCE — neither `…/send` nor `…/test-send` resolves — exactly
as CR-007's surface does, because a rule nobody asserts is a rule the next lane
deletes by accident.

`test_cr_009_tc7__a_staff_recipient_is_refused_with_the_ruling` — ⚠ AMENDED
2026-08-18 — used to be the prime directive in one line (the service raised
`NotImplementedError("OQ-261")`). The PO closed OQ-261 (2026-08-17, verbatim:
*"the user who started the action, plus all System Admins for failures"* →
BR-NOT-021): the recipient is a ruled PLATFORM POLICY, so setting one per rule
is still refused — now with the ruling quoted, because accepting a per-rule
value would build the picker the PO decided against.
"""

from __future__ import annotations

import pytest
from django.urls import Resolver404, resolve

from apps.notifications import in_app, models, rule_catalog, rule_service
from apps.notifications import rules_api as api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _call(view, method, tenant, actor, role="system_admin", **kwargs):
    return api_call(
        view, method, user=getattr(actor, "user", None), role=role, tenant=tenant, **kwargs
    )


# ── the routes exist at all (DEF-112 / DEF-128, four times in this repo) ────
def test_cr_009__all_three_paths_resolve_through_the_root_urlconf():
    base = "/api/brazosbend/notification-rules"
    assert resolve(base).func is api.notification_rules
    assert resolve(f"{base}/bill_ready").func is api.notification_rule
    assert resolve(f"{base}/bill_ready/queue-test").func is api.queue_test_message


def test_cr_009_tc12__no_send_endpoint_is_minted_by_this_surface():
    """US-NOT-017 TC-12. BR-NOT-005 / A11 Addendum r2 §4, verbatim: *"no
    synchronous send endpoint anywhere (queue only)"*.

    ⚠ **THE FIRST CUT OF THIS TEST WAS WRONG AND THE WRONGNESS IS WORTH
    KEEPING.** It asserted `Resolver404` for the bare two-segment
    `notification-rules/send` as well, and that FAILED — because `send` is a
    perfectly good `<str:event_key>` and the DETAIL view matched it. The right
    assertion is narrower and truer: no ACTION path named `send` or `test-send`
    exists, and the two-segment forms reach the read/write view for an event
    that does not exist, which answers 422 by name. A test that had been
    "fixed" by loosening the pattern would have stopped asserting the rule."""
    for path in ("bill_ready/send", "bill_ready/test-send"):
        with pytest.raises(Resolver404):
            resolve(f"/api/brazosbend/notification-rules/{path}")
    for path in ("send", "test-send"):
        # Not a send endpoint — the event detail view, for an event that is not
        # in the catalogue.
        assert resolve(f"/api/brazosbend/notification-rules/{path}").func is (
            api.notification_rule
        )


# ── TC-1/TC-2 · the matrix ─────────────────────────────────────────────────
def test_cr_009_tc1__a_tenant_who_has_never_opened_set12_still_has_a_full_matrix(brazos, dana):
    """There is no 'unset' state: an absent row and a defaulted row must not be
    two behaviours, because something would have to interpret the difference."""
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    assert response.status_code == 200
    assert response.data["count"] == len(rule_catalog.EVENTS)
    assert [row["key"] for row in response.data["results"]] == list(rule_catalog.EVENT_KEYS)
    assert response.data["categories"] == list(rule_catalog.CATEGORIES)
    # Every row carries a COMPLETE rule, not a null-shaped placeholder.
    for row in response.data["results"]:
        assert row["trigger_mode"] in rule_catalog.TRIGGER_MODES
        assert row["failure_policy"] in rule_catalog.FAILURE_POLICIES


def test_cr_009_tc2__the_requirement_claims_sixteen_events_and_names_fifteen(brazos, dana):
    """US-NOT-017 TC-2. The discrepancy is DATA on the wire rather than a note
    somebody remembers. Inventing a sixteenth event would put a row on a
    settings screen that no writer in this codebase can ever fire."""
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    assert response.data["requirement_claims_event_count"] == 16
    # ⚠ 15 UNTIL 2026-08-30, THEN 18, AND 30 SINCE. CR-048 wave B10 added three
    # events (the two move messages and the missed payment-plan instalment) and
    # wave B11 added twelve more the same day — the remaining customer wordings
    # that had a body seeded on every tenant and no rule that could send it. The
    # endpoint returns one row per event, so `count` moves with it.
    #
    # **The claim of 16 does NOT move** — it is what the requirement asserted,
    # kept beside what was built so the two can disagree in public. Subtracting
    # them is meaningless: one counts what this platform can notify about, the
    # other records what one document once said.
    #
    # ⚠ **AND 30 IS NOT 30 MESSAGES A UTILITY WILL RECEIVE.** Twelve of the
    # thirty carry `trigger_blocked_by` and are DRAWN AND REFUSED by name
    # (BR-NOT-018): the seven CR-009 shipped that way, plus five of B11's — the
    # statement, the planned outage, the autopay confirmation, the plan-void
    # letter and the door hanger, each with the question that owns its absence
    # on the row. The count of rows and the count of live triggers are different
    # facts and the wire carries both, which is what stops "thirty events" from
    # reading as thirty things that happen.
    # ⚠ **AND 31 SINCE 2026-09-23** — `CR-136-BRC07` `P2.11` added
    # `counter_left_open`, a counter nobody closed. It is LIVE from its first
    # commit (`apps/payments/counter_watch.py` through
    # `apps/payments/run_alert_seam.py`), so it carries no `trigger_blocked_by`
    # and the count of blocked rows below does NOT move with it — which is the
    # distinction the paragraph above exists to keep.
    # ⚠ **AND 32 SINCE 2026-09-27** — `CR-142-BRC07` `P4.10` added
    # `scheduled_report_ready`: the message a schedule sends when its report
    # has run. It is LIVE from its first commit (`apps/reports/delivery.py`
    # through `apps/reports/notifications_seam.py`), so it carries no
    # `trigger_blocked_by` and the count of blocked rows below does NOT move
    # with it either — the same distinction `counter_left_open` records above.
    # ⚠ **AND 40 SINCE 2026-10-04** — `CR-168-BRC10` P3.58/P3.59 (lane SRV-4)
    # added EIGHT, all LIVE from their first commit: the six Work escalations
    # (`apps/work/escalations.py` through `apps/notifications/work_escalations.py`)
    # and the two reminders that moved from a rule into Notifications (ruling
    # 34). And the blocked count moves the OTHER way, 12 → 11: `sla_breach`
    # gained its writer (a rule's *Past due* row), so it stopped saying that
    # nothing fires it — the same distinction, in the direction it was kept for.
    # ⚠ **AND 44 SINCE 2026-10-04 (`2.517.0`)** — `CR-168-BRC10` P6.1/P6.2
    # (lane SRV-5) added FOUR, all LIVE from their first commit: the customer's
    # *visit moved* (`apps/work/visit_notices.py` through
    # `apps/notifications/work_customer_messages.py`) and the office's three —
    # a job at risk, declined, on hold (`apps/notifications/work_escalations.py`).
    # And the blocked count falls 11 → 8: *booked*, *on the way* and *done*
    # gained their writers in the same commit, so they stopped saying that
    # nothing fires them.
    # ⚠ **AND THE BLOCKED COUNT FALLS 8 → 7 ON 2026-10-14 (`CR-182-BRC10`)** —
    # `high_usage_alert` gained its writer (a reading flagged high,
    # `apps/metering/high_consumption.py`; PO A4/A5), so it stopped saying that
    # nothing fires it. No row was added: the count of 44 does not move.
    # ⚠ **AND 45 SINCE 2026-10-21 (`DEF-WRK-10350`)** — the office's fourth
    # kind, R28's emergency nobody acknowledged in five minutes
    # (`apps/work/field_alerts.py` through `apps/notifications/work_escalations.py`),
    # LIVE from its first commit: the blocked count does not move.
    # ⚠ **AND 47 SINCE 2026-10-22 (`CR-188-BRC10`)** — a member of staff's own
    # sign-in: `staff_user_invited` and `staff_password_reset`, both LIVE from
    # their first commit (`apps/identity/password_links.py` through
    # `apps/identity/seams/notifications_seam.py`). The blocked count does not move.
    # ⚠ **AND 50 SINCE 2026-10-29** — `service_disconnected` and
    # `service_restored` (`DEF-NOT-10649`, PO *"1 A, 2 A, 3 A, 4 A"*), both LIVE
    # from their first commit (`customers.disconnects.commit_cut` /
    # `.restore_service`), so the blocked count does not move; and the event
    # `DEF-WRK-10652` added the same day without moving this figure (this line
    # was ALREADY RED at 48 when the DEF-NOT-10649 lane reached it).
    assert response.data["built_event_count"] == 50
    assert response.data["count"] == 50
    blocked = [row for row in response.data["results"] if row["trigger_blocked_by"]]
    assert len(blocked) == 7, (
        "seven of the forty-four rows should say that nothing fires them; "
        f"{len(blocked)} do — {sorted(row['key'] for row in blocked)}. A row that "
        "quietly stopped saying so is a switch that promises something."
    )


def test_cr_009__the_release_posture_travels_with_the_rules(brazos, dana):
    """BR-NOT-013. A matrix full of enabled toggles on a deployment with no
    dispatcher is a true fact about stored flags and a false impression about
    the product.

    ⚠ **AMENDED 2026-08-17 (CR-009 in-app lane): `dispatch_runs_in_this_release`
    IS NOW `True`, AND THE ASSERTION MOVED RATHER THAN LOOSENED.** In-app
    delivers (BR-NOT-019), so a flat False understated the product in the one
    direction that costs trust the moment somebody sees a message arrive — and a
    flat True would overstate it, because three of the four channels still have
    no provider at all. The posture is now a FLAG plus a LIST, and this test
    asserts BOTH halves: what CAN send, and that the other three still cannot.
    Delivery counts stay unavailable for the reason BR-NOT-013 gives, unchanged:
    `delivered` and `bounced` are a third party's confirmation and a third
    party's webhook, and a local adapter does not become a third party.
    """
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    assert response.data["dispatch_runs_in_this_release"] is True
    assert response.data["dispatchable_channels"] == [models.CHANNEL_IN_APP]
    assert models.CHANNEL_PRINT not in response.data["dispatchable_channels"]
    # ⚠ AMENDED 2026-10-22 (`DEF-NOT-10537`). This asserted the reason said
    # *"none of them leaves the building"* and *"sending is not switched on
    # yet"* — false once email sends through the utility's Custom SMTP
    # connector. The sentence is gone from the wire and the screen (PO: *"Each
    # channel tells the clerk the truth about itself, in one short line"*); the
    # list above is now derived from the dispatcher, and on this tenant (no
    # mail server) it is still in-app alone.
    assert "no_dispatcher_reason" not in response.data
    assert response.data["delivery_counts_available"] is False
    # The fact stays — nobody reports deliveries back — and the false reason
    # ("because sending is not switched on") is gone.
    counts_reason = response.data["delivery_counts_reason"]
    assert counts_reason == "No provider reports these back yet."


# ── TC-3 · channels this platform does not have ────────────────────────────
def test_cr_009_tc3__portal_is_reported_with_its_reason_and_is_not_a_toggle(brazos, dana):
    """US-NOT-017 TC-3. The requirement asks for Email+SMS+Portal on bill-ready.

    ⚠ **REVERSED 2026-09-07 BY `CR-084`, AND THE OLD ASSERTION IS QUOTED HERE
    RATHER THAN DELETED.** This test used to read: *"A 'Portal' flag would be a
    switch with nothing behind it (BR-NOT-010)"*, assert the reason contained
    *"no customer portal"*, and assert that switching it on was REFUSED by name.
    All three were right in August. `CR-068` then shipped the portal — 75 screens
    — and the Product Owner found the greyed-out row on the live product and
    ruled: *"can you swithc on this now - Customer portal"*.

    So the requirement's third channel is now a channel, and what this test
    guards is the OTHER direction: the toggle exists, the refusal is gone, and
    `mail` — the one on the next event that is still genuinely absent — has not
    been swept away with it. The test NAME is left alone deliberately: renaming
    it loses the link to US-NOT-017's TC-3 that G10 reads, and the sentence
    above says what changed instead.
    """
    with tenant_ctx(brazos):
        response = _call(api.notification_rule, "get", brazos, dana, event_key="bill_ready")
    assert response.status_code == 200
    channels = {row["channel"] for row in response.data["channel_rules"]}
    assert channels == {models.CHANNEL_EMAIL, models.CHANNEL_SMS, models.CHANNEL_PORTAL}
    unavailable = {row["channel"]: row["reason"] for row in response.data["unavailable_channels"]}
    assert set(unavailable) == set(), (
        "bill-ready has no unavailable channel left — the portal was its only one, and "
        f"the requirement's three are all real now. Still refused: {unavailable}"
    )
    # And it IS settable now, which is the whole of the Product Owner's ruling.
    with tenant_ctx(brazos):
        rule_service.update_rule(
            event_key="bill_ready", actor=dana, channels={"portal": {"enabled": True}}
        )
        after = _call(api.notification_rule, "get", brazos, dana, event_key="bill_ready")
    portal_row = next(
        row for row in after.data["channel_rules"] if row["channel"] == models.CHANNEL_PORTAL
    )
    assert portal_row["enabled"] is True


def test_cr_009__mail_on_the_disconnect_notice_is_named_as_a_vendor_gap(brazos, dana):
    """'Mail' means physical post. `pdf_print` RENDERS the letter; who franks and
    posts it is an integration nobody has chosen (BR-NOT-013)."""
    with tenant_ctx(brazos):
        response = _call(
            api.notification_rule, "get", brazos, dana, event_key="disconnect_notice"
        )
    unavailable = {row["channel"]: row["reason"] for row in response.data["unavailable_channels"]}
    assert "PHYSICAL POST" in unavailable["mail"]


# ── TC-4 · the escalation ladder, read from its ONE store ──────────────────
def test_cr_009_tc4__the_ladder_carries_the_tenants_own_five_figures(brazos, dana):
    """US-NOT-017 TC-4 / BR-NOT-017. The two MONEY figures are the ones that have
    never had a screen (DEF-204, DEF-097 reopened): $25.00 floor and 25% pause.
    Both are canonical STRINGS end to end (CLAUDE.md rule 2)."""
    with tenant_ctx(brazos):
        response = _call(
            api.notification_rule, "get", brazos, dana, event_key="past_due_reminder"
        )
    ladder = response.data["ladder"]
    assert ladder is not None
    assert ladder["reminder_days_after_due"] == 3
    assert ladder["notice_tier_days"] == [10, 5]
    assert ladder["final_notice_hours"] == 48
    assert ladder["balance_floor_amount"] == "25"
    assert ladder["partial_payment_pause_percent"] == "25"
    # ONE HOME for the rule is not a second STORE for the figure.
    assert ladder["write_endpoint"] == "/settings/collections"


def test_cr_009__a_non_collections_event_has_no_ladder_at_all(brazos, dana):
    with tenant_ctx(brazos):
        response = _call(api.notification_rule, "get", brazos, dana, event_key="payment_received")
    assert response.data["ladder"] is None


# ── TC-5/TC-6 · saving ─────────────────────────────────────────────────────
def test_cr_009_tc5__turning_a_rule_off_writes_one_audit_row(brazos, dana, audit_rows):
    """US-NOT-017 TC-5 / CLAUDE.md rule 7. The payload carries what MOVED and
    nothing else — a payload padded with unchanged fields makes the next reader
    hunt for the edit."""
    with tenant_ctx(brazos):
        _call(
            api.notification_rule,
            "put",
            brazos,
            dana,
            event_key="past_due_reminder",
            data={"enabled": False},
        )
    # A fresh context on purpose: `api_call` enters and LEAVES the BE-01 tenant
    # context around the view, so reading inside the outer block would read
    # through a context the call has already exited.
    with tenant_ctx(brazos):
        view = rule_service.rule("past_due_reminder")
    assert view.row.enabled is False
    rows = [row for row in audit_rows if row["action"] == rule_service.AUDIT_ACTION]
    assert len(rows) == 1
    assert rows[0]["before"] == {"enabled": True}
    assert rows[0]["after"] == {"enabled": False}


def test_cr_009_tc6__an_offset_trigger_with_no_offset_is_refused_by_name(brazos, dana):
    """US-NOT-017 TC-6. Refused in the SERVICE as well as by the CHECK
    constraint, because a constraint violation reaches a System Admin as a
    database error and this is a sentence they can act on (BR-SHL-020)."""
    with tenant_ctx(brazos), pytest.raises(rule_service.RuleRefused) as refusal:
        rule_service.update_rule(
            event_key="payment_received", actor=dana, trigger_mode="offset_days"
        )
    assert "needs the number" in str(refusal.value)
    with tenant_ctx(brazos):
        assert rule_service.rule("payment_received").row.trigger_mode == "immediate"


def test_cr_009__an_empty_save_is_refused_rather_than_audited(brazos, dana):
    """An empty save would write an audit row saying a System Admin changed how
    this utility contacts its customers and leave no way to see that they did
    not."""
    with tenant_ctx(brazos), pytest.raises(rule_service.RuleRefused) as refusal:
        rule_service.update_rule(event_key="payment_received", actor=dana)
    assert "nothing to save" in str(refusal.value)


# ── TC-7 · the recipient is RULED (BR-NOT-021) and still not a rule field ──
def test_cr_009_tc7__a_staff_recipient_is_refused_with_the_ruling(brazos, dana):
    """⚠ AMENDED 2026-08-18. US-NOT-017 TC-7 used to assert
    `NotImplementedError("OQ-261")` because the question was OPEN. The PO closed
    it (2026-08-17, verbatim: *"the user who started the action, plus all System
    Admins for failures"* → BR-NOT-021), choosing a PLATFORM POLICY over every
    per-rule picker option — so every spelling of "send it to X" is STILL
    refused, and the refusal now quotes the ruling instead of the question.
    NOT loosened: the same four keys, still no write."""
    for key in ("staff_recipient", "staff_role", "recipient_role", "owner"):
        with tenant_ctx(brazos), pytest.raises(rule_service.RuleRefused) as raised:
            rule_service.update_rule(event_key="sla_breach", actor=dana, **{key: "system_admin"})
        assert "BR-NOT-021" in str(raised.value)
        assert "System Admin" in str(raised.value)


def test_cr_009__every_staff_event_carries_the_ruled_policy_on_the_wire(brazos, dana):
    """⚠ AMENDED 2026-08-18 (was `staff_recipient_unresolved is True`). A screen
    must never have to INFER the policy from `audience == staff` — an inference
    is a place to be wrong — so every staff row states the ruled recipient
    policy, and `staff_recipient` stays None so nobody mistakes the policy for
    a stored per-rule value."""
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    staff = [
        row
        for row in response.data["results"]
        if row["audience"] == rule_catalog.AUDIENCE_STAFF
    ]
    # ⚠ **FIVE UNTIL 2026-09-23; `CR-136-BRC07` `P2.11` ADDED `counter_left_open`.**
    # A counter nobody closed is a staff event for the reason the other five are
    # — nothing here reaches a customer — and it carries the SAME ruled policy,
    # which is the property this case actually guards. The number moves; the
    # `all(...)` below is what must never stop being true of every one of them.
    # ⚠ **SIX UNTIL 2026-09-27; `CR-142-BRC07` `P4.10` ADDED
    # `scheduled_report_ready`.** A report a clerk asked for, arriving when it
    # is ready, is a staff event for the reason the other six are — nothing
    # here reaches a customer — and it carries the SAME ruled policy, which is
    # the property this case actually guards.
    # ⚠ **SEVEN UNTIL 2026-10-04; `CR-168-BRC10` P3.58/P3.59 (lane SRV-4) ADDED
    # EIGHT** — the six Work escalations and the two reminders that moved from
    # a rule into Notifications (ruling 34). Each is told to staff and carries
    # the SAME ruled policy (the escalations narrowed only by a rule's *Also
    # tell*, PO 2026-10-04), which is the property this case guards.
    # ⚠ **FIFTEEN UNTIL 2026-10-04 (`2.517.0`); `CR-168-BRC10` P6.2 (lane
    # SRV-5) ADDED THREE** — a job at risk, declined by the technician, put on
    # hold. Each is told to the office and carries the SAME ruled policy.
    # ⚠ **EIGHTEEN UNTIL 2026-10-21; `DEF-WRK-10350` ADDED R28's** — an
    # emergency alert nobody acknowledged in five minutes. Told to the office,
    # the SAME ruled policy.
    # ⚠ **NINETEEN UNTIL 2026-10-22; `CR-188-BRC10` ADDED TWO, AND THEY ARE THE
    # FIRST STAFF EVENTS WHOSE RECIPIENT IS NOT BR-NOT-021's POLICY.** A sign-in
    # link goes to the person whose account it is — never to the admin who
    # clicked, never to every System Admin — so each states its OWN sentence
    # (`STAFF_ACCESS_RECIPIENT_POLICY`) and the screen still infers nothing.
    assert len(staff) == 21, (
        "the staff events are billing_run_completed, reconciliation_exceptions, "
        "counter_left_open, scheduled_report_ready, sla_breach, daily_digest, "
        "security_alerts, the six work escalations, two work reminders and the "
        "three office kinds of ruling 3, R28's unacknowledged emergency and the "
        f"two staff sign-in emails; {sorted(row['key'] for row in staff)} were served"
    )
    access = {"staff_user_invited", "staff_password_reset"}
    assert all(
        row["staff_recipient_policy"] == rule_catalog.STAFF_RECIPIENT_POLICY
        for row in staff
        if row["key"] not in access
    )
    assert {
        row["staff_recipient_policy"] for row in staff if row["key"] in access
    } == {rule_catalog.STAFF_ACCESS_RECIPIENT_POLICY}
    customer = [
        row
        for row in response.data["results"]
        if row["audience"] == rule_catalog.AUDIENCE_CUSTOMER
    ]
    assert all(row["staff_recipient_policy"] is None for row in customer)


def test_cr_009_c11__in_app_is_a_real_channel_row_on_the_five_staff_events(brazos, dana):
    """The one-line-per-event change the old `unavailable_channels` entry
    promised for the day OQ-261 closed. The two events whose live writer is
    `queue_bulk_summary` seed ENABLED with its class; the three with no trigger
    seed with the channel present and OFF (BR-NOT-018 unchanged)."""
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    staff = {
        row["key"]: row
        for row in response.data["results"]
        if row["audience"] == rule_catalog.AUDIENCE_STAFF
    }
    # ⚠ **THIS LOOP RAN OVER EVERY STAFF EVENT UNTIL 2026-09-27 AND NOW ASKS
    # THE CATALOGUE FIRST — WHICH IS A STRONGER QUESTION, NOT A WEAKER ONE.**
    # `CR-142-BRC07` `P4.10` added `scheduled_report_ready`, whose catalogue
    # offers EMAIL and nothing else: `BR-REP-017` is signed — *"scheduled-report
    # email ships W6 with all email"* — and `US-REP-015` says the queue ROWS are
    # written now and the dispatch is flipped later. Giving it an in-app row to
    # satisfy a loop would put a bell on a settings screen for a channel the
    # signed rule does not name, and the only in-app class in the library is
    # `staff_bulk_summary`, whose palette is `{operation} {total_count}
    # {failed_count} {finished_at}` — a scheduled report rendered through it
    # would read as a bulk run that processed nothing.
    #
    # So the loop now asserts the contract WHERE THE CATALOGUE OFFERS IT, and
    # asserts the catalogue itself — an event that quietly DROPPED `in_app`
    # from its channels still fails here, which is what this case is for.
    for key, row in staff.items():
        channels = {channel["channel"]: channel for channel in row["channel_rules"]}
        offered = rule_catalog.event(key).channels
        if "in_app" not in offered:
            # `CR-188-BRC10` (2026-10-22): the two staff sign-in emails are
            # email-only too — a sign-in link belongs in the person's own
            # mailbox, and a bell needs a session the person does not yet have.
            assert key in {
                "scheduled_report_ready",
                "staff_user_invited",
                "staff_password_reset",
            }, (
                f"{key} dropped its in_app channel from the catalogue. Only "
                "scheduled_report_ready (BR-REP-017) and the two staff sign-in "
                "emails (CR-188-BRC10) are email-only."
            )
            continue
        assert "in_app" in channels, f"{key} lost its in_app channel row"
        assert "in_app" not in {entry["channel"] for entry in row["unavailable_channels"]}
        # In-app is the one channel whose route is deliverable today.
        assert channels["in_app"]["dispatchable"] is True
    assert staff["billing_run_completed"]["channel_rules"] != []
    wired = {
        key: {c["channel"]: c for c in row["channel_rules"]}["in_app"]
        for key, row in staff.items()
        if "in_app" in rule_catalog.event(key).channels
    }
    assert wired["billing_run_completed"]["template_code"] == "staff_bulk_summary"
    assert wired["billing_run_completed"]["enabled"] is True
    assert wired["reconciliation_exceptions"]["template_code"] == "staff_bulk_summary"
    for key in ("daily_digest", "security_alerts"):
        assert wired[key]["enabled"] is False, f"{key} has no writer and must seed OFF"
        assert wired[key]["template_code"] is None
    # `sla_breach` has a writer since 2026-10-04 (`CR-168-BRC10` P3.58, a Work
    # rule's *Past due* row) and renders through FIELD-2's in-app class.
    assert wired["sla_breach"]["template_code"] == "staff_field_work"
    assert wired["sla_breach"]["enabled"] is True


def test_cr_009__a_customer_scope_on_a_staff_event_is_refused(brazos, dana):
    """Storing 'primary contact only' on an SLA-breach alert would look like a
    second answer beside the ruled one (BR-NOT-021). ⚠ AMENDED 2026-08-18: the
    refusal used to name OQ-261; it now names the rule that closed it."""
    with tenant_ctx(brazos), pytest.raises(rule_service.RuleRefused) as refusal:
        rule_service.update_rule(
            event_key="sla_breach", actor=dana, customer_scope="primary_only"
        )
    assert "BR-NOT-021" in str(refusal.value)


# ── TC-8/TC-9 · the permission rule (PO 2026-08-17, shaped by DEF-196) ─────
def test_cr_009_tc8__an_executive_reads_the_matrix_and_cannot_write(brazos):
    """US-NOT-017 TC-8. A4 `settings_lookups` = {system_admin: Full, executive:
    View}. The READ must SUCCEED — that is the half DEF-196 found broken across
    eight Settings views, where every `readOnly` branch was unreachable code."""
    executive = staff_actor(brazos, "executive", "exec@brazosbendutilities.test")
    with tenant_ctx(brazos):
        read = _call(api.notification_rules, "get", brazos, executive, role="executive")
    assert read.status_code == 200
    with tenant_ctx(brazos):
        write = _call(
            api.notification_rule,
            "put",
            brazos,
            executive,
            role="executive",
            event_key="payment_received",
            data={"enabled": False},
        )
    assert write.status_code == 403
    # And the narrower gate refuses too — removing either must still refuse.
    with tenant_ctx(brazos), pytest.raises(Exception):
        rule_service.update_rule(event_key="payment_received", actor=executive, enabled=False)


def test_cr_009_tc9__a_billing_clerk_cannot_open_this_surface_at_all(brazos, marcus):
    """US-NOT-017 TC-9. A4 gives a Billing Clerk NO `settings_lookups` cell, and
    no cell is no access rather than read-only access (DEF-196's second cut)."""
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, marcus, role="billing_clerk")
    assert response.status_code == 403


# ── TC-10/TC-11 · "Send test" ENQUEUES ─────────────────────────────────────
def test_cr_009_tc10__send_test_queues_one_row_to_the_signed_in_users_own_address(
    brazos, dana
):
    """US-NOT-017 TC-10. A real queue row, through the ONE write path, and a
    response that says `queued: true` AND `will_be_delivered: false` — because
    "queued: true" alone reads, to the person who just clicked, as "a test email
    is on its way", which is exactly what BR-NOT-013 forbids."""
    with tenant_ctx(brazos):
        response = _call(
            api.queue_test_message,
            "post",
            brazos,
            dana,
            event_key="bill_ready",
            data={"channel": models.CHANNEL_EMAIL},
        )
    assert response.status_code == 200
    assert response.data["queued"] is True
    assert response.data["will_be_delivered"] is False
    assert response.data["recipient_address"] == dana.user.email
    assert response.data["dispatchable"] is False
    assert response.data["problem"] is not None
    with tenant_ctx(brazos):
        rows = list(
            models.OutboundMessage.objects.filter(source_type=rule_service.TEST_SOURCE_TYPE)
        )
    assert len(rows) == 1
    assert rows[0].recipient_address == dana.user.email
    assert rows[0].status == models.STATUS_QUEUED
    assert rows[0].channel == models.CHANNEL_EMAIL


def test_cr_009_tc11__a_second_test_click_is_a_second_copy_not_a_collision(brazos, dana):
    """US-NOT-017 TC-11. `copy_no > 0` is the documented meaning of a deliberate,
    human-requested extra copy — never one row and an `already_queued` problem,
    which is what a System Admin would read as "nothing happened"."""
    with tenant_ctx(brazos):
        for _ in range(2):
            _call(
                api.queue_test_message,
                "post",
                brazos,
                dana,
                event_key="bill_ready",
                data={"channel": models.CHANNEL_EMAIL},
            )
        rows = list(
            models.OutboundMessage.objects.filter(
                source_type=rule_service.TEST_SOURCE_TYPE
            ).order_by("copy_no")
        )
    assert [row.copy_no for row in rows] == [0, 1]


def test_def_265__the_in_app_channel_is_TESTABLE_because_it_is_the_one_that_delivers(
    brazos, dana
):
    """DEF-265 — the button that exists to prove the pipeline refused on the only
    channel that can prove it.

    `_test_recipient` answered for email and SMS and fell through to a PRINT
    sentence for everything else: *"there is no way to post a test letter to
    yourself"* — said to a System Admin clicking the in-app row, whose address
    is their own user id and whose adapter (`apps.notifications.in_app`) is the
    one real adapter this release has (BR-NOT-019). So the one channel that
    could show a person a delivered message was the one channel the test button
    would not use.

    Red proof, verbatim, before the fix:

        AssertionError: SET-12D refuses in-app with 'a test can only be sent to
        you, and the only addresses this platform holds for a user are an email
        address and a mobile number. There is no way to post a test letter to
        yourself.'

    ⚠ **THIS ADDS NO SEND PATH.** BR-NOT-013 stands: `queue_test` still only
    ENQUEUES, through the same single write path, and the row still waits for
    `manage.py dispatch_outbound` to become an inbox message (DEF-266, which
    this does not close). What changes is which address the queue row carries.
    """
    with tenant_ctx(brazos):
        result = rule_service.queue_test(
            event_key="billing_run_completed", channel=models.CHANNEL_IN_APP, actor=dana
        )
    assert result.unavailable_reason is None, (
        f"SET-12D refuses in-app with {result.unavailable_reason!r}"
    )
    assert result.queued is True
    # The address is the SIGNED-IN USER'S OWN id, spelled by `in_app.address_for`
    # — the one spelling the adapter and the inbox read both use. A second
    # spelling here would queue to a mailbox nobody opens.
    assert result.recipient_address == in_app.address_for(dana)
    assert result.recipient_address == str(dana.user.id)
    # And in-app is the one channel whose route is deliverable today, so the
    # screen may tell the truth about what happens next rather than "queued, but
    # nothing will leave".
    assert result.dispatchable is True
    with tenant_ctx(brazos):
        rows = list(
            models.OutboundMessage.objects.filter(source_type=rule_service.TEST_SOURCE_TYPE)
        )
    assert len(rows) == 1
    assert rows[0].channel == models.CHANNEL_IN_APP
    assert rows[0].recipient_address == str(dana.user.id)
    assert rows[0].status == models.STATUS_QUEUED


def test_def_265__print_is_still_refused_and_still_in_the_print_words(brazos, dana):
    """The fall-through sentence is CORRECT for print and stays. A fix that
    made every channel testable would have queued a paper letter to a member of
    staff, which is what the wording was written to prevent."""
    address, unavailable = rule_service._test_recipient(dana, models.CHANNEL_PRINT)
    assert address is None
    assert "no way to post a test letter to yourself" in unavailable


def test_cr_009__a_test_send_makes_no_provider_call(brazos, dana, monkeypatch):
    """BR-NOT-013, verbatim: *"no lane is to build or fake an adapter to turn a
    test green"*. The seam's deferred verdict is returned UNCHANGED and nothing
    reaches a provider."""
    from apps.notifications import provider_seam

    calls: list[str] = []
    original = provider_seam.channel_route

    def counting(channel, *, active):
        calls.append("route")
        return original(channel, active=active)

    monkeypatch.setattr(provider_seam, "channel_route", counting)
    monkeypatch.setattr(
        provider_seam,
        "dispatch_batch",
        lambda *a, **k: pytest.fail("a test send reached the provider seam's SEND path"),
        raising=False,
    )
    with tenant_ctx(brazos):
        result = rule_service.queue_test(
            event_key="bill_ready", channel=models.CHANNEL_EMAIL, actor=dana
        )
    assert result.queued is True
    assert result.dispatchable is False


def test_cr_009__a_test_to_a_user_with_no_address_says_so_and_queues_nothing(brazos):
    """A test goes to YOU and to nobody else, so a user with no mobile number
    gets a sentence rather than somebody else's phone."""
    with tenant_ctx(brazos):
        actor = staff_actor(brazos, "system_admin", "noPhone@brazosbendutilities.test")
        result = rule_service.queue_test(
            event_key="bill_ready", channel=models.CHANNEL_SMS, actor=actor
        )
    assert result.queued is False
    assert "no mobile number" in result.unavailable_reason
    with tenant_ctx(brazos):
        assert not models.OutboundMessage.objects.filter(
            source_type=rule_service.TEST_SOURCE_TYPE
        ).exists()


# ── TC-13 · a channel with no template cannot be switched on ───────────────
def test_cr_009_tc13__a_channel_with_no_template_cannot_be_enabled(brazos, dana):
    """US-NOT-017 TC-13, the requirement verbatim: *"A channel can't be enabled
    if its variant is deactivated."* Enforced in the SERVICE — BR-SHL-025 is
    explicit that the screen is not the enforcement."""
    with tenant_ctx(brazos), pytest.raises(rule_service.RuleRefused) as refusal:
        rule_service.update_rule(
            event_key="payment_failed",
            actor=dana,
            channels={models.CHANNEL_SMS: {"enabled": True, "template_code": None}},
        )
    assert "no template" in str(refusal.value)


# ── TC-14 · events nothing can fire (BR-NOT-018) ───────────────────────────
def test_cr_009_tc14__the_six_events_with_no_trigger_ship_off_and_say_why(brazos, dana):
    """US-NOT-017 TC-14 / BR-NOT-018. Drawn, configurable, OFF, and each naming
    the open question that owns its absence. A switch a utility can turn ON is a
    promise that something happens when they do.

    ⚠ **SEVEN BECAME TWELVE ON 2026-08-30 (CR-048 wave B task B11), AND THE
    FIVE ADDITIONS ARE THE POINT OF THAT WAVE RATHER THAN A REGRESSION IN IT.**
    B11's job was thirteen customer messages with wording seeded on every tenant
    and no rule that could ever send them. Seven of the thirteen had a live
    writer and are wired. **Five had none, and the honest thing to do with a
    message nothing can send is to draw it and refuse it BY NAME** — which is
    what this rule says and what those five now do. Before B11 they were not
    "not promised": they were INVISIBLE, sitting in the template library with a
    body a utility could edit and no row on this screen at all.

    Each names the question that owns its absence, and the five are five
    different absences rather than one:
      · `statement_ready`        OQ-1160 — this product has no statement at all
      · `planned_outage_notice`  OQ-1161 — no outage record, and no way to
                                 select the customers on one main
      · `autopay_enrolled`       OQ-1162 — autopay is a CAPTURE-ONLY flag
                                 (BR-CUS-059); nothing charges it, so the
                                 confirmation would promise a charge
      · `payment_plan_voided`    OQ-1163 — no plan status is `void`, and the
                                 2026-08-11 *"nodrop"* ruling removed the only
                                 automatic void there was
      · `door_hanger_left`       OQ-249  — Work is R5, the SAME blocker the
                                 three field-work rows above already carry
    """
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    blocked = {
        row["key"]: row["trigger_blocked_by"]
        for row in response.data["results"]
        if row["trigger_blocked_by"]
    }
    assert blocked == {
        # CR-009's seven, less the three P6.1 gave a writer. `high_usage_alert`
        # left this list on 2026-10-14: a reading flagged high fires it
        # (`CR-182-BRC10`, PO A4/A5, `apps/metering/high_consumption.py`).
        # `appointment_window`, `technician_on_the_way` and `completion_receipt`
        # left this list on 2026-10-04 (`2.517.0`): a job's assignment, the
        # technician's departure and the office's acceptance fire them
        # (`CR-168-BRC10` P6.1, lane SRV-5, `apps/work/visit_notices.py`).
        # `sla_breach` left this list on 2026-10-04: a Work rule's *Past due*
        # row fires it (`CR-168-BRC10` P3.58, lane SRV-4).
        "daily_digest": "OQ-262",
        "security_alerts": "OQ-262",
        # CR-048 B11's five.
        "statement_ready": "OQ-1160",
        "planned_outage_notice": "OQ-1161",
        "autopay_enrolled": "OQ-1162",
        "payment_plan_voided": "OQ-1163",
        "door_hanger_left": "OQ-249",
    }
    for row in response.data["results"]:
        if row["trigger_blocked_by"]:
            assert row["enabled"] is False, f"{row['key']} ships enabled with no trigger"
        else:
            assert row["enabled"] is True


def test_cr_009__an_event_the_platform_cannot_fire_is_refused_by_name(brazos, dana):
    """A tenant cannot invent an event, because only a writer in this codebase
    can fire one."""
    with tenant_ctx(brazos):
        response = _call(
            api.notification_rule, "get", brazos, dana, event_key="customer_birthday"
        )
    assert response.status_code == 422
    assert "customer_birthday" in str(response.data)


# ── the protective default the CR names in its own words ───────────────────
def test_cr_009__past_due_skips_payment_plans_by_default(brazos, dana):
    """CR-009, verbatim: *"Collections events default to their protective filters
    (past-due skips payment plans)"*."""
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    rows = {row["key"]: row for row in response.data["results"]}
    assert rows["past_due_reminder"]["skip_accounts_on_payment_plan"] is True
    assert rows["bill_ready"]["skip_accounts_on_payment_plan"] is False


def test_cr_009__no_medical_or_life_support_filter_exists_anywhere(brazos, dana):
    """PO ruling 2026-08-17, verbatim: *"Skip it ; not required as this point of
    time"*. Asserted as an ABSENCE so the ruling is visible in the suite — the
    clause IS in the PO's own written requirement, and a later reader diffing
    the CR against the product would otherwise rebuild it."""
    with tenant_ctx(brazos):
        response = _call(api.notification_rules, "get", brazos, dana)
    body = str(response.data).lower()
    assert "medical" not in body
    assert "life_support" not in body and "life-support" not in body
    assert not any(
        "medical" in field for field in rule_service.EDITABLE_RULE_FIELDS
    )
