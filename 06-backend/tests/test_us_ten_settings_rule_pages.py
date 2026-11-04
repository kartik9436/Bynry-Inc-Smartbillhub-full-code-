# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (EP-TEN-07 SCOPE ADDENDUM — the S63–S71 Reference-data
#           rule-page cards; their own stories US-TEN-013..017 are allocated but
#           UNAUTHORED, so these tests are anchored on the addendum + 11b §2.3)
# Rules:    BR-BIL-001/002/008/021/029 + BR-PAY-010 + BR-CUS-050 (S66) ·
#           BR-BIL-017 (S69) · BR-PAY-013/016/017/018 (S70) · BR-PAY-019 +
#           BR-BIL-013/014/018 + BR-REP-022 (S71) · BR-TEN-016 (one audit row) ·
#           BR-TEN-024 (atomic per-page save) · BR-TEN-043 (event-time forward)
# Note:     A4 grants Settings "Full" to System Admin and "View" to Executive —
#           the view class admits both and the SERVICE guard refuses the
#           Executive's write (BR-SHL-025 defense in depth). RLS halves = G5.
# ⚠ S64 (read-validation) LEFT THIS FILE 2026-08-26 — CR-038 A1 re-homed the
#   surface to apps/metering (per-service rows the ENGINE reads; the family
#   document here was a second home whose edits never reached validation).
#   Its coverage — defaults at provisioning, TC-7 edit-changes-config+audit,
#   TC-8 refusals, TC-10 per-tenant isolation — moved WITH the surface to
#   tests/test_cr038_s64_service_settings.py, strengthened per service.
# ───────────────────────────────────────────────────────
"""The four S8 rule pages (S66 · S69 · S70 · S71) + the BR-TEN-019 logo."""

import pytest

from apps.tenancy import api, models, selectors, services, settings_families
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    audit_actions,
    clerk_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

# The four ratified tenancy endpoints (11b §2.3, minus S64 — see the Trace)
# with one legal edit each, chosen so the edit is a value the page's own rule
# allows a tenant to set.
PAGES = [
    ("billing-defaults", {"late_pct": "2.0"}, "late_pct", "2.0"),
    ("budget-billing", {"settle_up_month": 6}, "settle_up_month", 6),
    ("collections", {"reminder_days_after_due": 5}, "reminder_days_after_due", 5),
    ("finance-controls", {"dso_target_days": 21}, "dso_target_days", 21),
]
API_VIEWS = {
    "billing-defaults": api.billing_defaults_settings,
    "budget-billing": api.budget_billing_settings,
    "collections": api.collections_settings,
    "finance-controls": api.finance_controls_settings,
}


