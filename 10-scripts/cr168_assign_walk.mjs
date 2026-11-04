// CR-168-BRC10 round 3, lane ASSIGN — the AFTER walk at 1440 wide, images 02, 12
// and 13 with the advice beside every name, on PostgreSQL.
//
//   BASE=http://127.0.0.1:5531 node 10-scripts/cr168_assign_walk.mjs
//
// Preconditions: seed_demo + load_sample_data --tenant brazosbend, then
// 10-scripts/cr168_assign_walk_prep.py (WO-0027, Water I, taken off D. Ortiz so
// nobody holds it).
//
// What it PROVES rather than draws (ruling 2 — the match advises and never
// blocks; a lapsed certificate only warns):
//   1. on WO-0027's edit page every candidate is listed and NONE is disabled;
//      M. Chen (no Water I) reads *Missing skill: Water I* and J. Okoro reads
//      *Certificate lapsed …*; the two are each chosen and the save is ACCEPTED
//      by the server (HTTP 200) — the one missing the skill is assigned;
//   2. on the reassign (WO-0027 now M. Chen's → J. Okoro) *Why it moves* is
//      required, and the save with a reason is accepted;
//   3. *Assign 2 orders* (WO-0016, WO-0022) lists everybody with the advice and
//      its line; choosing M. Chen says his advice under the field.
//
// WRITES IT MAKES: WO-0027 assigned to M. Chen, then reassigned to J. Okoro
// with the reason *Workload — M. Chen has four jobs that day.*
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5531";
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
const saves = [];
page.on("response", async (r) => {
  const url = r.url();
  if (url.includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${url.replace(BASE, "")}`);
  if (url.includes("/work-orders/") && r.request().method() !== "GET") {
    let body = "";
    try { body = await r.text(); } catch { /* gone */ }
    saves.push({ status: r.status(), request: r.request().postData(), body: body.slice(0, 300) });
  }
});
const settle = (ms = 1200) => page.waitForTimeout(ms);
const problems = [];
const check = (ok, what) => { console.log(`${ok ? "PASS" : "FAIL"} · ${what}`); if (!ok) problems.push(what); };
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
/** Every offered row: its name, its words, whether it is disabled. */
async function offered(scope) {
  return page.locator(`${scope} [role="option"]`).evaluateAll((lis) =>
    lis.map((li) => ({
      name: li.querySelector(".font-semibold")?.textContent ?? li.textContent,
      text: li.textContent,
      disabled: li.getAttribute("aria-disabled") === "true",
    })),
  );
}
async function pickByName(scope, name) {
  await page.locator(`${scope} [role="combobox"]`).click();
  await settle(400);
  await page.locator(`${scope} [role="option"]`).filter({ has: page.locator(".font-semibold", { hasText: name }) }).first().click();
  await settle(400);
}

// ── sign in ──────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

const PICKER = '[data-candidate-picker="assigned-to"]';
const wo27 = await orderId("WO-0027");

// ── 12 · Assign a job — the list open, the advice beside every name ───────
await go(`/work/orders/${wo27}/edit`);
await page.locator(`${PICKER} [role="combobox"]`).click();
await settle(800);
const rows12 = await offered(PICKER);
console.log("OFFERED 12:", JSON.stringify(rows12));
check(rows12.every((row) => !row.disabled), "no name on the assign list is disabled");
const chen = rows12.find((row) => row.name === "M. Chen");
const okoro = rows12.find((row) => row.name === "J. Okoro");
check(Boolean(chen) && /Missing skill: Water I/.test(chen.text), "M. Chen is offered with *Missing skill: Water I*");
check(Boolean(okoro) && /Certificate lapsed/.test(okoro.text), "J. Okoro is offered with *Certificate lapsed …*");
await shot("12-orders-assign-a-job-assign-advice", "Assign — every name, Best fit first, the advice at the right; none greyed");

// DRY=1 stops here: a look at the list with no write (used while lane SRV-2's
// server was still landing, when the list could not yet hold M. Chen).
if (process.env.DRY) {
  console.log(problems.length === 0 ? "DRY: CHECKS PASSED" : `DRY FAILED: ${JSON.stringify(problems)}`);
  await browser.close();
  process.exit(0);
}

// The one MISSING the skill is chosen and saved.
await page.locator(`${PICKER} [role="option"]`).filter({ has: page.locator(".font-semibold", { hasText: "M. Chen" }) }).first().click();
await settle(500);
await page.getByRole("button", { name: /Assign ✓/ }).click();
await settle(2500);
const save12 = saves.at(-1);
console.log("SAVE 12:", JSON.stringify(save12));
check(save12?.status === 200, "assigning M. Chen (missing the skill) is ACCEPTED by the server");

// ── 13 · Reassign — M. Chen → J. Okoro (the lapsed certificate), with a reason ─
await go(`/work/orders/${wo27}/edit`);
await pickByName(PICKER, "J. Okoro");
const help = await page.locator('[data-field-help="assigned-to"]').innerText();
console.log("HELP 13:", help);
check(/^Was M\. Chen\. J\. Okoro/.test(help), "the line under the field names who had it and the new name's advice");
await page.getByRole("button", { name: /Reassign ✓/ }).click();
await settle(500);
check(await page.getByText("Choose why it moves.").isVisible(), "a reassign without a reason is stopped on the page");
await page.getByLabel(/Why it moves/).selectOption("workload");
await page.getByLabel("Note", { exact: true }).fill("M. Chen has four jobs that day.");
await settle(400);
await shot("13-orders-reassign-a-job-assign-advice", "Reassign — Was M. Chen; J. Okoro's advice (lapsed certificate); Why it moves");
await page.getByRole("button", { name: /Reassign ✓/ }).click();
await settle(2500);
const save13 = saves.at(-1);
console.log("SAVE 13:", JSON.stringify(save13));
check(save13?.status === 200, "reassigning to J. Okoro (lapsed certificate) with a reason is ACCEPTED by the server");
check(/Workload — M\. Chen has four jobs that day\./.test(save13?.request ?? ""), "the reason travels with the save");

// ── 02 · Assign in bulk ─────────────────────────────────────────────────
await go("/work/orders");
await page.getByLabel("Select WO-0016").check();
// WO-0022 needs Water I (D. Ortiz's); WO-0016 needs no skill — so the advice
// across the two names who lacks Water I.
await page.getByLabel("Select WO-0022").check();
await page.getByRole("button", { name: "Assign selected…" }).click();
await settle(1200);
const BULK = '[data-candidate-picker="holder"]';
await page.locator(`${BULK} [role="combobox"]`).click();
await settle(800);
const rows02 = await offered(BULK);
console.log("OFFERED 02:", JSON.stringify(rows02));
check(rows02.length > 0 && rows02.every((row) => !row.disabled), "bulk: every name offered, none disabled");
await shot("02-orders-assign-in-bulk-assign-advice", "Assign 2 orders — everybody, with the advice; who and when");
// The first Esc puts the list away (IS-10) and leaves the dialog: the line
// under *Who is going* is the advice across the two orders.
await page.keyboard.press("Escape");
await settle(500);
const line02 = await page.locator('[data-field-help="holder"]').innerText().catch(() => "");
console.log("BULK LINE 02:", JSON.stringify(line02));
check(/lack.? a needed skill/.test(line02), "bulk: the line under Who is going says how many lack a needed skill");
await pickByName(BULK, "M. Chen");
const chosen02 = await page.locator('[data-field-help="holder"]').innerText().catch(() => "");
console.log("BULK LINE 02 (M. Chen chosen):", JSON.stringify(chosen02));
check(chosen02.startsWith("Advice: M. Chen"), "bulk: choosing a name says its advice under the field");
await shot("02b-orders-assign-in-bulk-chosen-assign-advice", "Assign 2 orders — M. Chen chosen, the advice line, date and window");

console.log(problems.length === 0 ? "ALL CHECKS PASSED" : `FAILED: ${JSON.stringify(problems)}`);
await browser.close();
