# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 (a work order TYPE catalogue) · US-WRK-008 (priorities,
#           each with its SLA hours) · US-WRK-009 (skills, safety kits, parts
#           categories — the three parked Settings cards) · US-WRK-010 (the
#           parts register, and NO stock level).  Screens: Work-018, Work-025
# Rules:    BR-WRK-017 (types are a catalogue, not free text) · BR-WRK-018 (a
#           priority carries SLA hours; rank orders the list) · BR-WRK-019
#           (the parts register is part no · name · category · unit · unit
#           cost — and NO stock level, NO reorder point) · BR-WRK-001/002
#           (Work owns these six tables and writes nobody else's) ·
#           CLAUDE.md hard rule 1 (tenant-scoped; RLS FORCE in work/0002) ·
#           hard rule 2 (money stored 4 dp, displayed 2) · hard rule 3 (a
#           quantity carries its unit — `unit_of_measure`, `sla_hours`)
# Tests:    06-backend/tests/test_us_wrk_007_types.py ·
#           tests/test_us_wrk_008_priorities.py · tests/test_us_wrk_009_lookups.py
#           · tests/test_us_wrk_010_parts.py · tests/test_us_wrk_rls_pg.py
# Impacts:  apps/work/migrations/0001_initial.py + 0002_rls_force.py ·
#           apps/work/lookups.py (the five reference-data handlers) ·
#           apps/tenancy/services.py (LOOKUP_LISTS + SEED_LIST_OWNERS)
# ───────────────────────────────────────────────────────
"""The Work module's own tables — six of them, and every one tenant-scoped.

WHY THIS FILE EXISTS AT ALL, AND WHAT IS NOT IN IT
--------------------------------------------------
`apps/work/` owned no table until wave C: the six tables Work will eventually
own (`connections`, `connection_services`, `work_orders`,
`work_order_templates`, `connection_todos`, `service_characteristics`) live in
`apps/metering/connections.py` and **still did until T-43** — ⚠ AMENDED
2026-10-21 (CR-187-BRC10 T-43): they now live in `apps/work/connection_models.py`
and are imported at the foot of this file; `work/0046` took them into Work's
migration state and `metering/0078` released them, neither touching a table.
The paragraph below is the record of why wave C did not move them. Where they end up is
`04-docs/05-modules/16-work/03-field-map.md` §4, which lists three ways to
honour the ruling and records the choice as PENDING the blueprint's §16 — a
section this repo has never been able to read. **Wave C does not decide it**
and deliberately does not move them: a migration-graph move of six tables with
two migrations, an audit trail and a test suite is not a thing to do on the
side of a Settings wave, and nothing in wave C needs it. The two columns wave
C adds to `work_order_templates` are therefore METERING's migration
(`metering/0045`), not this app's.

What IS here is the reference data — the six lists a utility fills in before
it dispatches anything. They are new, nobody else owns them, and they are
Work's from birth.

⚠ NO STOCK. `parts` carries **no `on_hand`, no `reorder_at`, no `location`**.
That is not an omission and not a phase boundary: `WM-07` and `WM-22` say *"No
stock levels, no reorder points"*, `CR-028` §11-D5 parked the parts-stock
table when Assets was ruled into scope, and the wireframe `Work-025` that
draws *On hand 184 · Reorder at 60* contradicts its own card — filed as
`DEF-WRK-3550`. Whether such a table may exist at all is `OQ-WRK-1490`, OPEN.
`apps.work.services.stock_position()` raises naming it, `GET /work/parts`
carries no such key, and `test_us_wrk_010_parts.py` asserts their absence BY
NAME so a lane cannot add one quietly.

WHAT EACH TABLE'S EXTRA COLUMN IS FOR
-------------------------------------
Every list here is a `code · name · active · is_system` lookup in the shape
`apps/assets/lookups.py` already established, plus at most a few columns of
its own. The Reference-data framework (`BR-SHL-035`) renders code, name and
ONE detail column per card, so each table's remaining columns are seeded and
read by the wave that needs them:

  * `work_order_types.est_duration` / `.customer_present` — read by the New
    work order wizard (wave G) and by the type picker; seeded here.
  * `work_order_types.default_template` — wave D publishes the first template;
    the column is NULL until then, which is what `US-WRK-007` §5 says.
  * `work_priorities.rank` — the list order (`BR-WRK-018`). Unique per tenant,
    so a tenant adding a fifth priority gets `max + 1` rather than a collision.
  * `work_priorities.colour` — a design TOKEN, never a hex a clerk types
    (`US-WRK-008` §5).
  * `work_safety_kits.items` — the kit's contents, shown on the template
    builder's safety step (wave E). Edited on the card as one comma-separated
    line, which is `items_text` in the serializer and this array underneath.
"""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower

from core.dbfields import uuid7_pk

#: `work_priorities.colour` — the four design tokens the drawings use, and
#: nothing else. A hex string typed by a clerk would survive a redesign as a
#: colour nobody can find; a token moves with `tokens.css`.
PRIORITY_COLOURS = ("danger", "warning", "info", "neutral")

#: `CR-187-BRC10` (PO answer 9) — the push kinds an ASSIGNMENT may ring with,
#: least to most urgent. A subset of `push.PUSH_KINDS`: a schedule change and a
#: dispatch message are not what an assignment is. Declared here rather than
#: imported from `push.py` because a model module must not import a job body.
PRIORITY_PUSH_KINDS: tuple[str, ...] = ("new_job", "urgent_assignment", "emergency")

#: The four seeded priorities — `BR-WRK-018` names them and `US-WRK-008` §4
#: gives the hours: Urgent 4 h · High 8 h · Normal 72 h · Low 168 h.
SEED_PRIORITIES: tuple[dict[str, object], ...] = (
    # `push_kind` (CR-187-BRC10, PO answer 9 of 2026-10-21): the most urgent
    # priority rings as an EMERGENCY, the next as an URGENT ASSIGNMENT, the
    # rest as an ordinary new job. A starting point the utility edits.
    {
        "code": "URGENT",
        "name": "Urgent",
        "rank": 1,
        "sla_hours": 4,
        "colour": "danger",
        "push_kind": "emergency",
    },
    {
        "code": "HIGH",
        "name": "High",
        "rank": 2,
        "sla_hours": 8,
        "colour": "warning",
        "push_kind": "urgent_assignment",
    },
    {"code": "NORMAL", "name": "Normal", "rank": 3, "sla_hours": 72, "colour": "info"},
    {"code": "LOW", "name": "Low", "rank": 4, "sla_hours": 168, "colour": "neutral"},
)

#: `CR-168-BRC10` P0.3/P0.4 (judgment J1) — the five reasons a job comes off the
#: run, seeded per tenant and edited on Settings like every other Work list. A
#: LOOKUP and never a CHECK list: a utility that needs *Waiting for a permit*
#: adds a row; it does not wait for a migration. `work/0028` seeds the tenants
#: that already exist from this same constant.
SEED_HOLD_REASONS: tuple[dict[str, object], ...] = (
    {"code": "WEATHER", "name": "Weather", "rank": 1},
    {"code": "WAITING_PART", "name": "Waiting for a part", "rank": 2},
    {"code": "CUSTOMER_NOT_HOME", "name": "Customer not home", "rank": 3},
    {"code": "ACCESS_REFUSED", "name": "Access refused", "rank": 4},
    {"code": "OTHER", "name": "Other", "rank": 5},
)

#: The EIGHT job types this product seeded until 2026-09-07, kept as a NAMED
#: constant because two things still need to read them: `work/0022`, which
#: DEACTIVATES them on every tenant that already has them, and the test that
#: asserts it did. The Product Owner rejected them in one sentence — *"this is
#: not correct - you will ahve to think from all Utilty services point of
#: view"* — and supplied the replacement themselves (decision log 2026-09-07).
#:
#: ⚠ **RETIRED MEANS DEACTIVATED, NEVER DELETED.** `BR-TEN-036` already rules
#: that a seeded row is deactivatable and never deletable, and here the rule
#: earns its keep twice over: `work_orders.type_id` points at these rows on a
#: live tenant, so deleting one would either fail on the FK or orphan a job
#: somebody did. A deactivated row keeps every order that names it, disappears
#: from every picker, and can be switched back on by a utility that wants it.
RETIRED_SEED_TYPES: tuple[tuple[str, str], ...] = (
    ("RECONNECT", "Reconnect after payment"),
    ("MAIN_REPAIR", "Main repair"),
    ("DISCONNECT_NONPAY", "Disconnect \u2014 non-payment"),
    ("LEAK_INVESTIGATION", "Leak investigation"),
    ("METER_EXCHANGE", "Meter exchange"),
    ("BACKFLOW_INSPECTION", "Backflow inspection"),
    ("READ_VERIFICATION", "Read verification"),
    ("MOVE_IN_ACTIVATION", "Move-in activation"),
)

#: **THE PRODUCT OWNER'S OWN NINE TYPES** (2026-09-07, verbatim preface: *"This
#: are the work order types and subtypes"*). A row with NO parent IS a type.
#:
#: They are the COMMON SPINE: every tenant gets all nine whatever it sells,
#: because the eleven services contribute SUB-types beneath them and no service
#: brings a tenth type of its own (*"we are good with these"*, same day).
#: **THE FOUR SUB-TYPES THAT DELIBERATELY BEAT THEIR PARENT HEADING.**
#:
#: ⚠ **THIS IS THE ONE THING IN THE PRIORITY DEFAULTS THAT IS NOT ARITHMETIC,
#: AND IT ARRIVES AT A CUSTOMER'S HOUSE.** A sub-type with no default of its own
#: is raised at its PARENT's — `_resolve_priority` reads `type_ref.
#: default_priority` and there is no third fallback. So *Gas leak call-out*,
#: which hangs under *Consumer Complaint*, would inherit **8 hours**. Eight
#: hours is a defensible number for a complaint about a bill and it is the
#: wrong number for a gas leak, and it would arrive there **by accident** —
#: nobody would have chosen it, and nothing on any screen would show that a
#: choice had been skipped.
#:
#: The same is true of *Odour complaint* (the other way a gas leak is reported),
#: *No Water Supply* and *Outage report* — the last two being a customer with no
#: service at all rather than a customer with a question about one.
#:
#: **So these four carry `URGENT` explicitly, and this note exists so that a
#: lane tidying "redundant" keys out of `SEED_TYPES` meets the reason before
#: the key.** Removing one does not break a test that mentions gas; it silently
#: moves a promised response time from four hours to eight.
URGENT_BEATS_ITS_PARENT: tuple[str, ...] = (
    "GAS_LEAK_CALLOUT",
    "GAS_ODOUR",
    "NO_WATER_SUPPLY",
    "ELEC_OUTAGE",
)

#: **THE DEFAULT PRIORITY EACH OF THE NINE TYPES IS SEEDED AT** — and every one
#: of these is a RESPONSE TIME, because `work_priorities.sla_hours` is what
#: `due_at` is stamped from at the moment an order is raised (`BR-WRK-018`).
#:
#: ⚠ **THESE ARE OUR FIGURES, NOT THE PRODUCT OWNER'S, AND THE DIFFERENCE IS
#: RECORDED RATHER THAN BLURRED** (`OQ-WRK-1765`, closed 2026-09-07 as a
#: JUDGMENT). The PO was shown these four bands with the hours each implies,
#: did not dispute the values, and answered a different question — *"you keep
#: them configurable in settings - user can change the timings"* — then said
#: *"please complete all the changes /bug we discussed - dont wait for me"*.
#: **That is a delegation, not a ratification.** What makes it safe to seed
#: them anyway is the PO's own ruling: the response time is a per-tenant
#: SETTING (`sla_hours`, editable on Settings → Reference data → Work
#: priorities since `work/0001`), so a seeded default is **a starting point a
#: utility changes in one word**, not a promise this platform makes on their
#: behalf. Every row here is `is_system` and every one is editable.
#:
#: Urgent 4 h · High 8 h · Normal 72 h (3 days) · Low 168 h (7 days) — the
#: figures in `SEED_PRIORITIES`, which a tenant may also change.
SEED_TYPE_SPINE: tuple[dict[str, object], ...] = (
    {"code": "COMPLAINT", "name": "Consumer Complaint", "default_priority": "HIGH"},
    {"code": "METER_MAINT", "name": "Meter Maintenance", "default_priority": "NORMAL"},
    {"code": "PREVENTIVE", "name": "Preventive Maintenance", "default_priority": "LOW"},
    {"code": "CONNECTION", "name": "Connection", "default_priority": "NORMAL"},
    {"code": "CORRECTIVE", "name": "Corrective Maintenance", "default_priority": "HIGH"},
    {"code": "INFRA_DEV", "name": "Infrastructure Development", "default_priority": "LOW"},
    {"code": "WATER_QUALITY", "name": "Water Quality Monitoring", "default_priority": "HIGH"},
    {"code": "CONSUMER_SVC", "name": "Consumer Services", "default_priority": "NORMAL"},
    {"code": "READING", "name": "Reading", "default_priority": "LOW"},
)

