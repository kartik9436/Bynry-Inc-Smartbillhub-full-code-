# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (EP-CUS-02 S20 Move-Out — `closed_at`, the terminal
#           status, the service agreements' `ended_on`, and the BR-CUS-031
#           final-bill handoff RECORD) · US-CUS-004 (EP-CUS-02 S19 Move-In —
#           the next occupant takes the freed unit through the SAME BR-CUS-017
#           guard, with BR-CUS-056's boundary day)
#           Screens: S19 · S20 · S17 · S21
# Rules:    BR-CUS-017 (one active account per unit — the guard move-in REUSES,
#           never copies) · BR-CUS-018 (a draft never occupied, so it cannot
#           move out) · BR-CUS-021 (reads commit through metering) ·
#           BR-CUS-022 (an occupying account needs a start date) ·
#           BR-CUS-023/024/025 (deposit: lookup, carry-forward, apply-first) ·
#           BR-CUS-029 (the account plan snapshot has no table) ·
#           BR-CUS-030 (move-out: closed_at, terminal status, dunning stop) ·
#           BR-CUS-031 (the final-bill handoff contract) · BR-CUS-054 (the
#           first-class customer entity) · BR-CUS-055 (behaviour classes) ·
#           BR-CUS-056 (the OUTGOING account pays the move day) ·
#           BR-CUS-057 (deposit interest) · BR-BIL-004 (issued invoices are
#           immutable) · BR-MET-036 (occupancy DERIVES — this is what a
#           move-out frees) · BR-MET-044 (the unit keeps its plan) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC)
# Journeys: T5-15 step 5 — "RECOVERY, the ratified door for a genuine tenant
#           change: Move-Out for ACC-1042 → unit derives Vacant → 4B reappears
#           in the pickers → the new move-in succeeds" · T4-06 steps 1 & 5 ·
#           J2 step 4
# Note:     The move-in CONCURRENCY proof is a separate file —
#           tests/test_us_cus_004_move_in_race.py — because advisory locks are
#           a PostgreSQL feature and a green sqlite run proves nothing about a
#           race. What is proved HERE is the refusal and the lock ORDERING;
#           what is proved THERE is that two concurrent move-ins cannot both
#           reach the check.
# ───────────────────────────────────────────────────────
"""W2 customers slice 3 — move-out and move-in.

THE GAP THIS FILE CLOSES, stated as the accounts lane reported it: "once a unit
is occupied, the only way to free it today is a direct status write." Slice 2
could make an account occupy a unit and had no flow that ever released one —
`_apply_status_change` refuses a bare flip to a terminal status (correctly), so
a unit taken by mistake stayed taken forever and T5-15 step 5's ratified
recovery door did not exist.

Three claims are made here that nothing else in the suite makes:

1. **A move-out really frees the unit** — asserted through METERING's derived
   occupancy (BR-MET-036) and through the fact that a following move-in
   SUCCEEDS, not merely through this module's own columns.
2. **Move-in goes through the SAME guard.** `test_us_cus_004_tc6__*` spies on
   `lock_unit_scope` and `occupying_accounts_for_unit` and asserts the ORDER —
   lock, then check — on the move-in path, exactly as US-CUS-003 does for
   create. A copy of the guard would pass a refusal test and fail this one.
3. **Everything the flows cannot do is named.** Every warning code carries the
   BR that owns it; the tests assert the exact SETS, so a later lane that
   silently drops one (because it implemented it, or because it stopped
   caring) goes red either way.
"""

from datetime import date

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    audit_actions,
    brazos,
    dana,
    erin,
    executive_actor,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)

from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: E402,F401

# DEF-CUS-10093 (PO 2026-10-13, option B): the final-bill draft is isolated
# here — this suite tests the close; see tests/move_out_draft_isolation.py.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("move_out_draft_isolated")]

MOVE_IN_DAY = "2026-08-15"
MOVE_OUT_DAY = "2026-08-14"


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — the EP-CUS-02 §4 world (U-10432-A / U-10432-B), built
# through the REAL services of the modules that own each row.
# ══════════════════════════════════════════════════════════════════════════
def _plan(tenant, name="Residential Standard", service_code="electric"):
    """A PUBLISHED rate plan the unit can be put on.

    Was `_tariff` until 2026-08-11: a unit held ONE service's rate schedule,
    and now holds the PLAN across its services (PO ruling). Created directly
    because the plan CONTENT is EP-RAT-01's story — what matters here is only
    that `units.rate_plan_id` is non-null, which is all BR-MET-040 asks.
    `status="published"` is load-bearing: BR-RAT-030 makes only published plans
    assignable, so a draft would fail to resolve and read as an unrelated bug.
    """
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit_with_plan(actor, tenant, *, label="Unit A", services=("electric", "water")):
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    for code in services:
        metering_services.ensure_service_point(unit["id"], code)
    return unit


