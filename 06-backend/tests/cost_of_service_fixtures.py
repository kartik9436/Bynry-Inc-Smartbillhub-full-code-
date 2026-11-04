"""The LE-11 purchase set — CI-1..CI-9, $51,902.50 — captured through the REAL
service, and the billed volumes the reconciliation reads against them.

NOT a test module and deliberately not named like one: pytest collects
`tests/test_*.py`, and a helper that defines pytest fixtures AND is imported by
several test modules registers those fixtures twice (`tests/test_us_led_001_
posting.py` records what that does — every test in the importing file errors
with `assert not self._finalizers` before it runs). So this file holds PLAIN
FUNCTIONS only, in the shape of `tests/ledger_le_fixtures.py`.

════════════════════════════════════════════════════════════════════════════
EVERY FIGURE HERE IS COPIED FROM THE WORKBOOK. NONE IS COMPUTED.
════════════════════════════════════════════════════════════════════════════
`04-docs/05-modules/09-ledger/08-worked-examples.md` §LE-11..LE-14, authored
2026-08-15 with EP-LED-06. A fixture that re-derived a total would agree with a
broken implementation — so the nine amounts, the nine volumes and the three
billed volumes are transcribed, and only the ASSERTIONS do arithmetic.

The workbook states the unit prices so every amount is checkable by hand:
water **$3.10/kgal** (400 × 3.10 = 1,240.00 · 250 × 3.10 = 775.00 · 100 × 3.10
= 310.00 · 50 × 3.10 = 155.00 · 200 × 3.10 = 620.00; 1,000 kgal × 3.10 =
3,100.00 ✔) · electric **$0.0685/kWh** (412,000 × 0.0685 = 28,222.00 ✔) · gas
**$4.30/MMBtu** (1,450 × 4.30 = 6,235.00 ✔).

════════════════════════════════════════════════════════════════════════════
ONE DEPARTURE FROM THE WORKBOOK'S TENANT, AND IT IS A FIXTURE FACT
════════════════════════════════════════════════════════════════════════════
LE-11's Brazos Bend sells **Electric · Water · Sewer · Trash · Gas**. The
repo's `brazosbend_payload()` provisions **Electric + Water**, and it is the
signed US-TEN-001 §4 test data that a dozen other test modules build on — so it
is NOT changed here. `enable_le11_services()` switches Sewer, Trash and Gas on
through the REAL `update_tenant_service` path, which is also what makes
US-LED-017 TC-3 (*"5140 is minted at that moment"*) a real assertion rather than
a seeded one.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from apps.ledger import cost_capture

# ── the month, and the moments (BR-TEN-043: nothing reads a clock) ──────────
JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)
AUGUST_START = date(2026, 8, 1)
AUGUST_END = date(2026, 8, 31)

#: LE-9's close, reused: *"July closed Aug 5"*.
JULY_CLOSED_AT = datetime(2026, 8, 5, 16, 30, tzinfo=dt_timezone.utc)
#: LE-13: CI-4 voided 2026-08-03 by Norma Reyes.
VOIDED_AT = datetime(2026, 8, 3, 10, 15, tzinfo=dt_timezone.utc)
#: LE-14: the July batch sent 2026-08-08.
EXPORTED_AT = datetime(2026, 8, 8, 9, 0, tzinfo=dt_timezone.utc)

#: LE-11's own words: *"the same tenant, actors and month as LE-1..LE-9"*, and
#: the five services Brazos Bend sells. Broadband is deliberately absent — TC-1
#: turns on 5145 NOT being seeded.
LE11_SERVICES: tuple[str, ...] = ("electric", "water", "sewer", "trash", "gas")

#: LE-11's fixture table, transcribed. `(reference, date, supplier, service,
#: volume, unit, amount, gl_code)`.
CI_ROWS: tuple[tuple[str, date, str, str, Decimal | None, str | None, Decimal, str], ...] = (
    (
        "RS-2607-0141",
        date(2026, 7, 6),
        "City of Rosenberg — Bulk Water Supply",
        "water",
        Decimal("400000"),
        "gal",
        Decimal("1240.00"),
        "5110",
    ),
    (
        "RS-2607-0158",
        date(2026, 7, 13),
        "City of Rosenberg — Bulk Water Supply",
        "water",
        Decimal("250000"),
        "gal",
        Decimal("775.00"),
        "5110",
    ),
    (
        "RS-2607-0175",
        date(2026, 7, 20),
        "City of Rosenberg — Bulk Water Supply",
        "water",
        Decimal("100000"),
        "gal",
        Decimal("310.00"),
        "5110",
    ),
    (
        "RS-2607-0192",
        date(2026, 7, 27),
        "City of Rosenberg — Bulk Water Supply",
        "water",
        Decimal("50000"),
        "gal",
        Decimal("155.00"),
        "5110",
    ),
    (
        "RS-2607-0208",
        date(2026, 7, 31),
        "City of Rosenberg — Bulk Water Supply",
        "water",
        Decimal("200000"),
        "gal",
        Decimal("620.00"),
        "5110",
    ),
    (
        "BVPC-070026",
        date(2026, 7, 31),
        "Brazos Valley Power Cooperative",
        "electric",
        Decimal("412000"),
        "kWh",
        Decimal("28222.00"),
        "5100",
    ),
    (
        "GCGT-2607-88",
        date(2026, 7, 31),
        "Gulf Coast Gas Transmission",
        "gas",
        Decimal("1450"),
        "MMBtu",
        Decimal("6235.00"),
        "5140",
    ),
    (
        "HPV-4471",
        date(2026, 7, 15),
        "Hillcrest Pipe & Valve",
        "operations_maintenance",
        None,
        None,
        Decimal("1845.50"),
        "5200",
    ),
    (
        "KMW-2026-118",
        date(2026, 7, 22),
        "Katy Meter Works (40 replacement meters)",
        "infrastructure",
        None,
        None,
        Decimal("12500.00"),
        "5300",
    ),
)

# ── LE-11 / LE-13 / LE-14's figures, transcribed ───────────────────────────
LE11_REGISTER_TOTAL = Decimal("51902.50")
LE13_TOTAL_AFTER_EDIT = Decimal("51904.90")  # CI-3 310.00 → 312.40
LE13_TOTAL_AFTER_VOID = Decimal("51747.50")  # CI-4 155.00 voided
LE11_WATER_COST = Decimal("3100.00")
LE11_WATER_VOLUME = Decimal("1000000")
LE11_ELECTRIC_VOLUME = Decimal("412000")
LE11_GAS_VOLUME = Decimal("1450")

#: LE-12: *"Billed volumes for the same month … Water 910,000 gal · Electric
#: 389,340 kWh · Gas 18,900 ccf"*.
BILLED_WATER = Decimal("910000")
BILLED_ELECTRIC = Decimal("389340")
BILLED_GAS = Decimal("18900")

#: The two figures the rule exists to produce, and the one it exists to hide.
WATER_PCT = Decimal("9.00")
ELECTRIC_PCT = Decimal("5.50")
SUPPRESSED_PCT = Decimal("-13.75")  # never printed anywhere — asserted absent
WATER_PCT_AFTER_VOID = Decimal("4.21")
#: OQ-202's other reading: June's 884,500 gal in July's denominator.
ISSUE_BASIS_BILLED_WATER = Decimal("884500")
ISSUE_BASIS_PCT = Decimal("11.55")

#: The isolation fixture (US-LED-018 TC-10 / J25 step 12).
LSR_REFERENCE = "LSR-BW-0091"
LSR_SUPPLIER = "City of Bandera"
LSR_DATE = date(2026, 7, 18)
LSR_VOLUME = Decimal("220000")
LSR_AMOUNT = Decimal("842.00")
LSR_BILLED = Decimal("214500")
LSR_PCT = Decimal("2.50")

#: LE-14's cost section, per GL account.
LE14_COST_ROWS: dict[str, Decimal] = {
    "5100": Decimal("28222.00"),
    "5110": Decimal("3100.00"),
    "5140": Decimal("6235.00"),
    "5200": Decimal("1845.50"),
    "5300": Decimal("12500.00"),
}
#: LE-14's QBO refs, set by Norma before the export can go (TC-5).
LE14_QBO_REFS: dict[str, str] = {
    "5100": "412",
    "5110": "413",
    "5140": "414",
    "5200": "420",
    "5300": "430",
}


#: BR-TEN-022 — the fiscal calendar the ledger's period boundaries come from.
#: The same monthly settings `tests/test_us_led_012_accrual_auto_reverse.py`
#: uses, so July is 2026-07-01 … 2026-07-31 in both files and no second calendar
#: exists in the suite.
FISCAL_SETTINGS = {
    "country": "United States",
    "timezone": "America/Chicago",
    "language": "en-US",
    "first_day_of_week": "sunday",
    "number_format": "1,234.56",
    "date_format": "MM/DD/YYYY",
    "time_format": "12-hour",
    "fy_start_month": 1,
    "fy_start_day": 1,
    "accounting_method": "accrual",
    "close_cadence": "monthly",
    "close_day": "3rd business day",
    "lock_closed_periods": True,
}


def with_monthly_fiscal_year(actor) -> None:
    """Give the tenant a fiscal calendar, through the real Settings service.

    Without it `close.period_window` REFUSES by design — *"this tenant has no
    fiscal settings"* — which is correct product behaviour and useless as a test
    precondition, so every capture test states the calendar first.
    """
    from apps.tenancy import services as tenancy_services

    tenancy_services.save_regional_settings(actor, dict(FISCAL_SETTINGS))


def enable_le11_services(actor) -> None:
    """Switch Sewer, Trash and Gas on through the REAL S8 write path.

    Not an ORM shortcut on purpose: this is also US-LED-017 TC-3's assertion
    surface — *"5140 is minted at that moment, not before"* — and a cost account
    that only appears when a test calls the ledger directly is not a feature
    (hard-won law 2).
    """
    from apps.tenancy import services as tenancy_services

    for code in ("sewer", "trash", "gas"):
        tenancy_services.update_tenant_service(actor, code, {"enabled": True})


def capture_le11_month(actor, *, skip=(), volumeless=()) -> dict[str, object]:
    """Capture CI-1..CI-9 through `cost_capture.capture_supplier_invoice`.

    `skip` drops references entirely; `volumeless` captures those references
    COST-ONLY, which is the degraded fixture BR-LED-031's ABSENT case turns on
    (*"CI-5 captured cost-only → Water volume 800,000 gal over 4 of 5
    purchases"*).

    Returns `{reference: captured row}` so a test can void or edit by name
    rather than by index.
    """
    captured: dict[str, object] = {}
    for reference, when, supplier, service, volume, unit, amount, _code in CI_ROWS:
        if reference in skip:
            continue
        cost_only = reference in volumeless
        captured[reference] = cost_capture.capture_supplier_invoice(
            actor,
            invoice_date=when,
            service=service,
            supplier_name=supplier,
            amount=amount,
            currency="USD",
            volume=None if cost_only else volume,
            volume_unit=None if cost_only else unit,
            reference=reference,
        )
    return captured
