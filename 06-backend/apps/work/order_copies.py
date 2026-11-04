# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-032 (the order's own copies — copied at raise, never read
#           through the template link) · US-WRK-028 TC-2 (a template picked on
#           the wizard's step 1 gives the order its copies).  Screens: Work-008
# Rules:    BR-WRK-008 (COPY, NEVER LINK; the version is stamped) ·
#           BR-WRK-015 (the copied reading carries its unit) · BR-WRK-002
#           (Work writes no other module's table) · CLAUDE.md hard rule 1
#           (tenant scope) · 3 (a quantity carries its unit) · 7 (audit_log)
# Tests:    06-backend/tests/test_us_wrk_032_copies.py (TC-1..TC-7) ·
#           06-backend/tests/test_us_wrk_032_copies_pg.py (RLS, PostgreSQL)
# Impacts:  apps/metering/connections.py:create_work_order (the one caller) ·
#           apps/work/checklist.py (reads what this writes)
# ───────────────────────────────────────────────────────
"""**The copy that turns an order from a view into a record** — `BR-WRK-008`.

THE RULE, VERBATIM
------------------
*"**Copy, never link.** When an order is raised it takes its OWN copies of the
template's details, safety rows, tasks, materials, readings and help, and stamps
the template version. **Editing or publishing a template afterwards changes no
order already raised.**"*

WHY IT MATTERS ENOUGH TO COST SIX TABLES
-----------------------------------------
A template is a living document: a utility edits it, publishes v2, publishes v3.
An order is what one job actually was, on one afternoon, at one address. If the
order read its checklist through `template_id`, then adding a task this
afternoon would change the steps a technician followed in January — on every
completed order that ever used that template, silently, with no row modified and
nothing in any audit trail to notice. The evidence a supervisor reviews and the
report a customer disputes would both quietly become descriptions of a template
as it stands TODAY rather than of the job as it happened.

So the copy is not an optimisation and it is not denormalisation. It is the
difference between a record and a view of something still moving.

WHERE THE BOUNDARY RUNS, AND WHY THIS FILE EXISTS AT ALL
---------------------------------------------------------
`work_orders` is METERING's table and `create_work_order` is metering's service.
The six copy tables are WORK's (`work/0012`). Cross-module writes are forbidden
in both directions (B2 §2), and G78 only watches one of them — so metering
cannot reach into `work_order_tasks` any more than Work may reach into
`connections`.

This is exactly the shape `publish` already takes, in reverse: metering owns the
header write and calls nothing of Work's; `apps/work/templates_svc.publish`
writes `work_order_template_versions` itself, inside the same transaction. Here
metering raises the order and then calls THIS function by name, and this
function writes Work's six tables. **Neither module writes the other's table;
both commit or neither does.**

⚠ **IT HANGS OFF `create_work_order` AND NOT OFF THE WIZARD, AND THAT IS THE
WHOLE POINT.** Orders are raised from at least five doors — the dispatcher's
three-step wizard, `commit_connection`, the five customer flows of wave P, a
failed outcome's follow-up (wave I) and the seeder. `BR-WRK-008` says *when an
order is raised*, not *when a dispatcher raises one*. Hanging the copy off one
screen would give four of those doors orders whose checklist is a live template
— which is the bug, arriving through the back.

WHAT IS COPIED, AND WHAT IS DELIBERATELY NOT
---------------------------------------------
Six collections: details, safety, tasks, materials, readings, help. Values, not
lookups: `title`, `text`, `prompt`, `unit_of_measure`, `min_value`, `max_value`,
`planned_qty` and the flags are all written as they read AT THIS INSTANT.

NOT copied: `wot_asset_types`, which is the seventh template collection and says
which asset types a template APPLIES TO. It is a matching rule used to choose a
template, never a fact about a job once one is chosen — an order that has been
raised has its asset already, and a copy of *this template suits gas meters*
would be an answer to a question nobody asks of a job in hand.

⚠ **`access_notes`, `hazards` AND `gate_code` ARE WRITTEN NULL AND THAT IS AN
ABSENCE, NOT A GAP LEFT BY THIS LANE.** `03-field-map.md` §2.4 sources them from
*"the premises' own access notes"* and **`metering.Premises` has no such
column** — no `access_notes`, no `hazards`, no `gate_code` anywhere on it, at
this tip. Inventing a gate code for a real address, or silently borrowing some
other text field into one, is worse than a dash on a screen (the `source` and
`due_at` posture `metering/0050` already takes). The four `show_*` flags ARE
copied, because those are the template's own and do exist. When a premises
gains the three columns, this function copies them and `Work-008`'s Location tab
stops drawing dashes; nothing else changes.

⚠ **A TEMPLATE IN DRAFT IS REFUSED, AND THE REFUSAL IS METERING'S** (`US-WRK-032`
TC-4). `version` 0 IS the draft state (`BR-WRK-011`: *"0 is a draft and it is
not a version"*), so there is no published version to copy and no number to
stamp. `create_work_order` refuses before this function is reached, so no order
row is written at all — the alternative would be an order stamped
`template_version = 0`, pointing at a bundle that may still change under it,
which is `BR-WRK-008` broken by a value rather than by a join.

⚠ **AN ORDER WITH NO TEMPLATE COPIES NOTHING AND IS NOT AN ERROR** (TC-7). A
one-off job — *go and look at the smell of gas at 12 Elm Row* — has no checklist
because nobody wrote one, and `Work-008`'s Checklist tab shows its empty state
rather than a failure.
"""

