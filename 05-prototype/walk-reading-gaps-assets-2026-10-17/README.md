# Walk — reading gaps A, F, D (2026-10-17)

PO ruling 2026-10-17, decision log *"WHERE A USER ENTERS A METER READING"* (gaps 2, 4, 5, 7)
and *"READING GAPS A, F, D: FOUR JUDGMENTS"*. Defects `DEF-AST-10182` (A), `DEF-MET-10183` (F),
`DEF-WRK-10184` (D). Every reading screen here uses the shared `MeterReadingEntry` (reading +
read date + Fetch), PO: *"use same code components"*.

**Set-up.** A private copy of the local database (`smartbillhub_rdast`, dropped afterwards);
this branch's backend `runserver` on **8024** (local settings); the SPA built with
`vite build --mode compose` and served by `server.mjs` on **8104**. Chromium at 1440px. Tenant
Brazos Bend, Dana Whitfield (System Admin; password set on the copy only). The field job for D
was prepared on the copy: a move-out of `AC-2026-00001` raised per-meter job **WO-0041** on
meter **E-5000**, and the technician read **3,537 kWh** and closed it; Dana accepted it in the
browser. Script: `10-scripts/walk_reading_gaps_assets_2026_10_17.mjs` — **12/12 checks passed**
on the final pass.

**Head-end.** The sample tenant has **Neptune 360** switched on, and no reading client is bound
on this deployment (`apps/integrations/meter_reading.READING_CLIENTS` is empty), so every Fetch
answers, honestly, *"Neptune 360 connected. No reading fetched."* and fills nothing. No
simulator exists anywhere in the repo, so a real fill could not be walked; the fill path is
proved by the routed DOM tests instead.

| Shot | What it shows |
|---|---|
| `A1-retire-step1-final-read-fetch.png` | Retire **W-5020**, step 1: the old meter's final reading, its date and Fetch (honest no-reading answer). |
| `A2-retire-step2-opening-read.png` | Step 2: replacement **W-5100** picked → *Opening read* `12 kgal`, read date opens on the retire date **10/17/2026**, Fetch on the NEW meter. |
| `A3-retire-step3.png` | Step 3 before *Retire W-5020 ✓*. |
| `A4-old-meter-read-history.png` | W-5020's Reads tab: **1815 kgal on 10/17/2026** (`final_read`). |
| `A5-new-meter-read-history.png` | W-5100's Reads tab: **12 kgal on 10/17/2026** (`opening_read`). |
| `F0-add-reading-multi-register-no-fetch.png` | Add reading on 4-register **M-7001**: no Fetch (one head-end figure is never split across registers), ONE read date. |
| `F1-add-reading-fetch.png` | Add reading on one-register **W-5010**: Fetch beside the reading and its date. |
| `F2a-one-time-bill-step1.png` | The one-time bill's step 1 for AC-2026-00016, period 10/01–10/17/2026. |
| `F2-one-time-bill-step2-fetch.png` | Interim one-time bill for **AC-2026-00016**, step 2: a Fetch on each meter row (E-5015, W-5015). |
| `D1-awaiting-approval.png` | Work → Awaiting approval on the final pass. WO-0041 was accepted from this screen on an earlier pass (*Accept WO-0041* → *Accept ✓*, HTTP 200), so it is no longer listed. |
| `D2-job-meter-read-history.png` | E-5000's Reads tab: **3537 kWh on 10/17/2026 — source *manual · Move-out***. |
| `D3-field-reading-detail-move-out.png` | The reading's detail: tag **MOVE-OUT** (`event_context = move_out`), not *New connection*. |

Read back from the copy after the walk (`meter_reads`, read date 2026-10-17):
`W-5020 1815 kgal final_read` · `W-5100 12 kgal opening_read` · `M-7301 9180 kWh final_read` ·
`M-5099 12 kWh opening_read` (an earlier pass of the same retire) · `E-5000 3537 kWh event move_out`.

**Seen and not fixed (reported):** on the one-time bill the shared piece sits in one cell
spanning *New reading* and *New read date*; at 1440px it wraps, so the date box draws under the
reading rather than under its own heading.
