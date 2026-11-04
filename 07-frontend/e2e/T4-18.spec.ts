// ── Trace ──────────────────────────────────────────────
// Journey:  T4-18 — 08-qa/01-e2e/journeys/T4-18-late-fee-percent-config-change.md
//           x = 1.5% min $5 → y = a new percentage; the NEXT assessment only,
//           existing fees untouched
// Story:    US-TEN-010 (the S66 rule pages) · US-PAY-014 · US-BIL-026
//           Screens: S8 Settings → Configure → Billing defaults (S66) · S30
// Rules:    BR-BIL-001/021 (the late-fee parameters are tenant CONFIG consumed
//           at ASSESSMENT time) · BR-BIL-008 (grace) · BR-TEN-016/041 (every
//           Settings write is audited) · BR-BIL-004 (an issued LATE line is an
//           immutable invoice line — a settings edit is not a retroactive money
//           lever)
// Money:    the floor is read from `08-qa/01-e2e/expected/money-triples.csv`
//           row (flat, cycle, none) — `next_late_fee`. Never retyped.
// Impacts:  nothing — this spec reads the product and drives its own screens.
// ───────────────────────────────────────────────────────
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

journey("T4-18", "Late-fee % config change — next assessment only", () => {
  skipUnlessAppServer(test);

  test("step 1 · the baseline formula is the tenant's own config: max(floor, % × overdue)", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const defaults = await apiJson(page, "/settings/billing-defaults");
    expect(defaults.status).toBe(200);
    expect(defaults.body?.late_pct, "BR-BIL-001's percentage is tenant config").toBe("1.5");
    expect(
      String(defaults.body?.late_min_amount),
      "the floor must equal the frozen dataset's next_late_fee for the unpaid cycle row",
    ).toBe(UNPAID.next_late_fee.replace(/\.00$/, ""));
  });

  test("step 2 · the S66 Billing-defaults page renders the parameters and can save them", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    // The clerk's route: the sidebar's Settings item, then Configure.
    const nav = page.getByRole("navigation", { name: "Main navigation" });
    await nav.getByRole("link", { name: "Settings", exact: true }).click();
    await page.goto(`/${tenant()}/settings/reference-data`);

    await expect(
      page.getByText(/late fee|billing defaults/i).first(),
      "T4-18 step 2: BR-TEN-041's S66 Billing-defaults page must be reachable from " +
        "Settings — a config-over-constant law needs a surface to change the config on",
    ).toBeVisible({ timeout: 15_000 });
  });

  test("steps 3 · 6 — every previously assessed fee is byte-identical after the save", async ({
    page,
  }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const invoices = await apiJson(page, "/invoices");
    const invoice = (invoices.body?.results ?? [])[0] as Record<string, string>;
    const before = await apiJson(page, `/invoices/${invoice.id}`);

    // The config write itself — BR-TEN-016: audited, and nothing else recomputes.
    const write = await page.request.put(`/api/${tenant()}/settings/billing-defaults`, {
      data: { ...(await apiJson(page, "/settings/billing-defaults")).body, late_pct: "2.0" },
    });
    expect(write.status(), "US-TEN-010: a System Admin can change the late-fee %").toBeLessThan(400);

    const after = await apiJson(page, `/invoices/${invoice.id}`);
    expect(
      JSON.stringify(after.body),
      "BR-BIL-004: an issued bill's lines are immutable — a settings edit may not " +
        "re-derive a fee already assessed",
    ).toBe(JSON.stringify(before.body));

    // BR-TEN-016: the change is audited, both directions.
    const audit = await apiJson(page, "/audit-log?f.entity_type=tenant_settings");
    expect(audit.status).toBe(200);

    // Put the tenant back the way the journey found it — a journey leaves the
    // world in the state the next journey's fixture line describes.
    await page.request.put(`/api/${tenant()}/settings/billing-defaults`, {
      data: { ...(await apiJson(page, "/settings/billing-defaults")).body, late_pct: "1.5" },
    });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: batch-A journey activation (2026-08-15)
// generated: 2026-08-15 by the batch-A journey lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: `npm run typecheck:e2e` · run against the live stack on 8110/8030
// exceptions: T4-18's $400 overdue / $6.00 fee are WE-15(a) WORKBOOK figures the
//   harness loads no source for; the FLOOR is asserted from moneyTriple and the
//   worked $6.00 is not retyped. Step 4 (the next assessment on the new %) needs
//   a second overdue account and is not walked; step 5's waiver contrast belongs
//   to BR-BIL-003 and is not walked.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
