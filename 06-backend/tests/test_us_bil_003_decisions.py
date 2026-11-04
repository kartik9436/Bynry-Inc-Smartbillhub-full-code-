# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-003 (S31.3 — decide, record, apply)   Screens: S31.3
# Rules:    BR-BIL-015 (estimate | hold | bill without the service) ·
#           BR-BIL-060 (bulk: N rows, one shared id) · BR-BIL-003 (a waiver is
#           manual, never bulk) · BR-BIL-061 (base-only is a recorded opt-in) ·
#           BR-BIL-055 (a hold writes the pending queue) · BR-MET-029 (an
#           estimate travels flagged) · CLAUDE.md rule 3 · rule 4's reasoning
# ───────────────────────────────────────────────────────
"""A decision reaches a bill — which, until this module, it could not.

`BillRunDecision` was a carefully designed table with no writer, and
`prepare_run` listed what needed deciding with nothing able to answer. The
tests here are about the join: a clerk enters an estimate, and the bill that
comes out is priced on it.

`tc4` is the one that matters. Everything else asserts recording; that one
asserts the estimate actually reaching money.
"""

from decimal import Decimal

import pytest

from apps.billing import decisions, models as billing_models, runs
from apps.billing.exceptions import BillingRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import (
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_004_run_loop import a_run, prepared_for

pytestmark = pytest.mark.django_db


def a_run_with_missing_read(actor, tenant, *, asset_no, account_no):
    """One account in a cycle whose read never arrived."""
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    unit = a_billed_unit(
        actor, tenant, cycle, plan, asset_no=asset_no, label="Unit A", consumption=None,
        read_last_month=True,  # DEF-BIL-8671: read in May, missed in June
    )
    account = an_account(tenant, unit["id"], account_no)
    return cycle, account


def test_us_bil_003_tc1__a_decision_is_recorded_with_who_and_why(brazos, dana):
    """The PO's requirement: *"all the decisions are made on screen and recorded"*.

    Recorded is the operative word. A month later "why was this account
    estimated instead of held?" needs an answer with a name on it.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7301", account_no="A-30001"
        )
        run = a_run(brazos, cycle)

        row = decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice=decisions.CHOICE_ESTIMATE,
            reason="meter unreachable, snow",
            amount=Decimal("400.000000"),
            unit="kWh",
            decided_by=dana.user,
        )

        assert row.case == "missing_read" and row.choice == "estimate"
        assert row.reason == "meter unreachable, snow"
        assert row.decided_by_id == dana.user.id
        assert row.superseded_by_id is None
        assert row.bulk_action_id is None  # taken on this account alone


def test_us_bil_003_tc2__changing_a_decision_supersedes_rather_than_edits(brazos, dana):
    """Evidence that can be edited is not evidence.

    The same reasoning hard rule 4 applies to money, applied to a decision
    trail: the original row keeps saying what it said, and points at the one
    that replaced it.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7302", account_no="A-30002"
        )
        run = a_run(brazos, cycle)

        first = decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice=decisions.CHOICE_ESTIMATE,
            amount=Decimal("400"),
            unit="kWh",
        )
        second = decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice=decisions.CHOICE_HOLD,
            reason="customer disputes the estimate",
        )

        first.refresh_from_db()
        assert first.superseded_by_id == second.pk
        assert first.choice == "estimate"  # the original still says what it said
        assert decisions.current_decision(run, str(account.id), "missing_read").pk == second.pk
        # Both rows survive — the trail is the point.
        assert billing_models.BillRunDecision.objects.filter(bill_run=run).count() == 2


def test_us_bil_003_tc3__a_bulk_action_writes_n_rows_and_one_shared_id(brazos, dana):
    """BR-BIL-060 — 1,000 late fees is not a thousand clicks.

    Each account keeps its OWN row, because its bill changed and a dispute is
    about one account. The shared id answers the DIFFERENT question — "was this
    considered individually, or was it one of a thousand?" — which a single row
    cannot carry alongside the first.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        accounts = []
        for n in (1, 2, 3):
            unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"M-731{n}", label=f"U{n}")
            accounts.append(an_account(brazos, unit["id"], f"A-3003{n}"))
        run = a_run(brazos, cycle)

        bulk_id, rows = decisions.record_bulk(
            bill_run=run,
            account_ids=[str(a.id) for a in accounts],
            case="late_fee",
            choice=decisions.CHOICE_APPLY,
            amount=Decimal("8.13"),
            decided_by=dana.user,
        )

        assert len(rows) == 3
        assert {r.bulk_action_id for r in rows} == {bulk_id}
        assert len({r.account_id for r in rows}) == 3  # one row per account


def test_us_bil_003_tc3b__a_waiver_may_not_be_taken_in_bulk(brazos, dana):
    """BR-BIL-003, and the asymmetry is deliberate.

    Applying a fee in bulk is fine — the rule computed each one. WAIVING in
    bulk would let one click forgive a thousand fees with a single reason
    between them, and the reason is the whole of the evidence a waiver leaves.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7304", account_no="A-30004"
        )
        run = a_run(brazos, cycle)

        with pytest.raises(BillingRuleError) as raised:
            decisions.record_bulk(
                bill_run=run,
                account_ids=[str(account.id)],
                case="late_fee",
                choice=decisions.CHOICE_WAIVE,
                reason="goodwill",
            )
        assert "may not be taken in bulk" in str(raised.value)

        # The same waiver, one account at a time, is allowed.
        row = decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="late_fee",
            choice=decisions.CHOICE_WAIVE,
            reason="goodwill",
        )
        assert row.choice == "waive" and row.bulk_action_id is None


