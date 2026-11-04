// ── Trace ──────────────────────────────────────────────
// Change:  TRF-02 transfer question T1, PO 2026-09-23 (`DEF-CUS-6386`) —
//          *"search custoemr id for buyer hence on step 2"* and *"we already
//          ahve this functionality component in other functionalities"*. The
//          finder lived INLINE in `NewConnectOwnerStep.tsx`, importable by
//          nothing (B14 rule 43); it is extracted here and BOTH screens mount it.
// Rules:   B14 rule 43 (a piece of UI is a component) · rule 31 (the customer
//          NUMBER, never an id) · rule 33 (labels ≤ 3 words, facts ≤ 6) ·
//          `BR-CUS-045` (contact PII is MASKED on screen) · `BR-CUS-1024` (a
//          phone never attaches — the search does not invite one) ·
//          `BR-CUS-019` (the match is advisory: the CLERK links)
// Decision: 12-governance/02-decision-log.md, 2026-09-23 — *"RULED: THE BUYER
//          SEARCH'S SEVERAL-MATCHES TABLE"* (PO: *"this si correct"*)
// Tests:   07-frontend/src/features/customers/CustomerFinder.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";

import { listCustomers } from "./customerEndpoints";
import type { CustomerRow } from "./customerEndpoints";

type Translator = (key: string, options?: Record<string, unknown>) => string;

/** `IS-3`, the same minimum every other search in this app uses: an empty box
 *  must not pull the tenant's whole customer register down the wire. */
export const MIN_CUSTOMER_SEARCH_CHARS = 2;

/**
 * What the customer search ANSWERED for the term it was asked.
 *
 * ⚠ **`searched` IS WHY THIS IS THREE FIELDS AND NOT A LIST.** An empty
 * `matches` with `searched: true` means *there is no such customer* — the
 * answer that lets a clerk go on and create one. With `searched: false` it
 * means *nobody has asked yet*. `DEF-732` is what it costs to state one of
 * those over the other.
 */
export interface CustomerSearchState {
  matches: readonly CustomerRow[];
  searched: boolean;
  /** The search itself could not be run. A PLATFORM fact, never a term fact. */
  failed: boolean;
}

export const CUSTOMER_SEARCH_IDLE: CustomerSearchState = {
  matches: [],
  searched: false,
  failed: false,
};

/**
 * The published customer search, as a hook — `GET /customers?q=` (number,
 * legacy reference, name, and a phone through its blind index). **No new
 * endpoint.** The host decides WHEN it asks: New Connect and the transfer both
 * pass the term the clerk SUBMITTED with the *Search customer* button, so a
 * half-typed name never flashes a table of strangers.
 */
export function useCustomerSearch(term: string, client: ApiClient): CustomerSearchState {
  const trimmed = term.trim();
  const enabled = trimmed.length >= MIN_CUSTOMER_SEARCH_CHARS;
  const query = useQuery({
    queryKey: ["customer-finder", trimmed],
    queryFn: () => listCustomers({ q: trimmed, per: 20 }, client),
    enabled,
    retry: false,
  });
  if (!enabled) return CUSTOMER_SEARCH_IDLE;
  return {
    matches: query.data?.results ?? [],
    searched: query.isSuccess,
    failed: query.isError,
  };
}

/** ⚠ **THE NUMBER, NEVER THE ID** (B14 rule 31). `customer_no` is nullable, so
 *  the label falls back to the name and never renders empty. */
export function customerFinderLabel(row: CustomerRow, t: Translator): string {
  const number = row.customer_no;
  if (number === null || number.trim() === "") {
    return row.display_name.trim() === ""
      ? t("customers.newConnect.step1.finder.unnamed", { defaultValue: "Customer with no number" })
      : row.display_name;
  }
  return `${number} — ${row.display_name}`;
}

/**
 * `m•••@gmail.com` — `BR-CUS-045` makes an email PII and display masking the
 * client's half of the rule. The first character and the domain stay, which is
 * enough for a clerk to ask *"is that your gmail address?"* and no more.
 */
export function maskEmail(email: string | null | undefined): string | null {
  const value = (email ?? "").trim();
  const at = value.indexOf("@");
  if (value === "" || at < 1) return value === "" ? null : "•••";
  return `${value.slice(0, 1)}•••${value.slice(at)}`;
}

/** `•••-4471` — the last four digits, which is what a clerk reads back. */
export function maskPhone(phone: string | null | undefined): string | null {
  const digits = (phone ?? "").replace(/\D/g, "");
  if (digits === "") return null;
  return `•••-${digits.slice(-4)}`;
}

// ⛔ **THE `CustomerFinder` COMPONENT IS DELETED (G40, lane CF-2, 2026-10-18).**
// Its last host, the transfer buyer step, now asks with *Search customer ID*
// and CF-1's results table (`CustomerMatchPanel`, image `07-transfer.png`).
// The search hook and the label/mask helpers above stay: New Connect's owner
// step re-exports and uses them.
