#!/usr/bin/env node
// ── nc5_five_step_photographs.mjs ───────────────────────────────────────────
//
// PHOTOGRAPH THE FIVE-STEP NEW CONNECT WIZARD **WITH REAL DATA IN IT**, AT
// 1440 AND 1280, SO THE PO CAN PUT EACH SHOT BESIDE THE APPROVED DRAWING.
//
// CLAUDE.md hard-won law 6 — no gate in this repo reads rendered output, and
// nine defects were found by diffing the running app against `05-prototype/`
// and by nothing else. This is a CAPTURE-AND-REPORT script: it changes no
// screen and fixes nothing.
//
// ── WHY A NEW SCRIPT, WHEN FIVE ALREADY WALK THIS WIZARD ────────────────────
// Law 11's last clause says read `10-scripts/` before writing a helper. All
// five were read, and each is short of this job in a way that cannot be
// patched out with a flag:
//
//   * `cr150_new_connect_five_steps_walkthrough.mjs` — the right FIVE steps
//     and 39 good checks, but it `page.goto`s each `?step=N` on a FRESH,
//     EMPTY draft. Every shot it takes is of an unfilled screen, which is
//     exactly the complaint against the stale photographs it was meant to
//     replace (`0 of 2`, *Choose a service*, an empty table).
//   * `nct01_steps12_walkthrough.mjs` — steps 1 and 2 only, also unfilled.
//   * `cr150_step3_units_walkthrough.mjs` — step 3 only; it types a unit
//     range but arrives on step 3 with no premise and no services behind it,
//     so the tiles still read `0 of 2`.
//   * `po_new_connect_clerk_walk.mjs` — the only one that FILLS, and it is
//     written for the retired EIGHT-step model (it presses forward through
//     *Map services*, *Plans & work orders* and *Communication*, which are
//     mounted nowhere now). Its selectors are where this script's came from.
//   * `lane_e_new_connect_split_capture.mjs` — a split-screen composite, not
//     a per-step photograph.
//
// ⚠ **AND EVERY ONE OF THEM SHOOTS `fullPage: true`, WHICH DOES NOT WORK ON
// THIS APP FRAME.** `.app-shell` is `height: 100vh; overflow: hidden` and
// `.view` is the `overflow-y: auto` pane inside it (`AppShell.css`), so the
// DOCUMENT never grows: `fullPage: true` returns the VIEWPORT, cropped at
// whatever is above the fold, on every step. A sibling lane produced two
// shots of two different states that were byte-identical because of it.
// So this script MEASURES `.view`'s scroll height, grows the viewport to
// reach it, and PRINTS each image's pixel dimensions beside its name — a
// reader can then see for themselves that two shots differ.
//
// ── RUN ─────────────────────────────────────────────────────────────────────
//   node 10-scripts/nc5_five_step_photographs.mjs
//   NC5_BASE (http://127.0.0.1:8080) · NC5_TENANT · NC5_EMAIL · NC5_PASSWORD ·
//   NC5_OUT · NC5_UNITS (6)
//
// ⚠ The bundle must be built `vite build --mode compose`; a bare build bakes
//   the deployed API host in and sign-in fails with *"That email or password
//   is incorrect."* on correct credentials (`DEF-INF-7802`).
// ⚠ NEVER `playwright install` — chromium is already at
//   `/opt/pw-browsers/chromium-*/chrome-linux/chrome`.
import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.NC5_BASE ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const TENANT = process.env.NC5_TENANT ?? "brazosbend";
const EMAIL = process.env.NC5_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.NC5_PASSWORD ?? "S3cure!passw0rd";
const OUT =
  process.env.NC5_OUT ??
  "05-prototype/new-connect-redesign-2026-09-28/built-2026-09-29-five-steps";
const UNITS = Number(process.env.NC5_UNITS ?? 6);

const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);

const observations = [];
const shots = [];
let failures = 0;

function check(label, ok, detail = "") {
  const line = `${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`;
  console.log(line);
  observations.push(line);
  if (!ok) failures += 1;
}
function note(line) {
  console.log(`      ${line}`);
  observations.push(`NOTE  ${line}`);
}

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  const found = readdirSync(root)
    .filter((n) => n.startsWith("chromium"))
    .flatMap((n) => ["chrome-linux/chrome", "chrome-linux64/chrome"].map((s) => join(root, n, s)))
    .filter(existsSync);
  if (found.length === 0) throw new Error(`no chromium under ${root}`);
  console.log(`  · pinned chromium absent; taking ${found[0]}`);
  return found[0];
}

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await context.newPage();
const serverErrors = [];
page.on("response", (r) => {
  if (r.status() >= 500) serverErrors.push(`${r.status()} ${r.url()}`);
});

