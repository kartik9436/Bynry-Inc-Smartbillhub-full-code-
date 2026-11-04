# Walk — Move-in searches all units, 2026-10-17

`DEF-CUS-10190` (register row filed by the tool as `DEF-CUS-10165`; the coordinator
reserved 10190–10199 for this lane and renumbers at merge). PO rulings: decision log
*"MOVE-IN SEARCHES ALL UNITS, NOT ONLY VACANT ONES"* and the *"Same day"* confirmation.

**Set-up.** Private copy `smartbillhub_mvin` (`createdb -T smartbillhub`, at the tip's
migrations; dropped afterwards). Backend `runserver` on **8028** (local settings), SPA
`vite build --mode compose` served by `server.mjs` on **8108**. Staff Dana Whitfield,
Brazos Bend, Chromium 1440px. Script: `10-scripts/walk_move_in_all_units_2026_10_17.mjs`
(`STEP=` one of `full`, `direct`, `cut`, `returning`, `searches`, `blocked`, `moveout`,
`finish`). The walk date is 2026-10-17, so the move-in day is **10/17/2026** and the
move-out the server proposes is **10/16/2026** (the day before).

**States the copy did not have, set up on the copy only:** a vacation hold with its
shut-off/turn-on jobs (through `temporary_stop.start_from_account`, the clerk's own
service); a marked-disconnect case with an active payment plan; two cut accounts
(case `cut`, status `Disconnected`); four accounts moved out to make Closed units; one
move-out draft (a Start move-out through the service); one removed unit; a second
utility (Lone Star Ridge) with one unit; and every service point of three sample units
put on one billing cycle (the sample data gives some units two cycles, which billing
correctly refuses to draft a final bill for — `noBillingCycle`).

## Results

| # | Scenario | Result | Figures |
|---|---|---|---|
| W1 | Vacant, owner-billed | **PARTIAL** | Vacant first-occupant move-in works (U-00214-200, Mason Dental → AC-2026-00067, 1 opening read, $45.00 fee to first bill). No vacant unit on the copy is owner-billed *and* has a plan: the 500 Main St units owned by AC-2026-00051 are refused *"This unit has no rate plan yet"* (BR-MET-040, correct). The owner's base charges stopping the day before could not be shown on this data. |
| W2 | Active left unreported, searched by occupant name | **PASS** (after 3 fixes) | Search *Petrov* → SCW-U-016 *Active · Priya Petrov* → warning *"Priya Petrov is still on this unit. Start a move-out for them first."* → Start move-out → move-out wizard on the draft, date **10/16/2026** prefilled → closing reads E-5015 5,205 / W-5015 1,741 → Complete: AC-2026-00016 **Closed 10/16**, final bill **BL-2610-000255 $1,563.25 draft** (10/01–10/16), $270.92 prior + bill = $1,834.17 owed → *Back to move-in* → unit and 10/17 kept, opening reads **5205 / 1741** carried → AC-2026-00058 opened **10/17**, *Opening reads 2 recorded* (0 consumption). No day twice: old last day 10/16, new first day 10/17. The $310 owed / $100 deposit case was not reproducible — no account on the copy holds a deposit on a unit billing can draft for (A-10432, $247.30 owed, $150 deposit, is on two cycles and its final bill is refused; it was left as the W13 unfinished move-out). |
| W3 | Active commercial, searched by meter number | **PASS** | *W-5046* → SCW-U-047 Silver Creek Duplex Holdings → closed 10/16, **BL-2610-000256 $2,551.59** draft, $733.31 prior (the account owed; none on the copy is in credit) → Harbor Cafe AC-2026-00059 opened 10/17, 2 reads (E-5046 21,702). |
| W4 | Sub-metered Mill Pond Apt 104 | **PASS** | SCW-U-044 Tessa Stavros: closing reads E-5043 7,441, W-5043 2,689, **SM-7043 120, SM-7201 95** → **BL-2610-000257 $784.91** → Lena Fourt AC-2026-00060, **4 opening reads** on the same four meters (SM-7043 120 on 10/16 old / 10/17 new). |
| W5 | Vacation hold | **PASS** (after 1 fix) | AC-2026-00018 Rosa Rasmussen, hold 10/17–11/30 with WO-0045 shut-off and WO-0046 turn-on → move-out 10/16: stop **cancelled** (it had not started), **WO-0045 and WO-0046 both cancelled**, BL-2610-000260 $415.28 → AC-2026-00063 opened 10/17. First pass (AC-2026-00015) left the shut-off WO-0041 queued → `DEF-CUS-10194`. |
| W6 | Marked disconnect on a payment plan | **PASS** | AC-2026-00019 Sam Sandoval, case DSC-26-0901 scheduled, plan $310.00 × 6 active → move-out 10/16: case **stopped, reason `customer_left`, 10/16**; plan **still active on the old account**; BL-2610-000261 $469.85, balance at close **$569.39** stays owed → Iris Calder AC-2026-00064. (A-11340 Northwind could not close: its unit is on two cycles — left as an unfinished move-out.) |
| W7 | Disconnected | **PASS** (after 1 fix) | A-11933 Nadia Iqbal, cut 10/12 → row *Disconnected* → *"Iqbal, Nadia was disconnected here. Close out their account first."* → Start close-out → close-out: account **closed at the cut date 10/12**, $402.15 stays owed (collections case DSC-26-0007 opened) → back to the move-in → Grace Mbeki AC-2026-00066 opened 10/17, **reconnect job WO-0048** raised for the new account, due 10/17. First pass (A-11902) came back empty → `DEF-CUS-10195`. |
| W8 | Closed, different person | **PASS** | SCW-U-010 *Closed · Jonas Janssen* (closed 10/15, owes $341.99) → Tom Ellery AC-2026-00068 opened 10/17, 2 opening reads. |
| W9 | Closed, returning customer | **PASS** (after 1 fix) | SCW-U-024 Xander Xanthos (closed 10/15, owes $454.73) → *Search customer ID* → *Lived here last C-00024* → *Same person · link* → *Reopen AC-2026-00024 / New account*, old balance *Carry it* → **AC-2026-00024 reopened** 10/17, C-00024 linked, 2 reads. Done screen listed services twice → `DEF-CUS-10196`. |
| W10 | Move-out in progress | **PASS** | SCW-U-012 (draft started through the service): *Move-out in progress · Finish the move-out first.*, greyed, no *Use*. The server refuses the move-in and a second Start move-out with the same key. |
| W11 | Pending activation | **PASS** | SCW-U-302: *Pending activation · Waiting for activation.*, greyed, no *Use*. |
| W12 | Removed | **PASS** | *Apt 103* finds only Mill Pond's SCW-U-043; the removed Riverbend U-00318-103 is not listed. |
| W13 | Move-out started from the move-in, unfinished | **PASS** | SCW-U-201 Miller (draft left unfinished) and SCW-U-204 Northwind: *Move-out in progress*, blocked. Finishing unblocks: every W2–W6 unit read *Closed* and selectable the moment its move-out completed. |
| W14 | Search by address / unit no / premise no / meter no / name; vacant first | **PASS** | *Bluestem* → vacant U-00101-B first, then active U-00101-A · *SCW-U-044* · *P-00009* · *W-5046* · *Kirchner*, one row each, new occupants shown (e.g. P-00009 → Jordan Newcomb, W-5046 → Harbor Cafe). The empty search lists vacant and closed units before occupied ones (pending-activation units waiting on a New Connection sort among the vacant ones, greyed). |
| W15 | Another utility's units | **PASS** | Lone Star Ridge's *77 Kestrel Ridge Rd · Ridge Cabin 9* → 0 rows from Brazos Bend. |

