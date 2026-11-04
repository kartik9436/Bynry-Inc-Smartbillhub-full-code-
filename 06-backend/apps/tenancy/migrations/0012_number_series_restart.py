# ── Trace ──────────────────────────────────────────────
# Change:   CR-005 — SET-08 Numbering: "Restart counter each year/month" per
#           entity.   Screens: S8 → Configure → Numbering / r10 SET-08
# Rules:    BR-TEN-035 clause (b) (restart period; a restart needs the date token
#           that keeps the restarted number unique) · CLAUDE.md rule 1 (tenant
#           scoping) · CLAUDE.md rule 4 (issued numbers are never re-minted)
# Tests:    06-backend/tests/test_cr005_numbering_set08.py
# Questions: OQ-252 (may restart be set on a format with no date token — refused)
# ───────────────────────────────────────────────────────
"""tenancy 0012 — `number_series.restart_period` + `number_series.period_counted`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-17 under the PO ruling of 2026-08-09 ("AI will do it; we
will review it later as human"), implementing CR-005 (PO 2026-08-16), verbatim:
*"Date-token formats roll the counter per period option: 'Restart counter each
year/month — Yes/No' per entity"*.

────────────────────────────────────────────────────────────────────────────
WHY TWO COLUMNS AND NOT ONE BOOLEAN
────────────────────────────────────────────────────────────────────────────
`restart_period` is the POLICY (`never` · `yearly` · `monthly`).
`period_counted` is the POSITION — which year or month the counter is currently
counting in (`""` · `"2026"` · `"2026-08"`).

The policy alone cannot decide a restart. "Restart every January" is only
actionable against a record of the January the counter last served: without it,
EVERY allocation in January looks like the first one and the counter resets on
each bill in the run. The position is written under the same `SELECT … FOR
UPDATE` that hands out the sequence (`apps.tenancy.services.allocate_series_number`),
so two concurrent issuances at midnight on 1 January cannot both believe they
are the first — one waits for the row lock and reads the position the other
just wrote.

────────────────────────────────────────────────────────────────────────────
RLS: NOTHING NEW IS NEEDED, AND HERE IS WHY THAT IS TRUE RATHER THAN HOPED
────────────────────────────────────────────────────────────────────────────
**NO TABLE IS CREATED — this migration adds TWO COLUMNS.** `number_series` is
already ENABLE + FORCE under its W0 policy, applied verbatim from
`06-backend/db/rls_tenancy_w0.sql` by `0003_rls_w0_policies`; that policy gates
the ROW, so columns added to a gated row are gated. Same posture and the same
reasoning as `0011_uom_service_scope` (one column on `uoms`) and
`0006_service_gl_attributes` (two on `tenant_services`). Writing a fresh policy
here would SHADOW the signed original, which is worse than adding none.

The claim is backed by a sweep rather than by this paragraph:
`tests/test_tenant_isolation.py` walks every tenant-scoped table rather than a
hand-kept list. Postgres only — the sqlite test DB cannot exercise RLS.

────────────────────────────────────────────────────────────────────────────
ORDERING (🔒) AND BACKFILL
────────────────────────────────────────────────────────────────────────────
Depends on tenancy/0011 only. No cross-app edge is added and no FK is created,
so there is no ordering hazard: this migration can only run after the table it
alters exists (tenancy/0001).

**EVERY EXISTING ROW LANDS AT `never` / `""`, WHICH IS EXACTLY WHAT IT DOES
TODAY.** A tenant's numbering therefore does not move because a column arrived —
the counter that was running keeps running, unbroken, and the first time
anything behaves differently is the moment an admin chooses a restart on SET-08
and saves it. That is the only safe default here for a reason stronger than
caution: turning restart ON retroactively would send live counters back to 1,
and a re-minted bill number lands on a row hard rule 4 forbids anyone to fix.

**THE THIRTEEN NEW SERIES ROWS ARE NOT SEEDED BY THIS MIGRATION, ON PURPOSE.**
Seeding them is a per-TENANT write and this migration runs once for the whole
database; `app.tenant_id` is unset here, so a loop over tenants would be writing
tenant rows outside tenant context (CLAUDE.md rule 1) with RLS FORCE on. The
seed belongs to `apps.tenancy.services._seed_number_series`, which provisioning
calls for every new tenant and which `manage.py seed_demo --tenant <subdomain>`
now calls for a tenant that already exists — the same repair door DEF-163's
notice templates used, for the same reason, four days earlier.

The CHECK constraint is added in the same operation set as the column, so there
is never a window in which a row could hold an unknown policy.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0011_uom_service_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="numberseries",
            name="restart_period",
            field=models.TextField(default="never"),
        ),
        migrations.AddField(
            model_name="numberseries",
            name="period_counted",
            field=models.TextField(default=""),
        ),
        migrations.AddConstraint(
            model_name="numberseries",
            constraint=models.CheckConstraint(
                condition=models.Q(restart_period__in=["never", "yearly", "monthly"]),
                name="ck_number_series_restart_period",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-012@80cdedf (the story this extends; the CHANGE is CR-005 — 12-governance/11-change-requests.md, PO 2026-08-16, SET-08)
# generated: 2026-08-17 by the CR-005 SET-08 Numbering lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(human review — row in 12-governance/09-human-review-ledger.md, four statements put to the PO)
# gates: pytest tests/test_cr005_numbering_set08.py · tests/test_us_ten_012_numbering.py · tests/test_be06_numbering.py
# exceptions: none stubbed. OQ-250 (pad minimum) and OQ-252 (restart without a date token) are OPEN and are answered in the direction that refuses nothing already stored
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
