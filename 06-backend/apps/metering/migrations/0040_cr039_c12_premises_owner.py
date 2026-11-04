# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave C tasks 12-13 — *"an owner as a typed record"* and
#           *"migrate the free-text names"*. PO ruling 2026-08-27, verbatim:
#           *"category is okay, no richer text"*.
#           Screens: S14 premises list · S16 guided add · PRM-01 edit modal ·
#           PRM-04 the owner-matching review surface
# Rules:    BR-MET-150 (NEW — the typed record) · BR-MET-151 (NEW — the
#           migration backfills NOTHING and matching is a human act) ·
#           BR-TEN-150 (the category vocabulary this FKs into) ·
#           CLAUDE.md hard rule 1 (RLS in the SAME migration)
# Question: OQ-500 (does the typed owner become the default payer? — this
#           migration deliberately changes nothing about that) · OQ-501 (is
#           `owner_manager` ever retired?) · OQ-503 (must a paying owner be
#           reachable?)
# Tests:    06-backend/tests/test_cr039_c12_premises_owner.py ·
#           06-backend/tests/test_cr039_c13_owner_migration.py
# Impacts:  apps/metering/models.PremisesOwner + Premises.owner ·
#           apps/metering/services (create/update/match) · selectors ·
#           04-docs/02-decisions/02-database-design-brief.md addendum r21
# ───────────────────────────────────────────────────────
"""metering 0040 — `premises_owners` and `premises.owner_id`, BR-MET-150.

HUMAN-OWNED (migration ordering AND RLS policies are CLAUDE.md 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-27 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). A row IS APPENDED in
`12-governance/09-human-review-ledger.md` for this file. Not RATIFIED without a
recorded human sign-off.

**WHAT A REVIEWER IS BEING ASKED TO CONFIRM**, in plain English with the figure:

  1. **That the owner of an address becomes a real party record.** Today a
     premises holds one free-text box with a name in it. After this, it points
     at a row that carries a KIND (landlord, builder, …), an email, a phone and
     — when they are one — a link to the customer they already are. The PO
     ruled for this on 2026-08-27: *"category is okay, no richer text"*.
  2. **THE WORKED FIGURE, AND IT IS A ZERO ON PURPOSE.** The demo tenant holds
     **twelve** premises carrying a free-text owner name — *Whitfield Rentals
     LLC*, *Chen, David*, *Mason Rd Holdings*, *Riverbend Apts LP*,
     *Rodriguez, M.*, *Northwind Mfg.*, *Silver Creek Duplex Holdings*, *Mill
     Pond Apartments LP*, *Creekside Laundromat*, *Quarry Hill Diner*, *Ridge
     Property LLC*, *Kestrel Park Developments*. **This migration creates
     ZERO owner rows and links ZERO premises.** Every one of those twelve is
     left exactly as it was found, and appears on the matching review list.
  3. **WHY ZERO, because it looks like a job left half done and it is not.**
     The ruling's own caveat, verbatim: *"They are real data on a live tenant. A
     flagged migration that offers each name for matching is the shape; silently
     guessing which string is which party is not."* An `LLC` suffix is not
     evidence of a landlord and a personal name is not evidence of an
     owner-occupier; a backfill that guessed would put a claim about a real
     party into a real customer's database, permanently, with nobody's name on
     it. BR-MET-151.
  4. **That nothing bills differently the moment this applies.**
     `customers.services.open_account` still reads `premises.owner_manager` for
     the default payer, exactly as it did on 2026-08-26. Whether the typed owner
     should supersede it is `OQ-500` and is NOT decided in this change.
  5. **That reversing it loses a STRUCTURE, not a FACT.** Dropping both objects
     returns the product to *"a premises names its owner with a string"*. Every
     one of the twelve names is still in `premises.owner_manager`, because this
     change never moved them out of it.

ADDITIVE ONLY: one new table, one new NULLABLE column on `premises`, **nothing
backfilled** and no existing value read or rewritten.

⚠ **RLS IS IN THIS SAME MIGRATION, NOT THE NEXT ONE.** `premises_owners` holds
named parties with contact details, and three of the five occupancy states make
one of them the party who PAYS — so an instant where it exists without `FORCE
ROW LEVEL SECURITY` is a hard-rule-1 violation on the most disclosure-sensitive
table this lane touches. Metering 0024/0025 and 0033/0034 split the pair and
each documents that the halves must be applied together; this lane was allocated
ONE metering number (0040), and the un-split form is strictly safer anyway.

⚠ **NUMBERED 0040 BY ALLOCATION, AND 0038 IS A SIBLING LANE'S.** Measured, not
assumed (`ls apps/metering/migrations/`): this branch holds 0037 and 0039 and
NOT 0038, which a concurrent lane holds on another branch. This migration
therefore depends on **0039**, the highest number actually present here. **AT
MERGE THE INTEGRATOR MUST CONFIRM THE CHAIN IS LINEAR** — if 0038 lands between
0037 and 0039, nothing here moves; if it lands after 0039, this `dependencies`
list is what needs re-pointing, or Django reports *"Conflicting migrations
detected; multiple leaf nodes in the migration graph"*. Linearise, do not add a
merge node: metering 0039 and rating 0018 both record the same call and the same
reason — a merge node is a no-op that documents nothing, and these migrations are
purely additive so the order carries no meaning to recover.

⚠ **THE UNIQUE INDEX ON `LOWER(name)` IS LOAD-BEARING, NOT TIDINESS.** The
ruling's reason for a typed record is *"the same landlord across twelve
addresses is one party rather than twelve unrelated strings"*. Matching happens
one premises at a time, so without this index a clerk working down the review
list creates twelve parties named *Whitfield Rentals LLC* and the change
achieves nothing while appearing to work. The index makes the second attempt
refuse and the service turns that refusal into *"this owner already exists —
link to it"*.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    # ⚠ DEPENDS ON 0039 AND 0038 IS A SIBLING LANE'S — see the module docstring.
    dependencies = [
        ("metering", "0039_oq421_asset_monthly_usage"),
        # The category vocabulary this table's NOT NULL FK points at. Naming it
        # here is what stops `migrate` running these two in the wrong order on a
        # fresh database.
        ("tenancy", "0022_cr039_c12_owner_categories"),
        # `customer_id` is the cross-module FK of B2 addendum r21. The customers
        # module's own leaf is named so the target table exists first.
        ("customers", "0028_cr039_wd_transfer_and_case_numbers"),
    ]

    operations = [
        migrations.CreateModel(
            name="PremisesOwner",
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
                ("name", models.TextField()),
                ("contact_name", models.TextField(blank=True, null=True)),
                ("email", models.TextField(blank=True, null=True)),
                ("phone", models.TextField(blank=True, null=True)),
                ("source_owner_manager", models.TextField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("is_sample", models.BooleanField(default=False)),
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
                (
                    "category",
                    models.ForeignKey(
                        db_column="category_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owners",
                        to="tenancy.premisesownercategory",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        db_column="customer_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="customers.customer",
                    ),
                ),
            ],
            options={
                "db_table": "premises_owners",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("name"),
                        name="uq_premises_owners_tenant_name_ci",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="premises",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                db_column="owner_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="premises_set",
                to="metering.premisesowner",
            ),
        ),
        PostgresOnlySQL(
            sql=load_db_sql("rls_cr039_c12_premises_owners_metering.sql"),
            reverse_sql=migrations.RunSQL.noop,  # policies are never rolled back silently
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave C tasks 12-14 + PO ruling 2026-08-27 ("category is okay, no richer text") + BR-MET-150/151
# generated: 2026-08-27 by the CR-039 wave C tasks 12-14 lane
# checklist: A✔ B=deferred(DDL+policy only — behaviour TCs assert through the services) C✔ D=deferred(no-API-half in this file) E=deferred(no-frontend-half in this file) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row APPENDED)
# gates: makemigrations --check clean · ruff✔ black✔ · sqlite migrate applied (PostgresOnlySQL skips honestly)
# exceptions: E3 the DDL and the RLS policy are in ONE migration rather than the metering 0024/0025 pair — one number was allocated, and the un-split form leaves no instant where a table of named parties exists without FORCE RLS · E3 DEF-639's NULLIF predicate rather than B2 §3's literal cast (identical guarantee) · E3 depends on 0039 while a sibling lane holds 0038 — the integrator confirms the chain is linear at merge · E3 a NEW cross-module FK COLUMN metering -> customers, B2 addendum r21, REVIEW OWED at the next B2 sitting · E3 LIVE POSTGRES PROOF NOT RUN IN THIS CONTAINER — the G5 isolation sweep is the gate and is REPORTED as owed for this table
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
