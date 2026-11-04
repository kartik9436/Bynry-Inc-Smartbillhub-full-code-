# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4: the two registries.
# Rules:    BR-RBS-022 (a runbook reaches another module ONLY through a named
#           port; work items and audit rows are the ENGINE's) · BR-RBS-002 (a
#           Check is CONSTRUCTED with no ports) · BR-RBS-039 (a read goes
#           through a seam this module owns; every seam is a row in the
#           cross-module interface register)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  apps/runbooks/seams/*_seam.py · apps/runbooks/ports/*_ports.py ·
#           B2 Addendum r25 (the register rows)
# ───────────────────────────────────────────────────────
"""The whole boundary of this module, in one importable place: 9 seams, 15 ports.

**Every import below is `apps.runbooks.*` — this module's own.** That is the
point: the registry can be read, counted and asserted without importing a single
line of another module, so a test can prove the shape of the boundary without
the boundary being crossed to do it.

⚠ **WHY THE REGISTRY IS ASSEMBLED BY STATIC IMPORTS AND NOT BY WALKING THE
DIRECTORY.** A discovery loop over `seams/` would be shorter and it would make
`G115`'s job harder in the one way that matters: a dynamic import cannot be
followed by a static census, so every such loop is a hole the gate must either
allow blindly or refuse. Fourteen explicit lines are auditable by eye, and a
fifteenth port added without a line here does not silently join the allow-list
— it fails `test_us_rbs_041_module.py`, which counts them.

⚠ **THIS SAID THIRTEEN UNTIL 2026-09-07 AND THE MECHANISM ABOVE IS EXACTLY WHAT
CAUGHT THE CHANGE.** `CR-075` wave `N` added `step_ladder` (payments) because a
collections step moves payments' own `notice_history` and
`account_collection_state` and `queue_notice` writes neither — `DEF-RBS-4347`.
The count test went red on the fourteenth port before this line was edited,
which is the whole reason the registry is written out by hand.

WHAT AN EMPTY `BOUND_PORTS` MEANS
---------------------------------
`bound_ports()` returns `()` in phase 1 and that is the product rather than a
gap. Phase 1's launch sentence promises *"nothing can be written: no writer is
bound"*, and this is where that promise is a fact you can assert instead of a
sentence in a plan. Wave L binds them with sending switched off; wave N turns
the first one on.
"""

from __future__ import annotations

from apps.runbooks.boundary import PortDeclaration, SeamDeclaration
from apps.runbooks.ports import (
    billing_ports,
    customers_ports,
    integrations_ports,
    metering_ports,
    notifications_ports,
    payments_ports,
)
from apps.runbooks.seams import (
    billing_seam,
    customers_seam,
    integrations_seam,
    ledger_seam,
    metering_seam,
    notifications_seam,
    payments_seam,
    rating_seam,
    tenancy_seam,
)

#: The NINE read seams, `operations → <module>`, keyed by the far side.
SEAMS: dict[str, SeamDeclaration] = {
    seam.module: seam
    for seam in (
        customers_seam.SEAM,
        metering_seam.SEAM,
        rating_seam.SEAM,
        billing_seam.SEAM,
        payments_seam.SEAM,
        ledger_seam.SEAM,
        notifications_seam.SEAM,
        tenancy_seam.SEAM,
        integrations_seam.SEAM,
    )
}

#: The FIFTEEN write ports, keyed by name (`send_partner_file` joined on
#: 2026-10-07, `CR-173-BRC10`). ⚠ `raise_work_item` is NOT here and
#: must not be added: raising a work item and writing an audit row are ENGINE
#: acts, which is the only thing that lets a Check populate the work list while
#: holding no writer at all (`BR-RBS-002`, `12-the-contract.md` §6).
PORTS: dict[str, PortDeclaration] = {
    port.name: port
    for port in (
        *notifications_ports.PORTS,
        *payments_ports.PORTS,
        *billing_ports.PORTS,
        *metering_ports.PORTS,
        *customers_ports.PORTS,
        #: CR-173-BRC10 — the FIFTEENTH, and the first owned by integrations.
        *integrations_ports.PORTS,
    )
}


def bound_ports() -> tuple[PortDeclaration, ...]:
    """Every port that actually has a writer. `()` in phase 1, by design."""
    return tuple(port for port in PORTS.values() if port.is_bound)


def ports_for(kind: str) -> tuple[PortDeclaration, ...]:
    """The ports a runbook of this kind may hold. **A Check holds none, ever.**

    `BR-RBS-002`, and it is the load-bearing half of the design: the capability
    is ABSENT for a Check, not merely unused, so a write from one is a
    construction error rather than a runtime refusal. Wave B's contract object
    calls this when it builds a runbook, which is where that becomes true of an
    actual runbook; here it is true of the vocabulary.

    An Action gets the fourteen **declarations** — not fourteen writers. In
    phase 1 every one of them raises `PortNotBound` when called.
    """
    if kind == "check":
        return ()
    return tuple(PORTS.values())
