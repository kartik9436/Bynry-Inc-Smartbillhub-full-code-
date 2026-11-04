// ── Trace ──────────────────────────────────────────────
// Ask:      PO 2026-10-01 — *"do web walk from Self service portal for Customer …
//           submit the new service request … for premises in the utility … for
//           premsies not in system … whether clark is able to see and process
//           that request from new request screen - check submitted document,
//           make any corrections to the request, and approve it raise move in or
//           new connect request - do various combination of customer class"*,
//           *"complete the move in process or new conenct request coming from
//           portal - extend it until entire process is completed and customer is
//           activated"*, *"When you take utilty take it for 6 utility services
//           water, trash, sewer, fire, solar and battery"*, *"also ensure you
//           check the all data is correctly saved updated, viewed"*.
// World:    10-scripts/cwpwalk_seed.py (Six Rivers Utility + Oak Hollow Water).
// Readback: 10-scripts/cwpwalk_readback.py reads every row this walk wrote.
// Results:  08-qa/screens/portal-walk21-2026-10-02/RESULTS.md
// ───────────────────────────────────────────────────────
//
// TWENTY-ONE WALKS, IN A REAL BROWSER AT 1440, AS THE CUSTOMER AND THEN AS THE
// CLERK (Dana Mercer, billing clerk):
//
//   W1–W12  three kinds of address (on file · on file with a unit · not in the
//           system) × a person or a business × ONE service (each of the six once)
//           or ALL SIX; six NEW customers and six LINKED; three MASTER accounts;
//           all seven pickable classes. Every application uploads a PDF and a
//           PNG; the clerk opens both, corrects one field (a name or the start
//           date), picks the property, links or records the search, approves,
//           and carries it to an ACTIVE account; the portal user then sees it.
//   W13     the clerk declines a request.
//   W14     the clerk asks for more; the customer tries to send a second file.
//   W15–W18 a start date under three working days · no address step · a closed
//           tab keeps the draft · another utility cannot see the request.
//   W19–W21 a wrong file type · a file over 10 MB · another utility cannot list
//           or open the documents.
//
// ⚠ WHAT WOULD MAKE THIS PASS WRONGLY (hard-won law 7): reading what a screen
// SAYS instead of what was SAVED — so every walk's ids land in a manifest and
// `cwpwalk_readback.py` reads the database row by row afterwards; and a step
// that silently did nothing — so every step records what the screen showed,
// and a failure keeps the screenshot and the text rather than a bare timeout.
//
//   node 10-scripts/cwpwalk_portal_walk21.mjs            (all)
//   WALKS=W1,W13 node 10-scripts/cwpwalk_portal_walk21.mjs
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8462";
const T = process.env.TENANT ?? "sixrivers";
const OTHER = process.env.OTHER_TENANT ?? "oakhollow";
const CLERK = { email: "dana.mercer@sixriversutility.com", password: "S3cure!passw0rd" };
const OTHER_ADMIN = { email: "omar@oakhollowwater.com", password: "S3cure!passw0rd" };
const PORTAL_PASSWORD = "Six-Rivers-Walk-2026";
const NEW_PORTAL_PASSWORD = "Walk-Login-2026!";
const DB = process.env.WALK_DB ?? "cwpwalk_db";
const OUT = new URL("../08-qa/screens/portal-walk21-2026-10-02/", import.meta.url).pathname;
const MANIFEST = `${OUT}walk-manifest.json`;
const CHROME = process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });

// ── the files a customer attaches ──────────────────────────────────────────
const PDF = (tag) =>
  Buffer.from(
    `%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n% ${tag}\ntrailer << /Root 1 0 R >>\n%%EOF\n`,
  );
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

// ── the twelve applications ────────────────────────────────────────────────
const SIX = ["water", "sewer", "trash", "solar", "battery", "fire"];
const P = (first, last, dob) => ({ kind: "person", first, last, dob, name: `${first} ${last}` });
const B = (company, tax) => ({ kind: "business", company, tax, name: company });
const WALKS = [
  { id: "W1", prem: "A", addr: "14 Alder Run", unit: "", unitLabel: "Main", who: P("Lena", "Ortiz", "1988-04-12"), email: "lena.ortiz@example.test", phone: "(281) 555-0301", services: ["water"], link: null, master: false, cls: "residential", fix: "name", fixTo: "Lena M. Ortiz" },
  { id: "W2", prem: "A", addr: "16 Alder Run", unit: "", unitLabel: "Main", who: P("Marcus", "Bell", "1979-03-21"), email: "marcus.applies@example.test", phone: "(281) 555-0302", services: SIX, link: "Marcus Bell", master: false, cls: "commercial", fix: "date" },
  { id: "W3", prem: "A", addr: "18 Alder Run", unit: "", unitLabel: "Main", who: B("Alder Bakry LLC", "74-2000003"), email: "books@alderbakery.test", phone: "(281) 555-0303", services: ["sewer"], link: null, master: false, oneUnit: true, cls: "institutional", fix: "name", fixTo: "Alder Bakery LLC" },
  { id: "W4", prem: "A", addr: "20 Alder Run", unit: "", unitLabel: "Main", who: B("Alder Freight Co", "74-1000004"), email: "ap@alderfreight.test", phone: "(281) 555-0304", services: SIX, link: "Alder Freight Co", master: false, cls: "industrial", fix: "date" },
  { id: "W5", prem: "B", addr: "400 Heron Court", unit: "Unit 2", unitLabel: "Unit 2", who: P("Nadia", "Rahmen", "1985-11-02"), email: "nadia.applies@example.test", phone: "(281) 555-0305", services: ["trash"], link: "Nadia Rahman", master: false, cls: "municipal", fix: "name", fixTo: "Nadia Rahman" },
  { id: "W6", prem: "B", addr: "402 Heron Court", unit: "Unit 2", unitLabel: "Unit 2", who: P("Owen", "Price", "1992-06-30"), email: "owen.price@example.test", phone: "(281) 555-0306", services: SIX, link: null, master: false, cls: "agricultural", fix: "date" },
  { id: "W7", prem: "B", addr: "404 Heron Court", unit: "Unit 3", unitLabel: "Unit 3", who: B("Heron Fire Suply Inc", "74-2000007"), email: "office@heronfire.test", phone: "(281) 555-0307", services: ["fire"], link: null, master: false, cls: "builder_developer", fix: "name", fixTo: "Heron Fire Supply Inc" },
  { id: "W8", prem: "B", addr: "406 Heron Court", unit: "Unit 1", unitLabel: "Unit 1", who: B("Heron Court Partners LLC", "74-1000008"), email: "ops.applies@heroncourt.test", phone: "(281) 555-0308", services: SIX, link: "Heron Court Partners LLC", master: true, cls: "commercial", fix: "date" },
  { id: "W9", prem: "C", addr: "77 Juniper Bend", unit: "", unitLabel: "1", who: P("Priya", "Naer", "1990-01-15"), email: "priya.nair@example.test", phone: "(281) 555-0309", services: ["solar"], link: null, master: false, cls: "residential", fix: "name", fixTo: "Priya Nair" },
  { id: "W10", prem: "C", addr: "79 Juniper Bend", unit: "", unitLabel: "1", who: P("Tomas", "Vega", "1983-08-08"), email: "tomas.applies@example.test", phone: "(281) 555-0310", services: SIX, link: "Tomas Vega", master: false, cls: "municipal", fix: "date" },
  { id: "W11", prem: "C", addr: "81 Juniper Bend", unit: "", unitLabel: "1", who: B("Kestrel Energy Coop", "74-1000011"), email: "office.applies@kestrel.test", phone: "(281) 555-0311", services: ["battery"], link: "Kestrel Energy Co-op", master: false, cls: "agricultural", fix: "name", fixTo: "Kestrel Energy Co-op" },
  { id: "W12", prem: "C", addr: "83 Juniper Bend", unit: "", unitLabel: "1", who: B("Juniper Foods Co", "74-2000012"), email: "ap@juniperfoods.test", phone: "(281) 555-0312", services: SIX, link: null, master: false, cls: "industrial", fix: "date" },
];
const SERVICE_NAME = { water: "Water", sewer: "Sewer", trash: "Trash", solar: "Solar", battery: "Battery", fire: "Fire" };
const LINKED_LOGIN = {
  "Marcus Bell": "marcus.bell@example.test",
  "Alder Freight Co": "ap@alderfreight.test",
  "Nadia Rahman": "nadia.rahman@example.test",
  "Heron Court Partners LLC": "ops@heroncourt.test",
  "Tomas Vega": "tomas.vega@example.test",
  "Kestrel Energy Co-op": "office@kestrel.test",
};

