/**
 * RENDERED-OUTPUT CHECK — the eight CR-075 wave C kit components.
 *
 * ⚠ WHY THIS EXISTS. Hard-won law 6: *"no gate looks at rendered output"*, and
 * nine defects in one day were found by diffing the running app against
 * `05-prototype/` and by nothing else. Every other check on these components
 * asks a question about SOURCE — `tsc` about types, eslint about style, vitest
 * about markup strings, `runbookKitClasses` about whether a class compiles.
 * **Not one of them can answer "is the danger band actually red on screen".**
 *
 * That is not a hypothetical gap on this exact surface. `DEF-SHL-4281`, filed
 * by this lane: `components/WarningBox.tsx` asks for `border-danger`, a colour
 * this theme does not declare, so B14 rule 6's danger tier draws in grey —
 * with `tsc`, eslint, every assertion and the compiler check written for that
 * shape all green over it. A COMPUTED COLOUR is the only thing that catches it.
 *
 * WHAT IT MEASURES, and each is a claim a source check cannot make:
 *   1. every one of the eight components paints — nothing renders as unstyled
 *      text, which is B14 rule 21's per-file trap (`DEF-974`);
 *   2. the three verdict tones are three DIFFERENT computed colours, and the
 *      danger one is actually red;
 *   3. a `bad` chain cell is visibly different from an `ok` one;
 *   4. the contribution bars are ordered widest-first and the top bar is full;
 *   5. every percentage on screen carries EXACTLY TWO decimals — hard rule 2,
 *      read off the rendered text rather than off a format string;
 *   6. the `ref:setting` box is DASHED, which is the visible half of the rule
 *      that its value is never duplicated;
 *   7. the sparkline has real geometry, and the estimated one is dashed;
 *   8. all 25 grid cells are real links with real hrefs (`DEF-CWP-3925`).
 *
 * RUN (from the repo root):
 *   (cd 07-frontend && npx vite build && npx vite-node ../10-scripts/render-checks/cr075-c-runbook-kit.render.tsx -- /tmp/body.html)
 *   node 10-scripts/render-checks/cr075-c-runbook-kit.mjs /tmp/body.html
 * Exits non-zero on any failed measurement. `--shot <path>` also writes a PNG.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const requireFrontend = createRequire(path.resolve("07-frontend/package.json"));
const { chromium } = requireFrontend("playwright-core");

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
  return wanted;
}

const bodyFile = process.argv[2];
const shotAt = process.argv.indexOf("--shot");
const shot = shotAt === -1 ? null : process.argv[shotAt + 1];
if (!bodyFile || !fs.existsSync(bodyFile)) {
  console.error("usage: cr075-c-runbook-kit.mjs <body.html> [--shot out.png]");
  process.exit(2);
}

const DIST = path.resolve(process.env.SBH_DIST ?? "07-frontend/dist/assets");
const css = fs
  .readdirSync(DIST)
  .filter((f) => f.endsWith(".css"))
  .map((f) => ({ f, s: fs.statSync(path.join(DIST, f)).size }))
  .sort((a, b) => b.s - a.s)[0]?.f;
if (!css) {
  console.error(`no stylesheet in ${DIST} — run \`npx vite build\` first`);
  process.exit(2);
}

// ⚠ RELATIVE href, and it is not a detail. A root-relative "/x.css" on a
// file:// page resolves to the filesystem ROOT, loads nothing, and every
// element then measures at its BROWSER DEFAULT — which reads exactly like the
// unstyled-text defect this script is looking for. `column-chooser-geometry.mjs`
// produced a false positive that way on 2026-08-24. The stylesheet-loaded
// assertion below is what makes a failure here believable.
const probe = path.join(DIST, "__cr075-kit-probe.html");
fs.writeFileSync(
  probe,
  `<meta charset="utf-8"><link rel="stylesheet" href="./${css}">
<body style="background:#f3f2f2;margin:0">${fs.readFileSync(bodyFile, "utf8")}</body>`,
);

const failures = [];
const notes = [];
function check(name, ok, detail) {
  (ok ? notes : failures).push(`${ok ? "ok  " : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: findChromium() });
const page = await browser.newPage({ viewport: { width: 1280, height: 1400 } });
await page.goto(`file://${probe}`);

// 0 · the stylesheet actually loaded. Without this every failure below is
// unbelievable, because an unloaded sheet looks identical to a broken class.
// ⚠ NOT `cssRules`. A file:// stylesheet is cross-origin to a file:// page, so
// reading `.cssRules` throws SecurityError — the check that was supposed to make
// every other check believable was itself unable to run (hard-won law 7's
// "incapable of passing"). Ask the CASCADE instead: plant an element with a
// utility on it and see whether the utility did anything. That is the same
// question, answered by the thing that actually matters.
const sheetLoaded = await page.evaluate(() => {
  const probe = document.createElement("div");
  probe.className = "flex";
  document.body.appendChild(probe);
  const live = getComputedStyle(probe).display === "flex";
  probe.remove();
  return live;
});
check("the built stylesheet loaded", sheetLoaded, sheetLoaded ? "" : "nothing below is meaningful");
if (!sheetLoaded) {
  console.error(failures.join("\n"));
  await browser.close();
  process.exit(1);
}

// 1 · every section paints something with real geometry.
for (const id of ["verdict", "chain", "bars", "outcome", "settings", "percent", "sparkline", "grid"]) {
  const box = await page.locator(`[data-probe="${id}"]`).boundingBox();
  check(`${id} paints`, box !== null && box.height > 20, box ? `${Math.round(box.width)}×${Math.round(box.height)}` : "no box");
}

// 2 · the three verdict tones are three DIFFERENT computed colours, and danger
// is red. This is the measurement `DEF-SHL-4281` needed and nothing had.
const chipColours = await page.$$eval("[data-verdict-word]", (els) =>
  els.map((e) => getComputedStyle(e).backgroundColor),
);
check("three verdict tones, three colours", new Set(chipColours).size === 3, chipColours.join(" · "));
const danger = chipColours[0];
const rgb = danger.match(/\d+/g)?.map(Number) ?? [];
check("the danger verdict is actually red", rgb[0] > 150 && rgb[1] < 90 && rgb[2] < 90, danger);

// 3 · a bad chain cell is visibly different from an ok one.
const chainCells = await page.$$eval("[data-chain-cell]", (els) =>
  els.map((e) => ({
    state: e.getAttribute("data-chain-state"),
    bg: getComputedStyle(e).backgroundColor,
    top: getComputedStyle(e).borderTopColor,
  })),
);
const bad = chainCells.find((c) => c.state === "bad");
const ok = chainCells.find((c) => c.state === "ok");
check("ten chain cells", chainCells.length === 10, `${chainCells.length}`);
// ⚠ THE UNIFORM-WIDTH CHECK, ADDED AFTER LOOKING AT THE PICTURE.
// The first draft of `Chain` was `flex flex-wrap` with `flex-1`, which passes
// every assertion in `Chain.test.tsx` and renders WRONG: flex distributes free
// space along each LINE, so the last line stretches. At this viewport the ten
// cells broke 7 + 3 and *Reads* drew 390px beside a 158px *Services*, where
// `RBS-006-R1` draws every cell at one width. Nothing but a real layout engine
// can see this — jsdom has no layout, so the class assertion is unfalsifiable
// there. This is the measurement that turns "I looked once" into a check.
const cellWidths = await page.$$eval("[data-chain-cell]", (els) =>
  els.map((e) => Math.round(e.getBoundingClientRect().width)),
);
const widest = Math.max(...cellWidths);
const narrowest = Math.min(...cellWidths);
check("every chain cell is the same width, wrapped ones included",
  widest - narrowest <= 1, `${narrowest}px … ${widest}px`);
check("a red cell differs from a clear one", bad && ok && bad.bg !== ok.bg && bad.top !== ok.top,
  bad && ok ? `bad ${bad.bg} / ${bad.top} vs ok ${ok.bg} / ${ok.top}` : "missing");

// 4 · the bars are widest-first and the top bar is full.
const widths = await page.$$eval("[data-bar-fill]", (els) => els.map((e) => e.getBoundingClientRect().width));
const track = await page.locator("[data-bar-track]").first().boundingBox();
check("the largest row fills its track", Math.abs(widths[0] - (track?.width ?? 0)) < 1.5,
  `${widths[0]?.toFixed(1)} of ${track?.width?.toFixed(1)}`);
check("bars descend, largest first", widths.every((w, i) => i === 0 || w <= widths[i - 1] + 0.5),
  widths.map((w) => w.toFixed(0)).join(" ≥ "));
check("a zero-weight cause still draws a row with an empty bar", widths.at(-1) === 0, `${widths.at(-1)}`);

// 5 · HARD RULE 2, read off the SCREEN. Every percentage carries exactly two
// decimals — a format string cannot prove this and a screenshot cannot be
// grepped.
const percents = await page.$$eval("[data-percent]", (els) => els.map((e) => e.textContent ?? ""));
const twoDp = percents.filter((p) => /^[+-]?[\d,]+\.\d{2}%$/.test(p.trim()));
check("every percentage on screen shows exactly 2 decimals", twoDp.length === percents.length && percents.length >= 6,
  percents.join(" · "));

// 6 · the ref:setting box is dashed — the visible half of "never duplicated".
const dashed = await page.$$eval("[data-settings-owned]", (els) =>
  els.map((e) => getComputedStyle(e).borderTopStyle),
);
check("every Settings-owned field is dashed", dashed.length === 3 && dashed.every((s) => s === "dashed"), dashed.join(" · "));
const states = await page.$$eval("[data-settings-state]", (els) => els.map((e) => e.getAttribute("data-settings-state")));
check("a value Settings has not got says so rather than sitting blank", states.includes("notSet"), states.join(" · "));

// 7 · the sparkline has real geometry and the estimated one is dashed.
const lines = await page.$$eval("[data-sparkline-line]", (els) =>
  els.map((e) => ({ points: (e.getAttribute("points") ?? "").split(" ").length, dash: e.getAttribute("stroke-dasharray") })),
);
check("the sparkline plots every month", lines[0]?.points === 12, `${lines[0]?.points} points`);
check("an estimated series is dashed and a read one is not", lines[0]?.dash === null && lines.at(-1)?.dash === "4 3",
  `read=${lines[0]?.dash} estimated=${lines.at(-1)?.dash}`);
const svg = await page.locator("[data-sparkline]").first().boundingBox();
check("the sparkline does not change the row height", svg !== null && svg.height <= 27, `${svg?.height}px`);

// 8 · EVERY grid cell is a real door (DEF-CWP-3925).
const cells = await page.$$eval("[data-record-cell]", (els) =>
  els.map((e) => ({ tag: e.tagName, href: e.getAttribute("href"), bg: getComputedStyle(e).backgroundColor })),
);
check("25 grid cells", cells.length === 25, `${cells.length}`);
check("every cell is an <a> with a real href",
  cells.every((c) => c.tag === "A" && typeof c.href === "string" && c.href.startsWith("/silvercreek/") && !c.href.startsWith("//")),
  `${cells.filter((c) => c.tag === "A").length} of ${cells.length} are links`);
check("the three grid states are three colours", new Set(cells.map((c) => c.bg)).size === 3,
  [...new Set(cells.map((c) => c.bg))].join(" · "));

// 9 · a numeric column is RIGHT-ALIGNED. The first draft of `ReportTable` asked
// for `num`, which no stylesheet declares and no compiler emits, so every money
// column drew left-aligned with the class sitting in the DOM. Nothing but a
// computed style can see that.
const numeric = await page.$$eval("[data-report-table] td.cell-num", (els) =>
  els.map((e) => getComputedStyle(e).textAlign),
);
check("numeric report columns are right-aligned",
  numeric.length > 0 && numeric.every((a) => a === "right"),
  `${numeric.length} cells: ${[...new Set(numeric)].join(" · ")}`);

if (shot) {
  await page.screenshot({ path: shot, fullPage: true });
  notes.push(`ok    screenshot written to ${shot}`);
}
await browser.close();
fs.unlinkSync(probe);

console.log(notes.join("\n"));
if (failures.length > 0) {
  console.error(`\n${failures.join("\n")}\n\n${failures.length} FAILED`);
  process.exit(1);
}
console.log(`\nALL ${notes.length} CHECKS PASSED`);
