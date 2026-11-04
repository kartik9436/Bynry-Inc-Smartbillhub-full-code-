# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-050 (part issues) · US-WRK-051 (labour rates) · US-WRK-053
#           (the report and its cost lines). The 🔒 files under review are
#           `apps/work/migrations/0011_rls_force_costing.py` (RLS + the freeze
#           trigger) and `apps/work/costing.py` (money rounding on a
#           customer-facing document) — review-ledger rows, wave N task N5.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE) · hard rule 4's shape (a frozen
#           document is corrected by a new version, never edited) ·
#           BR-WRK-050 · BR-WRK-051 · B2 §3 · hard-won law 14 (the suite runs
#           on SQLite, which has neither RLS nor PL/pgSQL) · law 7 (RED first)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""Wave N's four tables under real row-level security, on real PostgreSQL —
and the FREEZE trigger, which SQLite cannot run at all.

WHY THIS FILE EXISTS SEPARATELY FROM THE SUITE
-----------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. **SQLite has no row-level security and runs no PL/pgSQL
trigger**, so every assertion about either passes there by vacuum — hard-won
law 14's shape, one rule along. There are TWO guarantees here and SQLite is
blind to both.

Run it against a real database:

    createdb sbh_cr070n
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_cr070n"
    pytest tests/test_us_wrk_053_costing_pg.py

⚠ **AND THE TENANT-ISOLATION GATE IS NOT THIS PROOF** (`DEF-GOV-4024`, filed
2026-09-05): it runs the isolation suite without pointing it at PostgreSQL, so
it inherits SQLite — 46 of 238 proofs run, 192 skip, and it exits 0. A green
gate there is evidence of nothing at all. This file is the evidence.

WHAT EACH TABLE COSTS IF THE BOUNDARY LEAKS
--------------------------------------------
`labour_rates` read across is what another utility pays its crews — the most
commercially sensitive number in the module, and the reason `WM-45` refused to
put a rate on a PERSON at all. `part_issues` is its stores and who drew from
them. `work_order_cost_lines` and `work_order_reports` are job costs and a
customer's address on a signed document — and written across, a stranger
changes the total on a report a supervisor already approved.

AND THE FREEZE IS A DIFFERENT GUARANTEE FROM THE POLICY
--------------------------------------------------------
`BR-WRK-050`: a report is generated once and frozen; a correction is `-v2`
BESIDE `-v1`. A service-layer refusal holds for the service layer; this one
holds for the ORM, for `.update()`, for `raw()`, for a data migration and for a
person at a psql prompt, because it is `BEFORE UPDATE OR DELETE` and it raises.
The LINES are frozen too, or the `total` would be frozen over three numbers
that could still move.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.work import models as work_models

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

#: The four tables `work/0010` creates and `work/0011` protects.
WAVE_N_TABLES = (
    "labour_rates",
    "part_issues",
    "work_order_cost_lines",
    "work_order_reports",
)


@requires_postgres
def test_work_0011_every_table_is_enabled_AND_forced(brazos):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the owner.

    Read out of `pg_class` rather than out of the migration file, because what
    is asserted is the state of the DATABASE — a migration that ran, a policy
    somebody dropped by hand and a policy that was never written all look
    identical in the source tree.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s) ORDER BY c.relname",
            [list(WAVE_N_TABLES)],
        )
        found = {name: (enabled, forced) for name, enabled, forced in cursor.fetchall()}
    assert set(found) == set(WAVE_N_TABLES), f"missing: {set(WAVE_N_TABLES) - set(found)}"
    wrong = {name: flags for name, flags in found.items() if flags != (True, True)}
    assert wrong == {}, (
        "CLAUDE.md hard rule 1 / B2 §3: every wave N table needs ENABLE *and* FORCE "
        f"ROW LEVEL SECURITY — {wrong}"
    )


