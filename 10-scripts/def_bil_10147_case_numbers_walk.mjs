#!/usr/bin/env node
// DEF-BIL-10147 (G3, PO 2026-10-14) — a correction case is numbered at Send.
// Walk on a PRIVATE copy of the dev database (it COMMITS cases):
//   CC_BASE=http://127.0.0.1:8092 CC_OUT=05-prototype/correction-case-numbers-2026-10-14 \
//   CC_STEP=<step> node 10-scripts/def_bil_10147_case_numbers_walk.mjs
// Steps: `look` (screens only) · `single` (Fix one bill: Bills → Fix → Check →
// Send) · `bulk` (Fix a billing run). Each prints PASS/FAIL lines and takes
// full-page shots.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.CC_BASE || "http://127.0.0.1:8092";
const T = process.env.CC_TENANT || "brazosbend";
const OUT = process.env.CC_OUT || "05-prototype/correction-case-numbers-2026-10-14";
const EMAIL = process.env.CC_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.CC_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CC_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const STEP = process.env.CC_STEP || "look";
const PATH = process.env.CC_PATH || "/billing/fix";

const KILL = setTimeout(() => {
  console.error("REFUSED: walk exceeded 10 minutes — killing");
  process.exit(3);
}, 600000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(30000);
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};
async function shot(name) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`  shot ${name}`);
}

try {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.getByRole("button", { name: /sign in/i }).click(),
  ]);
  console.log("signed in");
  await page.goto(`${BASE}/${T}${PATH}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);

  if (STEP === "look") {
    await shot(process.env.CC_SHOT || "look.png");
    const text = await page.locator("main").innerText().catch(() => "");
    console.log(text.slice(0, Number(process.env.CC_CHARS || 4000)));
  } else if (STEP === "click") {
    // CC_CLICKS = a JSON list of [kind, name] — kind: button|link|label|text|fill:<value>
    for (const [kind, name] of JSON.parse(process.env.CC_CLICKS || "[]")) {
      if (kind === "button") await page.getByRole("button", { name, exact: false }).first().click();
      else if (kind === "link") await page.getByRole("link", { name, exact: false }).first().click();
      else if (kind === "label") await page.getByLabel(name).first().check();
      else if (kind === "text") await page.getByText(name, { exact: false }).first().click();
      else if (kind === "css") await page.locator(name).first().click();
      else if (kind.startsWith("fill:")) await page.getByLabel(name).first().fill(kind.slice(5));
      else if (kind.startsWith("cssselect:"))
        await page.locator(name).first().selectOption({ label: kind.slice(10) });
      else if (kind.startsWith("select:"))
        await page.getByLabel(name).first().selectOption({ label: kind.slice(7) });
      else if (kind.startsWith("cssfill:")) await page.locator(name).first().fill(kind.slice(8));
      else if (kind === "html")
        console.log(await page.locator(name).evaluateAll((els) => els.map((e) => e.outerHTML.slice(0, 400))));
      else if (kind === "wait")await page.waitForTimeout(Number(name));
      else if (kind === "waitfor") await page.waitForSelector(name, { timeout: 240000 });
      else if (kind === "shot") await shot(name);
      await page.waitForLoadState("networkidle").catch(() => undefined);
      await page.waitForTimeout(700);
    }
    await shot(process.env.CC_SHOT || "click.png");
    const text = await page.locator("main").innerText().catch(() => "");
    console.log(text.slice(0, Number(process.env.CC_CHARS || 4000)));
  }
  for (const expect of JSON.parse(process.env.CC_EXPECT || "[]")) {
    const body = await page.locator("main").innerText().catch(() => "");
    check(`page shows ${JSON.stringify(expect)}`, body.includes(expect));
  }
} catch (err) {
  failed += 1;
  console.error(`FAIL ${err.message}`);
  await page.screenshot({ path: join(OUT, `FAILED-${STEP}.png`), fullPage: true }).catch(() => {});
} finally {
  clearTimeout(KILL);
  await browser.close();
  process.exit(failed ? 1 : 0);
}
