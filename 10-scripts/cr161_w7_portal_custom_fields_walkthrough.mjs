#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W7 — the utility's own questions on the customer
//          portal's new-service form, carried onto the service request and
//          copied on approval with the W6 side-by-side pick.
// Rules:   PO 2026-10-02 Part 2 row 16 · the Rules table (one utility only,
//          including on the portal; *"Ask the customer"* off by default;
//          required only where it is typed in) · hard-won law 6 (no gate reads
//          rendered output, so the proof is a browser)
// ───────────────────────────────────────────────────────
// The PO's worked example: *Roof Material* (Metal / Tile / Shingle) on
// Premises, switched to *Ask the customer* and marked required. The applicant
// answers **Tile** on the portal; leaving the box blank first says so ON the
// box and holds Continue; the server refuses Send without it. The clerk's
// Request detail shows Tile read-only; Approve against a property already
// holding **Metal** shows both with Metal chosen, the clerk picks Tile and the
// property reads Tile. A field left on *Don't ask* (*Meter vault code*) is on
// neither the portal screen nor the portal's API response, and another
// utility's portal shows none of it.
//
// Against a real API and PostgreSQL 16 seeded with `seed_demo` +
// `load_sample_data --tenant brazosbend` + `seed_portal_demo` (for a second
// utility with a live portal), the front end built with
// `vite build --mode wolocal` and served by `07-frontend/server.mjs`.
//
//   node 10-scripts/cr161_w7_portal_custom_fields_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8974) OUT (screenshot folder) PGURL (for the
//        audit read-back) OTHER (a second live portal, default pine-hill)
import { execFileSync } from "node:child_process";
import { mkdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8974";
const T = "brazosbend";
const OTHER = process.env.OTHER || "pine-hill";
const OUT = process.env.OUT || "/tmp/cr161-w7-shots";
const PGURL = process.env.PGURL || "postgres://postgres@127.0.0.1:55433/cf7_walk";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const ADDRESS = process.env.ADDRESS || "2201 Cane Island Pkwy";
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
  const path = `${OUT}/cf7_${name}.png`;
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
        return { status: r.status, text: await r.text() };
      },
      [method, `${BASE}/api/${tenant}${path}`, body],
    ).then((r) => {
      let parsed = null;
      try {
        parsed = JSON.parse(r.text);
      } catch {
        parsed = null;
      }
      return { status: r.status, body: parsed, text: r.text };
    });
}

const token = (tag) => `cf7${tag}${Date.now()}abcdefabcdef`;
const startDate = () => {
  const d = new Date();
  d.setDate(d.getDate() + 21);
  return d.toISOString().slice(0, 10);
};

