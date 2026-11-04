# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-015 (manual reminder + disconnect-notice modals — bulk,
#           queue-writes, notice_history)   Screens: S35 · S34
# Rules:    BR-PAY-017 (manual sends share the ladder, the channels, the
#           exclusions and the STATE with the sequence engine) · BR-NOT-005
#           (queue-write only) · BR-PAY-029 (bulk actions on S34) · BR-CUS-039
#           (certified mail on the final tier; medical-hold excluded) ·
#           BR-BIL-007 (the reconnect fee is displayed from the charge code) ·
#           BR-CUS-043 (disconnect is blocked while a plan is active + current)
# ───────────────────────────────────────────────────────
"""The two S35 modals — and every reason an account is NOT told something."""

from datetime import date
from decimal import Decimal

import pytest

from apps.notifications import models as notification_models
from apps.payments import notices, plans
from apps.payments.collections_models import (
    NOTICE_DISCONNECT,
    NOTICE_REMINDER,
    OUTCOME_SKIPPED,
    TIER_FINAL_48_HOUR,
    TIER_SECOND_5_DAY,
    AccountCollectionState,
    NoticeHistory,
)
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_017_payment_plans import a_plan
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

CUT_DATE = date(2026, 8, 11)
TODAY = date(2026, 8, 1)
#: The prototype's own S35 fixture: RECONN $45.00, a Brazos Bend charge code.
RECONNECT_FEE = Decimal("45.00")


def four_accounts(brazos, dana):
    return [an_account(dana, brazos, account_no=f"A-1134{n}") for n in range(4)]


def test_us_pay_015_tc1__a_bulk_reminder_queues_per_account_and_records_history(brazos, dana):
    """TC-1 — four selected, one queue row set each, four history rows, one toast.

    The toast COUNT and the rows must agree: "Sent 4 ✓" over three queue rows is
    the shape a silently-dropped message has.
    """
    with tenant_ctx(brazos):
        accounts = four_accounts(brazos, dana)
        # `DEF-PAY-10651` — the channels are the Settings rule's and the
        # customer's: these four have no email and no SMS consent, so each gets
        # the printed letter, under the reminder's own kind.
        result = notices.send_reminders(
            account_ids=tuple(account.id for account in accounts),
            on_date=TODAY,
            actor=dana,
        )
        assert result.toast == "Sent 4 ✓"
        assert (
            NoticeHistory.objects.filter(notice_type=NOTICE_REMINDER, outcome="sent").count() == 4
        )
        queued = notification_models.OutboundMessage.objects.filter(source_type="reminder")
        assert queued.count() == 4
        assert {row.template_code for row in queued} == {"dunning"}


def test_us_pay_015_tc2__a_medical_hold_is_skipped_and_the_skip_is_recorded(brazos, dana):
    """TC-2 — *"Send 3 notices ✓"* from a selection of four (A15/BR-CUS-039).

    The skip is a ROW, not an absence: an account excluded for a medical hold
    and an account nobody ever chased must never look the same on S34.
    """
    with tenant_ctx(brazos):
        accounts = four_accounts(brazos, dana)
        held = accounts[3]
        result = notices.send_disconnect_notices(
            account_ids=tuple(account.id for account in accounts),
            tier=TIER_SECOND_5_DAY,
            cut_date=CUT_DATE,
            on_date=TODAY,
            medical_hold_account_ids=(held.id,),
            reconnect_fee=RECONNECT_FEE,
            actor=dana,
        )
        assert result.toast == "Sent 3 ✓ · 1 skipped"
        skip = NoticeHistory.objects.get(account=held, outcome=OUTCOME_SKIPPED)
        assert skip.skip_reason == notices.SKIP_MEDICAL_HOLD
        sent = NoticeHistory.objects.filter(notice_type=NOTICE_DISCONNECT, outcome="sent").first()
        assert (
            sent.detail["reconnect_fee"] == "45.00"
        ), "BR-BIL-007: displayed from the tenant's charge code, never invented here"


