# ── Trace ──────────────────────────────────────────────
# Change:  CR-046 waves C2 · C3 · C4 · C5 · C6 — the identifier is ISSUED from
#          the tenant's series on premises, units and accounts too, the column
#          becomes the MATCH KEY, and the write mode decides a known record's
#          fate.   Screens: WFL-01 premises/units/accounts import, stages 1–5
# Rules:   BR-MET-403 (new — the utility's own PREMISE reference, unique per
#          tenant) · BR-MET-404 (new — the same on `units`) · BR-CUS-172 (new —
#          the same on `accounts`) · BR-AST-049 (the meters precedent all three
#          follow) · BR-TEN-035 (the series is forward-only) · BR-CUS-017 (one
#          live account per unit — why a duplicate accounts load is a pile of
#          refusals) · BR-MET-401 as NARROWED 2026-08-27 (a blank owner LOADS
#          on the import) · hard rule 4 (an update re-posts no opening balance)
# Tests:   this file
# Impacts: apps/metering/import_runs.py · import_rules.py · seams.py ·
#          apps/customers/services.py · selectors.py · two migrations
# ───────────────────────────────────────────────────────
"""CR-046 C2–C6 — RED-FIRST PROOF (r11 step 2d).

Every guard below was broken FIRST, against the tree as it stood before this
lane's change, and the failure quoted. The four that matter:

**C2 · the premises number is issued, not read off the file.**
`test_cr046_c2__a_new_premises_takes_its_number_from_the_series` run against
the prior tree:

    AssertionError: the file's own P-10001 reached the table — the series
    issued nothing
    assert 'P-10001' == 'P-00101'

**C3 · the identity is the PAIR, and matching on the label alone overwrites a
different building's flat.** `test_cr046_c3__same_label_two_premises_is_two_
units` with `_key_of` reduced to the label only:

    AssertionError: Apt 3B at P-00102 was OVERWRITTEN by a row about
    P-00101 — 1 unit exists where 2 should
    assert 1 == 2

**C4 · a second load of the same accounts file duplicated the whole book.**
`test_cr046_c4__a_corrected_rerun_updates_and_does_not_duplicate` on the prior
tree, where `_load_accounts_rows` matched nothing at all:

    core.errors.BizError: BIZ-002 customers.account.unit_already_occupied
    (BR-CUS-017)

**C5 · `external_ref` was not unique, so it could not be a match key.**
`test_cr046_c5__external_ref_is_unique_per_tenant_case_insensitively` before
migration 0042:

    AssertionError: a second premises took the SAME external reference —
    the column cannot identify a row
    (no IntegrityError was raised)

Every walk here drives the REAL five stages on a seeded tenant.
"""

import csv
import io

import pytest
from django.db import IntegrityError, transaction

from apps.customers import models as customer_models
from apps.metering import import_rules, import_runs, models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

ALL_OFF = {
    "drop_exact_duplicates": False,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}