@requires_postgres
def test_with_no_tenant_context_none_of_the_four_is_readable(brazos, rls):
    """Hard rule 1 as the behaviour a person can check, not as a flag."""
    assert_denied_without_context(rls, *WAVE_N_TABLES)


@requires_postgres
def test_us_wrk_051_tc7_one_utility_cannot_read_anothers_labour_rates(
    brazos, lonestar, dana, erin, rls
):
    """TC-7 at the DATABASE layer — the application half is the SQLite file.

    What a utility pays its crews, under a non-superuser probe role.
    """
    from apps.work import services as work_services

    with tenant_ctx(brazos):
        work_services.create_labour_rate(dana, {
            "role": "field_technician", "hourly": "48.5000", "effective_from": "2026-01-01",
        })
    with tenant_ctx(lonestar):
        work_services.create_labour_rate(erin, {
            "role": "field_technician", "hourly": "51.0000", "effective_from": "2026-01-01",
        })
    assert_rls_scoped(rls, "labour_rates", owner=brazos, intruder=lonestar)


@requires_postgres
def test_us_wrk_050_tc6_one_utility_cannot_read_anothers_issue_log(
    brazos, lonestar, dana, erin, rls
):
    """TC-6 at the DATABASE layer — another utility's stores, and who drew."""
    from apps.work import services as work_services

    for tenant, actor, part_no in ((brazos, dana, "MTR-W58"), (lonestar, erin, "LSR-01")):
        with tenant_ctx(tenant):
            part = work_models.Part.objects.create(
                tenant=tenant, part_no=part_no, name=part_no,
                unit_of_measure="each", unit_cost=Decimal("92.4000"),
            )
            work_services.create_part_issue(actor, {"part_id": str(part.id), "qty": "-2"})
    assert_rls_scoped(rls, "part_issues", owner=brazos, intruder=lonestar)


@requires_postgres
def test_a_rate_stamped_for_another_utility_is_refused_by_the_policy(
    brazos, lonestar, dana, rls
):
    """The WITH CHECK half — a WRITE across the boundary, refused by the
    database and not by a queryset that could be forgotten."""
    from apps.work import services as work_services

    with tenant_ctx(brazos):
        work_services.create_labour_rate(dana, {
            "role": "field_technician", "hourly": "48.5000", "effective_from": "2026-01-01",
        })
    message = assert_write_into_other_tenant_refused(
        rls, "labour_rates", owner=brazos, intruder=lonestar
    )
    assert "row-level security" in message.lower()


# ══════════════════════════════════════════════════════════════════════════
# BR-WRK-050 — the freeze, which SQLite cannot run at all
# ══════════════════════════════════════════════════════════════════════════
def _report(brazos, dana):
    from apps.work import connection_models as work_tables
    from tests.test_us_met_helpers import make_premises

    premises = make_premises(dana, address_line="221 Oak Ave", services_available=["electric"])
    order = work_tables.WorkOrder.objects.create(
        tenant=brazos, type="Meter exchange", order_no="WO-4822",
        state=work_tables.WO_COMPLETED, premises_id=premises["id"],
        completed_at=dt.datetime(2026, 3, 15, 16, 7, tzinfo=dt.timezone.utc),
    )
    report = work_models.WorkOrderReport.objects.create(
        tenant=brazos, work_order=order, version=1,
        generated_at=dt.datetime(2026, 3, 16, 9, 12, tzinfo=dt.timezone.utc),
        total=Decimal("138.42"),
    )
    line = work_models.WorkOrderCostLine.objects.create(
        tenant=brazos, work_order=order, kind="labour", description="Field technician",
        qty=Decimal("0.87"), unit="h", rate=Decimal("48.5000"), amount=Decimal("42.1950"),
    )
    return order, report, line