def test_us_bil_003_tc4__an_estimate_actually_reaches_the_bill(brazos, dana):
    """THE TEST THIS MODULE EXISTS FOR.

    Before this, an account with no read broke at calculate and a clerk had no
    way to say "estimate it at 400 kWh". Now the decision is recorded, applied
    to the gathered data, and the bill is priced on it: 400 × 0.12 = 48.00,
    plus the 18.50 base = **66.50**.

    The estimate travels FLAGGED (BR-MET-029) — a customer disputing an
    estimated bill has to be able to see that it was one.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7305", account_no="A-30005"
        )
        run = a_run(brazos, cycle)

        prepared = prepared_for(cycle)
        # Without a decision, the account breaks — that is BR-BIL-015 refusing
        # to take the clerk's choice for them.
        assert runs.calculate_run(prepared, bill_run=run).drafted_count == 0

        decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice=decisions.CHOICE_ESTIMATE,
            amount=Decimal("400.000000"),
            unit="kWh",
            reason="meter unreachable",
            decided_by=dana.user,
        )
        decided = decisions.apply_decisions(prepared, bill_run=run)
        result = runs.calculate_run(decided, bill_run=run)

        assert result.drafted_count == 1
        invoice = billing_models.Invoice.objects.get(account=account)
        assert invoice.total == Decimal("66.500000")  # 400 × 0.12 + 18.50
        assert invoice.bill_payload["services"][0]["estimated"] is True


def test_us_bil_003_tc5__a_hold_takes_the_account_out_and_into_the_queue(brazos, dana):
    """BR-BIL-015's second choice, landing in BR-BIL-055's one pending queue.

    The account leaves the run and gains an exclusion row — the same table a
    phase-3 mark-for-later writes, because the PO confirmed one queue with two
    doors.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7306", account_no="A-30006"
        )
        run = a_run(brazos, cycle)

        prepared = prepared_for(cycle)
        decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice=decisions.CHOICE_HOLD,
            reason="customer away, re-read next month",
        )
        decided = decisions.apply_decisions(prepared, bill_run=run)

        assert decided.ready == ()
        exclusion = billing_models.BillRunExclusion.objects.get(bill_run=run, account=account)
        assert exclusion.reason_code == "staff_hold_missing_read"
        assert exclusion.resolved_at is None  # pending — that is what makes it a queue
        assert runs.calculate_run(decided, bill_run=run).drafted_count == 0


def test_us_bil_003_tc6__bill_without_the_service_drops_it_rather_than_zeroing_it(brazos, dana):
    """BR-BIL-015's third choice, and the distinction that makes it safe.

    The service LEAVES the bill. It is not billed at $0.00 — a zero usage line
    tells the customer their meter was read and showed nothing, which is a
    different and checkable claim from "we did not read this".
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7307", account_no="A-30007"
        )
        run = a_run(brazos, cycle)

        prepared = prepared_for(cycle)
        decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="missing_read",
            choice=decisions.CHOICE_BILL_WITHOUT_SERVICE,
            reason="single-service account",
        )
        decided = decisions.apply_decisions(prepared, bill_run=run)

        # ⚠ SUPERSEDED 2026-09-30 by the PO's fixed-charge case 1 (option A):
        # *"The customer sees a steady base every month and nothing is lost"*.
        # The service's USAGE leaves the bill (still never a $0.00 usage line)
        # and its BASE stays; the usage bills next bill. This read *"its only
        # service is gone, so there is nothing left to price"* until then.
        # The two-month proof is `test_bbr_fixed_charge_next_bill.py` case 1.
        assert decided.ready[0].readings == ()
        assert [t.base_only for t in decided.ready[0].tariffs] == [True]
        assert decided.ready[0].usage_next_bill == ("electric",)


def test_us_bil_003_tc7__an_estimate_without_its_unit_is_refused(brazos, dana):
    """CLAUDE.md rule 3 — the estimate reaches a bill as a consumption.

    "400" is not a quantity anyone can check against a meter, and by the time
    it is on a customer's bill the unit cannot be recovered.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7308", account_no="A-30008"
        )
        run = a_run(brazos, cycle)

        with pytest.raises(BillingRuleError) as raised:
            decisions.record_decision(
                bill_run=run,
                account_id=str(account.id),
                case="missing_read",
                choice=decisions.CHOICE_ESTIMATE,
                amount=Decimal("400"),
            )
        assert "unit" in str(raised.value)


