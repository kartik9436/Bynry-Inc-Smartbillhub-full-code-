// ── Trace ──────────────────────────────────────────────
// Journey:  J72 — the bulk bill run, redesigned · E11 (the drawing diff) ·
//           08-qa/01-e2e/journeys/J72-bulk-bill-run-redesign.md § E11
// Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md E11, D1
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/ (36 states × 1440, 1280)
// Criteria: 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md U2
// Seed:     `manage.py seed_demo` → `manage.py seed_j72_bulk_run`, PostgreSQL 16
// ───────────────────────────────────────────────────────
//
// E11 — CAPTURE EVERY DRAWN STATE, NAMED EXACTLY AS ITS D1 IMAGE, SO THE DIFF
// IS FILE FOR FILE. This spec does not judge the screens: a person puts each
// capture beside its drawing and records the verdict in J72 § E11. What it
// asserts is only that it REACHED each state, and it writes `reached.json`
// beside the captures naming every state it could not reach and why — a
// capture run that silently drops a state is law 7's "zero over a scope it
// excludes".
//
// ONE TEST PER WIDTH, IN THE CLERK'S ORDER, on ONE September run. Reset the
// database to the seeded snapshot before each width.
//
//   E2E_VIEWPORT=1440 E2E_BASE_URL=http://127.0.0.1:<web> \
//   E11_DATABASE_URL=postgres://…/<walk db> \
//     npx playwright test e2e/J72-bulk-bill-run-e11-capture.spec.ts --workers=1
//
// THREE STATES ARE SHOWN BY HOLDING A REAL RESPONSE, never by inventing data:
// Checking (09), Calculating (24) and Sending (34). With JOBS_EAGER the jobs
// finish inside the request, so no `n of N` is ever on screen long enough to
// see. The capture lets the REAL request run to completion and then answers
// the browser as the background path does (`202 {background, job_id}`), with
// a job record reading a fixed `n of N` until the shot is taken — the screen
// is the product's, only the clock is held. Module down (10) takes Meter
// Reads down for real through `10-scripts/j73_bulk_run_harness.py`
// (`DEF-BIL-8510` — the product has no switch), when E11_DATABASE_URL names
// the walk database; without it, 10 is recorded as not reached.
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

import { expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";
import { APP_SERVER_TAG } from "./support/census";

const WIDTH = Number(process.env.E2E_VIEWPORT ?? "1440");
const SHOTS = process.env.E11_SHOTS ?? "../08-qa/screens/bulk-bill-run-e11-2026-10-01";
const CYCLE = /J72-RIVERSIDE/;

interface Scope {
  name?: string;
  start: string;
  end: string;
  bill?: string;
  days?: string;
  template?: number | false;
}
const SEPTEMBER: Scope = {
  name: "September 2026 · Riverside",
  start: "2026-09-01",
  end: "2026-09-30",
  bill: "2026-10-01",
  days: "21",
};

const reached: Record<string, string> = {};

async function shot(page: Page, state: string): Promise<void> {
  await page.mouse.move(0, 0);
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  await page.waitForTimeout(400);
  await expandInnerScroller(page);
  await page.screenshot({ path: `${SHOTS}/${state}-${WIDTH}.png`, fullPage: true });
  reached[state] = "captured";
  writeFileSync(`${SHOTS}/reached-${WIDTH}.json`, `${JSON.stringify(reached, null, 2)}\n`);
}

/** Run one state; a state that cannot be reached is RECORDED, never dropped. */
async function state(name: string, body: () => Promise<void>): Promise<void> {
  try {
    await body();
    if (reached[name] === undefined) reached[name] = "captured";
  } catch (error) {
    reached[name] = `NOT REACHED: ${String(error).split("\n")[0].slice(0, 240)}`;
  }
  writeFileSync(`${SHOTS}/reached-${WIDTH}.json`, `${JSON.stringify(reached, null, 2)}\n`);
}

function notReachable(name: string, why: string) {
  reached[name] = `NOT REACHABLE ON THIS SEED: ${why}`;
}

async function openRun(page: Page, query = ""): Promise<void> {
  await page.goto(`/${tenant()}/billing/run${query}`);
  await expect(page.locator("[data-screen=bulk-bill-run]")).toBeVisible({ timeout: 30_000 });
}

async function fillScope(page: Page, s: Scope): Promise<void> {
  await page.locator("#label").fill(s.name ?? "");
  const cycle = page.locator("#cycle_id");
  const option = cycle.locator("option").filter({ hasText: CYCLE });
  await expect(option).toHaveCount(1, { timeout: 20_000 });
  await cycle.selectOption({ value: (await option.getAttribute("value")) ?? "" });
  await page.locator("#period_start").fill(s.start);
  await page.locator("#period_end").fill(s.end);
  if (s.bill !== undefined) await page.locator("#bill_date").fill(s.bill);
  if (s.days !== undefined) await page.locator("#due_days").fill(s.days);
  if (s.template !== false) {
    const template = page.locator("#template_id");
    await expect(template.locator("option").nth(1)).toBeAttached({ timeout: 20_000 });
    const index = s.template ?? 1;
    const options = await template.locator("option").count();
    await template.selectOption({ index: Math.min(index, options - 1) });
  }
  await page.waitForTimeout(1800);
}

async function onStep(page: Page, label: string, timeout = 60_000): Promise<void> {
  await expect(page.locator("[data-wizard=rail] [aria-current=step]")).toContainText(label, { timeout });
}

async function setOpen(page: Page, panel: string, open: boolean): Promise<void> {
  const button = page.locator(`[data-otb-panel=${panel}] button[aria-expanded]`).first();
  if ((await button.count()) === 0) return;
  if ((await button.getAttribute("aria-expanded")) !== String(open)) await button.click();
}

async function openTag(page: Page, tag: string): Promise<void> {
  const row = page.locator(`[data-tag=${tag}]`).first();
  await expect(row).toBeVisible({ timeout: 30_000 });
  await row.click();
  if (tag !== "ready") await expect(page.locator(`[data-tag-pane=${tag}]`)).toBeVisible({ timeout: 15_000 });
}

function harness(direction: "down" | "up"): void {
  const db = process.env.E11_DATABASE_URL;
  if (!db) throw new Error("E11_DATABASE_URL not set — Meter Reads cannot be taken down");
  const out = spawnSync(
    process.env.E11_PYTHON ?? "python3",
    ["../10-scripts/j73_bulk_run_harness.py", "meter-reads", direction],
    {
      cwd: resolve("../06-backend"),
      env: { ...process.env, DATABASE_URL: db, DJANGO_SETTINGS_MODULE: "config.settings.local", JOBS_EAGER: "false" },
      encoding: "utf8",
    },
  );
  if (out.status !== 0) throw new Error(`harness meter-reads ${direction} failed: ${out.stderr.slice(-300)}`);
}

/** Let the real request finish, then answer as the background path does, and
 *  serve a held `n of N` for the fake job until `release()` is called. */
async function holdAsJob(
  page: Page,
  post: RegExp,
  jobId: string,
  progress: { done: number; total: number },
): Promise<() => Promise<void>> {
  let done = false;
  await page.route(post, async (route: Route) => {
    try {
      if (route.request().method() !== "POST" || done) return await route.continue();
      const real = await route.fetch();
      if (!real.ok()) return await route.fulfill({ response: real });
      return await route.fulfill({ status: 202, json: { background: true, job_id: jobId } });
    } catch {
      // released while in flight
    }
  });
  const jobUrl = new RegExp(`/jobs/${jobId}(\\?|$)`);
  await page.route(jobUrl, (route) =>
    route.fulfill({
      json: {
        id: jobId,
        kind: "e11",
        status: done ? "succeeded" : "running",
        progress: done ? { done: progress.total, total: progress.total } : progress,
        error: null,
      },
    }),
  );
  return async () => {
    done = true;
    await page.waitForTimeout(3000);
  };
}

test.describe(`J72 E11 — every drawn state at ${WIDTH}`, { tag: APP_SERVER_TAG }, () => {
  skipUnlessAppServer(test);
  test.setTimeout(Number(process.env.E2E_TEST_TIMEOUT ?? "2400000"));

  test(`capture the 36 D1 states at ${WIDTH}`, async ({ page }) => {
    mkdirSync(SHOTS, { recursive: true });
    await page.setViewportSize({ width: WIDTH, height: 1000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await signIn(page);

    // ── Scope (no run yet) ────────────────────────────────────────────────
    await state("05-scope-problems", async () => {
      await openRun(page);
      await fillScope(page, { name: "", start: "2026-09-01", end: "2026-08-20", bill: "", days: "-3", template: false });
      await expect(page.locator("[data-run-problems=refusal]")).toBeVisible({ timeout: 20_000 });
      await shot(page, "05-scope-problems");
    });
    await state("02-scope-gap", async () => {
      await openRun(page);
      await fillScope(page, { ...SEPTEMBER, start: "2026-10-10", end: "2026-11-09", bill: "2026-11-10" });
      await expect(page.locator("[data-continuity=gap]")).toBeVisible({ timeout: 20_000 });
      await shot(page, "02-scope-gap");
    });
    await state("04-scope-warnings", async () => {
      await openRun(page);
      // The drawing's warnings: 45 days, not the bill day, days changed, another template.
      await fillScope(page, { ...SEPTEMBER, end: "2026-10-15", bill: "2026-10-20", days: "30", template: 2 });
      await expect(page.locator("[data-run-problems=warning]")).toBeVisible({ timeout: 20_000 });
      await shot(page, "04-scope-warnings");
    });
    await state("01-scope-continuous", async () => {
      await openRun(page);
      await fillScope(page, SEPTEMBER);
      await expect(page.locator("[data-continuity=continuous]")).toBeVisible({ timeout: 20_000 });
      await shot(page, "01-scope-continuous");
    });
    await state("06-scope-panels-collapsed", async () => {
      for (const panel of ["cycle-details", "run-covers", "previous-runs"]) await setOpen(page, panel, false);
      await shot(page, "06-scope-panels-collapsed");
      for (const panel of ["cycle-details", "run-covers"]) await setOpen(page, panel, true);
    });
    await state("07-scope-nobody-to-bill-panel", async () => {
      await page.locator("[data-run-problems=warning]").getByRole("button", { name: "See units" }).click();
      await expect(page.locator("[data-run-panel=nobody]")).toBeVisible();
      await shot(page, "07-scope-nobody-to-bill-panel");
      await page.locator("[data-run-panel=nobody] [data-run-panel-close]").click();
    });
    await state("08-scope-missing-meter-panel", async () => {
      // The seed fits a meter to every service: no Missing meter warning, so
      // no See services link to press. Reached only where the world has one.
      const link = page.locator("[data-run-problems=warning]").getByRole("button", { name: "See services" });
      if ((await link.count()) === 0) {
        notReachable("08-scope-missing-meter-panel", "every seeded service has a meter (Missing meter 0), so no See services link");
        return;
      }
      await link.click();
      await shot(page, "08-scope-missing-meter-panel");
      // Close it, or the open panel sits over Start checking.
      await page.locator("[data-run-panel] [data-run-panel-close]").first().click();
    });

    // ── Start → Check, with the Check job held at n of N (09) ────────────
    const checkGet = /\/billing\/runs\/[^/]+\/check(\?|$)/;
    let holdCheck = true;
    await page.route(checkGet, async (route) => {
      try {
        if (route.request().method() !== "GET" || !holdCheck) return await route.continue();
        const real = await route.fetch();
        const body = await real.json();
        body.job = { id: "e11-check", status: "running", progress: { done: 7, total: 11 }, error: null };
        return await route.fulfill({ response: real, json: body });
      } catch {
        // the route was released while this request was in flight
      }
    });
    await state("09-check-checking-progress", async () => {
      await page.getByRole("button", { name: "Start checking", exact: true }).click();
      await onStep(page, "Check", 90_000);
      await expect(page.locator("[data-run-progress=checking]")).toBeVisible({ timeout: 60_000 });
      await shot(page, "09-check-checking-progress");
    });
    holdCheck = false;
    await page.waitForTimeout(3000);
    await page.reload();
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
    const runUrl = page.url();

    await state("11-check-decision-tag-no-reading", async () => {
      await openTag(page, "missing_read");
      await shot(page, "11-check-decision-tag-no-reading");
    });
    await state("12-check-decision-rows-selected", async () => {
      await openTag(page, "billing_continuity");
      const pane = page.locator("[data-tag-pane=billing_continuity]");
      await pane.getByRole("checkbox", { name: "Select AC-2026-00009" }).check();
      await pane.getByRole("checkbox", { name: "Select AC-2026-00010" }).check();
      await shot(page, "12-check-decision-rows-selected");
      await pane.getByRole("checkbox", { name: "Select AC-2026-00009" }).uncheck();
      await pane.getByRole("checkbox", { name: "Select AC-2026-00010" }).uncheck();
    });
    await state("15-check-warning-tag", async () => {
      await page.getByRole("button", { name: /^Warnings \d+$/ }).click();
      const first = page.locator("[data-problem-list] [data-tag]:not([data-tag=ready])").first();
      await expect(first).toBeVisible({ timeout: 10_000 });
      await first.click();
      await shot(page, "15-check-warning-tag");
      await page.getByRole("button", { name: /^Problem types \d+$/ }).click();
    });
    await state("16-check-payments-tag", async () => {
      await openTag(page, "paid_after_cutoff");
      await shot(page, "16-check-payments-tag");
    });
    await state("17-check-filtered-blocked", async () => {
      await page.getByRole("button", { name: /^Blocked accounts \d+$/ }).click();
      await shot(page, "17-check-filtered-blocked");
      await page.getByRole("button", { name: /^Problem types \d+$/ }).click();
    });
    await state("18-check-problem-search", async () => {
      await page.locator("#problem-search").fill("meter");
      await page.waitForTimeout(500);
      await shot(page, "18-check-problem-search");
      await page.locator("#problem-search").fill("");
    });
    await state("19-check-passed-checks-shown", async () => {
      const box = page.locator("[data-problem-list] input[type=checkbox]").first();
      await box.check();
      await shot(page, "19-check-passed-checks-shown");
      await box.uncheck();
    });
    await state("20-check-ready-to-bill", async () => {
      await openTag(page, "ready");
      await expect(page.locator("[data-run-table=ready]")).toBeVisible({ timeout: 20_000 });
      await shot(page, "20-check-ready-to-bill");
    });
    await state("21-check-ready-left-out", async () => {
      const leave = page.locator("[data-leave-out]").first();
      await leave.click();
      await page.waitForTimeout(2500);
      await shot(page, "21-check-ready-left-out");
      // Put it back so the run prices what J72 prices.
      await page.locator("[data-leave-out]").first().click();
      await page.waitForTimeout(2500);
    });
    await state("22-check-fix-account-panel", async () => {
      await openTag(page, "unit_has_no_plan");
      await page.locator("[data-tag-pane=unit_has_no_plan] [data-row-account='AC-2026-00005'] [data-open-account]").first().click();
      await expect(page.locator("[data-run-panel]")).toBeVisible({ timeout: 15_000 });
      await shot(page, "22-check-fix-account-panel");
      await page.locator("[data-run-panel] [data-run-panel-close]").first().click();
    });
    await state("13-check-blocking-fixed-on-row", async () => {
      await openTag(page, "unit_has_no_plan");
      const row = page.locator("[data-tag-pane=unit_has_no_plan] [data-row-account='AC-2026-00004']");
      const fix = row.locator("[data-fix-here=set_plan] select");
      await expect(fix.locator("option").nth(1)).toBeAttached({ timeout: 20_000 });
      await fix.selectOption({ index: 1 });
      await row.locator("[data-fix-save]").click();
      await page.waitForTimeout(2500);
      await shot(page, "13-check-blocking-fixed-on-row");
    });
    await state("23-check-fixed-rechecked-row", async () => {
      await page.waitForTimeout(3000);
      await shot(page, "23-check-fixed-rechecked-row");
    });
    await state("14-check-blocking-fixed-elsewhere", async () => {
      // `seed_j72_bulk_run --e11-states` (DEF-BIL-8689) plants unit 115's
      // reading and meter with no unit: blocked, fixed in Meter Reads.
      await page.getByRole("button", { name: /^Blocked accounts \d+$/ }).click();
      const first = page.locator("[data-problem-list] [data-tag]:not([data-tag=ready])").first();
      if ((await first.count()) === 0) {
        notReachable("14-check-blocking-fixed-elsewhere", "the served Check blocks nothing on this world (seed without --e11-states)");
        await page.getByRole("button", { name: /^Problem types \d+$/ }).click();
        return;
      }
      await first.click();
      await shot(page, "14-check-blocking-fixed-elsewhere");
      await page.getByRole("button", { name: /^Problem types \d+$/ }).click();
    });
    await state("10-check-module-down", async () => {
      harness("down");
      try {
        await page.locator("[data-check-again]").click();
        await page.waitForTimeout(4000);
        await shot(page, "10-check-module-down");
      } finally {
        harness("up");
      }
      // Back up: the stop stays on screen until the clerk presses Try again.
      await page.goto(runUrl);
      await page.waitForTimeout(2000);
      const retry = page.getByRole("region", { name: "Check" }).getByRole("button", { name: "Try again" });
      if ((await retry.count()) > 0) await retry.click();
      else await page.locator("[data-check-again]").click({ timeout: 60_000 });
      await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
    });

    // ── The one lawful answer, then Price → Calculating (24) ──────────────
    await page.goto(runUrl);
    await expect(page.locator("[data-check-results]")).toBeVisible({ timeout: 120_000 });
    await openTag(page, "billing_continuity");
    await page.getByRole("combobox", { name: "Decide for AC-2026-00010" }).selectOption({ label: "Look into it" });
    await page.waitForTimeout(2500);
    await state("24-calculating-progress", async () => {
      const release = await holdAsJob(page, /\/billing\/runs\/[^/]+\/calculate(\?|$)/, "e11-calc", { done: 5, total: 9 });
      await page.getByRole("button", { name: /^Price \d+ accounts?$/ }).click();
      await expect(page.locator("[data-run-progress=calculating]")).toBeVisible({ timeout: 120_000 });
      await shot(page, "24-calculating-progress");
      await release();
    });
    await onStep(page, "Sign off", 180_000);
    await expect(page.locator("[data-run-table=who-accounts]")).toBeVisible({ timeout: 60_000 });

    // ── Sign off (25–31) ──────────────────────────────────────────────────
    const sections = ["who-is-billed", "usage-and-charges", "payments-balances", "by-customer-type", "not-in-run"];
    await state("25-signoff-summary-all-open", async () => {
      for (const s of sections) await setOpen(page, s, true);
      await shot(page, "25-signoff-summary-all-open");
    });
    for (const [name, open] of [
      ["26-signoff-who-is-billed", "who-is-billed"],
      ["27-signoff-usage-and-charges", "usage-and-charges"],
      ["28-signoff-payments-and-balances", "payments-balances"],
    ] as const) {
      await state(name, async () => {
        for (const s of sections) await setOpen(page, s, s === open);
        await shot(page, name);
      });
    }
    await state("29-signoff-not-in-run-nobody-to-bill", async () => {
      for (const s of sections) await setOpen(page, s, s === "not-in-run");
      await page.locator("[data-otb-panel=not-in-run]").getByText(/^Nobody to bill/).first().click();
      await page.waitForTimeout(1500);
      await shot(page, "29-signoff-not-in-run-nobody-to-bill");
      await page.locator("[data-otb-panel=not-in-run]").getByText(/^All/).first().click();
    });
    await state("30-signoff-failed-to-draft-panel", async () => {
      const breaks = page.locator("[data-see=breaks]");
      if ((await breaks.count()) === 0) {
        notReachable("30-signoff-failed-to-draft-panel", "every J72 account drafts; no bill failed to draft, so no See breaks");
        return;
      }
      await breaks.first().click();
      await shot(page, "30-signoff-failed-to-draft-panel");
      await page.locator("[data-run-panel] [data-run-panel-close]").first().click();
    });
    await state("31-signoff-confirmations-ticked", async () => {
      for (const s of sections) await setOpen(page, s, s === "who-is-billed" || s === "not-in-run");
      const confirmations = page.getByRole("group", { name: "Sign off" });
      for (const box of await confirmations.getByRole("checkbox").all()) await box.check();
      await shot(page, "31-signoff-confirmations-ticked");
    });
    await page.locator("[data-wizard=actions]").getByRole("button", { name: "Sign off", exact: true }).click();
    await onStep(page, "Send", 60_000);

    // ── Send (32–36) ──────────────────────────────────────────────────────
    await state("32-send-not-ticked", async () => {
      await expect(page.locator("[data-send-card]")).toBeVisible({ timeout: 30_000 });
      await shot(page, "32-send-not-ticked");
    });
    await state("33-send-ticked", async () => {
      await page.getByRole("region", { name: "Send" }).getByRole("checkbox", { name: "I checked the totals" }).check();
      await shot(page, "33-send-ticked");
    });
    await state("34-send-sending", async () => {
      const release = await holdAsJob(page, /\/billing\/runs\/[^/]+\/issue(\?|$)/, "e11-send", { done: 3, total: 6 });
      await page.locator("[data-wizard=actions]").getByRole("button", { name: /^Send \d+ bills?$/ }).click();
      await expect(page.locator("[data-run-progress=sending]")).toBeVisible({ timeout: 120_000 });
      await shot(page, "34-send-sending");
      await release();
    });
    await state("35-send-sent-not-in-run", async () => {
      await expect(page.locator("[data-sent-card]")).toBeVisible({ timeout: 120_000 });
      await shot(page, "35-send-sent-not-in-run");
    });
    await state("36-send-catch-up-started", async () => {
      const row = page.locator("[data-not-in-run-row]").filter({ has: page.locator("input[type=checkbox]") }).first();
      await row.locator("input[type=checkbox]").check();
      await page.locator("[data-catch-up]").click();
      await expect(page.locator("[data-catch-up-started]")).toBeVisible({ timeout: 60_000 });
      await shot(page, "36-send-catch-up-started");
    });

    // ── Back to Scope: the overlap, with Previous runs opened (03) ────────
    await state("03-scope-overlap", async () => {
      await openRun(page);
      await fillScope(page, { ...SEPTEMBER, start: "2026-09-15", end: "2026-10-14", bill: "2026-10-15" });
      await expect(page.locator("[data-continuity=overlap]")).toBeVisible({ timeout: 20_000 });
      await setOpen(page, "previous-runs", true);
      await page.waitForTimeout(1500);
      await shot(page, "03-scope-overlap");
    });

    writeFileSync(`${SHOTS}/reached-${WIDTH}.json`, `${JSON.stringify(reached, null, 2)}\n`);
    const missing = Object.entries(reached).filter(([, v]) => v.startsWith("NOT REACHED"));
    test.info().annotations.push({
      type: "reached",
      description: `${Object.values(reached).filter((v) => v === "captured").length} of 36 captured`,
    });
    expect(Object.keys(reached), "every drawn state is accounted for").toHaveLength(36);
    expect(missing, "a reachable state the capture failed to reach").toEqual([]);
  });
});
