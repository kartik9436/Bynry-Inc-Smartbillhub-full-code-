# Move-out with sewer billed as a share of water — walk of 2026-10-14

**Asked by the PO** (decision log, *"G1–G4 APPROVED"*, items 1 and 4), from a screenshot on Ottumwa Water Works:

* **G1** — step 3 said *"The draft bill is not generated. · Sewer: reading needed · —"* although sewer is billed as *90.00% of Water usage* and has no meter of its own.
* **G4** — step 2: master meter M-MASTER-01 (no last reading) showed *Estimate* ticked with *"Not enough history to estimate."* **and** *"Already read: 22 kgal billed."* in the same row.

Tenant `brazosbend`, signed in as Dana, private copy of the demo database (`smartbillhub_mvsewer`, dropped afterwards), build `2.579.0` + this lane. Account **AC-2026-00041** (Quentin Ortega, Apt 101) is the same shape as the PO's ACC-06: M-MASTER-01 (never read), W-5040 (read 10/07, 2,537 kgal) and sub-meter SM-7040 (never read). The demo data has no sewer, so `setup_sewer_share.py` gave the unit one through the product's own services: sewer switched on, offered at the premises, a `$12.00` sewer base charge code, a schedule *"90% of water usage at $5.00/kgal"* (and, for the second case, *"90% of water charges"*), bound to the unit's plan, and a sewer service point with no meter.

Every walk: move-out date 10/14/2026, reason *Lease ended*, E-5040 left at its prefilled 8,380, **W-5040 typed 2,545**, **SM-7040 typed 10**, **M-MASTER-01 Estimate ticked** (`walk.mjs`).

## Before (code at `417cba896`)

| Screen | What it said |
|---|---|
| Step 2, M-MASTER-01 (`before-step2.png`) | *"Not enough history to estimate."* **and** *"Already read: 16 kgal billed."* (16 here, 22 on the PO's data — it is W-5040's reading for the period either way) |
| Step 3 (`before-step3.png`) | *"The draft bill is not generated. · Sewer: reading needed · —"* — the PO's screen exactly |

## After (this lane)

| Case | Step 2, M-MASTER-01 | Step 3 draft bill |
|---|---|---|
| Sewer = 90% of water **usage** (`after-step2.png`, `after-step3.png`) | *"No history to estimate. Enter a reading."* — once | **Priced, $558.23.** Water 24 kgal (2,521 → 2,545); *sewer usage — 90.00% of water volume* **21.6 kgal @ $5.00 = $108.00**; sewer base (prorated) $5.42 |
| Sewer = 90% of water **charges** (`after-charge-basis-step2.png`, `after-charge-basis-step3.png`) | same | **Priced, $619.51.** *sewer usage — 90.00% of water usage charges* **$168.08** = 90% × ($9.57 + $31.12 + $146.07) |

## Why it happened

* **G1 (`DEF-BIL-10128`).** The step-3 pre-check that names every missing value (added 2026-10-11) asked each *reading* why it had no usage. Metering honestly answers *"no meter"* for sewer. Whether a reading is owed at all is a fact about the *price* (a share of water needs none), and the billing engine only decides that one step later — so the pre-check refused a bill the engine would have priced. It now asks the engine's own first two steps, so the two cannot disagree. A genuinely missing water reading is still named.
* **G4 (`DEF-BIL-10129`).** *"Already read"* matched any reading of the meter's *service*. A bill reads one figure per service point, so W-5040's reading was claimed for M-MASTER-01 and SM-7040, neither ever read. It now asks which meter the reading was taken on; a meter never read says it has no history. The *Not enough history* sentence was the move-in screen's own hint, shown beside the server's answer; on the move-out it is no longer drawn, so the row says one thing.
* **Nothing pre-ticks Estimate.** Step 2 opens every box at the last reading with Estimate off; a meter never read opens empty, and step 2 will not continue until it has a reading or Estimate, so the clerk ticks it.

## Left open

* **M-MASTER-01 is asked for a reading the bill does not use.** On this unit the water figure comes from W-5040's reading alone; the master's estimate changes nothing on the bill, yet step 2 still requires a reading or a tick for it. Whether a building master on a tenant's unit belongs in the required list is a product question, not changed here.
