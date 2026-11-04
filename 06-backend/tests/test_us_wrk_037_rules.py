# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) TC-1…TC-7 — rules that raise work orders on
#           their own.
# Rules:    BR-WRK-033 · BR-WRK-024 · BR-WRK-002 · CLAUDE.md hard rule 1
# ───────────────────────────────────────────────────────
"""The overnight sweep: idempotent, off-means-off, stamped, and scoped.

⚠ **WHAT THIS FILE CANNOT PROVE, AND SAYS SO RATHER THAN IMPLYING OTHERWISE.**
`config/settings/test.py` hardcodes SQLite, which has no aborted-transaction
state and no row-level security. So the SAVEPOINT that makes one refused
subject survivable (hard-won law 14) and the RLS policy that makes a rule
readable only by its own utility are BOTH invisible here — the broken version of
each passes every case below. `tests/test_us_wrk_037_rules_pg.py` runs those two
against real PostgreSQL as a NOSUPERUSER role, which is the only configuration
in which either is evidence.
"""

from __future__ import annotations

import datetime as dt

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work import rules
from core import tenancy as core_tenancy

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar · erin
from tests.test_us_met_helpers import make_installed_asset, tenant_ctx


def _published_template(actor, *, name="Meter exchange", service="electric"):
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _aged_meter(actor, *, asset_no, due, service="electric"):
    """One meter already past its certification life."""
    # INSTALLED (`CR-168-BRC10` §30, `BR-WRK-066`): a meter on the shelf is
    # no longer a certification subject.
    asset = make_installed_asset(actor, asset_no=asset_no, service=service)
    from apps.assets import models as assets_models

    assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=due)
    return asset


def _asset_age_rule(actor, template_id, *, name="Asset age rule", enabled=True):
    return rules.create_rule(
        actor,
        {
            "name": name,
            "source_module": work_models.WorkOrderRule.SOURCE_ASSETS,
            "trigger_kind": work_models.WorkOrderRule.TRIGGER_ASSET_PAST_CERTIFICATION,
            "template_id": template_id,
            "enabled": enabled,
        },
    )


YESTERDAY = dt.date.today() - dt.timedelta(days=1)


# ── TC-1 · the sweep is idempotent per (rule, meter) ────────────────────────
@pytest.mark.django_db
def test_tc1_running_the_sweep_twice_raises_nothing_the_second_time(dana, brazos):
    with tenant_ctx(brazos):
        template = _published_template(dana)
        for n in (1, 2, 3):
            _aged_meter(dana, asset_no=f"AST-0441{n}", due=YESTERDAY)
        rule = _asset_age_rule(dana, template["id"])

        first = rules.sweep(dana)
        assert first["raised"] == 3, first

        second = rules.sweep(dana)
        # THE WHOLE POINT. Same night, same rule, same three meters — nothing.
        assert second["raised"] == 0, second
        assert second["rules"][0]["subjects"] == 3, "the subjects are still THERE"

        # Three orders on the branch, not six.
        assert work_tables.WorkOrder.objects.filter(rule_id=rule["id"]).count() == 3
        assert work_models.WorkOrderRuleRaise.objects.filter(rule_id=rule["id"]).count() == 3


# ── TC-2 · a rule that is Off raises nothing ───────────────────────────────
@pytest.mark.django_db
def test_tc2_a_rule_that_is_off_raises_nothing(dana, brazos):
    with tenant_ctx(brazos):
        template = _published_template(dana)
        _aged_meter(dana, asset_no="AST-04412", due=YESTERDAY)
        rule = _asset_age_rule(dana, template["id"], enabled=False)

        result = rules.sweep(dana)
        assert result["raised"] == 0
        # Not merely "raised nothing" — the rule was not READ at all: it is
        # absent from the per-rule report, because `enabled` is filtered in the
        # QUERY. `BR-WRK-033`'s second half costs nothing when it is off.
        assert result["rules"] == []

        # And switching it on later DOES raise — otherwise this case would pass
        # over a sweep that was broken for every rule.
        rules.set_rule_enabled(dana, rule["id"], True)
        assert rules.sweep(dana)["raised"] == 1