#: **THE EIGHTEEN SUB-TYPES THE PRODUCT OWNER LISTED — AND THEY ARE WATER'S.**
#: The PO's own list, in the PO's own grouping. A row WITH a parent IS a
#: sub-type (`BR-WRK-058`).
#:
#: ⚠ **THEY CARRIED NO SERVICE TAG UNTIL 2026-09-07, AND THE PO CLOSED THAT THE
#: SAME DAY.** The list was seeded exactly as given — every tenant received all
#: eighteen whatever it sold — because *Low Pressure* and *Leak Repairs* are as
#: true of gas as of water while *Water Truck Services* plainly is not, and
#: deciding which is which is a judgment about a utility's operations rather
#: than about this software. **That judgment was put to the PO rather than made
#: here, and their answer was *"gas onlyutility carry only gas meters"*** — a
#: gas-only utility must not receive *No Water Supply* and *Water Truck
#: Services*. So a sub-type follows its service, the way gas's four always did,
#: and these eighteen are water's.
#:
#: ⚠ **AND ELEVEN OF THE EIGHTEEN CAME BACK OUT OF WATER'S LIST THE SAME
#: EVENING (2026-09-07, `DEF-WRK-4512`), BECAUSE THE PO RULED THEM COMMON TO
#: EVERY UTILITY.** Asked whether *Billing Issues*, *Meter Change*, *Re-read*,
#: *Connection* and the rest belong to everybody, they answered: *"yes that is
#: correct; but we will ahve to see which Utility service they do"*. So the
#: eleven service-neutral rows below carry **no `service` tag** and every
#: utility receives them; the **seven genuinely water-shaped ones keep it** —
#: *Low Pressure* · *No Water Supply* · *Water Pressure* · *Leak Repairs* ·
#: *Main Extension* · *Water Truck Services* · *Electrical Line*.
#:
#: **WORKED: a gas-only utility goes from `9 types / 4 sub-types` to `9 / 15`**,
#: and water-only stays at `9 / 18` because the eleven were always in its list.
#:
#: ⚠ **THE SECOND HALF OF THAT SENTENCE IS STILL OPEN AND IS NOT BUILT HERE.**
#: *"which Utility service they do"* is a narrower question than *"which
#: utility"*: **`Meter Change`, `Meter Dispose`, `Meter Replacement` and
#: `Re-read` have no subject on a service with no meter** — a trash cart and a
#: fire line are not re-read — so those four may yet be scoped to the metered
#: services (`core/sample_fixture.METERED_ESTATE_SERVICES`: water, electric,
#: gas, thermal/heat). **That per-service table is `OQ-WRK-1764`, OPEN**, and
#: it is with the PO. Until it is answered these eleven are common, which is
#: what was ruled; the refinement would take four of them back OFF some
#: services and is exactly the re-carving no lane may do on its own judgment.
SEED_BASE_SUB_TYPES: tuple[dict[str, object], ...] = (
    {"code": "LOW_PRESSURE", "name": "Low Pressure",
     "parent_code": "COMPLAINT", "service": "water"},
    # ⚠ BEATS ITS PARENT — see `URGENT_BEATS_ITS_PARENT` below.
    {"code": "NO_WATER_SUPPLY", "name": "No Water Supply",
     "parent_code": "COMPLAINT", "service": "water", "default_priority": "URGENT"},
    {"code": "BILLING_ISSUES", "name": "Billing Issues",
     "parent_code": "COMPLAINT"},
    {"code": "METER_CHANGE", "name": "Meter Change",
     "parent_code": "METER_MAINT"},
    {"code": "METER_DISPOSE", "name": "Meter Dispose",
     "parent_code": "METER_MAINT"},
    {"code": "ROUTINE_INSPECTION", "name": "Routine Inspection",
     "parent_code": "PREVENTIVE"},
    {"code": "METER_REPLACEMENT", "name": "Meter Replacement",
     "parent_code": "PREVENTIVE"},
    {"code": "NEW_CONN_SURVEY", "name": "Survey for New Connection",
     "parent_code": "CONNECTION"},
    {"code": "RESIDENTIAL_CONN", "name": "Residential Connection",
     "parent_code": "CONNECTION"},
    {"code": "COMMERCIAL_CONN", "name": "Commercial Connection",
     "parent_code": "CONNECTION"},
    {"code": "INDUSTRIAL_CONN", "name": "Industrial Connection",
     "parent_code": "CONNECTION"},
    {"code": "LEAK_REPAIRS", "name": "Leak Repairs",
     "parent_code": "CORRECTIVE", "service": "water"},
    {"code": "ELECTRICAL_LINE", "name": "Electrical Line",
     "parent_code": "CORRECTIVE", "service": "water"},
    {"code": "MAIN_EXTENSION", "name": "Main Extension",
     "parent_code": "INFRA_DEV", "service": "water"},
    {"code": "WATER_PRESSURE", "name": "Water Pressure",
     "parent_code": "WATER_QUALITY", "service": "water"},
    {"code": "DISCONNECT_RECONNECT", "name": "Disconnection/Reconnection",
     "parent_code": "CONSUMER_SVC"},
    {"code": "WATER_TRUCK", "name": "Water Truck Services",
     "parent_code": "CONSUMER_SVC", "service": "water"},
    {"code": "RE_READ", "name": "Re-read",
     "parent_code": "READING"},
)

#: **THE TWENTY-FOUR PER-SERVICE SUB-TYPES** (PO 2026-09-07, *"we are good with
#: these"*), each tagged with the service that brings it and hung under one of
#: the PO's own nine types. **No new TYPES** — that is what makes the
#: spine-plus-service reading work.
#:
#: ⚠ **`service` IS READ BY THE SEEDER AND IS NOT A COLUMN**, and the
#: difference is the whole ruling (*"this is also correct"*): a utility that
#: picks water and gas gets the eighteen plus the four gas ones; a water-only
#: utility gets exactly the eighteen. The row that lands is an ordinary
#: tenant row with no service tag on it — `service_size_classes` takes the
#: OPPOSITE posture on purpose (it tags every size for every tenant and lets
#: the pickers filter), and the two are different because the PO ruled
#: different things about them.
#:
#: ⚠ **WATER APPEARS IN `SEED_BASE_SUB_TYPES` AND NOT HERE**, which is a
#: grouping and not a rule: since 2026-09-07 every sub-type in this module
#: names a service, and water's eighteen are simply the ones the PO listed
#: first. A reader counting "per-service sub-types" must count BOTH tuples —
#: `SEED_TYPES` below is the only total that is safe to quote.
SEED_SERVICE_SUB_TYPES: tuple[dict[str, object], ...] = (
    # Gas — four
    # ⚠ BEATS ITS PARENT — see `URGENT_BEATS_ITS_PARENT` below.
    {"code": "GAS_LEAK_CALLOUT", "name": "Gas leak call-out",
     "parent_code": "COMPLAINT", "service": "gas", "default_priority": "URGENT"},
    {"code": "GAS_ODOUR", "name": "Odour complaint",
     "parent_code": "COMPLAINT", "service": "gas", "default_priority": "URGENT"},
    {"code": "GAS_PRESSURE_TEST", "name": "Pressure test",
     "parent_code": "CORRECTIVE", "service": "gas"},
    {"code": "GAS_LINE_PURGE", "name": "Line purge",
     "parent_code": "CORRECTIVE", "service": "gas"},
    # Electric — three
    {"code": "ELEC_OUTAGE", "name": "Outage report",
     "parent_code": "COMPLAINT", "service": "electric", "default_priority": "URGENT"},
    {"code": "ELEC_VOLTAGE", "name": "Voltage complaint",
     "parent_code": "COMPLAINT", "service": "electric"},
    {"code": "ELEC_TRANSFORMER", "name": "Transformer fault",
     "parent_code": "CORRECTIVE", "service": "electric"},
    # Trash — three
    {"code": "TRASH_MISSED", "name": "Missed collection",
     "parent_code": "COMPLAINT", "service": "trash"},
    {"code": "TRASH_DAMAGED_CART", "name": "Damaged cart",
     "parent_code": "COMPLAINT", "service": "trash"},
    {"code": "TRASH_CONTAINER_SWAP", "name": "Container swap",
     "parent_code": "CONSUMER_SVC", "service": "trash"},
    # Storm water — three
    {"code": "STORM_BLOCKED_INLET", "name": "Blocked inlet",
     "parent_code": "COMPLAINT", "service": "storm_water"},
    {"code": "STORM_FLOODING", "name": "Flooding",
     "parent_code": "COMPLAINT", "service": "storm_water"},
    {"code": "STORM_INLET_CLEARING", "name": "Inlet clearing",
     "parent_code": "PREVENTIVE", "service": "storm_water"},
    # Solar — two
    {"code": "SOLAR_INVERTER_FAULT", "name": "Inverter fault",
     "parent_code": "CORRECTIVE", "service": "solar"},
    {"code": "SOLAR_EXPORT_CHECK", "name": "Export config check",
     "parent_code": "PREVENTIVE", "service": "solar"},
    # Battery — one
    {"code": "BATTERY_INSPECTION", "name": "Battery inspection",
     "parent_code": "PREVENTIVE", "service": "battery"},
    # Broadband — three
    {"code": "BB_NO_SERVICE", "name": "No service",
     "parent_code": "COMPLAINT", "service": "broadband"},
    {"code": "BB_SLOW_SPEED", "name": "Slow speed",
     "parent_code": "COMPLAINT", "service": "broadband"},
    {"code": "BB_DROP_REPAIR", "name": "Drop repair",
     "parent_code": "CORRECTIVE", "service": "broadband"},
    # Thermal/Heat — one. The service CODE is `thermal_heat`, never the prose
    # name `thermal` (DEF-972): a tag that does not match `SERVICE_SEED` seeds
    # nothing and reports nothing, which is the silence this list must not have.
    {"code": "THERMAL_HX_SERVICE", "name": "Heat exchanger service",
     "parent_code": "PREVENTIVE", "service": "thermal_heat"},
    # Fire — two
    {"code": "FIRE_FLOW_TEST", "name": "Flow test",
     "parent_code": "PREVENTIVE", "service": "fire"},
    {"code": "FIRE_BACKFLOW_TEST", "name": "Backflow test",
     "parent_code": "PREVENTIVE", "service": "fire"},
    # Sewer — two
    {"code": "SEWER_BLOCKAGE", "name": "Blockage",
     "parent_code": "COMPLAINT", "service": "sewer"},
    {"code": "SEWER_BACKUP", "name": "Backup",
     "parent_code": "COMPLAINT", "service": "sewer"},
)

#: What `apps.work.services.seed_reference_list` offers for `work_order_types`:
#: the spine, then the base sub-types, then the per-service ones. **The ORDER
#: is not cosmetic** — the seeder makes two passes and creates parents before
#: children, so a list that put a sub-type first would still work; keeping the
#: three groups in this order is what lets a reader check the counts by eye.
#:
#: **Nine + eighteen + twenty-four = fifty-one**, of which a tenant receives the
#: nine — the common spine, always — and ONLY the sub-types of the services it
#: sells. Water-only **9 + 18**; water and gas **9 + 22**; electric and water
#: **9 + 21**; **gas-only 9 + 4**; all eleven services **9 + 42**.
SEED_TYPES: tuple[dict[str, object], ...] = (
    *SEED_TYPE_SPINE,
    *SEED_BASE_SUB_TYPES,
    *SEED_SERVICE_SUB_TYPES,
)

#: `US-WRK-009` TC-2 — the card's own sample copy becomes its seeded rows.
SEED_SKILLS: tuple[dict[str, str], ...] = (
    {"code": "WATER_I", "name": "Water I"},
    {"code": "WATER_II", "name": "Water II"},
    {"code": "WATER_III", "name": "Water III"},
    {"code": "ELECTRIC_I", "name": "Electric I"},
    {"code": "ELECTRIC_II", "name": "Electric II"},
    {"code": "METER_I", "name": "Meter I"},
    {"code": "READS", "name": "Reads"},
    {"code": "EXCAVATION", "name": "Excavation"},
)

#: `US-WRK-009` TC-2. `items` is the kit's contents — the list the template
#: builder's safety step reads (wave E) and the card edits as one line.
SEED_SAFETY_KITS: tuple[dict[str, object], ...] = (
    {"code": "BASIC_PPE", "name": "Basic PPE",
     "items": ["Hard hat", "Safety glasses", "Gloves", "Hi-vis vest"]},
    {"code": "LOTO", "name": "Lockout / tagout",
     "items": ["Lock", "Tag", "Voltage tester"]},
    {"code": "CONFINED_SPACE", "name": "Confined space",
     "items": ["Harness", "Gas monitor", "Tripod", "Retrieval line"]},
    {"code": "TRAFFIC_CONTROL", "name": "Traffic control",
     "items": ["Cones", "Signs", "Flagging kit"]},
)

#: `US-WRK-009` TC-2. ⚠ The card's sample copy also names *locations Yard ·
#: Van 3/8/12*; **a location is a STOCK concept and is not seeded here**
#: (`BR-WRK-019`, `OQ-WRK-1490`).
SEED_PART_CATEGORIES: tuple[dict[str, str], ...] = (
    {"code": "METERS", "name": "Meters"},
    {"code": "CONSUMABLES", "name": "Consumables"},
    {"code": "FITTINGS", "name": "Fittings"},
    {"code": "TEST_EQUIPMENT", "name": "Test equipment"},
)


