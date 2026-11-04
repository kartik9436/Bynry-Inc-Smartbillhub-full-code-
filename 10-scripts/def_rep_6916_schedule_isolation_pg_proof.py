#!/usr/bin/env python3
"""CAN ONE UTILITY READ ANOTHER UTILITY'S REPORT SCHEDULE? PROVED ON REAL PostgreSQL.

`06-backend/tests/test_cr142_p4_schedules_api.py::test_another_tenants_schedule_is_a_plain_404`
fails with `assert 200 == 404` (`DEF-REP-6916`). ⚠ **THAT RESULT ANSWERS
NOTHING ON ITS OWN.** CLAUDE.md hard-won law 14: `config/settings/test.py`
hardcodes in-memory SQLite, **which has no row-level security of any kind**, so
a 200 there is consistent BOTH with a real hole AND with an application that
correctly relies on RLS — which is what `schedules_api._schedules_queryset`
says, in its own words, that it does:

    ⚠ **NO `.filter(tenant_id=…)`, AND THAT IS NOT AN OVERSIGHT.**

A test asserting isolation in a harness where the guarantee cannot exist is
hard-won law 7's own example (`G5` called 192 skips a pass). So the answer has
to come from a real database.

    ./10-scripts/proof-db.sh clone secsched
    DATABASE_URL=... PYTHONPATH=06-backend \\
      06-backend/.venv/bin/python 10-scripts/def_rep_6916_schedule_isolation_pg_proof.py

⚠ **IT REFUSES TO RUN AS A ROLE RLS DOES NOT APPLY TO.** PostgreSQL exempts a
superuser from every policy unconditionally, `FORCE` included (`DEF-2717`), and
a `BYPASSRLS` role likewise. A proof run as either prints the same word as a
real one and means nothing.

⚠ **AND IT IS RED-FIRST BY CONSTRUCTION.** Step 4 proves tenant B's OWN context
can see the planted row before step 5 asks whether tenant A can. Without that
control the probe could be measuring an empty table and would print PASS over
a database with no rows in it at all.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import timedelta

import django


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    django.setup()

    from django.db import connection
    from django.utils import timezone
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.identity import models as identity_models
    from apps.reports import schedules_api
    from apps.reports.models import ReportDefinition, ReportSchedule
    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    failures = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'}  {label}{'' if not detail else f' — {detail}'}")
        if not ok:
            failures += 1

    # ── 0 · the role must be one RLS actually applies to ────────────────────
    with connection.cursor() as cur:
        cur.execute(
            "select current_user, rolsuper, rolbypassrls from pg_roles "
            "where rolname = current_user"
        )
        role, is_super, bypasses = cur.fetchone()
    if is_super or bypasses:
        print(
            f"REFUSED: running as {role!r}, which is "
            f"{'a SUPERUSER' if is_super else 'BYPASSRLS'}. PostgreSQL exempts it "
            "from every policy, FORCE included, so this proof would pass over an "
            "absent one."
        )
        return 2
    print(f"role {role!r}: NOSUPERUSER, NOBYPASSRLS — RLS applies to it\n")

    # ── 1 · the table must be FORCE, with both policy halves ────────────────
    with connection.cursor() as cur:
        cur.execute(
            "select relrowsecurity, relforcerowsecurity from pg_class "
            "where relname = 'report_schedules'"
        )
        row = cur.fetchone()
        if row is None:
            print("REFUSED: there is no `report_schedules` table in this database.")
            return 2
        enabled, forced = row
        cur.execute(
            "select polname, polcmd, pg_get_expr(polqual, polrelid) is not null, "
            "pg_get_expr(polwithcheck, polrelid) is not null "
            "from pg_policy p join pg_class c on c.oid = p.polrelid "
            "where c.relname = 'report_schedules'"
        )
        policies = cur.fetchall()
    check("1 · report_schedules has RLS ENABLED", bool(enabled))
    check("1 · report_schedules has RLS FORCED", bool(forced))
    check(
        "1 · a policy with BOTH halves (USING and WITH CHECK)",
        any(using and withcheck for _, _, using, withcheck in policies),
        ", ".join(f"{name} cmd={cmd!r}" for name, cmd, _, _ in policies) or "no policy at all",
    )

    # ── 2 · two tenants, and a staff user of tenant A to be the caller ──────
    tenants = list(Tenant.objects.order_by("created_at")[:2])
    if len(tenants) < 2:
        tenants.append(
            Tenant.objects.create(
                name="schedule isolation neighbour",
                subdomain=f"sched-proof-{uuid.uuid4().hex[:8]}",
                currency="USD",
            )
        )
        print("this database held ONE tenant; a second was created for the proof")
    alpha, beta = tenants[0], tenants[1]
    print(f"tenant A (the reader)  = {alpha.subdomain}  {alpha.id}")
    print(f"tenant B (the owner)   = {beta.subdomain}  {beta.id}\n")

    with core_tenancy.tenant_context(alpha.id):
        membership = (
            identity_models.TenantMembership.objects.select_related("user")
            .filter(tenant_id=alpha.id, status=identity_models.TenantMembership.STATUS_ACTIVE)
            .first()
        )
    if membership is None:
        print("REFUSED: tenant A has no active member to act as the caller.")
        return 2
    caller = membership.user
    print(f"caller: an active member of tenant A ({caller.pk})\n")

    # ── 3 · plant a REAL schedule for tenant B, in tenant B's own context ───
    key = f"isolation-proof-{uuid.uuid4().hex[:8]}"
    with core_tenancy.tenant_context(beta.id):
        definition = ReportDefinition.objects.create(
            tenant_id=beta.id,
            key=key,
            name="AR Ageing",
            dataset="invoices",
            group_code="finance",
        )
        foreign = ReportSchedule.objects.create(
            tenant_id=beta.id,
            definition=definition,
            cadence="daily",
            params={},
            recipients=[],
            next_run_at=timezone.now() + timedelta(days=1),
            enabled=True,
        )
    print(f"planted schedule {foreign.pk} for tenant B\n")

    # ── 4 · RED-FIRST CONTROL — tenant B's OWN context MUST see it ──────────
    with core_tenancy.tenant_context(beta.id):
        own = ReportSchedule.objects.filter(pk=foreign.pk).first()
    if own is None:
        print(
            "REFUSED: tenant B cannot see its own planted row, so every 'not "
            "visible' below would be measuring an empty table and would prove "
            "nothing. Stopping."
        )
        return 2
    print("4 · CONTROL: tenant B's own context DOES see the row — the probe has something to find\n")

    # ── 5 · tenant A's context, three ways ──────────────────────────────────
    with core_tenancy.tenant_context(alpha.id):
        with connection.cursor() as cur:
            cur.execute("select current_setting('app.tenant_id', true)")
            print(f"5 · app.tenant_id in this session = {cur.fetchone()[0]!r}")

        # (a) unfiltered
        unfiltered = list(ReportSchedule.objects.all())
        foreign_rows = [r for r in unfiltered if str(r.tenant_id) != str(alpha.id)]
        check(
            "5a · unfiltered SELECT returns NO row of another tenant",
            not foreign_rows,
            f"{len(unfiltered)} rows visible, {len(foreign_rows)} belonging to another tenant",
        )

        # (b) by its id
        by_id = ReportSchedule.objects.filter(pk=foreign.pk).first()
        check(
            "5b · SELECT by the foreign row's own id returns nothing",
            by_id is None,
            "the row came back" if by_id is not None else "0 rows",
        )

        # (b2) raw SQL, so the answer is the POLICY and not the ORM
        with connection.cursor() as cur:
            cur.execute("select count(*) from report_schedules where id = %s", [str(foreign.pk)])
            raw = cur.fetchone()[0]
        check("5b2 · raw SQL by id counts 0 (this is the policy, not the ORM)", raw == 0, f"count={raw}")

        # (c) through the API handler the failing test calls
        factory = APIRequestFactory()
        request = factory.get(f"/api/reports/schedules/{foreign.pk}")
        force_authenticate(request, user=caller)
        request.tenant_role = "system_admin"
        request.tenant_id = alpha.id
        try:
            response = schedules_api.schedule_detail(request, schedule_id=foreign.pk)
            status = response.status_code
        except Exception as exc:  # noqa: BLE001
            status = f"raised {type(exc).__name__}: {exc}"
        check(
            "5c · GET /reports/schedules/{foreign id} answers 404",
            status == 404,
            f"status = {status}",
        )

    # ── 6 · and with NO context at all, which is the hole RLS-alone leaves ──
    core_tenancy.clear_current_tenant()
    with connection.cursor() as cur:
        cur.execute("select current_setting('app.tenant_id', true)")
        setting = cur.fetchone()[0]
    try:
        none_ctx = ReportSchedule.objects.filter(pk=foreign.pk).count()
        outcome = f"{none_ctx} row(s) visible"
    except Exception as exc:  # noqa: BLE001
        outcome = f"raised {type(exc).__name__}"
    print(
        f"\n6 · with app.tenant_id = {setting!r} (no context), a read of the "
        f"foreign row gives: {outcome}"
    )
    print(
        "    ⚠ This is the fact that makes 'the application relies on RLS "
        "alone' a statement with a cost: it is lawful, and it means any code "
        "path that runs WITHOUT app.tenant_id set is the hole, not the query."
    )

    # ── 7 · clean up the planted rows ───────────────────────────────────────
    with core_tenancy.tenant_context(beta.id):
        ReportSchedule.objects.filter(pk=foreign.pk).delete()
        ReportDefinition.objects.filter(pk=definition.pk).delete()

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
