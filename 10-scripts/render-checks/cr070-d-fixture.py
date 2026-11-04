# ── Trace ──────────────────────────────────────────────
# Story:   US-WRK-013 · US-WRK-014 · US-WRK-015 · US-WRK-018 (EP-WRK-03) — the
#          template `wireframes/Work-013.png` and `Work-022.png` are drawn
#          around: *Meter exchange — residential*, v1 then v2, 4 orders then 31.
# Rules:   BR-WRK-008 (copy, never link — an order remembers WHICH version) ·
#          BR-WRK-009 (the bundle is ROWS) · BR-WRK-011 (publish is the ONE
#          write) · BR-WRK-012 (Delete refused while referenced) · hard rule 1
#          (every write inside one tenant's context) · hard rule 3 (a reading
#          carries its unit)
# Tests:   this is fixture prep for
#          10-scripts/render-checks/cr070-d-the-bundle-and-the-write.mjs
# ───────────────────────────────────────────────────────
"""`ST-nnnn · Meter exchange — residential`, v1 and v2, and the 35 orders.

WHY THIS FILE EXISTS, AND WHY IT IS NOT IN THE SEEDER
-----------------------------------------------------
`10-execution-plan.md` task `D4` names the drawing's fixture in figures:
*"`ST-0002 · Meter exchange — residential` v1 (6 tasks, 4 orders) then v2
(*Added Apply tamper seal*, 31 orders)"*. **None of it is in
`load_sample_data`**, and it should not be. The seeder writes the 24 READY-TO-
USE STARTERS (`BR-MET-109`), each published at v1 with the change note *First
publish* and **zero** orders raised from it, because the sample estate's own
work orders (`WO-0001`–`WO-0039`) are raised from the connection plan and carry
no `template_id` at all.

So on a freshly seeded database every template has ONE version, ZERO orders,
and **Delete is enabled on all 24** — which is correct, and which means the
three things `Work-022` exists to show cannot be seen:

  * a SUPERSEDED version sitting under a CURRENT one,
  * the count that proves `BR-WRK-008` (*the 4 v1 orders still read v1*),
  * **Delete refused with a number in the sentence** (`BR-WRK-012`).

This file writes exactly that story and nothing else.

EVERY WRITE GOES THROUGH THE PRODUCT'S OWN SERVICE
--------------------------------------------------
`apps/work/templates_svc` for the header, the six collections and the two
publishes; `apps/metering/connections.create_work_order` for the 35 orders. A
fixture that inserted `work_order_template_versions` rows with SQL would prove
the SCREEN renders and prove nothing about the rule — and `template_version` is
stamped **at creation from the template's version at that instant**, so the
only way to get four orders that honestly read v1 is to raise them while v1 is
what the template is.

IDEMPOTENT
----------
It deletes the orders it raised last time and then the template, by name, and
builds both again. `work_orders.template_id` is PROTECT, so the orders go
first; nothing a person raised is touched, because the sweep is by template.

⚠ **IT CONSUMES NUMBERS AND DOES NOT PUT THEM BACK.** Each run allocates one
`ST-` and 35 `WO-` numbers from the tenant's own series, and `BR-TEN-035` never
reuses one. That is what a real publish and a real order do, and it is why the
walkthrough asserts the SHAPE of `ST-nnnn` rather than a literal `ST-0002`.

RUN IT
------
    eval "$(10-scripts/proof-db.sh clone waved --export)"
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python manage.py shell < ../10-scripts/render-checks/cr070-d-fixture.py)

WHAT IT PRINTS WHEN IT IS RIGHT
-------------------------------
    cr070-d-fixture: published ST-0025 v1 — 6 tasks, 3 parts, 3 readings
    cr070-d-fixture: raised 4 order(s) against v1
    cr070-d-fixture: published ST-0025 v2 — "Added Apply tamper seal"
    cr070-d-fixture: raised 31 order(s) against v2
    cr070-d-fixture: Meter exchange — residential · ST-0025 · v2 · 35 orders
                     v2  current      31
                     v1  superseded    4
"""
from decimal import Decimal

from apps.identity.models import User
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.tenancy.models import Tenant
from apps.work import models as work_models
from apps.work import services as work_services
from apps.work import templates_svc
from core import tenancy as core_tenancy

TENANT_CODE = "brazosbend"
NAME = "Meter exchange — residential"
SERVICE = "water"

