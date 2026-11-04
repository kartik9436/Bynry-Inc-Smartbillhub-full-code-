# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 P3/P4 — the recorded ETL runner, stages 1–3.
#           SUPERSEDES US-MET-004 §5's "no persistence in v1")
#           Screens: WFL-01.premises.1–3, PRM-04
# Rules:    BR-MET-085 (a premises import loads premises and NOTHING else) ·
#           BR-MET-088 (the REAL target columns) · BR-MET-090 (declared rows;
#           severity and action as two columns; the rules AS THEY WERE) ·
#           BR-MET-091 (an unevaluable rule is declared unavailable, never
#           omitted) · BR-MET-003 (services ⊆ tenant-enabled) · BR-MET-034 ·
#           BR-MET-048 (audit) · BR-RAT-101 (inside_city_limits is THREE-STATE)
#           · CLAUDE.md hard rule 1 (tenant scoping)
# Journeys: the premises migration — a utility's first 431 rows
# ───────────────────────────────────────────────────────
"""The CR-023 import runner, stages 1–3 — and above all, THE ONE CLAIM.

**TC-1 IS THE SAFETY PROPERTY OF THE WHOLE DESIGN AND IT IS THE FIRST TEST IN
THIS FILE.** r10 prints the promise under its own title — *"Five stages ·
nothing is written until you commit at stage four"* — and every other guarantee
CR-023 makes rests on it: a dry run that can write is not a dry run, a rehearsal
that can create a lookup row has already changed the tenant, and an operator
who is told nothing happened has been told something false.

It was proved RED before it was trusted green (hard-won law 7). With five lines
added to `import_runs.transform` creating a premises from the first mapped row,
this file reported, verbatim:

    E   AssertionError: stages 1-3 created 1 premises row(s) — the ONE claim
        of this design is that they create none
    E   assert 2 == 1
    FAILED tests/test_cr023_import_stages.py::test_tc1__stages_1_to_3_write_nothing

**TC-5 was proved the same way and it is the second most important test here**,
because the failure it catches is silent: with `_parse_boolean3` returning
`False` for an empty cell instead of `None` — one line, and the obvious-looking
one — it reported

    E   assert False is None
    FAILED tests/test_cr023_import_stages.py::test_tc5__a_blank_inside_city_limits_stores_null_never_false

and every one of the other 37 tests still passed. A blank jurisdiction cell
defaulting to *outside city* would have surcharged 428 premises nobody surveyed.

Both injected lines were removed and both assertions went green. The test data
is B15 §16's
own: 431 premises rows — 3 exact duplicates, 2 rows whose premise type is not
in the lookup, 1 row with no address, 1 row with a service the tenant does not
sell, 1 row with a blank `inside_city_limits`, and 1 row repeating a
`premise_no`. Those figures are r10's own arithmetic: **431 in, 3 duplicates
dropped, 428 forward to validation.**
"""

import csv
import hashlib
import io

import pytest

from apps.metering import import_rules, import_runs, models
from apps.tenancy import models as tenancy_models
from core import errors
from core import tenancy as core_tenancy

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── the §16 test data, built once and readable ──────────────────────────────

HEADERS = [
    "PREMISE_ID",
    "ADDR1",
    "CITY",
    "STATE",
    "ZIP",
    "PROP_TYPE",
    "UNIT_CNT",
    "SVC_AVAIL",
    "OWNER",
    "LEGACY_KEY",
    "INSIDE_CITY",
]

#: r10's own mapping, corrected in the two places B15 §4.2A corrects it:
#: `LEGACY_KEY` maps to `external_ref` rather than being thrown away (#12), and
#: `UNIT_CNT` maps to NOTHING because there is no column for it (§4.2A closing
#: box, OQ-330). `INSIDE_CITY` is the column r10's import does not have at all
#: and the one a blank cell must not fill (#7).
MAPPING = {
    "PREMISE_ID": "premise_no",
    "ADDR1": "address_line",
    "CITY": "city",
    "STATE": "state",
    "ZIP": "postal_code",
    "PROP_TYPE": "premises_type",
    "UNIT_CNT": import_runs.IGNORE,
    "SVC_AVAIL": "services_available",
    "OWNER": "owner_manager",
    "LEGACY_KEY": "external_ref",
    "INSIDE_CITY": "inside_city_limits",
}

ALL_ON = {
    "drop_exact_duplicates": True,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}


def _row(index: int, **overrides) -> dict:
    """One row of a premises file, as a customer's export actually arrives TODAY.

    ⚠ **`PREMISE_ID` IS BLANK, AND IT USED TO BE `P-1000n` (`DEF-2794`).** The
    PO ruled on **2026-08-27** that a premise number is issued by the tenant's
    own numbering settings, so `CR-046` C2 made `PRM.PREMISE_NO_NOT_ON_FILE` an
    ERROR: an id that is not already on file is one the operator INVENTED. This
    fixture supplied `P-9xxxx` on every row, so from that day a 431-row file
    forwarded 428 rows and **rejected all 428**, and the two CR-023 suites went
    **35 tests red** and stayed red — `TC-1` read `errors 428 / clean 0 /
    warnings 0` against its ratified `3 / 423 / 2`.

    Nothing about the rule was wrong. **A file built from the shipped template
    leaves this column blank**, which is what this now is; an operator who has
    their old system's ids puts them in `LEGACY_KEY` (`external_ref`,
    BR-MET-403), which is where the rule's own fix hint sends them.

    The tests that are ABOUT a stated premise number still state one — they pass
    `PREMISE_ID=` explicitly — so the on-file warning and the twice-in-one-file
    error are unaffected.
    """
    row = {
        "PREMISE_ID": "",
        "ADDR1": f"{index} Bluestem Ln",
        "CITY": "Katy",
        "STATE": "TX",
        "ZIP": "77494",
        "PROP_TYPE": "single_family",
        "UNIT_CNT": "2",
        "SVC_AVAIL": "electric,water",
        "OWNER": "Whitfield Rentals LLC",
        "LEGACY_KEY": str(88000 + index),
        "INSIDE_CITY": "inside",
    }
    row.update(overrides)
    return row


def _csv(rows: list[dict], headers: list[str] | None = None) -> str:
    """A REAL CSV, written by `csv.writer`.

    ⚠ Hand-joining on commas is what this helper replaces, and it cost an hour:
    `SVC_AVAIL` is `electric,water`, so a naive join shifted every column after
    it by one and the jurisdiction cell arrived holding a legacy key. The
    parser was right and the fixture was lying — which is exactly the class of
    bug an import runner exists to catch, arriving first in its own tests.
    """
    headers = headers or HEADERS
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row[header] for header in headers])
    return buffer.getvalue()


def premises_csv() -> str:
    """B15 §16's file, exactly: 431 rows carrying six planted problems."""
    rows = [_row(index) for index in range(1, 429)]
    # 1 row with NO ADDRESS (§16) — tier 1, PRM.ADDRESS_REQUIRED
    rows[10]["ADDR1"] = ""
    # 2 rows whose premise type is NOT in the lookup (§16) — tier 2, warning
    rows[20]["PROP_TYPE"] = "TRIPLEX"
    rows[21]["PROP_TYPE"] = "QUADPLEX"
    # 1 row with a service the tenant does not sell (§16) — tier 1, BR-MET-003
    rows[30]["SVC_AVAIL"] = "electric,unicorn"
    # 1 row with a BLANK inside_city_limits (§16) — must store NULL, not False
    rows[40]["INSIDE_CITY"] = ""
    # 1 row repeating an IDENTIFIER already used in the file (§16) — tier 1.
    # ⚠ **THIS PLANTED `PREMISE_ID` UNTIL 2026-09-01 (`DEF-2794`).** With the
    # column blank on every row there is no premise number left to repeat, so
    # §16's sixth planted problem is expressed through the identifier a
    # template-built file still carries: `LEGACY_KEY` -> `external_ref`, and
    # `PRM.EXTERNAL_REF_UNIQUE` (CR-046 C5 / BR-MET-403) rejects a reference
    # used twice in one file for the same reason `PRM.PREMISE_NO_UNIQUE` did —
    # the second row would silently win. **The planted problem is the same
    # problem and the count does not move**, which is why the ratified
    # `3 / 423 / 2` still holds.
    rows[50]["LEGACY_KEY"] = rows[49]["LEGACY_KEY"]
    # 3 EXACT duplicates (§16) — dropped at stage 2, never seen by stage 3
    rows.extend([dict(rows[100]), dict(rows[200]), dict(rows[300])])
    assert len(rows) == 431, len(rows)
    return _csv(rows)


