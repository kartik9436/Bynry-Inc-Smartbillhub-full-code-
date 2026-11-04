// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-069 (EP-CWP-12) · US-CWP-070 · Screens: CWP-069 · CWP-070
//           wireframes/CWP-069.png · CWP-070.png
// Rules:    CR-068 R8 · hard-won law 3 · B14 rule 31 · BR-SHL-025 (view-only
//           roles see the controls disabled with the reason) · rule 21
// Cases:    US-CWP-069 TC-1 · TC-3 · TC-7 · TC-10 · US-CWP-070 TC-1 · TC-3 ·
//           TC-4 — at the first paint
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { PortalBranding, PortalSettings } from "@/api/portalSettingsEndpoints";
import { queryKeys } from "@/api/queryClient";
import type { ErrandCardKey, ErrandCardOffer } from "@/portal/api/guestClient";
import { ToastProvider } from "@/components/Toast";

import { CustomerPortalTab, portalSegmentFromParam } from "./SettingsCustomerPortalTab";

/**
 * The server sends all six errand cards with whether each may be used (PO
 * ruling 2026-09-05). These suites are about doors OTHER than the card grid,
 * so they name the usable ones and let this build the payload — one place to
 * edit if the shape moves again.
 */
function offered(...keys: ErrandCardKey[]): ErrandCardOffer[] {
  return CARD_KEYS.map((key) =>
    keys.includes(key)
      ? { key, available: true as const, reason_code: null }
      : { key, available: false as const, reason_code: "switched_off_by_the_utility" as const },
  );
}

const CARD_KEYS: ErrandCardKey[] = [
  "pay_bill",
  "report_problem",
  "check_my_area",
  "start_service",
  "what_things_cost",
  "help_answers",
];


function settings(over: Partial<PortalSettings> = {}): PortalSettings {
  return {
    address: { slug: "pine-hill", path: "/pine-hill/portal", url: "https://smartbillhub.bynry.com/pine-hill/portal" },
    is_live: false,
    switches: {
      quick_pay_enabled: true,
      self_read_enabled: false,
      plans_enabled: true,
      requests_enabled: true,
      outage_reporting_enabled: true,
    },
    agreement_link_valid_days: 7,
    bill_link_valid_days: 30,
    usage: [
      { key: "requests_from_portal", count: 0, reason: null },
      { key: "readings_sent_in", count: null, reason: "readings_off" },
    ],
    ...over,
  };
}

function branding(over: Partial<PortalBranding> = {}): PortalBranding {
  return {
    shared: {
      trading_name: "Pine Hill Water & Power",
      legal_name: "Pine Hill Water & Power",
      brand_primary_hex: "#EC3013",
      brand_accent_hex: "#E15B47",
      has_logo: false,
      logo_ref: null,
      logo: null,
      mark: { letters: "PH", background_hex: "#EC3013", ink_hex: "#FFFFFF", contrast_ratio: 5.1 },
      edited_at: "/settings/company",
    },
    portal_only: {
      strapline: "Your account, your bills and your meter readings — any time.",
      front_page_service_ids: ["0192a000-0000-7000-8000-000000000001"],
      office_hours_text: "8am to 5pm, Monday to Friday",
      emergency_phone: "(512) 555-0100",
    },
    services: [
      { id: "0192a000-0000-7000-8000-000000000001", code: "water", name: "Water", color: "#1e6b8f" },
      { id: "0192a000-0000-7000-8000-000000000002", code: "electric", name: "Electric", color: "#ec3013" },
    ],
    preview: {
      tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: "#EC3013", brand_accent_hex: "#E15B47" },
      is_live: true,
      // `DEF-CWP-3994` — the Regional settings ride on the front payload.
      regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language: null },
      // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`). The
      // back-office preview is served by the SAME `front()` selector, so it
      // carries the field whether or not this screen draws a picker.
      locales: ["en", "es"],
      cards: offered("pay_bill", "report_problem", "start_service", "what_things_cost"),
      links: { help: false, visit: false },
      services: [{ code: "water", name: "Water", color: "#1e6b8f" }],
      strapline: "Your account, your bills and your meter readings — any time.",
      office_hours_text: "8am to 5pm, Monday to Friday",
      emergency_phone: "(512) 555-0100",
    },
    ...over,
  };
}

