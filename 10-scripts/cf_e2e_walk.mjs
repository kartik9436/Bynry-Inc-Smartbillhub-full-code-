#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — the ONE end-to-end walk of tenant custom fields
//          across every record type (PO 2026-10-02: "we ahve to do it"),
//          with utility isolation as a MUST-PASS section (PO: "you ahve to
//          ensure utility isolation - we dont want these field to appear on
//          other utility screens") and the SEU mapping as a TEST-ONLY third
//          utility (PO: "use this only for testing purpose dont set it up").
// Rules:   the PO-agreed design (CR-161-BRC10 §R6, Parts 1–2, the Rules
//          table, the three gaps) · hard-won law 6 (no gate reads rendered
//          output, so the proof is a browser) · CLAUDE.md hard rule 1.
// ───────────────────────────────────────────────────────
// Three utilities on ONE scratch PostgreSQL 16 database:
//   A = brazosbend   one field on every record type, set up THROUGH SETTINGS
//   B = pine-hill    no fields of A's; the isolation and "no change" side,
//                    plus its OWN roof_material (same key, other options)
//   C = seu-test     the SEU mapping (13 fields), set up THROUGH SETTINGS at
//                    run time — never seeded, never a committed fixture.
//
// Database: `seed_demo` + `load_sample_data --tenant brazosbend` +
// `seed_portal_demo` + a scratch provisioning of `seu-test` (the lane's
// scratchpad, not this repository). Front end `vite build --mode wolocal`
// served by `07-frontend/server.mjs`.
//
//   PHASES=0,1,2 node 10-scripts/cf_e2e_walk.mjs
//   env: BASE · OUT (screenshots) · STATE (ids carried between phases) ·
//        PGURL (read-backs; a superuser URL is used ONLY for catalogue reads,
//        the RLS proof runs as a NOLOGIN NOSUPERUSER NOBYPASSRLS role)
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8932";
const OUT = process.env.OUT || "/tmp/cfe2e-shots";
const STATE = process.env.STATE || `${OUT}/state.json`;
const RESULTS = process.env.RESULTS || `${OUT}/results.json`;
const PGURL = process.env.PGURL || "postgres://postgres@127.0.0.1:55433/cfe2e_walk";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const PHASES = (process.env.PHASES || "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17").split(",").map((s) => s.trim());
mkdirSync(OUT, { recursive: true });

const A = { t: "brazosbend", email: "dana@brazosbendutilities.com", pw: "S3cure!passw0rd" };
const B = { t: "pine-hill", email: "sarah@pinehillwp.test", pw: "Pin3Hill!passw0rd" };
const C = { t: "seu-test", email: "admin@seutest.test", pw: "S3uTest!passw0rd" };

// ── results ────────────────────────────────────────────────────────────────
const state = existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : {};
const results = existsSync(RESULTS) ? JSON.parse(readFileSync(RESULTS, "utf8")) : { checks: {}, matrix: {} };
function save() {
  writeFileSync(STATE, JSON.stringify(state, null, 2));
  writeFileSync(RESULTS, JSON.stringify(results, null, 2));
}
let phase = "?";
let pass = 0;
const failures = [];
function ok(what, cond, detail = "", cell = null) {
  const good = Boolean(cond);
  const id = `${phase} · ${what}`;
  results.checks[id] = { ok: good, detail: good ? "" : String(detail).slice(0, 600) };
  if (cell) mark(cell[0], cell[1], good, cell[2]);
  if (good) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    failures.push(`${id} ${String(detail).slice(0, 400)}`);
    console.log(`  ✗ ${what} ${String(detail).slice(0, 400)}`);
  }
  return good;
}
/** A matrix cell is PASS only while every check feeding it passed. */
function mark(table, row, good, column) {
  const t = (results.matrix[table] ??= {});
  const r = (t[row] ??= {});
  r[column] = r[column] === false ? false : good;
}
async function shot(p, step, focus = null) {
  if (focus) {
    const el = p.locator(focus).first();
    if (await el.count()) await el.scrollIntoViewIfNeeded().catch(() => {});
  }
  await p.waitForTimeout(300);
  const path = `${OUT}/cfe2e_${phase}_${step}.png`;
  await p.screenshot({ path, fullPage: true });
  // A blank capture is not a proof: a white 1440×1000 PNG is ~5 KB.
  ok(`screenshot ${step} is not blank`, statSync(path).size > 20000, `${statSync(path).size} bytes`);
}