**Ledger after the walk:** 491 journal entries, **0 unbalanced**.

## Bugs found on the walk and fixed in this lane (each filed first, red test first)

| Lane id | Tool row | What was seen | Shot |
|---|---|---|---|
| DEF-CUS-10191 | DEF-CUS-10176 | *Back to move-in* carried `5894.000000` dated the closing day; the read door filed it as the same reading → *Opening reads 0 recorded* | `w2-6-back-to-move-in.png`, `w2-9-move-in-done.png` |
| DEF-CUS-10192 | DEF-CUS-10177 | the old long *"This account still holds the unit…"* strip drawn under the new warning | `w2-2-warning.png` |
| DEF-CUS-10193 | DEF-CUS-10185 | first Continue on the resumed move-in did nothing (stale cached account) | `w3-7-held.png`, `w5-7-held.png` |
| DEF-CUS-10194 | DEF-CUS-10186 | ending the hold left the shut-off job WO-0041 queued | (data check, W5 first pass) |
| DEF-CUS-10195 | DEF-CUS-10187 | back from the close-out the move-in was empty and autosaved empty | `w7-7-held.png` |
| DEF-CUS-10196 | DEF-CUS-10188 | done screen after a reopen: *Water · Electric · Water · Electric* | (W9 first pass) |

Found and fixed before the walk was recorded (own unshipped code, not filed): the
search asked for 10 rows a page and `core.pagination` serves at least 50, so the pager
would have counted wrong — the page is 50.

## Seen, not fixed (not this lane's, or needing a ruling)

* A move-in dated **after today** cannot carry opening reads dated the move-in day: the
  shared reading component refuses a read date after today (*"Read date is after
  today."*). The walk moved in on the walk date for that reason.
* The move-in's done screen does not mention the **reconnect job** the server raised
  for a cut unit (it is on the response as `reconnect`).
* Sample data: several units sit on two billing cycles, so their final bill is refused
  (A-10432, A-11340) — correct behaviour, but those two accounts could not be walked
  through to a close.
