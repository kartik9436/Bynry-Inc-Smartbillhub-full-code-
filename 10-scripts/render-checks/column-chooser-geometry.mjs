/**
 * RENDERED-OUTPUT CHECK — the column chooser's geometry.
 *
 * ⚠ WHY THIS EXISTS, AND WHY IT IS NOT A VITEST TEST.
 * Hard-won law 6: "no gate looks at rendered output", and nine defects were
 * found by that and nothing else. DEF-440 is one of them — the chooser panel
 * was too narrow, so every row wrapped its LABEL underneath its own checkbox
 * and a one-line row became three. The PO's words: *"its square, 1 column in
 * 1 row and arrows; in your UI it is disturbed"*.
 *
 * It was fixed, and on 2026-08-24 the symptom was reported AGAIN — once by the
 * PO against the deployed app, once by a lane against its own build. Neither
 * report could be reproduced from source, because the source is CORRECT: this
 * script measures 336px (= 21rem) and `display: flex` on every label. That
 * gap — a layout defect that source review passes and vitest cannot see — is
 * exactly the hole law 6 names.
 *
 * A vitest test CANNOT replace this. jsdom has no layout engine: it will
 * happily report `display: block` on a `.flex` element and every width as 0,
 * so an assertion about wrapping is unfalsifiable there. Only a real engine
 * can answer "did this wrap".
 *
 * WHAT IT CHECKS: the panel is exactly 21rem wide (a FIXED width, not a
 * min-width — a menu that reflows while the pointer is inside it moves the row
 * being clicked), each label computes to a flex row, and each row is ONE LINE
 * TALL. It reads the real built CSS from `dist/`, so it fails if a utility
 * stops generating a rule as much as if the markup changes.
 *
 * ⚠ THE HEIGHT IS THE ASSERTION THAT CATCHES DEF-440, AND THE OBVIOUS ONE DOES
 * NOT. "Is the checkbox on the same line as its text" sounds like the right
 * question and is unfalsifiable here: a `<label>` that is `display: flex` has
 * `flex-wrap: nowrap`, so its two children NEVER move onto separate lines
 * whatever the width — the text wraps INSIDE its own box instead and the row
 * grows taller. Both pre-fix shapes were planted and both passed that check.
 * What DEF-440 actually looked like is the PO's own words: *"a one-line row
 * becomes three"*. So the row's HEIGHT is the measurement, and it was shown to
 * go red on the pre-fix markup before this file was trusted green.
 *
 * RUN:  npx vite build && node 10-scripts/render-checks/column-chooser-geometry.mjs
 * Exits non-zero on any wrapped row or a panel that is not 21rem.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

// Borrow playwright-core from 07-frontend/node_modules, the way
// `12-smoke-walkthrough.mjs` does — this script has no dependencies of its own
// and must not add a second install.
const requireFrontend = createRequire(
  path.resolve("07-frontend/package.json"),
);
const { chromium } = requireFrontend("playwright-core");

/** Any installed chromium, not only the revision playwright pinned. */
function findChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  if (fs.existsSync(path.join(root, "chromium"))) return path.join(root, "chromium");
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    if (!dir.startsWith("chromium")) continue;
    for (const rel of ["chrome-linux/chrome", "chrome"]) {
      const candidate = path.join(root, dir, rel);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return wanted; // let playwright report the miss in its own words
}

const DIST = path.resolve(process.env.SBH_DIST ?? "07-frontend/dist/assets");
const REM = 16;
const EXPECTED_PANEL_PX = 21 * REM; // w-[21rem], DataTable.tsx

if (!fs.existsSync(DIST)) {
  console.error(`no build at ${DIST} — run \`npx vite build\` in 07-frontend first`);
  process.exit(2);
}
const css = fs
  .readdirSync(DIST)
  .filter((f) => f.endsWith(".css"))
  .map((f) => ({ f, s: fs.statSync(path.join(DIST, f)).size }))
  .sort((a, b) => b.s - a.s)[0]?.f;
if (!css) {
  console.error(`no stylesheet in ${DIST}`);
  process.exit(2);
}

// The panel, copied hunk-for-hunk from DataTable.tsx. ⚠ If that markup changes,
// change it here — this file is a MEASUREMENT of those classes, so a copy that
// drifts measures nothing. The long labels are deliberate: a label that fits is
// not a test of whether a long one wraps.
// One text line at this font is ~20px. Two lines is ~37px. The bound sits
// between them rather than at either, so a font-size change of a point or two
// does not turn this into a flake — and DEF-440's three-line row (~54px) is
// nowhere near it.
const MAX_ROW_PX = 28;

const LABELS = [
  "Account #",
  "Name",
  "Premise",
  "Services",
  "Balance",
  "Last bill",
  "Status",
  "Ageing",
  "Opening balance as at cutover", // long enough to force the truncate path
];
const row = (label) => `
  <div class="flex items-center justify-between gap-2 text-base">
    <label class="flex min-w-0 flex-1 cursor-pointer items-center gap-2" title="${label}">
      <input type="checkbox" class="shrink-0" checked />
      <span class="truncate">${label}</span>
    </label>
    <span class="ml-auto inline-flex shrink-0 items-center gap-1">
      <button type="button" class="inline-flex h-6 w-6 cursor-pointer items-center justify-center border border-divider bg-transparent text-btn-sm text-neutral-700">&#8593;</button>
      <button type="button" class="inline-flex h-6 w-6 cursor-pointer items-center justify-center border border-divider bg-transparent text-btn-sm text-neutral-700">&#8595;</button>
    </span>
  </div>`;

