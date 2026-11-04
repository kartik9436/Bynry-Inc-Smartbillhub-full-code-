#!/usr/bin/env node
// CR-171-BRC10 lane MVI-WIZ-BILL — walk the move-in's step 3 · Billing at 1440
// and photograph the four drawn states (images 41–44), then COMPLETE the J4
// worked case and photograph Move-in completed:
//   41  every tick on, Pay now, the whole $175.00 by check
//   42  See full rates open
//   43  + Add fee RUSH ($40.00) → $215.00, $100.00 paid → "$115.00 goes on the first bill."
//   44  Preferences and Tax unticked, Add to bill → "$215.00 goes on the first bill."
//
// Usage (after `10-scripts/cr171_wiz_bill_world.py` on a LANE database):
//   MWB_BASE=http://127.0.0.1:5726 MWB_OUT=08-qa/movein-2026-10-05/after/billing \
//   MWB_UNIT=U-00102 MWB_CERT=/path/to/np-4471-certificate.pdf \
//   node 10-scripts/cr171_wiz_bill_walkthrough.mjs
//
// Every shot asserts the page is not blank (h1 + the step's own handle) and
// the figure it exists to show.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.MWB_BASE || "http://127.0.0.1:5726";
const T = process.env.MWB_TENANT || "brazosbend";
const OUT = process.env.MWB_OUT || "08-qa/movein-2026-10-05/after/billing";
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
  const value = await page
    .locator("#mvi_unit option", { hasText: UNIT })
    .first()
    .getAttribute("value");
  await page.selectOption("#mvi_unit", value);
  await page.waitForLoadState("networkidle");
  await page.fill("#opened_at", DATE);
  await page.keyboard.press("Tab");
  await page.waitForLoadState("networkidle");
  // Step 1 now asks an opening read for every unread meter (lane WIZ-UNIT).
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

  // ── 41 · every tick on, Pay now the whole total by check ────────────────
  await page.selectOption("#paperless", "on");
  await page.selectOption("#sms_reminders", "on");
  await page.selectOption("#autopay", "on");
  await tick("Claim discounts");
  const d1 = page.locator('[data-array="move-in-discounts"] select[data-cell="discount"]').first();
  await d1.selectOption({ label: "Autopay discount" });
  await page.getByRole("button", { name: "+ Add discount" }).click();
  await page
    .locator('[data-array="move-in-discounts"] select[data-cell="discount"]')
    .nth(1)
    .selectOption({ label: "Paperless billing" });
  await tick("Tax exempt");
  await page.selectOption("#move_in_tax_category", { label: "Non-profit" });
  await page.fill("#move_in_tax_ref", "NP-4471");
  await page.fill("#move_in_tax_issued", "2026-01-15");
  await page.fill("#move_in_tax_expires", "2029-01-14");
  if (CERT !== "") await page.setInputFiles("#move_in_tax_certificate", CERT);
  await page.selectOption("#move_in_payment_method", "check");
  await page.fill("#move_in_payment_reference", "1043");
  await shot("B41-billing.png", '[data-move-in-billing]', [
    "Fees total $175.00",
    "All fees paid now. Receipt prints on complete.",
  ]);

  // ── 42 · See full rates ─────────────────────────────────────────────────
  await page.getByRole("button", { name: /See full rates/ }).click();
  await shot("B42-full-rates.png", "[data-move-in-full-rates]", ["Meters and devices"]);

  // ── 43 · + Add fee RUSH, $100.00 paid ───────────────────────────────────
  await page.getByRole("button", { name: "+ Add fee" }).click();
  await page.getByPlaceholder("Type a code or name").fill("RUSH");
  await page.getByText("RUSH · Same-day turn-on").first().click();
  await page.waitForFunction(() => document.querySelector("[data-fees-total]")?.textContent?.includes("215.00"));
  await page.fill("#move_in_payment_amount", "100.00");
  await shot("B43-fee-added-part-payment.png", "[data-move-in-billing]", [
    "Fees total $215.00",
    "$115.00 goes on the first bill.",
  ]);

  // ── 44 · Preferences and Tax unticked, Add to bill ──────────────────────
  await tick("Set preferences");
  await tick("Tax exempt");
  await page.getByRole("radio", { name: "Add to bill" }).click();
  await shot("B44-add-to-bill-sections-unticked.png", "[data-move-in-billing]", [
    "$215.00 goes on the first bill.",
  ]);
  console.log(`  · total read ${await total()}`);

  // ── Complete the J4 case: Pay now $100.00 by check 1043 ─────────────────
  await page.getByRole("radio", { name: "Pay now" }).click();
  await page.selectOption("#move_in_payment_method", "check");
  await page.fill("#move_in_payment_amount", "100.00");
  await page.fill("#move_in_payment_reference", "1043");
  await page.fill("#move_in_payment_received", DATE);
  await cont();
  await onStep(4);
  await shot("B45-review-after-billing.png", '[data-wizard="rail"]');
  await page.getByRole("button", { name: /Complete move-in/ }).click();
  await page.waitForSelector('[data-screen="move-in-completed"]', { timeout: 30000 });
  await shot("B48-completed-j4.png", "[data-check-list]");
} catch (error) {
  failed += 1;
  console.log(`  ✗ ${String(error).split("\n")[0]}`);
  await page.screenshot({ path: join(OUT, "FAILED.png"), fullPage: true }).catch(() => undefined);
}
await browser.close();
clearTimeout(KILL);
process.exit(failed === 0 ? 0 : 1);