#: v1 — the drawing's six steps. `est_minutes` and the camera flag are columns,
#: never words inside the title (`BR-WRK-009`).
V1_TASKS = [
    {"title": "Confirm address and access", "est_minutes": 3, "photo_required": False, "is_mandatory": True},
    {"title": "Photograph the old register", "est_minutes": 4, "photo_required": True, "is_mandatory": True},
    {"title": "Close the stop tap", "est_minutes": 5, "photo_required": False, "is_mandatory": True},
    {"title": "Remove the old meter", "est_minutes": 12, "photo_required": False, "is_mandatory": True},
    {"title": "Fit the new meter", "est_minutes": 15, "photo_required": True, "is_mandatory": True},
    {"title": "Restore supply and check for leaks", "est_minutes": 4, "photo_required": False, "is_mandatory": True},
]
#: v2 adds the seventh — the change note the drawing carries names it.
V2_EXTRA_TASK = {
    "title": "Apply tamper seal",
    "est_minutes": 2,
    "photo_required": True,
    "is_mandatory": True,
}
V2_CHANGE_NOTE = "Added Apply tamper seal"

SAFETY = [
    {"text": "Water off at the stop tap before you open the box", "is_mandatory": True},
    {"text": "Gloves and eye protection", "is_mandatory": True},
    {"text": "Cone the footway if the box is in it", "is_mandatory": False},
]

#: hard rule 3 — every reading carries its unit in its OWN column.
READINGS = [
    {"prompt": "Old meter final read", "unit_of_measure": "gal", "min": "0", "max": "9999999",
     "required": True, "photo_required": True, "posts_as_meter_read": True},
    {"prompt": "New meter opening read", "unit_of_measure": "gal", "min": "0", "max": "999",
     "required": True, "photo_required": True, "posts_as_meter_read": True},
    {"prompt": "Line pressure after restore", "unit_of_measure": "psi", "min": "20", "max": "80",
     "required": True, "photo_required": False, "posts_as_meter_read": False},
]

HELP = [
    {"kind": "document", "label": "Meter exchange method statement", "ref": "MS-014"},
    {"kind": "phone", "label": "Control room", "ref": "555-0142"},
    {"kind": "note", "label": "Leave the old meter in the van; stores books it in", "ref": None},
]

V1_ORDERS = 4
V2_ORDERS = 31

#: The register a template's MATERIALS point at. Written only when the tenant
#: has none — `Work-025`'s own numbers, so a reviewer holding the two screens
#: together sees the same parts on both.
STOCK = [
    ("MTR-W58", "Water meter 5/8 in", "each", "96.0000"),
    ("SEAL-TMP", "Tamper seal", "each", "1.2500"),
    ("GSKT-58", "Meter gasket 5/8 in", "each", "0.8500"),
]

