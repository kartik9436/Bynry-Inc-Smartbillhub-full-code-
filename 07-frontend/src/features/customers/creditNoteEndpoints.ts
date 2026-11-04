// ── Trace ──────────────────────────────────────────────
// Change:   CR-059 · CS-37 · task 28 — the P13 Credits tab. The CR's own words:
//           *"THE DIRECT ANSWER TO 'where can a user view all the credit notes
//           for an account?' — NOWHERE. To find every credit note Ajinkya has
//           ever been given, somebody must open each of his bills one at a time
//           and read the panel on each."*
// Story:    US-CUS-010 (the S21 tab bodies) · US-BIL-016 (the correction that
//           writes a credit note)
// Screens:  S21 → Credits tab
// Rules:    B14 rule 31 (RATIFIED 2026-08-31, PO: *"no Databse ID on screen -
//           that is a rule"*) · CLAUDE.md hard rule 2 (a money STRING travels
//           with its CHAR(3) currency and nothing here parses or re-rounds
//           one) · BR-CUS-034 (customers keeps no copy of a billing row — this
//           is one request to billing's own read) · hard-won law 2
// ───────────────────────────────────────────────────────
//
// THE TYPED WRAPPER FOR ONE ROUTE, AND WHY IT IS ITS OWN FILE.
//
// `billChainEndpoints.ts` wrote the reason and it has not changed:
// `api/endpoints.ts` is the file every lane appends to, and on any afternoon it
// holds two or three lanes' half-finished work. One family, one file, one
// lane's diff. Nothing here re-exports or shadows anything `endpoints.ts` or
// `billChainEndpoints.ts` publishes.
//
// ══════════════════════════════════════════════════════════════════════════
// `credit_note_no` IS NULL ON HISTORIC ROWS, PERMANENTLY, AND BY DESIGN
// ══════════════════════════════════════════════════════════════════════════
// CS-37 mints a `CM-` number for every credit note written from 2026-09-02 —
// and it does **not** back-fill the rows that came before, because a credit
// note freezes at issue and a migration that rewrote history would be exactly
// what the freeze exists to prevent. So the null branch is permanent, not
// transitional, and the screen renders the BILL and the DATE for it.
//
// It never renders `id`. That is the whole reason CS-37 exists: the bill-run
// sign-off panel fell back to the row's uuid and printed it at a finance user.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported from `endpoints.ts` so this file adds no
 *  coupling to a file three lanes are editing — `billChainEndpoints`' rule. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One credit note as the account read serves it. */
export interface AccountCreditNote {
  /** The React key and nothing else. B14 rule 31 — never a rendered value. */
  id: string;
  /** `CM-0001`. Null on a historic row; the screen then shows the bill and the
   *  date, which is CS-37's second new rule in as many words. */
  credit_note_no: string | null;
  /** CLAUDE.md hard rule 2 — the decimal STRING and its CHAR(3) partner travel
   *  together, and nothing in this app parses, sums or re-rounds one.
   *  NEGATIVE by database constraint (BR-BIL-074): a credit reduces what the
   *  customer owes, and `MoneyCell` renders the sign the server sent. */
  amount: string;
  currency: string;
  reason: string | null;
  issued_at: string | null;
  /** The bill it was raised against — the id to LINK to, never to print. */
  invoice_id: string | null;
  /** …and the number to print. Blank is normalised to null server-side, so an
   *  empty cell is impossible here (rule 31's other half). */
  invoice_no: string | null;
}

export interface AccountCreditNotes {
  account_id: string;
  credit_notes: AccountCreditNote[];
  count: number;
  /** True when the account holds more than one page of them. The tab SAYS so
   *  rather than showing a partial history that looks complete. */
  truncated: boolean;
}

export const accountCreditNotesKey = (accountId: string) =>
  ["accounts", "credit-notes", accountId] as const;

export async function getAccountCreditNotes(
  accountId: string,
  client: ApiClient = api,
): Promise<AccountCreditNotes> {
  return requireData(
    await client.get<AccountCreditNotes>(
      `/accounts/${encodeURIComponent(accountId)}/credit-notes`,
    ),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-059 §7 · §7b · §8 CS-37 · §11 task 28 · source route
//         apps/billing/credit_notes_api.py → apps/billing/selectors.account_credit_notes
// generated: 2026-09-02 by the CR-059 W5 credit-note identity lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 the type is written AS SERVED and is not widened to match
//         `InvoiceCreditNoteRef` — a field this route does not send must not be
//         renderable from this type (`ChainCreditNote`'s own rule)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
