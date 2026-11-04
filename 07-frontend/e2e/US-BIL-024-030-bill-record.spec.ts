// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-023 / US-BIL-024 (the outbound delivery queue, and the READ
//           that says where ONE bill went) ·
//           US-BIL-030 (the terminal stages' two guarantees: the saved bill
//           ties out to its charge lines, and the posted amounts balance)
//           Screens: S30 (bill detail)
// Rules:    BR-BIL-016 (delivery is a QUEUE, per channel, per bill) ·
//           BR-BIL-032 (the stamped instance ties out to its rows — "drift can
//           never be silent") · BR-BIL-011 (one balanced journal entry per
//           bill) · BR-SHL-020 (plain language) · CLAUDE.md rule 2 (money
//           travels with its currency)
// Impacts:  06-backend/apps/billing/selectors.py (`_deliveries_for`,
//           `_integrity_for`) · 07-frontend BillDetailPage
// ───────────────────────────────────────────────────────
//
// HARD-WON LAW 6 AND LAW 7, TOGETHER. Both of these shipped as engines with no
// question asked of them, and both were invisible to every unit test in the
// repo because the tests fed the engines directly:
//
//   · `issue.py` wrote a delivery row for every bill it issued from
//     2026-08-11, and `GET /invoices/{id}` answered a hardcoded
//     `deliveries: null`, so S30's delivery panel — BUILT, and shipped with
//     the screen — printed *"That queue is not built"* on every bill in the
//     product;
//   · `pipeline.tie_out_document` and `pipeline.balanced_handoff` had NO
//     caller outside their own test file, so BR-BIL-032's "drift can never be
//     silent" was enforced against fixtures and against no real bill.
//
// **THREE LANES ON 2026-08-16 SHIPPED A BROWSER CHECK THAT PASSED AGAINST THE
// BROKEN SCREEN**, so each assertion below is written against the thing that
// was actually wrong: the OLD sentence must be gone, and the NEW figures must
// be on the page. Asserting only that the panel exists would have passed
// before any of this was built.
import { expect, test } from "@playwright/test";

import { signIn, tenant, skipUnlessAppServer } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

function fixtureAccountNo(): string {
  return process.env.E2E_ACCOUNT_NO ?? "E2E-10001";
}

test.describe(
  "US-BIL-024 / US-BIL-030 — what a clerk can now learn from a bill",
  { tag: APP_SERVER_TAG },
  () => {
    skipUnlessAppServer(test);

    test("the bill says where it went and whether its own record agrees", async ({ page }) => {
      await signIn(page);

      // A human clicking, not a URL typed.
      const nav = page.getByRole("navigation", { name: "Main navigation" });
      await nav.getByRole("link", { name: "Billing", exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing$`));

      const row = page.getByRole("row").filter({ hasText: fixtureAccountNo() }).first();
      await expect(row).toHaveCount(1);
      await row.getByRole("link").first().click();
      await expect(page).toHaveURL(new RegExp(`/${tenant()}/billing/bills/`));

      // ── US-BIL-030 · the record check ────────────────────────────────────
      // Neither of these two sentences existed on any screen before today.
      await expect(page.getByText("Saved bill matches its charge lines")).toBeVisible();
      await expect(page.getByText("Posted amounts add up to the amount owed")).toBeVisible();

      // THE VERDICT, not merely the label. A panel that rendered its headings
      // and answered "Not checked" for both would satisfy a presence-only
      // check and tell a clerk nothing — which is the shape three browser
      // checks shipped in today.
      await expect(page.getByText("Yes — checked just now").first()).toBeVisible();

      // The ticket vocabulary never reaches a utility clerk (CLAUDE.md §Screen
      // IDs). Asserted on the page a human reads, not in a unit test.
      await expect(page.getByText(/BR-BIL-0\d\d/)).toHaveCount(0);

      // ── US-BIL-023/024 · the delivery queue ──────────────────────────────
      // THE SENTENCE THAT WAS ON EVERY BILL IN THE PRODUCT, asserted GONE.
      await expect(page.getByText("That queue is not built")).toHaveCount(0);

      // A row the issue path itself wrote, with its channel and its status.
      const delivery = page.getByRole("row").filter({ hasText: "Queued" }).first();
      await expect(delivery).toBeVisible();

      // And the panel says what "Queued" means here, so nobody reads a bill
      // sitting in the queue as a send that failed. Nothing in R2 sends.
      await expect(page.getByText(/Queued is the final state today/)).toBeVisible();
    });
  },
);
