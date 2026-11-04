"""`DEF-MET-10164` — Premises and Units lists show Created; imports may carry it.

PO ruling 2026-10-17 (decision log, *"PREMISES AND UNITS LISTS SHOW CREATED +
AGE; IMPORT MAY CARRY THE ORIGINAL CREATED DATE"*), the server half:

1. both list rows SERVE `created_at`, and both lists SORT on `created` in both
   directions (the Created and Age headers send the same sort);
2. Created is stamped by the system and no screen can edit it;
3. a premises or units import may carry an optional Created column — blank is
   the import day, a future or unreadable date refuses THAT row with a short
   reason, the others land;
4. a re-import carrying only the number and Created corrects the Created date
   of the record it names and nothing else, each change audited old → new;
5. tenant scoped (hard rule 1).

Worked figure from the ruling: 101 Silver Creek Rd, `03/14/1996` → Created
03/14/1996 (and Age 30 yrs 7 mos on 10/17/2026 — the age arithmetic is the
screen's, pinned in `07-frontend/src/features/metering/recordAge.test.ts`).

⚠ **RUN ON POSTGRESQL** (hard-won law 14): the load writes Created with a
follow-up `.update()` inside a per-row SAVEPOINT, and the dates-only path takes
its own savepoint — exactly the shape SQLite cannot prove.
"""

from datetime import date, datetime, timedelta

import pytest

from apps.metering import api, import_runs, models, seams
from apps.metering import selectors
from core import tenancy as core_tenancy

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    audit_rows,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_cr023_import_stages import ALL_ON

pytestmark = pytest.mark.django_db


def _backdate(model, pk, day: date) -> None:
    zone = seams.tenant_timezone()
    model.objects.filter(pk=pk).update(
        created_at=datetime.combine(day, datetime.min.time(), tzinfo=zone)
    )


def _local_day(moment) -> date:
    return moment.astimezone(seams.tenant_timezone()).date()


def _run(actor, target, content, mapping, write_mode="insert"):
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": f"{target}_created_case.csv",
            "content": content,
            "session_ref": "sess_10164",
            "ip": "71.42.108.14",
            "write_mode": write_mode,
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": ALL_ON})
    import_runs.validate(actor, run["id"])
    return run["id"]


def _load(actor, run_id, write_mode="insert"):
    return import_runs.load(actor, run_id, {"write_mode": write_mode, "approved": True})


def _rows_by_no(run_id) -> dict[int, models.ImportRunRow]:
    return {row.row_no: row for row in models.ImportRunRow.objects.filter(run_id=run_id)}


PREMISES_MAPPING = {"ADDRESS": "address_line", "CITY": "city", "CREATED": "created_at"}


# ═══════════════════════════════════════════════════════════════════════════
# 1 · SERVED AND SORTED
# ═══════════════════════════════════════════════════════════════════════════


def test_both_list_rows_serve_created_at(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="101 Silver Creek Rd")
        unit = make_unit(dana, premise["id"])
        _backdate(models.Premises, premise["id"], date(1996, 3, 14))
        _backdate(models.Unit, unit["id"], date(2015, 6, 1))
    listed = api_call(api.premises, "get", user=FakeUser(), role="system_admin", tenant=brazos)
    row = next(r for r in listed.data["results"] if r["id"] == premise["id"])
    with tenant_ctx(brazos):
        assert _local_day(datetime.fromisoformat(row["created_at"])) == date(1996, 3, 14)
    units = api_call(api.units, "get", user=FakeUser(), role="system_admin", tenant=brazos)
    urow = next(r for r in units.data["results"] if r["id"] == unit["id"])
    with tenant_ctx(brazos):
        # the UNIT's own date, not its building's
        assert _local_day(datetime.fromisoformat(urow["created_at"])) == date(2015, 6, 1)


def test_created_is_a_declared_sort_on_both_lists():
    assert selectors.PREMISES_SORTS["created"] == "created_at"
    assert selectors.UNIT_SORTS["created"] == "created_at"
    # the defaults did not move
    assert selectors.PREMISES_DEFAULT_SORT == "premise_no"
    assert selectors.UNIT_DEFAULT_SORT == "unit_no"


