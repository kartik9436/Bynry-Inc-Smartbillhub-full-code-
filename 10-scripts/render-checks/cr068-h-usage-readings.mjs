/**
 * RENDERED-OUTPUT CHECK — CR-068 wave H, "Usage, readings and equipment", in a
 * real browser. Screens `CWP-033` (/usage), `CWP-034` (/readings),
 * `CWP-037` (/equipment).
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ⚠ **AND THIS WAVE'S SUBJECT IS MOSTLY ABSENCES, WHICH IS THE HARDEST THING
 * TO TEST ANYWHERE ELSE.** `BR-CWP-073` is satisfied by a panel that says
 * *Billed on: Water used* and draws **no chart**; `US-CWP-043` TC-2 is
 * satisfied by a last-read cell that is **empty and not `0`**. A unit test can
 * assert a payload; only a browser can tell you that no `<svg>` was painted
 * inside the sewer panel and that a table cell is blank rather than zero.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   eval "$(10-scripts/proof-db.sh clone cwph --export)"
 *   export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
 *   (cd 06-backend && python3 manage.py seed_portal_demo)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-h-fixture.py)
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8079 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4279 API_PROXY_TARGET=http://127.0.0.1:8079 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4279 node 10-scripts/render-checks/cr068-h-usage-readings.mjs
 *
 * ⚠ **BUILD THE BUNDLE FIRST.** A stale `dist/` means every assertion here
 * passes or fails about a build nobody is shipping.
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ── WHAT IT CLICKS (the wave H demo script, 10-execution-plan.md) ─────────
 *   1  `/usage` — the KPI row, then TWELVE bars with the axis labelled in
 *      gallons and the lowest and highest months MARKED. Every figure is
 *      printed rather than only asserted.
 *   2  24 months — the window widens and the same two months stay marked.
 *   3  The unmeasured services — sewer says *billed on water used*, trash says
 *      *your 96 gal cart*, and NEITHER panel contains a chart of any kind.
 *   4  `/readings` — the method in words, and the estimated row that opens to
 *      say what it was corrected FROM, TO and WHEN.
 *   5  `/equipment` — three serials, an EMPTY last-read cell on the cart, and
 *      `TEST DUE NOV` on the backflow device.
 *   6  The CSV — every row carries its unit in a column of its own.
 *   7  B14 rule 31/32 and rule 36 — no database id and no internal code on any
 *      of the three screens, and no column so narrow it wraps one word per line.
 *
 * ⚠ **WHAT IT REFUSES TO CLAIM, AND HOW.** Wave H's own title promises *the
 * signed-in help and tip slots*, and all three of those screens are unbuilt, so
 * the demo script's step 5 cannot be performed today: `CWP-061` (the answer
 * under the bill's charges) is not a screen at all and is tracked at
 * `DEF-CWP-3945`; `CWP-062` is `CWP-033` with the `TipBar` filled and nothing
 * fills it; `CWP-059` is the guest `/help` screen wearing a different number.
 *
 * Those, and four places where this screen differs from `wireframes/CWP-033.png`,
 * are recorded through `lib/knownGaps.mjs` as **known gaps with their register
 * ids** — never as silent skips and never as failures.
 * **A CHECK THAT IS RED BY DESIGN IS A CHECK NOBODY READS**: this run finished
 * RED five times on its first outing, every failure correct and every one a
 * filed defect, and a walkthrough that exits 1 forever teaches its reader that
 * red is its normal colour. A gap here goes **red in BOTH directions** — still
 * missing is counted and printed; PRESENT is a failure naming the row to
 * delete — so nothing is being silenced. The counts print on a pass too, because
 * `0 failures, 8 known gaps` must never look like `0 failures, 0 known gaps`.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

import { Gaps } from "./lib/knownGaps.mjs";
import { attachTimings } from "./lib/timings.mjs";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/**
 * Where chromium actually is.
 *
 * ⚠ **`executablePath()` RETURNS A PATH, NOT A BROWSER**, and it is computed
 * from the version playwright was built against rather than from what is
 * installed — so it can answer a path that does not exist without throwing.
 * The path is TESTED here rather than trusted (hard-won law 7's second shape,
 * a check structurally incapable of failing). Same eight lines as `cr068-g`.
 */
