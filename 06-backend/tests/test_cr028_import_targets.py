# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W3 (B16 §4.7/§4.7a/§4.7b — the three assets targets on
#           the ONE workflow runner)   Screens: WFL-01.meters/submeters/
#           devices.1–5 · AST-04 (Imports tab, run history + rollback)
# Rules:    BR-AST-045 (one asset one unit; BLANK unit ACCEPTED → inventory) ·
#           BR-AST-046 (tab-named workflow entry; the modal path is retired) ·
#           BR-MET-096 (targets are dict entries on ONE runner) · BR-AST-003
#           (sub-meter parent) · BR-AST-026/033 (numbers) · CR-026 (100k cap ·
#           ASYNC_ROW_BAR 5,000 → 202) · CR-025 (sample = header + one worked
#           row) · OQ-580 (replace-the-batch WITHDRAWN everywhere — refused;
#           SUPERSEDES OQ-326, which asked the assets-only version)
# Tests:    this file — the AST-W3-T7 suite, off the committed W0-T2 fixtures
# Impacts:  apps/metering/import_runs.py · import_rules.py · apps/assets/
#           services.py (create/update/rollback_from_import) · selectors.py
# ───────────────────────────────────────────────────────
"""CR-028 AST-W3 — the three assets import targets, end to end.

RED-FIRST PROOF (r11 step 2d): the central BR-AST-045 case
(`test_br_ast_045__the_tagging_table_at_fixture_scale`) was run against the
tree AS IT STOOD BEFORE THIS LANE'S CHANGE, in a clean `git worktree` of the
prior HEAD, and failed at stage 1 with the runner refusing the target by name:

    core.errors.ValidationError: VAL-005 metering.import.kind_unknown
    params={'allowed': ['premises', 'units']}
    FAILED tests/test_cr028_import_targets.py::
        test_br_ast_045__the_tagging_table_at_fixture_scale

— which is exactly the absence this lane exists to close: before it, the
runner had no `assets_meters` target at all.

Every walk here drives the REAL five stages over the COMMITTED W0-T2 fixture
files (`tests/fixtures/cr028/*.csv`), on the seeded Silver Creek tenant, and
reads results back through the assets module's own selectors — the same reads
the registry screens use. The worked BR-AST-045 shape (r10's 1,262 → 1,255
loaded / 1,243 tagged / 12 inventory) is asserted at fixture scale:
**20 in → 3 rejected → 17 loaded → 14 tagged → 3 to inventory — and not one
of the 3 blank-unit rows is among the errors.**
"""

import csv
import io
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.db.models import Q

from apps.assets import models as assets_models
from apps.metering import import_runs, models as metering_models
from core import errors

from tests.test_cr028_seed import seeded, silvercreek  # noqa: F401 — fixture chain
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).parent / "fixtures" / "cr028"

#: The fixtures' headers → the targets' REAL columns (B16 §4.7b). `LEGACY` is
#: the field map's explicit "— ignore —" case, mapped so on purpose.
#: ⛔ **`METER_NO` MAPS TO `external_ref` SINCE 2026-08-27, AND THAT IS THE
#: WHOLE OF THE RULING IN ONE LINE (BR-AST-049).** PO verbatim: *"here we
#: should not allow usse to fill in Asset ID - we have number system set in
#: the settings, we shoudl call that function and get unique number and assign
#: it"*. This fixture IS a migration file: every `METER_NO` cell holds the OLD
#: system's number, which is exactly what `asset_no` now refuses and exactly
#: what `external_ref` is for. Mapped the old way the whole file rejects, and
#: the product's own auto-mapper agrees — `METER_NO` is an `external_ref`
#: alias now.
METERS_MAPPING = {
    "METER_NO": "external_ref",
    "METER_TYPE": "meter_type",
    "SERVICE": "service",
    "READ_METHOD": "read_method",
    "MULTIPLIER": "multiplier",
    "UNIT_REF": "unit_ref",
    "MFR": "manufacturer",
    "MODEL": "model",
    "INSTALL_DT": "install_date",
    "CERT_DUE": "certification_due",
    "WARRANTY_END": "warranty_end",
    "SUPPLIER": "supplier",
    "COST": "purchase_cost",
    "LEGACY": import_runs.IGNORE,
}
SUBMETERS_MAPPING = {
    **{k: v for k, v in METERS_MAPPING.items() if k != "LEGACY"},
    "PARENT_MTR": "parent_asset_no",
    "ALLOC_PCT": "allocation_share_pct",
}
#: Devices: the base meter columns the devices target does not OFFER are
#: ignored (they are blank in the fixture) — `NEXT_TEST` is the devices
#: target's own route to `certification_due`.
DEVICES_MAPPING = {
    "METER_NO": "external_ref",
    "METER_TYPE": import_runs.IGNORE,
    # ⚠ MAPPED since 2026-09-30: Service is REQUIRED on the devices sheet (PO
    # ruling, plan U2). The committed fixture leaves the cell blank on device
    # rows, so `_devices_fixture` fills it the way a utility would.
    "SERVICE": "service",
    "READ_METHOD": import_runs.IGNORE,
    "MULTIPLIER": import_runs.IGNORE,
    "UNIT_REF": "unit_ref",
    "MFR": "manufacturer",
    "MODEL": "model",
    "INSTALL_DT": "install_date",
    "CERT_DUE": import_runs.IGNORE,
    "WARRANTY_END": "warranty_end",
    "SUPPLIER": "supplier",
    "COST": "purchase_cost",
    "DEVICE_TYPE": "type",
    "PREMISE_ID": "premises",
    "TEST_FREQ": "test_interval_months",
    "NEXT_TEST": "certification_due",
    "EXPORT_KW": "export_capacity_kw",
}

