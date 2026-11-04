# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 (a work order type catalogue) · US-WRK-008 (priorities,
#           each with its SLA hours) · US-WRK-009 (skills, safety kits, parts
#           categories — the three parked Settings cards) · US-WRK-010 (the
#           parts register, and NO stock level) · US-WRK-012 (the four cards
#           and the four series; `dispatch_batch` stays unwired)
# Rules:    BR-WRK-017 · BR-WRK-018 · BR-WRK-019 · BR-WRK-021 · BR-SHL-035
#           (a card is DATA, served by the one management view) · BR-TEN-031
#           (the owning module validates) · BR-TEN-036 (a seeded row is
#           deactivatable, never deletable) · CLAUDE.md hard rule 1 (tenant
#           isolation) · hard rule 2 (4 stored, 2 displayed) · hard rule 3 (a
#           quantity carries its unit)
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""US-WRK-007 · 008 · 009 · 010 · 012 — the Work reference data, by TC.

⚠ **THE RLS HALF OF `US-WRK-010` TC-6 IS NOT HERE AND CANNOT BE.**
`config/settings/test.py` hardcodes in-memory SQLite, **which has no row-level
security at all**, so an RLS assertion made in this file would pass by vacuum
(CLAUDE.md hard-won law 14, one rule along). The isolation cases below are the
APPLICATION-layer proof — the handler filters by the tenant in context and one
tenant's rows are absent from the other's list. The DATABASE-layer proof is
`tests/test_us_wrk_rls_pg.py`, which runs on real PostgreSQL 16 under a
non-superuser probe role and reads `relrowsecurity`/`relforcerowsecurity` out
of `pg_class` for all six tables.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.tenancy import services as tenancy_services
from apps.work import lookups as work_lookups
from apps.work import models as work_models
from apps.work import selectors as work_selectors
from apps.work import services as work_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _codes(model, tenant):
    return set(model.objects.filter(tenant=tenant).values_list("code", flat=True))


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-012 — the four cards stop saying "arrives with Work"
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_012_tc1_the_five_lists_are_declared_and_owned_by_work():
    """The registry declares them and names `work` as the owner (BR-TEN-031).

    Without this row a card 404s — `lookup_handler` raises NotFound for a list
    tenancy does not declare, which is the skip-until-wired law and exactly
    what these four cards did for three weeks.
    """
    for code in (
        "work_order_types",
        "work_priorities",
        "work_skills",
        "work_safety_kits",
        "work_parts_categories",
    ):
        definition = tenancy_services.LOOKUP_LISTS[code]
        assert definition.owner == "work", code


def test_us_wrk_012_tc1_the_handlers_are_registered_at_startup(brazos):
    """`WorkConfig.ready()` ran and every list resolves to Work's handler."""
    for code, handler in work_lookups.WORK_LOOKUP_HANDLERS.items():
        resolved = tenancy_services.lookup_handler(code)
        assert isinstance(resolved, handler), code


