#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 waves W2 + W3, lane CF-W3b — tenant custom fields on
//          premises, units, service points and assets
// Defects: DEF-MET-9226 · DEF-MET-9227 · DEF-MET-9173 · DEF-AST-9171 · DEF-MET-9172
// Rules:   BR-TEN-052 as amended 2026-10-02 · hard-won law 6 (no gate reads
//          rendered output, so the proof is a browser)
// ───────────────────────────────────────────────────────
// The reproduction's steps, after the fix, against a real API and PostgreSQL
// 16: Roof Material end to end (defined, placed with the PO's Roof Material
// table, required on Add Premises, typed, refused when blank on that form only
// with the form kept, listed on Step 3, shown on the Premise page, edited,
// shown as a list column, filled by an import column), a unit field and a
// service-point field typed on Add Premises and shown on the Units tab, an
// asset field typed on Edit asset and shown on Asset detail and the Assets
// list, and a zero-fields tenant whose Add Premises draws nothing new.
//
// Expects a freshly seeded database (`manage.py seed_demo`) with no custom
// fields yet.   node 10-scripts/cr161_w3b_metering_assets_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8874) OUT (screenshot folder) CHROME
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8874";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "/tmp/cr161-w3b-shots";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
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
  const path = `${OUT}/cf3b_${name}.png`;
  await p.screenshot({ path, fullPage: true });
  ok(`screenshot ${name} is not blank`, statSync(path).size > 20000, `${statSync(path).size} bytes`);
}
async function signIn(browser, email, tenant) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(40000);
  await p.goto(`${BASE}/${tenant}/signin`);
  await p.fill("#signin-email", email);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}
