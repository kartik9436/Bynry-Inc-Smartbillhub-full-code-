# ── Trace ──────────────────────────────────────────────
# Story:   CR-115-BRC05 §7 — *"CUSTOM URLs ON A CONNECTOR"*, PO ruling
#          2026-09-17. R32 (*"they can give one or more URls to call. hence we
#          need a form to add them"*) · R36 (standard APIs enable/disable, and
#          are not editable).
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE on every tenant table) · B2 §3 (the
#          signed policy template, applied through `core.rls`) · BR-INT-003 (no
#          secret column where a reader can see it) · 🔒 migration ordering +
#          🔒 RLS policies (CLAUDE.md sensitive paths)
# Tests:   06-backend/tests/test_cr115_custom_apis.py ·
#          06-backend/tests/test_cr115_custom_apis_pg.py (the isolation probe)
# Impacts: apps/integrations/models.IntegrationApi · custom_apis.py ·
#          addressing.resolve_address (the `row` rung) · selectors.py · api.py
# ───────────────────────────────────────────────────────
"""integrations 0014 — `integration_api`, and its RLS policy in the same file.

HUMAN-OWNED (🔒 RLS policies + migration ordering). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-17 under the PO ruling of 2026-08-09; the review-ledger row
is in `12-governance/09-human-review-ledger.md`.

⚠ **THE POLICY IS IN THE MIGRATION THAT CREATES THE TABLE, NOT A LATER ONE.**
`integration_rate_limit` set that precedent in `0009` and `models.py` records
the reason in as many words: *a tenant table that exists for even one migration
without a policy is a hard-rule-1 breach with a window in it.* The five original
tables are guarded by `0002` only because they were all created in `0001`, which
is a fact about that pair and not a pattern to copy.

⚠ **THE UNIQUE IS THE PRODUCT RULE, NOT TIDINESS.** `CR-115-BRC05` §7.4: *"AN
API ALREADY CONFIGURED DROPS OUT OF THE DROPDOWN — one configuration per API,
never two."* The form hides a configured Kind and `custom_apis.add` refuses a
duplicate by name; this index is the half that is still true when two clerks
press Add in the same second. `is_standard` is part of the key so one operation
may hold BOTH an enablement record for the API we ship AND a clerk's custom
configuration — which is exactly the *"ours and theirs in ONE list"* the ruling
asks for.

⚠ **NO COLUMN HERE MAY EVER HOLD A SECRET.** A per-API key is a CREDENTIAL and
credentials live in `integration_credential` (`BR-INT-003`); §7.6 defers them
and `DEF-INT-5680` carries the deferral. `G75` refuses a secret column on
`integration_connection` and the same reasoning binds this table, whose rows are
read by screens and written into audit payloads.

⚠ **NOTHING IS BACKFILLED, AND THAT IS THE SAFE DIRECTION.** An empty table
means every connection behaves exactly as it did the minute before this ran:
`custom_apis.is_enabled` reads an ABSENT row as ON, so no scheduled sync stops
and no lookup changes. A backfill writing one `enabled=True` row per operation
per connection would be the same behaviour with thousands of rows to maintain,
and a window in which a half-finished data migration means *off*.

⚠ **THE DEPENDENCY WAS RE-DERIVED FROM THE PINNED TIP AT PUSH TIME** (CLAUDE.md
law 11). A sibling lane held an unpushed `0013` in the shared checkout while
this was written; a migration number taken from one checkout is the classic
*which world did the maximum come from* collision, and two leaves report as
*"Conflicting migrations detected"* naming neither lane.

SQLite has no RLS. The probe that proves this policy carries `requires_postgres`
and SKIPS there rather than passing vacuously (CLAUDE.md hard-won law 14).
"""


import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.rls import tenant_isolation_policy_sql

#: Named here rather than imported from `models.py`, so this migration reads the
#: same in a year when the model module has moved on — a migration is a record
#: of what was done, not a view of what is true now.
TABLE = "integration_api"


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(tenant_isolation_policy_sql(TABLE))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};")
    schema_editor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")



class Migration(migrations.Migration):

    dependencies = [
        # ⚠ **RE-DERIVED AT PUSH TIME, EXACTLY AS THIS FILE'S DOCSTRING SAID TO.**
        # It read `0012` while it was written, because a sibling lane held an
        # UNPUSHED `0013` in the shared checkout — a migration number taken from
        # one checkout is the classic *which world did the maximum come from*
        # collision (CLAUDE.md law 11). `0013_cr115_sending_domain` landed first,
        # and two leaves report as *"Conflicting migrations detected"* while
        # naming neither lane.
        ("integrations", "0013_cr115_sending_domain"),
        ("tenancy", "0044_cr094_i_account_document_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationApi",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("operation", models.TextField()),
                ("is_standard", models.BooleanField()),
                ("name", models.TextField(blank=True, null=True)),
                ("url", models.TextField(blank=True, null=True)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="apis",
                        to="integrations.integrationconnection",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "integration_api",
                "indexes": [
                    models.Index(fields=["connection"], name="ix_integration_api_connection")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("connection", "operation", "is_standard"),
                        name="uq_integration_api_connection_operation",
                    )
                ],
            },
        ),
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 (the 2026-09-17 rulings verbatim) + B2 §3 + hard rule 1
# generated: 2026-09-17 by the CR-115-BRC05 per-API lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=deferred(🔒 row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · pytest tests/test_cr115_custom_apis.py · tests/test_cr115_custom_apis_pg.py on PostgreSQL 16
# exceptions: none
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
