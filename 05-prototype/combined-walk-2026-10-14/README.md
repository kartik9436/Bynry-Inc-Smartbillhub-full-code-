# Combined walk — the October lanes together, 2026-10-14

Decision log *"EVERY ONE OF THE 77 TASKS IS WALKED END TO END IN A BROWSER"*: after
the lanes merged, one walk runs their features **in the order a utility meets them, on
one copy**, so a seam between two lanes is walked, not assumed.

**Set-up.** Build 2.581.0 (`bab1fbdc8`). Private copy `smartbillhub_e2e`
(`createdb -T smartbillhub`, migrated to the tip, dropped afterwards). Backend on 8015
(`runserver`, local settings, jobs eager), the SPA built with `vite build --mode walk`
(a local mode: the bundle calls its own origin) served by `server.mjs` on 8095. Tenant
**Brazos Bend** (`brazosbend`, America/Chicago), staff Dana Whitfield (System Admin)
and Sam Reyes (Billing Clerk), portal Ana Alvarez (`alvarez0@example.invalid`,
AC-2026-00001). Passwords were set on the copy only; the portal's *is live* switch was
turned on on the copy (it was off, so the portal sign-in page said *"We are not open
online yet"*). 1440 px.

**The clock.** Steps 3–9 need days to pass (a stop that starts, a month to bill). The
backend ran under a scratch launcher that shifts `django.utils.timezone.now` by N days
(not committed); the browser's clock was moved to the same day where a screen compares
dates (`CLOCK=` on the move-out and counter scripts, `page.clock`). Utility days used:
**10/14** (steps 1–3 ask/approve), **10/16** (the stop clock), **10/24** (restart),
**11/02** (steps 4–9). The copy's `created_at` columns are database time and were not
shifted.

Scripts: `10-scripts/combined_walk_2026_10_14_*.mjs` (new: shared lib, step 2 reading,
closing reads, send a draft) plus the lanes' own walks, reused —
`cr181_returning_customer_walk.mjs`, `cr182_high_consumption_walk.mjs`,
`cr183_temporary_stop_walk.mjs`, `def_cus_10093_move_out_final_draft_walkthrough.mjs`,
`rate_schedule_edit_reopen_walk.mjs`, `def_pay_10140_counter_second_session_walkthrough.mjs`,
`cr184_receivables_by_service_walkthrough.mjs`, `cr185_owner_summary_walkthrough.mjs`.
The bill run and the two corrections were driven screen by screen.

Before anything: 246 bills, 491 journal entries / 2,686 lines, receivables (1200)
**$27,885.40**, 0 unbalanced entries. After step 9: 338 bills, 629 / 3,561,
receivables **$46,991.36**, **0 unbalanced entries** — every entry the walk wrote
balances.

## Results

| # | Step | Result |
|---|---|---|
| 1 | Returning customer, Carry it | **PASS** — with a seam defect found in step 4 (`DEF-CUS-10154`) |
| 2 | 10× reading → portal alert, one email | **PASS** |
| 3 | Temporary stop → hold → early restart | **PASS** (open item: the turn-on visit keeps its old date) |
| 4 | Bill run; high reading billed; part-hold account; pricing check | **FAIL → fixed** (`DEF-CWP-10153`); double billing of the reopened account (`DEF-CUS-10154`, not fixed) |
| 5 | Fix a bill + bulk price mistake → case numbers | **PASS** — CC-2026-024 and CC-2026-025 on all three screens |
| 6 | Rate schedule edit, seasonal | **PASS** 9/9 |
| 7 | Move-out, sewer % of water, balance to owner | **PASS on a second unit**; the first unit cannot move out (`DEF-BIL-10155`), and the final bill prices the wrong water meter (`DEF-BIL-10156`) |
| 8 | Counter open/close/open, cash, force close | **PASS on the screens, FAIL in the books** — the cash moved nothing (`DEF-PAY-10157`) |
| 9 | Receivables by service + Owner summary vs Who owes you and the ledger | **PASS for totals; FAIL at the seam with step 7** (`DEF-REP-10158`, `DEF-REP-10159`) |

## 1 · Returning customer moves back in (CR-181)

*Set-up through the screens:* Viktor Valdez's AC-2026-00022 (SCW-U-022) was moved out
on **10/12** (W-5021 1,802, E-5021 3,937; shortfall *Collect*) → final bill
**BL-2610-000251 $205.38, Draft**, move-out MVO-26-0002 (`S1-pre-viktor-move-out-*`).

As Sam on 10/14, Move-ins › New, SCW-U-022: step 1 *Owes $168.18*; search by name +
phone → **Same name and phone** + **Lived here last**; *Reopen AC-2026-00022 · Owes
$168.18*; *Must pay first* refused by name (*Pay the old balance first.*); **Carry
it** → Review *Reopened AC-2026-00022 · $168.18 carried* → Completed **MVI-26-0023**
on the same number; details and the Move-ins list read *Reopened* (`S1-1` … `S1-7`).

*Seam seen:* the first attempt typed opening reads **below** the move-out's final reads
(1,800 / 3,880 vs 1,802 / 3,937): refused by BR-MET-129, the screen saying *The
move-in was not completed.* (`S1-x-refused-reads-below-final.png`). Correct.

| Record | Figure |
|---|---|
| `accounts` AC-2026-00022 | active · opened 10/14 · closed — · receivables **$168.18** (carried) |
| `move_in_reopenings` | carry · **168.1800** · was 08/01 → 10/12 |
| `move_records` | MVO-26-0002 move_out 10/12 · MVI-26-0023 move_in 10/14 |
| `audit_log` | `account.move_out.shortfall_decided`, `account.closed`, `account.reopened`, `account.moved_in`, `move_in.reopen_balance` |
| Final bill | **BL-2610-000251 $205.38 still a DRAFT on the reopened account** — see step 4 |

## 2 · A 10× reading (CR-182)

As Dana, Reads › *+ Add reading*: W-5000, 10/13, dial **1,104** (80 kgal against a
trailing 8 kgal a month) → posted (`S2-1`, `S2-2`). Ana's portal Home: **HIGH
CONSUMPTION ALERT · Water reading on Oct 13, 2026: unusually high. · See your
readings**; Readings tags **exactly one** row (`S2-3`, `S2-4`).

| Record | Figure |
|---|---|
| `meter_reads` W-5000 10/13 | 80 kgal · status `high` · committed |
| `outbound_messages` `usage_alert` | **exactly 1**: email · queued · `email_high_usage_alert` · to alvarez0@… · not held |

(The walk's own first attempt typed the date in the wrong format;
nothing was written.)

## 3 · Temporary stop (CR-183)

Ana asks on the portal for **10/16 → 10/31** (15 days) → **SR-26-0061**; Dana approves
with **Field visit needed** → *Stop scheduled 10/16/2026 – 10/31/2026 · Base charge
only · Visits WO-0041 · WO-0042* (`S3-a-*`; the lane script's own *"on vacation_hold"*
line reads FAIL because the stop starts in the future — expected). The clock run for
**10/16**: `started: [the hold]`; run again: `started: []` (idempotent) → account
`vacation_hold`. On **10/24** Ana presses *Restart my service now* → **SR-26-0062**;
Dana approves → **Active** (`S3-b-*`).

| Record | Figure |
|---|---|
| `temporary_stops` | stop 10/16 · restart **10/24** · **ended**, ended early · field visit · WO-0041 / WO-0042 |
| `service_requests` | SR-26-0061 approved `temporary_stop` · SR-26-0062 approved `restart_now` |
| `audit_log` | requested → approved → field_visit_raised → `account.temporary_stop_started` + started → restart_requested → ended_early → `account.temporary_stop_ended` + ended |
| `work_orders` | WO-0041 disconnect due 10/16 · **WO-0042 reconnect still due 10/31** after the 10/24 restart — CR-183's own open item 1, not refiled |

## 4 · The October bill run

Closing reads posted 10/31 through Reads (`S4-0-*`). As Dana on 11/02, Billing › Run:
*October 2026 Silver Creek*, CY-007, 10/01–10/31, bill date 11/02 → **RUN-0003**.
Check: 52 accounts checked, 45 ready, 7 need a decision, 3 warnings, and **PRICING
CHECK · 1 bill differs · Show bills** (`S4-1`, `S4-1b`). Sign off with the five ticks →
Send → **45 bills sent, $18,995.01**, due 11/22 (`S4-2` … `S4-4`).

| Record | Figure |
|---|---|
| Receivables | **$27,885.40 → $46,880.41** = + $18,995.01, the run exactly; 0 unbalanced entries |
| Ana BL-2611-000252 **$991.46** | electric 1,350 kWh; water **94 kgal** (8 + **80** + 6 — the high reading is billed, 79 kgal in tier 3 = $669.92); base $12.00 + $8.00 for the **whole** month although 10/16–10/23 was on hold; one entry, 6 lines, balanced. That is CR-183 judgment 11 exactly: a period partly on hold is billable, base runs every day, the meter prices the usage |
| Viktor BL-2611-000269 **$292.15** | see the defect below |

**FAIL → fixed: `DEF-CWP-10153`.** After the run Ana's Home showed **no** *Your last
bill is higher than usual* and the bill no *High usage*: both read only each service's
closing read (10/31, 6 kgal, low), never the bill's `chain_read_ids` where the 10/13
reading sits. Fixed in `apps/portal/seams/billing_seam.py`; test
`test_def_cwp_10153_a_high_reading_partway_through_the_period_still_marks_the_bill`
red first (`assert False is True`), then the file green on SQLite (12) and PostgreSQL
16 (12). Re-walked on the rebill after step 5: **HIGH USAGE · Your last bill is higher
than usual. · See why →**, the bill says **High usage** (`S4-5-after-fix-*`).

**Not fixed: `DEF-CUS-10154` — the reopened account is billed twice for 10/01–10/12.**
BL-2611-000269 measured from the 09/29 billed reads (1,123 kWh, 15 kgal — the 10/09 and
10/12 reads included) with tier blocks and base prorated over 18 days, while the
move-out's final bill **BL-2610-000251 $205.38** (760 kWh, 11 kgal for 10/01–10/12)
is still a sendable draft. Nothing on the reopen, the run's Check or the bill says so.
Needs a product decision (void the draft on reopen, or refuse the reopen until it is
sent) — reported, not built.

## 5 · Corrections get case numbers (G3)

*One customer:* Kaya Kowalski AC-2026-00011, BL-2611-000260, **Goodwill credit $10.00**
→ Send → *Corrections so far* **CC-2026-024 · Credit only · Waiting for approval** →
approve → **1 bill corrected · CM-0146 · −$10.00 · Case CC-2026-024**; the bill page's
*Corrections* tab reads **Case CC-2026-024** (`S5-1` … `S5-5`).
*Bulk, a price mistake:* 10/01–10/31, *Tax · Local*, *A charge was missed* **PAPER
$2.00** → 45 bills, **+$90.00**, *Payments moved to new bills $101.63* → Send →
**CC-2026-025** → approve → **45 bills corrected · 0 failed · Case CC-2026-025**; Ana's
BL-2611-000252 page: *case CC-2026-025 · CM-0147 · replacement BL-2611-000297*
(`S5-6` … `S5-10`).

| Record | Figure |
|---|---|
| `correction_cases` | CC-2026-024 done `account` `credit_only`; CC-2026-025 done `price_mistake` `restatement` (the series continues from the 23 backfilled) |
| Ledger | CM-0146: DR 6900 $10.00 / CR 2400 $10.00 (credit held, receivables unchanged); bulk: receivables **+$90.00** exactly; 0 unbalanced |

## 6 · Rate schedule edit (seasonal)

`rate_schedule_edit_reopen_walk.mjs` **9 of 9 PASS**: step 2 Summer 12.5000 / Winter
9.7500; Review $12.50 / $9.75; *Effective from* proposed **2026-11-01** (the browser's
tenant-zone day, 10/14); 0 changes; one save; new version from 11/01 open-ended,
previous ends 10/31 (`S6-*`).

## 7 · Move-out, sewer as a share of water, balance to the owner

`setup_sewer_share.py` gave the unit sewer at **90% of water usage** ($5.00/kgal,
$12.00 base). Moved out on 11/02, shortfall **Tie it back** to owner **AC-2026-00053**
(Mill Pond Apartments LP).

**AC-2026-00041 (Apt 101) cannot move out — `DEF-BIL-10155`.** Every way step 2 lets
the clerk answer its four meters, step 3 says *The draft bill is not generated. ·
Water: reading needed · M-MASTER-01, SM-7040, W-5040* and Complete refuses *The account
was not closed.* (`S7-x-AC41-*`). Measured on the preview: Estimate on the master →
`estimate_no_history`; a typed reading on the never-read sub-meter → `reading`; only
W-5040 + E-5040 → priced $112.15. The move-out lane priced the same unit on 10/14
because its 10/07 water reading was then still unbilled; the October run billed it.
Every Mill Pond unit has a never-read sub-meter (Apt 103 SM-7042 estimate →
`estimate_no_history`, same failure).

**AC-2026-00044 (Apt 104, Tessa Stavros) — PASS**, after posting a 10/31 reading on its
two sub-meters through Reads (`S7-0-subreads-*`, the workaround): W-5043 2,645, E-5043
+60, SM-7043 7, SM-7201 6 → step 3 priced, *sewer usage 0.9 kgal @ $5.00*, prior
$344.26 + final bill **$20.95** = **Short by $365.21** → *Tie it back* → Completed,
final bill **BL-2611-000342 $20.95 Draft** (`S7-step*`, `S7-done`). Then Billing → the
draft → Approve → **Issued**; the account reads **To the owner $365.21 · Posted**
(`S7-send-*`).

| Record | Commit | After the bill is sent |
|---|---|---|
| `balance_tie_backs` | **pending**, preview 365.21, final bill BL-2611-000342, nothing posted | **posted 365.21**, JE-110226-0629 |
| AC-2026-00044 receivables | $344.26 (unchanged) | **$0.00** |
| AC-2026-00053 (owner) | $2.00 | **$367.21** (+365.21) |
| Total receivables | $46,970.41 | **$46,991.36** = + $20.95, the bill alone; the transfer DR 1200 owner / CR 1200 tenant 365.21 nets to zero |

**`DEF-BIL-10156` (money, not fixed):** the final bill priced water at **1 kgal** — the
reading it used is **SM-7201's** (5 → 6), not the unit meter W-5043's **6 kgal**, which
stays committed and unbilled on a closed account; sewer followed it (0.9 kgal). The
October cycle bill for the same unit priced W-5043.

## 8 · Counter: open, close, open again, cash, force close (G2)

On 11/02: Start counter **CTR-261102-DW**, count, close; start again the same day →
**CTR-261102-DW-2** in the address and the page; Record payment *Goes into counter
CTR-261102-DW-2*, **$25.00 cash on Ana** (AC-2026-00001, from step 4); the counter
shows 1 payment; Force close → *CTR-261102-DW-2 · Forced* (`S8-*`).

**FAIL in the books — `DEF-PAY-10157`:** PY-261102-0087 is **processing** with no
journal entry; Ana's receivables stay **$1,181.38**, still after the force close. The
form leaves *Clearing date* empty for Cash and the server then allocates and posts
nothing, while the form's Check panel says *$25.00 goes to this account. It meets the
oldest bills first.* All 13 other cash payments on the copy are cleared with entries.

## 9 · Reports against the books

`cr184_receivables_by_service_walkthrough.mjs`, as-of **2027-03-31**: library report
Electric $20,167.32 · **Sewer $5.27** (the step-7 bill) · Water $7,406.35 · Taxes
$1,750.25 · Fees $1,044.35 · Other $96.95 = **$30,470.48, all over 90 days, 51
debtors**; the builder's Receivables subject, Save as, the custom report, Water
**$7,406.35** = Who owes you › Service: Water (`S9-a-*`, page text in
`S9-a-walk-results.json`).

| Check | Figure |
|---|---|
| Report total vs open issued bills | **$30,470.48 = $30,470.48** (146 issued bills $68,028.27 − allocations $37,557.79) |
| Finance › *Still owed* vs ledger 1200 | **$46,991.36 = $46,991.36**, 64 accounts |
| Report vs books | differ by $16,520.88; the report says *Rows do not match the books.* (imported balances and held credits, as the CR-184 walk found) |
| Owner summary, Mill Pond, 10/01–11/30 | **Grand total $2.00**, one property, the paper-fee rebill (`S9-b-*`; the lane script's three FAIL lines are its fixture's $85.00, not this copy's) |

**`DEF-REP-10158`:** the owner's summary says **$2.00** while the owner owes
**$367.21**, $365.21 of it moved onto them by step 7 in the same period — the summary
reads bills only and the transfer is a journal entry; nothing on the screen says so.
**`DEF-REP-10159`:** Receivables by service still names the **closed tenant
AC-2026-00044 as owing $365.21** (its bills stay open) and the owner as owing $2.00;
Who owes you says tenant $0.00, owner $367.21. Totals agree, the debtor does not.

## Defects

| Id | What | State |
|---|---|---|
| `DEF-CWP-10153` | High reading partway through a period: no *High usage* / no *higher than usual* | **fixed** (red → green, SQLite + PostgreSQL) |
| `DEF-CUS-10154` | Reopen keeps the move-out's draft final bill; the cycle bills the same days again | open — product decision |
| `DEF-BIL-10155` | Multi-meter unit cannot move out after a cycle bill | open |
| `DEF-BIL-10156` | Final bill prices water from a sub-meter, unit meter left unbilled | open — money |
| `DEF-PAY-10157` | Counter cash stays processing; nothing posts | open |
| `DEF-REP-10158` | Owner summary omits the balance moved to the owner | open — product decision |
| `DEF-REP-10159` | Receivables by service names the departed tenant after a transfer | open — product decision |

Noted, not filed: CR-183's open item 1 (WO-0042 keeps 10/31 after a 10/24 restart);
the goodwill credit is held in 2400 so *Owed today* on the bill page stays $641.93 and
Who owes you nets it ($633.93) — the two screens differ by the held credit, by design
as far as the records show.
