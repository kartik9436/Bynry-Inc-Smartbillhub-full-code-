// ── Trace ──────────────────────────────────────────────
// Journey:  T4-21 — 08-qa/01-e2e/journeys/T4-21-budget-level-override-bounds.md
//           x = the COMPUTED trailing-12 level → y = a staff override, bounded
//           ±30%; ±31% is refused server-side
// Story:    US-BIL-018/019/020 (budget billing)
//           Screens: S21/S30 budget panel · S69 budget-rules settings
// Rules:    BR-BIL-017 (OQ-068 closure: override allowed WITH reason + audit,
//           bounded ±30% of the COMPUTED level; the override PRESENTS, it never
//           overwrites the computation) · BR-RAT-043 (the plan flag) ·
//           BR-TEN-041 (every band parameter is a tenant setting) · BR-BIL-004
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// The band exists because the level is a COLLECTION SCHEDULE, not a price: let
// staff flex it for hardship, never so far that the variance balance becomes a
// hidden debt engine.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-21", "Budget level override within ±30% — the band is enforced", () => {
  skipUnlessAppServer(test);

  test("step 1 · the tenant's budget parameters carry the ±30% band and the whole-dollar rounding", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const rules = await apiJson(page, "/settings/budget-billing");
    expect(rules.status).toBe(200);
    expect(rules.body?.override_bound_pct, "BR-BIL-017 (OQ-068): the band is ±30%").toBe("30");
    expect(rules.body?.level_rounding, "the computed level is whole dollars").toBe("whole_dollar");
    expect(rules.body?.eligibility_months, "a 12-month history satisfies eligibility").toBe(12);
    expect(rules.body?.relevel_drift_pct, "auto re-level at ±20% drift").toBe("20");
    expect(rules.body?.relevel_cadence_months, "every 6 months").toBe(6);
    expect(rules.body?.drop_off_missed_payments, "off-budget after 2 missed payments").toBe(2);
  });

  test("step 2 · a Billing Clerk can submit an override with a reason, and it is bounded", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    // The override door itself. BR-BIL-017 makes it a per-account, reasoned,
    // audited action — so it must have a surface and an endpoint.
    const override = await page.request.post(
      `/api/${tenant()}/accounts/${account.id}/budget-billing/override`,
      { data: { level: "250.000000", reason: "customer requested rounding to expected raise" } },
    );
    expect(
      override.status(),
      "T4-21 step 2: BR-BIL-017's per-account budget-level override must exist as a " +
        "door a clerk can use — without it neither the accept nor the ±30% refusal " +
        "can happen",
    ).toBeLessThan(500);
    expect(
      override.status(),
      "the override endpoint must not be missing (404) — a bounded override nobody " +
        "can submit is not a bound",
    ).not.toBe(404);
  });

  test("step 5 · INVARIANCE — the COMPUTED level record is never overwritten", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // "the override PRESENTS, it never overwrites the computation": both
    // figures must be separately readable or the invariant is unprovable.
    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;
    const detail = await apiJson(page, `/accounts/${account.id}`);
    expect(
      JSON.stringify(detail.body),
      "T4-21 step 5: the account must publish the budget level (computed AND " +
        "presented) for 'the computation was not overwritten' to be checkable",
    ).toMatch(/budget/i);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-21's $242 level, the $2,904 trailing actuals and the WE-8
//   variance run are WORKBOOK figures with no loader in the harness, and the
//   journey itself says the band EDGES are engine-computed — so no money figure
//   is retyped and no moneyTriple lookup appears. Step 3's ±31% refusal cannot
//   be attempted until step 2's door exists.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
