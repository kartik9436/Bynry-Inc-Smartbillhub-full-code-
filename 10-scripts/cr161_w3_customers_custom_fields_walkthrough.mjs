#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 waves W2 + W3, customers lane — contacts, mailing
//          addresses and service agreements, and New Connection Step 1
// Defects: DEF-CUS-9168 · DEF-CUS-9169 · DEF-CUS-9170 (DEF-CUS-9159 is proved by
//          10-scripts/po20260929_new_connect_press_create.mjs, which types into
//          Step 1's Account details whatever the utility defined)
// Rules:   BR-TEN-052 as amended 2026-10-02 · hard-won law 6 (no gate reads
//          rendered output, so the proof is a browser)
// ───────────────────────────────────────────────────────
// THE SAME STEPS AS THE REPRODUCTION, AFTER THE FIX, against a real API and a
// real PostgreSQL 16 database. It WRITES rows — run it against a private clone.
// It creates (or reuses) three fields and places them:
//   Preferred name (Contacts)            Account contacts · Input
//   Delivery note  (Addresses)           New account mailing · Input ; Account mailing address · Input
//   Contract term  (Service agreements)  New account services · Input ; Change plan · Input ; Account services · View
//
//   node 10-scripts/cr161_w3_customers_custom_fields_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8948) OUT ACCOUNT (an account number with a
//        contact and an open service) UNIT (a vacant unit number with services)
import { createRequire } from "node:module";
import { mkdirSync, statSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8948";
const T = process.env.TENANT || "brazosbend";
const ADMIN = process.env.ADMIN || "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD || "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/cr161-w3-shots";
const ACCOUNT = process.env.ACCOUNT || "AC-2026-00012";
const UNIT = process.env.UNIT || "U-00102";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });
// A per-run stamp, so a re-run against the same database still CHANGES each
// value — an unchanged value is rightly not sent, and a check would misread it.
const RUN = new Date().toISOString().replace(/[^0-9]/g, "").slice(8, 14);
const NICK = `Johnny ${RUN}`;
const NOTE = `Side door ${RUN}`;
const TERM = `24 months ${RUN}`;

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
async function shot(p, name, focus = null) {
  // `fullPage` returns the fold here (`.view` is the scrolling pane), so a group
  // below it is scrolled into view first.
  if (focus !== null) await p.locator(focus).first().scrollIntoViewIfNeeded();
  const path = `${OUT}/cf3a_after_${name}.png`;
  await p.screenshot({ path, fullPage: true });
  // A blank capture is not a proof: a white 1440×1000 PNG is ~5 KB.
  ok(`screenshot ${name} is not blank`, statSync(path).size > 20000, `${statSync(path).size} bytes`);
}
const dialog = (p) => p.locator('[role="dialog"]');
const main = async (p) => ((await p.locator("main").textContent()) ?? "").replace(/\s+/g, " ");

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
try {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(40000);
  // Every PATCH the page sends, in order — a check reads the WHOLE list, so a
  // second request cannot hide behind the first one a wait happened to catch.
  const patches = [];
  p.on("request", (r) => {
    if (r.method() === "PATCH") patches.push({ url: r.url(), body: r.postData() });
  });
  await p.goto(`${BASE}/${T}/signin`);
  await p.fill("#signin-email", ADMIN);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 }),
    p.click('button[type="submit"]'),
  ]);
  const api = (method, path, body) =>
    p.evaluate(
      async ([m, u, b]) => {
        const r = await fetch(u, {
          method: m,
          credentials: "include",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: b === undefined ? undefined : JSON.stringify(b),
        });
        let j = null;
        try {
          j = await r.json();
        } catch {
          j = null;
        }
        return { status: r.status, body: j };
      },
      [method, `/api/${T}${path}`, body],
    );

  console.log("── setup · three fields, placed on the screens W3 drew ──");
  const existing = (await api("GET", "/settings/custom-fields")).body ?? [];
  const rows = Array.isArray(existing) ? existing : (existing.results ?? []);
  async function ensure(entity, label, placement, extra = {}) {
    let row = rows.find((r) => r.entity === entity && r.label === label);
    if (!row) row = (await api("POST", "/settings/custom-fields", { entity, label, data_type: "text", ...extra })).body;
    else {
      // A re-run: switch it back on and optional again, as a first run finds it.
      await api("PATCH", `/settings/custom-fields/${row.id}`, { active: true });
      await api("PATCH", `/settings/custom-fields/${row.id}`, { is_required: false });
    }
    const saved = await api("PUT", `/settings/custom-fields/${row.id}/placement`, { placement });
    ok(`${label} placed ${JSON.stringify(placement)}`, saved.status === 200, JSON.stringify(saved.body).slice(0, 300));
    return row;
  }
  const preferred = await ensure("contacts", "Preferred name", { S21: "input" });
  await ensure("addresses", "Delivery note", { S18: "input", S21: "input" });
  const term = await ensure("service_agreements", "Contract term", { S18: "input", S23: "input", S21: "view" });
  const slots = (await api("GET", "/settings/custom-fields/slots")).body.entities;
  for (const entity of ["contacts", "addresses", "service_agreements"]) {
    const row = slots.find((e) => e.entity === entity);
    ok(`Settings offers ${entity} now`, row.offered === true, JSON.stringify(row.slots.filter((s) => s.rendered).map((s) => s.key)));
  }

  console.log("\n── Settings · Contract term's placement names its three screens ──");
  await p.goto(`${BASE}/${T}/settings/reference-data/reference-data?list=custom_fields`, { waitUntil: "networkidle" });
  await p.locator("tr", { hasText: "Contract term" }).first().locator('button[aria-label="Placement"]').click();
  await dialog(p).waitFor();
  const placementText = ((await dialog(p).textContent()) ?? "").replace(/\s+/g, " ");
  ok(
    "the dialog names New account services, Change plan and Account services",
    ["New account services", "Change plan", "Account services"].every((w) => placementText.includes(w)),
    placementText.slice(0, 400),
  );
  await shot(p, "1_settings_placement_contract_term");
  await dialog(p).getByRole("button", { name: "Cancel" }).click();

  const list = (await api("GET", `/accounts?q=${ACCOUNT}`)).body.results;
  const account = list.find((r) => r.account_no === ACCOUNT) ?? list[0];

  console.log("\n── DEF-CUS-9168 · the contact edit and the Customer group ──");
  await p.goto(`${BASE}/${T}/accounts/${account.id}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  await p.locator('[data-overview-group="customer"] button').first().click();
  await dialog(p).waitFor();
  const contactBox = p.locator('[id="custom_data.preferred_name"]');
  await contactBox.waitFor({ timeout: 20000 }).catch(() => {});
  ok("the Customer edit offers Preferred name", (await contactBox.count()) === 1);
  await contactBox.fill(NICK);
  await shot(p, "2_contact_edit_dialog");
  const sentBefore = patches.length;
  let patch = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  let patched = await patch;
  await p.waitForTimeout(500);
  const contactPatches = patches.slice(sentBefore);
  ok(
    "one PATCH, and only the change travels",
    contactPatches.length === 1 &&
      contactPatches[0].url.endsWith("/contact") &&
      contactPatches[0].body === JSON.stringify({ custom_data: { preferred_name: NICK } }),
    JSON.stringify(contactPatches),
  );
  ok("PATCH /contact answers 200", patched.status() === 200, String(patched.status()));
  await p.waitForTimeout(1500);
  const customerGroup = ((await p.locator('[data-overview-group="customer"]').textContent()) ?? "").replace(/\s+/g, " ");
  ok("the Customer group shows the new Preferred name", customerGroup.includes("Preferred name") && customerGroup.includes(NICK), customerGroup.slice(0, 300));
  await shot(p, "3_account_detail_customer_group");

  console.log("\n── required binds on the contact edit only, and the form is kept ──");
  await api("PATCH", `/settings/custom-fields/${preferred.id}`, { is_required: true });
  await p.reload({ waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  await p.locator('[data-overview-group="customer"] button').first().click();
  await dialog(p).waitFor();
  await p.locator('[id="custom_data.preferred_name"]').waitFor();
  await p.fill("#contact_phone", "+1 (281) 555-0188");
  await p.locator('[id="custom_data.preferred_name"]').fill("");
  patch = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  patched = await patch;
  ok("a blank required Preferred name is refused 422", patched.status() === 422, String(patched.status()));
  await p.waitForTimeout(800);
  ok("the dialog stays open with the phone still typed", (await dialog(p).count()) === 1 && (await p.inputValue("#contact_phone")) === "+1 (281) 555-0188");
  const dialogText = ((await dialog(p).textContent()) ?? "").replace(/\s+/g, " ");
  ok("the refusal is on the screen", /required|needs|fill/i.test(dialogText), dialogText.slice(0, 300));
  await shot(p, "4_contact_required_refused_form_kept");
  await dialog(p).getByRole("button", { name: "Cancel" }).click();

  console.log("\n── DEF-CUS-9169 · the mailing edit and the Mailing address group ──");
  await p.locator('[data-overview-group="mailing-address"] button').first().click();
  await dialog(p).waitFor();
  await p.fill("#mailing_line1", "PO Box 4471");
  await p.fill("#mailing_city", "Austin");
  await p.fill("#mailing_state", "TX");
  await p.fill("#mailing_postal_code", "78701");
  const noteBox = p.locator('[id="custom_data.delivery_note"]');
  await noteBox.waitFor({ timeout: 20000 }).catch(() => {});
  ok("the mailing edit offers Delivery note", (await noteBox.count()) === 1);
  await noteBox.fill(NOTE);
  patch = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
  await dialog(p).locator('button[data-variant="primary"]').last().click();
  patched = await patch;
  ok("PATCH /mailing-address answers 200 carrying the note", patched.status() === 200 && JSON.stringify(patched.request().postDataJSON()).includes(NOTE), `${patched.status()} ${JSON.stringify(patched.request().postDataJSON())}`);
  await p.waitForTimeout(1500);
  const mailingGroup = ((await p.locator('[data-overview-group="mailing-address"]').textContent()) ?? "").replace(/\s+/g, " ");
  ok("the Mailing address group shows Delivery note", mailingGroup.includes("Delivery note") && mailingGroup.includes(NOTE), mailingGroup.slice(0, 300));
  await shot(p, "5_account_detail_mailing_group", '[data-overview-group="mailing-address"]');

  console.log("\n── DEF-CUS-9170 · New Account: mailing and service fields, active create ──");
  await p.goto(`${BASE}/${T}/accounts/new`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  await p.selectOption("#account_type", "residential");
  await p.fill("#full_name", "Rosa Pemberton");
  await p.fill("#email", "rosa.pemberton@example.com");
  await p.fill("#phone", "(281) 555-0199");
  if (await p.locator("#gov_id_last4").count()) await p.fill("#gov_id_last4", "4471");
  await p.getByText("Person", { exact: true }).first().click();
  ok("New Account opens with no address field while mailing is the service address", (await p.locator('[id="custom_data.delivery_note"]').count()) === 0);
  await p.locator("#mailing_same").setChecked(false, { force: true });
  await p.fill("#mailing_line1", "PO Box 9");
  await p.fill("#mailing_city", "Katy");
  await p.locator("#mailing_state").fill("TX");
  const stateOption = p.locator('[role="option"]', { hasText: "TX" }).first();
  if (await stateOption.count()) await stateOption.click();
  await p.fill("#mailing_postal_code", "77494");
  await p.locator('[id="custom_data.delivery_note"]').fill("Ring twice");
  await shot(p, "6_new_account_mailing_field", '[id="custom_data.delivery_note"]');
  const cont = async () => {
    await p.locator("button", { hasText: /^Continue/ }).first().click();
    await p.waitForTimeout(1500);
  };
  await cont();
  await p.locator("#unit_id").fill(UNIT);
  const option = p.locator('[role="option"]', { hasText: UNIT }).first();
  await option.waitFor({ timeout: 60000 });
  await option.click();
  await p.fill("#opened_at", "2026-10-02");
  await p.locator('[id="custom_data.contract_term"]').fill("12 months");
  await shot(p, "7_new_account_unit_step_contract_term", '[id="custom_data.contract_term"]');
  await cont();
  await cont();
  await cont();
  const answer = p.waitForResponse(
    (r) => r.url().endsWith(`/api/${T}/accounts`) && r.request().method() === "POST",
    { timeout: 60000 },
  );
  await p.locator('button[data-variant="primary"]').last().click();
  const res = await answer;
  const created = await res.json().catch(() => ({}));
  ok("POST /accounts answers 201", res.status() === 201, `${res.status()} ${JSON.stringify(created).slice(0, 400)}`);
  const fresh = (await api("GET", `/accounts/${created.id}`)).body;
  ok("the mailing row carries Delivery note = Ring twice", fresh?.addresses?.find((a) => a.kind === "mailing")?.custom_data?.delivery_note === "Ring twice");
  ok(
    "every service the account opened carries Contract term = 12 months",
    (fresh?.service_agreements ?? []).length > 0 && fresh.service_agreements.every((a) => a.custom_data?.contract_term === "12 months"),
    JSON.stringify(fresh?.service_agreements?.map((a) => a.custom_data)),
  );
  await p.goto(`${BASE}/${T}/accounts/${created.id}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const serviceGroup = ((await p.locator('[data-overview-group="service"]').textContent()) ?? "").replace(/\s+/g, " ");
  ok("Account detail → Services shows Contract term per service", serviceGroup.includes("Contract term") && serviceGroup.includes("12 months"), serviceGroup.slice(0, 400));
  await shot(p, "8_account_detail_services_group", '[data-overview-group="service"]');

  console.log("\n── DEF-CUS-9170 · Change plan: the confirm step merges into every open service ──");
  await p.goto(`${BASE}/${T}/accounts/${account.id}/change-plan`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const radios = p.locator('input[type="radio"][name="rate_plan_id"]:not([disabled]):not(:checked)');
  if ((await radios.count()) > 0) {
    await p.locator(`label[for="${await radios.first().getAttribute("id")}"]`).click();
    if (await p.locator("#drop_ack").count()) await p.locator("#drop_ack").check();
    await cont();
    await p.fill("#effective_on", "2026-11-01");
    const previewButton = p.locator("button", { hasText: /preview/i }).first();
    if (await previewButton.count()) {
      await previewButton.click();
      await p.waitForTimeout(2000);
    }
    await cont();
    const termBox = p.locator('[id="custom_data.contract_term"]');
    await termBox.waitFor({ timeout: 20000 }).catch(() => {});
    ok("the confirm step offers Contract term", (await termBox.count()) === 1);
    await termBox.fill(TERM);
    await shot(p, "9_change_plan_confirm_contract_term", '[id="custom_data.contract_term"]');
    const confirm = p.waitForResponse((r) => r.url().endsWith("/plan-changes") && r.request().method() === "POST", { timeout: 60000 });
    await p.locator('button[data-variant="primary"]').last().click();
    const confirmed = await confirm;
    ok("POST /plan-changes carries service_custom_data", JSON.stringify(confirmed.request().postDataJSON()).includes(JSON.stringify({ service_custom_data: { contract_term: TERM } }).slice(1, -1)), JSON.stringify(confirmed.request().postDataJSON()));
    ok("POST /plan-changes answers 200/201", [200, 201].includes(confirmed.status()), `${confirmed.status()} ${(await confirmed.text()).slice(0, 300)}`);
    const after = (await api("GET", `/accounts/${account.id}`)).body;
    const open = after.service_agreements.filter((a) => a.ended_on === null);
    ok("every open service now reads the new term", open.length > 0 && open.every((a) => a.custom_data?.contract_term === TERM), JSON.stringify(open.map((a) => a.custom_data)));
  } else {
    ok("Change plan offers another plan to move to", false, "no selectable plan on this account");
  }

  console.log("\n── isolation · another utility sees none of these definitions ──");
  for (const entity of ["contacts", "addresses", "service_agreements"]) {
    const here = await api("GET", `/custom-fields?entity=${entity}`);
    ok(`${entity}: this utility's registry holds its field`, (here.body?.fields ?? []).length >= 1);
  }
  const other = await p.evaluate(async () => (await fetch("/api/sixrivers/custom-fields?entity=contacts", { credentials: "include" })).status);
  ok("another utility's registry is not readable with this session", other === 403 || other === 404 || other === 401, String(other));

  console.log("\n── zero fields · every touched screen is unchanged ──");
  for (const id of [preferred.id, term.id]) await api("PATCH", `/settings/custom-fields/${id}`, { active: false });
  const note = rows.find((r) => r.label === "Delivery note") ?? (await api("GET", "/settings/custom-fields")).body.find?.((r) => r.label === "Delivery note");
  if (note) await api("PATCH", `/settings/custom-fields/${note.id}`, { active: false });
  const deactivated = (await api("GET", "/custom-fields?entity=contacts")).body?.fields ?? [];
  ok("deactivated fields leave the registry", deactivated.length === 0, JSON.stringify(deactivated).slice(0, 200));
  await p.goto(`${BASE}/${T}/accounts/${created.id}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  const bare = await main(p);
  ok("Account detail shows no custom field", !bare.includes("Contract term") && !bare.includes("Delivery note") && !bare.includes("Preferred name"));
  await p.locator('[data-overview-group="customer"] button').first().click();
  await dialog(p).waitFor();
  await p.waitForTimeout(800);
  ok("the Customer edit has no custom section", (await dialog(p).locator('[id^="custom_data."]').count()) === 0);
  await shot(p, "10_zero_fields_contact_edit");
} finally {
  await browser.close();
}

console.log(`\n${pass} passed · ${failures.length} failed`);
if (failures.length) {
  for (const f of failures) console.log(`  FAIL ${f}`);
  process.exitCode = 1;
}
