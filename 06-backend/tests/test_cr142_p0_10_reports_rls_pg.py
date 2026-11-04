# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.10`.
#          Verbatim: *"⚠ Postgres only. The unit suite hardcodes in-memory
#          SQLite and ignores DATABASE_URL, and SQLite has no row-level
#          security — a probe there proves nothing and passes."*
#          Outcome: *"Tenant A cannot read tenant B's definitions, categories
#          or overlay rows, PROVED ON POSTGRESQL."*
#          Plus `P0.18`'s own half: `account_attribute_history`.
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id`; RLS FORCE is on) · B2 §3 · hard-won law 7 (192
#          skips once read as a pass; `DEF-2717` — a superuser probe bypasses
#          the policy it is testing)
# Tests:   this file — SKIPPED on SQLite BY DESIGN, and the skip is the point.
# ───────────────────────────────────────────────────────
"""THE REPORTS TABLES, AND `account_attribute_history`, UNDER REAL RLS.

Run it against a real database — the whole line, because a walkthrough header
that omits `JOBS_EAGER=false` costs an hour (`DEF-567`):

    10-scripts/proof-db.sh clone repdb
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_repdb?sslmode=disable"
    pytest tests/test_cr142_p0_10_reports_rls_pg.py

⚠ **A PLATFORM ROW IS `tenant_id IS NULL` AND THAT IS WHY THESE THREE TABLES
NEED THEIR OWN PROBE RATHER THAN THE STANDARD ONE.** `report_definitions` and
`report_categories` hold the 46 platform rows every tenant reads, so the B2 §3
template's plain equality is **not** the whole policy here: it must admit
`tenant_id IS NULL` as well, and a tenant session must see *its own plus the
platform's and nothing else*. The failure mode the standard probe cannot see is
a policy that admits NULL **by accident** — for example through a nullable
comparison a reviewer reads as strict — and then also admits the neighbour's.
So the case below asserts the SET, not merely the absence of a leak.

⚠ **THE READS RUN UNDER A PROBE ROLE RATHER THAN THE APPLICATION'S OWN.**
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
unconditionally, `FORCE` included, and the development role is often a
superuser (`DEF-2717`). `rls.assert_is_a_real_proof()` FAILS — never skips — if
the probe role could bypass anything.

⚠ **`P0.1`–`P0.3` ARE LANE REP-P0A's AND MAY NOT BE ON THE BRANCH YET.** The
models are resolved BY `db_table` at call time, so this file imports cleanly
either way; a missing table FAILS BY NAME against `P0.1`/`P0.2`/`P0.3` rather
than erroring at collection and taking the rest of the suite with it. It is a
red that names its own cause, which is the only honest shape for a dependency
this file cannot satisfy itself.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.apps import apps as django_apps
from django.db import connection

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

#: `P0.1` · `P0.2` · `P0.3` — lane REP-P0A's three, by TABLE name, which is
#: what the brief contracts and what a class name is free to disagree with.
REPORTS_TABLES = ("report_definitions", "report_categories", "report_tenant_settings")
#: `P0.18` — this lane's own, and it carries no platform row: every row names a
#: tenant's account, so the plain B2 §3 template is exactly right for it.
OWN_TABLE = "account_attribute_history"

#: The two that hold PLATFORM rows (`tenant_id IS NULL`). `report_tenant_settings`
#: does not — a tenant overlay with no tenant is a contradiction.
PLATFORM_ROW_TABLES = ("report_definitions", "report_categories")


def _model_for(table: str):
    """The model whose `db_table` is `table`, or None. Never a guessed class name."""
    for model in django_apps.get_models():
        if model._meta.db_table == table:
            return model
    return None


def _require(table: str):
    model = _model_for(table)
    if model is None:
        pytest.fail(
            f"No model declares `db_table = {table!r}`. CR-142 `P0.1`–`P0.3` "
            "(lane REP-P0A) create the three reports tables; this probe is "
            "their RLS half and cannot run before them. This is a DEPENDENCY, "
            "not a policy failure."
        )
    return model


def _table_exists(table: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [table],
        )
        return cursor.fetchone() is not None


@requires_postgres
@pytest.mark.parametrize("table", (*REPORTS_TABLES, OWN_TABLE))
def test_p0_10_every_table_is_enabled_AND_forced(table):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the owner.

    Read out of `pg_class` rather than out of the migration file, because a
    migration that ran, a policy somebody dropped by hand and a policy that was
    never written **all look identical in the source tree**.
    """
    if not _table_exists(table):
        pytest.fail(
            f"`{table}` does not exist on this database. For the three reports "
            "tables that means CR-142 `P0.1`–`P0.3` have not run — a DEPENDENCY "
            "on lane REP-P0A, not a policy failure."
        )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [table],
        )
        row = cursor.fetchone()
    assert row == (True, True), (
        f"CLAUDE.md hard rule 1 / B2 §3: `{table}` needs ENABLE *and* FORCE ROW "
        f"LEVEL SECURITY — pg_class says {row}. Without FORCE the migration role "
        "owns the table and is exempt from its own policy, which makes the "
        "policy decoration."
    )


@requires_postgres
def test_p0_10_no_tenant_context_denies_every_table(rls):
    """With `app.tenant_id` unset, no TENANT row of any named table is visible.

    ⚠ **AMENDED 2026-10-02 (`DEF-REP-7823`) — THIS DOCSTRING CLAIMED THE
    OPPOSITE OF THE SIGNED POLICY.** It read *"NO row is visible — including,
    crucially, the PLATFORM rows"*, and `reports/0002` says, in its own words,
    *"with an unset GUC the platform rows are still readable"* — the shipped
    catalogue is the same on every deployment and is not what RLS protects
    here. The `NULLIF` form also DENIES rather than errors. So the probe now
    asks the hard-rule-1 question of the two platform tables — zero rows that
    belong to any tenant — and the plain zero-rows question of the overlay and
    of `account_attribute_history`, which carry no platform row.
    """
    rls.assert_is_a_real_proof()
    present = [t for t in (*REPORTS_TABLES, OWN_TABLE) if _table_exists(t)]
    # Law 7's fifth shape: print what was skipped beside what was checked.
    missing = [t for t in (*REPORTS_TABLES, OWN_TABLE) if t not in present]
    assert missing == [], (
        f"checked {present}; SKIPPED {missing} because they do not exist yet "
        "(CR-142 `P0.1`–`P0.3`, lane REP-P0A). A blind spot with no number "
        "beside it is indistinguishable from an empty one."
    )
    assert_denied_without_context(rls, *present)


def _seed_definition(model, tenant, key: str):
    """One row of `report_definitions`, written through the ORM under its tenant.

    Only the columns the brief contracts are set; anything else the sibling
    lane's model declares takes its own default. A column this does not know
    about is the sibling's to default, and a test that spelled out their whole
    column list would break every time they added one.
    """
    return model.objects.create(tenant_id=tenant.pk, key=key, name=key.replace("_", " ").title())


@requires_postgres
def test_p0_10_one_tenants_definitions_are_invisible_to_another(rls, brazos, lonestar):
    """`P0.10`'s own sentence: tenant A cannot read tenant B's definitions."""
    rls.assert_is_a_real_proof()
    model = _require("report_definitions")
    with tenant_ctx(brazos):
        mine = _seed_definition(model, brazos, "brazos_only_report")
    with tenant_ctx(lonestar):
        _seed_definition(model, lonestar, "lonestar_only_report")
    assert_rls_scoped(
        rls,
        "report_definitions",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(mine.pk)},
    )


@requires_postgres
@pytest.mark.parametrize("table", PLATFORM_ROW_TABLES)
def test_p0_10_a_tenant_sees_its_own_plus_the_platforms_and_nothing_else(rls, brazos, lonestar, table):
    """THE case the standard probe cannot make, and the one this design needs.

    `tenant_id IS NULL` is a PLATFORM row — the 46 definitions and the 6 groups
    with 19 sub-groups every utility reads. So the correct visible set under
    Brazos Bend is **Brazos Bend's rows plus the NULLs**, and a policy that got
    either half wrong fails here rather than in a support call: too strict and
    the catalogue is empty for everybody, too loose and Lone Star Ridge's rows
    come with it.
    """
    rls.assert_is_a_real_proof()
    _require(table)
    from tests.isolation_helpers import live_tenant_context

    with live_tenant_context(brazos.id):
        seen = rls.tenant_ids(table)
    foreign = {t for t in seen if t not in {str(brazos.id), None, "None"}}
    assert foreign == set(), (
        f"{table}: under Brazos Bend's context the database exposed rows of "
        f"{foreign}. A platform row is `tenant_id IS NULL` and nothing else — "
        "a policy admitting a NULL must not also admit a neighbour's uuid."
    )


@requires_postgres
@pytest.mark.parametrize("table", REPORTS_TABLES)
def test_p0_10_a_row_stamped_for_another_tenant_is_refused(rls, brazos, lonestar, table):
    """The policy's `WITH CHECK`. `USING` finds the row; `WITH CHECK` rejects it."""
    rls.assert_is_a_real_proof()
    model = _require(table)
    # ⚠ **SEED THE OWNER'S ROW FIRST (`DEF-REP-7823`, 2026-10-02).** This case
    # used to seed nothing, so Brazos Bend owned no row in any of the three
    # tables and `assert_write_into_other_tenant_refused` stopped — correctly —
    # on *"the owning tenant has no rows … a VACUOUS FIXTURE, not a leak"*. All
    # three `WITH CHECK` clauses had therefore never been exercised. A platform
    # row cannot stand in: it is `tenant_id IS NULL` and the UPDATE below
    # re-stamps rows WHERE tenant_id = the owner.
    with tenant_ctx(brazos):
        if table == "report_definitions":
            _seed_definition(model, brazos, "brazos_write_probe")
        elif table == "report_categories":
            model.objects.create(tenant_id=brazos.pk, code="brazos_probe", name="Brazos probe")
        else:  # report_tenant_settings — an overlay on a SHIPPED definition
            shipped = _model_for("report_definitions").objects.filter(tenant__isnull=True).first()
            assert shipped is not None, "no shipped definition to overlay — reports/0003 did not seed"
            model.objects.create(tenant_id=brazos.pk, definition=shipped)
    assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)


@requires_postgres
def test_p0_18_one_tenants_attribute_history_is_invisible_to_another(rls, brazos, lonestar, dana, erin):
    """`P0.18`'s 🔒 half — `customers/0073`, proved rather than asserted.

    This table is not in `P0.10`'s sentence and is tested here anyway, because
    it ships in the same phase, under the same rule, and a 🔒 RLS migration
    whose only evidence is its own docstring is hard-won law 1.
    """
    rls.assert_is_a_real_proof()
    from apps.customers import attribute_history
    from apps.customers import models as customer_models

    def seed(tenant, actor, service):
        premises = make_premises(actor, address_line="1 Probe Way", services_available=[service])
        unit = make_unit(actor, premises["id"], label="Unit A", services=[service])
        account = customer_models.Account.objects.create(
            tenant=tenant,
            unit_id=unit["id"],
            status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
            account_type=customer_models.AccountType.objects.filter(tenant=tenant).first(),
            account_no=f"A-{tenant.pk.hex[:8]}",
        )
        return attribute_history.record(account, on=date(2026, 7, 1))

    with tenant_ctx(brazos):
        mine = seed(brazos, dana, "electric")
    with tenant_ctx(lonestar):
        # Lone Star Ridge is WATER-ONLY — an electric unit there is refused by
        # metering with VAL-005, correctly.
        seed(lonestar, erin, "water")

    assert_rls_scoped(
        rls, OWN_TABLE, owner=brazos, intruder=lonestar, owner_ids={str(mine.pk)}
    )
    assert_write_into_other_tenant_refused(rls, OWN_TABLE, owner=brazos, intruder=lonestar)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P0.10 (+ P0.18's RLS half) — 05-prototype/09 Reports Build Brief.pdf p8-9
# screens: none
# generated: 2026-09-26 by lane REP-P0B
# checklist: A✔ B=n/a C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for what was and was NOT run on PostgreSQL.
# exceptions: (1) the three reports tables are lane REP-P0A's and are resolved BY db_table at call time, so this file imports cleanly before they exist and FAILS BY NAME rather than erroring at collection · (2) `requires_postgres` SKIPS on SQLite and the skip is loud on purpose — a probe there would pass by vacuum, which is the exact failure hard-won law 7 records as "192 skips read as a pass"
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING (RLS is a 🔒 path)
# ──────────────────────────────────────────────────────────
