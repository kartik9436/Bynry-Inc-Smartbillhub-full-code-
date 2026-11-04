// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 (the shell owns the app's URL shape and its nav config) ·
//           US-SHL-011 (the shared state an unrouted address renders)
//           Screens: every screen the sidebar points at
// Rules:    BR-SHL-001 (the sidebar IS the declared nav config) ·
//           BR-SHL-020 (plain-language state) · BR-SHL-025 (with its reason)
// ───────────────────────────────────────────────────────
// THE CHECK DEF-152 ASKED FOR, IN ITS OWN WORDS
// ══════════════════════════════════════════════════════════════════════════
//     "PREVENT: a check that no route reachable from the SIDEBAR falls through
//      to the catch-all — the sidebar is a finite, declared list, so this is
//      cheap and exact. Two screens have now reached users unbuilt and BOTH were
//      sidebar items; the pattern is not screens in general, it is top-level
//      navigation pointing at nothing."
//
// Both instances are the same shape and neither was found by a gate:
//
//   DEF-129  `/{tenant}/dashboard` — the first screen after EVERY sign-in. The
//            redirect pointed at a path no route declared.
//   DEF-152  `/{tenant}/reports` — one click from anywhere. The gap was known
//            and written in an App.tsx comment, three days later.
//
// WHY THIS LIVES IN VITEST AND NOT IN `10-scripts/gates/`. The question is
// "which component does React Router pick for this URL?", and the only exact
// answer is React Router's own. A Python gate would have to re-implement route
// ranking (static beats dynamic, longer beats shorter, `*` last) to read App.tsx
// statically, and a guard that re-implements the thing it guards is a guard that
// agrees with itself. So the REAL route table is mounted on a memory history and
// the real component tree is rendered — and `npm test` is merge-blocking in
// `.github/workflows/ci-frontend.yml`, so this is a gate in every sense that
// matters.
//
// PROVED RED BEFORE TRUSTED GREEN (hard-won law 7) — all three failures were
// produced and quoted in the lane report before this file was trusted:
//   1. with `/reports` removed from `UNBUILT_SIDEBAR_DESTINATIONS`, this file
//      fails naming `/reports`;
//   2. with `App.tsx` still mounting the old `ModulePlaceholder`, it fails on
//      the developer string;
//   3. with a nav item added that points at an undeclared path, it fails naming
//      that path — the general class, not just today's two.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import i18n from "@/i18n";
import { APP_ROUTES } from "@/App";
import { SHELL_NAV } from "@/components/AppShell";
import { UNBUILT_SIDEBAR_DESTINATIONS, unbuiltDestinationFor } from "@/components/NotBuiltYet";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SIDEBAR_DESTINATIONS } from "./sidebarDestinations";
import { ToastProvider } from "@/components/Toast";

const TENANT = "brazosbend";

/** The marker the catch-all — and ONLY the catch-all — puts on the page. */
const CATCH_ALL_MARKER = 'data-not-built-yet="true"';

const DANA: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

// Every A4 permission a System Admin holds that any sidebar destination gates
// on. A denied render is NOT a failure here (the route exists, which is what is
// being measured) — but a suite that measured routing through a permission
// decision would be measuring the wrong thing.
const ADMIN_PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    "settings_lookups",
    "user_management",
    "finance_reconcile_export",
    "reports",
    "plans_rates",
    "premises_units",
    "assets",
    "accounts",
    "meter_reads",
    "billing",
    "payments",
  ].map((code) => ({ code, label: code, access: "Full" as const })),
};

function RoutedApp() {
  return useRoutes(APP_ROUTES);
}

// ⚠ THE SHELL WILL NOT RENDER ITS OUTLET WITHOUT THIS, AND WITHOUT THE OUTLET
// THIS WHOLE SUITE MEASURED NOTHING — DEF-SHL-4277, found 2026-09-06 while
// adding `/runbooks` to the register.
//
// `ShellWithSession` returns `<LoadingSkeleton variant="card" />` whenever
// `tenantRegionalOf(regionalQuery.data)` is null — a deliberate gate, because a
// product that printed timestamps in a zone nobody chose is the defect it
// exists to prevent. With every query disabled, that data was `undefined`
// forever, so `renderAt` returned **389 characters of skeleton for every
// address in the product** and the `CATCH_ALL_MARKER` check below could never
// be true. `unreachable` was therefore always empty and the suite's central
// assertion PASSED over anything, in the exact shape hard-won law 7 calls
// *structurally incapable of failing*.
//
// It went unnoticed because the two assertions that WOULD have exposed it — the
// registered-copy one and the STALE ENTRY one — both loop over
// `UNBUILT_SIDEBAR_DESTINATIONS`, and that register has been EMPTY since
// `/work` became a real screen on 2026-09-03. An empty loop and a broken
// fixture look identical from the outside.
//
// So the regional settings are SEEDED rather than fetched. It is the smallest
// seed that satisfies the gate: a timezone and one of the seven formats
// `REGIONAL_DATE_FORMATS` declares. Everything else stays disabled, because
// this suite is still about ROUTING — a screen with no data renders its own
// honest loading state, which is still that screen.
//
// ⚠ **THE KEY MOVED ON 2026-09-06 (`DEF-SHL-4272`) AND THE GUARD ABOVE IS WHAT
// FOUND IT — ON THE VERY NEXT LANE, WITHIN THE HOUR OF BEING WRITTEN.** The
// shell used to boot on `GET /settings/regional`, which is Admin/Executive
// only, so a **Billing Clerk got 403 and every screen in the product rendered
// the shell's failure state** for sixteen days. It now boots on
// `GET /shell/display` — read-only, every signed-in role — and this fixture
// seeds that key instead. The self-check's own words were *"Seed whatever
// ShellWithSession now gates on"*, and this is that seed.
const REGIONAL_SEED = shellBootSeed({
  timezone: "America/Chicago",
  date_format: "MM/DD/YYYY",
});

