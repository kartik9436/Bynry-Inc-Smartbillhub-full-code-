# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007 §5 · US-WRK-008 §4   Question: OQ-WRK-1765, CLOSED
#           2026-09-07 as a JUDGMENT (a PO delegation, never a signature)
# Defect:   DEF-WRK-4512 (the eleven common sub-types)
# Rules:    BR-WRK-018 · BR-WRK-058 · BR-TEN-012 · CLAUDE.md law 13
# ───────────────────────────────────────────────────────
"""The default priority each job type is seeded at, and the four that beat theirs.

⚠ **WHY THIS FILE EXISTS AT ALL.** These are RESPONSE TIMES. `due_at` is stamped
from the priority at the moment an order is raised, so a wrong default is a
promise made to a customer by accident — and the specific accident this guards
is the one that costs most: **a sub-type inheriting its parent's eight hours
when the job is a gas leak.** Nothing else in the suite would notice that. The
figures are a lane's judgment recorded under a PO delegation, which is exactly
the kind of number that needs a test pinning it, because no signature does.
"""

from __future__ import annotations

from apps.work import models as work_models


def _migration(name: str):
    """One migration module by file name, imported for its pinned constant."""
    import importlib

    return importlib.import_module(f"apps.work.migrations.{name}")


COMMON = _migration("0026_br_wrk_058_common_sub_types")
PRIORITIES = _migration("0027_br_wrk_018_seed_default_priorities")


def _by_code() -> dict[str, dict]:
    return {str(entry["code"]): entry for entry in work_models.SEED_TYPES}


# ══ the judgment itself ════════════════════════════════════════════════════


def test_the_nine_types_each_carry_a_default_priority():
    """Every TYPE has one — a type with none raises an order with no due date."""
    entries = _by_code()
    for spec in work_models.SEED_TYPE_SPINE:
        code = str(spec["code"])
        assert entries[code].get("default_priority"), (
            f"{code} has no default priority, so an order raised under it gets no "
            "due date at all (BR-WRK-018) and the DUE cell draws a dash"
        )


def test_the_four_urgent_sub_types_beat_their_parent():
    """`GAS_LEAK_CALLOUT` and the other three are URGENT and their parent is not.

    ⚠ **THIS IS THE ASSERTION THE WHOLE FILE IS FOR.** `_resolve_priority` falls
    back to the TYPE's default and no further, so deleting one of these four
    keys does not fail a test that mentions gas — it silently moves a promised
    response from four hours to eight, on a gas leak.
    """
    entries = _by_code()
    for code in work_models.URGENT_BEATS_ITS_PARENT:
        spec = entries[code]
        assert spec.get("default_priority") == "URGENT", (
            f"{code} must be URGENT in its own right: it hangs under "
            f"{spec['parent_code']}, which is not, so without this it inherits "
            "the parent's slower promise by accident"
        )
        parent = entries[str(spec["parent_code"])]
        assert parent.get("default_priority") != "URGENT", (
            f"{code} is listed as BEATING its parent, but {spec['parent_code']} is "
            "itself URGENT — either the list or the parent is now wrong"
        )


def test_urgent_is_four_hours_and_the_bands_are_the_ones_put_to_the_po():
    """The hours behind the words, because the words are not the promise."""
    hours = {str(row["code"]): int(row["sla_hours"]) for row in work_models.SEED_PRIORITIES}
    assert hours == {"URGENT": 4, "HIGH": 8, "NORMAL": 72, "LOW": 168}, (
        "these four numbers are what the PO was shown in plain English; moving one "
        "moves a response time on every tenant seeded from here on"
    )


# ══ the pinned migration must not drift from the live constant ═════════════


def test_the_migration_pins_exactly_what_seed_types_carries():
    """`work/0027` writes the same mapping a new tenant is seeded with.

    ⚠ **NEITHER IS "THE" SOURCE AND THAT IS DELIBERATE** — the migration pins a
    historical fact (what was decided on 2026-09-07, for hosts that already
    exist) and `SEED_TYPES` carries the living one (what a new tenant gets).
    Pinning is right, and it is also exactly how two copies of one decision
    drift apart. This is the check that stops it.
    """
    entries = _by_code()
    pinned = {code: priority for code, _name, priority in PRIORITIES.DEFAULTS}
    live = {
        code: str(spec["default_priority"])
        for code, spec in entries.items()
        if spec.get("default_priority")
    }
    assert pinned == live, (
        "work/0027's pinned DEFAULTS and models.SEED_TYPES disagree about which "
        "priority a job type defaults to — an existing tenant and a new one would "
        "be given different response times"
    )


def test_the_migration_pins_the_seeded_names_it_matches_on():
    """It updates only rows still carrying their seeded name; the names must match."""
    entries = _by_code()
    for code, name, _priority in PRIORITIES.DEFAULTS:
        assert entries[code]["name"] == name, (
            f"work/0027 matches {code} on the name {name!r} and SEED_TYPES now says "
            f"{entries[code]['name']!r} — the migration would silently update nothing"
        )


# ══ DEF-WRK-4512 — the eleven the PO ruled common ══════════════════════════


def test_the_eleven_common_sub_types_carry_no_service_tag():
    """They are seeded to every utility, which is what *"common"* means here."""
    entries = _by_code()
    for code, _name in COMMON.COMMON_SUB_TYPES:
        assert not entries[code].get("service"), (
            f"{code} still names a service, so a utility that does not sell it "
            "would not receive the row the PO ruled common to every utility "
            "(DEF-WRK-4512)"
        )


def test_water_keeps_only_the_genuinely_water_shaped_rows():
    """Seven, not eighteen — the eleven came back out on 2026-09-07."""
    water = sorted(
        str(entry["code"])
        for entry in work_models.SEED_TYPES
        if entry.get("service") == "water"
    )
    assert water == sorted(
        [
            "LOW_PRESSURE", "NO_WATER_SUPPLY", "WATER_PRESSURE", "LEAK_REPAIRS",
            "MAIN_EXTENSION", "WATER_TRUCK", "ELECTRICAL_LINE",
        ]
    ), (
        "water's own list is no longer the seven rows that are actually about "
        "water; check whether a sub-type was re-tagged without the ruling that "
        "would justify it (OQ-WRK-1764 is the open question, not a licence)"
    )


def test_a_gas_only_utility_would_receive_nine_types_and_fifteen_sub_types():
    """The worked figure the PO was given: `9 / 4` became `9 / 15`."""
    types = [e for e in work_models.SEED_TYPES if not e.get("parent_code")]
    subs = [
        e
        for e in work_models.SEED_TYPES
        if e.get("parent_code") and e.get("service") in (None, "", "gas")
    ]
    assert len(types) == 9, f"the common spine is {len(types)} types, not nine"
    assert len(subs) == 15, (
        f"a gas-only utility would now receive {len(subs)} sub-types; the figure "
        "put to the PO was fifteen (eleven common + gas's four)"
    )
