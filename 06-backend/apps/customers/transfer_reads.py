# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (move-in) · US-CUS-005 (move-out) — a transfer is the
#           THIRD path beside them and owns no story of its own yet.
#           Screens: S89 (Transfers tab — the LIST half of task 7.4).
#           ⚠ **NO STORY OWNS S89.** B18 proposes it and
#           `04-docs/05-modules/03-customers/06-epics/` stops short of it —
#           hard-won law 8, the same finding `transfers.py` filed for the write
#           half and `disconnects.py` filed for S90. A story is OWED and is
#           reported rather than invented here.
# Change:   CR-030 W7 task 7.4 (S89 transfers tab — the two-line FROM cell and
#           the stacked MONEY sentences), BACKEND half only.
# Rules:    BR-CUS-015 (`accounts.balance` is a CACHE) · BR-CUS-023 (the
#           deposit is a lookup) · BR-CUS-024 (deposit carry-forward —
#           mechanics PROPOSED) · BR-CUS-025 (closure is the only time the
#           deposit moves) · BR-CUS-053 (the search legs) · BR-CUS-054 (the
#           customer entity and `customer_accounts`) · BR-CUS-057 (deposit
#           interest — CONFIRMED, NOT BUILT) · BR-CUS-081 · BR-CUS-082 ·
#           BR-TEN-043 (the event date is an argument, never a wall clock) ·
#           CLAUDE.md hard rules 1, 2, 4, 5
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7.1 (the five
#           KPI tiles) · §5.7.2 (the list — the two-line FROM cell and the
#           stacked MONEY sentences) · §5.7.3 (the ONE JOB callout) · §5.7.5
#           (TC-TRF-1..6) · §5.7.6 (the five seed rows) · W7 task 7.4
# Tests:    06-backend/tests/test_w7_worklists.py
# ───────────────────────────────────────────────────────
"""W7 task 7.4 · S89's TRANSFERS LIST — the read half, and nothing else.

B18 §5.7, verbatim: *"The same customer, a new address — **one job, not a
move-out followed by a move-in.**"*

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE IS SEPARATE FROM `transfers.py`, AND WHAT IT REUSES
════════════════════════════════════════════════════════════════════════════
`apps/customers/transfers.py` is the WRITER: the table, the five steps, the one
commit, the exclusion contract and the money statement. It is another lane's
file. This module is the READER for S89's list and **it restates none of that
law.** Every derived thing on a row comes back out of the writer:

    transfers._serialize(row, statement)   the row itself, `from_cell` included
    transfers._statement_for(account)      the two MONEY figures and their gaps
    transfers._unavailable_for(statement)  the stated absences, verbatim
    transfers.transfer_half_account_ids()  the exclusion contract (§5.7.3)
    transfers._pair / _display             ONE money formatter for this surface
    transfers._tenant_id()                 ONE tenant resolution

⚠ **SOME OF THOSE NAMES ARE UNDERSCORE-PREFIXED AND THAT IS DELIBERATE, NOT AN
OVERSIGHT.** The alternative is a second serializer, a second money formatter
and a second tenant read on the same surface, and hard-won law 5 is what
happens next: *"One generated file, committed once … Two copies of the OpenAPI
schema drifted within a day."* A private helper reused across two files of the
SAME app, on the same screen, is one derivation grouped two ways; a public copy
of it here would be two derivations that agree until the first amendment. If
`transfers.py`'s lane makes any of them public, this module follows the rename
and nothing else changes.

════════════════════════════════════════════════════════════════════════════
1 · THE TWO-LINE `FROM ACCOUNT` CELL (B18 §5.7.2, TC-TRF-2)
════════════════════════════════════════════════════════════════════════════
B18 §5.7.2, verbatim:

> **`FROM ACCOUNT`** is **two lines**: `A-10650` above, `→ A-11940` beneath in
> ink-45 `[shot]`. The new account number appears **as soon as it exists** and
> reads `→ —` before that

and TC-TRF-2: *"a transfer at step 1 → `→ —` in the FROM ACCOUNT cell, not a
blank"*.

**THE DASH IS NOT PRODUCED HERE.** `transfers._serialize` already builds
`from_cell` as a two-element list and already writes the literal `"→ —"`, with
its own comment saying why: *"a blank second line and an absent one are
indistinguishable once rendered."* This module carries that list through
untouched. A second place that decided what the second line says would be the
place that one day says `None`.

════════════════════════════════════════════════════════════════════════════
2 · THE STACKED `MONEY` SENTENCES, AND THE FOUR ABSENCES (task 7.3's read)
════════════════════════════════════════════════════════════════════════════
B18 §5.7.2, verbatim:

> **`MONEY`** stacks up to two sentences: `deposit carried $153.50` and,
> beneath, `arrear follows $542.10` in **amber** `[shot]`

⚠ **NO MONEY MOVES IN A TRANSFER, AND THE CELL MUST NOT SUGGEST OTHERWISE.**
`transfers.money_statement` serves the two figures plus stated ABSENCES, and
`transfers._unavailable_for` names them. On a row carrying both a deposit and
an arrear they are four:

  1. `transfer_money_rule_does_not_exist` — always. A transfer is a THIRD path
     and no signed rule covers its money; BR-CUS-025/081 and B18 §5.7.6 describe
     different products and choosing between them would be resolving an open
     question by picking a value.
  2. `deposit_carry_has_no_transfer_path` — the deposit is neither refunded nor
     re-collected (TC-TRF-3's guarantee, which IS built) and the POSITION does
     not move either, because BR-CUS-024's mechanics are PROPOSED.
  3. `arrears_follow_has_no_posting_path` — only the ledger posting service
     writes journal lines (hard rule 5) and no account-to-account posting is
     published to customers.
  4. `balance_is_the_cached_ar_figure` — BR-CUS-015. The arrear shown is the
     cache, named so no screen prints it as a ledger-verified number.

and a fifth, `deposit_interest_not_readable`, whenever BR-CUS-057's accrual
cannot be read.

**THE CELL THEREFORE HAS A LINE PER SENTENCE, AND A LINE MAY CARRY NO FIGURE.**
`MoneyStatement.sentences` emits a sentence only when its figure is readable —
which is right, and on its own would make an unreadable deposit look identical
to no deposit at all. So `money.lines` below carries a `deposit_carried` line
with `text: None`, `amount: {"stored": None, "display": None}` and the absence
attached, whenever the account HOLDS a deposit whose carried figure cannot be
stated. The screen renders the absence; it never renders `$0.00`.

⚠ **WHY `$0.00` IS THE ONE THING THAT MUST NEVER APPEAR HERE**, in the writer
lane's own measured words from its red-first proof: reading the unwired
interest seam as `ZERO` served **`'150.00'`** where **`$153.50`** is held —
*"the tempting zero does not merely lose precision, it serves the principal AS
the carried amount and keeps $3.50 of the customer's money."* (❄️ WE-7 / GT-23's
frozen pair.)

**TONE IS DATA, NOT A CAPTION.** §5.7.2 draws the arrear sentence in **amber**;
`lines[].tone` carries it so B14's colour decision is made once, in the design,
and not re-derived by every renderer.

════════════════════════════════════════════════════════════════════════════
3 · THE EXCLUSION CONTRACT IS USED, NEVER RE-IMPLEMENTED (§5.7.3, TC-TRF-1)
════════════════════════════════════════════════════════════════════════════
B18 §5.7.3, verbatim, and it is a callout on the screen:

> **ONE JOB** — *"A transfer appears only here. Its two halves are deliberately
> kept out of Move-ins and Move-outs — the same job listed three times would be
> counted three times."*

This list is the *"only here"* half. It does not filter anything out — a
transfer belongs here by definition — so what it does instead is **publish the
complement**: `exclusion.half_account_ids` is `transfers.transfer_half_account_ids()`
called, not re-derived, and `exclusion.contract` is `transfers.EXCLUSION_CONTRACT`
carried through. A Move-ins or Move-outs list built later can be diffed against
this payload directly, and a test asserts that every account id this list shows
is in that set. If the two ever disagree, one job is about to be counted twice.

════════════════════════════════════════════════════════════════════════════
4 · THE FIVE KPI TILES (B18 §5.7.1), EACH CHECKED AGAINST THE DRAWN FIXTURE
════════════════════════════════════════════════════════════════════════════
| Tile | Caption | Derived from | §5.7.6 |
|---|---|---|---|
| `OPEN` | *same customer, new address* | not done, not cancelled | Park + Osei = **2** ✔ |
| `MOVING THIS WEEK` | *within 7 days of today* | `out_date` in `[as_of, as_of+7]` | Park Aug 28 = **1** ✔ (Osei Sep 14 is not) |
| `DEPOSITS CARRYING` | *not refunded and re-collected* | `deposit_carry_elected` on an open row | Park = **1** ✔ |
| `ARREARS FOLLOWING` | *a debt moving to a new account* | `arrears_follow_elected` on an open row | Park = **1** ✔ |
| `COMPLETED THIS MONTH` | *one job, not two* | committed in the as-of month | Aug 02/05/09 = **3** ✔ |

**THE TWO ELECTION TILES COUNT DECISIONS, NOT MOVEMENTS**, and that is the
writer lane's own reason for storing an election at all: *"The election is what
makes B18 §5.7.1's `DEPOSITS CARRYING · 1` and `ARREARS FOLLOWING · 1`
countable without inventing a figure to count."* Counting them off the FIGURES
instead would count Osei's row the moment somebody opened it, before any human
decided anything.

⚠ **`MOVING THIS WEEK` USES `out_date`, AND THE CHOICE IS STATED.** §5.7.4's
same-day rule says *"outgoing pays the move day, incoming starts the next day
from the same reading"* — so the move day IS the out date, and Park's Aug 28
counts while their Sep 03 in-date does not. Worked against the drawn fixture the
tile reads **1** either way only under `out_date`; under `in_date` it reads 0.

⚠ **`COMPLETED THIS MONTH` IS THE AS-OF MONTH IN THE TENANT'S OWN CALENDAR**
(`seams.tenant_today()`, BR-TEN-043) and the basis is served as DATA
(`period_basis`), the posture `service_request_reads.kpi_strip` takes for the
same problem. No rule states which clock a KPI window uses; naming it beats
picking one silently.

════════════════════════════════════════════════════════════════════════════
5 · THE SEARCH — THREE LEGS OF FOUR, AND THE FOURTH IS SERVED AS ABSENT
════════════════════════════════════════════════════════════════════════════
B18 §5.7.2, verbatim: *"**Search:** "Customer, account #, either address, or
request #…" — **"either address"** is the whole point of the tab"*.

  · **Customer** — `customers.display_name` and `customers.customer_no`, through
    the `customer_accounts` link the transfer row already carries (BR-CUS-054).
    Never a name match against contacts on the ACCOUNT: a transfer is *the same
    customer*, and the entity is the thing being searched.
  · **Account #** — `from_account.account_no` OR `to_account.account_no`, so a
    clerk holding either number finds the one job.
  · **Either address** — `seams.unit_ids_matching(term)` (BR-CUS-053's service
    address / premise / unit-label leg, metering's own selector) matched
    against BOTH `from_account.unit_id` and `transfers.to_unit_id`. This is the
    leg §5.7.2 calls *"the whole point of the tab"*.
  · ⛔ **Request #** — **NOT SUPPORTED, AND SERVED AS AN ABSENCE.** §5.7.6 says
    Park *"links to `SR-26-0047`"*, but `transfers` has NO service-request
    column and no join to one exists (measured 2026-08-25: the `Transfer` model
    holds `from_account`, `to_account`, `customer`, `to_unit_id`, dates, step,
    state, the two elections and the two timestamps). Matching a request number
    would mean minting the link, which is a schema change in a file this lane
    does not own. `search.unavailable` names it and a REGISTER ROW IS OWED.

`MIN_SEARCH_CHARS` is `selectors.MIN_SEARCH_CHARS` (IS-3, two characters),
imported rather than restated: a one-character `A` would otherwise return every
transfer in the tenant through the account-number leg.

════════════════════════════════════════════════════════════════════════════
6 · WHAT IS NOT BUILT HERE, NAMED
════════════════════════════════════════════════════════════════════════════
· **No API route.** `apps/customers/api.py` is outside this lane's write scope.
  The exact `GET /transfers` handler is REPORTED for the merging session to
  paste, and until it is mounted **this list is built and not wired**
  (hard-won law 2) — no gate will say so, because G13 reads the frontend.
· **No screen.** S89's rendering is task 7.4's frontend half.
· **No seed.** §5.7.6's five `[shot]` rows are task 7.12, a data lane's.
· **Cancelled transfers are not listed**, for the reason
  `transfer_half_account_ids` gives for releasing their accounts: *"A cancelled
  job releases its account, because nothing about it happened."* A clerk cannot
  currently find one; stated rather than discovered.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import DateField, F, Q, TextField, Value

from apps.customers import seams, transfers
from core import errors, pagination

# ── the list envelope (11b G5: pagination is mandatory on every list) ───────
#: ONE page-size default for the product — `core.pagination`'s, so a direct
#: caller and a request through `parse_list_params` slice the same page. IS-2's
#: `PAGE_SIZES` vocabulary is clamped at the API edge, not here: this function
#: honours the `per` it is given so a test can ask for two rows.
DEFAULT_PER = pagination.DEFAULT_PAGE_SIZE
MAX_PER = pagination.PAGE_SIZES[-1]

#: B18 §5.7.2's columns, in the drawn order. Served as DATA so the screen and
#: this payload cannot disagree about which cells exist — the same reason
#: `transfers.STEPS` is a tuple rather than a docstring.
#:
#: ⚠ **`reference` LEADS AND B18 §5.7.2 DOES NOT DRAW IT — CR-039 wave D task
#: 15, 2026-08-27.** The design's eight columns are unchanged and follow it;
#: the ninth is the CR's own finding 5 made reachable: *"Transfer and disconnect
#: have tables and no number … A clerk cannot quote a reference"*. A number a
#: clerk cannot SEE is not a number, so the reference goes where a reference
#: goes — first, before the account it is about. The divergence is stamped here
#: rather than left for the next reader to treat as drift.
COLUMNS: tuple[str, ...] = (
    "reference",
    "from_account",
    "customer",
    "from_to",
    "out_date",
    "in_date",
    "step",
    "money",
    "state",
)

#: ⚠ **AMENDED 2026-08-25 — BR-CUS-099, PO ruling closing DEF-688.**
#: B18 §5.7.2 draws the box as *"Customer, account #, either address, or
#: **request #**…"*, and `transfers` has no service-request column and no join
#: to one. Put the two ways — add the link, as `connections.service_request_id`
#: already has it, or drop the leg — the PO ruled **"Drop the leg — remove 'or
#: request #' from the box"**.
#:
#: **So the box now offers exactly what the data can answer.** *"Either
#: address"* stays and is the one that earns its place: a transfer has two, and
#: a clerk may know only the one the customer is leaving.
#:
#: ⚠ **The consequence is a real one and it was accepted, not overlooked:**
#: there is now no way to get from a service request to the transfer it became.
#: It is acceptable because **a transfer can be raised without a request at
#: all**, so the link would be empty on most rows and a search finding only the
#: minority is its own kind of misleading. If the front door becomes the normal
#: way transfers arrive, this is worth revisiting — one nullable column.
SEARCH_HINT = "Customer, account #, or either address…"

#: §5.7.1's caption for `MOVING THIS WEEK`, verbatim, and the window it names.
WEEK_DAYS = 7

#: ⛔ **RESOLVED 2026-08-25 — the leg is GONE, not served as an absence.**
#: This constant recorded that §5.7.2's fourth search leg (`request #`) had no
#: column behind it, and the list served it as a stated absence so no clerk
#: would type a request number and get silence. **`BR-CUS-099` ruled the leg
#: away**, so there is no absence left to state: the box no longer offers it.
#:
#: Kept as the record of what was measured and why, because the decision is
#: cheap to reverse and the next reader needs the finding, not just the outcome:
#: §5.7.6 links `A-11455 · Park, Jenna` to `SR-26-0047`, and the `transfers`
#: table carries no service-request column and no join to one (measured
#: 2026-08-25). `connections.service_request_id` is the shape it would take.
SEARCH_REQUEST_NO_UNLINKED: dict[str, Any] = {
    "code": "transfer_has_no_request_link",
    "br_ref": "BR-CUS-099",
    "withdrawn": True,
    "detail": (
        "WITHDRAWN 2026-08-25 by BR-CUS-099: the PO ruled the request-number search leg away "
        "rather than adding the link, so there is no longer an absence to state. Retained as "
        "the record of the measurement: `transfers` has no service-request column and no join "
        "to one, while B18 §5.7.6 links `A-11455 · Park, Jenna` to `SR-26-0047`."
    ),
}


def _tenant_id() -> Any:
    """ONE tenant resolution for this surface — `transfers._tenant_id`.

    It raises `AuthError(AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")` when
    no tenant is set, which is hard rule 1 stated once. A copy here would be a
    second answer to *"may this query run at all"*.
    """
    return transfers._tenant_id()


def _as_of(as_of: date | None) -> date:
    """BR-TEN-043 — the event date is an argument, never a wall clock.

    The default is the TENANT's today (`seams.tenant_today`), not the server's:
    §5.7.1's `MOVING THIS WEEK` and `COMPLETED THIS MONTH` are both windows a
    clerk reads against their own calendar.
    """
    return as_of or seams.tenant_today()


def _within_the_week(day: date | None, as_of: date) -> bool:
    """§5.7.1's caption, verbatim: *"within 7 days of today"*.

    Inclusive at both ends, and it does NOT reach backwards: a move whose date
    has passed is not "moving this week". Worked on §5.7.6 with the fixture's
    own today: Park's Aug 28 counts, Osei's Sep 14 does not, so the tile reads
    **1**.
    """
    if day is None:
        return False
    return as_of <= day <= as_of + timedelta(days=WEEK_DAYS)


# ═══════════════════════════════════════════════════════════════════════════
# THE MONEY CELL — §5.7.2's stacked sentences, and never a fabricated figure
# ═══════════════════════════════════════════════════════════════════════════
LINE_DEPOSIT = "deposit_carried"
LINE_ARREAR = "arrear_follows"

#: §5.7.2 draws the arrear sentence in **amber**. Tone is DATA so the decision
#: is made once, in the design, rather than re-derived by each renderer.
LINE_TONE: dict[str, str] = {LINE_DEPOSIT: "ink", LINE_ARREAR: "amber"}


def money_cell(statement: transfers.MoneyStatement) -> dict[str, Any]:
    """B18 §5.7.2's MONEY cell — *"stacks up to two sentences"*.

    ⚠ **A LINE MAY CARRY NO FIGURE, AND THAT IS THE POINT.**
    `MoneyStatement.sentences` emits a sentence only when its figure is
    readable, so an account holding $150.00 whose BR-CUS-057 interest cannot be
    read produces NO deposit sentence — indistinguishable, once rendered, from
    an account with no deposit at all. This cell therefore emits the LINE either
    way and leaves `text` and both money strings `None`, with the absence
    attached. **`0.00` is never written into a line**: the writer lane's
    red-first proof measured what the tempting zero actually serves — `'150.00'`
    where `$153.50` is held, keeping $3.50 of the customer's money.

    Every absence dict is `transfers._unavailable_for`'s, carried through
    verbatim. This module authors no explanation of its own about money.
    """
    lines: list[dict[str, Any]] = []
    carried = statement.deposit_carried
    if statement.carries_a_deposit:
        readable = carried is not None
        lines.append(
            {
                "kind": LINE_DEPOSIT,
                "tone": LINE_TONE[LINE_DEPOSIT],
                "text": (f"deposit carried ${transfers._display(carried)}" if readable else None),
                "amount": transfers._pair(carried),
                "unavailable": None if readable else dict(transfers.DEPOSIT_INTEREST_NOT_READABLE),
            }
        )
    if statement.arrear_follows:
        lines.append(
            {
                "kind": LINE_ARREAR,
                "tone": LINE_TONE[LINE_ARREAR],
                "text": f"arrear follows ${transfers._display(statement.arrear)}",
                "amount": transfers._pair(statement.arrear),
                "unavailable": None,
            }
        )
    return {
        "currency": statement.currency,
        "lines": lines,
        # §5.7.2's own rendering, for a screen that wants the strings only.
        # Shorter than `lines` whenever a figure could not be read — which is
        # exactly why `lines` exists beside it.
        "sentences": statement.sentences,
        "gaps": statement.gaps,
        "unavailable": [dict(row) for row in transfers._unavailable_for(statement)],
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE ROW
# ═══════════════════════════════════════════════════════════════════════════
def _premise(unit_id: Any) -> str | None:
    """The service address, through metering's own selector (B1).

    `selectors._premise_cell` is customers' single reader for *"1408 Elm St ·
    A"* and returns `(label, full)`; this takes the full cell. A second
    formatter here would print the same address two ways on two tabs.
    """
    from apps.customers import selectors

    if unit_id is None:
        return None
    _label, premise = selectors._premise_cell(unit_id)
    return premise


def list_row(
    transfer: transfers.Transfer, *, as_of: date, buyers: dict[str, Any] | None = None
) -> dict[str, Any]:
    """One S89 row: `FROM ACCOUNT · CUSTOMER · FROM → TO · OUT DATE · IN DATE ·
    STEP · MONEY · STATE`.

    The base of the row is `transfers._serialize(transfer, statement)` — the
    writer's own shape, `from_cell` (the two lines, dash included) and `state`
    and `step_of` with it. What is added here is only what a LIST needs and a
    detail view does not: the customer's display name and number, the two
    addresses, the `3 of 5` string, and §5.7.2's money cell.
    """
    statement = transfers._statement_for(transfer.from_account)
    row = transfers._serialize(transfer, statement)
    customer = transfer.customer
    # ⛔ **THE BUYER, SERVED FOR THE `Sold to` COLUMN — `DEF-CUS-6462`.** Since
    # 2026-09-20 (`927f82bb4`, migration 0060) `transfers.customer` is the
    # SELLER for good and the buyer is `buyer_customer_id`; the list served only
    # the first, so `Sold to` named the seller on every completed sale. `buyers`
    # is the page's batch (`_buyers_for`); a caller without one reads the row.
    buyer = (
        buyers.get(str(transfer.buyer_customer_id))
        if buyers is not None
        else _customer(transfer.buyer_customer_id)
    )
    if buyer is None and transfer.buyer_customer_id is None and transfer.committed_at is not None:
        # A sale committed BEFORE 0060: that commit overwrote `customer_id`
        # with the buyer, so on these rows `customer` IS who bought it.
        buyer = customer
    to_premise = _premise(transfer.to_unit_id)
    row.update(
        {
            # BR-CUS-054 — the entity, read from the link the transfer carries.
            # ⊕ 0067 — a seller with no customer row is named as the account
            # named them (`transfers.seller_name`) and has no number
            # (`DEF-CUS-6387`).
            "customer": customer.display_name if customer is not None else transfer.seller_name,
            "customer_no": customer.customer_no if customer is not None else None,
            # `DEF-CUS-6462` — who BOUGHT it. `None` until the sale commits
            # (`set_new_customer` names the buyer and stores nothing) and on a
            # sale committed before 0060, whose buyer no column recorded.
            "buyer": buyer.display_name if buyer is not None else None,
            "buyer_no": buyer.customer_no if buyer is not None else None,
            # §5.7.2's `FROM → TO` column. `to` is None before step 2 and the
            # screen renders the absence; the FROM ACCOUNT cell's own dash
            # (`from_cell[1]`) is the writer's and is untouched here.
            "from_to": {
                "from": _premise(transfer.from_account.unit_id),
                "to": to_premise,
                "to_absence": None if to_premise else {"reason": "target_unit_not_chosen_yet"},
            },
            # §5.7.2's `STEP` column — "(of 5)". Built from the writer's own
            # `STEP_COUNT` so a sixth step could never be silently restated.
            "step_cell": f"{transfer.step} of {transfers.STEP_COUNT}",
            "money": money_cell(statement),
            "moving_this_week": _within_the_week(transfer.out_date, as_of),
        }
    )
    return row


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-CUS-5994` — THE SECOND KIND OF ROW: THE PARKED DRAFT (PO 2026-09-20)
# ═══════════════════════════════════════════════════════════════════════════
#: Named on EVERY row rather than inferred from a missing transfer id, which is
#: `BR-CUS-1077`'s posture and `DEF-127`'s lesson: a blank cell and an absent
#: fact read the same way once drawn.
ROW_KIND_TRANSFER = "transfer"
ROW_KIND_PARKED_TRANSFER = "parked_transfer"

#: ⚠ **MINTED, AND DECLARED UNDRAWN.** `Transfer.STATES` has four and every one
#: is a fact about a `transfers` ROW — a job that exists. A parked draft is a
#: `wizard_parks` row and no `transfers` row at all, so none of the four can
#: carry it and reusing `in_progress` would make the STATE cell say something
#: untrue of half the rows under it. The Move-ins tab minted `parked` for the
#: same reason on the same day; the two spellings are deliberately identical.
TRANSFER_STATE_IN_PROGRESS_DRAFT = "in_progress_draft"
TRANSFER_STATE_PARKED = "parked"

#: ⛔ A transfer draft carries no transfer number, and the reason is not a gap.
PARKED_TRANSFER_HAS_NO_REFERENCE: dict[str, Any] = {
    "code": "parked_transfer_has_no_reference",
    "br_ref": "BR-SHL-048",
    "detail": (
        "Nobody has started this transfer job yet — a draft holds what was typed and creates "
        "nothing — so no transfer number has been allocated. The number appears when the job "
        "is raised."
    ),
}

#: ⛔ The money cell on a draft. Nothing has been elected and nothing moves.
PARKED_TRANSFER_HAS_NO_MONEY: dict[str, Any] = {
    "code": "parked_transfer_has_no_money_statement",
    "br_ref": "BR-SHL-048",
    "detail": (
        "Nothing is carried and nothing follows until the transfer is run. A deposit or "
        "arrears election keyed into the wizard is typing, not a decision: every field is "
        "re-validated when the job is executed."
    ),
}

#: ⛔ Which search legs a draft can answer.
PARKED_TRANSFER_SEARCH_LEGS_ARE_NARROWER: dict[str, Any] = {
    "code": "parked_transfer_has_no_account_number_to_search",
    "br_ref": "BR-SHL-048",
    "detail": (
        "A draft joins to nothing — BR-SHL-048 (a) gives `wizard_parks` no foreign key on "
        "purpose — so the account-number and address legs cannot reach one. A parked "
        "transfer answers to the label it was parked under, which is the account headline "
        "the clerk saw when they put it down."
    ),
}


def parks_queryset(*, q: str | None = None, filters: dict[str, Any] | None = None):
    """The transfers a clerk started and put down — `wizard_parks`.

    ⚠ **THE WINDOW, NOT A COLUMN.** PO 2026-09-20, verbatim: *"remove it - it is
    anyway in the list so we dont need it sepretely - if it is not in list add
    it"*. Until that day a parked transfer was drawn on a pinned PANEL above
    this table (`CR-035` amendment 1) and this list could not see it at all.
    `move_out_parks_queryset` is the shape being copied — written 2026-09-19 for
    the Move-outs tab — rather than a second answer being designed.

    ⚠ **READ THROUGH THE SEAM, NEVER THE TABLE.** `wizard_parks` is
    TENANCY-hosted and customers may not import `apps.tenancy.models` (B1 /
    BR-TEN-013; G6 rule 4 refuses it). `seams.wizard_park_queryset` forwards to
    the owning module's own queryset, which carries the tenant filter under RLS
    `FORCE` — hard rule 1 applied where the queryset is BUILT.

    ⚠ **`f.state` IS EXCLUSIVE BETWEEN THE TWO SOURCES**, which is what lets one
    filter work over two tables: `list_queryset` answers `Transfer.STATES` and
    this one answers the two draft codes, and each returns NONE rather than
    EVERYTHING for a value it does not own (BR-SHL-011).
    """
    from apps.customers import selectors

    rows = seams.wizard_park_queryset(flow="transfer")

    state = (filters or {}).get("state")
    if state and state not in (TRANSFER_STATE_IN_PROGRESS_DRAFT, TRANSFER_STATE_PARKED):
        return rows.none()
    if state == TRANSFER_STATE_IN_PROGRESS_DRAFT:
        rows = rows.filter(waiting_on="")
    elif state == TRANSFER_STATE_PARKED:
        rows = rows.exclude(waiting_on="")

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        rows = rows.filter(subject_label__icontains=term)
    return rows


def park_state(park: Any) -> str:
    """`in_progress_draft` or `parked` — told apart by ONE column.

    `WizardPark.waiting_on`'s own docstring: *"EMPTY MEANS *A DRAFT*, NOT *A
    PARK WITH NO REASON*"*. `move_reads.move_out_park_state` reads the same
    column the same way; **the draft got no flag of its own on purpose**, since
    two columns that must agree are two columns free to disagree.
    """
    return (
        TRANSFER_STATE_PARKED
        if (park.waiting_on or "").strip()
        else TRANSFER_STATE_IN_PROGRESS_DRAFT
    )


def park_row(park: Any, *, as_of: date, account: Any | None) -> dict[str, Any]:
    """One UNFINISHED transfer, in the SAME nine cells as a job row.

    ⚠ **THE SHAPE IS IDENTICAL AND THE CONTENT IS NOT, WHICH IS WHAT `row_kind`
    IS FOR.** One screen renders both kinds, so every key a job row carries is
    carried here, with a NAMED absence wherever a draft genuinely cannot answer.
    A row that simply omitted `money` would render as an empty cell, and an
    empty cell and an absent fact are indistinguishable once drawn (`DEF-127`).

    ⚠ **THE STEP IS REAL, AND THAT IS THE IMPROVEMENT.** `wizard_parks.step` is
    the same number `TRANSFER_STEPS` gives the wizard's own rail, so `2 of 5`
    here and `2 of 5` in the wizard cannot drift.

    ⚠ **THE FROM ACCOUNT RESOLVES AND THE TO UNIT DOES NOT.** The transfer
    wizard starts from an account a clerk has already picked, so `subject_ref`
    carries it and it is read back by LOOKUP — never a join, because
    BR-SHL-048 (a) gives the store no foreign key. The unit being taken is
    chosen on a later step and is genuinely not known yet, which is the same
    absence `from_to.to_absence` already states for a job at step 1.
    """
    parked_at = park.parked_at
    return {
        "id": None,
        "row_kind": ROW_KIND_PARKED_TRANSFER,
        # The handle RESUME is built from — `?parked=<id>`. Nothing prints it,
        # so B14 rule 31 is not in play.
        "park_id": str(park.id),
        "transfer_no": None,
        "transfer_no_unavailable": dict(PARKED_TRANSFER_HAS_NO_REFERENCE),
        "state": park_state(park),
        "step": int(park.step),
        "step_of": transfers.STEP_COUNT,
        "step_label": None,
        "step_cell": f"{int(park.step)} of {transfers.STEP_COUNT}",
        "customer_id": None,
        "customer": None,
        "customer_no": None,
        # The label the clerk parked under — the account headline they saw,
        # COPIED at that moment and deliberately stale
        # (`WizardPark.subject_label`). Named as its own source so a reader can
        # tell it from the BR-CUS-054 entity.
        "customer_absence": {
            "code": "parked_transfer_customer_from_the_draft_label",
            "br_ref": "BR-SHL-048 · BR-CUS-054",
            "detail": (
                "Nobody has raised this transfer, so it names no customer record. The name "
                "shown is the label the draft was parked under: what the clerk saw when they "
                "started, copied at that moment and never re-read."
            ),
        },
        "from_account_id": str(account.id) if account is not None else None,
        "from_account_no": getattr(account, "account_no", None),
        "to_account_id": None,
        "to_account_no": None,
        "from_cell": [
            getattr(account, "account_no", None) or (park.subject_label or "—"),
            "→ —",
        ],
        "to_unit_id": None,
        "from_to": {
            "from": _premise(account.unit_id) if account is not None else None,
            "to": None,
            "to_absence": {"reason": "target_unit_not_chosen_yet"},
        },
        # ⛔ NEITHER DATE IS SET. Both are asked for inside the wizard, and a
        # draft parked before them holds neither — which is a fact about how far
        # the clerk got, not a gap in the store.
        "out_date": None,
        "in_date": None,
        "same_day": None,
        "deposit_carry_elected": None,
        "arrears_follow_elected": None,
        "committed_at": None,
        "cancelled_at": None,
        "money": {
            "currency": None,
            "lines": [],
            "sentences": [],
            "gaps": [],
            "unavailable": [dict(PARKED_TRANSFER_HAS_NO_MONEY)],
        },
        # A draft with no out date is not moving this week — it is not moving on
        # any stated day at all, and `False` says so without inventing one.
        "moving_this_week": False,
        # ⚠ **WHAT THE PANEL CARRIED, MOVED ONTO THE ROW (`DEF-CUS-5994`).**
        # Why it stopped, the clerk's own note, the remind-on date and whose
        # desk it is. `Parked by` is what `CR-035` amendment 1 put in place of a
        # mine/everyone's toggle, so losing it would re-open a closed question.
        "waiting_on": park.waiting_on or None,
        "park_note": park.park_note or None,
        "remind_on": park.remind_on.isoformat() if park.remind_on else None,
        "parked_at": parked_at.isoformat() if parked_at else None,
        "age_days": (as_of - parked_at.date()).days if parked_at else None,
        "parked_by_name": (
            (getattr(park.parked_by, "full_name", "") or None)
            if getattr(park, "parked_by_id", None)
            else None
        ),
    }


def _accounts_for_parks(parks: list[Any]) -> dict[str, Any]:
    """The accounts a page's drafts named — ONE query, never one per draft.

    ⚠ **A LOOKUP, NEVER A JOIN, AND THE DIFFERENCE IS THE RULING.** BR-SHL-048
    (a) gives `wizard_parks` no foreign key on purpose, so this reads the copied
    id out of `subject_ref` and asks `accounts` for it by id under the tenant
    filter. Nothing joins to a draft and nothing is blocked by one; an account
    that has since gone simply does not come back, and the row falls through to
    the parked label. `move_reads._accounts_for_parks` is the same function one
    module over and this is deliberately its twin.
    """
    from apps.customers import models as customers_models

    ids = []
    for park in parks:
        subject = park.subject_ref if isinstance(park.subject_ref, dict) else {}
        account_id = subject.get("account_id")
        if account_id:
            ids.append(str(account_id))
    if not ids:
        return {}
    return {
        str(row.id): row
        for row in customers_models.Account.objects.filter(
            tenant_id=_tenant_id(), id__in=ids
        ).select_related("status")
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE QUERY
# ═══════════════════════════════════════════════════════════════════════════
#: CR-045 wave D task D.12 (DEF-1702) — the one dimension S89 declares.
#: `Transfer.STATES` minus `cancelled`, because `list_queryset` excludes
#: cancelled jobs from the list itself (§6): offering an option that can never
#: return a row is a control that reports "none" for a reason the user cannot
#: see.
TRANSFER_FILTERS: tuple[str, ...] = ("state",)
TRANSFER_FILTER_STATES: tuple[str, ...] = tuple(
    state for state in transfers.Transfer.STATES if state != transfers.Transfer.STATE_CANCELLED
)


#: ── §5.7.2's SORT VOCABULARY (`BR-CUS-1046`, PO 2026-09-12) ────────────────
#: ⚠ **THIS TAB'S DEFAULT DID NOT MOVE, AND IT IS STILL IN THE SIX.** Transfers
#: already opened `-created_at, -id` — *"Newest job first"* — so `BR-CUS-1046`
#: asked nothing of it. What it had NO answer to was the rule's second clause:
#: *"a clerk's chosen sort must still win and still survive a refresh"*. There
#: was no sort to choose. `OQ-CUS-1790` measured that on six lists, this one
#: among them, and the PO chose option (c): *"the six gain a sort control."*
SORTS: dict[str, tuple[Any, ...]] = {
    #: ⚠ **WRITTEN ASCENDING, LIKE EVERY TERM IN THIS MAP — `order_terms` FLIPS
    #: IT AND `DEFAULT_DIR` IS `desc`.** The first draft of this pass stored
    #: `-created_at` here AND defaulted to `desc`, so the flip cancelled the
    #: minus and every list opened on the OLDEST row: the exact inversion of
    #: the ruling, shipped as a working feature. Nothing raised — it was found
    #: by curling the endpoint and reading the first three rows.
    "created": ("created_at", "id"),
    "reference": ("reference", "id"),
    "out_date": ("from_account__closed_at", "id"),
    "in_date": ("to_account__opened_at", "id"),
    "state": ("state", "id"),
}
DEFAULT_SORT = "created"
DEFAULT_DIR = "desc"


def list_queryset(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    dir: str = DEFAULT_DIR,
):
    """Every live transfer for this tenant, newest job first, with §5.7.2's search.

    Cancelled jobs are excluded — see §6 of the module docstring.

    ⚠ **THE DEFAULT IS UNCHANGED BY `BR-CUS-1046` — ONLY THE CONTROL IS NEW.**
    See `SORTS` above for why a list that already complied is still one of the
    six the PO's ruling names.
    """
    from apps.customers import selectors

    rows = (
        transfers.Transfer.objects.filter(tenant_id=_tenant_id())
        .exclude(state=transfers.Transfer.STATE_CANCELLED)
        .select_related("from_account", "to_account", "customer")
    )
    # ── CR-045 wave D task D.12 · `f.state`, applied in SQL ───────────────
    # `cancelled` is excluded above and is therefore not an option; asking for
    # it returns nothing rather than re-admitting the rows the list excludes.
    state = (filters or {}).get("state")
    if state:
        rows = rows.filter(state=str(state)) if str(state) in TRANSFER_FILTER_STATES else rows.none()
    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        # BR-CUS-053's address leg, through metering's own selector. It answers
        # unit ids, and a transfer touches TWO units — the one being left
        # (`from_account.unit_id`) and the one being taken (`to_unit_id`) —
        # which is §5.7.2's *"either address"* in one OR-group.
        unit_ids = [str(unit_id) for unit_id in seams.unit_ids_matching(term)]
        matches = Q(from_account__account_no__icontains=term)
        matches |= Q(to_account__account_no__icontains=term)
        matches |= Q(customer__display_name__icontains=term)
        # ⊕ 0067 — a sale of an account with nobody linked is found by the
        # name it recorded (`DEF-CUS-6387`).
        matches |= Q(seller_name__icontains=term)
        matches |= Q(customer__customer_no__icontains=term)
        if unit_ids:
            matches |= Q(from_account__unit_id__in=unit_ids)
            matches |= Q(to_unit_id__in=unit_ids)
        rows = rows.filter(matches)
    # Newest job first: the tab is a worklist and the job started last is the
    # one a clerk is still holding. Secondary by id for a stable page boundary
    # (IS-2), so row 26 does not reappear on page 2. Since 2026-09-12 that pair
    # is `SORTS["created"]` and is the DEFAULT rather than the only option.
    return rows.order_by(*pagination.order_terms(sort, dir, columns=SORTS, default=DEFAULT_SORT))


#: The ORDER of the union, over the columns BOTH kinds can publish.
#:
#: ⚠ **`reference` IS ALIASED ON BOTH SIDES, AND FIXING IT WAS NOT THE POINT OF
#: THIS CHANGE (`DEF-CUS-6004`).** `SORTS["reference"]` above reads
#: `("reference", "id")` and **`Transfer` HAS NO `reference` FIELD** — the
#: column is `transfer_no`. So `GET /transfers?sort=reference` raised
#: `FieldError` from 2026-09-13, on a sort name the endpoint publishes in its
#: own `sorts` list. Nothing caught it because no test asks for a sort by name
#: and a list that opens on its default never reaches the line. `wizard_parks`
#: DOES carry a `reference`, so the union has to alias one name over two real
#: columns anyway, and the alias is what makes both sides orderable.
#:
#: ⚠ **TWO OF THE FIVE ARE NULL ON A DRAFT, STATED RATHER THAN PAPERED OVER** —
#: `_move_out_page_keys`' own note, and the reasoning is identical. A draft has
#: no out date and no in date, so those sorts put every unfinished row in one
#: block at whichever end the database puts NULLs. The DEFAULT is `created`,
#: which both sides hold as a real column, so the list a clerk opens is ordered
#: properly over both kinds.
TRANSFER_UNION_SORTS: dict[str, tuple[Any, ...]] = {
    "created": ("created_at", "id"),
    "reference": ("ref_no", "id"),
    "out_date": ("out_on", "id"),
    "in_date": ("in_on", "id"),
    "state": ("state_key", "id"),
}


def _page_keys(
    *,
    q: str | None,
    filters: dict[str, Any] | None,
    sort: str | None,
    dir: str,
    page: int,
    per: int,
) -> tuple[int, list[tuple[str, str]]]:
    """ONE ordered, paginated window over BOTH kinds of row — in SQL.

    Returns `(total, [(row_kind, id), …])`, and the LIST is the order the page
    must be rendered in. `move_reads._move_out_page_keys` is the precedent and
    its reasoning is quoted rather than re-argued: `NFR-3` requires server
    pagination and `NFR-5` forbids a cap, so the page is a `LIMIT`/`OFFSET` over
    ONE order. Merging two materialised lists would read every transfer and
    every draft on every request — correct at three thousand accounts and
    thirteen times short at forty thousand.

    ⚠ **`.order_by()` WITH NO ARGUMENTS ON EACH ARM.** PostgreSQL and SQLite
    both refuse an `ORDER BY` inside a compound statement's arms, and
    `list_queryset` orders its own rows before returning them. The order that
    matters is applied to the UNION, once, over both kinds.

    ⚠ **EVERY SORT IS TOTAL** — `id` ends every tuple, or two rows comparing
    equal across the union swap between page 1 and page 2, showing a clerk one
    row twice and another never.

    ⚠ **TYPED `Value`s, NOT BARE `None`s**: a bare `None` leaves PostgreSQL to
    guess a type for a `UNION` arm and it refuses rather than guessing. The two
    sides must publish the same columns, in the same order, with the same types.
    """
    jobs = (
        list_queryset(q=q, filters=filters, sort=sort, dir=dir)
        .order_by()
        .annotate(
            row_kind=Value(ROW_KIND_TRANSFER, output_field=TextField()),
            ref_no=F("transfer_no"),
            out_on=F("from_account__closed_at"),
            in_on=F("to_account__opened_at"),
            state_key=F("state"),
        )
        .values("id", "row_kind", "created_at", "ref_no", "out_on", "in_on", "state_key")
    )
    parks = (
        parks_queryset(q=q, filters=filters)
        .order_by()
        .annotate(
            row_kind=Value(ROW_KIND_PARKED_TRANSFER, output_field=TextField()),
            ref_no=F("reference"),
            out_on=Value(None, output_field=DateField()),
            in_on=Value(None, output_field=DateField()),
            state_key=Value(None, output_field=TextField()),
        )
        .values("id", "row_kind", "created_at", "ref_no", "out_on", "in_on", "state_key")
    )
    combined = jobs.union(parks).order_by(
        *pagination.order_terms(
            sort, dir, columns=TRANSFER_UNION_SORTS, default=DEFAULT_SORT
        )
    )
    total = combined.count()
    start = (page - 1) * per
    return total, [
        (str(row["row_kind"]), str(row["id"])) for row in combined[start : start + per]
    ]


def _fetch_page(keys: list[tuple[str, str]]) -> tuple[list[Any], list[Any]]:
    """The page's rows, ONE query per kind, from the ids the union chose.

    The union answers *which rows and in what order*; these two reads answer
    *what is on them*. Two queries for a page, whatever the page size.
    """
    job_ids = [key for kind, key in keys if kind == ROW_KIND_TRANSFER]
    park_ids = [key for kind, key in keys if kind == ROW_KIND_PARKED_TRANSFER]
    jobs = (
        list(
            transfers.Transfer.objects.filter(tenant_id=_tenant_id(), id__in=job_ids)
            .select_related("from_account", "to_account", "customer")
        )
        if job_ids
        else []
    )
    parks = (
        list(seams.wizard_park_queryset(flow="transfer").filter(id__in=park_ids))
        if park_ids
        else []
    )
    return jobs, parks


def _buyers_for(window: list[Any]) -> dict[str, Any]:
    """The page's buyers, ONE query whatever the page size (`DEF-CUS-6462`).

    Keyed by the id as a string, because `buyer_customer_id` is a bare
    `UUIDField` with no foreign key to `select_related` through (0060).
    """
    ids = {row.buyer_customer_id for row in window if row.buyer_customer_id}
    if not ids:
        return {}
    from apps.customers import models as cmodels

    return {
        str(customer.id): customer
        for customer in cmodels.Customer.objects.filter(tenant_id=_tenant_id(), id__in=ids)
    }


def kpi_strip(*, as_of: date | None = None) -> dict[str, Any]:
    """B18 §5.7.1's five tiles. Every count is checked against §5.7.6's own five
    rows in the module docstring's table — 2 · 1 · 1 · 1 · 3.
    """
    on = _as_of(as_of)
    base = transfers.Transfer.objects.filter(tenant_id=_tenant_id()).exclude(
        state=transfers.Transfer.STATE_CANCELLED
    )
    live = base.filter(committed_at__isnull=True)
    month_start = on.replace(day=1)
    return {
        # *"same customer, new address"* — a job that has not committed yet.
        "open": live.count(),
        # *"within 7 days of today"* — see `_within_the_week`.
        "moving_this_week": sum(
            1 for day in live.values_list("out_date", flat=True) if _within_the_week(day, on)
        ),
        # *"not refunded and re-collected"* — the clerk's ELECTION, not a
        # figure. Counting figures would count a row nobody had decided.
        "deposits_carrying": live.filter(deposit_carry_elected=True).count(),
        # *"a debt moving to a new account"* — the election again.
        "arrears_following": live.filter(arrears_follow_elected=True).count(),
        # *"one job, not two"* — committed inside the as-of month.
        "completed_this_month": base.filter(
            committed_at__date__gte=month_start, committed_at__date__lte=on
        ).count(),
        # No rule states which clock a KPI window uses; the basis is served as
        # DATA rather than assumed (the `service_request_reads` posture).
        "period_basis": "tenant_month_to_date",
        "as_of": on.isoformat(),
    }


def list_transfers(
    *,
    q: str | None = None,
    page: int = 1,
    per: int = DEFAULT_PER,
    as_of: date | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    dir: str = DEFAULT_DIR,
) -> dict[str, Any]:
    """S89's list — B18 §5.7.2's rows, §5.7.1's KPI strip, §5.7.3's contract.

    Returns `{"rows", "kpis", "page", "per", "total", "pages", "columns",
    "search", "exclusion"}`.

    ⚠ **`exclusion` IS THE COUNTING CONTRACT, PUBLISHED RATHER THAN RESTATED.**
    §5.7.3: *"A transfer appears only here. Its two halves are deliberately kept
    out of Move-ins and Move-outs — the same job listed three times would be
    counted three times."* `half_account_ids` is
    `transfers.transfer_half_account_ids()` called, so the set a Move-ins or
    Move-outs list must subtract is the SAME set this list was built from, and a
    test asserts every row's two account ids are in it.
    """
    on = _as_of(as_of)
    page = max(1, int(page or 1))
    per = max(1, min(int(per or DEFAULT_PER), MAX_PER))
    # ── `DEF-CUS-5994` · TWO KINDS OF ROW, ONE ORDER, DECIDED IN SQL ─────
    # PO 2026-09-20: *"remove it - it is anyway in the list so we dont need it
    # sepretely - if it is not in list add it"*. The drafts that used to sit on
    # a pinned panel above this table are rows of it now, and the DATABASE
    # decides the order and the page over both kinds — never a Python splice
    # into a server-paged list.
    total, keys = _page_keys(q=q, filters=filters, sort=sort, dir=dir, page=page, per=per)
    window, park_window = _fetch_page(keys)
    park_accounts = _accounts_for_parks(park_window)
    buyers = _buyers_for(window)
    built: dict[str, dict[str, Any]] = {
        str(row.id): {
            **list_row(row, as_of=on, buyers=buyers),
            "row_kind": ROW_KIND_TRANSFER,
            "park_id": None,
        }
        for row in window
    }
    built.update(
        {
            str(park.id): park_row(
                park,
                as_of=on,
                account=park_accounts.get(
                    str((park.subject_ref or {}).get("account_id"))
                    if isinstance(park.subject_ref, dict)
                    else ""
                ),
            )
            for park in park_window
        }
    )
    return {
        "rows": [built[key] for _kind, key in keys if key in built],
        "kpis": kpi_strip(as_of=on),
        "page": page,
        "per": per,
        "total": total,
        "pages": (total + per - 1) // per if per else 0,
        "columns": list(COLUMNS),
        # CR-045 wave D task D.12 — the `f.<name>` vocabulary and the states it
        # accepts, served so the screen cannot offer `cancelled` (BR-SHL-010).
        "filters": list(TRANSFER_FILTERS),
        # …and the SORT names, on the same contract (`BR-CUS-1046`).
        "sorts": list(SORTS),
        "sort": sort if sort in SORTS else DEFAULT_SORT,
        "dir": dir,
        # `DEF-CUS-5994` — the two DRAFT codes join the vocabulary, each marked
        # `drawn: False` so no screen mistakes one for a B18 segment. They are
        # facts about a `wizard_parks` row rather than about a transfer job,
        # which is why they could not reuse `in_progress`.
        "states": (
            [{"code": code, "drawn": True} for code in TRANSFER_FILTER_STATES]
            + [
                {"code": TRANSFER_STATE_IN_PROGRESS_DRAFT, "label": "Draft", "drawn": False},
                {"code": TRANSFER_STATE_PARKED, "label": "Parked", "drawn": False},
            ]
        ),
        "steps": [{"step": n, "label": label} for n, label in transfers.STEPS],
        "search": {
            "hint": SEARCH_HINT,
            "min_chars": _min_search_chars(),
            "legs": ("customer", "account_no", "either_address"),
            # ⚠ EMPTY SINCE 2026-08-25 (BR-CUS-099). This carried
            # `SEARCH_REQUEST_NO_UNLINKED` so a clerk typing a request number met
            # a sentence rather than silence. The PO ruled the leg away instead
            # of adding the link, so there is no absence left to state — the box
            # does not offer it. The list is kept, not deleted, because a screen
            # that reads `unavailable` must keep working when it is empty.
            # ⚠ NO LONGER EMPTY — `DEF-CUS-5994` put a second kind of row on
            # this list and a draft cannot answer the account-number or address
            # legs. It was emptied in 2026-08-25 when BR-CUS-099 ruled the
            # `request #` leg away; the list was kept rather than deleted
            # precisely so a screen reading it keeps working either way.
            "unavailable": [dict(PARKED_TRANSFER_SEARCH_LEGS_ARE_NARROWER)],
        },
        "exclusion": {
            "callout": (
                "A transfer appears only here. Its two halves are deliberately kept out of "
                "Move-ins and Move-outs — the same job listed three times would be counted "
                "three times."
            ),
            "contract": list(transfers.EXCLUSION_CONTRACT),
            "half_account_ids": sorted(transfers.transfer_half_account_ids()),
        },
        "as_of": on.isoformat(),
    }


def _min_search_chars() -> int:
    from apps.customers import selectors

    return selectors.MIN_SEARCH_CHARS


# ═══════════════════════════════════════════════════════════════════════════
# THE TRANSFER RECORD — `GET /transfers/{ref}` (blueprint p133–p134)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⛔ **UNTIL TODAY A CLERK COULD MAKE A SALE AND HAD NO WAY TO READ IT BACK.**
# The conformance file `04-docs/05-modules/03-customers/conformance/
# transfer-against-its-blueprint.md` §10 ranks this page FIRST of everything
# the transfer surface still needs, in those words. The screen has existed
# since `TransferRecordPage.tsx` landed and has rendered its NOT-FOUND branch
# at every address, because nothing answered.
#
# ⚠ **THE REFERENCE IS THE KEY, NEVER THE UUID** (B14 rule 31). The blueprint's
# own URL is `/brazosbend/transfers/trf-26-0021`; `TRF-26-0001` is what a clerk
# quotes down a phone, ruled by the PO on 2026-08-27 when `OQ-426` closed.
# Matching is case-insensitive because the drawn URL is lower and the number a
# clerk reads is upper — `move_record_reads.record_detail`'s reasoning, reused
# rather than re-argued.
#
# ⚠ **AND THE ID IS ACCEPTED AS A FALLBACK, WHICH IS NOT A CONTRADICTION.**
# `transfer-record-what-is-durable.md` §1 says so in terms: a tenant
# provisioned before the `transfer` series was seeded has no catalogue row, and
# `_allocate_transfer_no` REPORTS rather than raises, so a real row can carry
# `transfer_no = NULL`. Such a sale would otherwise be unreadable for ever.
# **The fallback is a way IN, never a way to DISPLAY one** — `reference` still
# serves the server's own stated absence, and `TransferRecordPage` renders that
# absence rather than a uuid.
#
# ────────────────────────────────────────────────────────────────────────────
# WHAT THIS CAN ANSWER AND WHAT IT CANNOT — MEASURED, NOT ASSUMED
# ────────────────────────────────────────────────────────────────────────────
# `transfer-record-what-is-durable.md` measured this page against the database
# on 2026-09-20 and found FOUR drawn facts with no durable home. **One of the
# four closed the same day and three did not:**
#
#   ✅ **`Sold by` IS NOW SERVABLE.** That file's §3 called the seller this
#      page's blocker, because `reassign_account` DELETED the seller's link and
#      overwrote `transfers.customer_id` with the buyer's. Both halves were
#      reversed on 2026-09-20 (`customers/0060`): the link is ENDED rather than
#      deleted, `customer_id` keeps naming the SELLER permanently, and the
#      BUYER got `buyer_customer_id` of its own. So the drawn title
#      `Tan, Wei → Ferraro, L.` renders from one row, and §3's instruction to
#      put `Sold by` under *What this record does not say* is SUPERSEDED. ⚠ It
#      also warned **do not add `transfers.sold_by_customer_id`** — nobody did;
#      the column that arrived names the buyer, and the seller kept the one he
#      already had.
#   ⛔ **the balance and the deposit AS THEY STOOD.** Computed at commit, put
#      on the response and the audit row, stored NOWHERE. §4's fix is two
#      nullable `NUMERIC(18,4)` columns on `transfers`, which is a migration
#      this read does not make. **AND THE DRAWING FORBIDS THE OBVIOUS
#      WORKAROUND:** every figure is *"as it stood on the day, not as it stands
#      now"*, so reading today's `accounts.balance` and labelling it the sale's
#      figure would be wrong by exactly the amount the account has moved since
#      — a wrong number on a money path, which is worse than a blank. Both are
#      STATED ABSENCES.
#   ⛔ **`Buyer matched or created`.** `link_customer` returns it and the
#      commit puts it on the response; nothing stores it. §4's fix is a
#      nullable boolean beside the two figures. Stated absence.
#   ⛔ **`Committed by`.** No `transfers.committed_by`. The name is in
#      `audit_log`, **which is pruned on a retention schedule** — and CLAUDE.md
#      hard rule 4 forbids any document, screen or docstring describing that as
#      a permanent record. Stated absence rather than a log scrape.
#   ⛔ **the ledger's unbroken span** (*"38 months"*). Derivable as a query and
#      counted by nothing today; the same gap step 1's `Ledger` row has.
#
# ⚠ **A `$0.00` WHERE A FIGURE COULD NOT BE COMPUTED IS A MONEY CLAIM, NOT A
# BLANK.** A sibling shipped `Short by $0.00` under its own sentence saying the
# subtraction had not run, and it was filed as a defect the same day. Every
# money cell here is the server's figure or a named absence.
#
# ⚠ **`Refunded to the seller` AND `Re-collected from the buyer` ARE THE ONE
# EXCEPTION, AND THEY ARE A PROHIBITION RATHER THAN A MEASUREMENT.**
# `BR-CUS-085`: *"nothing is refunded and re-collected"*, and `reassign_account`
# commits `"refund_raised": False` with a test asserting it. They are served as
# `0.0000` FROM THE RULE — a non-zero would mean the rule had been broken and
# the screen must show it. Rendering them as an absence would say *"we did not
# check"* about the single fact this page exists to prove.
#
# ⚠ **NO ACTIONS, AND THAT IS THE ANSWER RATHER THAN A GAP.** The blueprint
# says so under the drawing: *"Drawing a button here would invent a decision
# the product does not offer."* This read serves **DOORS** — `Open the
# customer` and `Open the account` — and no verb.

#: The wire shape's three stated absences, spelled ONCE so the screen, a test
#: and a later migration all read the same sentence. Each carries `code` and
#: `detail`, which are the two fields `TransferRecordPage.Absent` reads.
SALE_FIGURE_NOT_STORED = {
    "code": "sale_figure_not_stored",
    "br_ref": "BR-CUS-1030",
    "detail": (
        "the balance and the deposit as they stood on the day of sale are computed at "
        "commit and are not stored on any row, so this record cannot state them. Today's "
        "account balance is NOT shown in their place: it has moved by every payment and "
        "every bill since, so it would be wrong by exactly that amount on a money path. "
        "Two nullable columns on `transfers` are the fix and are a migration this read "
        "does not make."
    ),
}
BUYER_MATCH_NOT_STORED = {
    "code": "buyer_match_not_stored",
    "br_ref": "BR-CUS-1024",
    "detail": (
        "whether the buyer was matched to a customer this utility already had, or was "
        "minted a new number, is decided at commit and put on the response. Nothing "
        "stores it, so a record read later cannot say which happened."
    ),
}
COMMITTED_BY_NOT_STORED = {
    "code": "committed_by_not_stored",
    "br_ref": "BR-CUS-1030",
    "detail": (
        "`transfers` has no column for who committed the sale. The name is in the audit "
        "log, which is pruned on a retention schedule, so reading it here would make this "
        "record say something that stops being true without warning."
    ),
}
LEDGER_SPAN_NOT_COUNTED = {
    "code": "ledger_span_not_counted",
    "br_ref": "BR-CUS-1030",
    "detail": (
        "how many months this account's ledger runs unbroken is derivable from the "
        "account's own postings and is counted nowhere in this product today."
    ),
}
DEPOSIT_INTEREST_AT_SETTLEMENT = {
    "code": "deposit_interest_at_settlement",
    "br_ref": "BR-CUS-057",
    "detail": (
        "deposit interest is computed at settlement (PO ruling 2026-09-19), and a sale "
        "settles nothing — the deposit stays on the account. So on the day of a sale "
        "there is no interest figure to show."
    ),
}
IDENTIFIER_NOT_RECORDED = {
    "code": "identifier_not_recorded",
    "br_ref": "BR-CUS-089",
    "detail": "no government identifier was captured for this buyer.",
}
NOT_COMMITTED_YET = {
    "code": "transfer_not_committed",
    "br_ref": "BR-CUS-1030",
    "detail": "this sale has not been committed, so the facts it would record do not exist yet.",
}

#: `BR-CUS-085` stated as arithmetic. **A CONSTANT OF THE RULE AND NOT A
#: READING** — see the block above for why these two alone carry a figure the
#: database was never asked for. Four decimals, as a STRING (hard rule 2).
REFUND_PROHIBITED = "0.0000"

#: `state` → the head chip the screen draws. The screen's own vocabulary is
#: three words and `transfers` has four states, so the mapping is stated here
#: rather than left to a `startswith` on the screen.
RECORD_STATES = {
    transfers.Transfer.STATE_DONE: "completed",
    transfers.Transfer.STATE_CANCELLED: "cancelled",
    transfers.Transfer.STATE_SCHEDULED: "in_flight",
    transfers.Transfer.STATE_IN_PROGRESS: "in_flight",
}

#: Which government identifier a buyer gave, in the order `BR-CUS-089` weighs
#: them. ⚠ **THE KIND, NEVER THE NUMBER** — `BR-CUS-092` keeps the value
#: app-layer encrypted, and a licence number on a record page would be a
#: government id rendered to anyone who can open a sale.
IDENTIFIER_KINDS: tuple[tuple[str, str], ...] = (
    ("ssn", "ssn"),
    ("driving_licence", "driving_licence"),
    ("tax_id", "tax_id"),
)


def _committed_by_fact(row: Any, committed: bool) -> dict[str, Any]:
    """`{name, at}` off the sale's own row (`DEF-CUS-9692`), or why not."""
    if not committed:
        return _fact(None, NOT_COMMITTED_YET)
    user_id = getattr(row, "committed_by_id", None)
    if user_id is None:
        return _fact(None, COMMITTED_BY_NOT_STORED)
    from apps.identity.models import User

    user = User.objects.filter(pk=user_id).first()
    name = (getattr(user, "full_name", "") or "").strip() or None if user else None
    return _fact(
        {"name": name, "at": row.committed_at.isoformat() if row.committed_at else None}
    )


def _fact(value: Any, absence: dict[str, Any] | None = None) -> dict[str, Any]:
    """One label→value cell: a value, OR the reason there is none.

    ⚠ **NEVER BOTH AND NEVER NEITHER** — `move_record_reads._fact`'s rule and
    its exact shape, reused so the two record screens cannot learn to render
    `null` two ways. A cell carrying a value AND an absence lets a screen draw
    whichever it reaches for first.
    """
    if value is not None and value != "":
        return {"value": value, "unavailable": None}
    return {"value": None, "unavailable": dict(absence) if absence else None}


def record_detail(ref: str) -> dict[str, Any]:
    """One sale, as `/transfers/{ref}` draws it. The blueprint's four sections.

    `WHAT HAPPENED` · `WHAT DID NOT CHANGE` · `THE MONEY, AS IT STOOD ON THE
    DAY` · `WHAT THIS RECORD DOES NOT SAY`, plus the head and the two doors.

    ⚠ **NOTHING IS COMPUTED HERE AND NOTHING IS DEFAULTED.** Every figure is a
    stored value or a named absence, and the two `BR-CUS-085` prohibitions are
    the single stated exception (see the block above). The total is NOT added
    up — `taken_on` is an absence for as long as its two parts are, because
    adding money on a read is what CLAUDE.md hard rule 2 and B4 put on the
    other side of the wire.
    """
    from apps.customers import selectors

    key = (ref or "").strip()
    if not key:
        raise errors.deny_as_not_found("BR-CUS-1030")

    row = (
        transfers.Transfer.objects.filter(tenant_id=transfers._tenant_id(), transfer_no__iexact=key)
        .select_related("from_account", "customer")
        .first()
    )
    if row is None:
        row = _by_id(key)
    if row is None:
        # A reference this tenant does not hold is a 404 and never a 403
        # (HR-1): the boundary must not confirm that the row exists somewhere
        # else. `move_record_reads` says the same at the same point.
        raise errors.deny_as_not_found("BR-CUS-1030")

    account = row.from_account
    committed = row.committed_at is not None
    buyer = _customer(row.buyer_customer_id)
    seller = row.customer
    label, premise = selectors._premise_cell(account.unit_id, account=account)

    return {
        "state": RECORD_STATES.get(row.state, "in_flight"),
        "reference": _fact(
            row.transfer_no,
            # ⚠ **THE SERVER'S OWN ABSENCE, NOT ONE INVENTED HERE.**
            # `transfers.TRANSFER_NUMBER_UNAVAILABLE` carries `code`, `series`,
            # `open_question` and `detail`, and the screen's type reads `code`
            # and `detail` off exactly that shape. A second wording would make
            # two surfaces explain one gap differently.
            dict(transfers.TRANSFER_NUMBER_UNAVAILABLE),
        ),
        "buyer_name": _fact(buyer.display_name if buyer else None, NOT_COMMITTED_YET),
        # ⛔ **THE LEFT HALF OF THE DRAWN TITLE, AND IT IS SERVABLE SINCE
        # 2026-09-20.** `transfers.customer_id` names the SELLER permanently —
        # the overwrite that lost him was itself the defect.
        "seller_name": _fact(seller.display_name if seller else row.seller_name),
        "what_happened": {
            "account": _fact(account.account_no),
            "unit": _fact(label),
            "service_address": _fact(premise),
            "sold_on": _fact(row.out_date.isoformat() if row.out_date else None),
            "sold_by": _fact(seller.display_name if seller else row.seller_name),
            "sold_to": _fact(buyer.display_name if buyer else None, NOT_COMMITTED_YET),
            "buyer_kind": _fact(buyer.kind if buyer else None, NOT_COMMITTED_YET),
            "identifier_given": _fact(_identifier_kind(buyer), IDENTIFIER_NOT_RECORDED),
            "buyer_matched": _fact(None, BUYER_MATCH_NOT_STORED),
            "changeover_read": _fact(_changeover(row)),
            # ⛔ **TWO ABSENCES, CHOSEN BY THE RECORD'S STATE — `DEF-CUS-6429`.**
            # This served `COMMITTED_BY_NOT_STORED` on every record, and the
            # screen drew one label for it — *"Not committed yet"* — so a DONE
            # sale read *Committed by: Not committed yet*. A sale that has not
            # committed has no committer to store; a sale that has committed
            # had one, and it is this table that does not keep it. Two facts,
            # two absences, and the screen's label follows the record's state.
            # ✅ `DEF-CUS-9692` (customers/0079) — the committer is ON THE ROW
            # since `2.520.2`; a sale committed before that still states *not
            # stored* and never borrows the pruned audit log (hard rule 4).
            "committed_by": _committed_by_fact(row, committed),
        },
        "unchanged": {
            # ⚠ **THE SAME ACCOUNT NUMBER IT HAD BEFORE THE SALE, AND THAT IS
            # THE WHOLE POINT OF THE SECTION.** `BR-CUS-1030` reassigns rather
            # than opening, so this cell and `what_happened.account` are the
            # same string by construction — which is the fact, not a repeat.
            "account_no": _fact(account.account_no),
            "status": _fact(account.status.code if account.status_id else None),
            "ledger_months": _fact(None, LEDGER_SPAN_NOT_COUNTED),
        },
        "money": {
            "currency": _currency(account),
            "balance": _fact(None, SALE_FIGURE_NOT_STORED),
            "deposit": _fact(None, SALE_FIGURE_NOT_STORED),
            "deposit_interest": _fact(None, DEPOSIT_INTEREST_AT_SETTLEMENT),
            # ⛔ THE RULE, NOT A READING. See the block above.
            "refunded": _fact(REFUND_PROHIBITED),
            "recollected": _fact(REFUND_PROHIBITED),
            "fees": _fact(REFUND_PROHIBITED),
            # ⛔ **NOT ADDED UP.** Two absences do not make a total, and doing
            # the arithmetic here would put a money computation on a read.
            "taken_on": _fact(None, SALE_FIGURE_NOT_STORED),
        },
        "doors": {
            "account": _fact({"account_id": str(account.id), "account_no": account.account_no}),
            # The BUYER's door — whose record this is now. A sale that has not
            # committed has no buyer, so the door is an absence rather than a
            # link to nobody (hard-won law 2's mirror: a control that goes
            # nowhere is worse than one that is not drawn).
            "customer": _fact(
                {"customer_id": str(buyer.id), "name": buyer.display_name} if buyer else None,
                NOT_COMMITTED_YET,
            ),
        },
        # Carried for the screen's head chip and for nothing else. NOT a
        # database id (B14 rule 31) — it is the STATE and the step count.
        "step": row.step,
        "step_of": transfers.STEP_COUNT,
        "committed": committed,
    }


def _by_id(key: str) -> Any:
    """The uuid fallback §1 of the durability measurement asks for.

    ⚠ **A WAY IN, NEVER A WAY TO DISPLAY ONE.** A sale made in a tenant
    provisioned before the `transfer` series was seeded carries
    `transfer_no = NULL` and would otherwise be unreadable for ever. The
    payload still serves the server's own stated absence for `reference`, so
    B14 rule 31 holds: no database id is the visible value of a field.
    """
    import uuid as _uuid

    try:
        _uuid.UUID(key)
    except (ValueError, AttributeError, TypeError):
        return None
    return (
        transfers.Transfer.objects.filter(tenant_id=transfers._tenant_id(), pk=key)
        .select_related("from_account", "customer")
        .first()
    )


def _customer(customer_id: Any) -> Any:
    """One `customers` row, or None. Tenant-scoped like every read here."""
    if not customer_id:
        return None
    from apps.customers import models as cmodels

    return cmodels.Customer.objects.filter(tenant_id=transfers._tenant_id(), pk=customer_id).first()


def _identifier_kind(buyer: Any) -> str | None:
    """WHICH government identifier the buyer gave — the kind, never the number.

    ⚠ **`BR-CUS-092` KEEPS THE VALUE APP-LAYER ENCRYPTED**, and a licence
    number drawn on a record page would be a government id rendered to
    everybody who can open a sale. The blueprint draws the KIND for exactly
    that reason and this serves the kind.
    """
    if buyer is None:
        return None
    for column, kind in IDENTIFIER_KINDS:
        if getattr(buyer, column, None):
            return kind
    return None


def _changeover(row: Any) -> dict[str, Any] | None:
    """The meter visit this sale raised: how many, and how many accepted.

    ⚠ **READ THROUGH `seams.flow_work_acceptance` AND NEVER BY IMPORTING
    `apps.work`** (B1 / B2 §2, and `G78` fails a foreign read by name). Zero
    raised is a REAL answer — a clerk who elected no field visit raised none —
    so `{raised: 0, completed: 0}` is served and the screen draws *none* rather
    than *we could not look*. **`None` is the different fact**: Work published
    no tally at all, and a caller that gets it concludes nothing.

    ⚠ **`completed` IS `accepted`, AND THE TWO WORDS ARE NOT THE SAME CLAIM.**
    The seam counts `work_orders.accepted_at` — `BR-MET-110`'s HUMAN act, a
    person reviewing the reading and accepting it — which is a stronger fact
    than a technician marking a visit done, and it is the only one the seam
    publishes. The screen's word is `completed`; the meaning is *accepted*, and
    it is written here so nobody reads this cell as *somebody turned up*.

    ⚠ **`on` IS ALWAYS NULL AND THAT IS NOT AN OVERSIGHT.** The wire shape asks
    when the visit is, and the seam publishes two integers and no date —
    deliberately, per its own docstring: *"only two integers cross it"*. The
    sale raises the job AFTER the commit and is allowed to fail without taking
    the sale down, so there is no appointment for this read to state either.
    """
    # ⚠ **BY THE `TRF-` NUMBER, NEVER THE ROW'S UUID (`DEF-CUS-9629`).**
    # `from_flows._resolve_transfer` stamps `source_ref = transfer_no` on the
    # job, so asking by `row.id` counted *0 raised · 0 done* over a changeover
    # read that was raised, done and accepted. A sale with no number raised
    # nothing that can be found, and reads 0.
    if not getattr(row, "transfer_no", None):
        return {"raised": 0, "completed": 0, "on": None}
    counts = seams.flow_work_acceptance(flow_kind="transfer", source_ref=row.transfer_no)
    if counts is None:
        return None
    return {
        "raised": int(counts.get("total") or 0),
        "completed": int(counts.get("accepted") or 0),
        "on": None,
    }


def _currency(account: Any) -> str | None:
    """ISO 4217, served with the figures (hard rule 2, `CHAR(3)`).

    ⚠ **IT IS SERVED EVEN THOUGH BOTH FIGURES ARE ABSENT TODAY**, because the
    two `BR-CUS-085` prohibitions ARE figures and a `0.00` with no currency
    beside it is a number a screen has to guess the units of.
    """
    statement = transfers._statement_for(account)
    return getattr(statement, "currency", None)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030 W7 task 7.4 (S89 transfers tab — backend half) — B18 §5.7.1 ·
#         §5.7.2 · §5.7.3 · §5.7.5 · §5.7.6 · apps/customers/transfers.py
# generated: 2026-08-25 by lane A-W7 (W7 worklist selectors)
# checklist: A✔ B=deferred(no-frontend-half — S89's rendering is task 7.4's
#         frontend lane) C✔ D=deferred(no API half — `GET /transfers` is
#         REPORTED with its exact handler; api.py is another lane's file)
#         E=deferred F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) `request #` is one of four drawn search legs and the
#         `transfers` table carries no service-request column — served as
#         `SEARCH_REQUEST_NO_UNLINKED`, register row OWED. (2) No story owns
#         S89 (hard-won law 8) — OWED. (3) Cancelled transfers are not listed.
#         (4) The transfer money rule itself does not exist — the cell states
#         four absences and moves nothing (transfers.py §3).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
