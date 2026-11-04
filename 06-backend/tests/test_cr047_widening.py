# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (the ONE recorded ETL runner, stage 4) ·
#           US-AST-010 (the three assets targets) · US-MET-003 (units)
#           Screens: S81 (Imports) · WFL-01 stages 4–5 · AST-04 Imports tab
# Change:   CR-047 WIDENING — tasks 20 (a savepoint per record on the three
#           assets targets), 21 (the same on the generic premises/units path),
#           22 (a per-target column map for the two result CSVs), plus the
#           download refusal's own message key.
# Rules:    BR-CUS-051 CONFIRMED, verbatim — "Import mechanics = the standard:
#           staged → per-row errors → skip-errors ON → 'N created · N failed'
#           summary → 10,000-row cap" · BR-AST-033 (a duplicate asset number
#           is a hard block) · BR-AST-049 (the utility's own legacy reference
#           is unique per tenant) · BR-AST-045 (blank unit → inventory) ·
#           BR-MET-090/096 (one runner, declared rules) · BR-MET-100 (a unit
#           may load with no plan) · CLAUDE.md hard rules 1, 4, 7
# Tests:    this file · DEF-2519 (critical), the same defect on five more
#           targets
# Impacts:  apps/metering/import_runs.py
# ───────────────────────────────────────────────────────
"""CR-047 widened — **one bad row costs one row on ALL SIX targets.**

DEF-2519 was fixed for `accounts` on 2026-08-29 and left live on the other
five. Two different mechanisms, and the fix reads differently for each.

**(a) THE THREE ASSETS TARGETS — business refusals.** `_load_assets_rows`
called `seams.create_asset_from_import` / `update_asset_from_import` with no
`try`, no `except` and no savepoint anywhere in its row loop, under stage 4's
one outer `transaction.atomic()`. `apps.assets.services._create_asset_inner`
refuses by name at least nineteen ways; any one of them on row 63 of a
1,846-meter migration left ZERO meters on file.

**(b) PREMISES AND UNITS — database refusals.** The generic path in
`_load_locked` writes straight through the ORM with no guard at all. What
escapes is a unique-index or NOT NULL violation stage 3 does not model, or a
race where another user takes the same premise reference between the rehearsal
and the commit. **Here the savepoint is MANDATORY rather than tidy:** in
PostgreSQL a failed statement poisons the whole transaction, so
`except IntegrityError: continue` on its own cannot work — the next row's very
first query answers *current transaction is aborted*.

PO ruling 2026-08-29, verbatim, and it names no target:

    "if it is success then you read next record, if it is fail - you display on
    screen shich record failed and why (dont write to dB) and continue to
    uplaod next record; at the end we need 2 CsV file 1 for success record and
    other for failed records"

⚠ **THE REFUSALS HERE ARE REAL, NOT INJECTED, AND THE WAY THEY ARE PROVOKED IS
THE POINT.** Stage 3 on this branch already models every write-time refusal
that can be produced from a file alone — which is the product being in good
shape, not a reason to skip the guard. What stage 3 structurally CANNOT see is
a record that lands **after** it read the world: `_existing_index` and
`assets_import_index` are read once, at the top of stage 4, and a row written
by anybody after that point is invisible to the whole run. So each case below
lands the clashing record MID-LOOP, from the ordinary door, and the refusal
that follows is the database's or the assets validator's own — a
`uq_units_tenant_premises_label` violation, a `uq_premises_tenant_external_ref_ci`
violation, a BR-AST-049 `BizError`. That is the race the packet names, made
deterministic.

RED-FIRST PROOF, PER TARGET (hard-won law 7 — every guard was watched failing
on the defect it was written for, before it was trusted green).

**The three assets targets.** With the `except` on `_load_assets_rows`
narrowed so the refusal is not caught, all three parametrised walks failed
identically — the refusal escaping the loop and taking the whole run with it:

    apps/metering/import_runs.py:5324: in load
    apps/metering/import_runs.py:5345: in _load_apply
    apps/metering/import_runs.py:5781: in _load_locked
    apps/metering/import_runs.py:7578: in _load_assets_rows
    E   core.errors.BizError: BIZ-STATE (assets.external_ref_duplicate)
    FAILED …::test_task20__one_refused_row…[assets_meters-meters-meter-MTR-2]
    FAILED …::test_task20__one_refused_row…[assets_submeters-submeters-meter-SUB-2]
    FAILED …::test_task20__one_refused_row…[assets_devices-devices-backflow-DEV-2]

With the guard restored, each answers `created == 2`, `rejected_at_write == 1`,
and the two good assets are on file.

**Premises and units.** With the `except` on the generic path narrowed the
same way:

    apps/metering/import_runs.py:6042: in _load_locked
    E   django.db.utils.IntegrityError: UNIQUE constraint failed:
        index 'uq_premises_tenant_external_ref_ci'
    E   django.db.utils.IntegrityError: UNIQUE constraint failed:
        units.tenant_id, units.premises_id, units.label
    FAILED …::test_task21__a_premises_row_the_database_refuses_costs_one_row
    FAILED …::test_task21__a_units_row_the_database_refuses_costs_one_row

**AND THE SAVEPOINT ITSELF, WHICH IS THE HALF NO SQLITE RUN CAN SEE.** The
suite runs on in-memory sqlite (`config/settings/test.py`), and sqlite does NOT
abort a transaction on a failed statement — so `except IntegrityError: continue`
would pass there with no savepoint at all, which is exactly the shape of a
guard that is trusted and does nothing. Re-run against real PostgreSQL 16
(`DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgres://…`) with
the nested `atomic()` removed and the `except` KEPT, the refused row is caught
correctly and **the next row cannot run at all**:

    WARNING import: premises row refused by the database (sqlstate 23505):
        duplicate key value violates unique constraint
        "uq_premises_tenant_external_ref_ci"
    apps/metering/import_runs.py:6061: in _load_locked
    E   django.db.transaction.TransactionManagementError: An error occurred in
        the current transaction. You can't execute queries until the end of the
        'atomic' block.

That is the whole argument for the shape of the code, measured rather than
asserted. With the savepoint restored, all five task-21 cases pass on
PostgreSQL as well as on sqlite.
"""

