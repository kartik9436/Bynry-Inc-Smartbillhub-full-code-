#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-056 W4 task 21 — an account with nothing to bill reads
//           *nothing to bill this period*, never an empty table.
// Rules:    BR-BIL-1024 · BR-BIL-1025 · B14 rules 21 (a utility only compiles
//           for a file on route-b-migrated.txt), 31 (no database id is the
//           visible value of a field) and 32 (a stated absence is CLOSED by
//           default, and no rule id or internal code in clerk-facing copy)
// Source:   PO ruling 2026-08-30 — *"All UI screen should be confirm using
//           real broswer testing and not just based on test cases"*
// ───────────────────────────────────────────────────────
/**
 * Open the step-2 markup in a REAL Chromium with the REAL compiled stylesheet
 * and measure what a clerk would actually see.
 *
 * ⚠ **WHY THIS EXISTS BESIDE FIVE PASSING VITEST CASES, and it is B14 rule 21
 * rather than ceremony.** The migration clause is per FILE: a Tailwind utility
 * written in a file that is not on `07-frontend/src/styles/route-b-migrated.txt`
 * renders as **nothing at all**, and `tsc`, eslint and every `toContain("mt-2")`
 * assertion pass on it because the class IS in the DOM. Only a browser with a
 * real style engine can answer whether a class DREW.
 *
 * ⚠ **AND IT MEASURES COMPUTED STYLE, NOT MARKUP.** `toContain("overflow-x-auto")`
 * is the check that cannot fail; `getComputedStyle(...).overflowX === "auto"` is
 * the one that can. Each assertion below reads a property whose default is
 * DIFFERENT from the expected value, so a stylesheet that failed to load turns
 * this red rather than leaving it quietly green.
 *
 * ⚠ **WHAT IT DOES NOT PROVE, said out loud.** It renders the component against
 * a served fixture rather than driving a whole bill run, because a silent
 * account cannot reach a CYCLE run today (`CR-056` §12's own correction: the
 * scope read cannot see an account that covers nothing). So this answers *"do
 * these classes paint, and does the copy read as words"* and NOT *"does a real
 * run put an account in this list"* — which is honest work still owed and is
 * recorded there rather than implied here.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   (cd 07-frontend && npx vite build)
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr056-w4-nothing-to-bill.mjs
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = join(here, "..", "..", "07-frontend");
const requireFrontend = createRequire(join(frontend, "package.json"));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const entry of readdirSync(root)) {
      for (const candidate of [
        join(root, entry, "chrome-linux", "chrome"),
        join(root, entry, "chrome-linux", "headless_shell"),
      ]) {
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found — never run `playwright install`");
}

function builtStylesheet() {
  const assets = join(frontend, "dist", "assets");
  if (!existsSync(assets)) throw new Error("run `npx vite build` in 07-frontend first");
  const css = readdirSync(assets).filter((f) => f.endsWith(".css"));
  if (css.length === 0) throw new Error("the build produced no stylesheet");
  return css.map((f) => readFileSync(join(assets, f), "utf8")).join("\n");
}

// The markup `SilentAccounts` produces, copied from the component so the class
// list under test is the one that ships. A divergence here is caught by the
// vitest cases, which assert the same strings against the real render.
const MARKUP = `
<div data-brun-s2="kpis">
  <details class="mt-2" data-brun-s2="silent-why">
    <summary class="cursor-pointer text-base">Which accounts had nothing to bill</summary>
    <div class="mt-2 overflow-x-auto">
      <table>
        <thead><tr><th>Account</th><th>Situation</th></tr></thead>
        <tbody>
          <tr data-brun-s2="silent-row" data-reason="account_has_nothing_to_bill">
            <td>AC-2026-00002</td>
            <td><span class="pill neutral">Nothing to bill this period</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </details>
</div>`;

const failures = [];
const notes = [];
function check(name, ok, detail) {
  if (ok) notes.push(`  PASS  ${name}`);
  else failures.push(`  FAIL  ${name} — ${detail}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.setContent(
  `<!doctype html><html><head><style>${builtStylesheet()}</style></head>` +
    `<body>${MARKUP}</body></html>`,
);

// 1 · THE CLASSES DREW. `mt-2` is 0.5rem; an undeclared class leaves 0px, which
//     is what B14 rule 21's migration clause produces on an unmigrated file.
const marginTop = await page.$eval('[data-brun-s2="silent-why"]', (el) =>
  getComputedStyle(el).marginTop,
);
check("the disclosure's `mt-2` compiles and paints", marginTop !== "0px", `marginTop=${marginTop}`);

const overflowX = await page.$eval('[data-brun-s2="silent-why"] div', (el) =>
  getComputedStyle(el).overflowX,
);
check("the table wrapper scrolls on its own (`overflow-x-auto`)", overflowX === "auto", `overflowX=${overflowX}`);

const cursor = await page.$eval('[data-brun-s2="silent-why"] summary', (el) =>
  getComputedStyle(el).cursor,
);
check("the summary is clickable to look at (`cursor-pointer`)", cursor === "pointer", `cursor=${cursor}`);

// 2 · CLOSED BY DEFAULT — B14 rule 32. The row must not be VISIBLE until the
//     disclosure is opened, and `open` must be absent from the element.
const openAttr = await page.$eval('[data-brun-s2="silent-why"]', (el) => el.hasAttribute("open"));
check("closed by default (B14 rule 32)", openAttr === false, "the `open` attribute is set");
const hiddenBeforeClick = await page.$eval('[data-brun-s2="silent-row"]', (el) => {
  const box = el.getBoundingClientRect();
  return box.width === 0 && box.height === 0;
});
check("the row is not drawn until somebody asks", hiddenBeforeClick, "the row has a box while closed");

// 3 · IT OPENS, AND WHAT IT SAYS IS WORDS.
await page.click('[data-brun-s2="silent-why"] summary');
const rowText = await page.$eval('[data-brun-s2="silent-row"]', (el) => el.innerText.trim());
check(
  "it reads *Nothing to bill this period*, in words",
  rowText.includes("Nothing to bill this period"),
  `row read ${JSON.stringify(rowText)}`,
);
check(
  "no reason CODE reaches the clerk (B14 rule 32)",
  !rowText.includes("account_has_nothing_to_bill"),
  "the code is visible text",
);
const reasonAttr = await page.$eval('[data-brun-s2="silent-row"]', (el) =>
  el.getAttribute("data-reason"),
);
check(
  "…and the code still rides as evidence",
  reasonAttr === "account_has_nothing_to_bill",
  `data-reason=${reasonAttr}`,
);
check(
  "no database id is the visible value of a field (B14 rule 31)",
  !/[0-9a-f]{8}-[0-9a-f]{4}/.test(rowText),
  "a uuid is visible",
);

// 4 · IT IS NOT AN EMPTY TABLE. The row exists and carries text in both cells.
const cells = await page.$$eval('[data-brun-s2="silent-row"] td', (tds) =>
  tds.map((td) => td.innerText.trim()),
);
check("never an empty table — every cell says something", cells.length === 2 && cells.every(Boolean), JSON.stringify(cells));

// 5 · NOTHING SCROLLS SIDEWAYS AT 1440.
const sideways = await page.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
);
check("the page does not scroll sideways at 1440", !sideways, "it does");

await browser.close();

console.log("CR-056 W4 task 21 — nothing to bill this period, in a real browser\n");
for (const line of notes) console.log(line);
for (const line of failures) console.log(line);
console.log(
  `\n${failures.length === 0 ? "PASS" : "FAIL"}: ${notes.length} check(s) passed, ` +
    `${failures.length} failed.`,
);
process.exit(failures.length === 0 ? 0 : 1);
