#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  DEF-REP-7010 — the two kinds of zero in the Billing Register's
#          USAGE cell, and the chips-per-row half of the services rule.
# Rules:   `BR-RAT-090` (a CAPACITY service is billed by a COUNT of the unit's
#          assets) · `BR-TEN-1180` (`capacity` is the basis that means that) ·
#          CLAUDE.md hard rule 1 (tenant scoping — `app.tenant_id` is SET
#          before a single row is touched) · hard rule 4 (financial
#          immutability — this CREATES rows and updates none).
# ───────────────────────────────────────────────────────
"""Seed a demo book that can PROVE both halves of two rules, in a browser.

⚠ **WITHOUT THIS, HALF OF EACH RULE IS UNPROVABLE AND THE WALKTHROUGH SAYS SO
RATHER THAN PASSING QUIETLY.** Every seeded tenant in this repo bills the same
services on every account, so:

  · the services column COLLAPSES on all of them and *"otherwise chips per
    row"* — the other half of the Product Owner's own sentence — has nowhere
    to be photographed;
  · every usage line carries a real figure, so *"a zero that MEANS something
    (a meter read of zero)"* has nowhere to be photographed either, and a fix
    that dropped EVERY zero would look perfect.

It writes two ISSUED bills into `brazosbend`:

  · **`BL-2608-900001`** — WATER only, and its meter read **0 kgal**. A
    reading. It must survive on screen.
  · **`BL-2608-900002`** — ELECTRIC + WATER + TRASH, and the unit has **0
    carts**. A count of nothing. It must not.

Both rows then sit on one screen under `q=BL-2608-900`, which is what makes
the screenshot an argument rather than an assertion.

⚠ **IT IS IDEMPOTENT AND IT REFUSES TO EDIT.** A second run finds the bills by
number and leaves them alone — hard rule 4 is not relaxed for a fixture.

USAGE
    DATABASE_URL=... DJANGO_SETTINGS_MODULE=config.settings.local \
    python3 10-scripts/def_rep_7010_seed_two_kinds_of_zero.py
(run from `06-backend`, or with it on `PYTHONPATH`)
"""
import django; django.setup()
from datetime import date, datetime, timezone
from decimal import Decimal
from django.db import connection
from apps.billing import models as bm
from apps.tenancy import models as tm
from apps.customers import models as cm

TENANT_SUB = "brazosbend"
tenant = tm.Tenant.objects.get(subdomain=TENANT_SUB)
with connection.cursor() as c:
    c.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant.id)])

# trash must be ENABLED and declared CAPACITY, or its cart count is not a count.
trash = tm.Service.objects.get(code="trash")
row, _ = tm.TenantService.objects.get_or_create(tenant=tenant, service=trash, defaults={"enabled": True})
row.enabled = True
row.billing_basis = "capacity"
row.save(update_fields=["enabled", "billing_basis"])
print("trash basis:", row.billing_basis)

water = tm.Service.objects.get(code="water")
electric = tm.Service.objects.get(code="electric")

account = cm.Account.objects.filter(tenant=tenant).order_by("account_no").first()
print("account:", account.account_no)

UTC = timezone.utc
ISSUED = datetime(2026, 8, 20, 9, 0, tzinfo=UTC)

def bill(no, lines, total):
    inv = bm.Invoice.objects.filter(tenant=tenant, invoice_no=no).first()
    if inv is not None:
        print("exists:", no); return inv
    inv = bm.Invoice.objects.create(
        tenant=tenant, account=account, invoice_no=no, bill_type="cycle",
        status=bm.INVOICE_ISSUED, service_date=date(2026, 8, 31),
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
        due_date=date(2026, 9, 25), issued_at=ISSUED,
        subtotal=total, tax_total=Decimal("0.00"), total=total, currency="USD",
        template_version=3, payload_version=1, bill_payload={},
    )
    for svc, desc, qty, unit, amount, kind in lines:
        bm.InvoiceLine.objects.create(
            tenant=tenant, invoice=inv, account=account, service=svc,
            kind=kind, description=desc, quantity=qty, unit=unit,
            unit_price=None, amount=amount, taxable=False,
            period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
        )
    print("made:", no)
    return inv

# ── A · WATER ONLY, AND ITS METER READ ZERO ─────────────────────────────
# `0 kgal` is a READING. It must survive.
bill("BL-2608-900001", [
    (water, "Water usage", Decimal("0"), "kgal", Decimal("0.00"), "usage"),
    (water, "Water base", None, None, Decimal("18.00"), "base"),
], Decimal("18.00"))

# ── B · ELECTRIC + WATER + TRASH, AND NOBODY HAS A CART ─────────────────
# `0 cart` is a COUNT. It must go.
bill("BL-2608-900002", [
    (electric, "Electric usage", Decimal("420"), "kWh", Decimal("50.40"), "usage"),
    (water, "Water usage", Decimal("7.5"), "kgal", Decimal("22.50"), "usage"),
    (trash, "Trash carts", Decimal("0"), "cart", Decimal("0.00"), "usage"),
], Decimal("72.90"))
