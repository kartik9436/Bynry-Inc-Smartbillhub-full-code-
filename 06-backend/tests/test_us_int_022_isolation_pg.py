# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-022 (EP-INT-06) TC-6 on a real database — one tenant's dead
#           mail server stays one tenant's problem. Screens: S8 · S142
# Rules:    BR-INT-041 (P5 — one tenant's outage is one tenant's outage) ·
#           BR-INT-024 (a skipped window is RECORDED as skipped) ·
#           CLAUDE.md hard rule 1 (RLS FORCE, proved under the NON-superuser
#           probe role) · hard-won law 14 (a guarantee the database enforces is
#           proved on PostgreSQL or it is not proved)
# Tests:    this file. The SQLite half is tests/test_us_int_022_isolation.py.
# Impacts:  apps/integrations/services.py (`guarded_adapter_call` writes the
#           breaker onto `integration_connection.config`) · runners/deliver.py
# ───────────────────────────────────────────────────────
"""`US-INT-022` on PostgreSQL — the isolation SQLite cannot express.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/<db> \\
        pytest tests/test_us_int_022_isolation_pg.py

⚠ **WHY THIS FILE EXISTS, AND IT IS NOT A DUPLICATE OF THE SQLITE ONE.** This
wave is *about* tenant isolation, so it is the last place to take isolation on
trust. The SQLite file beside it proves the POLICY — the cap, the breaker, the
skipped run row, and that Lone Star Ridge's connection is untouched while Brazos
Bend's breaker is open. It cannot prove ROW-LEVEL isolation at all: SQLite has no
row-level security, so a queryset under a tenant context returns both utilities'
rows there and the honest thing is to assert it here instead. That file says so
in the case that would otherwise have looked like a proof.

⚠ **AND A GREEN ISOLATION GATE IS NOT EVIDENCE (`DEF-GOV-4024`, 2026-09-05).**
The repository's tenant-isolation gate has been running the isolation suite
WITHOUT pointing it at PostgreSQL, so it inherits SQLite and skips the proofs it
exists to run — **46 of 238 run, 192 skip, exit code 0.** A wave about one
tenant's outage not reaching another may not lean on that. Every case below
carries `requires_postgres` and **SKIPS rather than passing vacuously**, so a
run on the default suite reports nothing rather than reporting success.

WHAT IS PROVED HERE
-------------------
1. The breaker lives on `integration_connection.config`, which is a tenant table
   under RLS `FORCE`: with no `app.tenant_id` set, the probe role sees nothing,
   and under one tenant's context the other's connection and its runs are
   invisible — asserted under the **non-superuser** probe role, because the
   developer role is a superuser and bypasses row security.
2. The skipped run row is real on a real database: `outcome = 'skipped'` with
   `attempted = 0`, written through the runner rather than constructed here.
3. And it is still append-only — a hand-written `UPDATE` turning a skipped run
   into a succeeded one is refused by the trigger, which is the statement that
   would otherwise quietly erase the fact that a window was missed.
"""

import time

import pytest
from django.db import DatabaseError, connection, transaction

from apps.integrations import models, runtime, services
from apps.integrations.runners import deliver
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin


class _Operation:
    name = "send_message"
    direction = "out"
    initiative = "us"
    timeout_s = 30
    concurrency = 2


class HangingAdapter:
    """A mail server that has stopped answering."""

    def execute(self, view, secrets, work):  # noqa: ARG002 — protocol shape
        raise runtime.ProviderTimeout("the mail server did not answer")


def _smtp(actor, tenant):
    return services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key="email_smtp",
        environment="production",
        label=f"{tenant.name} mailbox",
        config={"host": "smtp.example", "port": 587},
    )


def _open_the_breaker(row, *, attempts=3):
    """Three consecutive timeouts, through the REAL runner — never by writing
    the config by hand, which would prove only that a dict round-trips."""
    for _ in range(attempts):
        with pytest.raises(runtime.ProviderTimeout):
            deliver.execute_run(
                connection=row,
                operation=_Operation(),
                adapter=HangingAdapter(),
                work=[{"ref": "A-10432", "address": "a@example.test"}],
                trigger="scheduled",
            )
    row.refresh_from_db()
    return row


