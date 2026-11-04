# Temporary-stop backfill — walk of 2026-10-14 (`DEF-CUS-10161`)

**The defect.** A portal *stop my service* request raised before 2.580.0 wrote only the clerk's sentence. 2.580.0 recognises a temporary stop only from the `temporary_stops` row the portal has written since then, so after the upgrade those requests still read *Not yet classified*, and Approve offered only New connection / Move-in. On WDMWW Loader Test that is SR-26-0017 (AC-2026-00551, 13 → 16 Oct) and SR-26-0022 (14 → 28 Oct, *vacation*).

**The fix.** `customers/0086` runs once on upgrade, and `manage.py backfill_temporary_stops [--dry-run]` runs the same function on a host at any time. It reads the portal's own sentence, finds the account by number within the utility, and writes the row through the live portal path (`temporary_stop.record_from_portal`), with two audit rows. It skips requests it cannot read, accounts the utility does not have, and requests already decided, and it counts what it skipped.

**Set-up.** Private copy `smartbillhub_tsbf` (`createdb -T smartbillhub`; the dev database was at `customers/0082`), migrated to `customers/0085`. Then the pre-upgrade world was recreated: seven requests written exactly as 2.575.1 wrote them. Each is one `service_requests` row from `create_from_portal`, with the sentence composed by the portal's own `_stop_restart_words` and no temporary-stop row. Backend on **8018** (`runserver`, local settings). The SPA was built with `vite build --mode walk` (a local mode, so the bundle calls its own origin) and served by `server.mjs` on **8098**. Tenant Brazos Bend, clerk Dana Whitfield, 1440 px. The utility's day was **14 Oct** (America/Chicago). Script: `10-scripts/def_cus_10161_temporary_stop_backfill_walk.mjs`, phases `before`, `after` and `short-future`. The copy was dropped and both servers stopped afterwards.

| Request | Its sentence (as the portal wrote it) | Stands for |
|---|---|---|
| SR-26-0061 | AC-2026-00001 from 2026-10-13, starting again on 2026-10-16 | SR-26-0017 (3 days) |
| SR-26-0062 | AC-2026-00002 from 2026-10-14, starting again on 2026-10-28 … *Going on vacation* | SR-26-0022 |
| SR-26-0063 | AC-2026-00003 from 2026-10-20, with no restart date given | no restart |
| SR-26-0064 | **AC-2026-00551** (the PO's account, which Brazos Bend does not hold) | unknown account |
| SR-26-0065 | account **not stated** | unreadable |
| SR-26-0066 | AC-2026-00004 …, then **refused** before the upgrade | closed request |
| SR-26-0067 | AC-2026-00005 from 2026-10-16, starting again on 2026-10-19 (added after the migration, backfilled by the command) | a 3-day ask dated in the future |

## Before the migration (2.580 code, `0086` not applied): the defect, reproduced
| # | Screen | |
|---|---|---|
| 01 | `01-before-request-unclassified.png` | SR-26-0061: nothing says *Temporary stop*. |
| 02 | `02-before-approve-offers-new-connection-move-in.png` | Approve opens the *What kind: New connection / Move-in* window, blocked on *Property · Arrears*. The clerk cannot process it. |

## The migration
```
Applying customers.0086_def_cus_10161_temporary_stop_backfill...
    temporary-stop backfill: 3 portal stop request(s) given a temporary stop; left alone: 1 unreadable, 1 naming no account here, 0 failed (SR-26-0064, SR-26-0065)
 OK
```
Running `manage.py backfill_temporary_stops` straight afterwards wrote **0** and named the same two requests left alone, so a second run is a no-op. Run again after SR-26-0067 was added, it wrote **1**.

## After the migration
| # | Screen | |
|---|---|---|
| 03 | `03-after-requests-list-typed.png` | The list: SR-26-0061/62/63 read **TEMPORARY STOP**. SR-26-0064/65 still read *Not yet classified*, left for a clerk. SR-26-0066 (Refused) is untouched. |
| 04 | `04-after-vacation-request-typed.png` | SR-26-0062 typed. |
| 05 | `05-after-short-request-typed.png` | SR-26-0061 typed. |
| 06 | `06-after-approve-window-refuses.png` | Its own Approve window, with no New connection / Move-in. Dates 10/13 → 10/16 are editable. **Dates: That date has passed.** shows, because on the utility's 14 Oct the 13 Oct stop date is in the past. The window shows the first date problem, and this is the first. |
| 07 | `07-after-approve-window-dates-edited.png` | The clerk changes the dates to 10/15 → 10/27. The window reads **Dates ✓ 12 days**, and Approve is enabled. |
| 08–09 | `08-after-approved.png`, `09-after-account-stop-scheduled.png` | Approved. The account reads **Stop scheduled 10/15/2026 – 10/27/2026 · Base charge only** and stays **Active** until the stop date. |
| 10 | `10-short-future-approve-window-at-least-10-days.png` | SR-26-0067 (3 days, dated in the future). Its window reads **Dates ✗ At least 10 days.**, which is the PO's expected refusal for SR-26-0017. |
| 11–12 | `11-short-future-restart-moved.png`, `12-short-future-approved.png` | The clerk moves the restart date to 10/30 (14 days) and approves. |

## Record checks (read from the copy after the walk)
| Check | Result |
|---|---|
| `temporary_stops` | SR-26-0061 `scheduled` 2026-10-15 → 2026-10-27 (outcome `temporary_stop`, request `approved`) · SR-26-0062 `requested` 2026-10-14 → 2026-10-28, reason *Going on vacation* · SR-26-0063 `requested` 2026-10-20 → (none) · SR-26-0067 `scheduled` 2026-10-16 → 2026-10-30. All channel `customer_portal`. |
| Left alone | SR-26-0064 and SR-26-0065: no row, still `submitted`, sentence unchanged. SR-26-0066: still `refused`, no row. |
| `audit_log` | `temporary_stop.requested` 4 and `temporary_stop.backfilled` 4 (actor *job: Temporary stop backfill · DEF-CUS-10161*), plus `temporary_stop.approved` 2. |
| Accounts | AC-2026-00001 and AC-2026-00005 stay `active`. Both stop dates are in the future, and the daily clock moves them on the day. |

## Observations (no change made)
* A request with **no restart date** (SR-26-0063) is typed correctly. Its Approve window asks for a restart date (B3's rule), so the clerk adds one with the customer.
* The first `after` run printed `1 FAIL` from the walk script's own check: it looked for the word *past*, but the window says *passed*. The pattern is corrected in the script. Everything else in that run passed, including the approval check.