def _account_payload(**overrides):
    """The incoming tenant's fields — the S19 step-2 new-customer quick fields.

    ⚠ **THE DOCSTRING SAID *"which is all that can be written while
    BR-CUS-054's customer entity has no table"* AND THAT WAS ALREADY FALSE.**
    The entity was built on 2026-08-11 and `POST /accounts/{id}/move-in` has
    accepted the whole customer block since `CR-056` W3 — the screen simply
    never sent one, which is `DEF-2818`'s twin and what `CR-058` task 8 closes.

    ⛔ **AND SINCE 2026-09-01 THE BLOCK IS REQUIRED (`BR-CUS-1024`).** PO
    verbatim: *"Without identifier we cannot create Customer ID or master
    account ot regular account"*. A phone identifies the incoming tenant — the
    same one the contact already carries — which opens the door and mints a
    number without making any match `strong` and without reusing anybody's
    record, so no assertion in this file moves. The refusal itself is asserted
    in `tests/test_cr058_w1_one_customer_every_door.py::test_tc8`.
    """
    payload = {
        "account_type": "residential",
        "opened_at": MOVE_IN_DAY,
        "contact": {
            "full_name": "Thomas Nguyen",
            "email": "thomas.nguyen@example.com",
            "phone": "+1 (281) 555-0144",
        },
        "customer": {
            "display_name": "Thomas Nguyen",
            "kind": "person",
            "identity": {"phone": "+1 (281) 555-0144"},
        },
    }
    payload.update(overrides)
    return payload


#: The outgoing occupant's phone. `BR-CUS-1024` — an account needs an
#: identifier, and a phone is enough (`BR-CUS-1023` names it for a person). It
#: is DIFFERENT from the incoming tenant's above, so the two never resolve to
#: one customer and every move-out → move-in case still describes two parties.
OCCUPANT_PHONE = "+1 (281) 555-0155"


def _occupant(actor, tenant, unit, *, opened_at="2026-07-01", name="Sarah Miller"):
    """An ACTIVE account holding the unit — the state a move-out starts from."""
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened_at,
            "contact": {"full_name": name},
            # `BR-CUS-1024` (2026-09-01) — the outgoing tenant is identified too.
            "customer": {
                "display_name": name,
                "kind": "person",
                "identity": {"phone": OCCUPANT_PHONE},
            },
        },
    )


def _post(view, tenant, role, account_id, payload=None, user=None):
    return api_call(
        view,
        "post",
        user=user or FakeUser(),
        role=role,
        tenant=tenant,
        data=payload if payload is not None else {},
        account_id=account_id,
    )


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-005 — the move-out itself
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_005_tc1__move_out_closes_the_account_and_frees_the_unit(brazos, marcus, audit_rows):
    """US-CUS-005 TC-1 + T4-06 step 1: "`closed_at` = Jul 18; status → Closed;
    unit occupancy DERIVES Vacant (never manually set)".

    The freeing is asserted through METERING, not through this module's own
    columns — BR-MET-036 is the rule that matters and it lives over there.

    RED before this lane: `services.move_out` raised NotImplementedError and the
    only way to reach a terminal status was the direct ORM write
    `test_us_cus_001_tc5__a_closed_account_frees_the_unit_again` had to perform.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        assert (
            metering_selectors.occupancy_of(metering_selectors.unit_row(unit["id"])) == "occupied"
        )
        audit_rows.clear()

        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})

        assert closed["status"] == "closed"
        assert closed["status_behavior_class"] == "terminal"
        assert closed["closed_at"] == MOVE_OUT_DAY
        # BR-CUS-030 / US-CUS-005 §5: the same date ends every open agreement.
        assert [row["ended_on"] for row in closed["service_agreements"]] == [
            MOVE_OUT_DAY,
            MOVE_OUT_DAY,
        ]
        # …and the unit is genuinely free again, per metering's own derivation.
        assert customers_services.active_account_for_unit(unit["id"]) is None
        row = metering_selectors.unit_list_dict(metering_selectors.unit_row(unit["id"]))
        assert row["occupancy"] == "vacant"
        assert "account.closed" in audit_actions(audit_rows)


def test_us_cus_005_tc1__the_unit_keeps_its_plan_and_reappears_in_the_picker(brazos, marcus):
    """BR-MET-044 / BR-CUS-014 sc.5 (CONFIRMED): "the unit KEEPS its last plan
    after move-out as the next-tenant prefill" — and T5-15 step 5's "4B
    reappears in the pickers".

    Nothing in the move-out path touches `units.rate_plan_id`; this asserts
    that absence, because a lane that "tidied up" by clearing it would break the
    next move-in's BR-MET-040 check and nothing else would notice."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        plan_before = metering_selectors.unit_row(unit["id"]).rate_plan_id
        account = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})

        assert metering_selectors.unit_row(unit["id"]).rate_plan_id == plan_before
        vacant = metering_selectors.units_list(filters={"occupancy": "vacant"})
        assert str(unit["id"]) in {str(row.id) for row in vacant}


