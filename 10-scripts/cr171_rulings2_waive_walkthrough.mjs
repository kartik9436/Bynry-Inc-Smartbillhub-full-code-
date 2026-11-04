#!/usr/bin/env node
// CR-171-BRC10 lane RULINGS-2 — PO ruling (7) of 2026-10-05: walk the move-in's
// step 3 · Billing at 1440 and photograph the deposit WAIVE: the reason dialog
// (W1), the waived row with $215.00 → $65.00 and "$65.00 goes on the first
// bill." (W2), the Review's "Waived · Hardship" (W3), and Complete (W4).
//
// Usage (after `10-scripts/cr171_wiz_bill_world.py` on a LANE database):
//   MWB_BASE=http://127.0.0.1:5744 MWB_UNIT=U-00102 \
//   node 10-scripts/cr171_rulings2_waive_walkthrough.mjs
//
// Every shot asserts the page is not blank (h1 + a handle) and its figure.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.MWB_BASE || "http://127.0.0.1:5726";
const T = process.env.MWB_TENANT || "brazosbend";
const OUT = process.env.MWB_OUT || "08-qa/movein-2026-10-05/after/waive";
const EMAIL = process.env.MWB_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MWB_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MWB_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const UNIT = process.env.MWB_UNIT || "U-00102";
const CERT = process.env.MWB_CERT || "";
const DATE = process.env.MWB_DATE || "2026-10-10";

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 6 minutes — killing");
  process.exit(3);
}, 360000);

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
async function shot(name, mustSee, mustRead = []) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400);
  // The app scrolls inside its frame, so `fullPage` alone stops at 900px:
  // grow the window to the tallest scroller, shoot, and put it back.
  const tall = await page.evaluate(() =>
    Math.max(...[...document.querySelectorAll("*")].map((el) => el.scrollHeight), document.body.scrollHeight),
  );
  await page.setViewportSize({ width: 1440, height: Math.min(Math.max(tall + 120, 900), 6000) });
  await page.waitForTimeout(300);
  const title = (await page.locator("h1").first().innerText()).trim();
  const body = await page.locator("body").innerText();
  const missing = mustRead.filter((text) => !body.toLowerCase().includes(text.toLowerCase()));
  if (title === "" || (await page.locator(mustSee).count()) === 0 || missing.length > 0) {
    failed += 1;
    console.log(`  ✗ ${name} — h1 "${title}", ${mustSee}, missing ${JSON.stringify(missing)}`);
  }
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  console.log(`  ✓ ${name} — ${title}${mustRead.length ? " · " + mustRead.join(" · ") : ""}`);
}
const cont = () => page.getByRole("button", { name: "Continue" }).click();
const onStep = (n) => page.waitForSelector(`[data-wizard-step="${n}"][data-state="active"]`, { timeout: 20000 });
// The kit's tick is an sr-only input under its label: press the LABEL, as a
// person does.
const tick = (label) => page.locator("label", { hasText: label }).first().click();
const total = () => page.locator("[data-fees-total]").innerText();

try {
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#mvi_unit option:nth-child(2)", { state: "attached" });
  const value = await page.locator("#mvi_unit option", { hasText: UNIT }).first().getAttribute("value");
  await page.selectOption("#mvi_unit", value);
  await page.waitForLoadState("networkidle");
  await page.fill("#opened_at", DATE);
  await page.keyboard.press("Tab");
  await page.waitForLoadState("networkidle");
  for (const box of await page.locator("[data-opening-read] input").all()) {
    if ((await box.inputValue()) === "") await box.fill("9200");
  }
  await cont();
  await onStep(2);
  await page.getByLabel(/Full name/).fill("Nilesh G");
  await page.locator("label", { hasText: /^Person$/ }).first().click();
  await page.getByLabel(/^Phone/).fill("732-630-0285");
  await cont();
  await onStep(3);
  await page.waitForSelector("[data-fees-total]");

  // + Add fee RUSH → $215.00
  await page.getByRole("button", { name: "+ Add fee" }).click();
  await page.getByPlaceholder("Type a code or name").fill("RUSH");
  await page.getByText("RUSH · Same-day turn-on").first().click();
  await page.waitForFunction(() => document.querySelector("[data-fees-total]")?.textContent?.includes("215.00"));

  // ── W1 · the reason dialog ──────────────────────────────────────────────
  await page.getByRole("button", { name: "Waive deposit" }).click();
  await page.waitForSelector('[role="dialog"]');
  await page.fill("#reason", "Hardship");
  await shot("W1-waive-reason.png", '[role="dialog"]', ["Waive reason"]);
  await page.getByRole("dialog").getByRole("button", { name: "Waive", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("[data-fees-total]")?.textContent?.includes("65.00"));

  // ── W2 · waived: the Total and the first-bill line drop by $150.00 ──────
  await page.getByRole("radio", { name: "Add to bill" }).click();
  await shot("W2-deposit-waived-billing.png", "[data-deposit-waived]", [
    "Waived",
    "Hardship",
    "$65.00 goes on the first bill.",
  ]);
  console.log(`  · total read ${await total()}`);

  // ── W3 · Review ─────────────────────────────────────────────────────────
  await cont();
  await onStep(4);
  await shot("W3-review-deposit-waived.png", '[data-review-section="billing"]', ["Waived · Hardship"]);

  // ── W4 · Complete, and what was written ─────────────────────────────────
  await page.getByRole("button", { name: /Complete move-in/ }).click();
  await page.waitForSelector('[data-screen="move-in-completed"]', { timeout: 30000 });
  await shot("W4-completed.png", "[data-check-list]");
} catch (error) {
  failed += 1;
  console.log(`  ✗ ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "FAILED.png"), fullPage: true }).catch(() => undefined);
}
await browser.close();
clearTimeout(KILL);
process.exit(failed === 0 ? 0 : 1);
