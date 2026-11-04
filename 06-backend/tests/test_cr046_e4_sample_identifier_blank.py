# ── Trace ──────────────────────────────────────────────
# Change:  CR-046 wave E4 — "All four sample CSVs proved end to end: the blank
#          identifier cell reaches the downloaded file, per target."
# Rules:   CR-046 step 5 shape (1) and (2) — the identifier is issued from the
#          tenant's series and is never taken from the file; the column stays,
#          meaning "an EXISTING number, if this row updates a record already in
#          SMARTBillHub — blank for a new one" · BR-AST-026 (the series
#          allocates ALWAYS on the meters target) · BR-AST-049 / BR-CUS-054
#          (the utility's own reference goes in External reference)
# Screens: WFL-01 stage 1, the `Sample CSV` button
# ───────────────────────────────────────────────────────
"""CR-046 E4 — the DOWNLOADED FILE, not the column definition.

⚠ **THIS TEST EXISTS BECAUSE `DEF-962` SHIPPED AN INVENTED NUMBER INTO EXACTLY
THIS CELL AND EVERY CHECK PASSED OVER IT.** `_asset_column` defaulted `sample`
to `""` and wrote the key unconditionally; `sample_csv`'s `cell()` reads that
key FIRST, so every declared column short-circuited the kind-aware worked
values below it. The column DEFINITION was right and the FILE was wrong, and
nothing in the repo compared the two.

So the assertion here is deliberately made on the parsed BYTES of
`sample_csv`'s second row — the row a person receives — and never on
`FIELD_OVERRIDES_BY_TARGET`. `07-frontend/src/features/metering/
ImportIdentifierTruth.dom.test.tsx` carries the other half: that clicking the
button hands those same bytes to the browser unaltered.

⚠ **`assets_submeters` AND `assets_devices` ARE COVERED TOO, THOUGH CR-046
NAMES FOUR TARGETS.** They share `_asset_number_column` with the meters target,
so a change that broke them would break it — and a template that shipped a
number for a sub-meter while the meter's was blank is precisely the kind of
half-applied ruling this file is here to refuse.
"""
import csv
import io

import pytest

from apps.metering import import_runs
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

#: target -> the column that holds the record's OWN identifier. One entry per
#: target the product offers, so a NEW target with no entry fails the last test
#: in this file rather than quietly escaping the rule.
IDENTIFIER_COLUMN = {
    "premises": "premise_no",
    "units": "unit_no",
    "assets_meters": "asset_no",
    "assets_submeters": "asset_no",
    "assets_devices": "asset_no",
    "accounts": "account_no",
    # ⚠ **PARTS AND PAYMENTS JOINED ON 2026-10-03 (`DEF-MET-9264`)** — `parts`
    # became a target on 2026-09-07 (`ab382ca64`, CR-077) and `payments` on
    # 2026-09-22 (`c8bce7c8a`), neither extended this map, and the last test
    # below was red from the first of those days. Each is placed by WHO OWNS
    # its identifier, the principle `FILE_PROVIDED_IDENTIFIER` already states;
    # see the two sets under it.
    "parts": "part_no",
    "payments": "payment_no",
}

