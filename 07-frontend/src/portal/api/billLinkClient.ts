// ── Trace ──────────────────────────────────────────────
// Change:  DEF-BIL-10531 — the bill email's direct PDF link
//          (`apps/billing/bill_link_public_api.py`)
// Rules:   decision log 2026-10-22 *"One-time link secrets travel in the URL
//          FRAGMENT"* — the secret goes in the request BODY, never the address
// Tests:   src/portal/bill-link/BillLinkPage.dom.test.tsx
// ───────────────────────────────────────────────────────
import { api, apiPath, currentTenant, DEFAULT_BASE_URL } from "@/api/client";
import type { ApiClient } from "@/api/client";

/** The page's facts once the link has matched. */
export interface BillLinkOpen {
  state: "open";
  utility_name: string | null;
  bill_no: string | null;
  bill_date: string | null;
  due_date: string | null;
  /** The last day the link works, in the utility's zone. */
  expires_on: string | null;
}

/** ONE answer for an unknown, expired or foreign link. */
export interface BillLinkUnavailable {
  state: "unavailable";
  support_phone: string | null;
}

export type BillLink = BillLinkOpen | BillLinkUnavailable;

export const BILL_LINK_OPEN_PATH = "/bill-links/open";
export const BILL_LINK_DOCUMENT_PATH = "/bill-links/document";

export async function openBillLink(token: string, client: ApiClient = api): Promise<BillLink> {
  const response = await client.post<BillLink>(BILL_LINK_OPEN_PATH, { token });
  if (response.data === null || response.data === undefined) {
    throw new Error("empty 200 body where the contract promises one (bill-links/open)");
  }
  return response.data;
}

export type BillLinkDocument =
  | { kind: "pdf"; blob: Blob; filename: string }
  | { kind: "unavailable"; phone: string | null };

function filenameOf(disposition: string | null): string {
  const match = /filename="?([^";]+)"?/i.exec(disposition ?? "");
  return match?.[1] ?? "bill.pdf";
}

/**
 * The kept PDF. A plain `fetch`, because the shared client reads JSON only —
 * and a POST, because the secret may not ride in an address a server logs.
 */
export async function fetchBillLinkDocument(
  token: string,
  tenant: string = currentTenant(),
  fetchImpl: typeof fetch = fetch,
): Promise<BillLinkDocument> {
  const response = await fetchImpl(`${DEFAULT_BASE_URL}${apiPath(tenant, BILL_LINK_DOCUMENT_PATH)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/pdf, application/json" },
    body: JSON.stringify({ token }),
    credentials: "omit",
  });
  if (!response.ok) {
    throw new Error(`bill-links/document answered ${response.status}`);
  }
  const type = response.headers.get("Content-Type") ?? "";
  if (type.startsWith("application/pdf")) {
    return {
      kind: "pdf",
      blob: await response.blob(),
      filename: filenameOf(response.headers.get("Content-Disposition")),
    };
  }
  const body = (await response.json()) as BillLinkUnavailable;
  return { kind: "unavailable", phone: body.support_phone ?? null };
}