@requires_postgres
@pytest.mark.django_db
def test_us_int_022_the_breaker_state_is_a_tenant_row_and_another_tenant_cannot_see_it(
    brazos, lonestar, dana, erin, rls
):
    """`BR-INT-041` and hard rule 1 together, on a real database.

    ⚠ **THE BREAKER IS DURABLE, SO IT IS TENANT DATA**, and that is the reason
    this case exists rather than being obvious. Making the breaker survive
    across workers meant putting it in a database column; putting it in a
    database column means it is subject to exactly the same isolation as every
    other row, and a bug there would leak *which of your providers is down* —
    an operational fact about another utility — to anyone who can reach the
    table. Proved under the NON-superuser probe role, because the developer
    role bypasses row security and would report success either way.
    """
    with live_tenant_context(brazos.id):
        sick = _open_the_breaker(_smtp(dana, brazos))
        assert runtime.is_open(
            runtime.BreakerState.from_config(sick.config), now=time.time()
        ), "the sick connection's breaker should be open"

    with live_tenant_context(lonestar.id):
        healthy = _smtp(erin, lonestar)
        assert healthy.provider_key == sick.provider_key, (
            "both utilities must be on the SAME provider key or this proves nothing — "
            "a breaker keyed on the provider is the failure being ruled out"
        )
        healthy.refresh_from_db()
        assert runtime.BreakerState.from_config(healthy.config).consecutive_timeouts == 0
        assert healthy.status != models.STATUS_NOT_WORKING

    # ── the isolation itself, under the non-superuser probe ──────────────
    assert_rls_scoped(
        rls,
        "integration_connection",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(sick.id)},
    )
    assert_rls_scoped(
        rls,
        "integration_run",
        owner=brazos,
        intruder=lonestar,
    )


@requires_postgres
@pytest.mark.django_db
def test_us_int_022_a_skipped_window_is_a_real_row_on_a_real_database(brazos, dana):
    """`BR-INT-024` — the window nobody dialled, written down, on PostgreSQL.

    The eighth outcome word arrived with `integrations/0005`, whose whole claim
    is that it changes the database not at all (`sqlmigrate` prints `(no-op)`).
    That claim is only worth something if a row carrying the new value can
    actually be written and read back HERE, on the partitioned table, rather
    than on SQLite where the column has no opinion.
    """
    with live_tenant_context(brazos.id):
        row = _open_the_breaker(_smtp(dana, brazos))

        run = deliver.execute_run(
            connection=row,
            operation=_Operation(),
            adapter=HangingAdapter(),
            work=[{"ref": "A-10432", "address": "a@example.test"}],
            trigger="scheduled",
        )
        assert run.outcome == models.OUTCOME_SKIPPED
        assert run.attempted == 0

        # read back through a RAW cursor — the value is in the column, not just
        # in a Python attribute that happens to hold it
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT outcome, attempted, summary FROM integration_run WHERE id = %s",
                [str(run.id)],
            )
            outcome, attempted, summary = cursor.fetchone()
        assert outcome == "skipped"
        assert attempted == 0
        assert summary and "not answering" in summary


@requires_postgres
@pytest.mark.django_db
def test_us_int_022_a_skipped_window_cannot_be_quietly_turned_into_a_success(brazos, dana):
    """The most dangerous single statement about this wave's new row.

    A skipped window is a MISSED SEND. An `UPDATE` turning it into `succeeded`
    erases the fact that a utility's bills did not go out that night, and leaves
    a green tick where the evidence was. The database refuses it — the same
    append-only trigger `US-INT-020` TC-3 proves, now over the new word.
    """
    with live_tenant_context(brazos.id):
        row = _open_the_breaker(_smtp(dana, brazos))
        run = deliver.execute_run(
            connection=row,
            operation=_Operation(),
            adapter=HangingAdapter(),
            work=[{"ref": "A-10432", "address": "a@example.test"}],
            trigger="scheduled",
        )
        assert run.outcome == models.OUTCOME_SKIPPED

        with pytest.raises(DatabaseError) as refused:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE integration_run SET outcome = 'succeeded' WHERE id = %s",
                        [str(run.id)],
                    )
        assert "BR-INT-039" in str(refused.value)
        assert (
            models.IntegrationRun.objects.get(tenant_id=brazos.id, id=run.id).outcome
            == models.OUTCOME_SKIPPED
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-022@f62a7b7f (EP-INT-06 §3 TC-6 + BR-INT-024/041 verbatim)
# generated: 2026-09-05 by the CR-069 wave F build lane
# checklist: A✔ B✔ C✔ D✔(deliver.execute_run is the shipping runner) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_022_isolation_pg.py under config.settings.local + DATABASE_URL
# exceptions: every case SKIPS on SQLite by design (requires_postgres) — DEF-GOV-4024 records the isolation gate passing without pointing the suite at PostgreSQL, so a green gate is not evidence and this file is run by hand
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
