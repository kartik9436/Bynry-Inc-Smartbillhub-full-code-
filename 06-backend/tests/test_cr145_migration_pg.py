# ── Trace ──────────────────────────────────────────────
# Change:  CR-145-BRC08 — tasks T4 (the data migration) and T7 (one utility's
#          settings never affect another's, PROVED ON POSTGRESQL).
# Rules:   BR-IDN-026 (CONFIRMED-AS-AMENDED — 240 and 480 are withdrawn) ·
#          CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id`; RLS FORCE is on) · hard-won law 14 (the unit suite
#          hardcodes in-memory SQLite and ignores DATABASE_URL) · law 7
#          (a probe over a row that was never written prints the same PASS)
# Tests:   this file — SKIPPED on SQLite BY DESIGN, and the skip is the point.
# ───────────────────────────────────────────────────────
"""THE MIGRATION AND THE ISOLATION, ON A REAL DATABASE.

Run it against real PostgreSQL — the whole line, because a header that omits
`JOBS_EAGER=false` costs an hour (`DEF-567`):

    10-scripts/proof-db.sh clone cr145
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_cr145?sslmode=disable"
    pytest tests/test_cr145_migration_pg.py

⚠ **WHY NOT IN THE ORDINARY TIER, FOR BOTH HALVES SEPARATELY.**

**T4, the migration.** `identity/0007` moves every utility off a withdrawn
inactivity timeout and writes an audit row for each. `audit_log` is monthly
RANGE-partitioned and its policy carries a `WITH CHECK` — neither exists on
SQLite, so a migration that wrote no row at all, or wrote one into the wrong
tenant, would pass on SQLite in silence. Hard-won law 14 one door along.

**T7, the isolation.** SQLite has no row-level security, so a probe there is
not a weak proof, it is *no proof of the thing that matters*.

⚠ **AND THE PROBE RUNS AS A ROLE RLS ACTUALLY APPLIES TO.** PostgreSQL exempts
SUPERUSER and BYPASSRLS roles unconditionally, `FORCE` included, and the
development role is often a superuser (`DEF-2717`). The `rls` fixture reads
`rolsuper` and `rolbypassrls` out of `pg_roles` and FAILS — never skips — if
the probe could bypass anything.

⚠ **AND THE NEIGHBOUR'S ROW IS PLANTED AND PROVED VISIBLE FROM ITS OWN SEAT
FIRST.** A probe reporting *cannot see it* over a row that was never written
prints exactly the same PASS as a probe reporting a policy that works, and
that has already cost this repo an hour on `work_order_details`.
`assert_rls_scoped`'s `min_owner_rows` is that check, passed explicitly here
rather than left to its default, and the seats are then SWAPPED so the pair is
proved in both directions rather than in one lucky one.

⚠ **`sessions` IS NOT THE SUBJECT AND THAT IS NOT AN OVERSIGHT.** B2 §3
declares `sessions` RLS-EXEMPT on purpose — `/api/jobs/{id}` carries no
utility segment and has to read the session row to find out which utility to
open. `T7` asks whether one utility's SETTINGS can affect another's, and the
settings live in `security_policies`, which is neither exempt nor allowed to
be.
"""

from __future__ import annotations

from importlib import import_module

import pytest
from django.apps import apps as live_apps
from django.db import connection

from apps.identity import services
from apps.identity.models import SecurityPolicy
from apps.tenancy.models import Tenant
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import idn  # noqa: F401 (fixture import)

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLE = "security_policies"

#: The migration module, by path — `0007_…` is not a Python identifier, so it
#: cannot be reached with an `import … as` statement.
MIGRATION = "apps.identity.migrations.0007_cr145_withdraw_long_timeouts"


class _SchemaEditorStub:
    """What `RunPython` hands a migration: something with a `.connection`.

    The migration reads `connection.vendor` to decide whether to set the real
    PostgreSQL GUC or the Python mirror alone (hard-won law 14), so the stub
    hands it the real one.
    """

    connection = connection


