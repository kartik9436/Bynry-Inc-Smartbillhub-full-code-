// ── Trace ──────────────────────────────────────────────
// PO GIS review 2026-10-07, Lane D — gaps 9, 12, 13, 14 and Lane B's leftovers
// (a) the Preview with no layer, (b) "Nightly parcel check", (c) two "Parcel"s.
// Screens: S14/S15 premises & units, S16 Add premises, S142 the connector pages
// ───────────────────────────────────────────────────────
//
// One walk, run once per WORLD the lane sets up beforehand (a shell step, see
// the CR-171 section for Lane D):
//
//   WORLD=nogis    — no Esri ArcGIS connection (the demo's own state)
//   WORLD=working  — an Esri ArcGIS connection at the recorded City, working
//   WORLD=broken   — the same connection, its last test failed
//   WORLD=nolayer  — the same connection with no service address
//
//   BASE=http://127.0.0.1:5471 PHASE=before WORLD=nogis PREMISES=<uuid> UNIT=<uuid> \
//   OUT=08-qa/gis-lane-d-2026-10-07 node 10-scripts/gis_lane_d_screens_walkthrough.mjs
//
// A LOCAL stack only; the script prints every API host it saw.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5471";
const TENANT = process.env.TENANT ?? "brazosbend";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ADMIN = process.env.ADMIN ?? "dana@brazosbendutilities.com";
const CLERK = process.env.CLERK ?? "sam.reyes@sample.test";
const PHASE = process.env.PHASE ?? "before";
const WORLD = process.env.WORLD ?? "nogis";
const PREMISES = process.env.PREMISES;
const UNIT = process.env.UNIT;
const OUT = process.env.OUT ?? "/tmp/gis-lane-d";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });

async function session(email) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.calls = [];
  page.on("response", (r) => {
    const u = new URL(r.url());
    if (u.pathname.includes("/api/")) page.calls.push(`${r.status()} ${r.request().method()} ${u.host}${u.pathname}${u.search}`);
  });
  page.on("pageerror", (e) => console.log("  page error:", e.message));
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return page;
}

const shot = async (page, name, opts = {}) => {
  const file = `${PHASE}-${WORLD}-${name}-1440.png`;
  await page.screenshot({ path: join(OUT, file), fullPage: opts.full ?? false });
  console.log(`  ${file}`);
};
const text = async (page, sel) =>
  (await page.locator(sel).first().innerText().catch(() => "")).replace(/\s+/g, " ").trim();
const factLabels = async (page) =>
  (await page.locator("main").innerText().catch(() => ""))
    .split("\n")
    .filter((line) => /parcel|import reference|on the map|checked against gis|city connection|layer address/i.test(line))
    .slice(0, 12);

const admin = await session(ADMIN);

