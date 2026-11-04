# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (S14 premises detail) · US-MET-002 (S15 unit detail)
#           Change: CR-089 wave D — D1 (`PUJ-21`) and D2 (`PUJ-48`)
# Rules:    BR-MET-1164 (a premises cannot be deactivated while any unit on it
#           is active, any asset is still attached, or any account on it is
#           open; a unit is blocked by an open account, and the refusal NAMES
#           what is blocking) · BR-MET-047 (the money term, unchanged) ·
#           BR-MET-035 (a status change is the System Admin's) ·
#           BR-MET-048 (every change writes its audit row)
# Note:     ⚠ **PROVED RED FIRST.** With `_refuse_if_held` deleted from
#           `services.change_premises_status`, case 2 fails with
#           `Failed: DID NOT RAISE <class 'core.errors.BizError'>` and case 5
#           fails on `held_by` being None. Quoted in the report of 2026-09-08.
# ───────────────────────────────────────────────────────
"""BR-MET-1164 — taking a property or a unit out of service, and putting it back.

WHAT IS REAL HERE AND WHAT IS STUBBED, SAID PLAINLY
---------------------------------------------------
The ACTIVE-UNIT term is metering's own table, so it is exercised for real: a
premises with a live unit is refused, the unit is deactivated, and the premises
then goes. The ACCOUNT and ASSET terms cross a module boundary and are read
through `apps.metering.seams`, which is the contract; those cases stub the seam
by name, exactly as `test_us_met_001_002_lists.py` does, so this file tests the
RULE rather than re-testing customers' and assets' own selectors.

⚠ The one thing a stub must not do here is make the rule look enforced when it
is not — so the two seam-stubbed cases assert the refusal's `held_by` and its
`message_key`, both of which come from the rule and neither of which a stub
supplies.
"""

import pytest

from apps.metering import api, models, seams, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    FakeUser,
    api_call,
    audit_actions,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

TODAY = "2026-09-08"


def _change(actor, premises_id, status, **overrides):
    payload = {"status": status, "effective_date": TODAY, "reason": "Building demolished"}
    payload.update(overrides)
    return services.change_premises_status(actor, premises_id, payload)


def _change_unit(actor, unit_id, status, **overrides):
    payload = {"status": status, "effective_date": TODAY, "reason": "Flat knocked through"}
    payload.update(overrides)
    return services.change_unit_status(actor, unit_id, payload)


# ══════════════════════════════════════════════════════════════════════════
# D1 — a property can be taken out of service
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__the_preview_counts_every_term_the_rule_names(brazos, dana):
    """The dialog draws four counts, and a ZERO is drawn as well as a number.

    *"no open accounts"* and *"nobody looked"* are different claims (DEF-127),
    so the preview serves every term the rule names whatever its count is.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        make_unit(dana, premises["id"], label="Unit A")
        make_unit(dana, premises["id"], label="Unit B")
        view = selectors.premises_status_change(premises["id"])

    kinds = {row["kind"]: row for row in view["dependencies"]}
    assert set(kinds) == {"open_accounts", "unpaid_balances", "attached_assets", "active_units"}
    assert kinds["active_units"]["count"] == 2
    assert kinds["open_accounts"]["count"] == 0
    # Every count carries the list that clears it — a number a clerk cannot act
    # on is a wall (CR-089 §6 D1).
    assert kinds["active_units"]["link"] == {
        "route": "premises_units",
        "premises_id": premises["id"],
    }
    assert view["blocked"] is True and view["held_by"] == "active_units"
    assert view["target_status"] == "inactive"


def test_tc2__an_active_unit_refuses_the_deactivation_by_name(brazos, dana):
    """BR-MET-1164's first term, end to end and with no stub in sight."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], label="Unit A")
        with pytest.raises(errors.BizError) as excinfo:
            _change(dana, premises["id"], "inactive")

    assert excinfo.value.br_ref == "BR-MET-1164"
    assert excinfo.value.message_key == "metering.premises.status.holdUnits"
    assert excinfo.value.params["held_by"] == "active_units"
    assert excinfo.value.params["counts"]["active_units"] == 1
    # The premises did NOT move.
    with tenant_ctx(brazos):
        assert models.Premises.objects.get(pk=premises["id"]).status == "active"
        # …and the unit is what clears it.
        _change_unit(dana, unit["id"], "inactive")
        after = _change(dana, premises["id"], "inactive")
    assert after["status"] == "inactive"


