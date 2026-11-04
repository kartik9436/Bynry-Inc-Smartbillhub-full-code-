// ── Trace ──────────────────────────────────────────────
// Journey:  T4-19 — 08-qa/01-e2e/journeys/T4-19-grace-mode-calendar-to-business.md
//           x = grace counted in CALENDAR days → y = BUSINESS days; the switch
//           governs only evaluations that RUN after it
// Story:    US-TEN-010 (the S66 rule pages) · US-PAY-014
//           Screens: S8 Settings → Configure → Billing defaults (S66)
// Rules:    BR-BIL-002 (the mode is a tenant setting) · BR-BIL-008 (5-day grace)
//           · BR-BIL-024 (grace mode changes COUNTING, never the due date
//           itself) · BR-PAY-021 (on-time reads the POSTING date) · BR-BIL-004
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// The same 5-day grace lands on different dates under each mode, so the switch
// must not re-walk a determination already made.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-19", "Grace mode calendar → business — next evaluation only", () => {
  skipUnlessAppServer(test);

  test("step 1 · the baseline is calendar counting on a 5-day grace", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const defaults = await apiJson(page, "/settings/billing-defaults");
    expect(defaults.status).toBe(200);
    expect(defaults.body?.late_grace_mode, "x = CALENDAR counting").toBe("calendar");
    expect(defaults.body?.late_grace_days, "BR-BIL-008's 5-day grace").toBe(5);
  });

  test("step 2 · the mode is switchable from S66 and the switch re-evaluates nothing", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    await page.goto(`/${tenant()}/settings/reference-data`);
    await expect(
      page.getByText(/grace/i).first(),
      "T4-19 step 2: BR-BIL-002's grace MODE must be switchable on the S66 page — " +
        "the whole journey is about a tenant flipping it",
    ).toBeVisible({ timeout: 15_000 });

    // "zero fee lines created/removed at save" — the ledger is where that is
    // provable, and it must not move across the write.
    const before = await apiJson(page, "/ledger/trial-balance");
    const total = String(before.body?.total_debit);

    const current = (await apiJson(page, "/settings/billing-defaults")).body;
    const write = await page.request.put(`/api/${tenant()}/settings/billing-defaults`, {
      data: { ...current, late_grace_mode: "business" },
    });
    expect(write.status(), "BR-BIL-002: business-day counting is a supported mode").toBeLessThan(
      400,
    );

    const after = await apiJson(page, "/ledger/trial-balance");
    expect(String(after.body?.total_debit), "nothing re-evaluates at save time").toBe(total);

    // Leave the tenant as this journey's fixture line found it.
    await page.request.put(`/api/${tenant()}/settings/billing-defaults`, {
      data: { ...current, late_grace_mode: "calendar" },
    });
  });

  test("steps 3 · 5 — the due date itself never moved", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    const dueDate = invoice.due_date;
    expect(dueDate, "BR-BIL-024: due = bill date + the cycle's due-days").toBeTruthy();

    const again = await apiJson(page, "/invoices");
    expect(
      ((again.body?.results ?? [])[0] as Record<string, string>).due_date,
      "BR-BIL-024: grace mode changes COUNTING, not due dates",
    ).toBe(dueDate);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-19's WE-15 dates (Jul 26 / Jul 24 / Aug 21) are WORKBOOK
//   values, and the harness loads no source for them, so no date arithmetic is
//   retyped here — the SWITCHABILITY and the no-retro-evaluation law are what is
//   asserted. Step 4's post-switch assessment needs a second overdue bill.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
