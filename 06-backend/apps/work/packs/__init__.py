# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-016 (EP-WRK-03) §5 — *"pack | Work-014 | WS-14 | platform
#           data in `apps/work/packs/` (three packs) | code data |
#           reference-data | prefill only; never stored as a link"*.
#           Screens: Work-014 (`wireframes/Work-014.png`)
# Rules:    BR-WRK-011 (Publish is the ONE write — a pack writes NOTHING) ·
#           BR-WRK-009 (a bundle is ROWS) · BR-WRK-015 (a reading's unit is a
#           column) · BR-MET-109 (the utility's own templates decide the
#           grouping) · CLAUDE.md hard rule 3 (a quantity carries its unit)
# Tests:    06-backend/tests/test_us_wrk_016_019_builder.py
# Impacts:  apps/work/selectors.py (`template_packs`, which resolves the
#           material part numbers against the tenant's own register) ·
#           apps/work/api.py (`GET /work/template-packs`) ·
#           07-frontend/src/features/work/TemplateBuilder.tsx (step 1)
# ───────────────────────────────────────────────────────
"""The three platform starter packs — what step 1 of the builder PREFILLS with.

WHAT A PACK IS, AND THE ONE THING IT IS NOT
-------------------------------------------
`Work-014` offers four tiles: *Meter exchange · 7 tasks · 3 parts · 3
readings*, *New connection*, *Inspection*, and *Start empty*. Picking one fills
steps 2 to 7 with rows a person then edits. `US-WRK-016` §1: *"It prefills
safety, tasks, materials, readings and help. Everything stays editable."*

⚠ **A PACK IS PLATFORM DATA AND IS NEVER STORED AS A LINK.** Nothing on a
template records which pack it came from, and editing a pack here changes no
template that was ever built from one. The 24 SEEDED STARTERS are the opposite
— rows a tenant owns (`BR-WRK-013`) — and confusing the two would make a
utility's edits vanish on the next provisioning sweep. `selectors.py` says the
same thing above `TEMPLATE_PACKS`; it is repeated here because this is the file
a lane edits.

⚠ **THE COUNTS ARE DERIVED FROM THE ROWS, NEVER TYPED.** Until
this file existed the three packs were counts alone, and `INSPECTION` said
**3 tasks** where `wireframes/Work-014.png`, `08-screen-layouts.md` §13.1 and
`US-WRK-016` §1 all draw **4**. A hand-typed count beside the rows it describes
is a second answer to one question, which is what the 2026-09-05 ruling
(*"Work is NOT an isolated module"*) calls the way a figure drifts. `summary()`
counts the list.

⚠ **MATERIALS ARE NAMED BY PART NUMBER, NOT BY ID, AND THE TENANT MAY NOT HOLD
THEM.** A pack is platform data and a part is the utility's own row, so the
pack can only say *MTR-E1P*. `selectors.template_packs()` resolves each number
against the tenant's register and DROPS the ones it does not find, so a utility
that has not entered a part gets a pack with one material fewer rather than a
500. `unresolved_parts` on the answer names what was dropped: an absence a
screen can explain beats an absence nobody can see (`DEF-CUS-3653`'s lesson).

⚠ **EVERY READING CARRIES A UNIT, INCLUDING THE ONE THE DRAWING DRAWS AS `—`.**
`wireframes/Work-016.png` draws *New meter serial* with a dash in the UNIT
column; `BR-WRK-015`, hard rule 3, the `NOT NULL` on `wot_readings` and
`US-WRK-014` TC-3 (green since wave D) all require one. The pack ships
`serial`, which is what is being recorded, and the divergence from the drawing
is stamped in `08-screen-layouts.md` and filed as a defect row in this lane's
hand-off (`scratchpad/lane-WE-defects.md`; the id is allocated by the lane that
writes the register, which this one may not). Dropping the
row instead would have made the *Meter exchange* pack **2 readings** where the
drawing, the story and `J60` all say three.

WHAT IS AUTHORED HERE AND WHAT IS QUOTED
----------------------------------------
The **Meter exchange** pack is quoted, row for row, from three places that
agree: `wireframes/Work-015.png` (the seven tasks and their minutes, summing to
45), `wireframes/Work-016.png` (the three readings) and `J60` step 7 (the three
safety lines, the three part numbers and the three help rows).

The **New connection** and **Inspection** packs are AUTHORED HERE. No wireframe,
story or journey states their contents — only their counts (*3 · 1 · 1* and
*4 · 0 · 2*), which this file meets exactly. The rows are a plain reading of the
job each pack names, and they are the utility's to edit on the first screen they
reach. Recorded as a judgment in the decision log rather than presented as
something a document said.
"""

