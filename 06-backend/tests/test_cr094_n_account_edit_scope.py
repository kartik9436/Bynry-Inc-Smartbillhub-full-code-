# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave N — `ACC-S1` + `ACC-S15` (`BR-CUS-1053`):
#           an account's details are corrected from the account, and every
#           group on the Overview carries its own edit control.
#           Drawing: `05-prototype/02 Accounts Menu Blueprint.pdf` R5, pages
#           175–183, pinned at commit `033981d4f` (blob
#           `3f4d75fb74c8a0dc483692c8c21e341215c562d7`).
# Rules:    BR-CUS-1053 (the wave) · BR-CUS-017 (`unit_id` is create-only) ·
#           BR-CUS-030 (closing is the move-out flow) · BR-CUS-058 · BR-CUS-064
#           (`preferred_language` against tenancy's BR-TEN-042 set) ·
#           BR-SHL-025 (a control that cannot act is disabled WITH its reason) ·
#           hard rule 7 (every money action writes `audit_log`).
# Defect:   `DEF-CUS-5127` — `unit` and `account_type` come back
#           `unknown_field` instead of naming their rule. FIXED 2026-09-13
#           by the `BR-CUS-1047` lane; TC-5 is FLIPPED, not deleted.
# ───────────────────────────────────────────────────────
"""What `PATCH /accounts/{id}` actually accepts, refuses and writes.

**THIS FILE EXISTS BECAUSE THE RULE THAT COMMISSIONED THE WAVE GOT THE SCOPE
WRONG, IN BOTH DIRECTIONS, AND NOTHING WOULD HAVE CAUGHT IT.** `BR-CUS-1053`
and the decision-log entry of 2026-09-13 both say the door takes **seven**
fields and refuses **eleven** by name. Measured against the code on the day
the wave started:

* `PATCH_FIELDS` holds **ELEVEN** names, not seven. The three the rule omits
  are `tax_exempt_ref`, `tax_exempt_expires` and `preferred_language` — and
  all three are fields `R5`'s own dialog DRAWS, so a lane that believed the
  rule would have shipped a form with no exemption certificate number, no
  expiry and no language, and every test would have passed.
* `REFUSED_FIELDS` held **THIRTY-FOUR** entries when this was written, not
  eleven — **THIRTY-SIX since 2026-09-13**, when `unit` and `account_type`
  joined it and `DEF-CUS-5127` closed. The eleven the
  rule names are the *columns owned elsewhere*; the other twenty-three are
  proposed-schema columns and other doors' vocabulary.

A prose scope is a claim about code that nothing re-checks (`CLAUDE.md`
hard-won law 1, and the module-segment caveat's own lesson: *where a rule
restates what a tool does, name the tool and let a reader run it*). **TC-6 is
that tool**: it asserts the two set SIZES, so the next time either moves, the
rule and this docstring go red together instead of rotting.
"""

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

pytestmark = pytest.mark.django_db


#: The eight fields `R5`'s *Edit the account* dialog (`ACC-E02`, page 177)
#: draws as typed inputs, in the drawing's own order and grouping:
#: *What kind of account this is* → *Tax* → *Delivery and contact preferences*.
#:
#: ⚠ **THIS IS THE DRAWING'S EIGHT, NOT `PATCH_FIELDS`' ELEVEN, AND THE THREE
#: IT LEAVES OUT ARE LEFT OUT ON PURPOSE** — each is writable on the server and
#: deliberately not offered here:
#:   · `status`   — the drawing itself refuses it, on the form, in its own
#:                  words: *"closing an account is the move-out flow, not an
#:                  edit"*. B14 rule 38 leaves what a form CONTAINS to the
#:                  drawing, and a status select on a correction form is a
#:                  second door onto `BR-CUS-030`'s flow.
#:   · `opened_at`— drawn nowhere in `R5`. Backdating when service began moves
#:                  what a bill run will pick up; it is not a typo fix.
#:   · `custom_data` — the tenant's own fields. `CustomFieldsView` renders them
#:                  READ-ONLY on this Overview already, in another panel; an
#:                  input for them belongs to the group that displays them.
#: All three are recorded in the decision log of 2026-09-13 rather than
#: dropped in silence.
FORM_FIELDS: frozenset[str] = frozenset(
    {
        "account_subtype",
        "tax_exempt",
        "tax_exempt_ref",
        "tax_exempt_expires",
        "preferred_language",
        "paperless",
        "sms_reminders",
        "autopay",
    }
)

