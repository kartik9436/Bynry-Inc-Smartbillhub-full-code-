# CR-193-BRC10 · Shifts and timesheet, step 1 (MQ-040): working days, the phone's week, End shift, Submit the day

**Raised:** 2026-10-26 by the Product Owner, in chat, answering MQ-040.

**Requester's words, verbatim:** *"Shall I start step 1- start"*.

**Ruling record:** decision log 2026-10-26, *"MQ-040: shifts and timesheet, STEP 1 approved (working days, week view with holidays, End shift, Timesheet submit)"* — the last section of `12-governance/02-decision-log.md`. Worked example shown there: D. Ortiz Mon–Fri 07:00–15:30, Fri 30 Oct a utility holiday → Mon–Thu 07:00–15:30, Fri *Holiday*.

## 1 · Classification (step 1 of `13-change-process.md`)
A **change** — a capability the product never had. The phone's FF-46 *Shifts* and FF-47 *Timesheet* were built and read *"Not on this phone yet"* because the server held only a daily window per technician (`technicians.shift_start/shift_end`) and the utility's `HolidayCalendar`; there were no working days, no exceptions and no `work/mobile` doors for the week, End shift or Submit the day (execution plan T-24). Not a defect: nothing promised these before the PO approved step 1.

## 2 · What is added (nothing signed is reversed)
| Before | After |
|---|---|
| A technician had a daily window and nothing else | **Working days** per technician — a weekday set, Monday to Friday when none is saved (`BR-WRK-068`) — and **one-day exceptions**: a day off, or a different window, with a note. Office only, on the technician's page. |
| FF-46 read *Not on this phone yet* | The week the day's sync downloads and keeps: each day's window, the utility's holidays in grey, an exception's note; today's shift with the time so far and **End shift** (`BR-WRK-069`). Works with no signal. |
| FF-47 *Submit the day* said it was not sent | **Submit the day** reaches the office: the server snapshots that day's labour per job and travel from the job clocks (`BR-WRK-070`). After submit the day reads *Submitted* and is read-only on the phone. |
| The office saw no submitted days | A **Timesheets** tab on the technician's page lists every submitted day — date · jobs · on site · travel · submitted at — paged. |

**NOT added — step 2 is not approved:** time-off requests, office approval and notifications. *Request time off* still says it was not sent (`ME-shifts` stays its gap id).

## 3 · Our judgments, recorded so they are not re-asked (law 13)
1. **The order a day is decided in:** an exception wins, then a utility holiday, then the weekday rule, else *off*. An exception beats a holiday because it is the office's narrower, later word about one person (someone on call).
2. **The daily window stays where it is** (`technicians.shift_start/shift_end`, edited on Add crew member). Working days hold only the weekday set; the Working days panel shows the window beside the days and does not edit it.
3. **When the shift starts:** the server holds no clock-on moment, so today's shift starts at its window's start; the time so far is measured from it.
4. **End shift sets the person *off today*** (the brief) and records the moment. ⚠ **THE MORNING RETURN IS BUILT (2026-10-26, `DEF-WRK-10615`, PO *"yes reset each morning"*)**: an hourly job per utility returns them to *on shift* at the start of their next working day (working weekday or a different-hours exception; not a holiday, a non-working weekday or a whole-day *off* exception), settles the End shift (`work/0055` `settled_at`) so it runs once, and never overrides a status the office set by hand after the End shift or an *unavailable* the End shift found. The rest of this point is the record of step 1 as first built: nothing yet set them back to *on shift* next morning — so the phone's week reads an `off_today` left by an EARLIER day's End shift as a new day, while an `off_today` a dispatcher set by hand (no End shift that day) is obeyed. ~~**The morning roll-back of the status itself is NOT built**: the dispatch board will show the person *Off today* until the office sets them back. Recorded here as the known edge of step 1.~~ (Built — see the start of this point.)
5. **One submission per person per day.** The same key, or a second press for a day already submitted, answers the first with `duplicate: true`. The snapshot is what the technician handed in; a later correction of a job clock does not move it. A day with no clocks submits zeros rather than refusing (the decision log: *"Timesheet 0m … is correct when no job clock ran"* — the phone still disables the button when it holds no entries).
6. **Who edits working days and exceptions:** the roles that already write on the technician's page (`WorkOrdersReadAnyWriteAdminOrClerk` — the utility's admin and the clerk, who is the dispatcher in this product). Every write is audited (`work.shift.*`, `work.timesheet.submitted`).
7. **The phone keeps the week in its preferences** (one small JSON document per technician), not in a table: nothing queries inside it.

## 4 · What is built
**Server (work module)** — `apps/work/shift_models.py` (four tables), `work/0053` + `work/0054` (RLS ENABLE + FORCE), `apps/work/shifts.py`, `apps/work/shifts_api.py` (spliced into `api.urlpatterns` by one line), `apps/work/seams/tenancy_seam.holidays_between` (read only).

    GET  /work/mobile/week?from=YYYY-MM-DD
    POST /work/mobile/shift/end           {key, at?, capture_token?}
    POST /work/mobile/timesheet/submit    {date, key, capture_token?}
    GET|PUT      /work/technicians/{slug}/working-days
    GET|POST     /work/technicians/{slug}/exceptions          (paged)
    PATCH|DELETE /work/technicians/{slug}/exceptions/{id}
    GET          /work/technicians/{slug}/timesheets          (paged)

**Web** — `TechnicianWorkingDays.tsx` (*Working days* toggles + *Exceptions* list with add/edit/remove), `TechnicianTimesheetsTab.tsx`, `shiftsEndpoints.ts`; both components on `route-b-migrated.txt`; the page gains the *Timesheets* tab.

**Phone** — `sync/shifts.ts` (the week kept, the wire), two own-door outbox kinds `shift_end` and `timesheet_submit` (`sync/doors.ts`), `HttpTransport` doors, `screens/me/shiftsPorts.ts` wired in `FieldRuntime` (the week downloads after each sync run). FF-46 and FF-47 (and the tablet's FF-47 detail) wired; the FF-46 hold in `tests/proof/holds.test.tsx` fired red and is now its working test.

**Words** — 56 keys in all eleven catalogues (`10-scripts/i18n_fanin.py`), written natively.

## 5 · Tests
`06-backend/tests/test_cr193_shifts.py` (worked example, exception precedence, working days, exceptions, End shift, Submit the day, tenant isolation, the three doors through the stack) · `tests/test_cr193_shifts_pg.py` (RLS on all four tables, the savepoint) · `07-frontend/src/features/work/TechnicianShifts.dom.test.tsx` · `field-app/tests/sync/shifts.test.ts` · `field-app/tests/screens/me/shiftsWired.test.tsx` · `field-app/tests/proof/holds.test.tsx`.

## 6 · Rollback
`migrate work 0052` drops the four tables (every rule, exception, shift end and submitted day with them); revert the commit to remove the routes, panels and phone wiring. A handset with queued `shift_end`/`timesheet_submit` items keeps them: with the doors gone they are refused and shown on FF-50, nothing is lost.

## 7 · Version
Ships in the next release; `allocate.py version --bump change` answered **2.601.0** on 2026-10-26. The coordinator stamps the release (this lane does not move the shared version files).

## 8 · Status
**BUILT — awaiting the release and human review** (review-ledger row of 2026-10-26 for `work/0053`, `work/0054`).
