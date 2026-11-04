# ── Trace ──────────────────────────────────────────────
# Story:    CR-036 (i) — 9,881 premises imported with `services_available`
#           mapped and Matched, and every row landed with NO services.
#           Screens: WFL-01.premises.2/4, PRM-01
# Rules:    BR-MET-003 (services ⊆ tenant-enabled) · BR-MET-088 (the REAL
#           target columns) · BR-MET-090 (stage 4 writes what stage 2 mapped)
# ───────────────────────────────────────────────────────
"""CR-036 (i) — the mapped column must reach the created row."""

import csv
import io

import pytest

from apps.metering import import_runs, models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db


OTTUMWA_HEADERS = [
    "premise_no",
    "address_line",
    "city",
    "state",
    "postal_code",
    "services_available",
]

OTTUMWA_MAPPING = {name: name for name in OTTUMWA_HEADERS}

ALL_ON = {
    "drop_exact_duplicates": True,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}


@pytest.fixture()
def ottumwa(growth_plan, identity_seam):  # noqa: F405
    """The PO's own tenant: Water · Sewer · Trash, and nothing else."""
    tenant, _result = provisioned_tenant(
        brazosbend_payload(
            name="Ottumwa Water Works",
            subdomain="ottumwa-water-works",
            services=["water", "sewer", "trash"],
            owner={
                "full_name": "Ops Owner",
                "email": "owner@ottumwa-water-works.test",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def ottumwa_admin(ottumwa):
    return staff_actor(ottumwa, "system_admin", "admin@ottumwa-water-works.test")


def _csv(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(OTTUMWA_HEADERS)
    for row in rows:
        writer.writerow([row[header] for header in OTTUMWA_HEADERS])
    return buffer.getvalue()


def ottumwa_csv():
    return _csv(
        [
            {
                "premise_no": f"P-{10000 + index}",
                "address_line": f"{index} Court St",
                "city": "Ottumwa",
                "state": "IA",
                "postal_code": "52501",
                "services_available": "water,sewer,trash",
            }
            for index in range(3)
        ]
    )


def _load(actor, *, content=None, mapping=None):
    run = import_runs.extract(
        actor,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": "ottumwa_premises.csv",
            "content": ottumwa_csv() if content is None else content,
            "session_ref": "sess_cr036",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": mapping or OTTUMWA_MAPPING, "row_handling": ALL_ON},
    )
    import_runs.validate(actor, run["id"])
    receipt = import_runs.load(actor, run["id"], {"write_mode": "insert", "approved": True})
    return run, receipt


def test_cr036_i__a_mapped_services_column_reaches_the_created_premises(ottumwa, ottumwa_admin):
    """The PO's report, reduced to three rows: `services_available` is mapped
    and Matched at stage 2, and every created premises must carry the three
    codes the file gave it. `No services` on PRM-01 is this assertion failing.
    """
    with tenant_ctx(ottumwa):
        assert set(tenancy_models.Service.objects.values_list("code", flat=True)) >= {
            "water",
            "sewer",
            "trash",
        }
        _run, receipt = _load(ottumwa_admin)
        created = list(
            models.Premises.objects.filter(deleted_at__isnull=True).order_by("premise_no")
        )
        assert [row.premise_no for row in created] == ["P-10000", "P-10001", "P-10002"], receipt
        for row in created:
            assert sorted(row.services_available or []) == ["sewer", "trash", "water"], (
                f"{row.premise_no} landed with services_available="
                f"{row.services_available!r} — PRM-01 draws this as 'No services'"
            )


# ═══════════════════════════════════════════════════════════════════════════
# THE GENERAL GUARD — every mapped target must REACH the created row
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **DEF-542 IS WHY THIS IS GENERAL AND NOT ABOUT SERVICES.** The mapped area
# was checked at stage 3 and silently dropped at stage 4: *"a migration would
# lose every district assignment while every rule reported green."* The fix
# resolved AREA. Nothing was written that would notice the NEXT column to go
# the same way — which is exactly what CR-036 (i) reports about services.
#
# So the property asserted here is the one that covers all of them: **offer a
# column in the stage-2 picker and it must arrive on the row stage 4 creates.**
# A column that cannot demonstrate that is either a bug or must not be offered
# (BR-MET-088's own rule, in the other direction).

#: target → the attribute the value must be visible on afterwards. Anything not
#: named here is read back under its own name.
LANDS_ON = {
    "premises_type": "premises_type_id",
    "area": "area_id",
    "premises": "premises_id",
    "rate_plan": "rate_plan_id",
}

#: Offered targets deliberately NOT exercised, each with the reason. Keeping the
#: list here (rather than skipping quietly) is what makes an addition visible.
NOT_EXERCISED = {
    "custom_data",  # expanded per DEFINED custom field; this tenant defines none
}


def _cell_for(target: str, entry: dict, model) -> str:
    """One truthful cell for an offered column, chosen by its declared KIND and
    — for the plain-text fallback — by what the COLUMN actually holds."""
    kind = entry["kind"]
    if kind == import_runs.KIND_LOOKUP:
        return {"premises_type": "single_family", "unit_type": "residential"}[target]
    if kind == import_runs.KIND_LIST:
        return "water,sewer"
    if kind == import_runs.KIND_AREA:
        return "Guard District"
    if kind == import_runs.KIND_ENUM:
        return "active"
    if kind == import_runs.KIND_BOOLEAN3:
        return "inside"
    if kind == import_runs.KIND_BOOLEAN:
        return "yes"
    if kind == import_runs.KIND_INTEGER:
        return "980"
    if kind == import_runs.KIND_DATE:
        return "2026-01-01"
    if kind == import_runs.KIND_PREMISE_REF:
        return "P-20001"
    if kind == import_runs.KIND_PLAN_REF:
        return "guard-plan"
    field = model._meta.get_field(target)
    internal = field.get_internal_type()
    if internal in ("DecimalField", "FloatField"):
        return "30.123456"
    if internal in ("IntegerField", "BigIntegerField", "SmallIntegerField"):
        return "7"
    if internal == "BooleanField":
        return "yes"
    if internal == "DateField":
        return "2026-01-01"
    return f"Guard {target}"


def _guard_columns(target: str, model):
    return [
        entry
        for entry in import_runs.target_columns(target)
        if entry["target"] != import_runs.IGNORE
        and not entry.get("custom_field")
        and entry["target"] not in NOT_EXERCISED
    ]


def _guard_world(actor):
    """An area, a published plan and a parent premise — the three things a
    tenant-specific column resolves against."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    if not tenancy_models.Area.objects.filter(
        tenant_id=core_tenant_id(), name="Guard District"
    ).exists():
        tenancy_models.Area.objects.create(
            tenant_id=core_tenant_id(), name="Guard District", code="guarddist"
        )
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant_id=core_tenant_id(),
        name="Guard Plan",
        defaults={"code": "guard-plan", "status": "published"},
    )
    for code in ("water", "sewer"):
        service = tenancy_models.Service.objects.get(code=code)
        tariff, _ = rating_models.Tariff.objects.get_or_create(
            tenant_id=core_tenant_id(), name=f"Guard — {code}", service=service
        )
        rating_models.PlanRateSchedule.objects.get_or_create(
            tenant_id=core_tenant_id(), rate_plan=plan, service=service, defaults={"tariff": tariff}
        )
    return plan


def core_tenant_id():
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


def _guard_run(actor, target: str, model, extra: dict | None = None):
    columns = _guard_columns(target, model)
    row = {entry["target"]: _cell_for(entry["target"], entry, model) for entry in columns}
    row.update(extra or {})
    headers = [entry["target"] for entry in columns]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerow([row[header] for header in headers])
    content = buffer.getvalue()

    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": f"guard_{target}.csv",
            "content": content,
            "session_ref": "sess_guard",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": {header: header for header in headers}, "row_handling": ALL_ON},
    )
    validated = import_runs.validate(actor, run["id"])
    import_runs.load(actor, run["id"], {"write_mode": "insert", "approved": True})
    return columns, validated


def _assert_every_column_landed(columns, created, model):
    dropped = []
    for entry in columns:
        attribute = LANDS_ON.get(entry["target"], entry["target"])
        value = getattr(created, attribute, "<no such attribute>")
        if value in (None, "", [], {}, "<no such attribute>"):
            dropped.append(f"{entry['target']} (kind={entry['kind']}) → {attribute}={value!r}")
    assert not dropped, (
        "these stage-2 targets were offered, mapped and Matched, and did NOT reach "
        "the row stage 4 created:\n  " + "\n  ".join(dropped)
    )


def test_cr036__every_mapped_premises_target_reaches_the_created_row(ottumwa, ottumwa_admin):
    """DEF-542's lesson, generalised: an offered column that a file maps must
    be visible on the premises the load creates."""
    with tenant_ctx(ottumwa):
        _guard_world(ottumwa_admin)
        columns, validated = _guard_run(
            ottumwa_admin, "premises", models.Premises, extra={"premise_no": "P-20001"}
        )
        created = models.Premises.objects.filter(premise_no="P-20001").first()
        assert created is not None, f"the guard row did not load at all: {validated}"
        _assert_every_column_landed(columns, created, models.Premises)


def test_cr036__every_mapped_units_target_reaches_the_created_row(ottumwa, ottumwa_admin):
    """The same property on the OTHER target — the one CR-036's amendment says
    to check second."""
    with tenant_ctx(ottumwa):
        _guard_world(ottumwa_admin)
        _guard_run(ottumwa_admin, "premises", models.Premises, extra={"premise_no": "P-20001"})
        columns, validated = _guard_run(
            ottumwa_admin, "units", models.Unit, extra={"label": "Guard Unit"}
        )
        created = models.Unit.objects.filter(label="Guard Unit").first()
        assert created is not None, f"the guard unit did not load at all: {validated}"
        _assert_every_column_landed(columns, created, models.Unit)


# ═══════════════════════════════════════════════════════════════════════════
# CR-036 (iii) · IS `Insert & update` REACHABLE FOR A ROW ALREADY ON FILE?
# ═══════════════════════════════════════════════════════════════════════════
#
# The PO's re-import reported `ROWS CHECKED 9881 · PASSED CLEAN 0 · ERRORS 0 ·
# WARNINGS 9881`, every warning being `PRM.ADDRESS_ON_FILE` (action **Skip on
# load**) and the premise-ID-on-file flag. If `skip_on_load` were performed at
# stage 4, the advice *"re-run in Insert & update"* would be unreachable for
# every row it exists to serve. This measures which it is.


def _second_run_services():
    return _csv(
        [
            {
                "premise_no": f"P-{10000 + index}",
                "address_line": f"{index} Court St",
                "city": "Ottumwa",
                "state": "IA",
                "postal_code": "52501",
                "services_available": "water",
            }
            for index in range(3)
        ]
    )


def test_cr036_iii__a_second_run_in_upsert_updates_rows_already_on_file(ottumwa, ottumwa_admin):
    """Run the same premise IDs twice: the second run carries `water` alone and
    is committed in `upsert`. What the row holds afterwards is the answer.
    """
    with tenant_ctx(ottumwa):
        _load(ottumwa_admin)
        before = models.Premises.objects.get(premise_no="P-10000")
        assert sorted(before.services_available) == ["sewer", "trash", "water"]

        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "ottumwa_premises_again.csv",
                "content": _second_run_services(),
                "session_ref": "sess_cr036b",
                "ip": "71.42.108.14",
            },
        )
        import_runs.transform(
            ottumwa_admin,
            run["id"],
            {"mapping": OTTUMWA_MAPPING, "row_handling": ALL_ON},
        )
        validated = import_runs.validate(ottumwa_admin, run["id"])
        rules = {r["code"]: r for r in validated["rules"]}
        assert validated["counts"]["errors"] == 0, validated["counts"]
        assert rules["PRM.ADDRESS_ON_FILE"]["hits"] == 3, rules["PRM.ADDRESS_ON_FILE"]
        # ⛔ **WAS `skip_on_load` UNTIL DEF-750.** The rule's declared action is
        # now the one the loader PERFORMS — the row loads and is flagged. The
        # behaviour below this line has not changed by one row; only the
        # sentence the screen prints about it has.
        assert rules["PRM.ADDRESS_ON_FILE"]["action"] == "flag_only"

        receipt = import_runs.load(
            ottumwa_admin, run["id"], {"write_mode": "upsert", "approved": True}
        )
        after = models.Premises.objects.get(premise_no="P-10000")
        assert after.services_available == ["water"], (
            "the `Skip on load` action fired: the upsert never reached the row. "
            f"row holds {after.services_available!r}; receipt={receipt}"
        )
        assert (
            models.Premises.objects.filter(deleted_at__isnull=True).count() == 3
        ), "the second run duplicated rows instead of updating them"


# ═══════════════════════════════════════════════════════════════════════════
# CR-036 (a) · A US UTILITY'S DATES — `M/D/YYYY`
# ═══════════════════════════════════════════════════════════════════════════
#
# The PO's UNIT import rejected 9,881 of 9,881 rows on one rule —
# `Every value has to be the kind of value its column holds` · Reject row —
# with `1/1/2026 is not a date this import can read.` on every line.
#
# ⚠ **THE AMBIGUITY IS THE WHOLE PROBLEM AND IT IS NOT RESOLVED BY SNIFFING.**
# `3/4/2026` is 4 March in most of the world and 3 April in the United States,
# and NEITHER READING ERRORS. So the format is never inferred from the string:
# stage 2 reads ISO 8601, and — beside it — the format THIS TENANT DECLARES in
# its own regional settings (`tenant_settings.date_format`, BR-TEN-020, the S8
# Regional screen, defaulted to `MM/DD/YYYY` at provisioning). A token that is
# neither is still refused, and the refusal now NAMES the format we tried, so
# an operator can see which statement of theirs we read.

UNIT_HEADERS = ["label", "premises", "plan_effective_from"]


def _units_csv(effective_from: str):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(UNIT_HEADERS)
    writer.writerow(["Unit A", "P-10000", effective_from])
    return buffer.getvalue()


def _units_run(actor, effective_from: str):
    run = import_runs.extract(
        actor,
        {
            "target": "units",
            "source_kind": "file",
            "file_name": "ottumwa_units.csv",
            "content": _units_csv(effective_from),
            "session_ref": "sess_cr036c",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": {name: name for name in UNIT_HEADERS}, "row_handling": ALL_ON},
    )
    return import_runs.validate(actor, run["id"])


def test_cr036_a__a_us_utilitys_m_d_yyyy_date_is_read(ottumwa, ottumwa_admin):
    """`1/1/2026` in a US tenant's file loads as 2026-01-01 — the tenant's own
    declared `MM/DD/YYYY` is what reads it, never a guess about the string."""
    with tenant_ctx(ottumwa):
        from apps.tenancy import selectors as tenancy_selectors

        _load(ottumwa_admin)
        assert tenancy_selectors.regional_settings()["date_format"] == "MM/DD/YYYY"

        validated = _units_run(ottumwa_admin, "1/1/2026")
        parse_rule = next(r for r in validated["rules"] if r["code"] == "UNT.VALUES_PARSE")
        assert parse_rule["hits"] == 0, (
            "a US utility's own date format was refused by its own import: "
            f"{validated['rejects']}"
        )
        import_runs.load(ottumwa_admin, validated["id"], {"write_mode": "insert", "approved": True})
        unit = models.Unit.objects.get(label="Unit A")
        assert unit.plan_effective_from.isoformat() == "2026-01-01"


def test_cr036_a__iso_8601_keeps_working_unchanged(ottumwa, ottumwa_admin):
    """The format every existing file and the shipped sample use."""
    with tenant_ctx(ottumwa):
        _load(ottumwa_admin)
        validated = _units_run(ottumwa_admin, "2026-04-01")
        parse_rule = next(r for r in validated["rules"] if r["code"] == "UNT.VALUES_PARSE")
        assert parse_rule["hits"] == 0, validated["rejects"]
        import_runs.load(ottumwa_admin, validated["id"], {"write_mode": "insert", "approved": True})
        assert models.Unit.objects.get(label="Unit A").plan_effective_from.isoformat() == (
            "2026-04-01"
        )


def test_cr036_a__a_date_in_neither_format_is_still_refused_and_names_the_format(
    ottumwa, ottumwa_admin
):
    """⚠ The coercion must not become a sniffer. `01 Jan 2026` is neither ISO
    nor this tenant's declared format, so it is REFUSED — and the refusal says
    which format we read, because an operator cannot fix what we do not name.
    """
    with tenant_ctx(ottumwa):
        _load(ottumwa_admin)
        validated = _units_run(ottumwa_admin, "01 Jan 2026")
        parse_rule = next(r for r in validated["rules"] if r["code"] == "UNT.VALUES_PARSE")
        assert parse_rule["hits"] == 1, validated["rules"]
        hint = validated["rejects"][0]["fix_hint"]
        assert "MM/DD/YYYY" in hint, hint


def test_cr036_a__the_format_table_covers_every_format_a_tenant_can_declare():
    """⚠ Law 1 — the comment on `DATE_FORMAT_PATTERNS` claims its keys are
    `apps.tenancy.services.DATE_FORMATS` verbatim. This is that claim asserted.
    A key spelled differently is not a wrong date, it is a setting the importer
    silently cannot read while the tenant goes on seeing it on screen.
    """
    from apps.tenancy.services import DATE_FORMATS

    assert set(import_runs.DATE_FORMAT_PATTERNS) == set(DATE_FORMATS)


@pytest.mark.parametrize(
    ("token", "declared", "expected"),
    [
        ("2026-04-01", "MM/DD/YYYY", "2026-04-01"),  # ISO wins wherever it appears
        ("2026-04-01", None, "2026-04-01"),  # …and with nothing declared at all
        ("1/1/2026", "MM/DD/YYYY", "2026-01-01"),
        ("01/02/2026", "MM/DD/YYYY", "2026-01-02"),  # ⚠ US reading
        ("01/02/2026", "DD/MM/YYYY", "2026-02-01"),  # ⚠ the SAME token, the other day
        ("01.02.2026", "DD.MM.YYYY", "2026-02-01"),
        ("25-Aug-26", "DD-MMM-YY", "2026-08-25"),
        ("01/02/2026", None, None),  # nothing declared → NEVER guessed
        ("01/02/2026", "YYYY-MM-DD", None),  # declared ISO → the slashes stay unread
        ("01 Jan 2026", "MM/DD/YYYY", None),  # in neither format → refused
        ("13/13/2026", "MM/DD/YYYY", None),  # not a real day in the declared format
    ],
)
def test_cr036_a__the_date_parser_reads_iso_and_the_declared_format_and_nothing_else(
    token, declared, expected
):
    """`01/02/2026` appears twice on purpose: it is 2 January to a US utility
    and 1 February to most of the world, **and neither reading raises**. That
    is why the tenant's declaration is the only thing allowed to settle it.
    """
    assert import_runs._parse_date(token, declared) == expected


def test_cr036_a__a_mismatch_names_both_sides_the_setting_and_the_value(ottumwa, ottumwa_admin):
    """**BR-MET-117 (2)** — PO verbatim: *"you setting says this data format and
    you have given differnt and it does not match"*. Both halves in one
    sentence, in the clerk's words.
    """
    with tenant_ctx(ottumwa):
        _load(ottumwa_admin)
        validated = _units_run(ottumwa_admin, "01 Jan 2026")
        reject = validated["rejects"][0]
        assert reject["problem"] == (
            "Your settings say dates are written MM/DD/YYYY, and this row has "
            "01 Jan 2026, which does not match."
        ), reject["problem"]
        assert "MM/DD/YYYY" in reject["fix_hint"]
        assert "Settings" in reject["fix_hint"]
        # ⚠ and the message it SUPERSEDES is gone in both halves.
        assert "is not a date this import can read" not in reject["problem"]
        assert reject["fix_hint"] != "Use YYYY-MM-DD — 2026-04-01."


def test_cr036_a__a_tenant_with_no_declared_format_is_refused_never_guessed_for(
    ottumwa, ottumwa_admin
):
    """⚠ The consequence of BR-MET-117 (1) that the ruling did NOT settle, and
    it is a REFUSAL. Provisioning defaults the format so this should be
    unreachable — `should be unreachable` being the assumption this repo keeps
    being caught by, and the column is nullable.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(ottumwa):
        _load(ottumwa_admin)
        tenancy_models.TenantSettings.objects.filter(tenant_id=ottumwa.id).update(date_format=None)
        validated = _units_run(ottumwa_admin, "1/1/2026")
        parse_rule = next(r for r in validated["rules"] if r["code"] == "UNT.VALUES_PARSE")
        assert parse_rule["hits"] == 1, "an unset format must refuse, never pick one"
        assert "has not chosen a date format" in validated["rejects"][0]["problem"]


def test_cr036_a__stage_2_serves_the_format_and_the_column_it_could_not_read(
    ottumwa, ottumwa_admin
):
    """**BR-MET-117 (3)** — the backend half of *"when date matching happen at
    transform level - show the format - and in case any issue highlight it
    there itself"*. Stage 2's own answer carries the declared format and the
    per-column problem; nothing waits for stage 3 to reveal it.
    """
    with tenant_ctx(ottumwa):
        _load(ottumwa_admin)
        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": "units",
                "source_kind": "file",
                "file_name": "ottumwa_units.csv",
                "content": _units_csv("01 Jan 2026"),
                "session_ref": "sess_cr036d",
                "ip": "71.42.108.14",
            },
        )
        transformed = import_runs.transform(
            ottumwa_admin,
            run["id"],
            {"mapping": {name: name for name in UNIT_HEADERS}, "row_handling": ALL_ON},
        )
        spec = transformed["mapping_spec"]
        assert spec["date_format"] == "MM/DD/YYYY"
        assert spec["column_problems"] == [
            {
                "source_column": "plan_effective_from",
                "target": "plan_effective_from",
                "rows": 1,
                "first_row": 1,
                "example": "01 Jan 2026",
                "problem": (
                    "Your settings say dates are written MM/DD/YYYY, and this row "
                    "has 01 Jan 2026, which does not match."
                ),
                "fix_hint": (
                    "Write these cells as MM/DD/YYYY, or change the format in "
                    "Settings › Regional."
                ),
            }
        ], spec["column_problems"]
        # …and a file the tenant's format CAN read leaves the list empty, so an
        # empty list means "read clean", never "not computed".
        clean = import_runs.extract(
            ottumwa_admin,
            {
                "target": "units",
                "source_kind": "file",
                "file_name": "ottumwa_units_ok.csv",
                "content": _units_csv("1/1/2026"),
                "session_ref": "sess_cr036e",
                "ip": "71.42.108.14",
            },
        )
        ok = import_runs.transform(
            ottumwa_admin,
            clean["id"],
            {"mapping": {name: name for name in UNIT_HEADERS}, "row_handling": ALL_ON},
        )
        assert ok["mapping_spec"]["column_problems"] == []
        assert ok["mapping_spec"]["date_format"] == "MM/DD/YYYY"


def test_cr036_a__the_mapping_picker_tells_the_operator_what_a_date_is_read_as(
    ottumwa, ottumwa_admin
):
    """The other half of (3): `GET /imports/{id}/columns` — the stage-2 picker —
    carries the format on every DATE column, so the screen can print it BEFORE
    the operator commits to the mapping."""
    with tenant_ctx(ottumwa):
        for target in ("units", "assets_meters", "accounts"):
            dates = [
                entry
                for entry in import_runs.target_columns(target)
                if entry["kind"] == import_runs.KIND_DATE
            ]
            assert dates, f"{target} offers no date column — this test would pass vacuously"
            for entry in dates:
                assert entry["date_format"] == "MM/DD/YYYY", (target, entry)


def test_cr036_i__a_mapped_column_that_is_empty_in_every_row_is_said_out_loud(
    ottumwa, ottumwa_admin
):
    """CR-036 (i)'s shape, made VISIBLE at the stage it can still be fixed.

    A file carrying a `services_available` header with every cell empty maps,
    marks `Matched`, validates with zero errors and loads 3 premises reading
    `No services` — the PO's report exactly. Nothing in the run said so before
    this. ⚠ **PROPOSED, not ruled** — it is reported and never acted on.
    """
    with tenant_ctx(ottumwa):
        blank = _csv(
            [
                {
                    "premise_no": f"P-{10000 + index}",
                    "address_line": f"{index} Court St",
                    "city": "Ottumwa",
                    "state": "IA",
                    "postal_code": "52501",
                    "services_available": "",
                }
                for index in range(3)
            ]
        )
        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "ottumwa_premises_blank_services.csv",
                "content": blank,
                "session_ref": "sess_cr036f",
                "ip": "71.42.108.14",
            },
        )
        transformed = import_runs.transform(
            ottumwa_admin,
            run["id"],
            {"mapping": OTTUMWA_MAPPING, "row_handling": ALL_ON},
        )
        assert transformed["mapping_spec"]["empty_columns"] == [
            {"source_column": "services_available", "target": "services_available", "rows": 3}
        ], transformed["mapping_spec"]["empty_columns"]

        # …and it stays SILENT everywhere else: zero errors, three rows loaded,
        # every one of them with no services. That is the state the notice is
        # the only warning about.
        validated = import_runs.validate(ottumwa_admin, run["id"])
        assert validated["counts"]["errors"] == 0
        import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert", "approved": True})
        assert [
            row.services_available
            for row in models.Premises.objects.filter(deleted_at__isnull=True)
        ] == [[], [], []]