// ⚠ RELATIVE href, and this is not a detail. A root-relative "/file.css" on a
// file:// page resolves to the filesystem ROOT, loads nothing, and every
// element then measures at its BROWSER DEFAULT — labels report `display:
// inline` and the panel reports the viewport width. That reads exactly like
// the defect this script is looking for. It produced a false positive on
// 2026-08-24 before the path was fixed. Verify the stylesheet loaded before
// believing a failure: the check below does.
const probe = path.join(DIST, "__column-chooser-probe.html");
fs.writeFileSync(
  probe,
  `<link rel="stylesheet" href="./${css}">
<div style="position:relative;height:700px">
  <div id="panel" class="absolute right-0 top-0 z-40 flex w-[21rem] flex-col gap-2 border border-divider bg-surface p-3 shadow-md">
    <p class="m-0 whitespace-nowrap font-heading text-btn-sm font-semibold uppercase tracking-wider text-neutral-600">Columns</p>
    ${LABELS.map(row).join("")}
  </div>
</div>`,
);

const browser = await chromium.launch({ executablePath: findChromium() });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto("file://" + probe);
  await page.waitForTimeout(200);

  const out = await page.evaluate(() => {
    // Did the stylesheet actually load? Without this, a broken href reports the
    // browser DEFAULTS as a layout failure — see the note on the relative href.
    //
    // ⚠ NOT `styleSheets[i].cssRules`: over file:// that access is opaque and
    // throws, so the "did it load" guard reported a miss while the very
    // stylesheet it was asking about was demonstrably applied. A guard whose
    // output cannot distinguish pass from fail is worse than no guard, because
    // it is trusted (CLAUDE.md law 11's own lesson, in a different file).
    //
    // A SENTINEL cannot lie: an off-screen element carrying one utility whose
    // effect is unmistakable. If `.flex` computes to `flex`, the stylesheet is
    // loaded and matching; if it computes to `block`, it is not there at all.
    const sentinel = document.createElement("div");
    sentinel.className = "flex";
    sentinel.style.position = "absolute";
    sentinel.style.left = "-9999px";
    document.body.appendChild(sentinel);
    const loaded = getComputedStyle(sentinel).display === "flex";
    sentinel.remove();
    const rows = [...document.querySelectorAll("label")].map((l) => {
      const cb = l.querySelector("input").getBoundingClientRect();
      const sp = l.querySelector("span").getBoundingClientRect();
      return {
        label: l.querySelector("span").textContent,
        display: getComputedStyle(l).display,
        sameLine: Math.abs(cb.top - sp.top) < 6,
        height: Math.round(Math.max(l.getBoundingClientRect().height, sp.height)),
      };
    });
    return {
      loaded,
      panelWidth: Math.round(document.getElementById("panel").getBoundingClientRect().width),
      rows,
    };
  });

  const problems = [];
  if (!out.loaded) problems.push("the stylesheet did not load — this is the harness, not the app");
  if (out.panelWidth !== EXPECTED_PANEL_PX) {
    problems.push(`panel is ${out.panelWidth}px, expected ${EXPECTED_PANEL_PX}px (w-[21rem])`);
  }
  for (const r of out.rows) {
    if (r.display !== "flex") problems.push(`${JSON.stringify(r.label)}: label display=${r.display}, expected flex`);
    if (!r.sameLine) problems.push(`${JSON.stringify(r.label)}: the checkbox and its text are on different lines`);
    // THE DEF-440 ASSERTION. See the header: the row growing is the symptom,
    // not the two children separating.
    if (r.height > MAX_ROW_PX) {
      problems.push(
        `${JSON.stringify(r.label)}: DEF-440 — row is ${r.height}px, over the ${MAX_ROW_PX}px ` +
          `single-line bound; the label has wrapped and "a one-line row becomes three"`,
      );
    }
  }

  console.log(`stylesheet: ${css}`);
  console.log(`panel width: ${out.panelWidth}px (expected ${EXPECTED_PANEL_PX})`);
  for (const r of out.rows) {
    const ok = r.sameLine && r.display === "flex" && r.height <= MAX_ROW_PX;
    console.log(`  ${ok ? "OK " : "BAD"}  ${JSON.stringify(r.label).padEnd(34)} display=${r.display} h=${r.height}px`);
  }
  if (problems.length) {
    console.error("\ncolumn chooser geometry FAILED:");
    for (const p of problems) console.error("  - " + p);
    process.exitCode = 1;
  } else {
    console.log("\ncolumn chooser geometry: PASS — every row one line tall, panel at 21rem");
  }
} finally {
  fs.rmSync(probe, { force: true });
  await browser.close();
}