// ── bookkeeping ────────────────────────────────────────────────────────────
const manifest = existsSync(MANIFEST) ? JSON.parse(readFileSync(MANIFEST, "utf8")) : {};
const only = (process.env.WALKS ?? "").split(",").filter(Boolean);
const wanted = (id) => only.length === 0 || only.includes(id);
function rec(walk) {
  manifest[walk] = manifest[walk] ?? { steps: [] };
  return manifest[walk];
}
function step(walk, name, ok, detail = "") {
  rec(walk).steps.push({ name, ok, detail: String(detail).slice(0, 400) });
  console.log(`  ${ok === true ? "✓" : ok === false ? "✗" : "·"} ${walk} ${name}${detail ? ` — ${String(detail).slice(0, 160)}` : ""}`);
}
function save() {
  writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2));
}
async function shot(page, walk, name) {
  const path = `${OUT}${walk}-${name}.png`;
  await page.screenshot({ path, fullPage: true }).catch(() => {});
  rec(walk).shots = [...(rec(walk).shots ?? []), `${walk}-${name}.png`];
}
function sql(query) {
  return execFileSync("psql", ["-h", "127.0.0.1", "-p", "55433", "-U", "postgres", "-d", DB, "-Atc", query])
    .toString()
    .trim();
}
function workingDaysFromToday(n) {
  const day = new Date();
  let left = n;
  while (left > 0) {
    day.setDate(day.getDate() + 1);
    if (day.getDay() !== 0 && day.getDay() !== 6) left -= 1;
  }
  return day;
}
const iso = (d) => d.toISOString().slice(0, 10);
const mdy = (s) => `${s.slice(5, 7)}/${s.slice(8, 10)}/${s.slice(0, 4)}`;
const START = iso(workingDaysFromToday(15));
const FIXED_START = iso(workingDaysFromToday(20));
/** A date box is either the browser's own (`type=date`, ISO) or the kit's
 *  regional text box (MM/DD/YYYY here); type what each one takes. */
async function fillDate(page, selector, isoValue) {
  const type = await page.locator(selector).getAttribute("type");
  await page.fill(selector, type === "date" ? isoValue : mdy(isoValue));
  await page.locator(selector).blur();
}
const text = async (page, sel = "main") => (await page.locator(sel).first().innerText().catch(() => "")) ?? "";

// ── browser ────────────────────────────────────────────────────────────────
const browser = await chromium.launch({ executablePath: CHROME });
async function context() {
  return browser.newContext({ viewport: { width: 1440, height: 1000 }, baseURL: BASE });
}
async function staffSignIn(page, who, tenant = T) {
  await page.goto(`/${tenant}/signin`);
  await page.fill("#signin-email", who.email);
  await page.fill("#signin-password", who.password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
}

// ════════════════════════════════════════════════════════════════════════════
// THE CUSTOMER — the portal's four steps, as a stranger
// ════════════════════════════════════════════════════════════════════════════
async function guestApply(w, page) {
  await page.goto(`/${T}/portal/start-service`);
  await page.fill("#availability-address", w.addr);
  if (w.unit) await page.fill("#availability-unit", w.unit);
  await page.click('[data-action="check"]');
  await page.waitForSelector('[data-minitable], [data-availability="unmatched"]', { timeout: 30000 });
  const matched = (await page.locator("[data-minitable]").count()) > 0;
  step(w.id, "address step answers", matched === (w.prem !== "C"), matched ? "WE SERVE THIS ADDRESS" : "a person will look at it");
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 30000 });
  if (w.prem === "C") {
    await page.waitForSelector("[data-service-pick]", { timeout: 20000 });
    for (const code of w.services) {
      await page.locator(`[data-service-pick="${code}"] input`).check();
      await page.waitForTimeout(250);
    }
    step(w.id, "ticked services (address not held)", true, w.services.join(","));
  } else {
    await page.waitForSelector(`[data-step="when"] [data-kv="${w.services[0]}"]`, { timeout: 20000 }).catch(() => {});
    const shown = await page.$$eval('[data-step="when"] [data-kv]', (ns) => ns.map((n) => n.getAttribute("data-kv")));
    const got = shown.filter((k) => SIX.includes(k)).sort();
    step(w.id, "services the address takes", JSON.stringify(got) === JSON.stringify([...w.services].sort()), got.join(","));
  }
  await page.selectOption("#applicant_kind", w.who.kind);
  await page.fill("#requested_start", START);
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(700);
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-step="about"]', { timeout: 30000 });
  if (w.who.kind === "business") {
    await page.fill("#company_name", w.who.company);
    await page.locator("#company_name").blur();
    await page.fill("#tax_id", w.who.tax);
    await page.locator("#tax_id").blur();
  } else {
    await page.fill("#first_name", w.who.first);
    await page.fill("#last_name", w.who.last);
    await page.fill("#date_of_birth", w.who.dob);
    await page.locator("#date_of_birth").blur();
  }
  await page.fill("#email", w.email);
  await page.fill("#phone", w.phone);
  await page.locator("#phone").blur();
  const input = page.locator('[data-application-documents] input[type="file"]');
  const files = [`${w.id.toLowerCase()}-lease.pdf`, `${w.id.toLowerCase()}-photo-id.png`];
  await input.setInputFiles({ name: files[0], mimeType: "application/pdf", buffer: PDF(w.id) });
  await page.waitForSelector(`[data-attached-file="${files[0]}"]`, { timeout: 30000 });
  await input.setInputFiles({ name: files[1], mimeType: "image/png", buffer: PNG });
  await page.waitForSelector(`[data-attached-file="${files[1]}"]`, { timeout: 30000 });
  step(w.id, "two files attached on step 3", true, files.join(", "));
  await page.waitForTimeout(500);
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-screen="CWP-009"]', { timeout: 30000 });
  const review = await text(page);
  const svcLine = w.services.map((c) => SERVICE_NAME[c]);
  step(w.id, "check-and-send restates services", svcLine.every((n) => review.includes(n)), svcLine.join(", "));
  // DEF-CWP-9079 — paperless is the applicant's own act: the box arrives unticked.
  const paperlessTicked = await page.locator("#paperless").isChecked();
  step(w.id, "paperless box arrives unticked", paperlessTicked === false, paperlessTicked ? "TICKED" : "unticked");
  const submitted = page.waitForResponse((r) => r.url().includes("/submit") && r.request().method() === "POST", { timeout: 30000 });
  await page.click('[data-action="send"]');
  const res = await submitted;
  const body = await res.json().catch(() => ({}));
  step(w.id, "sent", res.status() === 200, `${res.status()} ${body.reference ?? JSON.stringify(body).slice(0, 120)}`);
  await page.waitForSelector("[data-reference]", { timeout: 30000 }).catch(() => {});
  await shot(page, w.id, "01-portal-sent");
  const token = new URL(page.url()).pathname.split("/").pop();
  Object.assign(rec(w.id), { request_id: body.request_id, reference: body.reference, token, files, start: START });
  save();
  return body;
}