import csv
import io

import pytest
from django.test import override_settings

from apps.assets import models as assets_models, services as assets_services
from apps.metering import import_runs, models as metering_models, services as metering_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    owner_for,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}


# ══════════════════════════════════════════════════════════════════════════
# THE FILES, AND THE ONE HELPER THAT RUNS THEM
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NO TARGET'S FILE QUOTES ONE OF OUR OWN NUMBERS.** Under the PO's ruling
# of 2026-08-27 a premise, unit and asset number is ISSUED by the tenant's
# series, and stage 3 rejects a row that quotes one which is not on file. So
# every file below identifies its rows the way a real migration file does —
# by the utility's OWN legacy reference — which is also what makes the
# mid-loop clash below a realistic one.

PREMISES_HEADERS = "LEGACY_KEY,ADDR1,CITY,STATE,ZIP,SVC_AVAIL"
PREMISES_MAPPING = {
    "LEGACY_KEY": "external_ref",
    "ADDR1": "address_line",
    "CITY": "city",
    "STATE": "state",
    "ZIP": "postal_code",
    "SVC_AVAIL": "services_available",
}

UNITS_HEADERS = "UNIT_REF,PREMISE_ID,UNIT_TYPE,SQFT,PLAN"
UNITS_MAPPING = {
    "UNIT_REF": "label",
    "PREMISE_ID": "premises",
    "UNIT_TYPE": "unit_type",
    "SQFT": "square_feet",
    "PLAN": "rate_plan",
}

METERS_HEADERS = "METER_NO,SERVICE,UNIT_REF,INSTALL_DT"
METERS_MAPPING = {
    "METER_NO": "external_ref",
    "SERVICE": "service",
    "UNIT_REF": "unit_ref",
    "INSTALL_DT": "install_date",
}

SUBMETERS_HEADERS = "METER_NO,SERVICE,UNIT_REF,INSTALL_DT,PARENT_MTR"
SUBMETERS_MAPPING = {**METERS_MAPPING, "PARENT_MTR": "parent_asset_no"}

# ⚠ SERVICE since 2026-09-30 — required on the devices sheet (PO ruling, plan U2).
DEVICES_HEADERS = "METER_NO,DEVICE_TYPE,SERVICE,UNIT_REF,INSTALL_DT"
DEVICES_MAPPING = {
    "METER_NO": "external_ref",
    "DEVICE_TYPE": "type",
    "SERVICE": "service",
    "UNIT_REF": "unit_ref",
    "INSTALL_DT": "install_date",
}

MAPPING_BY_TARGET = {
    import_runs.TARGET_PREMISES: PREMISES_MAPPING,
    import_runs.TARGET_UNITS: UNITS_MAPPING,
    import_runs.TARGET_ASSETS_METERS: METERS_MAPPING,
    import_runs.TARGET_ASSETS_SUBMETERS: SUBMETERS_MAPPING,
    import_runs.TARGET_ASSETS_DEVICES: DEVICES_MAPPING,
}


def _run(actor, target: str, content: str, *, write_mode: str = "insert") -> str:
    """Stages 1–3 over one file, returning the run id — the real three
    functions, never a shortcut around them."""
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": f"cr047-widening-{target}.csv",
            "content": content,
            "session_ref": "sess_cr047w",
            "write_mode": write_mode,
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": MAPPING_BY_TARGET[target], "row_handling": ALL_OFF},
    )
    import_runs.validate(actor, run["id"])
    return run["id"]


def _rows(run_id):
    return {
        row.row_no: row
        for row in metering_models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no")
    }


def _read_csv(run_id, kind):
    filename, body = import_runs.results_csv(run_id, kind)
    return filename, list(csv.reader(io.StringIO("".join(body))))


def _load(actor, run_id, **extra):
    return import_runs.load(
        actor, run_id, {"write_mode": "insert", "approved": True, **extra}
    )


