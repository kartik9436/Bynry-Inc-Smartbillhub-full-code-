// ── Trace ──────────────────────────────────────────────
// Change:  CR-168-BRC10 lane FLOW-MEASURE (§F "Flows that raise work") — the
//          PO's question, verbatim: "are you also raising work orders from Move
//          In, New Connect, Move out etc — and when work orders are completed is
//          the clerk able to see the status update in those requests?"
// What:    PHOTOGRAPH, as Dana in Chromium at 1440, the screen each flow's
//          clerk would look at — the record the work order was raised FROM —
//          once BEFORE the technician completes and the office accepts
//          (PHASE=before) and once AFTER (PHASE=after). Writes nothing.
// Rules:   BR-WRK-024 (every order carries its source) · BR-WRK-055 (the flow
//          does not wait for the visit and the visit does not close the flow) ·
//          B19 §12.3 (a request closes when its job finishes) · ruling 18 (the
//          office never completes, it only accepts).
// ───────────────────────────────────────────────────────
/**
 *   BASE=http://127.0.0.1:5601 PHASE=before OUT=08-qa/work-2026-10-04/flows \
 *     TARGETS=/tmp/flows-targets.json node 10-scripts/cr168_flows_walk.mjs
 *
 * TARGETS is a JSON list of {name, path, caption, find?} — `find` is a list of
 * strings whose presence on the screen is PRINTED (never asserted: this is a
 * measurement, and an absent word is the finding, not a crash).
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY (law 7 habit 2):
 *  * a screen that never loaded photographs as a skeleton — so every shot
 *    prints the API calls that failed and the first 300 characters of the
 *    rendered `.view` text, and the lane OPENS every PNG before citing it;
 *  * `fullPage: true` returns only the fold in this app (`.view` scrolls inside
 *    a 100vh shell), so the viewport is grown to `.view`'s scroll height.
 */
import { createRequire } from "node:module";
import { readFileSync, mkdirSync, statSync } from "node:fs";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5601";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const PHASE = process.env.PHASE ?? "before";
const OUT = process.env.OUT ?? "/tmp/cr168-flows";
const EXE = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const TARGETS = JSON.parse(readFileSync(process.env.TARGETS, "utf8"));

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: EXE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 950 } });
const page = await ctx.newPage();
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click("button[type=submit]");
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

for (const t of TARGETS) {
  failed.length = 0;
  await page.setViewportSize({ width: 1440, height: 950 });
  await page.goto(`${BASE}/${TENANT}${t.path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  if (t.click) {
    try { await page.getByRole("tab", { name: t.click }).first().click(); await page.waitForTimeout(1000); } catch { console.log(`  (no tab named ${t.click})`); }
  }
  const need = await page.evaluate(() => {
    const view = document.querySelector(".view");
    return view === null ? null : Math.ceil(view.getBoundingClientRect().top + view.scrollHeight + 24);
  });
  const height = Math.min(Math.max(need ?? 950, 950), 12000);
  await page.setViewportSize({ width: 1440, height });
  await page.waitForTimeout(400);
  const file = join(OUT, `${t.name}-${PHASE}.png`);
  await page.screenshot({ path: file, fullPage: false });
  const text = await page.evaluate(() => (document.querySelector(".view") ?? document.body).innerText);
  console.log(`\n=== ${t.name}-${PHASE}.png  1440x${height}  ${statSync(file).size} bytes — ${t.caption}`);
  console.log(`    ${page.url().replace(BASE, "")}`);
  if (failed.length) console.log(`    API ERRORS: ${JSON.stringify(failed)}`);
  for (const word of t.find ?? []) console.log(`    "${word}" on screen: ${text.includes(word) ? "YES" : "no"}`);
  console.log(`    text: ${text.replace(/\s+/g, " ").slice(0, 300)}`);
}
await browser.close();
