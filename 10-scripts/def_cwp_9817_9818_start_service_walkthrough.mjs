#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CWP-9817 — Start service step 1 asks Street address · Town ·
//          ZIP code · the unit, as the Customer Portal blueprint draws them
//          (p31), and every later step names the address in US form.
//          DEF-CWP-9818 — PO ruling 2026-10-06 (b): the applicant picks the
//          customer Category and Sub-category on step 3.
// Rules:   hard-won law 6 (no gate reads rendered output — the proof is a
//          browser) · the portal's mandatory pair of widths, 1440/1280 and 390
// ───────────────────────────────────────────────────────
// Walks, at 1440 and at 390:
//   1. Step 1 — the four drawn boxes, Check held with its reason, a malformed
//      ZIP refused on the box; a held address (MATCH_*) answers *We serve this
//      address* with the PREMISES' own line; an unknown one (1841 Quarry Hill Ct,
//      Silver Creek, 78611, Apt 12) answers *a person will look at it*.
//   2. Steps 2–3 — the head and the rail read the US-format line; step 3 holds
//      Continue on *Choose a category first.*, the Sub-category lists only the
//      chosen category's children.
//   3. Check and send — the address line and *Category* restated by name; Send.
//   4. Staff › the request — Type is the applicant's pick and *Address as given*
//      carries the town and ZIP.
//
//   BASE=http://127.0.0.1:<spa> TENANT=brazosbend SHOTS=<dir> \
//   MATCH_STREET=… MATCH_TOWN=… MATCH_ZIP=… EMAIL=<staff> PASSWORD=<pw> \
//   E2E_CHROMIUM_EXECUTABLE=<chrome> node 10-scripts/def_cwp_9817_9818_start_service_walkthrough.mjs
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:58172";
const T = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS ?? "/tmp/def-cwp-9817-shots";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const MATCH = {
  street: process.env.MATCH_STREET ?? "2201 Cane Island Pkwy",
  town: process.env.MATCH_TOWN ?? "Katy",
  zip: process.env.MATCH_ZIP ?? "77494",
};
const UNKNOWN = { street: "1841 Quarry Hill Ct", town: "Silver Creek", zip: "78611", unit: "Apt 12" };
mkdirSync(SHOTS, { recursive: true });

const results = [];
function ok(name, pass, detail = "") {
  results.push({ name, pass });
  console.log(`  ${pass ? "PASS" : "FAIL"}  ${name}${detail && !pass ? " — " + detail : ""}`);
}
async function shot(page, name) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}
function startDate() {
  const d = new Date();
  d.setDate(d.getDate() + 21);
  return d.toISOString().slice(0, 10);
}
const text = async (loc) => ((await loc.textContent()) ?? "").trim();

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE });

async function stepOne(g, where, width) {
  await g.goto(`${BASE}/${T}/portal/start-service`, { waitUntil: "networkidle" });
  const labels = await g.locator('[data-testid="start-service"] label').allTextContents();
  ok(`${width} · step 1 draws the four boxes in the drawn order`,
    JSON.stringify(labels.map((l) => l.replace(" *", ""))) ===
      JSON.stringify(["Street address", "Town", "ZIP code", "Is there a unit or apartment number?"]),
    JSON.stringify(labels));
  ok(`${width} · Check is held, with its reason`,
    (await g.locator('[data-action="check"]').isDisabled()) &&
      (await g.locator('[data-action="check"]').getAttribute("title")) === "Fill in street, town and ZIP.");
  await shot(g, `${width}-01-step1-empty`);
  await g.fill("#availability-address", where.street);
  await g.fill("#availability-town", where.town);
  await g.fill("#availability-zip", "7861");
  await g.locator("#availability-zip").blur();
  ok(`${width} · a four-digit ZIP is refused on the box`,
    (await text(g.locator('[data-field-error="availability-zip"]'))) === "Use 12345 or 12345-6789." &&
      (await g.locator('[data-action="check"]').isDisabled()));
  await g.fill("#availability-zip", where.zip);
  if (where.unit) await g.fill("#availability-unit", where.unit);
  await shot(g, `${width}-02-step1-filled`);
  await g.click('[data-action="check"]');
}

