"""CR-173-BRC10 on PostgreSQL 16 — the halves SQLite cannot prove.

* **One file per utility per day** is a partial unique index, and the claim is
  taken inside a SAVEPOINT. On PostgreSQL a refused INSERT ABORTS the whole
  transaction unless it was in a savepoint; SQLite has no such state, so the
  default suite would pass a version with the savepoint deleted (hard-won law
  14). The case below refuses the claim and then keeps using the SAME
  transaction — which raises `InFailedSqlTransaction` without the savepoint.
* **One active credential per (connection, slot)** is an EXCLUDE constraint
  that only PostgreSQL has.
* **`integration_file_delivery` is RLS-FORCEd** and invisible without a tenant.

RUN IT (it SKIPS on the default SQLite settings):

    DATABASE_URL="postgres://postgres@/sbh?host=<socket dir>&port=<port>" \\
    JOBS_EAGER=false pytest --ds=config.settings.pgtest tests/test_cr173_newworld_sftp_pg.py
"""

from __future__ import annotations

from datetime import date

import pytest
from django.db import IntegrityError, connection, transaction

from apps.integrations import models, receipt_push
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr173_newworld_sftp import _connect, _past_day, _set_up, server  # noqa: F401
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

TABLE = "integration_file_delivery"


def _claim(conn, day: date, *, status="sent", resend=False):
    return models.IntegrationFileDelivery.objects.create(
        tenant_id=conn.tenant_id,
        connection=conn,
        operation=receipt_push.OPERATION,
        data_day=day,
        filename=receipt_push.filename_for(day),
        folder="/",
        status=status,
        is_resend=resend,
        trigger="scheduled",
    )


@requires_postgres
@pytest.mark.django_db
def test_the_table_is_walked_by_the_isolation_probe():
    assert TABLE in models.TENANT_TABLES


@requires_postgres
@pytest.mark.django_db
def test_a_second_claim_for_a_day_is_refused_and_the_transaction_survives(brazos, dana, server):
    """The refusal, and the savepoint that keeps the transaction usable after it."""
    day = _past_day()
    with live_tenant_context(brazos.id):
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server)
        assert receipt_push.send(day, trigger="scheduled").done
        again = receipt_push.send(day, trigger="scheduled")
        # Still usable: a query after the refused claim. Without the savepoint
        # in `receipt_push.send` this raises InFailedSqlTransaction.
        sent = models.IntegrationFileDelivery.objects.filter(connection=conn, data_day=day).count()
    assert again.code == receipt_push.CODE_ALREADY
    assert sent == 1
    assert list(server.files()) == [receipt_push.filename_for(day)]


@requires_postgres
@pytest.mark.django_db
def test_a_run_racing_one_in_flight_is_refused_by_the_index_and_the_transaction_survives(
    brazos, dana, server
):
    """THE CASE THE SAVEPOINT EXISTS FOR. The polite `already_sent` read only
    sees a FINISHED file; a second run racing one still `sending` passes it and
    reaches the INSERT, which the index refuses. Without the savepoint the
    refusal aborts the whole PostgreSQL transaction and the next statement
    raises `InFailedSqlTransaction` — proved red by deleting it (law 7)."""
    day = _past_day()
    with live_tenant_context(brazos.id):
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server)
        _claim(conn, day, status="sending")  # another run, mid-upload
        raced = receipt_push.send(day, trigger="scheduled")
        rows = models.IntegrationFileDelivery.objects.filter(connection=conn, data_day=day).count()
    assert raced.code == receipt_push.CODE_ALREADY
    assert rows == 1
    assert server.files() == {}, "the racing run uploaded nothing"


@requires_postgres
@pytest.mark.django_db
def test_a_file_failing_the_template_check_writes_no_claim_and_leaves_the_day_sendable(
    brazos, dana, server, monkeypatch
):
    """DEF-INT-10304 (PO 2026-10-21: validate before writing to the outbox),
    on PostgreSQL: the refused file writes NO delivery claim, the failed run
    row survives, and the transaction is still usable — so once the fault is
    gone the SAME day sends normally, not *already sent*."""
    from apps.integrations import newworld

    real_render = newworld.render
    monkeypatch.setattr(
        receipt_push.newworld, "render",
        lambda receipts: real_render(receipts).replace(b"<ROOT", b"<Receipts").replace(
            b"</ROOT>", b"</Receipts>"
        ),
    )
    day = _past_day()
    with live_tenant_context(brazos.id):
        conn = _connect(brazos, dana)
        _set_up(brazos, dana, server)
        refused = receipt_push.send(day, trigger="scheduled")
        claims = models.IntegrationFileDelivery.objects.filter(connection=conn, data_day=day).count()
        failed_runs = models.IntegrationRun.objects.filter(connection=conn, outcome="failed").count()
        monkeypatch.setattr(receipt_push.newworld, "render", real_render)
        sent = receipt_push.send(day, trigger="scheduled")
    assert refused.code == receipt_push.CODE_FAILED
    assert refused.sentence == receipt_push.INVALID_SENTENCE
    assert claims == 0 and failed_runs == 1
    assert sent.done, "the day was never claimed, so it sends once the file is right"
    assert list(server.files()) == [receipt_push.filename_for(day)]
    assert newworld.validate(server.files()[receipt_push.filename_for(day)]) == []


@requires_postgres
@pytest.mark.django_db
def test_the_index_itself_refuses_the_second_successful_file(brazos, dana):
    """Below the application: two `sent` rows for one day cannot both exist —
    and a failed one, and a person's resend, are outside the guard."""
    day = date(2026, 10, 5)
    with live_tenant_context(brazos.id):
        conn = _connect(brazos, dana)
        _claim(conn, day, status="failed")
        _claim(conn, day, status="sent")
        _claim(conn, day, status="sent", resend=True)
        with pytest.raises(IntegrityError), transaction.atomic():
            _claim(conn, day, status="sent")
        with pytest.raises(IntegrityError), transaction.atomic():
            _claim(conn, day, status="sending")


@requires_postgres
@pytest.mark.django_db
def test_one_active_credential_per_slot_is_the_databases_rule(brazos, dana):
    with live_tenant_context(brazos.id):
        conn = _connect(brazos, dana)  # primary slot, active
        models.IntegrationCredential.objects.create(
            tenant_id=brazos.id, connection=conn, version=50, is_active=True,
            slot="send_file", payload_enc="{}", masked_hint="••••fake",
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            models.IntegrationCredential.objects.create(
                tenant_id=brazos.id, connection=conn, version=51, is_active=True,
                slot="send_file", payload_enc="{}", masked_hint="••••fake",
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT conname FROM pg_constraint WHERE conname LIKE 'ex_integration_credential_one_active%'"
            )
            names = sorted(row[0] for row in cursor.fetchall())
    assert names == ["ex_integration_credential_one_active_slot"]


@requires_postgres
@pytest.mark.django_db
def test_without_a_tenant_no_delivery_row_is_reachable(rls, brazos, dana):
    with live_tenant_context(brazos.id):
        _claim(_connect(brazos, dana), date(2026, 10, 5))
    assert_denied_without_context(rls, TABLE)


@requires_postgres
@pytest.mark.django_db
def test_one_utilitys_files_vanish_under_another_utilitys_context(rls, brazos, lonestar, dana, erin):
    with live_tenant_context(brazos.id):
        row = _claim(_connect(brazos, dana), date(2026, 10, 5))
    with live_tenant_context(lonestar.id):
        _connect(lonestar, erin)
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar, owner_ids={str(row.id)})
