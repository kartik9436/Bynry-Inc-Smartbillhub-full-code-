"""CR-060 T3 — THE SUB-METERING DEMO TENANT, which the fixtures did not have.

NOT a test module and deliberately not named like one: pytest collects
`tests/test_*.py`, and a helper that defines pytest fixtures AND is imported by
several test modules registers those fixtures twice. So this file holds PLAIN
FUNCTIONS only, in the shape of `tests/cost_of_service_fixtures.py` and
`tests/ledger_le_fixtures.py`.

════════════════════════════════════════════════════════════════════════════
WHY IT EXISTS, IN CR-060's OWN WORDS
════════════════════════════════════════════════════════════════════════════
*"TEST DATA IS THE GAP THAT BLOCKS TWO CHANGES. There is ONE demo tenant and it
is a utility. C8 and C9 are the sub-metering variants and nothing in the
fixtures can exercise them. Before either can be tested, the demo spec needs a
second tenant that is a sub-metering company: a master account, several
buildings, member accounts under each, and a supplier invoice per building."*

**T3 IS A FIXTURE TASK WITH NO PRODUCT CODE IN IT**, and it blocks two of the
three "must" changes. What it builds is exactly the four things named above,
plus the one shape §11 asks for by name: *"a per-building recovery with ONE
building deliberately missing its volume so the absent case is exercised rather
than assumed."*

════════════════════════════════════════════════════════════════════════════
THE FIXTURE, AND EVERY FIGURE IN IT IS CHECKABLE BY HAND
════════════════════════════════════════════════════════════════════════════
**Bayou Bend Submetering LLC** — three buildings, water only, July 2026.

Water is bought from the city at the master meter of each building and billed
on to the members inside it. The unit price is **$3.10 per kgal**, which is the
LE-11 workbook's own price for exactly this commodity, so every amount below is
`kgal x 3.10` and nothing here invents a rate.

    BUILDING            BOUGHT           COST        BILLED       UNACCOUNTED
    Cypress Court      600,000 gal   $1,860.00    570,000 gal        5.00%
    Magnolia Row       400,000 gal   $1,240.00    320,000 gal       20.00%
    Sabine Lofts       250,000 gal     $775.00    237,500 gal      ABSENT
    ---------------------------------------------------------------------
    Total                            $3,875.00

    Cypress:  (600,000 - 570,000) / 600,000 = 30,000 / 600,000 = 0.05  ->  5.00%
    Magnolia: (400,000 - 320,000) / 400,000 = 80,000 / 400,000 = 0.20  -> 20.00%
    Total:    1,860.00 + 1,240.00 + 775.00 = 3,875.00

**MAGNOLIA ROW IS THE LEAK AND IT IS THE POINT OF THE WHOLE FIXTURE.** Blended
across the tenant the three buildings read
`(1,250,000 - 1,127,500) / 1,250,000 = 9.80%` — a number that describes no
building and points at nothing. Per building, Magnolia is 20.00% and is the
FIRST ROW. That difference is C9, and this fixture is what makes it provable
rather than argued.

**SABINE LOFTS IS THE ABSENT CASE AND IT IS DELIBERATE.** Its second purchase
(SB-2607-0044, $310.00) is captured with NO volume, so BR-LED-031's
all-or-nothing rule suppresses Sabine's percentage and names the count — *"no
volume captured for 1 of 2 water purchases this period"*. **The two figures it
protects are the two things C9 is really about:** the partial denominator would
read `(150,000 - 237,500) / 150,000 = -58.33%`, a building that delivered more
water than it bought; and under the OLD tenant-wide rule that ONE cost-only
invoice suppressed water for every building at once, so Cypress and Magnolia
would both go dark because of a missing figure at a third address.

════════════════════════════════════════════════════════════════════════════
WHAT IS DELIBERATELY NOT HERE
════════════════════════════════════════════════════════════════════════════
* **NO `paid_on` AND NO POSTING.** Capture still posts nothing (BR-LED-028,
  OQ-200 ruled 2026-08-16). C1 / T6 changes that and *"needs a RECORDED RULING
  first"*; a fixture that anticipated it would be a lane answering a question
  the PO holds.
* **NO BILL RUN.** The billed side is built as issued invoices with usage lines
  through the ORM, exactly as `tests/test_us_led_020_reconciliation.py` already
  does and for the reason written there: driving a full run would make a
  failure in the LEDGER's reconciliation indistinguishable from a failure in
  billing. The SHAPE is the real one — an issued invoice, a usage line, a
  quantity and its unit — which is all the seam reads.
* **NO SEEDER ENTRY.** This is the pytest fixture that unblocks C8's and C9's
  tests. The DEMO SEEDER's second tenant (a thing a human clicks through) is
  the same specification pointed at `load_sample_data`, and it is written up in
  `08-qa/04-fixtures/02-demo-tenant-spec.md` §7 rather than half-built here.
"""

from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.ledger import cost_capture
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services

# ── the month, and the moments (BR-TEN-043: nothing reads a clock) ──────────
JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)
ISSUED_AT = datetime(2026, 8, 3, 14, 0, tzinfo=dt_timezone.utc)

