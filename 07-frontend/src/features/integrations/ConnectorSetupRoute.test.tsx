// ── Trace ──────────────────────────────────────────────
// Change:   CR-110-BRC04 wave A — the connector SET-UP screen, S147 / INT-07,
//           at `/:tenant/settings/connectors/:providerKey/configure`.
// Rules:    B14 rule 42 (built from the drawing AS AN IMAGE) · BR-INT-037 (a
//           29th connector costs no screen code) · CLAUDE.md hard-won law 2
//           (built is not wired) and law 7 (prove a guard RED first, in the
//           harness that will run it).
// Tests:    this file IS the test.
// ───────────────────────────────────────────────────────
//
// THE TEST THAT WOULD HAVE CAUGHT *"THIS SCREEN HAS NO ROUTE"*.
//
// Before this wave, typing the address below returned the product's *not built
// yet* page: `App.tsx` declared `settings/integrations/:key`, `…/:key/access`
// and `…/:key/mappings` and nothing at `settings/connectors/…`, so the address
// fell through `path: "*"` to `NotBuiltYetPage`. Every suite was green, `tsc`
// was clean and every gate passed — because **no gate in this repo reads a
// route table** and the one thing nobody had written was an assertion that the
// address opens anything at all.
//
// ⚠ **IT ASSERTS THE DESTINATION BY ADDRESS *AND* BY THE CONNECTOR IT OPENS,
// AND THAT SECOND HALF IS THE POINT.** Hard-won law 7's *looking at the wrong
// thing* clause records the exact miss this is written against: *"a hold-expiry
// test asserted a screen was REGISTERED at an address while the router was
// mounting it somewhere else; both screens opened onto 'not built yet' and every
// check passed."* So a bare "something rendered" would not do. The page stamps
// `data-screen="S147"` and `data-provider="<key>"`, and this file reads BOTH
// back off the markup the real router produced — a future lane that mounts the
// component at a different address, or mounts a different component here, goes
// red and is named.
//
// ⚠ **AND IT WALKS FOUR CONNECTORS, NOT ONE**, because `BR-INT-037` is the
// claim this whole wave stands on: one component rendered 28 ways from the
// manifest. A route test that passed on one key would be true of 28 hand-written
// screens too, and would therefore prove nothing about the thing that matters.
//
// PROVED RED BEFORE TRUSTED GREEN, IN THIS HARNESS — `npx vitest run
// src/features/integrations/ConnectorSetupRoute.test.tsx`, which is the command
// CI runs, not a path nobody uses (`DEF-GOV-3733`). The failure text is quoted
// in the wave's report.
//
// The fixture is `routing/sidebarReachability.test.tsx`'s, deliberately: it
// mounts the REAL `APP_ROUTES` on a memory history and lets React Router itself
// answer *which component does this URL pick?*, which is the only exact answer
// there is. Re-implementing route ranking in a Python gate would be a guard
// that agrees with itself.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

const TENANT = "brazosbend";

/** The marker the catch-all — and ONLY the catch-all — puts on the page. */
const CATCH_ALL_MARKER = 'data-not-built-yet="true"';

/**
 * Four connectors, one per SHAPE the blueprint draws, so a pass here is a
 * statement about the manifest loop rather than about one lucky vendor:
 *
 *   `email_google`         a vendor sign-in — the redirect field kind (CFG-02)
 *   `erp_sap`              a key WE issue them — `they_hold_ours` (CFG-10)
 *   `bank_lockbox_file`    a file channel with a mapping editor (CFG-23)
 *   `meters_neptune360`    sixteen operations — the `…8 more` case (CFG-06)
 *
 * ⚠ **THE SECOND ONE READ `gl_partner` UNTIL THE 28-MANIFEST SPLIT LANDED
 * (2026-09-16, hours after this file was written).** The shared finance
 * connector retired into five named ERPs and `erp_sap` is one of them.
 * **THE ROT WOULD HAVE BEEN SILENT, AND THAT IS WHY IT IS WRITTEN DOWN:** this
 * screen renders for ANY key — that is the last case in this file — so a case
 * pointed at a connector that no longer exists goes on PASSING while testing
 * nothing at all. Law 7's *looking at the wrong thing*, arriving because the
 * world moved rather than because anybody was careless.
 * **The route test could not catch it and the WALKTHROUGH did**, because the
 * walkthrough asks the real API for the real shape and the key panel stopped
 * appearing. A fixture that cannot tell a live key from a retired one needs a
 * companion that can.
 *
 * ⚠ THE KEYS ARE MANIFEST KEYS AND NOT A HAND-TYPED PRODUCT LIST. They name
 * files under `06-backend/apps/integrations/manifests/`; nothing on the screen
 * branches on any of them, which is what the last case below asserts directly.
 */
