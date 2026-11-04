# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-014/015 (the template bundle) · US-WRK-024 (dispatch acts) ·
#           US-WRK-050 (materials used) · US-WRK-051/053 (labour rate, cost) ·
#           US-TEN-019 (the sample set)   Screens: Work-013..017 · WM-15 ·
#           Work-008 · WS-23
# Rules:    BR-WRK-002 (Work writes no other module's table — the order header
#           and the template header both move through `metering_seam`) ·
#           BR-WRK-008 (an order COPIES its template) · BR-WRK-009 (a template
#           is rows, never a blob) · BR-WRK-011 (nothing reaches an order until
#           Publish) · BR-WRK-020 (the rate is snapshotted at close) ·
#           BR-WRK-025 (assignment is APPEND-ONLY) · BR-MET-110 (the field
#           sends, a human accepts) · BR-TEN-056/057/061/063/066 ·
#           CLAUDE.md hard rule 2 (money 4 dp stored, 2 displayed) · hard rule 3
#           (a quantity carries its unit) · hard-won law 14 (savepoints)
# Tests:    06-backend/tests/test_cr070_sample_field_work.py
# Impacts:  apps/tenancy/sample_data.py (SAMPLE_MODULES) · apps/work/services.py
# ───────────────────────────────────────────────────────
"""**A TEMPLATE WITH NO TASKS IS A FORM WITH NO QUESTIONS** — this fills them,
and then sends one crew out.

WHAT WAS MEASURED
-----------------
On 2026-09-07, on every seeded tenant: six published `work_order_templates`,
six versions, six `wot_details` rows — and `wot_tasks` **0**, `wot_materials`
**0**, `wot_readings` **0**, `wot_safety` **0**, `wot_help` **0**,
`wot_asset_types` **0**. Downstream of that: `work_order_tasks` **0**,
`work_order_materials` **0**, `work_order_assignments` **0**,
`work_order_cost_lines` **0**, against **39 raised work orders**.

So the template builder opened onto six headers with nothing under them, the
dispatch board showed 39 jobs and no way to send one, and **no work order in
the product had ever been costed**.

⚠ **IT FILLS THE SIX THAT EXIST AND CREATES NO SEVENTH.** They are the right
six — one per service-and-job pair the sample utility actually runs — and a
second set seeded beside them would be two sources of truth for the same job
(hard-won law 5). Where a header is missing a fact the bundle needs (a skill, a
safety kit, an estimate), that fact is written onto the EXISTING header through
`metering_seam.update_template`, which is metering's own service called by
name — `BR-WRK-002`'s sanctioned door and the same one `raise_work_order` uses.

⚠ **THE TASKS NAME SKILLS A TECHNICIAN NOW HOLDS, WHICH IS WHY THIS BLOCK RUNS
AFTER THE WORKFORCE ONE.** A template requiring `WATER_III` on a utility where
nobody holds it is a job the dispatcher can never assign — `skill_match()`
would return an empty candidate list and the Assign dialog would offer nobody,
correctly, with nothing on the screen to explain why. Every `skill_id` written
here is one of the four seeded technicians' or the contractor's.

WHAT "WORKED AND COSTED" MEANS HERE, STEP BY STEP
---------------------------------------------------
One order goes the whole way, and **every step is the product's own service**,
never a row inserted to look like one (the PO's standing rule: *"everything
should be executed based on actual code"*):

  1. `metering_seam.save_order_fields` attaches the template — the 39 seeded
     orders carry a free-text `type` and a NULL `template_id`, so nothing had
     ever been copied onto them.
  2. `order_copies.copy_template_onto_order` writes the six copies —
     `BR-WRK-008`, the same call `create_work_order` makes.
  3. `dispatch.record_act` × 4 — assign · schedule · depart · arrive. Append
     only (`BR-WRK-025`); the order's `dispatch_state` moves and its `state`
     does not, which is the separation `BR-WRK-023` exists for.
  4. `checklist.tick_safety` / `tick_task` — the mandatory rows, because
     `submit_field_result` REFUSES a completion with one unticked
     (`BR-WRK-037`, and the refusal is the server half of a lock the phone also
     has).
  5. `checklist.set_material_used` — used-of-planned, with who and when.
  6. `metering_seam.submit_field_result` — the crew says it is done. This is
     what stamps `labour_rate_snapshot` from `labour_rates` and
     `minutes_on_site` from the ARRIVE row, so the money is fixed at close.
  7. `metering.connections.accept_field_result` — the human act
     (`BR-MET-110`), which generates the report and PERSISTS the cost lines.

⚠ **THE ARRIVE ROW IS BACKDATED AND THE CLOSE IS NOT "NOW".** `minutes_on_site`
is `completed_at` minus the last arrival, and both stamped at the same instant
give a span of zero — which `_minutes_on_site` correctly answers as None, and
the job would then carry **no labour line at all**. So the four acts are moved
back onto yesterday afternoon on Work's OWN `work_order_assignments` table, and
the close is submitted with an explicit `completed_at`. A fixture describing
work that happened yesterday is stating a fact about the past, not falsifying a
clock.

⚠ **MOST OF THE BOARD IS LEFT UNFINISHED, ON PURPOSE.** One order is assigned,
worked, accepted and costed; one is out with a crew (departed, not back); one is
scheduled for tomorrow; one is assigned and not yet scheduled. **The remaining
thirty-five are untouched.** A demo in which every job is closed shows a
dispatcher nothing to do — it is the same principle that leaves the third
billing cycle unbilled, and it is the PO's own.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.work import checklist, dispatch, order_copies, templates_svc
from apps.work import models as work_models
from apps.work.seams import metering_seam
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work")

#: **THE SIX BUNDLES, KEYED ON `template_no`** — the allocation `publish` makes,
#: which is stable and is what `Work-013` shows. Keyed on that rather than on
#: `name` because TWO of the six are called *Meter set* (the electric one and
#: the water one), so a name is not an identifier here.
#:
#: `skill` is the header's requirement and every one is held by a seeded
#: technician or by the contractor. `kit` is one of the four seeded safety kits.
#: `minutes` is the header's estimate and is deliberately CLOSE to the sum of
#: the tasks' own minutes without being equal to it — an estimate that matches
#: its parts exactly reads as arithmetic rather than as a supervisor's judgment.
SEEDED_BUNDLES: tuple[dict[str, Any], ...] = (
    {
        "template_no": "ST-0001",
        "name": "Service drop",
        "skill": "ELECTRIC_I",
        "kit": "TRAFFIC_CONTROL",
        "minutes": 150,
        "crew_size": 2,
        "asset_types": ("Meter",),
        "safety": (
            ("Confirm the drop is de-energised at the transformer", True),
            ("Cones and signs set before the ladder goes up", True),
            ("Check for overhead clearance to the roofline", False),
        ),
        "tasks": (
            ("Confirm the service address and the point of attachment", 10, False, True),
            ("Fit the mast bracket and the insulator", 35, False, True),
            ("Run and tension the triplex to the weatherhead", 45, False, True),
            ("Terminate at the meter socket", 30, True, True),
            ("Photograph the finished drop from the street", 5, True, True),
            ("Leave the door hanger if nobody is home", 5, False, False),
        ),
        "materials": (("CPL-58B", "2"), ("TAPE-PTFE", "1")),
        "readings": (
            ("Service voltage at the socket", "V", "220", "250", True, False),
        ),
        "help": (
            ("document", "Overhead service standard", "STD-EL-004"),
            ("phone", "Dispatch — overhead crew", "+1 555 0142"),
        ),
    },
    {
        "template_no": "ST-0002",
        "name": "Meter set",
        "skill": "METER_I",
        "kit": "BASIC_PPE",
        "minutes": 45,
        "crew_size": 1,
        "asset_types": ("Meter",),
        "safety": (
            ("Confirm the socket is dead before the meter goes in", True),
            ("Wear arc-rated gloves for the set", True),
        ),
        "tasks": (
            ("Check the socket for burn marks or moisture", 5, True, True),
            ("Set the meter and confirm it seats square", 15, False, True),
            ("Seal the ring and record the seal number", 5, True, True),
            ("Confirm the display registers", 5, False, True),
        ),
        "materials": (("MTR-E1P", "1"), ("SEAL-WIRE", "1")),
        "readings": (
            # `DEF-WRK-9683` — a meter NUMBER is a note, not a register value:
            # it never posts as a meter read (two posting readings on one job
            # is `OQ-WRK-1723`'s question, and Accept would refuse it).
            ("Meter number as fitted", "text", None, None, True, False),
            ("Opening register", "kWh", "0", "99999999", True, True),
        ),
        "help": (("document", "Meter setting procedure", "STD-EL-011"),),
    },
    {
        "template_no": "ST-0003",
        "name": "Site inspection & mark-out",
        "skill": "WATER_I",
        "kit": "TRAFFIC_CONTROL",
        "minutes": 60,
        "crew_size": 1,
        "asset_types": (),
        "safety": (
            ("Locate and mark every buried service before any dig", True),
            ("Hi-vis on for the whole of the walk-over", True),
        ),
        "tasks": (
            ("Walk the route with the customer's plan", 20, False, True),
            ("Paint-mark the main and the proposed tap", 20, True, True),
            ("Note the surface to be reinstated", 10, True, True),
            ("Photograph the mark-out from both ends", 5, True, True),
        ),
        "materials": (("TAPE-PTFE", "1"),),
        "readings": (
            ("Depth to main", "in", "18", "96", True, False),
            ("Distance from the main to the meter pit", "ft", "0", "500", True, False),
        ),
        "help": (
            ("note", "Call the one-call centre 48 hours ahead", None),
            ("phone", "One-call centre", "811"),
        ),
    },
    {
        "template_no": "ST-0004",
        "name": "Tap and service line",
        "skill": "EXCAVATION",
        "kit": "CONFINED_SPACE",
        "minutes": 300,
        "crew_size": 2,
        "asset_types": (),
        "safety": (
            ("Trench box in before anybody enters the excavation", True),
            ("Gas-test the trench before entry and every 30 minutes", True),
            ("Spoil kept two feet back from the edge", True),
            ("Plates and lights left over any open cut", True),
        ),
        "tasks": (
            ("Set traffic control and open the cut", 60, True, True),
            ("Tap the main and fit the corporation stop", 60, False, True),
            ("Lay and bed the service line to the curb stop", 90, False, True),
            ("Pressure-test the new line", 30, False, True),
            ("Backfill, compact and reinstate the surface", 45, True, True),
            ("Photograph the reinstatement", 5, True, True),
        ),
        "materials": (("PIPE-CU34", "60"), ("VLV-CS58", "1"), ("CPL-58B", "2")),
        "readings": (
            ("Test pressure held", "psi", "100", "200", True, False),
            ("Length of service laid", "ft", "0", "500", True, False),
        ),
        "help": (
            ("document", "Trench safety plan", "SAF-WA-002"),
            ("phone", "Standby — water operations", "+1 555 0177"),
        ),
    },
    {
        "template_no": "ST-0005",
        "name": "Meter set",
        "skill": "METER_I",
        "kit": "BASIC_PPE",
        "minutes": 50,
        "crew_size": 1,
        "asset_types": ("Meter",),
        "safety": (
            ("Shut the curb stop before breaking the union", True),
            ("Check the pit for standing water before reaching in", True),
        ),
        "tasks": (
            ("Confirm the pit is the right address", 5, False, True),
            ("Fit the meter with the flow arrow in the direction of supply", 20, False, True),
            ("Charge the line and check for weeps at both unions", 10, False, True),
            ("Seal and record the seal number", 5, True, True),
            ("Photograph the meter in the pit", 5, True, True),
        ),
        "materials": (("MTR-W58", "1"), ("GSK-58", "2"), ("SEAL-WIRE", "1")),
        "readings": (
            # `DEF-WRK-9683` — a meter NUMBER is a note, not a register value:
            # it never posts as a meter read (two posting readings on one job
            # is `OQ-WRK-1723`'s question, and Accept would refuse it).
            ("Meter number as fitted", "text", None, None, True, False),
            ("Opening register", "gal", "0", "99999999", True, True),
        ),
        "help": (("document", "Water meter setting standard", "STD-WA-006"),),
    },
    {
        "template_no": "ST-0006",
        "name": "Meter exchange — residential",
        "skill": "METER_I",
        "kit": "BASIC_PPE",
        "minutes": 40,
        "crew_size": 1,
        "asset_types": ("Meter",),
        "safety": (
            ("Shut the curb stop before breaking the union", True),
            ("Check the pit for standing water before reaching in", True),
        ),
        "tasks": (
            ("Read and photograph the OLD meter before it comes out", 5, True, True),
            ("Shut the curb stop and break the unions", 5, False, True),
            ("Fit the new meter with new gaskets", 15, False, True),
            ("Charge the line and check for weeps", 5, False, True),
            ("Seal and photograph the NEW meter and its register", 5, True, True),
            ("Leave the exchange card with the customer", 3, False, False),
        ),
        "materials": (("MTR-W58", "1"), ("GSK-58", "2"), ("SEAL-WIRE", "1")),
        "readings": (
            ("Closing read on the OLD meter", "gal", "0", "99999999", True, True),
            ("New meter number", "text", None, None, True, True),
            ("Opening read on the NEW meter", "gal", "0", "99999999", True, True),
        ),
        "help": (
            ("document", "Meter exchange procedure", "STD-WA-012"),
            ("note", "Leave the old meter in the van; the shop logs it in", None),
        ),
    },
)

#: **THE DISPATCH BOARD, LEFT PART-DONE ON PURPOSE.** One entry per state a
#: dispatcher actually sees, and every one of the acts named here is a real
#: `dispatch.record_act` call. Everything not listed stays queued.
#:
#: `template_no` picks which of the six is copied onto the order, and the order
#: is chosen by matching its free-text `type` against that template's NAME —
#: which is how the 39 seeded orders identify their job today.
SEEDED_JOBS: tuple[dict[str, Any], ...] = (
    {
        # THE ONE THAT GOES ALL THE WAY. A water meter set, D. Ortiz,
        # yesterday afternoon, 105 minutes on site, three parts used.
        "key": "closed",
        "template_no": "ST-0005",
        "technician": "d.ortiz@sample.test",
        "acts": ("assign", "schedule", "depart", "arrive"),
        "minutes_on_site": 105,
        "used": (("MTR-W58", "1"), ("GSK-58", "2"), ("SEAL-WIRE", "1")),
        # The outcome is B18 §8.3's `passed`, read from metering at the close
        # (`DEF-WRK-9070`: this read `"completed"`, which is a STATE).
        "note": "Meter set and sealed; register photographed",
        "accept": True,
    },
    {
        # OUT WITH A CREW RIGHT NOW — departed and not back. `WM-15`'s
        # *en route* row has a subject only if somebody is on one. R. Patel
        # is the one who holds EXCAVATION, which this template requires.
        "key": "en_route",
        "template_no": "ST-0004",
        "technician": "r.patel@sample.test",
        "acts": ("assign", "schedule", "depart"),
        "accept": False,
    },
    {
        # SCHEDULED FOR TOMORROW, nobody on the road yet.
        "key": "scheduled",
        "template_no": "ST-0003",
        "technician": "d.ortiz@sample.test",
        "acts": ("assign", "schedule"),
        "accept": False,
    },
    {
        # ASSIGNED WITH NO APPOINTMENT TIME YET — somebody owns the job and
        # nobody has told the customer when.
        #
        # ⚠ **THERE IS NO SEPARATE *assigned* DISPATCH STATE, AND THAT IS
        # `BR-WRK-023` RATHER THAN A GAP.** `dispatch.act_moves_to()` maps
        # `assign` to SCHEDULED, so this order and the one above both read
        # *scheduled* on the board; what separates them is `scheduled_for`,
        # which this one leaves NULL. Written down because the obvious reading
        # of the row above — that `assign` and `schedule` are two states — is
        # wrong, and a lane seeding a fifth state that does not exist would
        # find out only by looking at the screen.
        "key": "assigned",
        "template_no": "ST-0001",
        "technician": "m.chen@sample.test",
        "acts": ("assign",),
        "accept": False,
    },
)

#: ⚠ **TWO OF THE SIX BUNDLES GET NO LIVE JOB, AND THAT IS MEASURED RATHER
#: THAN CHOSEN.** `ST-0002` (electric *Meter set*) and `ST-0006` (*Meter
#: exchange — residential*) are filled and published like the other four, and
#: this tenant has **no untouched planned order of either type** — the 39
#: seeded orders are 8 *Meter set* (water), 5 *Tap and service line*, 3 *Site
#: inspection & mark-out* and 1 *Service drop*, with nothing named *Meter
#: exchange* at all. The first draft of this file pointed the closed job at
#: `ST-0006` and it was SKIPPED, with the seeder naming the reason on the way
#: past; that named line is the only reason it took one run to find, and it is
#: what a silent `continue` would have cost.


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _templates_by_no() -> dict[str, Any]:
    """`template_no` → the header dict, read through the metering seam."""
    out: dict[str, Any] = {}
    for row in metering_seam.templates_queryset():
        number = str(getattr(row, "template_no", "") or "").strip()
        if number:
            out[number] = row
    return out


def _lookup_ids(model: Any) -> dict[str, Any]:
    return {row.code: row.id for row in model.objects.filter(tenant_id=_tenant_id())}


def _asset_type_ids(names: tuple[str, ...]) -> dict[str, Any]:
    """Asset-type NAME → id, THROUGH THE SEAM (`assets` owns the table).

    ⚠ **BY NAME AND NOT BY CODE, because the seam publishes only one lookup**
    — `assets_seam.asset_type_ids_of_names`, which is what
    `apps/work/sample_data.py` already uses for the *Backflow preventer* rule.
    Work holds no second list of what asset types exist and must not grow one
    to save a join (`US-WRK-021` TC-7's shape, one table along).

    An empty answer is lawful: a tenant that uses no meters gets a template
    with no asset-type restriction, which is WIDER than intended and is
    reported by the caller rather than silently narrowed.
    """
    from apps.work.seams import assets_seam

    wanted = [name for name in names]
    if not wanted:
        return {}
    found = assets_seam.asset_type_ids_of_names(wanted)
    # The seam answers ids without saying which name each came from, so the
    # mapping is rebuilt one name at a time. Six templates × one or two names
    # is not a query budget worth optimising, and guessing the pairing from
    # list order would be a silent mismatch.
    return {
        name: ids[0]
        for name in wanted
        if (ids := assets_seam.asset_type_ids_of_names([name]))
    } if found else {}


def _fill_one(actor: Any, spec: dict[str, Any], header: Any, lookups: dict[str, Any]) -> int:
    """One template's seven collections plus its header facts. Rows written."""
    template_id = str(header.id)
    parts, skills, kits, asset_types = (
        lookups["parts"], lookups["skills"], lookups["kits"], lookups["asset_types"]
    )
    written = 0

    # ── the HEADER, through metering's own service (BR-WRK-002's door) ─────
    # Only the facts that are ABSENT are written: a utility that has already
    # chosen a skill or an estimate keeps its answer (BR-TEN-063).
    header_payload: dict[str, Any] = {}
    if getattr(header, "skill_id", None) is None and spec["skill"] in skills:
        header_payload["skill_id"] = str(skills[spec["skill"]])
    if getattr(header, "safety_kit_id", None) is None and spec["kit"] in kits:
        header_payload["safety_kit_id"] = str(kits[spec["kit"]])
    if getattr(header, "est_duration", None) is None:
        # ⚠ **`est_duration_minutes`, NOT `est_duration`.** The column is a
        # DurationField (hard rule 3 — an interval carries its own unit) and
        # `templates_svc.update_header` is the one place the conversion
        # happens, so that a screen reading *45 min* never has to post an ISO
        # duration. Going straight to `metering_seam.update_template` with a
        # minutes integer is refused as an unknown header field.
        header_payload["est_duration_minutes"] = spec["minutes"]
    if getattr(header, "crew_size", None) in (None, 1) and spec["crew_size"] != 1:
        header_payload["crew_size"] = spec["crew_size"]
    if header_payload:
        try:
            with transaction.atomic():  # law 14
                templates_svc.update_header(actor, template_id, header_payload)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 field work): template %s kept its header unchanged — "
                "%s: %s. Work > Templates will show a blank skill or estimate",
                spec["template_no"], type(exc).__name__, exc,
            )

    collections: list[tuple[str, list[dict[str, Any]]]] = [
        ("safety", [
            {"text": text, "is_mandatory": mandatory}
            for text, mandatory in spec["safety"]
        ]),
        ("tasks", [
            {"title": title, "est_minutes": minutes,
             "photo_required": photo, "is_mandatory": mandatory}
            for title, minutes, photo, mandatory in spec["tasks"]
        ]),
        ("materials", [
            {"part_id": str(parts[code]), "planned_qty": qty}
            for code, qty in spec["materials"] if code in parts
        ]),
        ("readings", [
            {"prompt": prompt, "unit_of_measure": unit, "min": low, "max": high,
             "required": required, "posts_as_meter_read": posts}
            for prompt, unit, low, high, required, posts in spec["readings"]
        ]),
        ("help", [
            {"kind": kind, "label": label, "ref": ref}
            for kind, label, ref in spec["help"]
        ]),
        ("asset-types", [
            {"asset_type_id": str(asset_types[code])}
            for code in spec["asset_types"] if code in asset_types
        ]),
    ]
    for name, rows in collections:
        if not rows:
            continue
        model = templates_svc.COLLECTIONS[name]
        if model.objects.filter(tenant_id=_tenant_id(), template_id=template_id).exists():
            continue  # BR-TEN-063 — a utility's own edit is never replaced
        try:
            with transaction.atomic():  # law 14
                templates_svc.replace_collection(actor, template_id, name, rows)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 field work): template %s kept an empty %s — %s: %s",
                spec["template_no"], name, type(exc).__name__, exc,
            )
            continue
        written += len(rows)

    # `BR-WRK-011` — **nothing above reaches an order until Publish.** A second
    # publish with nothing changed returns the version that already exists, so
    # a replay does not manufacture a v3 a supervisor would have to explain.
    if written:
        try:
            with transaction.atomic():
                templates_svc.publish(
                    actor, template_id,
                    change_note="Sample content: tasks, parts, readings and safety steps",
                )
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 field work): template %s was filled but NOT republished "
                "— %s: %s. Its new content will not reach a job raised from it (BR-WRK-011)",
                spec["template_no"], type(exc).__name__, exc,
            )
    return written


