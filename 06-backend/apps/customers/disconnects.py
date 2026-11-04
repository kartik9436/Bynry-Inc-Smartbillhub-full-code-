# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-015 (S22's disconnect-notice modal — the only story that
#           owns any part of this surface today)
#           Screens: S22 · S90 (the disconnects tab, CR-030 W7 · B18 §5.8)
#           ⚠ **NO STORY OWNS S90.** B18 proposes it and
#           `04-docs/05-modules/03-customers/06-epics/` stops short of it —
#           hard-won law 8, the same finding W4 filed for S83/S84/S85. A story
#           is OWED and is reported rather than invented here.
# Rules:    **BR-CUS-103** (PO 2026-08-25, closing OQ-380 — base charges STOP at
#           the cut; the boundary is the CUT date, not the notice date) ·
#           **BR-CUS-104** (PO 2026-08-25, closing OQ-381 — the reconnection fee
#           lands AT THE CUT: A-11340 clears $8,315.00, not $8,240.00 · NOT
#           BUILT, DEF-708) · **BR-CUS-105** (the two together make a cut
#           account's balance STATIC — A-11488 owes $687.75 on the cut date and
#           on any later day) ·
#           BR-CUS-100 (the SEND is in-app and the PROOF is a record a person
#           enters; **a tier-3 cut must not be schedulable on an unrecorded
#           service** — PO 2026-08-25, closing DEF-692) · BR-MET-110 (cited by
#           BR-CUS-100 as the same human-record discipline: *"somebody decided,
#           and the record must name them"*) ·
#           BR-CUS-039 (disconnect notice: tiers per A19 §2; certified mail
#           REQUIRED on the final; medical-hold accounts EXCLUDED; each send
#           appends `notice_history`) · BR-CUS-030 (move-out; its `dunning
#           stops` clause superseded for the closed-with-balance case) ·
#           BR-CUS-082 (a debt surviving closure is STILL CHASED and the ladder
#           RESTARTS AT TIER 1 — PO 2026-08-24, closing OQ-346) · BR-CUS-097
#           (a sub-account's residue moves to its MASTER — PO 2026-08-24; its
#           "who is chased" half is OPEN) · BR-CUS-043 (while a plan is active
#           AND current, dunning and disconnect pause) · BR-CUS-044 (a plan
#           activates on the customer's signature alone) · BR-PAY-016 as
#           amended 2026-08-12 (a partial payment pauses the ladder only at or
#           above a TENANT-SET percentage — OQ-136; a missed instalment lifts
#           the pause immediately — OQ-170; a bounce restarts it — OQ-133) ·
#           BR-PAY-017 (the tenant-config collection sequence) · BR-PAY-021
#           (on-time is judged on the POSTING date) · BR-PAY-036 (a payment is
#           ALWAYS accepted and acceptance NEVER auto-changes account status) ·
#           BR-BIL-001 as amended (the $25.00 balance floor governs the WHOLE
#           ladder — OQ-137 — per-utility, OQ-157) · BR-NOT-005 (a notice is
#           WRITTEN; only the dispatcher sends) · BR-TEN-043 (the event date is
#           an argument, never a wall clock) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money 4dp stored / 2dp displayed) · rule 4
#           (corrections are new rows) · rule 7 (audit)
# Tests:    **06-backend/tests/test_br_cus_105_static_balance.py (BR-CUS-103/104/
#           105 — the static-balance guard, on REAL priced bills)** ·
#           06-backend/tests/test_w7_disconnects.py ·
#           06-backend/tests/test_w7_proof_of_service.py (BR-CUS-100) ·
#           06-backend/tests/test_w7_cut_reconnect.py (7.8 · 7.9)
# Impacts:  **apps/customers/selectors.service_off_windows (the forwarder billing
#           resolves BY NAME) · apps/billing/gather.py (`_service_days` subtracts
#           the dark days; `GATHER_PARTIAL_CUT` refuses a partial cut) — NO
#           migration and NO new column: BR-CUS-103 is a READ, and `commit_cut`
#           still writes nothing to `accounts`** ·
#           apps/customers/migrations/0022_cr030_w7_disconnect_ladder.py (the
#           three tables and their RLS) ·
#           apps/customers/migrations/0023_cr030_w7_proof_of_service.py
#           (BR-CUS-100's six columns and two check constraints) ·
#           apps/customers/migrations/0024_cr030_w7_cut_reconnect.py (7.8/7.9's
#           five columns and three check constraints) ·
#           apps/rating/selectors.charge_by_code (the tenant's `CC-RECON` row —
#           BR-BIL-007, resolved BY NAME and never a literal) ·
#           apps/customers/move_out_settlement.py
#           (whose `DUNNING_AFTER_CLOSE` this module CONSUMES rather than
#           restates) · apps/payments/dunning.py + apps/payments/ladder.py (the
#           collection ladder that already exists — resolved BY NAME, never
#           re-implemented) · apps/payments/outstandings.py (whose stated
#           absence `medical_hold_not_readable` this module's
#           `medical_hold_for` is written to close) · apps/customers/apps.py
#           (ONE LINE OWED — see "WHAT THIS FILE NEEDS AND DOES NOT OWN")
# ───────────────────────────────────────────────────────
"""The disconnect case, its protections, and the ladder that stops itself.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-25 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). RLS policy,
tenant scoping and a customer-facing collections sequence are 🔒 paths on
CLAUDE.md's own list. A row in `12-governance/09-human-review-ledger.md` is
OWED — this lane does not own that file and reports the row rather than
writing it. Not RATIFIED without a recorded human sign-off.

⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT STATE.
A glob in 10-scripts/gates/human_owned.txt DOES match this file now: the PO
ruled on 2026-08-31, having been shown all 62 unguarded files in five groups,
that groups one to four go on the watched list — "56 files" in their own words
— and this file is one of them. G7 checks it from that commit. The paragraph is
kept because WHY it went unguarded is worth knowing (DEF-2790: the check
written to catch exactly this looked for the wrong marker for three days), and
nothing below it should be read as describing today.

⚠ **AND SINCE 2026-08-31 IT IS A MONEY PATH IN ITS OWN RIGHT, NOT ONLY A
COLLECTIONS ONE.** `commit_cut` now raises a customer-facing BILL at the cut
(CR-052 W0 task 1, PO ruling 2026-08-30) and writes the account status that
decides whether the account is billed again at all — so what this module does
decides what a disconnected customer owes. **No glob in
`10-scripts/gates/human_owned.txt` matches this file**, so G7 reports conform
over it; that file's own header calls changing it a process event and says a
lane may not add itself, so the glob is ASKED FOR in the review-ledger row of
2026-08-31 alongside `apps/billing/cut_bill.py`.

CR-030 W7 tasks 7.5 (the three tables + RLS), 7.6 (the ladder, and it stops
itself), 7.7 (the three protections and their lifetimes), 7.8 (**the cut**),
7.9 (**the reconnect**) and 7.16 (the post-closure ladder, BR-CUS-082).

════════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT A SECOND COLLECTION LADDER — READ THIS BEFORE ADDING ONE
════════════════════════════════════════════════════════════════════════════
**The collection ladder already exists and is built**: `apps/payments/ladder.py`
(US-PAY-014, BR-PAY-017) with `apps/payments/collections_models.py`'s
`account_collection_state` holding the tier and `notice_history` recording every
send AND every skip. It knows the balance floor, the medical hold, the plan
pause, the partial-payment percentage and the bounce restart, and its `decide()`
is PURE.

So this module **owns the CASE and the PROTECTIONS, and delegates the
DECISION.** Every stopper is asked of `apps.payments.dunning` /
`apps.payments.ladder` BY NAME through `_resolve`, the seam idiom
`apps/payments/dunning.py` itself uses in the other direction. Nothing here
re-derives a rule payments already implements, because a second implementation
of "does the ladder run" is a second answer, and the two disagree on the day one
of them is amended.

⚠ **AND THE OVERLAP THAT REMAINS IS REPORTED, NOT HIDDEN — THIS IS DEF-675's
SHAPE.** DEF-675 (2026-08-25) found B18 specifying `account_discounts` over a
`discount_enrolments` table built six days earlier, and *"building it as drawn
would have shown a customer a discount and billed them in full"*. Two of the
three tables B18 §6.3 asks for here sit close to tables payments already owns:

  * `disconnect_notices` vs payments' `notice_history` — both append-only, both
    tier-stamped, both per account.
  * `disconnect_cases.tier` vs payments' `account_collection_state.tier` — one
    row per account either way.

They are built here because B18 §5.8 draws a SERVICE-disconnection case with a
scheduled cut, a cut and a reconnect, none of which `account_collection_state`
models, and because W7 task 7.5 names all three. **Whether they should instead
be columns on the payments tables is a RULING THIS LANE DID NOT TAKE**, and it
is reported with DEF-675 named beside it. If the answer is "one table", the
`tier` column here goes and `ladder_tier_of` reads payments' state directly —
that is a move, not a redesign, which is why `ladder_tier_of` exists as the ONE
place that answers it.

════════════════════════════════════════════════════════════════════════════
THE TIER VOCABULARIES DO NOT LINE UP, AND THE GAP IS SERVED, NOT SMOOTHED
════════════════════════════════════════════════════════════════════════════
B18 §5.8.2 draws THREE tier chips:

    TIER 1 · REMINDER   TIER 2 · 10-DAY   TIER 3 · 48-HOUR

BR-PAY-017 (CONFIRMED, PO-delegated 2026-08-08) names FOUR rungs and
`apps/payments/collections_models.py` spells them:

    friendly · first_10_day · second_5_day · final_48_hour

**`second_5_day` HAS NO CHIP.** Mapping it onto TIER 2 would show a customer at
the 5-day notice as though they were at the 10-day one; mapping it onto TIER 3
would show them as though a 48-hour certified letter had gone out. Both are
statements to a regulator about what a customer was told. So `tier_for_rung`
returns `TIER_UNMAPPED` for that rung and the caller renders the absence — the
same posture `LAST NOTICE` takes for the delivery adapter it does not have.
**A ruling is OWED**: either B18 §5.8 grows a fourth chip or BR-PAY-017 loses a
rung, and neither is this lane's to choose.

════════════════════════════════════════════════════════════════════════════
7.6 — WHAT "IT STOPS ITSELF" MEANS HERE, AND WHY IT CANNOT BE FORGOTTEN
════════════════════════════════════════════════════════════════════════════
B18 §5.8.3, verbatim: *"If a customer pays or agrees a payment plan, the ladder
stops automatically and the row leaves this list. Nothing here has to be
cancelled by hand — the modal exists for clerk error, a dispute, or a regulator
instruction."*

The safety property is built as a STRUCTURE, not as a habit:

1. **Nothing stores "the ladder is running."** `halt_reason()` is COMPUTED on
   every call from the balance, the protections and payments' own pause
   decision. `apps/payments/dunning.py` states the reason in its own words —
   *"a pause cached on a row is a pause that outlives its reason"* — and the
   mirror is what matters here: a RUN cached on a row outlives the debt.
2. **Every advancing path funnels through one gate.** `advance()` and
   `record_notice()` both call `_require_running()` first, and there is no
   second door. A lane adding a third path adds it through the same call or the
   ladder is not the thing this docstring says it is.
3. **The absence of a reading STOPS the ladder.** If AR cannot be read, if the
   tenant's floor cannot be read, if the pause percentage is not stored — the
   ladder does NOT run and says which reading failed. Hard-won law 3: the unsafe
   option must be the one you type, and here the unsafe option is chasing.
4. **Nothing has to be cancelled.** There is no `stop()` for the ordinary case,
   because a stop that must be called is a stop that can be missed — which is
   exactly the customer who paid on Friday and got a certified letter on Monday.
   `stop_by_hand()` exists ONLY for §5.8.3's three named cases (clerk error, a
   dispute, a regulator instruction) and is audited as a human act.

**The test to trust is `TC-DSC-1`**: money posts, NOTHING is called, and the
next `ladder_state` refuses to advance. It proves the property by omission,
which is the only way this property can be proved — a test that calls a stop
function proves the opposite.

⚠ **BR-PAY-036 IS NOT CONTRADICTED.** *"Payment is ALWAYS accepted … acceptance
NEVER auto-changes account status — restoration stays an explicit, audited staff
action"*. Payment halting the LADDER is not payment restoring SERVICE: a CUT
account that pays moves to `reconnecting` and waits for a visit (B18 §5.8.6's
`A-11507`, owing $0.00, tier `—`, still on the tab). The ladder stops itself;
the meter does not turn itself back on.

════════════════════════════════════════════════════════════════════════════
7.7 — THREE PROTECTIONS, THREE DIFFERENT LIFETIMES, THREE DIFFERENT SHAPES
════════════════════════════════════════════════════════════════════════════
B18 §5.8.3, verbatim: *"Three protections, and each has a different lifetime: a
medical certificate expires · a payment plan holds while it is kept and voids
when it is not · a weather moratorium is a date window set by the regulator, not
by the tenant."*

They are NOT collapsed into one nullable date, and the database is what keeps
them apart (`ck_protection_lifetime`):

  * **`medical_certificate` — LIFETIME_EXPIRES.** `expires_on` is NOT NULL. A
    certificate with no end date is not a certificate; it is a permanent
    exemption nobody signed. BR-CUS-039 excludes the account from every step
    while it stands (A15), and `apps/notifications/rights_footer.py` already
    tells the customer in as many words that *"a medical hold is not permanent:
    the certificate has to be renewed"*.
  * **`payment_plan` — LIFETIME_DERIVED.** `expires_on` is NOT NULL-able: it is
    forbidden to be set. This protection has NO date of its own because
    BR-CUS-043 does not grant one — it holds *while the plan is active AND
    current* and lapses the DAY an instalment is missed (BR-PAY-016 as amended,
    OQ-170, *"Immediate"*, no grace). Its liveness is READ from
    `apps.payments.dunning.collections_pause_for` every time it is asked. A
    stored expiry here would be a second, slower answer to a question payments
    answers exactly.
  * **`weather_moratorium` — LIFETIME_WINDOW.** BOTH `effective_from` and
    `expires_on` are NOT NULL, and `set_by` defaults to `regulator`: the window
    is *"set by the regulator, not by the tenant"*, so the dates are recorded as
    given and the product does not compute them.

**A protection with no expiry and a protection that lapses are different
objects.** The check constraint is what makes that sentence true of the data and
not only of this docstring (hard-won law 1: a comment claiming a guarantee is
not the guarantee).

⚠ **B18 §5.8.4's STEP 2 LISTS FOUR CHECKS — *"medical · plan · moratorium ·
dispute"* — AND §5.8.3 SAYS THREE PROTECTIONS.** The fourth, DISPUTE, is not a
protection with a lifetime and it is not built: **nothing in this repository
stores a disputed AMOUNT** (J08 step 7b(i), measured 2026-08-24; BR-CUS-096
conditions on exactly that). `protection_check()` therefore serves the dispute
row as `unavailable` with that reason rather than as `pass`, because a green
"no dispute" derived from a table that does not exist is a fabricated clearance
on the screen that authorises a cut. ⚠ **`metering.disputed_at` on a meter read
is NOT this dispute** — that is a QUANTITY in dispute, and wiring it here would
hold a cut because somebody queried a dial (J08 7b names it as the obvious wrong
wire).

════════════════════════════════════════════════════════════════════════════
7.8 — THE CUT: FOUR CONSEQUENCES, THREE PROHIBITIONS, AND ONE OMISSION
════════════════════════════════════════════════════════════════════════════
`DSC-02.4`'s two columns are the specification and they are quoted verbatim in
`CUT_WILL` / `CUT_WILL_NOT` and again on `commit_cut`. The four things that make
this a CUT and not a move-out:

1. **The account stays OPEN.** `commit_cut` writes the CASE and never touches
   `accounts` — not `closed_at`, not `status`, not `deposit_on_file`.
   *"Close the account or settle the deposit — that is a move-out, not a
   disconnect."* `apps/customers/models.py` already carries the same warning
   from BR-CUS-091: *"nothing in this module may quietly convert one into the
   other."*
2. **BASE CHARGES STOP AT THE CUT — BR-CUS-103, and it is still an omission
   HERE.** The rule was unsigned when this file was written and B18 §5.8.7 said
   so of itself (*"Base accrual after a cut is DRAWN TWICE and signed nowhere"*);
   the PO ruled it on 2026-08-25 (OQ-380, answer **"no"**) and DEF-707 is the
   behaviour it reverses. **`commit_cut` still writes nothing new** — no
   `accounts` column, no behaviour class, no accrual flag — because the fix is
   a READ: `service_off_windows()` publishes the dark days and
   `apps/billing/gather.py` subtracts them from `service_days`, which B4.3
   already prorates by. `CUT_STOPS_BASE` states the rule and names the seam.
   ⚠ The reconnection fee half (BR-CUS-104) is NOT built — see DEF-708 below.
3. **The reconnection fee is QUOTED from the tenant's `CC-RECON` code and is
   NOT posted.** BR-BIL-007 forbids a literal; BR-CUS-037 forbids customers
   writing a financial table; `apps.billing.services` publishes no ad-hoc
   charge service to hand it to. So the amount is recorded on the case and
   `FEE_POSTED` travels with every answer. **A cut REFUSES when no
   reconnection code is configured** — `DSC-02.4` quotes the fee *"so the
   customer is told what it will cost to get service back before it is taken
   away"*, and a cut nobody can price is a cut the customer cannot undo.
4. **The disconnected state lives on the CASE *and* on the ACCOUNT, since
   2026-08-30.** BR-CUS-055 seeded five statuses and none of them was it;
   BR-CUS-107 (PO 2026-08-25, closing DEF-701) added the sixth, `Disconnected`
   / `non_billable`, and for five days nothing assigned it, because assigning
   it drops the account out of `selectors.accounts_for_bill_run` and the days
   before the cut would then be billed by nobody (`OQ-1170`, **$23.23** of a
   **$40.00** base on `A-11488`). **The PO ruled the cut is the WHOLE event**
   — *"when we disconnect - we generate final bill at that time itself"* — so
   `commit_cut` now raises that bill through billing's own door, records what
   is outstanding, and writes the status in the same act; `restore_service`
   puts back the status the account held before the cut. See
   `DISCONNECTED_STATUS_ASSIGNED`, and `CUT_BILL_BLOCKED_SO_STATUS_HELD` for
   the one case where the status is deliberately NOT written.
   `new_service_block_for()` is *"blocks new service elsewhere until it
   is settled"* built as a read; **nothing consumes it** (hard-won law 2) and
   its subject is unstated in the same way BR-CUS-097's is.

⛔ **AND A RESTRICTOR IS REFUSED, NOT APPROXIMATED.** `DSC-02.1` offers three
treatments per service and this schema holds two.
`assert_treatments_expressible` raises on the third and names what building it
would take. B18 draws the restrictor as the DEFAULT for water and calls it *"what
many jurisdictions require"* — which is why it is refused loudly rather than
rounded to a cut.

════════════════════════════════════════════════════════════════════════════
7.9 — THE PATH BACK, AND THE TWO DEPOSITS THAT ARE NOT THE SAME DEPOSIT
════════════════════════════════════════════════════════════════════════════
§5.8.3 draws `CUT → RECONNECTING → restored`; §5.8.4 spells it *"payment
confirmed → visit scheduled → restored → the row leaves the tab."*

  * **`mark_reconnecting` is an EXPLICIT staff act, never a payment side
    effect.** BR-PAY-036: *"a payment is ALWAYS accepted and acceptance NEVER
    auto-changes account status — restoration stays an explicit, audited staff
    action."* The ladder stops itself when money posts; the meter does not turn
    itself back on. §5.8.6's `A-11507` is the drawn proof — $0.00 owed, tier
    `—`, still on the tab.
  * **It refuses while anything is outstanding**, because §5.8.1's caption for
    the state is *"paid, awaiting a visit"* and `DSC-02.4` blocks new service
    *"until it is settled"*. ⛔ **AND THAT REFUSAL IS NOW AGAINST A SIGNED RULE.
    `BR-CUS-1097` (PO 2026-09-25), verbatim: *"Show what's still owed and let the
    clerk proceed"*.** The balance need NOT be clear to reconnect: the screen
    states the arrears plus the fee and what has been paid, and the clerk
    restores service anyway. Worked, as put to the PO: **Brett Calloway owes
    $1,204.50 plus the fee, pays $400.00, agrees a plan for the rest, and the
    clerk restores water the same day.** The product then records what was still
    owed, what had been paid, who restored it and when — because with nothing
    blocking, that record is the only protection there is. **It is the pair of
    `BR-CUS-1096`** (a protection warns and never stops a clerk): one principle,
    two rulings, the same day. **THE CODE BELOW STILL REFUSES** — recorded, not
    wired; the reconnect design is paused at the PO's instruction. ⛔ **AND THE GATE IS $75.00 SHORT — DEF-708.**
    BR-CUS-104 (PO 2026-08-25, closing OQ-381) rules that the fee lands AT THE
    CUT, so `A-11340` must clear **$8,315.00** and this gate clears them at
    **$8,240.00**. ⚠ **THE FIX IS NOT TO FOLD THE RECORDED FEE INTO THIS
    COMPARISON**, and that is worth writing down because it is the obvious
    move: paying reduces AR to zero, the case's `reconnection_fee_amount` never
    clears, and the gate would then refuse forever — **no cut customer could
    ever be reconnected.** The fee has to become REAL RECEIVABLE at the cut, at
    which point this gate needs no change at all. See `FEE_POSTED` for why
    it cannot be posted from here today.
  * **`restore_service` only runs from `RECONNECTING`**, and `STATE_RESTORED`
    is one of the two states `open_case_for` excludes — so *"the row leaves the
    tab"* and *"a fresh case may be opened later"* are one fact, held once.
  * **The two deposit options DIVERGE at exactly this point.** `DSC-02.4`: *"Hold it
    — the deposit is available if they reconnect"* versus *"Apply it — nothing
    is held, so a new deposit is required to reconnect."* The election is
    recorded at the cut and read back here as `new_deposit_required`.
    ⚠ **Nothing collects that new deposit and nothing posted the application**
    (`DEPOSIT_APPLICATION_NOT_POSTED`): a deposit is `accounts.deposit_on_file`
    and applying one against an arrear is a balance-sheet posting, which rule 5
    leaves to the ledger posting service alone.
  * ⚠ **NOTHING BOOKS THE VISIT** (`VISIT_NOT_SCHEDULED`) — reported, not
    invented. ✅ **AND A CREW THAT ATTENDED AND DID NOT CUT IS RECORDABLE SINCE
    2026-09-20** (`BR-CUS-1083`, PO ruling, `OQ-383` closed). This bullet read
    *"nothing can record"* it for 26 days and that is no longer true:
    `apps/customers/disconnect_visits.py` holds the four outcomes the PO named
    — locked gate, access refused, paid at the door, disputed — and each one
    MOVES the case rather than annotating it. `CREW_OUTCOME_UNRECORDABLE` is
    amended in place below rather than deleted, because a screen, a test and a
    support person all read it by name.

════════════════════════════════════════════════════════════════════════════
7.16 — BR-CUS-082's RESTART, AND THE SUBJECT THAT STAYS UNNAMED
════════════════════════════════════════════════════════════════════════════
BR-CUS-082 (PO 2026-08-24, closing OQ-346), verbatim: *"(b) continue, ladder
restarts"* —

    "A DEBT SURVIVING ACCOUNT CLOSURE IS STILL CHASED, AND THE DUNNING LADDER
    RESTARTS FROM TIER 1. … a closed account cannot be escalated to
    disconnection — there is nothing left to disconnect — and the ladder for a
    closed account is a collections sequence, not a service one."

Worked, on the PO's own fixture: `A-11024 · Ridge Coffee Co.` closes owing
**$328.70** against **$153.50** of deposit and interest — **$175.20** survives
and is chased, starting again at TIER 1. **A customer already at TIER 2 at
closure does not stay at TIER 2**: `restart_after_closure()` takes no `tier`
argument and writes `TIER_1` unconditionally, so resuming is unrepresentable
rather than merely discouraged.

**A CLOSED ACCOUNT CANNOT BE CUT.** The case is opened with
`sequence=SEQ_COLLECTIONS`, and `assert_cut_reachable()` refuses on two
independent grounds — the sequence, and the account's own closed status — so
removing either one still leaves the guard standing. `schedule_cut()` is the
only door to a cut date and it calls that guard first.

⚠ **AND WHO IS CHASED IS NOT DECIDED HERE, BY CONSTRUCTION.** BR-CUS-097 (PO
2026-08-24) moves a sub-account's unpayable residue to its MASTER, and its own
text asks: *"If the residue moves to the master, who is chased — the departed
sub-account holder or the master account? The two rulings do not resolve that
between them, and W7 must not build both readings."*
`08-qa/01-e2e/journeys/J08-final-bill-settlement-five-paths.md` step **2b**
asserts the same thing and says a green assertion naming either party is a
FAILURE.

So: `restart_after_closure()` **has no subject parameter and no subject
column.** It is opened against the account the debt was measured on — the
account whose row it is — and the result carries
`move_out_settlement.DUNNING_AFTER_CLOSE`, whose `subject_unresolved` sentence
travels with every one of these cases. The restart FACT and the unresolved
SUBJECT ride together, and nothing in this module can name a party. **An OQ is
OWED** for that question; this lane reports it and does not mint one (prime
directive — all questions route to the PO).

════════════════════════════════════════════════════════════════════════════
NOTHING ADVANCES THIS LADDER ON A DATE — STATED, NOT IMPLIED
════════════════════════════════════════════════════════════════════════════
Measured on this tree, 2026-08-25: **no runner, job, queue or timer in this
product reads a date and acts on it.** `apps/payments/ladder.py` says the same
of itself in its own words — *"BR-PAY-017's ladder is evaluated by a scheduled
job and this repo's job runner (BE-07) registers no collections job"* — and
**DEF-320** is the deployed shape of it: `JOBS_EAGER=False` with no worker, so
what is enqueued never runs.

Therefore `next_step_due` here is a STORED DATE THAT NOTHING WATCHES.
`ladder_state()` returns `advances_on_a_schedule: False` with `DEF-320` beside
it on every call, so a caller cannot mistake a computed due date for a promise
that a tier will arrive. **A tier advances when something calls `advance()`**,
and today the only things that can are a test and a screen. This is the
`held_excess_has_no_release_path` shape (`move_out_settlement.hold_excess`) and
it is honest, not a failure.

════════════════════════════════════════════════════════════════════════════
MONEY SHAPE (CLAUDE.md rule 2, PO re-sign 2026-08-22)
════════════════════════════════════════════════════════════════════════════
*"MOney 4 decimal, percentage 6 decimal, display both 2 decimal"*. The two new
money columns are declared `NUMERIC(18,4)`; `currency` is `CHAR(3)` and is
DERIVED from the tenant, never an input (BR-TEN-021). Every figure is a
`Decimal`; nothing is coerced through a float; nothing here rounds — rounding
happens once, at display, through `core.money.finalize` (B4 ❄️).

════════════════════════════════════════════════════════════════════════════
BR-CUS-100 — THE SEND IS IN-APP, THE PROOF IS A RECORD A PERSON ENTERS
════════════════════════════════════════════════════════════════════════════
`DEF-692` was B18 contradicting itself: `DSC-02.3` draws four delivery channels
and marks certified mail **`Required at tier 3 — proof of service`**, over a
release whose own §5.8.2 says *"there is no email, SMS or print adapter"*. The
PO's ruling (2026-08-25) does not close that by building an adapter. It
SEPARATES TWO THINGS THIS MODULE HAD CONFLATED, verbatim:

    "So the two halves are separated and neither pretends to be the other: the
    SEND is in-app (and later email/SMS/print), and the PROOF is a **record a
    person enters** — the channel used, the reference, and the date it was
    signed for. That is what a regulator asks to see, and recording it is
    honest where claiming to have sent it is not."

**So there are now two column sets on `disconnect_notices` and they must never
be written by the same code path:**

  * `delivery_state` + `delivery_unavailable_reason` — what THIS PRODUCT did.
    Still NULL on every row, still carrying `DELIVERY_UNAVAILABLE`, and nothing
    in this file has changed about that. BR-CUS-100 says so in as many words:
    *"Until those columns exist, `delivery_state` stays NULL with its reason
    (the W7 lane's behaviour)"*.
  * `service_channel` · `proof_reference` · `served_on` · `signed_for_on` ·
    `proof_recorded_by` · `proof_recorded_at` — what a PERSON attests happened
    outside this product. Written only by `record_proof_of_service`, which
    touches no delivery column, and `tests/test_w7_proof_of_service.py` asserts
    that it does not.

⛔ **AND THE GUARD IS THE POINT OF THE WHOLE RULING** — `assert_service_proved`,
called by `schedule_cut`: *"a tier-3 cut must not be schedulable on an
unrecorded service, because that is the one thing on this screen whose absence
is not merely untidy."* Before it existed, a case could climb to TIER 3 on three
in-app notices and be scheduled for a cut with nobody having recorded that
anything was posted — which is exactly what the tests reported when the guard
was first broken (`Failed: DID NOT RAISE DisconnectRuleError`).

⚠ **TWO THINGS BR-CUS-100 DOES NOT SAY, AND NEITHER IS DECIDED HERE.**
**(1)** Whether a tier-3 cut needs the SIGNATURE to have come back, or only that
certified mail was sent — `assert_service_proved` does not read `signed_for_on`,
and the question is REPORTED. **(2)** Whether correcting a proof is a NEW notice
or a dedicated correction row — the second write is refused
(`proof_already_recorded`) and the question is REPORTED. Choosing either would
be this lane inventing law for households facing a cut.

════════════════════════════════════════════════════════════════════════════
AUDIT — RULE 7, WIDENED ON PURPOSE
════════════════════════════════════════════════════════════════════════════
CLAUDE.md rule 7 makes every MONEY action write `audit_log`. **A disconnection
is not a money action.** It is a SERVICE action against a named customer — a
meter turned off at an address where somebody lives — and the record a utility
shows a regulator when a customer says they were never told is the same record
either way. **So every state change in this module writes `audit_log`**: the
case opening, every notice, every protection recorded and lifted, every
scheduled cut, every by-hand stop, and the post-closure restart. Stated here
because it is a deliberate widening of the rule and not an accident of copying
one.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE NEEDS AND DOES NOT OWN — REPORTED, NOT WORKED AROUND
════════════════════════════════════════════════════════════════════════════
1. ⚠ **`apps/customers/models.py` — ONE LINE, AND WITHOUT IT THIS SCHEMA IS IN
   DRIFT.** Measured on this tree 2026-08-25 (found by lane S2 and confirmed
   here): `makemigrations --check --dry-run` proposes **DELETING**
   `DisconnectCase`, `DisconnectNotice` and `AccountProtection` by name. A model
   is registered by IMPORTING the module that defines it; Django imports
   `apps.customers.models` and nothing else, so migration STATE holds three
   models the app registry lacks and the autodetector answers that difference
   with a `DeleteModel`. **The tables would be correct on disk and the project
   permanently proposing to drop them.** The fix is the last line of
   `models.py`:

       from apps.customers import disconnects  # noqa: E402,F401  (registers three models)

   **EXACT PRECEDENT:** `apps/rating/models.py` ends with the same line for
   `apps/rating/discounts.py` and says why in its own words — *"the import
   below is what makes them exist for the app registry and for
   `makemigrations`; deleting it silently un-defines six tables."*
   `tests/test_w7_disconnects.py::test_customers_models_registers_the_three_disconnect_models`
   is the guard, `xfail(strict=False)` until the line lands.

   ⚠ **WHY NOT THE SELF-CONTAINED ALTERNATIVE** (`managed = False` plus raw
   per-vendor DDL in the migration, which lane S2 took for `transfers`): it
   would move SIX load-bearing constraints — the three protection LIFETIMES,
   `ck_collections_sequence_never_cuts`, the state and sequence vocabularies,
   and the one-open-case-per-account partial unique — out of the single
   `CreateModel` declaration and into two hand-maintained SQL dialects that
   nothing compares. `managed = False` also makes the `CheckConstraint`
   declarations on these models DECORATIVE, so
   `test_the_three_lifetimes_are_held_by_the_DATABASE` would be asserting
   hand-written SQL rather than the declaration a reader sees beside it. That
   is hard-won law 5's shape exactly (one thing, two copies, drift within a
   day) — over a constraint that decides whether somebody's power stays on.
   **One line with a documented precedent beats two dialects of DDL**, and the
   drift is loud rather than silent until it lands.

2. **`apps/customers/apps.py` — the alternative home for the same one line.** The three model classes live here
   rather than in `apps/customers/models.py` because another lane held that file
   (the reason `apps/payments/bankrec_models.py` and `collections_models.py`
   both record for themselves: *"two lanes in one models module is how a
   migration graph forks"*). `Meta.app_label` is `customers` and the tables are
   customers' own, but Django imports `apps.customers.models` and nothing else,
   so `ready()` needs

       from apps.customers import disconnects  # noqa: F401

   exactly as `PaymentsConfig.ready()` already does for its two. **Until that
   line lands, `makemigrations` cannot see these models** and would propose
   deleting them. The tests import the module explicitly, so they are unaffected
   — which is precisely why this is reported rather than left to be discovered.
3. **`apps/payments/outstandings.py` and `apps/payments/notices.py`** state the
   absence `medical_hold_not_readable` — *"`apps/customers` publishes no
   medical-hold selector"*. `medical_hold_for()` below IS that selector. Wiring
   it is a resolver call in payments (the `_resolve` idiom they already use) and
   belongs to that lane. **Until then this is built and not wired** (hard-won
   law 2), and no gate will say so because G13 reads the frontend.
4. **`12-governance/09-human-review-ledger.md`** — a row for this file and for
   the migrations (0022 AND 0023). G7 globs
   `06-backend/apps/*/migrations/0*.py`, so **G7 FAILS on both migrations until
   those rows exist.** Reported with the exact paths.
5. ⚠ **BR-CUS-100's GUARD MAKES THREE EXISTING TESTS WRONG, AND THEY ARE IN
   FILES THIS LANE DOES NOT OWN.** `tests/test_w7_disconnects.py::
   test_a_cut_is_scheduled_only_after_TIER_3` and
   `tests/test_w7_worklists.py::test_dsc_cut_date_is_accented_only_within_seven_days`
   / `::test_dsc_the_kpi_tiles_overlap_by_design_and_the_union_hides_nothing`
   each schedule a tier-3 cut with no proof of service recorded. They asserted
   the world BEFORE this ruling and now fail with `cut_on_unrecorded_service`
   — which is the guard working. Each needs a `record_proof_of_service(...)`
   call immediately before its `schedule_cut(...)`; the exact patch is in the
   lane report. **This is not a flaky test and must not be skipped:** it is the
   change process's step 4 — *what is already built and is now wrong* — and the
   answer is to update the assertion to the new rule.
6. **`notices_awaiting_proof()` IS BUILT AND NOT WIRED** (hard-won law 2). It is
   the queue of notices raised and not yet served, the shape
   `work_orders.accepted_by` gives the review queue in BR-MET-110. No screen
   reads it: S90's endpoints are tasks 7.11/7.9 and `apps/customers/api.py` and
   `disconnect_reads.py` are not in this lane's write scope. G13 reads the
   frontend and will not say so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.customers import notifications_seam, seams
from core import audit as core_audit
from core.dbfields import uuid7_pk
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")
HUNDRED = Decimal("100")


# ════════════════════════════════════════════════════════════════════════════
# VOCABULARY
# ════════════════════════════════════════════════════════════════════════════
#: B18 §5.8.2's three chips. ONE spelling, because the list, the case row and
#: the notice row must group on the same string — two vocabularies is how a
#: state machine grows a fourth tier nobody ruled.
TIER_1 = "tier_1_reminder"
TIER_2 = "tier_2_10_day"
TIER_3 = "tier_3_48_hour"
LADDER_TIERS: tuple[str, ...] = (TIER_1, TIER_2, TIER_3)

#: What comes next, and `None` at the top. TIER 3 is the LAST tier: after it the
#: case is SCHEDULED for a cut, which is a different act with a different guard.
NEXT_TIER: dict[str, str | None] = {TIER_1: TIER_2, TIER_2: TIER_3, TIER_3: None}

#: `apps/payments/collections_models.py`'s rung names, mirrored rather than
#: imported so this module states its own half of the contract and a test can
#: assert the two agree. Mirroring is the precedent
#: `apps/tenancy/settings_families.BACK_BILL_SEGMENT_ESTIMATE_SOURCES` sets, and
#: for the same reason: a second spelling is a mapping that silently stops
#: matching.
PAYMENTS_RUNG_FRIENDLY = "friendly"
PAYMENTS_RUNG_10_DAY = "first_10_day"
PAYMENTS_RUNG_5_DAY = "second_5_day"
PAYMENTS_RUNG_48_HOUR = "final_48_hour"

#: The rung → chip map, and the ONE rung that has no chip. See the module
#: docstring: mapping `second_5_day` onto either neighbouring chip misstates to
#: a regulator what a customer was told.
TIER_UNMAPPED = "unmapped_rung"
TIER_FOR_RUNG: dict[str, str] = {
    PAYMENTS_RUNG_FRIENDLY: TIER_1,
    PAYMENTS_RUNG_10_DAY: TIER_2,
    PAYMENTS_RUNG_48_HOUR: TIER_3,
}

#: BR-CUS-082: a closed account's ladder is a COLLECTIONS sequence, not a
#: service one. The distinction is a column because it is the thing that makes
#: a cut unreachable, and a distinction held only in a docstring is not held.
SEQ_SERVICE = "service"
SEQ_COLLECTIONS = "collections"
SEQUENCES: tuple[str, ...] = (SEQ_SERVICE, SEQ_COLLECTIONS)

#: B18 §5.8.2's segments, plus the two terminal states the tab does not draw
#: because a row in either has LEFT the list.
STATE_NOTICE_SENT = "notice_sent"
STATE_SCHEDULED = "scheduled"
STATE_ON_HOLD = "on_hold"
STATE_CUT = "cut"
STATE_RECONNECTING = "reconnecting"
STATE_STOPPED = "stopped"
STATE_RESTORED = "restored"
#: BR-CUS-430 (PO 2026-08-27, closing DEF-724) — the EIGHTH state, and the only
#: one that means *the account this case belongs to is finished*. A case reaches
#: it from `cut` and from nowhere else: `close_out.close_out` is the one writer,
#: and it is a separate act from a move-out because *"to a regulator those are
#: not the same event"*. It joins `stopped` and `restored` as a CLOSED state —
#: see `uq_one_open_disconnect_case_per_account` and `open_case_for`, both of
#: which must exclude it so `restart_after_closure` can open the BR-CUS-082
#: collections case beside a closed-out service case rather than colliding with
#: it on the partial unique index.
STATE_CLOSED_OUT = "closed_out"
CASE_STATES: tuple[str, ...] = (
    STATE_NOTICE_SENT,
    STATE_SCHEDULED,
    STATE_ON_HOLD,
    STATE_CUT,
    STATE_RECONNECTING,
    STATE_STOPPED,
    STATE_RESTORED,
    STATE_CLOSED_OUT,
)

#: The states in which a case is FINISHED and no longer occupies the one-open-
#: case-per-account slot. Named ONCE because it was written twice as a literal
#: tuple — in the partial unique index and in `open_case_for` — and BR-CUS-430
#: had to add a member to both. Two copies of one set is how the index and the
#: reader come to disagree, and the disagreement shows up as an
#: IntegrityError on a customer-facing act rather than as a failing test.
CLOSED_CASE_STATES: tuple[str, ...] = (STATE_STOPPED, STATE_RESTORED, STATE_CLOSED_OUT)

#: The three protections (B18 §5.8.3). NOT four — `dispute` is step 2's fourth
#: CHECK and is not a protection with a lifetime; see the module docstring.
PROTECTION_MEDICAL = "medical_certificate"
PROTECTION_PLAN = "payment_plan"
PROTECTION_MORATORIUM = "weather_moratorium"
PROTECTIONS: tuple[str, ...] = (PROTECTION_MEDICAL, PROTECTION_PLAN, PROTECTION_MORATORIUM)

#: Three lifetimes, three shapes. `LIFETIME_DERIVED` is the one that has NO date
#: of its own — the difference the `ck_protection_lifetime` constraint holds.
LIFETIME_EXPIRES = "expires_on_a_date"
LIFETIME_DERIVED = "derived_from_the_plan"
LIFETIME_WINDOW = "regulator_date_window"
PROTECTION_LIFETIME: dict[str, str] = {
    PROTECTION_MEDICAL: LIFETIME_EXPIRES,
    PROTECTION_PLAN: LIFETIME_DERIVED,
    PROTECTION_MORATORIUM: LIFETIME_WINDOW,
}

#: Why the ladder is not running. Every one is a CODE, because the S90 segment
#: and the KPI strip group on it and prose cannot be grouped.
#:
#: ⚠ **`HALT_PROTECTED` IS ABOUT THE UNATTENDED LADDER AND NOT ABOUT A CLERK.**
#: `BR-CUS-1096` (PO 2026-09-25) rules that a protection WARNS a clerk and never
#: stops them. It leaves this halt exactly as signed under `BR-CUS-039` — a
#: machine declining to send a notice is not a person being refused — but any
#: CLERK-FACING path that reaches this code is now against the rule. The one
#: that does today is `schedule_cut`; see its docstring.
HALT_NOTHING_OWED = "nothing_owed"
HALT_BELOW_FLOOR = "below_ladder_floor"
HALT_PROTECTED = "protected"
HALT_PLAN_PAUSE = "payment_plan_pause"
HALT_PARTIAL_PAYMENT = "partial_payment_pause"
HALT_BALANCE_UNREADABLE = "balance_not_readable"
HALT_FLOOR_UNREADABLE = "ladder_floor_not_readable"
HALT_PAUSE_PERCENT_UNSET = "partial_pause_percent_not_set"
HALT_LADDER_COMPLETE = "ladder_complete"
HALT_STOPPED_BY_HAND = "stopped_by_hand"

#: B18 §5.8.3's three named reasons a human may stop a ladder that would
#: otherwise keep running. The set is CLOSED: a fourth reason is a fourth way to
#: stop chasing a real debt, and it needs a ruling, not a string.
STOP_CLERK_ERROR = "clerk_error"
STOP_DISPUTE = "dispute"
STOP_REGULATOR = "regulator_instruction"
STOP_REASONS: tuple[str, ...] = (STOP_CLERK_ERROR, STOP_DISPUTE, STOP_REGULATOR)
#: `DEF-CUS-10190` — the FOURTH way a ladder stops, and it has its ruling (PO
#: 2026-10-17: *"Marked disconnect ✔ via move-out first (disconnect case closes
#: as customer left; debt stays on old account)"*). It is NOT one of the
#: clerk's three: nobody picks it in the stop modal, and `stop_by_hand` still
#: refuses it by name. Only `stop_for_move_out` writes it, when the account the
#: case chases moves out — the debt stays owed on that account.
STOP_CUSTOMER_LEFT = "customer_left"

#: hard rule 7, widened — see the module docstring. A disconnection is a service
#: action against a customer and is audited like a money one.
AUDIT_CASE_OPENED = "disconnect.case.opened"
AUDIT_NOTICE = "disconnect.notice.recorded"
AUDIT_CUT_SCHEDULED = "disconnect.cut.scheduled"
AUDIT_STOPPED = "disconnect.stopped"
AUDIT_PROTECTION_RECORDED = "disconnect.protection.recorded"
AUDIT_PROTECTION_LIFTED = "disconnect.protection.lifted"
AUDIT_POST_CLOSURE_RESTART = "disconnect.post_closure.restarted"
#: BR-CUS-100's human record. `BR-MET-110` is named in that rule as the same
#: discipline — *"somebody decided, and the record must name them"* — and
#: metering audits `work_order.accepted` for exactly this reason.
AUDIT_PROOF_RECORDED = "disconnect.service_proof.recorded"

#: The tenant setting family and the two keys, named as constants so the
#: contract is greppable from BOTH sides of the boundary — the reason
#: `apps/customers/seams.py` gives for `NSF_PRIVILEGE_KEY`.
COLLECTIONS_FAMILY = "collections"
FLOOR_KEY = "ladder_balance_floor_amount"
PAUSE_PERCENT_KEY = "partial_payment_pause_percent"

#: DEF-320 is the deployed shape of "nothing reads a date on a schedule": jobs
#: are enqueued and no worker runs them. Carried on every ladder answer.
#:
#: ⚠ **AMENDED 2026-09-20 (PO: *"Something has to read cut dates daily and
#: surface what's due"*). HALF OF THIS IS NO LONGER TRUE AND THE OTHER HALF IS
#: UNCHANGED, WHICH IS WHY THE TWO ARE NOW SEPARATE KEYS.** It read, until
#: today: *"no runner, job, queue or timer in this product reads a date and
#: acts on it (measured 2026-08-25)"* — one sentence joining a READ and an ACT,
#: so closing either half would have made the whole sentence a lie. The
#: Accounts blueprint prints the same joined sentence in red on p139.
#:
#:   * **READS a date: YES, since today.** `apps/customers/disconnect_schedule.py`
#:     is a celery-beat entry installed from `CustomersConfig.ready()` that
#:     reads every live utility's `cut_scheduled_for` daily and reports what is
#:     overdue and what is due today.
#:   * **ACTS on it: NO, and deliberately.** Nothing cuts a supply, advances a
#:     tier or writes a notice on a schedule. `advance()` is still called by a
#:     test or a screen, `commit_cut` still has exactly one caller — a person
#:     pressing **Mark as cut** — and whether an unattended job may ever perform
#:     a cut is `OQ-CUS-12525`, OPEN.
#:
#: `next_step_due` is STILL a stored date that nothing watches: the watch reads
#: `cut_scheduled_for` and nothing else. That is stated rather than implied,
#: because a reader who sees *a scheduler exists now* must not conclude that
#: the ladder advances on its own.
NO_SCHEDULER: dict[str, Any] = {
    "advances_on_a_schedule": False,
    "reads_cut_dates_on_a_schedule": True,
    "watches_next_step_due": False,
    "tracks": "DEF-320",
    "detail": "a daily job reads cut dates and surfaces them on the disconnects register, and "
    "NOTHING acts on a date: no runner, job, queue or timer in this product cuts a supply, "
    "advances a tier or writes a notice on its own (amended 2026-09-20; it read 'nothing reads "
    "a date and acts on it' from 2026-08-25). `apps/customers/disconnect_schedule.py` is the "
    "read half — a celery-beat entry, installed from `CustomersConfig.ready()`, that reports "
    "what is overdue and what is due today for every live utility. A tier still advances only "
    "when something calls `advance()`, and a cut still happens only when a person presses Mark "
    "as cut; whether a job may ever perform one is OQ-CUS-12525 and is open. `next_step_due` is "
    "still a STORED DATE THAT NOTHING WATCHES — the watch reads `cut_scheduled_for` alone.",
}

#: B18 §5.8.2's `LAST NOTICE` column claims a DELIVERY, and this product has no
#: email, SMS or print adapter (task 7.10). `delivery_state` is therefore NULL
#: on every row this module writes, and the reason travels with it.
DELIVERY_UNAVAILABLE: dict[str, Any] = {
    "code": "delivery_adapter_absent",
    "br_ref": "BR-NOT-005",
    "detail": "`LAST NOTICE` records HOW a notice was delivered — emailed, posted, certified "
    "sent, certified signed. There is no email, SMS or print adapter in this release; the in-app "
    "bell is the only channel that delivers anything, and `certified signed` asserts a signature "
    "came back. So `delivery_state` is written NULL and never `emailed`: a fabricated delivery "
    "state is what a utility shows a regulator when a customer says they were never told.",
}


# ════════════════════════════════════════════════════════════════════════════
# BR-CUS-100 — THE SEND AND THE PROOF ARE TWO DIFFERENT RECORDS
# ════════════════════════════════════════════════════════════════════════════
#: BR-CUS-100 (PO 2026-08-25, closing DEF-692), verbatim: *"So the two halves
#: are separated and neither pretends to be the other: the SEND is in-app (and
#: later email/SMS/print), and the PROOF is a **record a person enters** — the
#: channel used, the reference, and the date it was signed for."*
#:
#: These five are the channels a notice can be SERVED by, and they are
#: `DSC-02.3`'s own words rather than a vocabulary this lane invented. The
#: ladder draws *"Served Aug 04 · email"*, *"Served Aug 18 · posted"* and
#: *"Served Aug 22 · certified mail"*; `HOW IT GOES OUT` adds ☑ `Text message`
#: and ☑ `Door hanger`. A sixth channel is a claim about how a household was
#: told, and it needs a ruling rather than a string.
SERVE_CERTIFIED_MAIL = "certified_mail"
SERVE_POSTED = "posted"
SERVE_EMAIL = "email"
SERVE_TEXT_MESSAGE = "text_message"
SERVE_DOOR_HANGER = "door_hanger"
SERVICE_CHANNELS: tuple[str, ...] = (
    SERVE_CERTIFIED_MAIL,
    SERVE_POSTED,
    SERVE_EMAIL,
    SERVE_TEXT_MESSAGE,
    SERVE_DOOR_HANGER,
)

#: ⛔ **NOT A SERVING CHANNEL, AND NAMING IT IS THE POINT.** BR-CUS-100:
#: *"BUT IN-APP DOES NOT SATISFY CERTIFIED MAIL, AND THE RULE MUST NOT BE READ
#: AS IF IT DID. `DSC-02.3` marks certified mail **`Required at tier 3 — proof
#: of service`**, and proof of service is a **legal artefact produced outside
#: this product**: a posted item, a tracking number, a signature that came
#: back. No adapter can manufacture one."*
#:
#: In-app is how the notice is SENT (BR-CUS-100's confirmed half, through the
#: one notification seam `EP-NOT-05` describes). It is refused HERE by name so
#: that the day somebody records the bell as a service, the product says why
#: rather than accepting it.
SERVE_IN_APP_IS_A_SEND = "in_app"

#: `DSC-02.3` again, verbatim: certified mail is **`Required`** and LOCKED at
#: tier 3 — *"Required at tier 3 — proof of service"* — and BR-CUS-039 says the
#: same of the final tier in its own words (*certified mail REQUIRED on the
#: final*). Two signed documents, one channel. `assert_service_proved` reads
#: this constant rather than the literal so that a ruling admitting a second
#: lawful tier-3 service (personal delivery, a sheriff) is a one-line amendment
#: in a named place. **This lane did not take that ruling and must not.**
TIER_3_REQUIRED_CHANNEL = SERVE_CERTIFIED_MAIL


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.8 — THE CUT: ITS VOCABULARY, AND THE FOUR THINGS IT MUST NOT DO
# ════════════════════════════════════════════════════════════════════════════
#: `DSC-02.1`'s five reason cards, in the drawn order and with the drawn
#: sentence beside each: **Non-payment** (*the ladder has run and they have not
#: paid*) · **Unsafe installation** (*a hazard found on site*) · **Tampering or
#: theft** (*the meter has been interfered with*) · **Premises abandoned**
#: (*nobody is there and nobody is paying*) · **The customer asked** (*they want
#: service ended*).
CUT_REASON_NON_PAYMENT = "non_payment"
CUT_REASON_UNSAFE = "unsafe_installation"
CUT_REASON_TAMPERING = "tampering_or_theft"
CUT_REASON_ABANDONED = "premises_abandoned"
CUT_REASON_CUSTOMER_ASKED = "customer_asked"
CUT_REASONS: tuple[str, ...] = (
    CUT_REASON_NON_PAYMENT,
    CUT_REASON_UNSAFE,
    CUT_REASON_TAMPERING,
    CUT_REASON_ABANDONED,
    CUT_REASON_CUSTOMER_ASKED,
)

#: ⚠ **THE REASON IS RECORDED AND READ BY NOTHING — STATED, NOT IMPLIED.**
#: B18 §5.8.7 says it of this repo in its own words: *"THE REASON IS NOT
#: DECORATION. Only the first is a collections outcome; the other four are
#: operational and **must not require a dunning ladder at all**. A tampering cut
#: has no tier 3 notice to serve, and 'the customer asked' is closer to a
#: move-out. Nothing in `disconnects.py` keys off a reason."* That last sentence
#: is still true after this lane and is true ON PURPOSE: making a cut behave
#: differently by reason is a ruling about when a household may be cut without a
#: ladder, and it is not one this lane may take.
#:
#: ⛔ **AND THE CONSEQUENCE IS BIGGER THAN "UNUSED": FOUR OF THE FIVE REASONS
#: HAVE NO PATH TO A CUT AT ALL.** `schedule_cut` is the only door to a cut date
#: and it requires TIER 3 plus a certified proof of service (BR-CUS-039 /
#: BR-CUS-100). A tampering cut, an unsafe-installation cut and an abandoned
#: premises have no ladder to climb, so today they cannot be scheduled and
#: therefore cannot be cut. The reason vocabulary exists so the record can NAME
#: the four that are unreachable rather than leaving them unnamed and
#: unnoticed. **A ruling is OWED** and is REPORTED, not chosen.
REASON_DRIVES_NOTHING: dict[str, Any] = {
    "code": "cut_reason_drives_nothing",
    "br_ref": "B18 §5.8.7 · `DSC-02.1`",
    "detail": "the cut reason is recorded and nothing branches on it. Four of the five drawn "
    "reasons — unsafe installation, tampering or theft, premises abandoned, the customer asked "
    "— are OPERATIONAL and B18 says they *'must not require a dunning ladder at all'*. "
    "`schedule_cut` requires TIER 3 and a certified proof of service, so those four have no "
    "lawful path to a cut in this build. Which of them may be cut without a ladder, and on whose "
    "authority, is stated by no signed document. A RULING IS OWED.",
}

#: `DSC-02.1`'s `Which services` table — *"One decision per service, not all or
#: nothing"* — and its three columns: `FULL DISCONNECTION · RESTRICTOR /
#: LIMITER · LEAVE CONNECTED`.
TREATMENT_FULL = "full_disconnection"
TREATMENT_RESTRICTOR = "restrictor"
TREATMENT_LEAVE = "leave_connected"
SERVICE_TREATMENTS: tuple[str, ...] = (TREATMENT_FULL, TREATMENT_RESTRICTOR, TREATMENT_LEAVE)

#: ⛔ **A RESTRICTOR IS A THIRD STATE AND THIS SCHEMA HOLDS TWO.** B18 §5.8.7,
#: verbatim: *"A RESTRICTOR IS A THIRD STATE AND THE SCHEMA HAS TWO.
#: `disconnect_cases` knows cut and not-cut. *Restricted* is neither: service
#: continues, billing continues, and the account is under enforcement. **Not
#: built, and it is drawn as the DEFAULT treatment for water.**"* The drawn
#: caption is stronger still — a restrictor *"is what many jurisdictions require
#: for water"*.
#:
#: It is REFUSED BY NAME rather than quietly folded into either neighbour.
#: Recording a restrictor as a CUT tells a regulator a household's water was
#: stopped when it was throttled; recording it as LEAVE CONNECTED loses the
#: enforcement entirely and the account looks untouched. Both are false
#: statements about a household's water supply.
RESTRICTOR_UNBUILDABLE: dict[str, Any] = {
    "code": "restrictor_is_a_third_state",
    "br_ref": "B18 §5.8.7 · `DSC-02.1`",
    "detail": "a restrictor or load limiter is a THIRD state and `disconnect_cases` holds two: "
    "cut and not-cut. Under a restrictor service continues, billing continues and the account is "
    "under enforcement, so it is neither. It is refused rather than recorded as one of its "
    "neighbours: calling it a cut says a household's water was stopped when it was throttled, "
    "and calling it `leave_connected` loses the enforcement altogether.",
    "what_it_would_take": (
        "a per-service treatment ROW rather than a list of cut service codes — "
        "`disconnect_case_services(case_id, service_code, treatment, effective_from, "
        "restored_on)` with the three drawn treatments in a CHECK; a billing rule saying what a "
        "restricted service is charged (base only? full? a limiter tariff?), which no signed "
        "document states; and a field-work vocabulary for fitting and removing the device. "
        "None of the three exists, and the middle one is a money rule this lane may not invent."
    ),
}

#: `DSC-02.4`'s fee table — *"From your charge codes, never typed"* — and
#: BR-BIL-007 in its own words: *"NSF/reconnect fees are tenant-configured
#: charge codes, never hardcoded"*. The drawn figures are `CC-DISC` **$45.00**
#: on the cut, `CC-RECON` **$75.00** when service is restored and `CC-FIELD`
#: **$35.00** only if a crew attends. **No figure is written here** — the code
#: is the contract and the amount is the tenant's row.
#: ✅ **`RECON`, AND THE `CC-` PREFIX IS GONE — PO ruling 2026-09-21, verbatim:
#: *"reconnection fee is $75 - fix the code and seed"* (`OQ-CUS-12518`, CLOSED).**
#:
#: ⚠ **THIS CONSTANT READ `"CC-RECON"` AND RESOLVED ON NO TENANT IN THE PRODUCT,
#: SO NO DISCONNECTION COULD BE COMPLETED ANYWHERE.** The seed, `ledger/chart.py`
#: and every tenant's own `charges` row all spell it `RECON`; only this module
#: prefixed. **Three surfaces against one is why the code moved rather than the
#: data** — respelling the seed to `CC-RECON` would have meant changing the
#: ledger's chart of accounts too and orphaning the live row in every tenant's
#: catalogue, a data migration bought for nothing.
#:
#: ⚠ **AND THE SPELLING ALONE WOULD HAVE BEEN THE WORSE HALF-FIX:** the seed
#: shipped `$45.00` against a figure the PO signed at `$75.00` on 2026-08-25,
#: so aligning the lookup without the amount would have started charging
#: **$45.00, silently, on a real customer's bill.** The amount moves with it —
#: `migrations/0062` for rows already written, `lookup_defaults.json` for new
#: tenants, and `seed_demo.py`, which created no reconnection code at all.
RECONNECT_CHARGE_CODE = "RECON"
#: What the customer READS on the fee bill DEF-708 raises. The charge code's own
#: `name` is the fallback billing uses when this is None; it is stated here
#: because a bill line saying only *"CC-RECON"* is a code, not a sentence, and
#: this line is the whole content of a document the customer receives.
RECONNECTION_FEE_DESCRIPTION = "Reconnection fee"
#: ⊕ **THE SAME PREFIX FAULT, FIXED WITH IT, AND NO PRICE OF EITHER IS TOUCHED.**
#: `DISC` is seeded at `$45.00`, which already agrees with what p139 draws, so
#: this is a spelling repair and not a money change.
DISCONNECT_CHARGE_CODE = "DISC"
#: ⚠ **`FIELD` IS RESPELLED AND STILL RESOLVES TO NOTHING — STATED, NOT HIDDEN.**
#: **No seed creates a field-visit charge code at all**, in `lookup_defaults.json`
#: or in `seed_demo.py`, so this row keeps carrying its absence. p139 draws
#: `$35.00` and **the PO has not ruled it** — their 2026-09-21 ruling names the
#: RECONNECTION fee alone. A lane may not mint a money row the PO has not priced,
#: so nothing here invents one.
FIELD_VISIT_CHARGE_CODE = "FIELD"

#: ⚠ **THESE THREE CODES ARE NOT IN ANY SEED, AND ONE OF THEM IS SPELLED
#: DIFFERENTLY WHERE IT DOES EXIST.** Measured on this tree, 2026-08-25:
#: `apps/tenancy/management/commands/seed_demo.py` seeds `CONN`, **`DISC`**,
#: `NSF` and `TAMPER` — so B18's `CC-DISC` is the seed's `DISC` under another
#: name, and **there is no reconnection charge code at all**. `commit_cut`
#: therefore refuses on a tenant that has not configured one, which is the
#: `apps/notifications/notices.py` posture for the same figure in the same
#: letter: *"Configure the reconnect charge code, then generate."*
CHARGE_CODE_SPELLING_UNRULED: dict[str, Any] = {
    "code": "reconnect_charge_code_not_seeded",
    "br_ref": "BR-BIL-007 · `DSC-02.4`",
    "detail": "`DSC-02.4` names the codes `CC-DISC`, `CC-RECON` and `CC-FIELD`; the demo seed "
    "spells its disconnect fee `DISC` and seeds no reconnection fee at all. So the code this "
    "module looks up resolves on no tenant in this tree today and every cut refuses until one is "
    "configured. Whether the catalogue should carry B18's spelling, or the code should itself be "
    "a tenant setting, is stated nowhere. A RULING IS OWED.",
}

#: ⛔ **THE RULING IS NOW A FILED QUESTION WITH ITS FIGURES — `OQ-CUS-12518`,
#: RAISED 2026-09-20 BY `CR-125-BRC07`. THREE SOURCES, TWO DISAGREEMENTS, AND
#: EVERY CUT REFUSES ON EVERY TENANT IN THIS TREE.**
#:
#: Measured on this branch 2026-09-20, by reading all three:
#:
#:   1. **THE CODE looks up `CC-RECON`** — `RECONNECT_CHARGE_CODE` above, read
#:      by `reconnection_terms` and by `commit_cut`, and named the same way in
#:      `apps/notifications/notices.py`'s `{reconnect_fee}` token.
#:   2. **THE SEEDED CATALOGUE spells it `RECON` and prices it `$45.00`** —
#:      `apps/tenancy/fixtures/lookup_defaults.json`, `charge_codes[6]`:
#:      `{"code": "RECON", "name": "Reconnection fee", "charge_type":
#:      "one_time", "amount": "45"}`. `apps/ledger/chart.py` maps `RECON` to GL
#:      `4610`, so the ledger half agrees with the catalogue and not with the
#:      code. (The demo seed is a third spelling again: it seeds `CONN`, `DISC`,
#:      `NSF` and `TAMPER` and **no reconnection code at all.**)
#:   3. **THE BLUEPRINT AND THE SIGNED WORKED FIGURE BOTH SAY `$75.00`** —
#:      blueprint p139 draws `Reconnection fee · CC-RECON · $75.00`, and
#:      `BR-CUS-104` is signed on that number: PO 2026-08-25, verbatim, *"does
#:      reconnection need $8,315.00 - this is correct"*, over `A-11340`'s
#:      **$8,240.00** arrears **plus $75.00**. `FEE_TIMING_RULED` carries it.
#:
#: **SO THE DISAGREEMENTS ARE TWO AND THEY ARE INDEPENDENT:** a SPELLING
#: (`CC-RECON` against `RECON`) and a PRICE (`$75.00` against `$45.00`).
#: Resolving the spelling alone would make every cut start charging **$45.00**
#: — thirty dollars under the signed figure, silently, on a real customer's
#: bill. Resolving the price alone changes nothing, because the lookup still
#: finds no row.
#:
#: ⚠ **NOTHING HERE PICKS EITHER, AND THAT IS THE RULE AND NOT CAUTION.** This
#: is a money figure and it is `B14` rule 37's exception in the one direction
#: that matters: the `$75.00` on p139 is a drawn illustration, but the
#: `$8,315.00` in `BR-CUS-104` is a SIGNED worked figure, and a lane may not
#: move a signed figure or reconcile it with a fixture (CLAUDE.md law 13 — a
#: fact only the PO holds, and a collision with a signed rule). `$75.00`
#: therefore appears nowhere in this module as a value; it appears only as the
#: figure that was signed, quoted.
#:
#: **WHAT A CLERK SEES UNTIL IT IS ANSWERED:** `reconnection_terms` answers
#: `fee: None` with `fee_absence` beside it, `commit_cut` refuses, and the
#: refusal names the question. That is the prime directive's boundary: the code
#: runs up to the decision and stops there.
#: ✅ **THE RULING THAT REPLACED THE DISAGREEMENT (`OQ-CUS-12518`, CLOSED
#: 2026-09-21).** This block was `RECONNECT_FEE_DISAGREEMENT` and recorded that
#: THREE SOURCES DISAGREED and that no lane might choose between them. The PO
#: chose: *"reconnection fee is $75 - fix the code and seed"*.
#:
#: ⚠ **IT IS RENAMED RATHER THAN DELETED, AND RENAMED RATHER THAN LEFT.** Kept,
#: because the next reader of a `$75.00` in this module should find where the
#: number comes from without a git archaeology trip. **Renamed, because a
#: constant called DISAGREEMENT that records a settled answer is exactly the
#: fault this file warns about three screens down** — a comment claiming an
#: absence that has been closed is hard-won law 1 pointing the other way.
#:
#: ⚠ **`amount` IS NOT READ BY ANY PRICING PATH AND MUST NOT BECOME ONE.**
#: `BR-BIL-007` — *"NSF/reconnect fees are tenant-configured charge codes, never
#: hardcoded"* — so the figure a cut charges is still the TENANT's row, read
#: through `charge_by_code`. This records what the PO signed, so that a tenant
#: row disagreeing with it can be NOTICED; it is evidence, never a price.
RECONNECT_FEE_RULING: dict[str, Any] = {
    "code": "reconnect_charge_code_and_amount_ruled",
    "oq": "OQ-CUS-12518",
    "ruled_on": "2026-09-21",
    "br_ref": "BR-BIL-007 · BR-CUS-104 (PO 2026-08-25) · `DSC-02.4` (blueprint p139)",
    "looked_up": RECONNECT_CHARGE_CODE,
    "seeded_as": RECONNECT_CHARGE_CODE,
    "signed_amount": "75.0000",
    "detail": "PO 2026-09-21: 'reconnection fee is $75 - fix the code and seed'. The cut, the "
    "seeded catalogue, the ledger's chart of accounts and every tenant's own row now spell the "
    "code the same way, and the seeded amount is the $75.00 BR-CUS-104 signed on 2026-08-25 "
    "($8,240.00 arrears + $75.00 = $8,315.00). A tenant may still edit their own amount — this "
    "figure is what WE seed, never what we charge.",
}
#: Kept as an alias for one release so a sibling lane mid-edit does not break on
#: the rename; it is the SAME object, not a copy that can drift.
RECONNECT_FEE_DISAGREEMENT = RECONNECT_FEE_RULING

#: ✅ **DEF-708 IS FIXED — THE FEE IS A REAL RECEIVABLE (PO ruling 2026-08-27).**
#: PO verbatim: *"A customer can be reconnected $75 short - Make the fee a real
#: charge — It becomes a line that can be billed and paid, so the gate has
#: something to check."*
#:
#: ⚠ **THIS CONSTANT USED TO SAY THE OPPOSITE AND IS KEPT, RENAMED IN MEANING,
#: SO THE HISTORY SURVIVES (hard-won law 1: a comment claiming a guarantee is
#: not the guarantee — and a comment claiming an ABSENCE that has been closed is
#: the same fault pointing the other way).** It read: *"NOTHING POSTS THE FEE TO
#: THE BALANCE… `apps.billing.services.__all__` publishes `assess_late_fee` and
#: no ad-hoc charge service, so there is no owning-module service to hand this
#: to."* That was measured and true on 2026-08-25. It stopped being true when
#: billing published one.
#:
#: **WHAT HAPPENS NOW.** `commit_cut` calls
#: `apps.billing.services.raise_and_issue_charge_fee` through this module's
#: seam: billing drafts a `fee` bill carrying one `CC-RECON` line at the
#: tenant's own amount, issues it, stamps the charge code's GL account
#: (BR-BIL-010) and posts it (rule 5). The **$75.00** is then IN AR, so
#: `mark_reconnecting` — which has always read AR — refuses `A-11340` at
#: **$8,240.00** and admits them at **$8,315.00**, which is BR-CUS-104's own
#: worked figure.
#:
#: ⚠ **BR-CUS-037 IS NOT BENT BY THIS.** Customers still writes no financial
#: table and still posts no journal line; it calls the owning module's service,
#: which is exactly what BR-CUS-037 prescribes — *"S22 money modals are ENTRY
#: POINTS: validate → confirm → owning-module service"*.
FEE_POSTED: dict[str, Any] = {
    "code": "reconnection_fee_posted_to_ar",
    "closes": "DEF-708",
    "br_ref": "BR-CUS-104 (PO 2026-08-25, OQ-381) · PO ruling 2026-08-27 · BR-BIL-007 · "
    "BR-BIL-010 · BR-CUS-037",
    "detail": "the reconnection fee is charged at the cut as a real receivable: billing raises "
    "a `fee` bill for the tenant's own reconnection charge code and issues it, so the amount is "
    "in AR from the moment the service is cut. `A-11340` owes $8,240.00 in arrears, the fee is "
    "$75.00, and $8,315.00 is what `mark_reconnecting` now requires — which is BR-CUS-104's "
    "figure. The amount recorded on the case is the SAME figure and is the RECORD of what was "
    "quoted; the balance is the money. A caller states both and never adds them together.",
}

#: ✅ **RULED — BR-CUS-104, PO 2026-08-25, closing OQ-381. THE FEE LANDS AT THE
#: CUT.** `DSC-02.4` dated it two ways in one screen — the fee table said
#: `CC-RECON` applies *"When service is restored"* and the `What this will do`
#: panel beside it said the cut *"Add[s] **$75.00** to the balance"*. The
#: question was put with BOTH amounts, because the whole difference is which one
#: a customer must pay, and the PO confirmed the larger, verbatim:
#: *"does reconnection need $8,315.00 - this is correct"* — `A-11340` owes
#: **$8,240.00**, the fee is **$75.00**, so **$8,315.00** is the amount to clear.
#: The consequences panel is right and the fee table's *"When service is
#: restored"* is SUPERSEDED.
#:
#: ✅ **AND THE CODE NOW DOES IT — DEF-708 CLOSED 2026-08-27.** This clause read
#: *"AND THE CODE STILL DOES NOT DO IT"* until the PO ruled the fee a real
#: charge. `commit_cut` raises and issues it; `mark_reconnecting` reads AR and
#: the fee is in AR. See `FEE_POSTED` above.
FEE_TIMING_RULED: dict[str, Any] = {
    "code": "reconnection_fee_lands_at_the_cut",
    "tracks": "DEF-708",
    "br_ref": "BR-CUS-104 (PO 2026-08-25, OQ-381) · `DSC-02.4`",
    "detail": "the reconnection fee becomes owed the MOMENT the service is cut, not when it is "
    "restored (BR-CUS-104, PO 2026-08-25: *'does reconnection need $8,315.00 - this is "
    "correct'*). ⛔ The clause that followed here — *a customer must clear the arrears PLUS "
    "the fee before `mark_reconnecting` accepts them* — is SUPERSEDED by BR-CUS-1097 (PO "
    "2026-09-25, *'Show what\'s still owed and let the clerk proceed'*): $8,315.00 is what "
    "the clerk is SHOWN, never what they must collect first. The fee\'s TIMING is untouched. ✅ IMPLEMENTED 2026-08-27 (DEF-708): the cut raises and issues a `fee` bill "
    "for the tenant's reconnection charge code, so the fee is IN AR and the gate that reads AR "
    "requires it. Worked: $8,240.00 no longer clears; $8,315.00 does.",
}

# ────────────────────────────────────────────────────────────────────────────
# DEF-CUS-6050 — THE RECONNECTION FIGURE MEANS TWO DIFFERENT THINGS, AND WHICH
# ONE IT MEANS IS DECIDED BY THE VERY ACT IT DESCRIBES
# ────────────────────────────────────────────────────────────────────────────
#: ⛔ **BEFORE THE CUT THE FEE IS A QUOTE; THE INSTANT THE CUT COMMITS IT IS A
#: RECEIVABLE.** `commit_cut` raises and ISSUES the fee bill inside the cut's own
#: transaction (DEF-708, PO ruling 2026-08-27), so from that moment the AR
#: position ALREADY CONTAINS the $75.00 — and a figure built as *position + fee*
#: counts it twice. Measured on `A-11340` / `DSC-26-0001` on 2026-09-21, after
#: the first cut this product ever completed: the record read **`Owed
#: $8,315.00`** and **`To clear first $8,390.00`** on the same screen, with
#: nothing paid in between. BR-CUS-104's signed figure is **`$8,315.00`** (PO
#: 2026-08-25, *"does reconnection need $8,315.00 - this is correct"*).
#:
#: ⚠ **THE BASIS IS KEYED ON `cut_on`, WHICH IS THE FACT, AND NOT ON A LIST OF
#: STATES.** `service_off_windows` already reasons this way further down this
#: file and says why: `restored` and `stopped` cases also hold a `cut_on`, so a
#: state list drops them silently. `cut_on` is written in the same transaction
#: that issues the fee bill, and nothing else writes it — so it is exactly the
#: fact *"has this fee reached AR"*.
TO_CLEAR_BEFORE_THE_CUT: dict[str, Any] = {
    "code": "arrears_plus_the_quoted_fee",
    "fee_in_arrears": False,
    "br_ref": "BR-CUS-104 (PO 2026-08-25, OQ-381) · `DSC-02.4` · `DEF-CUS-6050`",
    "detail": "this case has not been cut, so the reconnection fee is a QUOTE and the ledger "
    "position does not contain it. The amount to clear is the arrears PLUS the fee — "
    "BR-CUS-104's $8,240.00 + $75.00 = $8,315.00 — and the sum is stated only when both halves "
    "are readable, because a total over one known half quotes a price short by the whole fee.",
}
TO_CLEAR_AFTER_THE_CUT: dict[str, Any] = {
    "code": "the_position_the_cut_left_behind",
    "fee_in_arrears": True,
    "closes": "DEF-CUS-6050",
    "br_ref": "BR-CUS-104 (PO 2026-08-25, OQ-381) · PO ruling 2026-08-27 (DEF-708) · "
    "`DEF-CUS-6050`",
    "detail": "this case has been cut, so the reconnection fee is an ISSUED bill and the ledger "
    "position already contains it. The amount to clear is that position, read once, and NOTHING "
    "is added to it: adding the fee again quotes one fee too much. Worked on `A-11340`: the "
    "arrears were $8,240.00, the cut issued $75.00, the position is $8,315.00 and that is what "
    "must be cleared — the same figure `mark_reconnecting` requires to reach zero.",
}

#: `DSC-02.4`'s deposit radio — *"A deposit is money you hold **on the
#: customer's behalf**. Applying it against the arrear reduces what they owe but
#: **does not make it income**, and it leaves nothing held if they later restore
#: service."* Two options, and the drawn default is ● **Hold it**.
DEPOSIT_HELD = "held"
DEPOSIT_APPLIED = "applied_against_arrear"
DEPOSIT_DISPOSITIONS: tuple[str, ...] = (DEPOSIT_HELD, DEPOSIT_APPLIED)

#: ⚠ **THE ELECTION IS RECORDED; THE MONEY DOES NOT MOVE HERE.** Applying a
#: deposit against an arrear is a BALANCE-SHEET posting — `DSC-02.4`'s own chip
#: says so: *"A liability, not revenue"* — and rule 5 leaves journal lines to
#: the ledger posting service alone. This is `move_out_settlement`'s
#: `DISPOSITION_APPLIED` / `DISPOSITION_SHOWN_NOT_APPLIED` distinction in a
#: second place and for the same reason: the election is a fact about what was
#: decided, never a claim that $500.00 moved.
DEPOSIT_APPLICATION_NOT_POSTED: dict[str, Any] = {
    "code": "deposit_application_not_posted",
    "br_ref": "CLAUDE.md rule 5 · BR-CUS-037 · `DSC-02.4`",
    "detail": "the deposit election is recorded and no journal line is written. `DSC-02.4` calls "
    "a deposit *'a liability, not revenue'*, so applying it against the arrear is a "
    "balance-sheet posting and only the ledger posting service writes those. The arrear shown in "
    "AR is therefore unchanged by this election; what the election decides today is whether a "
    "NEW deposit is required to restore service.",
}

#: ✅ **WHAT THE CUT DOES — `DSC-02.4`'s `Will` column, verbatim and in order.**
#:
#: ⚠ **ITEM 2 IS SUPERSEDED AND IS KEPT VERBATIM WITH ITS SUPERSESSION STAMPED
#: BESIDE IT, NEVER SILENTLY REWORDED.** `DSC-02.4` drew *"Keep charging base
#: and standing charges — a disconnected account still accrues"*; the PO
#: REVERSED it on 2026-08-25 (**BR-CUS-103**, closing OQ-380, answer **"no"**).
#: The screen's sentence stays here because a reader holding r10 beside this
#: file has to be able to find it and be told it no longer binds — deleting it
#: would leave the prototype saying one thing and the code doing another with
#: nothing to connect them.
CUT_WILL: tuple[str, ...] = (
    "Cut the services chosen at step 1 on the scheduled date, leaving the account open",
    "SUPERSEDED (BR-CUS-103, PO 2026-08-25 → base charges STOP at the cut) — `DSC-02.4` "
    "drew: 'Keep charging base and standing charges — a disconnected account still accrues'",
    "Add $75.00 to the balance as the price of getting service back",
    "Move the account into the disconnected state, which blocks new service elsewhere "
    "until it is settled",
)

#: ⛔ **WHAT THE CUT WILL NOT DO — `DSC-02.4`'s `Will NOT` column, verbatim.**
#: Chipped on the screen *"Worth being clear about"*, and every one of the three
#: is a thing this module could trivially do and must not.
CUT_WILL_NOT: tuple[str, ...] = (
    "Close the account or settle the deposit — that is a move-out, not a disconnect",
    "Stop the balance growing, or write any of it off",
    "Remove the meter, unless you chose meter removal as the field work",
)

#: **BASE CHARGES STOP AT THE CUT — BR-CUS-103, PO 2026-08-25, closing OQ-380.**
#: Asked in plain English with a figure — *"when a service is cut, does the base
#: charge keep running?"*, with `A-11488`, cut 2026-08-18 owing **$612.75** —
#: the PO answered **"no"**. A customer with no service pays nothing for it, and
#: the cost of coming back is recovered by the reconnection fee (BR-CUS-104)
#: rather than by billing a standing charge against a dead connection. Worked:
#: `A-11488` still owes **$612.75** on 2026-09-18.
#:
#: ⚠ **THIS CONSTANT USED TO SAY THE OPPOSITE, AND IT WAS TRUE WHEN IT WAS
#: WRITTEN.** It read *"Keep charging base and standing charges"* and held it
#: BY OMISSION — nothing wrote the account row, so the bill run went on billing.
#: **DEF-707** is that behaviour: there was no wrong line of code, which is why
#: it could not be read off the code and had to be put to the PO.
#:
#: ⚠ **AND THE FIX IS STILL AN OMISSION HERE — `commit_cut` WRITES NOTHING NEW.**
#: `DSC-02.4`'s first prohibition (*"Close the account or settle the deposit —
#: that is a move-out"*) is untouched: no `accounts` column, no behaviour class,
#: no accrual flag. Billing ASKS instead, through
#: `apps.customers.selectors.service_off_windows`, and subtracts the dark days
#: from `service_days` so B4.3's frozen `service_days / cycle_days` factor
#: prices it. **No new money math exists for this rule anywhere.**
CUT_STOPS_BASE: dict[str, Any] = {
    "code": "cut_stops_base_at_the_cut",
    "br_ref": "BR-CUS-103 (PO 2026-08-25, OQ-380) · B4.3 ❄️ · DEF-707",
    "detail": "base charges STOP at the cut (BR-CUS-103, PO 2026-08-25: *'no'*). The boundary "
    "is the CUT date and not the notice date — a service is billed base right up to the moment "
    "it is cut, because until then it was available — so the first day with no service is the "
    "day after `cut_on`. Nothing is written to `accounts` to achieve this: the bill run reads "
    "`apps.customers.selectors.service_off_windows` and subtracts those days from "
    "`service_days`, which B4.3 already prorates by. ⚠ A bill run that emits a base line for "
    "a period a service was cut is a DEFECT, not a rounding question.",
}

#: ✅ **CLOSED 2026-08-30 — THE STATUS IS ASSIGNED, AND THIS CONSTANT NOW SAYS
#: SO.** It was `DISCONNECTED_STATUS_ABSENT`, then
#: `DISCONNECTED_STATUS_NOT_ASSIGNED`, and both names described a gap that no
#: longer exists. The sentences they carried are deleted rather than reworded
#: (hard-won law 1: a stated absence outlives its subject faster than anything
#: else in this repo), and what replaced them is here.
#:
#: **PO ruling 2026-08-30 — THE DISCONNECT IS THE WHOLE EVENT**, verbatim:
#: *"when we disconnect - we generate final bill at that time itself - so later
#: bill is not required ... entire workflow including all settlement and status
#: update is taken care at time of disconnect or move out - so account status
#: changes and outstanding is pending on account if any"*. It closes `OQ-1170`.
#:
#: **WHY IT COULD NOT BE WRITTEN BEFORE, IN ONE SENTENCE.** Writing
#: `Disconnected` drops the account out of `selectors.accounts_for_bill_run`
#: (THIS module's scope seam, filtering on `services.OCCUPYING_BEHAVIOR_CLASSES`
#: — not billing's stage 1, which the note here named wrongly for three days,
#: `DEF-2640`), so the days it used BEFORE the cut would have been billed to
#: nobody: **$23.23** of a **$40.00** monthly base on `A-11488`, cut 18 August
#: (18 days of 31), plus every gallon and every kWh. BR-CUS-103 says base is
#: billed *"right up to the moment it is cut"* and BR-CUS-107 says a cut account
#: is `Disconnected`; both are signed, and they only ever coexisted because a cut
#: account was still in the run.
#:
#: **THE RULING REMOVES THE LATENESS INSTEAD OF PICKING A CASUALTY.** The final
#: metered bill is raised AT the cut, for the first unbilled day through the cut
#: day inclusive, so BR-CUS-103 keeps its words exactly — those days are billed,
#: just a month earlier — and BR-CUS-107 writes its status immediately, because
#: nothing is left for the next run to do.
#:
#: ⚠ **AND `DSC-02.4` STILL STANDS.** The act at the cut is a BILL and a
#: SETTLEMENT, never a close-out: the cut *"leaves the account open"* and is
#: *"not a move-out"*. `commit_cut` writes `accounts.status` and NOTHING else —
#: not `closed_at`, not `deposit_on_file` — and any remainder stays OUTSTANDING
#: on an open account (`outstanding_at_cut` is the record of it). Nothing is
#: written off.
DISCONNECTED_STATUS_ASSIGNED: dict[str, Any] = {
    "code": "disconnected_status_assigned_at_the_cut",
    "br_ref": "BR-CUS-107 · BR-CUS-103 · BR-CUS-110 · `DSC-02.4` · PO ruling 2026-08-30",
    "tracks": None,
    "detail": "the cut writes BR-CUS-107's `Disconnected` status on the account, in behaviour "
    "class `non_billable`, in the same act that raises the final metered bill for the days "
    "before it. PO 2026-08-30: *'when we disconnect - we generate final bill at that time "
    "itself - so later bill is not required ... entire workflow including all settlement and "
    "status update is taken care at time of disconnect or move out - so account status changes "
    "and outstanding is pending on account if any'*. The status is what removes the account from "
    "`selectors.accounts_for_bill_run`, and that is now CORRECT because the bill has already "
    "been raised — on `A-11488`, cut 18 August, the 18 days it used are billed at the cut "
    "($23.23 of a $40.00 base plus the consumption) instead of by nobody. `DSC-02.4` is "
    "untouched: no close, no deposit settlement, no meter removal, and any remainder stays "
    "outstanding on an OPEN account. The status the account held before the cut is recorded on "
    "the case as history; a restoration returns the account to Active (DEF-CUS-10668).",
}

#: ⛔ **THE ONE CASE WHERE THE STATUS IS NOT WRITTEN, AND IT IS THE SAFETY RULE
#: OF THIS WHOLE CHANGE.** The status is lawful BECAUSE the bill was raised. If
#: billing REFUSES the account — no tariff version in force at the service date,
#: no plan, a held period overlapping the window, a template that cannot be
#: pinned — then the days before the cut are NOT billed, and writing the status
#: would drop the account out of every future run with those days still unbilled.
#: That is `OQ-1170`'s defect exactly, and it is what this rule prevents:
#:
#:     `Disconnected` is written only when the days up to the cut are billed —
#:     or provably have nothing left to bill.
#:
#: So a blocked bill leaves the account on its existing BILLABLE status, in the
#: run, with the dark days that `service_off_windows` publishes still subtracted
#: by `gather` — the pre-ruling behaviour, which is the right behaviour for an
#: account whose configuration a human has to fix first. The CUT still happens
#: (a household's supply is not left on because its tariff has no version) and
#: the reason travels on the payload and into `audit_log`.
CUT_BILL_BLOCKED_SO_STATUS_HELD: dict[str, Any] = {
    "code": "cut_bill_blocked_status_not_written",
    "br_ref": "BR-CUS-107 · BR-CUS-103 · BR-BIL-015 · PO ruling 2026-08-30",
    "detail": "billing could not raise the final bill for the days before this cut, so the "
    "`Disconnected` status was NOT written and the account stays in the bill run. Writing it "
    "would remove the account from `selectors.accounts_for_bill_run` with those days still "
    "unbilled, which is the $23.23 OQ-1170 was raised about. The cut itself is recorded — the "
    "supply is off — and the account will be billed by the next ordinary run once the "
    "configuration billing named is fixed, with the dark days after the cut already subtracted "
    "(BR-CUS-103). The engine's own sentence travels on `cut_bill.detail`.",
}

#: ⚠ **AND THE STATUS A RESTORATION CANNOT WRITE.** Until 2026-10-29
#: `restore_service` returned the account to `disconnect_cases.status_before_cut`
#: and this named a NULL or deleted code there. Since `DEF-CUS-10668` (PO *"2A"*)
#: it writes Active, so the only thing left unresolvable is a tenant with no live
#: `active` row: the account keeps its status and the reason is named.
#: DEF-CUS-10668 (PO 2026-10-29, *"2A"*): a restored account returns to Active,
#: the seeded row by CODE (BR-CUS-055) — `services._default_active_status`'s
#: handle, which `Marked disconnect` cannot be mistaken for.
RESTORED_STATUS_CODE = "active"

RESTORED_STATUS_NOT_RECORDED: dict[str, Any] = {
    # The code is kept (it is a wire value two readers name); its meaning moved
    # on 2026-10-29 from "the pre-cut status" to "the Active row".
    "code": "status_before_cut_not_resolvable",
    "br_ref": "BR-CUS-107 · BR-CUS-055 · PO ruling 2026-10-29 (DEF-CUS-10668)",
    "detail": "this tenant has no live `active` account status, so this restoration left the "
    "account status untouched. Service is restored; set the account's status by hand from the "
    "accounts screen.",
}

#: ⚠ **"BLOCKS NEW SERVICE ELSEWHERE" IS BUILT AS A READ AND NOTHING CONSUMES
#: IT.** B18 §5.8.7's own finding: *"'Blocks new service elsewhere until it is
#: settled' is a CROSS-PREMISES rule with no id: a debt at one address stops a
#: move-in at another. That reaches into move-in, which does not check it."*
#: `new_service_block_for()` below is the state; hard-won law 2 is why this
#: constant exists rather than a quiet assumption that somebody will call it.
NEW_SERVICE_BLOCK_UNCONSUMED: dict[str, Any] = {
    "code": "new_service_block_not_consumed",
    "br_ref": "`DSC-02.4` · B18 §5.8.7",
    "detail": "the block is COMPUTED here and read by nothing. Measured 2026-08-25: no move-in, "
    "service-request or account-creation path in this repo calls it, so a customer cut at one "
    "address can take service at another today. The rule has no BR id at all, and its SUBJECT is "
    "unstated in the same way BR-CUS-097's is: `elsewhere` means another premises, and whether "
    "the block follows the ACCOUNT, the CUSTOMER or the person named on it is written nowhere. "
    "This read answers for the account the debt is on and names no other party.",
}

#: ✅ **THE SUBJECT IS RULED AS OF 2026-09-25 — `BR-CUS-1100`, CLOSING `OQ-384`.**
#: PO, verbatim: *"you ahve to mark account and Customer ID also"*. The block is
#: carried by the **ACCOUNT** and by the **CUSTOMER** record, and **NOT by the
#: premises**: marking the customer catches them applying at a DIFFERENT address,
#: and not marking the address means a NEW TENANT at that same unit is not
#: punished for the previous occupant's debt. The third reading `OQ-384` offered
#: — the PERSON, catching a spouse on another customer record — was not chosen.
#: ⚠ **THE `detail` ABOVE STILL SAYS THE SUBJECT IS UNSTATED. IT IS NOW STATED,
#: AND THE SENTENCE IS LEFT BECAUSE ITS OTHER HALF IS STILL TRUE:** this block is
#: COMPUTED and consumed by nothing but tests, so the screen's promise is still
#: unkept (hard-won law 2). The ruling gave it a subject; it did not wire it.
#: Whoever wires it rewrites this sentence in the same commit.
#: ⚠ **AND TWO THINGS ARE THIS REPO'S READING, NOT THE PO'S WORDS** — they were
#: told we will build them unless they say otherwise: the mark **WARNS and does
#: not refuse** (`BR-CUS-1096`'s principle again), and **"settled" includes an
#: AGREED PAYMENT PLAN**, because `BR-CUS-1097` lets a clerk reconnect on a plan
#: and a plan that did not clear the mark would put the two rules in
#: contradiction.

#: ⚠ **A CREW CAN ATTEND AND NOT CUT, AND NOTHING CAN RECORD THAT.**
#: `DSC-02.3`'s CREW banner, verbatim: *"A remote cut happens on the date. A
#: visit has to be scheduled, and **the crew will not attend if somebody is home
#: and disputes it on the doorstep**."* B18 §5.8.7 draws the consequence:
#: *"a cut can fail on the doorstep and the case must be able to record
#: *attended, not cut, disputed*. No outcome vocabulary covers it."*
#:
#: It is NOT invented here. `commit_cut` records a cut that HAPPENED; there is
#: no call that says a crew attended and left. A case whose crew turned back
#: stays `scheduled` — which is wrong in a knowable way (it will read as a cut
#: still pending on a date that has passed) and is reported rather than papered
#: over with a state nobody ruled.
#:
#: ✅ **THE RULING ARRIVED ON 2026-09-20 AND THIS CONSTANT IS AMENDED IN PLACE,
#: NOT DELETED.** PO, verbatim: *"The register reflects reality. Today a failed
#: visit is invisible and the case looks untouched."* The four outcomes are
#: theirs — **locked gate, paid at the door, disputed, access refused** — and
#: `apps/customers/disconnect_visits.record_outcome` is the door. `OQ-383` is
#: CLOSED and the rule is `BR-CUS-1083`.
#:
#: It keeps its NAME, its CODE and its place for `VISIT_NOT_SCHEDULED`'s reason:
#: a screen, a test and a support person all read it by name, and deleting it on
#: the day its case stopped happening would break every one of them to save a
#: paragraph. **What changed is the `detail`**, which now says where the door is
#: instead of saying there is none — because the old sentence was the only thing
#: a clerk would have read, and it would have told them to stop looking.
CREW_OUTCOME_UNRECORDABLE: dict[str, Any] = {
    "code": "crew_attended_not_cut_unrecordable",
    "br_ref": "BR-CUS-1083 (PO 2026-09-20, closing `OQ-383`) · `DSC-02.3` CREW banner",
    "detail": "the crew *'will not attend if somebody is home and disputes it on the doorstep'*, "
    "and until 2026-09-20 there was no outcome to record that — such a case stayed `scheduled` "
    "with a date in the past. **There is one now.** The PO named four: a locked gate, access "
    "refused, paid at the door, and disputed. Record the visit on the case record and the case "
    "MOVES: the first three clear the cut date and return the case to `notice_sent` so it can "
    "be re-scheduled, and a doorstep dispute stops the ladder with the reason B18 §5.8.3 "
    "already names. This key rides a cut that HAS happened, where no such outcome was "
    "recorded; the visit is a different act on a case still scheduled.",
}

#: ⚠ **THE DOOR OPENED ON 2026-09-05 (CR-070 wave P, `US-WRK-039`) AND THIS
#: CONSTANT KEEPS ITS NAME, ITS CODE AND ITS PLACE.** It reads exactly as it did
#: when it was written, and every sentence in it was TRUE then: `work_orders` is
#: metering's table and a cross-module write was forbidden with no seam to go
#: through. What changed is not the rule — it is that Work became a module on
#: 2026-09-03 with a read-only seam per neighbour and one named write door, so
#: there is now a lawful way to ask. `mark_reconnecting` books the visit through
#: `seams.raise_flow_work_orders`, and `apps/customers` still writes nothing to
#: `work_orders` (`BR-WRK-002`, `A7`, `G102`).
#:
#: ⚠ **AND IT IS STILL RETURNED, ON EXACTLY THE CASE IT WAS ALWAYS ABOUT** — a
#: reconnect where no visit was booked, because nobody ticked one or because the
#: raise failed. Deleting a constant that a screen, a test and a support person
#: all read by name, on the day its OTHER case stopped happening, would break
#: every one of them to save a paragraph. The name is not renamed for the same
#: reason `VISIT_NOT_SCHEDULED` is what it says: a visit that is not scheduled.
VISIT_NOT_SCHEDULED: dict[str, Any] = {
    "code": "reconnection_visit_not_scheduled",
    "br_ref": "B18 §5.8.4 · BR-MET-110 · B2 §2 · BR-WRK-055 (2026-09-05)",
    "detail": "§5.8.4's reconnect flow is *'payment confirmed → visit scheduled → restored'* and "
    "no visit was booked on this one. Since 2026-09-05 the reconnect CAN book it — the clerk "
    "ticks the job on the account's disconnect surface and Work raises it through its own seam — "
    "so this rides only a reconnect where none was ticked or where the raise did not succeed. "
    "`RECONNECTING` still means a visit is DUE: B18 §5.8.1's own caption, *'paid, awaiting a "
    "visit'*.",
}

#: hard rule 7 as this module widens it — see the module docstring. The cut and
#: the two steps back are service actions against a named customer, and each one
#: writes its row.
AUDIT_CUT_COMMITTED = "disconnect.cut.committed"
AUDIT_RECONNECTING = "disconnect.reconnection.started"
AUDIT_RESTORED = "disconnect.service.restored"


class DisconnectRuleError(Exception):
    """What this module raises when a disconnect step is refused by a rule.

    Deliberately NOT one of the `core.errors` catalog exceptions, and the split
    is `apps/payments/exceptions.PaymentRuleError`'s, for its reason: those
    carry an HTTP status because they answer a request, and these are raised
    inside paths that answer none.

    ⚠ **AND IT CARRIES NO `message_key`, WHICH IS A DELIBERATE CHOICE.** G32 is
    a ratchet — *"no `message_key` may be raised that does not resolve"* — and
    the locale catalogues belong to another lane. Raising a key with no sentence
    behind it would make the refusal SILENT on screen, which the ruling behind
    G32 calls *"worse than the defect being fixed"*. The proposed keys are
    written to the lane's `newkeys-S3.json` instead; the API boundary that
    mounts S90 translates this exception into one catalog code carrying
    `br_ref` and this sentence, exactly as `apps/payments/api._as_catalog_refusal`
    already does for its own.
    """

    def __init__(self, message: str, *, code: str, br_ref: str) -> None:
        super().__init__(message)
        self.code = code
        self.br_ref = br_ref


# ════════════════════════════════════════════════════════════════════════════
# THE THREE TABLES (task 7.5)
# ════════════════════════════════════════════════════════════════════════════
class DisconnectCase(models.Model):
    """One disconnection or post-closure collections case (B18 §5.8, W7 7.5).

    ONE OPEN CASE PER ACCOUNT, held by the database rather than by a
    SELECT-then-INSERT: two clerks on two screens is exactly the race a check in
    Python loses, and the loser gives one debt two cut dates. The partial unique
    index is `apps/payments/collections_models.PaymentPlan`'s precedent.

    `tier` is the B18 §5.8.2 chip and NOT payments' rung — see the module
    docstring's vocabulary section, and `ladder_tier_of()`, which is the one
    place that answers "which tier is this account on" so that folding this
    column into `account_collection_state` later is a move rather than a
    redesign.

    `sequence` is what makes BR-CUS-082's *"a collections sequence, not a
    service one"* a property of the data. `assert_cut_reachable()` reads it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: CR-039 wave D task 16 — *"the same for disconnect"*. The reference a
    #: clerk reads back to a customer holding a disconnection notice, allocated
    #: by `_allocate_case_no` INSIDE the transaction that opens the case.
    #:
    #: ⚠ **AMENDED 2026-08-27 — `OQ-427` IS CLOSED AND THIS IS NO LONGER NULL ON
    #: EVERY ROW.** PO verbatim, in full: *"it needs its own series"*. The
    #: `disconnect_case` series is catalogued at `DSC-{YY}-{0000}` — the FORMAT
    #: being the build's delegated choice, not the PO's — so a case opened on a
    #: provisioned tenant reads `DSC-26-0001` onwards. **It is still NULL on a
    #: host provisioned before the ruling** until `manage.py seed_demo --tenant
    #: <subdomain>` writes the row, so the reported absence below stays live.
    #: The original reasoning is kept because it is why the column shipped
    #: before the format did:
    #:
    #: ⚠ **NULL ON EVERY ROW TODAY — `OQ-427`, and that question has a THIRD
    #: answer the transfer one does not.** B18 §5.8 draws no case reference
    #: (§5.8.2's columns are `ACCOUNT · CUSTOMER · ADDRESS · OWED · TIER · CUT
    #: DATE · LAST NOTICE · STATE`; §5.8.6's nine rows carry account numbers) —
    #: **and r10 draws a disconnection as a WORK ORDER**, verbatim *"Disconnect
    #: work order raised · WO-4833"*, against a `work_order` series that is
    #: seeded into every tenant and has no live caller. Whether this case is its
    #: own document or that work order is a product judgment, not a lane's, so
    #: no series is minted and the allocator reports rather than invents.
    case_no = models.TextField(null=True, blank=True)
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    sequence = models.TextField(default=SEQ_SERVICE)
    state = models.TextField(default=STATE_NOTICE_SENT)
    #: NULL means "no chip" — either nothing has been sent yet, or the account
    #: sits on payments' `second_5_day` rung, which B18 draws no chip for.
    tier = models.TextField(null=True, blank=True)
    tier_reached_on = models.DateField(null=True, blank=True)

    #: CLAUDE.md rule 2 as re-signed 2026-08-22: money is STORED to 4 decimals.
    #: This is what was owed WHEN THE CASE WAS OPENED — a fact about the case,
    #: never the live balance, which is read from AR every time it is needed.
    amount_owed_at_open = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.CharField(max_length=3)

    opened_on = models.DateField()
    #: A STORED DATE THAT NOTHING WATCHES — see `NO_SCHEDULER`.
    next_step_due = models.DateField(null=True, blank=True)
    cut_scheduled_for = models.DateField(null=True, blank=True)
    cut_on = models.DateField(null=True, blank=True)
    reconnected_on = models.DateField(null=True, blank=True)

    # ── 7.8 / 7.9 — WHAT THE CUT RECORDED AND WHAT IT WILL COST TO UNDO ────
    #: `DSC-02.1`'s five reason cards. **RECORDED AND READ BY NOTHING** — see
    #: `REASON_DRIVES_NOTHING`. It is stored so the regulator-facing record can
    #: say WHY a household was cut, which is the one question this table exists
    #: to answer and the one B18 §5.8.7 notes nothing keys off.
    cut_reason = models.TextField(null=True, blank=True)
    #: The service codes FULLY DISCONNECTED — `DSC-02.1`'s *"One decision per
    #: service, not all or nothing"*. A service marked `leave_connected` is
    #: simply absent; a service marked `restrictor` never reaches this column,
    #: because `assert_treatments_expressible` refuses it by name
    #: (`RESTRICTOR_UNBUILDABLE` — the schema holds two states and a restrictor
    #: is a third).
    services_cut = models.JSONField(default=list)
    #: CLAUDE.md rule 2 as re-signed 2026-08-22 — money is STORED to 4 decimals.
    #: What the tenant's `CC-RECON` charge code carried on the day of the cut,
    #: never a literal (BR-BIL-007) and never the live catalogue price: the
    #: figure quoted to the customer BEFORE service was taken away is the figure
    #: the record has to keep. ⚠ **It is not in AR** — `FEE_POSTED`.
    reconnection_fee_amount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    #: WHICH code it came from, so the amount can be traced back to the row a
    #: tenant edited rather than to this module.
    reconnection_fee_code = models.TextField(null=True, blank=True)
    #: `DSC-02.4`'s deposit radio — `held` or `applied_against_arrear`. The
    #: ELECTION, never a posting: applying a deposit is a balance-sheet move and
    #: only the ledger posting service writes those (rule 5).
    deposit_disposition = models.TextField(null=True, blank=True)

    # ── CR-052 W0 task 1 — THE DISCONNECT IS THE WHOLE EVENT (PO 2026-08-30) ─
    #: The account status CODE this account held on the day it was cut. A
    #: HISTORICAL FACT that decides nothing since 2026-10-29: it was written so
    #: `restore_service` could put it back (CR-052 W0, `OQ-1170`'s second half),
    #: and the PO then ruled a restored account returns to Active instead
    #: (*"2A"*, `DEF-CUS-10668` — the mark clears). Still recorded at the cut.
    #:
    #: A CODE and not an FK, deliberately: statuses are per-tenant rows a tenant
    #: may replace, and a code survives a row being re-created where an id does
    #: not.
    status_before_cut = models.TextField(null=True, blank=True)
    #: CLAUDE.md rule 2 as re-signed 2026-08-22 — money is STORED to 4 decimals,
    #: displayed at 2. What the account owed once the whole event had happened:
    #: the final metered bill raised at the cut, the reconnection fee, and
    #: everything that was already outstanding. **The PO's own words: *"account
    #: status changes and outstanding is pending on account if any"*.**
    #:
    #: ⚠ **IT IS A RECORD, NOT A BALANCE.** The live balance is read from AR
    #: every time it is needed (`_balance_for`); this is what was outstanding at
    #: the moment of the cut and it never changes again. Nothing is written off
    #: and nothing is closed — `DSC-02.4` forbids both, and the ruling of
    #: 2026-08-30 is explicit that the cut leaves the account OPEN.
    outstanding_at_cut = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    #: §5.8.3's by-hand stop — *"the modal exists for clerk error, a dispute, or
    #: a regulator instruction"*. NULL on every ladder that stopped ITSELF,
    #: which is the ordinary case and leaves no row to write.
    stopped_on = models.DateField(null=True, blank=True)
    stopped_reason = models.TextField(null=True, blank=True)

    #: 🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration `customers/0060_cr125`,
    #: ledger row in `12-governance/09-human-review-ledger.md`.
    #:
    #: ⚠ **`What happened` — THE DRAWN FREE-TEXT NOTE ON A LADDER STOP, AND THE
    #: DECISION TO MAKE IT A COLUMN IS RECORDED HERE RATHER THAN INFERRED.**
    #:
    #: Blueprint p137 draws, under the three stop reasons, a text field labelled
    #: `What happened` holding *"Customer disputes INV-26-0411 on a meter
    #: reading"*, captioned *"Recorded with the act and with who did it."*
    #: Before `CR-125-BRC07` there was **no parameter and no column**:
    #: `stop_by_hand` took `reason`, one of three CODES, and nothing else.
    #:
    #: **THREE OPTIONS WERE OPEN AND THE THIRD WAS CHOSEN:**
    #:
    #: (a) *Put it in `audit_log` only.* Refused. `audit_log` is PRUNED on a
    #: retention schedule (CLAUDE.md hard rule 4's own note; whether an audit row
    #: may be exempt is `OQ-1340` and is OPEN). A note that says why a utility
    #: STOPPED chasing a real debt is exactly the record a regulator or an
    #: auditor asks for a year later, and a home that ages out is not a home.
    #:
    #: (b) *Reuse `stopped_reason`.* Refused, and this is the one that looks
    #: cheapest. `stopped_reason` holds a CODE from a closed set of three
    #: (`STOP_REASONS`), and `stop_by_hand` refuses anything else BY NAME
    #: precisely so *"a fourth way to stop chasing a real debt needs a ruling"*.
    #: Widening it to carry prose would delete that guard in the act of reusing
    #: the column — a closed vocabulary and a free-text field cannot be the same
    #: column, and the day somebody writes a sentence into it the check that
    #: refuses a fourth reason stops working.
    #:
    #: (c) **A COLUMN OF ITS OWN. CHOSEN.** It is the shape this module already
    #: uses one class over — `AccountProtection.note` is the same fact about the
    #: same kind of act — so it adds no new idea. WHO did it and WHEN are
    #: already recorded (`_audit` names the actor; `stopped_on` is the date), so
    #: the caption's *"with the act and with who did it"* is satisfied by the
    #: three together.
    #:
    #: ⚠ **NULLABLE, AND IT IS NOT MADE REQUIRED.** Every existing stopped case
    #: has none, a backfill would be fiction, and requiring one would refuse a
    #: stop — which on this ladder means letting a disconnection continue
    #: because a clerk had nothing to type. The note is evidence, never a gate.
    #:
    #: ⚠ **IT IS OURS TO DECIDE AND IT IS WRITTEN DOWN** (hard-won law 13): it
    #: collides with no signed rule, moves no ❄️ FROZEN figure and is not a fact
    #: only the PO holds, so a question here would have been the failure to make
    #: a decision. Decision log 2026-09-20.
    stopped_note = models.TextField(null=True, blank=True)

    # ── BR-CUS-430 / BR-CUS-431 (DEF-724) — THE CLOSE-OUT ─────────────────
    #: The day the ACCOUNT was closed out — the administrative act, which is
    #: NOT the day service ended. `accounts.closed_at` takes the CUT date
    #: (BR-CUS-431, and the derivation is there, not here); this column is the
    #: other half, so the record reads *the service ended on the cut date and
    #: the account was closed out on this later day*. Keeping them apart is the
    #: whole of *"cleaner in the record"*: a regulator reading one row can tell
    #: a disconnection from a departure, which is what a relaxed `move_out`
    #: would have destroyed.
    closed_out_on = models.DateField(null=True, blank=True)
    #: WHO closed it out. The `BR-CUS-097` `tied_back_by` precedent, for the
    #: same reason: a permanent, un-writable-back act should be readable
    #: without joining the audit row to find a person.
    closed_out_by = models.TextField(null=True, blank=True)
    #: WHY, in the clerk's own sentence. ⚠ **FREE TEXT, AND THAT IS A REPORTED
    #: GAP RATHER THAN A DESIGN** — see `close_out.REASON_VOCABULARY_UNRULED`
    #: and `OQ-830`. `accounts.close_reason` has been PROPOSED-SCHEMA since
    #: 2026-08-08 with no ruled vocabulary, and a fixed list invented by a lane
    #: would be a permanent record of a category nobody signed.
    close_out_reason = models.TextField(null=True, blank=True)

    #: `CR-094-BRC01` — **the service request this case was raised from**,
    #: `BR-CUS-080`'s CHILD half. NULL on every case the collections ladder
    #: opens by itself, which is the ordinary way a case starts; a case raised
    #: by approving a customer's DISCONNECT request (`BR-CUS-091`, PO
    #: 2026-08-24 — *"Yes customer can request it"*) names the application.
    #:
    #: ⚠ NO FOREIGN KEY — migration 0048 gives the reasons; the short one is
    #: that the link is evidence rather than integrity.
    request_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "customers"
        db_table = "disconnect_cases"
        indexes = [
            models.Index(fields=["tenant", "state"], name="ix_dsc_case_state"),
            models.Index(fields=["tenant", "cut_scheduled_for"], name="ix_dsc_case_cut_date"),
            # `CR-094-BRC01` — given a request, find the case it became.
            models.Index(fields=["tenant", "request_id"], name="ix_dsc_case_request"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "account"],
                condition=~Q(state__in=CLOSED_CASE_STATES),
                name="uq_one_open_disconnect_case_per_account",
            ),
            # CR-039 wave D task 16 (migration 0028). Per tenant,
            # case-INSENSITIVE, and only where a number exists — the shape
            # `uq_customers_tenant_customer_no_ci` established. The partial
            # predicate is what lets this column exist while OQ-427 is open:
            # every row is NULL today and NULLs must not collide. `Lower(...)`
            # is there because a clerk typing `dsc-26-0001` means the row that
            # reads `DSC-26-0001`, and BR-TEN-035 never reuses a number.
            models.UniqueConstraint(
                models.F("tenant"),
                Lower("case_no"),
                condition=Q(case_no__isnull=False),
                name="uq_disconnect_cases_tenant_case_no_ci",
            ),
            models.CheckConstraint(
                condition=Q(sequence__in=SEQUENCES), name="ck_disconnect_case_sequence"
            ),
            models.CheckConstraint(
                condition=Q(state__in=CASE_STATES), name="ck_disconnect_case_state"
            ),
            # BR-CUS-082: *"a closed account cannot be escalated to
            # disconnection — there is nothing left to disconnect"*. The
            # SECOND of two independent guards; `assert_cut_reachable()` is the
            # first. Removing either one still leaves a cut on a collections
            # case impossible, which is the point of writing it twice.
            models.CheckConstraint(
                condition=~Q(sequence=SEQ_COLLECTIONS)
                | Q(cut_scheduled_for__isnull=True, cut_on__isnull=True),
                name="ck_collections_sequence_never_cuts",
            ),
            models.CheckConstraint(
                condition=Q(cut_reason__isnull=True) | Q(cut_reason__in=CUT_REASONS),
                name="ck_disconnect_case_cut_reason",
            ),
            models.CheckConstraint(
                condition=Q(deposit_disposition__isnull=True)
                | Q(deposit_disposition__in=DEPOSIT_DISPOSITIONS),
                name="ck_disconnect_case_deposit_disposition",
            ),
            # A CUT ROW CARRIES THE PRICE OF COMING BACK. `DSC-02.4` quotes the
            # reconnection fee *"so the customer is told what it will cost to
            # get service back before it is taken away"* — so a row saying
            # service was cut, with no fee and no deposit election beside it, is
            # a record that cannot answer the question the customer will ask
            # first. `commit_cut` refuses before it writes; this is what makes
            # it true of the DATA (hard-won law 1).
            models.CheckConstraint(
                condition=Q(cut_on__isnull=True)
                | Q(
                    reconnection_fee_amount__isnull=False,
                    reconnection_fee_code__isnull=False,
                    deposit_disposition__isnull=False,
                ),
                name="ck_cut_records_the_price_of_coming_back",
            ),
        ]


class DisconnectNotice(models.Model):
    """One notice on a case — APPEND-ONLY (task 7.5).

    This is the record a utility shows a regulator when a customer says they
    were never told, and a row that can be edited afterwards is not that record
    (hard rule 4 in spirit; the same posture `notice_history` takes and states).

    ⚠ **`delivery_state` IS NULL ON EVERY ROW THIS MODULE WRITES.** Task 7.10:
    *"`LAST NOTICE` renders the absence of a delivery adapter, never a
    fabricated `emailed`"*. `DELIVERY_UNAVAILABLE` carries the reason to the
    caller so the column can render the absence rather than a blank.

    ⚠ **AND IT OVERLAPS `notice_history`** (payments), which already records
    every send and every skip with a tier. See the module docstring — DEF-675's
    shape, reported rather than resolved by this lane.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    case = models.ForeignKey(
        DisconnectCase, on_delete=models.PROTECT, db_column="case_id", related_name="notices"
    )
    tier = models.TextField()
    #: What was DELIVERED and how. NULL, always, today — see the class docstring.
    delivery_state = models.TextField(null=True, blank=True)
    delivery_unavailable_reason = models.TextField(null=True, blank=True)
    issued_on = models.DateField()
    actor = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="actor_id"
    )
    detail = models.JSONField(default=dict)

    # ── BR-CUS-100's PROOF OF SERVICE — six columns, and every one is NULL on
    # a notice that has been RAISED and not yet SERVED ────────────────────────
    #
    # BR-CUS-100 (PO 2026-08-25, closing DEF-692), verbatim: *"`disconnect_notices`
    # CANNOT HOLD THE PROOF TODAY. It carries `tier`, `delivery_state`,
    # `delivery_unavailable_reason`, `issued_on`, `actor` and `detail` — enough to
    # say a notice was raised, **not enough to say it was served, by what means, or
    # that a signature came back.** Owed: a proof reference, a served-at date and
    # the serving channel, entered by a human, on the same discipline `BR-MET-110`
    # applies to a field result — somebody decided, and the record must name them."*
    #
    # ⚠ **THESE ARE NOT A SECOND `delivery_state`, AND CONFLATING THE TWO IS THE
    # DEFECT.** `delivery_state` is a claim this product makes about a SEND it
    # performed, and it stays NULL with its reason because no email, SMS or print
    # adapter exists (`DELIVERY_UNAVAILABLE`). These six are a record of something
    # that happened OUTSIDE this product and that a person is attesting to. Writing
    # one must never write the other; `record_proof_of_service` touches no delivery
    # column and `tests/test_w7_proof_of_service.py` asserts that it does not.
    #
    # ⚠ **AND THE NULLS ARE THE QUEUE.** `BR-MET-110`'s `work_orders.accepted_by`
    # says the same of itself in `apps/metering/connections.py`: *"Nullable because
    # an order can be completed and not yet reviewed — that gap IS the review
    # queue, and a NULL here is the only thing that says an order is waiting for a
    # person."* A raised notice with no proof is a notice waiting for one, and
    # `notices_awaiting_proof()` is the read that lists them.
    #
    #: HOW it was served — one of `SERVICE_CHANNELS`, `DSC-02.3`'s own five.
    #: Never `in_app`: that is a SEND, and the refusal says so by name.
    service_channel = models.TextField(null=True, blank=True)
    #: WHAT a regulator asks to see — the tracking or article number of the
    #: posted item. BR-CUS-100 names *"the reference"* as one of the three
    #: things the record IS, so it is required whenever proof is recorded.
    proof_reference = models.TextField(null=True, blank=True)
    #: WHEN it was served. A business date supplied by the recorder, never a
    #: wall clock (BR-TEN-043) — the item was posted on the day it was posted.
    served_on = models.DateField(null=True, blank=True)
    #: WHEN the signature came back — `DSC-02.3`'s *"certified mail, signed
    #: for"*. **Nullable even on a fully recorded proof:** a certified item can
    #: be posted today and signed for on Thursday, and refusing to record the
    #: posting until the signature returns would lose the only date the
    #: statutory period is computed from. ⚠ Whether a tier-3 cut requires the
    #: SIGNATURE to have come back, or only that certified mail was sent, is
    #: **not written in any signed document** — it is REPORTED as owed and is
    #: not decided here; `assert_service_proved` does not read this column.
    signed_for_on = models.DateField(null=True, blank=True)
    #: WHO entered it. `BR-MET-110` is cited by BR-CUS-100 as the same
    #: discipline: *"somebody decided, and the record must name them"*.
    proof_recorded_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="proof_recorded_by",
    )
    #: WHEN they entered it — the mirror of `work_orders.accepted_at`. This one
    #: IS a wall clock and BR-TEN-043 is not violated: the business dates are
    #: `served_on` and `signed_for_on` above; this records the moment a person
    #: made the attestation, which is a fact about the audit trail.
    proof_recorded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "customers"
        db_table = "disconnect_notices"
        indexes = [
            models.Index(fields=["tenant", "case", "issued_on"], name="ix_dsc_notice_case"),
            # The QUEUE index: the notices waiting for a person. Partial, on the
            # NULL, for the reason the column comment gives — the gap is the
            # worklist and a worklist is read far more often than it is written.
            models.Index(
                fields=["tenant", "tier"],
                condition=Q(proof_recorded_at__isnull=True),
                name="ix_dsc_notice_unproved",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(tier__in=LADDER_TIERS), name="ck_disconnect_notice_tier"
            ),
            # `in_app` cannot reach this column, and the database is what makes
            # that true of the DATA rather than only of `record_proof_of_service`
            # (hard-won law 1: a comment claiming a guarantee is not the
            # guarantee). NULL is allowed — that is a notice not yet served.
            models.CheckConstraint(
                condition=Q(service_channel__isnull=True) | Q(service_channel__in=SERVICE_CHANNELS),
                name="ck_disconnect_notice_service_channel",
            ),
            # ALL OR NOTHING. A half-recorded proof is the shape that would let
            # `assert_service_proved` pass on a row naming no channel and no
            # article number — a cut authorised by a record that says nothing.
            # Either every part of BR-CUS-100's record is present, or the notice
            # is unserved and sits in the queue. `signed_for_on` is deliberately
            # outside both halves of the AND: see the column comment.
            models.CheckConstraint(
                condition=(
                    Q(
                        service_channel__isnull=True,
                        proof_reference__isnull=True,
                        served_on__isnull=True,
                        signed_for_on__isnull=True,
                        proof_recorded_at__isnull=True,
                    )
                    | Q(
                        service_channel__isnull=False,
                        proof_reference__isnull=False,
                        served_on__isnull=False,
                        proof_recorded_at__isnull=False,
                    )
                ),
                name="ck_disconnect_notice_proof_all_or_nothing",
            ),
        ]


class AccountProtection(models.Model):
    """A medical certificate, a payment-plan hold, or a weather moratorium.

    THE THREE LIFETIMES ARE HELD BY `ck_protection_lifetime`, not by a comment:

      * `medical_certificate` — `expires_on` NOT NULL. A certificate with no end
        date is a permanent exemption nobody signed.
      * `payment_plan` — `expires_on` MUST BE NULL. BR-CUS-043 grants no date;
        the hold lives *while the plan is active AND current* and lapses the day
        an instalment is missed (BR-PAY-016 as amended, OQ-170, no grace). Its
        liveness is READ from payments every time it is asked.
      * `weather_moratorium` — `effective_from` AND `expires_on` NOT NULL, and
        `set_by` defaults to `regulator`: B18 §5.8.3 calls it *"a date window
        set by the regulator, not by the tenant"*.

    ⚠ **THIS TABLE IS WHERE A CLINICAL FACT FINALLY LIVES.**
    `apps/payments/outstandings.py` carries the stated absence
    `medical_hold_not_readable` — *"`apps/customers` publishes no medical-hold
    selector"* — and three modules take the hold as an ARGUMENT because of it.
    `medical_hold_for()` is the read that closes it. The wiring is payments'
    and notifications' to do; see the module docstring.

    `lifted_on` + `lifted_reason` end a protection WITHOUT deleting it: the
    history of a hold that existed is what a regulator asks about, and a DELETE
    answers nothing. The same shape `delivery_return_events` uses for the
    bad-address flag, and for the same reason.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )
    kind = models.TextField()
    #: BR-TEN-043 — business dates, supplied by the caller, never a wall clock.
    effective_from = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    #: Who set it. The moratorium's default says the quiet part: the window is
    #: the regulator's and the product records it rather than computing it.
    set_by = models.TextField(default="tenant")
    #: For a `payment_plan` protection, WHICH plan — a deferred uuid rather than
    #: an FK, because `payment_plans` is payments-owned and B2 §2's reviewed FK
    #: set does not run in this direction (the B11 F-3 convention
    #: `notice_history.outbound_message_id` already uses for a boundary).
    reference_id = models.UUIDField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    lifted_on = models.DateField(null=True, blank=True)
    lifted_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "customers"
        db_table = "account_protections"
        indexes = [
            models.Index(fields=["tenant", "account", "kind"], name="ix_protection_account"),
            models.Index(fields=["tenant", "expires_on"], name="ix_protection_expiry"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=PROTECTIONS), name="ck_protection_kind"),
            # THE THREE LIFETIMES, held by the database. A protection with no
            # expiry and a protection that lapses are different objects.
            models.CheckConstraint(
                condition=(
                    Q(kind=PROTECTION_MEDICAL, expires_on__isnull=False)
                    | Q(kind=PROTECTION_PLAN, expires_on__isnull=True)
                    | Q(kind=PROTECTION_MORATORIUM, expires_on__isnull=False)
                ),
                name="ck_protection_lifetime",
            ),
        ]


# ════════════════════════════════════════════════════════════════════════════
# READS THAT BELONG TO OTHER MODULES — RESOLVED BY NAME, NEVER RE-IMPLEMENTED
# ════════════════════════════════════════════════════════════════════════════
def _resolve(module: str, attribute: str, kind: str) -> Any:
    """The owning module's callable, or None while its lane has not landed.

    `apps/customers/seams.py` publishes the same helper and this module uses it
    for the modules that seam already covers; this local copy exists only for
    `apps.payments.dunning`, which the customers seam does not name. Adding it
    THERE is the right home and that file is another lane's — REPORTED.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(target, attribute, None)
    return fn if callable(fn) else None


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    return core_tenancy.current_tenant_id()


# ═══════════════════════════════════════════════════════════════════════════
# THE CASE NUMBER (CR-039 wave D task 16) — allocated by name, never invented
# ═══════════════════════════════════════════════════════════════════════════
#: The catalogue KEY. Not a prefix, and not the thing `OQ-427` asks about — the
#: format a clerk reads out is the catalogue's to hold, and this key is what
#: `apps/metering/connections.py` calls `CONNECTION_SERIES`, one entity over.
DISCONNECT_CASE_SERIES = "disconnect_case"

#: `apps/metering/services._allocate_number`'s own code string, so a reader who
#: has met one stated absence has met all of them.
NUMBERING_SERIES_MISSING = "numbering_series_missing"

CASE_NUMBER_UNAVAILABLE: dict[str, Any] = {
    "code": NUMBERING_SERIES_MISSING,
    "series": DISCONNECT_CASE_SERIES,
    "open_question": "OQ-427",
    "detail": (
        "This case has no reference number yet. A number series for disconnections has not "
        "been set up, so nothing has been issued — the case is on the ladder as normal and "
        "only its reference is missing."
    ),
}


def _allocate_case_no() -> str | None:
    """BR-TEN-035 allocation for a disconnect case. **A missing series is
    REPORTED, never faked.**

    ⚠ **CALL THIS INSIDE THE TRANSACTION THAT CREATES THE ROW** — BR-TEN-035,
    and `apps/customers/services._allocate_account_no` is the precedent: the
    allocation and the `objects.create(...)` share one `atomic()` block, so a
    case never sits on file unnumbered even for the width of a transaction. A
    rolled-back open leaves a GAP in the counter, which BR-TEN-035 permits and
    prefers to a number issued twice.

    ⚠ **AMENDED 2026-08-27 — IT NO LONGER RETURNS `None` ON EVERY TENANT.** This
    said *"it returns `None` on every tenant today — `OQ-427`"*, and that
    question closed the same day on the PO's *"it needs its own series"*. The
    `disconnect_case` row is in `SERIES_CATALOG`, provisioning seeds it, and
    **not one line of this function changed** — which is what the wave D lane's
    refusal to invent a prefix bought.

    It still returns `None` on a host provisioned BEFORE the ruling, because
    `_seed_number_series` is `get_or_create` and the repair door is
    `manage.py seed_demo --tenant <subdomain>`. Reporting rather than raising is
    the difference between a case with no reference and no case at all: a
    household must not stay un-chased because nobody configured numbering, and
    the ladder's dates are regulated where its reference is not.
    """
    from core import numbering as core_numbering

    try:
        return core_numbering.next_number(DISCONNECT_CASE_SERIES, seams.tenant_today())
    except core_numbering.NumberingError:
        return None


def _collections_settings() -> dict[str, Any]:
    """The S70 collections family, or `{}` when it cannot be read.

    `{}` is never read as "the defaults": the ratified default lives once, in
    `apps.tenancy.settings_families`, and a copy here would be free to drift
    from the number on the tenant's own screen — the reason
    `seams.nsf_privilege_threshold` gives for returning None.
    """
    read = _resolve("tenancy", "settings_family", "selectors")
    if read is None:  # pragma: no cover - tenancy is always present in this tree
        return {}
    try:
        return dict(read(COLLECTIONS_FAMILY) or {})
    except Exception:  # pragma: no cover - defensive: a settings read must not chase
        return {}


def _decimal_setting(values: dict[str, Any], key: str) -> Decimal | None:
    raw = values.get(key)
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except Exception:  # pragma: no cover - the family types both DECIMAL
        return None


def _balance_for(account_id: Any) -> Decimal | None:
    """What the account owes, from the ledger, through the published seam.

    **None means the reading FAILED and is never read as zero.** A zero would
    stop the ladder (which is safe) — but `_balance_for` is also what a caller
    displays, and a fabricated $0.00 on an account in arrears is DEF-628's
    shape. The halt code says which reading failed.
    """
    positions = seams.ar_positions([account_id])
    if not positions.available:
        return None
    amount = positions.amount_for(account_id)
    return None if amount is None else Decimal(str(amount))


def _plan_pause(account_id: Any, *, as_of: date) -> Any:
    """payments' own pause decision, or None while that lane is absent.

    Resolved BY NAME. Re-deriving BR-CUS-043 here would be a second answer to
    "is this plan active and current", and the two disagree the day one is
    amended — which is the whole reason `apps/payments/dunning.py` resolves the
    customers-side rule in the opposite direction rather than copying it.
    """
    fn = _resolve("payments", "collections_pause_for", "dunning")
    return None if fn is None else fn(account_id, as_of=as_of)


def _account(account_id: Any) -> Any:
    from apps.customers import selectors

    return selectors.account_or_404(account_id)


#: BR-CUS-030 writes BOTH — *"`closed_at` = move-out date, status → closed"*.
CLOSED_STATUS_CODES = frozenset({"closed", "close", "final", "closed_final"})


def _account_is_closed(account: Any) -> bool:
    """BR-CUS-030's close — read from EITHER of the two facts it writes.

    The rule sets `closed_at` AND moves the status, and this reads both because
    an account carrying one without the other is exactly the state a guard
    protecting somebody's water supply must not be fooled by. The status
    vocabulary is tenant-extensible (BR-CUS-055), so a status this function does
    not recognise falls back to the date.

    ⚠ **A STATUS THAT CANNOT BE READ AT ALL IS TREATED AS CLOSED.** The only
    caller refuses a cut on the answer, so the unreadable case fails toward
    NOT cutting somebody off (hard-won law 3).
    """
    if getattr(account, "closed_at", None) is not None:
        return True
    status = getattr(account, "status", None)
    code = getattr(status, "code", None) or status
    if code is None:
        return True
    return str(code).strip().lower() in CLOSED_STATUS_CODES


def _audit(actor: Any, action: str, entity_id: Any, *, after: dict[str, Any]) -> None:
    """CLAUDE.md rule 7, widened to service actions — see the module docstring.

    A disconnection is not a money action. It is a meter turned off at an
    address where somebody lives, and the record is the same record.
    """
    core_audit.write_row(
        action=action,
        entity_type="account",
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=None,
        after=after,
    )


def _money(amount: Decimal) -> dict[str, str]:
    """Rule 2's two shapes, labelled — the `move_out_settlement.serialize` idiom.

    A caller never has to decide which one it is holding: `stored` is the 4dp
    string that would be written, `display` is the 2dp string for the screen.
    Rounding happens once, on the display leg, in `core.money.finalize` (B4 ❄️).
    """
    from core import money

    return {"stored": f"{amount:.4f}", "display": f"{money.finalize(amount):.2f}"}


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.7 — THE THREE PROTECTIONS
# ════════════════════════════════════════════════════════════════════════════
def _plan_protection_is_live(account_id: Any, *, as_of: date) -> tuple[bool, str]:
    """LIFETIME_DERIVED — asked of payments, never of a stored date."""
    decision = _plan_pause(account_id, as_of=as_of)
    if decision is None:
        return False, (
            "`apps.payments.dunning` is not resolvable in this build, so whether the plan is "
            "active AND current cannot be answered. The protection does NOT hold on an "
            "unanswerable question: a hold nobody can justify is a debt nobody chases."
        )
    if getattr(decision, "paused", False):
        return True, str(getattr(decision, "detail", ""))
    return False, str(getattr(decision, "detail", ""))


def protections_for(account_id: Any, *, as_of: date) -> tuple[dict[str, Any], ...]:
    """Every protection standing on this account on `as_of`, with its lifetime.

    Each row carries WHY it is or is not in force, in the words of the rule that
    grants it, because a screen that says `HELD · MEDICAL` and cannot say until
    when is a screen that will be argued with.
    """
    rows: list[dict[str, Any]] = []
    stored = AccountProtection.objects.filter(tenant_id=_tenant_id(), account_id=account_id)
    for row in stored.order_by("effective_from", "kind"):
        lifetime = PROTECTION_LIFETIME[row.kind]
        lifted = row.lifted_on is not None and row.lifted_on <= as_of
        started = row.effective_from <= as_of
        if row.kind == PROTECTION_PLAN:
            live, why = _plan_protection_is_live(account_id, as_of=as_of)
            in_force = started and not lifted and live
            expiry: date | None = None
        else:
            expiry = row.expires_on
            in_force = started and not lifted and (expiry is None or expiry >= as_of)
            why = (
                f"the window runs {row.effective_from} → {expiry}"
                if row.kind == PROTECTION_MORATORIUM
                else f"the certificate expires {expiry}"
            )
        rows.append(
            {
                "id": str(row.pk),
                "kind": row.kind,
                "lifetime": lifetime,
                "in_force": bool(in_force),
                "effective_from": row.effective_from,
                "expires_on": expiry,
                "lifted_on": row.lifted_on,
                "set_by": row.set_by,
                "reason": why,
            }
        )
    return tuple(rows)


def medical_hold_for(account_id: Any, *, as_of: date) -> bool:
    """A15 via BR-CUS-039 — is this account excluded from every ladder step?

    **THIS IS THE READ `apps/payments/outstandings.py` SAYS DOES NOT EXIST.**
    Its stated absence `medical_hold_not_readable` reads, verbatim:
    *"`apps/customers` publishes no medical-hold selector, so the A15 exclusion
    cannot be shown as a column here. It is passed IN to every send
    (`notices.py`, `ladder.py`) by the caller that knows it"*. It exists now.

    ⚠ **AND NOTHING CALLS IT YET** (hard-won law 2 — built is not wired). The
    call site is a `_resolve` in payments and notifications, in files this lane
    does not own; both are REPORTED with the exact absence they carry today.
    """
    return any(
        row["in_force"]
        for row in protections_for(account_id, as_of=as_of)
        if row["kind"] == PROTECTION_MEDICAL
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def record_protection(
    actor: Any,
    account_id: Any,
    *,
    kind: str,
    effective_from: date,
    expires_on: date | None = None,
    set_by: str | None = None,
    reference_id: Any = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Put a protection on an account, with the lifetime its kind demands.

    The three shapes are refused HERE as well as in the database, because a
    `CheckConstraint` violation is an `IntegrityError` with a constraint name in
    it and a clerk deserves the sentence instead. The constraint stays because a
    guard in Python is not a guarantee about the data (hard-won law 1).
    """
    if kind not in PROTECTIONS:
        raise DisconnectRuleError(
            f"{kind!r} is not one of the three protections B18 §5.8.3 names "
            f"({', '.join(PROTECTIONS)}). A fourth protection freezes a real debt and needs a "
            "ruling, not a string.",
            code="protection_kind_unknown",
            br_ref="BR-CUS-039",
        )
    if kind == PROTECTION_MEDICAL and expires_on is None:
        raise DisconnectRuleError(
            "a medical certificate must carry the date it expires. A hold with no end date is a "
            "permanent exemption nobody signed, and the customer's own rights footer already "
            "tells them the certificate has to be renewed.",
            code="medical_certificate_needs_expiry",
            br_ref="BR-CUS-039",
        )
    if kind == PROTECTION_PLAN and expires_on is not None:
        raise DisconnectRuleError(
            "a payment-plan protection has no expiry date of its own. BR-CUS-043 holds it "
            "*while the plan is active AND current*, and a missed instalment lifts it the very "
            "next day with no grace (PO 2026-08-12, OQ-170, *'Immediate'*). A stored date here "
            "would be a second, slower answer to a question payments answers exactly.",
            code="plan_protection_takes_no_expiry",
            br_ref="BR-CUS-043",
        )
    if kind == PROTECTION_MORATORIUM and expires_on is None:
        raise DisconnectRuleError(
            "a weather moratorium is a date WINDOW set by the regulator (B18 §5.8.3), so it "
            "carries both ends. TC-DSC-5 requires the window's dates to be SHOWN when a step is "
            "refused, and a window with one end cannot be shown.",
            code="moratorium_needs_a_window",
            br_ref="BR-CUS-039",
        )

    row = AccountProtection.objects.create(
        tenant_id=_tenant_id(),
        account_id=account_id,
        kind=kind,
        effective_from=effective_from,
        expires_on=expires_on,
        set_by=set_by or ("regulator" if kind == PROTECTION_MORATORIUM else "tenant"),
        reference_id=reference_id,
        note=note,
    )
    after = {
        "protection_id": str(row.pk),
        "account_id": str(account_id),
        "kind": kind,
        "lifetime": PROTECTION_LIFETIME[kind],
        "effective_from": str(effective_from),
        "expires_on": str(expires_on) if expires_on else None,
        "set_by": row.set_by,
    }
    _audit(actor, AUDIT_PROTECTION_RECORDED, account_id, after=after)
    return after


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def lift_protection(
    actor: Any, protection_id: Any, *, on_date: date, reason: str
) -> dict[str, Any]:
    """End a protection WITHOUT deleting it.

    The history of a hold that existed is what a regulator asks about, and a
    DELETE answers nothing. A reason is required for the same reason BR-CUS-072
    requires one to reopen a refused request: an unexplained lift is a cut
    nobody can account for.
    """
    if not reason or not str(reason).strip():
        raise DisconnectRuleError(
            "lifting a protection needs a reason. The next step after a lift is a notice or a "
            "cut, and an unexplained lift is a cut nobody can account for.",
            code="lift_needs_a_reason",
            br_ref="BR-CUS-039",
        )
    row = AccountProtection.objects.get(tenant_id=_tenant_id(), pk=protection_id)
    row.lifted_on = on_date
    row.lifted_reason = str(reason).strip()
    row.save(update_fields=["lifted_on", "lifted_reason", "updated_at"])
    after = {
        "protection_id": str(row.pk),
        "account_id": str(row.account_id),
        "kind": row.kind,
        "lifted_on": str(on_date),
        "lifted_reason": row.lifted_reason,
    }
    _audit(actor, AUDIT_PROTECTION_LIFTED, row.account_id, after=after)
    return after


def protection_check(account_id: Any, *, as_of: date) -> dict[str, Any]:
    """B18 §5.8.4 step 2 — *"medical · plan · moratorium · dispute, each pass or
    fail with its reason"*.

    FOUR rows and only THREE protections, and the fourth is served as
    `unavailable` rather than `pass`: **nothing in this repository stores a
    disputed AMOUNT** (J08 step 7b(i), measured 2026-08-24), so a green "no
    dispute" would be a fabricated clearance on the screen that authorises a
    cut. ⚠ `metering.disputed_at` is a QUANTITY in dispute and is NOT this — J08
    names it as the obvious wrong wire, and it is four minutes away by grep.

    ⚠ **`outcome: "fail"` IS A STATEMENT ABOUT THE CHECK, NOT AN INSTRUCTION TO
    REFUSE ANYTHING.** Under `BR-CUS-1096` (PO 2026-09-25, closing `OQ-680`) a
    protection in force **warns** a clerk and never stops them, so a reader
    wiring this into a clerk-facing screen renders the row and its dates and
    leaves every control enabled. What `fail` still legitimately drives is the
    **unattended** ladder halt below (`HALT_PROTECTED`), which the ruling does
    not touch: a machine declining to send a certified letter is not a person
    being stopped.
    """
    live = protections_for(account_id, as_of=as_of)
    by_kind = {row["kind"]: row for row in live if row["in_force"]}
    rows: list[dict[str, Any]] = []
    for kind in PROTECTIONS:
        held = by_kind.get(kind)
        rows.append(
            {
                "check": kind,
                "outcome": "fail" if held else "pass",
                "lifetime": PROTECTION_LIFETIME[kind],
                "reason": held["reason"] if held else "no protection of this kind is in force",
                "effective_from": held["effective_from"] if held else None,
                "expires_on": held["expires_on"] if held else None,
            }
        )
    rows.append(
        {
            "check": "dispute",
            "outcome": "unavailable",
            "lifetime": None,
            "reason": "nothing in this repository stores a disputed AMOUNT (J08 step 7b(i), "
            "measured 2026-08-24) — no model, no db_table, no seam, no publisher. BR-CUS-096 "
            "conditions on an open dispute over an amount, so this check is served as ABSENT "
            "rather than as `pass`: a green clearance derived from a table that does not exist "
            "would authorise a cut. `metering.disputed_at` is a QUANTITY in dispute and is not "
            "this dispute.",
            "effective_from": None,
            "expires_on": None,
        }
    )
    return {
        "account_id": str(account_id),
        "as_of": as_of,
        "checks": tuple(rows),
        "all_clear": not by_kind,
        "protections_in_force": tuple(by_kind),
    }


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.6 — THE LADDER, AND THE THING THAT STOPS IT
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class LadderState:
    """Whether the ladder runs for this account today, and why not if not.

    COMPUTED on every call and never read from a stored flag. The mirror of
    `apps/payments/dunning.py`'s own sentence — *"a pause cached on a row is a
    pause that outlives its reason"* — is what matters here: a RUN cached on a
    row outlives the debt, and that is the customer who paid on Friday and got a
    certified letter on Monday.
    """

    account_id: str
    runs: bool
    halt_code: str | None
    detail: str
    tier: str | None
    next_tier: str | None
    balance: Decimal | None
    sequence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "runs": self.runs,
            "halt_code": self.halt_code,
            "detail": self.detail,
            "tier": self.tier,
            "next_tier": self.next_tier,
            "balance": None if self.balance is None else _money(self.balance),
            "sequence": self.sequence,
            "scheduler": dict(NO_SCHEDULER),
        }


def tier_for_rung(rung: str | None) -> str | None:
    """payments' rung → B18's chip, and `TIER_UNMAPPED` for the one with none.

    `second_5_day` has no chip in B18 §5.8.2. Mapping it onto TIER 2 shows a
    customer at the 5-day notice as though they were at the 10-day one; onto
    TIER 3, as though a certified letter had gone out. Both are statements to a
    regulator about what a customer was told, so neither is made.
    """
    if rung is None:
        return None
    return TIER_FOR_RUNG.get(rung, TIER_UNMAPPED)


def ladder_tier_of(case: DisconnectCase) -> str | None:
    """THE one place that answers "which tier is this case on".

    It exists so that folding `disconnect_cases.tier` into payments'
    `account_collection_state` — if that is how the overlap in the module
    docstring is ruled — is a change to this function and not to five call
    sites.
    """
    return case.tier


#: The states a case can be DERIVED out of and into `on_hold` — the ones in
#: which a ladder is still running. A `cut`, `reconnecting`, `restored`,
#: `stopped` or `closed_out` case is NOT held by a protection arriving
#: afterwards: the supply is already off or the case is finished, and saying
#: *On hold* over either would be a worse sentence than the one it replaced.
HOLDABLE_CASE_STATES: tuple[str, ...] = (STATE_NOTICE_SENT, STATE_SCHEDULED)


def displayed_state(case: DisconnectCase, *, as_of: date) -> str:
    """The ONE answer to *what state is this case in*, for anything a clerk reads.

    ⛔ **`DEF-CUS-6755` — A CASE READ `At notice` AND `On hold` AT ONCE.**
    Blueprint p144's `WHAT HOLDING WILL DO` promises *"the case moves to the **On
    hold** segment, so it is never worked by accident"*. Holding writes an
    `AccountProtection` row and touched `disconnect_cases` not at all, so the
    record went on saying `notice_sent` beside a live protection, and
    `disconnect_reads._seg_on_hold` — which reads `state == on_hold` — answered
    **0 for ever** on a segment and a filter chip that are both drawn.

    ⚠ **THE FIX IS A DERIVATION AND NOT A COLUMN, BECAUSE THAT IS THE DESIGN
    THIS REPOSITORY ALREADY CHOSE AND WROTE DOWN TWICE.** `_ladder_restarts`
    rejects *"a stored `on_hold` state"* by name — *"`on_hold` is DERIVED in
    this module and deliberately never written"* — and `disconnect_reads.py` §1
    opens with *"`On hold` cannot be a stored state"*. The reason is the reason
    nothing stores *"the ladder is running"* either: **a hold cached on a row
    outlives the thing that caused it.** A payment plan's protection has no
    expiry at all (`BR-CUS-043` — a missed instalment lifts it the next day with
    no grace), so a written `on_hold` would have to be un-written by a nightly
    job that does not exist, and a case would sit held after the plan lapsed.
    **Computed, it is right every time it is asked and wrong at no time in
    between.**

    ⚠ **IT IS A DISPLAY ANSWER AND IT IS NOT A GATE.** `commit_cut`,
    `schedule_cut` and `advance` go on reading `case.state` and
    `halt_reason` — the protection refusal is `_require_running`'s and is
    unchanged. Deriving a state for a screen must not quietly become a fourth
    way to refuse an act, and `HOLDABLE_CASE_STATES` keeps it away from every
    state in which something has already happened.

    ⚠ **THE DRAWN WORD IS *SEGMENT*.** The promise p144 makes is about where the
    case appears in the register, which is exactly what this answers.
    """
    if case.state not in HOLDABLE_CASE_STATES:
        return case.state
    # ⚠ **`protections_for`, NOT `medical_hold_for` AND NOT ONE KIND.** All
    # THREE protections hold the ladder — `halt_reason`'s `HALT_PROTECTED` is
    # computed the same way — and a derivation that saw only a certificate would
    # leave a weather moratorium and a payment plan reading `At notice`, which
    # is `DEF-CUS-6755` fixed for one kind in three.
    if any(row["in_force"] for row in protections_for(case.account_id, as_of=as_of)):
        return STATE_ON_HOLD
    return case.state


def halt_reason(
    account_id: Any,
    *,
    as_of: date,
    case: DisconnectCase | None = None,
    paid_recently: Decimal = ZERO,
    for_cut: bool = False,
) -> dict[str, Any] | None:
    """Why the ladder does NOT run, or None when it does.

    `for_cut` asks the SAME question about a different step, and only ONE test
    differs: reaching TIER 3 stops another NOTICE (there is no fourth chip) and
    is the PRECONDITION of a cut. Every other stopper — the floor, a
    protection, a plan, a part payment, an unreadable reading — applies to both
    identically, which is why this is one function with a flag rather than two
    functions that would drift apart the first time a rule is amended.

    The order of the tests is the order of the rulings' own priority and it is
    `apps/payments/ladder.decide`'s order, deliberately: the FLOOR comes before
    the plan and the hold because a $2.40 debt must not be evaluated against
    anything, and the plan pause comes before the partial-payment test because a
    customer on a current plan is not partially paying — they are paying exactly
    what they agreed.

    ⚠ **EVERY UNREADABLE INPUT HALTS THE LADDER.** Hard-won law 3: the unsafe
    option must be the one you type, and here the unsafe option is chasing.
    """
    if case is not None and case.state in (STATE_STOPPED, STATE_RESTORED):
        return {
            "code": HALT_STOPPED_BY_HAND if case.stopped_reason else HALT_NOTHING_OWED,
            "br_ref": "BR-CUS-039",
            "detail": f"this case is {case.state!r} and has left the list. "
            + (f"It was stopped by hand: {case.stopped_reason}." if case.stopped_reason else ""),
        }

    balance = _balance_for(account_id)
    if balance is None:
        return {
            "code": HALT_BALANCE_UNREADABLE,
            "br_ref": "BR-PAY-032",
            "detail": "what this account owes could not be read from the ledger, so the ladder "
            "does not run. A balance that cannot be read is not a balance of zero and is not a "
            "licence to chase — the reading is reported and the customer is left alone.",
        }
    if balance <= ZERO:
        return {
            "code": HALT_NOTHING_OWED,
            "br_ref": "BR-PAY-021",
            "detail": "this account owes nothing, so there is nothing to chase and the row "
            "leaves the list AUTOMATICALLY (B18 §5.8.3). Nothing had to be cancelled by hand. "
            "Money POSTED by the due date settles a bill even if it clears later (BR-PAY-021). "
            "⚠ The LADDER stops; SERVICE does not restore itself — BR-PAY-036 keeps restoration "
            "an explicit, audited staff action, so a CUT account that pays moves to "
            "`reconnecting` and waits for a visit.",
        }

    settings = _collections_settings()
    floor = _decimal_setting(settings, FLOOR_KEY)
    if floor is None:
        return {
            "code": HALT_FLOOR_UNREADABLE,
            "br_ref": "BR-BIL-001",
            "detail": "this utility's collection floor could not be read from the S70 "
            "collections settings, and it is not defaulted here. The PO ruled the $25.00 floor "
            "onto the WHOLE ladder (2026-08-12, OQ-137) and made it PER-UTILITY the same day "
            "(OQ-157) — *'$38 vs $180 average-bill utilities'* was their own reasoning for why "
            "one number cannot fit both. A copy of the default here would be free to drift from "
            "the number on the tenant's own screen.",
        }
    if balance < floor:
        return {
            "code": HALT_BELOW_FLOOR,
            "br_ref": "BR-BIL-001",
            "detail": f"the balance of {balance} is under this utility's collection floor of "
            f"{floor}, so NO rung runs — not the reminder, not the notices, and above all not "
            "the certified final letter, which costs about $8.00 to send. The floor is STRICT: "
            "a balance of exactly the floor IS chased.",
        }

    check = protection_check(account_id, as_of=as_of)
    if not check["all_clear"]:
        held = [row for row in check["checks"] if row["outcome"] == "fail"]
        named = ", ".join(str(row["check"]) for row in held)
        return {
            "code": HALT_PROTECTED,
            "br_ref": "BR-CUS-039",
            "detail": f"the ladder is FROZEN by a protection in force: {named}. "
            + " ".join(f"{row['check']}: {row['reason']}." for row in held),
            "protections": tuple(held),
        }

    pause = _plan_pause(account_id, as_of=as_of)
    if pause is not None and getattr(pause, "paused", False):
        return {
            "code": HALT_PLAN_PAUSE,
            "br_ref": "BR-CUS-043",
            "detail": str(getattr(pause, "detail", "")),
            "plan_id": getattr(pause, "plan_id", None),
            "covers": getattr(pause, "covers", None),
            "not_covered": getattr(pause, "not_covered", None),
        }

    if paid_recently > ZERO:
        percent = _decimal_setting(settings, PAUSE_PERCENT_KEY)
        if percent is None:
            return {
                "code": HALT_PAUSE_PERCENT_UNSET,
                "br_ref": "BR-PAY-016",
                "detail": f"this account paid {paid_recently} against {balance} outstanding, and "
                "whether that pauses the ladder depends on a percentage the PO ruled on "
                "2026-08-12 to be a TENANT SETTING (OQ-136). None is stored. The PO named 25% "
                "and 50% as EXAMPLES, not as the value, so choosing one here would answer a "
                "question they deliberately handed to each utility — and the ladder does not run "
                "on a guess.",
            }
        before = balance + paid_recently
        share = (paid_recently / before) * HUNDRED if before > ZERO else ZERO
        if share >= percent:
            return {
                "code": HALT_PARTIAL_PAYMENT,
                "br_ref": "BR-PAY-016",
                "detail": f"a partial payment of {paid_recently} against {before} outstanding is "
                f"{share:.6f}%, at or above this utility's pause threshold of {percent}% "
                "(PO 2026-08-12, OQ-136), so the ladder pauses. Nothing had to be cancelled by "
                "hand.",
            }

    if case is not None and case.tier == TIER_3 and not for_cut:
        return {
            "code": HALT_LADDER_COMPLETE,
            "br_ref": "BR-CUS-039",
            "detail": "this case is at TIER 3 · 48-HOUR, the last tier B18 §5.8.2 draws. What "
            "follows is a SCHEDULED CUT, which is a different act with its own guard "
            "(`schedule_cut`), not a fourth notice.",
        }
    return None


def ladder_state(account_id: Any, *, as_of: date, paid_recently: Decimal = ZERO) -> LadderState:
    """The live answer for one account — recomputed, never stored.

    ⚠ Carries `NO_SCHEDULER` on every result: `next_step_due` is a stored date
    that nothing watches, and a caller must not read a computed due date as a
    promise that a tier will arrive (DEF-320).
    """
    case = open_case_for(account_id)
    halt = halt_reason(account_id, as_of=as_of, case=case, paid_recently=paid_recently)
    tier = ladder_tier_of(case) if case else None
    # ⛔ BR-CUS-098 / DEF-705 — `next_tier` MUST AGREE WITH WHAT `advance` WILL
    # DO, and a state that promised TIER 3 while `advance` sent TIER 1 would be
    # DEF-127's shape on the dunning screen: two surfaces, one account, two
    # answers. The restart is computed HERE as well, from the same function, so
    # the two cannot drift.
    restarting = (
        case is not None
        and halt is None
        and _ladder_restarts(account_id, case=case, as_of=as_of) is not None
    )
    return LadderState(
        account_id=str(account_id),
        runs=halt is None,
        halt_code=None if halt is None else str(halt["code"]),
        detail="the ladder runs" if halt is None else str(halt["detail"]),
        tier=tier,
        next_tier=(
            TIER_1 if restarting else (NEXT_TIER.get(tier) if tier in NEXT_TIER else TIER_1)
        ),
        balance=_balance_for(account_id),
        sequence=case.sequence if case else SEQ_SERVICE,
    )


def open_case_for(account_id: Any) -> DisconnectCase | None:
    """The one open case, or None. `uq_one_open_disconnect_case_per_account`
    makes "the one" a fact rather than a convention."""
    return (
        DisconnectCase.objects.filter(tenant_id=_tenant_id(), account_id=account_id)
        .exclude(state__in=CLOSED_CASE_STATES)
        .first()
    )


def _require_running(
    account_id: Any, *, as_of: date, case: DisconnectCase | None, for_cut: bool = False
) -> None:
    """THE ONE GATE. Every advancing path goes through it and there is no second door.

    A lane adding a third way to advance the ladder adds it through this call,
    or the safety property the module docstring claims is not held. `for_cut`
    is passed straight through to `halt_reason` — a cut asks the same question
    as a notice, minus "is the ladder already at the top", which is the reason
    a cut is being scheduled at all.
    """
    halt = halt_reason(account_id, as_of=as_of, case=case, for_cut=for_cut)
    if halt is not None:
        raise DisconnectRuleError(
            f"the ladder is not running for this account: {halt['detail']}",
            code=str(halt["code"]),
            br_ref=str(halt["br_ref"]),
        )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def open_case(
    actor: Any,
    account_id: Any,
    *,
    as_of: date,
    sequence: str = SEQ_SERVICE,
) -> dict[str, Any]:
    """Start a case at TIER 1, or return the one that is already open.

    Idempotent on the open case rather than on a key, because
    `uq_one_open_disconnect_case_per_account` already makes a second one
    impossible and a second CALL is an ordinary double-click.
    """
    existing = open_case_for(account_id)
    if existing is not None:
        return case_payload(existing)

    if sequence not in SEQUENCES:
        raise DisconnectRuleError(
            f"{sequence!r} is not a sequence. BR-CUS-082 names two and only two: a SERVICE "
            "sequence that can end in a cut, and a COLLECTIONS sequence that cannot.",
            code="sequence_unknown",
            br_ref="BR-CUS-082",
        )
    _require_running(account_id, as_of=as_of, case=None)

    balance = _balance_for(account_id)
    currency = seams.tenant_currency() or ""
    if not currency:
        raise DisconnectRuleError(
            "the tenant's currency could not be read, and `disconnect_cases.currency` is CHAR(3) "
            "derived from the tenant (BR-TEN-021), never an input. A case recording an amount "
            "with no currency is a figure nobody can act on.",
            code="currency_not_readable",
            br_ref="BR-TEN-021",
        )
    # CR-039 wave D task 16. The allocation and the INSERT share one
    # transaction (BR-TEN-035) — the `atomic()` is new and exists for exactly
    # that: without it the two are separate autocommits, and a failed insert
    # would burn a number that no case ever carried.
    with transaction.atomic():
        case = DisconnectCase.objects.create(
            tenant_id=_tenant_id(),
            case_no=_allocate_case_no(),
            account_id=account_id,
            sequence=sequence,
            state=STATE_NOTICE_SENT,
            tier=None,
            amount_owed_at_open=balance if balance is not None else ZERO,
            currency=currency,
            opened_on=as_of,
        )
    payload = case_payload(case)
    _audit(actor, AUDIT_CASE_OPENED, account_id, after=payload)
    return payload


#: BR-CUS-098 / DEF-705 — the key `record_notice` stamps into a notice's own
#: `detail` when that notice IS the restart. `disconnect_notices` is APPEND-ONLY
#: and already carries a JSON `detail`, so the fact has a home without a schema
#: change, and it lives on the row it is a fact ABOUT.
RESTART_MARKER = "restarted_after"


def _lapsed_protection(account_id: Any, *, as_of: date) -> dict[str, Any] | None:
    """Which protection HELD this ladder and no longer does — or `None`.

    Two sources, because this module holds protections in two shapes and
    `_halt_reason` reads both:

      1. **A stored `AccountProtection`** — a medical certificate or a weather
         moratorium — present on the account and not in force today.
      2. **THE PAYMENT PLAN, which has NO stored protection row at all.** Its
         hold is computed by `_plan_pause` straight from payments
         (`_plan_protection_is_live`: *"LIFETIME_DERIVED — asked of payments,
         never of a stored date"*), so a query over `AccountProtection` cannot
         see it — and a household coming off a payment plan is DEF-705's own
         headline case. A plan that exists and is not pausing is a lapse.
    """
    for row in protections_for(account_id, as_of=as_of):
        if not row["in_force"]:
            return row
    plans = seams.payment_plans_for(account_id, as_of=as_of)
    if plans:
        pause = _plan_pause(account_id, as_of=as_of)
        if pause is None or not getattr(pause, "paused", False):
            return {
                "kind": PROTECTION_PLAN,
                "in_force": False,
                "lifted_on": None,
                "expires_on": None,
                "reason": "a payment plan on this account is no longer holding the ladder",
            }
    return None


def _ladder_restarts(
    account_id: Any, *, case: DisconnectCase, as_of: date
) -> dict[str, Any] | None:
    """BR-CUS-098 — does the NEXT notice go back to TIER 1?

    ⛔ **DEF-705 — BR-CUS-098 WAS CONFIRMED AND NOT BUILT, AND THE ONLY TEST ON
    THE PATH ASSERTED THE SUPERSEDED DESIGN AND WAS GREEN ON IT.** B18 §5.8.5
    said the ladder *"resumes where it was"*; the PO reversed that on 2026-08-25
    closing DEF-689 — **"Back to tier 1"** — and `TC-DSC-3` still asserted tier
    2, so the check that existed was PINNING the reversed design in place, which
    is worse than no check. Until this function existed, a household coming off
    a payment plan was served the **48-HOUR CERTIFIED NOTICE AS ITS FIRST
    CONTACT** — the outcome the ruling itself calls *"what a regulator asks
    about"*.

    ⚠ **THE RULE IS SIGNED; THE DETECTION IS NOT, AND THIS IS THE DERIVATION —
    WRITTEN HERE BECAUSE IT IS A JUDGEMENT AND NOT A READING.** BR-CUS-098 says
    WHAT happens when a protection lapses and nothing about how a RESUMING
    ladder is recognised. Three candidate signals were considered and two are
    wrong in ways worth recording, because the next lane will reach for them:

      * **A stored `on_hold` state.** Not available and must not be made
        available: `on_hold` is DERIVED in this module and deliberately never
        written (`disconnect_reads.py` §1, *"`On hold` cannot be a stored
        state"*).
      * **A date window over lapses since the last notice.** This is the one
        that looks right and is not. The PAYMENT PLAN — DEF-705's own case —
        **has no end date anywhere**: its hold is asked of payments as of a
        date and never stored, so there is no lapse date to put in a window.
        A window silently covers medical certificates and misses exactly the
        case the defect was filed about.

    **So the signal is the LAPSE ITSELF, and the one-shot is stamped on the
    notice.** A restart writes its TIER 1 notice carrying `restarted_after` in
    the append-only `detail` it already has; this function refuses to restart
    again while the newest notice is that stamp. **That is what stops an
    infinite tier-1 loop** — without it a lapsed plan, which never expires,
    would re-trigger the restart on every advance and the ladder could never
    leave tier 1, which is a worse defect than the one this fixes.

    ⚠ **ONE CASE IS KNOWINGLY NOT COVERED AND IS STATED RATHER THAN HIDDEN:** a
    SECOND protection filed and lapsed with no notice sent in between is
    suppressed by the standing marker. Closing that needs the lapse to be
    identifiable — a stored lapse date on the protection, or a payments-side
    history read — and both are schema/seam decisions this rule does not make.

    ⚠ **AND WHAT BR-CUS-098 DOES NOT DECIDE IS NOT DECIDED HERE:** whether a
    second protection filed during a restarted ladder holds it again from
    wherever it has reached, and whether a household that has had six notices
    for one debt is owed anything different from one that has had three.
    Neither was put to the PO; neither is inferred.
    """
    if case.tier is None:
        # Nothing has been sent, so nothing was interrupted. `advance` opens at
        # TIER 1 on its own path and this must not claim a restart.
        return None
    latest = (
        DisconnectNotice.objects.filter(tenant_id=_tenant_id(), case=case)
        .order_by("-issued_on", "-created_at")
        .first()
    )
    if latest is not None and (latest.detail or {}).get(RESTART_MARKER):
        # The newest thing this customer received IS the restart. Advancing now
        # is the restarted ladder climbing, not a second interruption.
        return None
    return _lapsed_protection(account_id, as_of=as_of)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def advance(actor: Any, account_id: Any, *, as_of: date) -> dict[str, Any]:
    """Move this case up one tier and record the notice that goes with it.

    **It refuses whenever the ladder is not running**, and it does so through
    `_require_running` — the same gate `record_notice` uses. That is the whole
    of *"it stops itself"*: there is no stored "running" flag to go stale and
    nothing to cancel.

    ⚠ **NOTHING CALLS THIS ON A DATE.** See `NO_SCHEDULER` / DEF-320.
    """
    case = open_case_for(account_id)
    if case is None:
        # Opening a case is not itself a step: an account with no case that is
        # due a notice gets the case AND its TIER 1 notice from one call, so a
        # caller is never handed a case sitting at tier `None` that looks
        # advanced and is not.
        open_case(actor, account_id, as_of=as_of)
        case = open_case_for(account_id)
    _require_running(account_id, as_of=as_of, case=case)

    tier = case.tier
    # ⛔ BR-CUS-098 / DEF-705 — A LADDER THAT WAS HELD RESTARTS AT TIER 1.
    # PO 2026-08-25, closing DEF-689: **"Back to tier 1"**, over the build's own
    # recommendation, and the ruling records why: *"going straight to a 48-hour
    # cut notice on a household just out of a medical hardship is what a
    # regulator asks about"*. Without this, a customer held at TIER 2 by a
    # payment plan received `TIER 3 · 48-HOUR` — a certified letter, two days
    # from a cut — as their FIRST contact after the plan ended.
    # It also makes the product consistent with itself: `BR-CUS-082` already
    # restarts at TIER 1 after a closure, so both interruptions now resume the
    # same way rather than differing by accident.
    interrupted = _ladder_restarts(account_id, case=case, as_of=as_of)
    next_tier = (
        TIER_1 if interrupted is not None else (TIER_1 if tier is None else NEXT_TIER.get(tier))
    )
    if next_tier is None:
        raise DisconnectRuleError(
            "this case is already at the last tier B18 §5.8.2 draws. What follows is a scheduled "
            "cut, not a fourth notice.",
            code=HALT_LADDER_COMPLETE,
            br_ref="BR-CUS-039",
        )
    case.tier = next_tier
    case.tier_reached_on = as_of
    case.state = STATE_NOTICE_SENT
    case.save(update_fields=["tier", "tier_reached_on", "state", "updated_at"])
    notice = record_notice(
        actor,
        account_id,
        tier=next_tier,
        on_date=as_of,
        _case=case,
        # BR-CUS-098 — the restart is stamped on the notice it produced, which
        # is both the audit answer to "why did they get a reminder at tier 2?"
        # and the one-shot that stops the ladder looping at TIER 1.
        _restarted_after=None if interrupted is None else str(interrupted["kind"]),
    )
    payload = case_payload(case)
    payload["notice"] = notice
    if interrupted is not None:
        # The RESTART is a fact about this notice and a clerk asked "why did
        # they get a reminder when they were at tier 2?" needs it answerable
        # from the record, not from this comment.
        payload["restarted_at_tier_1"] = {
            "br_ref": "BR-CUS-098 (PO 2026-08-25, closing DEF-689)",
            "from_tier": tier,
            "protection": interrupted["kind"],
            "protection_ended_on": str(interrupted["lifted_on"] or interrupted["expires_on"]),
        }
    return payload


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def record_notice(
    actor: Any,
    account_id: Any,
    *,
    tier: str,
    on_date: date,
    _case: DisconnectCase | None = None,
    _restarted_after: str | None = None,
) -> dict[str, Any]:
    """Append one notice — and REFUSE to record one the ladder may not send.

    BR-CUS-039 excludes a medical-hold account from every send, and the skip is
    recorded rather than silent (J4 step 2). Here the refusal carries the reason
    to the caller instead, because `notice_history` — payments' append-only skip
    record — already exists and writing a second skip trail is the duplication
    the module docstring reports.

    ⚠ **`delivery_state` IS WRITTEN NULL.** Task 7.10: never a fabricated
    `emailed`.
    """
    case = _case or open_case_for(account_id)
    if case is None:
        raise DisconnectRuleError(
            "there is no open disconnect case on this account, so there is nothing to append a "
            "notice to.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    if tier not in LADDER_TIERS:
        raise DisconnectRuleError(
            f"{tier!r} is not one of B18 §5.8.2's three chips. If this is payments' "
            f"{PAYMENTS_RUNG_5_DAY!r} rung, it has NO chip and a ruling is owed — mapping it "
            "onto either neighbour misstates to a regulator what the customer was told.",
            code="tier_unknown",
            br_ref="BR-PAY-017",
        )
    if _case is None:
        _require_running(account_id, as_of=on_date, case=case)

    row = DisconnectNotice.objects.create(
        tenant_id=_tenant_id(),
        case=case,
        tier=tier,
        delivery_state=None,
        delivery_unavailable_reason=DELIVERY_UNAVAILABLE["code"],
        issued_on=on_date,
        # The service-layer actor is the B12 §6a shape (an object carrying `id`
        # and `role`), not a `User` row — the same derivation `core.audit`
        # makes for `actor_user_id`, so the trail and this column always name
        # the same person.
        actor_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        detail=(
            {"sequence": case.sequence}
            if _restarted_after is None
            # BR-CUS-098 / DEF-705 — `disconnect_notices` is append-only and
            # already carries a JSON `detail`, so the restart is recorded on
            # the row it is a fact ABOUT and needs no schema change.
            else {"sequence": case.sequence, RESTART_MARKER: _restarted_after}
        ),
    )
    payload = {
        "notice_id": str(row.pk),
        "case_id": str(case.pk),
        "account_id": str(account_id),
        "tier": tier,
        "issued_on": str(on_date),
        "delivery": dict(DELIVERY_UNAVAILABLE),
    }
    _audit(actor, AUDIT_NOTICE, account_id, after=payload)
    return payload


# ════════════════════════════════════════════════════════════════════════════
# BR-CUS-100 — RECORDING THE PROOF, AND THE QUEUE OF NOTICES WITHOUT ONE
# ════════════════════════════════════════════════════════════════════════════
def latest_notice_at_tier(case: DisconnectCase, tier: str) -> DisconnectNotice | None:
    """The most recent notice this case raised at `tier`, or None.

    LATEST, not first: the ladder can re-raise a tier (a bad address, a
    corrected letter) and the record that governs a cut is the one that was
    actually served last. Ordered by `issued_on` then `created_at` so two
    notices raised on the same business date still have a defined order.
    """
    return (
        DisconnectNotice.objects.filter(tenant_id=_tenant_id(), case=case, tier=tier)
        .order_by("-issued_on", "-created_at")
        .first()
    )


def proof_payload(row: DisconnectNotice) -> dict[str, Any]:
    """One notice's proof-of-service record, as a screen and an audit row need it.

    `recorded` is the single boolean a caller should branch on. It reads
    `proof_recorded_at`, not the channel, because `proof_recorded_at` is the
    column that says **a person did this** — which is what BR-CUS-100 means by
    *"a record a person enters"*.
    """
    return {
        "notice_id": str(row.pk),
        # `DEF-CUS-5169` — the queue served a notice with no account on it, so a
        # screen holding one household could not tell which letters were its
        # own. It is the case's account and never a second source.
        "account_id": str(row.case.account_id) if row.case_id else None,
        "tier": row.tier,
        "issued_on": str(row.issued_on),
        "recorded": row.proof_recorded_at is not None,
        "channel": row.service_channel,
        "reference": row.proof_reference,
        "served_on": str(row.served_on) if row.served_on else None,
        "signed_for_on": str(row.signed_for_on) if row.signed_for_on else None,
        "recorded_by": str(row.proof_recorded_by_id) if row.proof_recorded_by_id else None,
        "recorded_at": row.proof_recorded_at.isoformat() if row.proof_recorded_at else None,
        "br_ref": "BR-CUS-100",
    }


def service_proof_for(case: DisconnectCase, *, tier: str = TIER_3) -> dict[str, Any]:
    """Whether this case's `tier` notice has a recorded service — the ONE read.

    `assert_service_proved` and any screen that wants to say *"waiting for proof
    of service"* both come through here, so the answer a clerk is shown and the
    answer that governs a cut cannot drift apart.

    A case with NO notice at that tier answers `recorded: False` with a
    different `absence` code, because *"nothing was ever raised"* and *"it was
    raised and nobody has said how it went out"* are different facts about a
    household and a regulator asks about both.
    """
    row = latest_notice_at_tier(case, tier)
    if row is None:
        return {
            "tier": tier,
            "recorded": False,
            "absence": "no_notice_at_this_tier",
            "br_ref": "BR-CUS-100",
        }
    payload = proof_payload(row)
    if not payload["recorded"]:
        payload["absence"] = "awaiting_proof_of_service"
    return payload


def notices_awaiting_proof(*, tier: str | None = None) -> tuple[dict[str, Any], ...]:
    """THE QUEUE — every notice raised and not yet recorded as served.

    `BR-MET-110`'s shape, and `apps/metering/connections.py` states the reason in
    its own words for `work_orders.accepted_by`: *"Nullable because an order can
    be completed and not yet reviewed — that gap IS the review queue, and a NULL
    here is the only thing that says an order is waiting for a person."*

    ⚠ **THE *not wired* NOTE THAT STOOD HERE IS SPENT — `DEF-CUS-5169`, 2026-09-13.**
    It read *"No screen calls this yet"* and was true for as long as it took a
    lane to notice: step 3 of `DSC-02` told a clerk **"No final notice is
    recorded as served. Record it first."** and gave them nothing to record it
    with, so **no cut could be scheduled from that screen on any account in the
    tree**. The wizard reads `notices_for_account` below and posts to
    `record_proof_of_service`, and the queue this function serves is still the
    tenant-wide worklist it always was — it is simply no longer the only reader
    of these rows. Hard-won law 1: a docstring naming a gap is a note, not a
    plan, and it outlives the gap unless somebody deletes it.
    """
    rows = DisconnectNotice.objects.filter(tenant_id=_tenant_id(), proof_recorded_at__isnull=True)
    if tier is not None:
        rows = rows.filter(tier=tier)
    return tuple(proof_payload(row) for row in rows.order_by("issued_on", "created_at"))


def notices_for_account(account_id: Any) -> tuple[dict[str, Any], ...]:
    """Every disconnect notice raised on ONE account — `DSC-02.3`'s own table.

    `DEF-CUS-5169`. The blueprint draws step 3 opening on **What has gone out
    already**, a row per notice with the date it was sent, and then a **Proof
    that it was served** block that attests to one of them. Neither could be
    built: `notices_awaiting_proof` is TENANT-WIDE and its payload names no
    account, so a screen could not tell which letters belonged to the household
    in front of it, and the proof door is keyed by notice id — which nothing on
    any screen showed a clerk.

    NEWEST FIRST, and PROVED ROWS INCLUDED. The queue above excludes anything
    already attested to because it is a worklist; this is a RECORD, and a clerk
    reading step 3 has to be able to see that the final notice was proved on
    Monday as much as that the 10-day one was not. `service_proof_for` still
    owns the one answer that governs a cut — this changes no decision and adds
    no rule, it only lets the screen show what the table already holds.

    ⚠ **`account_id` RIDES ON EACH ROW.** `proof_payload` is shared with the
    queue, and a queue row with no account is a row a clerk cannot act on
    either; adding it here rather than in a second payload keeps one shape for
    one fact.
    """
    rows = (
        DisconnectNotice.objects.filter(tenant_id=_tenant_id(), case__account_id=account_id)
        .select_related("case")
        .order_by("-issued_on", "-created_at")
    )
    return tuple(proof_payload(row) for row in rows)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-100")
def record_proof_of_service(
    actor: Any,
    notice_id: Any,
    *,
    channel: str,
    reference: str,
    served_on: date,
    signed_for_on: date | None = None,
) -> dict[str, Any]:
    """A PERSON attests how a notice was served. This is not a send.

    BR-CUS-100 (PO 2026-08-25, closing DEF-692), verbatim: *"So the two halves
    are separated and neither pretends to be the other: the SEND is in-app (and
    later email/SMS/print), and the PROOF is a **record a person enters** — the
    channel used, the reference, and the date it was signed for. That is what a
    regulator asks to see, and recording it is honest where claiming to have
    sent it is not."*

    ⛔ **NOTHING HERE TOUCHES `delivery_state`.** BR-CUS-100: *"proof of service
    is a **legal artefact produced outside this product**: a posted item, a
    tracking number, a signature that came back. No adapter can manufacture
    one."* So this call records what a human says happened elsewhere; it does
    not make this product's own delivery claim any truer, and `delivery_state`
    stays NULL with `DELIVERY_UNAVAILABLE` beside it exactly as before.

    ⛔ **AND IT IS WRITTEN ONCE.** Hard rule 4 — *"no UPDATE/DELETE on issued
    invoices, invoice lines, payments, journal entries — corrections are new
    rows"* — is about money, and this is the same shape for the same reason:
    the record a utility shows a regulator when a customer says they were never
    told cannot be re-pointed afterwards. The first write fills columns that
    were NULL because the notice was waiting for it; a second is refused by
    name. **A correction today is a NEW notice with its own proof**, and
    whether BR-CUS-100 wants a dedicated correction row instead is REPORTED as
    owed rather than chosen here.
    """
    row = (
        DisconnectNotice.objects.filter(tenant_id=_tenant_id(), pk=notice_id)
        .select_related("case")
        .first()
    )
    if row is None:
        # BR-TEN-003 — a cross-tenant id is a 404, never a 403. The refusal must
        # not tell a caller that somebody else's notice exists.
        raise DisconnectRuleError(
            "there is no such disconnect notice on this tenant.",
            code="notice_not_found",
            br_ref="BR-TEN-003",
        )
    if row.proof_recorded_at is not None:
        raise DisconnectRuleError(
            "this notice already carries a proof of service, recorded by a person on "
            f"{row.proof_recorded_at.date()} ({row.service_channel}, {row.proof_reference}). It is "
            "not re-pointed: the record a utility shows a regulator when a customer says they "
            "were never told cannot be edited afterwards (hard rule 4's discipline). A correction "
            "is a NEW notice, served and recorded in its own right.",
            code="proof_already_recorded",
            br_ref="BR-CUS-100",
        )
    if channel == SERVE_IN_APP_IS_A_SEND:
        raise DisconnectRuleError(
            "the in-app bell is how this notice was SENT, not proof that it was SERVED. "
            "BR-CUS-100: *'IN-APP DOES NOT SATISFY CERTIFIED MAIL … proof of service is a legal "
            "artefact produced outside this product: a posted item, a tracking number, a "
            "signature that came back. No adapter can manufacture one.'* Record the posted item "
            "and its article number instead.",
            code="in_app_is_a_send_not_a_proof",
            br_ref="BR-CUS-100",
        )
    if channel not in SERVICE_CHANNELS:
        raise DisconnectRuleError(
            f"{channel!r} is not one of the ways `DSC-02.3` draws a notice being served "
            f"({', '.join(SERVICE_CHANNELS)}). A sixth channel is a claim about how a household "
            "was told, and it needs a ruling rather than a string.",
            code="service_channel_unknown",
            br_ref="BR-CUS-100",
        )
    cleaned_reference = str(reference or "").strip()
    if not cleaned_reference:
        raise DisconnectRuleError(
            "a proof of service needs its reference — the tracking or article number of the "
            "posted item. BR-CUS-100 names it as one of the three things the record IS: *'the "
            "channel used, the reference, and the date it was signed for'*, and a reference is "
            "what a regulator asks to see.",
            code="proof_needs_a_reference",
            br_ref="BR-CUS-100",
        )
    if signed_for_on is not None and signed_for_on < served_on:
        raise DisconnectRuleError(
            f"a signature cannot come back on {signed_for_on} for an item served on {served_on}. "
            "One of the two dates is a typing error, and the statutory period is computed from "
            "the served date — `DSC-02.3`: *'Computed as Aug 22 plus 48 hours'*.",
            code="signed_for_before_served",
            br_ref="BR-CUS-100",
        )

    row.service_channel = channel
    row.proof_reference = cleaned_reference
    row.served_on = served_on
    row.signed_for_on = signed_for_on
    row.proof_recorded_by_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    row.proof_recorded_at = timezone.now()
    row.save(
        update_fields=[
            "service_channel",
            "proof_reference",
            "served_on",
            "signed_for_on",
            "proof_recorded_by",
            "proof_recorded_at",
        ]
    )
    payload = proof_payload(row)
    payload["case_id"] = str(row.case_id)
    payload["account_id"] = str(row.case.account_id)
    # ⚠ The SEND is untouched and the payload says so out loud, so a caller
    # cannot read a recorded proof as a delivery this product performed.
    payload["delivery"] = dict(DELIVERY_UNAVAILABLE)
    payload["delivery_state"] = row.delivery_state
    _audit(actor, AUDIT_PROOF_RECORDED, row.case.account_id, after=payload)
    return payload


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def stop_by_hand(
    actor: Any,
    account_id: Any,
    *,
    on_date: date,
    reason: str,
    note: str | None = None,
) -> dict[str, Any]:
    """§5.8.3's modal — *"for clerk error, a dispute, or a regulator instruction"*.

    **This is NOT how the ordinary stop happens.** Payment and a plan stop the
    ladder by themselves and leave no row here; a stop that must be called is a
    stop that can be missed. The reason set is CLOSED for the same reason
    `BR-BIL-013`'s path set is: a fourth way to stop chasing a real debt needs a
    ruling.

    ⚠ **`note` IS THE DRAWING'S `What happened` AND IT IS NOT THE REASON.**
    Blueprint p137 draws both: a radio of three reasons AND a free-text line
    under them. The reason is the closed vocabulary this function refuses
    outside of; the note is the sentence that makes the row readable a year
    later. `DisconnectCase.stopped_note` carries the whole decision to give it a
    column of its own, including the two options that were refused.

    ⚠ **OPTIONAL, ON PURPOSE.** A required note would refuse a stop, and on this
    ladder a refused stop means a disconnection continues because a clerk had
    nothing to type.
    """
    if reason not in STOP_REASONS:
        raise DisconnectRuleError(
            f"{reason!r} is not one of the three reasons B18 §5.8.3 names for stopping a ladder "
            f"by hand ({', '.join(STOP_REASONS)}). Payment and a payment plan stop it "
            "automatically and need no modal at all.",
            code="stop_reason_unknown",
            br_ref="BR-CUS-039",
        )
    case = open_case_for(account_id)
    if case is None:
        raise DisconnectRuleError(
            "there is no open disconnect case on this account to stop.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    # ONE TRANSACTION, for `schedule_cut`'s reason above: the case write and the
    # audit row are one act (hard rule 7), and two unwrapped writes leave a
    # ladder stopped with nobody named as having stopped it.
    with transaction.atomic():
        case.state = STATE_STOPPED
        case.stopped_on = on_date
        case.stopped_reason = reason
        # An empty or whitespace note is stored as NULL, never as `""`: *nobody
        # wrote a note* and *somebody wrote nothing* are the same fact, and two
        # spellings of one fact is how a screen ends up rendering a blank line
        # where it meant to render an absence.
        case.stopped_note = str(note).strip() if note and str(note).strip() else None
        case.save(
            update_fields=[
                "state",
                "stopped_on",
                "stopped_reason",
                "stopped_note",
                "updated_at",
            ]
        )
        payload = case_payload(case)
        _audit(actor, AUDIT_STOPPED, account_id, after=payload)
    return payload


def stop_for_move_out(actor: Any, account_id: Any, *, on_date: date) -> dict[str, Any] | None:
    """`DEF-CUS-10190` — the customer LEFT, so the open ladder short of the cut
    closes as `customer_left` (PO ruling 2026-10-17). Called from inside
    `services.move_out`'s transaction (via `move_in_units`), never by a clerk.

    The same write `stop_by_hand` makes, with the ruled fourth reason. The
    debt is untouched: the balance and any payment plan stay on the account
    that owes them. `None` when no pre-cut case is open."""
    case = open_case_for(account_id)
    if case is None or case.state in (STATE_CUT, STATE_RECONNECTING):
        return None
    case.state = STATE_STOPPED
    case.stopped_on = on_date
    case.stopped_reason = STOP_CUSTOMER_LEFT
    case.save(update_fields=["state", "stopped_on", "stopped_reason", "updated_at"])
    payload = case_payload(case)
    _audit(actor, AUDIT_STOPPED, account_id, after=payload)
    return payload


# ════════════════════════════════════════════════════════════════════════════
# THE GUARDS THAT STAND IN FRONT OF A CUT — AND, SINCE 7.8, THE CUT ITSELF
# ════════════════════════════════════════════════════════════════════════════
# ⚠ **THIS BANNER SAID "THE CUT IS NOT BUILT HERE" UNTIL 2026-08-25.** It was
# true of the lane that wrote it (tasks 7.5–7.7 + 7.16) and stopped being true
# when W7 task 7.8 landed `commit_cut` below. Amended rather than deleted: a
# reader who learned this file from that line would have gone looking for a cut
# in another module and found none.
def assert_cut_reachable(case: DisconnectCase) -> None:
    """BR-CUS-082 — *"a closed account cannot be escalated to disconnection"*.

    TWO INDEPENDENT GROUNDS, on purpose. The sequence is one; the account's own
    status is the other; and `ck_collections_sequence_never_cuts` in the
    database is a third. Deleting any one of them still leaves a cut on a closed
    account impossible, which is what "unreachable" has to mean for a guard that
    protects a person's water supply.

    ⚠ **AMENDED 2026-08-25 (task 7.8).** This paragraph read *"THE CUT ITSELF
    (task 7.8) IS NOT BUILT IN THIS LANE. Only the guard is."* `commit_cut` now
    exists below and calls this guard AGAIN at the moment of the cut, not only
    at the schedule — days pass between the two and an account can close in
    them.
    """
    if case.sequence == SEQ_COLLECTIONS:
        raise DisconnectRuleError(
            "this is a COLLECTIONS sequence and it cannot reach a cut. BR-CUS-082 (PO "
            "2026-08-24, closing OQ-346): *'a closed account cannot be escalated to "
            "disconnection — there is nothing left to disconnect — and the ladder for a closed "
            "account is a collections sequence, not a service one.'*",
            code="collections_sequence_cannot_cut",
            br_ref="BR-CUS-082",
        )
    account = _account(case.account_id)
    if _account_is_closed(account):
        raise DisconnectRuleError(
            "this account is closed. There is no live service to disconnect, so a cut is not a "
            "step that exists for it (BR-CUS-082). A debt that survived the close is still "
            "chased — as a collections sequence, through `restart_after_closure`.",
            code="account_closed_cannot_cut",
            br_ref="BR-CUS-082",
        )


#: `BR-CUS-1099` (PO 2026-09-25) — what the utility could not show, recorded on
#: the act that went ahead without it. **The record protects the UTILITY here**,
#: which is the one place in the five 2026-09-25 rulings where that is true: a
#: final-tier cut without proved certified service is a cut the utility may not
#: lawfully have made, so its absence is the utility's own exposure.
#:
#: ⚠ **IT IS A WARNING AND NOT A REFUSAL — THAT IS THE WHOLE RULING.** PO,
#: verbatim: *"So we warn user , but we dont stop user - We can't send a
#: certified notice — a final-tier cut isn't lawful without one"*.
#:
#: ⚠ **NONE OF THIS REASONING REACHES A SCREEN** (B14 rule 33: rationale is zero
#: words on screen). The screen states the fact; the `detail` below is what the
#: audit row and the register carry.
CUT_WITHOUT_PROVED_SERVICE: dict[str, Any] = {
    "code": "cut_on_unrecorded_service",
    "br_ref": "BR-CUS-1099",
    "detail": (
        "no proof of certified service is recorded on this case's tier-3 notice. BR-CUS-100 "
        "made that a refusal; BR-CUS-1099 (PO 2026-09-25) makes it a WARNING — *'So we warn "
        "user , but we dont stop user'*. The in-app notice is a SEND; proof of service is the "
        "posted item, its article number and the date, recorded by a person through "
        "`record_proof_of_service`. This product cannot SEND a certified notice at all, which "
        "is a separate and already-filed gap."
    ),
}


def service_proof_warnings(case: DisconnectCase) -> tuple[dict[str, Any], ...]:
    """`BR-CUS-1099` — what a clerk is TOLD before a cut, having not been stopped.

    ⚠ **THE PAIR OF `assert_service_proved`, AND THE SPLIT IS THE RULING.** That
    function keeps the refusals; this one carries the fact that no longer
    refuses. They are separate functions rather than one function with a flag
    because a caller must not be able to ask for the warnings and skip the
    refusal by passing `False` — the two remaining refusals are not ruled on.

    ⚠ **IT IS ALSO THE RECORD.** `schedule_cut` and `commit_cut` put whatever
    this returns on the payload they audit, so `audit_log` carries *what the
    utility could not show at the moment it acted, who acted and when* —
    CLAUDE.md hard rule 7, and the half of `BR-CUS-1099` that is not about
    blocking.
    """
    proof = service_proof_for(case, tier=TIER_3)
    if proof["recorded"]:
        return ()
    warning = dict(CUT_WITHOUT_PROVED_SERVICE)
    # The absence the proof read states in its own words, carried rather than
    # restated — one set of words (hard-won law 1's discipline for sentences).
    warning["absence"] = proof.get("absence")
    return (warning,)


def assert_service_proved(case: DisconnectCase) -> None:
    """⛔ BR-CUS-100 — *"a tier-3 cut must not be schedulable on an unrecorded service."*

    The rule's own sentence, verbatim and in full: *"Until those columns exist,
    `delivery_state` stays NULL with its reason (the W7 lane's behaviour) and
    **a tier-3 cut must not be schedulable on an unrecorded service**, because
    that is the one thing on this screen whose absence is not merely untidy."*
    The columns now exist, so this is the half of BR-CUS-100 that becomes a
    guard rather than a note.

    **WHY IT IS SEPARATE FROM `assert_cut_reachable`.** That guard answers *"is
    a cut a step that exists for this case at all"* (BR-CUS-082 — a closed
    account, a collections sequence). This one answers *"was this household
    lawfully told"*, and the two fail for completely different reasons. Folding
    them together would give a clerk one sentence for two situations, one of
    which is fixed by recording a letter that already went out.

    ⚠ **IT READS THE PROOF, NEVER `delivery_state`.** A cut authorised by this
    product's own claim to have delivered something would be authorised by a
    column that is NULL on every row and always will be until an adapter
    exists. What authorises it is a person's attestation with a reference on it.

    ⚠ **IT DOES NOT READ `signed_for_on`.** Whether a tier-3 cut requires the
    signature to have COME BACK — or only that certified mail was sent — is
    **not written in BR-CUS-100, `DSC-02.3`, BR-CUS-039 or any other signed
    document**. `DSC-02.3` draws *"NOTICE SERVED Aug 22 certified mail, signed
    for"* on a case where it had, which states the happy path and rules
    nothing. Choosing either reading here would decide, for real households,
    whether an unclaimed letter stops a disconnection. It is REPORTED as owed
    and left unread.

    ⛔ **THE ABSENT-PROOF REFUSAL WAS WITHDRAWN ON 2026-09-25 — `BR-CUS-1099`.**
    PO ruling that day, verbatim: *"So we warn user , but we dont stop user - We
    can't send a certified notice — a final-tier cut isn't lawful without one"*.
    Step 3's *"No proof, no cut"* is a **WARNING**: a clerk may schedule a cut
    with **no proof of certified service recorded**, and the screen still asks
    for it. It is the same principle as `BR-CUS-1096` and `BR-CUS-1097` — **the
    product tells the clerk what is true and does not stop them acting** — and
    not a local exception.

    ⚠ **THE SURVIVING REFUSAL — `tier_3_proof_not_certified` — IS NOT RULED ON.**
    The PO's words are about the ABSENCE of proof and say nothing about a notice
    recorded as served by another channel. **It was not removed with the first.**

    ✅ **WIRED 2026-09-25, LANE CUTPATH (`DEF-CUS-6736` CLOSED).** This paragraph
    read *"NOTHING HERE CHANGED … the disconnect rebuild is PAUSED"* until the
    coordinator put this lane on it. **The `cut_on_unrecorded_service` refusal is
    GONE from this function and lives on as a WARNING** —
    `service_proof_warnings` above — which `schedule_cut` and `commit_cut` put on
    the payload they audit, so `audit_log` carries **that no proof was recorded
    at the moment the cut was scheduled, who scheduled it and when**. That
    capture is part of the rule and not a nicety: here, unlike `BR-CUS-1096` and
    `BR-CUS-1097`, **the record protects the UTILITY**.

    ⚠ **ONE REFUSAL REMAINS AND IT IS THE ONE THE RULING DOES NOT REACH.** The
    PO's words are about the ABSENCE of proof. `tier_3_proof_not_certified` is
    about a notice recorded as served by ANOTHER channel, and removing it with
    the first would be reading a ruling wider than it was given.

    ⚠ **AND THE SEND-SIDE GAP IS A SEPARATE, ALREADY-FILED FACT.** This product
    cannot SEND a certified notice at all; the notice is served outside it and
    the proof is typed in. **The ruling does not fix that** — it only says the
    absence of proof no longer blocks.
    """
    proof = service_proof_for(case, tier=TIER_3)
    if not proof["recorded"]:
        # ⛔ **NOT A REFUSAL SINCE 2026-09-25 — `BR-CUS-1099`.** It returns
        # rather than raising, because the SECOND refusal below reads
        # `proof["channel"]`, which is meaningless on a proof nobody recorded:
        # falling through would refuse an absent proof for *'the channel is
        # None'*, which is the ruled-away refusal wearing the other one's
        # sentence. The fact is carried by `service_proof_warnings`.
        return
    if proof["channel"] != TIER_3_REQUIRED_CHANNEL:
        raise DisconnectRuleError(
            f"the tier-3 notice is recorded as served by {proof['channel']!r}, and `DSC-02.3` "
            "marks certified mail *'Required at tier 3 — proof of service'* — BR-CUS-039 says "
            "the same of the final tier. A cut whose lawfulness rests on certified mail cannot "
            "rest on another channel. If this utility serves tier 3 another lawful way, that is "
            "a ruling to take with the Product Owner, not a value to pass here.",
            code="tier_3_proof_not_certified",
            br_ref="BR-CUS-039",
        )


def already_cut(case: DisconnectCase) -> bool:
    """Has this case's cut already been RECORDED? ONE fact, read once (`DEF-CUS-6062`).

    ⚠ **`cut_on` IS THE FACT; THE STATE IS ONLY ITS USUAL SPELLING.**
    `commit_cut` is the sole writer of `disconnect_cases.cut_on` and nothing in
    this product ever clears it, so an OPEN case carrying one has had a
    household's supply taken away — whatever the `state` column says today. The
    state moves on afterwards by design (`reconnecting`, while a paid customer
    waits for a visit) and, until 2026-09-20, `schedule_cut` could move it
    BACKWARDS: `state == STATE_CUT` was true when `commit_cut` asked and false
    one route later. That is the whole of `DEF-CUS-6062`.

    ⚠ **READ BY THREE CALLERS ON PURPOSE** — `schedule_cut`, `commit_cut` and
    `disconnect_record.cut_readiness` — because a guard on ONE verb is a refusal
    another verb can walk around, and that is what `DEF-CUS-6062` was: two
    accepted calls, a second reconnection-fee invoice and a second balanced
    ledger pair against a household already cut, both of which hard rule 4 makes
    permanent.

    ⛔ **IT DOES NOT ANSWER *may this account ever be cut again* — IT IS ABOUT
    THIS CASE.** A household can be cut, reconnected and cut again;
    `restore_service` writes `STATE_RESTORED`, which is in
    `CLOSED_CASE_STATES`, so the case leaves the tab and the next enforcement
    opens a NEW case at tier 1 with its own notices, its own certified proof and
    its own fee. `tests/test_def_cus_6062_a_cut_cannot_be_un_cut.py` walks that
    sequence end to end, because a guard that refused it would be worse than the
    defect it closed.
    """
    return case.state == STATE_CUT or case.cut_on is not None


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def schedule_cut(
    actor: Any,
    account_id: Any,
    *,
    cut_on: date,
    as_of: date,
    reason: str | None = None,
    services: Any = None,
    deposit: str | None = None,
) -> dict[str, Any]:
    """B18 §5.8.4 step 4 — set the cut date. THE ONLY DOOR TO ONE.

    Calls `assert_cut_reachable` first and `_require_running` second, so a
    closed account and an account whose ladder is not running are each refused
    before a date is written.

    ⛔ **THIS PARAGRAPH SAID `assert_cut_reachable` REFUSED *"a protected account
    and a closed account"*, AND THAT GUARD READS NO PROTECTION AT ALL** — it
    answers `BR-CUS-082` only (a closed account, a collections sequence). The
    protection refusal is `_require_running`'s, through `halt_reason`'s
    `HALT_PROTECTED`. Hard-won law 1: a comment claiming a guarantee is not the
    guarantee. Corrected 2026-09-25, lane PROT.

    ⛔ **AND THE PROTECTION REFUSAL ITSELF IS NOW AGAINST A SIGNED RULE.
    `BR-CUS-1096` (PO 2026-09-25, closing `OQ-680`), verbatim: *"so please show
    the warining - but dont stop clark from doing his work; we have to tell
    there is an issue but we ant stop them"*.** A medical certificate, a weather
    moratorium or an active payment plan must **WARN** the clerk here and must
    **NOT** refuse the schedule; the product records which protections were in
    force, that the warning was shown, who proceeded and when — and asks the
    clerk for nothing, because a typed reason was put to the PO and declined.
    **THE CODE BELOW STILL REFUSES.** It is described here rather than changed
    because recording a ruling and wiring it are two acts and this lane did only
    the first; see `12-governance/02-decision-log.md`, 2026-09-25.

    ⚠ **THE WIZARD SCHEDULES; IT NEVER CUTS.** B18 §5.8.7's footer is on every
    one of the five steps — *"Step N of 5 · nothing is cut until the scheduled
    date"* — and step 5's button reads `Schedule the disconnection ✓`, not
    *Cut*. So the three elections the wizard collects on the way (step 1's
    reason, step 1's per-service treatment, step 4's deposit radio) are recorded
    HERE, and `commit_cut` performs the act on the date.

    **All three are OPTIONAL and none is defaulted into a decision:**

      * `reason` — one of `CUT_REASONS`. **Nothing branches on it**
        (`REASON_DRIVES_NOTHING`), and it is optional because making it required
        would refuse a schedule this product already accepts today. ⚠ Whether it
        SHOULD be required once S90 passes it is REPORTED, not chosen.
      * `services` — `DSC-02.1`'s table as a mapping, `{service_code:
        treatment}`. A restrictor is REFUSED by name; see
        `assert_treatments_expressible`.
      * `deposit` — `held` or `applied_against_arrear`. Left unset, `commit_cut`
        records `DSC-02.4`'s own drawn default (● Hold it), which is also the
        option that moves no money.

    The cut itself is `commit_cut` (task 7.8). ⚠ **The danger-tier commit
    (`DSC-02.5`, B14's destructive-commit rule) is a SCREEN and no screen exists
    — S90 is task 7.11 and owns no story yet.**

    ⛔ **IT IS SAFELY REPEATABLE ON A CASE THAT HAS NOT BEEN CUT, AND REFUSED ON
    ONE THAT HAS — `DEF-CUS-6062`, 2026-09-20.** A date moves, a service
    election changes, a clerk corrects themselves: re-scheduling a RUNNING case
    is ordinary and is untouched. Re-scheduling a case whose supply is already
    off is not a second schedule, it is the un-cutting of a recorded cut, and it
    was the first of the two moves that charged `A-11340` the reconnection fee
    twice. `already_cut` states the fact; the refusal in the body states why.

    ⚠ **WHY HERE AND NOT IN `halt_reason`.** The defect register's own
    suggestion was the broader one — *"a case in a TERMINAL state is not
    running, and that is the place to say so once rather than per route"* — and
    it was NOT taken, deliberately. `halt_reason` answers *is the LADDER
    running*, and its codes are grouped on the S90 segment, the worklists and
    the KPI strip; teaching it that a cut case is halted would re-label every
    cut case on those screens and change what `cut_readiness` and
    `reconnection_readiness` say, on the authority of a guard. The fact that a
    cut has been recorded belongs to the CASE, so the guard is on the verbs that
    read the case — and it is on BOTH of them, because a refusal one verb can
    walk around is not a refusal (decision log, 2026-09-20).
    """
    if reason is not None and reason not in CUT_REASONS:
        raise DisconnectRuleError(
            f"{reason!r} is not one of the five reasons `DSC-02.1` draws for cutting service "
            f"({', '.join(CUT_REASONS)}). A sixth reason is a new ground for taking away "
            "somebody's supply, and it needs a ruling rather than a string.",
            code="cut_reason_unknown",
            br_ref="B18 §5.8.7",
        )
    chosen_services = assert_treatments_expressible(services) if services is not None else None
    if deposit is not None and deposit not in DEPOSIT_DISPOSITIONS:
        raise DisconnectRuleError(
            f"{deposit!r} is not one of the two things `DSC-02.4` offers to do with a deposit "
            f"({', '.join(DEPOSIT_DISPOSITIONS)}). A deposit is money held on the customer's "
            "behalf — *'a liability, not revenue'* — and a third disposition is an accounting "
            "rule, not a value to pass here.",
            code="deposit_disposition_unknown",
            br_ref="`DSC-02.4`",
        )
    case = open_case_for(account_id)
    if case is None:
        raise DisconnectRuleError(
            "there is no open disconnect case on this account to schedule a cut for.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  ⛔ `DEF-CUS-6062` — A CUT THAT HAS HAPPENED CANNOT BE UN-HAPPENED    ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    # `commit_cut` refuses a second cut BY NAME and gives the reason; this
    # function never mentioned `STATE_CUT` at all, so that refusal was reachable
    # AROUND in two moves — schedule the cut case (accepted, the state goes back
    # to `scheduled`), then commit (the guard no longer fires). It is not
    # theoretical: `A-11340` carries TWO issued $75.00 reconnection-fee invoices
    # and two balanced ledger pairs, raised three hours apart on 2026-09-20, and
    # `cut_on` moved from the 20th back to the 14th.
    #
    # ⚠ **FIRST, AND THE ORDER IS A CHOICE ABOUT WHAT A CLERK IS TOLD.** Every
    # check below answers *is a cut lawful here yet* — the tier, the certified
    # proof, the ladder. On a case whose supply is ALREADY OFF every one of
    # those answers is true and useless, and one of them ("this case is not at
    # tier 3") would send somebody to serve notices on a household that has
    # already been cut. `assert_service_proved` argues its own position at the
    # other end of the same list for the same reason.
    if already_cut(case):
        raise DisconnectRuleError(
            f"this account was already cut on {case.cut_on}, so there is no cut left to "
            "schedule on this case. A cut is recorded once — `commit_cut` refuses a second one "
            "by name because re-recording it would re-quote the reconnection fee and re-date "
            "the enforcement — and moving this case back to `scheduled` is the way ROUND that "
            "refusal rather than a way past it: the next commit would raise the reconnection "
            "fee a SECOND time against the same household, in a second invoice that hard rule "
            "4 makes permanent. Service comes back the way B18 §5.8.4 draws it — payment "
            "confirmed, visit scheduled, restored — and a later cut opens a NEW case with its "
            "own notices, its own proof of service and its own fee.",
            code="already_cut",
            br_ref="BR-CUS-039",
        )
    assert_cut_reachable(case)
    if case.tier != TIER_3:
        raise DisconnectRuleError(
            "a cut is scheduled after TIER 3 · 48-HOUR, the certified final notice "
            "(BR-CUS-039: certified mail is REQUIRED on the final tier, and SMS never stands "
            f"alone). This case is at {case.tier!r}.",
            code="cut_before_final_tier",
            br_ref="BR-CUS-039",
        )
    _require_running(account_id, as_of=as_of, case=case, for_cut=True)
    # ⛔ BR-CUS-100 — *"a tier-3 cut must not be schedulable on an unrecorded
    # service"*. LAST, and the ORDER IS A CHOICE ABOUT WHAT A CLERK IS TOLD.
    # A case below tier 3 is refused for being at the wrong rung; a protected or
    # paid-up account is refused by `_require_running` with the protection or the
    # payment named. Only when a cut is otherwise lawful does the missing
    # receipt become the answer — telling somebody to go and find a postal
    # receipt for a household that is medically protected would be true and
    # useless. This is the last thing standing between that household and a cut.
    assert_service_proved(case)
    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  `CR-125-BRC07` — THE COMMIT IS ONE TRANSACTION, AND IT WAS NOT      ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    # ⚠ **THE ROUTE'S OWN DOCSTRING CLAIMED THIS AND NOTHING PROVIDED IT.**
    # `transfer_disconnect_api.schedule_cut` reads *"one payload, one address,
    # one transaction"* and satisfied `BR-SHL-019` on the first two. There were
    # TWO writes here — the case, then the audit row — with no `atomic()` around
    # them and `ATOMIC_REQUESTS` off, so **a failed audit write left a household
    # scheduled for disconnection with no record of who scheduled it.** That is
    # CLAUDE.md hard rule 7 (*every money action writes `audit_log`*) resting on
    # the audit insert never failing. Hard-won law 1: a comment claiming a
    # guarantee is not the guarantee — and this one was in a different file from
    # the code it described, which is why nobody reading either found it.
    #
    # ⚠ **`atomic()` HERE AND NOT AT THE ROUTE.** Turning on `ATOMIC_REQUESTS`
    # would wrap every write in the product on one lane's authority. The
    # guarantee belongs to the ACT, so it is stated where the act is, exactly as
    # `commit_cut` already states it for its own four writes.
    with transaction.atomic():
        case.cut_scheduled_for = cut_on
        case.state = STATE_SCHEDULED
        if reason is not None:
            case.cut_reason = reason
        if chosen_services is not None:
            case.services_cut = list(chosen_services)
        if deposit is not None:
            case.deposit_disposition = deposit
        case.save(
            update_fields=[
                "cut_scheduled_for",
                "state",
                "cut_reason",
                "services_cut",
                "deposit_disposition",
                "updated_at",
            ]
        )
        payload = case_payload(case)
        # ── `BR-CUS-1099` · WHAT THE UTILITY COULD NOT SHOW, ON THE ACT ─────
        # The ruling's second half. With nothing blocking, the record is the
        # only protection there is — and here it protects the UTILITY: a
        # final-tier cut without proved certified service is one it may not
        # lawfully have made. Inside the transaction and on the audited payload,
        # so `audit_log` carries the absence, who scheduled it and when
        # (CLAUDE.md hard rule 7). The clerk is asked for nothing.
        warnings = service_proof_warnings(case)
        if warnings:
            payload["warnings"] = list(warnings)
        _audit(actor, AUDIT_CUT_SCHEDULED, account_id, after=payload)
    return payload


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.8 — THE CUT ITSELF
# ════════════════════════════════════════════════════════════════════════════
def _charge_code(code: str) -> dict[str, Any] | None:
    """One of the tenant's own charge codes, or None — rating's read, by name.

    BR-BIL-007: *"NSF/reconnect fees are tenant-configured charge codes, never
    hardcoded"*, and `apps/rating/selectors.charge_by_code` says the same of
    itself: *"The amount is a SEED the tenant edits (B4 §NSF), never a
    constant, which is exactly why this read exists rather than a literal at the
    call site."* A `percent` rule answers `amount: None` there, and this module
    refuses on that rather than charging a number nobody computed.

    ⚠ **RESOLVED THROUGH THE LOCAL `_resolve`, NOT THROUGH `seams.py`.**
    `apps/customers/seams.py` does not publish a charge-code read and that file
    is another lane's; adding it there is the right home and is REPORTED, the
    same posture this module already takes for `apps.payments.dunning`.
    """
    fn = _resolve("rating", "charge_by_code", "selectors")
    if fn is None:  # pragma: no cover - rating is always present in this tree
        return None
    try:
        found = fn(code)
    except Exception:  # pragma: no cover - defensive: a catalogue read must not cut
        return None
    return dict(found) if found else None


def _deposit_on_file(account: Any) -> Decimal:
    """What the utility HOLDS for this customer, as a `Decimal`.

    `accounts.deposit_on_file` is `NUMERIC(18,6)` — a lawful container under
    CLAUDE.md rule 2 as re-signed 2026-08-22 (*"existing 18,6 columns stay
    lawful containers"*). Nothing is rounded here; `_money` labels the 4dp
    stored form and the 2dp display form at the edge.
    """
    raw = getattr(account, "deposit_on_file", None)
    return ZERO if raw is None else Decimal(str(raw))


#: p139's `WHEN` column, verbatim per row, and the `CHARGED?` answer beside it.
#: The two are different questions and the drawing asks both: *when would this
#: fee land* and *is it landing on THIS cut*. Only the reconnection fee answers
#: yes, and the caption says so in the drawing's own words.
FEE_TABLE_ROWS: tuple[tuple[str, str, str, bool], ...] = (
    (RECONNECT_CHARGE_CODE, "Reconnection fee", "At the cut", True),
    (DISCONNECT_CHARGE_CODE, "Disconnection fee", "At the cut", False),
    (FIELD_VISIT_CHARGE_CODE, "Field visit", "Only if a crew attends", False),
)

#: ⛔ **TWO OF THE THREE FEES HAVE NO PATH TO A BILL, AND THE SCREEN MUST SAY
#: SO RATHER THAN LIST THEM AS IF THEY WERE COMING.** p139: *"The cut raises the
#: reconnection fee and nothing else: the other two codes exist as names with no
#: path to a bill."* Measured on this tree 2026-09-20: `commit_cut` raises ONE
#: charge — the reconnection fee — and nothing in this repository ever raises
#: `CC-DISC` or `CC-FIELD`. Listing them with an amount and no `charged` flag
#: would read as three fees about to be charged.
FEE_NOT_RAISED_BY_ANYTHING: dict[str, Any] = {
    "code": "fee_code_has_no_path_to_a_bill",
    "br_ref": "`DSC-02.4` (blueprint p139) · BR-BIL-007",
    "detail": "this charge code is named by the design and nothing in this product ever raises "
    "it. The cut raises the reconnection fee alone. It is listed so a clerk can see the code "
    "exists and is NOT being charged, which is what the drawing states; it is not a fee this "
    "customer is about to owe.",
}


def _fee_table() -> list[dict[str, Any]]:
    """p139's three-row fee table, priced from the TENANT'S OWN catalogue.

    ⚠ **NOT ONE AMOUNT IS TYPED HERE** (`BR-BIL-007`: *"NSF/reconnect fees are
    tenant-configured charge codes, never hardcoded"*). The drawing prices them
    `$75.00 · $45.00 · $35.00` and every one of those is an ILLUSTRATION (B14
    rule 37). Each row asks `_charge_code` and answers `amount: None` with its
    reason when the tenant has no such row — which, measured 2026-09-20, is all
    three on every tenant in this tree (`RECONNECT_FEE_DISAGREEMENT`).

    ⚠ **A PERCENT RULE IS AN ABSENCE, NOT A PRICE.** `charge_by_code` answers
    `amount: None` for a percent rule because a percent needs a basis, and this
    read has none to supply. It is reported rather than resolved, exactly as
    `reconnection_terms` already does for its own row.
    """
    rows: list[dict[str, Any]] = []
    for code, description, when, charged in FEE_TABLE_ROWS:
        found = _charge_code(code)
        amount = None if found is None else found.get("amount")
        rows.append(
            {
                "code": code,
                # The tenant's own name for it where there is a row, and the
                # design's word where there is not — never a code at a clerk
                # (B14 rule 31/32).
                "charge": (found or {}).get("name") or description,
                "amount": None if amount is None else _money(Decimal(str(amount))),
                "amount_absence": (
                    None
                    if amount is not None
                    else dict(
                        CHARGE_CODE_SPELLING_UNRULED
                        if found is None
                        else {
                            "code": "charge_is_not_a_flat_amount",
                            "br_ref": "BR-BIL-007",
                            "detail": f"the tenant's {code!r} row is an "
                            f"{found.get('amount_rule')!r} rule, and a percent needs a basis "
                            "this read has no way to supply.",
                        }
                    )
                ),
                "when": when,
                "charged_on_this_cut": charged,
                "charged_absence": None if charged else dict(FEE_NOT_RAISED_BY_ANYTHING),
            }
        )
    return rows


def _to_clear(account_id: Any, *, fee: Any, case: DisconnectCase | None = None) -> dict[str, Any]:
    """p139's `The reconnection figure` — **$8,315.00 on both sides of the cut**.

    `BR-CUS-104`, signed by the PO on 2026-08-25 over `A-11340`: **$8,240.00
    arrears + $75.00 fee = $8,315.00 to clear**, and that figure is what
    `mark_reconnecting` requires.

    ⛔ **THE FIGURE MEANS TWO DIFFERENT THINGS EITHER SIDE OF THE COMMIT, AND
    THIS FUNCTION ADDED THE FEE IN BOTH — `DEF-CUS-6050`.** Before the cut the
    fee is a QUOTE and the position does not hold it, so *arrears + fee* is the
    answer. The moment `commit_cut` issues the fee bill the fee IS a receivable,
    the position already holds it, and the same addition quotes it twice:
    `A-11340` read **`To clear first $8,390.00`** beside **`Owed $8,315.00`** on
    one screen, on 2026-09-21, after the first cut this product ever completed.
    It was correct until the day it first executed, because until then no cut
    had ever committed.

    ⚠ **THE SHAPE CHOSEN IS *READ THE POSITION ONCE*, NOT *KEEP THE SUM AND
    LABEL IT*, AND HERE IS WHY.** A figure built by ADDING two sources has to
    know whether they overlap, and this overlap is created by the very act the
    figure describes — so the sum has no stable meaning and no label can give it
    one. After the cut the answer is the position, read once through the same
    `_balance_for` the gate reads, and nothing is added to it. `basis` rides the
    payload so a reader can see WHICH question was answered; it explains the
    figure, it does not repair it.

    ⚠ **THE BASIS IS `cut_on`, WHICH IS THE FACT.** It is written in the same
    transaction that issues the fee bill and nothing else writes it, so it is
    exactly *has this fee reached AR*. Not a state list — `service_off_windows`
    records below why a state list drops `restored` and `stopped` cases that
    were nonetheless cut. When no case is handed in, the account's open case is
    read here rather than assumed either way: assuming *before* re-opens this
    defect, and assuming *after* quotes a price short by the whole fee, which is
    `DEF-708`'s own shape.

    ⚠ **THE ARREARS ARE THE LEDGER'S Σ AND ARE NOT RE-DERIVED.**
    `_balance_for` is this module's one balance read and `mark_reconnecting`
    gates on the same one, so the figure a clerk is quoted and the figure that
    admits the customer back cannot disagree. `None` when the books cannot be
    asked — never `0`, which is what a settled account reads (`DEF-127`).

    ⚠ **BEFORE THE CUT THE TOTAL IS STATED ONLY WHEN BOTH HALVES ARE.** An
    arrear with no fee is not *the arrear*, it is a quote missing the thing
    being quoted for. A sum over one known half would tell a customer a price
    short by the whole fee. **After the cut the fee is no longer a half of the
    sum**, so the total needs only the position: a catalogue row edited or
    deleted months later cannot blank out the figure that gates a household's
    supply.

    ⚠ **IT IS A READ AND NOT A POSTING.** Nothing here writes a journal line,
    raises a charge or touches AR (rule 5, `BR-CUS-037`). `FEE_POSTED` states
    where the money actually lands and rides the payload beside this.
    """
    arrears = _balance_for(account_id)
    fee_amount = None if fee is None else Decimal(str(fee))
    if case is None:
        case = open_case_for(account_id)
    after_the_cut = case is not None and case.cut_on is not None
    arrears_absence = (
        None
        if arrears is not None
        else {
            "code": "balance_not_readable",
            "br_ref": "BR-CUS-015 · `DEF-127`",
            "detail": "the ledger could not be asked what this account owes, so the amount "
            "to clear before reconnection cannot be stated. It is reported rather than "
            "shown as 0.00, which is what a settled account reads.",
        }
    )
    total: dict[str, str] | None
    total_absence: dict[str, Any] | None
    if after_the_cut:
        # ── The cut has committed, so the fee IS the position. Read once. ──
        total = None if arrears is None else _money(arrears)
        total_absence = (
            None
            if arrears is not None
            else {
                "code": "reconnection_total_not_computable",
                "br_ref": "BR-CUS-104 (PO 2026-08-25) · `DEF-CUS-6050`",
                "detail": "the cut has been made, so the amount to clear is the ledger position "
                "it left behind — the arrears with the issued reconnection fee already in them "
                "— and that position could not be read. No total is stated: this is the figure "
                "that decides whether somebody gets their supply back, and a fabricated one "
                "reads exactly like a settled account.",
            }
        )
    else:
        both = arrears is not None and fee_amount is not None
        total = _money(arrears + fee_amount) if both else None
        total_absence = (
            None
            if both
            else {
                "code": "reconnection_total_not_computable",
                "br_ref": "BR-CUS-104 (PO 2026-08-25) · `OQ-CUS-12518`",
                "detail": "the amount to clear is the arrears PLUS the reconnection fee "
                "(BR-CUS-104, signed: $8,240.00 + $75.00 = $8,315.00), and one of the two "
                "halves is unreadable. No total is stated: a sum over the arrears alone would "
                "quote a customer a price short by the entire fee, which is the gap DEF-708 "
                "closed and must not reopen on a screen.",
            }
        )
    return {
        "arrears": None if arrears is None else _money(arrears),
        "arrears_absence": arrears_absence,
        "fee": None if fee_amount is None else _money(fee_amount),
        "total": total,
        "total_absence": total_absence,
        # ⚠ **WHICH QUESTION THE TOTAL ANSWERED**, so no later reader has to
        # infer whether the fee is inside it (`DEF-CUS-6050`). `fee_in_arrears`
        # is the one a caller building its own figure must read.
        "basis": dict(TO_CLEAR_AFTER_THE_CUT if after_the_cut else TO_CLEAR_BEFORE_THE_CUT),
        "timing": dict(FEE_TIMING_RULED),
    }


def reconnection_terms(account_id: Any, *, case: DisconnectCase | None = None) -> dict[str, Any]:
    """What it will cost to get service back — `DSC-02.4`'s step-4 quote.

    *"The reconnection fee is quoted now so the customer is told what it will
    cost to get service back **before it is taken away**."* That sentence is why
    this is a READ callable at any step and not a number computed inside the
    commit: the wizard shows it at step 4, the tier-3 letter prints the same
    figure (`apps/notifications/notices.py`'s `{reconnect_fee}` token), and
    `commit_cut` records it. **One read, so the letter and the screen and the
    record cannot quote three different prices.**

    Three answers, and each carries its own absence rather than a zero:

      * `fee` — the tenant's `CC-RECON` row. `None` with a reason when the code
        is not configured or is not a flat amount. **Never a literal $75.00**
        (BR-BIL-007), and never `0`.
      * `deposit` — what is held, what was elected, and the consequence
        `DSC-02.4` draws: *"Nothing is held, so a new deposit is required to
        reconnect."*
      * `posting` — `FEE_POSTED`, on every answer, because nothing adds
        this figure to AR.
    """
    account = _account(account_id)
    held = _deposit_on_file(account)
    charge = _charge_code(RECONNECT_CHARGE_CODE)
    amount = None if charge is None else charge.get("amount")
    fee_absence: dict[str, Any] | None = None
    if charge is None:
        # `CR-125-BRC07` — the spelling/price disagreement is now a FILED
        # question with all three figures on it, so the absence names it rather
        # than saying only that a ruling is owed.
        fee_absence = dict(CHARGE_CODE_SPELLING_UNRULED)
        fee_absence["oq"] = RECONNECT_FEE_DISAGREEMENT["oq"]
        fee_absence["disagreement"] = dict(RECONNECT_FEE_DISAGREEMENT)
    elif amount is None:
        fee_absence = {
            "code": "reconnect_charge_is_not_a_flat_amount",
            "br_ref": "BR-BIL-007",
            "detail": f"the tenant's {RECONNECT_CHARGE_CODE!r} row is an "
            f"{charge.get('amount_rule')!r} rule, and a percent needs a basis this read has no "
            "way to supply. `apps/rating/selectors.charge_by_code` answers `amount: None` for "
            "exactly that reason, and a flat price is not invented from the column behind it.",
        }

    election = case.deposit_disposition if case is not None else None
    if election == DEPOSIT_APPLIED:
        new_deposit_required: bool | None = True
        deposit_detail = (
            "the deposit was elected APPLIED against the arrear, so nothing is held and "
            "`DSC-02.4` says a new deposit is required to reconnect."
        )
    elif election == DEPOSIT_HELD:
        new_deposit_required = False
        deposit_detail = (
            "the deposit is HELD — `DSC-02.4`: *'The $500.00 stays held. The arrear stands … and "
            "the deposit is available if they reconnect.'*"
        )
    else:
        new_deposit_required = None
        deposit_detail = (
            "no deposit election is recorded on this case yet. `DSC-02.4` draws ● **Hold it** as "
            "the selected option, and `commit_cut` records that default rather than leaving the "
            "question open on a cut account."
        )

    fee = None if amount is None else _money(Decimal(str(amount)))
    return {
        "account_id": str(account_id),
        "charge_code": RECONNECT_CHARGE_CODE,
        "fee": fee,
        "fee_absence": fee_absence,
        # ── `CR-125-BRC07` · p139's `The fees on this cut` TABLE ─────────
        # `CHARGE · CODE · AMOUNT · WHEN · CHARGED?`, three rows, and the drawn
        # caption is the point of it: *"Three fees are designed and one is
        # charged."* This read served ONE of the three and the screen had no way
        # to tell a clerk that the other two exist and will not be raised.
        "fees": _fee_table(),
        # ── p139's `What must be cleared before service comes back` ──────
        # ⚠ **THE CASE TRAVELS WITH IT** — `DEF-CUS-6050`. Whether the fee is
        # already a receivable is decided by `case.cut_on`, and a read that
        # could not see the case would have to guess, in a direction that is
        # wrong by $75.00 either way.
        "to_clear": _to_clear(account_id, fee=amount, case=case),
        "deposit": {
            "on_file": _money(held),
            "election": election,
            "new_deposit_required": new_deposit_required,
            "detail": deposit_detail,
            "posting": dict(DEPOSIT_APPLICATION_NOT_POSTED),
        },
        "posting": dict(FEE_POSTED),
        "timing": dict(FEE_TIMING_RULED),
    }


def assert_treatments_expressible(services: Any) -> tuple[str, ...]:
    """`DSC-02.1`'s per-service decision → the codes to CUT. Refuses a restrictor.

    *"One decision per service, not all or nothing"*, and the drawn caption:
    *"Cutting electric and sewer · restricting water rather than cutting it. A
    restrictor limits flow to a minimum rather than stopping it, **which many
    jurisdictions require for water**."*

    ⛔ **A RESTRICTOR IS REFUSED BY NAME.** See `RESTRICTOR_UNBUILDABLE`: this
    schema holds cut and not-cut, and a restrictor is neither. Refusing is the
    only answer that does not make a false statement about a household's water,
    and the refusal names what building it would take.

    Takes the drawn table's own shape — `{service_code: treatment}` — so a
    caller cannot pass a bare list of services and leave the treatment implied.
    """
    chosen = dict(services or {})
    cut: list[str] = []
    for service_code, treatment in chosen.items():
        if treatment == TREATMENT_RESTRICTOR:
            raise DisconnectRuleError(
                f"{str(service_code)!r} is marked for a restrictor or limiter, and this schema "
                "cannot hold one: `disconnect_cases` knows cut and not-cut, and a restricted "
                "service is neither — it keeps flowing, keeps billing, and is under enforcement. "
                "Recording it as a cut would tell a regulator the supply was stopped; recording "
                "it as `leave_connected` would lose the enforcement. "
                + str(RESTRICTOR_UNBUILDABLE["what_it_would_take"]),
                code=str(RESTRICTOR_UNBUILDABLE["code"]),
                br_ref=str(RESTRICTOR_UNBUILDABLE["br_ref"]),
            )
        if treatment not in SERVICE_TREATMENTS:
            raise DisconnectRuleError(
                f"{treatment!r} is not one of the three treatments `DSC-02.1` draws per service "
                f"({', '.join(SERVICE_TREATMENTS)}). A fourth is a statement about what happened "
                "to somebody's supply, and it needs a ruling rather than a string.",
                code="service_treatment_unknown",
                br_ref="B18 §5.8.7",
            )
        if treatment == TREATMENT_FULL:
            cut.append(str(service_code))
    assert_services_exist(tuple(chosen))
    return tuple(cut)


def assert_services_exist(service_codes: tuple[str, ...]) -> None:
    """⛔ **THE SERVICE NAMED MUST BE ONE THIS PRODUCT HAS.**

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  `CR-125-BRC07` — A CUT WAS ACCEPTED AND RECORDED FOR `"unicorn"`    ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Measured by driving this service against real PostgreSQL 2026-09-20, inside
    a rolled-back transaction: `schedule_cut` accepted `{"unicorn":
    "full_disconnection"}` and wrote `services_cut = ["unicorn"]` onto the case.
    Every check in this repository passed over it. `assert_treatments_
    expressible` above validated the TREATMENT — three values, refused by name —
    and never the SERVICE, so the half of the drawn table that says *what* was
    cut was the unvalidated half.

    ⚠ **WHY IT MATTERS MORE THAN A TYPO.** `commit_cut` opens a
    `service_off_windows` interval per code in `services_cut`, and billing
    subtracts those dark days from `service_days` so `B4.3`'s ❄️ FROZEN factor
    prices the base charge. A code nothing sells prices nothing and reads as a
    service that WAS cut — so the regulator-facing record of what was taken away
    is a string nobody can resolve, on the one table that exists to answer that
    question.

    ⚠⚠ **IT CHECKS THE PLATFORM CATALOGUE AND NOT THE TENANT'S ENABLED SET, AND
    THE FIRST DRAFT CHECKED THE TENANT'S — WHICH BROKE 18 TESTS AND WAS THE
    RIGHT WAY TO FIND OUT.** `seams.enabled_service_codes()` is *what THIS
    utility sells today*; `seams.service_catalog_order()` is *what this product
    HAS* (`BR-RAT-024`'s eleven). Written against the first, this refused
    `sewer` on Brazos Bend — a real service, on a tenant that has Electric and
    Water switched on — and took `tests/test_w7_cut_reconnect.py` from green to
    **18 failed**.
    **That was not a broken fixture; it was a second, stricter rule nobody
    ruled.** A utility can switch a service OFF in Settings after an account has
    been taking it for years, and the supply does not stop existing when the
    catalogue row does — so refusing to record a cut on it would be this module
    inventing a rule about what a tenant may disconnect. The defect was a code
    that names NO SERVICE IN THE PRODUCT, and that is exactly the line drawn
    here.
    **Whether a cut should ALSO be refused on a service the tenant has switched
    off is a real, narrower question, and it is REPORTED rather than taken.**

    ⚠ **THE CATALOGUE, NEVER A LITERAL.** `BR-RAT-024` has moved six → ten →
    eleven and every list that named the services individually is still being
    found (`G47`); a tuple of eleven strings here would be the next one.

    ⚠ **AN UNREADABLE CATALOGUE REFUSES NOTHING, AND THAT IS DELIBERATE.** The
    read answers an empty tuple when the platform table cannot be reached, and
    an empty tuple means *this could not be asked*, not *this product has no
    services*. Refusing every service on an unanswered question would make a
    partial deployment unable to cut anybody — turning a reporting gap into an
    outage. Hard-won law 7's own test: a check that cannot tell *absent* from
    *empty* is a check that fails wrongly.
    """
    if not service_codes:
        return
    known = set(seams.service_catalog_order())
    if not known:
        return
    unknown = sorted(str(code) for code in service_codes if str(code) not in known)
    if unknown:
        raise DisconnectRuleError(
            f"{', '.join(repr(code) for code in unknown)} "
            + ("is not a service" if len(unknown) == 1 else "are not services")
            + " this product knows. A cut records WHAT was taken away, and a code naming no "
            "service opens a service-off window billing cannot price and cannot be answered to "
            "a regulator. This product's services are "
            f"{', '.join(sorted(known))}.",
            code="service_code_unknown",
            br_ref="BR-RAT-024 · `DSC-02.1`",
        )


# ════════════════════════════════════════════════════════════════════════════
# CR-052 W0 TASK 1 — THE CUT IS THE WHOLE EVENT (PO ruling 2026-08-30)
#
# Four small acts, in this order, inside `commit_cut`'s one transaction:
# bill → settle → write the status → record what is still outstanding.
# None of them contains arithmetic and none of them writes a financial table.
# ════════════════════════════════════════════════════════════════════════════

#: BR-CUS-107's seeded row, by CODE. `services.SEED_ACCOUNT_STATUSES` is where
#: it is defined and `AccountStatus` is per-tenant, so the code is the handle
#: and the row is resolved against the tenant every time.
CUT_STATUS_CODE = "disconnected"

#: BR-CUS-104's terms, applied to the metered bill as well as to the fee.
#: **A DERIVATION, NOT A DEFAULT.** CR-029 D8③ makes a cycle-less bill take its
#: due-days from the caller — *"it will be capture at the time of bulk billing -
#: not here"* — and this caller is the CUT. `0` is a TYPED value meaning *due on
#: the bill date* (BR-MET-009's `due_days >= 0`), which is what the ruling of
#: 2026-08-30 says in the column's own vocabulary: the whole event happens at
#: the cut and *"outstanding is pending on account"* from that moment. The
#: reconnection fee already falls due on this day (`commit_cut`'s `due_days=0`,
#: BR-CUS-104), and two money items raised by ONE act falling due on two
#: different days would be a distinction nobody decided.
CUT_BILL_DUE_DAYS = 0


def _cycle_days_for(account: Any, *, as_of: date) -> int | None:
    """B4.3's DENOMINATOR for the cut bill — the customer's cycle length.

    B4.3 ❄️ prorates base by `service_days / cycle_days`, and the cut bill's
    window is short *because the service was cut*. Dividing by the window's own
    length would make the factor 1 and charge a FULL period's base for a part
    period: on the PO's own case, **$40.00** where 18 days of 31 is **$23.23**.

    ✅ **THAT IS WHAT THIS DID UNTIL 2026-08-31, AND IT IS `DEF-2708`** —
    $16.77 too much on a real customer's final bill. Metering had never
    published `billing_period_for_unit`, so this read answered `None` on every
    cut and the fallback was the whole charge. It is published now: the period
    is derived from the cycle's own ruled schedule (`OQ-339` · `OQ-340` ·
    B17 §2), and `A-11488` cut 18 August reads **1–31 August → 31 days**.

    ⚠ **IT IS READ, NEVER ASSUMED, AND `None` IS STILL AN HONEST ANSWER** —
    a pre-CR-029 cycle carries no frequency and no first run, and a unit on two
    cycles has no single period. Assuming a 30-day month would invent money from
    a calendar nobody configured. `None` travels to billing, which states the
    consequence on its result (`cut_bill.CUT_BILL_DENOMINATOR_ABSENT`) rather
    than applying it silently.

    ⚠ **`as_of` IS THE CUT DATE, NOT A CLOCK (BR-TEN-043 / G6).** A cut on
    18 February committed by a clerk in March must divide by February's 28 days
    and not March's 31 — on a $40.00 base that is $25.71 against $23.23. The
    event date is the account's, so it is passed; nothing here reads today.
    """
    window = seams.billing_period_for_unit(getattr(account, "unit_id", None), as_of=as_of)
    if not window:
        return None
    try:
        start = date.fromisoformat(str(window["start"]))
        end = date.fromisoformat(str(window["end"]))
    except (KeyError, TypeError, ValueError):  # pragma: no cover - defensive
        return None
    days = (end - start).days + 1
    return days if days > 0 else None


def _raise_final_bill_at_the_cut(actor: Any, account: Any, *, cut_on: date) -> Any:
    """Ask BILLING for the bill the ruling of 2026-08-30 puts at the cut.

    **PO verbatim:** *"when we disconnect - we generate final bill at that time
    itself - so later bill is not required"*. The window is the account's first
    unbilled day through `cut_on` INCLUSIVE (BR-CUS-103: *"a service is billed
    base right up to the moment it is cut"*), and billing derives its start —
    this module names the cut date and nothing else about the money.

    ⚠ **CUSTOMERS DOES NOT BILL, AND THIS IS THE WHOLE REASON THE SEAM EXISTS.**
    BR-CUS-037 keeps a money act to *"validate → confirm → owning-module
    service"*, only the ledger posting service writes journal lines (rule 5),
    and a cross-module write is forbidden (B1 / B2 §2). So this asks
    `apps.billing.services.raise_and_issue_cut_bill` by name, exactly as the
    reconnection fee asks `raise_and_issue_charge_fee`, and gets back a result
    that says which of four things happened.

    ⚠ **IT IS RAISED INSIDE THE CUT'S OWN TRANSACTION**, as the fee is. A cut
    recorded beside a bill that failed to issue is the customer told they owe
    the days and nobody ever charging them.
    """
    return seams.raise_and_issue_cut_bill(
        actor,
        account_id=account.pk,
        cut_on=cut_on,
        due_days=CUT_BILL_DUE_DAYS,
        # ⚠ THE CUT DATE, NOT TODAY (`DEF-2708` · BR-TEN-043). The period B4.3
        # divides by is the one the CUT falls in, and a clerk committing a
        # February cut in March would otherwise divide by the wrong month.
        cycle_days=_cycle_days_for(account, as_of=cut_on),
        # BR-TEN-043 / G6 — no clock on a money path. Billing derives the
        # instant from the cut DATE, so a replay stamps the same moment.
        issued_at=None,
    )


def _settle_at_the_cut(account_id: Any) -> Decimal | None:
    """The SETTLEMENT half of the ruling — read the position, write nothing off.

    **PO verbatim:** *"entire workflow including all settlement and status
    update is taken care at time of disconnect or move out - so account status
    changes and **outstanding is pending on account if any**"*.

    So settling at a cut is not a movement of money — it is the act of closing
    the position and stating what is left. This reads AR *after* the final bill
    and the reconnection fee have issued, which is why it is called last, and
    the figure is recorded on the case as the fact of the day.

    ⛔ **AND IT IS NOT `final_bill.settle_final_bill`.** `DSC-02.4`: *"Close the
    account or settle the deposit — that is a move-out, not a disconnect"*, and
    *"Stop the balance growing, or write any of it off"*. So no deposit is
    applied, no write-off threshold is consulted, no path is chosen and the
    account is not closed. On the PO's worked case `A-11488` is cut owing
    **$612.75**, the fee adds **$75.00** and the final bill adds the days before
    the cut — and every cent of it stays outstanding on an OPEN account.

    None means the ledger could not be read, and it is never read as zero: a
    fabricated $0.00 on the record of a household in arrears is DEF-628's shape,
    and `_balance_for` says so in its own docstring.
    """
    return _balance_for(account_id)


def _write_disconnected_status(account: Any) -> tuple[str | None, str | None]:
    """BR-CUS-107's status, written at the cut. Returns `(before, after)` CODES.

    **The status is what removes the account from
    `selectors.accounts_for_bill_run`** — that read filters on
    `services.OCCUPYING_BEHAVIOR_CLASSES`, which is `(billable,
    billable_base_only)`, and `disconnected` is `non_billable`. That drop is
    CORRECT the moment the days before the cut have been billed and was the
    whole of `OQ-1170`'s money until they were.

    ⚠ **ONLY `status` MOVES.** `DSC-02.4`'s first prohibition is untouched: not
    `closed_at`, not `deposit_on_file`, not `close_reason`. `update_fields` names
    exactly two columns so a later edit cannot widen it by accident.

    The code held BEFORE the cut is recorded on the case in the same
    transaction, as history — a restoration writes Active since 2026-10-29
    (`DEF-CUS-10668`), not this code. See
    `disconnect_cases.status_before_cut`.

    Returns `(None, None)` when the seeded row is missing on this tenant, which
    is a provisioning gap and not a decision: the caller reports it and does not
    invent a status.
    """
    from apps.customers import models as customers_models

    before = getattr(account.status, "code", None)
    row = customers_models.AccountStatus.objects.filter(
        tenant_id=account.tenant_id, code=CUT_STATUS_CODE
    ).first()
    if row is None:  # pragma: no cover - BR-CUS-107 seeds it on every tenant
        return (before, None)
    account.status = row
    account.save(update_fields=["status", "updated_at"])
    return (before, row.code)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def commit_cut(
    actor: Any,
    account_id: Any,
    *,
    cut_on: date,
    as_of: date,
    final_reads: Any = None,
) -> dict[str, Any]:
    """W7 7.8 — the cut happens. `DSC-02.4`'s consequences, and only those.

    ⚠ **AND SINCE 2026-08-30 IT IS THE WHOLE EVENT (CR-052 W0 task 1).** The PO
    ruled that a disconnection bills, settles and re-statuses in one act:
    *"when we disconnect - we generate final bill at that time itself - so later
    bill is not required ... entire workflow including all settlement and status
    update is taken care at time of disconnect or move out - so account status
    changes and outstanding is pending on account if any"*. Four things now
    happen inside the one transaction below, in this order and for this reason:

      1. **THE FINAL METERED BILL**, for the account's first unbilled day
         through `cut_on` inclusive, raised through billing's own door
         (`seams.raise_and_issue_cut_bill`) because customers may not write an
         invoice. FIRST, because stage 1 refuses to price an account that is not
         billable and step 3 is what makes it non-billable.
      2. **THE RECONNECTION FEE**, unchanged (BR-CUS-104 / DEF-708).
      3. **THE STATUS** — BR-CUS-107's `Disconnected`, and the code the account
         held before it, recorded on the case so the restoration can put it
         back. Written **only when step 1 billed the days or proved there were
         none**: the status is what drops the account out of
         `selectors.accounts_for_bill_run`, and doing that over unbilled days is
         the **$23.23** `OQ-1170` was raised about.
      4. **THE SETTLEMENT** — read the position, write nothing off, close
         nothing, move no deposit. Whatever remains is OUTSTANDING on an open
         account and `outstanding_at_cut` records what that was.

    ⚠ **`final_reads` JOINED 2026-08-26 (CR-038 W9 task 6).** The crew that
    cuts the service reads the meter as it goes dark, and that reading — per
    meter, dated `cut_on`, never a wall clock — commits through the metering
    event door with event `disconnect` and the acting user (BR-MET-128), the
    same append-only pipeline every read takes (BR-CUS-021). BR-MET-129 rides
    it: warnings post flagged; an ERROR refuses the WHOLE cut with the failing
    rows named, because the ONE transaction below makes the cut and its read a
    single act — a cut recorded over a refused reading would strand the final
    consumption. A row may carry `estimate: true` where the meter cannot be
    read (W9 task 8 — disclosed, capped, never a silent zero). Absent =
    nothing posts and nothing is invented; `DSC-02.4`'s own prohibitions
    stand untouched — nothing here writes `accounts`, and the meter-read
    write is METERING's, not this module's.

    ⛔ **NO SURFACE CALLS THIS WITH READS YET, AND THAT IS REPORTED, NOT
    PAPERED OVER.** The wizard schedules and never cuts (§1 of
    `DisconnectWizard.tsx` — *"`commit_cut` performs the act on the day, from
    somewhere else"*), and `apps/customers/api.py` mounts no disconnect write
    route. The door is ready for the cut surface the day it lands, exactly as
    `accept_field_result`'s send trigger was built ahead of its button.

    **WHAT IT DOES**, `DSC-02.4`'s `Will` column verbatim:

      * *"Cut the services chosen at step 1 on the scheduled date, **leaving the
        account open**."*
      * ⛔ *"**Keep charging base and standing charges — a disconnected account
        still accrues.**"* — **SUPERSEDED by BR-CUS-103 (PO 2026-08-25, OQ-380,
        *"no"*). Base charges STOP at the cut.**
      * *"Add $75.00 to the balance as the price of getting service back."*
      * *"Move the account into the **disconnected state, which blocks new
        service elsewhere until it is settled**."*

    **WHAT IT MUST NOT DO**, and each is a line this function could trivially
    cross:

      * *"Close the account or settle the deposit — that is a move-out, not a
        disconnect."* **Not `closed_at`, not `deposit_on_file`, not
        `close_reason`.** A cut that closed an account would be a move-out
        performed by the collections screen, and BR-CUS-091 already warns in
        `models.py` that *"nothing in this module may quietly convert one into
        the other"*.
        ⚠ **AMENDED 2026-08-30 — `accounts.status` IS NOW WRITTEN, AND ONLY
        THAT.** This clause read *"Nothing here writes `accounts`"* and listed
        `status` beside the two prohibitions above, which was right while the
        cut billed nothing. **PO ruling 2026-08-30 — the disconnect is the WHOLE
        event:** *"when we disconnect - we generate final bill at that time
        itself - so later bill is not required ... entire workflow including all
        settlement and status update is taken care at time of disconnect or move
        out - so account status changes and outstanding is pending on account if
        any"*. So BR-CUS-107's `Disconnected` is written here (`OQ-1170`,
        CLOSED), the account STAYS OPEN, the deposit stays where it is, and
        `DSC-02.4`'s two real prohibitions above are untouched. See
        `DISCONNECTED_STATUS_ASSIGNED`.
      * *"Stop the balance growing, or write any of it off."* ⚠ **THE FIRST
        HALF OF THAT SENTENCE IS SUPERSEDED BY BR-CUS-103** — the PO ruled on
        2026-08-25 that base charges STOP at the cut (OQ-380, *"no"*), so the
        balance does NOT keep growing. What survives, and is still held by
        omission here, is the second half: **nothing is written off**, because
        the account row is untouched. See `CUT_STOPS_BASE`.
      * *"Remove the meter, unless you chose meter removal as the field work."*
        Assets are metering's (B2 r4) and this module makes no cross-module
        write. A meter removal is a field work order, not a consequence of this
        call.

    ✅ **THE FEE IS QUOTED *AND CHARGED* — DEF-708, PO ruling 2026-08-27.** This
    paragraph read *"THE FEE IS QUOTED, NOT POSTED … it does not reach AR"* until
    the PO ruled: *"Make the fee a real charge — It becomes a line that can be
    billed and paid, so the gate has something to check."*

    Two writes now, and they are two different facts about the same money:

      * `reconnection_terms` reads the tenant's `CC-RECON` row (BR-BIL-007 —
        never a literal) and the amount is written to
        `disconnect_cases.reconnection_fee_amount` at 4dp. That is the RECORD of
        what the customer was quoted on the day, and it never changes again.
      * `seams.raise_and_issue_charge_fee` asks BILLING to raise the same charge
        code as a `fee` bill and ISSUE it, so the amount is in AR from the moment
        of the cut. That is the MONEY.

    ⚠ **A CALLER STATES BOTH AND NEVER ADDS THEM TOGETHER.** They are one $75.00
    seen twice. `FEE_POSTED` travels on the result and says so.

    ⚠ **THE FEE IS RAISED INSIDE THE SAME TRANSACTION AS THE CUT**, so a cut
    whose fee cannot be charged does not happen at all. The alternative —
    recording the cut and reporting the failed charge — is DEF-708 restored: the
    customer is told they owe $75.00 and nobody ever bills it.

    ⚠ **AND THE FEE'S TERMS ARE `due_days=0`, DERIVED FROM BR-CUS-104 AND NOT
    CHOSEN HERE.** The rule is that the fee is owed *at the cut* — *"does
    reconnection need $8,315.00 - this is correct"* — and a cycle-less bill takes
    its terms from the caller (CR-029 D8③) because there is no cycle to take them
    from. `0` is a TYPED value meaning *due on the bill date* (BR-MET-009's
    `due_days >= 0`), which is what "owed at the cut" says in the column's own
    vocabulary. It is not a default: `raise_and_issue_charge_fee` requires the
    argument and billing chooses nothing.

    And **the cut REFUSES when no reconnection charge code is configured**, because
    `DSC-02.4`'s own reason for quoting the fee is *"so the customer is told
    what it will cost to get service back before it is taken away"* — a cut
    nobody can price is a cut the customer cannot undo. This is
    `apps/notifications/notices.py`'s posture for the same figure in the same
    letter: *"Configure the reconnect charge code, then generate."*

    ⚠ **IT REFUSES IF THEY PAID.** `_require_running` is called again here, not
    only at `schedule_cut`, because days pass between the two: B18 §5.8.7's step
    5 promises the customer *"it stops automatically if they pay or agree a
    plan"*, and a schedule-time-only check would cut a household that paid on
    the Friday. `assert_cut_reachable` and `assert_service_proved` are re-run for
    the same reason — an account can close, and a proof cannot un-record but a
    tier can be re-raised.

    ⚠ **AND IT CANNOT RUN EARLY.** `DSC-02.3`: *"EARLIEST LAWFUL CUT Aug 24 ·
    Locked — computed, not chosen"* and *"Cannot be earlier than Aug 24."* A cut
    committed before the scheduled date is a cut the notice did not warn about.
    ⚠ **The scheduled date itself is NOT computed here** — the *"Aug 22 plus 48
    hours, rolled forward past weekends and public holidays"* roll is task
    7.9's date computation and is `schedule_cut`'s input today; B18 warns *"a
    lane must not read '48 hours' as '+2 days'"* and this lane reads neither.
    """
    case = open_case_for(account_id)
    if case is None:
        raise DisconnectRuleError(
            "there is no open disconnect case on this account, so there is nothing to cut.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    # ⚠ **`already_cut`, NOT `state == STATE_CUT` — `DEF-CUS-6062`.** This read
    # the state alone until 2026-09-20 and the state is the one thing another
    # verb could move: `schedule_cut` wrote a cut case back to `scheduled` and
    # this guard then saw nothing wrong. The predicate reads `cut_on` too, which
    # only this function writes and nothing ever clears, so the second door is
    # shut from the inside as well as from the outside — and the damaged rows
    # the walk-around already left behind (`scheduled` WITH a `cut_on`) are
    # refused here rather than charged a second fee.
    if already_cut(case):
        raise DisconnectRuleError(
            f"this account was already cut on {case.cut_on}. A cut is recorded once: re-recording "
            "it would re-quote the reconnection fee and re-date the enforcement, and the record a "
            "utility shows a regulator cannot be re-pointed afterwards (hard rule 4's "
            "discipline). If the crew attended twice, that is a field record, not a second cut.",
            code="already_cut",
            br_ref="BR-CUS-039",
        )
    if case.state != STATE_SCHEDULED:
        raise DisconnectRuleError(
            f"this case is {case.state!r} and no cut is scheduled on it. `DSC-02`'s footer is on "
            "every one of the five steps — *'nothing is cut until the scheduled date'* — and the "
            "scheduling is what serves the notice, computes the earliest lawful date and records "
            "the services chosen. A cut with no schedule behind it is a cut nobody was told "
            "about.",
            code="cut_not_scheduled",
            br_ref="B18 §5.8.7",
        )
    assert_cut_reachable(case)
    if case.cut_scheduled_for is None or cut_on < case.cut_scheduled_for:
        raise DisconnectRuleError(
            f"the earliest lawful cut on this case is {case.cut_scheduled_for} and this would cut "
            f"on {cut_on}. `DSC-02.3` locks that date — *'EARLIEST LAWFUL CUT · Locked — computed, "
            "not chosen'* — because it is the notice period the customer was given. Cutting "
            "before it is cutting without the notice.",
            code="cut_before_the_scheduled_date",
            br_ref="BR-CUS-039",
        )
    services = tuple(case.services_cut or ())
    if not services:
        raise DisconnectRuleError(
            "no service on this case is marked for full disconnection. `DSC-02.1` is explicit "
            "that this is *'One decision per service, not all or nothing'*, so a cut that names "
            "no service cannot fall back on cutting everything — that is precisely the assumption "
            "the drawn table exists to prevent.",
            code="no_services_chosen",
            br_ref="B18 §5.8.7",
        )
    _require_running(account_id, as_of=as_of, case=case, for_cut=True)
    assert_service_proved(case)

    terms = reconnection_terms(account_id, case=case)
    if terms["fee"] is None:
        absence = terms["fee_absence"] or dict(CHARGE_CODE_SPELLING_UNRULED)
        raise DisconnectRuleError(
            f"this cut cannot be recorded: the reconnection fee cannot be read from the tenant's "
            f"{RECONNECT_CHARGE_CODE!r} charge code. `DSC-02.4` quotes that fee before the cut "
            "*'so the customer is told what it will cost to get service back before it is taken "
            "away'*, and the tier-3 letter prints the same figure. A cut nobody can price is a "
            "cut the customer cannot undo. Configure the reconnection charge code, then cut. "
            + str(absence["detail"]),
            code=str(absence["code"]),
            br_ref=str(absence["br_ref"]),
        )

    fee = Decimal(str(terms["fee"]["stored"]))
    account = _account(account_id)
    with transaction.atomic():
        # ── CR-038 W9 task 6: the final read, in the SAME act as the cut ────
        # ⚠ **BEFORE THE CUT BILL, NOT AFTER IT (`DEF-CUS-10166`).** Until
        # 2026-10-17 nothing sent `final_reads` and the order was invisible;
        # the moment Mark as cut takes a closing reading, posting it AFTER
        # the bill would leave the very reading the clerk typed unbilled by
        # the bill the PO ruled makes a later one unnecessary. Move-out
        # posts its final reads before drafting its final bill for the same
        # reason (`DEF-CUS-10093`). One transaction either way: a refused
        # reading still refuses the whole cut.
        event_reads = None
        if final_reads is not None:
            from apps.customers import services

            event_reads = services._commit_event_reads(
                actor,
                event="disconnect",
                reads=final_reads,
                default_read_at=cut_on,
                # DEF-CUS-10166 — the dialog's closing read date, bounded.
                bounded_dates=True,
                context={
                    "account_id": str(account_id),
                    "unit_id": str(getattr(account, "unit_id", None)),
                    "case_id": str(case.id),
                    "flow": "disconnect",
                },
            )

        # ── CR-052 W0 · THE FINAL METERED BILL, BEFORE THE STATUS ───────────
        # PO 2026-08-30: *"when we disconnect - we generate final bill at that
        # time itself - so later bill is not required"*. It is raised BEFORE the
        # status is written and that ORDER is load-bearing: billing's stage 1
        # refuses to price an account that is not billable (BR-CUS-055), and
        # `disconnected` is `non_billable`. Bill first, then write the word.
        cut_bill = _raise_final_bill_at_the_cut(actor, account, cut_on=cut_on)
        case.state = STATE_CUT
        case.cut_on = cut_on
        case.reconnection_fee_amount = fee
        case.reconnection_fee_code = RECONNECT_CHARGE_CODE
        # `DSC-02.4`'s drawn default is ● **Hold it**, and holding is also the
        # option that moves no money — so an election nobody made lands on the
        # one that leaves the customer's deposit where it is. Applying it is
        # the irreversible half and must be asked for.
        case.deposit_disposition = case.deposit_disposition or DEPOSIT_HELD
        # ── DEF-708 · THE FEE BECOMES A RECEIVABLE, HERE, AT THE CUT ────────
        # BR-CUS-104 (PO 2026-08-25): the fee lands AT THE CUT, not when service
        # is restored. Inside the cut's own transaction (see the docstring) and
        # through the OWNING module's service (BR-CUS-037), which issues it and
        # hands the posting to the ledger (rule 5). Nothing financial is written
        # by this module.
        fee_invoice = seams.raise_and_issue_charge_fee(
            actor,
            account_id=account_id,
            charge_code=RECONNECT_CHARGE_CODE,
            on_date=cut_on,
            # See the docstring: BR-CUS-104's *owed at the cut*, in the column's
            # own vocabulary. Not a default and not billing's choice.
            due_days=0,
            description=RECONNECTION_FEE_DESCRIPTION,
        )
        # ── CR-052 W0 · THE STATUS, AND THE ONE RULE THAT GOVERNS IT ───────
        # **`Disconnected` is written only when the days up to the cut are
        # billed — or provably have nothing left to bill.** The status removes
        # the account from `selectors.accounts_for_bill_run`, so writing it over
        # a bill billing REFUSED would leave those days billed by nobody, which
        # is `OQ-1170`'s $23.23 restored by a convenience. The cut itself still
        # happens either way: a household's supply is not left connected because
        # its tariff has no version in force. See
        # `CUT_BILL_BLOCKED_SO_STATUS_HELD`.
        status_before = status_after = None
        if cut_bill.billed:
            status_before, status_after = _write_disconnected_status(account)
            case.status_before_cut = status_before
        # ── CR-052 W0 · SETTLE — read the position, write nothing off ───────
        # Last, so it sees the final bill and the fee that this same
        # transaction has just issued. `DSC-02.4` forbids the two things a
        # move-out settlement does, so nothing is applied and nothing is
        # closed: what is left is simply OUTSTANDING on an open account, which
        # is the PO's own last clause.
        outstanding = _settle_at_the_cut(account_id)
        case.outstanding_at_cut = outstanding
        case.save(
            update_fields=[
                "state",
                "cut_on",
                "reconnection_fee_amount",
                "reconnection_fee_code",
                "deposit_disposition",
                "status_before_cut",
                "outstanding_at_cut",
                "updated_at",
            ]
        )
        payload = cut_payload(case)
        # `BR-CUS-1099`, re-asked at the cut for the reason every other guard is
        # re-asked here: days pass between the schedule and the act, and a proof
        # recorded in between changes the answer. See `schedule_cut`.
        cut_warnings = service_proof_warnings(case)
        if cut_warnings:
            payload["warnings"] = list(cut_warnings)
        if event_reads is not None:
            payload["event_reads"] = event_reads
        # CR-052 W0 — the three halves of the ruled event, on the act that
        # performed them, so `audit_log` records WHY the status moved and what
        # was left owing when it did (CLAUDE.md rule 7).
        payload["cut_bill"] = cut_bill.as_payload()
        payload["account_status_written"] = status_after
        payload["account_status_before_cut"] = status_before
        if not cut_bill.billed:
            payload["account_status_held"] = dict(CUT_BILL_BLOCKED_SO_STATUS_HELD)
            # PO ruling 2026-09-21 — the days nobody has billed, named on the
            # act that left them unbilled. The status is HELD here, so they are
            # still in the bill run; `finish_cut(without_bill=True)` is what
            # takes them out of it, and it states them again when it does.
            payload["days_not_billed"] = unbilled_days_at_cut(case)
        payload["settlement"] = {
            "outstanding": None if outstanding is None else _money(outstanding),
            # CLAUDE.md rule 2 — a figure never travels without its currency,
            # and `_money` carries only the two SHAPES. The case's own CHAR(3)
            # is the one this account's ladder was opened in.
            "currency": case.currency,
            "written_off": None,
            "account_closed": False,
            "deposit_settled": False,
            "br_ref": "`DSC-02.4` · PO ruling 2026-08-30",
            "detail": "the cut settles the POSITION and moves no money: nothing is written "
            "off, the deposit is untouched and the account stays open. Whatever remains is "
            "outstanding on it (the PO's own words: *'outstanding is pending on account if "
            "any'*), and `outstanding_at_cut` is the record of what that was on the day.",
        }
        # DEF-708 — WHICH BILL carries the fee, on the act that raised it. A
        # figure with no document behind it is what this defect was.
        payload["fee_invoice"] = {
            "id": str(getattr(fee_invoice, "pk", "")),
            "invoice_no": getattr(fee_invoice, "invoice_no", None),
            "total": _money(Decimal(str(getattr(fee_invoice, "total", fee)))),
            "charge_code": RECONNECT_CHARGE_CODE,
        }
        # ── DEF-NOT-10649 · THE CUSTOMER IS TOLD ────────────────────────────
        # PO 2026-10-29, *"1 A, 2 A, 3 A, 4 A"*: *Service disconnected* by
        # email and (where they chose it) text, on by default, switchable per
        # utility. INSIDE this transaction and AFTER every write above, so a
        # cut refused or rolled back queues nothing; in its own savepoint
        # (the seam's), so a message that cannot be queued never undoes the
        # cut. The figures are `reconnection_terms` read NOW — after the cut,
        # the fee inside the position — and the closing reading is the one this
        # same act just posted, read back WITH its unit (hard rule 3).
        unit_id = getattr(account, "unit_id", None)
        payload["notification_queued"] = notifications_seam.queue_service_disconnected(
            case_id=case.id,
            account_id=account_id,
            cut_on=cut_on,
            terms=reconnection_terms(account_id, case=case),
            closing_reads=seams.reads_for_unit(unit_id) if unit_id is not None else None,
            currency=case.currency,
            actor=actor,
        )
        _audit(actor, AUDIT_CUT_COMMITTED, account_id, after=payload)
    return payload


def cut_is_unfinished(case: DisconnectCase, account: Any) -> bool:
    """Was this cut's final bill HELD — is the ruled event half-done? (`DEF-CUS-6063`)

    ONE fact, read from the two rows that carry it, so a screen, an API and the
    service cannot answer it three different ways.

    A cut is UNFINISHED when the supply is off and the account never took
    BR-CUS-107's status. `commit_cut` writes that status only when billing
    raised the days before the cut (`CUT_BILL_BLOCKED_SO_STATUS_HELD`), so an
    account still on its old status after a cut is, by construction, an account
    whose final bill was refused.

    ⚠ **THE ACCOUNT'S CURRENT STATUS DECIDES IT, NOT `status_before_cut`.** That
    column is the code to RESTORE to and is NULL both when the status was held
    and on every case cut before the ruling of 2026-08-30 — one column, two
    meanings, and only one of them is this question. The status a cut wrote is
    the thing a later restoration, a later close or a hand edit can move, so it
    is read fresh every time and never cached on the case.
    """
    if case.state != STATE_CUT or case.cut_on is None:
        return False
    code = getattr(getattr(account, "status", None), "code", None)
    return str(code or "").strip().lower() != CUT_STATUS_CODE


#: ✅ **THE WAY OUT OF `CUT_BILL_BLOCKED_SO_STATUS_HELD` (`DEF-CUS-6063`).** The
#: held branch has existed since 2026-08-30 and nothing could ever leave it:
#: `commit_cut` refuses a second cut BY NAME, `_write_disconnected_status` was
#: called from `commit_cut` and from nowhere else, and no run, job or screen
#: revisited the case. So a cut that billing refused left the supply off, the
#: $75.00 fee raised and the account on its OLD status for ever.
#:
#: **THIS IS NOT A NEW RULE AND NOTHING HERE WAS DECIDED.** It is the second
#: half of the PO's ruling of 2026-08-30 — *"entire workflow including all
#: settlement and status update is taken care at time of disconnect"* — reached
#: on the day the configuration billing named is fixed. Every condition
#: `commit_cut` applies still applies, in `commit_cut`'s own words, and the
#: safety rule is untouched: **`Disconnected` is written only when the days up
#: to the cut are billed, or provably have nothing left to bill.**
CUT_FINISHED_LATE: dict[str, Any] = {
    "code": "cut_finished_after_the_bill_was_fixed",
    "br_ref": "BR-CUS-107 · BR-CUS-103 · PO ruling 2026-08-30 · `DEF-CUS-6063`",
    "detail": "the final bill billing refused at the cut has now been raised, so BR-CUS-107's "
    "`Disconnected` status is written and the account leaves the bill run with nothing left "
    "unbilled. The CUT itself is untouched — its date, its services, its reconnection fee and "
    "its record are exactly as they were recorded on the day. `DSC-02.4` is untouched too: no "
    "close, no deposit settlement, no write-off, and any remainder stays outstanding on an open "
    "account.",
}

#: ⛔ **AND THE ANSWER WHEN IT IS STILL REFUSED.** Nothing is written, the case
#: does not move, and the engine's own sentence travels back to the screen so
#: the person who can fix the data is told what to fix.
#:
#: ⚠ **AMENDED 2026-09-21 — THIS IS NOW A CHOICE AND NO LONGER A DEAD END.**
#: PO ruling 1 of 2026-09-21: *"in single bill we have final bill workflow - so
#: if clark want to complete the bill he can do it from there - we will need to
#: allow clark to complete the cut request later without bill."* So a clerk who
#: cannot fix the configuration today may complete the cut request with NO BILL
#: (`finish_cut(..., without_bill=True)`) and raise the bill afterwards from
#: billing's own single-bill workflow. The refusal below is what a clerk gets
#: when they asked for the bill and billing refused it; it stops being the only
#: thing that can happen.
CUT_STILL_BLOCKED: dict[str, Any] = {
    "code": "cut_bill_still_blocked_status_not_written",
    "br_ref": "BR-CUS-107 · BR-CUS-103 · BR-BIL-015 · PO ruling 2026-08-30 · PO ruling "
    "2026-09-21",
    "detail": "billing still cannot raise the final bill for the days before this cut, so "
    "nothing was written and the account stays in the bill run. The engine's own sentence "
    "travels on `cut_bill.detail` and names what to fix. This is no longer the only way out: "
    "PO ruling 2026-09-21 allows the cut request to be COMPLETED with no bill at all, and the "
    "final bill to be raised afterwards from billing's own single-bill workflow. The days that "
    "were never billed then travel on `days_not_billed` rather than disappearing.",
}

#: ✅ **COMPLETING THE CUT REQUEST WITH NO BILL — PO RULING 2026-09-21.**
#: Verbatim: *"in single bill we have final bill workflow - so if clark want to
#: complete the bill he can do it from there - we will need to allow clark to
#: complete the cut request later without bill."*
#:
#: ⛔ **IT REVERSES A REFUSAL THIS PRODUCT SHIPPED THE DAY BEFORE**, and the
#: supersession is stated rather than assumed (`13-change-process.md` step 2).
#: `commit_cut` writes the status only when the days are billed, and
#: `finish_cut` — built 2026-09-20 under `DEF-CUS-6063` — kept that refusal.
#: **The reasoning was OURS, not the PO's**: *writing the status drops the
#: account out of the bill run with days still unbilled.* The PO's answer is
#: that the days are not the CUT's to bill. **Completing a cut and raising a
#: final bill are two acts.**
#:
#: ⚠ **WHAT IS NOT LOST, AND A LANE MAY NOT QUIETLY DROP IT.** The reason the
#: status was held is real — a `disconnected` account leaves
#: `selectors.accounts_for_bill_run`. So the unbilled days do not stop
#: mattering: they travel on `days_not_billed` here, on the record payload and
#: into `audit_log`, and `unbilled_days_at_cut` re-derives them on every read so
#: the statement CLOSES ITSELF the day billing raises the bill.
CUT_COMPLETED_WITHOUT_BILL: dict[str, Any] = {
    "code": "cut_completed_without_a_final_bill",
    "br_ref": "BR-CUS-107 · BR-CUS-103 · PO ruling 2026-09-21 (supersedes the refusal built "
    "2026-09-20 under `DEF-CUS-6063`)",
    "detail": "the cut request is completed and BR-CUS-107's `Disconnected` status is written "
    "WITHOUT a final bill, on the PO's ruling of 2026-09-21 that completing a cut and raising "
    "its final bill are two acts. No bill was asked for and none was raised. The account leaves "
    "the bill run, so the days it was never billed for are stated on `days_not_billed` and are "
    "raised from billing's own single-bill workflow. The CUT itself is untouched — its date, "
    "its services, its reconnection fee and its record stand as recorded on the day — and "
    "`DSC-02.4` is untouched: no close, no deposit settlement, no write-off.",
}

#: ⚠ **THE DAYS NOBODY HAS BILLED, STATED RATHER THAN LEFT SILENT.** It rides
#: every completion that raised no bill, and every record of a cut whose days
#: are still unbilled. **It is DERIVED on each read** (see
#: `unbilled_days_at_cut`), so it disappears by itself the moment a bill covers
#: the cut day — a stored flag would go on saying *unbilled* after the bill
#: landed, which is hard-won law 1's shape.
CUT_DAYS_NOT_BILLED: dict[str, Any] = {
    "code": "days_before_the_cut_are_not_billed",
    "br_ref": "BR-CUS-103 · BR-BIL-004 · PO ruling 2026-09-21",
    "detail": "these days were never billed and this account has left the bill run, so no "
    "ordinary run will pick them up. Raise them from billing's single-bill workflow. The window "
    "is derived from the last issued bill that covered service and the cut date, so this "
    "statement disappears on its own once that bill exists.",
}

#: ⛔ **AND WHEN BILLING CANNOT BE ASKED AT ALL.** A seam that resolves to
#: nothing answers `None`, which is indistinguishable from *nothing is unbilled*
#: — DEF-035's exact shape, where a missing seam let a guard silently permit
#: what it was written to refuse. Reported rather than read as a clean slate.
CUT_UNBILLED_DAYS_UNREADABLE: dict[str, Any] = {
    "code": "unbilled_days_not_readable",
    "br_ref": "BR-CUS-103 · PO ruling 2026-09-21 · DEF-035",
    "detail": "billing's `unbilled_service_window` selector is not published in this process, "
    "so whether any day before the cut is unbilled could not be established. This is NOT a "
    "statement that nothing is outstanding: it is the absence of an answer, and it is reported "
    "rather than rendered as silence.",
}

AUDIT_CUT_FINISHED = "disconnect.cut.finished"


def unbilled_days_at_cut(case: DisconnectCase) -> dict[str, Any] | None:
    """The days before this cut that NOBODY has billed — or `None`.

    **PO ruling 2026-09-21's other half.** A cut may now be completed with no
    bill, and a `disconnected` account leaves `accounts_for_bill_run`, so the
    days it was never billed for would simply stop being anywhere. They are
    here instead, and on every surface that reads this.

    ⚠ **DERIVED, NEVER STORED, AND THAT IS THE POINT.** Billing is asked the
    same question it asks at the cut, so the answer tracks reality: once the
    single-bill workflow raises the bill, `first_unbilled_day` moves past
    `cut_on` and this returns `None` on the next read, with nobody clearing a
    flag. A column written at completion would say *unbilled* for ever.

    ⚠ **`None` IS NOT ONE ANSWER, WHICH IS WHY THE UNREADABLE CASE IS TAGGED.**
    Billing answering *nothing is unbilled* and billing not answering at all
    both arrive as `None` through the seam, and only the first is good news.
    `billing_selectors_answer()` tells them apart, and the second comes back as
    `CUT_UNBILLED_DAYS_UNREADABLE` rather than as silence.

    Returns the window plus `CUT_DAYS_NOT_BILLED`'s sentence, so a caller
    states one fact and never has to assemble two.
    """
    if case is None or case.cut_on is None:
        return None
    window = seams.unbilled_service_window(case.account_id, through=case.cut_on)
    if window is None:
        if seams.billing_selectors_answer():
            return None
        return dict(CUT_UNBILLED_DAYS_UNREADABLE)
    stated = dict(CUT_DAYS_NOT_BILLED)
    stated.update(
        {
            "from": window["start"],
            "to": window["end"],
            "days": window["days"],
        }
    )
    return stated


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-039")
def finish_cut(
    actor: Any, account_id: Any, *, as_of: date, without_bill: bool = False
) -> dict[str, Any]:
    """COMPLETE the cut request — with the final bill, or (2026-09-21) without one.

    **`DEF-CUS-6063`.** The cut happened; billing refused the days before it;
    `commit_cut` therefore declined to write `Disconnected` and there was no
    second attempt anywhere in the product. This is that attempt.

    ⚠ **AND SINCE 2026-09-21 IT HAS TWO DOORS, BECAUSE THE PO REMOVED THE
    REFUSAL.** Verbatim: *"in single bill we have final bill workflow - so if
    clark want to complete the bill he can do it from there - we will need to
    allow clark to complete the cut request later without bill."* **Completing
    a cut and raising a final bill are two acts.** `without_bill=True` is the
    clerk saying so: the status is written, no bill is asked for and none is
    raised. The default is unchanged — ask billing, and if billing refuses,
    write nothing and hand back the engine's sentence. **The hold stays
    available; it stops being compulsory.**

    **WHAT IT DOES**, and the order is `commit_cut`'s own for `commit_cut`'s own
    reason — billing's stage 1 refuses to price an account that is not billable,
    so the bill comes before the word:

      1. **THE FINAL METERED BILL**, for the account's first unbilled day
         through `cut_on` inclusive, through billing's own door
         (`seams.raise_and_issue_cut_bill`) because customers may not write an
         invoice (BR-CUS-037, rule 5). The window is DERIVED from the case's
         recorded `cut_on` — never from today, never from a caller.
         ⛔ **SKIPPED ENTIRELY WHEN `without_bill` IS SET**, and skipped rather
         than attempted-and-ignored: a clerk who asked to complete WITHOUT a
         bill has not asked to be billed, and a bill that happened to succeed
         would be a money act nobody requested.
      2. **THE STATUS** — BR-CUS-107's `Disconnected`, and the code the account
         held before it, recorded on the case as history (a restoration writes
         Active since 2026-10-29, `DEF-CUS-10668`). Written when step 1 billed
         the days, when it proved there were
         none, **or when the clerk completed the request without a bill**.
      3. **THE SETTLEMENT** — read the position, write nothing off. The figure
         `outstanding_at_cut` recorded before the final bill existed is
         superseded by the one that includes it, and the audit row carries both.

    ⚠ **THE DAYS NOBODY BILLED DO NOT DISAPPEAR, AND THAT IS PART OF THE
    RULING RATHER THAN A KINDNESS.** The reason the status was held is real: a
    `disconnected` account leaves `selectors.accounts_for_bill_run`, so no
    ordinary run will ever pick those days up. The PO ruled who raises the
    bill, not that the days stop mattering — so every completion that raised no
    bill carries `days_not_billed` (`unbilled_days_at_cut`), the record screen
    states it, and `audit_log` keeps it. It is DERIVED on each read and so
    closes itself the day billing's single-bill workflow raises the bill.

    ⛔ **WHAT IT MUST NOT DO.** It does not cut anything, re-date anything,
    re-quote the reconnection fee or touch the case's services, notices or
    proof. A cut is recorded ONCE (`commit_cut`'s `already_cut` refusal and the
    regulator's record behind it) and this call does not re-record it: `state`,
    `cut_on`, `reconnection_fee_amount` and `reconnection_fee_code` are not in
    its `update_fields`. It does not close the account or settle a deposit —
    `DSC-02.4`, untouched.

    ⚠ **IT IS IDEMPOTENT BY REFUSAL, NOT BY REPLAY.** A cut that already carries
    the status is refused by name rather than re-billed: `raise_and_issue_cut_bill`
    would answer `already_billed` on BR-BIL-005's key, and a caller reading that
    as success would re-settle a figure for no reason.

    ⚠ **NO LADDER CHECK, DELIBERATELY.** `_require_running` asks *may this
    account still be cut* — whether it paid, whether a plan is running, whether a
    protection is live. That question belongs to an act that TAKES the supply
    away and this act does not: the supply is already off, and refusing to bill
    the days a customer used because they have since paid would leave those days
    billed by nobody, which is the whole of `OQ-1170`. A customer who has paid
    is restored through `restore_service`, which is a different door.

    `as_of` is the day the clerk is standing on and is recorded on the audit row.
    It is NOT the bill's date: BR-TEN-043 and G6 forbid a clock on a money path,
    and the window comes from `cut_on`.
    """
    case = open_case_for(account_id)
    if case is None:
        raise DisconnectRuleError(
            "there is no open disconnect case on this account, so there is no cut to finish.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    if case.state != STATE_CUT or case.cut_on is None:
        raise DisconnectRuleError(
            f"this case is {case.state!r} and no cut has been recorded on it. Only a cut that "
            "HAPPENED can be finished: this act raises the bill for the days before a cut and "
            "writes the status that cut should have written, and neither exists until the "
            "supply is actually off.",
            code="no_cut_to_finish",
            br_ref="BR-CUS-107",
        )
    account = _account(account_id)
    if not cut_is_unfinished(case, account):
        raise DisconnectRuleError(
            f"this cut is already finished — the account carries the {CUT_STATUS_CODE!r} status "
            f"that was written when it was cut on {case.cut_on}. Finishing it again would ask "
            "billing for a window it has already billed and re-state a settlement nobody "
            "changed.",
            code="cut_already_finished",
            br_ref="BR-CUS-107",
        )

    with transaction.atomic():
        # ⚠ **THE UNBILLED DAYS ARE READ BEFORE ANYTHING IS WRITTEN**, because
        # after step 1 has raised the bill the honest answer is *none* and the
        # fact a clerk needs on a completion WITHOUT a bill would be gone.
        days_not_billed = unbilled_days_at_cut(case)
        # PO ruling 2026-09-21 — completing the cut request and raising its
        # final bill are TWO ACTS, so the bill is skipped rather than attempted
        # when the clerk asked to complete without one. `cut_bill` is None on
        # that path and the payload says so by naming the ruling.
        cut_bill = (
            None if without_bill else _raise_final_bill_at_the_cut(actor, account, cut_on=case.cut_on)
        )
        payload: dict[str, Any] = {
            "case_id": str(case.id),
            "case_no": case.case_no,
            "account_id": str(account_id),
            "cut_on": str(case.cut_on),
            "finished_on": str(as_of),
            "cut_bill": None if cut_bill is None else cut_bill.as_payload(),
            "billed": False if cut_bill is None else cut_bill.billed,
        }
        if cut_bill is not None and not cut_bill.billed:
            # The clerk ASKED for the bill and billing refused it. Nothing is
            # written, the account keeps its billable status and stays in the
            # run, and the engine's sentence goes back to the screen.
            # ⚠ Since 2026-09-21 this is a CHOICE and not a dead end: the same
            # door with `without_bill=True` completes the request anyway, and
            # `CUT_STILL_BLOCKED` names that way out.
            payload["account_status_written"] = None
            payload["account_status_held"] = dict(CUT_STILL_BLOCKED)
            payload["days_not_billed"] = days_not_billed
            payload["finished"] = False
            return payload

        outstanding_before = case.outstanding_at_cut
        status_before, status_after = _write_disconnected_status(account)
        case.status_before_cut = status_before
        outstanding = _settle_at_the_cut(account_id)
        case.outstanding_at_cut = outstanding
        case.save(
            update_fields=["status_before_cut", "outstanding_at_cut", "updated_at"]
        )
        payload["finished"] = True
        payload["account_status_written"] = status_after
        payload["account_status_before_cut"] = status_before
        payload["completed"] = dict(
            CUT_COMPLETED_WITHOUT_BILL if without_bill else CUT_FINISHED_LATE
        )
        # ⚠ **THE DAYS NOBODY BILLED, ON THE COMPLETION THAT DID NOT BILL
        # THEM** (PO ruling 2026-09-21). Read BEFORE the bill was raised, so on
        # the billing path it states what the bill has just covered and on the
        # without-bill path it states what nobody has. `None` on either path is
        # the honest *there were none*.
        payload["days_not_billed"] = None if not without_bill else days_not_billed
        payload["settlement"] = {
            "outstanding": None if outstanding is None else _money(outstanding),
            "outstanding_recorded_at_the_cut": (
                None if outstanding_before is None else _money(Decimal(str(outstanding_before)))
            ),
            "currency": case.currency,
            "written_off": None,
            "account_closed": False,
            "deposit_settled": False,
            "br_ref": "`DSC-02.4` · PO ruling 2026-08-30",
            "detail": "the position is re-read and nothing is moved: no write-off, no deposit, "
            "no close. `outstanding_at_cut` is superseded by the figure read now, and both "
            "travel on this record."
            + (
                " No final bill was raised, so this figure does not include one — PO ruling "
                "2026-09-21, and `days_not_billed` states the days it would have covered."
                if without_bill
                else " That figure includes the bill the cut could not raise."
            ),
        }
        # CLAUDE.md rule 7 — the act that moved a customer's account out of the
        # bill run, and (on the without-bill path) the days it left behind.
        _audit(actor, AUDIT_CUT_FINISHED, account_id, after=payload)
    return payload


# ════════════════════════════════════════════════════════════════════════════
# BR-CUS-103 — THE ONE FACT BILLING LEARNS FROM THIS MODULE
# ════════════════════════════════════════════════════════════════════════════
#: **PO ruling 2026-08-25, closing OQ-380.** Asked in plain English with a
#: figure — *"when a service is cut, does the base charge keep running?"*, with
#: `A-11488`, cut 2026-08-18 owing **$612.75** — the PO answered **"no"**.
#:
#: ⚠ **DEF-707 IS WHY THIS READ EXISTS AND WHY IT IS A READ.** `commit_cut`
#: correctly never writes `accounts` (`DSC-02.4`'s three prohibitions), so
#: nothing ever told billing the service stopped and base ran on **because
#: nothing was written to stop it** — an omission, never a decision. The fix
#: keeps that prohibition intact: customers writes nothing new anywhere, and
#: billing ASKS. `apps/billing/gather.py` resolves this by name through the
#: seam idiom it already uses for `apps.customers.selectors.account_detail`.
#:
#: ⚠ **AND THERE IS DELIBERATELY NO `SERVICE_OFF_STATES` TUPLE HERE.** The
#: obvious shape is a list of states that mean "off" (`cut`, `reconnecting`),
#: and it is the wrong one: `restored` and `stopped` cases also hold a `cut_on`
#: and a month they darkened, and a state list would drop them silently. The
#: read is keyed on the two DATES, which are the facts, and a constant nothing
#: reads is dead code by hard-won law 2 — so it is not written.

#: ⚠ **THE BOUNDARY IS THE CUT DATE AND THE CUT DAY IS STILL BILLED.**
#: BR-CUS-103, verbatim: *"The boundary is the cut date, not the notice date —
#: a service is billed base right up to the moment it is cut, because until
#: then it was available."* So the first day with NO service is the day AFTER
#: `cut_on`, which is the same inclusive convention `gather._service_days`
#: already applies to `accounts.closed_at` on a move-out. **The offset is the
#: `+ timedelta(days=1)` in the function below and it lives HERE, in the module
#: that owns the cut** — billing subtracts days and decides nothing about what a
#: cut means. It is not lifted into a named constant: a constant would need an
#: `else` branch no test exercises, to express a boundary the PO ruled once.


def service_off_windows(account_id: Any) -> tuple[dict[str, Any], ...]:
    """The date ranges this account had NO service, and which services (BR-CUS-103).

    HUMAN-REVIEW-PENDING — a 🔒 money path: what this returns decides how much
    base charge a customer pays. A row in `12-governance/09-human-review-ledger
    .md` is OWED; this lane does not own that file and reports the row.

    One dict per case that ever reached a cut — `cut_on` is not NULL — newest
    first, whatever state the case is in now. A RESTORED case is included
    because a bill run over the month the service came back still has to know
    which of its days were dark, and `open_case_for` deliberately excludes
    restored cases. Nothing here is derived from `state`: `cut_on` and
    `reconnected_on` are the two facts, and reading the dates rather than the
    state means a case stopped by hand after a cut cannot silently lose its
    window.

    Each dict:

      * `off_from` — the FIRST day with no service, `cut_on + 1`. The cut DAY
        is served and is billed — see the comment above this function.
      * `off_through` — the LAST day with no service, `reconnected_on - 1`, or
        **None while the service is still off**. None is an open end, never a
        zero-length window.
      * `cut_on` / `restored_on` — the raw recorded dates, so a caller that
        needs the event rather than the window is not made to re-derive it.
      * `services` — the service CODES that were cut (`DSC-02.1`'s *"One
        decision per service, not all or nothing"*). A restrictor never appears:
        `assert_treatments_expressible` refuses it before a cut is scheduled.

    ⚠ **IT ANSWERS `()` FOR AN ACCOUNT THAT WAS NEVER CUT, AND THAT IS NOT AN
    ABSENCE.** Every account in the product is in that state; a caller reading
    `()` as "unknown" would refuse every ordinary bill.

    ⚠ **AND IT SAYS NOTHING ABOUT THE RECONNECTION FEE, WHICH SINCE 2026-08-27
    IS A REAL RECEIVABLE (`FEE_POSTED`, DEF-708 fixed).** This read answers
    DARK DAYS, so that billing can stop the base charge (BR-CUS-103); the fee is
    a separate charge on its own `fee` bill and is nowhere in this answer. A
    caller must not read a window from here as "everything the cut did to this
    customer's money" — and must not subtract the fee from a base charge either.
    """
    rows = (
        DisconnectCase.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, cut_on__isnull=False
        )
        .order_by("-cut_on", "-created_at")
        .values("id", "state", "cut_on", "reconnected_on", "services_cut")
    )
    return off_windows_from(rows)


def off_windows_from(rows: Any) -> tuple[dict[str, Any], ...]:
    """`service_off_windows`' reading of its rows (newest cut first) — shared
    with the bulk Check's batch read (`selectors.prime_check_batch`, B27) so
    the two cannot drift."""
    windows: list[dict[str, Any]] = []
    for row in rows:
        cut_on = row["cut_on"]
        restored_on = row["reconnected_on"]
        off_from = cut_on + timedelta(days=1)
        off_through = None if restored_on is None else restored_on - timedelta(days=1)
        if off_through is not None and off_through < off_from:
            # Cut and restored on the same day, or the day after: the service
            # was never dark for a whole day, so there is no window and none is
            # invented. A zero-length window that subtracted a day would bill
            # LESS than the customer owes for a service they kept.
            continue
        windows.append(
            {
                "case_id": str(row["id"]),
                "state": row["state"],
                "cut_on": cut_on,
                "restored_on": restored_on,
                "off_from": off_from,
                "off_through": off_through,
                "services": tuple(row["services_cut"] or ()),
                "br_ref": "BR-CUS-103",
            }
        )
    return tuple(windows)


def new_service_block_for(account_id: Any) -> dict[str, Any]:
    """`DSC-02.4` — *"blocks new service elsewhere until it is settled"*.

    THE STATE IS BUILT AND NOTHING CONSUMES IT (`NEW_SERVICE_BLOCK_UNCONSUMED`,
    hard-won law 2). Move-in does not call this; B18 §5.8.7 says so of itself
    and it is still true, measured on this tree 2026-08-25.

    ⚠ **`blocked` IS THREE-VALUED AND `None` IS NOT `False`.** *"Until it is
    settled"* is a statement about a BALANCE, and `_balance_for` answers `None`
    when AR cannot be read — which is not zero and is not a clearance
    (DEF-127/DEF-628). A consumer that reads `None` as "not blocked" would let a
    household take service elsewhere on a reading that failed, so the reason
    travels with the answer and the caller must handle it.

    ⚠ **AND IT NAMES NO PARTY BUT THE ACCOUNT.** *"Elsewhere"* means another
    premises, and whether the block follows the account, the customer record or
    the person named on it is stated by no rule — the same unresolved-subject
    shape BR-CUS-097 has for who is chased.
    """
    case = open_case_for(account_id)
    if case is None or case.state != STATE_CUT:
        return {
            "account_id": str(account_id),
            "blocked": False,
            "reason": (
                "no account of this tenant is cut and unsettled at this id."
                if case is None
                else f"this case is {case.state!r}, not `cut`."
            ),
            "absence": dict(NEW_SERVICE_BLOCK_UNCONSUMED),
        }
    balance = _balance_for(account_id)
    if balance is None:
        return {
            "account_id": str(account_id),
            "blocked": None,
            "reason": "this account is CUT and what it owes could not be read from the ledger, so "
            "whether it is settled cannot be answered. A reading that failed is not a settlement "
            "and must not be read as one.",
            "absence": dict(NEW_SERVICE_BLOCK_UNCONSUMED),
        }
    return {
        "account_id": str(account_id),
        "blocked": balance > ZERO,
        "balance": _money(balance),
        "reason": (
            "this account is CUT and still owes money, so `DSC-02.4`'s block stands "
            "until it is settled."
            if balance > ZERO
            else "this account is CUT and owes nothing, so the block does not stand — what is "
            "outstanding is the visit, not the money."
        ),
        "absence": dict(NEW_SERVICE_BLOCK_UNCONSUMED),
    }


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.9 — THE PATH BACK: CUT → RECONNECTING → RESTORED
# ════════════════════════════════════════════════════════════════════════════
#: `disconnect_record.ACTION_MARK_RECONNECTING` — the first step back.
STEP_MARK_RECONNECTING = "mark_reconnecting"
#: `disconnect_record.ACTION_RESTORE_SERVICE` — the last rung.
STEP_RESTORE_SERVICE = "restore_service"


def _refusal(code: str, br_ref: str, detail: str) -> dict[str, Any]:
    """One refusal, as a dict rather than an exception.

    The three fields `DisconnectRuleError` carries, in the shape
    `disconnect_record.cut_readiness` already collects — so a screen greying a
    button and a service refusing a call quote the SAME sentence.
    """
    return {"code": code, "br_ref": br_ref, "detail": detail}


def reconnect_blockers(
    case: DisconnectCase, *, balance: Decimal | None
) -> tuple[dict[str, Any], ...]:
    """Every reason `mark_reconnecting` would refuse, in its order, READ-ONLY.

    ⚠ **THE SENTENCES LIVE HERE AND THE WRITER CALLS THEM** — the opposite
    direction from `cut_readiness`, which catches the writer's exceptions,
    and the same guarantee: one set of words. `mark_reconnecting` raises the
    FIRST of these; a screen is answering *what would I have to do* and gets
    all of them, because a clerk told one thing at a time makes three trips.

    ⚠ **IT IS A PREVIEW, NOT A GATE.** `mark_reconnecting` re-runs it inside
    its own call, because days pass between a screen being drawn and a button
    being pressed.
    """
    blockers: list[dict[str, Any]] = []
    if case.state != STATE_CUT:
        blockers.append(
            _refusal(
                "not_cut",
                "B18 §5.8.3",
                f"this case is {case.state!r}, and only a CUT account is reconnected. §5.8.3 "
                "draws `RECONNECTING` between `CUT` and `restored`; a case that was never cut "
                "has nothing to restore and a case already reconnecting is waiting for a visit, "
                "not for this call.",
            )
        )
    if balance is None:
        blockers.append(
            _refusal(
                HALT_BALANCE_UNREADABLE,
                "BR-PAY-032",
                "what this account owes could not be read from the ledger, so it cannot be "
                "recorded as paid. §5.8.1's caption for this state is *'paid, awaiting a "
                "visit'*, and moving a case there on a reading that failed would put that "
                "sentence on the screen with nothing behind it. The account is not stuck — the "
                "reading is, and it is reported.",
            )
        )
    return tuple(blockers)


#: `BR-CUS-1097` — what the clerk is SHOWN where they used to be STOPPED.
#: Not a blocker and never again a blocker: the PO chose option (a) of two on
#: 2026-09-25 — *"Show what's still owed and let the clerk proceed"* — and
#: declined every friction offered beside it (no typed reason, no tick, no
#: supervisor), twice that day, here and on `BR-CUS-1096`.
RECONNECT_MONEY_STILL_OWED = "money_still_owed"

#: ⚠ **THE HALF OF `BR-CUS-1097` THIS PRODUCT CANNOT YET ANSWER, STATED RATHER
#: THAN GUESSED.** The rule requires the record to capture **what had been
#: PAID** against the arrears as well as what was still owed. Nothing on the
#: disconnect path reads that: `_balance_for` answers the ledger receivable and
#: **`DEF-PAY-6074` is the open row** for the second number — an account's CREDIT
#: POSITION, which `apps/billing/payments_seam.credit_position_for_account`
#: already publishes one module over and which this module has never asked for.
#: A figure invented here would be a second, wrong answer to a question billing
#: answers exactly (`BR-BIL-160`).
PAID_AGAINST_ARREARS_NOT_READ: dict[str, Any] = {
    "code": "paid_against_arrears_not_read",
    "br_ref": "BR-CUS-1097 · DEF-PAY-6074",
    "detail": (
        "what has been paid against these arrears is not read on the disconnect path. "
        "`BR-CUS-1097` asks the record to carry it beside what is still owed; the read that "
        "would answer it is billing's credit position (`BR-BIL-160`), which this module does "
        "not ask for. It is `DEF-PAY-6074` and it is open. Nothing here computes a substitute."
    ),
}


def reconnect_warnings(
    case: DisconnectCase, *, balance: Decimal | None
) -> tuple[dict[str, Any], ...]:
    """`BR-CUS-1097` — what a clerk is TOLD before restoring, having not been stopped.

    ⛔ **THIS WAS A REFUSAL UNTIL 2026-09-25 AND IS NOT ONE NOW (`DEF-CUS-6735`
    CLOSED).** `BR-CUS-1097`, PO ruling of that day, verbatim, choosing option
    (a) of two: *"Show what's still owed and let the clerk proceed"*. The worked
    case is the one put to the PO: **Brett Calloway owes $1,204.50 plus the
    reconnection fee, pays $400.00, agrees a plan for the rest, and the clerk
    restores water the same day.** Under the old `not_settled` blocker he was
    refused; he is not refused now.

    ⚠ **IT SUPERSEDES HALF OF `BR-CUS-104` AND THE SUPERSESSION IS STATED
    (hard-won law 13).** The fee's TIMING is untouched — it still lands at the
    cut, it is still a real receivable, and `A-11340`'s position is still
    **$8,315.00**. What is gone is the GATE. **$8,315.00 is now what the clerk
    is SHOWN, not what they must collect first.**

    ⚠ **DO NOT RESTATE `DSC-02.4`'s *"until it is settled"* AS CURRENT LAW
    ANYWHERE.** That drawn line went to the PO under B14 rule 41 and this ruling
    is the answer.

    ⚠ **NONE OF THIS REASONING REACHES A SCREEN** (B14 rule 33).
    """
    if balance is None or balance <= ZERO:
        return ()
    return (
        _refusal(
            RECONNECT_MONEY_STILL_OWED,
            "BR-CUS-1097",
            f"this account still owes {_money(balance)['display']} and service may be restored "
            "anyway (PO 2026-09-25: *'Show what's still owed and let the clerk proceed'*). "
            "✅ THE RECONNECTION FEE IS ALREADY INSIDE THIS FIGURE AND IS NOT ADDED TO IT "
            "(DEF-708, PO 2026-08-27; `DEF-CUS-6050`): the cut raised and issued it as a "
            "real charge, so this position IS the arrears plus the fee — BR-CUS-104's "
            "$8,315.00 on `A-11340`, not $8,240.00 and not $8,390.00. It is the same "
            "figure `reconnection_terms` quotes as `to_clear`, read once from the same "
            "place, so the amount a clerk states and the amount that admits the customer "
            "back cannot differ.",
        ),
    )


def restored_status_row(tenant_id: Any) -> Any:
    """The status a restoration writes — Active, by its seeded CODE (`DEF-CUS-10668`).

    One read for `restore_service` and `reconnection_readiness`, so the screen
    and the write cannot disagree. `None` only when the tenant has no live
    `active` row; see `RESTORED_STATUS_NOT_RECORDED`.
    """
    from apps.customers import models as customers_models

    return customers_models.AccountStatus.objects.filter(
        tenant_id=tenant_id, code__iexact=RESTORED_STATUS_CODE, active=True
    ).first()


def restore_blockers(case: DisconnectCase) -> tuple[dict[str, Any], ...]:
    """Every reason `restore_service` would refuse. One, and it is the middle state."""
    if case.state == STATE_RECONNECTING:
        return ()
    return (
        _refusal(
            "not_reconnecting",
            "B18 §5.8.4",
            f"this case is {case.state!r}. §5.8.4's reconnect flow is *'payment confirmed → "
            "visit scheduled → restored'*, so a case reaches `restored` through `RECONNECTING` "
            "and not around it. Record the settlement first — restoring an account that never "
            "settled states on the record that it paid.",
        ),
    )


def reconnection_readiness(
    account_id: Any, *, case: DisconnectCase | None = None
) -> dict[str, Any]:
    """Which step back this case is on, whether it can be taken, and why not.

    ⚠ **BUILT 2026-09-20, AND THE REASON IT DID NOT EXIST IS THE POINT.** PO,
    verbatim: *"The other half of the job. Today a utility can cut supply and
    cannot restore it from the product."* `mark_reconnecting` and
    `restore_service` were both written on 2026-08-25, both role-gated, both
    tested and both reachable **only from Python** — two of the six disconnect
    write paths with no door (hard-won law 2 read from the engine end). A screen
    cannot offer a step it cannot ask about, so this read is the first half of
    giving them one.

    `step` is what the case's own state admits and never what a caller asks
    for: a `cut` case is on `mark_reconnecting`, a `reconnecting` case is on
    `restore_service`, and anything else is on `mark_reconnecting` **with the
    `not_cut` refusal already in `blockers`** — which is the honest answer to
    *may I reconnect this* on a case nobody has cut.
    """
    case = case if case is not None else open_case_for(account_id)
    if case is None:
        return {
            "step": None,
            "ready": False,
            "refusal": _refusal(
                "no_open_case",
                "BR-CUS-039",
                "there is no open disconnect case on this account to reconnect.",
            ),
            "blockers": (),
            "warnings": (),
            "paid_absence": dict(PAID_AGAINST_ARREARS_NOT_READ),
            "balance": None,
        }
    if case.state == STATE_RECONNECTING:
        blockers = restore_blockers(case)
        warnings: tuple[dict[str, Any], ...] = ()
        step = STEP_RESTORE_SERVICE
        balance = None
    else:
        balance = _balance_for(account_id)
        blockers = reconnect_blockers(case, balance=balance)
        # ⚠ **WARNINGS ARE NOT BLOCKERS AND `ready` DOES NOT READ THEM** —
        # `BR-CUS-1097`. A screen that greyed its button on a warning would be
        # the refusal restored under another name, which is precisely what the
        # PO declined.
        warnings = reconnect_warnings(case, balance=balance)
        step = STEP_MARK_RECONNECTING
    return {
        "step": step,
        "ready": not blockers,
        "refusal": blockers[0] if blockers else None,
        "blockers": blockers,
        "warnings": warnings,
        # `BR-CUS-1097`'s second figure, and the honest answer is that nobody
        # reads it here yet. Never `0` — see `DEF-PAY-6074`.
        "paid_absence": dict(PAID_AGAINST_ARREARS_NOT_READ),
        # The live figure the gate itself reads, so the screen and the refusal
        # cannot quote two numbers. `None` where the step does not read one or
        # where the books could not be asked — never `0`, which is what a
        # settled account reads (`DEF-127`).
        "balance": None if balance is None else _money(balance),
        # What the account held at the cut — HISTORY since 2026-10-29: it no
        # longer decides the restored status, which is Active (`DEF-CUS-10668`,
        # PO *"2A"*). `status_absence` answers whether `restore_service` CAN
        # write Active, read the way it will read it.
        "status_before_cut": case.status_before_cut or None,
        "status_restored_to": RESTORED_STATUS_CODE,
        "status_absence": (
            None
            if restored_status_row(case.tenant_id) is not None
            else dict(RESTORED_STATUS_NOT_RECORDED)
        ),
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-PAY-036")
def mark_reconnecting(
    actor: Any, account_id: Any, *, on_date: date, template_ids: Any = None
) -> dict[str, Any]:
    """§5.8.3's `RECONNECTING — paid, awaiting a visit`. An EXPLICIT staff act.

    §5.8.4: *"Reconnect is its own short flow: payment confirmed → visit
    scheduled → restored → the row leaves the tab."* This is the first step, and
    it is a step somebody takes.

    ⛔⛔ **READ THIS BEFORE THE FOUR PARAGRAPHS BELOW ABOUT `$8,315.00`: THE
    BALANCE IS NO LONGER A GATE — `BR-CUS-1097`, PO 2026-09-25, wired by lane
    CUTPATH the same day (`DEF-CUS-6735` CLOSED).** *"Show what's still owed and
    let the clerk proceed"*. **Brett Calloway owes $1,204.50 plus the fee, pays
    $400.00, agrees a plan, and water goes back on the same day.** Everything
    those paragraphs say about `A-11340`'s **$8,315.00** is still TRUE and is
    still the figure — what changed is that it is now what the clerk is SHOWN
    (`reconnect_warnings`) rather than what they must collect first. The
    `DEF-CUS-6050` requirement that the quote and this read be ONE read is
    UNTOUCHED and matters more, not less: a warning quoting a different number
    from the panel beside it is the same defect with no refusal to make it
    visible. The rejected fix below — folding `case.reconnection_fee_amount`
    into the comparison — stays rejected for its second reason, which was never
    about the gate.

    ⛔ **IT IS NOT AUTOMATIC ON PAYMENT, AND THAT IS BR-PAY-036.** *"A payment is
    ALWAYS accepted and acceptance NEVER auto-changes account status —
    restoration stays an explicit, audited staff action."* The LADDER stops
    itself the moment money posts (task 7.6, and `halt_reason`'s
    `HALT_NOTHING_OWED` says so in its own words); the METER does not turn
    itself back on. §5.8.6's `A-11507` is the drawn proof: **$0.00 owed, tier
    `—`, state `Reconnecting`** — a paid account still on the tab because a
    visit is due.

    ✅ **DEF-708 IS CLOSED AND THIS FUNCTION DID NOT CHANGE — that is the point.**
    BR-CUS-104 (PO 2026-08-25, closing OQ-381) rules that the reconnection fee
    lands AT THE CUT: *"does reconnection need $8,315.00 - this is correct"*.
    `A-11340` owes $8,240.00, the fee is $75.00, and $8,315.00 is what must be
    cleared. This gate has always read AR; what was missing was the fee being
    IN AR. `commit_cut` now raises and issues it as a real charge (PO ruling
    2026-08-27, *"Make the fee a real charge — It becomes a line that can be
    billed and paid, so the gate has something to check"*), so the comparison
    below is correct without a single new clause. See `FEE_POSTED`.

    ⚠ **AND THE REJECTED FIX IS RECORDED, BECAUSE IT IS THE OBVIOUS ONE AND
    SOMEBODY WILL REACH FOR IT AGAIN.** Adding `case.reconnection_fee_amount`
    to the comparison DEADLOCKS the product: the recorded fee is a fact about
    the case that nothing ever clears, so once AR reaches zero the comparison
    would still refuse — **forever, for every cut customer.** The PO rejected it
    for the other half too: it makes the gate *work* and leaves the money
    *uncollected*. Never fold the case's figure into a balance.

    ⚠ **AND THAT IS WHY THIS GATE AND THE QUOTED FIGURE MUST BE THE SAME READ —
    `DEF-CUS-6050`.** `_to_clear` quotes what a customer has to pay and this
    refuses them until it is paid, so the two disagreeing by one fee is a
    household told to pay $8,390.00 to clear a gate that opens at $8,315.00.
    After the cut BOTH are `_balance_for`, read once, with nothing added; the
    test that pins them together is
    `test_def_cus_6050_reconnection_figure.py::…the_gate_and_the_quote…`.

    ✅ **AND SINCE 2026-09-05 IT BOOKS THE VISIT — CR-070 wave P, `US-WRK-039`,
    `BR-WRK-055`.** §5.8.4's middle step (*"payment confirmed → visit scheduled →
    restored"*) has been a hole in this function since it was written, and
    `VISIT_NOT_SCHEDULED` named it honestly: `work_orders` was metering's table
    and there was no lawful way to ask. Work became a module on 2026-09-03 with
    a read-only seam per neighbour and one named write door, so now there is.
    `template_ids` is what the clerk ticked on the account's disconnect surface.

    ⚠ **THE VISIT DOES NOT GATE THE STATE, AND THE ORDER OF THE TWO ACTS SAYS
    SO.** The case moves to `RECONNECTING` and is audited FIRST; the job is
    raised after. `BR-WRK-055`: the flow completes whether or not the visit could
    be booked. A customer who has paid $8,315.00 is *paid, awaiting a visit* the
    moment a clerk says so — a field module able to hold them in `CUT` because a
    template was deactivated would be this product refusing to acknowledge money
    it has already taken.
    """
    case = open_case_for(account_id)
    if case is None:
        raise DisconnectRuleError(
            "there is no open disconnect case on this account to reconnect.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    balance = _balance_for(account_id)
    # ⚠ **THEY MOVED OUT OF THIS FUNCTION ON 2026-09-20 AND NOT ONE WORD OF THEM
    # CHANGED — THERE WERE THREE AND THERE ARE TWO** (`BR-CUS-1097` withdrew
    # `not_settled` on 2026-09-25). `reconnect_blockers` holds them so the screen
    # that greys the button quotes the sentence this call would have raised —
    # a paraphrase on a screen is a second answer to a question the writer
    # already answers, and it drifts the moment either side is edited. This
    # raises the FIRST; the screen reads all of them.
    blockers = reconnect_blockers(case, balance=balance)
    if blockers:
        first = blockers[0]
        raise DisconnectRuleError(
            str(first["detail"]), code=str(first["code"]), br_ref=str(first["br_ref"])
        )
    # ── `BR-CUS-1097` · WITH NOTHING BLOCKING, THE RECORD IS THE ONLY
    #    PROTECTION THERE IS ───────────────────────────────────────────────
    # PO ruling 2026-09-25, and this half is as much the rule as the half that
    # stopped refusing: *"At reconnect the product captures, itself, without
    # asking the clerk for anything: what was still owed at the moment service
    # was restored · what had been paid · who restored it · when."* Reconnecting
    # on a payment plan is normal practice; reconnecting with no record of what
    # was outstanding is how a dispute six months later has no answer.
    #
    # ⚠ **THREE OF THE FOUR ARE HERE AND THE FOURTH IS A STATED ABSENCE.** *Who*
    # and *when* travel on the `audit_log` row `_audit` writes (hard rule 7);
    # *what was still owed* is `owed_at_reconnection` below, read once from the same
    # place the warning quotes. *What had been paid* is NOT read on this path —
    # `PAID_AGAINST_ARREARS_NOT_READ`, `DEF-PAY-6074` — and a number invented
    # here would be a second, wrong answer to a question billing answers exactly.
    warnings = reconnect_warnings(case, balance=balance)
    case.state = STATE_RECONNECTING
    case.save(update_fields=["state", "updated_at"])
    payload = cut_payload(case)
    # ⛔ **RENAMED FROM `settled_balance` ON 2026-09-25, AND THE RENAME IS THE
    # POINT RATHER THAN TIDINESS.** That key was named when a ZERO balance was
    # the precondition of getting here, so it was true of every payload that
    # could exist. `BR-CUS-1097` makes the balance a thing to RECORD rather than
    # a thing to CHECK, and the moment it did, `settled_balance: 1204.5000`
    # became a sentence claiming an account was settled while naming the money
    # it still owed. **A key named for a state the row is not in is this repo's
    # most-filed rot** — CLAUDE.md hard rule 4 records the same fix on
    # `amendment_history_is_not_a_permanent_record`, renamed rather than
    # reworded for exactly this reason. A rename is a fan-out, not an edit, and
    # the fan-out is done: `tests/test_w7_cut_reconnect.py`,
    # `tests/test_br_cus_1097_1099_warn_do_not_stop.py`, and the two docstrings
    # in `test_cr052_w0_*` that quote it.
    payload["owed_at_reconnection"] = _money(balance)
    payload["on_date"] = str(on_date)
    payload["warnings"] = list(warnings)
    payload["paid_absence"] = dict(PAID_AGAINST_ARREARS_NOT_READ)
    _audit(actor, AUDIT_RECONNECTING, account_id, after=payload)
    # ── CR-070 wave P · the visit, booked at last (US-WRK-039) ─────────────
    # AFTER the state move and AFTER the audit row, for the reason in the
    # docstring: this cannot hold a paid customer in `CUT`.
    from apps.customers import services as customer_services  # local: services imports this module

    visit = customer_services._raise_flow_work(
        actor,
        flow_kind="reconnect",
        flow_id=account_id,
        template_ids=customer_services._field_visit_templates(template_ids),
    )
    payload["work_orders"] = visit["work_orders"]
    # The constant still answers when no job was raised — see its own docstring
    # for why it keeps its name on the day its other case stopped happening.
    payload["visit"] = (
        {"code": "reconnection_visit_scheduled", "orders": visit["work_orders"]}
        if visit["work_orders"]
        else dict(VISIT_NOT_SCHEDULED)
    )
    if visit["warnings"]:
        payload["work_order_warnings"] = visit["warnings"]
    return payload


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-PAY-036")
def restore_service(actor: Any, account_id: Any, *, on_date: date) -> dict[str, Any]:
    """The visit happened — service is back and the row leaves the tab.

    §5.8.4: *"payment confirmed → visit scheduled → **restored** → the row leaves
    the tab."* `STATE_RESTORED` is one of the two states `open_case_for` excludes
    and `uq_one_open_disconnect_case_per_account` ignores, so leaving the list
    and being able to open a fresh case later are the same fact, held once.

    ⛔ **ONLY FROM `RECONNECTING`.** A cut account cannot jump straight to
    restored: the middle state is *"paid, awaiting a visit"* and skipping it
    would record a restoration on an account that never settled — which is
    exactly the shape BR-PAY-036 forbids in the other direction.

    ⚠ **THE DEPOSIT CONSEQUENCE TRAVELS WITH THE RESULT AND NOTHING COLLECTS
    IT.** `DSC-02.4`: applying the deposit *"leaves nothing held if they later
    restore service"* — *"Nothing is held, so a new deposit is required to
    reconnect."* This call reports `new_deposit_required: True` on an applied
    deposit and takes no money: a deposit is `accounts.deposit_on_file` and
    customers writes no financial table (BR-CUS-037).

    ✅ **IT WRITES THE ACCOUNT STATUS BACK, SINCE 2026-08-30 (CR-052 W0 task 1,
    `OQ-1170`'s second half).** Until then this call wrote `reconnected_on` and
    touched no `accounts` column, which was harmless while nothing wrote
    `Disconnected` either — and became a silent, permanent defect the moment the
    cut started writing it: a customer whose water was turned back on would have
    stayed `non_billable`, outside every bill run, **for ever**.

    ⛔ **UNTIL 2026-10-29 THE ACCOUNT RETURNED TO THE STATUS IT HELD BEFORE THE
    CUT** (`disconnect_cases.status_before_cut`), derived on 2026-08-30 from
    `mark_reconnecting` refusing while a cent was owed — so a restored account
    was always a settled one and the debt that would justify `Marked disconnect`
    could not exist. That premise died on 2026-09-25 with `BR-CUS-1097` (*"Show
    what's still owed and let the clerk proceed"*) and the conclusion stood
    unargued for a month, until a walk restored `A-11340` — marked → cut →
    reconnected owing **$8,315.00** — straight back to `Marked disconnect`, under
    a screen (S148 step 2) promising *"The mark on the account clears"*
    (`DEF-CUS-10668`).

    ✅ **THE ACCOUNT RETURNS TO `Active` — PO 2026-10-29, verbatim *"2A"*** (decision
    log *"Five open questions answered in one message (PO)"* item 2). The mark
    clears as the screen promises; if they still don't pay, the ladder starts
    again. Supersedes CR-052 W0's *"status held before the cut"*.

    **`Active` IS THE TENANT'S SEEDED `active` ROW, CHOSEN BY CODE** — the same
    handle `services._default_active_status` and `temporary_stop` use (BR-CUS-055).
    Never by behaviour class alone: `Marked disconnect` is ALSO `billable`, so
    "the first billable status" could hand the mark straight back. Never by id.
    `status_before_cut` is still recorded at the cut and now decides nothing — it
    is the history of what the account was.

    ⚠ **AND IT IS NOT GUESSED WHEN IT CANNOT BE READ.** A tenant whose `active`
    row is missing or switched off (a provisioning gap BR-TEN-036 forbids) keeps
    the account at the status it has, and `RESTORED_STATUS_NOT_RECORDED` says so
    by name — the restoration itself still happens, because service is back on
    whether or not the word can be written.
    """
    case = open_case_for(account_id)
    if case is None:
        raise DisconnectRuleError(
            "there is no open disconnect case on this account to restore.",
            code="no_open_case",
            br_ref="BR-CUS-039",
        )
    # ⚠ **THE REFUSAL MOVED OUT ON 2026-09-20 AND ITS WORDS DID NOT CHANGE** —
    # `restore_blockers` holds it so the screen and this call say one thing.
    blocked = restore_blockers(case)
    if blocked:
        first = blocked[0]
        raise DisconnectRuleError(
            str(first["detail"]), code=str(first["code"]), br_ref=str(first["br_ref"])
        )
    # ── CR-052 W0 · THE STATUS COMES BACK IN THE SAME ACT AS THE STATE ─────
    # One transaction, because a case that reads RESTORED beside an account that
    # is still `non_billable` is the exact silent gap OQ-1170's second half
    # named — and it would be invisible until the next bill run did not bill.
    with transaction.atomic():
        account = _account(account_id)
        restored_to = None
        # DEF-CUS-10668 (PO 2026-10-29, *"2A"*): Active, by its seeded CODE —
        # never `status_before_cut`, never a behaviour class, never an id.
        row = restored_status_row(account.tenant_id)
        if row is not None:
            account.status = row
            account.save(update_fields=["status", "updated_at"])
            restored_to = row.code
        case.state = STATE_RESTORED
        case.reconnected_on = on_date
        case.save(update_fields=["state", "reconnected_on", "updated_at"])
        payload = cut_payload(case)
        payload["leaves_the_tab"] = True
        # ── `BR-CUS-1097` AT THE MOMENT SERVICE IS RESTORED — DEF-CUS-10657 ──
        # PO 2026-10-29, C1 *"Restore = Reconnect request"*: the request
        # (`mark_reconnecting`) and the restoration are now days apart, and the
        # rule asks for what was still owed *"at the moment service was
        # restored"*. So it is read again HERE, from the same place, and
        # RECORDED — never a gate (a restoration over an unreadable balance
        # proceeds and says so by name rather than writing a zero, `DEF-127`).
        owed_now = _balance_for(account_id)
        payload["owed_at_restoration"] = None if owed_now is None else _money(owed_now)
        if owed_now is None:
            payload["owed_at_restoration_absence"] = {
                "code": "balance_unreadable",
                "br_ref": "BR-CUS-1097 · BR-PAY-032",
            }
        payload["paid_absence"] = dict(PAID_AGAINST_ARREARS_NOT_READ)
        payload["account_status_restored_to"] = restored_to
        if restored_to is None:
            payload["account_status_restore"] = dict(RESTORED_STATUS_NOT_RECORDED)
        # DEF-NOT-10649 — *Service restored*, in this transaction, after the
        # state is written; savepointed by the seam. See `commit_cut`.
        payload["notification_queued"] = notifications_seam.queue_service_restored(
            case_id=case.id, account_id=account_id, restored_on=on_date, actor=actor
        )
        _audit(actor, AUDIT_RESTORED, account_id, after=payload)
    return payload


def cut_payload(case: DisconnectCase) -> dict[str, Any]:
    """`case_payload` plus everything 7.8 and 7.9 recorded, and every absence.

    A SEPARATE payload rather than four more keys on `case_payload`: that one is
    the S90 row and the audit shape three other surfaces already read
    (`disconnect_reads.list_disconnects` among them), and widening a payload
    other lanes consume is how a key becomes load-bearing before anybody agreed
    it. Everything here is additive and this function is the only door to it.
    """
    payload = dict(case_payload(case))
    payload.update(
        {
            "cut_reason": case.cut_reason,
            "reason_absence": dict(REASON_DRIVES_NOTHING),
            "services_cut": tuple(case.services_cut or ()),
            "restrictor": dict(RESTRICTOR_UNBUILDABLE),
            "reconnected_on": str(case.reconnected_on) if case.reconnected_on else None,
            "reconnection_fee": (
                _money(case.reconnection_fee_amount)
                if case.reconnection_fee_amount is not None
                else None
            ),
            "reconnection_fee_code": case.reconnection_fee_code,
            "fee_posting": dict(FEE_POSTED),
            "fee_timing": dict(FEE_TIMING_RULED),
            "deposit_disposition": case.deposit_disposition,
            "deposit_posting": dict(DEPOSIT_APPLICATION_NOT_POSTED),
            "new_deposit_required": (
                None
                if case.deposit_disposition is None
                else case.deposit_disposition == DEPOSIT_APPLIED
            ),
            "account_open": True,
            "will": CUT_WILL,
            "will_not": CUT_WILL_NOT,
            "accrual": dict(CUT_STOPS_BASE),
            "account_status": dict(DISCONNECTED_STATUS_ASSIGNED),
            "crew_outcome": dict(CREW_OUTCOME_UNRECORDABLE),
        }
    )
    return payload


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.16 — BR-CUS-082's POST-CLOSURE LADDER
# ════════════════════════════════════════════════════════════════════════════
def _dunning_after_close() -> dict[str, Any]:
    """`move_out_settlement.DUNNING_AFTER_CLOSE`, CONSUMED and not restated.

    That module built the collision as a fact for W7 to inherit — *"the
    `dunning` block of its result carries the restart-at-TIER-1 fact and the
    unresolved subject side by side, for W7 to inherit as a fact rather than a
    guess"*. Restating it here would be a second copy of a sentence about an
    unresolved question, free to be "tidied" into an answer.
    """
    from apps.customers import move_out_settlement

    return dict(move_out_settlement.DUNNING_AFTER_CLOSE)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-CUS-082")
def restart_after_closure(
    actor: Any, account_id: Any, *, as_of: date, shortfall: Decimal, currency: str
) -> dict[str, Any]:
    """BR-CUS-082 — the debt survived the close, so the ladder starts AGAIN at TIER 1.

    PO 2026-08-24, closing OQ-346, verbatim: *"(b) continue, ladder restarts"*.
    Worked, on the PO's own fixture: `A-11024 · Ridge Coffee Co.` closes owing
    **$328.70** against **$153.50** of deposit and interest — **$175.20**
    survives and is chased from TIER 1.

    **THERE IS NO `tier` PARAMETER.** A customer already at TIER 2 at closure
    does not stay at TIER 2, and the way that is guaranteed is that resuming is
    not expressible: this function writes `TIER_1` and takes no instruction
    about it.

    **AND THERE IS NO `subject` PARAMETER.** BR-CUS-097 moves a sub-account's
    residue to its MASTER and BR-CUS-082 restarts the ladder against the debt;
    **whether the restarted ladder chases the departed sub-account holder or the
    master is stated by neither ruling.** J08 step 2b asserts that as OPEN and
    says a green assertion naming either party is a FAILURE. So the case is
    opened against the account the debt was measured on — the row it belongs to
    — and the result carries `DUNNING_AFTER_CLOSE`, whose `subject_unresolved`
    sentence travels with it. **An OQ is OWED**; this lane reports it and does
    not mint one.

    ⚠ **A COLLECTIONS SEQUENCE, NOT A SERVICE ONE.** The case is written with
    `sequence=SEQ_COLLECTIONS`, which `assert_cut_reachable` and
    `ck_collections_sequence_never_cuts` both refuse a cut on.
    """
    if shortfall is None or Decimal(str(shortfall)) <= ZERO:
        raise DisconnectRuleError(
            "an account that closes owing nothing has nothing to chase and no ladder runs. "
            "BR-CUS-030's `dunning stops` is superseded ONLY for the closed-with-balance case, "
            "and reading it wider would start a ladder against a settled customer.",
            code="closed_owing_nothing",
            br_ref="BR-CUS-030",
        )
    amount = Decimal(str(shortfall))
    existing = open_case_for(account_id)
    if existing is not None:
        # BR-CUS-082 restarts the ladder; it does not open a second one. The
        # partial unique index would refuse anyway — this is the sentence.
        existing.sequence = SEQ_COLLECTIONS
        existing.tier = TIER_1
        existing.tier_reached_on = as_of
        existing.state = STATE_NOTICE_SENT
        existing.cut_scheduled_for = None
        existing.save(
            update_fields=[
                "sequence",
                "tier",
                "tier_reached_on",
                "state",
                "cut_scheduled_for",
                "updated_at",
            ]
        )
        case = existing
    else:
        # CR-039 wave D task 16 — the SECOND creation site, and it needs the
        # same treatment as `open_case`'s: a post-closure collections case is
        # a case, and a clerk chasing a debt after the account shut has more
        # need of a reference than most. Its own `atomic()`, for the reason
        # given there.
        with transaction.atomic():
            case = DisconnectCase.objects.create(
                tenant_id=_tenant_id(),
                case_no=_allocate_case_no(),
                account_id=account_id,
                sequence=SEQ_COLLECTIONS,
                state=STATE_NOTICE_SENT,
                tier=TIER_1,
                tier_reached_on=as_of,
                amount_owed_at_open=amount,
                currency=currency,
                opened_on=as_of,
            )

    payload = case_payload(case)
    payload["amount_chased"] = _money(amount)
    payload["dunning"] = _dunning_after_close()
    payload["subject"] = None
    payload["escalates_to_disconnection"] = False
    _audit(actor, AUDIT_POST_CLOSURE_RESTART, account_id, after=payload)
    return payload


def case_payload(case: DisconnectCase) -> dict[str, Any]:
    """One case, as the S90 row and the audit trail both need it."""
    return {
        "case_id": str(case.pk),
        # CR-039 wave D task 16. The reference a clerk quotes, and — when there
        # is none — the REASON beside it. A screen handed a bare `None` can
        # only draw a blank or a dash, and neither says *"nobody has set up
        # disconnect numbering"*, which is a different thing from *"this case
        # has no number of its own"*.
        "case_no": case.case_no,
        "case_no_unavailable": None if case.case_no else dict(CASE_NUMBER_UNAVAILABLE),
        "account_id": str(case.account_id),
        "sequence": case.sequence,
        "state": case.state,
        "tier": ladder_tier_of(case),
        "tier_reached_on": str(case.tier_reached_on) if case.tier_reached_on else None,
        "amount_owed_at_open": _money(case.amount_owed_at_open),
        "currency": case.currency,
        "opened_on": str(case.opened_on),
        # ⚠ **THE NEXT NOTICE'S DATE, AND IT WAS MISSING FROM HERE ENTIRELY
        # UNTIL 2026-09-06 (`DEF-CWP-4142`).** The column has always existed and
        # `portal.selectors._timeline` has always had a `notice_next` branch
        # gated on this key, with `portal.overdue.step.notice_next` written in
        # all eleven catalogues to render it — so `CWP-057` could never draw the
        # *final notice* rung that `CWP-057.png` puts between the notice already
        # sent and the disconnection. Walked in a browser: the ladder jumped
        # from *Ten-day notice* straight to *Supply disconnected*, telling a
        # household when the supply goes and not when the last warning comes.
        # Nothing could see it — the branch is well-typed, the string exists,
        # and the selector's own test asserts the rows it expected to get.
        #
        # ⚠ **IT IS A FLOOR AND THE CONSUMER MUST SAY SO.** This module's own
        # words: *"`next_step_due` is a STORED DATE THAT NOTHING WATCHES"*
        # (`DEF-320`) — a tier advances when something happens, never because a
        # date passed. `_timeline` marks the row `is_floor` and the screen reads
        # *no earlier than*; a surface that printed this as a promise would be
        # telling a customer they have until a day the utility never agreed to.
        "next_step_due": str(case.next_step_due) if case.next_step_due else None,
        "cut_scheduled_for": str(case.cut_scheduled_for) if case.cut_scheduled_for else None,
        "cut_on": str(case.cut_on) if case.cut_on else None,
        "stopped_on": str(case.stopped_on) if case.stopped_on else None,
        "stopped_reason": case.stopped_reason,
        # `CR-125-BRC07` — the drawn `What happened` line. NULL on every case
        # stopped before this column existed and on every ladder that stopped
        # itself; see `DisconnectCase.stopped_note` for why it is not required.
        "stopped_note": case.stopped_note,
        "scheduler": dict(NO_SCHEDULER),
        "delivery": dict(DELIVERY_UNAVAILABLE),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: `DSC-02.1` … `DSC-02.5` (B18 §5.8.7, captured 2026-08-25 — the cut's
#         four consequences and its three prohibitions, verbatim) · lane CUT,
#         2026-08-25 · CR-030 W7 tasks 7.8 (the cut) and 7.9 (the reconnect) ·
#         BR-CUS-055 · BR-CUS-037 · BR-BIL-007 · BR-PAY-036
#         BR-CUS-100 (PO 2026-08-25, closing DEF-692 — the proof of service, its
#         six columns and the tier-3 cut guard) · lane PROOF, 2026-08-25 ·
#         CR-030 W7 tasks 7.5 · 7.6 · 7.7 · 7.16 — B18 §5.8 + §6.3 · BR-CUS-082 ·
#         BR-CUS-097 (open half) · BR-CUS-039 · BR-CUS-043 · BR-PAY-016/017 ·
#         J08 step 2b · apps/customers/move_out_settlement.py
# generated: 2026-08-25 by lane S3 (W7 disconnects backend)
# checklist: A✔ B✔ C✔ D=deferred(no API half — S90's six endpoints are their own
#         tasks 7.11/7.9) E=deferred(no-frontend-half — S90 is task 7.11)
#         F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — measured, not claimed
# exceptions: (1) the three model classes are here rather than in
#         apps/customers/models.py because another lane held that file; ONE line
#         is owed in apps/customers/apps.py `ready()` and is REPORTED.
#         (2) `disconnect_notices` and `disconnect_cases.tier` overlap payments'
#         `notice_history` / `account_collection_state`; built as B18 §6.3 asks
#         and REPORTED with DEF-675 named beside it — this lane did not take
#         that ruling. (3) payments' `second_5_day` rung has NO B18 chip;
#         `tier_for_rung` returns TIER_UNMAPPED rather than guessing.
#         (4) BR-CUS-097's "who is chased" half is OPEN; no subject is named
#         anywhere and an OQ is OWED. (5) Nothing advances a tier on a date —
#         DEF-320. (6) [lane PROOF] whether a tier-3 cut needs the SIGNATURE
#         back, and whether a proof CORRECTION is a new notice or its own row,
#         are unwritten in every signed document and are REPORTED, not chosen.
#         (7) [lane PROOF] `notices_awaiting_proof()` is built and NOT WIRED —
#         no screen reads the queue yet. (8) [lane PROOF] three tests in two
#         files this lane does not own now assert the pre-BR-CUS-100 world and
#         need a recorded proof before their `schedule_cut` — see the docstring.
#         (9) [lane CUT] a per-service RESTRICTOR is REFUSED, not recorded —
#         `DSC-02.1` draws three treatments and this schema holds two, and B18
#         draws the restrictor as the DEFAULT for water. What it would take is
#         named in `RESTRICTOR_UNBUILDABLE`. (10) [lane CUT] there is NO
#         `disconnected` account status — BR-CUS-055 seeds five and none is it —
#         so the state lives on `disconnect_cases.state='cut'` and nothing
#         writes the account row. A PO amendment is OWED. ⚠ **(10) IS HALF
#         SUPERSEDED — the amendment CAME. BR-CUS-107 (PO 2026-08-25, closing
#         DEF-701) adds the sixth status, `Disconnected` / `non_billable`, and
#         it is seeded. What still holds is the second half: NOTHING WRITES THE
#         ACCOUNT ROW.** See exception (21). (11) [lane CUT] the
#         reconnection fee is QUOTED from the tenant's `CC-RECON` code and is
#         NOT posted to AR (BR-CUS-037; billing publishes no ad-hoc charge
#         service), and NO SEED CREATES THAT CODE — the demo seed spells its
#         sibling `DISC`, so every cut refuses until a tenant configures one.
#         (12) [lane CUT] `DSC-02.4` dates that fee TWO ways in one screen (on
#         the cut / on restoration); neither reading is chosen. (13) [lane CUT]
#         the cut REASON is recorded and drives nothing, and four of the five
#         drawn reasons have NO path to a cut because `schedule_cut` requires
#         TIER 3 + certified proof. (14) [lane CUT] a crew that attends and does
#         NOT cut cannot be recorded — no outcome vocabulary exists. (15) [lane
#         CUT] `new_service_block_for()` is BUILT AND NOT WIRED: move-in does not
#         check it, and *"elsewhere"* names no subject. (16) [lane CUT] base
#         accrual after a cut is held BY OMISSION and is still an UNSIGNED rule
#         (B18 §5.8.7's own finding); a BR is OWED. (17) [lane CUT] the new
#         `ck_cut_records_the_price_of_coming_back` makes
#         `tests/test_w7_disconnects.py::test_tc_dsc_1b__paying_does_not_restore_service`
#         RED — it fakes a cut with an ORM write and now needs the fee, its code
#         and the deposit election beside `cut_on`. That file is not this lane's;
#         the three-line patch is in the lane report.
# revised: 2026-08-25 (lane CUTMONEY) — **TWO PO RULINGS ON THE CUT, AND ONLY ONE
#         OF THEM COULD BE BUILT. Both are written down here either way.**
#         **(A) BR-CUS-103 — BASE CHARGES STOP AT THE CUT** (PO 2026-08-25, closing
#         OQ-380; asked with `A-11488`, cut 2026-08-18 owing **$612.75**, answer
#         **"no"**). **BUILT.** DEF-707 is CLOSED by it. Items (12) and (16) above are
#         SUPERSEDED by this line and are left in place with their supersession
#         stamped, never deleted: (16) said base accrual was an UNSIGNED rule held by
#         omission — it is signed now and reversed; (12) said `DSC-02.4` dated the fee
#         two ways and neither was chosen — BR-CUS-104 chose (see B).
#         ⚠ **`commit_cut` STILL WRITES NOTHING NEW.** No `accounts` column, no
#         behaviour class, no accrual flag — `DSC-02.4`'s first prohibition is exactly
#         as intact as it was. The mechanism is a READ: `service_off_windows()`
#         publishes the dark days, `apps.customers.selectors.service_off_windows`
#         forwards it, and `apps/billing/gather.py` subtracts them from `service_days`,
#         which B4.3 ❄️ already prorates by. **No new money math exists anywhere for
#         this rule.** The BOUNDARY lives here — BR-CUS-103 bills base *"right up to the
#         moment it is cut"*, so the first dark day is `cut_on + 1`,
#         the same inclusive convention `gather._service_days` already applies to a
#         move-out's `closed_at`. `CUT_KEEPS_ACCRUING` is REPLACED by `CUT_STOPS_BASE`
#         and `CUT_WILL`'s second line keeps `DSC-02.4`'s superseded wording with its
#         supersession stamped beside it, so a reader holding r10 can still find it.
#         **(B) BR-CUS-104 — THE FEE LANDS AT THE CUT** (PO 2026-08-25, closing OQ-381,
#         verbatim *"does reconnection need $8,315.00 - this is correct"*: `A-11340`
#         owes $8,240.00, the fee is $75.00, $8,315.00 is what must be cleared).
#         ⛔ **NOT BUILT — DEF-708 STAYS OPEN.** `FEE_TIMING_UNRULED` is replaced by
#         `FEE_TIMING_RULED`, which states the ruling and names the defect;
#         `FEE_POSTED` now tracks DEF-708. `mark_reconnecting` is UNCHANGED and its
#         docstring says why: **the fee has to become a real receivable, and folding
#         `case.reconnection_fee_amount` into the gate's comparison DEADLOCKS the
#         product** — paying takes AR to zero, the recorded fee never clears, and no cut
#         customer could ever be reconnected. Why the posting could not be done from
#         here is measured in the lane report; the short form is that AR is Σ posted
#         journal lines, posting happens at ISSUE, `models.BILL_TYPES` has no fee type,
#         `issue._gl_account_for` REFUSES every `fee` line unconditionally, and issue
#         needs a BR-BIL-026 template pin. That is a billing story, not a one-liner.
#         TESTS: `tests/test_br_cus_105_static_balance.py` (5 passed, 1 xfailed —
#         BR-CUS-105's static-balance guard, on REAL priced bills, with the $687.75 half
#         pinned `xfail(strict=True)` on DEF-708 so it fires the day the fee posts).
#         `test_tc_dsc_7__the_cut_leaves_the_account_open_and_accruing` is RENAMED and
#         RE-POINTED — it asserted the reversed rule and was green on it, which is
#         DEF-705's lesson one day old.
#         (18) [lane CUTMONEY] a PARTIAL cut (some services cut, some not) now makes the
#         bill an EXCEPTION rather than a guess — B4.3 has one account-level proration
#         factor and no per-service `service_days` exists. `gather.GATHER_PARTIAL_CUT`.
#         (19) [lane CUTMONEY] whether base RESUMES on the restoration date is not
#         separately signed. It is implemented as the mirror of BR-CUS-103's own reason
#         (*"a customer with no service pays nothing for it"*) — the dark window ends at
#         `reconnected_on - 1` — and it is REPORTED for confirmation rather than raised
#         as a question, because the alternative is never billing base again.
#         (20) [lane CUTMONEY] `disconnect_reads.CUT_ACCRUAL_UNVERIFIED`'s CODE is left
#         alone and only its DETAIL is amended: `07-frontend` reads that string and this
#         lane does not own frontend files. The caption *"still accruing base charges"*
#         is now FALSE, not unverified. The rename and the copy fix are OWED.
#         ⚠ **(20) IS DONE — DEF-716, lane DISCSTATUS, 2026-08-25.** The constant is
#         `CUT_ACCRUAL_CAPTION_SUPERSEDED` / `cut_accrual_caption_superseded`, both
#         halves moved in one commit, and `tests/test_def_716_cut_accrual_caption.py`
#         pins them so a half-landed rename cannot go green again — measured, it did:
#         the frontend suite reported 19 passed on the retired spelling.
#         (21) ✅ **CLOSED 2026-08-31 (CR-052 W0 task 1, PO ruling 2026-08-30).**
#         This exception said BR-CUS-107's `Disconnected` status was SEEDED and
#         ASSIGNED BY NOBODY, blocked on two measured consequences of the
#         `non_billable` class. The occupancy half was RULED correct as written
#         (BR-CUS-110) and its terminal-path fallout fixed (DEF-724); the billing
#         half was `OQ-1170` and the PO closed it by making the cut the WHOLE
#         event. `commit_cut` now raises the final metered bill for the days up to
#         the cut, records what is outstanding and writes the status; the ONE case
#         where it declines to write it is `CUT_BILL_BLOCKED_SO_STATUS_HELD`, and
#         `DSC-02.4`'s three prohibitions are still untouched — no close, no
#         deposit settlement, no meter removal. See `DISCONNECTED_STATUS_ASSIGNED`
#         and `tests/test_cr052_w0_disconnected_at_the_cut.py`.
#         (22) [lane CR-052 W0] **THE CUT NOW CAUSES A CUSTOMER-FACING BILL AND
#         THIS MODULE STILL WRITES NO FINANCIAL TABLE.** Both bills — the final
#         metered one and the $75.00 fee — are raised through published billing
#         seams (`seams.raise_and_issue_cut_bill`, `seams.raise_and_issue_charge_fee`),
#         priced by billing's own engine and posted by the ledger. Customers
#         supplies the CUT DATE, the due terms and B4.3's denominator, and decides
#         nothing about the money. `apps/billing/cut_bill.py` holds no arithmetic.
#         (23) [lane CR-052 W0] **B4.3's DENOMINATOR CANNOT BE READ AND THE
#         FALLBACK IS STATED, NEVER SILENT** — `apps.metering.selectors.
#         billing_period_for_unit` is unpublished, so a cut bill charges a FULL
#         month's base for a part month: $40.00 where 18 of 31 days is $23.23,
#         $16.77 on the worked case. `DEF-2708`, and the sentence rides every
#         such bill on `cut_bill.CUT_BILL_DENOMINATOR_ABSENT`.
#         (24) [lane CR-052 W0] **THE STATUS IS HELD, NOT FORCED, WHEN BILLING
#         REFUSES** — `CUT_BILL_BLOCKED_SO_STATUS_HELD`. Writing `Disconnected`
#         over days nobody billed is `OQ-1170`'s defect restored by a
#         convenience, and this is the one branch of this change that a later
#         lane will be tempted to "tidy".
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
