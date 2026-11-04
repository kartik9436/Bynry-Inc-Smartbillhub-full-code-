# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — the operator's door to the ONE message a bulk
#           action sends, and the end-to-end proof of the in-app channel)
#           Screens: shell-chrome (the bell the message lands in)
# Rules:    BR-NOT-020 (one message per bulk action, with its failure count) ·
#           BR-NOT-019 (in-app is a real channel) · BR-NOT-005 (this QUEUES; it
#           does not send — `dispatch_outbound` is what delivers) ·
#           BR-TEN-043 (the moment is named by the caller, never a clock read
#           inside the service) · CLAUDE.md rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_cr_009_bulk_one_message.py
# ───────────────────────────────────────────────────────
"""`manage.py send_bulk_summary` — queue the one message a bulk action sends.

WHY THIS FILE EXISTS: hard-won law 2, *"built is not wired."* `bulk_summary.
queue_bulk_summary` is the rule and the mechanism, and the bill run does not
call it yet (BR-NOT-018 / OQ-262 — three staff events have no trigger anywhere
in this codebase). A rule nobody can invoke is a rule that renders nothing,
passes every test and does not exist. This is the door.

**IT IS ALSO HOW THE IN-APP CHANNEL IS PROVED END TO END**, which is what the PO
asked for on 2026-08-17: *"We can confirm it whether it is working on not if we
get in APp Notifcaition."* Two commands, in order, and a browser:

    python manage.py send_bulk_summary --tenant <slug> --user <email> \\
        --operation "Billing run" --total 1204 --failed 3
    python manage.py dispatch_outbound --tenant <slug> --channel in_app

The first writes ONE queue row. The second drains it through the real
dispatcher, the real template pin, the real renderer and the real provider seam
— into the recipient's inbox. Then the bell shows `1`, the popover shows
*"Billing run finished. 1204 processed · 3 failed"*, and opening it marks it
read. Nothing about that path is special-cased for in-app except which adapter
the seam resolves.

⚠ **THIS COMMAND QUEUES AND DOES NOT SEND.** BR-NOT-005 has no exception for an
operator, and running only the first command leaves a row sitting `queued` —
which is the correct, visible, half-finished state and is exactly what a bill
does today.

⚠ **`--user` IS AN EMAIL AND IT IS RESOLVED THROUGH IDENTITY'S OWN READ**, never
by this module querying `identity.users` (BR-TEN-013: a module never touches
another module's ORM). If identity publishes no such read the command REFUSES
and names the contract, rather than reaching across the boundary because it is
convenient at a shell prompt.
"""

from datetime import datetime, timezone as dt_timezone
from importlib import import_module
from types import SimpleNamespace
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.notifications import bulk_summary
from core import tenancy as core_tenancy

#: What `--event` accepts to mean "name no event at all" — the pre-CR-048 call.
#: A word rather than an empty string, because an empty `--event ""` at a shell
#: prompt is indistinguishable from a flag whose value was lost.
NO_EVENT = "none"

#: BE-01's own resolver, named once so the contract is greppable from both
#: sides — the same constant `dispatch_outbound` uses.
TENANCY_MODULE = "tenancy"
TENANT_LOOKUP = "tenant_id_for_subdomain"

