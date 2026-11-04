// ── Trace ──────────────────────────────────────────────
// Change:   CR-056 W5 task 25 — **a customers screen: list, search, one
//           person's accounts**. There was no way to browse people at all:
//           `apps/customers/api.py`'s own header recorded it, verbatim — *"no
//           story owns a customer LIST or DETAIL endpoint yet"*.
// Rules:    BR-CUS-054 (the entity and its N:M account link) · BR-CUS-089 (the
//           identity-match tier and its confirmer are STORED) · BR-CUS-092(c)
//           (LAST FOUR ONLY on every read path — never the full identifier in a
//           list response) · B14 rule 31 (no database id is a visible value)
// Tests:    07-frontend/src/features/customers/CustomersListPage.test.tsx
// Impacts:  06-backend `GET /api/{tenant}/customers` and
//           `GET /api/{tenant}/customers/{id}` (live, this change)
// ───────────────────────────────────────────────────────
//
// THE TYPED WRAPPERS FOR THE TWO ROUTES `customers/api.py` MOUNTS FOR PEOPLE.
//
// Its own file, not an appendix to `api/endpoints.ts`, for the reason
// `serviceRequestEndpoints.ts` gives in its header: that file is thousands of
// lines and every lane appends to it. One family, one file, one lane's diff.
//
// ⚠ **`identity` IS `held` + `last4` AND NEVER THE NUMBER.** `BR-CUS-092(c)`:
// *"every read path renders last four only and the full value is never in a
// list response, an export, a log line or an audit `details` blob"*. The type
// below has no field that could carry one, which is deliberate — a number that
// reaches the browser is in devtools, in a proxy log and in the HAR file
// attached to a ticket, whatever the screen chooses to draw.
//
// ⚠ **`held` AND `last4` ARE TWO FACTS AND THE SCREEN NEEDS BOTH.** *No licence
// on file* and *licence ••••4417* read nothing alike, and a single nullable
// string cannot tell them apart.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
// CR-060 C16 — the served-gap shape, TYPE-ONLY. `requireData` is restated in
// this file to avoid coupling to `endpoints.ts`; a `import type` is erased at
// compile time and adds no runtime edge at all, and re-declaring the gap shape
// here would be a second definition of one contract, which is worse.
import type { AccountWriteResult, LedgerUnavailable } from "@/api/endpoints";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated here rather than imported from `endpoints.ts` so this file adds no
 *  coupling to a file three lanes are editing — the `bankRecEndpoints` rule. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One account a person holds, as the person's row lists it. */
export interface CustomerAccountRow {
  /** A machine handle for the row link. B14 rule 31: never a visible value. */
  id: string;
  account_no: string;
  kind: string;
  status_code: string | null;
  status_name: string | null;
  /**
   * BR-CUS-089 — how this link came to be made. `null` on every link an import
   * wrote, and that is the honest state rather than a gap: a legacy reference
   * is a reconciliation key, not identity evidence, so it earns no tier.
   */
  match_tier: string | null;
  match_basis: string | null;
}

/**
 * ⚠ **IDENTITY IS PER KIND, SO SOME OF THESE ARE ALWAYS NULL ON A GIVEN ROW.**
 * A person carries a date of birth, a Social Security number and a driving
 * licence; a COMPANY carries a Tax ID and none of the other three — it has no
 * date of birth to carry. The server sends the whole shape either way so a
 * screen needs no branch to read it, and `kind` on the row says which half to
 * expect.
 */
export interface CustomerIdentity {
  date_of_birth: string | null;
  ssn_held: boolean;
  ssn_last4: string | null;
  driving_licence_held: boolean;
  driving_licence_last4: string | null;
  /** A company's identifier, and the only one it is asked for. */
  tax_id_held: boolean;
  tax_id_last4: string | null;
}

export interface CustomerRow {
  id: string;
  /** The number a person quotes down a phone — this is the visible one. */
  customer_no: string | null;
  display_name: string;
  kind: string;
  /** `CR-161-BRC10` W4 — the utility's own customer answers (Customer edit
   *  pre-fills from them). Optional for a fixture that predates the wave. */
  custom_data?: Record<string, unknown>;
  external_ref: string | null;
  phone: string | null;
  /** ⊕ T1 (`DEF-CUS-6386`) — the primary contact's email on the first account
   *  the person holds now. Optional: a single-row read does not ask for it.
   *  PII (`BR-CUS-045`), so a screen MASKS it (`maskEmail`). */
  email?: string | null;
  /** ⊕ `DEF-CUS-10253` — *Contact by* of the same contact the email is read
   *  from (email/text/phone/letter). Optional for an older fixture. */
  contact_by?: string | null;
  /** ⊕ PO 2026-10-22 — the customer holds a portal login that can sign in, so
   *  *Edit customer* offers *"Also use this as the portal sign-in email"*.
   *  Optional for an older fixture; absent reads as no login. */
  has_portal_login?: boolean;
  identity: CustomerIdentity;
  account_count: number;
  accounts: readonly CustomerAccountRow[];
}

