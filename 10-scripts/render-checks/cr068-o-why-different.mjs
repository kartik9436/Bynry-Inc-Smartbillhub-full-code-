/**
 * RENDERED-OUTPUT CHECK — CR-068 wave O, "Why this bill is different, and the
 * alert that has no trigger", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output, and nine defects in one day were found this way and by
 * nothing else. PO ruling 2026-09-03: *"ensure you do web walkthorugh before
 * you sign off the user story or build"*.
 *
 * ╔═══════════════════════════════════════════════════════════════════════════╗
 * ║ THE ONE THING THIS FILE IS FOR: MAKING THE SCREEN CHANGE ITS ANSWER       ║
 * ╚═══════════════════════════════════════════════════════════════════════════╝
 *
 * `CWP-030` explains why a bill differs from the last one. **A screen that
 * always says the same thing would pass any single-case test**, and the seeded
 * tenant makes that trap easy to fall into: `seed_portal_demo` bills 50
 * accounts, and **all 49 comparisons on the whole tenant went UP**. Assert
 * *cost more*, find it, pass — over a screen that could be printing a
 * constant. That is `CLAUDE.md` hard-won law 7's *"a check that cannot fail"*,
 * and wave I hit exactly this: its cheaper-to-stop-or-close screen had to be
 * driven THREE times with different inputs before anyone could say it computed
 * anything.
 *
 * So this drives the same screen **four times, at four addresses**, and
 * asserts the answer is DIFFERENT each time:
 *
 *     BL-O-2606-0100   first bill   no comparison at all
 *     BL-O-2608-0141   ↑  +$3.74    "cost more"
 *     BL-O-2609-0143   ↓  −$3.74    "cost less"
 *     BL-O-2610-0145   →   $0.00    "cost the same"
 *
 * ⚠ **AND THE LEVEL BILL IS THE LOAD-BEARING ONE.** October totals exactly
 * what September did, so the headline is *cost the same* — **but two of its
 * components are not zero**: water rises `+$5.00` and the tax falls `−$5.00`,
 * and they cancel. A screen that derived its breakdown FROM the headline
 * difference — the obvious wrong implementation, and one that would sail
 * through the rise and the fall above — draws nothing here, or draws four
 * zeros. This run asserts two real movements over a total that did not move.
 *
 * ⚠ **THE SUM IS CHECKED AS ARITHMETIC ON THE PRINTED STRINGS**, not against
 * the server's own figure. `BR-CWP-046` allows NO tolerance (`US-CWP-035`
 * TC-3, `J38` step 3: *"a tolerance here would defeat the whole story"*), and
 * the only version of that rule a customer can act on is *the numbers on the
 * page add up to the headline on the page*. Reading both off the DOM is the
 * one way to check it that a wrong server cannot satisfy.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cwpo
 *   export DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_cwpo?sslmode=disable"
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py seed_portal_demo
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 10-scripts/render-checks/cr068-o-fixture.py
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8149 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4349 API_PROXY_TARGET=http://127.0.0.1:8149 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4349 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-o-why-different.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ── WHAT IT CLICKS (the wave O demo script, 10-execution-plan.md) ─────────
 *   1  The bill that ROSE — the headline names `$3.74`, every component line
 *      is read off the screen, and the four of them are SUMMED and compared
 *      with the printed difference. The AGAINST LAST AUGUST panel draws two
 *      bars, and `4,171 → 4,820 gal` carries its unit on both ends.
 *   2  The bill that FELL — the same magnitude with the opposite sign and the
 *      opposite word. Every component is the negative of step 1's.
 *   3  The bill that is LEVEL — `$0.00` and *cost the same*, over TWO
 *      components that moved and cancelled.
 *   4  The FIRST bill — no comparison at all, and no difference figure
 *      anywhere on the page. Not a comparison against zero.
 *   5  `CWP-036` *your usage looks high* — NOT BUILT, and nothing fires it.
 *      The screen register has no address for it and none of the addresses
 *      the drawing suggests serves it. Recorded as a known gap, not built.
 *
 * ── WHAT IT DOES NOT DO ──────────────────────────────────────────────────
 * It does not perturb a component to watch the tie-out refuse. That case is
 * `test_us_cwp_035_tc3` in `06-backend/tests/test_us_cwp_035_comparison.py`,
 * it runs the seam directly, and reproducing it here would need this file to
 * write a bill whose stored total disagrees with its own lines — which
 * `cr068-o-fixture.py` deliberately refuses to plant.
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
 * The path is TESTED rather than trusted (law 7's second shape, a check
 * structurally incapable of failing). Same eight lines as `cr068-h`/`cr068-i`.
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

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4349";
const TENANT = process.env.SMOKE_TENANT ?? "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "o-why-different@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Elm-Street-1408";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-o";
const VIEWPORT = { width: 1440, height: 1000 };
const PORTAL = `${BASE}/${TENANT}/portal`;
const API = `${BASE}/api/${TENANT}/portal`;

/**
 * `cr068-o-fixture.py`'s own constants — the two files must agree, and the
 * FIGURES are the execution plan's rather than this file's invention.
 *
 * The four component shares the PO ruled on (`OQ-CWP-1569`, *"(a) list every
 * reason with its share"*) are `+$8.83`, `$0.00`, `+$4.29`, `−$9.38`, and the
 * plan's own worked headline is `$142.18 − $138.44 = +$3.74`.
 */
