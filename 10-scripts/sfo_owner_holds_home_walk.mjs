#!/usr/bin/env node
// ── sfo_owner_holds_home_walk.mjs ───────────────────────────────────────────
//
// CR-164-BRC10 wave 4 (2026-10-03) — the PO's ruling *"C By owner type: an
// owner who lives there holds it; a landlord or builder doesn't"*, walked in a
// browser. Derived from lane NC-R's `ncr_single_family_charges_walk.mjs`; the
// changes: step 1's Owner type is `NC_OWNER_KIND` (e.g. `owner_occupier`,
// `landlord`), step 5's *What Create makes* must read `NC_EXPECT` (*lives
// there* / *billing only*), and after Create the build's *Owner and scope*
// must say the same.
//
// ⚠ It WRITES ROWS. Run it against a private database, never a sibling's.
//
//   NC_BASE=http://127.0.0.1:8796 NC_BUILD=single NC_OWNER_KIND=landlord \
//     NC_EXPECT="billing only" NC_OUT=/tmp/x node 10-scripts/sfo_owner_holds_home_walk.mjs
import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.NC_BASE ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const TENANT = process.env.NC_TENANT ?? "brazosbend";
const EMAIL = process.env.NC_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.NC_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.NC_OUT ?? "/tmp/ncc-walk";
const BUILD = process.env.NC_BUILD ?? "apartment";
const PRESS = process.env.NC_PRESS !== "0";
const OWNER_KIND = process.env.NC_OWNER_KIND ?? "landlord";
const EXPECT = process.env.NC_EXPECT ?? "billing only";
const PREFIX = process.env.NC_PREFIX ?? `sfo_${OWNER_KIND}`;
const CHARGES = (process.env.NC_CHARGES ?? "CONN,INSPECT").split(",").filter((c) => c !== "");
const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(6, 14);

const SHAPES = {
  single: { type: "single_family", units: 1, party: "person", unitType: "residential" },
  apartment: { type: "apartment_complex", units: 3, party: "company", unitType: "residential_submetered" },
  commercial: { type: "commercial_building", units: 2, party: "company", unitType: "commercial" },
};
const SHAPE = SHAPES[BUILD];
if (SHAPE === undefined) throw new Error(`NC_BUILD must be one of ${Object.keys(SHAPES)}`);

