# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 AST-W3-T8 (BR-AST-048, PO 2026-08-22 — seeded default
#           mapping templates, tenant copy-on-write, detect order)
#           Screens: SET-04 (the import_mappings reference list) ·
#           WFL-01.*.1 ("Header row recognised as …") · WFL-01.*.2 ("Save
#           mapping as template")
# Rules:    BR-AST-048 (one system default per assets target, GENERATED from
#           the same contract as the CR-025 sample; copy-on-write; detect
#           order exact-match → tenant-beats-default → most-recently-used) ·
#           BR-TEN-036 (system rows deactivatable, never deletable) ·
#           BR-TEN-031 (tenancy owns the import_mappings table — every write
#           goes through tenancy's own services)
# Tests:    this file — the T8 suite
# Impacts:  apps/tenancy/models.py (ImportMapping target/mapping/last_used_at)
#           · apps/tenancy/services.py (handler + seed + save service) ·
#           apps/metering/import_runs.py (generator · extract recognition ·
#           save-template) · apps/metering/seams.py
# ───────────────────────────────────────────────────────
"""BR-AST-048 — the seeded default mapping templates, end to end.

RED-FIRST PROOF (r11 step 2d): `test_the_three_defaults_seed_for_a_fresh_
tenant` was run against the tree BEFORE T8's change landed and failed with

    assert 0 == 3
     +  where 0 = <QuerySet []>.count()
    FAILED tests/test_cr028_mapping_templates.py::
        test_the_three_defaults_seed_for_a_fresh_tenant

— the `import_mappings` list was deliberately seeded with NOTHING (the
2026-08-16 decision BR-AST-048 supersedes for the three GENERATED defaults),
and the table had no column a mapping could even live in (DEF-512).
"""

import csv
import io

import pytest

from apps.metering import import_runs
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services

from tests.test_cr028_import_targets import METERS_MAPPING, _extract, _validated
from tests.test_cr028_seed import seeded, silvercreek  # noqa: F401 — fixture chain
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

DEFAULT_NAMES = {
    "assets_meters": "Meters default",
    "assets_submeters": "Sub-meters default",
    "assets_devices": "Devices default",
    # BR-CUS-075 (PO 2026-08-24) — the fourth, on the same mechanism.
    "accounts": "Accounts default",
    # ⚠ **THE FIFTH AND SIXTH — PO RULING 2026-09-07, AND THEY ARE THE TWO A
    # UTILITY LOADS FIRST.** Verbatim: *"it is required for - Premises, Units,
    # Meters, Sub meter,s Assets, Parts, Accounts, Reading - including all
    # readings - Flat, Demand based, Seasonal, Peak , off peak, etc"*. The
    # README's build order is Premises → Units → Assets → Accounts, so the two
    # imports every migration BEGINS with were the two with no starter while
    # everything downstream of them had one.
    "premises": "Premises default",
    "units": "Units default",
    # ⚠ **THE SEVENTH — `CR-077`, 2026-09-07.** The same ruling's *"Parts"*,
    # built once `parts` became a target of the one runner rather than an
    # importer of its own. The table is `work`'s and the load goes through
    # `work.import_writer`; the DEFAULT MAPPING is metering's like every other
    # target's, because the mapping is a property of the runner.
    "parts": "Parts default",
    # ⚠ **THE EIGHTH — the lockbox payments target, `c8bce7c8a` (2026-09-22).**
    # Appended to `DEFAULT_MAPPING_TEMPLATES` with its target; this pin was not
    # moved, so two cases read red on a correct product (`DEF-MET-9247`).
    "payments": "Payments default",
}


def _defaults(tenant):
    return tenancy_models.ImportMapping.objects.filter(tenant=tenant, is_system=True)