// ── browser + API helpers ──────────────────────────────────────────────────
const dialog = (p) => p.locator('[role="dialog"]');
const box = (p, key) => p.locator(`[id="custom_data.${key}"]`);
const norm = (s) => String(s ?? "").replace(/\s+/g, " ");
const mainText = async (p) => norm(await p.locator("main").first().innerText().catch(() => ""));
const bodyText = async (p) => norm(await p.locator("body").innerText().catch(() => ""));

async function signIn(browser, who) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(40000);
  p.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 500) console.log(`    [api ${r.status()}] ${r.request().method()} ${r.url()}`);
  });
  await p.goto(`${BASE}/${who.t}/signin`);
  await p.fill("#signin-email", who.email);
  await p.fill("#signin-password", who.pw);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
    p.click('button[type="submit"]'),
  ]);
  p.api = apiOn(p, who.t);
  p.who = who;
  return p;
}
function apiOn(p, tenant) {
  return (method, path, body) =>
    p
      .evaluate(
        async ([m, url, b]) => {
          const r = await fetch(url, {
            method: m,
            credentials: "include",
            headers: { "Content-Type": "application/json", Accept: "application/json" },
            body: b === undefined ? undefined : JSON.stringify(b),
          });
          return { status: r.status, text: await r.text() };
        },
        [method, path.startsWith("/api/") ? path : `/api/${tenant}${path}`, body],
      )
      .then((r) => {
        let parsed = null;
        try {
          parsed = JSON.parse(r.text);
        } catch {
          parsed = null;
        }
        return { status: r.status, body: parsed, text: r.text };
      });
}
const rowsOf = (b) => (Array.isArray(b) ? b : (b?.results ?? []));
function psql(sql, url = PGURL) {
  return execFileSync("psql", [url, "-At", "-c", sql]).toString().trim();
}