def test_cr036_i__a_column_that_carried_values_is_NOT_reported_empty(ottumwa, ottumwa_admin):
    """The other half — without it the notice above cannot tell pass from fail."""
    with tenant_ctx(ottumwa):
        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "ottumwa_premises.csv",
                "content": ottumwa_csv(),
                "session_ref": "sess_cr036g",
                "ip": "71.42.108.14",
            },
        )
        transformed = import_runs.transform(
            ottumwa_admin,
            run["id"],
            {"mapping": OTTUMWA_MAPPING, "row_handling": ALL_ON},
        )
        assert transformed["mapping_spec"]["empty_columns"] == []


def test_cr036_i__the_shipped_sample_no_longer_ROUTES_a_tenant_to_no_services(
    ottumwa, ottumwa_admin
):
    """⛔ **THIS TEST USED TO ASSERT THE TRAP AND NOW ASSERTS IT IS CLOSED
    (DEF-754).**

    It read `assert cells["services_available"] == ""` and pinned the product's
    own route into CR-036 (i): the sample shipped the services header with an
    EMPTY cell — deliberately, *"tenant-specific vocabularies — never
    guessed"* — so a file built from it mapped the column, showed `Matched`,
    and tagged nothing on every row.

    **The reasoning was sound and the result was the incident.** What replaces
    it is not a guess either: the cell now carries THIS TENANT'S OWN ENABLED
    SERVICE CODES, which is the same declaration `BR-MET-003` already measures
    every imported row against. Ottumwa Water Works sells Water, Sewer and
    Trash, so its sample says so — and a different tenant's sample says
    something different, which is the property that makes it a reading rather
    than a default.

    ⚠ The cell contains commas, so `csv.writer` quotes it and this test reads
    the file with a real CSV reader. The old two-`split(",")` version would
    have reported `"sewer` — a sample that is only correct when parsed as CSV
    has to be ASSERTED as CSV.
    """
    with tenant_ctx(ottumwa):
        _filename, body = import_runs.sample_csv("premises")
        _header, worked = list(csv.reader(io.StringIO(body)))[:2]
        # DEF-1077 — the header is the column's LABEL now; the field order is
        # `sample_columns`, the one list `sample_csv` writes.
        fields = [str(c["target"]) for c in import_runs.sample_columns("premises")]
        cells = dict(zip(fields, worked, strict=False))
        assert "services_available" in cells
        assert cells["services_available"] == "sewer,trash,water", cells


