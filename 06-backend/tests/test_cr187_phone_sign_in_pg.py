# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — phone number as a field-app sign-in name, on
#           PostgreSQL 16
# Rules:    hard rule 1 (RLS ENABLE + FORCE on `users` survives identity/0013)
#           · BR-IDN-001/029 (unique inside one utility — the partial index) ·
#           hard-won law 14 (the duplicate refusal is checked before the write,
#           so no transaction is poisoned)
# ───────────────────────────────────────────────────────
"""Every case of `test_cr187_phone_sign_in.py` again, on real PostgreSQL, plus
what SQLite cannot show: FORCE still on `users`, and the partial unique index.

    DJANGO_SETTINGS_MODULE=config.settings.pgtest \\
    DATABASE_URL=postgres://postgres:postgres@localhost:5432/sbh JOBS_EAGER=false \\
    pytest tests/test_cr187_phone_sign_in_pg.py --ds=config.settings.pgtest
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, connection, transaction

from apps.identity.models import User
from tests.isolation_helpers import requires_postgres, writing_as_tenant
from tests.test_cr187_phone_sign_in import *  # noqa: F401,F403 — every case, re-run here
from tests.test_cr187_phone_sign_in import phone  # noqa: F401
from tests.test_us_idn_helpers import idn  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_users_is_still_enabled_AND_forced_after_identity_0013(phone):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'users' AND relnamespace = 'public'::regnamespace"
        )
        assert cursor.fetchone() == (True, True)


def test_the_partial_unique_index_exists_and_bites(phone):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_users_tenant_phone_e164'"
        )
        (definition,) = cursor.fetchone()
    assert "UNIQUE" in definition and "phone_e164 IS NOT NULL" in definition
    with writing_as_tenant(phone.silvercreek):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                User.objects.filter(pk=phone.users.priya.pk).update(phone_e164="+15125550104")
        # NULL twice is not a duplicate.
        User.objects.filter(pk=phone.users.priya.pk).update(phone_e164=None)
        User.objects.filter(pk=phone.users.diana.pk).update(phone_e164=None)
