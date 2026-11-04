# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-002 (the dispatcher's RUNNER — `manage.py dispatch_outbound`)
#           Screens: S8 · S30
# Rules:    BR-NOT-005 (one batch per channel per invocation, at the provider's
#           pace) · BR-TEN-013 (the tenant is resolved through tenancy's own
#           published selector, never by reading its ORM) · CLAUDE.md rule 1
# ───────────────────────────────────────────────────────
"""The command exists, resolves a tenant, runs a cycle, and prints the zeros.

Hard-won law 2 is why this file is here at all: a dispatcher nothing can invoke
renders nothing, passes every test and does not exist. These cases prove the
runner is REACHABLE (`call_command` finds it), that it refuses rather than
guessing when the tenant is unknown, and — the case that matters on this
deployment — that it prints the REASONS nothing was dispatched instead of an
empty success an operator would read as "the queue is clear".
"""

from __future__ import annotations

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.notifications import models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def a_queued_bill(tenant):
    with tenant_ctx(tenant):
        return models.OutboundMessage.objects.create(
            tenant_id=tenant.id,
            source_type="invoice",
            source_id=uuid.uuid4(),
            channel=models.CHANNEL_PRINT,
            template_code="bill_residential",
            template_version=3,
            recipient_address="1901 Bluestem Ln, Katy TX 77494",
        )


def test_us_not_002_tc9__the_dispatcher_is_reachable_from_a_command(brazos):
    """Hard-won law 2 — *"built is not wired"*. `dispatch_cycle` is a service
    function; this command is the only thing in the repo that calls it, and this
    case is what stops it being a feature nobody can run.

    It also asserts what the run PRINTS on this deployment: `dispatched: no`
    with the reasons, so an operator sees why nothing moved rather than reading
    silence as an empty queue.
    """
    a_queued_bill(brazos)
    out = StringIO()
    call_command("dispatch_outbound", "--tenant", brazos.subdomain, stdout=out)
    printed = out.getvalue()

    assert "dispatched: no" in printed
    # The two absences, by CODE, because a screen and a grep both need codes.
    assert "provider_status_unknown" in printed or "render_held_missing_template" in printed
    # ⚠ ADDED 2026-09-30 (`DEF-NOT-8451`). The line above accepts the code
    # ANYWHERE in the output, and from 2026-09-04 to 2026-09-07 it was satisfied
    # by the IN-APP channel's line (itself a defect, `DEF-NOT-4532`) while the
    # PRINT line — this bill's channel — wrongly said `provider_not_connected`.
    # It went red only when in_app was fixed (`5b6aaa823`). So the print row's
    # own reason is asserted by line, not by the whole printout.
    print_lines = [line for line in printed.splitlines() if "pdf_print" in line]
    assert print_lines, printed
    assert all("provider_not_connected" not in line for line in print_lines), print_lines
    assert any("provider_status_unknown" in line for line in print_lines), print_lines
    # ⚠ `held_marker_not_implemented` was asserted here until 2026-08-15. The
    # marker is BUILT now (US-NOT-014, migration 0007), so the cycle no longer
    # reports it as absent — it reports a COUNT of held rows when there are any,
    # and says nothing when there are none. This run has none, and asserting a
    # problem that correctly stopped appearing would be a test defending a gap
    # after the gap was closed.
    with tenant_ctx(brazos):
        assert models.OutboundMessage.objects.get().status == models.STATUS_QUEUED


def test_us_not_002_the_command_refuses_an_unknown_tenant_rather_than_dispatching(brazos):
    """CLAUDE.md rule 1. A dispatcher is the caller most likely to run outside a
    request; a command that shrugged at an unknown slug and ran anyway would
    drain whatever tenant context happened to be set."""
    with pytest.raises(CommandError, match="no live tenant"):
        call_command("dispatch_outbound", "--tenant", "not-a-tenant")


def test_us_not_002_the_command_takes_one_tenant_and_offers_no_all_tenants_switch():
    """Not a convenience choice — a B1 consequence. Iterating tenants would mean
    notifications reading `tenancy.Tenant`, and tenancy publishes no "every live
    tenant" selector. US-NOT-002 §1 wants a job PER TENANT anyway, so one
    utility's provider outage cannot delay another's bills."""
    from apps.notifications.management.commands import dispatch_outbound

    with pytest.raises(CommandError):
        call_command("dispatch_outbound")  # --tenant is required
    assert "all-tenants" not in dispatch_outbound.Command.help