class WorkOrderType(models.Model):
    """`work_order_types` — the job types this utility does, written down once.

    `work_orders.type` is free TEXT today and *"deliberately not an enum"*, so
    two clerks can type *Meter set* and *Meter Set* and nothing groups them.
    This is the catalogue `BR-WRK-017` asks for; `work_orders.type_id` points
    here (added beside the free-text column, whose retirement is §16's to
    state — `US-WRK-007` §1).

    ── TWO LEVELS (`BR-WRK-058`, PO ruling 2026-09-07) ──────────────────────
    ⚠ **THIS LIST WAS FLAT UNTIL 2026-09-07 AND THE CHANGE IS A SCHEMA CHANGE,
    NOT A FIXTURE EDIT.** The Product Owner rejected the eight flat rows this
    table shipped with — *"this is not correct - you will ahve to think from
    all Utilty services point of view"* — and supplied the replacement
    themselves: **nine types and eighteen sub-types**, then twenty-four more
    hung under the same nine, one group per utility service.

    **A row with no parent IS a type. A row with a parent IS a sub-type.**
    One list, one column, exactly two levels — which is `tenancy.Area`'s shape
    (`BR-MET-066b`) followed deliberately rather than a second posture
    invented: `lookups.py` refuses a grandparent and refuses a self-reference,
    and **depth is enforced in the SERVICE and NOT by a database constraint**,
    because SQL cannot express *"a parent must itself have no parent"* without
    a trigger and a trigger would be a second place the rule lives.

    ⚠ **`service` IS NOT A COLUMN HERE, AND THAT IS THE RULING RATHER THAN AN
    OMISSION.** What depends on the tenant's services is WHICH ROWS ARRIVE, not
    what a row then is: *"a utility that picks water and gas gets the eighteen
    plus the four gas ones; a water-only utility gets exactly the eighteen and
    nothing else"*. The tag therefore lives on the seed constants and is read
    once, at seeding time. A row a tenant owns is an ordinary row they may
    rename, retire or re-parent. `MeterSizeClass.service` takes the OPPOSITE
    posture — every size tagged for every tenant, filtered at the picker —
    because the PO ruled a different thing about that list; the two are not an
    inconsistency to tidy.

    ⚠ **EVERY SUB-TYPE NAMES A SERVICE SINCE 2026-09-07, THE EIGHTEEN
    INCLUDED.** They were seeded to everybody until that day, so a gas-only
    utility received *No Water Supply* and *Water Truck Services*. That was
    raised with the PO rather than corrected on a lane's judgment, and they
    ruled: *"gas onlyutility carry only gas meters"*. The eighteen are water's,
    and a gas-only utility gets the nine types and gas's four. **The nine TYPES
    are never scoped** — they are the common spine and every utility has all of
    them.

    ⚠ **AND A DEFAULT PRIORITY IS NOW RULED IN, BUT IS NOT SEEDED YET.** The PO
    answered *"Yes"* to whether a type carries one on 2026-09-07. *"Yes"*
    answers WHETHER and not WHICH: naming a gas leak call-out Urgent is a
    response time promised to a customer, so the proposed value for each type
    goes to the PO in plain English with the hours it implies before any of it
    is seeded (`OQ-WRK-1765`). Until then `default_priority` stays NULL on
    every seeded row and a clerk sets it on the card.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    #: `BR-WRK-058` — NULL = a top-level TYPE; set = a SUB-TYPE of that row.
    #: PROTECT, not CASCADE, for `Area.parent`'s reason: deleting a type that
    #: has sub-types must refuse and say so, never silently take four children
    #: with it. `lookups.WorkOrderTypeLookupHandler.delete` refuses first and
    #: names the count, so the FK is the backstop rather than the message.
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="parent_id",
        related_name="sub_types",
    )
    default_priority = models.ForeignKey(
        "work.WorkPriority",
        on_delete=models.PROTECT,
        db_column="default_priority_id",
        null=True,
        blank=True,
        related_name="default_for_types",
    )
    # NULL until wave D publishes the first template. A cross-module FK by
    # accident of geography rather than of design: `work_order_templates` is a
    # table this module will own (03-field-map.md §4), and it is in the
    # reviewed interface set either way (B2 §2).
    default_template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.PROTECT,
        db_column="default_template_id",
        null=True,
        blank=True,
        related_name="default_for_types",
    )
    # An interval carries its own unit (hard rule 3) — the same reasoning that
    # makes `WorkOrderTemplate.est_duration` a DurationField rather than
    # `est_minutes`.
    est_duration = models.DurationField(null=True, blank=True)
    customer_present = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    #: `CR-168-BRC10` P5.10 (`work/0028`) — a type's OWN promise, in whole
    #: hours, overriding its priority's. NULL is *use the priority's*, which is
    #: every type until a supervisor sets one; never 0, which would be a promise
    #: that every job is late the moment it is raised.
    sla_hours = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_types"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_work_order_types_tenant_code_ci"
            ),
        ]


class WorkPriority(models.Model):
    """`work_priorities` — a priority that carries a PROMISE (`BR-WRK-018`).

    `sla_hours` is the promise: *Urgent = 4 hours* means an order raised at
    09:00 reads *Due 13:00* with nobody typing a date. The default is applied
    AT RAISE and stamped (`US-WRK-008` TC-4: changing Urgent from 4 h to 2 h
    does not move an order already raised) — `work_orders.due_at` is wave G's
    column and the derivation lands with it.

    `rank` is the list order and is unique per tenant, so two priorities
    cannot both claim to be second.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    rank = models.IntegerField()
    # Hours, and the unit is in the column name (hard rule 3). Whole hours: no
    # SLA in this product is expressed in fractions of one, and an integer
    # cannot round.
    sla_hours = models.IntegerField(default=0)
    colour = models.TextField(default="neutral")  # PRIORITY_COLOURS — a token
    #: `CR-187-BRC10` (PO answer 9, 2026-10-21: *"yes"* — a job may be pushed
    #: as urgent or emergency AUTOMATICALLY). Which push kind an ASSIGNMENT of
    #: a job at this priority rings with on the technician's phone
    #: (`push.PUSH_KINDS`). Seeded by `work/0045`: the tenant's most urgent
    #: active priority `emergency`, the next `urgent_assignment`, the rest
    #: `new_job`. A dispatcher may still choose explicitly per assignment.
    push_kind = models.TextField(default="new_job")
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_priorities"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(push_kind__in=PRIORITY_PUSH_KINDS),
                name="ck_work_priorities_push_kind",
            ),
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_work_priorities_tenant_code_ci"
            ),
            models.UniqueConstraint(
                fields=["tenant", "rank"], name="uq_work_priorities_tenant_rank"
            ),
        ]


class WorkHoldReason(models.Model):
    """`work_hold_reasons` — why a job came off the run (`CR-168-BRC10` P0.4).

    Judgment J1 (decision log 2026-10-04, *"THE WORK SERVER'S ANSWERS"*): a
    tenant LOOKUP row, never a CHECK list — the blueprint's own warning was that
    a CHECK makes *"Waiting for a permit"* a migration. The same shape as
    `work_priorities`: code, name, rank, active. `work_orders.hold_reason_id`
    points here (`metering/0071`), and a reason in use is deactivated, never
    deleted (PROTECT).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    rank = models.IntegerField(default=0)
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_hold_reasons"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_work_hold_reasons_tenant_code_ci"
            ),
        ]


class WorkSkill(models.Model):
    """`work_skills` — what a job needs a person to be able to do.

    A template names one (`US-WRK-013` replaces `work_order_templates.skill`,
    free text and NULL on all 24 seeded rows, with a FK here) and a technician
    holds one (`technician_skills`, wave F). Flat: code and name.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_skills"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_work_skills_tenant_code_ci"
            ),
        ]


class WorkSafetyKit(models.Model):
    """`work_safety_kits` — the kit a job's safety step asks for.

    `items` is the kit's contents. It is a LIST because a kit is a list —
    *Harness · Gas monitor · Tripod* — and the Settings card edits it as one
    comma-separated line (`items_text` in the serializer). The template
    builder's safety step (wave E) reads the array.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    # JSON rather than `ArrayField`: `django.contrib.postgres` types do not
    # exist on the sqlite the suite runs on (law 14's other face), and every
    # list-valued column in this product is already a JSONField for that
    # reason. The CONTENT is a list of strings and `lookups.py` enforces it.
    items = models.JSONField(default=list, blank=True)
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_safety_kits"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_work_safety_kits_tenant_code_ci"
            ),
        ]


class PartCategory(models.Model):
    """`part_categories` — how a parts register groups itself.

    Seeded *Meters · Consumables · Fittings · Test equipment*. The card's own
    sample copy names *locations Yard · Van 3/8/12* as well; **a location is a
    STOCK concept and is not modelled** (`OQ-WRK-1490`, `BR-WRK-019`), so it
    is not seeded here and no column holds it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()
    name = models.TextField()
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "part_categories"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_part_categories_tenant_code_ci"
            ),
        ]


class Part(models.Model):
    """`parts` — the register: part number, name, category, unit, unit cost.

    ⚠ **AND NOTHING ELSE.** There is no `on_hand`, no `reorder_at` and no
    `location` column on this model, and adding one is not a small change: it
    would answer `OQ-WRK-1490` — a question that is OPEN, routed to the
    Product Owner, and carries three options of which the register is (a).
    `Work-025` draws all three columns plus a reorder banner and *"Issues
    deduct stock the moment they are recorded"*; the card that specifies the
    same screen says *"No stock levels, no reorder points"*, and where the two
    disagree the CARD wins (`08-screen-layouts.md`, `DEF-WRK-3550`).

    `unit_cost` is money: stored to **4 decimals**, displayed to **2**
    (CLAUDE.md hard rule 2). `MTR-W58` is `92.4000` in the column and `$92.40`
    on the screen. The wireframe prices it at `78.40` and the card at
    `92.4000`; the card's figure is used (`03-field-map.md` §5 D-1).

    `unit_of_measure` is required — a quantity with no unit is hard rule 3's
    exact prohibition, and *"2 meters"* is a different fact from *"2 metres"*.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    part_no = models.TextField()
    name = models.TextField()
    category = models.ForeignKey(
        "work.PartCategory",
        on_delete=models.PROTECT,
        db_column="category_id",
        null=True,
        blank=True,
        related_name="parts",
    )
    unit_of_measure = models.TextField()
    unit_cost = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    is_system = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    #: `BR-TEN-057` — the sample tag on the OWNING row (`work/0025`). Set by
    #: `sample_workforce.py` AFTER creation and never accepted as input: a
    #: supervisor authoring one of these must not be able to mark it as sample
    #: data, or `--remove` would take work the utility wrote itself.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "parts"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("part_no"), name="uq_parts_tenant_part_no_ci"
            ),
        ]




# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE D · THE TEMPLATE BUNDLE — seven child collections, and versions
# ══════════════════════════════════════════════════════════════════════════
#
# `BR-WRK-009` — **a template is a bundle of seven child collections stored as
# ROWS, never a JSON blob**, following `BR-MET-108`'s precedent (a pricing
# characteristic is a row, not a column). The argument is the same one that
# file makes and it is about queryability rather than tidiness: a blob cannot
# be counted (`Work-013`'s CONTENTS column is *7 tasks · 3 parts · 3
# readings*), cannot be ordered by a drag handle (`wot_tasks.seq` is what the
# phone shows), cannot carry a unit in its own column (hard rule 3), and
# cannot be joined to `parts` so that a deleted part is refused.
#
# ⚠ **THE HEADER IS STILL METERING'S ROW.** `work_order_templates` lives in
# `apps/metering/connections.py` and these eight tables point AT it across the
# module boundary — the same reviewed-set FK `WorkOrderType.default_template`
# already declares twenty lines up, and for the same reason of geography.
# Nothing in this package writes that row: the header columns are written
# through `apps/work/seams/metering_seam.py`, which calls metering's own
# `write_work_order_template` by name (`BR-WRK-002`, G78).


class WorkOrderTemplateDetail(models.Model):
    """`wot_details` — ONE row per template: what the technician is shown, and
    what they must bring back.

    Four ticks from the builder's step 1 (`Work-014`, *WHAT THE TECHNICIAN SEES
    ON THE JOB*). A row per template rather than four columns on the header
    because the header is metering's table and these are Work's facts; the
    one-to-one is enforced by the unique key rather than by convention.

    ⚠ **THE THREE SIGNATURE COLUMNS ARRIVED WITH THE BUILDER'S STEP 7 (CR-070
    wave E, `work/0005`), AND THEY ARE THE TEMPLATE'S *ASK*, NEVER THE JOB'S
    *ANSWER*.** `08-screen-layouts.md` §13.1 names step 7 *Signature* and
    `Work-017`'s review counts it as **three items** — *"Customer signature
    required; refusal recorded with a reason"* — and until this migration no
    table in phase 1 held any of the three. `work_order_signatures` is
    `US-WRK-036`'s (phase 2, the phone) and records what a technician actually
    CAPTURED; these say what the template asks for before anybody goes out.
    They are named after that table's own columns (`refused`,
    `decline_reason`, `door_hanger_document_id`) so the ask and the answer read
    in one vocabulary rather than two.

    They live HERE and not on the header because the header is metering's table
    and this is a Work fact about what happens on the job — the same argument
    that put the four ticks here in wave D.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="wot_details",
    )
    show_account_summary = models.BooleanField(default=True)
    show_asset_card = models.BooleanField(default=True)
    show_access_notes = models.BooleanField(default=True)
    show_appointment = models.BooleanField(default=True)
    #: FB-023 F4 (PO 2026-10-31, *"B a fifth tick 'Balance & payments'"*,
    #: `work/0061`) — whether the phone DISPLAYS the balance card and the
    #: payment facts on this template's jobs. It never switches off FB-013's
    #: check: a money step still reads the balance and still stops on a cleared
    #: one (coordinator judgment, decision log FB-023 item 4). DEFAULT TRUE, so
    #: nothing a technician sees today disappears.
    show_balance_payments = models.BooleanField(default=True)
    #: FB-028 (PO 2026-10-31, *"the 25 $ limit should be part of work order
    #: template when payment check is included in work order template and it
    #: should not be part of settings"*, `work/0064`) — the most a customer may
    #: still owe for a technician to reconnect a job RAISED ON SITE from this
    #: template. Money: stored to 4 places, shown to 2 (hard rule 2). NULL =
    #: no limit set, which the builder only allows on a template with no
    #: payment check; it fills **25.0000** when a step turns the check on.
    reconnect_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    # ── CR-070 wave E · the builder's step 7 (`work/0005`) ─────────────────
    signature_required = models.BooleanField(default=True)
    refusal_reason_required = models.BooleanField(default=True)
    door_hanger_on_no_answer = models.BooleanField(default=True)
    # ── DEF-WRK-10652 (PO 2026-10-29, rulings 3B and 4A, `work/0060`) ──────
    #: What the CUSTOMER should do before the visit (*"Clear 3 ft around the
    #: meter box."*), carried into the logged / booked / moved messages as
    #: `{prep_instructions}`. NULL — blank — reads the utility's default
    #: (`WorkSettings.visit_prep_default`). Copied onto the job (`BR-WRK-008`).
    prep_instructions = models.TextField(null=True, blank=True)
    #: Ruling 4A — the TEMPLATE decides whether its jobs send the customer any
    #: visit message (logged, booked, moved, on the way, done). Never a type
    #: name: no code knows what a disconnect is. ON by default; seeded OFF on
    #: the sample disconnect / reconnect templates. Copied onto the job.
    send_customer_visit_messages = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wot_details"
        constraints = [
            models.UniqueConstraint(fields=["template"], name="uq_wot_details_template"),
        ]


class WorkOrderTemplateSafety(models.Model):
    """`wot_safety` — one safety line, in the order it was entered."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="wot_safety",
    )
    seq = models.IntegerField()
    text = models.TextField()
    is_mandatory = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wot_safety"
        constraints = [
            models.UniqueConstraint(fields=["template", "seq"], name="uq_wot_safety_seq"),
        ]


class WorkOrderTemplateTask(models.Model):
    """`wot_tasks` — one step of the job: title, minutes, photo, must-do.

    ⚠ **A TASK IS THREE FACTS AND NOT ONE** (`US-WRK-014` §1, verbatim): *"a
    title alone gives a technician a checklist; a title with minutes gives a
    dispatcher a schedule; a title with a photo flag gives a supervisor
    evidence."* `est_minutes` may be **0** and that is lawful — a mandatory
    zero-minute check is a real thing (`US-WRK-014` TC-4 guards that the
    validator does not read *no estimate* as *invalid*).

    `seq` is DATA, not presentation: it is the order the phone shows the steps
    in, so the drag handle on `Work-015` rewrites this column.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="wot_tasks",
    )
    seq = models.IntegerField()
    title = models.TextField()
    est_minutes = models.IntegerField(default=0)
    photo_required = models.BooleanField(default=False)
    is_mandatory = models.BooleanField(default=False)
    #: PO 2026-10-04 (*"THREE WORK ANSWERS"* (3)): *"Add an instruction text
    #: box to each task, shown on the technician's phone."* Optional and free
    #: text — *Isolate at the main before touching the meter.* `work/0028`.
    instruction = models.TextField(null=True, blank=True)
    #: CR-187-BRC10 T-35 · R18 (*"Freshness sits on the template step, the same
    #: way photo required and must do already do. No code knows what a
    #: disconnect is"*). NULL = this step reads no money; a number = the step
    #: needs the account's balance no older than that many minutes (R17's bar
    #: is 5, `MONEY_FRESH_DEFAULT_MINUTES`). Stale is WARNED, never blocked.
    #: `work/0039`.
    money_fresh_minutes = models.PositiveIntegerField(null=True, blank=True)
    #: CR-187-BRC10 · R111 — the TENANT'S charge code whose bill this step asks
    #: about beside the balance (FF-61: *the reconnect fee*). Data, never a
    #: constant (BR-BIL-007). NULL = no charge question. `work/0039`.
    money_charge_code = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wot_tasks"
        constraints = [
            models.UniqueConstraint(fields=["template", "seq"], name="uq_wot_tasks_seq"),
            models.CheckConstraint(
                condition=models.Q(est_minutes__gte=0), name="ck_wot_tasks_minutes_not_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(money_fresh_minutes__isnull=True)
                | models.Q(money_fresh_minutes__gte=1),
                name="ck_wot_tasks_money_fresh_positive",
            ),
        ]


