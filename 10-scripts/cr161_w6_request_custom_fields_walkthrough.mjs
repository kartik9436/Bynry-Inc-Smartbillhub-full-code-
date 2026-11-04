#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W6 — the utility's own fields on the staff New
//          Request, read-only on the request, and copied on approval with the
//          R5 side-by-side pick (RULED C).
// Rules:   BR-TEN-052 (as amended 2026-10-02) · BR-TEN-048 · hard-won law 6
//          (no gate reads rendered output, so the proof is a browser)
// ───────────────────────────────────────────────────────
// The PO's worked example: *Roof Material* on Premises, Input on Staff New
// Request and View on Request detail. A request says **Tile** for a property
// already holding **Metal**; the review shows *Existing: Metal · Requested:
// Tile* with Metal pre-selected; the clerk picks Tile and the property reads
// Tile, with an audit row. A second field (*Gate code*) the property holds no
// answer for is simply copied. A utility with no fields sees no change.
//
// Against a real API and PostgreSQL 16 seeded with `seed_demo` +
// `load_sample_data --tenant brazosbend`, the front end built with
// `vite build --mode wolocal` and served by `07-frontend/server.mjs`.
//
//   node 10-scripts/cr161_w6_request_custom_fields_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8947) OUT (screenshot folder) PGURL (for the
//        audit read-back, e.g. postgres://postgres@127.0.0.1:55433/cf6_walk)
import { execFileSync } from "node:child_process";
import { mkdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8947";
const T = "brazosbend";
const OUT = process.env.OUT || "/tmp/cr161-w6-shots";
const PGURL = process.env.PGURL || "postgres://postgres@127.0.0.1:55433/cf6_walk";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const ADDRESS = process.env.ADDRESS || "2201 Cane Island";
const PREMISE_NO = process.env.PREMISE_NO || "P-00002";
mkdirSync(OUT, { recursive: true });

let pass = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    failures.push(`${what} ${detail}`);
    console.log(`  ✗ ${what} ${detail}`);
  }
}
async function shot(p, name) {
  const path = `${OUT}/cf6_${name}.png`;
  await p.screenshot({ path, fullPage: true });
  ok(`screenshot ${name} is not blank`, statSync(path).size > 20000, `${statSync(path).size} bytes`);
}

function apiOn(p, tenant) {
  return (method, path, body) =>
    p.evaluate(
      async ([m, url, b]) => {
        const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
        const r = await fetch(url, {
          method: m,
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: b === undefined ? undefined : JSON.stringify(b),
        });
        return { status: r.status, body: await r.json().catch(() => null) };
      },
      [method, `${BASE}/api/${tenant}${path}`, body],
    );
}

async function signIn(browser, tenant, email, password) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(40000);
  await p.goto(`${BASE}/${tenant}/signin`);
  await p.fill("#signin-email", email);
  await p.fill("#signin-password", password);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

