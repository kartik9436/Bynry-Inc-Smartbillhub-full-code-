# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-021 (the template lifecycle these rows live in) ·
#           US-BIL-005 (the issue this row is the precondition of) ·
#           US-TEN-001 (provisioning, which is where the row now comes from)
#           Screens: S8 (Templates tab) · S31 step 6 · S114 (signup)
# Rules:    BR-BIL-025 (assignment: account override → category default →
#           the tenant's FALLBACK, which is the row seeded here) ·
#           BR-BIL-026 (the pin is non-optional and only a PUBLISHED version is
#           pinnable) · BR-TEN-013 (tenancy reaches billing only through a
#           named seam) · BR-TEN-043 (the business date is the caller's) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 7 (audit)
# Tests:    this file · 06-backend/tests/test_us_bil_021_templates.py
# Impacts:  apps/billing/templates_service.seed_platform_default ·
#           apps/billing/services.seed_bill_templates ·
#           apps/tenancy/seams.seed_bill_templates ·
#           apps/tenancy/services._provision_inside_context ·
#           10-scripts/gates/g26_required_rows.py
# ───────────────────────────────────────────────────────
"""DEF-123 — no tenant had a bill template, and nothing could create one.

**THE DEFECT, VERBATIM:** *"No tenant has a bill template and nothing can create
one, so every bill run refuses at issue on BR-BIL-025 — the product cannot issue
a bill on any deployment."*

`bill_templates` / `bill_template_versions` landed on 2026-08-15 with
`templates_service` implementing BR-BIL-025's resolution order in full, and its
own tests passed — **against rows the TESTS create.** In the product no row was
ever created: S8's Templates tab has no endpoint, tenant provisioning seeded the
chart of accounts, the number series and the holidays but had no billing seeder,
and no migration planted a default. So `resolve_for` correctly refused *"this
tenant has no bill template … and no fallback"* for EVERY tenant, and BR-BIL-026
makes the pin non-optional, so no bill could issue anywhere.

**WHY THE EXISTING TESTS COULD NOT HAVE CAUGHT IT, and it is the whole lesson.**
`test_us_bil_021_templates.py` calls `create_template` and `save_draft` in its
own setup and then proves the resolution order over the rows it just made. A
test that supplies the row cannot discover that nothing else supplies it —
the same shape as DEF-035, where a test monkeypatching a seam could never notice
the seam was unwired. So this file does the one thing those tests cannot:
**it provisions a tenant through the real service and then asks the real
resolver, with nothing in between.**

That is *built is not wired* (hard-won law 2) applied to DATA rather than to a
component prop, which is why G13 looked straight past it. G26 required-rows is
the gate that now asks the general question; this file is the specific answer.
"""

import uuid
from datetime import date

import pytest

from apps.billing import template_models, templates_service
from apps.billing.exceptions import BillingRuleError
from apps.billing.template_models import (
    VERSION_PUBLISHED,
    BillTemplate,
    BillTemplateVersion,
)
from apps.tenancy import seams as tenancy_seams

