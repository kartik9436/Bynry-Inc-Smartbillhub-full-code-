# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) · 10-execution-plan.md wave M task M5's
#           fixture clause — *"AST-04412 and two more meters past certification
#           life; the drawing's seven rules, six On"*. Defect: DEF-WRK-4085.
# Rules:    BR-WRK-033 · BR-TEN-056/057 (the sample set and its tag) ·
#           BR-TEN-060 (a named not-loaded line, never a silent skip) ·
#           BR-TEN-063 (idempotent replay) · BR-TEN-061/066 (removal, partial
#           and named) · BR-WRK-002 / G78 (Work writes no other module's table)
#           · BR-WRK-016 / DEF-WRK-3573 (sequence >= 1 is what step 6 proposes)
#           · CLAUDE.md hard rule 1 (tenant scoping)
# Impacts:  apps/work/sample_data.py · apps/assets/sample_data.py ·
#           apps/metering/sample_data.py · apps/tenancy/sample_data.py
# ───────────────────────────────────────────────────────
"""The sample-data half of wave M — the rules a seeded tenant carries.

⚠ **WHY A TEST FILE FOR A FIXTURE.** `DEF-WRK-4085` was not a bug in the engine;
it was a fixture that did not exist, and nothing went red over it. Registering a
module for sample data is a shared-file edit to the framework EVERY tenant's
`load_sample_data` runs through, so the properties asserted here are the ones
that would hurt somebody other than this lane: it seeds inside one tenant, a
replay writes nothing, a utility's own edit survives that replay, and the
template it publishes does not change what New Connect proposes.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.tenancy import sample_data as tenancy_sample
from apps.work import rules, sample_data as work_sample
from apps.work.rules_models import WorkOrderRule, WorkOrderRuleRaise

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar · erin
from tests.test_us_met_helpers import make_asset, tenant_ctx

EXCHANGE = work_sample.EXCHANGE_TEMPLATE_NAME


def _publish_exchange(actor, *, service="electric", sequence=0):
    header = w6.create_work_order_template(
        actor, {"name": EXCHANGE, "service": service, "sequence": sequence}
    )
    w6.publish_work_order_template(actor, header["id"])
    return header


# ══ the registry ═══════════════════════════════════════════════════════════


def test_the_registry_carries_both_new_blocks():
    keys = [spec.key for spec in tenancy_sample.SAMPLE_MODULES]
    assert "work:seed_sample_records" in keys, (
        "DEF-WRK-4085: `work` owns tables and seeded none of them, which is why "
        "wave M's demo script could not be run at all"
    )
    assert "assets:seed_sample_aged_meters" in keys


def test_the_work_block_runs_after_the_block_that_publishes_its_template():
    """The POSITION is the feature, and it is load-bearing twice over.

    Creation: a rule's template is NOT NULL and metering publishes it.
    Removal: `BR-TEN-061` walks this tuple BACKWARDS, and a rule holds a PROTECT
    key to that template — so being late here is what lets the rules go first.
    """
    keys = [spec.key for spec in tenancy_sample.SAMPLE_MODULES]
    assert keys.index("work:seed_sample_records") > keys.index("metering:seed_sample_records")


def test_the_work_block_declares_that_dependency_verbatim():
    edges = tenancy_sample.BLOCK_DEPENDENCIES.get("work:seed_sample_records") or ()
    assert [upstream for upstream, _f, _q in edges] == ["metering:seed_sample_records"]
    upstream, path, quote = edges[0]
    import io

    assert quote in io.open(path, encoding="utf-8").read(), (
        "a dependency declared from prose stays true only while the prose does"
    )


# ══ what the block seeds ═══════════════════════════════════════════════════


@pytest.mark.django_db
def test_seven_rules_six_on_all_tagged(dana, brazos):
    with tenant_ctx(brazos):
        _publish_exchange(dana)
        written = work_sample.seed_sample_records(dana)

        rows = list(WorkOrderRule.objects.all())
        assert written == 7, [r.name for r in rows]
        assert len(rows) == 7
        # The drawing reads *7 rules · 6 on*. ⚠ Since 2026-10-04 TWO ship off:
        # *Backflow test due*, as drawn, and *Leak investigation*, which with a
        # service and a unit (`DEF-WRK-4097`) still matches 47 of the demo's 49
        # water meters at the only floor this product holds — so a supervisor
        # switches it on after reading *Tonight it would raise 47 jobs*
        # (decision log *"CR-168 ROUND 5 · SRV-4"*, lane SRV-4).
        assert sum(1 for r in rows if r.enabled) == 5
        assert all(r.is_sample for r in rows), "BR-TEN-057 — the tag is on the owning row"
        off = sorted(r.name for r in rows if not r.enabled)
        assert off == ["Backflow test due", "Leak investigation"], off


@pytest.mark.django_db
def test_every_seeded_rule_points_at_the_published_exchange_template(dana, brazos):
    with tenant_ctx(brazos):
        header = _publish_exchange(dana)
        work_sample.seed_sample_records(dana)
        # `DEF-WRK-9687` — all but one: *Backflow test due* raises the backflow
        # test, because the exchange template is done to meters.
        assert {
            str(r.template_id)
            for r in WorkOrderRule.objects.exclude(name="Backflow test due")
        } == {str(header["id"])}
        backflow = WorkOrderRule.objects.get(name="Backflow test due")
        assert str(backflow.template_id) != str(header["id"])


@pytest.mark.django_db
def test_a_replay_writes_nothing(dana, brazos):
    """BR-TEN-063 — sample data gets loaded more than once.

    ⚠ **THIS CANNOT DISTINGUISH THE CHECK FROM THE CONSTRAINT, AND THAT WAS
    PROVED RATHER THAN ASSUMED** (law 7). Deleting the seeder's `if name in
    existing` line and re-running this file left it GREEN: the second create
    then hits `uq_work_order_rules_tenant_name`, the per-rule `except` names it
    and the block still writes 0. The outcome is identical by design — the
    check is the fast path and the unique index is the guarantee — so what this
    test pins is the OUTCOME, and no test can pin which of the two delivered
    it. Said here so nobody reads a green line as proof of the branch above it.
    """
    with tenant_ctx(brazos):
        _publish_exchange(dana)
        assert work_sample.seed_sample_records(dana) == 7
        assert work_sample.seed_sample_records(dana) == 0
        assert WorkOrderRule.objects.count() == 7


@pytest.mark.django_db
def test_a_replay_does_not_switch_a_rule_the_utility_turned_off_back_on(dana, brazos):
    """The property that matters more than the count.

    A supervisor switches *Leak investigation* off in December. The next
    sample-data load must not turn it back on, or the rule the utility silenced
    starts raising work again with nobody having asked.
    """
    with tenant_ctx(brazos):
        _publish_exchange(dana)
        work_sample.seed_sample_records(dana)
        leak = WorkOrderRule.objects.get(name="Leak investigation")
        rules.set_rule_enabled(dana, leak.id, False)

        work_sample.seed_sample_records(dana)

        leak.refresh_from_db()
        assert leak.enabled is False
        assert WorkOrderRule.objects.count() == 7


@pytest.mark.django_db
def test_a_renamed_rule_is_seeded_again_under_its_original_name(dana, brazos):
    """The ONE edit a replay does not respect — asserted so it is a known fact.

    The name is the identity, so a utility that renames a seeded rule has, as
    far as the block can tell, no such rule. This is the cost of not putting a
    seed key on `work_order_rules`, and the alternative — skipping the whole
    block when any sample rule exists — would strand a tenant that legitimately
    seeded fewer than seven. Write it down rather than discover it on a demo.
    """
    with tenant_ctx(brazos):
        _publish_exchange(dana)
        work_sample.seed_sample_records(dana)
        leak = WorkOrderRule.objects.get(name="Leak investigation")
        rules.update_rule(dana, leak.id, {"name": "Leaks"})

        assert work_sample.seed_sample_records(dana) == 1
        assert WorkOrderRule.objects.count() == 8
        assert WorkOrderRule.objects.filter(name="Leak investigation").exists()


@pytest.mark.django_db
def test_no_published_template_is_a_named_refusal_and_not_a_crash(dana, brazos):
    """BR-TEN-060 — a block that cannot run says so and seeds nothing.

    The template is metering's row. If its block did not publish one, seeding
    seven rules that each show *This month 0* for ever would be worse than
    seeding none.
    """
    with tenant_ctx(brazos):
        assert work_sample.seed_sample_records(dana) == 0
        assert WorkOrderRule.objects.count() == 0


@pytest.mark.django_db
def test_a_draft_template_is_not_good_enough(dana, brazos):
    """`BR-WRK-012`/`BR-WRK-016` — `_raise_one` refuses to raise from a draft,
    so a rule pointed at one is a rule that can never fire."""
    with tenant_ctx(brazos):
        w6.create_work_order_template(dana, {"name": EXCHANGE, "service": "electric"})
        assert work_sample.seed_sample_records(dana) == 0


# ══ tenant scoping — CLAUDE.md hard rule 1 ═════════════════════════════════


@pytest.mark.django_db
def test_seeding_one_utility_writes_rows_for_that_utility_only(dana, brazos, lonestar):
    """Every row this block writes carries the tenant in context and no other.

    ⚠ **THIS IS NOT AN RLS PROOF AND MUST NOT BE READ AS ONE.** The suite runs
    on in-memory SQLite (`config/settings/test.py` replaces `DATABASES`
    wholesale — CLAUDE.md law 14), and SQLite has no row-level security, so an
    UNFILTERED `WorkOrderRule.objects.count()` inside `tenant_ctx(lonestar)`
    returns every row in the database. A first draft asserted exactly that and
    failed 7 == 0, which is the assertion being vacuous rather than the code
    leaking. What is provable here is the thing this block controls: the
    `tenant_id` it stamps. The DATABASE-enforced half is
    `tests/test_us_wrk_037_rules_pg.py`, on real PostgreSQL under a
    NOSUPERUSER role, and it is the only place that proof can be made.
    """
    with tenant_ctx(brazos):
        _publish_exchange(dana)
        work_sample.seed_sample_records(dana)
        assert work_sample.sample_record_count() == 7

    assert WorkOrderRule.objects.filter(tenant_id=brazos.id).count() == 7
    assert WorkOrderRule.objects.filter(tenant_id=lonestar.id).count() == 0

    with tenant_ctx(lonestar):
        # The module's own count is tenant-filtered, so it answers correctly
        # even where the database is not enforcing anything.
        assert work_sample.sample_record_count() == 0


# ══ removal — BR-TEN-061 / BR-TEN-066 ══════════════════════════════════════


@pytest.mark.django_db
def test_removal_deletes_rules_that_never_raised(dana, brazos):
    with tenant_ctx(brazos):
        _publish_exchange(dana)
        work_sample.seed_sample_records(dana)
        report = work_sample.remove_sample_records()
        assert report["removed"] == 7
        assert report["retained"] == []
        assert WorkOrderRule.objects.count() == 0


@pytest.mark.django_db
def test_a_rule_that_has_raised_is_switched_off_and_retained_by_name(dana, brazos):
    """Deleting it would CASCADE its raises away — and the raises are the
    sweep's memory. Removing sample data must not make tonight's sweep re-raise
    a job a crew already did."""
    with tenant_ctx(brazos):
        _publish_exchange(dana)
        work_sample.seed_sample_records(dana)
        rule = WorkOrderRule.objects.get(name="Asset age rule")
        WorkOrderRuleRaise.objects.create(
            tenant_id=rule.tenant_id,
            rule_id=rule.id,
            subject_kind="asset",
            subject_key="AST-04412",
        )

        report = work_sample.remove_sample_records()

        rule.refresh_from_db()
        assert rule.enabled is False, "switched off rather than deleted"
        assert WorkOrderRule.objects.filter(pk=rule.id).exists()
        assert [r["label"] for r in report["retained"]] == ["rule Asset age rule"]
        assert report["removed"] == 6


# ══ the template this fixture publishes must not move New Connect ══════════


@pytest.mark.django_db
def test_the_exchange_template_is_not_proposed_by_new_connect(dana, brazos):
    """`BR-WRK-016` / `DEF-WRK-3573`, which names THIS template by name.

    Step 6 proposes published templates with `sequence >= 1`. The exchange
    template is seeded at 0, so publishing it adds nothing to any build's
    proposal — the one property that makes seeding it safe for every tenant.
    """
    from apps.work import selectors

    with tenant_ctx(brazos):
        _publish_exchange(dana, sequence=0)
        proposed = selectors.proposed_work_orders("electric")
        names = [row.get("name") for row in (proposed.get("rows") or proposed.get("orders") or [])]
        assert EXCHANGE not in names, names