def test_us_cus_005_tc1__move_out_returns_the_handoff_it_can_assemble(brazos, marcus):
    """BR-CUS-031 (CONFIRMED) — the final-bill contract: {account, move-out
    date, committed final reads, plan snapshot per service date, prior balance,
    deposit disposition, refund method}.

    Three of those seven have a source in this repository. The other four carry
    their rule id instead of a plausible value, and the record says outright
    that it is NOT PERSISTED — there is no handoff table, queue or outbox in B2
    or any addendum, so nothing downstream can read it yet."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})

    handoff = closed["final_bill_handoff"]
    assert handoff["account_no"] == account["account_no"]
    assert handoff["moved_out_on"] == MOVE_OUT_DAY
    # BR-CUS-056: the outgoing account pays the move day, so the bill runs
    # THROUGH it — stated so billing never has to infer the boundary.
    assert handoff["bill_through"] == MOVE_OUT_DAY
    assert handoff["bill_through_br_ref"] == "BR-CUS-056"
    # Money is the STORED NUMERIC(18,6), never computed here.
    assert handoff["prior_balance"] == "0.000000"
    assert handoff["deposit_on_file"] == "0.000000"
    assert handoff["currency"] == "USD"
    # ⚠ **AMENDED 2026-08-26 (CR-038 W9 task 4) — `final_reads` IS SERVED NOW,
    # so this case pins the SERVED shape instead of the absence.** BR-CUS-021's
    # metering half exists (`metering.services.commit_event_reads`), and
    # `move_out` sweeps `seams.reads_for_unit` once at close and hands the
    # answer to the handoff. RED-FIRST PROOF, verbatim, before the assertion
    # moved:
    #     AssertionError: assert {'unit_id': '…', 'as_of': None, 'meters': []}
    #                     is None
    # This account's unit carries NO meters, so the served answer is the empty
    # meter list — which is why the element being SERVED had to be pinned
    # separately from it being non-empty: `final_reads: []` reading as "none
    # were taken" is exactly the confusion `final_reads_unavailable` was minted
    # for, and it is now `None` because the seam ANSWERED.
    assert handoff["final_reads"] is not None
    assert handoff["final_reads"]["meters"] == []
    assert handoff["final_reads_unavailable"] is None
    # The close-time flag rides beside it (migration 0026): a unit with no
    # meters has nothing to read, so no `taken`/`due` verdict is recorded.
    assert handoff["final_read_state"] is None
    assert handoff["plan_snapshot"] is None
    assert handoff["plan_snapshot_unavailable"] == "BR-CUS-029"
    assert handoff["deposit_interest_accrued"] is None
    assert handoff["deposit_interest_unavailable"] == "BR-CUS-057"
    assert handoff["deposit_disposition"] is None
    assert handoff["refund_method_unavailable"] == "BR-CUS-025"
    # And the one that matters most to a reader who assumes success:
    assert handoff["persisted"] is False
    assert handoff["persistence_unavailable"] == "BR-CUS-031"


def test_us_cus_005_tc1__move_out_names_every_downstream_it_cannot_perform(brazos, marcus):
    """T4-06's chain is the longest ratified downstream in the product: final
    bill → deposit apply → settlement → ledger → dunning stop → close-out
    documents. The response says what it could NOT do, by rule id, rather than
    letting silence read as success (the metering `history_recorded: false`
    precedent).

    ⚠ **THIS DOCSTRING SAID *"NONE of those modules has a table"* UNTIL
    2026-09-24 (`DEF-CUS-6465`), AND THAT WAS THE CLAIM THE WHOLE DEFECT WAS.**
    `invoices`, `refunds` and `payments` all have tables and have had for weeks,
    and the deposit-interest accrual has ANSWERED since 2026-09-03 (`CR-059`
    CS-20). Only collections and notifications are still tableless. The codes
    that survive are the ones still TRUE for a different reason: a move-out
    PRICES the closing window and does not RAISE the invoice, and settling the
    deposit needs that invoice.

    The SET is asserted, not a subset: a later lane that implements one of these
    must delete its entry here, and one that quietly drops an entry goes red."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})

    assert {warning["code"] for warning in closed["warnings"]} == {
        "final_bill_not_issued",
        "final_bill_handoff_not_persisted",
        "final_reads_not_committed",
        "deposit_not_settled",
        # ⛔ **`deposit_interest_not_accrued` LEFT THIS SET ON 2026-09-24 AND THE
        # REASON IS NOT THAT IT WAS DELETED (`DEF-CUS-6465`).** The entry still
        # exists; it became CONDITIONAL, on `final_reads_not_committed`'s
        # precedent. The accrual answers for this account, so claiming no
        # interest was worked out would be false — **an unconditional row is a
        # claim about the PRODUCT and a conditional one is a claim about THIS
        # move-out**, and the accrual stopped being a product-level absence the
        # day it shipped. A move-out where the figure genuinely cannot be
        # reached still carries it.
        #
        # ⚠ **AND THIS ASSERTION IS WHY THE FIX COULD NOT BE HALF-DONE.** It is
        # `==`, so the correction had to come here and be argued, rather than
        # passing quietly under a `<=`.
        # ⚠ **`close_reason_not_recorded` LEFT THIS SET ON 2026-09-20** (PO
        # ruling of that date, option A — the reason gets a column). It said
        # *"`accounts.close_reason` is PROPOSED-SCHEMA and not built"*, which
        # became a false claim on every response the moment migration 0058
        # landed. The set is EXACT (`==`), so this line going stale would have
        # been caught here rather than shipped — which is the assertion doing
        # its job, and the reason it is `==` and not `<=`.
        "dunning_not_stopped",
        "closeout_documents_not_queued",
        "move_out_date_not_checked_against_issued_bills",
    }
    assert {warning["br_ref"] for warning in closed["warnings"]} == {
        "BR-CUS-031",
        "BR-CUS-021",
        "BR-CUS-025",
        # ⛔ `BR-CUS-057` left with `deposit_interest_not_accrued` above, for the
        # same reason and on the same day: the accrual answers for this account,
        # so nothing cites the rule that governs its ABSENCE. The rule itself is
        # untouched and the row still rides a move-out where the figure cannot
        # be reached — this set follows the warnings, it does not define them.
        "BR-CUS-030",
        "BR-BIL-004",
    }
    assert all(warning.get("detail") for warning in closed["warnings"])