from __future__ import annotations

from typing import Any

#: `wot_help.kind` — the three the `ck_wot_help_kind` CHECK admits.
HELP_DOCUMENT = "document"
HELP_PHONE = "phone"
HELP_NOTE = "note"

#: What a technician is shown on the job (`wot_details`, `Work-014`'s four
#: ticks). Every pack turns all four on: the drawing draws them ticked and a
#: pack that hid the account summary would be deciding for the utility.
_ALL_FOUR_SHOWN: dict[str, bool] = {
    "show_account_summary": True,
    "show_asset_card": True,
    "show_access_notes": True,
    "show_appointment": True,
    # FB-023 F4 — the fifth tick, on like the four.
    "show_balance_payments": True,
}


#: ⚠ **THE ROWS, AND ONLY THE ROWS.** Each pack's `bundle` uses the SAME key
#: names and the SAME row shapes `PUT /work/templates/{id}/{collection}` takes,
#: so the builder can post a pack's prefill back unchanged. A second shape here
#: would be a translation layer nobody asked for.
PACKS: tuple[dict[str, Any], ...] = (
    {
        "code": "METER_EXCHANGE",
        "name": "Meter exchange",
        "bundle": {
            "details": dict(_ALL_FOUR_SHOWN),
            # J60 step 7 — all three mandatory. A safety row is what BLOCKS the
            # task list on the phone (`Work-017`: *"Blocks the task list until
            # all three are ticked"*), so an optional one would be a note.
            "safety": [
                {"text": "Isolate at the service head before removal", "is_mandatory": True},
                {"text": "Check for backfeed / on-site generation", "is_mandatory": True},
                {"text": "Confined space check where pit-set", "is_mandatory": True},
            ],
            # wireframes/Work-015.png, in the drawn order and with the drawn
            # minutes: 3 + 2 + 10 + 15 + 2 + 5 + 8 = 45, which is the EST. cell
            # on Work-013 and the figure the dispatcher schedules against.
            "tasks": [
                {
                    "title": "Verify meter ID matches work order",
                    "est_minutes": 3,
                    "photo_required": False,
                    "is_mandatory": True,
                },
                {
                    "title": "Record final read on old meter",
                    "est_minutes": 2,
                    "photo_required": True,
                    "is_mandatory": True,
                },
                {
                    "title": "Isolate supply & remove old meter",
                    "est_minutes": 10,
                    "photo_required": False,
                    "is_mandatory": True,
                },
                {
                    "title": "Fit new meter & pressure test",
                    "est_minutes": 15,
                    "photo_required": False,
                    "is_mandatory": True,
                },
                {
                    "title": "Record opening read on new meter",
                    "est_minutes": 2,
                    "photo_required": True,
                    "is_mandatory": True,
                },
                {
                    "title": "Apply tamper seal & log seal number",
                    "est_minutes": 5,
                    "photo_required": False,
                    "is_mandatory": True,
                },
                {
                    "title": "Restore supply & confirm flow",
                    "est_minutes": 8,
                    "photo_required": False,
                    "is_mandatory": True,
                },
            ],
            # J60's fixture register. `planned_qty` is a STRING at four
            # decimals end to end (hard rule 2) and the unit comes from the
            # part rather than being typed again (hard rule 3).
            "materials": [
                {"part_no": "MTR-E1P", "planned_qty": "1.0000"},
                {"part_no": "SEAL-01", "planned_qty": "1.0000"},
                {"part_no": "GSKT-STD", "planned_qty": "1.0000"},
            ],
            # wireframes/Work-016.png. The first two POST to the meter's read
            # history when a supervisor accepts the job; the serial is recorded
            # only — which is the switch that box on the drawing explains.
            "readings": [
                {
                    "prompt": "Final read on old meter",
                    "unit_of_measure": "kWh",
                    "min": "0",
                    "max": "99999",
                    "required": True,
                    "photo_required": True,
                    "posts_as_meter_read": True,
                },
                {
                    "prompt": "Opening read on new meter",
                    "unit_of_measure": "kWh",
                    "min": "0",
                    "max": "999",
                    "required": True,
                    "photo_required": True,
                    "posts_as_meter_read": True,
                },
                {
                    # ⚠ `serial` where Work-016 draws `—`. See the module
                    # docstring: the column is NOT NULL and a signed test
                    # refuses a blank one.
                    "prompt": "New meter serial",
                    "unit_of_measure": "serial",
                    "min": None,
                    "max": None,
                    "required": True,
                    "photo_required": False,
                    "posts_as_meter_read": False,
                },
            ],
            # J60 step 7's three, with the PHONE rows carrying no number: a
            # supervisor's extension is the utility's own fact and a platform
            # pack that invented one would put a wrong number on a phone in the
            # field. The label is the prefill; `ref` is what the clerk fills in.
            "help": [
                {"kind": HELP_DOCUMENT, "label": "Meter exchange SOP", "ref": None},
                {"kind": HELP_PHONE, "label": "Supervisor", "ref": None},
                {"kind": HELP_PHONE, "label": "AMI activation hotline", "ref": None},
            ],
        },
    },
    {
        "code": "NEW_CONNECTION",
        "name": "New connection",
        "bundle": {
            "details": dict(_ALL_FOUR_SHOWN),
            "safety": [
                {"text": "Confirm the main is isolated before you cut in", "is_mandatory": True},
                {"text": "Check for buried services before you dig", "is_mandatory": True},
            ],
            "tasks": [
                {
                    "title": "Confirm the connection point and the route",
                    "est_minutes": 10,
                    "photo_required": False,
                    "is_mandatory": True,
                },
                {
                    "title": "Lay the service and make the connection",
                    "est_minutes": 45,
                    "photo_required": True,
                    "is_mandatory": True,
                },
                {
                    "title": "Set the meter and record the opening read",
                    "est_minutes": 15,
                    "photo_required": True,
                    "is_mandatory": True,
                },
            ],
            "materials": [{"part_no": "MTR-W58", "planned_qty": "1.0000"}],
            "readings": [
                {
                    # ⚠ THE UNIT IS THE ELECTRIC DEFAULT AND IS MEANT TO BE
                    # EDITED. A pack does not know the service — the clerk
                    # picks that on step 1 — and a blank unit is refused
                    # (`BR-WRK-015`), so the pack names one and step 5 is where
                    # a water utility changes it.
                    "prompt": "Opening read on the new meter",
                    "unit_of_measure": "kWh",
                    "min": "0",
                    "max": "99999",
                    "required": True,
                    "photo_required": True,
                    "posts_as_meter_read": True,
                },
            ],
            "help": [
                {"kind": HELP_DOCUMENT, "label": "New connection standard", "ref": None},
                {"kind": HELP_PHONE, "label": "Supervisor", "ref": None},
            ],
        },
    },
    {
        "code": "INSPECTION",
        "name": "Inspection",
        "bundle": {
            "details": dict(_ALL_FOUR_SHOWN),
            "safety": [
                {"text": "Check the site is safe to enter", "is_mandatory": True},
            ],
            "tasks": [
                {
                    "title": "Confirm the address and the equipment on site",
                    "est_minutes": 5,
                    "photo_required": False,
                    "is_mandatory": True,
                },
                {
                    "title": "Inspect the installation against the standard",
                    "est_minutes": 20,
                    "photo_required": False,
                    "is_mandatory": True,
                },
                {
                    "title": "Photograph anything that is not right",
                    "est_minutes": 5,
                    "photo_required": True,
                    "is_mandatory": False,
                },
                {
                    "title": "Record the outcome and tell the customer",
                    "est_minutes": 5,
                    "photo_required": False,
                    "is_mandatory": True,
                },
            ],
            "materials": [],
            "readings": [
                {
                    "prompt": "Pressure at the test point",
                    "unit_of_measure": "psi",
                    "min": "0",
                    "max": "150",
                    "required": True,
                    "photo_required": True,
                    # An inspection reading is EVIDENCE, not consumption: it
                    # must not land in the meter's read history.
                    "posts_as_meter_read": False,
                },
                {
                    "prompt": "Meter register read at inspection",
                    "unit_of_measure": "kWh",
                    "min": "0",
                    "max": "99999",
                    "required": False,
                    "photo_required": False,
                    "posts_as_meter_read": False,
                },
            ],
            "help": [
                {"kind": HELP_DOCUMENT, "label": "Inspection checklist", "ref": None},
            ],
        },
    },
)

