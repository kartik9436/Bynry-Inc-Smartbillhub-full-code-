/**
 * RENDERED-OUTPUT CHECK — every list fits its column (DEF-SHL-5378, DEF-RAT-8842).
 *
 * ⚠ WHY THIS IS A BROWSER CHECK. jsdom performs no layout, so no unit test can
 * see a table that is 68px wider than its column — and that is exactly how the
 * Rate schedules list shipped with its Retire icon half cut off at 1440. The
 * shared DataTable had the gap under every list for weeks (145 callers); it
 * only shows once a screen declares enough columns. `DataTableWidth.dom.test.tsx`
 * proves the kit's RESPONSE to an overflow; this proves the overflow is
 * actually handled on real screens, with real rows, at the two staff widths.
 *
 * FOR EACH LIST, AT 1440 AND 1280 (the UI skill's staff pair):
 *   1. the page itself never scrolls sideways;
 *   2. the table is no wider than its column — OR its own box scrolls
 *      (`[data-table-scroll]` computes `overflow-x: auto`), never the page;
 *   3. the right edge of every row's last control (the row-action icons) is
 *      at or inside the visible edge of the table's box — i.e. never clipped;
 *   4. where the list has a `+ Filter` panel, it opens and is entirely visible:
 *      no ancestor clips it.
 *
 * RED ON THE OLD CODE (law 7), measured 2026-10-01 against the pre-fix bundle:
 *   1440 plans-rates/rates  table 1188 in 1120 · Retire icon right edge 1456,
 *        box edge 1400 → FAIL; likewise charge-codes (1444) and assets (1514).
 *
 * And the + Filter clause, planted with `PLANT_FRAME_SCROLL=1` (scrolls the
 * whole frame, the fix the wave C lane rejected): FAIL "the + Filter panel is
 * clipped by DIV.data-table-frame" — measured on Taxes & fees and Accounts at
 * 1440, the short lists, where the panel is taller than the table under it.
 *
 * RUN against a running app (backend + `server.mjs` serving a fresh build):
 *   BASE=http://127.0.0.1:4361 node 10-scripts/render-checks/table-width-fit.mjs
 *   LISTS=plans-rates/rates,assets  to narrow it.
 * Exits non-zero naming the list, the width and the measurement.
 */
import path from "node:path";
import { createRequire } from "node:module";

const requireFrontend = createRequire(path.resolve("07-frontend/package.json"));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:4361";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const CHROME = process.env.SBH_CHROMIUM ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const WIDTHS = (process.env.WIDTHS ?? "1440,1280").split(",").map(Number);
const LISTS = (
  process.env.LISTS ??
  [
    "plans-rates/rates",
    "plans-rates/charge-codes",
    "plans-rates/plans",
    "plans-rates/taxes-fees",
    "assets",
    "premises",
    "premises/units",
    "accounts",
    "customers",
    "reads",
  ].join(",")
).split(",");

