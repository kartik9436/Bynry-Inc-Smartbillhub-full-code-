# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, tasks `P0.3` and
#          `P0.4`. The drawing names `payments/0030` as its reference; that
#          number went to `P0.1`/`P0.2` because `payments/0029` was already
#          taken by `CR-132-BRC07` the same morning, so every phase 0
#          migration number in the document is one lower than the file.
# Rules:   CLAUDE.md hard rule 1 (isolation is `payments/0032`, its own file) ·
#          hard rule 2 (a NEW money column declares FOUR decimals — the drawing
#          says six and the signed rule wins; PO re-sign 2026-08-22) · hard
#          rule 7 (a forced close writes `audit_log` — phase 2's service, not
#          this schema)
# Tests:   06-backend/tests/test_cr135_p0_foundations.py ·
#          06-backend/tests/test_cr135_p0_rls_pg.py
#          ⚠ The first name read `test_cr135_p0_counter_sessions.py` until
#          2026-09-22 and no such file has ever existed (`DEF-PAY-6205`).
# Impacts: apps/payments/counter_session_models.CounterSession ·
#          apps/payments/apps.py (`ready()` registers that module) ·
#          the six phase 2 Counter screens, which all read this one table
# ───────────────────────────────────────────────────────
"""payments 0031 — `counter_sessions`, the till table. HUMAN-OWNED.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of
2026-08-09. Migration ordering is a CLAUDE.md 🔒 sensitive path, so there is a
row in `12-governance/09-human-review-ledger.md` stating in plain English, with
a figure, what would be put to the Product Owner.

**`P0.3`'s outcome: *"A till can be written. Six screens in phase 2 wait on
this one table."*** Phase 0 ships no screen, no endpoint and no service — PO
ruling 2026-09-22, *"go as per phase 0 ; we are going to implement all phases
one by one so fcus on current one."*

The column-by-column reasoning is in
`apps/payments/counter_session_models.py`'s docstring, which is where a reader
looking at the model will be. Three things belong HERE because they are about
the schema rather than about the table:

⚠ THE OPENING FLOAT IS `NUMERIC(18,4)` AND THE DRAWING SAYS `NUMERIC(18,6)`
-----------------------------------------------------------------------------
`P0.3`, verbatim: *"opening float at NUMERIC(18,6)"*. **Not followed.**
CLAUDE.md hard rule 2, PO re-sign 2026-08-22, verbatim: *"We already confirmed
this - MOney 4 decimal, percentage 6 decimal , display both 2 decimal"*.
Existing `18,6` columns stay lawful containers — `payments.amount` is one — but
the rule governs what a NEW column declares, and this one is new. It is
`core.money_fields.money_field()`, the single place that number is written
down. **This was put to the Product Owner and they were told the signed rule
wins; it is not re-asked (CLAUDE.md hard-won law 13)** and the divergence is
recorded in the decision log of 2026-09-22 so a reader comparing the drawing
with the schema finds the answer rather than a discrepancy.

⚠ THE PARTIAL INDEX IS THE POINT OF `P0.4`, NOT AN OPTIMISATION
----------------------------------------------------------------
*"The database refuses a second open till — not a service check that a second
caller can skip."* `uq_counter_sessions_open_owner` is
`UNIQUE (tenant_id, owner_id) WHERE closed_at IS NULL`. A service doing
`SELECT … then INSERT` cannot hold that when two terminals race; an index can.

**And the `WHERE` is the easy-to-miss half `P0.15` names**: without it a clerk
could open a till exactly once in the life of the utility. Both directions are
asserted — a second OPEN till is refused, a second CLOSED one is permitted.

⚠ THIS FILE CREATES THE TABLE AND GIVES IT NO ROW-LEVEL SECURITY
------------------------------------------------------------------
That is `payments/0032`, deliberately in its own file — the same split
`payment_tenders` uses (0021 table, 0022 policies) and `counter_receipts` uses
(0027 table, 0028 policies), so a reader looking for the 🔒 guarantees finds
them in a file whose name says so. `P0.5`'s own outcome: *"A tenant table with
no RLS migration is hard rule 1 broken."*
"""

import django.core.serializers.json
import django.db.models.deletion
from django.db import migrations, models

import core.dbfields


class Migration(migrations.Migration):

    dependencies = [
        # `identity` for `owner` and `closed_by`; `tenancy` for the tenant and
        # for `ServiceCentre`, which lives in `published_content_models.py`.
        ("identity", "0005_cr070_f_field_technician"),
        ("payments", "0030_cr135_p0_1_p0_2_origin_check"),
        ("tenancy", "0044_cr094_i_account_document_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="CounterSession",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                # ⚠ FOUR decimal places where the drawing says six — see above.
                ("opening_float", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("opened_at", models.DateTimeField()),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("close_kind", models.TextField(blank=True, null=True)),
                (
                    "counted_totals",
                    models.JSONField(
                        blank=True,
                        # Money in JSON is money as a STRING (hard rule 2 —
                        # never float). This encoder is what makes that true.
                        encoder=django.core.serializers.json.DjangoJSONEncoder,
                        null=True,
                    ),
                ),
                (
                    "difference",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "closed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="closed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        db_column="owner_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="counter_sessions",
                        to="identity.user",
                    ),
                ),
                (
                    "service_centre",
                    models.ForeignKey(
                        db_column="service_centre_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="counter_sessions",
                        to="tenancy.servicecentre",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "counter_sessions"},
        ),
        migrations.AddIndex(
            model_name="countersession",
            index=models.Index(fields=["tenant", "closed_at"], name="ix_counter_sessions_open"),
        ),
        migrations.AddIndex(
            model_name="countersession",
            index=models.Index(
                fields=["tenant", "owner", "-opened_at"], name="ix_counter_sessions_own"
            ),
        ),
        # ── P0.4 ────────────────────────────────────────────────────────────
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.UniqueConstraint(
                condition=models.Q(("closed_at__isnull", True)),
                fields=("tenant", "owner"),
                name="uq_counter_sessions_open_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(("close_kind__in", ("counted", "forced")))
                | models.Q(("close_kind__isnull", True)),
                name="ck_counter_sessions_close_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("close_kind__isnull", True),
                    ("closed_at__isnull", True),
                    ("closed_by__isnull", True),
                )
                | models.Q(
                    ("close_kind__isnull", False),
                    ("closed_at__isnull", False),
                    ("closed_by__isnull", False),
                ),
                name="ck_counter_sessions_closed_together",
            ),
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(("opening_float__gte", 0)),
                name="ck_counter_sessions_float_not_negative",
            ),
        ),
    ]
