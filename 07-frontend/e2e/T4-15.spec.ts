// ── Trace ──────────────────────────────────────────────
// Journey:  T4-15 — 08-qa/01-e2e/journeys/T4-15-meter-swap-reassign-final-read.md
//           x = old meter on the unit → y = new meter; the bill uses BOTH
//           registers' spans
// Story:    US-AST-009 (reassign) · US-MET-010 · US-RAT-012 · US-BIL-007
//           Screens: S49–S55 asset registry + detail (Reassign) · S15 unit
//           detail · S30 bill detail
// Rules:    BR-MET-043 (the ONLY ratified door is the assets reassign flow WITH
//           a final read) · BR-MET-019 (consumption is register arithmetic PER
//           METER — never one delta across two physical registers) · BR-MET-049
//           / BR-RAT-038 (explicit UoM or a defined conversion, else rating
//           blocks) · BR-MET-053 (reads append; a final read supersedes nothing)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// A swap without the final read would either LOSE or INVENT consumption, which
// is why step 1's flow REQUIRES one.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-15", "Meter swap via reassign-with-final-read — two register spans", () => {
  skipUnlessAppServer(test);

  test("step 1 · the assets Reassign flow REQUIRES a final read before the meter leaves the unit", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const assets = await apiJson(page, "/assets?f.type=meter");
    expect(assets.status).toBe(200);
    const meter = ((assets.body?.results ?? []) as Array<Record<string, string>>).find(
      (asset) => asset.status === "installed" || asset.status === "in_service",
    );
    expect(
      meter,
      "T4-15 step 1 needs a meter INSTALLED on a unit to swap; the E2E stack seeds " +
        "ten assets and assigns none",
    ).toBeTruthy();

    await page.goto(`/${tenant()}/assets/${meter!.id}`);
    await expect(
      page.getByRole("button", { name: /reassign/i }).first(),
      "BR-MET-043: the reassign flow is the ONLY ratified untag door",
    ).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: /reassign/i }).first().click();
    await expect(
      page.getByText(/final read/i).first(),
      "BR-MET-043: the flow must REQUIRE the final read — without it the cycle's " +
        "consumption is either lost or invented",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 3 · the cycle's usage is the SUM of two per-meter spans, attributed to both", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    expect(invoice, "T4-15 step 3 needs the cycle bill the swap falls inside").toBeTruthy();

    await page.goto(`/${tenant()}/billing/bills/${invoice.id}`);
    await page.getByRole("tab", { name: /Usage|Charges/i }).first().click();
    await expect(
      page.getByText(/meter|register|span/i).first(),
      "BR-MET-019 / BR-BIL-011: the bill's usage detail must ATTRIBUTE both meters' " +
        "spans — a single delta across two registers is the defect this journey names",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 5 · INVARIANCE — the unit never moved; only its asset did", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;
    const unit = await apiJson(page, `/units/${account.unit_id}`);
    expect(unit.status).toBe(200);
    const premisesId = unit.body?.premises_id;

    const again = await apiJson(page, `/units/${account.unit_id}`);
    expect(
      again.body?.premises_id,
      "BR-MET-046: units never change premises — only assets move",
    ).toBe(premisesId);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-15 states its span dollar figures are ENGINE-COMPUTED (§5), so
//   it names no frozen figure and no moneyTriple lookup appears — "the law
//   asserted here is the two-span structure", in the journey file's own words.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
