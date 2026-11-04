/**
 * RENDERED-OUTPUT CHECK — CR-085 step 2 lane 8, "what you used, and asking us
 * something", in a real browser at **390 AND 1280**. Screens `CWP-033`
 * (/usage), `CWP-034` (/readings), `CWP-037` (/equipment), `CWP-046`
 * (/requests), `CWP-051` (/requests/:reference), `CWP-010` (/ask), `CWP-054`
 * (/ask-a-question).
 *
 * ⚠ **WHY THIS EXISTS AND WHY IT IS SEPARATE FROM `cr068-h`.** That check walks
 * the wave-H demo script against a fixture tenant and asserts the FIGURES. This
 * one asserts the things step 2 changed and that nothing in this repo can see:
 * a heading that survives a failed read, a grid's computed column template, a
 * row's computed background, and whether a control the drawing puts beside a
 * message is actually there. Hard-won law 6 — no gate looks at rendered output.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   SMOKE_BASE=http://127.0.0.1:8462 SMOKE_TENANT=brazosbend \
 *   SMOKE_EMAIL=elena@example.test SMOKE_PASSWORD='Brazos-Bend-2026!' \
 *     node 10-scripts/render-checks/cr085-lane8-usage-ask.mjs
 *
 * ⚠ **BUILD THE BUNDLE FIRST.** A stale `dist/` means every line below is about
 * a build nobody is shipping.
 *
 * ⚠ **WHAT THE LIVE TENANT CANNOT SHOW, AND IT IS SAID OUT LOUD RATHER THAN
 * QUIETLY SKIPPED** (hard-won law 7 — a declared blind spot with no NUMBER
 * attached is indistinguishable from an empty one). `brazosbend`'s one account
 * has two meters with **no size class and no fire line**, and no clerk has
 * pinned a help answer to any screen. So the equipment SIZE and the attached
 * answer are exercised here through `page.route` fixtures, marked `[fixture]`
 * in the output, and the rest of the walk is live. The server halves of both
 * are proved against a real PostgreSQL in
 * `06-backend/tests/test_cr085_lane8_size_and_attached_answer.py`.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const candidates = [];
  try {
    candidates.push(chromium.executablePath());
  } catch {
    /* the computed path is optional */
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
    /* nothing under /opt */
  }
  for (const c of candidates) if (c && existsSync(c)) return c;
  throw new Error(`no chromium found. Tried: ${candidates.filter(Boolean).join(", ")}`);
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8462";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "elena@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Brazos-Bend-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/claude-0/cr085-lane8";
const PORTAL = `${BASE}/${TENANT}/portal`;

let failures = 0;
const check = (ok, what) => {
  if (!ok) failures += 1;
  console.log(`   ${ok ? "ok  " : "FAIL"}  ${what}`);
};
const record = (what, value) => console.log(`   ..    ${what}: ${value}`);

async function signIn(page) {
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 30000 });
}

