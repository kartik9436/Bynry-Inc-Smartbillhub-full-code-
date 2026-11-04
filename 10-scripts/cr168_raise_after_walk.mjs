// CR-168-BRC10 round 3, lane RAISE — the AFTER walk at 1440 wide, the same
// states as images 14–20 (raise on units, an asset type chosen, schedule &
// crew, confirm, result, from an account, from an asset).
//
// Run against a PostgreSQL-backed API and the built SPA:
//   BASE=http://127.0.0.1:5521 OUT=08-qa/work-2026-10-04/after node 10-scripts/cr168_raise_after_walk.mjs
// Preconditions: seed_demo + load_sample_data --tenant brazosbend.
//
// WRITES IT MAKES (so a later reader of the database is not misled): ONE job on
// 107 Mill Pond Ln's only unit; SIX jobs on 301 Mill Pond Ln (one per meter,
// W-5040 chosen for Apt 101), assigned to the first candidate; ONE job from
// account AC-2026-00001; ONE job from asset W-5040.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5521";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 2300 } });
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
});
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`=== ${name}.png — ${caption} — ${page.url().replace(BASE, "")}`);
  if (failed.length) console.log("API ERRORS:", JSON.stringify(failed.splice(0)));
}
async function go(path) {
  try {
    await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 });
  } catch { console.log("goto timeout", path); }
  await settle(1500);
}
const api = (path) =>
  page.evaluate(async ([tenant, p]) => {
    const res = await fetch(`/api/${tenant}${p}`, { credentials: "include" });
    return res.ok ? res.json() : { status: res.status };
  }, [TENANT, path]);
const posts = [];
page.on("request", (r) => {
  if (r.method() === "POST" && r.url().includes("bulk-raise")) posts.push(r.postData());
});
page.on("response", async (r) => {
  if (r.request().method() === "POST" && r.url().includes("bulk-raise")) {
    console.log("BULK-RAISE ANSWER", r.status(), (await r.text()).slice(0, 600));
  }
});

async function pickPremises(term, line) {
  await page.getByRole("combobox", { name: "Premises" }).fill(term);
  await page.getByRole("option", { name: new RegExp(line) }).first().click({ timeout: 15000 });
  await settle(1500);
}
async function tick(name) {
  await page.getByRole("checkbox", { name: `Choose ${name}`, exact: true }).check();
}
const cont = () => page.getByRole("button", { name: "Continue", exact: true }).click();

// ── sign in ──────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 14 · raise on units (500 Main St, 31 units) ──────────────────────────
await go("/work/orders/new");
await pickPremises("500 Main", "500 Main St");
await page.getByRole("checkbox", { name: "Choose all on this page" }).check();
await tick("Unit 301");
await page.getByLabel(/^Job type/).selectOption({ label: "Residential Connection" });
await settle(1200);
await page.getByLabel(/^Template/).selectOption({ label: "Tap and service line · v2" });
await settle(1200);
await page.getByLabel(/^Description/).fill("Tap and service line for each new flat.");
await shot("14-orders-raise-job-on-units", "Raise on units — premises picked, units ticked, one job per unit");

// ── ONE job on ONE unit (107 Mill Pond Ln, single-family) ────────────────
if (process.env.SKIP_ONE !== "1") {
await go("/work/orders/new");
await pickPremises("107 Mill", "107 Mill Pond Ln");
await page.getByLabel(/^Job type/).selectOption({ label: "Routine Inspection" });
await settle(1200);
await page.getByLabel(/^Template/).selectOption({ label: "Site inspection & mark-out · v2" });
await settle(800);
await cont(); await settle();
await cont(); await settle();
await shot("17b-raise-one-job-confirm", "One unit, one job — confirm");
await page.getByRole("button", { name: /Raise 1 job ✓/ }).click();
await settle(2500);
await shot("18b-raise-one-job-result", "One job raised");
console.log("POST one-job:", posts.at(-1));
}

