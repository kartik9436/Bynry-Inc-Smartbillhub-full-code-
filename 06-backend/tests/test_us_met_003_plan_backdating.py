# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (S16 default-plan panel — the plan-assignment path) ·
#           US-CUS-005 (the move-out guard whose shape this reuses)
#           Screens: S16 · S21 · S23
# Rules:    BR-BIL-004 (issued invoices are immutable; corrections are new
#           rows) · BR-MET-042 (a plan edit staff are allowed to make is
#           allowed WITH warning + audit) · BR-CUS-011 (history rows carry
#           who/when/from→to/reason/source) · BR-CUS-013 (plan_version is
#           SNAPSHOT at assignment) · BR-MET-041 (bulk writes a row per unit)
# Ruling:   PO 2026-08-11 — "backdating a plan change behind an issued bill:
#           option B, WARN AND ALLOW with a reason recorded."
# ───────────────────────────────────────────────────────
"""Backdating a plan change behind a bill that already went out.

THE CASE, in the PO's own figures. A unit's plan is changed effective **1
June**. June's bill went out on the **5th**, priced on the old plan. Nothing in
the product stopped that, and afterwards the records and the bill disagree:
the history says the unit was on plan B from 1 June, the issued invoice says it
was priced on plan A for the same days.

THE RULING (PO, 2026-08-11) was option **B** of three — block / warn-and-allow /
allow silently. Staff may proceed, and the justification is EVIDENCE. Same
shape as a late-fee waiver: the act is permitted, the record has to say who
decided and why.

So these tests pin three different things, and the middle one is the one that
is easy to get wrong:

  * TC-8  — behind an issued bill WITH a reason: the write lands, a warning
            comes back naming the bill, and the reason is on the row.
  * TC-9  — behind an issued bill with NO reason: refused, nothing written.
  * TC-10 — an ORDINARY forward-dated change: untouched. No warning, no reason
            demanded. An earlier draft of this writer refused ordinary flows
            and its own tests caught it in a minute; a version that demanded a
            reason from every caller would be the same mistake wearing a
            different hat.
  * TC-11 — the last BILLED DAY is itself behind. A change effective on the
            final day of an issued period reprices a day that was billed.
  * TC-12 — when billing publishes no such read, the response SAYS the check
            could not run. Silence would read as "the check passed".
  * TC-13 — a refused unit inside a BULK run moves nothing. Bulk catches
            per-unit failures and carries on, and `_apply_unit_plan` writes the
            unit's plan column before the history row, so without a per-unit
            savepoint a refusal left the column moved with no coverage behind
            it — the exact hole the gap-1 lane closed for the single path.
"""

from datetime import UTC, date, datetime

import pytest

from apps.metering import models as metering_models
from apps.metering import services
from apps.rating import models as rating_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx
from tests.test_w3_billing_models import a_draft, an_account

pytestmark = pytest.mark.django_db

#: The PO's figures, verbatim. June's bill, issued on the 5th, covering June.
JUNE_START = date(2026, 6, 1)
JUNE_END = date(2026, 6, 30)
ISSUED_ON = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
INVOICE_NO = "BL-2606-0001"


def history_for(unit_id):
    return list(
        rating_models.UnitPlanAssignment.objects.filter(unit_id=unit_id).order_by(
            "assigned_from", "created_at"
        )
    )


def a_billed_unit(actor, tenant, *, account_no="A-10432"):
    """An account whose June bill has been ISSUED — the world the ruling is about."""
    account = an_account(actor, tenant, account_no=account_no)
    a_draft(
        tenant,
        account,
        status="issued",
        invoice_no=INVOICE_NO,
        issued_at=ISSUED_ON,
        period_start=JUNE_START,
        period_end=JUNE_END,
        service_date=JUNE_END,
    )
    return account