#: The eleven `BR-CUS-1053` names — columns that exist and are owned by another
#: path. Each must come back with the id of the rule that owns it, because that
#: sentence is what the screen shows a clerk (`BR-SHL-025`).
COLUMN_REFUSALS: dict[str, str] = {
    "account_no": "BR-TEN-035",
    "balance": "BR-CUS-015",
    "credit_tier": "BR-CUS-058",
    "currency": "BR-TEN-021",
    "deposit_on_file": "BR-CUS-023",
    "deposit_received_on": "BR-CUS-050",
    "bad_address": "BR-PAY-018",
    "nsf_count": "BR-PAY-013",
    "closed_at": "BR-CUS-030",
    "kind": "BR-CUS-068",
    # ⚠ TWO RULES SINCE 2026-09-13, NOT ONE. `BR-CUS-1047` NARROWS
    # `BR-CUS-017`: the unit is still not editable HERE, and there is now a
    # door where it IS correctable, so the refusal cites both and points at it.
    "unit_id": "BR-CUS-017 · BR-CUS-1047",
}


#: ⚠ **`DEF-CUS-5127` IS SEVEN COLUMNS WIDE, NOT TWO — MEASURED BY `TC-6b`
#: BELOW ON 2026-09-13, AND THE OTHER FIVE HAD NEVER BEEN LOOKED AT.**
#:
#: `BR-CUS-1053` names `unit` and `account_type`. Walking every concrete column
#: of `accounts` through the door found five more that come back
#: `customers.account.unknown_field` — a real column told a caller it does not
#: exist. Each needs a `REFUSED_FIELDS` entry naming the rule that owns it, or
#: a place in `PATCH_FIELDS`; deciding which is a ruling and not this wave's.
#:
#:   · `external_ref`        — ⚠ **THE ONE WITH A CLERK-FACING COST.** The
#:                             utility's own legacy account id (`BR-CUS-172`,
#:                             CR-046 C4/C5). `_validate_account` HAS a branch
#:                             cleaning it, and `CREATE_FIELDS` and the import
#:                             accept it — but it is not in `PATCH_FIELDS`, so
#:                             a number typed wrong at cutover can never be
#:                             corrected from anywhere. `DEF-CUS-5141`. (First allocated `DEF-CUS-5130`; that register
#:                             line was lost to a sibling's whole-file write
#:                             before it reached the branch — law 11,
#:                             mechanism two — so the row was re-filed.)
#:   · `cash_only_no_autopay`
#:   · `final_read_state`
#:   · `is_sample`
#:   · `premises_id`
#:
#: **PINNED rather than fixed**, so this set can only shrink deliberately: it
#: goes red when one is ruled on AND when a new column arrives with no ruling
#: at all, which is the hole that let all seven through.
#: ⚠ **SEVEN BECAME FIVE ON 2026-09-13, AND THE TWO THAT LEFT DID SO FOR
#: DIFFERENT REASONS** — which is the distinction this set exists to hold.
#: `unit` left because a RULE was built (`BR-CUS-1047`); `account_type` left
#: because the refusal now NAMES the open question instead of claiming the
#: column does not exist. **A column leaves this set when it is answered, never
#: when it is merely tidied.**
UNRULED_COLUMNS: frozenset[str] = frozenset(
    {
        "premises_id",
        "external_ref",
        "cash_only_no_autopay",
        "final_read_state",
        "is_sample",
    }
)


