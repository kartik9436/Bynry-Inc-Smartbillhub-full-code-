#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9840 (PO report 2026-10-06) under PO ruling (a) of the same
//          day — one work order per service, one asset per panel tagged to the
//          unit, the bill on the sum of installed kW.
// What:    Kyle Mark applies on the portal for 9840 Sunline Way, Unit 1, taking
//          water and solar. The clerk approves into New Connect. On step 3,
//          Unit 1 takes Solar three times (1 kW + 10 kW + 10 kW): the Solar row
//          reads "3 panels · 21 kW", Panels 2 and 3 are sub-rows whose Work
//          order, Completes and Occupancy show the Solar row's, greyed, with
//          "Same as Solar row". Step 5 lists the three panel assets; Create;
//          the build's Units tab lists three asset numbers with their sizes;
//          the ONE solar work order is completed and accepted, the unit's
//          Solar service is activated, and all three assets read Installed.
//          Photographed at 1440.
// Usage:   W_BASE=http://127.0.0.1:5848 W_OUT=<dir> node 10-scripts/nct03_new_connect_solar_pieces_walk.mjs
//          (a local stack only — never the live site). The walk world must
//          sell solar and hold a published per-unit solar template; the walk
//          creates the template itself through the Work API when none exists.
// ───────────────────────────────────────────────────────
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.W_BASE ?? "http://127.0.0.1:5848").replace(/\/$/, "");
const TENANT = process.env.W_TENANT ?? "brazosbend";
const OUT = process.env.W_OUT ?? "/tmp/nct03-walk";
const EMAIL = process.env.W_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.W_PASSWORD ?? "S3cure!passw0rd";
// The technician who closes the job (the walk world gives them PASSWORD).
const TECH_EMAIL = process.env.W_TECH_EMAIL ?? "d.ortiz@sample.test";
// The unit label the build makes (a range of 1 to 1 with no prefix reads "1").
const UNIT = process.env.W_UNIT ?? "1";
mkdirSync(OUT, { recursive: true });

