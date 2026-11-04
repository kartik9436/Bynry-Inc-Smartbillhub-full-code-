// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.8 — screen 7·2 **Debtor**, the screen the debtor
//           list has never had. Blueprint `05-prototype/06 Payments Page
//           Blueprint.pdf` p083–p084, read as IMAGES at 2.0 (B14 rule 42).
//           Screens: 7·2 (S-NEW · PAY-J)
// Rules:    BR-PAY-032 (days late is anchored on the OLDEST UNPAID bill's due
//           date, never the total) · BR-CUS-015 (`accounts.balance` is a CACHE
//           and no screen here reads it) · BR-PAY-017 (the rungs) · B14 rule
//           31 (no database id is ever the visible value of a field) ·
//           BR-SHL-023 (ONE money path) · CLAUDE.md hard rule 2 (a money
//           figure travels with its CHAR(3))
// Tests:    src/features/payments/debtorPage.dom.test.tsx
// ───────────────────────────────────────────────────────
// The typed wrapper for `GET /debtors/{account_id}` — `P4.3`'s read, which has
// been served since earlier today and which nothing called.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE
// ══════════════════════════════════════════════════════════════════════════
// The same reason `bankRecEndpoints.ts` gives in its own header and which has
// only got truer: `endpoints.ts` is **20,297 lines** and every lane appends to
// it, so on any afternoon it holds two or three lanes' half-finished work.
// A pathspec commit naming it publishes all of them (hard-won law 11,
// mechanism five). One family, one file, one lane's diff.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ROUTE IS SERVED. THESE TYPES ARE READ OFF THE PAYLOAD BUILDER
// ══════════════════════════════════════════════════════════════════════════
// `apps/payments/debtor_api.py` mounts `debtors/<str:account_id>` and
// `config/urls.py` includes it, so this describes a LIVE contract. Every
// member below is `apps/payments/debtor_read.debtor`'s own key, field for
// field: **a field the server does not send is not typed here.**
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ EVERY NULL BELOW IS A MEASURED FACT, AND NONE OF THEM MAY BE `?? "0"`
// ══════════════════════════════════════════════════════════════════════════
// A sibling lane shipped **"$0.00 taken today"** onto a live screen where the
// server had said *"I cannot answer that"* — `tsc`, 26 test files and every
// gate passed over it. The cure is in the TYPE: a nullable money figure is
// `string | null` and never `string | undefined`, because `?? "0"` reads as
// tidy on an optional and reads as a lie on a null.
//
//   · `position: null`       — this account owes NOTHING. A measured fact:
//                              `outstanding_positions` returns a row only for
//                              an account with something open. Different from
//                              *"we could not work it out"*, which is on
//                              `problems[]` with a code.
//   · `oldest_due_on: null`  — no unpaid bill carries a due date, so this
//                              account is in NO ageing band (BR-PAY-032). It
//                              still owes the money. **Never rendered as 0.**
//   · `due_on: null`         — this BILL has no due date. `DEF-PAY-6254`.
//   · `account_no: null`     — the account genuinely has no number. The screen
//                              says so in words; it never falls back to the id
//                              (B14 rule 31).
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/** A 2xx with no body where the contract promises one is a server bug. Restated
 *  here rather than imported so this file adds no coupling to `endpoints.ts`. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One named thing this read could not answer, with the rule behind it. */
export interface DebtorProblem {
  code: string;
  br_ref: string;
  detail: string;
}

/**
 * One open bill of this account — `apps.payments.open_bills._bill_row`.
 *
 * The drawing's *"What is owed"* table: **BILL · ISSUED · DUE · AGE · TOTAL ·
 * OWES NOW.** `AGE` is not a served field and is not one here either: it is the
 * distance between `due_on` and the business day the screen asked about, which
 * is two dates the server gave and a subtraction with no money in it.
 */
export interface DebtorBill {
  /** ⚠ NEVER RENDER THIS (B14 rule 31). It keys the row; `number` is visible. */
  invoice_id: string | null;
  /** `BL-2606-000112` — the reference a clerk reads out on the telephone. */
  number: string;
  issued_on: string | null;
  /** ⚠ `DEF-PAY-6254` — served since 2026-09-23. `null` is MEASURED: billing
   *  declares the date nullable and BR-PAY-032 refuses to age a bill nobody can
   *  place in time. The screen draws a dash and never calls it *not due*. */
  due_on: string | null;
  /** BR-BIL-004 — what the bill CHARGED, immutable. 6dp decimal string. */
  total: string | null;
  /** BR-BIL-072 — what it ASKS for. Differs from `total` only on a budget bill. */
  amount_due: string | null;
  allocated: string | null;
  /** The drawing's **OWES NOW** — `amount_due − allocated`, done by the server. */
  open_balance: string | null;
  currency: string | null;
}

/** `apps.payments.debtor_read._position_row`, or **null meaning owes nothing**. */
export interface DebtorPosition {
  /** NET of the account's credit (CR-059 CS-38) — the figure the chase runs on. */
  balance: string;
  /** What the bills alone say, before any credit came off. */
  gross_balance: string;
  credit_applied: string;
  /** ⚠ **BR-PAY-032's ANCHOR** — the blueprint calls it out by name: *"Oldest —
   *  the number that decides the ladder rung, not the total."* */
  oldest_due_on: string | null;
  invoice_count: number;
  /** Unpaid bills carrying NO due date, by number. Excluded from the anchor and
   *  reported, never placed on a date nobody has. */
  undated: string[];
}