// ── The property and the unit (gap 9, leftover c) ──────────────────────────
if (PREMISES) {
  await admin.goto(`${BASE}/${TENANT}/premises/${PREMISES}`, { waitUntil: "networkidle" });
  await admin.waitForTimeout(1200);
  console.log(`PREMISES Overview lines: ${JSON.stringify(await factLabels(admin))}`);
  await shot(admin, "premises-overview", { full: true });
}
if (UNIT) {
  await admin.goto(`${BASE}/${TENANT}/premises/units/${UNIT}`, { waitUntil: "networkidle" });
  await admin.waitForTimeout(1200);
  console.log(`UNIT Overview lines: ${JSON.stringify(await factLabels(admin))}`);
  await shot(admin, "unit-overview", { full: true });
}
async function onePremiseDetails(page) {
  await page.goto(`${BASE}/${TENANT}/premises/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: /^continue/i }).first().click();
  await page.waitForTimeout(1200);
}
await onePremiseDetails(admin);
console.log(`ADD PREMISES lines: ${JSON.stringify(await factLabels(admin))}`);
await shot(admin, "add-premises", { full: true });

// The list's edit form — the import reference's own label (leftover c).
await admin.goto(`${BASE}/${TENANT}/premises`, { waitUntil: "networkidle" });
await admin.waitForTimeout(1200);
const edit = admin.getByRole("button", { name: /edit/i }).first();
if (await edit.count()) {
  await edit.click();
  await admin.waitForTimeout(800);
  console.log(`EDIT PREMISES dialog: ${JSON.stringify(await factLabels(admin))}`);
  await shot(admin, "edit-premises");
  await admin.keyboard.press("Escape");
}

// ── The connector pages (gap 13, leftover a and b) ─────────────────────────
await admin.goto(`${BASE}/${TENANT}/settings/integrations/geocoder_census`, { waitUntil: "networkidle" });
await admin.waitForTimeout(1200);
await shot(admin, "census-card");
const connect = admin.locator("main button, main a").filter({ hasText: /^\s*Connect\s*$/ }).first();
if (WORLD === "nogis" && (await connect.count())) {
  await connect.click();
  await admin.waitForTimeout(800);
  // The recorded Census host by default (this sandbox cannot reach the real
  // one); SERVICE=https://geocoding.geo.census.gov from a machine that can.
  const service = process.env.SERVICE ?? "https://geocoding.geo.census.example";
  await admin.locator("main input").first().fill(service);
  await shot(admin, "census-connect-form");
  const save = admin.getByRole("button", { name: /save and test/i }).first();
  await save.click();
  await admin.waitForTimeout(2500);
  console.log(`CENSUS after Connect: ${await text(admin, '[role="alert"], [role="dialog"]')}`);
  await shot(admin, "census-after-connect");
  const test = admin.getByRole("button", { name: /^test/i }).first();
  if (await test.count()) {
    await test.click().catch(() => undefined);
    await admin.waitForTimeout(800);
    const field = admin.locator('[role="dialog"] input').first();
    if (await field.count()) await field.fill("4600 Silver Hill Rd, Washington, DC 20233");
    const go = admin.locator('[role="dialog"]').getByRole("button", { name: /test/i }).last();
    if (await go.count()) await go.click().catch(() => undefined);
    await admin.waitForTimeout(4000);
    console.log(`CENSUS after Test: ${(await admin.locator("main").innerText()).match(/The geocoder[^\n]*/)?.[0] ?? "(no geocoder sentence)"}`);
    await shot(admin, "census-after-test");
  }
}

if (WORLD !== "nogis") {
  await admin.goto(`${BASE}/${TENANT}/settings/integrations/gis_esri`, { waitUntil: "networkidle" });
  await admin.waitForTimeout(1500);
  const body = await admin.locator("main").innerText();
  console.log(`ESRI page says Nightly: ${/nightly/i.test(body)} · Parcel check: ${/parcel check/i.test(body)}`);
  await shot(admin, "esri-connection", { full: true });
  const preview = admin.locator("[data-run-preview]").first();
  if (await preview.count()) {
    await preview.click();
    await admin.waitForTimeout(4000);
    const answered = admin.calls.filter((c) => c.includes("/reconcile")).slice(-1)[0] ?? "(no reconcile call)";
    console.log(`PREVIEW answered: ${answered}`);
    console.log(`PREVIEW says: ${await text(admin, '[data-reconcile-result], [role="alert"]')}`);
    await shot(admin, "esri-preview");
  }
}

// ── The Billing Clerk (gap 14) ─────────────────────────────────────────────
if (WORLD === "working") {
  const clerk = await session(CLERK);
  await onePremiseDetails(clerk);
  const street = clerk.locator("#address_line").first();
  if (await street.count()) {
    await street.fill("1408 Pec");
    await clerk.waitForTimeout(3000);
    const search = clerk.calls.filter((c) => c.includes("address-search")).slice(-1)[0] ?? "(no search call)";
    console.log(`CLERK address search answered: ${search}`);
    console.log(`CLERK candidates: ${await clerk.getByRole("button", { name: /^use/i }).count()}`);
    await shot(clerk, "clerk-address-search", { full: true });
  }
  console.log(`CLERK API hosts: ${[...new Set(clerk.calls.map((c) => c.split(" ")[2].split("/")[0]))].join(", ")}`);
}

console.log(`API hosts called: ${[...new Set(admin.calls.map((c) => c.split(" ")[2].split("/")[0]))].join(", ")}`);
const failures = admin.calls.filter((c) => /^5\d\d /.test(c));
console.log(`5xx answers: ${failures.join(" | ") || "none"}`);
await browser.close();