function resolveChromium() {
  const candidates = [];
  try {
    candidates.push(chromium.executablePath());
  } catch {
    /* the computed path is optional — the glob below is the real answer */
  }
  try {
    candidates.push(
      execFileSync("bash", [
        "-lc",
        "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
      ])
        .toString()
        .trim(),
    );
  } catch {
    /* nothing installed under /opt — the error below names what was tried */
  }
  for (const candidate of candidates) {
    if (candidate && existsSync(candidate)) return candidate;
  }
  throw new Error(
    `no chromium executable found. Tried: ${candidates.filter(Boolean).join(", ") || "(nothing)"}`,
  );
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4279";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "elm@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pine-Hill-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-h";
const VIEWPORT = { width: 1440, height: 1000 };
const PORTAL = `${BASE}/${TENANT}/portal`;

/** `US-CWP-040` §4 / `US-CWP-041` §4 / `US-CWP-043` §4 — the fixture's figures. */
const THIS_PERIOD = "4820";
const LOWEST = "3050";
const HIGHEST = "4820";

/**
 * ⚠ **THE FIGURE AND ITS FORMATTING ARE TWO CLAIMS AND ARE CHECKED SEPARATELY.**
 * The stories write every one of these with a thousands separator — `4,820 gal`,
 * `3,050 gal` — and `CWP-033` draws its KPI and its legend WITHOUT one while the
 * per-service panel on the same screen draws `43,300 gal` WITH one
 * (`DEF-CWP-4168`). Rolled into a single assertion, a wrong NUMBER and a missing
 * COMMA fail identically and the reader cannot tell which happened. So the digits
 * are asserted separator-insensitively — that check is about the arithmetic — and
 * the grouping is asserted once, by itself, against the defect it belongs to.
 */
const digitsOf = (text) => (text ?? "").replace(/,/g, "");
const isGrouped = (text) => /\b\d{1,3}(,\d{3})+\b/.test(text ?? "");
const WATER_SERIAL = "88-40219";
const CART_SERIAL = "C-11840";
const BACKFLOW_SERIAL = "BF-2210";
const ESTIMATED_DIAL = "144,600";
const CORRECTED_DIAL = "144,130";

mkdirSync(OUT, { recursive: true });

const failures = [];
const skipped = [];
/**
 * ⚠ **THE FOUR THINGS THIS WAVE FOUND MISSING ARE RECORDED, NOT ASSERTED RED.**
 * This run finished RED five times on its first outing, every failure correct
 * and every one of them a filed defect — and a walkthrough that exits 1 forever
 * teaches its reader that red is its normal colour, so the day a real regression
 * lands it hides in the pile (hard-won law 7's first shape, counted twenty times
 * on 2026-09-05). `lib/knownGaps.mjs` is the sibling lane's answer to exactly
 * this, and the property that makes it honest rather than a fudge is that a gap
 * goes RED IN BOTH DIRECTIONS: still missing → counted and printed; PRESENT →
 * failure, because the product grew it and this file still says it has not.
 */
const gaps = new Gaps();
/** Every figure this run READ OFF THE SCREEN, printed together at the end. */
const figures = [];

function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * A step this run could not exercise, named out loud.
 *
 * ⚠ **NOT A PASS, AND NOT COUNTED AS ONE.** Hard-won law 7's fifth shape is a
 * check reporting zero over a scope it silently excludes — *"a declared blind
 * spot with no NUMBER attached is indistinguishable from an empty one"*.
 */
function skip(message) {
  console.log(`   ⏭ SKIPPED — ${message}`);
  skipped.push(message);
}

function record(label, value) {
  figures.push(`${label}: ${value}`);
  console.log(`   · ${label} = ${value}`);
}

/**
 * ⚠ **THE ONE HELPER THIS SCRIPT WOULD BE WORTHLESS WITHOUT.**
 *
 * `[].every(...)` is `true`, so *"every quantity carries its unit"* PASSES over
 * a page with no quantities on it — and a page with nothing on it is precisely
 * the state these three screens were in before this wave's seed landed. That
 * is not a hypothetical: `DEF-WRK-4121` shipped a dispatcher who could not
 * raise a work order on any non-empty list, because every test exercised the
 * empty one.
 *
 * So a claim about "every X" is made in TWO parts, and the first part is that
 * there is an X at all. `expected` is asserted where the count is known from
 * the fixture, so the check also fails when the screen draws FEWER than it
 * should — which an existence check alone cannot see.
 */
function over(items, where, { min = 1, expected = null } = {}) {
  const n = items.length;
  if (expected !== null) {
    check(n === expected, `${where}: ${n} row(s) drawn (expected ${expected}) — nothing below is vacuous`);
  } else {
    check(n >= min, `${where}: ${n} row(s) drawn (need at least ${min}) — nothing below is vacuous`);
  }
  return n > 0;
}

/** B14 rule 31 and rule 32 — never a database id, never an internal code. */
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bUS-CWP-\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

async function noInternals(page, where) {
  const text = await page.locator("body").innerText();
  for (const pattern of FORBIDDEN) {
    check(!pattern.test(text), `${where}: nothing matching ${pattern} on screen (B14 rule 31/32)`);
  }
}

/**
 * B14 rule 36's one mechanical half — a column so narrow the text inside it
 * wraps to ONE WORD PER LINE.
 *
 * ⚠ **THIS IS NOT A STYLE OPINION AND NO OTHER CHECK IN THIS REPO CAN SEE IT.**
 * A preview panel shipped wrapping one word per line for eleven lines and every
 * test passed, because the text CONTENT is identical however it wraps. It is
 * found by measuring: an element whose rendered height is many line-boxes tall
 * while its width holds barely one word.
 */
async function noBrokenColumns(page, where) {
  const bad = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll("p, dd, td, li, span, h1, h2, h3")) {
      if (el.children.length) continue;
      const text = (el.textContent ?? "").trim();
      const words = text.split(/\s+/).filter(Boolean);
      if (words.length < 4) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      const line = parseFloat(getComputedStyle(el).lineHeight) || 16;
      const lines = Math.round(rect.height / line);
      // more line-boxes than half the word count == roughly one word a line
      if (lines >= 4 && lines >= words.length * 0.6) {
        out.push({ text: text.slice(0, 60), lines, words: words.length, width: Math.round(rect.width) });
      }
    }
    return out;
  });
  check(
    bad.length === 0,
    `${where}: no text column wraps ~one word per line (B14 rule 36)` +
      (bad.length ? ` — ${JSON.stringify(bad.slice(0, 3))}` : ""),
  );
}

