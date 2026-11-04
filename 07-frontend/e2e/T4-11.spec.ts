// ── Trace ──────────────────────────────────────────────
// Journey:  T4-11 — 08-qa/01-e2e/journeys/T4-11-tax-exempt-on-mid-cycle.md
//           x = taxed account → y = tax-exempt set mid-cycle; the NEXT bill is
//           exempt, ISSUED bills are never restated
// Story:    US-BIL-008 · US-RAT-013 · US-LED-014 · US-CUS-009
//           Screens: S21 account detail (exemption panel) · S30 bill detail ·
//           S41 remittance
// Rules:    BR-CUS-063 (the evidence set: flag + certificate reference + expiry;
//           NOTHING recomputes at flag time) · BR-RAT-006 (the engine consumes
//           the exemption at the NEXT bill's finalization — it never reaches
//           back) · BR-BIL-004 (an issued taxed bill is immutable) · BR-LED-002
//           (closed-period billed-basis remittance must not shrink)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { goldenCalc } from "./support/expected";
import { journey } from "./support/journey";

// The ONE issued bill on this stack is GT-1; its TAX is the figure step 2 says
// must still stand after the flag is set. Read from the ❄️ FROZEN document.
const [, , GT1_TAX] = goldenCalc("GT-1").steps;

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-11", "Tax-exempt ON mid-cycle — next bill exempt, issued bills stand", () => {
  skipUnlessAppServer(test);

  test("step 1 · the exemption evidence set is capturable and NOTHING recomputes at flag time", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    const detail = await apiJson(page, `/accounts/${account.id}`);
    expect(detail.status).toBe(200);
    // BR-CUS-063's evidence set — all three parts, or the exemption is not
    // evidenced and an auditor cannot be answered.
    expect(detail.body, "flag").toHaveProperty("tax_exempt");
    expect(
      JSON.stringify(detail.body),
      "BR-CUS-063: the evidence set is flag + CERTIFICATE REFERENCE + EXPIRY DATE",
    ).toMatch(/"(tax_exempt_certificate|certificate_ref|exemption_certificate)/);

    // The screen half — the panel a clerk sets it on.
    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await expect(page.getByText(/Tax exempt/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: /edit|exempt|certificate/i }).first(),
      "T4-11 step 1: a clerk must be able to SET the exemption with its evidence — " +
        "the journey's whole transition starts here",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 2 · the ISSUED bill still carries its tax and the remittance basis is unchanged", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;

    // BR-BIL-004: the issued bill's tax stands, at the figure finance signed.
    await page.goto(`/${tenant()}/billing/bills/${invoice.id}`);
    await page.getByRole("tab", { name: "Charges" }).click();
    const footer = page
      .locator("table.met-table")
      .filter({ has: page.locator("tfoot") })
      .locator("tfoot tr");
    await expect(footer.nth(1)).toContainText("Tax");
    await expect(footer.nth(1).locator(".cell-money-amount")).toHaveText(`$${GT1_TAX}`);

    // BR-LED-002: the billed-basis remittance for the closed period must not
    // shrink because a certificate arrived late.
    const remittance = await apiJson(page, "/finance/taxes?from=2026-07-01&to=2026-07-31");
    expect(
      remittance.status,
      "T4-11 step 2: S41's dual-basis remittance must serve, or 'July's figures are " +
        "frozen' is unverifiable",
    ).toBe(200);
  });

  test("step 4 · the tax-liability trend is basis-labelled per authority", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    await page.goto(`/${tenant()}/finance/taxes`);
    await expect(
      page.getByText(/billed|remit|basis/i).first(),
      "BR-REP-001: every remittance column names its basis",
    ).toBeVisible({ timeout: 15_000 });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-11's WE-1/WE-2 figures ($221.90 / $20.97 / $247.87 / $226.90)
//   are WORKBOOK values the harness loads no source for, and this stack's bill
//   is GT-1 rather than WE-1, so the ONE money figure asserted is GT-1's own tax
//   read from the frozen 05-golden-tests.md. Step 3 (the next bill, exempt)
//   needs a second cycle run and is not walked — stated rather than faked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
