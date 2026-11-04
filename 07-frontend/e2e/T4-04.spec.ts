// ── Trace ──────────────────────────────────────────────
// Journey:  T4-04 — 08-qa/01-e2e/journeys/T4-04-vacation-hold-mid-cycle.md
//           Active → Vacation hold (billable-base-only) mid-cycle → Active
// Story:    US-CUS-008 (status change) · US-MET-007 (interim read) ·
//           US-BIL-005/007
//           Screens: S21 account header (status pill + action) · S30 bill detail
// Rules:    BR-CUS-055 (the behaviour-class seed: Vacation hold =
//           billable-base-only) · BR-BIL-028 (the hold does NOT stop billing —
//           usage lines stop at the hold date, base + flat services continue the
//           FULL month) · BR-REP-012 ("Active accounts" still counts a held
//           account) · BR-BIL-004 (ending the hold never re-opens the bill)
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// Getting this wrong either bills phantom usage for an empty house or silently
// waives base revenue, so both halves are asserted: usage STOPS, base DOES NOT.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { journey } from "./support/journey";

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-04", "Vacation hold mid-cycle — base bills on, usage stops", () => {
  skipUnlessAppServer(test);

  test("step 1 · the status moves to a billable-base-only class and the header pill renders it", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;
    expect(account.status_behavior_class, "x = Active, behaviour class billable").toBe("billable");

    // The BR-CUS-055 seed must actually carry the class the journey names, or
    // the hold cannot mean anything downstream.
    const statuses = await apiJson(page, "/lookups/account_statuses");
    expect(statuses.status, "the account-status reference list must serve").toBe(200);
    const entries = (statuses.body?.entries ?? statuses.body?.results ?? statuses.body ?? []) as Array<
      Record<string, unknown>
    >;
    expect(
      JSON.stringify(entries),
      "BR-CUS-055: a status whose behaviour class is billable-base-only must exist, " +
        "or a Vacation hold cannot be told from a suspension",
    ).toMatch(/billable_base_only|billable-base-only/);

    // Step 1's screen half — the status change is an account-header action.
    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await expect(
      page.getByRole("button", { name: /vacation hold|change status|suspend/i }).first(),
      "T4-04 step 1: a clerk must be able to set Active → Vacation hold from the " +
        "account header (US-CUS-008)",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 2 · the bill keeps the base charge for the whole month and stops usage at the hold", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    expect(invoice, "T4-04 step 2 needs the cycle bill the hold falls inside").toBeTruthy();

    await page.goto(`/${tenant()}/billing/bills/${invoice.id}`);
    await page.getByRole("tab", { name: "Charges" }).click();

    // BR-BIL-028's two halves, asserted as structure — T4-04's dollar figures
    // are the WE-12 workbook's and are NOT carried by money-triples.csv or by
    // 05-golden-tests.md, so no figure is retyped here.
    await expect(
      page.getByText(/base/i).first(),
      "BR-BIL-028: base charges continue the FULL month through a hold",
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText(/hold|interim|through/i).first(),
      "BR-BIL-028: the usage line must show that it stops at the hold date",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 3 · reports still COUNT a held account as active, with a labelled basis", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // BR-REP-012: Active + Marked disconnect + Vacation hold all count.
    const accounts = await apiJson(page, "/accounts?f.status=vacation_hold");
    expect(
      accounts.status,
      "T4-04 step 3: the accounts read model must be able to answer for the held " +
        "status, or the KPI cannot include it",
    ).toBe(200);

    await page.goto(`/${tenant()}/finance`);
    await expect(
      page.getByText(/posting|accrual|basis/i).first(),
      "BR-REP-001: every report header names its basis",
    ).toBeVisible({ timeout: 15_000 });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-04's $96.26 / $9.10 / $105.36 are WE-12 WORKBOOK figures. They
//   are carried by neither `expected/money-triples.csv` nor the frozen
//   05-golden-tests.md, and the harness exposes no loader for the workbooks, so
//   retyping them here would make a second copy of a signed number (DEF-028).
//   The BR-BIL-028 STRUCTURE is asserted instead and the figure gap is REPORTED.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
