# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-962 — every reference cell in the three assets templates ships
#           BLANK (`unit_ref` on all three, `parent_asset_no` on sub-meters,
#           `premises` on devices), so the downloaded file shows no way to link
#           a meter to a unit and a file built from it loads every meter into
#           inventory with a clean rehearsal. PO verbatim, twice:
#           *"Template does not have a unit field so he is not going to link
#           it"* and *"you dont have Unit field in CSV file that is downloaded;
#           when you upload assets you iwll need Units field mapping - please
#           chekc out"*.
#           DEF-963 — the meter and sub-meter templates hardcode
#           `service=electric`, so on a utility that does not sell electricity
#           the product's own template is rejected by the product's own import.
#           DEF-965 — the commit that failed after a clean dry run. Not
#           reproduced; what IS closed here is the hole it fell through, which
#           is that nothing drove a SHIPPED TEMPLATE past stage 3 to the write.
# Rules:    CR-025 (the sample is header + ONE WORKED ROW) · CR-036 (i) /
#           DEF-754 (a tenant's own declaration is not a guess) · BR-AST-045
#           (a named unit tags, a blank unit loads to inventory) · BR-AST-003
#           (a sub-meter REQUIRES an active master) · BR-MET-003 /
#           AST.SERVICE_ENABLED (only a service this utility sells)
# Tests:    this file IS the prevention all three rows ask for.
# Impacts:  apps/metering/import_runs.py — _asset_column / _account_column
#           (the `sample` key is written only when DECLARED),
#           _sample_reference_cells, sample_csv.cell
# ───────────────────────────────────────────────────────
"""The template a utility downloads, measured on a utility that is not ours.

**THE PROPERTY THIS FILE ADDS IS NOT "the sample has a unit column".** It had
one, called `unit_ref`, and it was empty. The property is:

    the file this product hands a utility must survive THAT utility's own
    validation, and must demonstrate the link it exists to teach — all the way
    to the COMMIT, not as far as the rehearsal.

Every existing guard stopped short of that. `test_cr025_sample_csv` drives the
round trip for **premises only**. DEF-616's guard walks all six targets and
asserts stage 1 **detects the headers** and nothing more. Nothing anywhere
drove a shipped template to a write, on a tenant that sells something other
than electricity — which is every tenant this product has.

RED-FIRST PROOF (r11 step 2d), taken against the tree AS IT STOOD in a clean
`git worktree` of the branch tip, before this lane's change:

  DEF-963, the shipped meters template on Ottumwa Water Works (water · sewer ·
  trash), uploaded unedited:

      VALIDATE: {'in': 1, 'forward': 1, 'checked': 1, 'clean': 0, 'errors': 1}
        REJECT 1 This utility does not sell electric.
                 | Fix the service in the row, or turn it on in Settings first.
      DRY RUN: {'will_create': 0, 'rejected': 1}

  DEF-962, the same file's bytes, and the sub-meters and devices files beside
  it — the reference cells are the empty ones between the commas:

      asset_no,meter_type,service,read_method,multiplier,unit_ref,manufacturer,…
      M-9001,ami,electric,ami,1,,Sample Meter Co,MX-100,…
      SM-9001,sub_meter,electric,ami,1,,…,164.0000,,
      BF-9001,backflow,,,Sample Device Co,DX-10,…

  and the silent half, twenty rows built on that template with the Unit column
  left as the template leaves it:

      DRY: {'will_create': 20, 'rejected': 0, 'unit_tagged': 0, 'to_inventory': 20}
      LOAD OK: {'created': 20, 'unit_tagged': 0, 'to_inventory': 20}

  Twenty meters, no rejects, no flags, and not one of them attached to
  anything. That is the PO's *"he is not going to link it"*.

  And `tests/test_cr028_import_targets.py::test_cr025_sample_csvs_serve_header
  _plus_one_worked_row` PASSED on that tree while asserting
  `by_name.get("unit_ref", "") == ""` — the guard pinned the defect in place.
"""

import csv
import io

