# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-009 (disconnect-notice generation: tiers, certified final,
#           medical-hold exclusion, notice_history) · US-NOT-010 (reminder /
#           dunning rendering: the tone→tier mapping + tenant-config day
#           numbers)   Screens: S94 · S95 · S22 · S34 · S35
# Rules:    BR-CUS-039 (A19 §2 tiers; certified mail on the final tier; the
#           reconnect fee is a charge code and never a default; medical hold
#           excluded) · BR-PAY-017 (the ladder + its intervals are tenant
#           config) · BR-PAY-035 (tone→tier, no free text) · BR-NOT-008 (a
#           regulated step ALWAYS renders the disconnect class) · BR-REP-016
#           (stage day numbers are config, 7/14/30 are seeds) · BR-NOT-005
#           (output is queue rows) · A19 rule 2 (no regulatory footer on
#           dunning) · A19 rule 3 (SMS supplements, never replaces)
# ───────────────────────────────────────────────────────
"""The two notice stories, on the story's own fixture figures.

US-NOT-009 §4: A-11024 Ridge Coffee $1,842.10 (tiers 1–2), the final-tier cut
date Aug 18 2026, the RECON charge code $45.00, and A-11020 the medical-hold
skip fixture. US-NOT-010 §4: the tone fixtures Friendly / Firm / Final and the
cadence change 7/14/30 → 10/20/35.

⚠ WHAT THESE CASES CANNOT ASSERT, SAID HERE RATHER THAN LEFT TO LOOK LIKE
COVERAGE. `notice_history` is payments' table (r12 #7) and this module cannot
write it (B1), so every case asserts the `history_appends` this service HANDS
BACK — the rows J4 step 2 requires — and not rows in that table. A caller that
drops them writes no history, and no test here can catch that. REPORTED.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.notifications import models, notices, rendering, template_service
from apps.notifications import template_models as tm

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

#: A19 §2, reduced to its own tokens. `{state_puc_ref}` and `{rights_footer}`
#: are both MANDATORY class content (US-NOT-007 TC-6 + BR-NOT-015 via CR-007)
#: and the catalog enforces both at save.
#:
#: ⚠ **REWRITTEN 2026-08-17 (CR-007) — ONE BODY BECAME THREE, AND THAT IS THE
#: POINT OF THE CHANGE.** These cases used to publish a single `disconnect_notice`
#: body and generate every tier from it, which is what the code did: BR-NOT-014
#: had been CONFIRMED since 2026-08-16 (*"the ladder selects by tier"*) and
#: `generate_disconnect_notice` still resolved the superseded single class at
#: every stage (DEF-193's open remainder — DEF-230 on the wrong id). The tests could not see it because
#: they published the same body for all three tiers.
#:
#: Now each tier resolves its OWN class, so each fixture body must pass its own
#: class's whitelist — and the fixtures below are proof the whitelists differ:
#: only the 10-day one may name `{pay_by_date}`, only the 5-day one
#: `{reconnect_fee}`, only the 48-hour one `{48h}` and `{certified_no}`. A body
#: that mixed them is refused at save, which is the mechanism BR-NOT-014 exists
#: to provide.
DISCONNECT_10_DAY_BODY = (
    "Your account is past due in the amount of {balance}. Please pay by {pay_by_date} "
    "to avoid service interruption. {rights_footer} {state_puc_ref}"
)

DISCONNECT_5_DAY_BODY = (
    "FINAL REMINDER. Service to {service_address} is scheduled for disconnection on "
    "{cut_date} unless {balance} is received. A reconnect fee of {reconnect_fee} "
    "applies. {rights_footer} {state_puc_ref}"
)

DISCONNECT_48_HOUR_BODY = (
    "NOTICE OF DISCONNECTION. Service will be disconnected on {cut_date} ({48h}). Pay "
    "{balance} immediately or call {support_phone}. Certified {certified_no}. "
    "{rights_footer} {state_puc_ref}"
)

#: The 5-day letter with NO fee token — the contrast case for TC-5.
DISCONNECT_5_DAY_NO_FEE = (
    "Service is scheduled for disconnection on {cut_date} unless {balance} is received. "
    "{rights_footer} {state_puc_ref}"
)

#: A19 r8's dunning row: a REMINDER. No `{state_puc_ref}` — it is not in the
#: class's catalog at all, so a body reaching for one is refused at save.
DUNNING_BODY = "Hi {first_name}, {balance} is {days_late} days late (stage day {stage_day})."


#: US-NOT-009 §4's fixture accounts. Real rows, because `queue_document`
#: resolves the recipient through customers' own published read and a fabricated
#: uuid is indistinguishable from another tenant's account (HR-1).
def an_account(actor, tenant, *, account_no):
    """A minimal account — the same shortcut `test_us_not_001_queue_write.py`
    takes and for the same reason: these cases are about notice generation, not
    about the customers activation path."""
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line=f"{account_no} Ridge Rd")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def publish(actor, code, body, **kwargs):
    # DEF-207: `register` reports `(row, created)`; this helper wants the row.
    template, _created = template_service.register(
        code=code,
        name=code,
        actor=actor,
        category=kwargs.pop("category", tm.VARIANT_DEFAULT),
    )
    draft = template_service.save_draft(template=template, body=body, actor=actor, **kwargs)
    template_service.publish(version_row=draft, actor=actor)
    return template, draft


# ── US-NOT-009 TC-1 · the 10-day letter ─────────────────────────────────────
def test_us_not_009_tc1__tier_1_renders_from_the_published_version_and_queues(brazos, dana):
    """US-NOT-009 TC-1: *"10-day letter rendered from published S94 version —
    'past due in the amount of $1,842.10… pay by {pay_by_date}'; paper queue
    row; notice_history append (tier, template version, channel, when)."*

    Money renders at 2dp WITH its currency (A19 header, CLAUDE.md rule 2) — the
    figure reads `1842.10 USD`, never `1842.1`, and a float would be refused
    outright by the renderer.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        _template, version = publish(
            dana, "disconnect_notice_10_day", DISCONNECT_10_DAY_BODY
        )
        result = notices.generate_disconnect_notice(
            account_id=account.pk,
            tier=notices.TIER_FIRST_10_DAY,
            balance=Decimal("1842.100000"),
            cut_date=date(2026, 8, 18),
            pay_by_date=date(2026, 8, 8),
            reconnect_fee=Decimal("45.00"),
            state_puc_ref="TX PUC Substantive Rule 25.29",
            on_date=date(2026, 8, 1),
            actor=dana,
        )

    assert result.template_code == "disconnect_notice_10_day"
    assert "$1,842.10" in result.artifact.body
    # ⚠ THE FEE IS NOT ON THIS LETTER AND ITS ABSENCE IS THE RULE, NOT A GAP.
    # This case used to assert `45.00 USD` appeared, because every tier rendered
    # from ONE body that named `{reconnect_fee}` (DEF-193). A19 §2's tier-1
    # sentence has no fee in it — the fee arrives with the 5-day FINAL REMINDER —
    # and `disconnect_notice_10_day`'s palette does not contain the token, so a
    # 10-day warning that quoted a reconnect fee could not be saved at all
    # (BR-NOT-014). The caller still PASSES one, and it is correctly ignored.
    assert "$45.00" not in result.artifact.body
    assert "TX PUC Substantive Rule 25.29" in result.artifact.body
    assert result.artifact.template_version == version.version
    assert len(result.queued_message_ids) == 1
    # BR-NOT-005: queued, never sent — and stated as a value, not inferred.
    assert result.sent is False
    with tenant_ctx(brazos):
        row = models.OutboundMessage.objects.get(pk=result.queued_message_ids[0])
        assert row.status == models.STATUS_QUEUED
        assert row.template_version == version.version

    # J4 step 2's contract, handed back for payments to record.
    assert [append.outcome for append in result.history_appends] == ["sent"]
    assert result.history_appends[0].tier == notices.TIER_FIRST_10_DAY
    assert result.history_appends[0].detail["template_version"] == version.version


