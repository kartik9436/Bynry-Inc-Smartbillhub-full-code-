// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 task 5 — *"Call `/invoices/{id}/chain` and draw the
//           correction chain with `is_latest`"*. The CR's own reality check
//           says of this route: **"Mounted and never called"** — `GET
//           /invoices/{id}/chain` returns the chain head and `is_latest`, and
//           no screen calls it (verified again on this branch, 2026-08-30:
//           `curl` answered 200 with `is_latest:false` for a superseded bill
//           and `is_latest:true` for its replacement).
// Story:    US-BIL-015 TC-3 — *"the chain original ↔ credit note ↔ rebill,
//           navigable both ways"*
// Screens:  S30 → Corrections tab
// Rules:    BR-BIL-048 (a new correction case may only be opened on the LATEST
//           bill in a chain — which is what `is_latest` answers) · BR-BIL-064
//           (the chain HEAD is what a panel shows) · BR-SHL-025 (a control
//           that cannot act renders disabled WITH its reason) · hard-won law 2
//           (built is not wired — this file is the wiring)
// ───────────────────────────────────────────────────────
//
// THE TYPED WRAPPER FOR ONE ROUTE, AND WHY IT IS ITS OWN FILE.
//
// `serviceRequestEndpoints.ts` wrote the reason and it has not changed:
// `api/endpoints.ts` is the file every lane appends to, and on any afternoon it
// holds two or three lanes' half-finished work. One family, one file, one
// lane's diff. Nothing here re-exports or shadows anything `endpoints.ts` or
// `billingOpsEndpoints.ts` publishes.
//
// ══════════════════════════════════════════════════════════════════════════
// THE CHAIN IS NOT THE DETAIL'S THREE FIELDS, AND THE DIFFERENCE IS THE POINT
// ══════════════════════════════════════════════════════════════════════════
// `GET /invoices/{id}` already serves `rebill_of_invoice_id`,
// `corrected_by_invoice_id` and `credit_notes`, and S30's Corrections tab has
// drawn those three since 2026-08-11. What it could NOT answer is the question
// a clerk actually has in front of a corrected bill:
//
//     *"is the one I am looking at the one that counts?"*
//
// `is_latest` and `head` are that answer, they are computed by
// `corrections.latest_in_chain` over the whole chain rather than one hop, and
// they are the gate `BR-BIL-048` puts on opening a new correction case. A
// screen that walked `corrected_by_invoice_id` itself would be a second
// implementation of a rule the server already owns (hard-won law 5) and would
// get a two-step chain wrong.
//
// ⚠ **`credit_note_no` IS NULL ON REAL ROWS AND THAT IS NOT A BUG HERE.** The
// development database's only credit note carries `credit_note_no: null`, so
// the screen states the absence rather than printing an empty cell.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated rather than imported from `endpoints.ts` so this file adds no
 *  coupling to a file three lanes are editing — `worklistEndpoints`' rule. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One end of a chain leg — the id to link to and the number to print. */
export interface ChainInvoiceRef {
  invoice_id: string;
  /** BR-BIL-063 mints a number at DRAFT, but a served field can still be null
   *  (an older row, a partial response), so the screen states the absence. */
  invoice_no: string | null;
  /**
   * ⚠ **THE LEGS GREW A DATE AND A TOTAL ON 2026-09-14 (`CR-101-BRC03`) AND
   * `head` DID NOT.** The blueprint's *What happened* table gives every event a
   * WHEN and an EFFECT; `head` is not an event, it is the answer to *which bill
   * counts now*, and typing it with members the route does not send for it is
   * the exact widening the note below this refuses.
   *
   * OPTIONAL because that is what `head` makes them: one `ChainInvoiceRef`
   * serves three positions and only two of them carry these.
   */
  issued_at?: string | null;
  /** CLAUDE.md hard rule 2 — the decimal STRING and its CHAR(3) partner travel
   *  together. Nothing in this app parses, sums or re-rounds one. */
  total?: string;
  currency?: string;
}

/** WHO did something, as the chain serves it: a NAME and a ROLE, never an id
 *  (B14 rule 31). Both are nullable — `identity.User.full_name` is `""` while a
 *  user is only invited, and the screen states that absence. */
export interface ChainActor {
  name: string | null;
  role: string | null;
}