def test_us_wrk_012_tc4_nothing_allocates_from_the_dispatch_batch_series():
    """`BR-WRK-021` — the series is seeded and allocated by NOTHING.

    ⚠ **READ AS A GREP OVER THE BACKEND, NOT AS A MOCK.** `OQ-WRK-1497` asks
    what a dispatch batch IS; until it is answered, inventing a caller would
    answer it. The series stays on the Numbering screen exactly as seeded (the
    PO ruled the four standalone on 2026-08-16) and this test is what keeps it
    that way.
    """
    import re
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    callers = []
    for path in backend.glob("apps/**/*.py"):
        if "migrations" in path.parts:
            continue  # a migration may NAME the series it seeds
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if "dispatch_batch" not in line:
                continue
            # `allocate(... "dispatch_batch" ...)` is the shape that would be a
            # caller. A seed row, a constant and a comment are not.
            #
            # ⚠ **AND A COMMENT IS WHAT IT KEPT FINDING (`DEF-WRK-4062`,
            # 2026-09-05).** The clause above says a comment is not a caller and
            # the code did not act on it, so this test matched
            # `apps/work/dispatch.py`'s own lifecycle footer — *"`dispatch_batch`
            # allocates nothing (BR-WRK-021, OQ-WRK-1497 OPEN)"* — because that
            # line contains `dispatch_batch` and the word `allocates` contains
            # `allocate`. **The sentence asserting the rule was read as breaking
            # it**, and the suite was red at the tip for every lane.
            #
            # `G78`'s docstring records the same trap and its cure: *"Comments
            # and docstrings are read through `ast`, not grep, so a sentence
            # explaining the rule cannot trip it"* (the DEF-741 shape). A full
            # `ast` walk is more than this grep needs, so the two cheap halves
            # are done instead: skip comment lines, and require `allocate` as a
            # WORD rather than as a substring of `allocates`.
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"\ballocate\b", line) or "next_number(" in line:
                callers.append(f"{path.relative_to(backend)}:{line_no}: {line.strip()}")
    assert callers == [], (
        "BR-WRK-021 / OQ-WRK-1497: nothing may allocate a dispatch batch number "
        "until the Product Owner says what a batch is — found " + " · ".join(callers)
    )


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-007 — a work order type catalogue
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_007_tc2_the_seeded_types_are_the_product_owners_own(brazos):
    """TC-2 · TC-4's data.

    ⚠ **THIS TEST ASSERTED THE EIGHT FLAT ROWS `WS-07`/`WS-26` DRAW, WITH
    r10's OWN DEFAULT PRIORITIES, UNTIL 2026-09-07.** The Product Owner
    rejected all eight — *"this is not correct - you will ahve to think from
    all Utilty services point of view"* — and supplied nine TYPES with eighteen
    SUB-TYPES beneath them (`BR-WRK-058`). The list, its two levels and the
    per-service seeding rule are covered end to end in
    `tests/test_cr070_work_order_type_levels.py`; what stays here is US-WRK-007's
    own TC-2 shape: the seeded vocabulary is present and belongs to this tenant.

    ⚠ **EVERY SEEDED ROW CARRIES THE DEFAULT PRIORITY THE SEED GIVES IT — AND
    THIS DOCSTRING SAID THE OPPOSITE UNTIL 2026-10-04 (`DEF-WRK-9613`).** It
    read *"no seeded row carries a default priority any more"* and asserted
    every `default_priority_id` was None. That was true on 2026-09-07 morning
    and stopped being true the same day, when `91377e779` gave each of the nine
    types a response time and four sub-types `URGENT` (`OQ-WRK-1765`, closed as
    a JUDGMENT; `SEED_TYPE_SPINE` and `URGENT_BEATS_ITS_PARENT` in
    `apps/work/models.py` say why). The test then went red and stayed red for
    lanes that ran only their own files. It now reads the seed's own table, so
    the next change to a seeded priority moves the seed and this test together.
    Every row is still editable on the card.
    """
    with tenant_ctx(brazos):
        rows = {row.code: row for row in work_models.WorkOrderType.objects.filter(tenant=brazos)}
    assert {code for code, row in rows.items() if row.parent_id is None} == {
        "COMPLAINT",
        "METER_MAINT",
        "PREVENTIVE",
        "CONNECTION",
        "CORRECTIVE",
        "INFRA_DEV",
        "WATER_QUALITY",
        "CONSUMER_SVC",
        "READING",
    }
    assert rows["METER_CHANGE"].parent.code == "METER_MAINT"
    seeded = {entry["code"]: entry.get("default_priority") for entry in work_models.SEED_TYPES}
    with tenant_ctx(brazos):
        held = {
            code: (row.default_priority.code if row.default_priority_id else None)
            for code, row in rows.items()
            if code in seeded
        }
    assert held == {code: seeded[code] for code in held}
    # The nine types all carry one, and the four that beat their parent are Urgent.
    assert all(held[code] is not None for code in ("COMPLAINT", "READING", "CONNECTION"))
    assert {held[code] for code in work_models.URGENT_BEATS_ITS_PARENT if code in held} <= {"URGENT"}
    assert all(row.customer_present is False for row in rows.values())


def test_us_wrk_007_tc1_a_new_type_appears_immediately(brazos):
    """TC-1 — add *Backflow test* with its default priority; it is one more."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        before = handler.count()
        row = handler.create(
            {"code": "BACKFLOW_TEST", "name": "Backflow test", "default_priority": "Normal"}
        )
        assert handler.count() == before + 1
        assert handler.serialize(row)["default_priority"] == "Normal"
        assert row.is_system is False  # a tenant's own row, deletable


def test_us_wrk_007_tc3_a_duplicate_code_is_refused(brazos):
    """TC-3 · negative — unique per tenant, whatever the capitalisation."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            handler.create({"code": "meter_change", "name": "Meter swap"})
    assert refused.value.message_key == "work.lookups.duplicate_code"