ALL_OFF = {
    "drop_exact_duplicates": False,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


#: The service each fixture device is billed under (plan U2, 2026-09-30): a
#: backflow preventer protects the WATER supply; the rest sit behind the
#: electric meter on this tenant, which sells electric · water · sewer · trash.
_DEVICE_SERVICE = {"backflow": "water"}


def _devices_fixture() -> str:
    """The committed B16 fixture with its blank SERVICE cell filled per row."""


    rows = list(csv.reader(io.StringIO(_fixture("assets_devices.csv"))))
    header = rows[0]
    service, kind = header.index("SERVICE"), header.index("DEVICE_TYPE")
    for row in rows[1:]:
        row[service] = _DEVICE_SERVICE.get(row[kind], "electric")
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


#: ⚠ **THE METERS FILE'S SEATS MOVED ON 2026-10-03, NOT ITS SERVICES
#: (`DEF-3287`, the `DEF-AST-9259` idiom).** `CR-062` C4 (`70879c9aa`,
#: 2026-09-02) seeds a meter per unit per METERED service, so `SCW-U-001`…`050`
#: hold `E-5000`… beside `W-5000`…, and every electric row of the committed
#: fixture asked for a seat already taken. The product refused each one
#: correctly — *"Unit SCW-U-001 already has an active electric meter
#: (E-5000)"* — and five cases here then tested the seat rule instead of the
#: rule they are named for. So the rows are re-seated, IN THE TEST, on units
#: the sample leaves empty; the committed file is shared with two other suites
#: and is not edited. `SCW-U-011` (row 15, the water row whose taken seat IS
#: the case) and `SCW-U-999` (row 12, the unit that does not exist) keep their
#: refs, because those two refusals are what the file is for.
EMPTY_SEATS: tuple[str, ...] = (
    *(f"SCW-U-{n}" for n in (202, 203, 204, 205, 206, 208, 209, 210, 211, 212, 213)),
    *(f"SCW-U-{n}" for n in range(301, 320)),
    *(f"SCW-U-{n}" for n in range(325, 350)),
)
#: The fixture's electric seats, in file order → the empty seat each moves to.
_FIXTURE_SEATS = (
    "SCW-U-001", "SCW-U-002", "SCW-U-003", "SCW-U-004", "SCW-U-005",
    "SCW-U-047", "SCW-U-006", "SCW-U-007", "SCW-U-008", "SCW-U-009",
    "SCW-U-010", "SCW-U-012", "SCW-U-013", "SCW-U-014", "SCW-U-015",
)  # fmt: skip
RESEAT = dict(zip(_FIXTURE_SEATS, EMPTY_SEATS))


def _reseated(content: str, reseat: dict[str, str]) -> str:
    """`content` with each UNIT_REF cell in `reseat` replaced — that column
    only, every other byte of every row unchanged."""
    rows = list(csv.reader(io.StringIO(content)))
    unit = rows[0].index("UNIT_REF")
    for row in rows[1:]:
        row[unit] = reseat.get(row[unit], row[unit])
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def _meters_fixture(content: str | None = None) -> str:
    """The committed meters fixture (or an edited copy of it), re-seated."""
    return _reseated(content if content is not None else _fixture("assets_meters.csv"), RESEAT)


def _assert_seats_empty(seats) -> None:
    """Fail by NAME if the seed has grown into a seat this file relies on —
    rather than failing later on the seat rule, which is how `DEF-3287` hid."""
    taken = sorted(
        assets_models.AssetAssignment.objects.filter(
            unit__unit_no__in=list(seats), to_date__isnull=True
        ).values_list("unit__unit_no", flat=True)
    )
    assert not taken, f"the sample now seats something on {taken}; pick other empty units"


def _extract(actor, target: str, content: str, file_name: str = "cr028.csv"):
    return import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": file_name,
            "content": content,
            "session_ref": "sess_cr028",
            "ip": "71.42.108.14",
        },
    )


def _validated(actor, target: str, content: str, mapping: dict) -> str:
    run = _extract(actor, target, content)
    import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"])
    return run["id"]


def _rejects(run_id) -> dict[int, tuple[str, str | None]]:
    return {
        row["row_no"]: (row["problem"], row["fix_hint"])
        for row in import_runs.rejects(metering_models.ImportRun.objects.get(pk=run_id))
    }


def _asset(ref: str) -> assets_models.Asset:
    """The asset a fixture ROW produced, addressed by whichever identifier the
    file carried.

    ⚠ **IT LOOKS UP `external_ref` AS WELL AS `asset_no`, AND THAT IS
    `BR-AST-049` RATHER THAN A CONVENIENCE.** The fixture's `E-2001` is the
    utility's OLD system's number; since 2026-08-27 the import writes it to
    `external_ref` and gives the row a number of OUR OWN from the series, so
    `filter(asset_no="E-2001")` finds nothing and the test would report the
    row as never created. The identity the test means is *"the meter that
    arrived on the row labelled E-2001"*, and this is that."""
    row = (
        assets_models.Asset.objects.filter(
            Q(asset_no=ref) | Q(external_ref__iexact=ref)
        )
        .select_related("type", "status", "meter_type", "read_method", "parent_asset")
        .first()
    )
    assert row is not None, f"{ref} was not created"
    return row


def _current_unit(asset: assets_models.Asset):
    return assets_models.AssetAssignment.objects.filter(asset=asset, to_date__isnull=True).first()


# ══════════════════════════════════════════════════════════════════════════
# T1 · the three targets are REGISTERED — dict entries on the one runner
# ══════════════════════════════════════════════════════════════════════════


def test_the_three_targets_are_dict_entries_on_the_one_runner():
    """BR-MET-096 as written: vocabulary, catalog, aliases, columns — every
    registration point carries all three, and no fourth pipeline exists."""
    from apps.metering import import_rules

    for target in ("assets_meters", "assets_submeters", "assets_devices"):
        assert target in metering_models.IMPORT_TARGETS
        assert target in import_runs.TARGETS
        assert target in import_rules.PLATFORM_CATALOG
        assert target in import_runs.ALIASES_BY_TARGET
        assert target in import_runs.EXPLICIT_COLUMNS_BY_TARGET


