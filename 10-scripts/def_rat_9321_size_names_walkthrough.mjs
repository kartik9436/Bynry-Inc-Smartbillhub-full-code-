// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-9321 — a connection size printed as its internal CODE
//           (`W-58`, `W-1`) instead of the utility's name (`Water 5/8"`).
//           PO 2026-10-03 on Ottumwa's BASE-W-FIRE edit, step 2, at 2.455.0.
//           DEF-RAT-9322 — a code holding one size twice (every class AND one
//           class) read as the same size twice, and Save would flatten it.
// Rules:    12-governance/22-product-maintenance-process.md · law 6.
// ───────────────────────────────────────────────────────
// Walks, at 1440, on a PRIVATE database seeded by seed_demo + load_sample_data
// (brazosbend) plus two charge codes the lane's seed writes (BASE-W-FIRE priced
// by meter size, BASE-W-DUP with W-1 for every class and W-1 for Commercial):
//   1. Charge code Edit BASE-W-FIRE › step 2 Pricing (closed selects — a
//      native select cannot be photographed open, so each select's OPTION
//      texts are written to the JSON beside the shot)
//   2. the same wizard › Review
//   3. View details › Prices and › History
//   4. Edit BASE-W-DUP › step 2 (the two-rows-one-size case)
//   5. an asset with a size › Overview (Measurement panel)
//   6. that asset's premises › Assets tab
// Every visible text is checked for a raw size code and the count is printed.
//
//   BASE=http://127.0.0.1:5199 SHOTS=08-qa/size-labels-2026-10-03 PREFIX=after \
//   E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//   node 10-scripts/def_rat_9321_size_names_walkthrough.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:5199";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS ?? "08-qa/size-labels-2026-10-03";
const PREFIX = process.env.PREFIX ?? "after";
mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("    console: " + m.text()); });
await page.goto(`${BASE}/${TENANT}/signin`);
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
  page.click('button[type="submit"]'),
]);
const api = async (p) => (await ctx.request.get(`${BASE}/api/${TENANT}${p}`)).json();

const sizes = (await api("/lookups/service_size_classes?per=200")).results;
const CODE_RE = new RegExp(`(^|[^A-Za-z0-9-])(${sizes.map((s) => s.code.replace(/[-]/g, "\\-")).join("|")})(?![0-9A-Za-z-])`, "g");
const codesIn = (text) => [...text.matchAll(CODE_RE)].map((m) => m[2]);

const report = {};
async function shoot(name, root = "main") {
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${SHOTS}/${PREFIX}-${name}.png`, fullPage: true });
  const text = await page.locator(root).first().innerText();
  const selects = await page.$$eval('select[aria-label="Size"]', (els) =>
    els.map((el) => ({ value: el.value, shown: el.selectedOptions[0]?.textContent ?? "", options: [...el.options].map((o) => o.textContent) })),
  );
  const found = codesIn(text);
  report[name] = { codesOnScreen: found, selects };
  console.log(`${name}: ${found.length} raw size code(s) on screen${found.length ? " — " + [...new Set(found)].join(", ") : ""}`);
  for (const s of selects) console.log(`   select value=${s.value} shows "${s.shown}" · options: ${s.options.join(" | ")}`);
}

const charges = (await api("/charges?per=200")).results;
const fire = charges.find((c) => c.code === "BASE-W-FIRE");
const dup = charges.find((c) => c.code === "BASE-W-DUP");

// 1–2. Edit BASE-W-FIRE
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${fire.id}/edit`);
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForSelector('[data-array="charge-price-rows"]');
await shoot("01-base-w-fire-edit-pricing");
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForSelector('[data-step="review"]');
await shoot("02-base-w-fire-edit-review");

