# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 S1 · S2 · S3 (templates redesign, PO 2026-10-29)
# Rules:    A1 C · A3 A · A4 B (decision log 2026-10-29, "twelve questions") ·
#           BR-BIL-026 · BR-BIL-027 · BR-NOT-006 · CLAUDE.md rules 1, 4, 7
# Tests:    this file
# ───────────────────────────────────────────────────────
"""+ New variant, Duplicate as variant, Make live again — and the category axis.

Read `test_make_live_again_writes_a_new_version_and_history_keeps_every_wording`
first: it is the PO's drawing 08 in numbers — *"v1 goes out from now. v3 stays
in history."* — and it proves the three things that make the action safe: the
copy is a NEW row, the version it replaces is untouched, and History returns each
version's OWN stored wording rather than today's.
"""

from __future__ import annotations

import pytest

from apps.notifications import customers_seam, models, services
from apps.notifications import template_models as tm
from apps.notifications import template_service, template_variants, templates_api
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import audit_actions, make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

CODE = "dunning"
BODY_V2 = (
    "Hi {first_name}, your account {account} still shows a balance of {balance}. "
    "Please pay online at any time. Thank you."
)


def _post(view, tenant, actor, data, role="system_admin", **kwargs):
    return api_call(
        view, "post", user=getattr(actor, "user", None), role=role, tenant=tenant, data=data,
        **kwargs,
    )


def _get(view, tenant, actor, role="system_admin", **kwargs):
    return api_call(view, "get", user=getattr(actor, "user", None), role=role, tenant=tenant, **kwargs)


def _default_variant():
    from core import tenancy as core_tenancy  # noqa: PLC0415

    return tm.NotificationTemplate.objects.get(
        tenant_id=core_tenancy.current_tenant_id(),
        code=CODE,
        category=tm.VARIANT_DEFAULT,
        language=tm.VARIANT_DEFAULT,
    )


def _live(variant):
    return tm.NotificationTemplateVersion.objects.get(
        template=variant, status=tm.VERSION_PUBLISHED
    )


def _key(response):
    return (response.data.get("error") or response.data).get("message_key")


# ══════════════════════════════════════════════════════════════════════════
# S2 — + NEW VARIANT / DUPLICATE AS VARIANT
# ══════════════════════════════════════════════════════════════════════════
def test_routes_resolve_through_the_root_urlconf():
    from django.urls import resolve

    base = "/api/brazosbend/template-catalog/dunning"
    assert resolve(f"{base}/variant-options").func is templates_api.variant_options
    assert resolve(f"{base}/new-variant").func is templates_api.create_variant
    assert resolve(f"{base}/make-live-again").func is templates_api.make_live_again