def _run_migration(capsys) -> str:
    """Call the migrations' OWN functions against the live app registry.

    ⚠ **BOTH OF THEM, IN ORDER — AMENDED 2026-10-02 (`DEF-IDN-9137`).** This
    ran `0007` alone, and `0007` reads `security_policies` with no tenant
    context. That moves every row as a SUPERUSER and NONE as a role row-level
    security applies to — which is what production runs `migrate` as, and what
    the isolation proof now runs as too (`sbh_gate_iso`, NOSUPERUSER
    NOBYPASSRLS). So the first three T4 cases went red on the first proof
    taken as a correct role (2026-09-29) for a reason that is the TEST's: the
    product's withdrawal is `0007` + `0008`, and `0008` walks each utility
    under its own context. Running the shipped sequence makes these cases true
    on BOTH kinds of role, and the printed figure is the SUM, exactly as
    `WITHDRAWAL_MIGRATIONS` below already says the PO's count is.

    ⚠ **THE SHIPPING FUNCTION IS CALLED, NOT A COPY OF ITS LOGIC.** A test
    that re-implements *"update 240 and 480 to 60"* proves its own author can
    write that query and says nothing about the file that will run on the
    deployment. `apps.get_model` resolves against whatever registry it is
    handed, so the live one works.

    Returns whatever the migration PRINTED, because the printed count is the
    figure the PO is given and an unasserted figure is an assumption.
    """
    for name in WITHDRAWAL_MIGRATIONS:
        import_module(name).withdraw_long_timeouts(live_apps, _SchemaEditorStub())
    return capsys.readouterr().out


def _moved(printed: str) -> int:
    """The PO's figure: the sum of what each withdrawal migration printed."""
    import re

    return sum(int(n) for n in re.findall(r"CR-145[^:]*: (\d+) utility\(ies\) moved", printed))


def _reload(policy) -> None:
    """Re-read a row INSIDE its own utility's context.

    With no `app.tenant_id` a role RLS applies to sees nothing — deny-by-default,
    hard rule 1 — so a bare `refresh_from_db()` raised `DoesNotExist` on a row
    that is there. A superuser hid that by bypassing the policy.
    """
    with live_tenant_context(policy.tenant_id):
        policy.refresh_from_db()


# ═══════════════════════════════════════════════════════════════════════════
# T4 · the migration
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_t4_240_and_480_become_60_and_30_and_60_are_untouched(idn, capsys):
    """The ruling, as four utilities.

    ⚠ **30 AND 60 ARE IN THE FIXTURE ON PURPOSE.** The whole risk in this
    migration is a filter one `OR` away from matching everything, and a
    fixture holding only the two withdrawn values could not tell a correct
    migration from one that sets every utility in the product to 60.
    """
    quiet = Tenant.objects.create(name="Quiet Creek", subdomain="quietcreek")
    still = Tenant.objects.create(name="Still Water", subdomain="stillwater")

    with live_tenant_context(idn.silvercreek.id):
        on_240 = SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=240)
    with live_tenant_context(idn.bluemesa.id):
        on_480 = SecurityPolicy.objects.create(tenant=idn.bluemesa, session_timeout_minutes=480)
    with live_tenant_context(quiet.id):
        on_30 = SecurityPolicy.objects.create(tenant=quiet, session_timeout_minutes=30)
    with live_tenant_context(still.id):
        on_60 = SecurityPolicy.objects.create(tenant=still, session_timeout_minutes=60)

    printed = _run_migration(capsys)

    for policy in (on_240, on_480, on_30, on_60):
        _reload(policy)

    assert on_240.session_timeout_minutes == 60
    assert on_480.session_timeout_minutes == 60
    assert on_30.session_timeout_minutes == 30, "a utility on a STILL-VALID choice was moved"
    assert on_60.session_timeout_minutes == 60

    # ⚠ **THE PRINTED COUNT IS THE FIGURE THE PO IS GIVEN, so it is asserted.**
    assert _moved(printed) == 2, printed


@requires_postgres
def test_t4_one_audit_row_per_utility_moved(idn, capsys):
    """*"one audit row per utility moved"*, with before AND after on it."""
    with live_tenant_context(idn.silvercreek.id):
        SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=240)
    with live_tenant_context(idn.bluemesa.id):
        SecurityPolicy.objects.create(tenant=idn.bluemesa, session_timeout_minutes=480)

    _run_migration(capsys)

    rows = idn.rows_for("settings.security_updated")
    assert len(rows) == 2, [row["action"] for row in idn.rows]

    by_tenant = {str(row["tenant_id"]): row for row in rows}
    assert set(by_tenant) == {str(idn.silvercreek.id), str(idn.bluemesa.id)}

    silver = by_tenant[str(idn.silvercreek.id)]
    assert silver["before"] == {"session_timeout_minutes": 240}
    assert silver["after"] == {"session_timeout_minutes": 60}
    # No person did this — BR-AUD-003's UNNAMED SYSTEM JOB, which is exactly
    # what a migration is and how every reader already tells it from a clerk.
    assert silver["actor_user_id"] is None

    mesa = by_tenant[str(idn.bluemesa.id)]
    assert mesa["before"] == {"session_timeout_minutes": 480}


