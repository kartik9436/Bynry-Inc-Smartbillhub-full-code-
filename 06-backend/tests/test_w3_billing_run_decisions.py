# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-003 (S31.3 — the exception step)   Screens: S31.3
# Rules:    BR-BIL-015 (missing-service read → estimate | hold | bill-without-
#           service, per case, never silent) · BR-BIL-003 (a late-fee waiver is
#           ALWAYS a manual staff decision) · BR-BIL-007 (extra charges from
#           tenant charge codes only) · BR-BIL-029 (over-guardrail drafts
#           flagged before issue)
# ───────────────────────────────────────────────────────
"""Every decision taken during a run is recorded, with a name on it.

The PO's requirement, stated on 2026-08-11 while describing the run they want:

    "all the decisions are made on screen and recorded"

Before this table, only ONE of the exception step's choices had anywhere to
land: BR-BIL-015's "hold", which writes `bill_run_exclusions`. Estimating a
read, waiving a late fee, adding a charge code, releasing an over-guardrail
draft — each of those changes what a customer is charged, and each left no
record of who decided or why.

WHAT THESE TESTS PIN. That a decision is stored with its actor and its case
(TC-1); that a changed mind SUPERSEDES rather than overwrites, so the trail
survives (TC-2); that "current" is a query and not a guess (TC-3); and that a
service-specific case carries its service, because "bill without the service"
is meaningless without naming which one (TC-4).
"""

from decimal import Decimal

import pytest

from apps.billing import models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db


def current_decisions(run):
    return models.BillRunDecision.objects.filter(bill_run=run, superseded_by__isnull=True)


def test_us_bil_003_tc1__a_decision_is_recorded_with_who_made_it(brazos, dana):
    """BR-BIL-015 — an exception resolves by CHOICE, and the choice is kept.

    "Why was this account estimated instead of held?" has to have an answer
    with a name on it a month later, not a shrug.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)

        decision = models.BillRunDecision.objects.create(
            tenant=brazos,
            bill_run=run,
            account=account,
            case="missing_read",
            choice="estimate",
            reason="meter inaccessible — dog in the yard",
            amount=Decimal("684.000000"),
            unit="kWh",
            decided_by=dana.user,
        )

        stored = models.BillRunDecision.objects.get(pk=decision.pk)
        assert stored.case == "missing_read" and stored.choice == "estimate"
        assert stored.decided_by_id == dana.user.id  # a name, not just a timestamp
        assert stored.reason.startswith("meter inaccessible")
        assert stored.amount == Decimal("684.000000")  # six decimals (rule 2)
        assert stored.unit == "kWh"  # rule 3 — a quantity carries its unit
        assert stored.superseded_by_id is None  # current


def test_us_bil_003_tc2__changing_a_decision_supersedes_it_and_keeps_both(brazos, dana):
    """Append-only: the trail is evidence, and evidence that can be edited is
    not evidence.

    A clerk estimates, then thinks better of it and holds the account. Both
    facts matter — a customer disputing the eventual bill is entitled to know
    an estimate was considered and withdrawn.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)

        first = models.BillRunDecision.objects.create(
            tenant=brazos,
            bill_run=run,
            account=account,
            case="missing_read",
            choice="estimate",
            decided_by=dana.user,
        )
        second = models.BillRunDecision.objects.create(
            tenant=brazos,
            bill_run=run,
            account=account,
            case="missing_read",
            choice="hold",
            reason="estimate looked wrong against last year",
            decided_by=dana.user,
        )
        first.superseded_by = second
        first.save(update_fields=["superseded_by"])

        assert models.BillRunDecision.objects.filter(bill_run=run).count() == 2  # nothing erased
        live = list(current_decisions(run))
        assert len(live) == 1 and live[0].choice == "hold"
        assert models.BillRunDecision.objects.get(pk=first.pk).superseded_by_id == second.pk


def test_us_bil_003_tc3__a_late_fee_waiver_is_recorded_as_a_human_act(brazos, dana):
    """BR-BIL-003 — the waiver is ALWAYS manual, so it always has an author.

    An automatic waiver would need no record. That the rule makes it manual is
    exactly why the record has to exist.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)

        waiver = models.BillRunDecision.objects.create(
            tenant=brazos,
            bill_run=run,
            account=account,
            case="late_fee",
            choice="waive",
            reason="first occurrence; customer called ahead",
            amount=Decimal("8.13"),
            decided_by=dana.user,
        )

        assert waiver.decided_by_id is not None
        assert waiver.reason  # a waiver without a reason is not a decision
        assert waiver.amount == Decimal("8.13")  # what was given up, recorded


def test_us_bil_003_tc4__a_service_specific_case_names_its_service(brazos, dana):
    """ "Bill without the service" is meaningless without naming which one.

    A house on electric + water with a missing WATER read still bills its
    electric. The decision has to say which service was dropped, or the bill
    cannot be reconstructed from the trail.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)
        water = tenancy_models.Service.objects.get(code="water")

        decision = models.BillRunDecision.objects.create(
            tenant=brazos,
            bill_run=run,
            account=account,
            service=water,
            case="missing_read",
            choice="bill_without_service",
            reason="meter replaced mid-cycle; no closing read",
            decided_by=dana.user,
        )

        assert decision.service_id == water.id


