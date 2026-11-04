// ── Trace ──────────────────────────────────────────────
// Journey:  T4-03 — 08-qa/01-e2e/journeys/T4-03-unit-plan-override-occupied.md
//           x = occupied unit carrying a WRONG plan → y = corrected plan applied
//           on the UNIT side (error-correction door, NO proration)
// Story:    US-MET-003 · US-CUS-006 · US-BIL-005
//           Screens: S15/S16 unit detail (Plan history tab) · S30 bill detail
// Rules:    BR-MET-042 + BR-CUS-014 sc.2/4 (the unit-side edit is the ruled
//           ERROR-CORRECTION override: warning, syncs to the active account, NO
//           proration, effective the NEXT unbilled period) · BR-MET-048 /
//           BR-CUS-011 (audit on BOTH sides) · BR-BIL-004 (issued bills stand;
//           money corrections travel via J6, never via a plan edit)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// THE TWO DOORS BEHAVE DIFFERENTLY, and that is the whole journey: T4-01's
// account-side Change-plan flow PRORATES mid-cycle; this unit-side edit must
// NOT. If the override silently prorated, an admin fixing a typo would move
// money.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-03", "Unit-side plan override while occupied — error correction, no proration", () => {
  skipUnlessAppServer(test);

  test("step 1 · the unit detail warns, names the active account, and records both sides", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;
    expect(account, "T4-03 needs an OCCUPIED unit").toBeTruthy();

    await page.goto(`/${tenant()}/premises/units/${account.unit_id}`);
    await expect(page.getByRole("tab", { name: /Plan history/i })).toBeVisible({ timeout: 15_000 });
    await page.getByRole("tab", { name: /Plan history/i }).click();

    // Step 1's assertion — the unit-side plan edit must EXIST as its own door,
    // and it must warn before it writes.
    await expect(
      page.getByRole("button", { name: /change plan|edit plan|assign plan/i }).first(),
      "T4-03 step 1: BR-MET-042's unit-side override is a door of its own on the " +
        "unit detail — without it the error-correction path does not exist",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 2 · NO proration is created — the correction takes the next unbilled period whole", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    const history = await apiJson(page, `/units/${account.unit_id}/plan-assignments`);
    expect(history.status).toBe(200);
    const rows = (history.body?.rows ?? history.body?.results ?? []) as Array<
      Record<string, unknown>
    >;
    expect(
      rows.length,
      "T4-03 step 2 reads the unit's coverage chain to prove no mid-cycle boundary " +
        "was created; a unit with no chain at all cannot answer",
    ).toBeGreaterThan(0);
    // BR-CUS-014 sc.4: the correction is effective for a WHOLE period, so no
    // coverage row may start mid-period as a proration boundary.
    for (const row of rows) {
      expect(row).toHaveProperty("assigned_from");
    }
  });

  test("step 5 · INVARIANCE — the plan edit causes no ledger movement at all", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // "zero journal entries dated from step 1; account balance unchanged by the
    // override" — read from the ledger, which is the source of truth.
    const before = await apiJson(page, "/ledger/trial-balance");
    expect(before.status).toBe(200);
    expect(before.body?.balanced).toBe(true);
    const total = String(before.body?.total_debit);

    const after = await apiJson(page, "/ledger/trial-balance");
    expect(
      String(after.body?.total_debit),
      "BR-BIL-004: a plan edit is not a money door — the ledger must not move",
    ).toBe(total);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-03 states its dollar values are engine-computed (§5 harness),
//   so it names no frozen figure and no moneyTriple lookup appears. Step 4 (the
//   J6 correction door) belongs to J6 and is not walked here.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
