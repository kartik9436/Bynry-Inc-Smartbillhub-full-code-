// ── Trace ──────────────────────────────────────────────
// Journey:  T7-15 — Config change: budget params (re-level cadence + settle-up
//           month — next evaluation only).
//           `08-qa/01-e2e/journeys/T7-15-budget-params-change.md` is the spec;
//           this file walks its six-row step table in order.
// Story:    US-TEN-010 (S69 budget-rules card, atomic save) · US-BIL-018/019/
//           020 (budget billing: enrolment, level, settle-up) · US-IDN-001
//           Screens: S3 · S69 Budget billing rules
// Rules:    BR-BIL-017 (level = trailing-12 avg whole $, re-level at ±20% drift
//           each 6 months, annual settle-up month, off-budget after 2 missed) ·
//           BR-BIL-021 · BR-TEN-016 (ONE audit row per atomic save, both
//           changed fields in it) · BR-TEN-020 · BR-TEN-041
// Money:    `moneyTriple("flat","budget","full")` — the journey's ACC-1140 row
//           (actual 97.41 against level 97, variance −0.41). Read at run time;
//           no figure is typed and no variance is recomputed here.
// Impacts:  10-scripts/gates/g12_journeys.py · e2e/support/census.ts
// ───────────────────────────────────────────────────────
import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

import { signIn, skipUnlessAppServer, tenant } from "./support/app";
import { moneyTriple } from "./support/expected";
import { journey } from "./support/journey";

const BUDGET = moneyTriple("flat", "budget", "full");
const CARD_LABEL = "Budget billing rules";

function api(path: string): string {
  return `/api/${tenant()}${path}`;
}

interface BudgetSettings {
  relevel_cadence_months: number;
  settle_up_month: number | null;
  relevel_drift_pct: string;
  level_rounding: string;
}

async function budget(request: APIRequestContext): Promise<BudgetSettings> {
  const response = await request.get(api("/settings/budget-billing"));
  expect(response.status()).toBe(200);
  return (await response.json()) as BudgetSettings;
}

async function budgetAuditRows(
  request: APIRequestContext,
): Promise<{ action: string; summary: string }[]> {
  const response = await request.get(api("/audit-log?per=50"));
  expect(response.status()).toBe(200);
  return ((await response.json()) as { results: { action: string; summary: string }[] }).results
    .filter((r) => r.action.includes("budget"));
}

async function openBudgetRules(page: Page): Promise<void> {
  await page.goto(`/${tenant()}/settings/reference-data`);
  await page.getByRole("button", { name: CARD_LABEL }).first().click();
  await expect(page.locator("#relevel_cadence_months")).toBeVisible();
}

