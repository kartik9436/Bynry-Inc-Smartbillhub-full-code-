# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 wave E — the refusal codes, on the vendor that can
#           actually hold the guarantee.
# Rules:    CLAUDE.md hard-won law 14 (a caught database error and a
#           `continue` is a SAVEPOINT or it is data loss, and SQLite cannot
#           see the difference) · BR-INT-044 (the refusal reveals nothing)
# Tests:    this file. The everyday half is tests/test_cr110_refusal_codes.py
# Impacts:  apps/integrations/runners/serve.py::record_refusal
# ───────────────────────────────────────────────────────
"""`record_refusal` must never change WHETHER we refuse — proved on PostgreSQL.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_cr110_refusal_codes_pg.py

⚠ **THIS FILE EXISTS BECAUSE OF THE EXACT TRAP CLAUDE.md LAW 14 NAMES.**
`record_refusal` catches the record's failure and carries on, because a refusal
that turns into a `500` because its own bookkeeping failed is a LOUDER oracle
than any of the eight codes — a caller would learn from the `500` that they got
one of the five causes that writes a row rather than the one that does not.

**On PostgreSQL one failed statement ABORTS THE WHOLE TRANSACTION.** So the
obvious version — `try: record() except Exception: pass` — would swallow the
error and then lose the response anyway, at commit, with
`InFailedSqlTransaction`. The nested `transaction.atomic()` is a SAVEPOINT and
is the only construct that lets this continue. `config/settings/test.py`
hardcodes in-memory SQLite, **which has no aborted-transaction state at all**,
so the broken version passes the entire default suite green on every machine.

Every case carries `requires_postgres` and SKIPS on SQLite rather than passing
vacuously.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.integrations import models, partner_api
from apps.integrations.runners import serve
from tests.isolation_helpers import requires_postgres  # noqa: F401
from tests.test_us_int_041_partner_surface import (  # noqa: F401
    _bytes,
    _partner_get,
    _payments,
    aclarian,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx


@requires_postgres
@pytest.mark.django_db
def test_a_failed_record_does_not_take_the_refusal_down_with_it(
    brazos, dana, aclarian, monkeypatch
):
    """The savepoint, on the only vendor where the difference is visible.

    A statement is made to fail for real — `SELECT 1/0` inside the write — so
    the transaction is genuinely aborted rather than merely raising a Python
    exception. With the nested `transaction.atomic()` the refusal still goes out
    as `404` with the one body, and the request can go on querying. Remove that
    one `with` and the next ORM call raises `InFailedSqlTransaction`, which
    reaches the caller as a `500` — a refusal that says, loudly, *you are one of
    the five causes that writes a row*.
    """

    def _explode(**kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1/0")

    with tenant_ctx(brazos):
        _payments(brazos, dana, 3)
        credential = models.IntegrationCredential.objects.get()
        models.IntegrationCredential.objects.filter(pk=credential.pk).update(is_active=False)

    monkeypatch.setattr(serve, "record_read", _explode)
    refused = _partner_get(brazos, partner_api.partner_payments)

    assert refused.status_code == 404
    assert _bytes(refused) == (
        b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    )

    # ⚠ THE ASSERTION THE FILE EXISTS FOR. Without the savepoint this line
    # raises `InFailedSqlTransaction` rather than returning a number.
    with tenant_ctx(brazos):
        assert models.IntegrationRun.objects.count() == 0


@requires_postgres
@pytest.mark.django_db
def test_the_causes_are_recorded_on_postgres_too(brazos, dana, aclarian):
    """The ordinary path, on the real vendor — the row lands and names its cause.

    The everyday suite proves this on SQLite; `integration_run` is PARTITIONED
    on PostgreSQL and its composite primary key is a shape SQLite does not have,
    so *the row can be written at all* is a claim that has to be made here too.
    """
    with tenant_ctx(brazos):
        _payments(brazos, dana, 3)
        credential = models.IntegrationCredential.objects.get()
        models.IntegrationCredential.objects.filter(pk=credential.pk).update(is_active=False)

    _partner_get(brazos, partner_api.partner_payments)

    with tenant_ctx(brazos):
        row = models.IntegrationRun.objects.get()
    assert {one["ref"] for one in row.items} == {serve.CODE_KEY_REVOKED}
    assert row.summary.split(" · ")[0] == "key revoked"
    assert (row.attempted, row.succeeded) == (0, 0)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 wave E
# generated: 2026-09-16 by the CR-110-BRC04 wave E build lane
# checklist: A✔ B n/a C✔ D✔ E n/a F✔ G✔ H=pending(🔒 row in 09-human-review-ledger.md)
# gates: DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local pytest tests/test_cr110_refusal_codes_pg.py
# exceptions: none
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