def dedupe_csv() -> str:
    """§16's TWO duplicate shapes at small scale, on a file that states its keys.

    ⚠ **THE §16 FILE CANNOT CARRY THIS CASE ANY MORE (`DEF-2794`).**
    `DEDUPE_KEY_BY_TARGET[TARGET_PREMISES]` is `("premise_no", "Premise ID")`,
    so *"keep the latest row when a key appears twice"* keys on the premise
    NUMBER and on nothing else — `_key_of`'s `external_ref` fallback answers a
    different question (which record on file is this row ABOUT) for a different
    stage. Under the PO's 2026-08-27 numbering ruling a template-built file
    leaves that column blank, so on `premises_csv()` the control is a no-op and
    a case asserting *"4 dropped"* reads 3.

    So the cases that are ABOUT a stated premise number get a file that states
    one — the same posture `test_a_premise_id_TWICE_IN_ONE_FILE_is_still_the_error`
    already takes. **Stage 2 runs before validation**, so these rows being
    rejected at stage 3 for naming a number not on file changes none of the
    counts below.

    Six rows: one ordinary, TWO sharing `P-77001` (the keyed duplicate), and
    three EXACT copies of the first.
    """
    base = _row(1)
    rows = [
        base,
        _row(2, PREMISE_ID="P-77001"),
        _row(3, PREMISE_ID="P-77001"),
        dict(base),
        dict(base),
        dict(base),
    ]
    return _csv(rows)


def units_csv(premise_nos=None) -> str:
    """r10's own units sheet shape (`WFL-01.units.2`), trimmed to four rows.

    `premise_nos` are the numbers the SERVER allocated — see `seed_units_world`.
    Passing them in rather than hardcoding `P-10001` is what keeps this file a
    test of the real load order instead of a test of an invented one.

    ⚠ **IT CARRIES THE FOUR COLUMNS WE DO NOT OFFER**, deliberately: `METER_E`,
    `METER_W`, `OCCUPANT` and `STATUS`. A customer's real export has them —
    r10's does — and the import must be able to say *"nothing here maps to
    that"* rather than choke. The reasons are in `UNITS_ALIASES`: two are the
    PO's ruling that a units import creates no meter, and two are columns this
    product does not have.
    """
    first, second = premise_nos or ("P-10001", "P-10002")
    header = "UNIT_REF,PREMISE_ID,UNIT_TYPE,SQFT,METER_E,METER_W,OCCUPANT,STATUS,PLAN"
    rows = [
        f'U-10432-A,{first},APT,980,M-4021,M-4022,"Miller, Sarah",OCC,RES-STD',
        f'U-10432-B,{first},APT,1040,M-4023,M-4024,"Chen, Wei",OCC,RES-STD',
        f'U-10433-A,{second},APT,860,M-4025,M-4026,"Ortiz, Ana",VAC,RES-STD',
        # ⚠ the BR-MET-100 row: its premise IS on file, its plan is NOT.
        f'U-10433-B,{second},APT,910,M-4027,M-4028,"Novak, Jan",OCC,RES-STD-2027',
    ]
    return "\n".join([header, *rows]) + "\n"


UNITS_MAPPING = {
    "UNIT_REF": "label",
    "PREMISE_ID": "premises",
    "UNIT_TYPE": "unit_type",
    "SQFT": "square_feet",
    "PLAN": "rate_plan",
    # The four r10 draws and this product does not offer (`UNITS_ALIASES`).
    "METER_E": import_runs.IGNORE,
    "METER_W": import_runs.IGNORE,
    "OCCUPANT": import_runs.IGNORE,
    "STATUS": import_runs.IGNORE,
}


def _extract(actor, *, content=None, **overrides):
    payload = {
        "target": "premises",
        "source_kind": "file",
        "file_name": "silvercreek_premises_2026.csv",
        "content": premises_csv() if content is None else content,
        "session_ref": "sess_2b41",
        "ip": "71.42.108.14",
    }
    payload.update(overrides)
    return import_runs.extract(actor, payload)


def _full_cycle(actor, *, mapping=None, handling=None, content=None):
    run = _extract(actor, content=content)
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": mapping or MAPPING, "row_handling": handling or ALL_ON},
    )
    return import_runs.validate(actor, run["id"])


