// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-5666 (2026-09-17, CRITICAL) — a tenant whose `timezone` is
//          unset renders a PERMANENT SKELETON. Not one screen: the app shell
//          itself never mounts, so every address in the product is a blank
//          page, for ever, with no error anywhere.
// Rules:   DEF-SHL-3964 decision D3 (no screen renders before its date format
//          is known) · BR-SHL-025 (state the refusal) · hard-won law 2's
//          mirror (a live screen behind a dead control) · law 7
// ───────────────────────────────────────────────────────
// ⚠ **WHY NOTHING IN 4,800 FRONTEND TESTS COULD CATCH THIS.**
//
// `shellBootSeed.ts` says it out loud in its own docstring: a fixture that does
// not seed a timezone "gets a 389-character loading skeleton for every address
// in the product". The repository has known that since 2026-09-06 — and read it
// as a FIXTURE hazard, something suites must remember to avoid. Nobody asked
// the other question: **can a REAL tenant be in that state?**
//
// It can, and it is the ordinary one. `tenancy/services.py` seeds a new
// tenant's timezone from `default_timezone_for_state(data["state_code"])`, and
// `state` is OPTIONAL on the signup payload — no field error requires it. So a
// utility that signs up without a state gets `tenant_settings.timezone = NULL`
// and can never open the product it just paid for.
//
// ⚠ **AND EVERY CHECK PASSES OVER IT, WHICH IS WHY IT REACHED A CUSTOMER.**
// `GET /shell/display` answers **200**. The browser logs no error and shows no
// failed request. `displayQuery.isError` is false, so the shell takes its
// "still loading" branch and holds there — for ever, because the answer it is
// waiting for has already arrived and is simply empty.
//
// **The distinction this file pins is PENDING versus SETTLED-AND-UNUSABLE.**
// `tenantRegionalOf` returns `null` for both and says so deliberately ("three
// genuinely different situations, treated the same way on purpose"). That is
// right for the VALUE and wrong for the WAIT: a request that has not answered
// is worth waiting for, and one that answered with nothing is not.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import type { SessionUser, ShellDisplay } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

const TENANT = "lonestarridge";

const ADMIN: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@lonestarridge.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

/** `GET /shell/display` exactly as it answers for a tenant provisioned through
 *  the real signup service with no state: **200, and a null timezone**. Every
 *  other field is the seed `provision_tenant` writes, so this payload differs
 *  from a healthy one in ONE field — which is the whole point. */
function displayWithTimezone(timezone: string | null): ShellDisplay {
  return {
    period: null,
    regional: {
      country: "United States",
      timezone,
      language: "en-US",
      first_day_of_week: "sunday",
      currency: "USD",
      number_format: "1,234.56",
      date_format: "MM/DD/YYYY", // SEEDED — only the zone is ever missing
      time_format: "12-hour",
    },
    company: {
      legal_name: "Lone Star Ridge Water",
      dba_name: "Lone Star Ridge Water",
      has_logo: false,
      mark: { letters: "LR", background_hex: null, ink_hex: null, contrast_ratio: null },
      brand_primary_hex: null,
    },
  } as ShellDisplay;
}

function openProduct(display: ShellDisplay): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, ADMIN);
  // Seeded, so the query is SETTLED and SUCCESSFUL — which is precisely the
  // state the product is in. This is not a "slow network" fixture.
  queryClient.setQueryData(queryKeys.shellDisplay, display);
  const router = createMemoryRouter(APP_ROUTES, {
    initialEntries: [`/${TENANT}/dashboard`],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** `AppShell`'s own root. Present iff the shell mounted.
 *
 * ⚠ **THE OBVIOUS DISCRIMINATOR DOES NOT WORK AND THE FIRST DRAFT OF THIS FILE
 * USED IT.** `.skeleton[aria-busy]` is present in BOTH states — a healthy
 * dashboard renders its own loading skeleton while its data arrives — so a case
 * asserting "no skeleton" fails on a perfectly good screen. Measured on this
 * branch: a healthy tenant renders **7,819** characters with `.app-shell`, and
 * a null-timezone tenant renders **400** with none. That is the difference this
 * file is allowed to read. (Law 7: ask what would make the check pass — or fail
 * — wrongly. Here it was the control that went red, which is the only reason
 * the flaw was caught.) */
const shellMounted = (): boolean => document.querySelector(".app-shell") !== null;

afterEach(cleanup);

describe("DEF-SHL-5666 — a tenant with no time zone can still use the product", () => {
  it("the control: a tenant WITH a zone boots, so this fixture can tell the two apart", () => {
    openProduct(displayWithTimezone("America/Chicago"));
    expect(shellMounted()).toBe(true);
  });

  it("a tenant with NO zone still mounts the shell — today it hangs for ever", () => {
    openProduct(displayWithTimezone(null));
    // THE DEFECT. Today: false, and a skeleton in its place, on every address.
    expect(shellMounted()).toBe(true);
  });

  it("the sidebar navigation is reachable, so the admin can get to Settings and fix it", () => {
    openProduct(displayWithTimezone(null));
    // The whole point of not blocking: the ONE screen that can set a timezone
    // lives INSIDE this shell. A blocking frame — however well worded — cannot
    // link anywhere useful, because following the link renders this same gate.
    expect(document.querySelector('nav[aria-label]')).not.toBeNull();
  });

  it("the product SAYS the zone is unset rather than showing a wrong one silently", () => {
    openProduct(displayWithTimezone(null));
    // DEF-SHL-3964's objection was to a SILENT default arriving through a `??`.
    // A stated one is a different act, and BR-SHL-025 requires the statement.
    expect(document.body.textContent ?? "").toMatch(/time zone/i);
  });

  it("a request that has NOT answered still waits — the fix must not break D3", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    queryClient.setQueryData(queryKeys.me, ADMIN);
    // No shellDisplay seeded: genuinely pending, which is worth waiting for.
    const router = createMemoryRouter(APP_ROUTES, {
      initialEntries: [`/${TENANT}/dashboard`],
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(shellMounted()).toBe(false);
  });
});
