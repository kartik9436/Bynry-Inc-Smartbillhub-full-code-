# ── Trace ──────────────────────────────────────────────
# Story:    CR-007 (the disconnect notices — the platform writes the defaults,
#           PO ruling 2026-08-17)   Screens: S8 → Notifications · SET-10
# Rules:    BR-NOT-015 (the rights footer ships as a PLATFORM DEFAULT, VISIBLY
#           MARKED, overridable by a System Admin, audited) · BR-NOT-014 (three
#           disconnect slots, one per tier; the ladder selects by tier) ·
#           BR-CUS-039 (the reconnect fee is a tenant charge code) ·
#           BR-IDN-009 (server-enforced role gating) · CLAUDE.md rule 1 · rule 7
# ───────────────────────────────────────────────────────
"""The five rights clauses, the tick boxes, and the notice they finally produce.

**THE DEFECT THIS CLOSES, IN ONE SENTENCE:** until 2026-08-17 the three
disconnect tiers were built, EMPTY and refused every save by name, so **no
disconnection notice could be produced on any tenant** — a utility could bill a
customer, chase them and write them off, and could not send the one letter the
law requires before the water goes off.

**THE RULING THAT LET US FIX IT**, verbatim, PO 2026-08-17:

  > *"we will take this option; we provide default option for all 5 you ahve
  > mentioned; if Utility wants to over ride it let them do it; I can also give
  > tick boxes if required to add 5"*
  > *"you build default langauge and let Utility user change it as they want"*

**WHAT THIS FILE WILL NOT LET ANYONE FORGET.** A default is a starting point, not
legal advice. Every clause is marked as a platform default on screen, is
switchable and overridable by the utility's own System Admin, and nothing here —
in a body, in the UI or in a docstring — claims this platform warrants the
wording to anybody's regulator. `test_…the_default_is_visibly_marked_as_a_default`
is that requirement made mechanical.

Read the sections in order; each is a separate way the footer could go wrong:

  1. the clause vocabulary and the palette it may draw on
  2. the wording itself — what it may not say
  3. the tick boxes, and OFF meaning off
  4. the override, and who may make it
  5. the three tier bodies
  6. **the whole point: a real tenant produces a real disconnection notice**
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.notifications import catalogs, models, notices, rendering, rights_footer
from apps.notifications import seed_templates as seed
from apps.notifications import settings_api
from apps.notifications import template_models as tm
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_actions, make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

TIERS = (
    "disconnect_notice_10_day",
    "disconnect_notice_5_day",
    "disconnect_notice_48_hour",
)

#: The three tier bodies, keyed the way `SEEDABLE` holds them.
TIER_BODIES = {entry.code: entry for entry in seed.SEEDABLE if entry.code in TIERS}


def _call(view, tenant, actor, method="get", body=None, role="system_admin"):
    return api_call(view, method, tenant=tenant, user=actor.user, role=role, data=body)


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE VOCABULARY AND THE PALETTE
# ══════════════════════════════════════════════════════════════════════════
def test_cr_007__there_are_exactly_five_clauses_and_they_are_the_five_ruled():
    """BR-NOT-015 names five and the PO's ruling names the same five.

    Written out rather than counted, so adding a sixth is a decision somebody has
    to come here and make — which is the moment they have to say which ruling
    put a new paragraph on a regulated letter.
    """
    assert rights_footer.CLAUSE_CODES == (
        "dispute_rights",
        "medical_hold",
        "weather_suppression",
        "weekend_holiday_suppression",
        "commission_complaint",
    )


def test_cr_007__a_clause_may_only_use_a_token_all_three_tiers_allow():
    """**The palette is the INTERSECTION, and it is computed rather than typed.**

    One footer prints on all three of BR-NOT-014's slots, and their whitelists
    differ on purpose — that difference is what stops a 10-day warning being
    written as a 48-hour certified letter. A clause using `{48h}` would validate
    on tier 3 and be refused on tier 1, and the difference would only surface
    when somebody tried to save.

    PROVED RED by replacing the intersection with `catalog_for(TIERS[2]).tokens`:
    `{48h}` and `{certified_no}` entered the permitted set and
    `test_…a_clause_naming_a_tier_specific_token_is_refused` stopped raising
    (`Failed: DID NOT RAISE RightsFooterRefused`).
    """
    permitted = rights_footer.allowed_tokens()
    for code in TIERS:
        assert permitted <= catalogs.catalog_for(code).tokens, code
    # The tier-exclusive tokens are OUT, one per tier.
    assert "pay_by_date" not in permitted  # 10-day only
    assert "reconnect_fee" not in permitted  # 5-day only
    assert {"48h", "certified_no"} & permitted == set()  # 48-hour only
    # And the shared ones a clause actually needs are IN.
    assert {"support_phone", "support_email", "account_no", "service_address"} <= permitted


def test_cr_007__the_logo_token_is_excluded_from_the_clause_palette():
    """DEF-195 — the render context supplies no value for `{utility_logo}`, so a
    clause naming it would print `——` inside a statement of legal rights.

    All three tiers OFFER it (A19 §1.1's masthead is on every printable class),
    so the intersection would contain it if nothing removed it. It is removed
    explicitly and this asserts the removal rather than the intersection.
    """
    assert "utility_logo" in catalogs.catalog_for(TIERS[0]).tokens
    assert "utility_logo" not in rights_footer.allowed_tokens()


@pytest.mark.parametrize("clause", rights_footer.CLAUSES, ids=lambda c: c.code)
def test_cr_007__every_default_clause_uses_only_permitted_tokens(clause):
    """The defaults obey their own rule. A platform clause that could not be
    re-saved through the ordinary door would be a special case living inside a
    customer-facing document — the posture `seed_templates` already refuses."""
    used = set(rendering.tokens_in(clause.default_text))
    assert used <= rights_footer.allowed_tokens(), (
        f"{clause.code} uses {sorted(used - rights_footer.allowed_tokens())}, which not "
        "every disconnection tier allows"
    )


def test_cr_007__a_clause_naming_a_tier_specific_token_is_refused(brazos, dana):
    """The save-time gate. Without it a System Admin could put `{meter_no}` on a
    disconnection notice through the side door — the footer is merged INTO a body
    that has already been validated, so the body's own check cannot see it."""
    with tenant_ctx(brazos):
        with pytest.raises(rights_footer.RightsFooterRefused, match="cannot be used"):
            rights_footer.validate_clause_text(
                "weather_suppression", "Reconnection costs {reconnect_fee}."
            )
        with pytest.raises(rights_footer.RightsFooterRefused, match="cannot be used"):
            rights_footer.validate_clause_text("dispute_rights", "Meter {meter_no} was read.")
        # …and the one that would print a blank in the middle of the rights.
        with pytest.raises(rights_footer.RightsFooterRefused, match="cannot be used"):
            rights_footer.validate_clause_text("dispute_rights", "{utility_logo} Call us.")


def test_cr_007__an_empty_clause_is_refused_because_OFF_is_what_the_tick_box_is_for(brazos):
    """Blanking a clause would leave a heading with nothing under it, which reads
    on the printed notice exactly like wording somebody had not finished."""
    with tenant_ctx(brazos):
        with pytest.raises(rights_footer.RightsFooterRefused, match="switch it OFF"):
            rights_footer.validate_clause_text("medical_hold", "   ")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE WORDING — WHAT IT MAY NOT SAY
# ══════════════════════════════════════════════════════════════════════════
#: DEF-210's own table, reused rather than re-typed — one list of phrases the
#: prototype draws and no rule states, so a lane cannot fix a body by editing a
#: second copy of the table.
#:
#: ⚠ **`"60 days"` IS DELIBERATELY EXEMPTED HERE AND ONLY HERE, AND THE REASON IS
#: NOT "it looked fine".** In DEF-210's table it is *"r10's rate-change notice
#: period. No rule states one"* — and that is still true of a rate-change email.
#: The medical-hold renewal period is a DIFFERENT figure that IS ruled, twice:
#: BR-NOT-015's own clause list says *"medical hold (physician-certified, 60-day
#: renewable)"* and the PO's CR-007 ruling repeats it. So the exemption is scoped
#: to the one clause that carries it, and every other clause is still checked
#: against the phrase in full.
_UNRULED = {
    phrase: why
    for phrase, why in __import__(
        "tests.test_def_210_authored_template_bodies", fromlist=["UNRULED_PHRASES"]
    ).UNRULED_PHRASES.items()
}


@pytest.mark.parametrize("clause", rights_footer.CLAUSES, ids=lambda c: c.code)
def test_cr_007__no_clause_states_a_figure_or_rule_nobody_ruled(clause):
    """*"A body that invents a notice period is a compliance defect wearing a
    copy deck"* — applied to the five paragraphs where it matters most.

    A rights clause is the highest-risk prose in the product: it looks official
    the moment it is written, and a customer may act on it.
    """
    text = clause.default_text.lower()
    exempt = {"60 days"} if clause.code == "medical_hold" else set()
    found = sorted(phrase for phrase in _UNRULED if phrase.lower() in text and phrase not in exempt)
    assert found == [], f"{clause.code} states {found}: " + " ".join(
        _UNRULED[phrase] for phrase in found
    )


def test_cr_007__the_medical_hold_renewal_is_the_figure_the_ruling_states():
    """60 days, because BR-NOT-015 and the PO's ruling both write it — and the
    assertion is here so that changing it means changing a signed figure rather
    than editing a sentence."""
    assert "60 days" in rights_footer.CLAUSES[1].default_text
    assert rights_footer.CLAUSES[1].code == "medical_hold"


def test_cr_007__the_weather_clause_states_the_two_temperatures_the_po_named():
    """32°F and 100°F — the PO's own figures, in the ruling and in BR-NOT-015's
    clause list. Nothing converts them or adds a third."""
    text = rights_footer.CLAUSES[2].default_text
    assert "32°F" in text and "100°F" in text


def test_cr_007__no_clause_names_a_regulator_or_a_regulator_rule():
    """`{state_puc_ref}` is a per-tenant VALUE and nothing here writes one.

    r10 prints *"Required by PUC rule 25.29"* and *"follows TCEQ required
    language"* for a fictional Texas utility. A platform default that named a
    regulator would be wrong for every tenant outside that state, and wrong in
    the way that looks most authoritative.
    """
    for clause in rights_footer.CLAUSES:
        lowered = clause.default_text.lower()
        for banned in ("puc", "tceq", "25.29", "public utility commission of"):
            assert banned not in lowered, f"{clause.code} names {banned!r}"


def test_cr_007__no_clause_promises_an_outcome():
    """*"State rights and timeframes, never promise outcomes."*

    The clauses may say what a customer can ASK for and what we do not do. They
    may not say what the answer will be — a default that promised a hold would
    be a promise made on behalf of a utility that has never read it.
    """
    for clause in rights_footer.CLAUSES:
        lowered = clause.default_text.lower()
        for promise in (
            "we will grant",
            "we will approve",
            "guarantee",
            "we will hold your service",
            "your service will not be",
        ):
            assert promise not in lowered, f"{clause.code} promises: {promise!r}"


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE TICK BOXES — OFF MEANS OFF
# ══════════════════════════════════════════════════════════════════════════
def test_cr_007__every_clause_ships_on_and_untouched(brazos):
    """The PO's *"we provide default option for all 5"*. A footer arriving with
    a clause switched off would be a default nobody had chosen."""
    with tenant_ctx(brazos):
        clauses = rights_footer.effective_clauses()
    assert len(clauses) == 5
    assert all(clause.enabled for clause in clauses)
    assert all(clause.is_default for clause in clauses)


def test_cr_007__a_clause_switched_off_does_not_render_at_all(brazos, dana):
    """**The PO's own worked case:** *"a utility in a state with no weather rule
    must be able to turn that clause OFF"*.

    OFF contributes NOTHING — no heading, no blank line, no "(removed)" marker.
    A hole in a regulated letter is worse than a clause that was never there.

    PROVED RED by making `assemble` emit every clause regardless of `enabled`:
    the weather heading and its sentence both came back and this failed on
    `assert "Weather" not in footer`.
    """
    with tenant_ctx(brazos):
        before = rights_footer.footer_text()
        assert "32°F" in before
        assert rights_footer.CLAUSES[2].title in before

        rights_footer.update_clauses(actor=dana, weather_suppression={"enabled": False})
        after = rights_footer.footer_text()

    assert "32°F" not in after
    assert rights_footer.CLAUSES[2].title not in after
    # …and every OTHER clause is untouched. A tick box that quietly took a
    # neighbour with it is the failure this half exists to catch.
    for kept in (0, 1, 3, 4):
        assert rights_footer.CLAUSES[kept].title in after


def test_cr_007__all_five_off_leaves_an_empty_footer_and_the_notice_still_renders(brazos, dana):
    """The extreme the tick boxes make reachable, asserted rather than assumed.

    A utility may switch every clause off — it is their regulator's call, not
    ours. `{rights_footer}` then expands to nothing and the rest of the letter,
    including `{state_puc_ref}`, is unaffected. The alternative (refusing the
    last one) would be this platform deciding a compliance question for them.
    """
    with tenant_ctx(brazos):
        rights_footer.update_clauses(
            actor=dana, **{code: {"enabled": False} for code in rights_footer.CLAUSE_CODES}
        )
        assert rights_footer.footer_text() == ""
        rendered = rendering.render(
            template_code="disconnect_notice_10_day",
            template_version=1,
            body=TIER_BODIES["disconnect_notice_10_day"].body,
            context={"balance": Decimal("10.00"), "state_puc_ref": "REF-1"},
        )
    assert "REF-1" in rendered.body
    assert rights_footer.CLAUSES[0].title not in rendered.body


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE OVERRIDE, AND WHO MAY MAKE IT
# ══════════════════════════════════════════════════════════════════════════
def test_cr_007__an_override_replaces_the_default_and_flips_is_default(brazos, dana):
    """BR-NOT-015: *"a System Admin may replace it with their regulator-approved
    wording"*, and the platform's own text stays available to restore."""
    own = "Call {support_phone} within ten days to dispute this bill."
    with tenant_ctx(brazos):
        rights_footer.update_clauses(actor=dana, dispute_rights={"text": own})
        clauses = {c.code: c for c in rights_footer.effective_clauses()}
        footer = rights_footer.footer_text()

    assert clauses["dispute_rights"].text == own
    assert clauses["dispute_rights"].is_default is False
    assert clauses["dispute_rights"].default_text == rights_footer.CLAUSES[0].default_text
    assert own in footer
    # The platform sentence it replaced is GONE from the letter.
    assert "which charge you are questioning" not in footer
    # …and the other four are still ours.
    assert all(c.is_default for code, c in clauses.items() if code != "dispute_rights")


def test_cr_007__null_text_restores_the_platform_default(brazos, dana):
    """The way back. A tenant who overrode a clause and wants ours again must not
    have to retype a paragraph they would then own."""
    with tenant_ctx(brazos):
        rights_footer.update_clauses(actor=dana, medical_hold={"text": "Call us."})
        assert rights_footer.effective_clauses()[1].is_default is False
        rights_footer.update_clauses(actor=dana, medical_hold={"text": None})
        restored = rights_footer.effective_clauses()[1]
    assert restored.is_default is True
    assert restored.text == rights_footer.CLAUSES[1].default_text


def test_cr_007__only_a_system_admin_may_change_a_clause(brazos, marcus):
    """BR-NOT-015 (b) — *"the override is a System-Admin-only, AUDITED write — it
    is the text telling a customer their legal rights"*. Enforced in the SERVICE,
    so it holds for a shell and a job as well as for the screen (BR-IDN-009).

    PROVED RED by removing `@require_role(SYSTEM_ADMIN)` from `update_clauses`:
    a Billing Clerk rewrote the medical-hold clause on a regulated letter and
    this failed with `Failed: DID NOT RAISE AuthError`.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            rights_footer.update_clauses(actor=marcus, medical_hold={"enabled": False})
        # Nothing moved.
        assert rights_footer.effective_clauses()[1].enabled is True


def test_cr_007__every_change_writes_one_audit_row_carrying_the_full_before_and_after(
    brazos, dana, audit_rows
):
    """Hard rule 7 · BR-TEN-016, and the payload shape is the point.

    The text is recorded IN FULL rather than as a length or a hash: what changed
    is the sentence a customer reads about their legal rights, and a trail saying
    *"text changed, 412 → 380 characters"* answers nothing anybody would ask it.
    """
    with tenant_ctx(brazos):
        audit_rows.clear()
        rights_footer.update_clauses(
            actor=dana, commission_complaint={"text": "Write to the state commission."}
        )

    assert audit_actions(audit_rows) == ["notification_settings.updated"]
    trail = audit_rows[0]
    entry = trail["after"]["commission_complaint"]
    assert entry["text"] == "Write to the state commission."
    assert entry["is_platform_default"] is False
    assert trail["before"]["commission_complaint"]["is_platform_default"] is True


def test_cr_007__a_no_op_save_writes_nothing(brazos, dana, audit_rows):
    """A row saying a System Admin changed the rights wording, when they did not,
    is noise a reviewer has to read past on the one trail where they cannot."""
    with tenant_ctx(brazos):
        audit_rows.clear()
        # `enabled: True` is what every clause already holds.
        rights_footer.update_clauses(actor=dana, weather_suppression={"enabled": True})
    assert audit_actions(audit_rows) == []


def test_cr_007__a_sixth_clause_is_refused(brazos, dana):
    """The five codes are PLATFORM vocabulary. A clause a tenant invents has no
    palette and no review — the invention BR-NOT-015 exists to refuse. The whole
    body stays editable on SET-10 for a utility that needs more."""
    with tenant_ctx(brazos):
        with pytest.raises(rights_footer.RightsFooterRefused, match="not a rights clause"):
            rights_footer.update_clauses(actor=dana, late_fee_rights={"text": "Anything."})


# ══════════════════════════════════════════════════════════════════════════
# 4b · THE SCREEN'S OWN PAYLOAD — BR-NOT-015 (a), MADE MECHANICAL
# ══════════════════════════════════════════════════════════════════════════
def test_cr_007__the_default_is_visibly_marked_as_a_default(brazos, dana):
    """**THE REQUIREMENT CR-007 FORBADE SOFTENING, ASSERTED RATHER THAN TRUSTED.**

    BR-NOT-015 (a): the default must be VISIBLY MARKED as a default *"so it is
    never mistaken for the utility's own regulator's words"*. Three things carry
    that and all three are asserted, because each can be lost separately: the
    per-clause flag, the per-clause badge, and the standing paragraph that says
    a default is a starting point and must be reviewed against the utility's own
    commission before a notice goes out.

    ⚠ It is asserted on the API PAYLOAD rather than on a component, deliberately.
    Nothing in this repo reads rendered output (hard-won law 6), so the strongest
    honest guarantee is that the sentence is SERVED — a screen that worded it
    itself would drift from the rule the day BR-NOT-015 changed.
    """
    with tenant_ctx(brazos):
        response = _call(settings_api.disconnect_rights_footer, brazos, dana)
    assert response.status_code == 200
    payload = response.data

    notice = payload["platform_default_notice"]
    assert "not legal advice" in notice
    assert "starting point" in notice
    assert "commission" in notice
    assert "before any disconnection notice goes out" in notice

    for clause in payload["clauses"]:
        assert clause["is_default"] is True
        assert clause["source_label"] == rights_footer.PLATFORM_DEFAULT_LABEL
        assert "Platform default" in clause["source_label"]
        # Every clause carries OUR text alongside, so "restore the default" and
        # "compare against what it replaced" need no second round trip.
        assert clause["default_text"]

    # And the card says where the footer prints — BR-NOT-014's three tiers.
    assert [row["code"] for row in payload["prints_on"]] == list(TIERS)


def test_cr_007__the_marking_flips_when_a_utility_takes_the_clause_over(brazos, dana):
    """The other direction. A reader must be able to tell OUR words from THEIRS
    at a glance, both ways round — a one-way check passes on the day every clause
    reports "platform default" forever."""
    with tenant_ctx(brazos):
        _call(
            settings_api.disconnect_rights_footer,
            brazos,
            dana,
            method="patch",
            body={"clauses": {"weather_suppression": {"text": "No weather rule applies."}}},
        )
        response = _call(settings_api.disconnect_rights_footer, brazos, dana)
    rows = {row["code"]: row for row in response.data["clauses"]}
    assert rows["weather_suppression"]["is_default"] is False
    assert rows["weather_suppression"]["source_label"] == rights_footer.TENANT_WORDING_LABEL
    assert rows["medical_hold"]["is_default"] is True


def test_cr_007__the_endpoint_reports_read_only_for_a_clerk_with_its_reason(brazos, marcus):
    """BR-SHL-025 — the control renders, disabled, WITH the reason. A screen that
    hid it would leave a Billing Clerk unable to see what their utility's
    customers are being told."""
    with tenant_ctx(brazos):
        response = _call(
            settings_api.disconnect_rights_footer, brazos, marcus, role="billing_clerk"
        )
    assert response.data["can_edit"] is False
    assert "System Admin" in response.data["cannot_edit_reason"]
    assert len(response.data["clauses"]) == 5


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE THREE TIER BODIES
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("code", TIERS)
def test_cr_007__every_tier_body_passes_its_own_class_validator(code):
    """The one check that is never skipped: the seeded body is one the tenant's
    own designer would have accepted — same palette, same mandatory content."""
    rendering.validate_body(code, TIER_BODIES[code].body)


@pytest.mark.parametrize("code", TIERS)
def test_cr_007__every_tier_carries_the_commission_reference_and_the_rights_footer(code):
    """Both, on all three. `{state_puc_ref}` is US-NOT-007 TC-6's non-removable
    regulatory footer marker and `{rights_footer}` is the paragraph telling the
    customer what to do with it — a letter with one and not the other is half a
    legal notice."""
    body = TIER_BODIES[code].body
    assert "{state_puc_ref}" in body
    assert "{rights_footer}" in body
    assert catalogs.catalog_for(code).mandatory_content == (
        "{state_puc_ref}",
        "{rights_footer}",
    )


@pytest.mark.parametrize("code", TIERS)
def test_cr_007__no_tier_body_names_the_logo_token(code):
    """DEF-195. The context supplies no value, so it prints `——` on a customer's
    letter — and this is the letter where a blank is least acceptable."""
    assert "{utility_logo}" not in TIER_BODIES[code].body


def test_cr_007__tier_token_separation_still_holds_after_the_bodies_landed():
    """**BR-NOT-014's mechanism, re-asserted at the body level.**

    The catalog test proves the PALETTES differ. This proves the BODIES do — that
    the 10-day warning does not in fact speak of a cut date, a certified number
    or a reconnect fee, which is the thing a reader of the letter would notice.

    PROVED RED by pasting the 48-hour body over the 10-day entry in `SEEDABLE`:
    `validate_body` refused it at seed time (`{48h}, {certified_no} are not in
    the 'disconnect_notice_10_day' catalog`), and with the palettes widened to
    match, this case failed on `{'48h', 'certified_no', 'cut_date'} found in
    disconnect_notice_10_day`.
    """
    exclusive = {
        "disconnect_notice_10_day": {"pay_by_date"},
        "disconnect_notice_5_day": {"reconnect_fee"},
        "disconnect_notice_48_hour": {"48h", "certified_no"},
    }
    for code in TIERS:
        used = set(rendering.tokens_in(TIER_BODIES[code].body))
        for other, tokens in exclusive.items():
            if other == code:
                continue
            assert used & tokens == set(), f"{code} uses {sorted(used & tokens)}, {other}'s"


@pytest.mark.parametrize("code,sentence", sorted(seed._TIER_SENTENCES.items()))
def test_cr_007__every_tier_body_quotes_a19s_signed_sentence_verbatim(code, sentence):
    """A19 §2 writes one sentence per tier and OQ-243 quotes all three in full.

    The letter around it is authored; the sentence is not. Asserting it character
    for character means an edit that "improves" a signed paragraph goes RED
    rather than quietly reaching a customer — the same protection the two A13
    quotes have carried since 2026-08-16.
    """
    # The seeded bodies wrap for line length; compare on collapsed whitespace.
    body = " ".join(TIER_BODIES[code].body.split())
    assert " ".join(sentence.split()) in body


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE WHOLE POINT — A REAL TENANT PRODUCES A REAL NOTICE
# ══════════════════════════════════════════════════════════════════════════
def _an_account(actor, tenant, account_no):
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


def test_cr_007__a_provisioned_tenant_can_now_produce_all_three_disconnect_notices(brazos, dana):
    """**THE ACCEPTANCE CASE. Everything else in this file is a way it could be
    wrong; this is the thing that was broken.**

    Before 2026-08-17 this test could not have been written: every tier refused
    with *"no published 'disconnect_notice' template resolves"* on every tenant,
    because the slots were empty by design while nobody had ruled who writes the
    rights footer. Nothing was queued, nothing was rendered, and a utility could
    not send the letter the law requires before service is cut off.

    It uses NO fixture body. The tenant is provisioned through the real service
    and the notices render from what PROVISIONING PLANTED, which is the only
    shape that can catch this class of defect (DEF-163's own lesson, and
    DEF-123's before it).
    """
    with tenant_ctx(brazos):
        # THREE accounts, not one: hard rule 6 keys the queue on
        # (source_type, source_id, channel, copy_no), so three notices for one
        # account would be one queue row and a re-emitted event — correct
        # behaviour, and the wrong fixture for asserting three letters.
        one = _an_account(dana, brazos, "A-70001")
        two = _an_account(dana, brazos, "A-70002")
        three = _an_account(dana, brazos, "A-70003")

        first = notices.generate_disconnect_notice(
            account_id=one.pk,
            tier=notices.TIER_FIRST_10_DAY,
            balance=Decimal("1842.100000"),
            cut_date=date(2026, 9, 1),
            pay_by_date=date(2026, 8, 27),
            state_puc_ref="TX PUC Substantive Rule 25.29",
            on_date=date(2026, 8, 17),
            actor=dana,
        )
        second = notices.generate_disconnect_notice(
            account_id=two.pk,
            tier=notices.TIER_SECOND_5_DAY,
            balance=Decimal("1842.100000"),
            cut_date=date(2026, 9, 1),
            reconnect_fee=Decimal("45.000000"),
            state_puc_ref="TX PUC Substantive Rule 25.29",
            on_date=date(2026, 8, 22),
            actor=dana,
        )
        final = notices.generate_disconnect_notice(
            account_id=three.pk,
            tier=notices.TIER_FINAL_48_HOUR,
            balance=Decimal("1842.100000"),
            cut_date=date(2026, 9, 1),
            state_puc_ref="TX PUC Substantive Rule 25.29",
            on_date=date(2026, 8, 30),
            actor=dana,
        )

    # ── the ladder selects by tier (BR-NOT-014 / DEF-193) ─────────────────
    assert first.template_code == "disconnect_notice_10_day"
    assert second.template_code == "disconnect_notice_5_day"
    assert final.template_code == "disconnect_notice_48_hour"

    # ── each one rendered, and each one QUEUED (BR-NOT-005: never sent) ────
    for result in (first, second, final):
        assert result.artifact is not None
        assert len(result.queued_message_ids) == 1
        assert result.sent is False
        # The regulator's reference and the rights paragraph, on all three.
        assert "TX PUC Substantive Rule 25.29" in result.artifact.body
        for clause in rights_footer.CLAUSES:
            assert clause.title in result.artifact.body, clause.code

    # ── the tiers say different things, which is why there are three ───────
    assert "past due in the amount of" in first.artifact.body
    assert "FINAL REMINDER" in second.artifact.body
    assert "$45.00" in second.artifact.body  # BR-CUS-039's charge-code figure
    assert "NOTICE OF DISCONNECTION" in final.artifact.body
    assert final.certified_mail is True

    # ── and the queue rows are pinned to the RIGHT class ───────────────────
    with tenant_ctx(brazos):
        rows = models.OutboundMessage.objects.filter(account_id__in=[one.pk, two.pk, three.pk])
        assert {row.template_code for row in rows} == set(TIERS)


def test_cr_007__a_clauses_own_merge_fields_resolve_on_the_finished_letter(brazos, dana):
    """**The pre-pass order, proved on the output rather than argued in a comment.**

    `rendering.render` substitutes tokens with a single `re.sub`, and a
    replacement string is inserted literally and never re-scanned. A footer merged
    in DURING that pass would print `{support_phone}` on a customer's letter as
    fourteen literal characters and two braces.

    PROVED RED by moving `rights_footer.expand` to AFTER `TOKEN_RE.sub`. The
    ordering breaks in BOTH directions and the second is the nastier one, so both
    are asserted:

      * expanded too LATE and `{rights_footer}` has already been substituted as
        an ordinary token with no context value — so the whole rights paragraph
        is replaced by the named absence `——` and the customer's letter tells
        them nothing about their rights at all. Measured: the clause headings
        vanished and the phone number appeared ONCE (the sign-off) instead of
        twice.
      * expanded during the pass and a clause's own `{support_phone}` would be
        inserted literally, printing braces on a legal notice.
    """
    phone = "555-0100"
    with tenant_ctx(brazos):
        rendered = rendering.render(
            template_code="disconnect_notice_5_day",
            template_version=1,
            body=TIER_BODIES["disconnect_notice_5_day"].body,
            context={
                "balance": Decimal("100.00"),
                "cut_date": date(2026, 9, 1),
                "reconnect_fee": Decimal("45.00"),
                "state_puc_ref": "REF-9",
                "account_no": "A-70002",
                "support_phone": phone,
            },
        )
    # The clauses actually reached the page — not `——` where the rights go.
    for clause in rights_footer.CLAUSES:
        assert clause.title in rendered.body, clause.code
    assert rendering.ABSENT_MARK not in rendered.body.split("Commission reference")[0][-40:]
    # No unresolved braces anywhere in the footer the clauses contributed.
    assert "{support_phone}" not in rendered.body
    assert "{account_no}" not in rendered.body
    # `{support_phone}` appears in the CLAUSES as well as in the sign-off line,
    # so a count of one means the clause text never made it onto the letter.
    assert rendered.body.count(phone) >= 2
    # …and `{account_no}` merged inside a clause exactly as in the body.
    assert rendered.body.count("A-70002") >= 2


def test_cr_007__an_overridden_clause_reaches_the_customers_letter(brazos, dana):
    """The override is not a settings screen that stores a string — it changes
    the letter. Asserted end to end, because that is the only place the tenant's
    edit either did or did not matter."""
    own = "Dispute this bill by calling {support_phone} before the date above."
    with tenant_ctx(brazos):
        rights_footer.update_clauses(actor=dana, dispute_rights={"text": own})
        account = _an_account(dana, brazos, "A-70009")
        result = notices.generate_disconnect_notice(
            account_id=account.pk,
            tier=notices.TIER_FIRST_10_DAY,
            balance=Decimal("50.00"),
            cut_date=date(2026, 9, 1),
            pay_by_date=date(2026, 8, 27),
            state_puc_ref="REF-3",
            on_date=date(2026, 8, 17),
            actor=dana,
        )
    assert "Dispute this bill by calling" in result.artifact.body
    assert "which charge you are questioning" not in result.artifact.body


def test_cr_007__the_seeded_variant_survives_a_repair_run(brazos, dana):
    """Hard-won law 4 in its data form: a provisioning-time change reaches a
    tenant when it is created and never afterwards, so `seed_demo --tenant X` is
    the repair door for every tenant provisioned before today — and it must be
    safe to run on a tenant whose System Admin has already edited a body.

    ⚠ **THERE IS NO FIXTURE-VERSION BUMP ON THIS SEEDER AND SAYING SO IS THE
    POINT.** `notification_templates` has no `fixture_version` column — that
    mechanism belongs to `apps/tenancy`'s reference lists. This seeder is
    INSERT-MISSING: a variant that already publishes a version is left alone and
    reported `already_present`. So the three tier bodies reach a NEW tenant at
    provisioning and reach an EXISTING one only when an operator runs the repair
    door, and nothing overwrites a utility's own wording either way.
    """
    with tenant_ctx(brazos):
        again = seed.seed_notice_templates(dana, on_date=date(2026, 8, 17))
        rows = {row["code"]: row for row in again["seeded"]}
        for code in TIERS:
            assert rows[code]["already_present"] is True
            assert rows[code]["created"] is False
        published = tm.NotificationTemplateVersion.objects.filter(
            tenant_id=brazos.pk,
            template__code__in=TIERS,
            status=tm.VERSION_PUBLISHED,
        )
        assert published.count() == 3
