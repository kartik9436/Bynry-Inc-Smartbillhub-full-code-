# J-REP-03 — schedule a report, let the clock come round, and be told it ran

---
id: JREP03
tier: 1
rules: [BR-REP-007, BR-REP-017, BR-REP-018, BR-REP-020, BR-NOT-005, BR-TEN-022, NFR-3, NFR-5]
stories: [US-REP-014, US-REP-015]
change: CR-142-BRC07 · Phase 4 · P4.9
screens: ["2·3", "4·1", "4·2", "5·1"]
depends_on: [JREP01, JREP02]
# ⚠ **PARTLY BLOCKED, AND THE BLOCK IS NAMED IN STEP 1 RATHER THAN HIDDEN.**
# Steps 2–8 are walkable and proved. Step 1 — the clerk's own way IN — is not,
# because `ScheduleReportDialog.tsx` is built, tested and mounted by NOTHING
# (`DEF-REP-6913`). The dialog's door belongs on screen `2·1`, whose file is
# held by another lane. Recorded as a blocked step, never as a passing one:
# a journey that walks around its own missing door is how a product ships with
# two working entrances out of eight (CLAUDE.md hard-won law 2's mirror).
---

> **Read the drawings as IMAGES (B14 rule 42), never the text layer:**
> `python3 10-scripts/pdf/pdf_render.py "05-prototype/09 Reports Build Brief.pdf" <outdir> 3 14,15,33,34,40,41`
> The Phase 4 task table is **p014–p015**, `2·3` (the schedule dialog) is
> **p033–p034**, `4·1` (Scheduled) is **p040** and `4·2` (a schedule opened) is
> **p041**. The text layer of this PDF is measurably lossy — it renders
> *"names, addresses and balances"* as `aes, addesses ad baaces`.

## WHAT THIS JOURNEY IS FOR

**Phase 4's DONE WHEN, verbatim from p014:** *"A schedule set on Friday
produces a file on Monday, delivered to named internal staff."*

⚠ **THE SENTENCE HAS TWO HALVES AND THE PRODUCT ONLY HAD THE FIRST UNTIL
`P4.10`.** `apps/reports/schedules.py` fired the run and the file landed on
screen `5·1`; `report_schedules.recipients` held the people the schedule names,
refused by name if they were not staff (`BR-REP-020`) — and **nothing ever read
that list again.** Both halves were correct on their own and every test was
green over the gap, because the question *does anything consume this* belonged
to nobody. This journey is the walk of the whole sentence.

## THE HANDOFF CONTRACT

**What upstream (`J-REP-02`) leaves for this journey:** the History tab at
`/{tenant}/reports/history` and the fact that **a `jobs` row IS the run
record** — there is no `report_runs` table and there must not be one. A
scheduled run is not a second kind of run: it is the same `list_export` job a
clerk's Export button enqueues, with a `scope_key` added, so it appears on
`5·1` beside the manual ones with **Schedule** where a person's name would be.

**What this journey leaves for downstream:** one `outbound_messages` row per
finished run, `source_type='report'`, keyed on the RUN and never on the
schedule, carrying a LINK. **Nothing is sent** — `BR-REP-017` CONFIRMED
defers the dispatch to W6 with all email — so a downstream journey may assert
the row and must never assert an inbox.

## THE WALK

