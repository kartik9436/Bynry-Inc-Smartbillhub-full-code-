// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-010 (S9 History) · S10 plan detail
// Defects:  DEF-RAT-10032 · DEF-RAT-10033 · DEF-RAT-10031
// ───────────────────────────────────────────────────────
// Browser proof at 1440 for the three PO rulings of 2026-10-09:
//   1. Plans & Rates → History lists a tax change and a discount change in words
//      (filtered by Tax, then by Discount, then unfiltered);
//   2. a plan's Audit → Changes underneath shows its tax's change in words;
//   3. a plan's versions table reads Minimum bill: $10.00 → $12.00, and a copy
//      saved before the fix reads "Terms not recorded".
//
//   node 10-scripts/def_rat_10032_history_taxes_discounts_walk.mjs <base> <out-dir> <tax-plan-id> <versions-plan-id> <legacy-plan-id>
//   e.g. http://127.0.0.1:5837/brazosbend /tmp/shots <uuid> <uuid> <uuid>
//
// Fails (exit 1) when an expected sentence is missing, a uuid is on screen, or
// any API request leaves 127.0.0.1 (never walk against the live API).
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, "..", "07-frontend", "package.json"));
const { chromium } = require("playwright");

const [BASE, OUT, TAX_PLAN, VERSIONS_PLAN, LEGACY_PLAN] = process.argv.slice(2);
mkdirSync(OUT, { recursive: true });
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
let failed = false;
page.on("request", (request) => {
  const url = new URL(request.url());
  if (url.hostname !== "127.0.0.1" && url.pathname.includes("/api")) {
    console.log(`OFF-HOST REQUEST ${request.url()}`);
    failed = true;
  }
});

async function shot(name, expected) {
  await page.waitForTimeout(3500);
  const text = await page.locator("main").innerText();
  for (const sentence of expected) {
    const ok = text.includes(sentence);
    console.log(`${name}: ${ok ? "found" : "MISSING"} "${sentence}"`);
    if (!ok) failed = true;
  }
  if (UUID.test(text)) {
    console.log(`${name}: UUID ON SCREEN`);
    failed = true;
  }
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

await page.goto(`${BASE}/signin`);
await page.fill("#signin-email", "dana@brazosbendutilities.com");
await page.fill("#signin-password", "S3cure!passw0rd");
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin")),
  page.getByRole("button", { name: /^Sign in/ }).click(),
]);

await page.goto(`${BASE}/plans-rates/history`);
await shot("1-history-all", ["Tax · City Utility Franchise Fee 2%", "2.00%", "6.00%", "Discount · Senior 65+ discount"]);
await page.goto(`${BASE}/plans-rates/history?f.entity_type=tax`);
await shot("2-history-filter-tax", ["Tax · City Utility Franchise Fee 2%", "Rate:", "2.00%", "6.00%"]);
await page.goto(`${BASE}/plans-rates/history?f.entity_type=discount`);
await shot("3-history-filter-discount", ["Discount · Senior 65+ discount", "15.00%", "20.00%"]);
await page.goto(`${BASE}/plans-rates/plans/${TAX_PLAN}?tab=audit&a.f.kind=underneath`);
await shot("4-plan-audit-tax-change", ["Tax · City Utility Franchise Fee 2%", "Rate: 2.00% → 6.00%", "Discount · SENIOR65 · Senior 65+ discount"]);
await page.goto(`${BASE}/plans-rates/plans/${VERSIONS_PLAN}`);
await shot("5-plan-versions-minimum-bill", ["Minimum bill: $10.00 → $12.00"]);
await page.goto(`${BASE}/plans-rates/plans/${LEGACY_PLAN}`);
await shot("6-plan-versions-old-copy-marked", ["Terms not recorded"]);

await browser.close();
console.log(failed ? "WALK FAILED" : "WALK PASSED");
process.exit(failed ? 1 : 0);
