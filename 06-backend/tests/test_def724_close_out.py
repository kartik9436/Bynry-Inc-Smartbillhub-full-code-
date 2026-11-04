# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (the only story that owns any part of an account's
#           terminal path — it owns the MOVE-OUT wizard, S20). ⚠ **NO STORY
#           OWNS THE CLOSE-OUT**; one is OWED (hard-won law 8) and is reported
#           rather than invented.
#           Screens: S21/S22 · S90
# Change:   DEF-724 — *"A disconnected customer can never be closed - Add a
#           separate close-out act — Cleaner in the record"* (PO 2026-08-27).
# Rules:    **BR-CUS-430** (a SEPARATE act; the two doors are disjoint in both
#           directions) · **BR-CUS-431** (`accounts.closed_at` takes the CUT
#           date, never the day the clerk clicked) · BR-CUS-110 (a cut ENDS
#           OCCUPANCY — the ruling that made move-out a dead end) · BR-CUS-056
#           (the boundary day) · BR-CUS-103 (base stops at the cut) ·
#           BR-CUS-082 (a debt surviving closure is chased, ladder restarts at
#           TIER 1, collections and never service) · BR-CUS-097 (the tie-back
#           is CLERK-INITIATED, in the S20 wizard — not here) · BR-CUS-107 (the
#           `Disconnected` status) · BR-CUS-030 (move-out) · BR-CUS-055 (the
#           behaviour CLASS decides, never the label) · BR-TEN-043 (the event
#           date is an argument) · CLAUDE.md rule 4 (corrections are new rows) ·
#           rule 7 (audit)
# ───────────────────────────────────────────────────────
"""DEF-724 — the close-out act, and the refusal it exists to answer.

**READ `test_red__the_only_terminal_door_refuses_a_cut_customer` FIRST.** It is
the defect, reproduced, and it is deliberately written so that it FAILS the day
somebody "fixes" DEF-724 by relaxing `move_out`'s occupancy check — which is the
one fix the PO ruled out, because it would file a disconnection as a move-out in
a permanent record and *"to a regulator those are not the same event"*.

⚠ **THREE ASSERTIONS HERE ARE DELIBERATELY NEGATIVE AND MUST STAY THAT WAY.**

  1. `test_a_close_out_refuses_an_occupant` — the SECOND half of BR-CUS-430,
     and the half a later lane will be tempted to delete because it looks like
     an unnecessary restriction on a working door. It is not: an occupant
     leaving IS a move-out, and letting them through here would file a
     departure as a disconnection — the same falsification pointing the other
     way. A door that accepts everybody is `move_out` with a longer name.
  2. `test_no_move_record_is_written_by_a_close_out` — `moves.KINDS` stays at
     two. Writing a `kind="move_out"` row would be the exact thing BR-CUS-430
     forbids, done by the module built to avoid it.
  3. `test_billing_still_refuses_a_non_billable_account` — DEF-701's SECOND
     blocker, asserted as still standing. This close-out unblocks the first
     (a cut customer now has a terminal path) and NOT the second, and a test
     that quietly assumed both were gone would let a lane assign the
     `Disconnected` status and drop a whole account from the bill run.
"""

from datetime import date
from decimal import Decimal as D
from uuid import uuid4

import pytest

from apps.customers import close_out as close_out_service
from apps.customers import disconnects, moves
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_w7_cut_reconnect import CUT_ON, TODAY, _scheduled
from tests.test_w7_disconnects import _owes

pytestmark = pytest.mark.django_db

#: `A-11488`, the account BR-CUS-110, DEF-724 and OQ-386 were all put with:
#: cut **2026-08-18** owing **$612.75**, 12 Foundry Row already re-let.
#: The fixture cuts on `CUT_ON` (2026-08-24) because that is the date the W7
#: ladder fixture walks to lawfully; the FIGURE is the ruling's.
OWED = D("612.75")

#: The close-out happens weeks after the cut. The GAP is the whole point of
#: BR-CUS-431 — with `closed_out_on == cut_on` every wrong answer looks right.
CLOSED_OUT_ON = date(2026, 9, 30)


