# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — the PostgreSQL half.
# Defects: DEF-RAT-9293 · DEF-RAT-9294 · DEF-RAT-9296 (on a real server)
# Rules:   PO 2026-10-03 rulings 1, 2 and 4 · DEF-RAT-8050 (one version in
#          force per discount per day) · CLAUDE.md hard rule 1 (RLS FORCE) ·
#          hard-won laws 7 and 14
# ───────────────────────────────────────────────────────
"""The overlap lock, the one-version-per-date proof, the migration and RLS on
a real PostgreSQL 16.

    cd 06-backend
    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> JOBS_EAGER=false \\
        pytest tests/test_cr166_discounts_round2_pg.py --ds=config.settings.pgtest -s

Every case carries `requires_postgres` and SKIPS by name elsewhere — the
exclusion constraint and RLS do not exist on SQLite, so a green run there would
prove nothing (law 7, *incapable of failing*).

⚠ `ex_discount_versions_no_overlap` is DEFERRABLE INITIALLY DEFERRED and the
test transaction never commits, so each case that relies on it says `SET
CONSTRAINTS … IMMEDIATE` (`check_deferred_now`). Without that line an overlap
would pass whether or not the constraint existed.
"""

import importlib
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, connection, transaction

from apps.rating import discount_services, seams, selectors
from apps.rating import discounts as dm

from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr166_discounts_round2 import (
    DEC_31,
    JAN_01,
    TODAY,
    _bind,
    _discount,
    _home,
    _reduction_on,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, erin, lonestar, tenant_ctx  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]

D = Decimal


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)


def check_deferred_now() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ex_discount_versions_no_overlap IMMEDIATE")
        cursor.execute("SET CONSTRAINTS ex_discount_versions_no_overlap DEFERRED")


def _row(discount, version_no, value, start, end=None, status=dm.VERSION_ACTIVE):
    return dm.DiscountVersion.objects.create(
        tenant_id=discount.tenant_id,
        discount=discount,
        version_no=version_no,
        status=status,
        discount_type=dm.DISCOUNT_PERCENTAGE,
        value=D(value),
        currency="USD",
        effective_from=start,
        effective_to=end,
    )


def test_the_lock_refuses_two_approved_versions_on_one_date(brazos, dana):
    """Ruling 1 makes an APPROVED version price from its start, so the lock
    must hold for it. Approval writes `active`; a legacy `scheduled` row is
    inside the predicate too (`rating/0061`). Both shapes refused."""
    with tenant_ctx(brazos):
        senior = _discount(dana)  # v1 active from 08/01/2026, open-ended
        for status in (dm.VERSION_ACTIVE, dm.VERSION_SCHEDULED):
            with pytest.raises(IntegrityError) as refused:
                with transaction.atomic():  # law 14 — the SAVEPOINT is the only option
                    _row(senior, 9, "12", JAN_01, status=status)
                    check_deferred_now()
            assert "ex_discount_versions_no_overlap" in str(refused.value)
        # The connection is still usable after the refusal (law 14).
        assert dm.DiscountVersion.objects.filter(discount=senior).count() == 1


def test_approval_refuses_an_overlap_by_name_before_the_lock_speaks(brazos, dana):
    with tenant_ctx(brazos):
        senior = _discount(dana, start=date(2026, 8, 1), effective_to="2027-06-30")
        draft = _row(senior, 2, "12", JAN_01, status=dm.VERSION_PENDING_APPROVAL)
        draft.effective_to = None
        draft.save(update_fields=["effective_to"])
        from core import errors

        with pytest.raises(errors.BizError) as refused:
            with transaction.atomic():
                discount_services.approve_discount_version(dana, draft.id)
        check_deferred_now()
    assert refused.value.message_key == "rating.discounts.window_overlaps_version"


