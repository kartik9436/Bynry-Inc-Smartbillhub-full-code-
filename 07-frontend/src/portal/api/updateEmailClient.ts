// ── Trace ──────────────────────────────────────────────
// Change:   CR-189-BRC10 — the five calls behind `/{tenant}/portal/update-email`
//           (CWP-079). Its own file so this change stays out of
//           `portalClient.ts`, which a sibling lane edits the same day.
// Rules:    BR-CWP-032 (nothing about the account before it is proved) ·
//           BR-CWP-033 (the contacts arrive MASKED and are shown as they came)
// Tests:    src/portal/signin/UpdateEmail.dom.test.tsx
// Impacts:  06-backend/apps/portal/email_update_api.py
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("empty 200 body where the contract promises one (portal edge)");
  }
  return response.data;
}

/** One contact on file. `key` is opaque; `masked` is shown exactly as it came. */
export interface ContactOption {
  key: string;
  channel: "sms" | "email" | string;
  masked: string;
}

/** The utility's own phone and hours, from Settings. Either may be absent. */
export interface OfficeContact {
  phone: string | null;
  hours: string | null;
}

export interface UpdateEmailFound {
  matched: boolean;
  reason?: string;
  ref?: string | null;
  options?: ContactOption[];
  office?: OfficeContact;
}

export interface UpdateEmailSent {
  sent: boolean;
  reason?: string;
  ref?: string;
  sent_to?: string;
  channel?: string;
  expires_in_minutes?: number;
}

export interface UpdateEmailStarted {
  ok: boolean;
  reason?: string;
  ref?: string;
  sent_to?: string;
  expires_in_minutes?: number;
}

export interface UpdateEmailDone {
  ok: boolean;
  reason?: string;
  /** `check_email` — a reset link went to the new address; `enrol` — no login yet. */
  next?: "check_email" | "enrol" | string;
  sent_to?: string;
}

const BASE = "/portal/update-email";

export async function findForEmailUpdate(
  body: { account_number: string; postcode: string; last_name: string },
  client: ApiClient = api,
): Promise<UpdateEmailFound> {
  return requireData(await client.post<UpdateEmailFound>(`${BASE}/find`, body));
}

export async function sendEmailUpdateCode(
  body: { ref: string; option: string },
  client: ApiClient = api,
): Promise<UpdateEmailSent> {
  return requireData(await client.post<UpdateEmailSent>(`${BASE}/send-code`, body));
}

export async function verifyEmailUpdateCode(
  body: { ref: string; code: string },
  client: ApiClient = api,
): Promise<{ result: string }> {
  return requireData(await client.post<{ result: string }>(`${BASE}/verify-code`, body));
}

export async function startNewEmail(
  body: { ref: string; email: string },
  client: ApiClient = api,
): Promise<UpdateEmailStarted> {
  return requireData(await client.post<UpdateEmailStarted>(`${BASE}/new-email`, body));
}

export async function confirmNewEmail(
  body: { ref: string; code: string; email: string },
  client: ApiClient = api,
): Promise<UpdateEmailDone> {
  return requireData(await client.post<UpdateEmailDone>(`${BASE}/confirm`, body));
}

// ── The SIGNED-IN change (PO 2026-10-22, option A; DEF-CWP-10401) ───────────
// A code to the NEW address; only once it is entered do the contact email and
// the sign-in email move together. The session decides whose login.

export interface SignedInEmailDone {
  ok: boolean;
  reason?: string;
  accounts_updated?: number;
  sent_to?: string;
}

export async function startSignedInEmailChange(
  body: { email: string },
  client: ApiClient = api,
): Promise<UpdateEmailStarted> {
  return requireData(
    await client.post<UpdateEmailStarted>("/portal/my-details/email/start", body),
  );
}

export async function confirmSignedInEmailChange(
  body: { ref: string; code: string; email: string },
  client: ApiClient = api,
): Promise<SignedInEmailDone> {
  return requireData(
    await client.post<SignedInEmailDone>("/portal/my-details/email/confirm", body),
  );
}
