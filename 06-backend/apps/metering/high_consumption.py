# ── Trace ──────────────────────────────────────────────
# Change:   CR-182-BRC10 — PO rulings A1–A5, 2026-10-14 (decision log *"HIGH
#           CONSUMPTION: THE CUSTOMER IS ALERTED AS SOON AS A READING IS
#           FLAGGED — PORTAL MESSAGE, EMAIL, BILL NOTE, READING TAG (A1–A5)"*);
#           answers OQ-262's high-usage half.
# Rules:    BR-MET-020 / BR-MET-120 (the one definition of "high": above the
#           service's ratio threshold AND above its absolute floor) ·
#           BR-NOT-005 (queue only — nothing here sends) · BR-NOT-018 (the
#           SET-12 row now has a trigger) · CLAUDE.md hard rule 1 (tenant
#           scoping) · rule 3 (every quantity with its unit) · rule 6
#           (idempotency: the queue's own unique key) · rule 7 (the queue write
#           audits itself) · hard-won law 14 (a savepoint around the soft write)
# Tests:    06-backend/tests/test_cr182_high_consumption_alert.py (SQLite and
#           PostgreSQL)
# Impacts:  apps/metering/services.py (`_post_row`, `_supersede_row`,
#           `_cascade_evaluate_actual` call `notify_if_flagged`) ·
#           apps/metering/portal_reads.py (the portal's three reads) ·
#           apps/notifications/rule_catalog.py (`high_usage_alert`) ·
#           apps/notifications/catalogs.py + seed_templates.py
#           (`email_high_usage_alert`)
# ───────────────────────────────────────────────────────
"""A reading flagged HIGH tells the customer, the moment it is saved.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence Susan would recognise:                ║
║  "your water reading on 09/19/2026 was much higher than usual" reaches   ║
║  her inbox and her portal as soon as the reading is flagged — before a   ║
║  clerk has decided whether to bill it as it is or investigate.           ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
"HIGH" IS THE STAFF RULE, VERBATIM — THERE IS NO SECOND DEFINITION
────────────────────────────────────────────────────────────────────────────
PO A6 was not answered and our default (law 13, decision log 2026-10-14) is
that the customer's "high" IS BR-MET-020/120's: the reading's own stored
`rule_outcomes` carries `{"rule": "high", "severity": "warning"}`. Nothing here
recomputes a ratio or reads a threshold, so staff and customer can never
disagree about which readings are high. A rule a utility switched OFF reports
another severity and does not alert — the switch is honoured by construction.

────────────────────────────────────────────────────────────────────────────
THE ALERT IS THE FLAGGED READING ITSELF — WHY THERE IS NO ALERT TABLE
────────────────────────────────────────────────────────────────────────────
The brief for this change said *create one customer alert … mark it resolved
when a corrected reading is no longer high*. Every clause of that is already a
fact the product stores, so a second table would only be a second copy that
could disagree with the first:

  * **ONE alert per reading** — the email is queued keyed on
    (`usage_alert`, the reading's id, `email`), the queue's own unique key
    (hard rule 6). A re-save meets that key and writes nothing.
  * **RESOLVED by a correction** — a correction is a NEW head and the flagged
    row is closed (B2 r8). Every portal read below looks at heads only, so a
    corrected reading that is no longer high simply has no flag to show, and a
    reading that is still high carries its own.
  * **Told ONCE** — when the reading a correction replaces was already
    flagged, the customer has already been emailed about this collection, so
    the replacement does not email again (`REASON_ALREADY_TOLD`). The portal
    still shows the replacement's own flag.

────────────────────────────────────────────────────────────────────────────
METERING WRITES NO NOTIFICATIONS ROW
────────────────────────────────────────────────────────────────────────────
The email goes through `seams.queue_document` — `outbound_messages` is the one
table B1 opens to cross-module writes, and the queue resolves the recipient,
reads the utility's SET-12 rule (`event_key`), pins the template and writes the
audit row itself. A utility that switched *High usage alert* off gets an EMPTY
write that says so; the portal message is unaffected, because A1's in-app
warning is the reading's own flag and not a message anybody queues.

────────────────────────────────────────────────────────────────────────────
IT NEVER RAISES, AND IT RUNS IN ITS OWN SAVEPOINT
────────────────────────────────────────────────────────────────────────────
It is called inside a batch post of up to thousands of readings. An email that
cannot be queued is not a reason to lose a reading, so a failure is logged and
returned as a reason. The savepoint is the only option, not the tidy one: on
PostgreSQL one refused statement aborts the caller's transaction (law 14), and
the sqlite suite cannot show that.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date
from typing import Any

from django.db import transaction

from apps.metering import seams, validation

logger = logging.getLogger("smartbillhub.metering")

#: The outbound queue's source kind for this message (`notifications.models.
#: SOURCE_TYPES`). `source_id` is the READING's id.
SOURCE_USAGE_ALERT = "usage_alert"
#: The SET-12 row this message is (`rule_catalog.EVENTS`).
EVENT_KEY = "high_usage_alert"
#: The one template class it renders from (`catalogs.CATALOGS`).
TEMPLATE_CODE = "email_high_usage_alert"
#: Email only — PO A4 chose email and did not choose SMS.
CHANNELS: tuple[str, ...] = ("email",)

REASON_NOT_HIGH = "not_high"
REASON_NO_ACCOUNT = "no_account"
REASON_ALREADY_TOLD = "already_told"
REASON_QUEUE_UNWIRED = "queue_unwired"
REASON_QUEUE_FAILED = "queue_failed"


def is_flagged_high(rule_outcomes: Iterable[Any] | None) -> bool:
    """True when BR-MET-020/120's `high` rule WARNED on this reading.

    The stored outcome and nothing else — see the module docstring.
    """
    for outcome in rule_outcomes or ():
        if not isinstance(outcome, dict):
            continue
        if outcome.get("rule") == validation.RULE_HIGH and (
            outcome.get("severity") == validation.WARNING
        ):
            return True
    return False


def _read_date(read: Any) -> date | None:
    read_at = getattr(read, "read_at", None)
    return read_at.date() if read_at is not None else None


def _service_code(read: Any) -> str | None:
    from apps.metering import selectors

    point_id = getattr(getattr(read, "asset", None), "service_point_id", None)
    if point_id is None:
        return None
    return selectors.service_codes_for_points({point_id}).get(str(point_id))


def _render_context(read: Any) -> dict[str, Any]:
    """The facts the email states. Every value is one this module already
    holds or reads through a published seam; nothing is invented.

    `usage` carries its UNIT (hard rule 3) — `quantity_with_unit` returns None
    rather than a bare number, and the renderer then prints its named absence.
    """
    from apps.metering import quantity_display

    reference = seams.account_references([read.account_id]).get(str(read.account_id)) or {}
    name = reference.get("customer_name") or None
    code = _service_code(read)
    names = seams.service_names_by_code() if code else {}
    return {
        "customer_name": name,
        # The greeting: the first word of the one name the account carries —
        # `payments.receipts`' judgment (decision log 2026-09-07), reused.
        "first_name": str(name).split()[0] if name else None,
        "account_no": reference.get("account_no") or None,
        # The utility's OWN word for the service, never a code.
        "service_name": names.get(code) if code else None,
        # A DATE, so the renderer formats it in the utility's date format.
        "read_date": _read_date(read),
        "usage": quantity_display.quantity_with_unit(read.consumption, read.unit),
    }


def notify_if_flagged(read: Any, *, replaced: Any = None, actor: Any = None) -> dict[str, Any]:
    """Queue the high-consumption email for ONE freshly written reading.

    `replaced` is the head this reading closed (a correction or a cascade
    recompute), or None for a first reading. Returns `{"alerted": bool,
    "reason": str | None, "messages": [...]}` and never raises.
    """
    if not is_flagged_high(getattr(read, "rule_outcomes", None)):
        return {"alerted": False, "reason": REASON_NOT_HIGH, "messages": []}
    if getattr(read, "account_id", None) is None:
        return {"alerted": False, "reason": REASON_NO_ACCOUNT, "messages": []}
    if replaced is not None and is_flagged_high(getattr(replaced, "rule_outcomes", None)):
        return {"alerted": False, "reason": REASON_ALREADY_TOLD, "messages": []}
    pin = seams.template_pin(TEMPLATE_CODE)
    try:
        # ⚠ THE SAVEPOINT IS THE ONLY OPTION (hard-won law 14).
        with transaction.atomic():
            written = seams.queue_document(
                source_type=SOURCE_USAGE_ALERT,
                source_id=read.id,
                channels=CHANNELS,
                template=pin,
                account_id=read.account_id,
                actor=actor,
                job="metering.high_consumption",
                language=seams.tenant_default_language(),
                on_date=_read_date(read),
                render_context=_render_context(read),
                event_key=EVENT_KEY,
            )
    except Exception:  # noqa: BLE001 — a reading is never lost for an email
        logger.exception(
            "high consumption alert for reading %s could not be queued; the reading "
            "stands and the portal still shows its flag",
            read.id,
        )
        return {"alerted": False, "reason": REASON_QUEUE_FAILED, "messages": []}
    if written is None:
        return {"alerted": False, "reason": REASON_QUEUE_UNWIRED, "messages": []}
    messages = [
        {"channel": m.channel, "created": m.created, "id": m.id}
        for m in getattr(written, "messages", ()) or ()
    ]
    problems = [p.get("code") for p in getattr(written, "problems", ()) or ()]
    return {
        "alerted": bool(messages),
        "reason": None if messages else (problems[0] if problems else None),
        "messages": messages,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE PORTAL'S READS — what is flagged, and which alerts are still open
# ═══════════════════════════════════════════════════════════════════════════


def flagged_read_ids(read_ids: Iterable[Any]) -> set[str]:
    """Of these readings, the ids whose `high` rule warned (A2's bill note).

    By id and not by head: a bill names the readings it PRICED, and a reading
    corrected after the bill went out is still what that bill charged for.
    """
    from apps.metering import models

    wanted = [one for one in read_ids if one]
    if not wanted:
        return set()
    rows = models.MeterRead.objects.filter(id__in=wanted).values_list("id", "rule_outcomes")
    return {str(read_id) for read_id, outcomes in rows if is_flagged_high(outcomes)}


def open_alerts_for_accounts(account_ids: Iterable[Any]) -> list[dict[str, Any]]:
    """A1 — the alerts the portal Home shows while they are open.

    An alert is OPEN while its flagged reading is the LATEST head on its meter
    (a newer reading, or a correction that is no longer high, closes it) and has
    not yet been billed (once billed, the Home notice becomes *Your last bill is
    higher than usual*, which `apps/portal/selectors` derives from the bill).

    One row per meter, newest first. No id leaves this function (B14 rule 31):
    the screen names the reading by its service and its date.
    """
    # The flat meter's single register — the customer's *what did my meter
    # say*; a TOU window is a different quantity of the same unit.
    from apps.metering import models, selectors

    ids = [one for one in account_ids if one]
    if not ids:
        return []
    heads = (
        selectors._read_heads()
        .filter(account_id__in=ids, channel=models.CHANNEL_TOTAL)
        .select_related("asset")
        .order_by("asset_id", "-read_at", "-id")
    )
    latest: dict[str, Any] = {}
    for head in heads:
        latest.setdefault(str(head.asset_id), head)
    open_rows = [
        head
        for head in latest.values()
        if head.lifecycle != "billed" and is_flagged_high(head.rule_outcomes)
    ]
    if not open_rows:
        return []
    services = selectors.service_codes_for_points(
        {h.asset.service_point_id for h in open_rows if h.asset.service_point_id}
    )
    open_rows.sort(key=lambda h: h.read_at, reverse=True)
    return [
        {
            "service": (
                services.get(str(h.asset.service_point_id)) if h.asset.service_point_id else None
            ),
            "taken_on": h.read_at.date().isoformat(),
        }
        for h in open_rows
    ]

