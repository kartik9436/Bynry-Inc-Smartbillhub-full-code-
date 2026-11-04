# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — P0.3 (hold reason), P0.4 (the
#           hold-reason lookup), P1.33 (a reading that is words), P3.53 (a
#           contractor's phone and email), P4.4 (reassign as one act with a
#           reason), P5.10 (a job type's own promise), PO answer (1) (the
#           default SLA target) and PO answer (3) (task instruction text)
# Rules:    CR-168-BRC10 §7.3 (the agreed contract, migrations table) ·
#           judgments J1, J2, J7, J8 (decision log 2026-10-04, "THE WORK
#           SERVER'S ANSWERS") · BR-WRK-025 (append-only — untouched) ·
#           CLAUDE.md hard rule 1 (RLS FORCE — in work/0030) · hard rule 3
# Tests:    06-backend/tests/test_cr168_srv1_migrations_pg.py (up → down → up on
#           PostgreSQL 16) · tests/test_cr168_srv1_server.py
# ───────────────────────────────────────────────────────
"""work 0028 — why a job is held, and the seven columns round 2's contract needs.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-04 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT IT ADDS
------------
  * **`work_hold_reasons`** — a tenant LOOKUP (judgment J1), seeded with five
    rows on every tenant that exists: *Weather · Waiting for a part · Customer
    not home · Access refused · Other* (`models.SEED_HOLD_REASONS`, pinned
    below rather than read). A CHECK list would make *Waiting for a permit* a
    migration; a lookup makes it a Settings row. RLS ENABLE + FORCE is
    `work/0030`, in its own file like every Work table before it.
  * `work_order_assignments.reason`, `.act_group` — judgment J2: a reassign is
    one request writing two rows that share both. **Adding a column is not an
    UPDATE of a row**, so the append-only trigger (`work/0009`) is untouched and
    `ck_work_order_assignments_act` keeps its five tokens.
  * `crews.phone`, `.email` — a contractor's contact (P3.53).
  * `wot_tasks.instruction` — PO answer (3), verbatim *"Add an instruction text
    box to each task, shown on the technician's phone."*
  * `wot_readings.kind` (`number` | `text`, CHECK) and two CHECKs, the second of
    which is judgment J8 in the database: a text reading can never be marked to
    post as a meter read (hard rule 3).
  * `work_order_readings.kind`, `.value_text` — the order's copy of the kind,
    and where a reading that is words is stored. ⚠ `kind` on the ORDER's copy
    is not in §7.3's table; it is appended there by this lane with its reason:
    the server must know a reading is text from the job's own row, never by
    re-reading a template a supervisor may since have edited (`BR-WRK-008`).
  * `work_order_types.sla_hours` — P5.10, NULL = the priority's.
  * `work_settings.default_target_priority_id` — PO answer (1), judgment J7.
    NULL reads as the tenant's `NORMAL` priority (72 h seeded), so no row has
    to be written for the seeded answer to hold.

THE REVERSE drops every column and the table. Nothing here is money, and no
existing row's meaning moves: every new column is NULL or defaulted.
"""

import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

import core.dbfields

#: PINNED, NOT READ FROM `models.SEED_HOLD_REASONS` — `work/0027`'s reasoning:
#: this file records what was seeded on 2026-10-04 for the tenants that existed.
#: `test_cr168_srv1_migrations_pg.py` asserts the two are equal.
SEED = (
    ("WEATHER", "Weather", 1),
    ("WAITING_PART", "Waiting for a part", 2),
    ("CUSTOMER_NOT_HOME", "Customer not home", 3),
    ("ACCESS_REFUSED", "Access refused", 4),
    ("OTHER", "Other", 5),
)


def seed_hold_reasons(apps_registry, schema_editor):
    """Five rows per tenant, insert-missing (`BR-TEN-012`), and a printed count.

    The table carries no RLS yet (that is `work/0030`), so no GUC is needed to
    write it; `tenants` is read the way `work/0027` reads it.
    """
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    Reason = apps_registry.get_model("work", "WorkHoldReason")
    written = tenants = 0
    for tenant_id in Tenant.objects.values_list("id", flat=True):
        tenants += 1
        have = {
            code.lower()
            for code in Reason.objects.filter(tenant_id=tenant_id).values_list("code", flat=True)
        }
        for code, name, rank in SEED:
            if code.lower() in have:
                continue
            Reason.objects.create(
                tenant_id=tenant_id, code=code, name=name, rank=rank, is_system=True, active=True
            )
            written += 1
    if tenants:
        print(f"cr-168 hold reasons: {tenants} tenant(s) — {written} reason row(s) seeded")


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0058_storm_water_flat_size"),
        ("work", "0027_br_wrk_018_seed_default_priorities"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkHoldReason",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("rank", models.IntegerField(default=0)),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "work_hold_reasons"},
        ),
        migrations.AddConstraint(
            model_name="workholdreason",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("code"),
                name="uq_work_hold_reasons_tenant_code_ci",
            ),
        ),
        migrations.AddField(
            model_name="crew",
            name="email",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="crew",
            name="phone",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorderassignment",
            name="act_group",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorderassignment",
            name="reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorderreading",
            name="kind",
            field=models.TextField(default="number"),
        ),
        migrations.AddField(
            model_name="workorderreading",
            name="value_text",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertemplatereading",
            name="kind",
            field=models.TextField(default="number"),
        ),
        migrations.AddField(
            model_name="workordertemplatetask",
            name="instruction",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertype",
            name="sla_hours",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="worksettings",
            name="default_target_priority",
            field=models.ForeignKey(
                blank=True,
                db_column="default_target_priority_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="work.workpriority",
            ),
        ),
        migrations.AddConstraint(
            model_name="workordertemplatereading",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ("number", "text"))), name="ck_wot_readings_kind"
            ),
        ),
        migrations.AddConstraint(
            model_name="workordertemplatereading",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind", "text"), ("posts_as_meter_read", True), _negated=True),
                name="ck_wot_readings_text_never_posts",
            ),
        ),
        migrations.RunPython(seed_hold_reasons, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (migrations table, row work/0028) · §7.4 J1 J2 J7 J8
# generated: 2026-10-04 by CR-168 round 2 lane SRV-1
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# exceptions: `work_order_readings.kind` appended to §7.3 with its reason
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
