// ── Trace ──────────────────────────────────────────────
// Change:  CR-190-BRC10 lane AGREEMENT — the agreement link's three calls
//          (`apps/customers/agreement_public_api.py`)
// Tests:   src/portal/agreements/AgreementPage.dom.test.tsx
// ───────────────────────────────────────────────────────
import { api, apiPath, currentTenant, DEFAULT_BASE_URL } from "@/api/client";
import type { ApiClient } from "@/api/client";

/** The page's facts once the link has matched. */
export interface AgreementOpen {
  state: "open";
  utility_name: string | null;
  customer_name: string;
  account_no: string;
  agreement_name: string;
  version: number;
  effective_from: string | null;
  /** The agreement text exactly as published, rendered once at issue. */
  text: string;
  expires_at: string;
  /** Today in the UTILITY's zone — the only date the server accepts. */
  today: string;
}

/** ONE answer for an unknown, used, expired or voided link. */
export interface AgreementUnavailable {
  state: "unavailable";
  support_phone: string | null;
}

export type AgreementLink = AgreementOpen | AgreementUnavailable;

export interface AgreementAccepted {
  state: "accepted";
  agreement_name: string;
  accepted_date: string;
  accepted_name: string;
}

export interface AcceptBody {
  agreed: boolean;
  date: string;
  name: string;
}

function base(token: string): string {
  return `/agreements/public/${encodeURIComponent(token)}`;
}

export async function getAgreement(token: string, client: ApiClient = api): Promise<AgreementLink> {
  const response = await client.get<AgreementLink>(base(token));
  if (response.data === null || response.data === undefined) {
    throw new Error("empty 200 body where the contract promises one (agreements/public)");
  }
  return response.data;
}

export async function acceptAgreement(
  token: string,
  body: AcceptBody,
  client: ApiClient = api,
): Promise<AgreementAccepted | AgreementUnavailable> {
  const response = await client.post<AgreementAccepted | AgreementUnavailable>(
    `${base(token)}/accept`,
    body,
  );
  if (response.data === null || response.data === undefined) {
    throw new Error("empty 200 body where the contract promises one (agreements/public/accept)");
  }
  return response.data;
}

/** The PDF as sent — a plain link the browser downloads. */
export function agreementDocumentHref(token: string, tenant: string = currentTenant()): string {
  return `${DEFAULT_BASE_URL}${apiPath(tenant, `${base(token)}/document`)}`;
}