class WorkOrderTemplateMaterial(models.Model):
    """`wot_materials` — a planned part and how many of it.

    `part` is PROTECT: a part a template plans cannot be deleted out from
    under it, which is `BR-TEN-034` in the schema. `unit_of_measure` is a
    column of its own and copied from the part at the moment it is added —
    hard rule 3, and the same reason `parts` carries one.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="wot_materials",
    )
    part = models.ForeignKey(
        "work.Part", on_delete=models.PROTECT, db_column="part_id", related_name="planned_in"
    )
    planned_qty = models.DecimalField(max_digits=18, decimal_places=4, default=1)
    unit_of_measure = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wot_materials"
        constraints = [
            models.UniqueConstraint(fields=["template", "part"], name="uq_wot_materials_part"),
        ]


#: `CR-168-BRC10` P1.33 — the two shapes a reading takes, and no third.
READING_KIND_NUMBER = "number"
READING_KIND_TEXT = "text"
READING_KINDS: tuple[str, ...] = (READING_KIND_NUMBER, READING_KIND_TEXT)


class WorkOrderTemplateReading(models.Model):
    """`wot_readings` — what has to be MEASURED, in `BR-WRK-015`'s six columns.

    ⚠ **`unit_of_measure` IS NOT NULL AND THAT IS HARD RULE 3.** A prompt
    reading *Final read (kWh)* is a unit hidden in a sentence: nothing can
    validate it, convert it or compare it, and `US-WRK-014` TC-3 refuses it by
    name. The unit is a COLUMN.

    `posts_as_meter_read` is the flag that makes a field reading arrive in
    `meter_reads` on approval (`BR-WRK-015`, wave L). It is stored here and
    consumed nowhere yet, which is deliberate: the specification is the
    template's, the posting is the approval's.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="wot_readings",
    )
    seq = models.IntegerField()
    prompt = models.TextField()
    unit_of_measure = models.TextField()
    min_value = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True, db_column="min_value"
    )
    max_value = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True, db_column="max_value"
    )
    required = models.BooleanField(default=True)
    photo_required = models.BooleanField(default=False)
    posts_as_meter_read = models.BooleanField(default=False)
    #: `CR-168-BRC10` P1.33 (`work/0028`) — `number` (a value and its unit,
    #: hard rule 3) or `text` (a serial, a seal number: *W-5000-N*). A text
    #: reading NEVER posts as a meter read (judgment J8) — `ck_wot_readings_
    #: text_never_posts` says so in the database as well as the builder.
    kind = models.TextField(default="number")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wot_readings"
        constraints = [
            models.UniqueConstraint(fields=["template", "seq"], name="uq_wot_readings_seq"),
            models.CheckConstraint(
                condition=models.Q(kind__in=READING_KINDS), name="ck_wot_readings_kind"
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="text", posts_as_meter_read=True),
                name="ck_wot_readings_text_never_posts",
            ),
        ]


#: `wot_help.kind` — the three shapes a help entry takes, and no fourth.
#: A CHECK rather than an enum type, which is what every other lookup-free
#: token column in this schema does.
HELP_KINDS: tuple[str, ...] = ("document", "phone", "note", "link")
#: `link` — PO ruling 6 (24 Sep): *"help can be an uploaded document or a video
#: link"* (`CR-168-BRC10` P3.25). An `https` address held in `ref`; a document
#: holds its stored document's id there (P3.14). Added by `work/0034`.
HELP_KIND_DOCUMENT = "document"
HELP_KIND_LINK = "link"


class WorkOrderTemplateHelp(models.Model):
    """`wot_help` — the help pack: a document, a phone number or a note."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="wot_help",
    )
    seq = models.IntegerField()
    kind = models.TextField()
    label = models.TextField()
    ref = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wot_help"
        constraints = [
            models.UniqueConstraint(fields=["template", "seq"], name="uq_wot_help_seq"),
            models.CheckConstraint(
                condition=models.Q(kind__in=HELP_KINDS), name="ck_wot_help_kind"
            ),
        ]


class WorkOrderTemplateAssetType(models.Model):
    """`wot_asset_types` — which asset types this template applies to.

    `asset_type_id` is a POINTER at the assets module's own catalogue, read
    through `apps/work/seams/assets_seam.py`. It is a plain uuid column and
    NOT a Django FK: a FK here would require importing `apps.assets.models`
    into this file, which G78 refuses outside `seams/` — and the seam is where
    the reviewed interface (B2 §2) belongs.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="wot_asset_types",
    )
    asset_type_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wot_asset_types"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "asset_type_id"], name="uq_wot_asset_types_type"
            ),
        ]