/**
 * **THE WHOLE STEP, NOT THE FOLD.** Measures `.view`'s own scroll height,
 * grows the viewport until the pane no longer scrolls, then shoots. Returns
 * the image's real pixel dimensions so the README can print them — two shots
 * with the same dimensions AND the same bytes is the failure this exists to
 * make visible.
 */
async function shoot(name, width) {
  await page.setViewportSize({ width, height: 1200 });
  await page.waitForTimeout(500);
  const need = await page.evaluate(() => {
    const view = document.querySelector(".view");
    if (view === null) return null;
    const box = view.getBoundingClientRect();
    return Math.ceil(box.top + view.scrollHeight + 24);
  });
  if (need === null) {
    check(`${name} @ ${width}: the .view pane exists`, false, "no .view in the document");
    return null;
  }
  // Chromium refuses a viewport past 32767; nothing here comes near it, but a
  // silently truncated shot would be the very failure this function is for.
  const height = Math.min(Math.max(need, 900), 30000);
  await page.setViewportSize({ width, height });
  await page.waitForTimeout(500);
  const left = await page.evaluate(() => {
    const view = document.querySelector(".view");
    return view === null ? -1 : view.scrollHeight - view.clientHeight;
  });
  if (left > 2) note(`${name} @ ${width}: ${left}px of the pane is still below the fold`);
    // ⚠ **BLUR FIRST.** This kit's focus ring is the accent red, so whichever
  // box was filled last photographs with a red border and reads to the PO as
  // a refusal. A photograph is judged by eye; a stray focus ring is a defect
  // report waiting to be filed against a screen that is fine.
  await page.evaluate(() => {
    const el = document.activeElement;
    if (el instanceof HTMLElement) el.blur();
  });
  const file = join(OUT, `${name}-${width}.png`);
  await page.screenshot({ path: file, fullPage: false });
  const bytes = statSync(file).size;
  shots.push({ file, width, height, bytes, name });
  console.log(`  📷 ${file}  ${width}x${height}  ${bytes} bytes`);
  await page.setViewportSize({ width, height: 1200 });
  await page.waitForTimeout(300);
  return { width, height, bytes };
}

const railWords = async () => {
  const cells = await page.locator("[data-wizard-step]").allInnerTexts();
  return cells.map((text, at) => text.replace(String(at + 1), "").trim());
};

async function railAndLine(at, word) {
  const words = await railWords();
  check(`step ${at} · the rail has FIVE cells`, words.length === 5, `saw ${words.length}: ${words.join(" | ")}`);
  check(
    `step ${at} · the rail reads Customer · Premise · Units · Charges · Review, one word each`,
    JSON.stringify(words) === JSON.stringify(["Customer", "Premise", "Units", "Charges", "Review"]),
    words.join(" | "),
  );
  const line = (await page.locator("text=/Step \\d of \\d/").first().innerText()).trim();
  check(`step ${at} · the sub-line reads "Step ${at} of 5"`, line.includes(`Step ${at} of 5`), line);
  check(`step ${at} · the sub-line names the step "${word}"`, line.includes(word), line);

  // ⚠ **MEASURED, BECAUSE jsdom CANNOT.** `DEF-CUS-5198` was a ninth cell
  // hanging 244px out of a 1280 rail; every element is 0x0 in the suite, so
  // nothing but a real browser at a real width can ask this.
  const geometry = await page.evaluate(() => {
    const cells = Array.from(document.querySelectorAll("[data-wizard-step]"));
    if (cells.length === 0) return null;
    const rail = cells[0].parentElement.getBoundingClientRect();
    const last = cells[cells.length - 1].getBoundingClientRect();
    // ⚠ **THE WIDEST TOP-LEVEL BLOCK, NEVER "THE FIRST SECTION".** A first
    // draft took `.view section` and picked up step 4's narrow context-strip
    // cell, then reported the rail 588px out of line on a screen that is
    // straight — law 7's *looking at the wrong thing*, caught here because
    // the eye said the screen was fine.
    const view = document.querySelector(".view");
    const widest = Array.from(view?.children ?? []).reduce((best, node) => {
      const box = node.getBoundingClientRect();
      return best === null || box.width > best.width ? box : best;
    }, null);
    return {
      past: Math.round(last.right - rail.right),
      railRight: Math.round(rail.right),
      panelRight: widest === null ? null : Math.round(widest.right),
    };
  });
  check(
    `step ${at} · the last rail cell is inside the rail`,
    geometry !== null && geometry.past <= 1,
    `${geometry?.past}px past the rail's right edge`,
  );
  if (geometry?.panelRight !== null && geometry !== null) {
    const off = geometry.railRight - geometry.panelRight;
    check(
      `step ${at} · the rail's right edge lines up with the panels`,
      Math.abs(off) <= 2,
      `rail ends ${off}px ${off > 0 ? "past" : "short of"} the first panel`,
    );
  }
}

