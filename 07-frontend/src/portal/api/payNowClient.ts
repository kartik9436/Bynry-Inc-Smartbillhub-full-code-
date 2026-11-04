// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09) — pay now, and where the payment will land,
//           BEFORE it commits. Screen: CWP-038
// Rules:    BR-CWP-058 (the panel, before the commit) · BR-CWP-056 (a refused
//           control carries its reason — the REASON IS A CODE on the wire and
//           a sentence in eleven catalogues) · BR-CWP-057 (a token, never a card
//           number — read the fields below as the rule: there is no
//           `gateway_token` on this type because there is none on the wire) ·
//           BR-CWP-011 (the signed-in surface calls the PORTAL edge) ·
//           BR-CWP-047 (nothing here is cached) · CLAUDE.md hard rule 2 (money
//           travels as a STRING beside its currency, never as a number)
// Tests:    src/portal/payments/PayNow.dom.test.tsx
// Impacts:  06-backend/apps/portal/api.py (the shape these types are written
//           against) · apps/portal/seams/pay_now_seam.py
// ───────────────────────────────────────────────────────
// Hand-written against `06-backend/apps/portal/api.py`.
//
// ⚠ **ITS OWN FILE RATHER THAN THREE MORE FUNCTIONS IN `portalClient.ts`, AND
// THE REASON IS HARD-WON LAW 11.** Four lanes are building six payment screens
// in six worktrees at once and `portalClient.ts` is one file: a pathspec commit
// takes the whole working-tree content of every path it names, so the second
// lane to commit it silently reverts the first — with a correct file count, its
// own hunks present, and nothing anywhere looking wrong. `guestClient.ts`
// already establishes that this surface may have more than one client module.

import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** The contract promises a body; an empty 200 is a defect, not a value. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("empty 200 body where the contract promises one (portal pay-now)");
  }
  return response.data;
}

/**
 * A saved card or bank mandate — **a brand, four digits and nothing else**
 * (`BR-CWP-057`).
 *
 * ⚠ **THERE IS NO `gateway_token` ON THIS TYPE BECAUSE THERE IS NONE ON THE
 * WIRE.** The token is read server-side for the length of one charge; a
 * response body carrying it would put it in a browser, a proxy log and a
 * screenshot. `id` is served so the screen can say which method was chosen and
 * is **never a visible value** (B14 rule 31) — `label` is what a person reads.
 */
export interface PortalInstrument {
  id: string;
  label: string;
  brand: string;
  last_four: string;
  kind: "card" | "bank";
  status: string;
  used_for: string[];
  expires_month: number | null;
  expires_year: number | null;
  selectable: boolean;
  /** A CODE, never a sentence. Eleven catalogues write the words (B14 rule 35). */
  held_reason: string | null;
}

/** One open bill, exactly as `payments`' own picker read serves it. */
export interface PortalOpenBill {
  invoice_id: string | null;
  number: string;
  issued_on: string | null;
  total: string | null;
  amount_due: string | null;
  allocated: string | null;
  open_balance: string | null;
  currency: string | null;
}

/**
 * `GET accounts/{id}/pay-now` — what `CWP-038` draws before anything is typed.
 *
 * ⚠ **`held_reason` IS SERVED AND NOT INFERRED HERE.** Whether the utility has
 * connected a processor, whether the account is cash-only and whether this login
 * holds `pay` are facts the server has and the browser does not. A screen that
 * guessed would be one deploy away from a live-looking button over nothing at
 * all — `DEF-CWP-3925` exactly.
 */
export interface PortalPayNow {
  account_no: string | null;
  balance: string;
  currency: string | null;
  bills: PortalOpenBill[];
  bill_count: number;
  instruments: PortalInstrument[];
  can_pay: boolean;
  held_reason: string | null;
  /** The tenant's between-bill walk, on the wire so the footer under the panel
   *  states the rule that produced the rows rather than a sentence typed once. */
  order: string;
  /** `sandbox` while a utility is testing. The confirmation says so — a customer
   *  is entitled to know no real money moved (PO ruling 2026-09-05 §3). */
  environment: string | null;
  problems: { code: string }[];
}

/** One line of the *where it will go* panel. `owing_after` is the figure
 *  `US-CWP-045` TC-4 asks the screen to show BEFORE the commit. */
export interface PortalLanding {
  number: string;
  owing: string;
  paying: string;
  owing_after: string;
}

/**
 * `POST accounts/{id}/pay-now/preview` — **writes nothing, and mints the key.**
 *
 * ⚠ **THAT IS NOT A CONTRADICTION AND IT IS THE POINT** (`US-CWP-045` TC-7).
 * The idempotency key has to exist *before the first request leaves*, and the
 * first request leaves on the commit — so a key minted there could never cover
 * the one case it is for. The screen keeps `idempotency_key` and presents the
 * same string on the commit **and on every retry of it**.
 */
export interface PortalPayPreview {
  amount: string;
  currency: string | null;
  order: string;
  lands_on: PortalLanding[];
  credit_carried: string;
  remaining_balance: string;
  idempotency_key: string;
  /** Always `[]` — so a caller can tell a preview from a commit. */
  writes: string[];
}

/**
 * What the commit answers.
 *
 * ⚠ **FOUR OUTCOMES AND `no_answer` IS ITS OWN WORD.** *Declined* means no money
 * moved; *no answer* means nobody knows (`BR-INT-018`). Collapsing them would
 * tell a customer their card was refused when it may have been charged — and the
 * screen's two sentences are genuinely different sentences because of it.
 */
export type PayOutcome = "paid" | "declined" | "no_answer" | "refused";

export interface PortalPayResult {
  outcome: PayOutcome;
  held_reason: string | null;
  /** The `PMT-` number a customer can screenshot. Never a row id (rule 31). */
  payment_no: string | null;
  amount: string;
  currency: string | null;
  lands_on: PortalLanding[];
  /** ⚠ Carried back on a timeout so the retry presents the SAME key (TC-7). */
  idempotency_key: string | null;
  environment: string | null;
  problems: { code: string }[];
}

export async function getPayNow(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalPayNow> {
  return requireData(
    await client.get<PortalPayNow>(`/portal/accounts/${accountId}/pay-now`),
  );
}

export async function previewPayment(
  accountId: string,
  body: { amount: string; idempotency_key?: string },
  client: ApiClient = api,
): Promise<PortalPayPreview> {
  return requireData(
    await client.post<PortalPayPreview>(
      `/portal/accounts/${accountId}/pay-now/preview`,
      body,
    ),
  );
}

/**
 * `POST accounts/{id}/pay-now/commit` — the one call in this product that takes
 * a customer's money.
 *
 * ⚠ **`idempotency_key` IS REQUIRED AND IS THE PREVIEW'S.** It is not optional
 * on this signature on purpose: a caller that could omit it would have
 * idempotency that reads correctly and protects nothing.
 */
export async function payNow(
  accountId: string,
  body: { amount: string; instrument_id: string | null; idempotency_key: string },
  client: ApiClient = api,
): Promise<PortalPayResult> {
  return requireData(
    await client.post<PortalPayResult>(
      `/portal/accounts/${accountId}/pay-now/commit`,
      body,
    ),
  );
}
