# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-9009 (second half) — with the Answer for all fixed, the
#           40,015-account re-walk of 2.438.2 still drafted 5 bills: 40,004
#           accounts broke with `rating_refused_to_price` because SEWER bills
#           a percentage of WATER's volume, and water's usage had been told to
#           wait for the next bill
# Rulings:  PO 2026-09-30 fixed-charge case 1 (*Bill base, usage later*) ·
#           changes row 1 / BR-RAT-1015 (sewer follows water)
# Tracker:  BULK-CHG-48 · BULK-CHG-1
# ───────────────────────────────────────────────────────
"""When water's usage waits for the next bill, sewer's usage waits with it.

Sewer on the `usage` basis bills 40% of WATER's metered volume. *Bill base,
usage later* on water removed water's quantity from this bill, so the engine
refused sewer (`BasisUnavailable`: *"this bill carries no billed quantity for
'water'"*) and the WHOLE account broke. The judgment (decision log
2026-10-02): a service priced as a share of a deferred service is deferred
with it. Sewer's base bills now; its usage comes next bill, with water's.

RED FIRST on 2.438.2: `price_account` raises the refusal.
"""

from __future__ import annotations

from decimal import Decimal

from apps.billing import decisions, models, runs
from apps.billing.contracts import ServiceReading

from tests.test_br_bil_300_services_rulings_2026_09_30 import (  # noqa: F401
    _gather,
    _install,
    _lines,
    _rolled_back_resolution_chain,
    _world,
)


def _standing(choice):
    row = models.BillRunDecision(case="missing_read", choice=choice, account_id="acc-930")
    row.from_standing_answer = True
    return row


def test_def_bil_9009__bill_base_usage_later_on_water_takes_sewer_with_it(monkeypatch):
    _install(
        monkeypatch,
        _world(
            plan_services=["water", "sewer"], unit_services=["water"], assets={"water": ["m-1"]}
        ),
    )
    data = _gather([ServiceReading(service_code="water", consumption=None)])
    answered = decisions._apply_to_account(data, [_standing(decisions.CHOICE_BILL_WITHOUT_SERVICE)])

    priced = runs.price_account(answered)  # raised BasisUnavailable before the fix

    for service in ("water", "sewer"):
        kinds = [line.kind for line in _lines(priced, service)]
        assert "usage" not in kinds, (service, kinds)
    assert [line.amount for line in _lines(priced, "water") if line.kind == "base"] == [
        Decimal("8.00")
    ]
    assert [line.amount for line in _lines(priced, "sewer") if line.kind == "base"] == [
        Decimal("5.00")
    ]
    assert set(answered.usage_next_bill) >= {"water", "sewer"}