def test_us_cus_005_tc6__a_move_out_before_the_service_start_is_refused(brazos, marcus):
    """US-CUS-005 §5: the move-out date is "≥ opened_at". A tenancy that ended
    before it began would hand billing a negative day count for the B4.3
    proration BR-CUS-022 asks for."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit, opened_at="2026-08-01")
        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_out(marcus, account["id"], {"moved_out_on": "2026-07-31"})
        assert excinfo.value.code == errors.BIZ_STATE
        assert excinfo.value.br_ref == "BR-CUS-030"
        # Nothing written: the account still holds the unit.
        assert customers_services.active_account_for_unit(unit["id"])["id"] == account["id"]


def test_us_cus_005_tc1__only_an_occupant_can_move_out(brazos, marcus):
    """A `pending_activation` draft never took the unit (BR-CUS-018 — "never
    derives occupancy") and a closed account has already left it (BR-MET-036).
    Closing either would write a `closed_at` for a tenancy that never happened,
    or record a second ending for one that already ended."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        draft = customers_services.create_account(
            marcus,
            {"unit_id": str(unit["id"]), "account_type": "residential", "opened_at": MOVE_IN_DAY},
        )
        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_out(marcus, draft["id"], {"moved_out_on": MOVE_OUT_DAY})
        assert excinfo.value.br_ref == "BR-CUS-030"
        assert excinfo.value.params["status"] == "pending_activation"

        occupant = _occupant(marcus, brazos, _unit_with_plan(marcus, brazos, label="Unit B"))
        customers_services.move_out(marcus, occupant["id"], {"moved_out_on": MOVE_OUT_DAY})
        with pytest.raises(errors.BizError) as second:
            customers_services.move_out(marcus, occupant["id"], {"moved_out_on": MOVE_OUT_DAY})
        assert second.value.params["status"] == "closed"


def test_us_cus_005_tc1__the_move_out_date_is_required(brazos, marcus):
    """BR-CUS-030 hangs `closed_at`, every `ended_on` and the whole BR-CUS-031
    handoff off this one value; defaulting it to "today" would date a tenancy's
    end by when the clerk got round to the paperwork (BR-TEN-043 event-time
    law)."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_out(marcus, account["id"], {})
        assert excinfo.value.field_errors[0]["field"] == "moved_out_on"
        assert excinfo.value.field_errors[0]["code"] == errors.VAL_REQUIRED


def test_us_cus_005_tc1__a_non_terminal_status_cannot_end_a_tenancy(brazos, marcus):
    """BR-CUS-055: occupancy keys off the behaviour CLASS. A "move-out" onto
    `vacation_hold` would leave the account occupying the unit — the flow would
    report success and free nothing."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_out(
                marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY, "status": "vacation_hold"}
            )
        assert excinfo.value.br_ref == "BR-CUS-055"
        assert excinfo.value.params["behavior_class"] == "billable_base_only"


def test_us_cus_005_tc6__the_issued_bill_guard_bites_the_moment_billing_publishes_it(
    brazos, marcus, monkeypatch
):
    """US-CUS-005 TC-6: "move-out date before the last issued bill's period end
    → blocked; issued bills are untouched (BR-BIL-004)".

    Billing has no `invoices` table, so the seam is unwired and the real answer
    is unknown — which is why every move-out today carries the
    `move_out_date_not_checked_against_issued_bills` warning. That leaves the
    refusal itself unexercised, and unexercised code is code nobody has seen
    work: this drives the seam to an answer and asserts BOTH branches, so the
    guard is proved rather than merely present. It goes live with no change here
    the day billing publishes `last_issued_invoice_period_end`."""
    from apps.customers import seams as customers_seams

    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit, opened_at="2026-06-01")
        monkeypatch.setattr(
            customers_seams, "last_issued_invoice_period_end", lambda account_id: date(2026, 7, 31)
        )

        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_out(marcus, account["id"], {"moved_out_on": "2026-07-15"})
        assert excinfo.value.br_ref == "BR-BIL-004"
        assert excinfo.value.params["issued_through"] == "2026-07-31"
        assert customers_models.Account.objects.get(pk=account["id"]).closed_at is None

        # On or after the issued period end, the move-out proceeds — and the
        # "could not check" warning is GONE, because the check ran.
        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": "2026-07-31"})
        assert "move_out_date_not_checked_against_issued_bills" not in {
            warning["code"] for warning in closed["warnings"]
        }


