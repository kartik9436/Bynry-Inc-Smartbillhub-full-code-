// CR-168-BRC10 round 2, lane ORDERS-LIST — the AFTER walk at 1440 wide, the
// same states as images 01, 02, 12, 13, 21, 22, 23.
//
// Run against a PostgreSQL-backed API and the built SPA:
//   BASE=http://127.0.0.1:5461 OUT=08-qa/work-2026-10-04/after node 10-scripts/cr168_orders_list_after_walk.mjs
// Preconditions: seed_demo + load_sample_data --tenant brazosbend, then
// 10-scripts/cr168_orders_list_walk_prep.py (three jobs closed by their
// technician, so the Approvals queue has rows).
//
// WRITES IT MAKES (so a later reader of the database is not misled): WO-0018
// assigned to the crew *Field crew A* through the edit page (DEF-WRK-9563's
// proof); WO-0037 accepted from the Approvals queue (image 23).
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5461";
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
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
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
async function orderId(orderNo) {
  return page.evaluate(async ([tenant, no]) => {
    const res = await fetch(`/api/${tenant}/work-orders?q=${no}&status=`, { credentials: "include" });
    const data = await res.json();
    return (data.results ?? []).find((r) => r.order_no === no)?.id ?? null;
  }, [TENANT, orderNo]);
}
const headText = () => page.locator(".page-header-actions").first().innerText();

// ── sign in ──────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ONLY=13 re-photographs the reassign state alone (the walk's own writes —
// WO-0018 assigned, WO-0037 accepted — make the other states unrepeatable
// without a fresh seed).
const ONLY = process.env.ONLY ?? "";
if (ONLY === "") {
// ── 01 · Orders ──────────────────────────────────────────────────────────
await go("/work/orders");
console.log("HEAD ACTIONS 01:", JSON.stringify(await headText()));
await shot("01-orders-work-orders", "Orders — + New work order top right, tab reads Approvals");

// ── 02 · Assign in bulk ──────────────────────────────────────────────────
await page.getByLabel("Select WO-0016").check();
await page.getByLabel("Select WO-0018").check();
await page.getByRole("button", { name: "Assign selected…" }).click();
await settle();
await shot("02-orders-assign-in-bulk", "Assign 2 orders — who, date, window");
await page.keyboard.press("Escape");
await settle(500);
await page.getByRole("button", { name: "Reschedule selected…" }).click();
await settle();
await shot("02b-orders-reschedule-in-bulk", "Reschedule — a date picker and the window list, no free text");
await page.keyboard.press("Escape");

// ── 12 · Assign a job (unassigned WO-0018) ───────────────────────────────
// SKIP_ASSIGN=1 (round 7, WALK-A): since lane ASSIGN (2.499.0) the Assigned-to
// field is a typeable picker, not a <select>, so 12/13 are photographed by
// `cr168_assign_walk.mjs` and this walk goes straight on to Approvals.
if (process.env.SKIP_ASSIGN !== "1") {
const wo18 = await orderId("WO-0018");
await go(`/work/orders/${wo18}/edit`);
console.log("HEAD ACTIONS 12:", JSON.stringify(await headText()));
const picker = page.locator('[data-field="technician_id"]');
console.log("ASSIGNED-TO OPTIONS:", JSON.stringify(await picker.locator("option").allInnerTexts()));
console.log("STATUS OPTIONS:", JSON.stringify(await page.locator('[data-field="dispatch_state"] option').allInnerTexts()));
const crewValue = await picker.locator("option", { hasText: "· Crew" }).first().getAttribute("value");
await picker.selectOption(crewValue);
await settle(500);
await shot("12-orders-assign-a-job", "Assign — a crew picked, the effects name it; actions top right");
await page.getByRole("button", { name: /Assign ✓/ }).click();
await settle(2000);
console.log("AFTER ASSIGN URL:", page.url().replace(BASE, ""));
await page.fill('input[type="search"]', "WO-0018");
await settle(1500);
await shot("12b-orders-crew-assigned", "WO-0018 now held by the crew (DEF-WRK-9563)");
}
}
if (process.env.SKIP_ASSIGN !== "1") {
// ── 13 · Reassign a job (WO-0018, now held by Field crew A from step 12)────────────────────────────
const wo25 = await orderId("WO-0018");
await go(`/work/orders/${wo25}/edit`);
console.log("HEAD ACTIONS 13:", JSON.stringify(await headText()));
const picker13 = page.locator('[data-field="technician_id"]');
console.log("OPENS ON:", await picker13.evaluate((el) => el.options[el.selectedIndex].text));
const current = await picker13.inputValue();
const other = await picker13.evaluate((el) =>
  Array.from(el.options).filter((o) => o.text.endsWith("· Technician")).map((o) => o.value));
const next = other.find((value) => value !== current);
console.log("REASSIGN FROM", current, "TO", next, JSON.stringify(await picker13.evaluate((el) => Array.from(el.options).map((o) => o.text))));
if (next) await picker13.selectOption(next);
await settle(500);
await shot("13-orders-reassign-a-job", "Reassign — both people named in the effects");
}

if (ONLY === "") {
// ── 21 · Approvals ───────────────────────────────────────────────────────
await go("/work/awaiting-approval");
await shot("21-approvals-approvals", "Approvals — Select column, eye and ✓ per row");
const eyes = await page.getByRole("link", { name: "View" }).evaluateAll((as) => as.map((a) => a.getAttribute("href")));
console.log("EYE HREFS:", JSON.stringify(eyes));

// ── 22 · Accept (one ticked, the header button, the confirm) ─────────────
await page.getByLabel("Select WO-0037").check();
await settle(500);
console.log("HEAD ACTIONS 22:", JSON.stringify(await headText()));
await page.getByRole("button", { name: "Accept WO-0037" }).click();
await settle();
await shot("22-approvals-approvals-accept", "Accept WO-0037? — the consequence, Keep waiting / Accept ✓");

// ── 23 · Accepted ────────────────────────────────────────────────────────
await page.getByRole("button", { name: "Accept ✓" }).click();
await page.waitForTimeout(900);
await shot("23-approvals-approvals-accepted", "WO-0037 accepted — the queue is one shorter, the toast says so");

}
await browser.close();