#: Every pack code, for a caller that has to validate one.
PACK_CODES: tuple[str, ...] = tuple(pack["code"] for pack in PACKS)


def summary(pack: dict[str, Any]) -> dict[str, int]:
    """`Work-014`'s one-line count — *7 tasks · 3 parts · 3 readings*.

    ⚠ **COUNTED, NEVER TYPED.** See the module docstring: the typed form said
    *Inspection · 3 tasks* against three documents that draw four.
    """
    bundle = pack["bundle"]
    return {
        "tasks": len(bundle["tasks"]),
        "parts": len(bundle["materials"]),
        "readings": len(bundle["readings"]),
        "safety": len(bundle["safety"]),
        "help": len(bundle["help"]),
    }


def est_minutes(pack: dict[str, Any]) -> int:
    """The pack's total estimate — the sum of its tasks, which is what the
    dispatcher schedules against and what `Work-013`'s EST. column shows.

    45 for *Meter exchange*, and the drawing's own `TASKS — 7 STEPS · 45 MIN
    TOTAL` is the same arithmetic done by hand.
    """
    return sum(int(task["est_minutes"] or 0) for task in pack["bundle"]["tasks"])


def by_code(code: Any) -> dict[str, Any] | None:
    """One pack, or None. A caller that gets None has been handed a code no
    platform pack answers to, which is a refusal and not an empty pack."""
    wanted = str(code or "").strip().upper()
    for pack in PACKS:
        if pack["code"] == wanted:
            return pack
    return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-016@2b08ba9f (EP-WRK-03) · 10-execution-plan.md wave E task E1 · 08-screen-layouts.md §13.1 · wireframes/Work-014.png, Work-015.png, Work-016.png · J60 steps 6–7
# generated: 2026-09-05 by the CR-070 wave E build lane
# checklist: A✔ B✔ C✔ D✔ E✔(TemplateBuilder step 1 renders these) F✔ G✔ H=n/a(platform constants; no 🔒 path)
# gates: G78 (no foreign model is named here at all) · pytest tests/test_us_wrk_016_019_builder.py
# exceptions: E1 the New connection and Inspection packs' ROWS are authored by this lane — no document states them, only their counts, which are met exactly (decision log 2026-09-05) · E1 the third Meter-exchange reading carries `serial` where Work-016 draws `—` (defect row in scratchpad/lane-WE-defects.md, id not allocated by this lane)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