# ── the mid-loop clash: another writer lands a record AFTER stage 4 read the
# world. Both hooks wrap a real per-row function of the loader, so the clash
# happens between the index read and the write of the row it clashes with —
# which is precisely the window `_existing_index` cannot see into.
def _clash_on_generic_row(monkeypatch, marker: str, land):
    """Fire `land()` the first time the generic loop maps the row whose mapped
    values contain `marker`."""
    original = import_runs._resolve_fk_columns
    state = {"fired": False}

    def _wrapped(record, mapped, target, type_ids, area_ids, owner_exact):
        if not state["fired"] and marker in str(sorted((mapped or {}).items())):
            state["fired"] = True
            land()
        return original(record, mapped, target, type_ids, area_ids, owner_exact)

    monkeypatch.setattr(import_runs, "_resolve_fk_columns", _wrapped)
    return state


def _clash_on_asset_row(monkeypatch, marker: str, land):
    """The same, for the assets loop — `_asset_payload_from` is its per-row
    map and runs before the write of the row it belongs to."""
    original = import_runs._asset_payload_from
    state = {"fired": False}

    def _wrapped(target, mapped):
        if not state["fired"] and marker in str(sorted((mapped or {}).items())):
            state["fired"] = True
            land()
        return original(target, mapped)

    monkeypatch.setattr(import_runs, "_asset_payload_from", _wrapped)
    return state


# ══════════════════════════════════════════════════════════════════════════
# THE WORLDS EACH TARGET NEEDS BEFORE ITS FILE CAN LOAD
# ══════════════════════════════════════════════════════════════════════════
def _premises_file() -> str:
    return (
        f"{PREMISES_HEADERS}\n"
        "LEG-1,1 Bluestem Ln,Katy,TX,77494,electric\n"
        "LEG-2,2 Bluestem Ln,Katy,TX,77494,electric\n"
        "LEG-3,3 Bluestem Ln,Katy,TX,77494,electric\n"
    )


def _units_world(actor) -> str:
    """One premises, so the units file has a parent to name."""
    created = make_premises(actor, services_available=["electric"])
    return metering_models.Premises.objects.get(pk=created["id"]).premise_no


def _units_file(premise_no: str) -> str:
    return (
        f"{UNITS_HEADERS}\n"
        f"CR047-A,{premise_no},APT,980,\n"
        f"CR047-B,{premise_no},APT,1040,\n"
        f"CR047-C,{premise_no},APT,860,\n"
    )


def _assets_world(actor, count: int = 3):
    """`count` units on one electric premises, each carrying a service point —
    everything BR-AST-045 and BR-MET-119 need before a meter may be created."""
    premises = make_premises(actor, services_available=["electric"])
    units = []
    for index in range(count):
        unit = make_unit(actor, premises["id"], label=f"CR047W Unit {index}")
        metering_services.ensure_service_point(unit["id"], "electric")
        units.append(unit)
    return premises, units


def _meters_file(units) -> str:
    lines = [METERS_HEADERS]
    for index, unit in enumerate(units, start=1):
        lines.append(f"MTR-{index},electric,{unit['unit_no']},2024-03-0{index}")
    return "\n".join(lines) + "\n"


def _submeters_file(units, master_ref: str) -> str:
    lines = [SUBMETERS_HEADERS]
    for index, unit in enumerate(units, start=1):
        lines.append(f"SUB-{index},electric,{unit['unit_no']},2024-03-0{index},{master_ref}")
    return "\n".join(lines) + "\n"


def _devices_file(units) -> str:
    lines = [DEVICES_HEADERS]
    for index, unit in enumerate(units, start=1):
        # electric: the only service this world's premises offer (plan U5).
        lines.append(f"DEV-{index},backflow,electric,{unit['unit_no']},2024-03-0{index}")
    return "\n".join(lines) + "\n"


def _master_meter(actor, unit, external_ref: str):
    """A master meter that is ON FILE **and ACTIVE**, which is what
    `AST.PARENT_ON_FILE` asks of a sub-meter's parent. An inventory spare is on
    file and is not active, and a sub-meter naming one is rejected at stage 3 —
    so a fixture that made one would have tested nothing at all here."""
    return assets_services.create_asset(
        actor,
        {
            "type": "meter",
            "external_ref": external_ref,
            "service": "electric",
            "unit": "kWh",
            "unit_id": str(unit["id"]),
            "install_date": "2024-01-01",
        },
    )


def _land_asset(actor, external_ref: str, type_code: str = "meter"):
    """Create ONE asset through the ordinary door — the "another user" half of
    the race. It carries the file row's own legacy reference, which BR-AST-049
    makes unique per tenant."""

    def _land():
        assets_services.create_asset(
            actor,
            {
                "type": type_code,
                "external_ref": external_ref,
                "service": "electric",
                "unit": "kWh",
            },
        )

    return _land


