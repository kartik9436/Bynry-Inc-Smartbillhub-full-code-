# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — P3.23 (indexes for SQL paging)
# Rules:    NFR-3 (every list pages on the server) · CR-168-BRC10 §7.3 (row
#           work/0031) · CLAUDE.md hard rule 1 (`tenant` leads every index —
#           the policy filters on it)
# Tests:    06-backend/tests/test_cr168_srv1_migrations_pg.py
# ───────────────────────────────────────────────────────
"""work 0031 — two indexes so Crews can page in SQL (P3.23).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

`technicians (tenant_id, crew_id)` counts a crew's members; `crews (tenant_id,
kind, name)` serves the three Crews lists in name order. ⚠ The third index §7.3
put in this row, `work_order_templates (tenant_id, active, name)`, is in
`metering/0071` because that table is metering's model and a work migration
cannot name it. The reverse drops both.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("work", "0030_rls_force_cr168")]

    operations = [
        migrations.AddIndex(
            model_name="crew",
            index=models.Index(fields=["tenant", "kind", "name"], name="ix_crews_tenant_kind_name"),
        ),
        migrations.AddIndex(
            model_name="technician",
            index=models.Index(fields=["tenant", "crew"], name="ix_technicians_tenant_crew"),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (row work/0031)
# generated: 2026-10-04 by CR-168 round 2 lane SRV-1
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# exceptions: the templates index lives in metering/0071 (reason above)
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
