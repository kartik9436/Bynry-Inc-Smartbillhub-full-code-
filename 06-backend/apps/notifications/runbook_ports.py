# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-014 (EP-RBS-04) — CR-075 wave L task L2: the
#           two ports notifications owns, bound to ONE service function each,
#           in the module that owns the table.
# Rules:    BR-RBS-022 (a runbook reaches another module ONLY through a named
#           port, into the owning module's own service) · BR-NOT-005 (a notice
#           is WRITTEN to the outbound table; only the dispatcher sends) ·
#           BR-RBS-015 (the runbook is the audit actor) · CLAUDE.md hard rule 6
#           (idempotency) · hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_us_rbs_010_port_writers.py
# Impacts:  apps/runbooks/ports/notifications_ports.py (binds these two)
# ───────────────────────────────────────────────────────
"""The two writes a runbook may make in this module — and neither of them SENDS.

⚠ **THIS FILE LIVES IN `notifications`, NOT IN `runbooks`, AND THAT IS THE
WHOLE POINT OF A PORT.** `BR-RBS-022`: a runbook reaches another module only
through a named port, and a port maps to exactly ONE service function in the
OWNING module. So the list of everything the automation can ever do to this
module's rows is the two functions below, in this module's own directory, where
this module's reviewers read them — rather than thirteen scattered writes in a
module that does not own any of the tables. `G115` refuses an ORM write on a
foreign model anywhere under `apps/runbooks`, which is the machine half of the
same sentence.

⚠ **NOTHING HERE SENDS ANYTHING, IN ANY MODE, EVER** (`BR-NOT-005`, and
`RBR-07`, PO ruling 17 August 2026). Both functions QUEUE a row; the dispatcher
sends, and no delivery provider is connected. The word on every result screen is
**Queued**, never *Sent*. That is why `queue_notice` is the port the collections
ladder holds and why a misconfigured ladder in wave `L` cannot post a letter.

⚠ **NEITHER FUNCTION WRITES A RUNBOOK'S AUDIT ROW.** The engine does
(`apps/runbooks/engine/acts.py`), naming the runbook and its version as the
actor. What these DO write is this module's OWN rule-7 row for the queue write —
which is `queue_document`'s obligation and predates runbooks — and they hand the
runbook's `AutomationActor` down as the actor so **that** row is named too
rather than reading as an anonymous system job. `core.audit.money_action`
branches on `AutomationActor` before it reaches for `.id`, so this works and is
not an accident of duck typing.

⚠ **IDEMPOTENCY IS THE OWNING MODULE'S OWN, AND IT IS A SECOND LAYER RATHER
THAN THE ONLY ONE.** `queue_document` is already idempotent on
`(tenant, source_type, source_id, channel, copy_no)` and returns `created=False`
for a row that was already there. The runbook's per-record key
(`engine/acts.py`) is the first layer. Two layers is deliberate: the runbook's
key stops the ACT being planned twice, and this stops the ROW being written
twice even if some other caller got there first.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from apps.notifications import models, services

#: The namespace the deterministic `source_id` of a runbook-queued document is
#: minted in. A UUID5 rather than a random one **because the id IS part of the
#: idempotency**: the same subject at the same rung must produce the same
#: `source_id`, or `queue_document`'s own duplicate check has nothing to match
#: on. `apps/payments/notices.py::plan_notice_source_id` mints its ids exactly
#: this way and for exactly this reason.
RUNBOOK_SOURCE_NAMESPACE = uuid.UUID("6f1c1f2a-0a5e-5c3e-9a2f-9b7c4d5e6f70")


def runbook_source_id(*, runbook_key: str, subject_id: Any, discriminator: str) -> uuid.UUID:
    """The stable `source_id` for one runbook act. Same inputs, same id, always."""
    return uuid.uuid5(
        RUNBOOK_SOURCE_NAMESPACE, f"{runbook_key}|{subject_id}|{discriminator}"
    )


def queue_notice(
    *,
    actor: Any,
    runbook_key: str,
    account_id: Any,
    subject_id: Any,
    discriminator: str,
    channels: Sequence[str] = (models.CHANNEL_EMAIL,),
    recipients: Sequence[services.Recipient] = (),
    template: services.TemplatePin | None = None,
    render_context: Mapping[str, Any] | None = None,
    dispatch_not_before: Any = None,
) -> dict[str, Any]:
    """PORT `queue_notice` — write a queue row. **The dispatcher sends; this does not.**

    `BR-RBS-022` names this the notifications half of the collections ladder's
    two ports. `BR-NOT-005` is what it obeys: a notice is WRITTEN to
    `outbound_messages` and only the dispatcher sends it, so a runbook that
    queues 812 rows has sent nothing and a clerk reading the result sees
    **Queued**.

    `dispatch_not_before` carries `BR-NOT-009`'s quiet hours and is a PARAMETER
    rather than a clock read (`BR-TEN-043`, gate `G6`) — the runbook knows the
    tenant's quiet window; this module never reads a wall clock.

    Returns what the engine's audit row is written from: whether THIS call
    created anything, the rows it names, and the problems it could not solve.
    **A channel with no address still gets a row** — that is `queue_document`'s
    own law, and it is why an undeliverable customer leaves a trace instead of
    a silence.
    """
    source_id = runbook_source_id(
        runbook_key=runbook_key, subject_id=subject_id, discriminator=discriminator
    )
    write = services.queue_document(
        source_type="notice",
        source_id=source_id,
        channels=tuple(channels),
        template=template,
        account_id=account_id,
        recipients=tuple(recipients),
        dispatch_not_before=dispatch_not_before,
        render_context=dict(render_context or {}),
        actor=actor,
        job=f"runbook:{runbook_key}",
    )
    return _answer(write, entity_type="outbound_message")


def queue_receipt(
    *,
    actor: Any,
    runbook_key: str,
    account_id: Any,
    subject_id: Any,
    discriminator: str,
    channels: Sequence[str] = (models.CHANNEL_EMAIL,),
    recipients: Sequence[services.Recipient] = (),
    template: services.TemplatePin | None = None,
    render_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """PORT `queue_receipt` — a receipt document to the queue, for a landed payment.

    Separate from `queue_notice` and not a parameter of it, because
    `source_type` decides this module's PRINT FLOOR: a receipt files under
    `payment` and a dunning letter under `notice`, and `CHANNEL_FLOOR_BY_SOURCE`
    is keyed on that value. Collapsing the two into one function with a `kind`
    argument would put a runbook one typo away from posting a receipt under a
    disconnection notice's floor — the same class of mistake `CR-068` wave E
    recorded when a six-digit portal code nearly went out by letter.
    """
    source_id = runbook_source_id(
        runbook_key=runbook_key, subject_id=subject_id, discriminator=discriminator
    )
    write = services.queue_document(
        source_type="payment",
        source_id=source_id,
        channels=tuple(channels),
        template=template,
        account_id=account_id,
        recipients=tuple(recipients),
        render_context=dict(render_context or {}),
        actor=actor,
        job=f"runbook:{runbook_key}",
    )
    return _answer(write, entity_type="outbound_message")


def _answer(write: services.QueueWrite, *, entity_type: str) -> dict[str, Any]:
    """One shape for both ports, so the engine's audit row is written once.

    `created` is the honest half and it is the one the Records table draws:
    False means the row was already there — a replay, a resumed batch, a second
    run of the ladder — and **a clerk must never be told a message was queued
    twice**.
    """
    return {
        "entity_type": entity_type,
        # `QueueWrite.created` is a TUPLE of the rows THIS call wrote, not a
        # flag — so the boolean is derived here rather than read, and the count
        # travels beside it so a reader of the audit row can tell *one channel
        # queued* from *three*.
        "created": bool(write.created),
        "created_count": len(write.created),
        "message_ids": [message.id for message in write.messages],
        "channels": list(write.channels),
        "already": [message.id for message in write.already_queued],
        "problems": [dict(problem) for problem in write.problems],
        # Stated as a VALUE rather than only in prose (hard-won law 1): nothing
        # left the building, and a test can assert it.
        "dispatched": bool(write.dispatched),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 · US-RBS-014 (EP-RBS-04; CR-075 wave L task L2)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — a port is called by the engine, never over HTTP) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path here: the idempotency KEY is composed in apps/runbooks/engine/acts.py, which is on the guarded list; this file only passes a derived source id to an existing write door)
# gates: pytest tests/test_us_rbs_010_port_writers.py · G115 (the census that keeps this write OUT of apps/runbooks) · G6 (no clock read)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
