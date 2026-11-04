// CR-168-BRC10 round 5, lane PERFORMANCE — the walk at 1440 wide: image 65
// (Performance, P5.1) and the three boards P5 names and does not draw — at risk
// (P5.3), schedule (P5.4), raise across buildings (P5.5).
//
// Run against a PostgreSQL-backed API and the built SPA (`node server.mjs`):
//   BASE=http://127.0.0.1:5205 OUT=08-qa/work-2026-10-04/after node 10-scripts/cr168_perf_walk.mjs
// Preconditions: seed_demo + load_sample_data --tenant brazosbend, then
// `10-scripts/cr168_perf_walk_prep.py` (jobs near and past their promise).
//
// WRITES IT MAKES: one job dropped onto the first holder of today (a bulk
// assign), and one job per ticked asset raised across buildings.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5205";
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

// ── image 65 · Performance (P5.1): the headline and its rows ─────────────
await go("/work/performance");
const perf = await api("/work/performance?page=1&per=50");
const sum = (k) => perf.results.reduce((t, r) => t + r[k], 0);
console.log(
  `HEADLINE ${perf.tiles.sla_met_pct}% = ${perf.tiles.sla_met}/${perf.tiles.sla_measured}; rows sum ${sum("sla_met")}/${sum("sla_measured")}; ` +
    `volume tile ${perf.tiles.volume} = rows ${sum("volume")}; count ${perf.count}, page ${perf.results.length}; twin ${"by_job_type" in perf}`,
);
const tileText = await page.locator("[data-sla-detail]").innerText().catch(() => "(none)");
console.log("SLA TILE DETAIL:", JSON.stringify(tileText));
await shot("a65-performance", "Performance · Results — the SLA tile says N of M kept and the default promise");

// ── P5.3 · the at-risk board ─────────────────────────────────────────────
await go("/work/performance?view=at-risk");
const risk = await api("/work/at-risk?page=1&per=50");
console.log(`AT RISK ${risk.count} rows, window ${risk.window_hours} h; late ${risk.results.filter((r) => r.promise.overdue).length}`);
await shot("a65b-at-risk", "Performance · At risk — late first, then due soon");

// ── P5.4 · the schedule board ────────────────────────────────────────────
await go("/work/performance?view=schedule");
await shot("a65c-schedule", "Performance · Schedule — the jobs nobody holds and everybody's load today");
const firstJob = page.locator("[data-drag-order]").first();
const jobNo = await firstJob.getAttribute("data-drag-order");
const holder = page.locator("[data-drop-holder]").first();
const holderName = await holder.getAttribute("data-drop-holder");
await firstJob.dragTo(holder);
await settle(2500);
console.log(`DRAGGED ${jobNo} onto ${holderName}:`, await page.locator("[data-schedule-answer]").innerText().catch(() => "(no answer)"));
await shot("a65d-schedule-dropped", `Performance · Schedule — ${jobNo} dropped on ${holderName}`);

// ── P5.5 · bulk raise across buildings ───────────────────────────────────
await go("/work/performance?view=across");
const select = page.locator("[data-across-template]");
const options = await select.locator("option").allTextContents();
const water = options.find((o) => /water/i.test(o)) ?? options[1];
await select.selectOption({ label: water });
await settle(2000);
await page.locator("[data-across-test-due]").uncheck();
await settle(2000);
const ticks = page.locator("[data-testid='across-assets'] tbody input[type=checkbox]");
const n = Math.min(3, await ticks.count());
for (let i = 0; i < n; i += 1) await ticks.nth(i).check();
await settle();
await shot("a65e-raise-across-picked", `Performance · Raise across buildings — ${water}, ${n} assets ticked`);
await page.locator("[data-across-raise]").click();
await settle(3000);
await shot("a65f-raise-across-result", "Performance · Raise across buildings — one result per job");
const raised = await page.locator("[data-raise-step='result'] tbody tr").allInnerTexts().catch(() => []);
console.log("RESULT ROWS:", JSON.stringify(raised));

await browser.close();
