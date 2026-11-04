"""identity → notifications: the two staff sign-in emails, resolved BY NAME.

`CR-188-BRC10`. Identity must not import notifications (B1); `outbound_messages`
is the one table B1 opens to cross-module writes, and it is written by
notifications' own service. So this file resolves
`apps.notifications.staff_access_events` at CALL time — the idiom
`apps/reports/notifications_seam.py` and `apps/portal/seams/notifications_seam.py`
use — and `G20` harvests the names below.

⚠ **NOTHING HERE MAY BREAK THE CALLER, AND A `try` IS NOT ENOUGH ON
POSTGRESQL** (hard-won law 14). The queue write is inside a SAVEPOINT: a failure
in it rolls back to the savepoint and the user the admin just created stays
created.

⚠ **UNWIRED ⇒ `None` ⇒ THE ADMIN IS TOLD *NOT EMAILED*.** It never reports a
message it did not queue.

The template codes, the event keys and the token list live in the notifications
catalogue; identity passes only the KIND (`invite` / `reset`) and the facts
(PO 2026-10-22, *"don't do any hardcoding"*).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from django.db import transaction

MESSAGE_MODULE = "notifications"
MESSAGE_KIND = "staff_access_events"
WRITE_ACCESS_EMAIL = "queue_staff_access_email"
READ_REACHABILITY = "email_reachability"
SEND_NOW_KIND = "services"
SEND_NOW = "send_now"
READ_DATE_FORMAT = "format_link_date"

REASON_UNAVAILABLE = "email_unavailable"


def _resolve(name: str, kind: str = MESSAGE_KIND) -> Any:
    try:
        published = import_module(f"apps.{MESSAGE_MODULE}.{kind}")
    except ImportError:  # pragma: no cover — notifications is always installed
        return None
    found = getattr(published, name, None)
    return found if callable(found) else None


def email_reachability() -> str | None:
    """`None` when an email queued now would leave; else the reason CODE."""
    read = _resolve(READ_REACHABILITY)
    if read is None:  # pragma: no cover — G20 fails this at merge
        return REASON_UNAVAILABLE
    try:
        with transaction.atomic():  # SAVEPOINT — law 14
            return read()
    except Exception:  # noqa: BLE001 — a broken read must not block the admin
        return REASON_UNAVAILABLE


def queue_access_email(*, expires_at: Any, **fields: Any) -> dict[str, Any]:
    """Queue ONE staff sign-in email and ask for it to be sent NOW.

    Returns `{"status", "reason", "message_id"}`. Never raises.
    """
    write = _resolve(WRITE_ACCESS_EMAIL)
    send_now = _resolve(SEND_NOW, kind=SEND_NOW_KIND)
    formatter = _resolve(READ_DATE_FORMAT)
    if write is None or formatter is None:  # pragma: no cover — G20 fails this at merge
        return {"status": "not_sent", "reason": REASON_UNAVAILABLE, "message_id": None}
    try:
        with transaction.atomic():  # SAVEPOINT — law 14, not tidiness
            answer = write(link_expires_on=formatter(expires_at), **fields)
            if answer.message_id is not None and send_now is not None:
                # PO 2026-10-22: *"this should be instant email"* — sent on
                # commit through the dedicated high-priority queue.
                send_now([answer.message_id], actor=fields.get("actor"))
    except Exception:  # noqa: BLE001 — the user is created whatever happens here
        return {"status": "not_sent", "reason": REASON_UNAVAILABLE, "message_id": None}
    return {"status": answer.status, "reason": answer.reason, "message_id": answer.message_id}