def test_new_variant_is_a_draft_holding_the_published_wording(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        published = _live(_default_variant())
    response = _post(
        templates_api.create_variant, brazos, dana,
        {"channel": "pdf_print", "language": "default", "category": "commercial",
         "start_from": "published"},
        code=CODE,
    )
    assert response.status_code == 201, response.data
    assert response.data["variant"]["category"] == "commercial"
    assert response.data["variant"]["language"] == tm.VARIANT_DEFAULT
    assert response.data["version"]["status"] == tm.VERSION_DRAFT
    assert response.data["version"]["body"] == published.body
    assert response.data["started_from_version"] == published.version
    with tenant_ctx(brazos):
        # Nothing was published: the commercial variant has no live version, so
        # resolution for a commercial account still lands on All customers.
        resolved = template_service.resolve(code=CODE, category="commercial")
        assert resolved.template_id == published.template_id
    assert template_variants.AUDIT_VARIANT_CREATED in audit_actions(audit_rows)


def test_the_same_combination_twice_is_refused_by_name(brazos, dana):
    payload = {"language": "default", "category": "commercial", "start_from": "blank"}
    first = _post(templates_api.create_variant, brazos, dana, payload, code=CODE)
    assert first.status_code == 201
    assert first.data["version"] is None  # blank: nothing written yet
    second = _post(templates_api.create_variant, brazos, dana, payload, code=CODE)
    assert second.status_code in (400, 409, 422)
    assert _key(second) == template_variants.KEY_EXISTS
    # The All-customers variant in the utility's language already exists too —
    # sending the utility's own tag is the SAME combination, not a new one.
    with tenant_ctx(brazos):
        own = template_variants.utility_language()
    if own:
        third = _post(
            templates_api.create_variant, brazos, dana,
            {"language": own, "category": "default", "start_from": "blank"}, code=CODE,
        )
        assert _key(third) == template_variants.KEY_EXISTS


def test_a_language_the_utility_has_not_switched_on_is_refused(brazos, dana, monkeypatch):
    refused = _post(
        templates_api.create_variant, brazos, dana,
        {"language": "ja-JP", "category": "default", "start_from": "published"}, code=CODE,
    )
    assert _key(refused) == template_variants.KEY_LANGUAGE_NOT_ON
    # A4 B as built: a language one of the utility's customers has chosen is ON.
    monkeypatch.setattr(customers_seam, "preferred_languages_in_use", lambda: ("es",))
    options = _get(templates_api.variant_options, brazos, dana, code=CODE)
    assert "es" in {row["value"] for row in options.data["languages"]}
    assert "ja-JP" not in {row["value"] for row in options.data["languages"]}
    made = _post(
        templates_api.create_variant, brazos, dana,
        {"language": "es", "category": "commercial", "start_from": "published"}, code=CODE,
    )
    assert made.status_code == 201, made.data
    assert made.data["variant"]["language"] == "es"


def test_a_category_the_utility_does_not_have_and_a_wrong_channel_are_refused(brazos, dana):
    unknown = _post(
        templates_api.create_variant, brazos, dana,
        {"language": "default", "category": "low_income", "start_from": "blank"}, code=CODE,
    )
    assert _key(unknown) == template_variants.KEY_CATEGORY_UNKNOWN
    wrong = _post(
        templates_api.create_variant, brazos, dana,
        {"channel": "sms", "language": "default", "category": "commercial"}, code=CODE,
    )
    assert _key(wrong) == template_variants.KEY_CHANNEL_MISMATCH


def test_variant_options_serve_all_customers_then_the_utilitys_own_classes(brazos, dana):
    response = _get(templates_api.variant_options, brazos, dana, code=CODE)
    assert response.status_code == 200
    categories = response.data["categories"]
    assert categories[0] == {"value": "default", "label": "All customers"}
    assert "residential" in {row["value"] for row in categories}
    assert response.data["languages"][0]["value"] == "default"
    assert response.data["needs_approval"] is False
    assert ("default", "default") in {
        (row["category"], row["language"]) for row in response.data["taken"]
    }


def test_duplicate_as_variant_copies_the_named_variant(brazos, dana):
    with tenant_ctx(brazos):
        source = _default_variant()
        live = _live(source)
    response = _post(
        templates_api.create_variant, brazos, dana,
        {"language": "default", "category": "residential", "start_from": "variant",
         "source_variant": str(source.pk)},
        code=CODE,
    )
    assert response.status_code == 201, response.data
    assert response.data["version"]["body"] == live.body


def test_a_billing_clerk_cannot_create_a_variant_or_make_one_live(brazos, marcus):
    created = _post(
        templates_api.create_variant, brazos, marcus,
        {"language": "default", "category": "commercial"}, role="billing_clerk", code=CODE,
    )
    assert created.status_code == 403
    with tenant_ctx(brazos):
        live = _live(_default_variant())
    made = _post(
        templates_api.make_live_again, brazos, marcus, {"version_id": str(live.pk)},
        role="billing_clerk", code=CODE,
    )
    assert made.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
# S3 — MAKE LIVE AGAIN
# ══════════════════════════════════════════════════════════════════════════
def _second_version(brazos, dana):
    """v1 (seeded, published) → v2 typed and published; v1 is now archived."""
    with tenant_ctx(brazos):
        variant = _default_variant()
        v1 = _live(variant)
        v2 = template_service.save_draft(template=variant, body=BODY_V2, actor=dana)
        template_service.publish(version_row=v2, actor=dana)
        v1.refresh_from_db()
    return variant, v1, v2


def test_make_live_again_writes_a_new_version_and_history_keeps_every_wording(
    brazos, dana, audit_rows
):
    variant, v1, v2 = _second_version(brazos, dana)
    assert v1.status == tm.VERSION_ARCHIVED
    response = _post(
        templates_api.make_live_again, brazos, dana, {"version_id": str(v1.pk)}, code=CODE
    )
    assert response.status_code == 201, response.data
    assert response.data["outcome"] == template_variants.OUTCOME_LIVE
    assert response.data["restored_from_version"] == v1.version
    assert response.data["replaced_version"] == v2.version
    new = response.data["version"]
    assert new["version"] == v2.version + 1
    assert new["status"] == tm.VERSION_PUBLISHED
    assert new["body"] == v1.body
    assert new["restored_from_version"] == v1.version
    with tenant_ctx(brazos):
        v1_after = tm.NotificationTemplateVersion.objects.get(pk=v1.pk)
        v2_after = tm.NotificationTemplateVersion.objects.get(pk=v2.pk)
        # The old rows are untouched: v1 keeps its own first publish date, v2
        # "stays in history" archived, and new messages resolve to the copy.
        assert (v1_after.status, v1_after.published_at) == (tm.VERSION_ARCHIVED, v1.published_at)
        assert v2_after.status == tm.VERSION_ARCHIVED and v2_after.body == BODY_V2
        assert template_service.resolve(code=CODE).version == new["version"]
    assert template_variants.AUDIT_MADE_LIVE_AGAIN in audit_actions(audit_rows)
    # History returns each version's OWN stored wording, for its preview.
    detail = _get(templates_api.template_detail, brazos, dana, code=CODE,
                  query={"variant": str(variant.pk)})
    by_number = {row["version"]: row for row in detail.data["versions"]}
    assert by_number[v2.version]["body"] == BODY_V2
    assert by_number[v1.version]["body"] == v1.body
    assert by_number[v2.version]["can_make_live_again"] is True
    assert by_number[new["version"]]["can_make_live_again"] is False


def test_make_live_again_refuses_the_live_version_and_one_never_published(brazos, dana):
    variant, _v1, v2 = _second_version(brazos, dana)
    live = _post(templates_api.make_live_again, brazos, dana, {"version_id": str(v2.pk)}, code=CODE)
    assert _key(live) == template_variants.KEY_ALREADY_LIVE
    with tenant_ctx(brazos):
        draft = template_service.save_draft(template=variant, body=BODY_V2 + " Draft.", actor=dana)
    never = _post(
        templates_api.make_live_again, brazos, dana, {"version_id": str(draft.pk)}, code=CODE
    )
    assert _key(never) == template_variants.KEY_NOT_EARLIER_PUBLISHED


def test_a_legal_notice_is_sent_for_approval_instead(brazos, dana, monkeypatch):
    """A1 C — the copy is a DRAFT and the version going out keeps going out."""
    assert template_variants.is_legal_notice("disconnect_notice_10_day") is True
    assert template_variants.is_legal_notice(CODE) is False
    _variant, v1, v2 = _second_version(brazos, dana)
    monkeypatch.setattr(template_variants, "is_legal_notice", lambda code: True)
    response = _post(
        templates_api.make_live_again, brazos, dana, {"version_id": str(v1.pk)}, code=CODE
    )
    assert response.status_code == 201, response.data
    assert response.data["outcome"] == template_variants.OUTCOME_SENT_FOR_APPROVAL
    assert response.data["version"]["status"] == tm.VERSION_DRAFT
    assert response.data["replaced_version"] is None
    with tenant_ctx(brazos):
        assert template_service.resolve(code=CODE).version == v2.version


def test_another_utility_can_neither_see_nor_restore_this_ones_version(brazos, dana, lonestar, erin):
    _variant, v1, _v2 = _second_version(brazos, dana)
    response = _post(
        templates_api.make_live_again, lonestar, erin, {"version_id": str(v1.pk)}, code=CODE
    )
    assert response.status_code in (400, 404, 422)
    with tenant_ctx(brazos):
        assert tm.NotificationTemplateVersion.objects.filter(template=_variant).count() == 2


# ══════════════════════════════════════════════════════════════════════════
# S1 — THE CATEGORY AXIS AT QUEUE TIME, AND THE LADDER
# ══════════════════════════════════════════════════════════════════════════
def _account(tenant, actor, type_code, account_no):
    """A real account of one customer class — the shape `test_cr048_a1` uses."""
    from apps.customers import models as customer_models  # noqa: PLC0415

    premises = make_premises(actor, address_line=f"{account_no} Cedar Bayou Rd")
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.get(tenant=tenant, code=type_code),
        account_no=account_no,
    )


