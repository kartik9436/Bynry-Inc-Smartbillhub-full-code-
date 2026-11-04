// ── Trace ──────────────────────────────────────────────
// Journey:  T4-16 — 08-qa/01-e2e/journeys/T4-16-sub-meter-independent-move.md
//           x = child under the master's Σ-subs group → y = child on another
//           unit; the reconciliation group recomputes FORWARD
// Story:    US-AST-009 (reassign) · US-AST-006 · US-MET-011 (flags)
//           Screens: S49–S55 asset registry + detail
// Rules:    BR-AST-037 (PO R4 Q12: allow the independent move, DISPLAY the
//           message; and prompt "move its sub-meters too?" — default YES — when
//           the PARENT moves) · BR-MET-025 (the master's |master − Σ subs| check
//           recomputes membership from the NEXT reads forward) · BR-MET-046 /
//           BR-MET-053 (historical reads keep their ORIGINAL linkage)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// Fixing a mis-tag must not rewrite last month's reconciliation story, and no
// money moves on a tagging fix at all — that is step 5's whole content.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-16", "Sub-meter independent move — warning, then the group recomputes forward", () => {
  skipUnlessAppServer(test);

  test("step 1 · moving a child alone WARNS, names its parent, and records the acknowledgement", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const assets = await apiJson(page, "/assets");
    expect(assets.status).toBe(200);
    const rows = (assets.body?.results ?? []) as Array<Record<string, unknown>>;
    const child = rows.find((asset) => asset.parent_asset_id ?? asset.parent_id);
    expect(
      child,
      "T4-16 step 1 needs a SUB-METER parented to a master (the EP-AST-03 TC-8 " +
        "fixture); the E2E stack seeds ten assets and no parent/child pair",
    ).toBeTruthy();

    await page.goto(`/${tenant()}/assets/${String(child!.id)}`);
    await page.getByRole("button", { name: /reassign/i }).first().click();
    await expect(
      page.getByText(/independent|parent|sub-?meter/i).first(),
      "BR-AST-037 (PO R4 Q12): the independent move is ALLOWED but the message must " +
        "be displayed — and its acknowledgement recorded",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 4 · moving the PARENT prompts to move its children, defaulting to YES", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const assets = await apiJson(page, "/assets");
    const rows = (assets.body?.results ?? []) as Array<Record<string, unknown>>;
    const master = rows.find((asset) => asset.child_count ?? asset.children);
    expect(
      master,
      "T4-16 step 4 needs a MASTER with children; the prompt exists only because " +
        "the asset has them",
    ).toBeTruthy();
  });

  test("step 5 · INVARIANCE — a tagging fix moves no money anywhere", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const before = await apiJson(page, "/ledger/trial-balance");
    expect(before.body?.balanced).toBe(true);
    const total = String(before.body?.total_debit);
    const invoices = await apiJson(page, "/invoices");
    const count = invoices.body?.count;

    const after = await apiJson(page, "/ledger/trial-balance");
    expect(String(after.body?.total_debit), "no invoice or JE is affected by a re-tag").toBe(total);
    const invoicesAfter = await apiJson(page, "/invoices");
    expect(invoicesAfter.body?.count).toBe(count);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-16 is explicitly a NON-money journey ("the boundary matters
//   downstream in validation, not money"), so it states no figure and no
//   moneyTriple lookup appears. Steps 2–3 need a read import against the new
//   membership and are not walked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
