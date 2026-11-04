# ── Trace ──────────────────────────────────────────────
# Change:   CR-173-BRC10 — the ONE service function behind Runbooks' port
#           `send_partner_file` (`apps/runbooks/ports/integrations_ports.py`).
# Rules:    BR-RBS-022 (a runbook writes another module's world only through a
#           named port that maps to one service function in the owning module)
#           · BR-INT-054 as amended (integrations places the file; the runbook
#           decides the day) · PO 2026-10-07 S2 (*"You already ruled that
#           scheduled jobs run as runbooks - this is correct"*)
# Tests:    06-backend/tests/test_cr173_newworld_sftp.py
# Impacts:  apps/integrations/receipt_push.py
# ───────────────────────────────────────────────────────
"""What a runbook may ask integrations to DO — one function, and it places one file.

⚠ **IT RETURNS `done: False` RATHER THAN RAISING, AND THAT IS LOAD-BEARING.**
The engine calls a port inside a SAVEPOINT and rolls the savepoint back when
the port raises (`runbooks.engine.acts.act`). Everything `receipt_push.send`
writes on a failure — the run row Settings → Integrations shows, the failed
claim, the System Admins' alert — would be rolled back with it, and the night
would fail in silence. So a failure is an ANSWER: `{done: False, reason: …}`,
and the engine records the act as not done (resumable) with that reason.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.integrations import receipt_push


def send_receipt_file(
    *,
    day: str,
    trigger: str = "scheduled",
    started_by_name: str | None = None,
    actor: Any = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Build the utility's file for `day` (ISO date) and place it in the City's folder."""
    result = receipt_push.send(
        date.fromisoformat(str(day)),
        trigger=trigger if trigger in ("manual", "scheduled") else "scheduled",
        actor=actor,
        started_by_name=started_by_name,
    )
    return result.as_dict()
