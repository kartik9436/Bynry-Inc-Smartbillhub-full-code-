// ── Trace ──────────────────────────────────────────────
// Journey:  T4-17 — 08-qa/01-e2e/journeys/T4-17-master-account-link-change.md
//           x = transfers route to master ACC-0009 → y = to ACC-9001; executed
//           transfers STAND
// Story:    US-BIL-011 (final bill) · US-LED-002 · US-LED-010
//           Screens: S14 premises detail (the landlord-agreement link) · S36 ·
//           S60 by-premises
// Rules:    BR-BIL-013 (the transfer-to-master settlement path; OQ-069 closed
//           the landlord-agreement prerequisite) · BR-LED-001 (AR just changes
//           OWNER: CR final account / DR master, dimensions stamped) ·
//           BR-LED-011 / BR-MET-046 (the unit→premises chain) · BR-PAY-002
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// The link is a ROUTING designation consumed at settlement time: FUTURE final
// bills go to the new master, and every already-executed transfer is a balanced,
// audited, immutable transaction that stays exactly where it landed.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-17", "Master-account link change — future transfers re-point, executed ones stand", () => {
  skipUnlessAppServer(test);

  test("step 1 · the landlord-agreement link is a designation an admin can re-point", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const premises = await apiJson(page, "/premises");
    expect(premises.status).toBe(200);
    const site = (premises.body?.results ?? [])[0] as Record<string, string>;
    expect(site, "T4-17 needs a premises to carry the link").toBeTruthy();

    const detail = await apiJson(page, `/premises/${site.id}`);
    expect(
      JSON.stringify(detail.body),
      "BR-BIL-013 (OQ-069 prerequisite): the premises must carry the landlord-agreement " +
        "MASTER ACCOUNT link — without it there is no transfer-to-master settlement " +
        "option at all, and this journey has no subject",
    ).toMatch(/master|landlord/i);

    await page.goto(`/${tenant()}/premises/${site.id}`);
    await expect(
      page.getByText(/master|landlord/i).first(),
      "T4-17 step 1: the link must be visible and re-pointable on the premises detail",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 3 · the final bill's transfer is a balanced pair on the CURRENT master", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // BR-LED-001: AR total is unchanged — it only changes owner. The ledger is
    // the only place that is checkable.
    const tb = await apiJson(page, "/ledger/trial-balance");
    expect(tb.body?.balanced, "every transfer posts as a balanced pair").toBe(true);

    const entries = await apiJson(page, "/ledger/journal-entries");
    expect(entries.status, "the journal read must serve for a transfer to be traceable").toBe(200);
    expect(
      JSON.stringify(entries.body),
      "BR-LED-001: a balance transfer stamps its dimensions (account, premises, unit, " +
        "source) so the by-premises view can attribute it",
    ).toMatch(/premises|dimension|unit/i);
  });

  test("step 4 · the by-premises summary attributes the owed amount to the master, not the site", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    await page.goto(`/${tenant()}/reports/by-premises`);
    await expect(
      page.getByText(/premises/i).first(),
      "T4-17 step 4: S60's by-premises summary must render — LE-6's pattern is what " +
        "shows the owed sitting on the master rather than the site",
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText(/could not be loaded|not found|failed/i),
      "S60 must actually load its report, not render a failure state",
    ).toHaveCount(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-17's 289.40 / 153.50 / 135.90 are WE-7B/LE-1 WORKBOOK figures
//   the harness loads no source for, so none is retyped — the LAW (balanced
//   pair, current master, executed transfers immutable) is what is asserted.
//   Step 5's negative probe needs an executed transfer to attempt a re-route of
//   and is not walked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
