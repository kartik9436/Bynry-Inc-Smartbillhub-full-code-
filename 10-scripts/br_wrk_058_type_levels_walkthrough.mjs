// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-007, as amended by the PO ruling of 2026-09-07.  Screen: S8
//           → Reference data → Work order types (r10 SET-04)
// Rules:    BR-WRK-058 (two levels; a row with no parent IS a type) ·
//           BR-TEN-036 (a seeded row is deactivatable, never deletable) ·
//           B14 rule 31 (no database id is ever the visible value of a field) ·
//           CLAUDE.md hard-won law 6 (no gate reads rendered output — diff the
//           running app), law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * br_wrk_058_type_levels_walkthrough — the second hierarchical card, clicked.
 *
 * Nothing in this repository reads rendered output, and this card's whole
 * change is rendered: a Type / Sub-type chooser, a Parent column, a *"· N
 * sub-types"* suffix and four titles that follow the chooser. Every one of them
 * comes from `referenceDataConfig.ts`, so `tsc`, the unit tests and every gate
 * pass whether the words say "type" or "area" — which is exactly the failure
 * this file exists to catch.
 *
 *     # a real PostgreSQL with the migration applied and a tenant in it
 *     10-scripts/proof-db.sh build --from <a seeded template>
 *     eval "$(10-scripts/proof-db.sh clone wrk058 --export)"
 *     DATABASE_URL=$DATABASE_URL DJANGO_SETTINGS_MODULE=config.settings.local \
 *       ALLOWED_HOSTS='*' python3.12 manage.py runserver 127.0.0.1:8097
 *     cd 07-frontend && npx vite build
 *     PORT=4297 STATIC_DIR=$PWD/dist API_PROXY_TARGET=http://127.0.0.1:8097 \
 *       node server.mjs
 *     BASE=http://127.0.0.1:4297 node 10-scripts/br_wrk_058_type_levels_walkthrough.mjs
 *
 * ⚠ REBUILD THE BUNDLE FIRST and pass STATIC_DIR explicitly — `server.mjs`
 * resolves `dist/` from its OWN directory, so a lane in a `git worktree` that
 * runs the shared checkout's copy serves the shared checkout's bundle however
 * carefully it just built its own. Both traps are the portal walkthrough's,
 * learned there and repeated here rather than re-learned.
 *
 * It prints one line per check and exits non-zero on the first thing that is
 * wrong, so a red run names the screen rather than the assertion.
 */
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:4297";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const LIST = "work_order_types";

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const fail = (m) => { problems.push(m); console.log("  ✗ " + m); };
const note = (m) => console.log(m);

const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
});
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
const page = await ctx.newPage();
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(String(e)));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

/** The card, opened by its own address rather than by clicking through. */
async function openCard() {
  await page.goto(
    `${BASE}/${TENANT}/settings/reference-data?list=${LIST}`,
    { waitUntil: "domcontentloaded" },
  );
  await page.locator("table").first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(600);
}

/** Every rendered row: code, name cell (count suffix included) and parent. */
async function rows() {
  return page.evaluate(() => {
    const table = document.querySelector("table");
    if (!table) return [];
    const heads = [...table.querySelectorAll("thead th")].map((h) =>
      h.textContent.trim(),
    );
    return [...table.querySelectorAll("tbody tr")].map((tr) => {
      const cells = [...tr.querySelectorAll("td")].map((td) => td.textContent.trim());
      const row = {};
      heads.forEach((h, i) => (row[h] = cells[i] ?? ""));
      return row;
    });
  });
}

async function headings() {
  return page.evaluate(() =>
    [...document.querySelectorAll("table thead th")].map((h) => h.textContent.trim()),
  );
}

