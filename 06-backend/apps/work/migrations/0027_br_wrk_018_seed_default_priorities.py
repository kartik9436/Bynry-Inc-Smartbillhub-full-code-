# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 §5 · US-WRK-008 §4   Question: OQ-WRK-1765, CLOSED
#           2026-09-07 as a JUDGMENT (not a PO ratification — see below)
# Rules:    BR-WRK-018 (a priority carries a PROMISE, and `due_at` is stamped
#           from it at raise) · BR-TEN-012 (insert-missing: a utility's own
#           answer is never overwritten) · CLAUDE.md hard rule 1 · law 13 (a
#           judgment recorded with its reasoning is the deliverable)
# Tests:    06-backend/tests/test_cr070_default_priorities.py
# ───────────────────────────────────────────────────────
"""work 0027 — the nine job types get a default priority, and four beat theirs.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-07 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

⚠ **THESE ARE OUR FIGURES AND NOT THE PRODUCT OWNER'S, AND THAT DISTINCTION IS
THE MOST IMPORTANT SENTENCE IN THIS FILE.**
`OQ-WRK-1765` asked which priority each of the nine types should default to.
The PO was shown the four bands **with the response time each implies**, in
plain English. They did not dispute the values; they answered a **different**
question — *"you keep them configurable in settings - user can change the
timings"* — and later said *"please complete all the changes /bug we discussed
- dont wait for me"*. **That is a delegation, not a signature.** So this closes
`OQ-WRK-1765` as a recorded JUDGMENT under CLAUDE.md law 13 (*"a judgment call
recorded in the decision log with its reasoning is the deliverable; a question
is the failure to make one"*), and nothing anywhere may describe these hours as
ratified.

**WHAT MAKES IT SAFE TO SEED A RESPONSE TIME AT ALL**, and it is the PO's own
ruling rather than our confidence: `work_priorities.sla_hours` is a **per-tenant
SETTING**, editable on Settings → Reference data → Work priorities since
`work/0001`, and both places that turn a priority into a promise read the
tenant's live row (`connections._resolve_due_at` at raise,
`dispatch.change_priority` on edit). So a seeded default is **a starting point a
utility changes in one word**, not a promise this platform makes on a utility's
behalf. That was not true of the question as originally asked, which is why it
was originally refused.

WHAT IT WRITES
--------------
`Urgent` 4 h · `High` 8 h · `Normal` 72 h (3 days) · `Low` 168 h (7 days) — the
`SEED_PRIORITIES` figures, which a tenant may also change.

  * **High:** Consumer Complaint · Corrective Maintenance · Water Quality
    Monitoring
  * **Normal:** Meter Maintenance · Connection · Consumer Services
  * **Low:** Preventive Maintenance · Infrastructure Development · Reading
  * **Urgent, on FOUR SUB-TYPES that beat their parent heading:** Gas leak
    call-out · Odour complaint · No Water Supply · Outage report

⚠ **THE FOUR ARE THE POINT OF THIS FILE, NOT AN APPENDIX.** A sub-type with no
default of its own is raised at its PARENT's — `_resolve_priority` reads
`type_ref.default_priority` and there is no third fallback. *Gas leak call-out*
hangs under *Consumer Complaint*, so without a row of its own it would be raised
at **8 hours**. Eight hours is a reasonable number for a complaint about a bill
and it is the wrong number for a gas leak, **and it would arrive there by
accident** — nobody would have chosen it, nothing on any screen would show that
a choice had been skipped, and the consequence lands at a customer's house. The
same holds for *Odour complaint* (the other way a gas leak is reported) and for
*No Water Supply* and *Outage report*, which are a customer with no service at
all rather than a customer with a question about one.

WHAT IT REFUSES TO DO
----------------------
**It never overwrites a default a utility has already chosen** (`BR-TEN-012`).
Only a row whose `default_priority_id` is NULL is written, so a tenant that set
*Reading* to High keeps High. A replay therefore writes 0.

**It does not touch a row a utility RENAMED** — the same name test `0023`,
`0024` and `0026` all use: a renamed row is one they have made their own.

**It writes no priority row.** A tenant whose `work_priorities` are missing or
renamed gets NOTHING for that band, named in the printed count rather than
invented — `_resolve_priority`'s own posture: *"a tenant that has not seeded
priorities gets an order with none and a DUE cell that draws a dash, rather than
an invented Normal that reads as a promise somebody made."*

⚠ **ALREADY-RAISED ORDERS DO NOT MOVE**, and that is `US-WRK-008` TC-4 rather
than an oversight of this file: `due_at` is stamped AT RAISE from the priority
in force then. This changes what the NEXT order is raised at.

RLS
---
`work_order_types` and `work_priorities` both carry ENABLE + FORCE and FORCE
binds the migration role, so every tenant is visited under its own
`app.tenant_id` and the GUC is restored to its arrival state — `work/0024`'s
shape, followed rather than re-derived.
"""

