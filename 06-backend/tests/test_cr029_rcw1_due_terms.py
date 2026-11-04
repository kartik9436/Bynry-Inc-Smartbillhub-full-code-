# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W1 task W1-T3,
#           BACKEND HALF: the cycle keeps bill day + due days as DEFAULTS and
#           the RUN gains the override plumbing RC-W2's wizard will use.
#           Screens: SET-07.3 · SET-07D (Facts rail) · S31 step 1
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §3 D9
# Rules:    D9, PO verbatim 2026-08-23 — *"when we configure Cycle we are
#           provideing default values; mostly it wil remain as it is but user
#           can over ride them during billing"* · BR-BIL-024 (due date = bill
#           date + the cycle's due-days) · BR-BIL-070 (the clerk's typed bill
#           date is stored and wins) · BR-MET-009 (`due_days ≥ 0`) ·
#           CLAUDE.md rule 4 (financial immutability — nothing already issued
#           may move) · BR-MET-078 (no money on the cycle's config surfaces)
# ───────────────────────────────────────────────────────
"""CR-029 W1-T3 — the run may override, and **nothing already issued moves**.

⚠ **D9 SUPERSEDES THE UPGRADED PROTOTYPE.** Three screens (SET-07.3, SET-07.4
and the SET-07D Facts rail) carry the sentence *"Bill and due dates belong to
the run, not the cycle"*. The PO ruled the opposite: the cycle **provides the
defaults** and the run **overrides them**. A lane that builds the screenshot has
built the wrong thing, so the first case here asserts the columns are still on
the cycle — the shape the ruling protects.

**THE COMPARISON TEST IS THE POINT OF THIS FILE.** Adding a per-run override to
the due-date path touches the arithmetic that stamps a due date on every bill.
`test_...already_issued_figures_are_unchanged` recomputes the PRE-CR formula
independently, over a table of the cases the shipped code can be in, and
requires the new path to agree on every one of them. It fails the moment the
override starts leaking into a run that never asked for one.
"""

from datetime import date, timedelta

import pytest

from apps.billing import issue as billing_issue
from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)


#: ⚠ **`bill_date` IS GONE FROM THIS HELPER (RC-W6, metering 0023).** Every
#: cycle here carried a stored calendar `bill_date` because that is what
#: billing's fallback read. OQ-344 ruled the replacement on 2026-08-23 — *"I'd
#: say B - these are defualt - user can override"*, the bill DAY in the month
#: after the period ends — and the column was dropped. The default these cases
#: resolve through is therefore `bill_day`, and for the June period below
#: (1–30 June) it lands on **5 July**.
def _cycle(tenant, code, *, due_days=21, bill_day=5):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        due_days=due_days,
        bill_day=bill_day,
        start_day=1,
        days_to_complete=5,
    )


def _run(tenant, cycle, *, bill_date=None, due_days=None, key=None):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=bill_date,
        due_days=due_days,
        status="draft",
        idempotency_key=key or f"k-{cycle.code}-{bill_date}-{due_days}",
    )


# ═══════════════════════════════════════════════════════════════════════════
# D9 · THE DEFAULTS STAY ON THE CYCLE
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_t3__bill_day_and_due_days_stay_on_the_cycle_as_defaults(brazos, dana):
    """D9 verbatim: *"when we configure Cycle we are provideing default values;
    mostly it wil remain as it is but user can over ride them during billing"*.

    ⚠ This SUPERSEDES the upgraded prototype's *"Bill and due dates belong to
    the run, not the cycle"* — three screens carry that sentence and it is now
    wrong. The columns stay where they are; only the OVERRIDE is new."""
    fields = {field.name for field in metering_models.Cycle._meta.get_fields()}
    assert "bill_day" in fields, "D9 keeps the cycle's bill-day default"
    assert "due_days" in fields, "D9 keeps the cycle's due-days default"


def test_w1_t3__a_run_carries_its_own_due_days_override(brazos, dana):
    """The other half of D9 — *"user can over ride them during billing"*. The
    bill-date override already existed (`bill_runs.bill_date`, BR-BIL-070);
    due-days had nowhere to go, so half the ruling was unbuildable."""
    fields = {field.name for field in billing_models.BillRun._meta.get_fields()}
    assert "due_days" in fields
    assert "bill_date" in fields