// ════════════════════════════════════════════════════════════════════════════
// THE CLERK — the new-request screen
// ════════════════════════════════════════════════════════════════════════════
async function clerkSeesAndOpens(w, ctx, page) {
  const r = rec(w.id);
  await page.goto(`/${T}/requests`);
  await page.waitForSelector(`text=${r.reference}`, { timeout: 30000 });
  const row = page.locator("tr", { hasText: r.reference }).first();
  const rowText = (await row.innerText()).replace(/\s+/g, " ");
  step(w.id, "on the clerk's request list", rowText.includes(w.who.name) && rowText.includes("Customer portal"), rowText.slice(0, 160));
  await page.goto(`/${T}/requests/${r.request_id}`);
  await page.waitForSelector('[data-decision-action="approve"]', { timeout: 30000 });
  const detail = await text(page);
  const svcOk = w.services.every((c) => detail.includes(SERVICE_NAME[c]));
  step(w.id, "request detail: applicant, contact, services", detail.includes(w.who.name) && detail.includes(w.email) && detail.includes(w.phone) && svcOk);
  if (w.who.kind === "person") {
    step(w.id, "request detail: date of birth shown", detail.includes(mdy(w.who.dob)), mdy(w.who.dob));
  } else {
    step(w.id, "request detail: Tax ID last four shown", detail.includes(w.who.tax.slice(-4)), `•••• ${w.who.tax.slice(-4)}`);
  }
  await page.click('[data-tab="documents"]');
  for (const name of r.files) {
    const button = page.locator("[data-doc-open]", { hasText: name }).first();
    await button.waitFor({ timeout: 30000 });
    const [opened] = await Promise.all([ctx.waitForEvent("page", { timeout: 30000 }), button.click()]);
    await opened.waitForLoadState().catch(() => {});
    const url = opened.url();
    await opened.close().catch(() => {});
    const res = await ctx.request.get(url);
    const bytes = Buffer.from(await res.body());
    const want = name.endsWith(".pdf") ? PDF(w.id) : PNG;
    const ok = res.status() === 200 && bytes.equals(want);
    step(w.id, `clerk opens ${name}`, ok, `${res.status()} ${res.headers()["content-type"]} ${bytes.length}B`);
  }
  await shot(page, w.id, "02-clerk-documents");
}

async function clerkCorrects(w, page) {
  const r = rec(w.id);
  await page.goto(`/${T}/requests/new?request=${r.request_id}`);
  await page.waitForSelector("#applicant_name", { timeout: 30000 });
  if (w.fix === "name") {
    await page.fill("#applicant_name", w.fixTo);
    r.corrected = { field: "applicant_name", from: w.who.name, to: w.fixTo };
  } else {
    await page.goto(`/${T}/requests/new?request=${r.request_id}&step=3`);
    await page.waitForSelector("#requested_start", { timeout: 30000 });
    await page.fill("#requested_start", FIXED_START);
    await page.locator("#requested_start").blur();
    r.corrected = { field: "requested_start", from: START, to: FIXED_START };
  }
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.waitForURL(new RegExp(`/requests/${r.request_id}$`), { timeout: 30000 });
  await page.waitForSelector('[data-decision-action="approve"]', { timeout: 30000 });
  const after = await text(page);
  const shown = w.fix === "name" ? after.includes(w.fixTo) : after.includes(mdy(FIXED_START));
  step(w.id, `correction saved and shown (${r.corrected.field})`, shown, `${r.corrected.from} → ${r.corrected.to}`);
  save();
}

async function clerkClassAndProperty(w, page) {
  const r = rec(w.id);
  await page.goto(`/${T}/requests/new?request=${r.request_id}`);
  await page.waitForSelector("#account_type_code", { timeout: 30000 });
  await page.selectOption("#account_type_code", w.cls);
  if (w.prem !== "C") {
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForSelector("#address_as_given", { timeout: 30000 });
    await page.fill("#address_as_given", w.addr.split(" ").slice(1).join(" ").slice(0, 10));
    const option = page.locator("[data-premises-option]", { hasText: w.addr }).first();
    await option.waitFor({ timeout: 20000 });
    await option.click();
    const unitSelect = page.locator("select#address_unit_as_given");
    await unitSelect.waitFor({ timeout: 15000 });
    const labels = await unitSelect.locator("option").allInnerTexts();
    const want = labels.find((l) => l.endsWith(`· ${w.unitLabel}`));
    await unitSelect.selectOption({ label: want });
    step(w.id, "clerk picks the property and unit", Boolean(want), `${w.addr} · ${want}`);
  }
  await page.getByRole("button", { name: "Save changes" }).click();
  await page.waitForURL(new RegExp(`/requests/${r.request_id}$`), { timeout: 30000 });
  await page.waitForSelector('[data-decision-action="approve"]', { timeout: 30000 });
  const after = await text(page);
  if (w.prem !== "C") {
    step(w.id, "request shows the matched premises and unit", /Matched premises\s*\nP-\d+/.test(after) && /Matched unit\s*\nU-\d+/.test(after));
  }
}

async function clerkApproves(w, page) {
  const r = rec(w.id);
  await page.goto(`/${T}/requests/${r.request_id}`);
  await page.waitForSelector('[data-decision-action="approve"]', { timeout: 30000 });
  await page.click('[data-decision-action="approve"]');
  const modal = page.locator('[role="dialog"]').first();
  await modal.waitFor({ timeout: 15000 });
  const outcome = w.prem === "C" ? "new_connection" : "move_in";
  await modal.locator(`[data-segment="${outcome}"]`).click();
  await page.waitForTimeout(800);
  // ⚠ 2026-10-11 (`DEF-CUS-9043`, PO option B): *Search customer* takes NO
  // typed query — one press asks with what the application holds — and its
  // answer offers *Link* on each match (`data-match-action="link"`) and one
  // *No match* (`data-action="record-search"`), which is what the Arrears
  // row's old *Record that I searched* button became. The row itself now
  // only points here (`[data-approve-arrears-search]`).
  if (w.link) {
    await modal.locator("[data-customer-search]").click();
    const block = modal.locator("[data-match-block]", { hasText: w.link }).first();
    await block.waitFor({ timeout: 15000 });
    await block.locator('[data-match-action="link"]').click();
    await page.waitForTimeout(1500);
    step(w.id, "clerk links the customer on file", true, w.link);
  } else if (await modal.locator("[data-approve-arrears-search]").count()) {
    await modal.locator("[data-customer-search]").click();
    const noMatch = modal.locator('[data-action="record-search"]');
    await noMatch.waitFor({ timeout: 15000 });
    await noMatch.click();
    await page.waitForTimeout(1500);
    step(w.id, "clerk searches and records No match (no prior customer)", true);
  }
  await shot(page, w.id, "03-approve");
  const approve = modal.getByRole("button", { name: /^Approve/ }).last();
  const blocked = await approve.isDisabled();
  if (blocked) {
    step(w.id, `approve as ${outcome}`, false, (await modal.innerText()).replace(/\s+/g, " ").slice(-300));
    return false;
  }
  await approve.click();
  await page.waitForURL((u) => !u.pathname.endsWith(r.request_id), { timeout: 30000 });
  step(w.id, `approved as ${outcome}`, true, new URL(page.url()).pathname + new URL(page.url()).search);
  r.approved_as = outcome;
  r.landed = page.url();
  save();
  return true;
}