# ── seeded defaults: the DATABASE is the source, never a code constant ──────
def test_us_ten_009_tc1__every_rule_page_is_born_holding_its_ratified_defaults(
    growth_plan, identity_seam
):
    """BR-MET-020 (and BR-BIL-021's "all seeded, nothing hardcoded"): a freshly
    provisioned tenant already HAS the ratified values stored, so an engine
    reads config rather than falling back to a constant (US-MET-011 TC-9)."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        billing = selectors.settings_family("billing-defaults")
        budget = selectors.settings_family("budget-billing")
        collections = selectors.settings_family("collections")
        finance = selectors.settings_family("finance-controls")

    # (S64's defaults are asserted where the surface now lives —
    # tests/test_cr038_s64_service_settings.py, per service.)

    # S66 — BR-BIL-001 max($5, 1.5%) · BR-BIL-008 grace 5 calendar ·
    # BR-BIL-029 guardrail 200% · BR-PAY-010 oldest-invoice-first.
    assert (billing["late_pct"], billing["late_min_amount"]) == ("1.5", "5")
    assert (billing["late_grace_days"], billing["late_grace_mode"]) == (5, "calendar")
    assert billing["overcharge_guardrail_pct"] == "200"
    assert billing["allocation_order"] == "oldest_invoice_first"
    assert billing["deposit_interest_rate_annual"] == "0.000000"  # r9 #5, NUMERIC(18,6)
    # BR-BIL-021 names a tenant minimum-bill FALLBACK but ratifies no value —
    # UNSET, never 0 (BR-RAT-028: NULL means none).
    assert billing["minimum_bill_amount"] is None

    # S69 — BR-BIL-017 (OQ-068 CLOSED).
    assert budget["eligibility_months"] == 12
    assert budget["level_rounding"] == "whole_dollar"
    assert (budget["relevel_drift_pct"], budget["relevel_cadence_months"]) == ("20", 6)
    assert budget["drop_off_missed_payments"] == 2
    assert budget["override_bound_pct"] == "30"
    assert budget["settle_up_month"] is None  # rule names it, ratifies no month

    # S70 — BR-PAY-017 ladder + BR-PAY-016 plan notices + BR-PAY-013/018.
    assert collections["reminder_days_after_due"] == 3
    assert collections["notice_tier_days"] == [10, 5]
    assert collections["final_notice_hours"] == 48
    assert collections["plan_reminder_days_before"] == 3
    assert collections["plan_missed_notice_days_after"] == 1
    assert collections["plan_void_after_misses"] == 2
    assert collections["nsf_privilege_n"] == 2
    assert collections["suppress_paper_on_bad_address"] is True

    # S71 — BR-PAY-019 ±3d · BR-BIL-013 $5 · BR-REP-022 15d · BR-BIL-014/018.
    assert finance["bank_match_date_tolerance_days"] == 3
    assert finance["write_off_threshold_amount"] == "5"
    assert finance["dso_target_days"] == 15
    assert finance["correction_approval_mode"] == "all"
    assert (finance["back_bill_cap_months"], finance["back_bill_theft_exempt"]) == (12, True)


# ── round-trip + exactly one audit row (BR-TEN-024/016) ─────────────────────
@pytest.mark.parametrize("slug,change,key,expected", PAGES)
def test_us_ten_009_tc4__each_family_round_trips_with_one_audit_row(
    growth_plan, identity_seam, audit_rows, slug, change, key, expected
):
    tenant, _ = provisioned_tenant()
    audit_rows.clear()
    actor = admin_actor()
    with tenant_ctx(tenant):
        saved = services.save_settings_family(actor, slug, change)
        read_back = selectors.settings_family(slug)
    assert saved[key] == expected and read_back[key] == expected
    family = settings_families.FAMILIES[slug]
    rows = [row for row in audit_rows if row["action"] == family.audit_action]
    assert len(rows) == 1  # BR-TEN-024: whole page = ONE audit row
    assert rows[0]["actor_user_id"] == actor.id
    assert rows[0]["after"]["page"] == family.screen
    assert rows[0]["after"][key] == expected
    assert key in rows[0]["before"]  # before/after diff, BR-AUD-003
    # untouched parameters keep their ratified defaults — a partial PUT is not
    # a truncating PUT (BR-TEN-024 stages the whole page, saves it atomically)
    assert len(read_back) == len(family.params)


def test_us_ten_009_tc4__a_no_op_save_writes_nothing_and_audits_nothing(
    growth_plan, identity_seam, audit_rows
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        current = selectors.settings_family("collections")
        audit_rows.clear()
        services.save_settings_family(admin_actor(), "collections", current)
    assert audit_actions(audit_rows) == []


# (US-MET-011 TC-7/TC-8 — the S64 config API — moved with the surface to
# tests/test_cr038_s64_service_settings.py, CR-038 A1.)


# ── unknown fields, unknown pages, unratified choices ───────────────────────
@pytest.mark.parametrize("slug,_change,_key,_expected", PAGES)
def test_us_ten_010_tc5__unknown_parameters_are_refused_not_ignored(
    growth_plan, identity_seam, slug, _change, _key, _expected
):
    """A typo that silently does nothing is how a threshold quietly stays at
    its old value — every unknown key is a 422 naming the field."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_settings_family(admin_actor(), slug, {"not_a_parameter": 1})
    assert excinfo.value.field_errors[0]["field"] == "not_a_parameter"
    assert excinfo.value.field_errors[0]["message_key"] == "settings.unknown_field"


