# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10161 — portal stop asks raised before 2.580.0 have no
#           `temporary_stops` row, so they read "Not yet classified" and the
#           clerk cannot approve them as a temporary stop.
# Change:   CR-183-BRC10 (2.580.0) — the row the portal ask writes since then.
# Rules:    BR-CUS-1120 · BR-CWP-026 (the ask changes no account) ·
#           CLAUDE.md hard rules 1 (tenant scoped), 7 (audit every change)
# Tests:    06-backend/tests/test_def_cus_10161_temporary_stop_backfill.py
# Runs from: customers/0086 (once, on upgrade) and
#           `manage.py backfill_temporary_stops` (any time, on a host)
# ───────────────────────────────────────────────────────
"""**Give every pre-2.580 portal *stop my service* ask its temporary-stop row.**

WHY THIS EXISTS
---------------
Since 2.580.0 the portal ask stores its account, dates and reason in a
`temporary_stops` row (`temporary_stop.record_from_portal`), and that ROW is
what makes a request a *Temporary stop* (`kind_of`, `kinds_for`,
`for_request`). An ask raised on 2.575.1 or earlier wrote only the clerk's
sentence, so after the upgrade it stays *Not yet classified* and its Approve
offers New connection / Move-in — the clerk has no way to process it.

WHERE THE FACTS COME FROM
-------------------------
From the sentence the portal ITSELF composed (`portal.services.STOP_RESTART_NOTE`
via `_stop_restart_words`), which has not changed shape since it was written:

    Asked through the customer portal to stop service on account
    <ACCOUNT_NO> from <YYYY-MM-DD>, starting again on <YYYY-MM-DD>.
    The account stays open and standing charges keep running. <reason>

or `…from <YYYY-MM-DD>, with no restart date given. …` when the customer gave
none. `SENTENCE` below matches exactly that and nothing looser.
`test_def_cus_10161_…` generates the sentence with the portal's own function
and asserts the round trip, so the writer and this reader cannot drift.

⚠ **THIS IS A ONE-TIME MIGRATION OF OLD DATA, NOT A CLASSIFIER.** `kind_of`'s
own rule — *"Read from the ROW the ask wrote, never from its sentence"* — still
holds for every request: this function WRITES the row the old ask never wrote,
through the same `record_from_portal` the live ask calls, and from then on the
row is what classifies it.

WHAT IT TOUCHES — AND WHAT IT LEAVES ALONE
------------------------------------------
* Only a request still awaiting a decision (`APPROVE`'s from-states:
  submitted, under review, more info). A refused, approved, completed,
  withdrawn or closed request is history and is never touched.
* Only one whose sentence opens with the stop marker and has no row yet
  (as an ask or as a restart) — so a second run writes nothing (idempotent).
* A sentence that does not parse (an account the customer did not state, a
  date that is not ISO) and one naming an account this utility does not hold
  are LEFT EXACTLY AS THEY ARE and COUNTED, so the printed line says how many
  a clerk must still handle by hand. Nothing is guessed.
* Nothing on any account moves: the row is `requested`, exactly what the live
  ask writes, and a clerk still decides (BR-CWP-026). B3's limits are an
  approval rule, so a 3-day ask is stored as asked and the Approve window
  refuses it by name with the dates editable.

Each row is written in its own savepoint (hard-won law 14): one request that
fails does not abort the rest on PostgreSQL. Each written row carries the live
path's `temporary_stop.requested` audit row plus `temporary_stop.backfilled` on
the request, naming the request number and the build that did it.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from django.db import transaction

from apps.customers import models
from apps.customers import service_request as rules
from apps.customers import temporary_stop
from apps.customers.temporary_stop_models import TemporaryStop
from core import audit as core_audit
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.customers.temporary_stop_backfill")

#: The portal's marker (`portal.seams.customers_seam.STOP_RESTART_MARKER`),
#: repeated here because `customers` does not import `portal` (B2 §2). The
#: round-trip test asserts the two are the same string.
STOP_RESTART_MARKER = "Asked through the customer portal to stop service on account"

#: The whole sentence `portal.services._stop_restart_words` composes. Account
#: numbers carry no space; "not stated" (the portal's word for a missing one)
#: therefore does not match and the request is counted as unparseable.
SENTENCE = re.compile(
    re.escape(STOP_RESTART_MARKER) + r" (?P<account_no>\S+) from (?P<stop_from>\d{4}-\d{2}-\d{2})"
    r"(?:, starting again on (?P<restart_on>\d{4}-\d{2}-\d{2})|, with no restart date given)"
    r"\. The account stays open and standing charges keep running\."
    r"(?: (?P<reason>.+))?\Z",
    re.DOTALL,
)

#: The states a request is still awaiting a decision in — the only ones a
#: clerk can approve, so the only ones a row helps.
OPEN_STATES: tuple[str, ...] = tuple(rules.TRANSITIONS[rules.APPROVE][0])

AUDIT_ACTION = "temporary_stop.backfilled"


def parse(said: Any) -> dict[str, Any] | None:
    """The account number, dates and reason in a portal stop sentence, or None."""
    match = SENTENCE.match(str(said or "").strip())
    if match is None:
        return None
    try:
        stop_from = date.fromisoformat(match["stop_from"])
        restart_on = date.fromisoformat(match["restart_on"]) if match["restart_on"] else None
    except ValueError:
        return None
    reason = (match["reason"] or "").strip() or None
    return {
        "account_no": match["account_no"],
        "stop_from": stop_from,
        "restart_on": restart_on,
        "reason": reason,
    }


def candidates() -> Any:
    """The current tenant's open stop asks that have no row yet."""
    tenant_id = core_tenancy.current_tenant_id()
    have = TemporaryStop.objects.filter(tenant_id=tenant_id)
    taken = set(have.values_list("request_id", flat=True)) | set(
        have.exclude(restart_request_id=None).values_list("restart_request_id", flat=True)
    )
    return (
        models.ServiceRequest.objects.filter(
            tenant_id=tenant_id,
            state__in=OPEN_STATES,
            what_they_said__startswith=STOP_RESTART_MARKER,
        )
        .exclude(id__in=[value for value in taken if value is not None])
        .order_by("created_at", "id")
    )