def test_us_wrk_007_tc4_a_seeded_type_is_deactivated_never_deleted(brazos):
    """TC-4 · negative — `BR-TEN-036`: the card offers *Deactivate* instead."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        row = work_models.WorkOrderType.objects.get(tenant=brazos, code="METER_CHANGE")
        with pytest.raises(errors.BizError) as refused:
            handler.delete(row)
        assert refused.value.message_key == "work.lookups.system_row_not_deletable"
        handler.set_active(row, False)
        row.refresh_from_db()
        assert row.active is False


def test_us_wrk_007_an_unknown_default_priority_is_refused_naming_the_choices(brazos):
    """The detail field is CONSTRAINED — the refusal lists what would work."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            handler.create({"code": "X", "name": "X", "default_priority": "Immediately"})
    assert refused.value.message_key == "work.types.priority_unknown"
    assert "Urgent" in refused.value.params["allowed"]


def test_us_wrk_007_tc5_tenant_isolation_lone_star_sees_only_its_own(brazos, lonestar):
    """TC-5 — the application layer's half; the database's is the `_pg` file."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        handler.create({"code": "BACKFLOW_TEST", "name": "Backflow test"})
    with tenant_ctx(lonestar):
        codes = {row.code for row in handler.search(None)}
    assert "BACKFLOW_TEST" not in codes
    assert "METER_CHANGE" in codes  # its own seeded vocabulary is there


def test_us_wrk_007_tc6_existing_free_text_is_never_guessed_at(brazos):
    """TC-6 — `work_orders.type` stays a string; `type_id` stays NULL.

    `metering/0045` adds the column and backfills NOTHING. Matching *Meter set*
    to the seeded *Meter exchange* would be a guess about a customer's data,
    which is what the story forbids in as many words.
    """
    from apps.work import connection_models as work_tables

    field = work_tables.WorkOrder._meta.get_field("type_ref")
    assert field.null is True
    assert field.db_column == "type_id"
    assert work_tables.WorkOrder._meta.get_field("type").get_internal_type() == "TextField"


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-008 — priorities, each with its SLA
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_008_tc1_the_four_seeded_priorities_and_their_hours(brazos):
    """TC-1's data — Urgent 4 h · High 8 h · Normal 72 h · Low 168 h, by rank."""
    with tenant_ctx(brazos):
        rows = list(work_models.WorkPriority.objects.filter(tenant=brazos).order_by("rank"))
    assert [(r.name, r.sla_hours, r.rank) for r in rows] == [
        ("Urgent", 4, 1),
        ("High", 8, 2),
        ("Normal", 72, 3),
        ("Low", 168, 4),
    ]


def test_us_wrk_008_the_card_shows_the_hours_with_their_unit(brazos):
    """hard rule 3 — the card's detail column reads *4 h*, not *4*.

    The unit comes from the SERVER (`sla_hours_text`), so eleven catalogues and
    three screens cannot each glue on their own.
    """
    handler = work_lookups.WorkPriorityLookupHandler()
    with tenant_ctx(brazos):
        urgent = work_models.WorkPriority.objects.get(tenant=brazos, code="URGENT")
        payload = handler.serialize(urgent)
    assert payload["sla_hours_text"] == "4 h"
    assert payload["sla_hours"] == 4  # the value is still a number underneath


def test_us_wrk_008_tc3_a_negative_sla_is_refused(brazos):
    """TC-3 · negative — a promise cannot run backwards."""
    handler = work_lookups.WorkPriorityLookupHandler()
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            handler.create({"code": "SAMEDAY", "name": "Same day", "sla_hours_text": "-1"})
    assert refused.value.message_key == "work.priorities.sla_negative"


def test_us_wrk_008_a_new_priority_takes_the_next_free_rank(brazos):
    """`rank` is unique per tenant, so the fifth priority cannot be guessed 1."""
    handler = work_lookups.WorkPriorityLookupHandler()
    with tenant_ctx(brazos):
        row = handler.create({"code": "SAMEDAY", "name": "Same day", "sla_hours_text": "12 h"})
        assert row.rank == 5
        assert row.sla_hours == 12
        # Adding a second one does not collide with the first.
        second = handler.create({"code": "NEXTDAY", "name": "Next day", "sla_hours_text": "24"})
        assert second.rank == 6