#: ⛔ **THE ONE TARGET THE RULE DOES NOT REACH, AND IT IS A PO REVERSAL RATHER
#: THAN AN EXEMPTION THIS FILE GRANTED ITSELF (added 2026-08-30).**
#:
#: CR-046 C4 was built the way the other five were — blank cell, number issued
#: from Settings → Numbering — and the PO reversed it in the same change,
#: verbatim:
#:
#:   > *"we use utility provdied account number here - we dont create our own
#:   > number - since it will create lot of change management for utility ; if
#:   > row dont have account number reject it - please update the logic; here we
#:   > dont call settings -> account number logic"*
#:
#: So on `accounts` the identifier is **required, taken from the file verbatim,
#: and a blank cell is an ERROR** — the exact opposite of the other five. The
#: principle under both rulings is the same one and the code says so: the side
#: that OWNS the identifier issues it. A meter number is ours and the customer
#: has never seen it; an account number is on every bill they kept and in their
#: bank's payee list, so renumbering is a letter to every customer.
#:
#: ⚠ **THE TARGET IS KEPT IN `IDENTIFIER_COLUMN` AND ONLY ITS VERDICT INVERTS.**
#: Deleting the row would take it out of
#: `test_every_offered_target_is_covered_by_this_file` as well, and a target
#: that escapes the rule by not being mentioned is precisely what that test
#: exists to stop. The assertions below therefore RUN on `accounts` — they just
#: assert the opposite outcome, so the day somebody re-applies CR-046 to
#: accounts by mistake this file goes red again.
FILE_PROVIDED_IDENTIFIER: frozenset[str] = frozenset({"accounts", "parts"})
#: ⚠ **`parts` IS THE ACCOUNTS CASE BY CONSTRUCTION, NOT BY A RULING OF ITS
#: OWN.** There is no part-number series — `Work-025` has never issued one — so
#: the part number is the utility's, comes off the file, is required, and is the
#: upsert match key (`import_runs.PARTS_COLUMNS`). Same verdicts as `accounts`,
#: asserted the same way.

#: ⛔ **THE THIRD SHAPE: THE IDENTIFIER IS OURS AND THE FILE IS NEVER OFFERED IT
#: AT ALL (`payments`, `DEF-MET-9264`).** A payment's `payment_no` is issued from
#: the `PMT-` series inside `payments.services.record_payment`, and the target is
#: INSERT-ONLY (hard rule 4, `_refuse_payments_write_mode`), so there is no
#: update for the column to be a match key for — nothing for CR-046's *"keep the
#: column, change its meaning"* to preserve. The cheque number in `reference` is
#: the INSTRUMENT's, not the payment's. So the assertions RUN on `payments` and
#: assert the column ABSENT, from the downloaded bytes and from stage 2, which is
#: what goes red the day `payment_no` joins the template and invites a number we
#: would overwrite.
ISSUED_NOT_OFFERED: frozenset[str] = frozenset({"payments"})


def _downloaded(target: str) -> tuple[str, dict[str, str]]:
    """The file as a person receives it, keyed by FIELD.

    ⚠ The header a person reads is the column's LABEL since 2026-08-28
    (`DEF-1077`) — `Meter number (existing only)`, not `asset_no` — so the
    field order comes from `import_runs.sample_columns`, which is the same list
    `sample_csv` writes. Deriving it separately is `DEF-616`'s mechanism.
    """
    filename, body = import_runs.sample_csv(target)
    rows = list(csv.reader(io.StringIO(body)))
    assert len(rows) == 2, f"{target}: header row plus ONE example row, nothing else"
    fields = [str(column["target"]) for column in import_runs.sample_columns(target)]
    return filename, dict(zip(fields, rows[1]))


@pytest.mark.parametrize("target", sorted(IDENTIFIER_COLUMN))
def test_the_downloaded_sample_leaves_the_identifier_cell_blank(brazos, target):
    """CR-046 (1)+(2): blank is the normal case, on every target."""
    column = IDENTIFIER_COLUMN[target]
    with tenant_ctx(brazos):
        filename, cells = _downloaded(target)

    assert filename == f"{target}_sample.csv"
    if target in ISSUED_NOT_OFFERED:
        assert cells, f"{target}: the downloaded sample carries no columns at all"
        assert column not in cells, (
            f"{target}: the downloaded sample carries {column!r}. That number is "
            f"issued by SMARTBillHub inside the write and the target is "
            f"insert-only, so a column for it invites a value nothing reads."
        )
        return
    # The column SURVIVES — it is the match key for Insert & update, and
    # deleting it would take that with it (CR-046 step 2's addendum).
    assert column in cells, (
        f"{target}: the identifier column {column!r} is not in the downloaded "
        f"header at all. CR-046 keeps the column and changes its MEANING; "
        f"removing it takes the Insert & update match key with it."
    )
    if target in FILE_PROVIDED_IDENTIFIER:
        # The PO's 2026-08-27 reversal, asserted rather than skipped: this
        # target's sample MUST ship a worked number, because the operator has
        # to supply one and a blank example would teach the opposite.
        assert cells[column] != "", (
            f"{target}: the sample ships an EMPTY {column!r}. The PO reversed "
            f"CR-046 for this target on 2026-08-27 — the utility's own number "
            f"is required and a blank row is rejected — so an empty worked cell "
            f"teaches an operator to build a file every row of which errors."
        )
        return
    # ⛔ THE ASSERTION DEF-962 NEEDED, on the bytes rather than the definition.
    assert cells[column] == "", (
        f"{target}: the downloadable sample ships {cells[column]!r} in "
        f"{column!r}. Under CR-046 the number is issued from the tenant's "
        f"series INSIDE the write transaction and is never read off the file, "
        f"so a sample that fills this cell teaches every operator to supply "
        f"one — and DEF-962 is what that costs."
    )


