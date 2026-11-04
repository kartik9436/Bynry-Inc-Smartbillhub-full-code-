# ── Trace ──────────────────────────────────────────────
# Change:  CR-138-BRC07 `P4.2` — one query for the ladder.
# Defect:  the `NFR-3` breach `CLAUDE.md` does NOT name. `ladder_board` asked
#          `dunning.collections_pause_for` once per debtor (one query, two for
#          an account on a plan) and `settings_seam.tenant_currency()` once per
#          ROW. Measured on real PostgreSQL 16, 2026-09-23: **12,395
#          statements / 14.503 s at 2,046 debtors, and 244,195 statements /
#          285.572 s at 40,046** — over a worker that is given sixty seconds.
#          The board makes **20 statements at either size** now.
# Rules:   `NFR-3` · BR-CUS-043 (an active, current plan pauses the ladder) ·
#          BR-PAY-021 (on-time is `posted_on <= due_date`) · BR-TEN-042 (one
#          currency per tenant, which is what makes one read per BODY right) ·
#          CLAUDE.md hard-won law 7.
# ───────────────────────────────────────────────────────
"""The collections board costs the same number of round trips at any size.

⚠ **A STATEMENT COUNT IS THE ONLY INSTRUMENT THAT CAN SEE THIS, AND A WALL
CLOCK CANNOT.** `10-scripts/cr094c_accounts_page_cost.py` already recorded the
mirror-image lesson for the accounts list — a statement count stayed flat while
the work grew — and this is the other half of it: at the three debtors a unit
test can afford, the broken board and the fixed one both answer in
milliseconds. What separates them is whether the count MOVES when a debtor is
added, so that is what is asserted.

⚠ **AND THE ASSERTION IS `equal`, NOT `less than some number`.** A bound like
*"fewer than 40"* passes for ever while a read quietly grows from four
statements per board to thirty-nine, and it is the shape of a check that
cannot fail. Two boards of different sizes making the SAME number of
statements is the property `NFR-3` actually wants.

RED-PROVED FIRST (hard-won law 7), **through `pytest`, the harness that will
run this** — not `run_gates`, which runs gates and would have been law 7's
*proved through the wrong entry point* wearing the right words. With
`collections_pause_for_many` swapped back for the per-row
`collections_pause_for`, `test_the_board_costs_the_same_at_any_size` fails with
the two counts differing by one per debtor; with `tenant_currency()` moved back
inside the row loop it fails by three per debtor.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import connection

from apps.payments import collections_read, dunning, plans
from apps.payments.collections_models import PLAN_ACTIVE, PaymentPlan, PaymentPlanInstallment

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 9, 23)


class _Counter:
    """Counts EVERY statement — `connection.queries` is capped at 9,000."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


def _debtor(brazos, dana, *, suffix: str, owed: str = "500.00", days_late: int = 40):
    account = an_account(dana, brazos, account_no=f"LAD-{suffix}")
    an_issued_bill(
        brazos,
        account,
        number=f"BL-CR138L-{suffix}",
        total=Decimal(owed),
        issued_on=AS_OF - timedelta(days=days_late + 1),
        due_date=AS_OF - timedelta(days=days_late),
    )
    return account


def _a_plan(brazos, account, *, missed: int):
    """An ACTIVE plan with `missed` instalments not met by their due date."""
    plan = PaymentPlan.objects.create(
        tenant=brazos,
        account=account,
        total_amount=Decimal("300.00"),
        down_payment=Decimal("0"),
        currency="USD",
        installment_count=3,
        cadence="monthly",
        status=PLAN_ACTIVE,
        proposed_on=AS_OF - timedelta(days=90),
        signed_on=AS_OF - timedelta(days=89),
    )
    for seq in range(1, 4):
        due = AS_OF - timedelta(days=60 - seq)
        PaymentPlanInstallment.objects.create(
            tenant=brazos,
            plan=plan,
            seq=seq,
            due_date=due,
            amount=Decimal("100.00"),
            currency="USD",
            paid_posted_on=None if seq <= missed else due,
        )
    return plan


def _count_board(brazos) -> tuple[int, int]:
    counter = _Counter()
    with connection.execute_wrapper(counter):
        board = collections_read.ladder_board(as_of=AS_OF)
    return counter.count, len(board["rows"])


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · `NFR-3` — THE COST DOES NOT GROW WITH THE TENANT
# ══════════════════════════════════════════════════════════════════════════


def test_the_board_costs_the_same_at_any_size(brazos, dana):
    """Two boards, different sizes, SAME number of statements."""
    with tenant_ctx(brazos):
        _debtor(brazos, dana, suffix="a")
        small_statements, small_rows = _count_board(brazos)

        for suffix in ("b", "c", "d", "e"):
            _debtor(brazos, dana, suffix=suffix)
        large_statements, large_rows = _count_board(brazos)

        assert small_rows == 1 and large_rows == 5, "the fixture did not grow"
        assert large_statements == small_statements, (
            f"the board costs {large_statements} statements at {large_rows} debtors and "
            f"{small_statements} at {small_rows} — it is still paying per debtor"
        )


