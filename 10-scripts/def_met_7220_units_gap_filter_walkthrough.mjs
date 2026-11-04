// ── THE *Missing services* FILTER, ON A SEEDED TENANT, IN A BROWSER ─────────
//
// PO ruling 2026-09-28, verbatim: *"the Units "Missing services" block —
// filter or leave it. - filter"*. The separate block is deleted; the filter,
// its count and two columns take its place on the units list (`PRM-01U`).
//
// ⛔ **NO GATE IN THIS REPOSITORY READS RENDERED OUTPUT (hard-won law 6), SO
// THIS FILE IS THE ONLY CHECK THAT CAN ANSWER THE PO'S ACTUAL QUESTION.** The
// jsdom cases (`UnitsMissingServicesFilter.dom.test.tsx`) prove the screen ASKS
// the right things; only a browser proves a clerk SEES the count without
// switching anything on, at the width they are actually working at.
//
// ⚠ **THE FOUR THINGS THE PO WAS SHOWN AS THE REASON FOR THE CHANGE ARE THE
// FOUR THINGS WALKED HERE**, in this order, because those are what *done*
// means: the count with the filter OFF · the filter ON · the filter AND the
// search · the SELECTION and the bulk bar over the filtered set.
//
// ⚠ **AND THE BLOCK'S ABSENCE IS ASSERTED BY NAME.** A walk that only checks
// the new control would pass with the old panel still above it — which is the
// state the PO explicitly ruled against ("filter", not "filter as well").
//
// ⚠ **IT REFUSES A STALE BUILD**, the same guard every walkthrough here
// carries: a walk against an old bundle reports landed work as absent.
//
// ⚠ **IT WRITES NOTHING.** It only reads and ticks controls, so there is
// nothing to leave behind; the plan-assignment dialog is never committed.
//
//   MET7220_BASE     default http://127.0.0.1:8972
//   MET7220_TENANT   default brazosbend
//   MET7220_EMAIL    default dana@brazosbendutilities.com
//   MET7220_PASSWORD default S3cure!passw0rd
//   MET7220_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//   MET7220_SHOTS    where the shots land
//   MET7220_SEARCH   a street that some short unit is on
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { statSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.MET7220_ROOT || process.cwd();
const BASE = process.env.MET7220_BASE || "http://127.0.0.1:8972";
const T = process.env.MET7220_TENANT || "brazosbend";
const EMAIL = process.env.MET7220_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MET7220_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MET7220_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.MET7220_SHOTS || ".";
const SEARCH = process.env.MET7220_SEARCH || "Main";

function newestMtime(dir) {
  let newest = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const path = join(dir, entry.name);
    const at = entry.isDirectory() ? newestMtime(path) : statSync(path).mtimeMs;
    if (at > newest) newest = at;
  }
  return newest;
}
const built = statSync(join(ROOT, "07-frontend/dist/index.html")).mtimeMs;
const newestFile = newestMtime(join(ROOT, "07-frontend/src"));
if (built < newestFile) {
  console.error(
    `REFUSED: dist/ was built ${new Date(built).toISOString()} but 07-frontend/src\n` +
      `has work at ${new Date(newestFile).toISOString()}. Run \`npx vite build\` first.`,
  );
  process.exit(2);
}
console.log(`dist built ${new Date(built).toISOString()} >= src ${new Date(newestFile).toISOString()}`);

const R = [];
const ok = (n, c, d = "") => {
  R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
  console.log(R.at(-1));
};

const b = await chromium.launch({ executablePath: CHROME });

/** The toolbar's own toggle, by its accessible name and its pressed state —
 *  never the applied chip's ✕, which carries the same words. */
const CHIP = 'button[aria-pressed][data-chip]';

/** ⚠ **THE TABLE'S OWN SEARCH BOX, NAMED BY ITS PROMPT.** `input[type="search"]`
 *  also matches the app shell's global search, which is a different control on
 *  the same page — filling THAT typed into nothing and left the list unchanged
 *  while every other assertion still passed. B14 rule 19 gives this list its
 *  own sentence, so the sentence is what selects it. */
const SEARCH_BOX = 'input[type="search"][aria-label^="Search unit"]';

async function chipNamed(p) {
  const all = await p.locator(CHIP).all();
  for (const one of all) {
    const text = (await one.textContent()) ?? "";
    if (text.includes("Missing services")) return one;
  }
  return null;
}

async function rowCount(p) {
  return await p.locator("table tbody tr").count();
}