# ── US-NOT-009 TC-2/TC-3 · certified mail on the final tier ─────────────────
def test_us_not_009_tc2_tc3__the_final_tier_forces_certified_mail_and_sms_never_stands_alone(
    brazos, dana
):
    """US-NOT-009 TC-2: *"Certified-mail forced ON (server-side even if forged
    off)."* TC-3: *"a notice request with SMS-only is rejected."* A19 rule 3 is
    the reason both are one rule: the certified LETTER is the legal instrument
    and a text message supplements it.

    PROVED RED by deleting the `certified and CHANNEL_PRINT not in channels`
    branch: an SMS-only 48-hour final notice was then generated and queued, and
    this failed with `Failed: DID NOT RAISE NoticeRefused`.

    ⚠ The certified NUMBER is never produced — it comes from a provider response
    at dispatch and no provider exists on any channel (PO ruling 2026-08-15:
    delivery is out of this release). The case asserts the problem row that says
    so, because a fabricated tracking number on a legal notice is the failure
    this reports its way out of.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        publish(dana, "disconnect_notice_48_hour", DISCONNECT_48_HOUR_BODY)

        with pytest.raises(notices.NoticeRefused, match="certified mail"):
            notices.generate_disconnect_notice(
                account_id=account.pk,
                tier=notices.TIER_FINAL_48_HOUR,
                balance=Decimal("1842.10"),
                cut_date=date(2026, 8, 18),
                reconnect_fee=Decimal("45.00"),
                state_puc_ref="TX PUC 25.29",
                on_date=date(2026, 8, 16),
                actor=dana,
                channels=(models.CHANNEL_SMS,),
            )

        result = notices.generate_disconnect_notice(
            account_id=account.pk,
            tier=notices.TIER_FINAL_48_HOUR,
            balance=Decimal("1842.10"),
            cut_date=date(2026, 8, 18),
            reconnect_fee=Decimal("45.00"),
            state_puc_ref="TX PUC 25.29",
            on_date=date(2026, 8, 16),
            actor=dana,
            channels=(models.CHANNEL_PRINT, models.CHANNEL_SMS),
        )

    assert result.certified_mail is True
    assert result.history_appends[0].detail["certified_mail"] is True
    assert notices.NOTICE_CERTIFIED_NUMBER_UNAVAILABLE in {
        problem["code"] for problem in result.problems
    }
    # The number is a NAMED absence on the document, never a made-up string.
    assert rendering.ABSENT_MARK in result.artifact.body


# ── US-NOT-009 TC-4 · the medical hold ──────────────────────────────────────
def test_us_not_009_tc4__a_medical_hold_refuses_generation_and_records_the_skip(brazos, dana):
    """US-NOT-009 TC-4, verbatim: *"Any tier requested for medical-hold A-11020
    → Generation refuses; NOTHING queued; notice_history records the SKIP with
    reason medical_hold (J4 contract)."*

    PROVED RED by deleting the `if medical_hold:` branch: the notice was
    generated, a print row was queued for A-11020 and this failed at
    `assert result.queued_message_ids == ()` — i.e. a customer on a physician-
    certified medical hold was sent a disconnection notice.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11020")
        publish(dana, "disconnect_notice_5_day", DISCONNECT_5_DAY_NO_FEE)
        result = notices.generate_disconnect_notice(
            account_id=account.pk,
            tier=notices.TIER_SECOND_5_DAY,
            balance=Decimal("612.44"),
            cut_date=date(2026, 8, 18),
            state_puc_ref="TX PUC 25.29",
            on_date=date(2026, 8, 11),
            actor=dana,
            medical_hold=True,
        )
        assert models.OutboundMessage.objects.count() == 0

    assert result.skipped is True
    assert result.queued_message_ids == ()
    assert result.artifact is None
    assert [append.skip_reason for append in result.history_appends] == ["medical_hold"]


