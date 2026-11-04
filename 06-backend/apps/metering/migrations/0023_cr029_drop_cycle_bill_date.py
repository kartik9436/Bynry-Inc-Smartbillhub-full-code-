# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 RC-W6 — **OQ-344**, CLOSED-RULED by the PO 2026-08-23,
#           verbatim: *"I'd say B - these are defualt - user can override"*.
#           This drops `cycles.bill_date`, the SIXTH AND LAST legacy column.
# Rules:    D2 (one schedule generation) · D9 (the cycle carries bill day +
#           due days as DEFAULTS; the run overrides) · BR-BIL-024 (due date =
#           bill date + due days) · BR-BIL-070 (a typed bill date wins) ·
#           OQ-339 (a day the month does not have clamps to its last day) ·
#           CLAUDE.md rule 4 (financial immutability) · 🔒 sensitive paths
#           (migration ordering — HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will review it
# later as human") — a row in 12-governance/09-human-review-ledger.md is OWED
# for this file and is REPORTED by the RC-W6 lane rather than written by it.
# ───────────────────────────────────────────────────────
"""metering 0023 — CR-029 OQ-344: `cycles.bill_date`, the last legacy column.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-23. ⚠ Its row in `12-governance/09-human-review-ledger.md` is OWED and
REPORTED.

WHY IT SURVIVED 0021 AND WHY IT GOES NOW. RC-W5-T2 dropped five of the six
deprecated cycle columns and left this one standing, with its reason written
into 0021's own docstring: *"`apps/billing/issue.py::_due_terms_for` reads
`cycle__bill_date` as the fallback bill date for a run where the clerk typed
none, and no ruling says what replaces it"*. D9 kept `bill_day` — a
DAY-OF-MONTH — and turning a day-of-month into ONE RUN'S DATE means choosing a
month. The three candidate readings sat up to a month apart, and because the due
date is bill date + due days, each started the late-fee clock (BR-BIL-001) on a
different day. That lane refused to pick and reported OQ-344 instead of deleting
the fallback and choosing by omission.

THE RULING, 2026-08-23. PO verbatim, on one line so it can be grepped and
asserted whole:

    "I'd say B - these are defualt - user can override"

**(B) THE MONTH AFTER THE PERIOD ENDS.** On the figure
the PO was shown — bill day the 5th, 21 due-days, period 1–31 August — an
untouched run bills **5 September** and falls due **26 September**. It is the
ordinary arrears reading and the only one that answers the same whether the run
is taken on time or late, because the input is the PERIOD and never a clock
(BR-TEN-043 / gate G6).

WHAT MOVED BEFORE THIS MIGRATION RAN — the column is dropped after its readers,
never before:
  · `apps/billing/runs.default_bill_date` is the rule, expressed once.
  · `apps/billing/runs.effective_bill_date` takes a bill DAY and a period end.
  · `apps/billing/issue._due_terms_for` reads `cycle__bill_day`.
  · `apps/billing/selectors.cycle_terms_for` answers a bill DAY.
  · `apps/metering/selectors.cycle_dict` DERIVES `bill_date` / `due_date` for
    the cycle's next window, so both contracted keys keep meaning something.
  · `apps/metering/services._validate_cycle` still ACCEPTS the field name (a
    client that has not moved is entitled to think it exists) and stores nothing.
  · the S27 export column is dropped with the value behind it.

NOTHING ALREADY ISSUED MOVES (CLAUDE.md rule 4), and the reason is structural:
`invoices.due_date` and `invoices.bill_date` are STAMPED at issue and an issued
invoice is immutable (billing 0006 freezes the payload), so the resolution this
change touches is consulted only while a bill is a DRAFT.
`tests/test_cr029_rcw6_bill_date_default.py` proves it against a stamped bill.

WHAT DOES CHANGE, STATED PLAINLY: a NOT-YET-ISSUED run of a CR-006-era cycle
that carried a stored `bill_date` and whose clerk typed nothing now resolves to
the derived default instead of the stored date. That is the ruling's whole
purpose. On every cycle this product creates the stored column was NULL — no
shipped screen ever sent it and the sample seam stopped writing it at W5-T1 — so
in practice the resolution moves from a REFUSAL (BR-BIL-024, neither date
present) to a real default, which is the gap the PO was closing.

DATA LOSS IS REAL AND IS STATED: dropping a column destroys what it held, and
the reverse restores the SHAPE (a nullable date) and never the DATA — the same
posture 0021 recorded for the other five.

NO MONEY MOVES: this is date arithmetic, not an amount. No rate, no currency, no
❄️ FROZEN B4/B5 figure; the golden harness reads none of it.

RLS: NOTHING TO RE-POLICE. `cycles` has carried ENABLE + FORCE and its
tenant-isolation policy since metering's first migration, and that policy is
ROW-scoped — removing a column does not change which rows a tenant sees.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0022_cr029_drop_read_window_reader"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="cycle",
            name="bill_date",
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §3 D9 / §6 + OQ-344 in 12-governance/01-open-questions.md + metering/0021's own docstring, which named this column and said why it stayed
# screens: S31 step 1 · SET-07.3 · SET-07D
# generated: 2026-08-23 by the CR-029 RC-W6 lane
# checklist: A✔ B=deferred(no screen field is removed — the cycle payload's bill_date/due_date keys keep their names and change source) C✔(tests/test_cr029_rcw6_bill_date_default.py — RED first: AttributeError, apps.billing.runs has no attribute default_bill_date; 13 of 15 red) D✔ E✔ F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row OWED and reported)
# gates: makemigrations --check clean · golden 33 PASS / 0 FAIL before AND after · billing + metering suites green
# exceptions: (1) DATA IS DESTROYED and the reverse restores only the shape · (2) a not-yet-issued run of a CR-006-era cycle with a stored bill_date and no typed date resolves differently — that is the ruling, stated rather than hidden · (3) `bill_date` stays ACCEPTED on the cycle write path and is discarded, the `window_start`/`window_end` posture · (4) metering derives its own copy of the ruled arithmetic rather than calling billing's, because billing reads metering and never the reverse (B1 / G6)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
