# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-BIL-5255` (screen 16's DEFAULTS group and the run label) +
#           `CR-105-BRC03` (the bill template is decided at step 1 Scope).
#           Screens: S31 step 1 — the blueprint's screen 16 `Scope`, p046-p048
# Rules:    BR-BIL-1040 (the run's standing answers, resolved at creation from
#           the clerk's choice or the tenant's own S66 setting — never a
#           literal) · BR-BIL-1041 (the template is CHOSEN at Scope; its
#           version is still PINNED at issue) · BR-BIL-015 (a missing read is a
#           per-case staff choice — NOT replaced) · BR-BIL-026 (template +
#           version pinned at issue and frozen) · BR-BIL-005 (a run is
#           idempotent on tenant + cycle + period) · CLAUDE.md rule 4
# ───────────────────────────────────────────────────────
"""BR-BIL-1040 / BR-BIL-1041 — what a run decides ONCE, and what it must not.

⚠ **PROVE THIS FILE ON REAL POSTGRESQL.** `config/settings/test.py` hardcodes
in-memory SQLite (CLAUDE.md hard-won law 14), and two of the cases below turn on
behaviour SQLite does not have: a refused insert inside `create_run`'s
`transaction.atomic()`, and a `jsonb` column round-tripping a dict. Run it as

    DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=... pytest <this>

**THE MIRROR TEST IS THE POINT OF THE FIRST CASE.** `apps/tenancy` may not
import `apps/billing`, so the three choice tuples on S66 are MIRRORED from
`decisions.CHOICES_BY_CASE` — the `ALLOCATION_CLASS_SEQUENCE` precedent. A copy
nobody compares is how a case comes to mean two things: the tenant's screen
offering a word the engine refuses, or the engine accepting one the screen never
shows. This asserts the copies are EQUAL, so the drift goes red here rather than
in a clerk's browser.

**AND THE `no hardcoding` TEST IS THE SECOND** (PO instruction 2026-09-14). A
run created with nothing chosen must come out carrying the TENANT's three
values, not a literal typed into billing — so the case that matters moves the
tenant's setting and requires the next run to follow it.
"""

from datetime import date

import pytest

from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.billing import settings_seam as billing_settings_seam
from apps.billing import templates_service
from apps.billing.decisions import CHOICES_BY_CASE
from apps.billing.exceptions import BillingRuleError
from apps.billing.template_models import BillTemplate, BillTemplateVersion
from apps.metering import models as metering_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from apps.tenancy import settings_families
from core import errors as core_errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

PERIOD = (date(2026, 6, 1), date(2026, 6, 30))

#: The blueprint's three drawn values (p047), as the engine spells them.
#: `Estimate from history` · `Hold it for review` · `Pro-rate by days`.
DRAWN_DEFAULTS = {
    "missing_read": "estimate",
    "high_usage": "investigate",
    "days_threshold": "prorate_to_cycle_days",
}


def _cycle(tenant, code="06-A"):
    return metering_models.Cycle.objects.create(
        tenant=tenant, code=code, due_days=21, bill_day=5, start_day=1, days_to_complete=5
    )


def _published_template(tenant, *, name="Standard bill"):
    template = BillTemplate.objects.create(tenant=tenant, name=name, template_type="bill")
    BillTemplateVersion.objects.create(
        tenant=tenant,
        template=template,
        version_no=1,
        status=templates_service.VERSION_PUBLISHED,
        layout_key=templates_service.SEED_LAYOUT_KEY,
    )
    return template


# ═══════════════════════════════════════════════════════════════════════════
# BR-BIL-1040 · ONE VOCABULARY, MIRRORED AND COMPARED
# ═══════════════════════════════════════════════════════════════════════════
def test_the_s66_choice_tuples_are_billings_own_vocabulary_not_a_second_copy():
    """tenancy mirrors; this is the comparison that keeps the copies one fact."""
    assert settings_families.RUN_MISSING_READ_CHOICES == CHOICES_BY_CASE["missing_read"]
    assert settings_families.RUN_HIGH_USAGE_CHOICES == CHOICES_BY_CASE["high_usage"]
    assert settings_families.RUN_DAYS_THRESHOLD_CHOICES == CHOICES_BY_CASE["days_threshold"]


def test_the_three_seeded_values_are_the_three_the_blueprint_draws(brazos):
    """p047 draws `Estimate from history`, `Hold it for review`, `Pro-rate by
    days`. A tenant that has touched nothing opens the controls on exactly
    those — and they arrive from tenancy's seeded Params, not from billing."""
    with tenant_ctx(brazos):
        assert billing_settings_seam.run_case_defaults() == DRAWN_DEFAULTS