def test_premises_sort_by_created_both_directions(brazos, dana):
    days = [date(2010, 1, 1), date(1996, 3, 14), date(2001, 6, 1)]
    ids = []
    with tenant_ctx(brazos):
        for index, day in enumerate(days):
            made = make_premises(dana, address_line=f"{index} Sort Ln")
            _backdate(models.Premises, made["id"], day)
            ids.append(made["id"])
    for direction, expected in (("asc", [1, 2, 0]), ("desc", [0, 2, 1])):
        listed = api_call(
            api.premises,
            "get",
            user=FakeUser(),
            role="system_admin",
            tenant=brazos,
            query={"sort": "created", "dir": direction, "per": 100},
        )
        order = [r["id"] for r in listed.data["results"] if r["id"] in ids]
        assert order == [ids[i] for i in expected], direction


def test_units_sort_by_created_both_directions(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="7 Unit Sort Rd")
        ids = []
        for index, day in enumerate([date(2015, 1, 1), date(1999, 1, 1), date(2020, 1, 1)]):
            made = make_unit(dana, premise["id"], label=f"Apt {index}")
            _backdate(models.Unit, made["id"], day)
            ids.append(made["id"])
    for direction, expected in (("asc", [1, 0, 2]), ("desc", [2, 0, 1])):
        listed = api_call(
            api.units,
            "get",
            user=FakeUser(),
            role="system_admin",
            tenant=brazos,
            query={"sort": "created", "dir": direction, "per": 100},
        )
        order = [r["id"] for r in listed.data["results"] if r["id"] in ids]
        assert order == [ids[i] for i in expected], direction


# ═══════════════════════════════════════════════════════════════════════════
# 2 · NO SCREEN EDITS IT
# ═══════════════════════════════════════════════════════════════════════════


def test_edit_premise_and_edit_unit_cannot_move_created(brazos, dana):
    from apps.metering import services

    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="9 Fixed Date Way")
        unit = make_unit(dana, premise["id"])
        before_p = models.Premises.objects.get(pk=premise["id"]).created_at
        before_u = models.Unit.objects.get(pk=unit["id"]).created_at
        for call, pk in (
            (services.update_premises, premise["id"]),
            (services.update_unit, unit["id"]),
        ):
            try:
                call(dana, pk, {"created_at": "1990-01-01T00:00:00+00:00"})
            except Exception:  # noqa: BLE001 — a refusal is also "cannot edit"
                pass
        assert models.Premises.objects.get(pk=premise["id"]).created_at == before_p
        assert models.Unit.objects.get(pk=unit["id"]).created_at == before_u


# ═══════════════════════════════════════════════════════════════════════════
# 3 · IMPORT MAY CARRY CREATED
# ═══════════════════════════════════════════════════════════════════════════


def test_import_premises_with_created_blank_iso_future_and_unreadable(brazos, dana):
    with tenant_ctx(brazos):
        today = seams.tenant_today()
        future = (today + timedelta(days=30)).strftime("%m/%d/%Y")
        content = (
            "ADDRESS,CITY,CREATED\n"
            "101 Silver Creek Rd,Katy,03/14/1996\n"
            "102 Silver Creek Rd,Katy,\n"
            "103 Silver Creek Rd,Katy,2001-06-01\n"
            f"104 Silver Creek Rd,Katy,{future}\n"
            "105 Silver Creek Rd,Katy,14/03/1996\n"
        )
        run_id = _run(dana, "premises", content, PREMISES_MAPPING)
        rows = _rows_by_no(run_id)
        assert rows[4].outcome == "rejected"
        assert rows[4].problem == "Date is in the future."
        assert rows[5].outcome == "rejected"
        assert rows[5].problem == "14/03/1996 is not MM/DD/YYYY."
        assert rows[5].fix_hint == "Use MM/DD/YYYY."
        _load(dana, run_id)
        by_address = {
            p.address_line: p
            for p in models.Premises.objects.filter(address_line__startswith="10")
            if "Silver Creek" in p.address_line
        }
        assert set(by_address) == {
            "101 Silver Creek Rd",
            "102 Silver Creek Rd",
            "103 Silver Creek Rd",
        }
        assert _local_day(by_address["101 Silver Creek Rd"].created_at) == date(1996, 3, 14)
        assert _local_day(by_address["102 Silver Creek Rd"].created_at) == today
        assert _local_day(by_address["103 Silver Creek Rd"].created_at) == date(2001, 6, 1)