const dialog = (p) => p.locator('[role="dialog"]');

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  const p = await signIn(browser, T, "dana@brazosbendutilities.com", "S3cure!passw0rd");
  const api = apiOn(p, T);

  // ── 1 · Settings: Roof Material, placed through the Placement dialog ─────
  console.log("\n── Settings: Roof Material on New request (Input) and Request detail (View) ──");
  const listed = await api("GET", "/settings/custom-fields");
  const rows = listed.body?.results ?? listed.body ?? [];
  const find = (key) => (Array.isArray(rows) ? rows.find((r) => r.key === key) : undefined);
  let roof = find("roof_material");
  if (!roof) {
    roof = (
      await api("POST", "/settings/custom-fields", {
        label: "Roof Material",
        entity: "premises",
        data_type: "select",
        options: ["Metal", "Tile", "Shingle"],
      })
    ).body;
  }
  let gate = find("gate_code");
  if (!gate) {
    gate = (await api("POST", "/settings/custom-fields", { label: "Gate code", entity: "premises", data_type: "text" })).body;
  }
  ok("two premises fields defined", Boolean(roof?.id && gate?.id));
  await p.goto(`${BASE}/${T}/settings/reference-data/reference-data?list=custom_fields`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  await p.locator("tr", { hasText: "Roof Material" }).first().locator('button[aria-label="Placement"]').click();
  await dialog(p).waitFor();
  const text = (await dialog(p).textContent()) ?? "";
  ok("Placement offers New request", text.includes("New request"), text.slice(0, 300));
  ok("Placement offers Request detail", text.includes("Request detail"));
  ok("no screen key printed", !/REQUEST_NEW|REQUEST_DETAIL/.test(text));
  await p.selectOption("#placement-REQUEST_NEW", "input");
  await p.selectOption("#placement-REQUEST_DETAIL", "view");
  await shot(p, "1_placement");
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  await p.waitForTimeout(1500);
  ok("placement saved", (await dialog(p).count()) === 0);
  const gatePlaced = await api("PUT", `/settings/custom-fields/${gate.id}/placement`, {
    placement: { REQUEST_NEW: "input" },
  });
  ok("Gate code placed on New request", gatePlaced.status === 200, JSON.stringify(gatePlaced.body).slice(0, 200));

  // ── 2 · the property already says Metal ──────────────────────────────────
  const picked = await api("GET", `/premises/picker?q=${encodeURIComponent(ADDRESS)}&per=50`);
  const premises = (picked.body?.results ?? []).find((r) => r.premise_no === PREMISE_NO);
  ok(`${PREMISE_NO} found by the picker`, Boolean(premises), JSON.stringify(picked.body).slice(0, 200));
  const metal = await api("PATCH", `/premises/${premises.id}`, { custom_data: { roof_material: "Metal", gate_code: null } });
  ok("the property holds Roof Material = Metal", metal.status === 200 && metal.body?.custom_data?.roof_material === "Metal",
    JSON.stringify(metal.body).slice(0, 300));

  // ── 3 · New request: type Tile and 4471 on step 2 ────────────────────────
  console.log("\n── New request ──");
  await p.goto(`${BASE}/${T}/requests/new?step=1`, { waitUntil: "networkidle" });
  await p.waitForSelector("#account_type_code", { timeout: 30000 });
  ok("step 1: no custom panel (no customer or account field placed)",
    (await p.locator("[data-request-custom-input]").count()) === 0);
  await p.fill("#applicant_name", "Rivera, Elena");
  await p.selectOption("#account_type_code", { index: 1 });
  await p.locator("button", { hasText: /^Continue/ }).last().click();
  await p.waitForSelector("#address_as_given", { timeout: 30000 });
  await p.fill("#address_as_given", ADDRESS);
  await p.waitForTimeout(2500);
  await p.locator(`[data-premises-option="${PREMISE_NO}"]`).first().click();
  await p.waitForTimeout(1000);
  if ((await p.locator("select#address_unit_as_given").count()) > 0) {
    await p.selectOption("select#address_unit_as_given", { index: 1 });
  }
  const panel = p.locator('[data-request-custom-input="premises"]');
  await panel.waitFor({ timeout: 30000 });
  ok("step 2 draws the Property fields panel", (await panel.textContent()).includes("Roof Material"));
  await p.selectOption('[id="custom_data.roof_material"]', "Tile");
  await p.fill('[id="custom_data.gate_code"]', "4471");
  await panel.scrollIntoViewIfNeeded();
  await shot(p, "2_new_request_step2");
  await p.locator("button", { hasText: /^Continue/ }).last().click();
  await p.waitForTimeout(3000);
  const requestId = new URL(p.url()).searchParams.get("request");
  ok("the draft exists", Boolean(requestId), p.url());
  let detail = await api("GET", `/service-requests/${requestId}`);
  ok("the request's own copy holds Tile and 4471",
    detail.body?.custom_data?.premises?.roof_material === "Tile" && detail.body?.custom_data?.premises?.gate_code === "4471",
    JSON.stringify(detail.body?.custom_data));

  await p.goto(`${BASE}/${T}/requests/new?step=4&request=${requestId}`, { waitUntil: "networkidle" });
  const recap = p.locator("[data-custom-answers=premises]");
  await recap.waitFor({ timeout: 30000 });
  ok("step 4 lists Roof Material Tile", ((await recap.textContent()) ?? "").includes("Tile"));
  await recap.scrollIntoViewIfNeeded();
  await shot(p, "3_review_recap");

  // Submit, and the arrears search the approval needs (not this wave's subject).
  const submitted = await api("POST", `/service-requests/${requestId}/submit`, {});
  ok("submitted", submitted.status === 200, JSON.stringify(submitted.body).slice(0, 300));

  // ── 4 · Request detail shows the request's copy (gap 2) ──────────────────
  console.log("\n── Request detail ──");
  await p.goto(`${BASE}/${T}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
  const view = p.locator("[data-request-custom-detail]");
  await view.locator("dt", { hasText: "Roof Material" }).waitFor({ timeout: 30000 });
  const dd = await view.locator("dt", { hasText: "Roof Material" }).locator("xpath=following-sibling::dd[1]").textContent();
  ok("Applicant tab reads Roof Material Tile, read-only", dd?.trim() === "Tile" && (await view.locator("select,input").count()) === 0, dd);
  await view.scrollIntoViewIfNeeded();
  await shot(p, "4_request_detail");

  // ── 5 · Approve: Existing Metal pre-selected, pick Tile ──────────────────
  console.log("\n── Approve ──");
  await p.locator('[data-decision-action="approve"]').first().click();
  await dialog(p).waitFor();
  await p.locator('[data-segment="move_in"]').first().click();
  await p.waitForTimeout(800);
  // PO 2026-10-11, option B: the Arrears row only POINTS at Search customer
  // (`[data-approve-arrears-search]`); run the search, then its *No match*
  // (`data-action="record-search"`), which records it.
  if ((await dialog(p).locator("[data-approve-arrears-search]").count()) > 0) {
    await dialog(p).locator("[data-customer-search]").first().click();
    const search = dialog(p).locator('[data-action="record-search"]');
    await search.first().waitFor({ timeout: 15000 });
    await search.first().click();
    await p.waitForTimeout(2500);
    if ((await dialog(p).count()) === 0) {
      await p.locator('[data-decision-action="approve"]').first().click();
      await dialog(p).waitFor();
    }
    await p.locator('[data-segment="move_in"]').first().click();
    await p.waitForTimeout(800);
  }
  const conflict = dialog(p).locator('[data-copy-row="roof_material"]');
  await conflict.waitFor({ timeout: 30000 });
  ok("Roof Material is a conflict", (await conflict.getAttribute("data-copy-state")) === "conflict");
  const existing = conflict.locator('[data-segment="existing"]');
  const requested = conflict.locator('[data-segment="requested"]');
  ok("Existing: Metal is shown and pre-selected",
    ((await existing.textContent()) ?? "").includes("Metal") && (await existing.getAttribute("aria-checked")) === "true");
  ok("Requested: Tile is shown beside it", ((await requested.textContent()) ?? "").includes("Tile"));
  ok("Gate code with nothing held is copied",
    ((await dialog(p).locator('[data-copy-row="gate_code"]').textContent()) ?? "").includes("4471 · added"));
  await conflict.scrollIntoViewIfNeeded();
  await shot(p, "5_approve_conflict");
  await requested.click();
  ok("the clerk picks Tile", (await requested.getAttribute("aria-checked")) === "true");
  await shot(p, "6_approve_picked_tile");
  const submit = dialog(p).locator('button[type="submit"]').last();
  ok("Approve is enabled", !(await submit.isDisabled()), (await dialog(p).textContent())?.slice(0, 400));
  await submit.click();
  await p.waitForTimeout(4000);

  // ── 6 · the property reads Tile, the audit row exists ───────────────────
  const after = await api("GET", `/premises/${premises.id}`);
  ok("the property now reads Roof Material Tile", after.body?.custom_data?.roof_material === "Tile", JSON.stringify(after.body?.custom_data));
  ok("Gate code 4471 was copied", after.body?.custom_data?.gate_code === "4471");
  detail = await api("GET", `/service-requests/${requestId}`);
  ok("the request is approved", detail.body?.header?.state === "approved", detail.body?.header?.state);
  ok("the request keeps its own copy", detail.body?.custom_data?.premises?.roof_material === "Tile");
  const audit = execFileSync("psql", [PGURL, "-At", "-c",
    `select after::text from audit_log where action='service_request.custom_fields_copied' and entity_id='${requestId}'`]).toString().trim();
  ok("the audit row records the pick and the copy",
    audit.includes('"requested"') && audit.includes('"roof_material": "Tile"') && audit.includes('"gate_code": "4471"'), audit.slice(0, 400));
  console.log(`    audit: ${audit.slice(0, 300)}`);
  await shot(p, "7_after_approval");

  // ── 7 · a utility with no fields sees no change ─────────────────────────
  // Both fields switched OFF: the utility now has no active field anywhere a
  // request reads, which is the zero-field case (this scratch database holds
  // one utility).
  console.log("\n── No active fields ──");
  for (const field of [roof, gate]) {
    const off = await api("PATCH", `/settings/custom-fields/${field.id}`, { active: false });
    ok(`${field.key} switched off`, off.status === 200, JSON.stringify(off.body).slice(0, 200));
  }
  await p.goto(`${BASE}/${T}/requests/new?step=2`, { waitUntil: "networkidle" });
  await p.waitForSelector("#address_as_given", { timeout: 30000 });
  await p.waitForTimeout(1500);
  ok("New request step 2 draws no custom panel", (await p.locator("[data-request-custom-input]").count()) === 0);
  await shot(p, "8_no_fields_new_request");
  await p.goto(`${BASE}/${T}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  ok("the request's page draws no custom section", (await p.locator("[data-request-custom-detail] section").count()) === 0);
  const kept = await api("GET", `/service-requests/${requestId}`);
  ok("the answers are kept on the request (switched off, not deleted)", kept.body?.custom_data?.premises?.roof_material === "Tile");
  ok("Approve would copy nothing", (kept.body?.custom_field_copy ?? []).length === 0);
  for (const field of [roof, gate]) {
    await api("PATCH", `/settings/custom-fields/${field.id}`, { active: true });
  }
} finally {
  await browser.close();
}
console.log(`\n${pass} passed, ${failures.length} failed`);
for (const f of failures) console.log(`  ✗ ${f}`);
process.exit(failures.length === 0 ? 0 : 1);