@pytest.fixture(autouse=True)
def _premises_get_an_owner(monkeypatch):
    """BR-MET-401 / DEF-650, IN FLIGHT ON THIS TREE (measured 2026-08-27).

    `metering.services.create_premises` now REFUSES a payload with no typed
    owner (`metering.premises.owner_required`) and the shared W1 helper
    `make_premises` still supplies only the free-text `owner_manager`, so the
    whole W7 suite is red on this tree before this file adds a line —
    `tests/test_w7_cut_reconnect.py::test_a_cut_is_recorded_once` fails the same
    way. **That is another lane's change and its helper to fix**; editing a
    helper six suites share while its owning lane is mid-change is exactly the
    shared-tree collision CLAUDE.md law 11 is about, so this file supplies the
    owner for its own premises instead and REPORTS the breakage rather than
    reaching into it.

    `owner_id` is accepted on BOTH sides of that change (it is in `HEAD`'s
    `create_premises` too), so this fixture is correct whether the mandatory
    rule lands, is reverted, or is still in flight.
    """
    import tests.test_w7_disconnects as w7
    from apps.metering import premises_owners

    original = w7.make_premises

    def with_owner(actor, **overrides):
        if "owner_id" not in overrides:
            try:
                owner = premises_owners.create_premises_owner(
                    actor,
                    {"name": f"Foundry Row Holdings {uuid4().hex[:10]}", "category": "landlord"},
                )
                overrides["owner_id"] = str(owner["id"])
            except Exception:  # pragma: no cover - the pre-DEF-650 world
                pass
        return original(actor, **overrides)

    monkeypatch.setattr(w7, "make_premises", with_owner)


@pytest.fixture(autouse=True)
def _fee_seam_answers(monkeypatch):
    """DEF-708's fee posting, stubbed AT THE MODULE BOUNDARY — and this is not a
    convenience.

    `commit_cut` raises the reconnection fee through
    `seams.raise_and_issue_charge_fee`, which is BILLING's service
    (BR-CUS-037 — customers writes no financial table and asks the owning module
    instead). A customers test may not depend on billing's internals, and
    `_owes` above stubs `seams.ar_positions` in exactly the same place for
    exactly the same reason.

    ⚠ **IT IS ALSO BROKEN ON THIS TREE RIGHT NOW, BY ANOTHER LANE, AND THAT IS
    REPORTED RATHER THAN REACHED INTO.** Measured 2026-08-27:
    `apps/billing/fee_bill.py` is staged-but-uncommitted and calls
    `issue.issue_invoice()` without its three required keyword arguments —
    `issued_at`, `template_id`, `template_version` — so EVERY `commit_cut` on
    this tree raises `TypeError` before it reaches any customers code. That is
    the DEF-708 lane's fix to make, not this one's.
    """
    monkeypatch.setattr(
        disconnects.seams,
        "raise_and_issue_charge_fee",
        lambda *_a, **_k: {"invoice_id": None, "stubbed_at": "the customers/billing seam"},
    )


def _cut(actor, tenant, monkeypatch, *, owed=OWED, label="Unit A"):
    """A really-cut account: the W7 ladder walked, then `commit_cut`."""
    account = _scheduled(actor, tenant, monkeypatch, owed=owed, label=label)
    disconnects.commit_cut(actor, account["id"], cut_on=CUT_ON, as_of=TODAY)
    return account


def _row(account_id):
    return customers_models.Account.objects.get(id=account_id)


def _make_it_disconnected(account_id):
    """Assign BR-CUS-107's seeded `Disconnected` status.

    ⚠ **NOTHING IN THE PRODUCT DOES THIS YET** and this test file is not asking
    for it to: DEF-701's billing half is still open (see
    `test_billing_still_refuses_a_non_billable_account`). It is done HERE
    because BR-CUS-110's world — *a cut ends occupancy* — is the world DEF-724
    was filed about, and reproducing the defect means standing in it.
    """
    row = _row(account_id)
    row.status = customers_models.AccountStatus.objects.get(
        tenant_id=row.tenant_id, code="disconnected"
    )
    row.save(update_fields=["status", "updated_at"])
    return row


# ════════════════════════════════════════════════════════════════════════════
# THE DEFECT, REPRODUCED
# ════════════════════════════════════════════════════════════════════════════
def test_red__the_only_terminal_door_refuses_a_cut_customer(brazos, marcus, monkeypatch):
    """DEF-724, in one call. **This must never be "fixed" by relaxing it.**

    `move_out` refusing a non-occupant is CORRECT at every line — what changed
    is the set of accounts that reach it (BR-CUS-110). The close-out is a
    second door; this refusal stays exactly as it is.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        with pytest.raises(errors.BizError) as caught:
            customers_services.move_out(
                marcus, account["id"], {"moved_out_on": CLOSED_OUT_ON.isoformat()}
            )
    assert caught.value.message_key == "customers.account.not_an_occupant"
    assert caught.value.params["behavior_class"] == customers_services.CLASS_NON_BILLABLE
    assert _row(account["id"]).closed_at is None


def test_the_close_out_finishes_what_move_out_cannot(brazos, marcus, monkeypatch, audit_rows):
    """BR-CUS-430 — the same account, through the door the PO ruled."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        assert close_out_service.eligibility(account["id"])["eligible"] is True
        result = close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "settled and gone"},
        )
        row = _row(account["id"])
    assert row.status.behavior_class == customers_services.CLASS_TERMINAL
    assert row.closed_at is not None
    assert result["close_out"]["reason"] == "settled and gone"
    # BR-CUS-430 — a DIFFERENT event from a move-out, in the permanent record.
    actions = audit_actions(audit_rows)
    assert close_out_service.AUDIT_CLOSED_OUT in actions
    assert "account.closed" not in actions