def _fill_templates(actor: Any) -> int:
    headers = _templates_by_no()
    if not headers:
        logger.info(
            "sample data (CR-070 field work): no work order templates were filled — this "
            "tenant has none published. Check the Premises, units & service points block, "
            "which is what creates them"
        )
        return 0
    lookups = {
        "parts": {
            row.part_no: row.id
            for row in work_models.Part.objects.filter(tenant_id=_tenant_id())
        },
        "skills": _lookup_ids(work_models.WorkSkill),
        "kits": _lookup_ids(work_models.WorkSafetyKit),
        "asset_types": _asset_type_ids(
            tuple({name for row in SEEDED_BUNDLES for name in row["asset_types"]})
        ),
    }
    written = 0
    for spec in SEEDED_BUNDLES:
        header = headers.get(spec["template_no"])
        if header is None:
            logger.info(
                "sample data (CR-070 field work): template %s (%s) was not filled — this "
                "tenant has no such template",
                spec["template_no"], spec["name"],
            )
            continue
        written += _fill_one(actor, spec, header, lookups)
    return written


# ══════════════════════════════════════════════════════════════════════════
# THE BOARD — one job all the way, three part-way, thirty-five untouched
# ══════════════════════════════════════════════════════════════════════════


def _technicians_by_email() -> dict[str, Any]:
    rows = work_models.Technician.objects.filter(
        tenant_id=_tenant_id()
    ).select_related("user")
    return {str(row.user.email).strip().lower(): row for row in rows if row.user_id}