/** The live payment plan, or **null meaning there is no plan** — not *unknown*. */
export interface DebtorPlan {
  id: string;
  status: string;
  /** Instalments due by `as_of` and unmet. BR-PAY-016 as amended: the day one is
   *  missed the pause lifts and chasing resumes, with the plan STILL ACTIVE. */
  missed: number;
  suspend_late_fees: boolean;
  suspend_disconnect: boolean;
}

/** The rung already SENT and when — `collections_read.account_position`'s
 *  `state`. What stops a manual send doubling one. */
export interface DebtorLadderState {
  tier: string | null;
  tier_sent_on: string | null;
  last_notice_on: string | null;
  /** The drawing's *"disconnection 09/28"* — what goes out next, and when. */
  next_step_due: string | null;
}

/** Why this account is, or is not, being chased. */
export interface DebtorCollections {
  account_id: string;
  as_of: string;
  pause: Record<string, unknown>;
  disconnect_blocked: boolean;
  disconnect_detail: string;
  late_fee_suspended: boolean;
  plan: DebtorPlan | null;
  state: DebtorLadderState;
  rungs: string[];
  problems: DebtorProblem[];
}

/** One line of the drawing's *"What we tried"* — `notices.notice_history_row`.
 *  **Sends AND skips**, because an account excluded for a medical hold and one
 *  nobody ever chased must never read the same (J4 step 2). */
export interface DebtorNotice {
  /** ⚠ NEVER RENDER THIS (B14 rule 31). It keys the row. */
  id: string;
  account_id: string;
  notice_type: string;
  tier: string | null;
  /** The drawing's **HOW** — `Email · post`, `Text`, `Counter`. */
  channel: string | null;
  outcome: string | null;
  /** Present on a SKIP. The one thing a collections trail may not do is exclude
   *  somebody silently (`P4.16`). */
  skip_reason: string | null;
  outbound_message_id: string | null;
  detail: Record<string, unknown>;
  /** The drawing's **WHEN**. */
  occurred_on: string | null;
  /** The drawing's **WHO** — resolved to a name by the screen, or *system*. */
  actor_id: string | null;
}

/** `GET /debtors/{account_id}` — everything 7·2 draws, in ONE call. */
export interface DebtorResponse {
  /** ⚠ NEVER RENDER THIS (B14 rule 31). It addresses the API. */
  account_id: string;
  /** `AC-2026-00001` — the drawing's breadcrumb leaf and its subtitle. */
  account_no: string | null;
  as_of: string;
  /** **null = this account owes nothing.** Not *unknown*. */
  position: DebtorPosition | null;
  bills: DebtorBill[];
  bill_count: number | null;
  /** The header's *"across 4 bills"* figure, summed over exactly the rows
   *  below it, so the two can never disagree. */
  total_open: string | null;
  currency: string | null;
  collections: DebtorCollections;
  /** ONE PAGE of the trail — the only unbounded one of the four, paged in SQL. */
  history: DebtorNotice[];
  /** A real `COUNT(*)`, never the length of what was built. */
  history_count: number;
  history_offset: number;
  history_limit: number;
  history_page: number;
  rungs: string[];
  problems: DebtorProblem[];
}

/**
 * `GET /debtors/{account_id}` — the one call behind screen 7·2.
 *
 * `asOf` is REQUIRED for the same reason it is required on the wire
 * (`BR-TEN-043`): a server clock decides a business day in the SERVER's
 * timezone, and the tenant's own cannot be chosen yet.
 *
 * ⚠ **ONLY THE HISTORY PAGES**, and `NFR-3` is why: the position is one row,
 * the ladder state is one row, and the open bills are bounded by the account.
 * The notice trail grows for ever, so it is the one that takes a page.
 */
export async function getDebtor(
  params: { accountId: string; asOf: string; historyPage?: number; historyPer?: number },
  client: ApiClient = api,
): Promise<DebtorResponse> {
  return requireData(
    await client.get<DebtorResponse>(`/debtors/${encodeURIComponent(params.accountId)}`, {
      query: {
        as_of: params.asOf,
        history_page: params.historyPage === undefined ? undefined : String(params.historyPage),
        history_per: params.historyPer === undefined ? undefined : String(params.historyPer),
      },
    }),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/06 Payments Page Blueprint.pdf p083–p084 rendered at 2.0 and read as IMAGES · 06-backend/apps/payments/debtor_read.py + debtor_api.py (the payload builder, field for field) · CR-138-BRC07 §3 P4.3/P4.8
// generated: 2026-09-23 by LANE P4-SCREENS-A
// checklist: A✔ B✔(the route is mounted and this is its first caller) C✔ D=n/a E✔(DebtorPage renders it) F✔ G✔ H=n/a
// exceptions: (1) typed in its own file rather than appended to the 20,297-line `endpoints.ts`, for the reason `bankRecEndpoints.ts` already records — a pathspec commit on that file publishes every lane mid-edit in it · (2) `due_on` is typed because `DEF-PAY-6254` made the server send it TODAY; before that the drawing's DUE and AGE columns had no source at all · (3) nothing here re-exports or shadows anything `endpoints.ts` publishes
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