const FIRST_BILL = "BL-O-2606-0100";
const ROSE_BILL = "BL-O-2608-0141";
const FELL_BILL = "BL-O-2609-0143";
const LEVEL_BILL = "BL-O-2610-0145";

/**
 * The three cases, and what each must PRINT.
 *
 * ⚠ **`components` IS AN EXACT MAP, NOT A SUBSET CHECK.** `every()` over a
 * list that came back empty is `true` (law 7), so the run asserts the COUNT
 * first and then each named share, and a bucket that appeared or vanished
 * fails on the count rather than passing silently.
 */
const CASES = [
  {
    name: "the bill that ROSE",
    number: ROSE_BILL,
    direction: "cost_more",
    difference: "+$3.74",
    headlineWord: /cost .* more/i,
    total: "$142.18",
    prior: "$138.44",
    // A bucket that did NOT move reads the WORD `unchanged`, never `+$0.00` —
    // the PO's own fourth line was *trash cart charge unchanged*.
    components: {
      water_usage: "+$8.83",
      trash_base: "unchanged",
      water_discount: "+$4.29",
      bill_tax: "-$9.38",
    },
    // August pairs with August 2025, which the account HAS — so the panel draws.
    yearPanel: true,
  },
  {
    name: "the bill that FELL",
    number: FELL_BILL,
    direction: "cost_less",
    difference: "-$3.74",
    headlineWord: /cost .* less/i,
    total: "$138.44",
    prior: "$142.18",
    components: {
      water_usage: "-$8.83",
      trash_base: "unchanged",
      water_discount: "-$4.29",
      bill_tax: "+$9.38",
    },
    // September 2026 has no reading yet — nobody has walked the meter — so the
    // pair cannot be formed and the panel is correctly ABSENT (BR-CWP-093).
    yearPanel: false,
  },
  {
    name: "the bill that is LEVEL",
    number: LEVEL_BILL,
    direction: "cost_the_same",
    difference: "$0.00",
    headlineWord: /cost the same/i,
    total: "$138.44",
    prior: "$138.44",
    // ⚠ THE WHOLE POINT: the total did not move and TWO components did.
    components: {
      water_usage: "+$5.00",
      trash_base: "unchanged",
      water_discount: "unchanged",
      bill_tax: "-$5.00",
    },
    yearPanel: false,
  },
];

mkdirSync(OUT, { recursive: true });

const failures = [];
const skipped = [];
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
 * ⚠ **NOT A PASS, AND NOT COUNTED AS ONE.** Law 7's fifth shape is a check
 * reporting zero over a scope it silently excludes — *"a declared blind spot
 * with no NUMBER attached is indistinguishable from an empty one"*.
 */
function skip(message) {
  console.log(`   ⏭ SKIPPED — ${message}`);
  skipped.push(message);
}