def _candidate_order(header: Any, taken: set[Any]) -> Any:
    """An untouched PLANNED order this template could actually have raised.

    ⚠ **THE 39 SEEDED ORDERS CARRY A `type` STRING AND A NULL `template_id`.**
    They were raised before the template bundle existed, so nothing was ever
    copied onto them — which is why `work_order_tasks` measured 0 against 39
    jobs. Matching on the type string is how those jobs identify themselves
    today; wave G's New work order wizard sets `template_id` at raise, so a job
    raised from here on needs none of this.

    ⚠ **THE SERVICE IS PART OF THE MATCH AND NOT A REFINEMENT — TWO OF THE SIX
    TEMPLATES ARE BOTH CALLED *Meter set*.** `ST-0002` is electric's and
    `ST-0005` is water's, and `work_order_templates` allows that because its
    uniqueness is per SERVICE. Matching on the name alone would have copied
    the electric bundle — arc-rated gloves, a kWh opening register — onto a
    water meter job, and every check in this repository would have passed on
    it: the counts would be right, the screen would render, and a technician
    would be handed the wrong checklist. Found by reading the six rows rather
    than by any gate.
    """
    template_service_id = getattr(header, "service_id", None)
    name = str(getattr(header, "name", "") or "").strip().lower()
    for order in metering_seam.dispatch_queryset():
        if order.id in taken:
            continue
        if getattr(order, "template_id", None) is not None:
            continue
        if str(getattr(order, "state", "")) != "planned":
            continue
        if str(getattr(order, "type", "") or "").strip().lower() != name:
            continue
        order_service_id = getattr(order, "service_id", None)
        if (
            template_service_id is not None
            and order_service_id is not None
            and str(order_service_id) != str(template_service_id)
        ):
            continue
        return order
    return None