#: The identity read this command needs. Declared as a named contract for the
#: same reason `services.RECIPIENT_READ` is: an unresolved seam must be
#: reportable, not a silent import error.
IDENTITY_MODULE = "identity"
USER_LOOKUP = "user_by_email"


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
        "Queue THE ONE in-app message a bulk action sends (BR-NOT-020), addressed "
        "to a named staff user. Queues only — run dispatch_outbound to deliver it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="The tenant's subdomain slug.")
        parser.add_argument(
            "--user",
            required=True,
            help="The email address of the staff user whose inbox this lands in. The "
            "person who RAN the bulk action; a run with failures also reaches every "
            "active System Admin (BR-NOT-021, OQ-261 closed 2026-08-17).",
        )
        parser.add_argument(
            "--operation",
            default="Bulk action",
            help="The human phrase a clerk reads — 'Billing run', 'Payment import'. "
            "Not an event key: the reader is a clerk, not a developer.",
        )
        parser.add_argument("--total", type=int, required=True, help="Items processed.")
        parser.add_argument(
            "--failed",
            type=int,
            required=True,
            help="Items that FAILED. Required and never defaulted — a defaulted zero is "
            "how a run that failed 87 times reports success (BR-NOT-020).",
        )
        parser.add_argument(
            "--event",
            default=bulk_summary.EVENT_BILLING_RUN,
            help="The SET-12 event this summary IS, so the utility's own rule is read "
            "and obeyed (CR-048 B4). Defaults to the billing-run event; pass "
            f"{NO_EVENT!r} for the pre-CR-048 behaviour, which reads no rule at all. "
            "Switch the event off on Settings → Notifications and run this again to "
            "watch the setting actually stop the message.",
        )
        parser.add_argument(
            "--operation-id",
            default=None,
            help="The run's own id. Defaults to a fresh uuid per invocation; pass the "
            "SAME one twice to see rule 6 refuse the second summary.",
        )

    def handle(self, *args, **options):
        import uuid

        lookup = _resolve(TENANCY_MODULE, TENANT_LOOKUP)
        if lookup is None:  # pragma: no cover - tenancy publishes this today
            raise CommandError(
                f"apps.{TENANCY_MODULE}.selectors.{TENANT_LOOKUP} is not published, so "
                "the tenant cannot be resolved. Nothing was queued (CLAUDE.md rule 1)."
            )
        tenant_id = lookup(options["tenant"])
        if tenant_id is None:
            raise CommandError(
                f"no live tenant with subdomain {options['tenant']!r}. Nothing was queued."
            )

        with core_tenancy.tenant_context(tenant_id):
            actor = self._actor(options["user"])
            # BR-TEN-043: the moment is named HERE and passed down. Nothing in
            # the notifications module reads a wall clock, and G6 greps for it.
            finished_at = datetime.now(dt_timezone.utc)
            try:
                summary = bulk_summary.queue_bulk_summary(
                    operation=options["operation"],
                    operation_id=options["operation_id"] or uuid.uuid4(),
                    total_count=int(options["total"]),
                    failed_count=int(options["failed"]),
                    finished_at=finished_at,
                    actor=actor,
                    job=__name__,
                    # CR-048 B4 — the rule join. `--event none` restores the
                    # pre-CR-048 call exactly, which is what makes the DIFFERENCE
                    # demonstrable at a shell prompt rather than argued about.
                    event_key=(None if options["event"] == NO_EVENT else options["event"]),
                )
            except bulk_summary.BulkSummaryRefused as refusal:
                raise CommandError(str(refusal)) from refusal

        if summary.suppressed_by_rule:
            # CR-048 B4. NOT an error: a utility switching a notification off is
            # a choice, and a command that failed here would teach an operator
            # to distrust the setting rather than the message.
            self.stdout.write(
                f"[{options['tenant']}] {summary.operation}: {summary.total_count} "
                f"processed, {summary.failed_count} failed → NOTHING QUEUED — this "
                "utility has switched the notification off."
            )
            for problem in summary.problems:
                self.stdout.write(f"  ! {problem['code']}: {problem['detail']}")
            return

        self.stdout.write(
            f"[{options['tenant']}] {summary.operation}: {summary.total_count} processed, "
            f"{summary.failed_count} failed → "
            f"{'QUEUED' if summary.created else 'ALREADY QUEUED (rule 6 — same run id)'} "
            f"message {summary.message_id} on {summary.channel}"
            + (f" as {summary.event_key}" if summary.event_key else " (no event named)")
        )
        self.stdout.write(
            "  Nothing has been delivered yet. Run: manage.py dispatch_outbound "
            f"--tenant {options['tenant']} --channel in_app"
        )

    def _actor(self, email: str) -> Any:
        """The staff user this summary is addressed to, through identity's read."""
        read = _resolve(IDENTITY_MODULE, USER_LOOKUP)
        if read is None:
            raise CommandError(
                f"apps.{IDENTITY_MODULE}.selectors.{USER_LOOKUP} is not published, so this "
                "command cannot resolve a staff user by email. It will NOT query "
                "identity's ORM directly — BR-TEN-013 forbids a module touching another "
                "module's tables, and a convenience at a shell prompt is exactly how that "
                "boundary erodes. Nothing was queued."
            )
        user = read(core_tenancy.current_tenant_id(), email)
        if user is None:
            raise CommandError(
                f"no user with email {email!r} in this tenant. Nothing was queued: an "
                "in-app message belongs to a person, and there is no tenant-wide mailbox "
                "to fall back to."
            )
        # The B12 §6a actor shape, the same one the API layer builds.
        return SimpleNamespace(id=getattr(user, "id", None), role=None, user=user)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 fourth ruling set · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-019/BR-NOT-020 · apps/notifications/bulk_summary.py · apps/notifications/management/commands/dispatch_outbound.py, whose shape this follows)
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D=deferred(not an API surface — a management command) E=deferred(the message is READ in AppShell's bell) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: this command IS the 2d proof — it and `dispatch_outbound --channel in_app` are what put a real message in a real inbox; the transcript is in the lane report
# exceptions: (0) [CR-048 B4, 2026-08-29] `--event` NAMES THE SET-12 EVENT and defaults to `billing_run_completed`, so this demo path now reads the utility's own rule exactly as a real bill run will. Switch the event off on Settings → Notifications, run this again, and the command prints NOTHING QUEUED with the reason — which is CR-048's headline made visible at a shell prompt. `--event none` restores the pre-CR-048 call byte for byte, so the difference is demonstrable rather than argued. A suppressed summary is NOT a command error: a utility switching a notification off is a choice, and failing here would teach an operator to distrust the setting.
#         (1) QUEUES ONLY — BR-NOT-005 has no operator exception, and the command prints the second command rather than running it. (2) NO DIRECT ORM ACROSS THE BOUNDARY: the user is resolved through identity's published read or the command refuses and names the contract. (3) `--operation-id` DEFAULTS TO A FRESH UUID so repeated demo runs each queue a message; passing the same one twice is how rule 6's refusal is demonstrated by hand.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