// ── 15 · an asset type chosen (301 Mill Pond Ln, 6 flats) ────────────────
await go("/work/orders/new");
await pickPremises("Mill", "301 Mill Pond Ln");
await page.getByRole("checkbox", { name: "Choose all on this page" }).first().check();
await page.getByLabel(/^Job type/).selectOption({ label: "Meter Change" });
await settle(1200);
await page.getByLabel(/^Template/).selectOption({ label: "Meter exchange — residential · v2" });
await settle(2500);
const assets = page.getByTestId("raise-assets");
const names = await assets.locator("tbody tr td:nth-child(2)").allInnerTexts();
console.log("ASSETS LISTED:", JSON.stringify(names));
for (const no of names) {
  const row = assets.locator("tbody tr", { hasText: no });
  if (!(await row.innerText()).includes("Apt 101")) await tick(no.trim());
}
await page.getByLabel(/^Description/).fill("Replace the main water meters.");
await cont(); await settle();
await shot("15-orders-raise-job-an-asset-type-chosen", "Asset type chosen — Choose one on Apt 101, refusal named");

// ── 16 · schedule & crew ─────────────────────────────────────────────────
const first101 = names.find((n) => n.startsWith("W-"));
const apt101 = await assets.locator("tbody tr", { hasText: "Apt 101" }).locator("td:nth-child(2)").allInnerTexts();
console.log("APT 101 ASSETS:", JSON.stringify(apt101), "first:", first101);
await tick(apt101[0].trim());
await cont(); await settle();
await page.getByRole("combobox", { name: "Assign to" }).click();
await settle(1500);
await shot("16-orders-raise-schedule-and-crew", "Schedule & crew — due date picker, visit, assign to (open)");
const assignList = page.getByRole("listbox", { name: "Assign to" });
const opts = await assignList.getByRole("option").allInnerTexts();
console.log("ASSIGN OPTIONS:", JSON.stringify(opts.slice(0, 8)));
const pick = assignList.getByRole("option").filter({ hasNotText: "Nobody" }).first();
if (await pick.count()) await pick.click();
await settle(500);
await cont(); await settle();

// ── 17 · confirm ─────────────────────────────────────────────────────────
await shot("17-orders-raise-confirm", "Confirm — summary, the jobs, EFFECT, Raise 6 jobs ✓");

// ── 18 · result ──────────────────────────────────────────────────────────
await page.getByRole("button", { name: /Raise \d+ jobs ✓/ }).click();
await settle(3000);
await shot("18-orders-raise-result", "Result — N jobs raised, each numbered");
console.log("POST bulk:", posts.at(-1));

// ── 19 · from an account ─────────────────────────────────────────────────
const accounts = await api("/accounts?q=AC-2026-00001");
const accountId = (accounts.results ?? [])[0]?.id;
await go(`/accounts/${accountId}/work-orders/new`);
await page.getByLabel(/^Job type/).selectOption({ label: "Meter Change" });
await settle(1200);
await page.getByLabel(/^Template/).selectOption({ label: "Meter exchange — residential · v2" });
await settle(2500);
const accAssets = await page.getByTestId("raise-assets").locator("tbody tr td:nth-child(2)").allInnerTexts();
console.log("ACCOUNT ASSETS:", JSON.stringify(accAssets));
if (accAssets[0]) await tick(accAssets[0].trim());
await page.getByLabel(/^Description/).fill("Dial fogged — customer called.");
await shot("19-orders-raise-from-an-account", "From the account — filled");
await cont(); await settle(); await cont(); await settle();
await page.getByRole("button", { name: /Raise 1 job ✓/ }).click();
await settle(2500);
await shot("19b-raise-from-account-result", "From the account — one job raised");

// ── 20 · from an asset ───────────────────────────────────────────────────
const found = await api("/assets?q=W-5040");
const assetId = (found.results ?? []).find((r) => r.asset_no === "W-5040")?.id;
await go(`/assets/${assetId}/work-orders/new`);
await page.getByLabel(/^Job type/).selectOption({ label: "Meter Change" });
await settle(1200);
const tpl = page.getByLabel(/^Template/);
console.log("ASSET TEMPLATES:", JSON.stringify(await tpl.locator("option").allInnerTexts()));
await tpl.selectOption({ index: 1 });
await page.getByLabel(/^Description/).fill("Dial fogged — exchange it.");
await shot("20-orders-raise-from-an-asset", "From the asset — filled, three steps");
await cont(); await settle(); await cont(); await settle();
await page.getByRole("button", { name: /Raise 1 job ✓/ }).click();
await settle(2500);
await shot("20b-raise-from-asset-result", "From the asset — one job raised");
console.log("POST asset:", posts.at(-1));

await browser.close();
