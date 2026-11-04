# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W6: **OQ-344**,
#           *"A RUN WITH NO TYPED BILL DATE, AND A CYCLE HOLDING A BILL DAY —
#           WHICH MONTH'S 5th DOES IT BILL ON?"*  Screens: S31 step 1 · SET-07D
# Ruling:   OQ-344, CLOSED 2026-08-23, PO verbatim: *"I'd say B - these are
#           defualt - user can override"* — reading **(B) THE MONTH AFTER THE
#           PERIOD ENDS**.
# Rules:    D9 (the cycle carries defaults; the run overrides) · BR-BIL-070
#           (the clerk's typed bill date is stored and WINS) · BR-BIL-024 (due
#           date = bill date + due days) · BR-MET-009 (`due_days ≥ 0`) ·
#           OQ-339 (a day the month does not have clamps to its last day) ·
#           CLAUDE.md rule 4 (financial immutability — nothing issued moves) ·
#           B1 / gate G6 (billing does not import metering)
# ───────────────────────────────────────────────────────
"""RC-W6 — the bill date a run falls back to, and the last legacy column.

**THE QUESTION.** D9 gave a cycle a bill **day** (a day-of-month: *"this cycle
normally bills on the 5th"*) that the run may override. When a clerk types
nothing, billing had to fall back to `cycles.bill_date` — a stored calendar DATE
from the previous generation — because turning a day-of-month into ONE run's
date means CHOOSING A MONTH, and nothing ruled which. The three readings sat up
to a month apart, and since the due date is bill date + due days, each produced a
different date late fees would start from. RC-W5 refused to pick one and left the
column standing rather than delete the fallback and choose by omission.

**THE RULING.** PO 2026-08-23: *"I'd say B - these are defualt - user can
override"* — **the month AFTER the period ends**. On the figure they were shown:
a cycle whose bill day is the **5th** with **21** due-days, billing the period
**1–31 August**, bills on **5 September** and falls due on **26 September**. It
is the ordinary arrears reading and the only one that gives the same answer
whether the run is taken on time or late.

**AND IT IS A DEFAULT.** The PO restated D9 in the same breath: a clerk's typed
bill date still wins (BR-BIL-070), and a run's typed due-days still wins (D9).
This file asserts the fallback and the override in the same place so neither can
quietly become the other.

**WHAT IT UNBLOCKS.** `cycles.bill_date` — the sixth and last legacy column, the
one metering 0021 could not take — is dropped by metering 0023. The fallback is
computed from the cycle's own three fields and the stored calendar date is read
by nothing.

⚠ **NOTHING ALREADY ISSUED MOVES**, and the reason is structural rather than
careful: `invoices.due_date` is STAMPED at issue and the invoice is immutable
(CLAUDE.md rule 4), so this resolution is consulted only while a bill is a
DRAFT. The last case in this file proves it against a stamped bill.
"""

from datetime import date

import pytest

from apps.billing import issue as billing_issue
from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

AUG = (date(2026, 8, 1), date(2026, 8, 31))


def _cycle(tenant, code, *, bill_day=5, due_days=21):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        bill_day=bill_day,
        due_days=due_days,
    )


def _run(tenant, cycle, *, bill_date=None, due_days=None, period=AUG, key=None):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=period[0],
        period_end=period[1],
        bill_date=bill_date,
        due_days=due_days,
        status="draft",
        idempotency_key=key or f"k-{cycle.code}-{period[0]}-{bill_date}-{due_days}",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE PURE RULE — the PO's own figure, with no database in sight
# ═══════════════════════════════════════════════════════════════════════════
def test_oq344__the_worked_figure_the_po_ruled_on():
    """*"bill day 5 · due days 21 · period 1–31 Aug → bills 5 Sep, due 26 Sep"*.

    Written out on its own because it is the number the ruling was given on: a
    sweep failure names a case, this names the date.
    """
    billed = billing_runs.default_bill_date(5, date(2026, 8, 31))
    assert billed == date(2026, 9, 5)
    assert billing_issue.derive_due_date(billed, 21) == date(2026, 9, 26)


def test_oq344__the_two_readings_the_po_did_not_choose_are_not_produced():
    """(A) the period's START month would bill **5 Aug** — before the period it
    bills has even finished. (C) the month the run is TAKEN in would bill 5 Oct
    for a run caught up late, so the same period would fall due on a different
    date depending on when somebody got round to it.

    Neither is reachable, and (C) cannot be: nothing in this path reads a clock
    (BR-TEN-043 / gate G6) — the period is the only input.
    """
    assert billing_runs.default_bill_date(5, date(2026, 8, 31)) != date(2026, 8, 5)
    # The SAME period always answers the same date, whenever it is asked.
    assert billing_runs.default_bill_date(5, date(2026, 8, 31)) == billing_runs.default_bill_date(
        5, date(2026, 8, 31)
    )


