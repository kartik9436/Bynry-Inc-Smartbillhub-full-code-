"""HUMAN-OWNED · HUMAN-REVIEW-PENDING — W1 rating migration (migration ordering is a
sensitive path, CLAUDE.md as amended by PO 2026-08-09: AI authors it, a human reviews it
later). SCHEMA-GAP fix: storage for two RATIFIED rules that had none.

1. BR-RAT-031 (CONFIRMED-AS-MODIFIED) "Save-draft resumable … draft schedules are excluded
   from plan-builder pickers until activated": B2 §2 declares `tariff_versions.effective_from`
   NOT NULL, so a half-built structure (tiers/TOU windows entered, no date yet) could not be
   stored at all. The column becomes NULLABLE — **a version with NULL effective_from IS the
   draft**; its structure children hang off it exactly as they do off a dated version, so
   resuming reloads them. `uq_tariff_versions_one_draft` is a PARTIAL unique
   (WHERE effective_from IS NULL) allowing exactly one open draft per tariff and leaving
   every dated version untouched.
   ⚠ REPORTED, not resolved: B2 §2 also signs an `EXCLUDE USING gist (tenant_id WITH =,
   tariff_id WITH =, daterange(effective_from, coalesce(effective_to,'infinity')) WITH &&)`
   no-overlap constraint. Migration 0001 never materialized it (btree_gist is not in
   db/000_extensions.sql), so there was NO existing DB constraint here to rewrite as
   partial — nothing was dropped or weakened by this migration. Overlap is guarded
   app-side by services._guard_window, which now reads activated versions only. Adding the
   gist constraint needs the extension (outside this lane's territory) and is left for the
   human review of this row.
   ⚠ **CLOSED 2026-09-29 (`DEF-RAT-8000`). THE REVIEW THIS LINE WAITED FOR NEVER
   HAPPENED, AND THE REPORT SAT HERE FOR SIX WEEKS WHILE A LIVE TENANT COLLECTED
   FOUR VERSIONS OF ONE SEWER SCHEDULE IN FORCE ON ONE DATE.** `rating/0045`
   installs `btree_gist`, `rating/0046` repairs the rows (and REFUSES rather than
   guessing a same-date tie), `rating/0047` adds `ex_tariff_versions_no_overlap`.
   Nothing in THIS migration changed. **The durable lesson is the one hard-won law
   1 already states: a note saying "left for the human review of this row" is a
   comment, not a plan — the row it pointed at carried no such item, and nothing
   anywhere counted it.**

2. BR-RAT-043 / US-RAT-002 §5 ("Eligibility checkboxes … stored on the plan", advisory-with-
   audit): `rate_plans.eligibility` jsonb. ADVISORY ONLY — written/read by the plan service
   and carried in the plan's audit before/after; it never gates assignment.

Authored from the signed rules + B2 Addendum r16, never raw B2 §2/§3.
Row recorded in 12-governance/09-human-review-ledger.md.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0003_rls_w1_policies"),
    ]

    operations = [
        migrations.AddField(
            model_name="rateplan",
            name="eligibility",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="tariffversion",
            name="effective_from",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="tariffversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("effective_from__isnull", True)),
                fields=("tariff",),
                name="uq_tariff_versions_one_draft",
            ),
        ),
    ]
