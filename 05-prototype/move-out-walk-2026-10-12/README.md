# Move-out end-to-end walk — 2026-10-12

**Asked by the PO:** *"Can you also do end to end walk on move out including bill generation - take all kind of accounts to be move out cases - user reported bills are not yet generated during move out process"*.

Build `2.572.0` + this lane's fixes, tenant `brazosbend`, signed in as Dana (System Admin), on a private copy of the demo database. Every move-out was done through the screens (Accounts → account → Move-out, four steps, Complete). Move-out date **10/12/2026** for every case (mid-cycle: the Silver Creek cycle runs monthly from the 1st, so the closing window is Oct 1–12 = 12 of 31 days).

## The finding, in one paragraph

**The report is correct and it affects every move-out in every environment.** The wizard works out the final bill on step 3 (a draft, e.g. **$186.36** for Ana Alvarez) but it does not create it, and nothing creates it afterwards: no bill run bills a closed account, there is no background job for it (this is not a local-setup gap — nothing is queued), and once the account is closed **Billing → One-time bill → Final refuses it** (*account_already_closed_for_billing*). So the closing days are never billed. The completion screen then told the clerk *"No final bill was raised. Billing raises it on its run."* — the second sentence was false, and is the reason a user waits for a bill that cannot come. The PO ruled on 20 Sep (decision log, ruling 10) that step 3 should **link out to the real invoice** and that the invoice must be raised **before** the close; that link was never built. Proved on the same data that raising the final bill first works end to end (AC-2026-00002, one-time Final for Oct 1–12, **$220.96**, base prorated $4.65 + $3.10, journal balanced $220.96/$220.96, 3 delivery rows, then the move-out completed). **How to fix it is a product choice, and is put to the PO in the lane report** (`DEF-CUS-10093`).

## Scenarios

Final bill column = what step 3 showed. **No scenario produced a final invoice** — that is `DEF-CUS-10093`, so the *Final bill* check is FAIL on every completed row.

