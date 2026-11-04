# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10580 (beta MQ-006) — the platform code register, on
#           PostgreSQL 16
# Rules:    hard-won law 14 (a refused INSERT must not poison the office's
#           transaction) · hard rule 1 (the register is the DECLARED exemption;
#           `activation_codes` stays ENABLE + FORCE) · BR-IDN-006
# ───────────────────────────────────────────────────────
"""What SQLite cannot show about the register.

Run it (PostgreSQL 16 locally):

    DATABASE_URL=postgres://… JOBS_EAGER=false \\
    pytest tests/test_def_fld_10580_activation_lookup_pg.py --ds=config.settings.pgtest

1. **A forced collision redraws AND the transaction survives.** The draw runs
   inside the office's own transaction (`ATOMIC_REQUESTS` / *Create user*).
   On PostgreSQL a refused INSERT aborts that whole transaction unless it ran
   in a savepoint, so this test issues inside an outer `atomic()` and then
   keeps using the connection — without the savepoint it raises
   `InFailedSqlTransaction` (hard-won law 14).
2. **The register is not RLS-protected and needs no context** — and holds
   nothing but a digest, a tenant id and a timestamp.
3. **The tenant's own `activation_codes` is still walled**: under a role row
   security applies to, with no context the register answers and the codes do
   not; one utility's codes are invisible to the other.
4. Every SQLite case again, against the real kernel.
"""

from __future__ import annotations

import pytest
from django.db import connection, transaction

from apps.identity.models import ActivationCodeRegister
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_def_fld_10580_activation_lookup import *  # noqa: F401,F403
from tests.test_def_fld_10580_activation_lookup import _draws, _issue, _lookup, two  # noqa: F401
from tests.test_us_idn_helpers import idn  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_pg_a_collision_redraws_and_the_transaction_survives(two, monkeypatch):
    _draws(monkeypatch, "K7QM2P", "K7QM2P", "P3XW9A")
    assert _issue(two.silvercreek, two.marco) == "K7QM2P"
    with transaction.atomic():  # the office's request transaction
        assert _issue(two.bluemesa, two.jo) == "P3XW9A"
        # still usable after the refused INSERT — the savepoint is what makes it so
        assert ActivationCodeRegister.objects.count() == 2
    assert ActivationCodeRegister.objects.count() == 2
    assert _lookup("P3XW9A").json()["tenant"] == "bluemesa"


def test_pg_the_database_itself_refuses_a_duplicate_digest(two):
    from django.db import IntegrityError

    _issue(two.silvercreek, two.marco)
    row = ActivationCodeRegister.objects.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        ActivationCodeRegister.objects.create(
            code_digest=row.code_digest, tenant_id=two.bluemesa.id, created_at=row.created_at
        )


def test_pg_the_register_carries_no_rls_and_only_three_facts(two):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'activation_code_register'"
        )
        assert cursor.fetchone() == (False, False)
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'activation_code_register' ORDER BY column_name"
        )
        assert [r[0] for r in cursor.fetchall()] == ["code_digest", "created_at", "id", "tenant_id"]


@pytest.mark.isolation
def test_pg_with_no_context_the_register_answers_and_the_codes_do_not(two, rls):
    _issue(two.silvercreek, two.marco)
    _issue(two.bluemesa, two.jo)
    assert rls.count("activation_code_register") == 2
    assert rls.count("activation_codes") == 0
    assert rls.count("users") == 0


@pytest.mark.isolation
def test_pg_one_utilitys_codes_stay_invisible_to_the_other(two, rls):
    _issue(two.silvercreek, two.marco)
    _issue(two.bluemesa, two.jo)
    assert_rls_scoped(rls, "activation_codes", owner=two.silvercreek, intruder=two.bluemesa)
    assert_rls_scoped(rls, "users", owner=two.silvercreek, intruder=two.bluemesa)