def test_w1_t3__the_override_resolution_is_one_pure_function():
    """The same shape `runs.effective_bill_date` already has, so the two halves
    of one ruling cannot drift apart. The RUN's value first; the CYCLE's when
    nobody typed one; `None` when neither exists."""
    # ⚠ Its sibling changed shape with OQ-344 — `effective_bill_date` now takes
    # a bill DAY and a period end, because the stored date it used to fall back
    # to no longer exists. This one is unchanged: due-days was always a COUNT.
    assert billing_runs.effective_due_days(14, 21) == 14
    assert billing_runs.effective_due_days(None, 21) == 21
    assert billing_runs.effective_due_days(None, None) is None
    # ZERO IS A TYPED ANSWER, NOT AN ABSENT ONE. Due on the bill date is a real
    # arrangement (BR-MET-009 allows `due_days = 0`), and a falsy-test here
    # would silently replace it with the cycle's 21.
    assert billing_runs.effective_due_days(0, 21) == 0


def test_w1_t3__a_run_with_an_override_falls_due_on_the_overridden_terms(brazos, dana):
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-D9A")
        run = _run(brazos, cycle, due_days=14)
        bill_date, due_days = billing_issue._due_terms_for(run)
    assert due_days == 14
    # The period ends 30 June, so the cycle's bill day (the 5th) lands 5 July
    # (OQ-344), and 14 days on is 19 July.
    assert bill_date == date(2026, 7, 5)
    assert billing_issue.derive_due_date(bill_date, due_days) == date(2026, 7, 19)


def test_w1_t3__a_run_that_overrides_nothing_still_reads_the_cycles_defaults(brazos, dana):
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-D9B")
        run = _run(brazos, cycle)
        bill_date, due_days = billing_issue._due_terms_for(run)
    # OQ-344: the bill DAY (5th) in the month after the period ends (30 June).
    assert (bill_date, due_days) == (date(2026, 7, 5), 21)