@requires_postgres
def test_t4_a_utility_on_a_valid_value_gets_no_audit_row(idn, capsys):
    """The mirror, and it is the one that catches a filter matching everything:
    an audit row for a utility nothing happened to is a trail entry a clerk
    cannot explain."""
    with live_tenant_context(idn.silvercreek.id):
        SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=60)

    printed = _run_migration(capsys)

    assert idn.rows_for("settings.security_updated") == []
    assert _moved(printed) == 0 and "0 utility(ies) moved" in printed, printed


@requires_postgres
def test_t4_every_other_setting_keeps_todays_value_across_the_migration(idn, capsys):
    """Ruling 3's first half: *"every utility keeps today's values."*"""
    with live_tenant_context(idn.silvercreek.id):
        policy = SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=240)

    _run_migration(capsys)
    _reload(policy)

    assert policy.absolute_session_hours == 12
    assert policy.keep_signed_in_offered is True
    assert policy.keep_signed_in_days == 30
    assert policy.lockout_max_failed == 5
    assert policy.lockout_minutes == 15
    assert policy.pw_min_length == 8


#: Every migration that withdraws 240/480, in order. `0007` alone was the
#: whole list until 2026-09-28 evening (DEF-IDN-7504); the PO's count is the
#: SUM of what each one prints, and each only ever finds rows the previous one
#: left behind, so nothing is counted twice.
WITHDRAWAL_MIGRATIONS = (
    MIGRATION,
    "apps.identity.migrations.0008_cr145_withdraw_long_timeouts_per_tenant",
)

NIL_TENANT = "00000000-0000-0000-0000-000000000000"


@requires_postgres
def test_t4_the_withdrawal_moves_rows_as_a_role_rls_APPLIES_to(idn, rls, capsys):
    """⚠ **THE CASES ABOVE RUN THE MIGRATION AS A SUPERUSER, AND A SUPERUSER
    SEES EVERY UTILITY'S ROW WITHOUT A TENANT CONTEXT.** Production does not.
    `09-infra/01-deployment-architecture.md` §Step 0: the role that runs
    `migrate` owns the tables, is NOT a superuser and holds no BYPASSRLS
    (the PO ruled the grant out), `FORCE` binds the owner, and the database
    default for `app.tenant_id` is the nil UUID — which matches no row.

    So `SecurityPolicy.objects.filter(session_timeout_minutes__in=…)` with no
    tenant set returns NOTHING there, `0007` prints *"0 utility(ies) moved"*,
    and every utility on 240 or 480 stays on it — unable to save its Security
    tab, because the validator now refuses the value it holds. **And the 0 is
    the figure the PO would have been given.** The four cases above could not
    see it: hard-won law 7's *incapable of failing*, because the superuser
    that runs them is the one role for which the bug does not exist.

    This case runs the whole withdrawal as the non-superuser probe role, with
    the production default in the GUC, over a real row.
    """
    with live_tenant_context(idn.silvercreek.id):
        on_480 = SecurityPolicy.objects.create(tenant=idn.silvercreek, session_timeout_minutes=480)
    with live_tenant_context(idn.bluemesa.id):
        on_30 = SecurityPolicy.objects.create(tenant=idn.bluemesa, session_timeout_minutes=30)

    printed = []
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NIL_TENANT])
        cursor.execute(f'SET ROLE "{rls.role}"')
        cursor.execute("SELECT current_user, (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)")
        who, is_super = cursor.fetchone()
    assert who == rls.role and not is_super, (who, is_super)
    try:
        for name in WITHDRAWAL_MIGRATIONS:
            # A missing module is recorded rather than raised, so the RED this
            # case was proved with is the row left on 480 and the count of 0 —
            # the product's failure — rather than an ImportError. If `0008` is
            # ever deleted, the value assertions below still fail on the row.
            try:
                module = import_module(name)
            except ModuleNotFoundError:
                printed.append(f"(missing: {name})")
                continue
            module.withdraw_long_timeouts(live_apps, _SchemaEditorStub())
            printed.append(capsys.readouterr().out)
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")

    _reload(on_480)
    _reload(on_30)
    assert on_480.session_timeout_minutes == 60, (
        "the utility on 480 was NOT moved by a role RLS applies to: " + " | ".join(printed)
    )
    assert on_30.session_timeout_minutes == 30

    # The PO's figure is the sum of the printed counts, and it must be 1.
    import re

    counts = [
        int(match)
        for out in printed
        for match in re.findall(r"CR-145[^:]*: (\d+) utility\(ies\) moved", out)
    ]
    assert sum(counts) == 1, printed

    # …and the move left its trail, in the right utility, as the system.
    rows = idn.rows_for("settings.security_updated")
    assert [str(row["tenant_id"]) for row in rows] == [str(idn.silvercreek.id)], rows
    assert rows[0]["before"] == {"session_timeout_minutes": 480}