function renderAt(url: string): string {
  const queryClient = new QueryClient({
    // Nothing may fetch: this suite is about ROUTING, so a screen with no seed
    // renders its own honest loading state, which is still that screen.
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, DANA);
  queryClient.setQueryData(queryKeys.myPermissions, ADMIN_PERMISSIONS);
  queryClient.setQueryData(queryKeys.shellDisplay, REGIONAL_SEED);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <RoutedApp />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Every destination the sidebar offers: the items and their declared children. */
function sidebarDestinations(): string[] {
  const paths: string[] = [];
  for (const item of SHELL_NAV) {
    if (!paths.includes(item.path)) {
      paths.push(item.path);
    }
    for (const child of item.children ?? []) {
      if (!paths.includes(child.path)) {
        paths.push(child.path);
      }
    }
  }
  return paths;
}

describe("DEF-152 — no sidebar destination falls through to the catch-all unannounced", () => {
  it("the fixture actually renders BELOW the shell — without this every check here is vacuous", () => {
    // Added 2026-09-06. The assertion that proves the assertions: if the shell
    // ever stops handing control to its Outlet in this fixture, `renderAt`
    // returns a skeleton for every address, `CATCH_ALL_MARKER` is never found,
    // and the reachability check below passes over a product where NOTHING
    // routes. That is what it did until this commit.
    //
    // `/dashboard` is a real screen and `/nowhere-at-all` is not, so a fixture
    // that works tells them apart. One that does not returns the same skeleton
    // for both — which is the exact false pass this guards.
    const dashboard = renderAt(`/${TENANT}/dashboard`);
    const nowhere = renderAt(`/${TENANT}/nowhere-at-all`);
    expect(
      nowhere.includes(CATCH_ALL_MARKER),
      "an unrouted address does not render the catch-all — the shell is showing its loading " +
        "skeleton instead of its Outlet, so every assertion in this file is measuring nothing. " +
        "Seed whatever ShellWithSession now gates on (today: shellDisplay).",
    ).toBe(true);
    expect(
      dashboard.includes(CATCH_ALL_MARKER),
      "/dashboard renders the catch-all, so this fixture cannot tell a real screen from a " +
        "missing one",
    ).toBe(false);
  });

  it("the sidebar is a finite declared list and this suite reads ALL of it", () => {
    // If the nav ever stops being enumerable, everything below silently passes
    // on an empty loop — which is the shape DEF-129 escaped in (bootApp waited
    // for the sidebar, and the sidebar rendered perfectly).
    const paths = sidebarDestinations();
    expect(paths.length).toBeGreaterThanOrEqual(SHELL_NAV.length);
    expect(paths).toContain("/dashboard"); // DEF-129's path
    expect(paths).toContain("/reports"); // DEF-152's path
  });

  it("every sidebar destination reaches a screen, or is a REGISTERED unbuilt one", () => {
    const unreachable: string[] = [];
    for (const path of sidebarDestinations()) {
      const markup = renderAt(`/${TENANT}${path}`);
      if (markup.includes(CATCH_ALL_MARKER) && unbuiltDestinationFor(path) === null) {
        unreachable.push(path);
      }
    }
    expect(
      unreachable,
      `${unreachable.length} sidebar destination(s) land on the catch-all with nothing written ` +
        `down: ${unreachable.join(", ")}. Build the screen, or add an entry to ` +
        `UNBUILT_SIDEBAR_DESTINATIONS saying what the user will be told instead. A top-level nav ` +
        `item pointing at nothing is DEF-129 and DEF-152, both of which reached production.`,
    ).toEqual([]);
  });

  it("no sidebar destination renders a developer string or the word null", () => {
    for (const path of sidebarDestinations()) {
      const markup = renderAt(`/${TENANT}${path}`);
      // The exact string that reached users twice, matched by its stable half.
      expect(markup, `${path} renders the W0 marker`).not.toContain("W0 scaffold");
      expect(markup, `${path} renders a scaffold string`).not.toMatch(/scaffold/i);
      // DEF-151's shape, on any screen: a JS null formatted into user-facing
      // text. `null USD`, `null%`, `>null<` — all of them are the same defect.
      expect(markup, `${path} renders a raw null`).not.toMatch(/>\s*null\b|\bnull [A-Z]{3}\b/);
    }
  });

  it("a REGISTERED destination says what it will do, in its own words", () => {
    const t = i18n.getFixedT("en");
    for (const entry of UNBUILT_SIDEBAR_DESTINATIONS) {
      const markup = renderAt(`/${TENANT}${entry.path}`);
      // Its own sentences, not the generic fallback: an entry in the register
      // is an obligation to explain, not permission to ship a blank page.
      expect(markup, `${entry.path} does not render ${entry.bodyKey}`).toContain(
        escapeHtml(t(entry.bodyKey)),
      );
      expect(markup, `${entry.path} does not render ${entry.waitingKey}`).toContain(
        escapeHtml(t(entry.waitingKey)),
      );
      expect(markup, `${entry.path} fell back to the generic sentence`).not.toContain(
        escapeHtml(t("shell.notBuilt.generic.body")),
      );
      // And a way out — a user who lands here has nothing else to click.
      expect(markup).toContain(`/${TENANT}/dashboard`);
    }
  });

  it("DEF-176: the browser smoke check's path list IS this nav, in both directions", () => {
    // `e2e/DEF-176-sidebar-smoke.spec.ts` walks every sidebar destination in a
    // real browser against a `load_sample_data` tenant, and it cannot import
    // SHELL_NAV: that config carries inline SVG icons as JSX and pulls in
    // AppShell.css, neither of which Playwright's transpiler handles. So the
    // paths live in `sidebarDestinations.ts` as plain data — and a second list
    // is only ever acceptable if something fails when it drifts.
    //
    // This is that something. Order included, because the smoke check reports
    // its results in nav order and a reader compares them against the sidebar
    // they are looking at.
    expect(SIDEBAR_DESTINATIONS as readonly string[]).toEqual(sidebarDestinations());
  });

  it("the register is EXACT in both directions — a stale entry fails, like G23/G25", () => {
    const declared = sidebarDestinations();
    for (const entry of UNBUILT_SIDEBAR_DESTINATIONS) {
      expect(
        declared,
        `${entry.path} is registered as an unbuilt SIDEBAR destination and the sidebar does not ` +
          `declare it`,
      ).toContain(entry.path);

      const markup = renderAt(`/${TENANT}${entry.path}`);
      expect(
        markup.includes(CATCH_ALL_MARKER),
        `STALE ENTRY: ${entry.path} now resolves to a real screen. Delete its line from ` +
          `UNBUILT_SIDEBAR_DESTINATIONS in the same commit that landed the screen — a register ` +
          `that keeps claiming debt it has paid off is how a gate stops being a gate (DEF-077).`,
      ).toBe(true);

      expect(entry.dated, `${entry.path} needs a YYYY-MM-DD date`).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(
        entry.reason.length,
        `${entry.path}'s reason is ${entry.reason.length} characters — a one-line reason is an ` +
          `allowlist. Say why it is unbuilt AND what closes it.`,
      ).toBeGreaterThanOrEqual(40);
    }
  });
});

/** React's server renderer escapes text; the expectations compare like for like. */
function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001@b16a4de (story+rules snapshot — 00-platform-shell/06-epics/EP-SHL-01-app-shell.md §US-SHL-001 · BR-SHL-001's nav config · 12-governance/10-defect-log.csv DEF-129 + DEF-152)
// generated: 2026-08-16 by story-coder (DEF-151/DEF-152 production-fix lane)
// checklist: A✔ B✔ C✔ D=deferred(no API call — this suite disables every query on purpose, so a screen with no seed still renders itself) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, three ways — register entry removed (fails naming /reports), App.tsx reverted to ModulePlaceholder (fails on the developer string), a nav item added pointing at an undeclared path (fails naming it). All three quoted verbatim in the lane report. tsc✔ eslint --max-warnings 0✔ vitest✔
// exceptions: (1) this measures ROUTING, not permissions: a destination that renders A18 §6 counts as REACHED, because the route exists and the refusal is the product working · (2) it reads SHELL_NAV, so a destination reachable only by typing a URL is out of scope by design — DEF-152's own prevention column scopes it to top-level navigation, which is where both escapes happened
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
