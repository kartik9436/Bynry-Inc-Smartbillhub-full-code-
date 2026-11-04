# ── Trace ──────────────────────────────────────────────
# Change:  CR-025 — "also we will need sample CSV files to be downloaded at
#          every import at step 1" (PO 2026-08-21, verbatim)
# Screens: WFL-01 stage 1
# Rules:   BR-MET-088 (the header row is the target's REAL columns, derived) ·
#          BR-MET-096 (one runner, two targets — the sample takes its target
#          as a parameter) · BR-MET-032 (the precedent: reads_template.csv
#          shipped header + one worked row from BR-MET-032 until CR-038 W4 gave
#          it a second, the demand meter's peak row — corrected 2026-09-08 with
#          CR-077's read starters; THIS sample is still one row) · BR-MET-098 (an
#          absent plan loads UNPLANNED — the sample's rate_plan cell is empty
#          on purpose)
# ───────────────────────────────────────────────────────
"""CR-025 — the stage-1 sample CSV.

The one property worth a whole test file: **the sample is not documentation,
it is a WORKING FILE** — case 4 uploads the premises sample through the real
stages 1–3 and the real dry-run, and it validates clean and would load one
row. A sample that fails its own import is worse than none, and nothing but
an end-to-end run can prove it doesn't.
"""
import csv
import io

import pytest

from apps.metering import import_runs, services

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, lonestar, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _parse(body: str) -> tuple[list[str], list[str]]:
    rows = list(csv.reader(io.StringIO(body)))
    assert len(rows) == 2, "header row plus ONE example row, nothing else"
    return rows[0], rows[1]


def _fields(target: str) -> list[str]:
    """The FIELD NAME behind each header, in file order.

    ⚠ **THIS FILE USED TO KEY ITS CELLS OFF THE HEADER ROW ITSELF, AND THAT
    STOPPED BEING A FIELD NAME ON 2026-08-28 (`DEF-1077`).** The header is now
    the column's LABEL — `Unit`, not `unit_ref` — because the PO opened the
    downloaded template and could not tell what belonged in it. The cells this
    file asserts about are still per-FIELD facts, so the order comes from
    `import_runs.sample_columns`, which is the very list `sample_csv` writes:
    deriving it a second time here is how `DEF-616` happened.

    Must be called inside `tenant_ctx` — the offered columns are the tenant's
    own (custom fields, date format, unit readiness).
    """
    return [str(column["target"]) for column in import_runs.sample_columns(target)]


def test_the_premises_sample_is_the_targets_own_columns_with_one_worked_row(brazos):
    with tenant_ctx(brazos):
        filename, body = import_runs.sample_csv("premises")
        fields = _fields("premises")
    header, example = _parse(body)
    assert filename == "premises_sample.csv"
    # BR-MET-088: derived from the model, so the required column is there and
    # `— ignore —` / custom fields are not.
    for required in ("premise_no", "address_line", "city", "state", "postal_code"):
        assert required in fields
    assert import_runs.IGNORE not in fields
    # DEF-1077 — and the header a HUMAN reads is the label, not the field name.
    assert "Address line 1" in header and "address_line" not in header
    cells = dict(zip(fields, example))
    # The lookup cell is a RATIFIED seed code, not prose — so the example
    # validates against a fresh tenant's own reference data.
    assert cells["premises_type"] == services.SEED_PREMISES_TYPES[0][0]
    assert cells["status"] == "active"
    # The tenant's own AREA vocabulary is still empty — areas are free text a
    # tenant invents, and there is no declaration to read one from.
    assert cells["area"] == ""
    # ⛔ **THIS LINE USED TO ASSERT `""` AND THE CHANGE IS DELIBERATE
    # (CR-036 (i), DEF-754).** *"tenant-specific vocabularies — never guessed"*
    # is sound reasoning that produced the incident: a file built from this
    # sample carries the services header, maps it, reads `Matched`, and loads
    # 9,881 premises with no services. A tenant's ENABLED SERVICE CODES are
    # not a guess — they are the declaration BR-MET-003 already validates
    # every imported row against. Brazos Bend sells Electric and Water.
    assert cells["services_available"] == "electric,water"


def test_the_units_sample_shows_the_ordering_and_loads_unplanned(brazos):
    with tenant_ctx(brazos):
        filename, body = import_runs.sample_csv("units")
        fields = _fields("units")
    _header, example = _parse(body)
    assert filename == "units_sample.csv"
    cells = dict(zip(fields, example))
    # BR-MET-086: units load under an EXISTING premise — the cell deliberately
    # carries the premises sample's own ID so the two files demonstrate the
    # order they must be run in.
    assert cells["premises"] == "P-9001"
    # BR-MET-098: an absent plan is legal and loads UNPLANNED; a guessed plan
    # code would fail on every real tenant.
    assert cells["rate_plan"] == ""


def test_an_unknown_target_is_refused_by_name(brazos):
    with tenant_ctx(brazos):
        with pytest.raises(Exception) as caught:
            import_runs.sample_csv("assets")
    assert "kind_unknown" in str(getattr(caught.value, "message_key", caught.value))


