// ── Trace ──────────────────────────────────────────────
// Change:  CR-167-BRC10 round 3 task 8 (lane PLAN-EDIT) — walk Edit a plan in
//          a real browser at 1440 and photograph each built state beside
//          images 37–44 of `05-prototype/plans-2026-10-03/images/`, then do
//          the three ways on ONE published plan for real.
// ───────────────────────────────────────────────────────
//
// Expects:
//   * the API — `manage.py runserver 127.0.0.1:8211` on PostgreSQL 16
//     (`sbh_planedit`: `migrate` + `seed_demo` + `load_sample_data --tenant
//     brazosbend`; Brazos Bend, Dana);
//   * the SPA — `vite build --mode wolocal`, then
//     `PORT=5311 API_PROXY_TARGET=http://127.0.0.1:8211 node 07-frontend/server.mjs`.
//
//   PLAN=<plan id> OUT=08-qa/plans-2026-10-03/edit node 10-scripts/cr167_plan_edit_walk.mjs
//
// The walk WRITES: a rename (Name and details), a v2 from 01/01/2027 with a
// new minimum bill (Change from a date) and a correction of v1 (Fix a
// mistake). Run it on a fresh database; the database checks are
// `10-scripts/cr167_plan_edit_db_check.py`.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5311";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr167-edit";
const PLAN = process.env.PLAN;
// `FROM=correct` resumes a walk whose earlier ways already wrote (stages: info, change, correct, audit).
const STAGES = ["info", "change", "correct", "audit"];
const FROM = STAGES.indexOf(process.env.FROM ?? "info");
const run = (stage) => STAGES.indexOf(stage) >= FROM;
if (!PLAN) throw new Error("PLAN=<plan id> is required");
mkdirSync(OUT, { recursive: true });

const say = (line) => console.log(line);
/** The preinstalled Chromium (the lane does not run `playwright install`). */
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
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (error) => say(`PAGE ERROR ${error.message}`));
page.on("response", (response) => {
  const url = response.url();
  if (/\/plans\//.test(url) && response.request().method() !== "GET") {
    say(`  ${response.request().method()} ${url.replace(/^.*\/api\/v1/, "")} → ${response.status()}`);
  }
});

async function shot(name, caption) {
  await page.waitForTimeout(700);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(200);
  const height = await page.evaluate(() => {
    const scroller = [...document.querySelectorAll("main, main *")].find(
      (el) => el.scrollHeight > el.clientHeight + 4 && getComputedStyle(el).overflowY !== "visible",
    );
    const main = document.querySelector("main");
    const top = main ? main.getBoundingClientRect().top : 0;
    return Math.ceil(Math.max(900, (scroller ?? main ?? document.body).scrollHeight + top + 40));
  });
  await page.setViewportSize({ width: 1440, height });
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`=== ${name}.png — ${caption}`);
}
const click = (name) => page.getByRole("button", { name, exact: true }).click();
const edit = (query) => page.goto(`${BASE}/${TENANT}/plans-rates/plans/${PLAN}/edit${query}`, { waitUntil: "networkidle" });
async function text(selector) {
  return (await page.locator(selector).first().innerText()).replace(/\s+/g, " ").trim();
}
async function rail() {
  return (await page.locator('[data-wizard="rail"] button').allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim());
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.getByRole("button", { name: /sign in/i }).click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 1 · Name and details (images 38, 39) ─────────────────────────────────
if (run("info")) {
await edit("?change=info");
await page.getByLabel(/^Plan name/).waitFor();
say(`rail: ${JSON.stringify(await rail())}`);
say(`code fact: ${await text('[data-read-only-fact="plan-code"]')}`);
say(`locked: ${await text('[aria-labelledby="plan-sec-priced-locked"]')}`);
await shot("38-edit-info-1", "Edit · Name and details · step Details");
await click("Continue");
await page.getByText("What changes").waitFor();
await shot("39-edit-info-review-unchanged", "Name and details · Review, nothing changed (image 39)");
await click("Back");
await page.getByLabel(/^Description for customers/).fill("Water and electric for businesses inside the city.");
await click("Continue");
await page.getByText("What changes").waitFor();
say(`what changes: ${await text('[aria-labelledby="plan-sec-changes"]')}`);
await shot("39-edit-info-review", "Name and details · Review (same version), description moved");
await click("Save changes");
await page.locator("[data-plan-edit-saved]").waitFor();
say(`saved: ${await text("[data-plan-edit-saved]")}`);
await shot("39b-edit-info-saved", "Name and details · saved on this version");

}
// ── 2 · Change from a date (images 37, 40, 41, 42) ───────────────────────
if (run("change")) {
await edit("?change=change");
await page.getByRole("button", { name: "+ Add service" }).waitFor();
say(`rail: ${JSON.stringify(await rail())}`);
await shot("40-edit-change-1", "Change from a date · first step (Services)");
await edit("?change=change&step=2");
await page.getByRole("button", { name: "+ Add charge code" }).waitFor();
say(`step=2 opens: ${JSON.stringify(await rail())} · charge rows ${await page.getByRole("combobox", { name: "Charge code", exact: true }).count()}`);
await shot("37-detail-section-edit", "the address a section's Edit opens: ?change=change&step=2 → Charges");
await click("Continue");
await page.getByLabel(/^Minimum bill/).waitFor();
await page.getByLabel(/^Minimum bill/).fill("12.00");
await click("Continue");
await page.getByText("How it is saved").waitFor();
await page.fill("#plan-starts", "2027-01-01");
await page.locator("#plan-starts").blur();
await shot("41-edit-change-review", "Change from a date · Review (v1 ends, v2 new; units move)");
await click("Publish new version");
await page.getByText("Enter the reason.").waitFor();
await shot("42-edit-change-refused", "Change from a date · Publish without a reason — refused by name (image 42 draws this)");
await page.getByLabel(/^Reason/).fill("New minimum bill from council");
await click("Publish new version");
await page.locator("[data-plan-edit-saved]").waitFor();
say(`saved: ${await text("[data-plan-edit-saved]")}`);
await shot("42-edit-change-published", "Change from a date · new version published");

}
// ── 3 · Fix a mistake (images 43, 44) ────────────────────────────────────
if (run("correct")) {
await edit("?change=correct");
await page.getByRole("button", { name: "+ Add service" }).waitFor();
await shot("43-edit-correct-1", "Fix a mistake · first step");
await edit("?change=correct&step=3");
await page.getByLabel(/^Offer budget billing/).waitFor();
await page.getByLabel(/^Offer budget billing/).check({ force: true });
await click("Continue");
await page.getByText("How it is saved").waitFor();
await shot("44-edit-correct-review-noreason", "Fix a mistake · Review, before the reason");
await page.getByLabel(/^Reason/).fill("Budget billing was ruled on for this plan");
await shot("44-edit-correct-review", "Fix a mistake · Review (same dates, reason)");
await click("Save correction");
await page.locator("[data-plan-edit-saved]").waitFor();
say(`saved: ${await text("[data-plan-edit-saved]")}`);
await shot("44b-edit-correct-saved", "Fix a mistake · saved");

}
// ── 4 · Audit shows each ─────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/plans-rates/plans/${PLAN}?tab=audit`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("audit-after-three-ways", "Details · Audit after the three ways");
say(`audit: ${(await page.locator("main").innerText()).replace(/\s+/g, " ").slice(0, 2500)}`);

await browser.close();
