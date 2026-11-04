# ── Trace ──────────────────────────────────────────────
# Story:   US-CWP-035 (EP-CWP-07) — why this bill is different. Screen CWP-030
#          (blueprint `P16`). `US-CWP-044` (`CWP-036`, the high-usage alert) is
#          the wave's OTHER story and is a deliberate absence — nothing fires
#          it, no address serves it, and this fixture plants nothing for it.
# Rules:   BR-CWP-046 (the component lines sum EXACTLY to the difference — no
#          tolerance) · BR-CWP-093 (a first bill offers no comparison at all,
#          and NOT a comparison against zero) · CLAUDE.md hard rule 2 (money
#          stored to 4 decimals, DISPLAYED to 2) · hard rule 1 (every read and
#          write names its tenant EXPLICITLY — this runs as a superuser with
#          RLS skipped) · hard rule 4 (nothing here UPDATEs an issued invoice;
#          every bill is written once, as a new row)
# Decision: OQ-CWP-1563 / OQ-CWP-1569 CLOSED 2026-09-05 — PO verbatim,
#          *"(a) list every reason with its share"*. `COMPONENTS_SIGNED` is
#          True and the breakdown is live, so this fixture must produce bills
#          whose shares actually tie out.
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-o-why-different.mjs
# ───────────────────────────────────────────────────────
"""THE STATE `CWP-030` IS NORMALLY IN — WHICH IS NOT THE STATE
`seed_portal_demo` LEAVES IT IN.

WHY THIS FILE EXISTS, AND THE MEASUREMENT THAT MADE IT NECESSARY
----------------------------------------------------------------
`CWP-030` is built and served. Run the walkthrough against a plain
`seed_portal_demo` database and it cannot be driven at all, for two separate
reasons measured on 2026-09-06:

  * **`1408 Elm St · A` carries ZERO invoices.** It is the account wave H
    plants a meter history on — 24 monthly reads, the June correction, three
    assets — and it is the only account on the tenant that can populate the
    **AGAINST LAST AUGUST** panel. It has never been billed, so the screen
    404s on every address you could type.
  * **Every other account's bills all moved the SAME WAY.** Counted over the
    whole tenant: `seed_portal_demo` bills **50 accounts**, 49 of them twice
    and one of them once, which is **49 comparisons — and all 49 went UP**,
    June to July, between `+$3.38` and `+$56.65`. There is not one bill on the
    tenant that went DOWN and not one that stayed LEVEL.

⚠ **AND THE SECOND ONE IS THE REASON THIS FIXTURE IS THE WORK, NOT THE FIRST.**
A walkthrough driven against the seed as it stands would assert *cost more*,
find it, and pass — over a screen that could be hard-coded to say *cost more*
and would never be caught. That is CLAUDE.md hard-won law 7's *"a check that
cannot fail"*, and it is exactly what wave I's briefing warns about: its own
cheaper-to-stop-or-close screen had to be driven THREE times with different
inputs before anyone could say the screen computes anything at all.

**So this plants a chain of five bills on ONE account** and the walkthrough
drives the same screen four times, at four addresses, and asserts that the
answer CHANGES:

    BL-O-2606-0100   Jun 2026   $100.00   FIRST BILL — no comparison at all
    BL-O-2607-0139   Jul 2026   $138.44   (the prior for the case below)
    BL-O-2608-0141   Aug 2026   $142.18   ↑  +$3.74   "cost more"
    BL-O-2609-0143   Sep 2026   $138.44   ↓  −$3.74   "cost less"
    BL-O-2610-0145   Oct 2026   $138.44   →   $0.00   "cost the same"

THE THREE CASES, AND WHY EACH IS THE ONE IT IS
-----------------------------------------------
**THE RISE IS THE EXECUTION PLAN'S OWN FIGURE.** `10-execution-plan.md` wave O
step 1 names `BL-2607-0139 $138.44 → BL-2608-0141 $142.18`, a difference of
`+$3.74`, and the four component lines `+$8.83`, `$0.00`, `+$4.29`, `−$9.38`.
Those four are what `OQ-CWP-1569` was put to the PO on and what they ruled on,
so the walkthrough asserts the specification rather than arithmetic this file
invented. The lines are composed to produce exactly those four shares:

    bucket                    Jul        Aug      share
    (water, usage)         120.0000   128.8300   +8.83
    (trash, base)           12.0000    12.0000    0.00   ← listed, not omitted
    (water, discount)       -4.2900     —        +4.29   ← ended: prior only
    (bill,  tax)            10.7300     1.3500   -9.38
    ─────────────────────────────────────────────────────
    total                  138.4400   142.1800   +3.74

**THE FALL IS THE RISE'S EXACT MIRROR, AND THAT IS DELIBERATE.** September
repeats July's four lines against August, so the difference is `−$3.74` — the
same magnitude, the opposite sign. A screen that takes an absolute value
anywhere reads `$3.74` on both and can only be caught by the WORD; a screen
that reverses the word but not the figure is caught by the figure. Same
number, different answer, is the strongest single pair available here.

⚠ **THE LEVEL BILL IS THE ONE THAT PROVES THE BREAKDOWN IS COMPUTED, AND IT IS
THE CASE NO SINGLE-BILL TEST CAN REACH.** October totals `$138.44` against
September's `$138.44`, so the difference is exactly `$0.00` and the headline
is *cost the same*. **But two of its components are NOT zero:** water usage
rises `+$5.00` and the tax falls `−$5.00`, and they cancel.

    bucket                    Sep        Oct      share
    (water, usage)         120.0000   125.0000   +5.00   ← moved
    (trash, base)           12.0000    12.0000    0.00
    (water, discount)       -4.2900    -4.2900    0.00
    (bill,  tax)            10.7300     5.7300   -5.00   ← moved
    ─────────────────────────────────────────────────────
    total                  138.4400   138.4400    0.00

A screen that derived its component lines FROM the headline difference — the
obvious wrong implementation, and one that would pass every up-and-down test
written above — draws nothing at all here, or draws four zeros. The product
must name two real movements over a total that did not move. That assertion
is the single most load-bearing one in the walkthrough.

**AND THE FIRST BILL IS THE FOURTH ANSWER.** June is the oldest invoice on the
account, so `BR-CWP-093` applies: `compared: false`, no difference figure
anywhere on the page, and NOT a comparison against zero. *"$100.00 more than
last month"* is arithmetically true and, to somebody who has just moved in, a
lie.

WHY AUGUST, AND NOT ANY OTHER MONTH
------------------------------------
The rise is dated `period_end = 2026-08-31` on purpose. `metering_seam.
usage_same_month_last_year` reads the account's stored monthly usage over a
**24-month** window and pairs `2026-08` with `2025-08`; wave H's seed plants 24
reads on this account reaching back to October 2024, so August is one of the
few months where BOTH points exist and the **AGAINST LAST AUGUST** panel is
populated rather than absent. On the September and October bills that panel is
correctly ABSENT (`BR-CWP-093` — nothing empty ever appears), and the
walkthrough asserts the absence rather than ignoring it.

WHAT THIS FIXTURE DELIBERATELY DOES NOT DO
-------------------------------------------
* **It does not repair `seed_portal_demo`.** That every seeded bill moves the
  same way is a property of the seed, and a walkthrough fixture is not the
  place to change what every other wave's screens are driven against.
* **It plants nothing for `CWP-036`.** The high-usage alert has no trigger, no
  endpoint and no address; the drawing itself is stamped BLOCKED and carries
  its own *"this alert has no trigger in the product today"* panel. Seeding a
  row to make a screen appear would manufacture the very thing the wave
  records as absent.
* **It never UPDATEs an issued invoice** (hard rule 4). Bills it has already
  written are left exactly alone and re-running is a no-op.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, date, datetime
from decimal import Decimal

BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "06-backend",
)
sys.path.insert(0, BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from core.tenancy import tenant_context  # noqa: E402

# ── the login ───────────────────────────────────────────────────────────────
EMAIL = "o-why-different@example.test"
PASSWORD = "Elm-Street-1408"
ELM_ST = "1408 Elm St"
UNIT_LABEL = "A"

# ── the bills, and every line of each ───────────────────────────────────────
#: `BL-O-` and not the plan's bare `BL-2608-0141`: `seed_portal_demo` mints
#: `BL-2608-0000NN` off a counter for all 51 accounts, and a fixture that took
#: a bare number would collide the day the estate ahead of it changed size.
#: Wave I's fixture set the precedent with `BL-I-`. The FIGURES are the plan's;
#: the number is a label.
FIRST_BILL = "BL-O-2606-0100"
PRIOR_BILL = "BL-O-2607-0139"
ROSE_BILL = "BL-O-2608-0141"
FELL_BILL = "BL-O-2609-0143"
LEVEL_BILL = "BL-O-2610-0145"

#: The rise the execution plan names, and the fall that mirrors it exactly.
ROSE_BY = Decimal("3.74")
BASELINE = Decimal("138.44")
PEAK = Decimal("142.18")

#: One line: (service code or None for a bill-level charge, kind, description,
#: amount, quantity, unit). A `None` service is what `_bucket_totals` files
#: under `(None, kind)` and the screen words as a bill-level reason.
BILLS: tuple[tuple[str, date, date, Decimal, tuple], ...] = (
    (
        FIRST_BILL,
        date(2026, 6, 1),
        date(2026, 6, 30),
        Decimal("100.00"),
        (
            ("water", "usage", "Water used", Decimal("80.00"), Decimal("3050"), "gal"),
            ("trash", "base", "Trash cart charge", Decimal("12.00"), None, None),
            (None, "tax", "Tax", Decimal("8.00"), None, None),
        ),
    ),
    (
        PRIOR_BILL,
        date(2026, 7, 1),
        date(2026, 7, 31),
        BASELINE,
        (
            ("water", "usage", "Water used", Decimal("120.00"), Decimal("4090"), "gal"),
            ("trash", "base", "Trash cart charge", Decimal("12.00"), None, None),
            ("water", "discount", "Summer discount", Decimal("-4.29"), None, None),
            (None, "tax", "Tax", Decimal("10.73"), None, None),
        ),
    ),
    (
        # ↑ +$3.74 — the execution plan's own worked case.
        ROSE_BILL,
        date(2026, 8, 1),
        date(2026, 8, 31),
        PEAK,
        (
            ("water", "usage", "Water used", Decimal("128.83"), Decimal("4820"), "gal"),
            ("trash", "base", "Trash cart charge", Decimal("12.00"), None, None),
            # no discount line at all — it ENDED, and its whole value is a share
            (None, "tax", "Tax", Decimal("1.35"), None, None),
        ),
    ),
    (
        # ↓ −$3.74 — July's four lines again, so the fall mirrors the rise.
        FELL_BILL,
        date(2026, 9, 1),
        date(2026, 9, 30),
        BASELINE,
        (
            ("water", "usage", "Water used", Decimal("120.00"), Decimal("4090"), "gal"),
            ("trash", "base", "Trash cart charge", Decimal("12.00"), None, None),
            ("water", "discount", "Summer discount", Decimal("-4.29"), None, None),
            (None, "tax", "Tax", Decimal("10.73"), None, None),
        ),
    ),
    (
        # → $0.00 on the total, and TWO components that moved and cancelled.
        LEVEL_BILL,
        date(2026, 10, 1),
        date(2026, 10, 31),
        BASELINE,
        (
            ("water", "usage", "Water used", Decimal("125.00"), Decimal("4260"), "gal"),
            ("trash", "base", "Trash cart charge", Decimal("12.00"), None, None),
            ("water", "discount", "Summer discount", Decimal("-4.29"), None, None),
            (None, "tax", "Tax", Decimal("5.73"), None, None),
        ),
    ),
)


def _tenant():
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Tenant.objects.get(subdomain="pine-hill")


def _account(tenant):
    """The account at `1408 Elm St · A`, found through the PREMISES.

    ⚠ **NEVER BY ACCOUNT NUMBER** (`DEF-CWP-4174`): `AC-2026-00052` comes off a
    counter and moves whenever the estate ahead of it changes size, so a
    document that hard-codes one cannot enrol anybody on a fresh database.
    """
    from apps.customers import models as customers_models
    from apps.metering import models as metering_models

    unit = (
        metering_models.Unit.objects.filter(
            tenant_id=tenant.id, premises__address_line=ELM_ST, label=UNIT_LABEL
        )
        .select_related("premises")
        .first()
    )
    if unit is None:
        raise SystemExit(
            f"no {ELM_ST} · {UNIT_LABEL} on pine-hill — `manage.py seed_portal_demo` did not run"
        )
    account = customers_models.Account.objects.filter(
        tenant_id=tenant.id, unit_id=unit.id
    ).first()
    if account is None:
        raise SystemExit(f"nobody holds an account at {ELM_ST} · {UNIT_LABEL}")
    return account


def _services():
    """`{code: Service}` — the PLATFORM catalogue, which carries no tenant.

    `tenancy.Service` is a platform table (all eleven services, seeded once),
    so it is filtered by CODE and not by tenant. Every row this file writes
    against it still names `tenant_id` on the INVOICE LINE itself.
    """
    from apps.tenancy import models as tenancy_models

    return {row.code: row for row in tenancy_models.Service.objects.all()}


def plant_the_bills(tenant, account) -> list[str]:
    """Five ISSUED bills and their lines — written once, never updated.

    ⚠ **THE TOTAL IS THE SUM OF THE LINES AND THAT IS WHAT MAKES THE SCREEN
    WORK.** `billing_seam._components_view` gates the whole breakdown on
    `components_tie_out`, which compares the sum of the DISPLAYED component
    figures with the DISPLAYED difference and allows no tolerance
    (`BR-CWP-046`). A bill whose stored total does not equal its own lines
    serves the stated-absence branch instead — a correct answer to a broken
    bill, and a useless one to a walkthrough trying to read four shares. So
    each total below is asserted against its own lines before anything is
    written, and this file refuses rather than planting a bill that would make
    the screen state an absence for a reason that is this fixture's fault.
    """
    from apps.billing import models as billing_models

    services = _services()
    made: list[str] = []
    for number, start, end, total, lines in BILLS:
        # The arithmetic this fixture depends on, checked BEFORE the write.
        summed = sum((row[3] for row in lines), Decimal("0"))
        if summed != total:
            raise SystemExit(
                f"{number}: lines sum to {summed} and the total says {total}. "
                "The breakdown would not tie out and CWP-030 would state an "
                "absence — fix the figures in BILLS, do not plant this."
            )
        existing = billing_models.Invoice.objects.filter(
            tenant_id=tenant.id, invoice_no=number
        ).first()
        if existing is not None:
            made.append(f"{number} (already)")
            continue
        invoice = billing_models.Invoice.objects.create(
            tenant=tenant,
            account=account,
            invoice_no=number,
            status=billing_models.INVOICE_ISSUED,
            service_date=end,
            period_start=start,
            period_end=end,
            due_date=date(end.year + (end.month // 12), (end.month % 12) + 1, 18),
            subtotal=total,
            tax_total=sum(
                (row[3] for row in lines if row[1] == "tax"), Decimal("0")
            ),
            total=total,
            issued_at=datetime(end.year, end.month, end.day, 9, 0, tzinfo=UTC),
        )
        for code, kind, description, amount, quantity, unit in lines:
            billing_models.InvoiceLine.objects.create(
                tenant=tenant,
                invoice=invoice,
                account=account,
                service=services.get(code) if code else None,
                kind=kind,
                description=description,
                amount=amount,
                quantity=quantity,
                unit=unit,
                taxable=kind in ("usage", "base"),
                period_start=start,
                period_end=end,
            )
        made.append(f"{number} ${total}")
    print("  bills on the account      :")
    for row in made:
        print(f"      {row}")
    return made


def enrol(tenant, account) -> None:
    from apps.portal import credentials, models as portal_models

    existing = credentials.credential_by_email(tenant.id, EMAIL)
    if existing is not None:
        print(f"  {EMAIL} already enrolled — left alone")
        return
    credentials.create_credential(
        tenant.id,
        account=account,
        email=EMAIL,
        password=PASSWORD,
        otp_channel=portal_models.CHANNEL_SMS,
    )
    print(f"  {EMAIL} enrolled on {account.account_no}")


def main() -> None:
    tenant = _tenant()
    # ⚠ **EVERY FILTER NAMES `tenant_id` AND HAS TO** (hard rule 1). This runs
    # as `smartbillhub`, which is `rolsuper=t`, so `FORCE RLS` is skipped for
    # every query in this process and an unscoped queryset would silently reach
    # another of the seeded tenants.
    with tenant_context(tenant.id):
        account = _account(tenant)
        print(f"cr068-o fixture · pine-hill · {account.account_no} ({ELM_ST} · {UNIT_LABEL})")
        plant_the_bills(tenant, account)
        enrol(tenant, account)

    print()
    print(f"  sign in as {EMAIL}, password {PASSWORD}")
    print(f"  the first bill (no comparison) is {FIRST_BILL}")
    print(f"  the bill that ROSE  is {ROSE_BILL}   +${ROSE_BY}")
    print(f"  the bill that FELL  is {FELL_BILL}   -${ROSE_BY}")
    print(f"  the bill that is LEVEL is {LEVEL_BILL}   $0.00, two components moved")


main()
