# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-006 / TC-7 — "Lone Star Ridge template list → its own
#           versions only; Brazos Bend's invisible (RLS)"   Screens: S8 · S67
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE) · rule 4 (a published body is evidence of
#           what a customer was sent — corrections are new rows) · BR-BIL-026
#           (append-only versions) · BR-BIL-027 (a pinned version is
#           audit-locked) · B2 §3 policy template · DB-1 · NFR-8 (a version is
#           retained forever) · NFR-10 (zero tolerance, release blocker)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a VENDOR
#           reason off Postgres (`requires_postgres`) — never a bare
#           `pytest.mark.skip`. sqlite has neither RLS nor triggers, so a green
#           run there would prove nothing; tests/isolation_helpers.py explains
#           the non-superuser probe role that makes the RLS half real.
# ───────────────────────────────────────────────────────
"""Tenant isolation for the template store — and the append-only law beside it.

TWO GUARANTEES, TWO MECHANISMS, ASSERTED SEPARATELY BECAUSE THEY FAIL
SEPARATELY
-------------------------------------------------------------------
**RLS** decides WHOSE rows a session may touch. These tables hold no customer's
name — they hold the utility's own letters, its regulatory footer, the terms of
its contracts. A cross-tenant READ hands one utility the drafting of another's
legal notices. A cross-tenant WRITE is worse and quieter: publish a version into
a neighbour's registry and their next disconnect notice renders a body they
never wrote, on their letterhead, with their own audit trail showing nothing but
a normal dispatch.

**The append-only trigger** (migration 0006) decides WHAT may change on a row a
session legitimately owns. US-NOT-006 TC-6 — *"Direct UPDATE of a published
version's body → Rejected"* — is asserted HERE rather than in the service suite,
because a service check leaves `.update()`, a shell and a data migration outside
it, and the trigger is the half that does not.

Both are asserted through a NON-SUPERUSER probe role, so the policies are
genuinely consulted rather than bypassed.
"""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.notifications import template_models as tm
from apps.notifications import template_service

from tests.isolation_helpers import (
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    staff_actor,
)

pytestmark = pytest.mark.django_db

DUNNING_BODY = "Hi {first_name}, {balance} is {days_late} days late. Call {support_phone}."


def _tenant_with_a_published_template(payload=None, *, body=DUNNING_BODY, email=None):
    """A tenant carrying one variant and one published version of it."""
    tenant, _ = provisioned_tenant(payload or brazosbend_payload())
    admin = staff_actor(tenant, "system_admin", email or f"admin@{tenant.subdomain}.test")
    with live_tenant_context(tenant.id):
        # DEF-207: `register` reports `(row, created)`; this fixture wants the row.
        template, _created = template_service.register(
            code="dunning", name="Dunning", actor=admin
        )
        version = template_service.save_draft(template=template, body=body, actor=admin)
        template_service.publish(version_row=version, actor=admin)
    return tenant, template, version


@pytest.mark.isolation
@requires_postgres
def test_the_template_store_is_denied_outright_with_no_tenant_context(rls):  # noqa: F811
    """Deny-by-default, not filter-by-default: with `app.tenant_id` unset the
    B2 §3 template's `::uuid` cast of '' raises and NO row is visible.

    It matters on THESE tables because their reader is a DISPATCHER — a job that
    runs outside any request and is exactly the caller that forgets to enter a
    tenant context. An unscoped template read would let one utility's letter be
    rendered into another's envelope.
    """
    _tenant_with_a_published_template()
    assert_denied_without_context(rls, "notification_templates", "notification_template_versions")


@pytest.mark.isolation
@requires_postgres
def test_us_not_006_tc7__one_tenants_templates_are_invisible_to_another(rls):  # noqa: F811
    """US-NOT-006 TC-7, verbatim: *"Lone Star Ridge template list → its own
    versions only; Brazos Bend's invisible (RLS)."*

    Proved RED by neutering `notifications/0006`'s `apply_rls` to a no-op and
    rebuilding the test database: the probe then saw both tenants' rows and this
    failed naming the leak, while the G5 catalog sweep named both tables as
    tenant-scoped with no policy at all.
    """
    brazos, bb_template, bb_version = _tenant_with_a_published_template()
    lonestar, lsr_template, lsr_version = _tenant_with_a_published_template(
        lonestarridge_payload(),
        body="Reminder: {balance} outstanding. {support_phone}",
        email="erin@lsrwater.test",
    )

    assert_rls_scoped(
        rls,
        "notification_templates",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(bb_template.id)},
    )
    assert_rls_scoped(
        rls,
        "notification_template_versions",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(bb_version.id)},
    )

    with live_tenant_context(lonestar.id):
        # ⚠ THESE TWO READ `== {str(lsr_template.id)}` AND `== {str(lsr_version.id)}`
        # AND HAD BEEN RED SINCE PROVISIONING BEGAN SEEDING TEMPLATES (DEF-2497).
        # An equality pinned the COUNT of rows a tenant has, which is
        # provisioning's business and not this case's — and provisioning now
        # seeds a template catalogue on every new utility, so a second row
        # appeared and the assertion failed on a fact about the fixture.
        # WHAT TC-7 IS ACTUALLY FOR is unchanged and is now what it asserts:
        # this utility sees ITS OWN row, and NONE of the other utility's. An
        # equality could never say the second half — it only ever said "one".
        lonestar_templates = rls.ids("notification_templates")
        lonestar_versions = rls.ids("notification_template_versions")
        assert str(lsr_template.id) in lonestar_templates
        assert str(lsr_version.id) in lonestar_versions
        assert str(bb_template.id) not in lonestar_templates, (
            "Brazos Bend's template is visible inside Lone Star Ridge's context"
        )
        assert str(bb_version.id) not in lonestar_versions, (
            "Brazos Bend's wording is visible inside Lone Star Ridge's context"
        )
        # The reading that would actually matter: one utility must never be able
        # to read the WORDS another sends its customers.
        assert rls.count("notification_template_versions", "body LIKE %s", ["%days late%"]) == 0


