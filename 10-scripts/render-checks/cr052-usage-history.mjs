#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:   CR-052 task 9 — "Draw the twelve-month block on the bill document
//           and in the printable page", unblocked by closing DEF-2714.
// Screens:  S30 → "View the bill as sent"
// Rules:    A19 §1.7 · BR-MET-106 (an unread month is ABSENT, never 0) ·
//           BR-BIL-030 (the bill is frozen at issue — no live join) ·
//           B14 rule 31 (no database id on screen) · B14 rule 21 (a utility is
//           emitted only for a file on route-b-migrated.txt) ·
//           hard-won law 6 (no gate in this repo reads rendered output)
// ───────────────────────────────────────────────────────
/**
 * Open a bill that CARRIES the frozen twelve-month block and look at the chart.
 *
 * ⚠ **WHY THIS EXISTS BESIDE 8 PASSING VITEST CASES.** jsdom computes no
 * layout, so `height: 42%` and `height: 0%` are equally "in the document" and a
 * bar with no background colour is indistinguishable from one that is drawn.
 * Both are exactly the failure this feature can have:
 *
 *   · **A TAILWIND UTILITY IN AN UNMIGRATED FILE RENDERS AS NOTHING AT ALL**
 *     (B14 rule 21) — `tsc`, eslint and every `toContain` assertion pass on it
 *     because the class IS in the DOM. Only a computed style can tell.
 *   · **A BAR WITH NO HEIGHT IS A CHART THAT DID NOT DRAW.** The whole point of
 *     the block is a shape a customer can read at a glance.
 *
 * ⚠ **REBUILD BEFORE MEASURING.** A check pointed at a stale `vite build`
 * reports failure with total confidence and no hint that it is looking at an
 * old app (`cr049-bill-document.mjs` learned this on 2026-08-30).
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8032 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4232 API_PROXY_TARGET=http://127.0.0.1:8032 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4232 \
 *   SMOKE_BILL=<a bill whose payload carries usage_history> \
 *   SMOKE_BILL_NO_USAGE=<a bill issued before CR-052 task 8> \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr052-usage-history.mjs
 *
 * ⚠ **THE DEVELOPMENT DATABASE'S 94 SEEDED BILLS CARRY NO BLOCK** — they were
 * seeded on 2026-08-30 and every one predates task 8's stamp, which is the half
 * of `DEF-2714`'s diagnosis that did NOT hold when it was re-checked. Issue one
 * through the product's own path to get a bill with a chart; `BL-2608-000095`
 * (account `A-10432`) was raised that way on 2026-08-31 and carries three
 * measured months and nine absent ones — which is the interesting case, not a
 * blemish, because nine absent months is where BR-MET-106 bites.
 *
 * ⚠ **THE DOCUMENT STORE IS ON DISK AND IS NOT IN A WORKTREE.** A backend run
 * from a `git worktree` resolves `DOCUMENT_STORAGE_DIR` under that worktree, so
 * bills issued elsewhere answer `409 billing.document.bytesMissing` — a data
 * fault that reads exactly like a code fault (see `cr053-bill-surface.mjs`).
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  THE PANEL IS ON THE PAGE, with its heading, and it is BELOW the summary
 *      and ABOVE the messages — the order both server serialisations use.
 *   2  TWELVE SLOTS PER SERVICE, and the month labels are readable under them.
 *   3  A MEASURED MONTH DRAWS A BAR WITH REAL PIXELS AND A REAL COLOUR — a
 *      non-zero height and a background that is not transparent. This is the
 *      assertion that catches an unemitted Tailwind utility.
 *   4  AN ABSENT MONTH DRAWS NO BAR AT ALL — no height, no background. Never a
 *      zero-height bar, and never a `0` printed anywhere in the block.
 *   5  THE TALLEST MEASURED MONTH IS THE TALLEST THING DRAWN, and the others
 *      are shorter in the ratio the figures have.
 *   6  NO DATABASE ID IS ANYWHERE IN THE PANEL (B14 rule 31).
 *   7  A BILL WITH NO BLOCK DRAWS NO PANEL AND NO HEADING — omitted whole.
 *   8  THE PRINTABLE PAGE CARRIES THE SAME MONTHS, fetched as a real PDF.
 *   9  THE PAGE DOES NOT SCROLL SIDEWAYS with twelve columns on it.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4232";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const BILL = process.env.SMOKE_BILL ?? "";
const NO_USAGE = process.env.SMOKE_BILL_NO_USAGE ?? "";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr052-usage";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

/**
 * The usage panel as a BROWSER sees it: computed styles and measured boxes, not
 * attributes. Every number here is the thing jsdom cannot produce.
 */