def test_us_wrk_008_tc5_tenant_isolation_on_the_sla(brazos, lonestar):
    """TC-5 — Lone Star changes its Normal; Brazos Bend's is untouched."""
    handler = work_lookups.WorkPriorityLookupHandler()
    with tenant_ctx(lonestar):
        row = work_models.WorkPriority.objects.get(tenant=lonestar, code="NORMAL")
        handler.update(row, {"sla_hours_text": "48 h"})
    with tenant_ctx(brazos):
        assert work_models.WorkPriority.objects.get(tenant=brazos, code="NORMAL").sla_hours == 72


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-009 — the three parked cards
# ══════════════════════════════════════════════════════════════════════════
def test_us_wrk_009_tc2_the_seeded_sample_copy_became_the_seeded_rows(brazos):
    """TC-2 — the card's own sample line is now a list of real rows."""
    with tenant_ctx(brazos):
        skills = _codes(work_models.WorkSkill, brazos)
        kits = _codes(work_models.WorkSafetyKit, brazos)
        categories = _codes(work_models.PartCategory, brazos)
    assert {"WATER_I", "WATER_II", "WATER_III", "ELECTRIC_I", "METER_I", "READS"} <= skills
    assert kits == {"BASIC_PPE", "LOTO", "CONFINED_SPACE", "TRAFFIC_CONTROL"}
    assert categories == {"METERS", "CONSUMABLES", "FITTINGS", "TEST_EQUIPMENT"}


def test_us_wrk_009_a_safety_kit_carries_its_contents(brazos):
    """The kit's `items`, and the one comma-separated line the card edits."""
    handler = work_lookups.WorkSafetyKitLookupHandler()
    with tenant_ctx(brazos):
        row = work_models.WorkSafetyKit.objects.get(tenant=brazos, code="CONFINED_SPACE")
        payload = handler.serialize(row)
        assert payload["items"] == ["Harness", "Gas monitor", "Tripod", "Retrieval line"]
        assert payload["items_text"] == "Harness, Gas monitor, Tripod, Retrieval line"
        handler.update(row, {"items_text": "Harness, Gas monitor"})
        row.refresh_from_db()
        assert row.items == ["Harness", "Gas monitor"]


def test_us_wrk_009_tc1_a_new_skill_appears_on_the_card(brazos):
    """TC-1 — *Backflow* is added and the card lists it."""
    handler = work_lookups.WorkSkillLookupHandler()
    with tenant_ctx(brazos):
        handler.create({"code": "BACKFLOW", "name": "Backflow"})
        assert "Backflow" in {row.name for row in handler.search(None)}


def test_us_wrk_009_tc5_tenant_isolation_on_a_new_skill(brazos, lonestar):
    """TC-5 — Lone Star adds *Chlorination*; it is absent from Brazos Bend."""
    handler = work_lookups.WorkSkillLookupHandler()
    with tenant_ctx(lonestar):
        handler.create({"code": "CHLORINATION", "name": "Chlorination"})
    with tenant_ctx(brazos):
        assert "CHLORINATION" not in {row.code for row in handler.search(None)}


def test_us_wrk_009_a_parts_category_counts_the_parts_that_use_it(brazos):
    """`BR-TEN-029` — the used-by count is LIVE, and it is what locks a delete."""
    handler = work_lookups.PartCategoryLookupHandler()
    with tenant_ctx(brazos):
        meters = work_models.PartCategory.objects.get(tenant=brazos, code="METERS")
        assert handler.used_by(meters) == 0
        work_services.create_part(
            None,
            {
                "part_no": "MTR-W58",
                "name": 'Water meter 5/8"',
                "category": "Meters",
                "unit_of_measure": "each",
                "unit_cost": "92.4000",
            },
        )
        assert handler.used_by(meters) == 1


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-010 — the parts register, and NO stock
# ══════════════════════════════════════════════════════════════════════════
def _add(part_no, name, cost, category="Meters", unit="each"):
    return work_services.create_part(
        None,
        {
            "part_no": part_no,
            "name": name,
            "category": category,
            "unit_of_measure": unit,
            "unit_cost": cost,
        },
    )


