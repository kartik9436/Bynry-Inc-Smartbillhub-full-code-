// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 (the shell owns the app's URL shape and its nav config)
//           Screens: every screen the sidebar points at
// Rules:    BR-SHL-001 (the sidebar IS the declared nav config) ·
//           BR-SHL-044 (one page header, so every screen has a name) ·
//           B12 r3 §5 (FI-06 harness) · hard-won law 6 (look at the RENDERED
//           app) · hard-won law 7 (prove a new guard RED first)
// ───────────────────────────────────────────────────────
// THE GUARD DEF-176 ASKED FOR, IN ITS OWN WORDS.
//
//     "a route-level smoke check that signs in to a tenant loaded with
//      `load_sample_data` and visits every sidebar destination, asserting no
//      error boundary is rendered."
//
// ══════════════════════════════════════════════════════════════════════════
// WHY EVERY EXISTING CHECK MISSED A SCREEN THAT WAS COMPLETELY DEAD
// ══════════════════════════════════════════════════════════════════════════
// On 2026-08-16 the Finance screen rendered nothing at all — React Router's
// `Unexpected Application Error!`, no sidebar, no tabs — for anyone signed in to
// the seeded demo tenant. At that moment: 27 gates PASS, golden 33/33, 2,938
// backend tests and 1,250 frontend tests green.
//
// Every one of those looked at something other than the screen:
//
//   * `sidebarReachability.test.tsx` renders all 21 destinations against the
//     REAL route table and asserts none falls through to the catch-all — with
//     **every query disabled**. It proves ROUTING. A screen that routes
//     perfectly and then dies on its data passes it.
//   * the vitest component suites mount panels with fixtures that HAVE amounts.
//     S36's own suite passes `revenue_by_service: []`, so the table that killed
//     the route was never rendered with a row in it.
//   * the browser journeys drive seeded fixtures whose figures are computable.
//
// Only the DEMO TENANT — the one shaped like a real utility, without the year
// of history a real one would have — produces the absent set that broke it. So
// this check is deliberately the shallowest possible and the most real: sign in
// the way a human does, visit every destination the sidebar offers against a
// database `manage.py load_sample_data` built, and assert the app is still
// there. It knows nothing about what any screen contains, which is exactly why
// it cannot rot as the screens change.
//
// ══════════════════════════════════════════════════════════════════════════
// PROVED RED BEFORE TRUSTED GREEN
// ══════════════════════════════════════════════════════════════════════════
// Run against a build that crashes on the seeded demo tenant — `wire.py`
// serving `total_billed: null` at an UNGUARDED call site, and `MoneyCell`'s
// containment boundary removed, so the failure is the CLASS and not one bug —
// this spec fails, names the one destination that died out of twenty-one, and
// quotes what a person actually saw:
//
//     1 sidebar destination(s) rendered React Router's error boundary instead
//     of a screen, against a tenant seeded by `manage.py load_sample_data`. …
//     /finance → "Unexpected Application Error! MoneyCell was handed an absent
//      amount for USD. A figure the books will not state is rendered by
//      AbsentFigure WITH its reason — never as money, and never as a zero
//      (DEF-151). …"
//
// Against the fixed build on the same tenant: 2 passed, 22 browser assertions,
// 1.2 minutes for all twenty-one destinations.
//
// ══════════════════════════════════════════════════════════════════════════
// HOW TO RUN IT — IT NEEDS A SEEDED TENANT, AND IT SAYS SO WHEN IT HAS NONE
// ══════════════════════════════════════════════════════════════════════════
//     E2E_BASE_URL=http://127.0.0.1:8099 \
//     E2E_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//     npx playwright test e2e/DEF-176-sidebar-smoke.spec.ts
//
// `skipUnlessAppServer` makes a missing app a SKIP rather than a red, the same
// posture as every other UI spec here. What it must never become is DEF-057's
// shape — a job whose only outcomes are "skipped" and "skipped" — so the first
// test asserts the destination list is non-empty and holds the two paths that
// have already reached users broken, and `support/census.ts` fails a run that
// executed no browser assertion at all.
import { expect, test } from "@playwright/test";

import { SIDEBAR_DESTINATIONS } from "../src/routing/sidebarDestinations";

