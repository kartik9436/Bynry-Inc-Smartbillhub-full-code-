// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-10-06 11 (a) — the late-fee grace is set on the
//          late-fee charge code (DEF-RAT-9816, 2.551.0).
// What it walks, at 1440, signed in as a System Admin:
//   1. Plans & Rates › Charge codes › LATE › Edit — step 1 shows Grace days
//      and Counted in (photo 01), set to 10 business days, Review shows it
//      (photo 02), saved with a date and a reason; the API then serves 10 /
//      business on the code.
//   2. View details › How it bills shows *10 business days* (photo 03).
//   3. A plan whose late fee is LATE shows *Grace: 10 business days* under the
//      late fee's When, on its details (photo 04) and on Edit › Charges
//      (photo 05).
//   4. Puts the grace back to what it read before, so a re-run starts clean.
//
//   BASE=http://127.0.0.1:<spa> TENANT=<slug> EMAIL=<admin> PASSWORD=<pw> SHOTS=<dir> \
//   E2E_CHROMIUM_EXECUTABLE=<chrome> node 10-scripts/grace_on_late_fee_code_walk.mjs
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
const require = createRequire(`${REPO}/07-frontend/package.json`);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:5811";
const TENANT = process.env.TENANT ?? "mvimatrix";
const EMAIL = process.env.EMAIL ?? "marcus@cedarford.example";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const SHOTS = process.env.SHOTS ?? `${REPO}/08-qa/screens/grace-on-late-fee-code-2026-10-06`;
mkdirSync(SHOTS, { recursive: true });

const results = [];
function check(name, pass, detail = "") {
  results.push({ name, pass, detail });
  console.log(`  ${pass ? "PASS" : "FAIL"}  ${name}${detail ? " — " + detail : ""}`);
}

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_EXECUTABLE });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);
await page.goto(`${BASE}/${TENANT}/signin`);
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
  page.click('button[type="submit"]'),
]);
const api = (p) => `${BASE}/api/${TENANT}${p}`;
async function get(p) {
  const r = await ctx.request.get(api(p));
  if (!r.ok()) throw new Error(`GET ${p} → ${r.status()} ${(await r.text()).slice(0, 300)}`);
  return r.json();
}
async function shot(name) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
}
async function cont() {
  await page.getByRole("button", { name: /^Continue/ }).click();
  await page.waitForTimeout(500);
}
async function editLate(days, mode, reason, from, photos) {
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${late.id}/edit`);
  const box = page.getByLabel(/^Grace days/);
  await box.waitFor();
  if (photos) await shot("01-late-step1-grace-fields");
  await box.fill(String(days));
  await page.getByLabel(/^Counted in/).selectOption(mode);
  await cont();
  await cont();
  if (photos) await shot("02-late-review-grace");
  await page.getByLabel(/^Effective from/).fill(from);
  await page.getByLabel(/^Reason/).fill(reason);
  await page.getByRole("button", { name: /^Save change/ }).click();
  await page.waitForTimeout(1500);
}

const list = await get("/charges?q=LATE&per=50");
let late = list.results.find((row) => row.code === "LATE");
late = await get(`/charges/${late.id}`);
const before = { days: late.grace_days, mode: late.grace_mode };
check("LATE serves its seeded grace", before.days !== null && before.mode !== null, JSON.stringify(before));

await editLate(10, "business", "Board moved the late-fee grace to ten business days", "2026-11-01", true);
const after = await get(`/charges/${late.id}`);
check("the save put 10 business days on the code", after.grace_days === 10 && after.grace_mode === "business", `${after.grace_days} ${after.grace_mode}`);

await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${late.id}`);
await page.getByText("10 business days").first().waitFor();
await shot("03-late-view-details-how-it-bills");
check("View details shows 10 business days", await page.getByText("10 business days").first().isVisible());

const plans = await get("/plans?per=50");
let shown = 0;
for (const row of plans.results) {
  const sections = await get(`/plans/${row.id}`).catch(() => null);
  const lateRow = sections?.charge_codes?.find((code) => code.late_fee);
  if (!lateRow || lateRow.ref.code !== "LATE") continue;
  await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${row.id}?tab=charges`);
  const line = page.getByText("Grace: 10 business days").first();
  // Not fatal: a missing line is a FAIL row with its photo, not a crash
  // (the first run found the plan read's normaliser dropping `grace`).
  await line.waitFor({ timeout: 10000 }).catch(() => undefined);
  await shot("04-plan-details-late-fee-grace");
  check(`plan ${row.name} shows the code's grace on its details`, await line.isVisible());
  // The Charge codes panel's own Edit opens the plan form on its Charges step.
  await page.locator('[data-plan-section="charges"]').getByText(/^Edit$/).first().click();
  await page.locator('[data-plan-step="charges"]').first().waitFor({ timeout: 15000 }).catch(() => undefined);
  await page.waitForTimeout(800);
  const formLine = page.locator('[data-plan-step="charges"] [data-grace]').first();
  const seen = (await formLine.count()) > 0 ? await formLine.textContent() : null;
  await shot("05-plan-edit-charges-late-fee-grace");
  check(`plan ${row.name} Edit › Charges shows the code's grace`, seen === "Grace: 10 business days", String(seen));
  shown += 1;
  break;
}
check("a plan whose late fee is LATE was walked", shown === 1);

// Put it back so the walk can be re-run.
await editLate(before.days, before.mode, "Walk restores the grace it found", "2026-11-01", false);
const restored = await get(`/charges/${late.id}`);
check("grace restored", restored.grace_days === before.days && restored.grace_mode === before.mode, `${restored.grace_days} ${restored.grace_mode}`);

writeFileSync(`${SHOTS}/results.json`, JSON.stringify(results, null, 1));
const failed = results.filter((row) => !row.pass).length;
console.log(`${results.length - failed} PASS / ${failed} FAIL`);
await browser.close();
process.exit(failed === 0 ? 0 : 1);