// 3. View details
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${fire.id}?tab=prices`);
await page.waitForSelector('[data-array="charge-prices"]');
await shoot("03-base-w-fire-details-prices");

// 4. BASE-W-DUP
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${dup.id}/edit`);
await page.getByRole("button", { name: "Continue" }).click();
await page.waitForSelector('[data-array="charge-price-rows"]');
await shoot("04-base-w-dup-edit-pricing");
const dupRows = await page.$$eval('[data-array="charge-price-rows"] tbody tr', (rows) => rows.map((r) => r.innerText.replace(/\s+/g, " ").trim()));
report.dupRows = dupRows;
console.log("   dup rows:", JSON.stringify(dupRows));
if (process.env.SAVE_DUP === "1") {
  // The round trip: W-1 Commercial $18.00 → $19.00 from 11/01/2026, saved on
  // PostgreSQL. Before the fix the payload posted Commercial as every class.
  const amounts = page.locator('[data-array="charge-price-rows"] input[data-cell^="amount-"]');
  await amounts.nth(2).fill(process.env.DUP_AMOUNT ?? "19.00");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForSelector('[data-step="review"]');
  const from = page.getByLabel(/^Effective from/).first();
  await from.click();
  await from.fill("2026-11-01");
  await from.press("Tab");
  await page.getByLabel(/^Reason/).first().fill("DEF-RAT-9322 walk");
  await shoot("04b-base-w-dup-review-before-save");
  await page.getByRole("button", { name: "Save change" }).click();
  await page.waitForTimeout(2500);
  await shoot("04c-base-w-dup-after-save");
  const after = (await api(`/charges/${dup.id}`)).prices.filter((p) => !p.killed || p.effective_to === null);
  report.dupPricesAfterSave = after.map((p) => `${p.size_class}|${p.customer_class}|${p.amount_display}|${p.effective_from}→${p.effective_to}|killed=${p.killed}`);
  console.log("   dup prices after save:", JSON.stringify(report.dupPricesAfterSave));
}
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${dup.id}?tab=prices`);
await page.waitForSelector('[data-array="charge-prices"]');
await shoot("05-base-w-dup-details-prices");

// 5–6. An asset with a size, and its premises
const assets = (await api("/assets?per=200&filters[tab]=meters")).results ?? [];
const sized = assets.find((a) => a.size_class) ?? (await api("/assets?per=200")).results.find((a) => a.size_class);
if (sized) {
  await page.goto(`${BASE}/${TENANT}/assets/${sized.id}`);
  await page.waitForTimeout(1500);
  await shoot("06-asset-detail-measurement");
} else console.log("   no sized asset found");

// 7. a premises whose Assets tab holds a sized asset
const premises = (await api("/premises?per=60")).results ?? [];
let premisesWalked = false;
for (const one of premises) {
  const held = (await api(`/assets?f.premises_id=${one.id}&per=200`)).results ?? [];
  if (!held.some((a) => a.size_class)) continue;
  await page.goto(`${BASE}/${TENANT}/premises/${one.id}?tab=assets`);
  await page.waitForTimeout(2000);
  await shoot("07-premises-assets-tab");
  premisesWalked = true;
  break;
}
if (!premisesWalked) console.log("   no premises with a sized asset in the first 60 — premises tab not walked");

// 8. a route's edit wizard, step 3 (the meter table has a Size column)
const routes = (await api("/routes?per=50")).results ?? [];
const route = routes.find((r) => (r.premises ?? r.premises_count ?? 0) > 0) ?? routes[0];
if (route) {
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/routes-cycles/routes/${route.id}/edit`);
  await page.waitForTimeout(1500);
  for (let i = 0; i < 2; i++) {
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(1200);
  }
  await page.waitForSelector('[data-rcw="table"]', { timeout: 15000 }).catch(() => undefined);
  await page.waitForTimeout(1500);
  await shoot("08-route-wizard-meters");
  const sizeCells = await page.$$eval('[data-rcw="table"] tbody tr', (rows) => rows.slice(0, 8).map((r) => r.innerText.replace(/\s+/g, " ").trim()));
  report.routeRows = sizeCells;
  console.log("   route rows:", JSON.stringify(sizeCells));
} else console.log("   no route — route wizard not walked");

writeFileSync(`${SHOTS}/${PREFIX}-measure.json`, JSON.stringify(report, null, 2));
await browser.close();