def test_us_met_003_tc8__backdating_behind_an_issued_bill_is_allowed_with_a_reason(
    brazos, dana, audit_rows
):
    """PO 2026-08-11, option B: allowed, warned, and the reason recorded.

    Effective 1 June against a June bill issued on the 5th — the exact example
    put to the PO. The write lands (option A, block, was NOT chosen), the
    caller is told which bill it now disagrees with, and the reason is on the
    history row where a later reader of that row will find it.
    """
    with tenant_ctx(brazos):
        account = a_billed_unit(dana, brazos)
        plan = make_plan(brazos, name="Senior")

        result = services.assign_unit_plan(
            dana,
            str(account.unit_id),
            {
                "tariff_id": str(plan.id),
                "effective_from": "2026-06-01",
                "reason": "customer qualified for the senior rate on 1 June",
            },
        )

        warning = result["history"]["warning"]
        assert warning is not None
        assert warning["code"] == "plan_change_backdated_behind_issued_bill"
        assert warning["billed_through"] == "2026-06-30"
        assert warning["invoice_no"] == INVOICE_NO
        assert warning["assigned_from"] == "2026-06-01"
        # The caller sees it too — a warning nobody is handed is not surfaced.
        assert any(
            entry["code"] == "plan_change_backdated_behind_issued_bill"
            for entry in result["warnings"]
        )

        rows = history_for(account.unit_id)
        assert len(rows) == 1
        assert rows[0].assigned_from == JUNE_START
        assert rows[0].reason == "customer qualified for the senior rate on 1 June"

        # The other half of "recorded": an audit row that NAMES THE BILL. The
        # history row cannot — it has no column for an invoice — so the two
        # records carry different halves of the same decision.
        backdated = [row for row in audit_rows if row["action"] == "unit_plan_assignment.backdated"]
        assert len(backdated) == 1
        assert backdated[0]["after"]["invoice_no"] == INVOICE_NO
        assert backdated[0]["after"]["billed_through"] == "2026-06-30"
        assert backdated[0]["after"]["reason"] == "customer qualified for the senior rate on 1 June"
        assert str(backdated[0]["actor_user_id"]) == str(dana.id)


def test_us_met_003_tc9__backdating_with_no_reason_is_refused(brazos, dana):
    """The justification IS the ruling. Without it there is no option B —
    only option C, allow silently, which the PO did not choose."""
    with tenant_ctx(brazos):
        account = a_billed_unit(dana, brazos)
        plan = make_plan(brazos, name="Senior")

        with pytest.raises(errors.ValidationError) as raised:
            services.assign_unit_plan(
                dana,
                str(account.unit_id),
                {"tariff_id": str(plan.id), "effective_from": "2026-06-01"},
            )

        assert raised.value.code == errors.VAL_REQUIRED
        assert [error["field"] for error in raised.value.field_errors] == ["reason"]
        assert history_for(account.unit_id) == []  # refused BEFORE anything is written
        # …and the unit's plan column did not move either. The two travel
        # together or neither does — a moved column with no coverage row is the
        # hole that only shows up months later, inside a bill.
        assert metering_models.Unit.objects.get(pk=account.unit_id).rate_plan_id is None


def test_us_met_003_tc10__a_forward_dated_change_needs_no_reason(brazos, dana):
    """The ordinary flow must not have moved. 1 July is after the last billed
    day, so nothing already sent is contradicted and nothing is demanded."""
    with tenant_ctx(brazos):
        account = a_billed_unit(dana, brazos)
        plan = make_plan(brazos, name="Senior")

        result = services.assign_unit_plan(
            dana,
            str(account.unit_id),
            {"tariff_id": str(plan.id), "effective_from": "2026-07-01"},
        )

        assert result["history"]["warning"] is None
        rows = history_for(account.unit_id)
        assert len(rows) == 1 and rows[0].assigned_from == date(2026, 7, 1)


def test_us_met_003_tc11__the_last_billed_day_is_itself_behind(brazos, dana):
    """30 June was priced by the issued bill. A plan starting that day changes
    what a billed day should have cost, so it is backdating like any other."""
    with tenant_ctx(brazos):
        account = a_billed_unit(dana, brazos)
        plan = make_plan(brazos, name="Senior")

        with pytest.raises(errors.ValidationError):
            services.assign_unit_plan(
                dana,
                str(account.unit_id),
                {"tariff_id": str(plan.id), "effective_from": "2026-06-30"},
            )