def test_us_wrk_010_tc1_stored_at_four_decimals_and_served_at_four(brazos):
    """TC-1 — `92.4000` stored; the screen shows `$92.40` (hard rule 2).

    The SERVER's job is to keep four; trimming to two is `MoneyCell`'s, once,
    at the last inch before a pair of eyes.
    """
    with tenant_ctx(brazos):
        row = _add("MTR-W58", 'Water meter 5/8"', "92.4000")
        assert row["unit_cost"] == "92.4000"
        stored = work_models.Part.objects.get(tenant=brazos, part_no="MTR-W58")
        assert stored.unit_cost == Decimal("92.4000")


def test_us_wrk_010_tc5_the_payload_carries_no_on_hand_no_reorder_at_no_location(brazos):
    """TC-5 — **asserted BY NAME**, so a lane cannot add stock quietly.

    `BR-WRK-019` and `WM-07`/`WM-22` say *"No stock levels, no reorder points"*;
    the wireframe `Work-025` draws all three columns and a reorder banner, and
    the card wins (`DEF-WRK-3550`). Whether a stock table may exist at all is
    `OQ-WRK-1490`, OPEN and routed to the Product Owner.
    """
    with tenant_ctx(brazos):
        _add("MTR-E1P", "Electric meter 1φ AMI", "96.0000")
        page = work_selectors.parts_page()
        row = page["rows"][0]
    for forbidden in ("on_hand", "reorder_at", "location"):
        assert forbidden not in row, (
            f"BR-WRK-019 / OQ-WRK-1490: GET /work/parts must not publish {forbidden!r} — "
            "the register ships without stock until the Product Owner rules"
        )
    assert set(row) == set(work_selectors.PART_ROW_KEYS)


def test_us_wrk_010_tc5_a_stock_field_is_refused_on_the_way_IN_too(brazos):
    """The other side of the same door: `POST` refuses, never ignores."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            work_services.create_part(
                None,
                {
                    "part_no": "MTR-W58",
                    "name": "Water meter",
                    "unit_of_measure": "each",
                    "unit_cost": "92.4000",
                    "on_hand": "184",
                },
            )
    assert refused.value.message_key == "work.lookups.unknown_field"


def test_us_wrk_010_tc6_the_stock_boundary_raises_naming_the_ruling_not_a_question(brazos):
    """TC-6 — the boundary says what was DECIDED, not which question it waits on.

    ⚠ **THIS CASE ASSERTED `"OQ-WRK-1490"` UNTIL 2026-09-05 AND WAS RED ON THE
    BRANCH TIP (`DEF-WRK-3937`).** `OQ-WRK-1490` was ruled on 2026-09-04 —
    option (a), the register and the issue log and no stock at all — and
    `523d3625` rewrote the stub's message to carry the ruling so that nobody has
    to look an id up to learn whether to finish it. The code moved and this
    assertion did not.

    **So the contract is asserted rather than the sentence.** An exact-string
    match would go red on a re-wording, which is the wrong thing to defend. What
    matters is that the message names the ruling and its date, and that it names
    NO open question — an id here would send the next lane hunting an answer
    that already exists, which is what the rewrite was for.
    """
    with pytest.raises(NotImplementedError) as raised:
        work_services.stock_position("any-part")
    message = str(raised.value)
    assert message.startswith("ruled 2026-09-04:"), message
    assert "no stock at all" in message, message
    assert "OQ-" not in message, (
        "the boundary must state the decision, never send a reader to a register: " + message
    )


def test_us_wrk_010_nothing_calls_the_stock_stub():
    """A stub with a caller is not a boundary — it is a broken feature.

    ⚠ **READ WITH `ast`, NOT WITH `in`.** The first draft of this test matched
    the string and went RED on the four DOCSTRINGS that explain the stub — the
    exact false positive `G78`'s own header warns about (`DEF-741`'s shape: a
    sentence explaining a rule must not trip the check that enforces it). A
    call is a `Call` node whose function is named `stock_position`; prose is
    not.
    """
    import ast
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    callers = []
    for path in sorted(backend.glob("apps/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name == "stock_position":
                callers.append(f"{path.relative_to(backend)}:{node.lineno}")
    assert callers == [], (
        "stock_position is a DELIBERATE ABSENCE (OQ-WRK-1490, ruled 2026-09-04 "
        "option (a)), not a stub to unblock — a caller means someone reached for "
        "a stock figure this product does not keep: " + " · ".join(callers)
    )


def test_us_wrk_010_tc3_a_fifth_decimal_is_refused_never_rounded(brazos):
    """TC-3 · negative — `92.40004` is REFUSED.

    Rounding it to `92.4000` would be the storage layer silently changing a
    price, which is the defect nobody finds for a year (hard rule 2).
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            _add("MTR-W58", "Water meter", "92.40004")
    assert refused.value.message_key == "work.parts.cost_places"


