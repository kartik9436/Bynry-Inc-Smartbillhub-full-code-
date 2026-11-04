# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-015 (S22's disconnect-notice modal — the only story that
#           owns any part of this surface today)
#           Screens: S22 · S90 (Disconnects tab — the LIST half of task 7.11)
#           ⚠ **NO STORY OWNS S90.** `apps/customers/disconnects.py` filed the
#           same finding for the write half — hard-won law 8. A story is OWED
#           and is reported rather than invented here.
# Change:   CR-030 W7 task 7.11 (S90 disconnects tab — six tier chips and six
#           segments), BACKEND half only.
# Rules:    BR-CUS-039 (tiers; certified on the final; medical-hold accounts
#           EXCLUDED) · BR-CUS-043 (an active AND current plan pauses dunning
#           and disconnect) · BR-CUS-053 (the search legs) · BR-CUS-082 (a debt
#           surviving closure is STILL CHASED, ladder restarts at TIER 1) ·
#           BR-CUS-097 (the residue moves to the MASTER; its "who is chased"
#           half is OPEN — OQ-366) · BR-NOT-005 (a notice is WRITTEN; only the
#           dispatcher sends) · BR-PAY-016/017/021/036 · BR-BIL-001 as amended
#           (the $25.00 floor governs the WHOLE ladder) · BR-TEN-043 (the event
#           date is an argument, never a wall clock) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money 4dp stored / 2dp displayed)
# Questions: **OQ-366 — OPEN.** Who the restarted ladder chases when a
#           sub-account's residue moves to its master. No row here names a
#           party. ⛔ **AND ONE MORE IS OWED AND UNMINTED** — see §3 below: the
#           six drawn segments are not mutually exclusive and no rule gives a
#           precedence, so only `segment=all` is served.
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.8.1 (the five
#           KPI tiles) · §5.8.2 (the list — six segments, six tier chips, the
#           LAST NOTICE delivery claim, the accented CUT DATE) · §5.8.3 (the
#           ladder and the three protections) · §5.8.5 (TC-DSC-1..9) · §5.8.6
#           (the nine seed rows) · W7 task 7.11
# Tests:    06-backend/tests/test_w7_worklists.py
# ───────────────────────────────────────────────────────
"""W7 task 7.11 · S90's DISCONNECTS LIST — the read half, and nothing else.

B18 §5.8, verbatim: *"The collections ladder, its protections, the cut and the
reconnect. **Today this is a notice modal and nothing else** — no list, no
ladder, no protections gate."* The ladder and the protections landed with
`apps/customers/disconnects.py`; this is the list.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE REUSES, AND WHY IT AUTHORS NO RULE OF ITS OWN
════════════════════════════════════════════════════════════════════════════
`apps/customers/disconnects.py` is the WRITER and it is another lane's file.
The tier vocabulary, the three protections, the halt decision, the delivery
absence and the post-closure restart are all built there. Every one of them is
CALLED here, never restated:

    disconnects.halt_reason(...)        why the ladder is not running, per row
    disconnects.protections_for(...)    the three protections and their lifetimes
    disconnects.ladder_tier_of(case)    THE one place that answers "which tier"
    disconnects.case_payload(case)      the case as the S90 row needs it
    disconnects.DELIVERY_UNAVAILABLE    the LAST NOTICE absence, verbatim
    disconnects.NO_SCHEDULER            DEF-320, carried on every ladder answer
    disconnects._money / _tenant_id     ONE money formatter, ONE tenant read

⚠ **`halt_reason` IS RECOMPUTED ON EVERY ROW AND IS NOT MEMOIZED, BY DESIGN.**
The writer's own words: *"Nothing stores 'the ladder is running.' `halt_reason()`
is COMPUTED on every call from the balance, the protections and payments' own
pause decision … a RUN cached on a row outlives the debt."* A per-request cache
here would be that cache with a shorter lifetime and the same failure mode —
the customer who paid on Friday and got a certified letter on Monday. **The
OWED column is a different matter and IS read once for the page**
(`seams.ar_positions(ids)`, the DEF-127 posture), because that is a display
figure and not a decision.

════════════════════════════════════════════════════════════════════════════
1 · SIX TIER CHIPS (B18 §5.8.2)
════════════════════════════════════════════════════════════════════════════
B18 §5.8.2, verbatim:

> **`TIER`** is a bordered chip: `TIER 1 · REMINDER` · `TIER 2 · 10-DAY` ·
> `TIER 3 · 48-HOUR` (accent) · `HELD · MEDICAL` · `HELD · PAYMENT PLAN` ·
> `HELD · WEATHER MORATORIUM` (grey) · `—`

**SIX CHIPS AND A DASH.** The three ladder chips are `disconnects.LADDER_TIERS`,
carried through unchanged so there is one spelling; the three HELD chips are
declared here, one per `disconnects.PROTECTIONS` entry, because the writer
models a protection and does not model a chip.

⚠ **THE DASH IS AN ABSENCE, NOT A SEVENTH CHIP**, and it has TWO causes that a
screen must be able to tell apart: nothing has been sent yet, or the account
sits on payments' `second_5_day` rung, **which B18 draws no chip for**. The
writer's own refusal to guess that one is quoted on `CHIP_ABSENCE_UNMAPPED`.

⚠ **AND `chips` IS A LIST, WHICH IS NOT DECORATION.** B18 draws ONE chip per
row and its §5.8.6 fixture never needs two — every HELD row there has `—` for
LAST NOTICE, i.e. it never entered the ladder. **The product can produce two.**
§5.8.3's own diagram draws `T1 · T2 · T3 -.-> HOLD`, so a customer at TIER 2 who
files a medical certificate has BOTH a tier reached and a protection in force,
and a customer with a medical certificate and a weather moratorium has two HELD
chips. **Which one wins in a single cell is stated by no rule**, so this module
serves every chip that applies, in B18's own drawn order, and flags
`chips_ambiguous` when there is more than one. Picking one would be inventing a
precedence; dropping the others would hide a protection from a screen that
authorises a cut.

════════════════════════════════════════════════════════════════════════════
2 · `LAST NOTICE` — A DELIVERY CLAIM THE PRODUCT CANNOT MAKE (task 7.10)
════════════════════════════════════════════════════════════════════════════
B18 §5.8.2, verbatim, and it is the design's own warning:

> **`LAST NOTICE` is a delivery claim the product cannot currently make.** There
> is **no email, SMS or print adapter in this release** — the in-app bell is the
> only channel that delivers anything. `certified signed` asserts a signature
> came back. **This column is drawn against a capability that does not exist**,
> and a lane must render the absence rather than fabricate a delivery state.

So the cell carries the notice's TIER and its ISSUED DATE — both facts — with
`delivery_state: None` and `disconnects.DELIVERY_UNAVAILABLE` attached. It never
carries `emailed`, `posted`, `certified sent` or `certified signed`; TC-DSC-6 is
that assertion. The writer already writes the column NULL on every row, so this
is the read side of a guarantee that is held in the data.

════════════════════════════════════════════════════════════════════════════
3 · SIX SEGMENTS — AND ONLY `all` IS SERVED. AN OPEN QUESTION IS OWED.
════════════════════════════════════════════════════════════════════════════
B18 §5.8.2, verbatim:

> **Segments:** `All` · `At notice` · `Due to cut` · `On hold` · `Cut` ·
> `Reconnecting`

⛔ **THE FIVE NAMED SEGMENTS ARE NOT MUTUALLY EXCLUSIVE, AND NO RULE SAYS WHICH
WINS. MEASURED ON THIS TREE, 2026-08-25:**

  1. **`On hold` cannot be a stored state.** `disconnects.STATE_ON_HOLD` exists
     in `CASE_STATES` and **nothing in this repository ever assigns it** — grep
     over `apps/` finds it declared, listed in the migration's CHECK vocabulary,
     and written nowhere. `record_protection()` does not touch `case.state`.
     So a row is "on hold" because a PROTECTION is in force, which is computed
     from `account_protections` and payments' plan decision.
  2. **The other four ARE stored states** — `notice_sent`, `scheduled`, `cut`,
     `reconnecting` — on `disconnect_cases.state`.
  3. **The two axes are independent.** A case at `notice_sent` whose account
     acquires a medical certificate satisfies `At notice` AND `On hold`. A case
     at `cut` with a weather moratorium satisfies `Cut` AND `On hold`. §5.8.3's
     ladder diagram draws exactly that transition (`T1 · T2 · T3 -.-> HOLD`), so
     it is a designed path and not a corner case.
  4. **B18's own §5.8.6 fixture never shows the collision** — its three HELD
     rows have no notice and no cut date — **so the drawing cannot be read for
     an answer.** It also proves the STATE column is not the stored column:
     `A-11902` reads `On hold` where `disconnect_cases.state` would read
     `notice_sent`.

**Choosing `On hold` over `At notice` (or the reverse) is resolving an open
question by picking a value**, and the prime directive forbids it. So:

  · **`segment="all"` is served** — the union, which hides nothing.
  · **every other value raises `NotImplementedError`** naming the question.
    ⚠ **NO OQ-ID IS INVENTED.** `12-governance/` is outside this lane's write
    scope and the prime directive forbids minting one, so the refusal says the
    question is OWED and states it in full. Whoever mints the row replaces
    `SEGMENT_PRECEDENCE_UNRULED["tracks"]` with the id and nothing else changes.
  · **the row itself serves BOTH axes** (`state.stored` and `state.held_by`)
    with `one_cell_is_unresolved` set when they collide, so the screen can
    render §5.8.6's nine rows exactly as drawn today and cannot silently pick a
    winner tomorrow.

**The question, stated so whoever writes the row does not have to reconstruct
it, with B18's own figures:** *Bramble Bakery (`A-11812`) is at `TIER 2 · 10-DAY`
owing $2,410.00 and files a medical certificate. The Disconnects tab has six
segment tabs. Does that row appear under `At notice`, under `On hold`, or under
both — and does its TIER chip read `TIER 2 · 10-DAY` or `HELD · MEDICAL`? The
same question decides where `A-11488`, cut and owing $612.75, goes if a weather
moratorium is declared over it.*

════════════════════════════════════════════════════════════════════════════
4 · WHICH ROWS ARE ON THE TAB — A UNION, WHICH HIDES NOTHING
════════════════════════════════════════════════════════════════════════════
The row set is **open disconnect cases ∪ accounts with a protection in force**.

The union is DRAWN, not chosen: §5.8.6's `A-11902 · Okafor` sits on the tab at
`HELD · MEDICAL` owing $948.20 with **no cut date and no last notice** — an
account that never entered the ladder — so a list of cases alone would be
missing three of the nine rows. A union is also the safe shape while §3's
question is open: it can only ever show a row that belongs on the tab under one
reading, never hide one.

Cases in `stopped` or `restored` are excluded, because §5.8.3 says the row
*"leaves this list"*, and `disconnects.open_case_for` already draws that line.
⚠ **`open_case_for` EXCLUDES A THIRD STATE THAT THIS LIST DOES NOT** —
`closed_out`, added by `BR-CUS-430` on 2026-08-27 — which is `DEF-CUS-5777` and
is carried over unchanged by the paging fix below. See
`LIST_EXCLUDED_CASE_STATES`.

⚠ **AND THE UNION IS NO LONGER RESOLVED BY BUILDING IT (`DEF-CUS-5755`,
2026-09-19).** The two halves are not alike and the fix is that split: *which
accounts have an open case* is a stored `state` and is now a **subquery** that
returns no row to Python at all, while *which accounts are protected* is
**DERIVED** — `STATE_ON_HOLD` is assigned by nothing, and a payment plan's
liveness is read from payments on every call — so its ids are still resolved in
Python and handed to SQL as a list. `PROTECTED_HALF_IS_DERIVED` states that
exception in one sentence; `DEF-387`'s reasoning is why it was not "fixed" by
writing the derivation a second time in SQL. The page is a `LIMIT` and the
total a `COUNT(*)` over the union, so drawing fifty rows costs fifty accounts
and fifty cases instead of every disconnect-relevant account the tenant has.

════════════════════════════════════════════════════════════════════════════
5 · THE FIVE KPI TILES (B18 §5.8.1), CHECKED AGAINST THE DRAWN NINE ROWS
════════════════════════════════════════════════════════════════════════════
| Tile | Caption | Derived from | §5.8.6 |
|---|---|---|---|
| `AT NOTICE` | *somewhere on the ladder* | a case carrying a LADDER chip, not cut/reconnecting | A-11340 · A-11720 · A-11812 · A-11780 = **4** ✔ |
| `DUE TO CUT THIS WEEK` | *within 7 days of today* | `state == scheduled` **and** `cut_scheduled_for` in `[as_of, as_of+7]` | Aug 24 · Aug 26 = **2** ✔ |
| `ON HOLD — PROTECTED` | *medical, plans, moratorium* | ≥1 protection in force | A-11902 · A-11655 · A-11933 = **3** ✔ |
| `CUT, AWAITING PAYMENT` | ~~*still accruing base charges*~~ **SUPERSEDED (BR-CUS-103 → *cases with the service off*)** | `state == cut` | A-11488 = **1** ✔ |
| `RECONNECTIONS DUE` | *paid, awaiting a visit* | `state == reconnecting` | A-11507 = **1** ✔ |

⚠ **THE TILES OVERLAP ON PURPOSE AND THE SEGMENTS MAY NOT.** `AT NOTICE`'s four
INCLUDE the two scheduled rows that `DUE TO CUT THIS WEEK` also counts —
*"somewhere on the ladder"* is the caption's own word for it, and 4 + 2 + 3 + 1
+ 1 = 11 over nine rows. A KPI is a count and may double-count by design; a
segment is a place a row LIVES, which is why §3 above is a question and this
table is not.

⚠ **BUT A TILE IS STILL A DOOR, AND ITS NUMBER MUST BE THE ROWS BEHIND IT
(`DEF-CUS-6055`, 2026-09-20).** Overlapping with a NEIGHBOUR is by design;
counting rows the list does not return is a lie on a screen that authorises
turning somebody's water off. `DUE TO CUT THIS WEEK` was a pure DATE test and
`cut_scheduled_for` is not cleared at the cut, so on the first two
disconnections this product ever completed the tile read **2** over the **0**
rows its own `Due to cut` view returned. It reads the STATE beside the date
now. `KPI_SEGMENTS` declares all five row sets in one place and
`test_dsc_every_kpi_tile_equals_the_rows_of_its_own_segment` asserts every one
of them against the rows `list_disconnects` actually serves.

⚠ **TWO MORE TILES DIVERGE FROM THE SINGLE-STATE QUICK VIEW THAT CARRIES
THEIR NAME, AND NEITHER IS FIXED HERE — REPORTED, PER THE RULE THAT A LANE
DOES NOT WIDEN A FIX IT WAS NOT ASKED FOR:**
  · **`AT NOTICE` is WIDER than `f.state=notice_sent`** — it counts every case
    carrying a ladder chip, which includes `scheduled` rows. That is DRAWN
    (§5.8.6 counts 4, two of them scheduled) and the caption says *somewhere*,
    so the tile is right and the quick view is one state of two. It is equal
    today only because no case is `scheduled`.
  · **`ON HOLD — PROTECTED` has NO door at all.** `STATE_ON_HOLD` is assigned
    by nothing, so the `Filter ▾` panel's `on_hold` option answers **0** on
    every tenant, for ever, while the tile counts the derived holds.
    `DisconnectStateChips.tsx` §2 reports the same finding from the screen
    side. Both need a server leg answering *is this row held*, which is a
    filter dimension and not this defect.

⛔ **`CUT, AWAITING PAYMENT · still accruing base charges` IS NOW A FALSE
CAPTION, NOT AN UNVERIFIED ONE.** B18 drew it as *"the meter is off and the base
charge is not"*. **BR-CUS-103 (PO 2026-08-25, closing OQ-380) ruled "no" — base
charges STOP at the cut** (DEF-707), and billing implements it by subtracting
the dark days from `service_days`.

**DEF-716 CLOSES THAT, AND THE RENAME IS DONE (2026-08-25).** The absence
constant was `CUT_ACCRUAL_UNVERIFIED` carrying the code string
`cut_base_accrual_unverified`; it is now `CUT_ACCRUAL_CAPTION_SUPERSEDED` /
`cut_accrual_caption_superseded`. **The name was wrong in two ways and both
mattered:** the accrual is no longer *unverified* — it is settled, and settled
in the OPPOSITE direction — so neither the code nor the caption may keep
implying doubt about a question the PO answered. The old spelling is quoted
here rather than deleted (the `disconnects.CUT_WILL` posture): somebody holding
the r10 prototype, an old payload or a screenshot must be able to find the old
string and be told it no longer binds. `07-frontend`'s hardcoded copy of the
code moves in the SAME commit — a rename landing on one side only is a red
suite, which is what kept this defect open.

⚠ **WHAT THE REPLACEMENT DELIBERATELY DOES NOT SAY.** The tile now reads *cases
with the service off*, which is what the figure IS — a count of cases in the
`cut` state. It says nothing about what those customers OWE, because the
reconnection fee reaches the balance at the cut since 2026-08-27
(**DEF-708 fixed**; `disconnects.FEE_POSTED`) — so the reason this caption stays
silent about money changed without the caption changing: a COUNT IS NOT A SUM.
This tile counts cases; a balance caption would need money it never computed.

════════════════════════════════════════════════════════════════════════════
6 · OQ-366 — NO ROW NAMES A CHASED PARTY
════════════════════════════════════════════════════════════════════════════
**OQ-366 is OPEN** (registry, 2026-08-25): *"WHEN A SUB-ACCOUNT'S UNPAID DEBT
MOVES TO ITS MASTER ACCOUNT, WHO DOES THE REMINDER LADDER CHASE — THE DEPARTED
TENANT, OR THE MASTER?"* `BR-CUS-082` restarts the ladder at TIER 1 and
`BR-CUS-097` moves the residue to the master, and **neither says whose door it
knocks on.**

`disconnects.restart_after_closure()` is built so both readings are
unrepresentable — no `subject` parameter, no `tier` parameter, `subject: None`
and `escalates_to_disconnection: False` on the payload. **This list must not
undo that by inference.** A collections-sequence row therefore carries
`subject: None`, `disconnects` own `dunning` block with its
`subject_unresolved` sentence, and `chase_subject_unresolved` naming OQ-366 —
and the CUSTOMER column on such a row states the account the debt was measured
on, which is a fact about the row, never a claim about who is being pursued.
J08 step 2b: *"a green assertion naming either party is a FAILURE."*

════════════════════════════════════════════════════════════════════════════
7 · WHAT IS NOT BUILT HERE, NAMED
════════════════════════════════════════════════════════════════════════════
· **No API route.** `apps/customers/api.py` is outside this lane's write scope.
  The exact `GET /disconnects` handler is REPORTED for the merging session; until
  it is mounted **this list is built and not wired** (hard-won law 2).
· **No screen.** S90's rendering is task 7.11's frontend half.
· **No seed.** §5.8.6's nine `[shot]` rows are a data lane's.
· **Five of six segments refuse.** §3. The tab can show `All` and nothing else
  until the PO rules, and that is a visible product limitation, not a stub
  nobody will notice.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, TextField, Value

from apps.customers import disconnect_due, disconnects, seams
from core import pagination

# ── the list envelope (11b G5: pagination is mandatory on every list) ───────
#: ONE page-size default for the product — `core.pagination`'s. IS-2's
#: `PAGE_SIZES` vocabulary is clamped at the API edge, not here.
DEFAULT_PER = pagination.DEFAULT_PAGE_SIZE
MAX_PER = pagination.PAGE_SIZES[-1]

#: B18 §5.8.2's columns, in the drawn order.
#:
#: ⚠ **`reference` LEADS AND §5.8.2 DOES NOT DRAW IT — CR-039 wave D task 16,
#: 2026-08-27.** The design's eight are unchanged and follow it; the ninth is
#: the CR's finding 5 made reachable: *"Transfer and disconnect have tables and
#: no number … A clerk cannot quote a reference"*. Stamped here rather than left
#: to read as drift. ⚠ **AMENDED 2026-08-27 — this said it *"is EMPTY on every
#: row until `OQ-427` closes"*, and `OQ-427` closed the same day** (PO: *"it
#: needs its own series"*), so it prints `DSC-26-0001` onwards on a provisioned
#: tenant. It is still empty on a host provisioned before the ruling, and on a
#: row that is on this tab because of a PROTECTION it is empty for a second,
#: different reason — see `list_row`.
COLUMNS: tuple[str, ...] = (
    "reference",
    "account",
    "customer",
    "address",
    "owed",
    "tier",
    "cut_date",
    "last_notice",
    "state",
)

#: B18 §5.8.2's own words for the search box, PLUS the case number.
#:
#: ⚠ **`Case #` JOINED THIS PROMPT ON 2026-09-20 (`CR-125-BRC07`) AND THE LEG
#: JOINED THE QUERY IN THE SAME EDIT.** It read *"Customer, account #, address,
#: or meter #…"* — B18's own words — while the list's FIRST column is the case
#: number. So the one identifier a clerk can see on every row was the one
#: identifier the box could not find, and typing it returned an empty list with
#: no refusal: hard-won law 2 wearing a search box. A prompt and its legs are
#: ONE fact and are amended together, never separately, which is why this note
#: sits on the string rather than on the query.
SEARCH_HINT = "Case #, customer, account #, address, or meter #…"

#: §5.8.1's `DUE TO CUT THIS WEEK` caption, verbatim: *"within 7 days of today"*.
WEEK_DAYS = 7


# ═══════════════════════════════════════════════════════════════════════════
# THE SIX SEGMENTS (B18 §5.8.2) — and the precedence nobody ruled
# ═══════════════════════════════════════════════════════════════════════════
SEGMENT_ALL = "all"
SEGMENT_AT_NOTICE = "at_notice"
SEGMENT_DUE_TO_CUT = "due_to_cut"
SEGMENT_ON_HOLD = "on_hold"
SEGMENT_CUT = "cut"
SEGMENT_RECONNECTING = "reconnecting"

#: SIX, in B18 §5.8.2's drawn order. The tuple is the vocabulary, so a seventh
#: segment cannot appear without somebody reading this line.
SEGMENTS: tuple[str, ...] = (
    SEGMENT_ALL,
    SEGMENT_AT_NOTICE,
    SEGMENT_DUE_TO_CUT,
    SEGMENT_ON_HOLD,
    SEGMENT_CUT,
    SEGMENT_RECONNECTING,
)

#: B18 §5.8.2's labels, verbatim: `All` · `At notice` · `Due to cut` · `On hold`
#: · `Cut` · `Reconnecting`.
SEGMENT_LABELS: dict[str, str] = {
    SEGMENT_ALL: "All",
    SEGMENT_AT_NOTICE: "At notice",
    SEGMENT_DUE_TO_CUT: "Due to cut",
    SEGMENT_ON_HOLD: "On hold",
    SEGMENT_CUT: "Cut",
    SEGMENT_RECONNECTING: "Reconnecting",
}

#: ⛔ THE OWED QUESTION. See §3 of the module docstring for the measurement and
#: the plain-English form with B18's own figures. `tracks` is deliberately NOT
#: an OQ id: this lane may not mint one (prime directive; `12-governance/` is
#: outside its write scope), and a made-up id is worse than a stated absence.
SEGMENT_PRECEDENCE_UNRULED: dict[str, Any] = {
    "code": "segment_precedence_unruled",
    "tracks": "OQ-374",
    "br_ref": "B18 §5.8.2 · §5.8.3 · §5.8.6",
    "detail": (
        "B18 §5.8.2 draws six segments — All · At notice · Due to cut · On hold · Cut · "
        "Reconnecting — and they are NOT mutually exclusive. `On hold` cannot be a stored state: "
        "`disconnects.STATE_ON_HOLD` is declared, is in the migration's CHECK vocabulary and is "
        "assigned NOWHERE in this repository (measured 2026-08-25), and `record_protection()` "
        "does not touch `case.state`. So on-hold is COMPUTED from `account_protections` while "
        "the other four are the stored `disconnect_cases.state`, and the two axes are "
        "independent: a case at `notice_sent` whose account files a medical certificate "
        "satisfies `At notice` AND `On hold`, which is the transition §5.8.3's ladder diagram "
        "draws (`T1 · T2 · T3 -.-> HOLD`). §5.8.6's fixture never shows the collision — its "
        "three HELD rows have no notice and no cut date — so the drawing cannot be read for an "
        "answer, and choosing one would be resolving an open question by picking a value. "
        "Worked: Bramble Bakery (A-11812) at TIER 2 · 10-DAY owing $2,410.00 files a medical "
        "certificate — does the row appear under `At notice`, under `On hold`, or both, and "
        "does its chip read `TIER 2 · 10-DAY` or `HELD · MEDICAL`? `segment=all` is served and "
        "every other value is refused. AN OPEN QUESTION IS OWED and this lane may not mint it."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# THE SIX TIER CHIPS (B18 §5.8.2) — three ladder, three held, and a dash
# ═══════════════════════════════════════════════════════════════════════════
#: The three HELD chips, one per `disconnects.PROTECTIONS` entry. The ladder
#: three are `disconnects.TIER_1/2/3` and are NOT respelled here — one spelling,
#: because the list, the case row and the notice row must group on it.
CHIP_HELD_MEDICAL = "held_medical"
CHIP_HELD_PAYMENT_PLAN = "held_payment_plan"
CHIP_HELD_WEATHER_MORATORIUM = "held_weather_moratorium"

CHIP_FOR_PROTECTION: dict[str, str] = {
    disconnects.PROTECTION_MEDICAL: CHIP_HELD_MEDICAL,
    disconnects.PROTECTION_PLAN: CHIP_HELD_PAYMENT_PLAN,
    disconnects.PROTECTION_MORATORIUM: CHIP_HELD_WEATHER_MORATORIUM,
}

#: SIX, in B18 §5.8.2's drawn order. `—` is an ABSENCE and is not in here.
TIER_CHIPS: tuple[str, ...] = (
    disconnects.TIER_1,
    disconnects.TIER_2,
    disconnects.TIER_3,
    CHIP_HELD_MEDICAL,
    CHIP_HELD_PAYMENT_PLAN,
    CHIP_HELD_WEATHER_MORATORIUM,
)

#: B18 §5.8.2's chip text, verbatim.
CHIP_LABELS: dict[str, str] = {
    disconnects.TIER_1: "TIER 1 · REMINDER",
    disconnects.TIER_2: "TIER 2 · 10-DAY",
    disconnects.TIER_3: "TIER 3 · 48-HOUR",
    CHIP_HELD_MEDICAL: "HELD · MEDICAL",
    CHIP_HELD_PAYMENT_PLAN: "HELD · PAYMENT PLAN",
    CHIP_HELD_WEATHER_MORATORIUM: "HELD · WEATHER MORATORIUM",
}

#: §5.8.2: TIER 3 renders in the **accent**, the three HELD chips in **grey**.
#: Tone is DATA so B14's colour decision is made once, in the design.
CHIP_TONES: dict[str, str] = {
    disconnects.TIER_1: "ink",
    disconnects.TIER_2: "ink",
    disconnects.TIER_3: "accent",
    CHIP_HELD_MEDICAL: "grey",
    CHIP_HELD_PAYMENT_PLAN: "grey",
    CHIP_HELD_WEATHER_MORATORIUM: "grey",
}

#: The `—`, cause one: the ladder has not started.
CHIP_ABSENCE_NO_TIER: dict[str, Any] = {
    "code": "no_tier_reached",
    "br_ref": "BR-CUS-039",
    "detail": "no notice has been issued on this account, so it sits on no rung and B18 §5.8.2's "
    "TIER cell renders `—`. It is on this tab for another reason — a protection in force, a cut "
    "awaiting payment, or a reconnection visit due (§5.8.6's `A-11507` owes $0.00 at tier `—`).",
}

#: The `—`, cause two, and the writer lane's own refusal to guess it.
CHIP_ABSENCE_UNMAPPED: dict[str, Any] = {
    "code": disconnects.TIER_UNMAPPED,
    "br_ref": "BR-PAY-017 · B18 §5.8.2",
    "detail": "this account sits on payments' `second_5_day` rung, which B18 §5.8.2 draws NO chip "
    "for. Mapping it onto TIER 2 shows a customer at the 5-day notice as though they were at the "
    "10-day one; onto TIER 3, as though a 48-hour certified letter had gone out. Both are "
    "statements to a regulator about what a customer was told, so neither is made and the cell "
    "renders the absence. A RULING IS OWED: either B18 §5.8 grows a fourth chip or BR-PAY-017 "
    "loses a rung.",
}

#: ⚠ More than one chip applies and B18 draws one cell. See §1 of the module
#: docstring — no precedence is invented, every applicable chip is served.
CHIPS_AMBIGUOUS: dict[str, Any] = {
    "code": "more_than_one_chip_applies",
    "tracks": "OQ-374",
    "br_ref": "B18 §5.8.2 · §5.8.3",
    "detail": "B18 §5.8.2 draws ONE bordered chip per row and this row satisfies more than one: a "
    "tier was reached AND a protection is in force, or two protections are. §5.8.3's ladder "
    "diagram draws that path (`T1 · T2 · T3 -.-> HOLD`) so it is designed, not accidental, and "
    "§5.8.6's fixture never shows it — every HELD row there has `—` for LAST NOTICE. Which chip "
    "wins is stated by no rule, so every applicable chip is served in the drawn order and none "
    "is dropped. It is the same unruled precedence the six segments hit.",
}

#: ⚠ **RENAMED 2026-08-25 — DEF-716.** This constant was
#: `CUT_ACCRUAL_UNVERIFIED`, code string `cut_base_accrual_unverified`, and its
#: sentence read *"§5.8.1's `CUT, AWAITING PAYMENT` caption asserts billing
#: behaviour this packet does not rule and this module does not implement."*
#: That was TRUE when it was written and BR-CUS-103 made it false without
#: touching this file: the accrual is no longer UNVERIFIED, it is **settled, and
#: settled in the opposite direction** — base charges STOP at the cut. A name
#: that keeps implying doubt about a question the PO answered is the same defect
#: as the caption that started it, so both moved together. The old spelling is
#: quoted here and never deleted (the `disconnects.CUT_WILL` posture): a reader
#: holding r10, an old payload or a screenshot has to be able to find it and be
#: told it no longer binds.
#:
#: ⚠ **AND THE REPLACEMENT DOES NOT OVER-CLAIM.** It says the drawn caption is
#: superseded and what the figure IS — a count of cases in the `cut` state. It
#: says nothing about what those customers owe — and since 2026-08-27 that is
#: because a COUNT IS NOT A SUM, not because the money is missing: **DEF-708 is
#: fixed** and the reconnection fee reaches the ledger at the cut
#: (`disconnects.FEE_POSTED`).
CUT_ACCRUAL_CAPTION_SUPERSEDED: dict[str, Any] = {
    "code": "cut_accrual_caption_superseded",
    "br_ref": "BR-CUS-103 (PO 2026-08-25, OQ-380) · B18 §5.8.1 · DEF-707 · DEF-716",
    # ⚠ THIS STRING IS RENDERED COPY — it rides the S90 tile's `title`, so a
    # clerk reads it, and TWO of this tab's existing guards bit the first two
    # drafts of it. Both are recorded because both are instructive:
    #   · quoting the superseded caption to stamp it SUPERSEDED put the false
    #     sentence back on the screen —
    #     `expect(html).not.toContain("still accruing base charges")`. The
    #     verbatim old wording therefore lives in the comment above, which
    #     nobody renders, and this string DESCRIBES it instead.
    #   · saying the fee is *"not yet posted to the ledger"* tripped TC-DSC-6,
    #     *"no delivery claim appears anywhere on the tab"*: on a collections
    #     screen **posted** is what happens to a NOTICE, and `delivery_state` is
    #     NULL for every one of them (BR-NOT-005). Hence *"does not yet reach
    #     the ledger"* — same fact, no second meaning.
    "detail": "SUPERSEDED (BR-CUS-103 → base charges STOP at the cut). B18 §5.8.1 drew this "
    "tile a caption saying a cut account keeps accruing its base charge, and called it a money "
    "statement. The Product Owner ruled on 2026-08-25 that it does not, so that caption is not "
    "shown. This figure is a count of the cases whose service is off, and nothing more — in "
    "particular it says nothing about what those customers owe, because a count of cases is not a "
    "sum of balances.",
}

#: OQ-366's sentence, carried on every collections-sequence row. §6 above.
#: CR-039 wave D task 16 — the SECOND reason a reference cell can be empty, and
#: it is not `OQ-427`'s.
#:
#: ⚠ **A ROW WITH NO CASE IS NOT A ROW WITH AN UNNUMBERED CASE.** §5.8.6's three
#: HELD rows are on this tab because a PROTECTION is in force, and
#: `case_payload` is `None` for them — those accounts never entered the ladder,
#: so there is no record to have a number. Serving `OQ-427`'s sentence there
#: would tell a clerk that numbering is unconfigured when the truth is that
#: nothing has been opened, and the two absences look identical once rendered
#: (DEF-127's shape). They are therefore two codes, not one.
NO_CASE_TO_NUMBER: dict[str, Any] = {
    "code": "no_case_opened",
    "detail": "This account is on the list because a protection is in force. No disconnection "
    "case has been opened, so there is nothing to reference.",
}


def case_reference_absence(case: Any) -> dict[str, Any] | None:
    """Which of the two absences (if either) belongs on this row's reference.

    ⚠ **A THREE-LINE FUNCTION FOR A THREE-LINE EXPRESSION, AND IT EARNS ITS
    NAME.** The first version of this branch was inline in `list_row`, and the
    test written to hold the two absences apart read the two CONSTANTS instead
    of the branch — so when the branch was deliberately broken (both cases
    collapsed onto `CASE_NUMBER_UNAVAILABLE`) the test **passed**. Pulling the
    decision out is what makes it reachable by a test at all, and a check that
    cannot fail on the thing it is pointed at is worse than none, because it is
    trusted (DEF-182).

    `None` — a number exists · `NO_CASE_TO_NUMBER` — no case was ever opened ·
    `disconnects.CASE_NUMBER_UNAVAILABLE` — a real case, unnumbered (`OQ-427`).
    """
    if case is None:
        return dict(NO_CASE_TO_NUMBER)
    if case.case_no:
        return None
    return dict(disconnects.CASE_NUMBER_UNAVAILABLE)


CHASE_SUBJECT_UNRESOLVED: dict[str, Any] = {
    "code": "chase_subject_unresolved",
    "tracks": "OQ-366",
    "br_ref": "BR-CUS-082 · BR-CUS-097 · J08 step 2b",
    "detail": "BR-CUS-082 restarts the ladder at TIER 1 on a debt that survived closure and "
    "BR-CUS-097 moves a sub-account's residue to its MASTER; neither says whose door the "
    "letters go to. `restart_after_closure()` takes no `subject` and no `tier` parameter so "
    "both readings are unrepresentable, and this row names NO party — the account shown is the "
    "one the debt was measured on, which is a fact about the row and not a claim about who is "
    "pursued. J08 step 2b: a green assertion naming either party is a FAILURE.",
}


def _tenant_id() -> Any:
    """ONE tenant resolution for this surface — `disconnects._tenant_id`."""
    return disconnects._tenant_id()


def _as_of(as_of: date | None) -> date:
    """BR-TEN-043 — the event date is an argument, never a wall clock. The
    default is the TENANT's today, which is the calendar `DUE TO CUT THIS WEEK`
    is read against."""
    return as_of or seams.tenant_today()


def _within_the_week(day: date | None, as_of: date) -> bool:
    """§5.8.1's caption, verbatim: *"within 7 days of today"*, and §5.8.2's
    *"`CUT DATE` renders in the **accent** when it is this week"*.

    Inclusive at both ends and forward-looking only. ⚠ **A SCHEDULED CUT WHOSE
    DATE HAS PASSED IS IN NEITHER** — it is not accented and it is not counted —
    which is what the caption says and is not obviously what a clerk wants. It
    is stated here rather than quietly widened, because widening it would make
    the tile disagree with its own printed caption.
    """
    if day is None:
        return False
    return as_of <= day <= as_of + timedelta(days=WEEK_DAYS)


# ═══════════════════════════════════════════════════════════════════════════
# THE ROW SET — a union; §4 of the module docstring
# ═══════════════════════════════════════════════════════════════════════════
#: The states §5.8.3 says take a row OFF this list, named ONCE because it is
#: now read from three places (`open_cases`, the id subquery and the page's own
#: case read) and three literal copies of one set is how a list and a filter
#: come to disagree about which rows exist.
#:
#: ⛔ **IT IS NOT `disconnects.CLOSED_CASE_STATES` AND THE DIFFERENCE IS A
#: FILED DEFECT, NOT A CHOICE MADE HERE (`DEF-CUS-5777`).** That constant holds
#: THREE — `stopped`, `restored` and, since `BR-CUS-430` (2026-08-27),
#: `closed_out` — and it is what the partial unique index and
#: `disconnects.open_case_for` both read. This list has excluded TWO since it
#: was written in August and was never amended when the eighth state landed, so
#: an account whose service case was closed out AND whose surviving debt opened
#: a `BR-CUS-082` collections case beside it has TWO rows here and the dict
#: below keeps whichever the database returned last. **That is left exactly as
#: it is by this change**: widening the tuple would change WHICH ROW A CLERK
#: SEES on a tab that authorises a cut, which is a product decision and not a
#: paging one.
LIST_EXCLUDED_CASE_STATES: tuple[str, ...] = (
    disconnects.STATE_STOPPED,
    disconnects.STATE_RESTORED,
)


def open_cases():
    """Every case that has not left the list (§5.8.3: *"the row leaves this
    list"*). The exclusion is `LIST_EXCLUDED_CASE_STATES`, one line up.

    ⚠ **THE ONLY CALLER LEFT IS `kpi_strip`, AND THAT IS THE POINT
    (`DEF-CUS-5755`, 2026-09-19).** The LIST used to start here too — it built
    every open case in the tenant to key a dict by account — and now asks for
    the page's cases only (`_cases_for`). A KPI is a count over the whole set
    by definition, so this one genuinely wants every row; a LIST does not.

    ⚠ **AND `select_related("account")` IS GONE.** Nothing in this module has
    ever read `case.account` — `list_row` is handed the account separately and
    `case_payload` reads `case.account_id`, which is the column and costs no
    query — so the join was fetching a whole `accounts` row per case for
    nobody, tenant-wide, on every request. Removing it changes no predicate and
    no figure; it is the one saving on this path that needed no judgment at
    all.
    """
    return disconnects.DisconnectCase.objects.filter(tenant_id=_tenant_id()).exclude(
        state__in=LIST_EXCLUDED_CASE_STATES
    )


def _open_case_account_ids():
    """§4's FIRST half as a SUBQUERY — account ids, never built in Python.

    ⚠ **THIS IS THE HALF THAT COSTS NOTHING, AND IT IS WORTH SEPARATING FROM
    THE OTHER ONE.** *Which accounts have an open case* is a stored `state` on
    `disconnect_cases` and needs no derivation, so it can be asked of the
    database as a `WHERE account_id IN (SELECT …)` and never returns a row to
    Python. `_protected_account_ids` — the other half — cannot, and says why.
    """
    return open_cases().values("account_id")


def _protected_account_ids(*, as_of: date) -> list[Any]:
    """Accounts carrying a protection that is IN FORCE on `as_of`.

    The candidate set is narrowed in SQL (started, not lifted, not expired) and
    the answer is then taken from `disconnects.protections_for`, because a
    `payment_plan` protection's liveness is READ from payments every time it is
    asked (LIFETIME_DERIVED) and a stored date cannot answer it. Two steps, one
    authority.
    """
    candidates = (
        disconnects.AccountProtection.objects.filter(
            tenant_id=_tenant_id(), effective_from__lte=as_of
        )
        .filter(Q(lifted_on__isnull=True) | Q(lifted_on__gt=as_of))
        .filter(Q(expires_on__isnull=True) | Q(expires_on__gte=as_of))
        .values_list("account_id", flat=True)
        .distinct()
    )
    return [
        account_id
        for account_id in candidates
        if any(row["in_force"] for row in disconnects.protections_for(account_id, as_of=as_of))
    ]


# ═══════════════════════════════════════════════════════════════════════════
# THE CELLS
# ═══════════════════════════════════════════════════════════════════════════
def chips_for(*, case: Any, protections: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """B18 §5.8.2's TIER cell — every chip that applies, in the drawn order.

    See §1 of the module docstring: B18 draws one chip, the product can produce
    two, and no rule ranks them. Nothing is dropped and nothing is chosen.
    """
    applicable: list[str] = []
    unavailable: list[dict[str, Any]] = []
    tier = disconnects.ladder_tier_of(case) if case is not None else None
    if tier in (disconnects.TIER_1, disconnects.TIER_2, disconnects.TIER_3):
        applicable.append(tier)
    elif tier is not None:
        # A stored tier this vocabulary does not know — payments' `second_5_day`
        # is the one B18 draws no chip for.
        unavailable.append(dict(CHIP_ABSENCE_UNMAPPED))
    for row in protections:
        if row["in_force"]:
            applicable.append(CHIP_FOR_PROTECTION[row["kind"]])
    ordered = [chip for chip in TIER_CHIPS if chip in applicable]
    if not ordered and not unavailable:
        unavailable.append(dict(CHIP_ABSENCE_NO_TIER))
    return {
        "chips": [
            {"code": chip, "label": CHIP_LABELS[chip], "tone": CHIP_TONES[chip]} for chip in ordered
        ],
        "ambiguous": len(ordered) > 1,
        "unavailable": ([dict(CHIPS_AMBIGUOUS)] if len(ordered) > 1 else []) + unavailable,
    }


def last_notice_for(case: Any) -> dict[str, Any]:
    """B18 §5.8.2's `LAST NOTICE` — the tier and the date, never a delivery.

    §2 of the module docstring quotes the design's own warning. `delivery_state`
    is NULL on every row the writer creates and `DELIVERY_UNAVAILABLE` carries
    the reason; TC-DSC-6 asserts that no notice is ever recorded as `emailed`.
    """
    if case is None:
        return {
            "issued_on": None,
            "tier": None,
            "delivery_state": None,
            "unavailable": dict(disconnects.DELIVERY_UNAVAILABLE),
        }
    notice = (
        disconnects.DisconnectNotice.objects.filter(tenant_id=_tenant_id(), case=case)
        .order_by("-issued_on", "-created_at")
        .first()
    )
    return {
        "issued_on": notice.issued_on.isoformat() if notice else None,
        "tier": notice.tier if notice else None,
        # NEVER `emailed`. The column is written NULL and read NULL.
        "delivery_state": notice.delivery_state if notice else None,
        "unavailable": dict(disconnects.DELIVERY_UNAVAILABLE),
    }


def owed_cell(account: Any, positions: Any) -> dict[str, Any]:
    """B18 §5.8.2's `OWED` — the ledger's figure, or its stated absence.

    DEF-127, in `selectors._balance_cells`' own words: a fabricated `$0.00`
    *"looks exactly like a settled account"*, and on THIS tab it would look like
    an account nobody should be chasing. `None` means the reading failed.

    Rule 2's two shapes come from `disconnects._money` — the same formatter
    `case_payload` uses — so the OWED column and the case payload cannot round
    a figure two ways.
    """
    amount = positions.amount_for(account.id) if positions.available else None
    if amount is None:
        return {
            "stored": None,
            "display": None,
            "currency": account.currency,
            "source": None,
            "unavailable": positions.unavailable,
        }
    money = disconnects._money(Decimal(str(amount)))
    return {
        "stored": money["stored"],
        "display": money["display"],
        "currency": positions.currency or account.currency,
        "source": "ledger",
        "unavailable": None,
    }


def state_cell(*, case: Any, protections: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """B18 §5.8.2's `STATE` — BOTH axes, and never a silent winner.

    §3 of the module docstring: `On hold` is computed from the protections and
    the other four states are stored on the case, so a row can be both. The
    stored value and the held kinds are served side by side and
    `one_cell_is_unresolved` marks the collision. **§5.8.6's nine rows all have
    exactly one of the two**, so the drawn screen renders unchanged.
    """
    held = [row["kind"] for row in protections if row["in_force"]]
    stored = case.state if case is not None else None
    collides = bool(stored and held)
    return {
        "stored": stored,
        "held_by": held,
        "one_cell_is_unresolved": collides,
        "unavailable": dict(SEGMENT_PRECEDENCE_UNRULED) if collides else None,
    }


def last_visits_for(case_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """The MOST RECENT attendance on each of the page's cases, in ONE query.

    ⚠ **`DEF-CUS-6749` — THIS MODULE READ NO VISIT AT ALL UNTIL 2026-09-25.**
    `apps/customers/disconnect_visits.py` has existed since `BR-CUS-1083` with
    four outcomes, a CHECK constraint and its own test file, and
    `disconnect_reads.py` contained **zero references to it**. Three of the four
    outcomes CLEAR the cut date and return the case to `notice_sent` — which is
    a real, correct state — so a case a crew drove to on Tuesday and could not
    cut rendered **identically** to a case nobody has ever visited. No null, no
    dash, no gap: nothing for a check to notice, and the dispatcher sending the
    same crew back out is the one who finds it.

    ⚠ **ONE STATEMENT FOR THE WHOLE PAGE, NEVER ONE PER ROW.** `visits_for` in
    the writer's module answers *every* visit on *one* case — the record page's
    question. A list asks the other one, so it gets its own reader rather than a
    loop over that one, which is `NFR-3`'s reasoning applied to a join.

    Newest first by `visited_on`, then `created_at` — two visits recorded for
    the same day are ordered by when they were written down, so a correction
    (a new row, never an edit) wins over the row it corrects.
    """
    from apps.customers import disconnect_visits

    if not case_ids:
        return {}
    latest: dict[str, dict[str, Any]] = {}
    rows = disconnect_visits.DisconnectVisit.objects.filter(
        tenant_id=_tenant_id(), case_id__in=case_ids
    ).order_by("case_id", "-visited_on", "-created_at")
    for visit in rows:
        key = str(visit.case_id)
        # The queryset is already ordered newest-first WITHIN each case, so the
        # first one seen for a case is that case's answer.
        if key in latest:
            continue
        latest[key] = {
            "outcome": visit.outcome,
            "visited_on": visit.visited_on.isoformat(),
            "clears_the_cut_date": (
                visit.outcome in disconnect_visits.OUTCOMES_THAT_CLEAR_THE_DATE
            ),
        }
    return latest


def list_row(
    *,
    account: Any,
    case: Any,
    as_of: date,
    positions: Any,
    visits: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One S90 row: `ACCOUNT · CUSTOMER · ADDRESS · OWED · TIER · CUT DATE ·
    LAST NOTICE · STATE`.

    ⚠ `halt_reason` is called here, once per row, and is NOT memoized across the
    page — the writer's own design (*"a RUN cached on a row outlives the
    debt"*). It is what makes TC-DSC-1 true on this list: the customer who pays
    leaves it on the next read, with nothing cancelled by hand.
    """
    from apps.customers import selectors

    protections = disconnects.protections_for(account.id, as_of=as_of)
    halt = disconnects.halt_reason(account.id, as_of=as_of, case=case)
    _label, premise = selectors._premise_cell(account.unit_id)
    cut_date = case.cut_scheduled_for if case is not None else None
    collections = case is not None and case.sequence == disconnects.SEQ_COLLECTIONS
    row: dict[str, Any] = {
        "account_id": str(account.id),
        # CR-039 wave D task 16 — the reference, lifted to the top level of the
        # row because `case` is documented as an opaque record that no screen
        # reads a field from, and this is the one field a screen must.
        "case_no": case.case_no if case is not None else None,
        "case_no_unavailable": case_reference_absence(case),
        "account_no": account.account_no,
        # The primary CONTACT's name — BR-CUS-054's entity leg is another
        # reader's (`selectors.customer_for_account`) and this is the same cell
        # S17 renders, so one account reads one way on both tabs.
        "customer": selectors.primary_contact_name(account),
        "address": premise,
        "unit_id": str(account.unit_id),
        "owed": owed_cell(account, positions),
        "tier": chips_for(case=case, protections=protections),
        # §5.8.2: the accent is a fact about the date, served as data.
        "cut_date": cut_date.isoformat() if cut_date else None,
        "cut_date_is_this_week": _within_the_week(cut_date, as_of),
        # ⚠ **THE SECOND FACT ABOUT THE SAME DATE, AND IT IS NOT A SECOND
        # CALENDAR (PO 2026-09-20).** `cut_date_is_this_week` looks FORWARD
        # only, by its own docstring, so a date that has passed is in neither
        # the accent nor the tile. `cut_due` answers the other half — overdue,
        # today, ahead, no date, or already done — from `disconnect_due`, the
        # same function the `f.due` filter and the nightly watch read. One
        # predicate, three readers: a tile, a row and a job cannot drift
        # (`DEF-CUS-6055`).
        "cut_due": disconnect_due.due_fact(case=case, as_of=as_of),
        "last_notice": last_notice_for(case),
        # ── `DEF-CUS-6749` · WHETHER ANYBODY HAS BEEN OUT ──────────────────
        # ⚠ **THE STATE ALONE CANNOT SAY THIS, AND THAT IS THE DEFECT.** Three
        # of the four visit outcomes return the case to `notice_sent`, so the
        # stored state of *a crew attended and found a locked gate* and of
        # *nobody has been* is the SAME WORD. This cell is the difference, and
        # it is a fact about the row rather than a second state: the screen
        # prints the state word and this underneath it.
        #
        # `None` means no attendance is recorded — NOT that nobody went. The
        # distinction matters on a screen that authorises a cut, and it is the
        # honest reading: this product knows about visits somebody wrote down.
        "visit": (
            None if case is None else (visits or {}).get(str(case.pk))
        ),
        "state": state_cell(case=case, protections=protections),
        # Recomputed on every read, never stored — §5.8.3's "it stops itself".
        "ladder": {
            "runs": halt is None,
            "halt_code": None if halt is None else str(halt["code"]),
            "detail": "the ladder runs" if halt is None else str(halt["detail"]),
            "sequence": case.sequence if case is not None else disconnects.SEQ_SERVICE,
            "scheduler": dict(disconnects.NO_SCHEDULER),
        },
        "protections": [
            {
                "kind": row_["kind"],
                "lifetime": row_["lifetime"],
                "in_force": row_["in_force"],
                "effective_from": (
                    row_["effective_from"].isoformat() if row_["effective_from"] else None
                ),
                "expires_on": row_["expires_on"].isoformat() if row_["expires_on"] else None,
                "reason": row_["reason"],
            }
            for row_ in protections
        ],
        "case": disconnects.case_payload(case) if case is not None else None,
        # OQ-366 — §6. NO party is named on any row, and the collections row
        # says so out loud rather than by omission.
        "subject": None,
        "chase_subject_unresolved": dict(CHASE_SUBJECT_UNRESOLVED) if collections else None,
    }
    return row


# ═══════════════════════════════════════════════════════════════════════════
# THE QUERY
# ═══════════════════════════════════════════════════════════════════════════
def _search_q(term: str) -> Q | None:
    """B18 §5.8.2's search: *"Customer, account #, address, or meter #…"*.

    Every leg is BR-CUS-053's and is reached through the reader that already
    owns it — metering's `unit_ids_matching` for the address, assets'
    `unit_ids_for_asset_search` for the meter #, customers' own contact-name
    read — so the Disconnects box finds exactly what the Accounts box finds.
    `None` means "the term is too short to search on", not "no matches".

    ⚠ **IT RETURNS A PREDICATE AND NOT A SET OF IDS, SINCE 2026-09-19
    (`DEF-CUS-5755`).** It used to run its own `SELECT id FROM accounts` and
    hand back every matching id, which the caller then intersected in Python —
    so searching a tenant dragged every match into memory before anything was
    paged. **Not one leg moved**: the three `Q` terms below are the ones that
    were there, in the same order, with the same `icontains` and the same two
    seam reads. What changed is that the answer is now `AND`-ed onto the list's
    own queryset instead of being materialised first.
    """
    from apps.customers import selectors

    if len(term) < selectors.MIN_SEARCH_CHARS:
        return None
    unit_ids = set(seams.unit_ids_matching(term)) | set(seams.unit_ids_for_asset_search(term))
    matches = Q(account_no__icontains=term)
    matches |= Q(id__in=selectors._account_ids_by_contact_name(term))
    # ── `CR-125-BRC07` · THE CASE NUMBER, AND IT IS A SUBQUERY ───────────
    # The list's first column is `CASE #` and this box could not find one. The
    # leg is added as a `values("account_id")` SUBQUERY and never as a list of
    # ids built in Python, for the reason the docstring above already gives:
    # `DEF-CUS-5755` took exactly that cost off this read three days ago and a
    # new leg must not put it back. `case_no` is unique per tenant
    # CASE-INSENSITIVELY (`uq_disconnect_cases_tenant_case_no_ci`), so
    # `icontains` is the right operator — a clerk typing `dsc-26-0003` means
    # the row that reads `DSC-26-0003`, and a partial `0003` is a legitimate
    # search on a number a customer read out over the phone.
    #
    # ⚠ **EVERY CASE, NOT `open_cases()`.** A stopped or restored case leaves
    # the LIST (§5.8.3) and its number does not stop existing — a clerk holding
    # a letter that quotes `DSC-26-0003` is asking *what happened to this*, and
    # answering "no results" because the ladder ended is the wrong answer to
    # that question. The row set is still the list's own; this leg only decides
    # which ACCOUNTS the term matches.
    matches |= Q(
        id__in=disconnects.DisconnectCase.objects.filter(
            tenant_id=_tenant_id(), case_no__icontains=term
        ).values("account_id")
    )
    if unit_ids:
        matches |= Q(unit_id__in=[str(unit_id) for unit_id in unit_ids])
    return matches


#: CR-045 wave D task D.8 (DEF-1702) — the one filter dimension S90 declares.
#:
#: ⛔ **THIS IS NOT `?segment=`, AND THE DIFFERENCE IS THE WHOLE REASON IT IS
#: BUILDABLE.** §3 refuses every segment but `all` because B18 §5.8.2's six
#: segments are not mutually exclusive — `On hold` is COMPUTED from the
#: account's protections while the rest are the stored `disconnect_cases.state`
#: — and *no rule ranks them*, so assigning each row to exactly ONE segment is
#: an unruled decision this lane may not take (prime directive). A FILTER asks a
#: different question: *does this row's stored `state` equal X*. That needs no
#: ranking, no exclusivity and no precedence, so it can be answered today
#: without touching the open question. `?segment=` still refuses everything but
#: `all`, unchanged.
#:
#: ⚠ **`due` JOINED IT ON 2026-09-20 (PO: *"Something has to read cut dates
#: daily and surface what's due"*).** It is a SECOND DIMENSION and not a second
#: spelling of the first: `state` asks *what has been decided about this case*
#: and `due` asks *has its date arrived*. A case can be `scheduled` and six days
#: overdue, `scheduled` and a month away, or cut and neither — which is the whole
#: of the PO's complaint, because the drawn `Due to cut` chip is
#: `f.state=scheduled` and cannot tell those apart. The vocabulary, the
#: predicate and the labels all live in `disconnect_due.py` so the tile, this
#: list and the nightly watch read ONE function (`DEF-CUS-6055`'s own remedy).
DISCONNECT_FILTERS: tuple[str, ...] = ("state", "due")

#: The states a row ON THIS LIST can actually hold — `CASE_STATES` minus the two
#: `open_cases` excludes (*"the row leaves this list"*, §5.8.3). Derived by
#: subtraction rather than retyped, so adding a state to `disconnects.py` cannot
#: leave this tuple behind, and a state that leaves the list can never be
#: offered as a filter option that always answers "none".
DISCONNECT_FILTER_STATES: tuple[str, ...] = tuple(
    state
    for state in disconnects.CASE_STATES
    if state not in (disconnects.STATE_STOPPED, disconnects.STATE_RESTORED)
)


#: ── §5.8.2's SORT VOCABULARY (`BR-CUS-1046`, PO 2026-09-12) ────────────────
#: ⚠ **THESE ORDER `accounts`, NOT `disconnect_cases`, AND THAT IS FORCED BY §4.**
#: This list is a UNION of open cases and protected accounts, and a protected
#: account has `case is None` — so an ORDER BY over a case column would put
#: every protected row at one end of the list on a NULL. The union is resolved
#: through the accounts queryset, so the ordering lives there and the row's
#: `created` is the ACCOUNT's creation. That is also the honest reading of the
#: ruling on this tab: *"any entry … created in the system"*, and what a clerk
#: sees listed here is a customer, not a case.
#:
#: ⚠ **`cut_date` AND `tier` ARE DELIBERATELY ABSENT.** Both are per-case, one
#: of them (`tier`) is COMPUTED per row rather than stored, and §3's unruled
#: segment precedence is exactly the question *"how do these rank against each
#: other"*. Offering them would be this module inventing the precedence it
#: refuses to take.
SORTS: dict[str, tuple[Any, ...]] = {
    #: ⚠ **WRITTEN ASCENDING, LIKE EVERY TERM IN THIS MAP — `order_terms` FLIPS
    #: IT AND `DEFAULT_DIR` IS `desc`.** The first draft of this pass stored
    #: `-created_at` here AND defaulted to `desc`, so the flip cancelled the
    #: minus and every list opened on the OLDEST row: the exact inversion of
    #: the ruling, shipped as a working feature. Nothing raised — it was found
    #: by curling the endpoint and reading the first three rows.
    "created": ("created_at", "id"),
    #: The ordering this tab OPENED ON until 2026-09-12, and its footnote said
    #: so. Kept as a clickable column whose choice survives a refresh.
    "account_no": ("account_no", "id"),
}
DEFAULT_SORT = "created"
DEFAULT_DIR = "desc"


#: ⚠ **THE ONE `O(tenant)` STEP LEFT ON THIS READ, NAMED SO IT CAN BE COUNTED
#: RATHER THAN DISCOVERED** — the posture `selectors.account_list_is_sql_pageable`
#: and `rating.tax_list_is_sql_pageable` already take, and it is stated as a
#: constant rather than a predicate because it is a property of the TENANT'S
#: DATA and not of the clerk's request: every request pays it, and no request
#: can avoid it.
#:
#: §4's union is `open cases ∪ accounts with a protection IN FORCE`. The first
#: half is a stored `state` and is a subquery (`_open_case_account_ids`). The
#: second half is **DERIVED**: `disconnects.STATE_ON_HOLD` exists and nothing in
#: this repository ever assigns it, so *on hold* is computed — and a
#: `payment_plan` protection's liveness (`LIFETIME_DERIVED`) is READ FROM
#: PAYMENTS on every call, which no `WHERE` clause over `account_protections`
#: can answer. `DEF-387`'s reasoning, kept verbatim because it is the reason
#: this is a note and not a fix: *"a derived value cannot be filtered in the
#: database without re-implementing the derivation in SQL — two implementations
#: of one rule, which is how a list and a detail end up disagreeing about the
#: same row."* On a tab that authorises turning somebody's water off, the row
#: that disagrees is an account under a medical certificate.
#:
#: **What it costs, measured, and it is NOT the account count:** the id list is
#: the size of the tenant's `account_protections` window on `as_of` — 20 rows
#: on a tenant of 40,000 accounts with twenty holds. It is `O(protected)`, and
#: `O(tenant)` only for a utility that has declared a moratorium over
#: everybody. `DEF-CUS-5778` is the row that carries the rest of it.
PROTECTED_HALF_IS_DERIVED = (
    "the protected half of the disconnects row set is computed, not queried: a payment plan's "
    "liveness is read from payments on every call, so its account ids are resolved in Python "
    "and handed to SQL. It is O(accounts carrying a protection), never O(accounts)."
)


def _list_queryset(
    *,
    as_of: date,
    q: str | None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    dir: str = DEFAULT_DIR,
    protected: list[Any] | None = None,
):
    """The union of §4 as ONE LAZY accounts queryset — searched, filtered, ordered.

    ⚠ **LAZY IS THE WHOLE POINT (`NFR-3`, `DEF-CUS-5755`), AND NO PREDICATE
    MOVED.** Until 2026-09-19 this was `_rows_for`, which returned a BUILT list
    of `(account, case)` pairs, and `list_disconnects` did `total = len(pairs)`
    and `pairs[start : start + per]` — so drawing fifty rows built every
    disconnect-relevant account the tenant has, and counted them by building
    them. The union, the search, the `f.state` filter and the ordering are the
    same four steps in the same order; what changed is that they are now
    expressed ON the queryset instead of over a set of ids, so `list_disconnects`
    can put the page in a `LIMIT` and the total in a `COUNT(*)`.

    ⚠ **IT OPENS ON THE CREATION ORDER SINCE 2026-09-12 (`BR-CUS-1046`,
    `DEF-CUS-5060`).** It was ordered by account NUMBER, and the tab said so
    under its pager. That ordering is still here as `sort="account_no"`.

    It is STILL NOT ordered by urgency, and that has not changed: `AT NOTICE`,
    `DUE TO CUT` and `ON HOLD` are three different urgencies and ranking them
    against each other is the same unruled precedence §3 refuses to take. The
    new default is not a claim about urgency either — it is a claim about
    RECENCY, which is a fact this list can state without ranking anything.

    Every sort ends in `id` so the page boundary is stable (IS-2).

    `protected` is `_protected_account_ids`' answer, PASSED DOWN rather than
    re-derived — see `list_disconnects`. It is not a cache: one `as_of`, one
    request, one computation, and a caller who omits it gets a fresh one.
    """
    from apps.customers import models

    cases = _open_case_account_ids()
    # ── CR-045 wave D task D.8 · `f.state` ────────────────────────────────
    # ⚠ **A ROW WITH NO CASE CANNOT MATCH A CASE STATE, AND IT MUST NOT.** §4's
    # union is `open cases ∪ protected accounts`, so an account that is on the
    # list only because it holds a protection has `case is None` and no stored
    # state at all. Filtering by state drops it, which is the truthful answer:
    # it is not in that state, it is in no state.
    #
    # ⚠ **AND THAT IS WHY THE FILTERED BRANCH DROPS THE PROTECTED HALF
    # ENTIRELY RATHER THAN NARROWING THE UNION.** The old code unioned both
    # halves and then kept only the ids whose case matched; every id that
    # survived had a case, so the protected half could never contribute a row.
    # The set algebra is identical and the derived read is not paid at all.
    state = (filters or {}).get("state")
    # ── PO 2026-09-20 · `f.due` — *has the date arrived* ──────────────────
    # ⚠ **A SECOND DIMENSION, APPLIED AS A SECOND `WHERE`, WHICH IS WHY IT CAN
    # BE COMBINED.** `f.state=scheduled&f.due=overdue` is *"cuts that are
    # booked and late"* and both narrowings apply; neither hides a row the
    # other would have shown. That composition is the reason this is a filter
    # and not a segment — nothing has to be ranked (`OQ-374`, untouched).
    #
    # ⚠ **A ROW WITH NO CASE CANNOT HAVE A CUT DATE, AND IT MUST NOT MATCH.**
    # The protected half of §4's union has `case is None`, so the same set
    # algebra `f.state` uses applies: the filtered branch drops it entirely
    # rather than narrowing the union, and the derived read is not paid at all.
    due = (filters or {}).get("due")
    if due and str(due) not in disconnect_due.DUE_FILTER_VALUES:
        # a value this list cannot answer shows NOTHING, never all (BR-SHL-011)
        return models.Account.objects.none()
    if state:
        if str(state) not in DISCONNECT_FILTER_STATES:
            # a state this list cannot hold shows NOTHING, never all
            return models.Account.objects.none()
        # ── `DEF-CUS-6746` · `on_hold` IS RESOLVED THE WAY THE SCREEN RESOLVES
        #    IT, NOT THE WAY THE COLUMN STORES IT ───────────────────────────
        #
        # ⛔ **THIS BRANCH USED TO ASK `cases.filter(state="on_hold")` AND THAT
        #    COULD NEVER MATCH A ROW.** `STATE_ON_HOLD` is declared in
        #    `CASE_STATES`, is in the migration's CHECK vocabulary, and is
        #    **assigned nowhere in this repository** — two docstrings in this
        #    very file say so. `DISCONNECT_FILTER_STATES` derives its options by
        #    SUBTRACTION from the stored vocabulary, which is the right rule and
        #    produced a wrong member: a filter offered over two rows whose State
        #    cell reads `On hold`, answering zero forever. Hard-won law 7's
        #    INCAPABLE OF PASSING shape wearing a filter control.
        #
        # ⚠ **THE MEANING IS THE ONE THE UNFILTERED LIST AND THE TILE ALREADY
        #    USE**, so there is exactly one definition of *on hold* on this
        #    screen: an account carrying a protection IN FORCE on `as_of`. §4's
        #    union computes that half in Python (`PROTECTED_HALF_IS_DERIVED`
        #    says why it cannot be a `WHERE`), and this reuses the SAME answer —
        #    `protected` is passed down from `list_disconnects`, so asking for
        #    the view costs no second derivation.
        #
        # ⚠ **NOTHING ABOUT `OQ-374` IS DECIDED HERE.** That question asks which
        #    of two axes WINS when a row satisfies both. A filter picks no
        #    winner: `f.state=on_hold` narrows to rows that are held, and a held
        #    row with a notice out still answers `f.state=notice_sent` too. Both
        #    are true and neither hides the other.
        if str(state) == disconnects.STATE_ON_HOLD:
            held = _protected_account_ids(as_of=as_of) if protected is None else protected
            members = Q(id__in=list(held))
        else:
            members = Q(id__in=cases.filter(state=str(state)))
    elif due:
        members = Q(id__in=disconnect_due.due_account_ids(as_of=as_of, want=str(due)))
    else:
        ids = _protected_account_ids(as_of=as_of) if protected is None else protected
        members = Q(id__in=cases) | Q(id__in=list(ids))
    accounts = models.Account.objects.filter(tenant_id=_tenant_id()).filter(members)
    if due and state:
        # Both dimensions asked. The `state` branch above chose the members;
        # this is the `due` narrowing on top of it, as a subquery rather than a
        # second membership set, so the page and the total stay in SQL (NFR-3).
        accounts = accounts.filter(
            id__in=disconnect_due.due_account_ids(as_of=as_of, want=str(due))
        )
    search = _search_q((q or "").strip())
    if search is not None:
        accounts = accounts.filter(search)
    order = pagination.order_terms(sort, dir, columns=SORTS, default=DEFAULT_SORT)
    return accounts.order_by(*order)


# ═══════════════════════════════════════════════════════════════════════════
# `DEF-CUS-5994` — THE SECOND KIND OF ROW: THE PARKED DRAFT (PO 2026-09-20)
# ═══════════════════════════════════════════════════════════════════════════
#: B18 §5.8.7's FIVE, named in the wizard frame's own step strip: *"1 Account &
#: reason · 2 Protections · 3 Notice & date · 4 Fees & consequences · 5 Review"*.
#:
#: ⚠ **CARRIED AS A CONSTANT SO THE TWO HALVES CANNOT DRIFT**, which is
#: exactly what `MOVE_OUT_STEP_COUNT` exists for and what BR-SHL-046 was written
#: after: a denominator restated in a second language is a second place to get
#: it wrong, and `MOVE_IN_STEP_COUNT` shipped as a `5` under a six-step wizard
#: for weeks because nothing compared them (`DEF-CUS-5886`). The FRONT END's
#: `DISCONNECT_STEPS` is the list a clerk actually walks and this must equal its
#: length; the new test asserts the served `of` against the drafts step.
DISCONNECT_STEP_COUNT = 5

#: Named on EVERY row rather than inferred from a missing case, which is
#: `BR-CUS-1077`'s posture and `DEF-127`'s lesson: a blank cell and an absent
#: fact read the same way once drawn.
ROW_KIND_ACCOUNT = "account"
ROW_KIND_PARKED_DISCONNECT = "parked_disconnect"

#: ⚠ **MINTED, AND DECLARED UNDRAWN.** Every code in `DISCONNECT_FILTER_STATES`
#: is a stored `DisconnectCase.state` — a fact about a CASE. A parked draft has
#: no case at all (nothing is raised until the wizard is run), so none of them
#: can carry it. The Move-ins and Transfers tabs minted the same two spellings
#: on the same day, deliberately identical.
DISCONNECT_STATE_IN_PROGRESS_DRAFT = "in_progress_draft"
DISCONNECT_STATE_PARKED = "parked"

#: ⛔ A draft has raised no case, so there is no case number to quote.
PARKED_DISCONNECT_HAS_NO_CASE: dict[str, Any] = {
    "code": "parked_disconnect_has_no_case",
    "br_ref": "BR-SHL-048",
    "detail": (
        "Nobody has raised this disconnect yet. A parked draft holds what was typed and "
        "creates nothing — no case, no notice, no cut date — so there is no case number "
        "until somebody picks it back up and runs it."
    ),
}

#: ⛔ The ladder is a property of a CASE, and a draft has none.
PARKED_DISCONNECT_HAS_NO_LADDER: dict[str, Any] = {
    "code": "parked_disconnect_has_no_ladder",
    "br_ref": "BR-SHL-048",
    "detail": (
        "Nothing is chasing this account on account of this draft. The ladder runs off a "
        "raised case and none exists, so no notice is due, nothing is scheduled and nothing "
        "stops itself."
    ),
}

#: ⛔ A raised case records no wizard step, and that is about the CASE rather
#: than about this list. A disconnect case can be raised by paths that are not
#: the wizard, so a full bar on one would claim a clerk walked five steps they
#: never saw. `move_reads.CLOSED_MOVE_OUT_HAS_NO_STEP` is the same fact one
#: module over and was written for the same reason.
CASE_HAS_NO_WIZARD_STEP: dict[str, Any] = {
    "code": "disconnect_case_has_no_wizard_step",
    "br_ref": "BR-SHL-046",
    "detail": (
        "This disconnect has been raised and how many steps somebody walked to raise it was "
        "not written down. A case can be opened without the wizard, so a full bar here would "
        "say a clerk went through five steps that may never have happened."
    ),
    "wanted_columns": ("<a step column on disconnect_cases, written at raise time>",),
}

#: ⛔ Which search legs a draft can answer.
PARKED_DISCONNECT_SEARCH_LEGS_ARE_NARROWER: dict[str, Any] = {
    "code": "parked_disconnect_has_no_account_number_to_search",
    "br_ref": "BR-SHL-048",
    "detail": (
        "A draft joins to nothing — BR-SHL-048 (a) gives `wizard_parks` no foreign key on "
        "purpose — so the account-number, address and meter legs cannot reach one. A parked "
        "disconnect answers to the label it was parked under, which is the account headline "
        "the clerk saw when they put it down."
    ),
}


def parks_queryset(*, q: str | None = None, filters: dict[str, Any] | None = None):
    """The disconnects a clerk started and put down — `wizard_parks`.

    ⚠ **THE WINDOW, NOT A COLUMN.** PO 2026-09-20, verbatim: *"remove it - it is
    anyway in the list so we dont need it sepretely - if it is not in list add
    it"*. Until that day a parked disconnect was drawn on a pinned PANEL above
    this table (`CR-035` amendment 1) and this list could not see it at all.
    `move_reads.move_out_parks_queryset` is the shape being copied, written one
    day earlier for the Move-outs tab, rather than a second answer designed.

    ⚠ **READ THROUGH THE SEAM, NEVER THE TABLE.** `wizard_parks` is
    TENANCY-hosted and customers may not import `apps.tenancy.models` (B1 /
    BR-TEN-013; G6 rule 4 refuses it). `seams.wizard_park_queryset` carries the
    tenant filter under RLS `FORCE` — hard rule 1 where the queryset is BUILT.

    ⚠ **`f.state` IS EXCLUSIVE BETWEEN THE TWO SOURCES**, which is what lets one
    filter work over two tables: `_list_queryset` answers stored case states and
    this one answers the two draft codes, and each returns NONE rather than
    EVERYTHING for a value it does not own (BR-SHL-011).
    """
    from apps.customers import selectors

    rows = seams.wizard_park_queryset(flow="disconnect")

    # ⛔ **A DRAFT HAS NO CUT DATE, SO IT ANSWERS NO `due` QUESTION** — and it
    # returns NONE rather than everything, which is what `f.state` already does
    # for a value this source does not own (`BR-SHL-011`). The reason travels
    # as `disconnect_due.PARKED_DISCONNECT_HAS_NO_CUT_DATE`.
    if (filters or {}).get("due"):
        return rows.none()

    state = (filters or {}).get("state")
    if state and str(state) not in (
        DISCONNECT_STATE_IN_PROGRESS_DRAFT,
        DISCONNECT_STATE_PARKED,
    ):
        return rows.none()
    if str(state) == DISCONNECT_STATE_IN_PROGRESS_DRAFT:
        rows = rows.filter(waiting_on="")
    elif str(state) == DISCONNECT_STATE_PARKED:
        rows = rows.exclude(waiting_on="")

    term = (q or "").strip()
    if len(term) >= selectors.MIN_SEARCH_CHARS:
        rows = rows.filter(subject_label__icontains=term)
    return rows


def park_state(park: Any) -> str:
    """`in_progress_draft` or `parked` — told apart by ONE column.

    `WizardPark.waiting_on`'s own docstring: *"EMPTY MEANS *A DRAFT*, NOT *A
    PARK WITH NO REASON*"*. Every flow reads the same column the same way, and
    **the draft got no flag of its own on purpose**: two columns that must agree
    are two columns free to disagree.
    """
    return (
        DISCONNECT_STATE_PARKED
        if (park.waiting_on or "").strip()
        else DISCONNECT_STATE_IN_PROGRESS_DRAFT
    )


def park_row(park: Any, *, as_of: date, account: Any | None, positions: Any) -> dict[str, Any]:
    """One UNFINISHED disconnect, in the SAME nine cells as a case row.

    ⚠ **THE SHAPE IS IDENTICAL AND THE CONTENT IS NOT, WHICH IS WHAT `row_kind`
    IS FOR.** Every key a case row carries is carried here, with a NAMED absence
    wherever a draft genuinely cannot answer. A row that simply omitted `ladder`
    would render as an empty cell, and an empty cell and an absent fact are
    indistinguishable once drawn (`DEF-127`).

    ⚠ **`owed` IS A REAL FIGURE AND IS NOT AN ABSENCE.** The account owes what
    the LEDGER says it owes whether or not a clerk finished a wizard, and it is
    read through `seams.ar_positions` in the SAME page sweep the case rows use —
    never `accounts.balance`, which is a cache nothing writes and which once
    told a customer owing $108.88 that they owed nothing (`DEF-127` /
    BR-CUS-015). This is the cell a clerk is actually chasing, so serving an
    absence over a figure the ledger holds would be the worse half of the
    change.

    ⚠ **THE STEP IS REAL, AND SERVING IT IS THE IMPROVEMENT THE RULING BUYS.**
    This table draws no STEP column, so the number rides on the row as data and
    the screen prints it beside the draft's own state rather than in a column
    the blueprint does not draw (B14 rule 37 — a figure drawn in a wireframe is
    an illustration; the converse holds too, and a column nobody drew is not
    invented here).
    """
    from apps.customers import selectors

    parked_at = park.parked_at
    premise = selectors._premise_cell(account.unit_id)[1] if account is not None else None
    return {
        "row_kind": ROW_KIND_PARKED_DISCONNECT,
        # The handle RESUME is built from — `?parked=<id>`. Nothing prints it,
        # so B14 rule 31 is not in play.
        "park_id": str(park.id),
        "account_id": str(account.id) if account is not None else None,
        "case_no": None,
        "case_no_unavailable": dict(PARKED_DISCONNECT_HAS_NO_CASE),
        "account_no": getattr(account, "account_no", None),
        # The label the clerk parked under answers where the account link
        # cannot — deliberately stale, because it is what they SAW.
        "customer": (
            selectors.primary_contact_name(account)
            if account is not None
            else (park.subject_label or None)
        ),
        "address": premise,
        "unit_id": (
            str(account.unit_id) if account is not None and account.unit_id else None
        ),
        "owed": owed_cell(account, positions) if account is not None else None,
        # ⛔ NO TIER. The chips are a case's ladder position and its protections;
        # a draft has neither, and an empty chip row would read as "nothing is
        # protecting this account" rather than "nobody has asked".
        "tier": None,
        "cut_date": None,
        "cut_date_is_this_week": False,
        # ⛔ A DRAFT HAS NO DATE, so it is `no_date` and never `ahead` — the
        # shape is identical to a case row's and the content is a NAMED
        # absence, which is what `row_kind` is for. The reason a clerk would
        # want rides beside it rather than being inferred from a null.
        "cut_due": {
            **disconnect_due.due_fact(case=None, as_of=as_of),
            "unavailable": dict(disconnect_due.PARKED_DISCONNECT_HAS_NO_CUT_DATE),
        },
        "last_notice": None,
        "state": {"code": park_state(park), "drawn": False},
        "ladder": {
            "runs": False,
            "halt_code": PARKED_DISCONNECT_HAS_NO_LADDER["code"],
            "detail": PARKED_DISCONNECT_HAS_NO_LADDER["detail"],
            "sequence": None,
            "scheduler": dict(disconnects.NO_SCHEDULER),
        },
        "protections": [],
        "case": None,
        "subject": None,
        "chase_subject_unresolved": None,
        # ✅ THE REAL STEP, off `wizard_parks.step`. The denominator is the
        # flow's OWN declared list — the same one `DISCONNECT_STEPS` gives the
        # wizard's rail — so `2 of 5` here and `2 of 5` there cannot drift.
        "step": {"reached": int(park.step), "of": DISCONNECT_STEP_COUNT, "unavailable": None},
        # ⚠ **WHAT THE PANEL CARRIED, MOVED ONTO THE ROW (`DEF-CUS-5994`).**
        # `Parked by` is what `CR-035` amendment 1 put in place of a
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
    that has since gone simply does not come back and the row falls through to
    the parked label.
    """
    from apps.customers import models

    ids = [
        str((park.subject_ref or {}).get("account_id"))
        for park in parks
        if isinstance(park.subject_ref, dict) and (park.subject_ref or {}).get("account_id")
    ]
    if not ids:
        return {}
    return {
        str(row.id): row
        for row in models.Account.objects.filter(
            tenant_id=_tenant_id(), id__in=ids
        ).select_related("status")
    }


def _cases_for(accounts: list[Any]) -> dict[str, Any]:
    """The open case for each account ON THE PAGE, in ONE query.

    ⚠ **THIS IS THE READ THAT USED TO BE TENANT-WIDE.** `_rows_for` keyed a
    dict over every open case the tenant holds so that fifty rows could look
    theirs up; fifty rows now ask for fifty. `uq_one_open_disconnect_case_per_
    account` is what makes the dict unambiguous, and `LIST_EXCLUDED_CASE_STATES`
    says where that guarantee stops — the `closed_out` gap it names is
    `DEF-CUS-5777` and is deliberately carried over unchanged, collapse and all.
    """
    ids = [account.id for account in accounts]
    if not ids:
        return {}
    return {
        str(case.account_id): case
        for case in disconnects.DisconnectCase.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids
        ).exclude(state__in=LIST_EXCLUDED_CASE_STATES)
    }


#: The ORDER of the union, over the columns BOTH kinds can publish.
#:
#: ⚠ **ONE OF THE TWO IS NULL ON A DRAFT, STATED RATHER THAN PAPERED OVER** —
#: `move_reads._move_out_page_keys`' own note. A draft has no account number of
#: its own (`subject_ref` copies ids and joins to nothing, BR-SHL-048 (a)), so
#: `account_no` sorts every unfinished row into one block at whichever end the
#: database puts NULLs. The DEFAULT is `created`, which both sides hold as a
#: real column, so the list a clerk opens is ordered properly over both kinds.
DISCONNECT_UNION_SORTS: dict[str, tuple[Any, ...]] = {
    "created": ("created_at", "id"),
    "account_no": ("account_no", "id"),
}


def _page_keys(
    *,
    as_of: date,
    q: str | None,
    filters: dict[str, Any] | None,
    sort: str | None,
    dir: str,
    page: int,
    per: int,
    protected: list[Any] | None,
) -> tuple[int, list[tuple[str, str]]]:
    """ONE ordered, paginated window over BOTH kinds of row — in SQL.

    Returns `(total, [(row_kind, id), …])`, and the LIST is the order the page
    must be rendered in. `move_reads._move_out_page_keys` is the precedent and
    its reasoning is quoted rather than re-argued: `NFR-3` requires server
    pagination and `NFR-5` forbids a cap, so the page is a `LIMIT`/`OFFSET` over
    ONE order. Merging two materialised lists would read every disconnect-
    relevant account and every draft on every request — which is exactly the
    cost `DEF-CUS-5755` removed from this list three days ago and which must not
    come back through a new arm.

    ⚠ **`.order_by()` WITH NO ARGUMENTS ON EACH ARM.** PostgreSQL and SQLite
    both refuse an `ORDER BY` inside a compound statement's arms, and
    `_list_queryset` orders its own rows before returning them. The order that
    matters is applied to the UNION, once, over both kinds.

    ⚠ **EVERY SORT IS TOTAL** — `id` ends every tuple, or two rows comparing
    equal across the union swap between page 1 and page 2, showing a clerk one
    row twice and another never.
    """
    accounts = (
        _list_queryset(
            as_of=as_of, q=q, filters=filters, sort=sort, dir=dir, protected=protected
        )
        .order_by()
        .annotate(row_kind=Value(ROW_KIND_ACCOUNT, output_field=TextField()))
        .values("id", "row_kind", "created_at", "account_no")
    )
    parks = (
        parks_queryset(q=q, filters=filters)
        .order_by()
        .annotate(row_kind=Value(ROW_KIND_PARKED_DISCONNECT, output_field=TextField()))
        # ⚠ A TYPED `Value`, NOT A BARE `None`: a bare `None` leaves PostgreSQL
        # to guess a type for a `UNION` arm and it refuses rather than guessing.
        .values("id", "row_kind", "created_at", account_no=Value(None, output_field=TextField()))
    )
    combined = accounts.union(parks).order_by(
        *pagination.order_terms(
            sort, dir, columns=DISCONNECT_UNION_SORTS, default=DEFAULT_SORT
        )
    )
    total = combined.count()
    start = (page - 1) * per
    return total, [
        (str(row["row_kind"]), str(row["id"])) for row in combined[start : start + per]
    ]


# ════════════════════════════════════════════════════════════════════════════
# `DEF-CUS-6055` · EVERY TILE'S SEGMENT, DECLARED ONCE
# ════════════════════════════════════════════════════════════════════════════
# **A TILE IS A DOOR.** A clerk reads `DUE TO CUT · 2`, presses the word beside
# it and expects to find two rows. So a tile's number and the rows a clerk
# reaches with that word have to be the SAME SET, and this table is where that
# is stated — one predicate per tile.
#
# ⚠ **THEY ARE WRITTEN OVER THE SERVED ROW, NEVER OVER THE MODEL, AND THAT IS
# WHAT MAKES THE CHECK WORTH ANYTHING.** `kpi_strip` counts MODEL objects out
# of `open_cases()`; these read the payload `list_row` builds over
# `_list_queryset()`. Two code paths, two row sets, two derivations — so
# asserting one against the other is not a tautology. It fails the moment
# either side drifts, which is exactly what `DEF-CUS-6055` was: `DUE TO CUT`
# said **2** over the **0** rows its own `Due to cut` view returned, because
# the tile tested a DATE and the list tests a STATE.
#
# ⚠ **THE HABIT THE DEFECT NAMES, KEPT HERE SO IT IS NOT RE-LEARNED: a date
# that records WHEN SOMETHING HAPPENED goes on matching a window that was
# meant to mean WHEN IT WILL.** `cut_scheduled_for` is not cleared by a cut —
# correctly, it is the record of the day the supply went off — so a pure date
# test matches that case for the rest of its life. Every predicate below that
# reads a date reads a STATE beside it.
#
# ⚠ **A PARKED ROW MATCHES NOTHING HERE, AND THAT IS RIGHT.** `park_row`
# serves `state` as `{"code": …, "drawn": False}` with no `stored` key and no
# `tier`, because a parked disconnect is not a case. Every predicate reads
# through `.get`, so a park falls out of all five segments rather than being
# counted by one of them.


def _seg_stored(row: dict[str, Any]) -> str | None:
    """The row's STORED case state, or `None` on a row that has no case."""
    cell = row.get("state")
    return cell.get("stored") if isinstance(cell, dict) else None


def _seg_chip_codes(row: dict[str, Any]) -> list[str]:
    """The TIER cell's chip codes — `chips_for`'s own answer, not re-derived."""
    cell = row.get("tier")
    chips = cell.get("chips") if isinstance(cell, dict) else None
    return [str(chip.get("code")) for chip in (chips or []) if isinstance(chip, dict)]


def _seg_at_notice(row: dict[str, Any]) -> bool:
    """*"somewhere on the ladder"* — a LADDER chip, and not already cut.

    ⚠ **IT SPANS TWO STORED STATES ON PURPOSE AND IS DRAWN THAT WAY.** B18
    §5.8.6 counts `AT NOTICE` as **4**, and two of those four are `scheduled`
    rows that `DUE TO CUT` counts as well — the module docstring's §5 says so
    in the design's own word, *somewhere*. This is therefore the one tile whose
    segment is WIDER than the single-state quick view that carries its name,
    and narrowing it to `notice_sent` would be this file overruling the
    drawing. Reported, not taken.
    """
    return bool(_seg_chip_codes(row)) and any(
        code in disconnects.LADDER_TIERS for code in _seg_chip_codes(row)
    ) and _seg_stored(row) not in (disconnects.STATE_CUT, disconnects.STATE_RECONNECTING)


def _seg_due_to_cut(row: dict[str, Any]) -> bool:
    """*"within 7 days of today"* — a case still WAITING for the cut.

    `cut_date_is_this_week` is the row's own served flag, so the window is read
    and never recomputed: one calendar, `_within_the_week`, computed once per
    row. The STATE test beside it is `DEF-CUS-6055` itself.
    """
    return _seg_stored(row) == disconnects.STATE_SCHEDULED and bool(
        row.get("cut_date_is_this_week")
    )


def _seg_on_hold(row: dict[str, Any]) -> bool:
    """*"a protection is in force"* — the DERIVED axis, `state_cell`'s own.

    ⚠ **THIS SEGMENT HAS NO `f.state` DOOR AND CANNOT HAVE ONE.**
    `disconnects.STATE_ON_HOLD` is declared, is in the migration's CHECK
    vocabulary and is **assigned by nothing**, so `f.state=on_hold` can never
    return a row. The hold lives on `state.held_by`, which is what this reads.
    """
    cell = row.get("state")
    held = cell.get("held_by") if isinstance(cell, dict) else None
    return bool(held)


def _seg_cut(row: dict[str, Any]) -> bool:
    """*"cases with the service off"* — the stored `cut` state, nothing more."""
    return _seg_stored(row) == disconnects.STATE_CUT


def _seg_reconnecting(row: dict[str, Any]) -> bool:
    """*"paid, awaiting a visit"* — the stored `reconnecting` state."""
    return _seg_stored(row) == disconnects.STATE_RECONNECTING


#: Tile key on `kpi_strip`'s payload → the rows that tile is a door into.
#: `test_dsc_every_kpi_tile_equals_the_rows_of_its_own_segment` asserts all five
#: at once and cannot pass while any of them drift.
KPI_SEGMENTS: dict[str, Any] = {
    "at_notice": _seg_at_notice,
    "due_to_cut_this_week": _seg_due_to_cut,
    "on_hold_protected": _seg_on_hold,
    "cut_awaiting_payment": _seg_cut,
    "reconnections_due": _seg_reconnecting,
}


def kpi_strip(*, as_of: date | None = None, protected: list[Any] | None = None) -> dict[str, Any]:
    """B18 §5.8.1's five tiles. Every count is checked against §5.8.6's own nine
    rows in the module docstring's table — 4 · 2 · 3 · 1 · 1.

    The tiles OVERLAP by design (`AT NOTICE`'s four include the two scheduled
    rows `DUE TO CUT THIS WEEK` counts) — §5 of the module docstring.

    ⚠ **THIS READS EVERY OPEN CASE IN THE TENANT AND STILL DOES, DELIBERATELY
    (`DEF-CUS-5755`, 2026-09-19).** The LIST beside it now takes its page in
    SQL; these five tiles are counts over the WHOLE set, which is what a KPI
    is, so a whole-set read is the honest shape rather than the leftover one.
    Four of the five could be `COUNT(*)` aggregates today — they read `state`
    and `cut_scheduled_for`, which are columns nothing wraps. **The fifth
    cannot, and it is what keeps the other four here:** `AT NOTICE` asks
    `disconnects.ladder_tier_of(case)`, and that function exists precisely so
    that *"which tier is this case on"* has ONE home — its own docstring says
    it is there so folding the column into payments' `account_collection_state`
    is a change to one function rather than to five call sites. Writing
    `tier__in=LADDER_TIERS` in a `WHERE` clause would be the second site.
    Moving only the other four would buy nothing, because `AT NOTICE` scans the
    same rows either way. So the whole strip stays in Python, one pass, and the
    cost is recorded rather than hidden: `DEF-CUS-5778`.

    `protected` is `_protected_account_ids`' answer PASSED DOWN by
    `list_disconnects`, which needs the same list for the row set — one
    derivation per request instead of the two this read used to pay. Called on
    its own, this still computes its own.
    """
    on = _as_of(as_of)
    cases = list(open_cases())
    on_the_ladder = [
        case
        for case in cases
        if disconnects.ladder_tier_of(case) in disconnects.LADDER_TIERS
        and case.state not in (disconnects.STATE_CUT, disconnects.STATE_RECONNECTING)
    ]
    return {
        # *"somewhere on the ladder"*
        "at_notice": len(on_the_ladder),
        # *"within 7 days of today"* — **and still waiting for the cut**.
        #
        # ⚠ **THE STATE TEST IS `DEF-CUS-6055`, AND IT WOULD HAVE SENT A CREW
        # TO A DARK HOUSE (2026-09-20).** This was a pure DATE test: *every
        # open case whose `cut_scheduled_for` falls inside the window*.
        # `cut_scheduled_for` is NOT cleared when the cut happens — correctly,
        # it is the record of the day the supply went off — so a cut case went
        # on matching the window for the rest of its life. On the first two
        # disconnections this product ever completed, the register read
        # `DUE TO CUT · 2` over two households whose supply was already off,
        # and the `Due to cut` view beside it returned **no rows at all**.
        #
        # ⚠ **IT IS `== STATE_SCHEDULED`, NOT `not in (cut, reconnecting)`,
        # AND THE POSITIVE FORM IS THE POINT.** `scheduled` is the state this
        # product's own screens LABEL *"Due to cut"*, and the list's quick view
        # sets exactly `f.state=scheduled` — so this is *"the same predicate as
        # the list it opens"* rather than a shorter exclusion list that happens
        # to cover today's two rows. It also excludes a case that
        # `advance_tier` pushed back to `notice_sent` while a stale
        # `cut_scheduled_for` stayed on the row (that function saves `state`
        # and does not clear the date) — the same date shape one step removed,
        # which the negative form would have let through.
        #
        # `at_notice` above still spans BOTH `notice_sent` and `scheduled`,
        # deliberately: *"somewhere on the ladder"* is drawn that way and
        # §5.8.6 counts it that way. `KPI_SEGMENTS` states every tile's row set.
        "due_to_cut_this_week": sum(
            1
            for case in cases
            if case.state == disconnects.STATE_SCHEDULED
            and _within_the_week(case.cut_scheduled_for, on)
        ),
        # *"medical, plans, moratorium"* — computed, never a stored state.
        "on_hold_protected": len(
            _protected_account_ids(as_of=on) if protected is None else protected
        ),
        # B18 draws *"still accruing base charges"* here and BR-CUS-103
        # SUPERSEDED it — see `CUT_ACCRUAL_CAPTION_SUPERSEDED`. The count is of
        # cases in the `cut` state and asserts nothing about money.
        "cut_awaiting_payment": sum(1 for case in cases if case.state == disconnects.STATE_CUT),
        "cut_awaiting_payment_unavailable": dict(CUT_ACCRUAL_CAPTION_SUPERSEDED),
        # *"paid, awaiting a visit"*
        "reconnections_due": sum(
            1 for case in cases if case.state == disconnects.STATE_RECONNECTING
        ),
        "as_of": on.isoformat(),
    }


def state_counts(*, as_of: date, protected: list[Any]) -> dict[str, int]:
    """How many rows each offered `f.state` value WOULD return, so a view that
    is empty says so before a clerk opens it (`DEF-CUS-6746`).

    ⚠ **THIS EXISTS BECAUSE SIX OF THE EIGHT OFFERED VALUES ANSWERED ZERO AND
    THE SCREEN COULD NOT TELL A CLERK WHICH.** One of them (`on_hold`) was
    broken and is fixed in `_list_queryset`; the rest are TRUE zeroes — `cut`,
    `reconnecting` and `closed_out` are states no case in this tenant has
    reached yet, and the two draft codes are zero when nobody has parked a
    wizard. A control that answers *nothing* is indistinguishable from a broken
    one **until the number is beside it**, which is the whole of the remedy
    here: nothing is hidden and no option is withdrawn.

    ⚠ **IT IS THE WHOLE SET, NOT THE SEARCHED SET, AND THAT IS DELIBERATE.**
    The number says how many rows the VIEW holds, which is a property of the
    tenant's data; recomputing it under the current `q` would make an option's
    count move as a clerk types, and a filter list that renumbers itself while
    being read is harder to trust than one that does not.

    THREE statements and no per-row work: one GROUP BY over the open cases, two
    counts over the parked drafts. `protected` is §4's derived half, already
    computed for this request and passed in rather than re-derived
    (`PROTECTED_HALF_IS_DERIVED`).
    """
    counts: dict[str, int] = {code: 0 for code in DISCONNECT_FILTER_STATES}
    for row in open_cases().values("state").annotate(n=Count("id")):
        if row["state"] in counts:
            counts[str(row["state"])] = int(row["n"])
    # ⚠ **THE ONE VALUE THAT IS NOT A STORED STATE**, counted the way the list
    # and the HELD tile both resolve it — an account carrying a protection in
    # force. Reading it off `disconnect_cases.state` is exactly the bug this
    # function was written beside.
    counts[disconnects.STATE_ON_HOLD] = len(protected)
    counts[DISCONNECT_STATE_IN_PROGRESS_DRAFT] = parks_queryset(
        filters={"state": DISCONNECT_STATE_IN_PROGRESS_DRAFT}
    ).count()
    counts[DISCONNECT_STATE_PARKED] = parks_queryset(
        filters={"state": DISCONNECT_STATE_PARKED}
    ).count()
    return counts


def list_disconnects(
    *,
    segment: str = SEGMENT_ALL,
    q: str | None = None,
    page: int = 1,
    per: int = DEFAULT_PER,
    as_of: date | None = None,
    filters: dict[str, Any] | None = None,
    sort: str | None = None,
    dir: str = DEFAULT_DIR,
) -> dict[str, Any]:
    """S90's list — B18 §5.8.2's rows, §5.8.1's KPI strip, six chips, six segments.

    Returns `{"rows", "kpis", "page", "per", "total", "pages", "columns",
    "segment", "segments", "search", "chips"}`.

    ⛔ **ONLY `segment="all"` IS SERVED.** §3 of the module docstring measures
    why: the six drawn segments are not mutually exclusive, `On hold` is
    computed while the other four are stored, and no rule ranks them. Every
    other value raises `NotImplementedError` carrying the question in full —
    with **no invented OQ id**, because this lane may not mint one.
    """
    if segment not in SEGMENTS:
        raise NotImplementedError(
            f"{segment!r} is not one of B18 §5.8.2's six segments "
            f"({', '.join(SEGMENTS)}). {SEGMENT_PRECEDENCE_UNRULED['detail']}"
        )
    if segment != SEGMENT_ALL:
        raise NotImplementedError(
            f"the {SEGMENT_LABELS[segment]!r} segment cannot be served: "
            f"{SEGMENT_PRECEDENCE_UNRULED['detail']}"
        )
    on = _as_of(as_of)
    page = max(1, int(page or 1))
    per = max(1, min(int(per or DEFAULT_PER), MAX_PER))
    # §4's derived half, computed ONCE for this request and handed to both
    # readers that need it — the row set and the `ON HOLD — PROTECTED` tile.
    # It was computed twice per request until 2026-09-19 (`DEF-CUS-5755`), once
    # in each, which on a tenant with 200 holds was 200 avoidable statements.
    # `PROTECTED_HALF_IS_DERIVED` says why it cannot be a `WHERE` clause.
    protected = _protected_account_ids(as_of=on)
    # ⚠ **THE PAGE AND THE TOTAL BOTH REACH SQL (`NFR-3`), AND THE TOTAL IS
    # THE HALF THAT IS EASY TO LOSE:** a `LIMIT` over a list whose total is
    # still a `len()` has moved the cost rather than removed it. `NFR-5` is
    # honoured by there being no cap here — `per` clamps to IS-2's vocabulary
    # at the API edge and to `MAX_PER` above, and neither ever refuses a row
    # that exists.
    # ── `DEF-CUS-5994` · TWO KINDS OF ROW, ONE ORDER, DECIDED IN SQL ─────
    # PO 2026-09-20: *"remove it - it is anyway in the list so we dont need it
    # sepretely - if it is not in list add it"*. The drafts that used to sit on
    # a pinned panel above this table are rows of it now, and the DATABASE
    # decides the order and the page over both kinds — never a Python splice
    # into a server-paged list, which is the cost `DEF-CUS-5755` just removed.
    total, keys = _page_keys(
        as_of=on,
        q=q,
        filters=filters,
        sort=sort,
        dir=dir,
        page=page,
        per=per,
        protected=protected,
    )
    from apps.customers import models as customers_models

    account_ids = [key for kind, key in keys if kind == ROW_KIND_ACCOUNT]
    park_ids = [key for kind, key in keys if kind == ROW_KIND_PARKED_DISCONNECT]
    window = (
        list(
            customers_models.Account.objects.filter(
                tenant_id=_tenant_id(), id__in=account_ids
            ).select_related("status")
        )
        if account_ids
        else []
    )
    park_window = (
        list(seams.wizard_park_queryset(flow="disconnect").filter(id__in=park_ids))
        if park_ids
        else []
    )
    cases = _cases_for(window)
    park_accounts = _accounts_for_parks(park_window)
    # ONE ledger read for the page (DEF-127's posture), because OWED is a
    # DISPLAY figure. The ladder decision below is recomputed per row and is
    # deliberately not batched — see the module docstring.
    #
    # ⚠ **THE DRAFTS' ACCOUNTS GO INTO THE SAME SWEEP.** A draft's account owes
    # what the ledger says it owes whether or not a clerk finished a wizard, and
    # a second sweep for the drafts would be the per-row read this line exists
    # to avoid.
    positions = seams.ar_positions(
        [account.id for account in window] + [row.id for row in park_accounts.values()]
    )
    # `DEF-CUS-6749` — the page's attendances, in ONE statement, before the
    # rows are built. Handed down exactly as `positions` is: a per-row read
    # here would be the N+1 `_page_keys` was rewritten to remove.
    visits = last_visits_for([case.pk for case in cases.values() if case is not None])
    built: dict[str, dict[str, Any]] = {
        str(account.id): {
            **list_row(
                account=account,
                case=cases.get(str(account.id)),
                as_of=on,
                positions=positions,
                visits=visits,
            ),
            "row_kind": ROW_KIND_ACCOUNT,
            "park_id": None,
            # The case rows carry no wizard step and never did: a disconnect
            # case can be raised by paths that are not the wizard, so a full bar
            # here would claim a clerk walked five steps they never saw. It is
            # `STEP_HAS_NO_STORE`'s posture one module over.
            "step": {
                "reached": None,
                "of": DISCONNECT_STEP_COUNT,
                "unavailable": dict(CASE_HAS_NO_WIZARD_STEP),
            },
        }
        for account in window
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
                positions=positions,
            )
            for park in park_window
        }
    )
    # Computed ONCE and read twice — the strip below and `open_case_count`
    # further down. Calling `kpi_strip` twice would double the one `O(tenant)`
    # read on this path (`DEF-CUS-5778`).
    kpis = kpi_strip(as_of=on, protected=protected)
    # Three statements, and `protected` is the list already in hand — see
    # `state_counts` for why an option's count is the whole set.
    counts = state_counts(as_of=on, protected=protected)
    return {
        "rows": [built[key] for _kind, key in keys if key in built],
        "kpis": kpis,
        "page": page,
        "per": per,
        "total": total,
        "pages": (total + per - 1) // per if per else 0,
        "columns": list(COLUMNS),
        # CR-045 wave D task D.8 — the `f.<name>` vocabulary and the stored
        # states it accepts. `CASE_STATES` and not the six drawn SEGMENTS: the
        # segments are the unruled question, the states are the column.
        "filters": list(DISCONNECT_FILTERS),
        # …and the SORT names, on the same contract (`BR-CUS-1046` /
        # BR-SHL-010). TWO, and `SORTS` says why it is not four.
        "sorts": list(SORTS),
        "sort": sort if sort in SORTS else DEFAULT_SORT,
        "dir": dir,
        # `DEF-CUS-5994` — the two DRAFT codes join the vocabulary, each marked
        # `drawn: False` so no screen mistakes one for a B18 segment. They are
        # facts about a `wizard_parks` row rather than about a raised case,
        # which is why neither could reuse a stored case state.
        # ⚠ **EVERY OPTION CARRIES ITS COUNT — `DEF-CUS-6746`.** Six of these
        # eight answered zero and the screen offered all eight identically, so
        # a clerk could not tell a broken control from an empty view. One of
        # the six was genuinely broken (`on_hold`, fixed in `_list_queryset`);
        # the other five are true zeroes. `state_counts` says why the number is
        # the whole set rather than the searched one.
        "states": (
            [
                {"code": code, "drawn": True, "count": counts.get(code, 0)}
                for code in DISCONNECT_FILTER_STATES
            ]
            + [
                {
                    "code": DISCONNECT_STATE_IN_PROGRESS_DRAFT,
                    "label": "Draft",
                    "drawn": False,
                    "count": counts.get(DISCONNECT_STATE_IN_PROGRESS_DRAFT, 0),
                },
                {
                    "code": DISCONNECT_STATE_PARKED,
                    "label": "Parked",
                    "drawn": False,
                    "count": counts.get(DISCONNECT_STATE_PARKED, 0),
                },
            ]
        ),
        # ── PO 2026-09-20 · the `f.due` VOCABULARY ───────────────────────
        # ⚠ **SERVED, NEVER TYPED ON THE SCREEN** (`BR-SHL-010`). The values,
        # their words and their order are the server's, so a view this
        # deployment cannot answer can never be drawn as a chip — the trap
        # `DisconnectStateChips` §2 records for `on_hold`, which is drawn on
        # p142 and can never match a row.
        "dues": [
            {"code": code, "label": disconnect_due.DUE_FILTER_LABELS[code], "drawn": False}
            for code in disconnect_due.DUE_FILTER_VALUES
        ],
        # The applied value, echoed so a screen can light its own chip from the
        # response rather than from its local state (`DEF-664`'s posture).
        "due": str((filters or {}).get("due") or ""),
        "segment": segment,
        "segments": [
            {
                "code": code,
                "label": SEGMENT_LABELS[code],
                "supported": code == SEGMENT_ALL,
                "unavailable": None if code == SEGMENT_ALL else dict(SEGMENT_PRECEDENCE_UNRULED),
            }
            for code in SEGMENTS
        ],
        "chips": [
            {"code": chip, "label": CHIP_LABELS[chip], "tone": CHIP_TONES[chip]}
            for chip in TIER_CHIPS
        ],
        "search": {
            "hint": SEARCH_HINT,
            # `CR-125-BRC07` — `case_no` LEADS, because it is the list's first
            # column and the identifier a customer reads off a letter. The
            # prompt and this tuple are one fact; see `SEARCH_HINT`.
            "legs": ("case_no", "customer", "account_no", "address", "meter_no"),
        },
        # ── `CR-125-BRC07` · THE PAGE SUB-LINE'S COUNT ───────────────────
        # The drawing's sub-line reads `10 tabs · Disconnects · N open cases`
        # and the screen rendered `10 tabs · Disconnects` — the count was
        # OMITTED, not zeroed, because nothing served one. B14 rule 37: the `3`
        # drawn is an illustration; what is required is that a count exists.
        #
        # ⚠ **IT IS NOT `total` ABOVE.** `total` counts the ROWS of this list,
        # and §4 makes those rows a UNION of open cases and accounts carrying a
        # protection — an account on a medical hold with no case raised is a ROW
        # and is not an OPEN CASE. Serving `total` under the words *open cases*
        # would overstate, on the tab that authorises cutting people off.
        #
        # ⚠ **AND IT IS NOT THE KPI TILES ADDED UP EITHER, WHICH IS WHAT THIS
        # LINE SAID FIRST AND WAS WRONG.** `at_notice + cut_awaiting_payment +
        # reconnections_due` looks free — the strip has already counted them —
        # and the three ARE disjoint. **They are not exhaustive.** `at_notice`
        # is gated on `ladder_tier_of(case) in LADDER_TIERS`, and `open_case`
        # creates a case with `tier=None` (nothing has been sent yet), while
        # `TIER_UNMAPPED` is a real value for payments' `second_5_day` rung. So
        # a case raised this morning, and every case on the unmapped rung, would
        # have been counted by NO tile and silently missing from the sub-line —
        # undercounting the open work on the collections tab.
        #
        # **The honest definition is this list's own:** `open_cases()` is *a
        # case that has not left this list* (§5.8.3), which is exactly what the
        # words *open cases* mean. `.count()` is ONE `SELECT COUNT(*)` and
        # returns no row to Python (`NFR-3`) — cheaper than the tiles, not
        # dearer.
        "open_case_count": open_cases().count(),
        "delivery": dict(disconnects.DELIVERY_UNAVAILABLE),
        "scheduler": dict(disconnects.NO_SCHEDULER),
        "as_of": on.isoformat(),
    }

# ════════════════════════════════════════════════════════════════════════════
# CR-125-BRC07 · THE LIST'S EXPORT — `⇩ Export` HAD NO RESOURCE BEHIND IT
# ════════════════════════════════════════════════════════════════════════════
# The drawing puts `⇩ Export` beside the column picker and the control rendered
# nothing — correctly, because **no export resource was registered for this
# list**, and a front end will not wire a button to a 404. `apps/customers`
# registers NO exporter at all: `CustomersConfig.ready()`'s own lifecycle note
# says so in as many words (*"No exporter is registered"*), which has been true
# since 2026-08-10.


#: The CSV's columns — the LIST's own nine, minus the two a file cannot hold.
#:
#: ⚠ **THE CHIP AND THE ACTIONS ARE NOT COLUMNS.** `apps/assets/exports.py`
#: states the rule this follows, verbatim: *"a CSV has no selection and no
#: buttons, and writing the server's `actions` array into a file would export UI
#: affordances as if they were data."* `tier` and `state` are served to the
#: screen as CHIP OBJECTS — a code, a label and a TONE — so the file takes the
#: code and leaves the tone, which is a rendering instruction.
#:
#: ⚠ **`owed` IS MONEY AND IS WRITTEN AT 2dp WITH NO SYMBOL** (IS-9's `MONEY`
#: kind). The served cell is a `{stored, display}` pair — hard rule 2 — and the
#: file takes the STORED figure through the money formatter rather than the
#: display string, so a spreadsheet gets a number and not a pre-formatted label.
#: When the ledger could not be asked, the cell is **empty** and never `0.00`:
#: `DEF-127`'s whole lesson is that an absence spelled like a zero reads as a
#: settled account, and it reads that way in a CSV too.
#:
#: ⚠ **`case_no` LEADS.** It is the list's first column, the identifier a
#: customer reads off a letter, and — since this CR — the one the search box
#: finds. A file whose first column is a uuid would be B14 rule 31 in CSV form.


def _export_money(cell: Any) -> Any:
    """The STORED figure out of a `{stored, display}` money cell, or empty.

    `None` — not `0` — when the ledger could not be asked. See the note above:
    a zero in a collections export reads as a customer who owes nothing.
    """
    if not isinstance(cell, dict):
        return None
    return cell.get("stored")


def _export_tier(cell: Any) -> Any:
    """The TIER CODES out of `chips_for`'s served object — never labels, never tones.

    ⚠ **A ROW CAN CARRY MORE THAN ONE AND THE FILE SAYS SO.** §3's segment
    precedence is unruled, so `chips_for` serves a LIST and flags `ambiguous`;
    collapsing it to the first chip here would make the file state a tier the
    list itself refuses to state. They join with the kernel's own
    `MULTI_VALUE_SEPARATOR` (IS-9's `LIST` kind) rather than with a comma, which
    a CSV would split on.
    """
    chips = (cell or {}).get("chips") if isinstance(cell, dict) else None
    codes = [
        str(chip.get("code")) for chip in (chips or []) if isinstance(chip, dict) and chip.get("code")
    ]
    return codes or None


def _export_state(cell: Any) -> Any:
    """The STORED state out of `state_cell` — the case's own column.

    `state_cell` serves `stored` (the `disconnect_cases.state` column) beside
    `held_by` (the DERIVED hold), and it flags when the two collide. The file
    takes the stored one and `held_by` rides its own column, because merging a
    stored fact and a derived one into one cell is exactly the unruled
    precedence §3 refuses to take.
    """
    return (cell or {}).get("stored") if isinstance(cell, dict) else cell


class DisconnectExportSelection:
    """The list's rows, **streamed a page at a time** — `NFR-3` in a file.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  AN EXPORT IS THE ONE PLACE A PAGED LIST QUIETLY STOPS BEING PAGED   ║
    ╚══════════════════════════════════════════════════════════════════════╝
    The obvious implementation asks the selector for every row and hands the
    list to the kernel. That is `DEF-CUS-5755` returning through a door nobody
    is watching: the LIST takes its page in SQL and the EXPORT of the same list
    would build all of it in memory. At the top of `T5` this tab's row set is
    open cases plus accounts on a hold, and nothing caps it (`NFR-5`).

    **So this object is the selection, and it pages.** The kernel's contract is
    exactly two methods — `selection_count` calls `len()` on a non-QuerySet and
    `selection_iter` calls `iter()` — so a class with `__len__` and `__iter__`
    satisfies it with no change to the kernel and no new code path in it.

    ⚠ **`__len__` IS THE SQL `COUNT`, NOT `len(list(self))`.** The count is
    taken before a single row is built, because the kernel asks for it FIRST
    (to refuse over the cap and to set the job's progress total) and an
    implementation that materialised the rows to count them would have paid the
    whole cost before the first page was written.

    ⚠ **IT REUSES `list_disconnects` AND DOES NOT RE-QUERY.** The file and the
    screen are then one derivation seen twice. A second query shaped "like" the
    list is how an export and a list end up disagreeing about which accounts
    were on a tab the day somebody was cut off.

    ⚠ **THE PAGE SIZE IS `MAX_PER` AND IS NOT A CAP.** It is how many rows are
    held in memory at once, not how many are written; the iterator keeps going
    until the pages run out.

    ⚠ **WHAT REUSING THE LIST COSTS, MEASURED RATHER THAN GLOSSED.**
    `list_disconnects` builds its KPI strip on every call, and that strip is
    `O(open cases)` by design (`DEF-CUS-5778`) — so an export of `N` rows pays
    it `ceil(N / 1000)` times. **On every tenant whose tab is 1,000 rows or
    fewer that is exactly once, which is the same cost as opening the screen.**
    A tenant at the top of `T5` with 3,000 open cases pays it three times for
    one file. That is accepted rather than optimised away, because the
    alternative is a second row-building path — and a file that disagrees with
    the screen about which accounts were on a collections tab is worth more than
    two redundant counts.

    ⚠ **THE TOTAL IS RE-READ ON EVERY PAGE AND THE STREAM STOPS ON A SHORT
    PAGE, WHICH IS DELIBERATE.** Rows can be added or a case stopped WHILE a
    file is being written — this is a live tab — and a fixed page count taken at
    the start would either miss the tail or walk off the end. Stopping on a page
    shorter than `per` is the one condition that is true in both directions.
    """

    def __init__(self, params: Any, *, as_of: date | None = None) -> None:
        self._params = params
        self._as_of = as_of
        self._total: int | None = None

    def _page(self, page: int) -> dict[str, Any]:
        return list_disconnects(
            q=self._params.q or None,
            filters=dict(self._params.filters or {}),
            sort=self._params.sort,
            dir=self._params.dir or DEFAULT_DIR,
            page=page,
            per=MAX_PER,
            as_of=self._as_of,
        )

    def __len__(self) -> int:
        if self._total is None:
            self._total = int(self._page(1)["total"])
        return self._total

    def __iter__(self) -> Any:
        page = 1
        while True:
            body = self._page(page)
            rows = body["rows"]
            self._total = int(body["total"])
            yield from rows
            if len(rows) < MAX_PER:
                return
            page += 1


def _disconnects_select(params: Any) -> DisconnectExportSelection:
    return DisconnectExportSelection(params)


def register_export() -> None:
    """Register `disconnects` with the tenancy export kernel.

    ⚠ **THE RIGHT HOME FOR THIS CALL IS `CustomersConfig.ready()`, WHICH IS ONE
    LINE IN A FILE THIS LANE MAY NOT EDIT — SO IT IS CALLED AT THE BOTTOM OF
    THIS MODULE AND REPORTED.** `apps/customers/apps.py` is another lane's, and
    `apps/customers/disconnects.py` already takes exactly this posture for its
    own missing `ready()` line (its lifecycle exception 1). Every other module
    registers from `ready()` and this one should too.

    **What the module-import placement costs, stated rather than glossed:**
    `ready()` runs in EVERY process; a module-level call runs only where the
    module is imported. `apps/customers/api.py` imports this module at the top
    and is loaded by `config/urls.py`, so it is registered in any process that
    can serve a request — which includes the one that accepts the export, since
    accepting it is a request. **A job worker that never loads the URLconf would
    not have it**, and the kernel's own comment says that case is reachable
    (*"only reachable if a module were unregistered between accept and run"*).
    On this deployment jobs run in-process, so it is registered wherever it is
    needed today; the one line in `ready()` is what makes that true by design
    instead of by deployment shape.

    **Re-registration REPLACES and is logged** (the kernel's own behaviour), so
    importing this module twice is safe.

    ⚠ **THE SORT AND FILTER VOCABULARY IS THE LIST'S OWN, PASSED BY REFERENCE
    RATHER THAN RETYPED**, for `apps/assets/exports.register`'s stated reason:
    the export can then never honour a sort or a filter the list itself ignores.

    ⚠ **`EXPORT_ROW_CAP` IS THE KERNEL'S AND IS NOT NARROWED HERE.**
    `BR-SHL-016` measures 100,000 rows at accept time so no partial file can
    exist. That is a platform rule, not this list's: at the top of `T5` a tenant
    has 40,000 ACCOUNTS and this tab's rows are the subset carrying an open case
    or a hold, so the cap is above anything this resource can select. It is
    named here because `NFR-5` forbids a cap and a reader is owed the
    measurement rather than a silence.
    """
    from apps.tenancy import exports as export_kernel
    from apps.tenancy.exports import ExportColumn, ExportResource

    export_kernel.register_export_resource(
        ExportResource(
            name="disconnects",
            slug="disconnects",
            module="customers",
            select=_disconnects_select,
            columns=(
                ExportColumn("case_no", "case_no"),
                ExportColumn("account_no", "account_no"),
                ExportColumn("customer", "customer"),
                ExportColumn("address", "address"),
                ExportColumn("owed", lambda row: _export_money(row.get("owed")), "money"),
                ExportColumn("currency", lambda row: (row.get("owed") or {}).get("currency")),
                ExportColumn("tier", lambda row: _export_tier(row.get("tier")), "list"),
                ExportColumn("cut_date", "cut_date", "date"),
                # The date the LAST notice was ISSUED. ⚠ Not "delivered" — the
                # served cell carries `delivery_state` and it is NULL on every
                # row by design (`DELIVERY_UNAVAILABLE`, `DEF-692`); a column
                # named `delivered` in a file a regulator may read would be the
                # one fabricated fact in it.
                ExportColumn(
                    "last_notice_issued",
                    lambda row: (row.get("last_notice") or {}).get("issued_on"),
                    "date",
                ),
                ExportColumn(
                    "last_notice_tier", lambda row: (row.get("last_notice") or {}).get("tier")
                ),
                ExportColumn("state", lambda row: _export_state(row.get("state"))),
                # The DERIVED hold, in its own cell — see `_export_state`.
                ExportColumn(
                    "held_by", lambda row: (row.get("state") or {}).get("held_by"), "list"
                ),
                # ⚠ **`ladder_runs` IS NOT ON THE SCREEN AND IS ON THE FILE, ON
                # PURPOSE.** The tab renders it as the row's tone; a CSV has no
                # tone, and *is this household still being chased* is the one
                # fact somebody opens this file to answer.
                ExportColumn("ladder_runs", lambda row: (row.get("ladder") or {}).get("runs")),
                ExportColumn(
                    "halt_reason", lambda row: (row.get("ladder") or {}).get("halt_code")
                ),
            ),
            sorts=tuple(SORTS),
            default_sort=DEFAULT_SORT,
            default_dir=DEFAULT_DIR,
            filters=DISCONNECT_FILTERS,
        )
    )


register_export()



# ════════════════════════════════════════════════════════════════════════════
# CR-125-BRC07 · WHAT THE FIVE DRAWN WIZARD SCREENS ASK THE SERVER FOR
# ════════════════════════════════════════════════════════════════════════════
# The Accounts Menu Blueprint draws the disconnect wizard on pages 135–141 and
# every figure on those pages is an ILLUSTRATION (B14 rule 37), so nothing here
# is built to a drawn number. What is built to is the SHAPE: which facts a
# clerk is shown before they cut somebody off, and which of them this product
# can actually answer.
#
# ⚠ **THE READS BELOW AUTHOR NO RULE.** Every figure is the owning module's
# own — the ledger's balance, billing's bills, payments' plan, rating's charge
# code, `disconnects.py`'s ladder. This file reshapes and pages them; it
# computes no money and takes no decision. The one thing it DOES decide is what
# to say when a fact cannot be had, and the answer is always the same: an
# absence with a reason, never a zero and never a blank (DEF-127's lesson,
# stated in `selectors._balance_cells` and not re-argued here).


#: ⛔ **`Case raised by` IS DRAWN AND HAS NO DURABLE SOURCE — `OQ-CUS-12517`.**
#:
#: p136 draws, in the ladder panel, `Case raised by · S. Ortiz · 04/14/2026`.
#: Measured on this tree 2026-09-20: `disconnect_cases` has **no actor column**
#: — `case_no · account · sequence · state · tier · tier_reached_on ·
#: amount_owed_at_open · currency · opened_on · next_step_due ·
#: cut_scheduled_for · cut_on · reconnected_on · cut_reason · services_cut ·
#: reconnection_fee_* · deposit_disposition · stopped_on · stopped_reason ·
#: closed_out_* · request_id` and nothing else. `open_case` DOES name the actor
#: — `_audit(actor, AUDIT_CASE_OPENED, …)` — so the fact exists TODAY in
#: `audit_log`.
#:
#: ⚠ **AND THAT IS WHY THIS IS A QUESTION RATHER THAN A ONE-LINE READ.**
#: `audit_log` is PRUNED on a retention schedule (CLAUDE.md hard rule 4's own
#: note, `OQ-1340`, OPEN). So an answer read from it is correct this month and
#: silently becomes `—` when the retention window passes it — on the panel that
#: justifies having cut a household's supply, which is precisely the record a
#: regulator asks about a year later. Whether *who raised this case* is a
#: display convenience (read audit, accept that it ages out) or a fact of the
#: case (a column, a migration, a backfill that cannot recover the rows audit
#: has already pruned) is a product judgment about the durability of a
#: regulator-facing record, and no signed document states it.
#:
#: **SO IT IS SERVED AS AN ABSENCE WITH ITS REASON AND NOTHING IS INVENTED.**
#: Not a column, not an audit read, not a blank. The prime directive's shape for
#: a read: implement to the boundary and name the question.
CASE_RAISED_BY_UNSOURCED: dict[str, Any] = {
    "code": "case_raised_by_has_no_durable_source",
    "oq": "OQ-CUS-12517",
    "br_ref": "CLAUDE.md hard rule 4 · `OQ-1340` · `DSC-02.1` (blueprint p136)",
    "detail": "who raised this disconnect case is drawn on the wizard's ladder panel and no "
    "column holds it. The actor IS named on the `disconnect.case.opened` audit row, and "
    "`audit_log` is pruned on a retention schedule, so a panel fed from there would answer "
    "correctly today and blank itself later on the screen that justifies a cut. Whether this "
    "becomes a column on `disconnect_cases` or stays a best-effort audit read is `OQ-CUS-12517` "
    "and is OPEN.",
}


#: ⚠ **`Oldest item — N days past due` HAS A SOURCE, AND IT IS NOT A NEW
#: COLUMN.** Recorded here because the opposite was believed.
#:
#: ⚠ AMENDED 2026-10-17 (`DEF-CUS-10181`): this read *"the ageing cell … is
#: computed from `account_opening_buckets` … and says the INVOICE half is not
#: wired"*. It is wired now — `selectors.ageing_cells` reads the oldest unpaid
#: bill's due date from payments' debtor statement as well as the buckets — so
#: the list's Aging band and the figure below are the same derivation.
#:
#: **It is answerable from the bills themselves.** Every issued, unsettled bill
#: carries `due_date` (billing, `BR-BIL-024`), and the oldest of them minus
#: `as_of` IS *days past due* — the identical derivation
#: `payments.outstandings` already publishes as `days_late`. `bills_behind_the_
#: balance` below computes it **over the same rows it returns**, so the figure
#: and the list that justifies it cannot disagree, which is the whole point of
#: the drawn caption *"Three unpaid bills reconcile to the balance exactly."*
OLDEST_ITEM_IS_DERIVED = (
    "days past due is the oldest DUE DATE among this account's issued, unsettled bills, "
    "measured against `as_of` — the same derivation payments publishes as `days_late`. It is "
    "computed over the rows this read returns and is never a stored column."
)

#: A bill's state as the drawn `STATE` column names it — two values, both
#: DERIVED from the bill's own due date against `as_of`, and neither stored.
BILL_STATE_OVERDUE = "overdue"
BILL_STATE_ISSUED = "issued"

#: ⚠ **THE ONE COST ON `bills_behind_the_balance` THAT IS NOT IN SQL, NAMED SO
#: IT CAN BE COUNTED RATHER THAN DISCOVERED** — the posture
#: `PROTECTED_HALF_IS_DERIVED` above takes for the same reason, and it is stated
#: as a constant rather than hidden in a docstring because a declared blind spot
#: with no NUMBER beside it is indistinguishable from an empty one (CLAUDE.md
#: hard-won law 7).
#:
#: **The PAGE is server-side and the client never receives more than `per` rows.
#: The ROW SET behind it is materialised by payments' seam before it is sliced**,
#: because *which bills are still open* is not a `WHERE` clause: a bill is open
#: when `amount_due − allocated > 0`, `amount_due` is billing's own per-bill
#: answer under `BR-BIL-072` (a budget bill is measured at its LEVEL, read off
#: that bill's frozen payload), and expressing that as SQL would be a second
#: implementation of a signed money rule — `DEF-2416`'s own warning, and the
#: bug it names is a customer chased for a variance they did not owe.
#:
#: **WHAT IT COSTS, MEASURED, AND IT IS NOT THE ACCOUNT COUNT:** the set is one
#: ACCOUNT's unsettled issued bills. A monthly utility ten years behind on one
#: account is 120 rows; the top of T5 is 40,000 ACCOUNTS and none of them is on
#: this read at once. It is `O(one account's open bills)` and never `O(tenant)`,
#: which is the distinction `NFR-3` exists to protect and `DEF-CUS-5755` was
#: about losing. **`NFR-5` is untouched: nothing here caps a row out of the set.**
BILLS_ROW_SET_IS_MATERIALISED = (
    "the page is taken in Python over one account's open bills, because 'still open' is "
    "amount_due minus allocated and amount_due is billing's own per-bill answer under "
    "BR-BIL-072 — not a column and not a WHERE clause. The set is O(one account's open "
    "bills), never O(tenant): no cap is applied and no row is dropped."
)


def _bills_read() -> Any:
    """payments' open-bill seam, resolved by name — never imported at module top.

    `disconnects._resolve` is this module family's one cross-module resolver and
    its reasoning is not re-argued: a module that is not deployed must report,
    not crash. The read itself is `apps.payments.billing_seam.open_invoices_for_
    account`, which already does the `amount_due − allocated` subtraction under
    `BR-BIL-072` (a budget bill is measured at its LEVEL, `DEF-2416`). Doing
    that subtraction a second time here would be the second implementation of
    one rule, which is how a list and a detail end up disagreeing about the
    same bill.
    """
    return disconnects._resolve("payments", "open_invoices_for_account", "billing_seam")


def _billing_queryset() -> Any:
    """billing's own published, tenant-scoped invoice queryset — for `due_date`.

    ⚠ **THE SEAM ABOVE DOES NOT CARRY A DUE DATE AND THE DRAWING HAS A COLUMN
    FOR ONE.** `payments.billing_seam.OpenInvoice` carries number · balance ·
    issued_on · total · amount_due · allocated · currency, and `_rows_from_
    billing` reads `due_on` off the invoice and then drops it on the way into
    the dataclass. Rather than widen another lane's Protocol, the due date is
    read here along the SAME reviewed cross-module edge (B2 §2) the seam itself
    falls back to — `apps.billing.selectors.invoice_queryset`, no billing model
    imported (G6 rule 4).
    """
    return disconnects._resolve("billing", "invoice_queryset", "selectors")


def bills_behind_the_balance(
    account_id: Any,
    *,
    as_of: date | None = None,
    page: int = 1,
    per: int = DEFAULT_PER,
) -> dict[str, Any]:
    """*"The bills behind that figure"* — blueprint p136, SERVER-PAGED.

    The drawn table is `BILL · ISSUED · DUE · AMOUNT · STATE` under the balance
    the cut is justified by, and its caption reconciles the two: *"Three unpaid
    bills reconcile to the balance exactly."* **Nothing called anything for this
    before `CR-125-BRC07`** — `GET /accounts/{id}/open-bills` (payments,
    `CR-059` CS-4) is the nearest thing and it serves no due date, no state and
    **no page**.

    ⚠ **`NFR-3` IS THE REASON THIS IS NOT A SECOND CALL TO THAT ROUTE.** A
    debtor at the top of `T5` can carry years of unpaid bills; a panel that
    materialises all of them to show a clerk the three that matter is the shape
    `DEF-PAY-4221` already files against `GET /outstandings`. So this pages, and
    `NFR-5` is honoured by there being no cap: `per` clamps to IS-2's
    vocabulary and never refuses a row that exists.

    ⚠ **THE PAGE IS A WINDOW OVER AN ORDER, NOT A FILTER.** Oldest first — the
    order `BR-PAY-001` allocates in and the order the drawing lists — so page 1
    is always the debt the ladder is actually running on.

    ⚠ **`total_open` IS STATED ONLY WHEN THE PAGE HOLDS EVERY ROW, AND THE
    ABSENCE IS DELIBERATE.** The drawn caption is a RECONCILIATION claim, and a
    sum taken over one page of several is not one — it would read as *the
    balance* beside a list that does not add up to it, on the screen that
    authorises a cut. Summing the whole set in SQL is not available either: a
    bill's open amount is `amount_due − allocated` where `amount_due` is
    billing's own per-bill answer under `BR-BIL-072`, and expressing that as an
    aggregate would be re-implementing a signed money rule in SQL
    (`DEF-2416`'s own warning). So a partial page answers `total_open: None`
    with `total_open_absence` beside it, and the screen states the ledger
    balance — which it already has — instead of a sum it cannot vouch for.

    Returns `{"account_id", "as_of", "bills", "page", "per", "total", "pages",
    "total_open", "total_open_absence", "currency", "oldest_due_on",
    "days_past_due", "problems"}`.
    """
    on = _as_of(as_of)
    page = max(1, int(page or 1))
    per = max(1, min(int(per or DEFAULT_PER), MAX_PER))

    read = _bills_read()
    if read is None:  # pragma: no cover - payments is present in this tree
        return {
            "account_id": str(account_id),
            "as_of": str(on),
            "bills": [],
            "page": page,
            "per": per,
            "total": 0,
            "pages": 1,
            "total_open": None,
            "total_open_absence": {
                "code": "payments_publishes_no_open_bill_read",
                "br_ref": "BR-PAY-001",
                "detail": "apps.payments.billing_seam.open_invoices_for_account is not "
                "published, so the bills behind this balance cannot be read. Nothing is "
                "summed on a guess and no empty list is shown as 'nothing is owed'.",
            },
            "currency": None,
            "oldest_due_on": None,
            "days_past_due": None,
            "problems": [],
        }

    position = read(account_id)
    invoices = list(position.invoices)
    problems = [dict(problem) for problem in position.problems]

    # ── the DUE date, along billing's own reviewed edge ──────────────────
    due_by_id: dict[Any, Any] = {}
    queryset = _billing_queryset()
    if queryset is not None and invoices:
        due_by_id = {
            row["id"]: row["due_date"]
            for row in queryset()
            .filter(pk__in=[invoice.invoice_id for invoice in invoices])
            .values("id", "due_date")
        }
    elif invoices:  # pragma: no cover - billing is present in this tree
        problems.append(
            {
                "code": "billing_publishes_no_invoice_read",
                "br_ref": "BR-BIL-024",
                "detail": "apps.billing.selectors.invoice_queryset is not published, so no bill "
                "on this list can state the date it fell due and none of them can be called "
                "overdue. The amounts are still the bills' own.",
            }
        )

    # ⚠ **OLDEST FIRST, AND THE TIE IS BROKEN — `NFR-3`'s other half.** The seam
    # returns issue order; two bills issued on one day would otherwise swap
    # between page 1 and page 2, showing a clerk one bill twice and another
    # never. The bill NUMBER is the total tiebreak, as `_page_keys` uses `id`.
    invoices.sort(key=lambda invoice: (invoice.issued_on, str(invoice.number)))

    total = len(invoices)
    pages = max(1, -(-total // per))
    start = (page - 1) * per
    window = invoices[start : start + per]

    # ── `Oldest item — N days past due`, over EVERY open bill and not the page
    # (`OLDEST_ITEM_IS_DERIVED`). A window would make the figure depend on which
    # page a clerk happens to be looking at.
    dues = [due_by_id.get(invoice.invoice_id) for invoice in invoices]
    dated = sorted(due for due in dues if due is not None)
    oldest_due_on = dated[0] if dated else None
    days_past_due = (on - oldest_due_on).days if oldest_due_on is not None else None

    bills = []
    for invoice in window:
        due_on = due_by_id.get(invoice.invoice_id)
        bills.append(
            {
                # B14 rule 31 — the bill NUMBER a clerk reads, never the uuid.
                "number": invoice.number,
                "issued_on": str(invoice.issued_on) if invoice.issued_on else None,
                "due_on": str(due_on) if due_on else None,
                # Hard rule 2 — 4dp stored, 2dp displayed, as a STRING, with its
                # CHAR(3) beside it. `disconnects._money` is the one formatter
                # this surface uses.
                "amount": disconnects._money(invoice.balance),
                "currency": invoice.currency,
                # ⚠ DERIVED, NEVER STORED, AND NULL IS A REAL ANSWER. A bill
                # with no due date is neither overdue nor safely `issued` — it
                # is a bill nobody can place, which is exactly what
                # `BR-PAY-001` refuses to order. The problem code above says so
                # once for the whole list.
                "state": (
                    None
                    if due_on is None
                    else (BILL_STATE_OVERDUE if due_on < on else BILL_STATE_ISSUED)
                ),
                "issued_total": disconnects._money(invoice.total),
                "allocated": disconnects._money(invoice.allocated),
            }
        )

    complete = total <= per and page == 1
    total_open = (
        disconnects._money(sum((invoice.balance for invoice in invoices), disconnects.ZERO))
        if complete
        else None
    )
    return {
        "account_id": str(account_id),
        "as_of": str(on),
        "bills": bills,
        "page": page,
        "per": per,
        "total": total,
        "pages": pages,
        "total_open": total_open,
        "total_open_absence": (
            None
            if complete
            else {
                "code": "sum_not_stated_over_a_partial_page",
                "br_ref": "NFR-3 · BR-BIL-072 · `DEF-2416`",
                "detail": f"this page holds {len(bills)} of {total} open bills, so the figures "
                "on it do not add up to the balance and no total is stated for them. The "
                "account's balance is the LEDGER's own Σ and is served beside this list; a sum "
                "over the whole set is not computed in SQL because a bill's open amount is "
                "billing's per-bill answer under BR-BIL-072, and an aggregate would be a second "
                "implementation of a signed money rule.",
            }
        ),
        "currency": (window[0].currency if window else None),
        "oldest_due_on": str(oldest_due_on) if oldest_due_on else None,
        "days_past_due": days_past_due,
        "oldest_item_basis": OLDEST_ITEM_IS_DERIVED,
        # The one cost on this read that is not in SQL, served as data so a
        # reader never has to take it on trust — `BILLS_ROW_SET_IS_MATERIALISED`.
        "row_set_basis": BILLS_ROW_SET_IS_MATERIALISED,
        "problems": problems,
    }


def _customer_facts(account: Any) -> dict[str, Any]:
    """`Customer` and `Customer kind`, walked from the account's own link.

    The blueprint's customer panel names the CUSTOMER (*"Bramble Bakery"*) and
    what kind of one it is (*"Company"*), and neither is on the account payload:
    `account_row` serves `customer_no` and a primary CONTACT's name, and
    `customers.kind` is served only on `GET /customers/{id}`. A wizard that
    made a second call for two strings would be two round trips before a clerk
    can read one panel.

    ⚠ **NULL IS A REAL ANSWER AND NEEDS NO REASON BLOCK.** An account with no
    `customer_accounts` link has no customer — every account created before
    `BR-CUS-054`'s entity landed is one — and `account_row` already takes that
    posture for `customer_no`, in those words. Nothing is invented from the
    contact name, which is a different fact about a different party.

    ⚠⚠ **IT GOES THROUGH `selectors.customer_for_account` AND DOES NOT QUERY
    `customer_accounts` ITSELF — THE FIRST DRAFT OF THIS FUNCTION DID, AND IT
    WAS THE EXACT REGRESSION `customers/0060` HAD JUST WARNED ABOUT.** Since
    that migration a property sale **ENDS** the seller's link rather than
    deleting it, so the link table holds former owners — and the obvious query
    (`filter(account_id=…).order_by("created_at").first()`) takes the OLDEST
    row, which after a sale is **the SELLER**. Measured by that lane on the
    property-sale suite: one unfiltered reader took it from *23 of 25 rows with
    nothing red* to **5 of 25**, `account_customer_is_the_buyer: want True, saw
    False` on nineteen scenarios.

    `CustomerAccount.objects` was deliberately left UNFILTERED so a default
    manager could not hide that regression, which means **every reader of this
    table must say so itself** — and this surface would have named the previous
    owner as the customer **on the panel that authorises cutting their supply
    off**. Calling the module's own reader is not tidiness here; it is the
    difference between disconnecting the right household and the wrong one.
    """
    from apps.customers import selectors

    customer = selectors.customer_for_account(account.id)
    return {
        "customer_name": (customer or {}).get("display_name"),
        "customer_kind": (customer or {}).get("kind"),
        "customer_no": (customer or {}).get("customer_no"),
    }


def _ladder_floor() -> dict[str, Any]:
    """`Ladder floor` — the tenant's own `BR-BIL-001` amount, or its absence.

    Drawn on p136 as *"$25.00 — this is well above it"*, which is a COMPARISON
    the screen makes between this figure and the balance beside it. The figure
    itself is the tenant's `ladder_balance_floor_amount` collections setting and
    is read through `disconnects`' own accessor, never re-read here — a second
    reader is a second default (`HALT_BELOW_FLOOR` is decided from that one).
    """
    settings = disconnects._collections_settings()
    floor = disconnects._decimal_setting(settings, disconnects.FLOOR_KEY)
    return {
        "amount": None if floor is None else disconnects._money(floor),
        "unavailable": (
            None
            if floor is not None
            else {
                "code": "ladder_floor_not_readable",
                "br_ref": "BR-BIL-001 as amended",
                "detail": "this tenant states no ladder balance floor, so the ladder's own halt "
                "on a trivial debt cannot be computed and is reported rather than assumed to be "
                "zero. `disconnects.halt_reason` refuses with the same code.",
            }
        ),
    }


def _payment_plan_cell(account_id: Any, *, as_of: date) -> dict[str, Any]:
    """`Payment plan` — payments' own answer, and *None* is one of them.

    ⚠ **THIS IS NOT THE PLAN PROTECTION.** `protection_check` answers whether a
    plan HOLDS the ladder (`BR-CUS-043`: active AND current); this row answers
    whether a plan EXISTS, which is what the drawn panel states. They disagree
    on exactly the account that matters — a plan whose instalment was missed
    yesterday still exists and no longer protects — so serving one under the
    other's name would put a clerk one word away from the wrong conclusion.
    """
    plans = seams.payment_plans_for(account_id, as_of=as_of)
    if plans is None:
        return {
            "plans": None,
            "unavailable": {
                "code": "payments_publishes_no_plan_read",
                "br_ref": "BR-CUS-043",
                "detail": "payments publishes no payment-plan read on this deployment, so "
                "whether this customer is on a plan cannot be answered. It is reported rather "
                "than shown as *None*, which is the answer a clerk would act on.",
            },
        }
    return {"plans": list(plans), "unavailable": None}


def wizard_account_panel(account_id: Any, *, as_of: date | None = None) -> dict[str, Any]:
    """STEP 1's customer panel and money panel — blueprint p135–p136, in ONE call.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  FIFTEEN FACTS IN FRONT OF A CLERK BEFORE THEY CUT ANYBODY OFF       ║
    ╚══════════════════════════════════════════════════════════════════════╝
    The drawing's `The customer` block is fifteen rows — account number ·
    customer · customer number · customer kind · category · account status ·
    opened · premises · unit · service address · contact · phone · preferred
    language · paperless billing · autopay — and its `The money` block is six
    more: balance · oldest item · deposit on file · last payment · payment plan
    · ladder floor.

    ⚠ **MOST OF THEM WERE ALREADY SERVED AND THIS ADDS ONLY WHAT WAS NOT.**
    Measured against `selectors.account_detail_dict` on 2026-09-20: thirteen of
    the fifteen customer facts travel on the account payload already
    (`account_no`, `customer_no`, `account_type` + `account_subtype_name`,
    `status_name` + `status_behavior_class`, `opened_at`, `premise` +
    `premises_id`, `unit_label` + `unit_id`, `premise_address` +
    `premise_locality`, `contacts`, `preferred_language`, `paperless`,
    `autopay`), and so do `balance` and `deposit_on_file`. **Two did not** —
    the CUSTOMER's own name and kind, which live on `customers` and are served
    only by `GET /customers/{id}` — and **four of the money rows did not**:
    days past due, the last payment, the payment plan and the ladder floor.
    This read carries exactly those six and repeats none of the others, because
    a second copy of a fact is a fact that can disagree with itself.

    ⛔ **ONE ROW CANNOT BE SERVED AT ALL** — `Case raised by`
    (`CASE_RAISED_BY_UNSOURCED`, `OQ-CUS-12517`). It is drawn as an absence with
    its reason and nothing is read from `audit_log` to fill it.

    Read-only. No clock (`as_of` is an argument, `BR-TEN-043`), no money
    arithmetic beyond the formatter, no write.
    """
    from apps.customers import selectors

    on = _as_of(as_of)
    account = selectors.account_or_404(account_id)
    facts = _customer_facts(account)
    return {
        "account_id": str(account.id),
        "as_of": str(on),
        # ── the two customer facts the account payload does not carry ──
        "customer": facts,
        # ── the four money rows it does not carry ──
        "ladder_floor": _ladder_floor(),
        "payment_plan": _payment_plan_cell(account.id, as_of=on),
        "last_payment": _last_payment(account.id),
        # `days_past_due` and `oldest_due_on` ride on the BILLS read, over the
        # rows that justify them — see `OLDEST_ITEM_IS_DERIVED`. They are named
        # here so a caller knows which call answers them rather than finding a
        # missing key.
        "oldest_item": {
            "served_by": "GET /accounts/{id}/disconnect-bills",
            "basis": OLDEST_ITEM_IS_DERIVED,
        },
        # ── the drawn row nothing can answer ──
        "case_raised_by": None,
        "case_raised_by_unavailable": dict(CASE_RAISED_BY_UNSOURCED),
    }


def _last_payment(account_id: Any) -> dict[str, Any]:
    """`Last payment` — its AMOUNT and its DATE, which the drawing shows together.

    ⚠ **PAYMENTS' OWN ROWS, READ ALONG THE REVIEWED EDGE (B2 §2), AND NOT
    `outstandings`.** `payments.outstandings` already derives a
    `last_payment_on` for the debtor list, and it derives only the DATE —
    `Max(posted_at)` over an account's payments. The drawing shows *"$180.00 ·
    03/02/2026"*, so the amount travels with it, which means the ROW and not an
    aggregate.

    ⚠ **A PROCESSING PAYMENT IS NOT A PAYMENT YET** — the same exclusion
    `outstandings` makes, for the same reason: money that has not settled has
    not reduced anybody's debt, and showing it on the panel that justifies a cut
    would tell a clerk a customer has paid when the bank has not said so.
    """
    from apps.payments import balance_rule
    from apps.payments import models as payment_models

    row = (
        payment_models.Payment.objects.filter(tenant_id=_tenant_id(), account_id=account_id)
        # CR-186-BRC10: a receipt that stands — posted or cleared; never a
        # cancelled, failed or processing one (`DEF-PAY-10340`).
        .filter(status__in=balance_rule.RECEIPT_STATUSES)
        .order_by("-posted_at", "-created_at", "-id")
        .first()
    )
    if row is None:
        # A real measured fact and not an absence: this account has never paid.
        return {"amount": None, "posted_on": None, "method": None, "never_paid": True}
    return {
        "amount": disconnects._money(row.amount),
        "currency": getattr(row, "currency", None),
        "posted_on": row.posted_at.date().isoformat() if row.posted_at else None,
        "never_paid": False,
    }


def wizard_review(account_id: Any, *, as_of: date | None = None) -> dict[str, Any]:
    """STEP 5's review — blueprint p140–p141, in ONE call.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  EIGHT NOTICE-AND-PROOF FACTS THAT WERE SERVED AT THE NOTICES READ   ║
    ║  AND NEVER AT THE REVIEW                                             ║
    ╚══════════════════════════════════════════════════════════════════════╝
    The drawn `The notice` block is eight rows — tier · final notice written ·
    going out by · delivery confirmed · served by · proof reference · signed
    for on · proof recorded by — and every one of them is a fact this module
    already holds. **None of them reached the review.** `GET /accounts/{id}/
    disconnect-notices` serves the rows (`DEF-CUS-5169`) and step 3 reads it;
    step 5 re-draws the same eight as a summary and had to have been given them
    by the front end carrying them forward across four steps — which is a
    wizard remembering a legal fact instead of re-reading it.

    **So the review re-reads.** `service_proof_for` is the SAME function that
    governs whether a cut may be scheduled at all (`assert_service_proved`), so
    the summary a clerk confirms and the guard that lets them confirm it cannot
    drift apart. That is the whole reason this is one call rather than five.

    ⚠ **`Delivery confirmed` IS AN ABSENCE AND STAYS ONE.** `DELIVERY_
    UNAVAILABLE` (`DEF-692`) rides the payload verbatim: nothing in this
    product delivers a notice, and the drawn row says so in the drawing too
    (*"— nothing here delivers"*). A review that printed `Delivered` would be
    the one fabricated fact on the screen that authorises a cut.

    ⚠ **`Going out by` IS THE CHANNEL SET, AND IT IS THE SEND AND NOT THE
    PROOF.** p138 states the split in its own words — *"Sending and proving are
    two different records, and only one of them is ours"* — so the channels a
    notice went out on and the channel it was SERVED by are two keys, never one.

    Returns the five steps' facts under the drawn headings: `account`,
    `protections`, `notice`, `date`, `money`, `case`.
    """
    on = _as_of(as_of)
    case = disconnects.open_case_for(account_id)
    proof = (
        None
        if case is None
        else disconnects.service_proof_for(case, tier=disconnects.TIER_3)
    )
    notices = list(disconnects.notices_for_account(account_id))
    final = next((row for row in notices if row["tier"] == disconnects.TIER_3), None)
    return {
        "account_id": str(account_id),
        "as_of": str(on),
        "case": None if case is None else disconnects.case_payload(case),
        # ── `Protections` (step 2) — the three checks and the seven that cannot
        # be answered, as step 2 itself states them. `all_clear` travels under
        # its own name and a screen must NOT render it as a clean check: seven
        # of the ten questions are unasked (`account_protections`'s docstring).
        "protections": disconnects.protection_check(account_id, as_of=on),
        # ── `The notice` — the eight drawn rows, from the two reads that own
        # them. Nothing is carried forward from an earlier step.
        "notice": {
            "tier": None if case is None else disconnects.ladder_tier_of(case),
            "notices": notices,
            "final_notice": final,
            "final_notice_written_on": None if final is None else final["issued_on"],
            # `SERVICE_CHANNELS` is the SEND vocabulary; the proof's own channel
            # is `proof["channel"]` below and they are deliberately separate.
            "channels": list(disconnects.SERVICE_CHANNELS),
            "proof": proof,
            "delivery": dict(disconnects.DELIVERY_UNAVAILABLE),
        },
        # ── `The date` — the earliest lawful cut, what it is counted from, and
        # whether it is locked. `disconnects` owns the arithmetic; this reshapes.
        "date": {
            "scheduled_for": (
                None
                if case is None or case.cut_scheduled_for is None
                else str(case.cut_scheduled_for)
            ),
            "scheduler": dict(disconnects.NO_SCHEDULER),
        },
        # ── `The money` — step 4's quote, re-read rather than remembered.
        "money": disconnects.reconnection_terms(account_id, case=case),
        # ── `What happens when you confirm` — the acts, in the module's own
        # words. `CUT_WILL` / `CUT_WILL_NOT` are `DSC-02.4`'s two columns and
        # carry their own supersession stamps; nothing is reworded here.
        "on_confirm": {
            "will": list(disconnects.CUT_WILL),
            "will_not": list(disconnects.CUT_WILL_NOT),
            "base_charges": dict(disconnects.CUT_STOPS_BASE),
        },
    }


def schedule_readiness(account_id: Any, *, as_of: date | None = None) -> dict[str, Any]:
    """`DEF-CUS-7680` — the refusals `schedule_cut` can ALREADY answer on step 1.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  A CLERK FILLED FOUR STEPS FOR A CASE THAT COULD NEVER BE SCHEDULED  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `POST /disconnects/schedule` refuses at the END of the wizard. Four of the
    reasons it refuses for are decided by the CASE, which is chosen on step 1
    and does not change while the clerk types: **no open case · the cut is
    already recorded · a COLLECTIONS sequence or a closed account · the case is
    below TIER 3**. Every one of them is as true before the four steps as
    after, and on the deployed build every one of them cost a clerk four steps
    and then said nothing they could act on.

    ⚠ **IT IS `disconnect_record.cut_readiness`'s SHAPE, DELIBERATELY, AND FOR
    THE SAME REASON.** That function previews `commit_cut`; this one previews
    `schedule_cut`. Both call the WRITER's own predicates and guards — never a
    paraphrase of them — so a rule amended in `apps/customers/disconnects.py`
    moves both screens at once. The two are separate because they answer
    different questions about different acts: `cut_readiness` asks *may this
    scheduled cut be RECORDED today*, and this asks *may a cut be SCHEDULED on
    this case at all*.

    ⚠ **IT IS A PREVIEW AND NOT A GATE, AND `schedule_cut` IS UNCHANGED.** The
    commit re-runs every one of these inside its own transaction, plus the
    payload checks, the ladder halt and the certified-proof channel — days pass
    between a screen being drawn and a button being pressed, and a screen that
    decided eligibility for itself would be the next defect. Nothing here
    writes, and a `ready: True` here is not permission.

    ⚠ **THE ORDER IS `schedule_cut`'s OWN ORDER AND THAT IS WHAT MAKES
    `refusal` HONEST.** The commit stops at the FIRST refusal, so the first
    blocker here is the sentence the clerk would really have been given. The
    rest travel beside it because a clerk told one thing at a time makes four
    trips (`cut_readiness`'s own words).

    ⚠ **`detail` IS FOR THE LOG AND THE AUDIT ROW, NEVER FOR THE SCREEN**
    (`BR-SHL-020` r2, `DEF-322`): the clerk-facing sentence is the catalogue's,
    keyed by `code`. That is the same split `_as_catalog_refusal` already
    publishes on the refusal itself, and it is why this payload leads with the
    code rather than with the words.

    ⚠ **WHAT IS DELIBERATELY *NOT* PREVIEWED HERE.** The payload refusals
    (`cut_reason_unknown`, `deposit_disposition_unknown`,
    `service_treatment_unknown`, `service_code_unknown`,
    `restrictor_is_a_third_state`) depend on what the clerk has not typed yet;
    the ladder halts (`protected`, `nothing_owed`, `below_ladder_floor`, …)
    already ride on `ladder_state` beside this, on the same payload; and
    `tier_3_proof_not_certified` is step 3's own fact, which the notices read
    serves. Previewing those here would be a second answer to a question
    another read already answers exactly.

    Read-only. No clock (`as_of` is an argument, `BR-TEN-043`), no write.
    """
    on = _as_of(as_of)
    blockers: list[dict[str, Any]] = []

    def _refused(fn: Any) -> None:
        try:
            fn()
        except disconnects.DisconnectRuleError as refusal:
            blockers.append(
                {"code": refusal.code, "br_ref": refusal.br_ref, "detail": str(refusal)}
            )

    case = disconnects.open_case_for(account_id)
    if case is None:
        blockers.append(
            {
                "code": "no_open_case",
                "br_ref": "BR-CUS-039",
                "detail": (
                    "there is no open disconnect case on this account to schedule a cut for."
                ),
            }
        )
    else:
        # ⚠ **`already_cut`, NOT `state == STATE_CUT` — `DEF-CUS-6062`.** The
        # writer's own predicate, so a row reading `scheduled` while carrying a
        # `cut_on` — the record the walk-around left on `A-11340` — is caught
        # here exactly as `schedule_cut` catches it.
        if disconnects.already_cut(case):
            blockers.append(
                {
                    "code": "already_cut",
                    "br_ref": "BR-CUS-039",
                    "detail": (
                        f"this account was already cut on {case.cut_on}, so there is no cut "
                        "left to schedule on this case."
                    ),
                }
            )
        # BR-CUS-082, BOTH of its grounds, lifted from the guard rather than
        # restated: a COLLECTIONS sequence and a closed account.
        _refused(lambda: disconnects.assert_cut_reachable(case))
        # ⚠ `ladder_tier_of` and not `case.tier` — it is THE one place that
        # answers "which tier is this case on", so folding the column into
        # payments' `account_collection_state` stays a move rather than a
        # redesign (that function's own docstring).
        if disconnects.ladder_tier_of(case) != disconnects.TIER_3:
            blockers.append(
                {
                    "code": "cut_before_final_tier",
                    "br_ref": "BR-CUS-039",
                    "detail": (
                        "a cut is scheduled after TIER 3 · 48-HOUR, the certified final "
                        f"notice. This case is at {disconnects.ladder_tier_of(case)!r}."
                    ),
                }
            )

    return {
        "account_id": str(account_id),
        "as_of": str(on),
        "ready": not blockers,
        "blockers": blockers,
        "refusal": blockers[0] if blockers else None,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030 W7 task 7.11 (S90 disconnects tab — backend half) — B18 §5.8.1 ·
#         §5.8.2 · §5.8.3 · §5.8.5 · §5.8.6 · apps/customers/disconnects.py ·
#         OQ-366 · J08 step 2b
# generated: 2026-08-25 by lane A-W7 (W7 worklist selectors)
# checklist: A✔ B=deferred(no-frontend-half — S90's rendering is task 7.11's
#         frontend lane) C✔ D=deferred(no API half — `GET /disconnects` is
#         REPORTED with its exact handler; api.py is another lane's file)
#         E=deferred F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) FIVE OF SIX SEGMENTS REFUSE — the drawn segments are not
#         mutually exclusive and no rule ranks them; an OQ is OWED and this
#         lane may not mint one. (2) The TIER cell serves a LIST of chips, and
#         flags ambiguity, for the same unruled precedence. (3) OQ-366 stays
#         open: no row names a chased party. (4) `LAST NOTICE` renders the
#         absence of a delivery adapter and never a fabricated `emailed`.
#         (5) `CUT, AWAITING PAYMENT`'s "still accruing base charges" caption
#         is a billing claim this module does not implement — flagged.
#         (6) No story owns S90 (hard-won law 8) — OWED.
#         (7) 2026-09-19, `DEF-CUS-5755` — the page and the total are SQL, and
#         TWO `O(tenant)` reads are deliberately kept rather than moved: the
#         DERIVED protected half of §4's union (`PROTECTED_HALF_IS_DERIVED`,
#         because a plan's liveness is payments' answer and not a column) and
#         `kpi_strip`, whose `AT NOTICE` tile goes through
#         `disconnects.ladder_tier_of` — the one place that answers "which
#         tier", which a `WHERE` clause would become the second of. Both are
#         measured in `tests/test_def_cus_5755_disconnects_list_pages_in_sql.py`
#         and the residue is filed as `DEF-CUS-5778`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
