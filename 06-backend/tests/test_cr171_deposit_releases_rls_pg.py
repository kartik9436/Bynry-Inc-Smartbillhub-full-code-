# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 lane RULINGS — `deposit_releases` (payments/0047) and
#           its row-level security (payments/0048).
# Rules:    CLAUDE.md hard rule 1 · B2 §3 (the tenant isolation template)
# Tests:    this file — PostgreSQL ONLY (`requires_postgres`)
# ───────────────────────────────────────────────────────
"""`deposit_releases` under real row-level security.

`config/settings/test.py` is in-memory SQLite and has no RLS, so every case here
is skipped there by design and proves nothing until it runs on PostgreSQL:

    DATABASE_URL="postgres://postgres@127.0.0.1:55433/<db>?sslmode=disable" \\
      DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      pytest -q -p no:xdist tests/test_cr171_deposit_releases_rls_pg.py

The reads run under the probe role (`rls`), because a superuser or BYPASSRLS
role skips every policy, FORCE included; `rls.assert_is_a_real_proof()` fails
rather than skips if the probe could bypass anything.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.db import connection

from apps.payments.deposit_release_models import DepositRelease
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

TABLE = "deposit_releases"


def _release(tenant, key):
    return DepositRelease.objects.create(
        tenant=tenant,
        account_id=uuid4(),
        amount=Decimal("150.0000"),
        currency="USD",
        reason="move_in_cancelled",
        source_type="move_record",
        source_id=str(uuid4()),
        released_on=date(2026, 10, 5),
        idempotency_key=key,
    )


@requires_postgres
def test_deposit_releases_is_enabled_AND_forced():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        row = cursor.fetchone()
    assert row is not None, "deposit_releases does not exist — payments/0047 did not run"
    assert row == (True, True), f"hard rule 1: ENABLE and FORCE are both required, got {row}"


@requires_postgres
def test_no_tenant_context_denies_deposit_releases(rls):
    rls.assert_is_a_real_proof()
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_one_utilitys_release_is_invisible_to_another(rls, brazos, lonestar, dana, erin):
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        mine = _release(brazos, "brazos-1")
    with tenant_ctx(lonestar):
        _release(lonestar, "lonestar-1")
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar, owner_ids={str(mine.pk)})


@requires_postgres
def test_a_release_stamped_for_another_utility_is_refused(rls, brazos, lonestar, dana):
    rls.assert_is_a_real_proof()
    with tenant_ctx(brazos):
        _release(brazos, "brazos-check")
    assert_write_into_other_tenant_refused(rls, TABLE, owner=brazos, intruder=lonestar)
