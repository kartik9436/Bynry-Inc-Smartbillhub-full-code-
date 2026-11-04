# ── Trace ──────────────────────────────────────────────
# Component: W0 migrations lane tests — model/constraint halves of the W0 stories,
#            run against the sqlite test DB (migrations applied by pytest-django).
#            RLS / partitioning / trigger assertions CANNOT run on sqlite — they are
#            deliberately absent here and live in the G5 isolation suite (Postgres).
# ───────────────────────────────────────────────────────
"""Constraint tests for the W0 tables (tenancy · identity · audit).

Each test carries its US-ID + TC number and exercises the TABLE half of that
TC: the uniqueness/shape law the migration must make structural. The service/
API/UI halves of the same TCs land with their story lanes.
"""

import uuid
from datetime import date

import pytest
from django.db import IntegrityError, transaction

from apps.audit.models import AuditLog
from apps.identity.models import Role, TenantMembership, User
from apps.tenancy.models import (
    HolidayCalendar,
    Job,
    NumberSeries,
    ReferenceSeedRun,
    Service,
    SubscriptionPlan,
    Tenant,
    TenantSettings,
    Uom,
    UserPreference,
)
from core.dbfields import uuid7

pytestmark = pytest.mark.django_db


@pytest.fixture()
def brazosbend():
    return Tenant.objects.create(name="Brazos Bend Utilities", subdomain="brazosbend")


@pytest.fixture()
def lonestarridge():
    return Tenant.objects.create(name="Lone Star Ridge Water Co-op", subdomain="lonestarridge")


def _user(tenant, email, name="Test User"):
    return User.objects.create(tenant=tenant, email=email, full_name=name)


# ── platform seeds (migrations 0001) ────────────────────────────────────────
def test_w0_seed_three_predefined_roles_exist():
    # A4 addendum / BR-IDN-008: exactly the 3 predefined platform roles.
    assert set(Role.objects.values_list("code", flat=True)) == {
        "system_admin",
        "billing_clerk",
        "executive",
    }


def test_w0_seed_ten_service_catalog_rows_exist():
    # r5 #1 / BR-RAT-024: the 10-service platform catalog.
    codes = list(Service.objects.order_by("sort").values_list("code", flat=True))
    assert codes == [
        "electric",
        "water",
        "gas",
        "sewer",
        "trash",
        "storm_water",
        "solar",
        "broadband",
        "thermal_heat",
        "battery",
    ]


# ── US-TEN-001 — tenants root (table half) ──────────────────────────────────
def test_us_ten_001_tc3__duplicate_subdomain_rejected(brazosbend):
    # TC-3 table half: `tenants.subdomain` is globally UNIQUE — the 409 the
    # service returns rides this constraint.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Tenant.objects.create(name="Impostor Utilities", subdomain="brazosbend")


def test_us_ten_001_tc1__provisioning_rows_shape(brazosbend):
    # TC-1 table half: subscription (trial default) + services enablement rows.
    # The catalog is seeded by tenancy migration 0005 (2026-08-10) — read it
    # rather than minting a duplicate `growth` (unique on code).
    plan = SubscriptionPlan.objects.get(code="growth")
    sub = brazosbend.subscription_set.create(plan=plan)
    assert sub.status == "trial"  # BR-TEN-014 default
    electric = Service.objects.get(code="electric")
    row = brazosbend.tenantservice_set.create(service=electric)
    assert row.enabled is True and row.disabled_at is None


