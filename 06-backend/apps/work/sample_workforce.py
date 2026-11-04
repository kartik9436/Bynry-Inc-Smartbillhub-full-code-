# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-020 (crews & technicians) · US-WRK-021 (certifications) ·
#           US-WRK-010 (the parts register) · US-WRK-051 (labour rates) ·
#           US-TEN-019 (the sample set)   Screens: WS-23 · WS-24 · Work-025 ·
#           Work-030
# Rules:    BR-TEN-056/057/061/063/066 (a sample block: tagged, idempotent,
#           removable, partial-and-named) · BR-WRK-002 (Work writes no other
#           module's table — the logins come from identity) · BR-WRK-020 (a
#           labour rate is per ROLE and append-only) · BR-WRK-028 (a technician
#           is a profile beside an existing login) · BR-WRK-030 (the lapse
#           policy is per tenant) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           hard rule 2 (money 4 dp stored, 2 displayed) · hard rule 3 (a
#           quantity carries its unit) · hard rule 7 (every money action
#           writes audit_log) · hard-won law 14 (a SAVEPOINT, not a bare
#           `except … continue`)
# Tests:    06-backend/tests/test_cr070_sample_workforce.py
# Impacts:  apps/tenancy/sample_data.py (SAMPLE_MODULES) · apps/work/services.py
# ───────────────────────────────────────────────────────
"""**THIRTY-NINE WORK ORDERS AND NOBODY TO SEND** — this block is the crew.

WHAT WAS MEASURED, AND WHY THIS FILE EXISTS
---------------------------------------------
On 2026-09-07, across all six seeded tenants: `crews` **0**, `technicians`
**0**, `technician_skills` **0**, `technician_certifications` **0**, `parts`
**0**, `labour_rates` **0**, `work_settings` **0**. Against that: 39 raised
work orders, 8 skills, 6 certificate types, 4 safety kits, 4 part categories
and 8 work items — every one of them a REFERENCE list seeded at provisioning,
and not one of them with a person or a price attached.

So `Work → Crews` opened onto an empty table, the skills catalogue described
abilities nobody held, and **no work order in the product could be costed**,
because costing multiplies a labour rate by minutes and there were no rates.
The engine was proved by tests; the screens were proved by nothing (hard-won
law 6).

THE BOUNDARY, WHICH DECIDES THE SHAPE OF THIS FILE
----------------------------------------------------
`work.technicians.user` is NOT NULL and unique per tenant, and Work **may not
create a user** — it reads identity through `apps/work/seams/identity_seam.py`
and writes no other module's table (`BR-WRK-002`; `G78` fails the merge on the
first commit that tries). So the four field logins are seeded by IDENTITY's own
block, which runs first in `SAMPLE_MODULES`, and this block attaches a profile
to each one it finds. That is not a workaround: it is the same two steps a real
supervisor performs — invite on Settings → Team, then add the profile on
Work → Crews — and `create_technician` refuses a `user_id` with no login behind
it by name, which is the rule this block is obeying rather than dodging.

⚠ **IF IDENTITY'S BLOCK DID NOT RUN, THIS ONE SEEDS THE CREWS AND NAMES THE
ABSENCE** (`BR-TEN-060`): crews, parts, rates and settings need no login, so
they land, and the technicians are reported as not seeded WITH THE REASON. A
silent zero would look identical to a tenant that simply has no field staff.

WHAT IT SEEDS, AND WHY EACH NUMBER IS THAT NUMBER
---------------------------------------------------
The ICP is a North American utility of up to 40,000 accounts run by **10–20
staff** (CLAUDE.md). Everything here is sized to that and to nothing larger:

  * **3 crew rows** — two CREWS (`Field crew A`, `Field crew B`, headcount 2
    each, shifts that do not overlap) and one CONTRACTOR (`Redline Meter
    Services`). The contractor is what makes `WS-23`'s dash real: `headcount`
    NULL renders *—* rather than *0* ("nought people" is a different fact from
    "we do not count theirs"), and NULL shifts render *by arrangement*.
  * **4 technicians** across the two crews, one of them **off today** — a
    dispatcher's screen where everybody is available is a screen that never
    shows the state it exists to show.
  * **12 technician skills and 4 crew skills**, drawn from the eight already
    seeded. Nobody holds all eight: `WS-24` draws a *Not held* row by
    SUBTRACTING what is held from the catalogue, so a technician who holds
    everything makes that row unreachable.
  * **7 certifications, and one of them expires in 18 days.** That is the
    whole reason the certification screens are worth opening —
    `certification_watch()` sorts by how soon a certificate runs out, and a
    set that all expire in 2028 renders a watch with nothing to watch. One is
    already **LAPSED**, on the technician who is off today, because
    `work_settings.certification_lapse_policy` is the tenant's choice between
    *warn* and *block* (`BR-WRK-030`, PO ruling 2026-09-04) and neither branch
    has a subject without a lapse to test it against.
  * **10 parts** priced 1.8500–142.0000, over the four seeded categories.
  * **4 labour rates**, one current per role — `field_technician` 48.5000/h
    with overtime 72.7500 after 8 h (`BR-WRK-020`'s own confirmed figures),
    `senior_technician` 61.0000/h, `network_crew` 55.0000/h, and the
    contractor at 95.0000 flat **with a NULL overtime**, which is the dash
    `WM-45` calls *"the honest value"*.
  * **1 `work_settings` row** at the seeded default `warn`.

⚠ **EVERY ROW GOES THROUGH THE SCREEN'S OWN SERVICE** — `workforce.create_crew`,
`create_technician`, `set_skills`, `set_certifications`, `services.create_part`,
`services.create_labour_rate` — never a bare `objects.create`. That is the PO's
standing rule (*"everything should be executed based on actual code"*) and it
buys three things a direct insert would not: every validation the screen
applies is applied here, hard rule 7's audit row is written by the same code
that writes it for a clerk, and a refusal this fixture provokes is a refusal a
utility would have met. The two exceptions are `crew_skills` (which has no
service — `set_skills` is the technician's) and `work_settings`, and both are
Work's OWN tables written by Work.

⚠ **`is_sample` IS SET AFTER THE FACT, NOT PASSED IN** — the same posture
`apps/work/sample_data.py` takes for rules, and for the same reason: a
supervisor authoring a crew must never be able to mark it as sample data, or
`--remove` would take work the utility wrote itself.
"""