def _account(brazos, marcus):
    unit = _unit_with_plan(marcus, brazos)
    return customers_services.create_account(marcus, _create_payload(unit["id"]))


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · every key the form sends is WRITTEN — asserted key by key
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_n_tc1__every_field_the_form_sends_comes_back_changed(brazos, marcus):
    """**THE ONE FAILURE THIS WAVE IS MOST EXPOSED TO IS A CONTROL THAT WRITES
    NOTHING** — a form that validates, submits and toasts while dropping a
    field passes every other kind of test (`DEF-MET-4971`, and `DEF-1661`
    inside this very module, where five columns were declared lawful and
    dropped on the floor). So this asserts the read-back VALUE of all eight,
    one at a time, and never merely that the call returned."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        out = customers_services.update_account(
            marcus,
            created["id"],
            {
                "account_subtype": "small_commercial",
                "tax_exempt": True,
                "tax_exempt_ref": "TX-9921",
                "tax_exempt_expires": "2027-01-31",
                "preferred_language": "es",
                "paperless": True,
                "sms_reminders": True,
                "autopay": True,
            },
        )

    assert out["account_subtype"] == "small_commercial"
    # The LABEL rides beside the code: `account_subtypes` is tenant-defined
    # (BR-CUS-067), so the screen never invents one (`DEF-CUS-5000`).
    assert out["account_subtype_name"] == "Small commercial"
    assert out["tax_exempt"] is True
    assert out["tax_exempt_ref"] == "TX-9921"
    assert out["tax_exempt_expires"] == "2027-01-31"
    assert out["preferred_language"] == "es"
    assert out["paperless"] is True
    assert out["sms_reminders"] is True
    assert out["autopay"] is True


def test_cr094_n_tc1b__every_form_field_is_in_the_servers_own_vocabulary(brazos, marcus):
    """The form's eight are a SUBSET of `PATCH_FIELDS`, checked against the
    server's own set rather than against a list retyped here. A field added to
    the dialog that the door does not accept would be refused at runtime and
    green in every unit test — this is the cheap guard against that."""
    assert FORM_FIELDS <= customers_services.PATCH_FIELDS


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · hard rule 7 — the edit writes `audit_log`, before AND after
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_n_tc2__the_edit_writes_one_audit_row_carrying_before_and_after(
    brazos, marcus, audit_rows
):
    """Hard rule 7. `update_account` audits `before=` and `after=` snapshots,
    and the wave's brief asked this be checked against what the form SENDS —
    not merely that some row appeared."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        audit_rows.clear()
        customers_services.update_account(
            marcus, created["id"], {"tax_exempt": True, "tax_exempt_ref": "TX-9921"}
        )

    assert "account.updated" in audit_actions(audit_rows)
    row = next(r for r in audit_rows if r.get("action") == "account.updated")
    before, after = row["before"], row["after"]
    assert before["tax_exempt"] is False and after["tax_exempt"] is True
    assert before["tax_exempt_ref"] in (None, "") and after["tax_exempt_ref"] == "TX-9921"


