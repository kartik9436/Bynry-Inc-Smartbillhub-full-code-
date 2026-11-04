# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 wave B task 6/7 — "say what happened when a tenant was
#           seeded". PO 2026-08-26, verbatim: *"we need to look at what of 1
#           job fails and does not load the data - them what we do with rest of
#           the jobs - we should continue and should not lose entire setup"*.
#           Screens: S8 (Settings → Company profile → Sample data, BR-TEN-069)
# Rules:    BR-TEN-060 (an unwired seam is a NAMED line, not a skip — a row per
#           module, UNCHANGED by this migration) · BR-TEN-063 (atomic per
#           module, idempotent) · CLAUDE.md rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_cr039_sample_block_reporting.py
# ───────────────────────────────────────────────────────
"""tenancy 0020 — `sample_data_runs.blocks`, the per-block breakdown.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-26 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human").

⚠ **A ROW IN `12-governance/09-human-review-ledger.md` IS OWED FOR THIS FILE
AND THE LANE THAT WROTE IT COULD NOT ADD ONE.** This lane is barred from
editing `12-governance/`, and G7 requires the marker above AND a ledger row
matched by this file's repo-relative path. The row is REPORTED in the lane
report with its text drafted; until it lands, G7 names this file. That is the
guard working, not a surprise — it is recorded here so the next reader knows
the gap is declared rather than missed.

WHAT IT DOES, AND WHAT IT DELIBERATELY DOES NOT
------------------------------------------------
ONE additive column, `blocks jsonb NOT NULL DEFAULT '[]'`.

It does NOT touch `uq_sample_data_runs (tenant_id, module)`, and that restraint
is the design decision worth recording. The obvious way to report per block is
to make the row per block — and that would re-shape BR-TEN-060, which says in
its own words *"a row per module with a machine-readable reason_code and a
sentence an operator can act on"*. A lane does not amend a signed rule to make
a screen easier to write; it carries the extra fact alongside. So the module
row keeps its meaning, its worst-first merge and its CHECK constraint
(`ck_sample_run_reason_required` — a non-seeded row MUST say why), and the
per-block detail rides in a column beside it.

⚠ **NO BACKFILL, ON PURPOSE.** A row written before today reconciled up to
three blocks into one verdict, and there is no honest way to attribute that
verdict to one of them after the fact — inventing an attribution is precisely
the class of error CR-039 exists to stop. Legacy rows therefore carry `[]`, the
screen says "recorded before block-level reporting" rather than "no blocks",
and the next run fills the column truthfully.

⚠ **NO RLS CHANGE IS NEEDED AND NONE IS MADE.** The policy on
`sample_data_runs` is row-scoped on `tenant_id` (`db/rls_tenancy_sample_data.sql`,
migration 0009); adding a column to a table already under `FORCE ROW LEVEL
SECURITY` inherits that policy. Rollback is a clean column drop and loses only
the breakdown.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0019_cr035_wizard_parks_rls"),
    ]

    operations = [
        migrations.AddField(
            model_name="sampledatarun",
            name="blocks",
            field=models.JSONField(blank=True, default=list),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 (EP-TEN-03 — the sample-data orchestrator and its honest report) + CR-039 wave B, "B · Say what happened" (12-governance/11-change-requests.md)
# generated: 2026-08-26 by story-coder (CR-039 wave B lane)
# checklist: A✔ B=deferred(a migration draws nothing — the screen half is 07-frontend/src/features/tenancy/SettingsSampleData.tsx, shipped in the same lane) C✔ D=deferred(a migration serves no route — GET/POST /settings/sample-data* are the API half, shipped in the same lane) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check --dry-run reports NO change for tenancy (one PRE-EXISTING pending migration in apps/customers, another lane's) · ruff✔ black✔ · pytest tests/test_cr039_sample_block_reporting.py 17 passed · tests/test_us_ten_019_sample_data.py 20 passed / 1 skipped · G7 PROVED to be watching this file: removing HUMAN-OWNED from the docstring moves its finding count 26 → 27, and restoring it moves it back
# exceptions: ⚠ A ROW IN 12-governance/09-human-review-ledger.md IS OWED AND THIS LANE COULD NOT ADD ONE — it is barred from editing 12-governance/, so the row is REPORTED with its text drafted. ⚠ MEASURED, because it changes what the reader should expect: G7 does NOT currently name this file for the missing row. Its stub-detection reads a body of one `AddField` as stub-only, so requirement (a) — the HUMAN-OWNED marker — is all it asks of this file. That is a GAP IN THE GUARD rather than a licence: "migration ordering" is 🔒 on CLAUDE.md's own list and a schema change under that glob should carry a ledger row whether or not its body is one line · NO BACKFILL: a row written before this column reconciled up to three blocks into one verdict and there is no honest way to attribute that verdict to one of them afterwards, so legacy rows carry `[]` and the screen says "recorded before block-level reporting" rather than "no blocks" · NO RLS CHANGE: `sample_data_runs` is already under FORCE ROW LEVEL SECURITY from migration 0009 and a new column inherits its policy
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
