# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-002 (the dispatcher — this is the RUNNER that invokes one
#           cycle; the cycle itself is apps/notifications/dispatcher.py)
#           Screens: S8 · S30
# Rules:    BR-NOT-005 (batches at the provider's pace — one batch per channel
#           per invocation, never a drain loop) · BR-BIL-016 (mass sends are
#           never synchronous) · BR-NOT-009 (quiet hours) · BR-TEN-013 (a module
#           NEVER touches another module's ORM — the tenant is resolved through
#           tenancy's published selector) · BR-TEN-043 (event time is named by
#           the caller, never read from a clock) · CLAUDE.md rule 1 (tenant
#           scoping)
# Tests:    06-backend/tests/test_us_not_002_dispatch_command.py
# ───────────────────────────────────────────────────────
"""`python manage.py dispatch_outbound --tenant <subdomain>` — one cycle, once.

WHY THIS FILE EXISTS AT ALL: hard-won law 2, *"built is not wired."* A
dispatcher that no operator, job or runbook can invoke is a feature that renders
nothing, passes every test and does not exist. `dispatcher.dispatch_cycle` is a
service function; this is the one thing in the repo that calls it.

ONE INVOCATION = ONE BATCH PER CHANNEL, NOT A DRAIN
----------------------------------------------------
BR-NOT-005 paces at the PROVIDER's rate. Draining 10,000 queued rows is twenty
invocations of 500, spaced by whatever the tenant's provider tolerates — and a
`while queue: send()` loop inside one invocation would be the platform-speed
blast the rule exists to forbid (T5-24 step 2). So this command runs exactly one
cycle and exits. `--cycles N` is offered for an operator draining a backlog by
hand, and it is a REPEAT of the whole cycle (config re-read, window re-checked,
a fresh batch claimed) rather than a faster inner loop.

ONE TENANT PER INVOCATION, NAMED BY THE OPERATOR — AND THAT IS A B1 CONSEQUENCE
-------------------------------------------------------------------------------
There is no `--all-tenants`. Iterating tenants would mean this module reading
`tenancy.Tenant`, which B1 forbids (BR-TEN-013), and tenancy publishes no
"every live tenant" selector. What it DOES publish is
`apps.tenancy.selectors.tenant_id_for_subdomain`, the BE-01 resolver, so the
tenant is named on the command line and resolved through the owner's own read.

A scheduler therefore invokes this once per tenant. That is also the correct
SHAPE regardless of B1: US-NOT-002 §1 says *"scheduled job PER TENANT"*, and one
process draining every tenant's queue in a loop would let one utility's provider
outage delay another's bills.

⚠ NOTHING SCHEDULES THIS. There is no celery-beat wiring and no cron entry in
this repo (`maintain_partitions` records the same gap: *"celery-beat wiring
lands with the jobs-table story (TD-17); until then ops/CI run this command
directly"*). Until a scheduler exists an operator runs it, and saying so here is
the point of saying it at all.

WHAT IT PRINTS IS THE HONEST STATE, INCLUDING THE ZEROS
--------------------------------------------------------
⚠ **AMENDED 2026-08-17 (CR-009 in-app lane). This paragraph used to say it would
report `dispatched: no` EVERY TIME, and that stopped being true the day `in_app`
landed** — a paragraph describing the product is a claim about it (hard-won law
1). Print, email and SMS still report `no` with their reasons: no provider
adapter exists for any of them (`apps/integrations` is three docstrings,
BR-NOT-013). **In-app dispatches for real**, through the platform's own adapter
(`apps/notifications/in_app.py`), and its rows reach `sent`. Those reasons print
as PROBLEMS with their codes, so an operator sees why nothing moved on the three
that cannot move instead of concluding the queue is empty.
"""

from datetime import datetime, timezone as dt_timezone
from importlib import import_module
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.notifications import dispatcher, models
from core import tenancy as core_tenancy

#: The tenancy read that turns a subdomain into a tenant id — BE-01's own
#: resolver, named once so the contract is greppable from both sides.
TENANCY_MODULE = "tenancy"
TENANT_LOOKUP = "tenant_id_for_subdomain"


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


