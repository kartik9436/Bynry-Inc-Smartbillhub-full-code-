# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5823 — `rating/0039` restored three plans' customer classes
#          from snapshots whose `account_type_id` no longer resolves, so the
#          repair put back a class that points at nothing · DEF-RAT-5822 — the
#          same unresolved id renders as a raw UUID chip (B14 rule 31) and is
#          DROPPED by `addableCharges`, switching class narrowing off.
# Rules:   CLAUDE.md hard-won law 7 (ask what makes a check pass WRONGLY) ·
#          CLAUDE.md hard-won law 14 (the suite's sqlite cannot express this) ·
#          CLAUDE.md hard rule 1 (tenant scoping) · DEF-RAT-5768 (`[]` means
#          EVERY class)
# Fix in:  06-backend/apps/rating/migrations/
#          0041_def_rat_5823_drop_unresolvable_classes.py
# ───────────────────────────────────────────────────────
"""**A plan never names a customer class that resolves to nothing — and a class
that DOES resolve is never touched.**

════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THIS FILE PASS WRONGLY — asked first, per hard-won law 7
════════════════════════════════════════════════════════════════════════════
The obvious assertion is *"no plan holds a dangling id afterwards"*, and it is
worthless on its own, in two different directions:

* it passes on a migration that **empties every list**, which would silently
  widen every plan in the product to EVERY class; and
* it passes on a plan that **had no ids to begin with**, which is most of them.

So nothing here asserts only an absence. The load-bearing cases assert that a
RESOLVABLE id **survives** — alone, and mixed into a list beside a dangling one
where only the dangling entry may go — and that a plan whose list is already
clean is not written at all. `test_a_mixed_list…` is the one case that fails in
BOTH wrong directions, which is why it exists separately from the two either
side of it.

════════════════════════════════════════════════════════════════════════════
WHY PostgreSQL-ONLY, AND IT IS THE REASON THE DEFECT SHIPPED (law 14)
════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` hardcodes in-memory sqlite. `account_types` is RLS
`FORCE`-scoped on PostgreSQL since `customers/0055`, and sqlite has no
row-level security at all — so "what resolves FOR THIS TENANT" is a question
only the real database can answer, and the cross-tenant case below is
unprovable anywhere else. This is the same wall `DEF-RAT-5799` hit: `0038`'s
backfill read zero rows under RLS and twelve sqlite cases stayed green.

Run with:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
        pytest tests/test_def_rat_5823_unresolvable_classes_pg.py --reuse-db
"""

from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import connection

from apps.customers.models import AccountType
from apps.rating.models import PlanVersion, RatePlan

from tests.isolation_helpers import requires_postgres
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared W1 fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]

MIGRATION = "apps.rating.migrations.0041_def_rat_5823_drop_unresolvable_classes"
BACKFILL_0039 = "apps.rating.migrations.0039_def_rat_5799_class_backfill_under_rls"

#: An id shaped exactly like the three the beta actually holds — the deleted
#: PLATFORM generation `customers/0054` left behind. Any uuid would do; this
#: prefix is used so a failure message looks like the real defect.
DANGLING = "01a0afa2-8ba0-7452-b43e-9d5154a8eedd"


def _run(module_path: str) -> None:
    """Run a migration's forward function against the live registry.

    The historical models this migration asks for carry the same fields as the
    real ones at this point in the graph, so the app registry stands in for
    `apps` and a one-attribute shim for `schema_editor`. `apps.rating.migrations
    .0041…` is not importable by `from` — the module name starts with a digit —
    which is why `import_module` is used here and in `test_cr063_fire_service`.
    """
    from django.apps import apps as live_registry

    module = import_module(module_path)
    forward = module.__dict__[
        "_drop_unresolvable" if module_path == MIGRATION else "_repair"
    ]
    forward(live_registry, SimpleNamespace(connection=connection))
    # ⚠ THIS LEAVES `app.tenant_id` AT THE NIL UUID, exactly as the real
    # migration does — `set_config(..., false)` is SESSION level and the
    # migration resets it on the way out (`0039` and `customers/0054` do the
    # same). So every case below runs the migration OUTSIDE a tenant context,
    # which is how a migration actually runs, and re-enters to read back. A
    # case that read back inside the original `with` block would see
    # `RatePlan.DoesNotExist` under RLS and look exactly like a deleted row.


def _plan(env, code: str, account_type_ids):
    return RatePlan.objects.create(
        tenant=env.tenant,
        code=code,
        name=f"Plan {code}",
        account_type_ids=account_type_ids,
    )


