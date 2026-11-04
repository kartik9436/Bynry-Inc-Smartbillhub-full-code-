# ── Trace ──────────────────────────────────────────────
# Story:    CR-007 (the disconnect notices — the platform writes the defaults,
#           PO ruling 2026-08-17)   Screens: S8 → Notifications · SET-10
# Rules:    BR-NOT-015 (the rights footer ships as a PLATFORM DEFAULT and a
#           utility's System Admin may override it; the default must be VISIBLY
#           MARKED as a default and the override is System-Admin-only and
#           AUDITED) · BR-NOT-014 (three disconnect slots, one per tier) ·
#           BR-TEN-016 (a settings edit is audited, before→after) ·
#           BR-IDN-009 (server-enforced role gating is THE gating) ·
#           CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 7 (audited)
# Tests:    06-backend/tests/test_cr_007_disconnect_rights_footer.py
# Impacts:  apps/notifications/rendering.render (expands `{rights_footer}`) ·
#           apps/notifications/seed_templates (the three tier bodies carry the
#           token) · apps/notifications/settings_api (the S8 card) ·
#           10-scripts/gates/human_owned.txt (G7)
# ───────────────────────────────────────────────────────
"""The five rights clauses a disconnection notice carries — platform defaults.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — **this file holds the sentences that tell a
customer how to keep their water on.** It is the same authority
`seed_templates.py` is guarded for and it is one step more consequential, because
these five paragraphs are the part of a regulated letter that has legal weight.
AI-authored 2026-08-17 under the PO ruling below and the standing ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  A DEFAULT IS A STARTING POINT. IT IS NOT LEGAL ADVICE, AND NOTHING      ║
║  HERE — IN THE UI, IN THIS DOCSTRING, OR IN A CLAUSE — MAY IMPLY THAT    ║
║  THIS PLATFORM WARRANTS IT AGAINST ANY REGULATOR.                        ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
WHY THESE SENTENCES EXIST NOW, WHEN A LANE REFUSED TO WRITE THEM YESTERDAY
────────────────────────────────────────────────────────────────────────────
The template-authoring lane declined to write this footer on 2026-08-17, citing
BR-NOT-015's own words — *"the default's SENTENCES are NOT settled by this rule
and must not be invented"* — and that refusal was CORRECT at the time: nobody had
ruled who writes them. The consequence was measured and reported: all three
disconnect tiers were built, EMPTY, refusing every save by name, so **no
disconnection notice could be produced on any tenant.**

The Product Owner then ruled that the platform writes them. Verbatim,
2026-08-17, recorded in 12-governance/11-change-requests.md §"CR-007 · The
disconnect notices — the platform writes the defaults":

  > *"we will take this option; we provide default option for all 5 you ahve
  > mentioned; if Utility wants to over ride it let them do it; I can also give
  > tick boxes if required to add 5"*

and, when the consequence was restated:

  > *"you build default langauge and let Utility user change it as they want"*

**BR-NOT-015 is therefore SATISFIED rather than broken.** The sentences are no
longer invented by a lane; they are authored to a PO instruction and are the
PO's to approve. The rule's two non-optional halves are what this module
implements: **(a)** the default is VISIBLY MARKED as a default — `is_default` is
served per clause and `PLATFORM_DEFAULT_NOTICE` is the sentence the screen shows
— and **(b)** the override is a System-Admin-only, AUDITED write.

────────────────────────────────────────────────────────────────────────────
THE TICK BOXES, AND WHY THEY ARE NOT "DELETE THE TEXT AND HOPE"
────────────────────────────────────────────────────────────────────────────
The PO offered them (*"I can also give tick boxes if required to add 5"*) and
CR-007 takes them up for a concrete reason: **a utility in a state with no
weather rule must be able to turn that clause OFF.** Blanking the text would
leave a heading with nothing under it and would be indistinguishable, on the next
reader's screen, from a clause somebody had not got round to writing yet.

So a clause has two independent tenant facts — `enabled` and `text` — and the
platform default for both is held HERE and nowhere else.

────────────────────────────────────────────────────────────────────────────
WHERE THE TENANT'S CHOICES LIVE, AND WHY THAT IS NOT A SECOND MECHANISM
────────────────────────────────────────────────────────────────────────────
`notification_settings.disconnect_rights_clauses`, a JSON map on the row this
module's own tenant already has (BR-TEN-031: the settings FRAMEWORK is tenancy's,
the settings CONTENT is the owning module's — and this is notifications content).

**Only DEVIATIONS are stored.** An untouched tenant holds `{}` and therefore
holds every platform default, which is what makes *"is this the platform's
wording or ours"* answerable by looking: a clause code absent from the map IS the
default. A table pre-seeded with five rows per tenant could not answer it without
a second column carrying the same claim, free to drift (hard-won law 1).

**No new override mechanism is invented.** BR-NOT-015 names the properties — System
Admin only, audited — and `update_clauses` below is `dispatch_config`'s own
pattern applied to the same row: `@require_role(SYSTEM_ADMIN)`, one audit row per
save carrying before→after of only what moved.

────────────────────────────────────────────────────────────────────────────
THE PALETTE A CLAUSE MAY USE IS THE INTERSECTION OF THE THREE TIERS
────────────────────────────────────────────────────────────────────────────
One footer serves all three of BR-NOT-014's slots, and each slot has its OWN
whitelist on purpose — a 10-day warning that could carry `{48h}` and
`{certified_no}` is a 10-day warning that can be written as a 48-hour certified
letter. So a clause may only use a token **every** tier allows, which is computed
below rather than typed: `ALLOWED_TOKENS` is the set intersection, so narrowing a
tier's palette narrows this automatically instead of leaving a stale copy behind.

⚠ **`{utility_logo}` IS EXCLUDED EXPLICITLY** even though all three tiers offer
it (DEF-195): the render context supplies no value, so a clause naming it would
print `——` on a customer's letter — a named absence in the paragraph that tells
them their rights.

────────────────────────────────────────────────────────────────────────────
WHAT IS DELIBERATELY NOT STATED IN ANY CLAUSE
────────────────────────────────────────────────────────────────────────────
The same rule the authoring of the other twenty-six bodies ran under: **no
figure, fee, deadline, notice period or right that is not already ruled
somewhere in this repo.**

  · The **60-day** medical-hold renewal is the PO's own figure, written in the
    ruling and in BR-NOT-015's clause list (*"physician-certified, 60-day
    renewable"*).
  · **32°F and 100°F** are the PO's own figures, from the same list.
  · **No dollar amount appears anywhere here.** A reconnect fee is `{reconnect_fee}`
    on the tier that carries it (BR-CUS-039: a tenant charge code, never a
    constant), and the 5-day tier's signed sentence is where it belongs.
  · **No commission phone number, address or website is written.** The regulator
    differs per tenant and `{state_puc_ref}` is the token that holds it — which
    is BR-NOT-015's own *"as they already supply their commission reference"*.
    ⚠ **WHERE a tenant supplies it is a REAL GAP and it is filed, not papered
    over: OQ-263.** Nothing in the product stores a commission reference today;
    `notices.generate_disconnect_notice` takes it as a caller argument and no
    screen sets it, so an unfilled one renders the named absence `——`.
  · **No clause promises an outcome.** They state a right, a mechanism and a
    timeframe: *"ask us whether"*, never *"we will"*.

────────────────────────────────────────────────────────────────────────────
ENGLISH ONLY
────────────────────────────────────────────────────────────────────────────
As the template-authoring lane established and recorded: these are tenant-EDITABLE
content, not UI strings, and BR-NOT-006's language variants are the door for a
tenant that wants another language. A machine-translated statement of legal
rights is worse than an English default a utility replaces in its own words.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.notifications import catalogs, models
from core import audit, errors
from core import tenancy as core_tenancy
from core.permissions import SYSTEM_ADMIN, require_role

#: The merge token the three tier bodies carry. It is expanded by
#: `rendering.render` in a PRE-PASS, before the ordinary token substitution, so
#: a clause's own `{support_phone}` still merges — see `expand` below.
FOOTER_TOKEN = "rights_footer"

#: Hard rule 7 · the same `entity.action` grammar `dispatch_config` writes, and
#: the same ENTITY, because this is the same row. A reviewer reading a tenant's
#: notification-settings history sees the quiet-hours change and the rights-footer
#: change in one query rather than two.
AUDIT_ACTION = "notification_settings.updated"
AUDIT_ENTITY = "notification_settings"

#: The column on `notification_settings`. Named once; the model, the service and
#: the audit diff all read it from here.
SETTINGS_FIELD = "disconnect_rights_clauses"

#: BR-NOT-015 (a): the default must be VISIBLY MARKED as a default. This is that
#: marking, served to the screen rather than written into a component, for the
#: reason every other ruling in this module is served — a screen that remembered
#: it could stop saying it.
#:
#: ⚠ IT IS ALSO THE ONE SENTENCE CR-007 FORBADE SOFTENING. Read it as three
#: separate statements, because each does different work: the platform WROTE
#: these words (so they are not the utility's regulator's), they are a STARTING
#: POINT (so they are not advice), and they must be REVIEWED before a notice goes
#: out (so the review is the utility's, not ours).
PLATFORM_DEFAULT_NOTICE = (
    "These five clauses are wording SMART360 Next provides as a starting point. They are "
    "not legal advice and they are not your regulator's words: disconnection rules differ "
    "by state and by utility. Review each clause against your own commission's "
    "requirements — and edit or switch off whatever does not match them — before any "
    "disconnection notice goes out. A clause you have not changed is shown as "
    '"platform default".'
)

#: The BADGE on an untouched clause — BR-NOT-015 (a) at a glance, beside the
#: clause itself, where `PLATFORM_DEFAULT_NOTICE` is the standing paragraph above
#: the card. Two lengths for two jobs: the badge marks a row, the notice states
#: the rule. Both are served, so neither can be dropped by a screen that decides
#: it has said it often enough.
PLATFORM_DEFAULT_LABEL = "Platform default — review against your own commission"

TENANT_WORDING_LABEL = "Your wording"

#: The sentence shown against a clause whose text this tenant has replaced. The
#: other half of BR-NOT-015 (a): a reader must be able to tell the two apart at a
#: glance, in both directions.
TENANT_WORDING_NOTICE = (
    "This clause has been replaced with your own wording. SMART360 Next's default is still "
    "available and restoring it is one click."
)


@dataclass(frozen=True)
class RightsClause:
    """One clause of the regulatory rights footer: its heading and its default.

    `code` is PLATFORM VOCABULARY and is never tenant-defined — the five clauses
    are named by BR-NOT-015 and by the PO's ruling, and a sixth invented by a
    tenant would be a paragraph of a regulated letter that no validation, no
    palette and no review had ever seen.
    """

    code: str
    #: The heading printed above the clause on the notice, and the tick box's
    #: label on S8. ONE string, so a screen and a letter cannot disagree.
    title: str
    default_text: str
    #: Why this clause is in the footer at all — shown as helper text beside the
    #: tick box, so a System Admin switching one off knows what they are removing.
    purpose: str


# ══════════════════════════════════════════════════════════════════════════
# THE FIVE DEFAULTS — AUTHORED 2026-08-17 UNDER THE PO RULING ABOVE
# ══════════════════════════════════════════════════════════════════════════
# Voice: short sentences, no jargon, a small utility's voice. Every clause states
# a right, a way to use it, and where to go next — and none of them promises what
# the answer will be.

_DISPUTE_RIGHTS = RightsClause(
    code="dispute_rights",
    title="If you think this bill is wrong",
    purpose=(
        "Tells the customer how to challenge the amount BEFORE the disconnection date, "
        "and that they may ask for service to be held while it is looked at."
    ),
    default_text=(
        "If you believe the amount on this notice is wrong, contact us before the date "
        "shown above — not after it. Call {support_phone} or write to {support_email}, "
        "quote account {account_no}, and tell us which charge you are questioning and "
        "why. Ask us at the same time whether service can be held while we look into it. "
        "You can ask us to check the meter reading, and you can ask for the readings and "
        "the rates the bill was worked out from."
    ),
)

_MEDICAL_HOLD = RightsClause(
    code="medical_hold",
    title="If someone at this address has a medical need",
    purpose=(
        "Tells the customer that a physician-certified medical hold exists, what it "
        "needs, and that it has to be renewed every 60 days to stay in place."
    ),
    default_text=(
        "If anyone living at {service_address} depends on utility service for a serious "
        "illness or for medical equipment, tell us straight away on {support_phone}. We "
        "will ask for a written certificate from a licensed physician naming the person "
        "and the condition. A medical hold is not permanent: the certificate has to be "
        "renewed every 60 days for the hold to continue. A hold delays disconnection — it "
        "does not cancel the amount owed, so talk to us about paying it over time."
    ),
)

_WEATHER_SUPPRESSION = RightsClause(
    code="weather_suppression",
    title="Weather",
    purpose=(
        "States the temperature limits on disconnection. Switch this clause OFF if your "
        "state sets no weather limit, or edit it if your state sets different figures."
    ),
    default_text=(
        "We do not disconnect service on a day when the forecast temperature for your "
        "service address is below 32°F or above 100°F."
    ),
)

_WEEKEND_HOLIDAY_SUPPRESSION = RightsClause(
    code="weekend_holiday_suppression",
    title="Weekends and holidays",
    purpose=(
        "States that disconnection does not happen on days when the customer cannot "
        "reach anyone to have service restored."
    ),
    default_text=(
        "We do not disconnect service on a weekend or on a public holiday. If you are "
        "disconnected and you pay, call {support_phone} — reconnection is arranged by "
        "talking to us, not by waiting."
    ),
)

_COMMISSION_COMPLAINT = RightsClause(
    code="commission_complaint",
    title="If you are not satisfied with our answer",
    purpose=(
        "Tells the customer who to go to ABOVE the utility. The reference itself is "
        "yours — it renders from the commission reference on the notice."
    ),
    default_text=(
        "Come to us first: call {support_phone} or write to {support_email}, and give us "
        "the chance to put it right. If we cannot settle it between us, you can take the "
        "complaint to the commission that regulates {utility_name}. Its reference is "
        "printed on this notice. Have account {account_no} and this notice with you when "
        "you contact them."
    ),
)

#: In the order they print, which is the order BR-NOT-015 and the PO's ruling
#: both list them: what you can do about the bill · who is protected · when we do
#: not disconnect · who is above us.
CLAUSES: tuple[RightsClause, ...] = (
    _DISPUTE_RIGHTS,
    _MEDICAL_HOLD,
    _WEATHER_SUPPRESSION,
    _WEEKEND_HOLIDAY_SUPPRESSION,
    _COMMISSION_COMPLAINT,
)

CLAUSE_CODES: tuple[str, ...] = tuple(clause.code for clause in CLAUSES)

#: Every clause ships ON. The PO's ruling is *"we provide default option for all
#: 5"* — a footer that arrived with clauses switched off would be a default
#: nobody had chosen, and the tick boxes exist so a utility can REMOVE one
#: deliberately rather than have to notice that it was never there.
DEFAULT_ENABLED = True

#: BR-NOT-014's three slots. Named here rather than derived from a code prefix:
#: a prefix match would silently pick up a fourth tier somebody added.
TIER_CLASSES: tuple[str, ...] = (
    "disconnect_notice_10_day",
    "disconnect_notice_5_day",
    "disconnect_notice_48_hour",
)


def allowed_tokens() -> frozenset[str]:
    """The tokens a clause may use: what EVERY tier's palette allows, minus the logo.

    Computed, never typed. One footer serves three classes whose whitelists differ
    on purpose (BR-NOT-014), so a clause may only name a token all three accept —
    otherwise the same footer would validate on the 48-hour letter and refuse on
    the 10-day warning, and the difference would only appear when somebody tried
    to save.

    `{utility_logo}` is removed explicitly: all three tiers offer it and the
    render context supplies no value (DEF-195), so a clause naming it would print
    a named absence in the middle of a statement of legal rights.
    """
    palettes = [
        catalog.tokens
        for code in TIER_CLASSES
        if (catalog := catalogs.catalog_for(code)) is not None
    ]
    if not palettes:  # pragma: no cover — TIER_CLASSES are catalogued; asserted in tests
        return frozenset()
    shared = frozenset.intersection(*palettes)
    return shared - {"utility_logo", FOOTER_TOKEN}


class RightsFooterRefused(Exception):
    """This footer edit cannot be saved, and here is why — in a clerk's words.

    Deliberately not a `core.errors` catalog exception, for `DispatchConfigRefused`'s
    reason: this service is reachable from a management command as well as from a
    request, and a catalog code carries an HTTP status.
    """


def validate_clause_text(clause_code: str, text: str) -> None:
    """Refuse a clause that names a token the three tiers do not all allow.

    The same gate `rendering.validate_body` applies to a body, applied one level
    down — because the footer is merged INTO a body after that body has already
    been validated, so without this a tenant could put `{meter_no}` on a
    disconnection notice through the side door.

    `rendering` is imported inside the function on purpose: `rendering` imports
    THIS module for the `{rights_footer}` pre-pass, and a module-level import
    here would be a cycle. The dependency is genuinely one-way at import time and
    two-way at call time.
    """
    from apps.notifications import rendering  # local: see docstring

    if not isinstance(text, str) or not text.strip():
        raise RightsFooterRefused(
            f"the {clause_code!r} clause cannot be saved empty. A clause with no text is "
            "a heading with nothing under it, which reads on the printed notice exactly "
            "like wording somebody has not finished. To remove a clause from the notice, "
            "switch it OFF — that is what the tick box is for."
        )
    permitted = allowed_tokens()
    unknown = sorted(set(rendering.tokens_in(text)) - permitted)
    if unknown:
        raise RightsFooterRefused(
            f"{', '.join('{' + name + '}' for name in unknown)} cannot be used in a "
            f"rights clause. One footer prints on all three disconnection notices — the "
            f"10-day warning, the 5-day final reminder and the 48-hour certified letter — "
            f"and each of those carries its own merge fields (BR-NOT-014). A clause may "
            f"only use a field ALL THREE have: "
            f"{', '.join('{' + name + '}' for name in sorted(permitted))}. "
            "{utility_logo} is excluded because nothing fills it, so it would print a "
            "blank in the middle of a statement of your customer's rights."
        )


@dataclass(frozen=True)
class EffectiveClause:
    """One clause as this tenant will actually print it.

    `is_default` is BR-NOT-015 (a) as a value rather than as a screen's guess: it
    is TRUE when this tenant has never replaced the wording, which is exactly
    "the platform wrote this sentence, not your regulator".
    """

    code: str
    title: str
    purpose: str
    text: str
    enabled: bool
    is_default: bool
    #: The platform's own wording, always — so a screen can offer "restore the
    #: default" without a second round trip, and so a reviewer comparing an
    #: override against what it replaced never has to leave the page.
    default_text: str


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _row() -> models.NotificationSettings:
    """This tenant's settings row, created with the ratified defaults if absent.

    Same `get_or_create` as `dispatch_config._row` and for the same reason: a
    tenant that has never opened S8 and a tenant that opened it and saved nothing
    must be one row and one behaviour.
    """
    row, _ = models.NotificationSettings.objects.get_or_create(tenant_id=_tenant_id())
    return row


def _stored() -> dict[str, Any]:
    """The tenant's DEVIATIONS from the platform defaults. `{}` means none."""
    raw = getattr(_row(), SETTINGS_FIELD, None)
    return raw if isinstance(raw, dict) else {}


