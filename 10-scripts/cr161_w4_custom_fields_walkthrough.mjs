#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W4 — customers, work orders, readings, routes and
//          areas carry the utility's own fields
// Rules:   BR-TEN-046 (as amended 2026-10-02) · BR-TEN-048 · BR-TEN-052 ·
//          hard-won law 6 (no gate reads rendered output, so the proof is a
//          browser)
// ───────────────────────────────────────────────────────
// One field per record type, defined in Settings, typed on its Input screen and
// read back on its View screen; and one reading imported with the field as a
// column. The worked example put to the PO: *Seal number = S-2207* on a
// reading.
//
// Against a real API and a real PostgreSQL 16 database seeded with
// `seed_demo` + `load_sample_data --tenant brazosbend`, and the front end built
// with `vite build --mode wolocal` and served by `07-frontend/server.mjs`.
//
//   node 10-scripts/cr161_w4_custom_fields_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8896) OUT (screenshot folder)
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8896";
const T = process.env.TENANT || "brazosbend";
const ADMIN = process.env.ADMIN || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/cr161-w4-shots";
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
  const path = `${OUT}/cf4_${name}.png`;
  await p.screenshot({ path, fullPage: true });
  // A blank capture is not a proof: a white 1440×1000 PNG is ~5 KB.
  ok(`screenshot ${name} is not blank`, statSync(path).size > 20000, `${statSync(path).size} bytes`);
}
const CF = `${BASE}/${T}/settings/reference-data/reference-data?list=custom_fields`;
const dialog = (p) => p.locator('[role="dialog"]');
const box = (p, key) => p.locator(`[id="custom_data.${key}"]`);

async function api(p, path) {
  return p.evaluate(async (url) => {
    const r = await fetch(url, { credentials: "include" });
    return { status: r.status, body: await r.json().catch(() => null) };
  }, `${BASE}/api/${T}${path}`);
}
async function apiPost(p, path, body) {
  return p.evaluate(
    async ([url, payload]) => {
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
      const r = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(payload),
      });
      return { status: r.status, body: await r.json().catch(() => null) };
    },
    [`${BASE}/api/${T}${path}`, body],
  );
}

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

