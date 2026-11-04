# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (the dispatch config, served and editable) ·
#           US-NOT-005 (merge-variable catalogs) · US-NOT-006 (what is
#           PUBLISHED) · US-NOT-010 (the tone→tier mapping) · US-NOT-016
#           (custom fields as template variables)   Screens: S8
# Rules:    BR-TEN-041 #8 · BR-NOT-005 (queue only; no send endpoint) ·
#           BR-NOT-008 (a regulated step ALWAYS renders the disconnect class) ·
#           BR-NOT-009 (quiet hours) · BR-NOT-010 (print is the floor) ·
#           BR-PAY-035 (three tones, no fourth) · BR-REP-016 (day numbers are
#           tenant config) · BR-CUS-039 (certified mail on the final tier) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · CLAUDE.md rule 7
# ───────────────────────────────────────────────────────
"""The S8 Notifications CONFIG half, over HTTP.

`test_us_not_010__firm_selects_the_regulated_disconnect_notice` is the case to
read first, because it is the one a clerk gets wrong. BR-NOT-008 says
*"regulated ladder steps ALWAYS render the disconnect-notice template class
regardless of the tone picked in the reminder modal"*, so picking **Firm** does
not send a firmer reminder — it sends the **10-day REGULATED disconnect
notice**, and **Final** sends the **48-hour CERTIFIED** letter at real postage
and on the legal record. Until this route landed nothing in the product showed
that anywhere.

`test_the_template_read_separates_the_two_reasons_a_body_is_missing` is the
second. DEF-163 — nothing created a `notification_templates` row on any
deployment, so every notice was REFUSED at render — is CLOSED for the classes a
signed spec writes in full (`dunning`, `receipt`: provisioning plants them), and
deliberately OPEN for the rest. The read therefore carries TWO absences per row
and the test holds them apart: `published_unavailable` is *"this utility has not
been given the letter"* (a repair run fixes it) and `body_unavailable` is
*"nobody has written this letter"* (only a ruling fixes it — OQ-243, OQ-244,
OQ-206, OQ-207). A card that showed one blank cell for both would send a person
to the wrong place.

Every path is resolved through the REAL root URLconf first: an `api.py` that
exports `urlpatterns` is not an endpoint until `config/urls.py` includes it
(DEF-112 / DEF-128, four times in this repository).
"""

from __future__ import annotations

import pytest
from django.urls import resolve

from apps.notifications import catalogs, notices
from apps.notifications import settings_api as api

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _get(view, tenant, actor, role="system_admin"):
    return api_call(view, "get", user=getattr(actor, "user", None), role=role, tenant=tenant)


# ── the routes exist at all ────────────────────────────────────────────────
def test_the_three_config_paths_resolve_through_the_root_urlconf():
    base = "/api/brazosbend"
    assert resolve(f"{base}/notification-settings").func is api.notification_settings
    assert resolve(f"{base}/notification-templates").func is api.notification_templates
    assert resolve(f"{base}/notice-tones").func is api.notice_tones


def test_no_send_endpoint_is_minted_anywhere_in_this_module():
    """A11 Addendum r2 §4 / BR-NOT-005: *"no synchronous send endpoint anywhere
    (queue only)"*. Minting one is a gate failure; asserted as an ABSENCE so the
    rule stays visible."""
    from django.urls import Resolver404

    for path in ("notification-settings/send", "notice-tones/send", "notifications/send"):
        with pytest.raises(Resolver404):
            resolve(f"/api/brazosbend/{path}")


# ── US-NOT-004 · the dispatch configuration ────────────────────────────────
def test_us_not_004__the_config_a_tenant_has_is_readable(brazos, dana):
    """BR-BIL-016's 500 and BR-NOT-009's 08:00–21:00 are the tenant's own row,
    created on first read with the ratified defaults."""
    with tenant_ctx(brazos):
        response = _get(api.notification_settings, brazos, dana)
    assert response.status_code == 200
    assert response.data["dispatch_batch_size"] == 500
    assert response.data["quiet_hours_start"] == "08:00"
    assert response.data["quiet_hours_end"] == "21:00"
    # BR-BIL-036 — print is the FLOOR and has no column to switch off.
    assert response.data["print_dispatch_active"] is True