def test_import_accepts_the_timestamp_our_own_export_writes(brazos, dana):
    with tenant_ctx(brazos):
        run_id = _run(
            dana,
            "premises",
            "ADDRESS,CITY,CREATED\n201 Round Trip Rd,Katy,1996-03-14T00:00:00-06:00\n",
            PREMISES_MAPPING,
        )
        _load(dana, run_id)
        made = models.Premises.objects.get(address_line="201 Round Trip Rd")
        assert _local_day(made.created_at) == date(1996, 3, 14)


def test_units_import_carries_the_units_own_created(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="300 Older Unit Ave")
        _backdate(models.Premises, premise["id"], date(1996, 3, 14))
        premise_no = models.Premises.objects.get(pk=premise["id"]).premise_no
        run_id = _run(
            dana,
            "units",
            f"PREMISE_ID,UNIT_REF,CREATED\n{premise_no},Apt 1,06/01/2015\n{premise_no},Apt 2,\n",
            {"PREMISE_ID": "premises", "UNIT_REF": "label", "CREATED": "created_at"},
        )
        _load(dana, run_id)
        apt1 = models.Unit.objects.get(premises_id=premise["id"], label="Apt 1")
        apt2 = models.Unit.objects.get(premises_id=premise["id"], label="Apt 2")
        assert _local_day(apt1.created_at) == date(2015, 6, 1)
        assert _local_day(apt2.created_at) == seams.tenant_today()


def test_the_template_offers_created_as_an_optional_date_column(brazos):
    with tenant_ctx(brazos):
        for target in ("premises", "units"):
            column = next(
                c for c in import_runs.target_columns(target) if c["target"] == "created_at"
            )
            assert column["label"] == "Created"
            assert column["kind"] == import_runs.KIND_DATE
            assert column["required"] is False
            assert column["blank_means"] == "the import day"
            assert column.get("sample") == ""


# ═══════════════════════════════════════════════════════════════════════════
# 4 · RE-IMPORT CORRECTS CREATED ONLY, AUDITED OLD → NEW
# ═══════════════════════════════════════════════════════════════════════════


def test_reimport_number_and_created_updates_only_the_date_and_audits(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="400 Correction Rd", city="Katy")
        row = models.Premises.objects.get(pk=premise["id"])
        before_created = row.created_at
        before = {
            f: getattr(row, f)
            for f in ("address_line", "city", "owner_id", "status", "premise_no", "updated_at")
        }
        run_id = _run(
            dana,
            "premises",
            f"PREMISE_ID,CREATED\n{row.premise_no},03/14/1996\n",
            {"PREMISE_ID": "premise_no", "CREATED": "created_at"},
            write_mode="upsert",
        )
        assert _rows_by_no(run_id)[1].outcome != "rejected", _rows_by_no(run_id)[1].problem
        receipt = _load(dana, run_id, "upsert")
        row.refresh_from_db()
        assert _local_day(row.created_at) == date(1996, 3, 14)
        assert {f: getattr(row, f) for f in before} == before  # nothing else moved
        assert receipt["counts"]["created_dates_corrected"] == 1
        corrected = [r for r in audit_rows if r["action"] == "premises.created_date_corrected"]
        assert len(corrected) == 1
        assert corrected[0]["entity_id"] == row.pk or str(corrected[0]["entity_id"]) == str(row.pk)
        assert corrected[0]["before"]["created_at"] == before_created.isoformat()
        assert corrected[0]["after"]["created_at"].startswith("1996-03-14T00:00:00")
        assert corrected[0]["actor_user_id"] is not None


