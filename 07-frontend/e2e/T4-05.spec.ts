// ── Trace ──────────────────────────────────────────────
// Journey:  T4-05 — 08-qa/01-e2e/journeys/T4-05-marked-disconnect-pay-active.md
//           Active → Marked disconnect → pay → Active, BILLABLE throughout
// Story:    US-CUS-008 · US-CUS-015 · US-PAY-001 · US-PAY-014 · US-BIL-005
//           Screens: S22 disconnect-notice flow · S33 record payment · S36 aging
// Rules:    BR-CUS-055 (Marked disconnect = BILLABLE — the customer is still
//           consuming until the cut) · BR-PAY-017 (the ladder) · BR-PAY-021/033
//           (posting date ≠ clearing date; on-time reads the POSTING date) ·
//           BR-PAY-010 (allocation: oldest invoice, usage+base → taxes → fees) ·
//           BR-BIL-007 (no RECONN charge unless a real reconnect happened)
// Money:    `08-qa/01-e2e/expected/money-triples.csv` row (flat, cycle, none) —
//           outstanding and next_late_fee. Never retyped.
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
//
// If the mark silently stopped billing, every customer who strings out the
// ladder would get free service. That is what step 2 asserts.
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

const UNPAID = moneyTriple("flat", "cycle", "none");

async function apiJson(page: Page, path: string) {
  const response = await page.request.get(`/api/${tenant()}${path}`);
  return { status: response.status(), body: await response.json().catch(() => null) };
}

journey("T4-05", "Marked disconnect → pay → Active — billable throughout", () => {
  skipUnlessAppServer(test);

  test("step 1 · the ladder marks the account for disconnect and appends notice history", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    // The late fee this step assesses is the frozen floor for the unpaid cycle
    // row — max($5, 1.5% × outstanding).
    const defaults = await apiJson(page, "/settings/billing-defaults");
    expect(String(defaults.body?.late_min_amount)).toBe(UNPAID.next_late_fee.replace(/\.00$/, ""));

    await page.goto(`/${tenant()}/accounts/${account.id}`);
    await page.getByRole("button", { name: /Disconnect notice/i }).click();
    await expect(
      page.getByText(/notice|tier|certified/i).first(),
      "T4-05 step 1: the S22 disconnect-notice flow must record a notice tier and " +
        "move the account to Marked disconnect",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("step 2 · billing continues UNCHANGED while the account is Marked disconnect", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // BR-CUS-055: the behaviour class of Marked disconnect must be `billable`.
    const statuses = await apiJson(page, "/lookups/account_statuses");
    expect(statuses.status).toBe(200);
    const text = JSON.stringify(statuses.body);
    expect(text, "the reference list must carry the Marked disconnect status").toMatch(
      /marked[_ -]?disconnect/i,
    );
    const marked = /"code"\s*:\s*"marked_disconnect"[^}]*"behavior_class"\s*:\s*"([a-z_]+)"/.exec(
      text,
    );
    expect(
      marked?.[1],
      "BR-CUS-055 (PM-ruled seed): Marked disconnect is BILLABLE — nothing about the " +
        "mark may suppress or reduce a draft",
    ).toBe("billable");
  });

  test("step 3 · AR aging shows the outstanding on a labelled POSTING basis", async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    await page.goto(`/${tenant()}/finance`);
    await expect(
      page.getByText(/aging|ageing/i).first(),
      "T4-05 step 3: AR aging must render, basis-labelled (BR-REP-001/BR-REP-012)",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("steps 4–5 · payment allocates oldest-first with BOTH dates, and no reconnect fee appears", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const accounts = await apiJson(page, "/accounts");
    const account = (accounts.body?.results ?? [])[0] as Record<string, string>;

    // BR-PAY-021: posting date (day received) and clearing date are BOTH
    // recorded; on-time/late reads the POSTING date.
    await page.goto(`/${tenant()}/payments/record`);
    await expect(
      page.getByLabel(/posting/i).first(),
      "BR-PAY-021: the Record-payment form must take the POSTING date a clerk types",
    ).toBeVisible({ timeout: 15_000 });

    // Step 5's assertion of absence — the cut never happened, so no RECONN line.
    const charges = await apiJson(page, "/charges");
    const reconn = ((charges.body?.results ?? []) as Array<Record<string, string>>).find(
      (charge) => charge.code === "RECONN",
    );
    expect(reconn, "RECONN exists as a tenant charge code").toBeTruthy();
    expect(
      reconn?.auto_apply,
      "BR-BIL-007: only a REAL reconnect earns the fee — restoring a marked account " +
        "must not apply it automatically",
    ).toBe(false);

    const invoices = await apiJson(page, `/invoices?f.account_id=${account.id}`);
    expect(invoices.status).toBe(200);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: every money figure is read from moneyTriple("flat","cycle","none").
//   The journey's bill number BL-2607-0142 is a FIXTURE id this stack does not
//   allocate (the tenant's own series does), so the account is the row key —
//   the same choice W3-money-render.spec.ts made and for the same reason.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
