#!/usr/bin/env node
// CR-182-BRC10 E1 (lane HIGHUSE, 2026-10-14) — Ana Alvarez's water reading is
// flagged high; what she sees in her portal, and (PHASE=billed) after the bill.
//
// Usage (a PRIVATE copy of the dev database, servers on 8006/8086):
//   HU_BASE=http://127.0.0.1:8086 HU_PHASE=flagged|billed HU_BILL=<number> \
//   node 10-scripts/cr182_high_consumption_walk.mjs
//
// flagged · Home carries *High consumption alert · Water reading on 10/11/2026:
//           unusually high.* with *See your readings* → /readings; Readings
//           tags the 10/11 row and no other.
// billed  · Home carries *Your last bill is higher than usual.* with *See why →*
//           → /bills/<number>/comparison; the bill says *High usage* beside
//           *Why is this different?*; the reading alert has gone.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.HU_BASE || "http://127.0.0.1:8086";
const T = process.env.HU_TENANT || "brazosbend";
const OUT = process.env.HU_OUT || "05-prototype/high-consumption-alert-2026-10-14";
const LOGIN = process.env.HU_LOGIN || "alvarez0@example.invalid";
const PASSWORD = process.env.HU_PASSWORD || "Sample-Portal-2026!";
const CHROME = process.env.HU_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const PHASE = process.env.HU_PHASE || "flagged";
const BILL = process.env.HU_BILL || "";
const READ_DAY = process.env.HU_READ_DAY || "2026-10-11";

const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(25000);
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(String(e)));
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};
async function shot(name) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(500);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`  shot ${name}`);
}
const rel = (p) => `${BASE}/${T}/portal${p}`;

try {
  const signIn = await page.request.post(`${BASE}/api/${T}/portal/auth/sign-in`, {
    data: { email: LOGIN, password: PASSWORD },
  });
  check("portal sign-in", signIn.ok(), String(signIn.status()));

  await page.goto(rel("/home"), { waitUntil: "domcontentloaded" });
  await page.waitForSelector("[data-screen='CWP-022']");
  await page.waitForTimeout(1200);

  if (PHASE === "flagged") {
    const item = page.locator("[data-attention='high_consumption']").first();
    await item.waitFor();
    const text = await item.innerText();
    check("Home · the alert chip", text.toLowerCase().includes("high consumption alert"), text.replace(/\n/g, " · "));
    check("Home · the fact names the service and the date", /Water reading on .*unusually high\./.test(text));
    const href = await item.locator("a").first().getAttribute("href");
    check("Home · the door opens Readings", href === `/${T}/portal/readings`, href ?? "");
    await item.scrollIntoViewIfNeeded();
    await shot("1-home-high-consumption-alert.png");

    await page.goto(rel("/readings"), { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-screen='CWP-034']");
    await page.waitForTimeout(1500);
    const tags = await page.locator("[data-chip^='high-']").evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-chip")),
    );
    check("Readings · the flagged row is tagged, and only it", tags.length === 1 && tags[0] === `high-${READ_DAY}`, JSON.stringify(tags));
    await shot("2-readings-tag.png");
  } else {
    const item = page.locator("[data-attention='high_bill']").first();
    await item.waitFor();
    const text = await item.innerText();
    check("Home · the bill notice", text.includes("Your last bill is higher than usual."), text.replace(/\n/g, " · "));
    const href = await item.locator("a").first().getAttribute("href");
    check("Home · See why opens the comparison", href === `/${T}/portal/bills/${BILL}/comparison`, href ?? "");
    check("Home · the reading alert has gone", (await page.locator("[data-attention='high_consumption']").count()) === 0);
    await item.scrollIntoViewIfNeeded();
    await shot("4-home-last-bill-higher.png");

    await page.goto(rel(`/bills/${BILL}`), { waitUntil: "domcontentloaded" });
    await page.waitForSelector("[data-screen='CWP-028']");
    await page.waitForTimeout(1200);
    const chip = await page.locator("[data-chip='bill-high-usage']").innerText().catch(() => "");
    check("Bill · *High usage*", chip.trim().toLowerCase() === "high usage", chip);
    const cmp = await page.locator("[data-link='comparison']").getAttribute("href");
    check("Bill · beside *Why is this different?*", cmp === `/${T}/portal/bills/${BILL}/comparison`, cmp ?? "");
    await shot("5-bill-high-usage.png");
    await page.goto(rel(`/bills/${BILL}/comparison`), { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    await shot("6-bill-comparison.png");
    await page.goto(rel("/readings"), { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    await shot("7-readings-tag-after-billing.png");
  }
  check("no page errors", jsErrors.length === 0, jsErrors.slice(0, 3).join(" | "));
} catch (err) {
  failed += 1;
  console.error("WALK ERROR", err);
  await shot(`FAILED-${PHASE}.png`).catch(() => undefined);
} finally {
  clearTimeout(KILL);
  await browser.close();
}
console.log(failed ? `${failed} CHECK(S) FAILED` : "ALL CHECKS PASSED");
process.exit(failed ? 1 : 0);