def test_billing_gets_exactly_one_version_per_discount_for_any_date(brazos, dana, capsys):
    """THE proof the brief asks for: SENIOR 15% → 12% from 01/01/2027, on a real
    server. The bill path's own read (`billable_discount_rules`, which
    `billing/gather.py::_discounts_for` calls) returns exactly ONE SENIOR row on
    every date from 12/25/2026 to 01/05/2027 — 15% to 12/31, 12% from 01/01 —
    and a $60.00 bill is reduced −$9.00 then −$7.20."""
    with tenant_ctx(brazos):
        _unit, account = _home(dana, brazos)
        senior = _discount(dana, proof_before_first_reduction=False)
        plan = _bind(dana, brazos, senior)
        discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        discount_services.new_discount_value(
            dana, senior.id, {"value": "12", "effective_from": "2027-01-01"}
        )
        check_deferred_now()
        table = []
        day = date(2026, 12, 25)
        while day <= date(2027, 1, 5):
            rows = [
                row
                for row in selectors.billable_discount_rules(account["id"], plan.id, day)
                if row["code"] == "SENIOR"
            ]
            assert len(rows) == 1, (day, rows)
            table.append((day, D(rows[0]["value"]).normalize(), _reduction_on(account["id"], day)))
            day += timedelta(days=1)
        v1 = dm.DiscountVersion.objects.get(discount=senior, version_no=1)
    by_day = {row[0]: row for row in table}
    assert by_day[DEC_31][1:] == (D("15"), D("9.00"))
    assert by_day[JAN_01][1:] == (D("12"), D("7.20"))
    assert all(row[1] == D("15") for row in table if row[0] <= DEC_31)
    assert all(row[1] == D("12") for row in table if row[0] >= JAN_01)
    assert v1.effective_to == DEC_31
    print("\nONE VERSION PER DATE ON POSTGRESQL (date · SENIOR rows · value · off $60.00)")
    for day, value, cut in table:
        print(f"  {day:%m/%d/%Y} · 1 · {value}% · -${cut}")


def test_retire_on_a_date_on_postgres(brazos, dana):
    with tenant_ctx(brazos):
        _unit, account = _home(dana, brazos)
        senior = _discount(dana, proof_before_first_reduction=False)
        _bind(dana, brazos, senior)
        discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        discount_services.retire_discount(dana, senior.id, {"effective_to": "2026-12-31"})
        check_deferred_now()
        cuts = [_reduction_on(account["id"], day) for day in (date(2026, 9, 15), DEC_31, JAN_01)]
    assert cuts == [D("9.00"), D("9.00"), D("0.00")]


def test_unbinding_on_postgres_needs_no_savepoint_and_stops_the_next_bill(brazos, dana):
    """`OQ-322` closed: the old path raised `NotImplementedError` mid-save."""
    from apps.rating import services

    with tenant_ctx(brazos):
        _unit, account = _home(dana, brazos)
        senior = _discount(dana, proof_before_first_reduction=False)
        plan = _bind(dana, brazos, senior)
        discount_services.enrol_account(
            dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1)
        )
        services._apply_plan_children(plan, {"discounts": []}, dana)
        before = selectors.billable_discount_rules(account["id"], plan.id, date(2026, 10, 14))
        after = selectors.billable_discount_rules(account["id"], plan.id, date(2026, 10, 15))
    assert [row["code"] for row in before] == ["SENIOR"]
    assert after == []


def test_migration_0060_holds_assistance_and_puts_approved_in_force(brazos, dana):
    """The data migration on a real server, against rows in TODAY's shapes:
    free-text owner and group, legacy who-qualifies words, and a version left
    `scheduled` by the old four-act lifecycle."""
    migration = importlib.import_module("apps.rating.migrations.0060_cr166_discount_list_backfill")
    with tenant_ctx(brazos):
        cap = _discount(dana, "CAP", approve=False, exclusivity_group="low_income")
        senior = _discount(dana, "SENIOR", approve=False, exclusivity_group="low_income")
        dm.Discount.objects.filter(pk=cap.pk).update(programme_owner="City assistance programme")
        dm.DiscountVersion.objects.filter(discount__in=[cap, senior]).update(
            exclusivity_group="assistance",
            eligibility_code=None,
            eligibility_summary="Age 65+",
            status=dm.VERSION_SCHEDULED,
        )
        dm.DiscountListValue.objects.filter(
            code__in=("assistance", "city_assistance_programme")
        ).delete()
        migration._forwards(django_apps, SimpleNamespace(connection=connection))
        check_deferred_now()
        cap_v = dm.DiscountVersion.objects.get(discount=cap)
        senior_v = dm.DiscountVersion.objects.get(discount=senior)
        cap.refresh_from_db()
        owner = dm.DiscountListValue.objects.get(
            tenant=brazos, list_code=dm.LIST_PROGRAM_OWNER, code=cap.programme_owner
        )
    assert cap_v.exclusivity_group == senior_v.exclusivity_group == "assistance"
    assert owner.label == "City assistance programme" and owner.is_system is False
    assert cap_v.eligibility_code == "age_65_or_over"
    assert cap_v.status == senior_v.status == dm.VERSION_ACTIVE


def test_discount_list_values_are_tenant_scoped(rls, brazos, dana, lonestar, erin):
    """Hard rule 1 on the new table, under a role RLS applies to."""
    assert_denied_without_context(rls, "discount_list_values")
    assert_rls_scoped(rls, "discount_list_values", owner=brazos, intruder=lonestar)
