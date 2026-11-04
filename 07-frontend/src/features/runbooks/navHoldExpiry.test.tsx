// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 (the shell owns the app's URL shape and its nav config)
//           Screens: RBS-001 (Runbooks home) — BUILT 2026-09-06 by CR-075 wave
//           D task D2, and this file turned around in the SAME COMMIT
// Rules:    BR-SHL-001 amendment 3 (PO 2026-09-06, "Nav bar will have Runbook
//           as menu item - above reports module") · CLAUDE.md hard-won law 2,
//           mirror clause ("when you write a hold, write the test that fires
//           when the hold expires, in the same commit — assert the destination
//           by ADDRESS and by the screen id it opens")
// Defects:  DEF-CWP-3925 (eight of a page's doors still refusing over screens
//           that had shipped days earlier, every check green)
// Impacts:  07-frontend/src/components/AppShell.tsx (SHELL_NAV) ·
//           07-frontend/src/components/NotBuiltYet.tsx
//           (UNBUILT_SIDEBAR_DESTINATIONS) · CR-075 wave D
// ───────────────────────────────────────────────────────
// THE HOLD THIS FILE EXISTED TO KILL — AND IT KILLED IT, THE SAME DAY
// ══════════════════════════════════════════════════════════════════════════
// On 2026-09-06 the PO put **Runbooks** on the rail above Reports. The module
// behind it was real — CR-075 waves A and B had landed
// `06-backend/apps/runbooks`, its contract and its conformance suite — but its
// first screen, **RBS-001** (the Runbooks home), was wave D. So for a few hours
// the nav item resolved to the honest not-built-yet screen, with a dated row in
// `UNBUILT_SIDEBAR_DESTINATIONS` saying what it would do and what it waited on.
//
// **That row was a rule with a CLOCK in it**, and this file was the clock.
// CR-075 wave D task D2 landed `RBS-001` at `/{tenant}/runbooks` later the same
// day; the register row was deleted in the SAME COMMIT and the four assertions
// below were TURNED AROUND rather than deleted. They now hold the opposite
// claim, which is the only claim worth keeping: **this address opens RBS-001,
// by address and by screen id, and no register entry says otherwise.**
//
// Deleting them instead would have been the quiet failure this whole file is
// about. DEF-CWP-3925: the customer portal's front page had **two working doors
// out of eight**, five cards and the sign-in bar still refusing over screens
// that had shipped days earlier, with `tsc`, 42 portal test files, 391 cases
// and every gate green over it. Each wave had tested ITS OWN screen at ITS OWN
// address, and the question *has the door started pointing at it* belonged to
// nobody. It belongs to this file, before and after the hold.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY TWO ASSERTIONS AND NOT ONE — ADDRESS **AND** SCREEN ID
// ══════════════════════════════════════════════════════════════════════════
// Law 7 records a hold-expiry test that asserted a screen was REGISTERED at an
// address while the router was mounting it somewhere else: both screens opened
// onto "not built yet" and every check passed. A hold-expiry test that reads
// only a register is reading OUR CLAIM about the product, not the product.
//
// So this file asserts the two halves separately, and each fails on its own:
//
//   1. **BY ADDRESS.** The REAL route table (`APP_ROUTES`) is mounted on a
//      memory history at `/{tenant}/runbooks` and asked what React Router
//      picks. The answer must NOT be the catch-all, and no register row may
//      claim the address is unbuilt.
//   2. **BY SCREEN ID.** The same markup must carry `data-screen="RBS-001"`.
//      Every screen in this product stamps its id on its own root (the
//      convention `RunbookSetup.tsx` and 72 portal files already follow), so
//      this fails if the Runbooks home is replaced, renamed, or if the router
//      starts mounting something else at the nav item's address.
//
// Assertion 1 catches "nothing is here". Assertion 2 catches "something is
// here and it is not the screen the rail promises", which is the failure law 7
// says a single address check cannot see — it records a hold-expiry test that
// asserted a screen was REGISTERED at an address while the router mounted it
// elsewhere, with every check green over both.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT COVERS THIS AND WHAT DOES NOT — STATED, NOT ASSUMED (law 1, law 7)
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **`G103` (`10-scripts/gates/g103_holds_cannot_rot.py`) DOES NOT SEE THIS
// HOLD, AND IT IS THE GATE WHOSE WHOLE JOB IS ROTTING HOLDS.** It loads only
// front-end files whose path starts with `portal/`, plus files matching
// `data-screen="CWP-\d+"`. `AppShell.tsx`, `NotBuiltYet.tsx` and this file are
// none of those, so G103 will keep reporting PASS over a Runbooks nav entry
// that has rotted — truthfully, of everything it can see. That is law 7's
// *reporting zero over a scope it silently excludes*, and the honest response
// is to say the number: **G103 covers 36 portal holds and 0 staff-app holds.**
// This suite is the staff app's only cover for this one.
//
// ⚠ `sidebarReachability.test.tsx` DOES have a STALE ENTRY check that fires on
// the same event, and it is not redundant with this file: it walks every rail
// path generically and says "a register entry outlived its screen". It cannot
// say WHICH screen id was expected, and it does not read `data-screen` at all.
// Two tests failing on one event is the cheap half of this problem.
//
// ══════════════════════════════════════════════════════════════════════════
// PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (law 7, both halves)
// ══════════════════════════════════════════════════════════════════════════
// **WHEN THE HOLD STOOD** it was proved through `./node_modules/.bin/vitest` —
// the same runner CI uses — with a temporary `/runbooks` route added to
// `App.tsx` rendering `<main data-screen="RBS-001">`. BOTH assertions failed
// and both named the nav entry and the id.
//
// **WHEN THE HOLD WAS RELEASED (2026-09-06, task D2)** the same two assertions
// were proved red in the opposite direction, in the same runner: with
// `App.tsx`'s new `runbooks` route commented out, the ADDRESS assertion fails
// with *"/runbooks lands on the not-built-yet screen"* and the SCREEN ID
// assertion fails with *"/runbooks renders something that is not RBS-001"*.
// **A turned-around assertion is a NEW assertion and gets a new red proof** —
// an inverted `toBe(true)` → `toBe(false)` that was never watched to fail is
// law 7's *structurally incapable of failing* with the old proof stapled to it.
//
// ⚠ `vitest` TRANSPILES AND DOES NOT TYPE-CHECK, so a green run here is not a
// build. `./node_modules/.bin/tsc --noEmit` is run separately — and never
// `npx tsc`, which in a fresh worktree fetches a newer compiler, aborts on a
// config error and reports NO type errors at all (law 7's *incapable of
// failing*).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import { SHELL_NAV } from "@/components/AppShell";
import { UNBUILT_SIDEBAR_DESTINATIONS, unbuiltDestinationFor } from "@/components/NotBuiltYet";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

