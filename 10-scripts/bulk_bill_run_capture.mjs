#!/usr/bin/env node
/**
 * Screenshot every drawn state of the redrawn bulk bill run, named exactly as
 * the drawing's PNGs in `05-prototype/bulk-bill-run-2026-09-30/`
 * (`NN-<step>-<state>-<width>.png`), so the two sets pair one-to-one for the
 * `react-tailwind-css-ui-generator` skill's §4 side-by-side comparison.
 *
 * It drives the REAL page through `07-frontend/bulk-run-harness.html`, which
 * mounts `BulkRunPage` with the real stylesheets and an API answered from
 * `bulkRun/__fixtures__/bulkRunFixtures.ts`. Start the dev server first:
 *
 *     (cd 07-frontend && npx vite --port 5231 --strictPort --host 127.0.0.1)
 *     node 10-scripts/bulk_bill_run_capture.mjs
 *
 * States the build cannot reach are captured as the nearest real state and
 * say so in `08-qa/screens/bulk-bill-run-2026-09-30/README.md` (e.g. a row
 * fixed inline — the inline fixes are not served, DEF-BIL-8218).
 */
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5231/bulk-run-harness.html";
const OUT = process.env.OUT ?? new URL("../08-qa/screens/bulk-bill-run-2026-09-30/", import.meta.url).pathname;
const ONLY = process.env.ONLY ?? "";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const RUN = "33333333-3333-4333-8333-333333333333";
const CYCLE = "11111111-1111-4111-8111-111111111111";

async function scope(page) {
  await page.waitForSelector("#cycle_id option:nth-child(2)", { state: "attached" });
  await page.selectOption("#cycle_id", CYCLE);
  await page.fill("#label", "September 2026 · Riverside");
  await page.waitForTimeout(900);
}
async function scopeNoName(page) {
  await page.waitForSelector("#cycle_id option:nth-child(2)", { state: "attached" });
  await page.selectOption("#cycle_id", CYCLE);
  await page.waitForTimeout(900);
}
const tag = (id) => async (page) => {
  await page.waitForSelector("[data-check-results]");
  await page.click(`[data-tag="${id}"]`);
};
const tile = (id) => async (page) => {
  await page.waitForSelector("[data-check-results]");
  await page.click(`[data-kpi="${id}"]`);
};

