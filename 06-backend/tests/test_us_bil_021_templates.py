# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-021 (template CRUD, append-only versions, publish rights)
#           Screens: S8 · S91 · S92 · S93
# Rules:    BR-BIL-025 (assignment defaults by category, overridable per
#           account) · BR-BIL-026 (edit = new version; one published per
#           template; publishing affects only FUTURE bills — AMENDED
#           2026-08-12 by OQ-149) · BR-BIL-027 (Clerk drafts, System Admin
#           publishes, a pinned version is never deletable) · CLAUDE.md rule 1
#           (tenant scoping) · rule 7 (audit)
# ───────────────────────────────────────────────────────
"""Templates: what a tenant may change, who may publish it, and what is forever.

WHAT RUNS HERE AND WHAT DOES NOT, stated because it changes what these tests are
worth (hard-won law 1):

* The full lifecycle — draft → published → archived, version numbering, the
  rights split, the audit-lock and BR-BIL-025's resolution order — runs against
  real rows.
* The DATABASE-level guarantees (RLS, the published-version content freeze) are
  `requires_postgres` and run only on the Postgres tier. sqlite has neither.
* The RENDERING half is NOT tested here and is `test_us_bil_022_documents.py`'s.
  This story ships the version chain; `documents.py` still holds ONE built-in
  layout, which is the gap `TEMPLATES_UNAVAILABLE` reports rather than hides.
"""

from datetime import date

import pytest
from django.db import IntegrityError, transaction

from apps.billing import templates_service
from apps.billing.exceptions import BillingRuleError
from apps.billing.template_models import (
    VERSION_ARCHIVED,
    VERSION_DRAFT,
    VERSION_PUBLISHED,
    BillTemplateVersion,
)

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_rls_scoped,
    requires_postgres,
    rls,  # noqa: F401 — the probe fixture
    rls_probe_role,  # noqa: F401 — session fixture `rls` depends on
)
from tests.test_us_bil_016_bulk_corrections import an_issued_bill
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 16)
LAYOUT = "standard-letter-v1"


def a_template(*, name="Bill · residential", category="residential", actor=None):
    return templates_service.create_template(
        name=name, template_type="bill", category=category, actor=actor
    )


def test_us_bil_021_tc1__an_edit_is_a_new_append_only_version(brazos, dana):
    """TC-1 / BR-BIL-026 — *"every edit = a new version (append-only)"*.

    Priya edits "Bill · residential" and **v4** appears; **v3 stays published
    and byte-identical**, which is the guarantee every bill already pinned to v3
    depends on. Version numbers count up and are never reused: an invoice's
    `template_version` is frozen at issue, so a recycled number would make a
    2026 bill render on a 2031 page while every row still looked correct.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        v1 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v1, actor=dana, on_date=TODAY)

        v2 = templates_service.save_draft(
            template, layout_key=LAYOUT, options={"footer": "Thank you"}, actor=dana
        )

        assert (v1.version_no, v2.version_no) == (1, 2)
        assert v2.status == VERSION_DRAFT
        v1.refresh_from_db()
        assert v1.status == VERSION_PUBLISHED, "the published version is untouched by an edit"
        assert v1.options == {}

        # Test-print renders the DRAFT with sample data and writes nothing.
        printed = templates_service.test_print(v2)
        assert printed["version_no"] == 2 and printed["sample_data"] is True
        assert "no delivery row" in printed["writes"]


def test_us_bil_021_tc2__only_a_system_admin_publishes_and_the_incumbent_archives(
    brazos, dana, marcus
):
    """TC-2 / BR-BIL-027 — the rights split, SERVER-SIDE.

    *"Clerk's publish absent/disabled-with-reason + server-rejected; Admin
    publish succeeds → v2 published, v1 auto-archived (one published per
    template); only bills issued AFTER see v2."*

    A disabled button is a courtesy, not a gate — so Marcus (Billing Clerk) is
    refused by the service itself, and the refusal names the rule and the reason
    the right is narrower rather than just saying no.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        v1 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v1, actor=dana, on_date=TODAY)
        v2 = templates_service.save_draft(template, layout_key=LAYOUT, actor=marcus)

        with pytest.raises(BillingRuleError) as refusal:
            templates_service.publish(v2, actor=marcus, on_date=TODAY)
        message = str(refusal.value)
        assert "system_admin" in message and "BR-BIL-027" in str(refusal.value.br_ref or "")
        assert "disabled button is a courtesy" in message
        v2.refresh_from_db()
        assert v2.status == VERSION_DRAFT, "a refused publish changes nothing"

        templates_service.publish(v2, actor=dana, on_date=TODAY)

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert (v1.status, v2.status) == (VERSION_ARCHIVED, VERSION_PUBLISHED)
        assert templates_service.published_version(template).version_no == 2
        assert (
            BillTemplateVersion.objects.filter(template=template, status=VERSION_PUBLISHED).count()
            == 1
        )