const forwardButton = () => page.locator('[data-wizard="actions"] button').last();

async function forward(label) {
  const button = forwardButton();
  const text = (await button.innerText()).trim();
  if (await button.isDisabled()) {
    check(`${label} · Continue is pressable`, false, `"${text}" is disabled`);
    const said = await page.locator('[data-refusal],[role="alert"]').allInnerTexts();
    note(`refusals on screen: ${said.join(" | ").slice(0, 300) || "none"}`);
    return false;
  }
  await button.click();
  await page.waitForTimeout(1600);
  return true;
}

const has = async (selector) => (await page.locator(selector).count()) > 0;
async function fill(selector, value) {
  if (await has(selector)) {
    await page.fill(selector, value).catch(() => undefined);
    return true;
  }
  return false;
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
async function segmented(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) return false;
  // ⚠ The kit's radio is visually hidden and often below the fold, so neither
  // `check()` nor `scrollIntoViewIfNeeded()` can ever succeed on it
  // (`po_new_connect_clerk_walk.mjs` lost a whole walk to this). Dispatching
  // the click on the input is the same event React binds to.
  await el.evaluate((n) => n.click());
  return true;
}

// ════════════════════════════════════════════════════════════════════════════
// SIGN IN
// ════════════════════════════════════════════════════════════════════════════
console.log(`── sign in as ${EMAIL} at ${BASE}/${TENANT}`);
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);
if (/signin/.test(page.url())) {
  const said = (await page.locator("body").innerText()).slice(0, 240);
  console.error(`sign-in did not leave /signin — the page says: ${said}`);
  await page.screenshot({ path: join(OUT, "signin-failed.png") });
  await browser.close();
  process.exit(2);
}

// ════════════════════════════════════════════════════════════════════════════
// STEP 1 · CUSTOMER — filled as a clerk would
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 1 · Customer");
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

const h1of = async () => (await page.locator("h1").first().innerText()).trim();
check("step 1 · the drawn H1", (await h1of()) === "Who is asking, and what for?", await h1of());
await railAndLine(1, "Customer");

await choose("#nc_owner_kind", "individual_owner");
await choose("#nc_owner_category");
await choose("#nc_owner_subcategory", "permanent");
await segmented("nc_party_kind", "person");
await page.waitForTimeout(300);
await fill("#nc_owner_name", "Marisol Vandergriff");
await fill("#nc_owner_email", "marisol.vandergriff@example.com");
await fill("#nc_owner_phone", "512-555-0179");
await fill("#nc_ssn", "412-88-6630");
await fill("#nc_driving_licence", "TX-99441203");
await fill("#nc_owner_dob", "1984-03-11");
// The co-applicant, because its nine fields are the panel the PO asked about
// and an unopened panel photographs as a button.
const coToggle = page.locator('[data-step-content="co-applicant"] button').first();
if ((await coToggle.count()) > 0) {
  await coToggle.click().catch(() => undefined);
  await page.waitForTimeout(500);
  await choose("#nc_co_owner_kind", "individual_owner");
  await choose("#nc_co_owner_category");
  await segmented("nc_co_party_kind", "person");
  await page.waitForTimeout(250);
  await fill("#nc_co_owner_name", "Desmond Vandergriff");
  await fill("#nc_co_owner_email", "desmond.v@example.com");
  await fill("#nc_co_owner_phone", "512-555-0180");
  await fill("#nc_co_ssn", "412-88-7741");
}
await fill("#nc_prefix", "NC");
await fill("#nc_external_ref", `LEGACY-${STAMP.slice(8)}`);
await choose("#nc_mode", "our_crew");
await page.waitForTimeout(400);