import pytest

from apps.assets import models as assets_models
from apps.metering import import_runs, models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_premises,
    make_unit,
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db

ALL_OFF = {
    "drop_exact_duplicates": False,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}
ASSETS_TARGETS = ("assets_meters", "assets_submeters", "assets_devices")


# ══════════════════════════════════════════════════════════════════════════
# The PO's own tenant, rebuilt — water · sewer · trash, and no electricity.
# ══════════════════════════════════════════════════════════════════════════
#
# The subdomain and the service mix are the ones `test_cr036_import_services`
# already uses for the same reason: this is the tenant whose screenshot the
# report came from, and the whole of DEF-963 is invisible on any tenant that
# happens to sell what the literal said.


@pytest.fixture()
def ottumwa(growth_plan, identity_seam):  # noqa: F405
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


def _cells(target: str) -> dict[str, str]:
    """Keyed by FIELD — the header row is the column's LABEL since 2026-08-28
    (`DEF-1077`), and `sample_columns` is the one list `sample_csv` writes."""
    rows = list(csv.reader(import_runs.sample_csv(target)[1].splitlines()))
    fields = [str(column["target"]) for column in import_runs.sample_columns(target)]
    return dict(zip(fields, rows[1]))


def _estate(actor, count=3):
    """Premises → Units, in the build order the README states, so the template
    has something of the tenant's own to name."""
    units = []
    for index in range(count):
        premises = make_premises(
            actor,
            address_line=f"{100 + index} Court St",
            city="Ottumwa",
            state="IA",
            postal_code="52501",
            services_available=["water", "sewer", "trash"],
        )
        units.append((premises, make_unit(actor, premises["id"], label=f"Unit {index}")))
    return units


def _drive(actor, target, content, write_mode="insert"):
    """All five stages, on the DETECTED mapping — an operator who downloads the
    file, fills it in and uploads it touches nothing at stage 2."""
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": f"{target}_sample.csv",
            "content": content,
            "session_ref": "sess_def962",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(
        actor, run["id"], {"mapping": run["detected_mapping"], "row_handling": ALL_OFF}
    )
    checked = import_runs.validate(actor, run["id"])
    problems = [
        (row["row_no"], row["problem"])
        for row in import_runs.rejects(metering_models.ImportRun.objects.get(pk=run["id"]))
    ]
    figures = import_runs.dry_run(actor, run["id"], write_mode)
    return run, checked, problems, figures


# ══════════════════════════════════════════════════════════════════════════
# DEF-963 · the service cell is THIS utility's, not another one's
# ══════════════════════════════════════════════════════════════════════════


def test_def963__the_service_cell_is_this_tenants_own_enablement(ottumwa, ottumwa_admin):
    """Ottumwa sells water, sewer and trash — so its template says one of those.

    ⚠ **AND IT AGREES WITH THE LIST CELL BY CONSTRUCTION**: both come from
    `seams.enabled_service_codes()`, so a file cannot name a service in one
    column that the other says this utility does not sell.
    """
    with tenant_ctx(ottumwa):
        for target in ("assets_meters", "assets_submeters"):
            service = _cells(target)["service"]
            assert service != "electric", (
                f"{target}: the template still hardcodes another utility's service — "
                "DEF-963, and its own import rejects the row"
            )
            assert service in {"water", "sewer", "trash"}, service


def test_def963__a_tenant_that_sells_something_else_gets_something_else(brazos):  # noqa: F811
    """Brazos Bend sells Electric and Water. Nothing is borrowed between them —
    the same pair of cases CR-036 (i) pinned for `services_available`."""
    with tenant_ctx(brazos):
        assert _cells("assets_meters")["service"] in {"electric", "water"}


# ══════════════════════════════════════════════════════════════════════════
# DEF-962 · the reference cells carry the tenant's own rows
# ══════════════════════════════════════════════════════════════════════════