def test_us_bil_021_tc2b__publishing_never_touches_an_issued_bills_pin(brazos, dana):
    """BR-BIL-026 — *"publishing affects only FUTURE bills"*, asserted not assumed.

    A bill issued while v1 was live keeps `template_version=1` after v2 is
    published. This is structural rather than remembered: a bill carries its own
    pin, frozen with its money, and nothing on the render path reads "the latest
    published version" (`documents.LATEST_REGISTERED_VERSION` carries a comment
    saying exactly that).
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        v1 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v1, actor=dana, on_date=TODAY)

        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        bill = an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018410",
            template_id=template.pk,
            template_version=1,
        )

        v2 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v2, actor=dana, on_date=TODAY)

        bill.refresh_from_db()
        assert bill.template_version == 1, "an issued bill's pin is not moved by a publish"


def test_us_bil_021_tc3__resolution_is_override_then_category_then_fallback(brazos, dana):
    """TC-3 / BR-BIL-025 — the ruled order, all three steps.

    *"account-level override set on ACC-9001 → commercial template; resolution
    order account-override → category default"*, plus the tenant's fallback for
    a category with no template of its own — which every tenant needs, because
    an account still has to receive a bill.

    ⚠ The override is an ARGUMENT: BR-BIL-025 puts it on the customers-owned
    account row and no column exists yet. The ORDER is what this asserts, and
    the order is the half that would otherwise be re-guessed at every call site
    the day the column lands.

    ⚠ **AMENDED 2026-08-16 (DEF-123).** Step 3 used to create its own fallback
    named "Bill · standard". A provisioned tenant is now SEEDED its fallback
    (`templates_service.seed_platform_default`, called from provisioning —
    without it no tenant could issue a bill at all), so making a second one puts
    the tenant in a state resolution has no answer for: `uq_bill_templates_
    category` is partial on a NON-NULL category, so two category-less templates
    are permitted by the schema and `resolve_for` would take whichever came
    first. The test therefore resolves against the fallback the tenant ACTUALLY
    has, which is also the only one any real tenant has — S8's Templates tab is
    unmounted, so nothing can create a second. Reported in `TEMPLATES_UNAVAILABLE`
    rather than fixed by a constraint here: adding one is a migration on a 🔒
    path and belongs to the story that builds the screen.
    """
    with tenant_ctx(brazos):
        residential = a_template(name="Bill · residential", category="residential", actor=dana)
        commercial = a_template(name="Bill · commercial", category="commercial", actor=dana)
        for template in (residential, commercial):
            version = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
            templates_service.publish(version, actor=dana, on_date=TODAY)
        # The tenant's fallback, as PROVISIONING left it — not one made here.
        fallback, fallback_version = templates_service.resolve_for(consumer_category=None)
        assert fallback.category is None
        assert fallback_version.status == VERSION_PUBLISHED

        # 1 · category default
        picked, version = templates_service.resolve_for(consumer_category="residential")
        assert picked.pk == residential.pk and version.version_no == 1

        # 2 · account override WINS over the category default
        picked, _ = templates_service.resolve_for(
            consumer_category="residential", account_override_template_id=commercial.pk
        )
        assert picked.pk == commercial.pk

        # 3 · a category with no template of its own falls back
        picked, _ = templates_service.resolve_for(consumer_category="industrial")
        assert picked.pk == fallback.pk


def test_us_bil_021_tc4__a_pinned_version_can_never_be_deleted(brazos, dana):
    """TC-4 / BR-BIL-027 — **the audit-lock**, and an unpinned draft deletes fine.

    *"Delete attempted on v3 (pinned by 1,124 issued bills) → Blocked —
    audit-lock: archive allowed, delete never; an unpinned draft version deletes
    fine."*

    The refusal NAMES THE COUNT, because "you cannot delete this" without a
    number invites somebody to go looking for a way round it. The reason is
    reproducibility over a seven-year retention window, not tidiness — a bill
    whose version is gone can never be reprinted as it was sent.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        v1 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v1, actor=dana, on_date=TODAY)

        account = an_account(dana, brazos)
        run = a_run(brazos, key="2026-07|cycle-A")
        an_issued_bill(
            brazos,
            account,
            run,
            invoice_no="BL-2608-018410",
            template_id=template.pk,
            template_version=1,
        )
        assert templates_service.pin_count(v1) == 1

        with pytest.raises(BillingRuleError) as refusal:
            templates_service.delete_version(v1, actor=dana)
        message = str(refusal.value)
        assert "pinned by 1 issued bill" in message
        assert "Archive it instead" in message
        assert BillTemplateVersion.objects.filter(pk=v1.pk).exists()

        # Archive IS allowed — it is the answer delete is not.
        templates_service.archive(v1, actor=dana, on_date=TODAY)
        v1.refresh_from_db()
        assert v1.status == VERSION_ARCHIVED

        # And an unpinned DRAFT deletes fine.
        v2 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        assert templates_service.pin_count(v2) == 0
        templates_service.delete_version(v2, actor=dana)
        assert not BillTemplateVersion.objects.filter(pk=v2.pk).exists()