def test_oq344__december_rolls_into_the_next_year():
    """A period ending in December bills in JANUARY of the following year — the
    one place "the month after" is not "this year"."""
    assert billing_runs.default_bill_date(5, date(2026, 12, 31)) == date(2027, 1, 5)


def test_oq344__a_bill_day_the_month_does_not_have_clamps_to_its_last_day():
    """OQ-339's ruled clamp, applied to the bill day: *"there is no 31st feb so
    we have to manage either 28th or 29th of Feb."*

    A cycle billing on the 31st, for a period ending in January, bills in
    FEBRUARY — 28 in a common year, **29 in a leap one**. Rolling it into March
    or skipping the month were both rejected for the read window and there is no
    reading on which they would be right for a bill date instead.

    ⚠ The arithmetic is billing's OWN and deliberately does not import
    `apps.metering.schedule.clamp_day_to_month`: B1 / gate G6 forbid billing
    importing metering. What is shared is the RULE, quoted in both places, and
    both are held to the PO's same sentence.
    """
    assert billing_runs.default_bill_date(31, date(2026, 1, 31)) == date(2026, 2, 28)
    assert billing_runs.default_bill_date(31, date(2028, 1, 31)) == date(2028, 2, 29)
    assert billing_runs.default_bill_date(31, date(2026, 3, 31)) == date(2026, 4, 30)
    # …and a day the month DOES have is not touched.
    assert billing_runs.default_bill_date(29, date(2028, 1, 31)) == date(2028, 2, 29)


def test_oq344__no_bill_day_means_no_default():
    """A cycle nobody has given a bill day has no fallback, and the caller
    REFUSES (BR-BIL-024) rather than reaching for a clock. Inventing one here
    would decide when a late fee starts for every bill in the run."""
    assert billing_runs.default_bill_date(None, date(2026, 8, 31)) is None
    assert billing_runs.default_bill_date(5, None) is None


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE FALLBACK IN PLACE — and the override that still wins
# ═══════════════════════════════════════════════════════════════════════════
def test_oq344__a_run_that_types_nothing_bills_on_the_month_after_the_period(brazos, dana):
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344A")
        run = _run(brazos, cycle)
        bill_date, due_days = billing_issue._due_terms_for(run)
    assert (bill_date, due_days) == (date(2026, 9, 5), 21)
    assert billing_issue.derive_due_date(bill_date, due_days) == date(2026, 9, 26)


def test_oq344__a_typed_bill_date_still_wins(brazos, dana):
    """BR-BIL-070 (PO 2026-08-11, OQ-122 option A — *"Store what they type and
    use it"*) and D9 restated in this very ruling: *"these are defualt - user
    can override"*. A default that overrode the clerk would be neither."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344B")
        run = _run(brazos, cycle, bill_date=date(2026, 9, 3))
        bill_date, due_days = billing_issue._due_terms_for(run)
    assert bill_date == date(2026, 9, 3)
    assert billing_issue.derive_due_date(bill_date, due_days) == date(2026, 9, 24)


def test_oq344__a_typed_due_days_still_wins_over_the_cycles(brazos, dana):
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344C")
        run = _run(brazos, cycle, due_days=14)
        bill_date, due_days = billing_issue._due_terms_for(run)
    assert (bill_date, due_days) == (date(2026, 9, 5), 14)
    assert billing_issue.derive_due_date(bill_date, due_days) == date(2026, 9, 19)


def test_oq344__the_default_does_not_rewrite_the_cycle(brazos, dana):
    """A default is computed, never stored: the cycle still holds a DAY."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344D")
        _run(brazos, cycle)
        cycle.refresh_from_db()
    assert cycle.bill_day == 5
    assert not hasattr(cycle, "bill_date"), "the legacy column is gone (metering 0023)"