/** Delete one of THIS SCRIPT's own rows if a previous run left it behind.
 *
 * ⚠ **THE WALKTHROUGH HAS TO LEAVE THE TENANT AS IT FOUND IT**, or its second
 * run refuses every create on a duplicate code and reads exactly like a broken
 * screen. Children first: `parent` is PROTECT and the handler refuses a type
 * that still has sub-types under it, naming the count.
 */
async function removeIfPresent(code) {
  await openCard();
  const row = page.locator("tbody tr", { hasText: code }).first();
  if ((await row.count()) === 0) return false;
  const del = row.locator('button[aria-label="Delete"]').first();
  if ((await del.count()) === 0) return false; // 🔒 locked — used by something
  await del.click();
  await page.getByRole("button", { name: `Delete ${code}` }).first().click();
  await page.waitForTimeout(900);
  return true;
}

/** Open Add, choose a level, fill it in, save. */
async function addEntry({ level, code, name, parent }) {
  await page.getByRole("button", { name: "+ Add entry" }).first().click();
  await page.locator("#code").waitFor({ timeout: 15000 });
  if (level === "sub") {
    // The chooser is the kit's SegmentedField: a radiogroup whose <input>s are
    // visually hidden and driven by their labels — so CLICK THE LABEL, which is
    // also what a person does. Checking the input directly times out on
    // "element is not visible", correctly.
    await page.locator(".seg-opt", { hasText: "Sub-type" }).first().click();
    await page.waitForTimeout(300);
  }
  // ⚠ READ THE TITLE **AFTER** THE CHOOSER, NEVER BEFORE. The whole defect this
  // control closes is that the title did not follow the choice, so a title read
  // at OPEN says "Add a type" for both and the assertion below would be a test
  // named after something it does not check (hard-won law 7).
  const title = (await page.locator(".modal-title").first().textContent()) ?? "";
  await page.locator("#code").fill(code);
  await page.locator("#name").fill(name);
  if (parent !== undefined) {
    await page.locator("#parent_code").selectOption({ label: parent });
  }
  await page.locator(".modal-body ~ * button[type=submit], form button[type=submit]").last().click();
  await page.locator(".modal-title").waitFor({ state: "detached", timeout: 20000 });
  await page.waitForTimeout(800);
  return title.trim();
}

// ── 1 · the card draws the second level at all ─────────────────────────────
note("\nSettings → Reference data → Work order types");
await openCard();
const cols = await headings();
note(`  columns: ${cols.join(" · ")}`);
if (cols.some((c) => /parent type/i.test(c))) ok("the Parent type column is drawn");
else fail(`no "Parent type" column — got ${JSON.stringify(cols)}`);
if (cols.some((c) => /parent area/i.test(c)))
  fail('the column says "Parent area" — this card inherited areas\' words');

const seeded = await rows();
note(`  ${seeded.length} row(s) on page 1`);
const complaint = seeded.find((r) => /Consumer Complaint/.test(Object.values(r).join(" ")));
if (complaint) ok(`a seeded type is drawn — ${JSON.stringify(complaint).slice(0, 120)}`);
else fail("no seeded type on the first page");

// ── 2 · create a TYPE ──────────────────────────────────────────────────────
// A previous run's rows first, sub-type before type (PROTECT).
for (const code of ["WALK_SUB", "WALK_TYPE"]) {
  if (await removeIfPresent(code)) note(`  cleared a leftover ${code} from an earlier run`);
}
note("\ncreating a top-level TYPE");
const addTitle = await addEntry({
  level: "top",
  code: "WALK_TYPE",
  name: "Walkthrough type",
});
note(`  dialog title read: "${addTitle}"`);
if (/type/i.test(addTitle) && !/area/i.test(addTitle)) ok("the dialog title names a TYPE");
else fail(`the dialog title is wrong for this card: "${addTitle}"`);

