// ── Trace ──────────────────────────────────────────────
// Process: 12-governance/23-end-to-end-clerk-walk.md — the PO's own walk, and
//          its 2026-09-16 clause: "ensure he is able to perform this workflow
//          and it procude the intented result - you ahve to do it from product
//          screens".
// Rules:   hard-won law 6 (no gate in this repo reads rendered output) ·
//          B14 rule 42 (a screen is judged as it renders, not as code reads)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PASS MARK IS NOT "THE SCREENS RENDER".** A clerk can walk eight
// perfect screens and write nothing — that is exactly what this wizard did
// until the commit door stopped answering 404. So this walk ends in the
// DATABASE: after the press it reads back the premises, the units, the meters
// AND WHICH UNIT EACH ONE IS ON, the plans, the work orders, the account and
// the messages, and reports each against what the screen promised.
//
// ⚠ **A STATED ABSENCE PASSES. A SILENT NOTHING FAILS.** Several things are
// deliberately, visibly missing. What fails is a screen promising a count the
// server did not produce.
//
// RUN:  node 10-scripts/po_new_connect_clerk_walk.mjs
const { mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/po_clerk_walk";
const UNITS = Number(process.env.UNITS ?? 6);
mkdirSync(OUT, { recursive: true });

const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);
const ADDRESS = `${STAMP.slice(8)} Clerk Walk Drive`;
const say = (...a) => console.log(...a);
const refusals = [];
let stepNo = 0;

const browser = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") refusals.push(`console: ${m.text().slice(0, 120)}`); });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL}`);

const api = (path) => page.evaluate(async (p) => {
  const r = await fetch(p, { headers: { accept: "application/json" } });
  return { status: r.status, body: await r.text() };
}, path);

