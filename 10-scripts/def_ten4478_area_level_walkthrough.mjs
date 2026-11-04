#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defect: DEF-TEN-4478 — Settings → Reference data → Areas & sub-areas. The Add
//         dialog gave no visible sign which of the two it was making.
// Rules:  BR-MET-066b · B14 rules 8, 31, 32 · hard-won law 6 (diff the running
//         app; NO gate in this repo reads rendered output, which is why the
//         Product Owner is the one who found this)
// ───────────────────────────────────────────────────────
// WHAT THIS ANSWERS THAT A jsdom TEST CANNOT
// ------------------------------------------
// Three things, and only the first is about the fix:
//
//   1. The four flows END TO END, against the real API and a real database —
//      create an area, create a sub-area, edit an area, edit a sub-area — and
//      then the TABLE's own agreement with what was done: the Parent area
//      column and the "· N sub-areas" suffix.
//   2. Whether the dialog opens BLANK on a fresh load. That is the half of the
//      PO's report a unit test cannot settle: their screenshot showed `DTWN` in
//      Code and `Downtown` in the picker on a dialog they had just opened.
//   3. What a browser fill would actually DO now, reproduced the only way it
//      can be here — by writing the element's value with no React change event,
//      which is precisely what a real autofill does to a controlled input.
//
// ⚠ IT CANNOT REPRODUCE CHROME'S AUTOFILL ITSELF and does not pretend to:
// profile autofill needs a saved address/credential profile, and a Playwright
// context has none. So this measures the two things that ARE measurable — the
// initial state, and the consequence of a fill — and says so.
//
//   node 10-scripts/def_ten4478_area_level_walkthrough.mjs
//   env: BASE (http://127.0.0.1:8478) TENANT EMAIL PASSWORD OUT
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8478";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/ten4478-shots";

const failures = [];
const notes = [];
function ok(m) { console.log(`  ✓ ${m}`); }
function bad(m) { failures.push(m); console.error(`  ✗ ${m}`); }
function note(m) { notes.push(m); console.log(`  · ${m}`); }
function check(cond, m) { cond ? ok(m) : bad(m); }

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const c = join(root, dir, sub);
        if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium found");
}

const AREAS = `${BASE}/${TENANT}/settings/reference-data/reference-data?list=areas`;

// Codes are unique per tenant (BR-TEN-030), so a fixed code makes this script
// runnable exactly once against a given database — which is a walkthrough that
// passes for the first lane and refuses for the next. A per-run stamp keeps it
// re-runnable, and the names carry it too so the table assertions cannot match
// a row an earlier run left behind.
const RUN = Date.now().toString(36).slice(-5).toUpperCase();
const AREA_CODE = `WT${RUN}A`;
const SUB_CODE = `WT${RUN}S`;
const FILL_CODE = `WT${RUN}F`;
const AREA_NAME = `Walkthrough district ${RUN}`;
const SUB_NAME = `Walkthrough sub ${RUN}`;
const FILL_NAME = `Walkthrough fill ${RUN}`;

/** Choose a segment the way a PERSON does — by clicking the visible label.
 *  `SegmentedField` hides the radio itself (`.seg-opt input { opacity:0;
 *  width:0; height:0; pointer-events:none }`) and styles the label around it,
 *  which is r10's own markup. The input stays in the tab order and keeps its
 *  focus ring through `.seg-opt:has(input:focus-visible)`, so this is a
 *  presentation choice and not a keyboard trap — but a click has to land on
 *  the label, and a test that clicks the input is not testing the control. */
async function chooseLevel(dialog, label) {
  await dialog.locator("label.seg-opt").filter({ hasText: new RegExp(`^${label}$`) }).click();
  await dialog.page().waitForTimeout(250);
}

async function openAdd(page) {
  await page.getByRole("button", { name: /Add entry/i }).click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor({ state: "visible" });
  return dialog;
}

