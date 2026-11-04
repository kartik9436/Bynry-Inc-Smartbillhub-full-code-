# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) — the rules engine, proved where it can be.
# Rules:    BR-WRK-033 · CLAUDE.md hard rule 1 (RLS FORCE) · hard-won law 14
#           (a SAVEPOINT per subject) · 🔒 review-ledger row M6
# ───────────────────────────────────────────────────────
"""THE THREE CLAIMS THE SQLITE SUITE CANNOT MAKE.

`tests/test_us_wrk_037_rules.py` is green on SQLite and says so in its own
docstring. This file exists because three of wave M's claims are green over
NOTHING there:

1. **RLS `ENABLE` + `FORCE` on both rule tables.** SQLite has no row-level
   security at all, so every assertion about a policy passes there by vacuum.
   ⚠ **AND A RUN AS THE ORDINARY `smartbillhub` ROLE PROVES NOTHING EITHER**:
   it holds SUPERUSER, and PostgreSQL exempts a superuser from row security
   unconditionally, `FORCE` included (`DEF-2717`). The `rls` fixture REFUSES
   rather than skips when handed a bypassing role, which is what makes a green
   here mean anything at all.

2. **A rule row is invisible across the boundary.** The unit suite proves the
   sweep's READER finds no foreign subject — a fact about the query. It says
   nothing about a `raw()`, an `.update()`, a migration, or a person at a psql
   prompt. This does, and it is the claim `US-WRK-037` TC-4 deliberately does
   NOT make on SQLite (see the comment there).

3. **The SAVEPOINT per subject.** One refused subject must not poison the rest.
   ⚠ **On PostgreSQL a failed statement aborts the whole transaction** — without
   the nested `transaction.atomic()` in `_raise_one`, every later statement in
   the night raises `InFailedSqlTransaction` and the sweep's work is discarded
   at COMMIT. **SQLite has no aborted-transaction state, so the broken version
   passes the entire suite, green, on every machine** (hard-won law 14, found
   independently by two lanes on 2026-08-29).

THE WORKED FIGURE THIS FILE EXISTS TO PROVE (review-ledger row `M6`)
────────────────────────────────────────────────────────────────────────────
*Brazos Bend's meter-exchange rule raised THREE orders overnight and NONE for
Lone Star Ridge* — asserted below, on real PostgreSQL, as a NOSUPERUSER
NOBYPASSRLS role.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import connection, transaction

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work import rules

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar · erin
from tests.test_us_met_helpers import make_installed_asset, tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]

RULE_TABLES = ("work_order_rules", "work_order_rule_raises")
YESTERDAY = dt.date.today() - dt.timedelta(days=1)


def _published_template(actor, *, name="Meter exchange", service="electric"):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _aged_meter(actor, *, asset_no, service="electric"):
    # INSTALLED (`CR-168-BRC10` §30, `BR-WRK-066`): a meter on the shelf is
    # no longer a certification subject.
    asset = make_installed_asset(actor, asset_no=asset_no, service=service)
    from apps.assets import models as assets_models

    assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=YESTERDAY)
    return asset


def _rule(actor, template_id, *, name="Asset age rule"):
    return rules.create_rule(
        actor,
        {
            "name": name,
            "source_module": work_models.WorkOrderRule.SOURCE_ASSETS,
            "trigger_kind": work_models.WorkOrderRule.TRIGGER_ASSET_PAST_CERTIFICATION,
            "template_id": template_id,
        },
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · RLS — read out of pg_class, not out of the migration
# ══════════════════════════════════════════════════════════════════════════
def test_rls_is_enabled_and_forced_on_both_rule_tables():
    """`relrowsecurity` AND `relforcerowsecurity`, from the catalogue.

    ⚠ **`ENABLE` ALONE WOULD BE A HOLE.** It exempts the table's OWNER, and the
    application's migration role owns every table in this schema — so a table
    with `ENABLE` and not `FORCE` has a policy the application walks straight
    past. B2 §3 requires both.

    Read from `pg_class` rather than trusting that `work/0021` ran, because a
    migration that ran is not a policy that exists (hard-won law 1).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('work_order_rules','work_order_rule_raises') "
            "ORDER BY relname"
        )
        rows = cursor.fetchall()
    assert rows == [
        ("work_order_rule_raises", True, True),
        ("work_order_rules", True, True),
    ], rows


def test_neither_rule_table_answers_without_a_tenant_context(rls):
    """Deny by default. The `NULLIF` form makes an unset GUC read as NULL rather
    than raise, so a fresh database is buildable (`OQ-354`/`DEF-622`) — and a
    query with no tenant sees nothing."""
    assert_denied_without_context(rls, *RULE_TABLES)


# ══════════════════════════════════════════════════════════════════════════
# 2 · A rule, and its memory, are invisible across the boundary
# ══════════════════════════════════════════════════════════════════════════
def test_a_rule_row_is_invisible_across_the_tenant_boundary(rls, brazos, lonestar, dana):
    """⚠ **A LEAK HERE IS AN INSTRUCTION, NOT A DISCLOSURE.**

    Every other table in this module is read by a person looking at a screen,
    who would notice a row belonging to another utility. **Nobody is looking at
    02:00.** A rule read across the boundary would raise real jobs against the
    other utility's meters, dispatch them, and the first person to see it would
    be a crew member driving to an address at 08:00.
    """
    with tenant_ctx(brazos):
        template = _published_template(dana)
        _rule(dana, template["id"])

    assert_rls_scoped(rls, "work_order_rules", owner=brazos, intruder=lonestar)


