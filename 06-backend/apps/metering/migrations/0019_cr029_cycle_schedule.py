# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 RC-W1 task W1-T1 (B17 §6/§7) — the three schedule fields,
#           the eight-word frequency vocabulary, the backfill, and the legacy
#           calendar columns marked DEPRECATED (dropped at RC-W5, not here).
# Rules:    the pre-CR PO ruling 2026-08-23, verbatim — *"routes and cycles are
#           grouping only - so we will not tag late fees , etc - we can capture
#           start day, frequency, monthly, weekly daily, biweekly, once in two
#           months , quaterly etc and days to complete it ; give business names
#           to frequence - 1 word."* · D2 (*"Yes"* — unify the two cycle column
#           generations) · BR-MET-077 · BR-MET-078 (NO money column) ·
#           CLAUDE.md rule 1 (tenant scoping) · CLAUDE.md 🔒 sensitive paths
#           (migration ordering — HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will review it
# later as human") — a row in 12-governance/09-human-review-ledger.md is OWED
# for this file and is reported by the RC-W1 lane rather than written by it.
# ───────────────────────────────────────────────────────
"""metering 0019 — CR-029: `cycles.start_day` + `cycles.days_to_complete`, the
eight business frequency words, and the deprecation of the legacy calendar
columns.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-23 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). ⚠ Its row in `12-governance/09-human-review-ledger.md` is
OWED: the RC-W1 lane does not write governance files and has REPORTED the row
for the CR-029 close-out to add.

WHAT THIS MIGRATION DOES, IN ORDER
----------------------------------
1. Adds the two columns. Both NULLABLE with no default — an unscheduled cycle
   stays unscheduled, because inventing a start day here would put a read
   window on S27 that no human ever chose.
2. Maps every stored `frequency` onto its business word: `monthly` → `Monthly`,
   `bi_monthly` → `Bimonthly`, `quarterly` → `Quarterly` (CR-006 shipped
   exactly those three). Anything else is left EXACTLY as it is — a value this
   migration does not recognise is data, not a typo to be corrected.
3. Backfills `start_day` / `days_to_complete` from the legacy columns, day pair
   first and calendar dates second (`schedule.backfill_schedule` — the same
   function the service layer and the tests use, so the migration cannot drift
   from the rule it implements).
4. Marks the six legacy columns DEPRECATED with a Postgres column comment.

NOTHING IS DROPPED, AND THAT IS THE POINT (B17 §6: *deprecated → dropped at
W5*). `bill_date` is read by `apps/billing/issue.py` TODAY; `read_day_to` is
read by `apps/reports/dashboard_regions.py` TODAY; `window_start` is the S27
export's Read-window cell TODAY. Dropping a column billing reads is a change
with its own blast radius, and RC-W5 does it after every reader has moved.

NOTHING HERE IS MONEY (BR-MET-078). No rate, no amount, no currency, no
`late_day` — this CR HARDENS that rule rather than bending it, so no finance
re-sign is triggered (change process step 2: no ❄️ FROZEN B4/B5 figure moves).

RLS: NOTHING TO RE-POLICE. `cycles` has carried ENABLE + FORCE and the B2 §3
tenant-isolation policy since metering 0001/0002, and that policy is ROW-scoped
— a new column on an already-policed table is covered the moment it exists (the
verbatim posture of metering 0016 and 0018).

REVERSIBLE. The reverse un-maps the three business words to the CR-006 values
and blanks the two new columns. It cannot restore a frequency this migration
did not change, which is correct: it did not change it.
"""

from django.db import migrations, models

from apps.metering import schedule
from core.migrationtools import PostgresOnlySQL

#: The six columns CR-029 D2 supersedes. **NAMED, NOT DROPPED** — RC-W5 drops
#: them once every reader has moved (B17 §6/§7 W5-T2). The tests assert this
#: tuple and assert that no `RemoveField` operation appears below, so a lane
#: that "tidies up" one of them has to argue with a red test first.
LEGACY_DEPRECATED_COLUMNS: tuple[str, ...] = (
    "window_start",
    "window_end",
    "bill_date",
    "read_day_from",
    "read_day_to",
    "due_day",
)

