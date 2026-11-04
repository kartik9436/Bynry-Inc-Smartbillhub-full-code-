# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 RC-W5 task W5-T2 (B17 §6/§7) — the deprecated cycle columns
#           are DROPPED, five of the six that migration 0019 marked.
# Rules:    D2 (*"Yes"* — unify the two cycle column generations; legacy
#           calendar columns deprecated then dropped) · D9 (bill day + due days
#           STAY on the cycle as defaults) · BR-MET-077 · BR-MET-009 ·
#           CLAUDE.md rule 4 (financial immutability — nothing already issued
#           moves) · CLAUDE.md 🔒 sensitive paths (migration ordering —
#           HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will review it
# later as human") — a row in 12-governance/09-human-review-ledger.md is OWED
# for this file and is REPORTED by the RC-W5 lane rather than written by it.
# ───────────────────────────────────────────────────────
"""metering 0021 — CR-029 W5-T2: five deprecated cycle columns are dropped.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-23 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). ⚠ Its row in `12-governance/09-human-review-ledger.md` is
OWED: the RC-W5 lane does not write governance files and has REPORTED the row,
with the figures to put to the PO in plain English, in its closing report.

Migration 0019 named six columns in `LEGACY_DEPRECATED_COLUMNS`, stamped each
with a Postgres deprecation comment, and left a test asserting that **no
`RemoveField` existed yet** — W1 protecting this work from a lane that felt like
tidying up. This is the migration that test was waiting for.

WHAT GOES, AND WHAT REPLACED EACH ONE
-------------------------------------
    window_start · window_end   ONE PARTICULAR period's dates, from the
                                2026-08-08 modal. The read window is DERIVED
                                now — `start_day + days_to_complete`, B17 §2's
                                *"start day + N days IS the read window"* — and
                                `selectors.cycle_dict` computes it for every
                                cycle. Both were NULL on every cycle created
                                since CR-029 landed, so the screens that named
                                them have been reading the derived pair already.
    read_day_from · read_day_to the day-of-month pair `start_day` and
                                `days_to_complete` supersede. `services.
                                _sync_cycle_schedule` kept them in step as a
                                compatibility copy; nothing reads them.
    due_day                     a day-of-month that could wrap into the next
                                month. The DUE fact billing actually reads is
                                `due_days` — a COUNT added to the bill date
                                (BR-BIL-024) — and that column STAYS (D9).

⚠ **`bill_date` IS THE SIXTH AND IT IS NOT DROPPED. READ THIS BEFORE ADDING IT.**

`apps/billing/issue.py::_due_terms_for` reads `cycle__bill_date` as the fallback
bill date for a run where the clerk typed none (BR-BIL-070's precedence, in
`runs.effective_bill_date`). **No ruling says what replaces it.** D9 keeps
`bill_day` — a DAY-OF-MONTH — as the cycle's surviving default, and turning a
day-of-month into the bill DATE of a particular run means choosing a MONTH:

    a run for period 1–30 June, on a cycle whose bill day is the 5th, bills on
    5 June, 5 July, or the 5th of the month the run is taken in?

Those are three different dates up to a month apart, and each produces a
different DUE date, which is when the late-fee clock starts (BR-BIL-001). That
is a rule, not an implementation detail, and the prime directive forbids
resolving it by call site. **REPORTED as an open question**; until it is ruled
the column stays, keeps its 0019 deprecation comment, and is read by exactly one
fallback that is null on every cycle this product creates.

NOTHING ALREADY ISSUED MOVES (hard rule 4). No invoice, invoice line, payment or
journal entry names any of these five columns; the reads that consumed them
(BR-MET-016's duplicate clause, the staging context) take the derived window
instead, which is the same window for any cycle that had both dates and a real
window for every cycle that did not.

IRREVERSIBLE, AND SAID SO. The reverse re-adds the five columns as NULLABLE with
no default — the shape they had — and it cannot restore the VALUES, because a
dropped column's data is gone. That is stated here rather than in a comment
somewhere else: rolling this back gives a schema, not a history.

RLS: NOTHING TO RE-POLICE. `cycles` has carried ENABLE + FORCE and the B2 §3
tenant-isolation policy since metering 0001/0002, and that policy is ROW-scoped
— removing a column from an already-policed table changes nothing about who may
see which row.

NO MONEY MOVES (BR-MET-078, hardened by this CR). Not one of the five holds a
rate, an amount or a currency, and no ❄️ FROZEN B4/B5 figure is touched.
"""

from django.db import migrations, models

#: The five taken here, in the order 0019 listed them. `bill_date` is 0019's
#: sixth and is deliberately absent — see the module docstring.
DROPPED_COLUMNS: tuple[str, ...] = (
    "window_start",
    "window_end",
    "read_day_from",
    "read_day_to",
    "due_day",
)


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0020_cr029_route_model"),
    ]

    operations = [
        migrations.RemoveField(model_name="cycle", name="window_start"),
        migrations.RemoveField(model_name="cycle", name="window_end"),
        migrations.RemoveField(model_name="cycle", name="read_day_from"),
        migrations.RemoveField(model_name="cycle", name="read_day_to"),
        migrations.RemoveField(model_name="cycle", name="due_day"),
    ]


#: What a reverse re-creates. Held as data beside the operations so a reader can
#: see at a glance that the shape comes back and the DATA does not.
REVERSE_SHAPE = {name: models.IntegerField(null=True, blank=True) for name in DROPPED_COLUMNS[2:]}


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §6/§7 RC-W5 T2 + the CR-029 record in 12-governance/11-change-requests.md
# generated: 2026-08-23 by the CR-029 RC-W5 lane
# checklist: A✔ B✔(the wizard's Schedule step moved with the columns) C✔(tests/test_cr029_rcw5_legacy_columns.py) D✔ E✔ F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row OWED and REPORTED)
# gates: makemigrations --check clean · metering + reports + billing suites green
# exceptions: (1) `cycles.bill_date` is NOT dropped although 0019 deprecated it — billing's due-terms fallback reads it and no ruling says what replaces it; REPORTED as an open question · (2) the reverse restores the SHAPE and not the DATA, stated in the docstring rather than implied
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