function render(path: string, data: { settings?: PortalSettings; branding?: PortalBranding }, readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (data.settings) queryClient.setQueryData(queryKeys.portalSettings, data.settings);
  if (data.branding) queryClient.setQueryData(queryKeys.portalBranding, data.branding);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <CustomerPortalTab readOnly={readOnly} segment={path.endsWith("/branding") ? "branding" : undefined} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;
const OVERVIEW = "/pine-hill/settings/reference-data/customer-portal";
const BRANDING = `${OVERVIEW}/branding`;

describe("CWP-069 · Portal settings · Overview (US-CWP-069)", () => {
  it("TC-1: the address reads the slug as a path, copyable, with a QR code", () => {
    const html = render(OVERVIEW, { settings: settings() });
    expect(html).toContain('data-screen="CWP-069"');
    expect(html).toContain("https://smartbillhub.bynry.com/pine-hill/portal");
    expect(html).toContain('data-portal-address=""');
    expect(html).toContain("Copy");
    expect(html).toContain("QR code for your bills");
  });

  it("TC-3: a brand-new tenant is OFF, and self-read is the one switch off among the five", () => {
    const html = render(OVERVIEW, { settings: settings() });
    expect(html).toContain('data-portal-live="off"');
    expect(html).toMatch(/data-switch="quick_pay_enabled"[\s\S]*?data-switch-state="on"/);
    expect(html).toMatch(/data-switch="self_read_enabled"[\s\S]*?data-switch-state="off"/);
    expect((html.match(/data-switch="/g) ?? []).length).toBe(5);
  });

  it("TC-7: readings off is a sentence, not a zero; a count the product cannot take is absent", () => {
    const html = render(OVERVIEW, { settings: settings() });
    expect(html).toContain("Readings are off, so nothing is counted");
    expect(html).toContain('data-usage="requests_from_portal"');
    expect(html).not.toContain('data-usage="customers_enrolled"');
  });

  it("TC-10: Add it to the bill template is a control on the screen", () => {
    expect(render(OVERVIEW, { settings: settings() })).toContain("Add it to the bill template");
  });

  it("BR-SHL-025: a view-only role sees every switch disabled with the reason", () => {
    const html = render(OVERVIEW, { settings: settings() }, true);
    expect((html.match(/role="switch"[^>]*disabled=""/g) ?? []).length).toBe(6);
  });

  it("B14 rule 31: no uuid is a visible value", () => {
    expect(render(OVERVIEW, { settings: settings() })).not.toMatch(UUID);
  });
});

describe("CWP-070 · Portal settings · Branding (US-CWP-070)", () => {
  it("TC-1: the shared four are read-only with a link to Company", () => {
    const html = render(BRANDING, { branding: branding() });
    expect(html).toContain('data-screen="CWP-070"');
    expect((html.match(/data-readonly=""/g) ?? []).length).toBe(4);
    expect(html).toContain("#EC3013");
    expect(html).toContain("#E15B47");
    expect(html).toContain('data-link="edit-in-company"');
    expect(html).toContain("/pine-hill/settings/company");
  });

  it("TC-3 · TC-4: the preview IS the front page — strapline and ticked chip drawn by the same component", () => {
    const html = render(BRANDING, { branding: branding() });
    expect(html).toContain('data-portal-preview=""');
    expect(html).toMatch(/data-portal-preview=""[\s\S]*data-screen="CWP-001"/);
    expect(html).toMatch(/data-portal-preview=""[\s\S]*data-service-chip="water"/);
    expect(html).toContain("Your account, your bills and your meter readings — any time.");
    // ⚠ CHIPS SINCE 2026-09-04 (B14 rule 36 breach (e), DEF-CWP-3648): the
    // picker was a WALL OF CHECKBOXES, which r10 rule 9 forbids by name. It is
    // the kit's `ChipMultiSelect` now — the chosen service is a removable chip
    // and the rest live in one add control. The rule that has not changed is
    // rule 31: the chip carries the NAME and the value it sends is the id.
    expect(html).toContain('data-chip-select="services"');
    expect(html).toContain('data-chip-add="services"');
    expect(html).toMatch(/data-chip-add="services"[\s\S]*<option value="[^"]+">Electric<\/option>/);
    expect(html).not.toMatch(new RegExp(`>${"0192a000-0000-7000-8000-000000000001"}<`));
  });

  it("TC-8: Reset to defaults and Save are the two header actions", () => {
    const html = render(BRANDING, { branding: branding() });
    expect(html).toContain('data-action="reset"');
    expect(html).toContain('data-action="save"');
  });
});

describe("the segment strip", () => {
  it("falls back to Overview on an unknown segment (BR-SHL-011's spirit)", () => {
    expect(portalSegmentFromParam(undefined)).toBe("overview");
    expect(portalSegmentFromParam("branding")).toBe("branding");
    // ⚠ `tips` IS A REAL SEGMENT SINCE CR-068 wave D — it used to stand in for
    // "unknown" here, which is what a fallback test must never lean on.
    expect(portalSegmentFromParam("tips")).toBe("tips");
    expect(portalSegmentFromParam("help")).toBe("help");
    expect(portalSegmentFromParam("nothing-of-the-sort")).toBe("overview");
  });
});
