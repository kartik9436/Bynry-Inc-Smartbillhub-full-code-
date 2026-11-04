// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 1 — migrate ONE screen from hand-written CSS to
//           Tailwind utilities (Route B, PO 2026-08-19) and MEASURE the cost.
// Rules:    CR-018 §6 "Every screen renders identically to its pre-migration
//           self, proved by the conformance harness holding every baseline
//           number, plus before/after screenshots of the same screens".
//           DEF-316 (a full-page shot silently captures 900px of a much taller
//           page unless the inner scroller is released).
// Impacts:  nothing in src/ — this is an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// WHAT THIS IS
//
// The Phase 1 spike migrates `features/rating/RateSchedulesTab.tsx` and its
// rules in `features/rating/PlansRates.css`. "It looks the same" is not a
// claim anyone can check by reading a diff of 23 class names against 40
// utility strings, so this captures the SAME screen twice — once at the tip
// before the migration, once after — and the two artefacts are compared byte
// for byte outside the test.
//
// It writes TWO artefacts, and the second is the one that survives a
// disagreement:
//
//   1. a full-page PNG           — what a person sees
//   2. a computed-style census   — WHY, for every element the migration
//                                  touched: 22 properties read off
//                                  getComputedStyle, keyed by a stable path.
//
// A PNG alone tells you something moved and never what. The census names the
// element and the property, so a 1px drift is a diff line rather than an
// afternoon in an image viewer. Both are required: the census cannot see a
// z-order or a paint bug, and the PNG cannot tell you which of 300 rules
// caused one.
//
// HOW TO RUN IT
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npm run build && \
//       E2E_BASE_URL=http://127.0.0.1:8080 \
//       E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//       CR018_OUT=/tmp/cr018/before \
//       npx playwright test e2e/CR-018-rate-schedules-visual.spec.ts
//
// ⚠ REBUILD THE FRONTEND FIRST — `boot_stack.sh` serves `dist/`, so a stale
// bundle photographs yesterday's CSS. That is CR-016's recorded mistake and it
// is even easier to make here, where the whole point is that the CSS changed.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { baseUrl, expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

/** Where the pair of artefacts lands. The two runs MUST use different
 *  directories — a second run into the same one overwrites the "before" it is
 *  being compared against, and the comparison then passes vacuously. */
const OUT = process.env.CR018_OUT ?? "/tmp/cr018/shot";

/** The migrated screen. `/plans-rates` alone lands on the Plans tab; the rate
 *  schedules card grid is its own route segment. */
const SCREEN = "/plans-rates/rates";

/** The properties the census reads. Chosen as the ones a utility migration can
 *  plausibly get wrong — every layout property the deleted rules set, every
 *  colour and type property B14 ratifies, and the two (`border-radius`,
 *  `box-shadow`) whose Tailwind defaults Phase 0 had to neutralise. */
const PROPS = [
  "display",
  "flex-direction",
  "align-items",
  "justify-content",
  "gap",
  "flex-wrap",
  "grid-template-columns",
  "margin",
  "padding",
  "border",
  "border-bottom",
  "border-top",
  "border-left",
  "border-radius",
  "box-shadow",
  "background-color",
  "color",
  "font-family",
  "font-size",
  "font-weight",
  "font-style",
  "font-variant-numeric",
  "text-align",
  "white-space",
  "width",
  "height",
] as const;

test.describe("CR-018 Phase 1 — the migrated screen, photographed and measured", () => {
  test("rate schedules renders identically @app-server", async ({ page }) => {
    test.setTimeout(300_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page);

    await page.goto(`${baseUrl()}/${tenant()}${SCREEN}`);
    await page.waitForURL((url) => url.pathname === `/${tenant()}${SCREEN}`, { timeout: 30_000 });
    // Wait for the DATA, not the paint (DEF-176): the card grid does not exist
    // until the list query resolves, and a shot taken on first paint would
    // photograph a skeleton identically before and after while proving nothing.
    await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
    await page.waitForSelector("main.view", { timeout: 30_000 });
    await page.waitForTimeout(2_500);

    // The screen must actually have content, or both shots are of an empty
    // frame and the comparison is a loop over nothing (DEF-057's shape).
    const cards = await page.locator("main.view section").count();
    expect(cards, "the rate-schedule card grid rendered no cards").toBeGreaterThan(0);

    const census = await page.evaluate((props) => {
      // A stable key for an element: its position in the tree by tag and
      // sibling index. Deliberately NOT the class list — the class list is
      // exactly what this migration changes, so keying on it would make every
      // row a rename and the diff unreadable.
      function pathOf(el: Element): string {
        const parts: string[] = [];
        for (let node: Element | null = el; node !== null; node = node.parentElement) {
          if (node.tagName === "HTML") break;
          const parent = node.parentElement;
          const index =
            parent === null ? 0 : Array.prototype.indexOf.call(parent.children, node);
          parts.unshift(`${node.tagName.toLowerCase()}[${index}]`);
        }
        return parts.join(">");
      }
      const main = document.querySelector("main.view");
      if (main === null) return {};
      const out: Record<string, Record<string, string>> = {};
      for (const el of [main, ...Array.from(main.querySelectorAll("*"))]) {
        const cs = getComputedStyle(el);
        const row: Record<string, string> = {};
        for (const p of props) row[p] = cs.getPropertyValue(p);
        // The ::before pseudo carries the A12 service dot — a 6px circle whose
        // colour IS the datum. It has no element of its own, so it is read
        // here or it is not read at all.
        const before = getComputedStyle(el, "::before");
        if (before.content !== "none" && before.content !== "") {
          row["::before.content"] = before.content;
          row["::before.background-color"] = before.backgroundColor;
          row["::before.width"] = before.width;
          row["::before.height"] = before.height;
          row["::before.border-radius"] = before.borderRadius;
        }
        out[pathOf(el)] = row;
      }
      return out;
    }, PROPS as unknown as string[]);

    mkdirSync(OUT, { recursive: true });
    writeFileSync(join(OUT, "census.json"), `${JSON.stringify(census, null, 1)}\n`);

    // DEF-316: without this the full-page shot captures the viewport height of
    // a much taller page, and two truncated shots match each other perfectly.
    await expandInnerScroller(page);
    await page.screenshot({ path: join(OUT, "rate-schedules.png"), fullPage: true });

    // eslint-disable-next-line no-console
    console.log(`CR-018 census: ${Object.keys(census).length} elements → ${OUT}`);
  });
});