def test_a_number_and_created_file_maps_itself_by_its_plain_headers(brazos):
    """Found by the walk (W8): a file headed `Premise ID,Created` mapped only
    the date, read as a Created column alone and was refused at stage 2 for a
    missing address. The plain spellings now auto-detect."""
    with tenant_ctx(brazos):
        assert import_runs._auto_map(["Premise ID", "Created"], "premises") == {
            "Premise ID": "premise_no",
            "Created": "created_at",
        }
        assert import_runs._auto_map(["Unit No", "Created"], "units") == {
            "Unit No": "unit_no",
            "Created": "created_at",
        }


def test_reimport_dates_only_under_insert_changes_nothing(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="401 Insert Mode Rd")
        row = models.Premises.objects.get(pk=premise["id"])
        before = row.created_at
        run_id = _run(
            dana,
            "premises",
            f"PREMISE_ID,CREATED\n{row.premise_no},03/14/1996\n",
            {"PREMISE_ID": "premise_no", "CREATED": "created_at"},
        )
        _load(dana, run_id, "insert")
        row.refresh_from_db()
        assert row.created_at == before
        assert _rows_by_no(run_id)[1].outcome == "rejected"


def test_reimport_units_dates_only_by_unit_number(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="402 Unit Fix Rd")
        unit = make_unit(dana, premise["id"])
        row = models.Unit.objects.get(pk=unit["id"])
        plan_before, label_before = row.rate_plan_id, row.label
        run_id = _run(
            dana,
            "units",
            f"UNIT_NO,CREATED\n{row.unit_no},2015-06-01\n",
            {"UNIT_NO": "unit_no", "CREATED": "created_at"},
            write_mode="upsert",
        )
        assert _rows_by_no(run_id)[1].outcome != "rejected", _rows_by_no(run_id)[1].problem
        _load(dana, run_id, "upsert")
        row.refresh_from_db()
        assert _local_day(row.created_at) == date(2015, 6, 1)
        assert (row.rate_plan_id, row.label) == (plan_before, label_before)
        assert [r["action"] for r in audit_rows].count("unit.created_date_corrected") == 1


def test_rerunning_the_same_correction_writes_no_second_audit_row(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="403 Twice Rd")
        number = models.Premises.objects.get(pk=premise["id"]).premise_no
        # The SAME day written two ways — two different files (a byte-identical
        # second file is refused as already loaded, hard rule 6), one date.
        for written in ("03/14/1996", "1996-03-14"):
            run_id = _run(
                dana,
                "premises",
                f"PREMISE_ID,CREATED\n{number},{written}\n",
                {"PREMISE_ID": "premise_no", "CREATED": "created_at"},
                write_mode="upsert",
            )
            _load(dana, run_id, "upsert")
        actions = [r["action"] for r in audit_rows]
        assert actions.count("premises.created_date_corrected") == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5 · TENANT SCOPED
# ═══════════════════════════════════════════════════════════════════════════


def test_another_utility_cannot_correct_this_utilitys_date(brazos, dana, lonestar, erin):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="500 Mine Rd")
        row = models.Premises.objects.get(pk=premise["id"])
        before = row.created_at
        number = row.premise_no
    with tenant_ctx(lonestar):
        run_id = _run(
            erin,
            "premises",
            f"PREMISE_ID,CREATED\n{number},03/14/1996\n",
            {"PREMISE_ID": "premise_no", "CREATED": "created_at"},
            write_mode="upsert",
        )
        # the number is not on file FOR THIS UTILITY, so the row is refused
        assert _rows_by_no(run_id)[1].outcome == "rejected"
        _load(erin, run_id, "upsert")
    with tenant_ctx(brazos):
        row.refresh_from_db()
        assert row.created_at == before
    assert core_tenancy.current_tenant_id() is None