def _csv(headers: list[str], rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _validated(actor, target: str, content: str, mapping: dict, mode: str = "insert") -> str:
    """Stages 1–3. ⚠ `mode` is stage 3's, and it MATTERS since CR-046 wave B:
    the run's write mode reaches the rule catalogue, so *"this row names a
    record already on file"* is an ERROR under `insert` and a flag under
    `upsert`. Validating in one mode and committing in another is a real path
    (the mode is changeable at stage 4) and is exercised deliberately below."""
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": f"cr046_{target}.csv",
            "content": content,
            "session_ref": "sess_cr046",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"], mode)
    return run["id"]


def _commit(actor, run_id: str, mode: str) -> dict:
    """Stage 4, approving only when `BR-MET-098`'s bar is actually crossed.

    ⚠ **`approved: True` IS NOT A NO-OP WHEN NO APPROVAL IS NEEDED** — since
    `DEF-545` a Billing Clerk sending it is REFUSED BY NAME rather than
    obeyed, in both layers. Two tests here learned that the hard way; the
    helper asks the rehearsal first, which is what a screen does.
    """
    figures = import_runs.dry_run(actor, run_id, mode)
    payload: dict = {"write_mode": mode}
    if figures["approval"]["required"]:
        payload["approved"] = True
    return import_runs.load(actor, run_id, payload)


def _world_for(tenant):
    """The same world stage 3 builds, for asserting one rule's own sentence."""
    return import_runs._world()


def _rejects(run_id) -> dict[int, tuple[str, str | None]]:
    """⚠ **`import_runs.rejects` SERVES FLAGGED ROWS TOO**, because r10's stage-3
    list shows everything that has something to say about it. Only rows whose
    OUTCOME is `rejected` did not load, and that is what this asks."""
    return {
        row["row_no"]: (row["problem"], row["fix_hint"])
        for row in import_runs.rejects(models.ImportRun.objects.get(pk=run_id))
        if row["outcome"] == "rejected"
    }


def _flags(run_id) -> dict[int, tuple[str, str | None]]:
    """The rows that LOAD and have something to say about themselves."""
    return {
        row["row_no"]: (row["problem"], row["fix_hint"])
        for row in import_runs.rejects(models.ImportRun.objects.get(pk=run_id))
        if row["outcome"] != "rejected"
    }


PREMISES_HEADERS = ["PREMISE_ID", "ADDR1", "SVC_AVAIL", "LEGACY_KEY"]
PREMISES_MAPPING = {
    "PREMISE_ID": "premise_no",
    "ADDR1": "address_line",
    "SVC_AVAIL": "services_available",
    "LEGACY_KEY": "external_ref",
}
UNITS_HEADERS = ["UNIT_NO", "PREMISE_ID", "UNIT_REF", "LEGACY_KEY"]
UNITS_MAPPING = {
    "UNIT_NO": "unit_no",
    "PREMISE_ID": "premises",
    "UNIT_REF": "label",
    "LEGACY_KEY": "external_ref",
}


# ═══════════════════════════════════════════════════════════════════════════
# C2 · PREMISES — the number is OURS to issue
# ═══════════════════════════════════════════════════════════════════════════


def test_cr046_c2__a_new_premises_takes_its_number_from_the_series(brazos, marcus, dana):
    """⛔ **THE RULING, IN ONE ASSERTION** (PO 2026-08-27, widened to all four
    uploads by CR-046): *"we have number system set in the settings, we shoudl
    call that function and get unique number and assign it"*.

    The file says `P-10001`. The tenant's `premises` series stands at 101 with
    format `P-{00000}`. The row must land as **`P-00101`**, and the file's own
    string must be nowhere on the record.
    """
    content = _csv(
        PREMISES_HEADERS,
        [
            {
                "PREMISE_ID": "",
                "ADDR1": "1 Bluestem Ln",
                "SVC_AVAIL": "electric",
                "LEGACY_KEY": "GIS-9001",
            }
        ],
    )
    with tenant_ctx(brazos):
        run_id = _validated(marcus, "premises", content, PREMISES_MAPPING)
        _commit(dana, run_id, "insert")

        row = models.Premises.objects.get(address_line="1 Bluestem Ln")
        assert row.premise_no == "P-00101", (
            f"the series was supposed to issue P-00101 and the row carries "
            f"{row.premise_no!r}"
        )
        # ⚠ The utility's OWN reference is KEPT — the whole point of C5. A
        # ruling that took the number away and lost the legacy id with it would
        # have made the migration unreconcilable.
        assert row.external_ref == "GIS-9001"


def test_cr046_c2__a_quoted_number_this_utility_never_issued_is_refused(brazos, marcus, dana):
    """`PRM.PREMISE_NO_NOT_ON_FILE` — an INVENTED premise ID, which is exactly
    what the ruling forbids. It is wrong in BOTH write modes, so it blocks at
    stage 3 where the operator can still fix the file by clearing a cell.

    ⚠ **THE FIX HINT NAMES THE OTHER COLUMN.** Told only *"leave it blank"* an
    operator would DELETE their old system's ids, which have nowhere else to go.
    """
    content = _csv(
        PREMISES_HEADERS,
        [
            {
                "PREMISE_ID": "P-99999",
                "ADDR1": "2 Bluestem Ln",
                "SVC_AVAIL": "electric",
                "LEGACY_KEY": "",
            }
        ],
    )
    with tenant_ctx(brazos):
        run_id = _validated(marcus, "premises", content, PREMISES_MAPPING)
        rejects = _rejects(run_id)
        assert 1 in rejects, "a number this utility never issued has to be refused"
        problem, hint = rejects[1]
        assert "P-99999" in problem
        assert "External reference" in (hint or ""), (
            "the hint must name where the operator's own id goes, or they will "
            "delete data with no other home"
        )
        assert models.Premises.objects.filter(address_line="2 Bluestem Ln").count() == 0


def test_cr046_c2__insert_new_only_rejects_a_row_that_names_one_on_file(brazos, marcus, dana):
    """⛔ **PO verbatim: *"in case of insert - reject it"*.**

    Before CR-046 this row was silently `continue`d: the receipt said nothing
    about it and the operator read *"nothing needed doing"* about a row that had
    not loaded. The difference between a skip and a reject is what they do next.
    """
    with tenant_ctx(brazos):
        existing = make_premises(marcus, address_line="3 Bluestem Ln")
        content = _csv(
            PREMISES_HEADERS,
            [
                {
                    "PREMISE_ID": existing["premise_no"],
                    "ADDR1": "3 Bluestem Ln — corrected",
                    "SVC_AVAIL": "electric",
                    "LEGACY_KEY": "",
                }
            ],
        )
        # ── PATH 1 · the mode was chosen at stage 1, so stage 3 knows it and
        # refuses the row THERE, where the operator can still fix the file.
        # (`CR-042` moved the choice to step 1; `DEF-543`'s stated obstacle —
        # *"stage 3 does not know the write mode"* — stopped being true and
        # nobody had read the two together.)
        run_id = _validated(marcus, "premises", content, PREMISES_MAPPING, "insert")
        rejects = _rejects(run_id)
        assert 1 in rejects, "an on-file row under Insert new only must not load"
        assert existing["premise_no"] in rejects[1][0]

        # ── PATH 2 · **THE MODE IS STILL CHANGEABLE AT STAGE 4**, so the
        # loader must refuse it too — and REJECT it, not skip it. This is the
        # path `_insert_mode_on_file_sentences` exists for, and it is the one
        # that used to `continue` silently.
        rerun = _validated(marcus, "premises", content, PREMISES_MAPPING, "upsert")
        result = _commit(dana, rerun, "insert")
        counts = models.ImportRun.objects.get(pk=rerun).counts
        assert counts["rejected_existing"] == 1, (
            "an on-file row committed under Insert new only is REJECTED, not "
            f"skipped — counts were {counts!r}"
        )
        assert counts["created"] == 0
        row = import_runs.rejects(models.ImportRun.objects.get(pk=rerun))
        # `DEF-MET-9257`: the tab is *Numbering* (renamed in the hint 2026-08-30).
        assert any("Settings › Numbering" in (r["fix_hint"] or "") for r in row), (
            "the reject has to say where a number actually comes from, or the "
            "operator's next move is to invent a different one"
        )
        # …and the record it named is untouched.
        assert (
            models.Premises.objects.get(pk=existing["id"]).address_line == "3 Bluestem Ln"
        )
        assert result["status"] == "loaded"


def test_cr046_c2__insert_and_update_updates_the_details(brazos, marcus, dana):
    """The other half of the same PO sentence: *"in case of Insert & Update =
    update the details"*.

    ⚠ **AND THE NUMBER SURVIVES.** The row's identifier cell is what MATCHED;
    every other cell is an update. A blank cell means *"I am not telling you"*,
    never *"set this to nothing"* — so an update must never wipe a number the
    series issued.
    """
    with tenant_ctx(brazos):
        existing = make_premises(marcus, address_line="4 Bluestem Ln")
        content = _csv(
            PREMISES_HEADERS,
            [
                {
                    "PREMISE_ID": existing["premise_no"],
                    "ADDR1": "4 Bluestem Ln — corrected",
                    "SVC_AVAIL": "electric",
                    "LEGACY_KEY": "",
                }
            ],
        )
        # ⚠ Validated in the mode it will be committed in — under `upsert`
        # the on-file rule is a FLAG, which is the whole point of the mode.
        run_id = _validated(marcus, "premises", content, PREMISES_MAPPING, "upsert")
        assert _rejects(run_id) == {}, (
            "Insert & update exists for exactly this row — it must not be "
            "rejected at stage 3"
        )
        # …and the SENTENCE the operator reads says what each mode will do.
        # ⛔ CR-046 F2 — it used to read "Insert new only will skip it
        # unchanged", and the PO's word is REJECT: a skip reads as "nothing
        # needed doing", a reject reads as "this row did not load".
        hits = import_rules.evaluate(
            next(
                r
                for r in import_rules.PLATFORM_CATALOG["premises"]
                if r.code == "PRM.PREMISE_NO_ON_FILE"
            ),
            [{"row_no": 1, "mapped": {"premise_no": existing["premise_no"]}}],
            _world_for(brazos),
        )
        assert hits, "the on-file row must still say something about itself"
        assert "REJECT" in (hits[0].fix_hint or ""), hits[0]
        assert "skip it unchanged" not in (hits[0].fix_hint or "")
        _commit(dana, run_id, "upsert")
        row = models.Premises.objects.get(pk=existing["id"])
        assert row.address_line == "4 Bluestem Ln — corrected"
        assert row.premise_no == existing["premise_no"], (
            "the update wiped the number the series issued — a blank cell is "
            "not an instruction to clear a column"
        )


def test_cr046_c2__a_corrected_rerun_matches_on_the_legacy_reference(brazos, marcus, dana):
    """⛔ **THE CASE THE WHOLE OF C5 EXISTS FOR.**

    A first migration's file carries NO SMARTBillHub number — it never did. So
    a corrected re-run of that same file matches nothing under number-only
    matching and creates the entire estate a second time. `external_ref` is the
    only identifier such a file has, and CR-046 C5 makes it unique per tenant,
    so `_key_of` falls back to it.
    """
    content = _csv(
        PREMISES_HEADERS,
        [
            {
                "PREMISE_ID": "",
                "ADDR1": "5 Bluestem Ln",
                "SVC_AVAIL": "electric",
                "LEGACY_KEY": "GIS-5005",
            }
        ],
    )
    corrected = _csv(
        PREMISES_HEADERS,
        [
            {
                "PREMISE_ID": "",
                "ADDR1": "5 Bluestem Lane",
                "SVC_AVAIL": "electric,water",
                "LEGACY_KEY": "gis-5005",  # ⚠ LOWERCASE — the index is CI
            }
        ],
    )
    with tenant_ctx(brazos):
        first = _validated(marcus, "premises", content, PREMISES_MAPPING)
        _commit(dana, first, "insert")
        assert models.Premises.objects.filter(external_ref__iexact="GIS-5005").count() == 1

        second = _validated(marcus, "premises", corrected, PREMISES_MAPPING)
        _commit(dana, second, "upsert")

        rows = models.Premises.objects.filter(external_ref__iexact="GIS-5005")
        assert rows.count() == 1, (
            f"the corrected re-run created {rows.count()} premises where it "
            "should have updated one — the legacy key is the only identifier "
            "a first migration's file carries"
        )
        assert rows.first().address_line == "5 Bluestem Lane"


def test_cr046_c2__the_template_ships_the_identifier_cell_blank(brazos, marcus, dana):
    """`DEF-962`'s rule, on the two targets `DEF-962` did not reach.

    ⚠ **`sample=None` IS NOT `sample=""`.** A column that declares nothing
    falls through to the kind-generic worked value and would ship
    `Sample premise ID` — or, worse, `SAMPLE_TEXT_VALUES`' own `P-9001` — an
    invented number in the one file a first-time operator is told to start
    from, on the very column the PO objected to being asked to invent.
    """
    with tenant_ctx(brazos):
        for target, field in (("premises", "premise_no"), ("units", "unit_no")):
            _name, body = import_runs.sample_csv(target)
            _header, example = list(csv.reader(io.StringIO(body)))[:2]
            # DEF-1077 — the header is the column's LABEL now; the field order
            # comes from `sample_columns`, the list `sample_csv` itself writes.
            header = [str(c["target"]) for c in import_runs.sample_columns(target)]
            cells = dict(zip(header, example))
            assert cells[field] == "", (
                f"the {target} template proposes {cells[field]!r} for {field} — "
                "the number comes from Settings › Numbering and the template "
                "must not invent one"
            )
            # …and the column is STILL THERE, because it is the match key.
            assert field in header, (
                f"{field} was deleted from the {target} template — it is the "
                "match key Insert & update needs"
            )


def test_cr046_c2__the_column_says_what_it_now_takes(brazos, marcus, dana):
    """The header and the help text changed with the meaning. An operator
    reading *"Premise ID"* would fill it in; reading *"(existing only)"* they
    would not."""
    with tenant_ctx(brazos):
        columns = {c["target"]: c for c in import_runs.target_columns("premises")}
        entry = columns["premise_no"]
        assert entry["label"] == "Premise ID (existing only)"
        assert "LEAVE THIS BLANK" in entry["help"]
        assert "Settings → Numbering" in entry["help"]
        assert entry["sample"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# C3 · UNITS — the identity is the PAIR
# ═══════════════════════════════════════════════════════════════════════════


def test_cr046_c3__the_database_says_the_identity_is_the_pair(brazos, marcus, dana):
    """⛔ **CR-046 C3 ASKED THIS OUTRIGHT AND THE PO THEN CONFIRMED IT:
    *"premsies and unit name - not just unit name that combination is
    unique"*.**

    This test asserts the DATABASE's own answer, which is what the change
    request said to build to: `(tenant, premises, label)` is over two NOT NULL
    columns and therefore every unit has it; `(tenant, unit_no)` is over a
    NULLABLE column, so N units may carry no number at all. **A column that can
    be absent cannot be an identity.**
    """
    names = {c.name for c in models.Unit._meta.constraints}
    assert "uq_units_tenant_premises_label" in names
    assert "uq_units_tenant_unit_no" in names
    assert models.Unit._meta.get_field("label").null is False
    assert models.Unit._meta.get_field("premises").null is False
    assert models.Unit._meta.get_field("unit_no").null is True, (
        "if unit_no were NOT NULL the identity question would have a different "
        "answer — this assertion is what pins the reasoning to the schema"
    )


def test_cr046_c3__same_label_two_premises_is_two_units(brazos, marcus, dana):
    """⛔ **THE FAILURE THAT WOULD NEVER LOOK LIKE A FAILURE.**

    Two buildings each hold an `Apt 3B`. A file names ONE of them. Matching on
    the label alone would find the OTHER building's flat and, under *Insert &
    update*, quietly overwrite it — a row that loads clean, reports `updated`,
    and has rewritten somebody else's unit.

    The premises is half the key, so this must create a SECOND unit and leave
    the first exactly as it was.
    """
    with tenant_ctx(brazos):
        first = make_premises(marcus, address_line="10 Bluestem Ln")
        second = make_premises(marcus, address_line="20 Bluestem Ln")
        make_unit(marcus, first["id"], label="Apt 3B", square_feet=700)

        content = _csv(
            UNITS_HEADERS,
            [
                {
                    "UNIT_NO": "",
                    "PREMISE_ID": second["premise_no"],
                    "UNIT_REF": "Apt 3B",
                    "LEGACY_KEY": "",
                }
            ],
        )
        run_id = _validated(marcus, "units", content, UNITS_MAPPING)
        _commit(dana, run_id, "upsert")

        units = models.Unit.objects.filter(label="Apt 3B")
        assert units.count() == 2, (
            f"Apt 3B at {second['premise_no']} was matched against the one at "
            f"{first['premise_no']} — {units.count()} unit(s) exist where 2 should"
        )
        assert {str(u.premises_id) for u in units} == {
            str(first["id"]),
            str(second["id"]),
        }
        # The first building's flat is untouched — the overwrite did not happen.
        assert models.Unit.objects.get(premises_id=first["id"], label="Apt 3B").square_feet == 700


def test_cr046_c3__two_rows_naming_one_unit_are_an_error_not_a_warning(brazos, marcus, dana):
    """`UNT.LABEL_UNIQUE_IN_PREMISE` was flag-only while the pair was a
    convention. It is the IDENTITY now, so two rows naming `(premises, label)`
    twice are two rows claiming to be the same unit — and the database says so
    (`uq_units_tenant_premises_label`)."""
    with tenant_ctx(brazos):
        premises = make_premises(marcus, address_line="30 Bluestem Ln")
        content = _csv(
            UNITS_HEADERS,
            [
                {"UNIT_NO": "", "PREMISE_ID": premises["premise_no"], "UNIT_REF": "Apt 1", "LEGACY_KEY": ""},
                {"UNIT_NO": "", "PREMISE_ID": premises["premise_no"], "UNIT_REF": "Apt 1", "LEGACY_KEY": ""},
            ],
        )
        run_id = _validated(marcus, "units", content, UNITS_MAPPING)
        rejects = _rejects(run_id)
        assert 2 in rejects, "the second row claims to be the same unit as the first"
        assert "Row 1" in (rejects[2][1] or ""), rejects[2]
        rule = next(
            r for r in import_rules.PLATFORM_CATALOG["units"]
            if r.code == "UNT.LABEL_UNIQUE_IN_PREMISE"
        )
        assert rule.severity == import_rules.ERROR
        assert rule.action == import_rules.REJECT_ROW


def test_cr046_c3__the_unit_number_is_issued_from_the_series(brazos, marcus, dana):
    """C2's assertion, one noun along — and it is the `unit` series, at 101."""
    with tenant_ctx(brazos):
        premises = make_premises(marcus, address_line="40 Bluestem Ln")
        content = _csv(
            UNITS_HEADERS,
            [
                {
                    "UNIT_NO": "",
                    "PREMISE_ID": premises["premise_no"],
                    "UNIT_REF": "Apt 9",
                    "LEGACY_KEY": "LEG-9",
                }
            ],
        )
        run_id = _validated(marcus, "units", content, UNITS_MAPPING)
        _commit(dana, run_id, "insert")
        unit = models.Unit.objects.get(label="Apt 9")
        assert unit.unit_no == "U-00101", unit.unit_no
        assert unit.external_ref == "LEG-9"


def test_cr046_c3__a_units_file_quotes_a_premise_number_and_that_is_UNCHANGED(
    brazos, marcus, dana
):
    """⛔ **A CROSS-FILE REFERENCE IS NOT AN IDENTIFIER, AND CR-046 F4 ASKS FOR
    THIS PROVED RATHER THAN ASSUMED.**

    A unit NAMES a premises. That reference points at a record **we numbered**,
    so the file is quoting a number we issued — not inventing one — and it is
    untouched by this change. A lane reading *"the identifier never comes off
    the file"* could easily conclude the premises reference must go too; it
    must not, and the load order (premises → units → meters → accounts) is what
    makes it resolvable.
    """
    with tenant_ctx(brazos):
        premises = make_premises(marcus, address_line="50 Bluestem Ln")
        content = _csv(
            UNITS_HEADERS,
            [
                {
                    "UNIT_NO": "",
                    "PREMISE_ID": premises["premise_no"],
                    "UNIT_REF": "Apt 5",
                    "LEGACY_KEY": "",
                }
            ],
        )
        run_id = _validated(marcus, "units", content, UNITS_MAPPING)
        assert _rejects(run_id) == {}, (
            "the premises reference was refused — a unit quoting a number WE "
            "issued is the load order working, not an invented identifier"
        )
        _commit(dana, run_id, "insert")
        assert str(models.Unit.objects.get(label="Apt 5").premises_id) == str(premises["id"])


def test_cr046_c3__nothing_auto_creates_the_premises_a_unit_names(brazos, marcus, dana):
    """Existing law, asserted because CR-046 says the change must not weaken
    it: a units row naming a premises that is not on file is an ERROR, never an
    auto-create. Inventing the premises half of a utility's estate from a
    spreadsheet is the failure this prevents."""
    content = _csv(
        UNITS_HEADERS,
        [{"UNIT_NO": "", "PREMISE_ID": "P-77777", "UNIT_REF": "Apt 7", "LEGACY_KEY": ""}],
    )
    with tenant_ctx(brazos):
        before = models.Premises.objects.count()
        run_id = _validated(marcus, "units", content, UNITS_MAPPING)
        assert 1 in _rejects(run_id)
        assert models.Premises.objects.count() == before
        assert models.Unit.objects.filter(label="Apt 7").count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# C4 · ACCOUNTS — the ONE upload of six that does NOT call Settings › Numbering
# ═══════════════════════════════════════════════════════════════════════════


def test_cr046_c4__the_account_number_is_the_utilitys_and_is_required(brazos, marcus):
    """⛔⛔ **THE REVERSAL, AND IT IS AN EXCEPTION RATHER THAN AN
    INCONSISTENCY** (PO 2026-08-27): *"we use utility provdied account number
    here - we dont create our own number - since it will create lot of change
    management for utility ; if row dont have account number reject it …  here
    we dont call settings -> account number logic"*.

    **The principle under this ruling and the meter ruling is one principle —
    the side that OWNS the identifier issues it.** A meter number is ours and
    the customer has never seen it. An account number is theirs: it is on every
    bill they kept, in their bank's payee list, on the standing order.
    Renumbering is not a data change, it is a letter to every customer.

    So this asserts the three things that make accounts different, and a lane
    "harmonising" the four targets breaks all three at once:
    """
    with tenant_ctx(brazos):
        columns = {c["target"]: c for c in import_runs.target_columns("accounts")}
    entry = columns["account_no"]

    assert entry["required"] is True, (
        "a row with no account number is REJECTED — there is nothing safe to "
        "invent, because a number we made up is one the customer has never "
        "seen and the utility's own old records cannot match"
    )
    assert entry["sample"] == "A-10432", (
        "this column DOES ship a worked value, unlike the other three — it is "
        "a worked value for the OPERATOR'S OWN numbering"
    )
    assert "blank_means" not in entry, (
        "a `blank_means` here would be a blank-means-allocate path, which is "
        "exactly what the ruling removed"
    )
    assert "never issues one of its own" in entry["help"]
    # …and the rule that enforces it is STRUCTURAL, with its own sentence.
    rule = next(
        r for r in import_rules.PLATFORM_CATALOG["accounts"] if r.code == "ACC.NUMBER_REQUIRED"
    )
    assert rule.severity == import_rules.ERROR
    assert rule.tier == import_rules.TIER_STRUCTURAL
    # ⚠ The rule it replaced said the OPPOSITE and must be gone, not merely
    # unused — a catalogue holding both would answer one question two ways.
    assert not any(
        r.code == "ACC.NUMBER_NOT_ON_FILE" for r in import_rules.PLATFORM_CATALOG["accounts"]
    )


def test_cr046_c4__the_downloaded_accounts_file_carries_a_worked_number(brazos, marcus):
    """⛔ **PROVE THE BYTES, NOT THE COLUMN DEFINITION.** CR-046's own C6 asks
    for the downloaded file to be read; `DEF-962` is what happens when only the
    definition is checked.

    ⚠ **THIS TARGET IS THE OPPOSITE OF THE OTHER THREE AND THAT IS THE
    ASSERTION.** Premises, units and meters ship their identifier cell BLANK,
    because we issue those numbers. Accounts ship a WORKED value, because the
    operator supplies theirs — and a blank cell in a template whose column is
    REQUIRED would be a worked row that can never load.
    """
    with tenant_ctx(brazos):
        _name, body = import_runs.sample_csv("accounts")
        header = [str(c["target"]) for c in import_runs.sample_columns("accounts")]
    _header, example = list(csv.reader(io.StringIO(body)))[:2]
    cells = dict(zip(header, example))
    assert cells["account_no"] == "A-10432", (
        "the accounts template ships a worked account number — the column is "
        f"REQUIRED and a blank one could never load; got {cells['account_no']!r}"
    )
    assert "account_no" in header
    # …and the premises/units files really do ship theirs blank, in the same
    # read, so the divergence is asserted rather than described.
    with tenant_ctx(brazos):
        for target, field in (("premises", "premise_no"), ("units", "unit_no")):
            _n, other = import_runs.sample_csv(target)
            _h, e = list(csv.reader(io.StringIO(other)))[:2]
            h = [str(c["target"]) for c in import_runs.sample_columns(target)]
            assert dict(zip(h, e))[field] == ""


def test_cr046_c4__the_accounts_rehearsal_projects_no_numbers(brazos, marcus):
    """⛔ **A REHEARSAL THAT PRINTED *"we will issue AC-2026-00001 …"* WOULD
    PROMISE A RENUMBERING THE COMMIT WILL NOT PERFORM**, on the one identifier
    the customer actually knows. The three other targets DO project; this one
    is excluded by name."""
    assert import_runs._issued_numbers_preview("accounts", 12) == {}
    # …and the exclusion is not an accident of there being no series: the
    # `account` series exists in SERIES_CATALOG and the other targets' preview
    # is driven from the same map.
    assert "accounts" in import_runs.TARGET_SERIES
    for target in ("premises", "units"):
        assert target in import_runs.TARGET_SERIES


def test_cr046_c4__an_update_never_changes_the_number_it_matched_on(brazos, marcus):
    """The match key must survive the update that matched on it — otherwise the
    NEXT corrected re-run matches nothing and duplicates the whole book.

    ⚠ **AND `IMPORT_UPDATE_FIELDS` EXCLUDES EVERY MONEY FIELD** — hard rule 4:
    the four `ob_*` buckets became journal entries at the first load (GT-16 ❄️)
    and a journal entry is corrected by a NEW entry, never an edited one."""
    from apps.customers import services as customer_services

    updatable = customer_services.IMPORT_UPDATE_FIELDS
    assert "account_no" not in updatable, "a re-run must not rewrite the key it matched on"
    assert "unit_id" not in updatable, "re-homing an account is the move-out/move-in pair"
    for money in ("ob_current", "ob_31_60", "ob_61_90", "ob_90_plus", "deposit_on_file"):
        assert money not in updatable, (
            f"{money} is posted through the ledger at the first load — hard rule 4 "
            "makes a journal entry immutable and a correction a NEW entry"
        )
    # The two lists in two modules must agree, or a column is updatable on one
    # side and refused on the other.
    assert import_runs._IMPORT_UPDATABLE_ACCOUNT_FIELDS == updatable


# ═══════════════════════════════════════════════════════════════════════════
# C5 · external_ref is UNIQUE, which is what makes it a match key
# ═══════════════════════════════════════════════════════════════════════════


def test_cr046_c5__external_ref_is_unique_per_tenant_case_insensitively(brazos, marcus, dana):
    """⛔ **A NON-UNIQUE COLUMN CANNOT IDENTIFY A ROW**, which is the whole
    reason `serial_no` could not take this job on the meters target
    (BR-AST-033). The index is PARTIAL — N rows with no legacy reference must
    coexist — and CASE-INSENSITIVE, because `GIS-118` and `gis-118` are one
    property in every legacy export.
    """
    with tenant_ctx(brazos):
        make_premises(marcus, address_line="60 Bluestem Ln", external_ref="GIS-6006")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.Premises.objects.create(
                    tenant_id=brazos.id,
                    address_line="61 Bluestem Ln",
                    external_ref="gis-6006",
                )
        # PARTIAL: two rows with NO reference are lawful and must stay so.
        with transaction.atomic():
            models.Premises.objects.create(tenant_id=brazos.id, address_line="62 Bluestem Ln")
            models.Premises.objects.create(tenant_id=brazos.id, address_line="63 Bluestem Ln")


def test_cr046_c5__every_target_has_the_column_and_the_index(brazos, marcus, dana):
    """The four targets, one posture. ⚠ **`accounts` IS IN THIS LIST AND CR-046
    SAID IT WOULD NOT BE** — its C4 warning reads *"accounts already have the
    legacy-reference column this change is adding to the others"*. They did
    not: `BR-CUS-054`'s `external_ref` is on **`customers`**, the PERSON, and
    one landlord with fourteen units has ONE of those and FOURTEEN account
    references. That is `DEF-1660`."""
    for model, index_name in (
        (models.Premises, "uq_premises_tenant_external_ref_ci"),
        (models.Unit, "uq_units_tenant_external_ref_ci"),
        (customer_models.Account, "uq_accounts_tenant_external_ref_ci"),
    ):
        assert model._meta.get_field("external_ref") is not None
        assert index_name in {c.name for c in model._meta.constraints}, (
            f"{model.__name__}.external_ref has no unique — it cannot be a match key"
        )


# ═══════════════════════════════════════════════════════════════════════════
# THE RULE CATALOGUE — the mode-dependent half, on every target
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "target,code",
    [
        ("premises", "PRM.PREMISE_NO_ON_FILE"),
        ("units", "UNT.NUMBER_ON_FILE"),
        ("units", "UNT.PAIR_ON_FILE"),
        ("accounts", "ACC.NUMBER_ON_FILE"),
        ("assets_meters", "AST.NUMBER_ON_FILE"),
    ],
)
def test_cr046__the_on_file_rule_takes_the_runs_own_mode(target, code):
    """⛔ **CR-046 C1's MECHANISM, WIDENED TO ALL FOUR TARGETS RATHER THAN
    COPIED FOUR TIMES.** `insert` makes the rule an ERROR that rejects;
    `upsert` leaves it a flag. An unknown or absent mode returns the catalogue
    exactly as declared, which is the pre-CR-046 behaviour and the only safe
    default.

    ⚠ `assets_meters` is in this list on purpose: it is the target the
    mechanism was built for, and a widening that broke it would be a
    regression nothing else here would catch."""
    catalog = import_rules.PLATFORM_CATALOG[target]
    insert = {r.code: r for r in import_rules._for_write_mode(catalog, "insert")}
    upsert = {r.code: r for r in import_rules._for_write_mode(catalog, "upsert")}
    declared = {r.code: r for r in import_rules._for_write_mode(catalog, None)}

    assert insert[code].severity == import_rules.ERROR
    assert insert[code].action == import_rules.REJECT_ROW
    assert upsert[code].severity == import_rules.WARNING
    assert upsert[code].action == import_rules.FLAG_ONLY
    assert declared[code].severity == import_rules.WARNING
    # The sentence says which outcome applies — it no longer withholds it.
    assert "rejected" in insert[code].sentence
    assert "update" in upsert[code].sentence


def test_cr046__a_blank_identifier_fires_neither_predicate(brazos, marcus, dana):
    """⛔ **BLANK IS HOW A NEW RECORD IS SPELLED, SO IT IS NEITHER A MATCH NOR
    AN INVENTION.** A file of 428 new premises carries 428 blank cells; a rule
    that treated them as 427 duplicates of each other, or as 428 invented
    numbers, would reject the whole migration."""
    content = _csv(
        PREMISES_HEADERS,
        [
            {"PREMISE_ID": "", "ADDR1": f"{i} Blank Way", "SVC_AVAIL": "electric", "LEGACY_KEY": ""}
            for i in range(1, 6)
        ],
    )
    with tenant_ctx(brazos):
        run_id = _validated(marcus, "premises", content, PREMISES_MAPPING)
        assert _rejects(run_id) == {}, "blank identifier cells were treated as a problem"
        _commit(dana, run_id, "insert")
        counts = models.ImportRun.objects.get(pk=run_id).counts
        assert counts["created"] == 5
        assert counts["numbers_issued_from_series"] == 5, (
            "every created row takes its number from the series — the count is "
            "recorded so a receipt read a year from now says where they came from"
        )


def test_cr046_d1__the_dry_run_projects_numbers_without_consuming_them(brazos, marcus, dana):
    """⛔ **A REHEARSAL MAY LAWFULLY BE RUN TWICE**, so it must ALLOCATE
    NOTHING. The PO ruled the allocation belongs *"just before updating teh
    record in the database"*; N allocations per rehearsal would burn numbers on
    rows that never load."""
    from apps.tenancy import models as tenancy_models

    content = _csv(
        PREMISES_HEADERS,
        [
            {"PREMISE_ID": "", "ADDR1": f"{i} Peek Way", "SVC_AVAIL": "electric", "LEGACY_KEY": ""}
            for i in range(1, 4)
        ],
    )
    with tenant_ctx(brazos):
        run_id = _validated(marcus, "premises", content, PREMISES_MAPPING)

        def counter():
            return tenancy_models.NumberSeries.objects.get(
                tenant_id=brazos.id, series="premises"
            ).next_number

        before = counter()
        figures = import_runs.dry_run(marcus, run_id, "insert")
        import_runs.dry_run(marcus, run_id, "insert")  # twice, deliberately
        assert counter() == before, (
            f"the rehearsal moved the counter from {before} to {counter()} — a "
            "peek allocates nothing"
        )
        assert figures["will_create"] == 3
        assert figures["will_issue"]["numbers"][0] == "P-00101"
        assert figures["will_issue"]["count"] == 3


def test_cr046__a_rolled_back_load_returns_the_counter(brazos, marcus, dana):
    """⛔ **INSIDE THE WRITE TRANSACTION** — the other half of the ruling's
    *"just before updating teh record in the database"*. A rejected row burns
    no number, and a load that raises returns the counter, because the
    allocation and the write are the same transaction."""
    from apps.tenancy import models as tenancy_models

    content = _csv(
        PREMISES_HEADERS,
        [{"PREMISE_ID": "", "ADDR1": "1 Rollback Way", "SVC_AVAIL": "electric", "LEGACY_KEY": ""}],
    )
    with tenant_ctx(brazos):
        run_id = _validated(marcus, "premises", content, PREMISES_MAPPING)

        def counter():
            return tenancy_models.NumberSeries.objects.get(
                tenant_id=brazos.id, series="premises"
            ).next_number

        before = counter()
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                _commit(dana, run_id, "insert")
                raise RuntimeError("the operator's connection dropped")
        assert counter() == before, (
            f"a rolled-back load left the counter at {counter()} instead of "
            f"{before} — the number was burned on a row that never loaded"
        )
