# ── Trace ──────────────────────────────────────────────
# Change:   CR-194-BRC10 — refused field work kept on both phone and server
# Rules:    CLAUDE.md hard rule 1 (RLS ENABLE + FORCE, `work/0057`) ·
#           **hard-won law 14 (the copy's own savepoint)**
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""Where the copy's guarantees exist: PostgreSQL. Run::

    DJANGO_SETTINGS_MODULE=config.settings.pgtest JOBS_EAGER=false \\
      DATABASE_URL=postgres://postgres:postgres@localhost:5432/sbh \\
      pytest tests/test_cr194_refused_field_work_pg.py --ds=config.settings.pgtest

⚠ **THE POISON IS A REAL FAILED STATEMENT INSIDE `keep()`** — `SELECT 1/0`,
which PostgreSQL refuses with `division by zero` and which aborts the enclosing
transaction unless a SAVEPOINT stands between them. SQLite would raise the
same error and then carry on as though nothing had happened, which is the
other half of why this file exists (law 14).
"""

from __future__ import annotations

import contextlib

import pytest
from django.db import connection, transaction

from apps.work import refused_items, sync
from apps.work.refused_models import WorkRefusedItem
from apps.work.sync_models import WorkSyncReceipt
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr187_sync_volume import as_field, read_route, reading_items, seed_reference, technician
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]

TABLE = "work_refused_items"


def test_work_0057_the_table_is_enabled_and_forced(brazos):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        assert cursor.fetchone() == (True, True)


def _seed(tenant, actor):
    with tenant_ctx(tenant):
        assert refused_items.keep(
            door="reads",
            item={"key": f"pg-{tenant.id}", "kind": "reading", "value": "1", "unit": "gal"},
            refusal={"detail": {"reason": "unit_missing", "message_key": "work.mobile.reads.unit_missing"}},
            courier=actor,
        )


@pytest.mark.isolation
def test_work_0057_no_context_sees_nothing(brazos, dana, rls):
    _seed(brazos, dana)
    assert_denied_without_context(rls, TABLE)


@pytest.mark.isolation
def test_work_0057_one_utilitys_copies_are_invisible_to_the_other(brazos, lonestar, dana, rls):
    _seed(brazos, dana)
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar)
    assert_write_into_other_tenant_refused(rls, TABLE, owner=brazos, intruder=lonestar)


# ══════════════════════════════════════════════════════════════════════════
# Law 14 — a copy that cannot be written never costs the batch
# ══════════════════════════════════════════════════════════════════════════
def _three_with_a_refusal_in_the_middle(dana, brazos):
    """Readings 1 and 3 apply; reading 2 says `gal` on a kWh job and the
    service refuses it (hard rule 3) — so its COPY is written between two
    items that must both commit."""
    seed_reference()
    ortiz = technician(brazos)
    oid, rows = read_route(dana, brazos, ortiz, readings=3)
    items = reading_items(oid, rows)
    items[1]["payload"] = {**items[1]["payload"], "unit": "gal"}
    return oid, items, ortiz


def _poisoned_photos(*_args, **_kwargs):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1/0")
    return [], []  # pragma: no cover — never reached


def test_a_copy_that_fails_to_write_does_not_poison_the_batch_on_postgres(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        oid, items, ortiz = _three_with_a_refusal_in_the_middle(dana, brazos)
        monkeypatch.setattr(refused_items, "_photos_of", _poisoned_photos)
        out = sync.sync_batch(as_field(ortiz), oid, {"items": items})
        monkeypatch.undo()
        receipts = set(WorkSyncReceipt.objects.filter(work_order_id=oid).values_list("key", flat=True))
        copies = WorkRefusedItem.objects.filter(work_order_id=oid).count()

    assert [i["result"] for i in out["items"]] == ["accepted", "refused", "accepted"]
    # The refusal goes back to the phone exactly as before — WITHOUT the flag,
    # because no copy exists and the phone must not promise one.
    assert "kept_for_office" not in out["items"][1]["detail"]
    # …and items 1 and 3 are TRUE AFTER COMMIT, not merely in the response.
    assert receipts == {items[0]["key"], items[2]["key"]}
    assert copies == 0


def test_the_same_batch_keeps_its_copy_when_nothing_fails_on_postgres(brazos, dana):
    with tenant_ctx(brazos):
        oid, items, ortiz = _three_with_a_refusal_in_the_middle(dana, brazos)
        out = sync.sync_batch(as_field(ortiz), oid, {"items": items})
        copy = WorkRefusedItem.objects.get(work_order_id=oid)
        spent = WorkSyncReceipt.objects.filter(work_order_id=oid, key=items[1]["key"]).exists()

    assert out["items"][1]["detail"]["kept_for_office"] is True
    assert copy.key == items[1]["key"] and copy.payload["unit"] == "gal"
    assert spent is False, "a copy is never a receipt"


class _NoNestedAtomic:
    """`transaction` as `refused_items.py` sees it with the copy's own
    `atomic()` made a no-op — the copy written straight into the batch's
    transaction, the shape law 14 forbids."""

    @contextlib.contextmanager
    def atomic(self, *args, **kwargs):
        yield


def test_WITHOUT_the_copys_savepoint_the_batch_is_LOST_on_postgres(brazos, dana, monkeypatch):
    """The red proof, in the file (law 7): strip the copy's savepoint and the
    same poisoned copy aborts the batch's transaction — the next item's first
    query raises `InFailedSqlTransaction` and the whole day's batch is gone."""
    from django.db.utils import DatabaseError

    with tenant_ctx(brazos):
        oid, items, ortiz = _three_with_a_refusal_in_the_middle(dana, brazos)
        monkeypatch.setattr(refused_items, "_photos_of", _poisoned_photos)
        monkeypatch.setattr(refused_items, "transaction", _NoNestedAtomic())
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                sync.sync_batch(as_field(ortiz), oid, {"items": items})
        monkeypatch.undo()
        receipts = WorkSyncReceipt.objects.filter(work_order_id=oid).count()

    assert receipts == 0, "nothing of the batch survives a poisoned transaction"
