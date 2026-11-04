// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 task 13 — *"Print bills"* (W4). PO ruling 2026-08-30:
//           *"Im okay with this"*.   Screens: the Print bills screen
// Rules:    BR-NOT-029 (the PDF set plus the manifest and its fourteen
//           columns; clause (c) — no mail standard we do not perform) ·
//           BR-SHL-011 (the export mirrors the list's own filter state) ·
//           BR-TEN-043 (event time is an ARGUMENT the CLIENT supplies) ·
//           B12 r1 §3 (202 + job_id; poll `GET /jobs/{id}`)
// ───────────────────────────────────────────────────────
// The two typed wrappers for `GET`/`POST /billing/print-sets`.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE
// ══════════════════════════════════════════════════════════════════════════
// `endpoints.ts` is over 9,000 lines and every lane appends to it, so on any
// afternoon it holds two or three lanes' half-finished work. `billingOps
// Endpoints.ts` and `bankRecEndpoints.ts` are both here for that reason and
// both say so: one family, one file, one lane's diff.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TWO TYPE DECISIONS THAT MATTER
// ══════════════════════════════════════════════════════════════════════════
//   · **`generated_at` IS SENT BY THE CLIENT AND IS NOT OPTIONAL.** The server
//     reads no clock on any billing path (BR-TEN-043, gate G6), so the moment
//     the archive was produced has to travel with the request — the same shape
//     the release gate's `issued_at` already uses. `new Date().toISOString()`
//     is always offset-bearing, which is what the server requires.
//   · **`unavailable` IS A RENDERED FIELD, NOT A DIAGNOSTIC.** It carries the
//     server's own statement that no mail standard was performed (BR-NOT-029
//     clause (c)) and that two manifest columns have no column behind them
//     (DEF-2847). A screen that dropped it would be claiming, by silence,
//     exactly what the rule forbids claiming out loud.
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1). */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** A gap the SERVER reports about itself. Rendered, never swallowed. */
export interface PrintSetUnavailable {
  code: string;
  detail: string;
}

/**
 * What a print set over these filters WOULD contain. Counts; renders nothing.
 *
 * `bill_count` can legitimately be `0` — a cycle whose bills are all still
 * drafts has none to print — and the screen says so rather than offering a
 * button that produces an empty archive.
 */
export interface PrintSetPreview {
  bill_count: number;
  printable_statuses: string[];
  max_bills: number;
  over_ceiling: boolean;
  estimated_seconds: number;
  /** ── SCREEN 28's FOUR TILES (`DEF-BIL-5354`) ─────────────────────────────
   *  `will_print + held_back === bill_count`, always — the blueprint says so in
   *  its own words: *"A set that printed 404 of 412 without saying so sends a
   *  print shop a short run and tells nobody."* All four come off one server
   *  forecast so nothing on screen can disagree with anything else on it. */
  will_print: number;
  held_back: number;
  /** Non-zero reasons only. The CODE travels and the WORDS are the screen's —
   *  B14 rule 32 keeps an internal code off a clerk's screen. */
  held_reasons: { code: string; bills: number }[];
  /** FALSE = the address question could not be asked, which is NOT *"nothing is
   *  held"*. The screen states it; it never prints a confident zero. */
  held_reasons_complete: boolean;
  /** The page estimate a print shop quotes from — `will_print × pages_per_bill`,
   *  MEASURED (2 a bill, every one of the demo utility's 79 bills, 2026-09-15)
   *  rather than the 6 the wireframe illustrates (B14 rule 37). */
  pages: number;
  pages_per_bill: number;
  /** BR-NOT-029's fourteen, in the ruled order. Drawn so a clerk can see what
   *  the vendor will receive before committing a worker to it. */
  manifest_columns: string[];
  /** Would a worker actually run this? (DEF-2487 — never queue into a void.) */
  background_available: boolean;
  filters: Record<string, string>;
  unavailable: PrintSetUnavailable[];
}

/** The 202 (background) or 201 (ran inline) answer. Both carry a job id, because
 *  the finished archive is fetched by job id from the platform download. */
export interface PrintSetAccepted {
  job_id: string;
  status_url: string;
  background: boolean;
  bill_count: number;
  unavailable: PrintSetUnavailable[];
}

function queryFrom(filters: Record<string, string>): Record<string, string> {
  const query: Record<string, string> = {};
  for (const [name, value] of Object.entries(filters)) {
    if (value !== "") {
      query[`f.${name}`] = value;
    }
  }
  return query;
}

