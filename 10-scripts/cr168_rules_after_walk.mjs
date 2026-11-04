// CR-168-BRC10 round 5, lane RULES — the AFTER walk at 1440 wide: images 56–64
// photographed in their states, and the brief's proof end to end on PostgreSQL:
//   build a rule through the THREE-step builder (two triggers, a customer
//   message, an escalation that also tells a role), activate it, run the sweep
//   for it (SWEEP_CMD, a manage.py shell line the caller passes), see it raise
//   jobs, open its Jobs and Audit tabs, turn it off.
//
//   BASE=http://127.0.0.1:5203 OUT=08-qa/work-2026-10-04/after \
//   SWEEP=<path to a shell script that sweeps one rule id given as $1> \
//   node 10-scripts/cr168_rules_after_walk.mjs
//
// Preconditions: migrate + seed_demo + load_sample_data --tenant brazosbend on
// PostgreSQL, the API with this branch, the SPA served by 07-frontend/server.mjs.
// WRITES IT MAKES: one rule, the jobs its sweep raises, one switch-off.
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5203";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "08-qa/work-2026-10-04/after";
const SWEEP = process.env.SWEEP ?? "";
const NAME = "Backflow test due — walk";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const failed = [];
page.on("response", (r) => {
  if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`);
});
const settle = (ms = 1200) => page.waitForTimeout(ms);
const checks = [];
function check(name, ok, detail = "") {
  checks.push([name, ok]);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}
async function shot(name, caption) {
  await settle();
  // The frame scrolls inside <main>, so a "full page" shot is only the
  // viewport. Grow the viewport to the content, from the top, then restore.
  const tall = await page.evaluate(() => {
    const m = document.querySelector("main");
    m?.scrollTo(0, 0);
    window.scrollTo(0, 0);
    let h = document.documentElement.scrollHeight;
    for (const el of document.querySelectorAll("*")) {
      if (el.scrollHeight > el.clientHeight + 4 && getComputedStyle(el).overflowY !== "visible") h = Math.max(h, el.scrollHeight + 120);
    }
    return Math.min(h, 6000);
  });
  await page.setViewportSize({ width: 1440, height: Math.max(1100, tall) });
  await settle(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1100 });
  console.log(`=== ${name}.png — ${caption}`);
  if (failed.length) console.log("API 4xx/5xx:", JSON.stringify(failed.splice(0)));
}
async function go(path) {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle", timeout: 30000 }).catch(() => console.log("goto timeout", path));
  await settle(1500);
}
async function api(path, method = "GET", body = undefined) {
  return page.evaluate(
    async ([tenant, p, m, b]) => {
      const res = await fetch(`/api/${tenant}/${p}`, {
        method: m,
        credentials: "include",
        headers: b === undefined ? {} : { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      return { status: res.status, body: await res.json().catch(() => null) };
    },
    [TENANT, path, method, body],
  );
}
const main = () => page.locator("main").innerText();
const box = (name) => page.getByRole("textbox", { name, exact: true });
const pick = (name) => page.getByRole("combobox", { name, exact: true });
const press = (name) => page.getByRole("button", { name, exact: true }).first().click();
async function next() {
  await press("Continue");
  await settle(900);
}
async function selectByText(name, text) {
  const value = await pick(name).evaluate((el, t) => {
    const option = [...el.options].find((o) => o.textContent.includes(t) && o.value !== "");
    return option ? option.value : [...el.options].find((o) => o.value !== "")?.value ?? "";
  }, text);
  await pick(name).selectOption(value);
  return value;
}


// ── sign in ──────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 56 · the list ────────────────────────────────────────────────────────
await go("/work/rules");
const t56 = await main();
check("56 · + New rule with rules on screen", (await page.getByRole("link", { name: "+ New rule" }).count()) === 1 && t56.includes("Leak investigation"));
check("56 · LAST FIRED column", /last fired/i.test(t56));
check("56 · row actions: open, edit, duplicate", (await page.getByRole("link", { name: "Duplicate Leak investigation" }).count()) === 1);
await shot("56-rules-rules", "Rules · list");
await page.getByPlaceholder(/search rules/i).fill("Leak");
await settle(1500);
const t56b = await page.locator("tbody").innerText();
check("56b · the search narrows on the server", t56b.includes("Leak investigation") && !t56b.includes("Backflow test due"));
await shot("56b-rules-search", "Rules · searched for Leak");

// ── 57 · Trigger ─────────────────────────────────────────────────────────
await page.getByRole("link", { name: "+ New rule" }).click();
await settle(2000);
check("57 · three steps on the shared frame", (await page.locator("[data-wizard-step]").count()) === 3);
await page.locator("#rule-name").fill(NAME);
await page.locator("#rule-template").selectOption({ index: 1 });
await page.locator("#rule-template").evaluate((el) => {
  const o = [...el.options].find((x) => x.textContent.includes("Meter exchange"));
  if (o) { el.value = o.value; el.dispatchEvent(new Event("change", { bubbles: true })); }
});
await page.locator("#rule-priority").selectOption({ label: "Low" });
await page.locator("[data-cell='add-trigger']").selectOption("asset_age_rule");
await page.locator("[data-add-trigger]").click();
await page.locator("[data-cell='add-trigger']").selectOption("compliance_calendar");
await page.locator("[data-add-trigger]").click();
await settle(500);
const days = page.locator("[data-trigger-settings='compliance_calendar'] input[type='number']");
await days.fill("30");
await page.locator("#rule-assign").selectOption("skill");
await shot("57-rules-rule-trigger", "Rule · Trigger — two triggers, template, who gets it");
await next();

// ── 59 · Notify ──────────────────────────────────────────────────────────
await page.locator("[data-cell='add-message']").selectOption("raised");
await page.locator("[data-add-message]").click();
await page.locator("[data-cell='notify-1-who']").selectOption("customer");
await page.locator("[data-cell='notify-1-message']").selectOption("appointment_window");
await page.locator("[data-cell='add-message']").selectOption("done");
await page.locator("[data-add-message]").click();
await page.locator("[data-cell='notify-2-who']").selectOption("customer");
await page.locator("[data-cell='notify-2-message']").selectOption("completion_receipt");
await page.locator("[data-cell='add-escalation']").selectOption("unassigned");
await page.locator("[data-add-escalation]").click();
await page.locator("[data-cell='stall-1-hours']").fill("4");
await page.locator("[data-cell='add-escalation']").selectOption("overdue");
await page.locator("[data-add-escalation]").click();
await page.locator("[data-cell='stall-2-hours']").fill("24");
await page.locator("[data-cell='stall-2-also']").selectOption("role:field_technician");
await settle(500);
const t59 = await main();
check("59 · the escalation's message is shown (Promised deadline missed)", t59.includes("Promised deadline missed"));
await shot("59-rules-rule-notify", "Rule · Notify — who hears, when it stalls");
if (process.env.STOP_AFTER === "59") {
  // A re-shoot of the Notify step alone writes nothing (nothing is saved before Activate).
  await browser.close();
  process.exit(checks.some(([, ok]) => !ok) ? 1 : 0);
}
await next();

// ── 61 · Review ──────────────────────────────────────────────────────────
await settle(2000);
const t61 = await main();
const tonight = (t61.match(/Tonight it raises (\d+) jobs?/) ?? [])[1];
check("61 · the Review states tonight's count", tonight !== undefined, `count ${tonight}`);
check("61 · Also tell reads back", t61.includes("Field technician"));
await shot("61-rules-rule-review", "Rule · Review");
await page.getByRole("button", { name: "Activate rule", exact: true }).click();
await page.waitForURL((u) => /\/work\/rules\/[0-9a-f-]{36}$/.test(u.pathname), { timeout: 30000 });
await settle(2000);
const ruleId = page.url().split("/").pop().split("?")[0];
check("activate lands on the rule's own page", ruleId.length === 36);

// ── the sweep raises jobs ────────────────────────────────────────────────
if (SWEEP) {
  const out = execFileSync(SWEEP, [ruleId], { encoding: "utf-8" });
  console.log("sweep:", out.trim().split("\n").slice(-1)[0]);
}
const jobs = await api(`work/rules/${ruleId}/jobs?page=1&per=50`);
check("the rule raised jobs", (jobs.body?.count ?? 0) > 0, `count ${jobs.body?.count}`);

// ── 62 · Overview ────────────────────────────────────────────────────────
await go(`/work/rules/${ruleId}`);
const t62 = await main();
check("62 · Raises … at Low priority", t62.includes("at Low priority"));
check("62 · no id on screen", !t62.includes(ruleId));
await shot("62-rules-one-rule-overview", "One rule · Overview");

// ── 63 · Jobs ────────────────────────────────────────────────────────────
await go(`/work/rules/${ruleId}?tab=jobs`);
const t63 = await main();
check("63 · the jobs tab lists the raised jobs", /WO-\d+/.test(t63));
await shot("63-rules-one-rule-jobs", "One rule · Jobs");

// ── turn it off, then 64 · Audit ─────────────────────────────────────────
await go(`/work/rules/${ruleId}`);
await page.getByRole("button", { name: "Turn off", exact: true }).click();
await settle(1500);
await go(`/work/rules/${ruleId}?tab=audit`);
const t64 = await main();
check("64 · audit: written and turned off, by Dana", t64.includes("Rule written") && t64.includes("Turned off") && t64.includes("Dana Whitfield"));
await shot("64-rules-one-rule-audit", "One rule · Audit");

// ── Edit opens the builder on the rule; Duplicate on a copy ──────────────
await go(`/work/rules/${ruleId}/edit?step=3`);
check("edit re-opens with its triggers", (await main()).includes("An asset's certification is due soon"));
await go(`/work/rules/new?from=${ruleId}`);
check("duplicate fills a copy", (await page.locator("#rule-name").inputValue()).includes("(copy)"));

const failedCount = checks.filter(([, ok]) => !ok).length;
console.log(`\n${checks.length - failedCount}/${checks.length} checks passed`);
await browser.close();
process.exit(failedCount ? 1 : 0);