def test_the_three_defaults_seed_for_a_fresh_tenant(silvercreek):
    """BR-AST-048 + BR-CUS-075: provisioning leaves ONE system default per
    target that has one, on the SET-04 list — named exactly as ruled,
    target-tagged, active.

    ⚠ **THE NAME SAYS THREE AND THE COUNT SAYS FOUR, DELIBERATELY.** This test
    is what made CR-030 W1 REMOVE an accounts default it had added without a
    rule behind it, and that was the right call on the evidence then. The PO
    supplied the rule on 2026-08-24 (BR-CUS-075), pointing at Settings →
    Reference data → Finance → Import mappings showing `0` — *"you might hav to
    add account import mapping tempalte to this settings"* / *"we did that for
    other improt also"*. The function name is left alone so `git log -S` still
    finds both halves of that story on one identifier.

    ⚠ **AND THE COUNT IS SIX SINCE 2026-09-07.** This docstring read *"`premises`
    and `units` still have NO default, so the count is four rather than six: a
    signature covers only what was shown"* — correct, and correct only until
    they were shown. The PO named them, first in the list, on 2026-09-07. The
    same sentence is now the record of both halves: what a lane may not add on
    its own, and what happens the day the PO adds it.
    """
    with tenant_ctx(silvercreek):
        rows = _defaults(silvercreek)
        assert rows.count() == len(DEFAULT_NAMES)
        by_target = {row.target: row for row in rows}
        assert set(by_target) == set(DEFAULT_NAMES)
        for target, name in DEFAULT_NAMES.items():
            row = by_target[target]
            assert row.name == name
            assert row.active is True
            assert row.is_system is True
            assert isinstance(row.mapping, dict) and row.mapping


def test_defaults_are_generated_not_hand_written(silvercreek):
    """The template and the CR-025 sample derive from ONE source (the target's
    declared columns), so the two cannot drift (DEF-521's shape, prevented):
    the default's source headers ARE the sample CSV's header row."""
    with tenant_ctx(silvercreek):
        for row in _defaults(silvercreek):
            _filename, body = import_runs.sample_csv(row.target)
            sample_header = next(csv.reader(io.StringIO(body)))
            # ⚠ **THE HEADER IS THE COLUMN'S LABEL SINCE 2026-08-28
            # (`DEF-1077`), AND THAT IS EXACTLY WHY THIS TEST MATTERS.** A
            # mapping template is matched by its SOURCE HEADER SET, so a
            # default left keyed on field names would no longer recognise the
            # file it was generated from — the drift this test exists to catch,
            # arriving from the other direction.
            assert sorted(row.mapping.keys()) == sorted(sample_header)
            by_label = {
                str(column["label"]): column["target"]
                for column in import_runs.sample_columns(row.target)
            }
            for source, spec in row.mapping.items():
                # 1:1, and the DESTINATION is still a field name — it is what
                # `_apply_mapping` writes to. Only the source key is a label.
                assert spec["target"] == by_label[source]


def test_reseeding_is_idempotent_and_backfills(silvercreek):
    """`seed_demo --tenant` on an EXISTING tenant: a replay creates nothing;
    a tenant missing one default (deactivated is fine — deleted cannot happen,
    BR-TEN-036) gets exactly the missing one back."""
    actor = staff_actor(silvercreek, "system_admin", "t8@scw.test")
    with tenant_ctx(silvercreek):
        before = _defaults(silvercreek).count()
        tenancy_services.seed_reference_data_for_tenant(silvercreek, actor)
        assert _defaults(silvercreek).count() == before == len(DEFAULT_NAMES)


def test_a_system_default_is_never_deletable_and_its_mapping_never_tenant_edited(silvercreek):
    """BR-TEN-036 + BR-AST-048's "never mutated": delete refuses; the lookup
    update surface accepts code/name only, so the MAPPING cannot be reached by
    a tenant edit at all — renaming is allowed and leaves the mapping alone."""
    from core import errors as core_errors

    actor = staff_actor(silvercreek, "system_admin", "t8b@scw.test")
    with tenant_ctx(silvercreek):
        row = _defaults(silvercreek).get(target="assets_meters")
        with pytest.raises(core_errors.BizError):
            tenancy_services.delete_lookup_entry(actor, "import_mappings", row.pk)
        with pytest.raises(core_errors.ApiError):
            tenancy_services.update_lookup_entry(actor, "import_mappings", row.pk, {"mapping": {}})
        renamed = tenancy_services.update_lookup_entry(
            actor, "import_mappings", row.pk, {"name": "Our meters map"}
        )
        assert renamed["name"] == "Our meters map"
        row.refresh_from_db()
        assert row.mapping, "renaming never touches the mapping"


