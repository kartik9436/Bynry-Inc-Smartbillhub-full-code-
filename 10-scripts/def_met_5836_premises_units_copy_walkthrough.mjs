// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-5835 — the premises list opened with a 27-word explainer
//          that was RATIONALE end to end, over a blueprint whose stated
//          absence for that screen is "No prose on the screen at all".
//          DEF-MET-5836 — 218 of the 744 premises/units catalogue strings
//          breached B14 rule 33's five caps, 2,551 words in all.
// Rules:   B14 rule 33 (on-screen text is capped by what it is FOR: a LABEL
//          <= 3 words · a FACT <= 6 · an INSTRUCTION <= 6 PER SENTENCE, and
//          two sentences of six beat one sentence of twelve · a CONSEQUENCE
//          <= 6 per sentence, at most two, NEVER CUT BELOW CLARITY ·
//          RATIONALE = ZERO words on screen) · rule 32 (a screen has a
//          description budget) · rule 35 (a catalogue is written in its own
//          language) · CLAUDE.md hard-won law 6 — NO GATE IN THIS REPO READS
//          RENDERED OUTPUT, so this is the only instrument that can see any
//          of it.
// ───────────────────────────────────────────────────────
/**
 * Walk the premises and units screens and COUNT THE WORDS A CLERK SEES.
 *
 *     BASE=http://127.0.0.1:8137 TAG=after \
 *       CHROME_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
 *       node 10-scripts/def_met_5836_premises_units_copy_walkthrough.mjs
 *
 * ⚠ **A WORD COUNT TAKEN FROM THE CATALOGUE IS NOT A WORD COUNT OF THE
 * SCREEN, WHICH IS THE WHOLE REASON THIS EXISTS.** `G129` measures `en.json`
 * and is honest about its blind spot; it cannot see a string typed into a
 * component by hand, a key the screen draws from another namespace, or a
 * shortened key that nothing renders. A copy change is exactly the kind that
 * looks done in the diff and is absent on screen.
 *
 * Measured on 2026-09-19 across 17 screens in their default state:
 * **4,448 words before, 4,309 after.** The premises list alone went 1,113 ->
 * 1,066, and the 27-word explainer is gone from the rendered markup.
 *
 * ⚠ **THE TOTAL IS NOISY RUN TO RUN AND THE PER-SCREEN NUMBERS ARE NOT.**
 * Three full 17-screen runs of this script gave 4,299, 3,991 and 4,299: a tab
 * can open before its content has arrived, so its words are counted late. The
 * figure to quote is a SINGLE SCREEN measured the same way twice — the
 * premises list reads 1,113 before and 1,063 after on every run — and the
 * total is an order-of-magnitude check rather than a measurement. Raising the
 * waits would narrow it; saying so is better than a number that looks firmer
 * than it is.
 *
 * ⚠ **THE SCREEN NUMBER IS MUCH SMALLER THAN THE CATALOGUE NUMBER AND THAT IS
 * NOT A DISCREPANCY.** Most of what this sweep shortened — empty states,
 * refusals, wizard help behind later steps, modal consequences — does not
 * render in a screen's DEFAULT state, so a default-state walk cannot see it.
 * Quote both numbers or neither.
 *
 * ⚠ **THE STALENESS GUARD IS THE FIRST THING IT DOES, AND IT IS THE
 * DEV-SERVER FORM OF THE ONE `plan_wizard_seven_walkthrough.mjs` CARRIES.**
 * That one refuses a `dist/` older than `src/`. This one runs against a vite
 * DEV server, where the hazard is different and worse: six lanes each run
 * their own vite on their own port, so the risk is not a stale bundle but
 * THE WRONG WORKTREE — a walk that reports another lane's copy as though it
 * were ours. So it fetches `en.json` THROUGH the server and compares one key
 * against the same file on disk, and refuses if they differ.
 *
 * TO RUN ONE: `07-frontend/vite.walk.config.ts` is not in the repo (every lane
 * needs its own port). Copy `vite.config.ts`, add
 * `server: { port: <yours>, strictPort: true, proxy: { "/api": { target:
 * "http://127.0.0.1:8600", changeOrigin: true } } }`, and start it from
 * `07-frontend`.
 *
 * Credentials and the login-restore procedure are in
 * `def_rat_5731_plan_tables_walkthrough.mjs`'s header. CHECK THE CREDENTIAL
 * RATHER THAN THE PARAGRAPH — a stale blocker stops the one check that finds
 * what no test can.
 */
import { createRequire } from "node:module";
import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8137";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const TAG = process.env.TAG ?? "before";
const SHOTS = `/tmp/claude-0/-home-user-SMARTBillHub/da7d6dea-a84b-56ee-b035-57684ffe93fb/scratchpad/copysweep/shots-${TAG}`;
mkdirSync(SHOTS, { recursive: true });

// ── staleness guard, the dev-server form ────────────────────────────────────
// The other lanes run their own vite on other ports. If this script talked to
// one of THEIRS it would report another worktree's copy as though it were ours.
// So: ask the server for the catalogue and compare it with the file on disk.
const mine = readFileSync("07-frontend/src/i18n/locales/en.json", "utf8");
const served = await (await fetch(`${BASE}/src/i18n/locales/en.json`)).text();
const pick = (s) => { try { return JSON.parse(s)["metering.premises.explainer.premises"]; } catch { return null; } };
if (pick(served) !== pick(mine)) {
  console.error(`REFUSED: ${BASE} is not serving this worktree.\n  served: ${pick(served)}\n  ondisk: ${pick(mine)}`);
  process.exit(2);
}
console.log(`staleness guard OK — ${BASE} serves this worktree`);

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome" });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 1100 } });
const page = await ctx.newPage();
const errs = [];
page.on("pageerror", (e) => errs.push(e.message));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  page.click('button[type="submit"]'),
]);
console.log("signed in →", page.url());