function apiOf(p, tenant) {
  return (method, path, body) =>
    p.evaluate(
      async ([m, u, b]) => {
        const r = await fetch(u, {
          method: m,
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: b === undefined ? undefined : JSON.stringify(b),
        });
        let j = null;
        try {
          j = await r.json();
        } catch {
          /* empty body */
        }
        return { status: r.status, body: j };
      },
      [method, `/api/${tenant}${path}`, body],
    );
}
const main = (p) => p.locator("main");

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  const p = await signIn(browser, "dana@brazosbendutilities.com", T);
  const api = apiOf(p, T);

  console.log("1 · define the fields and place them (the PO's Roof Material table)");
  const define = async (payload, placement) => {
    const made = await api("POST", "/settings/custom-fields", payload);
    ok(`define ${payload.label}`, made.status === 201, JSON.stringify(made.body).slice(0, 200));
    const placed = await api("PUT", `/settings/custom-fields/${made.body.id}/placement`, { placement });
    ok(`place ${payload.label}`, placed.status === 200, JSON.stringify(placed.body).slice(0, 300));
    return made.body;
  };
  const roof = await define(
    { label: "Roof Material", entity: "premises", data_type: "select", options: ["Metal", "Tile", "Shingle"], is_required: true },
    { NEW_CONNECTION_PREMISE: "input", S16: "input", PREMISE_EDIT: "input", PREMISE_PAGE: "view" },
  );
  await define({ label: "Gate code", entity: "units", data_type: "text" }, { S16: "input", UNIT_EDIT: "input", PREMISE_UNITS: "view" });
  await define({ label: "Valve location", entity: "service_points", data_type: "text" }, { S16: "input", PREMISE_UNITS: "view" });
  await define({ label: "Warranty provider", entity: "assets", data_type: "text" }, { S51: "input", ASSET_EDIT: "input", S50: "view", S49: "view" });

  await p.goto(`${BASE}/${T}/settings/reference-data/reference-data?list=custom_fields`, { waitUntil: "networkidle" });
  await p.locator("tr", { hasText: "Roof Material" }).first().locator('button[aria-label="Placement"]').click();
  const dialog = p.locator('[role="dialog"]');
  await dialog.waitFor();
  const dialogText = (await dialog.innerText()).replace(/\s+/g, " ");
  for (const screen of ["New connection · Property", "Add premises", "Edit premise", "Premise page", "Premises list"]) {
    ok(`Placement offers "${screen}"`, dialogText.includes(screen), dialogText.slice(0, 400));
  }
  await shot(p, "after_settings_placement_roof_material");
  await p.keyboard.press("Escape");

  console.log("2 · Add Premises: Step 2 draws the fields; blank required is refused on that form only");
  await p.goto(`${BASE}/${T}/premises/new?mode=single_premise&step=2`, { waitUntil: "networkidle" });
  ok("Step 2 draws Roof Material", (await main(p).innerText()).includes("Roof Material"));
  ok("Step 2 draws Gate code (first unit)", (await main(p).innerText()).includes("Gate code"));
  ok("Step 2 draws Valve location per service", (await main(p).locator("text=Valve location").count()) >= 1);
  await p.fill("#address_line", "4410 Roofline Dr");
  await p.locator('[id="custom_data.gate_code"]').fill("4471");
  await p.locator('[id="custom_data.valve_location"]').first().fill("Front curb");
  await shot(p, "after_add_premises_step2");
  await p.getByRole("button", { name: "Continue" }).click();
  await p.waitForTimeout(800);
  await p.getByRole("button", { name: /Create premise/ }).click();
  await p.waitForTimeout(2500);
  const roofBox = p.locator('[id="custom_data.roof_material"]');
  ok("refused: back on Step 2 with Roof Material marked", (await roofBox.getAttribute("aria-invalid")) === "true");
  ok("form kept: gate code still typed", (await p.locator('[id="custom_data.gate_code"]').inputValue()) === "4471");
  ok("form kept: address still typed", (await p.inputValue("#address_line")) === "4410 Roofline Dr");
  await shot(p, "after_add_premises_required_refused");
  // The refused press leaves `Retry` where the action row was (WizardFrame
  // keeps every value); fixing the one box and retrying is the clerk's path.
  await roofBox.selectOption("Metal");
  await p.getByRole("button", { name: /Retry/ }).click();
  await p.waitForTimeout(3000);
  const found = await api("GET", "/premises?q=4410%20Roofline&per=5");
  const created = (found.body.results ?? [])[0];
  ok("premise created with Roof Material Metal", created?.custom_data?.roof_material === "Metal", JSON.stringify(created?.custom_data));

  console.log("2b · the happy path: Step 3 Review lists what Step 2 collected");
  await p.goto(`${BASE}/${T}/premises/new?mode=single_premise&step=2`, { waitUntil: "networkidle" });
  await p.fill("#address_line", "4412 Roofline Dr");
  await p.locator('[id="custom_data.roof_material"]').selectOption("Shingle");
  await p.locator('[id="custom_data.gate_code"]').fill("1200");
  await p.getByRole("button", { name: "Continue" }).click();
  await p.waitForTimeout(1000);
  const review = (await main(p).innerText()).replace(/\s+/g, " ");
  ok("Step 3 lists Roof Material Shingle", /Roof Material\s*Shingle/.test(review), review.slice(-600));
  ok("Step 3 lists Gate code 1200", /Gate code\s*1200/.test(review));
  await shot(p, "after_add_premises_step3_review");
  await p.getByRole("button", { name: /Create premise/ }).click();
  await p.waitForTimeout(3000);

  console.log("3 · Premise page shows it; Units tab shows the unit and service-point answers");
  await p.goto(`${BASE}/${T}/premises/${created.id}`, { waitUntil: "networkidle" });
  const page = (await main(p).innerText()).replace(/\s+/g, " ");
  ok("Premise page shows Roof Material Metal", /Roof Material\s*Metal/.test(page));
  await p.getByText("Roof Material").first().scrollIntoViewIfNeeded();
  await shot(p, "after_premise_page");
  await p.goto(`${BASE}/${T}/premises/${created.id}?tab=units`, { waitUntil: "networkidle" });
  const units = (await main(p).innerText()).replace(/\s+/g, " ");
  ok("Units tab has a Gate code column with 4471", /gate code/i.test(units) && units.includes("4471"));
  ok("Units tab has a Valve location column naming the service", /valve location/i.test(units) && /Electric: Front curb/.test(units), units.slice(-300));
  await shot(p, "after_premise_units_tab");

  console.log("4 · Edit premise changes it");
  await p.goto(`${BASE}/${T}/premises/${created.id}`, { waitUntil: "networkidle" });
  await p.getByRole("button", { name: "Edit", exact: true }).first().click();
  await p.locator('[role="dialog"] [id="custom_data.roof_material"]').selectOption("Tile");
  await shot(p, "after_edit_premise");
  await p.getByRole("button", { name: "Save premise" }).click();
  await p.waitForTimeout(2500);
  const after = await api("GET", `/premises/${created.id}`);
  ok("edit saved Tile", after.body.custom_data?.roof_material === "Tile", JSON.stringify(after.body.custom_data));
  await p.goto(`${BASE}/${T}/premises/${created.id}`, { waitUntil: "networkidle" });
  ok("Premise page now reads Tile", /Roof Material\s*Tile/.test((await main(p).innerText()).replace(/\s+/g, " ")));

  console.log("5 · Premises list: Not shown by default, a column once switched on");
  await p.goto(`${BASE}/${T}/premises?q=Roofline`, { waitUntil: "networkidle" });
  ok("no Roof Material column while Not shown", !(await main(p).locator("th", { hasText: "Roof Material" }).count()));
  await api("PUT", `/settings/custom-fields/${roof.id}/placement`, {
    placement: { NEW_CONNECTION_PREMISE: "input", S16: "input", PREMISE_EDIT: "input", PREMISE_PAGE: "view", S14: "view" },
  });
  await p.goto(`${BASE}/${T}/premises?q=Roofline`, { waitUntil: "networkidle" });
  ok("Roof Material column shown", (await main(p).locator("th", { hasText: "Roof Material" }).count()) > 0);
  ok("the column reads Tile", (await main(p).innerText()).includes("Tile"));
  await shot(p, "after_premises_list_column");

  console.log("6 · a premises import fills Roof Material from its column, judged by the field");
  const csv = "ADDR1,CITY,ROOF\n500 Import Rd,Katy,Shingle\n501 Import Rd,Katy,Purple\n502 Import Rd,Katy,\n";
  const run = await api("POST", "/imports", { target: "premises", source_kind: "file", file_name: "cf3b_roof.csv", content: csv });
  ok("import extracted", run.status === 201 || run.status === 200, JSON.stringify(run.body).slice(0, 200));
  const runId = run.body.id;
  const tf = await api("POST", `/imports/${runId}/transform`, {
    mapping: { ADDR1: "address_line", CITY: "city", ROOF: "custom_data.roof_material" },
    row_handling: { drop_exact_duplicates: false, keep_latest_on_key: false, skip_rows_missing_required: false },
  });
  ok("mapping accepted although Roof Material is required", tf.status === 200, JSON.stringify(tf.body).slice(0, 300));
  const val = await api("POST", `/imports/${runId}/validate`, { write_mode: "insert" });
  ok("validated", val.status === 200, JSON.stringify(val.body).slice(0, 300));
  const load = await api("POST", `/imports/${runId}/load`, { write_mode: "insert", approved: true });
  ok("loaded", load.status === 200 || load.status === 202, JSON.stringify(load.body).slice(0, 300));
  const imported = await api("GET", "/premises?q=Import%20Rd&per=10");
  const byAddr = Object.fromEntries((imported.body.results ?? []).map((r) => [r.address_line, r]));
  ok("Shingle row loaded with its answer", byAddr["500 Import Rd"]?.custom_data?.roof_material === "Shingle", JSON.stringify(byAddr["500 Import Rd"]?.custom_data));
  ok("Purple row refused (not a choice)", byAddr["501 Import Rd"] === undefined);
  ok("blank-cell row loaded, required never blocks an import", byAddr["502 Import Rd"] !== undefined && !byAddr["502 Import Rd"].custom_data?.roof_material);
  await p.goto(`${BASE}/${T}/premises/${byAddr["500 Import Rd"]?.id}`, { waitUntil: "networkidle" });
  ok("imported premise page shows Shingle", /Roof Material\s*Shingle/.test((await main(p).innerText()).replace(/\s+/g, " ")));
  await p.getByText("Roof Material").first().scrollIntoViewIfNeeded();
  await shot(p, "after_imported_premise_page");

  console.log("7 · an asset field: Edit asset types it, Asset detail and the list show it");
  const assets = await api("GET", "/assets?per=1");
  const asset = assets.body.results[0];
  await p.goto(`${BASE}/${T}/assets/${asset.id}/edit`, { waitUntil: "networkidle" });
  await p.locator('[id="custom_data.warranty_provider"]').fill("Acme Meters");
  await shot(p, "after_edit_asset");
  await p.getByRole("button", { name: "Save asset" }).click();
  await p.waitForTimeout(3000);
  const mainText = (await main(p).innerText()).replace(/\s+/g, " ");
  ok("Asset detail shows Warranty provider", /Warranty provider\s*Acme Meters/.test(mainText), mainText.slice(-400));
  await p.getByText("Acme Meters").first().scrollIntoViewIfNeeded();
  await shot(p, "after_asset_detail");
  await p.goto(`${BASE}/${T}/assets?q=${encodeURIComponent(asset.asset_no)}`, { waitUntil: "networkidle" });
  ok("Assets list has the Warranty provider column", (await main(p).locator("th", { hasText: "Warranty provider" }).count()) > 0);
  await shot(p, "after_assets_list_column");

  console.log("8 · a tenant with no fields: Add Premises is unchanged");
  const q = await signIn(browser, "priya@sixriversutility.com", "sixrivers");
  await q.goto(`${BASE}/sixrivers/premises/new?mode=single_premise&step=2`, { waitUntil: "networkidle" });
  const other = await q.locator("main").innerText();
  ok("no custom section and no Brazos field on another utility", !other.includes("Roof Material") && !other.includes("fields\n"));
  await shot(q, "after_zero_fields_tenant_add_premises");
} finally {
  await browser.close();
}
console.log(`\n${pass} passed, ${failures.length} failed`);
if (failures.length) {
  for (const f of failures) console.log(`  ✗ ${f}`);
  process.exit(1);
}