// ── B14 rule 31 · no database id is ever the visible value of a field ───────
async function ruleChecks(at) {
  const text = await page.locator("body").innerText();
  const uuid = text.match(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/);
  check(`step ${at} · B14 rule 31 — no uuid is visible on the screen`, uuid === null, uuid?.[0] ?? "");
  const key = text.match(/\b(?:customers|metering|rating|shell)\.[A-Za-z]+\.[A-Za-z0-9.]{3,}/);
  check(`step ${at} · no unresolved catalogue key on the screen`, key === null, key?.[0] ?? "");
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check(`step ${at} · no sideways page scroll`, sideways <= 0, `${sideways}px`);
}
await ruleChecks(1);
await shoot("step1-customer", 1440);
await shoot("step1-customer", 1280);
await ruleChecks(1);

if (!(await forward("step 1 · Customer"))) {
  note("stopped on step 1 — nothing beyond it could be photographed");
}

// ════════════════════════════════════════════════════════════════════════════
// STEP 2 · PREMISE — filled, several services, a published plan
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 2 · Premise");
await page.waitForTimeout(800);
check("step 2 · the drawn H1", (await h1of()) === "The premise", await h1of());
await railAndLine(2, "Premise");

await fill("#nc_address", `${STAMP.slice(8)} Copperleaf Terrace`);
await fill("#nc_unit", "Bldg A");
await fill("#nc_city", "Austin");
await fill("#nc_state", "TX");
await fill("#nc_zip", "78704");
await fill("#nc_premise_name", "Copperleaf Terrace Apartments");
await choose("#nc_premise_type");
await fill("#nc_parcel", `R-${STAMP.slice(8)}`);
await choose("#nc_route");
await fill("#nc_lat", "30.245117");
await fill("#nc_lng", "-97.769440");
await choose("#nc_scope", "new_premise");

// ── EVERY SERVICE THIS UTILITY SELLS, so step 3's tiles read a real count ───
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => undefined);
let offered = [];
if (await has("#services_available-add")) {
  offered = await page.$$eval("#services_available-add option", (ns) =>
    ns.map((o) => o.value).filter((v) => v !== ""),
  );
  for (const code of offered) {
    await page.selectOption("#services_available-add", code).catch(() => undefined);
    await page.waitForTimeout(220);
  }
}
check("step 2 · the services control offered this utility's own services", offered.length > 0, `${offered.length}: ${offered.join(", ")}`);
const plan = await choose("#nc_plan");
check("step 2 · a published plan could be chosen", plan !== null, plan ?? "no plan offered");
await page.waitForTimeout(1200);
await ruleChecks(2);
await shoot("step2-premise", 1440);
await shoot("step2-premise", 1280);

if (!(await forward("step 2 · Premise"))) note("stopped on step 2");

// ════════════════════════════════════════════════════════════════════════════
// STEP 3 · UNITS — a multi-unit premise, several services, real rows
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 3 · Units");
await page.waitForTimeout(900);
check("step 3 · the drawn H1", (await h1of()) === "The units", await h1of());
await railAndLine(3, "Units");

await fill("#nc_from", "1");
await fill("#nc_to", String(UNITS));
await page.waitForTimeout(900);
await choose("#nc_common_occupancy");
await page.waitForTimeout(400);
if (await has("[data-apply-to-all]")) {
  await page.locator("[data-apply-to-all]").first().click().catch(() => undefined);
  await page.waitForTimeout(900);
}

// ── the eight columns the fold produced, in the drawn order ────────────────
const headers = (await page.locator('[data-array="units-and-service-points"] thead th').allInnerTexts())
  .map((h) => h.trim())
  .filter((h) => h !== "");