| # | Account type | Account | What was done | Final bill (step 3) | Account | Unit | Reading saved | Final invoice | Ledger | Deposit / refund | Delivery | Audit | No DB id on screen | Defects |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Residential single-family, owes $158.10, electric + water | AC-2026-00001 | readings typed (+50 kWh, +6 kgal) | draft **$186.36** | PASS closed 10/12, reason recorded | PASS vacant | PASS 2 reads, flow move_out | **FAIL** none | n/a (no bill) | n/a (none held) | PASS move-out letter queued (email + print) | PASS account.closed + reads | PASS | 10090 |
| 2 | Residential, $150 deposit, $0 balance (refund case) | A-10650 | readings +20 | **not generated — "No billing cycle"** (ruled 2026-10-01) | PASS | PASS | none (no prior read to prefill) | **FAIL** | n/a | **FAIL** deposit still $150 on file, no refund (needs the final bill) | PASS | PASS | PASS | 10090 |
| 3 | Multi-family unit under a building master, owes $517.65 | AC-2026-00041 | readings +15, master + sub-meter ticked Estimate | draft **$376.94** | PASS | PASS | PASS 2 | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090, 10092 |
| 4 | Commercial small commercial, **demand meter**, owes | AC-2026-00047 | readings +30 | draft **$1,377.52** | PASS (after fix) | PASS | PASS 2 | **FAIL** | n/a | n/a | PASS | PASS | PASS | **10091 (fixed)**, 10090 |
| 5 | Commercial in credit, demand meter | AC-2026-00048 | readings +5 | draft **$891.17** | PASS (after fix) | PASS | PASS 2 | **FAIL** | n/a | n/a | PASS | PASS | PASS | **10091 (fixed)**, 10090 |
| 6 | Municipal | AC-2026-00049 | readings +40 | draft **$227.04** | PASS | PASS | PASS 2 | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090 |
| 7 | Light industrial, demand meter | AC-2026-00050 | readings +50 | draft **$5,106.03** | PASS (after fix) | PASS | PASS 2 | **FAIL** | n/a | n/a | PASS | PASS | PASS | **10091 (fixed)**, 10090 |
| 8 | Commercial master account (5 open tenants, 26 empty units billing) | AC-2026-00051 | tried | — | PASS **refused at step 1** with its reason (ruled: refuse) | — | — | — | — | — | — | — | PASS | — |
| 9 | Residential on **autopay**, $150 deposit, owes $247.30 | A-10432 | readings +20 | **not generated — "No billing cycle"** | PASS | PASS | PASS 2 | **FAIL** | n/a | **FAIL** deposit not applied | PASS | PASS | PASS | 10090 |
| 10 | **Vacation hold** | A-11512 | readings +5 | **not generated — "This bill cannot be priced"** (no cycle/plan on the sample account) | PASS (move-out allowed) | PASS | none to prefill | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090 |
| 11 | **Pending activation** | A-12048 | tried | — | PASS **refused at step 1**: *does not hold its unit* | — | — | — | — | — | — | — | PASS | — |
| 12 | **Marked disconnect**, owes $8,240 | A-11340 | readings +5 | **not generated — "cannot be priced"** | PASS (move-out allowed: still an occupant) | PASS | none to prefill | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090 |
| 13 | **Closed** | AC-2026-00042 | tried | — | PASS **refused at step 1**: *does not hold its unit* | — | — | — | — | — | — | — | PASS | — |
| 14 | Residential, box left at its **prefilled last reading** (Estimate not ticked) | AC-2026-00039 | Complete with the prefill | draft **$134.39** | PASS | PASS | PASS 2 — at the last value, so **zero usage** for the 12 days (the prefill the PO kept on 2026-10-11, `OQ-394`) | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090 |
| 14b | Residential, **estimated** final reading | AC-2026-00040 | Estimate ticked on both meters | draft **$290.32** | PASS | PASS | PASS 2 reads `estimated`, method trailing 3-period average | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090 |
| 15 | Residential **in credit** (−$58.56) | AC-2026-00009 | readings +10 | draft **$325.04**; credit applied, short by $207.92 | PASS | PASS | PASS 2 | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090 |
| 16 | Multi-family, after the sentence fix | AC-2026-00043 | readings +5 | draft **$238.34** | PASS | PASS | PASS | **FAIL** | n/a | n/a | PASS | PASS | PASS | 10090 (sentence now true) |
| C | Control: **final bill raised BEFORE the move-out** (by API, the One-time Final screen's own door) | AC-2026-00002 | One-time Final Oct 1–12, sent, then move-out | invoice **BL-2610-000122 $220.96**, base prorated $4.65 + $3.10 | PASS | PASS | PASS | **PASS** final, issued, period ends 10/12 | **PASS** JE balanced 220.96 / 220.96 | n/a | PASS 3 rows | PASS | — | — |

**Not covered, and why:** moving a balance to the master/owner — step 4's *Transfer* path needs a landing, which needs the final bill (10090), so it could not be reached honestly; a field-visit final reading — the work-order table is on step 2 and was left at *No visit needed*; dunning stop — the product states it has no collections tables.

## Defects

| Id | What | State |
|---|---|---|
| `DEF-CUS-10093` | A move-out never produces a final bill; afterwards it cannot be produced; the screen said billing would raise it | Sentence corrected (server + 11 catalogues), `90823a5a3`. **The bill itself waits for a PO decision** — see the lane report |
| `DEF-MET-10094` | Demand meters: the reading row opened on the kW register while the reading posts to kWh, so every commercial/industrial move-out with a demand meter was refused at Complete | **Fixed** `e5bee3e58` — the row now follows the total register; walked again: rows 4, 5, 7 complete |
| `DEF-BIL-10095` | Step 3 prints a prorated tier quantity with 28 decimals (`193.5483870967741935483870968 kWh`) | Filed, open (needs the display places for a computed quantity decided) |

## Rulings checked (decision log)

* 2026-10-12 — move-out does not write off: step 4 offers no write-off. Confirmed on screen.
* 2026-10-11 — refunds have no dispute hold: could not be exercised, no final bill means no landing.
* Reading box: the coordinator's brief said *starts empty*; the decision log's 2026-10-11 row says **`OQ-394` stands — the box opens with the last reading**, and the app does that. Left as the log says.

## Tests

* New: `06-backend/tests/test_def_cus_10093_move_out_final_bill_claim.py` (RED on the old sentence, GREEN now); two `test_def_met_10091__*` cases in `tests/test_w5_unit_reads.py` (RED on HEAD: `'demand' == 'total'`).
* Golden suite `tests/golden` and the 13 move-out files: 223 passed. **8 reds were already red on HEAD before this lane** — re-run with this lane's code reverted, same 7 failures + 1 error: `test_cr056_w6_*` tc4/tc6/tc7, `test_us_cus_004_tc1` (+ error), `test_tc_mvo_2/3/8`; and `test_w5_tc9` (`plan.base_charges` is `None`) in `test_w5_unit_reads.py`. None touches this lane's lines; reported, not fixed.