// ════════════════════════════════════════════════════════════════════════════
// THE CLERK — carried to an ACTIVE account
// ════════════════════════════════════════════════════════════════════════════
const wizardStep = async (page) => ((await text(page)).match(/Step (\d) of (\d) · ([^\n]+)/) ?? [])[0] ?? "?";

async function moveInWizard(w, page, { pickUnitText = null } = {}) {
  const r = rec(w.id);
  await page.waitForSelector('[data-wizard-step="1"]', { timeout: 30000 });
  await page.waitForTimeout(1500);
  for (let i = 0; i < 9; i += 1) {
    const s = await wizardStep(page);
    if (s.startsWith("Step 1")) {
      const sel = page.locator("#mvi_unit");
      await page.waitForFunction(() => (document.querySelector("#mvi_unit")?.options?.length ?? 0) > 1, null, { timeout: 30000 }).catch(() => {});
      await page.waitForTimeout(800);
      const value = await sel.inputValue().catch(() => "");
      if (pickUnitText !== null) {
        const opts = await sel.locator("option").allInnerTexts();
        const want = opts.find((o) => o.startsWith(pickUnitText));
        await sel.selectOption({ label: want });
        // The step reads the unit's accounts before it knows this is a first
        // occupant; Continue pressed before that answer is refused.
        await page.waitForSelector("text=Previous account", { timeout: 20000 }).catch(() => {});
        await page.waitForTimeout(800);
        step(w.id, "move-in: clerk picks the new unit", Boolean(want), want);
      } else {
        const label = await sel.locator("option:checked").innerText().catch(() => "");
        step(w.id, "move-in opens on the request's unit", value !== "" && label.startsWith(w.addr), label);
      }
    }
    if (s.startsWith("Step 2")) {
      const chips = (await text(page)).match(/Which services\?\n([\s\S]*?)\nSave & exit/);
      step(w.id, "move-in services", true, (chips?.[1] ?? "").replace(/\n×/g, "").replace(/\n/g, ","));
    }
    if (s.startsWith("Step 3")) {
      const kind = await page.$$eval('input[name="customer_kind"]', (ns) => ns.find((n) => n.checked)?.value ?? "");
      const want = w.who.kind === "business" ? "company" : "person";
      step(w.id, "move-in customer kind prefilled", kind === want, kind || "(none)");
      if (kind !== want) await page.locator(`input[name="customer_kind"][value="${want}"]`).evaluate((n) => n.click());
      const cls = await page.locator("#account_type").inputValue().catch(() => "");
      step(w.id, "move-in class prefilled from the request", cls === w.cls, cls);
      if (w.who.kind === "person") {
        const dob = await page.locator("#dob").inputValue().catch(() => "");
        step(w.id, "move-in date of birth prefilled", dob.includes(w.who.dob.slice(0, 4)), dob || "(empty)");
      }
    }
    if (s.startsWith("Step 4")) {
      const opened = await page.locator("#opened_at").inputValue().catch(() => "");
      const wantStart = r.corrected?.field === "requested_start" ? r.corrected.to : START;
      step(w.id, "move-in date prefilled from the request", opened === mdy(wantStart) || opened === wantStart, opened || "(empty)");
      if (opened === "") {
        await page.fill("#opened_at", mdy(wantStart));
        await page.locator("#opened_at").blur();
      }
      const reads = page.locator("input[id^=moveIn-read-]:not([id*=date])");
      const n = await reads.count();
      for (let k = 0; k < n; k += 1) {
        await reads.nth(k).fill(String(1000 + k));
        const dates = page.locator("input[id^=moveIn-read-date-]");
        await dates.nth(k).fill(mdy(wantStart));
        await dates.nth(k).blur();
      }
      if (n) step(w.id, "move-in opening reading(s) entered", true, `${n} meter(s)`);
    }
    if (s.startsWith("Step 7")) {
      await shot(page, w.id, "04-move-in-review");
      await page.getByRole("button", { name: /Complete move-in/ }).click();
      await page.waitForSelector("text=What was written", { timeout: 30000 }).catch(() => {});
      const done = await text(page);
      const account = done.match(/Account number\s*\n(AC-\d{4}-\d+)/)?.[1] ?? null;
      const customer = done.match(/Customer number\s*\n(C-\d+)/)?.[1] ?? null;
      step(w.id, "move-in complete", account !== null, `${account} · ${customer}`);
      await shot(page, w.id, "05-move-in-done");
      return { account, customer };
    }
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(1800);
    if ((await wizardStep(page)) === s) {
      step(w.id, `move-in stuck on ${s}`, false, (await text(page)).replace(/\s+/g, " ").slice(-300));
      await shot(page, w.id, "move-in-stuck");
      return { account: null, customer: null };
    }
  }
  return { account: null, customer: null };
}

async function masterAtBuilding(w, page) {
  const r = rec(w.id);
  await page.goto(`/${T}/requests/${r.request_id}`);
  const link = page.locator("[data-request-owner-master]");
  await link.waitFor({ timeout: 30000 });
  await link.click();
  await page.waitForSelector('[data-tab="common-areas"]', { timeout: 30000 });
  await page.waitForTimeout(1500);
  if (!(await page.getByRole("button", { name: /Create master account|Create another/ }).count())) {
    await page.getByRole("button", { name: "+ Add a common area" }).first().click();
    await page.fill("#common-area-label", "Laundry");
    await page.locator('[role="dialog"]').getByRole("button", { name: "Add" }).click();
    await page.waitForTimeout(2000);
    step(w.id, "clerk adds a common area (Laundry) so the master has shared space", true);
  }
  await page.getByRole("button", { name: /Create master account|Create another/ }).first().click();
  const dlg = page.locator('[role="dialog"]').first();
  await dlg.waitFor({ timeout: 15000 });
  await page.selectOption("#master-account-type", w.cls);
  const start = r.corrected?.field === "requested_start" ? r.corrected.to : START;
  await fillDate(page, "#master-opened-at", start);
  await page.fill("#master-payer", r.corrected?.field === "applicant_name" ? r.corrected.to : w.who.name);
  await shot(page, w.id, "04-master-form");
  await dlg.getByRole("button", { name: "Create account" }).click();
  await page.waitForTimeout(3000);
  const stillOpen = await dlg.isVisible().catch(() => false);
  if (stillOpen) {
    step(w.id, "master account created", false, (await dlg.innerText()).replace(/\s+/g, " ").slice(-300));
    await shot(page, w.id, "master-refused");
    return { account: null };
  }
  const account = sql(`select a.account_no from accounts a join service_requests sr on sr.id='${r.request_id}' where a.kind='master' and a.premises_id=sr.resolved_premises_id order by a.created_at desc limit 1`);
  step(w.id, "master account created", account !== "", account);
  await shot(page, w.id, "05-master-done");
  return { account };
}