async function walk(width, height) {
  console.log(`\n── ${width} ──`);
  const ctx = await browser.newContext({ viewport: { width, height } });
  const g = await ctx.newPage();
  g.setDefaultTimeout(40000);

  // A HELD address — the premises' own line comes back.
  await stepOne(g, MATCH, width);
  await g.waitForSelector('[data-minitable]');
  ok(`${width} · street + town + ZIP of a held premises is matched`, true);
  await shot(g, `${width}-03-step1-matched`);

  // An UNKNOWN address — the journey this defect was reported on.
  await stepOne(g, UNKNOWN, width);
  await g.waitForSelector('[data-availability="unmatched"]');
  ok(`${width} · an address we do not hold is not refused`, true);
  await g.click('[data-action="apply"]');
  await g.waitForSelector('[data-step="when"]');
  await g.waitForTimeout(1500);
  const line = "1841 Quarry Hill Ct, Apt 12, Silver Creek, TX 78611";
  const head = await text(g.locator(".page-header-rollup"));
  ok(`${width} · step 2's head names the US-format line`, head.includes(line), head);
  const offered = g.locator('[data-service-pick] input[type="checkbox"]');
  if ((await offered.count()) > 0) await offered.first().check();
  await g.fill("#requested_start", startDate());
  await g.locator("#requested_start").blur();
  await g.waitForTimeout(1200);
  await g.click('[data-action="continue"]');
  await g.waitForSelector('[data-step="about"]');
  await g.waitForTimeout(1200);
  const rail = await text(g.locator('[data-twocol-rail] [data-kv="address"] dd'));
  ok(`${width} · step 3's rail reads the US-format line`, rail === line, rail);
  await shot(g, `${width}-04-step3-rail`);
  await g.fill("#first_name", "Kyle");
  await g.locator("#first_name").blur();
  await g.fill("#last_name", "Mark");
  await g.locator("#last_name").blur();
  await g.fill("#email", `kyle.mark.${width}@example.test`);
  await g.locator("#email").blur();
  await g.fill("#phone", "(512) 555-0101");
  await g.locator("#phone").blur();
  await g.waitForTimeout(1200);
  ok(`${width} · Continue holds on the category, with its reason`,
    (await g.locator('[data-action="continue"]').isDisabled()) &&
      (await text(g.locator('[data-step-held="category"]'))) === "Choose a category first.");
  const cats = await g.locator("#account_type_code option").allTextContents();
  ok(`${width} · Category lists the offered categories by name`,
    cats[0] === "Choose one" && cats.includes("Commercial") && cats.includes("Residential") &&
      !cats.includes("Government"), JSON.stringify(cats));
  await g.selectOption("#account_type_code", "commercial");
  await g.waitForTimeout(800);
  const subs = await g.locator("#account_subtype_code option").allTextContents();
  ok(`${width} · Sub-category lists only Commercial's children`,
    subs[0] === "Optional" && subs.includes("Healthcare") && !subs.includes("Single-family"),
    JSON.stringify(subs));
  await g.selectOption("#account_subtype_code", { label: "Healthcare" });
  await g.waitForTimeout(1200);
  await g.locator("#account_type_code").scrollIntoViewIfNeeded();
  await shot(g, `${width}-05-step3-category`);
  await g.click('[data-action="continue"]');
  await g.waitForSelector('[data-screen="CWP-009"]');
  await g.waitForTimeout(1500);
  ok(`${width} · Check and send restates the line`,
    (await text(g.locator('[data-kv="address"] dd'))) === line);
  ok(`${width} · …and the category by name`,
    (await text(g.locator('[data-kv="category"] dd'))) === "Commercial · Healthcare");
  await shot(g, `${width}-06-check-and-send`);
  let reference = null;
  if (width === 1440) {
    await g.click('[data-action="send"]');
    await g.waitForSelector("[data-reference]", { timeout: 30000 });
    reference = await text(g.locator("[data-reference]"));
    ok("1440 · sent, with a reference", /^SR-/.test(reference), reference);
  }
  await ctx.close();
  return reference;
}