class WorkOrderTemplateVersion(models.Model):
    """`work_order_template_versions` — what was published, when, by whom.

    ⚠ **AN APPEND-ONLY RECORD OF THE ONE WRITE** (`BR-WRK-011`). A row is
    written by `publish` and by nothing else; a superseded version is never
    edited (`US-WRK-018` TC-3) and never deleted while an order references it
    (`BR-WRK-012`).

    `orders_raised` is DERIVED and is not a column here: `Work-022`'s Versions
    tab counts `work_orders` by `(template_id, template_version)` at read time,
    because a cached count on this row would be a second answer to a question
    the orders table already answers, and it is the copy that goes stale (the
    2026-09-05 ruling's *"two answers to one question is how a figure drifts"*).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        "work.WorkOrderTemplate",
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="versions",
    )
    version = models.IntegerField()
    published_at = models.DateTimeField()
    published_by = models.UUIDField(null=True, blank=True)
    change_note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_template_versions"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version"], name="uq_wot_versions_template_version"
            ),
        ]


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE F · THE WORKFORCE (Work-023, Work-024)
# ══════════════════════════════════════════════════════════════════════════
#
# Four tables from `03-field-map.md` §2.3, plus the one-row-per-tenant policy
# row the certification ruling needs. `technician_devices` is NOT here — it is
# `US-WRK-030`'s and arrives with the phone in wave J.
#
# ⚠ **A TECHNICIAN IS A PROFILE BESIDE A LOGIN, NEVER A SECOND LOGIN**
# (`BR-WRK-028`). `Technician.user` is a reviewed cross-module FK to
# `identity.User` and it is NOT NULL: `POST /work/technicians` refuses an email
# with no user and routes the caller to Settings → Team, because a second place
# to create people is a second place to invite, deactivate, reset and audit
# them — the same argument the Product Owner used on 2026-09-04 to keep field
# technicians in the one `users` table (`OQ-WRK-1494`).
#
# ⚠ **AND A CREW AND A CONTRACTOR ARE ROWS IN THE SAME TABLE AS A PERSON.**
# `WS-23` draws *Crew B (3)* and *Apex Utility Svc* between D. Ortiz and the
# rest, and `WM-13`'s reason is the one that matters: *"Whoever the work is
# offered to, the skill match is the same test."* A separate contractors table
# would fork that test in two and let the two copies disagree.


#: DEF-WRK-10652 — the PO's seeded default preparation text (2026-10-29).
VISIT_PREP_DEFAULT = (
    "Please give our technician clear access to the meter: unlock gates and keep pets inside."
)


class WorkSettings(models.Model):
    """`work_settings` — one row per tenant, holding the module's own policies.

    ⚠ **IT EXISTS BECAUSE `OQ-WRK-1493` WAS RULED PER-TENANT ON 2026-09-04.**
    The Product Owner chose option (c): a lapsed certification **blocks** an
    assignment or only **warns**, and the utility decides which. A two-person
    utility still has to be able to send J. Kaur out on 21 August; a utility
    with a safety officer has to be able to stop her. Both sides are built and
    this column is what picks one.

    ⚠ **WHY WORK'S OWN TABLE AND NOT `tenancy.tenant_settings`.** That row is
    tenancy's and Work writes nobody else's table (`BR-WRK-001`/`002`, and G78
    fails a foreign write). It is also organised one jsonb document per
    SETTINGS PAGE, and this is not a settings page — it is a dispatch policy
    the crews screen owns. A tenant with no row here reads the defaults below,
    exactly as `security_policies` serves a tenant that has never opened the
    tab.
    """

    #: `BR-WRK-030` as ruled: the expiry is SHOWN either way; only the refusal
    #: moves. `warn` is the seeded default and the value a new tenant starts at.
    LAPSE_WARN = "warn"
    LAPSE_BLOCK = "block"
    LAPSE_POLICIES = (LAPSE_WARN, LAPSE_BLOCK)

    id = uuid7_pk()
    tenant = models.OneToOneField(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id"
    )
    certification_lapse_policy = models.TextField(default=LAPSE_WARN)
    #: PO 2026-10-04 (*"THREE WORK ANSWERS"* (1), judgment J7): a job with no
    #: due date is measured against a DEFAULT target — *"the Normal priority's
    #: hours … a tenant setting"*. It NAMES A PRIORITY rather than storing
    #: hours, so a tenant that moves Normal from 72 h to 48 h moves every
    #: undated job with it. NULL reads as the tenant's `NORMAL` priority
    #: (`settings_svc.default_target`), which is the seeded answer without a
    #: row having to exist. `work/0028`.
    default_target_priority = models.ForeignKey(
        "work.WorkPriority",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="default_target_priority_id",
        related_name="+",
    )
    #: `BR-WRK-061` — how close a close's location fix must be to count as
    #: PRECISE, in metres. Our judgment (decision log, CR-168 §F): 50 m. A close
    #: whose best fix is wider is accepted and FLAGGED, never refused (PO ruling
    #: 2026-10-04, `BR-WRK-061`). `work/0035`.
    location_accuracy_m = models.IntegerField(default=50)
    #: `CR-168-BRC10` P5.3 (lane SRV-4, `work/0037`) — the at-risk list's
    #: WARNING WINDOW, in whole hours: an open job whose promise falls within
    #: this many hours of now is *at risk*. NULL — every tenant until a
    #: supervisor sets one — means *at risk once the promise has passed*, the
    #: only reading that invents no figure (§7.3 note on `sla.at_risk`). A
    #: product default would be a number nobody signed.
    at_risk_window_hours = models.IntegerField(null=True, blank=True)
    #: `CR-187-BRC10` — PO answer 9 as CORRECTED 2026-10-21: an automatic
    #: urgent / emergency push is an OPTION. ON: an assignment rings as its
    #: priority's `work_priorities.push_kind`. OFF: every assignment rings as
    #: an ordinary new job and only a dispatcher's explicit choice sends urgent
    #: or emergency. Seeded OFF for every tenant (our judgment, recorded) — a
    #: tenant with no row reads OFF too. `work/0045`.
    push_by_priority = models.BooleanField(default=False)
    #: DEF-WRK-10652 (PO 2026-10-29, ruling 3B, `work/0060`) — the utility's
    #: default preparation text, used when a job's template has none. NULL —
    #: every utility until somebody edits it — reads `VISIT_PREP_DEFAULT`; an
    #: EMPTY string is a utility that wants no default line at all.
    visit_prep_default = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_settings"


class Crew(models.Model):
    """`crews` — a crew or a contractor, offered work by the same skill test.

    `headcount` is the *(3)* in `Crew B (3)`. A contractor has none and the
    screen renders a dash rather than a nought, because *"nought people"* is a
    different fact from *"we do not count theirs"*.

    `shift_start` / `shift_end` are NULL for a contractor: `WS-23` draws *by
    arrangement*, which is an absence of a shift and not a shift from midnight
    to midnight.
    """

    KIND_CREW = "crew"
    KIND_CONTRACTOR = "contractor"
    KINDS = (KIND_CREW, KIND_CONTRACTOR)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    name = models.TextField()
    kind = models.TextField(default=KIND_CREW)
    headcount = models.IntegerField(null=True, blank=True)
    role_label = models.TextField(default="")  # WS-23's ROLE column: *Network crew*
    shift_start = models.TimeField(null=True, blank=True)
    shift_end = models.TimeField(null=True, blank=True)
    #: `CR-168-BRC10` P3.53 (`work/0028`) — how the office reaches a
    #: CONTRACTOR. NULL on a crew: a crew's people have their own logins and
    #: numbers, a contractor is reached at the firm. Refused on a crew by the
    #: service (`work.crew.contact_contractor_only`), not by a CHECK, so the
    #: day a crew gains a desk phone it is a ruling and not a migration.
    phone = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)
    #: `BR-TEN-057` — the sample tag on the OWNING row (`work/0025`). Set by
    #: `sample_workforce.py` AFTER creation and never accepted as input: a
    #: supervisor authoring one of these must not be able to mark it as sample
    #: data, or `--remove` would take work the utility wrote itself.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crews"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("name"), name="uq_crews_tenant_name_ci"
            ),
        ]
        indexes = [
            # `CR-168-BRC10` P3.23 (`work/0031`) — Crews pages its views in SQL.
            models.Index(fields=["tenant", "kind", "name"], name="ix_crews_tenant_kind_name"),
        ]


class Technician(models.Model):
    """`technicians` — what a login can DO, beside the login itself.

    ⚠ `user` IS NOT NULL AND IS UNIQUE PER TENANT. Two profiles for one login
    would give a dispatcher two D. Ortizes to pick between, each with half his
    skills, and no way to tell which the skill match used.

    `role_label` is the ROLE column's text (*Field technician · Senior
    technician*) and is NOT the identity role: `WS-23` shows *Senior
    technician* for R. Patel, which is a job title the utility types, while
    identity's `field_technician` is the thing that decides which app a login
    may open. Keeping them apart is deliberate — one is a label, the other is
    an access decision, and merging them would let a typo grant access.
    """

    STATUS_ON_SHIFT = "on_shift"
    STATUS_OFF_TODAY = "off_today"
    STATUS_UNAVAILABLE = "unavailable"
    #: FB-033 (`work/0062`) — what the technician says on the phone: *On
    #: break* and *Off duty*. ⚠ `off_duty` IS NOT `off_today`: `off_today` is
    #: End shift's (BR-WRK-069), `off_duty` is the technician's own word and
    #: can be undone the same day (decision log FB-033, D4 = B).
    STATUS_ON_BREAK = "on_break"
    STATUS_OFF_DUTY = "off_duty"
    STATUSES = (STATUS_ON_SHIFT, STATUS_OFF_TODAY, STATUS_UNAVAILABLE, STATUS_ON_BREAK, STATUS_OFF_DUTY)
    #: What the OFFICE may set by hand (`workforce.set_unavailable`). On break
    #: and Off duty are the technician's to say, from the phone.
    OFFICE_STATUSES = (STATUS_ON_SHIFT, STATUS_OFF_TODAY, STATUS_UNAVAILABLE)
    #: The PO's default (answer (2), 2026-10-05) — `work/0038`'s column default.
    DEFAULT_DAILY_JOB_LIMIT = 6

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    user = models.ForeignKey(  # ⚠ cross-module → identity (B2 §2 reviewed FK set)
        "identity.User", on_delete=models.PROTECT, db_column="user_id"
    )
    crew = models.ForeignKey(
        Crew, on_delete=models.PROTECT, null=True, blank=True, db_column="crew_id"
    )
    role_label = models.TextField(default="")
    shift_start = models.TimeField(null=True, blank=True)
    shift_end = models.TimeField(null=True, blank=True)
    van = models.TextField(default="")  # WS-24's note bar: *Van: Unit 12*
    status = models.TextField(default=STATUS_ON_SHIFT)
    #: FB-033 (`work/0062`) — WHEN `status` took its present value: the tap's
    #: moment for a phone change, the press for End shift, the office's save
    #: for a status set by hand. NULL until the first change after 0062.
    #: Crews reads it (*Off duty · since 15:30*); a phone tap older than it
    #: never overwrites the status (decision log FB-033).
    status_since = models.DateTimeField(null=True, blank=True)
    #: `US-WRK-020` TC-5 — a technician with assigned jobs is never deleted;
    #: *Set unavailable* is what a supervisor gets instead, and this is where
    #: the reason it was set lands so the crews screen can say why.
    unavailable_reason = models.TextField(default="")
    #: `CR-168-BRC10` §30 (`work/0038`) — how many jobs a day this person is
    #: expected to carry. PO answer (2), 2026-10-05: *"(b) Add a daily limit
    #: per technician (default 6), editable on the technician's page."*
    #: ADVICE, never a cap: nothing refuses a seventh job (ruling 2, NFR-5);
    #: the Schedule board marks the person over it.
    daily_job_limit = models.PositiveIntegerField(default=6)
    #: `BR-TEN-057` — the sample tag on the OWNING row (`work/0025`). Set by
    #: `sample_workforce.py` AFTER creation and never accepted as input: a
    #: supervisor authoring one of these must not be able to mark it as sample
    #: data, or `--remove` would take work the utility wrote itself.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "technicians"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="uq_technicians_tenant_user"),
        ]
        indexes = [
            # `CR-168-BRC10` P3.23 (`work/0031`) — a crew's members, counted.
            models.Index(fields=["tenant", "crew"], name="ix_technicians_tenant_crew"),
        ]


class TechnicianSkill(models.Model):
    """`technician_skills` — one row per skill a person or crew holds.

    ⚠ **THERE IS NO `not_held` PROFICIENCY AND THERE MUST NOT BE.** `WS-24`
    draws a *Not held* row for Water II, and that row is the ABSENCE of a row
    here: the screen derives it by listing the tenant's `work_skills` and
    subtracting the ones held. A stored `not_held` row would be a fact that
    goes stale the moment a skill is added to the catalogue, and two ways to
    answer *does this person hold Water II* is one too many.
    """

    PROFICIENCY_TRAINED = "trained"
    PROFICIENCY_CERTIFIED = "certified"
    PROFICIENCIES = (PROFICIENCY_TRAINED, PROFICIENCY_CERTIFIED)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        Technician, on_delete=models.CASCADE, db_column="technician_id", related_name="skills"
    )
    skill = models.ForeignKey(WorkSkill, on_delete=models.PROTECT, db_column="skill_id")
    proficiency = models.TextField(default=PROFICIENCY_TRAINED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "technician_skills"
        constraints = [
            models.UniqueConstraint(
                fields=["technician", "skill"], name="uq_technician_skills_person_skill"
            ),
        ]


class CrewSkill(models.Model):
    """`crew_skills` — the same fact for a crew or a contractor.

    ⚠ **A SEPARATE TABLE, AND THE REASON IS THE FOREIGN KEY RATHER THAN THE
    RULE.** `BR-WRK-029` says one skill test decides for a person, a crew and a
    contractor, and it does — `skill_match()` reads both tables and answers one
    question. What cannot be shared is the column: a row pointing at either
    `technicians` or `crews` needs a nullable pair of foreign keys and a check
    constraint saying exactly one is set, which is a shape that lets a bad row
    exist and then has to be policed. Two tables cannot hold that bad row at
    all.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    crew = models.ForeignKey(
        Crew, on_delete=models.CASCADE, db_column="crew_id", related_name="skills"
    )
    skill = models.ForeignKey(WorkSkill, on_delete=models.PROTECT, db_column="skill_id")
    proficiency = models.TextField(default=TechnicianSkill.PROFICIENCY_TRAINED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crew_skills"
        constraints = [
            models.UniqueConstraint(fields=["crew", "skill"], name="uq_crew_skills_crew_skill"),
        ]


class TechnicianCertification(models.Model):
    """`technician_certifications` — the person, the type and the date.

    The TYPE is `tenancy.CertificationType`, read through `tenancy_seam`: Work
    adds who holds it and when it runs out, and never a second list of what
    certifications exist (`US-WRK-021` TC-7).

    ⚠ `expires_on` IS NULLABLE, because not every certification expires, and a
    date in the PAST is accepted on entry (`US-WRK-021` TC-5): refusing it
    would lose the record of a lapse, which is the one thing the watch exists
    to show.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        Technician,
        on_delete=models.CASCADE,
        db_column="technician_id",
        related_name="certifications",
    )
    #: ⚠ cross-module → tenancy (B2 §2 reviewed FK set). The id is stored raw
    #: rather than as a Django FK so that Work declares no dependency on
    #: tenancy's migration graph for a lookup it only ever reads through the
    #: seam; `tenancy_seam.certification_types()` is what turns it into a name.
    certification_type_id = models.UUIDField()
    expires_on = models.DateField(null=True, blank=True)
    evidence_document_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "technician_certifications"
        constraints = [
            models.UniqueConstraint(
                fields=["technician", "certification_type_id"],
                name="uq_technician_certifications_person_type",
            ),
        ]


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE G · WHO HAD THIS JOB, AND WHEN — `BR-WRK-025`
# ══════════════════════════════════════════════════════════════════════════


class WorkOrderAssignment(models.Model):
    """`work_order_assignments` — **APPEND-ONLY**, `BR-WRK-025`, `WM-15`.

    `BR-WRK-025` verbatim: *"Assignment is an APPEND-ONLY history — assign,
    unassign, schedule, depart, arrive are rows in `work_order_assignments`.
    **Never an UPDATE.**"*

    WHY A HISTORY AND NOT THREE COLUMNS ON THE ORDER
    ------------------------------------------------
    The order DOES carry three cache columns — `assignee_technician_id`,
    `assigned_at`, `assigned_by` — and `03-field-map.md` §3 row 12 calls them a
    cache in exactly those words. They answer *who has it now*. They cannot
    answer *who had it before*, *when it was taken off D. Ortiz*, or *what time
    the van actually left*, and those are the three questions a dispatcher is
    asked when a customer rings to say nobody came.

    So the rows are the record and the columns are the summary, and
    `apps/work/dispatch.py` writes them in that order inside one transaction:
    the row first, the cache second. A cache can be rebuilt from the history;
    a history cannot be rebuilt from a cache.

    ⚠ **THE TRIGGER IS THE RULE, NOT THIS DOCSTRING** (hard-won law 1 — *a
    comment claiming a guarantee is not the guarantee*). `work/0009` puts a
    `BEFORE UPDATE OR DELETE` trigger on this table that raises, so the refusal
    holds for the ORM, for `raw()`, for a migration and for a person at a psql
    prompt. `tests/test_us_wrk_025_dispatch_pg.py` proves it on PostgreSQL,
    because SQLite runs no such trigger and would pass by vacuum (hard-won
    law 14's shape).

    ⚠ **`act` IS WHAT HAPPENED, AND FIVE IS THE WHOLE SET.** `depart` and
    `arrive` are here rather than on the phone's own table because they are the
    same fact as `assign` from the dispatcher's chair — a change in who is doing
    what and when — and splitting them would make *the history of this job* two
    queries that have to be merged in the right order by every reader.
    """

    ACT_ASSIGN = "assign"
    ACT_UNASSIGN = "unassign"
    ACT_SCHEDULE = "schedule"
    ACT_DEPART = "depart"
    ACT_ARRIVE = "arrive"
    ACTS: tuple[str, ...] = (ACT_ASSIGN, ACT_UNASSIGN, ACT_SCHEDULE, ACT_DEPART, ACT_ARRIVE)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ CROSS-MODULE FK work → metering, and the established direction in this
    #: file: nine columns already point at `metering.WorkOrderTemplate`.
    #: `work_orders` is metering's table until the blueprint's §16 settles the
    #: move (`03-field-map.md` §4), and this FK moves with it when it does.
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        db_column="work_order_id",
        related_name="assignments",
    )
    act = models.TextField()
    #: Who it went to. Both nullable, and both NULL on `unassign` — which is the
    #: row that says a job was taken OFF somebody, so it names no recipient.
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="technician_id",
        related_name="assignments",
    )
    crew = models.ForeignKey(
        "work.Crew",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="crew_id",
        related_name="assignments",
    )
    #: What was promised at this act — the date and the window a `schedule` row
    #: carries. Kept on the ROW as well as on the order, so a reschedule reads
    #: *moved from Tuesday 08:00–12:00 to Thursday 12:00–17:00* without joining
    #: to an audit blob.
    scheduled_for = models.DateTimeField(null=True, blank=True)
    window_start = models.DateTimeField(null=True, blank=True)
    window_end = models.DateTimeField(null=True, blank=True)
    #: WHO DID IT. Nullable only because the phone's own acts (wave K) may arrive
    #: from a device whose technician has no `identity.User` — `BR-WRK-028`'s
    #: boundary, which wave F left stubbed on `OQ-WRK-1492`.
    actor = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="actor_id",
        related_name="+",
    )
    #: `CR-168-BRC10` P4.4 (`work/0028`, judgment J2) — WHY, on a reassign.
    #: A reassign is ONE request writing TWO rows (`unassign` + `assign`), and
    #: both carry the same `reason` and the same `act_group`, so the Audit reads
    #: one act with one reason while `ck_work_order_assignments_act` keeps its
    #: five tokens (`BR-WRK-025`). Adding a column is not an UPDATE of a row:
    #: the append-only trigger (`work/0009`) is untouched.
    reason = models.TextField(null=True, blank=True)
    act_group = models.UUIDField(null=True, blank=True)
    #: `CR-187-BRC10` (lane S-GAPS, `work/0047`) — the handset's key for an
    #: act it sent from its outbox: a `depart` / `arrive` (`mobile.field_act`)
    #: or a hand-back's `unassign` (`field_dispatch.hand_back`). Minted AT
    #: CAPTURE (`07-endpoints.md` §0 rule 7, R45), unique per tenant where
    #: present, so a resend after a lost answer finds this row and answers
    #: *duplicate* instead of appending a second *depart*. NULL for every
    #: office act — the office's door is not an outbox and sends none.
    #: Written once, on INSERT; the append-only trigger (`work/0009`) still
    #: refuses any UPDATE of it.
    key = models.TextField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_assignments"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    act__in=("assign", "unassign", "schedule", "depart", "arrive")
                ),
                name="ck_work_order_assignments_act",
            ),
            #: A row names a person or a crew, never both — the order's own
            #: `ck_work_orders_one_assignee` one level down.
            models.CheckConstraint(
                condition=models.Q(technician__isnull=True) | models.Q(crew__isnull=True),
                name="ck_work_order_assignments_one_holder",
            ),
            #: One row per handset key (`CR-187-BRC10`, `work/0047`): the lost
            #: race between two sends of one outbox item ends here.
            models.UniqueConstraint(
                fields=["tenant", "key"],
                condition=models.Q(key__isnull=False),
                name="uq_work_order_assignments_key",
            ),
        ]
        indexes = [
            #: The order's own history, newest last — `GET /work-orders/{id}/audit`
            #: and the *three assign rows, not one* the bulk act must produce.
            models.Index(fields=["tenant", "work_order", "at"], name="ix_wo_assignments_order"),
        ]


# ══════════════════════════════════════════════════════════════════════════
# CR-070 wave N · what a job cost — `US-WRK-050`, `051`, `053`, `054`
#
# ⚠ FOUR TABLES OF MONEY AND NOT ONE OF THEM IS A BILL. A labour rate
# (`48.5000`), a part's cost (`96.0000`) and a report total (`138.42`) are
# stored to FOUR decimals and displayed to TWO (CLAUDE.md hard rule 2),
# computed by ONE named function (`apps.work.costing`, `BR-WRK-051`) and
# POSTED NOWHERE (`BR-WRK-004`, `OQ-WRK-1491` closed 2026-09-04 to option
# (a)). No journal line, no B4/B5 figure, no golden test — the freeze is not
# touched because nothing here is a bill.
# ══════════════════════════════════════════════════════════════════════════


class LabourRate(models.Model):
    """`labour_rates` — what an hour in the field costs, **per ROLE**.

    `BR-WRK-020`, CONFIRMED. Field technician `48.5000`/h, overtime
    `72.7500` after 8 h a day, effective 01 Jan 2026.

    ⚠ **PER ROLE, NEVER PER PERSON, AND THAT IS A DECISION RATHER THAN A
    SIMPLIFICATION** (`WM-45`, verbatim): *"a per-person rate is a salary, it
    belongs in payroll, and putting it on the crews screen would make `WS-23`
    a page a billing clerk must not open."* So there is no `technician_id`
    column here and adding one is not a small change — it would put a named
    person's pay on a screen a dispatcher opens to plan a day.

    ⚠ **APPEND-ONLY, ONE CURRENT PER ROLE.** A rate change is a NEW ROW and
    the old one gets `superseded_on`; it is **never an UPDATE** (`US-WRK-051`
    TC-3). The reason is the whole point of the table: `WO-4822` closed on
    15 Mar 2026 must still price at `48.5000` after the rate moves to
    `50.0000` on 1 April, and so must the 184 exchanges that closed before
    it. Editing the old row in place would silently reprice work that is
    already done — which is hard rule 4's shape, one table along from a bill.
    The order does not merely READ this table either: it keeps its own
    `labour_rate_snapshot` (`work_orders`, `metering/0051`), so a report is
    reproducible even if every row here were deleted.

    ⚠ **A CONTRACTOR CARRIES ONE RATE AND A DASH** (`WM-45`): *"an agency
    invoices its own overtime… The dash is the honest value."* So
    `overtime_hourly` and `overtime_after_hours` are NULLABLE, and NULL means
    *there is no such thing here* rather than *zero* — a contractor billed at
    `95.0000` flat would be given free overtime by a `0` default.

    Money is `numeric(18,4)` stored and two displayed (hard rule 2).
    `Work-030` is the ONE screen in the product that shows four, because it is
    the screen on which the stored value is being edited.
    """

    #: The role a rate belongs to. TEXT and not an enum, for the reason
    #: `work_orders.type` is text: `WS-23` lets a utility name its own roles,
    #: and an enum here would make a tenant's own role unrepresentable — the
    #: rate would then quietly fall back to somebody else's.
    #: The four the sample utility uses are below; `contractor:<crew_id>`
    #: carries the crew because two agencies do not share a price.
    ROLE_FIELD_TECHNICIAN = "field_technician"
    ROLE_SENIOR_TECHNICIAN = "senior_technician"
    ROLE_NETWORK_CREW = "network_crew"
    CONTRACTOR_PREFIX = "contractor:"

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    role = models.TextField()
    #: The words a supervisor typed — *Field technician*, *Apex Utility Svc*.
    #: Kept beside the code for the same reason `technicians.role_label` is
    #: kept beside identity's role: one is a label, the other is a key, and
    #: merging them makes a typo change which rate a job is priced at.
    role_label = models.TextField(default="")
    hourly = models.DecimalField(max_digits=18, decimal_places=4)
    #: NULL is a DASH on the screen, not a zero. See the contractor clause.
    overtime_hourly = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    #: Hours in a DAY after which overtime starts — `8` for an employee, NULL
    #: for a contractor. Not a duration: the threshold is counted in whole and
    #: part hours against a day's booked time, and `costing.py` is the only
    #: place that reads it.
    overtime_after_hours = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    effective_from = models.DateField()
    #: Set on the OLD row when a new one is written. NULL means *current*, and
    #: the partial unique index below is what makes "one current per role"
    #: a database guarantee rather than a service-layer intention.
    superseded_on = models.DateField(null=True, blank=True)
    #: `BR-TEN-057` — the sample tag on the OWNING row (`work/0025`). Set by
    #: `sample_workforce.py` AFTER creation and never accepted as input: a
    #: supervisor authoring one of these must not be able to mark it as sample
    #: data, or `--remove` would take work the utility wrote itself.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "labour_rates"
        constraints = [
            #: ONE CURRENT RATE PER ROLE — `BR-WRK-020`. A partial unique index
            #: on the rows that have not been superseded, so history is
            #: unlimited and the present is single. Two supervisors saving a
            #: new Field technician rate in the same second get one winner and
            #: one refusal, rather than two current rates and a report whose
            #: figure depends on row order.
            models.UniqueConstraint(
                fields=["tenant", "role"],
                condition=models.Q(superseded_on__isnull=True),
                name="uq_labour_rates_one_current_per_role",
            ),
            #: A rate is never negative. Free labour is a data-entry slip, and
            #: a negative one would credit a job.
            models.CheckConstraint(
                condition=models.Q(hourly__gte=0),
                name="ck_labour_rates_hourly_non_negative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "role", "effective_from"], name="ix_labour_rates_role_from"
            ),
        ]


class PartIssue(models.Model):
    """`part_issues` — who took what, when, and what for. **No count moves.**

    `BR-WRK-049`, CONFIRMED: *"Parts issued against a job are recorded as
    used-of-planned, naming who issued and when. NO on-hand count moves,
    because none lawfully exists."*

    ⚠ **THIS IS A LOG, NOT A LEDGER OF STOCK — `OQ-WRK-1490`, CLOSED
    2026-09-04 TO OPTION (a).** The Product Owner's own words: *"(a) — stock
    control is an inventory system, and the asset-maintenance precedent
    already parked it"*. So `Work-025`'s drawn *On hand 184 · Reorder at 60*,
    its *Roughly 320 units needed to restore cover* banner and its sentence
    *"Issues deduct stock the moment they are recorded"* are **not built**.
    D. Ortiz issuing two water meters from Van 12 against `WO-4821` writes ONE
    ROW HERE and moves **no count anywhere**. `services.stock_position()` is
    the boundary made visible and raises the ruling rather than a question id.

    ⚠ **`qty` IS SIGNED AND A RETURN IS A NEW POSITIVE ROW, NEVER A DELETION**
    (`US-WRK-050` TC-7): `−2` when D. Ortiz takes two, `+4` when R. Patel
    brings four back *Unused on job*. Deleting the issue would make the log
    say the parts were never taken, which is not what happened. This is hard
    rule 4's shape again — a correction is a new row — applied to a register
    that is not money but is evidence.

    ⚠ **`order_ref` IS PLAIN TEXT BY DESIGN AND IS NOT AN FK** (`WM-22`,
    verbatim): *"The work-order reference is plain text — this register does
    not know what a work order is."* It is what lets the register exist before
    the dispatcher does, and it lets a store-keeper write *"Van restock"* or
    *"Exchanges on Route 2 (ref WO-4821)"* — neither of which is one order.
    `Work-008`'s Parts tab reads the ORDER's own `work_order_materials`
    instead; the two are reconciled by the order number a human reads, not by
    a key, and that is deliberate.
    """

    #: What the movement was FOR. Text, not an enum — a store-keeper's reason
    #: is prose (*Van restock*, *Unused on job*) and the screen filters on it
    #: rather than branching on it.
    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    part = models.ForeignKey(
        "work.Part", on_delete=models.PROTECT, db_column="part_id", related_name="issues"
    )
    #: NEGATIVE for an issue, POSITIVE for a return. Never zero — a movement of
    #: nothing is a mis-keyed row, and the CHECK below refuses it rather than
    #: leaving the log with a line that means nothing.
    qty = models.DecimalField(max_digits=18, decimal_places=4)
    #: WHO took it. A technician or a crew, never both — the same shape
    #: `work_order_assignments` uses one table along, and for the same reason:
    #: *"D. Ortiz and Crew 2"* is not an answer to *who has this part*.
    issued_to_technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="issued_to_technician_id",
        related_name="+",
    )
    issued_to_crew = models.ForeignKey(
        "work.Crew",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="issued_to_crew_id",
        related_name="+",
    )
    purpose = models.TextField(default="")
    #: Plain text, deliberately. See the class docstring.
    order_ref = models.TextField(default="")
    #: WHO RECORDED IT — hard rule 7's discipline. A movement of stores that
    #: nobody's name is against is not evidence of anything.
    recorded_by = models.ForeignKey(  # ⚠ cross-module → identity (B2 §2 reviewed FK set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="recorded_by",
        related_name="+",
    )
    #: WHEN it happened, which is not when the row was typed. The issue log
    #: reads *Aug 16 08:10* because that is when D. Ortiz took the meters, and
    #: a clerk catching up on Monday must not restamp it to Monday
    #: (`BR-TEN-043` — an event date, never a wall clock).
    at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "part_issues"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(qty=0), name="ck_part_issues_qty_non_zero"
            ),
            #: A technician or a crew, never both.
            models.CheckConstraint(
                condition=models.Q(issued_to_technician__isnull=True)
                | models.Q(issued_to_crew__isnull=True),
                name="ck_part_issues_one_holder",
            ),
        ]
        indexes = [
            #: The log's own order — newest first, per `Work-025`'s default sort.
            models.Index(fields=["tenant", "at"], name="ix_part_issues_tenant_at"),
            #: The part detail's Movements tab.
            models.Index(fields=["tenant", "part", "at"], name="ix_part_issues_part_at"),
        ]


class WorkOrderCostLine(models.Model):
    """`work_order_cost_lines` — the three lines a report adds up.

    `BR-WRK-051`. Persisted AT ACCEPTANCE so that the report and the
    performance tab read **the same figures** rather than each recomputing
    them from tables that keep moving underneath — a rate is superseded, a
    part's unit cost is edited, and a report that recomputed would silently
    change after it was signed.

    ⚠ **THE STORED AMOUNT IS FOUR DECIMALS AND THE DISPLAYED ONE IS TWO, AND
    THE TOTAL IS THE SUM OF THE *DISPLAYED* ONES** (hard rule 2 + `BR-WRK-051`).
    `0.87 × 48.5000 = 42.1950` is what `amount` holds; `42.20` is what a
    reader sees; and the report's total is `42.20 + 96.00 + 0.22 = 138.42`,
    **not** the `138.4150` a four-decimal sum would give. That is the
    principle B4 already applies to a tax base — a reader adding the column
    must reach the total — and `costing.py` is the one place it happens.

    ⚠ **THERE IS NO TAX KIND AND THERE WILL NOT BE ONE** (`BR-WRK-052`, PO
    2026-09-03 verbatim: *"Dont add Tax on work order - for now"*). The
    wireframe `Work-032` draws two tax lines and a total of `149.84`; this
    table cannot hold them. `G111` fails the build if one is added.
    """

    KIND_LABOUR = "labour"
    KIND_OVERTIME = "overtime"
    KIND_PART = "part"
    #: ⚠ THREE KINDS. There is deliberately no `tax` — `BR-WRK-052`.
    KINDS = (KIND_LABOUR, KIND_OVERTIME, KIND_PART)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ CROSS-MODULE FK work → metering (B2 §2 reviewed set). `work_orders`
    #: is metering's table until the blueprint's §16 says otherwise
    #: (`03-field-map.md` §4), so a Work-owned child of it is a cross-module
    #: FK by construction. A POINTER: nothing here writes an order row.
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        db_column="work_order_id",
        related_name="cost_lines",
    )
    kind = models.TextField()
    #: What a reader sees in the first column — *Field technician*,
    #: *MTR-E1P — Electric meter, 1-phase*. Frozen prose, not a lookup: the
    #: part may be renamed next year and this report must not change.
    description = models.TextField()
    #: Hours for labour, a count for a part. WITH ITS UNIT (hard rule 3) —
    #: `0.87` alone is not a fact, `0.87 h` is.
    qty = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.TextField(default="")
    rate = models.DecimalField(max_digits=18, decimal_places=4)
    #: `qty × rate`, stored to four (hard rule 2). Displayed to two, and the
    #: TOTAL is the sum of those twos — see the class docstring.
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    #: The order the lines print in, so a report is byte-stable across two
    #: generations of the same figures.
    sequence = models.IntegerField(default=0)
    #: `CR-187-BRC10` (PO answer 11, 2026-10-21) — WHICH report version these
    #: lines add up to. The office may now reopen an ACCEPTED job, and the next
    #: acceptance writes `-v2` with its own lines BESIDE `-v1`'s (neither is
    #: overwritten — `work/0011`'s trigger). Every line written before `work/0045`
    #: belongs to `v1`, which is the only version that existed, so the column's
    #: default is the backfill and no frozen row is UPDATEd. Readers take the
    #: LATEST version's lines (`selectors.work_order_cost_lines`).
    report_version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_cost_lines"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=("labour", "overtime", "part")),
                name="ck_work_order_cost_lines_kind",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "work_order", "sequence"], name="ix_wo_cost_lines_order"
            ),
        ]


class WorkOrderReport(models.Model):
    """`work_order_reports` — generated ONCE, by Accept, and frozen.

    `BR-WRK-050`, CONFIRMED (`WM-47`): *"A PDF produced by
    `accept_field_result`, never by completion… Stored through
    `document_store` as kind `work_order_report`. A correction produces `-v2`
    beside `-v1`; neither is overwritten."*

    ⚠ **BY ACCEPT AND NEVER BY COMPLETION, AND THE REASON IS NOT TIDINESS**
    (`WM-47`): *"It is generated on approval and not on completion, because
    until a person accepts the field data nothing on the page is final."* A
    report produced at completion would be a document with a total on it that
    a supervisor had not yet agreed to. `US-WRK-053` TC-7 asserts there is no
    such call site — the renderer is reachable from `accept_field_result`
    only.

    ⚠ **A SECOND ACCEPT PRODUCES NO SECOND `v1`** (`US-WRK-053` TC-5). The
    unique key below is what guarantees it rather than the service layer's
    intention; the existing second-accept refusal in
    `metering.connections.accept_field_result` is the first line and this is
    the backstop, in the shape hard rule 6 uses for a bill run.

    ⚠ **A CORRECTION IS A NEW VERSION BESIDE THE OLD ONE, NEVER AN EDIT**
    (`US-WRK-053` TC-6) — hard rule 4's shape on a document. `v1` stays
    byte-identical after `v2` is written.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ CROSS-MODULE FK work → metering — see `WorkOrderCostLine` above.
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        db_column="work_order_id",
        related_name="reports",
    )
    version = models.IntegerField()
    #: ⚠ NULLABLE, AND THAT IS A DEPENDENCY AND NOT A CHOICE. The document is
    #: stored through tenancy's `stored_documents` under kind
    #: `work_order_report`, which `03-field-map.md` row 28 adds as part of
    #: `US-WRK-048` (CR-070 wave K, 33 → 36 kinds). **Wave K has not landed at
    #: the time this table is written**, so the row is created with its
    #: figures and no document, and `document_id` is filled the moment the
    #: kind exists. What is NOT deferred is the freeze: the cost lines are
    #: written and never rewritten, so the total on `-v1` cannot move.
    document_id = models.UUIDField(null=True, blank=True)
    generated_at = models.DateTimeField()
    generated_by = models.ForeignKey(  # ⚠ cross-module → identity (B2 §2 reviewed FK set)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="generated_by",
        related_name="+",
    )
    #: The total a reader reaches by adding the displayed column — `138.42`.
    #: Stored at TWO decimals because that is what it IS: a sum of rounded
    #: lines, not a rounded sum. Storing four would invite a later lane to
    #: "restore precision" and break `BR-WRK-051`.
    total = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_reports"
        constraints = [
            #: ONE `v1` PER ORDER, FOR EVER — `US-WRK-053` TC-5.
            models.UniqueConstraint(
                fields=["tenant", "work_order", "version"],
                name="uq_work_order_reports_order_version",
            ),
            models.CheckConstraint(
                condition=models.Q(version__gte=1), name="ck_work_order_reports_version"
            ),
        ]


# ══════════════════════════════════════════════════════════════════════════
# CR-070 WAVE H · THE ORDER'S OWN COPIES — `BR-WRK-008`, *COPY, NEVER LINK*
# ══════════════════════════════════════════════════════════════════════════
#
# `BR-WRK-008`, verbatim: *"**Copy, never link.** When an order is raised it
# takes its OWN copies of the template's details, safety rows, tasks, materials,
# readings and help, and stamps the template version. **Editing or publishing a
# template afterwards changes no order already raised.**"*
#
# WHY SIX TABLES AND NOT SIX JOINS
# --------------------------------
# A template says what a job of that kind INVOLVES. An order says what ONE job
# actually WAS. If the order read its checklist through `template_id`, then
# renaming task 3 this afternoon would rewrite the steps a technician followed
# in January — on every completed order that used it, silently, with no row
# changed and nothing in any audit trail to notice. The copy is what makes an
# order a RECORD rather than a VIEW of something still moving.
#
# ⚠ **SO NONE OF THESE SIX TABLES HAS A FOREIGN KEY TO ANY `wot_*` ROW, AND
# THAT ABSENCE IS THE RULE** (`US-WRK-032` TC-6 asserts it against the schema
# rather than against this comment — hard-won law 1). The ONLY reference an
# order keeps to the thing it was made from is `work_orders.template_id` plus
# `work_orders.template_version`, which together say *where this came from*
# without letting it move. `seq`, `title`, `unit_of_measure` and the rest are
# VALUES here, not lookups.
#
# It is the same posture three signed rules already take elsewhere in this
# schema: `invoice_lines.tariff_version_id`, `work_orders.est_duration`
# (`metering/0050`), and `work_orders.is_gate`. A published price, a promised
# duration and a checklist are all facts about a moment.
#
# THE SIX, AND WHY SIX RATHER THAN THE CARD'S THREE
# -------------------------------------------------
# `WM-18`'s card names three — tasks, readings, materials. The `WS-08` caption
# says *"the six order instance tables"*, `WS-11` shows safety and help copied
# too, and `WS-10` shows the Details ticks riding with the job. The decision-log
# row of 2026-09-03 settles it as **six copies, not three**, and
# `03-field-map.md` §5 records the discrepancy for §16. Copying five of six
# would leave a technician's safety list and gate code reading through a live
# template, which is the exact failure the rule exists to prevent.


class WorkOrderSafety(models.Model):
    """`work_order_safety` — the order's own safety list, copied at raise.

    ⚠ **THIS IS THE TABLE THE LOCK READS** (`BR-WRK-037`): *"Safety checks block
    the task list on the phone AND the server refuses a completion carrying an
    unticked mandatory safety row, naming the row. Two of three ticked is
    locked, not two-thirds unlocked."*

    So `is_mandatory` and `ticked_at` are not decoration: together they are the
    condition, and `apps/work/checklist.py` is the ONE place that evaluates it —
    for the staff screen and for the phone, so the two surfaces cannot drift
    into disagreeing about whether a job may proceed.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: ⚠ CROSS-MODULE FK work → metering, the direction `work_order_assignments`
    #: already established. `work_orders` is metering's table until §16 settles
    #: the move (`03-field-map.md` §4); this FK moves with it when it does.
    #: CASCADE and not PROTECT: a copy has no life of its own away from the
    #: order it was copied onto, which is the whole difference from a `wot_*` row.
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="safety_rows",
    )
    seq = models.IntegerField()
    #: A VALUE, not a lookup — the sentence as it read on the day this job was
    #: raised. `wot_safety.text` may be rewritten tomorrow; this may not.
    text = models.TextField()
    is_mandatory = models.BooleanField(default=True)
    ticked_at = models.DateTimeField(null=True, blank=True)
    ticked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="ticked_by",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_safety"
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "seq"], name="uq_work_order_safety_seq"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_safety_order"),
        ]


class WorkOrderTask(models.Model):
    """`work_order_tasks` — the seven steps this job actually asked for.

    ⚠ **NO FK TO `wot_tasks`.** `US-WRK-032` TC-2 is the shape of the rule:
    rename task 3 on the template and `WO-4822` still reads *Isolate supply &
    remove old meter*. TC-3 is the other half: publish v3 with eight tasks and
    `WO-4822` still has seven.

    `est_minutes` may be **0** and that is lawful — a mandatory zero-minute
    check is a real thing, and the template's own validator already guards that
    (`US-WRK-014` TC-4). It is copied rather than recomputed so that re-timing a
    template does not rewrite how long a crew was told a job would take.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="task_rows",
    )
    seq = models.IntegerField()
    title = models.TextField()
    est_minutes = models.IntegerField(default=0)
    photo_required = models.BooleanField(default=False)
    is_mandatory = models.BooleanField(default=False)
    #: PO answer (3) of 2026-10-04 — the template task's instruction text,
    #: COPIED like the title (`BR-WRK-008`): editing the template later does not
    #: re-word what this job's technician was told. Added by `work/0034`.
    instruction = models.TextField(null=True, blank=True)
    #: CR-187-BRC10 T-35 — the template step's freshness bar and charge code,
    #: COPIED like the title (`BR-WRK-008`), so editing the template later does
    #: not change what this job's technician was asked to check. `work/0039`.
    money_fresh_minutes = models.PositiveIntegerField(null=True, blank=True)
    money_charge_code = models.TextField(null=True, blank=True)
    #: R17 — *"Proceeding on stale data is recorded as unverified"*. The `as_at`
    #: of the figure the technician proceeded on (NULL = they saw none), when
    #: they proceeded, and the verdict: True = stale or unseen, False = fresh,
    #: NULL = this step was never proceeded on a money check. `work/0039`.
    money_as_at = models.DateTimeField(null=True, blank=True)
    money_proceeded_at = models.DateTimeField(null=True, blank=True)
    money_unverified = models.BooleanField(null=True, blank=True)
    ticked_at = models.DateTimeField(null=True, blank=True)
    ticked_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="ticked_by",
        related_name="+",
    )
    #: The FILE, when one was taken. A plain uuid and not a Django FK because
    #: `work_order_attachments` is wave K's table and does not exist yet — the
    #: B11 F-3 deferred-FK convention `work_orders.rule_id` already uses, and
    #: the FK is added by the migration that creates the table it points at.
    photo_attachment_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_tasks"
        constraints = [
            models.UniqueConstraint(fields=["work_order", "seq"], name="uq_work_order_tasks_seq"),
            models.CheckConstraint(
                condition=models.Q(est_minutes__gte=0),
                name="ck_work_order_tasks_minutes_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(money_fresh_minutes__isnull=True)
                | models.Q(money_fresh_minutes__gte=1),
                name="ck_work_order_tasks_money_fresh_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_tasks_order"),
        ]


