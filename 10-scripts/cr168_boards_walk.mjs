// CR-168-BRC10 §30, lane BOARDS — the walk at 1440 wide: the At risk tab next
// to Orders, D. Ortiz's daily job limit edited to 6 on his page, D. Ortiz over
// it on the Schedule board, and the Asset age rule leaving a warehouse meter
// alone.
//
// Run against a PostgreSQL-backed API and the built SPA (`node server.mjs`):
//   BASE=http://127.0.0.1:5221 OUT=08-qa/work-2026-10-04/after node 10-scripts/cr168_boards_walk.mjs
// Preconditions: seed_demo + load_sample_data --tenant brazosbend, then
// `10-scripts/cr168_boards_walk_prep.py` (Ortiz's limit at 7 and seven jobs
// tomorrow; AST-04413 installed, AST-04412/14 on the shelf; one sweep).
//
// WRITES IT MAKES: one PATCH of D. Ortiz's daily job limit, 7 → 6.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5221";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
});
page.on("request", (r) => {
  if (r.url().includes("/api/") && r.method() !== "GET") console.log("WRITE", r.method(), r.url().replace(BASE, ""), r.postData() ?? "");
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
  } catch {
    console.log("goto timeout", path);
  }
  await settle(1500);
}
const api = (path) =>
  page.evaluate(
    async ([tenant, p]) => {
      const res = await fetch(`/api/${tenant}${p}`, { credentials: "include" });
      return res.ok ? res.json() : { status: res.status };
    },
    [TENANT, path],
  );

// ── sign in ──────────────────────────────────────────────────────────────
await go("/signin");
await page.getByLabel(/email/i).first().fill(EMAIL);
await page.getByLabel(/password/i).first().fill(PASSWORD);
await page.getByRole("button", { name: /sign in/i }).first().click();
await settle(3000);

// ── (1) At risk is its own tab, right after Orders ───────────────────────
await go("/work/orders");
const tabs = await page.locator("[data-tab]").evaluateAll((els) => els.map((e) => e.getAttribute("data-tab")));
console.log("WORK TABS:", JSON.stringify(tabs));
await page.locator('[data-tab="at-risk"]').first().click();
await settle(2000);
console.log("AT RISK URL:", page.url().replace(BASE, ""));
console.log("AT RISK FACT:", JSON.stringify(await page.locator("[data-at-risk-fact]").innerText().catch(() => "(none)")));
console.log("AT RISK ROWS:", await page.locator("[data-at-risk-order]").count());
await shot("boards-1-at-risk-tab", "At risk, its own Work tab right after Orders");

await go("/work/performance?view=at-risk");
console.log("OLD ADDRESS LANDS ON:", page.url().replace(BASE, ""));
await go("/work/performance");
const views = await page.locator("[data-segment]").evaluateAll((els) => els.map((e) => e.getAttribute("data-segment")));
console.log("PERFORMANCE VIEWS:", JSON.stringify(views));
await shot("boards-2-performance-views", "Performance keeps Results, Schedule and Raise across buildings");

// ── (2) D. Ortiz's daily job limit, edited 7 → 6 on his page ─────────────
await go("/work/crews/d-ortiz");
console.log("LIMIT BEFORE:", JSON.stringify(await page.locator("[data-technician-daily-limit]").innerText().catch(() => "(none)")));
await page.locator("[data-edit-daily-limit]").click();
await settle(800);
const input = page.locator("#daily_job_limit");
await input.fill("6");
await shot("boards-3-limit-form", "Daily job limit for D. Ortiz — typed 6");
await page.getByRole("button", { name: /save limit/i }).click();
await settle(2000);
console.log("LIMIT AFTER:", JSON.stringify(await page.locator("[data-technician-daily-limit]").innerText().catch(() => "(none)")));
const detail = await api("/work/technicians/d-ortiz");
console.log("SERVER SAYS:", detail.daily_job_limit);
await shot("boards-4-limit-saved", "D. Ortiz's page — 6 jobs a day");

// ── (3) D. Ortiz over his limit on the Schedule board ────────────────────
await go("/work/performance?view=schedule");
const tomorrow = await page.evaluate(() => {
  const d = new Date(Date.now() + 86400000);
  return d.toISOString().slice(0, 10);
});
const dayInput = page.locator('[data-schedule-day] input[type="date"]');
// The prep gave D. Ortiz his seven jobs on its own "tomorrow" (DAY, printed by
// cr168_boards_walk_prep.py); default: tomorrow by the machine's UTC date.
await dayInput.fill(process.env.DAY ?? tomorrow);
await settle(2500);
console.log("BOARD DAY:", await dayInput.inputValue(), "(browser tomorrow", tomorrow + ")");
console.log("ORTIZ JOBS:", await page.locator('[data-holder-jobs="D. Ortiz"]').innerText().catch(() => "(none)"));
const ortizRow = page.locator('tr:has([data-drop-holder="D. Ortiz"])');
console.log("ORTIZ LOAD:", await ortizRow.locator("[data-holder-load]").getAttribute("data-holder-load").catch(() => "(none)"),
  JSON.stringify(await ortizRow.locator("[data-holder-load]").innerText().catch(() => "(none)")));
await ortizRow.scrollIntoViewIfNeeded().catch(() => undefined);
await shot("boards-5-schedule-over-limit", "Schedule — D. Ortiz, 7 jobs, Over limit of 6");

// ── (4) the Asset age rule leaves a warehouse meter alone ────────────────
const list = await api("/work/rules?page=1&per=50");
const ageRule = (list.results ?? []).find((r) => /asset age/i.test(r.name));
if (ageRule) {
  const one = await api(`/work/rules/${ageRule.id}`);
  console.log("RULE TONIGHT:", JSON.stringify(one.tonight));
  await go(`/work/rules/${ageRule.id}`);
  await shot("boards-6-rule-overview", "Asset age rule — Tonight counts installed meters only");
  await go(`/work/rules/${ageRule.id}?tab=jobs`);
  const jobsText = await page.locator("main").innerText().catch(() => "");
  const raised = await api(`/work/rules/${ageRule.id}/jobs?page=1&per=50`);
  console.log("RULE JOBS (server):", JSON.stringify((raised.results ?? []).map((r) => [r.order_no, r.asset?.asset_no ?? r.asset_no ?? null])));
  console.log("RULE JOBS ON SCREEN — WO-0042:", /WO-0042/.test(jobsText), "AST-04412:", /AST-04412/.test(jobsText), "AST-04414:", /AST-04414/.test(jobsText));
  await shot("boards-7-rule-jobs", "Asset age rule — Jobs: the installed AST-04413 only; the shelf meters were not raised");
} else {
  console.log("NO ASSET AGE RULE FOUND");
}

await browser.close();
