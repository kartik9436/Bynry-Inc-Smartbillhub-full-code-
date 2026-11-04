# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-6342 — marking post returned reached nobody, because two
#           bad-address facts existed and nothing wrote the one every screen
#           reads.
# Story:    US-PAY-016 (returned mail → bad-address flag → needs-attention →
#           banner)   Screens: S21 (the account) · U7 (the unit's Account tab)
# Rules:    BR-PAY-018 (VERBATIM: "Returned mail: delivery record marked
#           returned (single/bulk) → account bad-address flag → needs-attention
#           queue + banner → paper suppressed until address verified (config);
#           balances unaffected; audited.") · BR-CWP-086 (returned post clears
#           when the customer corrects their address) · B2 r12 #8
#           (`accounts.bad_address`) · B1 / B2 §2 (a module writes ITS OWN
#           tables; a neighbour asks it to) · CLAUDE.md rule 7 (audit)
# Tests:    06-backend/tests/test_def_pay_6342_bad_address.py
# Impacts:  apps/payments/returned_mail.py (sets and clears through this) ·
#           apps/customers/portal_self_service.py (clears through this) ·
#           apps/payments/outstandings.py + billing_seam.py (read through this)
# ───────────────────────────────────────────────────────
"""`accounts.bad_address` — THE ONE BAD-ADDRESS FACT, and its only writers.

════════════════════════════════════════════════════════════════════════════
WHY THE STORED COLUMN IS THE FACT (DEF-PAY-6342, 2026-09-23)
════════════════════════════════════════════════════════════════════════════
Until today there were TWO. `payments.returned_mail.bad_address_for` DERIVED a
flag from unresolved `delivery_return_events`, and `accounts.bad_address` was a
STORED column — and they never met. Every module was right about its own
boundary and wrong about the others, so nothing wrote the column:
notifications called it *"payments'"*, payments said it *"IS NOT HERE AND CANNOT
BE"*, and customers' own edit refusal said it was *"set by returned-mail
handling"*. So a clerk pressed *Mark returned* and the account page went on
reading **Bad address: No**.

The column wins, for three reasons that are about the product rather than taste:

  1. **It already had FIVE readers across four modules** — the account page,
     the unit page, the collections runbook's deliverability step, the customer
     portal's My details, and (now) payments' Debtors list. The derived flag had
     one. Moving five readers onto a derivation would have been five changes to
     fix one missing write.
  2. **It has two writers that are not returned mail at all**: a migration
     brings the flag across from the utility's old system (`IMPORT_ACCOUNT_
     FIELDS`), and the customer clears it by correcting their own address in
     the portal (`BR-CWP-086`). A derivation from return events cannot express
     either — an imported flag has no event behind it.
  3. **B2 r12 #8 signed the column.** The derived shape was a documented
     deviation (`returned_mail.py`'s own docstring said so and asked for
     *"one migration in customers plus a call at the two points below"*). The
     migration already existed; only the calls were missing.

The return EVENTS stay exactly what they are, and that is the other half of
the design rather than a leftover: they are the HISTORY — *which* letter,
*which* address, *when*, and how each was resolved — and they are the
needs-attention list. The flag says *this account's post is coming back*; the
events say *why we think so*.

════════════════════════════════════════════════════════════════════════════
WHO WRITES IT, AND HOW A NEIGHBOUR ASKS
════════════════════════════════════════════════════════════════════════════
Only this module's code writes the column. Payments ASKS, by name, from
`returned_mail.py` — the `record_deposit_movement` / `record_nsf` shape this
product already uses for the same reason (B1: a module writes its own tables).
The two writers here are conditional UPDATEs rather than read-then-write, so two
clerks marking the same account at once cannot both "flag" it and write two
audit rows: the database answers which one changed it.

⚠ **NEITHER FUNCTION HOLDS PAPER.** BR-PAY-018's *"paper suppressed until
address verified (config)"* is `notifications.delivery_ops.hold_paper_for_
accounts`, which has no caller and is out of this release by PO ruling (nothing
dispatches in R2, 2026-08-16). Setting this flag does not call it.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from apps.customers import models
from core import audit as core_audit
from core import tenancy as core_tenancy

#: How the flag moved, on the audit row. CODES, because a report groups on them.
VIA_RETURNED_MAIL = "returned_mail"
VIA_CLERK_CLEARED = "returned_mail_resolved"
VIA_CUSTOMER_PORTAL = "customer_portal"


def _tenant_id() -> Any:
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _write(
    account_id: Any,
    *,
    to: bool,
    actor: Any,
    via: str,
    context: dict[str, Any] | None,
) -> bool:
    """Move the flag to `to` if it is not there already. True when it moved.

    ONE conditional UPDATE: the row changes only when it currently holds the
    other value, so the database — not a SELECT a second clerk can race — says
    whether this call is the one that moved it, and exactly one audit row is
    written per real change.
    """
    moved = models.Account.objects.filter(
        tenant_id=_tenant_id(), pk=account_id, bad_address=not to
    ).update(bad_address=to, updated_at=timezone.now())
    if moved:
        core_audit.write_row(
            action="account.bad_address.flagged" if to else "account.bad_address.cleared",
            entity_type="account",
            entity_id=account_id,
            actor_user_id=core_audit.actor_user_id(actor),
            before={"bad_address": not to},
            after={"bad_address": to, "via": via, **(context or {})},
        )
    return bool(moved)


def flag_bad_address(
    account_id: Any, *, actor: Any = None, via: str = VIA_RETURNED_MAIL, context: Any = None
) -> bool:
    """BR-PAY-018's second arrow — *"→ account bad-address flag"*.

    PUBLISHED FOR PAYMENTS (`returned_mail.mark_returned`). True when this call
    raised it; False when it was already up, which is a normal Tuesday — the
    second envelope from the same account.
    """
    return _write(account_id, to=True, actor=actor, via=via, context=context)


def clear_bad_address(
    account_id: Any, *, actor: Any = None, via: str = VIA_CLERK_CLEARED, context: Any = None
) -> bool:
    """The flag comes down — a clerk verified or corrected the address, or the
    customer corrected it in the portal (`BR-CWP-086`).

    PUBLISHED FOR PAYMENTS (`returned_mail.clear_account`). True when this call
    lowered it.
    """
    return _write(account_id, to=False, actor=actor, via=via, context=context)


def flagged_account_ids() -> QuerySet:
    """Every flagged account's id, as a LAZY queryset — composed, never listed.

    PUBLISHED FOR PAYMENTS' Debtors filter (`f.bad_address=true`), which puts
    it inside its own statement as `account_id__in=<this>`. Nothing is
    materialised, so there is no list of ids to cap and no parameter limit to
    reach at 40,000 accounts (`NFR-3` / `NFR-5`).
    """
    return models.Account.objects.filter(tenant_id=_tenant_id(), bad_address=True).values("id")


def bad_address_flags(account_ids: Any) -> set[str]:
    """Which of these accounts are flagged — ONE statement for a page."""
    ids = [value for value in (account_ids or ()) if value not in (None, "")]
    if not ids:
        return set()
    return {
        str(pk)
        for pk in models.Account.objects.filter(
            tenant_id=_tenant_id(), pk__in=ids, bad_address=True
        ).values_list("id", flat=True)
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-6342 (the defect row, BR-PAY-018 verbatim, B2 r12 #8, J18)
# generated: 2026-09-23 by the BAD-ADDRESS lane (maintenance)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_def_pay_6342_bad_address.py — red first, quoted in the lane report
# exceptions: (1) NO PAPER IS HELD. `hold_paper_for_accounts` is out of this
#         release; this module does not call it and says so above.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
