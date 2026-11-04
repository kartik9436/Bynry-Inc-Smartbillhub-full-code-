// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-7640 — the Product Owner, deployed `v2.388.0`: `+ Build
//          your own` on Reports → Catalogue does nothing. It navigated to
//          `/reports/custom`, which since `P5.10` mounts the SAME catalogue on
//          its Custom sub-tab.
// Change:  PO ruling 2026-09-28, verbatim: *"Opens the editor on a blank
//          definition, then Save as"*.
// Rules:   `12-governance/22-product-maintenance-process.md` §0 (REPRODUCE it
//          before you read a line of code) and §4 (prove it against the
//          reproduction, in a browser) · CLAUDE.md hard-won law 6 (no gate in
//          this repo reads rendered output) · law 7 clause 3 (a check's output
//          must distinguish pass from fail to a READER).
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS SCRIPT IS THE REPRODUCTION AND THE PROOF, AND IT IS ONE FILE ON
// PURPOSE.** The maintenance process asks for the same state to be driven
// twice — once to see the defect and once to see it gone — and two scripts
// drift. Run it against the BROKEN build and step 1 fails naming the address
// the button landed on; run it against the fixed one and every step passes.
//
// ⚠ **EVERY STEP PRINTS WHAT IT COMPARED.** `PASS` with no value beside it is
// a line a reader cannot check, which is law 7's third habit.
//
//   1 · the button is drawn, and pressing it LEAVES the catalogue
//   2 · it leaves it for the EDITOR, at the address the router registers
//   3 · pressing it from `/reports/custom` — where the old target WAS the
//       page you are standing on — also opens the editor
//   4 · the editor opens BLANK: no subject, no columns, no filters
//   5 · the preview says it has nothing to show, in words, and shows no figure
//   6 · `Save as` on the blank draft is REFUSED, and the refusal names what is
//       missing
//   7 · choose a subject, tick a column, `Save as` with a name — the server
//       creates the report
//   8 · it is under **Custom** afterwards
//
// USAGE
//   BASE=http://127.0.0.1:8738 node 10-scripts/def_rep_7640_build_your_own_walkthrough.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/def-rep-7640";
const NAME = process.env.REPORT_NAME ?? `Blank build ${Date.now()}`;
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH or install to /opt/pw-browsers");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
let failures = 0;
const say = (...parts) => console.log(...parts);
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL} at ${BASE}`);

const buildButton = 'button:has-text("Build your own")';

/** Press the action and report where the browser ended up. */
async function pressFrom(path) {
  await page.goto(`${BASE}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const before = new URL(page.url()).pathname;
  const button = await page.$(buildButton);
  if (button === null) return { before, after: before, drawn: false };
  await button.click();
  await page.waitForTimeout(1200);
  return { before, after: new URL(page.url()).pathname, drawn: true };
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 · 2 · FROM THE CATALOGUE
// ═══════════════════════════════════════════════════════════════════════════
const fromCatalogue = await pressFrom(`/${TENANT}/reports`);
check("1 · `+ Build your own` is drawn on the catalogue", fromCatalogue.drawn);
check(
  "1 · pressing it LEAVES the catalogue",
  fromCatalogue.after !== fromCatalogue.before,
  `${fromCatalogue.before} → ${fromCatalogue.after}`,
);
await page.screenshot({ path: `${OUT}/1-from-catalogue.png`, fullPage: true });

const EDITOR = `/${TENANT}/reports/custom/new`;
check(
  "2 · it lands on the builder's own address",
  fromCatalogue.after === EDITOR,
  `expected ${EDITOR}, got ${fromCatalogue.after}`,
);
// BY THE SCREEN IT OPENS, not only by the address — `DEF-REP-6812` is the
// worked case: `/settings/audit-log` MATCHED a route perfectly well and opened
// Settings → Company.
const editorSections = await page.$$eval("[data-report-edit-panel]", (ns) => ns.length);
check("2 · and the editor's sections are on screen", editorSections === 1, `${editorSections} panel(s)`);

