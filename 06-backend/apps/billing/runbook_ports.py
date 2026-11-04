# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-010 · US-RBS-014 (EP-RBS-04) — CR-075 wave L task L2: the
#           one port billing owns, bound to ONE service function, in the module
#           that owns the table.
# Rules:    BR-RBS-022 (a write is a named port into the owning module's own
#           service) · BR-RBS-018 (a money-bearing action carries a SECOND
#           approval) · OQ-RBS-1732 CLOSED (every money-bearing action carries
#           it, NO threshold) · BR-RBS-013 / CLAUDE.md hard rule 4 (an issued
#           invoice is append-only) · BR-TEN-043 (event time is an argument)
# Tests:    06-backend/tests/test_us_rbs_010_port_writers.py
# Impacts:  apps/runbooks/ports/billing_ports.py (binds this one)
# ───────────────────────────────────────────────────────
"""The ONE write a runbook may make in this module — and it DRAFTS, never issues.

⚠ **THERE IS NO PORT THAT ISSUES A BILL AND THERE WILL NOT BE.** A runbook says
what would stop a bill run and hands billing a scope at most; the bill run is
billing's own act. That is what keeps phase 2's rollback clean — the dry cycle
produces correct arithmetic and **no bill number is consumed** — and it is hard
rule 4 read forward, since an issued invoice is append-only and a module that
could re-run one would be writing corrections nobody asked for.

⚠ **SO `apply_fee` DRAFTS.** `raise_charge_fee` creates a DRAFT fee bill;
`issue_charge_fee` is the separate act that consumes a number, and it is **not
bound to any port**. A runbook may put a fee in front of a person; a person
issues it. That is `BR-RBS-018`'s second approval expressed in the shape of the
code rather than in a flag somebody has to remember to check, and
`OQ-RBS-1732` (CLOSED 2026-09-06) is why there is no threshold argument below:
*every* money-bearing action carries the second approval, with no amount above
which it is skipped.

⚠ **THE ENGINE WRITES THE RUNBOOK'S AUDIT ROW, NOT THIS FILE** (`BR-RBS-022`).
`raise_charge_fee` writes billing's own rule-7 row as it always did, and the
runbook's `AutomationActor` is handed to it so that row is NAMED rather than
reading as an anonymous system job.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from apps.billing import fee_bill


def apply_fee(
    *,
    actor: Any,
    account_id: Any,
    charge_code: str,
    on_date: dt.date,
    due_days: int,
    description: str | None = None,
) -> dict[str, Any]:
    """PORT `apply_fee` — draft one fee bill for one charge code on one account.

    Delegates to `apps.billing.fee_bill.raise_charge_fee`. Three of its rules
    are the reason this port is thin rather than clever:

    * **`on_date` is the business event's date and is an ARGUMENT, never a clock
      read** (`BR-TEN-043`, gate `G6`). For a late fee it is the day the debt
      aged, so a ladder re-run for last Tuesday charges last Tuesday's fee.
    * **`due_days` is REQUIRED and billing does not choose it.** A cycle-less
      bill has no cycle to take its terms from (PO 2026-08-23), and `issue`
      refuses a bill whose due date cannot be derived rather than guessing one.
    * **The amount comes from the CHARGE CODE**, priced by rating. This port
      passes no amount at all, which is the only way a runbook cannot invent
      one — B4 is finance-signed and a runbook is not allowed near it.

    Returns the DRAFT invoice's id. Nothing has been issued: no bill number is
    consumed, and the fee reaches a customer only when a person issues it.
    """
    invoice = fee_bill.raise_charge_fee(
        actor,
        account_id=account_id,
        charge_code=charge_code,
        on_date=on_date,
        due_days=due_days,
        description=description,
    )
    return {
        "entity_type": "invoice",
        "entity_id": str(getattr(invoice, "pk", "") or ""),
        "created": True,
        "charge_code": charge_code,
        "on_date": str(on_date),
        # Stated as a VALUE rather than only in prose (hard-won law 1): this is
        # a draft, and a test can assert that a port write consumed no number.
        "issued": False,
        "status": str(getattr(invoice, "status", "")),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-010 · US-RBS-014 (EP-RBS-04; CR-075 wave L task L2)
# generated: 2026-09-06 by the CR-075 wave L build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — a port is called by the engine, never over HTTP) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path here: this file prices nothing and rounds nothing — it passes a charge code to billing's own draft door)
# gates: pytest tests/test_us_rbs_010_port_writers.py · G115 · G6 (no clock read)
# exceptions: issue_charge_fee is deliberately NOT bound — a runbook drafts a fee, a person issues it (BR-RBS-018)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