function record(what, value) {
  figures.push([what, value]);
  console.log(`   · ${what}: ${value}`);
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
 * A raw machine date on a customer's screen.
 *
 * ⚠ **THE TENANT'S OWN SETTING IS `MM/DD/YYYY`**, and every wave walked on the
 * night of 2026-09-05 found screens printing `2026-09-06` instead — waves F,
 * G, I, L and M each found their own set. This counts what is left on `CWP-030`
 * so the answer is a MEASUREMENT rather than an impression.
 */
const ISO_DATE = /\b\d{4}-\d{2}-\d{2}\b/g;
async function machineDates(page, where) {
  const text = await page.locator("body").innerText();
  const hits = text.match(ISO_DATE) ?? [];
  if (hits.length) {
    record(`${where} raw ISO dates the screen drew`, `${hits.length} — ${hits.slice(0, 4).join(", ")}`);
  }
  return hits;
}

/**
 * `+$8.83` → `8.83`; `-$9.38` → `-9.38`; `unchanged` → `0`.
 *
 * ⚠ **PARSED FROM THE PRINTED STRING AND FROM NOTHING ELSE.** The whole value
 * of the tie-out check below is that it uses the numbers a CUSTOMER can see,
 * so it must not reach for the payload the screen was built from.
 */
function moneyToNumber(printed) {
  const trimmed = (printed ?? "").trim();
  if (/^unchanged$/i.test(trimmed)) return 0;
  const match = trimmed.match(/^([+-]?)\$([\d,]+\.\d{2})$/);
  if (!match) return null;
  const sign = match[1] === "-" ? -1 : 1;
  return sign * Number(match[2].replace(/,/g, ""));
}

/** Every money string on the page must show exactly two decimals (hard rule 2). */
const MONEY_ON_SCREEN = /\$\s?-?[\d,]+(?:\.\d+)?/g;
function badlyScaledMoney(text) {
  return (text.match(MONEY_ON_SCREEN) ?? []).filter((one) => {
    const decimals = one.split(".")[1];
    return decimals === undefined || decimals.length !== 2;
  });
}

async function signIn(page) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
}