# ── US-NOT-009 TC-5 · the reconnect fee is never invented ───────────────────
def test_us_not_009_tc5__a_missing_reconnect_fee_refuses_rather_than_defaulting(brazos, dana):
    """US-NOT-009 TC-5, verbatim: *"Reconnect-fee token with no RECON charge
    code configured → Render fails with a config error naming the charge code —
    the fee is never invented or defaulted (BR-BIL-007)."*

    This is the one token that does NOT get the renderer's named-absence
    treatment, and the asymmetry is deliberate: OQ-117's closure lets a document
    go out with a named gap because the customer needs the rest of it, but a
    disconnection notice that misstates what must be paid to restore service is
    not a document with a gap — it is a wrong instruction on a legal notice.

    PROVED RED by removing the refusal: the letter rendered with `——` where
    $45.00 belongs, and this failed with `Failed: DID NOT RAISE NoticeRefused`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        # THE 5-DAY TIER, because it is the only one whose palette carries
        # `{reconnect_fee}` at all (BR-NOT-014). Before CR-007 this case used the
        # 10-day tier and a shared body, which could never have caught a tier
        # mix-up: the token was legal on every tier because there was one tier.
        publish(dana, "disconnect_notice_5_day", DISCONNECT_5_DAY_BODY)
        with pytest.raises(notices.NoticeRefused, match="RECONN charge code"):
            notices.generate_disconnect_notice(
                account_id=account.pk,
                tier=notices.TIER_SECOND_5_DAY,
                balance=Decimal("1842.10"),
                cut_date=date(2026, 8, 18),
                state_puc_ref="TX PUC 25.29",
                on_date=date(2026, 8, 1),
                actor=dana,
            )
        assert models.OutboundMessage.objects.count() == 0


def test_us_not_009_generation_refuses_when_no_disconnect_template_is_published(brazos, dana):
    """Field map N-1's posture at the generation door: *"content never
    invented."* Nothing is queued either — a queued row that can never render is
    a customer who is never told, which is worse than a refusal somebody sees.

    ⚠ **THE SET-UP CHANGED ON 2026-08-17 AND THE CHANGE IS THE GOOD NEWS.** This
    case used to need no set-up: NO tenant had a disconnect template, because the
    three tiers shipped empty (OQ-253). CR-007 seeds all three at provisioning,
    so the unpublished state now has to be CREATED — the seeded 10-day version is
    archived first. That is the defect DEF-163 was about, gone: the refusal below
    is a real edge case again instead of every tenant's normal Tuesday.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        tm.NotificationTemplateVersion.objects.filter(
            tenant_id=brazos.pk,
            template__code="disconnect_notice_10_day",
            status=tm.VERSION_PUBLISHED,
        ).update(status=tm.VERSION_ARCHIVED)
        with pytest.raises(notices.NoticeRefused, match="no published"):
            notices.generate_disconnect_notice(
                account_id=account.pk,
                tier=notices.TIER_FIRST_10_DAY,
                balance=Decimal("10.00"),
                cut_date=date(2026, 8, 18),
                on_date=date(2026, 8, 1),
                actor=dana,
            )
        assert models.OutboundMessage.objects.count() == 0


