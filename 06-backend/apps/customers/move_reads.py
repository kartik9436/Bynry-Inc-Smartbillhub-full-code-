# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (move-in) · US-CUS-005 (move-out).
#           Screens: the Accounts screen's `Move-ins` and `Move-outs` tabs — the
#           LAST TWO of B18 §5.1's eight, and the only two with no read model
#           and no endpoint (measured 2026-08-25, `AccountsListPage.tsx` renders
#           both as `<ArrivesWith>`).
#           ⚠ **NO STORY OWNS EITHER TAB.** US-CUS-004/005 own the two WIZARDS;
#           `04-docs/05-modules/03-customers/06-epics/` carries no epic for the
#           worklists. Hard-won law 8 — the same finding `transfer_reads.py`
#           filed for S89, `disconnect_reads.py` for S90 and `connection_reads`
#           for S86. A story is OWED and is REPORTED rather than invented here.
# Change:   CR-030 W5 — the move-in / move-out worklists, BACKEND half.
# Rules:    BR-CUS-015 (`accounts.balance` is a CACHE — never read here) ·
#           BR-CUS-017 (one occupying account per unit) · BR-CUS-018 (a draft
#           account is never billed, derives no occupancy and does not block the
#           unit — this is the whole move-in window) · BR-CUS-022 (an occupying
#           account without a start date could never be billed, so activation
#           refuses one) · BR-CUS-023 (the deposit is a LOOKUP; every write path
#           is refused) · BR-CUS-024 (deposit carry-forward — mechanics
#           PROPOSED) · BR-CUS-030 (move-out closes the account) · BR-CUS-031
#           (the final bill) · BR-CUS-053 (the search legs) · BR-CUS-054 (the
#           customer entity and `customer_accounts`) · BR-CUS-055 (billing and
#           occupancy key off the behaviour CLASS, never the tenant's label) ·
#           BR-CUS-057 (deposit interest — CONFIRMED, NOT BUILT) · BR-CUS-080
#           (the SR→child link is `outcome_kind` + `outcome_ref`, TEXT) ·
#           BR-MET-036 (occupancy is DERIVED) · BR-SHL-046 (a move-out is SIX
#           steps, not four) · BR-TEN-043 (the event date is an argument, never
#           a wall clock) · CLAUDE.md hard rules 1, 2, 4
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.5 (move-ins —
#           §5.5.1 the five tiles · §5.5.2 the list · §5.5.6 TC-MVI-1..10 ·
#           §5.5.7 the five seed rows) · §5.6 (move-outs — §5.6.1 · §5.6.2 ·
#           §5.6.6 TC-MVO-1..10 · §5.6.7 the six seed rows) · §5.7.3 (the ONE
#           JOB counting contract, which THIS file is the other half of)
# Tests:    06-backend/tests/test_w5_move_worklists.py
# ───────────────────────────────────────────────────────
"""W5 · THE MOVE-IN AND MOVE-OUT WORKLISTS — derivations over `accounts`.

════════════════════════════════════════════════════════════════════════════
0 · THE STRUCTURAL FACT EVERYTHING BELOW IS BUILT ON
════════════════════════════════════════════════════════════════════════════
`apps/customers/sample_data.py` states it in as many words and this module
re-measured it on 2026-08-25:

> **THERE IS NO `move_ins` TABLE AND NO `move_outs` TABLE.** `apps/customers/
> models.py` carries `accounts` · `contacts` · `addresses` · `customers` ·
> `customer_accounts` · `account_opening_buckets` · `account_import_batches`/
> `_rows` · `service_agreements` · `account_notes` · the eight
> `service_request*` tables — and nothing else; no migration under
> `apps/customers/migrations/` names either.

So these two lists are **derivations over `accounts`**, not selects from a
table, and the only question worth asking is *what, in the data, IS a move-in
and what IS a move-out*. Both answers are written down in the product already —
in the copy the two placeholder tabs have been showing users:

  · **Move-ins** — *"listed here **from the day a new occupant is booked in to
    the day their account opens**"* (`customers.accounts.arrives.moveIns`).
  · **Move-outs** — *"listed here **from the closing read to the final bill**"*
    (`customers.accounts.arrives.moveOuts`).

Both are WINDOWS with a stated start and a stated end. §1 and §2 below work out
what opens and closes each one in this schema, and the two answers are not
symmetrical: **one window is fully derivable and the other has no beginning.**

════════════════════════════════════════════════════════════════════════════
1 · A MOVE-IN IS THE LIFE OF A BR-CUS-018 DRAFT — and that is derivable
════════════════════════════════════════════════════════════════════════════
An account row is the only record a move-in has. It is created by
`services.create_account`, whose docstring gives the window's opening edge:

> *"Default status is BR-CUS-018's draft (`pending_activation`): it is never
> billed, derives no occupancy and does not block the unit."*

and `services.activate_account` gives its closing edge:

> *"the resume half of the S18 draft flow (BR-CUS-018): the pending account
> becomes the unit's occupant."*

**That pair IS the placeholder sentence, in code.** *"Booked in"* = a row
exists, holding a unit's name, a start date and a contact, that bills nothing
and blocks nobody. *"Their account opens"* = `activate_account` moves it to an
occupying behaviour class, `_make_occupying` runs BR-CUS-017 and BR-CUS-056
under the unit lock, and BR-MET-036 derives the unit to Occupied.

So:

    MOVE-IN IN PROGRESS  ≡  accounts.status.behavior_class == 'non_billable'
                            AND closed_at IS NULL

⚠⚠ **AND SINCE 2026-09-20 THAT IS ONE OF THREE SOURCES RATHER THAN THE
WINDOW** (`DEF-CUS-5994`; PO, verbatim: *"remove it - it is anyway in the list
so we dont need it sepretely - if it is not in list add it"*):

    A MOVE-IN THIS LIST HOLDS ≡ accounts (the draft window above)
                              ∪ move_in_jobs pending          (`BR-CUS-1077`)
                              ∪ wizard_parks WHERE flow = 'move_in'

**The third arm IS the ruling.** A clerk who opens the move-in wizard and puts
it down leaves a `wizard_parks` row with a real step, and until that day it was
drawn on a PINNED PANEL above this table — `CR-035` amendment 1's shape, chosen
on 2026-08-26 and settled the other way today. §2 below took the same widening
one day earlier for the move-out, so this is that ruling EXTENDED rather than a
second answer designed.

keyed off the CLASS and never off the label, because BR-CUS-055 is explicit
that *"billing keys off the CLASS, never the tenant's label"* and a tenant may
rename `pending_activation` or add one of its own (US-CUS-020 TC-3's *"Legal
hold"*). `selectors.occupying_accounts_for_unit` reads the same class set from
the same two signed rules, from the other side.

**THE FIXTURE CONFIRMS THE DERIVATION RATHER THAN THIS MODULE ASSERTING IT.**
`core/sample_fixture.py`'s `SR-26-0045 · Kwan, Michael` carries
`outcome: "move_in"`, `outcome_ref: "A-12048"` and the comment *"the account it
produced is A-12048, **PENDING ACTIVATION**"* — and B18 §5.5.7 draws that same
`A-12048` as a move-in at `3 of 5`, `Scheduled`. The one drawn move-in row this
tree can resolve to an account is in exactly the state this list selects.

⚠ **THE THREE SUB-STATES ARE DERIVED FROM `opened_at`, AND THE MAPPING IS THIS
LANE'S JUDGMENT — STATED, NOT SMUGGLED.** B18 §5.5.2 draws four state segments
(`Scheduled` · `In progress` · `Waiting` · `Done`). Two of them are facts about
a wizard nobody is holding (§3), so `MOVE_IN_STATES` below serves all four with
`supported` flags and this list computes the two it can plus one more:

    opened_at IS NULL   → `waiting`    — and this is a REAL blockage, not a
                          cosmetic one: `_make_occupying` REFUSES activation
                          without a start date (BR-CUS-022, `BIZ_COMPLETENESS`,
                          *"an occupying account without one could never be
                          billed"*). Nothing about this move-in can move.
    opened_at >  as_of  → `scheduled`  — B18's own word.
    opened_at <= as_of  → `due`        — the start date has arrived and the
                          account has not opened. B18 has no segment for it;
                          `in_progress` would be a claim about a wizard and
                          `scheduled` would hide the one row on the tab that
                          needs a human today. Minted, and declared unsupported
                          -as-drawn in `MOVE_IN_STATES` so no screen mistakes it
                          for a design segment.

════════════════════════════════════════════════════════════════════════════
2 · A MOVE-OUT'S BEGINNING IS IN `wizard_parks`, NOT IN `accounts` (2026-09-19)
════════════════════════════════════════════════════════════════════════════
`services.move_out` does the whole job in one commit:

> *"The occupant leaves: `closed_at` = the move-out date, status → the terminal
> status, every open service agreement ends on the same date, one
> `account.closed` audit row."*

There is **no state before that commit**. `accounts` carries `closed_at` and
nothing else about leaving: no `scheduled_move_out_on`, no move-out state, no
step, no case row — and `_reject_unknown(data, MOVE_OUT_FIELDS)` means the date
cannot even be parked on the account ahead of the close. So:

    MOVE-OUT ON FILE  ≡  accounts.closed_at IS NOT NULL
                         AND status.behavior_class == 'terminal'

and that is a move-out that has **already happened**.

⚠⚠ **AND THIS SECTION'S TITLE WAS WRONG, WHICH IS WHY IT IS KEPT AND CORRECTED
RATHER THAN QUIETLY REWRITTEN (PO ruling 2026-09-19, verbatim: `yes`, asked
whether this list should show move-outs that have not finished yet).** The
sentence above is true of `accounts` and it was read as true of the PRODUCT,
and those are different claims. A move-out DOES have a beginning on file: the
moment a clerk opens the wizard and parks it, `wizard_parks` holds a row with
`flow='move_out'`, a real `step`, the account in `subject_ref` and what the
clerk is waiting for — **since `CR-035`, which is weeks before this file was
written**. `move_record_reads` has served such a row as `in_flight` all along.
**What was missing was this list's WINDOW, not a column**, and a stated absence
nobody re-checked is what kept it missing (law 1: a comment claiming a
guarantee is not the guarantee — and it runs just as badly in reverse).

So the window is two sources now and the list says which each row is:

    A MOVE-OUT THIS LIST HOLDS ≡ accounts.closed_at IS NOT NULL
                                 AND status.behavior_class == 'terminal'
                               ∪ wizard_parks WHERE flow = 'move_out'

⛔ **ONE OF B18 §5.6.7's DRAWN STATES IS STILL UNHOLDABLE, AND ONLY ONE** —
`Scheduled`, a move-out somebody intends and nobody has started. Nothing is
written until the wizard is opened, and `_reject_unknown(data,
MOVE_OUT_FIELDS)` means the date cannot be parked on the account ahead of the
close. `MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE` is narrowed to exactly that, and
`sample_data.py`'s W5 block reached the identical measurement from the seeding
side and wrote `account_notes` rows instead, saying so: *"A NOTE IS NOT A
MOVE-OUT ROW AND THIS BLOCK DOES NOT PRETEND IT IS."*

⚠ **THE STEP CELL NOW HAS TWO ANSWERS AND BOTH ARE RIGHT.** A parked row prints
`2 of 6` off the draft's own column. A CLOSED row prints an absence and must:
**four code paths write `accounts.closed_at` and only one is the wizard** —
`services.move_out`, against the disconnect close-out, the account import and
the import rollback — so `6 of 6` on the other three would claim a clerk walked
six steps they never saw.

⚠ **AND THE WINDOW HAS NO CLOSING EDGE.** *"To the final bill"* would take a
row off this tab, and billing publishes no per-account final-bill total —
`move_out_settlement.GAP_FINAL_BILL`, verbatim: *"billing publishes no
per-account final-bill total … the caller must state it."* So nothing retires a
row and the list grows without bound. `MOVE_OUT_WINDOW_HAS_NO_CLOSING_EDGE`
says so on every response rather than leaving a clerk to notice.

════════════════════════════════════════════════════════════════════════════
3 · THE EXCLUSION CONTRACT — used, never re-implemented (B18 §5.7.3)
════════════════════════════════════════════════════════════════════════════
B18 §5.7.3, verbatim, and it is a callout on the Transfers screen:

> **ONE JOB** — *"A transfer appears only here. Its two halves are deliberately
> kept out of Move-ins and Move-outs — the same job listed three times would be
> counted three times."*

and its own gloss: *"**This is a counting contract between tabs.** … **A test
must assert the exclusion**, because nothing else will catch it."*

**THIS FILE IS THE OTHER HALF OF THAT CONTRACT AND IT IS NOT DECORATION HERE.**
`transfers.commit_transfer` performs its outgoing half *through*
`services.move_out` — the signed BR-CUS-030 path, not a copy — so **every
committed transfer sets a `closed_at` and a terminal status**, and an unfiltered
`move_outs_list` would show all of them. The incoming half goes through
`services.create_account`, so it can land in the draft class the move-in window
selects. Both lists therefore call:

    transfers.exclude_transfer_halves(queryset, field="id")

the published queryset form, resolved through `transfers.EXCLUSION_CONTRACT`.
Nothing here re-derives the set: a second opinion about which accounts are
transfer halves is the drift `tests/test_w7_transfers.py`'s static case exists
to catch, and that case reads THIS file by name.

⚠ **`transfers.py` NAMED ONE LEAK VECTOR AND THIS MODULE IS THE READER IT WAS
ADDRESSED TO:** *"A Move-outs list built by reading `audit_log` for
`account.closed` WOULD therefore pick up a transfer's outgoing half."* This list
is not built that way — it reads `accounts.closed_at` and subtracts the
contract — and the alternative is recorded here so the next lane does not
rediscover it.

════════════════════════════════════════════════════════════════════════════
4 · WHAT IS DRAWN AND CANNOT BE SERVED — every one, with the column it needs
════════════════════════════════════════════════════════════════════════════
| Drawn | Where | Why not | What it would take |
|---|---|---|---|
| ~~`STEP · 6 of 6` / `3 of 6`~~ **✅ SERVED FOR THE DRAFTS 2026-09-20** | §5.5.2 · §5.6.2 | **CLOSED for the rows that HAVE a step** (`DEF-CUS-5994`, PO: *"if it is not in list add it"*). A parked draft is a `wizard_parks` row with a real `step` and it is a ROW OF THIS LIST now, on BOTH tabs, bar filled in. ⚠ The absence STANDS on the account, job and closed rows and must: none of them records how far anybody walked. **This row has been rewritten three times in two days and each version was true when written** — *"no wizard store"* (false since `CR-035`), then *"it lives on the panel above this table"* (true for one day) | — closed for drafts; a case table is what the OTHER rows would still need, and §5.5.2's own footnote rules one out for the move-in |
| `estimated` (amber) | §5.6.2 | ✅ **SERVED since 2026-08-26 (CR-038 W9 task 4)** — `accounts.final_read_state` stores HOW the settlement's final read was obtained, derived once at close (`services.move_out`), and the FINAL READ cell says `estimated` off that flag. What stays stated: a close predating the column carries NULL and `final_read_state_not_recorded` rides beside the derived `taken`/`due` | — closed (was: the how-obtained flag TC-MVO-7 asserted missing) |
| `DEPOSIT` sentence | §5.5.2 | `waived` / `on first bill` / `carried` / `collected` is a DISPOSITION and no column records which; `deposit_on_file` holds an AMOUNT and is a REFUSED field on every account door (BR-CUS-023) | a disposition column, or the deposit schedule US-CUS-007 names |
| `DEPOSITS TO CARRY OVER` tile | §5.5.1 | it counts an ELECTION and `accounts` has none. `transfers.deposit_carry_elected` is exactly that column, on the transfer table | the same boolean on the move-in's record |
| `SHORTFALLS TO DECIDE` · `REFUNDS TO PAY` | §5.6.1 | both need a LANDING and a landing needs the final bill (§2) | `BR-CUS-031` / `US-BIL-011`'s per-account final-bill total |
| `Scheduled` move-out, nobody has started one | §5.6.2 · §5.6.7 | §2 — nothing is written until a clerk opens the wizard, and `accounts` has no `scheduled_move_out_on` to park a date on | `accounts.scheduled_move_out_on` + a state |
| ~~`In progress` / `Waiting` move-outs~~ **✅ SERVED 2026-09-19** | §5.6.2 · §5.6.7 | **CLOSED by PO ruling (`yes`)** — the row below predicted the fix and named it exactly: this list's window is widened to `wizard_parks` where `flow='move_out'`, the `BR-CUS-1077` shape. p117's `MVO-26-0087 · 2 of 6 · In progress` is REAL data now | — closed |
| ~~(the original row, kept for its reasoning)~~ | §5.6.2 · §5.6.7 | §2 — no state exists before the close **on `accounts`**. ⚠ **AND THE ACCOUNTS BLUEPRINT p117 (the 281-page edition, 2026-09-19) DRAWS ONLY TWO WORDS HERE — `Completed` and `In progress` — NOT B18's four.** `Completed` is this list's `closed` under the record page's own vocabulary (`move_record_reads.STATE_COMPLETED`); `In progress` is `move_record_reads.STATE_IN_FLIGHT`, which that page ALREADY serves off a `wizard_parks` row. So the missing half is a WINDOW, not a column | `accounts.scheduled_move_out_on` + a state for a move-out nobody parked, or this list's window widened to `wizard_parks` where `flow='move_out'` — the shape `BR-CUS-1077` already gave the Move-ins tab for pending jobs |
| `Done` move-ins | §5.5.2 · §5.6.7 | the window CLOSES when the account opens, and no rule sets a retention window for a finished one | a ruling on how long a completed move-in stays on the tab |
| `— draft` rows | §5.5.2 | a draft with no account is a `service_requests` row and cannot appear on a list built over `accounts` | nothing — §5.5.7's own `draft_has_no_account` says the request IS the draft |
| `request #` search, MOVE-OUTS only | §5.6.2 | a move-out creates no child, so `link_child` writes no `outcome_ref` — `SR-26-0046 · Thompson` carries `outcome_ref: None` | `outcome_ref` = the closing account's number, as the move-in side already does |

⚠ **`READS` / `FINAL READ` (`taken`/`due`) LEFT THIS TABLE ON 2026-08-26** —
CR-038 W9 task 2 published `apps.metering.selectors.reads_for_unit` and
`seams.reads_for_unit` resolves it, exactly the seam the old row asked for. Both
cells and the `FINAL READS DUE` tile now DERIVE their state (`unit_reads_cell`):
taken = a committed head exists at/after the row's own event date for EVERY
meter on the unit; due = not. ⚠ **AND `estimated` FOLLOWED ON THE SAME DAY
(W9 task 4)** — served off the settlement's own stored flag
(`accounts.final_read_state`), see the retired row above. What stays stated:
the unresolved-seam deployment (`READS_NOT_READABLE`, same code the tabs
speak), the meterless unit (`UNIT_HAS_NO_METERS`), the dateless move-in
(`READS_STATE_NEEDS_A_START_DATE`) and the unflagged close
(`FINAL_READ_STATE_NOT_RECORDED`). The screen half — DEF-786's ticket — is
the W9 frontend-adoption commit in this same lane: the tabs render
taken/due/estimated with the real counts and the tile's real number.

**The move-in `request #` leg IS served**, and it is the one `transfer_reads`
had to give up (BR-CUS-099 ruled it away there). It works here for a reason
worth stating: BR-CUS-080's link is TEXT, and the fixture writes the ACCOUNT
NUMBER into it — `SR-26-0045 → outcome_ref: "A-12048"`. So a request number
resolves to an account number and back. It is best-effort by construction and
`SEARCH_REQUEST_LEG_IS_BEST_EFFORT` says so: nothing constrains `outcome_ref`
to an account number (`tests/test_cr031_service_request.py` writes
`"MVI-26-0001"` into it), so the leg finds the rows that were linked that way
and silently finds nothing for the rest.

════════════════════════════════════════════════════════════════════════════
5 · WHAT THIS FILE DOES NOT DO
════════════════════════════════════════════════════════════════════════════
· **No API route.** `apps/customers/api.py` is another lane's file. The two
  exact handlers are REPORTED for the merging session, and until they are
  mounted these lists are built and not wired (hard-won law 2).
· **No money moves and no money is decided.** Both lists are READS: no
  `audit_log` row, because nothing happened (hard rule 7 is about ACTIONS).
· **`accounts.balance` IS NEVER READ.** DEF-127: it is a cache nothing writes,
  and serving it once told a customer owing $108.88 that they owed nothing. The
  outstanding figure comes from the LEDGER through `seams.ar_positions`, asked
  once per page, and its absence is reported rather than answered `0.00`.
· **No settlement VERDICT is computed per row.** §6 below.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import DateField, F, Q, TextField, Value

from apps.customers import models, move_out_settlement, moves, seams, services, transfers
from core import pagination

# ── the list envelope (11b G5: pagination is mandatory on every list) ───────
#: ONE page-size default for the product — `core.pagination`'s, so a direct
#: caller and a request through `parse_list_params` slice the same page.
DEFAULT_PER = pagination.DEFAULT_PAGE_SIZE
MAX_PER = pagination.PAGE_SIZES[-1]

#: §5.5.1 / §5.6.1's caption, verbatim: *"within 7 days of today"*.
WEEK_DAYS = 7

#: B18 §5.5.2's columns, in the drawn order. Served as DATA so the screen and
#: this payload cannot disagree about which cells exist.
MOVE_IN_COLUMNS: tuple[str, ...] = (
    # ⚠ **`reference` LEADS AND §5.5.2 DOES NOT DRAW IT — CR-039 wave D tasks
    # 17–19, 2026-08-27**, the same divergence `disconnect_reads.COLUMNS` and
    # S89 carry and stamped here for the same reason. The CR's finding 5 named
    # move-in and move-out as the two flows with **no record at all**; the PO
    # ruled *"you cna keep them as records for audit perpuses"* and this is the
    # cell that makes one quotable.
    "reference",
    "account",
    "customer",
    "unit",
    "move_in_date",
    "step",
    "reads",
    "deposit",
    "state",
)

#: B18 §5.6.2's columns, in the drawn order.
MOVE_OUT_COLUMNS: tuple[str, ...] = (
    "reference",  # as MOVE_IN_COLUMNS above — §5.6.2's eight follow it unchanged
    "account",
    "customer",
    "unit",
    "move_out_date",
    "step",
    "final_read",
    "settlement",
    "state",
)

# ═══════════════════════════════════════════════════════════════════════════
# CR-039 WAVE D 17–19 — THE REFERENCE CELL, AND ITS THIRD ABSENCE
# ═══════════════════════════════════════════════════════════════════════════
#: ⛔ A move row can have no reference for THREE distinct reasons, and merging
#: any two of them into one dash is DEF-127's shape (*"looks exactly like a
#: settled account"*). S90 already carries two; this list carries three:
#:
#:   1. **no record** — the job predates 2026-08-27, when `move_records` did not
#:      exist. Nothing is missing from the tenant's setup and nothing is broken;
#:      the job simply happened before the product kept a record of one.
#:   2. **a record with no number** — a host whose tenant has no `move_in` /
#:      `move_out` series row yet (`_seed_number_series` is `get_or_create`; the
#:      repair door is `manage.py seed_demo --tenant <subdomain>`). This one IS
#:      a settings gap and says so, from `moves.MOVE_NUMBER_UNAVAILABLE`.
#:   3. **a move-in that is still a DRAFT** — §5.5's whole list is the BR-CUS-018
#:      draft window, and a draft account has not been through `move_in` at all,
#:      so no job has happened yet to leave a record of.
#:
#: ⚠ **(3) IS WHY THE MOVE-INS TAB SHOWS AN EMPTY REFERENCE ON EVERY ROW TODAY,
#: AND THAT IS CORRECT RATHER THAN A GAP.** This tab lists drafts — *"a row
#: LEAVES this list when the move-in completes"* (`MoveInsTab`'s own §1) — and a
#: record is written by `services.move_in` at completion. So the column is
#: populated on the Move-OUTS tab and stated-absent on the Move-INS tab, and
#: **that asymmetry is a fact about what each list contains**, not an oversight.
#: It is REPORTED here rather than hidden by dropping the column: a reader who
#: can see the cell can ask why it is empty, and a reader who cannot, cannot.
MOVE_JOB_PREDATES_THE_RECORD: dict[str, Any] = {
    "code": "move_predates_the_record",
    "br_ref": "BR-CUS-150",
    "detail": (
        "This move happened before the product kept a record of one. Move-ins and move-outs "
        "have left a numbered record since 27 August 2026; jobs completed before then were "
        "never written down, and nothing is missing from this utility's setup."
    ),
}

#: ⚠ **NARROWED 2026-09-22 (`BR-CUS-1090`, `CR-133-BRC07`), AND ITS OLD
#: SENTENCE IS THE THING THAT CHANGE ACTUALLY REVERSED.** It read *"The record
#: and its number are written when the account opens — which is also when the
#: row leaves this list."* **That stopped being true in two steps, neither of
#: them this one**: `CR-122-BRC06` gave a PARKED move-in wizard a number from
#: this same series on 2026-09-20, and `BR-CUS-1090` gives an APPROVED move-in
#: one at the moment the clerk presses. A number no longer waits for anything.
#:
#: **SO WHO IS LEFT TO SERVE IT?** A move-in that nobody approved through a
#: service request and nobody has opened a wizard for — an ordinary BR-CUS-018
#: draft account, created through S18 — plus any job or draft on a tenant with
#: no `move_in` series row, which reads `MOVE_NUMBER_UNAVAILABLE` instead and
#: says a different thing. The sentence below names that row and no other.
MOVE_IN_IS_STILL_A_DRAFT: dict[str, Any] = {
    "code": "move_in_not_completed",
    "br_ref": "BR-CUS-018 · BR-CUS-150 · BR-CUS-1090",
    "detail": (
        "No number has been issued for this move-in. One is issued when a service request is "
        "approved, or when somebody opens the move-in wizard, and neither has happened here — "
        "so the reference appears with whichever comes first."
    ),
}


#: ⛔ **A JOB RAISED BEFORE `customers/0064`, WHICH IS A DIFFERENT FACT FROM A
#: TENANT WITH NO SERIES — AND SERVING THE WRONG ONE SENDS A CLERK TO SETTINGS
#: FOR NOTHING.** `moves.MOVE_NUMBER_UNAVAILABLE['move_in']` says *"A number
#: series for move-ins has not been set up"*, which is TRUE of an unconfigured
#: tenant and FALSE of every job `BR-CUS-1077` raised between 2026-09-16 and
#: 2026-09-22: those tenants have a series, the jobs simply predate the column
#: and the migration refuses to back-fill them (`customers/0064` §1). A clerk
#: reading the wrong sentence goes to Settings → Numbering, finds the format
#: perfectly configured, and learns that the product is lying to them.
#:
#: **It is `MOVE_JOB_PREDATES_THE_RECORD`'s shape one table over**, and it is the
#: third way a move-in reference can be absent for a reason that is nobody's
#: fault.
#:
#: ⚠ **THE TEST IS A DATE AND IS STATED AS AN APPROXIMATION** — `_fact`'s own
#: posture in `move_record_reads`, where `CLOSE_REASON_COLUMN_SHIPPED` does the
#: same job for the same reason. **Nothing on the row records whether the column
#: existed when it was written**; that is exactly the fact a column added after
#: the data cannot carry. A job raised on the day itself could fall either side,
#: and the cost of being one sentence too generous on a handful of rows is far
#: below the cost of sending a clerk to a settings screen that is already right.
MOVE_IN_JOB_NUMBER_COLUMN_SHIPPED = date(2026, 9, 22)

MOVE_IN_JOB_PREDATES_ITS_NUMBER: dict[str, Any] = {
    "code": "move_in_job_predates_its_number",
    "br_ref": "BR-CUS-1077 · BR-CUS-1090",
    "detail": (
        "This move-in was approved before the product gave an approved move-in a reference of "
        "its own, so it has none and nothing will issue one. Nothing is missing from this "
        "utility's setup, and every move-in approved since carries a number from the moment "
        "the clerk presses."
    ),
}


def move_in_job_reference(job: Any) -> dict[str, Any]:
    """The `reference` cell for one pending move-in job — `BR-CUS-1090`.

    ⚠ **A NAMED FUNCTION, DELIBERATELY, AND FOR `move_reference_cell`'s OWN
    REASON ONE SCREEN OVER:** a cell with more than one way of being empty is a
    cell whose absences get merged into a single dash the first time somebody
    inlines it (`DEF-127`, and `disconnect_reads.case_reference_absence`'s note).

    Three arms, and the two absent ones are DIFFERENT FACTS a clerk acts on
    differently: a tenant with no `move_in` series row goes to Settings, and a
    job raised before `customers/0064` does nothing at all because nothing is
    wrong.
    """
    if job.move_no:
        return {"move_no": job.move_no, "move_no_unavailable": None}
    raised = getattr(job, "created_at", None)
    predates = raised is not None and raised.date() < MOVE_IN_JOB_NUMBER_COLUMN_SHIPPED
    return {
        "move_no": None,
        "move_no_unavailable": dict(
            MOVE_IN_JOB_PREDATES_ITS_NUMBER
            if predates
            else moves.MOVE_NUMBER_UNAVAILABLE[moves.KIND_MOVE_IN]
        ),
    }


def move_records_by_account(account_ids: list[Any], *, kind: str) -> dict[str, Any]:
    """One query for a whole page's move records — never one per row.

    The `ar_positions` discipline, stated in `move_outs_list`'s own docstring:
    *"a per-row seam call is a query per row on the product's busiest screen"*.
    This is not a seam (it is customers' own table) and the reason still holds.

    Keyed by the account the job ACTED ON. A chained move-in also names the
    OUTGOING account in `from_account`, and that link is deliberately NOT keyed
    here: on the Move-outs tab the outgoing account's own move-out record is the
    row's reference, and keying the successor's arrival under it as well would
    put two different numbers in one cell.
    """
    rows = moves.MoveRecord.objects.filter(
        tenant_id=_tenant_id(), kind=kind, account_id__in=list(account_ids)
    ).order_by("-performed_at", "-created_at")
    out: dict[str, Any] = {}
    for row in rows:
        # BR-CUS-152 — a correction is a NEW row, so an account can hold more
        # than one record of a kind. The NEWEST is the current statement of the
        # job, and the earlier ones stay on file; `-performed_at` above is what
        # makes `setdefault` mean "newest".
        out.setdefault(str(row.account_id), moves.serialize(row))
    return out


def account_ids_for_move_reference(term: str, *, kind: str) -> list[str]:
    """`DEF-CUS-5896` — the accounts whose move REFERENCE matches a search term.

    The reference is the first column of both move lists and the only thing on
    either row that a person says out loud, and until 2026-09-19 neither search
    box could answer it: a clerk reading `MVO-26-0088` off the row, off a letter
    or off the phone typed it back in and got **nothing**. Measured on the
    seeded `brazosbend` tenant before the leg existed — `move_outs_list(q=
    "MVO-26-0001")` returned **0 rows** over the very row printing that number,
    while `move_outs_list(q="AC-2026-00042")` returned **1**.

    ⚠ **TENANT-SCOPED ON `move_records` ITSELF, not only on the rows it feeds**
    (CLAUDE.md hard rule 1). This is the same predicate `move_records_by_account`
    has always used — `tenant_id=_tenant_id()`, under RLS `FORCE` — so a
    reference belonging to another utility resolves to no account here. The
    account window this feeds is tenant-scoped too, which makes the leak
    unobservable in the rows; the rule is about the QUERYSET, so it is filtered
    where it is built and not left to the layer above.

    ⚠ **`kind` IS NOT OPTIONAL AND IS NOT TIDINESS.** An account that moved in
    and later moved out carries a record of BOTH kinds. Without the filter, a
    clerk typing a move-IN number would put that account's move-OUT row on
    screen under a reference the row does not print — a match they cannot
    account for, which is worse than no match.

    ⚠ **A CORRECTION IS A NEW ROW (BR-CUS-152), SO AN ACCOUNT CAN HAVE SEVERAL
    REFERENCES OF ONE KIND, AND EVERY ONE OF THEM FINDS IT.** The cell prints
    the NEWEST (`move_records_by_account` picks it); a clerk quoting a
    superseded number is quoting a number this product issued, and finding the
    row is the right answer. The row then shows the current reference, which is
    the correction being visible rather than a mismatch.

    `icontains`, the same shape as every other leg on these boxes, so a partial
    (`26-0088`) answers. Returns account ids as strings; an empty list means the
    leg matched nothing and the caller adds no `Q` at all.
    """
    if not term:
        return []
    return [
        str(account_id)
        for account_id in moves.MoveRecord.objects.filter(
            tenant_id=_tenant_id(), kind=kind, move_no__icontains=term
        ).values_list("account_id", flat=True)
    ]


def move_reference_cell(record: dict[str, Any] | None, *, drafted: bool = False) -> dict[str, Any]:
    """The `reference` cell for one move row — the number, or WHICH absence.

    Returns `{"move_no", "move_no_unavailable"}`, exactly the pair `transfers`
    and `disconnects` serve, so the ONE frontend cell (`RecordNumberCell`) reads
    all four flows without learning a fourth shape.

    ⚠ **A NAMED FUNCTION, DELIBERATELY, AND THAT IS DEF-182's LESSON APPLIED
    BEFORE IT BITES.** `disconnect_reads.case_reference_absence` was inline in
    its row builder, and the test written to hold its two absences apart read
    the two CONSTANTS rather than the branch — so collapsing both arms onto one
    of them left the test GREEN. Three arms is a stronger version of the same
    trap, so the decision is reachable by a test from the day it lands.
    """
    if record is not None:
        return {
            "move_no": record["move_no"],
            "move_no_unavailable": record["move_no_unavailable"],
        }
    return {
        "move_no": None,
        "move_no_unavailable": dict(
            MOVE_IN_IS_STILL_A_DRAFT if drafted else MOVE_JOB_PREDATES_THE_RECORD
        ),
    }


#: §5.5.2's search box, verbatim.
MOVE_IN_SEARCH_HINT = "Customer, unit, address, account #, or request #…"

#: ⚠ `BR-CUS-1077` — what a PENDING JOB's half of the search can answer, so a
#: clerk who types an account number and misses the job rows knows why. A row
#: with no account cannot be found by account number, and offering the leg
#: anyway is `BR-CUS-099`'s complaint about the transfers box.
PENDING_JOB_SEARCH_LEGS_ARE_NARROWER: dict[str, Any] = {
    "code": "pending_job_has_no_account_number_to_search",
    "br_ref": "BR-CUS-1077",
    "detail": (
        "The `account #` leg finds draft accounts only. A move-in nobody has started has no "
        "account number yet, so those rows answer to the applicant's name, the request number "
        "and the unit or address the application resolved to."
    ),
}

#: §5.6.2's search box, MINUS the leg the data cannot answer — see §4. The
#: `request #` leg is not offered here because a move-out creates no child and
#: `outcome_ref` is NULL on every move-out request in this tree; offering it
#: would be a box that silently finds nothing, which is BR-CUS-099's own
#: complaint about the transfers box in the other direction.
#:
#: ⚠ **`Reference` LEADS SINCE 2026-09-19 (`DEF-CUS-5896`, PO-approved).** It
#: read *"Customer, account #, unit, or address…"* while `reference` was the
#: FIRST COLUMN of this table — the one number a clerk reads off a row, a
#: letter or the phone and types straight back in — and the box answered
#: nothing at all for it. The Accounts blueprint p117 draws the prompt as
#: *"Search by reference, account, customer or unit"*; this keeps our own
#: wording and our own fifth leg (`address`, which the drawing's label omits
#: and the predicate has always had) and puts the reference at the front.
#:
#: ⚠ **THE FRONT END DOES NOT READ THIS STRING** — `MoveOutsTab.tsx` renders
#: the catalogue key `customers.moveOuts.list.searchPlaceholder` in eleven
#: languages, whose English is a copy of this constant. Changing one does NOT
#: change the other, which is exactly how the two came to disagree with the
#: column above them; the catalogue half is reported in DEF-CUS-5896.
MOVE_OUT_SEARCH_HINT = "Reference, customer, account #, unit, or address…"

#: ⚠ **FOUR SINCE 2026-09-24, AND THE SUPERSESSION IS NAMED RATHER THAN
#: ASSUMED.** `BR-SHL-046` (PO 2026-08-24, closing `DEF-648`, verbatim
#: *"6 steps"*) made this SIX, and B18 §5.6.2's `STEP (of 4)` and §5.6.7's
#: `4 of 4` were superseded by it. The PO has now ruled the move-out's shape
#: **FOUR** — *"i okay with these steps"* — so **the NUMBER in BR-SHL-046 moves
#: and its MECHANISM does not**: both bars are still driven by ONE declared
#: step list, which is the durable half the rule itself names.
#:
#: ⚠ **THE OLD `4` AND THIS `4` ARE NOT THE SAME FOUR, WHICH IS WHY THE CHAIN
#: IS WRITTEN OUT HERE.** B18's four was a DRAWN count that never matched the
#: wizard and was the defect `DEF-648` closed. This four is the wizard's own
#: declared list — `account · date · settlement · review` — after old steps 3+4
#: and 5+6 were merged. A lane that reads only *"it went back to 4"* will
#: reopen a closed defect.
#:
#: Carried as a constant so a screen cannot reintroduce a denominator of its
#: own, even though the NUMERATOR has no store (§4).
#: `tests/test_def_648_step_count_parity.py` holds this against
#: `moveShared.MOVE_OUT_STEPS`, in the other language, so the two cannot
#: disagree without going red.
MOVE_OUT_STEP_COUNT = 4

#: ⚠ **SIX, NOT FIVE — CORRECTED 2026-09-19 (`DEF-CUS-5886`).** This read `5`
#: from CR-030 step 2, citing §5.5.3's five steps. The wizard a clerk actually
#: walks has held SIX since BR-SHL-046: `moveShared.MOVE_IN_STEPS` is
#: `unit · customer · start · preferences · deposit · review`, and
#: `MoveInWizard.tsx` draws `Step 1 of 6` off that same list. So the Move-ins
#: list drew a FIVE-segment bar and served `of: 5` under a six-step wizard, and
#: the Accounts blueprint draws `6 of 6` and `3 of 6` — **p077 of the 281-page
#: edition**, which was p073 in the 242-page one the PO replaced on 2026-09-19.
#:
#: ⚠ **NOTHING IN THIS REPO COULD HAVE CAUGHT IT, WHICH IS WHY IT IS WRITTEN
#: OUT.** The NUMERATOR has no store (§4), so the cell never printed `4 of 5`
#: for anybody to compare against the wizard's `4 of 6` — the denominator stood
#: alone inside a cell whose own copy says the step is not recorded, and a wrong
#: number beside a stated absence reads as part of the absence. The two halves
#: live in two languages with no shared source, so `tsc`, every suite and every
#: gate are green either way. `MOVE_OUT_STEP_COUNT` above was corrected the same
#: way in August, from a drawn `4`; this is that precedent applied to the other
#: tab rather than a new kind of mistake.
#:
#: ⚠⚠ **FOUR SINCE 2026-10-05 (`CR-171-BRC10` P1.02, `DEF-CUS-9703`), AND THE
#: COUNT IS NOW DERIVED FROM A DECLARED LIST RATHER THAN TYPED.** The PO ruled
#: the move-in redesign's wizard *Unit · Customer · Billing · Review* (mock-up
#: v2/v4, images 30–47 — CR §2 S5). `DEF-CUS-9703` was this constant reading
#: `6` while the wizard read `of 7`: a typed number beside a declared list is
#: the second copy BR-SHL-046 forbids, so the IDS are declared here and the
#: count is their length. `MOVE_IN_STEP_NAMES` is what a list cell prints after
#: the number (image 01: *"3 of 4 · Billing"*); a screen translates the id.
#: ⚠ **THE FRONT END'S `moveShared.MOVE_IN_STEPS` STILL HOLDS SEVEN TODAY, ON
#: PURPOSE** — that constant also drives the live seven-body wizard's step line
#: and its resume, so it flips in the SAME commit as the four-step wizard
#: (`CR-171` P2.15, lane WIZ). `tests/test_def_648_step_count_parity.py`
#: carries a STRICT xfail on that half, which goes red the day it flips.
MOVE_IN_STEP_IDS: tuple[str, ...] = ("unit", "customer", "billing", "review")
MOVE_IN_STEP_NAMES: dict[str, str] = {
    "unit": "Unit",
    "customer": "Customer",
    "billing": "Billing",
    "review": "Review",
}
MOVE_IN_STEP_COUNT = len(MOVE_IN_STEP_IDS)

#: ⚠ **A DRAFT PARKED UNDER THE SEVEN-STEP WIZARD, READ IN THE FOUR-STEP ONE
#: (`CR-171-BRC10` P1.03, CR §4).** The CR's own map: old 1–2 (Find unit ·
#: Which services) → Unit, 3 (Customer) → Customer, 4 (Start date & reads) →
#: **Unit** — the date, the reads and the visit live on step 1 now (images
#: 30–32) —, 5–6 (Preferences · Deposit) → Billing, 7 (Review) → Review.
#: ⚠ **THE MAP IS NOT IDEMPOTENT, SO IT IS APPLIED ONLY TO A SEVEN-STEP DRAFT.**
#: New-connect's `NEW_CONNECT_STORED_STEP` could be applied to every stored
#: number because it is the identity on 1–3; this one is not (a four-step
#: draft at 2 · Customer would map to 1 · Unit). So a park says which shape
#: wrote it: `values.step_shape == "four"` (the four-step form writes it), or
#: a `subject_ref.service_request_id` — the request's Edit door
#: (`move_in_request.save_form`, P1.08) is the only writer that puts the link
#: there, and it has only ever written the four-step shape. Anything else is
#: a seven-step draft. **No value is touched**: the four-step form reads the
#: seven-step keys (`unit_id`, `opened_at`, `customer`, `preferences`,
#: `deposit`, `reads`, `discount`, `services`, `field_visit`,
#: `service_request_id` — CR §9.REQ), so only the STEP moves.
MOVE_IN_STEP_SHAPE_KEY = "step_shape"
MOVE_IN_STEP_SHAPE_FOUR = "four"
MOVE_IN_SEVEN_STEP_TO_FOUR: dict[int, int] = {1: 1, 2: 1, 3: 2, 4: 1, 5: 3, 6: 3, 7: 4}


def move_in_park_is_four_step(park: Any) -> bool:
    """Was this `move_in` draft written by the four-step form? See above."""
    values = park.values if isinstance(getattr(park, "values", None), dict) else {}
    subject = park.subject_ref if isinstance(getattr(park, "subject_ref", None), dict) else {}
    if values.get(MOVE_IN_STEP_SHAPE_KEY) == MOVE_IN_STEP_SHAPE_FOUR:
        return True
    return bool(subject.get("service_request_id"))


def move_in_park_step(park: Any) -> int:
    """The draft's step in the FOUR-step shape, clamped into `[1, 4]`.

    A seven-step number goes through the map; a four-step one is taken as it
    is; anything out of range is clamped (BR-SHL-011), never refused — a
    corrupted step must not make a clerk's draft unopenable.
    """
    raw = int(getattr(park, "step", 1) or 1)
    if move_in_park_is_four_step(park):
        step = raw
    else:
        step = MOVE_IN_SEVEN_STEP_TO_FOUR.get(raw, raw)
    return max(1, min(step, MOVE_IN_STEP_COUNT))


def move_in_step_cell(
    reached: int | None, *, unavailable: dict[str, Any] | None = None
) -> dict[str, Any]:
    """`{"reached", "of", "id", "name", "unavailable"}` — one shape for every row
    kind and for the record page, so *"3 of 4 · Billing"* is said one way."""
    step_id = MOVE_IN_STEP_IDS[reached - 1] if reached else None
    return {
        "reached": reached,
        "of": MOVE_IN_STEP_COUNT,
        "id": step_id,
        "name": MOVE_IN_STEP_NAMES.get(step_id) if step_id else None,
        "unavailable": unavailable,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE STATED ABSENCES — every one names the column or seam it would take
# ═══════════════════════════════════════════════════════════════════════════
#: ⛔ §4 row 1. The same measurement `sample_data.py` made from the seeding side.
#:
#: ⚠ **STILL EXACTLY TRUE AFTER `move_records` LANDED ON 2026-08-27, AND THE
#: RECIPROCAL POINTER IS HERE SO NOBODY HAS TO GUESS.** CR-039 wave D task 18
#: built a record for a move-in and a move-out, and it is a record of a
#: **COMPLETED** job — no `step`, no `state`, no row while the wizard is open.
#: What this absence asks for is what it says: *"a move-in/move-out case row
#: carrying step + state"*, which is a different thing, and B18 §5.5.2's own
#: footnote rules it out for the move-in. **So this is NOT closed by that
#: table**, and the sentence below is left word for word rather than softened.
#: `apps/customers/moves.MoveRecord`'s docstring says the same from its side.
#:
#: ⚠⚠ **THE SENTENCE BELOW SAID *"no wizard store"* UNTIL 2026-09-19, AND THAT
#: CLAUSE WAS FALSE (`DEF-CUS-5888`).** `wizard_parks` has existed since
#: `CR-035` step 6 and carries `flow`, `step`, `values`, `waiting_on`,
#: `park_note`, `remind_on` and `parked_at` — a `step` column, on the very
#: object this absence says has none. The running product proves it: the
#: Move-ins tab's own parked panel renders `Step 1 of 6` off that row.
#:
#: **THE ABSENCE ITSELF STANDS, AND ONLY THE REASON CHANGED**, which is the
#: distinction worth keeping. A park is a DRAFT a clerk chose to put down; it is
#: not an account and it is not a row of this list. The rows here are draft
#: ACCOUNTS and approved PENDING JOBS, and neither carries a step, so
#: `reached` is still `None` on every one of them — measured over all eight rows
#: of the seeded tenant on 2026-09-19. What would close it is unchanged and
#: still named in `wanted_columns`.
#:
#: This is the third time in four days a docstring in this module asserted an
#: absence that had been closed months earlier (`initial_reads`, `Park`, and now
#: this), so: **check the running product before believing a sentence about what
#: is missing** — including this one.
#: ⚠⚠ **AND ITS SECOND CLAUSE WAS TRUE FOR EXACTLY ONE DAY — AMENDED 2026-09-20
#: (`DEF-CUS-5994`).** On 2026-09-19 this note read *"THIS IS THE MOVE-INS TAB'S
#: SENTENCE, AND IT STAYS EXACTLY AS IT IS … a parked move-in is a panel row
#: above the table and not a row in it"*, and the `detail` below said the same
#: to a clerk. **The PO removed the panel the next day** — verbatim: *"remove it
#: - it is anyway in the list so we dont need it sepretely - if it is not in
#: list add it"* — so a sentence sending a reader to a panel now points at
#: nothing at all.
#:
#: ⚠ **THIS IS THE THIRD CORRECTION TO ONE CONSTANT IN TWO DAYS**, and the shape
#: is worth more than the fix: each version was TRUE when written and each was
#: falsified by a ruling rather than by a bug. A stated absence is a claim with
#: a clock in it (hard-won law 2's mirror), and **the clause that rots is always
#: the one naming ANOTHER SURFACE** — *"no wizard store"*, then *"the panel
#: above this table"*. So what is left names no surface at all: it says which
#: ROWS carry no step and why, and a reader who wants to know where a step IS
#: reads a row that has one.
#:
#: ⛔ **NEITHER PARKED ROW USES IT.** A parked move-in and a parked move-out are
#: rows of their own lists now, each with a real `step.reached` off
#: `wizard_parks.step`. This rides on the ACCOUNT and JOB rows, which genuinely
#: carry none; a CLOSED move-out has its own, different reason and
#: `CLOSED_MOVE_OUT_HAS_NO_STEP` carries it. **Two different facts get two
#: constants rather than one sentence stretched over both** — which is the
#: `MOVE_IN_DRAFT_HAS_NO_ACCOUNT` / `MOVE_IN_UNAPPROVED_DRAFT...` split, taken
#: for the same reason.
STEP_HAS_NO_STORE: dict[str, Any] = {
    "code": "move_step_has_no_store",
    "br_ref": "BR-CUS-018 · BR-SHL-046",
    "detail": (
        "B18 draws a STEP cell over a segmented bar, and this row has no step to put in it: "
        "it is a draft account or an approved job, and neither records how far anybody got. "
        "A half-finished wizard somebody put down IS recorded with a real step, and it is a "
        "row of this same list with its own bar filled in. Closing this would take a case "
        "table for the job — which B18 §5.5.2's own footnote rules out for the move-in "
        "(*\"a move-in is short enough that the wizard is the record\"*)."
    ),
    "wanted_columns": ("<a move-in/move-out case row carrying step + state>",),
}

#: ⛔ **WHY A FINISHED MOVE-OUT HAS NO STEP, WHICH IS NOT THE SAME FACT AS THE
#: ONE ABOVE** (PO ruling 2026-09-19 — the unfinished move-outs are rows now).
#:
#: An UNFINISHED move-out on that tab prints `2 of 6` off its own draft. A
#: CLOSED one cannot, and the reason is the close rather than the list: **four
#: code paths write `accounts.closed_at` and only one is the wizard** —
#: `services.move_out`, against the disconnect close-out (`close_out.py`), the
#: account import and the import rollback. Two of those three never showed a
#: clerk a step at all, so a full bar would state something that did not happen.
#:
#: ⚠ **IT IS A CLOSE-TIME COLUMN THAT WOULD FIX IT, NOT A LIST CHANGE**, which
#: is why `wanted_columns` names one rather than a case table.
CLOSED_MOVE_OUT_HAS_NO_STEP: dict[str, Any] = {
    "code": "closed_move_out_has_no_step",
    "br_ref": "BR-CUS-030 · BR-SHL-046",
    "detail": (
        "This move-out is finished, and how many steps somebody walked to finish it was not "
        "written down. An account can be closed four different ways and only one of them is "
        "the move-out wizard, so a full bar here would say a clerk went through six steps "
        "they may never have seen. A move-out still in progress does show its step."
    ),
    "wanted_columns": ("accounts.move_out_step_reached, written at close",),
}

#: ⛔ The DEPLOYMENT absence, kept under its ORIGINAL code so the tabs' copy map
#: still speaks it. ⚠ AMENDED 2026-08-26 (CR-038 W9 task 2): until then this
#: dict was the MISSING seam ("customers publishes NO metering read seam",
#: measured 2026-08-25) and rode on every row unconditionally. The seam exists
#: now — `seams.reads_for_unit` resolving `apps.metering.selectors
#: .reads_for_unit` by name — so this is served ONLY when that resolution comes
#: back None: a deployment where metering publishes no such selector.
READS_NOT_READABLE: dict[str, Any] = {
    "code": "unit_reads_not_readable_from_customers",
    "br_ref": "B1 · BR-MET-036 · CR-038 W9",
    "detail": (
        "B18 draws READS as `taken` / `due` and FINAL READ as `taken` / `due` / `estimated`, "
        "and `seams.reads_for_unit` — the reviewed door this absence used to ask for — "
        "resolved to nothing at call time: this deployment's metering publishes no "
        "`selectors.reads_for_unit`, so whether a read has been taken at the unit cannot be "
        "read from customers (B1 forbids the join). Stated rather than scored: None from a "
        "seam means 'cannot answer', never 'no reads' (DEF-075), and a `due`/`taken`/0 "
        "printed over it would be a verdict nobody derived (DEF-127)."
    ),
    "wanted_reads": (
        "apps.metering.selectors.reads_for_unit(unit_id, on=…) -> {unit_id, as_of, meters}",
    ),
}

#: ⚠ §4's `estimated` row RETIRED 2026-08-26 (CR-038 W9 task 4):
#: `ESTIMATED_STATE_HAS_NO_SETTLEMENT_FLAG` — *"`move_out_settlement` carries
#: no such flag, which is exactly what TC-MVO-7 asserts"* — is CLOSED by
#: `accounts.final_read_state` (migration 0026): `services.move_out` now
#: derives HOW the settlement's final read was obtained (taken / due /
#: estimated) at close and stores it beside `closed_at`, and a SERVED final
#: cell says `estimated` when the flag does. What REMAINS stated is the one
#: honest residue: a close that predates the column (or whose seam could not
#: answer at close time) has NO recorded flag, and this cell will not guess
#: one — the derived `taken`/`due` still serves, with this narrower absence
#: riding beside it.
FINAL_READ_STATE_NOT_RECORDED: dict[str, Any] = {
    "code": "final_read_state_not_recorded",
    "br_ref": "BR-CUS-031 · CR-038 W9 task 4",
    "detail": (
        "B18 §5.6.2's third, amber FINAL READ state — `estimated` — is a claim about how THE "
        "SETTLEMENT's final read was obtained. `accounts.final_read_state` records that at "
        "close since 2026-08-26, and this close carries NULL: it predates the column, or the "
        "read seam could not answer when it committed. The derived `taken`/`due` is served "
        "from live history; whether the settlement consumed an estimate is not recorded for "
        "this row and is not invented for it."
    ),
}

#: ⛔ A `taken`/`due` needs a date to measure AGAINST, and BR-CUS-022's
#: `waiting` move-in has none — the same missing fact that blocks activation.
READS_STATE_NEEDS_A_START_DATE: dict[str, Any] = {
    "code": "reads_state_needs_a_service_start_date",
    "br_ref": "BR-CUS-022 · BR-TEN-043",
    "detail": (
        "READS is measured against the move-in date — a read counts when a committed head "
        "exists at/after it — and this account has no service start date at all: BR-CUS-022 "
        "refuses even to activate it. There is no date to measure against, and measuring "
        "against today instead would be a wall clock standing in for the event date "
        "(BR-TEN-043). The `waiting` row state and `move_in_date_absence` carry the same "
        "cause; supplying the date resolves all three at once."
    ),
}

#: ⛔ The seam RESOLVED and answered: nothing is assigned to this unit. A
#: verdict over zero meters would be a lie in one direction or a wild goose
#: chase in the other, so the configuration fact is stated instead — the
#: posture billing's READ_ABSENT_NO_METER takes on the bill-run side.
UNIT_HAS_NO_METERS: dict[str, Any] = {
    "code": "unit_has_no_meters",
    "br_ref": "BR-MET-037 · BR-AST-028",
    "detail": (
        "`assets_on_unit` — the registry's own current-assignment read — answered that this "
        "unit holds no asset, so no read can exist and none can ever be taken. `taken` here "
        "would be vacuously true and read as 'the reads are in'; `due` would send a clerk to "
        "a meter that does not exist. A unit with nothing to read under a billed account is "
        "a configuration fact the staff must see."
    ),
}

#: ⛔ §4 row 4. BR-CUS-023 makes the deposit a LOOKUP and every account door
#: refuses to write it (`services.REFUSED_FIELDS`).
DEPOSIT_SENTENCE_HAS_NO_STORE: dict[str, Any] = {
    "code": "deposit_disposition_has_no_column",
    "br_ref": "BR-CUS-023 · BR-CUS-024 · US-CUS-007",
    "detail": (
        "B18 §5.5.2 draws DEPOSIT as a SENTENCE and not a number alone — `waived`, `on first "
        "bill`, `carried $153.50`, `collected $150.00`, `—`. Which of those applies is a "
        "DISPOSITION and no column records one: `accounts.deposit_on_file` holds an amount, "
        "and it is a REFUSED field on both doors that edit an account because BR-CUS-023 "
        "makes it a lookup from the plan deposit schedule. The AMOUNT ON FILE is served; the "
        "sentence is not, and `waived` is never printed for a zero — a deposit nobody "
        "recorded and a deposit deliberately waived are different facts that would read the "
        "same way."
    ),
    "wanted_columns": ("accounts.deposit_disposition",),
}

#: ⛔ §4 row 5. The tile counts an ELECTION and `accounts` has no column for one.
DEPOSIT_CARRY_ELECTION_HAS_NO_COLUMN: dict[str, Any] = {
    "code": "deposit_carry_election_has_no_column",
    "br_ref": "BR-CUS-024",
    "detail": (
        "B18 §5.5.1's `DEPOSITS TO CARRY OVER` counts *\"money moving from a closed "
        "account\"*, and BR-CUS-024's carry-forward mechanics are PROPOSED, not confirmed. "
        "`transfers.deposit_carry_elected` is exactly the column this tile needs — the "
        "transfer lane's own reason for storing an election was that it makes the equivalent "
        "tile *\"countable without inventing a figure to count\"* — and `accounts` has no "
        "equivalent. Counting deposits held instead would count every returning customer the "
        "moment somebody opened their row, before any human elected anything."
    ),
    # ⚠ **THE MOVE-IN RECORD EXISTS SINCE 2026-08-27 AND DELIBERATELY DOES NOT
    # CARRY THIS COLUMN — `DEF-921` / `OQ-510`.** `apps/customers/moves
    # .MoveRecord` was built for CR-039 wave D task 18, so the thing this
    # sentence points at is now a real table. It was NOT given the boolean,
    # because NEITHER WIZARD COLLECTS AN ELECTION: S19 refuses step 4's deposit
    # radios by name and S20 refuses step 3's disposition radios, both citing
    # BR-CUS-023/024, so the column would have no writer (hard-won law 2 on
    # data — DEF-837's shape). **This tile therefore still counts nothing and
    # the sentence below is still exactly true.** Closing it needs BR-CUS-024's
    # mechanics confirmed first, which is what `OQ-510` asks the PO.
    "wanted_columns": ("<the move-in record>.deposit_carry_elected",),
}

#: ⛔ §4 row 6, and it is the reason there is no SETTLEMENT verdict on this tab.
#: `move_out_settlement`'s OWN sentence, cited rather than restated (hard-won
#: law 5 — one derivation, one place).
FINAL_BILL_NOT_STATED: dict[str, Any] = {
    "code": move_out_settlement.GAP_FINAL_BILL,
    **move_out_settlement.GAP_REASONS[move_out_settlement.GAP_FINAL_BILL],
}

#: ⛔ BR-CUS-057's accrual is CONFIRMED and NOT BUILT. Again the engine's own
#: sentence, carried through.
DEPOSIT_INTEREST_NOT_ACCRUED: dict[str, Any] = {
    "code": move_out_settlement.GAP_DEPOSIT_INTEREST,
    **move_out_settlement.GAP_REASONS[move_out_settlement.GAP_DEPOSIT_INTEREST],
}

#: ⛔ §2 — THE FINDING OF THIS FILE, **NARROWED ON 2026-09-19 BY PO RULING**
#: (*"yes"*, asked whether the Move-outs list should show move-outs that have
#: not finished yet) — `DEF-CUS-5901`'s sibling half.
#:
#: ⚠⚠ **IT READ *"A move-out that has not committed yet is not recorded
#: anywhere"* UNTIL THAT DAY, AND THAT SENTENCE HAD BEEN FALSE SINCE `CR-035`.**
#: `wizard_parks` carries `flow`, `step`, `subject_ref`, `values` and
#: `waiting_on` for all five flows INCLUDING `move_out`, and
#: `move_record_reads` already serves such a row as `in_flight` with a real
#: step number. What was missing was never a column: it was this list's WINDOW,
#: which was closed accounts only. The window is widened now
#: (`move_out_parks_queryset`), so a parked move-out IS a row here.
#:
#: **WHAT IS STILL EXACTLY TRUE, AND IS WHY THE CODE IS KEPT RATHER THAN
#: DELETED** (a vanished code is a blank cell nobody can ask about — the
#: `MOVE_IN_DRAFT_HAS_NO_ACCOUNT` posture): a move-out nobody PARKED leaves no
#: trace at all. A clerk who opens the wizard, keys three steps and closes the
#: browser has written nothing, and `accounts` still carries no
#: `scheduled_move_out_on` — so B18 §5.6.7's `Scheduled` row, a move-out
#: somebody intends and has not started, is still a state this product cannot
#: hold.
MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE: dict[str, Any] = {
    "code": "move_out_before_close_has_no_store",
    "br_ref": "BR-CUS-030 · BR-SHL-048",
    "detail": (
        "A move-out somebody intends but has not started is not recorded anywhere. "
        "`accounts` carries no `scheduled_move_out_on` and no move-out state, so nothing "
        "marks an account as leaving until a clerk opens the wizard. A wizard a clerk has "
        "begun and parked IS listed here — it is a `wizard_parks` draft with a real step — "
        "and it is the only kind of unfinished move-out this product holds."
    ),
    "wanted_columns": (
        "accounts.scheduled_move_out_on",
        "accounts.move_out_state",
    ),
}

# ═══════════════════════════════════════════════════════════════════════════
# THE PARKED MOVE-OUT — what an UNFINISHED row can and cannot answer
# ═══════════════════════════════════════════════════════════════════════════
#: PO ruling 2026-09-19 (*"yes"*). Every one of these is a LIFECYCLE absence and
#: says so: none is a missing column, a broken seam or a job somebody failed to
#: do, and a screen that drew a dash for them would tell a clerk the opposite.
#: `move_record_reads._in_flight` takes the identical posture on the record page
#: and its docstring says why in the same words.

#: ⛔ A parked move-out has no reference **only when its tenant has no
#: `move_out` series row** — which is rare, and is the same absence a completed
#: move-out shows in that case.
#:
#: ⚠ **THIS WAS THE ORDINARY CASE UNTIL 2026-09-20 AND IS NOW THE EXCEPTION**
#: (PO ruling of that date, option A, item 9 — `OQ-CUS-12489` CLOSED). It read
#: *"A parked move-out carries NO reference, and that is a decision rather than
#: a gap … only a move-IN draft is numbered while it is in hand"*, which was
#: true for one day. `wizard_parks._allocate_draft_reference` now allocates
#: `MVO-{YY}-{0000}` from the `move_out` series the moment the draft is
#: written, and `services.move_out` adopts that number when the job completes,
#: so the row below serves `park.reference` and falls back to this sentence.
#:
#: ⚠ **AND THE CITATION ON THIS BLOCK READ `OQ-CUS-12511` UNTIL THE SAME DAY —
#: AN ID THE REGISTER HAS NEVER HELD** (`DEF-CUS-5937`). Its sibling at the
#: call site named `OQ-CUS-12489` correctly, so one question was cited two
#: ways forty lines apart and the wrong one pointed at nothing. It is
#: `DEF-GOV-5229`'s shape with the bite taken out — a dangling id rather than a
#: real id read for another real id — and nothing in the repo would have found
#: it, because no gate asks whether a cited question was ever ISSUED.
PARKED_MOVE_OUT_HAS_NO_REFERENCE: dict[str, Any] = {
    "code": "parked_move_out_has_no_reference",
    "br_ref": "BR-CUS-150 · BR-SHL-048",
    # ⚠ **WRITTEN AS THE CELL'S COPY, LIKE ITS SIBLINGS.**
    # `RecordNumberCell` renders THIS STRING to a clerk — the established
    # posture for this one family, which is why
    # `MOVE_JOB_PREDATES_THE_RECORD` is written the same way. No id, no
    # backtick, no module name may appear here (B14 rules 31 and 32).
    #
    # ⚠ **AND THE SENTENCE CHANGED WITH THE BEHAVIOUR.** It used to read *"This
    # move-out has not finished, so it has no number yet. A number is given
    # when it completes"* — which stopped being true on 2026-09-20, when an
    # unfinished move-out started being numbered at once. Leaving it would have
    # been hard-won law 1 exactly: a sentence describing a guarantee the code
    # no longer makes, shown to a clerk as fact.
    "detail": (
        "This move-out has no number because no number series for move-outs has been set "
        "up yet. Nothing that was typed is lost, and the move-out can still be finished."
    ),
}

#: ⛔ There is no settlement until the account closes, and there is nothing
#: half-built to show. The engine's rule on a CLOSED row is *any gap → no
#: landing*; here there is not even a gap to name, because no term has been
#: computed at all.
PARKED_MOVE_OUT_HAS_NO_SETTLEMENT: dict[str, Any] = {
    "code": "parked_move_out_has_no_settlement",
    "br_ref": "BR-CUS-030 · BR-SHL-048",
    "detail": (
        "Nothing is settled until the account closes. A parked draft changes nothing in the "
        "product — no closing date, no final bill, no deposit released — so there is no "
        "deposit-versus-outstanding position to state, not merely one that could not be "
        "read. The account's own page carries what is owed today."
    ),
}

#: ⛔ The move-out wizard's standalone road lets a clerk park BEFORE choosing an
#: account (`MoveOutWizard` — *"The standalone road has no account page to
#: return to until one is chosen"*), so `subject_ref.account_id` can be null.
PARKED_MOVE_OUT_HAS_NO_ACCOUNT: dict[str, Any] = {
    "code": "parked_move_out_has_no_account_yet",
    "br_ref": "BR-SHL-048",
    "detail": (
        "Nobody has chosen the account yet. The move-out wizard can be opened without one "
        "and parked on its first step, and a draft copies the ids a clerk has picked rather "
        "than linking to them — so an unpicked account is an empty field and not a broken "
        "link. It is chosen when the draft is picked back up."
    ),
}

#: ⛔ The account a draft named has since gone. `subject_ref` copies ids and
#: joins to nothing (BR-SHL-048 (a)), so this is the ruling working as designed
#: — *"Deleting a unit can never be blocked by a forgotten draft"* — and not a
#: dangling foreign key.
PARKED_MOVE_OUT_ACCOUNT_IS_GONE: dict[str, Any] = {
    "code": "parked_move_out_account_not_found",
    "br_ref": "BR-SHL-048",
    "detail": (
        "The account this draft named is no longer readable in this tenant. A draft copies "
        "the ids a clerk chose and joins to nothing, deliberately, so it outlives what it "
        "names. Picking the draft back up re-reads the account and asks for another."
    ),
}

#: ⚠ The search legs a DRAFT can answer, which are narrower than an account
#: row's — the `PENDING_JOB_SEARCH_LEGS_ARE_NARROWER` precedent, stated for the
#: same reason (BR-CUS-099: a box that silently finds nothing is worse than a
#: box that says what it matches).
PARKED_MOVE_OUT_SEARCH_LEGS_ARE_NARROWER: dict[str, Any] = {
    "code": "parked_move_out_has_no_account_number_to_search",
    "br_ref": "BR-SHL-048 · BR-CUS-099",
    "detail": (
        "An unfinished move-out answers to the label it was parked under — the customer or "
        "account name the clerk saw when they started it. It has no reference to match, and "
        "the account number, unit and address are copied ids rather than joined columns, so "
        "those legs find the finished move-outs only."
    ),
}

#: ⛔ §2 — the window's closing edge.
MOVE_OUT_WINDOW_HAS_NO_CLOSING_EDGE: dict[str, Any] = {
    "code": "move_out_window_has_no_closing_edge",
    "br_ref": "BR-CUS-031 · US-BIL-011",
    "detail": (
        "This tab's own copy says move-outs are listed *\"from the closing read to the final "
        "bill\"*. Billing publishes no per-account final-bill total, so nothing takes a row "
        "off this list and a closed account stays on it forever. Stated rather than left for "
        "a clerk to notice after the first hundred closures."
    ),
}

#: ⛔ §4 row 9 — B18's two `Done` move-ins.
MOVE_IN_DONE_HAS_NO_WINDOW: dict[str, Any] = {
    "code": "completed_move_in_has_no_retention_window",
    "br_ref": "BR-CUS-018",
    "detail": (
        "B18 §5.5.7 draws two `Done` move-ins. This list's window CLOSES when the account "
        "opens — which is what the tab's own copy says — so a completed move-in leaves it. "
        "Showing recent ones back would need a retention window (*how long does a finished "
        "move-in stay on the tab?*) that no rule states, and `opened_at` alone cannot tell a "
        "move-in completed last week from an account opened in 2019. Note that §5.5.1's five "
        "KPI tiles are ALL about open move-ins — there is no `completed` tile — which is the "
        "design agreeing with the window."
    ),
}

#: ⛔ §4 row 10 — B18's two `— draft` rows.
#:
#: ⚠⚠ **SUPERSEDED FOR THE APPROVED HALF ON 2026-09-16 (PO ruling, *"it should
#: do B"*, `BR-CUS-1077`), AND KEPT RATHER THAN DELETED.** Approving a move-in
#: now raises a pending `move_in_jobs` row, and **that row IS a `— draft` row on
#: this list**: no account, the linked request in the customer cell, and the
#: address walked from the premises the request resolved to. So the sentence
#: below is no longer true of an approved move-in.
#:
#: **It is still exactly true of an UNAPPROVED one**, which is what §5.5.7's two
#: drawn rows are: `SR-26-0044` is parked and `SR-26-0039` is `More info
#: needed`, neither has been approved, and neither raises a job. Those two are
#: still on the Requests tab and this list still cannot show them. The narrowed
#: sentence is `MOVE_IN_UNAPPROVED_DRAFT_IS_ON_THE_REQUESTS_TAB` below; this one
#: keeps its code because the tabs' copy map speaks it and a vanished code is a
#: blank cell nobody can ask about.
MOVE_IN_DRAFT_HAS_NO_ACCOUNT: dict[str, Any] = {
    "code": "parked_draft_has_no_account_row",
    "br_ref": "BR-CUS-018 · BR-CUS-080 · BR-CUS-1077",
    "detail": (
        "B18 §5.5.2 draws `— draft` in italic where the wizard has not created an account "
        "yet, and §5.5.7's `Alvarez, Rosa` and `Osei, Grace` are those two rows. An APPROVED "
        "move-in now appears here as exactly that row — the pending job approval raises. A "
        "move-in nobody has approved yet does not: it is a `service_requests` row and it is "
        "on the Requests tab, where `SR-26-0044` and `SR-26-0039` live."
    ),
}

#: ⛔ The narrowed half of the sentence above — what this list still cannot show.
MOVE_IN_UNAPPROVED_DRAFT_IS_ON_THE_REQUESTS_TAB: dict[str, Any] = {
    "code": "unapproved_move_in_is_a_request",
    "br_ref": "BR-CUS-080 · BR-CUS-1077",
    "detail": (
        "A move-in nobody has approved yet is an application and not a job, so it is not on "
        "this tab. It is on the Requests tab with its own state — parked, waiting on "
        "documents, or simply not decided — and it joins this list the moment a clerk "
        "approves it."
    ),
}

#: ⛔ `BR-CUS-1077` — the pending job has no account, and that is the RULING
#: rather than a gap. The Approve dialog says it in the drawing's own words.
PENDING_JOB_HAS_NO_ACCOUNT: dict[str, Any] = {
    "code": "pending_move_in_has_no_account",
    "br_ref": "BR-CUS-1077",
    "detail": (
        "This move-in has been approved and nobody has done it yet, so no account exists to "
        "name. Approving raises the job and opens nothing — the Approve dialog says so on "
        "every outcome: no account opens, no meter is fitted, nothing is energised. The "
        "account number appears when somebody runs the move-in."
    ),
}

#: ⛔ `BR-CUS-1077` — the deposit cell on a row with no account.
PENDING_JOB_HAS_NO_DEPOSIT: dict[str, Any] = {
    "code": "pending_move_in_has_no_deposit_on_file",
    "br_ref": "BR-CUS-023 · BR-CUS-1077",
    "detail": (
        "A deposit is held ON an account and this job has not opened one. Nothing is held and "
        "nothing has been waived; the amount the move-in wizard collects is decided when "
        "somebody runs it. The application's own fee is on the request."
    ),
}

#: ⛔ `DEF-CUS-5994` — a move-in draft names a UNIT, never an account.
#:
#: ⚠ **THIS IS THE ONE PLACE THE MOVE-OUT PRECEDENT DOES NOT CARRY OVER, AND IT
#: IS THE OLD OBJECTION ANSWERED RATHER THAN IGNORED.** `move_out_park_row`
#: could fill ACCOUNT, CUSTOMER and UNIT because a move-out wizard starts from
#: an account a clerk already picked. A move-IN starts from a UNIT and opens the
#: account at the end, so there is no account to name — which is exactly what
#: `parkedDrafts.tsx` §1 meant by *"a `MoveInRow` and a `WizardParkRow` share
#: not one field"*. The answer is `PENDING_JOB_HAS_NO_ACCOUNT`'s, one column
#: over: this list ALREADY renders a row with no account — B18 §5.5.2's own
#: `— draft` cell — and it says WHY rather than printing a dash. A draft is the
#: third row to do it, not the first.
PARKED_MOVE_IN_HAS_NO_ACCOUNT: dict[str, Any] = {
    "code": "parked_move_in_has_no_account_yet",
    "br_ref": "BR-SHL-048 · BR-CUS-018",
    "detail": (
        "Nobody has finished this move-in, so no account exists to name. The move-in wizard "
        "opens the account on its last step; a parked draft holds what was typed and has "
        "created nothing. The account number appears when somebody picks this back up and "
        "finishes it."
    ),
}

#: ⛔ `DEF-CUS-5994` — the deposit cell on a draft.
PARKED_MOVE_IN_HAS_NO_DEPOSIT: dict[str, Any] = {
    "code": "parked_move_in_has_no_deposit_on_file",
    "br_ref": "BR-CUS-023 · BR-SHL-048",
    "detail": (
        "A deposit is held ON an account and this draft has not opened one. A figure keyed "
        "into the wizard's deposit step is typing, not money: BR-SHL-048 (b) re-validates "
        "every field when the job is executed, and nothing is held until then."
    ),
}

#: ⛔ `DEF-CUS-5994` — which search legs a draft row can answer.
PARKED_MOVE_IN_SEARCH_LEGS_ARE_NARROWER: dict[str, Any] = {
    "code": "parked_move_in_has_no_account_number_to_search",
    "br_ref": "BR-SHL-048",
    "detail": (
        "A draft joins to nothing — BR-SHL-048 (a) gives `wizard_parks` no foreign key on "
        "purpose — so the account-number and request-number legs cannot reach one. A parked "
        "move-in answers to the label it was parked under, which is the unit a clerk picked."
    ),
}

#: ⛔ `BR-CUS-1077` §3 — the closing edge, stated rather than left to be noticed.
PENDING_JOB_CLOSES_ON_THE_RECORDED_MOVE: dict[str, Any] = {
    "code": "pending_job_closes_on_the_recorded_move",
    "br_ref": "BR-CUS-1077 · BR-CUS-150",
    "detail": (
        "A pending move-in leaves this list when a move-in record is written naming its "
        "request — which is what running the move-in does. A clerk who opens the account by "
        "another door passes no request, so nothing closes the job and it stays here beside "
        "the draft account it produced. It is the same job counted twice, and it is named "
        "here rather than hidden: closing it needs the move-in wizard opened FROM the job."
    ),
}

#: ⛔ §4 row 11 — the move-out request leg.
MOVE_OUT_REQUEST_LEG_UNLINKED: dict[str, Any] = {
    "code": "move_out_has_no_request_link",
    "br_ref": "BR-CUS-080",
    "detail": (
        "B18 §5.6.2 offers `request #` in the search box. A move-out creates no child row, so "
        "`link_child` has no reference to write and every move-out request in this tree "
        "carries `outcome_ref: None` — `SR-26-0046 · Thompson, R.` is the drawn one. The leg "
        "is therefore NOT offered rather than offered and silently empty. It would take "
        "`outcome_ref` carrying the CLOSING account's number, which is exactly what the "
        "move-in side already does (`SR-26-0045 → \"A-12048\"`)."
    ),
    "wanted_columns": ("service_requests.outcome_ref = the closing account_no",),
}

#: ⚠ §4's closing paragraph — the move-in leg IS served and its limit is named.
SEARCH_REQUEST_LEG_IS_BEST_EFFORT: dict[str, Any] = {
    "code": "request_leg_matches_only_linked_refs",
    "br_ref": "BR-CUS-080",
    "detail": (
        "The request-number leg resolves through BR-CUS-080's `outcome_ref`, which is TEXT "
        "and is not constrained to an account number — `link_child`'s own docstring calls it "
        "*\"TEXT, not a foreign key\"* and the service-request tests write `MVI-26-0001` into "
        "it. So the leg finds every move-in whose request was linked with the account "
        "number, and finds nothing for one linked another way. Best-effort by construction, "
        "named so a clerk who gets no hit knows it is a link problem and not an empty tenant."
    ),
}

#: ⚠ The settlement cell — see §6 of `move_out_settlement_cell`.
SETTLEMENT_TERMS_NOT_READ_ON_A_LIST: dict[str, Any] = {
    "code": "settlement_terms_not_read_on_a_list",
    "br_ref": "B19 §15.9 · BR-CUS-096 · BR-CUS-054",
    "detail": (
        "A full settlement also weighs unapplied credit, an unbanked export credit, the "
        "customer's OTHER accounts and any open dispute. This list reads none of them: each "
        "is a per-row query, and none of them can change a verdict that is already withheld "
        "for want of the final bill. The whole settlement, with every term, is "
        "`GET /accounts/{id}/close-impact` on the account's own page."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# THE SEGMENTS — every drawn state, and whether this product can fill it
# ═══════════════════════════════════════════════════════════════════════════
#: B18 §5.5.2's four segments plus `due` (§1). `supported` is served per
#: segment, the `disconnect_reads` posture: a screen disables what it cannot
#: fill and shows the reason ON the tab, rather than calling the route to
#: discover a refusal.
MOVE_IN_STATE_SCHEDULED = "scheduled"
MOVE_IN_STATE_DUE = "due"
MOVE_IN_STATE_WAITING = "waiting"
MOVE_IN_STATE_IN_PROGRESS = "in_progress"
MOVE_IN_STATE_DONE = "done"
#: ⚠ `BR-CUS-1077`, 2026-09-16. **The approved move-in nobody has started.**
#: NOT a B18 segment — see the entry below for why it is not `waiting` and not
#: `in_progress`, both of which are already spoken for and mean other things.
MOVE_IN_STATE_PENDING = "pending"
#: ⚠ **`DEF-CUS-5994`, 2026-09-20 — THE DRAFT A CLERK SAID NOTHING ABOUT.**
#: `Save & exit` writes a `wizard_parks` row with an EMPTY `waiting_on`, which
#: is `MOVE_IN_STATE_IN_PROGRESS` above: B18 drew that segment for *"a wizard
#: somebody is holding"* and it was declared unsupported only because this list
#: could not see one. It can now, so it is supported, and the DRAWN word is
#: used rather than a new one minted beside it.
#:
#: **`parked` IS THE OTHER HALF AND IT HAD TO BE MINTED.** A clerk who said what
#: they are waiting for is a different fact, and the Move-outs tab spells it
#: `waiting` — a word THIS tab already spends on BR-CUS-022's real blockage, an
#: account with no start date that can never open. Two facts must not share one
#: code, so the newer one takes the new word. Declared `drawn: False` for the
#: `due` and `pending` reason: no screen may mistake it for a B18 segment.
MOVE_IN_STATE_PARKED = "parked"

MOVE_IN_STATES: tuple[dict[str, Any], ...] = (
    {
        "code": MOVE_IN_STATE_PENDING,
        # B14 rule 33 — a label is ≤ 3 words and no sentence.
        "label": "Not started",
        # ⚠ Minted, and declared UNDRAWN so no screen mistakes it for a design
        # segment (the `due` precedent). B18's four are all facts about a move-in
        # that has an account: `waiting` means an account with no start date
        # (BR-CUS-022's real blockage), `in_progress` means a wizard somebody is
        # holding, and `scheduled`/`done` both read off `opened_at`. **This row
        # has no account at all**, so none of the four can carry it and reusing
        # one would make the state cell say something untrue of half the rows
        # under it.
        "drawn": False,
        "supported": True,
        "unavailable": None,
    },
    {
        "code": MOVE_IN_STATE_SCHEDULED,
        "label": "Scheduled",
        "drawn": True,
        "supported": True,
        "unavailable": None,
    },
    {
        "code": MOVE_IN_STATE_DUE,
        "label": "Due",
        # ⚠ NOT a B18 segment. Minted here for the row whose start date has
        # passed with the account still unopened — see §1. Declared so no
        # screen mistakes it for a drawn one.
        "drawn": False,
        "supported": True,
        "unavailable": None,
    },
    {
        "code": MOVE_IN_STATE_WAITING,
        "label": "Waiting",
        "drawn": True,
        "supported": True,
        "unavailable": None,
    },
    {
        "code": MOVE_IN_STATE_IN_PROGRESS,
        "label": "In progress",
        "drawn": True,
        # ⚠ **`supported` FLIPPED FROM FALSE ON 2026-09-20 (`DEF-CUS-5994`).**
        # It carried `STEP_HAS_NO_STORE` as its reason, and that reason was
        # about a row this list could not see rather than about a fact nobody
        # stored: a clerk holding a half-finished move-in IS recorded, in
        # `wizard_parks`, with a real step. The window widened; the segment
        # fills. `STEP_HAS_NO_STORE` still rides on every ACCOUNT and JOB row
        # and must — neither of those carries a step.
        "supported": True,
        "unavailable": None,
    },
    {
        "code": MOVE_IN_STATE_PARKED,
        "label": "Parked",
        # Minted 2026-09-20, undrawn for the `due` / `pending` reason.
        "drawn": False,
        "supported": True,
        "unavailable": None,
    },
    {
        "code": MOVE_IN_STATE_DONE,
        "label": "Done",
        "drawn": True,
        "supported": False,
        "unavailable": dict(MOVE_IN_DONE_HAS_NO_WINDOW),
    },
)

#: B18 §5.6.2's four segments. ⚠ **THREE OF THE FOUR ARE FILLABLE SINCE
#: 2026-09-19** — PO ruling, *"yes"*, asked whether the Move-outs list should
#: show move-outs that have not finished yet. Until that day exactly one was,
#: and the reason given for the other three had been false since `CR-035`.
MOVE_OUT_STATE_CLOSED = "closed"
#: ⚠ **A DRAFT — the clerk keyed some of the wizard and left.** `Save & exit`
#: writes a `wizard_parks` row with an EMPTY `waiting_on`, and `WizardPark
#: .waiting_on`'s own docstring is where that distinction is kept: *"EMPTY
#: MEANS *A DRAFT*, NOT *A PARK WITH NO REASON*"* (`CR-122-BRC06`).
MOVE_OUT_STATE_IN_PROGRESS = "in_progress"
#: ⚠ **PARKED — the clerk said what they are waiting for.** A non-empty
#: `waiting_on`, which is the one column that tells the two apart. **The draft
#: did not get a flag of its own on purpose**: two columns that must agree are
#: two columns free to disagree.
MOVE_OUT_STATE_WAITING = "waiting"


def move_out_park_state(park: Any) -> str:
    """`in_progress` or `waiting`, off the ONE column that distinguishes them.

    ⚠ **DERIVED IN ONE PLACE, AND THAT IS THE POINT.** The row builder, the
    `f.state` filter and any future tile all read this, so a draft cannot be
    `In progress` in the table and `Waiting` in a count. `row_dict` publishes
    the same distinction as `is_draft` for the panel; this is the list's word
    for it, and both read `waiting_on == ""`.
    """
    return MOVE_OUT_STATE_IN_PROGRESS if (park.waiting_on or "") == "" else MOVE_OUT_STATE_WAITING


MOVE_OUT_STATES: tuple[dict[str, Any], ...] = (
    {
        "code": MOVE_OUT_STATE_CLOSED,
        # ⚠ **`Completed`, NOT `Closed` — PO-ruled 2026-09-19 (`DEF-CUS-5901`),
        # and it is a DISPLAY word only.** The stored value is still `closed`
        # and no migration moves: the Accounts blueprint p117 draws `Completed`
        # and `move_record_reads.STATE_COMPLETED` already serves that word on
        # the record page, so the record spoke the blueprint's vocabulary and
        # only the LIST did not. The list is the surface that moved.
        #
        # ⚠ This label is a `defaultValue`, never the copy. The eleven
        # catalogues carry `customers.moveOuts.state.closed` and the screen
        # reads those; this is what a reader sees when no catalogue answers.
        "label": "Completed",
        # ⚠ NOT a B18 segment. B18's `Done` means *the wizard finished*; this
        # means *the account is closed*. A different claim keeps a different
        # word — and p117 draws `Completed` for exactly this row.
        "drawn": False,
        "supported": True,
        "unavailable": None,
    },
    {
        "code": "scheduled",
        "label": "Scheduled",
        "drawn": True,
        # ⛔ **STILL FALSE, AND IT IS THE ONE THAT STAYS FALSE.** `Scheduled` is
        # a move-out somebody intends and nobody has started — no wizard, no
        # draft, nothing written. `accounts` carries no `scheduled_move_out_on`
        # to hold it. The narrowed sentence is what this now names.
        "supported": False,
        "unavailable": dict(MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE),
    },
    {
        "code": MOVE_OUT_STATE_IN_PROGRESS,
        "label": "In progress",
        "drawn": True,
        # ✅ p117's drawn second row — `MVO-26-0087 · 2 of 6 · In progress` —
        # is THIS, and it is real data: a `wizard_parks` draft for `move_out`
        # with a real step. See `move_out_parks_queryset`.
        "supported": True,
        "unavailable": None,
    },
    {
        "code": MOVE_OUT_STATE_WAITING,
        "label": "Waiting",
        "drawn": True,
        # ✅ The same draft with a reason recorded against it (`Park — what are
        # you waiting for?`). One store, two words, one column deciding.
        "supported": True,
        "unavailable": None,
    },
)


# ═══════════════════════════════════════════════════════════════════════════
# SHARED PLUMBING — one tenant read, one clock, one week window
# ═══════════════════════════════════════════════════════════════════════════
def _tenant_id() -> Any:
    """ONE tenant resolution for this surface — `transfers._tenant_id`.

    It raises `AuthError(AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")` when no
    tenant is set, which is hard rule 1 stated once. A copy here would be a
    second answer to *"may this query run at all"*.
    """
    return transfers._tenant_id()


def _as_of(as_of: date | None) -> date:
    """BR-TEN-043 — the event date is an argument, never a wall clock.

    The default is the TENANT's today (`seams.tenant_today`), not the server's:
    §5.5.1's `STARTING THIS WEEK` and §5.6.1's `LEAVING THIS WEEK` are windows a
    clerk reads against their own calendar.
    """
    return as_of or seams.tenant_today()


def _within_the_week(day: date | None, as_of: date) -> bool:
    """§5.5.1 / §5.6.1's caption, verbatim: *"within 7 days of today"*.

    Inclusive at both ends and it does NOT reach backwards — a date that has
    passed is not "this week". The same window `transfer_reads._within_the_week`
    applies to §5.7.1, kept identical deliberately: three tabs on one screen
    counting "this week" two different ways is a KPI strip that lies.
    """
    if day is None:
        return False
    return as_of <= day <= as_of + timedelta(days=WEEK_DAYS)


def _min_search_chars() -> int:
    """IS-3's two characters, imported and not restated: a one-character `A`
    would otherwise return every account in the tenant through the number leg."""
    from apps.customers import selectors

    return selectors.MIN_SEARCH_CHARS


def _premise(unit_id: Any) -> str | None:
    """The service address, through customers' single reader for it.

    `selectors._premise_cell` returns `(label, full)` and formats *"1408 Elm St
    · A"*; this takes the full cell. A second formatter here would print the
    same address two ways on two tabs of one screen.
    """
    from apps.customers import selectors

    if unit_id is None:
        return None
    _label, premise = selectors._premise_cell(unit_id)
    return premise


def _customer_names(account_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """BR-CUS-054's entity for a whole page at once, with the S17 fallback.

    Two reads, both batched, because a per-row `customer_for_account` is a query
    per row on a worklist:

      1. `customer_accounts` — the ENTITY (BR-CUS-054). This is the right answer
         and it is what the Transfers tab shows.
      2. the primary CONTACT's name — `selectors._primary_contact_names`, the
         same ordering (`-is_primary`, then oldest) the accounts list uses.

    `None` from both is a REAL answer and not a gap: `customer_for_account`'s
    own docstring says every account created before the BR-CUS-054 entity
    existed has no link. The row carries `customer: None` and the screen renders
    the absence; nothing invents a name.
    """
    from apps.customers import selectors

    out: dict[str, dict[str, Any]] = {}
    if not account_ids:
        return out
    links = models.CustomerAccount.objects.filter(
        tenant_id=_tenant_id(), account_id__in=list(account_ids)
    ).select_related("customer").order_by("created_at")
    for link in links:
        out.setdefault(
            str(link.account_id),
            {
                "customer": link.customer.display_name,
                "customer_no": link.customer.customer_no,
                "customer_id": str(link.customer_id),
                "source": "customer_entity",
            },
        )
    contacts = selectors._primary_contact_names(list(account_ids))
    for account_id, name in contacts.items():
        if account_id not in out and name:
            out[account_id] = {
                "customer": name,
                "customer_no": None,
                "customer_id": None,
                # Named so a screen — and a reader of this payload — can tell
                # the entity from the fallback. They are different facts.
                "source": "primary_contact",
            }
    return out


# ═══════════════════════════════════════════════════════════════════════════
# THE READS SEAM'S CONSUMERS (CR-038 W9 task 2) — one derivation, two cells
# and one tile
# ═══════════════════════════════════════════════════════════════════════════
#: B18's read states. `taken`/`due` DERIVE from the seam on both tabs;
#: `estimated` (⚠ joined 2026-08-26, CR-038 W9 task 4) is served on a FINAL
#: READ cell only, and only off the settlement's OWN stored flag
#: (`accounts.final_read_state`) — never derived from history, because it is a
#: claim about which read the settlement consumed. A move-in READS cell
#: finding the third word has found a bug; a move-out cell finding a FOURTH
#: has too.
READS_STATE_TAKEN = "taken"
READS_STATE_DUE = "due"
READS_STATE_ESTIMATED = "estimated"


def _unit_reads_answers(unit_ids: list[Any]) -> dict[str, dict[str, Any]] | None:
    """`seams.reads_for_unit` once per DISTINCT unit — or None when unwired.

    The seam is resolved with `on=None` (the latest heads outright) and each
    caller compares against its OWN event date, because one list holds rows
    with different dates (each account's `closed_at` / `opened_at`) and the
    per-meter `latest_read_at` answers every one of them: the newest head is
    at/after a date exactly when SOME head is (BR-TEN-043 — the event date
    stays the row's, never a clock read here).

    **None means the seam did not resolve** — metering publishes no selector in
    this deployment — and it is None for every unit at once (a module-level
    fact), so the first refusal answers for the sweep. The callers then serve
    `READS_NOT_READABLE`, never a guess (DEF-075/DEF-127).
    """
    answers: dict[str, dict[str, Any]] = {}
    for unit_id in unit_ids:
        key = str(unit_id)
        if key in answers:
            continue
        answer = seams.reads_for_unit(unit_id)
        if answer is None:
            return None
        answers[key] = answer
    return answers


def _waiting_on_a_reading(rows: list[Any], jobs: list[Any]) -> dict[str, Any]:
    """The Accounts blueprint p077's THIRD tile — `WAITING ON A READING`
    (**p077 of the 281-page edition**; p073 before the 2026-09-19 replacement).

    ⚠ **IT REPLACED `WAITING ON THE CUSTOMER`, AND IT IS A DIFFERENT QUESTION
    RATHER THAN A REWORDING** (PO-approved 2026-09-19). The drawing's own note
    says why: *"The Reads column is the one a clerk works from. MVI-26-0113
    opened with no reading at all and MVI-26-0114 with one estimated register —
    both bill, and both need somebody to go back."* A move-in waiting on a
    document is waiting on a PERSON; a move-in waiting on a reading has already
    opened and is billing an estimate, which is money.

    ⚠ **DERIVED THROUGH `unit_reads_cell`, NEVER RE-IMPLEMENTED — THAT IS THE
    WHOLE DESIGN OF THIS FUNCTION.** The tile and the READS column answer one
    question, so they call one derivation over one seam sweep. A second
    hand-rolled count here is how a tile comes to say `2` over a table showing
    three amber cells, which a clerk reports as a bug in the number rather than
    as the disagreement it is. `move_in_state`'s own docstring sets that posture
    and `OPEN` follows it for the same reason.

    ⚠ **ONE SWEEP FOR BOTH KINDS OF ROW** (`BR-CUS-1077`) and one sweep for the
    WHOLE window rather than the page — a tile counts the list, not the page in
    front of you — which is the `ar_positions` discipline and never a seam call
    per row.

    ⚠ **A ROW WHOSE READS CANNOT BE JUDGED IS NOT COUNTED EITHER WAY, AND THE
    COUNT SAYS HOW MANY THOSE WERE.** Three branches of `unit_reads_cell` serve
    no state at all — the seam unresolved, a unit with no meters, a move-in with
    no start date to measure against — and each is *cannot answer*, never *no
    reads* (DEF-075). Rolling them into the count would overstate the work;
    dropping them silently would be a check reporting zero over a scope it
    excludes, which is hard-won law 7's fifth shape and the hardest to see. So
    `unjudged` rides beside `count` and the screen can state it.

    Returns `{"count", "unjudged", "drawn_as"}`. `drawn_as` is the drawing's own
    sub-line, kept as DATA because it cannot be served: p077 writes *"one
    unread, one estimated"*, and a move-in READS cell is two-state BY DESIGN —
    `taken` / `due`, with `estimated` reserved for a move-out settlement's own
    stored flag. The record page hit the same contradiction on 2026-09-19 and
    resolved it the same way (its amber chip says `1 register unread`).
    """
    answers = _unit_reads_answers(
        [row.unit_id for row in rows]
        + [job.request.resolved_unit_id for job in jobs if job.request.resolved_unit_id]
    )
    count = 0
    unjudged = 0
    pairs: list[tuple[Any, Any]] = [(row.unit_id, row.opened_at) for row in rows]
    pairs += [
        (job.request.resolved_unit_id, job.request.requested_start)
        for job in jobs
        if job.request.resolved_unit_id
    ]
    # A job with no resolved unit has nothing to sweep and cannot be judged —
    # counted as unjudged rather than skipped, for the reason in the docstring.
    unjudged += sum(1 for job in jobs if not job.request.resolved_unit_id)
    for unit_id, measured_from in pairs:
        cell = unit_reads_cell(
            None if answers is None else answers.get(str(unit_id)),
            measured_from=measured_from,
            final=False,
        )
        if cell["state"] is None:
            unjudged += 1
        elif cell["state"] != READS_STATE_TAKEN:
            count += 1
    return {"count": count, "unjudged": unjudged, "drawn_as": "one unread, one estimated"}


def _meters_due(answer: dict[str, Any], threshold_iso: str) -> list[str]:
    """The meters with NO committed head at/after the date — named, so a clerk
    acts on a meter number and a test can pin exactly which one is missing.

    ISO dates compare lexically == chronologically; `latest_read_at` is the
    seam's own per-meter max, so `latest >= threshold` ⟺ some committed head
    is at/after the date, which is the wired definition of covered."""
    return [
        meter["asset_no"]
        for meter in answer["meters"]
        if not (meter["latest_read_at"] and meter["latest_read_at"] >= threshold_iso)
    ]


def unit_reads_cell(
    answer: dict[str, Any] | None,
    *,
    measured_from: date | None,
    final: bool,
    settlement_state: str | None = None,
) -> dict[str, Any]:
    """B18's READS (§5.5.2) / FINAL READ (§5.6.2) cell, derived through the seam.

    ONE derivation for both tabs and the tile, so the cell a clerk reads and
    the KPI they act on cannot disagree (the `move_in_state` posture):

        taken ≡ every meter currently on the unit has a committed lineage head
                at/after the row's own event date (move-in `opened_at`,
                move-out `closed_at` — BR-CUS-030: `closed_at` IS the date)
        due   ≡ any meter has not

    ⚠ **`estimated` JOINED 2026-08-26 (CR-038 W9 task 4), AND ONLY THE STORED
    FLAG CAN SAY IT.** `settlement_state` is `accounts.final_read_state` — how
    the settlement's final read was obtained, derived once at close by
    `services.move_out` and stored beside `closed_at`. On a FINAL cell:

      · flag `estimated`      → the cell says `estimated` — B18's amber third
        state, live at last. History is NOT consulted for this word: a real
        read landing after the close does not un-estimate the settlement.
      · flag `taken` / `due`  → the cell serves the LIVE derived `taken`/`due`
        (a final read committed after the close updates the cell; the flag
        stays the close-time record) with no absence riding.
      · flag NULL             → the derived `taken`/`due` serves, and
        `FINAL_READ_STATE_NOT_RECORDED` rides beside it — a close that
        predates the column is not guessed about.

    Three branches serve NO state, each with its own reason (never a default —
    a blank and an absence are indistinguishable once rendered):

      · `answer is None`      → the seam did not resolve (`READS_NOT_READABLE`)
      · no meters on the unit → `UNIT_HAS_NO_METERS` — a verdict over zero
        meters lies in one direction or the other
      · `measured_from` None  → `READS_STATE_NEEDS_A_START_DATE` (BR-CUS-022's
        `waiting` move-in has nothing to measure against)

    An estimated covering head still derives `taken` — a committed estimate is
    a committed read; only the settlement's own flag may say the third word.
    A served move-in cell ignores `settlement_state` — READS is two-state by
    design.
    """
    cell: dict[str, Any] = {
        "state": None,
        "measured_against": None,
        "meters_total": None,
        "meters_read": None,
        "missing": [],
        "unavailable": None,
    }
    if answer is None:
        cell["unavailable"] = dict(READS_NOT_READABLE)
        return cell
    meters = answer["meters"]
    cell["meters_total"] = len(meters)
    if not meters:
        cell["meters_total"] = 0
        cell["unavailable"] = dict(UNIT_HAS_NO_METERS)
        return cell
    if measured_from is None:
        cell["unavailable"] = dict(READS_STATE_NEEDS_A_START_DATE)
        return cell
    threshold = measured_from.isoformat()
    missing = _meters_due(answer, threshold)
    derived = READS_STATE_DUE if missing else READS_STATE_TAKEN
    if final and settlement_state == READS_STATE_ESTIMATED:
        state = READS_STATE_ESTIMATED
    else:
        state = derived
    cell.update(
        {
            "state": state,
            "measured_against": threshold,
            "meters_read": len(meters) - len(missing),
            "missing": missing,
            "unavailable": (
                dict(FINAL_READ_STATE_NOT_RECORDED) if final and settlement_state is None else None
            ),
        }
    )
    return cell


# ═══════════════════════════════════════════════════════════════════════════
# THE BR-CUS-080 LINK — the request a move-in came from
# ═══════════════════════════════════════════════════════════════════════════
def _requests_by_account_no(account_nos: list[str], *, outcome: str) -> dict[str, dict[str, Any]]:
    """Every service request whose `outcome_ref` names one of these accounts.

    BR-CUS-080, PO 2026-08-24, verbatim: *"origin_service_request_id; SR keeps
    outcome + outcome_ref so it alone answers 'what happened to this
    application'"*. The child half of that link does not exist for a move-in —
    there is no child table (§0) — so the ACCOUNT is the child and its NUMBER is
    what `link_child` wrote. `core/sample_fixture.py` seeds exactly that:
    `SR-26-0045 → outcome_ref: "A-12048"`.

    Matched on `outcome_ref` and NOT on `outcome_kind`, deliberately: the
    fixture writes `outcome_kind: "account"` on the linked Kwan row while
    `OUTCOME_CHILD_KINDS` maps the same outcome to `"move_in"`, so the two
    vocabularies already disagree in this tree. `outcome` is the signed field
    (`ServiceRequest.OUTCOMES`) and is what this filters on. **The disagreement
    is REPORTED, not resolved here** — `outcome_kind` is another lane's column.
    """
    if not account_nos:
        return {}
    rows = models.ServiceRequest.objects.filter(
        tenant_id=_tenant_id(), outcome=outcome, outcome_ref__in=list(account_nos)
    ).order_by("created_at")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        out.setdefault(
            str(row.outcome_ref),
            {
                "id": str(row.id),
                "request_no": row.request_no,
                # ORTHOGONAL to `state` — the model's own docstring, and it is
                # what §5.5.1's `WAITING ON DOCUMENTS` tile is drawn against.
                "waiting_on": row.waiting_on,
                "park_note": row.park_note,
                "state": row.state,
                "requested_start": (
                    row.requested_start.isoformat() if row.requested_start else None
                ),
            },
        )
    return out


def _account_nos_for_request_term(term: str, *, outcome: str) -> list[str]:
    """The account numbers whose linked request number matches `term`.

    §5.5.2's fourth search leg, and the one `transfer_reads` had to give up
    (BR-CUS-099). It works here only because the link ref IS the account number
    — see `SEARCH_REQUEST_LEG_IS_BEST_EFFORT` for the limit that buys.
    """
    return [
        str(ref)
        for ref in models.ServiceRequest.objects.filter(
            tenant_id=_tenant_id(),
            outcome=outcome,
            outcome_ref__isnull=False,
            request_no__icontains=term,
        ).values_list("outcome_ref", flat=True)
        if ref
    ]


# ═══════════════════════════════════════════════════════════════════════════
# THE MOVE-INS LIST (B18 §5.5)
# ═══════════════════════════════════════════════════════════════════════════
def move_in_state(account: models.Account, *, as_of: date) -> str:
    """§1's three-way derivation, in one place so the row and the KPIs agree.

    ⚠ **`waiting` IS A MEASURED BLOCKAGE, NOT A LABEL.** An account with no
    `opened_at` cannot be activated at all: `services._make_occupying` raises
    `BIZ_COMPLETENESS` on BR-CUS-022 because *"an occupying account without one
    could never be billed"*. So the row genuinely cannot move until a human
    supplies the date, which is what §5.5.2's `Waiting` segment means.
    """
    if account.opened_at is None:
        return MOVE_IN_STATE_WAITING
    return MOVE_IN_STATE_SCHEDULED if account.opened_at > as_of else MOVE_IN_STATE_DUE


def _deposit_cell(account: models.Account) -> dict[str, Any]:
    """§5.5.2's DEPOSIT column — the AMOUNT, never the sentence.

    ⚠ **`waived` IS NEVER PRINTED, AND THAT IS THE POINT OF THIS CELL.** B18
    draws five outcomes and four of them are dispositions no column records
    (`DEPOSIT_SENTENCE_HAS_NO_STORE`). A zero here means *no deposit is recorded
    on this account* and NOT *a deposit was waived* — a clerk who reads the
    second where the first is true has been told a decision was made that
    nobody made. So `recorded` is served as its own boolean and the sentence is
    served as an absence.

    Both money shapes per CLAUDE.md rule 2: `stored` at 4 dp, `display` at 2,
    rounded ONCE here through `move_out_settlement._pair` — the same formatter
    the settlement engine uses, so the deposit reads identically on this tab and
    on the close-impact screen.
    """
    held = account.deposit_on_file or move_out_settlement.ZERO
    return {
        "currency": account.currency,
        "amount": move_out_settlement._pair(held),
        "recorded": held > move_out_settlement.ZERO,
        "sentence": None,
        "unavailable": [dict(DEPOSIT_SENTENCE_HAS_NO_STORE)],
    }


def move_in_row(
    account: models.Account,
    *,
    as_of: date,
    customer: dict[str, Any] | None,
    request: dict[str, Any] | None,
    reads: dict[str, Any],
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One §5.5.2 row: `ACCOUNT · CUSTOMER · UNIT · MOVE-IN DATE · STEP · READS ·
    DEPOSIT · STATE`.

    The STEP and DEPOSIT-sentence cells are stated absences, each with its own
    reason (§4); READS derives through the seam since 2026-08-26 (CR-038 W9
    task 2 — `reads` is `unit_reads_cell`'s answer, built by the caller from
    ONE seam sweep over the page). Nothing here defaults, and no cell is left
    blank: a blank and an absence are indistinguishable once rendered, which is
    the lesson `transfers._serialize` wrote its `"→ —"` literal for.
    """
    return {
        # CR-039 wave D 17–19 — the leading `reference` cell. The caller builds
        # it from ONE query over the page (`move_records_by_account`); a row
        # never reaches for its own record. `drafted=True` by default here
        # because every row on THIS list is a BR-CUS-018 draft, so the honest
        # absence is *"the job has not happened yet"* and not *"we did not keep
        # a record"* — see `move_reference_cell`'s three arms.
        **(reference or move_reference_cell(None, drafted=True)),
        # `BR-CUS-1077` — WHICH KIND OF ROW THIS IS. Served on every row rather
        # than inferred from the absent account number, because an inference is
        # a second implementation of a rule and this one is the difference
        # between *a move-in nobody has started* and *a move-in with an account*.
        "row_kind": ROW_KIND_ACCOUNT,
        "job_id": None,
        "account_id": str(account.id),
        "account_absence": None,
        # ⚠ NEVER `— draft`. Every row on this list HAS a number, because the
        # account row is what the row is. §5.5.2's italic `— draft` belongs to
        # requests with no account — see `MOVE_IN_DRAFT_HAS_NO_ACCOUNT`.
        "account_no": account.account_no,
        "customer": (customer or {}).get("customer"),
        "customer_no": (customer or {}).get("customer_no"),
        "customer_source": (customer or {}).get("source"),
        "customer_absence": (
            None
            if customer
            else {
                "code": "account_has_no_customer_link",
                "br_ref": "BR-CUS-054",
                "detail": (
                    "no `customer_accounts` link and no primary contact on this account. A "
                    "real answer, not a gap: an account created before the customer entity "
                    "existed has neither."
                ),
            }
        ),
        "unit_id": str(account.unit_id),
        "unit": _premise(account.unit_id),
        # §5.5.2 sorts on this and BR-CUS-022 requires it before the account can
        # open, so a NULL is the `waiting` state's whole cause rather than a
        # missing display value.
        "move_in_date": account.opened_at.isoformat() if account.opened_at else None,
        "move_in_date_absence": (
            None
            if account.opened_at
            else {
                "code": "service_start_date_not_set",
                "br_ref": "BR-CUS-022",
                "detail": (
                    "no service start date, so this account cannot be activated at all — "
                    "`_make_occupying` refuses an occupying account without one because it "
                    "could never be billed. This is what the row is waiting on."
                ),
            }
        ),
        # ⛔ §4 row 1. The DENOMINATOR is served and the numerator is not: a
        # screen that knows the bar has six segments can draw it empty and say
        # why, which is more honest than an invented `1 of 6`.
        "step": move_in_step_cell(None, unavailable=dict(STEP_HAS_NO_STORE)),
        # §5.5.2's READS — derived through the seam; measured against THIS
        # row's own move-in date (BR-TEN-043), which is why the caller passes
        # the built cell rather than this function reaching for a clock.
        "reads": reads,
        "deposit": _deposit_cell(account),
        "state": move_in_state(account, as_of=as_of),
        "starting_this_week": _within_the_week(account.opened_at, as_of),
        # §5.5.1's `OLDEST` is measured from here — the day the row was booked in.
        "booked_in_on": account.created_at.date().isoformat(),
        "age_days": (as_of - account.created_at.date()).days,
        # BR-CUS-080's link, when the request was linked with the account number.
        "request": request,
        "request_absence": None if request else {"code": "no_linked_request"},
        # `BR-CUS-1077` — the key the job rows carry, served here as `None` so
        # one screen reads one shape. A key that exists on half the rows is a
        # key every reader has to guard, and the guard is where they differ.
        "documents_outstanding": None,
    }


#: CR-045 wave D task D.9 (DEF-1702) — the ONE filter dimension the Move-ins
#: tab declares, in BR-SHL-011's `f.<name>` grammar. The vocabulary is exactly
#: the `MOVE_IN_STATES` codes marked `supported`; `in_progress` is NOT here
#: because `STEP_HAS_NO_STORE` — offering a filter for a state this schema
#: cannot hold would return an empty list forever and read as "there are none".
MOVE_IN_FILTERS: tuple[str, ...] = ("state",)

#: The same, for Move-outs (task D.10) — and it is a WINDOW rather than a state.
#: `MOVE_OUT_STATES` marks exactly one code `supported` (`closed`), so a state
#: filter would offer one option that changes nothing. `accounts.closed_at` is
#: the one stored, filterable fact on the row.
MOVE_OUT_FILTERS: tuple[str, ...] = ("closed",)

#: `f.closed` → how many days back from the as-of date. Buckets and not a date
#: PAIR because `TableRequestState.filters` is `Record<string, string>` — one
#: value per dimension, signed in BR-SHL-011 — so a range is not expressible
#: without an API change (`OQ-306` already carries that limit).
MOVE_OUT_CLOSED_WINDOWS: dict[str, int] = {"last7": 7, "last30": 30, "last90": 90}


#: ── §5.5.2 AND §5.6.2's SORT VOCABULARIES (`BR-CUS-1046`, PO 2026-09-12) ───
#: Two lists, two maps, ONE default: both open on the creation order and both
#: keep the date ordering they used to open on as a clickable column.
#:
#: ⚠ **A MOVE ROW *IS* AN ACCOUNT ROW ON THESE TWO TABS** — both querysets
#: select `Account`, which is why the created column is `accounts.created_at`
#: and why `booked_in_on` (the row's own age cell) reads the same field. The
#: sort and the cell cannot disagree.
#: ⚠ **EVERY NAME HERE IS THE SCREEN'S EXISTING COLUMN KEY, NOT A NEW ONE.**
#: `DataTable` stores a clerk's show/hide/reorder preference keyed by
#: `screenId` + column key (`BR-SHL-013`, `DEF-647`), so renaming a column to
#: match a tidier server name would silently discard every saved column set on
#: this screen. The server name moved instead; it is the cheaper half.
MOVE_IN_SORTS: dict[str, tuple[Any, ...]] = {
    #: ⚠ **WRITTEN ASCENDING, LIKE EVERY TERM IN THIS MAP — `order_terms` FLIPS
    #: IT AND `DEFAULT_DIR` IS `desc`.** The first draft of this pass stored
    #: `-created_at` here AND defaulted to `desc`, so the flip cancelled the
    #: minus and every list opened on the OLDEST row: the exact inversion of
    #: the ruling, shipped as a working feature. Nothing raised — it was found
    #: by curling the endpoint and reading the first three rows.
    "created": ("created_at", "id"),
    #: §5.5.2's footnote until 2026-09-12: *"Sorted by move-in date, soonest
    #: first. A move-in with no start date is listed first — it cannot open
    #: until one is set."* The nulls behaviour is UNCHANGED and is the database
    #: default for `ASC` on PostgreSQL only, so it is written out: see the
    #: queryset's own note.
    "move_in_date": ("opened_at", "id"),
    "account": ("account_no", "id"),
}
MOVE_IN_DEFAULT_SORT = "created"
MOVE_OUT_SORTS: dict[str, tuple[Any, ...]] = {
    "created": ("created_at", "id"),
    #: §5.6.2's footnote until 2026-09-12: *"Sorted by move-out date, soonest
    #: first."*
    "move_out_date": ("closed_at", "id"),
    "account": ("account_no", "id"),
}
MOVE_OUT_DEFAULT_SORT = "created"
MOVE_DEFAULT_DIR = "desc"


def move_ins_queryset(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    as_of: date | None = None,
    sort: str | None = None,
    dir: str = MOVE_DEFAULT_DIR,
):
    """§1's window, with §5.5.2's five search legs and §5.7.3's exclusion.

    ⚠ **THE ORDER OF THE TWO FILTERS IS NOT ARBITRARY.** The window is selected
    first and the transfer halves are subtracted from it, through the PUBLISHED
    `transfers.exclude_transfer_halves` and never through a set built here. A
    transfer's incoming half is created by `services.create_account`, so it can
    land in exactly the draft class this window selects — and §5.7.3's counting
    contract says it must not be listed twice.
    """
    from apps.customers import selectors

    rows = (
        models.Account.objects.filter(
            tenant_id=_tenant_id(),
            # BR-CUS-055 — the CLASS, never the label. See §1.
            status__behavior_class=services.CLASS_NON_BILLABLE,
            closed_at__isnull=True,
        )
        .select_related("status")
    )
    # ── B18 §5.7.3's counting contract, applied through the published form ──
    rows = transfers.exclude_transfer_halves(rows, field="id")

    # ── CR-045 wave D task D.9 · `f.state`, APPLIED IN SQL (DEF-1702) ──────
    # ⚠ **THE PREDICATE IS `move_in_state` READ BACKWARDS, AND IT HAS TO STAY
    # THAT WAY.** That function is §1's three-way derivation and the KPIs read
    # it too; a filter that decided `scheduled` by any other test could show a
    # row whose own STATE cell says something else. The three branches here are
    # the exact negations of its three returns:
    #     waiting   → opened_at IS NULL     (the blockage — BR-CUS-022)
    #     scheduled → opened_at >  as_of
    #     due       → opened_at <= as_of    (never NULL — `waiting` owns those)
    # An unknown value returns nothing rather than everything: BR-SHL-011 says
    # fall back or clamp, and falling back to "no filter" on a value the user
    # explicitly picked would silently show them MORE than they asked for.
    state = (filters or {}).get("state")
    if state:
        on = _as_of(as_of)
        if state == MOVE_IN_STATE_WAITING:
            rows = rows.filter(opened_at__isnull=True)
        elif state == MOVE_IN_STATE_SCHEDULED:
            rows = rows.filter(opened_at__gt=on)
        elif state == MOVE_IN_STATE_DUE:
            rows = rows.filter(opened_at__isnull=False, opened_at__lte=on)
        else:
            rows = rows.none()

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        matches = Q(account_no__icontains=term)
        # BR-CUS-053's customer legs — the ENTITY and the contact fallback, the
        # same two `_customer_names` renders from.
        matches |= Q(customeraccount__customer__display_name__icontains=term)
        matches |= Q(customeraccount__customer__customer_no__icontains=term)
        matches |= Q(contact__full_name__icontains=term, contact__deleted_at__isnull=True)
        # BR-CUS-053's unit / address leg, through metering's own selector (B1).
        unit_ids = [str(unit_id) for unit_id in seams.unit_ids_matching(term)]
        if unit_ids:
            matches |= Q(unit_id__in=unit_ids)
        # §5.5.2's `request #` leg — see `_account_nos_for_request_term`.
        request_account_nos = _account_nos_for_request_term(
            term, outcome=models.ServiceRequest.OUTCOME_MOVE_IN
        )
        if request_account_nos:
            matches |= Q(account_no__in=request_account_nos)
        rows = rows.filter(matches).distinct()
    # ── `BR-CUS-1046` / `DEF-CUS-5060` — the ORDER BY, and the default moved ─
    # ⚠ **THIS LIST OPENED ON `opened_at` UNTIL 2026-09-12**, under §5.5.2's
    # footnote *"Sorted by move-in date, soonest first. A move-in with no start
    # date is listed first — it cannot open until one is set."* The PO ruled the
    # default to the creation order and ruled this ordering into a column:
    # *"(c) All eight open newest-first and the six gain a sort control."*
    #
    # ⚠ **THE TIEBREAK CHANGED FROM `account_no` TO `id`, DELIBERATELY.** A page
    # is a window over an ORDER, and `(opened_at, account_no)` is not total —
    # two move-ins for the same account on the same date could swap between
    # pages. `id` is unique on every one of these sorts, which is the property
    # the pager actually needs.
    return rows.order_by(
        *pagination.order_terms(sort, dir, columns=MOVE_IN_SORTS, default=MOVE_IN_DEFAULT_SORT)
    )


# ═══════════════════════════════════════════════════════════════════════════
# `BR-CUS-1077` — THE SECOND KIND OF ROW: THE PENDING JOB (PO 2026-09-16)
# ═══════════════════════════════════════════════════════════════════════════
#: The two kinds of row this tab now serves, named on every row so a screen can
#: tell them apart without inferring it from a missing account number. An
#: inference is what `DEF-127` cost: a blank cell and an absent fact read the
#: same way once rendered.
ROW_KIND_ACCOUNT = "account"
ROW_KIND_PENDING_JOB = "pending_job"
#: ⚠ **THE THIRD KIND, ADDED 2026-09-20 (`DEF-CUS-5994`)** — the move-in a clerk
#: STARTED and put down. PO, verbatim: *"remove it - it is anyway in the list so
#: we dont need it sepretely - if it is not in list add it"*. Until that day this
#: row lived on a pinned PANEL above the table (`CR-035` amendment 1) and the
#: list below it said, in `STEP_HAS_NO_STORE`'s own words, that a parked draft
#: *"is not a row of this list"*. The ruling settles the placement that
#: amendment left open, and `ROW_KIND_PARKED_MOVE_OUT` on the Move-outs tab is
#: the shape being copied rather than a second answer being designed.
ROW_KIND_PARKED_MOVE_IN = "parked_move_in"


def move_in_jobs_queryset(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
):
    """The pending move-in jobs this tab shows beside the draft accounts.

    ⚠ **THE STATE FILTER IS EXCLUSIVE BETWEEN THE TWO SOURCES, AND THAT IS WHAT
    MAKES ONE `f.state` WORK OVER TWO TABLES.** `pending` is the only state a
    job can be in and it is a state no ACCOUNT can be in, so a clerk picking
    `pending` gets jobs and nothing else, and a clerk picking `waiting`,
    `scheduled` or `due` gets accounts and nothing else. Neither source has to
    know how the other one filters.

    The search legs are the ones a job can actually answer — the applicant's
    name, the request number, and the unit or address the request resolved to.
    `account #` cannot be answered by a row that has no account, and offering it
    silently would be `BR-CUS-099`'s complaint about the transfers box.
    """
    from apps.customers import move_in_jobs, selectors

    state = (filters or {}).get("state")
    rows = move_in_jobs.pending_queryset()
    if state and state != MOVE_IN_STATE_PENDING:
        return rows.none()

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        matches = Q(request__applicant_name__icontains=term)
        matches |= Q(request__request_no__icontains=term)
        unit_ids = [str(unit_id) for unit_id in seams.unit_ids_matching(term)]
        if unit_ids:
            matches |= Q(request__resolved_unit_id__in=unit_ids)
        rows = rows.filter(matches).distinct()
    return rows


def _premise_for_request(request: Any) -> str | None:
    """The job's address — **walked, never stored** (CLAUDE.md hard rule 8).

    Through `selectors._premise_cell`, the module's single reader, so this tab
    prints an address exactly as the account rows above it do. A request that
    resolved to a UNIT gets the unit's line; one that resolved only to a
    premises — which `SR-26-0024` on the demo tenant is — gets the premises'.

    The namespace is the cheap half of using one reader rather than two: that
    function reads `premises_id` off whatever it is handed, and a second
    formatter here would be a second way for one address to be printed.
    """
    from types import SimpleNamespace

    from apps.customers import selectors

    _label, premise = selectors._premise_cell(
        request.resolved_unit_id,
        account=SimpleNamespace(premises_id=request.resolved_premises_id),
    )
    return premise


def move_in_job_row(
    job: Any,
    *,
    as_of: date,
    reads: dict[str, Any],
) -> dict[str, Any]:
    """One pending move-in job, in the SAME eight cells as an account row.

    ⚠ **THE SHAPE IS IDENTICAL AND THE CONTENT IS NOT, WHICH IS THE WHOLE POINT
    OF `row_kind`.** One screen renders both kinds, so every key an account row
    carries is carried here — with a named absence wherever a job genuinely
    cannot answer. A row that simply omitted `deposit` would render as an empty
    cell, and an empty cell and an absent fact are indistinguishable once drawn
    (`DEF-127`).

    ⚠ **NOTHING IS COPIED.** Every value below is read off the REQUEST through
    the link, because that is where it lives — `move_in_jobs` §2.
    """
    from apps.customers import move_in_jobs

    request = job.request
    return {
        # ⚠ **THE JOB'S OWN `MVI-`, SINCE `BR-CUS-1090` (PO 2026-09-22).** This
        # cell served `MOVE_IN_IS_STILL_A_DRAFT` until that ruling, so a column
        # headed `Reference` showed nothing while the row beside it linked back
        # to the SERVICE REQUEST — the application's number standing in for the
        # job's. The number is the job's now, allocated when the clerk approved,
        # and the walk back to the request is still on the row (`request`
        # below) and on the job's own page. `move_no_unavailable` is served
        # beside it for a tenant with no `move_in` series row, which is the same
        # pair every other move surface carries.
        **move_in_job_reference(job),
        "row_kind": ROW_KIND_PENDING_JOB,
        "job_id": str(job.id),
        # ⚠ **`— draft`, AND IT IS THE DRAWING'S OWN CELL** (B18 §5.5.2). The
        # absence rides beside it so a clerk reads WHY rather than a dash.
        "account_id": None,
        "account_no": None,
        "account_absence": dict(PENDING_JOB_HAS_NO_ACCOUNT),
        # The applicant, from the application. Named `request_applicant` in
        # `customer_source` so a reader can tell it from the BR-CUS-054 entity
        # and from the primary-contact fallback — three different facts.
        "customer": request.applicant_name,
        "customer_no": None,
        "customer_source": "request_applicant",
        "customer_absence": None,
        "unit_id": str(request.resolved_unit_id) if request.resolved_unit_id else None,
        "unit": _premise_for_request(request),
        # What the applicant ASKED FOR. It is not a start date anybody has
        # agreed yet — the wizard's step 3 settles that — and a request with
        # none is the ordinary case rather than a blockage.
        "move_in_date": request.requested_start.isoformat() if request.requested_start else None,
        "move_in_date_absence": (
            None
            if request.requested_start
            else {
                "code": "no_requested_start_date",
                "br_ref": "BR-CUS-1077",
                "detail": (
                    "The application named no start date. Unlike a draft account with no start "
                    "date, nothing is blocked by that here: the date is settled in the move-in "
                    "wizard, and it is what the account is opened with."
                ),
            }
        ),
        # ⛔ Unchanged, and NOT closed by this table — `move_in_jobs` §1.
        "step": move_in_step_cell(None, unavailable=dict(STEP_HAS_NO_STORE)),
        "reads": reads,
        "deposit": {
            "currency": None,
            "amount": None,
            "recorded": False,
            "sentence": None,
            "unavailable": [dict(PENDING_JOB_HAS_NO_DEPOSIT)],
        },
        "state": MOVE_IN_STATE_PENDING,
        "starting_this_week": _within_the_week(request.requested_start, as_of),
        # The day the JOB was raised, which is the day the clerk approved. The
        # request is older and its age is the request tab's question.
        "booked_in_on": job.created_at.date().isoformat(),
        "age_days": (as_of - job.created_at.date()).days,
        "request": {
            "id": str(request.id),
            "request_no": request.request_no,
            "waiting_on": request.waiting_on,
            "park_note": request.park_note,
            "state": request.state,
            "requested_start": (
                request.requested_start.isoformat() if request.requested_start else None
            ),
        },
        "request_absence": None,
        # ⚠ **PO ruling 2026-09-16 — the unchecked documents travel WITH the
        # job.** They no longer block the approval, and *not mandatory* is not
        # *not mentioned*: what is still outstanding is read back live through
        # the link and carried into the wizard. `None` means nothing is.
        "documents_outstanding": move_in_jobs.outstanding_documents(request),
    }


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-CUS-5994` — THE THIRD KIND OF ROW: THE PARKED DRAFT (PO 2026-09-20)
# ═══════════════════════════════════════════════════════════════════════════
def _parked_by_name(park: Any) -> str | None:
    """Whose desk a draft is on — ONE reader, for both flows' park rows.

    ⚠ **IT IS NOT DECORATION: IT IS WHAT REPLACED THE MINE / EVERYONE'S
    TOGGLE.** `CR-035` amendment 1 dissolved that filter — *"it meant THERE AND
    NOWHERE ELSE"* — and the panel's `Parked by` line is what answered the
    question instead, for a clerk covering somebody else's desk. The panel is
    gone (`DEF-CUS-5994`), so the line comes onto the row rather than out of the
    product; dropping it would silently re-open a question that was closed.

    Free of a query: `wizard_parks.parks_queryset` already `select_related`s
    `parked_by` for `row_dict`'s sake, and this reads it exactly as that
    function does rather than spelling the fallback a second way.
    """
    if not getattr(park, "parked_by_id", None):
        return None
    return (getattr(park.parked_by, "full_name", "") or None)


def move_in_parks_queryset(*, q: str | None = None, filters: dict[str, Any] | None = None):
    """The move-ins a clerk started and put down — `wizard_parks`.

    ⚠ **THE WINDOW, NOT A COLUMN — and the Move-outs tab already proved it.**
    `move_out_parks_queryset` is this function one flow over, written on
    2026-09-19; today's ruling extends it rather than inventing a second answer
    (PO: *"if it is not in list add it"*). Everything below that could have been
    re-derived is quoted from there instead.

    ⚠ **READ THROUGH THE SEAM, NEVER THE TABLE.** `wizard_parks` is
    TENANCY-hosted and customers may not import `apps.tenancy.models` (B1 /
    BR-TEN-013; G6 rule 4 refuses it). `seams.wizard_park_queryset` forwards to
    the owning module's own `parks_queryset`, which carries the tenant filter
    under RLS `FORCE` — hard rule 1 applied where the queryset is BUILT.

    ⚠ **`f.state` IS EXCLUSIVE ACROSS ALL THREE SOURCES, WHICH IS WHAT LETS ONE
    FILTER WORK OVER THREE TABLES.** `move_ins_queryset` answers `waiting`,
    `scheduled` and `due`; `move_in_jobs_queryset` answers `pending`; this one
    answers `in_progress` and `parked` and nothing else. No source has to know
    how the other two filter, and every source returns NONE rather than
    EVERYTHING for a value it does not own — BR-SHL-011's rule that falling back
    to "no filter" would silently show a clerk more than they asked for.

    ⚠ **THE SEARCH LEGS ARE NARROWER AND THE RESPONSE SAYS SO**
    (`PARKED_MOVE_IN_SEARCH_LEGS_ARE_NARROWER`). A draft copies ids and joins to
    nothing, so the account-number, customer and request legs cannot reach it.
    What it can answer is the label it was parked under — for a move-in, the
    unit the clerk picked.
    """
    from apps.customers import selectors

    rows = seams.wizard_park_queryset(flow=moves.KIND_MOVE_IN)

    state = (filters or {}).get("state")
    if state and state not in (MOVE_IN_STATE_IN_PROGRESS, MOVE_IN_STATE_PARKED):
        return rows.none()
    if state == MOVE_IN_STATE_IN_PROGRESS:
        rows = rows.filter(waiting_on="")
    elif state == MOVE_IN_STATE_PARKED:
        rows = rows.exclude(waiting_on="")

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        rows = rows.filter(subject_label__icontains=term)
    return rows


def move_in_park_state(park: Any) -> str:
    """`in_progress` or `parked` — told apart by ONE column, as move-outs are.

    `WizardPark.waiting_on`'s own docstring is where the distinction is kept:
    *"EMPTY MEANS *A DRAFT*, NOT *A PARK WITH NO REASON*"*. `move_out_park_state`
    reads the same column the same way, and **the draft deliberately got no flag
    of its own**: two columns that must agree are two columns free to disagree.
    """
    return (
        MOVE_IN_STATE_PARKED
        if (park.waiting_on or "").strip()
        else MOVE_IN_STATE_IN_PROGRESS
    )


def move_in_park_row(park: Any, *, as_of: date, reads: dict[str, Any]) -> dict[str, Any]:
    """One UNFINISHED move-in, in the SAME nine cells as an account row.

    ⚠ **THE SHAPE IS IDENTICAL AND THE CONTENT IS NOT, WHICH IS WHAT `row_kind`
    IS FOR** — `move_in_job_row`'s note, unchanged and for the same reason: one
    screen renders three kinds now, so every key the other two carry is carried
    here, with a NAMED absence wherever a draft genuinely cannot answer. A row
    that simply omitted `deposit` would render as an empty cell, and an empty
    cell and an absent fact are indistinguishable once drawn (`DEF-127`).

    ⚠ **THE STEP IS REAL, AND SERVING IT IS THE IMPROVEMENT THIS RULING BUYS.**
    `MoveStepBar`'s docstring is explicit that `reached` is the SERVER's answer
    and the component never derives one, drawing empty with a reason wherever it
    is null. A parked draft HAS a step — `wizard_parks.step`, the same number
    the wizard's own rail counts off `MOVE_IN_STEPS` — so it is served, and
    `STEP_HAS_NO_STORE` goes on riding beside the account and job rows, which
    genuinely have none. **Two answers on one list, each true of its own row**,
    which is the posture the Move-outs tab took on 2026-09-19.

    ⚠ **A MOVE-IN DRAFT NAMES A UNIT AND NOT AN ACCOUNT**, which is the one
    place `move_out_park_row` does not carry over — see
    `PARKED_MOVE_IN_HAS_NO_ACCOUNT`. The UNIT is walked to its premises for the
    address (CLAUDE.md hard rule 8: an address is stored on `premises` and
    derived everywhere else), and the parked LABEL answers only where the unit
    link cannot.
    """
    subject = park.subject_ref if isinstance(park.subject_ref, dict) else {}
    values = park.values if isinstance(park.values, dict) else {}
    unit_id = subject.get("unit_id") or None
    # ⚠ WHAT WAS TYPED, NOT WHAT WAS AGREED. BR-SHL-048 (b): a park holds a draft
    # of a FORM and every field is re-validated at execution. It is rendered
    # because a clerk needs to know which week they were working towards; it
    # commits nothing, and the STATE beside it is what says so.
    intended = (values.get("opened_at") or "").strip() or None
    parked_reference = (park.reference or "").strip() or None
    unit_line = _premise(unit_id) if unit_id else None
    return {
        # `MVI-{YY}-{0000}` off the draft's own column — the SAME series the
        # finished record is filed under, so the number a clerk quotes down a
        # phone while the job is in their hands is the number it keeps
        # (`wizard_parks._allocate_draft_reference`).
        "move_no": parked_reference,
        "move_no_unavailable": (
            None if parked_reference else dict(MOVE_IN_IS_STILL_A_DRAFT)
        ),
        "row_kind": ROW_KIND_PARKED_MOVE_IN,
        # The handle RESUME is built from — `?parked=<id>`. It is the draft's own
        # id and nothing prints it, so B14 rule 31 is not in play.
        "park_id": str(park.id),
        "account_id": None,
        "account_no": None,
        "account_absence": dict(PARKED_MOVE_IN_HAS_NO_ACCOUNT),
        # ⛔ NO CUSTOMER ENTITY. `values["customer"]` is a block being TYPED into
        # the wizard's step 2; naming it here would print a customer this product
        # has not created and cannot be searched for. The label the clerk parked
        # under is served instead, named as its own source so a reader can tell
        # the two apart (`move_out_park_row` takes the same posture).
        "customer": None,
        "customer_no": None,
        "customer_source": None,
        "customer_absence": {
            "code": "parked_move_in_customer_is_still_being_typed",
            "br_ref": "BR-SHL-048 · BR-CUS-054",
            "detail": (
                "The customer is keyed into the move-in wizard and created when the job is "
                "run. A draft holds what was typed and has created nobody, so there is no "
                "customer record to name or to search for yet."
            ),
        },
        "unit_id": str(unit_id) if unit_id else None,
        # Hard rule 8 — WALKED to the premises, never a stored address. The
        # parked label is the fallback and it is deliberately stale: it is what
        # the clerk saw when they put the job down.
        "unit": unit_line or (park.subject_label or None),
        "move_in_date": intended,
        "move_in_date_absence": (
            None
            if intended
            else {
                "code": "parked_move_in_date_not_chosen_yet",
                "br_ref": "BR-SHL-048",
                "detail": (
                    "The start date is asked for on the move-in wizard's third step and this "
                    "draft was parked before it. Nothing was lost: a parked draft holds what "
                    "was typed and touches no records, so the date is chosen when it is "
                    "picked back up."
                ),
            }
        ),
        # ✅ A REAL NUMERATOR. `of` is `MOVE_IN_STEP_COUNT`'s SIX — the same
        # denominator the account rows carry and the same one `MOVE_IN_STEPS`
        # gives the wizard's rail (BR-SHL-046).
        # `CR-171` P1.03 — the FOUR-step number, mapped from a seven-step draft.
        "step": move_in_step_cell(move_in_park_step(park)),
        "reads": reads,
        "deposit": {
            "currency": None,
            "amount": None,
            "recorded": False,
            "sentence": None,
            "unavailable": [dict(PARKED_MOVE_IN_HAS_NO_DEPOSIT)],
        },
        "state": move_in_park_state(park),
        # Measured against the date the clerk typed, which is the only date this
        # row has. A draft with none is not "starting this week" — it is not
        # starting on any day yet, and `False` says so without inventing one.
        "starting_this_week": _within_the_week(
            date.fromisoformat(intended) if intended else None, as_of
        ),
        "booked_in_on": park.created_at.date().isoformat(),
        "age_days": (as_of - park.created_at.date()).days,
        # ⛔ NO REQUEST. A draft may have been started from one and the link is
        # not stored on the park, so claiming either way would be a guess.
        "request": None,
        "request_absence": {
            "code": "parked_move_in_has_no_request_link",
            "br_ref": "BR-SHL-048 (a) · BR-CUS-080",
            "detail": (
                "A draft joins to nothing, so whether this move-in came from an application "
                "is not recorded on it. The link is written when the move-in is run and the "
                "record is created."
            ),
        },
        # The wizard re-reads the outstanding documents when the draft is picked
        # back up; nothing is stored on the park, so nothing is claimed here.
        "documents_outstanding": None,
        # ⚠ **THE PARKED FACTS THE PANEL USED TO CARRY — FLAT, AND IN THE SAME
        # SPELLING `move_out_park_row` ALREADY USES (`DEF-CUS-5994`).** Each was
        # on screen before this ruling and each is a fact about the DRAFT rather
        # than about a move-in: why it stopped, the clerk's own note, the date
        # they asked to be reminded on, and whose desk it is. Removing a surface
        # must not remove what was on it.
        "waiting_on": park.waiting_on or None,
        "park_note": park.park_note or None,
        "remind_on": park.remind_on.isoformat() if park.remind_on else None,
        "parked_at": park.parked_at.isoformat() if park.parked_at else None,
        "parked_by_name": _parked_by_name(park),
    }


def move_in_kpis(*, as_of: date | None = None) -> dict[str, Any]:
    """B18 §5.5.1's five tiles — three derived, one derived-with-a-caveat, one
    served as an absence.

    | Tile | Caption | This product |
    |---|---|---|
    | `OPEN` | *taking over live service* | the window (§1) ✔ |
    | `STARTING THIS WEEK` | *within 7 days of today* | `opened_at` in the window ✔ |
    | `WAITING ON DOCUMENTS` | *nothing moves until they arrive* | ⚠ counted as *waiting on ANYTHING* — see below |
    | `DEPOSITS TO CARRY OVER` | *money moving from a closed account* | ⛔ absence — no election column |
    | `OLDEST` | *Alvarez, Rosa · started Aug 17* | days since `created_at` ✔, `null` when there are none |

    ⚠ **`WAITING ON DOCUMENTS` COUNTS A WIDER SET THAN IT IS DRAWN AS, AND SAYS
    SO.** `service_requests.waiting_on` is free TEXT with no vocabulary — the
    request module's own KPI strip calls the equivalent tile
    `waiting_on_customer` for exactly this reason, and the model's docstring
    contrasts *"waiting on a scheduled date"* with *"waiting on payment"* as two
    values of one free-text column. So the count served is *requests waiting on
    anything*, `drawn_as` names what B18 asked for, and the difference rides in
    `unavailable`. A narrower count would need a vocabulary nobody has ruled.

    ⚠ **`OLDEST` IS `null` WHEN THERE ARE NONE, NEVER `0`** — the
    `ConnectionKpis.oldest` precedent: *"0 days" is a different claim from
    "there is none"*.
    """
    on = _as_of(as_of)
    rows = list(move_ins_queryset())
    # `BR-CUS-1077` — the pending jobs count too. `OPEN` is *"taking over live
    # service"* and an approved move-in nobody has started is exactly that; a
    # tile that counted only the accounts would say five while the list under it
    # showed six, which is the kind of disagreement a clerk reports as a bug in
    # the number rather than as a missing feature.
    jobs = list(move_in_jobs_queryset().select_related("request"))
    account_nos = [row.account_no for row in rows]
    requests = _requests_by_account_no(
        account_nos, outcome=models.ServiceRequest.OUTCOME_MOVE_IN
    )
    waiting = sum(
        1
        for row in rows
        if (requests.get(row.account_no) or {}).get("waiting_on") not in (None, "")
    )
    # A pending job's request is right there on the row, so this half needs no
    # `outcome_ref` match at all — the link is an id.
    waiting += sum(1 for job in jobs if (job.request.waiting_on or "") != "")
    reading = _waiting_on_a_reading(rows, jobs)
    oldest_row = max(rows, key=lambda row: (on - row.created_at.date()).days, default=None)
    oldest_job = max(jobs, key=lambda job: (on - job.created_at.date()).days, default=None)
    customers = _customer_names([row.id for row in rows]) if oldest_row else {}
    # ⚠ **`OLDEST` IS THE OLDEST OF BOTH KINDS.** Two candidates, compared on the
    # one measure the tile draws — days since the row was booked in — and the
    # ACCOUNT wins a tie, because it is the row with a number a clerk can quote.
    oldest = None
    if oldest_row is not None:
        oldest = {
            "days": (on - oldest_row.created_at.date()).days,
            "account_no": oldest_row.account_no,
            "customer": (customers.get(str(oldest_row.id)) or {}).get("customer"),
            "booked_in_on": oldest_row.created_at.date().isoformat(),
            "row_kind": ROW_KIND_ACCOUNT,
        }
    if oldest_job is not None:
        job_days = (on - oldest_job.created_at.date()).days
        if oldest is None or job_days > oldest["days"]:
            oldest = {
                "days": job_days,
                # ⛔ No account number: the tile draws one and a pending job has
                # none. The REQUEST number is what a clerk quotes for this row.
                "account_no": None,
                "request_no": oldest_job.request.request_no,
                "customer": oldest_job.request.applicant_name,
                "booked_in_on": oldest_job.created_at.date().isoformat(),
                "row_kind": ROW_KIND_PENDING_JOB,
            }
    return {
        "open": len(rows) + len(jobs),
        # The two halves read two different dates for the same question — an
        # account's agreed `opened_at` and a job's REQUESTED start — and both
        # are what *"starting this week"* means for that kind of row.
        "starting_this_week": (
            sum(1 for row in rows if _within_the_week(row.opened_at, on))
            + sum(1 for job in jobs if _within_the_week(job.request.requested_start, on))
        ),
        "waiting_on": {
            "count": waiting,
            "drawn_as": "documents",
            "unavailable": [
                {
                    "code": "waiting_on_has_no_vocabulary",
                    "br_ref": "BR-CUS-080",
                    "detail": (
                        "B18 §5.5.1 draws this tile as `WAITING ON DOCUMENTS`. "
                        "`service_requests.waiting_on` is free text with no vocabulary — the "
                        "same column holds *\"a scheduled date\"* and *\"payment\"* — so this "
                        "counts move-ins whose request is waiting on ANYTHING. Narrowing it "
                        "to documents would need a vocabulary no rule states."
                    ),
                }
            ],
        },
        # ⚠ **p077's THIRD TILE, PO-APPROVED 2026-09-19** (p073 before the blueprint
        # was replaced the same day).** A different question
        # from `waiting_on` above, not a rewording of it — see
        # `_waiting_on_a_reading`. Both are served: the drawing shows three
        # tiles and the SCREEN draws three, while an established count that
        # cost nothing to keep stays on the payload for whatever asks next.
        "waiting_on_a_reading": reading,
        # ⛔ No election column exists — see the absence's own sentence.
        #
        # ⚠ **STILL SERVED, AND NO LONGER DRAWN.** The PO dropped `DEPOSITS TO
        # CARRY OVER` and `OLDEST` from the strip on 2026-09-19 (*"this si all
        # good - please update it"* over a table that says `drop` for both).
        # They are left on the payload deliberately: removing a served key is a
        # contract change that would break any other reader, and the screen
        # deciding not to DRAW something is not the server deciding not to KNOW
        # it. `MoveInsTab.moveInsKpis` is where the three tiles are chosen.
        "deposits_to_carry_over": None,
        "deposits_to_carry_over_unavailable": dict(DEPOSIT_CARRY_ELECTION_HAS_NO_COLUMN),
        "oldest": oldest,
        # No rule states which clock a KPI window reads; the basis is served as
        # DATA rather than picked silently (the `service_request_reads` posture).
        "period_basis": "tenant_today",
        "as_of": on.isoformat(),
    }


#: The union's own column names, one per `MOVE_IN_SORTS` key. ⚠ **A SECOND MAP
#: AND NOT A SECOND OPINION:** the keys are exactly `MOVE_IN_SORTS`'s, so a sort
#: the screen may ask for is a sort both halves can answer, and a test asserts
#: the two maps have the same keys. What differs is only the COLUMN NAME a
#: `UNION` can be ordered by, which is not the same string as a model field on
#: either side.
MOVE_IN_UNION_SORTS: dict[str, tuple[Any, ...]] = {
    "created": ("created_at", "id"),
    "move_in_date": ("move_in_on", "id"),
    "account": ("account_no", "id"),
}


def move_ins_list(
    *,
    q: str | None = None,
    page: int = 1,
    per: int = DEFAULT_PER,
    as_of: date | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    dir: str = MOVE_DEFAULT_DIR,
) -> dict[str, Any]:
    """The Move-ins tab — **forwarded to `move_in_list.move_ins_list` since
    2026-10-05 (`CR-171-BRC10` P1.04)**, which serves every status a move-in
    can be in (requests, drafts, jobs, committed, cancelled — CR §6.1) over one
    SQL union. The three-kind union that lived here (`_move_in_page_keys`,
    `_fetch_move_in_page`) is its first three arms now; one list, one door.
    The row builders above (`move_in_row`, `move_in_job_row`,
    `move_in_park_row`) are still the ones those three arms render through.
    """
    from apps.customers import move_in_list

    return move_in_list.move_ins_list(
        q=q, page=page, per=per, as_of=as_of, filters=filters, sort=sort, dir=dir
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE MOVE-OUTS LIST (B18 §5.6)
# ═══════════════════════════════════════════════════════════════════════════
def move_out_settlement_cell(
    account: models.Account, *, outstanding: Any, outstanding_gaps: tuple[dict[str, Any], ...]
) -> dict[str, Any]:
    """§5.6.2's SETTLEMENT column — the FIGURES that can be read, and NO verdict.

    ════════════════════════════════════════════════════════════════════════
    6 · WHY THIS CELL STATES NO LANDING, EVER, ON THIS TAB
    ════════════════════════════════════════════════════════════════════════
    B18 draws five outcomes here — `refunded $88.40` · `refund $11.20` ·
    `settles exactly` · **`SHORT $175.20`** · `—` — and each is a LANDING from
    `move_out_settlement.MONEY_LANDINGS`. `MoveOutSettlement.landing` is
    explicit about what decides one:

    > *"any gap → **no landing**. Not a sixth outcome: a missing deposit
    > interest understates `applied`, biasing the answer toward `short`; a
    > missing final bill understates `outstanding`, biasing it toward
    > `refund_due`. **One of those two directions posts a cheque.**"*

    **Both gaps are open on every row of this tab.** The final bill is stated by
    a CALLER and billing publishes none (`FINAL_BILL_NOT_STATED`); BR-CUS-057's
    interest accrual is confirmed and unbuilt (`DEPOSIT_INTEREST_NOT_ACCRUED`).
    So no landing can be stated for any account, and `landing: None` here is the
    engine's own answer rather than a shortcut taken to keep a list cheap.

    ⚠ **AND NO COMPOSED TOTAL IS SERVED EITHER.** It would be easy to call
    `move_out_settlement.derive()` per row and publish its `applied` and
    `outstanding` columns; that is refused, because those totals sum terms this
    list did not read — the unapplied credit, the unbanked export credit, the
    sibling positions and the open disputes are four per-row queries
    (`SETTLEMENT_TERMS_NOT_READ_ON_A_LIST`). A total built from a subset is a
    figure a clerk would act on and nobody derived. What is served is the two
    TERMS this list genuinely read, each labelled, and the whole settlement is
    one click away on `GET /accounts/{id}/close-impact`.

    ⚠ **THE OUTSTANDING FIGURE IS THE LEDGER'S, NEVER `accounts.balance`**
    (BR-CUS-015 · DEF-127). `None` means the books could not be asked and the
    screen renders the reason; it never renders `0.00`, which on this column
    would read as *this customer is square and owed nothing back*.
    """
    held = account.deposit_on_file or move_out_settlement.ZERO
    unavailable = [
        dict(FINAL_BILL_NOT_STATED),
        dict(DEPOSIT_INTEREST_NOT_ACCRUED),
        dict(SETTLEMENT_TERMS_NOT_READ_ON_A_LIST),
    ]
    unavailable.extend(dict(gap) for gap in outstanding_gaps)
    return {
        "currency": account.currency,
        # ⛔ THE VERDICT, WITHHELD BY THE ENGINE'S OWN RULE — see §6 above.
        "landing": None,
        "landings": list(move_out_settlement.MONEY_LANDINGS),
        "complete": False,
        "sentence": None,
        # The two terms this list really read, each named.
        "deposit_held": move_out_settlement._pair(held),
        "deposit_interest": None,
        "outstanding": move_out_settlement._pair(outstanding),
        "outstanding_source": "ledger" if outstanding is not None else None,
        "unavailable": unavailable,
    }


def move_out_row(
    account: models.Account,
    *,
    as_of: date,
    customer: dict[str, Any] | None,
    settlement: dict[str, Any],
    final_read: dict[str, Any],
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One §5.6.2 row for a move-out that HAS happened: `ACCOUNT · CUSTOMER ·
    UNIT · MOVE-OUT DATE · STEP (of 6) · FINAL READ · SETTLEMENT · STATE`.

    ⚠ **`state` IS `closed` ON EVERY ROW THIS FUNCTION BUILDS, AND IT IS NO
    LONGER THE ONLY VALUE THE COLUMN CAN TAKE** (PO ruling 2026-09-19 — *"yes"*,
    the list shows the unfinished ones too). This sentence read *"the ONLY value
    this column can take"* until that day. The unfinished rows come from
    `move_out_park_row` and carry `in_progress` or `waiting`; `MOVE_OUT_STATES`
    now marks three of B18's four segments supported and `scheduled` is the one
    that stays false, because a move-out nobody has started writes nothing.

    ⚠ **THE STEP STAYS AN ABSENCE HERE, AND THAT IS NOT AN OVERSIGHT.** A
    PARKED move-out carries a real step and prints it; a CLOSED one cannot, and
    must not be derived. **Four code paths write `accounts.closed_at` and only
    one is the wizard** — `services.move_out`, against the disconnect close-out,
    the account import and the import rollback — so `6 of 6` on the other three
    would claim a clerk walked six steps they never saw. A step where one is
    stored, an absence where none is.
    """
    return {
        # CR-039 wave D 17–19 — the leading `reference` cell, from the caller's
        # ONE query over the page. `drafted` is FALSE here: every row on this
        # list is a CLOSED account, so the job definitely happened and the only
        # honest absences left are "it predates the record" and "no series row".
        **(reference or move_reference_cell(None)),
        # PO ruling 2026-09-19 — WHICH KIND OF ROW THIS IS. Served on every row
        # rather than inferred from an absent field, the `BR-CUS-1077` posture:
        # an inference is a second implementation of a rule, and this one is the
        # difference between *a move-out that happened* and *one still in a
        # clerk's hands*.
        "row_kind": ROW_KIND_ACCOUNT,
        # The keys the PARKED rows carry, served `None` here so one screen reads
        # one shape. A key that exists on half the rows is a key every reader
        # has to guard, and the guard is where two readers differ.
        "park_id": None,
        "waiting_on": None,
        "park_note": None,
        "remind_on": None,
        "parked_at": None,
        "age_days": None,
        "account_id": str(account.id),
        "account_no": account.account_no,
        # ⚠ NEVER absent on a closed row: the account IS the row.
        "account_absence": None,
        "customer": (customer or {}).get("customer"),
        "customer_no": (customer or {}).get("customer_no"),
        "customer_source": (customer or {}).get("source"),
        "customer_absence": (
            None
            if customer
            else {
                "code": "account_has_no_customer_link",
                "br_ref": "BR-CUS-054",
                "detail": (
                    "no `customer_accounts` link and no primary contact on this account — a "
                    "real answer, not a gap."
                ),
            }
        ),
        "unit_id": str(account.unit_id),
        # BR-MET-036 — the unit derived back to Vacant when this account closed,
        # because the terminal class does not occupy. Stated because §5.6.5's
        # impact panel is drawn around it.
        "unit": _premise(account.unit_id),
        # `services.move_out`: *"`closed_at` = the move-out date"*. This IS the
        # move-out date; there is no second column.
        "move_out_date": account.closed_at.isoformat() if account.closed_at else None,
        # ⚠ Served for envelope parity with a parked row, and `None` here by
        # construction: `move_outs_queryset` filters `closed_at__isnull=False`.
        "move_out_date_absence": None,
        # ⛔ §4 row 1, and the denominator is BR-SHL-046's SIX and not B18's
        # superseded four — carried so a screen cannot reintroduce `of 4`.
        "step": {
            "reached": None,
            "of": MOVE_OUT_STEP_COUNT,
            # ⛔ ITS OWN REASON, NOT THE MOVE-INS TAB'S — see the constant.
            "unavailable": dict(CLOSED_MOVE_OUT_HAS_NO_STEP),
        },
        # §5.6.2's FINAL READ — `taken`/`due` derived through the seam against
        # THIS row's `closed_at`; `estimated` off the settlement's own stored
        # flag (`accounts.final_read_state`, W9 task 4 — TC-MVO-7's absence
        # CLOSED). A flagless close carries `final_read_state_not_recorded`.
        "final_read": final_read,
        "settlement": settlement,
        "state": MOVE_OUT_STATE_CLOSED,
        "leaving_this_week": _within_the_week(account.closed_at, as_of),
    }


def move_outs_queryset(
    *,
    q: str | None = None,
    filters: dict[str, Any] | None = None,
    as_of: date | None = None,
    sort: str | None = None,
    dir: str = MOVE_DEFAULT_DIR,
):
    """§2's window, with §5.6.2's search legs and §5.7.3's exclusion.

    ⚠⚠ **THE PARAGRAPH BELOW IS THE REASON THIS EXCLUSION WAS BUILT, AND IT
    STOPPED BEING TRUE ON 2026-09-01 (`DEF-CUS-5913`).** It read:

        *"THE EXCLUSION IS LOAD-BEARING HERE AND NOT MERELY REQUIRED.
        `transfers.commit_transfer` runs its outgoing half through
        `services.move_out` — the signed BR-CUS-030 path, not a copy of it — so
        every committed transfer writes a `closed_at` and a terminal status and
        would appear on this list as a move-out."*

    **`commit_transfer` NO LONGER EXISTS.** `BR-CUS-1030` (PO ruling
    2026-09-01, verbatim: *"dont create new account - we reassing that account
    - bascailly I have sold my property"*) replaced it with
    `transfers.reassign_account`, which **closes nothing**: the same account
    keeps its number, its unit and its ledger and changes CUSTOMER. A transfer
    therefore writes no `closed_at` at all, so no transfer half can reach this
    window in the first place and the sentence above describes a product that
    stopped existing eighteen days ago.

    ⚠ **THE CALL IS KEPT, AND NOT BECAUSE IT IS HARMLESS.** Two reasons, and
    only the first is comfortable: transfers committed BEFORE that ruling did
    close their outgoing half, those rows are real, and §5.7.3's counting
    contract still covers them. The second is `DEF-CUS-5913`:
    `transfer_half_account_ids()` names every non-cancelled transfer's
    `from_account_id` **forever**, so an account that was SOLD in March and
    then genuinely moved out in September is subtracted from this list by a
    predicate written for a flow that no longer closes anything — a real
    move-out that no screen shows. Changing the contract is a ruling and not a
    tidy-up, so it is FILED rather than fixed here.
    """
    from apps.customers import selectors

    rows = models.Account.objects.filter(
        tenant_id=_tenant_id(),
        closed_at__isnull=False,
        # BR-CUS-055 / BR-MET-036 — the terminal CLASS, never the label.
        status__behavior_class=services.CLASS_TERMINAL,
    ).select_related("status")
    rows = transfers.exclude_transfer_halves(rows, field="id")

    # ── CR-045 wave D task D.10 · `f.closed`, APPLIED IN SQL (DEF-1702) ────
    # The window is INCLUSIVE of today and counts back `n` days, so `last7` on
    # 2026-08-27 is 2026-08-21..2026-08-27 — seven dates, not eight. It is
    # anchored on the AS-OF date and never on a wall clock (BR-TEN-043).
    window = (filters or {}).get("closed")
    if window:
        days = MOVE_OUT_CLOSED_WINDOWS.get(str(window))
        if days is None:
            rows = rows.none()  # a value we do not serve shows NOTHING, never all
        else:
            on = _as_of(as_of)
            rows = rows.filter(closed_at__gte=on - timedelta(days=days - 1), closed_at__lte=on)

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        matches = Q(account_no__icontains=term)
        matches |= Q(customeraccount__customer__display_name__icontains=term)
        matches |= Q(customeraccount__customer__customer_no__icontains=term)
        matches |= Q(contact__full_name__icontains=term, contact__deleted_at__isnull=True)
        unit_ids = [str(unit_id) for unit_id in seams.unit_ids_matching(term)]
        if unit_ids:
            matches |= Q(unit_id__in=unit_ids)
        # ── `DEF-CUS-5896` · THE REFERENCE LEG (PO-approved 2026-09-19) ──────
        # The first column of this table, and the box could not answer it.
        # `account_ids_for_move_reference` carries the tenant filter, the
        # `kind` filter and the reason for each; see its docstring.
        reference_ids = account_ids_for_move_reference(term, kind=moves.KIND_MOVE_OUT)
        if reference_ids:
            matches |= Q(id__in=reference_ids)
        # ⛔ NO `request #` LEG — see `MOVE_OUT_REQUEST_LEG_UNLINKED`. A move-out
        # creates no child, so nothing was ever written to match against.
        rows = rows.filter(matches).distinct()
    # `BR-CUS-1046` / `DEF-CUS-5060` — §5.6.2's footnote *"Sorted by move-out
    # date, soonest first"* is now `sort="move_out_date"`, one click that
    # survives a refresh, and the default is the creation order. The tiebreak is
    # `id` for the reason the move-ins queryset above spells out.
    return rows.order_by(
        *pagination.order_terms(sort, dir, columns=MOVE_OUT_SORTS, default=MOVE_OUT_DEFAULT_SORT)
    )


# ═══════════════════════════════════════════════════════════════════════════
# A MOVE-OUT WHOSE ACCOUNT WAS REOPENED SINCE (`DEF-CUS-10125`)
# ═══════════════════════════════════════════════════════════════════════════
#: The row kind for a move-out that HAPPENED on an account a later move-in
#: reopened (CR-181-BRC10). It renders as a finished move-out — `state` is
#: `closed` — and is named so a reader can tell it from the account's CURRENT
#: close, which the account row itself still answers.
ROW_KIND_REOPENED_MOVE_OUT = "reopened_move_out"

#: Why the settlement figures are withheld on that row: the account is live
#: again, so its deposit and its books describe the NEW tenancy, not the one
#: this row ended. Printing them here would put today's balance beside a
#: move-out months old.
REOPENED_SETTLEMENT_IS_THE_NEW_TENANCYS = {
    "code": "account_reopened_since_this_move_out",
    "br_ref": "CR-181-BRC10",
    "detail": (
        "the account was reopened by a later move-in, so its deposit and balance now "
        "belong to the new tenancy; what it owed at the reopen is on the move-in."
    ),
}


def reopened_move_outs_queryset(
    *, q: str | None = None, filters: dict[str, Any] | None = None, as_of: date | None = None
):
    """The move-outs a later move-in REOPENED the account over — read from the
    record of that move-out, never from the account row (`DEF-CUS-10125`).

    ⚠ **WHY THIS IS NOT `move_outs_queryset`.** That window is *an account
    whose `closed_at` is set*, which was a complete answer while a close was
    write-once. `CR-181-BRC10` made an account reopenable at move-in: the reopen
    clears `closed_at`, so the earlier move-out simply left the list, though it
    happened and its record is on file. The record of THAT close is the
    `move_in_reopenings` row the reopen wrote — `previous_closed_at` is the date
    the tenancy ended, written once and never updated (`BR-CUS-152`'s posture)
    — so each such row is one finished move-out here, dated by it.

    ⚠ **WHY THE REOPENING AND NOT `move_records` ALONE.** Four code paths close
    an account and only the wizard writes a `move_out` record (this module's
    own note on `STEP_HAS_NO_STORE`); every reopen, whichever path closed the
    account, writes this row. The move-out RECORD is still the reference
    cell's source where one exists (`_reopened_reference_cells`).

    ⚠ **A CANCELLED REOPEN IS NOT A SECOND ROW.** Cancelling a move-in that
    reopened an account gives the account back this very close
    (`move_in_cancel.record_is_cancelled`, `DEF-CUS-10126`) — the account arm
    then shows it, so this arm drops it: closed BEFORE the move-in's own day.

    The same search legs, the same `f.closed` window and the same transfer
    exclusion as the account arm, each read through the reopened account.
    """
    from apps.customers import selectors
    from apps.customers.move_in_reopen_models import MoveInReopening

    rows = MoveInReopening.objects.filter(tenant_id=_tenant_id()).exclude(
        account__closed_at__lt=F("move_record__effective_on")
    )
    rows = transfers.exclude_transfer_halves(rows, field="account_id")

    window = (filters or {}).get("closed")
    if window:
        days = MOVE_OUT_CLOSED_WINDOWS.get(str(window))
        if days is None:
            rows = rows.none()
        else:
            on = _as_of(as_of)
            rows = rows.filter(
                previous_closed_at__gte=on - timedelta(days=days - 1), previous_closed_at__lte=on
            )

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        matches = Q(account__account_no__icontains=term)
        matches |= Q(account__customeraccount__customer__display_name__icontains=term)
        matches |= Q(account__customeraccount__customer__customer_no__icontains=term)
        matches |= Q(
            account__contact__full_name__icontains=term, account__contact__deleted_at__isnull=True
        )
        unit_ids = [str(unit_id) for unit_id in seams.unit_ids_matching(term)]
        if unit_ids:
            matches |= Q(account__unit_id__in=unit_ids)
        reference_ids = account_ids_for_move_reference(term, kind=moves.KIND_MOVE_OUT)
        if reference_ids:
            matches |= Q(account_id__in=reference_ids)
        rows = rows.filter(matches).distinct()
    return rows


def _reopened_reference_cells(reopenings: list[Any]) -> dict[str, dict[str, Any]]:
    """The move-out RECORD each reopened row ended with — ONE query for the
    page. The record dated on the reopening's `previous_closed_at`, else the
    newest move-out record on or before it; none is `move_predates_the_record`,
    the cell every closed row without one already states."""
    if not reopenings:
        return {}
    records = moves.MoveRecord.objects.filter(
        tenant_id=_tenant_id(),
        kind=moves.KIND_MOVE_OUT,
        account_id__in=[row.account_id for row in reopenings],
    ).order_by("-effective_on", "-performed_at", "-created_at")
    by_account: dict[str, list[Any]] = {}
    for record in records:
        by_account.setdefault(str(record.account_id), []).append(record)
    out: dict[str, dict[str, Any]] = {}
    for row in reopenings:
        chosen = next(
            (
                record
                for record in by_account.get(str(row.account_id), [])
                if record.effective_on <= row.previous_closed_at
            ),
            None,
        )
        out[str(row.id)] = move_reference_cell(moves.serialize(chosen) if chosen else None)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# THE UNFINISHED HALF OF THE LIST (PO ruling 2026-09-19 — *"yes"*)
# ═══════════════════════════════════════════════════════════════════════════
#: The second kind of row this list holds. The `ROW_KIND_PENDING_JOB` posture on
#: the Move-ins tab: served on EVERY row rather than inferred from an absent
#: field, because an inference is a second implementation of a rule.
ROW_KIND_PARKED_MOVE_OUT = "parked_move_out"


def move_out_parks_queryset(*, q: str | None = None, filters: dict[str, Any] | None = None):
    """The move-outs a clerk has started and not finished — `wizard_parks`.

    ⚠ **THIS IS A WINDOW, NOT A MISSING COLUMN, AND THAT IS THE WHOLE RULING**
    (PO 2026-09-19, verbatim: **`yes`**, asked whether the Move-outs list should
    show move-outs that have not finished yet). Until that day this file said a
    move-out before its close *"is not recorded anywhere"* — false since
    `CR-035`. `wizard_parks` carries `flow`, `step`, `subject_ref`, `values` and
    `waiting_on` for all five flows INCLUDING `move_out`, and
    `move_record_reads._in_flight` already serves such a row with a real step
    number. The list could not see them because its window was closed accounts,
    not because the data was absent.

    ⚠ **READ THROUGH THE SEAM, NEVER THE TABLE.** `wizard_parks` is
    TENANCY-hosted and customers may not import `apps.tenancy.models` (B1 /
    BR-TEN-013; G6 rule 4 refuses it). `seams.wizard_park_queryset` forwards to
    the owning module's own `parks_queryset`, which carries the tenant filter
    under RLS `FORCE` — hard rule 1 applied where the queryset is BUILT.

    ⚠ **`f.closed` EXCLUDES EVERY DRAFT, AND IT HAS TO.** That filter is a
    window on `accounts.closed_at` and a draft has closed nothing, so a clerk
    asking for *closed in the last 30 days* must get none of these rather than
    all of them. The `move_in_jobs_queryset` precedent is the same shape: one
    filter over two sources works because each source answers for itself.

    ⚠ **THE SEARCH LEGS ARE NARROWER AND THE RESPONSE SAYS SO**
    (`PARKED_MOVE_OUT_SEARCH_LEGS_ARE_NARROWER`). A draft copies ids and joins
    to nothing — BR-SHL-048 (a), *"no report, ageing bucket or occupancy query
    can reach a draft by joining to it"* — so the account-number, unit and
    address legs cannot reach it. What it can answer is the label it was parked
    under, which for a move-out is the account headline the clerk saw.
    """
    from apps.customers import selectors

    rows = seams.wizard_park_queryset(flow=moves.KIND_MOVE_OUT)

    # A window on `closed_at` over rows that have closed nothing: NONE, never all.
    if (filters or {}).get("closed"):
        return rows.none()

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        rows = rows.filter(subject_label__icontains=term)
    return rows


def move_out_park_row(
    park: Any,
    *,
    as_of: date,
    account: Any | None,
    customer: dict[str, Any] | None,
    final_read: dict[str, Any],
) -> dict[str, Any]:
    """One UNFINISHED move-out, in the SAME cells as a closed one.

    ⚠ **THE SHAPE IS IDENTICAL AND THE CONTENT IS NOT, WHICH IS WHAT `row_kind`
    IS FOR** — `move_in_job_row`'s own note, and the reasoning is unchanged: one
    screen renders both kinds, so every key a closed row carries is carried here,
    with a NAMED absence wherever a draft genuinely cannot answer. A row that
    simply omitted `settlement` would render as an empty cell, and an empty cell
    and an absent fact are indistinguishable once drawn (`DEF-127`).

    ⚠ **THE ACCOUNT IS WHY THIS IS A ROW AND THE MOVE-IN DRAFT IS A PANEL.**
    `parkedDrafts.tsx` §1 rejected merging drafts into these tables on one
    argument: *"a `MoveInRow` and a `WizardParkRow` share not one field"*. That
    is true of a move-IN draft, which has no account at all until it commits. It
    is **false of a move-out**: the wizard starts from an account a clerk has
    already picked, so `subject_ref.account_id` resolves and ACCOUNT, CUSTOMER
    and UNIT are the same facts the rows below print, read the same way. Four of
    the ten cells fill, including the table's identity column.

    ⚠ **THE STEP IS REAL, AND IT IS THE HALF OF `DEF-CUS-5888` THAT CLOSES
    HERE.** `STEP_HAS_NO_STORE` still rides on every CLOSED row and must: four
    code paths write `accounts.closed_at` and only one is the wizard
    (`services.move_out`; the others are the disconnect close-out, the account
    import and the import rollback), so `6 of 6` on a closed row would claim a
    clerk walked six steps they never saw. **The two answers coexist — a step
    where one is stored, an absence where none is** — which is what the ruling
    says in as many words.

    ⚠ **NOTHING IS COPIED FROM THE DRAFT THAT THE ACCOUNT CAN ANSWER.** The
    customer, the unit and the address are read off the account through the same
    helpers the closed rows use; only the move-out DATE comes from `values`,
    because that is a thing the clerk typed and nothing else holds it yet.
    """
    subject = park.subject_ref if isinstance(park.subject_ref, dict) else {}
    values = park.values if isinstance(park.values, dict) else {}
    account_id = subject.get("account_id") or None
    # ⚠ THE DATE IS WHAT WAS TYPED, NOT WHAT WAS AGREED. BR-SHL-048 (b): a park
    # holds a draft of a FORM and everything in it is re-validated at execution.
    # It is rendered because p117 draws a date on its in-flight row and because a
    # clerk needs to know which week they were working towards; it commits
    # nothing, and the STATE beside it is what says so.
    intended = (values.get("moved_out_on") or "").strip() or None
    # **THE NUMBER THE DRAFT ALREADY CARRIES** (PO ruling 2026-09-20, option A,
    # item 9 — `OQ-CUS-12489` CLOSED). These two lines read `None` and the
    # absence unconditionally until that day, with the comment *"⛔ NO
    # REFERENCE — only a move-IN draft is numbered while it is in hand"*.
    #
    # ⚠ **SERVING THE ABSENCE OVER A ROW THAT HAS A NUMBER WOULD HAVE BEEN THE
    # WORSE HALF OF THIS CHANGE**, and it is the half a lane fixing only the
    # allocator would have left: the draft would be numbered, `/moves/{ref}`
    # would open it, and the LIST — the one screen a clerk actually reads it
    # off — would still print *"this move-out has no number yet"*. One job,
    # two answers, and the screen's is the one that gets quoted down a phone.
    parked_reference = (park.reference or "").strip() or None
    return {
        "move_no": parked_reference,
        "move_no_unavailable": (
            None if parked_reference else dict(PARKED_MOVE_OUT_HAS_NO_REFERENCE)
        ),
        "row_kind": ROW_KIND_PARKED_MOVE_OUT,
        # The handle the RESUME is built from — `?parked=<id>`. It is the draft's
        # own id and not a database id standing in for a visible value, so B14
        # rule 31 is not in play: nothing prints it.
        "park_id": str(park.id),
        "account_id": str(account_id) if account_id else None,
        "account_no": getattr(account, "account_no", None),
        "account_absence": (
            None
            if account is not None
            else dict(
                PARKED_MOVE_OUT_HAS_NO_ACCOUNT
                if account_id is None
                else PARKED_MOVE_OUT_ACCOUNT_IS_GONE
            )
        ),
        "customer": (customer or {}).get("customer"),
        "customer_no": (customer or {}).get("customer_no"),
        "customer_source": (customer or {}).get("source"),
        # ⚠ **THE LABEL IS THE FALLBACK AND IT IS NOT A SECOND CUSTOMER FIELD.**
        # `subject_label` is what the clerk saw when they parked — the account
        # headline, copied, deliberately stale (`WizardPark.subject_label`:
        # *"a label that goes stale is honest about WHAT WAS PARKED"*). It
        # answers only where the account link cannot, and it is named as its own
        # source so a reader can tell the two apart.
        "customer_absence": (
            None
            if customer
            else {
                "code": "parked_move_out_customer_from_the_draft_label",
                "br_ref": "BR-SHL-048 · BR-CUS-054",
                "detail": (
                    "no customer could be read through the account, so the name shown is the "
                    "label this draft was parked under. It is what the clerk saw when they "
                    "started, copied at that moment and never re-read."
                ),
            }
        ),
        "unit_id": str(account.unit_id) if account is not None and account.unit_id else None,
        "unit": _premise(account.unit_id) if account is not None else None,
        "move_out_date": intended,
        "move_out_date_absence": (
            None
            if intended
            else {
                "code": "parked_move_out_date_not_chosen_yet",
                "br_ref": "BR-SHL-048",
                "detail": (
                    "the move-out date is asked for in the wizard and this draft was parked "
                    "before it. Nothing was lost: a parked draft holds what was typed and "
                    "touches no records, so the date is chosen when it is picked back up."
                ),
            }
        ),
        # ✅ A REAL NUMERATOR — the half of the STEP cell that was never missing.
        # `of` is BR-SHL-046's SIX, the same denominator the closed rows carry
        # and the same one the wizard's own rail counts.
        "step": {
            "reached": int(park.step),
            "of": MOVE_OUT_STEP_COUNT,
            "unavailable": None,
        },
        "final_read": final_read,
        # ⛔ NO SETTLEMENT, AND NOT EVEN A GAP TO NAME — see the constant.
        "settlement": {
            "currency": getattr(account, "currency", None),
            "landing": None,
            "landings": list(move_out_settlement.MONEY_LANDINGS),
            "complete": False,
            "sentence": None,
            "deposit_held": move_out_settlement._pair(None),
            "deposit_interest": None,
            "outstanding": move_out_settlement._pair(None),
            "outstanding_source": None,
            "unavailable": [dict(PARKED_MOVE_OUT_HAS_NO_SETTLEMENT)],
        },
        "state": move_out_park_state(park),
        # ⚠ MEASURED AGAINST THE DATE THE CLERK TYPED, which is the only date
        # this row has. A draft with none is not "leaving this week" — it is not
        # leaving on any stated day at all.
        "leaving_this_week": _within_the_week(
            date.fromisoformat(intended) if intended else None, as_of
        ),
        # What a clerk needs to act on a draft, and what the panel above printed
        # until 2026-09-20: why it stopped and how old it is.
        "waiting_on": park.waiting_on or None,
        "park_note": park.park_note or None,
        "remind_on": park.remind_on.isoformat() if park.remind_on else None,
        "parked_at": park.parked_at.isoformat() if park.parked_at else None,
        "age_days": (as_of - park.parked_at.date()).days if park.parked_at else None,
        # ⚠ **ADDED WITH THE PANEL'S REMOVAL (`DEF-CUS-5994`), AND IT IS THE ONE
        # FIELD THAT WOULD HAVE GONE MISSING.** Every other line this panel drew
        # was already on the row beside it; `Parked by` was not, and it is what
        # `CR-035` amendment 1 put in place of the mine/everyone's toggle. An
        # absence is invisible to every check this repo has (`DEF-CUS-3653`), so
        # it is moved rather than noticed later.
        "parked_by_name": _parked_by_name(park),
    }


#: The ORDER of the union, over the columns BOTH kinds can publish. ⚠ **`created`
#: is the only one both sides hold as a real column**, and it is the default —
#: see `_move_out_page_keys` for what the other two do to a draft.
MOVE_OUT_UNION_SORTS: dict[str, tuple[Any, ...]] = {
    "created": ("created_at", "id"),
    "move_out_date": ("move_out_on", "id"),
    "account": ("account_no", "id"),
}


def _move_out_page_keys(
    *,
    q: str | None,
    filters: dict[str, Any] | None,
    as_of: date,
    sort: str | None,
    dir: str,
    page: int,
    per: int,
) -> tuple[int, list[tuple[str, str]]]:
    """ONE ordered, paginated window over BOTH kinds of row — in SQL.

    Returns `(total, [(row_kind, id), …])`, and the LIST is the order the page
    must be rendered in. `_move_in_page_keys` is the precedent and its reasoning
    is quoted rather than re-argued: `NFR-3` requires server pagination and
    `NFR-5` forbids a cap, so the page is a `LIMIT`/`OFFSET` over ONE order;
    merging two materialised lists would read every closed account and every
    draft on every request — correct at three thousand accounts and thirteen
    times short at forty thousand.

    ⚠ **`.order_by()` WITH NO ARGUMENTS ON EACH ARM.** PostgreSQL and SQLite
    both refuse an `ORDER BY` inside a compound statement's arms, and both
    querysets order their own rows before returning them. The order that matters
    is applied to the UNION, once, over both kinds.

    ⚠ **EVERY SORT IS TOTAL** — `id` ends every tuple, or two rows comparing
    equal across the union swap between page 1 and page 2, showing a clerk one
    row twice and another never.

    ⚠ **TWO OF THE THREE SORTS ARE NULL ON A DRAFT, AND THAT IS STATED RATHER
    THAN PAPERED OVER.** A draft has no `closed_at` and no account number of its
    own — `subject_ref` copies ids and joins to nothing (BR-SHL-048 (a)) — so
    `move_out_date` and `account` sort every unfinished row into one block at
    whichever end the database puts NULLs. The DEFAULT sort is `created`, which
    both sides hold as a real column, so the list a clerk opens is ordered
    properly over both kinds; the other two are a click away and honest about
    what they can see. Reaching into `values` for the typed date would sort a
    JSON string against a date column across two databases, which is a worse
    answer than a stated one.
    """
    accounts = (
        move_outs_queryset(q=q, filters=filters, as_of=as_of, sort=sort, dir=dir)
        .order_by()
        .annotate(row_kind=Value(ROW_KIND_ACCOUNT, output_field=TextField()))
        .values("id", "row_kind", "created_at", "account_no", move_out_on=F("closed_at"))
    )
    parks = (
        move_out_parks_queryset(q=q, filters=filters)
        .order_by()
        .annotate(row_kind=Value(ROW_KIND_PARKED_MOVE_OUT, output_field=TextField()))
        .values(
            "id",
            "row_kind",
            "created_at",
            # ⚠ TYPED `Value`s, NOT BARE `None`s: a bare `None` leaves PostgreSQL
            # to guess a type for a `UNION` arm and it refuses rather than
            # guessing. The two sides must publish the same columns, in the same
            # order, with the same types.
            account_no=Value(None, output_field=TextField()),
            move_out_on=Value(None, output_field=DateField()),
        )
    )
    # `DEF-CUS-10125` — the move-outs a later move-in reopened the account over.
    reopened = (
        reopened_move_outs_queryset(q=q, filters=filters, as_of=as_of)
        .order_by()
        .annotate(row_kind=Value(ROW_KIND_REOPENED_MOVE_OUT, output_field=TextField()))
        .values(
            "id",
            "row_kind",
            "created_at",
            account_no=F("account__account_no"),
            move_out_on=F("previous_closed_at"),
        )
    )
    combined = accounts.union(parks, reopened).order_by(
        *pagination.order_terms(
            sort, dir, columns=MOVE_OUT_UNION_SORTS, default=MOVE_OUT_DEFAULT_SORT
        )
    )
    total = combined.count()
    start = (page - 1) * per
    return total, [
        (str(row["row_kind"]), str(row["id"])) for row in combined[start : start + per]
    ]


def _fetch_reopened_page(keys: list[tuple[str, str]]) -> list[Any]:
    """`DEF-CUS-10125` — the page's reopened move-outs, ONE query, with their
    accounts joined so a row costs nothing further."""
    from apps.customers.move_in_reopen_models import MoveInReopening

    ids = [key for kind, key in keys if kind == ROW_KIND_REOPENED_MOVE_OUT]
    if not ids:
        return []
    return list(
        MoveInReopening.objects.filter(tenant_id=_tenant_id(), id__in=ids).select_related(
            "account", "account__status"
        )
    )


def _fetch_move_out_page(keys: list[tuple[str, str]]) -> tuple[list[Any], list[Any]]:
    """The page's rows, ONE query per kind, from the ids the union chose.

    The union answers *which rows and in what order*; these two reads answer
    *what is on them*. Two queries for a page, whatever the page size — the
    `ar_positions` discipline this module follows everywhere else.
    """
    account_ids = [key for kind, key in keys if kind == ROW_KIND_ACCOUNT]
    park_ids = [key for kind, key in keys if kind == ROW_KIND_PARKED_MOVE_OUT]
    accounts = (
        list(
            models.Account.objects.filter(
                tenant_id=_tenant_id(), id__in=account_ids
            ).select_related("status")
        )
        if account_ids
        else []
    )
    parks = (
        list(seams.wizard_park_queryset(flow=moves.KIND_MOVE_OUT).filter(id__in=park_ids))
        if park_ids
        else []
    )
    return accounts, parks


def _accounts_for_parks(parks: list[Any]) -> dict[str, Any]:
    """The accounts a page's drafts named — ONE query, never one per draft.

    ⚠ **A LOOKUP, NEVER A JOIN, AND THE DIFFERENCE IS THE RULING.** BR-SHL-048
    (a) gives `wizard_parks` no foreign key on purpose, so this reads the copied
    ids out of `subject_ref` and asks `accounts` for them by id under the tenant
    filter. Nothing joins to a draft and nothing is blocked by one; an account
    that has since gone simply does not come back, and the row says so.
    """
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
        for row in models.Account.objects.filter(
            tenant_id=_tenant_id(), id__in=ids
        ).select_related("status")
    }


def move_out_kpis(
    *, as_of: date | None = None, reads_answers: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """B18 §5.6.1's five tiles — three derived, two served as absences.

    | Tile | Caption | This product |
    |---|---|---|
    | `OPEN` | *customers leaving* | ⚠ counts CLOSED move-outs — see below |
    | `LEAVING THIS WEEK` | *within 7 days of today* | `closed_at` in the window ✔ |
    | `FINAL READS DUE` | *nothing settles without one* | ✔ derived through the seam since 2026-08-26 (CR-038 W9 task 2) — see below |
    | `SHORTFALLS TO DECIDE` | *the deposit does not cover it* | ⛔ needs a landing |
    | `REFUNDS TO PAY` | *money leaving the building* | ⛔ needs a landing |

    ⚠ **`OPEN` DOES NOT MEAN WHAT §5.6.1 DRAWS IT MEANING, AND THE TILE SAYS
    SO.** *"Customers leaving"* is a count of move-outs in flight, and §2 is
    that a move-out in flight is not recorded anywhere in this product. What is
    counted is *move-outs that have closed and are not yet finally billed* —
    which is this tab's whole content and is a real figure — and `means` names
    it so nobody reads five here as five people still packing.

    ⚠ **`FINAL READS DUE` IS `unit_reads_cell`'s `due`, COUNTED** — a closed
    move-out with any meter holding no committed head at/after its OWN
    `closed_at` — so the tile and the rows it summarises cannot disagree.
    `final_reads_due_means` names it (the `open_means` precedent). A move-out
    on a METERLESS unit is not counted — nothing can ever be read there — and
    `final_reads_due_meterless` serves that exclusion beside the figure, so a
    `0` over meterless units is a different sentence from "every meter has been
    read" (DEF-127's concern, answered with data instead of a null). When the
    seam does not resolve the tile is `null` with `READS_NOT_READABLE`, never a
    count over units nobody could ask about. `reads_answers` lets
    `move_outs_list` share ONE seam sweep between this tile and its page rows;
    a standalone call resolves its own.

    ⚠ **THE LAST TWO ARE `null`, NEVER `0`.** DEF-127's lesson pointed at a
    KPI: `SHORTFALLS TO DECIDE · 0` says every closing account is square, and
    `REFUNDS TO PAY · 0` says nobody is owed their deposit back. Both would be
    read as good news by the one person whose job is to act on the bad kind.
    (Until 2026-08-26 `FINAL READS DUE` was the third of these; the seam is
    what changed, not the rule.)
    """
    on = _as_of(as_of)
    rows = move_outs_queryset()
    pairs = list(rows.values_list("unit_id", "closed_at"))
    closing_dates = [closed for _unit_id, closed in pairs]
    if reads_answers is None:
        reads_answers = _unit_reads_answers([unit_id for unit_id, _closed in pairs])
    if reads_answers is None:
        final_reads_due: int | None = None
        final_reads_meterless: int | None = None
        final_reads_unavailable: dict[str, Any] | None = dict(READS_NOT_READABLE)
    else:
        final_reads_due = 0
        final_reads_meterless = 0
        final_reads_unavailable = None
        for unit_id, closed in pairs:
            answer = reads_answers.get(str(unit_id))
            if answer is None:  # pragma: no cover — the sweep covered every unit
                continue
            if not answer["meters"]:
                final_reads_meterless += 1
            elif _meters_due(answer, closed.isoformat()):
                final_reads_due += 1
    return {
        "open": len(closing_dates),
        "open_means": "closed_and_not_yet_finally_billed",
        "open_unavailable": dict(MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE),
        "leaving_this_week": sum(1 for day in closing_dates if _within_the_week(day, on)),
        "final_reads_due": final_reads_due,
        "final_reads_due_means": "closed_move_outs_with_a_meter_unread_since_close",
        "final_reads_due_meterless": final_reads_meterless,
        "final_reads_due_unavailable": final_reads_unavailable,
        "shortfalls_to_decide": None,
        "shortfalls_to_decide_unavailable": dict(FINAL_BILL_NOT_STATED),
        "refunds_to_pay": None,
        "refunds_to_pay_unavailable": dict(FINAL_BILL_NOT_STATED),
        "period_basis": "tenant_today",
        "as_of": on.isoformat(),
    }


def move_outs_list(
    *,
    q: str | None = None,
    page: int = 1,
    per: int = DEFAULT_PER,
    as_of: date | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    dir: str = MOVE_DEFAULT_DIR,
) -> dict[str, Any]:
    """The Move-outs tab — §5.6.2's rows, §5.6.1's tiles, §5.7.3's exclusion.

    Returns the same envelope `move_ins_list` does, so one screen component can
    read either.

    ⚠ **TWO KINDS OF ROW SINCE 2026-09-19 (PO ruling, verbatim: `yes`,** asked
    whether this list should show move-outs that have not finished yet**)** —
    the CLOSED accounts this list has always shown, and the `wizard_parks`
    drafts a clerk has started and put down. Every row says which it is in
    `row_kind`, and the ORDER and the PAGE are decided by the database over both
    (`_move_out_page_keys`), never by merging two pages in Python: `NFR-3` is
    the reason, and it is the same reason `move_ins_list` gives.

    ⚠ **THIS LIGHTS UP THE BLUEPRINT'S OWN DRAWN ROW WITH REAL DATA — ALL FOUR
    CELLS OF IT SINCE 2026-09-20.** p117 draws `MVO-26-0087 · 2 of 6 · In
    progress` as its second row, and until the ruling of 2026-09-19 that row
    *could not exist* — an unfinished move-out is not a closed account. The
    step, the account and the state were real from that day; the REFERENCE was
    the one drawn cell still stated as an absence, because only a move-IN draft
    was numbered while it was in hand (`CR-122-BRC06`).
    **`OQ-CUS-12489` closed on 2026-09-20 (PO ruling, option A) and it is now
    real too**: a move-out draft takes `MVO-{YY}-{0000}` from the `move_out`
    series when it is written, and the completed move-out is filed under that
    same number rather than a second one. An unfinished row therefore prints
    the number a clerk can quote, and `PARKED_MOVE_OUT_HAS_NO_REFERENCE`
    survives for the one case that is still true — a tenant with no `move_out`
    series row at all.

    ⚠ **THE THREE TILES STILL COUNT THE CLOSED ROWS ONLY, AND THAT IS A
    DECISION RATHER THAN AN OVERSIGHT.** `move_out_kpis` reads
    `move_outs_queryset()` — closed accounts — and `open_means` says so in the
    server's own words (`closed_and_not_yet_finally_billed`), which is the
    mechanism that stops a caption redefining a figure. The ruling is about
    which ROWS the list holds; redefining what a tile COUNTS would move a number
    the PO read on this screen the same day, silently, and `OPEN` would then
    mean the opposite of what its own caption says. The decision log of
    2026-09-19 carries it with the worked figure.

    ⚠ **THE LEDGER IS ASKED ONCE FOR THE WHOLE PAGE**, not once per row:
    `seams.ar_positions(account_ids=[…])` is the published customers→ledger read
    and its own docstring says why — *"a per-row seam call is a query per row on
    the product's busiest screen"*. Its refusal travels through onto every row's
    settlement cell rather than being swallowed into a zero (DEF-127).

    ⚠ **AND THE READ SEAM IS SWEPT ONCE FOR THE WHOLE WINDOW** (CR-038 W9 task
    2): the `FINAL READS DUE` tile counts over the UNFILTERED window, its units
    are a superset of every page's, so one `_unit_reads_answers` sweep serves
    both the tile and the page's FINAL READ cells — the same discipline, and the
    reason `move_out_kpis` takes `reads_answers`.
    """
    on = _as_of(as_of)
    page = max(1, int(page or 1))
    per = max(1, min(int(per or DEFAULT_PER), MAX_PER))
    total, keys = _move_out_page_keys(
        q=q, filters=filters, as_of=on, sort=sort, dir=dir, page=page, per=per
    )
    window, park_window = _fetch_move_out_page(keys)
    reopened_window = _fetch_reopened_page(keys)
    # PO ruling 2026-09-19 — the accounts the page's DRAFTS named, in ONE query.
    # A lookup by copied id, never a join (BR-SHL-048 (a)); see
    # `_accounts_for_parks`.
    park_accounts = _accounts_for_parks(park_window)
    # ⚠ **BOTH KINDS OF ROW GO INTO THE ONE CUSTOMER READ** — a draft's account
    # has a customer exactly as a closed one does, and a second lookup for the
    # drafts would be the per-row query this module refuses everywhere else.
    customers = _customer_names(
        [row.id for row in window]
        + [account.id for account in park_accounts.values()]
        + [row.account_id for row in reopened_window]
    )
    # ⛔ THE LEDGER IS ASKED FOR THE CLOSED ROWS ONLY. A draft has settled
    # nothing and its absence is a LIFECYCLE fact, not an unreadable one
    # (`PARKED_MOVE_OUT_HAS_NO_SETTLEMENT`) — asking the books about it would
    # buy a position nothing renders and would let a seam refusal print the
    # wrong sentence on a row that never had a settlement to fail at.
    positions = seams.ar_positions(account_ids=[str(row.id) for row in window])
    gaps = tuple(positions.unavailable)
    # ⚠ **UNFILTERED ON PURPOSE, AND THE `f.closed` LEG MUST NOT REACH IT
    # (CR-045 wave D task D.10).** The `FINAL READS DUE` tile counts over the
    # whole window, so this sweep is a superset of every page's units by
    # construction. Narrowing it by the user's filter would make the TILE
    # change when a filter is applied, which is the one thing a KPI strip must
    # not do — the tiles answer "what is on this tab", not "what am I looking
    # at right now".
    # ⚠ **THE DRAFTS' UNITS JOIN THE SWEEP** (PO ruling 2026-09-19). p117 draws
    # `Due` in the FINAL READ cell of its in-flight row, and that is derivable:
    # the meters are on the unit today and the date the clerk typed is what they
    # are measured against. A second sweep for the drafts would be the per-row
    # seam call this line exists to avoid.
    reads_answers = _unit_reads_answers(
        list(move_outs_queryset().values_list("unit_id", flat=True))
        + [account.unit_id for account in park_accounts.values() if account.unit_id]
        + [row.account.unit_id for row in reopened_window if row.account.unit_id]
    )
    # CR-039 wave D 17–19 — ONE query for the page's move-out records. THIS is
    # the tab where the column fills: every row here is a CLOSED account, and
    # `services.move_out` has written a numbered record for each closure since
    # 2026-08-27. Rows closed before then state `move_predates_the_record`.
    move_records = move_records_by_account(
        [row.id for row in window], kind=moves.KIND_MOVE_OUT
    )
    # PO ruling 2026-09-19 — the two kinds are built separately and then put
    # back into the ORDER the union decided, so the page a clerk sees is the page
    # the database ordered and not two lists stapled together (`move_ins_list`'s
    # own discipline, followed rather than re-argued).
    built: dict[str, dict[str, Any]] = {
        str(row.id): move_out_row(
            row,
            as_of=on,
            customer=customers.get(str(row.id)),
            reference=move_reference_cell(move_records.get(str(row.id))),
            settlement=move_out_settlement_cell(
                row,
                outstanding=positions.amount_for(row.id),
                outstanding_gaps=gaps,
            ),
            final_read=unit_reads_cell(
                None if reads_answers is None else reads_answers.get(str(row.unit_id)),
                measured_from=row.closed_at,
                final=True,
                # CR-038 W9 task 4 — the settlement's OWN stored flag,
                # derived once at close (`services.move_out`); the only
                # thing that may make this cell say `estimated`.
                settlement_state=row.final_read_state,
            ),
        )
        for row in window
    }
    # `DEF-CUS-10125` — a move-out a later move-in reopened the account over:
    # the SAME cells as a closed row, dated by the record of that close.
    reopened_references = _reopened_reference_cells(reopened_window)
    for reopening in reopened_window:
        account = reopening.account
        settlement = move_out_settlement_cell(account, outstanding=None, outstanding_gaps=())
        settlement["deposit_held"] = move_out_settlement._pair(None)
        settlement["unavailable"].append(dict(REOPENED_SETTLEMENT_IS_THE_NEW_TENANCYS))
        row = move_out_row(
            account,
            as_of=on,
            customer=customers.get(str(account.id)),
            reference=reopened_references.get(str(reopening.id)),
            settlement=settlement,
            final_read=unit_reads_cell(
                None if reads_answers is None else reads_answers.get(str(account.unit_id)),
                measured_from=reopening.previous_closed_at,
                final=True,
                settlement_state=account.final_read_state,
            ),
        )
        row["row_kind"] = ROW_KIND_REOPENED_MOVE_OUT
        row["move_out_date"] = reopening.previous_closed_at.isoformat()
        row["leaving_this_week"] = _within_the_week(reopening.previous_closed_at, on)
        built[str(reopening.id)] = row
    for park in park_window:
        subject = park.subject_ref if isinstance(park.subject_ref, dict) else {}
        account = park_accounts.get(str(subject.get("account_id") or ""))
        values = park.values if isinstance(park.values, dict) else {}
        intended = (values.get("moved_out_on") or "").strip() or None
        built[str(park.id)] = move_out_park_row(
            park,
            as_of=on,
            account=account,
            customer=(
                customers.get(str(account.id))
                if account is not None
                else None
            )
            or (
                # ⚠ THE PARKED LABEL, AND ONLY WHERE THE ACCOUNT CANNOT ANSWER.
                # `source` names it so a reader can tell a live customer link
                # from a copy taken the day the draft was made.
                {
                    "customer": (park.subject_label or "").strip() or None,
                    "customer_no": None,
                    "source": "parked_label",
                }
                if (park.subject_label or "").strip()
                else None
            ),
            final_read=unit_reads_cell(
                (
                    None
                    if reads_answers is None or account is None
                    else reads_answers.get(str(account.unit_id))
                ),
                # ⚠ THE DATE THE CLERK TYPED — the only date this row has, and
                # BR-TEN-043's rule that an event date is an argument.
                measured_from=date.fromisoformat(intended) if intended else None,
                # ⛔ **`final=False`, DELIBERATELY, ON A CELL HEADED FINAL
                # READ.** `final=True` is what admits the word `estimated`, and
                # `estimated` comes from `accounts.final_read_state` — a flag
                # `services.move_out` writes AT CLOSE. This account has not
                # closed, so there is no settlement for a read to have been
                # estimated FOR, and the flagless-close sentence that rides on a
                # `final` cell would be the wrong reason on a row that never
                # closed. What is left is the true two-state question: has every
                # meter on the unit been read since the day they are leaving.
                final=False,
            ),
        )
    return {
        "rows": [built[key] for _kind, key in keys if key in built],
        "kpis": move_out_kpis(as_of=on, reads_answers=reads_answers),
        "page": page,
        "per": per,
        "total": total,
        "pages": (total + per - 1) // per if per else 0,
        "columns": list(MOVE_OUT_COLUMNS),
        # BR-SHL-010 / `BR-CUS-1046` — the SORT names this list accepts,
        # served beside the rows so the screen cannot offer a column the
        # server will not order by.
        "sorts": list(MOVE_OUT_SORTS),
        "sort": sort if sort in MOVE_OUT_SORTS else MOVE_OUT_DEFAULT_SORT,
        "dir": dir,
        "states": [dict(state) for state in MOVE_OUT_STATES],
        # CR-045 wave D task D.10 — the `f.<name>` vocabulary AND the window
        # codes, served so the screen's options cannot drift from the server's
        # (BR-SHL-010: only a declared capability renders).
        "filters": list(MOVE_OUT_FILTERS),
        "closed_windows": [
            {"code": code, "days": days} for code, days in MOVE_OUT_CLOSED_WINDOWS.items()
        ],
        "search": {
            "hint": MOVE_OUT_SEARCH_HINT,
            "min_chars": _min_search_chars(),
            # `DEF-CUS-5896` — `reference` LEADS, as the columns do. BR-SHL-010
            # is why this tuple exists at all: only a DECLARED capability
            # renders, so a leg the predicate answers and this tuple omits is a
            # box the screen will not offer.
            "legs": ("reference", "customer", "account_no", "unit", "address"),
            "unavailable": [
                dict(MOVE_OUT_REQUEST_LEG_UNLINKED),
                # PO ruling 2026-09-19 — the unfinished rows answer fewer of
                # these legs than the finished ones. Named rather than left for
                # a clerk to discover by getting no hit.
                dict(PARKED_MOVE_OUT_SEARCH_LEGS_ARE_NARROWER),
            ],
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
        # What this LIST cannot show at all, as opposed to what a CELL cannot
        # say. ⚠ **THE FIRST CODE IS KEPT AND ITS SENTENCE IS NARROWED** (PO
        # ruling 2026-09-19): it used to mean *no unfinished move-out is
        # listed*, over a list that now lists them, and it means the one thing
        # still true — a move-out nobody has STARTED writes nothing anywhere.
        "unavailable": [
            dict(MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE),
            dict(MOVE_OUT_WINDOW_HAS_NO_CLOSING_EDGE),
        ],
        "as_of": on.isoformat(),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030 W5 — the Move-ins and Move-outs worklists (backend half) ·
#         B18 §5.5.1 · §5.5.2 · §5.5.7 · §5.6.1 · §5.6.2 · §5.6.7 · §5.7.3 ·
#         apps/customers/services.py (`_open_account`, `_make_occupying`,
#         `activate_account`, `move_out`) · apps/customers/transfers.py
#         (EXCLUSION_CONTRACT) · apps/customers/move_out_settlement.py ·
#         apps/customers/sample_data.py's W5 block · BR-SHL-046 · BR-CUS-018 ·
#         BR-CUS-022 · BR-CUS-030 · BR-CUS-055 · BR-CUS-080 · DEF-127
# generated: 2026-08-25 by lane MOVES (the last two Accounts tabs) · AMENDED
#         2026-08-26 by the CR-038 W9-seam lane (task 2: READS / FINAL READ
#         `taken`/`due` and the FINAL READS DUE tile now DERIVE through
#         `seams.reads_for_unit` → `apps.metering.selectors.reads_for_unit` —
#         `unit_reads_cell` is the one derivation, RED-proved in
#         tests/test_w9_reads_seam.py (`assert None == 1` on the tile before
#         wiring). Still stated: the unresolved-seam deployment (original code,
#         reworded), `unit_has_no_meters`, the dateless move-in) · AMENDED
#         AGAIN 2026-08-26 by the CR-038 W9 event-reads lane (task 4:
#         `estimated` SERVES off `accounts.final_read_state` — the settlement's
#         stored how-obtained flag, derived at close by `services.move_out`;
#         `ESTIMATED_STATE_HAS_NO_SETTLEMENT_FLAG` retired to
#         `FINAL_READ_STATE_NOT_RECORDED`, the flagless-close residue.
#         RED-proved: test_w9_reads_seam's pinned "never estimated" case fails
#         against the new truth and was amended WITH the amendment. DEF-786's
#         frontend adoption lands in this same lane's frontend commit)
# checklist: A✔ B=deferred(the frontend half is MoveInsTab.tsx / MoveOutsTab.tsx
#         in this same lane) C✔ D=deferred(no API half — `GET /move-ins` and
#         `GET /move-outs` are REPORTED with their exact handlers; api.py is
#         another lane's file) E=deferred F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E3 **A MOVE-OUT THAT HAS NOT COMMITTED HAS NO STORE** — four of
#         B18 §5.6.7's six drawn rows are in a state `accounts` cannot hold, and
#         the columns it would take are named in
#         `MOVE_OUT_NOT_YET_CLOSED_HAS_NO_STORE` · E3 the move-out window has no
#         CLOSING edge, because billing publishes no per-account final bill, so
#         no row is ever retired · E3 **no SETTLEMENT landing is stated on any
#         row** and no composed total is served — the engine's own rule is that
#         a gap means no landing, and both gaps are open on every row · E3 STEP
#         has a denominator and no numerator on both tabs (no step on a draft
#         account or a pending job — NOT 'no wizard store', corrected
#         2026-09-19, `DEF-CUS-5888`); the
#         move-out denominator is BR-SHL-046's SIX, not B18's superseded four ·
#         E3 [SUPERSEDED IN PART 2026-08-26, CR-038 W9 task 2] READS / FINAL
#         READ were stated absences for want of a metering read seam; the seam
#         exists now and both derive · E3 [SUPERSEDED 2026-08-26, W9 task 4]
#         `estimated` was stated for want of the settlement how-obtained flag;
#         `accounts.final_read_state` stores it now and the cell serves it.
#         What remains E3: the flagless close (`final_read_state_not_recorded`),
#         the unresolved-seam deployment, `unit_has_no_meters`, the dateless
#         move-in ·
#         E3 the DEPOSIT cell serves the AMOUNT and never the sentence, and
#         NEVER prints `waived` for a zero · E3 `DEPOSITS TO CARRY OVER`,
#         `FINAL READS DUE`, `SHORTFALLS TO DECIDE` and `REFUNDS TO PAY` are
#         served `null` with their reasons, never `0` · E3 `WAITING ON
#         DOCUMENTS` counts *waiting on anything* and says so — `waiting_on` is
#         free text with no vocabulary · E3 `move_in_state`'s `due` and
#         `move_out_state`'s `closed` are MINTED codes, declared `drawn: False`
#         so no screen mistakes either for a B18 segment · E3 `outcome_kind`
#         disagrees with itself in this tree (`"account"` on the seeded Kwan row
#         vs `OUTCOME_CHILD_KINDS`' `"move_in"`); this file matches on the
#         signed `outcome` field instead and REPORTS the drift · E3 no story
#         owns either tab (hard-won law 8) — OWED
# gates: MEASURED by the CR-038 merge lane 2026-08-26 (G11 named this file as
#        the one CR-038 file with no `gates:` line, and a trailer that omits
#        the line is the same claim as one that invents it) — ruff✔ black✔
#        `makemigrations --check`✔ · pytest tests/test_us_cus_004_005_move_in_out.py
#        tests/test_w9_reads_seam.py → **46 passed in 180.63s**, run together
#        because this file's seam is what the second suite exercises and the
#        first is what renders it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
