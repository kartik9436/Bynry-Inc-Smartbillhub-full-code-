"""audit 0007 — US-AUD-010: an actor that is NOT a person can name itself. HUMAN-OWNED
(migration ordering is a CLAUDE.md 🔒 sensitive path — the same marker `audit/0001`
carries, and this file shipped without it: `G7` caught that, correctly, and it is
why the gate asks for the WORD rather than for the reviewer's good intentions).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under PO ruling 2026-08-09 ("AI
will do it; we will review it later as human"). Migration ordering is a
CLAUDE.md 🔒 sensitive path; the row is in
12-governance/09-human-review-ledger.md and this file is not RATIFIED without a
human sign-off.

WHAT IT ADDS AND WHY THE PLATFORM NEEDED IT
-------------------------------------------
`BR-RBS-015` already ruled the behaviour — *the runbook is the audit actor,
named and versioned; it never borrows a user identity* — and the platform could
not express it. `audit_log` recorded ONE kind of actor, a user id, and a NULL
meaning "a system job" (`BR-AUD-003`), so a bill run, an import, a retention
sweep and a runbook all wrote the same blank.

Worked, because that is what makes it a defect rather than a tidy-up: the
returned-payments runbook applies a $25 fee to 43 accounts overnight — $1,075
charged while nobody is at the office. Six weeks later a customer disputes
theirs and a clerk opens the account history. She sees a blank actor she cannot
tell from a bug, or a colleague's name because the automation borrowed the login
of whoever set it up. It must read "Returned payments, version 4".

Three columns: `actor_kind` (what it is), `actor_label` (what it is called) and
`actor_version` (which version, where it has one).

⚠ ALL THREE ARE NULLABLE AND NOTHING IS BACKFILLED, AND THAT IS BR-AUD-002
RATHER THAN A PREFERENCE. This table allows no UPDATE anywhere — the
`audit_log_append_only` trigger from 0001 refuses one outright and would refuse
this migration too if it tried. So every row already in the trail keeps exactly
the meaning it had, and a reader tells the three cases apart without a backfill:

    actor_kind IS NOT NULL  → a NAMED non-person actor (new; carries no user id)
    actor_user_id IS NOT NULL → a person (unchanged)
    both NULL                 → an unnamed system job (BR-AUD-003, unchanged)

⚠ THE VERSION IS ITS OWN COLUMN AND IS NOT FOLDED INTO THE LABEL. Storing
"Returned payments, version 4" would put an English sentence in a database
column that eleven catalogues cannot then translate — B14 rule 35, and G15 has
already caught a value that was never actually translated once. The screen
composes that sentence in the reader's own language from the two facts. Text
rather than an integer because a runbook numbers itself `4` while a platform job
would name a build like `2.209.0`, and an integer column would refuse the second.

⚠ THE CHECK CONSTRAINT IS BR-RBS-015 AT THE LAST LINE OF DEFENCE. `core.audit`
already refuses a named actor that also carries a user id; this is the table
refusing it as well, so a future writer cannot reintroduce the borrowed login by
accident. Every existing row satisfies it trivially (all three columns NULL), so
adding it validates without rewriting anything.

TWO-VENDOR REALITY, RECORDED HONESTLY (the same posture as 0001)
---------------------------------------------------------------
On PostgreSQL `audit_log` is the PARTITIONED parent that 0001's raw DDL built,
not a Django-managed table. `ALTER TABLE ... ADD COLUMN` and `ADD CONSTRAINT ...
CHECK` on a partitioned parent both propagate to every existing and future
partition (PG11+), so `AddField`/`AddConstraint` are correct here and no
per-partition statement is needed. On the sqlite test tier the table is plain
and Django rebuilds it; the partitioning, the append-only trigger and RLS are
untestable there, exactly as 0001 says, and those assertions live in the G5
isolation suite against live PostgreSQL.

⚠ NO RLS STATEMENT IS ISSUED HERE ON PURPOSE. The policy on `audit_log` is
already ENABLE + FORCE from 0002/0003 and is written on the TABLE, not per
column, so three new columns are covered by it the moment they exist. A fresh
policy statement here would replace a reviewed one with an unreviewed one for no
gain (CLAUDE.md rule 1 and the 🔒 RLS path).
"""

from django.db import migrations, models

from apps.audit.models import AUDIT_ACTOR_CONSTRAINT


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0006_rls_cr067_error_diagnostics"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="actor_kind",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="actor_label",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="actor_version",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="auditlog",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(actor_kind__isnull=True, actor_label__isnull=True)
                    | models.Q(
                        actor_kind__isnull=False,
                        actor_label__isnull=False,
                        actor_user_id__isnull=True,
                    )
                ),
                name=AUDIT_ACTOR_CONSTRAINT,
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-010 (04-docs/05-modules/11-audit/06-epics/EP-AUD-01-write-contract.md) + BR-AUD-019 (04-docs/05-modules/11-audit/02-business-rules.md) + BR-RBS-015 (04-docs/05-modules/17-runbooks/02-business-rules.md) + CR-075 task L1 (04-docs/05-modules/17-runbooks/10-execution-plan.md)
# generated: 2026-09-06 by the CR-075 L1 audit-actor lane
# checklist: A✔ B=deferred(a migration draws nothing) C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 migration ordering, review-ledger row appended)
# gates: see the story's §4 — TC-RBS-12 shown RED at the pinned tip a10eae00 before this file existed, then GREEN; migrations applied on live PostgreSQL 16 and on the sqlite tier; the CHECK proved to bite on PostgreSQL by TC-9.
# exceptions: no backfill and none possible (BR-AUD-002 — the append-only trigger refuses an UPDATE on this table); no new RLS statement (the FORCE policy from 0002/0003 is on the table and already covers new columns); `actor_version` is TEXT not INTEGER, so a build-numbered platform job is expressible — stated rather than discovered later.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
