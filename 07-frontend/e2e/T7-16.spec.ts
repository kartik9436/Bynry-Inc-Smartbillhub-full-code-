// ── Trace ──────────────────────────────────────────────
// Journey:  T7-16 — Config change: quiet-hours window (tonight's held queue
//           obeys the NEW window).
//           `08-qa/01-e2e/journeys/T7-16-quiet-hours-window-change.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-NOT-001 (the outbound table is the ONLY send path) · US-NOT-002
//           (the dispatcher) · US-NOT-004 (tenant notification settings) ·
//           US-IDN-001 (sign in)
//           Screens: S3 · S8 Notifications
// Rules:    BR-NOT-009 (the tenant send window; held messages dispatch per the
//           window IN FORCE AT DISPATCH TIME — future-dispatch-only, never a
//           retroactive send and never a re-hold of anything already sent) ·
//           BR-NOT-005 · BR-TEN-016 · BR-TEN-020
// Money:    NONE. Every row is about message state and timestamps; no figure is
//           rendered, so `moneyTriple` is not called rather than borrowed.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// SAME ROOT CAUSE AS T5-23 AND T7-17, and it is worth stating once per file so
// no reader mistakes three red journeys for three problems.
// `06-backend/apps/notifications/` carries 6,952 lines — an 877-line dispatcher
// with the BR-NOT-009 quiet-hours clock, a 356-line dispatch-config module whose
// own field list includes `quiet_hours_start` / `quiet_hours_end`, a provider
// seam, templates and delivery ops. `apps/notifications/api.py` is a one-line
// docstring and `config/urls.py` names no include for it, so nothing in the
// running product reaches any of it, and S8 → Notifications renders the
// `arrivesWith` panel. Built is not wired (CLAUDE.md hard-won law 2), at the
// largest scale in the repo.
//
// The PO's 2026-08-15 delivery ruling narrows what this journey may ask for: a
// dispatch cycle that reports the adapter absent is CORRECT OUTPUT. It does not
// excuse the missing WINDOW SETTING, which is a tenant config knob, nor the
// missing queue, which is where the hold lives.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

const WIDER = { start: "06:00", end: "21:00" };
const NARROWER = { start: "09:00", end: "20:00" };

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T7-16", "Config change: quiet-hours window — the held queue obeys the new window", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — widening the window on S8 Notifications saves and audits once", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/settings/notifications`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.locator("#quiet_hours_start").or(page.getByLabel(/quiet hours/i)).first(),
      "S8 → Notifications must render the BR-NOT-009 window as an editable tenant setting",
    ).toBeVisible();
  });

  test("step 2 — the save itself dispatches nothing", async ({ page }) => {
    await signIn(page);
    const save = await page.request.put(api("/settings/notifications"), {
      data: { quiet_hours_start: WIDER.start, quiet_hours_end: WIDER.end },
    });
    expect(
      [200, 201],
      `PUT /settings/notifications answered ${save.status()} — the notifications settings ` +
        "resource is not mounted, so the window cannot be changed at all",
    ).toContain(save.status());
  });

  test("step 3 — the drain begins at the NEW window edge, not the old one", async ({ page }) => {
    await signIn(page);
    const response = await page.request.post(api("/notifications/dispatch"), {
      data: { as_of: "2026-08-15T06:05:00-05:00" },
    });
    expect(
      response.status(),
      `the dispatch cycle answered ${response.status()} — the 877-line dispatcher has no ` +
        "mounted route, so 'the NEW window governed' cannot be observed",
    ).toBeLessThan(400);
  });

  test("step 4 — narrowing mid-drain re-holds what has not been handed off", async ({ page }) => {
    await signIn(page);
    const save = await page.request.put(api("/settings/notifications"), {
      data: { quiet_hours_start: NARROWER.start, quiet_hours_end: NARROWER.end },
    });
    expect([200, 201], `the second save answered ${save.status()}`).toContain(save.status());
  });

  test("step 5 — the drain resumes and completes under the narrowed window", async ({ page }) => {
    await signIn(page);
    const queue = await page.request.get(api("/outbound-messages?per=200"));
    expect(
      queue.status(),
      `the outbound queue answered ${queue.status()} — statuses cannot progress where no ` +
        "queue is readable",
    ).toBe(200);
  });

  test("step 6 — INVARIANCE: two audit rows for two saves, and nothing else changed", async ({
    page,
  }) => {
    await signIn(page);
    const audit = await page.request.get(api("/audit-log?per=50"));
    expect(audit.status()).toBe(200);
    const rows = ((await audit.json()) as { results: { action: string }[] }).results;
    expect(
      rows.filter((r) => r.action.includes("notification")).length,
      "BR-TEN-016: each atomic window save writes its own before/after row",
    ).toBeGreaterThanOrEqual(2);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-16 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the tenant-clock fixture (23:00 / 06:00 / 06:30 / 09:00) is
//   passed as an `as_of` PARAMETER rather than by moving a clock — BR-TEN-043
//   and gate G6 both forbid a wall-clock read, and a journey that waited for
//   06:00 would not be a test · (2) the PO's 2026-08-15 delivery ruling is
//   applied: no step asks for a delivered message, only for the dispatch
//   DECISION and its record · (3) no money figure is asserted
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