# ══════════════════════════════════════════════════════════════════════════
# TASK 20 — a savepoint per record on the three assets targets
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "target,build,type_code,ref",
    [
        (import_runs.TARGET_ASSETS_METERS, "meters", "meter", "MTR-2"),
        (import_runs.TARGET_ASSETS_SUBMETERS, "submeters", "meter", "SUB-2"),
        (import_runs.TARGET_ASSETS_DEVICES, "devices", "backflow", "DEV-2"),
    ],
)
def test_task20__one_refused_row_costs_one_row_and_not_the_migration(
    brazos, dana, monkeypatch, target, build, type_code, ref
):
    """⛔ **DEF-2519 ON THE THREE ASSETS TARGETS.**

    Three rows. Between the index read and the write of row 2, another user
    lands an asset carrying row 2's own legacy reference — so BR-AST-049's
    hard block refuses that row inside `_create_asset_inner`, which is exactly
    the refusal that used to escape the loop and take the file with it.

    Here it costs one row: the other two assets are on file, the run is
    `loaded`, and the refused row wrote nothing at all.
    """
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana, count=4 if build == "submeters" else 3)
        if build == "submeters":
            master = _master_meter(dana, units[-1], "MASTER-1")
            content = _submeters_file(units[:-1], master["asset_no"])
        elif build == "devices":
            content = _devices_file(units)
        else:
            content = _meters_file(units)
        run_id = _run(dana, target, content)

        before = set(
            assets_models.Asset.objects.filter(tenant_id=brazos.id).values_list("id", flat=True)
        )
        state = _clash_on_asset_row(monkeypatch, ref, _land_asset(dana, ref, type_code))
        receipt = _load(dana, run_id)
        assert state["fired"], "the mid-loop clash never landed — the test proves nothing"

        assert receipt["counts"]["created"] == 2
        assert receipt["counts"]["rejected_at_write"] == 1
        assert receipt["receipt"]["rejected_at_write"] == 1

        rows = _rows(run_id)
        assert rows[1].outcome in ("loaded", "flagged")
        assert rows[2].outcome == "rejected"
        assert rows[3].outcome in ("loaded", "flagged")
        # The refused row created nothing, so it has nothing to roll back.
        assert rows[2].created_record_id is None
        # ⚠ AND NOTHING IT WOULD HAVE WRITTEN IS ON FILE — the PO's *"dont
        # write to dB"*. The one extra asset is the clash we landed ourselves.
        landed = (
            assets_models.Asset.objects.filter(tenant_id=brazos.id)
            .exclude(id__in=before)
            .count()
        )
        assert landed == 3, "two rows loaded plus the one the race landed"

        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.status == "loaded"


def test_task20__the_refused_row_leaves_no_audit_row_behind(brazos, dana, monkeypatch, audit_rows):
    """The audit write sits INSIDE the savepoint, so a rolled-back row cannot
    leave a record of an asset that does not exist."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana)
        run_id = _run(dana, import_runs.TARGET_ASSETS_METERS, _meters_file(units))
        _clash_on_asset_row(monkeypatch, "MTR-2", _land_asset(dana, "MTR-2"))
        _load(dana, run_id)

        created = [row for row in audit_rows if row.get("action") == "assets.created_by_import"]
        assert len(created) == 2, "two assets were created by the import, so two audit rows"


def test_task20__the_counters_only_count_rows_that_actually_landed(brazos, dana, monkeypatch):
    """⚠ **THE COUNTERS MOVE AFTER THE WRITE, NEVER BEFORE IT.** `unit_tagged`,
    `to_inventory` and `numbers_issued_from_series` were incremented on the way
    INTO the create branch, which was harmless while a refusal killed the run
    and is a lie the moment one does not: a receipt reading *"3 tagged to a
    unit"* over 2 assets is the invisible failure this change exists to
    remove."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana)
        run_id = _run(dana, import_runs.TARGET_ASSETS_METERS, _meters_file(units))
        _clash_on_asset_row(monkeypatch, "MTR-2", _land_asset(dana, "MTR-2"))
        counts = _load(dana, run_id)["counts"]

        assert counts["created"] == 2
        assert counts["unit_tagged"] == 2
        assert counts["to_inventory"] == 0
        assert counts["numbers_issued_from_series"] == 2
        assert counts["unit_tagged"] + counts["to_inventory"] == counts["created"]


