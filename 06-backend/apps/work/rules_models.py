# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) — rules that raise work orders on their own.
#           Screens: Work-026 (the rule list + the five-step builder),
#           Work-007 (RAISED BY), Work-020.
# Rules:    BR-WRK-033 (a rule raises orders without a person; a rule that is
#           OFF raises nothing; every rule-raised order carries the rule as its
#           source; the list shows this month's count) · BR-WRK-024 (the source
#           stamp, and its second half — a rule-raised order also stamps the
#           rule) · BR-WRK-002 (Work writes no other module's tables; every
#           read is through a seam) · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_us_wrk_037_rules.py (TC-1…TC-7) ·
#           tests/test_us_wrk_037_rules_pg.py (isolation, real PostgreSQL,
#           NOSUPERUSER role)
# Impacts:  apps/work/models.py (one import line, which is what registers
#           these) · apps/work/rules.py · work/0018, work/0019
# ───────────────────────────────────────────────────────
"""`work_order_rules` and `work_order_rule_raises` — the two tables behind the
overnight sweep.

WHY THIS IS ITS OWN FILE AND NOT THE END OF `models.py`
────────────────────────────────────────────────────────────────────────────
`apps/work/models.py` is 1,950 lines with other CR-070 lanes editing it. A
pathspec commit takes the WHOLE working-tree content of every path it names
(CLAUDE.md hard-won law 11, mechanism two), so appending two classes there would
put this lane's copy of a 1,950-line shared file on the branch and silently
revert whatever a sibling pushed into it meanwhile — with a correct file count,
this lane's own hunks present, and nothing in the diff to notice. Wave K made
exactly this call for `evidence_models.py` and the reasoning is unchanged.

WHY THERE ARE **TWO** TABLES, WHICH IS THE ONE DESIGN DECISION HERE
────────────────────────────────────────────────────────────────────────────
`BR-WRK-033` asks for a rule. The execution plan asks for one more thing in six
words — *"idempotent per (rule, subject)"* — and those six words are a second
table, for a reason worth writing down because the cheaper answer looks correct
for about a month.

**The cheaper answer:** ask `work_orders` whether this rule already raised for
this subject — `WorkOrder.objects.filter(rule_id=…, asset_id=…).exists()`. It
needs no new table and it is wrong in both directions:

  * **An order that is CLOSED still answers yes.** `AST-04412` is exchanged in
    March and the rule stays quiet for ever, so the meter installed in its place
    never gets its own exchange in 2031. The check would have to grow *"…and not
    closed"*, and then a job finished last night makes the rule fire again
    tonight.
  * **An order that is CANCELLED answers yes too**, so a job cancelled by
    mistake can never be re-raised by the thing that raised it.

The subject a rule fires ON and the order it PRODUCED are two different facts
with two different lifetimes, and folding them into one column means the sweep's
memory is destroyed by ordinary work-order housekeeping. So the raise is
recorded in its own row, `work_order_rule_raises`, which nothing but the sweep
writes and nothing ever deletes — the sweep's memory outlives the order.

⚠ **AND THE UNIQUE CONSTRAINT IS THE IDEMPOTENCY, NOT THE `exists()` CHECK
ABOVE IT.** `rules.py` looks before it leaps, and that look is a race: two beat
processes, or a nightly firing overlapping a hand-run from the terminal, both
read *"not raised"* in the same millisecond and both raise. The `UniqueConstraint`
below is what makes the second one fail, and `rules.py` catches that failure
**inside a SAVEPOINT** (hard-won law 14) and treats it as *already raised*. The
check is the fast path; the constraint is the guarantee. A sweep whose only
protection is the `exists()` call is a sweep that double-raises about once a
quarter, at 02:00, with nothing in the logs.

WHAT A "SUBJECT" IS
────────────────────────────────────────────────────────────────────────────
The thing the rule fired ON — a meter, an account, a bill-run break. It is
stored as `subject_kind` + `subject_key` (text) rather than five nullable FKs,
which is judgment 4 of the 2026-09-04 plan applied again: five FKs would take
this table to seven columns and make every new trigger source a migration. The
key is whatever the source module calls its own row and it is only ever compared
for equality — never joined, never dereferenced by this table.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk


class WorkOrderRule(models.Model):
    """`work_order_rules` — *when this happens, raise that job.*

    `BR-WRK-033`, CONFIRMED. `Work-026` draws the list: RULE · SOURCE MODULE ·
    TRIGGER · TEMPLATE RAISED · PRIORITY · THIS MONTH · ENABLED.

    ⚠ **`enabled` IS THE WHOLE SECOND HALF OF THE RULE** — *"a rule that is off
    raises nothing"*. It is a column and not a deletion because a utility turns
    a rule off in December and on again in March, and a deleted rule takes its
    raise history with it.
    """

    #: The five modules a trigger may read, and the ONLY five. Each has exactly
    #: one reader in `rules.py` and each reader goes through a seam file — a
    #: sixth module means a sixth seam, reviewed, not a sixth `if` branch.
    SOURCE_PAYMENTS = "payments"
    SOURCE_BILLING = "billing"
    SOURCE_ASSETS = "assets"
    SOURCE_READS = "reads"
    SOURCE_ACCOUNTS = "accounts"

    SOURCE_MODULES: tuple[str, ...] = (
        SOURCE_PAYMENTS,
        SOURCE_BILLING,
        SOURCE_ASSETS,
        SOURCE_READS,
        SOURCE_ACCOUNTS,
    )

    #: The trigger each module offers today. TEXT and not an enum column for the
    #: reason `work_orders.type` is text — but validated against this tuple by
    #: `rules.py`, because an unknown trigger is a rule that silently never
    #: fires, which is worse than a refusal at save time.
    TRIGGER_FINAL_NOTICE_EXPIRED = "final_notice_expired_unpaid"
    TRIGGER_BILLING_EXCEPTION_UNRESOLVED = "billing_exception_unresolved"
    TRIGGER_ASSET_PAST_CERTIFICATION = "asset_past_certification_life"
    TRIGGER_CONTINUOUS_FLOW = "continuous_flow_alarm"
    TRIGGER_OCCUPANCY_COMPLETED = "occupancy_completed"

    #: Which module each trigger reads. `rules.py` asserts a rule's pair against
    #: this map at save time and at sweep time, so a rule cannot claim the
    #: assets module and carry a payments trigger.
    TRIGGER_MODULE: dict[str, str] = {
        TRIGGER_FINAL_NOTICE_EXPIRED: SOURCE_PAYMENTS,
        TRIGGER_BILLING_EXCEPTION_UNRESOLVED: SOURCE_BILLING,
        TRIGGER_ASSET_PAST_CERTIFICATION: SOURCE_ASSETS,
        TRIGGER_CONTINUOUS_FLOW: SOURCE_READS,
        TRIGGER_OCCUPANCY_COMPLETED: SOURCE_ACCOUNTS,
    }

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: What a supervisor typed — *Asset age rule*, *Final notice → disconnect
    #: visit*. It is what `Work-007` prints after *Raised by:*, so it is a
    #: sentence a clerk reads at 07:00 and not a code.
    name = models.TextField()
    source_module = models.TextField()
    trigger_kind = models.TextField()
    #: The trigger's own numbers — `{"days_past_due": 5}`, `{"consecutive_reads":
    #: 3}`. JSON because each of the five triggers takes different parameters
    #: and a column per parameter would be a migration per trigger.
    params = models.JSONField(default=dict, blank=True)
    #: WHAT IT RAISES. NOT NULL: a rule with no template is a rule that cannot
    #: do the one thing a rule is for, and letting it save would put a row on
    #: `Work-026` whose TEMPLATE RAISED column is a dash for ever.
    #: ⚠ Cross-module FK work → metering, the same one `work_order_assignments`
    #: already carries; `work_order_templates` is metering's table today
    #: (`03-field-map.md` §4).
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.PROTECT,
        db_column="template_id",
        related_name="raising_rules",
    )
    #: The priority every order this rule raises is stamped with. NULLABLE: a
    #: rule that names none lets the template's own default stand, and inventing
    #: *Normal* here would silently override a template whose author chose
    #: Urgent.
    priority = models.ForeignKey(
        "work.WorkPriority",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="priority_id",
        related_name="raising_rules",
    )
    #: Steps 2, 3 and 4 of the builder — assignment logic, notifications,
    #: reminders & escalation. Each is a small object and each is READ by the
    #: raise; none of them is a table because none is queried across rules.
    assignment = models.JSONField(default=dict, blank=True)
    notifications = models.JSONField(default=dict, blank=True)
    escalation = models.JSONField(default=dict, blank=True)
    #: `BR-WRK-033`'s second half. Default TRUE because the five-step builder's
    #: last step is *Review & activate* — a rule a supervisor has just finished
    #: writing and pressed Activate on is on.
    enabled = models.BooleanField(default=True)
    #: BR-TEN-057 — the sample tag, so BR-TEN-061's sweep deletes on this
    #: predicate and on nothing else.
    is_sample = models.BooleanField(default=False)
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_rules"
        constraints = [
            #: Two rules may not share a name inside one utility — the name is
            #: what `Work-007` prints after *Raised by:*, and two *Asset age
            #: rule*s would make that line unreadable as evidence.
            models.UniqueConstraint(
                fields=["tenant", "name"], name="uq_work_order_rules_tenant_name"
            ),
        ]
        indexes = [
            #: The sweep's ONLY query: *this tenant's enabled rules*. `enabled`
            #: is in the index rather than filtered after, because the sweep
            #: runs against every tenant every night and a rule that is off must
            #: cost nothing at all.
            models.Index(
                fields=["tenant", "enabled"], name="ix_work_order_rules_enabled"
            ),
        ]


class WorkOrderRuleRaise(models.Model):
    """`work_order_rule_raises` — *this rule has already fired for that subject.*

    The sweep's memory. One row per (rule, subject), written inside the same
    transaction as the order it produced, and **never updated and never
    deleted** — see the module docstring for why this cannot live on
    `work_orders.rule_id`.

    ⚠ **`work_order` IS NULLABLE AND THAT IS NOT AN OVERSIGHT.** `on_delete` is
    `SET_NULL` so that a utility purging old orders keeps the sweep's memory
    intact: the fact *"the asset-age rule fired for AST-04412 on 5 September"*
    is what stops it firing again, and it must survive the order it raised. A
    `CASCADE` here would delete the memory with the order and re-raise the job
    on the next sweep — the exact bug the second table exists to prevent, put
    back by a delete rule.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rule = models.ForeignKey(
        WorkOrderRule,
        on_delete=models.CASCADE,
        db_column="rule_id",
        related_name="raises",
    )
    #: What the rule fired on — `asset` · `account` · `bill_run_break` ·
    #: `meter` · `move`. Kept beside the key so a supervisor reading the row can
    #: tell what the key names without knowing which trigger wrote it.
    subject_kind = models.TextField()
    #: The source module's own id for that row, as text. Compared for equality
    #: and never joined — see the module docstring.
    subject_key = models.TextField()
    #: ⚠ Cross-module FK work → metering (`work_orders` is metering's table).
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="work_order_id",
        related_name="rule_raises",
    )
    raised_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_rule_raises"
        constraints = [
            #: **THE IDEMPOTENCY.** Not the `exists()` check in `rules.py` — see
            #: the module docstring. Per TENANT as well as per rule, so that a
            #: rule id colliding across utilities (it cannot, but the index does
            #: not depend on that) can never dedupe another utility's raise.
            models.UniqueConstraint(
                fields=["tenant", "rule", "subject_kind", "subject_key"],
                name="uq_work_order_rule_raises_subject",
            ),
        ]
        indexes = [
            #: `Work-026`'s THIS MONTH column — a count per rule over a date
            #: window, which is the only read of this table a screen makes.
            models.Index(
                fields=["tenant", "rule", "raised_at"],
                name="ix_wo_rule_raises_month",
            ),
        ]