let fails = 0;
const check = (ok, name, detail = "") => {
  if (!ok) fails += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + String(detail).slice(0, 300) : ""}`);
};
const note = (text) => console.log(`        ${text}`);

function chrome() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  const found = readdirSync(root)
    .filter((n) => n.startsWith("chromium"))
    .flatMap((n) => ["chrome-linux/chrome", "chrome-linux64/chrome"].map((s) => join(root, n, s)))
    .filter(existsSync);
  return found[0];
}

async function call(page, method, path, body) {
  return page.evaluate(
    async ({ method, url, body }) => {
      const res = await fetch(url, {
        method,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ?? "",
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return { status: res.status, body: await res.json().catch(() => null) };
    },
    { method, url: `/api/${TENANT}${path}`, body },
  );
}

async function shoot(page, name, selector) {
  await page.waitForTimeout(400);
  const file = join(OUT, `${name}.png`);
  if (selector) {
    await page.locator(selector).first().screenshot({ path: file });
  } else {
    await page.screenshot({ path: file, fullPage: true });
  }
  console.log(`      shot ${file}`);
}

const browser = await chromium.launch({ executablePath: process.env.CHROME ?? chrome(), args: ["--no-sandbox"] });

// ── 0 · the clerk signs in; a published per-unit solar template exists ─────
const ctx = await browser.newContext({ viewport: { width: Number(process.env.W_WIDTH ?? 1440), height: 1200 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);
const templates = await call(page, "GET", "/work/templates?per=200");
let solarTemplate = (templates.body?.results ?? []).find(
  (row) => row.name === "Solar installation" && row.version > 0,
);
if (solarTemplate === undefined) {
  const draft = await call(page, "POST", "/work/templates", {
    name: "Solar installation",
    service: "solar",
    scope: "per_unit",
    sequence: 1,
    crew_size: 2,
    est_duration_minutes: 240,
    is_gate: true,
  });
  check(draft.status === 201 || draft.status === 200, "a per-unit solar template is drafted", `${draft.status} ${JSON.stringify(draft.body).slice(0, 200)}`);
  const published = await call(page, "POST", `/work/templates/${draft.body?.id}/publish`, { change_note: "walk" });
  check(published.status === 200 || published.status === 201, "and published", `${published.status} ${JSON.stringify(published.body).slice(0, 200)}`);
  solarTemplate = published.body;
}
note(`template: ${solarTemplate?.template_no} ${solarTemplate?.name} v${solarTemplate?.version}`);

// ── 1 · Kyle Mark applies on the portal for water and solar ────────────────
const guest = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const gp = await guest.newPage();
gp.setDefaultTimeout(25000);
await gp.goto(`${BASE}/${TENANT}/portal`, { waitUntil: "domcontentloaded" });
const token = randomUUID();
const start = new Date(Date.now() + 21 * 86400000).toISOString().slice(0, 10);
const street = `${9840 + Math.floor(Math.random() * 100)} Sunline Way`;
const saved = await call(gp, "PUT", `/portal/public/applications/${token}`, {
  address_as_given: street,
  address_city_as_given: "Austin",
  address_postal_code_as_given: "78701",
  service_codes: ["water", "solar"],
  applicant_kind: "person",
  first_name: "Kyle",
  last_name: "Mark",
  email: "kyle.mark@example.test",
  phone: "(512) 555-0128",
  date_of_birth: "1990-03-14",
  requested_start: start,
  account_type_code: "residential",
});
check(saved.status === 200 || saved.status === 201, "Kyle Mark's application saved", `${saved.status} ${JSON.stringify(saved.body).slice(0, 200)}`);
const sent = await call(gp, "POST", `/portal/public/applications/${token}/submit`, { paperless: false });
check(sent.status === 200 || sent.status === 201, "Kyle Mark's application sent", `${sent.status} ${JSON.stringify(sent.body).slice(0, 200)}`);
const requestId = sent.body?.request_id;

// ── 2 · the clerk approves it into a new connection ───────────────────────
await call(page, "POST", `/service-requests/${requestId}/customer-link`, { customer_id: null });
await page.goto(`${BASE}/${TENANT}/requests/${requestId}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.getByRole("button", { name: "Approve", exact: true }).first().click();
await page.waitForTimeout(800);
await page.locator("[data-outcome-picker] button", { hasText: /new connection/i }).first().click().catch(() => undefined);
await page.waitForTimeout(800);
await page.locator('[role="dialog"] button').last().click();
await page.waitForURL(/connections\/new\?build=/, { timeout: 30000 }).catch(() => undefined);
check(/connections\/new\?build=/.test(page.url()), "Approve opens New Connect on the raised build", page.url());
const buildId = new URL(page.url()).searchParams.get("build");
await page.waitForTimeout(3000);
await page.fill("#nc_ssn", "412-55-1234").catch(() => undefined);

const forward = () => page.locator('[data-wizard="actions"] button').last();
await forward().click();
await page.waitForTimeout(2500);

// ── 3 · step 2 — single-family home, the residential plan ──────────────────
const pick = async (sel, prefer) => {
  const opts = await page
    .$$eval(`${sel} option`, (ns) => ns.filter((o) => !o.disabled && o.value !== "").map((o) => ({ v: o.value, t: o.textContent })))
    .catch(() => []);
  if (opts.length === 0) return null;
  const chosen = opts.find((o) => prefer && (o.v === prefer || (o.t ?? "").includes(prefer))) ?? opts[0];
  await page.selectOption(sel, chosen.v);
  return chosen.t;
};
note(`premise type: ${await pick("#nc_premise_type", "single_family")}`);
await page.waitForTimeout(500);
note(`plan: ${await pick("#nc_plan", "Residential")}`);
await page.waitForTimeout(2000);
// Solar must be among the address's services (the request asked for it).
const solarBox = page.locator('input[type="checkbox"][value="solar"], [data-service="solar"] input[type="checkbox"]').first();
if ((await solarBox.count()) > 0 && !(await solarBox.isChecked())) await solarBox.check().catch(() => undefined);
await shoot(page, "2-step2");
await forward().click();
await page.waitForTimeout(3000);

