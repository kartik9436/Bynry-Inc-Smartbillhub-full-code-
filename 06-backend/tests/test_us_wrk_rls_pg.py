# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 · 008 · 009 · 010 — the six Work reference tables.
#           The 🔒 file under review is `apps/work/migrations/0002_rls_force.py`
#           (review-ledger row, CR-070 wave C task C4)
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · B2 §3 (ENABLE + FORCE with
#           USING/WITH CHECK on `tenant_id`) · hard-won law 14 (the suite runs
#           on SQLite, which has NO row-level security — a proof about the real
#           database runs on the real database) · law 7 (proved RED first)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""The six Work tables under real row-level security, on real PostgreSQL.

WHY THIS FILE EXISTS SEPARATELY FROM THE SUITE
-----------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. **SQLite has no row-level security of any kind**, so every
assertion about a policy passes there by vacuum — a green test that proves
nothing, which is the shape hard-won law 14 was written for one rule along.

Run it against a real database:

    createdb sbh_cr070c
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr070c?sslmode=disable"
    pytest tests/test_us_wrk_rls_pg.py

AND WHY IT ASSERTS UNDER A PROBE ROLE RATHER THAN THE APP'S OWN
---------------------------------------------------------------
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
**unconditionally, `FORCE` included**, and the development role is a superuser
(`DEF-2717`: a second tenant reported 73 accounts inside its own context when
it had none — the count was the other tenant's). So the reads below run inside
`SET ROLE sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS) on the test's own
connection and transaction, and `rls.assert_is_a_real_proof()` FAILS — never
skips — if that role could bypass anything.

THREE THINGS ARE ASSERTED, AND THE FIRST TWO ARE OFTEN CONFUSED
---------------------------------------------------------------
  1. **The flags** — `relrowsecurity` AND `relforcerowsecurity` in `pg_class`,
     per table. `ENABLE` alone exempts the table's OWNER, and the application's
     migration role owns every table in this schema, so a table with ENABLE and
     no FORCE is a table with no policy for the process that matters.
  2. **The zero rows** — with no `app.tenant_id` set, every one of the six
     answers zero, and under one tenant's context not one of the other's rows
     is reachable. A flag is a claim; this is the behaviour.
  3. **The WITH CHECK** — a write stamped for another tenant is refused BY THE
     POLICY, with `row-level security` in PostgreSQL's own message.
"""

from __future__ import annotations

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

#: The FOURTEEN tables Work owns — the six `work/0001` creates and
#: `work/0002_rls_force` protects, and the eight `work/0003` creates and
#: `work/0004_rls_force_bundle` protects.
WORK_TABLES = (
    # ── CR-070 wave D · the template bundle (work/0003 + work/0004) ────────
    # ⚠ **THESE EIGHT ARE THE UTILITY'S METHOD, NOT ITS SETTINGS.** A template
    # bundle is the exact steps its crews follow, the minutes each takes, the
    # safety lines it demands and what every part it fits costs it — and a
    # WRITE across the boundary is worse than a read in a way that reaches a
    # customer: deleting another tenant's `wot_safety` row removes a safety
    # line, and the next order raised from that template is copied WITHOUT it
    # (`BR-WRK-008`, copy never link). Nothing about the resulting job looks
    # wrong.
    "wot_details",
    "wot_safety",
    "wot_tasks",
    "wot_materials",
    "wot_readings",
    "wot_help",
    "wot_asset_types",
    "work_order_template_versions",
    "work_order_types",
    "work_priorities",
    "work_skills",
    "work_safety_kits",
    "part_categories",
    "parts",
)


@requires_postgres
def test_work_0002_every_table_is_enabled_AND_forced(brazos):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the owner.

    Read out of `pg_class` rather than out of the migration file, because what
    is asserted is the state of the DATABASE — a migration that ran, a policy
    somebody dropped by hand and a policy that was never written all look the
    same in the source tree.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s) ORDER BY c.relname",
            [list(WORK_TABLES)],
        )
        found = {name: (enabled, forced) for name, enabled, forced in cursor.fetchall()}
    assert set(found) == set(WORK_TABLES), f"missing tables: {set(WORK_TABLES) - set(found)}"
    wrong = {name: flags for name, flags in found.items() if flags != (True, True)}
    assert wrong == {}, (
        "CLAUDE.md hard rule 1 / B2 §3: every Work reference table needs ENABLE *and* "
        f"FORCE ROW LEVEL SECURITY — {wrong}"
    )


@requires_postgres
def test_work_0002_with_no_tenant_context_all_six_tables_return_nothing(brazos, rls):
    """Hard rule 1, stated as the behaviour a person can check.

    `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL when
    nothing set it, `tenant_id = NULL` is NULL, and NULL is not TRUE — so no
    row is visible and no row may be written. Deny by default, without the
    error the older `::uuid` form raised (`DEF-639`).
    """
    assert_denied_without_context(rls, *WORK_TABLES)


def _a_published_bundle(actor, tenant) -> None:
    """Fill the eight `work/0003` bundle tables for `tenant`.

    ⚠ **PROVISIONING DOES NOT SEED THESE EIGHT AND THE LOOP BELOW ASSUMED IT
    DID (2026-09-05).** The six `work/0001` tables are reference lists a tenant
    gets at provisioning — job types, priorities, skills, safety kits, part
    categories — but a TEMPLATE BUNDLE only exists once somebody builds a
    template. So `wot_details` and its seven siblings were empty, and
    `assert_rls_scoped` correctly refused to conclude anything from a table
    with no owner rows in it.

    That is the same disposition `parts` already had in this file — *"seeded by
    nobody; given rows below"* — and it is the honest one: a scoping proof over
    an empty table is not a weaker proof, it is no proof. So the rows are made
    here, through the real services, and the loop keeps its full fourteen.
    """
    import uuid

    from apps.work import templates_svc

    from tests.test_us_wrk_032_copies import _published_template

    template_id = _published_template(actor, tenant)
    # `_published_template` fills six collections; `asset-types` is the seventh
    # and is not part of the copies fixture, so it is added here. The id points
    # at the assets catalogue through the seam and is never stored as text.
    templates_svc.replace_collection(
        actor, template_id, "asset-types", [{"asset_type_id": str(uuid.uuid4())}]
    )


@requires_postgres
def test_work_0002_one_tenants_rows_are_invisible_to_the_other(brazos, lonestar, dana, rls):
    """Brazos Bend's eight job types are not there for Lone Star Ridge.

    Asserted through the DATABASE under a role RLS applies to — the handler's
    own `filter(tenant_id=…)` is deliberately not in the path, so this is the
    policy and not the application layer agreeing with itself.
    """
    with tenant_ctx(brazos):
        _a_published_bundle(dana, brazos)
    for table in WORK_TABLES:
        if table == "parts":
            continue  # seeded by nobody; given rows in its own case below
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)


@requires_postgres
def test_work_0002_the_parts_register_is_scoped_too(brazos, lonestar, rls):
    """`parts` carries a PRICE, so it is the one worth naming separately."""
    from apps.work import services as work_services

    with tenant_ctx(brazos):
        work_services.create_part(
            None,
            {
                "part_no": "MTR-W58",
                "name": 'Water meter 5/8"',
                "category": "Meters",
                "unit_of_measure": "each",
                "unit_cost": "92.4000",
            },
        )
    assert_rls_scoped(rls, "parts", owner=brazos, intruder=lonestar)


@requires_postgres
def test_work_0002_a_write_stamped_for_another_tenant_is_refused_by_the_policy(
    brazos, lonestar, rls
):
    """The `WITH CHECK` half. Reading across the wall is a leak; WRITING across
    it is worse — flipping another utility's *Urgent* from 4 hours to 400 breaks
    every due date they raise from that moment, silently."""
    message = assert_write_into_other_tenant_refused(
        rls, "work_priorities", owner=brazos, intruder=lonestar
    )
    assert "row-level security" in message


@requires_postgres
def test_work_0002_the_seeded_counts_are_what_the_review_ledger_row_quotes(brazos):
    """The figures the Product Owner is shown in plain English (task C4).

    A review-ledger row that quotes a number nothing asserts is a number that
    drifts; this is the test that keeps the sentence *"Brazos Bend's job types
    are invisible to Lone Star Ridge"* meaning a measured number.

    ⚠ **THE JOB-TYPE FIGURE WAS `8` AND IS NOW `9 + 21` (`DEF-WRK-6787`,
    2026-09-25).** Eight was right on 2026-09-04, when this row was written.
    **`BR-WRK-058` superseded it on 2026-09-07** — the PO said the eight were
    the wrong list (*"this is not correct - you will ahve to think from all
    Utilty services point of view"*) and gave us the replacement: nine types
    with sub-types under them, per utility service. The review-ledger row for
    that ruling states the arithmetic this asserts, in the PO's own counts:
    *"A utility that sold electric and water gets 9 and 21."* Brazos Bend
    sells electric and water. **The eight are switched OFF rather than deleted
    on a utility that already had them, and a tenant provisioned after the
    ruling never receives them at all** — which is why the total here is 30 and
    not 38.

    It is asserted as ROOTS and CHILDREN rather than as a bare 30, because 30
    is a sum of two numbers the PO ruled separately and a single total cannot
    tell a lost sub-type from a gained type. The other four counts did not move.
    """
    with tenant_ctx(brazos):
        types = work_models.WorkOrderType.objects.filter(tenant=brazos)
        assert types.filter(parent__isnull=True).count() == 9
        assert types.filter(parent__isnull=False).count() == 21
        assert types.count() == 30
        assert work_models.WorkPriority.objects.filter(tenant=brazos).count() == 4
        assert work_models.WorkSkill.objects.filter(tenant=brazos).count() == 8
        assert work_models.WorkSafetyKit.objects.filter(tenant=brazos).count() == 4
        assert work_models.PartCategory.objects.filter(tenant=brazos).count() == 4
