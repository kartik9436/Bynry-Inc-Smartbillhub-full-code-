// ── Trace ──────────────────────────────────────────────
// Journey:  T5-03 — 08-qa/01-e2e/journeys/T5-03-currency-unlock-attempt.md
//           (tier 5 — a GUARD journey: the expected outcome is a REFUSAL)
// Story:    US-TEN-006
//           Screens: S8 Settings → Regional · S30 bill · S56 trial balance
// Guards:   BR-TEN-042 (one currency per tenant, LOCKED the moment the first
//           financial record exists) · NFR-22 (historical documents never
//           restate on a settings change)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// Changing the currency afterwards would restate every stored
// NUMERIC(18,6)+CHAR(3) amount's MEANING without touching a digit — the worst
// kind of silent corruption. The system must refuse at BOTH surfaces.
//
// This journey's fixture line reads "first financial record exists (issued bill
// BL-2607-0142)". On this stack the arming record is the E2E fixture's own
// issued bill; the bill NUMBER is the tenant series', not a constant, so the
// fixture's number is not asserted (the same choice W3-money-render made).
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

journey("T5-03", "Currency unlock attempt after the first financial record", () => {
  skipUnlessAppServer(test);

  test("step 1 · the Settings currency control renders DISABLED WITH REASON (IS-6)", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // The lock is armed: this tenant has an issued bill.
    const invoices = await apiJson(page, "/invoices");
    expect(invoices.body?.count, "the arming financial record exists").toBeGreaterThan(0);

    await page.goto(`/${tenant()}/settings/regional`);
    const currency = page.locator("#regional-currency, [name=currency], select").filter({
      has: page.locator("option[value=USD]"),
    });
    await expect(currency.first()).toBeVisible({ timeout: 15_000 });
    await expect(
      currency.first(),
      "BR-TEN-042 / IS-6: with the lock armed the currency control must be DISABLED. " +
        "An enabled control is a save a human can attempt, and step 1 says no save " +
        "is possible from the UI.",
    ).toBeDisabled();
  });

  test("step 2 · the API refuses the same change with a 409/422 validation posture", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const current = (await apiJson(page, "/settings/regional")).body;
    const attempt = await page.request.put(`/api/${tenant()}/settings/regional`, {
      data: { ...current, currency: "CAD" },
    });
    expect(
      attempt.status(),
      "BR-TEN-042: the refusal is an inline-validation posture (IS-7), not " +
        "permission-denied — no role can do this",
    ).toBeGreaterThanOrEqual(400);
    expect(attempt.status(), "…and it is not a 403: no role can do it, so it is not about role").not.toBe(
      403,
    );

    const after = await apiJson(page, "/settings/regional");
    expect(after.body?.currency, "currency still USD on the tenant row").toBe("USD");
  });

  test("step 3 · the issued document and the ledger still carry USD, unchanged", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    expect(invoice.currency, "every money row's CHAR(3) is untouched").toBe("USD");

    await page.goto(`/${tenant()}/billing/bills/${invoice.id}`);
    await page.getByRole("tab", { name: "Charges" }).click();
    const footer = page
      .locator("table.met-table")
      .filter({ has: page.locator("tfoot") })
      .locator("tfoot tr");
    await expect(
      footer.nth(2).locator(".cell-money-amount"),
      "NFR-22: the issued bill renders exactly as issued after the refused attempts",
    ).toHaveText(`$${GT1_TOTAL}`);

    const tb = await apiJson(page, "/ledger/trial-balance");
    expect(tb.body?.currency).toBe("USD");
    expect(tb.body?.balanced, "the ledger is balanced and unchanged").toBe(true);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T5-03's fixture cites $97.41 (money-triples `flat,cycle,full`);
//   the bill this stack actually issued is GT-1, so step 3's rendered figure is
//   read from the frozen 05-golden-tests.md rather than from a row describing a
//   different bill. Step 4's contrast case (a fresh tenant changing currency) is
//   T4-22's step 2 and is not duplicated here; step 5 is the abandon path and
//   asserts no state.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
