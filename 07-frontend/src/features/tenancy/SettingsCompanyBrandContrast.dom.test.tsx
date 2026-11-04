// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-10545 (portal a11y F-09, brand half)
// Rules:    decision log 2026-10-23 — Group A ruling 3(b): Company → Profile
//           refuses a brand colour that reaches 4.5:1 with neither white nor
//           the dark ink, and says why.
// Server:   06-backend/tests/test_a11y_group_a_brand.py
// ───────────────────────────────────────────────────────
/**
 * The server names the field and the key `settings.company.hex_contrast`; this
 * proves the sentence reaches the screen UNDER THE COLOUR FIELD, and in every
 * catalogue (a missing key would reach the admin as silence).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { CompanyProfile } from "@/api/endpoints";
import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { CompanyTab } from "./SettingsCompanyTab";

const CATALOGUES = import.meta.glob("../../i18n/locales/*.json", { eager: true, import: "default" }) as Record<
  string,
  Record<string, string>
>;

const PROFILE: CompanyProfile = {
  legal_name: "Brazos Bend Utility District No. 1",
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
  mark: { letters: "BB", background_hex: "#1B5E9E", ink_hex: "#FFFFFF", contrast_ratio: 6.68 },
  brand_primary_hex: "#1B5E9E",
  brand_accent_hex: "#0F7A6B",
  remit_to_address: null,
  remit_payable_to: null,
  service_hours: null,
};

function refusingClient() {
  return createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (_input: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "GET") {
        return new Response(JSON.stringify(PROFILE), { status: 200, headers: { "content-type": "application/json" } });
      }
      return new Response(
        JSON.stringify({
          code: "VAL_RANGE",
          message_key: "settings.company.hex_contrast",
          params: {},
          field_errors: [{ field: "brand_primary_hex", code: "VAL_RANGE", message_key: "settings.company.hex_contrast", params: {} }],
        }),
        { status: 400, headers: { "content-type": "application/json" } },
      );
    },
  });
}

describe("Group A 3(b) · Company → Profile refuses an unreadable brand colour", () => {
  beforeEach(() => window.history.replaceState({}, "", "/brazosbend/settings/company"));
  afterEach(cleanup);

  it("every catalogue carries the sentence", () => {
    const files = Object.keys(CATALOGUES);
    expect(files.length).toBe(11);
    for (const file of files) expect(CATALOGUES[file]["settings.company.hex_contrast"], file).toBeTruthy();
  });

  it("the refusal shows under the Primary color field", async () => {
    const user = (await import("@testing-library/user-event")).default;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.companyProfile, PROFILE);
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter>
            <CompanyTab readOnly={false} client={refusingClient()} />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    const field = screen.getByLabelText("Primary color");
    await user.clear(field);
    await user.type(field, "#EC3013");
    await user.click(screen.getByRole("button", { name: /Save changes/ }));
    const sentence = await screen.findAllByText("Text on this color is unreadable. Choose a darker or lighter one.");
    expect(sentence.length).toBeGreaterThan(0);
    const describedBy = field.getAttribute("aria-describedby") ?? "";
    const described = describedBy
      .split(" ")
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ");
    expect(described).toContain("Text on this color is unreadable.");
  });
});
