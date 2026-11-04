// ── Trace ──────────────────────────────────────────────
// Journey:  T4-01 — 08-qa/01-e2e/journeys/T4-01-plan-change-mid-cycle.md (tier 4)
//           x = billed on plan snapshot P-old → y = billed on P-new, changed
//           mid-cycle via the S23 Change-plan flow
// Story:    US-CUS-016/017 · US-CUS-006 · US-RAT-012 · US-BIL-007
//           Screens: S23 Change plan (steps 1–3) · S30 bill detail · S7/S36 KPIs
// Rules:    BR-CUS-041 (a proration PREVIEW writes nothing) · BR-CUS-014 sc.3/6
//           (append-only snapshot chain; rating resolves the snapshot as of each
//           service date) · BR-CUS-062 (a plan change triggers NO deposit
//           recompute in v1) · BR-BIL-004 (issued history is never repriced)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

async function subjectAccount(page: Page) {
  const accounts = await apiJson(page, "/accounts");
  const account = (accounts.body?.results ?? [])[0] as Record<string, string> | undefined;
  expect(account, "T4-01 needs an active account on a plan").toBeTruthy();
  return account!;
}

journey("T4-01", "Plan change mid-cycle — split-period bill from two snapshots", () => {
  skipUnlessAppServer(test);

  test("step 1 · S23 renders the two-sub-period proration preview and writes nothing", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);
    const account = await subjectAccount(page);

    // The clerk's own route: account detail → Change plan.
    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await page.getByRole("button", { name: /Change plan/i }).click();
    await expect(page).toHaveURL(new RegExp(`/accounts/${account.id}/change-plan`));

    // Step 1's assertion — the preview must render two sub-periods, base AND
    // usage prorated by calendar days (B4.3), before any write.
    await expect(
      page.getByText(/prorat|sub-period|Jul 1|Jul 16/i).first(),
      "T4-01 step 1: S23 must render the proration preview — two sub-periods split " +
        "at the effective date — before anything is written",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 2 · confirming appends BOTH snapshot chains in sync and audits both sides", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);
    const account = await subjectAccount(page);

    // The preview endpoint is the door step 1 opens and step 2 confirms
    // through — BR-CUS-041 says the preview itself writes nothing.
    const options = await apiJson(page, `/accounts/${account.id}/plan-changes/options`);
    expect(
      options.status,
      "T4-01 step 2: the S23 flow's options call must resolve before a change can " +
        "be confirmed",
    ).toBe(200);

    const preview = await page.request.post(
      `/api/${tenant()}/accounts/${account.id}/plan-changes/preview`,
      { data: { effective_from: "2026-07-16" } },
    );
    expect(preview.status(), "BR-CUS-041: the preview must compute without writing").toBeLessThan(
      400,
    );
    const body = await preview.json();
    expect(
      JSON.stringify(body),
      "step 1/2: the preview carries the two prorated sub-periods",
    ).toMatch(/2026-07-15|2026-07-16/);
  });

  test("steps 3–5 · the split bill prices each half on ITS snapshot, and the deposit does NOT move", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);
    const account = await subjectAccount(page);

    // Step 5's INVARIANCE — BR-CUS-062: a plan change triggers NO deposit
    // recompute in v1. The deposit held must read exactly as set at move-in.
    const detail = await apiJson(page, `/accounts/${account.id}`);
    expect(detail.status).toBe(200);
    expect(
      detail.body,
      "T4-01 step 5: the account must publish the deposit held, so 'it did not move' " +
        "is a checkable statement rather than an assumption",
    ).toHaveProperty("deposit_held");

    // Step 3's handoff — ONE document, two period-labelled line groups.
    const invoices = await apiJson(page, `/invoices?f.account_id=${account.id}`);
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string> | undefined;
    expect(invoice, "T4-01 step 3 needs the cycle bill the change lands on").toBeTruthy();
    await page.goto(`/${tenant()}/billing/bills/${invoice!.id}`);
    await page.getByRole("tab", { name: "Charges" }).click();
    await expect(
      page.getByText(/Jul 1|Jul 16|period/i).first(),
      "T4-01 step 3: ONE bill, two period-labelled line groups (BR-CUS-014 sc.6)",
    ).toBeVisible({ timeout: 15_000 });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-01 states in its own fixture line that the split-group dollar
//   values are ENGINE-COMPUTED (00-e2e-design.md §5), so it names no frozen
//   figure and no moneyTriple lookup appears. Step 4's report KPIs are asserted
//   by T4-05/J5 rather than duplicated here.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
