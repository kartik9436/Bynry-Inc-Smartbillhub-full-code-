# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-022 · US-RBS-026 (EP-RBS-05) — CR-075 wave P.
# Rules:    BR-RBS-018 (a money-bearing action carries a SECOND approval,
#           separate from the batch approval — CONFIRMED 2026-09-06, PO
#           verbatim: *"1732 … (a) every money action, no threshold (built)"*) ·
#           BR-RBS-005 / TC-RBS-8 (the approval must MATCH the plan as it
#           stands) · BR-RBS-004 (an Action always produces a plan first) ·
#           BR-RBS-041 (permission up front removes the WAIT, never the plan)
# Tests:    06-backend/tests/test_us_rbs_022_cash_application.py ·
#           06-backend/tests/test_us_rbs_026_bank_reconciliation.py ·
#           06-backend/tests/test_rbs_money_runbooks_pg.py
# Impacts:  definitions/cash_application.py · definitions/bank_reconciliation.py
# ───────────────────────────────────────────────────────
"""The second approval, in ONE place, because two copies of a money rule drift.

⚠ **THE LEADING UNDERSCORE IS LOAD-BEARING.** `test_us_rbs_015_conformance.py`
globs `definitions/*.py` and fails naming any module `DEFINITION_MODULES` does
not carry — `if not p.stem.startswith("_")` is the exemption, and it is why a
shared helper may live beside the runbooks without pretending to be one. This
file declares no `RUNBOOK` and registers nothing.

WHAT THE RULE IS, IN THE PRODUCT OWNER'S OWN WORDS
---------------------------------------------------
`OQ-RBS-1732` closed on 2026-09-06 with *"every money action, no threshold"*,
which **overruled** this project's own recommendation of per-action thresholds —
in the safe direction. The register says the rest in as many words: **a
threshold parameter is not to be added later without a new ruling.** So there is
no amount in this file and there must not be one.

⚠ **TWO COLUMNS ARE READ AND BOTH ARE LOAD-BEARING.** `approved_by` says a
second person pressed the button; `approved_count` says WHAT they approved.
`BR-RBS-005` exists because approving *"129 to apply"* and then acting on 140 is
the failure that can only happen when the plan moves between the two moments —
so an approval whose count does not match the plan as it stands is treated as no
approval at all, and the reason names both numbers.

⚠ **WHY THIS DOES NOT LOOK AT `gate_mode`, WHICH IS THE OBVIOUS THING TO DO.**
`BR-RBS-041` (PO ruling 2026-09-06) lets an admin grant permission UP FRONT, per
runbook, and a run then goes plan → act in one pass. That switch removes the
WAIT; it does not remove the approval, and **the rule it changes is where the
run pauses, not whether a person is on the hook.** `runbooks.gate_mode` holds
one value today (`approve_each_run`) and the second value has no writer, no
screen and no migration — minting one here would be this lane deciding a column's
vocabulary on the way past. When wave `L3` builds the switch, this function is
where it lands, and the test that covers it is already written round this shape.
"""

from __future__ import annotations

from typing import Any

from apps.runbooks import models

#: Cached on the execution context under this key. A run's approval is a fact
#: about the RUN, so asking the database once per payment would be 138 identical
#: queries AND would let the answer change halfway through a pass.
CACHE_KEY = "approval"


def second_approval(ctx, *, planned: int) -> dict[str, Any]:
    """Has a second person approved THIS run, for the plan as it stands?

    Returns `{"approved": bool, "reason": str, "approved_count": int | None}`.
    `reason` is a sentence a clerk reads and never a rule id (B14 rule 32); the
    rule travels separately, in `ReportRow.meta`, where no block draws it.
    """
    cached = ctx.set_results.get(CACHE_KEY)
    if cached is not None:
        return dict(cached)

    answer: dict[str, Any] = {"approved": False, "reason": "", "approved_count": None}
    run = (
        None
        if ctx.run_id is None
        else models.RunbookRun.objects.filter(pk=ctx.run_id)
        .only("approved_by", "approved_count")
        .first()
    )
    if run is None or run.approved_by_id is None:
        answer["reason"] = "Waiting for a second person to approve this run."
    else:
        answer["approved_count"] = run.approved_count
        if run.approved_count is None or int(run.approved_count) != int(planned):
            answer["reason"] = (
                f"The approval covers {run.approved_count} and this plan has {planned}. "
                "Approve the plan as it stands."
            )
        else:
            answer["approved"] = True
    ctx.set_results[CACHE_KEY] = dict(answer)
    return answer


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-022 · US-RBS-026 (EP-RBS-05; CR-075 wave P)
# generated: 2026-09-06 by the CR-075 wave P money-runbooks lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path — it composes no key and writes nothing)
# gates: pytest tests/test_us_rbs_022_cash_application.py tests/test_us_rbs_026_bank_reconciliation.py · G115
# exceptions: `gate_mode`'s second value is not read here — wave L3 owns it, and the reason is in the docstring
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