def test_every_declared_column_names_a_real_destination():
    """BR-MET-088's drift pin for the DECLARED sets: every offered column lands
    somewhere real — a column on the target's OWN model, or one of the named
    non-column destinations.

    ⚠ **THE DESTINATION MODEL IS PER TARGET.** This case checked everything in
    `EXPLICIT_COLUMNS_BY_TARGET` against `Asset` alone, which was correct while
    all three entries were assets targets and went red the moment CR-030 W1
    registered `accounts` — `account_no` *"lands nowhere"* on an `Asset` and
    lands squarely on an `Account`. The pin is worth keeping and the lookup is
    what was too narrow.
    """
    from apps.customers import models as customers_models

    asset_fields = {field.name for field in assets_models.Asset._meta.get_fields()}
    account_fields = {field.name for field in customers_models.Account._meta.get_fields()}

    asset_non_column = {
        "unit_ref",  # → asset_assignments (BR-AST-045)
        "premises",  # → the premises' one unit (devices)
        "service",  # → the service point at assignment (BR-AST-009)
        "parent_asset_no",  # → the BR-AST-003 parent FK, by number
    }
    account_non_column = {
        "unit_ref",  # → `accounts.unit_id`, resolved at load (BR-CUS-047)
        "customer_name",  # → the CONTACT row, and the customer's display name
        "customer_no",  # → `customers.customer_no` (CR-030 W0)
        "customer_ref",  # → `customers.external_ref` (BR-CUS-054's legacy id)
        "email",  # → the contact
        "phone",  # → the contact
        "mailing_line1",  # → an `addresses` row, kind=mailing
        "mailing_city",
        "mailing_state",
        "mailing_postal_code",
        "external_ref",  # → the customer, not the account
        # BR-CUS-048's four aged buckets → `account_opening_buckets` rows, and
        # then one balanced opening journal entry (BR-CUS-049). Deliberately
        # NOT account columns: `accounts.balance` caches their SUM.
        "ob_current",
        "ob_31_60",
        "ob_61_90",
        "ob_90_plus",
        # ⚠ **CR-058 W7 / BR-CUS-1041's four identity columns (`aa0fe2392`,
        # 2026-09-01) land on the CUSTOMER, not the account** — the kind picks
        # which identifier counts, and the three identifiers reach customers'
        # identity match by `import_runs.ACCOUNT_IDENTIFIER_FIELD` (`ssn`,
        # `driving_licence`, `tax_id`). They were never added here, so this case
        # was red from that commit on (`DEF-3287`).
        "customer_kind",
        "customer_ssn",
        "customer_driving_licence",
        "customer_tax_id",
    }
    # ⚠ **`parts` (2026-09-07) AND `payments` (2026-09-22) LAND ON THEIR OWN
    # MODULES' MODELS (`DEF-3287`)** — the same reason `accounts` has its own
    # entry, and the same red when they fell through to `Asset` instead.
    from apps.payments import models as payments_models
    from apps.work import models as work_models

    part_fields = {field.name for field in work_models.Part._meta.get_fields()}
    payment_fields = {field.name for field in payments_models.Payment._meta.get_fields()}
    payment_non_column = {
        "account_ref",  # → matched to an account by `payments.import_writer`
        "payer_name",  # → the same matcher, only when no account is named
        "paid_on",  # → `posted_at` AND `cleared_at`, one fact (BR-PAY-033)
        "reference",  # → `payments.confirmation`, the cheque number
    }
    destinations = {
        "accounts": (account_fields, account_non_column),
        "parts": (part_fields, set()),
        "payments": (payment_fields, payment_non_column),
    }
    for target, columns in import_runs.EXPLICIT_COLUMNS_BY_TARGET.items():
        fields, non_column = destinations.get(target, (asset_fields, asset_non_column))
        for column in columns:
            name = column["target"]
            assert (
                name in fields or name in non_column
            ), f"{target} offers {name}, which lands nowhere"
    # The three identifiers are named above as non-columns, so prove the
    # destination the comment claims rather than trusting it.
    assert {"customer_ssn", "customer_driving_licence", "customer_tax_id"} <= set(
        import_runs.ACCOUNT_IDENTIFIER_FIELD
    )


