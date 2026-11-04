// CR-157-BRC10 wave C part 2 — DEF-RAT-9011 re-checked on the walk's own
// schedules: View details, Overview, at 1440. Prints each tile's text and
// whether it overflows its box, and photographs the page.
//   node 10-scripts/rswalk_next_change_proof.mjs
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
const BASE = process.env.RSW_BASE || "http://127.0.0.1:8972";
const T = "brazosbend";
const OUT = process.env.RSW_OUT || "08-qa/screens/rate-schedules-waveC-2026-10-01";
const state = JSON.parse(readFileSync(`${OUT}/rswalk_state.json`, "utf8"));
const KEYS = ["electric-demand-industrial", "electric-tiered-every", "water-flat-commercial"];
const browser = await chromium.launch({ executablePath: process.env.RSW_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60_000 }), page.click('button[type="submit"]')]);
for (const key of KEYS) {
  const id = state.rows[key]?.id;
  await page.goto(`${BASE}/${T}/plans-rates/rates/${id}?tab=overview`, { waitUntil: "networkidle" });
  await page.getByRole("tab", { selected: true }).waitFor();
  await page.waitForTimeout(800);
  const tiles = await page.evaluate(() =>
    [...document.querySelectorAll("main *")]
      .filter((el) => /next change/i.test(el.textContent ?? "") && el.children.length > 0 && el.textContent.length < 120)
      .slice(-1)
      .map((el) => ({ text: el.innerText.replace(/\s+/g, " "), overflows: el.scrollWidth > el.clientWidth + 1 })),
  );
  console.log(key, JSON.stringify(tiles));
  await page.screenshot({ path: `${OUT}/matrix/def-rat-9011-next-change-${key}.png` });
}
await browser.close();
