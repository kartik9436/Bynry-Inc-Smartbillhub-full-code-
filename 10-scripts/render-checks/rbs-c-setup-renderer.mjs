/**
 * RENDERED-OUTPUT CHECK — `RBS-004`, the setup renderer, all seven tabs.
 * CR-075 wave C task C3.
 *
 * ⚠ WHY THIS EXISTS. Hard-won law 6: *"no gate looks at rendered output"*, and
 * nine defects in one day were found by diffing the running app against the
 * drawing and by nothing else. Every other check on this screen asks a question
 * about SOURCE — `tsc` about types, eslint about style, vitest about markup
 * strings and counts. **Not one of them can answer "is the Yes pill actually
 * red", "is the value column actually right-aligned", or "did that Tailwind
 * class do anything at all".**
 *
 * That last one is not hypothetical on this exact surface. `DEF-974`: a utility
 * in a file missing from `route-b-migrated.txt` renders as NOTHING, and `tsc`,
 * eslint and every `toContain("flex")` pass over it because the class IS in the
 * DOM. `DEF-SHL-4281`, filed one day before this: `WarningBox` asks for
 * `border-danger`, a colour this theme does not declare, so B14 rule 6's danger
 * tier drew in grey with every source check green. A COMPUTED STYLE is the only
 * instrument that sees either.
 *
 * ⚠ **WHY THIS SHAPE AND NOT `11-smoke-stack.sh`, STATED PLAINLY.** The full
 * stack cannot boot in this container: `python3 -c "import django"` fails and
 * there is no virtualenv anywhere on the box, so `11-smoke-stack.sh` refuses at
 * its own assumption 2 before it starts. And even booted it would measure
 * nothing here — `GET /runbooks/{key}` is task `D1`, in flight in a sibling
 * lane, so the screen would draw its failure state rather than its seven tabs.
 * So this follows the OTHER convention this repository already has for exactly
 * that case, the one `cr075-c-runbook-kit.mjs` established in this same wave:
 * build the SPA, server-render the real component with its real fixture, and
 * open it in real Chromium with the real built stylesheet. Postgres IS up; the
 * missing half is Python, and it is named rather than glossed.
 *
 * WHAT IT MEASURES, and each is a claim no source check can make:
 *   0.  the built stylesheet actually loaded — without this every result below
 *       is unbelievable, because an unloaded sheet looks exactly like a broken
 *       class;
 *   1.  all SEVEN tabs are drawn on every one of the seven tabs — the sheets
 *       crop to five, four and three, and `08-screen-layouts.md` says a lane
 *       building `RBS-004.7` literally ships a three-tab screen;
 *   2.  exactly one tab is active, and it is UNDERLINED — the sheet's *"active
 *       = ink with 2px accent underline"*, read as a computed border;
 *   3.  the count is visibly SMALLER than its label (13.5px vs 11px) — the
 *       reason `PageHeaderTab.count` was added to the kit at all;
 *   4.  a key–value row draws its label LEFT and its value RIGHT — every one of
 *       the six `PlainTable` regions says *"label left, value right-aligned"*;
 *   5.  a section heading is UPPERCASE and letter-spaced — *"12px uppercase 800
 *       · letter-spacing .08em"*;
 *   6.  Overview's three blocks sit SIDE BY SIDE in one row — region 3, *"3
 *       blocks in one grid row"*, measured as three equal tops;
 *   7.  a capability *Yes* and a *No* are two DIFFERENT computed colours and
 *       the *Yes* is actually red — B14 rule 6's danger tier, the exact thing
 *       `DEF-SHL-4281` found drawing grey;
 *   8.  the Guards **Edit** is really non-interactive, not merely styled so —
 *       `BR-RBS-012`, and a button that only LOOKS disabled is a guard a clerk
 *       can switch off;
 *   9.  the Runs table right-aligns its numeric column and draws the pager;
 *  10.  a step's `writes` marker is monospaced and small — *"right text mono
 *       11.5px"*;
 *  11.  NOTHING on the page renders as unstyled text (the `DEF-974` trap), and
 *       no region overflows its width;
 *  12.  a Check says *Nothing is written.* and a step with no why-line draws no
 *       second line at all (`BR-RBS-002`, `DEF-RBS-4285`).
 *
 * RUN (from the repo root):
 *   (cd 07-frontend && npx vite build && npx vite-node ../10-scripts/render-checks/rbs-c-setup-renderer.render.tsx -- /tmp/rbs004.html)
 *   node 10-scripts/render-checks/rbs-c-setup-renderer.mjs /tmp/rbs004.html --shots /tmp/rbs004-shots
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
const shotsAt = process.argv.indexOf("--shots");
const shotsDir = shotsAt === -1 ? null : process.argv[shotsAt + 1];
if (!bodyFile || !fs.existsSync(bodyFile)) {
  console.error("usage: rbs-c-setup-renderer.mjs <body.html> [--shots out-dir]");
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

// ⚠ RELATIVE href, and it is not a detail. A root-relative "/x.css" on a file://
// page resolves to the filesystem ROOT, loads nothing, and every element then
// measures at its BROWSER DEFAULT — which reads exactly like the unstyled-text
// defect this script is looking for. `column-chooser-geometry.mjs` produced a
// false positive that way on 2026-08-24.
const probe = path.join(DIST, "__rbs004-probe.html");
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

// 0 · the stylesheet actually loaded. Without this every check below is
// unbelievable. ⚠ NOT `cssRules`: a file:// stylesheet is cross-origin to a
// file:// page, so reading `.cssRules` throws SecurityError — the check that was
// supposed to make every other check believable would itself be unable to run
// (law 7's "incapable of passing"). Ask the CASCADE instead.
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

const TABS = ["overview", "steps", "scope", "guards", "limits", "runs", "activity"];

// ── 1 · all seven tabs on every tab (RBS-004.3/.5/.6/.7 crop to 5/4/4/3) ─────
for (const tab of TABS) {
  const count = await page.evaluate(
    (t) => document.querySelectorAll(`[data-shot="${t}"] [role="tab"]`).length,
    tab,
  );
  check(`${tab}: draws all seven tabs`, count === 7, `${count} tab(s)`);
}

// ── 2 · exactly one active tab, and it is UNDERLINED (computed border) ───────
for (const tab of TABS) {
  const measured = await page.evaluate((t) => {
    const tabs = [...document.querySelectorAll(`[data-shot="${t}"] [role="tab"]`)];
    const active = tabs.filter((el) => el.getAttribute("aria-selected") === "true");
    if (active.length !== 1) return { actives: active.length, width: 0, id: "" };
    const style = getComputedStyle(active[0]);
    return {
      actives: 1,
      width: parseFloat(style.borderBottomWidth),
      id: active[0].getAttribute("data-tab") ?? "",
      colour: style.borderBottomColor,
    };
  }, tab);
  check(
    `${tab}: exactly one tab is active and it is the one the address names`,
    measured.actives === 1 && measured.id === tab,
    `${measured.actives} active, id=${measured.id}`,
  );
  check(
    `${tab}: the active tab carries a real underline`,
    measured.width >= 1.5,
    `border-bottom ${measured.width}px ${measured.colour ?? ""}`,
  );
}

// ── 3 · the count is visibly smaller than its label ──────────────────────────
const countSize = await page.evaluate(() => {
  const strip = document.querySelector('[data-shot="overview"] [data-page-header-tabs]');
  const withCount = [...strip.querySelectorAll('[role="tab"]')].find((el) =>
    el.querySelector("[data-tab-count]"),
  );
  if (!withCount) return null;
  return {
    label: parseFloat(getComputedStyle(withCount).fontSize),
    count: parseFloat(getComputedStyle(withCount.querySelector("[data-tab-count]")).fontSize),
    text: withCount.textContent.trim(),
  };
});
check(
  "a tab's count is drawn smaller than its label (the reason the kit gained the field)",
  countSize !== null && countSize.count < countSize.label,
  countSize ? `"${countSize.text}" label ${countSize.label}px · count ${countSize.count}px` : "no counted tab",
);

// ── 4 · key–value rows: label LEFT, value RIGHT ──────────────────────────────
// ⚠ **MEASURED AS GEOMETRY, NOT AS `text-align`, AND THE FIRST DRAFT WAS WRONG
// IN THE INSTRUCTIVE DIRECTION.** It asked whether the cell's computed
// `text-align` was `right` — and a cell can report `left` while its content sits
// hard against the right edge, because justification and text alignment are two
// different mechanisms. Asking the property would now FAIL on a correct screen;
// asking the pixels answers the sheet's actual sentence, *"label left, value
// right-aligned"*, whatever mechanism achieves it. The first draft did find the
// real defect — the value really was drawn left — which is why the check stays
// and only its instrument changed.
const kv = await page.evaluate(() => {
  const rows = [...document.querySelectorAll('[data-shot="scope"] [data-kv]')];
  if (rows.length === 0) return null;
  // ⚠ **A `Range` OVER THE CELL'S CONTENTS, NOT `firstElementChild`.** The
  // second draft of this check measured the cell's first element — which is the
  // flex wrapper, and a flex wrapper FILLS its cell, so it reported `8px left /
  // 8px right` on a value that was in fact hard right. It could not have
  // distinguished a correct screen from a broken one, which is exactly what
  // CLAUDE.md law 7 means by asking what would make a check pass (or fail)
  // wrongly. A Range gives the TIGHT box of whatever was actually painted —
  // text nodes and elements alike — which is the thing a person sees.
  // ⚠ RANGE OVER THE CELL'S FLEX WRAPPER, NOT OVER THE CELL. The wrapper FILLS
  // the cell — that is what a flex row does — so a range over the cell returns
  // the wrapper's full width and reports the same gap on both sides whatever
  // the value is doing. Probed in the engine rather than guessed at, twice
  // over: cell 597→1140, wrapper 605→1132, painted text 997→1132.
  const tight = (el) => {
    const range = document.createRange();
    range.selectNodeContents(el.firstElementChild ?? el);
    return range.getBoundingClientRect();
  };
  return rows.map((row) => {
    const label = row.querySelector("th");
    const value = row.querySelector("td");
    const cell = value.getBoundingClientRect();
    const painted = tight(value);
    return {
      text: (label.textContent ?? "").trim(),
      value: (value.textContent ?? "").trim(),
      rightGap: Math.round(cell.right - painted.right),
      leftGap: Math.round(painted.left - cell.left),
    };
  });
});
// The sheet's sentence is *"label left, value right-aligned"*. A value is right
// when its painted box sits against the cell's right edge and there is real
// space on its left — measured, so a value drawn left cannot pass.
const alignedRight =
  kv !== null && kv.every((r) => r.rightGap <= 12 && r.leftGap > r.rightGap + 8);
check(
  "every key–value row draws its label left and its value hard right (all six regions say so)",
  alignedRight,
  kv
    ? kv.map((r) => `"${r.value}" ${r.leftGap}px left / ${r.rightGap}px right`).join(" · ")
    : "no row found",
);

// ── 5 · section headings are uppercase and letter-spaced ─────────────────────
const heading = await page.evaluate(() => {
  const h5 = document.querySelector('[data-shot="overview"] [data-region="schedule"] h5');
  if (!h5) return null;
  const s = getComputedStyle(h5);
  return {
    transform: s.textTransform,
    spacing: s.letterSpacing,
    size: parseFloat(s.fontSize),
    weight: s.fontWeight,
    text: h5.textContent,
  };
});
check(
  "a section heading is uppercase, letter-spaced and small",
  heading !== null &&
    heading.transform === "uppercase" &&
    parseFloat(heading.spacing) > 0 &&
    heading.size <= 13,
  heading
    ? `"${heading.text}" ${heading.size}px ${heading.weight} ${heading.transform} ls=${heading.spacing}`
    : "no heading",
);

// ── 6 · Overview's three blocks sit SIDE BY SIDE in one row ──────────────────
const blocks = await page.evaluate(() => {
  const tops = ["schedule", "last-run", "this-can"].map((r) => {
    const el = document.querySelector(`[data-shot="overview"] [data-region="${r}"]`);
    return el ? Math.round(el.getBoundingClientRect().top) : null;
  });
  const lefts = ["schedule", "last-run", "this-can"].map((r) => {
    const el = document.querySelector(`[data-shot="overview"] [data-region="${r}"]`);
    return el ? Math.round(el.getBoundingClientRect().left) : null;
  });
  return { tops, lefts };
});
const sameRow =
  blocks.tops.every((t) => t !== null && t === blocks.tops[0]) &&
  blocks.lefts[0] < blocks.lefts[1] &&
  blocks.lefts[1] < blocks.lefts[2];
check(
  "Overview draws its three blocks side by side in one row (region 3)",
  sameRow,
  `tops ${blocks.tops.join("/")} · lefts ${blocks.lefts.join("/")}`,
);

// ── 7 · a capability Yes is RED and a No is not ──────────────────────────────
const pills = await page.evaluate(() => {
  const one = (id) => {
    const el = document.querySelector(`[data-shot="overview"] [data-kv="${id}"] .pill`);
    if (!el) return null;
    const s = getComputedStyle(el);
    return { text: el.textContent.trim(), bg: s.backgroundColor, fg: s.color };
  };
  return { yes: one("notices"), no: one("bills") };
});
function rgb(value) {
  const m = /rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)/.exec(value ?? "");
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}
const yesFg = rgb(pills.yes?.fg);
const noFg = rgb(pills.no?.fg);
check(
  "a capability Yes and a No are two different computed colours",
  pills.yes && pills.no && pills.yes.fg !== pills.no.fg,
  `Yes ${pills.yes?.fg} on ${pills.yes?.bg} · No ${pills.no?.fg} on ${pills.no?.bg}`,
);
check(
  "the Yes pill is actually red — B14 rule 6's danger tier, drawn (DEF-SHL-4281)",
  yesFg !== null && yesFg[0] > yesFg[1] + 30 && yesFg[0] > yesFg[2] + 30,
  `Yes text ${pills.yes?.fg}`,
);
check(
  "the No pill is actually green — the reassurance a clerk is looking for",
  noFg !== null && noFg[1] > noFg[0] + 15,
  `No text ${pills.no?.fg}`,
);

// ── 8 · the Guards Edit is really non-interactive (BR-RBS-012) ───────────────
const guards = await page.evaluate(() => {
  const scope = document.querySelector('[data-shot="guards"]');
  const note = scope.querySelector("[data-guards-locked]");
  const edit = note ? note.querySelector("button") : null;
  if (!edit) return null;
  const box = edit.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
  const s = getComputedStyle(edit);
  return {
    disabled: edit.disabled,
    title: edit.getAttribute("title"),
    // A DISABLED button does not receive the click at all — that is what
    // `elementFromPoint` says, and it is the difference between a control that
    // is off and one that merely looks off.
    hitIsTheButton: hit === edit || edit.contains(hit),
    pointerEvents: s.pointerEvents,
    reason: note.querySelector("p")?.textContent ?? "",
    visible: box.width > 0 && box.height > 0,
  };
});
check(
  "the Guards Edit is drawn, disabled, and carries its reason (BR-RBS-012)",
  guards !== null && guards.disabled && guards.visible && (guards.reason ?? "").length > 0,
  guards ? `disabled=${guards.disabled} visible=${guards.visible} reason="${guards.reason}"` : "absent",
);
check(
  "the Guards refusal is six words or fewer (B14 rule 33)",
  (guards?.reason ?? "").split(/\s+/).filter(Boolean).length <= 6,
  `"${guards?.reason}" = ${(guards?.reason ?? "").split(/\s+/).filter(Boolean).length} words`,
);

// ── 9 · Runs — numeric column right-aligned, and the pager is drawn ──────────
const runs = await page.evaluate(() => {
  const scope = document.querySelector('[data-shot="runs"]');
  const headers = [...scope.querySelectorAll("thead th")].map((th) => th.textContent.trim()).filter(Boolean);
  const bodyRows = scope.querySelectorAll("tbody tr");
  const lastCell = bodyRows[1]?.querySelectorAll("td, th")[2];
  const pager = scope.querySelector(".table-pager-range");
  return {
    headers,
    rows: bodyRows.length,
    numericAlign: lastCell ? getComputedStyle(lastCell).textAlign : "",
    numericText: lastCell ? lastCell.textContent.trim() : "",
    pager: pager ? pager.textContent.trim() : "",
  };
});
check(
  "Runs draws When · Outcome · Acted and nothing else",
  JSON.stringify(runs.headers) === JSON.stringify(["When", "Outcome", "Acted"]),
  runs.headers.join(" | "),
);
check(
  "the Acted column is right-aligned (rule 20: numeric columns right, tabular)",
  runs.numericAlign === "right",
  `align=${runs.numericAlign} value="${runs.numericText}"`,
);
check("the pagination footer is drawn (rule 16)", runs.pager.length > 0, `"${runs.pager}"`);

// ── 10 · a step's read/writes marker is monospaced and small ─────────────────
const marker = await page.evaluate(() => {
  const el = document.querySelector('[data-shot="steps"] [data-step-writes="writes"]');
  if (!el) return null;
  const s = getComputedStyle(el);
  return { family: s.fontFamily, size: parseFloat(s.fontSize), text: el.textContent.trim() };
});
// ⚠ THE SHEET SAYS 11.5px AND THE SCREEN DRAWS 11px, DELIBERATELY. `tokens.css`
// deleted the half-steps on 2026-08-19 (OQ-275/276/278) and eslint refuses an
// arbitrary type value, so `text-xs` is the ruled step nearest the drawing. The
// bound below is the SCALE's, not the sheet's, and it is written that way so a
// reader is not surprised to see 11 where a sheet says 11.5.
check(
  "a step's writes marker is monospaced and on the ruled scale (sheet: mono 11.5px → text-xs, 11px)",
  marker !== null && /mono/i.test(marker.family) && marker.size <= 12,
  marker ? `"${marker.text}" ${marker.size}px ${marker.family.split(",")[0]}` : "absent",
);

// ── 11 · nothing renders as unstyled text, and nothing overflows ─────────────
const layout = await page.evaluate(() => {
  // The DEF-974 trap: a utility in an unlisted file emits NOTHING, so the
  // element falls back to the browser default. Two of this screen's own
  // utilities are asked whether they did anything at all.
  const grid = document.querySelector('[data-shot="overview"] [data-region="overview"]');
  const noteRow = document.querySelector('[data-shot="steps"] [data-settings-owned-note]');
  return {
    gridDisplay: grid ? getComputedStyle(grid).display : "",
    noteDisplay: noteRow ? getComputedStyle(noteRow).display : "",
    noteBorder: noteRow ? getComputedStyle(noteRow).borderLeftWidth : "",
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
check(
  "the Overview grid utility actually compiled (the DEF-974 trap)",
  layout.gridDisplay === "grid",
  `display=${layout.gridDisplay}`,
);
check(
  "the settings-owned note's utilities compiled — it is a flex row with a left rule",
  layout.noteDisplay === "flex" && parseFloat(layout.noteBorder) >= 3,
  `display=${layout.noteDisplay} border-left=${layout.noteBorder}`,
);
check("no region overflows the page width", layout.overflow <= 0, `${layout.overflow}px of overflow`);

// ── 12 · a Check: BR-RBS-002 on screen, and DEF-RBS-4285's absent why ────────
const check002 = await page.evaluate(() => {
  const overview = document.querySelector('[data-shot="check-overview"]');
  const steps = document.querySelector('[data-shot="check-steps"]');
  const absent = overview.querySelector('[data-absent="capabilities"]');
  const rows = [...steps.querySelectorAll("[data-step]")];
  return {
    sentence: absent ? absent.textContent.trim() : "",
    stepCount: rows.length,
    withWhy: rows.filter((r) => r.querySelector("[data-step-why]")).length,
    secondStepText: rows[1] ? rows[1].textContent.trim() : "",
  };
});
check(
  "a Check says Nothing is written rather than drawing an empty block (BR-RBS-002)",
  check002.sentence === "Nothing is written.",
  `"${check002.sentence}"`,
);
check(
  "a step whose why-line the contract cannot carry draws no second line (DEF-RBS-4285)",
  check002.stepCount === 3 && check002.withWhy === 1,
  `${check002.withWhy} of ${check002.stepCount} steps carry a why · step 2 reads "${check002.secondStepText}"`,
);

// ── screenshots, one per region ──────────────────────────────────────────────
if (shotsDir) {
  fs.mkdirSync(shotsDir, { recursive: true });
  for (const id of [...TABS, "check-overview", "check-steps"]) {
    const el = await page.$(`[data-shot="${id}"]`);
    if (el) await el.screenshot({ path: path.join(shotsDir, `RBS-004-${id}.png`) });
  }
  await page.screenshot({ path: path.join(shotsDir, "RBS-004-all.png"), fullPage: true });
  notes.push(`ok    screenshots written to ${shotsDir}`);
}

await browser.close();

// ⚠ THE OUTPUT DISTINGUISHES PASS FROM FAIL TO A READER, not merely to an exit
// code — CLAUDE.md law 7's third habit, added because `--stat` was twice
// trusted to answer a question it cannot answer. Every measurement prints its
// MEASURED VALUE beside its verdict, so a pass can be disbelieved.
console.log(notes.join("\n"));
if (failures.length > 0) {
  console.error(`\n${failures.join("\n")}`);
  console.error(`\n${failures.length} of ${failures.length + notes.length} measurements FAILED`);
  process.exit(1);
}
console.log(`\nall ${notes.length} measurements passed`);
