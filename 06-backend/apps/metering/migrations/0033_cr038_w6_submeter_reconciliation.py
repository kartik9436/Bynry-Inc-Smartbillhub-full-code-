# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W6 (2026-08-26) — sub-meters   Screens: S14 (PRM-02)
# Rules:    BR-MET-125 (the master-vs-subs unaccounted gap is STORED per
#           premises per period AND REPORTED — PO verbatim *"(a) store +
#           report — keeps the door open"*) · BR-MET-025 (the tolerance) ·
#           CLAUDE.md hard rule 1 (RLS lands in 0033, immediately after) ·
#           hard rule 2 (percentages 6dp) · hard rule 3 (an explicit unit)
# Tests:    06-backend/tests/test_cr038_w6_submeters_devices.py
# Impacts:  apps/metering/submeter_reconciliation.py (the ONLY writer) ·
#           apps/metering/services.py (commit_read_batch calls it) ·
#           apps/metering/selectors.py (the premises report reads it)
# ───────────────────────────────────────────────────────
"""metering 0032 — `premises_submeter_reconciliations`, BR-MET-125's stored gap.
HUMAN-OWNED (migration ordering is a 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-26 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"). A row in
12-governance/09-human-review-ledger.md is OWED for this file; not RATIFIED
without human sign-off.

**WHAT A REVIEWER IS BEING ASKED TO CONFIRM**, in plain English with the figure:

  1. **That a DERIVED number is stored at all.** Everywhere else in this module
     a derivable figure is derived at read time so no copy can drift. The PO
     overrode that for this one figure on 2026-08-26 by choosing *"(a) store +
     report"* over report-only. This migration is that ruling in a table.
  2. **The worked figure the ruling was signed on:** a building's master meter
     reads **12,400 kWh** for August, its two sub-meters total **11,940 kWh**,
     so **460 kWh (3.71%)** is unaccounted for against a **3%** tolerance — one
     row, holding both inputs, the gap, the percentage and the 3% it was judged
     against.
  3. **That nothing bills off it.** No rate, no account and no charge touches
     this table. Billing common areas from the gap is the door BR-MET-125
     deliberately leaves open, and opening it is a new ruling.
  4. **That an uncomputable gap is stored as an ABSENCE.** When a sub-meter was
     not read, the row stores NULL quantities and the reason
     `submeter_sum_incomplete` with the sub named — never a gap computed from a
     short sum, which would report a missing reading as a loss.

ADDITIVE ONLY: one new table, no existing table altered, nothing backfilled.
The table is EMPTY after this migration and stays empty until a batch posts a
master's read (`services._store_submeter_reconciliations`).

⚠ **RLS LANDS IN 0033, IMMEDIATELY AFTER.** A tenant table with no policy is a
CLAUDE.md rule-1 violation between the two migrations and the pair must be
applied together — the same pairing metering 0014/0015 and 0024/0025 document.

⚠ **NOT PARTITIONED, DELIBERATELY** — the same call metering 0024 records. This
table grows with (premises × master × month), which for the <3,000-connection
utility this product serves is orders of magnitude smaller than `meter_reads`.

⚠ **`master_asset_id` IS A CROSS-MODULE FK metering→assets.** It is the SAME
edge `meter_reads.asset_id` already is (B2 §2 reviewed interface set), so this
adds no new interface — but a B2 §2 interface ROW naming this table is OWED and
is REPORTED rather than written here (04-docs/ is outside this lane's
territory).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0008_cr028_allocation_share"),
        ("metering", "0032_cr038_w3_read_method"),
        ("tenancy", "0019_cr035_wizard_parks_rls"),
    ]

    operations = [
        migrations.CreateModel(
            name="PremisesSubmeterReconciliation",
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
                ("period_month", models.DateField()),
                ("channel", models.TextField(default="total")),
                (
                    "master_consumption",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "submeter_sum",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "gap_quantity",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "gap_pct",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                (
                    "tolerance_pct",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("within_tolerance", models.BooleanField(blank=True, null=True)),
                ("unit", models.TextField()),
                ("status", models.TextField(default="computed")),
                ("reason", models.TextField(blank=True, null=True)),
                ("submeter_count", models.IntegerField(default=0)),
                ("submeters_resolved", models.IntegerField(default=0)),
                ("unresolved_submeters", models.JSONField(default=list)),
                ("source_read_ids", models.JSONField(default=list)),
                ("computed_at", models.DateTimeField()),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "master_asset",
                    models.ForeignKey(
                        db_column="master_asset_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="assets.asset",
                    ),
                ),
                (
                    "premises",
                    models.ForeignKey(
                        db_column="premises_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.premises",
                    ),
                ),
                (
                    "service",
                    models.ForeignKey(
                        blank=True,
                        db_column="service_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.service",
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
                "db_table": "premises_submeter_reconciliations",
                "indexes": [
                    models.Index(
                        fields=["tenant", "premises", "period_month"],
                        name="ix_premises_submeter_recon",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "premises", "master_asset", "channel", "period_month"),
                        name="uq_premises_submeter_recon",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W6 (BR-MET-124/125/135 as ruled 2026-08-26) + DEF-791
# generated: 2026-08-26 by the CR-038 W6 lane (schema half of the slice)
# checklist: A✔ B=deferred(table-half only — the behaviour TCs assert through the service) C✔ D=deferred(no-API-half — the endpoint is the same lane's separate file) E=deferred(no-frontend-half — the PRM-02 section is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09 — migrations 🔒 HUMAN-REVIEW-PENDING; the ledger row is REPORTED to the orchestrator, 12-governance/ being outside this lane's territory)
# gates: makemigrations --check clean · ruff✔ black✔ · sqlite migrate applied
# exceptions: stores a DERIVED figure, against this module's standing derive-don't-store posture — the PO ruled it stored (BR-MET-125 option (a), 2026-08-26) and the model docstring carries the reasoning · NO supersede chain, unlike meter_read_monthly_usage next door: no money reads this row, so a recompute updates in place (model docstring law 5) · B2 §2 interface row for the metering→assets FK is OWED and REPORTED (04-docs/ outside territory)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
