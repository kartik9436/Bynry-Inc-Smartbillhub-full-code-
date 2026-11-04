# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2855 (BR-BIL-054's unusually-large-bill list has never existed —
#           S31 step 4 names its three required actions and then says the list
#           cannot be drawn)
# Story:    US-BIL-004 (phase 3 — post-calculation exceptions with their
#           required actions)   Screens: S31 step 4
# Rules:    BR-BIL-029 (the guardrail: a draft above the tenant's % of the
#           account's trailing average is flagged BEFORE issue; arithmetic and
#           threshold unchanged by anything here) · BR-BIL-054 (it is surfaced
#           AFTER calculation with its actions, never as a pre-block) ·
#           BR-BIL-021 (the % is tenant config, seeded, never hardcoded) ·
#           CLAUDE.md prime directive (an unanswered question is stubbed with
#           its OQ id, never answered by choosing a value)
# Blocked:  OQ-1202
# ───────────────────────────────────────────────────────
"""BR-BIL-054's list — the shape of it, and the one thing nobody has ruled.

**WHAT THE PO ASKED FOR, VERBATIM (2026-08-11):** *"this is an exception, mark
it and show exception high consumption cases, after billing process and let user
take the action on it; you have to show this list and required actions"*.

**WHY THIS FILE HOLDS A REFUSAL AND NOT A LIST.** Everything the comparison
needs exists except its own definition, and the rule contradicts its own worked
example about which definition it is:

  * BR-BIL-029 says *"any draft **bill** above tenant-set % … of the account's
    trailing average"*, and `07-billing/03-field-map.md` spells the same rule
    `draft_total > (guardrail_pct ÷ 100) × trailing_average` — **money**.
  * `EP-BIL-01` US-BIL-002 §4, the fixture for that same rule, is
    **26.24 kgal of water against a trailing average of 8.40 kgal = 312%** —
    **consumption**.

**THE TWO READINGS FLAG DIFFERENT CUSTOMERS, WHICH IS WHY THIS IS NOT A
TIDY-UP.** A leak that doubles a customer's water — 8.40 → 16.80 kgal, exactly
200% of their usual usage — moves their bill from $52.30 to $71.40, which is
137%, because base charges, the fixed sewer share and taxes do not double with
the water. On a 200% guardrail the consumption reading flags that leak and the
money reading does not. It runs the other way too: a $400 reconnection fee on an
ordinary month is 312% of a customer's usual BILL and nothing unusual has been
used at all.

**AND IF IT IS MONEY, A SECOND THING IS UNRULED: over how many bills.** No
signed document says. The consumption reading has no such gap — OQ-002 closed
the metering flag's window (trailing 12 months, trailing 3 when history is
short) and `apps/metering` already computes and stores that verdict on the
priced read, which `apps/billing/read_analysis` already renders on step 2.

So `flagged_drafts` raises. **Picking either reading here would decide which
customers a clerk is warned about before money leaves**, which is exactly the
kind of guess CLAUDE.md's prime directive exists to stop, and this is a money
guardrail on a 🔒 path.

**WHAT IS DELIBERATELY NOT IN THIS FILE.** No threshold, no window, no default
and no fallback. `guardrail_pct` is read from the tenant's own
`overcharge_guardrail_pct` (BR-BIL-021, seeded 200) by the caller and passed in;
this module never reaches for a number of its own. The precedent is
`budget.compute_level`, which refuses rather than assuming twelve months for the
same class of reason: *"a caller that could not read the setting must refuse,
not assume twelve"*.

**THE ACTIONS ARE NOT BLOCKED AND ARE NAMED HERE**, because the PO asked for
*"this list and required actions"* and the actions are ruled even though the
list is not: release it knowingly · exclude it from this run · send it back for
a reading check (BR-BIL-054). The screen already draws all three; it is the rows
they act on that do not exist.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

#: The open question this module is stubbed against. Named as a constant so a
#: test can assert the stub cites the RIGHT question — `OQ-\d{3}` search
#: patterns have silently returned a different, real question before (DEF-2804),
#: and here the wrong id would route a money guardrail to the wrong answer.
BLOCKED_BY = "OQ-1202"

#: BR-BIL-054's three required actions, in the order the rule states them. They
#: are PUBLISHED from here rather than hardcoded in the screen for the reason
#: `decisions.CHOICES_BY_CASE` gives: a client-side option list drifts off the
#: rule the day one changes, and the failure mode is a control that submits a
#: choice the server refuses.
REQUIRED_ACTIONS: tuple[str, ...] = ("release", "exclude", "read_check")


def flagged_drafts(
    bill_run: Any,
    *,
    guardrail_pct: Decimal,
    basis: str | None = None,
) -> Any:
    """The drafts BR-BIL-029 flags on this run — **blocked on OQ-1202**.

    `guardrail_pct` is the tenant's own setting and is an ARGUMENT with no
    default, so a caller that could not read it must refuse rather than assume
    200 (BR-BIL-021). `basis` is the half OQ-1202 asks about and has no
    permitted value yet; it is on the signature so the shape of the answer is
    already visible in the code that is waiting for it.

    Raises `NotImplementedError` naming the question, per the prime directive.
    """
    raise NotImplementedError(
        f"{BLOCKED_BY}: BR-BIL-029 says a draft BILL above the tenant's percentage of the "
        "account's trailing average is flagged, and its own worked fixture compares 26.24 kgal "
        "of water against an 8.40 kgal average. Money and consumption flag different customers "
        "— a leak that doubles usage moves a bill by 137%, and a $400 reconnection fee moves it "
        "by 312% with nothing unusual used — so the basis is a ruling, not a choice. If it is "
        "money the averaging window is unruled as well; if it is consumption, OQ-002 already "
        "ruled the window and metering already stores the verdict. "
        f"guardrail_pct={guardrail_pct}, basis={basis!r}, bill_run={getattr(bill_run, 'pk', bill_run)}"
    )
