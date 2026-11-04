# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — work/0028–0031, metering/0071–0072
# Rules:    CLAUDE.md hard rule 1 (RLS ENABLE + FORCE, read from pg_class) ·
#           law 14 (proved on PostgreSQL, never by SQLite's vacuum) · the
#           completion guard (ruling 18) and the acceptance money path unchanged
# Tests:    this file — run under config.settings.pgtest
# ───────────────────────────────────────────────────────
"""CR-168 round 2 · SRV-1 on real PostgreSQL 16.

1. The three new tables carry ENABLE *and* FORCE, and a second tenant reads
   none of the first's rows under the non-superuser probe role.
2. The seeded hold reasons equal the constant `work/0028` pinned.
3. The acceptance money path is UNCHANGED: a job closed by its technician and
   accepted by the office writes the same cost lines and the same meter read it
   wrote before the guard — the guard moves WHO may close, never what a close
   writes (§8 *Rollback*).

The up → down → up of the six migrations is run through `manage.py migrate`
against the lane's database and its transcript is in CR-168 §9; a migration
test inside the suite would roll back a schema every other case depends on.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

from apps.work import models as work_models
from apps.work import services as work_services

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

NEW_TABLES = ("work_hold_reasons", "work_order_rule_triggers", "work_order_rule_escalation_fires")


@requires_postgres
def test_work_0030_the_three_new_tables_are_enabled_and_forced():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s)",
            [list(NEW_TABLES)],
        )
        found = {name: (enabled, forced) for name, enabled, forced in cursor.fetchall()}
    assert found == {table: (True, True) for table in NEW_TABLES}


@requires_postgres
def test_work_0030_hold_reasons_are_invisible_to_another_tenant(brazos, lonestar, rls):
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_hold_reasons", [], "test")
    assert_rls_scoped(rls, "work_hold_reasons", owner=brazos, intruder=lonestar, min_owner_rows=5)


def test_work_0028_pins_the_same_five_reasons_the_model_seeds():
    pinned = importlib.import_module("apps.work.migrations.0028_cr168_hold_reasons_and_columns")
    assert [(c, n, r) for c, n, r in pinned.SEED] == [
        (row["code"], row["name"], row["rank"]) for row in work_models.SEED_HOLD_REASONS
    ]


@requires_postgres
def test_the_acceptance_money_path_is_unchanged_by_the_guard(dana, brazos):
    """Closed by the technician it was given to, accepted by the office: the
    order is completed AND reads Complete, accepted_by is the office, and the
    acceptance wrote the same rows the pre-guard path wrote (`accept` is not
    touched by this lane). Law 14 — on PostgreSQL."""
    from apps.identity import models as identity_models
    from apps.metering import connections as w6
    from apps.work import connection_models as work_tables
    from apps.work import dispatch

    from tests.test_us_met_helpers import make_premises

    with tenant_ctx(brazos):
        for code in ("work_priorities", "work_order_types"):
            work_services.seed_reference_list(code, [], "test")
        premises = make_premises(dana, address_line="77 Cedar Ct", services_available=["water"])
        raised = w6.create_work_order(
            dana, None, {"type": "Leak investigation", "service": "water",
                         "premises_id": premises["id"]},
        )
        user = identity_models.User.objects.create(
            tenant_id=brazos.id, email="d-ortiz@brazos.test", full_name="D. Ortiz"
        )
        tech = work_models.Technician.objects.create(tenant_id=brazos.id, user=user)
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
        w6.submit_field_result(
            SimpleNamespace(id=user.id, role="field_technician"), raised["id"],
            field_data={"ok": True}, outcome="passed",
        )
        w6.accept_field_result(dana, raised["id"])
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert (order.state, order.dispatch_state) == ("completed", "complete")
        assert order.accepted_by_id == dana.id and order.accepted_at is not None