const browser = await chromium.launch({ executablePath: CHROME });
const problems = [];
let measured = 0;
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60_000 }),
    page.click('button[type="submit"]'),
  ]);

  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: 1000 });
    for (const list of LISTS) {
      await page.goto(`${BASE}/${TENANT}/${list}`, { waitUntil: "networkidle" });
      const found = await page
        .waitForSelector("table.data-table tbody tr", { timeout: 15_000 })
        .then(() => true)
        .catch(() => false);
      if (!found) {
        // Counted, never skipped silently (law 7: a blind spot needs a number).
        problems.push(`${width} ${list}: no rows rendered — nothing was measured`);
        continue;
      }
      await page.waitForTimeout(300);
      const m = await page.evaluate(() => {
        const table = document.querySelector("table.data-table");
        const box = table.closest("[data-table-scroll]") ?? table.parentElement;
        // The visible right edge: the tightest clipping ancestor of the cells.
        let edge = window.innerWidth;
        for (let el = table.parentElement; el; el = el.parentElement) {
          if (getComputedStyle(el).overflowX !== "visible") {
            edge = Math.min(edge, el.getBoundingClientRect().right);
          }
        }
        let actRight = 0;
        for (const row of table.querySelectorAll("tbody tr.data-table-row")) {
          const control = [...(row.lastElementChild?.querySelectorAll("button,a,summary") ?? [])].pop();
          if (control) actRight = Math.max(actRight, control.getBoundingClientRect().right);
        }
        return {
          pageScrollsX: document.documentElement.scrollWidth > window.innerWidth,
          table: Math.round(table.getBoundingClientRect().width),
          box: Math.round(box.clientWidth),
          boxScrolls: getComputedStyle(box).overflowX === "auto",
          edge: Math.round(edge),
          actRight: Math.round(actRight),
        };
      });
      measured += 1;
      const where = `${width} ${list}`;
      if (m.pageScrollsX) problems.push(`${where}: the PAGE scrolls sideways`);
      if (m.table > m.box + 1 && !m.boxScrolls) {
        problems.push(`${where}: table ${m.table}px in a ${m.box}px column and its box does not scroll`);
      }
      if (m.actRight > m.edge + 1) {
        problems.push(`${where}: a row's last control ends at ${m.actRight}px, past the visible edge ${m.edge}px — clipped`);
      }

      // The + Filter panel, where the list has one.
      const filter = page.locator("summary", { hasText: /^\s*\+\s*Filter/ }).first();
      if ((await filter.count()) > 0) {
        if (process.env.PLANT_FRAME_SCROLL === "1") {
          // Law 7 self-test: plant the rejected fix (scroll the WHOLE frame)
          // and this clause must go red with "clipped by DIV.data-table-frame".
          await page.evaluate(() => {
            const f = document.querySelector(".data-table-frame");
            if (f) f.style.overflowX = "auto";
          });
        }
        await filter.click();
        await page.waitForTimeout(200);
        const p = await page.evaluate(() => {
          const details = [...document.querySelectorAll("details[open]")].find((d) =>
            /\+\s*Filter/.test(d.querySelector("summary")?.textContent ?? ""),
          );
          const panel = details?.querySelector(":scope > div");
          if (!panel) return null;
          const r = panel.getBoundingClientRect();
          // Clipped if any ancestor BELOW the page's own scroller clips it.
          // `main.view` scrolls vertically and is how a clerk reaches the
          // bottom of a tall panel, so the walk stops there: everything above
          // it only clips to the window. A box between the panel and `main`
          // that clips — e.g. a scroll wrapper put round the whole table
          // frame, which is the fix the wave C lane rejected — is the failure.
          for (let el = details.parentElement; el; el = el.parentElement) {
            if (el.tagName === "MAIN") break;
            const cs = getComputedStyle(el);
            if (cs.overflowX === "visible" && cs.overflowY === "visible") continue;
            const b = el.getBoundingClientRect();
            if (r.left < b.left - 1 || r.right > b.right + 1 || r.bottom > b.bottom + 1) {
              return { clippedBy: `${el.tagName}.${String(el.className).slice(0, 40)}` };
            }
          }
          return { width: Math.round(r.width), right: Math.round(r.right), vw: window.innerWidth };
        });
        if (p === null) problems.push(`${where}: + Filter did not open a panel`);
        else if (p.clippedBy) problems.push(`${where}: the + Filter panel is clipped by ${p.clippedBy}`);
        else if (p.right > p.vw) problems.push(`${where}: the + Filter panel runs off the window (${p.right} > ${p.vw})`);
        await page.keyboard.press("Escape");
      }
      console.log(`${where}: table ${m.table} · box ${m.box}${m.boxScrolls ? " (scrolls)" : ""} · last control ${m.actRight || "-"} ≤ edge ${m.edge}`);
    }
  }
} finally {
  await browser.close();
}
console.log(`measured ${measured} of ${LISTS.length * WIDTHS.length} list×width pairs`);
if (problems.length > 0) {
  console.error(`\nFAIL — ${problems.length} problem(s):\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
console.log("PASS — every list fits its column, every row's actions are visible, + Filter opens whole");
