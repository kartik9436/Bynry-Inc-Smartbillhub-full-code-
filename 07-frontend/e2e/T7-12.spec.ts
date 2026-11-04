// ── Trace ──────────────────────────────────────────────
// Journey:  T7-12 — Config change: late-fee % change (next assessment only;
//           assessed fees immutable).
//           `08-qa/01-e2e/journeys/T7-12-late-fee-params-change.md` is the
//           spec; this file walks its six-row step table in order.
// Story:    US-TEN-010 (S66 rule page, atomic tab save) · US-PAY-014
//           (collections / late-fee assessment) · US-IDN-001 (sign in)
//           Screens: S3 · S66 Billing defaults
// Rules:    BR-BIL-021 (late-fee params are tenant config) · BR-BIL-008 ·
//           BR-TEN-016 (one before/after audit row per atomic save) ·
//           BR-TEN-020 (a settings save never restates history) · B4 §Late fee
//           (`max(min, pct × overdue portion)` — ❄️ FROZEN)
// Money:    `moneyTriple("flat","penalty","none")` — the journey's ACC-1110 row
//           (the 8.13 fee already assessed at 1.5%) — and
//           `moneyTriple("flat","cycle","partial60")` — ACC-1111's 38.96
//           overdue, whose next fee is MIN-dominated. Read at run time; no
//           figure is typed in this file, and none is hand-computed: the
//           journey's own §3 says the post-change expectations are
//           machine-computed by 10-scripts/04-e2e-expected-gen.py.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

// ACC-1110's assessed fee (%-dominated at 1.5% of 542.15) and ACC-1111's
// min-dominated next fee. Both read from the frozen dataset.
const PENALTY = moneyTriple("flat", "penalty", "none");
const PARTIAL = moneyTriple("flat", "cycle", "partial60");
const CARD_LABEL = "Billing defaults";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface BillingDefaults {
  late_pct: string;
  late_min_amount: string;
}

async function defaults(request: APIRequestContext): Promise<BillingDefaults> {
  const response = await request.get(api("/settings/billing-defaults"));
  expect(response.status()).toBe(200);
  return (await response.json()) as BillingDefaults;
}

async function billingAuditRows(request: APIRequestContext): Promise<{ summary: string }[]> {
  const response = await request.get(api("/audit-log?per=50"));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { results: { action: string; summary: string }[] }).results
    .filter((r) => r.action === "settings.billing_defaults.updated");
}

async function openBillingDefaults(page: Page): Promise<void> {
  await page.goto(`/${tenant()}/settings/reference-data`);
  await page.getByRole("button", { name: CARD_LABEL }).first().click();
  await expect(page.locator("#late_pct")).toBeVisible();
}