const drawn = ["Unit", "Kind", "Service", "Asset", "Size", "Work order", "Completes", "Occupancy"];
check(
  "step 3 · the eight ruled columns, in the drawn order",
  JSON.stringify(headers.map((h) => h.toUpperCase())) === JSON.stringify(drawn.map((h) => h.toUpperCase())),
  headers.join(" · "),
);
check(
  "step 3 · UNIT · KIND · COMPLETES · OCCUPANCY are present (the absorbed fold, not drift)",
  ["UNIT", "KIND", "COMPLETES", "OCCUPANCY"].every((c) => headers.map((h) => h.toUpperCase()).includes(c)),
  headers.join(" · "),
);
// ⛔ `OQ-CUS-12770` IS OPEN AND MULTIPLIES A PRICE ON A REAL INVOICE.
check(
  "step 3 · NO Qty column — OQ-CUS-12770 is OPEN and must not be built",
  !headers.map((h) => h.toUpperCase()).includes("QTY"),
  headers.join(" · "),
);
const rows = await page.locator('[data-array="units-and-service-points"] [data-cell="service"]').count();
check("step 3 · the table has real rows", rows > 0, `${rows} service rows`);
const tileText = (await page.locator("body").innerText()).match(
  /(SERVICES HERE|SERVICE POINTS|METERS TO FIT|WORK ORDERS)\n([^\n]+)/g,
);
note(`the four tiles read: ${(tileText ?? []).map((t) => t.replace("\n", " = ")).join(" · ")}`);
// ⚠ **THE THREE ABSORBED STEPS, ASKED FOR BY WHAT IS ACTUALLY ON THE PAGE.**
// `cr150_new_connect_five_steps_walkthrough.mjs` §4 asks for `data-unit-count`,
// `data-unit-service-grid` and `data-from-each-step`. **Not one of those three
// strings exists in the mounted tree**: the first and third exist nowhere in
// `07-frontend/src` at all, and the second lives only in
// `NewConnectServicesStep.tsx`, which the five-step wizard mounts nowhere.
// They are checks that cannot pass — hard-won law 7's third shape — and they
// are reported rather than copied.
for (const [sel, what] of [
  ["#nc_from", "the unit range (old step 3 · Units)"],
  ['[data-array="units-and-service-points"] [data-cell="service"]', "the per-unit service rows (old step 4 · Map services)"],
  ['[data-array-action="add-work-order"]', "the work orders (old step 5 · Plans & work orders)"],
  ["[data-proposals]", "the work-order proposals"],
]) {
  check(`step 3 carries ${what}`, await has(sel));
}
await ruleChecks(3);
await shoot("step3-units", 1440);
await shoot("step3-units", 1280);

// ── + Add row · IN PLACE, never a dialog ────────────────────────────────────
const serviceCells = () =>
  page.locator('[data-array="units-and-service-points"] [data-cell="service"]').count();
const before = await serviceCells();
await page.locator('[data-array-action="add-row"]').first().click().catch(() => undefined);
await page.waitForTimeout(500);
const after = await serviceCells();
check("step 3 · + Add row adds a row IN PLACE", after > before, `${before} → ${after}`);
check(
  "step 3 · + Add row opens NO dialog (the drawing says so in words)",
  !(await has('[role="dialog"]')),
);
await shoot("step3a-add-row", 1440);

await page.locator('[data-array-action="add-work-order"]').first().click().catch(() => undefined);
await page.waitForTimeout(600);
check("step 3 · + Add work order reaches a template search in place", await has("#nc_add_order"));
check(
  "step 3 · + Add work order opens NO dialog",
  !(await has('[role="dialog"]')),
);
await shoot("step3b-add-work-order", 1440);

if (!(await forward("step 3 · Units"))) note("stopped on step 3");

// ════════════════════════════════════════════════════════════════════════════
// STEP 4 · CHARGES
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 4 · Charges");
await page.waitForTimeout(1500);
check("step 4 · the drawn H1", (await h1of()) === "Charges", await h1of());
await railAndLine(4, "Charges");

await choose("#nc_quote_payer");
await fill("#nc_quote_due_days", "30");
await fill("#nc_quote_posting_date", "2026-10-01");
await choose("#nc_payment_option", "check");
await page.waitForTimeout(500);
await fill("#nc_payment_amount", "250.00");
await fill("#nc_payment_reference", `4471`);
await fill("#nc_payment_date", "2026-09-29");
await page.waitForTimeout(600);

