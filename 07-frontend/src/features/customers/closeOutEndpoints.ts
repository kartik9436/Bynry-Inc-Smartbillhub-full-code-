// ── Trace ──────────────────────────────────────────────
// Component: the two typed wrappers behind S21/S22's CLOSE-OUT act.
// Story:    US-CUS-005 (the only story that owns any part of an account's
//           terminal path). ⚠ NO STORY OWNS THE CLOSE-OUT; one is OWED.
// Change:   DEF-724 — *"A disconnected customer can never be closed - Add a
//           separate close-out act — Cleaner in the record"* (PO 2026-08-27).
// Rules:    BR-CUS-430 · BR-CUS-431 · BR-CUS-082 · BR-CUS-110 · BR-CUS-015
//           (`accounts.balance` is a CACHE — the server reads AR, and a
//           `display: null` is a READING THAT FAILED, never $0.00)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE
// ══════════════════════════════════════════════════════════════════════════
// `worklistEndpoints.ts`'s reason, unchanged and re-measured on 2026-08-27:
// `api/endpoints.ts` is the file every lane appends to, and on this afternoon
// it holds another lane's unpushed work. One family, one file, one lane's diff.
// Nothing here re-exports or shadows anything `endpoints.ts` publishes.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported, for the reason in the header. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/**
 * One stated absence — `{code, br_ref?, tracks?, detail}`, the shape every
 * customers selector builds. `detail` is the only field that reaches a user;
 * `tracks` names the register row whose closure kills the sentence, so an
 * absence expires by itself instead of outliving its question (G38).
 */
export interface CloseOutAbsence {
  code: string;
  br_ref?: string;
  tracks?: string;
  detail: string;
}

/** CLAUDE.md rule 2's two shapes, as the server builds them: `stored` is 4 dp,
 *  `display` is the 2 dp the SERVER already rounded. A screen renders
 *  `display` or the reason — never a re-rounding of `stored` (DEF-088). */
export interface CloseOutMoney {
  stored: string;
  display: string;
}

/** Why the act is refused, in the words of the rule that refuses it. */
export interface CloseOutBlocker {
  code: string;
  message_key: string;
  br_ref: string;
  detail: string;
}

/** BR-CUS-082, as the server will apply it — shown BEFORE the commit so the
 *  clerk knows whether a debt is about to start a TIER-1 collections ladder. */
export interface CloseOutDunning {
  chased: boolean;
  restarts_at_tier: number;
  escalates_to_disconnection: boolean;
  /** `null` when the balance could not be read — NOT "no ladder" (DEF-628). */
  will_restart: boolean | null;
  reason: string;
  subject: string;
  subject_detail: string;
  detail: string;
}

/**
 * `GET /accounts/{id}/close-out` — the PREVIEW. Writes nothing.
 *
 * ⚠ **`closed_at_will_be` IS THE POINT OF THIS CALL.** BR-CUS-431 writes the
 * CUT date into `accounts.closed_at`, not the day the clerk clicks, and that
 * date is the one thing on the screen no correction row can un-say (hard rule
 * 4). It is shown before it is written, and it is not an input.
 */