def test_cr036_g__a_skip_on_load_rule_does_not_skip_anything_MEASURED(ottumwa, ottumwa_admin):
    """⚠ **CR-036 (g)'s blocking measurement, pinned as behaviour — and this
    test asserts the DEFECT, not the desired end state.**

    The CR held (g) — *move the write-mode choice to stage 1 or 2* — on one
    unresolved fact, because the repo contradicted itself about it:
    `import_rules.py` said the `skip_on_load` ACTION *"is performed at stage 4,
    which is P5 and unbuilt"*, while `ImportWorkflowPage.tsx` said **"STAGE 4
    COMMITS NOW … this note used to say the opposite."** Both were half right.
    Stage 4 IS built and DOES commit; the rule ACTION was never wired into it.
    `SKIP_ON_LOAD` is assigned once (`PRM.ADDRESS_ON_FILE`) and read nowhere.

    **What that costs, in both directions.** It makes CR-036 (iii)'s advice —
    *re-run the same file in `Insert & update`* — genuinely reachable for all
    9,881 rows, which is the answer already given to the PO. And it makes the
    stage-3 table's **"Skip on load"** label a promise no code keeps, on 9,881
    rows, to an operator planning a migration around it.

    ⛔ **Whether to build the action or stop claiming it is CR-036 (g)'s
    question and is not decided here.** This test exists so that whoever
    answers it must come here and say so: the day the skip fires, this goes RED
    on purpose.
    """
    with tenant_ctx(ottumwa):
        _load(ottumwa_admin)
        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "ottumwa_premises_again.csv",
                "content": _second_run_services(),
                "session_ref": "sess_cr036g",
                "ip": "71.42.108.14",
            },
        )
        import_runs.transform(
            ottumwa_admin,
            run["id"],
            {"mapping": OTTUMWA_MAPPING, "row_handling": ALL_ON},
        )
        validated = import_runs.validate(ottumwa_admin, run["id"])

        # (1) The rule declares the action THE LOADER PERFORMS, on every row.
        rule = next(r for r in validated["rules"] if r["code"] == "PRM.ADDRESS_ON_FILE")
        assert (rule["action"], rule["hits"]) == ("flag_only", 3), rule

        # (2) …and the rows it hit are `flagged`, NOT `skipped`. `_loadable_rows`
        #     excludes `skipped` and forwards `flagged`, so this one word is the
        #     whole of whether the action fires.
        outcomes = sorted(
            models.ImportRunRow.objects.filter(run_id=run["id"]).values_list("outcome", flat=True)
        )
        assert outcomes == ["flagged", "flagged", "flagged"], outcomes

        # (3) The dry run PLANS to write all three — the operator is told the
        #     truth before committing, which is the one thing that is fine here.
        figures = import_runs.dry_run(ottumwa_admin, run["id"], "upsert")
        assert (figures["will_create"], figures["will_update"]) == (0, 3), figures

        # (4) …and the commit writes all three. `skipped` stays 0.
        receipt = import_runs.load(
            ottumwa_admin, run["id"], {"write_mode": "upsert", "approved": True}
        )
        counts = receipt["counts"]
        assert (counts["created"], counts["updated"], counts["skipped"]) == (0, 3, 0), counts
        assert models.Premises.objects.get(premise_no="P-10000").services_available == ["water"]

        # (5) **AND THE ROW'S OWN SENTENCE STOPS PROMISING IT TOO.** The hint on
        #     every hit row read *"It will be skipped unless you say to load it
        #     anyway."* — a second copy of the same false promise, one level
        #     down, in the words the operator reads next to their own row. The
        #     row was never skipped and there was never anything to say.
        hints = set(
            models.ImportRunRow.objects.filter(run_id=run["id"]).values_list("fix_hint", flat=True)
        )
        assert not any("skipped" in (hint or "") for hint in hints), hints