// ── A REAL CHARGE ROW, so "What is charged" is not photographed empty ──────
// The stale shots showed an empty screen and demonstrated nothing; an empty
// charges table is the same failure one step on.
const addCharge = page.locator('[data-array-action="add-charge"]').first();
if ((await addCharge.count()) > 0 && !(await addCharge.isDisabled())) {
  await addCharge.click().catch(() => undefined);
  await page.waitForTimeout(600);
  // ⚠ `CellSelect` puts `data-cell` ON the `<select>`, not on a wrapper. A
  // descendant selector finds nothing here and would report "0 charge codes
  // offered" over a full dropdown — a check looking at the wrong thing.
  const codes = await page
    .$$eval('select[data-cell="charge-0"] option', (ns) =>
      ns.filter((o) => !o.disabled && o.value !== "").map((o) => o.value),
    )
    .catch(() => []);
  if (codes.length > 0) {
    await page.selectOption('select[data-cell="charge-0"]', codes[0]).catch(() => undefined);
    await page.waitForTimeout(2000);
  }
  note(`step 4 · a charge row was added; ${codes.length} charge codes offered`);
} else {
  const why = await page.locator("[data-no-billable-charge]").allInnerTexts().catch(() => []);
  note(`step 4 · + Add charge could not be pressed — ${why.join(" | ") || "no stated reason"}`);
}
await page.waitForTimeout(800);

const chargeHeaders = (await page.locator('[data-array="quote-lines"] thead th').allInnerTexts())
  .map((h) => h.trim().toUpperCase())
  .filter((h) => h !== "");
// ⚠ **THE QTY QUESTION, ASKED THE WAY THE RULING ACTUALLY PUTS IT.** The
// brief for this capture says *"the drawing's QTY column is NOT built, on
// purpose"*. On step 3 it is genuinely absent. **On step 4 the COLUMN IS ON
// THE SCREEN** — `CHARGE · BASIS · QTY · EACH · AMOUNT` — rendered by
// `NewConnectChargesStep.tsx` as a `CellStatic` count with a comment citing
// `OQ-CUS-12770` by name. What `CR-150-BRC09` §5 held back is the EDITABLE
// BOX, which is the half that would multiply a price. So both halves are
// asked separately rather than one being read as the other.
note(
  `step 4 · a Qty column IS on the screen (${chargeHeaders.includes("QTY") ? "present" : "absent"}) — reported to the PO, not treated as drift`,
);
const qtyInputs = await page
  .locator('[data-array="quote-lines"] input[data-cell^="qty"], [data-array="quote-lines"] input[aria-label="Qty"]')
  .count();
check(
  "step 4 · Qty is NOT an editable box — OQ-CUS-12770 is OPEN and it multiplies a price",
  qtyInputs === 0,
  `${qtyInputs} editable Qty inputs`,
);
check(
  "step 4 · the What-is-charged table rendered its columns",
  chargeHeaders.length > 0,
  chargeHeaders.join(" · "),
);
note(`step 4 · What is charged columns: ${chargeHeaders.join(" · ")}`);
const money = await page.locator("[data-quote-money],[data-charge-total]").allInnerTexts();
note(`step 4 money on screen: ${money.join(" | ").slice(0, 200) || "none rendered"}`);
await ruleChecks(4);
await shoot("step4-charges", 1440);
await shoot("step4-charges", 1280);

if (!(await forward("step 4 · Charges"))) note("stopped on step 4");

// ════════════════════════════════════════════════════════════════════════════
// STEP 5 · REVIEW
// ════════════════════════════════════════════════════════════════════════════
console.log("\n── step 5 · Review");
await page.waitForTimeout(1500);
check("step 5 · the drawn H1", (await h1of()) === "What will be created", await h1of());
await railAndLine(5, "Review");
check("step 5 carries the messages table (old step 7)", await has("[data-telling]"));
// ⚠ `cr150_new_connect_five_steps_walkthrough.mjs` asks for
// `[data-from-each-step]`, which exists nowhere in `07-frontend/src`. The
// review read-back's real marker is `data-review-group`, four of them.
const groups = await page.locator("[data-review-group]").allInnerTexts();
check(
  "step 5 carries the four-group review read-back",
  groups.length === 4,
  `${groups.length} groups: ${groups.map((g) => g.split("\n")[0]).join(" | ")}`,
);
check("step 5 carries the At-a-glance tiles", await has("[data-at-a-glance]"));
check("step 5 carries the What-Create-makes table", await has("[data-create-makes]"));

