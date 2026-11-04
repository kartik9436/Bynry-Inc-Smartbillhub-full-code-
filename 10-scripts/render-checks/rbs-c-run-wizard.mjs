/**
 * RENDERED-OUTPUT CHECK — RBS-005's four Check-path states, region by region.
 *
 * ⚠ WHY THIS EXISTS. Hard-won law 6: *"no gate looks at rendered output"*, and
 * nine defects in one day were found by diffing the running app against
 * `05-prototype/` and by nothing else. Every other check on this screen asks a
 * question about SOURCE — `tsc` about types, vitest about markup strings,
 * `runWizardClasses` about whether a class compiles. **Not one of them can
 * answer "is the failed step's marker actually red, and is the table actually
 * 13.5px".**
 *
 * WHAT IT MEASURES, and each is a claim a source check cannot make. The numbers
 * come from the build sheets' own SIZE · STATE · RULE columns, not from taste:
 *
 *   1. every one of the four states paints — nothing renders as unstyled text,
 *      which is B14 rule 21's per-file trap (`DEF-974`);
 *   2. the page head is the shared kit's, and the subtitle is `r10`'s own 13px
 *      (`.page-head .sub`). ⚠ The TITLE is 40px where `r10` draws 32px and this
 *      sheet says 22px — `DEF-SHL-4295`, product-wide and not this screen's, so
 *      the size is PRINTED beside the defect id rather than asserted;
 *   3. the rail's four cells are ONE width apiece and the current one carries
 *      the accent — four, never the ladder's six (`04-flows.md` §4);
 *   4. the five progress markers are five DIFFERENT computed colours, and the
 *      failed one is actually red (`RBS-005.2` region 5);
 *   5. **not one progress row is blank** — `RBR-01`, read off the rendered text
 *      rather than off a props object;
 *   6. the progress rows are 13.5px and the right-hand figure is monospace
 *      (`RBS-005.2` region 5: *"13.5px rows … right text mono 11.5px"*);
 *   7. the bar is 5px on a neutral track with an accent fill, and its width is
 *      the honest fraction of steps (`RBS-005.2` regions 3 and 4);
 *   8. the consequence box sits ABOVE the commit row in real geometry, not just
 *      earlier in the markup (B14 rule 11);
 *   9. every address is tenant-scoped and none is protocol-relative
 *      (`DEF-CWP-3925`);
 *  10. no internal id, screen code or step key is VISIBLE (B14 rule 31, read as
 *      innerText because `data-screen` carries the id by design).
 *
 * ⚠ **WHAT IT CANNOT ANSWER, STATED WITH A NUMBER (law 7's fifth shape).** This
 * renders the component server-side and opens the markup in Chromium with the
 * real built stylesheet. It therefore does NOT exercise the app's router, its
 * shell, or a real API: **`RBS-005` has no route in `App.tsx` today** — the
 * Runbooks paths mounted so far are `/{tenant}/runbooks/:key` (RBS-004, task
 * C3) and nothing else, and route mounting is wave D's. So of the **24
 * measurements** this script makes (25 lines with `--shot`), **24 are about
 * this screen's own pixels and ZERO are about reaching it from a browser
 * address bar.** That half is owed,
 * it is wave D's one line, and it is named here rather than left to be assumed
 * from a green run.
 *
 * RUN (from the repo root):
 *   (cd 07-frontend && npx vite build \
 *     && npx vite-node ../10-scripts/render-checks/rbs-c-run-wizard.render.tsx -- /tmp/rbs.html)
 *   node 10-scripts/render-checks/rbs-c-run-wizard.mjs /tmp/rbs.html --shot /tmp/rbs.png
 * Exits non-zero on any failed measurement.
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
  console.error("usage: rbs-c-run-wizard.mjs <body.html> [--shot out.png]");
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
// file:// page resolves to the filesystem ROOT, loads nothing, and every element
// then measures at its BROWSER DEFAULT — which reads exactly like the
// unstyled-text defect this script is looking for.
const probe = path.join(DIST, "__rbs-c-run-wizard-probe.html");
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
const px = (value) => Math.round(parseFloat(value) * 10) / 10;

const browser = await chromium.launch({ executablePath: findChromium() });
const page = await browser.newPage({ viewport: { width: 1280, height: 1600 } });
await page.goto(`file://${probe}`);

// 0 · the stylesheet actually loaded. Without this every check below is
// unbelievable, because an unloaded sheet looks identical to a broken class.
// ⚠ NOT `cssRules`: a file:// stylesheet is cross-origin to a file:// page, so
// reading it throws SecurityError — the check that makes the others believable
// would itself be unable to run (law 7's "incapable of passing"). Ask the
// CASCADE instead.
const sheetLoaded = await page.evaluate(() => {
  const el = document.createElement("div");
  el.className = "flex";
  document.body.appendChild(el);
  const live = getComputedStyle(el).display === "flex";
  el.remove();
  return live;
});
check("the built stylesheet loaded", sheetLoaded, sheetLoaded ? "" : "nothing below is meaningful");
if (!sheetLoaded) {
  console.error(failures.join("\n"));
  await browser.close();
  process.exit(1);
}

// 1 · every state paints with real geometry.
for (const id of ["scope", "checking", "failed", "done"]) {
  const box = await page.locator(`[data-probe="${id}"]`).boundingBox();
  check(
    `RBS-005 ${id} paints`,
    box !== null && box.height > 120,
    box ? `${Math.round(box.width)}×${Math.round(box.height)}` : "no box",
  );
}

// 2 · the page head is r10's, measured. `RBS-005.1` region 1: kicker 11px
// uppercase 800, title 22px 800, subtitle 13.5px.
const head = await page.evaluate(() => {
  const scope = document.querySelector('[data-probe="scope"]');
  const back = scope.querySelector(".page-header-back");
  const h1 = scope.querySelector("h1");
  const sub = scope.querySelector(".page-header-rollup span");
  const s = (el) => (el ? getComputedStyle(el) : null);
  return {
    backText: back?.textContent ?? "",
    backHref: back?.getAttribute("href") ?? "",
    title: {
      size: s(h1).fontSize,
      weight: s(h1).fontWeight,
      text: h1.textContent,
      // The kit's own container, so "it composes PageHeader" is a measurement
      // rather than a claim about the source.
      inHead: h1.closest(".page-header-id") !== null,
    },
    sub: { size: s(sub).fontSize, text: sub.textContent },
  };
});
// ⚠ **THE TITLE'S SIZE IS THE SHARED KIT'S AND IT IS 8px FROM r10
// (`DEF-SHL-4295`, filed by this lane from this very measurement).** Three
// numbers exist for one thing: this sheet says 22px, `r10`'s own stylesheet
// says 32px (`SMARTBillHub.dc.html` line 136, `.page-head h1`), and the product
// draws **40px** because `global.css` sets every `h1` to `--text-h1` and
// `PageHeader.css` overrides nothing. That is true of every page head in the
// product, was true before this screen existed, and moving it is a change to a
// shared component rather than a lane's tidy-up. So what is asserted here is
// what this screen OWNS — that it composes the kit's head and does not roll its
// own title — and the measured size is printed beside the defect id so nobody
// reads the line as agreement.
check(
  `the title comes from the shared page head (DEF-SHL-4295: r10 draws 32px)`,
  Number(head.title.weight) >= 800 && head.title.text === "Run" && head.title.inHead,
  `${head.title.size} / ${head.title.weight} "${head.title.text}"`,
);
// The SUBTITLE is r10's own 13px (`.page-head .sub`), not the sheet's 13.5px —
// the same three-documents problem one line down, resolved the way B14 rule 36
// says to resolve it: the pack gives layout and detail, r10 gives the style.
check("the subtitle is r10's 13px and is the CHECK's sentence", px(head.sub.size) === 13 && head.sub.text === "This check changes nothing.", `${head.sub.size} "${head.sub.text}"`);
check("the ← is a real link out of the page (B14 rule 1)", head.backText.startsWith("←") && head.backHref === "/silvercreek/runbooks/configuration-check", `${head.backText} -> ${head.backHref}`);

// 3 · the rail — FOUR cells, one width apiece, the current one accent.
// ⚠ THE UNIFORM-WIDTH MEASUREMENT IS THE ONE ONLY A LAYOUT ENGINE CAN MAKE.
// `flex-1` distributes free space along each LINE, so a rail that wrapped would
// draw its last row wider — and jsdom, having no layout, cannot see it.
const rail = await page.evaluate(() => {
  const cells = [...document.querySelectorAll('[data-probe="scope"] [data-run-step]')];
  return cells.map((c) => ({
    id: c.getAttribute("data-run-step"),
    state: c.getAttribute("data-state"),
    width: Math.round(c.getBoundingClientRect().width),
    colour: getComputedStyle(c).color,
    badge: getComputedStyle(c.querySelector("span")).backgroundColor,
  }));
});
check("the rail draws FOUR cells, not the ladder's six", rail.length === 4, rail.map((c) => c.id).join(" · "));
check("every rail cell is the same width", Math.max(...rail.map((c) => c.width)) - Math.min(...rail.map((c) => c.width)) <= 1, `${Math.min(...rail.map((c) => c.width))}px … ${Math.max(...rail.map((c) => c.width))}px`);
const current = rail.find((c) => c.state === "current");
const todo = rail.find((c) => c.state === "todo");
check("the current cell is visibly different from a to-do one", current && todo && current.colour !== todo.colour && current.badge !== todo.badge, current && todo ? `${current.colour} / ${current.badge} vs ${todo.colour} / ${todo.badge}` : "missing");

// 4 · the five progress markers are five different colours, and failed is red.
const marks = await page.evaluate(() => {
  const rows = [
    ...document.querySelectorAll('[data-probe="checking"] li[data-run-progress-step]'),
    ...document.querySelectorAll('[data-probe="failed"] li[data-run-progress-step]'),
  ];
  return rows.map((r) => ({
    state: r.getAttribute("data-state"),
    bg: getComputedStyle(r.querySelector("[data-run-progress-mark]")).backgroundColor,
    size: getComputedStyle(r.querySelector("[data-run-progress-mark]")).height,
  }));
});
const byState = new Map(marks.map((m) => [m.state, m]));
check("the marker states drawn are distinct colours", new Set([...byState.values()].map((m) => m.bg)).size === byState.size, [...byState].map(([s, m]) => `${s}=${m.bg}`).join(" · "));
const failedMark = byState.get("failed");
const rgb = failedMark?.bg.match(/\d+/g)?.map(Number) ?? [];
check("a failed step's marker is actually red", rgb[0] > 150 && rgb[1] < 90 && rgb[2] < 90, failedMark?.bg ?? "no failed marker");
check("the marker is 18px, as the sheet's own size column says", marks.every((m) => px(m.size) === 18), [...new Set(marks.map((m) => m.size))].join(" · "));

// 5 · RBR-01 — NOT ONE ROW IS BLANK, read off the rendered text.
const rows = await page.evaluate(() =>
  [...document.querySelectorAll('[data-probe="failed"] li[data-run-progress-step]')].map((r) => ({
    key: r.getAttribute("data-run-progress-step"),
    state: r.getAttribute("data-state"),
    text: (r.innerText || r.textContent || "").replace(/\s+/g, " ").trim(),
    why: r.querySelector("[data-run-progress-why]")?.textContent ?? "",
  })),
);
check("all ten declared steps are listed on a run that stopped at step 2", rows.length === 10, `${rows.length} rows`);
const blank = rows.filter((r) => r.state !== "done" && r.why.trim() === "");
check("RBR-01 · not one step that did not run is blank", blank.length === 0, blank.length ? blank.map((r) => r.key).join(", ") : `${rows.filter((r) => r.why.includes("did not get this far")).length} read "The run did not get this far."`);

// 6 · the rows are the table tier and the right-hand figure is monospace.
const typography = await page.evaluate(() => {
  const row = document.querySelector('[data-probe="checking"] li[data-run-progress-step]');
  const detail = row.querySelector("[data-run-progress-detail]");
  return {
    row: getComputedStyle(row).fontSize,
    detail: getComputedStyle(detail).fontFamily,
    detailSize: getComputedStyle(detail).fontSize,
  };
});
check("a progress row is 13.5px (B14 rule 20 · the sheet's own size)", px(typography.row) === 13.5, typography.row);
check("the right-hand figure is monospace", /mono|Menlo|SFMono|ui-monospace/i.test(typography.detail), `${typography.detailSize} ${typography.detail}`);

// 7 · the bar: 5px, neutral track, accent fill, honest width.
const bar = await page.evaluate(() => {
  const track = document.querySelector('[data-probe="checking"] [data-run-bar]');
  const fill = track.querySelector("[data-run-bar-fill]");
  return {
    trackH: getComputedStyle(track).height,
    trackBg: getComputedStyle(track).backgroundColor,
    fillBg: getComputedStyle(fill).backgroundColor,
    ratio: fill.getBoundingClientRect().width / track.getBoundingClientRect().width,
    label: document.querySelector('[data-probe="checking"] [data-run-bar-label="left"]').textContent,
    right: document.querySelector('[data-probe="checking"] [data-run-bar-label="right"]').textContent,
  };
});
check("the bar is a 5px track with a different fill", px(bar.trackH) === 5 && bar.trackBg !== bar.fillBg, `${bar.trackH} · track ${bar.trackBg} fill ${bar.fillBg}`);
check("the fill is the honest fraction of STEPS (2 of 10)", Math.abs(bar.ratio - 0.2) < 0.01, `${(bar.ratio * 100).toFixed(1)}% · "${bar.label}" · "${bar.right}"`);
check("the right label is a percentage, not an invented time", /%/.test(bar.right) && !/second|minute/i.test(bar.right), `"${bar.right}"`);

// 8 · B14 rule 11 — the consequence box sits ABOVE the commit, in GEOMETRY.
const above = await page.evaluate(() => {
  const box = document.querySelector('[data-probe="scope"] [data-consequence]').getBoundingClientRect();
  const commit = document.querySelector('[data-probe="scope"] [data-run-action="start"]').getBoundingClientRect();
  return { boxBottom: box.bottom, commitTop: commit.top };
});
check("the consequence box is drawn above the commit button", above.boxBottom <= above.commitTop + 1, `box ends ${Math.round(above.boxBottom)}, button starts ${Math.round(above.commitTop)}`);

// 9 · every door is a real tenant-scoped address (DEF-CWP-3925).
const hrefs = await page.$$eval("a[href]", (els) => els.map((e) => e.getAttribute("href")));
const bad = hrefs.filter((h) => h.startsWith("//") || (!h.startsWith("/silvercreek/") && !h.startsWith("/api/silvercreek/")));
check("every address is tenant-scoped and none is protocol-relative", bad.length === 0 && hrefs.length >= 6, bad.length ? bad.join(" · ") : `${hrefs.length} links, all under /silvercreek/`);

// 10 · B14 rule 31 — read as innerText, because `data-screen` carries the id.
// ⚠ **SCOPED TO THE SCREENS, NOT TO THE PAGE.** The first draft read
// `document.body.innerText` and went red on THIS HARNESS'S OWN panel captions
// ("RBS-005.1 · 1 Scope"), which are scaffolding a clerk never sees. A check
// that reports its own scaffolding as a product defect is one that gets
// switched off, so the question is asked of `[data-screen]` and its contents.
const visible = await page.evaluate(() =>
  [...document.querySelectorAll("[data-screen]")].map((el) => el.innerText).join("\n"),
);
const leaks = [
  /\bBR-[A-Z]{3}-\d/, /\bUS-[A-Z]{3}-\d/, /\bOQ-\d/, /\bDEF-\d/, /\bS15\d/, /\bRBS-00\d\.\d/,
  /reads_and_windows/,
].filter((re) => re.test(visible));
check("nothing internal is visible to a clerk", leaks.length === 0, leaks.length ? leaks.map(String).join(" · ") : "no id, screen code or step key in the rendered text");

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
