# ── Trace ──────────────────────────────────────────────
# Change:  CR-165-BRC10 round 2 task 3 — backfill of the tax chain.
# Rules:   CLAUDE.md hard rule 1 (`app.tenant_id` set per tenant — RLS FORCE,
#          `rating/0039`'s lesson) · BR-RAT-104 (corrections)
# Tests:   06-backend/tests/test_cr165_tax_versions_pg.py
# ───────────────────────────────────────────────────────
"""rating 0057 — every existing tax row joins a chain.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering). Ledger row 2026-10-03.

A row with no `corrects` starts its own chain (`chain_id = id`, v1). A
correction joins the chain of the row it corrects and takes that row's
version + 1 — walked in `created_at` order so a correction of a correction
finds its parent already stamped.

**No figure moves.** Measured before this lane: every tax row on every tenant
is UNDATED and no (tenant, jurisdiction, kind) group holds two rows
(`DEF-RAT-8060`'s own measurement), so every row is its own chain and v1.

DOWN PATH: nothing to undo — 0056's reverse drops both columns.
"""

from django.db import migrations

NO_TENANT = ""


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _forwards(apps, schema_editor):
    Tenant = apps.get_model("tenancy", "Tenant")
    Tax = apps.get_model("rating", "Tax")
    connection = schema_editor.connection
    for tenant_id in list(Tenant.objects.values_list("id", flat=True)):
        _set_tenant(connection, tenant_id)
        stamped: dict = {}
        rows = list(Tax.objects.filter(tenant_id=tenant_id).order_by("created_at", "id"))
        pending = rows
        # A correction may have been created before its parent in a clock-skewed
        # fixture; loop until every row is stamped, bounded by the row count.
        for _ in range(len(rows) + 1):
            if not pending:
                break
            later = []
            for row in pending:
                if row.corrects_id is None:
                    stamped[row.id] = (row.id, 1)
                elif row.corrects_id in stamped:
                    chain, version = stamped[row.corrects_id]
                    stamped[row.id] = (chain, version + 1)
                else:
                    later.append(row)
            pending = later
        for row in pending:  # a dangling link: the row starts its own chain
            stamped[row.id] = (row.id, 1)
        for row in rows:
            chain, version = stamped[row.id]
            Tax.objects.filter(pk=row.id).update(chain_id=chain, version_no=version)
    _set_tenant(connection, NO_TENANT)


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0056_cr165_tax_chains_and_authority_accounts"),
    ]

    operations = [migrations.RunPython(_forwards, migrations.RunPython.noop)]
