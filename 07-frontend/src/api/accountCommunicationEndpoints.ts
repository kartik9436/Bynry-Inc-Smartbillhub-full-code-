// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave K — `ACC-S16`, the communication section.
//           Step 1 lane 2 finding F11, drawing `R6` pages 186–188.
// Rules:    BR-NOT-005 (queue rows only — nothing is ever SENT from a screen) ·
//           BR-NOT-013 (post, email and SMS have no provider on this release) ·
//           BR-BIL-036 (an absent address is STATED, never a blank) ·
//           CLAUDE.md rule 6 (the message id is the idempotency key).
// Tests:    07-frontend/src/features/customers/AccountCommunication.dom.test.tsx
// Impacts:  features/customers/AccountCommunicationDialog.tsx (the only
//           consumer) · 06-backend/apps/customers/communication_api.py (every
//           key below is read from it by name).
// ───────────────────────────────────────────────────────
// Its own file, the `bankRecEndpoints.ts` / `notificationRuleEndpoints.ts`
// precedent: `endpoints.ts` holds two or three lanes' half-finished work on any
// afternoon, so one family, one file, one lane's diff (CLAUDE.md law 11,
// mechanism five).
//
// ⚠ **THE HISTORY HALF IS NOT HERE AND THAT IS THE POINT.** *"What has already
// gone out"* is `getOutbound({ filters: { account_id } })`, which `endpoints.ts`
// has published since the S8 queue landed — paginated, searchable, and sorted
// failed-and-bounced-first by the server. A second wrapper over the same route
// would be two spellings free to disagree.
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated here rather than imported from `endpoints.ts`, exactly as
 *  `bankRecEndpoints.ts` restates it, so this file adds no coupling to a file
 *  three lanes are editing. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One row of the compose view's channel table — `communication_api._form`. */
export interface CommunicationChannel {
  channel: string;
  /** Where it would go. `null` with a reason beside it, never a blank. */
  address: string | null;
  /** `BR-BIL-036` — "no email address on file" and "nobody looked" are
   *  different facts, and this column is which one it is. */
  unavailable_reason: string | null;
  on_file: boolean;
  /**
   * ⚠ **WHETHER A ROW QUEUED HERE WOULD ACTUALLY LEAVE THE BUILDING.**
   * `BR-NOT-013`, CONFIRMED 2026-08-15: there is no provider adapter on post,
   * email or SMS and none is coming in this release, so those rows rest
   * `queued`. The screen states it rather than implying delivery — served, not
   * inferred here, so the dialog and the dispatcher cannot disagree.
   */
  delivers: boolean;
  delivers_reason: string | null;
}

/** One row of `customer_events.message_kinds()`. A kind that may not be
 *  composed here carries the code of the rule that owns it instead. */
export interface CommunicationKind {
  kind: string;
  allowed: boolean;
  refusal: string | null;
}

/**
 * One of the utility's own published messages, offered as a starting point.
 *
 * ⚠ **`body` IS ALREADY SAFE TO QUEUE AND THAT IS THE WHOLE POINT.** The server
 * resolves the published version for this account's language, then sorts every
 * token in it: the ones a clerk's message can really carry (`{first_name}`,
 * `{account_no}`, `{utility_name}` …) stay as tokens and dispatch fills them,
 * and the ones only the originating event knows — an amount, a confirmation
 * number — arrive as a blank line for the clerk to type over. So nothing
 * offered here can be queued into a refusal, and nothing reaches a customer
 * with a token printed in it.
 */
export interface CommunicationTemplate {
  /** Internal, never rendered — B14 rule 31. The `name` is what a clerk reads. */
  code: string;
  name: string;
  subject: string;
  body: string;
}

export interface CommunicationForm {
  account_id: string;
  account_no: string | null;
  customer_name: string | null;
  language: string | null;
  kinds: CommunicationKind[];
  /** Empty is a real answer — a tenant with nothing published — and the dialog
   *  simply offers no picker rather than an empty one. */
  templates: CommunicationTemplate[];
  channels: CommunicationChannel[];
}

export interface CommunicationQueued {
  message_id: string | null;
  channels: string[];
  /** `move_message_queued` or `move_message_already_queued` — the second is a
   *  repeated submit finding its own row, never a second message. */
  outcome: string;
  problems: { code: string; detail?: string | null }[];
}

/** `GET /accounts/{id}/communication` — who it would go to, and what may be
 *  written. */
export async function getAccountCommunication(
  accountId: string,
  client: ApiClient = api,
): Promise<CommunicationForm> {
  return requireData(
    await client.get<CommunicationForm>(
      `/accounts/${encodeURIComponent(accountId)}/communication`,
    ),
  );
}

/**
 * `POST /accounts/{id}/communication` — **queue** the message. Never send.
 *
 * ⚠ `message_id` is minted by the CALLER and is the idempotency key (CLAUDE.md
 * rule 6). The dialog mints one when it opens, so a double-clicked *Queue the
 * message* finds its own row instead of writing a second message to a customer.
 */
export async function queueAccountMessage(
  accountId: string,
  body: {
    message_id: string;
    kind: string;
    channels: string[];
    subject: string;
    body: string;
    signed_by: string;
    on_date: string;
  },
  client: ApiClient = api,
): Promise<CommunicationQueued> {
  return requireData(
    await client.post<CommunicationQueued>(
      `/accounts/${encodeURIComponent(accountId)}/communication`,
      body,
    ),
  );
}