def test_save_mapping_as_template_is_copy_on_write(seeded):
    """Stage 2's "Save mapping as template": ALWAYS a new tenant row — even
    under a default's own name — and the default is left byte-identical."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(
            actor,
            "assets_meters",
            (FIXTURES / "assets_meters.csv").read_text(),
            METERS_MAPPING,
        )
        default = _defaults(tenant).get(target="assets_meters")
        default_mapping_before = dict(default.mapping)

        saved = import_runs.save_mapping_template(actor, run_id, {"name": "Meters default"})
        assert saved["is_system"] is False
        assert saved["id"] != str(default.pk)
        default.refresh_from_db()
        assert default.mapping == default_mapping_before
        assert default.is_system is True

        # A second save under the same name is ANOTHER new row (codes differ).
        again = import_runs.save_mapping_template(actor, run_id, {"name": "Meters default"})
        assert again["id"] not in (saved["id"], str(default.pk))
        assert (
            tenancy_models.ImportMapping.objects.filter(
                tenant=tenant, is_system=False, name="Meters default"
            ).count()
            == 2
        )


def test_detect_order__exact_match_then_tenant_beats_default(seeded):
    """BR-AST-048's golden path: a file whose header row IS the sample's is
    recognised as the system default with ZERO mapping work — and the moment a
    tenant template matches the same header set, the tenant's wins."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        _filename, body = import_runs.sample_csv("assets_meters")
        run = _extract(actor, "assets_meters", body, "sample_roundtrip.csv")
        recognised = run["recognised_template"]
        assert recognised is not None
        assert recognised["name"] == "Meters default"
        assert recognised["is_system"] is True
        # The detected mapping is the TEMPLATE's — 1:1, every column, no
        # alias guessing left to do. ⚠ The header row is the column's LABEL
        # since 2026-08-28 (`DEF-1077`) and the destination is still the field,
        # so this is `label → field` rather than the identity it used to be.
        header = next(csv.reader(io.StringIO(body)))
        by_label = {
            str(column["label"]): column["target"]
            for column in import_runs.sample_columns("assets_meters")
        }
        assert run["detected_mapping"] == {name: by_label[name] for name in header}
        assert run["mapping_id"] == recognised["id"]

        # Save a tenant template over the same header set…
        import_runs.transform(
            actor,
            run["id"],
            {"mapping": {name: by_label[name] for name in header}, "row_handling": {}},
        )
        mine = import_runs.save_mapping_template(actor, run["id"], {"name": "Meter fleet v2"})

        # …and the SAME file now recognises the tenant's, not the default.
        rerun = _extract(actor, "assets_meters", body, "sample_roundtrip2.csv")
        assert rerun["recognised_template"]["id"] == mine["id"]
        assert rerun["recognised_template"]["is_system"] is False
        # The winner's clock moved — most-recently-used breaks future ties.
        row = tenancy_models.ImportMapping.objects.get(pk=mine["id"])
        assert row.last_used_at is not None