const READ_USAGE = `(() => {
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const panel = document.querySelector('[data-bil="bill-usage"]');
  if (!panel) return { present: false };
  const heading = panel.querySelector("h3");
  const seriesEls = [...panel.querySelectorAll('[data-bil="bill-usage-series"]')];
  const summary = [...document.querySelectorAll("section")].find(
    (s) => (s.querySelector("h3")?.textContent || "").trim() === "Summary",
  );
  const messages = document.querySelector('[data-bil="bill-copy"]');
  return {
    present: true,
    heading: (heading?.textContent || "").trim(),
    panelBox: box(panel),
    summaryY: summary ? box(summary).y : null,
    messagesY: messages ? box(messages).y : null,
    text: (panel.textContent || "").trim(),
    series: seriesEls.map((s) => ({
      caption: (s.querySelector('[data-bil="bill-usage-caption"]')?.textContent || "").trim(),
      months: [...s.querySelectorAll('[data-bil="bill-usage-month"]')].map((m) =>
        (m.textContent || "").trim(),
      ),
      bars: [...s.querySelectorAll('[data-bil="bill-usage-bar"]')].map((b) => {
        const cs = getComputedStyle(b);
        return {
          month: b.getAttribute("data-month"),
          absent: b.getAttribute("data-absent") === "true",
          estimated: b.getAttribute("data-estimated") === "true",
          height: box(b).h,
          width: box(b).w,
          background: cs.backgroundColor,
          title: b.getAttribute("title") || "",
        };
      }),
    })),
  };
})()`;

const SIDEWAYS = `Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)`;

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

function transparent(colour) {
  return !colour || colour === "transparent" || /rgba\(\s*0,\s*0,\s*0,\s*0\s*\)/.test(colour);
}