const dialog = (p) => p.locator('[role="dialog"]');

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  // ── 1 · Settings: Roof Material → Ask the customer ───────────────────────
  const staffCtx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await staffCtx.newPage();
  p.setDefaultTimeout(40000);
  await p.goto(`${BASE}/${T}/signin`);
  await p.fill("#signin-email", "dana@brazosbendutilities.com");
  await p.fill("#signin-password", "S3cure!passw0rd");
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
    p.click('button[type="submit"]'),
  ]);
  const api = apiOn(p, T);
  console.log("\n── Settings: Roof Material on the portal form ──");
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
  const required = await api("PATCH", `/settings/custom-fields/${roof.id}`, { is_required: true });
  ok("Roof Material is required", required.status === 200, required.text.slice(0, 200));
  let vault = find("meter_vault_code");
  if (!vault) {
    vault = (
      await api("POST", "/settings/custom-fields", { label: "Meter vault code", entity: "premises", data_type: "text" })
    ).body;
  }
  const vaultPlaced = await api("PUT", `/settings/custom-fields/${vault.id}/placement`, { placement: { S16: "input" } });
  ok("Meter vault code is a clerk field only (Don't ask)", vaultPlaced.status === 200, vaultPlaced.text.slice(0, 200));

  // A re-run starts from a field placed nowhere, so "starts on Don't ask" is
  // asked of the default every time.
  const reset = await api("PUT", `/settings/custom-fields/${roof.id}/placement`, { placement: {} });
  ok("Roof Material starts placed nowhere", reset.status === 200, reset.text.slice(0, 200));
  await p.goto(`${BASE}/${T}/settings/reference-data/reference-data?list=custom_fields`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  await p.locator("tr", { hasText: "Roof Material" }).first().locator('button[aria-label="Placement"]').click();
  await dialog(p).waitFor();
  const text = (await dialog(p).textContent()) ?? "";
  ok("Placement offers the portal form", text.includes("New-service form"), text.slice(0, 300));
  ok("its choices are Ask the customer / Don't ask", text.includes("Ask the customer") && text.includes("Don't ask"));
  ok("no screen key printed", !/PORTAL_NEW_SERVICE/.test(text));
  ok("a field starts on Don't ask", (await p.locator("#placement-PORTAL_NEW_SERVICE").inputValue()) === "not_shown");
  await p.selectOption("#placement-PORTAL_NEW_SERVICE", "input");
  await p.selectOption("#placement-REQUEST_DETAIL", "view");
  await shot(p, "1_placement_ask_the_customer");
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  await p.waitForTimeout(1500);
  ok("placement saved", (await dialog(p).count()) === 0);
  const after = (await api("GET", "/settings/custom-fields")).body;
  const saved = (after?.results ?? after ?? []).find((r) => r.key === "roof_material");
  ok("stored: Ask the customer", saved?.placement?.PORTAL_NEW_SERVICE === "input", JSON.stringify(saved?.placement));

  // ── 2 · the applicant, on the portal ─────────────────────────────────────
  console.log("\n── The portal: step 2 asks Roof Material ──");
  const guestCtx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  const g = await guestCtx.newPage();
  g.setDefaultTimeout(40000);
  const tok = token("walk");
  await g.goto(`${BASE}/${T}/portal/start-service/${tok}?address=${encodeURIComponent(ADDRESS)}`, {
    waitUntil: "networkidle",
  });
  const block = g.locator('[data-portal-questions="premises"]');
  await block.waitFor({ timeout: 30000 });
  ok("step 2 draws the property's question", ((await block.textContent()) ?? "").includes("Roof Material"));
  const body = (await g.textContent("body")) ?? "";
  ok("the Don't-ask field is not on the screen", !body.includes("Meter vault code"));
  const wire = await g.evaluate(async (url) => (await fetch(url)).text(), `${BASE}/api/${T}/portal/public/applications/${tok}`);
  ok("the portal's API response names Roof Material", wire.includes("roof_material"));
  ok("…and never the Don't-ask field, its key or a placement", !/meter_vault_code|Meter vault code|placement|S16|REQUEST_DETAIL/.test(wire), wire.slice(0, 300));
  await g.fill("#requested_start", startDate());
  await g.locator("#requested_start").blur();
  const box = g.locator("#cf-premises-roof_material");
  await box.focus();
  await box.blur();
  await g.waitForTimeout(500);
  ok("a blank required box says so on the box", ((await g.locator('[data-field-error="cf-premises-roof_material"]').textContent()) ?? "").includes("Answer this question."));
  ok("…tied to the box (aria-invalid, aria-describedby)",
    (await box.getAttribute("aria-invalid")) === "true" &&
      (await g.locator(`#${await box.getAttribute("aria-describedby")}`).getAttribute("aria-live")) === "polite");
  ok("Continue is held", await g.locator('[data-action="continue"]').isDisabled());
  ok("…with its reason", ((await g.locator('[data-step-held="property_questions"]').textContent()) ?? "").includes("Answer the questions marked"));
  await block.scrollIntoViewIfNeeded();
  await shot(g, "2_portal_required_on_its_box");
  await box.selectOption("Tile");
  await g.waitForTimeout(1500);
  ok("choosing Tile frees Continue", !(await g.locator('[data-action="continue"]').isDisabled()));
  await shot(g, "3_portal_tile_chosen");
  await g.click('[data-action="continue"]');
  await g.waitForSelector('[data-step="about"]');
  await g.fill("#first_name", "Amara");
  await g.locator("#first_name").blur();
  await g.fill("#last_name", "Okafor");
  await g.locator("#last_name").blur();
  await g.fill("#email", "amara.okafor@example.test");
  await g.locator("#email").blur();
  await g.fill("#phone", "(281) 555-0144");
  await g.locator("#phone").blur();
  await g.waitForTimeout(1500);
  await g.click('[data-action="continue"]');
  await g.waitForSelector('[data-screen="CWP-009"]');
  await g.waitForTimeout(1500);
  ok("Check and send restates Roof Material Tile",
    ((await g.locator('[data-kv="cf-premises-roof_material"]').textContent()) ?? "").includes("Tile"));
  await shot(g, "4_portal_check_and_send");

  // The SERVER holds Send too: a second application with the box left blank.
  const blank = token("blank");
  const put = await g.evaluate(
    async ([url, start]) => {
      const r = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address_as_given: "2201 Cane Island Pkwy",
          service_codes: ["water"],
          applicant_kind: "person",
          first_name: "Lee",
          last_name: "Park",
          email: "lee@example.test",
          phone: "281-555-0100",
          requested_start: start,
        }),
      });
      return r.status;
    },
    [`${BASE}/api/${T}/portal/public/applications/${blank}`, startDate()],
  );
  const held = await g.evaluate(
    async (url) => {
      const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      return { status: r.status, body: await r.json() };
    },
    `${BASE}/api/${T}/portal/public/applications/${blank}/submit`,
  );
  ok("the server refuses Send without the required answer, naming the step",
    put === 200 && held.status === 422 && held.body?.params?.step === "property_questions", JSON.stringify(held.body).slice(0, 200));
  // …and refuses a Don't-ask key written from the portal.
  const sneak = await g.evaluate(
    async (url) => {
      const r = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ custom_data: { premises: { meter_vault_code: "999" } } }),
      });
      return r.status;
    },
    `${BASE}/api/${T}/portal/public/applications/${blank}`,
  );
  ok("the portal cannot write a Don't-ask field", sneak === 422, String(sneak));

  await g.click('[data-action="send"]');
  await g.waitForSelector("[data-reference]", { timeout: 30000 });
  const reference = ((await g.locator("[data-reference]").textContent()) ?? "").trim();
  ok("sent, with a reference", /^SR-/.test(reference), reference);
  await shot(g, "5_portal_sent");

  // ── 3 · the clerk: Request detail shows Tile, read-only ──────────────────
  console.log("\n── Request detail ──");
  const found = await api("GET", `/service-requests?q=${encodeURIComponent(reference)}`);
  const hit = (found.body?.results ?? []).find((r) => r.request_no === reference) ?? (found.body?.results ?? [])[0];
  const requestId = hit?.id;
  ok("the request is on the worklist", Boolean(requestId), found.text.slice(0, 200));
  let detail = await api("GET", `/service-requests/${requestId}`);
  ok("the request's own copy holds Tile", detail.body?.custom_data?.premises?.roof_material === "Tile", JSON.stringify(detail.body?.custom_data));
  await p.goto(`${BASE}/${T}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
  const view = p.locator("[data-request-custom-detail]");
  await view.locator("dt", { hasText: "Roof Material" }).waitFor({ timeout: 30000 });
  const dd = await view.locator("dt", { hasText: "Roof Material" }).locator("xpath=following-sibling::dd[1]").textContent();
  ok("Applicant tab reads Roof Material Tile, read-only", dd?.trim() === "Tile" && (await view.locator("select,input").count()) === 0, dd);
  await view.scrollIntoViewIfNeeded();
  await shot(p, "6_request_detail_tile");

  // ── 4 · Approve: the property holds Metal; Existing pre-selected ─────────
  console.log("\n── Approve ──");
  const picked = await api("GET", `/premises/picker?q=${encodeURIComponent(ADDRESS)}&per=50`);
  const premises = (picked.body?.results ?? []).find((r) => r.premise_no === PREMISE_NO);
  ok(`${PREMISE_NO} found`, Boolean(premises), picked.text.slice(0, 200));
  const metal = await api("PATCH", `/premises/${premises.id}`, { custom_data: { roof_material: "Metal" } });
  ok("the property holds Roof Material = Metal", metal.status === 200 && metal.body?.custom_data?.roof_material === "Metal", metal.text.slice(0, 200));
  // The clerk picks the property and its unit — what Approve's checks ask for
  // before a move-in (not this wave's subject; the W6 walk does it on screen).
  const unitId = execFileSync("psql", [PGURL, "-At", "-c",
    `select u.id from units u where u.premises_id='${premises.id}' order by u.unit_no limit 1`]).toString().trim();
  const resolved = await api("PATCH", `/service-requests/${requestId}`, {
    picked_premises_id: premises.id,
    picked_unit_id: unitId,
  });
  ok("the clerk points the request at the property", resolved.status === 200, resolved.text.slice(0, 300));
  await p.goto(`${BASE}/${T}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
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
  await conflict.scrollIntoViewIfNeeded();
  await shot(p, "7_approve_conflict");
  await requested.click();
  ok("the clerk picks Tile", (await requested.getAttribute("aria-checked")) === "true");
  const submit = dialog(p).locator("button", { hasText: /^Approve$/ }).last();
  const enabled = !(await submit.isDisabled());
  ok("Approve is enabled", enabled, ((await dialog(p).textContent()) ?? "").slice(0, 500));
  if (enabled) {
    await submit.click();
    await p.waitForTimeout(4000);
  }
  const prem = await api("GET", `/premises/${premises.id}`);
  ok("the property now reads Roof Material Tile", prem.body?.custom_data?.roof_material === "Tile", JSON.stringify(prem.body?.custom_data));
  detail = await api("GET", `/service-requests/${requestId}`);
  ok("the request is approved", detail.body?.header?.state === "approved", detail.body?.header?.state);
  const audit = execFileSync("psql", [PGURL, "-At", "-c",
    `select after::text from audit_log where action='service_request.custom_fields_copied' and entity_id='${requestId}'`]).toString().trim();
  ok("the audit row records the pick", audit.includes('"requested"') && audit.includes('"roof_material": "Tile"'), audit.slice(0, 300));
  console.log(`    audit: ${audit.slice(0, 300)}`);
  await shot(p, "8_after_approval");

  // ── 5 · another utility's portal shows none of it ───────────────────────
  console.log(`\n── ${OTHER}'s portal ──`);
  const otherTok = token("other");
  await g.goto(`${BASE}/${OTHER}/portal/start-service/${otherTok}?address=${encodeURIComponent("31 Palm Ct")}`, {
    waitUntil: "networkidle",
  });
  await g.waitForSelector('[data-step="when"]', { timeout: 30000 });
  await g.waitForTimeout(1500);
  const otherBody = (await g.textContent("body")) ?? "";
  ok(`${OTHER}'s form draws no question block`, (await g.locator("[data-portal-questions]").count()) === 0);
  ok(`${OTHER}'s form names neither field`, !otherBody.includes("Roof Material") && !otherBody.includes("Meter vault code"));
  const otherWire = await g.evaluate(async (url) => (await fetch(url)).text(), `${BASE}/api/${OTHER}/portal/public/applications/${otherTok}`);
  ok(`${OTHER}'s API response carries none of ${T}'s fields`, !/roof_material|Roof Material|meter_vault_code/.test(otherWire), otherWire.slice(0, 200));
  const crossRead = await g.evaluate(async (url) => (await fetch(url)).status, `${BASE}/api/${OTHER}/portal/public/applications/${tok}`);
  ok(`${OTHER} cannot open ${T}'s application`, crossRead === 404, String(crossRead));
  await shot(g, "9_other_utility_portal");
} finally {
  await browser.close();
}

console.log(`\n${pass} passed, ${failures.length} failed`);
if (failures.length) {
  for (const f of failures) console.log(`  FAIL ${f}`);
  process.exit(1);
}