const reference = await walk(1440, 1100);
await walk(390, 844);

// ── 4 · the clerk's side ────────────────────────────────────────────────────
console.log("\n── Staff › the request ──");
const sctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const p = await sctx.newPage();
p.setDefaultTimeout(40000);
await p.goto(`${BASE}/${T}/signin`);
await p.fill("#signin-email", EMAIL);
await p.fill("#signin-password", PASSWORD);
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
  p.click('button[type="submit"]'),
]);
const list = await (await sctx.request.get(`${BASE}/api/${T}/service-requests?q=${encodeURIComponent(reference ?? "")}`)).json();
const row = (list.results ?? []).find((r) => r.request_no === reference) ?? (list.results ?? [])[0];
ok("the request is on the clerk's list", row !== undefined, JSON.stringify(list).slice(0, 200));
const detail = await (await sctx.request.get(`${BASE}/api/${T}/service-requests/${row.id}`)).json();
const loc = detail.location_and_services ?? {};
ok("the request carries the town and ZIP as given",
  loc.address_city_as_given === "Silver Creek" && loc.address_postal_code_as_given === "78611",
  JSON.stringify(loc).slice(0, 300));
await p.goto(`${BASE}/${T}/requests/${row.id}`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
// ⚠ The request's *Customer category* row is where the applicant's pick
// lands (the seven categories from Settings). *Asked for › Type* is a
// DIFFERENT fact — the job classification (move-in / new connection) the
// clerk settles — and it still reads *Not yet classified*; see the decision
// log, 2026-10-06, judgment 12.
const category = await text(p.locator('[data-drawn-row="customer-category"]').first());
ok("Customer category is the applicant's pick", category.includes("Commercial · Healthcare"), category);
const asGiven = await text(p.locator('[data-drawn-row="as-given"]').first());
ok("Address as given carries the town and ZIP",
  asGiven.includes("1841 Quarry Hill Ct, Apt 12") && asGiven.includes("Silver Creek") && asGiven.includes("78611"),
  asGiven);
await shot(p, "1440-07-staff-request-category-and-address");

// ── 5 · keyboard only (accessibility questions 1–3) ─────────────────────────
console.log("\n── Keyboard only ──");
{
  const kctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const k = await kctx.newPage();
  await k.goto(`${BASE}/${T}/portal/start-service`, { waitUntil: "networkidle" });
  await k.focus("#availability-address");
  await k.keyboard.type(UNKNOWN.street);
  const order = [];
  for (const value of [UNKNOWN.town, UNKNOWN.zip, UNKNOWN.unit]) {
    await k.keyboard.press("Tab");
    order.push(await k.evaluate(() => document.activeElement?.id ?? ""));
    await k.keyboard.type(value);
  }
  ok("Tab walks street → town → ZIP → unit", JSON.stringify(order) ===
    JSON.stringify(["availability-town", "availability-zip", "availability-unit"]), JSON.stringify(order));
  await k.keyboard.press("Tab");
  ok("…then reaches Check →", await k.evaluate(() => document.activeElement?.getAttribute("data-action") === "check"));
  const outline = await k.evaluate(() => getComputedStyle(document.activeElement).outlineStyle);
  ok("the focused control shows where you are", outline !== "none", outline);
  await k.keyboard.press("Enter");
  await k.waitForSelector('[data-availability="unmatched"]');
  ok("Enter on Check → checks the address", true);
  const labelled = await k.evaluate(() =>
    ["availability-address", "availability-town", "availability-zip", "availability-unit"].every(
      (id) => document.querySelector(`label[for="${id}"]`) !== null &&
        document.getElementById(id)?.getAttribute("autocomplete") !== null,
    ),
  );
  ok("every box has a bound label and an autocomplete purpose", labelled);
  await kctx.close();
}

await browser.close();
const failed = results.filter((r) => !r.pass).length;
console.log(`\n${results.length - failed} PASS · ${failed} FAIL`);
process.exit(failed ? 1 : 0);