def test_tc3__the_open_account_holds_first_and_says_so(brazos, dana, monkeypatch):
    """Three counts at once, and the refusal names the FIRST thing to do.

    CR-089 §6 D1: *"the refusal shows 4 active units · 9 attached assets · 3
    open accounts, each linked, and holds on Close the accounts first"*. All
    three are drawn; the hold is the account, because an account is closed
    before its unit can go.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        units = [make_unit(dana, premises["id"], label=f"Unit {n}") for n in "ABCD"]
        monkeypatch.setattr(
            seams,
            "accounts_for_units",
            lambda ids: {str(u["id"]): {"account_no": "AC-1"} for u in units[:3]},
        )
        monkeypatch.setattr(
            seams,
            "asset_counts_for_units",
            lambda ids: {str(units[0]["id"]): 5, str(units[1]["id"]): 4},
        )
        view = selectors.premises_status_change(premises["id"])
        with pytest.raises(errors.BizError) as excinfo:
            _change(dana, premises["id"], "inactive")

    counts = {row["kind"]: row["count"] for row in view["dependencies"]}
    assert counts["active_units"] == 4
    assert counts["attached_assets"] == 9
    assert counts["open_accounts"] == 3
    assert excinfo.value.message_key == "metering.premises.status.holdAccounts"
    assert excinfo.value.params["held_by"] == "open_accounts"


def test_tc4__a_clear_property_goes_and_the_audit_row_holds_both_answers(
    brazos, dana, audit_rows
):
    """The date and the reason live in `audit_log` and in NO column."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        audit_rows.clear()
        result = _change(dana, premises["id"], "inactive", reason="Demolished 4 Sep")

    assert result["status"] == "inactive"
    assert "premises.deactivated" in audit_actions(audit_rows)
    row = [r for r in audit_rows if r["action"] == "premises.deactivated"][-1]
    assert row["before"] == {"status": "active"}
    assert row["after"]["effective_date"] == TODAY
    assert row["after"]["reason"] == "Demolished 4 Sep"


def test_tc5__reactivation_is_held_by_nothing_and_writes_its_own_row(
    brazos, dana, audit_rows
):
    """CR-089 §8 names this as the one half the rollback must keep.

    Every dependency the rule names is a reason not to STOP serving an address;
    none of them is a reason not to start again.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        _change(dana, premises["id"], "inactive")
        # A live unit would refuse a deactivation; it must not refuse this.
        models.Unit.objects.filter(premises_id=premises["id"]).delete()
        make_unit(dana, premises["id"], label="Unit A")
        view = selectors.premises_status_change(premises["id"])
        audit_rows.clear()
        result = _change(dana, premises["id"], "active", reason="Rebuilt")

    assert view["target_status"] == "active"
    assert view["blocked"] is False and view["held_by"] is None
    assert result["status"] == "active"
    assert "premises.reactivated" in audit_actions(audit_rows)


@pytest.mark.parametrize(
    "overrides,field,message_key",
    [
        ({"reason": ""}, "reason", "metering.premises.status_reason_required"),
        ({"effective_date": ""}, "effective_date", "metering.premises.status_date_required"),
        ({"effective_date": "4 Sep 2026"}, "effective_date", "metering.premises.status_date_format"),
        ({"effective_date": "2099-01-01"}, "effective_date", "metering.premises.status_date_future"),
        ({"__status__": "retired"}, "status", "metering.premises.status_unknown"),
    ],
)
def test_tc6__both_answers_are_required_and_a_future_date_is_refused(
    brazos, dana, overrides, field, message_key
):
    """A future date is refused because `premises.status` holds no pending
    change — accepted, it would be applied at once and then read as scheduled.
    `move_unit` refuses one screen over for the same reason."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        # A field refusal is a `ValidationError` (VAL-001), not a BIZ one — the
        # form is wrong before any rule gets a look at it.
        # `__status__` overrides the STATUS itself, which `_change` takes
        # positionally — a keyword would collide with it.
        target = overrides.pop("__status__", "inactive")
        with pytest.raises(errors.ValidationError) as excinfo:
            _change(dana, premises["id"], target, **overrides)
    errs = excinfo.value.field_errors or []
    assert [e["field"] for e in errs] == [field]
    assert errs[0]["message_key"] == message_key