// ── 4 · step 3 — Unit 1 takes three solar panels ───────────────────────────
// One unit, then sizes: the common selection first, then Apply to all.
if ((await page.locator("#nc_from").inputValue()) === "") await page.fill("#nc_from", "1");
if ((await page.locator("#nc_to").inputValue()) === "") await page.fill("#nc_to", "1");
await page.waitForTimeout(800);
const empties = await page.$$eval("main select", (ns) =>
  ns
    .map((n, i) => ({ i, v: n.value, opts: [...n.options].filter((o) => o.value !== "" && !o.disabled).length, cell: n.getAttribute("data-cell") }))
    .filter((x) => x.v === "" && x.opts > 0 && x.cell !== "service")
    .map((x) => x.i),
);
for (const index of empties) {
  const sel = page.locator("main select").nth(index);
  const first = await sel.evaluate((n) => [...n.options].find((o) => o.value !== "" && !o.disabled)?.value ?? "");
  if (first) await sel.selectOption(first).catch(() => undefined);
}
await page.getByRole("button", { name: "Apply to all" }).first().click().catch(() => undefined);
await page.waitForTimeout(800);

const units = page.locator('[data-array="units-and-service-points"]').first();
// The Solar SERVICE row: the row whose own Service box reads solar.
await page.$$eval('select[data-cell="service"]', (ns) => {
  const hit = ns.find((s) => s.value === "solar");
  hit?.closest("tr")?.setAttribute("data-walk-solar-row", "");
});
const solarRow = () => page.locator("tr[data-walk-solar-row]").first();
// Solar's own size on its row: 1 kW.
await solarRow().locator('select[data-cell="size"]').selectOption({ label: "Solar panel 1 kW" }).catch(async () => {
  const labels = await solarRow().locator('select[data-cell="size"] option').allInnerTexts();
  note(`solar sizes offered: ${labels.join(" | ")}`);
});
// Two more panels: + Add row, then Solar on the new row — twice.
for (let n = 0; n < 2; n += 1) {
  await page.getByRole("button", { name: "+ Add row" }).first().click();
  await page.waitForTimeout(600);
  if (n === 0) await shoot(page, "3-step3-added-row", '[data-array="units-and-service-points"]');
  // The new row is the one whose Service box is still empty.
  const index = await page.$$eval('select[data-cell="service"]', (ns) => {
    const empty = ns.map((s, i) => ({ i, v: s.value })).filter((x) => x.v === "");
    return empty.length === 0 ? -1 : empty[empty.length - 1].i;
  });
  note(`empty service box: ${index}`);
  await page.locator('select[data-cell="service"]').nth(index).selectOption("solar");
  await page.waitForTimeout(500);
}
const pieces = units.locator("tr[data-editable-nested]");
check((await pieces.count()) === 2, "two extra panels are SUB-ROWS of the Solar row", `${await pieces.count()} nested`);
for (let n = 0; n < 2; n += 1) {
  await pieces.nth(n).locator('select[data-cell="size"]').selectOption({ label: "Solar panel 10 kW" });
  await page.waitForTimeout(300);
}
const pieceNames = await pieces.locator("[data-piece-of]").allInnerTexts();
check(
  pieceNames[0] === "↳ Panel 2 · Solar panel 10 kW" && pieceNames[1] === "↳ Panel 3 · Solar panel 10 kW",
  "they read ↳ Panel 2 and ↳ Panel 3 with their sizes",
  pieceNames.join(" | "),
);
const summary = await units.locator("[data-pieces-summary]").first().innerText().catch(() => "");
check(summary === "3 panels · 21 kW", "the Solar row reads 3 panels · 21 kW", summary);
for (let n = 0; n < 2; n += 1) {
  const row = pieces.nth(n);
  const order = row.locator('select[data-cell="work-order"]');
  const orderText = await order.locator("option:checked").innerText().catch(() => "");
  check(
    (await order.isDisabled()) && orderText.includes("Solar installation"),
    `Panel ${n + 2}'s Work order shows the Solar row's job, greyed`,
    orderText,
  );
  check((await row.locator("[data-same-as]").innerText()) === "Same as Solar row", `Panel ${n + 2} says Same as Solar row`);
  const completes = row.locator('input[data-cell="completes"]');
  check((await completes.isDisabled()) && (await completes.isChecked()), `Panel ${n + 2}'s Completes is the Solar row's tick, greyed`);
  const occupancy = row.locator('select[data-cell="occupancy"]');
  const occText = await occupancy.locator("option:checked").innerText().catch(() => "");
  check((await occupancy.isDisabled()) && occText !== "" && occText !== "—", `Panel ${n + 2}'s Occupancy shows the unit's, greyed`, occText);
}
await shoot(page, "3-step3-solar-sub-rows", '[data-array="units-and-service-points"]');

