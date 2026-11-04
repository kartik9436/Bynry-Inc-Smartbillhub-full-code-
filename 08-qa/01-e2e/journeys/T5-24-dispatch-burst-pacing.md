# T5-24 — Dispatch burst (pacing proof at 10k — no synchronous blast exists)

---
id: T5-24
tier: 5
guards: [BR-NOT-005, BR-BIL-016, NFR-1]
stories: [US-NOT-001, US-NOT-002, US-BIL-023, US-BIL-024]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** EVERY outbound email/SMS from any module is written to the outbound table first — never sent inline — and a dispatcher sends in tenant-config batches at the PROVIDER'S pace (BR-NOT-005; PO: "ESP/Twilio will not send such emails quickly"). The refusal proven here: the system will not blast 10,000 messages at generation speed. Mass sends are never synchronous (BR-BIL-016); generation speed and sending speed are decoupled by construction (NFR-1).

**Fixture.** Volume-tenant fixture (transactional ESP connected per BR-INT-006, the 6k–10k path) · bill run issues **10,000** bills with email delivery elected · tenant batch size = default 500 · ESP responds 429 (rate-limited) on one mid-run batch.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions | Guard |
|---|---|---|---|---|
| 1 | Issue completes for 10,000 bills at ~generation speed | Issue writes one delivery record per bill per channel into the outbound queue — and RETURNS; zero provider calls happen inside the issue transaction | 10,000 outbound_messages rows status=queued within the issue window; issue latency independent of provider; provider call count at issue commit = 0 | BR-NOT-005 · BR-BIL-016 |
| 2 | Harness watches the dispatcher drain the queue | Dispatch proceeds in batches of ≤500 (tenant config) at provider pace — never one 10k hand-off; concurrent burst capped at the batch size | Max messages per provider hand-off ≤ 500; queue drains monotonically; statuses progress queued→sent→delivered/failed/bounced per row | BR-NOT-005 · NFR-1 |
| 3 | ESP returns 429 on batch 7 | Dispatcher backs off and retries ×3 with backoff — it does NOT drop the batch, does NOT hammer the provider, does NOT fail the run | Batch-7 rows show retry counters ≤3 with backoff spacing; other batches unaffected; final failures marked failed (not lost) for re-queue | BR-NOT-005 |
| 4 | Probe: any module attempts an inline send (a code path calling a provider adapter without a queue row) — harness contract check | No such path exists: the outbound table is THE ONLY send path platform-wide (US-NOT-001); adapters accept work only from the dispatcher | Every provider call traces to a queue row id; zero orphan provider calls in the adapter log | BR-NOT-005 |
| 5 | Ops reviews the per-run delivery dashboard | Dashboard shows the run's queued/sent/delivered/failed/bounced counts with re-queue for failures | Counts sum to 10,000; re-queue writes new dispatch attempts, never duplicate messages | BR-NOT-005 · US-BIL-024 |
| 6 | RECOVERY — the ratified doors for throughput needs: raise the tenant batch size (config, within provider limits) and/or connect the transactional ESP integration built for volume (BR-INT-006); quiet hours still gate the window (T5-23) | Config/integration changes take effect on subsequent dispatch cycles; pacing discipline itself is never disabled | Faster drains remain batched, paced, statused, and dashboard-visible | BR-NOT-005 · BR-INT-006 |