def test_tc7__the_list_row_door_enforces_the_same_widened_rule(brazos, dana):
    """⚠ **BOTH DOORS, ONE COMPUTATION.** `POST /premises/{id}/deactivate` is
    the units list's row action and predates this wave. Left on its old
    BR-MET-047-only blocker set it would deactivate a building with four live
    units — a signed rule breached by pressing the other button."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        make_unit(dana, premises["id"], label="Unit A")
        with pytest.raises(errors.BizError) as excinfo:
            services.deactivate_premises(
                dana,
                premises["id"],
                # ⚠ **THE PAYLOAD IS NEW AND IT IS THE POINT (`DEF-4743`).** This
                # door used to take none, and recorded neither the date nor the
                # reason — a clerk who went out of service from the LIST row left
                # no record of WHEN it took effect or WHY. PO ruling 2026-09-10,
                # option (b): keep the door, make it demand both. It now delegates
                # to `change_premises_status`, so there is one path through the
                # blockers and one audit shape.
                {"effective_date": TODAY, "reason": "Building demolished"},
            )
    assert excinfo.value.message_key == "metering.premises.status.holdUnits"


def test_def_4743_the_list_door_demands_a_reason_and_a_date(dana, brazos):
    """`DEF-4743` — the old door demanded nothing, and lost the audit facts.

    ⚠ **RED-PROVED AGAINST THE OLD SIGNATURE:** the two-argument
    `deactivate_premises` accepted a bare call and deactivated happily, so this
    case could not have been written against it — the call would simply have
    succeeded. It asserts the behaviour change itself.

    ⚠ **ONE FIELD AT A TIME, BECAUSE THAT IS WHAT THE VALIDATOR DOES.** A first
    draft of this test asserted that an empty payload names BOTH `reason` and
    `effective_date`. It cannot: `_validate_status_change` refuses on the FIRST
    missing field, in the order status → reason → effective_date. That draft
    would have been a test that can never pass, dressed as a stricter one — so
    each field is asked for separately, which is the only way to prove both are
    required.

    ⚠ **AND IT HAS NEVER RUN.** There is no Python environment in the container
    this was written in — `import django` fails — so it is written and
    syntax-checked and NOT executed. Said here rather than implied (hard-won
    law 1: a comment claiming a guarantee is not the guarantee).
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)

        # Nothing at all — the reason is asked for first.
        with pytest.raises(errors.ValidationError) as no_reason:
            services.deactivate_premises(dana, premises["id"], {})
        assert [item["field"] for item in no_reason.value.field_errors] == ["reason"]

        # A reason but no date — now the date is what is missing.
        with pytest.raises(errors.ValidationError) as no_date:
            services.deactivate_premises(dana, premises["id"], {"reason": "Demolished"})
        assert [item["field"] for item in no_date.value.field_errors] == ["effective_date"]