def _counts() -> tuple[int, int, int]:
    return (
        models.Premises.objects.count(),
        models.Unit.objects.count(),
        models.ServicePoint.objects.count(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · THE SAFETY PROPERTY
# ═══════════════════════════════════════════════════════════════════════════


def test_tc1__stages_1_to_3_write_nothing(brazos, marcus):
    """TC-1 — row counts in `premises`, `units` and `service_points` are
    IDENTICAL before and after a full extract → transform → validate.

    ⚠ This is the assertion every other guarantee in CR-023 rests on. Proved
    RED first by making `transform` create a premises from its first mapped
    row; the failure is quoted in this module's docstring.
    """
    with tenant_ctx(brazos):
        make_premises(marcus, address_line="1 Existing St")
        before = _counts()

        result = _full_cycle(marcus)

        after = _counts()
        assert after[0] == before[0], (
            f"stages 1-3 created {after[0] - before[0]} premises row(s) — the ONE "
            "claim of this design is that they create none"
        )
        assert after[1] == before[1], "stages 1-3 created a unit (BR-MET-085)"
        assert after[2] == before[2], "stages 1-3 created a service point"
        # ⚠ THE RATIFIED FIGURES, asserted exactly so drift goes RED. These are
        # the numbers put to the PO in the human-review ledger row of
        # 2026-08-21: **1 property, 0 units and 0 service connections before
        # AND after 431 rows are read, mapped and checked.**
        assert before == (1, 0, 0)
        assert after == (1, 0, 0)
        # …and they DID do their own work, so the test cannot pass by doing nothing.
        assert result["status"] == "validated"
        assert result["counts"] == {
            "in": 431,
            "duplicates_dropped": 3,
            "skipped": 0,
            "forward": 428,
            "checked": 428,
            "clean": 423,
            "errors": 3,
            "warnings": 2,
        }


def test_tc9__a_premises_run_never_creates_a_unit_even_with_a_unit_count(brazos, marcus):
    """TC-9 / BR-MET-085 — *"We we load premises - it will be only premises."*

    r10 prints the opposite twice (*"181 single-unit premises auto-create their
    unit"*) and the PO's ruling of 2026-08-21 withdraws it. The file here
    carries `UNIT_CNT` on every row, which is the input r10's auto-create used,
    and no unit appears.
    """
    with tenant_ctx(brazos):
        before = models.Unit.objects.count()
        _full_cycle(marcus)
        assert models.Unit.objects.count() == before


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 1 · EXTRACT
# ═══════════════════════════════════════════════════════════════════════════


def test_tc2__the_file_hash_is_computed_server_side(brazos, marcus):
    """TC-2 — a client-supplied hash proves nothing, so it is not read."""
    body = premises_csv()
    with tenant_ctx(brazos):
        run = _extract(marcus, file_hash="deadbeef" * 8)
    assert run["file_hash"] == hashlib.sha256(body.encode("utf-8")).hexdigest()
    assert run["file_hash"] != "deadbeef" * 8
    assert run["file_bytes"] == len(body.encode("utf-8"))


def test_extract_stages_every_row_including_the_ones_that_will_fail(brazos, marcus):
    """`ReadImportRow`'s ratified claim, carried over: every row that enters
    the file comes out of the report."""
    with tenant_ctx(brazos):
        run = _extract(marcus)
        assert models.ImportRunRow.objects.filter(run_id=run["id"]).count() == 431
        assert run["counts"]["in"] == 431
        assert run["encoding_delimiter"] == "UTF-8 · comma (detected)"


def test_extract_detects_the_mapping_by_header_including_legacy_key(brazos, marcus):
    """TC-6 — `LEGACY_KEY` → `external_ref`, not `— ignore —`.

    B15 §4.2A #12: discarding the customer's own key means you can never
    reconcile our rows against their system, a re-import duplicates every row
    it already created, and *"what happened to property 88214"* has no answer.
    """
    with tenant_ctx(brazos):
        run = _extract(marcus)
    detected = run["detected_mapping"]
    assert detected["LEGACY_KEY"] == "external_ref"
    assert detected["PREMISE_ID"] == "premise_no"
    assert detected["ADDR1"] == "address_line"
    assert detected["INSIDE_CITY"] == "inside_city_limits"
    # ⚠ and the one that must NOT be detected, because it has no column:
    assert "UNIT_CNT" not in detected


def test_tc6__external_ref_round_trips_into_the_mapped_row(brazos, marcus):
    with tenant_ctx(brazos):
        run = _extract(marcus)
        import_runs.transform(marcus, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
        first = models.ImportRunRow.objects.get(run_id=run["id"], row_no=1)
    assert first.mapped["external_ref"] == "88001"


def test_br_met_096__the_units_target_is_accepted_now(brazos, marcus):
    """⚠ **THIS CASE USED TO ASSERT THE OPPOSITE, AND THE RULING IS WHY.**

    It read *"B15 §17 puts the units target at P8 and its plan rule is unruled
    (§4B.3)"* and pinned `allowed == ["premises"]`. `BR-MET-100` (PO
    2026-08-21) ruled the plan half — a units row naming a missing plan loads
    unplanned and flagged — and `BR-MET-096` ruled that premises and units run
    the SAME workflow. Both blockers are closed, so the refusal is gone.

    A test left asserting the refusal would have gone green on a target that no
    longer refuses, which is the failure mode `DEF-490` named: a check whose
    output cannot tell pass from fail.
    """
    with tenant_ctx(brazos):
        numbers = seed_units_world(marcus)
        run = import_runs.extract(
            marcus,
            {
                "target": "units",
                "source_kind": "file",
                "file_name": "riverside_units.csv",
                "content": units_csv(numbers),
            },
        )
    assert run["target"] == "units"
    assert run["counts"]["in"] == 4
    # BR-MET-096: the workflow is the same one. The run row, the hash, the
    # staged rows and the encoding line are all produced by the same code.
    assert run["file_hash"] and run["encoding_delimiter"].startswith("UTF-8")


def test_br_met_096__an_unknown_target_is_still_refused_by_name(brazos, marcus):
    """A declared set, not "any string". A new target is a dict entry, not a
    guess — and CR-028 AST-W3 added exactly three of them (the refused name
    here is deliberately `meters`, which is a TAB, not a target: the runner's
    vocabulary is `assets_meters`)."""
    with tenant_ctx(brazos), pytest.raises(errors.ValidationError) as caught:
        _extract(marcus, target="meters")
    assert caught.value.params["allowed"] == [
        "premises",
        "units",
        "assets_meters",
        "assets_submeters",
        "assets_devices",
        # CR-030 W1 — the sixth target. This list is the REFUSAL's own
        # vocabulary, so it grows with the runner by design.
        "accounts",
        # CR-077 — the seventh. `parts` is `work`'s table and the load goes
        # through work's own `import_writer`; from the refusal's point of view
        # it is one more declared name, which is BR-MET-096 working.
        "parts",
    ]


def test_non_file_sources_are_refused_by_name(brazos, marcus):
    """Three of stage 1's four cards are out of scope (B15 §4.1)."""
    with tenant_ctx(brazos), pytest.raises(errors.ValidationError) as caught:
        _extract(marcus, source_kind="sftp")
    assert caught.value.params["allowed"] == ["file"]


def test_tc21__the_same_file_may_be_uploaded_twice(brazos, marcus):
    """TC-21 first half — re-opening the wizard on the same file is allowed.

    The idempotency constraint is scoped to LOADED runs, exactly as
    `uq_read_import_batches_idempotency` is scoped to POSTED batches: a staged
    run is a rehearsal and only a second COMMIT is a double-load. The second
    half (committing twice is refused) belongs to stage 4 and is not built.
    """
    with tenant_ctx(brazos):
        first = _extract(marcus)
        second = _extract(marcus)
    assert first["file_hash"] == second["file_hash"]
    assert first["id"] != second["id"]


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 2 · TRANSFORM
# ═══════════════════════════════════════════════════════════════════════════


def test_tc4__maps_to_offers_the_real_columns_and_nothing_else(brazos, marcus):
    """TC-4 / BR-MET-088 — *"you can choose actual column you have from table"*.

    ⛔ **AMENDED 2026-09-19 — `DEF-MET-5802` ENDED THE GUARANTEE THIS CASE USED
    TO ASSERT, ON PURPOSE, AND THIS IS THE ONLY TEST IN THE REPO THAT MEASURED
    IT.** It read `from_model - {"custom_data"} <= offered` — *every* concrete
    field on `Premises` must be offered — under the reasoning that *"the offered
    set is asserted against `Premises._meta` itself, so a hand-written list can
    never drift from the schema"*.

    **That reasoning is still right and it is no longer the whole rule.** The
    PO reviewed the generated template on 2026-09-19 and retired nine premises
    fields the address-matching process writes for itself — they were on every
    customer's template with headings generated from their field names, *"Gis
    parcel id was"*, *"Gis verified at"*, and derivation put them there because
    `_meta` cannot judge whether a column is a **utility's to supply**.

    ⚠ **SO THE DRIFT THIS CASE EXISTS TO CATCH IS ASSERTED THE OTHER WAY UP.**
    A declared list CAN silently omit a real column, which is the half
    derivation gave free; it is bought back by requiring every model field to be
    **classified** — offered, or withheld WITH A WRITTEN REASON. A new field on
    `premises` still fails here, by name, exactly as it did before. What it can
    no longer do is appear on a customer's template because nobody looked.

    The fuller set of these checks, including the reasons table and the
    retirement list by name, is
    `tests/test_def_met_5802_declared_columns.py`; this case keeps TC-4's own
    question — can an operator choose the real columns, and nothing else.
    """
    with tenant_ctx(brazos):
        offered = {column["target"] for column in import_runs.target_columns("premises")}

    from_model = {
        field.name
        for field in models.Premises._meta.get_fields()
        if getattr(field, "concrete", False) and field.name not in import_runs.NEVER_IMPORTABLE
    }
    # ⚠ **NOTHING OFFERED THAT THE TABLE DOES NOT HAVE** — `BR-MET-088`'s first
    # half, unchanged and still the one that matters most, because a column
    # with nothing behind it is a value accepted, listed and silently dropped
    # (DEF-388's shape). The owner-identity columns are VIRTUAL by design and
    # are named rather than waved through.
    phantom = offered - from_model - {import_runs.IGNORE}
    phantom -= set(import_runs.PREMISES_OWNER_COLUMN_NAMES)
    phantom = {name for name in phantom if not str(name).startswith("custom_data.")}
    assert not phantom, f"offered with nothing behind it: {sorted(phantom)}"
    # ⚠ **AND EVERY MODEL FIELD ACCOUNTED FOR** — the replacement for the old
    # subset assertion. Offered, or deliberately withheld with a reason.
    unclassified = from_model - offered - set(import_runs.PREMISES_COLUMNS_NOT_OFFERED)
    assert unclassified == {"custom_data"}, (
        f"fields nobody has classified: {sorted(unclassified - {'custom_data'})} — add each "
        "to PREMISES_COLUMNS if a utility supplies it, or to PREMISES_COLUMNS_NOT_OFFERED "
        "with the reason it does not"
    )
    # … and the withheld set is a DECISION, not a dumping ground: every entry
    # is a real column of the table and every one states why.
    assert set(import_runs.PREMISES_COLUMNS_NOT_OFFERED) <= from_model
    assert all(str(why).strip() for why in import_runs.PREMISES_COLUMNS_NOT_OFFERED.values())
    # `custom_data` is expanded per defined field rather than offered whole.
    assert "custom_data" not in offered
    assert import_runs.IGNORE in offered  # "ignored on purpose" ≠ "nobody mapped it"
    # B15 §4.2A: fourteen fields, and these six are the ones r10 never maps.
    for missing_in_r10 in (
        "name",
        "inside_city_limits",
        "area",
        "external_ref",
        "status",
    ):
        assert missing_in_r10 in offered
    # …and the one r10 maps that has nowhere to land (OQ-330).
    assert "expected_units" not in offered
    assert "unit_count" not in offered
    # never importable, on any run
    for never in ("tenant", "is_sample", "created_at", "deleted_at", "id"):
        assert never not in offered


def test_tc4__a_tenants_own_custom_fields_are_offered_by_name(brazos, marcus):
    with tenant_ctx(brazos):
        tenancy_models.CustomField.objects.create(
            tenant_id=brazos.id,
            entity="premises",
            key="legacy_book_page",
            label="Deed book & page",
            data_type="text",
        )
        offered = {column["target"]: column for column in import_runs.target_columns("premises")}
    assert offered["custom_data.legacy_book_page"]["label"] == "Deed book & page"
    assert offered["custom_data.legacy_book_page"]["custom_field"] is True


def test_transform_does_not_offer_what_it_cannot_do(brazos, marcus):
    """r10 names `Standardise to USPS` and `ZIP+4 split`. Neither is offered,
    and each carries its reason rather than leaving a silent gap."""
    codes = {entry["code"] for entry in import_runs.UNAVAILABLE_TRANSFORMS}
    assert codes == {"standardise_usps", "zip4_split"}
    for entry in import_runs.UNAVAILABLE_TRANSFORMS:
        assert entry["reason"], "an unavailable transform with no reason is a silent gap"
    with tenant_ctx(brazos):
        offered = {c["target"]: c for c in import_runs.target_columns("premises")}
    assert "standardise_usps" not in offered["address_line"]["transforms"]
    assert "zip4_split" not in offered["postal_code"]["transforms"]


def test_tc3__transform_reconciles(brazos, marcus):
    """TC-3 — r10's own three figures: **in 431 · duplicates dropped 3 · rows
    forward to validation 428**, and `in − dropped − skipped = forward`."""
    with tenant_ctx(brazos):
        run = _extract(marcus)
        result = import_runs.transform(
            marcus, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON}
        )
    counts = result["counts"]
    assert counts["in"] == 431
    assert counts["duplicates_dropped"] == 3
    assert counts["skipped"] == 0
    assert counts["forward"] == 428
    assert counts["in"] - counts["duplicates_dropped"] - counts["skipped"] == counts["forward"]


def test_tc7__an_unmapped_address_is_refused_at_stage_2_not_stage_3(brazos, marcus):
    """TC-7 — `address_line` is the ONLY non-null business column on the table
    (B15 §4.2A #3), so a file with no address column cannot produce a single
    loadable row and must be stopped while the operator is still mapping."""
    mapping = {key: value for key, value in MAPPING.items() if value != "address_line"}
    with tenant_ctx(brazos):
        run = _extract(marcus)
        with pytest.raises(errors.ValidationError) as caught:
            import_runs.transform(marcus, run["id"], {"mapping": mapping, "row_handling": ALL_ON})
        assert caught.value.params["targets"] == ["address_line"]
        # and the run never reached validation
        assert models.ImportRun.objects.get(pk=run["id"]).status == "extracted"


def test_a_blank_address_can_be_SKIPPED_at_stage_2_when_the_operator_says_so(brazos, marcus):
    """r10's third checkbox — *"Skip rows with empty required fields rather
    than rejecting them"*. Off by default: with the box unticked the row goes
    forward and stage 3 refuses it, which is the safer of the two."""
    handling = {**ALL_ON, "skip_rows_missing_required": True}
    with tenant_ctx(brazos):
        run = _extract(marcus)
        result = import_runs.transform(
            marcus, run["id"], {"mapping": MAPPING, "row_handling": handling}
        )
    assert result["counts"]["skipped"] == 1
    assert result["counts"]["forward"] == 427


def test_keep_latest_on_key_drops_the_earlier_row_not_the_later(brazos, marcus):
    """*"Keep the latest row when a key appears twice"* — the key is
    `premise_no` (B15 §4.2A #1), and the LAST occurrence wins.

    Runs on `dedupe_csv()` rather than §16's file since 2026-09-01; that
    helper's docstring says why (`DEF-2794`).
    """
    handling = {**ALL_ON, "keep_latest_on_key": True}
    with tenant_ctx(brazos):
        run = _extract(marcus, content=dedupe_csv())
        result = import_runs.transform(
            marcus, run["id"], {"mapping": MAPPING, "row_handling": handling}
        )
        rows = models.ImportRunRow.objects.filter(run_id=run["id"]).order_by("row_no")
        earlier = rows.get(row_no=2)
        later = rows.get(row_no=3)
    assert result["counts"]["duplicates_dropped"] == 4  # the 3 exact copies + this one
    assert earlier.outcome == "duplicate"
    assert later.outcome == "staged"


# ═══════════════════════════════════════════════════════════════════════════
# THE THREE-STATE FLAG — TC-5, the field a default corrupts
# ═══════════════════════════════════════════════════════════════════════════


def test_tc5__a_blank_inside_city_limits_stores_null_never_false(brazos, marcus):
    """TC-5 / BR-RAT-101 — `True` inside · `False` outside · **`None` nobody
    recorded it**.

    `rating.resolution.money_factor` REFUSES on `None` rather than assuming,
    because assuming *inside* under-charges a customer the utility may be
    entitled to surcharge and assuming *outside* over-charges one who never
    agreed. A CSV blank is not `False`.
    """
    with tenant_ctx(brazos):
        run = _extract(marcus)
        import_runs.transform(marcus, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
        blank = models.ImportRunRow.objects.get(run_id=run["id"], row_no=41)
        populated = models.ImportRunRow.objects.get(run_id=run["id"], row_no=1)
    assert blank.mapped["inside_city_limits"] is None
    assert blank.mapped["inside_city_limits"] is not False
    assert populated.mapped["inside_city_limits"] is True


def test_outside_reads_as_false_and_a_word_nobody_can_read_is_an_error(brazos, marcus):
    """ "Nobody recorded it" and "somebody recorded something we cannot read"
    are different facts, and only one of them is safe to leave empty."""
    rows = [_row(1, INSIDE_CITY="outside"), _row(2, INSIDE_CITY="maybe")]
    body = _csv(rows)
    with tenant_ctx(brazos):
        result = _full_cycle(marcus, content=body)
        first = models.ImportRunRow.objects.get(run_id=result["id"], row_no=1)
        second = models.ImportRunRow.objects.get(run_id=result["id"], row_no=2)
    assert first.mapped["inside_city_limits"] is False
    assert second.outcome == "rejected"
    assert "inside or outside" in (second.problem or "")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 3 · VALIDATE
# ═══════════════════════════════════════════════════════════════════════════


def test_stage_3_counts_reconcile_against_the_rows(brazos, marcus):
    """*"ROWS CHECKED · PASSED CLEAN · ERRORS · WARNINGS"* — and the four add
    up, because a count that cannot be checked against the rows is a number
    nobody can defend."""
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
    counts = result["counts"]
    assert counts["checked"] == 428
    assert counts["clean"] + counts["errors"] + counts["warnings"] == counts["checked"]
    # the three planted tier-1 failures: no address · unsold service · repeated id
    assert counts["errors"] == 3
    # the two planted unknown premise types
    assert counts["warnings"] == 2


def test_tc8__a_service_the_tenant_does_not_sell_is_refused(brazos, marcus):
    """TC-8 / BR-MET-003 — *"Split on comma"* is NOT enough. A tenant that does
    not sell sewer must have it REFUSED, not stored: a premises listing a
    service the utility cannot bill is one that can never bill correctly."""
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
        row = models.ImportRunRow.objects.get(run_id=result["id"], row_no=31)
    assert row.outcome == "rejected"
    assert "unicorn" in row.problem


def test_a_repeated_premise_id_is_an_error_and_names_the_other_row(brazos, marcus):
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
        row = models.ImportRunRow.objects.get(run_id=result["id"], row_no=51)
    assert row.outcome == "rejected"
    assert "appears twice" in row.problem
    assert "50" in (row.fix_hint or "")


def test_a_premise_id_already_on_file_is_a_WARNING_that_names_the_modes(brazos, marcus):
    """⚠ **INVERTED 2026-08-22 (`DEF-543`).** This case used to assert the
    on-file match REJECTED — which made `Insert & update` a mode that could
    never update: stage 3 runs before the write mode is chosen, so the row a
    re-import exists for was stripped before stage 4 could see it. The DB-half
    is `PRM.PREMISE_NO_ON_FILE` now, a WARNING whose sentence tells the
    operator what each mode will do; the IN-FILE duplicate (the next case)
    stays the error.

    The taken id is still read back from the premises the SERVICE created,
    for the same reason as before: `premise_no` is series-allocated and a
    hard-coded id would test a string, not the behaviour.
    """
    with tenant_ctx(brazos):
        existing = make_premises(marcus, address_line="9 Taken St")
        taken = existing["premise_no"]
        assert taken, "the premises series must allocate, or this test proves nothing"
        body = _csv([_row(1, PREMISE_ID=taken)])
        result = _full_cycle(marcus, content=body)
        row = models.ImportRunRow.objects.get(run_id=result["id"], row_no=1)
    assert row.outcome == "flagged"
    assert "already on file" in row.problem
    assert result["counts"]["errors"] == 0


def test_a_premise_id_TWICE_IN_ONE_FILE_is_still_the_error(brazos, marcus):
    """The half of the old rule that survives, pinned so the split cannot
    quietly widen: the second row would silently win, whatever the mode."""
    with tenant_ctx(brazos):
        body = _csv([_row(1, PREMISE_ID="P-77001"), _row(2, PREMISE_ID="P-77001")])
        result = _full_cycle(marcus, content=body)
        second = models.ImportRunRow.objects.get(run_id=result["id"], row_no=2)
    assert second.outcome == "rejected"
    assert "appears twice in this file" in second.problem


def test_an_unknown_premise_type_warns_and_sets_nothing(brazos, marcus):
    """r10's action here is `Default to Residential` and it is NOT shipped.

    Two reasons and either would be enough: BR-MET-090 calls it a warning that
    performs a write nobody asked for, and **there is no such type** —
    BR-MET-034 seeds Apartment complex · Commercial building · Single-family ·
    Mixed-use · Mobile-home park. OQ-329 holds the question.
    """
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
        row = models.ImportRunRow.objects.get(run_id=result["id"], row_no=21)
    assert row.outcome == "flagged"  # a WARNING, so the load is not blocked
    assert row.mapped["premises_type"] is None  # …and nothing was chosen for them
    assert row.mapped["premises_type_raw"] == "TRIPLEX"
    rule = next(r for r in result["rules"] if r["code"] == "PRM.TYPE_IN_LOOKUP")
    assert rule["severity"] == "warning"
    assert rule["action"] == "flag_only"
    assert rule["action_value"] is None
    assert rule["hits"] == 2


def test_an_area_that_is_not_on_file_rejects_the_row_and_names_it(brazos, marcus):
    """B15 §4.3A tier 1 — *"Every FK resolves"*. ⛔ OQ-328: whether an unknown
    area should instead be CREATED or LEFT NULL is unruled, so rejecting is the
    boundary and not a chosen answer."""
    headers = HEADERS + ["AREA"]
    row = {**_row(1), "AREA": "Riverbend quarter"}
    body = _csv([row], headers)
    mapping = {**MAPPING, "AREA": "area"}
    with tenant_ctx(brazos):
        assert not tenancy_models.Area.objects.filter(
            tenant_id=brazos.id, name="Riverbend quarter"
        ).exists()
        result = _full_cycle(marcus, content=body, mapping=mapping)
        stored = models.ImportRunRow.objects.get(run_id=result["id"], row_no=1)
    assert stored.outcome == "rejected"
    assert "Riverbend quarter" in stored.problem
    assert "Settings" in (stored.fix_hint or "")


def test_an_area_on_file_passes(brazos, marcus):
    """`North district` is one of the four areas CR-004's platform fixture
    seeds, so this matches a REAL row rather than one the test planted."""
    headers = HEADERS + ["AREA"]
    row = {**_row(1), "AREA": "North district"}
    body = _csv([row], headers)
    mapping = {**MAPPING, "AREA": "area"}
    with tenant_ctx(brazos):
        assert tenancy_models.Area.objects.filter(
            tenant_id=brazos.id, name="North district"
        ).exists()
        result = _full_cycle(marcus, content=body, mapping=mapping)
        stored = models.ImportRunRow.objects.get(run_id=result["id"], row_no=1)
    assert stored.outcome == "staged"
    assert stored.mapped["area_name"] == "North district"


def test_tier_1_stops_the_row_before_tier_2_is_asked(brazos, marcus):
    """B15 §4.3A — a premises with no address does not ALSO appear in the
    *"already on file at this address"* count: it has no address to compare."""
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
        no_address = models.ImportRunRow.objects.get(run_id=result["id"], row_no=11)
    assert no_address.outcome == "rejected"
    assert "no street address" in no_address.problem
    duplicate_rule = next(r for r in result["rules"] if r["code"] == "PRM.ADDRESS_ON_FILE")
    assert duplicate_rule["hits"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-090 / BR-MET-091 — the rules as they were, and the ones we cannot run
# ═══════════════════════════════════════════════════════════════════════════


def test_tc18__an_unavailable_rule_is_listed_with_its_reason(brazos, marcus):
    """TC-18 / BR-MET-091 — *"an operator reading three rules where four were
    expected learns nothing"*.

    ⚠ **THIS TEST USED TO PIN `PRM.ADDRESS_IN_TERRITORY` AND NOW PINS ITS
    ABSENCE (`BR-MET-097`, PO 2026-08-21).** It was r10's only error-severity
    platform rule, and it was the example this case was written around: declared
    but `available=False`, because the product has no geocoder. The PO ruled the
    RULE away rather than waiting for the implementation — *"We dont have to
    check; accept what utility user give right now"* — so the row is gone, and
    a test that still asserted `available is False` would have gone green on a
    rule that no longer exists in any form.

    `PRM.EXPECTED_UNITS_INTEGER` carries TC-18 now: it is genuinely unavailable
    (the product records no expected-unit count) and it is genuinely LISTED with
    its reason, which is the whole of what BR-MET-091 asks for.
    """
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
    by_code = {rule["code"]: rule for rule in result["rules"]}
    # BR-MET-097: absent, not greyed. An operator is never offered it.
    assert "PRM.ADDRESS_IN_TERRITORY" not in by_code
    expected_units = by_code["PRM.EXPECTED_UNITS_INTEGER"]
    assert expected_units["available"] is False
    assert "does not record how many units" in expected_units["unavailable_reason"]


def test_br_met_097__no_platform_error_rule_remains_on_a_premises_import(brazos, marcus):
    """⚠ BR-MET-091's arithmetic, measured rather than asserted into existence
    — and the rule's own wording needed narrowing because of it.

    BR-MET-091 says *"no error-severity rules left at all"*. Among the PLATFORM
    (tier-2) rules that is exactly true and it is what this asserts — and since
    `BR-MET-097` it is true BY RULING rather than by a missing geocoder, which
    means it is now a fact to keep rather than a gap to close. It is NOT
    true of the load as a whole: the five STRUCTURAL tier-1 rules are
    error-severity, no utility can switch one off, and they do block. The
    amendment of 2026-08-21 records the distinction on the rule itself.
    """
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
    blocking = result["blocking_rules"]
    # ⛔ **THESE WERE 0 / 5 / 5 AND A PO RULING MOVED THEM (`DEF-2794`,
    # `BR-MET-091` amendment 2, 2026-09-01).** `CR-046` C2 built
    # `PRM.PREMISE_NO_NOT_ON_FILE` — a premise id NOT already on file is one the
    # operator invented — as a tier-2 PLATFORM rule at ERROR severity, and C5
    # added `PRM.EXTERNAL_REF_UNIQUE` as a sixth tier-1 STRUCTURAL error. So a
    # premises import CAN now be stopped by a platform rule, which is the exact
    # sentence this case used to deny.
    #
    # **What the case is FOR is unchanged**: a UTILITY still cannot configure an
    # error into existence. Every error here comes from a ruling or from the
    # schema, never from a tenant's settings — that is the distinction
    # `BR-MET-091` amendment 1 drew and it survives amendment 2 intact.
    assert blocking["platform"] == 1, (
        "one PLATFORM rule blocks a premises load — PRM.PREMISE_NO_NOT_ON_FILE, "
        "built by CR-046 C2 under the PO's 2026-08-27 numbering ruling"
    )
    assert blocking["structural"] == 6, "the six structural rules always can"
    assert blocking["count"] == 7


def test_tc17__changing_a_rule_does_not_change_an_old_runs_receipt(brazos, marcus):
    """TC-17 / BR-MET-090 — *"a receipt reading '2 warnings' in July would read
    '2 errors' in August with nothing to show the run itself never changed."*"""
    with tenant_ctx(brazos):
        first = _full_cycle(marcus)
        assert first["counts"]["warnings"] == 2
        assert first["counts"]["errors"] == 3

        # the utility raises "premise type" from warning to error
        models.ImportRule.objects.create(
            tenant_id=brazos.id,
            code="PRM.TYPE_IN_LOOKUP",
            target="premises",
            tier=2,
            severity="error",
            action="reject_row",
        )
        second = _full_cycle(marcus)
        reread = import_runs.read_run(first["id"])

    # the NEW run sees the new set…
    assert second["counts"]["errors"] == 5
    assert second["counts"]["warnings"] == 0
    # …and the OLD run's stored receipt is untouched, read back from the table.
    old_rule = next(r for r in reread["rules"] if r["code"] == "PRM.TYPE_IN_LOOKUP")
    assert old_rule["severity"] == "warning"
    assert old_rule["action"] == "flag_only"
    assert reread["counts"]["warnings"] == 2
    assert reread["counts"]["errors"] == 3


def test_a_structural_rule_can_never_be_reconfigured(brazos, marcus):
    """BR-MET-090 — tier 1 comes from the schema and the hard rules. A row that
    claims to switch one off is IGNORED, because the alternative is a screen
    reporting that a rule the database enforces has been turned off."""
    with tenant_ctx(brazos):
        models.ImportRule.objects.create(
            tenant_id=brazos.id,
            code="PRM.ADDRESS_REQUIRED",
            target="premises",
            tier=2,
            severity="off",
            action="flag_only",
        )
        result = _full_cycle(marcus)
    rule = next(r for r in result["rules"] if r["code"] == "PRM.ADDRESS_REQUIRED")
    assert rule["severity"] == "error"
    assert rule["action"] == "reject_row"
    assert rule["hits"] == 1


def test_a_tenant_rule_of_its_own_runs(brazos, marcus):
    """Tier 3 — *"every premise must carry an owner"*, one of B15 §4.3A's own
    three examples."""
    body = _csv([_row(1, OWNER="")])
    with tenant_ctx(brazos):
        models.ImportRule.objects.create(
            tenant_id=brazos.id,
            code="TEN.OWNER_REQUIRED",
            target="premises",
            tier=3,
            sentence="Every premises must name an owner.",
            severity="error",
            action="reject_row",
            rule_kind="required_field",
            params={"field": "owner_manager", "label": "owner"},
        )
        result = _full_cycle(marcus, content=body)
        row = models.ImportRunRow.objects.get(run_id=result["id"], row_no=1)
    assert row.outcome == "rejected"
    assert row.problem == "This row has no owner."
    rule = next(r for r in result["rules"] if r["code"] == "TEN.OWNER_REQUIRED")
    assert rule["tier"] == 3 and rule["available"] is True


def test_a_tenant_rule_we_cannot_evaluate_is_listed_unavailable(brazos, marcus):
    """BR-MET-091 applied to the tenant's own half: *"no premise outside our
    three ZIP codes"* needs a value list and has no evaluator. A rule the
    utility authored and cannot see on the receipt is a rule they believe is
    protecting them."""
    with tenant_ctx(brazos):
        models.ImportRule.objects.create(
            tenant_id=brazos.id,
            code="TEN.ZIP_ALLOWLIST",
            target="premises",
            tier=3,
            sentence="No premises outside our three ZIP codes.",
            severity="error",
            action="reject_row",
            rule_kind="value_in_list",
            params={"field": "postal_code", "values": ["77494"]},
        )
        result = _full_cycle(marcus)
    rule = next(r for r in result["rules"] if r["code"] == "TEN.ZIP_ALLOWLIST")
    assert rule["available"] is False
    assert rule["hits"] == 0
    assert "cannot make yet" in rule["unavailable_reason"]


def test_the_rejects_list_carries_a_sentence_and_a_fix_for_every_row(brazos, marcus):
    """r10's own reject list — row, key, problem, fix. A hit with no sentence
    is a number with no explanation."""
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
    assert len(result["rejects"]) == 3
    for reject in result["rejects"]:
        assert reject["problem"], "a reject with no sentence tells the operator nothing"
        assert reject["fix_hint"]
        assert reject["source_key"]
        # CR-028 debt sweep D8: the row's SOURCE cells ride with the reject —
        # the stage-3 inline "fix here" editor edits exactly these, and
        # fix_row patches them by the same column names.
        assert (
            isinstance(reject["raw"], dict) and reject["raw"]
        ), "a reject must carry its raw cells for the inline editor"


# ═══════════════════════════════════════════════════════════════════════════
# THE HARD RULES — audit and tenant scoping
# ═══════════════════════════════════════════════════════════════════════════


def test_tc22__every_stage_writes_an_audit_row(brazos, marcus, audit_rows):
    """BR-MET-048 — an audit trail that started at stage 4 could not answer
    *who uploaded this file* for a run that never loaded."""
    with tenant_ctx(brazos):
        _full_cycle(marcus)
    actions = [row["action"] for row in audit_rows if row["action"].startswith("import_run.")]
    assert actions == ["import_run.extracted", "import_run.transformed", "import_run.validated"]
    extracted = next(r for r in audit_rows if r["action"] == "import_run.extracted")
    assert extracted["after"]["rows"] == 431
    assert extracted["actor_user_id"] == marcus.id


def test_tc23__a_run_is_invisible_to_another_tenant(brazos, marcus, lonestar, erin):
    """CLAUDE.md hard rule 1 — no cross-tenant queryset, RLS FORCE behind it.

    ⚠ Two halves, and only one of them can be measured here. The APPLICATION
    half is asserted: every query in `import_runs` carries `tenant_id=` and
    another tenant's run is a NotFound however it is asked for. The DATABASE
    half — `import_runs_tenant_isolation` FORCEd in migration 0015 — cannot be
    exercised on the sqlite test database, where RLS does not exist; that proof
    is the G5 live-Postgres isolation sweep (NFR-10). Asserting a bare
    `ImportRun.objects.filter(pk=…)` here would pass on Postgres and fail on
    sqlite for a reason that has nothing to do with the guarantee.
    """
    with tenant_ctx(brazos):
        run = _extract(marcus)
    with tenant_ctx(lonestar):
        assert models.ImportRun.objects.filter(tenant_id=lonestar.id, pk=run["id"]).count() == 0
        with pytest.raises(errors.NotFoundError):
            import_runs.read_run(run["id"])
        with pytest.raises(errors.NotFoundError):
            import_runs.transform(erin, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
        with pytest.raises(errors.NotFoundError):
            import_runs.validate(erin, run["id"])


def test_the_run_carries_the_receipt_fields(brazos, marcus):
    """B15 §4.5's receipt: SOURCE · FILE HASH · RUN BY · SESSION · IP ·
    MAPPING USED. Stage 5 draws them; stage 1 is what records them."""
    with tenant_ctx(brazos):
        run = _extract(marcus)
        stored = models.ImportRun.objects.get(pk=run["id"])
    assert stored.file_name == "silvercreek_premises_2026.csv"
    assert stored.session_ref == "sess_2b41"
    assert str(stored.ip) == "71.42.108.14"
    assert stored.run_by_id == marcus.id
    # ⛔ **`IMP-`, NOT `RUN-` — DEF-615, and the catalogue is the half that is
    # right.** This line asserted `RUN-` from the day CR-023 landed, and the
    # seeded default for the `import_run` series is `IMP-{YY}{MM}{DD}-{00}`, so
    # a run numbers `IMP-260824-01` and this assertion failed. It is not a
    # coin-toss between the two: **OQ-342 (PO ruling 2026-08-23, verbatim
    # *"A: a real series (RUN-0001, like RT-001)"*) gave `RUN-` to the BILL RUN
    # series**, and `core/numbering.py` records the consequence at that ruling —
    # *"`import_run` IS NOT THIS AND NEVER WAS … the ruling wins and `import_run`
    # opens on `IMP-{YY}{MM}{DD}-{00}`"*. Two series sharing a prefix would greet
    # every new tenant with CR-005's duplicate-prefix warning. So this assertion
    # was pinning a default the PO has since ruled away, and it now asserts what
    # the tenant is actually seeded with. `RUN-` remains OFFERED on this series
    # (a duplicate prefix is a warning, never a block), so a tenant that chooses
    # it is still lawful — this asserts the SEEDED DEFAULT only.
    # The drift itself is guarded now: `tests/test_def615_series_defaults.py`
    # renders every series' seeded default and pins its prefix, so a catalogue
    # entry and its expectations cannot disagree silently again.
    assert stored.run_no and stored.run_no.startswith("IMP-"), stored.run_no


def test_nothing_writes_a_rollback_point_yet(brazos, marcus):
    """⛔ B15 §8 Q7 — *"available for 30 days"* is r10 copy, not a signed
    figure. The table exists so a receipt never promises a rollback with no row
    behind it; nothing may default the window on the way past."""
    with tenant_ctx(brazos):
        _full_cycle(marcus)
        assert models.RollbackPoint.objects.count() == 0


def test_re_mapping_clears_the_previous_verdict(brazos, marcus):
    """r10 invites a remap — *"You can still remap at the next stage"* — so
    stage 2 can run over a run stage 3 has already judged.

    The old rule results and the old checked/clean/errors/warnings must go with
    the old mapping, or the screen shows a verdict on a mapping that no longer
    exists. ⚠ This is NOT in tension with BR-MET-090's *stored, never
    recomputed*: that protects a run whose LOAD has happened, and nothing here
    has loaded anything — there is no history to rewrite, only a rehearsal to
    redo.
    """
    with tenant_ctx(brazos):
        result = _full_cycle(marcus)
        assert result["counts"]["errors"] == 3
        # 8, not 9, since `BR-MET-097` (PO 2026-08-21) removed
        # `PRM.ADDRESS_IN_TERRITORY` from the declared premises rules. A result
        # row is written for every DECLARED rule, including the unavailable
        # ones, so this count is the size of the declared set and it moved by
        # exactly one when the rule was ruled away.
        # 9 since 2026-08-22: `PRM.PREMISE_NO_ON_FILE` joined when `DEF-543`
        # split the on-file half of uniqueness into its own WARNING. (8 after
        # BR-MET-097 removed the territory rule; 9 before that.)
        assert models.ImportRuleResult.objects.filter(run_id=result["id"]).count() == 9

        again = import_runs.transform(
            marcus, result["id"], {"mapping": MAPPING, "row_handling": ALL_ON}
        )
        assert models.ImportRuleResult.objects.filter(run_id=result["id"]).count() == 0
        assert "errors" not in again["counts"]
        assert "checked" not in again["counts"]
        assert again["counts"]["forward"] == 428  # the transform figures DO survive
        assert again["status"] == "transformed"


def test_error_severity_helper_reports_what_can_block(brazos, marcus):
    """The helper the Validate screen reads, exercised directly so the
    arithmetic behind `blocking_rules` is not only asserted end to end."""
    with tenant_ctx(brazos):
        rules = import_rules.resolve("premises", brazos.id)
    blocking = import_rules.error_severity_rules(rules)
    # ⛔ **FIVE BECAME SEVEN ON 2026-08-27 AND THIS SET WAS NEVER UPDATED
    # (`DEF-2794`).** `CR-046` C2 and C5 added the last two under the PO's
    # numbering ruling. Listed by name rather than counted, so the next rule to
    # arrive names itself here instead of moving a number nobody reads.
    assert {rule.code for rule in blocking} == {
        "PRM.ADDRESS_REQUIRED",
        "PRM.PREMISE_NO_UNIQUE",
        "PRM.PREMISE_NO_NOT_ON_FILE",  # CR-046 C2 — tier 2, and the ONLY one
        "PRM.EXTERNAL_REF_UNIQUE",  # CR-046 C5
        "PRM.SERVICES_ENABLED",
        "PRM.REFERENCES_ON_FILE",
        "PRM.VALUES_PARSE",
    }
    # ⚠ **NOT `all(... TIER_STRUCTURAL)` ANY MORE, AND THE EXCEPTION IS THE
    # WHOLE OF `BR-MET-091` AMENDMENT 2.** Six of the seven are tier-1
    # structural — error by construction, from the schema. The seventh is
    # tier-2 PLATFORM, which is the claim amendment 1 said could never happen
    # and a PO ruling made possible. Asserted as one-and-six rather than
    # relaxed to "some are structural", so a rule quietly changing tier goes
    # red here.
    structural = {rule.code for rule in blocking if rule.tier == import_rules.TIER_STRUCTURAL}
    platform = {rule.code for rule in blocking if rule.tier == import_rules.TIER_PLATFORM}
    assert len(structural) == 6
    assert platform == {"PRM.PREMISE_NO_NOT_ON_FILE"}


# ═══════════════════════════════════════════════════════════════════════════
# BR-MET-096 / BR-MET-100 — THE UNITS TARGET
#
# ⚠ Every case here goes through the SAME three functions the premises cases
# use. That is the assertion, not a convenience: `BR-MET-096` (PO 2026-08-21)
# rules one workflow for both targets, so a units-only `extract_units` or a
# `if target == "units"` branch would be the second implementation it forbids.
# ═══════════════════════════════════════════════════════════════════════════


def seed_units_world(actor) -> list[str]:
    """The two premises and the one plan a units file references, and it
    returns the premise numbers the SERVER allocated.

    ⚠ **THIS IS THE PO'S LOAD ORDER, AS A FIXTURE** (2026-08-21): *"when unit
    are uploaded, both plans and premises should be in system so that we can map
    many to many correctly"*. A units suite that invented its own parent rows
    would be testing a shortcut the product does not offer.

    ⚠ **AND IT READS THE NUMBERS BACK RATHER THAN CHOOSING THEM.** The first
    draft passed `premise_no` to `create_premises` and was refused
    `metering.unknown_field` — the number comes from the tenant's numbering
    series (BR-MET-005), not from the caller. A fixture that set it directly on
    the model would have hidden that, and then the units file would have
    referenced a premise number no real import could ever produce.

    `RES-STD-2027` is deliberately NOT created — it is the misspelling
    `BR-MET-100` is about.
    """
    from apps.metering import services as metering_services
    from apps.rating import models as rating_models

    numbers = []
    for address in ("1408 Elm Street", "22 Cedar Row"):
        created = metering_services.create_premises(actor, {"owner_id": owner_for(actor), "address_line": address})
        premises = models.Premises.objects.get(pk=created["id"])
        numbers.append(premises.premise_no)
    rating_models.RatePlan.objects.create(
        tenant_id=core_tenancy.current_tenant_id(),
        code="RES-STD",
        name="Residential Standard",
        status="published",
        version=1,
    )
    return numbers


def _units_cycle(actor, *, mapping=None, content=None, edit=None):
    """Seed the world, then run the SAME three functions the premises cases do.

    `edit` is a callable over the generated CSV, so a case can corrupt one
    field (a wrong premise, a duplicate label) without hardcoding a premise
    number the server has not allocated yet.
    """
    numbers = seed_units_world(actor)
    body = units_csv(numbers) if content is None else content
    if edit is not None:
        body = edit(body, numbers)
    run = import_runs.extract(
        actor,
        {
            "target": "units",
            "source_kind": "file",
            "file_name": "riverside_units.csv",
            "content": body,
        },
    )
    import_runs.transform(
        actor,
        run["id"],
        {"mapping": mapping or UNITS_MAPPING, "row_handling": ALL_ON},
    )
    return import_runs.validate(actor, run["id"])


def test_br_met_096__the_maps_to_list_is_the_UNIT_table_not_the_premises_one(brazos, marcus):
    """BR-MET-088 over the second target: the picker offers the columns
    `metering.Unit` actually has, derived from its own `_meta`."""
    with tenant_ctx(brazos):
        columns = {entry["target"] for entry in import_runs.target_columns("units")}
    assert {"label", "premises", "unit_type", "square_feet", "rate_plan"} <= columns
    # ⚠ and NOT the premises columns — this is the whole of what Transform
    # differentiates (`BR-MET-096`).
    assert "address_line" not in columns
    assert "premise_no" not in columns


def test_br_met_096__the_four_columns_r10_draws_and_we_do_not_offer(brazos, marcus):
    """r10's units sheet has ten columns and this product honours six.

    ⚠ **EACH ABSENCE IS A RULING OR A MISSING TABLE, NEVER AN OVERSIGHT**, and
    a test says so per column so that adding one back is a deliberate act:
      * `METER_E`/`METER_W` — PO 2026-08-21: *"we will not add meter or asset
        here when we are uploading units"* (BR-MET-093).
      * `OCCUPANT` — no occupant column on `units`.
      * `STATUS` — `units` has NO occupancy column BY DESIGN; unit status is
        computed for display, so a mapping target could not be written.
    """
    with tenant_ctx(brazos):
        columns = {entry["target"] for entry in import_runs.target_columns("units")}
        detected = import_runs._auto_map(
            ["UNIT_REF", "PREMISE_ID", "METER_E", "METER_W", "OCCUPANT", "STATUS", "ROUTE"],
            "units",
        )
    for absent in ("meter_e", "meter_w", "occupant", "occupancy_status", "route"):
        assert absent not in columns
    # detection must not guess them onto anything either
    assert set(detected) == {"UNIT_REF", "PREMISE_ID"}


def test_br_met_096__stage_2_carries_the_premise_and_plan_as_TEXT(brazos, marcus):
    """A reference is the customer's own text until LOAD — the posture
    `KIND_AREA` already takes. Resolving ids in a rehearsal would depend on
    data that can change before the commit."""
    with tenant_ctx(brazos):
        numbers = seed_units_world(marcus)
        run = import_runs.extract(
            marcus,
            {
                "target": "units",
                "source_kind": "file",
                "file_name": "riverside_units.csv",
                "content": units_csv(numbers),
            },
        )
        import_runs.transform(marcus, run["id"], {"mapping": UNITS_MAPPING, "row_handling": ALL_ON})
        first = models.ImportRunRow.objects.get(run_id=run["id"], row_no=1)
    # ⚠ the number the SERVER allocated, not one this test chose — see
    # `seed_units_world`. The first draft hardcoded `P-10001` on both sides,
    # which proved only that a constant equals itself.
    assert first.mapped["premises_ref"] == numbers[0]
    assert first.mapped["rate_plan_ref"] == "RES-STD"
    assert first.mapped["label"] == "U-10432-A"
    assert first.mapped["square_feet"] == 980  # KIND_INTEGER parsed, not text


def test_br_met_100__a_row_naming_a_missing_plan_is_a_WARNING_not_a_rejection(brazos, marcus):
    """⚠ **THE PO OVERRULED THE RECOMMENDATION HERE AND THIS IS THE CASE THAT
    PINS IT.** Option A rejected the row and named the plan; the PO ruled B —
    load it, flag it. So the rule's severity is WARNING, the row's outcome is
    `flagged` rather than `rejected`, and it is NOT counted in `errors`.

    If someone later "fixes" this to reject, this case goes red and the ruling
    it reverses is named right here.
    """
    with tenant_ctx(brazos):
        result = _units_cycle(marcus)
        by_code = {rule["code"]: rule for rule in result["rules"]}
        plan_rule = by_code["UNT.PLAN_ON_FILE"]
        assert plan_rule["severity"] == "warning"
        assert plan_rule["action"] in ("flag_only", "flag")
        assert plan_rule["hits"] == 1  # the RES-STD-2027 row, and only it
        row = models.ImportRunRow.objects.get(run_id=result["id"], row_no=4)
    assert row.outcome == "flagged"
    assert "RES-STD-2027" in (row.problem or "")
    # ⚠ and the fix hint carries the cost the PO accepted, in words: this unit
    # will exist and will not bill.
    assert "cannot be billed" in (row.fix_hint or "")


def test_br_met_100__the_plan_rule_hits_nothing_when_every_plan_is_on_file(brazos, marcus):
    """The mirror, so the case above is not passing for the wrong reason."""
    with tenant_ctx(brazos):
        result = _units_cycle(marcus, edit=lambda body, _n: body.replace("RES-STD-2027", "RES-STD"))
        by_code = {rule["code"]: rule for rule in result["rules"]}
    assert by_code["UNT.PLAN_ON_FILE"]["hits"] == 0


def test_units__a_missing_parent_premise_REJECTS(brazos, marcus):
    """r10's own error-severity units rule, and the one it shows hitting —
    row 119, `U-11902-B`, *"Parent premise P-11902 was not loaded"*.

    ⚠ The contrast with the case above is the whole of `BR-MET-100`: a missing
    PREMISE rejects because the unit has nowhere to live; a missing PLAN does
    not, because the unit exists and simply cannot bill yet.
    """
    with tenant_ctx(brazos):
        result = _units_cycle(marcus, edit=lambda body, nums: body.replace(nums[1], "P-99999"))
        by_code = {rule["code"]: rule for rule in result["rules"]}
        premise_rule = by_code["UNT.PARENT_PREMISE_ON_FILE"]
        assert premise_rule["severity"] == "error"
        assert premise_rule["hits"] == 2
        rejected = models.ImportRunRow.objects.filter(
            run_id=result["id"], outcome="rejected"
        ).count()
    assert rejected == 2
    assert result["counts"]["errors"] == 2
    # BR-MET-091: with a real error-severity rule on this target, the blocking
    # count is NOT zero — the premises number (BR-MET-097) is a premises fact.
    assert result["blocking_rules"]["count"] >= 1


def test_units__a_duplicate_label_in_one_premise_is_FLAGGED_never_suffixed(brazos, marcus):
    """⚠ **A DELIBERATE DIVERGENCE FROM r10, STAMPED RATHER THAN SILENT.**
    r10's action column reads *"suffix and continue"*. We flag instead: silently
    renaming a customer's unit `12` to `12-2` invents an identifier the utility
    never chose, cannot search for and will not recognise on a bill.
    """
    with tenant_ctx(brazos):
        result = _units_cycle(marcus, edit=lambda body, _n: body.replace("U-10432-B", "U-10432-A"))
        by_code = {rule["code"]: rule for rule in result["rules"]}
        rule = by_code["UNT.LABEL_UNIQUE_IN_PREMISE"]
        assert rule["severity"] == "warning"
        assert rule["hits"] == 1
        row = models.ImportRunRow.objects.get(run_id=result["id"], row_no=2)
    assert row.outcome == "flagged"
    # the label is UNTOUCHED — nothing was suffixed
    assert row.mapped["label"] == "U-10432-A"


def test_units__the_same_label_in_a_DIFFERENT_premise_is_fine(brazos, marcus):
    """Unique WITHIN its premise. `Unit A` in two buildings is normal."""
    with tenant_ctx(brazos):
        result = _units_cycle(marcus, edit=lambda body, _n: body.replace("U-10433-A", "U-10432-A"))
        by_code = {rule["code"]: rule for rule in result["rules"]}
    assert by_code["UNT.LABEL_UNIQUE_IN_PREMISE"]["hits"] == 0


def test_units__stage_3_writes_no_unit(brazos, marcus):
    """BR-MET-085 over the second target: stages 1–3 are a rehearsal."""
    with tenant_ctx(brazos):
        before = models.Unit.objects.count()
        _units_cycle(marcus)
        after = models.Unit.objects.count()
    assert before == after


# ═══════════════════════════════════════════════════════════════════════════
# DEF-522 — AN UNRECOGNISED ROW-HANDLING OPTION IS REFUSED, NEVER COERCED
# ═══════════════════════════════════════════════════════════════════════════
#
# The kit's `contract.ts` named the middle checkbox `keep_latest_on_duplicate_
# key`; `import_runs.ROW_HANDLING_KEYS` has always called it
# `keep_latest_on_key`. Stage 2 read its three options with a dict
# comprehension over that fixed tuple, so the kit's spelling was NOT refused —
# it was read as `False`. The operator ticked *"keep the latest row when a key
# appears twice"*, the server kept the FIRST row, and nothing 400'd, nothing
# logged and every test on both sides passed because each side sent its own
# spelling.
#
# ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN** (hard-won law 7). With the
# refusal removed and the old comprehension restored, this file reported,
# verbatim:
#
#     E       Failed: DID NOT RAISE ValidationError
#     FAILED tests/test_cr023_import_stages.py::
#            test_def522__an_unknown_row_handling_option_is_refused_by_name
#     1 failed, 1 passed, 50 deselected
#
# ⚠ **AND THE SECOND TEST BELOW PASSED UNDER THAT MUTATION — SAY SO.** It sends
# the SERVER's spelling both times, so it measures what the option does (4
# duplicates dropped ticked, 3 unticked) and NOT whether a misspelling is
# refused. It is here because the first test only proves a 400: without this
# one, nothing states the customer-visible half — the fourth drop is the
# repeated `premise_no` that *keep the latest* exists for, and a silent `False`
# is exactly the difference between 4 and 3. Only the first test is the
# red-proof; claiming both would be hard-won law 1 in a test file.


def test_def522__an_unknown_row_handling_option_is_refused_by_name(brazos, marcus):
    """A misspelled option is a 400 that NAMES it, not a silent `False`."""
    handling = {**ALL_ON, "keep_latest_on_duplicate_key": True}
    with tenant_ctx(brazos):
        run = _extract(marcus)
        with pytest.raises(errors.ValidationError) as refusal:
            import_runs.transform(marcus, run["id"], {"mapping": MAPPING, "row_handling": handling})
    assert refusal.value.message_key == "metering.import.unknown_row_handling"
    assert refusal.value.params["option"] == "keep_latest_on_duplicate_key"
    # The whole vocabulary travels beside the offender, so the operator can fix
    # it without reading our source.
    assert refusal.value.params["allowed"] == list(import_runs.ROW_HANDLING_KEYS)


def test_def522__the_kits_old_spelling_used_to_keep_the_FIRST_row(brazos, marcus):
    """THE CUSTOMER-VISIBLE HALF, on a file carrying both duplicate shapes.

    The file carries 3 exact duplicates plus 1 row repeating a `premise_no`.
    With `keep_latest_on_key` ticked the run drops **4**; with the kit's old
    spelling it dropped **3** and kept the EARLIER of the two rows sharing the
    key — the opposite of what the operator asked for. Now that the misspelling
    refuses, the only way to reach 3 is to leave the box unticked, which is an
    honest answer to an honest request.

    ⚠ Measured on §16's own 431 rows until 2026-09-01; it runs on
    `dedupe_csv()` now, and that helper's docstring says why (`DEF-2794`).
    """
    with tenant_ctx(brazos):
        body = dedupe_csv()
        ticked = import_runs.transform(
            marcus,
            _extract(marcus, content=body)["id"],
            {"mapping": MAPPING, "row_handling": {**ALL_ON, "keep_latest_on_key": True}},
        )
        unticked = import_runs.transform(
            marcus,
            _extract(marcus, content=body)["id"],
            {"mapping": MAPPING, "row_handling": {**ALL_ON, "keep_latest_on_key": False}},
        )
    assert ticked["counts"]["duplicates_dropped"] == 4
    assert unticked["counts"]["duplicates_dropped"] == 3
