// ── Trace ──────────────────────────────────────────────
// Change:   PO ruling 2026-08-20 — "Icons everywhere, per r10 and rule 15.
//           Convert ~40 buttons in 10 files… it needs a browser walkthrough,
//           not a green suite."
// Rules:    B14 rule 15 (row actions are ICONS with tooltips, never text links)
// Defects:  DEF-337 (the defect this closes) · DEF-342 (closes with it)
// Impacts:  nothing in src/ — an instrument, not a screen.
// ───────────────────────────────────────────────────────
//
// THE BROWSER HALF OF RULE 15's GUARD.
//
// `10-scripts/gates/g37_row_actions.py` reads SOURCE and can prove that every
// row action goes through `RowAction` and that `RowAction` writes an
// `aria-label`. It cannot prove that the attribute survives to the DOM, that
// the glyph is visible, or that the cell holds no stray word — and hard-won law
// 6 is blunt about which of those matters: no gate looks at rendered output,
// and nine defects in one day were found by diffing the running app against the
// prototype and by nothing else.
//
// ⚠ DEF-337's PREVENTION COLUMN ASKS FOR EXACTLY THIS AND SAYS WHY IT MUST GO
// RED TWICE: *"it must contain an icon control with an accessible name, and no
// bare text link… once on a text link, once on an icon with no accessible
// name, because the second is the failure the obvious check misses."* An icon
// with no name renders beautifully and passes every text-absence assertion.
//
//     ./08-qa/01-e2e/stack/boot_stack.sh
//     cd 07-frontend && npm run build && \
//       E2E_BASE_URL=http://127.0.0.1:8080 \
//       npx playwright test e2e/CR-018-rule15-row-actions.spec.ts
//
// ⚠ REBUILD FIRST — boot_stack serves dist/.
import { expect, test } from "@playwright/test";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

/**
 * Every screen the ruling converted, plus the seven that were already icons —
 * because a rule that holds only where somebody just worked is not a rule.
 *
 * A settings SUB-tab needs a real load to mount, which is why they carry the
 * full path rather than being reached by clicking.
 *
 * ⚠ FIVE OF THESE PATHS WERE WRONG ON THE FIRST RUN AND THE TEST PASSED ANYWAY.
 * `/units`, `/finance/chart-of-accounts`, `/settings/reference-data` (with no
 * `?list=`), `/settings/custom-fields` and `/settings/rules` all rendered ZERO
 * row actions — four of them are not routes at all — and the run reported
 * "641 row actions, all named" over a walk that never reached five screens.
 * The global `> 20` floor is what let it: it is satisfied by two screens.
 *
 * That is DEF-057's shape and this spec's own comment warned about it one
 * paragraph earlier, which is the useful part — a warning in prose does not
 * check anything. Every screen now declares what it must find, so a wrong path
 * is a FAILING screen rather than a quiet zero.
 */
const SCREENS = [
  { name: "assets", path: "/assets" },
  { name: "premises", path: "/premises" },
  { name: "units", path: "/premises/units" },
  { name: "plans-rates", path: "/plans-rates" },
  { name: "finance-gl", path: "/finance/gl?view=chart" },
  { name: "settings-users", path: "/settings/users" },
  { name: "settings-reference-data", path: "/settings/reference-data?list=uoms" },
  // ⚠ EXEMPT, WITH A REASON. `CustomField` has no seeder anywhere in
  // 06-backend/apps/**, so the demo fixture holds zero rows and this
  // screen renders an empty state. Its row actions are therefore
  // verifiable by NOTHING — not this spec and not a human clicking —
  // until the fixture grows one. That is a coverage gap and it is
  // written down rather than passed over in silence.
  { name: "settings-custom-fields", path: "/settings/reference-data?list=custom_fields", expectEmpty: true },
  // The allocation-order arrows live on BILLING DEFAULTS, not finance
  // controls — `choice_sequence` is declared there (settingsRulePages.ts).
  { name: "settings-billing-defaults", path: "/settings/reference-data?list=billing_defaults" },
  { name: "settings-templates", path: "/settings/reference-data/templates" },
  { name: "settings-routes-cycles", path: "/settings/routes-cycles" },
  { name: "settings-services", path: "/settings/services" },
  { name: "settings-accounting", path: "/settings/accounting" },
] as const;

interface CellFinding {
  screen: string;
  cells: number;
  actions: number;
  nameless: string[];
  wordy: string[];
  glyphless: string[];
}