# ── TC-3 · every rule-raised order stamps its source AND its rule ──────────
@pytest.mark.django_db
def test_tc3_a_rule_raised_order_says_why_it_exists(dana, brazos):
    with tenant_ctx(brazos):
        template = _published_template(dana)
        asset = _aged_meter(dana, asset_no="AST-04412", due=YESTERDAY)
        rule = _asset_age_rule(dana, template["id"])

        rules.sweep(dana)

        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        # BR-WRK-024, both halves. ⚠ This read `"assets"` until 2026-10-04 and
        # asserted the defect: `assets` is the Assets DOOR's label (BR-WRK-056),
        # so a rule's job could not be told from a clerk's (`DEF-WRK-4096`,
        # CR-168 P3.31 — the process's own label, lane SRV-4).
        assert order.source == "asset_age_rule"
        assert str(order.rule_id) == str(rule["id"])
        # `Work-007` prints this after *Raised by:* — the rule's NAME, because
        # B14 rule 31 forbids an internal id being the visible value of a field.
        assert order.source_ref == "Asset age rule"
        # BR-WRK-006 — the anchor is the meter the rule fired on.
        assert str(order.asset_id) == str(asset["id"])


# ── TC-4 · one utility's rule never reads another's meters ─────────────────
@pytest.mark.django_db
def test_tc4_lone_stars_assets_raise_nothing_on_brazos_bend(dana, brazos, erin, lonestar):
    with tenant_ctx(lonestar):
        # Lone Star Ridge sells WATER ONLY — a meter created as `electric` is
        # refused by `assets.service_not_enabled` before this case can begin,
        # which is a different rule doing its job and not this one's subject.
        _aged_meter(erin, asset_no="AST-09001", due=YESTERDAY, service="water")

    with tenant_ctx(brazos):
        template = _published_template(dana)
        rule = _asset_age_rule(dana, template["id"])
        result = rules.sweep(dana)

        # Brazos Bend has no aged meter of its own, and Lone Star Ridge's is not
        # visible to it. A sweep that read across the boundary would raise a job
        # against another utility's meter — and dispatch a crew to it.
        assert result["raised"] == 0
        assert result["rules"][0]["subjects"] == 0

    # ⚠ **WHETHER LONE STAR RIDGE CAN *READ* BRAZOS BEND'S RULE ROW IS NOT
    # ASSERTED HERE, AND THAT IS DELIBERATE RATHER THAN A GAP.** A first draft
    # ended with `WorkOrderRule.objects.filter(pk=rule["id"]).count() == 0`
    # under Lone Star's context and it FAILED — correctly. SQLite has no
    # row-level security at all, so a bare queryset sees every row whatever
    # `app.tenant_id` says, and the only honest place for that claim is
    # `tests/test_us_wrk_037_rules_pg.py`, which runs on real PostgreSQL as a
    # NOSUPERUSER role. Asserting it here would have meant either a green that
    # proves nothing or a red that never goes away.
    #
    # What IS proved above is the thing this case is for and it needs no RLS:
    # the sweep, running as Brazos Bend, found NO subjects — Lone Star's aged
    # meter is not in its reader's answer — so no job was raised against
    # another utility's meter and no crew was sent to its address.
    assert str(rule["id"])


# ── TC-5 · five readers, five modules, all through seams ──────────────────
def test_tc5_every_trigger_has_a_reader_and_names_its_own_module():
    model = work_models.WorkOrderRule
    # A trigger with a reader and no module — or a module with no reader — is a
    # rule that saves and never fires, and nothing on screen would show it.
    assert set(rules.TRIGGER_READERS) == set(model.TRIGGER_MODULE)
    assert set(model.TRIGGER_MODULE.values()) == set(model.SOURCE_MODULES)
    assert len(model.SOURCE_MODULES) == 5


