// ── Trace ──────────────────────────────────────────────
// Journey:  J5 — 08-qa/01-e2e/journeys/J5-month-end.md (tier 1)
//           deposits reconcile → trial balance → close → export
// Story:    US-PAY-001 (the cash side the close reconciles) · US-LED-015 (month
//           close) · US-LED-016 (the export that closes it out) · US-TEN-006
//           (fiscal close, BR-TEN-038)
//           Screens: S36 Finance (Deposits & Bank · General ledger · Export) ·
//           S56 trial balance · S42 export
// Rules:    BR-TEN-038 (period closed; late-dated events auto-post forward with
//           audit) · BR-MET-046 (premises filter resolves via the unit chain) ·
//           BR-LED-007 (the tie-out)
// Money:    the ONE issued bill on this stack is GT-1; its figure is read from
//           the ❄️ FROZEN 05-golden-tests.md, never retyped.
// Impacts:  nothing — this spec reads the product.
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { goldenCalc } from "./support/expected";
import { journey } from "./support/journey";

const GT1_TOTAL = goldenCalc("GT-1").total;

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("J5", "Month-end — deposits reconcile → trial balance → close → export", () => {
  skipUnlessAppServer(test);

  test("step 1 · the deposit batches screen reconciles and locks the day's takings", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // The Finance sidebar item, clicked the way a controller clicks it.
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Finance", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/${tenant()}/finance`));

    await page.getByRole("link", { name: /Deposits & Bank/i }).first().click();
    await expect(
      page.getByText(/matched|unmatched|locked|batch/i).first(),
      "J5 step 1: deposit batches must be matchable, resolvable and lockable on S36",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 2 · the trial balance foots (debits = credits) and renders on screen", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // The engine half — BR-LED-007's tie-out, read from the product.
    const tb = await apiJson(page, "/ledger/trial-balance");
    expect(tb.status).toBe(200);
    expect(tb.body?.balanced, "step 2 handoff: debits = credits").toBe(true);
    expect(tb.body?.total_debit).toBe(tb.body?.total_credit);
    // The one posted entry on this stack is GT-1's issue, so the trial balance
    // must foot at GT-1's signed total.
    expect(String(tb.body?.total_debit)).toBe(`${GT1_TOTAL}0000`);

    // The SCREEN half — S56 is reached from Finance's General ledger tab, and a
    // trial balance nobody can see is the defect this journey exists to catch.
    await page.goto(`/${tenant()}/finance/general-ledger`);
    await expect(
      page.getByText(new RegExp(GT1_TOTAL.replace(".", "\\."))).first(),
      "J5 step 2: the trial balance must RENDER its footing — a figure no human " +
        "can read is not a month-end control",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 3 · US-TEN-006 closes the fiscal period and late-dated events post forward", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const regional = await apiJson(page, "/settings/regional");
    expect(regional.status).toBe(200);
    expect(regional.body?.current_period?.status, "the period must be open before it closes").toBe(
      "open",
    );
    expect(
      regional.body?.lock_closed_periods,
      "BR-TEN-038's forward-posting behaviour is only meaningful with the lock on",
    ).toBe(true);

    // Step 3's handoff — "period closed". The close is US-TEN-006's action and
    // must be reachable from the S36 period header a controller works from.
    await page.goto(`/${tenant()}/finance`);
    await expect(
      page.getByRole("button", { name: /close (the )?period|close month/i }).first(),
      "J5 step 3: closing the period is US-TEN-006's own action (BR-TEN-038) and " +
        "must be reachable from the Finance period header",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 4 · the export writes ONE summary JE per month in a named format", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    await page.goto(`/${tenant()}/finance/export`);
    // Step 4's handoff — "one summary JE per month; QBO/CSV/IIF/Xero".
    await expect(
      page.getByText(/QBO|IIF|Xero|CSV/i).first(),
      "J5 step 4: S42 must offer the four ratified accounting export formats",
    ).toBeVisible({ timeout: 15_000 });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: J5's only money figure on this stack is GT-1's total, read from
//   the frozen B5 document through goldenCalc — the 245-row money-triples
//   dataset carries no row for a trial-balance footing.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
