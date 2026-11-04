"""metering 0052 — two columns wave I needs: what the crew is told, and what a
failure produced.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`
guards every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `I1`); not RATIFIED without a
recorded sign-off.

`CR-070` wave I task `I1` · `US-WRK-031` · `US-WRK-034` · `BR-WRK-031` ·
`BR-WRK-054` · `03-field-map.md` §3 rows 17 and 18 · hard rule 1.

WHY A METERING MIGRATION IN A WORK WAVE
---------------------------------------
`work_orders` is METERING's table today, and `metering/0050` records the
mechanism in full: Django resolves a migration's `model_name` inside its own
app, so an `AddField` on `workorder` written into `apps/work/migrations` raises
before it can run. `I1`'s row does not say `work/000N` — the wave G lane already
amended that convention for the whole module — so nothing needs amending here.

WHAT IT ADDS — TWO COLUMNS AND ONE WIDENED CHECK
-------------------------------------------------
  * **`technician_notes`** (`03-field-map.md` §3 row 17, `[ours]`, `WS-21`) —
    the free sentence a dispatcher writes FOR THE CREW: *"Dog on property — use
    side gate."* Nullable text and deliberately not a structured field: the
    whole value of it is that it carries what no column anticipated.

    ⚠ **IT IS NOT THE CUSTOMER'S NOTE AND NOT THE FIELD'S REPORT.** The field's
    answer comes back in `field_data` (`BR-MET-109`, free-shaped); what the
    customer said belongs to the request that raised the order. Three sentences
    about one job that read alike and are written by three different people at
    three different times — merging any two of them would lose who said it.

  * **`follows_order_id`** (`03-field-map.md` §3 row 18, `[ours]`, `WM-25`) — a
    self FK: *the follow-up names what failed*. `BR-WRK-054`'s follow-up already
    carries `blocked_by`, and **the two are not the same fact**, which is why
    both exist and why this column is not redundant:

      - `blocked_by` says **"do not start me yet"** — a SEQUENCING fact, cleared
        when the blocker finishes, and written by any wave that orders work.
      - `follows_order_id` says **"I exist BECAUSE that one failed"** — a
        PROVENANCE fact, permanent, and the thing
        `EP-WRK-10`'s FIRST-TIME FIX counts (*"share of orders with no follow-up
        pointing at them; 88%"*). Derive that figure from `blocked_by` and every
        ordinary two-step job counts as a return visit and the number is wrong
        every month, quietly.

`on_delete=PROTECT` for the reason hard rule 4 gives everywhere else: the failed
order is the evidence for the follow-up's existence, and a database that can
delete the evidence and keep the conclusion is worse than one that refuses.

  * **`ck_work_orders_source`, DROPPED AND REBUILT AT FIFTEEN TOKENS.**
    `BR-WRK-054` and `US-WRK-034` §5 name `source = failed_outcome` for the
    order a failure produces, and `J66` draws it as *Raised by: Failed outcome ·
    WO-4907*. **That token did not exist.** Wave P closed the vocabulary at
    fourteen (`metering/0049`) and this CHECK refuses anything else — so the
    consequence chain would have been refused **by PostgreSQL, inside the
    acceptance transaction**, taking a supervisor's whole Accept down with it
    and naming a constraint rather than a cause.

    ⚠ **THIS IS A WIDENING, WHICH IS THE OPPOSITE DIRECTION FROM THE ONE
    `DEF-WRK-3726` FORBIDS, AND THE TWO LOOK ALIKE IN A DIFF.** That defect is
    about a wave DECLARING a shorter list and thereby refusing writes other
    waves make, three sprints downstream of the cause. Adding a token refuses
    nothing that worked yesterday.

    ⚠ **AND IT MUST BE A MIGRATION RATHER THAN JUST A PYTHON EDIT.**
    `metering/0049` builds its constraint from a LIVE import of
    `connections.WORK_ORDER_SOURCES`, so appending a token silently changes what
    that migration *would* create — while every database that already ran it
    keeps the fourteen-token constraint. The result is the one failure nobody
    can debug from the symptom: **Python accepts the raise and PostgreSQL
    refuses the INSERT.** `RemoveConstraint` + `AddConstraint` under the same
    name makes the database agree with the tuple.

RLS IS UNTOUCHED, AND WHY THAT IS SAFE
--------------------------------------
`work_orders` has had `ENABLE` + `FORCE` row-level security since
`metering/0027`. **A policy is on the TABLE, not on its columns**, so both new
columns are covered by the existing policy on the day they exist — the same
statement `metering/0049` and `0050` each made about their own.

⚠ **THAT SENTENCE IS A CLAIM AND IT IS NOT YET PROVED — SAID PLAINLY, BECAUSE
HARD-WON LAW 1 IS THAT A COMMENT CLAIMING A GUARANTEE IS NOT THE GUARANTEE.**

An earlier draft of this paragraph named `tests/test_us_wrk_031_034_edit_pg.py`
as reading `relrowsecurity` and `relforcerowsecurity` out of `pg_class` on a
real PostgreSQL. **That file does not exist.** The wave ran out of time before
writing it, and a docstring naming a test that was never written is precisely
the defect law 1 was written from — three files once described an OpenAPI
CI-diff that no workflow ran.

**What is actually true today:** the policy is on the TABLE and these two
columns are covered by it the moment they exist, which is a property of
PostgreSQL rather than of anything this migration does — the same statement
`metering/0049` and `0050` each made, and `tests/test_us_wrk_rls_pg.py` reads
`pg_class` for `work_orders` already. **What is NOT proved** is the specific
cross-tenant case for `follows_order_id`: that one tenant cannot point a
follow-up at another tenant's order. The FK's read is tenant-scoped so it should
be unreachable, and *should be* is exactly the phrase law 1 exists to catch.

⚠ **AND DO NOT TAKE THE ISOLATION GATE AS EVIDENCE IN THE MEANTIME**
(`DEF-GOV-4024`, filed the same day): `G5` runs the isolation suite with no
settings override, inherits SQLite where RLS cannot be tested at all, and
reports PASS with **192 of its 238 proofs skipped**.
"""

from __future__ import annotations

from django.db import migrations, models

from apps.metering.connections import WORK_ORDER_SOURCES


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0051_cr070_n_costing"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="technician_notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="follows_order",
            field=models.ForeignKey(
                blank=True,
                db_column="follows_order_id",
                null=True,
                on_delete=models.PROTECT,
                related_name="follow_ups",
                to="metering.workorder",
            ),
        ),
        # ── the fifteenth source token, in the database ────────────────────
        # Dropped and rebuilt under the SAME NAME. `0049` imports the tuple
        # live, so its own definition already reads fifteen after this commit;
        # what it cannot do is change a database that has already run it.
        migrations.RemoveConstraint(
            model_name="workorder",
            name="ck_work_orders_source",
        ),
        migrations.AddConstraint(
            model_name="workorder",
            constraint=models.CheckConstraint(
                condition=models.Q(source__isnull=True)
                | models.Q(source__in=WORK_ORDER_SOURCES),
                name="ck_work_orders_source",
            ),
        ),
    ]