def test_w1_t3__the_override_does_not_rewrite_the_cycles_default(brazos, dana):
    """*"an override applies to THAT RUN"* (BR-MET-077's own words about the day
    defaults). A run that bills on shorter terms must not silently re-terms
    every later run of the same cycle."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-D9C")
        _run(brazos, cycle, due_days=7)
        cycle.refresh_from_db()
    assert cycle.due_days == 21


# ═══════════════════════════════════════════════════════════════════════════
# THE COMPARISON PROOF — nothing already issued moves (CLAUDE.md rule 4)
# ═══════════════════════════════════════════════════════════════════════════

#: Every shape a SHIPPED run can be in, with the due date the code produces for
#: it — computed BY HAND from the rules, never from the code under test.
#:
#: ⚠ **THIS TABLE WAS KEYED ON `cycles.bill_date` UNTIL 2026-08-23 AND IS NOW
#: KEYED ON `cycles.bill_day` (OQ-344).** It existed to prove W1-T3's per-run
#: due-days override moved nothing already issued, and it still does — what
#: changed is the FALLBACK it compares against, because the PO ruled it: *"I'd
#: say B - these are defualt - user can override"*, the bill day in the month
#: AFTER the period ends. Each case states the period it bills, since the
#: fallback is now a function of it.
#:
#: (run bill date, cycle bill DAY, cycle due-days, period end) → due date
POST_OQ344_CASES: tuple[tuple[date | None, int | None, int | None, date, date | None], ...] = (
    # The ordinary run: the cycle's day and terms. Period ends 30 Jun → bills
    # 5 Jul, + 21 = 26 Jul.
    (None, 5, 21, date(2026, 6, 30), date(2026, 7, 26)),
    # BR-BIL-070's worked case, PO-shown: the clerk types 3 Aug and it WINS over
    # the default, so the bill falls due 24 Aug.
    (date(2026, 8, 3), 5, 21, date(2026, 7, 31), date(2026, 8, 24)),
    # Net-10 on a cycle that bills late in the month: period ends 30 Jun →
    # bills 26 Jul, + 10 = 5 Aug.
    (None, 26, 10, date(2026, 6, 30), date(2026, 8, 5)),
    # Due on the bill date — zero is lawful (BR-MET-009: due_days ≥ 0).
    (None, 5, 0, date(2026, 6, 30), date(2026, 7, 5)),
    # A leap-year span, because February is where date arithmetic goes wrong:
    # period ends 31 Jan 2028 → bills 20 Feb 2028, + 14 = 5 Mar.
    (None, 20, 14, date(2028, 1, 31), date(2028, 3, 5)),
    # OQ-339's clamp reaching the BILL day: the 31st, for a period ending in
    # January, bills 28 Feb in a common year — and 29 in a leap one.
    (None, 31, 0, date(2026, 1, 31), date(2026, 2, 28)),
    (None, 31, 0, date(2028, 1, 31), date(2028, 2, 29)),
    # The two refusals: no terms, and no bill day at all.
    (None, 5, None, date(2026, 6, 30), None),
    (None, None, 21, date(2026, 6, 30), None),
)


@pytest.mark.parametrize(
    "run_bill_date,cycle_bill_day,cycle_due_days,period_end,expected", POST_OQ344_CASES
)
def test_w1_t3__already_issued_figures_are_unchanged(
    brazos, dana, run_bill_date, cycle_bill_day, cycle_due_days, period_end, expected
):
    """⚠ **THE PROOF W1-T3 REQUIRED, CARRIED FORWARD THROUGH OQ-344.**

    Every run on the shipped tree carries `due_days = NULL` on the run row,
    because the column did not exist when it was created. So for every one of
    those runs the resolution must return the CYCLE's terms, and the arithmetic
    must still be exactly *bill date + due days*.

    ⚠ **AND NOTHING A CUSTOMER HAS CAN MOVE WHATEVER THIS RETURNS**, which is
    the claim OQ-344 needed: `invoices.due_date` is stamped at issue and the
    invoice is immutable (CLAUDE.md rule 4), so this resolution is consulted
    only while a bill is a DRAFT. Proved against a stamped bill in
    `tests/test_cr029_rcw6_bill_date_default.py`.

    `expected` is computed by hand from the rules, not from the code under test:
    a comparison against the implementation would pass for any implementation,
    which is the failure mode this whole case exists to avoid.
    """
    with tenant_ctx(brazos):
        cycle = metering_models.Cycle.objects.create(
            tenant=brazos,
            code=f"CY-P{abs(hash((run_bill_date, cycle_bill_day, cycle_due_days))) % 100000}",
            bill_day=cycle_bill_day,
            due_days=cycle_due_days,
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=period_end.replace(day=1),
            period_end=period_end,
            bill_date=run_bill_date,
            status="draft",
            idempotency_key=f"post-oq344-{cycle.code}-{period_end}",
        )
        assert run.due_days is None, "a run created before this CR overrides nothing"
        bill_date, due_days = billing_issue._due_terms_for(run)
        if expected is None:
            with pytest.raises(billing_issue.BillingRuleError):
                billing_issue.derive_due_date(bill_date, due_days)
        else:
            assert billing_issue.derive_due_date(bill_date, due_days) == expected
            # …and the arithmetic itself is still `bill date + due days`.
            assert bill_date + timedelta(days=due_days) == expected


def test_w1_t3__a_negative_override_is_refused_exactly_as_a_negative_default_is(brazos, dana):
    """BR-MET-009 (`due_days ≥ 0`) is a rule about the TERMS, not about which
    column they came from. A due date before the bill date puts every bill in
    the run instantly overdue and starts the late-fee clock on money nobody has
    been asked for — that is true whoever typed the -3."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-NEG")
        run = _run(brazos, cycle, due_days=-3)
        bill_date, due_days = billing_issue._due_terms_for(run)
        with pytest.raises(billing_issue.BillingRuleError) as caught:
            billing_issue.derive_due_date(bill_date, due_days)
    assert "due_days ≥ 0" in str(caught.value)


def test_w1_t3__the_run_service_accepts_the_override(brazos, dana):
    """Built is not wired (hard-won law 2). A column no writer can reach is dead
    schema, so the SERVICE takes it in W1 and records it in the audit trail.

    ⚠ The HTTP door is deliberately NOT opened here: `POST /billing/runs` gains
    the field with RC-W2-T2's wizard control, which is also where the refusal
    copy a malformed value needs in eleven catalogues gets written. Stated in
    `apps/billing/api.py` beside the create call rather than left to be noticed.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-WIRE")
        run = billing_runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            due_days=14,
            run_by=dana,
            actor=dana,
        )
    assert run.due_days == 14