def test_THE_POINT__the_premises_sample_survives_its_own_import(brazos, marcus):
    """Stage 1 auto-detects every header, stage 2 accepts the detected map
    unchanged, stage 3 rejects nothing, and the dry-run would load the row."""
    with tenant_ctx(brazos):
        _, body = import_runs.sample_csv("premises")
        run = import_runs.extract(
            marcus,
            {
                "target": "premises",
                "source_kind": "file",
                "file_name": "premises_sample.csv",
                "content": body,
                "session_ref": "sess_cr025",
                "ip": "71.42.108.14",
            },
        )
        detected = run["detected_mapping"]
        # Every column the sample ships is recognised without the operator
        # touching a thing. ⚠ **AND NOW IT IS RECOGNISED AS THE RIGHT COLUMN**
        # (`DEF-1077`): the headers are LABELS, so this asserts the round trip
        # label → field rather than the tautology a field-name header made of it.
        header = next(csv.reader(io.StringIO(body)))
        assert set(detected.keys()) == set(header)
        assert [detected[name] for name in header] == _fields("premises")
        import_runs.transform(
            marcus,
            run["id"],
            {
                "mapping": detected,
                "row_handling": {
                    "drop_exact_duplicates": True,
                    "keep_latest_on_key": False,
                    "skip_rows_missing_required": False,
                },
            },
        )
        checked = import_runs.validate(marcus, run["id"])
        assert checked["counts"]["errors"] == 0, (
            f"the sample failed its own validation: {checked['counts']}"
        )
        figures = import_runs.dry_run(marcus, run["id"], "insert")
        assert figures["will_create"] == 1
        assert figures["rejected"] == 0
        assert figures["approval"]["required"] is False


# ═══════════════════════════════════════════════════════════════════════════
# DEF-754 — THE SAMPLE AND THE MAPPING SCREEN TOLD ONE TENANT TWO DIFFERENT
# THINGS, AND CR-036 (i) — THE SAMPLE'S EMPTY LIST CELL IS A ROUTE TO 9,881
# SERVICELESS PREMISES
# ═══════════════════════════════════════════════════════════════════════════
#
# The sample emitted `2026-01-01` for every date while stage 2 told a US tenant
# its dates are read as `MM/DD/YYYY` (BR-MET-117). It WORKED — ISO always
# parses — which is exactly why no test could catch it: the cost was to trust,
# not to data. One declaration (`tenant_settings.date_format`), two consumers
# (`_parse_date` and the sample), which is hard-won law 5's shape.
#
# And the list cell shipped `""` with the reasoning *"tenant-specific
# vocabularies — never guessed"*. The reasoning is sound and the RESULT was the
# CR-036 (i) incident: a file built from the shipped sample carries the
# services header, maps it, shows `Matched` and fills nothing. A tenant's OWN
# enabled service codes are not a guess — they are the same declaration
# `BR-MET-003` validates every imported row against.


def _cells(target: str) -> dict[str, str]:
    _header, example = _parse(import_runs.sample_csv(target)[1])
    return dict(zip(_fields(target), example))


def test_def754__the_sample_writes_dates_in_the_tenants_own_declared_format(brazos):
    """`MM/DD/YYYY` is what stage 2 tells this tenant, so it is what the sample
    it hands them writes. One declaration, two consumers."""
    with tenant_ctx(brazos):
        from apps.tenancy import selectors as tenancy_selectors

        assert tenancy_selectors.regional_settings()["date_format"] == "MM/DD/YYYY"
        assert _cells("units")["plan_effective_from"] == "01/01/2026"


def test_def754__another_tenants_format_produces_another_sample(brazos):
    """The one that proves it is READ and not hardcoded a second time: change
    the declaration and the sample changes with it."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        tenancy_models.TenantSettings.objects.filter(tenant_id=brazos.id).update(
            date_format="DD.MM.YYYY"
        )
        assert _cells("units")["plan_effective_from"] == "01.01.2026"


def test_def754__a_tenant_that_declared_no_format_still_gets_a_readable_sample(brazos):
    """⚠ The unset case is ISO, deliberately: `_parse_date` reads ISO before it
    reads anything else, so the sample this tenant downloads still loads. The
    alternative — a cell in a format nobody declared — would be a sample that
    fails its own import."""
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        tenancy_models.TenantSettings.objects.filter(tenant_id=brazos.id).update(date_format=None)
        assert _cells("units")["plan_effective_from"] == "2026-01-01"


def test_def754__the_assets_samples_take_the_same_format(brazos):
    """The assets targets declare their worked cells beside the column
    (`sample="2026-01-01"`), which bypassed the kind branch entirely — so the
    contradiction lived in three more files than the one DEF-754 names."""
    with tenant_ctx(brazos):
        assert _cells("assets_meters")["install_date"] == "01/01/2026"


def test_cr036_i__the_list_cell_carries_THIS_TENANTS_OWN_SERVICE_CODES(brazos):
    """⚠ **THIS REVERSES AN ASSERTION THIS FILE USED TO MAKE** — see the note on
    the first test. Brazos Bend sells Electric and Water, so that is what its
    own sample shows. It is not a guess at a vocabulary: it is the tenant's own
    enablement, the same set `BR-MET-003` measures every imported row against.
    """
    with tenant_ctx(brazos):
        assert _cells("premises")["services_available"] == "electric,water"


def test_cr036_i__a_different_tenant_gets_a_different_list_cell(lonestar):
    """Water only — so one code, and nothing borrowed from the other tenant."""
    with tenant_ctx(lonestar):
        assert _cells("premises")["services_available"] == "water"