# ── US-NOT-010 TC-1/TC-2 · the tone mapping, one table, two doors ───────────
def test_us_not_010_tc1_tc2__friendly_renders_dunning_and_firm_routes_to_the_regulated_class(
    brazos, dana
):
    """US-NOT-010 TC-1: the due+3 step renders the dunning stage — *"unpaid-bill
    table, days-late, plan offer, NO footer"*. TC-2: *"Priya picks tone 'Firm'
    → Resolves via the BR-PAY-035 mapping to the 10-day step — same mapping as
    the engine, no separate path."*

    And BR-NOT-008 is the part that surprises: 'firm' does not produce a
    sterner reminder, it produces the REGULATED DISCONNECT NOTICE. *"Regulated
    ladder steps ALWAYS render the disconnect-notice template class regardless
    of the tone picked in the reminder modal."*

    PROVED RED by making `TONE_TO_STEP["firm"]` map to `None`: the firm tone
    then rendered the courtesy dunning letter to a customer at the 10-day step,
    and this failed with `assert 'dunning' == 'disconnect_notice'`.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        publish(dana, "dunning", DUNNING_BODY)
        publish(dana, "disconnect_notice_10_day", DISCONNECT_10_DAY_BODY)

        friendly = notices.generate_reminder(
            account_id=account.pk,
            balance=Decimal("412.80"),
            days_late=9,
            on_date=date(2026, 7, 9),
            actor=dana,
            tone=notices.TONE_FRIENDLY,
        )
        firm = notices.generate_reminder(
            account_id=account.pk,
            balance=Decimal("412.80"),
            on_date=date(2026, 7, 16),
            actor=dana,
            tone=notices.TONE_FIRM,
            cut_date=date(2026, 7, 26),
            state_puc_ref="TX PUC 25.29",
        )

    assert friendly.template_code == notices.CLASS_DUNNING
    assert "$412.80" in friendly.artifact.body
    # A19 rule 2 — a reminder carries no regulatory footer, and the catalog is
    # what makes that structural: `{state_puc_ref}` is not in the dunning
    # palette at all, so the body could never have been saved with one.
    assert "state_puc_ref" not in rendering.tokens_in(DUNNING_BODY)

    # BR-NOT-008 — a "firm" tone renders a REGULATED notice, and BR-NOT-014
    # decides WHICH: the 10-day class, not the superseded single class this
    # assertion named until 2026-08-17 (DEF-193). The difference is the whole
    # point of the three slots — "final" renders `disconnect_notice_48_hour`,
    # at certified postage.
    assert firm.template_code == notices.TIER_TO_CLASS[notices.TIER_FIRST_10_DAY]
    assert firm.template_code == "disconnect_notice_10_day"
    assert firm.tier == notices.TIER_FIRST_10_DAY


def test_us_not_010_tc5__a_free_text_tone_is_refused(brazos, dana):
    """US-NOT-010 TC-5, verbatim: *"API reminder request with tone
    'urgent-custom' → Rejected — free-text tones do not exist (BR-PAY-035)."*

    Server-side, so it holds for an API caller and not only for a select box:
    the tone chooses WHICH LETTER, and two of the three choose the regulated
    disconnect notice.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        with pytest.raises(notices.NoticeRefused, match="not a tone"):
            notices.generate_reminder(
                account_id=account.pk,
                balance=Decimal("412.80"),
                on_date=date(2026, 7, 9),
                actor=dana,
                tone="urgent-custom",
            )