def test_cr025_sample_csvs_serve_header_plus_one_worked_row(seeded):
    """`GET /imports/sample?target=assets_*` — real header, one worked row,
    and the sample maps ITSELF at stage 2 (every header is its own alias)."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        for target in ("assets_meters", "assets_submeters", "assets_devices"):
            filename, body = import_runs.sample_csv(target)
            assert filename == f"{target}_sample.csv"
            rows = list(csv.reader(body.splitlines()))
            assert len(rows) == 2, "header + exactly one worked row (CR-025)"
            header, worked = rows
            declared = [c["target"] for c in import_runs.EXPLICIT_COLUMNS_BY_TARGET[target]]
            # ⚠ **THE HEADER IS THE COLUMN'S LABEL SINCE 2026-08-28
            # (`DEF-1077`)** — `Unit`, not `unit_ref`, because the PO opened
            # this file and could not tell what belonged in the column. So the
            # header is compared to the LABELS and the field order comes from
            # `sample_columns`, the one list `sample_csv` itself writes.
            assert header == [str(c["label"]) for c in import_runs.EXPLICIT_COLUMNS_BY_TARGET[target]]
            fields = [str(c["target"]) for c in import_runs.sample_columns(target)]
            assert fields == declared
            assert any(cell for cell in worked), "the worked row is not empty"
            detected = import_runs._auto_map(header, target)
            assert set(detected.values()) == set(declared), (
                f"{target}: the sample must map itself — unmapped: "
                f"{set(declared) - set(detected.values())}"
            )
            # …and to the RIGHT column, which a field-name header could not test.
            assert [detected[name] for name in header] == declared
            # ⛔ **THIS ASSERTION USED TO READ `== ""` AND THE REVERSAL IS
            # DELIBERATE — `DEF-962`, and it is CR-036 (i) happening a second
            # time.** The reasoning it carried — *"tenant references are never
            # guessed (and blank unit is itself the BR-AST-045 worked case)"* —
            # is the same reasoning `services_available` carried until DEF-754,
            # and it produced the same outcome one target along: the PO
            # downloaded this file and reported the column as ABSENT — *"you
            # dont have Unit field in CSV file that is downloaded; when you
            # upload assets you iwll need Units field mapping"*.
            #
            # It is worse here than it was for services, because BLANK IS
            # LAWFUL: BR-AST-045 loads an untagged meter into inventory, so a
            # file built from this template rehearses clean, reports 20 created
            # and 0 rejected, and seats twenty meters nowhere. A blank that is
            # also a valid answer cannot double as a worked example.
            #
            # A row THIS TENANT ALREADY HAS is not a guess — it is the same
            # index `AST.UNIT_ON_FILE` judges every imported row against. So
            # the cell is the tenant's own first unit when they have one, and
            # `""` only when they genuinely have none, which is the honest way
            # to say Premises → Units → Assets.
            by_name = dict(zip(fields, worked))
            seeded_units = metering_models.Unit.objects.filter(tenant=tenant).exists()
            if seeded_units:
                assert by_name.get("unit_ref", "") != "", (
                    f"{target}: the template's Unit cell is empty on a tenant that HAS "
                    "units, so the downloaded file shows no way to link a meter to a "
                    "place (DEF-962)"
                )
            else:
                assert by_name.get("unit_ref", "") == ""


# ══════════════════════════════════════════════════════════════════════════
# T2 · BR-AST-045 — the tagging table, at fixture scale (THE CENTRAL CASE)
# ══════════════════════════════════════════════════════════════════════════


def test_br_ast_045__the_tagging_table_at_fixture_scale(seeded):
    """THE WORKED SHAPE: 20 in → 3 rejected → 17 loaded → 14 tagged → 3 to
    inventory, and NONE of the blank-unit rows is an error (PO verbatim: "If
    they dont provide unit, its okay, we will still accept them").

    Proved RED first — before this lane, stage 1 refused the target by name
    (the failure is quoted in the module docstring).
    """
    tenant, actor = seeded
    with tenant_ctx(tenant):
        _assert_seats_empty(RESEAT.values())
        run_id = _validated(actor, "assets_meters", _meters_fixture(), METERS_MAPPING)
        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.counts["in"] == 20
        assert run.counts["checked"] == 20
        assert run.counts["errors"] == 3, _rejects(run_id)
        # ⛔ **SEVEN, NOT FOUR — AND THE THREE THAT MOVED IT ARE NOT THIS
        # LANE'S (DEF-1105, filed).** `AST.UNIT_BLANK_TO_INVENTORY` arrived
        # with DEF-1079 at 12:28 on 2026-08-27 and flags every blank-unit row
        # — rows 7, 8 and 20 of this fixture, which are precisely the three the
        # assertion five lines down proves are NOT rejects. That commit did not
        # update this number, so this test has been RED on the branch since it
        # landed. Corrected here rather than left, because a red nobody owns is
        # a red the next lane inherits and reads as its own.
        assert run.counts["warnings"] == 7

        rejects = _rejects(run_id)
        # Row 10 — E-2009 twice in one file (the in-file duplicate is the
        # ERROR; the on-file case is the write mode's to decide).
        assert "appears twice in this file" in rejects[10][0]
        # Row 12 — SCW-U-999 does not exist: CR-023's precedent, applied.
        assert rejects[12][0] == "Unit SCW-U-999 was not loaded."
        assert "Load the premise/unit first" in rejects[12][1]
        # Row 15 — the unit already has an active water meter (r10 row 588's
        # shape), and the inline correction is offered in words.
        assert "already has an active water meter" in rejects[15][0]
        assert "Load into inventory instead" in rejects[15][1]
        # ⚠ The blank-unit rows (7, 8, 20) are NOT among the rejects.
        assert {7, 8, 20}.isdisjoint(rejects.keys())

        before = assets_models.Asset.objects.filter(tenant_id=tenant.id).count()
        result = import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        paper = result["receipt"]
        assert paper["loaded"] == 17
        assert paper["rejected"] == 3
        # Seven, for `run.counts["warnings"]`'s reason above (DEF-1105).
        assert paper["flagged"] == 7
        assert paper["unit_tagged"] == 14
        assert paper["to_inventory"] == 3
        assert assets_models.Asset.objects.filter(tenant_id=tenant.id).count() - before == 17

        # One asset, one CURRENT unit — the structural guarantee, sampled.
        tagged = _asset("E-2001")
        seat = _current_unit(tagged)
        assert seat is not None
        assert tagged.status.behavior_class == "in_service"
        assert (
            assets_models.AssetAssignment.objects.filter(asset=tagged, to_date__isnull=True).count()
            == 1
        )
        # Blank unit → INVENTORY, not an error (BR-AST-045).
        spare = _asset("E-2007")
        assert spare.status.behavior_class == "available"
        assert _current_unit(spare) is None
        # The blank NUMBER row was allocated from the series (BR-AST-026).
        allocated = assets_models.AssetAssignment.objects.filter(
            unit__unit_no=RESEAT["SCW-U-008"],
            to_date__isnull=True,
            asset__type__code="meter",
            # The unit's own seeded WATER meter (W-…) also sits here; the row
            # under test is the ELECTRIC one this run created with a SERIES
            # number (BR-AST-026's M- prefix).
            asset__asset_no__startswith="M-",
        ).select_related("asset")
        assert allocated.count() == 1
        # W → default ×1, performed AND flagged (never silent).
        assert _asset("E-2012").multiplier == Decimal("1")
        assert _asset("E-2013").multiplier == Decimal("1")
        # The valuation columns landed (stored 4dp — rule 2/D10).
        assert _asset("E-2001").purchase_cost == Decimal("289.0000")
        assert _asset("E-2001").certification_due == date(2027, 5, 4)
        assert _asset("E-2001").supplier == "Itron Inc"
        # An unknown meter type loads UNSET and flagged, never guessed.
        assert _asset("E-2016").meter_type is None


def test_inline_correction__load_into_inventory_instead_works(seeded):
    """r10 WFL-01.meters.3: *"Fix the rejects here — no need to re-upload."*
    The rejected unit-taken row is fixed by CLEARING its UNIT_REF cell — one
    PATCH — after which stages 2–3 re-run and the row is ACCEPTED to
    inventory (BR-AST-045)."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", _meters_fixture(), METERS_MAPPING)
        assert 15 in _rejects(run_id)

        answer = import_runs.fix_row(actor, run_id, 15, {"values": {"UNIT_REF": ""}})
        assert answer["fixed_row"]["raw"]["UNIT_REF"] == ""
        # The fix sends the run back to stage 1: a load over the stale verdict
        # must be impossible until stages 2–3 re-judge.
        assert answer["status"] == "extracted"
        with pytest.raises(errors.BizError):
            import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})

        import_runs.transform(actor, run_id, {"mapping": METERS_MAPPING, "row_handling": ALL_OFF})
        import_runs.validate(actor, run_id)
        rejects = _rejects(run_id)
        assert 15 not in rejects, "the cleared unit cell must be accepted (inventory)"
        assert len(rejects) == 2

        result = import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        assert result["receipt"]["loaded"] == 18
        assert result["receipt"]["to_inventory"] == 4
        assert _asset("W-6001").status.behavior_class == "available"