def test_us_not_004__no_screen_can_read_a_channel_flag_as_a_send(brazos, dana):
    """A switch is always read beside what its channel is actually doing.

    ⚠ AMENDED 2026-10-22 (`DEF-NOT-10533`, PO: *"Each channel tells the clerk
    the truth about itself, in one short line"*). This asserted the card-wide
    *"Nothing is sent in this release … none of it leaves the building"* — true
    in R2, false once the dispatcher and the Custom SMTP adapter went live. The
    claim that survives is the one this test is named for: no flag is served
    without its channel's live line beside it, and the old sentence is gone.
    """
    with tenant_ctx(brazos):
        response = _get(api.notification_settings, brazos, dana)
    assert "no_dispatcher_reason" not in response.data
    assert "dispatch_runs_in_this_release" not in response.data
    lines = {line["channel"]: line for line in response.data["channel_lines"]}
    assert set(lines) == {"email", "sms", "pdf_print"}
    # Email and text ship switched off, and say so rather than "sending".
    assert lines["email"]["state"] == "off"
    assert lines["sms"]["state"] == "off"
    # Print has no switch (BR-BIL-036); with no vendor connected it waits.
    assert lines["pdf_print"]["state"] == "waitingPrintVendor"


def test_us_not_004_tc5__a_clerk_may_read_the_config_and_may_not_change_it(brazos, marcus):
    """A1: Settings screens are System Admin. The gate is the SERVICE's
    `@require_role`, so it holds for every endpoint, job and shell — the screen
    hiding a field is not the gate (BR-SHL-025)."""
    with tenant_ctx(brazos):
        assert (
            _get(api.notification_settings, brazos, marcus, role="billing_clerk").status_code == 200
        )
        denied = api_call(
            api.notification_settings,
            "patch",
            user=getattr(marcus, "user", None),
            role="billing_clerk",
            tenant=brazos,
            data={"dispatch_batch_size": 250},
        )
    assert denied.status_code == 403


def test_us_not_004__an_admin_edit_is_saved_and_audited(brazos, dana, audit_rows):
    """T7-17: a saved change takes effect at the next hand-off, and ONE audit
    row records it before→after (hard rule 7)."""
    with tenant_ctx(brazos):
        response = api_call(
            api.notification_settings,
            "patch",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"dispatch_batch_size": 250, "quiet_hours_start": "09:00"},
        )
        assert response.status_code == 200
        assert response.data["dispatch_batch_size"] == 250
        assert response.data["quiet_hours_start"] == "09:00"
    # ONE row, carrying only what ACTUALLY moved (T7-16/T7-17 both assert that
    # shape) — a payload padded with unchanged fields makes the next reader hunt
    # for the edit.
    written = [row for row in audit_rows if row["action"] == "notification_settings.updated"]
    assert len(written) == 1
    assert written[0]["before"]["dispatch_batch_size"] == 500
    assert written[0]["after"]["dispatch_batch_size"] == 250


def test_us_not_004_tc6__a_zero_batch_size_is_refused_with_its_reason(brazos, dana):
    """A zero would hand the provider nothing on every cycle: the queue fills,
    nothing leaves, and every screen shows a provider outage that is not
    happening."""
    with tenant_ctx(brazos):
        response = api_call(
            api.notification_settings,
            "patch",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"dispatch_batch_size": 0},
        )
    assert response.status_code == 422
    assert "would hand the provider nothing" in str(response.data)


def test_a_window_that_ends_before_it_starts_is_refused(brazos, dana):
    """BR-NOT-009 exists to stop a utility texting late-payment reminders at
    23:00, and one transposed pair of times would invert that protection for
    every customer at once. Refused rather than read as "wraps midnight"."""
    with tenant_ctx(brazos):
        response = api_call(
            api.notification_settings,
            "patch",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"quiet_hours_start": "21:00", "quiet_hours_end": "08:00"},
        )
    assert response.status_code == 422
    assert "ends before it starts" in str(response.data)


