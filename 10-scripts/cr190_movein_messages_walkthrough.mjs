#!/usr/bin/env node
// CR-190-BRC10 lane MOVEIN-MSG — walk the two screens this lane changed:
//   1 · Settings → Templates → Service agreement → *Create from our default*
//       → the draft opens in the editor → Publish.
//   2 · Move-in step 4 · Messaging: untick the service agreement and move the
//       welcome to Printed letter, then Complete. The queued welcome is then
//       rendered by `cr190_movein_messages_readback.py`.
//
// Usage — on a PRIVATE walk database only (it commits a move-in and publishes
// a contract version):
//   CMM_BASE=http://127.0.0.1:8982 CMM_OUT=<dir> node 10-scripts/cr190_movein_messages_walkthrough.mjs
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.CMM_BASE || "http://127.0.0.1:8982";
const T = process.env.CMM_TENANT || "brazosbend";
const OUT = process.env.CMM_OUT || ".";
const EMAIL = process.env.CMM_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.CMM_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.CMM_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DATE = process.env.CMM_DATE || "2026-10-22";
const EFFECTIVE = process.env.CMM_EFFECTIVE || "2026-10-23";

const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 8 minutes — killing");
  process.exit(3);
}, 480000);

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1800 } });
const page = await context.newPage();
page.setDefaultTimeout(30000);
let failed = 0;
function ok(what, cond, detail = "") {
  if (cond) console.log(`  ✓ ${what}`);
  else {
    failed += 1;
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}
async function shot(name) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, name), fullPage: true });
  console.log(`    · ${name}`);
}
async function cont() {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: "Continue" }).click();
}
async function onStep(n) {
  await page.waitForSelector(`[data-wizard-step="${n}"][data-state="active"]`, { timeout: 30000 });
}

try {
  await page.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    page.click('button[type="submit"]'),
  ]);

  console.log("\n── 1 · Create from our default ─────────────────────────");
  await page.goto(
    `${BASE}/${T}/settings/reference-data/templates?template=contract_service_agreement`,
    { waitUntil: "domcontentloaded" },
  );
  await page.waitForLoadState("networkidle");
  if (process.env.CMM_SKIP_CREATE !== "1") {
    await page.waitForSelector('[data-testid="platform-default-offer"]');
    ok("the offer is drawn", (await page.locator('[data-testid="create-from-default"]').count()) === 1);
    await shot("01-offer-with-create-from-default.png");
    await page.fill("#from_default_effective_from", EFFECTIVE);
    await page.keyboard.press("Tab");
    await page.getByTestId("create-from-default-submit").click();
    await page.getByText("Draft created. Publish it when ready.").waitFor();
    ok("the toast says a draft was created", true);
    await shot("02-draft-open-in-editor.png");
    const body = await page.locator("textarea").first().inputValue().catch(() => "");
    ok("the editor holds the platform wording", body.length > 200, `length ${body.length}`);
  }
  // Publish is the version history's own action, exactly as for any draft.
  await page.goto(
    `${BASE}/${T}/settings/reference-data/templates?template=contract_service_agreement&view=history`,
    { waitUntil: "domcontentloaded" },
  );
  await page.waitForLoadState("networkidle");
  const publish = page.getByRole("button", { name: /Publish/ }).first();
  ok("the draft offers Publish", (await publish.count()) > 0);
  if ((await publish.count()) > 0) {
    await publish.click();
    const confirm = page.getByRole("dialog").getByRole("button", { name: /Publish/ });
    if ((await confirm.count()) > 0) await confirm.click();
    await page.waitForTimeout(2000);
  }
  await shot("04-published.png");

  console.log("\n── 2 · Move-in step 4 — untick + channel change ────────");
  await page.goto(`${BASE}/${T}/move-ins/new`, { waitUntil: "domcontentloaded" });
  const unitRow = page.locator("tr", { hasText: process.env.CMM_UNIT || "U-00102" }).first();
  await unitRow.getByRole("button", { name: "Use" }).click();
  await page.waitForLoadState("networkidle");
  await page.fill("#opened_at", DATE);
  await page.keyboard.press("Tab");
  await page.waitForLoadState("networkidle");
  // Every metered service needs its opening read (on or before today).
  await page.waitForTimeout(1500);
  const reads = page.locator('input[id*="-read-"]:not([id*="-read-date-"])');
  for (let i = 0; i < (await reads.count()); i += 1) {
    if ((await reads.nth(i).inputValue()) === "") {
      await reads.nth(i).fill(process.env.CMM_READ || "8700");
      await page.keyboard.press("Tab");
    }
  }
  const visit = page.getByLabel("Visit needed");
  if ((await visit.count()) > 0 && (await visit.isChecked())) await visit.uncheck({ force: true });
  await cont();
  await onStep(2);
  await page.getByLabel(/Full name/).fill("Okafor, Ade");
  await page.locator("label", { hasText: /^Person$/ }).first().click();
  await page.getByLabel(/^Email/).first().fill("ade.okafor@example.test").catch(() => undefined);
  await page.getByLabel(/^Phone/).fill("512-555-0142");
  await cont();
  await onStep(3);
  await page.waitForLoadState("networkidle");
  // Fees go on the first bill; this walk is about the messages, not the money.
  const addToBill = page.getByText("Add to bill", { exact: true });
  if ((await addToBill.count()) > 0) await addToBill.first().click({ force: true });
  const method = page.getByLabel(/^Method/);
  if ((await method.count()) > 0 && (await method.isVisible())) {
    await method.selectOption({ index: 1 });
  }
  await cont();
  // A press before the step's own reads settle is held; press once more if so.
  if ((await page.locator('[data-wizard-step="4"][data-state="active"]').count()) === 0) {
    await page.waitForTimeout(2000);
    await cont();
  }
  await onStep(4);
  await page.waitForSelector("[data-move-in-messages] [data-editable-row]");
  await shot("05-step4-defaults.png");
  const rows = page.locator("[data-move-in-messages] [data-editable-row]");
  const welcome = rows.filter({ has: page.locator('[data-message-name="move_in_welcome"]') });
  const agreement = rows.filter({ has: page.locator('[data-message-name="service_agreement"]') });
  ok("the welcome's tick is live", !(await welcome.getByRole("checkbox").isDisabled()));
  await welcome.locator("select").first().selectOption("pdf_print");
  await agreement.getByRole("checkbox").uncheck({ force: true });
  await shot("06-step4-unticked-and-rechannelled.png");
  const willSend = await page.locator("[data-will-send]").innerText();
  ok("the footer counts one fewer", /1 will send/.test(willSend), willSend);
  await page.getByRole("button", { name: /Complete move-in/ }).click();
  await page.waitForTimeout(4000);
  await shot("07-completed.png");
  console.log(`    url ${page.url()}`);
} catch (error) {
  failed += 1;
  console.log(`  ✗ walk stopped: ${error.message}`);
  await page.screenshot({ path: join(OUT, "99-stopped.png"), fullPage: true }).catch(() => undefined);
} finally {
  clearTimeout(KILL);
  await browser.close();
}
console.log(failed === 0 ? "\nPASS" : `\nFAIL (${failed})`);
process.exit(failed === 0 ? 0 : 1);
