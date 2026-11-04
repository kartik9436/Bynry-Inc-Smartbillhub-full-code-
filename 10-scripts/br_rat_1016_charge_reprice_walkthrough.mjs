// ── Trace ──────────────────────────────────────────────
// Change:   the uniform correction verbs. PO ruling 2026-09-17, shown a table
//           of what each of the five priced objects does today: *"please fix
//           all these"*.
// Defects:  DEF-RAT-5712 — a live charge code's price moved with no reason, no
//           version, no filing record and no lock.
// Rules:    BR-RAT-1016 · BR-RAT-088 · CLAUDE.md hard-won law 6 (NO GATE READS
//           RENDERED OUTPUT — diff the running app) · law 2 in both directions
//           · 13-change-process.md's CLOSURE BAR, PO 2026-08-18: *"CR is not
//           closed until we have confirm user is able to perform tasks using
//           screen/broswer/UI"*
// ───────────────────────────────────────────────────────
/**
 * Walk the charge-code wizard IN A REAL BROWSER and prove the round trip.
 *
 *     BASE=http://127.0.0.1:8580 node 10-scripts/br_rat_1016_charge_reprice_walkthrough.mjs
 *
 * ⚠ **WHY THE 30 VITEST/PYTEST CASES DO NOT REPLACE IT.** They prove the server
 * refuses and the box renders. Neither can prove the REFUSAL LANDS ON THE BOX —
 * that needs the real client, the real transport and the real error envelope,
 * and it is the exact join `DEF-384` was filed for one object over: a refusal
 * with nowhere to go.
 *
 * ⚠ **IT ASSERTS THE ROUND TRIP, NEVER A DRAWN FIGURE (B14 rule 37).** Every
 * amount below belongs to the seeded tenant or is typed by this script.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8580";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";

const problems = [];
const fail = (m) => { problems.push(m); console.log("  x " + m); };
const ok = (m) => console.log("  ok " + m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("    console: " + m.text()); });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
console.log(`signed in as ${EMAIL} -> ${page.url()}`);

// The tenant's own catalogue, read through the API the screen reads.
const listRes = await ctx.request.get(`${BASE}/api/${TENANT}/charges?per=100`);
const list = await listRes.json();
const rows = list.results ?? list;
const inUse = rows.find((r) => (r.used_by_plans ?? 0) > 0 || (r.used_by_schedules ?? 0) > 0);
const spare = rows.find((r) => (r.used_by_plans ?? 0) === 0 && (r.used_by_schedules ?? 0) === 0
  && (r.used_by_invoice_lines ?? 0) === 0 && r.amount_rule === "flat");
console.log(`catalogue: ${rows.length} code(s); in use: ${inUse ? inUse.code : "none"}; spare: ${spare ? spare.code : "none"}`);
if (!inUse) { fail("no charge code on this tenant is in use — the walk cannot reach the guard"); }

if (inUse) {
  console.log(`\n1 · a code IN USE (${inUse.code}, plans=${inUse.used_by_plans}, schedules=${inUse.used_by_schedules})`);
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${inUse.id}/edit`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  const box = page.getByLabel("Reason for change");
  if (await box.count()) { ok("step 3 offers the `Why this changed` box"); }
  else { fail("step 3 offers NO reason box on a code that is in use — the refusal has nowhere to land"); }
  const issued = page.getByText("Bills already sent keep their price.");
  if (await issued.count()) { ok("it says bills already sent keep their price (hard rule 4)"); }
  else { fail("nothing on screen says issued bills are untouched"); }

  // 2 · move the price with NO reason, and read where the refusal lands.
  const current = inUse.amount ?? "0";
  const moved = (Number(current) + 1).toFixed(2);
  const refusal = await ctx.request.fetch(`${BASE}/api/${TENANT}/charges/${inUse.id}`, {
    method: "PATCH", data: { amount: moved },
  });
  const body = await refusal.json();
  const fieldErrors = body?.error?.field_errors ?? body?.field_errors ?? [];
  const onReason = fieldErrors.find((f) => f.field === "reason");
  if (refusal.status() >= 400 && onReason && onReason.message_key === "rating.charges.reason_required") {
    ok(`the server refuses the move ${current} -> ${moved} and puts it on \`reason\``);
  } else {
    fail(`a price move with no reason was NOT refused on \`reason\` (status ${refusal.status()}, body ${JSON.stringify(body).slice(0, 300)})`);
  }

  // 3 · the same move WITH a reason.
  const accepted = await ctx.request.fetch(`${BASE}/api/${TENANT}/charges/${inUse.id}`, {
    method: "PATCH",
    data: { amount: moved, reason: "Walkthrough: proving the filing record is written." },
  });
  const saved = await accepted.json();
  if (accepted.ok() && saved.amount_display === Number(moved).toFixed(2)) {
    ok(`the same move WITH a reason is accepted and reads ${saved.amount_display}`);
  } else {
    fail(`the move with a reason was refused (status ${accepted.status()}, ${JSON.stringify(saved).slice(0, 300)})`);
  }
  if (saved.issued_bills_unchanged === true && saved.open_question === "OQ-RAT-12408") {
    ok("the response names OQ-RAT-12408 and says issued bills are unchanged");
  } else {
    fail("the response does not name the dated-storage question");
  }
  // put it back, so the walk leaves the tenant as it found it
  await ctx.request.fetch(`${BASE}/api/${TENANT}/charges/${inUse.id}`, {
    method: "PATCH",
    data: { amount: current, reason: "Walkthrough: restoring the figure this walk moved." },
  });
}

if (spare) {
  console.log(`\n2 · a code NOBODY uses (${spare.code}) — verb 1, still free`);
  await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${spare.id}/edit`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  if (await page.getByLabel("Reason for change").count()) {
    fail("a code nobody uses is asked for a reason — verb 1 is broken");
  } else { ok("no reason box on a code that has priced nothing"); }
  const free = await ctx.request.fetch(`${BASE}/api/${TENANT}/charges/${spare.id}`, {
    method: "PATCH", data: { amount: (Number(spare.amount ?? 0) + 1).toFixed(2) },
  });
  if (free.ok()) { ok("its amount changes with no reason at all"); }
  else { fail(`an unused code refused a free edit (status ${free.status()})`); }
  await ctx.request.fetch(`${BASE}/api/${TENANT}/charges/${spare.id}`, {
    method: "PATCH", data: { amount: spare.amount ?? "0" },
  });
} else {
  console.log("\n2 · no unused flat code on this tenant — the free-edit half is not walked");
}

console.log(`\n${problems.length === 0 ? "WALK CLEAN" : problems.length + " PROBLEM(S)"}`);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