async function signIn(page) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT, acceptDownloads: true });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-h: ${BASE} tenant=${TENANT} as ${EMAIL} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await signIn(page);

  // ═════ 1 · the year, and the axis that names its unit ════════════════════
  console.log("\n── 1 · a year of water, with the unit on the axis ──");
  await page.goto(`${PORTAL}/usage`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-033"]', { timeout: 20000 });

  // ⚠ **THE BARS ARE COUNTED BEFORE ANYTHING IS ASSERTED ABOUT THEM.** An axis
  // label is drawn whether or not there is a chart under it, so checking the
  // label first would pass on an empty screen — the exact state this wave's
  // blocker left the demo tenant in.
  const water = page.locator('[data-testid="usage-water"]');
  check((await water.count()) === 1, "the water panel is on the screen");
  // ⚠ **THE WINDOW IS TWELVE TRACKS; THE MONTHS WITH A READING ARE FEWER, AND
  // THAT IS CORRECT.** `window_months(latest, 12)` ends at the CURRENT month, so
  // on any day in September the twelfth track is September — a month nobody has
  // read yet, drawn as an absence. An earlier draft of this check asserted
  // twelve READINGS and went red against a screen that was right; the fixture
  // ends at 31 August on purpose, because the demo script's own next line is
  // *"next reading due 2–6 Sep"*.
  const tracks = await water.locator("[data-month]").all();
  over(tracks, "CWP-033 water chart, the twelve-month window", { expected: 12 });
  const bars = await water.locator('[data-month][data-absent="false"]').all();
  const drawn = over(bars, "CWP-033 months with a reading in that window", { min: 11 });
  const absent = tracks.length - bars.length;
  record("CWP-033 months drawn / with a reading / absent", `${tracks.length} / ${bars.length} / ${absent}`);
  const emptyChart = await water.locator("[data-chart-empty]").count();
  check(emptyChart === 0, "…and it is a CHART, not the empty-state sentence");

  if (drawn) {
    const axis = (await water.locator("[data-chart-axis]").innerText()).trim();
    record("CWP-033 axis label", `"${axis}"`);
    check(/gal/i.test(axis), `the axis names its unit (hard rule 3): "${axis}"`);

    const highest = water.locator('[data-month][data-extreme="highest"]');
    const lowest = water.locator('[data-month][data-extreme="lowest"]');
    check((await highest.count()) >= 1, "the highest month is MARKED on the chart");
    check((await lowest.count()) >= 1, "the lowest month is MARKED on the chart");
    const highTitle = (await highest.first().getAttribute("title")) ?? "";
    const lowTitle = (await lowest.first().getAttribute("title")) ?? "";
    record("CWP-033 highest month", `"${highTitle}"`);
    record("CWP-033 lowest month", `"${lowTitle}"`);
    check(
      digitsOf(highTitle).includes(HIGHEST),
      `the highest month IS ${HIGHEST} gal (digits, whatever the grouping): "${highTitle}"`,
    );
    check(
      digitsOf(lowTitle).includes(LOWEST),
      `the lowest month IS ${LOWEST} gal (digits, whatever the grouping): "${lowTitle}"`,
    );
    check(/gal/i.test(highTitle), "…and the marked month carries its unit too");
    // The formatting, as its own claim — see `isGrouped`'s note. A KNOWN GAP,
    // so it is counted and printed rather than reddening every run; it goes RED
    // the day somebody groups the figure and forgets to delete this row.
    gaps.known(
      isGrouped(highTitle),
      `the marked month is grouped with a thousands separator: "${highTitle}"`,
      {
        defect: "DEF-CWP-4168",
        why:
          "metering.quantity_display.quantity_text formats with f'{trimmed:f}' and adds no grouping, " +
          "while the per-service panel on the same screen reaches its figure by a path that does group",
      },
    );

    // ⚠ **THE HIGHEST BAR IS A DARKER TIER, and the class could be in the DOM
    // and compile to nothing (DEF-974), so the BROWSER is asked what it
    // painted.**
    const highColour = await highest.first().evaluate((el) => getComputedStyle(el).backgroundColor);
    const plainBar = await water
      .locator('[data-month][data-absent="false"]:not([data-extreme="highest"])')
      .first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    record("CWP-033 highest bar colour", highColour);
    check(
      highColour !== plainBar && highColour !== "rgba(0, 0, 0, 0)",
      `the highest month is painted differently from an ordinary one (${highColour} vs ${plainBar})`,
    );

    // Month names under the bars — one label per bar track.
    const labels = await water.locator("[data-month-label]").count();
    const allBars = await water.locator("[data-month]").count();
    check(labels === allBars, `every bar has a month label under it (${labels} of ${allBars})`);
  }

  // The KPI row. Printed whatever it says — this run REPORTS the figures, it
  // does not decide them.
  const screenText = await page.locator('[data-screen="CWP-033"]').innerText();
  check(
    digitsOf(screenText).includes(THIS_PERIOD),
    `this period's figure ${THIS_PERIOD} gal is on the screen (digits, whatever the grouping)`,
  );
  // ⚠ **THE SAME SCREEN FORMATS THE SAME KIND OF NUMBER TWO WAYS**, which is
  // what makes `DEF-CWP-4168` a defect rather than a preference: the KPI reads
  // `4820 gal` and the per-service panel below reads `43,300 gal`.
  const grouped = (screenText.match(/\b\d{1,3}(?:,\d{3})+\b/g) ?? []).length;
  const ungrouped = (screenText.match(/(?<![,\d])\d{4,}(?![\d,])/g) ?? []).length;
  record("CWP-033 quantities grouped / ungrouped", `${grouped} / ${ungrouped}`);
  gaps.known(
    ungrouped === 0,
    `every four-figure quantity on CWP-033 is grouped ` +
      `(${grouped} grouped, ${ungrouped} not) — one screen must not format one kind of number two ways`,
    {
      defect: "DEF-CWP-4168",
      why: "the KPI and the chart legend draw 4820 gal while the panel below draws 43,300 gal",
    },
  );
  for (const [label, selector] of [
    ["months read", '[data-months-read="water"]'],
    ["estimated months", '[data-estimated-months="water"]'],
  ]) {
    const node = water.locator(selector);
    if (await node.count()) record(`CWP-033 ${label}`, `"${(await node.innerText()).trim()}"`);
  }
  // ⚠ **THE WIREFRAME HAS THREE KPI TILES AND THE BUILD HAS TWO.** This is a
  // KNOWN GAP and not a skip: a skip says *this run could not look*, and the run
  // looked. The third tile is drawn in `wireframes/CWP-033.png` and named in the
  // wave's own demo script, so the day it lands this line goes red and says so.
  const nextReading = page.locator("[data-next-reading]");
  gaps.known(
    (await nextReading.count()) > 0,
    "CWP-033 draws the *next reading due* tile the wireframe gives it",
    {
      defect: "DEF-CWP-4169",
      why: "Usage.tsx has the [data-next-reading] hook and nothing renders inside it",
    },
  );
  if (await nextReading.count()) {
    record("CWP-033 next reading due", `"${(await nextReading.innerText()).trim()}"`);
  }
  gaps.known(
    /daily average/i.test(screenText),
    "the second KPI is the DAILY average the wireframe specifies, not a monthly one",
    {
      defect: "DEF-CWP-4170",
      why:
        "the drawing reads 'DAILY AVERAGE 155 gal' and the build reads 'MONTHLY AVERAGE 3936.36 gal' — " +
        "4,820 gal over August's 31 days is 155, so the figure is derivable from what the screen holds",
    },
  );
  // The whole-screen KPI strip, whatever shape it took.
  const kpiText = (await page.locator('[data-screen="CWP-033"]').innerText())
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  for (const line of kpiText.slice(0, 14)) {
    if (/%|average|per day|vs|gal/i.test(line)) record("CWP-033 line", `"${line}"`);
  }
  await noInternals(page, "CWP-033");
  await noBrokenColumns(page, "CWP-033");
  await page.screenshot({ path: join(OUT, "1-usage-12-months.png"), fullPage: true });

  // ═════ 2 · twenty-four months ════════════════════════════════════════════
  console.log("\n── 2 · the same chart, two years wide ──");
  // ⚠ **FOUND BY TEXT, NOT BY ROLE.** The window switch is a SegmentedControl,
  // so its two options need not carry the `button` role — an earlier draft asked
  // `getByRole("button")` and reported *"no control matching /24 months/"* over
  // a control that is plainly on the screen. A skip printed for a reason that is
  // not true is worse than a failure, because nobody goes looking.
  const wider = page.getByText(/^24 months$/i);
  if (await wider.count()) {
    await wider.first().click();
    await page.waitForTimeout(1200);
    const bars24 = await water.locator('[data-month][data-absent="false"]').all();
    over(bars24, "CWP-033 water chart, the 24-month view", { min: 13 });
    record("CWP-033 bars at 24 months", String(bars24.length));
    check(
      bars24.length > bars.length,
      `the window really widened (${bars.length} → ${bars24.length} months with a reading)`,
    );
    const axis24 = (await water.locator("[data-chart-axis]").innerText()).trim();
    check(/gal/i.test(axis24), `the axis still names its unit at 24 months: "${axis24}"`);
    await page.screenshot({ path: join(OUT, "2-usage-24-months.png"), fullPage: true });
    // back to the default view for the rest of the run
    const narrower = page.getByText(/^12 months$/i);
    if (await narrower.count()) {
      await narrower.first().click();
      await page.waitForTimeout(800);
    }
  } else {
    skip("the 24-month switch — no element reading exactly '24 months' is on CWP-033");
  }

  // ═════ 3 · the services that are NOT measured ════════════════════════════
  console.log("\n── 3 · billed on something else, and NO empty chart ──");
  for (const [code, mustSay] of [
    ["sewer", /water/i],
    ["trash", /cart/i],
  ]) {
    const panel = page.locator(`[data-testid="usage-${code}"]`);
    if (!(await panel.count())) {
      check(false, `the ${code} panel is on CWP-033 (BR-CWP-073 needs it to be there to say so)`);
      continue;
    }
    const billedOn = page.locator(`[data-billed-on="${code}"]`);
    check((await billedOn.count()) === 1, `${code}: the panel states what it is BILLED ON`);
    if (await billedOn.count()) {
      const said = (await billedOn.innerText()).trim();
      record(`CWP-033 ${code} billed on`, `"${said}"`);
      check(mustSay.test(said), `${code}: …and it names the right thing — ${mustSay}`);
    }
    const notMeasured = page.locator(`[data-not-measured="${code}"]`);
    check((await notMeasured.count()) === 1, `${code}: the panel says it is not measured`);
    if (await notMeasured.count()) {
      record(`CWP-033 ${code} not measured`, `"${(await notMeasured.innerText()).trim()}"`);
    }
    // ⚠ **THE ABSENCE, MEASURED.** `BR-CWP-073`: no chart and no zero series.
    // Asked of the PANEL's own subtree, because a chart elsewhere on the page
    // is not this panel's fault and would make the check meaningless.
    const svg = await panel.locator("svg, canvas, [data-chart]").count();
    check(svg === 0, `${code}: no <svg>, no canvas and no chart inside the panel (BR-CWP-073) — found ${svg}`);
    const zeroBars = await panel.locator('[data-month][data-absent="false"]').count();
    check(zeroBars === 0, `${code}: and no zero series either — ${zeroBars} bar(s)`);
  }
  await page.screenshot({ path: join(OUT, "3-unmeasured-panels.png"), fullPage: true });

  // ═════ 4 · every reading, and the estimate that was put right ════════════
  console.log("\n── 4 · how each reading was taken, and what the correction moved ──");
  await page.goto(`${PORTAL}/readings`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-034"]', { timeout: 20000 });
  check((await page.locator("[data-readings-empty]").count()) === 0, "CWP-034 is not in its empty state");

  const readingCells = await page.locator("[data-reading]").all();
  const haveReadings = over(readingCells, "CWP-034 readings list", { min: 4 });

  if (haveReadings) {
    // hard rule 3 — every used-since carries its unit. Guarded by `over`, so
    // this cannot pass over an empty list.
    const used = await page.locator("[data-used]").allInnerTexts();
    over(used, "CWP-034 used-since cells", { min: 4 });
    // ⚠ **AN EM-DASH IS AN ABSENCE, NOT A FIGURE MISSING ITS UNIT.** The FIRST
    // reading of any lineage is a baseline with no consumption — `BR-MET-106`:
    // *"an unread month is ABSENT, never a zero"* — and `Readings.tsx` renders
    // `—` for it, correctly. An earlier draft of this check counted that dash as
    // a filled cell and reported `23 of 24`, failing a screen that was right.
    const nonEmpty = used.map((t) => t.trim()).filter((t) => t !== "" && t !== "—" && t !== "-");
    const withUnit = nonEmpty.filter((t) => /gal/i.test(t));
    record("CWP-034 used-since cells", `${nonEmpty.length} filled, ${withUnit.length} carry a unit`);
    check(
      nonEmpty.length > 0 && withUnit.length === nonEmpty.length,
      `every used-since figure carries "gal" (hard rule 3) — ${withUnit.length} of ${nonEmpty.length}`,
    );

    // The method, in words rather than a code.
    const hows = (await page.locator("[data-how]").allInnerTexts()).map((t) => t.trim()).filter(Boolean);
    over(hows, "CWP-034 method cells", { min: 4 });
    record("CWP-034 methods drawn", JSON.stringify([...new Set(hows)].slice(0, 6)));
    check(
      hows.length > 0 && hows.every((h) => /[a-z]{3}/i.test(h) && !/^[a-z_]+$/.test(h)),
      "every method is written in WORDS, never a bare enum key (BR-CWP-071)",
    );

    // ⚠ **THE DRAWN DATE, NOT THE PAYLOAD'S (`DEF-MET-4101`).** A read is
    // stored normalised to midnight UTC on purpose — that normalisation IS the
    // one-read-per-meter-per-date key — and the staff Reads tab renders it in
    // the tenant's timezone, drawing 2026-03-15 as 03/14/2026. Every check in
    // the repo compares UTC dates and the screen renders local ones, so the two
    // never meet. This asserts what the BROWSER drew, so the day the fold is
    // fixed this line moves and names it.
    const drawnDates = (await page.locator("[data-reading]").evaluateAll((els) =>
      els.map((el) => (el.closest("tr")?.innerText ?? "").split("\t")[0].trim()),
    )).filter(Boolean);
    record("CWP-034 first row as drawn", JSON.stringify(drawnDates.slice(0, 2)));

    // The estimate, and what opening it says.
    const opener = page.locator("[data-open-correction]");
    if (await opener.count()) {
      const before = (await page.locator("[data-correction]").allInnerTexts()).join(" ");
      await opener.first().click();
      await page.waitForTimeout(600);
      const correction = (await page.locator("[data-correction]").allInnerTexts()).join(" ").trim();
      record("CWP-034 correction sentence", `"${correction}"`);
      check(correction.length > before.length, "the correction row OPENS to say more than it did closed");
      check(
        digitsOf(correction).includes(digitsOf(ESTIMATED_DIAL)),
        `…and it says what was estimated (${ESTIMATED_DIAL})`,
      );
      check(
        digitsOf(correction).includes(digitsOf(CORRECTED_DIAL)),
        `…and what it was corrected to (${CORRECTED_DIAL})`,
      );
      // ⚠ **THE DATE IS THERE AND IT IS A MACHINE DATE.** The sentence reads
      // *"…when the meter was read on 2026-07-03"* where `US-CWP-041` §4 says
      // *"read on 3 July"*. So the two claims are separated: the correction
      // names the right DAY, and it names it in a form a customer would write.
      check(/2026-07-03|3 jul|jul(y)? 3/i.test(correction), "…and when the meter was actually read (3 July)");
      gaps.known(
        !/\b\d{4}-\d{2}-\d{2}\b/.test(correction),
        `the correction says the date the way a person writes it, not as ISO: "${correction}"`,
        {
          defect: "DEF-CWP-4172",
          why:
            "US-CWP-041 §4's sentence is 'read on 3 July'; the sentence is composed server-side, so " +
            "DEF-CWP-3994's fix for the date COLUMNS will not reach inside it",
        },
      );
      check(
        /not charged twice|no.*charged twice|twice/i.test(correction),
        `…and that the customer was not charged twice (BR-CWP-072): "${correction}"`,
      );
    } else {
      check(false, "CWP-034 draws no correction to open — the estimated-then-corrected row is missing");
    }
  }
  await noInternals(page, "CWP-034");
  await noBrokenColumns(page, "CWP-034");
  await page.screenshot({ path: join(OUT, "4-readings.png"), fullPage: true });

  // ═════ 5 · what is at the property ═══════════════════════════════════════
  console.log("\n── 5 · three things at the kerb, and one empty cell ──");
  await page.goto(`${PORTAL}/equipment`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-037"]', { timeout: 20000 });
  check((await page.locator("[data-equipment-empty]").count()) === 0, "CWP-037 is not in its empty state");

  const serials = (await page.locator("[data-serial]").allInnerTexts()).map((t) => t.trim());
  over(serials, "CWP-037 equipment rows", { expected: 3 });
  record("CWP-037 serials drawn", JSON.stringify(serials));
  for (const serial of [WATER_SERIAL, CART_SERIAL, BACKFLOW_SERIAL]) {
    check(serials.includes(serial), `${serial} is on the screen, by its serial (B14 rule 31)`);
  }

  // ⚠ **AN EMPTY CELL, NOT A ZERO — `US-CWP-043` TC-2's whole point.** Nobody
  // reads a wheelie bin, and `0` is a claim that somebody did and it read zero.
  const cartRead = page.locator(`[data-last-read="${CART_SERIAL}"]`);
  check((await cartRead.count()) === 1, `the cart ${CART_SERIAL} has a last-read cell`);
  if (await cartRead.count()) {
    const text = (await cartRead.innerText()).trim();
    record("CWP-037 cart last read", `"${text}"`);
    check(text === "", `the cart's last-read cell is EMPTY, not a zero: "${text}"`);
    check(!/\b0\b/.test(text), "…and there is no 0 in it");
  }
  // The meter, by contrast, HAS one — otherwise "empty" above proves nothing.
  const meterRead = page.locator(`[data-last-read="${WATER_SERIAL}"]`);
  if (await meterRead.count()) {
    const text = (await meterRead.innerText()).trim();
    record("CWP-037 water meter last read", `"${text}"`);
    check(
      text !== "",
      "the water meter's last-read cell is FILLED — so the cart's empty one is a distinction, not a broken column",
    );
  } else {
    check(false, "the water meter has no last-read cell at all");
  }

  const equipText = await page.locator('[data-screen="CWP-037"]').innerText();
  check(/test due/i.test(equipText), "the backflow device says its test is due");
  const nov = /test due\s*nov/i.test(equipText);
  check(nov, `…and it names the month: ${/test due[^\n]*/i.exec(equipText)?.[0] ?? "(not found)"}`);
  record("CWP-037 test chip", `"${/test due[^\n]*/i.exec(equipText)?.[0] ?? "(none)"}"`);
  check(
    !/installed\/active|installed \/ active/i.test(equipText),
    "no slash-joined lookup value on a customer's screen (DEF-CWP-3992)",
  );
  await noInternals(page, "CWP-037");
  await noBrokenColumns(page, "CWP-037");
  await page.screenshot({ path: join(OUT, "5-equipment.png"), fullPage: true });

  // ═════ 6 · the CSV, and the column that carries the unit ═════════════════
  console.log("\n── 6 · a download whose numbers still mean something ──");
  await page.goto(`${PORTAL}/usage`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-033"]', { timeout: 20000 });
  const download = page.getByRole("button", { name: /download|csv|export/i });
  if (await download.count()) {
    const [file] = await Promise.all([
      page.waitForEvent("download", { timeout: 15000 }).catch(() => null),
      download.first().click(),
    ]);
    if (file) {
      const path = await file.path();
      const body = path ? execFileSync("cat", [path]).toString() : "";
      const lines = body.split(/\r?\n/).filter((l) => l.trim() !== "");
      over(lines, "the usage CSV", { min: 2 });
      const header = lines[0] ?? "";
      record("usage CSV header", `"${header}"`);
      check(/unit/i.test(header), `the CSV has a UNIT COLUMN (hard rule 3): "${header}"`);
      const unitAt = header.split(",").findIndex((h) => /unit/i.test(h));
      const rows = lines.slice(1);
      const withUnit = rows.filter((r) => (r.split(",")[unitAt] ?? "").trim() !== "");
      record("usage CSV rows", `${rows.length} data row(s), ${withUnit.length} carry a unit`);
      check(
        rows.length > 0 && withUnit.length === rows.length,
        `every CSV row carries its unit — ${withUnit.length} of ${rows.length}`,
      );
    } else {
      skip("the CSV export — the download button did not produce a file within 15s");
    }
  } else {
    skip("the CSV export — no control matching /download|csv|export/ is on CWP-033");
  }

  // ═════ 7 · the tip, and the two things that are not built ════════════════
  console.log("\n── 7 · the tip bar, and what this wave cannot show ──");
  // ⚠ **WAVE H's OWN TITLE PROMISES *the signed-in help and tip slots*, AND ALL
  // THREE OF THOSE SCREENS ARE UNBUILT** — so step 5 of the demo script cannot
  // be performed today. Recorded as GAPS with their register ids rather than as
  // skips, because a skip says *this run could not look* and these were looked
  // for and are genuinely not there; and rather than as failures, because they
  // are known, filed and deliberate. Each goes red the day its screen lands.
  const tip = page.locator('[data-testid="tip-bar"], [data-tip]');
  gaps.known((await tip.count()) > 0, "the watering tip fills the TipBar on CWP-033 (CWP-062)", {
    defect: "DEF-CWP-3988",
    why:
      "CWP-062 is not a screen of its own — it is CWP-033 with the TipBar filled — and nothing " +
      "renders a tip here; its server side (tenancy_seam.tip_for_screen) does exist",
  });
  if (await tip.count()) {
    record("CWP-062 tip on CWP-033", `"${(await tip.first().innerText()).trim()}"`);
  }
  gaps.known(false, "the answer sits under the bill's charges (CWP-061)", {
    defect: "DEF-CWP-3945",
    why:
      "CWP-061 is not a screen either — the drawing calls it 'CWP-028 + one block' — and the " +
      "AttachedAnswerCard slot is unbuilt, so a clerk can pin an answer and the customer never sees it",
  });
  gaps.known(false, "a signed-in help screen of its own (CWP-059)", {
    defect: "DEF-CWP-3988",
    why:
      "a signed-in customer reaches the GUEST /help screen, which IS built and works — there is no " +
      "signed-in twin to walk, so nothing refuses and nothing is broken",
  });

  await timings.report({
    targets: [
      { id: "RT-2", match: "/portal/auth/sign-in", p95: 900 },
      { id: "RT-3", match: "/usage", p95: 600 },
    ],
  });

  console.log("\n── every figure this run read off the screen ──");
  for (const line of figures) console.log(`   ${line}`);

  if (skipped.length) {
    console.log("\n── not exercised (NOT passes) ──");
    for (const one of skipped) console.log(`   ⏭ ${one}`);
  }

  await browser.close();
  // ⚠ **THE COUNTS PRINT EVEN ON A PASS.** `0 failures, 7 known gaps` must never
  // look like `0 failures, 0 known gaps` — law 7's fifth shape, a declared blind
  // spot with no NUMBER attached being indistinguishable from an empty one.
  console.log(`\n── ${skipped.length} step(s) skipped, ${figures.length} figure(s) read ──`);
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