def test_queue_time_resolution_picks_the_accounts_category_variant(brazos, dana):
    """End to end through the real customers read: the writer names only the
    account, and the pin is the account's class variant — or All customers."""
    with tenant_ctx(brazos):
        base = _live(_default_variant())
        commercial, _ = template_service.register(
            code=CODE, name="Past-due (commercial)", actor=dana, category="commercial"
        )
        draft = template_service.save_draft(template=commercial, body=BODY_V2, actor=dana)
        template_service.publish(version_row=draft, actor=dana)
        shop = _account(brazos, dana, "commercial", "ACC-1991")
        home = _account(brazos, dana, "residential", "ACC-1992")
        assert customers_seam.account_category(shop.pk) == "commercial"
        rows = {}
        for account, source in ((shop, "c199"), (home, "c19a")):
            write = services.queue_document(
                source_type="payment",
                source_id=f"0197b0a0-0000-7000-8000-00000000{source}",
                channels=(models.CHANNEL_PRINT,),
                template=services.TemplatePin(code=CODE),
                account_id=account.pk,
                actor=dana,
            )
            rows[account.account_no] = models.OutboundMessage.objects.get(pk=write.messages[0].id)
        assert (rows["ACC-1991"].template_id, rows["ACC-1991"].template_version) == (
            commercial.pk,
            draft.version,
        )
        # Residential has no wording of its own: All customers, exactly as before.
        assert (rows["ACC-1992"].template_id, rows["ACC-1992"].template_version) == (
            base.template_id,
            base.version,
        )