def test_task20__a_refused_row_says_why_in_english_and_what_to_do_next(
    brazos, dana, monkeypatch
):
    """PO: *"you display on screen shich record failed and why"*. An operator
    cannot tell — and should not have to — which side of a module boundary
    refused their row, so an assets refusal reads exactly like the four the
    loader already handled."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana)
        run_id = _run(dana, import_runs.TARGET_ASSETS_METERS, _meters_file(units))
        _clash_on_asset_row(monkeypatch, "MTR-2", _land_asset(dana, "MTR-2"))
        _load(dana, run_id)

        refused = _rows(run_id)[2]
        assert refused.outcome == "rejected"
        assert refused.problem, "a rejected row with no reason is a number with no explanation"
        assert refused.fix_hint, "and one with no next step is a dead end"
        # The operator's OWN reference is the noun — it is the only identifier
        # this row has, because our number is issued at the write.
        assert "MTR-2" in refused.problem
        # ⚠ NO IDS, NO CODES, NO UUIDS — CR-016's no-internal-references rule.
        text = f"{refused.problem} {refused.fix_hint}"
        assert "BIZ-" not in text and "VAL-" not in text
        assert "BR-AST" not in text
        assert str(units[1]["id"]) not in text


def test_task20__an_unmapped_refusal_key_still_gets_an_operator_sentence(
    brazos, dana, monkeypatch
):
    """⚠ **A GAP IN THE SENTENCE TABLE MAY NOT PRODUCE A BLANK ROW.** A refusal
    whose `message_key` nobody has written words for falls back to its catalog
    CLASS, and never to `params.detail` — rendering that free text is exactly
    what DEF-322 ruled out."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana, count=1)
        run_id = _run(dana, import_runs.TARGET_ASSETS_METERS, _meters_file(units))

        def _refuses(**kwargs):
        # This raise is the SUBJECT of the case: a refusal whose message_key
        # nobody has written words for. core/refusal_catalogue refuses exactly
        # that under the test settings, so it is turned off for this block —
        # the guard and the case are asking the same question from opposite
        # sides, and this is the one place the unresolved key is deliberate.
            with override_settings(REFUSAL_KEYS_MUST_RESOLVE=False):
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="BR-AST-999",
                    message_key="assets.a_rule_nobody_wrote_words_for",
                    params={"detail": "internal diagnostic that must not be shown"},
                )

        monkeypatch.setattr(import_runs.seams, "create_asset_from_import", _refuses)
        receipt = _load(dana, run_id)

        assert receipt["counts"]["rejected_at_write"] == 1
        row = _rows(run_id)[1]
        assert row.problem and row.fix_hint
        assert "internal diagnostic" not in f"{row.problem} {row.fix_hint}"
        assert "meter" in f"{row.problem} {row.fix_hint}"


def test_task20__a_system_fault_rejects_its_row_and_no_longer_takes_the_run_down(
    brazos, dana, monkeypatch
):
    """⛔ **SUPERSEDED 2026-09-30 BY THE PO (`DEF-AST-8102`, GO with its steps):
    *"a non-rule exception on ONE row rejects that row with its reason and the
    load continues"*.** This case asserted the opposite — that a `SysError`
    takes the whole run down — and that posture is exactly how an asset upload
    over the 200-row bar lost every row to one role refusal. What still holds:
    nothing is WRITTEN for a refused row (its savepoint rolls back, law 14),
    every refused row is COUNTED and SAYS so, and the fault is logged with its
    traceback for support. The unwired-module case below is unchanged: it is
    raised outside the per-row `try` and still aborts the run."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana, count=2)
        run_id = _run(dana, import_runs.TARGET_ASSETS_METERS, _meters_file(units))

        def _broken(**kwargs):
            with override_settings(REFUSAL_KEYS_MUST_RESOLVE=False):
                raise errors.SysError(
                    errors.SYS_INTERNAL, message_key="assets.numbering_unavailable"
                )

        monkeypatch.setattr(import_runs.seams, "create_asset_from_import", _broken)
        receipt = _load(dana, run_id)

        assert receipt["counts"]["rejected_at_write"] == 2
        assert all(row.outcome == "rejected" and row.problem for row in _rows(run_id).values())
        assert not assets_models.Asset.objects.filter(
            tenant_id=brazos.id, external_ref__in=("MTR-1", "MTR-2")
        ).exists()


def test_task20__an_unwired_assets_module_still_aborts_the_whole_run(brazos, dana, monkeypatch):
    """⚠ **`_refuse_assets_unwired()` IS RAISED OUTSIDE THE `try`, ON PURPOSE.**
    It is a `BizError` too, and catching it would turn *"the assets module
    cannot answer at all"* into 1,846 politely-rejected rows — a migration
    reported as fully judged when nothing was ever asked. That is DEF-075's
    shape."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana, count=2)
        run_id = _run(dana, import_runs.TARGET_ASSETS_METERS, _meters_file(units))
        monkeypatch.setattr(
            import_runs.seams, "create_asset_from_import", lambda **kwargs: None
        )
        with pytest.raises(errors.BizError) as caught:
            _load(dana, run_id)
        assert caught.value.message_key == "metering.import.assets_unwired"


# ══════════════════════════════════════════════════════════════════════════
# TASK 21 — the same on the generic premises/units path
# ══════════════════════════════════════════════════════════════════════════
def test_task21__a_premises_row_the_database_refuses_costs_one_row(
    brazos, dana, monkeypatch
):
    """⛔ **DEF-2519 ON THE PREMISES TARGET, AND THE SAVEPOINT IS MANDATORY
    HERE RATHER THAN TIDY.**

    Between the index read and the write of row 2, another user lands a
    premises carrying row 2's own legacy reference — so
    `uq_premises_tenant_external_ref_ci` refuses it, from PostgreSQL, which
    poisons the transaction. Without the savepoint the run does not merely
    lose row 2: every row after it fails too, on *current transaction is
    aborted*.
    """
    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())

        def _land():
            metering_services.create_premises(
                dana,
                {
                    "owner_id": owner_for(dana),
                    "address_line": "Landed mid-run",
                    "external_ref": "LEG-2",
                },
            )

        state = _clash_on_generic_row(monkeypatch, "LEG-2", _land)
        receipt = _load(dana, run_id)
        assert state["fired"], "the mid-loop clash never landed — the test proves nothing"

        assert receipt["counts"]["created"] == 2
        assert receipt["counts"]["rejected_at_write"] == 1
        assert receipt["receipt"]["rejected_at_write"] == 1

        rows = _rows(run_id)
        assert rows[1].outcome in ("loaded", "flagged")
        assert rows[2].outcome == "rejected"
        assert rows[3].outcome in ("loaded", "flagged"), "the row AFTER the refusal still loaded"
        addresses = set(
            metering_models.Premises.objects.filter(tenant_id=brazos.id).values_list(
                "address_line", flat=True
            )
        )
        assert "1 Bluestem Ln" in addresses and "3 Bluestem Ln" in addresses
        assert "2 Bluestem Ln" not in addresses, "the refused row must have written nothing"


