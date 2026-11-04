# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-3422 (PO, 2026-09-02) — *"this says - staff notification - but we
#           dont get any notification"*, with the bell reading "You're all caught
#           up." `bell_events` was one of the three dead links: a table with an
#           index, a writer whose docstring called itself "the only sanctioned
#           writer", a sink nothing ever registered, and no reader anywhere.
# Rules:    BR-SHL-026 (the CLOSED five-event bell catalogue — UNTOUCHED by this;
#           it says what the bell SHOWS, never where it is kept) ·
#           BR-NOT-019 / BR-NOT-021 (the store that survives, and its ruled
#           audience) · CLAUDE.md hard-won law 1 (a docstring claiming a
#           guarantee is not the guarantee) · law 2 (built is not wired)
# Tests:    06-backend/tests/test_def3422_bell_staff_alert.py — the acceptance
#           case, and the two guards that this table is gone from the model set
#           AND from the database
# ───────────────────────────────────────────────────────
"""tenancy 0036 — drop `bell_events`, the bell's second store.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

WHY IT GOES RATHER THAN GETTING ITS MISSING WIRE
--------------------------------------------------
The bell already has a store, and has had one since CR-009 (2026-08-17):
`outbound_messages` is what the platform undertook to send and `in_app_messages`
is what a person actually received and whether they have looked at it. That pair
carries tenant scoping, read state, an audience the Product Owner ruled
(BR-NOT-021), a settings screen, an API and the screen that renders it —
`AppShell.tsx`'s bell reads it on every mount.

`bell_events` carried none of those and would have needed all of them. Keeping
both would give this product **two answers to "what is in my bell"**, which is
the failure the defect's own fix must not create. The full reasoning, and the
judgment that was overturned to reach it, is in
`12-governance/02-decision-log.md` (2026-09-03).

⚠ **AND THE WIRE WAS NOT THE ONLY THING MISSING.** `core.bell.notify()` had no
registered sink AND no caller: nothing outside its own test file ever imported
it. Registering a sink would have made this a table something COULD write and
nothing DOES — the same defect one step later, looking fixed.

NOTHING IS LOST, MEASURED RATHER THAN ASSUMED
----------------------------------------------
The table has never had a writer, so on every deployment it holds zero rows.
There is no data to migrate and none to keep.

REVERSIBILITY
--------------
`DeleteModel` reverses into `CreateModel`, so a rollback re-creates the table and
its index. It does NOT re-create the RLS policy, which `0003_rls_w0_policies`
applied and which PostgreSQL dropped with the table — so a reversed database has
the table back UNPROTECTED. Stated rather than hidden: nothing writes it in that
state either, and re-running `db/rls_tenancy_w0.sql` is what would put the policy
back. That file is HUMAN-OWNED and is deliberately not edited here; it still
names `bell_events` and it still runs BEFORE this migration, so a fresh database
builds the table, protects it, and then drops it — in that order, correctly.
"""

from django.db import migrations


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0035_cr065_size_class_service_backfill"),
    ]

    operations = [
        migrations.DeleteModel(
            name="BellEvent",
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-SHL-004@5a55bc4 (the bell story, and the commit that fixed DEF-3422 · 12-governance/10-defect-log.csv · 12-governance/02-decision-log.md 2026-09-03 · 10-scripts/gates/g74_unread_tables_baseline.txt, whose BellEvent line is deleted in the same commit · apps/tenancy/models.py, where the removal is explained in place)
# generated: 2026-09-03 by story-coder (DEF-3422 bell lane)
# checklist: A✔ B=deferred(no frontend half — nothing on a screen ever read this table) C✔ D=deferred(no HTTP surface — it never had one) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16.13; `to_regclass('public.bell_events')` is NULL after forward and non-NULL after reverse, and the assertion was proved RED first against a tree in which this migration did not exist
# exceptions: (1) THE RLS `.sql` FILE IS NOT EDITED. `db/rls_tenancy_w0.sql` is HUMAN-OWNED and still names this table; it runs at 0003, long before this migration, so a fresh database creates the table, applies the policy and then drops it in that order. Editing a human-owned file to tidy a name that is still correct at the moment it runs is a process event, not a lane's call. (2) A REVERSED DATABASE HAS THE TABLE BACK WITHOUT ITS POLICY — stated in the docstring rather than implied.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