@requires_postgres
def test_t4_the_withdrawn_values_are_gone_from_the_choices(idn):
    """The migration and the validator must agree, or a utility is moved off a
    value the Security tab would happily put it straight back on."""
    assert services.SETTING_LIMITS["session_timeout_minutes"]["choices"] == (15, 30, 45, 60)
    assert 240 not in services.SESSION_TIMEOUT_OPTIONS
    assert 480 not in services.SESSION_TIMEOUT_OPTIONS


# ═══════════════════════════════════════════════════════════════════════════
# T7 · one utility's settings never affect another's
# ═══════════════════════════════════════════════════════════════════════════
@requires_postgres
def test_t7_security_policies_is_enabled_AND_forced(idn):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the OWNER.

    Read out of `pg_class` rather than out of the migration file, because a
    migration that ran, a policy somebody dropped by hand, and a policy that
    was never written all look identical in the source tree.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        row = cursor.fetchone()

    assert row is not None, f"{TABLE} does not exist"
    enabled, forced = row
    assert enabled, f"{TABLE}: row-level security is not ENABLED"
    assert forced, f"{TABLE}: FORCE is off, so the table owner bypasses the policy"


@requires_postgres
def test_t7_with_no_tenant_context_the_table_answers_nothing(idn, rls):
    """Cleared context must deny EVERYTHING, never expose everything."""
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_t7_one_utilitys_settings_are_invisible_to_another(idn, rls):
    """Both rows planted; each proved visible from its OWN seat before either
    absence is believed. See the module docstring for why that order matters.
    """
    with live_tenant_context(idn.silvercreek.id):
        silver = SecurityPolicy.objects.create(
            tenant=idn.silvercreek,
            session_timeout_minutes=15,
            lockout_max_failed=3,
            lockout_minutes=5,
        )
    with live_tenant_context(idn.bluemesa.id):
        mesa = SecurityPolicy.objects.create(
            tenant=idn.bluemesa,
            session_timeout_minutes=60,
            lockout_max_failed=10,
            lockout_minutes=60,
        )

    assert_rls_scoped(
        rls,
        TABLE,
        owner=idn.silvercreek,
        intruder=idn.bluemesa,
        owner_ids={str(silver.id)},
        min_owner_rows=1,
    )
    assert_rls_scoped(
        rls,
        TABLE,
        owner=idn.bluemesa,
        intruder=idn.silvercreek,
        owner_ids={str(mesa.id)},
        min_owner_rows=1,
    )


@requires_postgres
def test_t7_the_engines_read_answers_each_utility_its_own_numbers(idn):
    """The DATABASE half is above; this is the half a person would notice.

    `selectors.security_policy_values` is what `sign_in`, `authenticate` and
    the portal's seam all resolve their numbers through, so if the two
    utilities' settings were ever going to bleed into one another this is the
    function it would happen in.
    """
    with live_tenant_context(idn.silvercreek.id):
        SecurityPolicy.objects.create(
            tenant=idn.silvercreek,
            session_timeout_minutes=15,
            absolute_session_hours=4,
            keep_signed_in_offered=False,
            keep_signed_in_days=1,
            lockout_max_failed=3,
            lockout_minutes=5,
        )
    with live_tenant_context(idn.bluemesa.id):
        SecurityPolicy.objects.create(
            tenant=idn.bluemesa,
            session_timeout_minutes=60,
            absolute_session_hours=12,
            keep_signed_in_offered=True,
            keep_signed_in_days=30,
            lockout_max_failed=10,
            lockout_minutes=60,
        )

    from apps.identity import selectors

    with live_tenant_context(idn.silvercreek.id):
        silver = selectors.security_policy_values(idn.silvercreek.id)
    with live_tenant_context(idn.bluemesa.id):
        mesa = selectors.security_policy_values(idn.bluemesa.id)

    assert silver["lockout_max_failed"] == 3
    assert silver["keep_signed_in_offered"] is False
    assert silver["absolute_session_hours"] == 4
    assert mesa["lockout_max_failed"] == 10
    assert mesa["keep_signed_in_offered"] is True
    assert mesa["absolute_session_hours"] == 12