const results = [];
const serverErrors = [];
const record = (verdict, label, evidence = "") => {
  results.push({ verdict, label, evidence: String(evidence).slice(0, 900) });
  console.log(`${verdict.padEnd(5)} ${label}${evidence === "" ? "" : ` — ${String(evidence).slice(0, 300)}`}`);
};
const check = (label, ok, evidence) => record(ok ? "PASS" : "FAIL", label, evidence);

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  const found = readdirSync(root)
    .filter((n) => n.startsWith("chromium"))
    .flatMap((n) => ["chrome-linux/chrome", "chrome-linux64/chrome"].map((s) => join(root, n, s)))
    .filter(existsSync);
  if (found.length === 0) throw new Error(`no chromium under ${root}`);
  return found[0];
}

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
page.on("response", (r) => {
  if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`);
});

async function shoot(name) {
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.waitForTimeout(300);
  const need = await page.evaluate(() => {
    const view = document.querySelector(".view");
    return view === null ? null : Math.ceil(view.getBoundingClientRect().top + view.scrollHeight + 24);
  });
  const height = Math.min(Math.max(need ?? 1200, 900), 20000);
  await page.setViewportSize({ width: 1440, height });
  await page.waitForTimeout(300);
  const file = join(OUT, `${PREFIX}_${name}.png`);
  await page.screenshot({ path: file });
  console.log(`      shot ${file} 1440x${height} ${statSync(file).size} bytes`);
  await page.setViewportSize({ width: 1440, height: 1200 });
}
const has = async (s) => (await page.locator(s).count()) > 0;
const bodyText = async () => (await page.locator("body").innerText()).replace(/\s+/g, " ");
async function fill(selector, value) {
  if (!(await has(selector))) return false;
  await page.fill(selector, value).catch(() => undefined);
  return true;
}
async function choose(selector, preferred) {
  if (!(await has(selector))) return null;
  const values = await page.$$eval(`${selector} option`, (ns) =>
    ns.filter((o) => !o.disabled && o.value !== "").map((o) => o.value),
  );
  if (values.length === 0) return null;
  const take = preferred !== undefined && values.includes(preferred) ? preferred : values[0];
  await page.selectOption(selector, take);
  return take;
}
async function tick(selector, want = true) {
  const el = await page.$(selector);
  if (el === null) return null;
  if ((await el.evaluate((n) => n.checked)) !== want) await el.evaluate((n) => n.click());
  await page.waitForTimeout(150);
  return el.evaluate((n) => n.checked);
}
async function segmented(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) return false;
  await el.evaluate((n) => n.click());
  return true;
}
async function forward(label) {
  const button = page.locator('[data-wizard="actions"] button').last();
  if (await button.isDisabled()) {
    record("FAIL", `${label}: forward button disabled`);
    return false;
  }
  await button.click();
  await page.waitForTimeout(1800);
  return true;
}
const h1 = async () => (await page.locator("h1").first().innerText().catch(() => "")).trim();

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);

// ── step 1 ──────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
check("step 1 opens", (await h1()) === "Who is asking, and what for?", await h1());
await shoot("1_empty");
TYPEDOWNER: {
  record("NOTE", "owner type picked", await choose("#nc_owner_kind", OWNER_KIND));
  await choose("#nc_owner_category");
  await choose("#nc_owner_subcategory", "permanent");
  await segmented("nc_party_kind", SHAPE.party);
  await page.waitForTimeout(400);
  await fill("#nc_owner_name", `NCC ${BUILD} owner ${STAMP}`);
  await fill("#nc_owner_email", `ncc.${BUILD}.${STAMP}@example.com`);
  await fill("#nc_owner_phone", "512-555-0142");
  if (SHAPE.party === "person") {
    await fill("#nc_owner_dob", "1981-04-12");
    await fill("#nc_ssn", process.env.NC_SSN ?? `412-${STAMP.slice(2, 4)}-${STAMP.slice(4, 8)}`);
    await fill("#nc_driving_licence", `TX-${STAMP}`);
  } else {
    await fill("#nc_tax_id", process.env.NC_TAX ?? `74-${STAMP.slice(1, 8)}`);
  }
}
// `CR-164-BRC10` wave 2 — the utility's own customer fields for the owner,
// where the utility placed any on New Connection Step 1.
const ownerField = page.locator('[data-step-content="owner"] section input[type="text"]').first();
if ((await ownerField.count()) > 0) {
  await ownerField.fill(process.env.NC_OWNER_FIELD ?? "Gold");
  record("NOTE", "owner custom field typed", process.env.NC_OWNER_FIELD ?? "Gold");
}
await choose("#preferred_language", process.env.NC_LANGUAGE ?? "es-MX");
await page.waitForTimeout(2000);
const matchPanel = (await page.locator('[data-step-content="customer-match"]').innerText().catch(() => "")).replace(/\s+/g, " ");
record("NOTE", "step 1 owner lookup says", matchPanel);
check("no Customer ID search box", !(await has("#nc_customer_q")), "");
if (process.env.NC_EXPECT_MATCH === "1") {
  check("an exact identifier is a Match", /match/i.test(matchPanel) && /Use this customer/.test(matchPanel), matchPanel);
  await shoot("1_match");
  await page.locator('[data-owner-match-action="use"]').first().click().catch(() => undefined);
  await page.waitForTimeout(800);
}
await choose("#nc_mode", "our_crew");
await shoot("1_filled");
if (!(await forward("step 1"))) await shoot("1_refused");

// ── step 2 ──────────────────────────────────────────────────────────────────
check("step 2 opens", (await h1()) === "The premise", await h1());
await fill("#nc_address", `${STAMP.slice(4)} NCC ${BUILD} Way`);
await page.waitForTimeout(1500);
await fill("#nc_city", "Austin");
await fill("#nc_state", "TX");
await fill("#nc_zip", "78704");
await fill("#nc_premise_name", `NCC ${BUILD} ${STAMP}`);
await choose("#nc_premise_type", SHAPE.type);
await choose("#nc_route");
await choose("#nc_scope", "new_premise");
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => undefined);
if (await has("#services_available-add")) {
  const offered = await page.$$eval("#services_available-add option", (ns) =>
    ns.map((o) => o.value).filter((v) => v !== ""),
  );
  for (const code of offered.slice(0, BUILD === "single" ? 3 : 5)) {
    await page.selectOption("#services_available-add", code).catch(() => undefined);
    await page.waitForTimeout(200);
  }
}
await choose("#nc_plan");
await page.waitForTimeout(2000);
await shoot("2_filled");
if (!(await forward("step 2"))) await shoot("2_refused");

// ── step 3 ──────────────────────────────────────────────────────────────────
check("step 3 opens", (await h1()) === "The units", await h1());
await shoot("3_empty");
await fill("#nc_from", "1");
await fill("#nc_to", String(SHAPE.units));
await page.waitForTimeout(800);
await choose("#nc_common_occupancy");
await choose("#nc_common_unit_type", SHAPE.unitType);
if (await has("[data-apply-to-all]")) {
  await page.locator("[data-apply-to-all]").first().click().catch(() => undefined);
  await page.waitForTimeout(1000);
}
await shoot("3_filled");
if (!(await forward("step 3"))) await shoot("3_refused");

// ── step 4 ──────────────────────────────────────────────────────────────────
check("step 4 opens", (await h1()) === "Charges", await h1());
const addCharge = page.locator('[data-array-action="add-charge"]').first();
// Ruling 1 (PO 2026-10-02): a single-family build's charges go to the owner's
// own account, so EVERY building carries charges here now.
for (const [index, code] of CHARGES.entries()) {
  if ((await addCharge.count()) === 0 || (await addCharge.isDisabled())) break;
  await addCharge.click().catch(() => undefined);
  await page.waitForTimeout(800);
  await choose(`select[data-cell="charge-${index}"]`, code);
  await page.waitForTimeout(2500);
}
const payerOptions = await page
  .$$eval("#nc_quote_payer option", (ns) => ns.map((o) => `${o.value}${o.disabled ? " (disabled)" : ""}: ${o.textContent}`))
  .catch(() => []);
record("NOTE", "Who is billed offers", payerOptions.join(" | "));
await choose("#nc_quote_payer", "owner_account");
await choose("#nc_quote_due_days", "30");
if ((await choose("#nc_payment_option", "card")) === "card") {
  await page.waitForTimeout(500);
  await fill("#nc_payment_amount", process.env.NC_PAID ?? "25.00");
  await fill("#nc_payment_reference", `AUTH${STAMP}`);
  await fill("#nc_payment_date", "2026-10-02");
}
await shoot("4_filled");
if (!(await forward("step 4"))) await shoot("4_refused");
if ((await h1()) === "Charges") {
  const refusal = (await bodyText()).match(/No master account to bill[^.]*\.[^.]*\./);
  record("FAIL", "step 4 refused to continue", refusal === null ? "(no refusal sentence found)" : refusal[0]);
  await shoot("4_refused");
}

// ── step 5 ──────────────────────────────────────────────────────────────────
check("step 5 opens", (await h1()) === "What will be created", await h1());
await page.waitForTimeout(1500);
for (const summary of await page.locator("details summary").all()) {
  await summary.click().catch(() => undefined);
}
await page.waitForTimeout(800);
await shoot("5_review");
const review = await bodyText();
check("no database id on review (rule 31)", !/\b[0-9a-f]{8}-[0-9a-f]{4}-/.test(review), "");
const makes = (await page.locator("[data-create-makes]").innerText().catch(() => "")).replace(/\s+/g, " ");
record("NOTE", "What Create makes", makes);
check(`step 5 says "Owner's account · ${EXPECT}"`, makes.includes(`Owner's account · ${EXPECT}`), makes);

if (PRESS) {
  const button = page.locator('[data-wizard="actions"] button').last();
  const wait = page.waitForResponse((r) => r.url().includes("/connections/commit"), { timeout: 60000 }).catch(() => null);
  await button.click();
  const resp = await wait;
  await page.waitForTimeout(4000);
  const status = resp === null ? "none" : resp.status();
  check("PRESS CREATE accepted", typeof status === "number" && status < 300, `${status} ${resp === null ? "" : (await resp.text()).slice(0, 400)}`);
  await shoot("6_done");
  record("NOTE", "Done screen", (await bodyText()).slice(0, 900));
  // Ruling 2 — Send now on the build record's Messages tab, then read the tab.
  const built = resp === null ? null : await resp.json().catch(() => null);
  const buildId = built?.id ?? null;
  record("NOTE", "build id", buildId ?? "(none)");
  if (buildId !== null) {
    // The request's Overview — *What this build made* names the account.
    await page.goto(`${BASE}/${TENANT}/connections/${buildId}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(3000);
    const made = (await bodyText()).match(/What this build made.{0,400}/)?.[0] ?? "";
    record("NOTE", "request Overview, What this build made", made);
    check(`request page says "Owner's account · ${EXPECT}"`, made.includes(`Owner's account · ${EXPECT}`), made);
    await shoot("7_request_overview");
  }
  if (process.env.NC_SEND_NOW === "1" && buildId !== null) {
    await page.goto(`${BASE}/${TENANT}/connections/${buildId}?tab=messages`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    for (const code of (process.env.NC_SEND_CODES ?? "build_created,quote_and_what_is_owed").split(",")) {
      const send = page.locator(`[data-testid="send-${code}"]`).first();
      if ((await send.count()) === 0 || (await send.isDisabled())) {
        record("FAIL", `Send now ${code} not offered`);
        continue;
      }
      await send.click();
      await page.waitForTimeout(800);
      await choose("#build-message-channel", "email");
      await page.locator('[role="dialog"] button[type="submit"]').last().click().catch(() => undefined);
      await page.waitForTimeout(2500);
    }
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    const table = (await page.locator('[data-table="build-messages"]').innerText().catch(() => "")).replace(/\s+/g, " ");
    record("NOTE", "Messages tab", table);
    await shoot("7_messages");
  }
}
for (const e of serverErrors) record("FAIL", "5xx during the walk", e);
writeFileSync(join(OUT, `${PREFIX}_RESULTS.json`), JSON.stringify({ BUILD, results, serverErrors }, null, 2));
await browser.close();
const failed = results.filter((r) => r.verdict === "FAIL").length;
console.log(`── ${results.length} checks, ${failed} FAIL`);
process.exit(failed === 0 ? 0 : 1);