class WorkOrderRuleTrigger(models.Model):
    """`work_order_rule_triggers` — one of a rule's several triggers
    (`CR-168-BRC10` P3.65, `work/0029`).

    The drawing of 26 Sep: *several triggers, any of them raises the job*. One
    `trigger_kind` column cannot hold that, so each trigger is a row. `work/0029`
    copies every existing rule's `trigger_kind`/`params` in as its first row and
    KEEPS the two columns as lawful containers, so a rollback loses no rule.
    Nothing reads these rows yet — the sweep is SRV-4's (round 5).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    rule = models.ForeignKey(
        WorkOrderRule, on_delete=models.CASCADE, db_column="rule_id", related_name="trigger_rows"
    )
    seq = models.IntegerField(default=1)
    kind = models.TextField()
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_rule_triggers"
        constraints = [
            models.UniqueConstraint(fields=["rule", "seq"], name="uq_work_order_rule_triggers_seq"),
        ]


class WorkOrderRuleEscalationFire(models.Model):
    """`work_order_rule_escalation_fires` — *this escalation has fired for that
    job* (`CR-168-BRC10` P3.57, `work/0029`).

    ONCE per job per kind: the unique key is the guarantee, the
    `work_order_rule_raises` shape. Written by the escalation sweep (SRV-4,
    round 5); round 2 lands only the table, so the sweep is never built onto a
    schema that does not exist.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="escalation_fires",
    )
    kind = models.TextField()
    fired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_rule_escalation_fires"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "work_order", "kind"],
                name="uq_work_order_rule_escalation_fires_once",
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-037@d1b76486 (EP-WRK-07) · 10-execution-plan.md wave M task M1
# generated: 2026-09-05 by the CR-070 wave M build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint in this file) E=n/a(no screen) F✔ G✔ H✔(work/0019_rls_force_rules is the 🔒 path; review-ledger row is M6)
# gates: pytest tests/test_us_wrk_037_rules.py · tests/test_us_wrk_037_rules_pg.py on PostgreSQL · G78
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
