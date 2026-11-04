# ── Trace ──────────────────────────────────────────────
# Change:  CR-165-BRC10 round 2 task 3 — the PostgreSQL half.
# Defects: DEF-RAT-9281 (nothing stops two rows of one tax overlapping) ·
#          DEF-RAT-9280 / 9282 / 9283 (one row per tax per date, on a real
#          server) · DEF-RAT-9276 (one code names one chain)
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE) · hard-won law 14 (anything that
#          meets a database refusal is proved on PostgreSQL, inside a
#          SAVEPOINT) · law 7 (each lock proved red)
# ───────────────────────────────────────────────────────
"""The database locks on the tax chain, and the billing lookup on a real server.

    cd 06-backend
    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> JOBS_EAGER=false \\
        pytest tests/test_cr165_tax_versions_pg.py --ds=config.settings.pgtest

Every case carries `requires_postgres` and SKIPS by name elsewhere — the
exclusion constraints, the trigger and RLS do not exist on SQLite, and a green
run there would prove nothing (law 7, *incapable of failing*).

⚠ `ex_taxes_chain_no_overlap` is DEFERRABLE INITIALLY DEFERRED (a correction
inserts its row before it can supersede the old one), and pytest's transaction
never commits — so each case that asserts it says `SET CONSTRAINTS … IMMEDIATE`,
which runs the deferred check now. Without that line the overlap case would
pass whether or not the constraint existed.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from apps.rating import models as rating_models
from apps.rating import services

from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_cr165_tax_versions import (
    NOV_01,
    NOV_15,
    OCT_15,
    OCT_31,
    a_state_sales_tax,
    authority,
    bind,
    charged,
    rules_on,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


def check_deferred_now() -> None:
    """Run the deferred overlap check NOW, then put it back to deferred — a
    constraint switched to IMMEDIATE stays so for the rest of the transaction,
    and the next correction (whose two rows overlap for a few statements by
    design) would then be refused mid-write."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ex_taxes_chain_no_overlap IMMEDIATE")
        cursor.execute("SET CONSTRAINTS ex_taxes_chain_no_overlap DEFERRED")


def test_9281_two_live_rows_of_one_tax_overlapping_are_refused(brazos):
    """v1 6.25% open-ended + v2 6.5% from 11/01/2026, both live: refused.
    RED before the fix (branch tip `2a842fafc`): stored without a word."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 PG overlap", services=("water",))
        v1, state = a_state_sales_tax(brazos, plan)
        with pytest.raises(IntegrityError) as refused:
            with transaction.atomic():  # law 14 — the SAVEPOINT is the only option
                rating_models.Tax.objects.create(
                    tenant=brazos, jurisdiction=state, name="State sales tax", kind="percent",
                    rate=Decimal("0.065000"), effective_from=NOV_01, chain_id=v1.chain_id,
                    version_no=2,
                )
                check_deferred_now()
        assert "ex_taxes_chain_no_overlap" in str(refused.value)
        # The connection is still usable after the refusal (law 14).
        assert rating_models.Tax.objects.filter(chain_id=v1.chain_id).count() == 1


def test_9283_new_rate_and_a_correction_both_satisfy_the_lock(brazos, dana):
    """The two writers that create versions never trip the constraint —
    including a correction, whose two rows overlap for a few statements."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 PG writers", services=("water",))
        v1, _state = a_state_sales_tax(brazos, plan)
        services.new_tax_rate(dana, v1.id, {"rate": "0.065000", "effective_from": "2026-11-01"})
        check_deferred_now()
        v2 = rating_models.Tax.objects.get(chain_id=v1.chain_id, version_no=2)
        services.correct_tax(dana, v2.id, {"rate": "0.064000", "reason": "Statute read wrong"})
        check_deferred_now()
        assert rating_models.Tax.objects.filter(chain_id=v1.chain_id).count() == 3


def test_9276_one_code_names_one_chain_in_the_database(brazos):
    with tenant_ctx(brazos):
        state = authority(brazos, "CR165 PG Code State")
        rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=state, name="A", kind="percent",
            rate=Decimal("0.01"), code="SAME",
        )
        with pytest.raises(IntegrityError) as refused:
            with transaction.atomic():
                rating_models.Tax.objects.create(
                    tenant=brazos, jurisdiction=state, name="B", kind="percent",
                    rate=Decimal("0.02"), code="same",
                )
        assert "ex_taxes_code_one_chain" in str(refused.value)