async function newConnectBuild(w, page) {
  const r = rec(w.id);
  await page.waitForSelector('[data-wizard-step="1"]', { timeout: 30000 });
  await page.waitForTimeout(2500);
  for (let i = 0; i < 7; i += 1) {
    const s = await wizardStep(page);
    if (s.startsWith("Step 1")) {
      const name = await page.locator("#nc_owner_name").inputValue();
      step(w.id, "build owner prefilled from the request", name !== "", name);
      await page.selectOption("#nc_owner_kind", w.master ? "property_owner" : "occupier").catch(() => {});
      await page.selectOption("#nc_owner_category", w.cls);
      const kind = w.who.kind === "business" ? "company" : "person";
      await page.locator(`input[name="nc_party_kind"][value="${kind}"]`).evaluate((n) => n.click());
      const linked = await page.locator('[data-customer-finder="linked"]').count();
      step(w.id, w.link ? "build step 1 already names the linked customer" : "build step 1: new customer", w.link ? linked > 0 : linked === 0);
      if (kind === "company" && !w.link && (await page.locator("#nc_tax_id").count())) {
        // ⚠ Left EMPTY on purpose: the Tax ID the business typed online is read
        // from the application (DEF-CWP-9045). Typing it here would prove nothing.
      }
    }
    if (s.startsWith("Step 2")) {
      await page.selectOption("#nc_premise_type", "single_family");
      await page.fill("#nc_city", "Katy");
      await page.fill("#nc_state", "TX");
      await page.fill("#nc_zip", "77494");
      const offered = await page.$$eval("#services_available-add option", (ns) => ns.map((o) => o.value).filter(Boolean));
      const already = SIX.filter((c) => !offered.includes(c));
      step(w.id, "build step 2: services already carried from the request", w.services.every((c) => already.includes(c)), already.join(",") || "(none)");
      for (const code of w.services) {
        if (offered.includes(code)) {
          await page.selectOption("#services_available-add", code);
          await page.waitForTimeout(250);
        }
      }
      await page.selectOption("#nc_plan", { label: "Sample — Residential" });
    }
    if (s.startsWith("Step 3")) {
      await page.fill("#nc_from", "1");
      await page.fill("#nc_to", "1");
      await page.waitForTimeout(400);
      await page.click("[data-apply-to-all]");
      await page.waitForTimeout(1500);
      const grid = await text(page);
      const sized = !/SERVICE\tASSET\tSIZE[\s\S]*?—\t—/.test(grid);
      step(w.id, "build step 3: device and size offered to the clerk", sized, grid.includes("Templates could not be loaded") ? "catalogues refused (DEF-CUS-9048)" : "");
      await shot(page, w.id, "04-build-units");
    }
    if (s.startsWith("Step 5")) {
      await shot(page, w.id, "05-build-review");
      await page.locator('[data-wizard="actions"] button').last().click();
      // ⚠ NOT `text=CREATED` — that also matches the review's own "On create".
      await page.waitForSelector("text=Open the connection", { timeout: 40000 }).catch(() => {});
      await page.waitForTimeout(800);
      const done = await text(page);
      const con = done.match(/CON-\d{2}-\d+/)?.[0] ?? null;
      step(w.id, "build created", con !== null, con ?? done.replace(/\s+/g, " ").slice(-200));
      r.connection = con;
      save();
      return con;
    }
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(2200);
    if ((await wizardStep(page)) === s) {
      step(w.id, `build stuck on ${s}`, false, (await text(page)).replace(/\s+/g, " ").slice(-300));
      await shot(page, w.id, "build-stuck");
      return null;
    }
  }
  return null;
}

// ════════════════════════════════════════════════════════════════════════════
// THE CUSTOMER AGAIN — can they sign in and see it?
// ════════════════════════════════════════════════════════════════════════════
async function portalSees(w, accountNo) {
  const ctx = await context();
  const page = await ctx.newPage();
  const r = rec(w.id);
  try {
    if (w.link) {
      await page.goto(`/${T}/portal/sign-in`);
      await page.fill("#portal-email", LINKED_LOGIN[w.link]);
      await page.fill("#portal-password", PORTAL_PASSWORD);
      await page.locator("main button", { hasText: /^Sign in$/ }).click();
      await page.waitForURL(/\/portal\/home/, { timeout: 30000 });
      step(w.id, "linked customer signs in with their existing login", true, LINKED_LOGIN[w.link]);
    } else {
      const surname = w.who.kind === "business" ? (r.corrected?.field === "applicant_name" ? r.corrected.to : w.who.company) : (r.corrected?.field === "applicant_name" ? r.corrected.to.split(" ").pop() : w.who.last);
      await page.goto(`/${T}/portal/enrol`);
      await page.fill("#enrol-account", accountNo);
      await page.fill("#enrol-postcode", "77494");
      await page.fill("#enrol-lastname", surname);
      await page.getByRole("button", { name: /Continue/ }).click();
      await page.waitForSelector("#enrol-code", { timeout: 20000 });
      const code = sql(`select o.render_context->>'code' from outbound_messages o join accounts a on a.id=o.account_id where a.account_no='${accountNo}' and o.render_context ? 'code' order by o.created_at desc limit 1`);
      await page.fill("#enrol-code", code);
      await page.getByRole("button", { name: /Verify/ }).click();
      await page.waitForSelector("#enrol-email", { timeout: 20000 });
      const login = `${w.id.toLowerCase()}.login@example.test`;
      await page.fill("#enrol-email", login);
      await page.fill("#enrol-new", NEW_PORTAL_PASSWORD);
      await page.fill("#enrol-again", NEW_PORTAL_PASSWORD);
      await page.locator('input[name="otp-channel"][value="email"]').evaluate((n) => n.click());
      await page.getByRole("button", { name: /Create my login/ }).click();
      await page.waitForTimeout(3000);
      if (!/\/portal\/home/.test(page.url())) {
        await page.goto(`/${T}/portal/sign-in`);
        await page.fill("#portal-email", login);
        await page.fill("#portal-password", NEW_PORTAL_PASSWORD);
        await page.locator("main button", { hasText: /^Sign in$/ }).click();
        await page.waitForURL(/\/portal\/home/, { timeout: 30000 });
      }
      r.portal_login = login;
      step(w.id, "new customer enrols on number + ZIP + name and signs in", true, `${accountNo} · 77494 · ${surname}`);
    }
    await page.goto(`/${T}/portal/accounts`);
    await page.waitForTimeout(2500);
    const list = await text(page);
    step(w.id, "portal: My accounts lists the new account", list.includes(accountNo), accountNo);
    await shot(page, w.id, "06-portal-accounts");
    await page.goto(`/${T}/portal/requests`);
    await page.waitForTimeout(2000);
    const reqs = await text(page);
    step(w.id, "portal: my requests shows the application", reqs.includes(r.reference), r.reference);
    save();
  } catch (error) {
    step(w.id, "portal sees the account", false, error.message.split("\n")[0]);
    await shot(page, w.id, "portal-failed");
  } finally {
    await ctx.close();
  }
}