def effective_clauses() -> tuple[EffectiveClause, ...]:
    """The five clauses as this tenant prints them, in printing order.

    Always five. A clause switched off is RETURNED with `enabled=False` rather
    than dropped, because the screen has to draw its tick box and because "we
    turned that one off" and "that clause does not exist" are different answers
    to a reviewer asking why a notice has no weather paragraph.
    """
    stored = _stored()
    rows: list[EffectiveClause] = []
    for clause in CLAUSES:
        override = stored.get(clause.code) or {}
        text = override.get("text")
        has_override = isinstance(text, str) and text.strip() != ""
        enabled = override.get("enabled")
        rows.append(
            EffectiveClause(
                code=clause.code,
                title=clause.title,
                purpose=clause.purpose,
                text=text if has_override else clause.default_text,
                enabled=bool(enabled) if isinstance(enabled, bool) else DEFAULT_ENABLED,
                is_default=not has_override,
                default_text=clause.default_text,
            )
        )
    return tuple(rows)


def assemble(clauses: tuple[EffectiveClause, ...]) -> str:
    """The clauses that are ON, as the block that replaces `{rights_footer}`.

    A clause that is OFF contributes NOTHING — no heading, no blank line, no
    "(removed)" marker. That is the whole point of the tick box: a utility in a
    state with no weather rule gets a notice that reads as though the clause was
    never there, rather than one with a visible hole in it.

    Every clause that is ON prints its heading. The heading is not decoration on
    a regulated letter: it is what lets a customer find the paragraph that
    applies to them without reading all five.
    """
    blocks = [f"{clause.title}\n{clause.text.strip()}" for clause in clauses if clause.enabled]
    return "\n\n".join(blocks)