# ── US-NOT-010 · which letter a tone actually selects ──────────────────────
def test_us_not_010__firm_selects_the_regulated_disconnect_notice(brazos, dana):
    """BR-NOT-008 — the assertion this whole surface exists for.

    Picking **Firm** in a reminder modal does not send a firmer reminder: it
    sends the REGULATED 10-day disconnect notice, with its cut date and its
    statutory footer. **Final** sends the 48-hour CERTIFIED letter, at real
    postage and on the legal record. Only **friendly** renders the dunning class.
    """
    with tenant_ctx(brazos):
        response = _get(api.notice_tones, brazos, dana)
    assert response.status_code == 200
    by_tone = {row["tone"]: row for row in response.data["tones"]}

    assert by_tone["friendly"]["template_class"] == notices.CLASS_DUNNING
    assert by_tone["friendly"]["regulated"] is False
    assert by_tone["friendly"]["certified_mail"] is False

    # ⚠ AMENDED 2026-08-17 (CR-007 / DEF-193). Both regulated tones used to
    # report the SAME class here — the superseded single `disconnect_notice` —
    # so this surface could not tell a System Admin the one thing it exists to
    # tell them: that "final" sends a DIFFERENT letter at certified postage.
    # BR-NOT-014 gives each tier its own class and `TIER_TO_CLASS` is the map.
    assert by_tone["firm"]["template_class"] == "disconnect_notice_10_day"
    assert by_tone["firm"]["step"] == notices.TIER_FIRST_10_DAY
    assert by_tone["firm"]["regulated"] is True

    assert by_tone["final"]["template_class"] == "disconnect_notice_48_hour"
    assert by_tone["final"]["step"] == notices.TIER_FINAL_48_HOUR
    assert by_tone["firm"]["template_class"] != by_tone["final"]["template_class"]
    # BR-CUS-039 — certified mail is REQUIRED on the final tier.
    assert by_tone["final"]["certified_mail"] is True

    # BR-PAY-035 — three tones and no fourth: "free-text tones do not exist".
    assert len(by_tone) == 3
    assert response.data["free_text_tones_exist"] is False
    # PO 2026-08-16 — generating a notice QUEUES it. Nothing sends.
    assert response.data["generation_queues_only"] is True


def test_us_not_010_tc3__the_day_numbers_are_the_tenants_own_or_are_absent(brazos, dana):
    """BR-REP-016: *"day numbers are always tenant config, never constants"*.

    Whichever the tenant's settings say, the response either carries THEIR
    numbers or reports that it could not read them — and never falls back to
    BR-REP-016's 7/14/30 seeds, because a letter printing the wrong day tells a
    customer the wrong date to pay by.
    """
    with tenant_ctx(brazos):
        response = _get(api.notice_tones, brazos, dana)
    days = response.data["stage_days"]
    reason = response.data["stage_days_unavailable"]
    assert (days is None) != (reason is None)  # exactly one of the two
    if days is None:
        assert "seeds" in reason.lower() or "ladder" in reason.lower()
    # The CLASS a tone selects is a rule and never depends on a day number, so
    # the tones render either way.
    assert len(response.data["tones"]) == 3