# ═══════════════════════════════════════════════════════════════════════════
# BR-BIL-1040 · WHAT A RUN STORES
# ═══════════════════════════════════════════════════════════════════════════
def test_a_run_with_nothing_chosen_stores_the_tenants_three_values(brazos, dana):
    with tenant_ctx(brazos):
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos).id, period_start=PERIOD[0], period_end=PERIOD[1]
        )
        run.refresh_from_db()
        assert run.case_defaults == DRAWN_DEFAULTS


def test_no_hardcoding__moving_the_tenant_setting_moves_the_next_runs_defaults(brazos, dana):
    """PO 2026-09-14, *"no hardcoding"*. A utility that would rather HOLD an
    account with no reading than estimate it says so once on Settings, and the
    next run carries `hold` — with the other two untouched."""
    with tenant_ctx(brazos):
        tenancy_services.save_settings_family(
            dana, "billing-defaults", {"run_default_missing_read": "hold"}
        )
        assert tenancy_selectors.settings_family("billing-defaults")["run_default_missing_read"] == "hold"
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-B").id, period_start=PERIOD[0], period_end=PERIOD[1]
        )
        run.refresh_from_db()
        assert run.case_defaults["missing_read"] == "hold"
        assert run.case_defaults["high_usage"] == "investigate"
        assert run.case_defaults["days_threshold"] == "prorate_to_cycle_days"


def test_what_the_clerk_left_a_control_at_wins_over_the_tenant_setting(brazos, dana):
    with tenant_ctx(brazos):
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-C").id,
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            case_defaults={"high_usage": "bill_as_is"},
        )
        run.refresh_from_db()
        assert run.case_defaults["high_usage"] == "bill_as_is"
        # the two the clerk did not touch still come from the tenant
        assert run.case_defaults["missing_read"] == "estimate"


def test_a_run_already_created_does_not_move_when_the_setting_moves(brazos, dana):
    """The freeze argument, in miniature. A tenant editing Settings between
    Scope and Check must not change what a run in flight decided — the same
    hazard BR-BIL-026 freezes the template against."""
    with tenant_ctx(brazos):
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-D").id, period_start=PERIOD[0], period_end=PERIOD[1]
        )
        tenancy_services.save_settings_family(
            dana, "billing-defaults", {"run_default_missing_read": "bill_without_service"}
        )
        run.refresh_from_db()
        assert run.case_defaults["missing_read"] == "estimate"


# ═══════════════════════════════════════════════════════════════════════════
# BR-BIL-1040 · THE TWO REFUSALS, AND NEITHER LEAVES A ROW
# ═══════════════════════════════════════════════════════════════════════════
def test_a_case_kind_the_engine_does_not_raise_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "06-E")
        with pytest.raises(BillingRuleError) as refused:
            billing_runs.create_run(
                cycle_id=cycle.id,
                period_start=PERIOD[0],
                period_end=PERIOD[1],
                case_defaults={"unusually_purple": "estimate"},
            )
        assert "unusually_purple" in str(refused.value)
        assert not billing_models.BillRun.objects.filter(cycle=cycle).exists()


def test_a_choice_outside_the_cases_own_vocabulary_is_refused_by_name(brazos, dana):
    """`estimate` is a real choice — on `missing_read`, not on `high_usage`.
    A run default the case does not offer would be recorded here and refused
    per account at prepare time: a decision a clerk made and the run dropped."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "06-F")
        with pytest.raises(BillingRuleError) as refused:
            billing_runs.create_run(
                cycle_id=cycle.id,
                period_start=PERIOD[0],
                period_end=PERIOD[1],
                case_defaults={"high_usage": "estimate"},
            )
        assert "bill_as_is" in str(refused.value)
        assert not billing_models.BillRun.objects.filter(cycle=cycle).exists()


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-BIL-5255` ④ · THE LABEL
# ═══════════════════════════════════════════════════════════════════════════
def test_the_label_is_stored_as_the_clerk_typed_it(brazos, dana):
    with tenant_ctx(brazos):
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-G").id,
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            label="September, after the water rate change",
        )
        run.refresh_from_db()
        assert run.label == "September, after the water rate change"


def test_a_blank_label_is_nobody_typed_one_and_is_null(brazos, dana):
    with tenant_ctx(brazos):
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-H").id,
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            label="   ",
        )
        run.refresh_from_db()
        assert run.label is None


def test_two_runs_over_one_cycle_may_carry_the_same_label(brazos, dana):
    """Not unique, deliberately: a uniqueness rule on a human's note would
    refuse a run for a reason that is not about billing."""
    with tenant_ctx(brazos):
        for code in ("06-I", "06-J"):
            billing_runs.create_run(
                cycle_id=_cycle(brazos, code).id,
                period_start=PERIOD[0],
                period_end=PERIOD[1],
                label="first attempt",
            )
        assert billing_models.BillRun.objects.filter(label="first attempt").count() == 2


# ═══════════════════════════════════════════════════════════════════════════
# BR-BIL-1041 · THE TEMPLATE CHOSEN AT SCOPE — AND THE FREEZE THAT DOES NOT MOVE
# ═══════════════════════════════════════════════════════════════════════════
def test_a_run_may_carry_no_template_and_that_is_the_ordinary_case(brazos, dana):
    """NULL is BR-BIL-025's per-account chain running exactly as it does today."""
    with tenant_ctx(brazos):
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-K").id, period_start=PERIOD[0], period_end=PERIOD[1]
        )
        run.refresh_from_db()
        assert run.template_id is None


