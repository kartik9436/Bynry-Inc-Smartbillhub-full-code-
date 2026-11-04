// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 `U1`/`U2`/`U3` — the units list, Add units · Details and
//          Add units · Review & create, against their drawn frames.
// Drawn:   04-docs/05-modules/04-metering/conformance/CR-089-p050-units-list.md
//          · CR-089-p053-add-units-details.md · CR-089-p059-add-units-review-create.md
// Rules:   B14 rule 15 (max two row actions visible, then `…`) · B14 rule 32 ·
//          B14 rule 37 (a drawn figure is an illustration) · BR-MET-094 +
//          BR-CUS-170 · BR-MET-1165 · hard-won law 6 (no gate reads rendered
//          output — this file and a person are the only things that do)
// Usage:   BASE=http://127.0.0.1:8377 node 10-scripts/cr089_u1u2u3_units_screens_walkthrough.mjs
//          (boot with 10-scripts/11-smoke-stack.sh, or point BASE at any
//          running join; nothing below writes.)
// ───────────────────────────────────────────────────────
//
// ⚠ **IT IS READ-ONLY AND THAT IS DELIBERATE.** `Continue` STAGES through
// `POST /premises/imports`, which validates every row and writes NOTHING
// (`BR-MET-004`, `US-MET-004` §5), so the review can be read without creating a
// single unit. `Create` is never pressed. The wave-E walkthrough beside this one
// is the file that presses it, because proving `BR-MET-1165` needs the write.
//
// ⚠ **FOUR THINGS HERE WERE FOUND BY THIS FILE AND BY NOTHING ELSE**, with the
// whole vitest suite, `tsc` and every gate green over them: the premises picker
// labelled its options with the property CODE first; the review's `Services`
// row carried `Utility services`, the premises column's spelling of the same
// fact; the preview table headed its first two columns `Unit` and `Unit ID`
// where the frame draws `Label` and `Unit number`; and the step rail read
// `Building and how many` / `Review` where the frame draws `Details` /
// `Review & create`. Every one is a STRING a test asserting a key's own value
// can never see is the wrong string.
//
// ⚠ **AND ONE ASSERTION IN HERE WAS WRONG BEFORE IT WAS RIGHT.** The row-action
// count read node COUNTS and `<details>` keeps its children in the DOM when
// closed, so it reported seven controls and a failure over a correct screen.
// B14 rule 15 caps what a person can SEE, so the check reads visibility.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8377";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089u123";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
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

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });
let failures = 0;
const say = (...p) => console.log(...p);
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── U1 · the units list ────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr", { timeout: 20000 });
const h1 = (await page.$eval("h1", (n) => n.textContent.trim()));
check("U1 · the H1 reads Units", h1 === "Units", h1);
const sub = await page.$eval(".page-header-rollup", (n) => n.textContent.trim()).catch(() => "");
check("U1 · the drawn subtitle sits under the title", sub.startsWith("Every unit that can take service"), sub);
check("U1 · no explainer below the strip", (await page.$$(".page-header-explainer")).length === 0);
const headers = await page.$$eval("table thead th", (ns) => ns.map((n) => n.textContent.trim()));
say("columns:", JSON.stringify(headers));
check("U1 · Unit is column 2 (after Select) and Address is column 3", headers[1] === "Unit" && headers[2] === "Address", JSON.stringify(headers.slice(0, 4)));
check("U1 · the header reads Occupant", headers.includes("Occupant") && !headers.includes("Occupant / Account"));
const rows = await page.$$eval("table tbody tr", (rs) =>
  rs.slice(0, 12).map((r) => Array.from(r.querySelectorAll("td")).map((c) => c.innerText.trim())));
const mi = headers.indexOf("Meters");
const meterCells = rows.map((r) => r[mi]).filter((v) => v !== undefined);
say("meter cells:", JSON.stringify(meterCells.slice(0, 8)));
check("U1 · Meters is a count or the absence word, never an asset number",
  meterCells.every((v) => /^\d+$/.test(v) || /no meters/i.test(v)), JSON.stringify(meterCells.slice(0, 8)));
const oi = headers.indexOf("Occupant");
const wi = headers.indexOf("Owed");
const vacant = rows.find((r) => /Vacant/i.test(r[oi] ?? ""));
say("a vacant row:", JSON.stringify(vacant ? [vacant[oi], vacant[wi]] : null));
check("U1 · a vacant row says who pays, as VISIBLE text",
  vacant !== undefined && /base charges bill to the owner/i.test(vacant[oi]), JSON.stringify(vacant?.[oi]));
check("U1 · and its money cell never invents a zero",
  vacant === undefined || !/^0\.00$/.test(vacant[wi] ?? ""), JSON.stringify(vacant?.[wi]));
