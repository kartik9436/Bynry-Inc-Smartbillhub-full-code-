# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 RC-W6 — **OQ-343**, CLOSED-RULED by the PO 2026-08-23,
#           verbatim: *"B: no reader anywhere, correct the screenshot and drop
#           the stored name"*. Recorded as **D14** in B17 §3.
# Rules:    D6 (*"reader — not required"*, which OQ-343 extended from
#           ASSIGNMENT to the historical fact) · BR-MET-048 (route/cycle
#           changes are audited — the audit row is not this column) ·
#           CLAUDE.md 🔒 sensitive paths (migration ordering —
#           HUMAN-REVIEW-PENDING) · hard-won law 1 (a column no screen shows is
#           not evidence of anything)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will review it
# later as human") — a row in 12-governance/09-human-review-ledger.md is OWED
# for this file and is REPORTED by the RC-W6 lane rather than written by it.
# ───────────────────────────────────────────────────────
"""metering 0022 — CR-029 OQ-343: `read_windows.reader` is dropped.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-23 under the PO ruling of 2026-08-09. ⚠ Its row in
`12-governance/09-human-review-ledger.md` is OWED and REPORTED.

WHY THE COLUMN EXISTED AND WHY IT GOES. metering 0020 gave a closed read window
a `reader` — a cross-module FK to identity recording WHO WALKED it — straight
from the PO's SET-06D.audit screenshot (*"Aug 2026 · Aug 3 · M. Chen · 196 · 196
· Complete"*). D6 had already ruled *"not required"* about reader ASSIGNMENT, and
whether that reached this after-the-fact HISTORY was genuinely unclear: an
assignment says who WILL read; this says who DID. RC-W3c built the column, left
the screen column out, and asked rather than guessed (OQ-343).

The PO answered **(B)**: *"no reader anywhere, correct the screenshot and drop
the stored name"*. So the Read history is **Window · Read on · Collected ·
Expected · Result**, the screenshot is corrected in B17 §3 as D14 so no later
lane "fixes" it back, and the stored name goes — the product does not keep data
no screen shows.

⚠ **`routes.assigned_to` IS NOT TOUCHED, AND THAT IS AN EXPLICIT BOUNDARY.** It
predates CR-029, D6 preserved the ops tab's existing read-only reader display,
and the PO was not asked about it. A migration that took it too would be a
defect, not thoroughness.

DATA LOSS IS REAL AND IS STATED. Dropping a column destroys what it held. On
this tree that is nothing — `close_read_window` is `read_windows`' only writer,
it landed on 2026-08-23, and the demo seed sets no reader — but on a host that
has closed windows with a reader recorded, those names are gone and cannot be
recovered by reversing this migration. The reverse restores the SHAPE (a
nullable FK), never the DATA. That is the same posture metering 0021 recorded
for the five legacy cycle columns.

NOT FINANCIAL. `read_windows` holds no money (BR-MET-078, hardened by this CR):
this touches no invoice, no payment, no journal line, so CLAUDE.md rule 4 does
not arise. No golden figure reads it.

RLS: NOTHING TO RE-POLICE. `read_windows` carries ENABLE + FORCE and its
tenant-isolation policy from metering 0020, and that policy is ROW-scoped —
removing a column does not change which rows a tenant sees.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0021_cr029_drop_legacy_cycle_columns"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="readwindow",
            name="reader",
        ),
    ]

    # ⚠ The reverse is Django's own `AddField` of the same nullable FK, which
    # restores the SHAPE and not the DATA — see the docstring. It is left
    # implicit rather than hand-written so the historical model stays exactly
    # what 0020 declared.


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §3 D14 / §4 (SET-06D Audit tab) + OQ-343 in 12-governance/01-open-questions.md
# screens: SET-06D (Audit tab · Read history)
# generated: 2026-08-23 by the CR-029 RC-W6 lane
# checklist: A✔ B=done-by-the-sibling-lane(the frontend dropped reader_id/reader_name from RouteReadWindowRow and the Read-history table before this landed) C✔(tests/test_cr029_rcw2_read_windows.py — RED first: the two reader assertions inverted and failed on the served keys) D✔ E✔ F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row OWED and reported)
# gates: makemigrations --check clean · metering suite green
# exceptions: (1) DATA IS DESTROYED and the reverse restores only the shape — stated in the docstring rather than implied · (2) `routes.assigned_to` is deliberately NOT dropped; D6 preserved it and OQ-343 did not reach it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
