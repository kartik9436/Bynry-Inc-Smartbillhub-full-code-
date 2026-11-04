# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2859 — the estimate box is empty although the product already
#          knows the account's own average month. PO 2026-08-31, estimating a
#          missing water read on an account whose neighbours read 5.76 kgal:
#          they typed 345 into a blank box and nothing questioned it.
# Rules:   BR-BIL-015 · BR-BIL-061 (nothing pre-selected) · BR-MET-106 (the
#          stored monthly grain) · CLAUDE.md rule 3 (a quantity with its unit)
# Decision: 12-governance/02-decision-log.md, 2026-08-31 — why a prefilled VALUE
#          is not a pre-selected CHOICE, and why the question fires at 10×.
# ───────────────────────────────────────────────────────
"""The starting figure is METERING's, or there is no starting figure.

⚠ **THE ONE THING THESE CASES EXIST TO PIN IS THAT BILLING AVERAGES NOTHING.**
The figure served on a `missing_read` row is `usage_payload`'s own
`avg_per_month` for that service — the same number the account screen's Usage
tab draws — picked out of the payload, never recomputed. A second averaging in
billing would disagree with the first the day a late read restated a month, and
nothing would say which was right.

RED-FIRST RECORD (hard-won law 7), against the pre-fix tree:

    KeyError: 'basis'

and, with the member present but populated from the case instead of from
metering, `assert None == '5.760000'`.
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import selectors as billing_selectors
from apps.metering import models as metering_models

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
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=SERVICE_DATE,
        idempotency_key=key,
    )


def a_run_with_missing_read(actor, tenant, *, asset_no, account_no):
    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    unit = a_billed_unit(
        actor, tenant, cycle, plan, asset_no=asset_no, label="Unit A", consumption=None
    )
    account = an_account(tenant, unit["id"], account_no)
    return cycle, account


def a_stored_month(tenant, account, service_id, *, month: date, quantity: str, unit: str):
    """One BR-MET-106 row — the grain the basis is read out of.

    Written directly because these rows are the PAST a run starts from, exactly
    as `test_cr038_w8_read_analysis` writes its committed heads.
    """
    return metering_models.MonthlyUsage.objects.create(
        tenant=tenant,
        account=account,
        service_id=service_id,
        period_month=month,
        quantity=Decimal(quantity),
        unit=unit,
        read_count=1,
        estimated_read_count=0,
        source_read_ids=[],
        source_fingerprint=f"def2859|{month}|{quantity}",
        computed_at=datetime(2026, 8, 31, 9, 0, tzinfo=dt_timezone.utc),
    )


def service_id_of(code: str):
    """`tenancy.Service` is the PLATFORM catalogue — ten rows, no tenant column
    (BR-RAT-024). A tenant's participation lives on `TenantService`."""
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Service.objects.get(code=code).id


def missing_read_row(run):
    rows = [
        row
        for row in billing_selectors.exceptions_dict(run)["rows"]
        if row["case"] == "missing_read"
    ]
    assert len(rows) == 1, f"expected one missing_read row, got {len(rows)}"
    return rows[0]


def test_def2859_tc1__an_account_with_no_stored_months_offers_no_figure(brazos, dana):
    """AN ACCOUNT WE KNOW NOTHING ABOUT GETS A BLANK BOX, and that is correct.

    A suggested figure with no history behind it would be an invention, which is
    the guess CLAUDE.md's prime directive forbids. The absence is the answer.
    """
    with tenant_ctx(brazos):
        cycle, _account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2859A", account_no="A-28591"
        )
        run = a_run(brazos, cycle, "def2859|tc1")
        assert missing_read_row(run)["basis"] is None


