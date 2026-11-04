# ── Trace ──────────────────────────────────────────────
# Change:  PO ruling 2026-09-28 — the Accounts list carries FOUR tiles, one per
#          account status: **Active · Pending · Disconnecting · Suspended**.
#          Each states a count and each narrows the list to it.
# Defect:  DEF-CUS-7700 — two of the five tiles it replaces never counted
#          anything. `PAST DUE 60+` and `CLOSED THIS YEAR` rendered the literal
#          "Not counted yet" from the day they shipped, and the test that
#          guarded them asserted that literal — so the gap read as intended
#          behaviour to every check in the repo.
# Rules:   BR-CUS-055 (the seeded statuses, their behaviour classes, and the
#          list being tenant-EXTENSIBLE) · CLAUDE.md hard rule 1 (tenant
#          scoping, RLS FORCE) · NFR-3 (the count is a server aggregate, never
#          a page counted in the browser)
# Screens: S17 — Accounts → Accounts
# ───────────────────────────────────────────────────────
"""`selectors.account_status_counts()` — one grouped query, four tiles.

WHAT EACH CASE PROVES, AND WHY IT IS THAT SHAPE
-----------------------------------------------
**§1 · the arithmetic.** The four seeded codes come back with the accounts that
really sit on them, and nothing else does. Asserted as a whole MAP rather than
four `assert counts["active"] == 2` lines: a check that reads only the keys it
expects cannot fail when a fifth appears or a sixth vanishes, which is half of
what this read is for.

**§2 · a status with NO accounts still comes back, at zero.** This is the case
that decides the shape of the query, and it is the one a
`accounts.values("status__code").annotate(Count())` cannot answer: grouping
from the ACCOUNTS side returns no row at all for an empty status, and the
screen then cannot tell *"nobody is suspended"* from *"this utility has no such
status"*. The join runs from `account_statuses` for exactly this.

**§3 · a status the tenant does not have is ABSENT, not zero.** The mirror of
§2, and the reason the two are separate cases. A utility that never seeded
`vacation_hold` gets no key for it, so the tile can draw an absence instead of
claiming a count of zero about a thing that does not exist here.

**§4 · a RENAMED status is still counted, under its own name.** BR-CUS-055 is
tenant-extensible; the tile keys off the CODE and the tenant's own `name`
travels beside it. A count that keyed off the label would silently read zero
for every utility that reworded a seeded status.

**§5 · ONE query.** `django_assert_num_queries`, because the read this replaces
was a second whole `GET /accounts` fired from the browser for one envelope
`count` — and four tiles built that way are four list reads.

**§6 · tenant scoping, and §7 the same guarantee AT THE DATABASE on real
PostgreSQL.** §6 is the app-layer filter and runs on any vendor. §7 executes
the GROUPED SQL ITSELF through `sbh_rls_probe` — NOLOGIN, NOSUPERUSER,
NOBYPASSRLS — with the app-layer filter deliberately out of the path, so the
only thing that can be scoping the count is the row-level policy. sqlite has no
RLS, so it cannot hold that guarantee and the case is skipped there with a
vendor reason rather than passing vacuously (hard-won law 7).

PROVEN RED BEFORE TRUSTED GREEN (hard-won law 7) — see the lane report: every
case here was run against `selectors.py` WITHOUT `account_status_counts` and
failed with `AttributeError: module 'apps.customers.selectors' has no attribute
'account_status_counts'`, and §2 was additionally run against a draft that
grouped from the accounts side and failed with `KeyError: 'vacation_hold'`.

RUN WITH `JOBS_EAGER=false --reuse-db` (DEF-567, DEF-GOV-3778).
"""
import pytest

from apps.customers import models as customers_models, selectors, services as customers_services

from tests.isolation_helpers import (
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The four the PO's tiles read, by CODE. `services.SEED_ACCOUNT_STATUSES`
#: verbatim — never retyped English, because a renamed label must not move a
#: tile and a retyped code would not say so.
TILE_CODES = ("active", "pending_activation", "marked_disconnect", "vacation_hold")


def _plant(tenant, code_counts: dict[str, int]) -> None:
    """`code_counts[code]` accounts on each named status, inside `tenant`.

    ⚠ **EVERY ACCOUNT GETS ITS OWN UNIT.** BR-CUS-017 puts at most one occupying
    account on a unit, and three of these four codes are occupying classes — so
    a fixture that reused one unit would be planting a state the product
    refuses, and the count it proved would be a count of something impossible.
    """
    from apps.metering import models as metering_models

    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line="1408 Elm St", city="Ottumwa", state="IA"
    )
    account_type = customers_models.AccountType.objects.filter(tenant=tenant).first()
    assert account_type is not None, "the tenant has no account type seeded"
    serial = 0
    for code, how_many in code_counts.items():
        status = customers_models.AccountStatus.objects.get(tenant=tenant, code=code)
        for _ in range(how_many):
            serial += 1
            unit = metering_models.Unit.objects.create(
                tenant=tenant, premises=premises, label=f"Unit {serial}"
            )
            customers_models.Account.objects.create(
                tenant=tenant,
                unit=unit,
                account_no=f"A-8{serial:04d}",
                status=status,
                account_type=account_type,
            )


