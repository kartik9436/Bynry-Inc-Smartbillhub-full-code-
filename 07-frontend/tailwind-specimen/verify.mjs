/* CR-018 Phase 0 — drive the proof page in a real browser and print the verdict.
 *
 *   cd 07-frontend
 *   npx vite build --config tailwind-specimen/vite.config.ts
 *   (cd tailwind-specimen/dist-specimen && python3 -m http.server 8931 &)
 *   node tailwind-specimen/verify.mjs http://127.0.0.1:8931/index.html out.png
 *
 * file:// does NOT work — Chrome blocks the module script as cross-origin, the
 * page renders empty and the verdict comes back null. Serve it over HTTP.
 * If Playwright's own browser is not downloaded, point at any Chromium with
 * CR018_CHROME=/opt/pw-browsers/chromium-1194/chrome-linux/chrome.
 *
 * Exits 1 if anything failed, so it is usable as a gate the day Phase 1 wants
 * one. It is deliberately NOT wired into run_gates.py today: it needs a browser
 * and a built page, and claiming a gate the repo does not run is hard-won law 1.
 */
import { chromium } from "@playwright/test";

const url = process.argv[2] ?? "http://127.0.0.1:8931/index.html";
const shot = process.argv[3];

const launch = {};
if (process.env.CR018_CHROME) launch.executablePath = process.env.CR018_CHROME;

const browser = await chromium.launch(launch);
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(url);
await page.waitForSelector("body[data-ready='1']", { timeout: 20000 });
const r = await page.evaluate(() => window.__CR018);
if (shot) await page.screenshot({ path: shot, fullPage: true });
await browser.close();

const line = (n, o) => `${o.pass === o.total ? "PASS" : "FAIL"}  ${n}: ${o.pass}/${o.total}`;
console.log(line("utilities   ", r));
console.log(line("variables   ", r.vars));
console.log(line("neutralised ", r.neutralised));
console.log(
  `tokens in tokens.css: ${r.tokensInSource} · covered here: ${r.covered} · uncovered: ${r.uncovered.join(", ") || "none"}`,
);
for (const f of [...r.fail, ...r.vars.fail, ...r.neutralised.fail]) console.log("  ✗", JSON.stringify(f));
for (const e of errors) console.log("  page error:", e);

const ok =
  r.pass === r.total &&
  r.vars.pass === r.vars.total &&
  r.neutralised.pass === r.neutralised.total &&
  r.uncovered.length === 0 &&
  r.tokensInSource === r.covered;
process.exit(ok ? 0 : 1);
