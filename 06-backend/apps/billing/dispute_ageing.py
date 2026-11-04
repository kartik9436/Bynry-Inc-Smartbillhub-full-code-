# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — late-fee assessment) · EP-MET-04 (the dispute
#           marker this reads)
#           Screens: — (S31.2's Balances tab consumes `assess_late_fee`)
#           NOTE: no US-ID in this header ON PURPOSE — G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs", and this file ships one
#           resolver, not a story. Same precedent as apps/billing/late_fee.py.
# Change:   CR-038 — BR-MET-133 clause 4 (the disputed amount does not age)
# Rules:    BR-MET-133 (CONFIRMED, PO 2026-08-26, closes OQ-245) · BR-MET-024 +
#           the OQ-043 closure (the marker, and the hold on the NEXT run) ·
#           BR-BIL-001 (late fee = max($5, 1.5% × overdue portion)) ·
#           CLAUDE.md hard rule 4 (issued money stays) · B1 (billing never
#           reads metering's tables — only its published selectors)
# Tests:    06-backend/tests/test_br_met_133_dispute_ageing.py
# ───────────────────────────────────────────────────────
"""BR-MET-133 clause 4 — who is disputing, and how much of the bill.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive
paths), AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never
invents it.

════════════════════════════════════════════════════════════════════════════
THE RULE, VERBATIM (BR-MET-133, CONFIRMED 2026-08-26, closing OQ-245)
════════════════════════════════════════════════════════════════════════════
PO verbatim: *"Bill stands, resolution through the billed-correction door, and
the disputed amount doesn't age into late fees while open"*. The four clauses,
and only ONE of them is new work:

  1. The issued invoice is **NOT voided or held** — it is issued money and it
     stays (hard rule 4). EXISTING: `issue_invoice` writes nothing on a
     dispute, `supersede_read` still refuses a billed read, and nothing in this
     module touches an invoice.
  2. The marker **holds the account out of the NEXT run**. EXISTING:
     `apps/billing/runs._dispute_hold_for`, on the same seam this file reads.
  3. Resolution goes through the **billed-correction door** — right → supersede
     plus the money correction it opens; wrong → clear the marker, the bill was
     always correct. EXISTING: `correct_billed_read` is that door
     (BR-MET-053/US-MET-016) and clearing is System-Admin-only.
  4. ⚠ **NEW.** *"while the dispute is open, the disputed amount is excluded
     from ageing and from late-fee assessment — a customer is not penalised for
     the days we investigate. The undisputed remainder of the bill ages
     normally."*

This module answers the two questions clause 4 asks of a bill, and it answers
one of them honestly and the other by refusing.

════════════════════════════════════════════════════════════════════════════
WHAT IS READABLE, AND WHAT IS NOT (OQ-420)
════════════════════════════════════════════════════════════════════════════
**Readable: IS a dispute open.** `apps.metering.selectors.dispute_holds_for_unit`
returns every uncleared marker on a unit's meters — set and not cleared, the
exact predicate `needs_attention_counts` and `prepare_run` use.

**NOT readable: HOW MUCH is disputed.** Measured 2026-08-26 across the whole
repository: no model, no column and no service writes a disputed AMOUNT. That
is the same measurement `apps/customers/move_out_settlement.py` recorded on
2026-08-24 for BR-CUS-096, and it has not changed.

⚠ **AND `meter_reads.disputed_at` IS NOT IT.** A read dispute is **a quantity
in dispute, not a sum of money**. A customer saying *"the meter says 684 kWh
and the property was empty since July"* has disputed a READING; how many
dollars of a multi-service bill that reading is responsible for is written
nowhere. Do not wire the marker's `consumption` in here as though it were an
amount — a quantity handed to a money rule is CLAUDE.md rule 3 broken in the
most expensive direction.

So `open_dispute_for_account` reports `open=True, amount=None`, and
`late_fee.ageable_portion` raises `NotImplementedError("OQ-420")` on it. It
does not fall back to zero, and it does not fall back to the whole bill: those
two readings are **$137.20 apart** on the rule's own worked bill ($184.20 with
$47.00 disputed), and picking one would be this file writing money law.

════════════════════════════════════════════════════════════════════════════
AND AN UNKNOWN IS NOT A "NO"
════════════════════════════════════════════════════════════════════════════
When metering publishes no dispute selector at all, this reports
`open=True, amount=None` — the SAME shape as a real open dispute, so the
assessment refuses. That is deliberate and it is `runs._dispute_hold_for`'s own
posture restated: *"we could not tell"* and *"there is no dispute"* are
different facts and only one of them is safe to charge a late fee on. A silent
"no dispute" here bills a penalty to a customer who may be under investigation,
which is precisely what clause 4 exists to stop.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from apps.billing.late_fee import NO_DISPUTE, DisputeExclusion

#: The machine name a surface renders when the disputed AMOUNT cannot be read.
#: A CODE, not prose (G28: no internal provenance reaches a utility user), and
#: it deliberately mirrors `move_out_settlement.GAP_DISPUTES_UNREADABLE` —
#: it is the same absence, met by a second rule.
GAP_DISPUTED_AMOUNT_UNREADABLE = "disputed_amount_not_recorded"

#: The seam metering publishes for BR-MET-024's hold. Named once so a grep for
#: the string finds both readers (this file and `runs._dispute_hold_for`).
METERING_DISPUTE_SEAM = "dispute_holds_for_unit"


def _dispute_holds() -> Any:
    """Metering's published selector, resolved at call time — never imported.

    B1/BR-TEN-013: no import statement binds billing to another module's
    internals (gate G6), and the moment a lane publishes the function every
    caller starts using it with no re-wiring. `None` when it is absent, which
    the caller must NOT read as "no disputes" — see the module docstring.
    """
    try:
        selectors = import_module("apps.metering.selectors")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    found = getattr(selectors, METERING_DISPUTE_SEAM, None)
    return found if callable(found) else None


def open_dispute_for_account(
    account: Any, *, unit_ids: tuple[str, ...] | None = None
) -> DisputeExclusion:
    """BR-MET-133 clause 4's first question: is a dispute open on this account?

    Returns `NO_DISPUTE` when no marker is open — the whole overdue portion
    ages, which is the ordinary bill — and `DisputeExclusion.unreadable()`
    otherwise, because the AMOUNT is not recorded anywhere (OQ-420).

    `unit_ids` covers BR-CUS-068's multi-unit account for the same reason
    `runs._dispute_hold_for` takes it: a disputed read on the shared-irrigation
    meter is priced onto the same bill as one on the hallway meter, so both
    must be looked at. `None` keeps the anchor-only read.

    **NO WRITE CROSSES THE BOUNDARY and no invoice is touched** — clause 1 says
    the issued bill stays exactly as it is, and this function only reads.
    """
    holds = _dispute_holds()
    if holds is None:
        # Metering publishes nothing. NOT "no dispute" — see the module
        # docstring; the assessment refuses rather than charging a fee it
        # cannot justify.
        return DisputeExclusion.unreadable()
    for unit_id in unit_ids or (getattr(account, "unit_id", None),):
        if unit_id is None:
            continue
        if holds(unit_id):
            return DisputeExclusion.unreadable()
    return NO_DISPUTE


def dispute_ageing_gap(exclusion: DisputeExclusion) -> dict[str, Any] | None:
    """The stated absence a surface renders, or `None` when there is none.

    Shaped like every other reported gap in this repo (the
    `move_out_settlement.GAP_*` rows): a CODE plus a sentence saying what the
    product could not do and why, so a clerk reads a fact rather than a silence.
    """
    if not exclusion.open or exclusion.amount is not None:
        return None
    return {
        "code": GAP_DISPUTED_AMOUNT_UNREADABLE,
        "br_ref": "BR-MET-133",
        "open_question": "OQ-420",
        "detail": (
            "a dispute is open on this account and nothing in this product records HOW "
            "MUCH of the bill is disputed. BR-MET-133 excludes the disputed amount from "
            "ageing and lets the undisputed remainder age normally, which cannot be "
            "computed without that figure - so no late fee is assessed and none is "
            "waived. The dispute marker on a meter reading is a QUANTITY in dispute, not "
            "a sum of money, and is deliberately not used as one."
        ),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@6107784 — sha1[:7] of four sources concatenated in this
#         order, computed 2026-08-26: 04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/05-modules/04-metering/02-business-rules.md (BR-MET-133) ·
#         04-docs/05-modules/07-billing/02-business-rules.md (BR-BIL-001 as
#         amended 2026-08-11). US-BIL-002 is the story this serves — the same
#         one `late_fee.py` names, and for the same reason: this file is one
#         resolver inside it, not the story. The packet also read OQ-245's
#         closure row and BR-MET-024 / the OQ-043 closure.
# generated: 2026-08-26 by the CR-038 BR-MET-132/133 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E✔ F✔ G✔ H=deferred(🔒 money math)
#            ⚠ ONE LINE ON PURPOSE — G03 reads `checklist:(.*)` and `.` does not
#            match a newline, so a wrapped trailer loses every letter after the
#            first line. This one wrapped and the gate reported C,D,E,F,G,H
#            missing on a file that had all eight. The prose lives here instead:
#            B — the S29 dispute banner states clause 4 in the clerk's words
#            (07-frontend/src/features/metering/ReadDetailPage.tsx). D — this is
#            a resolver; `assess_late_fee` has no production caller and no route
#            serves a late fee yet. H — HUMAN-REVIEW-PENDING, row filed in
#            12-governance/09-human-review-ledger.md; nothing here is ratified.
# gates: ruff✔ black✔ · pytest tests/test_br_met_133_dispute_ageing.py → 18
#        passed (16 cases; 3 of them parametrised) · with the metering half,
#        tests/test_us_met_013_tc_dispute.py → 29 passed · GT-8 UNMOVED and
#        VERIFIED not assumed: `pytest tests -m golden` 23 passed,
#        10-scripts/03-golden-verify.py 12 PASS / 0 FAIL exit 0 ·
#        makemigrations --check --dry-run → "No changes detected" (this file
#        adds no column) · G07 human-owned: row filed, this file not among its
#        findings · G20 seam-implementers PASS · G31 declared-classes PASS
# exceptions: (1) THE DISPUTED AMOUNT IS UNREADABLE AND IS REFUSED, NOT GUESSED
#            — OQ-420, `NotImplementedError` in `late_fee.ageable_portion`.
#            (2) An UNPUBLISHED metering seam reports the same shape as a real
#            open dispute, so the assessment refuses; "we could not tell" is not
#            "there is no dispute" (`runs._dispute_hold_for`'s own posture).
#            (3) `meter_reads.disputed_at` carries a CONSUMPTION and it is
#            deliberately NOT read as an amount (CLAUDE.md rule 3).
#            (4) Clauses 1-3 of BR-MET-133 are EXISTING behaviour and are
#            CONFIRMED by test rather than rebuilt.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