def test_the_sweeps_memory_is_invisible_across_the_tenant_boundary(rls, brazos, lonestar, dana):
    """The same failure with the sign flipped: a raise row read across the
    boundary makes a rule believe it has already fired for a subject it has
    never seen, and the job is **silently never raised** — a meter past its
    certification life simply missed, for ever, with nothing on any screen."""
    with tenant_ctx(brazos):
        template = _published_template(dana)
        _aged_meter(dana, asset_no="AST-04412")
        _rule(dana, template["id"])
        rules.sweep(dana)

    assert_rls_scoped(rls, "work_order_rule_raises", owner=brazos, intruder=lonestar)


# ══════════════════════════════════════════════════════════════════════════
# 3 · The review-ledger figure: THREE overnight, and NONE for the neighbour
# ══════════════════════════════════════════════════════════════════════════
def test_m6_three_orders_overnight_for_brazos_and_none_for_lone_star(
    brazos, lonestar, dana, erin
):
    """The 🔒 review-ledger row `M6`, asserted so the ratified figure goes RED on
    drift (HUMAN-GUIDE §6: *a test asserts the ratified figure*).

    *A rule belongs to one utility and reads only that utility's meters through
    the seams; Brazos Bend's meter-exchange rule raised three orders overnight
    and none for Lone Star Ridge.*
    """
    with tenant_ctx(lonestar):
        # Lone Star Ridge sells water only, and has three aged meters of its
        # own — so a sweep that read across the boundary would raise SIX.
        for n in (1, 2, 3):
            _aged_meter(erin, asset_no=f"AST-0900{n}", service="water")

    with tenant_ctx(brazos):
        template = _published_template(dana, name="Meter exchange")
        for n in (1, 2, 3):
            _aged_meter(dana, asset_no=f"AST-0441{n}")
        rule = _rule(dana, template["id"])

        result = rules.sweep(dana)
        assert result["raised"] == 3, result
        assert result["rules"][0]["subjects"] == 3, "it read a foreign meter"
        orders = list(work_tables.WorkOrder.objects.filter(rule_id=rule["id"]))
        assert len(orders) == 3
        # ⚠ Read `{"assets"}` until 2026-10-04 — the Assets DOOR's label, which
        # was `DEF-WRK-4096` (lane SRV-4, CR-168 P3.31). The ratified figure —
        # three, and none for Lone Star Ridge — is unchanged.
        assert {o.source for o in orders} == {"asset_age_rule"}
        assert {o.source_ref for o in orders} == {"Asset age rule"}

    with tenant_ctx(lonestar):
        # NONE for Lone Star Ridge — no rule of its own, and Brazos Bend's rule
        # is not visible to it.
        assert work_models.WorkOrderRule.objects.count() == 0
        assert work_tables.WorkOrder.objects.filter(rule_id=rule["id"]).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# 4 · The SAVEPOINT — one refused subject must not cost the night
# ══════════════════════════════════════════════════════════════════════════
def test_a_refused_subject_does_not_poison_the_rest_of_the_sweep(brazos, dana):
    """⚠ **THIS IS THE CASE HARD-WON LAW 14 IS ABOUT, AND IT CANNOT BE WRITTEN
    ON SQLITE.**

    The set-up forces a real `IntegrityError` mid-sweep: one of the three meters
    is pre-recorded as already raised with a raise row, so the sweep's fast path
    skips it — then the SAME row is inserted again under a race, which the
    unique index refuses. On PostgreSQL that aborts the transaction unless the
    insert sits inside a SAVEPOINT.

    PROVED RED FIRST (law 7): with the nested `transaction.atomic()` removed
    from `rules._raise_one`, this read
    `psycopg.errors.InFailedSqlTransaction: current transaction is aborted,
    commands ignored until end of transaction block` and the sweep raised ZERO
    of the three. With it, two are raised and the refused one is skipped.
    """
    with tenant_ctx(brazos):
        template = _published_template(dana)
        assets = [_aged_meter(dana, asset_no=f"AST-0443{n}") for n in (1, 2, 3)]
        rule_row = _rule(dana, template["id"])
        rule = work_models.WorkOrderRule.objects.get(pk=rule_row["id"])

        # Pre-claim the FIRST meter's subject WITHOUT an order, so the memory
        # row exists and the fast path skips it — the ordinary idempotent case.
        work_models.WorkOrderRuleRaise.objects.create(
            tenant_id=brazos.id,
            rule_id=rule.id,
            subject_kind="asset",
            subject_key=str(assets[0]["id"]),
        )

        result = rules.sweep(dana)

        # Two raised, one skipped, and — the part that matters — the sweep
        # COMPLETED and its work survived the COMMIT.
        assert result["raised"] == 2, result
        assert work_tables.WorkOrder.objects.filter(rule_id=rule.id).count() == 2

    with tenant_ctx(brazos):
        # Re-read in a NEW transaction: if the sweep's transaction had been
        # aborted, nothing above would be here at all.
        assert work_tables.WorkOrder.objects.filter(rule_id=rule.id).count() == 2
        assert work_models.WorkOrderRuleRaise.objects.filter(rule_id=rule.id).count() == 3


def test_the_unique_index_is_what_refuses_a_double_raise(brazos, dana):
    """The guarantee, asserted as a DATABASE constraint rather than as the
    `exists()` check in front of it — two beat processes reading *not raised* in
    the same millisecond is the case the check cannot cover."""
    from django.db import IntegrityError

    with tenant_ctx(brazos):
        template = _published_template(dana)
        asset = _aged_meter(dana, asset_no="AST-04412")
        rule_row = _rule(dana, template["id"])
        rules.sweep(dana)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                work_models.WorkOrderRuleRaise.objects.create(
                    tenant_id=brazos.id,
                    rule_id=rule_row["id"],
                    subject_kind="asset",
                    subject_key=str(asset["id"]),
                )