/** The row's own Edit button, found by the row's NAME cell. */
async function openEdit(page, name) {
  const row = page.locator("tr", { hasText: name }).first();
  await row.getByRole("button", { name: /Edit/i }).click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor({ state: "visible" });
  return dialog;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium(), headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.on("response", (r) => {
    if (r.status() >= 500) bad(`5xx from ${r.url()} (${r.status()})`);
  });

  console.log(`\n── sign in ──`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  // Wait for the session POST itself, not for "networkidle" — the SPA fires
  // its first authenticated reads the moment the 201 lands, and a click that
  // only waits for the network to go quiet returns before any of it (which
  // reads as three 401s and a screen that never left /signin).
  await Promise.all([
    page.waitForResponse((r) => r.url().includes("/auth/session") && r.request().method() === "POST"),
    page.getByRole("button", { name: /Sign in/i }).click(),
  ]);
  await page.waitForTimeout(2500);
  check(!page.url().endsWith("/signin"), `signed in as ${EMAIL} (now at ${page.url()})`);

  console.log(`\n── 1 · the dialog opens BLANK, on Area, and says so ──`);
  await page.goto(AREAS, { waitUntil: "networkidle" });
  await page.waitForSelector("table", { timeout: 20000 });
  await page.waitForTimeout(600);
  let d = await openAdd(page);
  await page.screenshot({ path: join(OUT, "01-add-opens-on-area.png"), fullPage: true });

  const heading = (await d.getByRole("heading").first().textContent())?.trim();
  check(heading === "Add an area", `title reads "${heading}" (want "Add an area")`);
  const areaRadio = d.getByRole("radio", { name: "Area", exact: true });
  const subRadio = d.getByRole("radio", { name: "Sub-area", exact: true });
  check(await areaRadio.isChecked(), "the Area segment is the one chosen");
  check(!(await subRadio.isChecked()), "the Sub-area segment is not chosen");
  check((await d.locator("#parent_code").count()) === 0, "no Parent area picker is drawn");

  // The PO's own observation, measured: what is in the fields on a fresh open?
  const codeVal = await d.locator("#code").inputValue();
  const nameVal = await d.locator("#name").inputValue();
  check(codeVal === "", `the Code box opens empty (read "${codeVal}")`);
  check(nameVal === "", `the Name box opens empty (read "${nameVal}")`);
  check(
    (await d.locator("#code").getAttribute("autocomplete")) === "off",
    "the Code box refuses browser fill (autocomplete=off)",
  );
  const body = (await d.textContent()) ?? "";
  check(!body.includes("Leave blank for an area"), "the sentence that carried the whole choice is gone");

  console.log(`\n── 2 · choosing Sub-area moves the title and reveals the picker ──`);
  await chooseLevel(d, "Sub-area");
  await page.waitForTimeout(200);
  const heading2 = (await d.getByRole("heading").first().textContent())?.trim();
  check(heading2 === "Add a sub-area", `title now reads "${heading2}"`);
  const picker = d.locator("#parent_code");
  check((await picker.count()) === 1, "the Parent area picker appears");
  const optionText = await picker.locator("option").allTextContents();
  check(optionText[0] === "Select the parent area", `its first option is the prompt, not a district (read "${optionText[0]}")`);
  check((await picker.inputValue()) === "", "and it opens on that prompt, not on a district");
  note(`picker offers: ${optionText.join(" | ")}`);
  await page.screenshot({ path: join(OUT, "02-add-sub-area.png"), fullPage: true });

  console.log(`\n── 3 · a sub-area with no parent is refused HERE, not turned into an area ──`);
  await d.locator("#code").fill(`WT${RUN}N`);
  await d.locator("#name").fill(`Walkthrough no parent ${RUN}`);
  await d.getByRole("button", { name: "Add entry", exact: true }).click();
  await page.waitForTimeout(500);
  const refused = (await d.textContent()) ?? "";
  check(refused.includes("Pick the area it sits under."), "it says which area to pick");
  check((await page.getByRole("dialog").count()) === 1, "and the dialog is still open");
  await page.screenshot({ path: join(OUT, "03-sub-area-needs-parent.png"), fullPage: true });

  console.log(`\n── 4 · CREATE AN AREA ──`);
  await chooseLevel(d, "Area");
  await d.locator("#code").fill(AREA_CODE);
  await d.locator("#name").fill(AREA_NAME);
  await d.getByRole("button", { name: "Add entry", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.waitForLoadState("networkidle");
  let table = (await page.locator("table").first().textContent()) ?? "";
  check(table.includes(AREA_NAME), "the area is in the table");
  await page.screenshot({ path: join(OUT, "04-area-created.png"), fullPage: true });

  console.log(`\n── 5 · CREATE A SUB-AREA under it ──`);
  d = await openAdd(page);
  await chooseLevel(d, "Sub-area");
  await d.locator("#code").fill(SUB_CODE);
  await d.locator("#name").fill(SUB_NAME);
  await d.locator("#parent_code").selectOption({ label: AREA_NAME });
  await d.getByRole("button", { name: "Add entry", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.waitForLoadState("networkidle");

  // The table's own agreement with what was just done.
  const subRow = page.locator("tr", { hasText: SUB_NAME }).first();
  const subRowText = (await subRow.textContent()) ?? "";
  check(subRowText.includes(AREA_NAME), `the Parent area column names its parent (row: ${subRowText.replace(/\s+/g, " ").trim()})`);
  const parentRowText = (await page.locator("tr", { hasText: AREA_NAME }).first().textContent()) ?? "";
  check(parentRowText.includes("1 sub-area"), `the parent row counts it (row: ${parentRowText.replace(/\s+/g, " ").trim()})`);
  await page.screenshot({ path: join(OUT, "05-sub-area-created.png"), fullPage: true });

  console.log(`\n── 6 · EDIT THE SUB-AREA — opens on Sub-area, parent already named ──`);
  d = await openEdit(page, SUB_NAME);
  const h6 = (await d.getByRole("heading").first().textContent())?.trim();
  check(h6 === "Edit a sub-area", `title reads "${h6}"`);
  check(await d.getByRole("radio", { name: "Sub-area", exact: true }).isChecked(), "the Sub-area segment is chosen");
  await page.waitForTimeout(600);
  const pickedParent = await d.locator("#parent_code").inputValue();
  check(pickedParent === AREA_CODE, `its parent is already named (picker reads "${pickedParent}")`);
  await page.screenshot({ path: join(OUT, "06-edit-sub-area.png"), fullPage: true });
  await d.locator("#name").fill(`${SUB_NAME} renamed`);
  await d.getByRole("button", { name: "Save entry", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.waitForLoadState("networkidle");
  const renamed = (await page.locator("tr", { hasText: `${SUB_NAME} renamed` }).first().textContent()) ?? "";
  check(renamed.includes(AREA_NAME), "and it kept its parent through the save");

  console.log(`\n── 7 · EDIT THE AREA — opens on Area, no picker to leave blank ──`);
  d = await openEdit(page, AREA_NAME);
  const h7 = (await d.getByRole("heading").first().textContent())?.trim();
  check(h7 === "Edit an area", `title reads "${h7}"`);
  check(await d.getByRole("radio", { name: "Area", exact: true }).isChecked(), "the Area segment is chosen");
  check((await d.locator("#parent_code").count()) === 0, "no Parent area picker is drawn");
  await page.screenshot({ path: join(OUT, "07-edit-area.png"), fullPage: true });
  await d.locator("#name").fill(`${AREA_NAME} renamed`);
  await d.getByRole("button", { name: "Save entry", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.waitForLoadState("networkidle");
  const areaRow = (await page.locator("tr", { hasText: `${AREA_NAME} renamed` }).first().textContent()) ?? "";
  check(areaRow.includes("1 sub-area"), "it is still top level and still counts its sub-area");

  console.log(`\n── 8 · A FILL NOBODY CHOSE cannot change what gets made ──`);
  // A real autofill writes the element and fires no React change event. That is
  // exactly what this does, and it is the reproducible half of the PO's report.
  d = await openAdd(page);
  await chooseLevel(d, "Sub-area");
  await page.waitForTimeout(200);
  await d.locator("#parent_code").evaluate((el, code) => { el.value = code; }, AREA_CODE);
  const shown = await d.locator("#parent_code").inputValue();
  note(`the picker now DISPLAYS "${shown}" without the screen ever being told`);
  await chooseLevel(d, "Area");
  await d.locator("#code").fill(FILL_CODE);
  await d.locator("#name").fill(FILL_NAME);
  await d.getByRole("button", { name: "Add entry", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.waitForLoadState("networkidle");
  const fillRow = (await page.locator("tr", { hasText: FILL_NAME }).first().textContent()) ?? "";
  check(!fillRow.includes(AREA_NAME), `it was made as an AREA, not under the filled parent (row: ${fillRow.replace(/\s+/g, " ").trim()})`);
  await page.screenshot({ path: join(OUT, "08-fill-ignored.png"), fullPage: true });

  console.log(`\n── 9 · the OTHER tree through this dialog is unchanged ──`);
  await page.goto(`${BASE}/${TENANT}/settings/reference-data/reference-data?list=account_subtypes`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  d = await openAdd(page);
  check((await d.getByRole("radiogroup").count()) === 0, "account sub-types get no Area/Sub-area chooser");
  check((await d.locator("#parent_code").count()) === 1, "their Account type picker is drawn as it always was");
  const h9 = (await d.getByRole("heading").first().textContent())?.trim();
  note(`its title still reads "${h9}"`);
  await page.screenshot({ path: join(OUT, "09-account-subtypes.png"), fullPage: true });

  console.log(`\n── 10 · clean up after itself ──`);
  // A walkthrough that leaves rows behind is a walkthrough the next lane runs
  // once. Deleted through the API on the page's own session, SUB-AREA FIRST:
  // the server refuses to delete an area that still has children and names
  // them (BR-MET-066b), which is correct and is not what this step is testing.
  const api = `${BASE}/api/${TENANT}/lookups/areas`;
  const listed = await page.request.get(`${api}?per=200`);
  const rows = (await listed.json()).results ?? [];
  const mine = [SUB_CODE, AREA_CODE, FILL_CODE, `WT${RUN}N`]
    .map((code) => rows.find((r) => r.code === code))
    .filter(Boolean);
  let removed = 0;
  for (const row of mine) {
    const res = await page.request.delete(`${api}/${row.id}`);
    if (res.ok()) removed += 1;
    else bad(`could not remove ${row.code}: ${res.status()}`);
  }
  // `WT${RUN}N` was refused at the form and never created, so three is right.
  check(removed === mine.length, `removed ${removed} of the ${mine.length} rows this run created`);

  await browser.close();

  console.log(`\n── result ──`);
  notes.forEach((n) => console.log(`  note: ${n}`));
  if (failures.length) {
    console.error(`\nFAILED (${failures.length}):`);
    failures.forEach((f) => console.error(`  ✗ ${f}`));
    process.exit(1);
  }
  console.log(`\nALL CHECKS PASSED — screenshots in ${OUT}`);
}

main().catch((e) => { console.error(e); process.exit(2); });
