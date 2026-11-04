# ── Trace ──────────────────────────────────────────────
# Story:    `CR-115-BRC05` §7 — domain verification, which the Product Owner
#           calls the long pole: our part is days, the utility's IT team is one
#           to three weeks, and Production is gated behind it.
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE on every tenant table; the policy
#           is in the SAME migration that creates the table) · B2 §3 (the
#           RLS-exempt list, which this table is NOT on) · 🔒 migration ordering
# Tests:    06-backend/tests/test_cr115_esp_adapters.py
# ───────────────────────────────────────────────────────
"""integrations 0013 — `integration_sending_domain`: what the ESP last said.

HUMAN-OWNED (🔒 migration ordering). HUMAN-REVIEW-PENDING — AI-authored
2026-09-17 under the PO ruling of 2026-08-09; the review-ledger row is in
`12-governance/09-human-review-ledger.md`.

THE EIGHTH TABLE, AND THE SEVENTH TENANT ONE
---------------------------------------------
It holds a provider's answer about a utility's own domain, so it is a tenant
table and gets the standard policy — **in this migration and not a later one**.
`integration_key_directory` (0011) is the module's one exemption and it is
declared, argued and on B2 §3's list; this is not that case and no exemption is
claimed.

WHY IT IS NOT `integration_connection.config`
-----------------------------------------------
⚠ **BECAUSE THAT WOULD HAVE WORKED UNTIL THE FIRST TIME A CLERK PRESSED SAVE.**
`services.update_connection` prunes the stored config down to the field names
the manifest still declares — `DEF-INT-5582`'s fix, and the right behaviour —
so a DNS answer parked there would be deleted by the next `PATCH`, with a
correct file count, a green suite and nothing to see. The records are a provider
FACT with a timestamp, not connection CONFIG, and the two have different
lifetimes.

NO BACKFILL, AND NONE IS POSSIBLE
-----------------------------------
No ESP adapter existed before the commit this migration ships in, so no domain
has ever been checked and there is nothing to carry forward. The table starts
empty on every deployment by construction rather than by a row count — the same
argument `manifests/sendgrid.py` makes about the rename, and for the same
reason: a count proves one deployment, a construction proves all of them.

REVERSING IT
-------------
`DeleteModel`. After a reverse the sending-domain endpoint answers *never
checked* for every connection and the panel asks for a check, which is the safe
direction — nothing is asserted about DNS that we no longer hold (hard-won
law 3).

⚠ **WHAT THIS MIGRATION DOES NOT DO: MAKE ANYTHING PUBLISH A RECORD.** The
utility's IT team does that, in their own DNS, on their own clock. This table
holds what the provider said about it and nothing else.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields
from core.rls import tenant_isolation_policy_sql

TABLE = "integration_sending_domain"


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
        ("integrations", "0012_cr115_run_mode_and_who"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationSendingDomain",
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
                ("domain", models.TextField()),
                (
                    "state",
                    models.TextField(
                        choices=[
                            ("verified", "verified"),
                            ("partial", "partial"),
                            ("unverified", "unverified"),
                            ("not_found", "not_found"),
                        ]
                    ),
                ),
                ("records", models.JSONField(blank=True, default=list)),
                ("checked_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("provider_text", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sending_domains",
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
            options={"db_table": TABLE},
        ),
        migrations.AddConstraint(
            model_name="integrationsendingdomain",
            constraint=models.UniqueConstraint(
                fields=("tenant", "connection", "domain"),
                name="uq_integration_sending_domain",
            ),
        ),
        # ⚠ **THE POLICY IS HERE AND NOT IN A LATER MIGRATION.** A tenant table
        # that exists for even one migration without one is a hard-rule-1 breach
        # with a window in it — `integration_rate_limit`'s own `0009` records
        # the same reasoning. SQLite has no RLS, so this is a PostgreSQL-only
        # guarantee and is never faked on the default suite (law 14).
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 (domain verification, the long pole) · the decision log of 2026-09-17 (PO questions 4 and 5, re-asked in plain words) · apps/integrations/models.py TENANT_TABLES
# generated: 2026-09-17 by the CR-115-BRC05 email-adapter lane
# checklist: A✔ B=n/a C✔ D✔(GET|POST /integrations/{key}/sending-domain reads and writes it) E=n/a(the panel is another lane's) F✔ G✔ H=PENDING(🔒 migration ordering — ledger row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · pytest tests/test_cr115_esp_adapters.py · G5 isolation (this table is NOT on the RLS-exempt list and claims no exemption)
# exceptions: SQLite carries no RLS; the policy assertion is PostgreSQL-only and never faked. No backfill and none is possible — no ESP adapter existed before this commit, so no domain has ever been checked.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