/** Ask the product's own API, through the session the browser is holding. */
async function api(page, path) {
  return page.evaluate(async (url) => {
    const answer = await fetch(url, { credentials: "include" });
    return { status: answer.status, body: await answer.text() };
  }, `${API}/${path}`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const timings = attachTimings(context);
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`\ncr068-o · ${BASE} · ${TENANT} · ${EMAIL}`);
  await signIn(page);
  let allDates = [];

  // ═══ 1-3 · the same screen, three bills, three different answers ═════════
  for (const [index, kase] of CASES.entries()) {
    console.log(`\n── ${index + 1} · CWP-030 · ${kase.name} (${kase.number}) ──`);
    await page.goto(`${PORTAL}/bills/${kase.number}/comparison`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-screen="CWP-030"]', { timeout: 20000 });
    await page.screenshot({
      path: join(OUT, `${index + 1}-cwp-030-${kase.direction}.png`),
      fullPage: true,
    });

    // ── the headline, which is the half that deflects the phone call ──
    const headline = page.locator("[data-direction]");
    check((await headline.count()) === 1, `${kase.number}: exactly one headline sentence`);
    const direction = await headline.getAttribute("data-direction");
    const headlineText = (await headline.innerText()).trim();
    record(`${kase.number} headline`, `"${headlineText}"`);
    check(
      direction === kase.direction,
      `${kase.number}: direction is ${kase.direction} (screen says ${direction})`,
    );
    check(
      kase.headlineWord.test(headlineText),
      `${kase.number}: the sentence says ${kase.headlineWord} — "${headlineText}"`,
    );

    // ── the three money figures ──
    const printedTotal = (await page.locator('[data-figure="total"]').innerText()).trim();
    const printedPrior = (await page.locator('[data-figure="prior_total"]').innerText()).trim();
    const printedDiff = (await page.locator('[data-figure="difference"]').innerText()).trim();
    record(`${kase.number} this bill / last bill / difference`, `${printedTotal} / ${printedPrior} / ${printedDiff}`);
    check(printedTotal === kase.total, `${kase.number}: this bill reads ${kase.total}`);
    check(printedPrior === kase.prior, `${kase.number}: last month reads ${kase.prior}`);
    check(
      printedDiff === kase.difference,
      `${kase.number}: the difference reads ${kase.difference} — sign included`,
    );

    // ── the breakdown: COUNT first, then each named share ──
    const absent = await page.locator("[data-components-absent]").count();
    check(
      absent === 0,
      `${kase.number}: the breakdown is SERVED, not the stated-absence branch ` +
        `(OQ-CWP-1563 closed 2026-09-05; DEF-CWP-3968)`,
    );
    const rows = await page.locator("[data-component]").all();
    const wanted = Object.keys(kase.components);
    check(
      rows.length === wanted.length,
      `${kase.number}: ${wanted.length} component line(s) drawn (found ${rows.length}) — ` +
        `counted BEFORE anything is claimed about "every" one of them`,
    );
    const printedShares = {};
    for (const row of rows) {
      const code = await row.getAttribute("data-component");
      printedShares[code] = (await row.innerText()).trim();
    }
    record(`${kase.number} what moved`, JSON.stringify(printedShares));
    for (const [code, expected] of Object.entries(kase.components)) {
      check(
        printedShares[code] === expected,
        `${kase.number}: ${code} reads ${expected} (screen says ${printedShares[code] ?? "— absent —"})`,
      );
    }

    // ── BR-CWP-046, checked as ARITHMETIC on the printed strings ──
    // ⚠ Both sides are read off the DOM. A server that served a breakdown
    //   disagreeing with its own headline cannot satisfy this.
    const parsed = Object.values(printedShares).map(moneyToNumber);
    check(
      parsed.length > 0 && parsed.every((one) => one !== null),
      `${kase.number}: every component parsed as money or "unchanged" ` +
        `(${JSON.stringify(Object.values(printedShares))})`,
    );
    const summed = Math.round(parsed.reduce((a, b) => a + (b ?? 0), 0) * 100) / 100;
    const headlineNumber = moneyToNumber(printedDiff);
    record(`${kase.number} Σ components vs the headline`, `${summed.toFixed(2)} vs ${headlineNumber?.toFixed(2)}`);
    check(
      summed === headlineNumber,
      `${kase.number}: the lines on the page sum EXACTLY to the difference on the page ` +
        `(${summed.toFixed(2)} = ${headlineNumber?.toFixed(2)}) — BR-CWP-046, no tolerance`,
    );

    // ── the plan's colour tier, read as a COMPUTED COLOUR ──
    //
    // ⚠ **COMPARED AGAINST THE DIFFERENCE ROW RATHER THAN AGAINST A CLASS
    // NAME.** Task O2 says *"positive in brand red, zero and negative ink"*,
    // and the Difference row already implements exactly that through the kit's
    // `TotalRow signed` prop — so the question is whether a component that
    // ROSE is painted the same colour as a headline that rose. Asserting the
    // class `text-accent` instead would pass the day somebody renamed the
    // token and stopped painting anything (`DEF-CWP-3736`: every rule reading
    // an unset `--brand` painted GREY, and every test passed).
    if (kase.direction === "cost_more") {
      const colours = await page.evaluate(() => {
        const read = (el) => (el ? getComputedStyle(el).color : null);
        const rise = [...document.querySelectorAll("[data-component]")].find((el) =>
          el.textContent.trim().startsWith("+"),
        );
        return {
          headline: read(document.querySelector('[data-figure="difference"]')),
          component: read(rise),
          componentText: rise ? rise.textContent.trim() : null,
        };
      });
      record(
        `${kase.number} colour of the headline rise vs a component rise`,
        `${colours.headline} vs ${colours.component} (${colours.componentText})`,
      );
      gaps.known(
        colours.component !== null && colours.component === colours.headline,
        "a component that ROSE is painted in brand red, as the drawing and task O2 both ask",
        {
          defect: "DEF-CWP-4210",
          why: `the headline rise is ${colours.headline} and the component rise ${colours.componentText} is ${colours.component}. The kit already owns this decision in TotalRow's signed prop; the component rows render bare, so a rise and a fall are the same colour and the sign is the only cue.`,
        },
      );
    }

    // ── hard rule 2 — money DISPLAYS to two decimals, everywhere ──
    const bodyText = await page.locator("body").innerText();
    const wrong = badlyScaledMoney(bodyText);
    check(
      wrong.length === 0,
      `${kase.number}: every money figure shows exactly 2 decimals ` +
        `(${wrong.length} did not: ${wrong.slice(0, 4).join(", ")})`,
    );

    // ── the AGAINST LAST AUGUST panel, asserted in BOTH directions ──
    const yearRows = await page.locator("[data-year-compare]").count();
    const yearCharts = await page.locator("[data-year-chart]").count();
    if (kase.yearPanel) {
      check(
        yearRows >= 1 && yearCharts >= 1,
        `${kase.number}: the year panel DRAWS — ${yearCharts} chart(s), ${yearRows} figure row(s) ` +
          `(DEF-CWP-4206: it drew for nobody until today)`,
      );
      const compare = (await page.locator("[data-year-compare]").first().innerText()).trim();
      record(`${kase.number} against the same month last year`, compare);
      // Hard rule 3 — a quantity ALWAYS carries its unit, on BOTH ends.
      const bothUnits = (compare.match(/\bgal\b/g) ?? []).length;
      check(
        bothUnits === 2,
        `${kase.number}: both ends of "${compare}" carry the unit (hard rule 3) — found ${bothUnits}`,
      );
      const months = await page.locator("[data-month-label]").allInnerTexts();
      record(`${kase.number} bar labels`, months.join(" | "));
      check(
        months.length === 2 && months.every((m) => !/^\d{4}-\d{2}$/.test(m.trim())),
        `${kase.number}: the two bars are labelled in words, not as ${'"2026-08"'} (${months.join(", ")})`,
      );
      // ⚠ **AND THAT CHECK ALONE PASSES ON `Aug | Aug`**, which is what the
      // product actually draws — two bars a YEAR apart, labelled identically.
      // A label check that cannot tell the bars apart is a check that cannot
      // fail on the thing that matters (law 7), so the distinctness is its own
      // assertion.
      gaps.known(
        new Set(months.map((m) => m.trim())).size === months.length,
        "the two bars a year apart carry labels that tell them APART",
        {
          defect: "DEF-CWP-4209",
          why: `both bars read "${months[0]?.trim()}" — UsageBars renders a bare month name, which is right on CWP-033's twelve consecutive months and ambiguous here, where the year is the only thing separating them. The drawing labels them "Aug 2025" and "Aug 2026".`,
        },
      );

      // ⚠ **THE QUANTITY'S THOUSANDS SEPARATOR — ALREADY FILED, NOT REFILED.**
      // `DEF-CWP-4168` names its own surface as *CWP-033 and every consumer of
      // `quantity_text`*, and this panel is one of them, so this is that defect
      // seen from a second screen rather than a new one.
      gaps.known(/\d,\d{3}/.test(compare), "the year figures are grouped (4,171 rather than 4171)", {
        defect: "DEF-CWP-4168",
        why: `the panel reads "${compare}"; the drawing and US-CWP-040 both write 4,090 gal and 4,820 gal. metering.quantity_display.quantity_text formats without grouping and every consumer inherits it.`,
      });
      const hint = await page.locator("[data-jump-hint]").count();
      check(hint === 1, `${kase.number}: the panel carries its one explaining sentence (B14 rule 32)`);
    } else {
      check(
        yearRows === 0 && yearCharts === 0,
        `${kase.number}: the year panel is ABSENT — this month has no reading yet, so there is ` +
          `no pair to draw and BR-CWP-093 forbids an empty panel (found ${yearCharts}/${yearRows})`,
      );
    }

    await noInternals(page, kase.number);
    allDates = allDates.concat(await machineDates(page, kase.number));
  }

  // ═══ 4 · the FIRST bill offers no comparison at all ═══════════════════════
  console.log(`\n── 4 · CWP-030 · the FIRST bill (${FIRST_BILL}) ──`);
  await page.goto(`${PORTAL}/bills/${FIRST_BILL}/comparison`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-030"]', { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "4-cwp-030-first-bill.png"), fullPage: true });

  const noComparison = page.locator("[data-no-comparison]");
  check((await noComparison.count()) === 1, `${FIRST_BILL}: the no-comparison sentence is drawn`);
  const firstText = (await noComparison.innerText()).trim();
  record(`${FIRST_BILL} says`, `"${firstText}"`);

  // ⚠ **NOT A COMPARISON AGAINST ZERO** — the story says so in as many words.
  // `$100.00 more than last month` is arithmetically true and, to somebody who
  // has just moved in, a lie. So there must be NO difference figure at all.
  const firstBody = await page.locator("body").innerText();
  check(
    (await page.locator('[data-figure="difference"]').count()) === 0,
    `${FIRST_BILL}: no difference figure anywhere on the page`,
  );
  check(
    (await page.locator("[data-component]").count()) === 0,
    `${FIRST_BILL}: no breakdown either — there is nothing to break down`,
  );
  check(
    !/\$0\.00\s+(more|less)/i.test(firstBody) && !/\$100\.00 more/i.test(firstBody),
    `${FIRST_BILL}: the page never claims a rise or a fall against nothing`,
  );
  await noInternals(page, FIRST_BILL);
  allDates = allDates.concat(await machineDates(page, FIRST_BILL));

  // ═══ 5 · CWP-036 — the alert that has no trigger ══════════════════════════
  console.log("\n── 5 · CWP-036, your usage looks high — NOT BUILT ──");
  //
  // ⚠ **THIS IS A DELIBERATE ABSENCE, NOT LATE WORK, AND THE DRAWING SAYS SO
  // ITSELF.** `wireframes/CWP-036.png` is stamped **BLOCKED** and carries its
  // own panel: *"This alert has no trigger in the product today. The event is
  // declared in the notification catalogue and nothing ever fires it."* The
  // execution plan places `US-CWP-044` here from `wave: 0` as a recorded scope
  // decision. **Nothing is built here on purpose** — firing it needs a daily
  // or weekly comparison against the account's own history, and a
  // monthly-read utility has no such cadence.
  //
  // What IS asserted: that no address serves it, so nobody has half-built it
  // behind a door this run cannot see.
  const addresses = ["/alerts/high-usage", "/alerts", "/usage/high"];
  for (const address of addresses) {
    const answer = await page.goto(`${PORTAL}${address}`, { waitUntil: "networkidle" });
    const served = await page.locator('[data-screen="CWP-036"]').count();
    record(`${address}`, `HTTP ${answer?.status() ?? "?"}, CWP-036 present: ${served}`);
    check(served === 0, `${address}: does not serve CWP-036 (it is not built)`);
  }
  gaps.known(
    false,
    "CWP-036 *your usage looks high* is reachable somewhere in the product",
    {
      defect: "US-CWP-044 (scope decision, CR-068 wave O)",
      why: "the alert has no trigger: the message class exists in the notification catalogue and nothing ever fires it. Firing it needs a daily or weekly comparison against the account's own history, which a monthly-read utility cannot produce — so on this product it could only ever fire at billing time. The drawing is stamped BLOCKED and says so itself. Recorded, not built.",
    },
  );

  // ⚠ **AND THE OTHER HALF OF STEP 5: NOTHING FIRES IT.** The read-validation
  // threshold (`RULE_HIGH`) flags a READING for a clerk, which is a different
  // question from *this household's use has changed*. Asserted on the wire,
  // because an absence is invisible on a screen.
  // `portal/home`'s `attention` list is where an alert would surface to a
  // signed-in customer; there is no messages FEED to read, because `CWP-053`
  // (Messages) is itself one of the ten unbuilt screens and has no endpoint.
  const home = await api(page, "home");
  if (home.status === 200) {
    const attention = JSON.parse(home.body).attention ?? [];
    record("home 'attention' rows", JSON.stringify(attention));
    const firesIt = attention.some((row) => /high[_-]?usage|usage[_-]?high/i.test(row.kind ?? ""));
    check(
      !firesIt,
      `nothing on the account raises a high-usage alert — ${attention.length} attention row(s), ` +
        `kinds ${JSON.stringify(attention.map((r) => r.kind))}, none of them a usage alert`,
    );
  } else {
    skip(`portal/home answered HTTP ${home.status}, so "nothing fires it" was not checked on the wire`);
  }

  // ═══ the wireframe, side by side ═════════════════════════════════════════
  //
  // ⚠ **B14 rule 36 is RATIFIED AND UNENFORCED** — no gate in this repo reads
  // rendered output, so these are eye checks turned into assertions. Each one
  // was made against `wireframes/CWP-030.png` opened beside the running screen.
  console.log("\n── 6 · CWP-030 against its wireframe ──");
  await page.goto(`${PORTAL}/bills/${ROSE_BILL}/comparison`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-030"]', { timeout: 20000 });

  const heading = (await page.locator("h1").first().innerText()).trim();
  record("the drawn H1 is *Why August cost $3.74 more*; the product's H1", `"${heading}"`);
  gaps.known(
    /\$3\.74/.test(heading),
    "the heading names the month and the figure, as the drawing does",
    {
      defect: "DEF-CWP-4211",
      why: "the drawing's H1 is *Why August cost $3.74 more* — the answer IS the heading. The product's H1 is the generic question *Why is this bill different?* and puts the figure in a sentence below it. The figure is on the screen either way, so this is a layout divergence rather than missing information.",
    },
  );

  const rateRow = await page.locator("[data-year-rate]").count();
  gaps.known(rateRow > 0, "the year panel states whether the RATE changed", {
    defect: "DEF-CWP-4212",
    why: "the drawing's right column carries *Rate per gallon — unchanged* under the usage figures, and neither the screen nor the server's reply carries any rate at all. A customer who used more water and is told only that cannot tell whether the price also moved, which is the second thing they ring up to ask.",
  });

  const sendReading = await page.getByRole("link", { name: /send a reading/i }).count();
  const queryBill = await page.getByRole("link", { name: /query this bill/i }).count();
  record("the drawing's two buttons, found on the page", `send a reading: ${sendReading}, query this bill: ${queryBill}`);
  gaps.known(sendReading + queryBill > 0, "the year panel offers the drawing's two next steps", {
    defect: "DEF-CWP-4213",
    why: "the drawing ends the right column with *Send a reading* and *Query this bill*. Both destinations are BUILT — the self-read screen shipped in wave J and the dispute screen in wave I — so this is a screen that explains a bill and then offers no way to act on the explanation.",
  });

  // ═══ what the run measured ═══════════════════════════════════════════════
  console.log("\n── what this run read off the screen ──");
  for (const [what, value] of figures) console.log(`   ${what}: ${value}`);

  console.log("\n── the answer changed, which is the point ──");
  const answers = CASES.map((k) => k.direction);
  check(
    new Set(answers).size === CASES.length,
    `the same screen gave ${new Set(answers).size} different answers across ${CASES.length} bills ` +
      `(${answers.join(", ")}) — plus "no comparison at all" on the first bill`,
  );

  record("raw ISO dates counted across every CWP-030 branch", `${allDates.length}`);
  check(
    allDates.length === 0,
    `no branch of CWP-030 prints a raw machine date to a customer ` +
      `(${allDates.length} found${allDates.length ? `: ${allDates.slice(0, 6).join(", ")}` : ""})`,
  );

  if (skipped.length) {
    console.log(`\n   ⏭ ${skipped.length} step(s) SKIPPED and not counted as passes:`);
    for (const one of skipped) console.log(`      ${one}`);
  }

  await timings.report?.();
  await browser.close();
  console.log(`\n   screenshots in ${OUT}`);
  process.exit(gaps.report(failures));
})().catch((error) => {
  console.error("\n⛔ the run itself failed:", error);
  process.exit(1);
});