def test_def962__with_nothing_on_file_the_reference_cells_are_HONESTLY_empty(
    ottumwa, ottumwa_admin
):
    """A tenant with no units cannot link a meter to one, and the template says
    so by leaving the cell empty rather than inventing `U-00001`.

    That is not the defect — the defect is a blank cell on a tenant that HAS
    units. This case exists so the fix cannot be read as "always put something
    there", which would teach the opposite of the build order.
    """
    with tenant_ctx(ottumwa):
        assert metering_models.Unit.objects.filter(tenant=ottumwa).count() == 0
        for target in ASSETS_TARGETS:
            assert _cells(target)["unit_ref"] == ""
        assert _cells("assets_submeters")["parent_asset_no"] == ""


def test_def962__the_unit_cell_names_a_unit_THIS_TENANT_HAS(ottumwa, ottumwa_admin):
    """THE PO'S OWN SENTENCE, as a test: the downloaded file shows how a meter
    is linked to a unit, on all three targets."""
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        on_file = {unit["unit_no"] for _premises, unit in units}
        for target in ASSETS_TARGETS:
            cell = _cells(target)["unit_ref"]
            assert cell != "", (
                f"{target}: the Unit cell is empty on a tenant that has "
                f"{len(on_file)} units — DEF-962, the file the PO downloaded"
            )
            assert cell in on_file, f"{target}: {cell} is not a unit this tenant has"


def test_def962__the_devices_template_names_a_premises_this_tenant_has(ottumwa, ottumwa_admin):
    """A behind-the-meter device seats on a premises or a unit (BR-AST-045);
    the template shipped both cells blank, so it demonstrated neither."""
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        on_file = {premises["premise_no"] for premises, _unit in units}
        assert _cells("assets_devices")["premises"] in on_file


def test_def962__the_submeter_template_names_an_ACTIVE_master(ottumwa, ottumwa_admin):
    """BR-AST-003: `parent_asset_no` is REQUIRED and structural, so a template
    that ships it blank has a worked row that can never load.

    ⚠ The cell must name a parent `AST.PARENT_ON_FILE` will ACCEPT — a meter or
    a net-meter, and an in-service one. A retired master or a sub-meter would
    be a cell that looks filled in and rejects, which is worse than blank.
    """
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        _premises, unit = units[0]
        master = asset_services_create(ottumwa_admin, unit)
        cell = _cells("assets_submeters")["parent_asset_no"]
        assert cell == master["asset_no"], (cell, master["asset_no"])


def asset_services_create(actor, unit):
    """One ACTIVE master meter on a unit, through the real service."""
    from apps.assets import services as asset_services

    return asset_services.create_asset_for_unit(
        actor=actor,
        unit_id=unit["id"],
        service_point_id=None,
        payload={
            "type": "meter",
            "asset_no": "M-7001",
            "service": "water",
            "read_method": "ami",
            "multiplier": "1",
        },
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-935 · a service with no unit is REJECTED AT STAGE 3, not inside the write
# ══════════════════════════════════════════════════════════════════════════
#
# RED, verbatim, on the tree before `AST.SERVICE_HAS_UNIT` existed — this is
# the PO's symptom reproduced, and the rehearsal was CLEAN:
#
#     VALIDATE: {'in': 1, 'forward': 1, 'checked': 1, 'clean': 1, 'errors': 0}
#     DRY:      {'will_create': 1, 'rejected': 0}
#     E   core.errors.ValidationError: VAL-001 (assets.uom_required)
#     apps/assets/services.py:248: ValidationError
#
# `tenancy.selectors.service_default_uoms` states the cause in its own
# docstring: *"Four of the ten catalog services — sewer, solar, thermal/heat,
# battery — have no design-stated default, so a tenant that enables one carries
# a NULL."* The load is RIGHT to refuse (hard rule 3 — a reading with no unit
# is the one thing this product may never store); what was wrong is that it
# refused in the only stage that writes, after a rehearsal that promised
# twenty rows, taking the whole all-or-nothing transaction with it.


def _meters_csv(rows):
    header = [
        "asset_no", "meter_type", "service", "read_method",
        "multiplier", "unit_ref", "install_date",
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(name, "") for name in header])
    return buffer.getvalue()