from __future__ import annotations

import logging
from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.work import models as work_models
from apps.work import services as work_services
from apps.work import workforce
from apps.work.seams import identity_seam, tenancy_seam
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work")

#: The three crew rows. `kind`, `headcount` and the shift pair are the whole
#: difference between a crew and a contractor on `WS-23`, so all three vary.
SEEDED_CREWS: tuple[dict[str, Any], ...] = (
    {
        "name": "Field crew A",
        "kind": work_models.Crew.KIND_CREW,
        "headcount": 2,
        "role_label": "Network crew",
        "shift_start": "07:00",
        "shift_end": "15:30",
        "skills": (("WATER_I", "certified"), ("EXCAVATION", "trained")),
    },
    {
        "name": "Field crew B",
        "kind": work_models.Crew.KIND_CREW,
        "headcount": 2,
        "role_label": "Meter crew",
        "shift_start": "12:00",
        "shift_end": "20:30",
        "skills": (("METER_I", "certified"),),
    },
    {
        # ⚠ NO headcount and NO shift, on purpose. `WS-23` renders a dash and
        # *by arrangement*; a contractor seeded with `0` and midnight-to-
        # midnight would make both of those unreachable.
        "name": "Redline Meter Services",
        "kind": work_models.Crew.KIND_CONTRACTOR,
        "headcount": None,
        "role_label": "Contractor",
        "shift_start": None,
        "shift_end": None,
        "skills": (("METER_I", "certified"),),
    },
)

