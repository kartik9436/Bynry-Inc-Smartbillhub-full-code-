"""`OQ-FLD-12797` on real PostgreSQL 16, plus what SQLite cannot show.

    DATABASE_URL=postgres://postgres:postgres@localhost:5432/postgres \\
    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
    pytest tests/test_oq_fld_12797_field_app_pins_pg.py --ds=config.settings.pgtest

1. **`security_policies` — the table the pin list lives on — is RLS ENABLE +
   FORCE**, read out of `pg_class`, and the new column is covered by the same
   policy: one utility's list is invisible to another under a role row
   security applies to. No new table, so no new policy (`identity/0015`).
2. **Every case of `test_oq_fld_12797_field_app_pins.py` again**, so the
   tenant GUC is the shipping kernel's — in particular *one utility's list
   never reaches another utility's phones* — and a refused save, whose
   `ValidationError` is raised inside `transaction.atomic`, leaves nothing
   written on a database that does abort a transaction.
"""

from __future__ import annotations

import pytest

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
    writing_as_tenant,
)
from tests.test_oq_fld_12797_field_app_pins import *  # noqa: F401,F403 — every case, re-run here
from tests.test_oq_fld_12797_field_app_pins import _defaults, _pin, X2  # noqa: F401
from tests.test_us_idn_helpers import idn  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_security_policies_is_enabled_AND_forced_and_carries_the_pin_column(idn):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["security_policies"],
        )
        assert cursor.fetchone() == (True, True)
        cursor.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns"
            " WHERE table_name = 'security_policies' AND column_name = 'field_app_pins'"
        )
        assert cursor.fetchone() == ("jsonb", "YES")


@pytest.mark.isolation
def test_one_utilitys_pin_list_is_invisible_to_another(idn, rls):
    from apps.identity.models import SecurityPolicy

    for tenant in (idn.silvercreek, idn.bluemesa):
        with writing_as_tenant(tenant):
            SecurityPolicy.objects.create(
                tenant=tenant, field_app_pins=[*_defaults(), _pin(X2, "ISRG Root X2", "2040-09-17")]
            )
    assert_denied_without_context(rls, "security_policies")
    assert_rls_scoped(rls, "security_policies", owner=idn.silvercreek, intruder=idn.bluemesa)