@pytest.mark.isolation
@requires_postgres
def test_a_write_into_another_tenants_template_store_is_refused(rls):  # noqa: F811
    """The half that would do the damage. `WITH CHECK` refuses a row stamped for
    another tenant, so a caller in one tenant's context cannot plant a template —
    or a published body — inside another utility's registry.

    ⚠ THE VERSION-TABLE PROBE USES A **DRAFT** ROW ON PURPOSE, and the reason is
    worth writing down: the shared helper re-stamps `tenant_id` on a row the
    owner can see, and on a PUBLISHED version the append-only TRIGGER refuses
    first — `tenant_id` is one of the columns it freezes. The refusal is real
    and it is even stronger, but it is not the RLS one, so asserting it here
    would leave the policy itself unproven. Measured, not assumed: with a
    published row the failure read *"BR-BIL-026 / hard rule 4: template version 1
    is published — its body is append-only"* and never mentioned row-level
    security. A draft passes the trigger and lands on the policy, which is the
    thing under test.
    """
    brazos, _, _ = _tenant_with_a_published_template()
    lonestar, _, _ = _tenant_with_a_published_template(
        lonestarridge_payload(), email="erin2@lsrwater.test"
    )
    assert_write_into_other_tenant_refused(
        rls, "notification_templates", owner=brazos, intruder=lonestar
    )

    with live_tenant_context(brazos.id):
        admin = staff_actor(brazos, "system_admin", "draftprobe@brazos.test")
        template = tm.NotificationTemplate.objects.get(tenant_id=brazos.id, code="dunning")
        draft = template_service.save_draft(
            template=template, body=DUNNING_BODY + " draft", actor=admin
        )
        message = rls.refused(
            "UPDATE notification_template_versions SET tenant_id = %s WHERE id = %s",
            [str(lonestar.id), str(draft.id)],
        )
    assert "row-level security" in message, (
        "a cross-tenant write to a DRAFT version was refused, but not by the RLS "
        f"policy — {message}"
    )


@pytest.mark.isolation
@requires_postgres
def test_us_not_006_tc6__the_database_refuses_to_rewrite_a_published_body():
    """US-NOT-006 TC-6, verbatim: *"Direct UPDATE of a published version's body
    → Rejected — versions are append-only rows; edits create drafts."*

    Asserted as a RAW UPDATE, deliberately bypassing the service, because that
    is the path the service cannot guard: hard rule 4 says a rendered document
    is never rewritten, and a rule enforced only by the function people usually
    call is not enforced.

    Proved RED by neutering migration 0006's `apply_append_only` to a no-op and
    rebuilding the test database — the UPDATE then succeeded and the published
    body of a letter customers had already received silently changed.
    """
    tenant, _template, version = _tenant_with_a_published_template()
    with live_tenant_context(tenant.id):
        with pytest.raises(DatabaseError, match="append-only"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE notification_template_versions SET body = %s WHERE id = %s",
                        ["Pay us or else.", str(version.id)],
                    )
        version.refresh_from_db()
        assert version.body == DUNNING_BODY


@pytest.mark.isolation
@requires_postgres
def test_a_published_version_can_never_be_deleted_even_by_raw_sql():
    """NFR-8 (*"v2 retained FOREVER"*) and BR-BIL-027's audit-lock, enforced
    where a DELETE actually lands. The service refuses too — this is the layer
    that survives a shell, a data migration and a future endpoint.

    A DRAFT stays deletable, which is T5-02 step 4's contrast case: drafts are
    pinned by nothing and have been sent to nobody.
    """
    tenant, template, version = _tenant_with_a_published_template()
    with live_tenant_context(tenant.id):
        admin = staff_actor(tenant, "system_admin", "raw@brazos.test")
        draft = template_service.save_draft(
            template=template, body=DUNNING_BODY + " v2", actor=admin
        )
        with pytest.raises(DatabaseError, match="never be deleted"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM notification_template_versions WHERE id = %s",
                        [str(version.id)],
                    )
        assert tm.NotificationTemplateVersion.objects.filter(pk=version.pk).exists()

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM notification_template_versions WHERE id = %s", [str(draft.id)]
            )
        assert not tm.NotificationTemplateVersion.objects.filter(pk=draft.pk).exists()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-006@9a4f21c (the four US-NOT-006 sources — EP-NOT-02 §1/§3/§5 · 10-notifications/02-business-rules.md · 04-flows.md §2 · J22/T4-08/T4-09/T5-02)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — the template store)
# checklist: A✔ B✔ C✔ D=deferred(no API call — DB-tier assertions) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a live Postgres cluster — `apply_rls` neutered ⇒
#         the probe saw both tenants' rows and G5's catalog sweep named both
#         tables policy-less; `apply_append_only` neutered ⇒ a raw UPDATE
#         rewrote a PUBLISHED body and a raw DELETE removed a published version.
#         Restored: green. Verbatim transcripts in the lane report · ruff✔ black✔
# exceptions: POSTGRES ONLY, by `requires_postgres` (the vendor skipif) and never
#         a bare `pytest.mark.skip` — sqlite has neither RLS nor triggers, so a
#         green sqlite run here would prove nothing at all.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
