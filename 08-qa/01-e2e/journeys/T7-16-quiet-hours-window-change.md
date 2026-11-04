# T7-16 — Config change: quiet-hours window (tonight's held queue obeys the NEW window)

> ⚠ **THE ROW COUNT IN THIS JOURNEY IS THE PRE-RULING ONE (`DEF-2467`, amended 2026-08-30).**
> This journey asks for **email + SMS**, and that is still exactly what the fixture asks for.
> But its source kind is `notice`, and the Product Owner ruled on 2026-08-29 that **print is
> the floor on every customer document**, not on bills alone — `BR-NOT-024` was amended to six
> source kinds, so `queue_document` now writes a third `pdf_print` row per account.
> **340 accounts therefore hold 1,020 rows, not 680.** The 680 below is left in place rather
> than overwritten: it is what was agreed before the ruling, and the amendment only reads
> against it. What the fixture asserts is now DERIVED from the floor
> (`tests/journey_cohort_fixtures._queue_row_channels`), never re-typed, so a further change to
> the rule moves the arithmetic on its own.
> The journey's subject — quiet hours, batching, the window change — is untouched: the extra
> rows are queued under the same window and drain with the rest.


---
id: T7-16
tier: 7
knob: quiet_hours 08:00–21:00 → 06:00–21:00, then → 09:00–20:00 (S8 Notifications tab)
rules: [BR-NOT-009, BR-NOT-005, BR-TEN-016, BR-TEN-020]
stories: [US-NOT-004, US-NOT-002, US-NOT-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** T5-23 proved the hold; this journey turns the knob it holds against. The ratified semantics (T5-23 step 6): held messages dispatch per the window IN FORCE AT DISPATCH TIME — a window edit is future-dispatch-only, never a retroactive send and never a re-hold of anything already sent. Both directions are proven: widening releases tonight's queue earlier; narrowing mid-drain stops the dispatcher at the new edge.

**Fixture.** Tenant brazos-bend, timezone America/Chicago, quiet hours default 08:00–21:00 (BR-NOT-009) · 340-account bulk reminder fired at 22:15 → 680 email/SMS rows queued-and-held (the T5-23 fixture); print rows already processed (exempt) · System Admin Alex Reed edits the window at 23:00 and again at 06:30.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | 23:00 — Alex widens the window to 06:00–21:00 on S8 Notifications; atomic save | Toast → ONE audit row `notification_settings.updated`, before/after `{quiet_hours: 08:00-21:00→06:00-21:00}` | BR-TEN-016 shape (notifications field-map audit row) · BR-AUD-011 | BR-TEN-016 · BR-NOT-009 |
| 2 | The save itself, at 23:00 | NOTHING dispatches at save time — 23:00 is outside even the new window; held rows stay held; the edit is config, not a send trigger | Zero provider calls at 23:00; statuses unchanged | BR-NOT-009 |
| 3 | 06:00 tenant time | Dispatcher begins draining the held 680 rows — two hours earlier than the old window; first provider call ≥ 06:00, < 08:00 (proving the NEW window governed) | Batches at tenant batch size, provider pacing intact (no 06:00 burst — T5-24 invariant) | BR-NOT-009 · BR-NOT-005 |
| 4 | 06:30 — mid-drain, Alex NARROWS the window to 09:00–20:00; atomic save (second audit row) | Dispatcher halts at the next cycle: rows not yet handed off re-hold until 09:00; rows already sent stay sent — a sent message is history, never re-held or re-sent | No send occurs in 06:30→09:00 after the halt takes effect; retry counters untouched on held rows | BR-NOT-009 · BR-TEN-016 |
| 5 | 09:00 | Drain resumes and completes under 09:00–20:00 | Statuses progress queued→sent→delivered per row; per-run dashboard counts sum to 680 | BR-NOT-009 · BR-NOT-005 |
| 6 | INVARIANCE — sweep outbound_messages + documents + postings across both edits | Sent rows keep their original sent/delivered timestamps (no restatement); no message sent twice (queue-row identity is the send identity); zero money/document rows touched by either save | Two audit rows total for the two saves; nothing else changed | BR-TEN-020 · NFR-22 · BR-NOT-005 |
