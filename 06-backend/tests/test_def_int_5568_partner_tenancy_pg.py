# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) · CR-110-BRC04 — the partner surface.
#           Screens: S142 *Who has been reading*
# Defects:  DEF-INT-5568 · DEF-INT-5569 · DEF-INT-5570 · DEF-INT-5571 — the
#           four unscoped reads. This file proves the OTHER strand (RLS,
#           and the partitions of `integration_run`), which is why it
#           cannot go red on any of them; its docstring says so.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE, proved under the NON-superuser
#           probe role) · hard-won law 14 (a guarantee the database enforces is
#           proved on PostgreSQL or it is not proved) · law 7 (a check that
#           reports zero over a scope it silently excludes) · B2 §3 (every
#           partition carries the tenant policy — DEF-027)
# Tests:    this file. The SQLite half — the query's OWN scoping, which is the
#           only tier that can go red — is
#           tests/test_def_int_5568_partner_tenancy.py.
# Impacts:  core/partitioning.py (`unguarded_partitions`) ·
#           apps/integrations/migrations/0002_rls_force.py · 0009
# ───────────────────────────────────────────────────────
"""The FIRST strand: what the database refuses, on the vendor that has one.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub \\
        pytest tests/test_def_int_5568_partner_tenancy_pg.py --reuse-db

⚠ **THIS FILE CANNOT GO RED ON THE DEFECT AND SAYS SO RATHER THAN PRETENDING.**
`DEF-INT-5568` is four queries that name no tenant. On a healthy PostgreSQL all
four are scoped anyway, by RLS `FORCE` — measured on 2026-09-17, on this
database, with all four sites still unfixed:

    under Lone Star Ridge's context, `IntegrationRun.objects.filter(
      connection__provider_key='erp_aclarian', direction=…)` returned 1 row,
      Lone Star Ridge's own, with Brazos Bend's two present in the table.

So a case here asserting *"the access log shows only this utility's reads"*
would have been green before the fix and green after it: law 7's *incapable of
failing*, wearing `requires_postgres` and therefore reading as rigorous. The
case that goes red lives next door, on SQLite, where RLS does not exist and the
query's own words are the only thing left.

**What this file is for instead is the half the SQLite tier cannot see**, and
both halves are needed before anyone may say the product is safe:

  1. RLS is really ON for the six integrations tenant tables and really scopes
     them — under `sbh_rls_probe`, a role that does NOT bypass row security,
     because the developer role would make a green mean nothing (`DEF-2717`).
  2. **`integration_run` is PARTITIONED and a partition read directly consults
     only its OWN policies.** `core.partitioning.unguarded_partitions` is the
     existing detector and its docstring — *"partitions missing ENABLE, FORCE,
     or a policy of their own"* — records that this has gone wrong before
     (`DEF-027`). It is asked here by name, on a real database, and the answer
     is asserted rather than described.
  3. The fix changed no behaviour where RLS was already doing the work: the
     same utility still sees the same rows.

⚠ **WHAT WOULD MAKE THESE CASES PASS WRONGLY:**

  * **A count of zero on an empty table looks exactly like a table nobody may
     read.** So both utilities are given their own rows and the assertions are
     identities, not zeroes.
  * **A superuser bypasses row security completely, `FORCE` included.** The
     probe self-verifies (`rls.assert_is_a_real_proof()`) and FAILS rather than
     skips when the role it was handed can see through the policies.
  * **A partition check on a database with no partitions reports zero
     truthfully and proves nothing.** So the number of partitions is asserted
     to be at least one before the unguarded count is asserted to be zero.
"""

from __future__ import annotations

import pytest
from django.db import connection as dj_connection

from apps.integrations import models, services
from apps.integrations.runners import serve
from core import crypto, partitioning
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_enabled_tables,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

PARTNER = "erp_aclarian"

#: The six integrations tables `0002_rls_force` and `0009` put under ENABLE +
#: FORCE. `integration_key_directory` is deliberately absent — migration `0011`
#: declares it RLS-EXEMPT so a key can name a utility before one is open.
TENANT_TABLES = (
    "integration_connection",
    "integration_credential",
    "integration_run",
    "integration_target_reference",
    "integration_consent",
    "integration_rate_limit",
)


def _connect(tenant, actor, key, hint):
    connection = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=PARTNER,
        label="Aclarian",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={"client_id": "aclarian"},
    )
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=key,
        masked_hint=hint,
        blind_index=crypto.blind_index(key, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
    )
    return connection