const SHAPES: readonly string[] = [
  "email_google",
  "erp_sap",
  "bank_lockbox_file",
  "meters_neptune360",
];

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
  permissions: ["settings_lookups"].map((code) => ({
    code,
    label: code,
    access: "Full" as const,
  })),
};

const REGIONAL_SEED = shellBootSeed({
  timezone: "America/Chicago",
  date_format: "MM/DD/YYYY",
});

function RoutedApp() {
  return useRoutes(APP_ROUTES);
}

function renderAt(url: string): string {
  const queryClient = new QueryClient({
    // Nothing may fetch: this suite is about ROUTING, so a screen with no seed
    // renders its own honest loading state — which is still that screen, and
    // still carries its own `data-screen` stamp.
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

function setUpAddress(key: string): string {
  return `/${TENANT}/settings/connectors/${key}/configure`;
}

describe("CR-110 wave A — the connector set-up screen has an address of its own", () => {
  it("the fixture can tell a real screen from a missing one", () => {
    // ⚠ THE ASSERTION THAT PROVES THE ASSERTIONS, and it is not ceremony:
    // `sidebarReachability.test.tsx` carries the same case because without it
    // the shell returned 389 characters of loading skeleton for EVERY address
    // in the product, `CATCH_ALL_MARKER` was never found anywhere, and the
    // suite's central check passed over a product where nothing routed at all
    // (`DEF-SHL-4277`). That is law 7's *structurally incapable of failing*.
    const dashboard = renderAt(`/${TENANT}/dashboard`);
    const nowhere = renderAt(`/${TENANT}/nowhere-at-all`);
    expect(
      nowhere.includes(CATCH_ALL_MARKER),
      "an unrouted address does not render the catch-all — the shell is showing its loading " +
        "skeleton instead of its Outlet, so every assertion in this file is measuring nothing",
    ).toBe(true);
    expect(
      dashboard.includes(CATCH_ALL_MARKER),
      "/dashboard renders the catch-all, so this fixture cannot tell a real screen from a " +
        "missing one",
    ).toBe(false);
  });

  it.each(SHAPES)("%s — the set-up address opens a screen, not the catch-all", (key) => {
    const markup = renderAt(setUpAddress(key));
    expect(
      markup.includes(CATCH_ALL_MARKER),
      `${setUpAddress(key)} falls through to the catch-all: a clerk typing the connector's ` +
        `set-up address gets "this screen is not built yet". Declare the route in App.tsx.`,
    ).toBe(false);
  });

  it.each(SHAPES)("%s — the address opens S147, and opens it for THAT connector", (key) => {
    const markup = renderAt(setUpAddress(key));
    // BY ADDRESS: the router picked the set-up screen for this URL.
    expect(
      markup,
      `${setUpAddress(key)} does not render S147. A screen mounted at some OTHER address ` +
        `leaves this one opening onto nothing while every other suite stays green — which is ` +
        `precisely the miss hard-won law 7 records.`,
    ).toContain('data-screen="S147"');
    // BY CONNECTOR: and it is reading the key out of the URL, not a default.
    expect(
      markup,
      `S147 opened at ${setUpAddress(key)} without binding to "${key}". One screen rendered 28 ` +
        `ways from the manifest (BR-INT-037) means the provider comes from the address.`,
    ).toContain(`data-provider="${key}"`);
  });

  it("no connector key is hand-typed into the screen — the 29th costs no screen code", () => {
    // BR-INT-037, asserted rather than asserted-about. An address for a key no
    // manifest declares must still reach the SCREEN (which then shows the
    // server's refusal), because a front end that only routes keys it knows
    // about is a front end that has to be edited for connector 29.
    //
    // ⚠ THIS IS THE CASE THAT WOULD CATCH A `switch (key)` CREEPING IN, and it
    // is the reason this file does not simply loop the four shapes: four keys
    // passing is equally true of four hand-written screens.
    const invented = "a_vendor_nobody_has_written_yet";
    const markup = renderAt(setUpAddress(invented));
    expect(
      markup.includes(CATCH_ALL_MARKER),
      `the set-up address for an unknown connector falls through to the catch-all, so the ` +
        `front end knows a finite list of vendors — BR-INT-037 says it must not`,
    ).toBe(false);
    expect(markup).toContain('data-screen="S147"');
    expect(markup).toContain(`data-provider="${invented}"`);
  });
});