def test_task21__a_units_row_the_database_refuses_costs_one_row(brazos, dana, monkeypatch):
    """The same on the units target, over `uq_units_tenant_premises_label` —
    the constraint that makes *"one premises cannot hold two units with the
    same label"* structural rather than promised."""
    with tenant_ctx(brazos):
        premise_no = _units_world(dana)
        run_id = _run(dana, import_runs.TARGET_UNITS, _units_file(premise_no))
        premises_id = str(
            metering_models.Premises.objects.get(
                tenant_id=brazos.id, premise_no=premise_no
            ).pk
        )

        def _land():
            metering_services.create_unit(dana, {"premises_id": premises_id, "label": "CR047-B"})

        state = _clash_on_generic_row(monkeypatch, "CR047-B", _land)
        receipt = _load(dana, run_id)
        assert state["fired"], "the mid-loop clash never landed — the test proves nothing"

        assert receipt["counts"]["created"] == 2
        assert receipt["counts"]["rejected_at_write"] == 1

        rows = _rows(run_id)
        assert rows[2].outcome == "rejected"
        assert rows[3].outcome in ("loaded", "flagged"), "the row AFTER the refusal still loaded"
        labels = set(
            metering_models.Unit.objects.filter(
                tenant_id=brazos.id, premises_id=premises_id
            ).values_list("label", flat=True)
        )
        assert {"CR047-A", "CR047-B", "CR047-C"} == labels
        assert (
            metering_models.Unit.objects.filter(
                tenant_id=brazos.id, premises_id=premises_id, label="CR047-B"
            ).count()
            == 1
        ), "the refused row must have written nothing"


def test_task21__the_sentence_names_the_operators_own_cell_and_no_constraint(
    brazos, dana, monkeypatch
):
    """⚠ **A `psycopg` ERROR STRING IS NOT A SENTENCE A CLERK CAN ACT ON.** The
    raw text is *duplicate key value violates unique constraint
    "uq_premises_tenant_external_ref_ci"* — a constraint name, a table name and
    a column name, none of which are on the operator's spreadsheet and all of
    which are the internal references CR-016 rules out."""
    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())

        def _land():
            metering_services.create_premises(
                dana,
                {
                    "owner_id": owner_for(dana),
                    "address_line": "Landed mid-run",
                    "external_ref": "LEG-2",
                },
            )

        _clash_on_generic_row(monkeypatch, "LEG-2", _land)
        _load(dana, run_id)

        refused = _rows(run_id)[2]
        assert refused.problem and refused.fix_hint
        text = f"{refused.problem} {refused.fix_hint}"
        # The row's own identifying cell — its address, which is what they typed.
        assert "2 Bluestem Ln" in refused.problem
        assert "already on file" in refused.problem
        # NOTHING from the driver, and no uuid.
        for leak in ("uq_", "duplicate key", "psycopg", "constraint", "DETAIL", "premises_id"):
            assert leak not in text, f"the operator was shown {leak!r}"


def test_task21__an_operational_fault_still_takes_the_whole_run_down(
    brazos, dana, monkeypatch
):
    """⛔ **THE OTHER HALF OF TASK 21.** The `except` names `IntegrityError` and
    `DataError` — the database saying *"this ROW's data is wrong"* — and not
    `Exception`. An `OperationalError` is the server or the connection, it will
    refuse every row that follows in the same way, and a run reporting *"9,881
    failed"* over a dropped connection would be a data-quality report about an
    outage."""
    from django.db import OperationalError

    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())
        original = import_runs._resolve_fk_columns

        def _wrapped(record, mapped, target, type_ids, area_ids, owner_exact):
            if "2 Bluestem Ln" in str(sorted((mapped or {}).items())):
                raise OperationalError("the server went away")
            return original(record, mapped, target, type_ids, area_ids, owner_exact)

        monkeypatch.setattr(import_runs, "_resolve_fk_columns", _wrapped)
        with pytest.raises(OperationalError):
            _load(dana, run_id)

        assert not metering_models.Premises.objects.filter(
            tenant_id=brazos.id, address_line="1 Bluestem Ln"
        ).exists()


def test_task21__the_number_is_taken_refusal_is_still_a_run_level_abort(
    brazos, dana, monkeypatch
):
    """⚠ **`_refuse_if_number_taken` IS CALLED OUTSIDE THE SAVEPOINT, ON
    PURPOSE**, and its own docstring is the reason: *"IT RAISES, WHICH TAKES
    THE WHOLE TRANSACTION. That is deliberate and it is the safe direction."*
    It fires when the tenant's series and the table have genuinely come apart,
    which is true of every row that follows and not just of this one."""
    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())

        def _taken(target, record, number_field, row_no):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-TEN-035",
                message_key="metering.import.issued_number_taken",
                params={"row": row_no},
            )

        monkeypatch.setattr(import_runs, "_refuse_if_number_taken", _taken)
        with pytest.raises(errors.BizError) as caught:
            _load(dana, run_id)
        assert caught.value.message_key == "metering.import.issued_number_taken"