export interface CustomerList {
  results: readonly CustomerRow[];
  count: number;
}

export interface CustomerListQuery {
  q?: string;
  page?: number;
  per?: number;
  sort?: string;
  dir?: string;
  kind?: string;
}

/**
 * `GET /customers` — the list and its search.
 *
 * One box, four legs on the server: the customer number, the legacy reference,
 * the name, and the phone through its blind index.
 *
 * ⚠ **THE PHONE LEG IS AN EQUALITY PROBE, NOT A CONTAINS.** The column is
 * app-layer encrypted with a randomised scheme, so it is searched through a
 * keyed blind index — half a number finds nobody. That is a property of the
 * encryption rather than a bug in the box, and the search placeholder says so
 * in plain words (B14 rule 19).
 */
export async function listCustomers(
  query: CustomerListQuery = {},
  client: ApiClient = api,
): Promise<CustomerList> {
  return requireData(
    await client.get<CustomerList>("/customers", {
      query: {
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        sort: query.sort,
        dir: query.dir,
        "f.kind": query.kind === undefined || query.kind === "" ? undefined : query.kind,
      },
    }),
  );
}

/**
 * One account on a customer statement — **CR-060 C16.**
 *
 * `balance` is `string | null` and the null is load-bearing (DEF-127): when the
 * books cannot be asked, an absence is rendered with its reason and NEVER as
 * 0.00, because a fabricated zero looks exactly like a settled account.
 */
export interface CustomerStatementRow {
  /** A machine handle for the row key. B14 rule 31: `account_no` is the value a
   *  screen prints, and this never reaches a cell. */
  id: string;
  account_no: string;
  kind: string;
  status_code: string | null;
  status_name: string | null;
  balance: string | null;
  /** `BR-CUS-089`'s stored tier. **NULL on every import link**, which is the
   *  honest state rather than a gap: the bulk import matches on the legacy
   *  system's id, a reconciliation key and not identity evidence. */
  match_tier: string | null;
  /** Whether this link is one the total may include (`strong` or `probable`).
   *  Served rather than derived here, so the screen and the read model cannot
   *  disagree about which rows were counted. */
  confident: boolean;
  /** The OTHER holders of this same account, by name. C16: a jointly-held
   *  account is shown IN FULL to each holder — joint and several liability
   *  correctly presented — and this is what explains the duplicate figure. */
  held_with: readonly string[];
}

export interface CustomerStatement {
  basis: string | null;
  currency: string | null;
  customer: { id: string; customer_no: string | null; display_name: string; kind: string };
  account_count: number;
  rows: readonly CustomerStatementRow[];
  /** The sum of the CONFIDENT rows, or `null` when the books could not be
   *  asked at all. Never 0.00 in that case (DEF-127). */
  total: string | null;
  /** What was deliberately left OUT of `total`, as a figure — so the screen can
   *  say so without an adjective. */
  unconfident_total: string | null;
  unconfident_count: number;
  available: boolean;
  unavailable: readonly LedgerUnavailable[];
}

/**
 * `GET /reports/customer-statement?customer={id}` — **CR-060 C16 / T17.**
 *
 * The customer rides as a QUERY parameter rather than a path segment because
 * the URL is a report's and a report is parameterised — and because it lets the
 * screen carry the selection in its own URL, so a statement someone ran is a
 * link they can send.
 */
export async function getCustomerStatement(
  customerId: string,
  client: ApiClient = api,
): Promise<CustomerStatement> {
  return requireData(
    await client.get<CustomerStatement>("/reports/customer-statement", {
      query: { customer: customerId },
    }),
  );
}

/** `GET /customers/{id}` — one person and the accounts linked to them. */
export async function getCustomer(
  customerId: string,
  client: ApiClient = api,
): Promise<CustomerRow> {
  return requireData(await client.get<CustomerRow>(`/customers/${encodeURIComponent(customerId)}`));
}