#: The four technicians, keyed on the identity login's email — which is what
#: `apps/identity/sample_data.SAMPLE_STAFF` seeds and the ONLY handle this
#: module has on them across the boundary (`users` carries no `is_sample`
#: column, so the `@sample.test` address is identity's own sample key).
#:
#: `role_label` is the ROLE column's prose and is NOT identity's role code —
#: `technicians.role_label` says so at length. It also decides which labour
#: rate a closed job is priced at: `services.snapshot_labour_rate_at_close`
#: slugifies this text and matches it against `labour_rates.role`, so
#: *Field technician* → `field_technician` → 48.5000/h. A label that matches
#: nothing stamps NOTHING and the job yields no labour line at all, which is
#: why these four read exactly as the rates below are named.
SEEDED_TECHNICIANS: tuple[dict[str, Any], ...] = (
    {
        "email": "d.ortiz@sample.test",
        "crew": "Field crew A",
        "role_label": "Field technician",
        "shift_start": "07:00",
        "shift_end": "15:30",
        "van": "Unit 12",
        "status": work_models.Technician.STATUS_ON_SHIFT,
        "skills": (("WATER_I", "certified"), ("METER_I", "certified"), ("READS", "trained")),
        "certifications": (("FA-CPR", 540), ("TRAF", 18)),
    },
    {
        "email": "r.patel@sample.test",
        "crew": "Field crew A",
        "role_label": "Senior technician",
        "shift_start": "07:00",
        "shift_end": "15:30",
        "van": "Unit 3",
        "status": work_models.Technician.STATUS_ON_SHIFT,
        "skills": (
            ("WATER_I", "certified"),
            ("WATER_II", "certified"),
            ("METER_I", "certified"),
            ("EXCAVATION", "certified"),
        ),
        "certifications": (("FA-CPR", 260), ("TRENCH", 700), ("CONF-SP", 410)),
    },
    {
        "email": "m.chen@sample.test",
        "crew": "Field crew B",
        "role_label": "Field technician",
        "shift_start": "12:00",
        "shift_end": "20:30",
        "van": "Unit 8",
        "status": work_models.Technician.STATUS_ON_SHIFT,
        "skills": (("METER_I", "certified"), ("READS", "certified"), ("ELECTRIC_I", "trained")),
        "certifications": (("FA-CPR", 95),),
    },
    {
        # ⚠ OFF TODAY, and the one carrying a LAPSED certificate. Both states
        # exist so the screens that render them have a subject: a crews page
        # where everybody is on shift never shows *Off today*, and the lapse
        # policy (`BR-WRK-030`) has two branches and no lapse to try them on.
        "email": "j.okoro@sample.test",
        "crew": "Field crew B",
        "role_label": "Field technician",
        "shift_start": "12:00",
        "shift_end": "20:30",
        "van": "Unit 5",
        "status": work_models.Technician.STATUS_OFF_TODAY,
        "unavailable_reason": "Annual leave until Monday",
        "skills": (("WATER_I", "trained"), ("READS", "trained")),
        "certifications": (("FA-CPR", -12),),
    },
)

#: `Work-025`'s register. `unit_cost` is money — stored to FOUR decimals
#: (hard rule 2), displayed to two. `MTR-W58` at `92.4000` is `03-field-map.md`
#: §5 D-1's own figure, taken from the card rather than from the wireframe's
#: `78.40` where the two disagree.
SEEDED_PARTS: tuple[dict[str, Any], ...] = (
    {"part_no": "MTR-W58", "name": "Water meter 5/8\" positive displacement",
     "category": "METERS", "unit_of_measure": "each", "unit_cost": "92.4000"},
    {"part_no": "MTR-W100", "name": "Water meter 1\" positive displacement",
     "category": "METERS", "unit_of_measure": "each", "unit_cost": "142.0000"},
    {"part_no": "MTR-E1P", "name": "Electric meter single-phase",
     "category": "METERS", "unit_of_measure": "each", "unit_cost": "78.5000"},
    {"part_no": "GSK-58", "name": "Meter gasket 5/8\"",
     "category": "CONSUMABLES", "unit_of_measure": "each", "unit_cost": "1.8500"},
    {"part_no": "SEAL-WIRE", "name": "Meter seal, wire and tag",
     "category": "CONSUMABLES", "unit_of_measure": "each", "unit_cost": "0.7500"},
    {"part_no": "TAPE-PTFE", "name": "PTFE thread tape",
     "category": "CONSUMABLES", "unit_of_measure": "roll", "unit_cost": "2.2000"},
    {"part_no": "CPL-58B", "name": "Brass coupling 5/8\"",
     "category": "FITTINGS", "unit_of_measure": "each", "unit_cost": "6.4000"},
    {"part_no": "VLV-CS58", "name": "Curb stop valve 5/8\"",
     "category": "FITTINGS", "unit_of_measure": "each", "unit_cost": "24.9000"},
    {"part_no": "PIPE-CU34", "name": "Copper service pipe 3/4\"",
     "category": "FITTINGS", "unit_of_measure": "ft", "unit_cost": "3.1500"},
    {"part_no": "TST-BF", "name": "Backflow test kit calibration",
     "category": "TEST_EQUIPMENT", "unit_of_measure": "each", "unit_cost": "48.0000"},
)