# ══════════════════════════════════════════════════════════════════════════
# TASK 22 — one column set per target
# ══════════════════════════════════════════════════════════════════════════
def test_task22__every_target_declares_its_own_successes_columns():
    """Six entries, one per member of `TARGETS`. A target with no entry would
    fall back to the ACCOUNTS columns and hand a premises operator five empty
    account columns — worse than no file, because it reads as *"nothing
    landed"*."""
    assert set(import_runs.SUCCESS_COLUMNS_BY_TARGET) == set(import_runs.TARGETS)
    for target, columns in import_runs.SUCCESS_COLUMNS_BY_TARGET.items():
        assert columns, target
        assert len(set(columns)) == len(columns), f"{target} declares a column twice"
        for column in columns:
            assert column == column.lower()
            assert " " not in column


def test_task22__the_accounts_columns_are_unchanged():
    """The accounts half of CR-047 shipped and was reviewed; widening the map
    must not move it."""
    assert import_runs.SUCCESS_COLUMNS_BY_TARGET[import_runs.TARGET_ACCOUNTS] == (
        "account_number",
        "customer_name",
        "unit_reference",
        "opening_balance_total",
        "services_inherited",
    )


def test_task22__the_premises_successes_file_names_what_landed(brazos, dana):
    """The premise number the SERIES issued (it is not on their file at all),
    the address they typed, the services the premises now offers, and the
    owner — blank when there is none, which is the PO's 2026-08-27 ruling and
    the one thing that makes a blank-owner premises findable."""
    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())
        _load(dana, run_id)

        filename, rows = _read_csv(run_id, "successes")
        assert filename.endswith("-successes.csv")
        assert rows[0] == ["premise_number", "address", "city", "services_offered", "owner"]
        assert len(rows) == 4
        first = rows[1]
        assert first[0], "the number the series issued — never blank on a loaded row"
        assert first[1] == "1 Bluestem Ln"
        assert first[2] == "Katy"
        assert first[3] == "electric"


def test_task22__the_units_successes_file_names_its_premises_and_its_plan(brazos, dana):
    """For a unit: which unit landed, under what number, at which premises, on
    what plan. **A blank plan cell is BR-MET-100's ruled-lawful state** — *"a
    unit with no plan does not fail — it simply never appears on a bill"* — and
    naming those units is what makes the receipt's count reviewable."""
    with tenant_ctx(brazos):
        premise_no = _units_world(dana)
        run_id = _run(dana, import_runs.TARGET_UNITS, _units_file(premise_no))
        _load(dana, run_id)

        _filename, rows = _read_csv(run_id, "successes")
        assert rows[0] == ["unit_number", "unit_label", "premises_reference", "rate_plan"]
        assert len(rows) == 4
        assert rows[1][0], "the number the series issued"
        assert rows[1][1] == "CR047-A"
        assert rows[1][2] == premise_no
        assert rows[1][3] == "", "no plan on the file, so no plan claimed"