def test_us_bil_003_tc5__every_case_the_exception_step_offers_has_a_home(brazos, dana):
    """The gap this table closes, stated as a list.

    Before it, only "hold" had storage (`bill_run_exclusions`). Each of these
    changes what a customer is charged.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)
        for case, choice in (
            ("missing_read", "estimate"),
            ("late_fee", "apply"),
            ("extra_charge", "add"),
            ("overcharge", "release"),
            ("no_usage", "bill"),
            ("base_only_billing", "include"),
            # CR-038 W8 (2026-08-26) — the read-analysis cases. This loop went
            # RED on the day they were declared — verbatim `AssertionError:
            # assert 6 == 13` — which is this tripwire doing the exact job its
            # comment below promises.
            ("estimated_read", "keep"),
            ("high_usage", "bill_as_is"),
            ("low_usage", "investigate"),
            ("days_threshold", "prorate_to_cycle_days"),
            ("meter_factor", "confirm_factor"),
            ("replacement", "prorate_both_segments"),
            ("true_up", "apply_next_bill"),
        ):
            assert case in models.DECISION_CASES
            models.BillRunDecision.objects.create(
                tenant=brazos,
                bill_run=run,
                account=account,
                case=case,
                choice=choice,
                decided_by=dana.user,
            )

        # ⚠ AMENDED 2026-09-30 — `service_not_connected` (BR-BIL-301, PO ruling
        # 2026-09-25, option (b)) joined DECISION_CASES in `3a572853d` and this
        # tripwire went red that day, as it is meant to. It is STORABLE and it
        # is on screen, but it deliberately has NO choice yet: its fix is
        # connecting the property through the four existing paths and no
        # other (BR-BIL-302, same day — "no connect a service action"), so
        # `decisions.CHOICES_BY_CASE` offers nothing and `runs.py` says why.
        # Writing a row here would mean inventing a choice word the product
        # does not have. So it is named as the one case with no answer, and
        # the moment a choice is ruled for it the second assertion goes red.
        from apps.billing import decisions

        no_choice_yet = {"service_not_connected"}
        for case in no_choice_yet:
            assert case in models.DECISION_CASES
            assert not decisions.CHOICES_BY_CASE.get(case), (
                f"{case} now offers a choice — record one above and drop it from this set"
            )

        # Every case the exception step can raise has somewhere to land. The
        # count is against DECISION_CASES itself, so ADDING a case without
        # covering it here fails — which is how the PO's `base_only_billing`
        # addition was caught the moment it was declared.
        assert current_decisions(run).count() == len(models.DECISION_CASES) - len(no_choice_yet)


def test_us_bil_003_tc6__a_bulk_action_writes_one_row_per_account_sharing_an_id(brazos, dana):
    """PO ruling 2026-08-11 — the bulk option, and why it is not one row.

    *"if there are 500 or 1000 or 5000 bills to be generated and 1000 bills has
    late fees, it is impossible for user to do this manually account by
    account."*

    One click, a thousand accounts. Each account keeps its OWN row, because its
    bill changed and a dispute a year later is about that account. The shared
    `bulk_action_id` keeps the other fact — that it was one human act, not a
    thousand considered judgements. A reviewer needs both, and neither can be
    reconstructed from the other.
    """
    from uuid import uuid4

    with tenant_ctx(brazos):
        run = a_run(brazos)
        accounts = [an_account(dana, brazos, account_no=f"A-BULK-{n}") for n in range(3)]
        bulk_id = uuid4()
        for account in accounts:
            models.BillRunDecision.objects.create(
                tenant=brazos,
                bill_run=run,
                account=account,
                case="late_fee",
                choice="apply",
                amount=Decimal("8.13"),
                decided_by=dana.user,
                bulk_action_id=bulk_id,
            )

        rows = models.BillRunDecision.objects.filter(bulk_action_id=bulk_id)
        assert rows.count() == len(accounts)  # one per account, not one total
        assert {row.account_id for row in rows} == {a.id for a in accounts}
        assert len({row.choice for row in rows}) == 1  # one act, one choice


def test_us_bil_003_tc7__a_solo_decision_carries_no_bulk_id(brazos, dana):
    """The distinction has to be visible, or the id means nothing.

    If every decision carried a bulk id, "was this one of a thousand?" would be
    unanswerable — which is the whole reason the column exists.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)
        solo = models.BillRunDecision.objects.create(
            tenant=brazos,
            bill_run=run,
            account=account,
            case="overcharge",
            choice="hold",
            reason="1,240 against a 110 average — checking the meter",
            decided_by=dana.user,
        )
        assert solo.bulk_action_id is None


def test_us_bil_003_tc8__billing_the_base_only_accounts_is_a_recorded_choice(brazos, dana):
    """PO ruling 2026-08-11 — *"this is decision user make hence during pre
    billing process, you have to give option to user to opt in or opt out."*

    BR-CUS-055 says a Vacation-hold or Suspended account CAN be billed for its
    base charges. Whether THIS run does is the staff's call, made at prepare
    time and recorded — not a silent consequence of a status class.
    """
    with tenant_ctx(brazos):
        run = a_run(brazos)
        account = an_account(dana, brazos)

        assert "base_only_billing" in models.DECISION_CASES
        opted_out = models.BillRunDecision.objects.create(
            tenant=brazos,
            bill_run=run,
            account=account,
            case="base_only_billing",
            choice="exclude",
            reason="owner asked us to pause billing while the unit is renovated",
            decided_by=dana.user,
        )
        assert opted_out.choice == "exclude"
        assert opted_out.reason  # opting OUT of revenue needs a why


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-003@e9d5a48 (ships with apps/billing/migrations/0003+0004)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: the RLS half was proved RED on live Postgres — with 0004's
#         `apply_policy` made a no-op, the G5 catalog sweep fails naming
#         'bill_run_decisions' verbatim; restored, 59 passed / 12 skipped.
# exceptions: these assert the RECORD, not the ACT — estimating a read is
#         metering's write, holding an account writes `bill_run_exclusions`,
#         adding a charge is a line on the draft. None of those exist on this
#         path yet, and the run service that ties recording to acting is the
#         next story. Stated rather than left looking like the exception step
#         is built
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