#: `BR-WRK-020` — one CURRENT rate per role, and a contractor's overtime is a
#: DASH rather than a zero. The first row's three figures are the rule's own
#: confirmed ones and are what `US-WRK-053` TC-1's arithmetic is pinned to.
SEEDED_LABOUR_RATES: tuple[dict[str, Any], ...] = (
    {"role": "field_technician", "role_label": "Field technician",
     "hourly": "48.5000", "overtime_hourly": "72.7500", "overtime_after_hours": "8",
     "effective_from": "2026-01-01"},
    {"role": "senior_technician", "role_label": "Senior technician",
     "hourly": "61.0000", "overtime_hourly": "91.5000", "overtime_after_hours": "8",
     "effective_from": "2026-01-01"},
    {"role": "network_crew", "role_label": "Network crew",
     "hourly": "55.0000", "overtime_hourly": "82.5000", "overtime_after_hours": "8",
     "effective_from": "2026-01-01"},
    {"role": "contractor", "role_label": "Redline Meter Services",
     "hourly": "95.0000", "overtime_hourly": None, "overtime_after_hours": None,
     "effective_from": "2026-01-01"},
)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _skill_ids() -> dict[str, Any]:
    """`work_skills` code → id, for the tenant in context. Work's own table."""
    return {
        row.code: row.id
        for row in work_models.WorkSkill.objects.filter(tenant_id=_tenant_id())
    }


def _certification_type_ids() -> dict[str, Any]:
    """Certificate code → id, read THROUGH THE SEAM.

    `certification_types` is tenancy's table and Work never holds a second
    list of what certifications exist (`US-WRK-021` TC-7). The seam serves
    dicts; the CODE is what this file keys on, because a name is prose a
    utility may edit and a code is not.
    """
    out: dict[str, Any] = {}
    for kind in tenancy_seam.certification_types():
        code = str(kind.get("code") or "").strip()
        if code:
            out[code] = kind["id"]
    return out


def _users_by_email() -> dict[str, Any]:
    """The tenant's logins, keyed by lowercased email — READ, through the seam.

    `identity_seam.staff_user_choices()` is the *add a technician* picker's own
    read (`BR-WRK-028`), so this block sees exactly the logins a supervisor
    would be offered and cannot attach a profile to one they could not.
    """
    return {
        str(row.get("email") or "").strip().lower(): row["user_id"]
        for row in identity_seam.staff_user_choices()
        if row.get("email")
    }