/**
 * **What `PATCH /customers/{id}` accepts — `BR-CUS-1054`, PO 2026-09-13.**
 *
 * ⚠ **THIS ROUTE WAS READ-ONLY UNTIL TODAY.** A misspelt name, a wrong
 * telephone number and a wrong email could not be corrected anywhere in the
 * product, and the account edit surfaces never reached them because they are
 * not `accounts` columns.
 *
 * ⚠ **EVERY FIELD THE SERVER DOES NOT OWN IS REFUSED BY NAME**, with the rule
 * that owns it in `params` — so a screen never holds a second copy of the
 * refusal list. `customer_no`, `kind`, the mailing address and the portal
 * sign-in are each refused that way.
 *
 * ⚠ **THE PARTIAL IS THE POINT.** An absent key is *leave it alone*; a key with
 * `""` is *clear it*. The two are different acts and the dialog sends only what
 * the clerk actually changed.
 */
/**
 * ── `POST /customers/match` — NEW CONNECTION STEP 1's OWNER LOOKUP ──────────
 * `CR-164-BRC10` item 11, PO ruling Q5 (2026-10-02): an SSN or a driving
 * licence (a company's Tax ID) that is exactly the one on file is a **match**;
 * the name AND the date of birth is a **possible** match; anything less is
 * nothing. A READ carried on POST so an identifier never rides a query string.
 * Only last fours come back (`BR-CUS-092(c)`); `id` is a handle and is never
 * shown (B14 rule 31).
 */
export type CustomerMatchVerdict = "match" | "possible";

export interface CustomerMatchRow {
  id: string;
  customer_no: string | null;
  display_name: string;
  kind: string;
  verdict: CustomerMatchVerdict;
  agreed: readonly string[];
  date_of_birth: string | null;
  phone: string | null;
  ssn_last4: string | null;
  driving_licence_last4: string | null;
  tax_id_last4: string | null;
}

export interface CustomerMatchResult {
  verdict: CustomerMatchVerdict | null;
  candidates: readonly CustomerMatchRow[];
}

export interface CustomerMatchQuery {
  kind: string;
  name?: string;
  date_of_birth?: string;
  ssn?: string;
  driving_licence?: string;
  tax_id?: string;
}

export async function matchCustomer(
  query: CustomerMatchQuery,
  client: ApiClient = api,
): Promise<CustomerMatchResult> {
  return requireData(await client.post<CustomerMatchResult>("/customers/match", query));
}

/**
 * ── `POST /customers/match` with `purpose: "search_customer_id"` ────────────
 * `CR-171-BRC10` P2.23 — the move-in's *Search customer ID* (images 34–37,
 * 40). Contract: CR §9.IDN as amended by lane RULINGS (2.537.0): the verdicts
 * are New Connection's Q5 and nothing else — `found` (an SSN, licence or Tax
 * ID on file), `possible` (a person's name AND date of birth), `new` (nobody
 * our rule shows). A name alone is never on the wire, so nothing here can draw
 * image 35's *"Only the name matches."* (PO ruling 2026-10-05).
 * `result: null` is *nothing to judge yet*, never *new*.
 */
export type CustomerSearchVerdict = "found" | "possible" | "name_phone" | "last_occupant";

/** `CR-181-BRC10` (PO 2026-10-13, *"Q1 C both"*) — the two levels BELOW Q5's,
 *  strongest first. `name_phone`: the name and the phone agree; `last_occupant`:
 *  the name typed is whoever held THIS unit's last account (`unit_id` sent). */
export const CUSTOMER_SEARCH_VERDICTS: readonly CustomerSearchVerdict[] = [
  "found",
  "possible",
  "name_phone",
  "last_occupant",
];

/** `CR-181-BRC10` Q2/Q4 — the customer's closed account on THIS unit, whether
 *  it may be reopened (`reason` when not) and what the books say it owes. */
export interface CustomerReopenOffer {
  account_id: string;
  account_no: string;
  closed_at: string | null;
  eligible: boolean;
  reason: "other_unit" | "not_closed" | "cancelled" | "too_old" | "unit_occupied" | null;
  /** A decimal STRING from the LEDGER (hard rule 2), `null` = unreadable. */
  outstanding: string | null;
  currency: string | null;
  within_years: number;
}

/** `CR-181-BRC10` Q3 — what happens to a reopened account's old balance. */
export type ReopenBalanceChoice = "pay_first" | "carry";

export interface CustomerSearchAccount {
  id: string;
  account_no: string;
  status_code: string;
  status_name: string;
  closed_at: string | null;
  address: {
    line1: string | null;
    unit_label: string | null;
    city: string | null;
    state: string | null;
    postal_code: string | null;
  } | null;
  /** The ledger's signed position, a decimal STRING (hard rule 2). */
  balance: string | null;
  /** `max(balance, 0)` — what is owed on this account. */
  outstanding: string | null;
  confident: boolean;
}

