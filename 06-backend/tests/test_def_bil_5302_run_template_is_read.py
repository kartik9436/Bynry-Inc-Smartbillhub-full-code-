# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-5302 — `bill_runs.template_id` is WRITTEN by `create_run`
#          (migration 0028, `validated_template_pin`) and READ BY NOBODY.
#          `api._template_pin_for` resolved from the request body, else the
#          tenant's BR-BIL-025 fallback. So a clerk picks a template at Scope,
#          we store it, and issue re-resolves from whatever the request happens
#          to carry — the pinned layout and the printed layout can differ with
#          nothing raising. And a pin that goes stale between Scope and Send is
#          discovered inside the issue loop, after the batch has started.
# Rules:   BR-BIL-026 (a bill is pinned to a PUBLISHED template version; a draft
#          is test-printable and never pinned) · BR-BIL-025 (the per-account
#          resolution chain) · BR-BIL-1041 · PO ruling 2026-09-14, verbatim:
#          *"in this step 1 scope - you will ahve to also decide on billing
#          template"* · CLAUDE.md hard-won law 2 (built is not wired — here the
#          purest form: a column with a writer and no reader)
# Impacts: 06-backend/apps/billing/api.py (`_template_pin_for`) ·
#          apps/billing/runs.py (`refuse_unresolvable_template`) ·
#          apps/billing/release.py (`authorise_release`)
# ───────────────────────────────────────────────────────
"""The template chosen at Scope is the template the bills are printed on.

⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY, asked before trusting it green
(hard-won law 7).**

  1. **The reader test passing because the body happened to carry the same
     template.** `tc1` posts NO template in the body, so the only way the pin
     can come back is off the run — and `tc2` posts a DIFFERENT one in the body
     and asserts the run's wins, which is the assertion that would go red if
     somebody "simplified" the order back.
  2. **The gate test passing because the release was refused for another
     reason** — no drafts, a missing confirmation, a stale draft. So the
     fixtures give the run a draft, all five confirmations, and no decisions,
     and `tc4` asserts the SAME run authorises cleanly once the template is
     published again. A gate that cannot pass is law 7's *incapable of passing*.
  3. **The gate refusing every run.** `tc3` asserts a run that pinned NOTHING
     authorises — null is the ordinary case and refusing it would block the
     whole product.
  4. **A refusal whose message_key does not resolve.** No key is invented here:
     `refuse_unresolvable_template` raises a plain `BillingRuleError`, which
     `_as_catalog_refusal` gives the catalogue's own `billing.run.refused`.
     `tc6` asserts the raised object carries no `message_key`, so a later lane
     that adds one has to add a catalogue entry with it (`G18`/`G32`).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import api as billing_api, models as billing_models, release, runs
from apps.billing import templates_service
from apps.billing.exceptions import BillingRuleError
from apps.billing.template_models import BillTemplate, BillTemplateVersion
from django.db.models.deletion import ProtectedError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import a_cycle

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)


def a_published_template(tenant, *, name):
    template = BillTemplate.objects.create(tenant=tenant, name=name, template_type="bill")
    BillTemplateVersion.objects.create(
        tenant=tenant,
        template=template,
        version_no=1,
        status=templates_service.VERSION_PUBLISHED,
        layout_key=templates_service.SEED_LAYOUT_KEY,
    )
    return template


def unpublish(template):
    BillTemplateVersion.objects.filter(template=template).update(
        status=templates_service.VERSION_DRAFT
    )


# ══════════════════════════════════════════════════════════════════════════
# THE READER — the column had a writer and nobody read it
# ══════════════════════════════════════════════════════════════════════════


def test_tc1__the_pin_comes_off_the_run_when_the_body_names_nothing(brazos, dana):
    """**THE DEFECT.** The body names no template, so the only honest source is
    the run's own pin — and before this change the answer was the tenant's
    fallback, whatever the clerk had chosen at Scope.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        chosen = a_published_template(brazos, name="Scope choice")
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            template_id=chosen.pk,
        )

        template_id, version_no, explicit = billing_api._template_pin_for({}, run=run)

        assert template_id == chosen.pk
        assert version_no == 1
        # EXPLICIT: a clerk chose it for the whole run, so BR-BIL-025's
        # per-account chain does not override it.
        assert explicit is True


def test_tc2__the_runs_pin_outranks_an_explicit_body_pair(brazos, dana):
    """⚠ **THE ASSERTION THAT GOES RED IF THE ORDER IS "SIMPLIFIED" BACK.**

    The body's pair is a statement about THIS REQUEST; the run's pin is a
    statement about THIS RUN, made at Scope, stored, and shown to the clerk who
    signed the release. Also hazard 1: the body names a DIFFERENT template, so
    a passing result cannot be a coincidence.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        chosen = a_published_template(brazos, name="Scope choice")
        other = a_published_template(brazos, name="Something else")
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            template_id=chosen.pk,
        )

        template_id, _version, explicit = billing_api._template_pin_for(
            {"template_id": str(other.pk), "template_version": 1}, run=run
        )

        assert template_id == chosen.pk
        assert explicit is True


def test_tc3__a_run_that_pinned_nothing_still_resolves_the_old_way(brazos, dana):
    """The ordinary case, and the one a too-eager change would break.

    `bill_runs.template_id` is nullable and null means *nobody chose one at
    Scope*. The body's pair, then the tenant's BR-BIL-025 fallback, are both
    exactly where they were — this lane NARROWED the order, it did not replace
    it.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        typed = a_published_template(brazos, name="Typed by the caller")
        run = runs.create_run(cycle_id=cycle.id, period_start=PERIOD_START, period_end=PERIOD_END)

        # Source 2 — the body, for a run that pinned nothing.
        template_id, version_no, explicit = billing_api._template_pin_for(
            {"template_id": str(typed.pk), "template_version": 7}, run=run
        )
        assert (template_id, version_no, explicit) == (str(typed.pk), 7, True)

        # Source 3 — the tenant's fallback, when nothing at all was named.
        _fallback_id, _fallback_version, fallback_explicit = billing_api._template_pin_for(
            {}, run=run
        )
        assert fallback_explicit is False