def test_us_wrk_010_tc4_a_part_with_no_unit_is_refused(brazos):
    """TC-4 · negative — CLAUDE.md hard rule 3, at the door."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            work_services.create_part(
                None, {"part_no": "SEAL-01", "name": "Wire seal", "unit_cost": "0.2200"}
            )
    assert refused.value.message_key == "work.lookups.required"


def test_us_wrk_010_a_negative_unit_cost_is_refused(brazos):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            _add("SEAL-01", "Wire seal", "-0.22")
    assert refused.value.message_key == "work.parts.cost_negative"


def test_us_wrk_010_a_duplicate_part_number_is_refused(brazos):
    with tenant_ctx(brazos):
        _add("SEAL-01", "Wire seal", "0.2200", category="Consumables")
        with pytest.raises(errors.ValidationError) as refused:
            _add("seal-01", "Wire seal, spare", "0.2300", category="Consumables")
    assert refused.value.message_key == "work.parts.duplicate_no"


def test_us_wrk_010_the_register_searches_part_number_and_description(brazos):
    """`Work-025`'s search box names exactly these two columns (B14 rule 19)."""
    with tenant_ctx(brazos):
        _add("MTR-W58", 'Water meter 5/8"', "92.4000")
        _add("MTR-E1P", "Electric meter 1φ AMI", "96.0000")
        _add("SEAL-01", "Wire seal", "0.2200", category="Consumables")
        by_number = work_selectors.parts_page(q="MTR")
        by_words = work_selectors.parts_page(q="seal")
    assert {row["part_no"] for row in by_number["rows"]} == {"MTR-W58", "MTR-E1P"}
    assert {row["part_no"] for row in by_words["rows"]} == {"SEAL-01"}


def test_us_wrk_010_tc6_tenant_isolation_on_the_register(brazos, lonestar):
    """TC-6 — Brazos Bend's `MTR-W58` is absent from Lone Star's register."""
    with tenant_ctx(brazos):
        _add("MTR-W58", 'Water meter 5/8"', "92.4000")
    with tenant_ctx(lonestar):
        assert work_selectors.parts_page()["rows"] == []


def test_us_wrk_010_a_cross_tenant_part_id_is_indistinguishable_from_an_absent_one(
    brazos, lonestar
):
    """hard rule 1 — *not yours* and *not there* are the same answer."""
    with tenant_ctx(brazos):
        row = _add("MTR-W58", 'Water meter 5/8"', "92.4000")
    with tenant_ctx(lonestar):
        assert work_selectors.part(row["id"]) is None
        with pytest.raises(errors.NotFoundError):
            work_services.update_part(None, row["id"], {"name": "Theirs"})


def test_us_wrk_010_editing_a_price_writes_an_audit_row_naming_both_figures(brazos, audit_rows):
    """CLAUDE.md hard rule 7 — a unit cost is money, so the change is recorded.

    Read off the BE-03 capture sink (`audit_rows`), which is where every audit
    row in this suite is asserted: the row is handed to the sink at the moment
    of the write, so this proves the SERVICE writes it rather than proving the
    audit table can be queried.
    """
    with tenant_ctx(brazos):
        row = _add("MTR-W58", 'Water meter 5/8"', "92.4000")
        work_services.update_part(None, row["id"], {"unit_cost": "94.0000"})
    created = [r for r in audit_rows if r["action"] == "work.part.created"]
    updated = [r for r in audit_rows if r["action"] == "work.part.updated"]
    assert created and created[-1]["after"]["unit_cost"] == "92.4000"
    assert updated, "hard rule 7: a price change writes an audit row"
    assert updated[-1]["before"]["unit_cost"] == "92.4000"
    assert updated[-1]["after"]["unit_cost"] == "94.0000"