def test_us_ten_009_tc1__an_unknown_rule_page_is_404_never_a_guessed_page(
    growth_plan, identity_seam
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.NotFoundError):
            selectors.settings_family("no-such-page")
        with pytest.raises(errors.NotFoundError):
            services.save_settings_family(admin_actor(), "no-such-page", {})


@pytest.mark.parametrize(
    "slug,payload,field",
    [
        # BR-PAY-010 confirms the DEFAULT order and B4 §Payments still carries a
        # PLACEHOLDER for the alternatives — a second value would be a guess.
        ("billing-defaults", {"allocation_order": "newest_invoice_first"}, "allocation_order"),
        # BR-BIL-014 (OQ-072 CLOSED): v1 is ALL corrections; threshold mode is v2.
        ("finance-controls", {"correction_approval_mode": "threshold"}, "correction_approval_mode"),
        # BR-BIL-017 ratifies whole-dollar levels only.
        ("budget-billing", {"level_rounding": "nearest_ten"}, "level_rounding"),
    ],
)
def test_us_ten_010_tc5__values_no_rule_ratifies_are_refused(
    growth_plan, identity_seam, slug, payload, field
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_settings_family(admin_actor(), slug, payload)
    error = next(fe for fe in excinfo.value.field_errors if fe["field"] == field)
    assert error["code"] == errors.VAL_UNKNOWN_LOOKUP
    assert error["params"]["allowed"]  # the refusal names what IS ratified


# ── per-family bounds the rules state in words ──────────────────────────────
@pytest.mark.parametrize(
    "slug,payload,field",
    [
        # BR-BIL-013 / OQ-070: write-off threshold is tenant-config 0–50.
        ("finance-controls", {"write_off_threshold_amount": "75"}, "write_off_threshold_amount"),
        # BR-BIL-008: grace is configurable 0–30.
        ("billing-defaults", {"late_grace_days": 45}, "late_grace_days"),
        # BR-PAY-017: the ladder escalates — tiers must strictly descend.
        ("collections", {"notice_tier_days": [5, 10]}, "notice_tier_days"),
        # BR-BIL-017: a settle-up month is a month.
        ("budget-billing", {"settle_up_month": 13}, "settle_up_month"),
    ],
)
def test_us_ten_010_tc5__out_of_bound_values_are_refused(
    growth_plan, identity_seam, slug, payload, field
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_settings_family(admin_actor(), slug, payload)
    assert any(fe["field"] == field for fe in excinfo.value.field_errors)


def test_us_ten_009_tc1__decimal_parameters_never_become_floats(growth_plan, identity_seam):
    """CLAUDE.md rule 2: money and rates are NUMERIC/Decimal, never binary
    floats. Every decimal parameter crosses the wire and the jsonb document as
    a canonical decimal STRING."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_settings_family(
            admin_actor(), "billing-defaults", {"late_min_amount": 7.25, "late_pct": "1.75"}
        )
        billing = selectors.settings_family("billing-defaults")
    stored = models.TenantSettings.objects.get(tenant=tenant).billing_defaults
    assert billing["late_min_amount"] == "7.25" and billing["late_pct"] == "1.75"
    assert isinstance(stored["late_min_amount"], str)
    assert not any(isinstance(value, float) for value in stored.values())


def test_us_ten_009_tc1__s66_reuses_the_typed_columns_it_already_had(growth_plan, identity_seam):
    """Storage choice: `late_grace_mode`/`late_grace_days` (B2 header late-fee
    settings) and `deposit_interest_rate_annual` (r9 #5, tagged S66) already
    existed as typed columns and STAY the source of truth — the S66 page
    surfaces them, it does not shadow them into jsonb."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_settings_family(
            admin_actor(),
            "billing-defaults",
            {
                "late_grace_days": 10,
                "late_grace_mode": "business",
                "deposit_interest_rate_annual": "1.5",
            },
        )
    row = models.TenantSettings.objects.get(tenant=tenant)
    assert row.late_grace_days == 10 and row.late_grace_mode == "business"
    assert str(row.deposit_interest_rate_annual) == "1.500000"
    assert "late_grace_days" not in row.billing_defaults  # no second home
    assert "deposit_interest_rate_annual" not in row.billing_defaults


# ── roles (A4) and tenant isolation ─────────────────────────────────────────
@pytest.mark.parametrize("slug,change,key,expected", PAGES)
def test_us_ten_009_tc5__executive_reads_admin_writes_clerk_denied(
    growth_plan, identity_seam, slug, change, key, expected
):
    """A4 "Settings & lookup tables: Full / — / View": the Executive may read a
    rule page and may NOT save it; the Billing Clerk sees neither."""
    tenant, _ = provisioned_tenant()
    view = API_VIEWS[slug]
    clerk_get = api_call(view, "get", user=FakeUser(), role="billing_clerk", tenant=tenant)
    exec_get = api_call(view, "get", user=FakeUser(), role="executive", tenant=tenant)
    exec_put = api_call(view, "put", user=FakeUser(), role="executive", tenant=tenant, data=change)
    admin_put = api_call(
        view, "put", user=FakeUser(), role="system_admin", tenant=tenant, data=change
    )
    assert clerk_get.status_code == 403 and clerk_get.data["code"] == "AUTH-002"
    assert exec_get.status_code == 200 and key in exec_get.data
    assert exec_put.status_code == 403 and exec_put.data["code"] == "AUTH-002"
    assert admin_put.status_code == 200 and admin_put.data[key] == expected


@pytest.mark.parametrize("slug,change,key,expected", PAGES)
def test_us_ten_009_tc5__the_service_guard_refuses_a_clerk_even_off_the_api(
    growth_plan, identity_seam, slug, change, key, expected
):
    """BR-SHL-025: the service refuses no matter which caller forgot to gate."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.AuthError) as excinfo:
            services.save_settings_family(clerk_actor(), slug, change)
    assert excinfo.value.code == errors.AUTH_PERMISSION_DENIED


def test_us_ten_009_tc6__rule_page_values_are_per_tenant(growth_plan, identity_seam):
    """Lone Star Ridge sets reminder day 5, Brazos Bend keeps 3 — a rule page's
    value is the tenant's own. (S64's per-tenant proof moved with its surface —
    tests/test_cr038_s64_service_settings.py.)"""
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(lonestar):
        services.save_settings_family(admin_actor(), "collections", {"reminder_days_after_due": 5})
    with tenant_ctx(brazos):
        assert selectors.settings_family("collections")["reminder_days_after_due"] == 3
    with tenant_ctx(lonestar):
        assert selectors.settings_family("collections")["reminder_days_after_due"] == 5
    # (RLS FORCE half of this TC = G5 isolation suite on live Postgres)


def test_us_ten_009_tc4__api_get_then_put_is_the_shape_the_frontend_integrates(
    growth_plan, identity_seam
):
    """The wire shape: a FLAT document per page, same keys in and out."""
    tenant, _ = provisioned_tenant()
    read = api_call(
        api.collections_settings, "get", user=FakeUser(), role="system_admin", tenant=tenant
    )
    saved = api_call(
        api.collections_settings,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"notice_tier_days": [14, 7, 3], "nsf_privilege_n": 3},
    )
    assert read.status_code == 200
    assert set(read.data) == {p.key for p in settings_families.COLLECTIONS.params}
    assert saved.status_code == 200
    assert saved.data["notice_tier_days"] == [14, 7, 3]
    assert saved.data["nsf_privilege_n"] == 3
    assert saved.data["suppress_paper_on_bad_address"] is True  # untouched, still there
