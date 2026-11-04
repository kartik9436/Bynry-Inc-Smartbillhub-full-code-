# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 task `P4.14`
#          (*"BI tier 2 — scheduled delivery"*), brief p015 (the task row),
#          §7.8 p088–p089 (the tier table) and p090 (the decisions register),
#          read as IMAGES per B14 rule 42.
# Rules:   **RULED, p090, FINAL:** *"A scheduled file may leave the product —
#          Yes — admin-set destinations, encrypted in transit, every delivery
#          logged."* · **RULED, p089:** this does NOT reopen `BR-REP-020` ·
#          `BR-REP-020` CONFIRMED (a schedule's recipients are this tenant's
#          own users) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 6
#          (idempotency) · hard rule 7 (every money action writes `audit_log`)
#          · the PRIME DIRECTIVE (a lane never resolves an open question by
#          choosing a value) · hard-won law 2's mirror (never a live control
#          over a refusal) · law 3 (defaults fail closed)
# Open:    **OQ-REP-12767 — OPEN.** Whose host key does an SFTP destination
#          trust, and where is the credential kept? NOT answered here.
# Tests:   06-backend/tests/test_cr142_p4_14_signed_delivery.py
# Impacts: apps/reports/models.py (`ReportDestination`, `ReportDelivery`,
#          `ReportSchedule.destination`) · apps/reports/delivery.py (the sweep
#          that calls `deliver`) · apps/reports/signed_links.py
# ───────────────────────────────────────────────────────
"""WHERE A SCHEDULED FILE MAY GO, AND THE ONE TRANSPORT THAT IS BUILT.

THE RULING, AND ITS THREE CONDITIONS MAPPED TO CODE
───────────────────────────────────────────────────
Brief p015, verbatim: *"The scheduler already writes a file; send it to **SFTP
or a signed URL** on a timer. **Ruled, with three conditions:** destinations are
set up **by an administrator** and never by whoever creates the schedule;
**encrypted in transit**; **every delivery logged**."*

  1 · **an administrator sets it up** → `ReportDestination` is its own table
      with its own role gate (`create`, below). A schedule POINTS at a row; it
      cannot describe a destination. p015's worked failure is the reason:
      *"Without the first, a clerk schedules the debtor list — 412 names,
      addresses and balances — to a personal address and nothing records it."*
  2 · **encrypted in transit** → the one transport built here is HTTPS, and the
      link is refused over anything else (`_require_https`).
  3 · **every delivery logged** → a `ReportDelivery` row AND a `audit_log`
      entry, written in the same transaction as the send. Two records, two
      questions — the `ReportDelivery` docstring says which is which.

════════════════════════════════════════════════════════════════════════════
⚠ **SFTP IS NOT BUILT, AND THAT IS A STUB WITH AN ID, NOT AN OVERSIGHT**
════════════════════════════════════════════════════════════════════════════
The ruling names SFTP and this module refuses it BY NAME with `OQ-REP-12767`.
Two separate things are missing and only one of them is code:

**(a) A DECISION NOBODY HAS MADE.** An SFTP client has to decide what to do
the first time it meets a host key. *Accept whatever the server presents* is
the default of every convenient library and it is a man-in-the-middle with no
symptom: the file goes somewhere, the transfer succeeds, the delivery is logged
as sent, and the bytes — *"412 names, addresses and balances"* — are read by
whoever answered. The alternative, pinning a fingerprint the utility gives us,
is a fact **only the customer holds** (CLAUDE.md law 13's third bullet) and
changes what an administrator must type on the set-up form. **A lane may not
pick one.** Nothing in `12-governance/02-decision-log.md` or
`01-open-questions.md` mentions a host key — grepped, zero hits, 2026-09-27 —
so this is a new question rather than a re-ask (law 13).

**(b) NO CLIENT.** `paramiko`, `pysftp` and `asyncssh` are all absent from this
deployment — checked, not assumed. `apps/integrations/manifests/accounting_file.py`
already met this exact wall and its posture is the one copied here: the path is
complete, the absence is NAMED, and a bound writer runs the whole thing.

⚠ **AND THE REFUSAL IS AT THE *CREATE*, NOT ONLY AT THE SEND — WHICH IS LAW 2's
MIRROR.** A destination of kind `sftp` that could be created and then failed
every night would be a live control over a dead transport: an administrator
would see it in the picker, a clerk would choose it, and the failure would
arrive as an operational mystery weeks later. So `create` refuses the kind
outright and the picker has nothing to offer. When `OQ-REP-12767` is answered,
the refusal moves and the form gains a field — one commit, both halves.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction

from core import audit as core_audit
from core import errors

from apps.reports import models as reports_models, signed_links

#: The open question this module will not answer for itself.
SFTP_QUESTION = "OQ-REP-12767"

#: What `create` says when somebody asks for the transport that is not built.
#: A SENTENCE a person can act on, naming both halves — hard-won law 7's
#: *a check's output must distinguish pass from fail TO A READER*.
SFTP_NOT_BUILT = (
    "an SFTP destination cannot be created yet: nothing has ruled whose host "
    f"key it trusts ({SFTP_QUESTION}), and no SSH client is installed on this "
    "deployment. A signed link is available now."
)


def create(
    tenant_id: Any, *, name: str, kind: str, actor_user_id: Any, config: Any = None
):
    """An ADMINISTRATOR adds a destination. Condition 1 of the ruling.

    ⚠ **THE ROLE GATE IS THE CALLER'S AND IT IS NOT OPTIONAL** — `api.py`
    declares it, the same way `service_accounts` issue does, because a
    permission enforced in a service that an internal caller can reach around
    is a permission nobody has. `created_by_user_id` records WHO, which is what
    makes the ruling's first condition auditable afterwards rather than merely
    true at the moment it was typed.
    """
    if kind == reports_models.DESTINATION_SFTP:
        # Prime directive: implement to the boundary and stub the gap with the
        # OQ id IN THE CODE. See the module docstring for both halves of why.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-REP-020",
            message_key="reports.destination.sftp_not_built",
            params={"question": SFTP_QUESTION},
        )
    if kind not in reports_models.DESTINATION_KINDS:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="reports.destination.unknown_kind",
            params={"kind": str(kind)},
            field_errors=[{"field": "kind", "code": errors.VAL_FORMAT}],
        )

    row = reports_models.ReportDestination.objects.create(
        tenant_id=tenant_id,
        name=name,
        kind=kind,
        config=config or {},
        created_by_user_id=actor_user_id,
    )
    core_audit.write_row(
        action="report_destination.created",
        entity_type="report_destination",
        entity_id=row.id,
        actor_user_id=actor_user_id,
        # ⚠ The NAME and the KIND, never the config — a config that ever holds
        # a credential must not reach the audit row, and the rule is easier to
        # keep if it was never written in the first place.
        after={"name": name, "kind": kind},
    )
    return row


def deliver(
    schedule: Any, *, job_id: Any, now: datetime, actor_user_id: Any = None
) -> Any | None:
    """Send ONE finished run's file to the schedule's destination, ONCE.

    Answers the `ReportDelivery` row, or `None` when the schedule names no
    destination — which is the ordinary case and is not a failure.

    ⚠ **HARD RULE 6 IS THE DATABASE'S HERE, NOT THIS FUNCTION'S MEMORY.**
    `delivery.py` RECONCILES on every beat rather than hooking the job's end
    (its docstring says why), so this will meet the same `(schedule, job,
    destination)` again in sixty seconds. The unique constraint refuses the
    second row and the `IntegrityError` is caught as *already delivered*,
    rather than this code asking *have I done this* and racing itself.

    ⚠ **AND THE `except` TAKES A SAVEPOINT** — CLAUDE.md hard-won law 14. On
    PostgreSQL a failed statement aborts the WHOLE transaction, so catching
    `IntegrityError` and carrying on loses everything afterwards at COMMIT. The
    suite runs on SQLite, which has no aborted-transaction state, so the version
    without the savepoint passes every test on every machine and fails the first
    time two beats overlap in production. The nested `atomic()` is not the tidy
    option; it is the only one.

    ⚠ **`now` IS A PARAMETER** (`BR-TEN-043`) — the sweep holds the beat's own
    moment, so a test can state the hour the link was minted and the hour it
    expires.
    """
    from django.db import IntegrityError

    destination = schedule.destination
    if destination is None or not destination.enabled:
        return None

    if destination.kind == reports_models.DESTINATION_SFTP:
        # Unreachable through `create` today; asserted here anyway, because a
        # row written by a migration or a fixture must not silently do nothing.
        raise NotImplementedError(SFTP_QUESTION)

    token, expires_at = signed_links.mint(
        tenant_id=schedule.tenant_id, job_id=job_id, now=now
    )
    try:
        with transaction.atomic():  # the SAVEPOINT — see the docstring
            row = reports_models.ReportDelivery.objects.create(
                tenant_id=schedule.tenant_id,
                destination=destination,
                schedule=schedule,
                job_id=job_id,
                status=reports_models.ReportDelivery.STATUS_SENT,
                expires_at=expires_at,
            )
    except IntegrityError:
        # Already delivered on an earlier beat. Not an error, and NOT a second
        # send: the file has left once and the link it left with is still the
        # one in the recipient's hands.
        return None

    core_audit.write_row(
        action="report_delivery.sent",
        entity_type="report_delivery",
        entity_id=row.id,
        actor_user_id=actor_user_id,
        # ⚠ **THE TOKEN IS NOT IN THE AUDIT ROW.** It is a bearer credential;
        # an audit log a support engineer can read is an audit log that hands
        # out the file. What is recorded is that a link was issued, to which
        # destination, for which job, and when it dies.
        after={
            "destination": destination.name,
            "kind": destination.kind,
            "job_id": str(job_id),
            "expires_at": expires_at.isoformat(),
        },
    )
    row.token = token  # transient, for the caller that hands it to the transport
    return row


# gates: pytest tests/test_cr142_p4_14_signed_delivery.py · G78 is not in scope
#        (reports writes only its own tables here)
# exceptions: the `sftp` kind is REFUSED at create and raises at send —
#   `OQ-REP-12767`, OPEN. Not a missing feature: a decision nobody has made
#   plus a client nobody has installed. Both halves are in the module docstring.
# status: VERIFIED-UNRATIFIED
