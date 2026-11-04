# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — WHO receives a staff notification, ruled and
#           wired: OQ-261 CLOSED 2026-08-17)   Screens: shell-chrome (the bell) ·
#           S8 (SET-12's staff rows)
# Rules:    BR-NOT-021 (staff recipients: the user who started the action, plus
#           all System Admins for failures — PO 2026-08-17, OQ-261 CLOSED) ·
#           BR-NOT-019 (in-app is a real channel; the platform is its provider) ·
#           BR-NOT-020 (ONE message per bulk action — this module widens the
#           MAILBOXES, never the message count) ·
#           BR-TEN-013 (a cross-module read resolves the owner's published
#           callable, never its ORM) · CLAUDE.md rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_cr_009_c11_staff_recipients.py
# Impacts:  apps/notifications/bulk_summary.py (the ONE live staff writer) ·
#           apps/notifications/in_app.py (deliver_batch fans one queue row out
#           to every listed mailbox) · apps/notifications/rule_catalog.py (the
#           five staff events now offer `in_app`)
# ───────────────────────────────────────────────────────
"""WHO receives a staff notification — the ruled answer, in one place.

╔══════════════════════════════════════════════════════════════════════════╗
║  OQ-261 IS CLOSED. PO 2026-08-17, verbatim (decision log, CR-010 C-section ║
║  rulings): "11 - A ✅ the user who started the action, plus all System     ║
║  Admins for failures"                                                     ║
╚══════════════════════════════════════════════════════════════════════════╝

That sentence is the whole recipient policy and this module is its only
implementation, so the wire, the screen and the writers all name the same rule
rather than three spellings of it:

  * **Every staff event goes to the user who STARTED the action.** Whoever
    pressed the button is, definitionally, involved in the operation.
  * **A FAILURE additionally goes to every ACTIVE System Admin of the tenant.**
    "Failure" is the event's own fact — a bulk summary with `failed_count > 0`,
    a billing run that failed — never something this module infers from prose.
  * **Nothing else.** No per-rule role picker, no named-user column, no
    tenant-wide operations contact: the PO chose the policy over every one of
    OQ-261's three options, so none of them is built.

────────────────────────────────────────────────────────────────────────────
ONE MESSAGE, MANY MAILBOXES — WHERE THE FAN-OUT LIVES
────────────────────────────────────────────────────────────────────────────
BR-NOT-020's one-message rule is untouched, exactly as `models.InAppMessage`'s
docstring promised the day it was written: *"that is ONE queue row and THREE
inboxes."* The queue row's `recipient_address` stays the PRIMARY recipient (the
initiator, or the first System Admin when a job had none) and the FULL list
travels in `recipient_snapshot["recipients"]` — snapshotted at queue time
(BR-TEN-017, never re-resolved) — and `in_app.deliver_batch` writes one mailbox
row per listed recipient. A two-person utility whose nightly run fails gets one
queue row, two bells.

────────────────────────────────────────────────────────────────────────────
HOW THE SYSTEM ADMINS ARE FOUND — THROUGH IDENTITY'S OWN PUBLISHED READS
────────────────────────────────────────────────────────────────────────────
`apps.identity.selectors.user_list` (the memberships with user + role) and
`apps.identity.selectors.is_active_system_admin` are resolved BY NAME at call
time (BR-TEN-013) — no identity model is imported here. An identity read that
cannot be resolved is REPORTED (`admins_unresolvable`) and the initiator still
receives their copy: a broken seam must never silence the one recipient who
needs no lookup, and must never be reported as "this tenant has no admins"
(DEF-075's zero-that-means-I-don't-know).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from apps.notifications import in_app
from core import errors
from core import tenancy as core_tenancy

#: The ruling, quoted where every consumer can cite it. VERBATIM (r11 step 1).
RULING = (
    'PO 2026-08-17, OQ-261 CLOSED: "the user who started the action, plus all '
    'System Admins for failures"'
)
BR_REF = "BR-NOT-021"

#: The identity reads this module depends on, named once so each contract is
#: greppable from BOTH sides of the boundary (the tenancy_seam discipline).
IDENTITY_MODULE = "identity"
MEMBERSHIP_LIST_READ = "user_list"
ACTIVE_ADMIN_TEST = "is_active_system_admin"

#: Problem code. A CODE, because a dispatch home groups on codes, never prose.
ADMINS_UNRESOLVABLE = "admins_unresolvable"


@dataclass(frozen=True)
class StaffRecipient:
    """One person a staff notification is addressed to, snapshotted."""

    user_id: str
    display_name: str | None
    #: Why this person is on the envelope: "initiator" or "system_admin".
    #: Carried into the snapshot so a delivery record a year on can say not
    #: just WHO was told but under which half of the ruling.
    reason: str


@dataclass(frozen=True)
class StaffAudience:
    """The resolved audience of ONE staff event, and anything that broke."""

    recipients: tuple[StaffRecipient, ...]
    problems: tuple[dict[str, Any], ...] = ()

    @property
    def primary(self) -> StaffRecipient | None:
        """The queue row's own `recipient_address` — the initiator when there
        is one, else the first System Admin. None means the ruling names
        nobody for this event (a clean scheduled run with no signed-in user)."""
        return self.recipients[0] if self.recipients else None

    def snapshot_entries(self) -> list[dict[str, Any]]:
        """The `recipient_snapshot["recipients"]` payload — BR-TEN-017's
        queue-time snapshot, one entry per mailbox `in_app.deliver_batch`
        will fill."""
        return [
            {
                "user_id": recipient.user_id,
                "display_name": recipient.display_name,
                "reason": recipient.reason,
            }
            for recipient in self.recipients
        ]


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(attribute: str) -> Any:
    """Identity's published callable, or None while it publishes none.

    getattr at CALL time — the idiom every seam in this module uses — so no
    import statement binds notifications to identity's internals.
    """
    try:
        target = import_module(f"apps.{IDENTITY_MODULE}.selectors")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _display_name(user: Any) -> str | None:
    return getattr(user, "full_name", "") or getattr(user, "email", "") or None


def _initiator(actor: Any) -> StaffRecipient | None:
    """The user who started the action, or None for a job with no signed-in
    user. Address spelling is `in_app.address_for`'s — ONE spelling, always."""
    if actor is None:
        return None
    try:
        address = in_app.address_for(actor)
    except in_app.InboxRefused:
        return None
    user = getattr(actor, "user", None) or actor
    return StaffRecipient(user_id=address, display_name=_display_name(user), reason="initiator")


