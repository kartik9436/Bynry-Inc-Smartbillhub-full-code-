# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) — "one `inline` run row per search session
#           summarising 14 lookups · 1 pick", CR-069 wave M task M1
# Rules:    BR-INT-048 (`C15` — an inline operation has a latency budget and no
#           job) · BR-INT-039 (every attempt is a durable record)
# ───────────────────────────────────────────────────────
"""integrations 0008 — the sixth trigger word: `inline`. HUMAN-OWNED
(migration ordering is a 🔒 sensitive path, CLAUDE.md).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); the review-ledger row is
in `12-governance/09-human-review-ledger.md` and states, in plain English with
the figure, exactly what a reviewer is being asked to agree to.

⚠ **THIS MIGRATION EMITS NO SQL, FOR `0005`'s REASON EXACTLY.** `trigger` is
`text` with no CHECK constraint (`0001_initial`), so `choices` is a Django-side
validation list; `sqlmigrate` prints the atomic block and nothing else, and no
`ALTER TABLE` cascades to `integration_run`'s yearly partitions. It is written
down anyway so a lane meeting an `AlterField` on a partitioned parent can see
that without running anything.

WHY A SIXTH WORD RATHER THAN REUSING `manual`
----------------------------------------------
`manual` already means *a person pressed Run it now* — and that path queues a
`core.jobs` row and answers `202` with a poll url. An inline operation does
none of it: the call goes out inside the request the clerk is waiting on, there
is no job row, and there is nothing to poll (`C15`: *a latency budget, not a
job*). Filing both under one word would leave S142 unable to tell a row that
has a job from a row that never could, which is the difference between
offering a poll and offering one that answers nothing.

⚠ **AND THE ROW IS PER SEARCH SESSION, NOT PER KEYSTROKE.** Fourteen lookups
and one pick is ONE row (`US-INT-042` TC-1). A row per keystroke would write
fourteen rows into a yearly-partitioned table to record one thing a clerk did.

ORDERING: depends on `integrations/0007` (wave K's `request_key`), this app's
own next number, RE-DERIVED AT PUSH TIME (CLAUDE.md law 11).

⚠ **IT WAS WRITTEN AS `0007` AND RENUMBERED, WHICH IS THE LAW WORKING RATHER
THAN A TYPO.** Wave K pushed `0007_k1_request_key.py` while this wave was being
built. Two leaves in one migration graph is not a test failure — Django refuses
**every test in the process** with *"Conflicting migrations detected; multiple
leaf nodes"*, naming neither lane and looking exactly like a broken tree
(`DEF-2872`). The number was re-derived against the pinned tip at push time,
which is the one moment the answer can be final.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0007_k1_request_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="integrationrun",
            name="trigger",
            field=models.TextField(
                choices=[
                    ("manual", "manual"),
                    ("scheduled", "scheduled"),
                    ("dispatcher", "dispatcher"),
                    ("webhook", "webhook"),
                    ("partner", "partner"),
                    ("inline", "inline"),
                ],
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042 (EP-INT-12 §3 TC-1 — "one `inline` run row per search session") · BR-INT-048 · BR-INT-039
# generated: 2026-09-06 by the CR-069 wave M build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 row in 09-human-review-ledger.md)
# gates: sqlmigrate prints no ALTER TABLE — a TextField's `choices` is Django-side only and the column has no CHECK constraint (0001_initial), so nothing cascades to integration_run's partitions · makemigrations --check clean · tests/test_us_int_042_gis.py (the session row reads `inline` and carries no job_id)
# exceptions: an AlterField that emits NO SQL, recorded for 0005's reason
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
