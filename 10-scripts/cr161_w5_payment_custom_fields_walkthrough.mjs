#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W5 — payment custom fields, captured at entry only
// Rules:   BR-TEN-046 (as amended 2026-10-02) · BR-TEN-048 · BR-TEN-052 ·
//          CLAUDE.md hard rule 4 · hard-won law 6 (no gate reads rendered
//          output, so the proof is a browser)
// ───────────────────────────────────────────────────────
// The worked example put to the PO: a cashier records **Drawer = 2** on a
// **$120.00** payment; it shows on Payment detail; nothing there can change it.
//
// Against a real API and a real PostgreSQL 16 database seeded with
// `seed_demo` + `load_sample_data --tenant brazosbend`, and the front end
// built with `vite build --mode wolocal` and served by `07-frontend/server.mjs`.
//
//   node 10-scripts/cr161_w5_payment_custom_fields_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8876) OUT ACCOUNT (an account number)
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8876";
const T = process.env.TENANT || "brazosbend";
const ADMIN = process.env.ADMIN || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/cr161-w5-shots";
const ACCOUNT = process.env.ACCOUNT || "A-10432";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });

let pass = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    failures.push(`${what} ${detail}`);
    console.log(`  ✗ ${what} ${detail}`);
  }
}
async function shot(p, name) {
  const path = `${OUT}/cf5_${name}.png`;
  await p.screenshot({ path, fullPage: true });
  // A blank capture is not a proof: a white 1440×1000 PNG is ~5 KB.
  ok(`screenshot ${name} is not blank`, statSync(path).size > 20000, `${statSync(path).size} bytes`);
}
const CF = `${BASE}/${T}/settings/reference-data/reference-data?list=custom_fields`;
const RECORD = `${BASE}/${T}/payments/record/new`;
const dialog = (p) => p.locator('[role="dialog"]');
const drawer = (p) => p.locator('[id="custom_data.drawer"]');