def test_def2859_tc2__the_basis_is_the_average_month_with_its_unit_and_its_range(brazos, dana):
    """THE FIGURE THE ESTIMATE WINDOW OFFERS, and the range it questions against.

    Three stored months on the run's own axis — 3.20, 8.10 and 5.76 kgal — so
    metering's `avg_per_month` is their mean over 3 months, its `peak` is 8.10
    and its `low` is 3.20. Billing serves those four values and computes none
    of them.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2859B", account_no="A-28592"
        )
        electric = service_id_of("electric")
        # ⚠ EVERY MONTH IS AT OR BEFORE THE RUN'S PERIOD END (2026-06-30).
        # `usage_payload` builds its axis backwards from `today`, which billing
        # passes as the run's own period end and NEVER as a clock read
        # (BR-TEN-043) — so a month dated after it is not on the axis at all and
        # is silently outside the basis. A July row here made the peak read
        # 5.76 instead of 8.10 and looked like an averaging bug.
        for month, quantity in (
            (date(2026, 4, 1), "3.200000"),
            (date(2026, 5, 1), "8.100000"),
            (date(2026, 6, 1), "5.760000"),
        ):
            a_stored_month(brazos, account, electric, month=month, quantity=quantity, unit="kgal")

        run = a_run(brazos, cycle, "def2859|tc2")
        basis = missing_read_row(run)["basis"]

        assert basis is not None, "three stored months and no basis served"
        # NEVER a quantity without its unit (rule 3).
        assert basis["unit"] == "kgal"
        assert basis["high"] == "8.100000"
        assert basis["low"] == "3.200000"
        assert basis["months"] == 3
        # The average is METERING's. Asserted as the mean of the three months so
        # that a second arithmetic appearing in billing goes RED here rather
        # than quietly disagreeing with the account screen.
        assert Decimal(basis["quantity"]) == (
            (Decimal("3.200000") + Decimal("5.760000") + Decimal("8.100000")) / 3
        ).quantize(Decimal(basis["quantity"]))


def test_def2859_tc3__a_window_whose_months_disagree_about_the_unit_offers_nothing(brazos, dana):
    """CLAUDE.md rule 3, at the point it actually bites.

    Two months in different units have no summable figure at all — metering
    says so itself rather than picking one — so the window opens blank instead
    of offering a number in a unit nobody chose.
    """
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2859C", account_no="A-28593"
        )
        electric = service_id_of("electric")
        a_stored_month(
            brazos, account, electric, month=date(2026, 6, 1), quantity="5.760000", unit="kgal"
        )
        # BOTH months are on the axis — see tc2's note. A month dated after the
        # run's period end would be excluded and the disagreement would vanish,
        # which is the shape of a test that cannot fail.
        a_stored_month(
            brazos, account, electric, month=date(2026, 5, 1), quantity="5760.000000", unit="gal"
        )

        run = a_run(brazos, cycle, "def2859|tc3")
        assert missing_read_row(run)["basis"] is None


def test_def2859_tc4__only_a_missing_read_carries_a_basis(brazos, dana):
    """A basis is the answer to *what should this estimate be*, and only one case
    asks it. Every other row says so with a null rather than by lacking the
    member, which a client would read as an older server."""
    with tenant_ctx(brazos):
        cycle, account = a_run_with_missing_read(
            dana, brazos, asset_no="M-2859D", account_no="A-28594"
        )
        electric = service_id_of("electric")
        a_stored_month(
            brazos, account, electric, month=date(2026, 7, 1), quantity="5.760000", unit="kgal"
        )
        run = a_run(brazos, cycle, "def2859|tc4")
        for row in billing_selectors.exceptions_dict(run)["rows"]:
            assert "basis" in row, f"{row['case']} row has no basis member at all"
            if row["case"] != "missing_read":
                assert row["basis"] is None, f"{row['case']} carries an estimate basis"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2859 + 12-governance/02-decision-log.md (2026-08-31)
# generated: 2026-08-31 by the S31 decision-visibility lane
# checklist: A✔ B=n/a(the frontend half is def2857DecisionAnswer.dom.test.tsx) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED on the pre-fix tree (KeyError: 'basis')
# exceptions: E3 the fixture's service is `electric` because that is what
#         `a_billed_unit` provisions; the unit is kgal because the figure under
#         test is the PO's own water case and the unit travels with the row
#         rather than being derived from the service
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