// ✕ on the Solar row asks first; Cancel keeps all three.
await solarRow().locator("button[aria-label^='Remove row']").first().click();
await page.waitForTimeout(400);
const dialog = page.getByRole("alertdialog");
const dialogText = (await dialog.innerText().catch(() => "")).replace(/\s+/g, " ");
check(dialogText.includes(`Remove Solar from ${UNIT}?`) && dialogText.includes("Removes 3 panels · 21 kW too."), "✕ on the Solar row asks first", dialogText);
await shoot(page, "3-step3-remove-asks", '[role="alertdialog"]');
await dialog.getByRole("button", { name: /Cancel/i }).click().catch(() => undefined);
await page.waitForTimeout(400);
check((await pieces.count()) === 2, "Cancel keeps all three panels");

await forward().click();
await page.waitForTimeout(2500);
// Step 4 (charges) → step 5 (review).
await forward().click();
await page.waitForTimeout(3000);

// ── 5 · Review lists three panel assets ────────────────────────────────────
const unitsGroup = page.locator('[data-review-group="units"]').first();
await unitsGroup.locator("summary").first().click().catch(() => undefined);
await page.waitForTimeout(500);
const planned = (await unitsGroup.locator("[data-planned-asset]").allInnerTexts()).map((s) => s.trim());
const solarPlanned = planned.filter((line) => line.includes("Solar panel"));
check(
  solarPlanned.length === 3 &&
    solarPlanned.filter((l) => l.endsWith(`Solar panel 1 kW · ${UNIT}`)).length === 1 &&
    solarPlanned.filter((l) => l.endsWith(`Solar panel 10 kW · ${UNIT}`)).length === 2,
  "Review lists three panel assets: 1 kW, 10 kW, 10 kW on Unit 1",
  planned.join(" | "),
);
await shoot(page, "5-review-assets", '[data-review-group="units"]');

const createButton = forward();
note(`review button: ${await createButton.innerText().catch(() => "")}`);
await createButton.click();
await page.waitForTimeout(7000);
await shoot(page, "5-after-create");

