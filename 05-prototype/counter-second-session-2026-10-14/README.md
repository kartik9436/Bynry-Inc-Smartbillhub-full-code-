# A second counter on one day — walk, 2026-10-14 (`DEF-PAY-10140`)

**Reported by the PO:** a clerk opened and closed counter CTR-261013-BS (06:24–06:44), opened another at 13:04 the same day, and could not open it (*"Counter could not load. The counter did not answer."*) or force-close it.

**Why:** the code was built from the day and the person's initials every time it was read, never stored, so both tills were called CTR-261013-BS and the server refused a name that matched two. **The fix (decision log *"G1–G4 APPROVED"* item 2):** the code is stored when the counter opens, unique per utility; a second counter on the same name gets `-2`, then `-3`; existing clashes are repaired oldest first, so no code anyone has seen changes.

Build `2.579.0` + this lane's changes, tenant `brazosbend`, signed in as Dana Whitfield (System Admin), on a private copy of the demo database (`smartbillhub_ctr`, dropped afterwards). Backend :8011, SPA :8091. Script: `10-scripts/def_pay_10140_counter_second_session_walkthrough.mjs`.

## The PO's state, reproduced and repaired

Before migrating the copy, two tills were written for Dana the way the old code wrote them: 10/13 06:24–06:44 (counted) and 10/13 13:04 (still open), no stored code. Applying `payments/0050` stored:

| Opened (UTC) | Code after the repair |
|---|---|
| 10/08 08:30 | CTR-261008-DW |
| 10/09 08:30 | CTR-261009-DW |
| 10/13 06:24 | **CTR-261013-DW** (unchanged) |
| 10/13 13:04 | **CTR-261013-DW-2** (was unreachable) |

The migration was also reversed and re-applied on the copy: same codes, and the unique index `uq_counter_sessions_code` is in place. Times on screen are the utility's (Houston), so 06:24 UTC shows as 01:24.

## Screens

| # | What | Result |
|---|---|---|
| 01 | Counters list after the repair | PASS — both 10/13 tills listed under different codes; *Your counter · CTR-261013-DW-2 · open* in the page head |
| 02 | Open CTR-261013-DW-2 by its code (the page that failed for the PO) | PASS — opens; no database id on screen |
| force-close-CTR-261013-DW-2, 03 | Force close it from the list | PASS — row reads *Forced · Not counted* |
| 04 | Open a code that does not exist (CTR-261013-ZZ) | PASS — the panel says *"This counter does not exist."*, the server's own reason, not *"did not answer"* |
| 06 | Today: start a counter (CTR-261014-DW), count it, close it | PASS |
| 06-start-counter-round-2, 07 | Start another the same day as the same person | PASS — **CTR-261014-DW-2**, in the address bar and the page |
| 08, 09, 10 | My counter → Record payment, $25.00 cash on AC-2026-00001 | PASS — the form says *Goes into counter CTR-261014-DW-2*; the counter shows 1 payment |
| force-close-CTR-261014-DW-2, 11 | Force close the second counter | PASS — *Forced · 1 payment · $25.00 · Not counted*; tiles read Taken today $25.00 |

## Seen on the way, not part of this fix

* **The payments table on *Your counter* lists every payment in the utility**, not the till's own (02 and 07 show October payments under a till with 0 payments). The screen narrows by a filter the server does not declare, and the server ignores it silently. Filed **`DEF-PAY-10141`**.
* *open since {{when}}* shows the placeholder — already filed as `DEF-PAY-8026`.
* The walk set Dana's password on the private copy only.