from __future__ import annotations

from typing import Any

from apps.work import models
from core import audit as core_audit
from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


#: The six collections, in the order `BR-WRK-008` names them. `details` is the
#: odd one out — ONE row rather than a list — so it has its own branch below
#: rather than being pretended into the same shape (the posture
#: `templates_svc.COLLECTIONS` already takes for the template side).
_LIST_COLLECTIONS: tuple[str, ...] = ("safety", "tasks", "materials", "readings", "help")


def copy_template_onto_order(
    actor: Any,
    *,
    order_id: Any,
    template_id: Any,
    template_version: Any,
    tenant_id: Any = None,
) -> dict[str, int]:
    """Write the order's six copies. Returns a count per collection.

    Called by `apps.metering.connections.create_work_order` INSIDE its own
    transaction, so a refusal anywhere here takes the order row with it: an
    order that exists with half a checklist would be a job a technician could
    pick up and complete without the steps somebody meant them to follow.

    `template_version` is passed rather than re-read because the caller has
    already stamped it on the order, and reading it twice is two answers to one
    question (the 2026-09-05 ruling's own words). It is recorded on the audit
    row so *which version this job's checklist came from* is answerable from the
    audit trail alone, without joining to an order that may since have been
    cancelled.
    """
    tenant_id = tenant_id or _tenant_id()
    counts: dict[str, int] = dict.fromkeys(("details", *_LIST_COLLECTIONS), 0)
    if not template_id:
        # TC-7 — a one-off job with no template. Nothing to copy, and that is
        # an empty checklist rather than an error.
        return counts

    def _rows(model: Any) -> list[Any]:
        return list(
            model.objects.filter(tenant_id=tenant_id, template_id=template_id).order_by("seq")
        )

    # ── details — ONE row, and its three address facts are absences ────────
    detail = models.WorkOrderTemplateDetail.objects.filter(
        tenant_id=tenant_id, template_id=template_id
    ).first()
    if detail is not None:
        models.WorkOrderDetail.objects.create(
            tenant_id=tenant_id,
            work_order_id=order_id,
            # See the module docstring: `metering.Premises` carries none of
            # these three at this tip, and a guessed gate code is worse than a
            # dash. They are filled when the premises gains them.
            access_notes=None,
            hazards=None,
            gate_code=None,
            show_account_summary=detail.show_account_summary,
            show_asset_card=detail.show_asset_card,
            show_access_notes=detail.show_access_notes,
            show_appointment=detail.show_appointment,
            # FB-023 F4 — the fifth tick, copied like the other four.
            show_balance_payments=detail.show_balance_payments,
            # FB-028 — the Reconnect limit, copied (BR-WRK-008).
            reconnect_limit=detail.reconnect_limit,
            # DEF-WRK-10652 — copied like the flags, never linked: the
            # customer's messages about THIS job read the job's own copy.
            prep_instructions=detail.prep_instructions,
            send_customer_visit_messages=detail.send_customer_visit_messages,
        )
        counts["details"] = 1

    # ── safety — the rows BR-WRK-037's lock will read ─────────────────────
    safety = _rows(models.WorkOrderTemplateSafety)
    if safety:
        models.WorkOrderSafety.objects.bulk_create(
            [
                models.WorkOrderSafety(
                    tenant_id=tenant_id,
                    work_order_id=order_id,
                    seq=row.seq,
                    text=row.text,
                    is_mandatory=row.is_mandatory,
                )
                for row in safety
            ]
        )
        counts["safety"] = len(safety)

    # ── tasks — the seven steps, with their minutes and their photo rule ───
    tasks = _rows(models.WorkOrderTemplateTask)
    if tasks:
        models.WorkOrderTask.objects.bulk_create(
            [
                models.WorkOrderTask(
                    tenant_id=tenant_id,
                    work_order_id=order_id,
                    seq=row.seq,
                    title=row.title,
                    est_minutes=row.est_minutes,
                    photo_required=row.photo_required,
                    is_mandatory=row.is_mandatory,
                    # PO answer (3) — copied like the title, never linked.
                    instruction=row.instruction,
                    # CR-187-BRC10 T-35 — the money bar and charge, copied too.
                    money_fresh_minutes=row.money_fresh_minutes,
                    money_charge_code=row.money_charge_code,
                )
                for row in tasks
            ]
        )
        counts["tasks"] = len(tasks)

    # ── materials — planned, in the unit the template planned in ──────────
    # `part_id` stays a real reference because a part is a catalogue entry, not
    # a version of a sentence (see `WorkOrderMaterial`'s own docstring).
    # `unit_of_measure` is COPIED — hard rule 3, and the reason a later edit to
    # the part's unit cannot silently restate what a crew was told to bring.
    materials = list(
        models.WorkOrderTemplateMaterial.objects.filter(
            tenant_id=tenant_id, template_id=template_id
        ).order_by("part_id")
    )
    if materials:
        models.WorkOrderMaterial.objects.bulk_create(
            [
                models.WorkOrderMaterial(
                    tenant_id=tenant_id,
                    work_order_id=order_id,
                    part_id=row.part_id,
                    planned_qty=row.planned_qty,
                    used_qty=None,
                    unit_of_measure=row.unit_of_measure,
                    unplanned=False,
                )
                for row in materials
            ]
        )
        counts["materials"] = len(materials)

    # ── readings — BR-WRK-015: the copied reading carries its unit ─────────
    readings = _rows(models.WorkOrderTemplateReading)
    if readings:
        models.WorkOrderReading.objects.bulk_create(
            [
                models.WorkOrderReading(
                    tenant_id=tenant_id,
                    work_order_id=order_id,
                    seq=row.seq,
                    prompt=row.prompt,
                    unit_of_measure=row.unit_of_measure,
                    min_value=row.min_value,
                    max_value=row.max_value,
                    required=row.required,
                    photo_required=row.photo_required,
                    posts_as_meter_read=row.posts_as_meter_read,
                    # `CR-168-BRC10` P1.33 — the KIND is copied like every
                    # other column, so a template edited later cannot turn a
                    # job's text reading into a number nobody can type.
                    kind=row.kind,
                    # `value`, `captured_*`, `photo_attachment_id` and
                    # `in_range` are the JOB's answers and stay empty until
                    # somebody goes out.
                )
                for row in readings
            ]
        )
        counts["readings"] = len(readings)

    # ── help — copied so it opens with no signal (US-WRK-042) ─────────────
    help_rows = _rows(models.WorkOrderTemplateHelp)
    if help_rows:
        models.WorkOrderHelp.objects.bulk_create(
            [
                models.WorkOrderHelp(
                    tenant_id=tenant_id,
                    work_order_id=order_id,
                    seq=row.seq,
                    kind=row.kind,
                    label=row.label,
                    ref=row.ref,
                )
                for row in help_rows
            ]
        )
        counts["help"] = len(help_rows)

    # CLAUDE.md hard rule 7. The row names the VERSION as well as the template,
    # because *which checklist was this job given* is the question this write
    # answers and `BR-WRK-008` is the reason it can never be re-derived later.
    core_audit.write_row(
        action="work_order.template_copied",
        entity_type="work_order",
        entity_id=order_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={
            "template_id": str(template_id),
            "template_version": template_version,
            **{f"{name}_rows": count for name, count in counts.items()},
        },
    )
    return counts