async function signIn(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(40000);
  await p.goto(`${BASE}/${T}/signin`);
  await p.fill("#signin-email", ADMIN);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

async function openRecord(p) {
  await p.goto(RECORD, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
}
async function chooseAccountAndAmount(p) {
  await p.locator("#account_id").fill(ACCOUNT);
  const option = p.locator('[role="option"]', { hasText: ACCOUNT }).first();
  await option.waitFor({ timeout: 60000 });
  await option.click();
  await p.fill("#amount", "120.00");
}
function submit(p) {
  const answer = p.waitForResponse(
    (r) => /\/api\/[^/]+\/accounts\/[^/]+\/payments$/.test(r.url()) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  return p
    .locator("button", { hasText: /^Record payment$/ })
    .last()
    .click()
    .then(() => answer);
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  const p = await signIn(browser);

  await p.goto(CF, { waitUntil: "networkidle" });
  // Re-runnable: a second run on the same database finds Drawer already defined
  // and walks the rest; the zero-field and create steps belong to the first run.
  const firstRun = (await p.locator("tr", { hasText: "Drawer" }).count()) === 0;
  if (firstRun) {
  console.log("\n── a utility with no payment fields: Record payment is unchanged ──");
  await openRecord(p);
  ok("no custom section on Record payment", (await p.locator('[id^="custom_data."]').count()) === 0);
  await shot(p, "1_record_payment_no_fields");

  console.log("\n── Settings: define Drawer on Payments, Input on Record payment, View on Payment detail ──");
  await p.goto(CF, { waitUntil: "networkidle" });
  await p.locator("button", { hasText: "+ Add custom field" }).first().click();
  await dialog(p).waitFor();
  const appliesTo = await p.locator("#entity option").allTextContents();
  ok("Applies to offers Payments", appliesTo.includes("Payments"), JSON.stringify(appliesTo));
  await p.fill("#label", "Drawer");
  await p.selectOption("#entity", { label: "Payments" });
  await p.selectOption("#data_type", "text");
  const required = dialog(p).getByLabel(/Required/i).first();
  if (await required.count()) await required.check({ force: true });
  await shot(p, "2_settings_new_payment_field");
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  await p.waitForTimeout(1800);
  }
  await p.goto(CF, { waitUntil: "networkidle" });
  await p.locator("tr", { hasText: "Drawer" }).first().locator('button[aria-label="Placement"]').click();
  await dialog(p).waitFor();
  const placementText = (await dialog(p).textContent()) ?? "";
  ok("Placement names Record payment and Payment detail", placementText.includes("Record payment") && placementText.includes("Payment detail"), placementText);
  ok("no screen id is printed", !/\bS\d{1,3}\b/.test(placementText));
  const recordChoices = await p.locator("#placement-S35 option").allTextContents();
  const detailChoices = await p.locator("#placement-S33 option").allTextContents();
  ok("Record payment offers Input / Not shown", JSON.stringify(recordChoices) === '["Input","Not shown"]', JSON.stringify(recordChoices));
  ok("Payment detail offers View / Not shown", JSON.stringify(detailChoices) === '["View","Not shown"]', JSON.stringify(detailChoices));
  await p.selectOption("#placement-S35", "input");
  await p.selectOption("#placement-S33", "view");
  await shot(p, "3_settings_placement");
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  await p.waitForTimeout(1800);
  ok("the placement saved", (await dialog(p).count()) === 0);

  console.log("\n── Record payment: required Drawer left blank is refused and the form is kept ──");
  await openRecord(p);
  await drawer(p).waitFor({ timeout: 30000 });
  ok("Record payment draws Drawer", (await drawer(p).count()) === 1);
  await chooseAccountAndAmount(p);
  const refused = await submit(p);
  const refusedBody = refused.request().postDataJSON();
  ok("the blank answer is refused (422)", refused.status() === 422, String(refused.status()));
  ok("the form sent its answers from this screen", JSON.stringify(refusedBody.custom_data) === "{}", JSON.stringify(refusedBody.custom_data));
  await p.waitForTimeout(800);
  ok("Drawer is marked", (await drawer(p).getAttribute("aria-invalid")) === "true");
  ok("the amount is kept", (await p.inputValue("#amount")) === "120.00");
  await shot(p, "4_record_payment_required_refused");

  console.log("\n── Record payment: Drawer = 2 on $120.00 ──");
  await drawer(p).fill("2");
  const recorded = await submit(p);
  const created = await recorded.json().catch(() => ({}));
  ok("POST answers 201", recorded.status() === 201, `${recorded.status()} ${JSON.stringify(created).slice(0, 300)}`);
  ok("the answer travelled", JSON.stringify(recorded.request().postDataJSON().custom_data) === '{"drawer":"2"}');
  await p.waitForTimeout(1500);
  await shot(p, "5_record_payment_recorded");

  console.log("\n── Payment detail: Drawer 2, read-only ──");
  await p.goto(`${BASE}/${T}/payments/${created.payment_no}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const label = p.locator("dt", { hasText: "Drawer" }).first();
  await label.waitFor({ timeout: 30000 });
  const value = (await label.locator("xpath=following-sibling::dd[1]").textContent()) ?? "";
  ok("Payment detail shows Drawer = 2", value.trim() === "2", value);
  const section = label.locator("xpath=ancestor::section[1]");
  ok("no control inside the section", (await section.locator("input, select, textarea, button").count()) === 0);
  ok("no Drawer input anywhere on the page", (await drawer(p).count()) === 0);
  await shot(p, "6_payment_detail_read_only");
  const edit = p.locator("button", { hasText: /^Correct reference$/ }).first();
  if (await edit.count()) {
    await edit.click();
    await dialog(p).waitFor();
    ok("the Correct reference dialog does not offer Drawer", !(((await dialog(p).textContent()) ?? "").includes("Drawer")));
    await shot(p, "7_correct_reference_has_no_drawer");
    await dialog(p).getByRole("button", { name: "Cancel" }).click();
  }
} finally {
  await browser.close();
}

console.log(`\n${pass} passed · ${failures.length} failed`);
if (failures.length > 0) {
  for (const f of failures) console.log(`  FAILED: ${f}`);
  process.exit(1);
}