// ⚠ **VISIBILITY, NOT PRESENCE.** `<details>` keeps its children in the DOM
// when it is closed, so a selector count reads SEVEN and B14 rule 15 caps what
// a person can SEE. The first draft of this check counted nodes and reported a
// failure over a correct screen — which is the same class of mistake as a check
// that cannot fail, one step to the left.
const actionNames = await page.$$eval(
  "table tbody tr:first-child td:last-child button, table tbody tr:first-child td:last-child a, table tbody tr:first-child td:last-child summary",
  (ns) => ns.filter((n) => n.checkVisibility()).map((n) => n.getAttribute("aria-label") ?? n.textContent.trim()),
);
say("row actions VISIBLE:", JSON.stringify(actionNames));
check("U1 · three controls are visible on the row: open, edit, more", actionNames.length === 3, JSON.stringify(actionNames));
await page.screenshot({ path: `${OUT}/01-units-list-1440.png` });
// the overflow actually opens
await page.click("table tbody tr:first-child td:last-child details summary");
const menu = await page.$$eval("table tbody tr:first-child td:last-child details div button", (ns) => ns.map((n) => n.textContent.trim()));
say("overflow menu:", JSON.stringify(menu));
check("U1 · the four moved actions are in the overflow, with their words", menu.length === 4, JSON.stringify(menu));
await page.screenshot({ path: `${OUT}/02-row-overflow.png` });
await page.setViewportSize({ width: 1280, height: 1000 });
await page.goto(`${BASE}/${TENANT}/premises/units`, { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr");
const sideways = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
check("U1 · the page body does not scroll sideways at 1280", !sideways);
await page.screenshot({ path: `${OUT}/03-units-list-1280.png` });

// ── U2 · Add units · Details, opened FROM a property ───────────────────────
await page.setViewportSize({ width: 1440, height: 1400 });
const premises = await page.evaluate(async (t) => {
  const r = await fetch(`/api/${t}/premises?per=50`, { credentials: "include" });
  return (await r.json()).results ?? [];
}, TENANT);
const withUnits = premises.find((p) => (p.units ?? 0) > 0) ?? premises[0];
await page.goto(`${BASE}/${TENANT}/premises/${withUnits.id}`, { waitUntil: "networkidle" });
await page.waitForSelector("h1");
await page.click('button:has-text("+ New unit")');
await page.waitForURL((u) => u.pathname.endsWith("/premises/units/new"), { timeout: 20000 });
const url = new URL(page.url());
check("U2 · the door carried the building", url.searchParams.get("premises") === withUnits.id, page.url());
await page.waitForSelector("#premises_id", { timeout: 20000 });
await page.waitForTimeout(1500);
const labels = await page.$$eval(".field label, label", (ns) => ns.map((n) => n.textContent.trim()));
say("field labels:", JSON.stringify(labels));
for (const want of ["Search premises", "How many units", "Start numbering at", "Unit type", "Floor", "Unit numbers", "Or add a common area instead", "Plan", "Starts", "Or leave it for later"]) {
  check(`U2 · ${want} is on the form`, labels.some((l) => l.startsWith(want)), "");
}
const cardText = await page.$eval("#premises_id", () => 1).catch(() => 0);
const bodyText = await page.evaluate(() => document.body.innerText);
check("U2 · the building card is filled in from the door", /Change/.test(bodyText) && bodyText.includes(withUnits.address_line), withUnits.address_line);
check("U2 · Cancel is the header action and `← Units` is gone", /Cancel/.test(bodyText) && !/←\s*Units/.test(bodyText));
await page.screenshot({ path: `${OUT}/04-add-units-details.png`, fullPage: true });
void cardText;

// ── U3 · the review · Continue STAGES and writes nothing (US-MET-004 §5) ────
await page.fill("#units_per_floor", "7");
await page.click('button:has-text("Continue")');
await page.waitForSelector("table thead th", { timeout: 30000 });
await page.waitForTimeout(1200);
const answers = await page.$$eval("dl dt", (ns) => ns.map((n) => n.textContent.trim()));
say("answer rows:", JSON.stringify(answers));
for (const want of ["Building", "It has today", "Route and cycle", "Services", "How many", "Unit numbers", "Unit type", "Floor", "Plan", "Common areas"]) {
  check(`U3 · the answer row ${want}`, answers.includes(want), JSON.stringify(answers));
}
const previewHeaders = await page.$$eval("[data-consequence-panel] thead th", (ns) => ns.map((n) => n.textContent.trim()));
say("preview columns:", JSON.stringify(previewHeaders));
check("U3 · the five drawn columns, Type and Starts included",
  JSON.stringify(previewHeaders) === JSON.stringify(["Label", "Unit number", "Type", "Plan", "Starts"]),
  JSON.stringify(previewHeaders));
const previewRows = await page.$$eval("[data-consequence-panel] tbody tr", (ns) => ns.length);
check("U3 · EVERY row is drawn — a run of seven shows seven", previewRows === 7, String(previewRows));
const reviewText = await page.evaluate(() => document.body.innerText);
check("U3 · nothing is elided", !/and \d+ more/i.test(reviewText));
check("U3 · the consequence box is the kit's", (await page.$$('[data-consequence="add-units"]')).length === 1);
check("U3 · the commit says what it will do", /Create 7 units/.test(reviewText), "");
await page.screenshot({ path: `${OUT}/05-add-units-review.png`, fullPage: true });

const failed = failures;
say(`\n${failed === 0 ? "ALL PASS" : `${failed} FAILURE(S)`}`);
await browser.close();
process.exit(failed === 0 ? 0 : 1);