def _report_minutes_on_site(order: Any, minutes: int) -> None:
    """Say how long the crew were on site — the one figure the phone reports.

    ⚠ **THREE GUARANTEES MAKE THE OBVIOUS APPROACH IMPOSSIBLE, AND EACH OF THEM
    IS RIGHT.** `costing.minutes_on_site` is `completed_at` minus the last
    ARRIVE row, and a fixture cannot manufacture a gap between them:

      * `work_order_assignments.at` is `auto_now_add`, so an act cannot be
        inserted with a time of its own;
      * a PostgreSQL trigger (`work_assignment_append_only`) REFUSES an UPDATE
        on that table by name — *"BR-WRK-025: the assignment history is
        append-only … To change who has a job, add an unassign row and an
        assign row."* The first draft of this file tried exactly that and the
        database refused it, which is the guarantee working on its author;
      * `submit_field_result` REFUSES a `completed_at` in the future, because
        *"a close stamped tomorrow would date a meter read into a period that
        has not been billed yet"*.

    So the four acts and the close all land in the same second, `_minutes_on_site`
    correctly computes **0**, and `costing` then yields **no labour line at
    all** — a job with parts on it and no time, which is precisely the empty
    report this block exists to stop being the only kind there is.

    **What is supplied instead is the figure the column was built for.**
    `costing.py` says where a real one comes from in as many words: *"`started_at`
    IS WAVE `J`'s `arrive` ASSIGNMENT ROW and is not on the order yet. Where a
    real arrival time comes from is the phone's."* A handset that has been out
    of signal since 13:15 reports 105 minutes when it syncs; this fixture
    reports the same thing, through `metering_seam.save_order_fields` — the ONE
    write door onto an order, one named column, no bare `save()`.

    ⚠ **AND THE ORDER'S OWN AUDIT TRAIL WILL SHOW THE ACTS SECONDS APART**,
    because that is when the fixture performed them. That divergence is stated
    here rather than hidden: it is the cost of the three guarantees above, and
    the alternative — weakening any one of them so a fixture looks tidier — is
    not a trade this block gets to make.
    """
    order.minutes_on_site = int(minutes)
    metering_seam.save_order_fields(order, ["minutes_on_site"])