await openCard();
let after = await rows();
let mine = after.find((r) => Object.values(r).includes("WALK_TYPE"));
if (mine) ok(`the type is listed — parent cell "${mine["Parent type"] ?? "?"}"`);
else fail("the new type is not in the table");
if (mine && (mine["Parent type"] ?? "").trim() === "—") ok("its parent cell is an em dash");
else if (mine) fail(`its parent cell reads "${mine["Parent type"]}" and should be "—"`);

// ── 3 · create a SUB-TYPE under it ─────────────────────────────────────────
note("\ncreating a SUB-TYPE under it");
const subTitle = await addEntry({
  level: "sub",
  code: "WALK_SUB",
  name: "Walkthrough sub-type",
  parent: "Walkthrough type",
});
note(`  dialog title read: "${subTitle}"`);
if (/sub-type/i.test(subTitle)) ok("the dialog title followed the chooser to SUB-TYPE");
else fail(`the title did not follow the chooser: "${subTitle}"`);

await openCard();
after = await rows();
const sub = after.find((r) => Object.values(r).includes("WALK_SUB"));
if (sub) ok(`the sub-type is listed — parent "${sub["Parent type"] ?? "?"}"`);
else fail("the new sub-type is not in the table");
if (sub && /Walkthrough type/.test(sub["Parent type"] ?? ""))
  ok("its Parent type column names the type it sits under");
else if (sub) fail(`its Parent type reads "${sub["Parent type"]}"`);

// ── 4 · the count suffix, on the NAME of the parent ────────────────────────
const parentRow = after.find((r) => Object.values(r).includes("WALK_TYPE"));
const parentName = parentRow ? Object.values(parentRow).find((v) => /Walkthrough type/.test(v)) : "";
note(`  the parent's name cell now reads: "${parentName}"`);
if (/1 sub-type\b/.test(parentName ?? "")) ok('it carries "· 1 sub-type"');
else if (/sub-area/.test(parentName ?? "")) fail('it says "sub-area" — areas\' word on a work order type');
else fail(`no sub-type count on the parent's name: "${parentName}"`);

// The count is the SERVER's, so a seeded parent must show its own.
const readingRow = after.find((r) => /(^|\W)Reading(\W|$)/.test(Object.values(r).join(" ")));
if (readingRow) {
  const readingName = Object.values(readingRow).find((v) => /Reading/.test(v));
  note(`  the seeded "Reading" type reads: "${readingName}"`);
  if (/1 sub-type\b/.test(readingName ?? "")) ok("Reading shows its one seeded sub-type (Re-read)");
  else fail(`Reading's count is wrong: "${readingName}"`);
}

// ── 5 · EDIT each, and the chooser opens on what the row IS ────────────────
note("\nediting each of the two");
async function openEdit(code) {
  await openCard();
  const row = page.locator("tbody tr", { hasText: code }).first();
  await row.locator('button[aria-label="Edit"]').first().click();
  await page.locator("#code").waitFor({ timeout: 15000 });
  return (await page.locator(".modal-title").first().textContent()) ?? "";
}
const editTypeTitle = (await openEdit("WALK_TYPE")).trim();
note(`  editing the type — title "${editTypeTitle}"`);
if (/edit/i.test(editTypeTitle) && /type/i.test(editTypeTitle) && !/sub-type/i.test(editTypeTitle))
  ok("the edit dialog opens as a TYPE");
else fail(`the edit title is wrong: "${editTypeTitle}"`);
await page.locator("#name").fill("Walkthrough type (edited)");
await page.locator("form button[type=submit]").last().click();
await page.locator(".modal-title").waitFor({ state: "detached", timeout: 20000 });

const editSubTitle = (await openEdit("WALK_SUB")).trim();
note(`  editing the sub-type — title "${editSubTitle}"`);
if (/sub-type/i.test(editSubTitle)) ok("the edit dialog opens as a SUB-TYPE");
else fail(`the edit title is wrong: "${editSubTitle}"`);
await page.locator("#name").fill("Walkthrough sub-type (edited)");
await page.locator("form button[type=submit]").last().click();
await page.locator(".modal-title").waitFor({ state: "detached", timeout: 20000 });

