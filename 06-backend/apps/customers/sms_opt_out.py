# ── Trace ──────────────────────────────────────────────
# Change:   CR-198-BRC10 (PO 2026-10-29, ruling 6A: "ONly Stop option is
#           required") — a customer replying STOP turns OFF the account's
#           *SMS reminders* tick.
# Rules:    BR-INT-086 · BR-CUS-028 (the tick is the customer's consent to
#           texts) · CLAUDE.md hard rule 1 (tenant-scoped) · hard rule 7 (the
#           change is audited) · B1 (only customers writes `accounts`)
# Tests:    06-backend/tests/test_cr198_sms_twilio.py
# ───────────────────────────────────────────────────────
"""Turn the *SMS reminders* tick off because the customer asked us to stop.

⚠ **THE ONE WRITER OF THIS COLUMN FOR A STOP, AND IT IS HERE BECAUSE THE COLUMN
IS OURS.** Notifications learns of the STOP (from the integrations door) and
asks through its customers seam; it never writes `accounts` itself (B1, the
no-cross-module-write rule).

**Only ever OFF.** A STOP never turns anything on, and nothing here does: Twilio
answers START at the carrier level (PO: only STOP is built), and a customer who
wants texts again asks the utility, whose clerk ticks the box — the safe
direction, because a wrongly-resumed text goes to a person who said no.

**One audit row per account that changed**, naming the reason and the masked
number (BR-AUD-006: a phone enters the trail as its last two digits). An account
whose tick was already off is not touched and not audited — nothing changed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction

from apps.customers import models
from core import audit
from core import tenancy as core_tenancy
from core import errors

AUDIT_ACTION = "account.sms_reminders_turned_off"
AUDIT_ENTITY = "account"
REASON_REPLIED_STOP = "customer_replied_stop"
REASON_PROVIDER_OPTED_OUT = "provider_reported_opted_out"
REASONS = (REASON_REPLIED_STOP, REASON_PROVIDER_OPTED_OUT)


def _mask(number: str | None) -> str:
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    return f"***{digits[-2:]}" if len(digits) >= 2 else "***"


@transaction.atomic
def turn_off_sms_reminders(
    *,
    account_ids: Any,
    reason: str,
    at: datetime,
    number: str | None = None,
    job: str = "notifications.sms_stop",
) -> tuple[str, ...]:
    """Turn the tick OFF on these accounts. Returns the ids that CHANGED."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    if reason not in REASONS:
        raise ValueError(f"{reason!r} is not a reason to turn texts off; one of {REASONS}")
    ids = sorted({str(one) for one in (account_ids or ()) if one})
    if not ids:
        return ()
    rows = list(
        models.Account.objects.select_for_update()
        .filter(tenant_id=tenant_id, pk__in=ids, sms_reminders=True)
        .order_by("id")
    )
    changed: list[str] = []
    for account in rows:
        account.sms_reminders = False
        account.save(update_fields=["sms_reminders", "updated_at"])
        audit.money_action(
            None,
            AUDIT_ACTION,
            AUDIT_ENTITY,
            str(account.pk),
            before={"sms_reminders": True},
            after={
                "sms_reminders": False,
                "reason": reason,
                "number": _mask(number),
                "at": at.isoformat(),
                "job": job,
            },
        )
        changed.append(str(account.pk))
    return tuple(changed)


__all__ = ["REASON_PROVIDER_OPTED_OUT", "REASON_REPLIED_STOP", "turn_off_sms_reminders"]
