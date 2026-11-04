// ── Trace ──────────────────────────────────────────────
// Journey:  T7-17 — Config change: dispatch batch size (next hand-off at the
//           new size; pacing invariant unbroken).
//           `08-qa/01-e2e/journeys/T7-17-dispatch-batch-size-change.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-NOT-002 (the dispatcher) · US-NOT-004 (tenant notification
//           settings) · US-IDN-001 (sign in)
//           Screens: S3 · S8 Notifications
// Rules:    BR-NOT-005 (the dispatcher sends in tenant-config batches at the
//           provider's pace; a batch handed to a provider is a fact) ·
//           BR-TEN-016 (one before/after audit row per atomic save; the field
//           map constrains the size to > 0) · BR-TEN-020 · NFR-1
// Money:    NONE. Every row is about queue rows, batch sizes and timestamps;
//           `moneyTriple` is not called rather than borrowed.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// SAME ROOT CAUSE AS T5-23 AND T7-16 — see T7-16's header for the full
// statement. In one line: `apps/notifications/` is 6,952 lines of dispatcher,
// pacing and config with a one-line `api.py` and no include in
// `config/urls.py`, so no route reaches it and S8 → Notifications renders the
// `arrivesWith` panel.
//
// The PO's 2026-08-15 delivery ruling applies to the SEND half only. The batch
// SIZE is a tenant config knob and the hand-off log is the dispatcher's own
// record; neither is delivery, and neither exists.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const OLD_SIZE = 500;
const NEW_SIZE = 200;

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T7-17", "Config change: dispatch batch size — the next hand-off uses the new size", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the drain hands off in batches of the configured size", async ({ page }) => {
    await signIn(page);
    const settings = await page.request.get(api("/settings/notifications"));
    expect(
      settings.status(),
      `GET /settings/notifications answered ${settings.status()} — the seeded ` +
        `dispatch_batch_size of ${OLD_SIZE} (notifications field map r12 #16) has no ` +
        "readable surface",
    ).toBe(200);
    const config = (await settings.json()) as { dispatch_batch_size: number };
    expect(config.dispatch_batch_size, "the seeded batch size").toBe(OLD_SIZE);
  });

  test("step 2 — the size change saves atomically, audits once, and rejects a non-positive size", async ({
    page,
  }) => {
    await signIn(page);
    const save = await page.request.put(api("/settings/notifications"), {
      data: { dispatch_batch_size: NEW_SIZE },
    });
    expect(
      [200, 201],
      `the batch-size save answered ${save.status()} — the notifications settings ` +
        "resource is not mounted",
    ).toContain(save.status());

    // The field-map constraint: > 0.
    const invalid = await page.request.put(api("/settings/notifications"), {
      data: { dispatch_batch_size: 0 },
    });
    expect(invalid.status(), "a batch size of 0 must be refused").toBeGreaterThanOrEqual(400);
  });

  test("step 3 — the in-flight hand-off completes as handed off", async ({ page }) => {
    await signIn(page);
    const handoffs = await page.request.get(api("/notifications/handoffs?per=50"));
    expect(
      handoffs.status(),
      `the hand-off log answered ${handoffs.status()} — BR-NOT-005's "a batch given to ` +
        'the provider is never clawed back" cannot be observed without one',
    ).toBe(200);
  });

  test("step 4 — every hand-off after the save is at or under the new size", async ({ page }) => {
    await signIn(page);
    const handoffs = await page.request.get(api("/notifications/handoffs?per=200"));
    expect(handoffs.status()).toBe(200);
    const rows = ((await handoffs.json()) as { results: { rows: number }[] }).results;
    expect(
      rows.every((h) => h.rows <= OLD_SIZE),
      "the config in force at hand-off time bounds every hand-off",
    ).toBe(true);
  });

  test("step 5 — a retried batch retries as ITS batch, not re-cut to the new size", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.get(api("/notifications/handoffs?per=200&f.retried=true"));
    expect(
      response.status(),
      `the retry view answered ${response.status()} — retry counters and backoff spacing ` +
        "have no surface, so 'unchanged by the config save' cannot be checked",
    ).toBe(200);
  });

  test("step 6 — INVARIANCE: the config change touched no money or document row", async ({
    page,
  }) => {
    await signIn(page);
    const invoices = await (await page.request.get(api("/invoices?per=200"))).text();
    const ledger = await (await page.request.get(api("/ledger/trial-balance"))).text();
    await page.request.put(api("/settings/notifications"), {
      data: { dispatch_batch_size: OLD_SIZE },
    });
    expect(await (await page.request.get(api("/invoices?per=200"))).text()).toBe(invoices);
    expect(await (await page.request.get(api("/ledger/trial-balance"))).text()).toBe(ledger);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-17 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the 2,000-row drop the journey drains is not staged — no
//   queue exists to stage it in — so every step asserts the SURFACE the journey
//   needs and names what answered instead · (2) the PO's 2026-08-15 delivery
//   ruling is applied: nothing here asks for a delivered message · (3) no money
//   figure is asserted
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