export interface CustomerSearchRow {
  /** A handle for the link, never shown (B14 rule 31). */
  id: string;
  customer_no: string | null;
  display_name: string;
  kind: string;
  verdict: CustomerSearchVerdict;
  agreed: readonly string[];
  /** `CR-181-BRC10` — held the searched unit's last account. */
  last_occupant?: boolean;
  /** `CR-181-BRC10` — only when the search named a unit; never parked. */
  reopen?: CustomerReopenOffer | null;
  /** Lane CF-1 (2026-10-18) — the results table's *Date of birth* column,
   *  `YYYY-MM-DD` (BR-CUS-1020: not an identifier under BR-CUS-092). Optional:
   *  a parked link predates it. */
  date_of_birth?: string | null;
  /** Lane CF-1 — the *Phone* column, LAST FOUR only (BR-CUS-092(c)). */
  phone_last4?: string | null;
  /** `null` only on a link read back from a parked draft — money is never
   *  parked, so a resumed link draws no week-old balances. */
  accounts: {
    count: number;
    rows: readonly CustomerSearchAccount[];
    outstanding_total: string | null;
    currency: string | null;
    available: boolean;
    /** Lane CF-1 — how many of ALL the customer's accounts are open (the
     *  rows are cut at the server's bound, so they cannot be counted here). */
    open_count?: number;
  } | null;
  company: {
    legal_name?: string | null;
    trading_as?: string | null;
    business_type?: string | null;
    registered_in?: string | null;
    po_number?: string | null;
    bills_go_to?: string | null;
    contact_person?: {
      full_name: string | null;
      email: string | null;
      phone: string | null;
      job_title?: string | null;
      contact_by?: string | null;
    } | null;
  } | null;
}

export interface CustomerSearchResult {
  result: CustomerSearchVerdict | "new" | null;
  count: number;
  customers: readonly CustomerSearchRow[];
}

export interface CustomerSearchQuery {
  kind: string;
  name?: string;
  date_of_birth?: string;
  ssn?: string;
  driving_licence?: string;
  phone?: string;
  tax_id?: string;
  /** `CR-181-BRC10` — the move-in's unit, so its last occupant can be found
   *  and a reopen offered. An email is NOT sent: a customer row holds none,
   *  so the server has nothing to compare it with. */
  unit_id?: string;
}

export async function searchCustomerId(
  query: CustomerSearchQuery,
  client: ApiClient = api,
): Promise<CustomerSearchResult> {
  const answer = requireData(
    await client.post<{ search: CustomerSearchResult }>("/customers/match", {
      ...query,
      purpose: "search_customer_id",
    }),
  );
  return answer.search;
}

/**
 * ── THE MOVE-IN WIZARD'S DOCUMENTS — `CR-171-BRC10` P2.25 ──────────────────
 * A file uploaded on the Customer step (image 39) is STAGED: stored now as an
 * account document whose filing card is written on the new account at
 * Complete (`documents: [{card_id, doc_type}]` on the commit). `card_id` is a
 * handle, never shown.
 */
export interface StagedMoveInDocument {
  card_id: string;
  doc_type: string;
  name: string;
  size_bytes: number;
  content_type: string;
}

export async function stageMoveInDocument(
  body: { file: File; docType: string },
  client: ApiClient = api,
): Promise<StagedMoveInDocument> {
  const form = new FormData();
  form.append("file", body.file);
  form.append("doc_type", body.docType);
  form.append("name", body.file.name);
  return requireData(await client.post<StagedMoveInDocument>("/move-ins/documents", form));
}

/** The staged file's content route — opened through `openDocumentContent`,
 *  the same route shape account and request documents use. */
export function stagedMoveInDocumentPath(cardId: string): string {
  return `/move-ins/documents/${encodeURIComponent(cardId)}/content`;
}

/** `CR-171-BRC10` P2.24 — a co-owner's photo ID, filed on the account once it
 *  exists (`POST /accounts/{id}/co-owners/{coOwnerId}/photo-id`). */
export async function uploadCoOwnerPhotoId(
  accountId: string,
  coOwnerId: string,
  file: File,
  client: ApiClient = api,
): Promise<{ co_owner_id: string; photo_id: boolean; document_id: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("name", file.name);
  return requireData(
    await client.post<{ co_owner_id: string; photo_id: boolean; document_id: string }>(
      `/accounts/${encodeURIComponent(accountId)}/co-owners/${encodeURIComponent(coOwnerId)}/photo-id`,
      form,
    ),
  );
}