def test_fix_row_refuses_on_a_committed_run(seeded):
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", _meters_fixture(), METERS_MAPPING)
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        with pytest.raises(errors.BizError):
            import_runs.fix_row(actor, run_id, 12, {"values": {"UNIT_REF": "SCW-U-001"}})


# ══════════════════════════════════════════════════════════════════════════
# T2 · write modes — insert-new-only · insert-and-update (replace WITHDRAWN)
# ══════════════════════════════════════════════════════════════════════════


def test_insert_and_update_overrides_billing_fields_and_audits_the_change(seeded, audit_rows):
    """⛔ **RENAMED FROM `…touches_spec_fields_and_never_billing_ones` ON
    2026-10-03 (`DEF-3287`), BECAUSE THE RULE IT WAS NAMED FOR WAS SUPERSEDED.**
    PO ruling 2026-09-30, verbatim: *"we need to override it in case of
    upload"* (`DEF-AST-8099`, decision log of that day) — a re-uploaded sheet
    now overrides the 💲 fields, multiplier included, and `BR-AST-034`'s
    *"billing-affecting never via upload"* is SUPERSEDED. This case could not
    notice: from 2026-09-02 `E-2006` was never created (its seat was taken, see
    `RESEAT`), so it went red on that and the ruling arrived behind it.

    What the ruling KEPT is asserted instead of what it removed, so the case
    is no weaker: the new value lands, and the change is audited before/after
    (`BR-AST-012`, hard rule 7)."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", _meters_fixture(), METERS_MAPPING)
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        original_multiplier = _asset("E-2006").multiplier

        # The same file again, with a changed supplier and multiplier on E-2006.
        content = _meters_fixture(
            _fixture("assets_meters.csv").replace(
                "E-2006,ami,electric,ami,200,SCW-U-047,Itron Inc,OpenWay CT,2026-05-07,2027-05-07,2031-05-07,Itron Inc,412.0000",
                "E-2006,ami,electric,ami,50,SCW-U-047,Itron Inc,OpenWay CT,2026-05-07,2027-05-07,2031-05-07,Meter Supply Co,412.0000",
            )
        )
        rerun = _validated(actor, "assets_meters", content, METERS_MAPPING)
        result = import_runs.load(actor, rerun, {"write_mode": "upsert", "approved": True})
        assert result["receipt"]["loaded"] >= 1
        row = _asset("E-2006")
        assert row.supplier == "Meter Supply Co", "spec fields update on upsert"
        assert original_multiplier == Decimal("200")
        assert row.multiplier == Decimal("50"), (
            "a re-upload overrides the multiplier (PO 2026-09-30, DEF-AST-8099)"
        )
        edits = [
            r
            for r in audit_rows
            if r["action"] == "asset.updated" and str(r["entity_id"]) == str(row.id)
        ]
        assert edits, "the override is audited (BR-AST-012)"
        assert Decimal(str(edits[-1]["before"]["multiplier"])) == Decimal("200")
        assert Decimal(str(edits[-1]["after"]["multiplier"])) == Decimal("50")


def test_insert_new_only_rejects_a_row_already_on_file_and_says_so(seeded):
    """⛔ **RENAMED FROM `…skips_an_existing_number…` — the PO chose the word
    (2026-08-27): *"in case of insert - reject it"*.**

    A skip reads on a receipt as *"left unchanged"*; a reject reads as *"this
    row did not load"*. Only one of those is true, and the operator's next
    action differs. `skipped_existing` is still SERVED as 0 so one receipt
    screen renders every target — the accounts loader still skips."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", _meters_fixture(), METERS_MAPPING)
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        before = assets_models.Asset.objects.filter(tenant_id=tenant.id).count()
        # The IGNORED LEGACY column is edited so the re-upload's SHA-256
        # differs: a byte-identical file cannot COMMIT twice at all
        # (`uq_import_runs_idempotency` — hard rule 6), which is its own law
        # and not this case's.
        rerun = _validated(
            actor,
            "assets_meters",
            _meters_fixture(_fixture("assets_meters.csv").replace("LG-88", "LG-99")),
            METERS_MAPPING,
        )
        result = import_runs.load(actor, rerun, {"write_mode": "insert", "approved": True})
        # ⚠ **NOTHING IS WRITTEN, AND THAT PART IS UNCHANGED.** What changed is
        # WHERE the rows stop and what they are called. The 16 rows whose
        # external reference is already on file are REJECTED — at stage 3 now,
        # because the run states its write mode at stage 1 (CR-046 wave B) and
        # `AST.NUMBER_ON_FILE` is an ERROR under `insert`. The old assertion
        # counted them on the receipt as `skipped_existing`, which is served as
        # 0 on this target now.
        assert result["receipt"]["skipped_existing"] == 0
        assert assets_models.Asset.objects.filter(tenant_id=tenant.id).count() - before == 0
        rejected = metering_models.ImportRunRow.objects.filter(
            run_id=rerun,
            outcome="rejected",
            problem__contains="already carries this external reference",
        )
        assert rejected.count() == 16, "each rejected row says so on the row"


