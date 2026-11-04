// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — the New tax or fee form (round 2).
// Contract: CR-165-BRC10 §9 "Round 2 API contract" — names are fixed there and
//           never renamed here.
// ───────────────────────────────────────────────────────
//
// The two reads the New tax or fee form needs that `endpoints.ts` does not
// carry: the form's own option lists and the utility's accounts with each
// authority. Kept in their own file so the back-end lane, the list lane and
// this lane do not all append to the one 22,000-line file at once.
//
// ⚠ **BOTH ARE NEW ROUTES AND MAY NOT BE SERVED YET.** The form reads them with
// `retry: false` and renders an empty list when the read fails, so a missing
// route is an empty dropdown with its own "Add one" door — never a broken step.
import { api } from "./client";
import type { ApiClient } from "./client";
import { readListPage } from "./paginated";

export interface TaxFormOption {
  value: string;
  label: string;
}

/**
 * A boundary row may say it needs a PLACE NAME typed beside it — image 07's
 * *A named place* opens a *Place name* box. `needs_place` is added to the
 * contract by task 4 (CR-165-BRC10 §9); a server that does not send it simply
 * offers no boundary that asks for a place, which is the safe reading.
 */
export interface TaxFormBoundary extends TaxFormOption {
  needs_place: boolean;
}

/** `GET /taxes/form-options` — every list the form renders, from the server. */
export interface TaxFormOptions {
  boundaries: TaxFormBoundary[];
  due_rules: TaxFormOption[];
  bases: TaxFormOption[];
  filing_frequencies: TaxFormOption[];
}

export const EMPTY_TAX_FORM_OPTIONS: TaxFormOptions = {
  boundaries: [],
  due_rules: [],
  bases: [],
  filing_frequencies: [],
};

export const TAX_FORM_OPTIONS_PATH = "/taxes/form-options";
export const AUTHORITY_ACCOUNTS_PATH = "/settings/authority-accounts";

function optionList(raw: unknown): TaxFormOption[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter(
      (row): row is TaxFormOption =>
        typeof row === "object" &&
        row !== null &&
        typeof (row as TaxFormOption).value === "string" &&
        typeof (row as TaxFormOption).label === "string",
    )
    .map((row) => ({ value: row.value, label: row.label }));
}

export async function getTaxFormOptions(client: ApiClient = api): Promise<TaxFormOptions> {
  const response = await client.get<Partial<TaxFormOptions>>(TAX_FORM_OPTIONS_PATH);
  const body = response.data ?? {};
  const boundaries = Array.isArray(body.boundaries) ? (body.boundaries as unknown[]) : [];
  return {
    boundaries: optionList(boundaries).map((row) => ({
      ...row,
      needs_place: boundaries.some(
        (raw) =>
          (raw as { value?: unknown }).value === row.value &&
          (raw as { needs_place?: unknown }).needs_place === true,
      ),
    })),
    due_rules: optionList(body.due_rules),
    bases: optionList(body.bases),
    filing_frequencies: optionList(body.filing_frequencies),
  };
}

/** One account the utility holds with a tax authority (Settings › Accounting). */
export interface AuthorityAccount {
  id: string;
  authority_name: string;
  account_number: string;
  jurisdiction_id: string | null;
  active: boolean;
}

/** The words a picker shows for one account: *TX Comptroller · 32-1180455*. */
export function authorityAccountLabel(row: AuthorityAccount): string {
  return `${row.authority_name} · ${row.account_number}`;
}

const AUTHORITY_ACCOUNTS_PER = 200;

/**
 * `GET /settings/authority-accounts`, every page (NFR-3: the server pages; a
 * picker follows the count rather than stopping at page one). Only ACTIVE
 * accounts are offered — a retired account is not something a new tax files to.
 */
export async function getAuthorityAccounts(client: ApiClient = api): Promise<AuthorityAccount[]> {
  const rows: AuthorityAccount[] = [];
  for (let page = 1; ; page += 1) {
    const answer = await readListPage<AuthorityAccount>(
      AUTHORITY_ACCOUNTS_PATH,
      { page, per: AUTHORITY_ACCOUNTS_PER },
      client,
    );
    rows.push(...answer.rows);
    if (answer.rows.length === 0 || rows.length >= answer.total) {
      return rows.filter((row) => row.active !== false);
    }
  }
}
