# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2857 — the estimate is written and the answer never comes back.
#          PO 2026-08-31, working the deployed bill run: *"i add the estamate
#          and submit - nothing happened - ony estaimated wrritern"*.
# Rules:   BR-BIL-015 (estimate | hold | bill without the service) ·
#          CLAUDE.md rule 3 (a consumption is always stated with its unit) ·
#          the PO's own requirement quoted in EP-BIL-01 §5, *"all the decisions
#          are made on screen and recorded"*
# Tests:   TC-DEF2857-1 · TC-DEF2857-2
# ───────────────────────────────────────────────────────
"""What the clerk typed has to survive the round trip.

THE WRITE WAS NEVER THE PROBLEM, and that is the whole reason this went to a
customer. `POST /billing/runs/{id}/exceptions/{case}/resolve` answers 201,
`bill_run_decisions` holds the choice, the amount and the unit, and every
existing test of the write passes. The defect is entirely in what comes BACK:
`exceptions_dict` mapped the decision's natural key to `row.choice` — the WORD
— and served `quantity` and `unit` null on every phase-1 row, so the 345 kgal a
clerk typed existed in the database and on no screen.

RED-FIRST RECORD (hard-won law 7). Against the pre-fix tree both cases below
failed on the missing member, verbatim:

    KeyError: 'chosen_quantity'

and with the members present but populated from the case rather than the
decision, TC-DEF2857-2 fails on `assert None == '345.000000'`.
"""

from decimal import Decimal

import pytest

from apps.billing import decisions, models as billing_models
from apps.billing import selectors as billing_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)

pytestmark = pytest.mark.django_db


def a_run(tenant, cycle, key):
    """⚠ `bill_date` is SET, and it is not decoration: `prepared_for` refuses a
    run with neither a typed bill date nor a cycle default (BR-BIL-024), so a
    run created without one cannot be read by the very endpoint under test."""
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=SERVICE_DATE,
        idempotency_key=key,
    )


def a_run_with_missing_read(actor, tenant, *, asset_no, account_no):
    """One account in a cycle whose read never arrived — the `missing_read`
    case row, which is the only surface BR-BIL-015 offers *estimate* on."""
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    unit = a_billed_unit(
        actor, tenant, cycle, plan, asset_no=asset_no, label="Unit A", consumption=None
    )
    account = an_account(tenant, unit["id"], account_no)
    return cycle, account


def a_missing_read_row(run):
    rows = [
        row
        for row in billing_selectors.exceptions_dict(run)["rows"]
        if row["case"] == "missing_read"
    ]
    assert len(rows) == 1, f"expected one missing_read row, got {len(rows)}"
    return rows[0]


def test_def2857_tc1__an_undecided_row_says_so_in_every_member(brazos, dana):
    """Born undecided, and the new members are born undecided WITH it.

    BR-BIL-015 and BR-BIL-061 forbid a pre-committed default, so a row nobody
    has answered carries no choice, no quantity and no unit — not a zero, and
    not a figure borrowed from somewhere else on the screen.
    """
    with tenant_ctx(brazos):
        cycle, _account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2857A", account_no="A-28571"
        )
        run = a_run(brazos, cycle, key="def2857|tc1")

        row = a_missing_read_row(run)
        assert row["chosen"] is None
        assert row["chosen_quantity"] is None
        assert row["chosen_unit"] is None


def test_def2857_tc2__the_recorded_estimate_comes_back_with_its_unit(brazos, dana):
    """The PO's 345, on the row, after the round trip.

    The figure is served as a STRING at the column's own scale, exactly as
    every other quantity on this payload is: a browser that parses a decimal
    has become a money path (CLAUDE.md rule 2), and it never travels without
    the unit it is a consumption in (rule 3).
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2857B", account_no="A-28572"
        )
        run = a_run(brazos, cycle, key="def2857|tc2")
        case_row = a_missing_read_row(run)

        decisions.resolve_cases(
            bill_run=run,
            case_id=case_row["id"],
            choice=decisions.CHOICE_ESTIMATE,
            amount=Decimal("345.000000"),
            unit="kgal",
            decided_by=dana.user,
        )

        row = a_missing_read_row(run)
        assert row["chosen"] == "estimate"
        assert row["chosen_quantity"] == "345.000000"
        assert row["chosen_unit"] == "kgal"


def test_def2857_tc3__changing_the_mind_serves_the_decision_that_stands(brazos, dana):
    """An append-only trail still has ONE current answer, and it is the one
    the screen shows. The superseded 345 is not deleted and is not served."""
    with tenant_ctx(brazos):
        cycle, _account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2857C", account_no="A-28573"
        )
        run = a_run(brazos, cycle, key="def2857|tc3")
        case_row = a_missing_read_row(run)

        for figure in ("345.000000", "5.760000"):
            decisions.resolve_cases(
                bill_run=run,
                case_id=case_row["id"],
                choice=decisions.CHOICE_ESTIMATE,
                amount=Decimal(figure),
                unit="kgal",
                decided_by=dana.user,
            )

        row = a_missing_read_row(run)
        assert row["chosen_quantity"] == "5.760000"


def test_def2857_tc4__a_choice_that_is_worth_no_quantity_serves_none(brazos, dana):
    """*Bill without that service* is a real recorded decision with nothing to
    measure. It reads back as a choice and two honest absences — never a 0,
    which on a consumption column is a claim that nobody used anything."""
    with tenant_ctx(brazos):
        cycle, _account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2857D", account_no="A-28574"
        )
        run = a_run(brazos, cycle, key="def2857|tc4")
        case_row = a_missing_read_row(run)

        decisions.resolve_cases(
            bill_run=run,
            case_id=case_row["id"],
            choice=decisions.CHOICE_BILL_WITHOUT_SERVICE,
            decided_by=dana.user,
        )

        row = a_missing_read_row(run)
        assert row["chosen"] == "bill_without_service"
        assert row["chosen_quantity"] is None
        assert row["chosen_unit"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2857 (12-governance/10-defect-log.csv) + EP-BIL-01-bill-run.md §5
# generated: 2026-08-31 by the S31 decision-visibility lane
# checklist: A✔ B=n/a(no frontend half in this file) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED on the pre-fix tree (KeyError: 'chosen_quantity')
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