/**
 * The correction CASE this bill was pinned into — the only source for the two
 * events the drawn table has that the invoice rows cannot produce: *correction
 * opened* and *approved*.
 *
 * `case_no` is the case's number, taken at Send from the tenant's Correction
 * case series (G3, PO 2026-10-14; it read "null until BR-BIL-014 mints it at
 * approval" until then, and nothing ever minted it — DEF-BIL-10147). It is
 * null only when that series was missing at Send; the screen then says so in
 * words and never prints the case's database id.
 */
export interface ChainCase {
  case_no: string | null;
  status: string;
  reason_codes: string[];
  opened_at: string | null;
  opened_by: ChainActor | null;
  approved_on: string | null;
  approved_by: ChainActor | null;
}

/** A credit note as the chain serves it — a SHORTER row than the detail's
 *  `InvoiceCreditNoteRef`, which also carries `reason` and `issued_at`.
 *  Typed as served rather than widened to match its cousin: a field this route
 *  does not send must not be renderable from this type. */
export interface ChainCreditNote {
  id: string;
  credit_note_no: string | null;
  /** CLAUDE.md hard rule 2 — the decimal STRING and its CHAR(3) partner travel
   *  together. Nothing in this app parses, sums or re-rounds one. */
  amount: string;
  currency: string;
  /**
   * ⚠ **SERVED SINCE 2026-09-14 (`CR-101-BRC03`), SO THE NOTE ABOVE IS NOW
   * HISTORY RATHER THAN A CONSTRAINT.** It read *"a SHORTER row than the
   * detail's `InvoiceCreditNoteRef`… a field this route does not send must not
   * be renderable from this type"*, which was true and is the right instinct;
   * the route sends both now, so the type follows the route rather than the
   * other way round.
   *
   * `reason` is the SERVED CODE (`wrong_read`), not a sentence — turning it
   * into words is the screen's job and is `DEF-2448` / `DEF-BIL-5233`.
   */
  reason: string | null;
  issued_at: string | null;
}

/** `single_correction.chain_of`, field for field. */
export interface InvoiceChain {
  invoice_id: string;
  invoice_no: string | null;
  status: string;
  /** The bill THIS one replaces (`invoices.corrects_invoice_id` read forwards). */
  replaces: ChainInvoiceRef | null;
  /** The bill that replaced this one (the same column read backwards —
   *  `uq_invoices_one_replacement` makes it single-valued). */
  replaced_by: ChainInvoiceRef | null;
  credit_notes: ChainCreditNote[];
  /** This bill's own issue date and total — the first row of the drawn *What
   *  happened* table, which is the bill being issued. */
  issued_at: string | null;
  total: string;
  currency: string;
  /** The correction case, when this bill was pinned into one. */
  case: ChainCase | null;
  /**
   * Σ(credit notes against this bill) + the replacement's total — *"the one
   * figure a caller actually asks for"* (blueprint legend 3).
   *
   * ⚠ **`null`, NEVER `"0.00"`, WHEN NOTHING HAS CORRECTED THIS BILL.** A
   * class-R restatement that nets to zero is a real thing — the server carries
   * a warning for it by name — so "nothing happened" and "it netted to zero"
   * cannot share a value. Derived by the SERVER at the stored scale and rounded
   * nowhere; `MoneyCell` is the display and hard rule 2 rounds there.
   */
  net_effect: string | null;
  /** The bill that counts today. For an uncorrected bill it is this bill. */
  head: ChainInvoiceRef;
  /** BR-BIL-048's gate: whether `head` IS this bill. */
  is_latest: boolean;
  br_ref: string;
  chain_column: string;
}

export const billChainKey = (invoiceId: string) => ["billing", "chain", invoiceId] as const;

export async function getInvoiceChain(
  invoiceId: string,
  client: ApiClient = api,
): Promise<InvoiceChain> {
  return requireData(
    await client.get<InvoiceChain>(`/invoices/${encodeURIComponent(invoiceId)}/chain`),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-053 task 5 (12-governance/11-change-requests.md §CR-053) · source route apps/billing/corrections_api.py::invoice_chain → apps/billing/single_correction.py::chain_of
// generated: 2026-08-30 by the CR-053 billing-surface lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest✔ · the route was called over real HTTP before this file was written (200, is_latest true and false on the two halves of the development database's one correction chain)
// exceptions: E3 `ChainCreditNote` is a SUBSET of the detail's `InvoiceCreditNoteRef` because this route serves fewer fields — typed as served, never widened, so no screen can render a `reason` this endpoint does not send
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