def _two_real_classes(env) -> tuple[str, str]:
    """Two ids that genuinely resolve for this tenant, taken from the rows
    provisioning seeded rather than invented."""
    rows = list(
        AccountType.objects.filter(tenant_id=env.tenant.id)
        .order_by("code")
        .values_list("id", flat=True)[:2]
    )
    assert len(rows) == 2, (
        "this tenant has fewer than two account_types, so the cases below "
        "could not tell 'kept' from 'dropped' — the fixture is wrong, not the code"
    )
    return str(rows[0]), str(rows[1])


# ══ the pure rule, readable on its own ═════════════════════════════════════


def test_the_rule_keeps_order_and_drops_only_what_is_unknown():
    """`resolvable()` alone, with no database in the way."""
    module = import_module(MIGRATION)
    known = {"a", "b"}
    assert module.resolvable(["a", DANGLING, "b"], known) == ["a", "b"]
    assert module.resolvable(["b", "a"], known) == ["b", "a"], "order is preserved"
    assert module.resolvable([DANGLING], known) == []
    assert module.resolvable([], known) == []
    assert module.resolvable(None, known) == [], "a NULL column reads as every class"
    assert module.resolvable(["a", None, 7], known) == ["a"], "junk is not an id"


# ══ the cases that carry the weight ════════════════════════════════════════


def test_a_resolvable_class_survives_untouched(env):
    """⚠ THE ANTI-'CLEARS EVERYTHING' CASE. A migration that emptied every list
    would pass a dangling-id test and fail here."""
    with tenant_ctx(env.tenant):
        good, _ = _two_real_classes(env)
        plan = _plan(env, "KEEP", [good])
    _run(MIGRATION)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        assert plan.account_type_ids == [good], (
            "a class that resolves was removed — this migration may only ever "
            "drop what points at nothing"
        )


def test_a_dangling_class_is_removed_and_nothing_is_invented(env):
    with tenant_ctx(env.tenant):
        plan = _plan(env, "DROP", [DANGLING])
    _run(MIGRATION)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        assert plan.account_type_ids == [], (
            f"expected the unresolvable id to be dropped, got "
            f"{plan.account_type_ids!r}"
        )
        # ⚠ AND NOT SUBSTITUTED. The failure this guards against is a lane
        # "helpfully" resolving the id by plan code or by position, which
        # `BR-MET-151` clause 3 forbids and which would be invented data.
        assert DANGLING not in (plan.account_type_ids or [])


def test_a_mixed_list_loses_only_the_dangling_entry_and_keeps_its_order(env):
    """⚠ THE CASE THAT FAILS IN BOTH WRONG DIRECTIONS AT ONCE — it is red for a
    migration that clears everything AND for one that clears nothing."""
    with tenant_ctx(env.tenant):
        first, second = _two_real_classes(env)
        plan = _plan(env, "MIXED", [first, DANGLING, second])
    _run(MIGRATION)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        assert plan.account_type_ids == [first, second], (
            f"expected exactly the two resolvable ids, in order, got "
            f"{plan.account_type_ids!r}"
        )


def test_a_plan_whose_list_is_already_clean_is_not_written_at_all(env):
    """A repair that rewrote every row would churn every plan for nothing.

    ⚠ **THE OBVIOUS VERSION OF THIS TEST CANNOT FAIL, AND IT TOOK A LIVE
    DATABASE TO SEE IT (hard-won law 7).** The first draft asserted that
    `updated_at` had not moved. It never moves: `updated_at` is `auto_now`, and
    `save(update_fields=["account_type_ids"])` writes only the named column, so
    Django does not refresh it. **Measured on the beta, which is what settled
    it:** the three `SCW-*` rows went from a dangling id to `[]` — they were
    written — and their `updated_at` came back byte-identical, to the
    microsecond. A test asserting that timestamp is green whether the row was
    written or not.

    So this counts the WRITES instead. `CaptureQueriesContext` sees every
    statement the migration issues, and an `UPDATE` naming this plan is the
    thing that must not be there.
    """
    from django.test.utils import CaptureQueriesContext

    with tenant_ctx(env.tenant):
        good, _ = _two_real_classes(env)
        clean = _plan(env, "CLEAN", [good])
        dirty = _plan(env, "DIRTY", [DANGLING])

    with CaptureQueriesContext(connection) as captured:
        _run(MIGRATION)

    # ⚠ TWO TRAPS HERE, BOTH MET WHILE WRITING THIS AND BOTH SILENT.
    # (1) `"UPDATE" in sql.upper()` also matches a SELECT that lists the
    #     column `updated_at`, so the filter has to be on the STATEMENT, not
    #     on the text.
    # (2) psycopg renders a uuid parameter WITHOUT DASHES —
    #     `'01a0b8d8e8167e7c9f8a22a0f045b0db'::uuid` — so `str(pk)` is never
    #     found in the SQL and every `in sql` test answers False. A version of
    #     this case that only asserted the clean plan was absent would have
    #     been GREEN on both mistakes at once, which is why the second
    #     assertion below exists.
    updates = [
        q["sql"]
        for q in captured.captured_queries
        if q["sql"].lstrip().upper().startswith("UPDATE") and "rate_plans" in q["sql"]
    ]

    def _names(pk) -> bool:
        return any(str(pk) in sql or pk.hex in sql for sql in updates)
    assert not _names(clean.pk), (
        f"the clean plan was written although nothing about it changed; "
        f"{len(updates)} UPDATE(s) on rate_plans were issued"
    )
    # ⚠ AND THE OTHER HALF, or this passes on a migration that writes NOTHING —
    # which is exactly the `clears-nothing` failure direction.
    assert _names(dirty.pk), (
        "no UPDATE touched the plan that DID hold a dangling id, so this case "
        "would have passed on a migration that does nothing at all"
    )