# ── US-TEN-002 — seeding evidence ───────────────────────────────────────────
def test_us_ten_002_tc3__one_seed_run_record_per_list_per_version(brazosbend):
    # TC-3: re-run changes nothing — UNIQUE (tenant, list_code, fixture_version).
    ReferenceSeedRun.objects.create(
        tenant=brazosbend, list_code="uoms", fixture_version="2026.08", seeded_count=6
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ReferenceSeedRun.objects.create(
                tenant=brazosbend, list_code="uoms", fixture_version="2026.08", seeded_count=6
            )


# ── US-TEN-005 / US-TEN-006 — company profile + settings row ────────────────
def test_us_ten_005_tc1__company_profile_fields_persist(brazosbend):
    # TC-1 table half: the §4 fixture values store and read back unchanged.
    brazosbend.legal_name = "Brazos Bend Utility District No. 1"
    brazosbend.dba_name = "Brazos Bend Utilities"
    brazosbend.ein = "743182640"  # stored digits; app-layer encryption = service lane
    brazosbend.remit_to_address = "PO Box 2210, Katy, TX 77492"
    brazosbend.brand_primary_hex = "#1B5E9E"
    brazosbend.save()
    saved = Tenant.objects.get(subdomain="brazosbend")
    assert saved.legal_name == "Brazos Bend Utility District No. 1"
    assert saved.brand_primary_hex == "#1B5E9E"


def test_us_ten_006_tc1__regional_fiscal_settings_row_is_one_to_one(brazosbend):
    # TC-1 table half (+ the 1:1 law): the §4 TX defaults persist; a second
    # settings row for the same tenant is impossible.
    TenantSettings.objects.create(
        tenant=brazosbend,
        timezone="America/Chicago",
        first_day_of_week="sunday",
        date_format="MM/DD/YYYY",
        fy_start_month=10,
        fy_start_day=1,
        accounting_method="accrual",
        close_cadence="monthly",
        lock_closed_periods=True,
    )
    assert TenantSettings.objects.get(tenant=brazosbend).timezone == "America/Chicago"
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            TenantSettings.objects.create(tenant=brazosbend)


# ── US-TEN-010 — lookup framework (UoM list) ────────────────────────────────
def test_us_ten_010_tc4__uom_duplicate_code_rejected_case_insensitively(brazosbend):
    # TC-4: add `KGAL` when `kgal` exists → case-insensitive duplicate rejected
    # (BR-TEN-030; UNIQUE (tenant, lower(code))).
    Uom.objects.create(tenant=brazosbend, code="kgal", name="Kilogallons")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Uom.objects.create(tenant=brazosbend, code="KGAL", name="Kilogallons again")


def test_us_ten_010_tc7__same_uom_code_allowed_in_another_tenant(brazosbend, lonestarridge):
    # TC-7 isolation table half: codes are unique PER TENANT.
    Uom.objects.create(tenant=brazosbend, code="kgal", name="Kilogallons")
    row = Uom.objects.create(tenant=lonestarridge, code="kgal", name="Kilogallons")
    assert row.pk is not None


# ── US-TEN-012 — number_series storage ──────────────────────────────────────
def test_us_ten_012_tc8__series_rows_are_per_tenant(brazosbend, lonestarridge):
    # TC-8: counters and formats are per-tenant — each tenant holds its own
    # `bill` row; a second `bill` row for the SAME tenant is impossible.
    NumberSeries.objects.create(
        tenant=brazosbend, series="bill", format="BL-{YY}{MM}-{000000}", next_number=18411
    )
    NumberSeries.objects.create(
        tenant=lonestarridge, series="bill", format="BL-{YY}{MM}-{000000}", next_number=1
    )
    assert NumberSeries.objects.filter(series="bill").count() == 2
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NumberSeries.objects.create(
                tenant=brazosbend, series="bill", format="BL-{YY}{MM}-{000000}"
            )


def test_us_ten_012_tc5__counter_below_one_rejected(brazosbend):
    # TC-5 table half: monotonic-from-1 check backs the forward-only law.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            NumberSeries.objects.create(
                tenant=brazosbend, series="account", format="AC-{YYYY}-{00000}", next_number=0
            )


