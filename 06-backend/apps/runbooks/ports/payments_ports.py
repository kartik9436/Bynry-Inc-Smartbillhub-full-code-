# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-002 (a Check holds none) · BR-RBS-018 (a
#           money-bearing action carries a second approval) · CLAUDE.md hard
#           rule 4 (payments are append-only apart from three named columns)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 · apps/runbooks/interfaces.py
# ───────────────────────────────────────────────────────
"""Six ports owned by `payments` — the largest group. **All six bound.**

⚠ **THIS DOCSTRING SAID *"None is bound"* UNTIL 2026-09-06, AND *"Five"*
UNTIL 2026-09-07.** Wave L task L2 puts one service function in the owning
module behind each, in
`apps/payments/runbook_ports.py`, and every one of them writes a NEW ROW —
`apply_payment` records a payment, `post_credit` writes allocations,
`raise_refund` writes a REQUEST, `record_match` names a pairing,
`schedule_retry` writes an intent. **Not one of them updates anything**, which
is hard rule 4 expressed in the shape of the code.

Payments is the module this one can do the most to, which is why the dry half of
phase 4 exists: the ports, the cap, the stop, the idempotency key and the audit
actor all run against real accounts in production for a full cycle **while being
unable to do anything**, and turning them on is then a one-line change to a
runbook's kind rather than a first outing.

⚠ **EVERY ONE OF THESE IS MONEY-BEARING, SO EVERY ONE CARRIES THE SECOND
APPROVAL** (`BR-RBS-018`). The threshold above which it applies is the Product
Owner's and was `OQ-RBS-1732`. ⚠ **THAT QUESTION IS CLOSED — PO 2026-09-06:
every money-bearing action carries the second approval and there is NO
threshold.** So there is no threshold argument on any writer below and adding
one would be a new ruling, not a refinement: a threshold can only ever widen
what an automation may do unattended.

⚠ **A PAYMENT ROW IS APPEND-ONLY** apart from the three columns hard rule 4 was
narrowed for on 2026-09-02. None of these ports touches those three, and none of
them may ever be widened into an UPDATE: a correction is a new row, performed by
payments' own service, and this module asks for it rather than doing it.
"""

# ⚠ A FOREIGN IMPORT IN ONE OF THE TWO LAWFUL DOORS (`G115` rule 1). It names
# the owning module's own service functions and nothing else.
from apps.payments import runbook_ports as payments_writers

from apps.runbooks.boundary import PortDeclaration

APPLY_PAYMENT = PortDeclaration(
    name="apply_payment",
    owning_module="payments",
    what_it_does="Applies a landed payment by the allocation order",
    writer=payments_writers.apply_payment,
)

POST_CREDIT = PortDeclaration(
    name="post_credit",
    owning_module="payments",
    what_it_does="A credit to an open account",
    writer=payments_writers.post_credit,
)

RAISE_REFUND = PortDeclaration(
    name="raise_refund",
    owning_module="payments",
    what_it_does="A refund awaiting its own approval",
    writer=payments_writers.raise_refund,
)

RECORD_MATCH = PortDeclaration(
    name="record_match",
    owning_module="payments",
    what_it_does="A bank line matched to a deposit batch",
    writer=payments_writers.record_match,
)

SCHEDULE_RETRY = PortDeclaration(
    name="schedule_retry",
    owning_module="payments",
    what_it_does="A retry of a failed debit",
    writer=payments_writers.schedule_retry,
)

#: ⚠ **THE FOURTEENTH PORT, ADDED 2026-09-07 BY `CR-075` WAVE `N` AND THE ONLY
#: ONE THIS PROJECT HAS EVER ADDED.** `12-the-contract.md` §6 anticipates it in
#: as many words — *"a new runbook that needs a new port is adding a reviewed
#: interface, not a custom write"* — and this is the review: the reasoning is
#: `DEF-RBS-4347`'s ruling in `12-governance/02-decision-log.md`, and the count
#: moved in `interfaces.py`, `boundary.py`, `12-the-contract.md` §6 and
#: `test_us_rbs_041_module.py` in the same commit.
#:
#: **Why it had to exist.** A collections step is three writes — the queue row,
#: the `notice_history` row and the `account_collection_state` tier — and the
#: last two are PAYMENTS' tables under `BR-PAY-017`. Runbook 8 held only
#: `queue_notice`, which is `notifications`', so **the ladder never climbed**:
#: 512 state rows before wave `M`'s month and 512 after, and no notice history
#: at either end. Nothing else could close that: the runbook writing payments'
#: state is a second writer of a signed rule, and `notifications` writing it is
#: a cross-module write. The act belongs to the module that owns the state.
#:
#: ⚠ **IT IS NOT `queue_notice` RENAMED.** `queue_notice` stays exactly as it
#: is and is still the right port for runbooks 11, 15 and 17, which queue a
#: message and move no collections state at all.
STEP_LADDER = PortDeclaration(
    name="step_ladder",
    owning_module="payments",
    what_it_does="One collections step: the notice, its record and the tier",
    writer=payments_writers.step_ladder,
)

PORTS = (
    APPLY_PAYMENT,
    POST_CREDIT,
    RAISE_REFUND,
    RECORD_MATCH,
    SCHEDULE_RETRY,
    STEP_LADDER,
)