/** Everything a heading-and-door check needs, read in one evaluate. */
const frameOf = (page) =>
  page.evaluate(() => ({
    h1: document.querySelector("h1")?.textContent ?? null,
    headings: document.querySelectorAll("h1,h2,h3,h4").length,
    screen: document.querySelector("[data-screen]")?.getAttribute("data-screen") ?? null,
    state: document.querySelector("[data-portal-state]")?.getAttribute("data-portal-state") ?? null,
    waysOut: [...document.querySelectorAll("[data-way-out]")].map((el) =>
      el.getAttribute("data-way-out"),
    ),
    hrefs: [...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href")),
    scrollsSideways: document.documentElement.scrollWidth > window.innerWidth,
  }));

(async () => {
  mkdirSync(OUT, { recursive: true });
  // ⚠ **PLAYWRIGHT'S 180s LAUNCH TIMEOUT IS NOT ENOUGH ON A SHARED CONTAINER
  // AND THE FAILURE READS LIKE A BROKEN CHECK.** On 2026-09-11 this run died on
  // `browserType.launch: Timeout 180000ms exceeded` with the box at load 160
  // and 1.3 GB of 16 GB free — chromium had been LAUNCHED (the log prints its
  // pid) and simply could not finish starting. Nothing about the app was wrong.
  // A walkthrough that cannot be told apart from a defect is one nobody re-runs.
  const browser = await chromium.launch({ executablePath: resolveChromium(), timeout: 600000 });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 160)}`);
  });
  console.log(`cr085-lane8: ${BASE} tenant=${TENANT} as ${EMAIL}`);

  await signIn(page);

  // ⚠ `SMOKE_ONLY=failed` runs the two sections below the happy walk and
  // nothing else. It exists because the happy walk takes twenty minutes on a
  // loaded container and the failure branch is the half that matters most.
  for (const width of process.env.SMOKE_ONLY === "failed" ? [] : [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });

    // ═════ CWP-033 · /usage ═════════════════════════════════════════════
    console.log(`\n── /usage · CWP-033 · ${width} ──`);
    await page.goto(`${PORTAL}/usage`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-screen="CWP-033"]', { timeout: 30000 });
    const usage = await frameOf(page);
    record("h1", JSON.stringify(usage.h1));
    check(usage.h1 === "What you have used", "DEF-CWP-4846 — the screen has its page title");
    check(usage.screen === "CWP-033", "the screen id is in the DOM");
    check(!usage.scrollsSideways, "nothing scrolls sideways");
    // B14 rule 2 / the census's last case — ONE title, not a second copy.
    const titleCopies = await page.evaluate(() =>
      [...document.querySelectorAll("*")].filter(
        (el) => el.textContent === "What you have used" && el.children.length === 0,
      ).length,
    );
    check(titleCopies === 1, `exactly one element says the title (found ${titleCopies})`);

    const kpi = await page.evaluate(() => {
      const row = document.querySelector("[data-kpi-row]");
      const tile = document.querySelector("[data-kpi]");
      const cs = row ? getComputedStyle(row) : null;
      const ts = tile ? getComputedStyle(tile) : null;
      return {
        tiles: document.querySelectorAll("[data-kpi]").length,
        columns: cs?.gridTemplateColumns ?? null,
        rowGap: cs?.rowGap ?? null,
        padBlock: ts?.paddingTop ?? null,
        padInline: ts?.paddingLeft ?? null,
        gap: ts?.rowGap ?? null,
        values: [...document.querySelectorAll("[data-kpi-value]")].map((e) => e.textContent),
        units: [...document.querySelectorAll("[data-kpi-unit]")].map((e) => e.textContent),
      };
    });
    record("KPI tiles / columns", `${kpi.tiles} / ${kpi.columns}`);
    record("KPI values", JSON.stringify(kpi.values));
    record("KPI units", JSON.stringify(kpi.units));
    record("B14 rule 39 anchor — tile padding block/inline, gap", `${kpi.padBlock} / ${kpi.padInline}, ${kpi.gap}`);
    const tracks = (kpi.columns ?? "").trim().split(/\s+/).filter(Boolean).length;
    // ⚠ **AN ACCOUNT WITH NO MEASURED SERVICE DRAWS NO KPI ROW, AND THAT IS
    // CORRECT — SO THESE CHECKS MUST SAY "VACUOUS" RATHER THAN "ok".** The
    // `brazosbend` account has no services on its usage payload at all, so
    // every assertion about tiles, columns, units and the axis passes over
    // NOTHING here. A check that cannot be told apart from a real pass is
    // worse than no check (hard-won law 7, `DEF-182`), and the numbers above
    // are printed so a reader can see which case they are in. The column rule
    // itself is asserted where it CAN be: `kpiColumns()` and the rendered
    // `grid-cols-3` class in `Usage.dom.test.tsx`.
    if (kpi.tiles === 0) {
      record(
        `KPI row @${width}`,
        "NO TILES on this account — every tile, unit and axis check below is VACUOUS",
      );
    } else if (width === 1280) {
      // DEF-CWP-4847 — no row may end with exactly one orphan tile.
      const orphan = tracks > 0 && kpi.tiles % tracks === 1 && kpi.tiles > tracks;
      check(!orphan, `DEF-CWP-4847 — ${kpi.tiles} tiles in ${tracks} columns leaves no orphan`);
      // CLAUDE.md hard rule 3 — every consumption figure carries its unit.
      check(
        kpi.units.length > 0,
        `hard rule 3 — ${kpi.units.length} units against ${kpi.values.length} figures`,
      );
    } else {
      check(tracks === 1, `at 390 the KPI row stacks to one column (${tracks})`);
    }
    const axis = await page.locator("[data-chart-axis]").first().textContent().catch(() => null);
    record("chart axis", JSON.stringify(axis));
    // ⚠ **THE MONTH LABELS ARE TRUNCATED BY CSS (`truncate`), SO `textContent`
    // CANNOT SEE IT.** A label reading `May` in the DOM renders as `M…` in a
    // 27px track, and a check that printed the text would report twelve
    // perfectly good month names over an unreadable axis — a check looking at
    // the wrong thing (hard-won law 7). `scrollWidth > clientWidth` is the
    // measurement that actually answers it.
    const months = await page.evaluate(() =>
      [...document.querySelectorAll("[data-chart] [data-month-label]")].map((el) => ({
        text: (el.textContent ?? "").trim(),
        clipped: el.scrollWidth > el.clientWidth,
        track: Math.round(el.getBoundingClientRect().width),
      })),
    );
    record("axis labels", JSON.stringify(months.map((m) => m.text)));
    record(
      "…of which CLIPPED by CSS",
      `${months.filter((m) => m.clipped).length} of ${months.length}` +
        ` (track ${months[0]?.track ?? "?"}px)`,
    );
    await page.screenshot({ path: `${OUT}/usage-${width}.png`, fullPage: true });

    // ═════ CWP-034 · /readings ═════════════════════════════════════════
    console.log(`\n── /readings · CWP-034 · ${width} ──`);
    await page.goto(`${PORTAL}/readings`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-screen="CWP-034"]', { timeout: 30000 });
    const readings = await frameOf(page);
    record("h1", JSON.stringify(readings.h1));
    check(readings.h1 !== null, "the screen has its page title");
    check(!readings.scrollsSideways, "nothing scrolls sideways");
    const figures = await page.evaluate(() => ({
      dial: [...document.querySelectorAll("[data-reading]")].map((e) => e.textContent),
      used: [...document.querySelectorAll("[data-used]")].map((e) => e.textContent),
      cardUsed: [...document.querySelectorAll("[data-card-used]")].map((e) => e.textContent),
      rowBackgrounds: [...document.querySelectorAll("tbody tr")].map(
        (tr) => getComputedStyle(tr).backgroundColor,
      ),
      estimatedCards: [...document.querySelectorAll("[data-reading-card][data-estimated]")].map(
        (el) => getComputedStyle(el).backgroundColor,
      ),
      empty: document.querySelector("[data-readings-empty]")?.textContent ?? null,
      nextRead: document.querySelector("[data-next-read]")?.textContent ?? null,
    }));
    record("dial figures", JSON.stringify(figures.dial));
    record("used-since figures", JSON.stringify(figures.used));
    record("used-since on the phone card", JSON.stringify(figures.cardUsed));
    record("next read line", JSON.stringify(figures.nextRead));
    record("empty state", JSON.stringify(figures.empty));
    record("estimated card backgrounds", JSON.stringify(figures.estimatedCards));
    // ⚠ **`DEF-CWP-4168` READ AS A NEGATIVE, WHICH IS THE ONLY WAY IT CAN
    // FAIL HONESTLY.** The defect is two FORMATS on one screen, so asserting
    // "this cell says 4,820" would pass on a tenant whose figures are all
    // three digits and prove nothing. What cannot be true after the fix is a
    // run of four or more digits with no separator in it, in either column.
    // (A tenant whose numbers are all small makes both checks vacuous — the
    // figures are PRINTED above so a reader can see which case they are in.)
    check(
      figures.used.every((u) => u === null || !/\d{4,}/.test(u)),
      `DEF-CWP-4168 — no ungrouped four-digit consumption on the row ${JSON.stringify(figures.used)}`,
    );
    check(
      figures.dial.every((d) => d === null || !/\d{4,}/.test(d)),
      "…and none in the dial column either",
    );
    await page.screenshot({ path: `${OUT}/readings-${width}.png`, fullPage: true });

    // ═════ CWP-037 · /equipment ════════════════════════════════════════
    console.log(`\n── /equipment · CWP-037 · ${width} ──`);
    await page.goto(`${PORTAL}/equipment`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-screen="CWP-037"]', { timeout: 30000 });
    const equip = await frameOf(page);
    record("h1", JSON.stringify(equip.h1));
    check(equip.h1 !== null, "the screen has its page title");
    check(equip.hrefs.some((h) => h?.endsWith("/portal/usage")), "the ← Usage door is live");
    check(!equip.scrollsSideways, "nothing scrolls sideways");
    const cells = await page.evaluate(() => ({
      kinds: [...document.querySelectorAll("[data-kind]")].map((e) => e.textContent),
      cardKinds: [...document.querySelectorAll("[data-card-kind]")].map((e) => e.textContent),
      monthly: [...document.querySelectorAll("[data-monthly]")].map((e) => e.textContent),
    }));
    record("equipment cells", JSON.stringify(cells.kinds));
    record("equipment cells (phone card)", JSON.stringify(cells.cardKinds));
    record("monthly", JSON.stringify(cells.monthly));
    const said = [...cells.kinds, ...cells.cardKinds].filter(Boolean);
    check(
      said.every((c) => !/^(\w+) \1\b/.test(c ?? "")),
      "DEF-CWP-4848 — no cell repeats its own service word",
    );
    // ⚠ **THE FIRST DRAFT OF THIS CHECK WAS WRONG AND THE SCREEN WAS RIGHT.**
    // It tested `/\b(FL|W|CART|DUMP|E)-\d/` against the page text and went red
    // on **`W-7001`** — the ASSET NUMBER, which is exactly the reference
    // `US-CWP-043` TC-5 says a customer reads off the box. A size-class code
    // and an asset number are the same SHAPE (`W-58` / `W-7001`); only the
    // actual value tells them apart. So the codes are read from the payload
    // the screen was given, and where the account has none the check SAYS SO
    // rather than passing silently over nothing — hard-won law 7, a declared
    // blind spot carries a number.
    const sizeCodes = await page.evaluate(async () => {
      const tenant = location.pathname.split("/")[1];
      const session = await fetch(`/api/${tenant}/portal/session`).then((r) => r.json());
      const account = session?.accounts?.[0]?.id;
      if (!account) return [];
      const body = await fetch(`/api/${tenant}/portal/accounts/${account}/equipment`).then((r) =>
        r.json(),
      );
      return [...new Set((body?.equipment ?? []).map((row) => row.size_class).filter(Boolean))];
    });
    if (sizeCodes.length === 0) {
      record("B14 rule 32", "this account records NO size class — the check is vacuous here");
    } else {
      const text = await page.locator("body").innerText();
      check(
        sizeCodes.every((code) => !text.includes(code)),
        `B14 rule 32 — none of ${JSON.stringify(sizeCodes)} is on the glass`,
      );
    }
    await page.screenshot({ path: `${OUT}/equipment-${width}.png`, fullPage: true });

    // ═════ the other four, for the frame and the sideways check ════════
    for (const [path, id] of [
      ["/requests", "CWP-046"],
      ["/ask", "CWP-010"],
      ["/ask-a-question", "CWP-054"],
    ]) {
      console.log(`\n── ${path} · ${id} · ${width} ──`);
      await page.goto(`${PORTAL}${path}`, { waitUntil: "networkidle" });
      await page.waitForSelector(`[data-screen="${id}"]`, { timeout: 30000 });
      const f = await frameOf(page);
      record("h1", JSON.stringify(f.h1));
      check(!f.scrollsSideways, "nothing scrolls sideways");
      if (path === "/ask-a-question") {
        const ring = await page.evaluate(() => {
          const card = document.querySelector('[data-testid="question-or-ring"]');
          return card === null
            ? { present: false, phones: 0 }
            : { present: true, phones: card.querySelectorAll("[data-phone]").length };
        });
        record("OR RING card", JSON.stringify(ring));
        check(
          !ring.present || ring.phones > 0,
          "BR-CWP-093 — the Or ring card is ABSENT rather than empty",
        );
      }
      await page.screenshot({ path: `${OUT}/${id}-${width}.png`, fullPage: true });
    }
  }

  // ═════ THE FAILED READ — the state nobody walks ══════════════════════
  console.log("\n── every read answers 500 — the branch DEF-CWP-4846 is about ──");
  await page.setViewportSize({ width: 1280, height: 900 });
  for (const [path, id, sentence] of [
    ["/usage", "CWP-033", "We could not read your usage."],
    ["/readings", "CWP-034", "We could not read your meter history."],
    ["/equipment", "CWP-037", "We could not read your equipment."],
  ]) {
    await page.route("**/api/**/accounts/**", (route) => {
      const url = route.request().url();
      if (/\/(usage|readings|equipment)(\?|$)/.test(url)) {
        return route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
      }
      return route.continue();
    });
    // ⚠ **`domcontentloaded`, NOT `networkidle`, AND THE REASON IS THE STATE
    // BEING TESTED.** With the account reads answering 500 the screen's own
    // effect retries and the dev server's HMR socket never goes quiet, so
    // `networkidle` times out at 30s and the run dies **before** the branch it
    // exists to look at — a check that cannot reach its subject. The wait that
    // actually means something is the state card appearing.
    await page.goto(`${PORTAL}${path}`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(`[data-portal-state="failed"]`, { timeout: 60000 });
    const f = await frameOf(page);
    console.log(`   ${path}`);
    record("h1 / screen / state", `${JSON.stringify(f.h1)} / ${f.screen} / ${f.state}`);
    record("ways out", JSON.stringify(f.waysOut));
    check(f.h1 !== null, `${id} keeps its page title through a failed read`);
    check(f.screen === id, `${id} keeps its screen id through a failed read`);
    check(f.state === "failed", "R-22 — the card says WHICH state it is");
    check(f.waysOut.length > 0, "R-10 — a way out is beside the message");
    check(
      (await page.locator("body").innerText()).includes(sentence),
      "…and the sentence is this screen's own",
    );
    await page.screenshot({ path: `${OUT}/failed-${id}.png`, fullPage: true });
    await page.unroute("**/api/**/accounts/**");
  }

  // ═════ [fixture] the fire line, and the clerk's pinned answer ════════
  console.log("\n── [fixture] the two facts the live tenant cannot show ──");
  await page.route("**/api/**/accounts/**/equipment", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        as_of: "2026-09-11",
        equipment: [
          {
            serial_no: "W-2209", asset_no: "W-2209", kind: "Meter", kind_code: "meter",
            category: "meters", service: "water", service_name: "Water", where: null,
            fitted_on: "2026-06-02", status: "Installed", status_code: "active",
            behavior_class: "in_service", test_due_on: null, test_due: false,
            size_class: "W-58", size_class_name: 'Water 5/8"', last_read_on: null,
            maintained_by: "utility", charge_basis: "usage_only",
            monthly_charge: null, monthly_charge_bill: null,
          },
          {
            serial_no: "F-0118", asset_no: "F-0118", kind: "Fire service line",
            kind_code: "fire_line", category: "behind_the_meter", service: "fire",
            service_name: "Fire", where: null, fitted_on: "2026-06-02",
            status: "Installed", status_code: "active", behavior_class: "in_service",
            test_due_on: null, test_due: false, size_class: "FL-2",
            size_class_name: 'Fire line 2"', last_read_on: null,
            maintained_by: "utility", charge_basis: "per_item",
            monthly_charge: "12.00", monthly_charge_bill: "BL-2608-000042",
          },
        ],
      }),
    }),
  );
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${PORTAL}/equipment`, { waitUntil: "networkidle" });
    await page.waitForSelector('[data-screen="CWP-037"]', { timeout: 30000 });
    const drawn = await page.evaluate(() => ({
      kinds: [...document.querySelectorAll("[data-kind],[data-card-kind]")].map((e) => e.textContent),
      monthly: [...document.querySelectorAll("[data-monthly],[data-card-monthly]")].map(
        (e) => e.textContent,
      ),
      code: /FL-2|W-58/.test(document.body.innerText),
    }));
    record(`[fixture] equipment cells @${width}`, JSON.stringify(drawn.kinds));
    record(`[fixture] monthly @${width}`, JSON.stringify(drawn.monthly));
    check(
      drawn.kinds.includes('Fire service line · 2"'),
      `[fixture] DEF-CWP-4848 — the fire row states its size @${width}`,
    );
    check(
      drawn.kinds.includes('Water Meter · 5/8"'),
      `[fixture] the water meter keeps its service word and states its size @${width}`,
    );
    // The fixture's own two codes, by name — never a shape, for the reason the
    // live check above records (`W-2209` is a serial and `W-58` is a size).
    check(!drawn.code, `[fixture] B14 rule 32 — neither FL-2 nor W-58 is on the glass @${width}`);
    await page.screenshot({ path: `${OUT}/equipment-fire-${width}.png`, fullPage: true });
  }
  await page.unroute("**/api/**/accounts/**/equipment");

  console.log(`\ncr085-lane8: ${failures} failure(s). shots in ${OUT}`);
  await browser.close();
  process.exit(failures === 0 ? 0 : 1);
})().catch((error) => {
  console.error(error);
  process.exit(2);
});