class WorkOrderReading(models.Model):
    """`work_order_readings` — what has to be measured, and what was.

    ⚠ **`photo_required` IS THE RULE AND `photo_attachment_id` IS THE FILE, AND
    THEY ARE TWO COLUMNS** (`03-field-map.md` §2.4, `US-WRK-049`). Collapsing
    them into one nullable column would make *a photograph was asked for and not
    taken* indistinguishable from *no photograph was ever asked for* — which is
    exactly the question a supervisor reviewing a disputed final read is asking.

    ⚠ **`unit_of_measure` IS NOT NULL AND THAT IS HARD RULE 3** — *consumption
    always with an explicit unit; never assume*. A prompt reading *Final read
    (kWh)* is a unit hidden in a sentence: nothing can validate, convert or
    compare it. `BR-WRK-015`: the copied reading carries its unit.

    `in_range` is SERVER-DERIVED and nullable — NULL while no value has been
    captured, then True or False against `min_value`/`max_value` as they stood
    when the job was raised. It is stored rather than computed on read because
    the range can be edited on the template afterwards and the flag must go on
    meaning what it meant. `US-WRK-047` (wave K) is where an out-of-range
    reading flags and never refuses; this column is what it writes.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="reading_rows",
    )
    seq = models.IntegerField()
    prompt = models.TextField()
    unit_of_measure = models.TextField()
    min_value = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True, db_column="min_value"
    )
    max_value = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True, db_column="max_value"
    )
    required = models.BooleanField(default=True)
    #: THE RULE — did the template ask for a photograph of this reading.
    photo_required = models.BooleanField(default=False)
    posts_as_meter_read = models.BooleanField(default=False)
    #: What the technician actually read. Four decimals, hard rule 2's storage
    #: precision, which a meter read must match to post through metering's door.
    value = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    #: `CR-168-BRC10` P1.33 (`work/0028`). `kind` is COPIED from the template
    #: reading at the raise, like every other column here; `value_text` holds a
    #: reading that is words (*W-5000-N*). A text reading never posts as a
    #: meter read (hard rule 3, judgment J8): `posts_as_meter_read` is False on
    #: every copy whose kind is `text`, and the accept path reads `value` only.
    kind = models.TextField(default="number")
    value_text = models.TextField(null=True, blank=True)
    #: `DEF-WRK-10601` (`work/0051`). The technician's answer that there is NO
    #: figure (*Unable to read*, field app R13): `value` and `value_text` stay
    #: NULL, `in_range` stays NULL, and the row is flagged for the office in
    #: `close_readiness`. Never refused (decision log 2026-10-04, TECHNICIAN
    #: SYNC DESIGN: no field record is dropped). `unable_reason` is the CODE of
    #: one of metering's can't-read reasons (`DEF-MET-10609`, decision log
    #: 2026-10-26: one list for routes and jobs) — or, for a row captured
    #: before that, the words the phone sent. An unknown code is stored and
    #: flagged, never refused. `unable_note` is the technician's optional note
    #: (`work/0052`).
    unable_to_read = models.BooleanField(default=False)
    unable_reason = models.TextField(null=True, blank=True)
    unable_note = models.TextField(null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    captured_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="captured_by",
        related_name="+",
    )
    #: THE FILE — see `WorkOrderTask.photo_attachment_id` for why it is a plain
    #: uuid today.
    photo_attachment_id = models.UUIDField(null=True, blank=True)
    in_range = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_readings"
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "seq"], name="uq_work_order_readings_seq"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_readings_order"),
        ]


class WorkOrderMaterial(models.Model):
    """`work_order_materials` — planned of, and used of.

    `part` is a real FK and PROTECT, unlike everything else copied here, and the
    reason is that a part is a CATALOGUE ENTRY rather than a version of a
    sentence: `MTR-W58 · Water meter 5/8"` is the same object next year, and a
    job that used one must go on naming it. What is COPIED is `planned_qty` and
    `unit_of_measure` — how many the template asked for on the day, in the unit
    it asked in (hard rule 3, and the same reason `wot_materials` carries one).

    ⚠ **NO STOCK MOVES HERE AND THAT IS RULED, NOT MISSING** — `OQ-WRK-1490`,
    closed 2026-09-04 option (a): *"stock control is an inventory system"*. There
    is no `on_hand`, no `reorder_at` and no `location` anywhere in this module,
    and `used_qty` deducts nothing from anywhere.

    `unplanned` is what separates *the template asked for three and two were
    used* from *the technician needed a fourth thing nobody predicted* — the
    second is the row `Work-025` shows a supervisor, and without the flag it
    reads as a planning error rather than as what happened.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="material_rows",
    )
    part = models.ForeignKey(
        "work.Part", on_delete=models.PROTECT, db_column="part_id", related_name="used_in"
    )
    planned_qty = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    used_qty = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    unit_of_measure = models.TextField()
    issued_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="issued_by",
        related_name="+",
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    unplanned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_materials"
        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "part"], name="uq_work_order_materials_part"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order"], name="ix_wo_materials_order"),
        ]


