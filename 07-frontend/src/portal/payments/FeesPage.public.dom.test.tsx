// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-050 (EP-CWP-09) · Screen: CWP-050 at `/{tenant}/portal/fees`
// Change:   CR-085 (2026-09-08) — a stranger may open this address.
// Rules:    BR-CWP-093 (nothing empty ever appears) · CR-068 R8 (a portal that
//           is OFF shows the holding page on EVERY route) · B14 rule 31 (no id
//           and no internal code is a visible value) · rule 32 · rule 35 ·
//           hard-won law 2 (assert a destination BY ADDRESS, never by label)
// Cases:    a signed-out visitor gets the utility's frame and a readable page ·
//           NOT the *Failed · Download error report* card · the one price door
//           that IS public today · a real server failure still fails
//
// ⚠ **WHY ITS OWN FILE (hard-won law 11).** `Fees.dom.test.tsx` next to it
// mocks `../api/portalClient` at module scope for `FeesView`; this file needs
// that module NOT mocked, because the thing under test is exactly what
// `FeesPage` does when `getSession` refuses. Two module-level mock regimes
// cannot share one file, and several lanes are in this tree — a new path
// collides with nobody.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { PortalFront } from "../api/guestClient";

import { FeesPage } from "./FeesPage";

const FRONT: PortalFront = {
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water & Power",
    brand_primary_hex: "#EC3013",
    brand_accent_hex: "#E15B47",
  },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: null },
  locales: ["en", "es"],
  cards: [],
  links: { help: true, visit: true },
  services: [],
  strapline: null,
  office_hours_text: "8am to 5pm, Monday to Friday",
  emergency_phone: "(512) 555-0100",
};

/** What the running server actually answers a signed-out `GET /portal/session`. */
const SIGNED_OUT = new ApiError(401, {
  code: "AUTH-001",
  message_key: "errors.auth-001",
  params: {},
  field_errors: [],
  br_ref: null,
  trace_id: "ab3bb81bca4c48ed8730154401d85c26",
});

/** And what a genuinely broken one answers — the case that must STILL fail. */
const BROKEN = new ApiError(500, {
  code: null,
  message_key: "api.error.unexpected",
  params: {},
  field_errors: [],
  br_ref: null,
  trace_id: null,
});

function clientRefusingSessionWith(error: ApiError): ApiClient {
  return {
    get: async (path: string) => {
      if (path.includes("/portal/session")) throw error;
      if (path.includes("/portal/public/front")) return { data: FRONT, status: 200 };
      return { data: undefined, status: 200 };
    },
    post: async () => ({ data: undefined, status: 200 }),
    put: async () => ({ data: undefined, status: 200 }),
    patch: async () => ({ data: undefined, status: 200 }),
    del: async () => ({ data: undefined, status: 200 }),
  } as unknown as ApiClient;
}

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`DEF-CWP-3925`) — a bare
 *  `MemoryRouter` leaves `useParams().tenant` undefined and every address the
 *  page builds comes out `//portal/…`, a protocol-relative URL to another host
 *  that reads as a perfectly good string to `toContain`. */
function draw(error: ApiError) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.portalFront, FRONT);
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/pine-hill/portal/fees"]}>
        <Routes>
          <Route
            path="/:tenant/portal/fees"
            element={<FeesPage client={clientRefusingSessionWith(error)} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("CWP-050 · what a stranger sees at /fees (CR-085)", () => {
  it("opens for a visitor instead of refusing them", async () => {
    const { container } = draw(SIGNED_OUT);
    await waitFor(() =>
      expect(container.querySelector('[data-screen="CWP-050"]')).not.toBeNull(),
    );
    // ⚠ **THE DEFECT, ASSERTED BY ITS OWN WORDS.** Typing this address
    // signed out produced a grey *Failed · We could not open this page ·
    // You're signed out · Download error report* card OUTSIDE the utility's
    // frame — no nav, no branding, no way back — over a page nothing was
    // wrong with.
    expect(container.textContent).not.toContain("You're signed out");
    expect(container.textContent).not.toContain("Download error report");
    // And it is inside the utility's own frame, like every other guest screen.
    expect(container.textContent).toContain("Pine Hill Water & Power");
  });

  it("says the prices are not shown here, and gives the number instead", async () => {
    const { container } = draw(SIGNED_OUT);
    await waitFor(() =>
      expect(container.querySelector("[data-prices-not-published]")).not.toBeNull(),
    );
    // ⚠ The drawing's own state for this page: *"Not published — the utility
    // has not turned this page on: the phone number, not an empty page."*
    expect(container.querySelector("[data-prices-phone]")?.textContent).toBe("(512) 555-0100");
    // The catalogue's words, never the key (B14 rule 35 · `DEF-CWP-3952`).
    expect(container.textContent).not.toContain("portal.fees.");
    expect(container.textContent).not.toContain("portal.card.");
  });

  it("points at the one price a stranger CAN get today, by address", async () => {
    const { container } = draw(SIGNED_OUT);
    await waitFor(() =>
      expect(container.querySelector("[data-prices-not-published]")).not.toBeNull(),
    );
    // ⚠ BY ADDRESS, not by label (`DEF-CWP-3925`): `/start-service` is where
    // `POST /public/premises/availability` quotes a connection fee and a
    // deposit to anybody who types an address — the only figure this product
    // publishes to a visitor.
    const links = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(links).toContain("/pine-hill/portal/start-service");
  });

  it("names no fee, no tariff and no invented figure (the prime directive)", async () => {
    const { container } = draw(SIGNED_OUT);
    await waitFor(() =>
      expect(container.querySelector("[data-prices-not-published]")).not.toBeNull(),
    );
    // ⚠ **THE ABSENCE IS THE DELIVERABLE HERE.** Every figure the drawing shows
    // is in the database already; what is missing is the ruling about which of
    // it is public (`rating.TariffVersion.publish_public` is *capture-only v1*,
    // wired to nothing, false on every row). An open question is not resolved
    // by choosing a value, so this page shows the shape and no content — and a
    // later lane that quietly types `$45.00` in here goes red.
    expect(container.innerHTML).not.toMatch(/\$\d/);
    expect(container.textContent).not.toMatch(/per kgal/i);
  });

  it("a REAL failure still fails — a 500 is not a visitor", async () => {
    const { container } = draw(BROKEN);
    // ⚠ The whole fix is telling *no session* from *the server broke*. If this
    // case ever goes green on the public page, the screen has started swallowing
    // outages and telling everybody the prices are simply not published.
    await waitFor(() => expect(container.textContent).toContain("Download error report"));
    expect(container.querySelector("[data-prices-not-published]")).toBeNull();
  });
});
