# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, tag it, report
#           it, remove it)   Screens: S8 (Settings → Company profile), S62
# Rules:    BR-TEN-060 (an unwired seam is a NAMED line, not a skip — the row
#           this table stores) · BR-TEN-063 (atomic per module, idempotent per
#           tenant — the UNIQUE key) · BR-TEN-056 clause 3 (report honestly) ·
#           CLAUDE.md rule 1 (tenant-scoped + RLS FORCE) · B2 §3 policy template
# ───────────────────────────────────────────────────────
"""tenancy 0009 — `sample_data_runs`, plus its RLS policy.

HUMAN-OWNED (migration ordering + RLS policy are CLAUDE.md 🔒 sensitive paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a human sign-off.

WHY THE TABLE LANDS AHEAD OF THE THING IT REPORTS ON
-----------------------------------------------------
US-TEN-019 has four parts and this migration serves exactly one of them — the
HONESTY REPORT (BR-TEN-060). The other three (the `is_sample` tag, the sample
RECORDS, the removal) cannot be built from this module at all: BR-TEN-057 puts
`is_sample boolean NOT NULL DEFAULT false` on `premises`, `units`,
`service_points`, `assets`, `asset_assignments` and `meter_reads`, and every
one of those tables is owned by apps/metering or apps/assets. BR-TEN-013 and
B1's boundary rule forbid tenancy adding a column to another module's table,
and BR-TEN-057 says so in its own words: the tag is written "only by that
module's own service function on the sample path, never by tenancy directly".

So this lane builds the orchestrator and its ledger, and the ledger's first
honest content is *"every module: skipped, seam_not_wired"*. That is not a
placeholder — it is the DEF-016 prevention doing its job before there is
anything to prevent. A run that reports truthfully that it did nothing is worth
having; one that reports success is exactly the defect BR-TEN-060 exists to end.

THE POLICY, AND WHY IT IS IN THE SAME MIGRATION HERE
-----------------------------------------------------
This repo's convention splits table and policy (tenancy 0007/0008, customers
0002, metering 0004). That convention exists so a reviewer can read a policy
diff alone. It is followed in SPIRIT rather than in numbering here: the policy
SQL lives in its own reviewable file, `06-backend/db/rls_tenancy_sample_data.sql`,
and this migration only loads it — but it loads it in the SAME migration as the
CREATE, because a tenant-scoped table that exists for even one migration
without ENABLE + FORCE is a table an operator can be mid-deploy on with no
isolation (B2 §7's ordering rule read strictly). One file, one reviewable
policy, no window.

Postgres only for the policy half: the sqlite test DB cannot run RLS, so
`PostgresOnlySQL` skips it there honestly. Live cross-tenant proof is the G5
isolation suite's job (NFR-10, zero tolerance) — see
tests/test_us_ten_019_sample_data.py::test_us_ten_019_tc11_*.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="SampleDataRun",
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
                ("module", models.TextField()),
                ("outcome", models.TextField()),
                ("seeded_count", models.IntegerField(default=0)),
                ("reason_code", models.TextField(blank=True, null=True)),
                ("detail", models.TextField(blank=True, null=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "sample_data_runs"},
        ),
        migrations.AddConstraint(
            model_name="sampledatarun",
            constraint=models.UniqueConstraint(
                fields=("tenant", "module"), name="uq_sample_data_runs"
            ),
        ),
        migrations.AddConstraint(
            model_name="sampledatarun",
            constraint=models.CheckConstraint(
                condition=models.Q(outcome__in=("seeded", "skipped", "failed")),
                name="ck_sample_run_outcome",
            ),
        ),
        migrations.AddConstraint(
            model_name="sampledatarun",
            constraint=models.CheckConstraint(
                condition=models.Q(outcome="seeded") | models.Q(reason_code__isnull=False),
                name="ck_sample_run_reason_required",
            ),
        ),
        PostgresOnlySQL(
            sql=load_db_sql("rls_tenancy_sample_data.sql"),
            reverse_sql=migrations.RunSQL.noop,  # policies are never rolled back silently
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 (EP-TEN-03 — the sample-data run ledger; the tag, the records and the removal are NOT in this lane and cannot be, see the module docstring)
# generated: 2026-08-15 by story-coder (tenancy/identity lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: `manage.py migrate` from EMPTY on PostgreSQL 16✔ · `makemigrations --check --dry-run` reports `No changes detected`✔ · pytest tests/test_us_ten_019_sample_data.py 16 tests (sqlite 15 passed/1 vendor-skipped; live Postgres 16 passed)✔ · run_gates: 19 PASS / 2 FAIL / 0 SKIP — and BOTH FAILS ARE OTHER LANES' (G6 names apps/ledger/billing_seam.py:41; G7 names 6 files under apps/ledger, apps/notifications and apps/billing with no review-ledger row). Enumerated mechanically, not assumed: no file of this lane appears in either. The baseline when this lane started was 20 PASS / 0 FAIL (G21 arrived from a concurrent lane mid-session) · RED-PROVED: with the policy removed from db/rls_tenancy_sample_data.sql the isolation TC fails under the non-superuser probe role with `AssertionError: sample_data_runs: LEAK — tenant … can read tenant …'s rows`; restored, it passes. The sqlite half is genuinely skipped, not silently green: PostgresOnlySQL is what makes that honest
# exceptions: the policy rides the SAME migration as the CREATE rather than a separate numbered file (the repo convention), because a tenant-scoped table without ENABLE+FORCE for even one migration step is a real deploy window — the policy SQL still lives in its own reviewable file, which is what the convention is FOR · the `is_sample` columns BR-TEN-057 names are NOT added here and cannot be: every one is on a metering- or assets-owned table (B1 boundary rule, BR-TEN-013) · no `is_sample` column means no sample RECORDS and no removal path in this lane — the run ledger reports every module as `skipped/seam_not_wired` and that is the honest state, not a stub
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
