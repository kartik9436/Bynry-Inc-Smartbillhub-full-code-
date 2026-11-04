# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 / TC-7 — "Lone Star Ridge dispatch home: its own batch
#           size (500 seeded), its own provider status; Brazos Bend config
#           invisible (RLS)"   Screens: S8
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE) · B2 §3 policy template · DB-1 ·
#           BR-NOT-009 (the quiet-hours window this table stores is a
#           compliance control) · NFR-10 (zero tolerance, release blocker)
# Note:     These cases carry @pytest.mark.isolation and SKIP with a vendor
#           reason off Postgres — sqlite has no RLS, so a green run there would
#           prove nothing (tests/isolation_helpers.py explains the probe role).
# ───────────────────────────────────────────────────────
"""Tenant isolation for the dispatch config — where the WRITE side is the risk.

`outbound_messages` holds a customer's name and address per row, so a missing
policy there is a mailing list. This table holds two numbers, and its danger
runs the other way: a cross-tenant WRITE moves another utility's quiet-hours
window, and the visible consequence is a 23:00 late-payment text to THEIR
customers, from THEIR address, with nothing in their own audit trail to explain
it (T5-23's incident, caused from outside). `WITH CHECK` is what stops that, and
it is the half asserted hardest here.

Asserted through a NON-SUPERUSER probe role, so the policy is genuinely
consulted rather than bypassed.
"""

from datetime import time

import pytest

from apps.notifications import models

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


def _configured(payload=None, **overrides):
    """A tenant with a dispatch config row, edited away from the seeds.

    ⚠ **IT EDITS THE PROVISIONED ROW; IT DOES NOT CREATE ONE (2026-09-05).**
    This used to `.create()`, and all three cases here died on
    `notification_settings_tenant_id_key`. The constraint is right and the
    fixture was stale: `notification_settings` is ONE ROW PER TENANT, and
    CR-010 item 7 had provisioning write it *"so the dispatch home opens
    populated"* rather than leaving it to be created on first read. So the row
    exists before this helper runs, and inserting a second is what that unique
    index exists to refuse.

    Nobody saw it because every case here carries `requires_postgres` and the
    isolation gate ran on SQLite, where they all skipped (DEF-GOV-4024).
    """
    tenant, _ = provisioned_tenant(payload or brazosbend_payload())
    values = {"dispatch_batch_size": 200, "quiet_hours_start": time(9, 0)}
    values.update(overrides)
    with live_tenant_context(tenant.id):
        row = models.NotificationSettings.objects.get(tenant_id=tenant.id)
        for field, value in values.items():
            setattr(row, field, value)
        row.save(update_fields=list(values))
    return tenant, row


@pytest.mark.isolation
@requires_postgres
def test_the_dispatch_config_is_denied_outright_with_no_tenant_context(rls):  # noqa: F811
    """Deny-by-default, not filter-by-default: with `app.tenant_id` unset the
    B2 §3 template's `::uuid` cast of '' raises and NO row is visible.

    It matters here for the same reason it matters on the queue: the reader of
    this table is a DISPATCHER, which runs as a job outside any request and is
    exactly the caller that forgets to enter a tenant context.
    """
    _configured()
    assert_denied_without_context(rls, "notification_settings")


@pytest.mark.isolation
@requires_postgres
def test_us_not_004_tc7__one_tenants_dispatch_config_is_invisible_to_another(rls):  # noqa: F811
    """US-NOT-004 TC-7, verbatim: *"Lone Star Ridge dispatch home → its own
    batch size (500 seeded), its own provider status; Brazos Bend config
    invisible (RLS)."*

    Proved RED by neutering `notifications/0004`: the probe then saw both
    tenants' rows and this failed naming the leak.
    """
    brazos, bb_row = _configured()
    lonestar, lsr_row = _configured(
        lonestarridge_payload(), dispatch_batch_size=500, quiet_hours_start=time(8, 0)
    )

    assert_rls_scoped(
        rls,
        "notification_settings",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(bb_row.id)},
    )

    with live_tenant_context(lonestar.id):
        assert rls.count("notification_settings", "id = %s", [str(bb_row.id)]) == 0
        assert rls.ids("notification_settings") == {str(lsr_row.id)}
        # The reading that would actually matter: one tenant must never be able
        # to see — or infer — the hours another utility is allowed to send in.
        assert rls.count("notification_settings", "dispatch_batch_size = 200") == 0


@pytest.mark.isolation
@requires_postgres
def test_a_write_into_another_tenants_dispatch_config_is_refused(rls):  # noqa: F811
    """The half that would do the damage. `WITH CHECK` refuses the INSERT, so a
    caller in one tenant's context cannot plant a row — or a send window —
    inside another utility's configuration.
    """
    brazos, _ = _configured()
    lonestar, _ = _configured(lonestarridge_payload())
    assert_write_into_other_tenant_refused(
        rls, "notification_settings", owner=brazos, intruder=lonestar
    )