test.describe("B14 rule 15 — every row action is an icon with an accessible name", () => {
  test("no ACTIONS cell holds a bare word, and no glyph is nameless @app-server", async ({
    page,
  }) => {
    test.setTimeout(600_000);
    await signIn(page);

    const findings: CellFinding[] = [];

    for (const screen of SCREENS) {
      await page.goto(`${baseUrl()}/${tenant()}${screen.path}`);
      await page
        .waitForLoadState("networkidle", { timeout: 8_000 })
        .catch(() => undefined);
      // Wait for the DATA, not the paint (DEF-176's lesson): a list's rows do
      // not exist until they arrive, and a check that ran on first paint would
      // count ZERO cells and pass — the exact way a walkthrough lies.
      await page.waitForTimeout(1_500);

      findings.push(
        await page.evaluate((name) => {
          // A row action is identified by what the kit STAMPS on it, not by a
          // class name: `data-size="row"` is written by `buttonKit`, one place.
          const controls = Array.from(
            document.querySelectorAll<HTMLElement>('[data-size="row"]'),
          ).filter((el) => {
            const s = getComputedStyle(el);
            return s.display !== "none" && s.visibility !== "hidden";
          });

          const cells = new Set(
            controls.map((el) => el.closest("td,th,li,div")).filter(Boolean),
          );

          const label = (el: HTMLElement) => el.getAttribute("aria-label") ?? "";
          const nameless = controls
            .filter((el) => label(el).trim() === "")
            .map((el) => el.outerHTML.slice(0, 140));

          // A glyph, not a word. Everything a row action renders must be an
          // <svg> or an element drawn purely by CSS (the services on/off ring),
          // never text content.
          const wordy = controls
            .filter((el) => (el.textContent ?? "").trim() !== "")
            .map((el) => `${label(el)}: "${(el.textContent ?? "").trim()}"`);

          const glyphless = controls
            .filter((el) => el.querySelector("svg") === null && el.children.length === 0)
            .map((el) => label(el) || el.outerHTML.slice(0, 140));

          return {
            screen: name,
            cells: cells.size,
            actions: controls.length,
            nameless,
            wordy,
            glyphless,
          };
        }, screen.name),
      );
    }

    // ⚠ THE WALK MUST NOT BE AN EMPTY LOOP. Thirteen screens that render zero
    // row actions would pass every assertion below. A suite that silently
    // proves nothing and reports it as an answer is DEF-057's shape.
    const total = findings.reduce((n, f) => n + f.actions, 0);
    const evidence = findings
      .map((f) => `${f.screen}: ${f.actions} action(s) in ${f.cells} cell(s)`)
      .join("\n  ");
    expect(total, `no row actions were found at all:\n  ${evidence}`).toBeGreaterThan(20);

    // ...and EVERY screen must have been reached. A global floor is satisfied
    // by two busy screens while eleven render nothing, which is exactly how the
    // first run of this spec reported a clean product over five broken paths.
    const exempt = new Set(SCREENS.filter((s) => "expectEmpty" in s).map((s) => s.name));
    expect(
      findings.filter((f) => f.actions === 0 && !exempt.has(f.screen)).map((f) => f.screen),
      `screen(s) rendered NO row actions — a wrong path, an empty fixture or a ` +
        `cell that never converted, and all three are failures here:\n  ${evidence}`,
    ).toEqual([]);

    // ...and an exemption must still be TRUE. A screen listed as empty that
    // starts rendering rows is a fixture that grew, and the exemption has to
    // come off — otherwise the list quietly becomes the place checks go to die.
    expect(
      findings.filter((f) => exempt.has(f.screen) && f.actions > 0).map((f) => f.screen),
      "screen(s) marked expectEmpty now render row actions — the fixture grew, " +
        "so remove the exemption and let them be checked",
    ).toEqual([]);

    const nameless = findings.filter((f) => f.nameless.length > 0);
    expect(
      nameless.map((f) => `${f.screen}: ${f.nameless.join(" | ")}`),
      "a row action with no accessible name renders beautifully, passes every " +
        "text-absence check in the suite, and cannot be used without a mouse",
    ).toEqual([]);

    const wordy = findings.filter((f) => f.wordy.length > 0);
    expect(
      wordy.map((f) => `${f.screen}: ${f.wordy.join(" | ")}`),
      "DEF-337: row actions are icons, never text links — this is what " +
        '"four red words in one cell" looks like to a check',
    ).toEqual([]);

    const glyphless = findings.filter((f) => f.glyphless.length > 0);
    expect(
      glyphless.map((f) => `${f.screen}: ${f.glyphless.join(" | ")}`),
      "an icon control that renders NOTHING is a 32x32 hole — it passes the " +
        "no-text check and the accessible-name check together",
    ).toEqual([]);

    // eslint-disable-next-line no-console
    console.log(`rule 15 · ${total} row action(s):\n  ${evidence}`);
  });

  test("DEF-342 — one row-action size, not two @app-server", async ({ page }) => {
    // Thirteen full loads of a 6.4 MB chunk. The default 90 s is a single
    // navigation's budget and this walks the product.
    test.setTimeout(600_000);
    await signIn(page);
    const shapes = new Set<string>();

    for (const screen of SCREENS) {
      await page.goto(`${baseUrl()}/${tenant()}${screen.path}`);
      await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
      await page.waitForTimeout(1_200);
      for (const shape of await page.evaluate(() =>
        Array.from(document.querySelectorAll<HTMLElement>('[data-size="row"]')).map((el) => {
          const s = getComputedStyle(el);
          return `${s.width}x${s.height} pad ${s.padding} type ${s.fontSize}`;
        }),
      )) {
        shapes.add(shape);
      }
    }

    // `row` and `settings-row` were 0 8px and 2px 6px — two sizes under one
    // conforming font size, which is all DEF-342 ever was. One content, one box.
    expect(
      [...shapes],
      `row actions render ${shapes.size} distinct shapes: ${[...shapes].join("  ·  ")}`,
    ).toHaveLength(1);
  });
});
