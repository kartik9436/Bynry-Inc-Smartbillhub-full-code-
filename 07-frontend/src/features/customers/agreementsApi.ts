// ── Trace ──────────────────────────────────────────────
// Change:  CR-190-BRC10 lane AGREEMENT — the staff side of click-to-accept
//          agreements (`apps/customers/agreements_api.py`)
// Tests:   src/features/customers/AccountAgreementsPanel.dom.test.tsx
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";

export type AgreementStatus = "pending" | "accepted" | "expired" | "voided";

/** One request on an account. `id` is a React key only (B14 rule 31). */
export interface AccountAgreement {
  id: string;
  template_code: string;
  agreement_name: string;
  version: number;
  status: AgreementStatus;
  issued_at: string;
  expires_at: string;
  accepted_at: string | null;
  accepted_date: string | null;
  accepted_name: string | null;
  /** The `account_documents` filing of the stamped copy, once accepted. */
  accepted_document_id: string | null;
  sent_by_email: boolean;
  sent_by_letter: boolean;
}

export function accountAgreementsPath(accountId: string): string {
  return `/accounts/${encodeURIComponent(accountId)}/agreements`;
}

export async function listAccountAgreements(
  accountId: string,
  client: ApiClient = api,
): Promise<AccountAgreement[]> {
  const response = await client.get<{ results: AccountAgreement[] }>(accountAgreementsPath(accountId));
  return response.data?.results ?? [];
}

export async function resendAccountAgreement(
  accountId: string,
  requestId: string,
  client: ApiClient = api,
): Promise<AccountAgreement> {
  const response = await client.post<AccountAgreement>(
    `${accountAgreementsPath(accountId)}/${encodeURIComponent(requestId)}/resend`,
    {},
  );
  if (response.data === null || response.data === undefined) {
    throw new Error("empty 201 body where the contract promises one (agreements/resend)");
  }
  return response.data;
}

/** The newest request per agreement — what the account's chip summarises. */
export function latestPerAgreement(rows: readonly AccountAgreement[]): AccountAgreement[] {
  const seen = new Set<string>();
  const out: AccountAgreement[] = [];
  for (const row of rows) {
    if (seen.has(row.template_code)) continue;
    seen.add(row.template_code);
    out.push(row);
  }
  return out;
}