# ══════════════════════════════════════════════════════════════════════════
# D2 — a unit can be taken out of service
# ══════════════════════════════════════════════════════════════════════════
def test_tc8__an_open_account_holds_a_unit_and_its_meters_do_not(brazos, dana, monkeypatch):
    """BR-MET-1164 names ONE term for a unit, and the assets are counted beside
    it rather than blocking on it.

    A meter blocking would refuse nearly every unit this product has — and the
    control exists precisely to retire a flat that has been knocked through,
    which has a meter on it.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], label="Unit A")
        monkeypatch.setattr(seams, "assets_on_unit", lambda uid: [{"id": "1"}, {"id": "2"}])
        monkeypatch.setattr(
            seams, "active_account_for_unit", lambda uid: {"account_no": "AC-1"}
        )
        held = selectors.unit_status_change(unit["id"])
        with pytest.raises(errors.BizError) as excinfo:
            _change_unit(dana, unit["id"], "inactive")

        # The account closes; the two meters stay attached and the unit goes.
        monkeypatch.setattr(seams, "active_account_for_unit", lambda uid: None)
        free = selectors.unit_status_change(unit["id"])
        result = _change_unit(dana, unit["id"], "inactive")

    counts = {row["kind"]: row for row in held["dependencies"]}
    assert counts["open_accounts"]["count"] == 1 and counts["open_accounts"]["blocking"] is True
    assert counts["attached_assets"]["count"] == 2
    assert counts["attached_assets"]["blocking"] is False
    assert counts["attached_assets"]["link"]["route"] == "unit_assets"
    assert excinfo.value.message_key == "metering.units.status.holdAccount"
    assert free["blocked"] is False
    assert result["id"] == unit["id"]
    with tenant_ctx(brazos):
        assert models.Unit.objects.get(pk=unit["id"]).deleted_at is not None


def test_def_met_4761_the_units_list_door_records_the_date_and_the_reason(
    brazos, dana, monkeypatch, audit_rows
):
    """`DEF-MET-4761` — `DEF-4743` one level down, on the unit instead of the
    property, and the PO's ruling of 2026-09-10 applied rather than re-asked.

    ⚠ **NOTHING UNSAFE EVER GOT THROUGH THE OLD DOOR, AND THAT IS WHY NO TEST
    COULD SEE IT.** Both doors refused on `BR-MET-1164` off one computation, so
    every assertion about WHO IS REFUSED passed on both. What differed is what
    reached `audit_log` — the effective date and the reason live there and in NO
    column — and no check in this repo reads what an audit row CONTAINS.

    ⚠ **RED-PROVED AGAINST THE OLD SIGNATURE:** the two-argument
    `deactivate_unit` accepted a bare call and deactivated happily, so the first
    two assertions here could not have been written against it — the call would
    simply have succeeded and written `{"active": False}`.

    ⚠ **ONE FIELD AT A TIME, BECAUSE THAT IS WHAT THE VALIDATOR DOES.**
    `_validate_status_change` refuses on the FIRST missing field, in the order
    status → reason → effective_date, and `status` is forced by this door — so a
    payload asking for both at once could never pass, which is a test dressed as
    a stricter one.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], label="Unit A")
        monkeypatch.setattr(seams, "active_account_for_unit", lambda uid: None)

        # Nothing at all — the reason is asked for first.
        with pytest.raises(errors.ValidationError) as no_reason:
            services.deactivate_unit(dana, unit["id"], {})
        assert [item["field"] for item in no_reason.value.field_errors] == ["reason"]

        # A reason but no date — now the date is what is missing.
        with pytest.raises(errors.ValidationError) as no_date:
            services.deactivate_unit(dana, unit["id"], {"reason": "Merged into Unit 1"})
        assert [item["field"] for item in no_date.value.field_errors] == ["effective_date"]

        # Both given: it goes, and BOTH facts are in the audit row rather than
        # the bare `{"active": False}` the old door wrote.
        # ⚠ `TODAY` and not a literal — a future date is refused by name, so a
        # hardcoded one is a test that starts failing on a date nobody chose.
        audit_rows.clear()
        services.deactivate_unit(
            dana,
            unit["id"],
            {"effective_date": TODAY, "reason": "Merged into Unit 1"},
        )
        assert models.Unit.objects.get(pk=unit["id"]).deleted_at is not None

    assert "unit.deactivated" in audit_actions(audit_rows)
    row = [r for r in audit_rows if r["action"] == "unit.deactivated"][-1]
    assert row["before"] == {"status": "active"}
    assert row["after"]["effective_date"] == TODAY
    assert row["after"]["reason"] == "Merged into Unit 1"
    assert row["after"]["br_ref"] == "BR-MET-1164"

    with tenant_ctx(brazos):

        # ⚠ **AND IT CANNOT REACTIVATE THROUGH A DOOR NAMED `deactivate`.** The
        # status is FORCED rather than accepted, so a caller sending `active`
        # gets the same-status refusal instead of a reactivation.
        with pytest.raises(errors.BizError) as same:
            services.deactivate_unit(
                dana,
                unit["id"],
                {"status": "active", "effective_date": TODAY, "reason": "oops"},
            )
        assert same.value.message_key == "metering.unit.status_unchanged"