def test_us_pay_015_tc3__the_final_tier_forces_certified_mail_and_sms_never_stands_alone(
    brazos, dana
):
    """TC-3 — A19 rule 3. A 48-hour final delivered only by text is not a notice."""
    with tenant_ctx(brazos):
        accounts = four_accounts(brazos, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            notices.send_disconnect_notices(
                account_ids=(accounts[0].id,),
                tier=TIER_FINAL_48_HOUR,
                cut_date=CUT_DATE,
                on_date=TODAY,
                channels=("sms",),
                reconnect_fee=RECONNECT_FEE,
                actor=dana,
            )
        assert "certified mail" in str(refusal.value)

        notices.send_disconnect_notices(
            account_ids=(accounts[0].id,),
            tier=TIER_FINAL_48_HOUR,
            cut_date=CUT_DATE,
            on_date=TODAY,
            channels=("pdf_print",),
            reconnect_fee=RECONNECT_FEE,
            actor=dana,
        )
        row = NoticeHistory.objects.get(account=accounts[0], notice_type=NOTICE_DISCONNECT)
        assert row.detail["certified_mail"] is True


def test_us_pay_015_tc4__a_tier_never_double_sends(brazos, dana):
    """TC-4 — the manual modal and the engine advance ONE collection state.

    Two states — one for staff, one for the job — would send the 5-day notice
    twice to the customer who rang to complain about the first one.
    """
    with tenant_ctx(brazos):
        accounts = four_accounts(brazos, dana)
        target = accounts[0]
        notices.send_disconnect_notices(
            account_ids=(target.id,),
            tier=TIER_SECOND_5_DAY,
            cut_date=CUT_DATE,
            on_date=TODAY,
            reconnect_fee=RECONNECT_FEE,
            actor=dana,
        )
        assert AccountCollectionState.objects.get(account=target).tier == TIER_SECOND_5_DAY

        again = notices.send_disconnect_notices(
            account_ids=(target.id,),
            tier=TIER_SECOND_5_DAY,
            cut_date=CUT_DATE,
            on_date=date(2026, 8, 2),
            reconnect_fee=RECONNECT_FEE,
            actor=dana,
        )
        assert len(again.sent) == 0 and len(again.skipped) == 1
        assert again.skipped[0].skip_reason == notices.SKIP_TIER_ALREADY_SENT


def test_us_pay_015_tc5__a_reminder_that_queues_nothing_never_reports_sent(brazos, dana):
    """TC-5 (negative) — a send that queued nothing must not report success,
    which is exactly what a dropped message looks like.

    ⚠ RE-STATED 2026-10-29 (`DEF-PAY-10651`). It asserted that a call naming
    NO channel was refused; the reminder's channels are no longer the
    caller's (PO ruling 1A — the Settings rule and the customer decide), so
    the zero-channel case is now the rule switched OFF, and the guarantee is
    the same one: "Sent 0", a skip with its reason, no Sent row. The
    disconnect sender still refuses a zero-channel call (asserted below)."""
    from apps.notifications import rule_models

    with tenant_ctx(brazos):
        accounts = four_accounts(brazos, dana)
        rule_models.NotificationRule.objects.filter(
            tenant_id=brazos.id, event_key="past_due_reminder"
        ).update(enabled=False)
        result = notices.send_reminders(account_ids=(accounts[0].id,), on_date=TODAY, actor=dana)
        assert result.toast == "Sent 0 ✓ · 1 skipped"
        assert result.skipped[0].skip_reason == "rule_off"
        assert not NoticeHistory.objects.filter(outcome="sent").exists()
        assert not notification_models.OutboundMessage.objects.exists()
        with pytest.raises(PaymentRuleError):
            notices.send_disconnect_notices(
                account_ids=(accounts[0].id,),
                tier=TIER_SECOND_5_DAY,
                cut_date=CUT_DATE,
                on_date=TODAY,
                channels=(),
                actor=dana,
            )


def test_us_pay_015_tc6__the_queue_is_the_only_path(brazos, dana):
    """TC-6 (negative) — BR-NOT-005.

    Two assertions, because one is a claim and two are a guarantee: the module
    contains no provider client, and every row it produced is `queued` with no
    `sent_at`.
    """
    import apps.payments.notices as module

    source = open(module.__file__).read()
    assert not hasattr(module, "OutboundMessage"), (
        "payments never binds the queue MODEL — `queue_document` is the one write "
        "path (B1, B2 r16 #7). The class name appears in this module's docstring, "
        "which is where it explains why reaching for it is forbidden."
    )
    assert "from apps.notifications" not in source, (
        "the queue is resolved BY NAME, so payments carries no import of another "
        "module's internals (the seam idiom)"
    )
    with tenant_ctx(brazos):
        accounts = four_accounts(brazos, dana)
        notices.send_reminders(account_ids=(accounts[0].id,), on_date=TODAY, actor=dana)
        rows = notification_models.OutboundMessage.objects.all()
        assert rows.exists()
        assert all(row.status == notification_models.STATUS_QUEUED for row in rows)


def test_us_pay_015_tc8__an_active_current_plan_blocks_a_forced_disconnect(brazos, dana):
    """US-PAY-019 TC-6 reached through THIS door — the gate is server-side.

    BR-CUS-043 pauses disconnect while a plan is active and current, and the
    modal is where a clerk would otherwise force one through. The skip is
    recorded with its reason like any other.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        created = a_plan(brazos, dana, account)
        plans.activate_payment_plan(actor=dana, plan_id=created["id"], signed_on=date(2026, 8, 20))
        result = notices.send_disconnect_notices(
            account_ids=(account.id,),
            tier=TIER_SECOND_5_DAY,
            cut_date=CUT_DATE,
            on_date=date(2026, 8, 21),
            reconnect_fee=RECONNECT_FEE,
            actor=dana,
        )
        assert len(result.sent) == 0
        assert result.skipped[0].skip_reason == notices.SKIP_PLAN_PAUSE


def test_us_pay_015_tc7__notices_never_cross_tenants(brazos, dana):
    """TC-7 (isolation) — its templates, queue rows and history only."""
    with tenant_ctx(brazos):
        accounts = four_accounts(brazos, dana)
        notices.send_reminders(account_ids=(accounts[0].id,), on_date=TODAY, actor=dana)
        assert NoticeHistory.objects.filter(tenant=brazos).count() == NoticeHistory.objects.count()
