// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-014 (Send statement) — `CR-094-BRC01` wave M
//           Screens: S21 Account detail, quick action `ACC-Q07`
// Rules:    BR-CUS-040 (statement != bill) · A19 §1 + rule 1 (the "nothing is
//           due" disclaimer) · BR-NOT-005 / BR-NOT-013 (QUEUED, never sent) ·
//           BR-TEN-043 (the caller names the dates) · BR-SHL-023 (one money
//           formatting path) · CLAUDE.md hard rule 2 (money 4dp on the wire,
//           2dp on screen)
// Tests:    07-frontend/src/features/customers/accountQuickActions.test.ts
// Impacts:  apps/billing/statement_api.py (the server half)
// ───────────────────────────────────────────────────────
//
// **`POST /accounts/{id}/statement` — the door the ✉ quick action opens.**
//
// ⚠ **ITS OWN FILE, AND THAT IS THE `bankRecEndpoints` RULE RATHER THAN A
// PREFERENCE.** `api/endpoints.ts` and `features/customers/customerEndpoints.ts`
// are both thousands of lines that every lane appends to, and on the day this
// was written eight lanes shared one working tree. A one-function module is a
// file no sibling is editing, so adding it collides with nobody — which is
// hard-won law 11 applied before the push rather than after it.
//
// ⚠ **IT LIVES UNDER `features/billing` BECAUSE THE STATEMENT IS A BILLING
// DOCUMENT.** `apps/notifications/seed_templates.py` says so in as many words
// — *"Bills and statements are BILLING's registry (B2 r10 #4)"* — and the
// server half is `apps/billing/statement.py`. The `accounts/` path segment is
// URL grammar for a thing that hangs off an account, not a claim about which
// module owns it; billing's credit-notes route is mounted on exactly that
// reading.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated here rather than imported from `endpoints.ts` — the same call
 *  `customerEndpoints.ts` makes, and for the same reason it records: that file
 *  is thousands of lines and several lanes are editing it, so importing one
 *  four-line helper from it would buy a coupling far more expensive than the
 *  duplication. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One queue row this call left — or found already there. */
export interface QueuedStatementRow {
  /** `statement_queued` / `statement_email_queued`. A CODE, because the screen
   *  and the dispatch home both group on it and neither can group on a
   *  sentence. */
  code: string;
  /** `pdf_print` or `email`. */
  channel: string;
  message_id: string | null;
  /** **False means it was ALREADY queued**, not that it failed. Asking twice
   *  for the same period is one statement (hard rule 6), and a clerk must
   *  never be told a document was queued twice. */
  created: boolean;
}

/** Something the server could not do, in the server's own words. */
export interface StatementProblem {
  code?: string;
  br_ref?: string;
  detail?: string;
}

export interface QueuedStatement {
  account_id: string;
  /** The window the BOOKS used, echoed back — not the one the form sent. */
  period: { start: string | null; end: string | null };
  currency?: string | null;
  /** ⚠ **4-DECIMAL STRINGS, WHICH IS THE STORED PRECISION AND NOT THE
   *  DISPLAYED ONE** (CLAUDE.md rule 2). Render them through `MoneyCell` —
   *  the one display-rounding path (BR-SHL-023) — never by slicing the
   *  string, or this screen becomes a second place money is rounded and the
   *  first place it is rounded differently. */
  opening_balance: string | null;
  closing_balance: string | null;
  row_count?: number;
  queued: QueuedStatementRow[];
  problems: StatementProblem[];
  /** ⚠ **ALWAYS FALSE, AND IT IS A VALUE RATHER THAN A COMMENT ON PURPOSE.**
   *  No vendor is connected on email, text or post and none is this release
   *  (`BR-NOT-013`, PO 15 August 2026). The screen can ASSERT that it is
   *  saying *queued* rather than *sent*, instead of a reader taking a
   *  docstring's word for it (hard-won law 1). */
  dispatched: boolean;
}

/**
 * **QUEUE this account's statement for a period. It does not send it.**
 *
 * `from` and `to` are ISO days and BOTH ARE REQUIRED — `BR-TEN-043`: the
 * server keeps no default and reads no clock, because a statement covering the
 * wrong three months is wrong in a way nobody notices. A missing or malformed
 * date comes back 422 naming which of the two it is.
 *
 * `copy_no` is the one deliberate door through the idempotency key and it is a
 * HUMAN's: the same account over the same period is the same document and a
 * replay queues nothing, while a clerk who genuinely wants a second copy asks
 * for one.
 */
export async function queueAccountStatement(
  accountId: string,
  period: { from: string; to: string; copy_no?: number },
  client: ApiClient = api,
): Promise<QueuedStatement> {
  return requireData(
    await client.post<QueuedStatement>(
      `/accounts/${encodeURIComponent(accountId)}/statement`,
      period,
    ),
  );
}