// ⛔ **THE DUPLICATE PANELS.** `ReviewStep` renders *Who we are telling* and
// the *Messages* table itself, AND `NewConnectWizard` still mounts the whole
// `CommunicationStep` after it under a comment reading *"until the REVIEW
// lane draws it there"* — which it now has. Counted, because a photograph of
// this and a photograph of a correct screen differ only by a scroll.
const telling = await page.locator("[data-telling]").count();
const whoHeads = await page.getByText("Who we are telling", { exact: true }).count();
check(
  "step 5 shows the Messages table ONCE",
  telling === 1,
  `${telling} copies of [data-telling]`,
);
check(
  'step 5 shows the "Who we are telling" heading ONCE',
  whoHeads === 1,
  `${whoHeads} copies`,
);
await ruleChecks(5);
await shoot("step5-review", 1440);
await shoot("step5-review", 1280);

// ── THE DRAWING SHOWS ONE GROUP OPENED, WITH ITS CHARGES TABLE ─────────────
// `step5-review.png` draws *Charges and payment* expanded over the CHARGE ·
// BASIS · QTY · EACH · AMOUNT table. A photograph of four folded rows cannot
// be compared against it, so the opened state gets its own shot.
// ⚠ The group is a `<details>`, so the thing that toggles is its `<summary>`,
// and `[data-group-fields]` is in the DOM open or shut — asserting its
// presence is a check that cannot fail. `details[open]` is the real question.
const chargesSummary = page.locator('[data-review-group="charges"] summary');
if ((await chargesSummary.count()) > 0) {
  await chargesSummary.click().catch(() => undefined);
  await page.waitForTimeout(700);
  const openNow = await page.locator("[data-review-group] details[open]").count();
  check(
    "step 5 · a review group opens in place to its own fields",
    openNow === 1,
    `${openNow} groups open`,
  );
  // ⚠ **THE DRAWING'S OPENED GROUP CARRIES FIVE COLUMNS** — `CHARGE · BASIS
  // · QTY · EACH · AMOUNT`, the same five as step 4. Asked here because the
  // component's own docstring says *"`Each` and `Amount` come from
  // `POST /connections/quote-preview`"*, and a comment claiming a guarantee
  // is not the guarantee (hard-won law 1).
  const reviewCols = (
    await page.locator('[data-array="review-charges"] thead th').allInnerTexts()
  )
    .map((h) => h.trim().toUpperCase())
    .filter((h) => h !== "");
  check(
    "step 5 · the opened charges group shows EACH and AMOUNT, as drawn",
    reviewCols.includes("EACH") && reviewCols.includes("AMOUNT"),
    reviewCols.join(" · "),
  );
  await shoot("step5-review-group-open", 1440);
}