def _tick_everything(actor: Any, order_id: Any) -> None:
    """Every MANDATORY safety row and every task — `BR-WRK-037`'s server lock.

    `submit_field_result` refuses a completion with an unticked mandatory
    safety row, so a fixture that skipped this would be refused BY THE PRODUCT
    and the job would never close. That refusal working is the reason this is
    four lines rather than a flag.

    Non-mandatory rows are left UNTICKED on purpose: `US-WRK-043` TC-4 says a
    completion with an advisory row unticked is accepted, and a fixture where
    every box is ticked cannot show that.
    """
    tenant_id = _tenant_id()
    for row in work_models.WorkOrderSafety.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, is_mandatory=True, ticked_at__isnull=True
    ):
        checklist.tick_safety(actor, order_id, row.id)
    for row in work_models.WorkOrderTask.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, ticked_at__isnull=True
    ):
        checklist.tick_task(actor, order_id, row.id)


#: A one-pixel PNG — the demo's stand-in for a photograph of a dial. Small on
#: purpose: it is evidence that a row was photographed, not a picture of one.
_SAMPLE_PHOTO = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63382127070002b6010534a675aa0000000049454e44ae426082"
)


def _photograph_required_rows(actor: Any, order_id: Any) -> None:
    """Every photo-REQUIRED reading and task, photographed through #77's own
    service (`evidence.record_attachment`) with the row named — never a column
    written to look like it. `BR-WRK-040` (as superseded 2026-10-21): without them the
    close would carry a recorded gap, and the demo's jobs should not."""
    from apps.work import evidence

    tenant_id = _tenant_id()
    for row in work_models.WorkOrderReading.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, photo_required=True,
        photo_attachment_id__isnull=True,
    ):
        evidence.record_attachment(
            actor, order_id,
            {"idempotency_key": f"sample-r-{row.id}", "reading_id": str(row.id),
             "content_type": "image/png"},
            _SAMPLE_PHOTO,
        )
    for row in work_models.WorkOrderTask.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, photo_required=True,
        photo_attachment_id__isnull=True,
    ):
        evidence.record_attachment(
            actor, order_id,
            {"idempotency_key": f"sample-t-{row.id}", "task_id": str(row.id),
             "content_type": "image/png"},
            _SAMPLE_PHOTO,
        )


