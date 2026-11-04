# Walk — reading gaps C, B and Enter opening read (Accounts lane), 2026-10-17

`DEF-CUS-10165` (Move-in step 1 read date) · `DEF-CUS-10166` (Mark as cut: closing
reading + read date + Fetch) · `DEF-CUS-10167` (Enter opening read: read date + Fetch) ·
`DEF-CUS-10168` (Mark as cut stayed open after the cut — found on this walk, fixed).
Decision log 2026-10-17, *"WHERE A USER ENTERS A METER READING"*. All four stay **open**
for the coordinator to close at release.

**Set-up.** Private copy `smartbillhub_rdacc` (`createdb -T smartbillhub`, already at the
tip's migrations, dropped afterwards). Backend `runserver` on **8023** (local settings),
SPA `vite build --mode compose` served by `server.mjs` on **8103**. Staff Dana Whitfield,
Brazos Bend, 1440px, Chromium. Today = 10/17/2026. Script:
`10-scripts/walk_reading_gaps_accounts_2026_10_17.mjs` (`WR_SKIP`, `WR_UNIT`,
`WR_STEP1_ONLY`, `WR_ASSETS`).

Two preconditions were made on the copy, because the sample tenant had neither:
* **A cut that can be marked.** The only scheduled cases (`DSC-26-0001/0002`) had no
  service chosen and sat on units with no meters. `DSC-26-0002` was pointed at
  `AC-2026-00003` (meters `E-5002`, `W-5002`) with `services_cut = [electric, water]` by
  SQL. Everything after that went through the screens.
* **A move-in waiting on a read.** None existed; one was committed through the product's
  own door (`POST /units/{Apt 102}/move-in`, no readings) → `MVI-26-0022`, moved in
  10/14/2026, *Waiting on a read* on `M-7302`.

**Fetch.** Brazos Bend holds a Neptune 360 connection with no live client bound
(`integrations/meter_reading.py`: `READING_CLIENTS` is empty on this deployment), so every
Fetch answered **"Neptune 360 connected. No reading fetched."** and left the box empty. No
simulator exists, so no real fill could be shown in a browser; the fill (value + the
meter's own date, date box locked) is proved in the routed DOM tests instead.

## C · Move-in step 1 — PASS

| Shot | What it shows |
|---|---|
| `C1-move-in-future-read-date-refused.png` | Unit U-00102, move-in 10/15/2026, M-7450 reading 9150; Read date opened on **10/15/2026**, changed to 10/30/2026 → **"Read date is after today."** No Estimate control. |
| `C2-move-in-before-last-refused.png` | Read date 07/15/2026, before the last reading (08/01/2026) → **"Earlier than the last reading."** |
| `C3-move-in-read-date-10-12-and-fetch.png` | Read date **10/12/2026** — before the move-in day, lawful; Fetch says *Neptune 360 connected. No reading fetched.* |
| `C4-move-in-completed.png` | The same steps on **U-00318-101** (M-7301), completed: `AC-2026-00058`, Mensah, Kofi. |
| `C5-read-history-opening-read-dated-10-12.png` | M-7301 → Reads: **10/12/2026 · 9150 · 58 kWh · manual** — the reading stored with the clerk's date, not the move-in day. |

Database read-back: `M-7301 | 2026-10-12 | 9150 | move_in | manual`.

## B · Disconnect → Mark as cut — PASS

| Shot | What it shows |
|---|---|
| `B1-mark-as-cut-required-and-fetch.png` | One row per meter on the cut services (W-5002, E-5002): reading + unit, read date opening on the cut date **10/13/2026**, Fetch, *No access to …*. Pressing *Mark as cut* empty → **"Enter the reading."**, nothing posted. Fetch → *Neptune 360 connected. No reading fetched.* No Estimate. |
| `B2-mark-as-cut-readings-typed.png` | E-5002 **5810**, read date **10/12/2026**; W-5002 **1124**, date left on the cut date. |
| `B3-case-after-cut.png` | The case after the cut: *Off*, the dialog closed (`DEF-CUS-10168`). |
| `B4-read-history-E-5002.png` · `B4-read-history-W-5002.png` | The closing readings in each meter's read history. |

Database read-back: `E-5002 | 2026-10-12 | 5810 | disconnect` · `W-5002 | 2026-10-13 | 1124 |
disconnect`; account status `disconnected`, `cut_on` 2026-10-13. **The cut bill priced the
closing readings:** `BL-2610-000251` (10/01–10/13) bills **1,336 kWh** = 1,300 (to 5774 on
10/08) + **36** (to the typed 5810), and **18 kgal** water = 13 + **5** (to the typed 1124).
Before this lane `commit_cut` raised that bill before posting `final_reads`, so the same cut
would have billed 1,300 kWh and 13 kgal and left the typed readings for a later bill.

## Move record → Enter opening read — PASS

| Shot | What it shows |
|---|---|
| `M1-opening-read-future-refused.png` | `MVI-26-0022`: M-7302 **6520**, Read date opened on the move-in date **10/14/2026**, changed to 10/30/2026 → Save holds with **"Read date is after today."** Fetch answered honestly. |
| `M2-opening-read-dated-10-15.png` | Read date **10/15/2026**. (The old refusal line stays under the field until Save is pressed again — `FormModal`'s re-validate-on-click behaviour, BR-SHL-017; the save then succeeds.) |
| `M3-move-record-after-save.png` | The record after saving. |
| `M4-read-history-M-7302.png` | M-7302 → Reads: **10/15/2026 · 6520**. |

Database read-back: `M-7302 | 2026-10-15 | 6520 | total | move_in`. Metering's event door
also wrote an `export` register row for M-7302 with no value on the same date — metering's
own behaviour for that meter, outside this lane, noted for the Reads lane.

## Torn down

Servers on 8023 and 8103 stopped by PID; `smartbillhub_rdacc` dropped.