def backfill_current_tenant(*, dry_run: bool = False) -> dict[str, Any]:
    """Run the backfill for the tenant in context. Returns the counts and the
    request numbers left alone, so a person can find them."""
    found = {"created": 0, "unparseable": 0, "account_missing": 0, "failed": 0}
    left: list[str] = []
    for request in candidates():
        facts = parse(request.what_they_said)
        if facts is None:
            found["unparseable"] += 1
            left.append(request.request_no)
            continue
        account = models.Account.objects.filter(
            tenant_id=request.tenant_id, account_no=facts["account_no"]
        ).first()
        if account is None:
            found["account_missing"] += 1
            left.append(request.request_no)
            continue
        if dry_run:
            found["created"] += 1
            continue
        try:
            # ⚠ A SAVEPOINT, NOT A TIDY OPTION (hard-won law 14): on PostgreSQL a
            # failed statement poisons the transaction, so one bad request would
            # otherwise abort every row after it.
            with transaction.atomic():
                stop = temporary_stop.record_from_portal(
                    request.id,
                    account_id=account.id,
                    stop_from=facts["stop_from"],
                    restart_on=facts["restart_on"],
                    reason=facts["reason"],
                )
                core_audit.write_row(
                    action=AUDIT_ACTION,
                    entity_type="service_request",
                    entity_id=request.id,
                    automation=core_audit.AutomationActor(
                        kind="job", name="Temporary stop backfill", version="DEF-CUS-10161"
                    ),
                    before=None,
                    after={
                        "request_no": request.request_no,
                        "temporary_stop_id": str(stop.id),
                        "account_no": account.account_no,
                        "stop_from": facts["stop_from"].isoformat(),
                        "restart_on": facts["restart_on"].isoformat()
                        if facts["restart_on"]
                        else None,
                        "source": "DEF-CUS-10161",
                    },
                )
        except Exception:  # noqa: BLE001 - counted and logged, never swallowed silently
            logger.exception("temporary-stop backfill failed for %s", request.request_no)
            found["failed"] += 1
            left.append(request.request_no)
            continue
        found["created"] += 1
    return {**found, "left": left}


def backfill_all_tenants(*, dry_run: bool = False) -> dict[str, Any]:
    """Every tenant, each under its own `app.tenant_id` (hard rule 1)."""
    from apps.tenancy import models as tenancy_models

    totals = {"tenants": 0, "created": 0, "unparseable": 0, "account_missing": 0, "failed": 0}
    left: list[str] = []
    for tenant_id in tenancy_models.Tenant.objects.order_by("id").values_list("id", flat=True):
        with core_tenancy.tenant_context(tenant_id):
            report = backfill_current_tenant(dry_run=dry_run)
        totals["tenants"] += 1
        for key in ("created", "unparseable", "account_missing", "failed"):
            totals[key] += report[key]
        left.extend(report["left"])
    return {**totals, "left": left}


def summary(report: dict[str, Any]) -> str:
    """One line a person reads after the migration or the command."""
    line = (
        f"temporary-stop backfill: {report['created']} portal stop request(s) given a "
        f"temporary stop; left alone: {report['unparseable']} unreadable, "
        f"{report['account_missing']} naming no account here, {report['failed']} failed"
    )
    if report.get("left"):
        line += " (" + ", ".join(report["left"]) + ")"
    return line
