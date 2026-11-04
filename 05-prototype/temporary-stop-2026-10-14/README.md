# Temporary stop — walk of 2026-10-14 (`CR-183-BRC10`)

Walked in a browser on a **private copy** of the dev database (`smartbillhub_tstop`, made with `createdb -T smartbillhub`, migrated to `customers/0084`, dropped afterwards), backend on 8007, frontend on 8087. Script: `10-scripts/cr183_temporary_stop_walk.mjs` (phases `ask`, `approve`, `portal-restart`, `approve-restart`, `list`, `counter`, `account-on-hold`). Customer: Ana Alvarez, `AC-2026-00001` (Brazos Bend); clerk: Dana Whitfield.

⚠ **The utility's own day was 13 Oct** (America/Chicago, the walk ran at about 23:20 on the 13th local), so a stop dated 14 Oct was correctly *scheduled*, not started, on approval. The hold was then started by running the daily clock for 14 Oct by hand (`temporary_stop_schedule.run_one("brazosbend", as_of=2026-10-14)`), which is what the beat entry does each hour.

## What the customer did and saw
| # | Screen | |
|---|---|---|
| 01–04 | `01-portal-stop-or-restart.png` … `04-portal-asked.png` | Asks to stop from **14 Oct** to **30 Oct** (16 days), reason *Away visiting family* → reference **SR-26-0061**. |
| 11 | `11-portal-paused.png` | *Your account* → **Service paused** · *Paused Oct 14, 2026 – Oct 30, 2026* · *Restarts Oct 30, 2026* · *Standing charge only while paused.* · **Restart my service now**. |
| 12 | `12-portal-restart-asked.png` | Pressed → *Restart asked · SR-26-0062*; the button is gone. |

## What the clerk did and saw
| # | Screen | |
|---|---|---|
| 07 | `07-staff-request-typed.png` | SR-26-0061 reads **TEMPORARY STOP** in the head and *Type: Temporary stop* — not *Not yet classified*. |
| 08 | `08-staff-approve-window.png` | Its own Approve window: Stop from / Restart on (editable), checks *Account AC-2026-00001 ✓*, *Dates 16 days ✓*, *During the hold — Base charge only*, **Field visit needed** ticked, *The account stays open. Base charge only from 10/14/2026.* No New connection / Move-in anywhere. |
| 10 | `10-staff-account-on-hold.png` | The account after approval: *Stop scheduled 10/14/2026 – 10/30/2026 · Base charge only · Visits WO-0041 · WO-0042*. |
| 14–16 | `14-staff-restart-request.png` … `16-staff-restart-approved.png` | SR-26-0062 reads **RESTART NOW**; window: *Back on from 10/13/2026*, *The hold ends today. Normal billing from 10/13/2026.* → Approved, window closed. |
| 17 | `17-staff-account-active.png` | Account back on **Active**. |
| 18 | `18-staff-requests-typed.png` | The Requests list's TYPE column: *Temporary stop* / *Restart now*. |
| 19–23 | `19-staff-counter-start.png` … `23-staff-ended.png` | From the account page: **Temporary stop** → start one (to 20 Nov) → *On hold 10/13/2026 – 11/20/2026 · Base charge only* (header pill *Vacation hold/Suspended*) → **End now** → Active. |

## Record checks (read from the database after the walk)
| Check | Result |
|---|---|
| `temporary_stops` for SR-26-0061 | `customer_portal`, stop **2026-10-14**, restart **2026-10-30**, field visit **true**, shut-off **WO-0041**, turn-on **WO-0042**, restart request **SR-26-0062** (`approved`); status **cancelled** — the restart was approved on the utility's 13 Oct, before the stop date, so no day was spent on hold (judgment 6). |
| The clock | first run for 14 Oct: `started: [the hold]`; second run the same day: `started: [] ended: []` (idempotent). Account → `vacation_hold`. |
| `service_requests` | SR-26-0061 `approved` / outcome `temporary_stop`; SR-26-0062 `approved` / outcome `restart_now`. |
| `work_orders` | WO-0041 `disconnect`, ref `AC-2026-00001`, due **2026-10-14**, *Disconnection/Reconnection*; WO-0042 `reconnect`, due **2026-10-30**. |
| `audit_log` | `temporary_stop.requested` → `.approved` → `.field_visit_raised` → `.started` + `account.temporary_stop_started` → `.restart_requested` → `.cancelled` + `account.temporary_stop_ended`; the counter stop `scheduled` / `started` / `account.temporary_stop_started` / `account.temporary_stop_ended` / `cancelled`. |
| Account stays open | `accounts.closed_at` empty; **2** service agreements open before and after. |
| The bill (T5) | October 1–31 prepared for the account's cycle while it was on hold 14–29 Oct: gathered as **billable** (status class `billable_base_only`), 31 of 31 service days. Draft **BL-2610-000251 $168.68** — electric base **$12.00** + water base **$8.00** for the whole month, the meter's usage (800 kWh, 8 kgal) and tax $3.31. A period wholly inside the hold (15–28 Oct) gathers as `billable_base_only` — base only. |

## Faults the walk found, fixed in this CR before it closed
1. The Approve window printed **`{{days}} days`** (wrong interpolation key) — fixed; the dom test now asserts *3 days* and no `{{`.
2. The window **stayed open** after a successful Approve — fixed; the dom test asserts it closes.
3. Approving the restart returned **500** (nothing saved): the account-history period had been opened on 14 Oct by the clock while the utility's day was 13 Oct, and the history refuses a backdate — fixed (`_set_status` updates the open period in place); `test_ending_a_hold_whose_history_period_opens_later_does_not_fail` was red on it first.