async function walk(width) {
  const p = await b.newPage({ viewport: { width, height: 1100 } });
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);

  // ── 1 · THE COUNT, WITH THE FILTER OFF ────────────────────────────────
  await p.goto(`${BASE}/${T}/premises/units`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: join(SHOTS, `units-gap-${width}-1-filter-off.png`), fullPage: false });

  // The deleted block, asserted ABSENT by its own heading's disclosure.
  const blockRows = await p.locator('details summary:has-text("Missing services")').count();
  ok(`${width}px · the separate block is GONE`, blockRows === 0, `disclosures=${blockRows}`);

  const chip = await chipNamed(p);
  ok(`${width}px · the count is on the toolbar with the filter OFF`, chip !== null);
  const offText = chip === null ? "" : ((await chip.textContent()) ?? "").trim();
  const pressedOff = chip === null ? null : await chip.getAttribute("aria-pressed");
  ok(`${width}px · …and it is not engaged`, pressedOff === "false", `"${offText}"`);
  ok(`${width}px · …and it states a number`, /\d/.test(offText), `"${offText}"`);
  const totalOff = (await p.locator("table tbody tr").count());

  // ── 2 · THE FILTER ON ─────────────────────────────────────────────────
  await chip.click();
  await p.waitForTimeout(2500);
  await p.screenshot({ path: join(SHOTS, `units-gap-${width}-2-filter-on.png`) });
  const onChip = await chipNamed(p);
  ok(`${width}px · pressing it engages the filter`,
     (await onChip.getAttribute("aria-pressed")) === "true");
  ok(`${width}px · the address carries it`, p.url().includes("f.missing_services=yes"), p.url());
  const totalOn = await rowCount(p);
  ok(`${width}px · the list NARROWS`, totalOn > 0 && totalOn < totalOff,
     `${totalOn} rows of ${totalOff}`);
  // The applied-filter chip, which is what B14 rule 12 asks for.
  const applied = await p.locator('text=/Missing services: /').count();
  ok(`${width}px · it leaves a removable chip`, applied > 0, `chips=${applied}`);
  // The new column, on the row.
  const missingHead = await p.locator('th:has-text("Missing")').count();
  ok(`${width}px · the Missing column is drawn`, missingHead > 0, `headers=${missingHead}`);

  // ── 3 · THE FILTER AND THE SEARCH ─────────────────────────────────────
  await p.fill(SEARCH_BOX, SEARCH);
  await p.waitForTimeout(2800);
  await p.screenshot({ path: join(SHOTS, `units-gap-${width}-3-filter-and-search.png`) });
  const bothUrl = p.url();
  ok(`${width}px · the filter AND the search ride one address`,
     bothUrl.includes("f.missing_services=yes") && /q=\w/.test(bothUrl), bothUrl);
  const searched = await rowCount(p);
  // ⚠ **A ZERO HERE WOULD PASS AND WOULD PROVE NOTHING**, and it is also a
  // useless picture for the person who asked for this. The default `MET7220_SEARCH`
  // is a street the seeded utility has short units on, so the shot shows a
  // NARROWED list rather than an empty state.
  ok(`${width}px · and the list narrows again, to something`,
     searched > 0 && searched < totalOn, `${searched} rows of ${totalOn}`);

  // ── 4 · THE SELECTION AND THE BULK BAR ────────────────────────────────
  // ⚠ **THE PO'S STRONGEST REASON.** The gap is a thing to FIX, and the block
  // was the one place in the product where these units could not be selected.
  await p.fill(SEARCH_BOX, "");
  await p.waitForTimeout(2800);
  const boxes = p.locator('table tbody input[type="checkbox"]');
  const n = await boxes.count();
  ok(`${width}px · the filtered rows carry a checkbox`, n > 0, `boxes=${n}`);
  await boxes.first().check();
  await boxes.nth(1).check();
  await p.waitForTimeout(600);
  const assign = p.locator('button:has-text("Assign plan")').first();
  const enabled = await assign.isEnabled();
  ok(`${width}px · the bulk bar reaches the filtered set`, enabled);
  await p.screenshot({ path: join(SHOTS, `units-gap-${width}-4-bulk-bar.png`) });

  // ⚠ `Select all {n}` must state the SERVER's total for the FILTERED set, not
  // the page — a clerk told they selected 13,339 and given fifty is DEF-TEN-5840.
  const selectAll = (await p.locator('button:has-text("Select all")').first().textContent()) ?? "";
  ok(`${width}px · Select all states the filtered total`, /\d/.test(selectAll), selectAll.trim());

  // Nothing is committed: the page is left as it was found.
  await p.close();
}

await walk(1440);
await walk(1280);
await b.close();
console.log("\n" + R.join("\n"));
process.exit(R.some((line) => line.startsWith("FAIL")) ? 1 : 0);