class WorkOrderHelp(models.Model):
    """`work_order_help` — the SOP, the two phone numbers, the note.

    Copied for a reason the others share and one they do not: `US-WRK-042` says
    the help rows must open **with no signal**, so they ride with the job onto
    the phone. A help pack read through a live template is a help pack that is
    not there when a technician is standing in a basement.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="help_rows",
    )
    seq = models.IntegerField()
    #: The same shapes `wot_help` takes — `HELP_KINDS` (four since `work/0034`).
    kind = models.TextField()
    label = models.TextField()
    ref = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_help"
        constraints = [
            models.UniqueConstraint(fields=["work_order", "seq"], name="uq_work_order_help_seq"),
            models.CheckConstraint(
                condition=models.Q(kind__in=HELP_KINDS), name="ck_work_order_help_kind"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_help_order"),
        ]


class WorkOrderDetail(models.Model):
    """`work_order_details` — ONE row: what the technician is shown, and how to
    get in.

    Two sources rather than one, which is the difference from the other five.
    The four `show_*` flags are copied from `wot_details` — what the TEMPLATE
    says a technician needs on screen. `access_notes`, `hazards` and `gate_code`
    come from the PREMISES, because they are facts about the address rather than
    about the kind of job, and `WS-10` rides them onto the phone so a gate code
    is readable with no signal.

    ⚠ **A COPY OF AN ADDRESS FACT, NOT A SECOND HOME FOR AN ADDRESS.** Hard rule
    8 says an address lives on `premises` and nowhere else; `gate_code` and
    `access_notes` are not an address and no map or envelope is composed from
    them. The order still derives its address by walking to the premises.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="detail_rows",
    )
    access_notes = models.TextField(null=True, blank=True)
    hazards = models.TextField(null=True, blank=True)
    gate_code = models.TextField(null=True, blank=True)
    show_account_summary = models.BooleanField(default=True)
    show_asset_card = models.BooleanField(default=True)
    show_access_notes = models.BooleanField(default=True)
    show_appointment = models.BooleanField(default=True)
    #: FB-023 F4 (`work/0061`) — the template's fifth tick, copied at raise.
    show_balance_payments = models.BooleanField(default=True)
    #: FB-028 (`work/0064`) — the template's Reconnect limit, copied at raise
    #: (`BR-WRK-008`): editing the template later moves no raised job's gate.
    reconnect_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    #: DEF-WRK-10652 (`work/0060`) — the template's two visit-message facts,
    #: COPIED at raise (`order_copies`), so editing the template afterwards
    #: changes no message about a job already raised (`BR-WRK-008`).
    prep_instructions = models.TextField(null=True, blank=True)
    send_customer_visit_messages = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_details"
        constraints = [
            models.UniqueConstraint(fields=["work_order"], name="uq_work_order_details_order"),
        ]