// ── Settings, driven as a clerk drives it ──────────────────────────────────
const CF = (t) => `${BASE}/${t}/settings/reference-data/reference-data?list=custom_fields`;
const TYPE_LABEL = { text: "Text", number: "Number", date: "Date", boolean: "Yes / No", select: "Pick one", multi_select: "Pick several" };
const ENTITY_LABEL = {
  accounts: "Accounts", customers: "Customers", contacts: "Contacts", addresses: "Addresses",
  service_agreements: "Service agreements", premises: "Premises", units: "Units", service_points: "Service points",
  assets: "Assets", work_orders: "Work orders", meter_reads: "Readings", routes: "Routes", areas: "Areas", payments: "Payments",
};
async function listFields(p) {
  return rowsOf((await p.api("GET", "/settings/custom-fields")).body);
}
/** Add one field through the Add custom field dialog. Returns the server row. */
async function addFieldViaSettings(p, f) {
  const have = (await listFields(p)).find((r) => r.entity === f.entity && r.label === f.label);
  if (have) {
    if (!have.is_active) await p.api("PATCH", `/settings/custom-fields/${have.id}`, { active: true });
    return have;
  }
  await p.goto(CF(p.who.t), { waitUntil: "networkidle" });
  await p.locator("button", { hasText: "+ Add custom field" }).first().click();
  await dialog(p).waitFor();
  await p.fill("#label", f.label);
  await p.selectOption("#entity", { label: ENTITY_LABEL[f.entity] });
  await p.selectOption("#data_type", { label: TYPE_LABEL[f.type] });
  if (f.options) await p.fill("#options", f.options.join("\n"));
  if (f.help) await p.fill("#help_text", f.help);
  if (f.required) await p.locator("#is_required").check({ force: true });
  const answer = p.waitForResponse((r) => r.url().endsWith("/settings/custom-fields") && r.request().method() === "POST", { timeout: 30000 });
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  const res = await answer;
  const body = await res.json().catch(() => ({}));
  await p.waitForTimeout(600);
  ok(`${p.who.t}: Settings adds ${f.label} (${f.entity}, ${f.type})`, res.status() === 201, `${res.status()} ${JSON.stringify(body).slice(0, 300)}`, f.cell ? [f.cell[0], f.cell[1], "set up"] : null);
  return body;
}
/** Open Placement for a label and choose each screen's mode; returns the dialog text. */
async function placeViaSettings(p, label, placement, { shotStep = null, expectRefusal = false } = {}) {
  await p.goto(CF(p.who.t), { waitUntil: "networkidle" });
  await p.locator("tr", { hasText: label }).first().locator('button[aria-label="Placement"]').click();
  await dialog(p).waitFor();
  for (const [key, mode] of Object.entries(placement)) {
    const sel = p.locator(`#placement-${key}`);
    if ((await sel.count()) === 0) {
      ok(`${p.who.t}: Placement for ${label} offers ${key}`, false, "no such choice on the dialog");
      continue;
    }
    await sel.selectOption(mode);
  }
  if (shotStep) await shot(p, shotStep);
  const text = norm(await dialog(p).textContent());
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  await p.waitForTimeout(1300);
  const open = (await dialog(p).count()) > 0;
  const after = open ? norm(await dialog(p).textContent()) : "";
  if (open && !expectRefusal) {
    ok(`${p.who.t}: Placement for ${label} saved`, false, after.slice(0, 400));
  }
  if (open) await dialog(p).getByRole("button", { name: "Cancel" }).click().catch(() => {});
  return { text, refused: open, after };
}