/** Tenant-relative, exactly as `SHELL_NAV` declares it (PO 2026-08-10 path tenancy). */
const RUNBOOKS_ROUTE = "/runbooks";

/** The screen this nav item will open when CR-075 wave D lands. */
const RUNBOOKS_HOME_SCREEN = "RBS-001";

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

/**
 * Render the REAL route table at a REAL tenant address.
 *
 * ⚠ Mounted through `APP_ROUTES`, never bare inside a `MemoryRouter` with no
 * `/:tenant` pattern. DEF-CWP-3925's fixture did the latter, so `useParams()`
 * gave `undefined` and every address the page built came out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good string
 * to `toContain`. A fixture that cannot tell a working link from a broken one
 * is how that defect hid.
 */
// ⚠ WITHOUT THIS SEED THIS WHOLE FILE WOULD MEASURE A LOADING SKELETON.
// `ShellWithSession` returns `<LoadingSkeleton variant="card" />` while
// `tenantRegionalOf(regionalQuery.data)` is null, and with every query disabled
// that is forever — 389 characters of skeleton for every address in the
// product. `sidebarReachability.test.tsx` had exactly that fixture and its
// central assertion was structurally incapable of failing (DEF-SHL-4277); found while
// writing this file and fixed there in the same commit. The seed is the
// smallest one that satisfies the gate: a timezone and one of the seven formats
// `REGIONAL_DATE_FORMATS` declares. Everything else stays disabled on purpose.
const REGIONAL_SEED = { timezone: "America/Chicago", date_format: "MM/DD/YYYY" };