// ═══════════════════════════════════════════════════════════════════════════
// 3 · FROM `/reports/custom` — WHERE THE OLD TARGET WAS THE PAGE ITSELF
// ═══════════════════════════════════════════════════════════════════════════
const fromCustom = await pressFrom(`/${TENANT}/reports/custom`);
check(
  "3 · pressing it from /reports/custom is not a no-op",
  fromCustom.after === EDITOR,
  `${fromCustom.before} → ${fromCustom.after}`,
);
await page.screenshot({ path: `${OUT}/3-from-custom.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// 4 · THE DRAFT IS BLANK
// ═══════════════════════════════════════════════════════════════════════════
const dataset = await page.$eval("#report-edit-dataset", (n) => n.value).catch(() => "MISSING");
check("4 · no subject is chosen", dataset === "", `dataset select reads ${JSON.stringify(dataset)}`);
const ticked = await page.$$eval(
  "[data-report-edit-panel] input[type=checkbox]",
  (ns) => ns.filter((n) => n.checked).length,
);
check("4 · no column is ticked", ticked === 0, `${ticked} ticked`);
const filterRows = await page.$$eval("[data-report-filter]", (ns) => ns.length);
check("4 · no filter is on the bar", filterRows === 0, `${filterRows} filter row(s)`);

// ═══════════════════════════════════════════════════════════════════════════
// 5 · THE PREVIEW SAYS IT HAS NOTHING, AND SHOWS NO FIGURE
// ═══════════════════════════════════════════════════════════════════════════
const previewWords = await page
  .$eval("[data-report-blank-preview]", (n) => n.textContent.replace(/\s+/g, " ").trim())
  .catch(() => "");
check("5 · the preview says so in words", previewWords !== "", JSON.stringify(previewWords));
check(
  "5 · and carries no figure a clerk could read as money",
  !/\d[\d,]*\.\d\d/.test(previewWords),
  JSON.stringify(previewWords),
);
await page.screenshot({ path: `${OUT}/5-blank-editor.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// 6 · `Save as` ON A BLANK DRAFT IS REFUSED, NAMING WHAT IS MISSING
// ═══════════════════════════════════════════════════════════════════════════
await page.click('button:has-text("Save as")');
await page.waitForTimeout(600);
const refusal = await page
  .$eval("[data-report-save-refusal]", (n) => n.textContent.replace(/\s+/g, " ").trim())
  .catch(() => "");
check("6 · pressing Save as is refused", refusal !== "", JSON.stringify(refusal));
const dialogOpen = await page.$('input#name');
check("6 · and no Save-as dialog opened over an empty draft", dialogOpen === null);
await page.screenshot({ path: `${OUT}/6-refused.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// 7 · CHOOSE A SUBJECT, TICK A COLUMN, SAVE
// ═══════════════════════════════════════════════════════════════════════════
const datasets = await page.$$eval("#report-edit-dataset option", (ns) =>
  ns.map((n) => n.value).filter((v) => v !== ""),
);
say(`   datasets offered: ${datasets.length} — ${datasets.slice(0, 4).join(", ")}…`);
await page.selectOption("#report-edit-dataset", datasets[0]);
await page.waitForTimeout(800);
const boxes = await page.$$("[data-report-edit-panel] input[type=checkbox]");
check("7 · choosing a subject offers its columns", boxes.length > 0, `${boxes.length} column(s)`);
await boxes[0].click();
await page.waitForTimeout(400);
// Where it lives — the save needs a group, and the dialog's own field is
// required. Pick the first real group on the panel.
const groups = await page.$$eval(
  '[data-report-edit-panel] select[aria-label="Group"] option',
  (ns) => ns.map((n) => n.value).filter((v) => v !== ""),
);
if (groups.length > 0) {
  await page.selectOption('[data-report-edit-panel] select[aria-label="Group"]', groups[0]);
  await page.waitForTimeout(300);
}
await page.screenshot({ path: `${OUT}/7-filled.png`, fullPage: true });
await page.click('button:has-text("Save as")');
await page.waitForTimeout(800);
const nameBox = await page.$("input#name");
check("7 · the Save-as dialog opens once the draft is real", nameBox !== null);
if (nameBox !== null) {
  await nameBox.fill(NAME);
  if (groups.length > 0) {
    await page.selectOption("select#group", groups[0]).catch(() => {});
  }
  await page.waitForTimeout(200);
  await page.screenshot({ path: `${OUT}/7-dialog.png`, fullPage: true });
  // ⚠ **SCOPED TO THE DIALOG.** `button:has-text("Save")` also matches the
  // page head's `Save as` — which is BEHIND the overlay, so Playwright waited
  // sixty seconds for an element it could never click and the walk died with
  // a timeout that named neither button.
  await page.click('.modal-overlay button[type="submit"]');
  await page.waitForTimeout(2500);
}
const landed = new URL(page.url()).pathname;
check(
  "7 · the server created it and the screen opened what it made",
  landed !== EDITOR && landed.startsWith(`/${TENANT}/reports/`),
  `landed on ${landed}`,
);
await page.screenshot({ path: `${OUT}/7-saved.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// 8 · IT IS UNDER **CUSTOM**
// ═══════════════════════════════════════════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/reports/custom`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const customText = await page.$eval("body", (n) => n.textContent ?? "");
check("8 · the saved report is on the Custom sub-tab", customText.includes(NAME), NAME);
await page.screenshot({ path: `${OUT}/8-custom.png`, fullPage: true });

say("");
say(failures === 0 ? `ALL STEPS PASSED — shots in ${OUT}` : `${failures} STEP(S) FAILED — shots in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-REP-7640 (PO, deployed v2.388.0, 2026-09-28) · PO ruling 2026-09-28 "Opens the editor on a blank definition, then Save as" · 12-governance/22-product-maintenance-process.md §0/§4
// screens: 1·1 (S44) · 2·2 (A1 S47)
// generated: 2026-09-28 by lane REP-BUILD-YOUR-OWN
// gates: RUN RED FIRST against the unfixed build — steps 1, 2 and 3 failed naming `/brazosbend/reports/custom` as where the press landed; quoted in the lane report.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