// ── the field plans ────────────────────────────────────────────────────────
// A — one field per record type; every type used at least once.
const A_FIELDS = [
  { entity: "accounts", label: "Contract ref", key: "contract_ref", type: "text", required: true,
    placement: { S18: "input", S21: "input", REQUEST_NEW: "input", REQUEST_DETAIL: "view" } },
  { entity: "customers", label: "Loyalty tier", key: "loyalty_tier", type: "select", options: ["Gold", "Silver"],
    placement: { S18: "input", NEW_CONNECTION_OWNER: "input", CUSTOMER_EDIT: "input", S21: "view", REQUEST_NEW: "input", REQUEST_DETAIL: "view", PORTAL_NEW_SERVICE: "input" } },
  { entity: "contacts", label: "Preferred name", key: "preferred_name", type: "text", required: true, placement: { S21: "input" } },
  { entity: "addresses", label: "Delivery note", key: "delivery_note", type: "text", placement: { S18: "input", S21: "input" } },
  { entity: "service_agreements", label: "Contract term", key: "contract_term", type: "select", options: ["12 months", "24 months"],
    placement: { S18: "input", S23: "input", S21: "view" } },
  { entity: "premises", label: "Roof Material", key: "roof_material", type: "select", options: ["Metal", "Tile", "Shingle"], required: true,
    placement: { PORTAL_NEW_SERVICE: "input", REQUEST_NEW: "input", NEW_CONNECTION_PREMISE: "input", S16: "input", PREMISE_EDIT: "input", PREMISE_PAGE: "view", S14: "view", REQUEST_DETAIL: "view" } },
  { entity: "premises", label: "Meter vault code", key: "meter_vault_code", type: "text", placement: { S16: "input", PREMISE_PAGE: "view" } },
  { entity: "units", label: "Gate code", key: "gate_code", type: "text", placement: { S16: "input", UNIT_ADD: "input", UNIT_EDIT: "input", PREMISE_UNITS: "view" } },
  { entity: "service_points", label: "Valve location", key: "valve_location", type: "text", placement: { S16: "input", UNIT_ADD: "input", PREMISE_UNITS: "view" } },
  { entity: "assets", label: "Warranty provider", key: "warranty_provider", type: "text", placement: { S51: "input", ASSET_EDIT: "input", S50: "view", S49: "view" } },
  { entity: "work_orders", label: "Crew radio", key: "crew_radio", type: "number", placement: { WORK_NEW: "input", WORK_EDIT: "input", WORK_DETAIL: "view" } },
  { entity: "meter_reads", label: "Seal number", key: "seal_number", type: "text", placement: { READ_ENTRY: "input", S29: "view" } },
  { entity: "routes", label: "Patrol day", key: "patrol_day", type: "multi_select", options: ["Mon", "Tue", "Wed", "Thu", "Fri"], placement: { ROUTE_FORM: "input", ROUTE_PAGE: "view" } },
  { entity: "areas", label: "Warden", key: "warden", type: "boolean", placement: { AREA_FORM: "input", AREA_LIST: "view" } },
  { entity: "payments", label: "Cheque date", key: "cheque_date", type: "date", placement: { S35: "input", S33: "view" } },
];
const RECORD_TYPES = [
  "accounts", "customers", "contacts", "addresses", "service_agreements", "premises", "units", "service_points",
  "assets", "work_orders", "meter_reads", "routes", "areas", "payments", "service_request", "portal",
];
// C — the SEU mapping, the PO's own definitions (2026-10-02), TEST ONLY.
const ACC = { PORTAL_NEW_SERVICE: "input", REQUEST_NEW: "input", S18: "input", S21: "input", REQUEST_DETAIL: "view" };
const PRM = { PORTAL_NEW_SERVICE: "input", REQUEST_NEW: "input", NEW_CONNECTION_PREMISE: "input", S16: "input", PREMISE_EDIT: "input", PREMISE_PAGE: "view", REQUEST_DETAIL: "view" };
const SEU_FIELDS = [
  { n: 1, entity: "accounts", label: "Name on DTE Bill", key: "name_on_dte_bill", type: "text", help: "As printed on DTE bill", placement: ACC, sample: "Maria L. Okafor" },
  { n: 2, entity: "accounts", label: "DTE Account Number", key: "dte_account_number", type: "text", help: "From your DTE bill", placement: ACC, sample: "9100 2233 4455" },
  { n: 3, entity: "accounts", label: "DTE Meter Number", key: "dte_meter_number", type: "text", help: "From your DTE bill", placement: ACC, sample: "DTE-77821" },
  { n: 4, entity: "accounts", label: "Budgetwise Enrolled", key: "budgetwise_enrolled", type: "boolean", placement: ACC, sample: true },
  { n: 5, entity: "premises", label: "Main Electric Panel Location", key: "main_electric_panel_location", type: "select",
    options: ["Basement", "Garage", "Utility room", "Outside wall", "Other", "Don't know"], placement: PRM, sample: "Utility room" },
  { n: 6, entity: "premises", label: "Roof Age", key: "roof_age", type: "select", options: ["0–5", "6–10", "11–20", "Over 20", "Don't know"],
    help: "Years since last replaced", placement: PRM, sample: "0–5" },
  { n: 7, entity: "premises", label: "Number of Stories", key: "number_of_stories", type: "select", options: ["1", "2", "3", "4 or more"], placement: PRM, sample: "4 or more" },
  { n: 8, entity: "premises", label: "Roof Material", key: "roof_material", type: "select",
    options: ["Asphalt shingle", "Metal", "Tile", "Slate", "Flat / membrane", "Wood shake", "Other", "Don't know"], placement: PRM, sample: "Flat / membrane" },
  { n: 9, entity: "premises", label: "Roof Shading", key: "roof_shading", type: "select",
    options: ["None", "Light (under 25%)", "Partial (25–50%)", "Heavy (over 50%)", "Don't know"], placement: PRM, sample: "Partial (25–50%)" },
  { n: 10, entity: "premises", label: "Generator on Site", key: "generator_on_site", type: "boolean", placement: PRM, sample: true },
  { n: 11, entity: "premises", label: "Generator Model", key: "generator_model", type: "text", help: "Only if you have one", placement: PRM, sample: "Generac 22kW" },
  { n: 12, entity: "premises", label: "EV Charged on Site", key: "ev_charged_on_site", type: "boolean", placement: PRM, sample: false },
  { n: 13, entity: "premises", label: "Appliances", key: "appliances", type: "multi_select",
    options: ["Gas furnace", "Electric furnace", "Heat pump", "Central A/C", "Gas water heater", "Electric water heater",
      "Heat-pump water heater", "Gas range", "Electric range", "Gas dryer", "Electric dryer", "None of these"],
    help: "Tick all that apply", placement: PRM, sample: ["Heat pump", "Electric range", "None of these"] },
];