class Command(BaseCommand):
    help = (
        "Run ONE outbound dispatch cycle for one tenant: at most the tenant's "
        "batch size per channel, handed to its provider in one call."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            required=True,
            help="The tenant's subdomain slug. REQUIRED and single — there is no "
            "--all-tenants (see the module docstring: B1 plus per-tenant pacing).",
        )
        parser.add_argument(
            "--channel",
            action="append",
            choices=list(models.CHANNELS),
            help="Restrict to one or more channels. Default: all four (in_app is "
            "the one that actually delivers today). Rows for a channel whose SEND "
            "is deferred are never touched either way.",
        )
        parser.add_argument(
            "--cycles",
            type=int,
            default=1,
            help="Repeat the WHOLE cycle N times (config re-read, window re-checked, "
            "a fresh batch claimed each time). Not a faster inner loop — the pacing "
            "rule is per hand-off.",
        )

    def handle(self, *args, **options):
        lookup = _resolve(TENANCY_MODULE, TENANT_LOOKUP)
        if lookup is None:  # pragma: no cover - tenancy publishes this today
            raise CommandError(
                f"apps.{TENANCY_MODULE}.selectors.{TENANT_LOOKUP} is not published, so "
                "the tenant cannot be resolved. Dispatch is refused rather than run "
                "without a tenant context (CLAUDE.md rule 1)."
            )
        subdomain = options["tenant"]
        tenant_id = lookup(subdomain)
        if tenant_id is None:
            raise CommandError(
                f"no live tenant with subdomain {subdomain!r}. Nothing was dispatched."
            )

        channels = tuple(options["channel"]) if options["channel"] else models.CHANNELS
        cycles = max(1, int(options["cycles"]))

        # BR-TEN-043: the moment is named ONCE, here, and passed down — every
        # window and schedule decision in the cycle is made against the same
        # instant rather than against a clock read part-way through.
        now = datetime.now(dt_timezone.utc)

        with core_tenancy.tenant_context(tenant_id):
            for index in range(cycles):
                result = dispatcher.dispatch_cycle(now=now, channels=channels, job=__name__)
                self._report(subdomain, index + 1, cycles, result)
                if not result.claimed:
                    # Nothing was even claimed — a further cycle would claim
                    # nothing either, and repeating it would only reprint the
                    # same reasons.
                    break

    def _report(self, subdomain, index, cycles, result):
        self.stdout.write(
            f"[{subdomain}] cycle {index}/{cycles} · batch size {result.batch_size} · "
            f"claimed {result.claimed} · sent {result.sent} · "
            f"dispatched: {'yes' if result.dispatched else 'no'}"
        )
        for batch in result.batches:
            if batch.batch_id is None and not batch.claimed:
                continue
            self.stdout.write(
                f"  {batch.channel}: batch {batch.batch_id} — sent {batch.sent}, "
                f"failed {batch.failed}, retrying {batch.retrying}"
            )
        for problem in result.problems:
            # The reasons nothing moved are the POINT of the output on a
            # deployment where nothing can move yet. Codes first, so an operator
            # can grep them and a screen can group on them.
            self.stdout.write(f"  ! {problem['code']}: {problem['detail'][:160]}")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-002@7d4e0c5 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md — US-NOT-002 §1 "scheduled job per tenant" — · 10-notifications/02-business-rules.md · 10-notifications/04-flows.md §1 · 08-qa/01-e2e/journeys/T5-24-dispatch-burst-pacing.md)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane — the dispatcher's runner)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — a management command) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_not_002_dispatch_command.py
# exceptions: (1) NOTHING SCHEDULES THIS. No celery-beat wiring and no cron entry
#         exists in this repo — the same gap `apps/audit/management/commands/
#         maintain_partitions.py` records for TD-17. An operator runs it. REPORTED
#         rather than left for a reader to discover that a "dispatcher" never
#         runs (hard-won law 2).
#         (2) NO `--all-tenants`, and it is a B1 consequence rather than a
#         convenience choice: iterating tenants would mean this module reading
#         `tenancy.Tenant`, and tenancy publishes no "every live tenant" read.
#         US-NOT-002 §1 wants a job PER TENANT anyway, so one utility's provider
#         outage cannot delay another's bills.
#         (3) `--cycles` REPEATS THE WHOLE CYCLE and is not a drain loop: config
#         re-read, window re-checked, a fresh batch claimed. A loop that kept
#         sending until the queue emptied would be the platform-speed blast
#         BR-NOT-005 forbids (T5-24 step 2).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