# ════════════════════════════════════════════════════════════════════════════
# BR-CUS-431 — THE DATE, AND THE 43 DAYS IT COSTS TO GET IT WRONG
# ════════════════════════════════════════════════════════════════════════════
def test_closed_at_is_the_cut_date_and_never_the_day_the_clerk_clicked(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        preview = close_out_service.eligibility(account["id"])
        # Shown BEFORE it is written, because it is the one thing on this
        # screen that no correction row can un-say.
        assert preview["closed_at_will_be"] == CUT_ON.isoformat()
        close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "written off"},
        )
        row = _row(account["id"])
        # TWO cases now, and that is the design: the SERVICE case is closed out
        # and BR-CUS-082's COLLECTIONS case opens beside it for the $612.75
        # that survived. `CLOSED_CASE_STATES` is what lets them coexist under
        # `uq_one_open_disconnect_case_per_account`.
        case = disconnects.DisconnectCase.objects.get(
            account_id=account["id"], state=disconnects.STATE_CLOSED_OUT
        )
    assert row.closed_at == CUT_ON
    assert row.closed_at != CLOSED_OUT_ON
    # The act's own date is NOT lost — it is recorded where it is true.
    assert case.closed_out_on == CLOSED_OUT_ON
    assert case.state == disconnects.STATE_CLOSED_OUT
    assert case.cut_on == CUT_ON


def test_the_boundary_day_lets_the_next_occupant_start_the_day_after_the_cut(
    brazos, marcus, monkeypatch
):
    """BR-CUS-056 + BR-CUS-110 — the measured consequence BR-CUS-431 is derived
    from, and the only thing that makes the date question answerable rather than
    a preference.

    `selectors.last_closed_account_for_unit` takes the greatest `closed_at` on
    the unit and `_refuse_if_start_lands_on_the_prior_move_day` refuses any
    start on or before it. With the CLOSE-OUT date written instead, every day
    from the cut to the close-out is refused for a unit the utility was
    entitled to re-let the whole time.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "gone"},
        )
        unit_id = _row(account["id"]).unit_id
        # The day AFTER the cut, which BR-CUS-110 grants.
        incoming = customers_services.create_account(
            marcus,
            {
                "unit_id": str(unit_id),
                "account_type": "residential",
                "status": "active",
                "opened_at": (CUT_ON.replace(day=CUT_ON.day + 1)).isoformat(),
                "contact": {"full_name": "The next occupant"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "The next occupant", account_type="residential"
                ),
            },
        )
    assert incoming["id"]


# ════════════════════════════════════════════════════════════════════════════
# THE TWO DOORS ARE DISJOINT IN BOTH DIRECTIONS
# ════════════════════════════════════════════════════════════════════════════
def test_a_close_out_refuses_an_occupant(brazos, marcus, monkeypatch):
    """BR-CUS-430's second half. **DO NOT DELETE THIS TO MAKE A FLOW EASIER.**

    An occupant leaving is a MOVE-OUT. Filing it here would put a departure
    into the record as a disconnection — the same falsification the ruling
    forbids, pointing the other way.
    """
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)  # still `marked_disconnect` = billable
        assert customers_services.is_occupying(_row(account["id"]).status) is True
        with pytest.raises(errors.BizError) as caught:
            close_out_service.close_out(
                marcus,
                account["id"],
                {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "no"},
            )
    assert caught.value.message_key == "customers.account.close_out_still_occupying"
    assert _row(account["id"]).closed_at is None


def test_a_close_out_refuses_an_account_that_was_never_cut(brazos, marcus, monkeypatch):
    """No cut means no cut DATE, and BR-CUS-431 has nothing to write."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("0"))
        account = _scheduled(marcus, brazos, monkeypatch, owed=OWED)
        _make_it_disconnected(account["id"])  # non-occupying, but never cut
        answer = close_out_service.eligibility(account["id"])
        with pytest.raises(errors.BizError) as caught:
            close_out_service.close_out(
                marcus,
                account["id"],
                {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "x"},
            )
    assert answer["eligible"] is False
    assert answer["blocked_by"]["code"] == "not_a_cut_account"
    assert caught.value.message_key == "customers.account.close_out_not_a_cut_account"