def test_the_customers_language_beats_a_closer_category_match(brazos, dana):
    """Rosa — residential, Español — gets the All-customers SPANISH wording, not
    the residential English one (ruling B; ladder reordered 2026-10-29)."""
    with tenant_ctx(brazos):
        residential, _ = template_service.register(
            code=CODE, name="Residential", actor=dana, category="residential"
        )
        spanish, _ = template_service.register(code=CODE, name="Español", actor=dana, language="es")
        # (the platform may already have seeded an Español variant; `register`
        # is idempotent and a newly published draft makes it ours either way)
        for variant in (residential, spanish):
            draft = template_service.save_draft(template=variant, body=BODY_V2, actor=dana)
            template_service.publish(version_row=draft, actor=dana)
        rosa = template_service.resolve(code=CODE, category="residential", language="es")
        assert (rosa.template_id, rosa.via) == (spanish.pk, template_service.VIA_CATEGORY_FALLBACK)
        english = template_service.resolve(code=CODE, category="residential", language="nl-NL")
        assert (english.template_id, english.via) == (
            residential.pk,
            template_service.VIA_LANGUAGE_FALLBACK,
        )


def test_the_seam_reads_no_category_for_an_unknown_or_malformed_account(brazos):
    with tenant_ctx(brazos):
        assert customers_seam.account_category("0197b0a0-0000-7000-8000-00000000ffff") is None
        assert customers_seam.account_category("not-a-uuid") is None
        assert customers_seam.account_category(None) is None