tenant = Tenant.objects.get(subdomain=TENANT_CODE)
with core_tenancy.tenant_context(tenant.id):
    actor = User.objects.order_by("created_at").first()
    print(f"cr070-d-fixture: actor {actor.email}")

    # ── last run's rows ────────────────────────────────────────────────────
    # `work_orders.template_id` is PROTECT, so the orders go first. Scoped to
    # THIS template, so nothing a person raised is swept up.
    #
    # ⚠ `DEF-WRK-4109` — wave M SEEDS RULES ON THIS TEMPLATE (*Meter exchange
    # programme*, *Move-in / move-out*), and `WorkOrderRule.template` is
    # PROTECT, so deleting it refused every run on a seeded tenant. The rules
    # are not this fixture's to delete: the old template is moved aside by
    # NAME now, its rules are re-pointed at the new one once it is published
    # (below), and only then is the old one deleted.
    replaced = []
    rules_to_move = []
    for old in work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant.id, name=NAME):
        gone = work_tables.WorkOrder.objects.filter(tenant_id=tenant.id, template_id=old.id).delete()
        work_models.WorkOrderTemplateVersion.objects.filter(
            tenant_id=tenant.id, template_id=old.id
        ).delete()
        rules_to_move += list(
            work_models.WorkOrderRule.objects.filter(tenant_id=tenant.id, template_id=old.id)
        )
        old.name = f"{NAME} · replaced {old.template_no or old.id}"
        old.save(update_fields=["name"])
        replaced.append(old)
        print(f"cr070-d-fixture: moved an earlier {NAME} aside and cleared {gone[0]} row(s) with it")

    # ── the parts the bundle plans ─────────────────────────────────────────
    # ⚠ **THE SEEDED ESTATE HAS NO PARTS AT ALL, AND THAT IS CORRECT.** Neither
    # `seed_demo` nor `load_sample_data` writes a `parts` row — the register is
    # the utility's own stock list (`BR-WRK-019`), so a fresh tenant's is empty
    # and `Work-025` draws its empty state. A template's MATERIALS point at that
    # register, so this fixture stocks three rows through the product's own
    # writer when it finds none, rather than failing and reading like a broken
    # screen.
    parts = list(work_models.Part.objects.filter(tenant_id=tenant.id).order_by("part_no")[:3])
    if len(parts) < 3:
        for part_no, name, unit, cost in STOCK:
            if work_models.Part.objects.filter(tenant_id=tenant.id, part_no=part_no).exists():
                continue
            work_services.create_part(actor, {
                "part_no": part_no, "name": name,
                "unit_of_measure": unit, "unit_cost": cost,
            })
            print(f"cr070-d-fixture: + part {part_no} · {name} · {cost}/{unit}")
        parts = list(work_models.Part.objects.filter(tenant_id=tenant.id).order_by("part_no")[:3])
    materials = [
        {"part_id": str(part.id), "planned_qty": Decimal(qty)}
        for part, qty in zip(parts, ("1", "2", "1"))
    ]

    skill = work_models.WorkSkill.objects.filter(tenant_id=tenant.id).order_by("code").first()
    kit = work_models.WorkSafetyKit.objects.filter(tenant_id=tenant.id).order_by("code").first()
    job_type = work_models.WorkOrderType.objects.filter(tenant_id=tenant.id).order_by("code").first()

    # ── the draft, and its bundle ──────────────────────────────────────────
    header = templates_svc.create_draft(actor, {
        "name": NAME,
        "service": SERVICE,
        "scope": work_tables.SCOPE_ASSET,
        "crew_size": 1,
        "est_duration_minutes": 45,
        "skill_id": None if skill is None else str(skill.id),
        "safety_kit_id": None if kit is None else str(kit.id),
        "type_id": None if job_type is None else str(job_type.id),
    })
    template_id = header["id"]

    templates_svc.replace_collection(actor, template_id, "details", {
        "show_account_summary": True,
        "show_asset_card": True,
        "show_access_notes": True,
        "show_appointment": False,
    })
    templates_svc.replace_collection(actor, template_id, "safety", SAFETY)
    templates_svc.replace_collection(actor, template_id, "tasks", V1_TASKS)
    templates_svc.replace_collection(actor, template_id, "materials", materials)
    templates_svc.replace_collection(actor, template_id, "readings", READINGS)
    templates_svc.replace_collection(actor, template_id, "help", HELP)

    v1 = templates_svc.publish(actor, template_id, change_note="First publish")
    row = work_tables.WorkOrderTemplate.objects.get(pk=template_id)
    print(
        f"cr070-d-fixture: published {row.template_no} v{v1['version']} — "
        f"{len(V1_TASKS)} tasks, {len(materials)} parts, {len(READINGS)} readings"
    )

    # ── the four orders that will still read v1 ────────────────────────────
    # ⚠ RAISED **BEFORE** v2 EXISTS, ON PURPOSE. `create_work_order` stamps
    # `template_version` from the template's version at that instant, so this
    # is the only honest way to hold four orders that read v1 (`BR-WRK-008`).
    premises = metering_models.Premises.objects.filter(tenant_id=tenant.id).order_by("premise_no")[:1]
    if not premises:
        raise SystemExit("cr070-d-fixture: no premises seeded — load_sample_data first.")
    anchor = premises[0]

    def raise_orders(count):
        for _ in range(count):
            w6.create_work_order(actor, None, {
                "premises_id": str(anchor.id),
                "type": NAME,
                "service": SERVICE,
                "scope": work_tables.SCOPE_PREMISE,
                "template_id": str(template_id),
            })

    raise_orders(V1_ORDERS)
    print(f"cr070-d-fixture: raised {V1_ORDERS} order(s) against v1")

    # The seeded rules follow the template they always named, by NAME.
    for rule in rules_to_move:
        rule.template_id = template_id
        rule.save(update_fields=["template"])
        print(f"cr070-d-fixture: rule {rule.name} now names {row.template_no}")
    for old in replaced:
        old.delete()

    # ── v2 ─────────────────────────────────────────────────────────────────
    templates_svc.replace_collection(actor, template_id, "tasks", [*V1_TASKS, V2_EXTRA_TASK])
    v2 = templates_svc.publish(actor, template_id, change_note=V2_CHANGE_NOTE)
    print(f'cr070-d-fixture: published {row.template_no} v{v2["version"]} — "{V2_CHANGE_NOTE}"')

    raise_orders(V2_ORDERS)
    print(f"cr070-d-fixture: raised {V2_ORDERS} order(s) against v2")

    # ── what a reader will see, printed so the run can be quoted ───────────
    row.refresh_from_db()
    total = work_tables.WorkOrder.objects.filter(tenant_id=tenant.id, template_id=template_id).count()
    print(f"cr070-d-fixture: {row.name} · {row.template_no} · v{row.version} · {total} orders")
    for version in work_models.WorkOrderTemplateVersion.objects.filter(
        tenant_id=tenant.id, template_id=template_id
    ).order_by("-version"):
        raised = work_tables.WorkOrder.objects.filter(
            tenant_id=tenant.id, template_id=template_id, template_version=version.version
        ).count()
        state = "current" if version.version == row.version else "superseded"
        print(f"    v{version.version}  {state:<12} {raised:>3}   {version.change_note}")

    # ── the walkthrough's own second template ──────────────────────────────
    # A DRAFT is what `Work-013`'s footer counts and what the Versions tab's
    # *"has not been published yet"* sentence is drawn for; the seeder leaves
    # none, because a starter is published. Left here so the walkthrough can
    # read a draft WITHOUT first pressing Duplicate — pressing Duplicate is one
    # of the things it is there to prove, and a check that depends on an
    # earlier check having passed cannot tell you which one broke.
    DRAFT = "Leak investigation — walkthrough draft"
    # ⚠ **AND THE WALKTHROUGH'S OWN LEFTOVERS GO TOO.** It presses Duplicate
    # (which writes `… (copy)`, then `… (copy 2)`) and it publishes a second
    # draft named `… — at once <timestamp>`. There is no product door that
    # removes a template with orders behind it and there should not be, so the
    # FIXTURE clears what the last run left — otherwise the list grows by two
    # rows per run and the footer stops matching the drawing.
    leftovers = work_tables.WorkOrderTemplate.objects.filter(
        tenant_id=tenant.id, name__startswith=NAME
    ).exclude(name=NAME) | work_tables.WorkOrderTemplate.objects.filter(
        tenant_id=tenant.id, name__startswith=DRAFT
    )
    for old in leftovers:
        work_tables.WorkOrder.objects.filter(tenant_id=tenant.id, template_id=old.id).delete()
        work_models.WorkOrderTemplateVersion.objects.filter(
            tenant_id=tenant.id, template_id=old.id
        ).delete()
        print(f"cr070-d-fixture: cleared a walkthrough leftover — {old.name}")
        old.delete()
    for old in work_tables.WorkOrderTemplate.objects.filter(tenant_id=tenant.id, name=DRAFT):
        work_models.WorkOrderTemplateVersion.objects.filter(
            tenant_id=tenant.id, template_id=old.id
        ).delete()
        old.delete()
    draft = templates_svc.create_draft(actor, {
        "name": DRAFT,
        "service": SERVICE,
        "scope": work_tables.SCOPE_PREMISE,
        "crew_size": 2,
        "est_duration_minutes": 30,
    })
    templates_svc.replace_collection(actor, draft["id"], "tasks", V1_TASKS[:2])
    print(f"cr070-d-fixture: left a DRAFT — {DRAFT} (no number, 2 tasks)")

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-013/014/015/018@3be2d9fd (EP-WRK-03) · 10-execution-plan.md wave D task D6 · wireframes/Work-013.png · Work-022.png
# generated: 2026-09-05 by the Work walkthrough lane
# checklist: A=n/a(fixture prep, not product code) B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: not a product path — the walkthrough it feeds is the check. Idempotence proved by running it twice and reading the same 35 orders back.
# exceptions: it deletes work orders directly, which product code may never do — stated here because this is a FIXTURE and not a module, and it is scoped to the one template it created
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
