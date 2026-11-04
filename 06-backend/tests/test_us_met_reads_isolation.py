# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007/TC-8 · US-MET-008/TC-9 · US-MET-009/TC-7 ·
#           US-MET-010/TC-8 · US-MET-011/TC-10 · US-MET-014/TC-8 — the
#           isolation TC of every reads story, in one place
#           Screens: S25 · S28 · S29
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE) · B2 §3 policy template · DB-1 ·
#           NFR-10 (zero tolerance, release blocker)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a vendor
#           reason off Postgres — sqlite has no RLS, so a green run there would
#           prove nothing (tests/isolation_helpers.py explains the probe role).
#           Each was proved RED against the live cluster by dropping the
#           metering reads policies first; transcripts in the lane report
#           (Hard-won law 7).
# ───────────────────────────────────────────────────────
"""The database half of the reads lane's tenant isolation.

The four W2 reads tables are asserted through a NON-SUPERUSER probe role, so
the policies are genuinely consulted rather than bypassed. `meter_reads` is the
interesting one: it is PARTITIONED, and RLS on a partitioned parent is
inherited by every partition — the probe therefore proves the whole 2-year hot
window at once, and every month the create-ahead job adds later.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.metering import models

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    staff_actor,
)

pytestmark = pytest.mark.django_db

READS_TABLES = (
    "read_validation_settings",
    "read_import_batches",
    "read_import_rows",
    "meter_reads",
)


def _world(payload=None):
    """A tenant with one meter, one staged batch and one committed read."""
    from apps.assets import services as asset_services
    from apps.metering import services

    tenant, _ = provisioned_tenant(payload or brazosbend_payload())
    actor = staff_actor(tenant, "system_admin", f"admin@{tenant.id}.test")
    with live_tenant_context(tenant.id):
        services.ensure_read_validation_settings()
        premise = services.create_premises(
            actor,
            {"owner_id": owner_for(actor), 
                "address_line": "1408 Bluestem Ln",
                "city": "Katy",
                "state": "TX",
                "services_available": ["water"],
            },
        )
        unit = services.create_unit(
            actor, {"premises_id": premise["id"], "label": "Unit A", "services": ["water"]}
        )
        asset = asset_services.create_asset(
            actor,
            {
                "type": "meter",
                "asset_no": "M-7001",  # the SAME number in both tenants, on purpose
                "service": "water",
                "unit": "gal",
                "read_method": "manual",
                "multiplier": "1",
                "register_digits": 5,
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
                "status": "active",
            },
        )
        batch = services.stage_read_batch(
            actor,
            {
                "source_kind": "csv",
                "source_detail": "walk_by",
                "period_month": "2026-08-01",
                "file_name": "reads.csv",
                "file_content": "meter_id,read_date,reading\nM-7001,2026-08-03,42864\n",
            },
        )
        read = models.MeterRead.objects.create(
            tenant_id=tenant.id,
            asset_id=asset["id"],
            read_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
            channel="total",
            current_value=Decimal("42864"),
            multiplier=Decimal("1"),
            consumption=Decimal("684.000000"),
            unit="gal",  # explicit, always
            source="import",
            status="ok",
            lifecycle="committed",
        )
    return tenant, batch, read


@pytest.mark.isolation
@requires_postgres
def test_reads_tables_are_denied_outright_with_no_tenant_context(rls):  # noqa: F811
    """CLAUDE.md rule 1: with `app.tenant_id` unset the policy's ::uuid cast of
    '' fails and NO row is visible. Deny-by-default, not filter-by-default."""
    _world()
    assert_denied_without_context(rls, *READS_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_met_010_tc8__a_posted_batch_and_its_reads_never_cross_tenants(rls):  # noqa: F811
    """Proved RED by dropping `meter_reads_tenant_isolation` on the live
    database: the probe then sees BOTH tenants' reads and this fails naming
    the leak."""
    brazos, bb_batch, bb_read = _world()
    lonestar, lsr_batch, lsr_read = _world(lonestarridge_payload())

    assert_rls_scoped(
        rls, "meter_reads", owner=brazos, intruder=lonestar, owner_ids={str(bb_read.id)}
    )
    assert_rls_scoped(
        rls, "read_import_batches", owner=brazos, intruder=lonestar, owner_ids={bb_batch["id"]}
    )
    assert_rls_scoped(rls, "read_import_rows", owner=brazos, intruder=lonestar)
    assert_rls_scoped(rls, "read_validation_settings", owner=brazos, intruder=lonestar)

    with live_tenant_context(lonestar.id):
        # The id-guessing attack — the one that survives a missing app filter.
        assert rls.count("meter_reads", "id = %s", [str(bb_read.id)]) == 0
        assert rls.ids("meter_reads") == {str(lsr_read.id)}
        assert rls.count("read_import_batches", "id = %s", [bb_batch["id"]]) == 0
    assert_no_foreign_rows_anywhere(rls, lonestar, READS_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_a_write_into_another_tenants_reads_is_refused(rls):  # noqa: F811
    """WITH CHECK, not just USING: a tenant cannot INSERT a row stamped with a
    neighbour's tenant_id even though it knows the value."""
    brazos, _b, _r = _world()
    lonestar, _lb, _lr = _world(lonestarridge_payload())
    for table in ("read_import_batches", "read_validation_settings"):
        assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)


@pytest.mark.isolation
@requires_postgres
def test_meter_reads_is_partitioned_and_every_partition_inherits_the_policy(rls):  # noqa: F811
    """DB-7 / BR-MET-055 + rule 1 together: the parent is a partitioned table
    and RLS on it is inherited, so no monthly partition can be born unguarded.

    This is the assertion that would have caught a hand-written partition
    created outside the parent — the failure mode a per-partition policy list
    invites and inheritance forecloses.
    """
    from django.db import connection

    _world()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relkind, relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE relname = 'meter_reads'"
        )
        relkind, rls_on, forced = cursor.fetchone()
        assert relkind == "p", "meter_reads must be the PARTITIONED parent (DB-7)"
        assert rls_on and forced, "ENABLE + FORCE, both (B2 §3 — FORCE applies to the owner too)"

        cursor.execute(
            "SELECT count(*) FROM pg_inherits i "
            "JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = 'meter_reads'"
        )
        assert cursor.fetchone()[0] >= 24, "the 2-year hot window must be writable from day one"

        # Every partition must be reachable ONLY through the parent's policy.
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity FROM pg_inherits i "
            "JOIN pg_class p ON p.oid = i.inhparent JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE p.relname = 'meter_reads' AND c.relrowsecurity = false"
        )
        unguarded = [row[0] for row in cursor.fetchall()]
        assert not unguarded, f"partitions without RLS: {unguarded}"


@pytest.mark.isolation
@requires_postgres
def test_the_head_uniqueness_constraint_exists_on_the_partitioned_parent(rls):  # noqa: F811
    """B2 r8's UNIQUE (asset, read_at, channel), scoped to lineage HEADS so the
    supersede the same addendum mandates remains possible. A plain unique here
    would make corrections impossible; no unique at all would let a double
    post through under a race."""
    from django.db import connection

    _world()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'meter_reads' AND indexname = 'uq_meter_reads_head'"
        )
        row = cursor.fetchone()
    assert row is not None, "uq_meter_reads_head is missing — a double post could land"
    indexdef = row[0]
    assert "UNIQUE" in indexdef
    assert "superseded_by_id IS NULL" in indexdef  # heads only
    for column in ("tenant_id", "asset_id", "read_at", "channel"):
        assert column in indexdef
