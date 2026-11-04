# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — P2.12 / ruling 19 (raise in bulk
#           on units, one job per unit), idempotent
# Rules:    CLAUDE.md hard rule 6 (idempotency) · OQ-WRK-1497 CLOSED (no batch
#           number) · CR-168-BRC10 §7.3 (bulk raise)
# Tests:    06-backend/tests/test_cr168_srv2_bulk_raise_pg.py
# ───────────────────────────────────────────────────────
"""work 0032 — `work_bulk_raises`: the first answer to one bulk raise, keyed by
the client's idempotency key, `UNIQUE (tenant_id, idempotency_key)`.

HUMAN-OWNED · 🔒 HUMAN-REVIEW-PENDING (idempotency keys + migration ordering are CLAUDE.md
sensitive paths). Row in `12-governance/09-human-review-ledger.md`.

Down: the table is dropped. Nothing else reads it; a rollback loses only the
memory of which presses were already answered, so a repeated press after a
rollback would raise its jobs again — stated in CR-168 §15.
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0058_storm_water_flat_size"),
        ("work", "0031_cr168_paging_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkBulkRaise",
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
                ("idempotency_key", models.TextField()),
                ("actor_id", models.UUIDField(blank=True, null=True)),
                ("answer", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
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
                "db_table": "work_bulk_raises",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "idempotency_key"),
                        name="uq_work_bulk_raises_tenant_key",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (bulk raise) · §8 R3 SRV-2
# generated: 2026-10-04 by CR-168 round 3 lane SRV-2
# checklist: A✔ B=n/a C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 → review-ledger row)
# gates: migrate up → down → up on PostgreSQL 16
# exceptions: none
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