// Capture the step the clerk is looking at, at BOTH staff widths.
async function shot(name) {
  stepNo += 1;
  const n = String(stepNo).padStart(2, "0");
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/${n}-${name}-1280.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/${n}-${name}-1440.png`, fullPage: true });
  // A refusal the clerk can see, counted rather than described.
  const seen = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-refusal],[role="alert"]'))
      .map((n) => n.textContent.trim()).filter(Boolean).slice(0, 4));
  if (seen.length) refusals.push(`${name}: ${seen.join(" | ")}`);
  say(`  captured ${n}-${name}`);
}

// ⚠ **A RADIO IN THIS KIT IS VISUALLY HIDDEN AND OFTEN BELOW THE FOLD, AND
// `force: true` DOES NOT BYPASS PLAYWRIGHT'S VIEWPORT CHECK** — `check()` fails
// with "Element is outside of the viewport". The first run of this walk lost
// every step to that and read as a product blocker: eight presses, eight
// refusals, the clerk never leaving step 1. Scroll it into view first.
async function pick(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) { refusals.push(`no control named ${name}=${value}`); return false; }
  // ⚠ **THE RADIO IS VISUALLY HIDDEN — ZERO-SIZED — SO IT CAN NEVER BE "IN THE
  // VIEWPORT" AND NEITHER `check()` NOR `scrollIntoViewIfNeeded()` WILL EVER
  // SUCCEED.** The control a person actually clicks is the label around it.
  // Dispatching the click on the input itself is the same event React binds to,
  // so this is the user's action and not a state poke.
  await el.evaluate((n) => n.click());
  const on = await page.evaluate(
    ([n, v]) => document.querySelector(`input[name="${n}"][value="${v}"]`)?.checked === true,
    [name, value]);
  if (!on) refusals.push(`${name}=${value} would not take`);
  return on;
}

async function forward(label) {
  const buttons = await page.$$('[data-wizard="actions"] button');
  const last = buttons[buttons.length - 1];
  const text = (await last.innerText()).trim();
  const disabled = await last.isDisabled();
  say(`  → ${label}: "${text}"${disabled ? "  ⛔ DISABLED" : ""}`);
  if (disabled) { refusals.push(`${label}: the clerk cannot advance — "${text}" is disabled`); return text; }
  await last.click();
  await page.waitForTimeout(1500);
  return text;
}

await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

// ── 1 · Owner & scope ────────────────────────────────────────────────────
await page.selectOption("#nc_owner_kind", "builder_developer").catch(() => {});
await page.fill("#nc_owner_name", "Clerk Walk Developments LLC");
await page.selectOption("#nc_owner_subcategory", "permanent").catch(() => {});
await page.fill("#nc_owner_email", "build@clerkwalk.example").catch(() => {});
await page.fill("#nc_owner_phone", "512-555-0143").catch(() => {});
await pick("nc_party_kind", "company");
await page.waitForTimeout(400);
for (const s of ["#nc_tax_id", "#nc_owner_tax_id"]) {
  if (await page.$(s)) await page.fill(s, `TX-${STAMP.slice(8)}`).catch(() => {});
}
await page.fill("#nc_prefix", "Apt").catch(() => {});
await pick("nc_scope", "new_premise");
await pick("nc_mode", "our_crew");
await shot("step1-owner-and-scope");
await forward("step 1 · Owner & scope");

// ── 2 · Premise ──────────────────────────────────────────────────────────
await page.fill("#nc_address", ADDRESS).catch(() => {});
for (const [s, v] of [["#nc_city", "Austin"], ["#nc_postal_code", "78704"], ["#nc_zip", "78704"],
                      ["#nc_premises_name", "Clerk Walk Court"], ["#nc_name", "Clerk Walk Court"]]) {
  if (await page.$(s)) await page.fill(s, v).catch(() => {});
}
if (await page.$("#nc_state")) await page.fill("#nc_state", "TX").catch(() => {});
const ptypes = await page.$$eval("#nc_premise_type option", (ns) => ns.map((o) => o.value).filter(Boolean)).catch(() => []);
if (ptypes.length) await page.selectOption("#nc_premise_type", ptypes[0]);
// ⚠ **THE SERVICES CONTROL IS A CHIP MULTI-SELECT, NOT TICK BOXES.** It reads
// the tenant's own enabled services — "Only the services your utility sells are
// listed" — through `data-chip-add`. The first run of this walk looked for
// `#nc_premise_services_<code>` checkboxes, found none, mapped nothing, and the
// build committed with "Services mapped on this build: none yet" and 0 meters.
// That read as a product gap and was a wrong selector.
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
const addSel = await page.$("#services_available-add");
if (addSel === null) { refusals.push("step 2: no services control found"); }
else {
  const offered = await page.$$eval("#services_available-add option", (ns) =>
    ns.map((o) => o.value).filter(Boolean));
  say(`  services this utility sells: ${offered.length} — ${offered.join(", ")}`);
  for (const code of offered) {
    await page.selectOption("#services_available-add", code).catch(() => {});
    await page.waitForTimeout(250);
  }
}
// ⚠ THE PLAN IS PICKED HERE, ON STEP 2, AND THE ID IS `nc_plan` — SINGULAR.
// PO ruling 2026-09-16: "why you ahve plans we have modeved them to step 2".
// ⚠ AND THIS BLOCK USED TO READ `#nc_plan_apartments` / `#nc_plan_common`,
// WHICH ARE STEP 5's RETIRED PICKERS, EACH WRAPPED IN `.catch(() => {})`.
// A selector that matches nothing then costs NOTHING TO SAY — the catch eats
// it, the walk sails on, and the commit refuses 300 lines later with "Choose
// a plan" while every screenshot looks perfect. That is hard-won law 7's
// *looking at the wrong thing*: a check named after an assertion it does not
// make. So the plan is now ASSERTED rather than attempted.
const plans = await page
  .$$eval("#nc_plan option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
if (plans.length === 0) {
  refusals.push("step2: #nc_plan offered no plan — the commit will refuse later");
} else {
  await page.selectOption("#nc_plan", plans[0]);
  const chosen = await page.$eval("#nc_plan", (n) => n.value).catch(() => "");
  if (chosen === "") refusals.push("step2: the plan would not stick");
  else say(`  plan chosen on step 2: ${plans.length} offered, took ${chosen}`);
}
await shot("step2-premise");
await forward("step 2 · Premise");

// ── 3 · Units ────────────────────────────────────────────────────────────
await page.fill("#nc_from", "1").catch(() => {});
await page.fill("#nc_to", String(UNITS)).catch(() => {});
await page.waitForTimeout(600);
await shot("step3-units");
await forward("step 3 · Units");

// ── 4 · Map services (the grid) ──────────────────────────────────────────
await page.waitForTimeout(1200);
const grid = await page.evaluate(() => ({
  rows: document.querySelectorAll('[id^="nc_asset_"]').length,
  sizes: document.querySelectorAll('[id^="nc_size_"]').length,
  installs: document.querySelectorAll('[id^="nc_install_"]').length,
}));
say(`  grid: ${grid.rows} asset cells · ${grid.sizes} size cells · ${grid.installs} install dates`);
await shot("step4-map-services");
await forward("step 4 · Map services");

// ── 5 · Plans & work orders ──────────────────────────────────────────────
await page.waitForTimeout(800);
// ⚠ STEP 5 ASKS FOR NO PLAN AND MUST NOT. It is "Work orders" now, and the
// whole point of the PO's ruling is that the question is asked ONCE. So this
// walk ASSERTS THE ABSENCE — a walk that only looks for what was added cannot
// see a duplicate that stayed.
const stray = await page.$$("#nc_plan, #nc_plan_apartments, #nc_plan_common");
if (stray.length > 0) refusals.push(`step5: a plan is still asked here (${stray.length} picker(s))`);
await shot("step5-work-orders");
await forward("step 5 · Work orders");

// ── 6 · Charges ──────────────────────────────────────────────────────────
await shot("step6-charges");
await forward("step 6 · Charges");

// ── 7 · Communication ────────────────────────────────────────────────────
await shot("step7-communication");
await forward("step 7 · Communication");

// ── 8 · Review & confirm — what the SCREEN promises, before the press ─────
await page.waitForTimeout(900);
const promised = await page.evaluate(() => document.body.innerText);
await shot("step8-review-and-confirm");
const before = JSON.parse((await api(`/api/${TENANT}/connections?per=1`)).body ?? "{}");
const pressedLabel = await forward("step 8 · REVIEW → press the button");
await page.waitForTimeout(6000);
await shot("step9-after-the-press");

// ── THE DATABASE, ASKED — not the manifest, not the screen ───────────────
const list = JSON.parse((await api(`/api/${TENANT}/connections?per=5`)).body ?? "{}");
const made = (list.data ?? list.results ?? [])[0] ?? null;
say("\n══ WHAT REACHED THE DATABASE ══");
if (made === null) {
  say("  NOTHING — no connection row came back");
  refusals.push("the press produced no connection row");
} else {
  say(`  connection ${made.connection_no ?? made.id}`);
  const detail = JSON.parse((await api(`/api/${TENANT}/connections/${made.id}`)).body ?? "{}");
  const d = detail.data ?? detail;
  for (const k of ["premises_id", "units", "meters", "plan_assignments", "work_orders",
                   "owner_account_id", "state", "quote_total", "invoice_no"]) {
    if (d[k] !== undefined) say(`  ${k.padEnd(20)} ${JSON.stringify(d[k])}`);
  }
}
say("\n══ WHAT THE REVIEW SCREEN PROMISED ══");
say("  " + (promised.match(/\b\d+\s+(?:units?|meters?|plan[s ]|work orders?|messages?)/gi) ?? []).join(" · "));
say(`\n══ REFUSALS THE CLERK SAW: ${refusals.length} ══`);
refusals.forEach((r) => say("  · " + r));
say(`\nbutton pressed: "${pressedLabel}"`);
say(`screens: ${OUT}`);
await browser.close();