# ── US-NOT-005 / US-NOT-006 / US-NOT-016 · the letters themselves ──────────
def test_the_template_read_separates_the_two_reasons_a_body_is_missing(brazos, dana):
    """DEF-163, both halves — the one that is fixed and the one that is not.

    **Fixed:** provisioning plants the classes A13 writes in full, so `dunning`
    and `receipt` answer with a published version and this utility can produce
    a reminder and a receipt for the first time.

    **Still empty, on purpose:** the SUPERSEDED single `disconnect_notice` class
    answers `published: null` and says WHY — A19 §2 has three tier bodies and a
    variant holds one, so a body here would be a fourth disconnect wording with
    no tier and no ladder position. ⚠ **Its THREE REPLACEMENTS are no longer
    empty** (CR-007, 2026-08-17): the PO ruled that the platform writes the
    rights footer, so `disconnect_notice_10_day` / `_5_day` / `_48_hour` each
    carry a seeded body and this utility can produce a disconnection notice.

    The two absences are different problems with different fixes and the row
    keeps them apart.
    """
    with tenant_ctx(brazos):
        response = _get(api.notification_templates, brazos, dana)
    assert response.status_code == 200
    rows = {row["code"]: row for row in response.data["results"]}

    for code in ("dunning", "receipt"):
        assert rows[code]["published"] is not None, code
        assert rows[code]["published"]["version"] == 1, code
        assert rows[code]["published_unavailable"] is None, code
        assert rows[code]["body_unavailable"] is None, code

    disconnect = rows["disconnect_notice"]
    assert disconnect["published"] is None
    # ⚠ AMENDED (CR-016, 2026-08-19). Both of these asserted a RULE ID inside a
    # sentence the Settings → Notifications screen renders to a utility. The
    # distinction the test exists to protect — that the two absences are
    # DIFFERENT PROBLEMS WITH DIFFERENT FIXES, and a card showing one blank cell
    # for both would send a person to the wrong place — is unchanged and is
    # asserted on the customer wording.
    #
    # Provenance: `published_unavailable` is BR-NOT-001's mandatory default
    # variant; `body_unavailable` for this class is structural, because
    # BR-NOT-014 replaced the single class with three tiers.
    #
    # "this utility has not been given the letter" — a repair run fixes it.
    assert "has no published wording" in disconnect["published_unavailable"]
    assert "Publish a default version" in disconnect["published_unavailable"]
    assert "BR-NOT-" not in disconnect["published_unavailable"]
    # "nobody has written this letter" — and for THIS class it is structural
    # rather than a missing ruling: the single class was replaced by three.
    assert "replaced by three separate notices" in disconnect["body_unavailable"]
    assert "BR-NOT-" not in disconnect["body_unavailable"]
    # ⚠ AND THE THREE THAT REPLACED IT DO ANSWER, which is CR-007's whole point:
    # before 2026-08-17 no tenant on the platform could produce a disconnection
    # notice at any tier.
    for tier_code in (
        "disconnect_notice_10_day",
        "disconnect_notice_5_day",
        "disconnect_notice_48_hour",
    ):
        assert rows[tier_code]["body_unavailable"] is None, tier_code
        assert rows[tier_code]["published"] is not None, tier_code
    # ⚠ AMENDED (CR-016): OQ-244 was the id in the sentence. The claim it
    # protected — that the payment-plan agreement HAS wording waiting and is
    # merely undated — is what is asserted now. (OQ-244's remainder is the
    # repeating-block renderer for the instalment schedule.)
    assert "ready and waiting" in rows["contract_payment_plan"]["body_unavailable"]
    assert "OQ-" not in rows["contract_payment_plan"]["body_unavailable"]
    # ⚠ AMENDED 2026-08-17 (DEF-210). `email_past_due` used to answer OQ-206
    # here; the PO ruled *"please define it for this product"* and it now has a
    # body, so the case moves to a class that ruling could NOT reach — a NACHA
    # autopay authorization, whose wording is a payment scheme's.
    assert rows["email_past_due"]["body_unavailable"] is None
    # ⚠ AMENDED (CR-016): OQ-206 was the id. The claim — that this class is a
    # PLACEHOLDER the product refuses to print, not a default a utility can
    # publish as it stands — is what a person must be told, and is asserted here.
    autopay = rows["contract_autopay_authorization"]["body_unavailable"]
    assert "placeholder, not finished wording" in autopay
    assert "will not print it until you replace it" in autopay
    assert "OQ-" not in autopay

    from apps.notifications import seed_templates as _seed

    seeded = [entry.code for entry in _seed.SEEDABLE]
    assert response.data["platform_seeded_classes"] == seeded
    assert response.data["classes_without_a_body"] == len(response.data["results"]) - len(seeded)
    assert response.data["seeder"] == "apps.notifications.services.seed_notice_templates"


def test_us_not_005__the_variable_catalogue_is_served_per_class(brazos, dana):
    """A token outside the catalogue is refused at SAVE rather than rendered
    empty (US-NOT-005 TC-5), so serving the whitelist is what lets a person see
    what a letter of this kind may say."""
    with tenant_ctx(brazos):
        response = _get(api.notification_templates, brazos, dana)
    rows = {row["code"]: row for row in response.data["results"]}

    # A19 §2 tier 3's own tokens, and the regulatory footer that cannot be
    # removed from this class (US-NOT-007 TC-6).
    assert "cut_date" in rows["disconnect_notice"]["variables"]
    assert "reconnect_fee" in rows["disconnect_notice"]["variables"]
    assert "{state_puc_ref}" in rows["disconnect_notice"]["mandatory_content"]

    # CR-007 — the three LIVE tiers add a second non-removable phrase. The pair
    # is the rule: `{state_puc_ref}` is the regulator's reference and
    # `{rights_footer}` is the paragraph telling the customer what to do with
    # it, and a letter carrying one without the other is half a legal notice.
    for tier_code in (
        "disconnect_notice_10_day",
        "disconnect_notice_5_day",
        "disconnect_notice_48_hour",
    ):
        mandatory = rows[tier_code]["mandatory_content"]
        assert "{state_puc_ref}" in mandatory, tier_code
        assert "{rights_footer}" in mandatory, tier_code

    # A19 rule 2: dunning is a REMINDER and carries NO regulatory footer, so the
    # token is deliberately ABSENT and a body using it is refused.
    assert "state_puc_ref" not in rows["dunning"]["variables"]

    # US-NOT-005 TC-5 — a receipt has no meter number, by whitelist.
    assert "meter_no" not in rows["receipt"]["variables"]


