// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-069 (EP-CWP-12) — `GET/PUT settings/portal` · US-CWP-070 —
//           `GET/PUT settings/portal/branding` · the QR (07-endpoints.md §3).
//           Screens: CWP-069 · CWP-070
// Rules:    CR-068 §0 row 18 (the back-office pair lives in apps/portal) ·
//           US-CWP-069 TC-2 (the address is served, never stored twice) ·
//           US-CWP-070 TC-2 (the shared four are read-only on the wire too)
// Tests:    src/features/tenancy/SettingsCustomerPortalTab.test.tsx
// Impacts:  06-backend/apps/portal/backoffice_api.py (the shape) ·
//           src/api/queryClient.ts (`queryKeys.portalSettings` · `portalBranding`)
// ───────────────────────────────────────────────────────
// Hand-written against `06-backend/openapi/schema.json` + `selectors.overview()`
// / `selectors.branding()`.

import { apiHref } from "./apiHref";
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/** The contract promises a body; an empty 200 is a defect, not a value. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("empty 200 body where the contract promises one (settings/portal)");
  }
  return response.data;
}
import type { CompanyMark } from "./endpoints";
import type { PortalFront, PortalSwitches } from "@/portal/api/guestClient";



export type { PortalSwitches } from "@/portal/api/guestClient";

/** The address, read from `tenants.subdomain` and never stored twice. */
export interface PortalAddress {
  slug: string;
  path: string; // "/pine-hill/portal"
  url: string | null; // scheme + host the request arrived on + path
}

/**
 * WHO IS USING IT — only what the product can count today. A row with
 * `count: null` carries its reason (readings off); a count the product
 * cannot yet take is ABSENT, never a zero.
 */
export interface PortalUsageRow {
  key: "requests_from_portal" | "readings_sent_in" | "customers_enrolled" | "signed_in_this_month";
  count: number | null;
  reason: "readings_off" | null;
}

/** `GET /settings/portal`. */
export interface PortalSettings {
  address: PortalAddress;
  is_live: boolean;
  switches: PortalSwitches;
  /** CR-190-BRC10 — how many days an emailed agreement link stays valid. */
  agreement_link_valid_days: number;
  /** DEF-BIL-10531 — how many days the bill email's PDF link stays valid. */
  bill_link_valid_days: number;
  usage: PortalUsageRow[];
}

/** A PUT carries any subset of the six (each a boolean) and, since
 *  CR-190-BRC10, the agreement link's life in whole days. */
export type PortalSettingsChanges = Partial<
  PortalSwitches & {
    is_live: boolean;
    agreement_link_valid_days: number;
    bill_link_valid_days: number;
  }
>;

export interface PortalServiceOption {
  id: string; // the platform services.id — sent back, never displayed (rule 31)
  code: string;
  name: string;
  color: string | null;
}

/** `GET /settings/portal/branding`. */
export interface PortalBranding {
  shared: {
    trading_name: string;
    legal_name: string | null;
    brand_primary_hex: string | null;
    brand_accent_hex: string | null;
    has_logo: boolean;
    /** CR-172-BRC10 — the logo's reference: the cache key its address carries. */
    logo_ref: string | null;
    logo: { logo_file_id: string; content_type: string } | null;
    mark: CompanyMark;
    edited_at: string; // "/settings/company" — the one home of the shared four
  };
  portal_only: PortalBrandingFields;
  services: PortalServiceOption[];
  preview: PortalFront;
}

export interface PortalBrandingFields {
  strapline: string | null;
  front_page_service_ids: string[];
  office_hours_text: string | null;
  emergency_phone: string | null;
}

export async function getPortalSettings(client: ApiClient = api): Promise<PortalSettings> {
  return requireData(await client.get<PortalSettings>("/settings/portal"));
}

export async function savePortalSettings(
  changes: PortalSettingsChanges,
  client: ApiClient = api,
): Promise<PortalSettings> {
  return requireData(await client.put<PortalSettings>("/settings/portal", changes));
}

export async function getPortalBranding(client: ApiClient = api): Promise<PortalBranding> {
  return requireData(await client.get<PortalBranding>("/settings/portal/branding"));
}

export async function savePortalBranding(
  changes: Partial<PortalBrandingFields>,
  client: ApiClient = api,
): Promise<PortalBranding> {
  return requireData(await client.put<PortalBranding>("/settings/portal/branding", changes));
}

/**
 * `GET /settings/portal/qr.svg` as a URL an `<img>` or a download link can
 * carry, ON THE API'S ORIGIN through `apiHref()` (`DEF-CWP-9718`: built with
 * `apiPath()` it had no origin, so on a two-host deployment the browser asked
 * the app's static host and drew a broken image). The session cookie rides
 * (same site) and the server answers for the caller's own tenant. `slug` is the one the SERVER served in
 * `PortalSettings.address` (read off `tenants.subdomain`), so the link is
 * built from the same fact the screen displays and needs no window.
 * `download` adds the attachment disposition (B14 rule 4: `↓` is a download).
 */
export function portalQrUrl(slug: string, download = false): string {
  return apiHref(`/${slug}${download ? "/settings/portal/qr.svg?download=1" : "/settings/portal/qr.svg"}`);
}
