"""`CR-188-BRC10` on real PostgreSQL, plus what SQLite cannot show.

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
    pytest tests/test_cr188_staff_invite_email_pg.py --ds=config.settings.pgtest

1. **`password_links` is RLS ENABLE + FORCE**, read out of `pg_class`, and one
   utility's links are invisible to another under a role row security applies to.
2. **Every case of `test_cr188_staff_invite_email.py` again**, so the tenant
   GUC is the shipping kernel's and the token is looked up under it.
3. **A failure in the queue does not lose the user** (hard-won law 14): the
   queue write raises INSIDE the request's work, and on PostgreSQL a caught
   error would abort the transaction — the seam's savepoint is what keeps the
   user row. Proved by making the queue raise.
"""

from __future__ import annotations

import pytest

from apps.identity.models import User
from apps.notifications import staff_access_events
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr188_staff_invite_email import *  # noqa: F401,F403 — every case, re-run here
from tests.test_cr188_staff_invite_email import _add, _alex, _fresh_throttle, mail  # noqa: F401
from tests.test_us_idn_helpers import idn  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_identity_0014_password_links_is_enabled_AND_forced(idn):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            ["password_links"],
        )
        assert cursor.fetchone() == (True, True)


@pytest.mark.isolation
def test_identity_0014_one_utilitys_links_are_invisible_to_another(mail, rls):
    mail.seed_silvercreek()
    _add(_alex())
    assert_denied_without_context(rls, "password_links")
    assert_rls_scoped(rls, "password_links", owner=mail.silvercreek, intruder=mail.bluemesa)


def test_cr188_pg__a_failing_queue_never_loses_the_user(mail, monkeypatch):
    def broken(**_fields):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1/0")  # a real database error, mid-transaction

    monkeypatch.setattr(staff_access_events, "queue_staff_access_email", broken)
    mail.seed_silvercreek()
    response = _add(_alex())
    assert response.status_code == 201
    assert response.json()["invitation_email"]["status"] == "not_sent"
    assert User.objects.filter(email="tom@silvercreek.example").exists()
