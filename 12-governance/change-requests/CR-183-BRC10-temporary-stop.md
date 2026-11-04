# CR-183-BRC10 · Temporary stop — a customer's "stop my service for a while" becomes a real, scheduled hold

**Raised:** 2026-10-14 by the Product Owner, in chat, testing the customer portal and the staff request page.
**Requester's words (as relayed to this lane by the coordinator; the PO's chat message itself is not in the repo):** a portal *stop service* request, `SR-26-0017` (Susan Cook, stop `AC-2026-00551` on 13 Oct, restart 16 Oct), reached staff as *Not yet classified*, and *Approve* offered only **New connection** or **Move-in** — neither of which is what the customer asked for.
**Rulings (verbatim, 2026-10-14):** decision log *"TEMPORARY STOP — FOUR PO RULINGS (B1–B4)"* — *"B1 … Option 1; B2 … Option 2 Optional: the clerk ticks "Field visit needed" when approving. - this is corect; B3 … Option 1 No minimum, 12 months maximum, set in Settings. - this is correct - also set min limit to 10 days for time being; B4 … Option 1 Yes: "Restart my service now" in the portal sends a request, the clerk approves it, and billing returns to normal from that day. - this is correct"*

## 1 · Classification
A **change**. The portal ask has existed since `US-CWP-062` and did exactly what its rule said (`BR-CWP-026`: *"a public form may create work and may never change an account"*): one worklist row, the facts in a sentence. What is new is a request TYPE the product never had (*Temporary stop* and its *Restart now*), a hold that is scheduled and ends on its own, and two tenant settings. Not a defect: nothing promised a typed request.

## 2 · What is added
| Before | After |
|---|---|
| The stop ask's account and dates live only in the clerk's sentence | They are stored with the request (`temporary_stops` row: account, stop from, restart on, reason); the sentence stays for the clerk |
| *Not yet classified*; Approve offers New connection / Move-in | Classified **Temporary stop** (or **Restart now**) on arrival; its own Approve window: account, dates, *Base charge only* during the hold, *Field visit needed* tick (B2). New connection / Move-in are not offered for it |
| No limits | **B3** — at least **10 days**, at most **12 months**; both on S66 *Billing defaults*; outside them Approve is refused by name |
| `vacation_hold` exists and nothing sets it | On the stop date the account becomes `vacation_hold`; on the restart date `active` again — a daily job, idempotent, audited; the account stays open, service agreements untouched |
| — | **B1** — during the hold the bill carries the base charge only (by the day) |
| — | **B2** — with *Field visit needed*: a shut-off work order for the stop date and a turn-on for the restart date |
| — | Staff can start a temporary stop from the account page, change its dates, or end it early |
| — | **B4** — portal shows *Service paused … · restarts …* and a *Restart my service now* button that sends a request; on approval the account is active from that day |

## 3 · Tasks
T1 structured fields · T2 classification · T3 Approve window + limits + settings · T4 schedule · T5 billing check · T6 field visit work orders · T7 staff start / change / end · T8 portal status + restart request · T9 tests (SQLite + PostgreSQL, dom) · walk in `05-prototype/temporary-stop-2026-10-14/`.

## 4 · Ids
`BR-CUS-1120` (temporary stop: B1, B2, B4) and `BR-CUS-1121` (the limits, B3) — taken by hand after a grep of the remote tip found `BR-CUS-1119` the maximum.

## 5 · Status — BUILT, NOT RELEASED (lane TSTOP, 2026-10-14). No version bumped and no CHANGELOG line — the release lane does both.

Judgments of ours: decision log *"TEMPORARY STOP — HOW THE FOUR RULINGS WERE BUILT: TWELVE JUDGMENTS OF OURS"*. Rules: `BR-CUS-1120`, `BR-CUS-1121` (customers business rules). Review ledger: `customers/0084` (table + RLS) and `billing/gather._behavior_class_for_period`, PENDING.

| # | Built |
|---|---|
| T1 | `temporary_stops` (`customers/0084`, RLS same file); the portal ask writes its row through `temporary_stop.record_from_portal` in the same transaction as the request; the clerk's sentence unchanged. |
| T2 | Type read from the row: header `classification`, list `type`, `detail.temporary_stop`; `outcome` = `temporary_stop` / `restart_now` on approval; the generic decide / approve refuse such a request by name. |
| T3 | `POST service-requests/{id}/temporary-stop/approve`; `TemporaryStopApproveModal` (dates editable, Account / Dates / *Base charge only*, *Field visit needed*, consequence); limits refused by name; S66 settings `temporary_stop_min_days` (10) / `temporary_stop_max_months` (12), `BR-CUS-1121`. |
| T4 | `temporary_stop.apply_due` via beat entry `customers.temporary_stop_clock` (hourly fan-out, idempotent); `vacation_hold` ↔ `active`, audit + account history; account open, agreements untouched. |
| T5 | Engine measured: a period partly on hold run while on hold billed base only and lost the active days' usage ($18.50 instead of $67.94 on the test figures). Fixed in `gather` — class by the hold's days. |
| T6 | *Field visit needed* → Work's `raise_temporary_stop_visits`: *Disconnection/Reconnection* jobs, source `disconnect` due the stop date and `reconnect` due the restart date; numbers on the hold. |
| T7 | Account page: **Temporary stop** button → start (counter, no request) / change dates / **End now**; status strip under the head. |
| T8 | Portal *Your account*: **Service paused** card, *Restart my service now* (B4 request, contact filled from the file), the pending ask by reference; request hub titles *Restarting service now*. |
| T9 | `tests/test_cr183_temporary_stop.py` (15) + `_billing.py` (4), SQLite and PostgreSQL 16; dom: `TemporaryStopApproveModal.dom.test.tsx` (4, under the real request route), `TemporaryStopAccount.dom.test.tsx` (3), portal `TemporaryStopCard.dom.test.tsx` (3). Walk: `05-prototype/temporary-stop-2026-10-14/`. |

**Open items (not built here):**
1. Moving a hold's dates, or ending / cancelling it, does **not** move or cancel the two field-visit work orders (walk: WO-0041/WO-0042 stayed open after the restart). A dispatcher must close them in Work.
2. A period partly on hold whose meter was NOT read meets the run's ordinary missing-read decision (estimate / hold) over the whole period; an estimate would include the hold days.
3. T6's *optional meter read at stop/restart* has no path of its own: the turn-off/turn-on jobs carry the meter, and a read is entered through the existing Reads screens.
4. Changing dates is offered only to staff; the customer can end early (B4) but not move the dates from the portal.