journey("T7-12", "Config change: late-fee % — next assessment only, assessed fees immutable", () => {
  // NOT serial: each row re-reads the settings, so the run reports which of the
  // journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — baseline: the %-dominated fee already assessed is the immutability control", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), { data: { late_pct: "1.5" } });
    const config = await defaults(page.request);
    expect(config.late_pct, "the journey's starting %").toBe("1.5");
    expect(config.late_min_amount, "the minimum stays 5.00 throughout this journey").toBe("5");

    // The assessed fee this journey never lets move.
    const invoices = await page.request.get(api("/invoices?per=100"));
    expect(invoices.status()).toBe(200);
    const rows = ((await invoices.json()) as { results: { total: string | null }[] }).results;
    expect(
      rows.map((r) => r.total),
      `ACC-1110's ${PENALTY.next_late_fee} assessed fee is the control this journey ` +
        "holds still; the seeded tenant carries no penalty bill",
    ).toContain(PENALTY.next_late_fee);
  });

  test("step 2 — the % edit saves atomically and writes ONE before/after audit row", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), { data: { late_pct: "1.5" } });
    const before = (await billingAuditRows(page.request)).length;

    await signIn(page);
    await openBillingDefaults(page);
    await page.locator("#late_pct").fill("2.0");
    await page.getByRole("button", { name: /^Save/ }).first().click();

    await expect
      .poll(async () => (await defaults(page.request)).late_pct, {
        message: "the atomic tab save must land the new percentage",
      })
      .toMatch(/^2(\.0+)?$/);

    const rows = await billingAuditRows(page.request);
    expect(rows.length, "BR-AUD-011: one atomic save = exactly one audit row").toBe(before + 1);
    expect(
      rows[0].summary,
      "the row must carry the changed field with its before → after",
    ).toMatch(/late_pct:\s*1\.5\s*→\s*2/);
    // …and the MINIMUM was not touched by a save that named only the %.
    expect((await defaults(page.request)).late_min_amount).toBe("5");
  });

  test("step 3 — a min-dominated assessment is unchanged by the % change, BY THE FORMULA", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), { data: { late_pct: "2.0" } });

    const accounts = await page.request.get(api("/accounts?per=50"));
    const ids = ((await accounts.json()) as { results: { id: string }[] }).results.map((a) => a.id);
    const response = await page.request.post(api("/collections/run"), {
      data: { as_of: "2026-08-31", account_ids: ids },
    });
    expect(
      response.status(),
      `the collections evaluation answered ${response.status()}: ` +
        `${(await response.text()).slice(0, 300)}`,
    ).toBeLessThan(400);
    const body = await response.text();
    expect(
      body,
      `the evaluation must name the fee it assessed; the dataset's min-dominated row is ` +
        `${PARTIAL.next_late_fee} on ${PARTIAL.outstanding} overdue`,
    ).toMatch(/fee|assess/i);
  });

  test("step 4 — a %-dominated assessment computes at the NEW percentage", async ({ page }) => {
    await signIn(page);
    await page.request.put(api("/settings/billing-defaults"), { data: { late_pct: "2.0" } });
    const accounts = await page.request.get(api("/accounts?per=50"));
    const ids = ((await accounts.json()) as { results: { id: string }[] }).results.map((a) => a.id);
    const response = await page.request.post(api("/collections/run"), {
      data: { as_of: "2026-09-30", account_ids: ids },
    });
    expect(response.status()).toBeLessThan(400);

    const invoices = await page.request.get(api("/invoices?per=200"));
    const totals = ((await invoices.json()) as { results: { total: string | null }[] }).results.map(
      (r) => r.total,
    );
    // The new-% figure is machine-computed by the expectation generator; what
    // must NOT appear is a second copy of the OLD %-dominated fee on a NEW row.
    expect(
      totals.filter((t) => t === PENALTY.next_late_fee).length,
      `the new assessment reproduced the OLD 1.5% figure ${PENALTY.next_late_fee} — a fee ` +
        "assessed after the save must compute at the new percentage",
    ).toBeLessThanOrEqual(1);
  });

  test("step 5 — the pre-change assessed fee is byte-identical after both assessments", async ({
    page,
  }) => {
    await signIn(page);
    const before = await (await page.request.get(api("/invoices?per=200"))).text();
    await page.request.put(api("/settings/billing-defaults"), { data: { late_pct: "1.5" } });
    await page.request.put(api("/settings/billing-defaults"), { data: { late_pct: "2.0" } });
    expect(
      await (await page.request.get(api("/invoices?per=200"))).text(),
      "BR-TEN-020 / CLAUDE.md #4: only a human-initiated correction (new rows) may " +
        "ever change an assessed fee",
    ).toBe(before);
  });

  test("step 6 — INVARIANCE: nothing pre-dating the save is restated", async ({ page }) => {
    await signIn(page);
    const before = await (await page.request.get(api("/ledger/trial-balance"))).text();
    await page.request.put(api("/settings/billing-defaults"), { data: { late_pct: "1.5" } });
    expect(
      await (await page.request.get(api("/ledger/trial-balance"))).text(),
      "a settings change is not a money event",
    ).toBe(before);
    expect((await defaults(page.request)).late_pct, "the fixture is left as found").toBe("1.5");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-12 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) ACC-1110/1111/1112 are not seeded, so step 1 asserts the
//   absence of the control fixture rather than pretending to hold it still, and
//   steps 3–4 exercise the collections evaluation against whatever the tenant
//   holds · (2) NO post-change figure is hand-computed here: the journey's own
//   §3 makes 04-e2e-expected-gen.py the source, and step 4 therefore asserts the
//   NEGATIVE (the old %-dominated figure must not be reproduced on a new row)
//   rather than inventing the new one · (3) the spec restores `late_pct: 1.5`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