def test_def750__no_rule_declares_an_action_THE_LOADER_DOES_NOT_PERFORM():
    """⛔ **DEF-750's prevention, and it is the check nobody had.**

    The defect was not that the skip was missing. It was that a rule could
    DECLARE an action, the screen could print it in the ACTION column on 9,881
    rows, and **nothing anywhere compared that declaration against what the
    loader does** — so an operator planned a migration around a promise the
    product does not keep, and every test in this repo passed.

    **Measured, not inferred:** `import_runs` reads a rule's `action` in exactly
    two places, `_evaluate` (to record it) and `rule_results` (to serve it).
    It NEVER branches on one. So the only actions a rule may declare are the
    ones that need no branch: `reject_row` (delivered by severity — an ERROR
    row is `rejected` and `_loadable_rows` excludes it) and `flag_only` (which
    is the absence of an action, said out loud).

    ⚠ **`DEFAULT_TO` IS DELIBERATELY NOT IN THIS SET AND IS NOT ASSERTED
    EITHER.** Two assets rules declare it (`AST.MULTIPLIER_POSITIVE_INT`,
    `AST.NEXT_TEST_DERIVABLE`) and the loader performs neither — but their
    stated effects appear to be delivered by other means (`Asset.multiplier`
    defaults to 1 in the model; `next_test` is DERIVED at read time by
    `assets.selectors.next_test_date`). **This lane did not measure either
    claim**, and asserting an allow-list entry it had not verified would be the
    same comment-as-guarantee failure in a new place (hard-won law 1). The
    question is REPORTED, not answered here.

    So the guard is narrow and exact: **no declared rule may carry an action
    that has been measured to do nothing.** Today that is `skip_on_load`. The
    day a lane builds it, it goes in the loader and comes off this list, in one
    commit.
    """
    from apps.metering import import_rules

    unperformed = {import_rules.SKIP_ON_LOAD}
    offenders = [
        (rule.code, rule.action)
        for catalog in import_rules.PLATFORM_CATALOG.values()
        for rule in catalog
        if rule.action in unperformed
    ]
    assert offenders == [], (
        "these rules declare an action the loader has been measured not to "
        f"perform, so the ACTION column on stage 3 is a promise: {offenders}"
    )
