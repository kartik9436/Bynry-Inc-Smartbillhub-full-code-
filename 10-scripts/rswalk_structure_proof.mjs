// CR-157-BRC10 wave C part 2 — DEF-RAT-9015 proved by clicking: on Add rate
// schedule, the Structure dropdown for a counted service (trash) offers Time of
// use and Demand disabled with their reason, and a metered one (electric) offers
// both. Writes two photographs and prints each option's label and state.
//   node 10-scripts/rswalk_structure_proof.mjs   (RSW_BASE, RSW_OUT as the walk)
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
const BASE = process.env.RSW_BASE || "http://127.0.0.1:8972";
const T = "brazosbend";
const OUT = process.env.RSW_OUT || "08-qa/screens/rate-schedules-waveC-2026-10-01";
const browser = await chromium.launch({ executablePath: process.env.RSW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60_000 }), page.click('button[type="submit"]')]);
for (const service of ["trash", "electric"]) {
  await page.goto(`${BASE}/${T}/plans-rates/rates/new`, { waitUntil: "networkidle" });
  await page.locator("[data-step=details]").waitFor();
  await page.waitForFunction(() => document.querySelectorAll("#rs-service option").length > 2);
  await page.selectOption("#rs-service", service);
  const options = await page.$$eval("#rs-structure option", (all) => all.map((o) => `${o.disabled ? "DISABLED" : "offered "} ${o.value.padEnd(19)} ${o.textContent}`));
  console.log(`── ${service}\n${options.join("\n")}`);
  await page.locator("#rs-structure").focus();
  await page.screenshot({ path: `${OUT}/matrix/def-rat-9015-structure-${service}.png` });
}
await browser.close();