def test_tc5b_every_reader_reads_through_a_seam_and_imports_no_foreign_model():
    """`BR-WRK-002` at the file level, asserted here as well as by G78.

    G78 fails the merge on a foreign models import outside `seams/`. This case
    states the same rule from the other side — that `rules.py` itself names only
    seam modules — so a lane reading this file learns the constraint without
    having to run the gate.
    """
    import ast
    import pathlib

    source = pathlib.Path(rules.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    foreign = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("apps."):
            if not (node.module or "").startswith(("apps.work.seams", "apps.work")):
                foreign.append(node.module)
    assert foreign == [], f"rules.py imports another module directly: {foreign}"


# ── TC-6 · the beat entry, and the job's queue ─────────────────────────────
def test_tc6_the_sweep_has_a_beat_entry_and_rides_the_work_queue():
    entry = rules.beat_schedule()
    assert rules.BEAT_ENTRY in entry
    assert entry[rules.BEAT_ENTRY]["task"] == rules.SWEEP_TASK
    assert entry[rules.BEAT_ENTRY]["schedule"] == float(rules.SWEEP_EVERY_SECONDS)


def test_tc6b_ready_installs_the_entry_on_the_celery_app():
    """The schedule being CORRECT and the schedule being INSTALLED are two
    different claims (hard-won law 2), so this asserts the second one.

    PROVED RED FIRST (law 7): with `rules.install()` removed from
    `WorkConfig.ready()`, this read `KeyError: 'work.rules_sweep'` — the entry
    was absent from `app.conf.beat_schedule` while `beat_schedule()` above still
    returned it perfectly.
    """
    from config.celery import app as celery_app

    installed = dict(getattr(celery_app.conf, "beat_schedule", None) or {})
    assert rules.BEAT_ENTRY in installed, (
        "the nightly sweep has no beat entry — `WorkConfig.ready()` did not "
        "call `rules.install()`, so nothing fires it and every rule is inert"
    )
    assert installed[rules.BEAT_ENTRY]["task"] == rules.SWEEP_TASK


def test_tc6c_the_job_kind_is_routed_to_the_work_queue():
    from core import jobs as core_jobs

    assert core_jobs.job_queue(rules.RULES_SWEEP_JOB) == rules.WORK_QUEUE


# ── TC-7 · `Work-026`'s THIS MONTH column ─────────────────────────────────
@pytest.mark.django_db
def test_tc7_the_list_shows_this_months_count_and_survives_a_purged_order(dana, brazos):
    with tenant_ctx(brazos):
        template = _published_template(dana)
        for n in (1, 2):
            _aged_meter(dana, asset_no=f"AST-0442{n}", due=YESTERDAY)
        rule = _asset_age_rule(dana, template["id"])
        rules.sweep(dana)

        page = rules.rules_page()
        assert page["total"] == 1
        row = page["rows"][0]
        assert row["name"] == "Asset age rule"
        assert row["this_month"] == 2
        assert row["template"]["name"] == "Meter exchange"
        assert row["enabled"] is True

        # ⚠ THE COUNT IS THE SWEEP'S MEMORY, NOT THE ORDERS. A utility that
        # purges closed jobs must still see a truthful figure — which is the
        # reason `work_order_rule_raises` exists at all.
        work_tables.WorkOrder.objects.filter(rule_id=rule["id"]).delete()
        assert rules.rules_page()["rows"][0]["this_month"] == 2


@pytest.mark.django_db
def test_tc7b_a_rule_with_an_unknown_trigger_is_refused_at_the_door(dana, brazos):
    """Refused when a person is present to read the message, never ignored at
    02:00 — see `rules._clean_rule`."""
    from core import errors

    with tenant_ctx(brazos):
        template = _published_template(dana)
        with pytest.raises(errors.ValidationError):
            rules.create_rule(
                dana,
                {
                    "name": "Nonsense",
                    "source_module": "assets",
                    "trigger_kind": "the_moon_is_full",
                    "template_id": template["id"],
                },
            )
        # And a trigger that exists but belongs to another module is refused
        # too: a rule reported under the wrong source would attribute THIS
        # MONTH to the wrong module for ever.
        with pytest.raises(errors.ValidationError):
            rules.create_rule(
                dana,
                {
                    "name": "Mismatched",
                    "source_module": "assets",
                    "trigger_kind": work_models.WorkOrderRule.TRIGGER_CONTINUOUS_FLOW,
                    "template_id": template["id"],
                },
            )