/** BR-TEN-048 / DB-17 — every money path that must never read a tenant's own
 *  answers: rating, the ledger, payment allocation, and billing apart from the
 *  one module that stamps document-safe answers onto a printed bill. */
function grepMoneyPaths() {
  const root = new URL("../06-backend/apps/", import.meta.url).pathname;
  let out = "";
  try {
    out = execFileSync("grep", ["-rln", "custom_data", `${root}rating`, `${root}ledger`, `${root}billing`,
      `${root}payments/allocation.py`, `${root}payments/allocation_release.py`, "--include=*.py"]).toString();
  } catch (e) {
    out = (e.stdout ?? "").toString();
  }
  return out.split("\n").filter((l) => l && !/\/tests?\/|migrations|custom_snapshot\.py$/.test(l));
}

/** `manage.py shell -c` against the walk's database (the bill's stamp is a
 *  server function with no screen of its own until a bill is printed). */
function djShell(code) {
  const backend = new URL("../06-backend/", import.meta.url).pathname;
  const python = process.env.PYTHON || "/tmp/venv_a5c/bin/python";
  return execFileSync(python, ["manage.py", "shell", "-c", code], {
    cwd: backend,
    env: { ...process.env, DJANGO_SETTINGS_MODULE: "config.settings.local", DATABASE_URL: PGURL, JOBS_EAGER: "false" },
  }).toString();
}

const H = {
  grepMoneyPaths,
  djShell,
  ok, mark, shot, save, state, results, dialog, box, norm, mainText, bodyText, signIn, apiOn, rowsOf, psql,
  CF, listFields, addFieldViaSettings, placeViaSettings, BASE, OUT, PGURL, A, B, C, A_FIELDS, SEU_FIELDS, RECORD_TYPES,
  setPhase: (id) => { phase = id; },
};

// ── the phases live in their own module so the walk reads as one story ────
const { makePhases } = await import("./cf_e2e_walk_phases.mjs");
const PHASE_TABLE = makePhases(H);
const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const ctx = { browser, pages: {} };
try {
  for (const id of PHASES) {
    const run = PHASE_TABLE[id];
    if (!run) continue;
    phase = `p${id}`;
    console.log(`\n══ phase ${id} · ${run.title} ══`);
    try {
      await run.fn(ctx);
    } catch (e) {
      ok(`phase ${id} ran to its end`, false, (e && e.stack) || String(e));
      for (const p of Object.values(ctx.pages)) await p.keyboard.press("Escape").catch(() => {});
    }
    save();
  }
} finally {
  save();
  await browser.close();
}
console.log(`\n${pass} passed · ${failures.length} failed`);
for (const f of failures) console.log(`  FAILED: ${f}`);
process.exitCode = failures.length ? 1 : 0;