# ══════════════════════════════════════════════════════════════════════════
# THE GATE — a pin that went stale between Scope and sign-off
# ══════════════════════════════════════════════════════════════════════════


def a_draft_on(brazos, run, account):
    return billing_models.Invoice.objects.create(
        tenant=brazos,
        account=account,
        bill_run=run,
        status=billing_models.INVOICE_DRAFT,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=PERIOD_END,
        currency="USD",
        total=Decimal("108.880000"),
        subtotal=Decimal("100.000000"),
        tax_total=Decimal("8.880000"),
    )


ALL_FIVE = dict(
    compliance=True, email_mandate=True, sms_mandate=True, autopay_mandate=True, final=True
)


def sign_off(run, user):
    return release.authorise_release(
        bill_run=run,
        summary=release.summary_for(run),
        confirmations=release.Confirmations(**ALL_FIVE),
        confirmed_by=user.id,
        # A PARAMETER and never a clock read (BR-TEN-043 / G6).
        confirmed_at=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
    )


def test_tc4__an_unpublished_pin_refuses_at_the_gate_and_passes_once_republished(brazos, dana):
    """⚠ **BOTH DIRECTIONS IN ONE CASE, deliberately (hazard 2).**

    A gate that refuses and can never be satisfied is law 7's *incapable of
    passing*, and it reads exactly like the rule working. So this asserts the
    refusal AND asserts the same run signs off once the template is published
    again — nothing else about the run changes between the two.
    """
    from tests.test_us_bil_001_prepare import a_priced_plan, a_billed_unit, an_account

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5302", label="U1")
        account = an_account(brazos, unit["id"], "A-53021")
        chosen = a_published_template(brazos, name="Scope choice")
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            template_id=chosen.pk,
        )
        a_draft_on(brazos, run, account)

        # The tenant unpublishes that template between Scope and Send.
        unpublish(chosen)
        with pytest.raises(BillingRuleError) as refused:
            sign_off(run, dana.user)
        assert "no published version" in str(refused.value)
        assert refused.value.br_ref == "BR-BIL-026"

        # Published again — the SAME run, and nothing else touched.
        BillTemplateVersion.objects.filter(template=chosen).update(
            status=templates_service.VERSION_PUBLISHED
        )
        row = sign_off(run, dana.user)
        assert row.bill_run_id == run.pk


def test_tc5__a_run_that_pinned_nothing_signs_off(brazos, dana):
    """Hazard 3: the gate must not refuse the ordinary run.

    Null `template_id` is most runs in the product. If this case ever goes red
    the gate has stopped being a check and started being a wall.
    """
    from tests.test_us_bil_001_prepare import a_priced_plan, a_billed_unit, an_account

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5303", label="U1")
        account = an_account(brazos, unit["id"], "A-53022")
        run = runs.create_run(cycle_id=cycle.id, period_start=PERIOD_START, period_end=PERIOD_END)
        a_draft_on(brazos, run, account)

        assert sign_off(run, dana.user).bill_run_id == run.pk


def test_tc6__the_refusal_invents_no_message_key_and_the_missing_branch_is_defence_in_depth(
    brazos, dana
):
    """Hazard 4, and a finding worth writing down rather than hiding.

    ⚠ **NO KEY IS INVENTED.** `_as_catalog_refusal` gives an unnamed
    `BillingRuleError` the catalogue's own `billing.run.refused`, which exists
    and resolves in eleven languages. A key raised with no catalogue entry
    reaches a clerk as SILENCE — two were shipped this week and `G18`/`G32`
    caught them. Asserting the ABSENCE of a key means a later lane that adds one
    must add its catalogue entry in the same breath.

    ⚠ **AND THE `template is None` BRANCH IS UNREACHABLE FOR A RUN THAT PINS
    ONE, MEASURED RATHER THAN ASSUMED.** `BillRun.template` is `on_delete=
    PROTECT`, so the database itself refuses to delete a template a run points
    at — asserted below, because *"this branch is currently redundant"* is only
    worth saying if something proves it. It STAYS for the reason
    `record_break`'s savepoint stays: the protection is the FK's today and not
    this function's, and a data migration, a raw delete or a cross-tenant id
    would all reach it. What is actually reachable is the UNPUBLISHED case, and
    that is the one `tc4` drives end to end.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        chosen = a_published_template(brazos, name="Scope choice")
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            template_id=chosen.pk,
        )

        # The database refuses the delete — so the branch above it is depth.
        with pytest.raises(ProtectedError):
            BillTemplate.objects.filter(pk=chosen.pk).delete()

        # The reachable refusal, and it names no key of its own.
        unpublish(chosen)
        with pytest.raises(BillingRuleError) as refused:
            runs.refuse_unresolvable_template(run)
        assert "no published version" in str(refused.value)
        assert getattr(refused.value, "message_key", None) is None
        assert refused.value.br_ref == "BR-BIL-026"