def test_a_published_template_is_stored_as_the_runs_pin(brazos, dana):
    with tenant_ctx(brazos):
        template = _published_template(brazos, name="Rate-change letter")
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-L").id,
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            template_id=template.pk,
        )
        run.refresh_from_db()
        assert run.template_id == template.pk


def test_deciding_is_not_stamping__no_version_is_pinned_at_scope(brazos, dana):
    """⚠ The whole safety of `CR-105-BRC03`. The run carries the TEMPLATE and
    no version number, so publishing version 2 between Scope and Send changes
    nothing about what the run decided — `assemble_document` still resolves and
    freezes the version at ISSUE (BR-BIL-026)."""
    with tenant_ctx(brazos):
        template = _published_template(brazos, name="Two-version letter")
        run = billing_runs.create_run(
            cycle_id=_cycle(brazos, "06-M").id,
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            template_id=template.pk,
        )
        assert not hasattr(run, "template_version")
        assert [f.name for f in billing_models.BillRun._meta.get_fields()
                if "template" in f.name] == ["template"]


def test_a_template_with_only_a_draft_version_is_refused_at_step_one(brazos, dana):
    """The argument for the whole change. `issue.template_problems` counts the
    bills that could not resolve a template — AFTER the clerk signed off. This
    is the same refusal, at Scope, before anything was checked."""
    with tenant_ctx(brazos):
        draft_only = BillTemplate.objects.create(
            tenant=brazos, name="Draft only", template_type="bill"
        )
        BillTemplateVersion.objects.create(
            tenant=brazos,
            template=draft_only,
            version_no=1,
            status=templates_service.VERSION_DRAFT,
            layout_key=templates_service.SEED_LAYOUT_KEY,
        )
        cycle = _cycle(brazos, "06-N")
        with pytest.raises(BillingRuleError) as refused:
            billing_runs.create_run(
                cycle_id=cycle.id,
                period_start=PERIOD[0],
                period_end=PERIOD[1],
                template_id=draft_only.pk,
            )
        assert "PUBLISHED" in str(refused.value)
        assert not billing_models.BillRun.objects.filter(cycle=cycle).exists()


def test_a_template_that_is_not_this_tenants_is_absent_not_refused(brazos, dana):
    """HR-1: unknown, malformed and cross-tenant are ONE answer, so existence
    cannot be probed — the posture the cycle check beside it already takes."""
    import uuid

    with tenant_ctx(brazos):
        cycle = _cycle(brazos, "06-O")
        with pytest.raises(core_errors.NotFoundError):
            billing_runs.create_run(
                cycle_id=cycle.id,
                period_start=PERIOD[0],
                period_end=PERIOD[1],
                template_id=uuid.uuid4(),
            )
        assert not billing_models.BillRun.objects.filter(cycle=cycle).exists()


# ═══════════════════════════════════════════════════════════════════════════
# CLAUDE.md RULE 4 · NOTHING ALREADY ISSUED MOVES
# ═══════════════════════════════════════════════════════════════════════════
def test_a_run_that_predates_the_columns_reads_null_on_all_three(brazos):
    """The migration adds no default and backfills nothing. A row written the
    way every run was written before it carries NULL, and NULL is a fact."""
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=_cycle(brazos, "06-P"),
            period_start=PERIOD[0],
            period_end=PERIOD[1],
            status="draft",
            idempotency_key="pre-0028",
        )
        run.refresh_from_db()
        assert run.case_defaults is None
        assert run.label is None
        assert run.template_id is None