@pytest.mark.parametrize(
    "field,value,br_ref",
    [
        # ⚠ **`reason` LEFT THIS LIST ON 2026-09-20** (PO ruling, option A). It
        # read `("reason", "Tenant lease ended", "BR-CUS-030")` with the comment
        # *"accounts.close_reason not built"*. It is built, `MOVE_OUT_FIELDS`
        # accepts `reason`, and the refusal it is replaced by — an UNKNOWN code,
        # which is a different refusal on a different rule — has its own case in
        # `test_br_cus_030_close_reason.py`. `close_reason` (the COLUMN's name)
        # stays refused on this door and is asserted there too.
        # ⚠ `final_reads` LEFT THIS LIST 2026-08-26 (CR-038 W9 task 4). It is no
        # longer a field with no home: `MOVE_OUT_FIELDS` accepts it and it routes
        # through `seams.commit_event_reads`. Its refusal is still asserted —
        # `test_us_cus_005__an_empty_final_reads_is_refused_as_rows_required`
        # below — but it is a DIFFERENT refusal (rows required, not "not
        # writable"), which is why it cannot ride this parametrize. RED-FIRST
        # PROOF, verbatim, with the row still here:
        #     KeyError: 'br_ref'
        # i.e. the row was already being refused by the reads parser rather than
        # by REFUSED_FIELDS, and the case was asserting a key the new refusal
        # does not carry.
        ("deposit_disposition", "apply_first", "BR-CUS-025"),  # needs the final bill
        ("refund_method", "ach", "BR-CUS-025"),  # payments `refunds` has no tables
        ("deposit_interest_accrued", "3.20", "BR-CUS-057"),  # engine is US-CUS-023 §7
        ("closed_at", "2026-08-14", "BR-CUS-030"),  # the flow names it `moved_out_on`
    ],
)
def test_us_cus_005_tc1__move_out_fields_with_no_home_are_refused_by_rule(
    brazos, marcus, field, value, br_ref
):
    """ "Anything the API cannot honour is REFUSED with its rule identifier,
    never silently dropped." Each of these is a real S20 wizard field whose
    destination is an unbuilt column or another module's table — a clerk who
    typed a refund method and got a 201 would believe a refund was queued."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_out(
                marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY, field: value}
            )
    error = excinfo.value.field_errors[0]
    assert error["field"] == field
    assert error["params"]["br_ref"] == br_ref
    assert error["message_key"] == "customers.account.field_not_writable"


def test_us_cus_005__an_empty_final_reads_is_refused_as_rows_required(brazos, marcus):
    """The replacement for `final_reads`' row in the parametrize above.

    CR-038 W9 task 4 made `final_reads` WRITABLE, so it is no longer refused by
    `REFUSED_FIELDS` with `BR-CUS-021` — but an EMPTY list is still refused, and
    for a better reason: a wizard that sent a `final_reads` key sent one because
    a clerk keyed readings, and `[]` is a payload that lost them somewhere
    between the screen and the door. `services._commit_event_reads` states it —
    *"A non-list / empty / junk `reads` payload is REFUSED, not skimmed: a
    wizard that sent readings must learn what happened to every one"* — and the
    field named in the refusal is the WIZARD's own (`final_reads`), never the
    metering door's inner `reads`, so the message lands on the control the clerk
    typed into.

    An OMITTED `final_reads` is a different thing entirely and is NOT refused:
    a move-out with no readings at all is lawful, and every other case in this
    file commits one.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_out(
                marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY, "final_reads": []}
            )
        still_open = customers_models.Account.objects.get(pk=account["id"])

    error = excinfo.value.field_errors[0]
    assert error["field"] == "final_reads"
    assert error["message_key"] == "customers.event_reads.rows_required"
    # The refusal is the whole act (BR-SHL-019): nothing closed.
    assert still_open.closed_at is None


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-004 — the move-in, through the SAME guard
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_004_tc1__the_recovery_door_move_out_then_move_in(brazos, marcus, audit_rows):
    """T5-15 step 5 END TO END — the ratified door this whole slice exists for:
    "Move-Out wizard for ACC-1042 … unit derives Vacant, THEN Move-In creates
    the new account … Unit history: sequential occupancy, never parallel".

    RED before this lane: the move-out half raised NotImplementedError, so the
    unit could never be freed and the second half had nothing to take.
    """
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})
        audit_rows.clear()

        incoming = customers_services.move_in(marcus, outgoing["id"], _account_payload())

        # A NEW account with its own number — reopening does not exist (T4-06 §5).
        assert incoming["id"] != outgoing["id"]
        assert incoming["account_no"] != outgoing["account_no"]
        assert incoming["status"] == "active"
        assert incoming["unit_id"] == str(unit["id"])
        assert incoming["name"] == "Thomas Nguyen"
        assert incoming["moved_in_after_account_no"] == outgoing["account_no"]
        assert "account.moved_in" in audit_actions(audit_rows)
        # Occupancy is back on, derived, and names the NEW account.
        row = metering_selectors.unit_list_dict(metering_selectors.unit_row(unit["id"]))
        assert row["occupancy"] == "occupied"
        assert row["account_no"] == incoming["account_no"]
        # Sequential, never parallel: one occupant, two tenancies on the unit.
        assert (
            customers_models.Account.objects.filter(
                unit_id=unit["id"],
                status__behavior_class__in=customers_services.OCCUPYING_BEHAVIOR_CLASSES,
            ).count()
            == 1
        )
        assert customers_services.account_reference_count(unit["id"]) == 2
        # Fresh service agreements, opened on the move-in day (US-CUS-004 §5).
        assert [row["started_on"] for row in incoming["service_agreements"]] == [
            MOVE_IN_DAY,
            MOVE_IN_DAY,
        ]
        assert all(row["ended_on"] is None for row in incoming["service_agreements"])


