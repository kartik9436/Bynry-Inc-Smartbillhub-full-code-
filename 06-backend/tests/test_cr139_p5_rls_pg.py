# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, task `P5.5`'s
#          second half: *"Plus its own RLS migration."* Outcome, verbatim:
#          *"Every tenant table has a policy."* The 🔒 file under review is
#          `apps/payments/migrations/0039_rls_cr139_p5_5_settlements.py`.
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set; RLS FORCE is on) · B2 §3 · hard-won law 14 (the
#          suite runs on SQLite, which has no row-level security at all) ·
#          hard-won law 7 (*192 skips once read as a pass* — the skip below is
#          loud on purpose)
# Tests:   this file — SKIPPED on SQLite BY DESIGN, and the skip is the point.
# ───────────────────────────────────────────────────────
"""`settlements` and `settlement_members` under real row-level security.

⚠ **`config/settings/test.py` HARDCODES IN-MEMORY SQLITE AND IGNORES
`DATABASE_URL`**, so every assertion about a policy passes there by vacuum.
Run it against a real database — the whole line, because a walkthrough header
that omits `JOBS_EAGER=false` costs an hour (`DEF-567`):

    10-scripts/proof-db.sh clone p5db
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p5db?sslmode=disable"
    pytest tests/test_cr139_p5_rls_pg.py

⚠ **BOTH TABLES, AND THE JOIN ROW IS THE ONE THAT GETS FORGOTTEN.**
`settlement_members` carries no identity a reader would call its own — it is a
join row — and **a join row with no policy reads exactly like a working
table**, because every query a lane writes reaches it through `settlement`,
which IS filtered. The hole only shows to somebody querying the members
directly, which is to say: to nobody, until it matters.

⚠ **AND THE READS RUN UNDER A PROBE ROLE RATHER THAN THE APPLICATION'S OWN.**
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
**unconditionally, `FORCE` included**, and the development role is often a
superuser (`DEF-2717`). `rls.assert_is_a_real_proof()` FAILS — never skips — if
the probe role could bypass anything.

⚠ **SET THE TENANT BEFORE COUNTING ANYTHING.** With `app.tenant_id` unset this
policy answers ZERO for every query, truthfully, and a lane that counts first
and reads the number as *the table is empty* has drawn the wrong conclusion.
That is `DEF-PAY-6166` on this same table's neighbour, where a backfill matched
**zero rows of seventy-four** and printed `OK`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import connection

from apps.payments import models as payment_models
from apps.payments import settlement_models

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLES = ("settlements", "settlement_members")
PAID_OUT_AT = datetime(2026, 8, 6, 3, 0, tzinfo=UTC)
POSTED_AT = datetime(2026, 8, 5, 14, 30, tzinfo=UTC)
PROVIDER = "payments_sandbox"


def _account_for(actor, tenant, *, service="electric"):
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(actor, address_line="1901 Bluestem Ln", services_available=[service])
    unit = make_unit(actor, premises["id"], label="Unit A", services=[service])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=f"A-{tenant.pk.hex[:8]}",
    )


def _payout_for(tenant, actor, *, code, service="electric"):
    """One payout with one member, inside `tenant`'s own context."""
    payment = payment_models.Payment.objects.create(
        tenant=tenant,
        account=_account_for(actor, tenant, service=service),
        amount=Decimal("100.0000"),
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
    )
    settlement = settlement_models.Settlement.objects.create(
        tenant=tenant,
        provider=PROVIDER,
        code=code,
        paid_out_at=PAID_OUT_AT,
        gross=Decimal("100.0000"),
        fees=Decimal("2.9000"),
        net=Decimal("97.1000"),
    )
    member = settlement_models.SettlementMember.objects.create(
        tenant=tenant,
        settlement=settlement,
        payment=payment,
        gross=Decimal("100.0000"),
        fee=Decimal("2.9000"),
    )
    return settlement, member


@requires_postgres
@pytest.mark.parametrize("table", TABLES)
def test_cr139_p5_5_both_tables_are_enabled_AND_forced(table):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the owner.

    Read out of `pg_class` rather than out of the migration file, because a
    migration that ran, a policy somebody dropped by hand and a policy that was
    never written **all look identical in the source tree.**

    ⚠ **WITHOUT `FORCE`, THIS FILE WOULD BE DECORATION.** The application's
    migration role OWNS every table in this schema, and PostgreSQL exempts a
    table's owner from its own policies unless `FORCE` is set.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [table],
        )
        row = cursor.fetchone()
    assert row is not None, f"{table} does not exist — payments/0038 did not run"
    assert row == (True, True), (
        f"CLAUDE.md hard rule 1 / B2 §3: `{table}` needs ENABLE *and* FORCE ROW LEVEL "
        f"SECURITY — pg_class says {row}. `P5.5`: *every tenant table has a policy*, and "
        "a join row with no policy reads exactly like a working table."
    )


@requires_postgres
def test_cr139_p5_5_no_tenant_context_denies_both_tables(rls):
    """With `app.tenant_id` unset, every named table errors under the probe role."""
    rls.assert_is_a_real_proof()
    assert_denied_without_context(rls, *TABLES)


@requires_postgres
def test_cr139_p5_5_one_tenants_payout_is_invisible_to_another(rls, brazos, lonestar, dana, erin):
    """Brazos Bend's payout and its member vanish under Lone Star Ridge.

    ⚠ **THE MEMBER IS ASSERTED SEPARATELY AND THAT IS THE POINT OF THIS CASE.**
    Every ordinary query reaches a member through its settlement, which IS
    filtered — so a `settlement_members` table with no policy of its own would
    pass every behavioural test in the product and leak to anyone who queried
    it directly.

    ⚠ Lone Star Ridge is **water-only** (its provisioning payload says so), so
    its account is created on `water`; an electric unit there is refused by
    metering with `VAL-005`, correctly.
    """
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        settlement, member = _payout_for(brazos, dana, code="po_brazos_0001")
    with tenant_ctx(lonestar):
        _payout_for(lonestar, erin, code="po_lonestar_0001", service="water")

    assert_rls_scoped(
        rls,
        "settlements",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(settlement.pk)},
    )
    assert_rls_scoped(
        rls,
        "settlement_members",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(member.pk)},
    )


@requires_postgres
@pytest.mark.parametrize("table", TABLES)
def test_cr139_p5_5_a_row_stamped_for_another_tenant_is_refused(rls, brazos, lonestar, dana, table):
    """The policy's `WITH CHECK`, in PostgreSQL's own words.

    `USING` lets the UPDATE find the row; `WITH CHECK` rejects the result. That
    is the table-agnostic form of *"an INSERT carrying another tenant's id"*,
    and it is the half a `USING`-only policy silently omits — a tenant could
    then read only its own rows and write into anybody's.
    """
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        _payout_for(brazos, dana, code=f"po_check_{table}")
    assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)
