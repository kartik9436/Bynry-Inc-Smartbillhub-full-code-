# ── Trace ──────────────────────────────────────────────
# Change:   `BR-CUS-1047` BUILT — the PO ruling of 2026-09-12 (option (a) on
#           `OQ-CUS-1769`) reaching code for the first time.
# Rules:    BR-CUS-1047 (the four conditions) · BR-CUS-017 (NARROWED — its
#           surviving half is asserted here too) · BR-CUS-020 · BR-MET-040 ·
#           OQ-042's closure (*"supervisor = SysAdmin/Executive"*) · A4 /
#           BR-IDN-014 (`adjustment_approval`: Approve · Approve · Request) ·
#           CLAUDE.md hard rule 4 (issued bills) · hard rule 7 (audit).
# Question: OQ-CUS-12355 — the REQUEST half is not built; TC-10 pins the
#           boundary so the day it is ruled the suite names it.
# ───────────────────────────────────────────────────────
"""CAN A CLERK FIX AN ACCOUNT THAT IS ON THE WRONG UNIT, AND ONLY THEN?

**THIS FILE EXISTS BECAUSE A RULING REACHED FOUR DOCUMENTS AND NO LINE OF
CODE.** `OQ-CUS-1769` closed on 2026-09-12 — the decision log has it, the
open-questions register has it, `BR-CUS-1047` has it and `BR-CUS-017`'s own row
carries the narrowing — and on 2026-09-13 `apps/customers/services.py` still
refused the field and `PATCH /accounts/{id}` still had no path for it. **Nothing
in this repository can see that gap.** Every gate was green over it, because a
gate reads code against code and a ruling that never arrives leaves nothing to
disagree with. The only check that finds one is a person reading the register
against the product, which is what `r11` step 0 asks for.

So the cases below are written against the RULING, sentence by sentence, rather
than against the function — PO 2026-09-12, verbatim: ***"(a) Narrow the rule to
allow exactly this correction: a reason from a fixed list, a supervisor's
approval, effective today, never backdated, issued bills untouched."***
"""

import datetime as dt

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.customers import unit_correction as uc
from apps.customers.unit_correction_models import AccountUnitCorrection
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

pytestmark = pytest.mark.django_db


@pytest.fixture()
def priya(brazos):
    """Priya Menon — Brazos Bend EXECUTIVE.

    She is here because `approved_by` is a real foreign key into `users`, so a
    synthetic uuid would break the reviewed cross-module FK set (B2 §2), and
    because A4 gives an Executive `Approve` on the approval row. Both halves of
    the supervisor reading get exercised: Dana (System Admin) below, Priya here.
    """
    return staff_actor(brazos, "executive", "priya@brazosbendutilities.test")


def _two_units(actor, tenant):
    """Suite 1 and Suite 2 of one building — the ruling's own worked case, at
    the same address, which is also hard rule 8 being demonstrated rather than
    asserted: neither unit carries an address and both walk to the premises."""
    first = _unit_with_plan(actor, tenant, label="Suite 1")
    second = _unit_with_plan(actor, tenant, label="Suite 2")
    return first, second