/** Define one field in Settings and place it — through the screen. */
async function defineField(p, { label, entity, placements, shotName }) {
  await p.goto(CF, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  if ((await p.locator("tr", { hasText: label }).count()) === 0) {
    const add = p.locator("button", { hasText: "+ Add custom field" }).first();
    if ((await add.count()) === 0) await shot(p, `debug_no_add_${entity}`);
    await add.click();
    await dialog(p).waitFor();
    const appliesTo = await p.locator("#entity option").allTextContents();
    ok(`Applies to offers ${entity}`, appliesTo.includes(entity), JSON.stringify(appliesTo));
    await p.fill("#label", label);
    await p.selectOption("#entity", { label: entity });
    await p.selectOption("#data_type", "text");
    await dialog(p).locator('button[data-variant="primary"]').last().click();
    await p.waitForTimeout(1500);
  }
  await p.goto(CF, { waitUntil: "networkidle" });
  await p.locator("tr", { hasText: label }).first().locator('button[aria-label="Placement"]').click();
  await dialog(p).waitFor();
  const text = (await dialog(p).textContent()) ?? "";
  ok(`${entity}: no screen id printed in Placement`, !/\b(S\d{1,3}|ROUTE_|AREA_|WORK_|READ_|CUSTOMER_)\w*/.test(text), text.slice(0, 200));
  for (const [key, mode] of Object.entries(placements)) {
    await p.selectOption(`#placement-${key}`, mode);
  }
  if (shotName) await shot(p, shotName);
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  await p.waitForTimeout(1500);
  ok(`${entity}: placement saved`, (await dialog(p).count()) === 0);
}

async function viewValue(p, label) {
  const dt = p.locator("dt", { hasText: label }).first();
  await dt.waitFor({ timeout: 30000 });
  // The shell scrolls inside its main column, so a full-page capture is the
  // viewport: bring the answer into it before the screenshot that proves it.
  await dt.scrollIntoViewIfNeeded();
  return ((await dt.locator("xpath=following-sibling::dd[1]").textContent()) ?? "").trim();
}

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  const p = await signIn(browser);

  // ── ROUTES ─────────────────────────────────────────────────────────────
  console.log("\n── Routes: Patrol day, Input on the route form, View on the route page ──");
  await defineField(p, {
    label: "Patrol day",
    entity: "Routes",
    placements: { ROUTE_FORM: "input", ROUTE_PAGE: "view" },
    shotName: "01_settings_route_placement",
  });
  const routes = await api(p, "/routes?per=5");
  const route = (routes.body?.results ?? [])[0];
  ok("a seeded route exists", route !== undefined, JSON.stringify(routes).slice(0, 200));
  await p.goto(`${BASE}/${T}/settings/reference-data/routes-cycles/routes/${route.id}/edit`, {
    waitUntil: "networkidle",
  });
  await box(p, "patrol_day").waitFor({ timeout: 30000 });
  const patrolDay = (await box(p, "patrol_day").inputValue()) === "Tuesday" ? "Friday" : "Tuesday";
  await box(p, "patrol_day").fill(patrolDay);
  await shot(p, "02_route_wizard_patrol_day");
  for (let i = 0; i < 3; i += 1) {
    await p.locator("button", { hasText: /^Continue/ }).last().click();
    await p.waitForTimeout(1200);
  }
  const saved = p.waitForResponse(
    (r) => r.url().includes(`/routes/${route.id}`) && r.request().method() === "PATCH",
    { timeout: 60000 },
  );
  await p.locator("button", { hasText: /✓/ }).last().click();
  const routeSave = await saved;
  ok("route save answers 200", routeSave.status() === 200, String(routeSave.status()));
  ok(
    "the route form sent only the changed answer",
    JSON.stringify(routeSave.request().postDataJSON().custom_data) === JSON.stringify({ patrol_day: patrolDay }),
    JSON.stringify(routeSave.request().postDataJSON().custom_data),
  );
  await p.goto(`${BASE}/${T}/settings/reference-data/routes-cycles/routes/${route.id}`, {
    waitUntil: "networkidle",
  });
  ok(`the route page shows Patrol day = ${patrolDay}`, (await viewValue(p, "Patrol day")) === patrolDay);
  await shot(p, "03_route_page_patrol_day");

  // ── AREAS ──────────────────────────────────────────────────────────────
  console.log("\n── Areas: Warden, Input on the area dialog, a column on the Areas list ──");
  await defineField(p, {
    label: "Warden",
    entity: "Areas",
    placements: { AREA_FORM: "input", AREA_LIST: "view" },
    shotName: "04_settings_area_placement",
  });
  const AREAS = `${BASE}/${T}/settings/reference-data/reference-data?list=areas`;
  await p.goto(AREAS, { waitUntil: "networkidle" });
  await p.locator("button", { hasText: "+ Add entry" }).first().click();
  await dialog(p).waitFor();
  const areaCode = `CF4-${Date.now().toString(36).slice(-4).toUpperCase()}`;
  await p.fill("#code", areaCode);
  await p.fill("#name", `CF4 North ${areaCode}`);
  await box(p, "warden").fill("J. Ortiz");
  await shot(p, "05_area_dialog_warden");
  const areaSave = p.waitForResponse(
    (r) => /\/lookups\/areas/.test(r.url()) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  const areaAnswer = await areaSave;
  ok("area create answers 201", areaAnswer.status() === 201, String(areaAnswer.status()));
  await p.waitForTimeout(1200);
  await p.goto(`${AREAS}&q=CF4`, { waitUntil: "networkidle" });
  const header = p.locator("th", { hasText: "Warden" });
  ok("the Areas list carries a Warden column", (await header.count()) > 0);
  ok("the new area's row reads J. Ortiz", (await p.locator("tr", { hasText: areaCode }).first().textContent())?.includes("J. Ortiz") === true);
  await shot(p, "06_areas_list_warden_column");

  // ── WORK ORDERS ────────────────────────────────────────────────────────
  console.log("\n── Work orders: Crew radio, Input on New / Edit, View on detail ──");
  await defineField(p, {
    label: "Crew radio",
    entity: "Work orders",
    placements: { WORK_NEW: "input", WORK_EDIT: "input", WORK_DETAIL: "view" },
    shotName: "07_settings_work_order_placement",
  });
  const premises = await api(p, "/premises?per=1");
  const premisesId = (premises.body?.results ?? [])[0]?.id;
  ok("a seeded premises exists", Boolean(premisesId));
  await p.goto(`${BASE}/${T}/work/orders/new`, { waitUntil: "networkidle" });
  await p.fill("#new-order-premises", premisesId);
  await p.fill("#new-order-type", "Leak check");
  await box(p, "crew_radio").fill("Ch 4");
  await shot(p, "08_new_work_order_crew_radio");
  await p.locator("button", { hasText: /^Continue/ }).last().click();
  await p.waitForTimeout(800);
  await p.locator("button", { hasText: /^Continue/ }).last().click();
  await p.waitForTimeout(800);
  const raised = p.waitForResponse(
    (r) => /\/work-orders$/.test(r.url()) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await p.locator("button", { hasText: /Raise work order/ }).last().click();
  const raisedAnswer = await raised;
  const order = await raisedAnswer.json().catch(() => ({}));
  ok("the raise answers 200", raisedAnswer.status() === 200, `${raisedAnswer.status()} ${JSON.stringify(order).slice(0, 200)}`);
  ok("the answer travelled", JSON.stringify(raisedAnswer.request().postDataJSON().custom_data) === '{"crew_radio":"Ch 4"}');
  await p.waitForURL((u) => u.pathname.includes("/work/orders/") && !u.pathname.endsWith("/new"), { timeout: 60000 });
  await p.waitForTimeout(1500);
  ok("Work order detail shows Crew radio = Ch 4", (await viewValue(p, "Crew radio")) === "Ch 4");
  await shot(p, "09_work_order_detail_crew_radio");
  await p.goto(`${BASE}/${T}/work/orders/${order.id}/edit`, { waitUntil: "networkidle" });
  await box(p, "crew_radio").waitFor({ timeout: 30000 });
  ok("Edit work order opens with Ch 4", (await box(p, "crew_radio").inputValue()) === "Ch 4");
  await box(p, "crew_radio").fill("Ch 9");
  const edited = p.waitForResponse(
    (r) => r.url().includes(`/work-orders/${order.id}`) && r.request().method() === "PATCH",
    { timeout: 60000 },
  );
  await shot(p, "10_edit_work_order_crew_radio");
  await p.locator('button[data-action="save"]').click();
  const editAnswer = await edited;
  ok("the edit answers 200 and names custom_data", editAnswer.status() === 200 && JSON.stringify(await editAnswer.json()).includes("custom_data"));
  const after = await api(p, `/work-orders/${order.id}`);
  ok("the order now reads Ch 9", after.body?.custom_data?.crew_radio === "Ch 9", JSON.stringify(after.body?.custom_data));

  // ── READINGS ───────────────────────────────────────────────────────────
  console.log("\n── Readings: Seal number, Input on the manual entry, View on reading detail, a column in the import ──");
  await defineField(p, {
    label: "Seal number",
    entity: "Readings",
    placements: { READ_ENTRY: "input", S29: "view" },
    shotName: "11_settings_reading_placement",
  });
  // A meter the quick entry can resolve: the seeded electric meters carry a plan.
  const reads = await api(p, "/reads?per=100");
  const seen = new Set();
  let meterNo = null;
  // The highest register on file per meter, so the counter read goes FORWARD.
  const highest = new Map();
  for (const row of reads.body?.results ?? []) {
    const v = Number(row.current_value ?? 0);
    if (row.meter && v > (highest.get(row.meter) ?? 0)) highest.set(row.meter, v);
  }
  for (const row of reads.body?.results ?? []) {
    if (!row.meter || seen.has(row.meter)) continue;
    seen.add(row.meter);
    const ctx = await api(p, `/reads/quick-context?meter_no=${encodeURIComponent(row.meter)}&read_date=2026-10-01`);
    if (ctx.status === 200 && (ctx.body?.registers?.channels ?? []).length === 1) {
      meterNo = row.meter;
      break;
    }
  }
  ok("a one-register meter exists for the counter case", meterNo !== null);
  await p.goto(`${BASE}/${T}/reads`, { waitUntil: "networkidle" });
  await p.locator("button", { hasText: "+ Add reading" }).first().click();
  await dialog(p).waitFor();
  await p.fill("#meter_no", meterNo);
  await p.locator("#meter_no").blur();
  await p.waitForTimeout(1500);
  await box(p, "seal_number").waitFor({ timeout: 30000 });
  const readDate = dialog(p).locator("#read_date");
  if ((await readDate.inputValue()) === "") await readDate.fill("10/01/2026");
  await p.waitForTimeout(1500);
  const history = await api(p, `/reads?q=${encodeURIComponent(meterNo)}&per=50`);
  const last = Math.max(0, ...(history.body?.results ?? []).map((r) => Number(r.current_value ?? 0)));
  await dialog(p).locator("#reading").fill(String(Math.round(last + 120)));
  await box(p, "seal_number").fill("S-2207");
  await shot(p, "12_manual_reading_seal_number");
  const staged = p.waitForResponse(
    (r) => /\/read-batches$/.test(r.url()) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await dialog(p).locator("button", { hasText: "Post reading" }).last().click();
  const stagedAnswer = await staged;
  const stagedRows = stagedAnswer.request().postDataJSON().rows ?? [];
  ok("the manual entry sent the answer on its row", JSON.stringify(stagedRows[0]?.custom_data) === '{"seal_number":"S-2207"}', JSON.stringify(stagedRows));
  await p.waitForTimeout(4000);
  await shot(p, "13_manual_reading_posted");
  const byMeter = await api(p, `/reads?q=${encodeURIComponent(meterNo)}&per=20`);
  const posted = (byMeter.body?.results ?? []).find((row) => row.custom_data?.seal_number === "S-2207")
    ?? (byMeter.body?.results ?? [])[0];
  await p.goto(`${BASE}/${T}/reads/${posted.id}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  ok("Reading detail shows Seal number = S-2207", (await viewValue(p, "Seal number")) === "S-2207");
  await shot(p, "14_reading_detail_seal_number");

  // The import: the same field as a column of the S28 upload, by its label.
  const importDate = "2026-10-01";
  const csv = `meter_id,read_date,reading,Seal number\n${meterNo},${importDate},${Math.round(last + 240)},S-3301\n`;
  const upload = await apiPost(p, "/read-batches", {
    source_kind: "csv",
    source_detail: "walk_by",
    period_month: "2026-10-01",
    file_name: "cf4_seal_numbers.csv",
    file_content: csv,
  });
  ok("the upload staged (201)", upload.status === 201, `${upload.status} ${JSON.stringify(upload.body).slice(0, 300)}`);
  ok("the mapping reads the Seal number column", upload.body?.mapping?.["custom_data.seal_number"] === "Seal number", JSON.stringify(upload.body?.mapping));
  ok("the mapping names it by its label", upload.body?.mapping_labels?.["custom_data.seal_number"] === "Seal number");
  const batch = await api(p, `/read-batches/${upload.body.id}`);
  const row = (batch.body?.rows ?? [])[0] ?? {};
  ok("the staged row carries S-3301", row.custom_data?.seal_number === "S-3301", JSON.stringify(row.custom_data));
  await p.goto(`${BASE}/${T}/reads/upload`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  await shot(p, "15_reads_upload_screen");

  // ── CUSTOMERS ──────────────────────────────────────────────────────────
  console.log("\n── Customers: Loyalty tier, Input on Edit customer, View in the account header ──");
  await defineField(p, {
    label: "Loyalty tier",
    entity: "Customers",
    placements: { S18: "input", CUSTOMER_EDIT: "input", S21: "view" },
    shotName: "16_settings_customer_placement",
  });
  const customers = await api(p, "/customers?per=5");
  const customer = (customers.body?.results ?? []).find((c) => c.accounts.length > 0);
  ok("a seeded customer with an account exists", customer !== undefined);
  await p.goto(`${BASE}/${T}/customers?q=${encodeURIComponent(customer.display_name)}`, { waitUntil: "networkidle" });
  await p.locator(`[data-testid="customer-edit-${customer.id}"]`).first().click();
  await dialog(p).waitFor();
  await box(p, "loyalty_tier").waitFor({ timeout: 30000 });
  await box(p, "loyalty_tier").fill("Gold");
  await shot(p, "17_edit_customer_loyalty_tier");
  const custSave = p.waitForResponse(
    (r) => r.url().includes(`/customers/${customer.id}`) && r.request().method() === "PATCH",
    { timeout: 60000 },
  );
  await dialog(p).locator('button[type="submit"]').last().click();
  const custAnswer = await custSave;
  ok("Edit customer answers 200", custAnswer.status() === 200, String(custAnswer.status()));
  await p.goto(`${BASE}/${T}/accounts/${customer.accounts[0].id}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  ok("the account header shows Loyalty tier = Gold", (await viewValue(p, "Loyalty tier")) === "Gold");
  await shot(p, "18_account_header_loyalty_tier");
  await p.goto(`${BASE}/${T}/accounts/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  ok("New account's customer step draws Loyalty tier", (await box(p, "loyalty_tier").count()) === 1);
  await shot(p, "19_new_account_customer_field");
} finally {
  await browser.close();
}

console.log(`\n${pass} passed · ${failures.length} failed`);
if (failures.length > 0) {
  for (const f of failures) console.log(`  FAILED: ${f}`);
  process.exit(1);
}
