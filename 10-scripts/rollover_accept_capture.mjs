#!/usr/bin/env node
/**
 * DEF-BIL-9077 — the one-time bill's ACCEPT-ROLLOVER control, walked in a real
 * browser and photographed at both staff widths (1440 and 1280).
 *
 * It drives the REAL page through `07-frontend/otb-harness.html?rollover=1`,
 * whose preview answers the server's own `possible_rollover` 422 (meter
 * E-55120, dials 99,800 → 240 → 700, 900 kWh) until the request carries
 * `accepted_rollovers: ["electric"]`, and then prices. The backend half — the
 * hold, its facts and the $90.00 across the rollover — is proved on PostgreSQL
 * in `06-backend/tests/test_def_bil_9075_9076_chain_lock_and_rollover.py`.
 *
 *     (cd 07-frontend && npx vite --port 5199 --strictPort --host 127.0.0.1)
 *     node 10-scripts/rollover_accept_capture.mjs
 *
 * It FAILS (exit 1) when the panel does not show its facts, when Accept does
 * not clear it, or when the page scrolls sideways — a walk that cannot fail
 * is not a check.
 */
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5199/otb-harness.html";
const OUT = process.env.OUT ?? new URL("../08-qa/screens/rollover-accept-2026-10-02/", import.meta.url).pathname;
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

const failures = [];
function check(ok, what) {
  console.log(`${ok ? "PASS" : "FAIL"}  ${what}`);
  if (!ok) failures.push(what);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
for (const width of [1440, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.goto(`${BASE}?kind=interim&rollover=1`);
  await page.locator('[id="account_id"]').fill("Alv");
  await page.locator('[id="account_id-listbox"] [role="option"]').first().click();
  await page.locator('[id="period_start"]').fill("2026-10-15");
  await page.locator('[id="period_end"]').fill("2026-11-13");
  const panel = page.getByRole("region", { name: "Meter rolled over" });
  await panel.waitFor({ timeout: 5000 });
  const text = await panel.innerText();
  check(text.includes("E-55120"), `${width}: the meter is named by its number`);
  check(text.includes("99,800 → 240 → 700"), `${width}: the three dials`);
  check(text.includes("900 kWh"), `${width}: the usage they imply`);
  const sideways = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  check(!sideways, `${width}: no sideways scroll`);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: join(OUT, `${width}-1-held.png`), fullPage: true });
  await panel.getByRole("button", { name: /Accept rollover/ }).click();
  await panel.waitFor({ state: "detached", timeout: 5000 }).catch(() => undefined);
  check((await page.getByRole("region", { name: "Meter rolled over" }).count()) === 0, `${width}: Accept clears the hold`);
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, `${width}-2-accepted.png`), fullPage: true });
  await page.close();
}
await browser.close();
if (failures.length > 0) {
  console.log(`\n${failures.length} check(s) failed`);
  process.exit(1);
}
console.log("\nall checks passed");
