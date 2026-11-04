// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 5 — enable Tailwind Preflight (PO: "Complete this -
//           Phase 5 (Preflight) not started")
// Rules:    CR-018 §6 (every screen renders identically) · hard-won law 6
// Impacts:  nothing in src/ — an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// PREFLIGHT IS ONE IMPORT LINE AND THE LARGEST BLAST RADIUS IN THE CR.
//
// Phase 1 imported it once, on purpose, and photographed the result: **684
// computed property values moved on ONE screen**, `<h1>` went 30px → 15px, and
// 654 border values went `0px none` → `0px solid`. It was deferred to last for
// that reason and for one more: **no gate in this repo reads rendered output**,
// so it would have shipped green (hard-won law 6).
//
// ⚠ THE LAYER IS WHAT MAKES THIS SURVIVABLE, AND IT IS WORTH SPELLING OUT.
// Preflight is imported into `layer(base)`. The cascade orders unlayered author
// CSS ABOVE any layer, so:
//
//      browser UA styles  <  layer(base) = Preflight  <  40 legacy stylesheets
//
// Every legacy rule still wins. What Preflight can therefore change is exactly
// the set of properties where THE BROWSER was supplying the value and no author
// rule overrides — which is a much smaller set than 684 and is what this
// measures. `global.css` gives `h1`–`h6` a family, a weight, a leading and a
// tracking and **no font-size**, so the size is one of them.
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npm run build && \
//       E2E_BASE_URL=http://127.0.0.1:8124 CR018_OUT=/tmp/p5/before \
//       npx playwright test e2e/CR-018-phase5-preflight.spec.ts
//
// ⚠ BEFORE and AFTER go to DIFFERENT directories, served by two servers on two
// ports against one backend — a second run into the same directory overwrites
// the baseline and the comparison then passes vacuously.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const OUT = process.env.CR018_OUT ?? "/tmp/p5/census";

/** Breadth over depth: Preflight resets BASE ELEMENTS, so the risk is spread
 *  evenly across the product rather than concentrated on one feature. */
const SCREENS = [
  "/dashboard", "/accounts", "/premises", "/premises/units", "/assets",
  "/reads", "/billing/bills", "/payments", "/payments/outstandings",
  "/finance/gl?view=chart", "/finance/close", "/reports",
  "/reports/account-ledger", "/settings/company", "/settings/users",
  "/settings/reference-data", "/settings/accounting", "/settings/numbering",
  "/settings/notifications", "/checklist",
] as const;

/** Every element type Preflight touches. */
const TAGS = "h1,h2,h3,h4,h5,h6,p,ul,ol,li,table,thead,th,td,img,svg,button,input,select,textarea,a,hr,fieldset,legend,blockquote,pre,figure";

/** Every property Preflight sets, plus the ones a heading reset moves. */
const PROPS = [
  "font-size", "font-weight", "font-family", "line-height", "letter-spacing",
  "margin-top", "margin-right", "margin-bottom", "margin-left",
  "padding-top", "padding-right", "padding-bottom", "padding-left",
  "border-top-width", "border-top-style", "border-top-color",
  "border-bottom-width", "border-bottom-style",
  "list-style-type", "list-style-position",
  "display", "vertical-align", "text-align", "text-indent",
  "border-collapse", "border-spacing", "box-sizing", "color",
  "background-color", "text-decoration-line", "cursor",
] as const;

test.describe("CR-018 Phase 5 — what does Preflight actually move?", () => {
  test("census every base element on 20 screens @app-server", async ({ page }) => {
    test.setTimeout(900_000);
    await signIn(page);
    mkdirSync(OUT, { recursive: true });

    const census: Record<string, { key: string; style: string }[]> = {};
    let total = 0;
    const perScreen: string[] = [];

    for (const path of SCREENS) {
      await page.goto(`${baseUrl()}/${tenant()}${path}`);
      await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
      await page.waitForTimeout(1_200);

      const rows = await page.evaluate(
        ({ tags, props }) => {
          const out: { key: string; style: string }[] = [];
          const nodes = Array.from(document.querySelectorAll<HTMLElement>(tags)).filter((el) => {
            const s = getComputedStyle(el);
            return s.display !== "none" && s.visibility !== "hidden";
          });
          // ⚠ KEYED BY TAG + ORDINAL WITHIN THAT TAG, not by a global index.
          // Preflight can change an element's `display`, which changes what is
          // VISIBLE, which would shift a global ordinal and make every later
          // element look changed. Per-tag ordinals localise that.
          const seen: Record<string, number> = {};
          for (const el of nodes) {
            const tag = el.tagName.toLowerCase();
            seen[tag] = (seen[tag] ?? 0) + 1;
            const s = getComputedStyle(el);
            out.push({
              key: `${tag}#${seen[tag]}`,
              style: props.map((p) => `${p}:${s.getPropertyValue(p)}`).join(";"),
            });
          }
          return out;
        },
        { tags: TAGS, props: PROPS as unknown as string[] },
      );

      census[path] = rows;
      total += rows.length;
      perScreen.push(`${path}: ${rows.length}`);
    }

    writeFileSync(join(OUT, "census.json"), JSON.stringify(census, null, 2));

    // ⚠ NOT AN EMPTY LOOP. Twenty screens rendering nothing satisfies a
    // comparison trivially, and this file's siblings have both been that.
    expect(
      total,
      `the walk found almost no base elements — it has gone blind:\n  ${perScreen.join("\n  ")}`,
    ).toBeGreaterThan(1_000);

    // eslint-disable-next-line no-console
    console.log(`phase5 · ${total} element(s) across ${SCREENS.length} screens -> ${OUT}`);
  });
});