def test_another_tenants_class_does_not_resolve_here(env, django_user_model):
    """⚠ ONLY PostgreSQL CAN ASK THIS. Since `customers/0054` a code is no
    longer a platform-wide fact: two utilities may both have `residential` as
    different rows. A plan may name only ITS OWN tenant's vocabulary, so an id
    belonging to another tenant is exactly as unresolvable as a deleted one."""
    from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

    payload = brazosbend_payload()
    payload["subdomain"] = f"other{uuid4().hex[:8]}"
    payload["name"] = "Another Utility"
    other, _ = provisioned_tenant(payload)

    with tenant_ctx(other):
        foreign = str(
            AccountType.objects.filter(tenant_id=other.id).values_list("id", flat=True)[0]
        )

    with tenant_ctx(env.tenant):
        mine, _ = _two_real_classes(env)
        plan = _plan(env, "FOREIGN", [mine, foreign])
    _run(MIGRATION)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        assert plan.account_type_ids == [mine], (
            f"another tenant's account type was treated as resolvable — "
            f"got {plan.account_type_ids!r}"
        )


def test_running_it_twice_changes_nothing_the_second_time(env):
    with tenant_ctx(env.tenant):
        good, _ = _two_real_classes(env)
        plan = _plan(env, "TWICE", [good, DANGLING])
    _run(MIGRATION)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        once = plan.account_type_ids
    _run(MIGRATION)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        assert plan.account_type_ids == once == [good]


# ══ the claim `0039` makes about itself, PROVED rather than repeated ════════


def test_0039_never_overwrites_a_class_a_clerk_already_set(env):
    """`0039`'s docstring says *"IT ONLY EVER FILLS AN EMPTY LIST"*. That is a
    comment claiming a guarantee (hard-won law 1), so here is the guarantee.

    The plan holds a class set by hand; its filed snapshot names a DIFFERENT
    one. If `0039` preferred the snapshot, the clerk's choice would be silently
    replaced — and on this estate it would be replaced by a dangling id.
    """
    with tenant_ctx(env.tenant):
        by_hand, _ = _two_real_classes(env)
        plan = _plan(env, "BYHAND", [by_hand])
        PlanVersion.objects.create(
            tenant=env.tenant,
            rate_plan=plan,
            version_no=1,
            snapshot={"account_type_id": DANGLING, "code": "BYHAND"},
        )
    _run(BACKFILL_0039)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        assert plan.account_type_ids == [by_hand], (
            f"0039 overwrote a class that was already set — got "
            f"{plan.account_type_ids!r}, expected the clerk's {by_hand!r}"
        )


def test_0039_does_fill_an_empty_list_from_the_snapshot(env):
    """The other half, so the case above cannot pass because `0039` does
    nothing at all — which would make it a check incapable of failing."""
    with tenant_ctx(env.tenant):
        stated, _ = _two_real_classes(env)
        plan = _plan(env, "EMPTY", [])
        PlanVersion.objects.create(
            tenant=env.tenant,
            rate_plan=plan,
            version_no=1,
            snapshot={"account_type_id": stated, "code": "EMPTY"},
        )
    _run(BACKFILL_0039)
    with tenant_ctx(env.tenant):
        plan.refresh_from_db()
        assert plan.account_type_ids == [stated]