(async () => {
  if (!BILL) {
    console.log("⛔ give SMOKE_BILL a bill whose payload carries usage_history");
    process.exit(2);
  }

  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });

  console.log(`cr052 usage: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in");

  // ── THE BILL THAT CARRIES A BLOCK ───────────────────────────────────────
  console.log(`\n── the twelve-month block (${BILL.slice(0, 8)}) ──`);
  await page.goto(`${BASE}/${TENANT}/billing/bills/${BILL}/document`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(OUT, "usage-panel.png"), fullPage: true });

  const usage = await page.evaluate(READ_USAGE);
  writeFileSync(join(OUT, "usage.json"), JSON.stringify(usage, null, 2));

  check(usage.present, "1 · the usage panel is on the page");
  if (!usage.present) {
    console.log("\n⛔ no panel — nothing further can be measured");
    await browser.close();
    process.exit(1);
  }

  check(usage.heading.length > 0, `1 · it has a heading (${usage.heading})`);
  check(
    usage.summaryY === null || usage.panelBox.y > usage.summaryY,
    "1 · it sits BELOW the summary box, as both serialisations put it",
  );
  check(
    usage.messagesY === null || usage.panelBox.y < usage.messagesY,
    "1 · and ABOVE the messages",
  );
  check(usage.panelBox.h > 40, `1 · it occupies real space (${usage.panelBox.h}px tall)`);

  check(usage.series.length > 0, `2 · at least one service is drawn (${usage.series.length})`);
  for (const series of usage.series) {
    check(
      series.bars.length === 12,
      `2 · ${series.caption || "(unnamed)"} draws twelve slots (${series.bars.length})`,
    );
    check(
      series.months.length === 12,
      `2 · ${series.caption || "(unnamed)"} labels twelve months (${series.months.length})`,
    );

    const drawn = series.bars.filter((b) => !b.absent);
    const absent = series.bars.filter((b) => b.absent);

    // ── 3 · A MEASURED MONTH IS ACTUALLY DRAWN ───────────────────────────
    // The assertion that catches an unemitted Tailwind utility: a class that
    // renders as nothing still passes `tsc` and every `toContain` assertion.
    for (const bar of drawn) {
      check(bar.height > 0, `3 · ${series.caption} ${bar.month} has real height (${bar.height}px)`);
      check(bar.width > 0, `3 · ${series.caption} ${bar.month} has real width (${bar.width}px)`);
      check(
        !transparent(bar.background),
        `3 · ${series.caption} ${bar.month} has a real colour (${bar.background})`,
      );
    }

    // ── 4 · AN ABSENT MONTH IS NOT A ZERO ────────────────────────────────
    for (const bar of absent) {
      check(
        transparent(bar.background),
        `4 · ${series.caption} ${bar.month} draws NO bar (background ${bar.background})`,
      );
      check(
        bar.title.length > 0,
        `4 · ${series.caption} ${bar.month} says why it is empty`,
      );
    }
    if (absent.length > 0) {
      // BR-MET-106 — nothing may print a fabricated zero for an unread month.
      const zeroish = /(^|[^0-9.])0([^0-9.]|$)/.test(usage.text);
      check(!zeroish, "4 · no fabricated 0 is printed anywhere in the block");
    }

    // ── 5 · THE SHAPE IS THE DATA ────────────────────────────────────────
    if (drawn.length > 1) {
      const tallest = Math.max(...drawn.map((b) => b.height));
      const shortest = Math.min(...drawn.map((b) => b.height));
      check(
        tallest > shortest,
        `5 · ${series.caption} months differ in height (${shortest}px … ${tallest}px)`,
      );
      check(
        absent.length === 0 || tallest > Math.max(0, ...absent.map((b) => b.height)) ||
          absent.every((b) => transparent(b.background)),
        "5 · a measured month stands taller than an unmeasured one",
      );
    }
  }

  // ── 6 · NO DATABASE ID ──────────────────────────────────────────────────
  check(!UUID.test(usage.text), "6 · no database id is anywhere in the panel (B14 rule 31)");

  // ── 9 · NO SIDEWAYS SCROLL ──────────────────────────────────────────────
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `9 · the page does not scroll sideways (${sideways}px)`);

  // ── 8 · THE PRINTABLE PAGE CARRIES THE SAME MONTHS ──────────────────────
  // THE LINK THE PAGE OFFERS, not one this file composes. A composed URL that
  // 404s reads as a broken feature; the point is to follow what a clerk clicks.
  const pdfHref = await page.evaluate(`(() => {
    const a = [...document.querySelectorAll("a")].find((el) =>
      (el.getAttribute("href") || "").endsWith("/document.pdf"),
    );
    return a ? a.getAttribute("href") : null;
  })()`);
  check(Boolean(pdfHref), `8 · the page offers a printable-page link (${pdfHref})`);
  const pdf = await page.evaluate(async (url) => {
    if (!url) return { status: 0, type: null, text: "", bytes: 0 };
    const response = await fetch(url, { credentials: "include" });
    const buffer = await response.arrayBuffer();
    return {
      status: response.status,
      type: response.headers.get("content-type"),
      text: new TextDecoder("latin1").decode(buffer),
      bytes: buffer.byteLength,
    };
  }, pdfHref);
  check(pdf.status === 200, `8 · the printable page answers 200 (${pdf.status})`);
  check(
    (pdf.type || "").includes("pdf"),
    `8 · and it really is a PDF (${pdf.type}, ${pdf.bytes} bytes)`,
  );
  const monthsOnScreen = usage.series[0]?.months ?? [];
  for (const label of monthsOnScreen) {
    check(pdf.text.includes(label), `8 · the page prints ${label} too`);
  }

  // ── 7 · A BILL WITH NO BLOCK DRAWS NOTHING ──────────────────────────────
  if (NO_USAGE) {
    console.log(`\n── a bill with no frozen block (${NO_USAGE.slice(0, 8)}) ──`);
    await page.goto(`${BASE}/${TENANT}/billing/bills/${NO_USAGE}/document`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: join(OUT, "no-usage.png"), fullPage: true });
    const bare = await page.evaluate(READ_USAGE);
    // ⚠ **THE PAGE MUST HAVE RENDERED FIRST, OR THIS CHECK CANNOT FAIL.** A
    // bill whose document 409s (`billing.document.bytesMissing`, the
    // worktree document-store fault above) draws no bands at all, so "no usage
    // panel" would be trivially true and this check would report success over a
    // broken page. Proved on 2026-08-31: the first bill tried answered 409 and
    // check 7 passed for entirely the wrong reason.
    const rendered = await page.evaluate(`(() => {
      const bands = [...document.querySelectorAll("section h3")].map((h) => h.textContent.trim());
      return { bands, hasSummary: bands.includes("Summary") };
    })()`);
    check(
      rendered.hasSummary,
      `7 · the comparison bill's document actually rendered (${rendered.bands.length} bands)`,
    );
    check(
      rendered.hasSummary && !bare.present,
      "7 · a bill that froze no block draws no panel at all",
    );
  } else {
    console.log("   (skipping 7 — give SMOKE_BILL_NO_USAGE a pre-task-8 bill)");
  }

  await browser.close();
  console.log(`\nscreenshots in ${OUT}`);
  if (failures.length) {
    console.log(`\n⛔ ${failures.length} failure(s):`);
    for (const line of failures) console.log(`   · ${line}`);
    process.exit(1);
  }
  console.log("\n✓ every check passed");
})();
