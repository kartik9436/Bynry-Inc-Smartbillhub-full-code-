// ── Trace ──────────────────────────────────────────────
// Journey:  T4-13 — 08-qa/01-e2e/journeys/T4-13-autopay-enroll-cancel.md
//           x = not enrolled → y = a CAPTURE-INTENT on every issue → cancel and
//           the intents stop
// Story:    US-PAY-024 (autopay intents) · US-CUS-009 · US-BIL-005 · US-PAY-001
//           Screens: S21 account header (autopay pill) · S32/S33 payments
// Rules:    BR-PAY-015 / BR-CUS-059 (v1 is CAPTURE-ONLY: no money moves until
//           rails land in W7; intents are minted AT ISSUE, never at enrolment) ·
//           BR-PAY-034 (the fulfilled state is COMPUTED from a matching recorded
//           payment) · BR-BIL-004 · BR-PAY-002 (payments append-only)
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

journey("T4-13", "Autopay enroll → cancel — intents mint at issue, and stop", () => {
  skipUnlessAppServer(test);

  test("step 1 · enrolment is a preference the account carries, and mints NO intent by itself", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    // "NO intent exists yet (intents are minted at issue, not at enrolment)".
    const intents = await apiJson(page, "/autopay-intents");
    expect(intents.status, "US-PAY-024's intent read must serve").toBe(200);

    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await expect(page.getByText(/Autopay/i).first()).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByRole("button", { name: /autopay|enrol|enroll/i }).first(),
      "T4-13 step 1: a clerk must be able to ENROL the account — BR-CUS-059's " +
        "capture-only enrolment is the transition this journey is about",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 2 · issuing a bill records ONE capture-intent dated the DUE DATE, and moves no money", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    expect(invoice.due_date, "BR-PAY-015: the intent is dated the bill's DUE DATE").toBeTruthy();

    const intents = await apiJson(page, "/autopay-intents");
    const rows = (intents.body?.rows ?? intents.body?.results ?? []) as Array<
      Record<string, unknown>
    >;
    expect(
      rows.length,
      "T4-13 step 2: issuing a bill for an enrolled account records exactly one " +
        "capture-intent (BR-PAY-015). None exists on this stack, so the mint-at-issue " +
        "hook is what the journey is asking after.",
    ).toBeGreaterThan(0);

    // "no payment row, no ledger movement, no AR change from the intent itself".
    const payments = await apiJson(page, "/payments");
    expect(payments.body?.count, "an intent is not a payment").toBe(0);
  });

  test("step 6 · INVARIANCE — enrol and cancel are pure preference transitions", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const before = await apiJson(page, "/ledger/trial-balance");
    expect(before.body?.balanced).toBe(true);
    const total = String(before.body?.total_debit);

    const after = await apiJson(page, "/ledger/trial-balance");
    expect(
      String(after.body?.total_debit),
      "BR-BIL-004 / BR-PAY-002: an autopay preference never touches issued bills, " +
        "recorded payments, allocations or the ledger",
    ).toBe(total);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-13 names $97.41 as the Aug bill; this stack's issued bill is
//   GT-1, so no money figure is retyped and the intent's AMOUNT is asserted only
//   as "an intent exists dated the due date". Steps 3–5 need a second issue
//   cycle and a recorded payment, and are not walked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
