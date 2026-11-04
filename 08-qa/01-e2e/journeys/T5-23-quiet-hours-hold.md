# T5-23 — Quiet-hours violation (the queue holds, nothing sends)

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
id: T5-23
tier: 5
guards: [BR-NOT-009, BR-NOT-005, NFR-1]
stories: [US-NOT-001, US-NOT-002, US-NOT-004, US-PAY-015]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Email/SMS have a tenant-config send window — default 08:00–21:00 tenant time (BR-NOT-009). Messages generated outside the window must QUEUE AND HOLD until it opens; print/PDF generation is exempt. A utility texting late-payment reminders at 23:00 is a compliance and reputation incident; the refusal here is the dispatcher's: it will not hand a held message to any provider, no matter who asks or how the message was generated.

**Fixture.** Tenant brazos-bend, timezone America/Chicago, quiet-hours default 08:00–21:00 · at 22:15 tenant time a clerk runs a bulk payment-reminder action (S34) over 340 accounts, channels: email + SMS + print.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed until the window) | Guard |
|---|---|---|---|---|
| 1 | Clerk fires the 22:15 bulk reminder (modal → confirm → toast) | Action SUCCEEDS as a queue write — every message written to outbound_messages first, never sent inline; email/SMS rows enter status queued with a hold-until-window marker | 680 email/SMS queue rows exist, all status=queued; ZERO provider calls at 22:15; the bulk action itself audits (BR-AUD-001 — executed money/destructive UI action) | BR-NOT-005 · BR-NOT-009 |
| 2 | Print/PDF rows from the same action are processed immediately | Print generation is exempt from quiet hours — PDFs render now | 340 print rows progress; email/SMS still held; no partial email sends ride along | BR-NOT-009 |
| 3 | Harness polls the dispatcher between 22:15 and 07:59 | Dispatcher REFUSES to dispatch held rows on every cycle — no send attempt, no provider traffic, statuses unchanged | Provider adapters record zero calls all night; retry counters untouched (nothing was attempted) | BR-NOT-009 · NFR-1 |
| 4 | Probe: clerk finds a "send now" affordance on a held message / calls a direct-send API | No inline-send path exists — the outbound table is the ONLY send path (US-NOT-001); any re-queue action still lands behind the window | Held rows stay held; no bypass; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero sends | BR-NOT-005 |
| 5 | At 08:00 tenant time the window opens | Dispatcher begins draining the held rows in tenant-config batches at provider pace — pacing rules still apply (no 08:00 burst; see T5-24) | Statuses progress queued→sent→delivered per row; first provider call timestamp ≥ 08:00 tenant time; delivery dashboard shows the run | BR-NOT-009 · BR-NOT-005 |
| 6 | RECOVERY — the ratified door for genuinely urgent night traffic: adjust the tenant quiet-hours window in Settings → Notifications (config change, future-only effect — the T7 config journey), or use print/PDF which is exempt | Window edit is a tenant setting; subsequent queues honor the new window; nothing retroactively sends | Config change audited; held messages from before the edit dispatch per the window in force at dispatch time | BR-NOT-009 |