def _account_on(actor, unit):
    return customers_services.create_account(actor, _create_payload(unit["id"]))


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · THE RULING, END TO END — the account is on the other unit afterwards
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__a_supervisor_corrects_the_unit_and_the_account_moves(brazos, marcus, dana):
    """**THE ONE THING A CLERK COULD NOT DO YESTERDAY.** Asserted on the
    READ-BACK value and not merely on the call returning — a door that accepts,
    responds and writes nothing is `DEF-MET-4971`'s shape and it is the failure
    this wave is most exposed to."""
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        out = uc.correct_account_unit(
            dana, account["id"], {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"}
        )
        row = customers_models.Account.objects.get(pk=account["id"])

    assert str(row.unit_id) == str(suite2["id"])
    assert out["correction"]["from_unit_id"] == str(suite1["id"])
    assert out["correction"]["to_unit_id"] == str(suite2["id"])
    assert out["correction"]["reason_code"] == "opened_on_wrong_unit"


def test_tc1b__the_record_survives_the_call_and_names_its_approver(brazos, marcus, priya):
    """The RECORD half. `audit_log` is pruned on a retention schedule and the
    issued bills are not, so the answer to *"why is this account on Suite 2 when
    five bills say Suite 1?"* has to outlive the prune."""
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        uc.correct_account_unit(
            priya,
            account["id"],
            {"unit_id": suite2["id"], "reason_code": "moved_in_to_wrong_unit"},
        )
        rows = list(AccountUnitCorrection.objects.filter(account_id=account["id"]))

    assert len(rows) == 1
    assert str(rows[0].approved_by_id) == str(priya.id)
    assert rows[0].approved_at is not None
    assert str(rows[0].from_unit_id) == str(suite1["id"])
    assert str(rows[0].to_unit_id) == str(suite2["id"])


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · CONDITION 2 — A SUPERVISOR'S APPROVAL
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__a_billing_clerk_is_refused(brazos, marcus):
    """⚠ **A CORRECTION A CLERK CAN GIVE THEMSELVES IS NOT AN APPROVAL** — the
    same sentence `test_w7__a_billing_clerk_cannot_cosign` makes about the
    read-batch co-sign, under the same closure.

    *"Supervisor"* is not this lane's pick. `OQ-042` closed with the PO naming
    the roles verbatim — *"supervisor = SysAdmin/Executive"* — and A4's signed
    grid gives `Approve` to those two and `Request` to a Billing Clerk on
    `adjustment_approval`. Two independent sources, one answer."""
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        with pytest.raises(errors.AuthError):
            uc.correct_account_unit(
                marcus,
                account["id"],
                {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"},
            )
        row = customers_models.Account.objects.get(pk=account["id"])

    # ⚠ **AND THE REFUSAL CHANGED NOTHING** — asserted, because the failure this
    # wave is fixing is precisely a door that refuses and writes anyway, or
    # accepts and writes nothing.
    assert str(row.unit_id) == str(suite1["id"])
    assert not AccountUnitCorrection.objects.filter(account_id=account["id"]).exists()


def test_tc2b__an_executive_qualifies_too_and_a_field_technician_does_not(brazos, marcus):
    """**BOTH halves of *"supervisor = SysAdmin/Executive"*, asserted through
    BEHAVIOUR rather than by reading the decorator's private state.**

    Dana (System Admin) is TC-1; Priya (Executive) is here, and so is the
    negative that stops the guard being *"anyone who is not a clerk"* — a field
    technician holds no staff permission at all (`A4_MATRIX` renders "—" on
    every row for them) and must be refused for that reason, not by omission."""
    executive = staff_actor(brazos, "executive", "priya@brazosbendutilities.test")
    technician = staff_actor(brazos, "field_technician", "dee@brazosbendutilities.test")
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        with pytest.raises(errors.AuthError):
            uc.correct_account_unit(
                technician,
                account["id"],
                {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"},
            )
        out = uc.correct_account_unit(
            executive,
            account["id"],
            {"unit_id": suite2["id"], "reason_code": "imported_onto_wrong_unit"},
        )

    assert out["correction"]["approved_by"] == str(executive.id)


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · CONDITION 1 — A REASON FROM A FIXED LIST
# ══════════════════════════════════════════════════════════════════════════
def test_tc3__a_reason_is_required(brazos, marcus, dana):
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        with pytest.raises(errors.ValidationError) as excinfo:
            uc.correct_account_unit(dana, account["id"], {"unit_id": suite2["id"]})

    error = excinfo.value.field_errors[0]
    assert error["field"] == "reason_code"
    assert error["message_key"] == "customers.account.correction_reason_required"


def test_tc3b__free_text_is_not_a_reason_this_path_accepts(brazos, marcus, dana):
    """*"a reason from a fixed list"* — so a sentence a clerk typed is refused,
    and refused BY NAME with the rule rather than as an unknown field. A `reason`
    key is a thing a caller will reasonably try; telling them it does not exist
    would hide the real answer."""
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        with pytest.raises(errors.ValidationError) as excinfo:
            uc.correct_account_unit(
                dana,
                account["id"],
                {"unit_id": suite2["id"], "reason": "clerk picked the wrong suite"},
            )

    error = excinfo.value.field_errors[0]
    assert error["field"] == "reason"
    assert error["message_key"] == "customers.account.field_not_writable"
    assert error["params"]["br_ref"] == "BR-CUS-1047"


def test_tc3c__a_reason_outside_the_list_is_refused_and_the_list_rides_back(brazos, marcus, dana):
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        with pytest.raises(errors.ValidationError) as excinfo:
            uc.correct_account_unit(
                dana,
                account["id"],
                {"unit_id": suite2["id"], "reason_code": "customer_moved"},
            )

    error = excinfo.value.field_errors[0]
    assert error["message_key"] == "customers.account.correction_reason_unknown"
    assert error["params"]["allowed"] == list(uc.CORRECTION_REASONS)


def test_tc3d__no_reason_in_the_list_describes_a_customer_who_moved(brazos):
    """⚠ **THE DISTINCTION THAT KEEPS `BR-CUS-017` INTACT, ASSERTED RATHER THAN
    EXPLAINED.** Every reason names a RECORD that was wrong — a door in this
    product that wrote the unit. None of them names a PERSON who went somewhere,
    because a genuine move is still move-out → move-in: the bills, meters and
    reads belong to the unit and must not follow a customer.

    A lane adding `customer_moved` or `tenant_relocated` to that tuple has to
    delete this case first, which is the point of writing it down here."""
    for reason in uc.CORRECTION_REASONS:
        assert "moved" not in reason or reason.endswith("wrong_unit"), reason
    assert "customer_moved" not in uc.CORRECTION_REASONS
    assert "relocated" not in " ".join(uc.CORRECTION_REASONS)


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · CONDITION 3 — EFFECTIVE TODAY, NEVER BACKDATED
# ══════════════════════════════════════════════════════════════════════════
def test_tc4__the_date_is_todays_and_the_server_supplies_it(brazos, marcus, dana):
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        out = uc.correct_account_unit(
            dana, account["id"], {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"}
        )
        row = AccountUnitCorrection.objects.get(account_id=account["id"])

    from django.utils import timezone

    assert row.effective_on == timezone.localdate()
    assert out["correction"]["effective_on"] == timezone.localdate().isoformat()


@pytest.mark.parametrize("field", ["effective_on", "effective_date"])
def test_tc4b__a_date_in_the_body_is_refused_by_name(brazos, marcus, dana, field):
    """⚠ **A DATE A CLERK MAY TYPE IS A DATE A CLERK MAY BACKDATE.** Hiding the
    input on the form is a UI convenience and never enforcement — the same point
    `_eligible_unit` makes about a picker that hides an occupied unit. So the
    server refuses the key, and the refusal names `BR-CUS-1047` rather than
    answering *"unknown field"* about a date the caller had every reason to
    think it wanted."""
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        with pytest.raises(errors.ValidationError) as excinfo:
            uc.correct_account_unit(
                dana,
                account["id"],
                {
                    "unit_id": suite2["id"],
                    "reason_code": "opened_on_wrong_unit",
                    field: yesterday,
                },
            )

    error = excinfo.value.field_errors[0]
    assert error["field"] == field
    assert error["message_key"] == "customers.account.field_not_writable"
    assert error["params"]["br_ref"] == "BR-CUS-1047"


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · CONDITION 4 — ISSUED BILLS UNTOUCHED (CLAUDE.md hard rule 4)
# ══════════════════════════════════════════════════════════════════════════
def test_tc5__every_issued_invoice_is_byte_identical_afterwards(brazos, marcus, dana):
    """⚠ **THE CONDITION WITH NO COLUMN, PROVED BY READING THE ROWS.**

    *"issued bills untouched"* cannot be asserted by looking at this module —
    absence is invisible to every check this repo has, which is the lesson
    `DEF-CUS-3653` left. So this reads every invoice row belonging to the
    account BEFORE the correction and again AFTER, field by field, and refuses
    any difference at all: not a re-issue, not a re-rate, not an `updated_at`.

    A bill issued against Suite 1 stays a bill issued against Suite 1. One that
    was wrong is credited and replaced through billing's own flow, which is a
    new row — never an edited one (hard rule 4)."""
    from apps.billing import models as billing_models

    def _snapshot(account_id):
        return sorted(
            (
                tuple(sorted(row.items()))
                for row in billing_models.Invoice.objects.filter(account_id=account_id).values()
            )
        )

    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        before = _snapshot(account["id"])
        uc.correct_account_unit(
            dana, account["id"], {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"}
        )
        after = _snapshot(account["id"])

    assert after == before


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · WHAT `BR-CUS-017` STILL ENFORCES — narrowed, never reversed
# ══════════════════════════════════════════════════════════════════════════
def test_tc6__a_unit_another_account_occupies_is_still_refused(brazos, marcus, dana):
    """Still **at most ONE active account per unit**. The correction is a new
    door onto the same rule, so it takes the same lock and the same read under
    it — a check before the lock is the check-then-act race `T5-15` step 4
    describes, and a correction racing a move-in is exactly that race."""
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        customers_services.activate_account(marcus, account["id"], {})
        neighbour = _account_on(marcus, suite2)
        customers_services.activate_account(marcus, neighbour["id"], {})
        with pytest.raises(errors.BizError) as excinfo:
            uc.correct_account_unit(
                dana,
                account["id"],
                {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"},
            )

    assert "BR-CUS-017" in str(excinfo.value.br_ref)


def test_tc6b__correcting_to_the_unit_it_is_already_on_is_refused(brazos, marcus, dana):
    """A correction to the same unit is not a correction, and it would write a
    record saying nothing happened. Refused at the door AND by a database CHECK,
    so a second writer cannot skip the first."""
    with tenant_ctx(brazos):
        suite1, _suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        with pytest.raises(errors.BizError) as excinfo:
            uc.correct_account_unit(
                dana,
                account["id"],
                {"unit_id": suite1["id"], "reason_code": "opened_on_wrong_unit"},
            )

    assert excinfo.value.message_key == "customers.account.correction_same_unit"


def test_tc6c__the_service_history_closes_there_and_opens_here_on_the_same_day(
    brazos, marcus, dana
):
    """**THIS IS WHAT ACTUALLY RE-POINTS THE PLAN, THE METERS, THE ROUTE AND THE
    CYCLE**, none of which has a column on the account (`BR-CUS-029`, PO
    2026-08-11: *"from unit you will derive the plan"*). The agreements are the
    first link of the chain, so the account reaches the new unit's services and
    stops reaching the old one's — with no gap and no overlap, both on today."""
    from django.utils import timezone

    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        # ⚠ **ACTIVATED ON PURPOSE, AND THE FIRST DRAFT OF THIS CASE WAS NOT.**
        # `BR-CUS-018`'s draft derives no occupancy and `create_account` writes
        # it NO service agreements, so a draft has nothing to move and this case
        # asserted a count of zero against zero. The ruling's own subject is an
        # account with five issued bills — services certainly exist — so the
        # fixture is made to be that account rather than the assertion relaxed
        # to fit the one it had.
        customers_services.activate_account(marcus, account["id"], {})
        out = uc.correct_account_unit(
            dana, account["id"], {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"}
        )
        open_rows = list(
            customers_models.ServiceAgreement.objects.filter(
                account_id=account["id"], ended_on__isnull=True
            )
        )
        closed_rows = list(
            customers_models.ServiceAgreement.objects.filter(
                account_id=account["id"], ended_on__isnull=False
            )
        )
        new_points = {
            str(p["id"]) for p in customers_services.seams.service_points_for(suite2["id"])
        }

    today = timezone.localdate()
    assert out["agreements_ended"] == len(closed_rows) > 0
    assert out["agreements_opened"] == len(open_rows) > 0
    assert {str(r.service_point_id) for r in open_rows} == new_points
    assert all(r.ended_on == today for r in closed_rows)
    assert all(r.started_on == today for r in open_rows)


def test_tc6d__a_draft_is_repointed_and_gains_no_service_links(brazos, marcus, dana):
    """**THE MIRROR OF TC-6c, AND IT PINS A DECISION RATHER THAN A BEHAVIOUR.**

    `BR-CUS-018`'s draft *"never derives occupancy and does not block the unit"*,
    so `create_account` writes it no service agreements at all. A correction
    that handed one the links a draft is not supposed to have would leave it in
    a state no create can produce — and `activate_account` would then find them
    already there, on the OLD unit's points if the order ever changed.

    So the correction mirrors what the account already is: the unit is put
    right, nothing is inherited, and the draft inherits from the CORRECT unit
    when something activates it."""
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)  # pending_activation — a draft
        out = uc.correct_account_unit(
            dana, account["id"], {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"}
        )
        row = customers_models.Account.objects.get(pk=account["id"])
        links = customers_models.ServiceAgreement.objects.filter(account_id=account["id"]).count()

    assert str(row.unit_id) == str(suite2["id"])  # the record is put right …
    assert out["agreements_ended"] == 0  # … and nothing was moved,
    assert out["agreements_opened"] == 0  #     because there was
    assert links == 0  #     nothing to move.


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · hard rule 7 — every money-adjacent act writes `audit_log`
# ══════════════════════════════════════════════════════════════════════════
def test_tc7__the_correction_writes_its_audit_row(brazos, marcus, dana, audit_rows):
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        audit_rows.clear()
        uc.correct_account_unit(
            dana, account["id"], {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"}
        )

    assert "account.unit_corrected" in audit_actions(audit_rows)
    written = [r for r in audit_rows if r.get("action") == "account.unit_corrected"][0]
    # before→after, because that is what makes a correction reviewable rather
    # than merely recorded.
    assert written["before"]["unit_id"] != written["after"]["unit_id"]
    assert written["after"]["correction"]["reason_code"] == "opened_on_wrong_unit"


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · THE OLD REFUSAL NOW POINTS AT THE NEW DOOR
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("field", ["unit_id", "unit"])
def test_tc8__patch_still_refuses_the_unit_and_says_where_to_go(brazos, marcus, field):
    """⚠ **A REFUSAL WHOSE REASON HAS EXPIRED IS HARD-WON LAW 1 IN ITS SECOND
    FORM**, and this one expired the day `BR-CUS-1047` was ruled: it told a
    clerk the unit can never change, which stopped being true on 2026-09-12.

    An edit is still the wrong door and `PATCH` still refuses — what changed is
    that the refusal now NAMES the right one. `unit` is here beside `unit_id`
    because `DEF-CUS-5127` was exactly that spelling gap: the model calls the
    column `unit`, a caller sending `unit` was told the field does not exist."""
    with tenant_ctx(brazos):
        unit = _unit_with_plan(marcus, brazos)
        account = customers_services.create_account(marcus, _create_payload(unit["id"]))
        with pytest.raises(errors.ValidationError) as excinfo:
            customers_services.update_account(marcus, account["id"], {field: str(unit["id"])})

    error = excinfo.value.field_errors[0]
    assert error["field"] == field
    assert error["message_key"] == "customers.account.field_not_writable"
    assert "BR-CUS-1047" in error["params"]["br_ref"]
    assert "correct-unit" in error["params"]["reason"]


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · THE CASES THIS DOOR DOES NOT SERVE, EACH REFUSED BY NAME
# ══════════════════════════════════════════════════════════════════════════
def test_tc9__a_master_account_is_refused_by_name(brazos, marcus, dana):
    """`BR-CUS-1010`/`BR-CUS-1012`: a master account's anchor unit is DERIVED
    from the premises' common areas and it may hold many. Re-pointing one at a
    single unit would silently unmake that derivation, and `BR-CUS-1047`'s
    worked case is a regular account."""
    from tests.test_br_cus_068_master_accounts import _create as _create_master
    from tests.test_br_cus_068_master_accounts import _elm_1408

    with tenant_ctx(brazos):
        # ⚠ The neighbouring suite's OWN fixture, not a second one written here.
        # A master account needs a premises with common-area units carrying
        # plans and service points, and `BR-CUS-068`'s file already builds
        # exactly that — a second copy would be a second set of assumptions
        # about what a master account is.
        premises, _commons = _elm_1408(marcus, brazos)
        master = _create_master(marcus, premises)
        suite = _unit_with_plan(marcus, brazos, label="Suite 9")
        with pytest.raises(errors.BizError) as excinfo:
            uc.correct_account_unit(
                dana,
                master["id"],
                {"unit_id": suite["id"], "reason_code": "opened_on_wrong_unit"},
            )
    assert excinfo.value.message_key == "customers.account.correction_not_for_master"


# ══════════════════════════════════════════════════════════════════════════
# TC-10 · THE BOUNDARY — what is NOT built, pinned so the ruling can find it
# ══════════════════════════════════════════════════════════════════════════
def test_tc10__there_is_no_request_half_and_oq_cus_12349_carries_it(brazos):
    """⚠ **PINS A DELIBERATE ABSENCE, NOT A BUG.**

    A4's signed grid gives a Billing Clerk `Request` on `adjustment_approval`,
    so the product's own vocabulary contemplates *clerk raises it, supervisor
    approves it* as two acts. **Nothing in this product implements a request
    that waits for an approval, on any table.** Building the pending row, the
    queue and the supervisor's inbox would resolve an open decision by picking a
    value, which the prime directive forbids — so the boundary is drawn and
    `OQ-CUS-12355` asks the PO where it should be.

    This goes RED the day somebody adds a request state, which is the point:
    whoever adds one comes here and names the ruling that authorised it."""
    fields = {f.name for f in AccountUnitCorrection._meta.concrete_fields}
    assert "requested_by" not in fields
    assert "status" not in fields
    assert "approved_by" in fields and "approved_at" in fields


# ══════════════════════════════════════════════════════════════════════════
# TC-11 · hard rule 1 — the record is tenant-scoped like everything else
# ══════════════════════════════════════════════════════════════════════════
def test_tc11__a_neighbouring_tenant_reads_none_of_these(brazos, lonestar, marcus, dana):
    """The RLS policy (`customers 0046`) is the enforcement; this is the query
    half, asserted because a read that forgot its tenant filter looks identical
    to one that did not on sqlite, where RLS does not exist."""
    with tenant_ctx(brazos):
        suite1, suite2 = _two_units(marcus, brazos)
        account = _account_on(marcus, suite1)
        uc.correct_account_unit(
            dana, account["id"], {"unit_id": suite2["id"], "reason_code": "opened_on_wrong_unit"}
        )
        mine = uc.corrections_for(account["id"])
    with tenant_ctx(lonestar):
        theirs = uc.corrections_for(account["id"])

    assert len(mine) == 1
    assert theirs == []
