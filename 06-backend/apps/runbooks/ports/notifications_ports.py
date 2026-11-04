# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-002 (a Check holds none) · BR-RBS-008 (idempotent
#           per record) · CLAUDE.md hard rule 7 (every money action writes
#           audit_log — the ENGINE writes it, not the port)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 · apps/runbooks/interfaces.py
# ───────────────────────────────────────────────────────
"""Two ports owned by `notifications`. **Both bound from `CR-075` wave L.**

⚠ **THIS DOCSTRING SAID *"Neither is bound"* UNTIL 2026-09-06 AND IT WAS TRUE
UNTIL THE COMMIT THAT CHANGED IT.** Wave L task L2 puts one service function in
the owning module behind each — `apps.notifications.runbook_ports.queue_notice`
and `.queue_receipt` — and `G115` prints `2 bound` instead of `0 bound` where it
used to. **Nothing is SENT by either**: both write a queue row and the
dispatcher sends, no delivery provider is connected, and no runbook is on
`engine.acts.LIVE_ENABLED_RUNBOOKS`, so a dry run reaches a writer-less copy of
these declarations and records what it WOULD do (`BR-RBS-003`).

⚠ **A NOTICE CANNOT BE UNSENT.** These two are the reason phase 4 is split into
a dry half and a live half, and the reason the cap, the batch approval and the
stop button are first-release requirements rather than hardening for later. The
failure that hurts is not a runbook doing nothing — somebody notices that — it
is a misconfigured runbook queueing three thousand wrong disconnection notices
in four minutes.

Each maps to ONE service function in `notifications`, is **idempotent per
record** (the `UNIQUE (tenant_id, idempotency_key)` index on
`runbook_run_records` is what makes that true rather than hoped for), and its
audit row is written **by the engine**, naming the runbook and its version as
the actor — never by the port.
"""

# ⚠ A FOREIGN IMPORT, AND THIS FILE IS ONE OF THE TWO DOORS WHERE IT IS LAWFUL
# (`G115` rule 1: `seams/<x>_seam.py` reads, `ports/<x>_ports.py` writes). It
# names the OWNING module's own service function and nothing else — no model,
# no queryset, no ORM verb — because a write performed here rather than there
# would be the cross-module write B2 §2 forbids, and `G115` fails an ORM write
# on a foreign model even inside this door.
from apps.notifications import runbook_ports as notifications_writers

from apps.runbooks.boundary import PortDeclaration

QUEUE_NOTICE = PortDeclaration(
    name="queue_notice",
    owning_module="notifications",
    what_it_does="Writes a queue row; the dispatcher sends",
    writer=notifications_writers.queue_notice,
)

QUEUE_RECEIPT = PortDeclaration(
    name="queue_receipt",
    owning_module="notifications",
    what_it_does="A receipt document to the queue",
    writer=notifications_writers.queue_receipt,
)

PORTS = (QUEUE_NOTICE, QUEUE_RECEIPT)
