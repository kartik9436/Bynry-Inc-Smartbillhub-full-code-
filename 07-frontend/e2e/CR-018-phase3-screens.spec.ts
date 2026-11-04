// ── Trace ──────────────────────────────────────────────
// Change:   CR-018 Phase 3 — migrate the shared BUTTON family's call sites to
//           the component API (PO ruling 2026-08-19, "Route B").
// Rules:    CR-018 §6 "Every screen renders identically to its pre-migration
//           self … plus before/after screenshots" · DEF-316 (a full-page shot
//           captures only the viewport unless the inner scroller is released)
// Impacts:  nothing in src/ — an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// Four screens, chosen for BUTTON DENSITY rather than importance, because the
// thing being migrated is buttons and a screen with two of them proves two:
//
//   /dashboard                          the low end — a header and a KPI strip
//   /assets                             list + row actions + a guarded control
//   /settings/reference-data            the high end — icon buttons in rows,
//                                       and the descendant rule
//                                       `.settings-row-actions .btn`
//   /settings/reference-data/templates  the chip strip, whose class name is
//                                       assembled from state at runtime
//
// It writes a PNG (what a person sees) and a per-button computed-style census
// (why). Run it once at the tip, once after the migration, into DIFFERENT
// directories, and diff the two outside the test — a second run into the same
// directory overwrites the "before" and the comparison then passes vacuously.
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npm run build && \
//       E2E_BASE_URL=http://127.0.0.1:8080 CR018_OUT=/tmp/cr018p3/before \
//       npx playwright test e2e/CR-018-phase3-screens.spec.ts
//
// ⚠ REBUILD FIRST — boot_stack serves dist/.
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { baseUrl, expandInnerScroller, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const OUT = process.env.CR018_OUT ?? "/tmp/cr018p3/shot";

const SCREENS = [
  { name: "dashboard", path: "/dashboard" },
  { name: "assets", path: "/assets" },
  { name: "reference-data", path: "/settings/reference-data" },
  { name: "templates", path: "/settings/reference-data/templates" },
] as const;

/** Everything a button migration can plausibly move. Geometry is included on
 *  purpose: a padding that changed by 0.4px is a diff line here and is
 *  invisible in a PNG at this scale. */
const PROPS = [
  "display",
  "align-items",
  "justify-content",
  "gap",
  "margin",
  "padding",
  "border-width",
  "border-style",
  "border-color",
  "border-radius",
  "background-color",
  "color",
  "opacity",
  "cursor",
  "font-family",
  "font-size",
  "font-weight",
  "line-height",
  "text-decoration-line",
  "text-align",
  "white-space",
  "width",
  "height",
] as const;

test.describe("CR-018 Phase 3 — the four button-density screens", () => {
  test("photographed and measured @app-server", async ({ page }) => {
    test.setTimeout(600_000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await signIn(page);

    mkdirSync(OUT, { recursive: true });
    let totalButtons = 0;

    for (const screen of SCREENS) {
      await page.goto(`${baseUrl()}/${tenant()}${screen.path}`);
      await page.waitForSelector("main.view", { timeout: 30_000 });
      await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
      await page.waitForTimeout(2_500);

      const census = await page.evaluate(
        (props) => {
          // Keyed by TREE POSITION and visible text, never by class list — the
          // class list is exactly what this migration deletes, so keying on it
          // would make every row a rename and the diff unreadable.
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
          // Every clickable, whatever it is built from — the kit is applied to
          // <button>, <a>, <summary> and a router <Link> (which renders an <a>).
          for (const el of Array.from(main.querySelectorAll("button, a, summary"))) {
            const cs = getComputedStyle(el);
            const row: Record<string, string> = {
              "#text": (el.textContent ?? "").trim().slice(0, 40),
            };
            for (const p of props) row[p] = cs.getPropertyValue(p);
            const box = el.getBoundingClientRect();
            row["#box"] =
              `${Math.round(box.width * 100) / 100}×${Math.round(box.height * 100) / 100}`;
            out[pathOf(el)] = row;
          }
          return out;
        },
        PROPS as unknown as string[],
      );

      const count = Object.keys(census).length;
      totalButtons += count;
      expect(count, `${screen.name} rendered no clickable at all`).toBeGreaterThan(0);
      writeFileSync(join(OUT, `${screen.name}.json`), `${JSON.stringify(census, null, 1)}\n`);

      // DEF-316: without this the full-page shot captures 900px of a much
      // taller page, and two truncated shots match each other perfectly.
      await expandInnerScroller(page);
      await page.screenshot({ path: join(OUT, `${screen.name}.png`), fullPage: true });
    }

    // eslint-disable-next-line no-console
    console.log(
      `CR-018 Phase 3 screens: ${totalButtons} clickables across ${SCREENS.length} screens → ${OUT}`,
    );
    expect(totalButtons, "the walk measured almost nothing").toBeGreaterThan(40);
  });
});