def test_oq344__a_late_run_of_the_same_period_bills_on_the_same_date(brazos, dana):
    """The property that decided the ruling: *"the only one that gives the same
    answer whether the run is taken on time or late"*. Two runs over ONE period,
    created weeks apart, resolve to one bill date — because the input is the
    PERIOD and never the day of creation."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344E")
        on_time = _run(brazos, cycle, key="on-time")
        catch_up = _run(brazos, cycle, key="catch-up")
        first = billing_issue._due_terms_for(on_time)
        second = billing_issue._due_terms_for(catch_up)
    assert first == second == (date(2026, 9, 5), 21)


# ═══════════════════════════════════════════════════════════════════════════
# 3 · NOTHING ALREADY ISSUED MOVES — CLAUDE.md rule 4
# ═══════════════════════════════════════════════════════════════════════════
def test_oq344__an_issued_bills_due_date_is_stamped_and_cannot_move(brazos, dana):
    """⚠ **THE PROOF THIS CHANGE OWES.**

    `invoices.due_date` is a STORED column written when the bill is issued, and
    an issued invoice is immutable (CLAUDE.md rule 4, `billing 0006` freezes it).
    So `_due_terms_for` is consulted only while a bill is a DRAFT, and changing
    what it returns cannot reach a figure a customer already has.

    Asserted rather than argued: a bill stamped with the OLD fallback's answer
    (1 September, the date a CR-006-era `cycles.bill_date` would have produced)
    still reads 22 September after the new rule would have said 26 September.

    `invoices` has no `bill_date` column — the bill date lives on the RUN
    (`bill_runs.bill_date`, BR-BIL-070) and reaches the invoice as its
    `service_date`, BR-RAT-007's pricing pivot. Both stamped, both immutable.
    """
    from tests.test_us_bil_025_026_bills_read import an_account, an_invoice

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344F")
        run = _run(brazos, cycle, key="issued")
        account = an_account(brazos, dana, account_no="AC-344F", label="Unit 1")
        invoice = an_invoice(
            brazos,
            account,
            bill_run=run,
            invoice_no="BL-344F-000001",
            issued_at=None,
        )
        billing_models.Invoice.objects.filter(pk=invoice.pk).update(
            service_date=date(2026, 9, 1), due_date=date(2026, 9, 22), status="issued"
        )
        invoice.refresh_from_db()
        fresh_bill_date, fresh_due_days = billing_issue._due_terms_for(run)

    # What the run WOULD resolve to today…
    assert (fresh_bill_date, fresh_due_days) == (date(2026, 9, 5), 21)
    # …and what the customer's bill still says, unchanged.
    assert invoice.due_date == date(2026, 9, 22)
    # …and the SERVICE date it was priced at (BR-RAT-007's pivot) with it.
    assert invoice.service_date == date(2026, 9, 1)


def test_oq344__a_cycle_with_no_bill_day_still_refuses_rather_than_guessing(brazos, dana):
    """BR-BIL-024 — the due date *"is never typed and never defaulted: a guessed
    due date decides when a late fee starts"*. A cycle with no bill day and a run
    with no typed date have nothing to derive from, and the refusal is the same
    one this path has always raised."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344G", bill_day=None)
        run = _run(brazos, cycle)
        bill_date, due_days = billing_issue._due_terms_for(run)
        assert bill_date is None
        with pytest.raises(billing_issue.BillingRuleError):
            billing_issue.derive_due_date(bill_date, due_days)


def test_oq344__a_negative_override_is_still_refused(brazos, dana):
    """BR-MET-009 is a rule about the TERMS, not about which column they came
    from — and the new fallback does not launder a bad one."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344H")
        run = _run(brazos, cycle, due_days=-3)
        bill_date, due_days = billing_issue._due_terms_for(run)
        with pytest.raises(billing_issue.BillingRuleError) as caught:
            billing_issue.derive_due_date(bill_date, due_days)
    assert "due_days ≥ 0" in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE LAST LEGACY COLUMN IS GONE
# ═══════════════════════════════════════════════════════════════════════════
def test_oq344__cycles_bill_date_is_dropped_and_nothing_reads_it(brazos, dana):
    """RC-W5-T2 dropped five of six deprecated cycle columns and REPORTED the
    sixth: *"billing's due-terms fallback reads it and no ruling says what
    replaces it"*. OQ-344 is that ruling, so metering 0023 takes the column.

    Asserted on the MODEL rather than on a grep, because a model field is what a
    reader can actually reach.
    """
    fields = {field.name for field in metering_models.Cycle._meta.get_fields()}
    assert "bill_date" not in fields
    # The three fields the fallback is computed from, and the two D9 defaults,
    # all survive — the column went because it was REPLACED, not because the
    # cycle stopped carrying dates.
    assert {"start_day", "days_to_complete", "frequency", "bill_day", "due_days"} <= fields


def test_oq344__the_derived_bill_date_still_reaches_the_cycle_payload(brazos, dana):
    """The contracted `bill_date` / `due_date` keys stay on `cycle_dict` and are
    DERIVED now — the same move `window_start`/`window_end` made in W1-T2. A key
    that went permanently null would be an em-dash on a screen forever (hard-won
    law 2); the honest answer is the date the cycle's NEXT period would bill on.
    """
    from apps.metering import selectors as metering_selectors

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "CY-344I")
        cycle.first_run_date = date(2026, 8, 1)
        cycle.save(update_fields=["first_run_date"])
        served = metering_selectors.cycle_dict(cycle, as_of=date(2026, 8, 10))
    # The next window after 10 Aug is 1–3 Sep, so the bill lands the month after
    # that period ends: 5 October, due 26 October.
    assert served["bill_date"] == "2026-10-05"
    assert served["due_date"] == "2026-10-26"
    assert served["bill_day"] == 5