// ════════════════════════════════════════════════════════════════════════════
// ONE WALK, W1–W12
// ════════════════════════════════════════════════════════════════════════════
async function walk(w) {
  console.log(`\n══ ${w.id} · ${w.prem} · ${w.who.kind} · ${w.services.length === 6 ? "all six" : w.services[0]} · ${w.link ? "linked" : "new"} · ${w.master ? "master" : "regular"} · ${w.cls}`);
  manifest[w.id] = { steps: [], walk: w };
  const guest = await context();
  const gpage = await guest.newPage();
  try {
    await guestApply(w, gpage);
  } catch (error) {
    step(w.id, "portal application", false, error.message.split("\n")[0]);
    await shot(gpage, w.id, "portal-failed");
    save();
    await guest.close();
    return;
  }
  await guest.close();
  const staff = await context();
  const page = await staff.newPage();
  try {
    await staffSignIn(page, CLERK);
    await clerkSeesAndOpens(w, staff, page);
    await clerkCorrects(w, page);
    await clerkClassAndProperty(w, page);
    if (!(await clerkApproves(w, page))) return;
    let result = { account: null };
    if (w.prem !== "C" && !w.master) {
      if (w.oneUnit) {
        // BR-CUS-1114 (PO 2026-10-02) — a single-unit address takes no master
        // account: the request page draws the owner's-master door CLOSED.
        await page.goto(`/${T}/requests/${rec(w.id).request_id}`);
        await page.waitForTimeout(2000);
        const closed = await page.locator("[data-request-owner-master-closed]").count();
        step(w.id, "owner's master door closed on a single unit", closed > 0);
        await page.goto(`/${T}/move-ins/new?request=${rec(w.id).request_id}`);
      }
      result = await moveInWizard(w, page);
    } else if (w.prem !== "C" && w.master) {
      result = await masterAtBuilding(w, page);
    } else {
      const con = await newConnectBuild(w, page);
      if (con !== null && w.master) {
        result.account = sql(`select a.account_no from accounts a join connections c on c.owner_account_id=a.id where c.connection_no='${con}'`);
        step(w.id, "owner's master account opened by the build", result.account !== "", result.account);
      } else if (con !== null) {
        rec(w.id).build_owner_account = sql(`select a.account_no from accounts a join connections c on c.owner_account_id=a.id where c.connection_no='${con}'`);
        // BR-CUS-1114 / BR-CUS-1115 (PO 2026-10-02) — every C build is ONE unit,
        // so it raises no owner's master account; the applicant's regular
        // account (the move-in below) holds the services.
        step(w.id, "single-unit build raised no owner master", rec(w.id).build_owner_account === "", rec(w.id).build_owner_account);
        await page.goto(`/${T}/move-ins/new?request=${rec(w.id).request_id}`);
        result = await moveInWizard(w, page, { pickUnitText: w.addr });
      }
    }
    rec(w.id).account_no = result.account;
    save();
    if (result.account) {
      const id = sql(`select id from accounts where account_no='${result.account}'`);
      await page.goto(`/${T}/accounts/${id}`);
      await page.waitForTimeout(2500);
      const acct = await text(page);
      step(w.id, "clerk's account page shows it Active", acct.includes(result.account) && /Active/i.test(acct), result.account);
      await shot(page, w.id, "06-clerk-account");
      await page.goto(`/${T}/requests/${rec(w.id).request_id}`);
      await page.waitForTimeout(2000);
      const req = await text(page);
      step(w.id, "request page after fulfilment", /Approved/.test(req), (req.match(/Approved → [^\n]+/) ?? [""])[0]);
      await portalSees(w, result.account);
    }
  } catch (error) {
    step(w.id, "clerk flow", false, error.message.split("\n")[0]);
    await shot(page, w.id, "clerk-failed");
  } finally {
    save();
    await staff.close();
  }
}

// ════════════════════════════════════════════════════════════════════════════
// W13–W21
// ════════════════════════════════════════════════════════════════════════════
async function quickApply(id, { addr = "88 Riverbend Way", first = "Sam", last = "Okafor", files = true } = {}) {
  const w = { id, prem: "A", addr, unit: "", who: P(first, last, "1991-02-02"), email: `${id.toLowerCase()}@example.test`, phone: "(281) 555-0399", services: SIX, link: null, master: false, cls: "residential" };
  manifest[id] = { steps: [], walk: w };
  const ctx = await context();
  const page = await ctx.newPage();
  try {
    await guestApply(w, page);
  } finally {
    await ctx.close();
  }
  return w;
}

// The portal's Track page (CWP-012): the reference and ONE second fact — the
// ZIP code of the address applied for (quickApply's is 77494).
async function trackLookup(gp, reference, fact = "77494") {
  await gp.goto(`/${T}/portal/track`);
  await gp.waitForSelector("#cwp012-reference");
  await gp.fill("#cwp012-reference", reference);
  await gp.fill("#cwp012-second-fact", fact);
  await gp.getByRole("button", { name: /Look it up/ }).click();
  await gp.waitForTimeout(2500);
}

async function w13Decline() {
  const w = await quickApply("W13");
  const ctx = await context();
  const page = await ctx.newPage();
  const r = rec("W13");
  await staffSignIn(page, CLERK);
  await clerkSeesAndOpens(w, ctx, page);
  // BR-CUS-094, once: `government` is a legacy class and is not offered on a
  // new request (the server's refusal is test_portal_request_to_active case 9).
  await page.goto(`/${T}/requests/new?request=${r.request_id}`);
  await page.waitForSelector("#account_type_code", { timeout: 30000 });
  const classes = await page.locator("#account_type_code option").evaluateAll((os) => os.map((o) => o.value).filter(Boolean));
  step("W13", "the legacy government class is not offered on a new request", classes.length >= 7 && !classes.includes("government"), classes.join(", "));
  await page.goto(`/${T}/requests/${r.request_id}`);
  await page.click('[data-decision-action="refuse"]');
  const dlg = page.locator('[role="dialog"]').first();
  await dlg.waitFor();
  await page.selectOption("#reason_code", "documents_not_provided");
  await page.fill("#message_to_applicant", "We could not read the lease you sent. Please apply again with a clear copy.");
  await shot(page, "W13", "03-refuse");
  await dlg.getByRole("button", { name: "Refuse the request" }).click();
  await page.waitForTimeout(2500);
  const after = await text(page);
  step("W13", "request declined and says so", /Refused/.test(after));
  await shot(page, "W13", "04-refused");
  await ctx.close();
  const guest = await context();
  const gp = await guest.newPage();
  await trackLookup(gp, r.reference);
  const tracked = await text(gp, "aside:has([data-reference])");
  step("W13", "customer's Track page shows the refusal", /REFUSED/i.test(tracked), tracked.replace(/\s+/g, " ").slice(0, 200));
  const addOnRefused = await gp.locator("[data-track-add-document]").count();
  step("W13", "a refused request offers no Add a document", addOnRefused === 0, addOnRefused ? "OFFERED" : "not offered");
  await shot(gp, "W13", "05-portal-track");
  await guest.close();
  save();
}