# ── holiday calendar (S63 card, BR-TEN-039 / r5 #3) ─────────────────────────
def test_w0_holiday_date_unique_per_tenant(brazosbend, lonestarridge):
    HolidayCalendar.objects.create(
        tenant=brazosbend, holiday_date=date(2026, 7, 4), label="Independence Day"
    )
    HolidayCalendar.objects.create(
        tenant=lonestarridge, holiday_date=date(2026, 7, 4), label="Independence Day"
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            HolidayCalendar.objects.create(
                tenant=brazosbend, holiday_date=date(2026, 7, 4), label="July 4th again"
            )


# ── US-SHL-013 — user_preferences ───────────────────────────────────────────
def test_us_shl_013_tc3__preference_roundtrip_one_row_per_key(brazosbend):
    # TC-3 table half: write → read back; (tenant, user, key) is UNIQUE so the
    # PUT service is an upsert, never a duplicate.
    alex = _user(brazosbend, "alex@silvercreek.example", "Alex Reed")
    UserPreference.objects.create(
        tenant=brazosbend, user=alex, key="shell.sidebar_collapsed", value=True
    )
    stored = UserPreference.objects.get(tenant=brazosbend, user=alex, key="shell.sidebar_collapsed")
    assert stored.value is True
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserPreference.objects.create(
                tenant=brazosbend, user=alex, key="shell.sidebar_collapsed", value=False
            )


# ── US-SHL-004 — the bell's store ───────────────────────────────────────────
#
# ⚠ `test_us_shl_004_tc1__bell_events_store_and_list_newest_first` WAS HERE AND
# IS GONE WITH THE TABLE IT EXERCISED (DEF-3422, 2026-09-03). It created three
# `bell_events` rows and read them back newest-first, and it passed for three
# weeks over a bell that could never show anything: nothing in the product ever
# wrote that table, nothing read it, and nothing called the writer whose
# docstring named itself *"the only sanctioned writer"*. A test that supplies
# the missing link cannot see that the link is missing.
#
# The bell's store is `outbound_messages` + `in_app_messages`, and the case that
# stands in this one's place drives a REAL failure through the REAL provisioning
# job and reads the bell through the same call the shell makes:
# `06-backend/tests/test_def3422_bell_staff_alert.py`.


# ── BE-07 — jobs table backs the store contract ─────────────────────────────
def test_w0_jobs_one_active_job_per_scope_key(brazosbend):
    # NFR-16: the partial unique index refuses a second ACTIVE job with the
    # same (tenant, kind, scope_key) — core.jobs.enqueue's fold-in, DB-backed.
    Job.objects.create(tenant=brazosbend, kind="bill_run", scope_key="08-A|2026-08")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Job.objects.create(tenant=brazosbend, kind="bill_run", scope_key="08-A|2026-08")
    # A FINISHED job frees the scope key (condition covers queued/running only).
    Job.objects.filter(kind="bill_run").update(status="succeeded")
    replay = Job.objects.create(tenant=brazosbend, kind="bill_run", scope_key="08-A|2026-08")
    assert replay.status == "queued"


# ── US-IDN-004 / US-IDN-005 — per-tenant users ──────────────────────────────
def test_us_idn_005_tc3__duplicate_email_in_same_tenant_rejected(brazosbend):
    # TC-3: already a member → rejected (UNIQUE(tenant_id, email), BR-IDN-029);
    # case-insensitive per the citext/Lower() law.
    _user(brazosbend, "priya@silvercreek.example", "Priya Menon")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _user(brazosbend, "PRIYA@silvercreek.example", "Priya Again")


def test_us_idn_004_tc6__same_email_in_two_tenants_is_two_users(brazosbend, lonestarridge):
    # TC-6: two tenant-scoped user rows, no linkage (BR-IDN-029 / B2 r11).
    first = _user(brazosbend, "marcus@silvercreek.example", "Marcus (BB)")
    second = _user(lonestarridge, "marcus@silvercreek.example", "Marcus (LSR)")
    assert first.pk != second.pk
    assert User.objects.filter(email="marcus@silvercreek.example").count() == 2


def test_us_idn_004_tc1__membership_row_carries_role_status_last_active(brazosbend):
    # TC-1 table half: the list's columns exist per the §5 mapping — role via
    # role_id, status default `invited`, last_active_at null → "Never".
    tom = _user(brazosbend, "tom@silvercreek.example", "Tom Nguyen")
    membership = TenantMembership.objects.create(
        tenant=brazosbend, user=tom, role=Role.objects.get(code="billing_clerk")
    )
    assert membership.status == TenantMembership.STATUS_INVITED  # BR-IDN-011
    assert membership.last_active_at is None
    with pytest.raises(IntegrityError):  # r11: memberships are 1:1 per (tenant, user)
        with transaction.atomic():
            TenantMembership.objects.create(
                tenant=brazosbend, user=tom, role=Role.objects.get(code="executive")
            )


# ── US-AUD-001 — audit_log shape (sqlite half; partition/RLS = G5 suite) ────
def test_us_aud_001_tc2__trail_row_inserts_with_the_b2_shape(brazosbend):
    # TC-2 table half: a BR-TEN-016-shaped row lands with who/when/tenant/
    # entity/before→after. tenant_id is a bare uuid (BR-AUD-015 — no FK).
    row = AuditLog.objects.create(
        tenant_id=brazosbend.id,
        actor_user_id=uuid.uuid4(),
        action="billing_settings.updated",
        entity_type="billing_settings",
        entity_id=None,
        before={"late_grace_days": 10},
        after={"late_grace_days": 15},
    )
    assert row.created_at is not None  # stamped at insert — the "when"
    stored = AuditLog.objects.get(id=row.id)
    assert stored.before == {"late_grace_days": 10}
    assert stored.after == {"late_grace_days": 15}


def test_w0_uuid7_pks_are_time_ordered():
    # DB-2 / O-1 shim: uuidv7-style ids sort by creation time.
    first, second = uuid7(), uuid7()
    assert first.version == 7
    assert first.int >> 80 <= second.int >> 80  # 48-bit ms timestamp is monotonic-ish
