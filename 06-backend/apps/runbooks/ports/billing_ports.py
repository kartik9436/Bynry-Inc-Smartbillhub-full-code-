# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-018 (a money-bearing action carries a second
#           approval) · CLAUDE.md hard rule 4 (issued invoices are append-only)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 · apps/runbooks/interfaces.py
# ───────────────────────────────────────────────────────
"""One port owned by `billing`. **Bound in wave L, and it DRAFTS.**

⚠ **THIS DOCSTRING SAID *"It is not bound"* UNTIL 2026-09-06.** Wave L binds
`apps.billing.runbook_ports.apply_fee`, which delegates to
`fee_bill.raise_charge_fee` — a **DRAFT** fee bill. `issue_charge_fee` is a
separate act, consumes the bill number, and is bound to NOTHING. So a runbook
can put a fee in front of a person and a person issues it, which is
`BR-RBS-018`'s second approval written into the shape of the code rather than
into a flag somebody has to remember to check.

`apply_fee` sits **behind the second approval** because it is money-bearing
(`BR-RBS-018`) — a late fee applied by rule to 812 accounts is the kind of thing
a utility must be able to see before it happens and stop while it is happening.

⚠ **THERE IS NO PORT THAT ISSUES A BILL, AND THERE WILL NOT BE.** A runbook says
what would stop a bill run and hands billing a scope at most; the bill run is
billing's own act. That is what keeps phase 2's rollback clean — 25 coverage
cells produce correct arithmetic and **no bill number is consumed** — and it is
hard rule 4 read forward, since an issued invoice is append-only and a module
that could re-run one would be writing corrections nobody asked for.
"""

# ⚠ A FOREIGN IMPORT IN ONE OF THE TWO LAWFUL DOORS (`G115` rule 1).
from apps.billing import runbook_ports as billing_writers

from apps.runbooks.boundary import PortDeclaration

APPLY_FEE = PortDeclaration(
    name="apply_fee",
    owning_module="billing",
    what_it_does="A fee by rule, behind the second approval",
    writer=billing_writers.apply_fee,
)

PORTS = (APPLY_FEE,)