const STATES = [
  ["01-scope-continuous", "?scope=continuous", scope],
  ["02-scope-gap", "?scope=gap", scope],
  ["03-scope-overlap", "?scope=overlap", async (p) => { await scope(p); await p.click('button[aria-label="Previous runs"]'); }],
  ["04-scope-warnings", "?scope=warnings", scope],
  ["05-scope-problems", "?scope=problems", scopeNoName],
  ["06-scope-panels-collapsed", "?scope=continuous", async (p) => {
    await scope(p);
    for (const name of ["Cycle details", "This run covers"]) await p.click(`button[aria-label="${name}"]`);
  }],
  ["07-scope-nobody-to-bill-panel", "?scope=continuous", async (p) => { await scope(p); await p.click("text=See units"); }],
  ["08-scope-missing-meter-panel", "?scope=continuous", async (p) => { await scope(p); await p.click("text=See services"); }],
  ["09-check-checking-progress", `?run=${RUN}&checking=1`, async (p) => { await p.waitForSelector('[data-run-progress="checking"]'); }],
  ["10-check-module-down", `?run=${RUN}&down=1`, async (p) => { await p.waitForSelector("[data-check-stop]"); }],
  ["11-check-decision-tag-no-reading", `?run=${RUN}`, tag("noReading")],
  ["12-check-decision-rows-selected", `?run=${RUN}`, async (p) => {
    await tag("noReading")(p);
    const boxes = p.locator('[data-tag-pane="noReading"] tbody input[type="checkbox"]');
    await boxes.nth(0).check();
    await boxes.nth(1).check();
  }],
  ["13-check-blocking-fixed-on-row", `?run=${RUN}`, tag("noUnit")],
  ["14-check-blocking-fixed-elsewhere", `?run=${RUN}`, tag("meterSwapped")],
  ["15-check-warning-tag", `?run=${RUN}`, tile("warnings")],
  ["16-check-payments-tag", `?run=${RUN}`, tag("lateFee")],
  ["17-check-filtered-blocked", `?run=${RUN}`, tile("blocked")],
  ["18-check-problem-search", `?run=${RUN}`, async (p) => { await p.waitForSelector("[data-check-results]"); await p.fill("#problem-search", "meter"); }],
  ["19-check-passed-checks-shown", `?run=${RUN}`, async (p) => {
    await p.waitForSelector("[data-check-results]");
    await p.check('[data-problem-list] input[type="checkbox"]');
  }],
  ["20-check-ready-to-bill", `?run=${RUN}`, tag("ready")],
  ["21-check-ready-left-out", `?run=${RUN}`, tile("ready")],
  ["22-check-fix-account-panel", `?run=${RUN}`, async (p) => { await tag("noReading")(p); await p.click("[data-open-account] >> nth=0"); }],
  ["23-check-fixed-rechecked-row", `?run=${RUN}`, async (p) => { await tag("noSize")(p); await p.click('[data-tag-pane="noSize"] [data-recheck]'); }],
  ["24-calculating-progress", `?run=${RUN}`, async (p) => {
    await p.waitForSelector("[data-check-results]");
    await p.click('[data-wizard="actions"] button:has-text("Price")');
    await p.waitForSelector('[data-run-progress="calculating"]');
  }],
  ["25-signoff-summary-all-open", `?run=${RUN}&phase=calculated`, async (p) => {
    await p.waitForSelector("[data-fix-in-check]");
    await p.click('button[aria-label="By customer type"]');
  }],
  ["26-signoff-who-is-billed", `?run=${RUN}&phase=calculated`, async (p) => { await p.waitForSelector("[data-fix-in-check]"); }],
  ["27-signoff-usage-and-charges", `?run=${RUN}&phase=calculated`, async (p) => { await p.waitForSelector("[data-fix-in-check]"); }],
  ["28-signoff-payments-and-balances", `?run=${RUN}&phase=calculated`, async (p) => { await p.waitForSelector("[data-fix-in-check]"); }],
  ["29-signoff-not-in-run-nobody-to-bill", `?run=${RUN}&phase=calculated`, async (p) => {
    await p.waitForSelector("[data-fix-in-check]");
    await p.click('[data-see="nobody"]');
  }],
  ["30-signoff-failed-to-draft-panel", `?run=${RUN}&phase=calculated`, async (p) => {
    await p.waitForSelector("[data-fix-in-check]");
    await p.click('[data-signoff-warnings] [data-see="breaks"]');
  }],
  ["31-signoff-confirmations-ticked", `?run=${RUN}&phase=calculated`, async (p) => {
    await p.waitForSelector("[data-fix-in-check]");
    for (const box of await p.locator("[data-confirmation]").all()) await box.check();
  }],
  ["32-send-not-ticked", `?run=${RUN}&phase=authorised`, async (p) => { await p.waitForSelector("[data-acknowledge]"); }],
  ["33-send-ticked", `?run=${RUN}&phase=authorised`, async (p) => { await p.waitForSelector("[data-acknowledge]"); await p.check("[data-acknowledge]"); }],
  ["34-send-sending", `?run=${RUN}&phase=authorised`, async (p) => {
    await p.waitForSelector("[data-acknowledge]");
    await p.check("[data-acknowledge]");
    await p.click('[data-wizard="actions"] button:has-text("Send")');
    await p.waitForTimeout(5);
  }],
  ["35-send-sent-not-in-run", `?run=${RUN}&phase=issued`, async (p) => { await p.waitForSelector('[data-not-in-run-row="blocked"]'); }],
  ["36-send-catch-up-started", `?run=${RUN}&phase=issued`, async (p) => {
    await p.waitForSelector('[data-not-in-run-row="blocked"]');
    await p.locator('[data-not-in-run="sent"] tbody input[type="checkbox"]').first().check();
    await p.click("[data-catch-up]");
    await p.waitForSelector("[data-catch-up-started]");
  }],
];

const browser = await chromium.launch({ executablePath: resolveChromium() });
for (const width of [1440, 1280]) {
  for (const [name, query, act] of STATES) {
    if (ONLY !== "" && !name.startsWith(ONLY)) continue;
    const page = await browser.newPage({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
    await page.goto(`${BASE}${query}`);
    try {
      await act(page);
    } catch (error) {
      console.log(`!  ${name} @${width}: ${String(error).split("\n")[0]}`);
    }
    await page.waitForTimeout(name.startsWith("34") ? 0 : 500);
    // Side panels are `position: fixed`; a full-page capture keeps them over
    // the viewport. Nothing focused, scrolled to the top.
    await page.evaluate(() => {
      if (document.activeElement instanceof HTMLElement && !document.querySelector("[role=dialog]")) document.activeElement.blur();
      window.scrollTo(0, 0);
    });
    const file = `${name}-${width}.png`;
    await page.screenshot({ path: join(OUT, file), fullPage: true });
    console.log(`·  ${file}`);
    await page.close();
  }
}
await browser.close();