await openCard();
after = await rows();
const editedSub = after.find((r) => Object.values(r).includes("WALK_SUB"));
if (editedSub && /Walkthrough type \(edited\)/.test(editedSub["Parent type"] ?? ""))
  ok("the sub-type's Parent column followed the parent's rename");
else fail(`the parent column did not follow the rename: "${editedSub?.["Parent type"]}"`);

// ── 6 · THE CHOOSER BY KEYBOARD ALONE, WITH NO MOUSE AT ALL ────────────────
// `SegmentedField` hides its radio inputs (opacity 0, width 0, pointer-events
// none) and styles the label around them, so "it is a radiogroup" is a claim
// about markup rather than about what a person can do. Everything above this
// point clicks; a card that had become mouse-only would pass every one of
// those checks. This section touches nothing but the keyboard.
note("\noperating the chooser by keyboard only");
await openCard();
await page.getByRole("button", { name: "+ Add entry" }).first().click();
await page.locator("#code").waitFor({ timeout: 15000 });
const titleBefore = ((await page.locator(".modal-title").first().textContent()) ?? "").trim();
// Focus the group the way a person arrives at it: from the top of the dialog.
await page.locator(".modal-title").first().focus().catch(() => {});
await page.keyboard.press("Tab");
await page.keyboard.press("Tab");
const landedOn = await page.evaluate(() => {
  const el = document.activeElement;
  return el === null ? "" : `${el.tagName.toLowerCase()}[name=${el.getAttribute("name") ?? "-"}]`;
});
note(`  after two Tabs, focus is on ${landedOn}`);
await page.keyboard.press("ArrowRight");
await page.waitForTimeout(300);
const titleAfter = ((await page.locator(".modal-title").first().textContent()) ?? "").trim();
const pickerVisible = await page.locator("#parent_code").isVisible().catch(() => false);
const focusRing = await page.evaluate(
  () => document.querySelectorAll(".seg-opt:has(input:focus-visible)").length,
);
note(`  title "${titleBefore}" → "${titleAfter}"; parent picker visible: ${pickerVisible}`);
// The assertion is INHERENTLY capable of failing: with no keyboard effect the
// title is unchanged and the picker never appears, which is what a mouse-only
// control looks like from here.
if (titleAfter !== titleBefore && /sub-type/i.test(titleAfter))
  ok("ArrowRight moved the chooser and the title followed — no mouse used");
else fail(`the keyboard did not move the chooser: "${titleBefore}" → "${titleAfter}"`);
if (pickerVisible) ok("the Parent type picker appeared under the sub level");
else fail("choosing Sub-type by keyboard drew no parent picker");
if (focusRing === 1) ok("the visible segment carries the focus ring");
else fail(`focus-visible ring on ${focusRing} segment(s), expected exactly 1`);
await page.keyboard.press("Escape");
await page.waitForTimeout(400);

// ── 7 · B14 rule 31 — no uuid anywhere a person can read ───────────────────
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const bodyText = await page.evaluate(() => document.body.innerText);
if (UUID.test(bodyText)) fail("a database id is visible on the card (B14 rule 31)");
else ok("no database id is drawn anywhere on the card");

// ── 8 · put the tenant back exactly as it was found ────────────────────────
note("\ntidying up");
for (const code of ["WALK_SUB", "WALK_TYPE"]) {
  if (await removeIfPresent(code)) ok(`${code} deleted`);
  else fail(`${code} could not be deleted — it is still on the card`);
}

if (jsErrors.length) jsErrors.forEach((e) => fail("JS error: " + e));
else ok("no JavaScript errors");

note(`\n${problems.length === 0 ? "ALL CHECKS PASSED" : problems.length + " PROBLEM(S)"}`);
await browser.close();
process.exit(problems.length === 0 ? 0 : 1);