@pytest.mark.parametrize(
    ("target", "name"),
    [("premises", "Premises default"), ("units", "Units default")],
)
def test_the_premises_and_units_samples_round_trip_with_zero_mapping_work(seeded, target, name):
    """⚠ **THE PROMISE THE OTHER FOUR STARTERS MAKE, NOW MADE BY THE TWO A
    UTILITY LOADS FIRST** (PO ruling 2026-09-07).

    Download the sample, upload it, and stage 2 is already done: the file is
    recognised as the system default and every header is mapped to its own
    field. Asserted here for premises and units specifically, because these two
    reach `default_import_mapping_entries` by a DIFFERENT ROUTE from the other
    four — their columns are DERIVED from the model's `_meta` rather than
    declared in `EXPLICIT_COLUMNS_BY_TARGET` (BR-MET-088). A generated default
    that read the declared dict raised `KeyError('premises')`; one that reads
    `sample_columns` gets the same list `sample_csv` writes, which is what makes
    the round trip true rather than merely likely.
    """
    tenant, actor = seeded
    with tenant_ctx(tenant):
        _filename, body = import_runs.sample_csv(target)
        run = _extract(actor, target, body, f"{target}_sample_roundtrip.csv")

        recognised = run["recognised_template"]
        assert recognised is not None, (
            f"the shipped {target} sample was not recognised as any template — the starter and "
            "the sample have drifted, which is the one thing generating both from one source "
            "is supposed to make impossible"
        )
        assert recognised["name"] == name
        assert recognised["is_system"] is True
        assert run["mapping_id"] == recognised["id"]

        # ZERO mapping work: every header already points at its own field.
        header = next(csv.reader(io.StringIO(body)))
        by_label = {
            str(column["label"]): column["target"]
            for column in import_runs.sample_columns(target)
        }
        assert run["detected_mapping"] == {label: by_label[label] for label in header}


def test_a_file_nobody_has_a_template_for_still_auto_detects_by_alias(seeded):
    """The fixture headers (METER_NO …) match no stored template — the alias
    auto-detect keeps working exactly as before, and nothing is 'recognised'.

    ⚠ **AMENDED 2026-08-30 — `METER_NO` NOW DETECTS AS `external_ref`, NOT
    `asset_no`, AND THE RE-POINTING IS THE POINT OF A PO RULING (2026-08-27,
    BR-AST-049 / CR-046).** `asset_no` used to mean *"the number to give this
    meter"*; it now means *"an EXISTING SMARTBillHub number"*, and a first
    migration file's `METER_NO` column is the exact opposite of that — every
    cell of it is the OLD system's number, which this product has never issued.
    Leaving the alias where it was would have auto-mapped a utility's whole
    estate onto the one column that now REFUSES it (`AST.NUMBER_NOT_ON_FILE`),
    and the operator would meet one identical error per row on a file the
    product's own auto-mapper built. Pointed at `external_ref` the same header
    lands where BR-AST-049 says the utility's own reference belongs.

    So the assertion is not merely renamed: both halves are pinned, because
    detecting it as `asset_no` again is the regression the ruling closed.
    """
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run = _extract(
            actor,
            "assets_meters",
            (FIXTURES / "assets_meters.csv").read_text(),
            "legacy_headers.csv",
        )
        assert run.get("recognised_template") is None
        assert run["detected_mapping"]["METER_NO"] == "external_ref"
        assert "asset_no" not in run["detected_mapping"].values(), (
            "BR-AST-049 (PO 2026-08-27): no header a utility would plausibly "
            "ship claims `asset_no` any more — it keeps only its own field name "
            "and its label, so an operator updating existing meters maps it by "
            "hand, deliberately, which is the only case it is now for."
        )


from pathlib import Path  # noqa: E402 — used by the fixtures above

FIXTURES = Path(__file__).parent / "fixtures" / "cr028"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/B16 + BR-AST-048 (PO 2026-08-22, 04-docs/05-modules/05-assets/02-business-rules.md) · AST-W3-T8
# generated: 2026-08-22 by the CR-028 AST-W3 lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the FE half of "recognised as" is the runner screen's) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr028_mapping_templates.py
# exceptions: the RED-first failure is quoted in the module docstring (run before the T8 change landed) · detect-order's most-recently-used TIE case is exercised implicitly (the tenant winner's clock is asserted set) — two tenant templates with identical header sets is the only pure-tie shape and the save flow mints unique codes for both, so the MRU comparison is covered by the ordering the selector applies
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