def footer_text() -> str:
    """This tenant's assembled rights footer. Empty when every clause is off."""
    return assemble(effective_clauses())


def expand(body: str) -> str:
    """Replace `{rights_footer}` with this tenant's footer. A no-op without it.

    ⚠ **THIS IS A PRE-PASS, AND THE ORDER IS THE WHOLE DESIGN.** `rendering.render`
    substitutes tokens with a single `re.sub`, and a replacement string is
    inserted literally rather than re-scanned — so a footer merged in during that
    pass would print `{support_phone}` on the customer's letter as five literal
    characters and a brace. Expanding FIRST means the clause's own tokens are
    still there when the ordinary substitution runs, and they merge like any
    other.

    It runs AFTER `render_custom_fields`, also deliberately: a tenant's clause
    override must not be able to reach into `{{account.custom.…}}`, which is
    tenant-authored data resolved from a stamped snapshot. Platform vocabulary
    only, and `validate_clause_text` is what holds that line at save time.
    """
    if FOOTER_TOKEN not in body:
        return body
    return body.replace("{" + FOOTER_TOKEN + "}", footer_text())


def _clean_changes(changes: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Submitted edits → validated per-clause deviations, or the refusal."""
    unknown = sorted(set(changes) - set(CLAUSE_CODES))
    if unknown:
        raise RightsFooterRefused(
            f"{', '.join(unknown)} is not a rights clause. The footer has five, named by "
            f"BR-NOT-015 and by the ruling that authorised these defaults: "
            f"{', '.join(CLAUSE_CODES)}. A sixth clause would be a paragraph of a "
            "regulated letter that no validation and no review has ever seen — if you "
            "need one, the whole notice body is editable on Settings → Templates."
        )
    cleaned: dict[str, dict[str, Any]] = {}
    for code, raw in changes.items():
        if not isinstance(raw, dict):
            raise RightsFooterRefused(
                f"the {code!r} clause must be submitted as its own object with an "
                '"enabled" flag, a "text" string, or both.'
            )
        extra = sorted(set(raw) - {"enabled", "text"})
        if extra:
            raise RightsFooterRefused(
                f"{', '.join(extra)} is not something you can set on the {code!r} clause. "
                'A clause has two settings: "enabled" (the tick box) and "text" (your own '
                "wording, replacing the platform default)."
            )
        entry: dict[str, Any] = {}
        if "enabled" in raw:
            if not isinstance(raw["enabled"], bool):
                raise RightsFooterRefused(
                    f"the {code!r} clause is either on the notice or it is not — "
                    f"{raw['enabled']!r} is neither, so it is refused rather than read as "
                    "one of them."
                )
            entry["enabled"] = raw["enabled"]
        if "text" in raw:
            # `null` is RESTORE THE PLATFORM DEFAULT, and it is the only way back:
            # a tenant who has overridden a clause and wants ours again must be
            # able to say so without retyping a paragraph they would then own.
            if raw["text"] is None:
                entry["text"] = None
            else:
                validate_clause_text(code, raw["text"])
                entry["text"] = raw["text"].strip()
        cleaned[code] = entry
    return cleaned


def _audit_shape(entry: dict[str, Any] | None) -> dict[str, Any]:
    """One clause's stored state in a form the audit payload can carry.

    ⚠ THE TEXT IS RECORDED IN FULL, not as a length or a hash. BR-TEN-016 wants
    before→after, and the thing that changed here is the sentence a customer
    reads about their legal rights — a trail saying *"text changed, 412 → 380
    characters"* answers nothing anybody would ever ask it.
    """
    entry = entry or {}
    return {
        "enabled": entry.get("enabled", DEFAULT_ENABLED),
        "text": entry.get("text"),
        "is_platform_default": entry.get("text") is None,
    }


@require_role(SYSTEM_ADMIN, br_ref="BR-NOT-015")
def update_clauses(*, actor: Any, **changes: Any) -> tuple[EffectiveClause, ...]:
    """Save a rights-footer edit. **System-Admin-only, validated, audited, atomic.**

    That sentence is BR-NOT-015 (b) verbatim — *"the override is a System-Admin-only,
    AUDITED write — it is the text telling a customer their legal rights"* — and
    all three properties are enforced HERE, in the service, so they hold for an
    endpoint, a shell and any job that forgot to gate (BR-SHL-025, BR-IDN-009).

    Pass only the clauses being changed, each as `{"enabled": bool}`,
    `{"text": str}`, `{"text": None}` (restore ours) or both. A value that is
    already stored is not a change and does not appear in the audit payload.

    Raises `RightsFooterRefused` for something the tenant can fix and `AuthError`
    AUTH-002 for a caller who may not make the edit at all.
    """
    cleaned = _clean_changes(changes)
    if not cleaned:
        raise RightsFooterRefused(
            "no clause was named, so there is nothing to save. An empty save would write "
            "a trail row saying a System Admin changed the rights wording on a "
            "disconnection notice and leave no way to see that they did not."
        )

    with transaction.atomic():
        row = _row()
        stored = dict(getattr(row, SETTINGS_FIELD, None) or {})
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
        for code, entry in cleaned.items():
            current = dict(stored.get(code) or {})
            updated = dict(current)
            if "enabled" in entry:
                updated["enabled"] = entry["enabled"]
            if "text" in entry:
                if entry["text"] is None:
                    updated.pop("text", None)
                else:
                    updated["text"] = entry["text"]
            # ⚠ NORMALISE BEFORE COMPARING — a deviation equal to the default is
            # NOT a deviation. Ticking an already-ticked box stores
            # `{"enabled": true}`, which differs from `{}` as a dict and is the
            # same footer on the same letter; without this the trail would carry
            # a row saying a System Admin changed a customer's rights wording,
            # on the one trail where a reader cannot afford to read past noise.
            # It also keeps `is_default` honest: switching a clause off and on
            # again returns the row to "untouched" rather than leaving a marker
            # that means nothing.
            if updated.get("enabled") == DEFAULT_ENABLED:
                updated.pop("enabled", None)
            if updated == current:
                continue
            before[code] = _audit_shape(current)
            after[code] = _audit_shape(updated)
            # A clause back at every platform default carries no key at all —
            # `{}` and "absent" must not be two states, or `is_default` becomes a
            # question about which one this tenant happens to hold.
            if updated:
                stored[code] = updated
            else:
                stored.pop(code, None)

        if not before:
            return effective_clauses()

        setattr(row, SETTINGS_FIELD, stored)
        row.save(update_fields=[SETTINGS_FIELD, "updated_at"])
        # Hard rule 7, in the SAME transaction. A changed rights clause cannot
        # stand without its trail row (`core.audit` fails loudly).
        audit.money_action(
            actor, AUDIT_ACTION, AUDIT_ENTITY, str(row.pk), before=before, after=after
        )

    return effective_clauses()


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-007@rights-footer (12-governance/11-change-requests.md §"CR-007 · The disconnect notices — the platform writes the defaults" · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-014 + BR-NOT-015 · 04-docs/01-spec/19-document-templates.md §2 + r8 revision · 12-governance/01-open-questions.md OQ-253 (row 249, the rights-footer meaning — see DEF-226 on the id collision))
# generated: 2026-08-17 by story-coder (CR-007 DISCONNECT-NOTICE lane)
# checklist: A✔ B✔ C✔ D✔(GET|PATCH /disconnect-rights-footer) E✔(S8 → Notifications, the rights-footer card with five tick boxes) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · G7 (enrolled in 10-scripts/gates/human_owned.txt — this file holds the sentences that tell a customer how to keep their water on) · every guard proved RED first, transcripts in 06-backend/tests/test_cr_007_disconnect_rights_footer.py
# exceptions: (1) NO COMMISSION CONTACT IS WRITTEN. BR-NOT-015 says a utility
#         "already supplies its commission reference" and NOTHING IN THE PRODUCT
#         STORES ONE — `generate_disconnect_notice` takes `state_puc_ref` as a
#         caller argument and no screen sets it. OQ-263 minted rather than
#         answered; the clause points at the reference printed on the notice
#         instead of naming a regulator.
#         (2) THE FIVE CLAUSE CODES ARE PLATFORM VOCABULARY. A tenant may edit
#         and switch off, and may not add a sixth — a clause with no palette and
#         no review is the invention BR-NOT-015 exists to refuse. The whole body
#         stays editable on SET-10 for a utility that needs more.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