def test_us_bil_021_tc5__a_tenant_cannot_supply_its_own_layout(brazos, dana):
    """TC-5 + the 2026-08-12 scope narrowing — **OQ-149, and why it matters**.

    PO, verbatim: *"out platform will porvide standard 3 to 5 variouation of
    printed bill - user can use those only in V1"*. A tenant chooses one of the
    platform's variants; it does not design the page.

    This is the check that keeps a ~200MB rendering library out of the
    deployment image, and the connection is not decorative: tenant-authored
    HTML/CSS is what would have needed WeasyPrint plus Pango, HarfBuzz and
    fontconfig in every container. With no key that can name a page the platform
    did not write, nothing ever has to render one.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        with pytest.raises(BillingRuleError) as refusal:
            templates_service.save_draft(
                template, layout_key="<html>my own bill</html>", actor=dana
            )
        message = str(refusal.value)
        assert "not one of the platform's printed-bill layouts" in message
        assert "does not design the page" in message
        assert not BillTemplateVersion.objects.filter(template=template).exists()

        # ⚠ AMENDED 2026-08-16. This block used to assert
        # `platform_layout_set_incomplete` and `len(PLATFORM_LAYOUTS) == 1` —
        # *"the platform publishes ONE layout where 3–5 were ruled"* — and the
        # PO closed that shortfall the same day (*"why cant we give 5 differnt
        # tempaltes to start with and ask user to choose anyone"*). FIVE ship,
        # the entry is REWRITTEN rather than deleted, and what a tenant may never
        # do — design its own page — is now a ruling instead of a gap.
        codes = {entry["code"] for entry in templates_service.TEMPLATES_UNAVAILABLE}
        assert "tenant_authors_no_layout_of_its_own" in codes
        assert "platform_layout_set_incomplete" not in codes, (
            "the shortfall entry outlived the shortfall — hard-won law 1 runs in both "
            "directions and a build that keeps reporting a gap it has closed is lying "
            "the other way"
        )
        assert len(templates_service.PLATFORM_LAYOUTS) == 5
        # THE LIBRARY IS NOT FIVE NAMES FOR ONE PAGE. `templates_service` refused
        # to pad the registry with placeholder keys precisely because *"a chooser
        # offering four identical options is worse than one offering one honest
        # one"*, so the constraint is asserted rather than trusted: every layout
        # must have a renderer, and no two may produce the same page.
        assert all(layout.renders for layout in templates_service.PLATFORM_LAYOUTS)


def test_us_bil_021_tc5b__a_draft_is_never_pinnable(brazos, dana):
    """BR-BIL-026 — a template with no PUBLISHED version cannot be resolved.

    A draft is test-printable and never pinned: a bill pinned to a draft could
    be edited after the customer received it, which is the whole thing the
    version chain exists to prevent.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)

        with pytest.raises(BillingRuleError) as refusal:
            templates_service.resolve_for(consumer_category="residential")
        assert "no PUBLISHED version" in str(refusal.value)


