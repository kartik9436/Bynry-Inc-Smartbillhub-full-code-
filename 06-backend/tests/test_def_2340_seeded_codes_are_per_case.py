# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2340 (the remaining half) — the four seeded actual-cost charge
#           codes TAP, IMPACT, DAMAGE and BULK-WATER are set to *entered when
#           used* (`amount_rule = per_case`).
# Ruling:   decision log 2026-10-01, "A ONE-TIME FEE BILL MAY CARRY THE AMOUNT
#           THE CLERK TYPES — FOR THE FOUR ACTUAL-COST CHARGES ONLY", point (3).
# Rules:    BR-BIL-020 (narrowed) · BR-RAT-1054 · CR-010 A2 · hard rule 1
# Run:      sqlite (default suite) AND PostgreSQL 16:
#             DATABASE_URL=postgres://… pytest tests/test_def_2340_seeded_codes_are_per_case.py \
#               --ds=config.settings.pgtest --reuse-db
# ───────────────────────────────────────────────────────
"""The four actual-cost codes say they are priced when used — on a new tenant
by the seed, on an existing one by `rating/0055` — and a tenant's own price
survives the move.

WHAT EACH CASE HAS TO PROVE
---------------------------
1. A NEW tenant's TAP, IMPACT, DAMAGE and BULK-WATER are `per_case` and carry
   no price row (the seed in `services.seed_reference_list`).
2. The worked figure put to the PO: a one-time Fee bill for TAP with
   **$1,250.00** entered previews ONE line of **$1,250.00**, through the real
   preview endpoint.
3. TAP with no amount entered is refused, and the refusal names TAP.
4. A tenant that priced TAP at **$500.00** keeps $500.00 after the migration,
   and a typed amount for it is refused (BR-BIL-020 holds for a priced code).
5. The migration moves an unpriced seeded code, leaves a deleted one, and a
   second run writes nothing.

WHAT WOULD MAKE THIS PASS WRONGLY: a migration that skipped every row would
pass case 4 — so case 5 asserts the unpriced row DID move. A preview that
showed the entered figure without pricing it would pass a "charge block"
check, so case 2 reads the bill's LINES and its TOTAL, not the charge block.
"""

from __future__ import annotations

import importlib
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.billing import api as billing_api
from apps.billing import fee_bill
from apps.billing.exceptions import BillingRuleError
from apps.rating.constants import ALL_SIZES
from apps.rating import models as rating_models
from tests.test_cr108_w1_one_time_fee_lines_and_books import a_one_time_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db

FOUR = ("TAP", "IMPACT", "DAMAGE", "BULK-WATER")
FEE_ON = date(2026, 7, 9)


def _migrate():
    """Run `rating/0055`'s forward step exactly as `migrate` would."""
    migration = importlib.import_module(
        "apps.rating.migrations.0055_def_2340_seeded_codes_per_case"
    )
    migration._forwards(django_apps, SimpleNamespace(connection=connection))


def _clerk(tenant):
    return FakeUser(user_id=staff_actor(tenant, "billing_clerk", "priya@def2340.test").id)


def _preview(tenant, account, **extra):
    body = {
        "account_id": str(account.id),
        "kind": "fee",
        "charge_code": "TAP",
        "bill_date": FEE_ON.isoformat(),
        "due_days": 21,
        **extra,
    }
    return api_call(
        billing_api.one_time_preview,
        "post",
        user=_clerk(tenant),
        role="billing_clerk",
        tenant=tenant,
        data=body,
    )


def test_a_new_tenants_four_actual_cost_codes_are_entered_when_used(brazos):
    with tenant_ctx(brazos):
        rows = {
            row.code: row
            for row in rating_models.Charge.objects.filter(
                tenant=brazos, code__in=FOUR, deleted_at__isnull=True
            )
        }
        assert sorted(rows) == sorted(FOUR)
        assert {code: row.amount_rule for code, row in rows.items()} == {
            code: "per_case" for code in FOUR
        }
        assert not rating_models.ChargeCodeAmount.objects.filter(
            charge_id__in=[r.id for r in rows.values()]
        ).exists()


def test_a_tap_fee_bill_with_1250_entered_previews_one_line_of_1250(brazos, dana):
    with tenant_ctx(brazos):
        account = a_one_time_account(brazos, dana)
    response = _preview(brazos, account, entered_amount="1250.00")
    assert response.status_code == 200, response.data
    lines = [line for group in response.data["bill"]["groups"] for line in group["lines"]]
    assert len(lines) == 1, lines
    assert Decimal(lines[0]["amount"]) == Decimal("1250.00")
    assert Decimal(response.data["bill"]["total"]) == Decimal("1250.00")
    assert Decimal(response.data["charge"]["amount"]) == Decimal("1250.00")


def test_tap_with_no_amount_entered_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(BillingRuleError, match=r"'TAP'.*no amount was entered"):
            fee_bill.charge_code_line("TAP")
        account = a_one_time_account(brazos, dana)
    response = _preview(brazos, account)
    assert response.status_code == 422, response.data
    assert "TAP" in str(response.data)


def test_a_tenant_that_priced_tap_at_500_keeps_it_and_a_typed_amount_is_refused(brazos):
    with tenant_ctx(brazos):
        tap = rating_models.Charge.objects.get(tenant=brazos, code="TAP")
        # The tenant's own price, as the screens store one: a flat rule and an
        # *All sizes* row from the epoch.
        rating_models.Charge.objects.filter(pk=tap.pk).update(amount_rule="flat")
        rating_models.ChargeCodeAmount.objects.create(
            tenant=brazos,
            charge_id=tap.id,
            size_class=ALL_SIZES,
            customer_class=None,
            amount=Decimal("500.0000"),
            effective_from=date(2000, 1, 1),
        )
    _migrate()
    with tenant_ctx(brazos):
        tap.refresh_from_db()
        assert tap.amount_rule == "flat"
        assert fee_bill.charge_code_line("TAP").amount == Decimal("500.00")
        with pytest.raises(
            BillingRuleError, match="BR-BIL-020|no amount may be typed|entered when used"
        ):
            fee_bill.charge_code_line("TAP", entered_amount=Decimal("1250.00"))


def test_the_migration_moves_only_unpriced_live_codes_and_a_rerun_writes_nothing(brazos):
    with tenant_ctx(brazos):
        # The state every tenant provisioned before this fix holds.
        rating_models.Charge.objects.filter(tenant=brazos, code__in=FOUR).update(amount_rule=None)
        rating_models.Charge.objects.filter(tenant=brazos, code="DAMAGE").update(
            deleted_at=datetime(2026, 9, 1, tzinfo=UTC)
        )
    _migrate()
    with tenant_ctx(brazos):
        rules = dict(
            rating_models.Charge.objects.filter(tenant=brazos, code__in=FOUR).values_list(
                "code", "amount_rule"
            )
        )
    assert rules == {
        "TAP": "per_case",
        "IMPACT": "per_case",
        "BULK-WATER": "per_case",
        "DAMAGE": None,
    }
    _migrate()
    with tenant_ctx(brazos):
        again = dict(
            rating_models.Charge.objects.filter(tenant=brazos, code__in=FOUR).values_list(
                "code", "amount_rule"
            )
        )
    assert again == rules