def test_us_cus_004_tc6__a_move_in_onto_a_still_occupied_unit_is_refused(brazos, marcus):
    """US-CUS-004 TC-6: "Move-in attempted on U-10432-A (occupied by A-10432) …
    forged submit rejected by BR-CUS-017 one-active-per-unit".

    This is the guard REUSE assertion in its simplest form: move-in did not get
    its own occupancy rule, it walked into the existing one — and the refusal
    still NAMES the existing account, because that is what the IS-7 failed state
    renders (T5-15 step 3)."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        sitting = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_in(marcus, sitting["id"], _account_payload())
        assert excinfo.value.code == errors.BIZ_STATE
        assert excinfo.value.br_ref == "BR-CUS-017"
        assert excinfo.value.params["account_no"] == sitting["account_no"]
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 1


def test_us_cus_004_tc6__the_move_in_locks_the_scope_before_it_checks(brazos, marcus, monkeypatch):
    """THE guard-reuse proof, and the one a copied guard would fail.

    Move-in must reach the unit through the SAME `_make_occupying` ordering the
    create path uses: lock the (tenant, unit) scope, THEN read the occupancy.
    A lock taken after the check serializes nothing — both writers have already
    read "vacant" — and on a vacant unit `SELECT … FOR UPDATE` has no rows to
    lock, which is why the scope lock is the only thing that closes it.

    Asserted on every vendor; the cross-session effect is
    tests/test_us_cus_004_move_in_race.py (live Postgres)."""
    calls: list[str] = []
    real_lock = customers_services.lock_unit_scope
    real_check = customers_selectors.occupying_accounts_for_unit

    def spy_lock(unit_id):
        calls.append("lock")
        return real_lock(unit_id)

    def spy_check(unit_id, *, lock=False):
        calls.append("check-locked" if lock else "check")
        return real_check(unit_id, lock=lock)

    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})

        monkeypatch.setattr(customers_services, "lock_unit_scope", spy_lock)
        monkeypatch.setattr(customers_selectors, "occupying_accounts_for_unit", spy_check)
        customers_services.move_in(marcus, outgoing["id"], _account_payload())

    assert "lock" in calls, "the move-in path did not take the BR-CUS-017 scope lock at all"
    assert calls.index("lock") < calls.index("check-locked"), (
        f"the scope lock must precede the occupancy check; call order was {calls} — "
        "a check before the lock is exactly the T5-15 step-4 race, and a move-in that "
        "carried its own copy of the guard would not appear here at all"
    )


def test_us_cus_004_tc6__the_chained_start_cannot_land_on_the_move_day(brazos, marcus):
    """BR-CUS-056 (CONFIRMED — PO OQ-060 a): "the OUTGOING account pays the move
    day; the incoming account starts the NEXT day from the same reading — no
    gap, no double-bill." US-CUS-004 TC-6: "the backdated chained start blocks".

    Both sides are asserted: the move day itself is refused (and the refusal
    says which day IS available), and move-day + 1 succeeds. Without the guard
    the first call returns 201 and the shared day gets billed twice."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})

        for backdated in (MOVE_OUT_DAY, "2026-08-10"):
            with pytest.raises(errors.BizError) as excinfo:
                customers_services.move_in(
                    marcus, outgoing["id"], _account_payload(opened_at=backdated)
                )
            assert excinfo.value.code == errors.BIZ_STATE
            assert excinfo.value.br_ref == "BR-CUS-056"
            assert excinfo.value.params["prior_account_no"] == outgoing["account_no"]
            assert excinfo.value.params["earliest_start"] == MOVE_IN_DAY

        # Nothing was written by either refusal…
        assert customers_models.Account.objects.filter(unit_id=unit["id"]).count() == 1
        # …and the day after the move day is accepted.
        incoming = customers_services.move_in(
            marcus, outgoing["id"], _account_payload(opened_at=MOVE_IN_DAY)
        )
        assert incoming["opened_at"] == MOVE_IN_DAY


