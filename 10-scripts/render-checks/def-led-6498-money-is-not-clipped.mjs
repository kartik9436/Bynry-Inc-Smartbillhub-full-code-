/**
 * `DEF-LED-6498` / Finance blueprint `P2.2` (p014) — **NO ELEMENT CARRYING A
 * MONEY VALUE MAY BE NARROWER THAN THE MONEY IN IT.**
 *
 * The defect `P2.1` fixed: the Finance headline rendered `$23,766…`. The tile
 * gave its value **146px** of content width and the figure needed **159px**, so
 * `text-overflow: ellipsis` removed the cents — from the pixels, not from the
 * DOM. A receivable was displayed SMALLER than it is, on the screen whose job is
 * to say what the utility is owed, against CLAUDE.md hard rule 2 (money DISPLAYS
 * to two decimals).
 *
 * ⚠ **WHY THIS IS A BROWSER PROBE AND NOT A `vitest` CASE, WHICH IS THE WHOLE
 * POINT OF THE TASK.** `P2.2`'s own brief says it: *"A string assertion CANNOT
 * see this class of bug — the DOM text was always correct."* Every existing KPI
 * assertion reads `textContent`, gets the full `$23,766.56`, and passes — while
 * a clerk reads four digits and an ellipsis. And a `jsdom` test cannot rescue
 * it: **jsdom performs no layout**, so `scrollWidth` and `clientWidth` are both
 * `0` there and `0 > 0` is false for a clipped element and an unclipped one
 * alike. A guard written in `jsdom` would be hard-won law 7's *structurally
 * incapable of failing* — green on the defect, green on the fix, worthless in
 * both directions. Geometry is only real in a browser, so the check lives here,
 * beside `cr093-page-title-size.mjs`, whose shape it follows.
 *
 * ⚠ **IT READS `dist/`, SO IT MEASURES WHAT SHIPS.** It refuses when the built
 * stylesheet is missing rather than reporting a pass over nothing (law 7 again:
 * a check that cannot fail is worse than no check). Run `npx vite build` first.
 *
 * Usage:
 *   node 10-scripts/render-checks/def-led-6498-money-is-not-clipped.mjs
 *   node 10-scripts/render-checks/def-led-6498-money-is-not-clipped.mjs --before
 *
 * `--before` re-applies the two declarations this defect removed — the 180px
 * track minimum and `text-overflow: ellipsis` on `.kpi .v` — and **MUST fail**.
 * That is the red proof taken through the SAME entry point as the green run,
 * which is the half hard-won law 7 gained on 2026-09-04 (`DEF-GOV-3733`): a red
 * proof through a path nobody uses is no proof of the thing that matters.
 *
 * ── WHAT IT COVERS ────────────────────────────────────────────────────────
 * Every tile in the strip, not only the one that was reported — `P2.2`'s
 * outcome is *"Every KPI tile in the product is covered, not just this one"*.
 * `KPIStrip` is the ONE strip component (`components/KPIStrip.tsx`, 20 render
 * sites in 19 files per `KPIStrip.css`'s own note), so measuring the component
 * measures the product. The figures below are the range it must hold:
 *
 *   $23,766.56      Brazos Bend's receivable — the reported defect
 *   $1,234,567.89   `P2.1`'s stated ceiling; a T5 tenant at 40,000 accounts
 *   $0.00           the short end, which must not be special-cased away
 *   ($12,345.67)    a credit balance in accounting parentheses
 *
 * ⚠ **THE ASSERTION IS `scrollWidth > clientWidth` ON THE VALUE ELEMENT, AND
 * IT DOES NOT DEPEND ON THE ANCESTOR'S `overflow`.** `.kpi` sets
 * `overflow: hidden` for its own border layout; a check that read the TILE
 * would be answering a different question. `scrollWidth` is the value's own
 * content width and `clientWidth` its own box — they diverge exactly when the
 * figure does not fit, whatever any ancestor does about it.
 */
import pw from "/home/user/SMARTBillHub/07-frontend/node_modules/playwright-core/index.js";
import fs from "node:fs";
import path from "node:path";
const { chromium } = pw;

const REPO = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const DIST = path.join(REPO, "07-frontend/dist/assets");
const BEFORE = process.argv.includes("--before");
/** Where to drop a picture of the strip. Unset = measure only. */
const SHOTS = process.env.SHOTS ?? null;

if (!fs.existsSync(DIST)) {
  console.error(`REFUSING: ${DIST} does not exist — run \`npx vite build\` first.`);
  process.exit(2);
}
const sheets = fs
  .readdirSync(DIST)
  .filter((f) => f.endsWith(".css"))
  .map((f) => path.join(DIST, f));
if (!sheets.length) {
  console.error(`REFUSING: no built stylesheet in ${DIST} — run \`npx vite build\` first.`);
  process.exit(2);
}

/**
 * **THE SIX TILES `RevenueArPage` ACTUALLY DECLARES**, in its own order —
 * Billed · Collected · Collection % · Still owed · DSO · Written off YTD
 * (`RevenueArPage.tsx:248-340`). The COUNT is the reproduction and not a
 * detail, which the first draft of this file got wrong and is worth writing
 * down: with four invented tiles the strip never reached its `180px` track
 * minimum at all, so the pre-fix declarations clipped NOTHING and the red
 * proof came back green — a check structurally incapable of failing, caught
 * only because the red proof was run first (hard-won law 7).
 *
 * Money figures are the range a tile has to hold; the two non-money tiles are
 * short by nature and are carried so the strip has its real width.
 */
