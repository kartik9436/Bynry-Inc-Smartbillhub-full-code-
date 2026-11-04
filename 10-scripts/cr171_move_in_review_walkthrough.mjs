#!/usr/bin/env node
// CR-171-BRC10 lane MVI-WIZ-REV — walk step 4 · Review (image 45), its
// Messaging table with a message added (image 46) and the Edit door on a
// move-in REQUEST and on a NOT STARTED move-in (image 47), at 1440, for the
// side-by-side with `05-prototype/movein-redesign-2026-10-05/images/`.
//
// Usage (a lane database seeded with `seed_demo`, `load_sample_data --tenant
// brazosbend` and `10-scripts/cr171_detail_seed.py`):
//   MWR_BASE=http://127.0.0.1:5727 MWR_OUT=08-qa/movein-2026-10-05/after/review \
//   MWR_REQUEST=<a To approve request id> MWR_NOT_STARTED=<a Not started request id> \
//   node 10-scripts/cr171_move_in_review_walkthrough.mjs
//
// It COMMITS NOTHING: the review is photographed and left; the request Edit is
// SAVED (Save draft & exit writes the request's own fields back unchanged), so
// run it on a lane database. Each shot asserts the page is not blank — the h1
// and the named element must be on it.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.MWR_BASE || "http://127.0.0.1:5727";
const T = process.env.MWR_TENANT || "brazosbend";
const OUT = process.env.MWR_OUT || "08-qa/movein-2026-10-05/after/review";
const EMAIL = process.env.MWR_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MWR_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MWR_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DATE = process.env.MWR_DATE || "2026-10-10";
const REQUEST = process.env.MWR_REQUEST || "";
const NOT_STARTED = process.env.MWR_NOT_STARTED || "";

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: { width: 1440, height: Number(process.env.MWR_HEIGHT || 2300) } });
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
async function shot(name, mustSee) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);
  const title = (await page.locator("h1").first().innerText()).trim();
  if (title === "" || (await page.locator(mustSee).count()) === 0) {
    failed += 1;
    console.log(`  ✗ ${name} — blank or missing ${mustSee} (h1: "${title}")`);
  }
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`  ✓ ${name} — ${title}`);
}
async function onStep(n) {
  await page.waitForSelector(`[data-wizard-step="${n}"][data-state="active"]`, { timeout: 20000 });
}
async function cont() {
  // Each step reads its own facts on mount; a press before they land is
  // held by the step (the deposit waits on the plan's figure), so settle first.
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: "Continue" }).click();
}

try {
  // ── Image 45 · step 4 · Review, from a fresh move-in ─────────────────────
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#mvi_unit option:nth-child(2)", { state: "attached" });
  const unit = await page.locator("#mvi_unit option").nth(1).getAttribute("value");
  await page.selectOption("#mvi_unit", unit);
  await page.waitForLoadState("networkidle");
  await page.fill("#opened_at", DATE);
  await page.keyboard.press("Tab");
  await cont();
  await onStep(2);
  await page.getByLabel(/Full name/).fill("Nilesh G");
  await page.locator("label", { hasText: /^Person$/ }).first().click();
  await page.getByLabel(/^Email/).first().fill("nilesh@bynry.io").catch(() => undefined);
  await page.getByLabel(/^Phone/).fill("732-630-0285");
  await cont();
  await onStep(3);
  await cont();
  await onStep(4);
  await page.waitForSelector('[data-review-section="billing"]');
  await shot("W45-review.png", "[data-move-in-review]");

  // ── Image 46 · + Add message, a message picked ───────────────────────────
  await page.getByRole("button", { name: "+ Add message" }).click();
  const added = page.locator("[data-editable-row]").last();
  const picker = added.locator("select").first();
  const options = await picker.locator("option").allTextContents();
  if (options.length > 1) {
    await picker.selectOption({ index: 1 });
  }
  await added.locator("select").nth(2).selectOption("text");
  await shot("W46-review-message-added.png", "[data-will-send]");

  // ✎ Edit returns to its step
  await page.locator('[data-review-edit="customer"]').click();
  await onStep(2);
  await shot("W45b-edit-to-customer.png", '[data-wizard="rail"]');

  // ── Image 47 · Edit on a To approve REQUEST ──────────────────────────────
  if (REQUEST !== "") {
    await page.goto(`${BASE}/${T}/move-ins/new?request=${REQUEST}&edit=1`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => /Edit move-in · SR-/.test(document.querySelector("h1")?.textContent ?? ""), null, {
      timeout: 20000,
    });
    await shot("W47-edit-request.png", '[data-wizard="rail"]');
    await page.getByRole("button", { name: "Save draft & exit" }).click();
    await page.waitForURL((u) => /\/moves\/SR-/.test(u.pathname), { timeout: 20000 });
    await shot("W47b-request-saved-back.png", "h1");
  }

  // ── Image 47 · Edit on a NOT STARTED move-in ─────────────────────────────
  if (NOT_STARTED !== "") {
    await page.goto(`${BASE}/${T}/move-ins/new?request=${NOT_STARTED}&edit=1`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => /Edit move-in · MVI-/.test(document.querySelector("h1")?.textContent ?? ""), null, {
      timeout: 20000,
    });
    await shot("W47c-edit-not-started.png", '[data-wizard="rail"]');
  }
} catch (error) {
  failed += 1;
  console.log(`  ✗ ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "FAILED.png"), fullPage: true }).catch(() => undefined);
}
await browser.close();
clearTimeout(KILL);
process.exit(failed === 0 ? 0 : 1);