def test_us_cus_004_tc6__the_boundary_day_binds_every_occupying_path_not_just_move_in(
    brazos, marcus
):
    """BR-CUS-056 is about the UNIT's boundary day, not about which wizard was
    used — so the check lives in `_make_occupying` and a plain create (the
    standalone S19 entry, and T5-15 step 3's forged submit) meets it too.

    If it lived in `move_in` alone, `POST /accounts` would be an open side door
    onto the outgoing account's paid day."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})

        with pytest.raises(errors.BizError) as excinfo:
            customers_services.create_account(
                marcus,
                {
                    "unit_id": str(unit["id"]),
                    "account_type": "residential",
                    "status": "active",
                    "opened_at": MOVE_OUT_DAY,
                },
            )
        assert excinfo.value.br_ref == "BR-CUS-056"


def test_us_cus_004_tc1__move_in_names_what_it_cannot_carry_over(brazos, marcus):
    """US-CUS-004's whole reason for existing beyond a plain create is the
    RETURNING customer: prior-final read prefill, the customer entity, and the
    deposit carried forward from their closed account — plus J2 step 4's two
    (`plan_snapshot_not_recorded`, `deposit_not_applied`) which every occupying
    path already owes.

    ⚠ **AMENDED 2026-09-20 — `customer_not_linked` IS NO LONGER AMONG THEM
    (`DEF-CUS-5912`).** This docstring said *"All three need tables that do not
    exist, so all three are reported"*, and that stopped being true on
    **2026-08-11**, when `US-CUS-019` built `customers` and `customer_accounts`.
    The entry rode every move-in for forty days regardless — including the ones
    that recognised a returning customer and linked them — carrying a reason
    (*"the first-class `customers` entity has no table"*) whose every clause was
    false. `move_in` now drops it whenever the commit linked OR created a
    customer, which on a committed move-in is always: `require_identity=True`
    means `BR-CUS-1024` refuses an account whose customer identifies nobody, so
    the un-linked case never reaches a commit.

    **This assertion is what let it ride.** It named the codes it EXPECTED and
    compared them as a set, so it would have gone red if one disappeared — and
    it went green for forty days because nobody re-read what the set was
    claiming. `DEF-CUS-5912`'s own prevention line: *"Where a stated absence can
    close, assert that it stops being served on the day it closes."* So the
    absence is asserted below by NAME rather than left to the set equality."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})
        incoming = customers_services.move_in(marcus, outgoing["id"], _account_payload())

    codes = {warning["code"] for warning in incoming["warnings"]}
    # ⚠ **AMENDED 2026-10-05 (`DEF-CUS-9702`, CR-171 P1.21, lane MVI-FLOW).**
    # This set held `plan_snapshot_not_recorded`, false since BR-CUS-029 was
    # superseded on 2026-08-11 (the plan lives on the unit); it is asserted
    # ABSENT by name, `DEF-CUS-5912`'s own prevention line. ⚠ The equality on
    # the WHOLE set was ALREADY red on the tip before this change: the set no
    # longer carries `deposit_not_applied` (the deposit capability filters it,
    # `services` "IS FALSE ON A DOOR THAT JUST APPLIED"), so it is narrowed to
    # the two members this test is about.
    assert "plan_snapshot_not_recorded" not in codes
    assert {"deposit_carry_forward_unavailable", "initial_reads_not_committed"} <= codes
    # `DEF-CUS-5912` — asserted BY NAME, not only by the set above, so a lane
    # putting it back has to delete this line and read the reason first.
    assert "customer_not_linked" not in codes, (
        "this move-in created and linked a customer — `customer_not_linked`'s "
        "stated reason expired on 2026-08-11 when `customers` was built"
    )
    assert incoming["customer_outcome"] == "created"
    assert {warning["br_ref"] for warning in incoming["warnings"]} >= {
        # `BR-CUS-054` left with `customer_not_linked` — `DEF-CUS-5912`;
        # `BR-CUS-029` with `plan_snapshot_not_recorded` — `DEF-CUS-9702`.
        "BR-CUS-024",
        "BR-CUS-021",
    }
    assert "BR-CUS-029" not in {warning["br_ref"] for warning in incoming["warnings"]}
    # BR-CUS-023: the deposit is a LOOKUP from a plan schedule that has no
    # table, so it is 0.000000 and unclaimed — never a guessed $150.00.
    assert incoming["deposit_on_file"] == "0.000000"
    assert incoming["plan"] is None


def test_us_cus_004_tc1__the_move_in_unit_comes_from_the_outgoing_account(brazos, marcus):
    """11b §S19 scopes the move-in to an account, and US-CUS-005 TC-3 chains it
    "pre-scoped to U-10432-A". A `unit_id` in the body would be a second,
    disagreeing source of truth for which room the tenant is entering — refused
    with BR-CUS-017 rather than silently ignored."""
    with tenant_ctx(brazos):
        unit_a = _unit_with_plan(marcus, brazos, label="Unit A")
        unit_b = _unit_with_plan(marcus, brazos, label="Unit B")
        outgoing = _occupant(marcus, brazos, unit_a)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})

        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.move_in(
                marcus, outgoing["id"], _account_payload(unit_id=str(unit_b["id"]))
            )
        error = excinfo.value.field_errors[0]
        assert error["field"] == "unit_id"
        assert error["params"]["br_ref"] == "BR-CUS-017"


def test_us_cus_004_tc3__a_move_in_that_would_not_occupy_is_refused(brazos, marcus):
    """US-CUS-004 §1's exit is "unit derives Occupied". A move-in onto a
    non-occupying status would report success and leave the unit vacant; the
    draft road stays open and is `POST /accounts` (BR-CUS-018)."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})
        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_in(
                marcus, outgoing["id"], _account_payload(status="pending_activation")
            )
        assert excinfo.value.br_ref == "BR-CUS-055"
        assert excinfo.value.params["behavior_class"] == "non_billable"


def test_us_cus_004_tc1__a_move_in_still_needs_a_start_date_and_a_plan(brazos, marcus):
    """The completeness rules `_make_occupying` already owned apply unchanged —
    BR-CUS-022's start date and BR-MET-040's plan-at-activation. Asserted on the
    move-in path so a future refactor cannot route around them."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)
        customers_services.move_out(marcus, outgoing["id"], {"moved_out_on": MOVE_OUT_DAY})
        payload = _account_payload()
        payload.pop("opened_at")
        with pytest.raises(errors.BizError) as excinfo:
            customers_services.move_in(marcus, outgoing["id"], payload)
        assert excinfo.value.br_ref == "BR-CUS-022"


# ══════════════════════════════════════════════════════════════════════════
# The endpoints — mounted, role-gated, tenant-scoped
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_005_tc1__the_move_routes_are_actually_mounted(brazos):
    """HARD-WON LAW 2 at the routing layer: an endpoint no URLconf includes is
    not an endpoint. Resolved through the REAL root URLconf, so a lane that
    forgets the include goes red here instead of shipping an API nobody can
    call."""
    from django.urls import resolve

    assert (
        resolve(f"/api/brazosbend/accounts/{brazos.id}/move-in").func
        is customers_api.account_move_in
    )
    assert (
        resolve(f"/api/brazosbend/accounts/{brazos.id}/move-out").func
        is customers_api.account_move_out
    )


