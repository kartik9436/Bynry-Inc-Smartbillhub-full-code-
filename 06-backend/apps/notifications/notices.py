# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-009 (disconnect-notice generation: tiers, certified final,
#           medical-hold exclusion, notice_history) · US-NOT-010 (reminder /
#           dunning rendering: the tone→tier mapping + tenant-config day
#           numbers)   Screens: S94 · S95 · S22 · S34 · S35
# Rules:    BR-CUS-039 (tiers render A19 §2 content; certified mail on the final
#           tier; the reconnect fee comes from a tenant charge code and is NEVER
#           hardcoded; medical-hold accounts excluded) · BR-PAY-017 (10-day →
#           5-day → 48h certified final; the ladder and its intervals are tenant
#           config; manual sends use the same ladder, channels and exclusions) ·
#           BR-PAY-035 (tone→tier: friendly = due+3 · firm = 10-day · final =
#           5-day/48h — free-text tones do not exist) · BR-NOT-008 (a regulated
#           ladder step ALWAYS renders the disconnect class, whatever tone was
#           picked) · BR-REP-016 (dunning stage day numbers render from the
#           tenant cadence config — 7/14/30 are seeds, never constants) ·
#           BR-NOT-005 (output is QUEUE ROWS; nothing is ever sent inline) ·
#           A19 rule 2 (dunning is a courtesy reminder with NO regulatory
#           footer) · A19 rule 3 (SMS supplements the mailed notice and never
#           replaces it) · BR-TEN-043 (a business date is an argument) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money is Decimal at 2dp)
#           · rule 7 (audited)
# Tests:    06-backend/tests/test_us_not_009_010_notice_generation.py ·
#           06-backend/tests/test_us_not_009_010_notice_isolation.py
# Impacts:  apps/notifications/services.queue_document (the ONE write path this
#           uses) · apps/notifications/template_service (resolves the tier's
#           published version) · the S22/S34/S35 trigger surfaces, which are
#           customers' and payments' and are NOT in this lane — their US-IDs are
#           in the docstring, because G10 reads any US-ID in this block as "this
#           file ships that story's test cases", Impacts lines included.
# ───────────────────────────────────────────────────────
"""ONE notice-generation service — every trigger surface renders through it.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides what a customer about
to be disconnected is told, and enforces the certified-mail constraint that
makes a 48-hour notice legally effective. AI-authored 2026-08-15 under the PO
ruling of 2026-08-09; row required in 12-governance/09-human-review-ledger.md.

US-NOT-009 §1: *"ONE disconnect-notice generation service that every trigger
surface calls — the S22 modal (US-CUS-015), the sequence engine (US-PAY-014),
the S35 bulk modal (US-PAY-015)."* US-NOT-010 §1 adds the reminder half and locks
it to one mapping: *"friendly = due+3 reminder · firm = 10-day · final =
5-day/48h — free-text tones do not exist."*

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS RENDERS AND QUEUES. IT NEVER SENDS, AND IT NEVER WRITES            ║
║  `notice_history` — THAT TABLE IS PAYMENTS'.                             ║
╚══════════════════════════════════════════════════════════════════════════╝
BR-NOT-005: output is queue rows. There is no SMTP, ESP, Twilio or print-vendor
call in this file and there must not be one.

`notice_history` (B2 r12 #7) is payments' table and `apps/payments/notices.py`
`record_notice` is documented as *"the ONLY writer"* of it. The B1 boundary is
absolute — cross-module WRITES are forbidden — so this service does not write
one row of it and does not reach for the function that does. Instead every
result carries `history_appends`: the exact rows J4 step 2 requires (*"every send
AND skip"*), as data, for the CALLER that owns the table to record.

⚠ THAT IS A REAL, REPORTED SEAM AND NOT A TIDY ONE. A caller that ignores
`history_appends` produces a notice with no history row, and nothing here can
stop it. The alternative — notifications writing payments' table — trades a
reportable gap for a boundary violation, which is the trade B1 exists to refuse.
`apps/payments/notices.py` already records its own history for the paths IT
drives; this service exists for the S22/customers surface and for any future
trigger, and it hands the rows back rather than assuming.

────────────────────────────────────────────────────────────────────────────
THE TONE→TIER MAPPING IS ONE TABLE, USED BY BOTH DOORS (BR-PAY-035)
────────────────────────────────────────────────────────────────────────────
US-NOT-010 TC-2: *"Priya picks tone 'Firm' in S35 → Resolves via the BR-PAY-035
mapping to the 10-day step's rendering — same mapping as the engine, no separate
path."* `TONE_TO_STEP` below is that table and there is no other. TC-5's negative
falls out of it: a tone the table does not contain is refused, so *"urgent-custom"*
cannot be smuggled in through an API caller.

**And the mapping decides the TEMPLATE CLASS, not merely the day number** —
BR-NOT-008, verbatim: *"Regulated ladder steps ALWAYS render the
disconnect-notice template class regardless of the tone picked in the reminder
modal."* So `firm` and `final` route to `generate_disconnect_notices`, which
renders the REGULATED class with its footer and its cut date, and only
`friendly` renders the dunning class. US-NOT-010 TC-4 states the consequence
from the other end: *"dunning never renders a cut date it doesn't have."* A
`{cut_date}` token is not even in the dunning catalog, so the mistake is a save
refusal rather than a blank line on a letter.

────────────────────────────────────────────────────────────────────────────
FOUR THINGS THAT ARE ARGUMENTS AND NOT READS, EACH FOR ITS OWN REASON
────────────────────────────────────────────────────────────────────────────
1. **The medical hold.** A clinical fact about a person, owned by customers,
   which publishes no read for it. `apps/payments/notices.py` made the same call
   and said why: *"inferring one here would put a clinical fact in the wrong
   module."* Generation REFUSES for a held account (US-NOT-009 TC-4: *"Generation
   refuses; NOTHING queued"*) and returns the skip row.
2. **The reconnect fee.** BR-BIL-007 via BR-CUS-039: it is DISPLAYED from the
   tenant's charge code and never defaulted. US-NOT-009 TC-5 makes a missing one
   a REFUSAL — *"Render fails with a config error naming the charge code — the
   fee is never invented or defaulted"* — and this module implements exactly
   that: if the resolved body uses `{reconnect_fee}` and no fee was passed, the
   whole generation refuses. It does not render `——` for this one token, because
   a disconnection notice that names no fee misstates what the customer must pay
   to be reconnected.
3. **The balance, the pay-by date, the cut date.** Billing's and payments'
   figures. Money arrives as `Decimal` and is refused as `float` by the renderer
   (CLAUDE.md rule 2) — an unguarded float renders `247.3` where a document must
   read `247.30`.
4. **The account's category, and its language.** The category is
   customers-owned; see `template_service`'s docstring. Passing it is how a
   commercial account gets the commercial variant. The caller passes the
   UTILITY's default language as the fallback; the account's own preferred
   language is asked first wherever the utility published the notice in it
   (PO option B, 2026-10-29, superseding `OQ-CUS-12619` (a) for messages —
   `BR-NOT-006` as amended that day).

The ONE thing that IS read here is the tenant's ladder configuration
(`tenancy_seam.collections_config`), because BR-REP-016 makes the day numbers
tenant config and US-NOT-010 TC-3 asserts a change flows through — and it
REFUSES rather than falling back to the 7/14/30 seeds.

────────────────────────────────────────────────────────────────────────────
CERTIFIED MAIL ON THE FINAL TIER (BR-CUS-039, A19 rule 3)
────────────────────────────────────────────────────────────────────────────
US-NOT-009 TC-2: *"Certified-mail forced ON (server-side even if forged off)."*
TC-3: *"a notice request with SMS-only is rejected."* Both are enforced here and
not on a screen, because the screen is not the enforcement (BR-SHL-025).

⚠ `{certified_no}` — the certified-mail NUMBER — comes from the provider
response at dispatch (field map §3, r10 #8). **No provider exists on any channel
(PO ruling 2026-08-15: delivery is out of this release), so no certified number
is ever produced**, and the token renders as a NAMED ABSENCE rather than a
fabricated tracking number. The letter is generated and the number is not
invented. REPORTED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from apps.notifications import models, rendering, services, template_service, tenancy_seam
from core import audit, errors
from core import tenancy as core_tenancy

#: A19 §2's three tiers, spelled EXACTLY as `apps/payments/collections_models.py`
#: spells them. One vocabulary across the boundary or the two modules describe
#: different ladders — and payments is the module that stores the tier a customer
#: has reached, so its spelling governs.
TIER_FIRST_10_DAY = "first_10_day"
TIER_SECOND_5_DAY = "second_5_day"
TIER_FINAL_48_HOUR = "final_48_hour"
DISCONNECT_TIERS = (TIER_FIRST_10_DAY, TIER_SECOND_5_DAY, TIER_FINAL_48_HOUR)

#: BR-PAY-035's tones. THREE, and no fourth: *"free-text tones do not exist"*.
TONE_FRIENDLY = "friendly"
TONE_FIRM = "firm"
TONE_FINAL = "final"

#: The ONE mapping (BR-PAY-035 + BR-NOT-008). `None` = the due+3 reminder step,
#: which is NOT a disconnect tier and renders the dunning class; a tier value
#: routes to the regulated disconnect class whatever the modal called it.
TONE_TO_STEP: dict[str, str | None] = {
    TONE_FRIENDLY: None,
    TONE_FIRM: TIER_FIRST_10_DAY,
    TONE_FINAL: TIER_FINAL_48_HOUR,
}

#: The template classes this service renders. Both are catalogued from signed
#: A19 tokens (`apps/notifications/catalogs.py`), which is why these two stories
#: are buildable while the email and SMS classes wait on OQ-206.
#:
#: ⚠ `CLASS_DISCONNECT` IS THE SUPERSEDED SINGLE CLASS AND IS NO LONGER RESOLVED
#: BY THIS MODULE. See `TIER_TO_CLASS` below. It is retained because older queue
#: rows and audit rows name it, and `catalogs.SUPERSEDED_CLASSES` explains it.
CLASS_DISCONNECT = "disconnect_notice"
CLASS_DUNNING = "dunning"

#: **BR-NOT-014's LADDER, IN CODE — DEF-193's OPEN REMAINDER, CLOSED 2026-08-17.**
#: ⚠ (DEF-193, not DEF-190. Nine places in this repo cite DEF-190 for this and
#: DEF-190 is an unrelated i18n defect in tenancy — DEF-230.)
#:
#: The rule has been CONFIRMED since 2026-08-16 (*"the registry holds a separate
#: template per tier and the ladder selects by tier, never by seniority of
#: wording"*) and for one day the code did not do it: `generate_disconnect_notice`
#: resolved the single legacy class at EVERY tier, so tier 1 and tier 3 would
#: have rendered the same slot. It was invisible because the legacy class has no
#: body — generation refused for want of one, so no customer could receive the
#: wrong letter and every test passed over the gap. **CR-007 published bodies for
#: all three tiers, which is exactly the day that stopped being safe**, and the
#: rewiring lands in the same change as the bodies rather than after them.
#:
#: Written as an explicit map, not a f-string on the tier name: a name-derived
#: class would silently invent `disconnect_notice_<anything>` for a tier
#: somebody added, and the failure would be a template that does not resolve at
#: the moment a utility is trying to send a legal notice.
TIER_TO_CLASS: dict[str, str] = {
    TIER_FIRST_10_DAY: "disconnect_notice_10_day",
    TIER_SECOND_5_DAY: "disconnect_notice_5_day",
    TIER_FINAL_48_HOUR: "disconnect_notice_48_hour",
}

#: A19 §2's own token. If the resolved body uses it and no fee was supplied,
#: generation REFUSES (US-NOT-009 TC-5) instead of rendering a named absence.
TOKEN_RECONNECT_FEE = "reconnect_fee"

#: Skip reasons, spelled as `apps/payments/notices.py` spells them so a
#: `notice_history` row written from either side groups the same on S34.
SKIP_MEDICAL_HOLD = "medical_hold"

#: Problem codes. CODES, because the dispatch home groups on them.
NOTICE_CERTIFIED_NUMBER_UNAVAILABLE = "certified_number_unavailable"
NOTICE_TEMPLATE_UNRESOLVED = "notice_template_unresolved"

AUDIT_ACTION = "notice.generated"
AUDIT_ENTITY = "outbound_message"


class NoticeRefused(Exception):
    """This notice cannot be generated, and here is why — in a clerk's words.

    Not a `core.errors` catalog exception, for the reason `QueueWriteRefused`
    gives: generation runs over bulk selections of hundreds of accounts where
    the right handling is to record the break and carry on (BR-BIL-055's shape).
    """


@dataclass(frozen=True)
class HistoryAppend:
    """One `notice_history` row this generation OWES — for payments to write.

    J4 step 2's contract: *"notice_history appended; medical-hold skipped;
    certified mail on final tier"*, and 04-flows.md §3: *"every send AND skip →
    notice_history append"*. This module cannot write the table (B1) so it hands
    the row back as data. The field names match
    `apps.payments.notices.record_notice`'s parameters exactly, so a caller
    forwards it without translating — a translation layer between two modules'
    vocabularies is where a skip reason quietly becomes a different one.
    """

    account_id: Any
    notice_type: str
    outcome: str
    tier: str | None = None
    channel: str | None = None
    skip_reason: str | None = None
    outbound_message_id: Any = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedNotice:
    """What ONE generation produced: the artifact, the rows, and the gaps."""

    account_id: Any
    template_code: str
    tier: str | None
    tone: str | None
    #: The rendered document. Present even when the queue write was partial —
    #: a notice that rendered and could not be queued is a different failure
    #: from one that never rendered, and a dashboard must be able to tell them
    #: apart.
    artifact: rendering.RenderedArtifact | None = None
    queued_message_ids: tuple[str, ...] = ()
    certified_mail: bool = False
    history_appends: tuple[HistoryAppend, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def sent(self) -> bool:
        """Deliberately ALWAYS False, and stated as a value rather than left to
        be inferred (hard-won law 1). Generation queues; the dispatcher sends;
        and on this deployment the dispatcher sends nothing at all because no
        provider adapter exists on any channel (PO ruling 2026-08-15). A caller
        can ASSERT that rather than take this docstring's word for it."""
        return False


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def step_for_tone(tone: str) -> str | None:
    """BR-PAY-035's mapping, and the ONLY door to it (US-NOT-010 TC-2/TC-5).

    Returns the disconnect TIER a tone escalates to, or None for the due+3
    reminder. A tone outside the three is refused rather than defaulted: a
    default would let an API caller invent a tone and receive whichever letter
    the default happened to name.
    """
    if tone not in TONE_TO_STEP:
        raise NoticeRefused(
            f"{tone!r} is not a tone. BR-PAY-035 fixes three — "
            f"{', '.join(TONE_TO_STEP)} — and states that *'free-text tones do not "
            "exist'*: the tone is not a label on a letter, it selects WHICH LETTER, and "
            "'firm' and 'final' select the regulated disconnect notice (BR-NOT-008). A "
            "tone nobody ratified would either render nothing or render the wrong class "
            "to a customer facing disconnection."
        )
    return TONE_TO_STEP[tone]


def stage_days() -> tuple[int, ...]:
    """BR-REP-016's dunning stage day numbers, FROM TENANT CONFIG.

    US-NOT-007 TC-3 and US-NOT-010 TC-3 are the same assertion: *"Tenant cadence
    7/14/30 → 10/20/35 → stage banners re-render from config; no constant
    anywhere."* The seeds live in `apps.tenancy.settings_families.COLLECTIONS`
    and are read through the seam, which REFUSES rather than falling back — see
    `tenancy_seam.CollectionsConfigUnavailable`.

    The day list is assembled from the S70 keys that exist: `reminder_days_after
    _due` (the due+3 stage) followed by `notice_tier_days` (10, 5 …). A19 r8's
    dunning row describes stages 1/2/3 and BR-REP-016 seeds them 7/14/30, which
    are the CADENCE seeds rather than the LADDER seeds — 04-flows.md §3 keeps
    both lists and says *"day numbers: cadence seeds 7/14/30 + ladder seeds
    due+3/10/5/48h — always tenant config, never constants"*. The ladder keys
    are the ones S70 stores today, so those are what render, and the fact that
    the cadence list has no separate storage is REPORTED here rather than
    papered over with a constant.
    """
    config = tenancy_seam.collections_config()
    days: list[int] = []
    reminder = config.get("reminder_days_after_due")
    if reminder is not None:
        days.append(int(reminder))
    for tier_day in config.get("notice_tier_days") or ():
        days.append(int(tier_day))
    if not days:
        raise tenancy_seam.CollectionsConfigUnavailable(
            "this tenant's collections settings carry no ladder intervals, so a dunning "
            "letter has no day number to print. BR-REP-016's 7/14/30 are SEEDS of that "
            "setting and are not a fallback: a reminder that prints the wrong day tells a "
            "customer the wrong date to pay by."
        )
    return tuple(days)


def _resolved_or_refuse(
    *,
    code: str,
    category: str | None,
    language: str | None,
    on_date: date | None,
    account_id: Any = None,
) -> template_service.ResolvedTemplate:
    """`language` is the utility's default and the FALLBACK; the account's own
    language is asked first where the utility published this class in it (PO
    option B, 2026-10-29 — `message_language.language_for`). The pin this
    returns is handed to `queue_document` already resolved, so this is the one
    place a notice's language is chosen."""
    from apps.notifications import message_language

    asked = message_language.language_for(
        code,
        stated=message_language.account_language(account_id),
        utility=language,
        category=category,
        on_date=on_date,
    )
    try:
        return template_service.resolve(
            code=code, category=category, language=asked, on_date=on_date
        )
    except template_service.TemplateRefused as unresolved:
        raise NoticeRefused(
            f"no published {code!r} template resolves, so this notice cannot be generated: "
            f"{unresolved} Nothing is sent and nothing is invented — the notice is REFUSED "
            "rather than queued against a template that does not exist, because a queued "
            "row that can never render is a customer who is never told."
        ) from unresolved


def _render(
    resolved: template_service.ResolvedTemplate, context: dict[str, Any]
) -> rendering.RenderedArtifact:
    pinned = template_service.load_pinned(
        template_id=resolved.template_id, version=resolved.version
    )
    return rendering.render(
        template_code=pinned.code,
        template_version=pinned.version,
        body=pinned.body,
        context=context,
        subject=pinned.subject,
        language=resolved.language,
    )


def generate_disconnect_notice(
    *,
    account_id: Any,
    tier: str,
    balance: Decimal,
    cut_date: date,
    on_date: date,
    actor: Any,
    pay_by_date: date | None = None,
    reconnect_fee: Decimal | None = None,
    state_puc_ref: str | None = None,
    channels: tuple[str, ...] = (models.CHANNEL_PRINT,),
    medical_hold: bool = False,
    category: str | None = None,
    language: str | None = None,
    extra_context: dict[str, Any] | None = None,
) -> GeneratedNotice:
    """Render and queue ONE disconnect notice at ONE tier (US-NOT-009).

    Enforces, in this order and all server-side:

      * **Medical hold → REFUSE** (TC-4): nothing rendered, nothing queued, and
        a SKIP row returned for `notice_history`. The flag is an argument — see
        the module docstring.
      * **The final tier forces certified mail** (TC-2, BR-CUS-039), server-side
        even if a caller forged it off, and **SMS never stands alone** (TC-3,
        A19 rule 3) — the letter is the legal instrument.
      * **A `{reconnect_fee}` in the body with no fee supplied → REFUSE** (TC-5,
        BR-BIL-007): named as a config error against the charge code, never
        defaulted to zero and never rendered as an absence.

    Output is queue rows (BR-NOT-005). `result.sent` is False, always.
    """
    _tenant_id()
    if tier not in DISCONNECT_TIERS:
        raise NoticeRefused(
            f"{tier!r} is not a disconnect tier. A19 §2 defines three — "
            f"{', '.join(DISCONNECT_TIERS)} — and the spelling matches payments' own, "
            "because payments stores the tier an account has reached and two spellings "
            "would be two ladders."
        )
    if medical_hold:
        # US-NOT-009 TC-4, verbatim: *"Generation refuses; NOTHING queued;
        # notice_history records the SKIP with reason medical_hold."*
        return GeneratedNotice(
            account_id=account_id,
            # The tier's own class, so a SKIP row names the letter that would
            # have gone out rather than the superseded single class (BR-NOT-014).
            template_code=TIER_TO_CLASS[tier],
            tier=tier,
            tone=None,
            skipped=True,
            skip_reason=SKIP_MEDICAL_HOLD,
            history_appends=(
                HistoryAppend(
                    account_id=account_id,
                    notice_type="disconnect",
                    outcome="skipped",
                    tier=tier,
                    skip_reason=SKIP_MEDICAL_HOLD,
                    detail={"cut_date": cut_date.isoformat()},
                ),
            ),
        )

    certified = tier == TIER_FINAL_48_HOUR
    if certified and models.CHANNEL_PRINT not in channels:
        # TC-2 + TC-3 in one refusal: the final tier is certified MAIL, so the
        # print row is not optional, and an SMS-only request is not a notice.
        raise NoticeRefused(
            "the 48-hour final notice requires certified mail, so the print channel "
            "cannot be omitted and SMS never stands alone (BR-CUS-039, A19 rule 3). The "
            "certified letter is the legal instrument; a text message supplements it. "
            "Forced server-side because the screen is not the enforcement."
        )

    # BR-NOT-014 — the LADDER SELECTS BY TIER. One class per stage, so a 10-day
    # warning cannot be rendered from the 48-hour slot or the reverse (DEF-193).
    tier_class = TIER_TO_CLASS[tier]
    resolved = _resolved_or_refuse(
        code=tier_class,
        category=category,
        language=language,
        on_date=on_date,
        account_id=account_id,
    )
    pinned = template_service.load_pinned(
        template_id=resolved.template_id, version=resolved.version
    )
    if TOKEN_RECONNECT_FEE in rendering.tokens_in(pinned.body) and reconnect_fee is None:
        # US-NOT-009 TC-5, verbatim: *"Render fails with a config error naming
        # the charge code — the fee is never invented or defaulted."*
        raise NoticeRefused(
            "this disconnect notice prints a {reconnect_fee} and no reconnect fee was "
            "supplied. The figure comes from the tenant's RECONN charge code (BR-BIL-007 "
            "via BR-CUS-039) and is DISPLAY-ONLY here: it is never defaulted to zero and "
            "never rendered as a dash, because a notice that misstates what a customer "
            "must pay to be reconnected is worse than one that has not gone out. Configure "
            "the reconnect charge code, then generate."
        )

    context: dict[str, Any] = {
        "balance": balance,
        "cut_date": cut_date,
        "pay_by_date": pay_by_date,
        "reconnect_fee": reconnect_fee,
        "state_puc_ref": state_puc_ref,
        **(extra_context or {}),
    }
    artifact = _render(resolved, context)

    problems: list[dict[str, Any]] = []
    if certified and "certified_no" in rendering.tokens_in(pinned.body):
        problems.append(
            {
                "code": NOTICE_CERTIFIED_NUMBER_UNAVAILABLE,
                "br_ref": "BR-CUS-039",
                "detail": "the certified-mail NUMBER arrives on the provider response at "
                "dispatch (field map §3, r10 #8) and no provider adapter exists on any "
                "channel — delivery is out of this release by PO ruling (2026-08-15). The "
                "token renders as a named absence; a tracking number is never fabricated.",
            }
        )

    write = services.queue_document(
        source_type="notice",
        source_id=account_id,
        channels=tuple(channels),
        template=services.TemplatePin(
            code=tier_class,
            template_id=resolved.template_id,
            version=resolved.version,
            language=resolved.language,
        ),
        account_id=account_id,
        actor=actor,
        category=category,
        language=language,
        on_date=on_date,
        # ⚠ `DEF-NOT-4449` — **THE SAME CONTEXT THIS FUNCTION JUST RENDERED
        # WITH, STAMPED ON THE ROW.** Until 2026-09-07 it was built, handed to
        # `_render` four lines up, and then DROPPED: the artifact returned to
        # the caller carried the balance and the cut date, and the queue row a
        # customer's letter is actually rendered from at dispatch carried
        # nothing, so the same notice read `pay {balance} by {pay_by_date}` in
        # one place and `pay —— by ——` in the other. `render_for_dispatch`
        # merges `outbound_messages.render_context` under its explicit
        # argument, which is what BR-NOT-012 means by *"the notification's own
        # stored render context"* — this is the caller supplying it.
        render_context=context,
    )
    problems.extend(write.problems)

    audit.money_action(
        actor,
        AUDIT_ACTION,
        AUDIT_ENTITY,
        None,
        after={
            "template_code": tier_class,
            "template_version": resolved.version,
            "tier": tier,
            "certified_mail": certified,
            "channels": list(channels),
            "queued": len(write.messages),
            "cut_date": cut_date.isoformat(),
            # BR-AUD-006: no PII. The account id is an identifier, not a name.
            "account_id": str(account_id),
        },
    )

    return GeneratedNotice(
        account_id=account_id,
        template_code=tier_class,
        tier=tier,
        tone=None,
        artifact=artifact,
        queued_message_ids=tuple(message.id for message in write.messages),
        certified_mail=certified,
        history_appends=tuple(
            HistoryAppend(
                account_id=account_id,
                notice_type="disconnect",
                outcome="sent",
                tier=tier,
                channel=channel,
                detail={
                    "cut_date": cut_date.isoformat(),
                    "certified_mail": certified,
                    "template_version": resolved.version,
                    # BR-BIL-007: shown, never applied, and reported ABSENT
                    # rather than printed as zero.
                    "reconnect_fee": str(reconnect_fee) if reconnect_fee is not None else None,
                },
            )
            for channel in channels
        ),
        problems=tuple(problems),
    )


def generate_reminder(
    *,
    account_id: Any,
    balance: Decimal,
    on_date: date,
    actor: Any,
    tone: str = TONE_FRIENDLY,
    days_late: int | None = None,
    late_fee: Decimal | None = None,
    channels: tuple[str, ...] = (models.CHANNEL_PRINT,),
    medical_hold: bool = False,
    category: str | None = None,
    language: str | None = None,
    cut_date: date | None = None,
    extra_context: dict[str, Any] | None = None,
    **disconnect_kwargs: Any,
) -> GeneratedNotice:
    """Render and queue ONE reminder — or escalate, per BR-NOT-008 (US-NOT-010).

    The tone is resolved through `TONE_TO_STEP` and NOWHERE ELSE, so the S35
    modal and the sequence engine take the same path (TC-2). A `firm` or `final`
    tone is a REGULATED step and routes to `generate_disconnect_notice` — that
    is BR-NOT-008 in code: *"regulated ladder steps ALWAYS render the
    disconnect-notice template class regardless of the tone picked in the
    reminder modal."* It needs a cut date to do so, and refuses without one
    rather than rendering a disconnection letter with a blank date on it.

    The friendly tone renders the DUNNING class: a courtesy reminder, with no
    regulatory footer (A19 rule 2) and no cut date it does not have (TC-4).
    `{stage_day}` renders from the tenant's ladder config (BR-REP-016) and the
    seam refuses rather than printing the 7/14/30 seeds.
    """
    _tenant_id()
    step = step_for_tone(tone)
    if step is not None:
        if cut_date is None:
            raise NoticeRefused(
                f"tone {tone!r} maps to the {step!r} step, which is a REGULATED ladder "
                "step: BR-NOT-008 says it *'ALWAYS renders the disconnect-notice template "
                "class regardless of the tone picked in the reminder modal'*, and a "
                "disconnect notice states the date service is cut off. No cut date was "
                "supplied, so nothing is rendered. A reminder cannot stand in for it — "
                "US-NOT-010 TC-4: dunning never renders a cut date it doesn't have."
            )
        return generate_disconnect_notice(
            account_id=account_id,
            tier=step,
            balance=balance,
            cut_date=cut_date,
            on_date=on_date,
            actor=actor,
            channels=channels,
            medical_hold=medical_hold,
            category=category,
            language=language,
            extra_context=extra_context,
            **disconnect_kwargs,
        )

    if medical_hold:
        return GeneratedNotice(
            account_id=account_id,
            template_code=CLASS_DUNNING,
            tier=None,
            tone=tone,
            skipped=True,
            skip_reason=SKIP_MEDICAL_HOLD,
            history_appends=(
                HistoryAppend(
                    account_id=account_id,
                    notice_type="reminder",
                    outcome="skipped",
                    skip_reason=SKIP_MEDICAL_HOLD,
                    detail={"tone": tone},
                ),
            ),
        )

    days = stage_days()
    resolved = _resolved_or_refuse(
        code=CLASS_DUNNING,
        category=category,
        language=language,
        on_date=on_date,
        account_id=account_id,
    )
    context: dict[str, Any] = {
        "balance": balance,
        # BR-REP-016 — the FIRST stage's day number, from config. Never 7.
        "stage_day": days[0],
        "days_late": days_late,
        "late_fee": late_fee,
        **(extra_context or {}),
    }
    artifact = _render(resolved, context)

    write = services.queue_document(
        source_type="notice",
        source_id=account_id,
        channels=tuple(channels),
        template=services.TemplatePin(
            code=CLASS_DUNNING,
            template_id=resolved.template_id,
            version=resolved.version,
            language=resolved.language,
        ),
        account_id=account_id,
        actor=actor,
        category=category,
        language=language,
        on_date=on_date,
        # `DEF-NOT-4449` — the context this reminder was rendered from, stamped
        # on the row so the dispatch-time render says the same thing. See the
        # disconnect branch above for the whole argument.
        render_context=context,
    )

    audit.money_action(
        actor,
        AUDIT_ACTION,
        AUDIT_ENTITY,
        None,
        after={
            "template_code": CLASS_DUNNING,
            "template_version": resolved.version,
            "tone": tone,
            "stage_day": days[0],
            "channels": list(channels),
            "queued": len(write.messages),
            "account_id": str(account_id),
        },
    )

    return GeneratedNotice(
        account_id=account_id,
        template_code=CLASS_DUNNING,
        tier=None,
        tone=tone,
        artifact=artifact,
        queued_message_ids=tuple(message.id for message in write.messages),
        history_appends=tuple(
            HistoryAppend(
                account_id=account_id,
                notice_type="reminder",
                outcome="sent",
                channel=channel,
                detail={"tone": tone, "stage_day": days[0], "template_version": resolved.version},
            )
            for channel in channels
        ),
        problems=tuple(write.problems),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-009@4b7d13e (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-03-notices-contracts.md — US-NOT-009 §1/§3/§5 + US-NOT-010 §1/§3/§5 — · 10-notifications/02-business-rules.md — BR-NOT-005/008 — · 10-notifications/04-flows.md §3 (the notice ladder, rendering side) · 08-qa/01-e2e/journeys/J4-collections.md, so a later change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — notice generation)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the trigger surfaces S22/S34/S35 are customers' and payments' and are NOT this lane's; this service is the interface they call) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_009_010_notice_generation.py ·
#         four guards proved RED before green (hard-won law 7) — the medical-hold
#         refusal, the certified-mail forcing, the missing-reconnect-fee refusal
#         and the tone→class routing; transcripts in the lane report
# exceptions: (1) THIS MODULE DOES NOT WRITE `notice_history` (r12 #7 —
#         payments-owned; `apps/payments/notices.record_notice` is documented as
#         its ONLY writer). B1 forbids the cross-module write, so every result
#         carries `history_appends` as DATA for the owning caller to record. ⚠ A
#         caller that ignores them produces a notice with no history row and
#         nothing here can stop it — REPORTED rather than fixed by violating the
#         boundary.
#         (2) THE MEDICAL HOLD, THE RECONNECT FEE, THE BALANCE AND THE ACCOUNT'S
#         CATEGORY/LANGUAGE ARE ALL ARGUMENTS. Each is another module's fact and
#         none has a published read; `apps/payments/notices.py` made the same
#         call for the hold and stated the same reason.
#         (3) NO CERTIFIED-MAIL NUMBER IS EVER PRODUCED. It arrives on a provider
#         response at dispatch and no provider exists on any channel (PO ruling
#         2026-08-15 — delivery is out of this release). The token renders as a
#         named absence and a problem row says so; a tracking number is never
#         fabricated.
#         (4) `stage_days()` READS THE **LADDER** KEYS (`reminder_days_after_due`,
#         `notice_tier_days`) because those are what S70 stores. 04-flows.md §3
#         names a SECOND list — the cadence seeds 7/14/30 behind A19 r8's dunning
#         stages 1/2/3 — and no settings family holds it. The ladder days render
#         and the missing cadence storage is REPORTED here rather than replaced
#         by the constants BR-REP-016 explicitly calls seeds.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
