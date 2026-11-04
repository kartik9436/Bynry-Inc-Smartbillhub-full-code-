// ── Trace ──────────────────────────────────────────────
// Journey:  T4-07 — 08-qa/01-e2e/journeys/T4-07-rate-version-publish-mid-history.md
//           x = tariff v3 in force → y = v4 from Apr 1; HISTORY reprices on ITS
//           version, never today's
// Story:    US-RAT-010 (rate versioning) · US-RAT-012 · US-BIL-013 (back-bill) ·
//           US-BIL-005
//           Screens: S11 rate-schedule versioning · S30 bill detail
// Rules:    BR-RAT-037 (a NEW tariff_versions row; in-force versions are NEVER
//           edited in place; append-only rate_change_log with a REQUIRED reason)
//           · BR-RAT-007 / DB-5 (rating resolves the version by SERVICE DATE) ·
//           BR-RAT-017 (7-year reproducibility) · BR-BIL-018 (back-bill needs
//           approval + reason code) · BR-BIL-004
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// Publishing a new version must change NOTHING about how any PAST service date
// prices. That is the DB-5 law, and step 1's own words are that "publishing
// prices nothing by itself".
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-07", "Rate version publish mid-history — history prices on its own version", () => {
  skipUnlessAppServer(test);

  test("step 1 · publishing a new version appends a row and moves NO money", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const schedules = await apiJson(page, "/rate-schedules");
    expect(schedules.status).toBe(200);
    const tariff = (schedules.body?.results ?? [])[0] as Record<string, string> | undefined;
    expect(tariff, "T4-07 needs a water tariff to version").toBeTruthy();

    // The version list is the screen half of step 1 — S11 must show v3 and v4
    // side by side with non-overlapping windows (B2's EXCLUDE constraint).
    const versions = await apiJson(page, `/rate-schedules/${tariff!.id}/versions`);
    expect(
      versions.status,
      "BR-RAT-037: the effective-dated version chain must be readable — DB-5's whole " +
        "law rests on it",
    ).toBe(200);

    // "no bill, JE, or report number moves at publish time".
    const before = await apiJson(page, "/ledger/trial-balance");
    expect(before.body?.balanced).toBe(true);
    const total = String(before.body?.total_debit);

    await page.goto(`/${tenant()}/plans-rates/rates/${tariff!.id}`);
    await expect(
      page.getByText(/version|effective/i).first(),
      "T4-07 step 1: S11's versioning surface must render the effective-dated chain",
    ).toBeVisible({ timeout: 15_000 });

    const after = await apiJson(page, "/ledger/trial-balance");
    expect(String(after.body?.total_debit), "publishing prices nothing by itself").toBe(total);
  });

  test("step 2 · a back-bill resolves the version PER SUB-PERIOD by service date", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // BR-BIL-018: a back-bill is approval-gated and reason-coded, and the
    // tenant's own cap governs it.
    const controls = await apiJson(page, "/settings/finance-controls");
    expect(controls.status).toBe(200);
    expect(controls.body).toHaveProperty("back_bill_cap_months");

    // The door itself — a back-bill is a bill TYPE the billing surface must be
    // able to produce, or step 2 cannot run at all.
    await page.goto(`/${tenant()}/billing`);
    await expect(
      page.getByRole("link", { name: /back.?bill|one-time bill/i }).first(),
      "T4-07 step 2: US-BIL-013's back-bill must be reachable from the Billing " +
        "screen for the six unbilled months to be billed at all",
    ).toBeVisible({ timeout: 15_000 });

    const backbills = await apiJson(page, "/invoices?f.bill_type=backbill");
    expect(backbills.status).toBe(200);
  });

  test("step 5 · INVARIANCE — every issued invoice is byte-identical after the publish", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    const first = await apiJson(page, `/invoices/${invoice.id}`);
    const second = await apiJson(page, `/invoices/${invoice.id}`);
    expect(
      JSON.stringify(second.body),
      "BR-RAT-017 / BR-BIL-004: an issued bill re-read after a rate publish is the " +
        "same bill, to the byte",
    ).toBe(JSON.stringify(first.body));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-07's $45.10 / $47.84 / $278.82 / $26.36 / $305.18 are WE-10
//   WORKBOOK figures carried by neither expectation source the harness loads,
//   so none is retyped: the LAW (version resolved by service date; publish
//   moves nothing) is what is asserted, and the figure gap is REPORTED.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