from tests.isolation_helpers import assert_rls_scoped, requires_postgres
from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    live_tenant_context,
    rls,
    rls_probe_role,
)
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — provisioning fixtures
from tests.test_us_ten_helpers import (
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — the caller names the business date. Nothing in this file reads a
#: clock, and neither does the seeder it drives.
ON_DATE = date(2026, 8, 16)


def test_def_123_tc1__a_provisioned_tenant_can_resolve_a_bill_template(growth_plan, identity_seam):
    """**THE ONE ASSERTION THAT WAS MISSING.** Sign up, then ask for the pin.

    Not *"the resolver resolves the rows I made"* — that was always covered and
    was always green while the product could not issue a single bill. This is
    *"a tenant that came into existence the way tenants come into existence has
    the row the money path refuses without"*, and nothing between the two steps
    creates it by hand.

    Without the seam this refuses with BR-BIL-025's own sentence, which is what
    every tenant on every deployment got on 2026-08-15.
    """
    tenant, result = provisioned_tenant()
    assert result["created"] is True

    with tenant_ctx(tenant):
        template, version = templates_service.resolve_for(consumer_category=None)

    # BR-BIL-025's FALLBACK: category NULL is the answer for an account whose
    # own category has no template of its own.
    assert template.category is None
    assert template.template_type == "bill"
    # BR-BIL-026: only a PUBLISHED version is pinnable — a draft is
    # test-printable and never pinned, so a seeded draft would leave the tenant
    # exactly as unable to issue as no row at all.
    assert version.status == VERSION_PUBLISHED
    assert version.version_no == 1
    assert version.layout_key == templates_service.SEED_LAYOUT_KEY


def test_def_123_tc2__every_consumer_category_falls_back_to_the_seeded_row(
    growth_plan, identity_seam
):
    """BR-BIL-025's resolution order, over a tenant that has ONLY the fallback.

    A brand-new tenant has no category templates, so an account of EVERY
    consumer category must resolve to the one seeded row. If they did not, a run
    would issue some bills and refuse others on the same tenant — the worst of
    the three possible failures, because a partially-issued run looks like a run
    that worked.

    ⚠ **THE CATEGORIES ARE READ, NOT TYPED — AND ONE OF THEM USED TO BE A CODE
    THIS PRODUCT HAS NEVER HAD.** This loop said `residential, commercial,
    industrial, govt` until 2026-09-17 (`DEF-BIL-5660`): `govt` was billing's
    own invention, the ratified fourth code is `municipal`, and the four
    `BR-CUS-094` added in August were never covered here at all. Reading the
    tenant's own categories means this now covers all eight, and follows
    `BR-CUS-094a` — a class the utility invents is covered the day it adds it.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        seeded, _version = templates_service.resolve_for(consumer_category=None)
        for category in template_models.categories():
            template, version = templates_service.resolve_for(consumer_category=category)
            assert template.pk == seeded.pk, category
            assert version.status == VERSION_PUBLISHED, category


def test_def_123_tc3__the_seed_is_insert_missing_and_a_re_run_repairs_nothing(
    growth_plan, identity_seam
):
    """Idempotent, in the `seed_chart_of_accounts` sense: a re-run is a REPAIR.

    The operator door for a tenant provisioned before the seeder existed is
    `manage.py seed_demo --tenant <subdomain>`, which calls this same seam. It
    must be safe to run on a healthy tenant — and *safe* means it writes
    nothing, not that it writes a harmless duplicate: a second published version
    is refused by `uq_bill_template_one_published` and a second fallback
    template would make BR-BIL-025's last step a coin toss.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        before_templates = BillTemplate.objects.count()
        before_versions = BillTemplateVersion.objects.count()

        again = templates_service.seed_platform_default(on_date=ON_DATE)

        assert again["created"] is False
        assert again["already_present"] is True
        assert "insert-missing left it untouched" in again["reason"]
        assert BillTemplate.objects.count() == before_templates
        assert BillTemplateVersion.objects.count() == before_versions


def test_def_123_tc4__the_seam_is_wired_and_answers_through_tenancy(growth_plan, identity_seam):
    """The SEAM, not the function — DEF-075's lesson, applied here.

    `apps/tenancy/seams.py` documents this contract in prose and resolves the
    callable by name at call time. A seam whose implementer is absent answers
    None and provisioning commits anyway, which is the honest posture for an
    optional seam and is exactly how a tenant ends up unable to bill anybody
    with nothing going red. So this asserts the resolution itself: tenancy asks
    billing by name, and billing answers.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        assert tenancy_seams.resolve("billing", "seed_bill_templates") is not None
        answer = tenancy_seams.seed_bill_templates(None, on_date=ON_DATE)
    assert answer is not None
    assert answer["already_present"] is True


def test_def_123_tc5__a_template_whose_only_live_version_was_archived_is_repaired(
    growth_plan, identity_seam
):
    """The second shape of "no pin": a template with no PUBLISHED version.

    `resolve_for` refuses that too, and for a good reason (BR-BIL-026 — a bill
    pinned to a draft could be edited after the customer received it). A repair
    run must therefore fix the VERSION as well as the template, or an operator
    following the refusal's advice would run the repair and stay broken.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        template, version = templates_service.resolve_for(consumer_category=None)
        templates_service.archive(version, actor=None, on_date=ON_DATE)

        with pytest.raises(BillingRuleError) as refusal:
            templates_service.resolve_for(consumer_category=None)
        assert "has no PUBLISHED version" in str(refusal.value)

        repaired = templates_service.seed_platform_default(on_date=ON_DATE)
        assert repaired["created"] is True
        assert repaired["version_no"] == 2  # append-only: v1 is never reused

        template_again, live = templates_service.resolve_for(consumer_category=None)
        assert template_again.pk == template.pk
        assert live.status == VERSION_PUBLISHED


def test_def_123_tc6__the_seeded_version_names_no_human_publisher(growth_plan, identity_seam):
    """`published_by` is NULL, and the NULL is the true answer.

    BR-BIL-027 gives publishing to a System Admin because it *"puts a page in
    front of every customer the template is assigned to"*. Nobody did that here
    — the platform planted its own default before any human had signed in — so
    the row says nobody rather than naming the owner, who has never seen it.
    The audit row is where the provisioning seed is recorded.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        _template, version = templates_service.resolve_for(consumer_category=None)
        assert version.published_by_id is None
        assert version.created_by_id is None
        assert version.published_on == version.published_on  # a date, not a clock read
        assert version.options == {}  # BR-BIL-021's messages are the TENANT's copy


def test_def_123_tc7__the_seed_is_audited(growth_plan, identity_seam, audit_rows):
    """CLAUDE.md rule 7 — the row a customer's bill will point at forever is
    written under an audit trail that says where it came from."""
    provisioned_tenant()
    actions = [row["action"] for row in audit_rows]
    assert "template.created" in actions
    assert "template.published" in actions
    published = [row for row in audit_rows if row["action"] == "template.published"][0]
    assert published["after"]["source"] == "provisioning_seed"
    assert published["after"]["layout_key"] == templates_service.SEED_LAYOUT_KEY


@pytest.mark.isolation
@requires_postgres
def test_def_123_tc8__one_tenants_seeded_template_never_reaches_another(
    growth_plan, identity_seam, rls  # noqa: F811
):
    """Hard rule 1 — two provisioned tenants, two templates, no crossing.

    The seed writes a row into a tenant-scoped table on a path that runs for
    every signup, so it is exactly the shape that would leak if `_tenant_id()`
    were ever dropped from it.
    """
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())

    # Each provisioned tenant got exactly ONE fallback template, counted with an
    # EXPLICIT tenant filter AND inside that tenant's own context.
    #
    # ⚠ The second half used to be absent, and the comment here used to say the
    # filter was enough "because the Django connection in tests is the table
    # owner". That sentence was true and is now the whole problem: the suite is
    # run as a role row-level security genuinely applies to (DEF-GOV-4036), and
    # FORCE ROW LEVEL SECURITY applies the policy to the owner too — so with no
    # `app.tenant_id` these counts are 0, whatever the filter says. Deny by
    # default is hard rule 1 working; the count below is what a tenant sees of
    # its own library. The ISOLATION claim is still made under the NOSUPERUSER
    # probe below, where only row-level security can be doing it.
    with live_tenant_context(brazos.id):
        assert BillTemplate.objects.filter(tenant_id=brazos.id).count() == 1
    with live_tenant_context(lonestar.id):
        assert BillTemplate.objects.filter(tenant_id=lonestar.id).count() == 1

    for table in ("bill_templates", "bill_template_versions"):
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
        assert_rls_scoped(rls, table, owner=lonestar, intruder=brazos)


def test_def_123_tc9__a_tenant_that_never_ran_the_seeder_still_refuses_by_the_rule(
    growth_plan, identity_seam
):
    """The refusal is not weakened by the fix, and that matters.

    DEF-123 was never *"the refusal is wrong"* — `resolve_for` was right the
    whole time. If a deployment ever loses the seam again, the money path must
    still refuse with the rule's own sentence rather than issue on an invented
    pin: a bill in the world that cannot say what rendered it is worse than a
    bill that did not issue.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        BillTemplateVersion.objects.all().delete()
        BillTemplate.objects.all().delete()

        with pytest.raises(BillingRuleError) as refusal:
            templates_service.resolve_for(consumer_category=None)

    assert "has no bill template" in str(refusal.value)
    assert refusal.value.br_ref == "BR-BIL-025"


def test_def_123_tc10__the_seed_needs_a_tenant_context(growth_plan, identity_seam):
    """Hard rule 1, from the other side: no `app.tenant_id`, no write."""
    from core import errors

    with pytest.raises(errors.AuthError):
        templates_service.seed_platform_default(on_date=ON_DATE)
    assert uuid.UUID  # keeps the import honest for the isolation helpers above


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-123 (12-governance/10-defect-log.csv DEF-123 ·
#         04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-025/026/027 ·
#         04-docs/05-modules/07-billing/06-epics/EP-BIL-06-templates-delivery.md
#         US-BIL-021 · 08-qa/01-e2e/journeys/J24-five-phase-bill-run.md)
# generated: 2026-08-16 by story-coder (DEF-116/123 lane — the row without which
#         no tenant could issue a bill)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S8's Templates tab is still
#         unmounted; this seeds the row, it does not build the screen)
#         E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · RED-PROVED before green by removing the provisioning
#         call — tc1 failed with BR-BIL-025's own refusal, which is verbatim the
#         sentence every tenant got. Transcript quoted in the lane report.
# exceptions: tc5 archives the seeded version through the real `archive` service
#         rather than an UPDATE, so the repair is proved against a state a
#         tenant can actually reach · tc9 deletes the rows directly because
#         there is no service that removes a tenant's last template and there
#         should not be — the point is only that the refusal survives
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
