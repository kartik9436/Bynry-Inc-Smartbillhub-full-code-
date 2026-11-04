#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W1 — Settings honesty for tenant custom fields
// Defects: DEF-TEN-9153 · DEF-TEN-9154 · DEF-TEN-9155 · DEF-TEN-9156 ·
//          DEF-TEN-9157 · DEF-CUS-9158
// Rules:   BR-TEN-052 (as amended 2026-10-02) · hard-won law 6 (no gate reads
//          rendered output, so the proof is a browser)
// ───────────────────────────────────────────────────────
// THE SAME STEPS AS THE REPRODUCTION, AFTER THE FIX, against a real API and a
// real PostgreSQL 16 database. It expects the database the reproduction left:
// Roof Material (Premises, stored on S14/S15/S16), Access note (Accounts,
// stored View-only on Account detail), Gate code (Accounts, REQUIRED, placed
// nowhere) and Visit window (Accounts, Input on New account and Account
// detail). Run the reproduction first, or create those four by hand.
//
//   node 10-scripts/cr161_w1_custom_field_settings_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8862) OUT UNIT (a vacant unit number)
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8862";
const T = process.env.TENANT || "brazosbend";
const ADMIN = process.env.ADMIN || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/cr161-w1-shots";
const UNIT = process.env.UNIT || "U-00102";
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
  const path = `${OUT}/cfw1_after_${name}.png`;
  await p.screenshot({ path, fullPage: true });
  // A blank capture is not a proof: a white 1440×1000 PNG is ~5 KB.
  ok(`screenshot ${name} is not blank`, statSync(path).size > 20000, `${statSync(path).size} bytes`);
}
const CF = `${BASE}/${T}/settings/reference-data/reference-data?list=custom_fields`;
const dialog = (p) => p.locator('[role="dialog"]');

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
async function rowText(p, label) {
  return ((await p.locator("tr", { hasText: label }).first().textContent()) ?? "").replace(/\s+/g, " ");
}
async function openPlacement(p, label) {
  await p.goto(CF, { waitUntil: "networkidle" });
  await p.locator("tr", { hasText: label }).first().locator('button[aria-label="Placement"]').click();
  await dialog(p).waitFor();
}
async function save(p) {
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  await p.waitForTimeout(1500);
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  const p = await signIn(browser);

  console.log("\n── DEF-TEN-9153 · the Screens count is screens that show the field ──");
  await p.goto(CF, { waitUntil: "networkidle" });
  const roofRow = await rowText(p, "Roof Material");
  ok("Roof Material no longer claims three screens", !/Pick one\s*No\s*3/.test(roofRow) && /0/.test(roofRow), roofRow);
  await shot(p, "1_table");

  console.log("\n── DEF-TEN-9153/9154 · Roof Material's placement (Premises: nothing renders yet) ──");
  await openPlacement(p, "Roof Material");
  const roofDialog = (await dialog(p).textContent()) ?? "";
  ok("no screen id is printed", !/\bS\d{1,3}\b/.test(roofDialog), roofDialog);
  ok("it says the import fills it", roofDialog.includes("Filled by import."), roofDialog);
  ok("no screen is offered", (await dialog(p).locator("select").count()) === 0);
  await shot(p, "2_roof_material_placement");
  await dialog(p).getByRole("button", { name: "Cancel" }).click();

  console.log("\n── DEF-TEN-9154 · an account field: named screens, grouped, their own choices ──");
  await openPlacement(p, "Visit window");
  const vwDialog = (await dialog(p).textContent()) ?? "";
  ok("grouped under Clerk input", vwDialog.includes("Clerk input"), vwDialog);
  ok("New account and Account detail are named", vwDialog.includes("New account") && vwDialog.includes("Account detail"));
  ok("no screen id is printed", !/\bS\d{1,3}\b/.test(vwDialog));
  const newAccount = await p.locator("#placement-S18 option").allTextContents();
  const detail = await p.locator("#placement-S21 option").allTextContents();
  ok("New account offers Input / Not shown", JSON.stringify(newAccount) === '["Input","Not shown"]', JSON.stringify(newAccount));
  ok("Account detail offers Input / View / Not shown", JSON.stringify(detail) === '["Input","View","Not shown"]', JSON.stringify(detail));
  await shot(p, "3_account_field_placement");
  await dialog(p).getByRole("button", { name: "Cancel" }).click();

  console.log("\n── DEF-TEN-9155 · shown on Account detail, collected nowhere → refused ──");
  await openPlacement(p, "Access note");
  await p.selectOption("#placement-S18", "not_shown");
  await p.selectOption("#placement-S21", "view");
  await save(p);
  const refusal = (await dialog(p).textContent()) ?? "";
  ok("the save is refused: No screen collects this field.", refusal.includes("No screen collects this field."), refusal);
  await shot(p, "4_no_input_route_refused");
  await p.selectOption("#placement-S18", "input");
  await save(p);
  ok("collected on New account, the same placement saves", (await dialog(p).count()) === 0);

  console.log("\n── DEF-TEN-9156 · Type help only for Number ──");
  await p.goto(CF, { waitUntil: "networkidle" });
  await p.locator("button", { hasText: "+ Add custom field" }).first().click();
  const appliesTo = await p.locator("#entity option").allTextContents();
  ok("Applies to offers only what something collects", JSON.stringify(appliesTo) === '["Premises","Units","Accounts"]', JSON.stringify(appliesTo));
  await p.selectOption("#data_type", "date");
  ok("Date carries no number help", (await p.locator("#data_type-help").count()) === 0);
  await p.selectOption("#data_type", "number");
  ok("Number says it is never used in a charge", ((await p.locator("#data_type-help").textContent()) ?? "").includes("Never used in any charge."));
  await shot(p, "5_type_help_number");
  await dialog(p).getByRole("button", { name: "Cancel" }).click();

  console.log("\n── DEF-TEN-9157 · Gate code required and placed nowhere: New Account saves ──");
  await p.goto(`${BASE}/${T}/accounts/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  await p.selectOption("#account_type", "residential");
  await p.fill("#full_name", "Rosa Pemberton");
  await p.fill("#email", "rosa.pemberton@example.com");
  await p.fill("#phone", "(281) 555-0199");
  await p.fill("#gov_id_last4", "4471");
  await p.getByText("Person", { exact: true }).first().click();
  const cont = async () => {
    await p.locator("button", { hasText: /^Continue/ }).first().click();
    await p.waitForTimeout(1500);
  };
  await cont();
  await p.locator("#unit_id").fill(UNIT);
  const option = p.locator('[role="option"]', { hasText: UNIT }).first();
  await option.waitFor({ timeout: 60000 });
  await option.click();
  await p.fill("#opened_at", "2026-10-02");
  await cont();
  await p.fill('[id="custom_data.visit_window"]', "Mornings");
  ok("Gate code is not on the form", (await p.locator('[id="custom_data.gate_code"]').count()) === 0);
  await cont();
  await cont();
  const answer = p.waitForResponse(
    (r) => r.url().endsWith(`/api/${T}/accounts`) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await p.locator('button[data-variant="primary"]').last().click();
  const res = await answer;
  const created = await res.json().catch(() => ({}));
  ok("POST /accounts answers 201", res.status() === 201, `${res.status()} ${JSON.stringify(created).slice(0, 300)}`);
  ok("the account carries Visit window = Mornings", created?.custom_data?.visit_window === "Mornings");
  await p.waitForTimeout(2000);
  await shot(p, "6_new_account_created");

  console.log("\n── DEF-CUS-9158 · Account detail edits the field placed Input there ──");
  await p.goto(`${BASE}/${T}/accounts/${created.id}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const before = (await p.locator("main").textContent()) ?? "";
  ok("Account detail shows Visit window read-only", before.includes("Visit window") && before.includes("Mornings"));
  await p.locator('button[aria-label^="Edit account"]').first().click();
  await dialog(p).waitFor();
  const box = p.locator('[id="custom_data.visit_window"]');
  await box.waitFor({ timeout: 20000 }).catch(() => {});
  ok("the Account setup dialog offers Visit window", (await box.count()) === 1);
  await box.fill("Afternoons");
  await shot(p, "7_account_edit_dialog");
  const patch = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  const patched = await patch;
  const sent = patched.request().postDataJSON();
  ok("only the change travels", JSON.stringify(sent) === '{"custom_data":{"visit_window":"Afternoons"}}', JSON.stringify(sent));
  ok("PATCH answers 200", patched.status() === 200, String(patched.status()));
  await p.waitForTimeout(1500);
  const after = (await p.locator("main").textContent()) ?? "";
  ok("Account detail now reads Afternoons", after.includes("Afternoons"));
  await shot(p, "8_account_detail_after_edit");

  console.log("\n── zero fields · every touched screen is unchanged ──");
  for (const label of ["Visit window", "Gate code", "Access note", "Roof Material"]) {
    await p.goto(CF, { waitUntil: "networkidle" });
    const row = p.locator("tr", { hasText: label }).first();
    const power = row.locator('button[aria-label="Deactivate"]');
    if (await power.count()) {
      await power.click();
      await p.waitForTimeout(1200);
    }
  }
  await p.goto(`${BASE}/${T}/accounts/${created.id}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  ok("Account detail shows no custom field", !((await p.locator("main").textContent()) ?? "").includes("Visit window"));
  await p.locator('button[aria-label^="Edit account"]').first().click();
  await dialog(p).waitFor();
  ok("the Account setup dialog has no custom section", (await dialog(p).locator('[id^="custom_data."]').count()) === 0);
  await shot(p, "9_zero_fields_account_edit");
} finally {
  await browser.close();
}

console.log(`\n${pass} passed · ${failures.length} failed`);
if (failures.length > 0) {
  for (const f of failures) console.log(`  FAILED: ${f}`);
  process.exit(1);
}