def test_us_not_010_tc4__a_regulated_tone_with_no_cut_date_refuses(brazos, dana):
    """US-NOT-010 TC-4's boundary: *"the ladder's 10-day/5-day/48h NOTICE steps
    route to US-NOT-009 (disconnect class, regulated); dunning never renders a
    cut date it doesn't have."*

    So a 'final' tone with no cut date cannot silently fall back to a reminder —
    that would downgrade a 48-hour disconnection warning into a courtesy letter
    and the customer would never learn the date."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        publish(dana, "dunning", DUNNING_BODY)
        with pytest.raises(notices.NoticeRefused, match="cut date"):
            notices.generate_reminder(
                account_id=account.pk,
                balance=Decimal("412.80"),
                on_date=date(2026, 7, 30),
                actor=dana,
                tone=notices.TONE_FINAL,
            )


# ── US-NOT-010 TC-3 · the day numbers are CONFIG ────────────────────────────
def test_us_not_010_tc3__stage_day_numbers_re_render_from_tenant_config(brazos, dana):
    """US-NOT-010 TC-3 / US-NOT-007 TC-3 — the same assertion from two stories:
    *"Tenant cadence 7/14/30 → 10/20/35 → stage banners render from config; no
    constant anywhere (BR-REP-016)."*

    PROVED RED by replacing `stage_days()`'s config read with the literal
    `(7, 14, 30)`: the letter kept printing `stage day 3` after the tenant moved
    its ladder to 6, and this failed with `assert 'stage day 6' in ...` — i.e. a
    customer would have been told the wrong day to pay by while every other test
    stayed green.
    """
    from apps.tenancy import services as tenancy_services

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-11024")
        publish(dana, "dunning", DUNNING_BODY)
        seeded = notices.generate_reminder(
            account_id=account.pk,
            balance=Decimal("412.80"),
            on_date=date(2026, 7, 9),
            actor=dana,
        )
        assert "stage day 3" in seeded.artifact.body  # the S70 seed, read not assumed

        tenancy_services.save_settings_family(dana, "collections", {"reminder_days_after_due": 6})
        changed = notices.generate_reminder(
            account_id=account.pk,
            balance=Decimal("412.80"),
            on_date=date(2026, 7, 9),
            actor=dana,
        )

    assert "stage day 6" in changed.artifact.body


def test_us_not_010_the_stage_day_read_refuses_rather_than_printing_the_seeds(
    brazos, dana, monkeypatch
):
    """BR-REP-016 says 7/14/30 are SEEDS of a tenant setting. An unreachable
    setting is therefore not a setting, and printing the seed would put a date
    on a letter that the tenant never configured — silently, and with every gate
    still green. The seam refuses instead."""
    from apps.notifications import tenancy_seam

    monkeypatch.setattr(tenancy_seam, "_resolve", lambda *args, **kwargs: None)
    with tenant_ctx(brazos):
        with pytest.raises(tenancy_seam.CollectionsConfigUnavailable, match="7/14/30"):
            notices.stage_days()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-009@4b7d13e (the four sources — EP-NOT-03 US-NOT-009/010 §1/§3/§5 · 10-notifications/02-business-rules.md · 04-flows.md §3 · J4-collections.md)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — notice generation)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the trigger surfaces are customers'/payments') E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · five guards proved RED before green (hard-won law 7):
#         the certified-mail forcing, the medical-hold refusal, the
#         missing-reconnect-fee refusal, the tone→class routing and the
#         config-not-constant stage day; transcripts in the lane report
# exceptions: `notice_history` ROWS ARE NOT ASSERTED IN THAT TABLE — it is
#         payments' (r12 #7) and this module cannot write it (B1). The cases
#         assert the `history_appends` the service hands back. A caller that
#         drops them writes no history and no test here catches that. REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