async function w14MoreInfo() {
  const w = await quickApply("W14", { first: "Ama", last: "Boateng" });
  const ctx = await context();
  const page = await ctx.newPage();
  const r = rec("W14");
  await staffSignIn(page, CLERK);
  await clerkSeesAndOpens(w, ctx, page);
  await page.goto(`/${T}/requests/${r.request_id}`);
  await page.click('[data-decision-action="request_info"]');
  const dlg = page.locator('[role="dialog"]').first();
  await dlg.waitFor();
  // The box is the kit's visually-hidden input; its LABEL is what a clerk clicks.
  await page.locator('label[for="info-needed-proof_of_identity"]').click();
  await page.fill("#ask_message_to_applicant", "Please send a clearer photo of your ID.");
  await dlg.getByRole("button", { name: /Ask and queue/ }).click();
  await page.waitForTimeout(2500);
  step("W14", "clerk asks for more", /More info/.test(await text(page)));
  await shot(page, "W14", "03-more-info");
  const guest = await context();
  const gp = await guest.newPage();
  await trackLookup(gp, r.reference);
  const tracked = await text(gp, "aside:has([data-reference])");
  step("W14", "customer's Track page says more is needed", /MORE INFO NEEDED/i.test(tracked), tracked.replace(/\s+/g, " ").slice(0, 200));
  // DEF-CWP-9049 — Track offers Add a document while the request waits on the applicant.
  const addBox = gp.locator('[data-track-add-document] input[type="file"]');
  const offered = (await addBox.count()) > 0;
  step("W14", "customer's Track page offers Add a document", offered, offered ? "" : "no Add a document on Track");
  await shot(gp, "W14", "04-portal-track");
  if (offered) {
    await addBox.setInputFiles({ name: "w14-second-id.png", mimeType: "image/png", buffer: PNG });
    const sentRow = await gp
      .waitForSelector('[data-sent-file="w14-second-id.png"]', { timeout: 30000 })
      .then(() => true)
      .catch(() => false);
    step("W14", "customer sends a second document from the portal", sentRow, "w14-second-id.png");
    await shot(gp, "W14", "05-portal-sent-document");
  }
  // The application's own upload door, re-tried with the draft token: refused once sent.
  const res = await gp.request.post(`/api/${T}/portal/public/applications/${r.token}/documents`, {
    multipart: { file: { name: "w14-second-id.png", mimeType: "image/png", buffer: PNG } },
  });
  step("W14", "the sent application's upload door refuses a second file", res.status() >= 400, `${res.status()}`);
  await guest.close();
  // What the clerk sees: the customer's new file beside the two originals,
  // and the customer's reply on the request's History.
  await page.goto(`/${T}/requests/${r.request_id}?tab=documents`);
  await page.waitForTimeout(2500);
  const docs = await page.locator("[data-doc-open]").count();
  const docsText = await text(page);
  step("W14", "clerk sees a second document from the customer", docs > 2 && docsText.includes("w14-second-id.png"), `${docs} file(s) on the request`);
  await shot(page, "W14", "06-clerk-documents");
  const third = sql(`select id from service_request_documents where request_id='${r.request_id}' and name='w14-second-id.png' limit 1`);
  if (third) {
    const opened = await page.request.get(`/api/${T}/service-requests/${r.request_id}/documents/${third}/content?as=view`);
    step("W14", "clerk opens w14-second-id.png", opened.status() === 200 && (opened.headers()["content-type"] ?? "").startsWith("image/png"), `${opened.status()} ${opened.headers()["content-type"]}`);
  }
  await page.goto(`/${T}/requests/${r.request_id}?tab=history`);
  await page.waitForTimeout(2500);
  const history = await text(page);
  step("W14", "the request shows the customer replied", /Customer replied/.test(history), (history.match(/Customer replied[^\n]*/) ?? ["(not shown)"])[0]);
  await shot(page, "W14", "07-clerk-history");
  await ctx.close();
  save();
}

async function w15StartTooSoon() {
  manifest.W15 = { steps: [] };
  const ctx = await context();
  const page = await ctx.newPage();
  await page.goto(`/${T}/portal/start-service`);
  await page.fill("#availability-address", "88 Riverbend Way");
  await page.click('[data-action="check"]');
  await page.waitForSelector("[data-minitable]", { timeout: 30000 });
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 30000 });
  const soon = iso(workingDaysFromToday(1));
  await page.fill("#requested_start", soon);
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(1500);
  const shown = await text(page);
  const refused = /three working days/i.test(shown) && /(at least|refus|too soon|cannot)/i.test(shown);
  const saved = sql(`select coalesce(requested_start::text,'') from portal_application_drafts where token='${new URL(page.url()).pathname.split("/").pop()}'`);
  step("W15", "a start date under three working days is refused", refused && saved !== soon, `typed ${soon}; draft holds '${saved}'`);
  await shot(page, "W15", "01-start-too-soon");
  await ctx.close();
  save();
}

async function w16NoAddress() {
  manifest.W16 = { steps: [] };
  const ctx = await context();
  const page = await ctx.newPage();
  const token = "5f0e3a2c-6b1d-4e8f-9a7c-0d1e2f3a4b16";
  await page.goto(`/${T}/portal/start-service/${token}`);
  await page.waitForTimeout(3000);
  const shown = await text(page);
  const cont = page.locator('[data-action="continue"]');
  const held = (await cont.count()) === 0 || (await cont.isDisabled());
  const res = await page.request.post(`/api/${T}/portal/public/applications/${token}/submit`, { data: { paperless: false } });
  const body = await res.json().catch(() => ({}));
  step("W16", "an application with no address step cannot be sent", res.status() >= 400 && !body.reference, `${res.status()} ${body.message_key ?? ""} step=${body.params?.step ?? ""}`);
  step("W16", "the screen does not offer to carry on without an address", held || /address/i.test(shown), held ? "Continue held" : shown.replace(/\s+/g, " ").slice(0, 160));
  await shot(page, "W16", "01-no-address");
  await ctx.close();
  save();
}

async function w17ClosedTab() {
  manifest.W17 = { steps: [] };
  // The guest door allows sixty requests a minute per address (BR-CWP-022) and
  // every walk here comes from 127.0.0.1, so W13-W16 back to back use up the
  // minute; a real applicant is one person typing. Let the window clear, or the
  // name saves are answered 429 and the walk measures the throttle instead.
  await new Promise((done) => setTimeout(done, 61000));
  const ctx = await context();
  let page = await ctx.newPage();
  await page.goto(`/${T}/portal/start-service`);
  await page.fill("#availability-address", "88 Riverbend Way");
  await page.click('[data-action="check"]');
  await page.waitForSelector("[data-minitable]", { timeout: 30000 });
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 30000 });
  await page.fill("#requested_start", START);
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(800);
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-step="about"]', { timeout: 30000 });
  await page.fill("#first_name", "Kofi");
  await page.locator("#first_name").blur();
  await page.fill("#last_name", "Mensah");
  await page.locator("#last_name").blur();
  await page.fill("#email", "kofi.mensah@example.test");
  await page.locator("#email").blur();
  await page.waitForTimeout(1500);
  const url = page.url().split("?")[0];
  await page.close();
  page = await ctx.newPage();
  await page.goto(url);
  await page.waitForTimeout(3000);
  const values = await Promise.all(["#first_name", "#last_name", "#email"].map((s) => page.locator(s).inputValue().catch(() => "")));
  const head = await text(page);
  step("W17", "a closed tab keeps the draft", values[0] === "Kofi" && values[1] === "Mensah" && values[2] === "kofi.mensah@example.test", `${values.join(" | ")} · ${(head.match(/Picked up where you left off/) ?? ["(no resume head)"])[0]}`);
  await shot(page, "W17", "01-draft-kept");
  await ctx.close();
  save();
}