def test_a_second_close_out_is_refused(brazos, marcus, monkeypatch):
    """CLAUDE.md hard rule 4 — correcting a close-out is a NEW row, never a
    second one written over the first."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        payload = {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "settled"}
        close_out_service.close_out(marcus, account["id"], payload)
        with pytest.raises(errors.BizError) as caught:
            close_out_service.close_out(marcus, account["id"], payload)
    assert caught.value.message_key == "customers.account.close_out_already_terminal"


def test_the_act_cannot_predate_the_cut_it_closes(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        with pytest.raises(errors.BizError) as caught:
            close_out_service.close_out(
                marcus,
                account["id"],
                {"closed_out_on": "2026-08-01", "reason": "backdated"},
            )
    assert caught.value.message_key == "customers.account.close_out_before_cut"


# ════════════════════════════════════════════════════════════════════════════
# THE BALANCE — BR-CUS-082, CONSUMED AND NOT RESTATED
# ════════════════════════════════════════════════════════════════════════════
def test_a_surviving_debt_restarts_the_ladder_at_tier_1_as_collections(brazos, marcus, monkeypatch):
    """BR-CUS-082, on its own worked shape: the account closes owing **$612.75**
    and TIER 1 fires — as a COLLECTIONS sequence, which
    `ck_collections_sequence_never_cuts` makes uncuttable in the database as
    well as in Python."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        result = close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "written off"},
        )
        collections = disconnects.DisconnectCase.objects.filter(
            account_id=account["id"], sequence=disconnects.SEQ_COLLECTIONS
        )
    assert result["balance_at_close_out"]["display"] == "612.75"
    assert result["dunning"]["restarts_at_tier"] == 1
    assert result["dunning"]["escalates_to_disconnection"] is False
    assert collections.count() == 1
    row = collections.get()
    assert row.tier == disconnects.TIER_1
    assert row.cut_on is None and row.cut_scheduled_for is None
    # BR-CUS-097 as qualified: no clerk tied anything back here, so the ladder
    # runs against THIS account and no landlord gets a letter.
    assert any(w["code"] == "close_out_shortfall_not_tied_back" for w in result["warnings"])


def test_an_account_closing_owing_nothing_starts_no_ladder(brazos, marcus, monkeypatch):
    """BR-CUS-030's `dunning stops` survives unchanged for the ordinary case;
    BR-CUS-082 supersedes it ONLY for the closed-with-balance one, and reading
    it wider would start a ladder against a settled customer."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        _owes(monkeypatch, D("0"))
        result = close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "settled in full"},
        )
        collections = disconnects.DisconnectCase.objects.filter(
            account_id=account["id"], sequence=disconnects.SEQ_COLLECTIONS
        )
    assert result["dunning"]["will_restart"] is False
    assert collections.count() == 0


def test_an_unreadable_balance_is_never_reported_as_zero(brazos, marcus, monkeypatch):
    """DEF-628's shape. A fabricated $0.00 on an account in arrears would stop a
    ladder BR-CUS-082 requires, and the screen would show a settled customer."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        _owes(monkeypatch, None, available=False)
        answer = close_out_service.eligibility(account["id"])
    assert answer["balance"] is None
    assert answer["balance_unreadable"] is True
    assert answer["dunning_if_closed"]["will_restart"] is None


# ════════════════════════════════════════════════════════════════════════════
# WHAT IT WRITES, AND WHAT IT MUST NOT
# ════════════════════════════════════════════════════════════════════════════
def test_service_agreements_end_on_the_cut_date_too(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "gone"},
        )
        ended = customers_models.ServiceAgreement.objects.filter(account_id=account["id"])
    assert ended.count() > 0
    assert {row.ended_on for row in ended} == {CUT_ON}


