# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-762 — *"'NOBODY HAS ASKED ABOUT THIS ADDRESS' AND 'THIS ADDRESS
#          OFFERS NOTHING' RENDER IDENTICALLY — THE READ PATH COLLAPSES NULL
#          INTO []"*. `selectors.premises_detail_dict` read
#          `list(row.services_available or [])`, so SQL NULL and `[]` arrived at
#          every client as the same value and three screens printed
#          "No services" for both.
# Change:  CR-036 (h) — *"existing premises hold NULL … NULL is not 'none', it
#          is NEVER ASKED; do not backfill"* (PO, 2026-08-26)
# Story:   US-MET-001 (premises read) · EP-MET-01 S14
# Rules:   BR-MET-003 (`services_available` ⊆ the tenant's ENABLED services)
# ───────────────────────────────────────────────────────
"""The READ half of CR-036 (h). Its write half is pinned next door and is NOT
weakened by any of this: `test_cr036h_premises_services_write.py` still says a
create that never asked leaves NULL, an unrelated edit leaves NULL, and an
explicit `[]` from a clerk is stored. Those three are the reason the information
still EXISTS to be served; these are about serving it.

⚠ **WHY THIS FILE HAS TO EXIST AT ALL, AND WHY NOTHING CAUGHT THE DEFECT.**
Both states are valid, both render, and the collapse happened at a line where a
falsy check reads as ordinary defensive coding (`row.services_available or []`).
There was nothing to go red: every existing test asserted a LIST, and `[]` is a
list. So the assertions below are deliberately about the DIFFERENCE — `is None`
against `== []` — and each was proved red by restoring the `or []` (hard-won law
7). The RED text is recorded in the lifecycle block at the foot of this file.

⚠ **AND THE EXPORT IS ASSERTED TOO, BECAUSE THE CSV CANNOT CARRY IT IN ONE
CELL.** `format_list` writes an empty cell for `None` and for `[]` alike, so a
fix that stopped at the JSON would have left the downloaded file saying exactly
what the screens had stopped saying. `services_recorded` is derived from the one
nullable field at export time — it cannot drift from the cell beside it.
"""

import csv

import pytest

from apps.metering import exports as metering_exports
from apps.metering import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _dict_for(address: str):
    row = models.Premises.objects.get(address_line=address)
    return selectors.premises_detail_dict(row)


def test_def762__a_premises_nobody_was_asked_about_serves_null_not_an_empty_list(brazos, dana):
    """THE DEFECT. The column holds NULL; the serialiser must publish NULL.

    `[]` here is not a smaller lie than a wrong list — it is the answer *this
    address offers nothing*, put into a clerk's mouth by a serialiser.
    """
    with tenant_ctx(brazos):
        services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "21 Quarry Hill Rd"})
        served = _dict_for("21 Quarry Hill Rd")
    assert served["services_available"] is None
    # Stated as its own assertion because `[] is None` is False but `[] == []`
    # is True, and it is the SECOND that the old line satisfied.
    assert served["services_available"] != []


def test_def762__an_explicit_empty_answer_serves_an_empty_list_not_null(brazos, dana):
    """The other direction, and the reason `None` cannot simply be dropped from
    the payload: a clerk who emptied the control ANSWERED, and that answer must
    survive the read exactly as `[]`."""
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana, {"owner_id": owner_for(dana), "address_line": "23 Quarry Hill Rd", "services_available": []}
        )
        assert models.Premises.objects.get(pk=created["id"]).services_available == []
        served = _dict_for("23 Quarry Hill Rd")
    assert served["services_available"] == []
    assert served["services_available"] is not None


def test_def762__the_two_states_are_not_equal_to_each_other_when_served(brazos, dana):
    """One assertion the two tests above cannot make between them: whatever the
    serialiser does, the two rows must not come out the SAME. This is the shape
    the next refactor would have to break on purpose."""
    with tenant_ctx(brazos):
        services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "25 Quarry Hill Rd"})
        services.create_premises(
            dana, {"owner_id": owner_for(dana), "address_line": "27 Quarry Hill Rd", "services_available": []}
        )
        never_asked = _dict_for("25 Quarry Hill Rd")
        answered_none = _dict_for("27 Quarry Hill Rd")
    assert never_asked["services_available"] != answered_none["services_available"]


def test_def762__a_real_list_is_still_a_plain_copied_list(brazos, dana):
    """The ordinary case is unchanged, and the copy is still a copy — a caller
    that mutates the served value must not reach the model's own object."""
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"owner_id": owner_for(dana), "address_line": "29 Quarry Hill Rd", "services_available": ["electric", "water"]},
        )
        served = _dict_for("29 Quarry Hill Rd")
        served["services_available"].append("gas")
        row = models.Premises.objects.get(pk=created["id"])
    assert row.services_available == ["electric", "water"]