def test_us_bil_003_tc8__the_unbuildable_case_refuses_by_name(brazos, dana):
    """The prime directive's shape: implement to the boundary, refuse loudly.

    `overcharge` needs BR-BIL-029's trailing-average guardrail, whose averaging
    WINDOW no signed statement anywhere states. Accepting a release-or-hold on a
    guardrail nobody computed would be a decision about a number that does not
    exist.

    ⚠ **THIS CASE USED TO LOOP OVER TWO CASES AND WAS RED ON THE BRANCH TIP —
    `DEF-2862`.** `extra_charge` was the second one, and CR-051 task 18 gave it
    real choices on 2026-08-31: it left `decisions.UNSUPPORTED_CASES` and gained
    `apply`/`waive` in `CHOICES_BY_CASE`, because the charge-code reader it was
    said to be waiting on has existed since BR-BIL-075 landed. The change was
    correct and its own lane could not have seen this assertion — it lives in a
    test file about a different story, and nothing in `run_gates` executes it
    (G4 runs `pytest -m golden` and this case carries no marker).

    So the loop is split rather than deleted. The refusal half keeps the case
    that is still genuinely unbuildable, and the positive half below asserts what
    replaced the other one — which is the assertion that would have gone red if
    task 18 had removed the refusal without building the recording.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7309", account_no="A-30009"
        )
        run = a_run(brazos, cycle)

        with pytest.raises(BillingRuleError) as raised:
            decisions.record_decision(
                bill_run=run,
                account_id=str(account.id),
                case="overcharge",
                choice="apply",
            )
        assert "overcharge" in str(raised.value)
        assert "does not exist" in str(raised.value) or "cannot yet" in str(raised.value)

        # And the vocabulary agrees with the refusal, which is the half a screen
        # reads: a case that cannot be recorded offers no choices at all, rather
        # than an empty list that reads as "no options".
        assert "overcharge" in decisions.UNSUPPORTED_CASES
        assert "overcharge" not in decisions.CHOICES_BY_CASE


def test_us_bil_003_tc8b__a_charge_to_add_is_RECORDED_and_HOLDS_the_account(brazos, dana):
    """BR-BIL-007 after CR-051 task 18 — the half that replaced tc8's second case.

    **The two halves are separated and only one of them exists.** The clerk's
    reply IS recorded, with their name on it, using the same `apply`/`waive` the
    late fee uses — S31.3's *Charges to add* tab drew Apply on every row and the
    server refused every one of them, so an answer went nowhere. The MONEY
    application does not exist: BR-BIL-007's amount belongs to the tenant's own
    charge code and no case row in this product names one. So `apply` HOLDS the
    account at that named boundary instead of billing it without the charge a
    human asked to add.

    `waive` is deliberately NOT a holding choice: waiving means the charge does
    not go on the bill, so the account bills normally and the recorded row is the
    whole of the act — the `late_fee`/`waive` shape exactly.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-7310", account_no="A-30010"
        )
        run = a_run(brazos, cycle)

        row = decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="extra_charge",
            choice=decisions.CHOICE_APPLY,
            reason="reconnection agreed on the phone",
            decided_by=dana,
        )

        assert row.case == "extra_charge"
        assert row.choice == decisions.CHOICE_APPLY
        assert str(row.decided_by_id) == str(dana.pk), "a decision carries WHO made it"
        assert row.reason == "reconnection agreed on the phone"

        # The vocabulary the screen renders, published from the module.
        assert decisions.CHOICES_BY_CASE["extra_charge"] == (
            decisions.CHOICE_APPLY,
            decisions.CHOICE_WAIVE,
        )
        assert "extra_charge" not in decisions.UNSUPPORTED_CASES
        # `apply` holds at the named boundary; `waive` does not hold anything.
        assert ("extra_charge", decisions.CHOICE_APPLY) in decisions.HOLDING_CHOICES
        assert ("extra_charge", decisions.CHOICE_WAIVE) not in decisions.HOLDING_CHOICES


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-003@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔
# exceptions: (1) tc6 leaves an account with NO services, because the fixture
#         is single-service — so "bill without the service" empties the bill and
#         the run reports it. That is the honest outcome for that fixture and is
#         asserted as such; a multi-service account keeps its other services,
#         which is what the choice is for
#         (2) NO SCREEN AND NO ENDPOINT. This is the data and the transformation
#         S31.3 will drive; nothing renders it yet
#         (3) `no_usage` is accepted and recorded but changes nothing on the
#         data — a real zero is a real bill. It exists so "someone looked and
#         decided to bill it" is distinguishable from "nobody looked", which is
#         the only reason to record a decision that changes nothing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