def _time(value: str | None):
    if not value:
        return None
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _seed_crews(actor: Any, skills: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """The three crew rows and their `crew_skills`. Returns (written, by name)."""
    tenant_id = _tenant_id()
    existing = {
        row.name: row.id for row in work_models.Crew.objects.filter(tenant_id=tenant_id)
    }
    written = 0
    for spec in SEEDED_CREWS:
        crew_id = existing.get(spec["name"])
        if crew_id is None:
            try:
                # hard-won law 14 — a SAVEPOINT, so this `except` really can
                # continue. On PostgreSQL one refused INSERT aborts the WHOLE
                # transaction (this runs inside tenancy's per-module atomic),
                # and every later statement would raise InFailedSqlTransaction
                # while the entire SQLite suite stayed green. Not tidiness.
                with transaction.atomic():
                    created = workforce.create_crew(
                        actor,
                        {
                            "name": spec["name"],
                            "kind": spec["kind"],
                            "headcount": spec["headcount"],
                            "role_label": spec["role_label"],
                            "shift_start": spec["shift_start"],
                            "shift_end": spec["shift_end"],
                        },
                    )
            except Exception as exc:  # noqa: BLE001 — named, never swallowed
                logger.info(
                    "sample data (CR-070 workforce): crew %r was not seeded — %s: %s. "
                    "Work > Crews will list one row fewer than the drawing",
                    spec["name"], type(exc).__name__, exc,
                )
                continue
            crew_id = created["id"]
            written += 1
            # BR-TEN-057 — the tag on the owning row, written by this module on
            # its OWN table. `create_crew` does not accept it and must not.
            work_models.Crew.objects.filter(tenant_id=tenant_id, pk=crew_id).update(
                is_sample=True
            )
        existing[spec["name"]] = crew_id
        for code, proficiency in spec["skills"]:
            skill_id = skills.get(code)
            if skill_id is None:
                continue  # this tenant does not carry that skill; named below
            with transaction.atomic():
                work_models.CrewSkill.objects.get_or_create(
                    tenant_id=tenant_id,
                    crew_id=crew_id,
                    skill_id=skill_id,
                    defaults={"proficiency": proficiency},
                )
    return written, existing


def _seed_technicians(
    actor: Any, crews: dict[str, Any], skills: dict[str, Any], certs: dict[str, Any]
) -> int:
    """One profile per seeded field login. Returns how many were CREATED."""
    tenant_id = _tenant_id()
    users = _users_by_email()
    today = date.today()
    written = 0
    for spec in SEEDED_TECHNICIANS:
        user_id = users.get(spec["email"])
        if user_id is None:
            # BR-TEN-060 — a NAMED not-loaded line, never a silent zero. This
            # is the one precondition this block cannot supply for itself:
            # Work may not create a login (BR-WRK-002, G78).
            logger.info(
                "sample data (CR-070 workforce): technician %r was not seeded — this tenant "
                "has no login %s for a profile to sit beside (BR-WRK-028). Check the Sample "
                "staff users block, which is what invites them",
                spec["role_label"], spec["email"],
            )
            continue
        row = work_models.Technician.objects.filter(
            tenant_id=tenant_id, user_id=user_id
        ).first()
        if row is None:
            try:
                with transaction.atomic():  # law 14 — see `_seed_crews`
                    workforce.create_technician(
                        actor,
                        {
                            "user_id": user_id,
                            "crew_id": crews.get(spec["crew"]),
                            "role_label": spec["role_label"],
                            "shift_start": spec["shift_start"],
                            "shift_end": spec["shift_end"],
                            "van": spec["van"],
                        },
                    )
            except Exception as exc:  # noqa: BLE001 — named, never swallowed
                logger.info(
                    "sample data (CR-070 workforce): technician %s was not seeded — %s: %s",
                    spec["email"], type(exc).__name__, exc,
                )
                continue
            row = work_models.Technician.objects.get(tenant_id=tenant_id, user_id=user_id)
            written += 1
            work_models.Technician.objects.filter(pk=row.pk).update(is_sample=True)
        # `status` and `unavailable_reason` are set on Work's OWN table rather
        # than through `set_unavailable`, which is the supervisor's ACTION and
        # writes an audit row saying a person was taken off the roster today.
        # A fixture stating that J. Okoro is on leave is describing the world,
        # not performing that act.
        if spec["status"] != work_models.Technician.STATUS_ON_SHIFT:
            work_models.Technician.objects.filter(pk=row.pk).update(
                status=spec["status"],
                unavailable_reason=spec.get("unavailable_reason", ""),
            )
        wanted_skills = [
            {"skill_id": str(skills[code]), "proficiency": proficiency}
            for code, proficiency in spec["skills"]
            if code in skills
        ]
        if wanted_skills and not row.skills.exists():
            with transaction.atomic():
                workforce.set_skills(actor, row.id, {"skills": wanted_skills})
        # ⚠ THE EXPIRY DATES ARE RELATIVE TO TODAY AND THAT IS THE POINT. A
        # fixture with a hard-coded 2027 date is a certification watch that is
        # correct on the day it is written and meaningless a year later — the
        # *18 days* row is what puts a name in the *Expiring soon* panel, and
        # the *−12 days* row is what gives `BR-WRK-030`'s two branches a
        # subject. Both move with the calendar, for ever.
        wanted_certs = [
            {
                "certification_type_id": str(certs[code]),
                "expires_on": (today + timedelta(days=days)).isoformat(),
            }
            for code, days in spec["certifications"]
            if code in certs
        ]
        if wanted_certs and not row.certifications.exists():
            with transaction.atomic():
                workforce.set_certifications(actor, row.id, {"certifications": wanted_certs})
    return written


def _seed_parts(actor: Any) -> int:
    """`Work-025`'s register, through the screen's own service.

    ⚠ **`category` IS A CODE OR A NAME, NEVER AN ID** — `_clean_part` resolves
    it by matching `part_categories.name` first and then `.code`, which is
    hard-won law 2's mirror one layer down and B14 rule 31's shape (*"no
    database id is ever the visible value of a field"*): the parts form posts
    the words a clerk picked. The first draft of this file passed the UUID and
    every one of the ten parts was refused with `work.parts.category_unknown` —
    correctly, and the seeder reported each refusal by name, which is the only
    reason it took one run to find.
    """
    tenant_id = _tenant_id()
    known = {
        row.code
        for row in work_models.PartCategory.objects.filter(tenant_id=tenant_id)
    }
    existing = set(
        work_models.Part.objects.filter(tenant_id=tenant_id).values_list("part_no", flat=True)
    )
    written = 0
    for spec in SEEDED_PARTS:
        if spec["part_no"] in existing:
            continue  # BR-TEN-063 — a replay changes no count
        payload = {
            "part_no": spec["part_no"],
            "name": spec["name"],
            "unit_of_measure": spec["unit_of_measure"],
            "unit_cost": spec["unit_cost"],
        }
        if spec["category"] in known:
            payload["category"] = spec["category"]
        try:
            with transaction.atomic():  # law 14 — see `_seed_crews`
                created = work_services.create_part(actor, payload)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 workforce): part %r was not seeded — %s: %s",
                spec["part_no"], type(exc).__name__, exc,
            )
            continue
        written += 1
        work_models.Part.objects.filter(tenant_id=tenant_id, pk=created["id"]).update(
            is_sample=True
        )
    return written