def test_oq_580__replace_the_batch_is_refused_by_name(seeded):
    """⛔ **`Replace the batch` IS REFUSED, AND THE QUESTION IT NAMES CHANGED.**

    This test was `test_oq_326__…` and it asserted the same refusal for a
    narrower reason: OQ-326 asked what replace does to ASSETS in the database
    and not in the file, and only the three assets targets refused.

    **CR-042 (PO 2026-08-27) withdrew the mode from every import**, so the
    refusal now covers all six targets of this rail and names **OQ-580** — the
    question the withdrawal itself raises: with the mode gone, how does a
    utility retire a premise it no longer serves? OQ-326 is marked MOOT rather
    than deleted; the control it asked about no longer exists.

    ⚠ **The assertion is deliberately unchanged in SHAPE** — both the rehearsal
    and the commit refuse, independently, and nothing is written on the way to
    either. That property is what makes the withdrawal safe, and it is the same
    property whichever question the refusal cites.
    """

    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", _meters_fixture(), METERS_MAPPING)
        for verb in (
            lambda: import_runs.dry_run(actor, run_id, "replace"),
            lambda: import_runs.load(actor, run_id, {"write_mode": "replace"}),
        ):
            with pytest.raises(errors.BizError) as caught:
                verb()
            assert caught.value.br_ref == "OQ-580"
            assert caught.value.params["oq"] == "OQ-580"
        # And nothing was written on the way to either refusal.
        assert not metering_models.ImportRunRow.objects.filter(
            run_id=run_id, outcome="loaded"
        ).exists()


# ══════════════════════════════════════════════════════════════════════════
# T1 · sub-meters — parent law, allocation share
# ══════════════════════════════════════════════════════════════════════════


def test_submeters__parent_rules_and_allocation_share(seeded):
    from apps.assets import services as assets_services

    tenant, actor = seeded
    with tenant_ctx(tenant):
        # The fixture's retired-master case (SM-9008 → W-5011). DEF-597 fixed
        # (CR-028 debt sweep D1): the sample seeder now performs this
        # retirement ITSELF — the workaround that retired it here always hit
        # BIZ-IMMUTABLE the moment the seeder was fixed. Retire through the
        # real service only if some seed ordering left it active, and either
        # way judge the case against a genuinely terminal master.
        retired_master = assets_models.Asset.objects.select_related("status").get(
            tenant_id=tenant.id, asset_no="W-5011"
        )
        if retired_master.status.behavior_class != "terminal":
            assets_services.retire_asset(actor, retired_master.id, {"reason": "replaced"})
        run_id = _validated(
            actor, "assets_submeters", _fixture("assets_submeters.csv"), SUBMETERS_MAPPING
        )
        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.counts["in"] == 10
        assert run.counts["errors"] == 4, _rejects(run_id)

        rejects = _rejects(run_id)
        assert rejects[6][0] == "Parent meter M-GONE-77 was not loaded."
        assert rejects[7][0] == "This row names no parent master meter."
        assert "is not active" in rejects[8][0], "a RETIRED master cannot take a sub"
        assert "appears twice in this file" in rejects[10][0]
        # Blank unit (row 9) is NOT an error — inventory, with its parent kept.
        assert 9 not in rejects

        result = import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        assert result["receipt"]["loaded"] == 6
        assert result["receipt"]["unit_tagged"] == 5
        assert result["receipt"]["to_inventory"] == 1

        sub = _asset("SM-9001")
        assert sub.type.code == "sub_meter"
        assert sub.parent_asset is not None and sub.parent_asset.asset_no == "M-MASTER-01"
        # ALLOC_PCT: 40 stored to the 6dp percentage column; blank = metered,
        # not allocated → NULL.
        assert _asset("SM-9004").allocation_share_pct == Decimal("40")
        assert _asset("SM-9001").allocation_share_pct is None
        spare = _asset("SM-9009")
        assert spare.status.behavior_class == "available"
        assert spare.parent_asset is not None


def test_submeters__cross_premises_and_over_allocation_warn(seeded):
    """The two sub-meter WARNINGS the committed fixture has no case for,
    exercised on a three-row synthetic: a sub whose unit is on a DIFFERENT
    premises than its master's seat, and two shares under one master totalling
    130%. Warnings flag — all three rows still LOAD (BR-MET-100's posture)."""
    header = (
        "METER_NO,METER_TYPE,SERVICE,READ_METHOD,MULTIPLIER,UNIT_REF,MFR,MODEL,"
        "INSTALL_DT,CERT_DUE,WARRANTY_END,SUPPLIER,COST,PARENT_MTR,ALLOC_PCT"
    )
    rows = [
        # W-5001's seat is SCW-U-002 (house #2); SCW-U-003 is house #3.
        "SM-9101,sub_meter,water,manual,1,SCW-U-003,Neptune,T-10 Sub,2026-06-01,,,,156.0000,W-5001,",
        "SM-9102,sub_meter,water,manual,1,SCW-U-042,Neptune,T-10 Sub,2026-06-01,,,,156.0000,M-MASTER-01,60",
        "SM-9103,sub_meter,water,manual,1,SCW-U-043,Neptune,T-10 Sub,2026-06-01,,,,156.0000,M-MASTER-01,70",
    ]
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(
            actor, "assets_submeters", "\n".join([header, *rows]) + "\n", SUBMETERS_MAPPING
        )
        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.counts["errors"] == 0
        assert run.counts["warnings"] == 3
        flagged = {
            row.row_no: row.problem
            for row in metering_models.ImportRunRow.objects.filter(run_id=run_id, outcome="flagged")
        }
        assert "not on the same premises as its master W-5001" in flagged[1]
        assert "total 130%" in flagged[2]
        assert "total 130%" in flagged[3]
        result = import_runs.load(actor, run_id, {"write_mode": "insert"})
        assert result["receipt"]["loaded"] == 3, "warnings flag; they never stop a row"


