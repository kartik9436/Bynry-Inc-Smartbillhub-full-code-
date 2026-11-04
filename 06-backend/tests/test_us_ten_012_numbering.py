# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-012 (number formats per series — prefix · next-number ·
#           preview; the live number_series storage behind the BE-06 kernel)
# Rules:    BR-TEN-016 · BR-TEN-024 · BR-TEN-033 (templates panel nav-only) ·
#           BR-TEN-035 (grammar, in-txn allocation, gaps ok, forward-only) ·
#           BR-TEN-043 (issue date is an input, never the wall clock)
# Note:     TC-6's true concurrency (row lock, no deadlock) needs live Postgres
#           — sequential allocation proven here, the lock semantics ride the
#           G5/Postgres tier. Sink registered by apps.py ready() (BE-06).
# ───────────────────────────────────────────────────────
"""US-TEN-012 — number series settings + the SELECT-FOR-UPDATE allocator."""

from datetime import date

import pytest
from django.db import transaction

from apps.tenancy import api, models, services
from core import errors
from core import numbering as core_numbering

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

ISSUE_DATE = date(2026, 8, 8)  # §4: issue date, tenant timezone America/Chicago


@pytest.fixture(autouse=True)
def series_sink():
    """apps.py ready() registers this once per process; other test modules may
    have cleared it (BE-06 unit tests) — re-register for this module."""
    core_numbering.set_series_sink(services.allocate_series_number)
    yield
    core_numbering.set_series_sink(services.allocate_series_number)


def test_us_ten_012_tc1__allocation_inside_issuing_transaction(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "bill", next_number=18410)
        with transaction.atomic():  # the issuing transaction (BR-TEN-035)
            number = core_numbering.next_number("bill", ISSUE_DATE)
    assert number == "BL-2608-018410"
    row = models.NumberSeries.objects.get(tenant=tenant, series="bill")
    assert row.next_number == 18411  # counter advanced
    assert row.format == "BL-{YY}{MM}-{000000}"  # format untouched


def test_us_ten_012_tc2__format_change_is_future_only(growth_plan, identity_seam, audit_rows):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "bill", next_number=18411)
        audit_rows.clear()
        result = services.save_number_series(
            admin_actor(), "bill", format_string="BBU-{YYYY}{MM}-{000000}"
        )
        assert result["next_number"] == 18411  # counter NOT reset by a format edit
        with transaction.atomic():
            number = core_numbering.next_number("bill", ISSUE_DATE)
    assert number == "BBU-202608-018411"  # the NEXT issued number uses it
    saves = [r for r in audit_rows if r["action"] == "settings.numbering.updated"]
    assert saves[0]["before"]["format"] == "BL-{YY}{MM}-{000000}"  # before/after kept
    assert saves[0]["after"]["format"] == "BBU-{YYYY}{MM}-{000000}"
    # issued numbers are strings stamped on immutable rows elsewhere; this module
    # exposes NO renumber/reformat API by design (BR-TEN-035)
    assert not hasattr(services, "renumber_series")


def test_us_ten_012_tc3__next_number_forward_edit_allowed(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "account", next_number=568)
        result = services.save_number_series(admin_actor(), "account", next_number=1000)
        assert result["next_number"] == 1000
        with transaction.atomic():
            number = core_numbering.next_number("account", date(2026, 8, 8))
    assert number == "AC-2026-01000"