def _active_system_admins() -> tuple[tuple[StaffRecipient, ...], dict[str, Any] | None]:
    """(admins, problem). Empty-with-a-problem is 'nobody could look', which is
    a DIFFERENT fact from a tenant that genuinely has no active admin, and the
    two must never travel the same (DEF-075)."""
    memberships_read = _resolve(MEMBERSHIP_LIST_READ)
    admin_test = _resolve(ACTIVE_ADMIN_TEST)
    if memberships_read is None or admin_test is None:
        return (), {
            "code": ADMINS_UNRESOLVABLE,
            "br_ref": BR_REF,
            "detail": (
                f"apps.{IDENTITY_MODULE}.selectors.{MEMBERSHIP_LIST_READ} / "
                f"{ACTIVE_ADMIN_TEST} could not be resolved, so the System Admins this "
                f"failure must reach ({RULING}) could not be listed. The initiator's own "
                "copy is unaffected; the gap is reported rather than read as 'this tenant "
                "has no admins'."
            ),
        }
    admins: list[StaffRecipient] = []
    for membership in memberships_read(_tenant_id(), sort=None, direction="asc"):
        if not admin_test(membership):
            continue
        user = membership.user
        admins.append(
            StaffRecipient(
                user_id=str(user.id),
                display_name=_display_name(user),
                reason="system_admin",
            )
        )
    # Deterministic order — by display name then id — so a retried job builds
    # the same envelope and the idempotent replay compares equal.
    admins.sort(key=lambda entry: (entry.display_name or "", entry.user_id))
    return tuple(admins), None


def resolve_staff_recipients(*, actor: Any, failure: bool) -> StaffAudience:
    """The ruled audience of one staff event. BR-NOT-021, and nothing else.

    `failure` is the CALLER's fact — a bulk summary passes `failed_count > 0`,
    a billing-run-failed event passes True — because only the writer knows what
    its event reports. Nothing here parses a message body for the word
    "failed".

    Returns an audience that may be EMPTY: a scheduled job with no signed-in
    user and nothing failed has, under the ruling, nobody to tell — and that is
    the ruling's own answer, not a refusal this module invents.
    """
    recipients: list[StaffRecipient] = []
    problems: tuple[dict[str, Any], ...] = ()

    initiator = _initiator(actor)
    if initiator is not None:
        recipients.append(initiator)

    if failure:
        admins, problem = _active_system_admins()
        if problem is not None:
            problems = (problem,)
        seen = {entry.user_id for entry in recipients}
        for admin in admins:
            if admin.user_id in seen:
                # The initiator IS one of the admins: one person, one mailbox.
                # The initiator entry wins because it is the more specific fact.
                continue
            recipients.append(admin)
            seen.add(admin.user_id)

    return StaffAudience(recipients=tuple(recipients), problems=problems)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009c11 (12-governance/02-decision-log.md → 2026-08-17 "CR-010 — the B and C sections ruled" C-11 verbatim · 12-governance/11-change-requests.md → CR-009 · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-021 · apps/identity/selectors.py user_list + is_active_system_admin, the published reads)
# generated: 2026-08-18 by story-coder (CR-009 C-section lane)
# checklist: A✔ B✔ C✔ D=deferred(no HTTP surface — writers call this; the wire carries the policy sentence via rule_service) E=deferred(the screen half is NotificationRules.tsx's audience card) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr_009_c11_staff_recipients.py — the failure fan-out was RED-proved by asserting two mailboxes before deliver_batch grew the fan-out loop, and the admins-unresolvable branch by unpublishing the identity read
# exceptions: (1) THE POLICY IS NOT TENANT-SETTABLE. The PO ruled a policy, not a setting: rule_service still refuses every spelling of "send it to X", now citing BR-NOT-021 instead of raising OQ-261. (2) AN EMPTY AUDIENCE IS A LAWFUL ANSWER — a clean scheduled run with no signed-in user reaches nobody under the ruling, and the caller reports that rather than inventing an addressee. (3) IDENTITY IS READ THROUGH ITS PUBLISHED SELECTORS ONLY; a resolution failure is reported (`admins_unresolvable`) and never rendered as "no admins".
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
