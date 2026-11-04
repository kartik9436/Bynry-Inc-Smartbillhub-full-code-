# T7-17 — Config change: dispatch batch size (next hand-off at the new size; pacing invariant unbroken)

---
id: T7-17
tier: 7
knob: dispatch_batch_size 500 → 200 (S8 Notifications tab; r12 #16 tenant setting)
rules: [BR-NOT-005, BR-TEN-016, BR-TEN-020, NFR-1]
stories: [US-NOT-004, US-NOT-002]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The dispatcher sends in tenant-config batches at the provider's pace (BR-NOT-005; seeded 500 per the notifications field map). Changing the size mid-queue must apply from the NEXT hand-off — batches already handed to a provider are facts — and the T5-24 pacing invariant (every provider call traces to queue rows; hand-off ≤ the size in force at hand-off time) must hold continuously through the change. This is also the "raise the batch size" recovery door T5-24 step 6 names, proven turnable in both directions.

**Fixture.** Tenant brazos-bend (transactional ESP connected) · a bill-run drop of **2,000** queued email rows, dispatcher draining at batch size 500 · System Admin Alex Reed changes the size to 200 after the 2nd hand-off · harness logs every provider hand-off with its row count and the config in force.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Drain begins under 500 | Hand-offs #1 and #2 each ≤ 500 rows; statuses progress queued→sent per row | Provider calls trace 1:1 to queue-row sets; no inline sends anywhere (US-NOT-001 only-path) | BR-NOT-005 |
| 2 | Alex sets `dispatch_batch_size` 500→200 on S8 Notifications; atomic save | Toast → ONE audit row `notification_settings.updated`, before/after `{batch_size: 500→200}`; validation enforces > 0 (field-map constraint) | BR-TEN-016 shape · BR-AUD-011 | BR-TEN-016 · BR-NOT-005 |
| 3 | The in-flight hand-off at save time | Completes as handed off — a batch given to the provider is never clawed back or split retroactively | Its rows finish their status progression normally | BR-NOT-005 |
| 4 | Hand-offs after the save | Every subsequent hand-off ≤ 200 (config read per dispatch cycle); drain continues monotonically to zero | Harness log shows the size step-change exactly once, at the config boundary; total sent = 2,000, no row lost or duplicated | BR-NOT-005 · NFR-1 |
| 5 | Probe: retry behavior across the change | A 429-retried batch from the 500-era retries as ITS batch (×3 backoff, T5-24 rule) — retries are not re-cut to 200 | Retry counters and backoff spacing per row unchanged by the config save | BR-NOT-005 |
| 6 | INVARIANCE — sweep queue rows, delivery dashboard, documents, postings | Sent/delivered rows keep their timestamps and batch lineage; dashboard counts sum to 2,000; zero money or document rows touched; quiet-hours window still gates independently (T7-16) | Config change altered throughput shape only — never message identity or history | BR-TEN-020 · NFR-22 |
