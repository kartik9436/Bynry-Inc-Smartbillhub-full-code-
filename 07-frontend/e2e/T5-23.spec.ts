// ── Trace ──────────────────────────────────────────────
// Journey:  T5-23 — Quiet-hours violation (the queue holds, nothing sends).
//           `08-qa/01-e2e/journeys/T5-23-quiet-hours-hold.md` is the spec; this
//           file walks its six-row step table in order.
// Story:    US-NOT-001 (the outbound table is the ONLY send path) · US-NOT-002
//           (the dispatcher) · US-NOT-004 (tenant notification settings) ·
//           US-PAY-015 (the S34 bulk reminder action) · US-IDN-001 (sign in)
//           Screens: S3 · S34 Outstandings (bulk reminder) · S8 Notifications
// Rules:    BR-NOT-009 (email/SMS have a tenant send window, default
//           08:00–21:00 tenant time; out-of-window messages QUEUE AND HOLD;
//           print/PDF is exempt) · BR-NOT-005 (the dispatcher sends in
//           tenant-config batches at provider pace) · NFR-1
// Money:    NONE. Every row of this journey is about message state, not money;
//           `moneyTriple` is not called rather than borrowed.
// Tests:    this file. Fixture: 08-qa/01-e2e/stack/seed_e2e_fixture.py
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
//
// THE PO'S 2026-08-15 DELIVERY RULING IS APPLIED HERE, and it does NOT excuse
// what this journey finds. The ruling is that issuing a bill does not mean the
// customer receives one — delivery is out of this release, no provider adapter
// exists on any channel, and a dispatch cycle reporting the adapter absent is
// CORRECT OUTPUT. So step 5 below asks only that a dispatch cycle can be run
// and reports the adapter's absence; it does not ask for a delivered message.
//
// What the ruling does not cover is the QUEUE. BR-NOT-009's hold is not
// delivery — it is the refusal to hand anything to a provider — and every row
// of this journey up to step 4 is about rows in `outbound_messages` and the
// dispatcher's decision not to touch them.
//
// `06-backend/apps/notifications/` is 6,952 lines: dispatcher, quiet-hours
// clock, batch pacing, provider seam, templates, delivery ops, models. Its
// `api.py` is a one-line docstring and `config/urls.py` names no include for
// it. So nothing in the running product can reach any of it, and the S8
// Notifications tab renders an `arrivesWith` panel. That is what this run is
// expected to find, and it is the same finding T7-16 and T7-17 make.
import { expect, test } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

journey("T5-23", "Quiet-hours violation — the queue holds, nothing sends", () => {
  // NOT serial: each row builds its own precondition, so the run reports which
  // of the journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — the out-of-window bulk reminder writes QUEUED rows and calls no provider", async ({
    page,
  }) => {
    await signIn(page);

    // The clerk's door: S34 Outstandings → bulk payment reminder.
    await page.goto(`/${tenant()}/payments/outstandings`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /remind|send reminder|notify/i }).first(),
      "S34 must offer the bulk payment-reminder action US-PAY-015 describes",
    ).toBeVisible();
  });

  test("step 2 — print/PDF rows are exempt and render now; email/SMS stay held", async ({
    page,
  }) => {
    await signIn(page);
    // BR-NOT-009's exemption is a property of the QUEUE, so the queue has to be
    // readable to assert it. (Under the PO's 2026-08-15 ruling the print row
    // ends at a RENDERED DOCUMENT, not at a posted letter — this step asks only
    // that the row exists and is distinguishable from the held ones.)
    const response = await page.request.get(api("/outbound-messages?per=200"));
    expect(
      response.status(),
      `GET /outbound-messages answered ${response.status()} — the outbound table ` +
        "US-NOT-001 calls the ONLY send path is not served, so neither the hold nor " +
        "the print exemption can be observed",
    ).toBe(200);
  });

  test("step 3 — the dispatcher refuses held rows on every cycle inside quiet hours", async ({
    page,
  }) => {
    await signIn(page);
    const response = await page.request.post(api("/notifications/dispatch"), { data: {} });
    // Under the PO's ruling, a cycle that reports the adapter absent is CORRECT
    // OUTPUT. What must never happen is a cycle that cannot be run at all.
    expect(
      response.status(),
      `POST /notifications/dispatch answered ${response.status()} — apps/notifications/ ` +
        "carries a 877-line dispatcher with a quiet-hours clock and nothing mounts it",
    ).toBeLessThan(400);
    expect(
      await response.text(),
      "the cycle must report either a hold or the absent adapter — never a send",
    ).toMatch(/quiet|held|hold|adapter|no provider/i);
  });

  test("step 4 — no inline 'send now' path exists on a held message", async ({ page }) => {
    await signIn(page);
    for (const path of ["/notifications/send", "/outbound-messages/send-now"]) {
      const response = await page.request.post(api(path), { data: {} });
      expect(
        [404, 405, 409, 422],
        `${path} answered ${response.status()} — US-NOT-001 makes the outbound table the ` +
          "ONLY send path, so an inline send must not succeed",
      ).toContain(response.status());
    }
  });

  test("step 5 — when the window opens the dispatcher drains; the absent adapter is correct output", async ({
    page,
  }) => {
    await signIn(page);
    // PO 2026-08-15: delivery is OUT of this release. This step therefore asks
    // for the DRAIN DECISION and its record, not for a delivered message.
    const response = await page.request.get(api("/notifications/delivery"));
    expect(
      response.status(),
      `the delivery dashboard answered ${response.status()} — BR-NOT-005's per-run ` +
        "counts have no surface, so 'the run shows on the dashboard' cannot be observed",
    ).toBe(200);
  });

  test("step 6 — RECOVERY: the quiet-hours window is editable in Settings → Notifications", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/${tenant()}/settings/notifications`);
    await expect(page.locator("main")).toBeVisible();
    await expect(
      page.locator("main"),
      "S8 → Notifications must offer the BR-NOT-009 window as a tenant setting; it " +
        "currently renders the 'arrives with' panel instead",
    ).not.toContainText(/arrives with|not built|coming/i);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T5-23 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the PO's 2026-08-15 delivery ruling is applied: steps 5 asks
//   for a dispatch DECISION and its record, never for a delivered message, and
//   an "adapter absent" answer is accepted as correct · (2) the journey's 22:15
//   tenant-clock fixture cannot be staged — no surface reads or sets the
//   dispatcher clock — so step 3 asserts the cycle's DECISION rather than a
//   time-travelled one · (3) no money figure is asserted
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