#: LE-11's own bulk-water price, reused rather than re-invented: $3.10/kgal.
WATER_PRICE_PER_KGAL = Decimal("3.10")

#: The three buildings. `(key, address, bought_gal, billed_gal, expected_pct)`.
#: `expected_pct` is `None` where the fixture deliberately withholds a volume.
BUILDINGS: tuple[tuple[str, str, Decimal, Decimal, Decimal | None], ...] = (
    ("cypress", "1400 Cypress Court", Decimal("600000"), Decimal("570000"), Decimal("5.00")),
    ("magnolia", "88 Magnolia Row", Decimal("400000"), Decimal("320000"), Decimal("20.00")),
    ("sabine", "3 Sabine Lofts", Decimal("250000"), Decimal("237500"), None),
)

#: The purchases, per building. `(reference, invoice_date, volume_gal, amount)`.
#: A `None` volume is the ABSENT case — see the module docstring.
PURCHASES: dict[str, tuple[tuple[str, date, Decimal | None, Decimal], ...]] = {
    "cypress": (
        ("CY-2607-0011", date(2026, 7, 8), Decimal("350000"), Decimal("1085.00")),
        ("CY-2607-0029", date(2026, 7, 24), Decimal("250000"), Decimal("775.00")),
    ),
    "magnolia": (("MG-2607-0017", date(2026, 7, 15), Decimal("400000"), Decimal("1240.00")),),
    "sabine": (
        ("SB-2607-0021", date(2026, 7, 12), Decimal("150000"), Decimal("465.00")),
        # ⚠ NO VOLUME, ON PURPOSE. BR-LED-031's all-or-nothing rule suppresses
        # Sabine's percentage and names the count; the −58.33% it protects
        # against is worked in the module docstring.
        ("SB-2607-0038", date(2026, 7, 29), None, Decimal("310.00")),
    ),
}

#: How many member accounts sit inside each building. Small on purpose: the
#: fixture proves a per-building denominator, and forty members would make the
#: arithmetic unreadable without proving anything the third member does not.
MEMBERS_PER_BUILDING = 2

#: The blended figure this fixture exists to argue AGAINST — CR-060 C9's
#: *"an average that describes neither and points at nothing anyone can go and
#: fix"*. `(1,250,000 − 1,127,500) / 1,250,000 = 0.098 → 9.80%`. Asserted by the
#: tests as the number the per-building read must NOT produce.
BLENDED_PCT_THAT_HIDES_THE_LEAK = Decimal("9.80")

TOTAL_BOUGHT_COST = Decimal("3875.00")
CYPRESS_PCT = Decimal("5.00")
MAGNOLIA_PCT = Decimal("20.00")
#: What Sabine would read from its partial denominator, and never does.
SABINE_SUPPRESSED_PCT = Decimal("-58.33")


def submetering_payload(subdomain: str = "bayoubend") -> dict[str, object]:
    """The signup payload — water only, which is what a sub-metering company
    resells. Shaped like `tests/test_us_ten_helpers.brazosbend_payload()`."""
    return {
        "name": "Bayou Bend Submetering LLC",
        "subdomain": subdomain,
        "state": "Texas",
        "services": ["water"],
        "currency": "USD",
        "owner": {
            "full_name": "Renata Alcorn",
            "email": f"renata@{subdomain}.test",
            "password": "S3cure!passw0rd",
            "phone": "+1 (713) 555-0142",
        },
    }


def mark_as_sub_metering(actor) -> str:
    """CR-060 C7 / task T2 — the one field C8 and C9 read, set the way a human
    sets it: through Settings → Company → Profile, not by an ORM update.

    This is the whole dependency T3 has on T2, and it is one line — which is
    why T2's row says T3 and T4 cannot start without it.
    """
    tenancy_services.save_company_profile(
        actor,
        {
            "legal_name": "Bayou Bend Submetering LLC",
            "organisation_type": tenancy_models.ORGANISATION_TYPE_SUB_METERING,
        },
    )
    return tenancy_models.ORGANISATION_TYPE_SUB_METERING


def make_buildings(actor) -> dict[str, dict[str, object]]:
    """Three premises, created through metering's own service (no ORM shortcut).

    A sub-metering company's "building" IS a premises: the master meter is on
    the building and the members are units inside it, which is why C3 puts a
    `premises_id` on the purchase rather than inventing a building table.
    """
    from tests.test_us_met_helpers import make_premises

    made: dict[str, dict[str, object]] = {}
    for key, address, *_rest in BUILDINGS:
        made[key] = make_premises(
            actor,
            address_line=address,
            premises_type="apartment_complex",
            services_available=["water"],
            owner_manager="Bayou Bend Submetering LLC",
        )
    return made


