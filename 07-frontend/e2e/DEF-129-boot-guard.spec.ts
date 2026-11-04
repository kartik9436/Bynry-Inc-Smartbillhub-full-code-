// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-019 (S7 — the landing screen)   Screens: S7
// Rules:    BR-SHL-044 (one page header, so every screen has a name) ·
//           B12 r3 §5 (FI-06 harness) · hard-won law 7 (prove a new guard RED
//           before trusting it green)
// ───────────────────────────────────────────────────────
// THE GUARD THAT WOULD HAVE CAUGHT DEF-129, PROVED AGAINST THE DEFECT ITSELF.
//
// DEF-129's escape route, in one sentence from its own row: *"the E2E helper
// bootApp() waits for the SIDEBAR to appear and then proceeds. The sidebar
// renders perfectly. So every journey that signs in walked straight past a
// blank landing screen."*
//
// `expectScreenInContentPane` closes that. This file is the proof that it
// actually bites, and it is SERVER-FREE on purpose — it builds the pre-fix page
// shape with `setContent` rather than needing an app, so it runs on every CI
// job and cannot quietly become a test whose only outcomes are "skipped" and
// "skipped" (DEF-057's shape, which this suite has already met once).
//
// Three cases, and the FIRST one is the whole point: the guard must fail on the
// exact markup the product shipped on 2026-08-15.
import { expect, test } from "@playwright/test";

import { expectScreenInContentPane } from "./support/app";

/** The shell as it rendered on the day of the defect: a perfect sidebar, and a
 *  content pane holding the developer string. Copied from the shape
 *  `AppShell.tsx` emits (`<main className="view">`) and `ModulePlaceholder`
 *  rendered into it (`<p>{t("w0.scaffold")}</p>`).
 *
 *  KEPT after DEF-152 retired that string, because it is the historical record
 *  of what shipped — but it is no longer what the guard MATCHES, and pretending
 *  otherwise is how a guard quietly stops guarding (see CATCH_ALL below). */
const PRE_FIX_SHELL = `
  <div class="shell">
    <nav aria-label="Main navigation"><a href="/x/dashboard">Dashboard</a></nav>
    <main class="view"><p>SMARTBillHub — W0 scaffold</p></main>
  </div>`;

/** THE CATCH-ALL AS IT RENDERS TODAY (DEF-152): honest copy, a real `<h1>`, a
 *  link out — and the one structural marker that says it is not a screen.
 *
 *  This fixture is the reason the guard had to change. Every text-based check
 *  passes over this pane: it has a heading, it has prose, it has no developer
 *  string. Only `[data-not-built-yet]` distinguishes it, which is why the guard
 *  matches THAT and not the copy. */
const CATCH_ALL = `
  <div class="shell">
    <nav aria-label="Main navigation"><a href="/x/dashboard">Dashboard</a></nav>
    <main class="view"><div class="page-header"><h1>Reports</h1></div>
      <div class="not-built" data-not-built-yet="true">
        <p class="not-built-body">The report library will list every report this product can
        run.</p><a href="/x/dashboard">Back to Dashboard</a></div></main>
  </div>`;

/** The same shell with a real screen in it — a page header with a name. */
const BUILT_SCREEN = `
  <div class="shell">
    <nav aria-label="Main navigation"><a href="/x/dashboard">Dashboard</a></nav>
    <main class="view"><div class="page-header"><h1>Welcome back, Dana Whitfield.</h1></div>
      <div class="kpi-grid"><div class="kpi"><span class="k">AR outstanding</span>
      <span class="v">$152.32</span></div></div></main>
  </div>`;

/** A pane the shell framed and nothing filled — the other way to ship nothing. */
const EMPTY_PANE = `
  <div class="shell">
    <nav aria-label="Main navigation"><a href="/x/dashboard">Dashboard</a></nav>
    <main class="view"></main>
  </div>`;

test.describe("DEF-129 — the boot guard looks INSIDE the frame", () => {
  test("it FAILS on the exact pane the product shipped (the defect itself)", async ({ page }) => {
    await page.setContent(PRE_FIX_SHELL);
    // The chrome check that used to be the whole of `bootApp` still passes here
    // — which is precisely why it was never enough.
    await page.getByRole("navigation", { name: "Main navigation" }).waitFor();

    // A bare `<p>` and no heading: the guard refuses it for having no screen
    // name, which is the other half of the assertion and the half that survives
    // the marker string being retired.
    let failed = false;
    try {
      await expectScreenInContentPane(page, "/brazosbend/dashboard");
    } catch {
      failed = true;
    }
    expect(failed, "the pane the product shipped must not pass the boot guard").toBe(true);
  });

  test("DEF-152: it FAILS on the catch-all's HONEST state, which has a heading and prose", async ({
    page,
  }) => {
    // The one the old text match would sail past. An unbuilt destination is a
    // legitimate STATE and is still not a SCREEN, and this is the assertion
    // that keeps DEF-152's fix from disarming DEF-129's guard.
    await page.setContent(CATCH_ALL);
    await page.getByRole("navigation", { name: "Main navigation" }).waitFor();

    await expect(expectScreenInContentPane(page, "/brazosbend/reports")).rejects.toThrow(
      /not-built-yet state, not a screen/,
    );
  });

  test("it FAILS on a pane the shell framed and nothing filled", async ({ page }) => {
    await page.setContent(EMPTY_PANE);
    // try/catch rather than `expect().rejects`: the guard's own 15-second wait
    // is longer than the assertion timeout, and a guard test that fails on its
    // own harness rather than on the thing it guards teaches nothing.
    let failed = false;
    try {
      await expectScreenInContentPane(page, "/brazosbend/dashboard");
    } catch {
      failed = true;
    }
    expect(failed, "an empty content pane must not pass the boot guard").toBe(true);
  });

  test("it PASSES on a built screen, so it is a guard and not a blanket refusal", async ({
    page,
  }) => {
    await page.setContent(BUILT_SCREEN);
    await expectScreenInContentPane(page, "/brazosbend/dashboard");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-REP-019@f9ccd14 (DEF-129's PREVENT column: "bootApp() must assert something in the CONTENT pane, not only the chrome")
// screens: S7   (DEF-137's screen-id stamp — see 10-scripts/gates/g25_screen_coverage.py)
// generated: 2026-08-16 by story-coder (DEF-129 lane)
// checklist: A✔ B✔ C✔ D=deferred(no API call — this spec needs no server, deliberately) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED against the REAL pre-fix bundle as well as this fixture — with the S7 route removed and the bundle rebuilt, the OLD helper PASSED over a content pane reading "SMARTBillHub — W0 scaffold" and the NEW one failed naming it. Quoted verbatim in the lane report.
// exceptions: (1) SERVER-FREE by design — `setContent` builds the pre-fix shape, so this runs on every CI job rather than skipping when no stack is up. DEF-057 is the reason that matters: a check whose only outcomes are "skipped" and "skipped" is not a check · (2) it asserts a HEADING and the absence of the scaffold marker, and nothing about what any particular screen contains — a guard that knew each screen's contents would have to be edited by every lane and would rot
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
