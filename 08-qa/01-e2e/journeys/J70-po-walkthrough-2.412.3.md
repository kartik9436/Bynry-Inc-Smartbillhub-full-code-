# One-time bill — the PO's walk-through on 2.412.3 (plan task C3)

> **Applies to 2.412.4.** Walked for the PO on 2026-09-30 on build 2.412.4 (the eight checks are
> unchanged from 2.412.3); the result and the screenshots are at the foot. On a fresh demo seed the
> account numbers differ from the ones below — Maria Alvarez, Unit A, is `AC-2026-00055` — and
> *Alvarez* matches six accounts, not four (the J70 seed gives Maria Alvarez Units A, C, D, E and F).
> The checks do not depend on either.

Status: **READY FOR THE PO**, prepared 2026-09-30. The PO's result goes in the table at the foot, with
what they saw, and closes C3 (and with it the one-time bill plan, 74 of 74).

## Before you start

1. **Deploy 2.412.3.** The version shows in the app.
2. **Run the database updates.** Four are new since 2.411.4: `billing` 0032, 0033 and 0034 (the bulk run's saved
   check results) and `tenancy` 0054 (the kept-document list). `python manage.py migrate`.
3. **Test data.** Run `10-scripts/seed_j70_one_time_bill.py` on a **demo tenant only** (it creates Maria Alvarez,
   `AC-2026-00042`, at 1408 Elm St Unit A; Dana Brooks, `AC-2026-00043`, Unit B). Never on a live utility.

## The eight checks

| # | Do this | You should see |
|---|---|---|
| 1 | Bills → One-time → **Interim** → type *Alvarez* in Find account | Four matches; pick Maria Alvarez. The account card fills at once: Plan, Cycle, Last bill, Balance, *21 days to pay* |
| 2 | Continue with no readings entered | A warning, not a stop: *3 meters need a reading. Enter them next.* Type them on step 2 |
| 3 | Review, then Send | **Five ticks**: Compliance checked, Email checked, Texts checked, Autopay checked, Ready to send. Send stays grey until all five are ticked. The bill prints the customer's name, service address, mailing address and the utility's address |
| 4 | **First bill** for Maria | Move-in date is a date picker, filled from the account (Sep 12). Change it to Sep 13: *Differs from the account*. It applies to this bill only |
| 5 | **Final bill** for Maria, move-out Sep 18 | Settlement shows deposit −$150.00 against the **$93.47** bill: **Refund due $56.53** (from 2.416.5; it read $103.67 / $46.33 while the demo cycle could not be read — `DEF-BIL-8333`). Send works |
| 6 | **Catch-up** Jul–Sep with no readings | Step 1 waits for the readings instead of refusing. Before you type them, lines are marked *Estimated*. Typed September readings are shared across the months they cover |
| 7 | **Penalty** with two overlapping periods | *Overlaps another period.* on the row and in the list. *Approved by* can be picked, but is not required |
| 8 | Any kind, leave a field empty and Continue | Every problem names itself and sits on its field, tinted; never a lone *This step isn't finished* |

## Known and not a fault

