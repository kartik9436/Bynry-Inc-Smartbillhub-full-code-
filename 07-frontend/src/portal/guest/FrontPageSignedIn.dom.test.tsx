// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LINE 1 AND THE FILE IS `.dom.test.tsx`, which is the
// convention `vitest.config.ts` sets out (DEF-523): the default environment is
// `node` so 200+ first-paint suites stay fast, and a suite that needs a real
// DOM opts in per file. `FrontPage.test.tsx` beside this one renders to static
// markup and cannot observe a `<Navigate>`, because a redirect happens in an
// effect and static rendering runs none.
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-001 · CR-085 step 2 lane 4 (home and accounts)
// Screens:  CWP-001 at `/{tenant}/portal` · CWP-022 at `/{tenant}/portal/home`
// Defects:  DEF-CWP-4900 — a signed-in customer who opened `/{tenant}/portal`
//           was shown the GUEST front page, with a *Sign in* bar on it, at the
//           address a utility prints on its bills.
// Rules:    the customer-portal blueprint, screen 26, verbatim: *"The portal
//           serves the home page at both `/{tenant}/portal` and
//           `/{tenant}/portal/home`. Both render screen 03 … They must render
//           the SAME SCREEN, not two that drift."* · hard-won law 2 (assert a
//           door BY ADDRESS, not by the presence of a link-shaped string)
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { queryKeys } from "@/api/queryClient";

import type { PortalFront } from "../api/guestClient";
import type { PortalSession } from "../api/portalClient";

import { FrontPage } from "./FrontPage";

const FRONT: PortalFront = {
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water & Power",
    brand_primary_hex: "#EC3013",
    brand_accent_hex: "#E15B47",
  },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
  locales: ["en", "es"],
  cards: [{ key: "pay_bill", available: true, reason_code: null }],
  links: { help: false, visit: false },
  switches: {
    quick_pay_enabled: true,
    self_read_enabled: false,
    plans_enabled: true,
    requests_enabled: true,
    outage_reporting_enabled: true,
  },
  services: [{ code: "water", name: "Water", color: "#1e6b8f" }],
  strapline: "Your account, your bills and your meter readings — any time.",
  office_hours_text: "8am to 5pm, Monday to Friday",
  emergency_phone: "(512) 555-0100",
};

const SESSION = {
  customer: { display_name: "Elena Rivera" },
  accounts: [],
  language: null,
} as unknown as PortalSession;

/**
 * ⚠ **BOTH ADDRESSES ARE IN THE ROUTE TABLE AND THE SECOND ONE RENDERS A MARK.**
 * A `MemoryRouter` with only `/:tenant/portal` in it would report a passing
 * redirect to a route that does not exist — the shape hard-won law 7 calls
 * *looking at the wrong thing*, and the shape a hold-expiry test already hit
 * once in this repo. `useParams().tenant` is bound for the same reason
 * `FrontPage.test.tsx` binds it: a bare mount builds every address as
 * `//portal/…`, a protocol-relative URL to another host.
 */
function mount(session: PortalSession | undefined) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.portalFront, FRONT);
  if (session !== undefined) queryClient.setQueryData(["portal", "session"], session);
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/pine-hill/portal"]}>
        <Routes>
          <Route path="/:tenant/portal" element={<FrontPage />} />
          <Route path="/:tenant/portal/home" element={<p data-screen="CWP-022">the home screen</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("DEF-CWP-4900 · /{tenant}/portal is the customer's home when they are signed in", () => {
  it("a signed-in customer lands on CWP-022, not on the guest front page", async () => {
    const { container } = mount(SESSION);
    expect(await screen.findByText("the home screen")).toBeTruthy();
    expect(container.querySelector("[data-screen='CWP-022']")).not.toBeNull();
    // The two things that made this defect worth its severity: a *Sign in* bar
    // offered to somebody who is signed in, over errands they no longer need.
    expect(container.textContent).not.toContain("Sign in");
    expect(container.querySelector("[data-errand]")).toBeNull();
  });

  it("a stranger still gets the guest front page at the same address", () => {
    const { container } = mount(undefined);
    expect(container.querySelector("[data-errand='pay_bill']")).not.toBeNull();
    expect(container.textContent).toContain("Sign in");
    expect(container.querySelector("[data-screen='CWP-022']")).toBeNull();
  });
});