def _premises_csv_columns():
    return metering_exports.PREMISES.columns


def test_def762__the_export_carries_the_distinction_the_csv_cell_cannot(brazos, dana):
    """⚠ The CSV writes an EMPTY CELL for both states — `format_list(None)` and
    `format_list([])` are both `""`. So the file gets a second, DERIVED column
    saying whether anybody answered, and the two cells are read together:
    `false` + empty = never asked; `true` + empty = offers nothing.
    """
    with tenant_ctx(brazos):
        services.create_premises(dana, {"owner_id": owner_for(dana), "address_line": "31 Quarry Hill Rd"})
        services.create_premises(
            dana, {"owner_id": owner_for(dana), "address_line": "33 Quarry Hill Rd", "services_available": []}
        )
        services.create_premises(
            dana, {"owner_id": owner_for(dana), "address_line": "35 Quarry Hill Rd", "services_available": ["water"]}
        )
        rows = {
            row.address_line: selectors.premises_detail_dict(row)
            for row in models.Premises.objects.filter(address_line__endswith="Quarry Hill Rd")
        }

    columns = {column.name: column for column in _premises_csv_columns()}
    assert "services_recorded" in columns, "the CSV lost the distinction the API now serves"

    recorded = columns["services_recorded"]
    services_cell = columns["services_available"]

    never_asked = rows["31 Quarry Hill Rd"]
    answered_none = rows["33 Quarry Hill Rd"]
    answered_water = rows["35 Quarry Hill Rd"]

    # The list cell genuinely cannot tell the first two apart …
    assert services_cell.value(never_asked) is None
    assert services_cell.value(answered_none) == []
    # … and the derived column is what does.
    assert recorded.value(never_asked) is False
    assert recorded.value(answered_none) is True
    assert recorded.value(answered_water) is True


def test_def762__the_derived_column_is_derived_and_cannot_drift(brazos, dana):
    """It reads the SAME field it describes, in this one place — there is no
    stored `asked` flag that a later write could leave disagreeing with the
    list. Fabricating a row proves the derivation, not a database state."""
    column = {c.name: c for c in _premises_csv_columns()}["services_recorded"]
    assert column.value({"services_available": None}) is False
    assert column.value({"services_available": []}) is True
    assert column.value({"services_available": ["electric"]}) is True
    # A row that does not carry the key at all is not an answer either.
    assert column.value({}) is False


def test_def762__the_csv_header_names_both_columns_in_order():
    """The header is a contract with every spreadsheet already built on it, so
    the new column's POSITION is pinned beside its name."""
    names = [column.name for column in _premises_csv_columns()]
    assert names == [
        "premise_no",
        "address_line",
        "premises_type_name",
        "units",
        "services_available",
        "services_recorded",
        "owner_manager",
        "status",
    ]
    # `csv` is imported so the reader can see this is about a FILE and not a
    # dict; the writer itself is covered by tests/test_be_list_export.py.
    assert csv.QUOTE_MINIMAL is not None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-762 (12-governance/10-defect-log.csv) + CR-036 (h)
#         (12-governance/11-change-requests.md, verbatim) + BR-MET-003
# screens: S14 (premises list) · PRM-02 (premises detail) · the S14 Download
# generated: 2026-08-26 by lane DEFSWEEP
# RED proof (hard-won law 7), both runs on a `cp -a` copy under
#   scratchpad/defsweep/06-backend — never the shared tree:
#   A · `selectors.py` restored to `list(row.services_available or [])`:
#       3 failed, 4 passed
#       FAILED …::test_def762__a_premises_nobody_was_asked_about_serves_null_not_an_empty_list
#         E   assert [] is None
#       FAILED …::test_def762__the_two_states_are_not_equal_to_each_other_when_served
#         E   assert [] != []
#       FAILED …::test_def762__the_export_carries_the_distinction_the_csv_cell_cannot
#         E   AssertionError: assert [] is None
#         E    +  where [] = ExportColumn(name='services_available', …).value({…'address_line': '31 Quarry Hill Rd'…})
#   B · the fix kept, the derived export column deleted:
#       3 failed, 4 passed
#       FAILED …::test_def762__the_export_carries_the_distinction_the_csv_cell_cannot
#         E   AssertionError: the CSV lost the distinction the API now serves
#         E   assert 'services_recorded' in {…}
#       FAILED …::test_def762__the_derived_column_is_derived_and_cannot_drift
#         E   KeyError: 'services_recorded'
#       FAILED …::test_def762__the_csv_header_names_both_columns_in_order
#         E   At index 5 diff: 'owner_manager' != 'services_recorded'
# gates: pytest tests/test_def762_premises_services_read.py
#        tests/test_be_list_export.py tests/test_cr036h_premises_services_write.py
#        -> 61 passed (exit 0)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