const FIGURES = [
  { label: "Billed", value: "$1,234,567.89", why: "P2.1's stated ceiling" },
  { label: "Collected", value: "($12,345.67)", why: "a credit, in parentheses" },
  { label: "Collection %", value: "94.2%", why: "a non-money tile, for the real count" },
  // ⚠ `still_owed` IS the receivable, and it is the FOURTH tile. The reported
  // figure is placed on it deliberately: `.kpi:first-child` drops its left
  // padding and so gets 20px more room than any other tile, which is enough to
  // hide this exact defect. A probe that put the reported value in slot one
  // would measure the one tile the bug spares.
  { label: "Still owed", value: "$23,766.56", why: "the reported defect — THE receivable" },
  { label: "DSO", value: "31 days", why: "a non-money tile, for the real count" },
  { label: "Written off YTD", value: "$0.00", why: "the short end" },
];

const css = sheets.map((f) => `<style>${fs.readFileSync(f, "utf8")}</style>`).join("");

/**
 * The two declarations `P2.1` removed, re-applied for the red proof. They are
 * written out here rather than read from git so this file states, in one place,
 * exactly what the defect WAS — a reader should not need a blame trail.
 */
const REGRESSION = `<style>
  .kpi-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) !important; }
  .kpi .v { overflow: hidden !important; text-overflow: ellipsis !important; }
</style>`;

const strip =
  `<div class="kpi-grid">` +
  FIGURES.map(
    (f) =>
      `<div class="kpi"><div class="k">${f.label}</div>` +
      `<div class="v">${f.value}</div>` +
      `<div class="d">this period</div></div>`,
  ).join("") +
  `</div>`;

let failures = 0;
let measurements = 0;

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
// The staff app's two mandatory widths. The strip is `auto-fit`, so 1280 packs
// the tiles tighter than 1440 and is the width that bites first.
for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  // ⚠ **THE STRIP IS MOUNTED INSIDE THE REAL FRAME, NOT ON A BARE PAGE, AND
  // THAT IS WHAT MAKES THIS CHECK CAPABLE OF FAILING.** The tiles do not get
  // the viewport: they get the viewport LESS the 240px sidebar and less
  // `.view`'s own padding (32px each side at 1440, 24px at 1280 — the
  // `max-width: 1440px` branch). At 1280 that is a ~976px column over six
  // tiles, which is where `minmax(180px, 1fr)` starts packing them and where
  // the cents were lost. Measured on a bare 1280px page the same six tiles are
  // comfortable and every assertion passes over the live defect.
  //
  // The classes are the product's own (`AppShell.tsx:862` and `:1066`), so this
  // column cannot drift from the real one without this file going red.
  await page.setContent(
    `${css}${BEFORE ? REGRESSION : ""}` +
      `<div class="app-shell"><div class="sidebar"></div>` +
      `<div class="main"><main class="view"><div class="fin-page">${strip}</div></main></div></div>`,
  );
  const got = await page.evaluate(() =>
    Array.from(document.querySelectorAll(".kpi .v")).map((el) => ({
      text: el.textContent,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      fontSize: getComputedStyle(el).fontSize,
    })),
  );
  if (got.length !== FIGURES.length) {
    console.error(
      `  FAIL  ${width}px  expected ${FIGURES.length} value elements, found ${got.length}` +
        " — the markup or the class names moved, and this check is measuring nothing.",
    );
    failures += 1;
  }
  for (const [i, m] of got.entries()) {
    measurements += 1;
    // `scrollWidth`/`clientWidth` are integers, so a sub-pixel rounding can show
    // a 1px difference on text that fits. 1px of slack keeps that from being a
    // false RED without letting a lost digit — never less than ~8px — through.
    const clipped = m.scrollWidth - m.clientWidth > 1;
    if (clipped) failures += 1;
    console.log(
      `  ${clipped ? "FAIL" : "PASS"}  ${width}px  ${m.text}  (${FIGURES[i].why}) → ` +
        `content ${m.scrollWidth}px in a ${m.clientWidth}px box at ${m.fontSize}` +
        (clipped ? `  — CLIPPED by ${m.scrollWidth - m.clientWidth}px` : ""),
    );
  }
  // A picture of the strip beside the numbers, because `P2.8` says this phase's
  // proof is a RENDERED-OUTPUT check rather than a journey, and a reader who
  // does not trust an integer can look at the cents.
  if (SHOTS) {
    fs.mkdirSync(SHOTS, { recursive: true });
    await page
      .locator(".kpi-grid")
      .screenshot({ path: path.join(SHOTS, `kpi-${BEFORE ? "before" : "after"}-${width}.png`) });
  }
  await page.close();
}
await browser.close();

if (BEFORE) {
  if (failures === 0) {
    console.error(
      "\nRED PROOF DID NOT GO RED — the pre-fix declarations clipped nothing, so this" +
        " check cannot fail and is worthless. Do not trust a green run of it.",
    );
    process.exit(1);
  }
  console.log(
    `\nRED PROOF OK: the pre-fix declarations clipped ${failures} of ${measurements} money values.`,
  );
  process.exit(0);
}
console.log(
  failures === 0
    ? `\ndef-led-6498: ${measurements} money values, none clipped, at 1280 and 1440.`
    : `\ndef-led-6498: ${failures} of ${measurements} money values are clipped.`,
);
process.exit(failures === 0 ? 0 : 1);