def _by_code(rows) -> dict[str, int]:
    return {row["code"]: row["accounts"] for row in rows}


# ══════════════════════════════════════════════════════════════════════════
# §1 · THE ARITHMETIC
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__each_seeded_status_reports_the_accounts_that_sit_on_it(brazos):  # noqa: F811
    with tenant_ctx(brazos):
        _plant(
            brazos,
            {"active": 3, "pending_activation": 1, "marked_disconnect": 2, "vacation_hold": 1},
        )
        counts = _by_code(selectors.account_status_counts())

    # The WHOLE map, not four picked keys: a check that reads only the keys it
    # expects cannot notice a status appearing or disappearing.
    assert counts == {
        "active": 3,
        "pending_activation": 1,
        "marked_disconnect": 2,
        "vacation_hold": 1,
        "closed": 0,
        "disconnected": 0,
    }


def test_tc1b__the_four_tile_codes_are_the_seed_and_not_retyped_english():
    """The tiles' four codes exist in `SEED_ACCOUNT_STATUSES` and are spelled it.

    ⚠ **THE FRONT END KEYS ITS FOUR TILES OFF THESE STRINGS**, so a rename in
    the seed with no change here is a screen that silently counts nothing — the
    service-list failure this repo already records twice (CLAUDE.md, hard-won
    law 2's *never hand-type a list*).
    """
    seeded = {code for code, _name, _cls in customers_services.SEED_ACCOUNT_STATUSES}
    assert set(TILE_CODES) <= seeded, f"a tile names a status the seed does not: {TILE_CODES}"


# ══════════════════════════════════════════════════════════════════════════
# §2 · AN EMPTY STATUS IS A ZERO — and §3 A MISSING ONE IS AN ABSENCE
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__a_status_holding_nobody_still_comes_back_at_zero(brazos):  # noqa: F811
    """`vacation_hold` exists here and holds nobody. That is a real zero.

    ⚠ **THIS IS THE CASE THE OBVIOUS QUERY FAILS.** Grouping from `accounts`
    returns no row for a status no account is on, and the tile would then have
    to guess whether the utility has no suspended customers or no such status.
    """
    with tenant_ctx(brazos):
        _plant(brazos, {"active": 2})
        counts = _by_code(selectors.account_status_counts())

    assert counts["vacation_hold"] == 0
    assert counts["active"] == 2


def test_tc3__a_status_the_tenant_does_not_have_is_absent_rather_than_zero(brazos):  # noqa: F811
    """A utility that does not carry `vacation_hold` gets NO KEY for it.

    BR-CUS-055 is tenant-extensible in both directions — this is the deletion
    half. The screen draws an absence here, never `0`, because zero suspended
    customers and no such status are different sentences.
    """
    with tenant_ctx(brazos):
        _plant(brazos, {"active": 1})
        customers_models.AccountStatus.objects.filter(
            tenant=brazos, code="vacation_hold"
        ).delete()
        counts = _by_code(selectors.account_status_counts())

    assert "vacation_hold" not in counts
    assert counts["active"] == 1


# ══════════════════════════════════════════════════════════════════════════
# §4 · A RENAMED STATUS IS STILL COUNTED
# ══════════════════════════════════════════════════════════════════════════
def test_tc4__renaming_a_seeded_status_does_not_move_its_count(brazos):  # noqa: F811
    with tenant_ctx(brazos):
        _plant(brazos, {"vacation_hold": 4, "active": 1})
        customers_models.AccountStatus.objects.filter(
            tenant=brazos, code="vacation_hold"
        ).update(name="Snowbird hold")
        rows = selectors.account_status_counts()

    suspended = next(row for row in rows if row["code"] == "vacation_hold")
    assert suspended["accounts"] == 4, "the count keys off the CODE, never the label"
    # …and the tenant's own word travels with it, so a caller that wants it
    # needs no second read of the lookup table.
    assert suspended["name"] == "Snowbird hold"


def test_tc5__a_tenant_added_status_is_served_and_no_tile_draws_it(brazos):  # noqa: F811
    """US-CUS-020 TC-3's *Legal hold*. Served, counted, and not a tile.

    Serving only the four would make this read the tiles' private index rather
    than the tenant's status census, and the next screen that wants a fifth
    figure would add a fifth query instead of reading this one.
    """
    with tenant_ctx(brazos):
        legal = customers_models.AccountStatus.objects.create(
            tenant=brazos,
            code="legal_hold",
            name="Legal hold",
            behavior_class=customers_services.CLASS_NON_BILLABLE,
        )
        _plant(brazos, {"active": 1})
        customers_models.Account.objects.filter(tenant=brazos).update(status=legal)
        counts = _by_code(selectors.account_status_counts())

    assert counts["legal_hold"] == 1
    assert counts["active"] == 0
    assert set(TILE_CODES) <= set(counts), "the four tiles still have their statuses"