# ══════════════════════════════════════════════════════════════════════════
# T1 · devices — premises law, next-test derivation, export capacity
# ══════════════════════════════════════════════════════════════════════════


def test_devices__premises_rules_derived_next_test_and_export(seeded):
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(
            actor, "assets_devices", _devices_fixture(), DEVICES_MAPPING
        )
        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.counts["in"] == 10
        assert run.counts["errors"] == 2, _rejects(run_id)
        # ⛔ **TWO, NOT ONE, AND BOTH HALVES OF THE MOVE ARE RECORDED.**
        # `AST.UNIT_BLANK_TO_INVENTORY` (DEF-1079) flags a row that seats
        # NOWHERE, and row 9 of this fixture names neither a unit nor a
        # premises — so it earns a warning it never used to get. It briefly
        # flagged SEVEN more: the rule read `mapped["premises"]` where stage 2
        # writes `premises_ref`, so every premises-seated device was told it
        # was going to inventory (DEF-1106, fixed in the same commit as this
        # line).
        assert run.counts["warnings"] == 2

        rejects = _rejects(run_id)
        assert rejects[6][0] == "Premises P-99999 was not loaded."
        assert "appears twice in this file" in rejects[10][0]
        # COM-4502 (row 9): blank premises AND blank unit → inventory, no error.
        assert 9 not in rejects

        result = import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        assert result["receipt"]["loaded"] == 8
        assert result["receipt"]["unit_tagged"] == 7
        assert result["receipt"]["to_inventory"] == 1

        backflow = _asset("BF-3301")
        assert backflow.type.code == "backflow"
        assert backflow.certification_due == date(2027, 3, 1)
        seat = _current_unit(backflow)
        assert seat is not None, "a single-unit premises seats the device on its one unit"
        # BF-3303: TEST_FREQ 12, NEXT_TEST blank → derived install + 12 months,
        # exactly where stage 3 said it would be (W → default).
        derived = _asset("BF-3303")
        assert derived.test_interval_months == 12
        assert derived.certification_due == date(2027, 4, 7)
        # EXPORT_KW rides the inverter (a capacity, never money — BR-AST-025).
        assert _asset("PV-1204").export_capacity_kw == Decimal("7.6")
        assert _asset("EV-2101").export_capacity_kw is None
        assert _asset("COM-4502").status.behavior_class == "available"


# ══════════════════════════════════════════════════════════════════════════
# T4 · rollback — reversed to inventory; read-carrying meters KEPT
# ══════════════════════════════════════════════════════════════════════════


def test_rollback_reverses_to_inventory_and_keeps_read_carrying_meters(seeded, monkeypatch):
    """The AST-04 callout, walked: after a rollback the created assets are
    back in Inventory with their assignments CLOSED — except the one given
    reads, which is KEPT and reported on the receipt by count and on its row
    by sentence. Deactivate, never delete: every row still exists."""
    from apps.assets import seams as assets_seams

    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", _meters_fixture(), METERS_MAPPING)
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        keeper = _asset("E-2001")

        real_count = assets_seams.read_count_for_asset

        def with_reads(asset_id):
            return 3 if str(asset_id) == str(keeper.id) else real_count(asset_id)

        monkeypatch.setattr(assets_seams, "read_count_for_asset", with_reads)
        result = import_runs.rollback(staff_actor(tenant, "system_admin", "rb@scw.test"), run_id)
        paper = result["receipt"]
        assert result["status"] == "rolled_back"
        assert paper["kept_reads"] == 1
        assert result["counts"]["rolled_back"] == 16

        kept = _asset("E-2001")
        assert kept.status.behavior_class == "in_service", "the read-carrying meter is KEPT"
        assert _current_unit(kept) is not None
        reversed_row = _asset("E-2002")
        assert reversed_row.status.behavior_class == "available"
        assert _current_unit(reversed_row) is None, "the assignment is closed on rollback"
        kept_row = metering_models.ImportRunRow.objects.get(
            run_id=run_id, created_record_id=keeper.id
        )
        assert "already carries reads" in kept_row.problem
        # Nothing was deleted — 17 created rows all still exist.
        assert (
            assets_models.Asset.objects.filter(
                tenant_id=tenant.id,
                id__in=metering_models.ImportRunRow.objects.filter(
                    run_id=run_id, created_record_id__isnull=False
                ).values_list("created_record_id", flat=True),
            ).count()
            == 17
        )


# ══════════════════════════════════════════════════════════════════════════
# T6 · volume — the async bar crossed with REAL rows; the 100k generation
# ══════════════════════════════════════════════════════════════════════════