def make_members(actor, tenant, buildings) -> dict[str, list]:
    """`MEMBERS_PER_BUILDING` member accounts inside each building.

    ⚠ **THE ACCOUNT ROWS ARE WRITTEN THROUGH THE ORM AND THAT IS THIS
    DIRECTORY'S EXISTING POSTURE**, not a new shortcut: `ledger_le_fixtures.
    make_accounts` does the same, for the same reason — these tests are about
    the LEDGER's per-building denominator, and `create_account` carries
    BR-CUS-1024's identity gate plus the whole onboarding wizard's rules, so a
    failure there would surface here as a reconciliation failure. The UNITS and
    the PREMISES above ARE created through metering's real services, because
    the account → unit → premises chain is what the reconciliation resolves and
    a faked chain would prove nothing.
    """
    from tests.test_us_met_helpers import make_unit

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    account_type = customer_models.AccountType.objects.first()
    made: dict[str, list] = {}
    for key, address, *_rest in BUILDINGS:
        made[key] = []
        for index in range(MEMBERS_PER_BUILDING):
            unit = make_unit(
                actor,
                buildings[key]["id"],
                label=f"{index + 1}0{index + 1}",
                services=["water"],
            )
            made[key].append(
                customer_models.Account.objects.create(
                    tenant=tenant,
                    unit_id=unit["id"],
                    account_no=f"{key[:3].upper()}-{index + 1:03d}",
                    status=status,
                    account_type=account_type,
                )
            )
    return made


def make_master_account(actor, tenant, buildings, *, building: str = "cypress"):
    """The master account CR-060 §11 asks for — the owner/manager's own account.

    A master is not a parent: BR-CUS-068 makes it an ORDINARY `accounts` row
    with `kind='master'`, billed directly, which is why its statement is just an
    account statement and why nothing here rolls members up into it. It exists
    in this fixture so C8's tiles and C16's customer statement have the shape
    they describe, and it deliberately carries NO usage: the members are billed
    for the water, and a master that also carried volume would double-count the
    building's billed side.
    """
    from tests.test_us_met_helpers import make_unit

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    account_type = customer_models.AccountType.objects.first()
    unit = make_unit(actor, buildings[building]["id"], label="COMMON", services=["water"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no="BB-MASTER-001",
        status=status,
        account_type=account_type,
        kind="master",
    )


def bill_member_usage(tenant, account, *, quantity, unit="gal", period=(JULY_START, JULY_END)):
    """One ISSUED bill carrying one water usage line — the billed half.

    The same helper shape `tests/test_us_led_020_reconciliation.py` already
    uses, and the same reason: this is the ledger's reconciliation under test,
    not billing's run.
    """
    from tests.ledger_le_fixtures import service_id

    invoice = billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        service_date=period[1],
        period_start=period[0],
        period_end=period[1],
        status=billing_models.INVOICE_ISSUED,
        issued_at=ISSUED_AT,
        subtotal=Decimal("0"),
        tax_total=Decimal("0"),
        total=Decimal("0"),
        currency="USD",
    )
    billing_models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=account,
        service_id=service_id("water"),
        kind="usage",
        description="water usage",
        quantity=quantity,
        unit=unit,
        amount=Decimal("0"),
        period_start=period[0],
        period_end=period[1],
    )
    return invoice


def capture_building_purchases(actor, buildings) -> dict[str, list]:
    """The bought half — one or two supplier invoices per building, through the
    REAL capture service, each carrying its building (CR-060 C3)."""
    captured: dict[str, list] = {}
    for key, rows in PURCHASES.items():
        captured[key] = []
        for reference, invoice_date, volume, amount in rows:
            captured[key].append(
                cost_capture.capture_supplier_invoice(
                    actor,
                    invoice_date=invoice_date,
                    service="water",
                    supplier_name="City of Bayou Bend — Bulk Water",
                    amount=amount,
                    currency="USD",
                    volume=volume,
                    # CLAUDE.md rule 3 — a quantity always carries its unit, and
                    # a volume-less purchase carries neither (the DB refuses one
                    # without the other: ck_supplier_invoices_volume_unit).
                    volume_unit="gal" if volume is not None else None,
                    premises_id=buildings[key]["id"],
                    reference=reference,
                )
            )
    return captured


def bayou_bend_july(tenant, clerk, admin) -> dict[str, object]:
    """The whole fixture in one call: the type, the buildings, the members,
    the master, the billed water and the captured purchases.

    Returns everything a test needs to assert against, so no test has to
    re-derive a figure the module docstring already worked by hand.
    """
    from tests.cost_of_service_fixtures import with_monthly_fiscal_year

    with_monthly_fiscal_year(admin)
    mark_as_sub_metering(admin)
    buildings = make_buildings(admin)
    members = make_members(admin, tenant, buildings)
    master = make_master_account(admin, tenant, buildings)

    # The billed side, split evenly between each building's members. Even
    # splits keep the arithmetic in the docstring checkable by hand; the
    # reconciliation sums them per building either way.
    for key, _address, _bought, billed, _pct in BUILDINGS:
        share = billed / MEMBERS_PER_BUILDING
        for account in members[key]:
            bill_member_usage(tenant, account, quantity=share)

    captured = capture_building_purchases(clerk, buildings)
    return {
        "buildings": buildings,
        "members": members,
        "master": master,
        "captured": captured,
    }
