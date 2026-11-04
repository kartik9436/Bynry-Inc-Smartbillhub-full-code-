// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-005 (EP-TEN-05 §Stories)  Screens: S8 (Settings → Company)
// Change:   CR-048 wave D — the utility's own mark.
// Defect:   DEF-192 (the logo bytes had no route, so nothing could draw a
//           logo) · DEF-195 (the mark was ruled and drawn nowhere)
// Rules:    BR-TEN-019
// ───────────────────────────────────────────────────────
/**
 * THE ONE THING A `node` SUITE CANNOT ASSERT: the logo's URL.
 *
 * `companyLogoFileUrl()` builds `/api/{tenant}/settings/company/logo/file`
 * from the tenant in the browser's own path, so proving that an `<img>` is
 * drawn AND that it points at the right place needs a window with a URL in it.
 * `vitest.config.ts` keeps `node` as the default environment for the 200+
 * static suites, and files opt in per-file with the pragma on line 1 — this is
 * that opt-in, and it is deliberately tiny.
 *
 * Why it is worth a file of its own: the assertion it replaces read
 * `expect(html).not.toContain("<img")` with the comment *"nothing streams the
 * bytes back, so nothing pretends to show the image"*. The comment was true
 * and the product was broken — a utility uploaded a logo, the screen said
 * "On file: image/png, 12 KB" and showed a coloured square, and the image
 * appeared nowhere in the product. A test that pins the URL is what stops that
 * sentence becoming true again quietly.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { CompanyProfile } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { CompanyTab } from "./SettingsCompanyTab";

const BRAZOS_BEND: CompanyProfile = {
  legal_name: "Brazos Bend Utility District No. 1",
  // CR-060 C7 — the server serves both on every read; `utility` is the seed.
  organisation_type: "utility",
  organisation_types: ["utility", "sub_metering", "hoa"],
  dba_name: "Brazos Bend Utilities",
  ein: "74-3182640",
  state_utility_id: null,
  mailing_address: null,
  support_phone: null,
  support_email: null,
  website: null,
  logo_file_id: null,
  logo: null,
  has_logo: false,
  logo_ref: null,
  mark: {
    letters: "BB",
    background_hex: "#1B5E9E",
    ink_hex: "#FFFFFF",
    contrast_ratio: 6.68,
  },
  brand_primary_hex: "#1B5E9E",
  brand_accent_hex: "#0F7A6B",
  remit_to_address: null,
  remit_payable_to: null,
  service_hours: null,
};

function renderTab(profile: CompanyProfile) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.companyProfile, profile);
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <CompanyTab readOnly={false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("S8 Company → Brand: what sits where the logo goes", () => {
  beforeEach(() => {
    // The tenant lives in the URL (PO ruling 2026-08-10), and that is where
    // `currentTenant()` reads it from.
    window.history.replaceState({}, "", "/brazosbend/settings/company");
  });

  // Vitest globals are OFF in this repo, so React Testing Library never
  // registers its own afterEach — without this every test renders into the
  // PREVIOUS test's DOM and `queryBy*` finds the last case's markup.
  afterEach(cleanup);

  it("DEF-192: an uploaded logo is DRAWN, at the route that serves its bytes", () => {
    renderTab({
      ...BRAZOS_BEND,
      logo_file_id: "0199b1c2-0000-7000-8000-00000000a1",
      logo: {
        logo_file_id: "0199b1c2-0000-7000-8000-00000000a1",
        content_type: "image/png",
        size_bytes: 12_288,
      },
      has_logo: true,
      logo_ref: "0199b1c2-0000-7000-8000-00000000a1",
    });
    const image = screen.getByAltText("Brazos Bend Utilities logo");
    expect(image.tagName).toBe("IMG");
    // CR-172-BRC10 — the reference rides in the address, so a replaced logo is
    // a new address. (The API origin in front of it is DEF-TEN-9704's case,
    // asserted in src/api/companyLogoFileUrl.dom.test.ts with an origin set.)
    expect(image.getAttribute("src")).toBe(
      "/api/brazosbend/settings/company/logo/file?v=0199b1c2-0000-7000-8000-00000000a1",
    );
  });

  it("CR-172-BRC10: an image that cannot be fetched falls back to the two-letter mark", () => {
    renderTab({ ...BRAZOS_BEND, has_logo: true, logo_ref: "r-broken" });
    const image = screen.getByAltText("Brazos Bend Utilities logo");
    fireEvent.error(image);
    expect(screen.queryByAltText("Brazos Bend Utilities logo")).toBeNull();
    expect(screen.getByLabelText("Brazos Bend Utilities logo").textContent).toBe("BB");
  });

  it("DEF-TEN-10636: the on-file line names type and size, and never the logo's id (B14 rule 31)", () => {
    const id = "01a17d37-5c2e-7a10-9b3f-0e6d2c4a8b91";
    renderTab({
      ...BRAZOS_BEND,
      logo_file_id: id,
      logo: { logo_file_id: id, content_type: "image/png", size_bytes: 2_048 },
      has_logo: true,
      logo_ref: id,
    });
    expect(document.body.textContent).toContain("On file: PNG, 2 KB.");
    // The id may build the image's address; it is never visible text.
    expect(document.body.textContent).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });

  it("DEF-195: with no logo the same slot carries the two-letter mark", () => {
    renderTab(BRAZOS_BEND);
    expect(screen.queryByAltText("Brazos Bend Utilities logo")).toBeNull();
    const mark = screen.getByLabelText("Brazos Bend Utilities logo");
    expect(mark.tagName).toBe("SPAN");
    expect(mark.textContent).toBe("BB");
  });

  it("the mark updates LIVE as the trading name is typed (BR-TEN-019)", async () => {
    const user = (await import("@testing-library/user-event")).default;
    renderTab(BRAZOS_BEND);
    const dba = screen.getByLabelText("Doing business as");
    await user.clear(dba);
    await user.type(dba, "Hilltop Power");
    expect(screen.getByLabelText("Hilltop Power logo").textContent).toBe("HP");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-048 wave D · CR-007 PO ruling 2026-08-16 · OQ-257
// generated: 2026-08-30 by the CR-048 wave-D lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