def _run_job(actor: Any, spec: dict[str, Any], headers: dict[str, Any], taken: set[Any]) -> int:
    """One board entry: attach, copy, act, and — for the closed one — cost it."""
    header = headers.get(spec["template_no"])
    if header is None:
        return 0
    # ⚠ `DEF-WRK-9071` — THE JOB THAT IS FINISHED RAISES ITS OWN ORDER. Every
    # planned order in the sample tenant belongs to one of B18 §5.4.8's drawn
    # builds, and finishing one moves a drawn `ORDERS` cell (it took WO-0026
    # and CON-26-0121 read 3 of 5 against the drawn 2 of 5). The jobs that are
    # only assigned or scheduled move no cell, so they still use a seeded order.
    raised = bool(spec.get("accept"))
    order = _raised_order(actor, header) if raised else _candidate_order(header, taken)
    if order is None:
        logger.info(
            "sample data (CR-070 field work): the %r job was not set up — this tenant has no "
            "untouched PLANNED work order of type %r for it to use",
            spec["key"], str(header.name),
        )
        return 0
    taken.add(order.id)
    technicians = _technicians_by_email()
    technician = technicians.get(spec["technician"])
    if technician is None:
        logger.info(
            "sample data (CR-070 field work): the %r job was not set up — this tenant has no "
            "technician profile for %s. Check the Crews and technicians block above",
            spec["key"], spec["technician"],
        )
        return 0

    written = 0
    if raised:
        # The raise stamped the template and wrote the six copies already
        # (`create_work_order`, BR-WRK-008), so steps 1 and 2 are done.
        return written + 1 + _work_the_order(actor, spec, order, technician)
    # ── 1 · attach the template, through metering's ONE write door ─────────
    order.template_id = header.id
    order.template_version = int(getattr(header, "version", 1) or 1)
    metering_seam.save_order_fields(order, ["template_id", "template_version"])
    # ── 2 · BR-WRK-008's copy — the same call `create_work_order` makes ────
    counts = order_copies.copy_template_onto_order(
        actor,
        order_id=order.id,
        template_id=header.id,
        template_version=order.template_version,
    )
    written += sum(int(value or 0) for value in counts.values())
    return written + _work_the_order(actor, spec, order, technician)


