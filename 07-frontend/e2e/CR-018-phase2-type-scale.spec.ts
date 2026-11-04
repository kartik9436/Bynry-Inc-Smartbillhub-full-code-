// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 2 — adopt the ruled type scale (decision log
//           2026-08-19 "THE TYPE SCALE IS RULED — OQ-275 and OQ-276 CLOSED",
//           commit 4b6baa6) and replace hand-written `font-size:Npx` literals
//           with token references.
// Rules:    the ruling's own bar — "no pixel may move except where the ruling
//           says it must". The three intended movements are the pricing hero
//           (42px → 56px), the 9px/10px re-points, and the seven half-steps.
//           Everything else is a literal becoming a token with the SAME value,
//           and a token that resolves one pixel differently is a regression.
//           DEF-316 (a full-page shot silently captures 900px of a much taller
//           page unless the inner scroller is released).
// Impacts:  nothing in src/ — this is an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// WHY THIS EXISTS AND WHY THE CONFORMANCE SPEC IS NOT ENOUGH
//
// `CR-016-ui-conformance.spec.ts` holds 24 screens against an exact register,
// and it is the gate. But it reads SIX aggregate facts per screen — the DISTINCT
// table body sizes, the DISTINCT button sizes, four counts. A stylesheet that
// re-points `.kpi .k` from 10px to 25px, or fat-fingers `--text-sm` onto a
// heading, changes NO distinct-set the register watches and passes it green.
//
// So this census reads the font size of EVERY element on every screen and keys
// it by tree path, exactly the way Phase 1's `CR-018-rate-schedules-visual`
// census does for one screen. Run it once before the change and once after; the
// diff is the complete list of pixels that moved, element by element, and every
// line in it has to be one the ruling asked for.
//
// HOW TO RUN IT
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npx vite build && \
//       E2E_BASE_URL=http://127.0.0.1:8080 \
//       E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//       CR018P2_OUT=/tmp/cr018p2/before \
//       npx playwright test e2e/CR-018-phase2-type-scale.spec.ts
//
// ⚠ REBUILD THE FRONTEND FIRST — `boot_stack.sh` serves `dist/`, so a stale
// bundle photographs yesterday's CSS. That is CR-016's recorded mistake and
// Phase 1 repeated the warning; the whole point here is that the CSS changed.
//
// ⚠ THE TWO RUNS MUST USE DIFFERENT `CR018P2_OUT` DIRECTORIES. A second run
// into the same one overwrites the "before" it is being compared against and
// the comparison then passes vacuously.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { SIDEBAR_DESTINATIONS } from "../src/routing/sidebarDestinations";