@pytest.mark.parametrize(
    "target,build,columns",
    [
        (
            import_runs.TARGET_ASSETS_METERS,
            "meters",
            # ⛔ The six-group order and the new/💲 fields since 2026-09-30
            # (plan U8, PO: every downloaded file follows the plan order).
            list(import_runs.SUCCESS_COLUMNS_BY_TARGET[import_runs.TARGET_ASSETS_METERS]),
        ),
        (
            import_runs.TARGET_ASSETS_SUBMETERS,
            "submeters",
            list(import_runs.SUCCESS_COLUMNS_BY_TARGET[import_runs.TARGET_ASSETS_SUBMETERS]),
        ),
        (
            import_runs.TARGET_ASSETS_DEVICES,
            "devices",
            list(import_runs.SUCCESS_COLUMNS_BY_TARGET[import_runs.TARGET_ASSETS_DEVICES]),
        ),
    ],
)
def test_task22__the_assets_successes_files_name_what_landed(
    brazos, dana, target, build, columns
):
    """The asset number our series issued, what kind of thing it is, the unit
    it was seated on and what it measures. **The number cannot come from
    anywhere but the writer** — under the 2026-08-27 ruling it is not on the
    operator's file at all."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana, count=3 if build == "submeters" else 2)
        if build == "submeters":
            master = _master_meter(dana, units[-1], "MASTER-9")
            content = _submeters_file(units[:-1], master["asset_no"])
        elif build == "devices":
            content = _devices_file(units)
        else:
            content = _meters_file(units)
        run_id = _run(dana, target, content)
        _load(dana, run_id)

        _filename, rows = _read_csv(run_id, "successes")
        # `DEF-AST-8363`: the header prints the template's LABELS; `columns`
        # (the internal keys) is still what each cell is looked up by.
        assert rows[0] == import_runs.success_headers(target)
        assert len(rows[0]) == len(columns)
        assert len(rows) == 3
        assert rows[1][0], "the number the series issued — never blank on a loaded row"
        assert rows[1][1], "the kind of asset, in the tenant's own words"
        cells = dict(zip(columns, rows[1]))
        assert cells["unit_assigned"] == units[0]["label"], "the unit it was seated on"
        if build == "submeters":
            assert cells["master_meter"] == master["asset_no"], "the master it was hung on"


def test_task22__the_failures_file_is_the_original_row_plus_exactly_two_columns(
    brazos, dana, monkeypatch
):
    """⛔ **THE RULE THAT DOES NOT CHANGE PER TARGET.** The operator's next act
    is to fix the rows and upload again, so the rejects come back under the
    FILE'S OWN headers, in the FILE'S OWN order, carrying the ROW'S OWN cells,
    with `why_it_failed` and `how_to_fix_it` appended and nothing else."""
    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())

        def _land():
            metering_services.create_premises(
                dana,
                {
                    "owner_id": owner_for(dana),
                    "address_line": "Landed mid-run",
                    "external_ref": "LEG-2",
                },
            )

        _clash_on_generic_row(monkeypatch, "LEG-2", _land)
        _load(dana, run_id)

        filename, rows = _read_csv(run_id, "failures")
        assert filename.endswith("-failures.csv")
        assert rows[0] == [*PREMISES_HEADERS.split(","), "why_it_failed", "how_to_fix_it"]
        assert len(rows) == 2
        failed = rows[1]
        assert failed[: len(PREMISES_HEADERS.split(","))] == [
            "LEG-2",
            "2 Bluestem Ln",
            "Katy",
            "TX",
            "77494",
            "electric",
        ]
        assert failed[-2] and failed[-1]


def test_task22__the_two_files_partition_every_targets_run(brazos, dana, monkeypatch):
    """Every row a run holds comes out of exactly one of the two files. A row
    in neither would be DEF-016's silently-dropped row; one in both would
    double-count a migration."""
    with tenant_ctx(brazos):
        _premises, units = _assets_world(dana)
        run_id = _run(dana, import_runs.TARGET_ASSETS_METERS, _meters_file(units))
        _clash_on_asset_row(monkeypatch, "MTR-2", _land_asset(dana, "MTR-2"))
        _load(dana, run_id)

        _f1, successes = _read_csv(run_id, "successes")
        _f2, failures = _read_csv(run_id, "failures")
        assert (len(successes) - 1) + (len(failures) - 1) == 3
        assert metering_models.ImportRunRow.objects.filter(run_id=run_id).count() == 3


def test_task22__a_row_loaded_before_this_change_still_produces_a_file(brazos, dana):
    """⚠ **A HISTORICAL RUN RECORDED NO `LOAD_RESULT` AND MUST NOT CRASH THE
    DOWNLOAD.** Every cell falls back to an empty one — *"the run did not
    say"* — which is `receipt()`'s own posture for a figure a run predates."""
    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())
        _load(dana, run_id)
        # Strip what the loader recorded, exactly as a pre-CR-047 run carries.
        for row in metering_models.ImportRunRow.objects.filter(run_id=run_id):
            mapped = dict(row.mapped or {})
            mapped.pop(import_runs.LOAD_RESULT, None)
            row.mapped = mapped
            row.save(update_fields=["mapped", "updated_at"])

        _filename, rows = _read_csv(run_id, "successes")
        assert rows[0] == ["premise_number", "address", "city", "services_offered", "owner"]
        assert len(rows) == 4
        # The address survives because `mapped` still carries the operator's
        # own cell; the number does not, and an empty cell is the honest
        # answer rather than a claim.
        assert rows[1][1] == "1 Bluestem Ln"


# ══════════════════════════════════════════════════════════════════════════
# THE DOWNLOAD REFUSAL'S OWN KEY
# ══════════════════════════════════════════════════════════════════════════
def test_the_download_refusal_no_longer_borrows_the_rollback_doors_sentence(brazos, dana):
    """⛔ **SAME PREDICATE, DIFFERENT SENTENCE.** Both doors ask
    `run.status != "loaded"` and carry `BR-MET-090`; until this lane they also
    shared `metering.import.not_loaded`, whose English ends *"…so there is
    nothing to reverse."* That is right at the rollback door and wrong on a
    download, where an operator asking for a result file is not trying to
    reverse anything.

    ⚠ **THE KIND CHANGED FROM `failures` TO `successes` UNDER `DEF-2487`**, and
    the sentence this case is about did not. The failures half is now served
    from `validated` onward — an operator whose commit failed needs the list of
    what failed, and stage 3 has already written it — so the *"has not been
    loaded"* refusal is now the successes half's alone, which is the half it was
    always describing.
    """
    with tenant_ctx(brazos):
        run_id = _run(dana, import_runs.TARGET_PREMISES, _premises_file())
        with pytest.raises(errors.BizError) as caught:
            import_runs.results_csv(run_id, "successes")
        assert caught.value.message_key == "metering.import.not_loaded_no_download"
        assert caught.value.br_ref == "BR-MET-090"