const wordsOf = (s) => (s.replace(/\s+/g, " ").trim().match(/[0-9A-Za-zÀ-￿][^\s]*/g) ?? []).length;

const report = [];
async function grab(name, path, prep) {
  await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2200);
  if (prep) { try { await prep(); } catch (e) { console.log(`  prep failed on ${name}: ${e.message}`); } }
  await page.waitForTimeout(900);
  // MAIN only: the left nav and the app frame are not this sweep's copy.
  const main = page.locator("main").first();
  const text = (await main.count()) ? await main.innerText() : await page.locator("body").innerText();
  const n = wordsOf(text);
  await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
  writeFileSync(`${SHOTS}/${name}.txt`, text);
  report.push({ name, path, words: n });
  console.log(`  ${name.padEnd(28)} ${String(n).padStart(5)} words  ${path}`);
  return text;
}

console.log(`\n── rendered word counts (${TAG}) ──`);
await grab("premises-list", `/${TENANT}/premises`);
await grab("units-list", `/${TENANT}/premises/units`);
await grab("premises-imports", `/${TENANT}/premises/imports`);

// first premises row → detail, then each tab (tabs are CLICKED, not ?tab=)
await page.goto(`${BASE}/${TENANT}/premises`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
const firstLink = page.locator('main a[href*="/premises/"]').first();
let premPath = null;
if (await firstLink.count()) {
  const href = await firstLink.getAttribute("href");
  if (href && !href.includes("/units") && !href.includes("/import") && !href.endsWith("/new")) premPath = href;
}
console.log("premises detail href:", premPath);

async function tabWalk(prefix, path, names) {
  for (const name of names) {
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1800);
    const tab = page.getByRole("tab", { name }).or(page.getByRole("button", { name })).first();
    let reached = true;
    if (await tab.count()) { await tab.click().catch(() => { reached = false; }); }
    else reached = false;
    await page.waitForTimeout(1600);
    const slug = `${prefix}-${String(name).toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    const main = page.locator("main").first();
    const text = (await main.count()) ? await main.innerText() : await page.locator("body").innerText();
    await page.screenshot({ path: `${SHOTS}/${slug}.png`, fullPage: true });
    writeFileSync(`${SHOTS}/${slug}.txt`, text);
    const n = wordsOf(text);
    report.push({ name: slug, path, words: n, reached });
    console.log(`  ${slug.padEnd(34)} ${String(n).padStart(5)} words${reached ? "" : "   (TAB NOT REACHED)"}`);
  }
}

if (premPath) {
  await tabWalk("premises-detail", premPath,
    ["Overview", "Units", "Common areas", "Assets", "Work orders", "Audit log"]);
}

// units list → first unit detail
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
const unitLink = page.locator('main a[href*="/premises/units/"]').first();
if (await unitLink.count()) {
  const href = await unitLink.getAttribute("href");
  if (href && !href.endsWith("/new") && !href.endsWith("/import")) {
    await tabWalk("unit-detail", href,
      ["Overview", "Account", "Plan", "Assets", "Occupancy", "Audit log"]);
  }
}

// the two wizards — a clerk meets these from the list's primary action
await grab("add-premises-wizard", `/${TENANT}/premises/new`);
await grab("add-units-wizard", `/${TENANT}/premises/units/new`);

// ── THE SCREEN-COUNT GUARD ────────────────────────────────────────────────
// ⚠ **THE FIRST RUN OF THIS SCRIPT AFTER THE SWEEP REPORTED ELEVEN SCREENS
// AND SAID NOTHING ABOUT THE SIX IT MISSED.** The unit-detail link had not
// rendered yet, so `unitLink.count()` was 0, the whole block was skipped, and
// the total came out 3,189 — a smaller, better-looking number over a smaller
// scope. That is hard-won law 7's *reporting zero over a scope it silently
// excludes*: the script was not lying, and a reader had no way to tell a walk
// of 17 screens from a walk of 11.
//
// So the expected count is DECLARED, and falling short is a loud failure
// rather than a quieter total.
const EXPECTED_SCREENS = 17;
const total = report.reduce((a, r) => a + r.words, 0);
console.log(`\nTOTAL rendered words across ${report.length} screens: ${total}`);
if (report.length < EXPECTED_SCREENS) {
  console.log(
    `\n✗ REACHED ONLY ${report.length} OF ${EXPECTED_SCREENS} SCREENS — the total above is ` +
      `over a SMALLER SCOPE and is not comparable with a full run. Re-run; if it ` +
      `persists, a door this walk depends on is broken and that is the finding.`,
  );
  errs.push(`reached ${report.length}/${EXPECTED_SCREENS} screens`);
}
const unreached = report.filter((r) => r.reached === false);
if (unreached.length) {
  console.log(`✗ ${unreached.length} tab(s) did not open: ${unreached.map((r) => r.name).join(", ")}`);
}
writeFileSync(`${SHOTS}/report.json`, JSON.stringify({ tag: TAG, total, report, errs }, null, 2));
if (errs.length) { console.log("\nPAGE ERRORS:"); errs.forEach((e) => console.log("  ✗", e)); }
await browser.close();