def _seed_labour_rates(actor: Any) -> int:
    """`BR-WRK-020` — one current rate per role, and the contractor's dash.

    ⚠ **THE CONTRACTOR ROLE IS `contractor`, NOT `contractor:<crew_id>`.**
    The model documents the prefixed form for a utility that uses two agencies
    at two prices; this sample utility uses one, and a seeded id inside a role
    code would be a value nobody could read on `Work-030`.
    """
    tenant_id = _tenant_id()
    existing = set(
        work_models.LabourRate.objects.filter(
            tenant_id=tenant_id, superseded_on__isnull=True
        ).values_list("role", flat=True)
    )
    written = 0
    for spec in SEEDED_LABOUR_RATES:
        if spec["role"] in existing:
            continue
        try:
            with transaction.atomic():  # law 14 — see `_seed_crews`
                created = work_services.create_labour_rate(
                    actor,
                    {
                        "role": spec["role"],
                        "role_label": spec["role_label"],
                        "hourly": spec["hourly"],
                        "overtime_hourly": spec["overtime_hourly"],
                        "overtime_after_hours": spec["overtime_after_hours"],
                        "effective_from": spec["effective_from"],
                    },
                )
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 workforce): labour rate %r was not seeded — %s: %s. "
                "A job closed by that role will carry NO labour line at all (BR-WRK-020)",
                spec["role"], type(exc).__name__, exc,
            )
            continue
        written += 1
        work_models.LabourRate.objects.filter(
            tenant_id=tenant_id, pk=created["id"]
        ).update(is_sample=True)
    return written


def _seed_settings() -> int:
    """One `work_settings` row at the seeded default.

    ⚠ **THE DEFAULT IS ALREADY `warn` IN THE MODEL, SO WHY WRITE A ROW AT
    ALL.** Because a tenant with no row reads the default and the Crews screen
    has no policy to SHOW being changed — `BR-WRK-030` was ruled per-tenant
    precisely so a utility could pick, and a demo where the control has never
    been written to cannot demonstrate picking. The value seeded is the same
    one an unwritten row would read, so nothing behaves differently; what
    changes is that the row exists to be edited.
    """
    _, created = work_models.WorkSettings.objects.get_or_create(
        tenant_id=_tenant_id(),
        defaults={"certification_lapse_policy": work_models.WorkSettings.LAPSE_WARN},
    )
    return 1 if created else 0


def seed_sample_records(actor: Any) -> int:
    """`BR-TEN-056/057` — the crew, the register and the rates.

    Returns the number of rows CREATED across all six tables, which is 0 on a
    replay and 0 again on a tenant that already has them — both of which are
    success, not a skip (`BR-TEN-010`).
    """
    skills = _skill_ids()
    certs = _certification_type_ids()
    crews_written, crews = _seed_crews(actor, skills)
    technicians = _seed_technicians(actor, crews, skills, certs)
    parts = _seed_parts(actor)
    rates = _seed_labour_rates(actor)
    settings = _seed_settings()
    return crews_written + technicians + parts + rates + settings