/** The doc types the utility ticked as required for a move-in (BR-CUS-095). */
export async function getMoveInRequiredDocuments(
  client: ApiClient = api,
): Promise<readonly string[]> {
  return requireData(
    await client.get<{ required: string[] }>("/move-ins/documents/required"),
  ).required;
}

export interface CustomerEdit {
  display_name?: string;
  external_ref?: string;
  /** A PERSON's only. A company has none and the server refuses it by name. */
  date_of_birth?: string;
  /** The customer's own encrypted column; its blind index moves with it, so a
   *  corrected number is findable by the search box straight away. */
  phone?: string;
  ssn?: string;
  driving_licence?: string;
  /** A COMPANY's only. */
  tax_id?: string;
  /** `contacts.email`, on EVERY account this customer holds (BR-CUS-054). */
  email?: string;
  /** ⊕ `DEF-CUS-10253` — `contacts.contact_by`, on every account, like the email. */
  contact_by?: string;
  /** ⊕ PO 2026-10-22 — the tick box: `true` moves the portal sign-in to `email`
   *  (sent with it), mails the old address and sends a reset link. */
  portal_sign_in?: boolean;
  /** `CR-161-BRC10` W4 — the utility's own customer answers that changed (a
   *  cleared one is `null`), merged into the stored ones (`CUSTOMER_EDIT`). */
  custom_data?: Record<string, unknown>;
}

/**
 * The answer: the customer as `GET` serves them, plus how many accounts an
 * email correction reached.
 *
 * ⚠ **`accounts_updated` IS A SENTENCE A CLERK CAN ACT ON.** *Four accounts
 * updated* tells a landlord's clerk the correction went everywhere; *saved*
 * does not, and `contacts` hangs off the account so the difference is real.
 */
export interface CustomerEditResult extends CustomerRow {
  accounts_updated: number;
  account_ids: readonly string[];
  /** ⊕ PO 2026-10-22 — the login moved (false when unticked or already equal). */
  portal_sign_in_moved?: boolean;
}

export async function updateCustomer(
  customerId: string,
  changes: CustomerEdit,
  client: ApiClient = api,
): Promise<CustomerEditResult> {
  return requireData(
    await client.patch<CustomerEditResult>(
      `/customers/${encodeURIComponent(customerId)}`,
      changes,
    ),
  );
}
// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-056 W5 task 25 (12-governance/11-change-requests.md §CR-056)
//         + BR-CUS-054 + BR-CUS-089 + BR-CUS-092(c) + B14 rule 31
//         ⚠ NO `US-XXX-###@<hex>` STAMP AND NONE IS INVENTED — `CR-056` allocates no story ids, and minting one to satisfy `G01`'s regex would put a citation in the tree that resolves to nothing. Same posture as `apps/customers/close_out.py`, which writes its DEF id instead
// generated: 2026-08-31 by the CR-056 W2/W3/W5 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc --noEmit clean · eslint --max-warnings 0 clean · vitest CustomersListPage.test.tsx 9/9 · src/features/customers 627 passed · routeBUtilities.test.ts 10/10 · G31 PASS (0 undeclared classes) · G13 PASS
// exceptions: the types are read off `apps/customers/selectors.customer_row` field for field, and a field the server does not send is not typed here · `identity` carries `held` + `last4` and has NO field that COULD hold a full identifier (BR-CUS-092(c)); the two are separate because *nothing on file* and *•••• 6789* read nothing alike · `requireData` is restated rather than imported from `api/endpoints.ts`, the `bankRecEndpoints` rule: that file is thousands of lines and every lane appends to it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/**
 * `PATCH /accounts/{id}/co-applicant` — **the account's SECOND person**, the
 * account page's pencil (T4, PO 2026-09-23: *"Store a second person on the
 * account (name, email, phone), shown on the account page"*; `DEF-CUS-6391`).
 * An absent key keeps what is stored; `full_name: ""` removes the person.
 * Answers the whole account, as the other account-group doors do.
 */
export async function updateAccountCoApplicant(
  accountId: string,
  changes: Record<string, unknown>,
  client: ApiClient = api,
): Promise<AccountWriteResult> {
  const response = await client.request<AccountWriteResult>(
    `/accounts/${encodeURIComponent(accountId)}/co-applicant`,
    { method: "PATCH", body: changes },
  );
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}
