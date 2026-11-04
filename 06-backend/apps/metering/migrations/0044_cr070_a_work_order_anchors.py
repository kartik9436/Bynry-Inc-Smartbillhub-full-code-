# ── Trace ──────────────────────────────────────────────
# Change:   CR-070 wave A, task A4 — `work_orders.connection_id` goes nullable;
#           `premises_id` and `account_id` sit beside the `asset_id` that
#           already exists; a CHECK requires at least one anchor.
#           Screens: Work-007 (the Orders tab lists the order with a dash under
#           CONNECTION) · Work-002 (unchanged)
# Rules:    BR-WRK-006 (PROPOSED — `WM-01` + our CHECK: *"a work order may
#           exist without a connection; premises, account and asset anchors
#           beside it; at least one anchor required"*) · CLAUDE.md hard rule 1
#           (RLS FORCE on `work_orders` is UNTOUCHED — an ALTER COLUMN and an
#           ADD CONSTRAINT change no policy) · B2 §2 (a cross-module FK is
#           part of the reviewed interface set — Addendum r23) · CR-070 §14
#           (phase 0 rolls back cleanly: a nullable column and mounted buttons)
# Tests:    06-backend/tests/test_us_wrk_001_anchors.py (TC-1..5 on the
#           suite's SQLite, where Django's CheckConstraint also runs) ·
#           06-backend/tests/test_us_wrk_001_anchor_check_pg.py (TC-6: the
#           CHECK refuses a raw INSERT on PostgreSQL 16, around the ORM)
# Impacts:  apps/metering/connections.py (WorkOrder.connection null=True;
#           WorkOrder.premises · WorkOrder.account · the CheckConstraint;
#           create_work_order's widened contract) · apps/work/ (reads and
#           raises through its seam) · 04-docs/02-decisions/02-database-
#           design-brief.md (`### Module: work`, Addendum r23 — the same
#           commit as this file, per CR-070 §2(a))
# ───────────────────────────────────────────────────────
"""metering 0044 — a work order may stand on something other than a build.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing BR-WRK-006
as the Work module's documentation states it (`WM-01`, the blueprint's *"one
structural blocker"*, plus the CHECK that is ours). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

WHAT THIS CHANGES, IN PLAIN TERMS
---------------------------------
Until now every work order had to belong to a new-connection build, because
the column that points at the build could not be empty. A leak investigation
on a meter that has been in the ground for ten years has no build, so it could
not be recorded — not from a screen, not from the terminal, not by hand.

Three things, on one table, and no policy touched:

  1. `work_orders.connection_id` may be NULL. **Every existing row keeps its
     value** — there is no data change here at all, and US-WRK-001 TC-4 counts
     the rows before and after to prove zero moved.
  2. Two new nullable columns beside the `asset_id` that already exists:
     `premises_id → premises` (metering's own table) and
     `account_id → accounts` (⚠ a cross-module FK, metering → customers, the
     third of its kind on this file's tables after `asset_id` and
     `accepted_by`; Addendum r23 in B2 records it for the reviewed set).
  3. `ck_work_orders_has_anchor` — at least one of the four is set. This is the
     database refusing an order attached to nothing, so relaxing (1) cannot
     create one by any path that skips `create_work_order`'s own refusal.
     Django emits a real CHECK on both vendors; the PostgreSQL proof is
     `tests/test_us_wrk_001_anchor_check_pg.py`, which INSERTs around the ORM
     and reads the constraint's name back out of the refusal.

WHY THIS IS METERING'S MIGRATION AND NOT `work/0001`
----------------------------------------------------
`work_orders` lives in `apps/metering/connections.py` today, with two
migrations, an audit trail and tests (`16-work/03-field-map.md` §1). Whether
the six Work tables MOVE into `apps/work/` is that file's §4 — PENDING the
blueprint's §16 and the lane that opens phase 1. A column on a metering table
is a metering migration either way (US-WRK-001: *"Do not write `work/0001` for
a column on a metering table"*), and the Work module reaches it through
`apps/work/seams/metering_seam.py`.

RLS
---
`work_orders` was created with ENABLE + FORCE ROW LEVEL SECURITY and its
tenant-isolation policy in `0026_cr030_w6_connections`. An ALTER COLUMN, two
ADD COLUMNs and an ADD CONSTRAINT change nothing about that policy, and
`tests/test_w6_connections.py::test_w6_rls_scopes_all_five_tables` still runs
its probe over this table on PostgreSQL. `human_owned.txt`'s `*rls*` glob does
not match this file because it holds no policy; its `migrations/0*.py` glob
does, for the ordering.

ROLLBACK
--------
Clean, as CR-070 §14 promises for phase 0: drop the CHECK, drop the two
columns, make `connection_id` NOT NULL again — which succeeds only while no
row without a connection exists, exactly as it should.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0043_cr054_w1_row_key"),
        # The `account_id` FK points at customers' `accounts`; its latest
        # migration at HEAD. customers' own chain depends on metering ≤ 0043,
        # so this edge closes no cycle.
        ("customers", "0039_def2847_mailing_address_line2_country"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workorder",
            name="connection",
            field=models.ForeignKey(
                blank=True,
                db_column="connection_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="work_orders",
                to="metering.connection",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="premises",
            field=models.ForeignKey(
                blank=True,
                db_column="premises_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="work_orders",
                to="metering.premises",
            ),
        ),
        migrations.AddField(
            model_name="workorder",
            name="account",
            field=models.ForeignKey(
                blank=True,
                db_column="account_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="customers.account",
            ),
        ),
        migrations.AddConstraint(
            model_name="workorder",
            constraint=models.CheckConstraint(
                condition=(
                    Q(connection__isnull=False)
                    | Q(premises__isnull=False)
                    | Q(account__isnull=False)
                    | Q(asset__isnull=False)
                ),
                name="ck_work_orders_has_anchor",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-001@87b94265 (EP-WRK-01 story + BR-WRK-006 snapshot) · 16-work/03-field-map.md §3 rows 1–4 · CR-070 §2(a), §14
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=deferred(POST /work-orders is wave B's — 07-endpoints.md §1 row 14) E✔(the Orders tab draws the dash) F✔ G✔ H=HUMAN-REVIEW-PENDING (row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · migrate on PostgreSQL 16 (sbh_cr070a) · pytest tests/test_us_wrk_001_anchors.py · tests/test_us_wrk_001_anchor_check_pg.py on PostgreSQL · G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row)
# exceptions: no index on (tenant, premises) or (tenant, account) yet — the Orders tab reads by (tenant, state), which is indexed; a per-anchor read arrives with the doors that need it (waves B, M)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