#: What CR-006 shipped, and what CR-029 calls it. Only these three exist in any
#: deployed row; the wider spelling map lives in `schedule.LEGACY_FREQUENCIES`
#: for the WRITE path, where a client may still send the PO's own words.
_FREQUENCY_MAP = {"monthly": "Monthly", "bi_monthly": "Bimonthly", "quarterly": "Quarterly"}

_DEPRECATION_NOTE = (
    "DEPRECATED by CR-029 D2 (2026-08-23) — superseded by cycles.start_day + "
    "cycles.days_to_complete; the read window is derived, never stored. Still "
    "written and still true until RC-W5 drops this column."
)


def map_frequencies_and_backfill(apps, schema_editor):
    """Step 2 + step 3, in ONE pass over the rows.

    ⚠ **NO TENANT FILTER AND NO `app.tenant_id`, DELIBERATELY.** A migration
    runs as the schema owner across every tenant's rows; scoping it to one
    tenant would leave every other tenant's cycles on the old vocabulary, which
    is the failure mode the CLAUDE.md rule-1 scoping law exists to prevent in
    the opposite direction. RLS `FORCE` does not apply to the migration role,
    and no per-tenant decision is taken here — the mapping is the same for every
    row.
    """
    Cycle = apps.get_model("metering", "Cycle")
    for row in Cycle.objects.all().iterator():
        changed = []
        mapped = _FREQUENCY_MAP.get(str(row.frequency or "").strip().lower())
        if mapped and row.frequency != mapped:
            row.frequency = mapped
            changed.append("frequency")
        if row.start_day is None and row.days_to_complete is None:
            start_day, days = schedule.backfill_schedule(
                read_day_from=row.read_day_from,
                read_day_to=row.read_day_to,
                window_start=row.window_start,
                window_end=row.window_end,
            )
            if start_day is not None:
                row.start_day = start_day
                changed.append("start_day")
            if days is not None:
                row.days_to_complete = days
                changed.append("days_to_complete")
        if changed:
            row.save(update_fields=changed)


def unmap_frequencies(apps, schema_editor):
    Cycle = apps.get_model("metering", "Cycle")
    back = {word: legacy for legacy, word in _FREQUENCY_MAP.items()}
    for row in Cycle.objects.all().iterator():
        legacy = back.get(str(row.frequency or "").strip())
        row.frequency = legacy if legacy else row.frequency
        row.start_day = None
        row.days_to_complete = None
        row.save(update_fields=["frequency", "start_day", "days_to_complete"])


_COMMENT_SQL = "\n".join(
    f"COMMENT ON COLUMN cycles.{column} IS '{_DEPRECATION_NOTE}';"
    for column in LEGACY_DEPRECATED_COLUMNS
)
_UNCOMMENT_SQL = "\n".join(
    f"COMMENT ON COLUMN cycles.{column} IS NULL;" for column in LEGACY_DEPRECATED_COLUMNS
)


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0018_cr028_premises_geo"),
    ]

    operations = [
        migrations.AddField(
            model_name="cycle",
            name="start_day",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cycle",
            name="days_to_complete",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(map_frequencies_and_backfill, unmap_frequencies),
        # The deprecation lives in the DATABASE and not only in a docstring: a
        # DBA reading `\d+ cycles` is the person most likely to be misled by a
        # column nothing writes any more (hard-won law 1 — a comment claiming a
        # guarantee is not the guarantee, so this comment claims only what is
        # true: superseded, still maintained, dropped at W5).
        PostgresOnlySQL(sql=_COMMENT_SQL, reverse_sql=_UNCOMMENT_SQL),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §2/§6/§7 RC-W1 T1 + the CR-029 record in 12-governance/11-change-requests.md
# generated: 2026-08-23 by the CR-029 RC-W1 lane
# checklist: A✔ B=deferred(RC-W3 owns the screens) C✔(tests/test_cr029_rcw1_schedule.py) D✔ E✔ F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row OWED and reported)
# gates: makemigrations --check clean · metering suite green
# exceptions: (1) the RunPython walks every tenant's rows with no `app.tenant_id` — stated in the function docstring; the mapping is tenant-independent · (2) a frequency value this migration does not recognise is LEFT ALONE rather than defaulted
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
