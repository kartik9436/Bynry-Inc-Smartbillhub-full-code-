#!/usr/bin/env node
// CR-171-BRC10 lane MVI-DETAIL — photograph the move-in details view at 1440,
// one shot per (reference, tab, opened control), for the side-by-side with
// `05-prototype/movein-redesign-2026-10-05/images/03–29`.
//
// Usage:
//   MDW_BASE=http://127.0.0.1:5722 MDW_OUT=08-qa/movein-2026-10-05/after/detail \
//   node 10-scripts/cr171_move_in_detail_walkthrough.mjs 'SR-26-0001' 'MVI-26-0002:billing' 'SR-26-0001:overview:more'
//
// Each argument is `REF[:TAB[:OPEN]]`; OPEN is `more` (the More ▾ menu) or an
// action id (`approve`, `decline`, `askForMore`, `cancel`, …) whose control is
// pressed — from the head, or from the open More menu. The PNG is named
// `<ref>[-<tab>][-<open>].png`. Each page also asserts it is not blank: the
// title and the status chip must be on it.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.MDW_BASE || "http://127.0.0.1:5722";
const T = process.env.MDW_TENANT || "brazosbend";
const OUT = process.env.MDW_OUT || "08-qa/movein-2026-10-05/after/detail";
const EMAIL = process.env.MDW_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MDW_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MDW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);

let failed = 0;
for (const arg of process.argv.slice(2)) {
  const [ref, tab = "", open = ""] = arg.split(":");
  const query = tab && tab !== "overview" ? `?tab=${tab}` : "";
  await page.goto(`${BASE}/${T}/moves/${encodeURIComponent(ref)}${query}`, { waitUntil: "domcontentloaded" });
  try {
    await page.waitForSelector('[data-screen="move-in-detail"] [data-move-status]', { timeout: 20000 });
    await page.waitForLoadState("networkidle");
    if (open === "more") {
      await page.click('[data-move-more] summary');
    } else if (open) {
      const head = page.locator(`[data-testid="move-action-${open}"]`);
      if (await head.count()) {
        await head.first().click();
      } else {
        await page.click('[data-move-more] summary');
        await page.click(`[data-testid="move-more-${open}"]`);
      }
      await page.waitForSelector('[role="dialog"], [role="alertdialog"]', { timeout: 10000 });
      await page.waitForLoadState("networkidle");
    }
    await page.waitForTimeout(300);
    const status = await page.locator("[data-move-status]").first().innerText();
    const title = await page.locator("h1").first().innerText();
    const name = [ref, tab, open].filter(Boolean).join("-") + ".png";
    await page.screenshot({ path: join(OUT, name), fullPage: true });
    console.log(`  ✓ ${name} — ${title} · ${status}`);
  } catch (error) {
    failed += 1;
    console.log(`  ✗ ${arg} — ${String(error).split("\n")[0]}`);
  }
}
await browser.close();
clearTimeout(KILL);
process.exit(failed === 0 ? 0 : 1);
