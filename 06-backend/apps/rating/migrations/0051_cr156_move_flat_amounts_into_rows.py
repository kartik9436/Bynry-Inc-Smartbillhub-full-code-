# ── Trace ──────────────────────────────────────────────
# Change:  CR-156-BRC10 — PO 2026-10-01, option A, verbatim: *"The old field on
#          the charge code is no longer written; today's values move into rows
#          once."*
# Rules:   BR-RAT-1048 · BR-RAT-1049 · BR-RAT-1051 · CLAUDE.md hard rule 1
#          (`app.tenant_id` set per tenant — RLS FORCE) · hard rule 2
# Tests:   06-backend/tests/test_cr156_charge_prices_pg.py (the move, measured)
# ───────────────────────────────────────────────────────
"""rating 0051 — **the one-time move**, per tenant, under RLS.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering; money already
stored moves tables). Row in `12-governance/09-human-review-ledger.md`.

THREE THINGS, EACH IDEMPOTENT:

1. **Every existing price row is dated from `2000-01-01`.** These rows existed
   before dates did and have priced every bill since; dating them from the day
   a code was created would refuse every catch-up bill for the months before
   it. The brief offered *"the charge's created date (or a safe epoch)"* — the
   epoch is taken because a sample utility's codes are created the day it is
   seeded and its catch-up bills are for the months before (decision log
   2026-10-01, this lane's judgment (1)).
2. **Every `charges.amount` that is set becomes ONE *All sizes* row** — every
   class, from the same epoch — and the column is cleared. A code that already
   holds a live *All sizes* every-class row is left alone (a re-run writes
   nothing). A code holding BOTH a flat amount and sized rows — refused by the
   save since `CR-013` part 2, and refused by billing on billing day — moves
   too: no figure is destroyed, and the lookup goes on refusing that code by
   the same name (`amount_and_size_table`), so no bill changes.
3. **Every code gets its kind** where it has none: `is_base` → base; the PO's
   plan list, penalties and deposits → plan; everything else → other.

⚠ **THE CONSTANTS ARE COPIED HERE, NOT IMPORTED.** A migration runs against the
schema of its own moment for ever; importing `apps.rating.constants` would let
a later edit to the plan list silently re-classify history on the next fresh
database. The copy is the value ruled on 2026-10-01.

⚠ **HARD RULE 1: `app.tenant_id` IS SET FOR EACH TENANT** (`rating/0039`'s
lesson — RLS FORCE silently emptied `rating/0038`'s backfill because no tenant
was set, and the migration reported success over zero rows). The count of rows
moved is logged per tenant so an empty run is visible.
"""

import logging
from datetime import date
from decimal import Decimal

from django.db import migrations

logger = logging.getLogger(__name__)

NO_TENANT = "00000000-0000-0000-0000-000000000000"
ALL_SIZES = "All sizes"
EPOCH = date(2000, 1, 1)
PLAN_CODES = {
    "CONN",
    "DISC",
    "RECON",
    "TRANSFER",
    "MOVE-OUT",
    "CC-CONV",
    "PAPER",
    "HYDRANT",
    "LATE",
    "NSF",
    "TAMPER",
    "DEPOSIT",
}
PLAN_CHARGE_TYPES = {"penalty", "refundable"}


def _kind(code, charge_type, is_base):
    if is_base:
        return "base"
    if (code or "").strip().upper() in PLAN_CODES:
        return "plan"
    if (charge_type or "").strip().lower() in PLAN_CHARGE_TYPES:
        return "plan"
    return "other"


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _forwards(apps, schema_editor):
    Charge = apps.get_model("rating", "Charge")
    Amount = apps.get_model("rating", "ChargeCodeAmount")
    connection = schema_editor.connection
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        dated = Amount.objects.filter(tenant_id=tenant_id, effective_from__isnull=True).update(
            effective_from=EPOCH
        )
        moved = 0
        kinds = 0
        for charge in Charge.objects.filter(tenant_id=tenant_id).order_by("id"):
            fields = []
            if charge.legacy_amount is not None:
                has_flat = Amount.objects.filter(
                    tenant_id=tenant_id,
                    charge_id=charge.id,
                    size_class=ALL_SIZES,
                    customer_class__isnull=True,
                    killed_at__isnull=True,
                ).exists()
                if not has_flat:
                    Amount.objects.create(
                        tenant_id=tenant_id,
                        charge_id=charge.id,
                        size_class=ALL_SIZES,
                        customer_class=None,
                        amount=Decimal(charge.legacy_amount),
                        effective_from=EPOCH,
                        effective_to=None,
                    )
                    moved += 1
                charge.legacy_amount = None
                fields.append("legacy_amount")
            if not charge.kind:
                charge.kind = _kind(charge.code, charge.charge_type, charge.is_base)
                fields.append("kind")
                kinds += 1
            if fields:
                charge.save(update_fields=fields)
        logger.info(
            "rating 0051 · tenant %s: %d price row(s) dated, %d flat amount(s) moved into "
            "'All sizes' rows, %d kind(s) set",
            tenant_id,
            dated,
            moved,
            kinds,
        )
    _set_tenant(connection, NO_TENANT)


def _backwards(apps, schema_editor):
    """Put each live every-class *All sizes* amount back on `charges.amount`
    and remove the rows this move wrote (from the epoch, never killed). Rows a
    clerk wrote after the move (dated later, or killed) are left — reversing
    must not destroy a price history somebody created."""
    Charge = apps.get_model("rating", "Charge")
    Amount = apps.get_model("rating", "ChargeCodeAmount")
    connection = schema_editor.connection
    for tenant_id in _tenant_ids(apps):
        _set_tenant(connection, tenant_id)
        for row in Amount.objects.filter(
            tenant_id=tenant_id,
            size_class=ALL_SIZES,
            customer_class__isnull=True,
            killed_at__isnull=True,
            effective_from=EPOCH,
        ):
            Charge.objects.filter(tenant_id=tenant_id, pk=row.charge_id).update(
                legacy_amount=row.amount
            )
            row.delete()
    _set_tenant(connection, NO_TENANT)


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0050_cr156_price_rows_dated_and_kinds"),
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunPython(_forwards, _backwards)]