/**
 * One bill in the period, as screen 28's table draws it.
 *
 * ⚠ **`id` AND `account_id` TRAVEL AND ARE RENDERED BY NOTHING** (B14 rule 31).
 * `id` keys the row; what a clerk reads is the BILL NUMBER and the ACCOUNT
 * NUMBER, which are the two things they can quote down a telephone.
 *
 * ⚠ **`will_print` IS A FORECAST, NOT A RESULT.** Three of the eight reasons a
 * bill can be held are knowable without drawing its page — no bill number, a
 * bill number no file name can carry, an incomplete mailing address — and the
 * other five are only knowable by drawing it. The server forecasts the three;
 * `held-back.csv` inside the finished archive remains the record of all eight.
 */
export interface PrintBillRow {
  /** The invoice's id — the bill's address (`billDetailPath`), never shown. */
  id: string;
  invoice_no: string | null;
  account_no: string | null;
  /** Served by the mounted S30 row (`selectors.invoice_row`); typed for record
   *  links (PO 2026-10-19). Builds the account's address only. */
  account_id?: string;
  customer_name: string | null;
  period_start: string | null;
  period_end: string | null;
  total: string | null;
  currency: string;
  will_print: boolean;
  /** A stable reason code — `address_incomplete`, `no_bill_number`,
   *  `unsafe_bill_number` — never rendered raw. Null when the bill will print. */
  hold_reason: string | null;
  /** The measured estimate, or null for a held bill: nothing will draw it, and
   *  a `0` there is a number a print shop could quote against. */
  pages: number | null;
}

/**
 * `GET /billing/print-sets/bills` — the bills in this period, one page.
 *
 * ⚠ **THE PAGE AND THE TOTAL BOTH COME FROM THE DATABASE** (`NFR-3`/`NFR-5`):
 * at the top of the ICP this list is tens of thousands of rows, so nothing here
 * slices an array or counts one.
 *
 * A local query builder rather than `endpoints.ts`'s private `listPage`, for
 * one reason: `hold` is not an `f.<name>` filter — the server reads it as its
 * own parameter, because the bills list's filter vocabulary is `INVOICE_FILTERS`
 * and this verdict is not one of them.
 */
export async function getPrintSetBills(
  args: {
    state: { q: string; page: number; per: number };
    filters: Record<string, string>;
    hold?: "held" | "will_print";
  },
  client: ApiClient = api,
): Promise<{ rows: PrintBillRow[]; total: number }> {
  const query: Record<string, string | number> = {
    page: args.state.page,
    per: args.state.per,
    ...queryFrom(args.filters),
  };
  if (args.state.q !== "") {
    query.q = args.state.q;
  }
  if (args.hold !== undefined) {
    query.hold = args.hold;
  }
  const body = requireData(
    await client.get<{ count: number; results: PrintBillRow[] }>("/billing/print-sets/bills", {
      query,
    }),
  );
  return { rows: body.results, total: body.count };
}

/** `GET /billing/print-sets` — the look-before-you-commit half. */
export async function getPrintSetPreview(
  filters: Record<string, string>,
  client: ApiClient = api,
): Promise<PrintSetPreview> {
  return requireData(
    await client.get<PrintSetPreview>("/billing/print-sets", { query: queryFrom(filters) }),
  );
}

/**
 * `POST /billing/print-sets` — produce the set.
 *
 * `background` asks for a worker; the server answers **202** when one would run
 * it and **201** having run it inline when nothing would (DEF-2487, law 3 — an
 * accepted job nothing will execute is worse than a visible failure). The
 * caller polls in both cases: an inline 201 is already finished, so the first
 * poll is terminal and the code path is one instead of two.
 */
export async function requestPrintSet(
  body: { filters: Record<string, string>; generated_at: string; background: boolean },
  client: ApiClient = api,
): Promise<PrintSetAccepted> {
  return requireData(
    await client.post<PrintSetAccepted>("/billing/print-sets", body),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-053 task 13 (12-governance/11-change-requests.md) + BR-NOT-029
//         (04-docs/05-modules/10-notifications/02-business-rules.md)
// generated: 2026-08-31 by the CR-053 W4 print-bills lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: (1) NO DOWNLOAD WRAPPER. The finished archive is the job record's
//         own `result_link` (`/api/exports/{job_id}/file`), followed as a plain
//         same-origin navigation so the session cookie rides along and the
//         server's `Content-Disposition` names the file — the identical posture
//         `features/exports/ListExportButton.tsx` records, and for the same
//         reason: a fetch-then-blob would need the bytes in the tab's memory.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
