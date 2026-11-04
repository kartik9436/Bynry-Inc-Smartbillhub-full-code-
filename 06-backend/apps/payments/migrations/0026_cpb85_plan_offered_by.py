# ── Trace ──────────────────────────────────────────────
# Story:   CR-085 `CPB-21` — *"A plan says who set it up"*
# Question: OQ-CWP-1567 CLOSED 2026-09-08, option (a) — a durable column on the
#          plan rather than an audit read that the retention schedule deletes.
#          Decision log 2026-09-08.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE) · hard rule 4
#          (`payment_plans` is NOT one of the four immutable tables) ·
#          B14 rule 31 (the id is never the visible value — the portal
#          resolves a NAME and the id never leaves the server)
# Tests:   tests/test_cr085_cpb21_plan_offered_by.py
# Impacts: apps/payments/collections_models.PaymentPlan ·
#          apps/payments/plans.propose_payment_plan · .payment_plans_for_account
# ───────────────────────────────────────────────────────
"""payments 0026 — who offered the plan, kept ON THE PLAN.

WHY A COLUMN AND NOT A READ OF THE TRAIL
----------------------------------------
`OQ-CWP-1567` asked how a customer learns who set their payment plan up, when
the only record is the `payment_plan.rows_written` audit row — and
**`audit_log` is pruned on a retention schedule** (CLAUDE.md hard rule 4 says
the same thing about a corrected payment reference, and `OQ-1340` is open on
whether such rows are exempt). Its worked example is the argument: Maria opens
the offer on 3 September and the row naming Sarah was written on 2 September;
in eighteen months the plan is closed, the audit row is gone, and `CWP-043`
still shows the plan. Option (b) — publish the audit read — makes the screen's
sentence true for a while and then quietly false, with nothing anywhere going
red on the day it stops being true.

So the fact is stored **as a fact about the plan** rather than as a trace of
the action that created it. That is the shape `stored_documents.stored_by_user_id`
already uses for exactly the same reason, and it survives pruning because
nothing prunes a plan.

NULLABLE, AND THE NULL IS A REAL ANSWER
---------------------------------------
Every plan written before this migration has no name to give, and so does every
plan a job or an import writes with no human actor (`core.audit.money_action`'s
`AutomationActor` branch has no `.id` — *"never make the wrong call quiet"*).
The portal says so in words, in the customer's own language, rather than
inventing an office.

NO BACKFILL, DELIBERATELY
-------------------------
The trail is the only place the old actor lives and it is pruned, so a backfill
would be right for the rows still in the window and silently wrong for the rest
— a column that is true for recent plans and fabricated for old ones is worse
than one that is honestly empty. Existing plans keep NULL.

RLS IS UNTOUCHED AND THAT IS CHECKED RATHER THAN ASSUMED
--------------------------------------------------------
`payment_plans` already carries its policy (`tenancy/0015_rls_payments_w1`,
swept into the deny-on-unset form by `audit/0005`). A policy is written against
the TABLE, not against its column list, so adding a nullable column changes no
predicate and needs no new policy. `test_tenant_isolation` still covers it.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0025_def_pay_4054_deny_on_unset"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentplan",
            name="offered_by",
            field=models.ForeignKey(
                blank=True,
                db_column="offered_by_user_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        )
    ]