- Services list Electric before Water (the product's service order); the drawing shows Water first.
- The price version reads *Water · from 07/16/2026*, not *Water v4*: rating stores no version number.
- Paying the $56.53 refund out is not built yet; it stays owed to the customer (open question OQ-195).

## If something is wrong

Tell us in one sentence; we file it and fix it. To go back: `04-docs/05-modules/07-billing/18-rollback-2.412.md`
(back to 2.411.4; leave `tenancy` 0054 applied).

## Result (filled in from the PO's answer)

| Date | Build | What the PO saw | Outcome |
|---|---|---|---|
| 2026-09-30 | 2.412.4 | The ten screenshots of the eight checks (`08-qa/screens/one-time-bill-po-walk-2.412.4/`), walked for the PO at 1440 on PostgreSQL: account card, missing-reading warning, five ticks with Send off, the issued bill with name and both addresses, move-in "Differs from the account", Refund due $46.33, catch-up waiting then Estimated, overlap on the row, problem on its field. PO verbatim: *"ok"* | **ACCEPTED — C3 closed; one-time bill 74 of 74** |

### Walked for the PO — 2026-09-30, build 2.412.4

A fresh PostgreSQL 16 database on 127.0.0.1:55433 (migrate, `seed_demo`, then
`10-scripts/seed_j70_one_time_bill.py`), a real Chromium browser at 1440 wide, one check at a time,
waiting for each step to finish checking before Continue — as a person would. Screenshots:
`08-qa/screens/one-time-bill-po-walk-2.412.4/`. **The PO judges from the screenshots; this table is
what we saw.**

| # | Check | Result | Screenshot(s) | What it shows |
|---|---|---|---|---|
| 1 | Account card fills at once | **PASS** | `1-account-card.png` | Maria Alvarez, Unit A: Plan *Residential Standard (Elm St)*, Cycle *21 days to pay*, Last bill —, Balance $0.00. *Alvarez* matched six accounts on this seed, not four |
| 2 | Missing-reading warning, not a stop | **PASS** | `2-missing-reading-warning.png` | *3 meters need a reading. Enter them next.* under the step; Continue went on to step 2 |
| 3 | Five ticks; Send grey until all five; the bill prints name and addresses | **PASS** | `3a-five-ticks-send-off.png` · `3b-issued-bill-name-addresses.png` | Four of five ticked and *Send $185.13 bill* still grey. The bill as sent: Brazos Bend Utilities, 9410 FM 1093 Rd, Katy TX 77494 · Maria Alvarez · service address 1408 Elm St, Katy TX 77494, Unit A · mailing address 1408 Elm St, Katy TX |
| 4 | Move-in date picker, *Differs from the account* | **PASS** | `4-move-in-differs.png` | Filled 09/12/2026, changed to 09/13/2026: *Differs from the account (09/12/2026)* |
| 5 | Final bill: **Refund due $46.33**, Send works | **PASS** | `5-refund-due.png` | Settlement: this final bill $103.67, deposit held −$150.00, **Refund due $46.33**; sent as BL-2609-000102. ⚠ The screenshot was REPLACED on 2026-10-01 (2.416.5): with the demo cycle readable the same bill is **$93.47, refund $56.53** — see the update at the foot (`DEF-BIL-8333`) |
| 6 | Catch-up with no readings: waits, then *Estimated* | **PASS** | `6a-catch-up-waiting.png` · `6b-catch-up-estimated.png` | John Robert (read only to Jun 30): step 2 waits, *Enter reading* on September. Maria Alvarez Unit E before typing: lines marked *Estimated*, *10 readings estimated.* (Typed readings shared across the months: proved in J70 E4/P5.) ⚠ Seen beside it, not part of the check: `DEF-BIL-8328` |
| 7 | Penalty, overlapping periods named on the row | **PASS** | `7-overlaps-on-row.png` | *Overlaps another period.* under row 1's From and in the list. (*Approved by* sits on step 2 and is optional — proved in J70 E5.) |
| 8 | A problem sits on its field | **PASS** | `8-problem-on-field.png` | *Fix 2 things to continue.* — *Ends before it starts.* on To, *Enter days to pay.* on Days to pay; never the lone generic line |

**Found on the way, filed and not fixed (as asked):**
- `DEF-BIL-8327` — seen once on a cold first run: Continue pressed straight after typing the Final
  bill's dates left *This step isn't finished* standing alone over a complete step 1. One retry did not
  reproduce it.
- `DEF-BIL-8328` — a catch-up's step 2 marks every period *Actual* while every reading is still waiting,
  and shows a shared July read as *Actual 700 kWh* on one half of the split month.

### The PO's own reports, walked as a clerk — 2026-09-30, build 2.415.1 (shipped as 2.416.1)

The PO asked whether the bugs they reported were walked in a browser from the clerk's side. The
2.412.5 fixes (`DEF-BIL-8287`, `8288`, `8289`, `8327`, `8328`, `8329`) had been proved by automated
tests only, on SQLite. Here they are walked: a fresh PostgreSQL 16 database on 127.0.0.1:55433
(migrate, `seed_demo`, then `10-scripts/seed_j70_one_time_bill.py`, which now also seeds **Unit K —
Nina Castillo**, on a water-only plan whose only water rate ends Jul 31, and **Unit L — John Mauli**,
on no billing cycle), a real Chromium browser at 1440 wide, typed the way a clerk types. Build
2.415.1 (the same code is 2.416.1 after rebasing onto the branch) also carries `DEF-BIL-8330` (a first bill with no cycle is stopped), `DEF-BIL-8332` (a cycle
with no name shows its code) and `DEF-BIL-8563` (a first bill from the move-in date opens on that
day's reading); row 8 walks the last. Screenshots: `08-qa/screens/one-time-bill-po-reports-walk/`.

| # | The PO's scenario | Result | Screenshot(s) | What it shows |
|---|---|---|---|---|
| 1 | Interim bill, no Water rate in force on the period end (Nina Castillo, Aug 1–31) | **PASS** | `1a-no-rate-while-typing.png` · `1b-no-rate-after-continue.png` | Nothing shown while typing, even after the automatic preview had answered; after Continue: *No Water rate on Aug 31, 2026. Add one in Plans & Rates.* |
| 2 | First bill, move-in 07/01 and To 07/01 (Maria Alvarez, Unit A) | **PASS** | `2-to-not-after-move-in.png` | *To must be after move-in.* on the To field, tinted; no preview was asked after Continue |
| 3 | First bill for an account with no cycle (John Mauli, Unit L) | **PASS** | `3a-no-cycle-on-pick.png` · `3b-no-cycle-continue-waits.png` | Cycle *None*; *No billing cycle. Assign one on the account.* in the problem list and on the account field the moment the account is picked; Continue stays on step 1; no $418.00 anywhere |
| 4 | Step 1 half-typed (interim, From only) | **PASS** | `4-half-typed.png` | *Finish step 1 to see figures.*; no Failed panel |
| 5 | Continue pressed straight after typing the dates (Dana Brooks, Unit B) | **PASS** | `5-continue-at-once.png` | Never the generic *This step isn't finished* alone; step 2 reached |
| 6 | Catch-up Jul–Sep with no readings typed (Maria Alvarez, Unit E) | **PASS** | `6-catch-up-waiting-estimated.png` | Every period and row says *Estimated* (September *Enter reading*); none says *Actual*. The Jul 16–31 row shows its own share, **361.29 kWh**, not 700 (Jul 1–15 shows 338.71) |
| 7 | Account card of an account on a cycle (Maria Alvarez, Unit A) | **PASS** | `7-card-names-the-cycle.png` | Cycle *J70-MONTHLY* — the cycle, never *21 days to pay*. The demo's cycle has no name, so it shows its code (`DEF-BIL-8332`; on 2.412.5 this said *None*) |
| 8 | `DEF-BIL-8563`: first bill from the account's own move-in date (Maria Alvarez, Unit C, 09/12–09/30) | **PASS** | `8a-first-from-move-in-day-services.png` · `8b-first-from-move-in-day-review.png` · `8c-first-from-move-in-day-sent.png` | The move-in readings of 09/12 are on file (W-10442C 479.8, E-55120C 18,500); Move-in charges: deposit $150.00 and CONN $45.00; Review total $397.82 on 2.415.1 (whole bases). **Re-walked on 2.416.3 after `DEF-BIL-8331`: $393.15** — screenshots replaced; see below |

**Found on the way:** `DEF-BIL-8331` (filed, not fixed) — a first bill charges each whole month's base
charge even for an account on a cycle: a 16-day first bill charges the $8.00 water base where 16 of 31
days is $4.13. J74's $397.82 is priced the same way (*"bases whole"*), so row 8 matches it; whether a
first bill's base should be prorated is for the coordinator and the PO.

**Update, same day — `DEF-BIL-8331` fixed in 2.416.3 (a first bill prorates its base from the
move-in day; signed law BR-BIL-012 and the frozen worked example 15/30 × $30.50 = $15.25).** Row 8
re-walked at 1440 on PostgreSQL:

| Line | Before (2.415.1, whole bases) | After (2.416.3, 19 of 30 days) |
|---|---|---|
| Water base, W-10442C and W-10443C | 2 × $8.00 | 2 × $5.07 ($8.00 × 19/30) |
| Water usage (the 5 kgal first block also scales to 19/30 = 3.17 kgal) | $32.45 + $28.85 | $34.74 + $31.14 |
| Sewer base | $6.00 | $3.80 |
| Trash (per cart $15.00 + base) | $18.00 | $16.90 (base $1.90) |
| Electric usage, sewer share | $64.74, $32.80 | unchanged |
| Subtotal | $198.84 | $194.26 |
| Tax, Local 2.00% | $3.98 | $3.89 |
| Deposit + connection charge (not taxed) | $195.00 | $195.00 |
| **Total** | **$397.82** | **$393.15** (sent as BL-2609-000101) |

⚠ **The $393.15 needs the cycle's calendar to be readable.** The demo cycle `J70-MONTHLY` is seeded
with no first run date, so metering cannot say how long it is, and the bill falls back to its own
length — whole bases, $397.82, exactly as before. For the re-walk the walk database only was given a
first run date of 2026-01-01 (the seed is unchanged); `DEF-BIL-8333` records it. With that date the
interim bill for Unit A stayed **$185.13**, and the final bill for Unit D moved from **$103.67 to
$93.47** — not from this fix (the final bill has read the cycle since 2026-09-20; with the demo's
cycle as seeded it is still $103.67), but because its cycle can now be read. That final figure was
accepted by the PO, so re-showing it is the coordinator's call. Screenshots `8a`/`8b`/`8c` are
replaced with the $393.15 walk.

**Update, 2026-10-01 — `DEF-BIL-8333` fixed in 2.416.5 (coordinator ruling: fix the seed).** The
demo cycle `J70-MONTHLY` is now seeded with a first run date of 2026-01-01, so its calendar can be
read on the seed as shipped and every demo first and final bill prorates its bases. The paragraph
above ("the seed is unchanged") no longer holds. Re-walked at 1440 on PostgreSQL on a database built
from the fixed seed:

| Bill | Days | Before | After | What moved |
|---|---|---|---|---|
| First bill, Maria Alvarez Unit C, Sep 12–30 | 19 of 30 | $397.82 | **$393.15** | as tabled above |
| Final bill, Maria Alvarez Unit D, Sep 1–18 | 18 of 30 | $103.67, refund $46.33 | **$93.47, refund $56.53** | water bases 2 × $8.00 → 2 × $4.80; sewer base $6.00 → $3.60; trash base $3.00 → $1.80 (trash line $18.00 → $16.80); usage unchanged; subtotal $101.64 → $91.64; tax 2% $2.03 → $1.83 |
| Interim bill, Maria Alvarez Unit A, Sep 1–30 | whole month | $185.13 | **$185.13** | nothing |

The $103.67 the PO accepted on 2026-09-30 is superseded by the arithmetic of the signed rule, not by
a new ruling (decision log 2026-10-01). Screenshots: `08-qa/screens/one-time-bill-po-walk-2.412.4/
5-refund-due.png` (replaced), `08-qa/screens/one-time-bill-po-reports-walk/8a`, `8b` (replaced, v2.416.5)
and `9a-final-unit-d-review.png` (new). `8c` is the $393.15 bill sent on 2.416.3.

⚠ **Send could not be re-walked on 2026-10-01 (`DEF-BIL-8334`, filed, not fixed).** The demo's own
calendar rolls with today, so a database seeded on 1 October closes SEPTEMBER, and every September
bill in this world is refused at Send (*"this journal entry is dated 2026-09-18, which falls inside
the CLOSED fiscal period 2026-09-01 … 2026-09-30"*). The figures above are the Review totals.

**Update, 2026-10-01 — `DEF-BIL-8334` fixed in 2.416.6 (coordinator ruling: pin the walk world to
September 2026).** The J70/J74 seed now declares its walk month (`WALK_MONTH`, Sep 1–30 2026) and
reopens it through ledger's own reopen (System Admin, reason, audit row) when the main demo's rolling
calendar has closed it; the main demo is unchanged. On a database seeded today (1 October) Send works
again, re-walked at 1440 on PostgreSQL:

| Bill | Review | Sent | Screenshots |
|---|---|---|---|
| First bill, Maria Alvarez Unit C, Sep 12–30 | $393.15 | BL-2609-000001, $393.15 | `8a`, `8b`, `8c` (replaced) |
| Final bill, Maria Alvarez Unit D, Sep 1–18 | $93.47, refund due $56.53 | BL-2609-000002, $93.47 | `9a`, `9b` (new), `5-refund-due.png` (replaced) |

The ⚠ *"Send could not be re-walked"* note above is superseded. J74's eight cases were re-run on the
same kind of fresh database: 8 of 8 pass end to end, case 3 $393.15, case 4 $93.47 with $43.47 still
to pay, case 5 $93.47 with $56.53 refunded (see J74's own journey and screenshots).