export interface CloseOutEligibility {
  account_id: string;
  account_no: string;
  eligible: boolean;
  blocked_by: CloseOutBlocker | null;
  closed_at_will_be: string | null;
  cut_on: string | null;
  case_no: string | null;
  /**
   * ── WHAT WAS CUT, AND WHEN — served since 2026-09-13, lane A ─────────────
   * The blueprint's second panel on this screen asks for the case, the REASON,
   * the SERVICES CUT, the cut date and what was owed at the cut. Four of the
   * five were on `DisconnectCase` all along and none of them was on the wire,
   * so the panel could not be drawn and a clerk ending an account could not see
   * what they were ending.
   *
   * OPTIONAL, every one, and for the reason `premise_locality` is: a bundle
   * deployed against a server that has not shipped them yet reads `undefined`
   * and draws one row fewer, rather than throwing on a terminal screen.
   *
   * ⚠ `services_cut` is a list of service CODES. B14 rule 31 keeps a code off
   * the screen, so the component renders them as this product's service badges
   * and never as their slugs.
   */
  cut_reason?: string | null;
  services_cut?: string[];
  case_opened_on?: string | null;
  /** What was owed the day the supply was cut. `null` is a real answer on a
   *  case opened before the column existed, and the screen says which — it is
   *  never back-filled from the live balance, because two figures under one
   *  label is how a clerk reads a payment that never happened. */
  outstanding_at_cut?: CloseOutMoney | null;
  /** `null` means the READING FAILED. It is never rendered as `$0.00` — a
   *  fabricated zero on an account in arrears looks exactly like a settled
   *  account (DEF-127/DEF-628). */
  balance: CloseOutMoney | null;
  balance_unreadable: boolean;
  currency: string;
  dunning_if_closed: CloseOutDunning;
  absences: CloseOutAbsence[];
}

/** What the act recorded — the TWO dates, side by side, because the whole
 *  point of BR-CUS-430 is that they are different and the record shows both. */
export interface CloseOutRecord {
  case_id: string;
  case_no: string | null;
  closed_out_on: string | null;
  closed_out_by: string | null;
  reason: string;
  cut_on: string;
  closed_at: string;
  service_agreements_ended: number;
}

export interface CloseOutResult {
  id: string;
  account_no: string;
  close_out: CloseOutRecord;
  balance_at_close_out: CloseOutMoney | null;
  dunning: CloseOutDunning;
  warnings: CloseOutAbsence[];
}

/** The ONLY three fields the server accepts. `closed_at` is DERIVED and is not
 *  offered — a payload that could name the date is a payload that could get it
 *  wrong (BR-CUS-431). */
export interface CloseOutRequest {
  closed_out_on: string;
  reason: string;
  status?: string;
}

// ⚠ **THE LEADING SLASH IS LOAD-BEARING — `DEF-CUS-5073`, 2026-09-12.**
// `apiPath(tenant, path)` returns `${API_PREFIX}/${tenant}${path}`. Without the
// slash the tenant segment and `accounts` weld into one word and BOTH calls
// below go to `/api/brazosbendaccounts/<id>/close-out` — a 404 on every tenant.
// It failed SAFE and it failed SILENT: the preview's own absence handling
// renders `Account closed on —`, `no reference` and `could not be read`, and
// leaves the commit disabled with no reason, which is exactly what the screen
// shows when the server has legitimately nothing to say. The server's real
// answer on the same account is a 409 naming the rule in plain words, and no
// clerk ever saw it. `apiPathLiteral.guard.test.ts` refuses this line now.
const path = (accountId: string) => `/accounts/${encodeURIComponent(accountId)}/close-out`;

export async function getCloseOutEligibility(
  accountId: string,
  client: ApiClient = api,
): Promise<CloseOutEligibility> {
  return requireData(await client.get<CloseOutEligibility>(path(accountId)));
}

export async function closeOutAccount(
  accountId: string,
  body: CloseOutRequest,
  client: ApiClient = api,
): Promise<CloseOutResult> {
  // ⚠ **`body` IS THE SECOND POSITIONAL ARGUMENT, NOT A KEY — `DEF-CUS-5074`.**
  // `ApiClient.post(path, body, options)`. This line read `post(path, { body })`,
  // so the wire payload was `{"body":{"closed_out_on":…,"reason":…}}` and the
  // server refused it BY NAME — `422 VAL-002 customers.account.unknown_field`,
  // `field_errors:[{field:"body"}]`. The three fields sent flat get the real
  // business answer instead. `tsc` passes over the wrong shape because `body`
  // is typed `unknown`, which is what an HTTP body legitimately is, so nothing
  // but posting it at a running server could tell the two apart. It sat behind
  // `DEF-CUS-5073`'s 404: the commit was disabled, so this was never reached.
  return requireData(await client.post<CloseOutResult>(path(accountId), body));
}