def test_a_plan_does_not_add_a_statement_either(brazos, dana):
    """The SECOND half of the N+1 — `outstanding_installments` per plan.

    ⚠ **THE FIRST DRAFT OF THIS TEST ASSERTED THE WRONG INVARIANT AND WENT RED
    ON CORRECT CODE, WHICH IS WHY THE REAL ONE IS WRITTEN OUT HERE.** It
    compared a board with NO plans against a board with three and demanded the
    two counts be EQUAL. They are not, and they should not be: with no live
    plan at all `outstanding_installment_counts([])` returns `{}` without
    touching the database, and with one or more it issues **exactly one**
    grouped `COUNT`. So a tenant that has any plans pays ONE statement more
    than a tenant that has none, for ever, however many plans it has.

    **That is the property `NFR-3` wants, and it is what is asserted below:**
    the count does not grow with the NUMBER of plans. Three plans and six
    plans cost the same, and the step from zero to some is a constant, named
    here so the next reader does not mistake it for the defect coming back.
    """
    with tenant_ctx(brazos):
        for suffix in ("p1", "p2", "p3"):
            _debtor(brazos, dana, suffix=suffix)
        no_plans, _ = _count_board(brazos)

        for suffix in ("p4", "p5", "p6"):
            account = _debtor(brazos, dana, suffix=suffix)
            _a_plan(brazos, account, missed=0)
        three_plans, rows = _count_board(brazos)

        for suffix in ("p7", "p8", "p9"):
            account = _debtor(brazos, dana, suffix=suffix)
            _a_plan(brazos, account, missed=0)
        six_plans, more_rows = _count_board(brazos)

        assert (rows, more_rows) == (6, 9), "the fixture did not grow"
        assert six_plans == three_plans, (
            f"doubling the plans from three to six moved the board from "
            f"{three_plans} statements to {six_plans} — it is still paying per plan"
        )
        assert three_plans == no_plans + 1, (
            f"a board with plans should cost exactly ONE grouped COUNT more than a "
            f"board with none; it cost {three_plans - no_plans} more"
        )


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · THE BATCHED RULE IS THE SAME RULE
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("missed", [0, 1, 3])
def test_the_plural_agrees_with_the_singular(brazos, dana, missed):
    """`collections_pause_for_many` and `collections_pause_for`, same answer.

    ⚠ This is the ONLY thing stopping the two forms drifting. Both call
    `_pause_decision`, which takes no query — but a batched READ that picked a
    different plan, or counted a missed instalment differently, would separate
    a PREVIEW from the SEND that follows it, and no statement count can see
    that.
    """
    with tenant_ctx(brazos):
        accounts = []
        for index in range(3):
            account = _debtor(brazos, dana, suffix=f"eq{missed}{index}")
            if index:  # one account deliberately has NO plan at all
                _a_plan(brazos, account, missed=missed)
            accounts.append(account)

        ids = [account.id for account in accounts]
        batched = dunning.collections_pause_for_many(ids, as_of=AS_OF)
        for account_id in ids:
            one = dunning.collections_pause_for(account_id, as_of=AS_OF)
            many = batched[account_id]
            assert (many.paused, many.reason, many.plan_id) == (
                one.paused,
                one.reason,
                one.plan_id,
            )


def test_the_batched_instalment_count_agrees_with_the_rows(brazos, dana):
    """`outstanding_installment_counts` is `len(outstanding_installments)`.

    Including BR-PAY-021's two edges: an instalment due TODAY is not missed
    today, and a payment posted after its due date does not make it on time.
    """
    with tenant_ctx(brazos):
        account = _debtor(brazos, dana, suffix="cnt")
        plan = _a_plan(brazos, account, missed=2)
        # One instalment due exactly on `as_of` — not missed (BR-PAY-021).
        PaymentPlanInstallment.objects.create(
            tenant=brazos,
            plan=plan,
            seq=4,
            due_date=AS_OF,
            amount=Decimal("100.00"),
            currency="USD",
        )
        # One paid LATE — still missed.
        PaymentPlanInstallment.objects.create(
            tenant=brazos,
            plan=plan,
            seq=5,
            due_date=AS_OF - timedelta(days=10),
            amount=Decimal("100.00"),
            currency="USD",
            paid_posted_on=AS_OF - timedelta(days=2),
        )
        expected = len(plans.outstanding_installments(plan, as_of=AS_OF))
        counts = plans.outstanding_installment_counts([plan.pk], as_of=AS_OF)
        assert counts[plan.pk] == expected
        assert expected == 3, "the fixture should hold two unpaid and one paid late"


def test_the_english_predicate_and_the_sql_count_agree(brazos, dana):
    """`dunning.plan_is_current` is BR-PAY-021's rule in one English line.

    ⚠ **THIS IS THE TEST THAT KEEPS THAT LINE ALIVE.** Nothing calls
    `plan_is_current` on the pause path since `CR-138-BRC07` `P4.2` — the
    singular reads a length and the plural reads a `COUNT` in SQL — so
    without this assertion it would be a function nobody calls and nobody
    checks, which is hard-won law 2's dead code. With it, it is the
    specification the SQL is measured against, and the two cannot drift.
    """
    with tenant_ctx(brazos):
        for missed, suffix in ((0, "cur"), (2, "beh")):
            account = _debtor(brazos, dana, suffix=f"eng{suffix}")
            plan = _a_plan(brazos, account, missed=missed)
            counted = plans.outstanding_installment_counts([plan.pk], as_of=AS_OF)
            assert dunning.plan_is_current(plan, as_of=AS_OF) == (counted.get(plan.pk, 0) == 0), (
                f"BR-PAY-021 is stated twice and the two disagree on {plan.pk}: "
                f"plan_is_current says {dunning.plan_is_current(plan, as_of=AS_OF)} "
                f"and the SQL count says {counted.get(plan.pk, 0)}"
            )


def test_an_empty_list_is_not_the_whole_tenant(brazos, dana):
    """`[]` means nothing; it must never be read as *everybody*."""
    with tenant_ctx(brazos):
        _debtor(brazos, dana, suffix="empty")
        assert dunning.collections_pause_for_many([], as_of=AS_OF) == {}
        assert plans.outstanding_installment_counts([], as_of=AS_OF) == {}