function renderAt(relativePath: string): string {
  const queryClient = new QueryClient({
    // Nothing may fetch: this is about ROUTING, so a screen with no seed still
    // renders its own honest loading state — which is still that screen.
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, DANA);
  queryClient.setQueryData(queryKeys.myPermissions, ADMIN_PERMISSIONS);
  // DEF-SHL-4272 — the shell boots on `GET /shell/display` (every signed-in
  // role), not on the two Admin/Executive settings reads. Without this seed
  // the shell holds and every address renders a loading skeleton.
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(REGIONAL_SEED));
  queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL_SEED);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${relativePath}`]}>
          <RoutedApp />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const REGRESSION =
  `The Runbooks nav item must open ${RUNBOOKS_HOME_SCREEN} at ${RUNBOOKS_ROUTE}. CR-075 wave D ` +
  `task D2 landed that screen and deleted "${RUNBOOKS_ROUTE}" from UNBUILT_SIDEBAR_DESTINATIONS ` +
  `in the SAME COMMIT. If this is failing, either the route was removed from App.tsx, or the ` +
  `screen stopped stamping its id, or a register entry has come back over a live screen — which ` +
  `is DEF-CWP-3925, where the customer portal shipped a front page with two working doors out ` +
  `of eight and every check was green over it.`;

describe("BR-SHL-001 amendment 3 — the Runbooks nav item, and the screen it opens", () => {
  it("the nav entry exists, sits between Finance and Reports, and carries a label key", () => {
    // The ADDRESS half of the hold starts here: if the item is not on the rail
    // at this exact path, everything below is asserting about nothing — the
    // empty-loop shape that let DEF-129 through.
    const order = SHELL_NAV.map((item) => item.path);
    const at = order.indexOf(RUNBOOKS_ROUTE);
    expect(
      at,
      `${RUNBOOKS_ROUTE} is not in SHELL_NAV. The PO ruled it onto the rail on 2026-09-06: ` +
        `"Nav bar will have Runbook as menu item - above reports module."`,
    ).toBeGreaterThan(-1);
    expect(order[at - 1], "Runbooks sits directly after Finance").toBe("/finance");
    expect(order[at + 1], "Runbooks sits directly before Reports").toBe("/reports");
    expect(SHELL_NAV[at].labelKey).toBe("shell.nav.runbooks");
    expect(SHELL_NAV[at].module).toBe("runbooks");
    // Thirteen items, not twelve — the count BR-SHL-001 now carries.
    expect(SHELL_NAV).toHaveLength(13);
  });

  it("the fixture can tell a real screen from a missing one — or nothing below means anything", () => {
    // The assertion that proves the assertions, and it is not theoretical: the
    // fixture this file started from returned a loading skeleton for EVERY
    // address, so "RBS-001 does not render at /runbooks" was true of a page
    // that rendered nothing at all. A hold-expiry test that cannot see a
    // screen would sit green through the very event it exists to catch.
    const dashboard = renderAt("/dashboard"); // a real, routed screen
    const nowhere = renderAt("/nowhere-at-all"); // nothing claims this
    expect(
      nowhere.includes(CATCH_ALL_MARKER),
      "an unrouted address does not render the catch-all, so the shell is showing its loading " +
        "skeleton instead of its Outlet and every assertion below is measuring nothing. Seed " +
        "whatever ShellWithSession now gates on (today: regionalSettings).",
    ).toBe(true);
    expect(
      dashboard.includes(CATCH_ALL_MARKER),
      "/dashboard renders the catch-all, so this fixture cannot tell a real screen from a " +
        "missing one",
    ).toBe(false);
  });

  it("RELEASED, BY ADDRESS: /runbooks no longer lands on the not-built-yet screen", () => {
    const markup = renderAt(RUNBOOKS_ROUTE);
    expect(
      markup.includes(CATCH_ALL_MARKER),
      `${RUNBOOKS_ROUTE} lands on the not-built-yet screen. ` + REGRESSION,
    ).toBe(false);
    // And the register no longer claims a debt it has paid off. A row that
    // outlives its gap tells a user a finished screen is unfinished, which is
    // hard-won law 1 and the reason `sidebarReachability.test.tsx` calls the
    // same condition a STALE ENTRY.
    expect(
      unbuiltDestinationFor(RUNBOOKS_ROUTE),
      `${RUNBOOKS_ROUTE} is registered as an unbuilt destination over a screen that renders. ` +
        REGRESSION,
    ).toBeNull();
  });

  it("RELEASED, BY SCREEN ID: RBS-001 is what renders at /runbooks", () => {
    // The half a register cannot answer, and the half law 7 says a single
    // address check cannot see: a screen can land while the router mounts it
    // somewhere else, and both addresses then open onto something that looks
    // plausible. `data-screen="<id>"` is how every screen in this product
    // declares which one it is, so this asserts the id at the address rather
    // than trusting either alone.
    const markup = renderAt(RUNBOOKS_ROUTE);
    expect(
      markup,
      `${RUNBOOKS_ROUTE} renders something that is not ${RUNBOOKS_HOME_SCREEN}. ` + REGRESSION,
    ).toContain(`data-screen="${RUNBOOKS_HOME_SCREEN}"`);
  });

  it("the register is empty, so nothing on the rail is claiming an unbuilt screen", () => {
    // `/runbooks` was the register's only entry. Emptying it is the state the
    // register has been in twice before — after `/reports` shipped and after
    // `/work` did — and the mechanism it exists for is unchanged: an entry is
    // an obligation to explain, never permission to ship a blank page.
    expect(
      UNBUILT_SIDEBAR_DESTINATIONS.map((row) => row.path),
      "a rail destination is registered as unbuilt; if that is true, its screen is missing, and " +
        "if it is not, the row is stale (DEF-077).",
    ).toEqual([]);
  });

  it("B14 rules 31 and 32 — no id, rule or change-request number reaches the clerk", () => {
    // The screen stamps `RBS-001` as an ATTRIBUTE, which is not visible copy —
    // so the check is on what a person READS, with the tags stripped, exactly
    // as rule 31's own note prescribes for a value that rides on `title`.
    const text = renderAt(RUNBOOKS_ROUTE)
      .replace(/<[^>]*>/g, " ")
      .replace(/&[a-z]+;/g, " ");
    expect(text, "a screen id reaches a clerk").not.toContain(RUNBOOKS_HOME_SCREEN);
    expect(text, "a change-request id reaches a clerk").not.toContain("CR-075");
    expect(text, "a rule id reaches a clerk").not.toContain("BR-SHL-001");
    expect(text, "a defect id reaches a clerk").not.toMatch(/\bDEF-[A-Z]{3}-\d{3,5}\b/);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: BR-SHL-001 amendment 3 (PO 2026-09-06, decision log) + CLAUDE.md hard-won law 2 mirror clause + 12-governance/10-defect-log.csv DEF-CWP-3925
// generated: 2026-09-06 by the CR-075 nav lane
// checklist: A✔ B✔ C✔ D=deferred(no API call — every query is disabled on purpose, so routing is what is measured) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST through ./node_modules/.bin/vitest — with a temporary /runbooks route in App.tsx rendering <main data-screen="RBS-001">, the ADDRESS assertion failed ("/runbooks NO LONGER lands on the not-built-yet screen") and the SCREEN ID assertion failed ("RBS-001 now renders at /runbooks and the nav item is STILL held"); both quoted verbatim in the lane report. Route removed, file green. tsc --noEmit✔ (the local compiler, never npx)
// exceptions: (1) G103 does not cover this hold — it reads only portal/ files and CWP screen ids, and says so in this file's header rather than being assumed to · (2) this measures ROUTING, not permissions
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