def test_us_not_016__custom_fields_are_offered_as_a_SHAPE_not_a_live_list(brazos, dana):
    """BR-NOT-012: custom fields resolve from the STAMPED SNAPSHOT and never
    from live master data. Serving this tenant's current field list here would
    be exactly the lookup that rule forbids, one layer up."""
    with tenant_ctx(brazos):
        response = _get(api.notification_templates, brazos, dana)
    rows = {row["code"]: row for row in response.data["results"]}
    assert "{{account.custom.<key>}}" in rows["dunning"]["custom_field_variables"]


def test_a_class_with_no_token_catalogue_carries_its_REASON(brazos, dana):
    """An empty catalogue and an unspecified one are different facts. The
    seventeen classes A19 ratifies and gives no tokens (OQ-206, OQ-207) travel
    with the reason verbatim rather than as an empty variable list.

    ⚠ **AMENDED 2026-08-18 (CR-011 item 9) — THERE ARE NO LONGER ANY.** The last
    two examples here were the service and deposit agreements, and the PO ruled
    *"the 4 template classes needing legal wording - already answer - provide
    default and allow user to change"*, so both have a palette.
    `catalog_unavailable` is now `None` on EVERY row, which is the assertion
    below: the field stays on the payload (the next unruled class needs it) and
    is proved to be reporting an empty set rather than quietly always-null.
    """
    with tenant_ctx(brazos):
        response = _get(api.notification_templates, brazos, dana)
    rows = {row["code"]: row for row in response.data["results"]}
    # ⚠ AMENDED 2026-08-17 (DEF-210) — `email_past_due` and
    # `plan_notice_missed` were the examples here and both now HAVE a palette
    # (PO: *"please define it for this product"*).
    assert rows["email_past_due"]["catalog_unavailable"] is None
    assert rows["plan_notice_missed"]["catalog_unavailable"] is None
    # ⚠ INVERTED 2026-08-18 (CR-011 item 9) — both contracts have palettes now.
    assert rows["contract_service_agreement"]["catalog_unavailable"] is None
    assert rows["contract_deposit"]["catalog_unavailable"] is None
    assert all(row["catalog_unavailable"] is None for row in response.data["results"])
    assert catalogs.CLASSES_WITHOUT_CATALOG == {}, (
        "a class landed with no palette — this row's reason must be served, not null"
    )
    # PO 2026-08-16 — S91-S96 are CUT, so nothing here is writable.
    assert response.data["designer_cut_in_r2"] is True
    assert all(row["writable"] is False for row in response.data["results"])


def test_bills_and_statements_are_not_listed_here(brazos, dana):
    """B2 r10 #4: bills and statements pin `bill_templates`, a DIFFERENT
    registry with its own chooser (S8 → Bill layout, US-BIL-021). Listing them
    here would give one document two homes and two published pointers."""
    with tenant_ctx(brazos):
        response = _get(api.notification_templates, brazos, dana)
    codes = {row["code"] for row in response.data["results"]}
    assert codes.isdisjoint({"bill_residential", "bill_commercial", "statement"})


@pytest.mark.isolation
def test_another_tenants_config_is_never_reachable(brazos, dana, lonestar, erin):
    """CLAUDE.md rule 1 / HR-1. Each tenant's row is its own; a read entered in
    one context can never return the other's send window."""
    with tenant_ctx(brazos):
        api_call(
            api.notification_settings,
            "patch",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data={"dispatch_batch_size": 250},
        )
    with tenant_ctx(lonestar):
        theirs = _get(api.notification_settings, lonestar, erin)
    assert theirs.data["dispatch_batch_size"] == 500  # their own default, not 250


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004@3c1f8ab (ships with apps/notifications/settings_api.py — the same sources)
# generated: 2026-08-16 by story-coder (surface-debt tails lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — all three paths answered Resolver404 before
#         config/urls.py named the module, and the BR-NOT-008 assertion was run
#         against a TONE_TO_STEP mapping `firm` to the dunning class and failed
#         verbatim; transcripts in the lane report
# exceptions: (1) `test_us_not_010_tc3` asserts the XOR of a day list and a
#         reason rather than a fixed 7/14/30: those are SEEDS of a tenant
#         setting and pinning them here would re-introduce the constant the rule
#         forbids.
#         (2) The template test asserts a LIVE GAP (DEF-163). It is written as
#         an assertion rather than an xfail because the reporting is the
#         behaviour: the day a seeder lands, this test tells whoever wrote it
#         that the read must now carry a version.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