@pytest.mark.parametrize(
    "bad_format,problem",
    [
        ("BL-{YY}{MM}", "no_sequence_token"),
        ("BL-{000}-{000}", "multiple_sequence_tokens"),
        ("BL-{QQ}-{000}", "unknown_token"),
    ],
)
def test_us_ten_012_tc4__malformed_format_rejected_with_specific_problem(
    growth_plan, identity_seam, bad_format, problem
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_number_series(admin_actor(), "bill", format_string=bad_format)
    assert excinfo.value.params["problem"] == problem  # BR-TEN-035 grammar
    row = models.NumberSeries.objects.get(tenant=tenant, series="bill")
    assert row.format == "BL-{YY}{MM}-{000000}"  # save blocked


def test_us_ten_012_tc5__backward_counter_edit_rejected(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        services.save_number_series(admin_actor(), "bill", next_number=18411)
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_number_series(admin_actor(), "bill", next_number=500)
    assert excinfo.value.code == errors.VAL_RANGE
    assert excinfo.value.params == {"min": 18411}  # "must be ≥ 18,411"


def test_us_ten_012_tc6__sequential_allocations_are_distinct_and_gapless_here(
    growth_plan, identity_seam
):
    """sqlite half of TC-6: two issuances get distinct sequential numbers. The
    concurrent row-lock/no-deadlock half needs live Postgres (G5 tier)."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with transaction.atomic():
            first = core_numbering.next_number("payment", ISSUE_DATE)
            second = core_numbering.next_number("payment", ISSUE_DATE)
    assert (first, second) == ("PY-260808-0001", "PY-260808-0002")


def test_us_ten_012_tc8__series_counters_and_formats_are_per_tenant(growth_plan, identity_seam):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(brazos):
        services.save_number_series(admin_actor(), "bill", next_number=18411)
        with transaction.atomic():
            core_numbering.next_number("bill", ISSUE_DATE)
    with tenant_ctx(lonestar):
        with transaction.atomic():
            first_lonestar = core_numbering.next_number("bill", ISSUE_DATE)
    assert first_lonestar == "BL-2608-000001"  # own counter, default format
    assert models.NumberSeries.objects.get(tenant=brazos, series="bill").next_number == 18412


def test_us_ten_012_tc1b__unknown_series_or_missing_row_refuses_loudly(growth_plan, identity_seam):
    """⚠ AMENDED BY CR-005, 2026-08-17 — and the amendment IS the change.

    This case used to prove that `deposit_batch` REFUSED, because BR-TEN-041's
    DEP-/RCT-/EXP- series had no design-stated default and provisioning seeded
    no row for them. CR-005 states those formats, so the refusal it asserted is
    gone: a deposit batch now numbers. The case keeps its job — an unknown
    series must still refuse loudly — against a key that IS unknown, because a
    test asserting a gap that has been filled asserts nothing.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        with transaction.atomic():
            # Seeded by CR-005; the DEP- default is r10 SET-08's own first option.
            assert core_numbering.next_number("deposit_batch", ISSUE_DATE) == "DEP-260808-01"
        with transaction.atomic():
            with pytest.raises(core_numbering.NumberingError):
                core_numbering.next_number("no_such_series", ISSUE_DATE)
        with pytest.raises(errors.NotFoundError):
            services.save_number_series(admin_actor(), "no_such_series", next_number=5)


def test_us_ten_012_api__tab_read_shows_live_previews(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    response = api_call(
        api.number_series, "get", user=FakeUser(), role="system_admin", tenant=tenant
    )
    assert response.status_code == 200
    by_series = {row["series"]: row for row in response.data}
    # CR-005: FIVE became TWENTY-TWO. The five originals are asserted by name
    # because they are the ones a tenant may already have configured.
    assert set(by_series) == set(core_numbering.KNOWN_SERIES)
    assert {"account", "bill", "payment", "adjustment", "asset"} <= set(by_series)
    assert by_series["adjustment"]["preview"] == "ADJ-001"  # preview allocates nothing
    assert models.NumberSeries.objects.get(tenant=tenant, series="adjustment").next_number == 1


def test_us_ten_012_api__put_series_validates_and_saves(growth_plan, identity_seam):
    tenant, _ = provisioned_tenant()
    saved = api_call(
        api.number_series_update,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"next_number": 569},
        series="account",
    )
    assert saved.status_code == 200 and saved.data["next_number"] == 569
    rejected = api_call(
        api.number_series_update,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        data={"format": "AC-{QQ}-{000}"},
        series="account",
    )
    assert rejected.status_code == 422
    assert rejected.data["code"] == "VAL-002"
