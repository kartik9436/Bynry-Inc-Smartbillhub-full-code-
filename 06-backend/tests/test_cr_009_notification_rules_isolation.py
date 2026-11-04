# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 / TC-15 — "Lone Star Ridge's notification rules with
#           Brazos Bend's app.tenant_id set → invisible"   Screens: S8
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE) · B2 §3 policy template · DB-1 ·
#           BR-NOT-017 (these rows are the ONE home of every notification rule,
#           so they govern what every customer of a utility receives) ·
#           NFR-10 (zero tolerance, release blocker)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a vendor
#           reason off Postgres — sqlite has no RLS, so a green run there would
#           prove nothing.
# ───────────────────────────────────────────────────────
"""Tenant isolation for the CR-009 rule tables — the WRITE side is the risk.

These rows hold no customer's name. What they hold is WHICH customers get
contacted and how, which makes a cross-tenant WRITE the damaging direction:
flipping another utility's `past_due_reminder` off stops every chasing letter
they send, silently, with nothing in their own audit trail to explain it — their
receivables age, their disconnect ladder never starts, and the first sign is a
month-end number nobody can account for. `WITH CHECK` is what stops that, and it
is the half asserted hardest here.

Asserted through a NON-SUPERUSER probe role, so the policy is genuinely
consulted rather than bypassed.
"""

import pytest

from apps.notifications import rule_models

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
)

pytestmark = pytest.mark.django_db


def _ruled(payload=None, *, event_key="past_due_reminder", enabled=False):
    """A tenant whose `event_key` rule has been moved off its seeded state.

    ⚠ **IT UPDATES THE SEEDED ROW; IT DOES NOT CREATE A SECOND ONE
    (2026-09-05).** This used to `.create()` a rule, and every case in this file
    then died on `uq_notification_rules_tenant_event`. The constraint is right
    and the fixture was stale: since `DEF-258`, provisioning calls
    `rule_service.seed_rules()`, which writes the WHOLE catalogue — **thirty
    events per tenant** — so that *"has this utility configured its
    notifications?"* is never answered by zero rows. A tenant therefore already
    HAS a `past_due_reminder` rule the moment it is provisioned, and a second
    one for the same event is exactly what that unique index exists to refuse.

    Nobody saw it because every case here carries `requires_postgres` and the
    isolation gate was running on SQLite, where they all skipped (DEF-GOV-4024).

    `past_due_reminder` seeds `enabled=True` (its trigger is not blocked), so
    the default `enabled=False` still moves the row off its seeded state, which
    is what the callers below rely on.
    """
    tenant, _ = provisioned_tenant(payload or brazosbend_payload())
    with live_tenant_context(tenant.id):
        row = rule_models.NotificationRule.objects.get(
            tenant_id=tenant.id, event_key=event_key
        )
        row.enabled = enabled
        row.save(update_fields=["enabled"])
    return tenant, row


@pytest.mark.isolation
@requires_postgres
def test_notification_rules_are_denied_outright_with_no_tenant_context(rls):  # noqa: F811
    """Deny-by-default, not filter-by-default. It matters here because the
    eventual reader of this table is a DISPATCHER — a job that runs outside any
    request and is exactly the caller that forgets to enter a tenant context.
    """
    _ruled()
    assert_denied_without_context(rls, "notification_rules")


@pytest.mark.isolation
@requires_postgres
def test_cr_009_tc15__one_tenants_notification_rules_are_invisible_to_another(rls):  # noqa: F811
    """US-NOT-017 TC-15."""
    brazos, bb_row = _ruled()
    lonestar, lsr_row = _ruled(lonestarridge_payload(), enabled=True)

    assert_rls_scoped(
        rls,
        "notification_rules",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(bb_row.id)},
    )

    with live_tenant_context(lonestar.id):
        assert rls.count("notification_rules", "id = %s", [str(bb_row.id)]) == 0
        # Lone Star sees its OWN rule, and NOTHING that belongs to anyone else.
        # Not "exactly one row": provisioning seeds all thirty catalogue events
        # per tenant (DEF-258), so an equality against a single id would be
        # asserting the seeding away rather than asserting isolation.
        assert str(lsr_row.id) in rls.ids("notification_rules")
        assert rls.tenant_ids("notification_rules") == {str(lonestar.id)}


@pytest.mark.isolation
@requires_postgres
def test_a_write_into_another_tenants_notification_rules_is_refused(rls):  # noqa: F811
    """The half that would do the damage — see the module docstring."""
    brazos, _ = _ruled()
    lonestar, _ = _ruled(lonestarridge_payload())
    assert_write_into_other_tenant_refused(
        rls, "notification_rules", owner=brazos, intruder=lonestar
    )


@pytest.mark.isolation
@requires_postgres
def test_the_channel_rows_carry_their_own_policy_and_not_their_parents(rls):  # noqa: F811
    """`notification_rule_channels` holds its OWN `tenant_id` and its OWN policy.

    Asserted separately because a child table protected only through its parent's
    FK is protected by a JOIN nobody wrote — and the channel row is where the
    template and the language live, which is what actually decides what a
    customer reads.
    """
    brazos, bb_rule = _ruled()
    lonestar, lsr_rule = _ruled(lonestarridge_payload())
    # The email channel of `past_due_reminder` is SEEDED, template and all
    # (`email_past_due`) — the same row this test used to create for itself,
    # which now collides with the seeding's own `get_or_create`. Reading it is
    # strictly better than writing it: the row under test is the one a real
    # tenant has.
    with live_tenant_context(brazos.id):
        bb_channel = rule_models.NotificationRuleChannel.objects.get(
            rule=bb_rule, channel="email"
        )
        assert bb_channel.template_code == "email_past_due"
    with live_tenant_context(lonestar.id):
        lsr_channel = rule_models.NotificationRuleChannel.objects.get(
            rule=lsr_rule, channel="email"
        )
        assert str(lsr_channel.id) in rls.ids("notification_rule_channels")
        assert rls.tenant_ids("notification_rule_channels") == {str(lonestar.id)}
        assert rls.count("notification_rule_channels", "id = %s", [str(bb_channel.id)]) == 0
    assert_write_into_other_tenant_refused(
        rls, "notification_rule_channels", owner=brazos, intruder=lonestar
    )