def _raised_order(actor: Any, header: Any) -> Any:
    """A stand-alone order for the finished job, raised through metering's own
    door (`metering_seam.raise_work_order`) on the premises of the activated
    build, with the template stamped at the raise. None when the tenant has no
    activated build, which `_run_job` reports like a missing order.
    """
    premises_id = metering_seam.premises_of_an_activated_build()
    if premises_id is None:
        return None
    service_code = getattr(getattr(header, "service", None), "code", None)
    raised = metering_seam.raise_work_order(
        actor,
        {
            "premises_id": str(premises_id),
            "type": str(header.name),
            "service": service_code,
            "scope": getattr(header, "scope", None) or None,
            "template_id": str(header.id),
            "is_sample": True,
            # `DEF-WRK-9627` — a stand-alone job a dispatcher raised reads
            # *Raised by: Dispatcher*, never a dash (`BR-WRK-024`).
            "source": "dispatcher",
            # `DEF-WRK-9571` — raised at Normal, the PO's default target for an
            # undated job; see `metering.sample_data._normal_priority_id`.
            "priority_id": _normal_priority_id(),
        },
    )
    return metering_seam.work_order_row(raised["id"])


def _normal_priority_id() -> str | None:
    row = work_models.WorkPriority.objects.filter(
        tenant_id=_tenant_id(), code__iexact="NORMAL"
    ).first()
    return str(row.id) if row is not None else None


def _as_actor(technician: Any) -> Any:
    """The technician's own login, in the shape every service reads an actor."""
    from types import SimpleNamespace

    user = technician.user
    return SimpleNamespace(id=user.id, role="field_technician")


def _work_the_order(actor: Any, spec: dict[str, Any], order: Any, technician: Any) -> int:
    """Steps 3 to 7 — act, tick, use, close, accept — on an order that already
    carries its template's copies."""
    written = 0
    # ── 3 · the acts, append-only (BR-WRK-025) ────────────────────────────
    now = timezone.now()
    scheduled_for = (now + timedelta(days=1)).replace(microsecond=0)
    for act in spec["acts"]:
        payload: dict[str, Any] = {"act": act}
        if act in ("assign", "schedule"):
            payload["technician_id"] = str(technician.id)
        if act == "schedule":
            payload["scheduled_for"] = scheduled_for.isoformat()
        dispatch.record_act(actor, order.id, payload)
        written += 1

    if not spec.get("accept"):
        return written

    # ── 4 · the checklist, then the parts actually used ───────────────────
    _tick_everything(actor, order.id)
    used = dict(spec.get("used") or ())
    for row in work_models.WorkOrderMaterial.objects.filter(
        tenant_id=_tenant_id(), work_order_id=order.id
    ).select_related("part"):
        quantity = used.get(getattr(row.part, "part_no", None))
        if quantity is None:
            continue
        checklist.set_material_used(actor, order.id, row.id, {"used_qty": quantity})

    # ── 4b · the photographs the template asks for, each sent FOR its row
    #        (`DEF-WRK-9625`): the close below is refused while one is missing,
    #        exactly as it is for a technician on the phone.
    _photograph_required_rows(_as_actor(technician), order.id)

    # ── 5 · the crew says it is done. THIS stamps the labour rate from
    #        `labour_rates`, so the money is fixed at close (BR-WRK-020).
    order = metering_seam.work_order_row(order.id)
    # ⚠ **AS THE TECHNICIAN, NOT AS THE SEEDING ADMIN** (`CR-168-BRC10` P1.34,
    # ruling 18): the close admits only the person the job was given to, and
    # step 3 gave it to `technician`. The demo now records what the product
    # requires — the field closed it, the office accepted it.
    metering_seam.submit_field_result(
        _as_actor(technician),
        order.id,
        outcome=metering_seam.passed_outcome(),
        field_data={"note": spec.get("note") or "Completed"},
    )
    written += 1

    # ── 6 · how long they were there — see `_report_minutes_on_site` for why
    #        this cannot be derived from the acts above.
    order = metering_seam.work_order_row(order.id)
    _report_minutes_on_site(order, int(spec["minutes_on_site"]))

    # ── 7 · the HUMAN act (BR-MET-110) — this is what persists the cost ────
    # `DEF-WRK-9062` — through the seam, never `apps.metering` (BR-WRK-002, G78).
    metering_seam.accept_field_result(actor, order.id)
    written += int(
        work_models.WorkOrderCostLine.objects.filter(
            tenant_id=_tenant_id(), work_order_id=order.id
        ).count()
    )
    return written