def test_def935__a_service_with_no_unit_on_file_is_REJECTED_AT_STAGE_3(ottumwa, ottumwa_admin):
    """Ottumwa sells sewer and declares no unit for it. The row must be refused
    where the operator can act on it, with a sentence naming the service and
    the screen that fixes it — never as a dead commit.

    ⚠ **AMENDED 2026-10-03 (`DEF-MET-9248`) — THE ROW CARRIED `asset_no:
    "M-4001"` AND HAS BEEN REFUSED ON A DIFFERENT RULE SINCE BR-AST-049.**
    Its sibling below was amended on 2026-08-30 for exactly this; this one
    was missed, so the first problem read *"M-4001 is not a number this
    utility has issued"* and the `sewer` assertion failed on a rule the case
    is not about. Blank, as the sibling: Insert mode allocates the number.

    ⚠ **AND THE PREMISE MOVED UNDER IT TOO: `CR-081` (2026-09-08) gave sewer a
    unit** (90% of the water volume), so a fresh Ottumwa no longer holds the
    NULL this case is about, and with the number blanked the row loaded clean.
    The NULL is a state a tenant can still hold — the stored row is the
    tenant's to change, and four catalogue services carry none — so the case
    now SETS it on the tenant's own sewer row rather than relying on the seed.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(ottumwa):
        tenancy_models.TenantService.objects.filter(
            tenant=ottumwa, service__code="sewer"
        ).update(primary_uom=None)
        units = _estate(ottumwa_admin, 1)
        _premises, unit = units[0]
        content = _meters_csv(
            [
                {
                    "meter_type": "ami",
                    "service": "sewer",
                    "read_method": "ami",
                    "multiplier": "1",
                    "unit_ref": unit["unit_no"],
                    "install_date": "01/01/2026",
                }
            ]
        )
        _run, checked, problems, figures = _drive(ottumwa_admin, "assets_meters", content)
        assert checked["counts"]["errors"] == 1, (checked["counts"], problems)
        assert figures["will_create"] == 0, figures
        problem = problems[0][1]
        # The SERVICE is named, and so is the place the NULL lives. The load's
        # own sentence — "Choose the unit this asset reads in." — names a field
        # the assets import does not even offer as a column.
        assert "sewer" in problem, problem
        assert "unit" in problem.lower(), problem
        assert assets_models.Asset.objects.filter(tenant=ottumwa).count() == 0


def test_def935__the_rule_is_STRUCTURAL_so_a_tenant_cannot_switch_it_off(ottumwa):
    """TIER 1, for the reason `AST.SERVICE_AT_PREMISES` gives one rule up: the
    loader refuses the row whatever this table says, so a switchable rule would
    tell an operator the load succeeded when it did not (BR-MET-090)."""
    from apps.metering import import_rules

    with tenant_ctx(ottumwa):
        for target in ("assets_meters", "assets_submeters"):
            rule = next(
                declared
                for declared in import_rules.resolve(target, ottumwa.id)
                if declared.code == "AST.SERVICE_HAS_UNIT"
            )
            assert rule.tier == import_rules.TIER_STRUCTURAL
            assert rule.severity == import_rules.ERROR
            assert rule.action == import_rules.REJECT_ROW


def test_def935__a_service_that_HAS_a_unit_is_untouched_by_the_new_rule(ottumwa, ottumwa_admin):
    """The rule must bite on the NULL and on nothing else — water carries a
    unit, so a water meter loads exactly as it did before.

    ⚠ **AMENDED 2026-08-30 — THE ROW USED TO CARRY `asset_no: "M-4002"` AND THE
    PRODUCT NOW REFUSES IT (PO ruling 2026-08-27, BR-AST-049 / CR-046).** That
    column means *"an EXISTING SMARTBillHub number"* since the ruling, so a
    legacy number in it is `AST.NUMBER_NOT_ON_FILE` — and this case then failed
    on a rule it is not about. It is left BLANK, which is the ruling's normal
    case and the only case in Insert mode: BR-AST-026 allocates the number from
    the tenant's series inside the write. The case's own subject —
    `AST.SERVICE_HAS_UNIT` biting on the NULL and on nothing else — is
    unchanged, and the created meter is now asserted to carry a real
    platform-issued number so the blank cell cannot pass by loading nothing.
    """
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin, 1)
        _premises, unit = units[0]
        content = _meters_csv(
            [
                {
                    "meter_type": "ami",
                    "service": "water",
                    "read_method": "ami",
                    "multiplier": "1",
                    "unit_ref": unit["unit_no"],
                    "install_date": "01/01/2026",
                }
            ]
        )
        run, checked, problems, figures = _drive(ottumwa_admin, "assets_meters", content)
        assert checked["counts"]["errors"] == 0, problems
        receipt = import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert"})
        assert receipt["counts"]["created"] == 1
        assert receipt["counts"]["unit_tagged"] == 1
        # BR-AST-026 — the blank cell is not a missing number: the series
        # allocated one inside the write.
        created = assets_models.Asset.objects.get(tenant=ottumwa)
        assert (created.asset_no or "").strip(), (
            "the row left `asset_no` blank, as CR-046 says it must, and the "
            "platform issued no number in its place"
        )


# ══════════════════════════════════════════════════════════════════════════
# THE POINT — a shipped template survives its own import, past the rehearsal
# and all the way to the WRITE, on a utility that is not ours
# ══════════════════════════════════════════════════════════════════════════


def test_THE_POINT__every_assets_template_loads_on_the_tenant_it_was_built_for(
    ottumwa, ottumwa_admin
):
    """Download → upload unedited → commit, for all three targets in the order
    the product itself requires (a sub-meter needs its master first).

    ⚠ **THIS ASSERTS THE COMMIT, NOT THE DRY RUN, AND THAT IS DELIBERATE.**
    DEF-965 is a commit that failed behind a clean rehearsal; the class of
    defect it belongs to (DEF-618: a condition stage 3 never checks, refused
    inside the one stage that writes) is invisible to any test that stops at
    `dry_run`. Every existing sample guard stopped there.
    """
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin)
        for target in ASSETS_TARGETS:
            _filename, body = import_runs.sample_csv(target)
            run, checked, problems, figures = _drive(ottumwa_admin, target, body)
            assert checked["counts"]["errors"] == 0, (
                f"{target}: the shipped template failed its OWN validation on the "
                f"tenant it was downloaded from — {problems}"
            )
            assert figures["will_create"] == 1, (target, figures)
            receipt = import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert"})
            assert receipt["counts"]["created"] == 1, (target, receipt["counts"])
            # BR-AST-045 — and the whole of the PO's report: the row that
            # arrives is ATTACHED, not sitting in inventory.
            assert receipt["counts"]["unit_tagged"] == 1, (
                f"{target}: the template's own row loaded UNLINKED — the Unit cell "
                "taught nothing (DEF-962)"
            )
            assert receipt["counts"]["to_inventory"] == 0, (target, receipt["counts"])
        assert assets_models.Asset.objects.filter(tenant=ottumwa).count() == 3


def test_def962__a_file_built_on_the_template_no_longer_lands_twenty_meters_NOWHERE(
    ottumwa, ottumwa_admin
):
    """The silent outcome, as a case: twenty rows built by copying the
    template's own worked row down, on a tenant with units.

    Before the fix this loaded 20 created / 20 to_inventory / 0 rejected — no
    error anywhere, and every meter unattached. `_empty_columns` cannot see it
    because the column is not empty in the FILE; it is empty in the EXAMPLE the
    file was copied from.

    ⚠ **AMENDED 2026-08-30 — THIS FILLED `asset_no` WITH `M-8000…M-8019` AND
    THE PRODUCT NOW REFUSES EXACTLY THAT (PO ruling 2026-08-27, BR-AST-049 /
    CR-046).** `asset_no` changed meaning: it is *"an EXISTING SMARTBillHub
    number, if this row updates a meter already on file — blank for a new
    one"*, and a first-migration number this product never issued is refused by
    name (`AST.NUMBER_NOT_ON_FILE`). All twenty rows errored on it, which is the
    guard working: **the number is issued from Settings → Numbering inside the
    write transaction (BR-AST-026), and the utility's own number goes in
    External reference.**

    **The amendment makes the case a CLOSER reproduction of what it is about,
    not a weaker one.** DEF-962 is about a person copying the shipped worked row
    down; under the ruling the shipped `asset_no` cell is an explicit blank, so
    a person copying it down leaves it blank — which is now exactly what this
    builds. Only the UNIT varies, which is the one cell DEF-962 says the
    template must teach them to fill. The old number lives on as
    `external_ref`, where BR-AST-049 puts it, so nothing is lost from the file.
    """
    with tenant_ctx(ottumwa):
        estate = _estate(ottumwa_admin, 20)
        header, worked = list(csv.reader(import_runs.sample_csv("assets_meters")[1].splitlines()))
        # DEF-1077 — the header row is the LABEL, so the POSITIONS come from
        # `sample_columns`; the file itself is still written header-first, so a
        # person copying the worked row down is reproduced exactly.
        fields = [str(c["target"]) for c in import_runs.sample_columns("assets_meters")]
        number_at, unit_at = fields.index("asset_no"), fields.index("unit_ref")
        ref_at = fields.index("external_ref")
        # The ruling, asserted on the bytes before the file is even built: the
        # shipped worked row leaves the identifier cell EMPTY. If that ever
        # regresses, this case would silently start testing the old world again.
        assert worked[number_at] == "", (
            "the shipped assets_meters sample fills `asset_no` — CR-046/DEF-962: "
            "the number is issued from Settings → Numbering and is never read "
            f"off the file. Got {worked[number_at]!r}"
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(header)
        # Twenty rows built the way a person builds them: the template's worked
        # row copied down, with the cells that are THIS row's own changed.
        # ⚠ The unit varies because `AST.UNIT_SERVICE_FREE` is right — one unit
        # may hold one active meter per service — and because the template
        # showing a unit is precisely what makes an operator fill this column
        # in. Before the fix the cell was blank, so it stayed blank.
        for index, (_premises, unit) in enumerate(estate):
            row = list(worked)
            # `asset_no` is LEFT AS THE TEMPLATE SHIPS IT — blank. The utility's
            # own number goes where BR-AST-049 puts it.
            row[ref_at] = f"M-{8000 + index}"
            row[unit_at] = unit["unit_no"]
            writer.writerow(row)
        run, checked, problems, figures = _drive(ottumwa_admin, "assets_meters", buffer.getvalue())
        assert checked["counts"]["errors"] == 0, problems
        assert figures["will_create"] == 20, figures
        receipt = import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert"})
        counts = receipt["counts"]
        assert counts["created"] == 20, counts
        # ⚠ THE ONE THAT MATTERS. `to_inventory == 20` was the defect, and it
        # was reported by nothing: 0 rejected, 0 flagged, a clean receipt.
        assert counts["to_inventory"] == 0, (
            "a file built on the shipped template still lands every meter in "
            f"inventory — DEF-962: {counts}"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-962 · DEF-963 · DEF-965 (PO report 2026-08-27) — CR-025 (sample =
#         header + one worked row) · CR-036 (i)/DEF-754 (a tenant's own
#         declaration is not a guess) · B16 §4.7b (the assets field map) ·
#         BR-AST-045/003 · BR-MET-003
# generated: 2026-08-27 by lane ASSETIMPORT
# checklist: A✔ B=n/a(backend-only defect fix) C✔ D=n/a E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E1 DEF-965 — the commit failure the PO reported is NOT reproduced
#         and is NOT closed by this file. What is closed is the hole it fell
#         through: no test drove a shipped template past stage 3 to a write.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