def _generated_rows(tmp_path: Path, rows: int) -> str:
    spec = importlib.util.spec_from_file_location("make_100k", FIXTURES / "make_100k.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path / f"meters_{rows}.csv"
    module.generate(out, rows=rows)
    return out.read_text()


@pytest.mark.slow
def test_t6__six_thousand_real_rows_cross_the_async_bar_and_complete(seeded, tmp_path, monkeypatch):
    """CR-026 at REAL volume on the meters target: 6,000 generated rows (over
    `ASYNC_ROW_BAR = 5_000`, untouched) answer 202-shaped (`deferred: true`)
    at transform, validate AND load; each stage then completes in the worker
    path and the gauge reads `done`.

    ⚠ The full 100,000-row file is NOT walked in CI — extract alone stages
    100k rows and the suite would spend minutes proving what 6,000 already
    proves about the BAR. The 100k half is the GENERATION smoke below
    (`test_t6__the_100k_file_generates_at_the_cap`), stated per the task.
    """
    from django.test import override_settings

    from core import jobs as core_jobs

    tenant, actor = seeded
    # ⚠ EACH STAGE RE-ENTERS THE TENANT CONTEXT: `core_jobs.run_pending` runs
    # the job body under the RECORD's own tenant (B3's worker posture) and
    # exits that context on the way out — so the ambient context this test
    # entered does not survive a worker call, exactly as it would not in
    # production, where the poller is a fresh request.
    with override_settings(IMPORT_PROGRESS_ISOLATED=False):
        with tenant_ctx(tenant):
            assert import_runs.ASYNC_ROW_BAR == 5_000, "the ratified bar, untouched"
            # ⚠ RE-SEATED, FOR `RESEAT`'s REASON (`DEF-3287`): the generator
            # cycles `SCW-U-001`…, every one of which holds a seeded electric
            # meter since 2026-09-02, so all 6,000 claims lost to the seed and
            # `unit_tagged` read 0. Its real seats move to empty ones; its
            # deliberately bad refs (`SCW-U-9xx`) and blanks are untouched.
            generated = _generated_rows(tmp_path, 6_000)
            cycled = sorted(
                {
                    row["UNIT_REF"]
                    for row in csv.DictReader(io.StringIO(generated))
                    if row["UNIT_REF"].startswith("SCW-U-0")
                }
            )
            assert len(cycled) <= len(EMPTY_SEATS), "more seats than empty units"
            _assert_seats_empty(EMPTY_SEATS[: len(cycled)])
            content = _reseated(generated, dict(zip(cycled, EMPTY_SEATS)))
            run = _extract(actor, "assets_meters", content, "assets_meters_6000.csv")
            assert run["counts"]["in"] == 6_000
            run_id = run["id"]

            transform = import_runs.transform(
                actor, run_id, {"mapping": METERS_MAPPING, "row_handling": ALL_OFF}
            )
            assert transform["deferred"] is True and transform["stage"] == "transform"
            core_jobs.run_pending(transform["job_id"])
        assert metering_models.ImportRun.objects.get(pk=run_id).status == "transformed"

        with tenant_ctx(tenant):
            validate = import_runs.validate(actor, run_id)
            assert validate["deferred"] is True and validate["stage"] == "validate"
            core_jobs.run_pending(validate["job_id"])
        run_row = metering_models.ImportRun.objects.get(pk=run_id)
        assert run_row.status == "validated"
        assert run_row.counts["checked"] == 6_000

        with tenant_ctx(tenant):
            # The generator cycles 48 units, so the one-active-meter rule
            # rejects every later claim on a seat — the approval bar is
            # legitimately crossed and the commit carries the second approval
            # (BR-MET-098).
            figures = import_runs.dry_run(actor, run_id, "insert")
            assert figures["approval"]["required"] is True

            load = import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
            assert load["deferred"] is True and load["stage"] == "load"
            core_jobs.run_pending(load["job_id"])
        finished = metering_models.ImportRun.objects.get(pk=run_id)
        assert finished.status == "loaded"
        gauge = finished.importrunprogress_set.first()
        assert gauge is not None and gauge.state == "done" and gauge.stage == "load"
        with tenant_ctx(tenant):
            paper = import_runs.receipt(finished)["receipt"]
        assert paper["loaded"] == finished.counts["created"]
        assert paper["loaded"] > 0
        # ⚠ **`cycled`, NOT `fixture.UNIT_COUNT` (`DEF-3287`, 2026-10-03).**
        # It read 48 until 2026-09-02, when `CR-062` J3/J4 changed it to
        # `UNIT_COUNT` (50) on the ground that this is *"the count the
        # GENERATOR cycles"* — but `make_100k.py` cycles `i % 48` and never
        # read the fixture, so the edit made the two disagree rather than
        # stopping them. The count is now read off the generated FILE itself,
        # which is the only source that cannot disagree with it.
        assert paper["unit_tagged"] == len(cycled), (
            f"one seat per unit — the {len(cycled)} winners"
        )


def test_t6__the_100k_file_generates_at_the_cap(tmp_path):
    """The 100,000-row half, smoked: the file GENERATES at exactly CR-026's
    cap, deterministically, and the runner's own cap admits it (100_000 ≤
    CSV_ROW_CAP — the 100,001st row would refuse at upload)."""
    content = _generated_rows(tmp_path, 100_000)
    lines = content.count("\n")
    assert lines == 100_001  # header + 100,000 rows
    assert import_runs.CSV_ROW_CAP == 100_000


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/B16@2026-08-22 §4.7/§4.7a/§4.7b · BR-AST-045/046 (PO 2026-08-22, verbatim in CR-028's record) · AST-W3-T7
# generated: 2026-08-22 by the CR-028 AST-W3 lane
# checklist: A✔ B✔ C✔ D✔(service-level; the routes are pass-throughs covered by the CR-023/026 API cases) E=deferred(the frontend half is vitest's) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr028_import_targets.py · tests/test_cr023_*.py · tests/test_cr026_background_stages.py (no regression)
# exceptions: the RED-first proof ran the central case in a `git worktree` of the prior HEAD (quoted in the module docstring) — the working tree is never moved (hard-won law 11's seventh occurrence) · the read-carrying rollback case patches the ASSETS module's own read seam rather than manufacturing a meter_reads row: what is under test is keep-and-report, not the reads schema · the 100k file is generated and counted, not walked through the runner in CI — stated in the T6 case per the task's own alternative · the volume case is marked slow
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