def _read(connection, hint, rows):
    caller = serve.PartnerCaller(
        connection=connection,
        credential_id=models.IntegrationCredential.objects.filter(connection=connection)
        .first()
        .id,
        hint=hint,
        tenant_id=connection.tenant_id,
        scopes=("payments",),
    )
    return serve.record_read(
        caller=caller, operation="serve_payment", rows=rows, window="Payments, 2 years"
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · the flags — ENABLE without FORCE leaves the owner exempt
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_the_six_integrations_tables_carry_both_enable_and_force():
    """`relrowsecurity` alone is ENABLE, which exempts the table OWNER — and the
    owner is the role this application connects as. A table enabled but not
    forced would pass every row-count check in this file while the product
    itself read every utility's rows."""
    forced = set(rls_enabled_tables())
    missing = [table for table in TENANT_TABLES if table not in forced]
    assert not missing, (
        f"{missing} do not carry BOTH relrowsecurity AND relforcerowsecurity "
        "(CLAUDE.md hard rule 1; integrations/0002 + 0009)"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · the partitions of `integration_run` — the second half of the mechanism
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_every_partition_of_integration_run_is_guarded_on_its_own():
    """⚠ **THE PARENT'S POLICY DOES NOT REACH A PARTITION READ DIRECTLY.**

    PostgreSQL applies a parent's policies to rows reached THROUGH the parent;
    a partition queried by its own name consults only its own. `DEF-027` is
    that lesson, and `core.partitioning.create_partition_sql` answers it by
    emitting the policy in the SAME statement that creates each partition.

    This asks the existing detector, by name, on a real database — and asserts
    there IS something to detect first, because *zero unguarded partitions* is
    also what a table with no partitions says (law 7: a check that reports zero
    over a scope it silently excludes).
    """
    with dj_connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE p.relname = 'integration_run' AND c.relkind = 'r' ORDER BY 1"
        )
        partitions = [row[0] for row in cursor.fetchall()]
    assert partitions, (
        "`integration_run` is in core.partitioning.ACTIVE_TABLES but this database has no "
        "partitions of it — a zero from the detector below would mean nothing"
    )
    unguarded = partitioning.unguarded_partitions("integration_run")
    assert unguarded == [], (
        f"{len(unguarded)} partition(s) of integration_run are missing ENABLE, FORCE or a "
        f"policy of their own: {unguarded}. Every access-log row in them is readable by any "
        f"utility that queries the partition directly (B2 §3, DEF-027). "
        f"`core.partitioning.ensure_partition_policies('integration_run')` repairs it."
    )


# ══════════════════════════════════════════════════════════════════════════
# 3 · the policies really scope, under a role that cannot bypass them
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_one_utilitys_connector_rows_are_invisible_under_the_other(
    brazos, lonestar, dana, erin, rls
):
    """Both utilities activate Aclarian and both have rows. Asserted through
    the DATABASE under `sbh_rls_probe`, so the application-layer filter this
    defect added is deliberately NOT in the path — this case is about the first
    strand and would still hold if every `tenant_id=` keyword were deleted."""
    with live_tenant_context(brazos.id):
        brazos_connection = _connect(brazos, dana, "sbh_live_7Q2F_brazos", "••••7Q2F")
        _read(brazos_connection, "••••7Q2F", 48_000)
    with live_tenant_context(lonestar.id):
        lonestar_connection = _connect(lonestar, erin, "sbh_live_4K8W_lonestar", "••••4K8W")
        _read(lonestar_connection, "••••4K8W", 7)

    assert_rls_scoped(
        rls,
        "integration_connection",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(brazos_connection.id)},
    )
    assert_rls_scoped(rls, "integration_run", owner=brazos, intruder=lonestar)
    assert_rls_scoped(rls, "integration_credential", owner=brazos, intruder=lonestar)


# ══════════════════════════════════════════════════════════════════════════
# 4 · the fix changed nothing where RLS was already doing the work
# ══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_the_access_log_read_returns_the_same_rows_it_did_before(brazos, lonestar, dana, erin):
    """`DEF-INT-5568` added a `tenant_id=` keyword to a query RLS already
    scoped. On this vendor that must be a no-op — the same utility, the same
    rows — or the fix is a behaviour change wearing a security fix's clothes."""
    with live_tenant_context(brazos.id):
        brazos_connection = _connect(brazos, dana, "sbh_live_7Q2F_brazos", "••••7Q2F")
        _read(brazos_connection, "••••7Q2F", 500)
        _read(brazos_connection, "••••7Q2F", 48_000)
    with live_tenant_context(lonestar.id):
        lonestar_connection = _connect(lonestar, erin, "sbh_live_4K8W_lonestar", "••••4K8W")
        _read(lonestar_connection, "••••4K8W", 7)
        mine = sorted(
            models.IntegrationRun.objects.filter(
                tenant_id=lonestar.id,
                connection__provider_key=PARTNER,
                direction=models.RUN_DIRECTION_INBOUND_READ,
            ).values_list("attempted", flat=True)
        )
    assert mine == [7]
    with live_tenant_context(brazos.id):
        theirs = sorted(
            models.IntegrationRun.objects.filter(
                tenant_id=brazos.id,
                connection__provider_key=PARTNER,
                direction=models.RUN_DIRECTION_INBOUND_READ,
            ).values_list("attempted", flat=True)
        )
    assert theirs == [500, 48_000], "the owning utility must still see all of its own"
    assert lonestar_connection.id != brazos_connection.id


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-INT-5568 (maintenance — 12-governance/22-product-maintenance-process.md)
# generated: 2026-09-17 by the DEF-INT-5568 lane
# checklist: A✔ B=n/a(no screen change) C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=… pytest tests/test_def_int_5568_partner_tenancy_pg.py
# exceptions: every case carries `requires_postgres` and SKIPS on the default suite rather than passing vacuously; this file states in its own docstring that it CANNOT go red on the defect and names the file that can
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