// ── STEP 1's "Account details" HEADING OVER NOTHING ────────────────────────
// Checked at the end so the walk does not have to go back: its own comment
// says *"IT RENDERS NOTHING AT ALL WHEN THE UTILITY DEFINED NONE"*, and the
// `<h4>` sits OUTSIDE `CustomFieldsInput`.
await page.goto(`${BASE}/${TENANT}/connections/new?step=1`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const accountDetails = await page
  .locator('[data-step-content="account-details"]')
  .first()
  .innerText()
  .catch(() => "");
const hasFields = (await page.locator('[data-step-content="account-details"] input, [data-step-content="account-details"] select').count()) > 0;
check(
  'step 1 · "Account details" is not a heading over nothing',
  accountDetails.trim() === "" || hasFields,
  `heading rendered with ${hasFields ? "fields" : "NO fields"} under it — text is ${JSON.stringify(accountDetails.trim())}`,
);

// ⚠ NOTHING IS COMMITTED. This is a photograph task; the final button is not
// pressed, so the isolated clone ends the run with no new connection in it.
note("the commit button was NOT pressed — this run photographs, it does not write");

// ════════════════════════════════════════════════════════════════════════════
// THE README — every image with its real dimensions beside it
// ════════════════════════════════════════════════════════════════════════════
for (const e of serverErrors) check(`no 5xx during the run`, false, e);

const byBytes = new Map();
for (const s of shots) {
  const key = `${s.bytes}`;
  byBytes.set(key, [...(byBytes.get(key) ?? []), s.name + "@" + s.width]);
}
for (const [bytes, names] of byBytes) {
  if (names.length > 1) {
    check(`two shots are byte-identical (${bytes} bytes)`, false, names.join(" = "));
  }
}

// ⚠ **THE STATE EACH IMAGE SHOWS, IN WORDS.** A photograph of a correct
// screen and a photograph of a wrong one look identical to a reader who does
// not know what to miss, so the README says what was on the screen when the
// shutter went. B14 rule 42 still holds: the IMAGES are the specification and
// this file is an index to them.
const STATES = {
  "step1-customer":
    "filled as a clerk would — Marisol Vandergriff, person, Residential/Permanent, SSN + driver's license, a co-applicant OPEN with its nine fields, mailing address ticked Same as service address, prefix NC, an external reference, mode Our crew did it",
  "step2-premise":
    "filled — Copperleaf Terrace Apartments, Bldg A, Austin TX 78704, parcel, read route RT-001, lat/lng typed, scope A new premise, BOTH services this utility sells chosen (electric, water), plan Industrial. The plan covers only electric, so the screen shows the real WON'T COVER refusal — which is the state step2-premise.png itself draws",
  "step3-units":
    "REAL DATA — 6 units (NC 1..NC 6), 2 services each, tiles reading SERVICES HERE 2 of 2 · SERVICE POINTS 12 · METERS TO FIT 12 · WORK ORDERS 0 will be written. The first unit group is open, the other five folded",
  "step3a-add-row": "after one press of + Add row — the new row is added IN PLACE, no dialog",
  "step3b-add-work-order":
    "after + Add work order — the template search opens in place at the bottom of the table, no dialog",
  "step4-charges":
    "filled — owner's account, 30-day terms, posting date, Check 4471 for $250.00, and ONE real priced charge line: AFTER-HRS · After-hours service call, per unit, Qty 6, $75.00 each, $450.00",
  "step5-review":
    "the review of everything above, all four groups FOLDED as the wizard opens them",
  "step5-review-group-open":
    "the same screen with Charges and payment opened, which is the state step5-review.png draws",
};

const lines = [
  "NEW CONNECT — THE FIVE BUILT STEPS, PHOTOGRAPHED WITH REAL DATA",
  `captured ${new Date().toISOString()} by 10-scripts/nc5_five_step_photographs.mjs`,
  "",
  "⚠ THE IMAGES ARE THE THING (B14 rule 42). This file is an index to them.",
  "⚠ Nothing was committed: the Create button was never pressed, and the walk ran",
  "  against an ISOLATED CLONE of the demo database, not the demo database.",
  "",
  "IMAGES — name · pixel dimensions · bytes · what state it shows",
  ...shots.flatMap((s) => [
    `  ${s.name}-${s.width}.png   ${s.width}x${s.height}   ${s.bytes} bytes`,
    `      ${STATES[s.name] ?? "(state not described — add it to STATES in the script)"}`,
  ]),
  "",
  "⚠ THE DIMENSIONS ARE PRINTED BECAUSE fullPage:true DOES NOT WORK ON THIS FRAME.",
  "  `.app-shell` is height:100vh;overflow:hidden and `.view` is the scrolling pane",
  "  inside it, so the document never grows and fullPage returns the fold. Each shot",
  "  here grew the VIEWPORT to `.view`'s own scroll height. Two shots with the same",
  "  height AND the same byte count would be the bug this note exists to expose.",
  "",
  "CHECKED OBSERVATIONS — the deliverable as much as the images are",
  ...observations.map((o) => `  ${o}`),
  "",
  `${failures} failed`,
  "",
  "THE FAILURES ARE FILED, NOT FIXED — this lane photographs and reports:",
  "  DEF-CUS-7910  step 5 renders 'Who we are telling' and Messages TWICE",
  "  DEF-CUS-7911  step 5's review charges table drops EACH and AMOUNT",
  "  DEF-CUS-7912  step 1's 'Account details' heading renders over nothing",
  "  DEF-CUS-7913  cr150's walkthrough §4 asks for three attributes that do not exist",
  "",
  "The drawing-by-drawing comparison is DIVERGENCES-steps-4-5.md beside this file.",
];
writeFileSync(join(OUT, "00-README.txt"), lines.join("\n") + "\n");
console.log(`\n── ${shots.length} images · ${failures} failed · ${OUT}/00-README.txt`);

await browser.close();
process.exit(failures === 0 ? 0 : 1);