class TechnicianDevice(models.Model):
    """`technician_devices` — the phone a job is pushed to (`US-WRK-030`).

    ONE ROW PER DEVICE, NOT PER TECHNICIAN. A two-person utility's technician
    carries one phone, but the same person re-installs the field app on a
    replacement handset and the old token stays valid at the provider for a
    while. So the row is the DEVICE, `active` is what a re-registration turns
    off on the rows it supersedes, and `US-WRK-030` TC-2's *"the phone has no
    registered push token"* is the question *does this technician have any
    ACTIVE device row*, which is a query rather than a nullable column on
    `technicians`.

    ⚠ **`token` IS A BEARER CREDENTIAL FOR SOMEBODY ELSE'S SERVICE.** It is
    what a push provider accepts as *"deliver to this handset"*. It is never
    rendered on a screen (B14 rule 31 already forbids the id; this forbids the
    token as well), never logged, and never returned by any read: the register
    call answers with `device_id` and `last_four`, which is enough for a
    technician to recognise their own phone in a list and useless to anybody
    who intercepts it.

    ⚠ **WHY IT IS WORK'S TABLE AND NOT IDENTITY'S.** The thing being addressed
    is a TECHNICIAN — a person on a route with jobs assigned — not a login. A
    clerk has a login and never a device row; a technician who leaves keeps
    their login for a week of handover and must stop receiving jobs the moment
    the profile is set unavailable. Hanging it off `technicians` makes that one
    fact rather than two that can disagree.

    ⚠ **NO `last_push_at` AND NO DELIVERY RECEIPT.** Whether a provider
    actually delivered is the provider's answer, arriving later and out of
    band, and a column here would be a comment claiming a guarantee (hard-won
    law 1). What the audit line says is what THIS product did: a push was
    ATTEMPTED against a registered token, or there was no token to attempt it
    against — `US-WRK-030` TC-2's *never* **pushed** *when it was not*.
    """

    PLATFORM_IOS = "ios"
    PLATFORM_ANDROID = "android"
    PLATFORM_WEB = "web"
    #: `web` is the one this product actually issues today — `BR-WRK-045` makes
    #: the phone a web app, so the token is a Web Push subscription rather than
    #: an APNs or FCM handle. The other two are declared because a utility
    #: wrapping the same app in a store shell later changes a token's SHAPE and
    #: nothing else, and a CHECK that would have to be rebuilt for that is a
    #: migration nobody would remember to write.
    PLATFORMS: tuple[str, ...] = (PLATFORM_IOS, PLATFORM_ANDROID, PLATFORM_WEB)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.CASCADE,
        db_column="technician_id",
        related_name="devices",
    )
    #: The push provider's handle. ⚠ **NULLABLE FROM `work/0043`
    #: (`CR-187-BRC10`)**: the native app registers a handset BY NAME at
    #: activation, before — or without — any push permission, so a row may
    #: carry no token at all. Push reads only rows that have one
    #: (`push._active_devices`).
    token = models.TextField(null=True, blank=True)
    platform = models.TextField(default=PLATFORM_WEB)
    #: What the technician sees in a list of their own phones — *iPhone 13* or
    #: whatever the browser reported, or the name given at activation (*Van 14
    #: tablet*). Free text, never trusted, never a key.
    label = models.TextField(default="")
    active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    #: Set by every sync, so a supervisor asking *"is that phone still in use"*
    #: reads a fact rather than an assumption. NOT a delivery receipt — see the
    #: docstring.
    last_seen_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    # ── CR-187-BRC10 · the native app's device registration (Security §4) ──
    # HUMAN-REVIEW-PENDING — 🔒 auth, AI-authored 2026-10-21; ledger row owed
    # by the coordinator.
    #: The handset's own stable id (the native app's `deviceId`). NULL on every
    #: row the web field app registered by push token alone. ⚠ **ONE ROW PER
    #: (DEVICE, TECHNICIAN), NOT PER DEVICE**: a shared tablet carries Dana's
    #: row and Marco's, so Dana's capture credential — bound to HER row — still
    #: verifies when her unsent items go up under Marco's sign-in (`BR-WRK-060`,
    #: `R132`). The office's remote sign-out signs out the PHYSICAL handset, so
    #: it acts on every row of the same `device_uid`.
    device_uid = models.TextField(null=True, blank=True)
    #: The office's remote sign-out (`R115`). Set once; cleared only by the
    #: technician registering the handset again after a fresh sign-in.
    signed_out_at = models.DateTimeField(null=True, blank=True)
    signed_out_by = models.UUIDField(null=True, blank=True)
    #: Bumped by every remote sign-out. A capture credential carries the epoch
    #: it was minted under; one from an earlier epoch names a signed-out
    #: registration, and its items are HELD for review rather than applied —
    #: never thrown away (`R113`, `R115`).
    capture_epoch = models.IntegerField(default=0)

    class Meta:
        db_table = "technician_devices"
        constraints = [
            #: The same handset registering twice must not become two rows that
            #: both get pushed — the technician would get the job twice and the
            #: audit could not say which token carried it. Per TENANT rather
            #: than globally: two utilities' tokens live in different provider
            #: projects and a collision across them is not our business, while
            #: a unique index spanning tenants would leak that a token exists
            #: elsewhere (HR-1).
            models.UniqueConstraint(
                fields=["tenant", "token"], name="uq_technician_devices_tenant_token"
            ),
            #: `CR-187-BRC10` — one registration per technician per handset.
            models.UniqueConstraint(
                fields=["tenant", "device_uid", "technician"],
                condition=models.Q(device_uid__isnull=False),
                name="uq_technician_devices_uid_tech",
            ),
        ]
        indexes = [
            #: The push path's only query: *this technician's active devices*.
            models.Index(
                fields=["tenant", "technician", "active"], name="ix_tech_devices_active"
            ),
            #: The remote sign-out's query: *every row of this handset*.
            models.Index(fields=["tenant", "device_uid"], name="ix_tech_devices_uid"),
        ]


#: The six collections an order copies at raise, and the model behind each —
#: read by `apps/work/checklist.py` and by `US-WRK-032` TC-1's count. Ordered as
#: `BR-WRK-008` names them.
ORDER_COPY_COLLECTIONS: dict[str, object] = {
    "details": WorkOrderDetail,
    "safety": WorkOrderSafety,
    "tasks": WorkOrderTask,
    "materials": WorkOrderMaterial,
    "readings": WorkOrderReading,
    "help": WorkOrderHelp,
}


# ── CR-070 wave K (2026-09-05) — what the phone sends back ────────────────
# `WorkOrderAttachment` and `WorkOrderSignature` are declared in
# `apps/work/evidence_models.py` and imported here because Django registers a
# model when the module defining it is imported, and `models.py` is what the app
# loads. They live in their own file rather than at the end of this one because
# this file is 1,900 lines with three CR-070 lanes editing it, and a pathspec
# commit takes the WHOLE working-tree content of every path it names (hard-won
# law 11, mechanism two). Two new tables did not need to carry that risk.
# Re-exported so `from apps.work.models import WorkOrderAttachment` keeps
# working for anyone who reaches for the obvious import.
from apps.work.evidence_models import (  # noqa: E402,F401  (import placed with the models it registers)
    WorkOrderAttachment,
    WorkOrderSignature,
    WorkPhotoLink,
)

# ── CR-070 wave M (2026-09-05) — the rules engine ─────────────────────────
# `WorkOrderRule` and `WorkOrderRuleRaise` are declared in
# `apps/work/rules_models.py` for the reason wave K gave for `evidence_models`:
# this file is ~1,950 lines with other CR-070 lanes editing it, and a pathspec
# commit takes the WHOLE working-tree content of every path it names (hard-won
# law 11, mechanism two). One import line is the smallest edit that registers
# two models.
from apps.work.rules_models import (  # noqa: E402,F401  (import placed with the models it registers)
    WorkOrderRule,
    WorkOrderRuleEscalationFire,
    WorkOrderRuleRaise,
    WorkOrderRuleTrigger,
)

# ── CR-070 wave L (2026-09-05) — the server's memory of an offline day ────
# Same reasoning as the block above, one table: `WorkSyncReceipt` lives in
# `apps/work/sync_models.py` and is imported here so Django registers it.
from apps.work.sync_models import (  # noqa: E402,F401  (import placed with the model it registers)
    WorkSyncReceipt,
)

# ── CR-187-BRC10 Phase 13 (2026-10-21) — one row per money change pushed ───
# Same reasoning again: `WorkMoneyPush` lives in `apps/work/money_models.py`.
from apps.work.money_models import (  # noqa: E402,F401  (import placed with the model it registers)
    WorkMoneyPush,
)

# ── CR-187-BRC10 T-41 (2026-10-21) — an alert sent to a handset, and its answer.
# Same reasoning again, one table: `apps/work/alert_models.py`.
from apps.work.alert_models import (  # noqa: E402,F401  (import placed with the model it registers)
    WorkFieldAlert,
)

# ── CR-187-BRC10 lane S-ORDER (2026-10-21) — the field app's order acts ────
# Same reasoning again: three tables in `apps/work/field_order_models.py`.
from apps.work.field_order_models import (  # noqa: E402,F401  (import placed with the models it registers)
    WorkFieldRaise,
    WorkOrderLabour,
    WorkOrderReopen,
)

# ── CR-187-BRC10 lane FINDINGS (2026-10-22) — a route finding (`BR-WRK-067`).
# Same reasoning again, one table: `apps/work/route_finding_models.py`.
from apps.work.route_finding_models import (  # noqa: E402,F401  (import placed with the model it registers)
    WorkRouteFinding,
)

# ── CR-193-BRC10 (MQ-040 step 1, 2026-10-26) — working days, one-day
# exceptions, End shift and submitted timesheet days: `shift_models.py`.
from apps.work.shift_models import (  # noqa: E402,F401  (import placed with the models it registers)
    TechnicianDayException,
    TechnicianShiftEnd,
    TechnicianWorkingDays,
    TimesheetSubmission,
)

# ── FB-033 (2026-10-31) — every availability tap from the phone:
# `availability_models.py`.
from apps.work.availability_models import (  # noqa: E402,F401  (import placed with the model it registers)
    TechnicianAvailabilityChange,
)

# ── CR-194-BRC10 (2026-10-26, PO "store on both") — the server's copy of a
# refused field item, for the office: `refused_models.py`.
from apps.work.refused_models import (  # noqa: E402,F401  (import placed with the model it registers)
    WorkRefusedItem,
)

# ── CR-187-BRC10 T-43 (2026-10-21) — the six Work tables come home ─────────
# `connections`, `connection_services`, `work_orders`, `work_order_templates`,
# `service_characteristics` and `connection_todos` were declared in
# `apps/metering/connections.py` until T-43; they are Work's
# (`16-work/03-field-map.md` §4) and now live in `apps/work/connection_models.py`.
# ⚠ THIS IMPORT IS WHAT REGISTERS THEM — without it `makemigrations` sees six
# models in Work's migration state that the registry lacks and proposes to drop
# the tables (the drift `metering/models.py` once carried the same line against).
from apps.work.connection_models import (  # noqa: E402,F401  (import placed with the models it registers)
    Connection,
    ConnectionService,
    ConnectionTodo,
    ServiceCharacteristic,
    WorkOrder,
    WorkOrderTemplate,
)

class WorkBulkRaise(models.Model):
    """`work_bulk_raises` — the FIRST answer to one bulk raise, kept so a
    repeated press returns it instead of raising the jobs twice (`CR-168-BRC10`
    P2.12, ruling 19; CLAUDE.md hard rule 6's shape for a write a person can
    send twice).

    🔒 HUMAN-REVIEW-PENDING (idempotency keys are a CLAUDE.md sensitive path).

    ⚠ **NO BATCH NUMBER.** `OQ-WRK-1497` closed 2026-09-04 (*"three separate
    assignments"*): a bulk act is N separate jobs, never a numbered thing, so
    this row is not a "batch" a person can see or quote — it holds the answer
    and nothing else. `idempotency_key` is the client's (the screen mints one
    per press); the tenant is the constraint's other column, never in the key.

    ⚠ **THE KEY IS CLAIMED BEFORE THE FIRST JOB IS RAISED**, inside the same
    transaction, so a second press racing the first blocks on the unique index
    until the first commits and then reads its answer — the PostgreSQL case in
    `tests/test_cr168_srv2_bulk_raise_pg.py` proves it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    idempotency_key = models.TextField()
    actor_id = models.UUIDField(null=True, blank=True)
    answer = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_bulk_raises"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"], name="uq_work_bulk_raises_tenant_key"
            ),
        ]


#: The seven collections a caller may replace, and the model behind each. The
#: ROUTE is one (`PUT /work/templates/{id}/{collection}`) precisely because
#: seven near-identical routes are seven places for a rule to be forgotten.
TEMPLATE_COLLECTIONS: dict[str, object] = {
    "safety": WorkOrderTemplateSafety,
    "tasks": WorkOrderTemplateTask,
    "materials": WorkOrderTemplateMaterial,
    "readings": WorkOrderTemplateReading,
    "help": WorkOrderTemplateHelp,
    "asset-types": WorkOrderTemplateAssetType,
}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-007/008/009/010@81bb7e45 (EP-WRK-02) · 03-field-map.md §2.1 · 10-execution-plan.md wave C task C1
# generated: 2026-09-04 by the CR-070 wave C build lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H✔(work/0002_rls_force is the 🔒 path; review-ledger row is C4)
# gates: pytest tests/test_us_wrk_00{7,8,9}*.py tests/test_us_wrk_010_parts.py · tests/test_us_wrk_rls_pg.py on PostgreSQL · G78 (Work writes nothing foreign)
# exceptions: no `on_hand`/`reorder_at`/`location` on `parts` — OQ-WRK-1490, asserted by name in the tests · the six EXISTING Work tables stay in apps/metering (03-field-map.md §4, §16 unread)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