def test_us_cus_004_tc1__the_chain_works_through_the_real_endpoints(brazos, marcus):
    """The S20 → S19 chain as a client drives it: move-out 200, move-in 201 with
    a Location header pointing at the NEW account (US-CUS-004 §1's "new account
    #")."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        outgoing = _occupant(marcus, brazos, unit)

    closed = _post(
        customers_api.account_move_out,
        brazos,
        "billing_clerk",
        outgoing["id"],
        {"moved_out_on": MOVE_OUT_DAY},
    )
    assert closed.status_code == 200
    assert closed.data["closed_at"] == MOVE_OUT_DAY

    moved_in = _post(
        customers_api.account_move_in, brazos, "billing_clerk", outgoing["id"], _account_payload()
    )
    assert moved_in.status_code == 201
    assert moved_in["Location"].endswith(f"/accounts/{moved_in.data['id']}")
    assert moved_in.data["id"] != outgoing["id"]


def test_us_cus_005_tc1__an_executive_may_not_move_an_account_out_or_in(brazos, marcus):
    """A4: Accounts is VIEW for Executive; BR-SHL-025/BR-IDN-009 make the server
    the enforcement. Both halves are asserted — the endpoint AND the service —
    because a move-out is the most destructive thing this module can do."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        occupant = _occupant(marcus, brazos, unit)

    for view in (customers_api.account_move_out, customers_api.account_move_in):
        forged = _post(view, brazos, "executive", occupant["id"], {"moved_out_on": MOVE_OUT_DAY})
        assert forged.status_code == 403
        assert forged.data["code"] == errors.AUTH_PERMISSION_DENIED

    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            customers_services.move_out(
                executive_actor(), occupant["id"], {"moved_out_on": MOVE_OUT_DAY}
            )
        # …and nothing happened: the unit is still held by the same account.
        assert customers_services.active_account_for_unit(unit["id"])["id"] == occupant["id"]


def test_us_cus_005_tc7__another_tenants_account_is_a_404_never_a_403(
    brazos, lonestar, marcus, erin
):
    """US-CUS-005 TC-7 / HR-1: a cross-tenant id is indistinguishable from an
    absent one. Asserted on BOTH new endpoints, because "that account exists,
    but not for you" is a disclosure either of them could make."""
    with tenant_ctx(lonestar):
        premises = make_premises(erin, services_available=["water"])
        unit = make_unit(erin, premises["id"], label="Unit LSR")
        metering_services.assign_unit_plan(
            erin, unit["id"], {"tariff_id": str(_plan(lonestar, service_code="water").id)}
        )
        metering_services.ensure_service_point(unit["id"], "water")
        foreign = customers_services.create_account(
            erin,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-07-01",
            },
        )

    # A VALID body for each endpoint, so the refusal under test is the identity
    # of the account and nothing else.
    for view, body in (
        (customers_api.account_move_out, {"moved_out_on": MOVE_OUT_DAY}),
        (customers_api.account_move_in, _account_payload()),
    ):
        response = _post(view, brazos, "billing_clerk", foreign["id"], body)
        assert response.status_code == 404
        assert response.data["code"] is None  # 404 carries no catalog code (G1/G4)

    with tenant_ctx(lonestar):
        assert customers_models.Account.objects.get(pk=foreign["id"]).closed_at is None


# ══════════════════════════════════════════════════════════════════════════
# The selector the boundary rule reads
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_004_tc1__the_prior_tenancy_lookup_picks_the_latest_closed_one(brazos, marcus):
    """BR-CUS-056 compares against the unit's most recent FINISHED tenancy, so
    the lookup must order by `closed_at` and must ignore a terminal account with
    no date on it — slice 2 could write exactly that state, and treating it as
    "closed on some unknown day" would either block every move-in or none."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        first = _occupant(marcus, brazos, unit, opened_at="2026-05-01", name="First Tenant")
        customers_services.move_out(marcus, first["id"], {"moved_out_on": "2026-06-30"})
        second = customers_services.move_in(
            marcus,
            first["id"],
            _account_payload(opened_at="2026-07-01", contact={"full_name": "Second"}),
        )
        customers_services.move_out(marcus, second["id"], {"moved_out_on": MOVE_OUT_DAY})

        latest = customers_selectors.last_closed_account_for_unit(unit["id"])
        assert latest.account_no == second["account_no"]

        # A terminal row with no `closed_at` is skipped, not guessed at.
        customers_models.Account.objects.filter(pk=second["id"]).update(closed_at=None)
        fallback = customers_selectors.last_closed_account_for_unit(unit["id"])
        assert fallback.account_no == first["account_no"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005@bbed56d (story+rules snapshot — EP-CUS-02 move-out lead story; co-packets US-CUS-004@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-11 by story-coder (W2 customers slice 3 — move-out + move-in)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: the move-in CONCURRENCY half lives in tests/test_us_cus_004_move_in_race.py behind the `isolation` marker (advisory locks are a PostgreSQL feature) · US-CUS-004 TC-1/TC-2/TC-5 (returning-customer link, prior-final read prefill, negative-read exception) and US-CUS-005 TC-1/TC-2/TC-5/TC-8 (committed final reads, the priced preview, the negative-read block, the same-day read handover) are NOT asserted: each needs metering's read-commit path, billing's invoices or BR-CUS-054's customer entity, and none of the three exists · US-CUS-005 TC-6's issued-bill guard is asserted only as the WARNING it produces today — the refusal is written and goes live with billing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
