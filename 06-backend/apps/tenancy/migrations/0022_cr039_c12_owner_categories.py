# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave C task 12 — *"an owner as a typed record (kind ·
#           contact · linked to the customer they already are)"*, unblocked by
#           the PO ruling of 2026-08-27: *"category is okay, no richer text"*.
#           Screens: S8 Reference data (the new `owner_categories` card)
# Rules:    BR-TEN-150 (NEW — this list) · BR-TEN-031 (tenancy hosts, metering
#           owns) · BR-TEN-036 / DB-14 (seeded + tenant-extensible) ·
#           BR-TEN-067 (STRUCTURAL: the toggle cannot suppress it) ·
#           BR-TEN-030 (code immutable once used) · CLAUDE.md hard rule 1 (RLS
#           in the SAME migration)
# Question: OQ-502 (are the five closed, or may a tenant add a sixth?)
# Tests:    06-backend/tests/test_cr039_c12_premises_owner.py
# Impacts:  apps/tenancy/services.PremisesOwnerCategoryLookupHandler +
#           LOOKUP_LISTS + SEED_LIST_OWNERS + STRUCTURAL_REFERENCE_LISTS ·
#           apps/tenancy/fixtures/lookup_defaults.json (V2.48.0.3) ·
#           apps/metering/migrations/0040 (the FK that points here)
# ───────────────────────────────────────────────────────
"""tenancy 0022 — `premises_owner_categories`, BR-TEN-150's vocabulary.

HUMAN-OWNED (migration ordering AND RLS policies are CLAUDE.md 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-27 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). A row IS APPENDED in
`12-governance/09-human-review-ledger.md` for this file. Not RATIFIED without a
recorded human sign-off.

**WHAT A REVIEWER IS BEING ASKED TO CONFIRM**, in plain English with the figure:

  1. **That an owner's KIND is a reference row rather than a hardcoded enum.**
     Five rows are seeded on every tenant — owner-occupier, landlord, property
     manager, HOA, builder — and a tenant may add a sixth of its own, exactly
     as it may add an area or a meter size class. That extensibility is the
     HOUSE PATTERN (DB-14 / BR-TEN-036) and NOT something the PO ruled;
     `OQ-502` puts it to them.
  2. **The worked figure.** A brand-new tenant's `premises_owner_categories`
     holds **5 rows**, all `is_system = true`, and a tenant that turns the S111
     *"Load standard reference data"* toggle OFF still holds **5** — because
     this list is STRUCTURAL (BR-TEN-067). If it were discretionary the count
     would be **0**, and `premises_owners.category_id` is NOT NULL, so that
     tenant could not record a single owner.
  3. **That nothing bills off it.** No rate, no invoice line and no charge reads
     this table. It types a party; it prices nothing.
  4. **That reversing it loses a VOCABULARY, not a FACT.** Dropping this table
     requires dropping `premises_owners` first (the FK PROTECTs it), and that
     returns the product to its 2026-08-26 behaviour: a premises names its owner
     with `premises.owner_manager`, the free-text column this change does NOT
     remove (BR-MET-151).

ADDITIVE ONLY: one new table, no existing table altered, **nothing backfilled**.
The five rows arrive through the ordinary reference seed
(`lookup_defaults.json` V2.48.0.3 → `PremisesOwnerCategoryLookupHandler.seed`),
not through a data migration — so an existing tenant receives them the same way
it receives any other list, and a replay writes nothing (BR-TEN-012).

⚠ **RLS IS IN THIS SAME MIGRATION, NOT THE NEXT ONE.** A tenant table with no
policy is a hard-rule-1 violation for however long the pair is split, and this
lane was allocated ONE tenancy migration number (0022), so the split is not
available. The un-split form is strictly safer: there is no instant at which the
table exists without `FORCE ROW LEVEL SECURITY`.

⚠ **THE POLICY SQL IS IN `06-backend/db/`, NOT INLINE.** That is CR-004's own
posture for the hosted reference lists (`rls_tenancy_cr004_reference_lists.sql`)
and this list is one more of exactly those — so it follows the neighbour it will
sit beside rather than the inline form metering 0039 had to take.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0021_cr039_wave_f_commercial_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="PremisesOwnerCategory",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "premises_owner_categories",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_premises_owner_categories_tenant_code_ci",
                    )
                ],
            },
        ),
        PostgresOnlySQL(
            sql=load_db_sql("rls_cr039_c12_premises_owners.sql"),
            reverse_sql=migrations.RunSQL.noop,  # policies are never rolled back silently
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave C tasks 12-14 + PO ruling 2026-08-27 ("category is okay, no richer text") + BR-TEN-150
# generated: 2026-08-27 by the CR-039 wave C tasks 12-14 lane
# checklist: A✔ B=deferred(DDL+policy only — behaviour TCs assert through the handler) C✔ D=deferred(no new route: /lookups/owner_categories is the existing generic surface) E=deferred(no-frontend-half in this file) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row APPENDED)
# gates: makemigrations --check clean · ruff✔ black✔ · sqlite migrate applied (PostgresOnlySQL skips honestly)
# exceptions: E3 the DDL and the RLS policy are in ONE migration rather than a pair — one number was allocated to this lane, and the un-split form leaves no instant where the table exists without FORCE RLS · E3 DEF-639's NULLIF predicate rather than B2 §3's literal cast (identical guarantee) · E3 LIVE POSTGRES PROOF NOT RUN IN THIS CONTAINER — the G5 isolation sweep is the gate and is REPORTED as owed for this table
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