def test_the_trigger_starts_or_joins_a_chain_on_a_raw_insert(brazos):
    """A path that bypasses `Tax.save()` still gets a chain."""
    with tenant_ctx(brazos):
        state = authority(brazos, "CR165 PG Trigger State")
        parent = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=state, name="Parent", kind="percent", rate=Decimal("0.01")
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO taxes (id, tenant_id, jurisdiction_id, name, kind, rate, "
                "base_includes_usage, base_includes_base, discount_treatment, is_draft, "
                "version_no, created_at, updated_at) VALUES (gen_random_uuid(), %s, %s, "
                "'Raw', 'percent', 0.02, true, true, 'after', true, 1, now(), now()) "
                "RETURNING id, chain_id",
                [str(brazos.id), str(state.id)],
            )
            raw_id, raw_chain = cursor.fetchone()
            cursor.execute(
                "INSERT INTO taxes (id, tenant_id, jurisdiction_id, name, kind, rate, "
                "base_includes_usage, base_includes_base, discount_treatment, is_draft, "
                "version_no, corrects_tax_id, created_at, updated_at) VALUES "
                "(gen_random_uuid(), %s, %s, 'Child', 'percent', 0.03, true, true, 'after', "
                "true, 2, %s, now(), now()) RETURNING chain_id",
                [str(brazos.id), str(state.id), str(parent.id)],
            )
            child_chain = cursor.fetchone()[0]
        assert raw_chain == raw_id
        assert child_chain == parent.chain_id


def test_phase5_billing_gets_exactly_one_row_per_tax_per_date_on_postgres(brazos, dana, capsys):
    """THE web walk's phase 5 on a real server: the lookup is asked for each
    tax on each side of every change and answers ONE row — 6.25% on 10/31/2026,
    6.5% on 11/01/2026 ($3.90 on $60.00), the 3% correction and never the 150%
    row, and the renamed tax as the same row as before."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="CR165 PG phase 5", services=("water",))
        sales, _state = a_state_sales_tax(brazos, plan)
        county = authority(brazos, "CR165 PG County")
        county_tax = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=county, name="County utility tax", kind="percent",
            rate=Decimal("0.020000"),
        )
        bind(brazos, plan, county)
        city = authority(brazos, "CR165 PG City")
        typo = rating_models.Tax.objects.create(
            tenant=brazos, jurisdiction=city, name="City franchise fee", kind="percent",
            rate=Decimal("1.500000"), code="PG-CITY",
        )
        bind(brazos, plan, city)

        services.new_tax_rate(dana, sales.id, {"rate": "0.065000", "effective_from": "2026-11-01"})
        fixed = services.correct_tax(dana, typo.id, {"rate": "0.030000", "reason": "Typed as 150%"})
        services.update_tax(dana, county_tax.id, {"name": "County utility tax (renamed)"})
        check_deferred_now()

        table = []
        for on in (OCT_15, OCT_31, NOV_01, NOV_15):
            rules = rules_on(plan, on)
            by_tax = {}
            for rule in rules:
                chain = rating_models.Tax.objects.get(pk=rule["tax_id"]).chain_id
                by_tax.setdefault(chain, []).append(rule)
            assert all(len(found) == 1 for found in by_tax.values()), on
            assert len(by_tax) == 3, on  # sales, county, city — never a fourth row
            ids = {rule["tax_id"] for rule in rules}
            assert str(typo.id) not in ids  # the superseded 150% row is never returned
            assert fixed["id"] in ids and str(county_tax.id) in ids
            sales_rule = by_tax[sales.chain_id][0]
            table.append((on.isoformat(), str(Decimal(str(sales_rule["rate"]))),
                           str(charged([sales_rule])), str(charged(rules))))
        assert [(row[0], row[2]) for row in table] == [
            ("2026-10-15", "3.75"), ("2026-10-31", "3.75"),
            ("2026-11-01", "3.90"), ("2026-11-15", "3.90"),
        ]
        # $60.00: sales + county $1.20 + city 3% $1.80.
        assert [row[3] for row in table] == ["6.75", "6.75", "6.90", "6.90"]
        print("\nPHASE-5 ON POSTGRESQL (date · sales rate · sales tax · whole bill's tax)")
        for row in table:
            print("  " + " · ".join(row))


def test_authority_accounts_are_tenant_scoped(rls, brazos, dana, lonestar, erin):
    """CLAUDE.md hard rule 1 on the new table, asserted under a role RLS
    applies to (`sbh_rls_probe`), never the superuser the suite connects as."""
    with tenant_ctx(brazos):
        services.create_authority_account(
            dana, {"authority_name": "TX Comptroller", "account_number": "32-1180455"}
        )
    with tenant_ctx(lonestar):
        services.create_authority_account(
            erin, {"authority_name": "Iowa DOR", "account_number": "IA-77"}
        )
    assert_denied_without_context(rls, "tax_authority_accounts")
    assert_rls_scoped(rls, "tax_authority_accounts", owner=brazos, intruder=lonestar)
    assert_write_into_other_tenant_refused(
        rls, "tax_authority_accounts", owner=brazos, intruder=lonestar
    )