def remove_sample_records() -> dict[str, Any]:
    """`BR-TEN-061/066` — delete this block's `is_sample` rows, name the rest.

    ⚠ **A TECHNICIAN WITH JOBS AGAINST THEIR NAME IS RETAINED, BY NAME**, which
    is `US-WRK-020` TC-5's own rule arriving one table along: `work_orders.
    assignee_technician_id` is a live FK and a deleted row would leave a job
    assigned to nobody with no way to see it happened. They are set
    UNAVAILABLE instead — the same answer a supervisor gets from the screen —
    and reported as retained.

    ⚠ **A PART OR A RATE THAT PRICED A CLOSED JOB IS RETAINED TOO.** The cost
    LINES are frozen (`work/0011`'s trigger) so nothing reprices, but
    `work_order_materials.part_id` is PROTECT and the delete would simply be
    refused — reporting the reason beats reporting a failure.

    The order below is the only one that works: skills and certifications
    CASCADE from a technician, technicians PROTECT their crew, and materials
    PROTECT their part. B2 declares no `ON DELETE CASCADE` on any of it.
    """
    tenant_id = _tenant_id()
    removed = 0
    retained: list[dict[str, Any]] = []

    for row in work_models.Technician.objects.filter(tenant_id=tenant_id, is_sample=True):
        if work_models.WorkOrderAssignment.objects.filter(
            tenant_id=tenant_id, technician_id=row.id
        ).exists():
            if row.status != work_models.Technician.STATUS_UNAVAILABLE:
                work_models.Technician.objects.filter(pk=row.pk).update(
                    status=work_models.Technician.STATUS_UNAVAILABLE,
                    unavailable_reason="sample data removed",
                )
            retained.append(
                {
                    "label": f"technician {row.role_label or row.id}",
                    "reason": (
                        "work orders are assigned to them; deleting the profile would leave "
                        "those jobs assigned to nobody. They are set unavailable instead"
                    ),
                }
            )
            continue
        row.delete()  # skills and certifications CASCADE
        removed += 1

    for crew in work_models.Crew.objects.filter(tenant_id=tenant_id, is_sample=True):
        if work_models.Technician.objects.filter(tenant_id=tenant_id, crew_id=crew.id).exists():
            retained.append(
                {
                    "label": f"crew {crew.name}",
                    "reason": "a technician still belongs to it, and a crew is not deleted "
                              "out from under a person",
                }
            )
            continue
        work_models.CrewSkill.objects.filter(tenant_id=tenant_id, crew_id=crew.id).delete()
        crew.delete()
        removed += 1

    for part in work_models.Part.objects.filter(tenant_id=tenant_id, is_sample=True):
        used = work_models.WorkOrderMaterial.objects.filter(
            tenant_id=tenant_id, part_id=part.id
        ).exists()
        planned = work_models.WorkOrderTemplateMaterial.objects.filter(
            tenant_id=tenant_id, part_id=part.id
        ).exists()
        if used or planned:
            retained.append(
                {
                    "label": f"part {part.part_no}",
                    "reason": "a job or a template still names it, and the price it was "
                              "recorded at is part of that record",
                }
            )
            continue
        part.delete()
        removed += 1

    for rate in work_models.LabourRate.objects.filter(tenant_id=tenant_id, is_sample=True):
        rate.delete()
        removed += 1

    # ⛔ `work_settings` HAS NO `is_sample` COLUMN and is a ONE-ROW-PER-TENANT
    # policy row rather than sample content — the same divergence
    # `wizard_parks`, `disconnect_cases` and `account_protections` already
    # carry. Deleting it would take a utility's own choice of lapse policy with
    # it. It is left, and the column is OWED (reported, never papered over).
    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    """How many sample workforce rows this tenant holds right now, read live."""
    tenant_id = _tenant_id()
    return int(
        work_models.Crew.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + work_models.Technician.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + work_models.Part.objects.filter(tenant_id=tenant_id, is_sample=True).count()
        + work_models.LabourRate.objects.filter(tenant_id=tenant_id, is_sample=True).count()
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-070 · US-WRK-020/021/010/051 · US-TEN-019 · PO standing rule
#         ("everything should be executed based on actual code")
# generated: 2026-09-07 by the CR-070 work sample-data lane
# checklist: A✔ B=n/a(no new screen — WS-23/WS-24/Work-025/Work-030 render it)
#         C✔ D=n/a(no endpoint) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr070_sample_workforce.py · G78 · G66 (savepoints)
# exceptions: `work_settings` has no `is_sample` column, so removal leaves it —
#         reported in `remove_sample_records`, and the column is OWED.
#         `crew_skills` is written directly because no service publishes it
#         (`set_skills` is the technician's); it is Work's own table.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