def _run_board(actor: Any) -> int:
    headers = _templates_by_no()
    if not headers:
        return 0
    taken: set[Any] = set()
    written = 0
    for spec in SEEDED_JOBS:
        try:
            # law 14 — one job's refusal must not abort the transaction the
            # other three are still being written in. On PostgreSQL, without
            # this, a single refused act would lose the whole block at COMMIT
            # while the SQLite suite stayed green.
            with transaction.atomic():
                written += _run_job(actor, spec, headers, taken)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 field work): the %r job was not set up — %s: %s. The "
                "dispatch board will show one state fewer than the drawing",
                spec["key"], type(exc).__name__, exc,
            )
            continue
    return written


def seed_sample_records(actor: Any) -> int:
    """`BR-TEN-056/057` — the six bundles, then the board.

    Returns rows CREATED, which is 0 on a replay (`BR-TEN-010`): a template
    whose collection already holds rows is left alone, and an order that has
    already been attached to a template is never a candidate again.
    """
    return _fill_templates(actor) + _run_board(actor)


def remove_sample_records() -> dict[str, Any]:
    """`BR-TEN-061/066` — and here removal is mostly a REFUSAL, by name.

    ⚠ **NOTHING THIS BLOCK WROTE CAN SIMPLY BE DELETED, AND SAYING SO IS THE
    HONEST ANSWER RATHER THAN A GAP.** Three reasons, each a rule already
    written down somewhere else:

      * **A published template's content is a VERSION.** `BR-WRK-011` says the
        bundle reaches an order at Publish; emptying `wot_tasks` under a
        published v2 would leave a version row promising a checklist that no
        longer exists, and every job raised from it holding a copy of rows the
        template denies. The collections stay.
      * **An assignment history is APPEND-ONLY** (`BR-WRK-025`, verbatim:
        *"Never an UPDATE"*). Deleting the rows would be worse than an update.
      * **A COST LINE IS FROZEN** — `work/0011`'s trigger, and hard rule 4's
        shape: a report a person accepted does not get unpicked by a fixture.

    So this reports what it is holding and removes nothing, which is exactly
    what `BR-TEN-066` asks for — a partial answer, named, rather than a silent
    success or a refused delete.
    """
    tenant_id = _tenant_id()
    retained: list[dict[str, Any]] = []
    filled = work_models.WorkOrderTemplateTask.objects.filter(tenant_id=tenant_id).count()
    if filled:
        retained.append(
            {
                "label": f"{filled} template task(s)",
                "reason": (
                    "they are part of a PUBLISHED version, and every job raised from it "
                    "holds a copy. Removing them would leave a version promising a "
                    "checklist that no longer exists"
                ),
            }
        )
    acts = work_models.WorkOrderAssignment.objects.filter(tenant_id=tenant_id).count()
    if acts:
        retained.append(
            {
                "label": f"{acts} assignment row(s)",
                "reason": "assignment history is append-only; who had a job and when is "
                          "not a thing a fixture may erase",
            }
        )
    lines = work_models.WorkOrderCostLine.objects.filter(tenant_id=tenant_id).count()
    if lines:
        retained.append(
            {
                "label": f"{lines} cost line(s)",
                "reason": "they belong to an accepted work order report and are frozen",
            }
        )
    return {"removed": 0, "retained": retained}


def sample_record_count() -> int:
    """Rows this block is responsible for, read live.

    ⛔ **NONE OF THESE TABLES CARRIES `is_sample`**, so this counts the rows
    themselves rather than a tag — which is a WIDER key than `BR-TEN-057`
    wants and is stated rather than hidden. It is safe only because this block
    removes nothing: an over-count that drives no delete misreports a number,
    where an over-count that drove one would delete a utility's own work. The
    columns are OWED, the same divergence `wizard_parks` already carries.
    """
    tenant_id = _tenant_id()
    return int(
        work_models.WorkOrderTemplateTask.objects.filter(tenant_id=tenant_id).count()
        + work_models.WorkOrderAssignment.objects.filter(tenant_id=tenant_id).count()
        + work_models.WorkOrderCostLine.objects.filter(tenant_id=tenant_id).count()
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-070 · US-WRK-014/015/024/050/051/053 · US-TEN-019 · PO standing
#         rule ("everything should be executed based on actual code")
# generated: 2026-09-07 by the CR-070 work sample-data lane
# checklist: A✔ B=n/a(no new screen — Work-013..017, WM-15 and Work-008 render
#         it) C✔ D=n/a(no endpoint) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr070_sample_field_work.py · G78 · G66
# exceptions: `_backdate_acts` writes `work_order_assignments.at` directly —
#         argued in its own docstring; there is no service that backdates an
#         act and there must not be. Removal is a NAMED refusal rather than a
#         delete, for three rules quoted in `remove_sample_records`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