def test_us_met_003_tc12__an_unwired_billing_read_is_reported_not_assumed_clean(
    brazos, dana, monkeypatch
):
    """Hard-won law 1. If the question cannot be asked, say so — a silent pass
    is a claim that the bill and the records agree, which nobody checked."""
    from apps.rating import seams as rating_seams

    monkeypatch.setattr(
        rating_seams, "last_issued_bill_for_unit", lambda unit_id: {"wired": False, "bill": None}
    )

    with tenant_ctx(brazos):
        account = a_billed_unit(dana, brazos)
        plan = make_plan(brazos, name="Senior")

        result = services.assign_unit_plan(
            dana,
            str(account.unit_id),
            {"tariff_id": str(plan.id), "effective_from": "2026-06-01"},
        )

        warning = result["history"]["warning"]
        assert warning["code"] == "plan_backdating_not_checked_against_issued_bills"
        # Allowed, because an unaskable question is not a refusal — but never
        # silently: no reason was demanded and the response says why.
        assert len(history_for(account.unit_id)) == 1


def test_us_met_003_tc13__a_refused_unit_in_a_bulk_run_moves_nothing(brazos, dana):
    """BR-MET-041 bulk, and the property the gap-1 lane fought for.

    `_apply_unit_plan` writes `units.rate_plan_id` before it writes the history
    row. Bulk catches per-unit failures and carries on, so without a per-unit
    savepoint the refused unit kept a moved plan column with no coverage row
    behind it — the single-unit path never had that hole, because its exception
    escapes its transaction. One unit here is backdated with no reason; it must
    fail whole, and the other unit must still be assigned.
    """
    with tenant_ctx(brazos):
        billed = a_billed_unit(dana, brazos, account_no="A-10432")
        clean = an_account(dana, brazos, account_no="A-10433")
        plan = make_plan(brazos, name="Senior")

        result = services.bulk_assign_unit_plans(
            dana,
            {
                "unit_ids": [str(billed.unit_id), str(clean.unit_id)],
                "tariff_id": str(plan.id),
                "effective_from": "2026-06-01",
            },
        )

        assert (result["assigned"], result["failed"]) == (1, 1)
        assert history_for(billed.unit_id) == []
        assert metering_models.Unit.objects.get(pk=billed.unit_id).rate_plan_id is None
        # The unit with no issued bill is untouched by its neighbour's refusal.
        assert len(history_for(clean.unit_id)) == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-003@d76f5b4 (EP-MET-01 — PO ruling 2026-08-11 item 7,
#         "backdating a plan change behind an issued bill → option B")
# generated: 2026-08-11 by story-coder (rating plan-assignment backdating lane)
# checklist: A✔ B✔ C✔ D=deferred(service-layer — the API inherits it) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED proved before green, twice, quoted verbatim.
#         (1) Against the pre-ruling code, all five original tests failed —
#             `5 failed in 14.72s`: TC-8 `E KeyError: 'warning'` · TC-9
#             `E Failed: DID NOT RAISE ValidationError` · TC-10
#             `E KeyError: 'warning'` · TC-11 `E Failed: DID NOT RAISE
#             ValidationError` · TC-12 `E AttributeError: <module
#             'apps.rating.seams' ...> has no attribute
#             'last_issued_bill_for_unit'`. Then `6 passed`.
#         (2) TC-13 separately: with the per-unit savepoint removed from
#             `bulk_assign_unit_plans` it fails
#             `E AssertionError: assert UUID('019fefd8-dbdc-70f2-8dcc-9c554eec0d6d') is None`
#             — the refused unit's plan column had moved with no history row
#             behind it. Restored → 6 passed in 22.68s.
#         (3) TC-8's audit assertion separately: with the `core_audit.write_row`
#             call in `record_unit_plan_assignment` disabled it fails
#             `E assert 0 == 1 / +  where 0 = len([])` — no
#             `unit_plan_assignment.backdated` row. Restored → 6 passed in 23.03s.
# exceptions: the guard reads billing through apps/rating/seams.last_issued_bill_for_unit
#         → apps/billing/selectors.last_issued_bill_for_unit; rating never imports
#         billing's models. customers' own move-out guard resolves its billing read
#         from apps.billing.SERVICES and is therefore STILL unwired — REPORTED in the
#         lane report, not fixed here (customers/ is another lane's territory).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
