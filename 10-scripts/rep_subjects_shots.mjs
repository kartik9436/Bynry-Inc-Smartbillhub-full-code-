// ── Trace ──────────────────────────────────────────────
// Change:  **BR-REP-043** (`P2.15`, the UNIT statement) and **BR-REP-044**
//          (`P5.5`, the Delivery settings card), both PO rulings 2026-09-27.
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app — no gate looks at
//          rendered output"*) · law 2's mirror (a live screen behind a dead
//          control) · hard rule 8 (a unit declares no address) · B14 rule 44
//          (a staff screen is built at 1440).
// ───────────────────────────────────────────────────────
//
// PHOTOGRAPH WHAT IS THERE. No CSS is injected, no element is hidden, no value
// is substituted. Where a state cannot be reached the script SAYS SO in
// `00-README.txt` rather than skipping it — an absence with no reason beside it
// is indistinguishable from a pass (hard-won law 7's fifth shape).
//
//   node 10-scripts/rep_subjects_shots.mjs
//
// Env: SMOKE_BASE · SMOKE_TENANT · SMOKE_EMAIL · SMOKE_PASSWORD · SHOT_OUT ·
//      REP_UNIT (the unit id in the URL; without it the script says so)
//
// ⚠ **WHAT A SCREENSHOT MUST SHOW HERE, AND WHY EACH IS COUNTED IN TEXT TOO.**
// A reader cannot count a column from a PNG, so beside every shot the script
// prints what it measured out of the DOM:
//   * the unit statement's HEAD — the PREMISES address and the unit LABEL,
//     because hard rule 8 says the unit has no address of its own and a shot
//     of a head with a unit address on it is a shot of the defect;
//   * the OCCUPANT column's presence, and how many rows carry a name — the
//     column is this subject's whole point;
//   * that no heading contains a DOT, which is what a fallen-back i18n key
//     looks like and what no English word does (`DEF-REP-6900`);
//   * that no money cell shows more than two decimals (hard rule 2 DISPLAYS 2;
//     the wire carries `84.200000` and a cell printing that is the bug that
//     has shipped three times).

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "scratchpad/po-shots/statement-subjects";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const UNIT = process.env.REP_UNIT ?? "";

const notes = [];
function note(line) {
  console.log(line);
  notes.push(line);
}

async function shot(page, name, width = 1440) {
  await page.setViewportSize({ width, height: 1100 });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await (await browser.newContext()).newPage();

  note(`base ${BASE} · tenant ${TENANT}`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ SEVEN SECONDS, MEASURED. At 3s the app was still on /signin and every
  // assertion after it read an unauthenticated page — which LOOKED like the
  // Delivery card being absent. A wait too short is a check that fails for a
  // reason that has nothing to do with what it is testing.
  await page.waitForTimeout(7000);
  if (/\/signin/.test(page.url())) {
    throw new Error(`still on the sign-in screen at ${page.url()} — every shot below would photograph a logged-out app`);
  }
  note(`signed in → ${page.url()}`);

  // ── BR-REP-044 · the Delivery card, and that it is a LINK ───────────────
  await page.goto(`${BASE}/${TENANT}/settings/reference-data`, { waitUntil: "networkidle" });
  // ⚠ **WAIT FOR THE GRID, NEVER FOR A CLOCK.** At a fixed 1200ms this step
  // reported *"Delivery card present: false"* on one run and true on the next,
  // over a card that had shipped either way — a flake that reads exactly like
  // a real absence. Waiting for the thing itself is the only version of this
  // check that can be believed.
  await page
    .waitForFunction(() => /Delivery/.test(document.body.innerText), { timeout: 20000 })
    .catch(() => note("  WARNING: the Delivery card did not appear within 20s"));
  await shot(page, "delivery-card-grid");
  const cardText = await page.evaluate(() => document.body.innerText);
  note(`  Delivery card present: ${/Delivery/.test(cardText)}`);

  // ⚠ **CLICKED, NOT ASSUMED.** A card that renders and navigates nowhere is
  // exactly law 2's mirror — the failure this repo files more than any other.
  const before = page.url();
  const clicked = await page.evaluate(() => {
    const tiles = [...document.querySelectorAll("button, [role=button], .lookup-card, article")];
    const hit = tiles.find((el) => /Delivery/.test(el.textContent ?? ""));
    if (!hit) return false;
    hit.click();
    return true;
  });
  await page.waitForTimeout(2500);
  note(`  Delivery clicked: ${clicked} · ${before} → ${page.url()}`);
  note(`  lands on 4·1 Scheduled: ${/\/reports\/scheduled/.test(page.url())}`);
  await shot(page, "delivery-lands-on-scheduled");

  // ── BR-REP-043 · the UNIT statement ─────────────────────────────────────
  if (!UNIT) {
    note("  SKIPPED the unit statement: no REP_UNIT given, so the URL would name");
    note("  no subject and the report would correctly refuse. That is an ABSENCE");
    note("  WITH A REASON, not a pass (hard-won law 7's fifth shape).");
  } else {
    const url =
      `${BASE}/${TENANT}/reports/statement` +
      `?subject=unit&subject_id=${UNIT}&f.from=2026-07-01&f.to=2026-09-30`;
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await shot(page, "unit-statement");
    await shot(page, "unit-statement", 1280);

    const measured = await page.evaluate(() => {
      const headings = [...document.querySelectorAll("th")].map((th) => th.innerText.trim());
      const rows = [...document.querySelectorAll("tbody tr")].map((tr) =>
        [...tr.querySelectorAll("td")].map((td) => td.innerText.trim()),
      );
      return { headings, rows, body: document.body.innerText };
    });
    note(`  columns on screen: ${measured.headings.join(" | ")}`);
    note(`  rows: ${measured.rows.length}`);
    // ⚠ CASE-INSENSITIVE. The kit upper-cases table headings in CSS, so the
    // DOM reads `OCCUPANT`. The first version of this line compared against
    // `"Occupant"` and reported FALSE over a column that was plainly on the
    // screen — a check failing for a reason that has nothing to do with the
    // thing it tests, which is worse than no check because it is believed.
    const upper = measured.headings.map((h) => h.toUpperCase());
    note(`  Occupant column present: ${upper.includes("OCCUPANT")}`);
    note(`  Account column present: ${upper.includes("ACCOUNT")}`);
    // ⚠ **THE HEAD — hard rule 8.** The unit declares no address; the head
    // must read the PREMISES' address plus the unit's LABEL.
    note(`  head names the premises address: ${/163 Willow Bend Dr/.test(measured.body)}`);

    // ⚠ A DOT IN A HEADING IS A FALLEN-BACK i18n KEY. No English word has one.
    const dotted = measured.headings.filter((h) => h.includes("."));
    note(`  headings containing a dot (must be none): ${JSON.stringify(dotted)}`);

    // ⚠ MONEY DISPLAYS AT TWO DECIMALS (hard rule 2). The wire carries six.
    const overPrecise = [];
    for (const row of measured.rows) {
      for (const cell of row) {
        const m = cell.match(/\d+\.(\d+)/);
        if (m && m[1].length > 2) overPrecise.push(cell);
      }
    }
    note(`  cells showing more than 2 decimals (must be none): ${JSON.stringify(overPrecise.slice(0, 5))}`);
  }

  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
  await browser.close();
}

main().catch((error) => {
  notes.push(`FAILED: ${error.message}`);
  try {
    mkdirSync(OUT, { recursive: true });
    writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
  } catch {}
  console.error(error);
  process.exit(1);
});
