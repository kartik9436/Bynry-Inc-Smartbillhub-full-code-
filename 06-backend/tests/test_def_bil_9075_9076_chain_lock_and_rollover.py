# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (the one-time bill) · US-MET-016 (a billed read is
#           corrected only with its money fix)
# Rules:    BR-MET-053 (a billed reading is locked; only `correct_billed_read`
#           changes it) · PO 2026-09-30 changes rows 45–46 (a rollover waits for
#           a clerk to accept it) · BR-AST-015
# Defect:   DEF-BIL-9075 · DEF-BIL-9076 (both follow-ups of DEF-BIL-9016)
# ───────────────────────────────────────────────────────
"""TWO FOLLOW-UPS OF DEF-BIL-9016, BOTH ON A ONE-TIME BILL.

`DEF-BIL-9075` — since 9016 a bill charges for EVERY reading chained back to
the period's opening dial, and only the closing reading was locked at issue. A
clerk could then supersede the 1 Nov reading the bill had charged 200 kWh for,
on the plain path with no money fix, and the bill and the meter history would
disagree. Every reading in the chain is now locked.

`DEF-BIL-9076` — a 5-digit dial opening at 99,800, wrapping to 240 on 1 Nov
and read 700 on 13 Nov used **900 kWh**. The chain stops at a wrap so that a
rollover stays the clerk's to accept (PO 2026-09-30), but a one-time bill has
no last-bill anchor to ask, so it billed **460** and said nothing. It is now
HELD by name until the rollover is accepted, and then bills all 900
(**$90.00** at winter's $0.10).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.billing import issue, one_time, one_time_answer, runs, single
from apps.billing import models as billing_models
from apps.billing.exceptions import BillingRuleError
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from core import errors

from tests.test_def_bil_9016_chained_period_reads import a_seasonal_meter
from tests.test_oq234_season_split import WINTER_END, WINTER_START, _round, _usage
from tests.test_us_bil_005_issue import TEMPLATE_ID, TEMPLATE_VERSION
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _draft(account, **extra):
    body = one_time.create(
        one_time.OneTimeRequest(
            account_id=str(account.id),
            kind=one_time.KIND_INTERIM,
            period_start=WINTER_START,
            period_end=WINTER_END,
            bill_date=WINTER_END,
            due_days=21,
            **extra,
        ),
        run_by=None,
        actor=None,
    )
    return billing_models.Invoice.objects.get(pk=body["invoice_id"])


def _read_on(asset_no, day):
    return metering_models.MeterRead.objects.get(
        asset__asset_no=asset_no, channel="total", read_at__date=day
    )


# ── DEF-BIL-9075 · every reading the bill charged for is locked ────────────


def test_def_bil_9075_every_reading_in_the_chain_is_locked_at_issue(brazos, dana):
    with tenant_ctx(brazos):
        account, _cycle = a_seasonal_meter(
            brazos,
            dana,
            start=WINTER_START,
            end=WINTER_END,
            middle="2026-11-01",
            account_no="A-90751",
            asset_no="M-9075",
        )
        # Issue stamps every line's ledger account; the fixture's four tax
        # authorities carry none, so this bill is priced without them — the
        # subject here is the lock, not the tax.
        rating_models.PlanTaxRule.objects.filter(tenant=brazos).delete()
        draft = _draft(account)
        assert [(line.quantity, _round(line.amount)) for line in _usage(draft)] == [
            (Decimal("300"), Decimal("30.00"))
        ]
        issue.issue_invoice(
            draft,
            issued_at=datetime(2026, 11, 14, 12, 0, tzinfo=UTC),
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
        )
        middle = _read_on("M-9075", date(2026, 11, 1))
        closing = _read_on("M-9075", WINTER_END)
        opening = _read_on("M-9075", WINTER_START)
        assert (middle.lifecycle, closing.lifecycle) == ("billed", "billed")
        # The opening dial's own usage belongs to the period before: not this
        # bill's to lock.
        assert opening.lifecycle == "committed"
        with pytest.raises(errors.BizError) as refusal:
            metering_services.supersede_read(
                dana, middle.id, {"value": "1150", "reason": "keyed wrong"}
            )
    assert refusal.value.code == errors.BIZ_LOCKED
    assert refusal.value.br_ref == "BR-MET-053"


# ── DEF-BIL-9076 · a rollover inside the period waits for the clerk ────────


def a_wrapped_meter(tenant, actor, *, account_no, asset_no):
    """Winter $0.10. A 5-digit dial: 99,800 (opening) → 240 (1 Nov, wrapped:
    metering stored 440) → 700 (13 Nov, 460). Used: 900 kWh."""
    account, _cycle = a_seasonal_meter(
        tenant,
        actor,
        start=WINTER_START,
        end=WINTER_END,
        middle="2026-11-01",
        account_no=account_no,
        asset_no=asset_no,
        dials=(("99800", "99400", "400"), ("240", "99800", "440"), ("700", "240", "460")),
    )
    return account


def test_def_bil_9076_an_unaccepted_rollover_holds_the_one_time_bill_by_name(brazos, dana):
    with tenant_ctx(brazos):
        account = a_wrapped_meter(brazos, dana, account_no="A-90761", asset_no="M-9076")
        prepared = single.prepare_single_bill(
            account_id=str(account.id),
            period_start=WINTER_START,
            period_end=WINTER_END,
            service_date=WINTER_END,
        )
        assert [problem.reason for problem in prepared.blocked] == [runs.POSSIBLE_ROLLOVER]
        assert "rolled over" in prepared.blocked[0].detail
        with pytest.raises(BillingRuleError) as held:
            _draft(account)
    assert "rolled over" in str(held.value)


def test_def_bil_9077_the_preview_refusal_carries_what_the_accept_control_shows(brazos, dana):
    """DEF-BIL-9077 — the one-time screen's Accept-rollover control is drawn
    from the preview's 422: the meter by its NUMBER, the three dials
    (99,800 → 240 → 700) and the usage they imply (900 kWh). No id."""
    with tenant_ctx(brazos):
        account = a_wrapped_meter(brazos, dana, account_no="A-90771", asset_no="M-9077")
        internal = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=WINTER_START,
                period_end=WINTER_END,
                bill_date=WINTER_END,
                due_days=21,
            )
        )
        refusal = one_time_answer.pricing_refusal(internal["blocked"][0])
        accepted = one_time.preview(
            one_time.OneTimeRequest(
                account_id=str(account.id),
                kind=one_time.KIND_INTERIM,
                period_start=WINTER_START,
                period_end=WINTER_END,
                bill_date=WINTER_END,
                due_days=21,
                accepted_rollovers=("electric",),
            )
        )
    assert refusal.message_key == runs.ROLLOVER_HELD_KEY
    facts = {key: refusal.params.get(key) for key in ("reason", "service_code", "meter", "unit")}
    assert facts == {
        "reason": runs.POSSIBLE_ROLLOVER,
        "service_code": "electric",
        "meter": "M-9077",
        "unit": "kWh",
    }
    dials = [
        Decimal(refusal.params[key]) for key in ("from", "to", "closing", "suggested_quantity")
    ]
    assert dials == [Decimal("99800"), Decimal("240"), Decimal("700"), Decimal("900")]
    # Accepted, the preview prices the whole period: 900 × $0.10.
    assert internal["ready"] == 0 and accepted["ready"] == 1 and not accepted["blocked"]


def test_def_bil_9076_an_accepted_rollover_bills_the_whole_period(brazos, dana):
    with tenant_ctx(brazos):
        account = a_wrapped_meter(brazos, dana, account_no="A-90762", asset_no="M-9077")
        draft = _draft(account, accepted_rollovers=("electric",))
        assert [(line.quantity, _round(line.amount)) for line in _usage(draft)] == [
            (Decimal("900"), Decimal("90.00"))
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-BIL-9075 · DEF-BIL-9076 · DEF-BIL-9016 · BR-MET-053 · PO 2026-09-30 rows 45–46
# generated: 2026-10-02 by the season-change-reading lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the one-time screen's accept control — see DEF-BIL-9076's row) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest (PostgreSQL 16, config.settings.pgtest) ✔
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