def test_cr094_n_tc2b__a_patch_that_changes_nothing_writes_no_audit_row(brazos, marcus, audit_rows):
    """`update_account` builds `fields` by COMPARING, and only saves and audits
    when something moved. Worth pinning: a dialog whose Save is pressed with no
    edit must not manufacture an audit row that reads as a correction."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        audit_rows.clear()
        customers_services.update_account(
            marcus, created["id"], {"tax_exempt": created["tax_exempt"]}
        )

    assert "account.updated" not in audit_actions(audit_rows)


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · every refusal the screen shows NAMES ITS RULE (BR-SHL-025)
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(("field", "br_ref"), sorted(COLUMN_REFUSALS.items()))
def test_cr094_n_tc3__a_refused_column_comes_back_with_the_rule_that_owns_it(
    brazos, marcus, field, br_ref
):
    """**A REFUSAL IS SHOWN TO A CLERK, SO IT HAS TO SAY WHY.** `BR-SHL-025`:
    a control that cannot act is disabled WITH its reason, never hidden — and
    the reason the screen prints for these eleven is the server's own, read off
    `REFUSED_FIELDS` rather than retyped into a catalogue where it would drift
    away from the rule it cites."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.update_account(marcus, created["id"], {field: "anything"})

    error = excinfo.value.field_errors[0]
    assert error["field"] == field
    assert error["message_key"] == "customers.account.field_not_writable"
    assert error["params"]["br_ref"] == br_ref
    assert error["params"]["reason"]


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · the two the drawing refuses ON THE FORM are refused BY THE SERVER too
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_n_tc4__status_is_writable_here_and_the_form_still_does_not_offer_it(brazos, marcus):
    """⚠ **THE ONE PLACE THE DRAWING IS STRICTER THAN THE SERVER, AND THE
    DRAWING WINS.** `status` IS in `PATCH_FIELDS` and this PATCH really does
    move it — so nothing stops a future form offering it, and the reason it is
    not offered is a decision rather than a limit. `R5` states it on the form:
    *"Status — closing an account is the move-out flow, not an edit"*
    (`BR-CUS-030`). This test holds both halves at once, so the day somebody
    adds a status select they have to come here and change a sentence that
    explains why they should not."""
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        out = customers_services.update_account(marcus, created["id"], {"status": "active"})

    assert out["status"] == "active"  # the server allows it …
    assert "status" not in FORM_FIELDS  # … and the dialog does not offer it


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · DEF-CUS-5127 — FIXED 2026-09-13; this is the flip it asked for
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("field", ["unit", "account_type"])
def test_cr094_n_tc5__def_cus_5127_unit_and_account_type_refuse_by_name(brazos, marcus, field):
    """⚠ **THIS CASE PINNED A DEFECT AND THE DEFECT IS NOW FIXED, SO IT HAS
    BEEN FLIPPED RATHER THAN DELETED — which is what its own note asked for:**
    *"When `DEF-CUS-5127` is fixed this flips to `field_not_writable` with a
    `br_ref`, and THIS LINE IS THE ONE THAT SHOULD FAIL — it is how the register
    row and the code stay in step."* It failed, and here is the step.

    **What was wrong, restated so the history survives the flip:**

    `BR-CUS-1053` and the decision log of 2026-09-13 both say these two are
    *"skipped SILENTLY"* — that `update_account` does
    `if field in ("unit", "account_type"): continue`, so a form offering either
    gets a SUCCESS and changes nothing. **Measured, that is not what happens.**

    Both are refused at the door with `VAL-002`, because `_reject_unknown`
    checks the payload against `PATCH_FIELDS` before anything else and neither
    name is in it. The `continue` one function later is **DEAD CODE on this
    path**: `_validate_account` populates `unit` and `account_type` only under
    `if not partial:`, and `update_account` always passes `partial=True`.

    **The reason given.** `_reject_unknown`'s own docstring promises *"a field
    that names a real column or a real rule gets that rule back, so the caller
    learns WHY rather than being told the field does not exist"* — and both are
    real columns on `accounts`. A clerk correcting a miscategorised account was
    told the field does not exist.

    **What each one answers now**, and the two are not the same kind of answer:

      * **`unit` / `unit_id`** → `BR-CUS-017 · BR-CUS-1047`, and the reason
        POINTS AT `POST /accounts/{id}/correct-unit`. An edit is still the wrong
        door; the old wording said re-homing is the move-out → move-in pair full
        stop, which stopped being the whole truth when `BR-CUS-1047` was ruled.
      * **`account_type`** → `BR-CUS-012 · OQ-CUS-12356`, and it says plainly
        that **no rule states how a category may be changed**. Inventing a rule
        id to make that entry read like its neighbours would be a refusal citing
        a guarantee nobody signed (hard-won law 1), so the question is named
        instead and the refusal stands meanwhile.
    """
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.update_account(marcus, created["id"], {field: "anything"})

    error = excinfo.value.field_errors[0]
    assert error["field"] == field
    assert error["message_key"] == "customers.account.field_not_writable"
    assert error["params"]["reason"]
    expected = {
        "unit": "BR-CUS-017 · BR-CUS-1047",
        "account_type": "BR-CUS-012 · OQ-CUS-12356",
    }[field]
    assert error["params"]["br_ref"] == expected
    if field == "unit":
        # The refusal must say where to GO, not only that this is the wrong
        # door — a dead end and a redirection read the same to a gate and
        # completely differently to a clerk.
        assert "correct-unit" in error["params"]["reason"]


