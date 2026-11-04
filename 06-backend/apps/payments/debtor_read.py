# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.3 — "A debtor read: bills, ladder state and
#           history for one account." Blueprint `05-prototype/06 Payments Page
#           Blueprint.pdf` p21 and screen **7·2 Debtor**, whose own task line
#           is *"One read that gathers bills, ladder state and history for an
#           account"* and whose TODAY line is *"No such screen. The debtor list
#           is a report you cannot drill into."*
#           Screens: 7·2 Debtor (S-NEW · PAY-J) — the SCREEN is `P4.8`, HELD
# Rules:    BR-PAY-032 (days late = today − the OLDEST UNPAID invoice's due
#           date) · BR-CUS-015 (`accounts.balance` is a CACHE and never the
#           figure a ladder runs on) · BR-PAY-017 (the rungs) · B14 rule 31
#           (no database id is the visible value of a field) · NFR-3 (server
#           pagination) · NFR-5 (no hard caps) · BR-TEN-043 (the business date
#           is an argument) · CLAUDE.md hard rule 1 · hard rule 2
# Tests:    06-backend/tests/test_cr138_p4_3_debtor_read.py
# Impacts:  apps/payments/debtor_api.py (the route) · config/urls.py ·
#           apps/payments/open_bills.open_bill_position · collections_read.
#           account_position · notices.notice_history_page / _count ·
#           billing_seam.outstanding_positions
# ───────────────────────────────────────────────────────
"""**ONE CALL BEHIND THE SCREEN THE DEBTOR LIST HAS NEVER HAD.**

The blueprint's question for 7·2, verbatim: *"Why does this account owe
$1,284.60, and what have we already tried?"* Today there is no answer anywhere
— the debtor list is a report a clerk cannot drill into, so the person with the
customer on the phone opens the account screen, the bills tab, the collections
tab and the notices list, and assembles it themselves.

⚠ **THE SCREEN IS `P4.8` AND IS HELD TO WAVE 2. THIS READ IS BUILT AHEAD OF
IT, DELIBERATELY, AND THAT IS HARD-WON LAW 2 IN REVERSE.** Law 2 says *built is
not wired*: a component nothing renders is dead UI. A READ nothing calls is the
same defect facing the other way — it renders nothing, every test passes, and
the feature does not exist. **So this is stated rather than left to be
noticed: its consumer is `P4.8`, and `P4.8`'s row on the `CR-138-BRC07` board
names this read.** If `P4.8` is ever cut, this endpoint goes with it.

═══════════════════════════════════════════════════════════════════════════════
THE FOUR THINGS IT GATHERS, AND WHERE EACH COMES FROM
═══════════════════════════════════════════════════════════════════════════════
Each is read from the surface that OWNS it and **nothing here re-derives a
figure** — the seam pattern, and `DEF-127`'s lesson:

  ① **THE OLDEST**, `billing_seam.outstanding_positions`. The blueprint calls
     it out by name: *"Oldest — the number that decides the ladder rung, not
     the total."* `BR-PAY-032` makes days-late the distance from the OLDEST
     UNPAID bill's due date, so a customer with a new large bill and one small
     ancient one is chased on the ancient one. ⚠ It is **NOT**
     `accounts.balance`: that column is customers' CACHE (`BR-CUS-015`) and a
     ladder driven off a cache chases people for money they have paid.
  ② **THE BILLS**, `open_bills.open_bill_position`. What each bill still OWES,
     not what it was issued for — `BL-2608-018410` was issued at **247.87** and
     a 200.00 payment left **47.87** open, and a screen built on the bill list
     would show a clerk the wrong number to aim at.
  ③ **THE LADDER**, `collections_read.account_position`. The pause, the plan,
     the tier already sent and what stops the chase. Whole and unmodified, so
     this screen and S21's header cannot disagree about where a customer stands.
  ④ **THE HISTORY**, `notices.notice_history_page` — **PAGED IN SQL.**

═══════════════════════════════════════════════════════════════════════════════
`NFR-3` — THE HISTORY IS THE UNBOUNDED ONE, AND IT IS THE ONLY ONE PAGED
═══════════════════════════════════════════════════════════════════════════════
Three of the four are bounded by the ACCOUNT and one is not:

  * the oldest is ONE row; the ladder state is ONE row;
  * the open bills are bounded by how many bills an account can have open at
    once, which is a cycle count and not a tenant size;
  * **the notice trail grows for ever.** Every send AND every skip appends
    (J4 step 2), the ladder runs nightly, and `notice_history` on a
    long-standing debtor at a 40,000-account utility is thousands of rows. It
    is paged with `LIMIT`/`OFFSET` **in the database** through
    `notices.notice_history_page`, which exists for exactly this and whose own
    docstring records what it replaced: a read that asked for 2,000 rows, built
    2,000 dicts and let DRF slice fifty — *"so the 2,001st notice was
    unreachable on every page of the list"*.

`history_limit` is a PAGE SIZE and not a cap (`NFR-5`): `history_offset`
reaches every row behind it and `history_count` is a real `COUNT(*)`, so there
is no number here any row can be beyond.

⚠ **ONE REDUNDANT BOUNDED READ, STATED RATHER THAN HIDDEN (law 1).**
`collections_read.account_position` builds its own 100-row `notices` list, and
this read POPS it and serves the paged page instead — **one representation of
those rows, never two** (`DEF-014`'s shape). The cost is one extra bounded
query per call. It is not removed by copying `account_position`'s twenty lines
of composition here, which would be a second answer to *"where does this
customer stand"*; it is removed by giving that function a history limit — and
`collections_read.py` is `P4.2`'s file in this same wave, so **this lane does
not edit it** (law 11: two lanes writing one file). Recorded for whoever lands
`P4.2`: one parameter closes it.

This module WRITES NOTHING: no clock, no money arithmetic, no audit row.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.payments import (
    billing_seam,
    collections_read,
    ladder,
    notices,
    open_bills,
    selectors,
)

#: The history page a screen gets when it asks for none. A DEFAULT, not a cap —
#: `debtor()` takes `history_limit` and `history_offset` and reaches every row.
DEFAULT_HISTORY_PAGE = 25


def debtor(
    *,
    account_id: Any,
    as_of: date,
    history_offset: int = 0,
    history_limit: int = DEFAULT_HISTORY_PAGE,
) -> dict[str, Any]:
    """Everything 7·2 draws about ONE debtor, in one call.

    `as_of` is the caller's business day (`BR-TEN-043`) — this layer reads no
    clock, so a clerk looking at Monday's position on Tuesday gets Monday's.

    A cross-tenant or unknown account id refuses by the same sentence
    `POST /accounts/{id}/payments` refuses by: `open_bills.open_bill_position`
    resolves the account and a miss is a miss (hard rule 1, HR-1). **The
    account is resolved FIRST**, before anything else is read, so a bad id
    cannot produce a half-built body.
    """
    # ② THE BILLS — and the account resolution every other read here relies on.
    bills = open_bills.open_bill_position(account_id=account_id)

    # ① THE OLDEST. `outstanding_positions` answers in bulk for the whole S34
    # list; asked for one account it is the same two queries, and asking it
    # rather than recomputing is what stops this screen and the debtor list
    # disagreeing about a number they both print.
    positions, position_problems = billing_seam.outstanding_positions(account_ids=(account_id,))
    position = positions[0] if positions else None

    # ③ THE LADDER, whole. `notices` is popped: the paged history below is the
    # ONE representation of those rows (see the module docstring).
    collections = collections_read.account_position(account_id=account_id, as_of=as_of)
    collections.pop("notices", None)

    # ④ THE HISTORY — paged in SQL, counted in SQL.
    limit = max(int(history_limit), 0)
    offset = max(int(history_offset), 0)
    history = notices.notice_history_page(account_id=account_id, offset=offset, limit=limit)
    history_count = notices.notice_history_count(account_id=account_id)

    problems = [dict(problem) for problem in position_problems]
    for problem in collections.get("problems", ()):
        entry = dict(problem)
        if entry not in problems:
            problems.append(entry)
    for problem in bills.get("problems", ()):
        entry = dict(problem)
        if entry not in problems:
            problems.append(entry)

    return {
        # B14 rule 31 — the id is the React key and the address, never a cell.
        # `account_no` is what a clerk reads out on the telephone, and
        # `open_bill_position` already resolves it.
        "account_id": str(account_id),
        "account_no": bills.get("account_no"),
        "as_of": as_of.isoformat(),
        # ① — the two figures the blueprint puts side by side, and the reason
        # they are BOTH here: a clerk asked why a notice says 222.30 when the
        # bill says 247.30 needs the gross and the credit, not a subtraction
        # they have to guess at (CR-059 CS-38).
        "position": _position_row(position),
        # ② `bills` carries its own currency, count and open total — the
        # screen's *"owes 341.10 across 2 bills"* header, summed over exactly
        # the rows below it.
        "bills": bills.get("bills", []),
        "bill_count": bills.get("bill_count"),
        "total_open": bills.get("total_open"),
        "currency": bills.get("currency"),
        # ③
        "collections": collections,
        # ④ — and `count` is a TOTAL, never the length of what was built.
        "history": history,
        "history_count": history_count,
        "history_offset": offset,
        "history_limit": limit,
        # One vocabulary with the board and the hand-send door (BR-PAY-017).
        "rungs": list(ladder.LADDER_RUNGS),
        "problems": problems,
    }


def _position_row(position: Any) -> dict[str, Any] | None:
    """`OutstandingPosition` on the wire, or **None meaning *owes nothing***.

    ⚠ `None` IS A MEASURED FACT AND NOT AN ABSENCE. `outstanding_positions`
    returns a row only for an account with something open, so a missing one
    means this read looked and there is nothing owed — which is a different
    sentence from *"we could not work it out"*, and the screen must not print
    the same thing for both. Anything that could not be answered is on
    `problems` with a code.

    Every money member is a decimal STRING at `NUMERIC(18,6)` (hard rule 2 —
    display rounds to 2, this does not round at all).
    """
    if position is None:
        return None
    gross = position.gross_balance if position.gross_balance is not None else position.balance
    return {
        "balance": f"{position.balance:.6f}",
        # What the bills alone say, before any credit came off.
        "gross_balance": f"{gross:.6f}",
        "credit_applied": f"{position.credit_applied:.6f}",
        # BR-PAY-032's anchor — *"the number that decides the ladder rung, not
        # the total"*, in the blueprint's own words.
        "oldest_due_on": (position.oldest_due_on.isoformat() if position.oldest_due_on else None),
        "invoice_count": position.invoice_count,
        # Unpaid bills carrying NO due date. EXCLUDED from the anchor and
        # reported, never placed by a convention no rule states.
        "undated": position.undated,
    }


# Kept so a reader grepping this module for the tenant guard finds one: every
# read above enters through a published function that scopes itself, and
# `selectors` is imported for that statement rather than used directly.
_TENANT_SCOPE_IS_THE_CALLEES = selectors


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.3 · 05-prototype/06 Payments Page Blueprint.pdf
#         p21 + screens 7·1/7·2 (pp.83–84) · apps/payments/open_bills.py ·
#         collections_read.py · notices.py · billing_seam.py · BR-PAY-032 ·
#         BR-CUS-015 · B14 rule 31 · NFR-3 · NFR-5
# generated: 2026-09-23 by the CR-138 lane P4-READS
# checklist: A✔ B=deferred(`P4.8` owns screen 7·2 and is HELD to wave 2 — SAID
#            OUT LOUD here and on the board rather than left to be noticed,
#            because a read nothing calls is hard-won law 2 facing backwards)
#            C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see the test file's own header.
# exceptions:
#   (1) ⚠ **ITS CONSUMER IS `P4.8` AND `P4.8` IS HELD.** Built ahead on purpose
#       so the screen lane has one call instead of four; stated in the module
#       docstring, in this lane's report and on the CR board's `P4.8` row.
#   (2) ONLY THE HISTORY IS PAGED, because only the history is unbounded. The
#       other three are bounded by the ACCOUNT — one position row, one ladder
#       row, and the bills an account can have open at once (a cycle count, not
#       a tenant size).
#   (3) ONE REDUNDANT BOUNDED READ: `account_position` builds a 100-row notices
#       list that this pops, so those rows have ONE representation. Removed by a
#       history-limit parameter on `collections_read.account_position` — which
#       is `P4.2`'s file in this same wave, so this lane does not edit it.
#   (4) NO `days_late` IS COMPUTED HERE. `BR-PAY-032` measures it from `as_of`
#       to `oldest_due_on`, and both travel on the body; computing it in two
#       places is how a screen and a letter come to disagree by a day.
#   (5) A MISSING POSITION IS `null` AND MEANS *owes nothing* — a measured fact.
#       Anything unanswerable is a coded `problems` entry instead.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