import { baseUrl, expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const OUT = process.env.CR018P2_OUT ?? "/tmp/cr018p2/shot";

/** The same walk CR-016's register uses, so the two instruments cannot
 *  disagree about which screens are covered. */
const EXTRA_DESTINATIONS = [
  "/settings/reference-data/templates",
  "/settings/reference-data/routes-cycles",
] as const;
const DESTINATIONS = [...SIDEBAR_DESTINATIONS, ...EXTRA_DESTINATIONS];

/** Photographed, not merely measured. The brief asks for the pricing page (the
 *  one screen whose pixels are MEANT to move) and three app screens; these
 *  three are the densest small-text surfaces in the product — a settings hub
 *  full of kickers and pills, a list screen with a real table, and a wizard. */
/** ⚠ /dashboard AND /payments WERE ADDED IN PHASE 2b, and they are not "two
 *  more screens" — they are THE TWO SCREENS THE RULING MOVES. OQ-278 re-points
 *  `.kpi .v` from 30px to `--text-metric` (26px), which is the dashboard and
 *  every KPI strip, and `.pay-today-amount` from 40px to `--text-metric-lg`
 *  (32px), which is `/payments`. A phase whose only intended pixel movements
 *  were on screens this instrument did not photograph would have proved
 *  nothing about the only thing it changed. */
const PHOTOGRAPHED = new Set<string>([
  "/dashboard",
  "/payments",
  "/settings",
  "/accounts",
  "/settings/reference-data/routes-cycles",
]);

/** Type properties only. This census answers ONE question — did any text
 *  change size or weight — and a narrow census diffs cleanly. Phase 1's
 *  25-property census is the instrument for a layout migration. */
const PROPS = [
  "font-size",
  "font-weight",
  "font-family",
  "line-height",
  "letter-spacing",
  "text-transform",
] as const;

/** Read every element's type properties, keyed by a path that does NOT include
 *  the class list — a class rename must not read as a moved pixel. */
const censusScript = (props: string[]) => {
  function pathOf(el: Element): string {
    const parts: string[] = [];
    for (let node: Element | null = el; node !== null; node = node.parentElement) {
      if (node.tagName === "HTML") break;
      const parent = node.parentElement;
      const index = parent === null ? 0 : Array.prototype.indexOf.call(parent.children, node);
      parts.unshift(`${node.tagName.toLowerCase()}[${index}]`);
    }
    return parts.join(">");
  }
  const root = document.querySelector("main.view") ?? document.body;
  const out: Record<string, Record<string, string>> = {};
  for (const el of [root, ...Array.from(root.querySelectorAll("*"))]) {
    const cs = getComputedStyle(el);
    const row: Record<string, string> = {};
    for (const p of props) row[p] = cs.getPropertyValue(p);
    out[pathOf(el)] = row;
  }
  return out;
};

test.describe("CR-018 Phase 2 — the type scale, measured on every screen", () => {
  test("every screen's type is photographed and censused @app-server", async ({ page }) => {
    test.setTimeout(1_800_000);
    await page.setViewportSize({ width: 1440, height: 900 });

    const census: Record<string, Record<string, Record<string, string>>> = {};

    // ── The PUBLIC pricing page first, before any sign-in. It is the only
    // screen the ruling MOVES (the hero, 42px → 56px), and it is outside the
    // authenticated shell, so it is walked on its own.
    await page.goto(`${baseUrl()}/`);
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.waitForSelector('[data-pricing="hero"] h1', { timeout: 30_000 });
    await page.waitForTimeout(1_200);
    const heroSize = await page.evaluate(
      () => getComputedStyle(document.querySelector('[data-pricing="hero"] h1') as Element).fontSize,
    );
    census["/"] = await page.evaluate(censusScript, PROPS as unknown as string[]);
    await expandInnerScroller(page);
    await page.screenshot({ path: join(OUT, "pricing.png"), fullPage: true });

    await signIn(page);

    for (const path of DESTINATIONS) {
      if (path.startsWith("/settings/")) {
        await page.goto(`${baseUrl()}/${tenant()}${path}`);
      } else {
        await page.evaluate((to) => {
          window.history.pushState({}, "", to);
          window.dispatchEvent(new PopStateEvent("popstate"));
        }, `/${tenant()}${path}`);
      }
      await page.waitForURL((url) => url.pathname === `/${tenant()}${path}`, { timeout: 30_000 });
      // Wait for the DATA, not the paint (DEF-176): a list's rows do not exist
      // until the query resolves, and a census taken on first paint would
      // measure a skeleton identically before and after while proving nothing.
      await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
      await page.waitForTimeout(1_800);

      census[path] = await page.evaluate(censusScript, PROPS as unknown as string[]);

      if (PHOTOGRAPHED.has(path)) {
        // DEF-316: without this the full-page shot captures the viewport height
        // of a much taller page, and two truncated shots match each other.
        await expandInnerScroller(page);
        await page.screenshot({
          path: join(OUT, `${path.replace(/\//g, "_").replace(/^_/, "")}.png`),
          fullPage: true,
        });
      }
    }

    // A census over an empty walk is a comparison that passes vacuously —
    // DEF-057's shape, and the reason CR-016's spec carries the same guard.
    const elements = Object.values(census).reduce((n, s) => n + Object.keys(s).length, 0);
    expect(Object.keys(census).length).toBeGreaterThanOrEqual(20);
    expect(elements, "the census measured almost nothing").toBeGreaterThan(2_000);

    mkdirSync(OUT, { recursive: true });
    writeFileSync(join(OUT, "census.json"), `${JSON.stringify(census, null, 1)}\n`);
    writeFileSync(join(OUT, "hero.txt"), `${heroSize}\n`);

    // eslint-disable-next-line no-console
    console.log(
      `CR-018 Phase 2 census: ${Object.keys(census).length} screens, ${elements} elements, ` +
        `pricing hero ${heroSize} → ${OUT}`,
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 12-governance/02-decision-log.md 2026-08-19 "THE TYPE SCALE IS RULED — OQ-275 and OQ-276 CLOSED" (commit 4b6baa6) + 12-governance/11-change-requests.md CR-018 §6 + 04-docs/02-decisions/14-ui-conventions.md B14 rules 5 and 20
// generated: 2026-08-19 by the CR-018 Phase 2 lane
// checklist: A✔ B=n/a(instrument, no screen) C=deferred(no backend half — this reads a browser, not an API) D=deferred(no API call) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST (hard-won law 7). Run against the tip build it recorded the pricing hero at 42px; run again with `--text-display` wired it recorded 56px, and the before/after census diff named exactly the elements the ruling moves. The emptiness guards were proved by pointing the walk at a one-entry list (screens 1 < 20 → RED) and by censusing a `display:none` root (elements 0 < 2000 → RED).
// exceptions: (1) it WRITES artefacts and asserts almost nothing — the comparison happens outside the test, between two output directories, because "identical to the previous run" is not a fact a single run can hold · (2) it reads six type properties and nothing else, so a layout regression is invisible to it; CR-016's register and Phase 1's 25-property census are the instruments for that · (3) it walks screens reachable by NAVIGATION and opens no modal, wizard step or panel, so a font size only reachable behind a click is not in the census
// status: VERIFIED-UNRATIFIED