def test_cr094_n_tc5b__the_dead_branch_is_still_in_update_account(brazos, marcus):
    """The other half of `DEF-CUS-5127`: the branch that reads as the handling
    for those two names is present and unreachable. Asserted on the SOURCE, so
    the row cannot be closed by deleting the test that describes it."""
    import inspect

    source = inspect.getsource(customers_services.update_account)
    assert 'if field in ("unit", "account_type")' in source
    assert "partial=True" in source


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · the two set sizes BR-CUS-1053 states in prose
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_n_tc6__the_scope_figures_quoted_in_prose_are_checked_here(brazos, marcus):
    """⚠ **THE RULE'S PROSE WAS WRONG IN BOTH DIRECTIONS AND NOTHING NOTICED.**
    `BR-CUS-1053` said *seven* writable and *eleven* refused; the code holds
    **eleven** and **thirty-four** (thirty-six since 2026-09-13). Both figures
    are amended in the rule, dated,
    and pinned here — because the failure was not the arithmetic, it was that a
    figure lived only in prose. The eleven the rule lists by name are still a
    real subset and `COLUMN_REFUSALS` above is it."""
    # 11 -> 12 on 2026-10-06: `po_number` joined (`DEF-CUS-9820`, PO ruling D4
    # (a) — *"an editable "PO on bills" field"*). BR-CUS-1053 amended, dated.
    assert len(customers_services.PATCH_FIELDS) == 12
    # 34 -> 36 on 2026-09-13: `unit` and `account_type` joined the map when
    # `DEF-CUS-5127` was fixed. The figure is checked rather than described,
    # which is the whole reason this case exists.
    assert len(customers_services.REFUSED_FIELDS) == 36
    assert set(COLUMN_REFUSALS) <= set(customers_services.REFUSED_FIELDS)
    # Every field the form offers is writable, and none of them is also refused.
    assert not (FORM_FIELDS & set(customers_services.REFUSED_FIELDS))


def test_cr094_n_tc6b__every_concrete_account_column_is_writable_or_named(brazos, marcus):
    """**`DEF-CUS-5127`'s PREVENTION, generalised.** Walk every concrete column
    of the `accounts` model and ask the door about it: each must come back
    EITHER writable OR refused with a `br_ref`. The set that comes back
    `unknown_field` is pinned, and `account_type` is the whole of it today.

    This is the check whose absence let the defect through, and it goes red two
    ways: when the defect is fixed, and when a NEW column is added to `accounts`
    with no ruling about who may write it."""
    # ⚠ `f.name`, NEVER `f.attname`. The door speaks in PAYLOAD KEYS and a
    # relation's payload key is `account_type`, not `account_type_id` — a first
    # draft of this test asked about the attnames and reported three refusals
    # that were its own spelling rather than the server's.
    concrete = {f.name for f in customers_models.Account._meta.concrete_fields}
    ignore = {"id", "tenant", "created_at", "updated_at", "created_by", "updated_by"}
    unknown: set[str] = set()
    with tenant_ctx(brazos):
        created = _account(brazos, marcus)
        for field in sorted(concrete - ignore):
            if field in customers_services.PATCH_FIELDS:
                continue
            try:
                customers_services.update_account(marcus, created["id"], {field: "anything"})
            except errors.ValidationError as exc:
                first = exc.field_errors[0]
                if first.get("message_key") == "customers.account.unknown_field":
                    unknown.add(field)

    assert unknown == UNRULED_COLUMNS, (
        f"columns refused with no rule: {sorted(unknown)} — each needs a "
        "REFUSED_FIELDS entry naming the rule that owns it (DEF-CUS-5127)"
    )