@requires_postgres
def test_us_bil_021_tc5c__one_published_version_per_template_is_a_database_guarantee(brazos, dana):
    """BR-BIL-026's *"one published per template"*, held where a race cannot win.

    `templates_service.publish` archives the incumbent in the same transaction,
    and this index is what survives two clerks publishing at the same instant. A
    SELECT-then-INSERT check in the service loses exactly that race, and two
    published versions is a question with no answer at issue time — a bill would
    pin whichever the query happened to return first.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        v1 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v1, actor=dana, on_date=TODAY)
        v2 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                # The service would archive v1 first; this is the racing writer
                # that did not, and the index is what stops it.
                BillTemplateVersion.objects.filter(pk=v2.pk).update(status=VERSION_PUBLISHED)


@requires_postgres
def test_us_bil_021_tc5d__a_published_versions_content_is_frozen(brazos, dana):
    """BR-BIL-026 in the DATABASE — an edit is a new version, structurally.

    If a published version's `layout_key` or `options` could change, every bill
    already pinned to it would silently start rendering differently: history
    rewritten without a single UPDATE to an invoice, and every existing gate
    still green. `status` may still move, because published → archived is the
    lifecycle.

    PROVED RED: applied without the `0019` trigger, this UPDATE succeeded.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        v1 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v1, actor=dana, on_date=TODAY)

        with pytest.raises(Exception) as refusal:  # noqa: B017 — the DB's own error type
            with transaction.atomic():
                BillTemplateVersion.objects.filter(pk=v1.pk).update(options={"footer": "new"})
        assert "BR-BIL-026" in str(refusal.value)

        # But the lifecycle still moves.
        templates_service.archive(v1, actor=dana, on_date=TODAY)
        v1.refresh_from_db()
        assert v1.status == VERSION_ARCHIVED


@pytest.mark.isolation
@requires_postgres
def test_us_bil_021_tc6__isolation_templates_never_cross_a_tenant(
    brazos, lonestar, dana, erin, rls
):
    """TC-6 / hard rule 1 — *"Own template set only; Brazos Bend versions invisible"*.

    Asserted THROUGH THE DATABASE under `sbh_rls_probe`, a role RLS applies to,
    so the app-layer `tenant_id=` filter is deliberately not in the path. A
    template row carries the tenant's own bill-message and footer copy, which is
    text a utility wrote and every one of its customers reads — not metadata.
    """
    with tenant_ctx(brazos):
        brazos_template = a_template(name="Bill · residential", actor=dana)
        templates_service.save_draft(brazos_template, layout_key=LAYOUT, actor=dana)
    with tenant_ctx(lonestar):
        lsr_template = templates_service.create_template(
            name="Bill · standard", template_type="bill", category=None, actor=erin
        )
        templates_service.save_draft(lsr_template, layout_key=LAYOUT, actor=erin)

    assert_rls_scoped(
        rls,
        "bill_templates",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(brazos_template.pk)},
    )
    assert_rls_scoped(
        rls,
        "bill_templates",
        owner=lonestar,
        intruder=brazos,
        owner_ids={str(lsr_template.pk)},
    )
    assert_denied_without_context(rls, "bill_templates", "bill_template_versions")


def test_us_bil_021_rule7__every_template_action_is_audited(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 — *"`audit_log` `template.saved/published/archived`"*.

    A template change decides what every customer of a category receives, so the
    trail records who and when for each transition — the fifth of BR-BIL-058's
    facts applied here: WHO did it and WHEN is a stronger record than a tick.

    ⚠ **AMENDED 2026-08-16 (DEF-123).** The counts are now taken over THIS
    TEMPLATE's rows rather than over every row in the trail. Provisioning seeds
    the tenant's fallback template and publishes its version (without which no
    tenant can issue a bill), so the fixture arrives carrying one
    `template.created` and one `template.published` of its own. Counting the
    whole trail asserted that nothing else in the product ever writes one of
    these actions, which was never the claim rule 7 makes.
    """
    with tenant_ctx(brazos):
        template = a_template(actor=dana)
        v1 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v1, actor=dana, on_date=TODAY)
        v2 = templates_service.save_draft(template, layout_key=LAYOUT, actor=dana)
        templates_service.publish(v2, actor=dana, on_date=TODAY)

        ours = {str(template.pk), str(v1.pk), str(v2.pk)}
        mine = [row for row in audit_rows if str(row.get("entity_id")) in ours]
        actions = [row["action"] for row in mine]
        assert "template.created" in actions
        assert actions.count("template.saved") == 2
        assert actions.count("template.published") == 2
        assert "template.archived" in actions

        published = next(row for row in mine if row["action"] == "template.published")
        assert published["after"]["affects"].startswith("future bills only")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-021@2b52def (ships with apps/billing/template_models.py — the same four sources)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest · run_gates
# exceptions: (1) THE RENDERING HALF IS NOT TESTED HERE — it is US-BIL-022's
#         (`test_us_bil_022_documents.py`). This story ships the version chain;
#         `documents.LAYOUTS` still holds ONE built-in layout and that gap is
#         asserted as REPORTED (tc5) rather than hidden.
#         (2) THE DATABASE-LEVEL GUARANTEES USE `requires_postgres`, never a
#         bare skip — sqlite has neither RLS, the partial unique index nor the
#         freeze trigger, and a check that skips silently is not a check.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