| # | Step | What must be true | Proved by |
|---|---|---|---|
| 1 | Open a report and press **Schedule** | The `2·3` dialog opens — **one `FormModal`, three fields**: How often · Format · Send to. ⚠ **NOT WALKABLE TODAY** — see the block above and `DEF-REP-6913` | — (blocked) |
| 2 | Pick a cadence, a format and a person, and save | `POST /reports/schedules` answers with the row and a computed **Next**. A free-text email address is refused BY NAME (`BR-REP-020`) | `tests/test_cr142_p4_schedules_api.py` |
| 3 | Open **Scheduled** (`4·1`) | The address is `/{tenant}/reports/scheduled`; six columns in p040's order — **Report · How often · Next · Send to · Status · actions**; *How often* is a word and never a cron string | `07-frontend/.../scheduledTab.dom.test.tsx` |
| 4 | **Force the clock** past *Next* | The sweep fires exactly one run. A schedule that fires twice in one instant produces **one** file — the `jobs` scope key folds the second into the first | `tests/test_cr142_p4_schedules.py` |
| 5 | Find the run on **History** (`5·1`) | A new row, **Schedule** in the *Started by* column, the report's name, its parameters, **Ready** and a download | `tests/test_cr142_p3_run_history.py` |
| 6 | **The notification** | ONE `outbound_messages` row, `source_type='report'`, channel **email**, addressed to the person the schedule names, whose `render_context.report_link` is `/{tenant}/reports/history/{run}` — **the link, never the file** | `tests/test_cr142_p4_10_delivery.py` |
| 7 | Let the clock come round **again** | A second run, a second message. ⚠ The message is keyed on the RUN, so October's does not fold into September's | idem |
| 8 | **Break the report** and let it fire | `4·1` shows the schedule **Failing** and keeps it; the run says failed; and **no message is queued at all** | idem + `tests/test_cr142_p4_schedules.py` |

### ⚠ STEP 6 IS THE ONE THIS PHASE EXISTS TO GET RIGHT

**The queue carries the LINK and never the file.** A CSV on an envelope
respects nobody's permissions once it has left the building — it is a page of a
utility's debtors, addresses and balances, forwardable by anyone who receives
it. The link is screen `5·2`'s address, behind the same sign-in as every other
screen, and `BR-REP-018` keeps the file behind it for three days.

**It is enforced and not intended.** `catalogs.email_scheduled_report` declares
`{report_link}` as **mandatory content**, so `rendering.validate_body` refuses
a body a utility has edited down to *"Your report is ready."* There is no token
in the palette that could carry an attachment, and a test asserts the palette
rather than the value — so a later lane adding one fails here rather than in a
review comment.

### ⚠ STEP 8 IS ITS MIRROR, AND IT IS THE CHEAPER FAILURE TO GET WRONG

A message that announces a run which failed is worse than no message: a clerk
told *"your report is ready"* stops looking, and the month-end pack is missing
for a week. So delivery reads the status screen `5·1` draws — the same
function, `run_history.present` — and the only status that produces a message
is *ready*. **Failing on `4·1` and silence in the inbox are the same fact read
from the same place.**

## WHAT THIS JOURNEY DOES NOT ASSERT, AND WHY

* **An inbox.** `BR-REP-017` is CONFIRMED — *"scheduled-report email ships W6
  with all email; v1 = download only"* — so the ROWS are written now and the
  dispatch is a flip later. Step 6 asserts `status == 'queued'` and
  `sent_at is None` as VALUES, so the day something does send, this journey
  goes red and names it rather than passing over a changed product.
* **A time of day.** `FIRE_AT_HOUR = 06:00` tenant-local is a lane CHOICE —
  p040's *Next* column draws dates and never a clock — and a journey that
  asserted it would harden an unratified decision into a contract.
* **A cycle close.** `monthly, on cycle close` resolves to the ACCOUNTING
  period's close (`BR-TEN-022`), because `CR-029` `D8①` withdrew the
  billing-cycle concept outright. **`OQ-REP-12741` is open** on whether the
  LABEL should read *period*; this journey names neither word in an assertion.
* **A tenant with no fiscal calendar.** It gets no computed date, the schedule
  stays on, and `4·1` marks it **Failing** so a person looks. No date is
  substituted. That is a case in `tests/test_cr142_p4_schedules.py`, not a step
  here, because there is nothing for a clerk to walk.

<!-- generated: 2026-09-27 by lane REP-P4-REST · CR-142-BRC07 P4.9 -->