@pytest.mark.parametrize("target", sorted(IDENTIFIER_COLUMN))
def test_the_identifier_column_says_what_it_now_means(brazos, target):
    """CR-046 E2's server half: the header and the help the screen renders.

    The wizard draws whatever a column DECLARES (see `helpColumns` in
    `ImportWorkflowPage.tsx`), so this asserts the declaration exists and says
    the two things an operator must act on: leave it blank, and where the
    number actually comes from.
    """
    column = IDENTIFIER_COLUMN[target]
    with tenant_ctx(brazos):
        offered = import_runs.target_columns(target)
    entry = next((c for c in offered if c["target"] == column), None)
    if target in ISSUED_NOT_OFFERED:
        assert offered, f"{target}: stage 2 offers no columns at all"
        assert entry is None, (
            f"{target}: {column!r} is offered at stage 2. It is issued from the "
            f"tenant's series and the target is insert-only, so a mapped value "
            f"has nothing to do but be overwritten."
        )
        # The insert-only half of the reason, asserted rather than cited.
        with pytest.raises(errors.BizError):
            import_runs._refuse_payments_write_mode("upsert", target=target)
        return
    assert entry is not None, f"{target}: {column!r} is not offered at stage 2"

    help_text = str(entry.get("help") or "")
    assert help_text != "", (
        f"{target}: {column!r} changed meaning on 2026-08-27 and declares no "
        f"help. The stage-2 screen renders any column that declares one, so "
        f"the sentence is the only thing between the operator and a file built "
        f"the old way."
    )
    lowered = help_text.lower()
    if target in FILE_PROVIDED_IDENTIFIER:
        # The two things an operator must act on here are the MIRROR IMAGE of
        # the other five, so they are asserted rather than waived: the number is
        # theirs, and an empty cell is rejected.
        assert "your" in lowered, (
            f"{target}: {column!r}'s help never says the number is the "
            f"UTILITY'S OWN. Got: {help_text!r}"
        )
        assert "empty" in lowered or "reject" in lowered, (
            f"{target}: {column!r}'s help never tells the operator that a blank "
            f"cell is rejected — which is the whole of the PO's 2026-08-27 "
            f"reversal. Got: {help_text!r}"
        )
        return
    assert "blank" in lowered or "leave" in lowered, (
        f"{target}: {column!r}'s help never tells the operator to leave it "
        f"blank — which is the whole ruling. Got: {help_text!r}"
    )
    assert "numbering" in lowered, (
        f"{target}: {column!r}'s help never says WHERE the number comes from. "
        f"An operator told only 'leave it blank' has no way to check what "
        f"they will get. Got: {help_text!r}"
    )


def test_every_offered_target_is_covered_by_this_file(brazos):
    """A new import target must not escape the identifier rule by being new.

    `TARGETS` is the product's own list; this file's map is the rule's list.
    They are compared rather than assumed, because the failure mode CR-046 was
    written for — a template that invites a number the system will overwrite —
    is invisible until a utility has already built a file from it.
    """
    assert set(import_runs.TARGETS) == set(IDENTIFIER_COLUMN), (
        "A target has been added or renamed and the CR-046 identifier rule was "
        "not extended to it. Add it to IDENTIFIER_COLUMN with the column that "
        "holds its own identifier."
    )