async function otherUtilityProbes(id, request) {
  const ctx = await context();
  const page = await ctx.newPage();
  await staffSignIn(page, OTHER_ADMIN, OTHER);
  const results = {};
  for (const [name, path] of [
    ["request detail", `/api/${OTHER}/service-requests/${request.request_id}`],
    ["request documents", `/api/${OTHER}/service-requests/${request.request_id}/documents`],
    ["request list search", `/api/${OTHER}/service-requests?q=${request.reference}`],
  ]) {
    const res = await page.request.get(path);
    const body = await res.text();
    results[name] = { status: res.status(), leaks: body.includes(request.reference) };
  }
  const docId = sql(`select id from service_request_documents where request_id='${request.request_id}' limit 1`);
  const content = await page.request.get(`/api/${OTHER}/service-requests/${request.request_id}/documents/${docId}/content?as=view`);
  results["document content"] = { status: content.status(), leaks: content.headers()["content-type"]?.startsWith("application/pdf") || content.headers()["content-type"]?.startsWith("image/") };
  await page.goto(`/${OTHER}/requests/${request.request_id}`);
  await page.waitForTimeout(2500);
  results["screen"] = { status: 0, leaks: (await text(page)).includes(request.reference) };
  await shot(page, id, "01-other-utility");
  const guest = await page.request.get(`/api/${OTHER}/portal/public/applications/${request.token}`);
  results["guest draft by token"] = { status: guest.status(), leaks: (await guest.text()).includes(request.reference) };
  await ctx.close();
  return results;
}

async function w18OtherUtilityRequest() {
  manifest.W18 = { steps: [] };
  const source = rec("W1").request_id ? rec("W1") : rec("W13");
  const results = await otherUtilityProbes("W18", source);
  for (const name of ["request detail", "request list search", "screen", "guest draft by token"]) {
    const one = results[name];
    step("W18", `another utility cannot see the request — ${name}`, !one.leaks && (one.status === 0 || one.status >= 400 || name === "request list search"), `${one.status ? `status ${one.status}` : "page opened"}, ${one.leaks ? "LEAKS the reference" : "reference not shown"}`);
  }
  save();
}

async function aboutStep(page) {
  await page.goto(`/${T}/portal/start-service`);
  await page.fill("#availability-address", "88 Riverbend Way");
  await page.click('[data-action="check"]');
  await page.waitForSelector("[data-minitable]", { timeout: 30000 });
  await page.click('[data-action="apply"]');
  await page.waitForSelector('[data-step="when"]', { timeout: 30000 });
  await page.fill("#requested_start", START);
  await page.locator("#requested_start").blur();
  await page.waitForTimeout(700);
  await page.click('[data-action="continue"]');
  await page.waitForSelector('[data-step="about"]', { timeout: 30000 });
}

async function w19WrongType() {
  manifest.W19 = { steps: [] };
  const ctx = await context();
  const page = await ctx.newPage();
  await aboutStep(page);
  const input = page.locator('[data-application-documents] input[type="file"]');
  await input.setInputFiles({ name: "notes.png", mimeType: "image/png", buffer: Buffer.from("<html><script>alert(1)</script></html>") });
  await page.waitForTimeout(2500);
  const shown = await text(page);
  const listed = await page.locator('[data-attached-file="notes.png"]').count();
  step("W19", "a file that is not PDF, JPG or PNG is refused by name", listed === 0 && /notes\.png/.test(shown), (shown.match(/notes\.png[^\n]*/) ?? ["(no sentence)"])[0]);
  await shot(page, "W19", "01-wrong-type");
  const held = sql(`select count(*) from portal_application_documents d join portal_application_drafts p on p.id=d.draft_id where p.token='${new URL(page.url()).pathname.split("/").pop()}'`);
  step("W19", "nothing was stored for the refused file", held === "0", `${held} row(s)`);
  await ctx.close();
  save();
}

async function w20TooBig() {
  manifest.W20 = { steps: [] };
  const ctx = await context();
  const page = await ctx.newPage();
  await aboutStep(page);
  const big = Buffer.concat([Buffer.from("%PDF-1.4\n"), Buffer.alloc(10 * 1024 * 1024 + 4096, 0x20), Buffer.from("\n%%EOF\n")]);
  const input = page.locator('[data-application-documents] input[type="file"]');
  await input.setInputFiles({ name: "scan-11mb.pdf", mimeType: "application/pdf", buffer: big });
  await page.waitForTimeout(4000);
  const shown = await text(page);
  const listed = await page.locator('[data-attached-file="scan-11mb.pdf"]').count();
  step("W20", "a file over 10 MB is refused by name", listed === 0 && /scan-11mb\.pdf/.test(shown), (shown.match(/scan-11mb\.pdf[^\n]*/) ?? ["(no sentence)"])[0]);
  await shot(page, "W20", "01-too-big");
  const held = sql(`select count(*) from portal_application_documents d join portal_application_drafts p on p.id=d.draft_id where p.token='${new URL(page.url()).pathname.split("/").pop()}'`);
  step("W20", "nothing was stored for the refused file", held === "0", `${held} row(s)`);
  await ctx.close();
  save();
}

async function w21OtherUtilityDocuments() {
  manifest.W21 = { steps: [] };
  const source = rec("W1").request_id ? rec("W1") : rec("W13");
  const results = await otherUtilityProbes("W21", source);
  for (const name of ["request documents", "document content"]) {
    const one = results[name];
    step("W21", `another utility cannot ${name === "request documents" ? "list" : "open"} the documents`, one.status >= 400 && !one.leaks, `status ${one.status}${one.leaks ? " LEAKS" : ""}`);
  }
  save();
}

// ════════════════════════════════════════════════════════════════════════════
for (const w of WALKS) if (wanted(w.id)) await walk(w);
const extras = { W13: w13Decline, W14: w14MoreInfo, W15: w15StartTooSoon, W16: w16NoAddress, W17: w17ClosedTab, W18: w18OtherUtilityRequest, W19: w19WrongType, W20: w20TooBig, W21: w21OtherUtilityDocuments };
for (const [id, fn] of Object.entries(extras)) {
  if (!wanted(id)) continue;
  console.log(`\n══ ${id}`);
  try {
    await fn();
  } catch (error) {
    step(id, "walk", false, error.message.split("\n")[0]);
  }
}
save();
await browser.close();
const fails = Object.entries(manifest).flatMap(([id, r]) => (r.steps ?? []).filter((s) => s.ok === false).map((s) => `${id} ${s.name}`));
console.log(`\nmanifest: ${MANIFEST}\nfailed steps: ${fails.length}`);
fails.forEach((f) => console.log(`  ✗ ${f}`));
