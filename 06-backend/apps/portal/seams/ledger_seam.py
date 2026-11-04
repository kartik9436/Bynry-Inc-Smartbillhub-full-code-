# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 4 · `P4.15` (*"a landlord sees their own account
#           only"*).  Screen: CWP-024 Property statement.
# Change:   `CR-142-BRC07` `P4.15`, brief p016 + p070/p071 (report `R24c`
#           *Statement · by premises*), read as IMAGES per B14 rule 42.
# Rules:    **R24c LAW (ruled)** — *"This report crosses customers … Staff see
#           it as drawn. In the customer portal a landlord sees **their own
#           master account only**: the $69.60, never Unit 3's $100.00"* ·
#           BR-CWP-016 (PO 2026-09-04, option *"(a) no"* — a landlord sees the
#           accounts they hold and never a tenant's) · BR-CWP-012 (read through
#           a seam, no second copy) · BR-CWP-041 (nothing above the issued bill)
#           · BR-LED-010 (`r_n = r_{n−1} + charge_n − payment_n`) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (4 dp stored,
#           displayed at 2) · hard rule 5 (ONLY the ledger posting service
#           writes journal lines — this READS and writes nothing) ·
#           CR-068 §2d (a seam composes; it computes nothing)
# Tests:    06-backend/tests/test_cr142_p4_15_premises_statement.py
#           10-scripts/rep_p4_15_landlord_rls_proof.py (real PostgreSQL 16)
# Impacts:  apps/portal/premises_statement.py (its only caller)
# ───────────────────────────────────────────────────────
"""What the portal reads from `ledger`. **NOTHING HERE WRITES** (G81).

⚠ **THE PORTAL HAD NO LEDGER SEAM UNTIL THIS FILE, AND THAT IS WHY IT IS ONE
FUNCTION WIDE.** `apps/portal/seams/` holds one file per module it reads, and
`ledger` was simply not among them: every money figure the portal shows today
comes through `payments_seam`, which answers *what do you owe right now*. A
STATEMENT is a different question — *what happened between two dates* — and it
is the ledger's, because the ledger is the only place that holds both sides.

⚠ **IT COMPUTES NOTHING** (`CR-068` §2d). `apps.ledger.reporting.account_ledger`
already is the engine: it sums the opening position from every posted AR line
before the window and carries `r_n = r_{n−1} + charge_n − payment_n` across a
SQL page. Re-deriving any of it here would be a second reading of one
customer's money, which is how two screens come to disagree about one balance —
and this one would be the screen the letter does not say.

⚠ **THE TENANT AND THE ACCOUNT SET ARE THE CALLER'S TO INTERSECT, AND THIS
SEAM CANNOT DO IT FOR THEM** (`BR-CWP-010`, `G96`). `account_ledger` takes one
account id and asks no questions about who is holding it. That is correct for a
staff report and is exactly the hole `P4.15` exists to close, so the ONE caller
— `premises_statement` — resolves the account set FIRST and hands this seam
only ids it has already proved belong to the signed-in person. A future second
caller that skips that step re-opens the ruling, which is why this docstring
says so instead of leaving it to be inferred.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: Hard rule 2 — money is a `Decimal`, never a float and never cents.
ZERO = Decimal("0.0000")


def window_totals(account_id: Any, *, start: date, end: date) -> dict[str, Any]:
    """One account's CHARGES · CREDITS · CLOSING between two dates.

    The three figures `R24c` draws per row, and nothing else: the seam
    deliberately does not carry the ledger's line ROWS across, because the
    portal's property statement is a per-account summary and a seam that
    published the lines would be publishing every posting of an account the
    caller may only have been cleared to total.

    ⚠ **`credits` IS THE LEDGER'S `payments`, RENAMED AT THIS BOUNDARY AND
    NOWHERE ELSE.** `R24c`'s column is CREDITS and the ledger's key is
    `payments`; mapping it here keeps the drawing's word on the screen without
    a second vocabulary inside `ledger`. The SIGN is the ledger's too — it
    publishes payments as a positive magnitude, and the screen draws the minus.

    Returns `None` figures for nothing: an account with no movement in the
    window is `0.0000`, which is a fact, where `None` would be an absence.
    """
    from apps.ledger import reporting as ledger_reporting

    answer = ledger_reporting.account_ledger(account_id, start=start, end=end, per=1)
    totals = answer.get("totals") or {}
    return {
        "opening": _money(answer.get("opening_balance")),
        "charges": _money(totals.get("charges")),
        "credits": _money(totals.get("payments")),
        "closing": _money(totals.get("closing_balance")),
    }


def _money(value: Any) -> Decimal:
    """FOUR DECIMALS, because that is what money IS in this product.

    ⚠ **THE LEDGER HANDS BACK SIX AND THAT IS NOT A BUG THERE.** `journal_lines`
    columns are the lawful `NUMERIC(18,6)` containers CLAUDE.md hard rule 2
    leaves in place, so `account_ledger` answers `Decimal('659.780000')` — and
    **that reached the wire as `"659.780000"` before this function existed**,
    measured against a real PostgreSQL 16 clone on 2026-09-27. Nothing looked
    wrong: the screen rounds to 2 for display (hard rule 2's other half), every
    test passed, and the extra two zeros were invisible on the page.

    ⚠ **IT IS QUANTIZED HERE, AT THE SEAM, AND NOT IN THE SCREEN.** The rule
    governs what is WRITTEN and what crosses a boundary, not what a component
    happens to render — and a payload carrying six decimals is a payload the
    next reader of this API is entitled to believe. `ROUND_HALF_UP` because that
    is B4's rounding and this is a money path, even though no value here should
    ever need the tie broken: the two trailing digits the ledger adds are zeros.
    """
    return (Decimal(value or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# gates: G81 (no write here) · G91 (no apps.identity) · G96 (no ORM chain here —
#        the one read is `ledger`'s own published function, which scopes itself)
# status: VERIFIED-UNRATIFIED
