# Rate schedule Edit — seasonal prices come back, Effective from is proposed (2026-10-14)

Defects **DEF-RAT-10148** (seasonal prices blank on Edit) and **DEF-RAT-10149**
(Effective from empty on Review), ruled in the decision log entry of 2026-10-14
*"RATE SCHEDULE EDIT: "EFFECTIVE FROM" IS PREFILLED WITH THE FIRST DAY OF NEXT
MONTH; SEASONAL PRICES COME BACK ON EDIT"* (PO *"go A"*).

## What was walked

A private copy of the local database (`smartbillhub_rate`, made with
`createdb -T smartbillhub`, migrated with this branch), the API on port 8014 and
the built screen on port 8094 (`server.mjs`, bundle built with
`vite build --mode walk` so it talks to its own origin). Script:
`10-scripts/rate_schedule_edit_reopen_walk.mjs`.

Ann Arbor is not in the local database, so the walk creates a schedule of the
same shape on Brazos Bend: **seasonal, priced per kW-DC, Summer 1 Apr – 30 Sep
at 12.50, Winter 1 Oct – 31 Mar at 9.75, in force from 05/01/2026.** It is put
on Electric because Solar is switched off for this utility; that is why the
view page shows a kW-DC vs kWh unit warning, which has nothing to do with
these defects.

Then, as a clerk: Edit → Continue → step 2 → Continue → Review → type a reason →
Create new version, changing nothing. Then it reads back from the server what
was stored.

## Before the fix (build of `c5b1740d7`) — 2 of 9 checks pass

| Check | Seen |
|---|---|
| Step 2 shows both prices | both boxes **empty** (`0a-before-step2-prices-blank.png`) |
| Review shows $12.50 and $9.75 | both rows show **—** (`0b-before-review-blank.png`) |
| Effective from proposed | **empty** |
| Save goes through | **no** — refused, nothing saved |
| What changes reads 0 | passes — and that is a blind spot, see below |

## After the fix — 9 of 9 checks pass

| Check | Seen |
|---|---|
| Step 2 *Price per kW-DC* | Summer **12.5000**, Winter **9.7500** (`2-edit-step2-prices.png`) |
| Review | Summer **$12.50**, Winter **$9.75**; *What changes* **0 changes** (`3-edit-review.png`) |
| Effective from | proposed as **11/01/2026** (today is 10/14/2026 in the utility's own time zone); Effective to blank |
| Save | *"… saved as new version."* (`4-saved.png`) |
| Stored new version | Summer **12.5**, Winter **9.75**, starts **11/01/2026**, no end date |
| Previous version | now ends **10/31/2026**, the day before (`5-view-after.png`: *In force from 05/01/2026 · 10/31/2026*, *Change scheduled — new prices start 11/01/2026*) |
| Page errors | none |

## One thing the walk shows that is NOT fixed here

*What changes* read **0 changes** before the fix too, while the screen was about
to save two seasons with no price. It compares the clerk's draft with the same
draft as first loaded, so anything the reopen fails to load is missing from both
sides and can never show as a change. Recorded as an open item in the lane
report; not changed in this fix.
