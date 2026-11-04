# ── Trace ──────────────────────────────────────────────
# Change:   DEF-REP-7010 — the Billing Register's USAGE cell, reported by the
#           Product Owner from the deployed build (`v2.380.3`, screen
#           `RPT-02`): *"`0 cart · 0 connection · 0 kW · 15.2 kgal` — three
#           zeros and one real figure"*, and the rule they set against it:
#           *"Show only what was actually used… A zero that MEANS something (a
#           meter read of zero) is not the same as a measure that does not
#           apply — do not collapse the two."*
# Rules:    `BR-RAT-090` (an unmetered service is billed by a COUNT of the
#           unit's assets) · `BR-TEN-1180` (`capacity` is the basis that means
#           exactly that) · CLAUDE.md hard rule 3 (a quantity always carries
#           its unit) · hard rule 1 (tenant scoping) · hard-won law 7 clause
#           (2) — what would make this check pass WRONGLY.
# Impacts:  apps/billing/reporting.py · apps/billing/tenancy_seam.py ·
#           apps/reports/queries.py
# ───────────────────────────────────────────────────────
"""**TWO KINDS OF ZERO, AND ONLY THE READ MODEL CAN TELL THEM APART.**

`0 cart` and `0 kgal` are the same three characters on the wire and they are
not the same fact. One says *nobody has a cart at this unit*; the other says
*the meter was read, and it read zero* — which is news, and is the figure a
clerk chasing a dead meter is looking for.

**The screen cannot work it out.** A front end sniffing the UNIT would be the
hand-typed list the skill's §12 forbids and would be wrong the first time a
utility called its carts something else. So the register says which is which,
and this file is the contract for that sentence.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):

  · **A tenant that declares nothing.** `capacity_service_codes()` degrades to
    an empty set, every unit comes back measured, and *"kgal is measured"*
    passes over a register that has learned nothing. So the counted case and
    the measured case are asserted on the SAME bill, in the same call.
  · **A unit that no line ever produced.** Asserting `"cart" not in measured`
    would pass on a bill with no trash line at all. Every case below asserts
    the unit IS in `usage` first.
  · **SQLite.** Nothing here is a `WHERE`; the aggregation is a Python loop
    over the page's lines, so the default suite decides it honestly. The
    PAGING proof is `10-scripts/cr142_p2_read_path_cost.py` and is separate.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import reporting as billing_reporting
from apps.reports import queries

from tests.test_us_bil_025_026_bills_read import a_line, an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc
WINDOW_START = date(2026, 7, 1)
WINDOW_END = date(2026, 7, 31)


def _service(code):
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Service.objects.get(code=code)


def _declare(tenant, code, basis):
    """Enable `code` for this tenant on `basis`.

    ⚠ **THIS IS THE DECLARATION THE WHOLE FEATURE TURNS ON**, and it is a
    tenant's own setting rather than a property of the service: `BR-TEN-1180`
    gives `tenant_services.billing_basis` three values and
    `unmetered_service_codes()` filters on `capacity` ALONE.
    """
    from apps.tenancy import models as tenancy_models

    row, _ = tenancy_models.TenantService.objects.get_or_create(
        tenant=tenant, service=_service(code), defaults={"enabled": True}
    )
    row.enabled = True
    row.billing_basis = basis
    row.save(update_fields=["enabled", "billing_basis"])
    return row


def _a_mixed_bill(tenant, account):
    """One ISSUED bill carrying all three shapes of zero and non-zero.

    `trash` is CAPACITY and its cart count is **0** — nobody has a cart here.
    `water` is METERED and its meter read **0** — a real reading of nothing.
    `electric` is METERED and read **684 kWh** — the ordinary case, present so
    a filter that dropped everything would be visible.
    """
    invoice = an_invoice(
        tenant,
        account,
        invoice_no="BL-2607-000001",
        issued_at=datetime(2026, 7, 9, 9, 0, tzinfo=UTC),
    )
    a_line(
        tenant,
        invoice,
        account,
        service=_service("electric"),
        quantity=Decimal("684"),
        unit="kWh",
        amount=Decimal("82.08"),
    )
    a_line(
        tenant,
        invoice,
        account,
        service=_service("water"),
        description="Water usage",
        quantity=Decimal("0"),
        unit="kgal",
        amount=Decimal("0.00"),
    )
    a_line(
        tenant,
        invoice,
        account,
        service=_service("trash"),
        description="Trash carts",
        quantity=Decimal("0"),
        unit="cart",
        amount=Decimal("0.00"),
    )
    return invoice


def _register(tenant):
    return billing_reporting.billing_register(start=WINDOW_START, end=WINDOW_END)


# ═══════════════════════════════════════════════════════════════════════════
# THE READ MODEL SAYS WHICH UNITS CAME FROM A COUNT
# ═══════════════════════════════════════════════════════════════════════════
def test_a_capacity_service_unit_is_reported_as_counted(brazos, dana):
    with tenant_ctx(brazos):
        _declare(brazos, "trash", "capacity")
        account = an_account(brazos, dana)
        _a_mixed_bill(brazos, account)

        row = _register(brazos)["rows"][0]
        units = {unit for _amount, unit in row.usage}

        # PRESENCE first — `"cart" not in measured` would pass on a bill that
        # never had a trash line.
        assert units == {"cart", "kWh", "kgal"}, units
        assert row.counted_units == ("cart",), row.counted_units


def test_a_metered_zero_is_not_counted__the_POs_own_caveat(brazos, dana):
    with tenant_ctx(brazos):
        _declare(brazos, "trash", "capacity")
        account = an_account(brazos, dana)
        _a_mixed_bill(brazos, account)

        row = _register(brazos)["rows"][0]
        # `0 kgal` is a meter that was read. It is NOT in `counted_units`, so
        # the screen keeps it — which is the half of the PO's sentence that is
        # easy to lose while fixing the other half.
        assert ("0.000000" in str(dict((u, a) for a, u in row.usage)["kgal"])) or (
            dict((u, a) for a, u in row.usage)["kgal"] == Decimal("0")
        )
        assert "kgal" not in row.counted_units


def test_a_tenant_declaring_no_capacity_basis_counts_nothing(brazos, dana):
    with tenant_ctx(brazos):
        _declare(brazos, "trash", "metered")
        account = an_account(brazos, dana)
        _a_mixed_bill(brazos, account)

        row = _register(brazos)["rows"][0]
        # The register renders byte-for-byte what it rendered before this field
        # existed. `cart` is still a unit on the bill; it is simply not a count.
        assert "cart" in {unit for _amount, unit in row.usage}
        assert row.counted_units == ()


def test_a_reading_wins_when_a_count_and_a_reading_share_a_unit(brazos, dana):
    """Water and sewer are both metered in kgal — a shared unit is real.

    If a capacity line ever met a metered line on one unit, calling that unit
    *counted* would hide a genuine reading. The reading wins, always.
    """
    with tenant_ctx(brazos):
        _declare(brazos, "trash", "capacity")
        account = an_account(brazos, dana)
        invoice = an_invoice(
            brazos, account, invoice_no="BL-2607-000002",
            issued_at=datetime(2026, 7, 9, 9, 0, tzinfo=UTC),
        )
        a_line(
            brazos, invoice, account, service=_service("trash"),
            description="Trash, in kgal for the sake of argument",
            quantity=Decimal("0"), unit="kgal", amount=Decimal("0.00"),
        )
        a_line(
            brazos, invoice, account, service=_service("water"),
            description="Water usage", quantity=Decimal("12"), unit="kgal",
            amount=Decimal("36.00"),
        )

        row = _register(brazos)["rows"][0]
        assert "kgal" in {unit for _amount, unit in row.usage}
        assert row.counted_units == (), row.counted_units


# ═══════════════════════════════════════════════════════════════════════════
# AND IT REACHES THE WIRE, WHICH IS WHERE THE SCREEN READS IT
# ═══════════════════════════════════════════════════════════════════════════
def test_the_wire_carries_measured_per_entry(brazos, dana):
    with tenant_ctx(brazos):
        _declare(brazos, "trash", "capacity")
        account = an_account(brazos, dana)
        _a_mixed_bill(brazos, account)

        payload = queries.billing_register(
            {"from": WINDOW_START.isoformat(), "to": WINDOW_END.isoformat()}
        )
        usage = {entry["unit"]: entry for entry in payload["rows"][0]["usage"]}
        assert set(usage) == {"cart", "kWh", "kgal"}, set(usage)
        assert usage["cart"]["measured"] is False
        assert usage["kgal"]["measured"] is True
        assert usage["kWh"]["measured"] is True


def test_quantity_without_a_declaration_is_measured(brazos, dana):
    """`_quantity`'s default keeps every OTHER report in the product unchanged."""
    assert queries._quantity([(Decimal("0"), "cart")]) == [
        {"quantity": "0", "unit": "cart", "measured": True}
    ]