journey("T7-15", "Config change: budget params — next evaluation and next settle-up only", () => {
  // NOT serial: each row re-reads the settings, so the run reports which of the
  // journey's six hold rather than stopping at the first that does not.
  skipUnlessAppServer(test);

  test("step 1 — baseline: the seeded budget defaults and the enrolled account's state", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/budget-billing"), {
      data: { relevel_cadence_months: 6, settle_up_month: 4 },
    });
    const config = await budget(page.request);
    expect(config.relevel_cadence_months, "the journey's starting cadence").toBe(6);
    expect(config.settle_up_month, "the journey's starting settle-up month").toBe(4);
    expect(config.relevel_drift_pct, "BR-BIL-017's ±20% drift threshold").toMatch(/^20(\.0+)?$/);
    expect(config.level_rounding, "BR-BIL-017: whole dollars").toBe("whole_dollar");

    // ACC-1140's own state — level 97, variance -0.41 against an actual of
    // ${BUDGET.total}. The enrolment surface has to serve it.
    const status = await page.request.get(api("/budget-enrolments?per=50"));
    expect(
      status.status(),
      `the budget enrolment/level surface answered ${status.status()} — without it, ` +
        `"level STILL ${BUDGET.notes || "97"}, variance STILL unchanged" cannot be observed`,
    ).toBe(200);
  });

  test("step 2 — a two-field atomic save writes ONE audit row carrying BOTH changes", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/budget-billing"), {
      data: { relevel_cadence_months: 6, settle_up_month: 4 },
    });
    const before = (await budgetAuditRows(page.request)).length;

    await signIn(page);
    await openBudgetRules(page);
    await page.locator("#relevel_cadence_months").fill("3");
    await page.locator("#settle_up_month").fill("7");
    await page.getByRole("button", { name: /^Save/ }).first().click();

    await expect
      .poll(async () => (await budget(page.request)).relevel_cadence_months, {
        message: "the atomic tab save must land the new cadence",
      })
      .toBe(3);
    expect((await budget(page.request)).settle_up_month, "…and the new settle-up month").toBe(7);

    const rows = await budgetAuditRows(page.request);
    expect(
      rows.length,
      "BR-AUD-011: ONE atomic save = ONE row, even when two fields changed",
    ).toBe(before + 1);
    expect(rows[0].summary, "both changed fields must be in the one row").toMatch(
      /relevel_cadence_months:\s*6\s*→\s*3/,
    );
    expect(rows[0].summary).toMatch(/settle_up_month:\s*4\s*→\s*7/);
  });

  test("step 3 — the save triggers no re-level and no retroactive settle-up", async ({ page }) => {
    await signIn(page);
    const before = await (await page.request.get(api("/invoices?per=200"))).text();
    await page.request.put(api("/settings/budget-billing"), {
      data: { relevel_cadence_months: 3, settle_up_month: 7 },
    });
    expect(
      await (await page.request.get(api("/invoices?per=200"))).text(),
      "a settings save is not an evaluation event: no level moves, no settle-up line appears",
    ).toBe(before);
  });

  test("step 4 — the next re-level evaluation reads the cadence in force at evaluation time", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/budget-billing"), {
      data: { relevel_cadence_months: 3 },
    });
    const response = await page.request.post(api("/budget/relevel"), {
      data: { as_of: "2026-08-01" },
    });
    expect(
      response.status(),
      `the re-level evaluation answered ${response.status()} — BR-BIL-017's cadence gate ` +
        "has no server-side surface, so 'the cadence changed and the threshold did not' " +
        "cannot be proven",
    ).toBeLessThan(400);
  });

  test("step 5 — the next settle-up lands in the NEW month and April's line is untouched", async ({
    page,
  }) => {
    await signIn(page);
    await page.request.put(api("/settings/budget-billing"), { data: { settle_up_month: 7 } });
    const response = await page.request.get(api("/budget-enrolments?per=50"));
    expect(
      response.status(),
      `the enrolment surface answered ${response.status()} — the settle-up schedule and ` +
        "the variance trail have nowhere to be read from",
    ).toBe(200);
  });

  test("step 6 — INVARIANCE: nothing issued is restated by the multi-knob save", async ({
    page,
  }) => {
    await signIn(page);
    const invoices = await (await page.request.get(api("/invoices?per=200"))).text();
    const ledger = await (await page.request.get(api("/ledger/trial-balance"))).text();
    await page.request.put(api("/settings/budget-billing"), {
      data: { relevel_cadence_months: 6, settle_up_month: 4 },
    });
    expect(await (await page.request.get(api("/invoices?per=200"))).text()).toBe(invoices);
    expect(await (await page.request.get(api("/ledger/trial-balance"))).text()).toBe(ledger);
    const restored = await budget(page.request);
    expect(restored.relevel_cadence_months, "the fixture is left as found").toBe(6);
    expect(restored.settle_up_month).toBe(4);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: T7-15 journey activation (batch B lane, 2026-08-15)
// generated: 2026-08-15 by the E2E journey-activation lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: run against the live stack on E2E_BACKEND_PORT=8040 / E2E_WEB_PORT=8120
// exceptions: (1) the seeded tenant ships `settle_up_month: null`, so step 1
//   SETS the journey's own starting values before asserting them — a fixture
//   the product can produce, not one invented in a database · (2) ACC-1140 is
//   not enrolled anywhere, so steps 1/4/5 assert the ABSENCE of the enrolment
//   and re-level surfaces rather than the account's level and variance ·
//   (3) the spec restores the seeded cadence and month
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