from django.db import migrations

#: **PINNED, NOT READ FROM `SEED_TYPES`.** This file records what was decided on
#: 2026-09-07 for the tenants that already exist. `SEED_TYPES` carries the same
#: mapping for tenants provisioned from here on, and the two are asserted equal
#: by `test_cr070_default_priorities.py` — which is the check that keeps them
#: from drifting apart without either one being "the" source. A live read here
#: would silently re-apply a LATER ruling to a host migrating late, under this
#: migration's name and with this migration's date in the log.
DEFAULTS: tuple[tuple[str, str, str], ...] = (
    # (type code, seeded name, priority code)
    ("COMPLAINT", "Consumer Complaint", "HIGH"),
    ("CORRECTIVE", "Corrective Maintenance", "HIGH"),
    ("WATER_QUALITY", "Water Quality Monitoring", "HIGH"),
    ("METER_MAINT", "Meter Maintenance", "NORMAL"),
    ("CONNECTION", "Connection", "NORMAL"),
    ("CONSUMER_SVC", "Consumer Services", "NORMAL"),
    ("PREVENTIVE", "Preventive Maintenance", "LOW"),
    ("INFRA_DEV", "Infrastructure Development", "LOW"),
    ("READING", "Reading", "LOW"),
    # ⚠ THE FOUR THAT BEAT THEIR PARENT — see the module docstring.
    ("GAS_LEAK_CALLOUT", "Gas leak call-out", "URGENT"),
    ("GAS_ODOUR", "Odour complaint", "URGENT"),
    ("NO_WATER_SUPPLY", "No Water Supply", "URGENT"),
    ("ELEC_OUTAGE", "Outage report", "URGENT"),
)


def _apply_tenant(apps_registry, tenant_id) -> int:
    WorkOrderType = apps_registry.get_model("work", "WorkOrderType")
    WorkPriority = apps_registry.get_model("work", "WorkPriority")
    priorities = {
        row.code.upper(): row.id
        for row in WorkPriority.objects.filter(tenant_id=tenant_id)
    }
    written = 0
    for code, seeded_name, priority_code in DEFAULTS:
        priority_id = priorities.get(priority_code)
        if priority_id is None:
            # Named by the count, never invented. See the docstring.
            continue
        written += WorkOrderType.objects.filter(
            tenant_id=tenant_id,
            code=code,
            name=seeded_name,
            is_system=True,
            default_priority_id__isnull=True,  # BR-TEN-012 — never overwrite
        ).update(default_priority_id=priority_id)
    return written


def apply_ruling(apps_registry, schema_editor):
    Tenant = apps_registry.get_model("tenancy", "Tenant")
    connection = schema_editor.connection
    is_postgres = connection.vendor == "postgresql"

    arrival = None
    if is_postgres:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            arrival = cursor.fetchone()[0]

    written = tenants = 0
    try:
        for tenant_id in Tenant.objects.values_list("id", flat=True):
            if is_postgres:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
            tenants += 1
            written += _apply_tenant(apps_registry, tenant_id)
    finally:
        if is_postgres:
            with connection.cursor() as cursor:
                if arrival is None:
                    cursor.execute("RESET app.tenant_id")
                else:
                    cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [arrival])

    if tenants:
        print(
            f"br-wrk-018 default priorities: {tenants} tenant(s) — {written} job type(s) "
            "given a default (OQ-WRK-1765, closed as a judgment)"
        )


def undo_ruling(apps_registry, schema_editor):
    """A NO-OP, and stated rather than silent.

    Reversing would mean clearing `default_priority` again, and by then this
    migration cannot tell a row IT wrote from one a utility set themselves on
    the same screen. Clearing both would take somebody's answer away to satisfy
    a rollback; leaving them costs one edit per row to a person who wants them
    gone.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0026_br_wrk_058_common_sub_types"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_ruling, undo_ruling),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-WRK-1765 (closed as a judgment) · BR-WRK-018 · US-WRK-007/008 ·
#         PO 2026-09-07 "dont wait for me"
# generated: 2026-09-07 by the CR-070 work sample-data lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr070_default_priorities.py · makemigrations
#         --check --dry-run · migrate against real PostgreSQL 16
# exceptions: the HOURS are this lane's judgment under a PO delegation, not a
#         PO signature — said in the docstring, the decision log and the
#         review-ledger row, and NOT to be restated as ratified
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
