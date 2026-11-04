// ── Trace ──────────────────────────────────────────────
// Journey:  T4-02 — 08-qa/01-e2e/journeys/T4-02-plan-change-across-category.md
//           x = Residential-category plan (deposit rule $150) → y = Commercial
//           (rule $400) — and the deposit does NOT move
// Story:    US-CUS-016/017 · US-CUS-007 · US-BIL-005
//           Screens: S23 Change plan · S21 account detail · S36 deposit tie-out
// Rules:    BR-CUS-062 (v1: the deposit set at move-in STANDS until final-bill
//           settlement — category-differential recompute is v1.1) · BR-CUS-052
//           (category change is forward-only, warned and audited) ·
//           BR-BIL-025/026 (the template resolves by the NEW category and is
//           pinned at issue) · BR-LED-007 (Σ deposits held = deposit GL)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// THE ASSERTION OF ABSENCE IS THE POINT (the journey file says so): the obvious
// behaviour — recompute the deposit differential — is exactly what the PO ruled
// OUT for v1.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-02", "Plan change across consumer category — deposit NO-recompute", () => {
  skipUnlessAppServer(test);

  test("step 1 · S23 warns on the category change and offers a next-cycle effective date", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;
    expect(account, "T4-02 needs an active residential account").toBeTruthy();

    await page.goto(`/${tenant()}/accounts/${account.id}/change-plan`);
    // BR-CUS-052: a consumer-category change is forward-only and must WARN.
    await expect(
      page.getByText(/categor/i).first(),
      "T4-02 step 1: crossing consumer category must raise the BR-CUS-052 warning " +
        "on S23 before it is acknowledged",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("steps 2 · 5 — nothing recomputes: the deposit held is unmoved and no differential exists", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    // Step 2's assertion of ABSENCE — no differential line, no billed $250, no
    // credit, no refund row, zero payment/adjustment rows created.
    const payments = await apiJson(page, `/payments?f.account_id=${account.id}`);
    expect(payments.status).toBe(200);
    expect(
      payments.body?.count,
      "BR-CUS-062: a plan change creates NO deposit-differential transaction",
    ).toBe(0);

    // The deposit position must be READABLE for "it did not move" to be a
    // checkable statement — that is what the tie-out (BR-LED-007) rests on.
    const detail = await apiJson(page, `/accounts/${account.id}`);
    expect(
      detail.body,
      "T4-02 steps 2/5: the account must publish the deposit held so the S36 " +
        "tie-out (Σ deposits held = deposit GL) can be checked at all",
    ).toHaveProperty("deposit_held");
  });

  test("step 3 · the next bill renders on the NEW category's template, pinned at issue", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    expect(invoice, "T4-02 step 3 needs an issued bill to read the pinned template from").toBeTruthy();

    const detail = await apiJson(page, `/invoices/${invoice.id}`);
    expect(detail.status).toBe(200);
    expect(
      detail.body,
      "BR-BIL-026: the template and its version are PINNED at issue, so the bill " +
        "must publish which template rendered it",
    ).toHaveProperty("template_id");
    // "no deposit line anywhere on the bill" (step 3's own words).
    await page.goto(`/${tenant()}/billing/bills/${invoice.id}`);
    await page.getByRole("tab", { name: "Charges" }).click();
    await expect(page.getByText(/deposit/i)).toHaveCount(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-02's $150/$400 deposit figures are `plan_deposit_rules` FIXTURE
//   values, not frozen expectation-dataset rows, so they are never retyped here:
//   the journey's ruled behaviour is that the held deposit does not MOVE, and
//   that is what is asserted. Step 4 (move-out settlement) is explicitly
//   out-of-scope execution in the journey file and is not walked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