// ── 6 · the build record: three asset numbers, one solar order ────────────
const activation = await call(page, "GET", `/connections/${buildId}/activation`);
const solar = (activation.body?.rows ?? []).find((row) => row.service === "solar");
check(solar !== undefined && solar.assets.length === 3, "the build holds three solar assets on Unit 1", JSON.stringify(solar?.assets?.map((a) => [a.asset_no, a.size_class, a.status]) ?? activation.body).slice(0, 300));
check(solar?.assets?.every((a) => a.status === "inventory"), "all three are In stock until the job is done");
await page.goto(`${BASE}/${TENANT}/connections/${buildId}?tab=units`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const pointCell = page.locator(`[data-service-point="${solar?.id}"]`);
const lines = await pointCell.locator("[data-asset-no]").allInnerTexts();
check(
  lines.length === 3 && lines.filter((l) => l.includes("Solar panel 10 kW")).length === 2 && lines.some((l) => l.includes("Solar panel 1 kW")),
  "the Units tab lists each asset number with its size",
  lines.join(" | "),
);
await shoot(page, "6-build-units-before", '[data-table="build-units"]');

const detail = await call(page, "GET", `/connections/${buildId}`);
const orders = (detail.body?.work_orders ?? []).filter((o) => (o.service?.code ?? o.service) === "solar");
check(orders.length === 1, "ONE work order for Unit 1's solar", JSON.stringify(orders.map((o) => o.order_no)));

// ── 7 · the technician completes it; the clerk accepts and activates ──────
// Only the technician the job was GIVEN to may close it (`BR-MET-110`), so the
// office assigns it, the technician signs in and reports it done, and the
// office accepts it — the three real doors.
// W_TECH_ID names TECH_EMAIL's technician row (the walk world's setup prints it).
const tech = { id: process.env.W_TECH_ID, name: TECH_EMAIL };
note(`technician: ${tech?.name ?? tech?.full_name ?? JSON.stringify(techs.body).slice(0, 120)}`);
const field = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const fp = await field.newPage();
fp.setDefaultTimeout(30000);
await fp.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
// A technician signs in on the FIELD app (`BR-WRK-043`), so through its door.
const techSession = await call(fp, "POST", "/auth/session", { email: TECH_EMAIL, password: PASSWORD, surface: "mobile" });
note(`technician signs in on the field app: ${techSession.status}`);
for (const order of orders) {
  const given = await call(page, "POST", `/work-orders/${order.id}/assignments`, { act: "assign", technician_id: tech?.id });
  note(`assign ${order.order_no}: ${given.status} ${JSON.stringify(given.body).slice(0, 160)}`);
  const took = await call(fp, "POST", `/work/mobile/jobs/${order.id}/accept`, {});
  note(`technician takes ${order.order_no}: ${took.status} ${JSON.stringify(took.body).slice(0, 120)}`);
  const done = await call(fp, "POST", `/work/mobile/jobs/${order.id}/sync`, {
    items: [{ key: randomUUID(), kind: "close", seq: 1, payload: { outcome: "passed", field_data: {} } }],
  });
  const closed = (done.body?.items ?? [])[0];
  check(done.status === 200 && closed?.result !== "refused", `the technician completes ${order.order_no} on the field app`, `${done.status} ${JSON.stringify(done.body).slice(0, 300)}`);
  const accepted = await call(page, "POST", `/work-orders/${order.id}/accept`, {});
  check(accepted.status === 200, `the office accepts ${order.order_no}`, `${accepted.status} ${JSON.stringify(accepted.body).slice(0, 200)}`);
}
const ready = await call(page, "GET", `/connections/${buildId}/activation`);
const solarReady = (ready.body?.rows ?? []).find((row) => row.service === "solar");
note(`solar row ready=${solarReady?.ready} open=${JSON.stringify(ready.body?.open_orders ?? []).slice(0, 200)}`);
const activated = await call(page, "POST", `/connections/${buildId}/activate`, {
  service_ids: [solarReady?.id],
  acknowledge_open_orders: true,
});
check(activated.status === 200, "Unit 1's Solar is activated", `${activated.status} ${JSON.stringify(activated.body).slice(0, 300)}`);
const after = await call(page, "GET", `/connections/${buildId}/activation`);
const solarAfter = (after.body?.rows ?? []).find((row) => row.service === "solar");
check(
  solarAfter?.assets?.length === 3 && solarAfter.assets.every((a) => a.status === "active" && a.install_date),
  "all THREE panels are Installed, dated",
  JSON.stringify(solarAfter?.assets?.map((a) => [a.asset_no, a.status, a.install_date])),
);
await page.goto(`${BASE}/${TENANT}/connections/${buildId}?tab=units`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const linesAfter = await page.locator(`[data-service-point="${solar?.id}"] [data-asset-no]`).allInnerTexts();
check(linesAfter.length === 3 && linesAfter.every((l) => l.includes("Installed")), "the Units tab reads Installed on all three", linesAfter.join(" | "));
await shoot(page, "7-build-units-installed", '[data-table="build-units"]');

console.log(`\n${fails === 0 ? "ALL PASS" : `${fails} FAIL`}`);
await browser.close();
process.exit(fails === 0 ? 0 : 1);
