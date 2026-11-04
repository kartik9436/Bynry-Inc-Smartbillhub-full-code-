# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W0 — every customer gets a number (B18 §2.5, §11 W0 task 0.3)
# Rules:    BR-TEN-035 (numbers come from the tenant series) · BR-CUS-054 (the
#           customer entity this numbers) · CLAUDE.md rule 1 (tenant scoping)
# Impacts:  apps/customers/models.py (the column) · core/numbering.py (the
#           twenty-fourth series) · apps/tenancy (number_series rows)
# ───────────────────────────────────────────────────────
"""Backfill `customers.customer_no`, and seed the series it comes from.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — CLAUDE.md files *migration ordering* as a
🔒 sensitive path. AI-authored under the PO ruling of 2026-08-09 (*"AI will do
it; we will review it later as human"*); row in
`12-governance/09-human-review-ledger.md`.

════════════════════════════════════════════════════════════════════════════
WHY THIS IS TWO STEPS AND NOT ONE
════════════════════════════════════════════════════════════════════════════
`seed_number_series` runs at PROVISIONING. Every tenant provisioned before
today therefore has twenty-three `number_series` rows and no `customer` row —
so a backfill that went straight to allocating would raise `NumberingError` on
the first existing tenant it touched, and a migration that fails halfway
through a live database is the thing migration ordering exists to prevent.

So: seed first, per tenant, then allocate. Both inside one atomic migration.

════════════════════════════════════════════════════════════════════════════
WHY IT ALLOCATES ROW BY ROW RATHER THAN NUMBERING IN SQL
════════════════════════════════════════════════════════════════════════════
A `row_number() OVER ()` would be faster and would produce numbers that do not
come from the tenant's series. The series holds `next_number`, and a bulk
update that did not advance it would hand the SAME numbers out again to the
next customer created through `link_customer` — a duplicate-key error on
`uq_customers_tenant_customer_no_ci` at some unrelated later moment, which is
the worst kind of bug to inherit.

Numbers are GAPLESS WITHIN A TENANT and allocated in `created_at` order, so the
oldest customer holds the lowest number, which is what a human expects of a
customer number and what makes the backfill reproducible.

════════════════════════════════════════════════════════════════════════════
REVERSIBILITY
════════════════════════════════════════════════════════════════════════════
Reverse NULLs the column and rewinds each tenant's counter to where it started.
It deliberately does NOT delete the `number_series` row: a tenant that has since
edited its own customer format (BR-TEN-035 makes every series tenant-editable)
would lose that edit, and a seeded row costs nothing.
"""

from django.db import migrations


def _series_defaults():
    """Imported lazily — a migration that imports app services at module scope
    runs that import during `makemigrations` on every unrelated app."""
    from core import numbering as core_numbering

    key = core_numbering.CUSTOMER
    group, options = core_numbering.SERIES_CATALOG[key]
    return key, options[0], core_numbering.RESTART_NEVER


def forwards(apps, schema_editor):
    from core import numbering as core_numbering

    Customer = apps.get_model("customers", "Customer")
    NumberSeries = apps.get_model("tenancy", "NumberSeries")
    key, default_format, restart = _series_defaults()

    tenant_ids = list(
        Customer.objects.order_by("tenant_id").values_list("tenant_id", flat=True).distinct()
    )
    for tenant_id in tenant_ids:
        row, _created = NumberSeries.objects.get_or_create(
            tenant_id=tenant_id,
            series=key,
            defaults={
                "format": default_format,
                "next_number": 1,
                "restart_period": restart,
                "period_counted": "",
            },
        )
        rows = list(
            Customer.objects.filter(tenant_id=tenant_id, customer_no__isnull=True)
            .order_by("created_at", "id")
            .values_list("id", "created_at")
        )
        if not rows:
            continue
        counter = row.next_number
        for customer_id, created_at in rows:
            # BR-TEN-043 — the ISSUE DATE is the business event's own date, never
            # a clock read in here. For a backfill that date is when the customer
            # was created, which also keeps the result reproducible: re-running
            # this migration on a restored dump produces the same numbers.
            #
            # ⚠ AND IT MATTERS EVEN THOUGH THE DEFAULT FORMAT HAS NO DATE TOKEN.
            # `C-{00000}` never reads the date — but BR-TEN-035 makes every
            # series tenant-editable, so a tenant that has already switched to
            # `C-{YYYY}-{0000}` WOULD, and passing None there raises inside
            # `render`. Handing it the real date costs nothing and cannot rot.
            Customer.objects.filter(pk=customer_id).update(
                customer_no=core_numbering.render(row.format, counter, created_at.date())
            )
            counter += 1
        row.next_number = counter
        row.save(update_fields=["next_number"])


def backwards(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    NumberSeries = apps.get_model("tenancy", "NumberSeries")
    from core import numbering as core_numbering

    for tenant_id in list(
        Customer.objects.order_by("tenant_id").values_list("tenant_id", flat=True).distinct()
    ):
        filled = Customer.objects.filter(tenant_id=tenant_id, customer_no__isnull=False).count()
        if not filled:
            continue
        Customer.objects.filter(tenant_id=tenant_id).update(customer_no=None)
        row = NumberSeries.objects.filter(
            tenant_id=tenant_id, series=core_numbering.CUSTOMER
        ).first()
        if row is not None:
            row.next_number = max(1, row.next_number - filled)
            row.save(update_fields=["next_number"])


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("customers", "0013_cr030_w0_customer_no"),
        # The series rows this seeds into live in tenancy. Naming the dependency
        # rather than assuming ordering is the point of the 🔒 flag on this file.
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
