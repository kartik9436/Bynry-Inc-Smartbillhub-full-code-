# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10651 — the automatic past-due reminder (ladder rung 1,
#           due + 3 days) queued nothing a customer could receive, and the
#           notice history said Sent anyway
# Ruling:   PO 2026-10-29, *"1A 2A 3A 4B, start"* — decision log entry of that
#           date (the rule's on/off and channels; email if an address, SMS only
#           with consent; a printed letter for a customer with neither; due + 3
#           unchanged; no historic list)
# Rules:    BR-PAY-017 (the ladder, due + 3) · BR-NOT-009 (SMS quiet hours, the
#           dispatcher's) · BR-NOT-005 (queue only) · CLAUDE.md rule 6
#           (idempotency) · hard-won law 1 (history must not claim a send)
# ───────────────────────────────────────────────────────
"""The friendly reminder, end to end: what is QUEUED, and what the history SAYS.

Every case asserts the template code on the queued row, because the defect was a
row that existed, was counted, and could never render: `collections_reminder_
friendly` is catalogued nowhere. A count of rows cannot see that; a code can.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone as django_timezone

from apps.customers import models as customer_models
from apps.notifications import dispatch_config, dispatcher, models as nmodels, rendering
from apps.notifications import rule_models, template_models
from apps.payments import collections_schedule, ladder, notices, notices_by_hand
from apps.payments.collections_models import (
    NOTICE_REMINDER,
    OUTCOME_SENT,
    OUTCOME_SKIPPED,
    TIER_FRIENDLY,
    AccountCollectionState,
    NoticeHistory,
)
from apps.tenancy import models as tenancy_models

from tests.test_cr049_t2_dispatch_freeze import provider_connected  # noqa: F401 — fixture
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

DUE_ON = date(2026, 10, 1)
#: BR-PAY-017's due + 3 — the day rung 1 falls due under the seeded setting.
DUE_PLUS_3 = DUE_ON + timedelta(days=3)
OWED = Decimal("148.20")
FLOOR = Decimal("25.00")


def _debtor(tenant, dana, *, account_no, email=None, phone=None, sms=False, contact=True):
    account = an_account(dana, tenant, account_no=account_no)
    if sms:
        account.sms_reminders = True
        account.save(update_fields=["sms_reminders"])
    if contact:
        customer_models.Contact.objects.create(
            tenant=tenant,
            account=account,
            full_name="Rosa Delgado",
            email=email,
            phone=phone,
            is_primary=True,
        )
    an_issued_bill(
        tenant,
        account,
        number=f"BL-{account_no}",
        total=OWED,
        issued_on=DUE_ON,
        due_date=DUE_ON,
    )
    return account


def _run(account, *, as_of=DUE_PLUS_3):
    return ladder.run_ladder(account_ids=(account.id,), as_of=as_of, balance_floor=FLOOR)


def _queued(account):
    return {
        (row.channel, row.template_code)
        for row in nmodels.OutboundMessage.objects.filter(account_id=account.id)
    }


def _history(account):
    return sorted(
        (row.channel or "", row.outcome, row.skip_reason or "")
        for row in NoticeHistory.objects.filter(account=account, notice_type=NOTICE_REMINDER)
    )


def _tier(account):
    state = AccountCollectionState.objects.filter(account=account).first()
    return state.tier if state else None


def _rule_enabled(tenant, enabled):
    row = rule_models.NotificationRule.objects.filter(
        tenant_id=tenant.id, event_key="past_due_reminder"
    ).first()
    if row is None:
        from apps.notifications import rule_service

        rule_service.seed_rules()
        row = rule_models.NotificationRule.objects.get(
            tenant_id=tenant.id, event_key="past_due_reminder"
        )
    row.enabled = enabled
    row.save(update_fields=["enabled"])


# ══════════════════════════════════════════════════════════════════════════
# 1A — the rule's channels, per the customer's contacts and consent
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_10651__the_scheduled_run_queues_email_and_sms_from_the_rule(
    brazos, dana, monkeypatch
):
    """Email address + SMS consent, run by the SCHEDULE at due + 3 ⇒ one
    `email_past_due` and one `sms_past_due`, no letter, history Sent per channel,
    and the ladder at rung 1."""
    with tenant_ctx(brazos):
        row = tenancy_models.TenantSettings.objects.get(tenant=brazos)
        row.timezone = "America/Chicago"
        document = dict(row.collections or {})
        document["collections_schedule_enabled"] = True
        document["collections_schedule_hour"] = 6
        row.collections = document
        row.save(update_fields=["timezone", "collections", "updated_at"])
        account = _debtor(
            brazos,
            dana,
            account_no="A-10651",
            email="rosa@example.com",
            phone="+1 512 555 0142",
            sms=True,
        )
        # 06:05 Central on due + 3.
        moment = datetime(2026, 10, 4, 11, 5, tzinfo=UTC)
        monkeypatch.setattr(django_timezone, "now", lambda: moment)
        report = collections_schedule._run_within_tenant(
            {"subdomain": "brazos", "ran": False, "problems": []}, force=False
        )
        assert report["ran"] is True, report.get("reason")
        assert _queued(account) == {
            (nmodels.CHANNEL_EMAIL, "email_past_due"),
            (nmodels.CHANNEL_SMS, "sms_past_due"),
        }
        assert _history(account) == [
            ("email", OUTCOME_SENT, ""),
            ("sms", OUTCOME_SENT, ""),
        ]
        assert _tier(account) == TIER_FRIENDLY


def test_def_pay_10651__no_sms_consent_sends_email_only(brazos, dana):
    with tenant_ctx(brazos):
        account = _debtor(
            brazos, dana, account_no="A-10652", email="rosa@example.com", phone="+1 512 555 0142"
        )
        _run(account)
        assert _queued(account) == {(nmodels.CHANNEL_EMAIL, "email_past_due")}
        assert _history(account) == [
            ("email", OUTCOME_SENT, ""),
            ("sms", OUTCOME_SKIPPED, "no_sms_consent"),
        ]
        assert _tier(account) == TIER_FRIENDLY


# ══════════════════════════════════════════════════════════════════════════
# 2A — the printed letter, only for a customer nothing digital can reach
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_10651__no_contacts_gets_the_printed_letter(brazos, dana):
    with tenant_ctx(brazos):
        account = _debtor(brazos, dana, account_no="A-10653", contact=False)
        _run(account)
        assert _queued(account) == {(nmodels.CHANNEL_PRINT, "dunning")}
        letter = nmodels.OutboundMessage.objects.get(account_id=account.id)
        assert letter.template_version is not None, "the letter must render: pinned at queue"
        assert letter.source_type == "reminder"
        history = _history(account)
        assert ("pdf_print", OUTCOME_SENT, "") in history
        assert ("email", OUTCOME_SKIPPED, "no_contact") in history
        assert _tier(account) == TIER_FRIENDLY


def test_def_pay_10651__the_letter_is_seeded_in_eleven_languages(brazos):
    with tenant_ctx(brazos):
        languages = set(
            template_models.NotificationTemplate.objects.filter(
                tenant_id=brazos.id, code="dunning"
            ).values_list("language", flat=True)
        )
    assert {
        "default",
        "en",
        "es",
        "es-MX",
        "de",
        "hi",
        "fr-FR",
        "id-ID",
        "it-IT",
        "ja-JP",
        "ko-KR",
        "pt-BR",
    } <= languages


# ══════════════════════════════════════════════════════════════════════════
# the rule's on/off, and a template nobody published
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_10664__rule_off_skips_the_reminder_and_the_ladder_carries_on(brazos, dana):
    """⚠ AMENDED 2026-10-29 (`DEF-PAY-10664`, PO B4 A, reversing `DEF-PAY-10651`
    judgment 4): this read *"rule off queues nothing and the ladder does not
    advance"*, which stopped every account at rung 1 forever. Rule OFF now
    means SKIP the reminder and carry on: nothing queued, history *Not sent ·
    rule off*, the account on rung 1 with NO last-notice date (nobody was
    written to), and the 10-day notice on its own day, due + 13 — unchanged.
    RED on the tip: ``assert None == 'friendly'``."""
    from apps.payments.collections_models import TIER_FIRST_10_DAY

    with tenant_ctx(brazos):
        _rule_enabled(brazos, False)
        account = _debtor(
            brazos, dana, account_no="A-10654", email="rosa@example.com", phone="+1", sms=True
        )
        run = _run(account)
        assert _queued(account) == set()
        assert _history(account) == [("", OUTCOME_SKIPPED, "rule_off")]
        assert _tier(account) == TIER_FRIENDLY, "rule off skips the reminder; the ladder goes on"
        state = AccountCollectionState.objects.get(account=account)
        assert state.last_notice_on is None, "nobody was written to, so no notice date"
        assert [d.skip_reason for d in run.skipped] == ["rule_off"]
        # The 10-day rung's own timing is unchanged: not on due + 12 …
        _run(account, as_of=DUE_ON + timedelta(days=12))
        assert _tier(account) == TIER_FRIENDLY
        # … and on due + 13, as for a customer who was reminded.
        _run(account, as_of=DUE_ON + timedelta(days=13))
        assert _tier(account) == TIER_FIRST_10_DAY


def test_def_pay_10664__nothing_queued_for_any_other_reason_still_does_not_advance(brazos, dana):
    """Only the deliberate rule-off continues. A reminder that could not go —
    here no published wording on any channel — stays an honest *not taken*."""
    with tenant_ctx(brazos):
        template_models.NotificationTemplateVersion.objects.filter(
            tenant_id=brazos.id, template__code__in=("email_past_due", "sms_past_due", "dunning")
        ).update(status="archived")
        account = _debtor(brazos, dana, account_no="A-10664", email="rosa@example.com")
        _run(account)
        assert _queued(account) == set()
        assert all(row[1] == OUTCOME_SKIPPED for row in _history(account))
        assert ("", OUTCOME_SKIPPED, "rule_off") not in _history(account)
        assert _tier(account) is None, "a reminder that could not go is not a step taken"


def test_def_pay_10651__a_missing_template_is_not_sent_and_never_said_to_be(brazos, dana):
    with tenant_ctx(brazos):
        template_models.NotificationTemplateVersion.objects.filter(
            tenant_id=brazos.id, template__code="email_past_due"
        ).update(status="archived")
        account = _debtor(brazos, dana, account_no="A-10655", email="rosa@example.com")
        _run(account)
        history = _history(account)
        assert ("email", OUTCOME_SKIPPED, "template_missing") in history
        assert ("email", OUTCOME_SENT, "") not in history
        assert (nmodels.CHANNEL_EMAIL, "email_past_due") not in _queued(account)
        # Nothing digital could go, so the letter is the fallback.
        assert _queued(account) == {(nmodels.CHANNEL_PRINT, "dunning")}


# ══════════════════════════════════════════════════════════════════════════
# rule 6 — the same day twice is one reminder
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_10651__a_rerun_the_same_day_writes_no_duplicate(brazos, dana):
    with tenant_ctx(brazos):
        account = _debtor(brazos, dana, account_no="A-10656", email="rosa@example.com")
        _run(account)
        _run(account)
        notices.send_reminders(account_ids=(account.id,), on_date=DUE_PLUS_3, actor=dana)
        assert nmodels.OutboundMessage.objects.filter(account_id=account.id).count() == 1
        sent = [row for row in _history(account) if row[1] == OUTCOME_SENT]
        assert sent == [("email", OUTCOME_SENT, "")]


def test_def_pay_10651__the_manual_send_shares_the_path(brazos, dana):
    """S35 *Send reminder* (tone friendly) reaches the same resolution."""
    with tenant_ctx(brazos):
        account = _debtor(brazos, dana, account_no="A-10657", email="rosa@example.com")
        body = notices_by_hand.send(
            account_ids=(account.id,),
            as_of=DUE_PLUS_3,
            tone="friendly",
            channels=("pdf_print",),
            balance_floor=FLOOR,
            idempotency_key="k-10657",
            actor=dana,
        )
        assert [row["account_id"] for row in body["sent"]] == [str(account.id)]
        assert _queued(account) == {(nmodels.CHANNEL_EMAIL, "email_past_due")}


# ══════════════════════════════════════════════════════════════════════════
# BR-NOT-009 — quiet hours are the dispatcher's, and they hold the text
# ══════════════════════════════════════════════════════════════════════════
def test_def_pay_10651__the_sms_holds_outside_quiet_hours(brazos, dana, provider_connected):
    from apps.integrations import services as integrations_services

    calls = []

    def adapter(channel, messages):
        calls.append(channel)
        return {m["id"]: {"provider_reference": "p", "status": "sent"} for m in messages}

    import pytest as _pytest

    patch = _pytest.MonkeyPatch()
    patch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    patch.setattr(
        rendering,
        "render_for_dispatch",
        lambda row: rendering.RenderedArtifact(
            template_code=row.template_code,
            template_version=row.template_version or 1,
            language=row.template_language,
            channel=row.channel,
            body="Past due",
        ),
    )
    try:
        with tenant_ctx(brazos):
            dispatch_config.update_dispatch_settings(actor=dana, sms_dispatch_active=True)
            account = _debtor(brazos, dana, account_no="A-10658", phone="+1 512 555 0142", sms=True)
            _run(account)
            assert _queued(account) == {(nmodels.CHANNEL_SMS, "sms_past_due")}
            # 22:15 Central — outside the seeded 08:00–21:00 window.
            result = dispatcher.dispatch_cycle(
                now=datetime(2026, 10, 5, 3, 15, tzinfo=UTC), channels=(nmodels.CHANNEL_SMS,)
            )
            assert calls == []
            assert dispatcher.CYCLE_QUIET_HOURS_HOLD in {p["code"] for p in result.problems}
            row = nmodels.OutboundMessage.objects.get(account_id=account.id)
            assert row.status == nmodels.STATUS_QUEUED and row.attempts == 0
    finally:
        patch.undo()


def test_def_pay_10651__the_rule_screen_is_told_the_letter_is_not_floored(brazos):
    """The Settings rule drew *Printed letter · Always on* — a lock over a
    switch the server honours. The wire now says which events the print floor
    reaches, from the one floor table."""
    from apps.notifications import rule_service

    with tenant_ctx(brazos):
        assert rule_service.rule("past_due_reminder").as_wire()["print_is_floor"] is False
        assert rule_service.rule("disconnect_notice").as_wire()["print_is_floor"] is True
