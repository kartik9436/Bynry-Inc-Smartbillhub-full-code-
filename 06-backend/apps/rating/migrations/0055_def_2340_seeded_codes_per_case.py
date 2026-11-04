# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2340 (the remaining half) — PO 2026-10-01, option A, point (3):
#          *"the four seeded codes TAP, IMPACT, DAMAGE, BULK-WATER are to be
#          set to entered when used"*.
# Rules:   BR-BIL-020 (narrowed) · BR-RAT-1054 (`per_case`) · CR-010 A2 ·
#          CLAUDE.md hard rule 1 (`app.tenant_id` set per tenant — RLS FORCE)
# Tests:   06-backend/tests/test_def_2340_seeded_codes_are_per_case.py
# ───────────────────────────────────────────────────────
"""rating 0055 — the four actual-cost codes a tenant never priced become
*entered when used*, per tenant, under RLS.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering). Row in
`12-governance/09-human-review-ledger.md`, 2026-10-01, `DEF-2340`.

WHAT IT CHANGES, AND ONLY THIS: `charges.amount_rule` from NULL to `per_case`
on a row that is

  * one of TAP, IMPACT, DAMAGE, BULK-WATER (matched case-insensitively, as the
    seed and `uq_charges_tenant_code` treat a code), AND
  * still in the state the seed wrote it: `amount_rule` NULL, no `percent`, no
    legacy `amount`, AND
  * holding NO live price row (`charge_code_amounts.killed_at IS NULL`), AND
  * not deleted (`charges.deleted_at IS NULL`).

**A code the tenant has priced is left alone** — any rule, any percent, any
live price row — because that price is the tenant's own choice and the ruling
does not reach it (decision log 2026-10-01). A deleted code is left alone
because nobody can use it.

IDEMPOTENT: a second run finds no NULL rule on these rows and writes nothing.

NO SCHEMA CHANGE: `amount_rule` is free text validated by
`services.AMOUNT_RULES`, which has carried `per_case` since `rating/0054`.

⚠ **THE CODES ARE COPIED HERE, NOT IMPORTED** — a migration runs against the
schema of its own moment for ever (`rating/0051`'s rule).

⚠ **HARD RULE 1: `app.tenant_id` IS SET FOR EACH TENANT** (`rating/0039`'s
lesson — RLS FORCE silently emptied `rating/0038`'s backfill because no tenant
was set, and the migration reported success over zero rows). The count moved
is logged per tenant so an empty run is visible.

REVERSE: puts `per_case` back to NULL only on these four codes where no live
price row exists — the exact state forward found. A code a clerk has since
priced (it then holds a live row, or another rule) is not touched.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

NO_TENANT = "00000000-0000-0000-0000-000000000000"
FOUR = ("TAP", "IMPACT", "DAMAGE", "BULK-WATER")
PER_CASE = "per_case"


def _tenant_ids(apps):
    return list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))


def _set_tenant(connection, tenant_id):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])


def _four(Charge, tenant_id):
    rows = Charge.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True)
    return [row for row in rows if (row.code or "").strip().upper() in FOUR]


def _has_live_price(Amount, tenant_id, charge_id):
    return Amount.objects.filter(
        tenant_id=tenant_id, charge_id=charge_id, killed_at__isnull=True
    ).exists()


def _forwards(apps, schema_editor):
    Charge = apps.get_model("rating", "Charge")
    Amount = apps.get_model("rating", "ChargeCodeAmount")
    connection = schema_editor.connection
    try:
        for tenant_id in _tenant_ids(apps):
            _set_tenant(connection, tenant_id)
            moved = []
            for charge in _four(Charge, tenant_id):
                if charge.amount_rule is not None:
                    continue  # already per_case, or priced by the tenant
                if charge.percent is not None or charge.legacy_amount is not None:
                    continue
                if _has_live_price(Amount, tenant_id, charge.id):
                    continue  # the tenant's own price — left alone
                Charge.objects.filter(pk=charge.pk, amount_rule__isnull=True).update(
                    amount_rule=PER_CASE
                )
                moved.append(charge.code)
            logger.info(
                "rating 0055 · tenant %s: %d code(s) set to entered when used %s",
                tenant_id,
                len(moved),
                sorted(moved),
            )
    finally:
        _set_tenant(connection, NO_TENANT)


def _backwards(apps, schema_editor):
    Charge = apps.get_model("rating", "Charge")
    Amount = apps.get_model("rating", "ChargeCodeAmount")
    connection = schema_editor.connection
    try:
        for tenant_id in _tenant_ids(apps):
            _set_tenant(connection, tenant_id)
            for charge in _four(Charge, tenant_id):
                if charge.amount_rule != PER_CASE or _has_live_price(Amount, tenant_id, charge.id):
                    continue
                Charge.objects.filter(pk=charge.pk).update(amount_rule=None)
    finally:
        _set_tenant(connection, NO_TENANT)


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0054_def_rat_8753_class_terms_and_per_case"),
        ("tenancy", "0001_initial"),
    ]

    operations = [migrations.RunPython(_forwards, _backwards)]