def test_no_move_record_is_written_by_a_close_out(brazos, marcus, monkeypatch):
    """**NEGATIVE ON PURPOSE.** A close-out is not a move. `moves.KINDS` stays
    at two, and a `kind="move_out"` row here would be the falsification
    BR-CUS-430 forbids, written by the module built to avoid it."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        close_out_service.close_out(
            marcus,
            account["id"],
            {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "gone"},
        )
        records = moves.MoveRecord.objects.filter(account_id=account["id"])
    assert records.count() == 0
    assert moves.KINDS == (moves.KIND_MOVE_IN, moves.KIND_MOVE_OUT)


def test_the_reason_is_required_and_is_free_text_pending_oq_830(brazos, marcus, monkeypatch):
    """OQ-830 — a REQUIRED sentence, and no fixed list. Nothing is stubbed,
    because a stub would break the act the PO ruled; what is missing is the
    ability to COUNT closures by reason, and that is asked, not guessed."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        with pytest.raises(errors.ValidationError) as caught:
            close_out_service.close_out(
                marcus, account["id"], {"closed_out_on": CLOSED_OUT_ON.isoformat()}
            )
    assert caught.value.message_key == "customers.account.close_out_reason_required"
    assert close_out_service.REASON_VOCABULARY_UNRULED["tracks"] == "OQ-830"


def test_a_closed_at_cannot_be_supplied_by_the_caller(brazos, marcus, monkeypatch):
    """BR-CUS-431 is DERIVED, so it is not offered as a field. A payload that
    could name the date would be a payload that could get it wrong."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        with pytest.raises(errors.ValidationError):
            close_out_service.close_out(
                marcus,
                account["id"],
                {
                    "closed_out_on": CLOSED_OUT_ON.isoformat(),
                    "reason": "x",
                    "closed_at": "2026-09-30",
                },
            )


# ════════════════════════════════════════════════════════════════════════════
# THE BOUNDARIES THIS LANE DID NOT CROSS
# ════════════════════════════════════════════════════════════════════════════
def test_billing_still_refuses_a_non_billable_account(brazos):
    """**NEGATIVE ON PURPOSE — DEF-701's SECOND blocker, still standing.**

    Re-measured on this tree 2026-08-27 rather than taken from the defect row.
    This close-out unblocks the FIRST blocker (a cut customer now has a terminal
    path) and not this one. Assigning BR-CUS-107's `Disconnected` status before
    billing is fixed would drop the WHOLE account from the run, so the usage
    consumed BEFORE the cut would never be billed — trading a wrong LABEL for a
    wrong BILL.

    ⚠ **CORRECTED 2026-08-30 (CR-052 W0, `DEF-2640`) — THE FIRST ASSERTION IS
    POINTED AT THE WRONG CONSTANT AND CANNOT GO RED FOR WHAT IT GATES.** This
    case's own docstring said *"when this test goes RED, DEF-701 is ready to
    close"*, and `CLASSES_THAT_BILL` is not what drops the account: it never
    reaches billing's stage 1. `billing.runs.prepare_run` scopes a run through
    **`customers.selectors.accounts_for_bill_run`**, which filters on
    `services.OCCUPYING_BEHAVIOR_CLASSES` — customers' own constant — so a lane
    could widen `CLASSES_THAT_BILL`, watch this case turn red, assign the status
    and STILL drop the account from every run. The original assertion is KEPT
    (billing's refusal is a real second wall) and the one that actually gates it
    is added beside it. The behavioural proof, on a really-cut account rather
    than on a constant, is
    `tests/test_cr052_w0_disconnected_at_the_cut.py::
    test_the_blocker_is_customers_own_scope_seam_not_billings_stage`.
    """
    from apps.billing.stages import resolve_subscription

    assert customers_services.CLASS_NON_BILLABLE not in resolve_subscription.CLASSES_THAT_BILL
    # The gate that actually fires, one module earlier — and it is ours.
    assert (
        customers_services.CLASS_NON_BILLABLE not in customers_services.OCCUPYING_BEHAVIOR_CLASSES
    )


def test_the_close_out_performs_no_clearance_and_says_so(brazos, marcus, monkeypatch):
    """OQ-680 / DEF-744 — OPEN, and this act must not imply a clearance it did
    not perform. Refusing on a blocker nobody ruled would give the product a
    dead end with no way past it, which is DEF-724's own failure one flow
    over."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
        answer = close_out_service.eligibility(account["id"])
    stated = {entry["code"]: entry for entry in answer["absences"]}
    assert stated["close_out_clearance_not_performed"]["tracks"] == "OQ-680"


def test_another_tenants_account_cannot_be_closed_out(brazos, lonestar, marcus, erin, monkeypatch):
    """CLAUDE.md rule 1 — RLS FORCE, and no cross-tenant queryset."""
    with tenant_ctx(brazos):
        account = _cut(marcus, brazos, monkeypatch)
        _make_it_disconnected(account["id"])
    with tenant_ctx(lonestar):
        with pytest.raises(Exception):
            close_out_service.close_out(
                erin,
                account["id"],
                {"closed_out_on": CLOSED_OUT_ON.isoformat(), "reason": "x"},
            )
    with tenant_ctx(brazos):
        assert _row(account["id"]).closed_at is None