@requires_postgres
def test_us_wrk_053_tc6_an_approved_report_cannot_be_edited(brazos, dana):
    """`BR-WRK-050` — a correction produces `-v2`; `-v1` is never overwritten.

    The trigger, not the docstring. A report whose total can be changed after
    approval is not evidence of anything.
    """
    # ⚠ `ProgrammingError`, NOT `InternalError`. A PL/pgSQL `RAISE EXCEPTION`
    # arrives as `psycopg.errors.RaiseException`, which Django maps to
    # `ProgrammingError` — measured against real PostgreSQL 16 rather than
    # guessed, because on SQLite this whole file is skipped and a wrong class
    # here would be a test that cannot fail for the right reason.
    from django.db import ProgrammingError, transaction

    with tenant_ctx(brazos):
        _, report, _ = _report(brazos, dana)
        with pytest.raises(ProgrammingError) as excinfo, transaction.atomic():
            work_models.WorkOrderReport.objects.filter(id=report.id).update(
                total=Decimal("999.99")
            )
    assert "BR-WRK-050" in str(excinfo.value)
    assert "frozen" in str(excinfo.value)


@requires_postgres
def test_us_wrk_053_tc6b_an_approved_report_cannot_be_deleted(brazos, dana):
    """Nor deleted — the other half of `BEFORE UPDATE OR DELETE`."""
    # ⚠ `ProgrammingError`, NOT `InternalError`. A PL/pgSQL `RAISE EXCEPTION`
    # arrives as `psycopg.errors.RaiseException`, which Django maps to
    # `ProgrammingError` — measured against real PostgreSQL 16 rather than
    # guessed, because on SQLite this whole file is skipped and a wrong class
    # here would be a test that cannot fail for the right reason.
    from django.db import ProgrammingError, transaction

    with tenant_ctx(brazos):
        _, report, _ = _report(brazos, dana)
        with pytest.raises(ProgrammingError) as excinfo, transaction.atomic():
            work_models.WorkOrderReport.objects.filter(id=report.id).delete()
    assert "BR-WRK-050" in str(excinfo.value)


@requires_postgres
def test_the_cost_lines_are_frozen_too_or_the_total_is_frozen_over_nothing(brazos, dana):
    """⚠ **THE LOAD-BEARING HALF.**

    Freezing the report row while leaving its lines editable would freeze the
    `total` column and let the three numbers underneath it move — a document
    that adds up to something other than the sum of its own lines, which is
    exactly what `BR-WRK-051` exists to prevent.
    """
    # ⚠ `ProgrammingError`, NOT `InternalError`. A PL/pgSQL `RAISE EXCEPTION`
    # arrives as `psycopg.errors.RaiseException`, which Django maps to
    # `ProgrammingError` — measured against real PostgreSQL 16 rather than
    # guessed, because on SQLite this whole file is skipped and a wrong class
    # here would be a test that cannot fail for the right reason.
    from django.db import ProgrammingError, transaction

    with tenant_ctx(brazos):
        _, _, line = _report(brazos, dana)
        with pytest.raises(ProgrammingError) as excinfo, transaction.atomic():
            work_models.WorkOrderCostLine.objects.filter(id=line.id).update(
                amount=Decimal("999.9999")
            )
    assert "BR-WRK-051" in str(excinfo.value)


@requires_postgres
def test_us_wrk_053_tc5_a_second_v1_cannot_exist_even_if_a_caller_tried(brazos, dana):
    """TC-5 — pressing Accept twice produces no second `v1`.

    `accept_field_result` already refuses a second acceptance; this is the
    backstop underneath it, in the shape hard rule 6 uses for a bill run. A
    guarantee that lives only in a service layer is one call site away from
    not existing.
    """
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        order, _, _ = _report(brazos, dana)
        with pytest.raises(IntegrityError), transaction.atomic():
            work_models.WorkOrderReport.objects.create(
                tenant=brazos, work_order=order, version=1,
                generated_at=dt.datetime(2026, 3, 17, 9, 0, tzinfo=dt.timezone.utc),
                total=Decimal("138.42"),
            )