import { baseUrl, signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

/** React Router's default boundary. It is ENGLISH and it is React's, not this
 *  product's copy, so matching its text is safe from the catalogues — and this
 *  app declares no `errorElement`, so nothing else can print it. */
const ROUTER_BOUNDARY = "Unexpected Application Error";

/** The shell's content pane (`AppShell.tsx` renders `<main className="view">`).
 *  Its ABSENCE is the tell: the boundary replaces the whole tree, sidebar
 *  included, so a crashed route has no pane at all. */
const CONTENT_PANE = "main.view";

/** After the router has swapped panes, how long the screen gets to finish
 *  fetching and re-render. Measured, not guessed: on this stack S36 paints its
 *  header immediately and resolves `GET /finance/revenue-ar` ~1.2 s later, and
 *  the crash is in that second render. */
const SETTLE_MS = 2_500;

test.describe("DEF-176 — every sidebar destination still renders against a seeded tenant", () => {
  test("the list this spec walks is the real sidebar, and it is not empty", () => {
    // Without this, a broken import or an emptied list would turn the walk
    // below into a loop over nothing that reports itself as a pass.
    expect(SIDEBAR_DESTINATIONS.length).toBeGreaterThanOrEqual(20);
    expect(SIDEBAR_DESTINATIONS).toContain("/dashboard"); // DEF-129's path
    expect(SIDEBAR_DESTINATIONS).toContain("/reports"); // DEF-152's path
    expect(SIDEBAR_DESTINATIONS).toContain("/finance"); // DEF-176's path
  });

  test("no destination renders an error boundary @app-server", async ({ page }) => {
    // Twenty-one destinations. The default 90 s budget is a per-TEST budget and
    // this is one test walking a whole product, so it is raised explicitly
    // rather than by splitting the walk into twenty-one tests that would each
    // pay the sign-in cost.
    test.setTimeout(600_000);
    await signIn(page);

    const dead: string[] = [];
    for (const path of SIDEBAR_DESTINATIONS) {
      // CLIENT-SIDE navigation, which is what a person clicking the sidebar
      // actually does — `<Link>` pushes onto history and the router re-renders;
      // it does not reload the page. It is also the only affordable way to walk
      // twenty-one destinations: `vite build` emits ONE 5.7 MB chunk (it says so
      // on every build) and a full reload of it costs ~13 s in this sandbox, so
      // `page.goto` per destination is four and a half minutes of parsing the
      // same bundle. The nav LINKS themselves are not clicked because the
      // sidebar reveals a group's children only when that group is open, and a
      // smoke check that had to drive the disclosure would be testing the
      // sidebar rather than the screens.
      await page.evaluate((to) => {
        window.history.pushState({}, "", to);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }, `/${tenant()}${path}`);
      await page.waitForURL((url) => url.pathname === `/${tenant()}${path}`, { timeout: 30_000 });

      // ⚠ WAIT FOR THE DATA, NOT FOR THE PAINT — THIS IS THE WHOLE CHECK.
      //
      // Two earlier versions of this loop passed against a screen this lane had
      // just watched die in the same browser, and both mistakes are worth
      // keeping written down because they are the ones the engineering plan's
      // step 2d names ("three lanes shipped a browser check that PASSED against
      // the broken screen"):
      //
      //   1. waiting for "a `main.view` holding a heading" — `AppShell` is a
      //      LAYOUT route, so that pane is the SAME element on every
      //      destination and never goes away between them. The condition was
      //      true before React had swapped anything.
      //   2. waiting for a pane the previous screen had not been stamped on —
      //      same reason, the stamp is still on it.
      //
      // What is actually true of the defect: S36 painted its header and tab
      // strip immediately, and only when `GET /finance/revenue-ar` RESOLVED did
      // one table cell take the route down. So the wait that matters is for the
      // network to go quiet and then for React to commit. `networkidle` carries
      // an EXPLICIT budget because `waitForLoadState` otherwise inherits the
      // test's, which is ten minutes here — an unbounded one on a polling
      // screen hangs the whole run and reports nothing, which is what the
      // second version did.
      await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => undefined);
      await page.waitForTimeout(SETTLE_MS);

      // TWO TELLS, because the boundary replaces the WHOLE tree: its text, and
      // the disappearance of the shell's own content pane. The second is what
      // makes this independent of React Router's English copy.
      const boundaryText = (await page.getByText(ROUTER_BOUNDARY).count()) > 0;
      const shellGone = (await page.locator(CONTENT_PANE).count()) === 0;
      if (boundaryText || shellGone) {
        const said = (await page.locator("body").innerText()).replace(/\s+/g, " ").trim();
        dead.push(`${path} → ${JSON.stringify(said.slice(0, 400))}`);
        // The boundary replaces the whole tree, so a client-side push into the
        // wreckage would report every REMAINING destination as dead too. A full
        // reload puts the app back and keeps the list of casualties honest.
        await page.goto(`${baseUrl()}/${tenant()}${SIDEBAR_DESTINATIONS[0]}`);
        await page.locator(CONTENT_PANE).waitFor({ state: "attached", timeout: 60_000 });
        continue;
      }
      // Not crashed: the shell must still be framing SOMETHING. An empty pane
      // is DEF-129's shape and is a failure of its own.
      const framed = (await page.locator(CONTENT_PANE).innerText()).trim();
      expect(framed, `${path} rendered an EMPTY content pane — the shell framed nothing`).not.toBe(
        "",
      );
    }

    expect(
      dead,
      `${dead.length} sidebar destination(s) rendered React Router's error boundary instead of ` +
        `a screen, against a tenant seeded by \`manage.py load_sample_data\`. This is DEF-176: ` +
        `one uncomputable figure reaching an unguarded MoneyCell deletes the WHOLE route, ` +
        `sidebar and all. The screen must branch on the absence and render AbsentFigure with ` +
        `its reason.\n\n${dead.join("\n\n")}`,
    ).toEqual([]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001 + 12-governance/10-defect-log.csv DEF-176 (its own PREVENT column)
// generated: 2026-08-16 by story-coder (DEF-176 finance-route outage lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — against a build carrying an injected `total_billed: null` at an unguarded call site with the containment boundary removed, it FAILED naming /finance and quoting the boundary verbatim (1 of 21 dead, no cascade); against the fixed build on the same tenant, 2 passed / 22 browser assertions / 1.2 min. ⚠ AND IT PASSED TWICE ON A SCREEN THIS LANE HAD JUST WATCHED DIE before it was trusted — both false greens are written into the loop's own comment, because both were the engineering plan's step 2d failure ("a browser check that PASSED against the broken screen") and only running it against a known-crashing build found them. tsc -p tsconfig.e2e.json✔ · eslint --max-warnings 0✔
// exceptions: (1) it asserts the app EXISTS and nothing about what any screen contains — a smoke check that knew each screen's copy would rot on the next design change and would stop being cheap · (2) it walks the SIDEBAR only, which is DEF-152's own scoping: a destination reachable solely by typing a URL is out of scope · (3) it needs a seeded tenant and SKIPS without one; the shared list guard above is what stops that becoming a silent no-op
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