# ══════════════════════════════════════════════════════════════════════════
# §5 · ONE QUERY
# ══════════════════════════════════════════════════════════════════════════
def test_tc6__all_four_counts_cost_exactly_one_statement(brazos, django_assert_num_queries):  # noqa: F811
    with tenant_ctx(brazos):
        _plant(brazos, {"active": 2, "pending_activation": 1})
        with django_assert_num_queries(1):
            selectors.account_status_counts()


# ══════════════════════════════════════════════════════════════════════════
# §6 · TENANT SCOPING — the app-layer filter, on any vendor
# ══════════════════════════════════════════════════════════════════════════
def test_tc7__the_counts_never_include_another_tenants_accounts(brazos, lonestar):  # noqa: F811
    with tenant_ctx(brazos):
        _plant(brazos, {"active": 2})
    with tenant_ctx(lonestar):
        _plant(lonestar, {"active": 7, "vacation_hold": 3})

    with tenant_ctx(brazos):
        mine = _by_code(selectors.account_status_counts())
    with tenant_ctx(lonestar):
        theirs = _by_code(selectors.account_status_counts())

    assert mine["active"] == 2, "Brazos Bend is counting Lone Star Ridge's accounts"
    assert mine["vacation_hold"] == 0
    assert theirs["active"] == 7
    assert theirs["vacation_hold"] == 3


# ══════════════════════════════════════════════════════════════════════════
# §7 · THE SAME GUARANTEE AT THE DATABASE — real PostgreSQL only
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_tc8__rls_alone_scopes_the_grouped_count(brazos, lonestar, rls):  # noqa: F811
    """The GROUPED SQL, run through `sbh_rls_probe` with no app-layer filter.

    ⚠ **THE APP FILTER IS DELIBERATELY OUT OF THE PATH.** `account_status_counts`
    filters on `tenant_id` twice over, so a test that calls it can never tell
    whether the ORM or the policy did the scoping. This runs the join the
    selector emits — `account_statuses LEFT JOIN accounts` — as raw SQL under a
    NOLOGIN NOSUPERUSER NOBYPASSRLS role, so the ONLY thing that can be keeping
    Lone Star Ridge's seven accounts out of Brazos Bend's tile is RLS.

    ⚠ **SKIPPED ON THE DEFAULT sqlite RUN** (`requires_postgres`), and that is
    not a gap being tolerated: sqlite has no row-level security, so the
    guarantee cannot exist there and a green case would be hard-won law 7's
    *incapable of failing*. `config/settings/test.py` hardcodes sqlite, which is
    why this needs `DATABASE_URL` and `config.settings.local`.

    ⚠ **HOW THIS WAS PROVED RED, AND WHY NOT THE USUAL WAY (law 7).** The house
    proof is `ALTER TABLE accounts DISABLE ROW LEVEL SECURITY`, watch the case
    fail, restore. **This container refuses that statement**, so the proof was
    made from the other side and is no weaker: the two tenants are planted with
    **2** and **7** active accounts, so an unscoped count reads **9**. The
    assertion was temporarily changed to `== 9` and run, and it failed with

        AssertionError: accounts: LEAK — … assert 2 == 9

    which says in one line that the probe really reads 2 and that 9 — the exact
    number a leak produces — is a value this assertion refuses. A check that
    could not tell 2 from 9 is the one this clause exists to rule out.
    """
    rls.assert_is_a_real_proof()

    with tenant_ctx(brazos):
        _plant(brazos, {"active": 2, "marked_disconnect": 1})
    with tenant_ctx(lonestar):
        _plant(lonestar, {"active": 7, "vacation_hold": 3})

    from tests.isolation_helpers import live_tenant_context

    grouped = (
        "SELECT s.code, count(a.id) "
        "FROM account_statuses s LEFT JOIN accounts a ON a.status_id = s.id "
        "GROUP BY s.code ORDER BY s.code"
    )
    with live_tenant_context(brazos.id):
        seen = {code: total for code, total in rls.rows(grouped)}

    assert seen.get("active") == 2, (
        "accounts: LEAK — Brazos Bend's Active tile counted rows the policy "
        f"should have hidden (saw {seen.get('active')!r}, expected 2)"
    )
    assert seen.get("marked_disconnect") == 1
    # Lone Star Ridge's three suspended accounts must not reach this tenant's
    # tile, and its own statuses must not reach this tenant's strip at all.
    assert seen.get("vacation_hold") == 0
    assert len(seen) == len(
        set(code for code, _n, _c in customers_services.SEED_ACCOUNT_STATUSES)
    ), f"the strip saw another tenant's status rows: {sorted(seen)}"