def test_def_met_4763_a_blocked_unit_names_the_account_rather_than_counting_it(
    brazos, dana, monkeypatch
):
    """`DEF-MET-4763` — the `U12` frame draws *Account <number> is still open*,
    not *1 open account*.

    A unit is blocked by AT MOST ONE account (`BR-MET-036` derives occupancy
    from exactly that), so the number is knowable here and the count alone threw
    it away: a clerk with two flats open in two tabs could not tell which
    account the refusal meant.

    ⚠ **THE FIGURE IS THE FIXTURE'S, NEVER THE BLUEPRINT'S** — B14 rule 37, PO
    2026-09-10: *"Treat every number drawn in a wireframe as an illustration,
    never a fact to build to."*
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], label="Unit A")
        monkeypatch.setattr(
            seams, "active_account_for_unit", lambda uid: {"account_no": "AC-90001"}
        )
        named = selectors.unit_status_change(unit["id"])

        # An account the seam could not name falls back to the count, and the
        # key is ABSENT rather than null — the screen tells the two apart.
        monkeypatch.setattr(seams, "active_account_for_unit", lambda uid: {"account_no": None})
        unnamed = selectors.unit_status_change(unit["id"])

    accounts = {row["kind"]: row for row in named["dependencies"]}["open_accounts"]
    assert accounts["reference"] == "AC-90001"
    # It is `reference` and NOT `detail`: `detail` is DEF-099's money shape, and
    # one field answering two questions is DEF-755's mechanism exactly.
    assert "detail" not in accounts
    bare = {row["kind"]: row for row in unnamed["dependencies"]}["open_accounts"]
    assert "reference" not in bare
    # A PREMISES never carries it — a building blocked by three accounts has no
    # single number to name, and `P11` counts them for that reason.
    with tenant_ctx(brazos):
        building = selectors.premises_status_change(premises["id"])
    assert all("reference" not in row for row in building["dependencies"])


def test_tc9__a_unit_is_not_reactivated_onto_a_property_that_is_out_of_service(brazos, dana):
    """Derived from BR-MET-1164 rather than invented: the rule says a property
    cannot be inactive while a unit on it is active, so allowing this move would
    breach that invariant one press later."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], label="Unit A")
        _change_unit(dana, unit["id"], "inactive")
        _change(dana, premises["id"], "inactive")
        with pytest.raises(errors.BizError) as excinfo:
            _change_unit(dana, unit["id"], "active")
    assert excinfo.value.message_key == "metering.units.status.holdPremises"

    with tenant_ctx(brazos):
        _change(dana, premises["id"], "active")
        back = _change_unit(dana, unit["id"], "active")
        assert models.Unit.objects.get(pk=unit["id"]).deleted_at is None
    assert back["id"] == unit["id"]


def test_tc10__the_same_status_twice_is_refused_rather_than_audited_as_a_change(brazos, dana):
    """A no-op status change would put a row in the audit trail saying nothing
    happened — `move_unit`'s same-premises refusal, one rule over."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        with pytest.raises(errors.BizError) as excinfo:
            _change(dana, premises["id"], "active")
    assert excinfo.value.message_key == "metering.premises.status_unchanged"


# ══════════════════════════════════════════════════════════════════════════
# The two doors, wired
# ══════════════════════════════════════════════════════════════════════════
def test_tc11__the_endpoints_are_reachable_and_the_write_is_system_admin_only(brazos, dana):
    """BR-MET-035: the READ is any tenant role, the WRITE is the System Admin.

    Built is not wired (hard-won law 2): a service nothing routes to is a
    feature that does not exist.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)

    read = api_call(
        api.premises_status_change,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        premises_id=str(premises["id"]),
    )
    assert read.status_code == 200
    assert read.data["held_by"] is None

    refused = api_call(
        api.premises_status,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        data={"status": "inactive", "effective_date": TODAY, "reason": "x"},
        premises_id=str(premises["id"]),
    )
    assert refused.status_code == 403

    allowed = api_call(
        api.premises_status,
        "post",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={"status": "inactive", "effective_date": TODAY, "reason": "Demolished"},
        premises_id=str(premises["id"]),
    )
    assert allowed.status_code == 200
    assert allowed.data["status"] == "inactive"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 §6 wave D · BR-MET-1164 (PO 2026-09-08, verbatim in
#         04-docs/05-modules/04-metering/02-business-rules.md) · BR-MET-047
# generated: 2026-09-08 by the CR-089 wave D lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
