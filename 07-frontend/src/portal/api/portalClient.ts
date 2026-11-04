// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-016 · 017 · 018 · 019 · 020 (EP-CWP-05) · 023 · 024
//           (EP-CWP-06) — ⚠ **THIS READ `(EP-CWP-03/04)` UNTIL 2026-09-05
//           (`DEF-CWP-3862`): those are *report a problem* and *starting
//           service*, neither of which owns any of these stories.** —
//           the signed-in customer's edge. Screens: CWP-015 … CWP-019 · CWP-022
// Rules:    BR-CWP-011 (the SIGNED-IN surface calls the PORTAL edge and nothing
//           else — this file is the whole of what it may call, and it is a
//           different file from guestClient.ts for the same reason the backend
//           has two) · BR-CWP-032 (a find-account response carries no name, no
//           balance and no address — the TYPE below says so, so a screen cannot
//           read a field the server does not send) · BR-CWP-038 (both reset
//           answers are the same shape) · BR-CWP-047 (a balance is never
//           cached — nothing here is put in a query cache with a stale time)
// Tests:    src/portal/signin/Enrol.test.tsx · PortalShell.test.tsx
// Impacts:  06-backend/apps/portal/api.py (the shape these types are written
//           against)
// ───────────────────────────────────────────────────────
// Hand-written against `06-backend/apps/portal/api.py`.

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
/**
 * ⚠ **THE TIP'S TYPE IS THE WIRE'S, AND IT WAS NOT — `DEF-CWP-3998`.** Both
 * `PortalHome.tip` and `PortalUsage.tip` were declared `{ title?: string;
 * body?: string }`, and the server has never sent either key:
 * `published_content.tip_for_screen` returns `{"text": …, "target_screen": …}`
 * and both selectors hand it straight through. So `data.tip.body ??
 * data.tip.title` was `undefined ?? undefined` on every live tip, and a clerk
 * who switched one on published an EMPTY BOX to every customer.
 *
 * ⚠ **IT PASSED EVERYTHING, AND THE REASON IS THE INTERESTING PART.** Both
 * keys were declared OPTIONAL, so `tsc` had nothing to object to; and each
 * screen's own test built the fixture from the same wrong type, so the tests
 * asserted the invented shape rather than the served one. A fixture written
 * from the client type can only ever confirm the client type.
 *
 * One type now, imported from where the endpoint that answers it is declared.
 */
import type { PortalHelpAnswer, PortalTip } from "./guestClient";

// ── DEF-CWP-5747 — THE LIST WINDOW EVERY PAGED PORTAL READ CARRIES ─────────
//
// ⚠ **ONE SHAPE FOR FIVE LISTS, BECAUSE THE GRAMMAR IS ONE GRAMMAR.** The
// portal edge parses `q / sort / dir / page / per / f.<name>` with
// `core.pagination.parse_list_params` — the same parser every staff list in the
// product uses — and `BR-SHL-011` is what makes an unrecognised value fall back
// or clamp rather than 4xx. Five wrappers spelling their own query string would
// be five chances to send `?search=` at a server that reads `?q=`.
//
// ⚠ **AND THE SEARCH AND THE SORT TRAVEL WITH THE PAGE OR NOT AT ALL**
// (`DEF-CWP-5747`). The defect these types exist for is not that the portal
// fetched too much: it is that fixing THAT alone would have left the browser
// searching one page of N. A request type that can carry a page and cannot
// carry a needle is the half-fix with a compiler behind it.

import type { PageSize } from "@/components/tableTypes";

/** What a paged portal list asks for. Every field is optional: omitted, the
 *  server serves page 1 of its own default order, which is what the five
 *  screens' first render asks for. */
export interface PortalListRequest {
  page?: number;
  per?: PageSize;
  /** The search box's text, as typed. Trimmed and lower-cased by the server. */
  q?: string;
  /** A column key the endpoint declares. Anything else falls back (`BR-SHL-011`). */
  sort?: string | null;
  dir?: "asc" | "desc";
  /** The chips, as `f.<name>` — `{ group: "bill" }` sends `?f.group=bill`. The
   *  key is the FILTER's name and never a column of a table (B14 rule 31). */
  filters?: Record<string, string | null | undefined>;
}

/** What a paged portal list answers beside its rows. ⚠ **`count` IS THE WHOLE
 *  MATCHING SET** — the figure the footer prints and the one a screen may never
 *  compute from `rows.length` (`DEF-NOT-5746`). */
export interface PortalListWindow {
  count: number;
  page: number;
  per: number;
}

/** `PortalListRequest` as the query parameters the edge reads. Exported so a
 *  test can assert the REQUEST rather than the row count — which is the only
 *  assertion that can tell server paging from client paging. */
export function listQuery(request: PortalListRequest = {}): Record<string, string | number> {
  const query: Record<string, string | number> = {};
  if (request.page !== undefined) query.page = request.page;
  if (request.per !== undefined) query.per = request.per;
  // An empty needle is NOT sent: `?q=` and no `q` mean the same thing to the
  // server, and sending the empty one makes every idle screen's URL carry it.
  if (request.q !== undefined && request.q.trim() !== "") query.q = request.q.trim();
  if (request.sort !== undefined && request.sort !== null) query.sort = request.sort;
  if (request.dir !== undefined) query.dir = request.dir;
  for (const [name, value] of Object.entries(request.filters ?? {})) {
    // `all` is the chip this component supplies for *no narrowing*, so it is
    // an ABSENCE on the wire rather than a filter value the server has to know.
    if (value !== undefined && value !== null && value !== "" && value !== "all") {
      query[`f.${name}`] = value;
    }
  }
  return query;
}


function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("empty 200 body where the contract promises one (portal edge)");
  }
  return response.data;
}

// ══ Enrolment ══════════════════════════════════════════════════════════════

/**
 * `POST enrol/find-account`.
 *
 * ⚠ **READ THE FIELDS AS THE RULE** (`BR-CWP-032`). There is no `name`, no
 * `balance`, no `address` and no `account_id` on this type, because there is
 * none on the wire: between *matched* and *proven* the portal knows which
 * account is meant and has told the visitor **nothing**. `sent_to` is the
 * masked contact — `••• ••• 4218` — which is the least that lets a person know
 * which phone to pick up, and `account_ref` is the CODE ROW's id, a capability
 * that dies with the code.
 */
export interface FindAccountResult {
  matched: boolean;
  /** `not_matched` · `locked` · `use_reset` · `no_contact_on_file`. A KEY, so
   *  eleven catalogues each write the sentence in their own language. */
  reason?: string;
  account_ref?: string | null;
  sent_to?: string;
  channel?: string;
  expires_in_minutes?: number;
}

export async function findAccount(
  body: { account_number: string; postcode: string; last_name: string },
  client: ApiClient = api,
): Promise<FindAccountResult> {
  return requireData(await client.post<FindAccountResult>("/portal/enrol/find-account", body));
}

/** `ok` · `wrong` · `expired` · `locked` — four answers, and `expired` is its
 *  own (`BR-CWP-035`: a person who waited eleven minutes is offered a resend). */
export interface VerifyCodeResult {
  result: string;
}

export async function verifyCode(
  body: { account_ref: string; code: string },
  client: ApiClient = api,
): Promise<VerifyCodeResult> {
  return requireData(await client.post<VerifyCodeResult>("/portal/enrol/verify-code", body));
}

/**
 * `POST enrol/consequences` — what `CWP-018`'s rail states (`BR-CWP-039`).
 *
 * ⚠ **THE FIRST SCREEN IN THE FLOW THAT MAY SHOW A BALANCE**, and it may only
 * because the code has already been consumed. `services` are CODES and
 * `cannot` are KEYS; the screen turns each into a word in the reader's own
 * language, because a server that returned *"Water"* would ship English to
 * eleven catalogues (B14 rule 35).
 */
export interface EnrolConsequences {
  account_no: string;
  service_address: string | null;
  services: string[];
  balance: string;
  currency: string | null;
  policy_min_length: number;
  cannot: string[];
}

export async function getConsequences(
  body: { account_ref: string },
  client: ApiClient = api,
): Promise<EnrolConsequences> {
  return requireData(await client.post<EnrolConsequences>("/portal/enrol/consequences", body));
}

export interface SetPasswordResult {
  ok: boolean;
  failures?: string[];
  min_length?: number;
}

export async function setPassword(
  body: { account_ref: string; email: string; password: string; otp_channel: string },
  client: ApiClient = api,
): Promise<SetPasswordResult> {
  return requireData(await client.post<SetPasswordResult>("/portal/enrol/set-password", body));
}

// ══ Sign in, sign out, reset ═══════════════════════════════════════════════

export async function signIn(
  body: { email: string; password: string },
  client: ApiClient = api,
): Promise<{ ok: boolean }> {
  return requireData(await client.post<{ ok: boolean }>("/portal/auth/sign-in", body));
}

export async function signOut(client: ApiClient = api): Promise<{ ok: boolean }> {
  return requireData(await client.post<{ ok: boolean }>("/portal/auth/sign-out", {}));
}

/**
 * `POST auth/forgot-password`.
 *
 * ⚠ **ONE TYPE, ONE SHAPE, BOTH WAYS** (`BR-CWP-038`). There is no branch here
 * and there must never be one: the server returns the same object for an
 * address with a login and one without, and a client that told the two apart
 * would put the disclosure back that the server took out.
 */
export interface ResetAsked {
  ok: boolean;
  reason: string;
}

export async function forgotPassword(
  body: { email: string },
  client: ApiClient = api,
): Promise<ResetAsked> {
  return requireData(await client.post<ResetAsked>("/portal/auth/forgot-password", body));
}

/**
 * `POST auth/reset-password` — spend the emailed link on a new password
 * (`DEF-CWP-10381`). `ref` and `token` are the two halves the email's link
 * carries. A refusal THROWS an `ApiError` whose `messageKey` is
 * `portal.reset.link.<wrong|expired|locked>` or `portal.reset.policy` (with
 * `params.failures` / `params.min_length`) — the screen reads those keys.
 */
export async function resetPassword(
  body: { ref: string; token: string; password: string },
  client: ApiClient = api,
): Promise<{ ok: boolean }> {
  return requireData(await client.post<{ ok: boolean }>("/portal/auth/reset-password", body));
}

// ══ Session, the account set, and the balance ══════════════════════════════

/**
 * One entry of the FLAT account set (`BR-CWP-013`).
 *
 * ⚠ **THERE IS NO `children` FIELD AND THERE MUST NEVER BE.** A master account
 * over common areas is one more entry, not a parent; `is_master` is served so
 * the row can read *Billed to you as owner*, which is a BILLING fact and not a
 * permission (`BR-CWP-014`). `label` is the service address — B14 rule 31: the
 * `id` is never the visible value of a field.
 */
export interface PortalAccount {
  id: string;
  account_no: string;
  label: string;
  permissions: string[];
  source: string;
  is_master: boolean;
}

export interface PortalSession {
  customer: { display_name: string | null };
  accounts: PortalAccount[];
  /** The SERVER's answer to *is the switcher a control or a label* — one entry
   *  means a label (`09-component-inventory.md` §1). Deciding it per screen is
   *  how two screens disagree. */
  account_count: number;
  /**
   * THIS CUSTOMER'S OWN LANGUAGE — `accounts.preferred_language`, or `null`
   * when they have stated none **or when the login's accounts disagree**
   * (`DEF-CWP-4440`, `BR-CWP-105`; the server folds it in
   * `selectors.account_language`, the same function that opens the picker on
   * `CWP-024`, so the language a customer chooses and the one they read cannot
   * come from two rules).
   *
   * **PO ruling 2026-09-07:** *"a signed-in customer will get their account's
   * own preferred language - Signed customer should get their own
   * references."* So this BEATS the tenant's default on `PortalFront.regional`
   * — it is the customer's own statement and the utility's is not.
   */
  language: string | null;
}

export async function getSession(client: ApiClient = api): Promise<PortalSession> {
  return requireData(await client.get<PortalSession>("/portal/session"));
}

/**
 * A named gap in a served figure — **the CODE, and nothing else** (`DEF-CWP-3926`,
 * and the wire half of it filed 2026-09-05).
 *
 * ⚠ **`detail` USED TO BE ON THIS TYPE AND ITS REMOVAL IS THE POINT.** The
 * server still sends it, and it is a sentence addressed to a DEVELOPER: what a
 * customer's `GET /portal/home` carries today is
 *
 *     apps.billing.selectors.issued_invoices_for_account is not published, so
 *     no bill states its usage+base / taxes / tenant-defined / fees balances …
 *     (OQ-128, `minimum_adjustment` belongs to no named class) … (BR-PAY-038,
 *     PO 2026-08-11)
 *
 * — a module path, three rule ids and an open question, in a payload anyone can
 * read in devtools. `NamedGaps` already refuses to render it and draws a
 * catalogue sentence keyed by `code` instead, which is correct and complete on
 * the SCREEN. **What was left was the invitation.** A field typed
 * `detail: string` is a standing offer to the next screen that needs words in a
 * hurry, and taking that offer is exactly how `DEF-CWP-3926` happened: two
 * screens wrote `t(key, { defaultValue: problem.detail })` and printed the
 * paragraph above onto `CWP-022`, a customer's home page.
 *
 * Declaring it off the type makes that a COMPILE ERROR rather than a review
 * somebody has to remember. `payNowClient.ts` — a later wave — already types
 * its problems this way; this is the older half catching up.
 *
 * ⚠ **THE SERVER STILL SERIALISES IT, AND THAT IS A FILED DEFECT RATHER THAN
 * A THING WE DECIDED TO LIVE WITH.** `apps/portal/api.py::_webhook_view`
 * already rules on it in this module's own words — *"`detail` is a sentence
 * addressed to a DEVELOPER … the CODE travels and the sentence does not"* —
 * and drops it there. Twelve producers across five files still send it on the
 * signed-in reads; that is an edge change of its own, and half a scrub reads
 * as a finished one, so it is written up instead of started here.
 */
export interface PortalProblem {
  code: string;
  /** A `BR-`/`OQ-` ref for a SUPPORT engineer. Never rendered (B14 rule 32). */
  oq_ref?: string;
}

/** One account's money. Four decimals on the wire, two on the screen (hard
 *  rule 2) — the formatting is the screen's and the precision is the store's. */
export interface AccountBalance {
  account_id: string;
  /** What the letter, the next bill and the collection ladder all state. */
  owing: string;
  /** What the bills alone add up to, before any held credit came off. */
  bills_open: string;
  credit_held: string;
  currency: string | null;
  due_on: string | null;
  open_bill_count: number;
  /** ⚠ **`detail` IS DELIBERATELY NOT ON THIS TYPE** — see `PortalProblem`. */
  problems: PortalProblem[];
}

export interface BalanceSummary {
  as_of: string | null;
  accounts: AccountBalance[];
  account_count: number;
  /** ⚠ A SUM FOR INFORMATION, NEVER AN AMOUNT PAYABLE (`BR-CWP-015`). Nothing
   *  on this type can be paid; there is no merged invoice and never will be. */
  total_owing: string | null;
  currency: string | null;
  /** ⚠ **`detail` IS DELIBERATELY NOT ON THIS TYPE** — see `PortalProblem`. */
  problems: PortalProblem[];
}

/**
 * ⚠ **NEVER CACHED** (`BR-CWP-047`). These two are plain calls and are
 * deliberately NOT wrapped in a query with a stale time: *a credit that was
 * real on Tuesday can be spent by Thursday*. The server says `no-store` as
 * well; both halves, because either alone is one refactor from being lost.
 */
export async function getBalanceSummary(client: ApiClient = api): Promise<BalanceSummary> {
  return requireData(await client.get<BalanceSummary>("/portal/balance/summary"));
}

export async function getAccountBalance(
  accountId: string,
  client: ApiClient = api,
): Promise<AccountBalance> {
  return requireData(await client.get<AccountBalance>(`/portal/accounts/${accountId}/balance`));
}

// ── CR-068 wave F · CWP-023 — all my accounts (US-CWP-026) ─────────────────

/** One row of `CWP-023`. ⚠ **`state` IS A STATE, NOT A SENTENCE** — the server
 *  sends `clear · due · overdue` and a day count, and the screen writes the
 *  words in the reader's language (B14 rule 35). A server that sent
 *  *"19 days overdue"* would ship English to eleven catalogues. */
export interface MyAccountRow {
  id: string;
  /** The customer's own reference — a human number, never a database id
   *  (B14 rule 31). */
  account_no: string;
  /** Walked to `premises` (hard rule 8); `null` when the account has none. */
  service_address: string | null;
  /** ⚠ The NAME is the utility's own word for the service, not ours. */
  services: { code: string; name: string }[];
  owing: string | null;
  currency: string | null;
  due_on: string | null;
  state: "clear" | "due" | "overdue";
  days_overdue: number | null;
  /** `BR-CWP-014` — a BILLING fact, never a permission. */
  billed_to: "owner" | "tenant";
  is_master: boolean;
}

export interface MyAccounts extends PortalListWindow {
  as_of: string;
  accounts: MyAccountRow[];
  account_count: number;
  /** ⚠ INFORMATION, NEVER AN AMOUNT PAYABLE (`BR-CWP-015`). */
  total_owing: string | null;
  currency: string | null;
  /** False for a householder: a total of one number is noise, and worse — a
   *  `$142.18` row above a `$142.18` total reads as `$284.36` owed. */
  show_total: boolean;
  /** ⚠ **`detail` IS DELIBERATELY NOT ON THIS TYPE** — see `PortalProblem`. */
  problems: PortalProblem[];
}

/**
 * ⚠ **NEVER CACHED** (`BR-CWP-047`) — four live balances, and a screen that
 * showed Tuesday's figures on Thursday is what the rule exists for.
 *
 * ⚠ **ONE PAGE SINCE `DEF-CWP-5747`, AND `total_owing` IS STILL THE WHOLE
 * SET'S** (`BR-CWP-015`): a total of the PAGE would be a different number on
 * page 2, and a customer could reasonably believe it and try to pay it.
 * `account_count` is the whole set's too, which is what tells the screen
 * whether to draw a total at all and whether to draw the *Owing* chip.
 */
export async function getMyAccounts(
  request: PortalListRequest = {},
  client: ApiClient = api,
): Promise<MyAccounts> {
  return requireData(
    await client.get<MyAccounts>("/portal/my-accounts", { query: listQuery(request) }),
  );
}

// ── CR-068 wave F · CWP-065 — your account (US-CWP-031) ────────────────────

/** The facts about an account that are not on a bill.
 *
 *  ⚠ **THERE IS NO `credit_tier`, `match_tier` OR `match_basis` ON THIS TYPE
 *  AND THERE MUST NEVER BE** (`BR-CWP-052`). A credit tier is the utility's own
 *  assessment of the person reading the screen; the server does not select it
 *  and this type does not name it. */
export interface AccountSummary {
  account_id: string;
  opened_on: string | null;
  /** ⚠ `null` when no deposit is held — a panel that is ABSENT, never `$0.00`,
   *  because a zero reads as *we took nothing from you* rather than *there is
   *  nothing here* (`US-CWP-031` TC-8). */
  deposit: {
    held: string;
    taken_on: string | null;
    /** ⚠ `null` is a real answer and must not be shown as zero: the signed
     *  accrual engine answers null when it cannot compute, and the settlement
     *  that pays this money out fails closed on the same value. */
    interest: string | null;
    currency: string | null;
    returns_at_closing: boolean;
    is_money_off_a_bill: boolean;
  } | null;
  /** `name` is the utility's OWN word for the service. */
  services: { code: string; name: string; since: string | null }[];
  billing: {
    current: { name: string; since: string | null } | null;
    before: { name: string; from: string | null; to: string | null }[];
  };
  tax_exemption: {
    until: string | null;
    /** WHETHER one is held — never the utility's own reference number. */
    certificate_on_file: boolean;
    reminder_days_before: number;
    /** `DEF-CWP-9795` — one row per LIVE per-tax certificate: the tax it
     *  removes and when it runs out. Empty for the blanket exemption, whose
     *  expiry is `until`. Never the certificate number. */
    taxes?: { tax: string; until: string | null }[];
  } | null;
}

/** ⚠ **NEVER CACHED** — a held deposit and its accrued interest are money in
 *  motion at closing time. */
export async function getAccountSummary(
  accountId: string,
  client: ApiClient = api,
): Promise<AccountSummary> {
  return requireData(await client.get<AccountSummary>(`/portal/accounts/${accountId}/summary`));
}

// ── CR-068 wave F · CWP-022 — the whole home page in one read (US-CWP-025) ──

/** One quantity a bill charged for, with the unit it is in (hard rule 3). */
export interface HomeBillUsage {
  /** `BR-MET-144` — two decimals, trailing zeros trimmed, composed by the
   *  server. Never the stored `NUMERIC(18,6)` (`DEF-CWP-3770`). */
  quantity_display: string;
  unit: string;
}

export interface HomeBill {
  /** The number on the paper — never a database id (B14 rule 31). */
  number: string | null;
  issued_on: string | null;
  due_on: string | null;
  total: string;
  currency: string | null;
  period_start: string | null;
  period_end: string | null;
  /** ⚠ **PRESENT ONLY ON `recent_bills`, ABSENT ON `last_bill`**
   *  (`DEF-CWP-3965`). `CWP-022`'s table is *Bill / Period / Usage / Amount /
   *  Status*, and the two right-hand columns cost a balance read and the
   *  bill's own lines; the lead tile needs neither, so the server does not
   *  compute them for it. */
  owing?: string;
  /** `paid · part_paid · due · overdue · corrected` — a STATE, not a sentence;
   *  the catalogue writes the words, exactly as on `CWP-027` (B14 rule 35). */
  state?: string;
  /** One entry per UNIT. Two services in two units are two figures and never a
   *  sum (hard rule 3); `[]` is ordinary — a base-only bill charges for no
   *  measured quantity at all. */
  usage?: HomeBillUsage[];
}

/** One row of `CWP-022`'s **YOUR SERVICE** panel.
 *
 *  ⚠ **`varies` IS SERVED RATHER THAN RESOLVED**, the posture `PortalMyDetails`
 *  already takes: a landlord's three accounts sit at three addresses and share
 *  one plan, so the address row says *varies by account* while the plan row
 *  states the plan. Showing the first account's address would tell a landlord
 *  their service is at one building. */
export interface HomeServiceFact {
  value: string | boolean | null;
  varies: boolean;
}

export interface HomeService {
  address: HomeServiceFact;
  plan: HomeServiceFact;
  /** One of the eight business words — `Monthly`, `Quarterly`… The catalogue
   *  writes it (B14 rule 35); the wire carries the word. */
  billed: HomeServiceFact;
  /** ⚠ **`true` MEANS EMAIL WAS ADDED, NEVER THAT PAPER STOPPED**
   *  (`BR-BIL-036`: print is the FLOOR and *a paperless customer still receives
   *  the document*). The screen's two words say so. */
  paperless: HomeServiceFact;
}

/** ⚠ **EVERY USAGE ROW CARRIES ITS UNIT** (hard rule 3). A row with a quantity
 *  and no unit never reaches this type — the server drops it rather than let a
 *  bare `4,820` onto a screen.
 *
 *  ⚠ **`period_end` BECAME `month`, AND `quantity_display` ARRIVED — PO ruling
 *  2026-09-04 (`DEF-CWP-3770`).** The tile used to sum bill LINES, whose key was
 *  an invoice period end; it reads `metering`'s stored MONTHS now, whose key is
 *  the month itself. `quantity` is the stored `NUMERIC(18,6)` figure and a
 *  screen printing it reads `4820.000000 gal` — `quantity_display` is
 *  `BR-MET-144`'s two-decimals-trailing-zeros-trimmed, composed once by the
 *  server so two screens cannot disagree. */
export interface HomeUsage {
  month: string;
  service: string;
  unit: string;
  quantity: string;
  quantity_display: string | null;
  /** `BR-MET-106` — part of the month was estimated, and the customer may know. */
  estimated: boolean;
}

/** One fact folded across the login's accounts — the value, or *they disagree*.
 *  The same shape `HomeServiceFact` already has, and deliberately so: the
 *  server folds every per-account fact through one function. */
export type HomeFact = HomeServiceFact;

/** `CWP-022`'s account card — *am I in the right place, and is this me?*
 *
 *  ⚠ **THE ACCOUNT NUMBER AND THE ADDRESS ARE NOT ON THIS TYPE.** The frame
 *  draws both on the account bar, one line above the card, on every signed-in
 *  screen. Serving them again would put two facts twice on one screen.
 *
 *  ⚠ **`phone` AND `email` ARRIVE ALREADY MASKED** (PO 2026-09-08, *"you can
 *  mask these detials"*). This screen never receives the full value, so no
 *  later edit of a component can reveal one; `CWP-024` still serves both in
 *  full because that screen edits them. `null` where the accounts disagree —
 *  one of four telephone numbers shown alone reads as settled.
 *
 *  ⚠ **THERE IS NO GOVERNMENT-ID FIELD AND ADDING ONE IS NOT THIS TYPE'S
 *  DECISION.** The drawing asks for *Driving licence ••••4417*;
 *  `customers.Contact.gov_id_last4` holds four digits and nothing in the
 *  portal reads it. Which record it would come from on a login holding several
 *  accounts, and whether the portal may read it at all, has never been put to
 *  anybody. The row is ABSENT, which is what the drawing itself asks for when
 *  there is no ID on file. */
export interface HomeIdentity {
  /** Whose account this is — `contact_details`' own `legal_name`. */
  name: HomeFact;
  /** The utility's OWN word from its `account_statuses` lookup — `Active`,
   *  `Vacation hold`, and a tenant's own additions. Not one of ours. */
  status: HomeFact;
  /** The lookup's `behavior_class` — `billable`, `non_billable`,
   *  `billable_base_only`, `terminal`, and a tenant's own (`BR-CUS-055`).
   *  ⚠ **THE CHIP'S COLOUR READS THIS AND NEVER THE NAME.** A utility may
   *  rename *Active* or add *Legal hold* tomorrow; a screen matching on the
   *  word would go grey on the day it did, silently. */
  status_class: HomeFact;
  /** ⚠ The NAME is the utility's own word for the service, not ours. */
  services: { code: string; name: string }[];
  /** ⚠ **BARE REFERENCES, NEVER DESCRIPTIONS** — `W-2209`, not *Water meter
   *  W-2209 · 5/8 inch* (PO 2026-09-08: *"just show IDs not details"*). The
   *  serial where there is one, the utility's asset number otherwise; neither
   *  is a database id (B14 rule 31). `[]` draws no row. */
  equipment: string[];
  phone: string | null;
  phone_varies: boolean;
  email: string | null;
  email_varies: boolean;
}

export interface HomeAttention {
  /** A KIND, not a sentence — the catalogue writes the words. `pay`, and since
   *  `CR-182-BRC10` (PO A1) `high_consumption` (a reading flagged high, not yet
   *  billed) and `high_bill` (the last bill priced one). */
  kind: string;
  amount?: string;
  currency?: string | null;
  /** `high_consumption` — the service CODE and the tenant's own word for it. */
  service?: string | null;
  service_name?: string | null;
  /** `high_consumption` — the reading's date, ISO. */
  taken_on?: string | null;
  /** `high_bill` — the bill's own number, which is its address. */
  number?: string | null;
}

export interface PortalHome {
  as_of: string;
  balances: BalanceSummary;
  /** `null` for somebody who has not been billed yet — never a `$0.00` tile. */
  last_bill: HomeBill | null;
  last_payment: { amount: string; currency: string | null; paid_on: string | null; method: string | null } | null;
  /** `[]` for an account with no measured service — no tile and NO empty chart. */
  usage: HomeUsage[];
  usage_series: HomeUsage[];
  recent_bills: HomeBill[];
  /** `CWP-022`'s rail — the four facts about the service itself. */
  service: HomeService;
  /** `CWP-022`'s account card. ⚠ **PRESENT ON EVERY HOME PAYLOAD** — its rows
   *  close up one at a time when they have no answer, which is not the same
   *  thing as the block being optional (hard-won law 2: an optional prop
   *  nothing passes is dead UI). */
  identity: HomeIdentity;
  /** ⚠ An EMPTY LIST, never a list of empty things (`BR-CWP-093`). */
  attention: HomeAttention[];
  /** `null` closes the slot up so nobody can tell it was there. */
  tip: PortalTip | null;
}

/** ⚠ **ONE ROUND TRIP AND NEVER CACHED.** The home page is opened four to
 *  twelve times a year and left in thirty seconds; six parallel calls would
 *  each pay the tenant resolution, and the slowest would set the page's speed.
 *  `BR-CWP-047` forbids caching the balance inside it. */
export async function getHome(client: ApiClient = api): Promise<PortalHome> {
  return requireData(await client.get<PortalHome>("/portal/home"));
}

// ── CR-068 wave G · CWP-027 — every bill (US-CWP-032) ──────────────────────

/** One row of `CWP-027`.
 *
 *  ⚠ **`total` AND `owing` ARE TWO FACTS AND THE SCREEN NEVER SUBTRACTS**
 *  (`BR-CWP-043`): the bill CHARGED `total` and still OWES `owing`, both
 *  computed by the server from the ledger. A screen doing the arithmetic is a
 *  screen that can disagree with what the utility will actually accept. */
export interface PortalBill {
  number: string | null;
  issued_on: string | null;
  due_on: string | null;
  total: string;
  owing: string;
  currency: string | null;
  period_start: string | null;
  period_end: string | null;
  /** `paid · part_paid · due · overdue · corrected` — a STATE, not a sentence;
   *  the catalogue writes the words (B14 rule 35). */
  state: string;
  /** `DEF-CWP-3980` — days from the server's own `today` to the due date, so
   *  the chip can count DOWN (*Due in 12 days*) as `CWP-027` draws it.
   *  Negative once the date has passed, `null` when the bill has no due date.
   *  ⚠ **THE SERVER COMPUTES IT, AND THAT IS THE POINT** — it is the same
   *  `today` that produced `state`, so the word and the count cannot disagree
   *  on a device whose clock or time zone is a day out. */
  due_in_days: number | null;
  /** What this bill CHARGED FOR, one entry per unit and never summed across
   *  units (hard rule 3). `[]` for a base-only bill. */
  usage: { quantity_display: string; unit: string }[];
  /** `BR-CWP-042` — a corrected bill names its replacement by the number on
   *  the paper, never by an id. */
  replaced_by: string | null;
  replaces: string | null;
}

/** ⚠ **NEVER CACHED** — every row carries a live owing figure. */
/**
 * `GET bills`, for the account the switcher names — or for the whole set when
 * it names none.
 *
 * ⚠ **`accountId` IS A QUERY PARAMETER AND NEVER PART OF THE PATH**
 * (`BR-CWP-010`, B14 rule 31). The server intersects it with the session's own
 * set in its query, so an id outside the set answers the same 404 as one that
 * does not exist; a screen that filtered the rows it was given would be a
 * screen enforcing a rule the query is supposed to enforce.
 */
/** `GET bills`, one page of it (`DEF-CWP-5747`).
 *
 *  ⚠ **THE THREE WHOLE-SET FACTS ARE SERVED BECAUSE THE SCREEN CAN NO LONGER
 *  COUNT THEM.** `oldest_on` is the drawing's *"Every bill since you started,
 *  Jun 2026 · 3 bills"*, `any_owing` decides whether the *Pay* control is
 *  drawn at all, and `populated` tells *you have no bills* apart from *none of
 *  your bills says that*. Read off a PAGE, the first would say *since Aug
 *  2026* on page 1 of eleven years and the second would hide the Pay button
 *  from somebody whose only unpaid bill is on page 2. */
export interface PortalBills extends PortalListWindow {
  bills: PortalBill[];
  oldest_on: string | null;
  any_owing: boolean;
  populated: boolean;
}

export async function getBills(
  options: { accountId?: string | null } & PortalListRequest = {},
  client: ApiClient = api,
): Promise<PortalBills> {
  const { accountId, ...request } = options;
  const query = listQuery(request);
  if (accountId) query.account_id = accountId;
  return requireData(await client.get<PortalBills>("/portal/bills", { query }));
}

// ── CR-068 wave G · CWP-024 — my details (US-CWP-028) ──────────────────────

/** A postal address as `CWP-024` edits it.
 *
 *  ⚠ **`line2` AND `country` ARE HERE BECAUSE A CUSTOMER TYPING THEIR OWN
 *  ADDRESS IS THE FIRST THING THAT CAN FILL THEM** (`DEF-2847` added the
 *  columns and nothing could: an address may not be split by guessing, and the
 *  utility's own country is not a statement about where a customer lives). */
export interface PortalPostal {
  line1: string | null;
  line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
}

export interface PortalMyDetails {
  as_of: string;
  email: string | null;
  /** ⚠ **TRUE WHEN THE LOGIN'S ACCOUNTS DO NOT AGREE**, including when some
   *  have no value at all. Three accounts with an email and one without is one
   *  bill going nowhere, and the screen has to be able to say so rather than
   *  showing the majority as though it were settled. */
  email_varies: boolean;
  phone: string | null;
  phone_varies: boolean;
  postal: PortalPostal | null;
  postal_varies: boolean;
  /** `BR-CWP-026` — shown, and never editable. Present in the body on purpose:
   *  a field left out reads as an oversight, a field shown read-only with *ask
   *  us to change this* reads as a rule. */
  legal_name: string | null;
  /** `BR-CWP-086` — how many of this login's accounts have post coming back. */
  returned_post_accounts: number;
  account_count: number;
  refused: string[];
  locales: string[];
  locale: string | null;
  security: {
    password_changed_on: string | null;
    code_channel: string | null;
    devices_signed_in: number;
  };
}

export async function getMyDetails(client: ApiClient = api): Promise<PortalMyDetails> {
  return requireData(await client.get<PortalMyDetails>("/portal/my-details"));
}

/** The `contact_detail` write (`BR-CWP-001` kind ⑤).
 *
 *  ⚠ **THERE IS NO `account_ids` FIELD AND THERE MUST NEVER BE** (`BR-CWP-010`).
 *  The set is the session's, re-derived on the request; a body that named
 *  accounts would be a customer choosing whose contact row to write. */
/** What a My details save answers. `phone_removed` / `text_reminders_on`
 *  (F-11, `DEF-CWP-10549`): an emptied phone box removed the number, and
 *  whether any account it was removed from has text reminders on. */
export interface MyDetailsSaved {
  accounts_updated: number;
  account_ids: string[];
  phone_removed?: boolean;
  text_reminders_on?: boolean;
}

export async function saveMyDetails(
  body: { email?: string; phone?: string; postal?: Partial<PortalPostal> },
  client: ApiClient = api,
): Promise<MyDetailsSaved> {
  return requireData(
    await client.post<MyDetailsSaved>(
      "/portal/my-details/save",
      body,
    ),
  );
}

// ── CR-068 wave G · CWP-020 — add another account (US-CWP-027) ─────────────

/** ⚠ **`matched: false` CARRIES ONE REASON FOR TWO DIFFERENT MISSES** — a
 *  wrong postcode and an unknown number answer identically, or this form walks
 *  the account-number space of the utility. `already_held` is the exception,
 *  and it discloses nothing: the account is on the list the asker is reading. */
export interface AddAccountFound {
  matched: boolean;
  reason?: string;
  account_ref?: string | null;
  sent_to?: string;
  channel?: string;
  expires_in_minutes?: number;
}

export async function findAccountToAdd(
  body: { account_number: string; postcode: string },
  client: ApiClient = api,
): Promise<AddAccountFound> {
  return requireData(await client.post<AddAccountFound>("/portal/accounts/add/find", body));
}

/** The `account_link` write (kind ⑥). ⚠ The code proves the person adding the
 *  account can read a message sent to **that account's** own contact. */
export async function verifyAccountToAdd(
  body: { account_ref: string; code: string },
  client: ApiClient = api,
): Promise<{ linked: boolean; reason?: string; created?: boolean }> {
  return requireData(
    await client.post<{ linked: boolean; reason?: string; created?: boolean }>(
      "/portal/accounts/add/verify",
      body,
    ),
  );
}

// ── CR-068 wave H · CWP-031 — documents and letters (US-CWP-036) ───────────

/** One route a document went by. ⚠ **`state` NEVER SAYS IT ARRIVED.** Nothing
 *  on this deployment reports a delivery on any channel, so the four values
 *  are `sent`, `queued`, `held` and `could_not_send` — and `sent` means it
 *  left the building, never that it was received (`BR-CWP-083`). */
export interface PortalDocumentRoute {
  channel: string;
  state: "sent" | "queued" | "held" | "could_not_send";
  reason: string | null;
  /** A letter the post office sent back was GENUINELY sent, so this is a date
   *  beside a `sent` route rather than a state of its own. */
  returned_on: string | null;
}

export interface PortalDocument {
  /** One of `tenancy.DOCUMENT_KINDS`, or `null` where no class has been ruled
   *  on for it — a stated absence, never the nearest kind. */
  kind: string | null;
  group: "bill" | "receipt" | "letter";
  /** The number on the paper — `BL-2608-0141`. ⚠ **NEVER an id and never part
   *  of one** (B14 rule 31; a truncated uuid is the same breach — DEF-3158).
   *  `null` where no human-facing number was minted, and the screen says so. */
  reference: string | null;
  sent_on: string | null;
  queued_on: string | null;
  /** `DEF-CWP-3969` — WHICH MONTH a bill covers, so the row can be named after
   *  the document rather than after its class. `null` on anything that is not
   *  a bill, and the screen falls back to the kind word. */
  period_start: string | null;
  period_end: string | null;
  /** `DEF-CWP-3969` — HOW MUCH a receipt was for. The stored 4dp figure,
   *  rounded where money is always rounded: at display (hard rule 2). */
  amount: string | null;
  currency: string | null;
  routes: PortalDocumentRoute[];
  state: "sent" | "queued" | "held" | "could_not_send";
  delivery_reported: boolean;
  delivery_not_reported_reason: string;
  stored_document: { available: boolean; reason: string | null };
}

/** ⚠ **`documents: null` IS NOT `[]`.** Null is the queue unreachable — nobody
 *  could ask — and `[]` is a customer who has genuinely been sent nothing. The
 *  type keeps them apart so a screen cannot render one empty state over both
 *  and tell a customer of eleven months that we never wrote to them. */
export interface PortalDocuments extends PortalListWindow {
  /** ⚠ **`null` AND `[]` ARE DIFFERENT ANSWERS.** Null means the queue that
   *  records what was sent could not be asked; `[]` means it was asked and
   *  this account has nothing. Rendering one empty state over both would tell
   *  a customer of eleven months that we never wrote to them. */
  documents: PortalDocument[] | null;
  groups: string[];
  unavailable: string | null;
  /** Whether this account has ANY post at all — which `count` cannot say,
   *  because `count` is the set the search and the chip matched. */
  populated: boolean;
  /** Whether ANY of it has a kept copy, over the whole set. `CPB-15`'s
   *  *Download a year* is held when this is false, and counting it off a PAGE
   *  would hold the control on page 2 for a customer whose kept documents are
   *  all on page 1 — a refusal that is simply untrue. */
  any_kept: boolean;
}

export async function getDocuments(
  accountId: string,
  request: PortalListRequest = {},
  client: ApiClient = api,
): Promise<PortalDocuments> {
  return requireData(
    await client.get<PortalDocuments>(`/portal/accounts/${accountId}/documents`, {
      query: listQuery(request),
    }),
  );
}

// ── CR-068 wave H · CWP-063 — a plan the utility has offered (US-CWP-053) ──

export interface PortalPlanInstalment {
  number: number;
  due_on: string;
  amount: string;
  currency: string;
}

/** ⚠ **THERE IS NO `id` ON THIS TYPE AND THERE MUST NEVER BE.** B14 rule 31,
 *  and nothing on this screen names the plan back to the server: all three
 *  controls are held (`OQ-CWP-1568`), so there is no request to identify. */
export interface PortalPlanOffer {
  covers: string;
  paid_up_front: string;
  spread: string;
  currency: string;
  instalment_count: number;
  cadence: string;
  offered_on: string | null;
  first_payment_on: string | null;
  instalments: PortalPlanInstalment[];
  /** Codes, not sentences: two of them are read from THIS plan's own elections
   *  (`BR-CUS-043`), so a plan that does not suspend late fees says fees still
   *  apply instead of promising they stop. */
  consequences: string[];
  /** ⚠ `expires_on` is `null` with its question named — no column holds an
   *  offer's expiry (`OQ-CWP-1566`). The screen states the absence; it invents
   *  nothing.
   *  ⚠ These read 1563/1564 until 2026-09-06 (`DEF-CWP-4139`); the SERVER has
   *  always sent the right pair in `expires_on_unavailable` and
   *  `offered_by_unavailable`, so nothing ever disagreed out loud. */
  expires_on: string | null;
  expires_on_unavailable: string | null;
  /** ⚠ **A PERSON'S NAME, OR `null` — `OQ-CWP-1567` CLOSED 2026-09-08, option
   *  (a)** (`CR-085` `CPB-21`). It used to be `null` always, because the clerk
   *  lived only on an audit row the retention schedule deletes;
   *  `payment_plans` keeps the fact now. **Never an id** (B14 rule 31): the
   *  resolution happens in `payments`, since the portal may not read
   *  `identity` at all (`BR-CWP-004`, `G91`). */
  offered_by: string | null;
  /** `null` where a person is named; `"not_recorded"` where none is — a plan
   *  older than the column, or one a job wrote. Nothing was backfilled. */
  offered_by_unavailable: string | null;
  agreement: { available: boolean; reason: string | null };
  actions_held: boolean;
  actions_held_reason: string;
}

export async function getPlanOffer(
  accountId: string,
  client: ApiClient = api,
): Promise<{ offer: PortalPlanOffer | null }> {
  return requireData(
    await client.get<{ offer: PortalPlanOffer | null }>(`/portal/accounts/${accountId}/plans/offer`),
  );
}

// ── CR-068 wave H · CWP-044 — level pay (US-CWP-054) ───────────────────────

/** ⚠ **`level` IS `null` WITH A REASON, NEVER `0.00`.** A zero monthly amount
 *  is a real, chooseable figure and would read as *this customer pays
 *  nothing* — the posture `budget_api` already takes one screen along. */
export interface PortalLevelPay {
  months_of_history: number;
  required_months: number | null;
  trailing_total: string | null;
  months_counted: number;
  monthly_average: string | null;
  level: string | null;
  level_unavailable: string | null;
  currency: string | null;
  rounding: string | null;
  /** 1–12, or `null` — ⚠ **never 6.** `settings_families` ratifies no month
   *  (*"rule names the parameter, ratifies no month"*), so a screen that
   *  hardcoded June would be right for one utility and silently wrong for the
   *  rest (`US-CWP-054` TC-6). */
  settle_up_month: number | null;
  relevel_cadence_months: number | null;
  settings_unavailable: string | null;
  enrolled: boolean;
  enrolled_level: string | null;
  enrolled_settle_up_month: number | null;
  /** What was BILLED, oldest first — the chart's bars. The line is `level`. */
  billed: string[];
  /** ⚠ **`CR-085` `CPB-18` — WHICH months are missing, `[year, month]`, newest
   *  first.** *8 of 12* is a count a customer cannot act on: it does not say
   *  whether a bill is missing or whether they simply have not been here a
   *  year. Empty for an account never billed — that is no history, not a hole
   *  in one. */
  missing_months: [number, number][];
  /** The subset INSIDE the billed history: a real gap in a run of bills. */
  missing_month_gaps: [number, number][];
  /** The subset BEFORE the first bill: not long enough with us yet. */
  missing_months_before_first_bill: [number, number][];
  /** `[year, month]` of the first bill this account was ever issued. */
  first_billed_month: [number, number] | null;
  join_held: boolean;
  join_held_reason: string;
}

export async function getLevelPay(
  accountId: string,
  client: ApiClient = api,
): Promise<{ level_pay: PortalLevelPay | null }> {
  return requireData(
    await client.get<{ level_pay: PortalLevelPay | null }>(`/portal/accounts/${accountId}/level-pay`),
  );
}

// ── CR-068 wave H · CWP-033 · CWP-034 · CWP-037 (US-CWP-040 · 041 · 043) ────
//
// ⚠ **THESE TYPES DESCRIBE `metering`'s OWN PUBLISHED READ, NOT A PORTAL
// INVENTION.** `apps/metering/monthly_usage_reads.usage_payload` is what the
// staff Account details Usage tab draws too; the portal is the third surface on
// it (`04-docs/05-modules/15-portal/12-reuse-map.md`), so the shapes below are
// the same facts in a customer's words and never a second interpretation.
//
// ⚠ **THERE IS NO `id` ON ANY OF THEM AND THAT IS THE TYPE DOING THE WORK**
// (B14 rule 31). A field that is not on the type is a field a screen cannot
// render, which is a stronger guarantee than a review comment — and
// `DEF-3158` records that eight characters of a uuid is the same breach as a
// whole one, so there is nothing here to truncate either.

/** One month of one service. ⚠ `quantity: null` with `absent: true` is an
 *  UNREAD month and is **never** a `0` (`BR-MET-106`): *"zero usage and no
 *  read are different claims about a customer"*. */
export interface PortalUsagePoint {
  month: string;
  quantity: string | null;
  quantity_display: string | null;
  unit: string | null;
  absent: boolean;
  read_count: number;
  estimated_read_count: number;
  estimated: boolean;
  computed_at: string | null;
}

/** ⚠ `value: null` with an `absent_reason` — an average over no months is not
 *  `0`, and *"no change"* and *"we cannot say"* are different claims. */
export interface PortalUsageMetric {
  value: string | null;
  display: string | null;
  unit: string | null;
  month?: string | null;
  absent_reason: string | null;
  description?: string;
  months_counted?: number;
  months_absent?: number;
  this_year_total?: string | null;
  prior_year_total?: string | null;
  /** `CPB-06` / `CPB-07` — one month measured against ONE other month.
   *
   *  ⚠ **`difference_display` AND `unit` ARE `null` TOGETHER OR NEITHER IS**
   *  (CLAUDE.md hard rule 3). There is no state in which a screen holds the
   *  number and not the unit, which is wave H's *"Monthly average 800"* made
   *  structurally impossible rather than merely repaired. */
  difference?: string | null;
  difference_display?: string | null;
  /** ⚠ **A CODE, NEVER A WORD** (B14 rule 35): `more` · `less` · `same`.
   *  `same` is a THIRD value and not a signed zero, because *"0.00% more"* is
   *  not a sentence anybody says. Eleven catalogues write the sentence. */
  direction?: string | null;
  /** The month this comparison actually used — which is NOT always the month
   *  before (`BR-MET-106` makes an unread month absent, so the server walks
   *  back to the nearest month that has a figure). The screen prints it, or
   *  *"20% less than last month"* would be a false claim about a month nobody
   *  walked. */
  against_month?: string | null;
}

/** One charge line of a usage month, as the BILL wrote it. */
export interface PortalUsageCostLine {
  description: string | null;
  /** Never present without its `unit` — the server drops the pair otherwise
   *  (hard rule 3). */
  quantity: string | null;
  unit: string | null;
  /** FOUR decimals — a rate is not money (`OQ-620`(a), PO 2026-08-27). */
  rate: string | null;
  /** `per_unit` · `percent`, so a screen puts a `$` on one and a `%` on the
   *  other (`DEF-CWP-3967`). */
  rate_basis: string | null;
  rate_percent: string | null;
  amount_display: string;
}

/** `CPB-08` — what a usage month cost, entirely off the bill's own lines.
 *
 *  ⚠ **`lines` IS PLURAL BECAUSE REAL TARIFFS ARE TIERED.** The blueprint draws
 *  one line; Ana's own July electric bill has TWO — `500 kWh at $0.1100 =
 *  $55.00` and `300 kWh at $0.1350 = $40.50`. Showing only the first would tell
 *  a customer `$55.00` for a month that cost `$95.50`.
 *
 *  ⚠ **`total_display` IS THE SUM OF THE LINES' OWN STORED AMOUNTS**, summed on
 *  the server, so the panel foots against the printed column by construction.
 *  Nothing on the screen multiplies or adds. */
export interface PortalUsageCost {
  month: string;
  /** The bill's NUMBER, so a customer can go and check it (B14 rule 31). */
  bill_number: string;
  lines: PortalUsageCostLine[];
  total_display: string;
  /** The unit the month is measured in when every line agrees on one. */
  unit: string | null;
  /** Whether `month` is the LATEST month the account has a reading for.
   *
   *  ⚠ **USUALLY IT IS NOT, AND THAT IS WHY THIS FIELD EXISTS.** The newest
   *  read month is almost never billed yet — Ana's August is read and unbilled
   *  while her July cost `$95.50` — so the panel walks back to the most recent
   *  month that HAS a bill. This is what lets the screen say *"August is not
   *  billed yet"* above the answer rather than silently answering about a
   *  different month than the number above it. */
  is_latest_month?: boolean;
}

export interface PortalUsageSeries {
  /** ⚠ **NO `id`** — the portal strips the platform service uuid. */
  service: { code: string; name: string };
  unit: string | null;
  /** A window whose months disagree about their unit has no summable figure at
   *  all (hard rule 3), and the screen says so rather than adding them. */
  unit_absence: { reason: string } | null;
  points: PortalUsagePoint[];
  months_present: number;
  months_absent: number;
  /** `CPB-08` — what the LATEST stated month cost, **entirely off the bill's own
   *  line**. `null` is the COMMON answer rather than the edge: the latest stated
   *  month is usually not billed yet. */
  cost?: PortalUsageCost | null;
  metrics: {
    avg_per_month: PortalUsageMetric;
    peak: PortalUsageMetric;
    low: PortalUsageMetric;
    /** Twelve months against the twelve BEFORE them — a total against a total. */
    yoy: PortalUsageMetric;
    /** `CPB-07` — the latest stated month against the one before it. */
    vs_last_month: PortalUsageMetric;
    /** `CPB-06` — the latest stated month against the SAME month a year back. */
    same_month_last_year: PortalUsageMetric;
  };
}

/** What an UNMEASURED service is billed on (`BR-CWP-073`). ⚠ A SHAPE, never a
 *  sentence: eleven catalogues write *Billed on: water used* and *Billed on:
 *  your 96 gal cart* in their own language (B14 rule 35). */
export type PortalBilledOn =
  | { kind: "share"; of: string | null }
  | { kind: "equipment"; count: number; size: string | null; equipment: string | null };

export interface PortalUsageService {
  code: string;
  /** The utility's OWN word for the service, rendered verbatim. */
  name: string;
  /** `metered` · `share` · `capacity` — `tenant_services.billing_basis`. */
  basis: string;
  measured: boolean;
  /** ⚠ `null` for an unmeasured service — **and also for a measured one with
   *  no stated month**, which is a different claim the screen must keep apart:
   *  *not measured* versus *not read yet*. */
  series: PortalUsageSeries | null;
  billed_on: PortalBilledOn | null;
}

export interface PortalUsage {
  as_of: string;
  window: { months: number; from: string; to: string; options: number[] };
  windows: number[];
  services: PortalUsageService[];
  /** `null` closes the tile up — most days have no window open. */
  next_reading: { from: string; to: string; open_now: boolean } | null;
  /** `null` closes the slot up so nobody can tell it was there. */
  tip: PortalTip | null;
  /**
   * `CWP-060`'s SECOND placement — the answer a clerk pinned to this screen
   * (`DEF-CWP-3945`, wired 2026-09-11).
   *
   * ⚠ **`ALSO_SHOW_SCREENS` HAS NAMED `usage` SINCE THE FEATURE SHIPPED
   * AND THIS FIELD DID NOT EXIST**, so the tick a clerk made on Settings →
   * Help was accepted, stored and never rendered anywhere. The bill and the
   * overdue screen each read theirs.
   *
   * ⚠ **`null` IS THE COMMON CASE AND THE KEY IS ALWAYS PRESENT**
   * (`BR-CWP-093`) — the same posture `PortalBillDetail` records one type
   * along, and for the same reason: a missing key reads as *"this build has
   * no such feature"*.
   */
  attached_answer: PortalAttachedAnswer | null;
}

export async function getAccountUsage(
  accountId: string,
  months: number,
  client: ApiClient = api,
): Promise<PortalUsage> {
  return requireData(
    await client.get<PortalUsage>(`/portal/accounts/${accountId}/usage`, { query: { months } }),
  );
}

/** `BR-CWP-072` — the reason AND the size. ⚠ `estimated_reading_display` is
 *  often `null` and that is `BR-MET-028`: an estimate carries a consumption and
 *  no dial figure, because nobody read a dial. The catalogue then writes the
 *  shorter sentence and never a `0`. */
export interface PortalReadingCorrection {
  estimated_reading: string | null;
  estimated_reading_display: string | null;
  estimated_used: string | null;
  corrected_to: string | null;
  corrected_to_display: string | null;
  corrected_on: string | null;
  reason: string | null;
}

/** One committed reading. ⚠ **`how` IS A CODE AND THE CATALOGUE WRITES THE
 *  WORDS** (`BR-CWP-071`, B14 rule 35) — `estimated_corrected`, `self_read`,
 *  `reader`, `automatic`, `estimated`, `not_stated`. */
export interface PortalReading {
  taken_on: string | null;
  meter_serial: string | null;
  meter_no: string | null;
  /** ⚠ The service the meter stands on, as a CODE (`DEF-CWP-3990`). `null` for
   *  a meter on no service point. */
  meter_service: string | null;
  /** ⚠ The TENANT'S OWN NAME for that service — `Water`, not a word this
   *  product wrote (B14 rule 35, and the same standing `service_name` has on a
   *  bill line). `null` when the code resolves to none of the tenant's enabled
   *  services. */
  meter_service_name: string | null;
  reading: string | null;
  reading_display: string | null;
  used_since: string | null;
  /** ⚠ The rendered PAIR — `4,820 gal`. `null` when the unit is missing, and
   *  the cell dashes rather than printing a bare number (hard rule 3). */
  used_since_display: string | null;
  unit: string | null;
  how: string;
  read_method: string | null;
  read_method_origin: string;
  estimated: boolean;
  /** `CR-182-BRC10` (PO A3) — BR-MET-020/120 flagged this reading high; the
   *  row carries the *High consumption alert* tag. */
  high_consumption?: boolean;
  correction: PortalReadingCorrection | null;
  channel: string;
  /** ⚠ `null` for a reading no ISSUED bill covers — an EMPTY cell, never the
   *  nearest bill (`US-CWP-041` TC-4). */
  on_bill: string | null;
}

/** One of `CWP-034`'s meter tabs — `⚡ Electric · 8841-C`.
 *
 *  ⚠ **THE SERVER ANSWERS THIS NOW (`DEF-CWP-5747`), AND IT HAS TO.** The
 *  screen built its tabs from the payload it held; the payload is one page, so
 *  tabs built from it would read *the services in the newest fifty readings*
 *  and a quarterly-read water meter would lose its tab with every test green.
 *
 *  `name` is the TENANT'S own word for the service (B14 rule 35) and `meters`
 *  is the distinct references that answered on it — the screen brings the
 *  meter column back when there is not exactly one, which is the only case a
 *  tab cannot state. */
export interface PortalReadingService {
  code: string;
  name: string | null;
  meters: string[];
}

export interface PortalReadings extends PortalListWindow {
  readings: PortalReading[];
  /** ⚠ **OVER THE WHOLE ACCOUNT, NEVER OVER THE PAGE** — see the type above. */
  services: PortalReadingService[];
  /** ⚠ **`null` CLOSES THE LINE UP** (`BR-CWP-093`) — a dash above a list of
   *  readings reads as a date we lost. */
  next_read: PortalNextRead | null;
  /** `US-CWP-042` TC-7 (`DEF-CWP-10175`) — whether *Send a reading* appears.
   *  `false` means ABSENT, never greyed (`BR-CWP-093`). Optional only because
   *  hand-built fixtures predate it; the server always sends it. */
  self_read_enabled?: boolean;
}

/** One register of a meter the customer may read (`CWP-035`). The reading
 *  always travels with its unit (hard rule 3). `last_reading: null` with a
 *  date is an estimate nobody read a dial for; both null is a meter never read. */
export interface PortalSelfReadRegister {
  register: string;
  unit: string | null;
  last_reading: string | null;
  last_read_on: string | null;
  /** *Expected now — about 153,300*: a hint for the person typing, never a
   *  threshold. `null` when there is no period to measure a rate from. */
  expected_now: string | null;
}

/** A meter on the customer's own unit, named by SERIAL (B14 rule 31). `meter`
 *  is the meter NUMBER the reading is posted under — the value of the select,
 *  never a database id. */
export interface PortalSelfReadMeter {
  meter: string;
  serial: string | null;
  service: string | null;
  /** The TENANT'S own word for the service (B14 rule 35). */
  service_name: string | null;
  where: string | null;
  registers: PortalSelfReadRegister[];
}

/** `GET accounts/{id}/readings/send` — `CWP-035`'s frame. */
export interface PortalSelfReadFrame {
  today: string;
  meters: PortalSelfReadMeter[];
  window: PortalNextRead | null;
}

/** `POST accounts/{id}/readings/send` — what came of it (`BR-CWP-074`).
 *  `flagged` is the VALIDATION flag; every reading carries the provenance flag
 *  `customer` on the server whether flagged or not. */
export interface PortalSelfReadResult {
  received: boolean;
  flagged: boolean;
  checks: string[];
  used: string | null;
  unit: string | null;
  /** The high check's own ratio, rounded — *about nineteen times your usual*. */
  times_usual: number | null;
  read_on: string;
  reading: string;
}

/** `GET accounts/{id}/readings/send` — `CWP-035`'s frame (`US-CWP-042`). */
export async function getSelfReadFrame(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalSelfReadFrame> {
  return requireData(
    await client.get<PortalSelfReadFrame>(`/portal/accounts/${accountId}/readings/send`),
  );
}

/** `POST accounts/{id}/readings/send` — the `meter_reading` write point. */
export async function sendReading(
  accountId: string,
  body: { meter: string; register: string; value: string; read_on: string },
  client: ApiClient = api,
): Promise<PortalSelfReadResult> {
  return requireData(
    await client.post<PortalSelfReadResult>(`/portal/accounts/${accountId}/readings/send`, body),
  );
}

/**
 * `GET accounts/{id}/readings` — **ONE PAGE, searched and sorted by the
 * server** (`DEF-CWP-5747`, `NFR-3`).
 *
 * ⚠ **THIS USED TO ASK FOR EVERY READING THE ACCOUNT HAD EVER TAKEN.** A
 * household is a few hundred rows and an AMI deployment is an interval reading
 * per meter per hour — ~17,000 rows for two years, served so that a browser
 * could search, sort and slice them. `?f.service=` is the meter tab.
 */
export async function getAccountReadings(
  accountId: string,
  request: PortalListRequest = {},
  client: ApiClient = api,
): Promise<PortalReadings> {
  return requireData(
    await client.get<PortalReadings>(`/portal/accounts/${accountId}/readings`, {
      query: listQuery(request),
    }),
  );
}

/** One thing fitted at the property. ⚠ **`last_read_on: null` IS A CART**, and
 *  it renders as an empty cell — a `0` would say the cart measured nothing
 *  (`US-CWP-043` TC-2). */
export interface PortalEquipment {
  serial_no: string | null;
  asset_no: string | null;
  kind: string;
  kind_code: string;
  category: string;
  service: string | null;
  /** ⚠ The TENANT'S OWN NAME for that service (`DEF-CWP-3991`). `kind` alone is
   *  the seed word `Meter`, which two rows at one property both carry; this is
   *  what lets the screen say *Water Meter* and *Refuse cart*. `null` for a
   *  device on no service point, which then keeps its bare kind. */
  service_name: string | null;
  where: string | null;
  fitted_on: string | null;
  status: string;
  status_code: string;
  behavior_class: string;
  test_due_on: string | null;
  test_due: boolean;
  /** The ratified size-class CODE — `W-58`, `FL-2`, `CART-96`. ⚠ **NEVER
   *  DRAWN**: B14 rule 32 keeps an internal code off clerk-facing copy. What
   *  the screen shows is `size_class_name` below. */
  size_class: string | null;
  /**
   * `DEF-CWP-4848` — **the size as a person reads it**: `Water 5/8"`,
   * `Fire line 2"`, `Trash 96-gallon cart`, resolved on the server from the
   * ratified vocabulary (`tenancy.service_size_classes`).
   *
   * ⚠ **IT MATTERS MOST ON FIRE.** CLAUDE.md's fire rule is that the SIZE
   * CLASS PICKS THE PRICE and the COUNT multiplies it — one 2" line is
   * `$12.00`, one 6" line is `$60.00` — so a fire line is the one row on this
   * screen carrying a monthly charge whose figure could not be checked against
   * anything else the screen said. The drawing's note: *"Size is stated in
   * inches, as the customer's plumber would."*
   *
   * ⚠ **`null` IS ORDINARY** — most equipment has no recorded size class,
   * and a code with no ratified name answers `null` rather than falling back
   * to the code. The cell closes up (`BR-CWP-093`).
   */
  size_class_name: string | null;
  last_read_on: string | null;
  /** `CPB-10` — **whose it is**: `utility` · `customer`, a CODE the catalogue
   *  writes as *Ours* / *Yours* (B14 rule 35). It settles the repair-bill
   *  question, which is the drawing's own reason for the column. */
  maintained_by: string;
  /** `usage_only` · `per_item`. ⚠ **THIS IS A DIFFERENT ABSENCE FROM A NULL
   *  CHARGE AND THE SCREEN MUST TELL THEM APART.** *A meter carries no monthly
   *  charge* is a FACT (the drawing writes **No charge**); *we cannot find what
   *  you were charged for this cart* is a GAP. Collapsing both to `null` prints
   *  **No charge** over something the customer is in fact paying for. */
  charge_basis: string;
  /** The LATEST BILL's own rate for one of these, at two places (hard rule 2),
   *  or `null`. Never `amount ÷ quantity` — see `billing_seam.per_item_monthly`. */
  monthly_charge: string | null;
  /** The bill that figure came off, by its NUMBER (B14 rule 31). */
  monthly_charge_bill: string | null;
}

/** `CPB-09` — when somebody is coming to read the meter next.
 *
 *  ⚠ **`days_until` IS A NUMBER AND THE CATALOGUE WRITES *in 22 days***
 *  (B14 rule 35). It is never negative: a crew already walking the route is not
 *  *"in −3 days"*, and `open_now` is the fact the sentence turns on. */
export interface PortalNextRead {
  from: string;
  to: string;
  open_now: boolean;
  days_until: number;
}

export async function getAccountEquipment(
  accountId: string,
  client: ApiClient = api,
): Promise<{ as_of: string; equipment: PortalEquipment[] }> {
  return requireData(
    await client.get<{ as_of: string; equipment: PortalEquipment[] }>(
      `/portal/accounts/${accountId}/equipment`,
    ),
  );
}

// ── CR-068 wave H · CWP-028 · CWP-029 · CWP-030 — one bill (US-CWP-033 · 034 · 035) ──
//
// ⚠ **THE PATH SEGMENT IS THE BILL NUMBER AND NEVER AN ID** (B14 rule 31).
// `BL-2608-0141` is what is printed on the paper the customer is holding and
// what they would read out on the telephone. A truncated id was never an
// option either — `features/customers/accountDetailTabs.tsx` records that eight
// characters of a uuid used as link text is the same breach as the whole of it.

/** One charge line, as the server projected it for a customer.
 *
 *  ⚠ **`quantity` AND `unit` ARE NULL TOGETHER OR NOT AT ALL** (hard rule 3).
 *  The server refuses to serve a quantity whose unit it does not know, so a
 *  screen cannot render `4,820` in a column headed *Quantity* even by mistake.
 *
 *  ⚠ **`rate` IS FOUR DECIMALS AND IS NOT MONEY** — `OQ-620(a)`, PO 2026-08-27:
 *  *"A rate is not money and not a quantity - 4 decimal places"*. Passing it to
 *  `formatMoney` would print `$0.01` for `0.0089`. */
export interface PortalBillLine {
  description: string | null;
  quantity: string | null;
  unit: string | null;
  rate: string | null;
  /** `DEF-CWP-3967` — WHAT KIND of number `rate` is. `per_unit` means money
   *  per `unit`; `percent` means a proportion and `rate_percent` carries it in
   *  percentage POINTS. `null` on a line with no rate at all. */
  rate_basis: "per_unit" | "percent" | null;
  /** Percentage POINTS at two padded places — `6.25`, `40.00` (hard rule 2).
   *  ⚠ **THE SERVER DID THE ×100.** The stored figure is a FRACTION and
   *  converting in the browser is how `0.02%` gets printed for a 2% tax. */
  rate_percent: string | null;
  /** DEF-BIL-8744 — the days this line's amount was cut down by
   *  (`{days: 19, of: 30}`); null on every line that foots without it. */
  day_share?: { days: number; of: number } | null;
  /** The stored 4dp figure. */
  amount: string;
  /** ⚠ **THE FIGURE THE CUSTOMER ADDS UP** — rounded ONCE, by the server, so
   *  the column foots to the group subtotal and to the bill's own total. */
  amount_display: string;
  kind: string | null;
}

/** One service's block — `WATER`, `SEWER`, `TRASH`, … and `taxes_and_fees`. */
export interface PortalBillGroup {
  /** A service CODE, or `taxes_and_fees` for everything the bill charges at
   *  bill level (PO 2026-08-11: *"Tax rates are for bill not for service"*). */
  service: string;
  /** The platform catalogue's name, used only when the catalogue has no word. */
  service_name: string | null;
  subtotal_display: string | null;
  lines: PortalBillLine[];
}

/** `BR-CWP-071` — one reading behind the bill, and HOW it was taken. */
export interface PortalBillReading {
  meter: string | null;
  /** `DEF-CWP-3967` — the service CODE this meter measures, worded by
   *  `rating.service.*`. `null` for a meter with no service point. */
  service: string | null;
  read_at: string | null;
  /** Already composed with its unit by the server, or null. */
  prior_value: string | null;
  current_value: string | null;
  usage: string | null;
  unit: string | null;
  read_method: string | null;
  /** `recorded` · `derived` · `not_stated` — what keeps `read_method` honest. */
  read_method_origin: string | null;
  estimated: boolean;
  /** `CR-182-BRC10` — BR-MET-020/120 flagged this reading high. */
  high_consumption?: boolean;
}

export interface PortalBillDetail {
  number: string | null;
  issued_on: string | null;
  due_on: string | null;
  period_start: string | null;
  period_end: string | null;
  total: string;
  owing: string;
  currency: string | null;
  state: string;
  /** `CR-182-BRC10` (PO A2) — this bill priced a reading flagged high; the
   *  screen says *High usage* and nothing longer. */
  high_usage?: boolean;
  replaced_by: string | null;
  replaces: string | null;
  groups: PortalBillGroup[];
  /** The three footer figures, each rounded once by the server. ⚠ The screen
   *  never adds them up: `subtotal + tax = total` is asserted in a test, not
   *  recomputed in a browser. */
  subtotal_display: string;
  tax_display: string;
  total_display: string;
  account: {
    /** ⚠ `null` is a REAL answer and is never drawn as `$0.00` — `BR-BIL-035`
     *  writes nulls rather than zeros when the stamp could not be taken, and
     *  `0.00` would tell a customer in arrears that they are square. */
    brought_forward: string | null;
    paid_since: string | null;
    this_bill: string;
    owing: string;
  };
  readings: PortalBillReading[];
  /**
   * `CWP-061` — the answer the utility attached to bills (`also_show_on_screen`).
   *
   * ⚠ **`null` IS THE COMMON CASE AND THE SLOT CLOSES UP** (`BR-CWP-093`).
   * The KEY is always present: a missing key would read as *"this build has
   * no such feature"* rather than *"nothing is attached"*, and the next lane
   * needs to be able to tell those apart.
   */
  attached_answer: PortalAttachedAnswer | null;
}

export interface PortalAttachedAnswer {
  slug: string;
  question: string;
  topic: string;
  body: string;
  asked_for: string;
  shown_in: string;
  is_fallback: boolean;
  updated_on: string | null;
}


export async function getBillDetail(
  number: string,
  client: ApiClient = api,
): Promise<PortalBillDetail> {
  return requireData(
    await client.get<PortalBillDetail>(`/portal/bills/${encodeURIComponent(number)}`),
  );
}

/** `CWP-029`. ⚠ **`available` IS THE ONLY THING THE SCREEN BRANCHES ON.**
 *  `provenance` is `original` or it is not served at all: the portal refuses to
 *  hand a customer a fresh render under the sentence *"the bill we sent you"*. */
export interface PortalPrintedBill {
  number: string | null;
  issued_on: string | null;
  provenance: string;
  available: boolean;
  unavailable_reason: string | null;
  template_version: number | null;
  byte_length: number | null;
  content_type: string | null;
}

export async function getPrintedBill(
  number: string,
  client: ApiClient = api,
): Promise<PortalPrintedBill> {
  return requireData(
    await client.get<PortalPrintedBill>(
      `/portal/bills/${encodeURIComponent(number)}/document`,
    ),
  );
}

/** Where the kept page is downloaded from. A plain URL rather than a fetch: the
 *  response is `application/pdf` with `Content-Disposition: attachment`, and
 *  the browser's own download is what a customer pressed the button for. */
export function printedBillHref(tenant: string, number: string): string {
  return apiHref(`/${tenant}/portal/bills/${encodeURIComponent(number)}/document.pdf`);
}

/**
 * `CR-085` `CPB-14` — a copy of ONE document we sent, by the number printed on
 * it (`CWP-031`, and `CWP-041`'s receipt, which is the same document).
 *
 * ⚠ **AN ADDRESS, NOT A FETCH.** The response is the frozen artefact with
 * `Content-Disposition: attachment`, so the browser's own download is what the
 * customer pressed the control for — the same posture `printedBillHref` takes
 * and for the same reason.
 *
 * ⚠ **THE NUMBER, NEVER A ROW ID** (B14 rule 31). A document with no minted
 * number cannot be addressed one at a time; it still leaves in the year's
 * archive, which is why `documentsBundleHref` is not merely a convenience.
 */
export function documentFileHref(tenant: string, reference: string): string {
  return apiHref(`/${tenant}/portal/documents/${encodeURIComponent(reference)}/file`);
}

/**
 * `CR-085` `CPB-14` — the SIGNED agreement for the plan this account is on
 * (`CWP-043`), beside `CWP-063`'s offer agreement.
 *
 * ⚠ **NO PLAN ID IN THE ADDRESS** (B14 rule 31). A customer holds at most one
 * live plan, so *this account's current plan's agreement* names it exactly, and
 * `current_plans` deliberately publishes no id for a URL to carry.
 */
export function planAgreementHref(tenant: string, accountId: string): string {
  return apiHref(
    `/${tenant}/portal/accounts/${encodeURIComponent(accountId)}/plans/current/agreement`,
  );
}

/** `CR-085` `CPB-15` — a year of this account's kept documents, as one zip. */
export function documentsBundleHref(tenant: string, accountId: string): string {
  return apiHref(`/${tenant}/portal/accounts/${encodeURIComponent(accountId)}/documents/year.zip`);
}

/** One line of *why* — ⚠ **NONE ARE SERVED YET** (`OQ-CWP-1563`). The type
 *  exists so the screen that will draw them is written against a shape rather
 *  than against nothing, and so `components_available` is the switch rather
 *  than an empty array read as *"nothing moved"*. */
export interface PortalBillComponent {
  /** A stable identifier for a test and a log — `water_usage`, `bill_tax`.
   *  ⚠ **NEVER SHOWN.** B14 rule 32 keeps internal codes out of customer copy;
   *  the screen words the row from `service` and `kind`. */
  code: string;
  /** The service this share belongs to, worded by `rating.service.*`. `null`
   *  is a bill-level charge — a tax, a whole-bill discount. */
  service: string | null;
  /** `usage · base · tax · discount · fee · adjustment · minimum`. */
  kind: string;
  amount: string;
  amount_display: string;
}

/** `CWP-030`. ⚠ **`compared: false` MEANS NO COMPARISON IS OFFERED AT ALL** —
 *  not one against zero. A first bill described as *"$142.18 more than last
 *  month"* is arithmetically true and, to somebody who has just moved in, a lie. */
export interface PortalBillComparison {
  number: string | null;
  compared: boolean;
  period_start: string | null;
  period_end: string | null;
  total_display: string;
  prior_number?: string | null;
  prior_period_end?: string | null;
  prior_total_display?: string;
  /** ⚠ **SIGNED, AND NOTHING TAKES AN ABSOLUTE VALUE OF IT.** `-3.74` is a bill
   *  that FELL; read as `3.74` it would be reported as a rise with a
   *  correct-looking figure. */
  difference?: string;
  difference_display?: string;
  /** `cost_more` · `cost_less` · `cost_the_same`. The catalogue writes the
   *  words (B14 rule 35). */
  direction?: string;
  components: PortalBillComponent[];
  components_available: boolean;
  /** The open question the breakdown waits on, or null once it is signed. */
  components_blocked_by: string | null;
  against_last_year: {
    service: string | null;
    service_name: string | null;
    unit: string;
    this_year: string;
    last_year: string;
    this_year_label: string;
    last_year_label: string;
    this_year_estimated: boolean;
    last_year_estimated: boolean;
  }[];
}

export async function getBillComparison(
  number: string,
  client: ApiClient = api,
): Promise<PortalBillComparison> {
  return requireData(
    await client.get<PortalBillComparison>(
      `/portal/bills/${encodeURIComponent(number)}/comparison`,
    ),
  );
}

// ── CR-068 wave G · CWP-041 — the money list (US-CWP-048) ──────────────────

/**
 * One row of everything that moved money.
 *
 * ⚠ **A BOUNCE IS TWO ROWS AND THE TYPE SAYS SO** (`BR-CWP-061`): the reversal
 * arrives with `kind: "reversal"`, `returned_by_the_bank: true` and a NEGATIVE
 * `amount`, directly above the payment it undoes — whose `state` is
 * `"reversed"`, **derived by the server** from the existence of that row. The
 * original payment is never edited (hard rule 4).
 *
 * ⚠ **THE SIGN IS THE SERVER'S. TAKE NO ABSOLUTE VALUE.** `-129.0200` on a
 * reversal and a negative credit note are both meant; `credit_notes.amount <= 0`
 * is a database constraint added after two writers stored opposite signs and a
 * sign-off panel read `$272.30` on an account owing `$222.30`.
 *
 * ⚠ **THERE IS NO `id` ON THIS TYPE AND THERE MUST NEVER BE** (B14 rule 31 —
 * and eight characters of one is the same breach). `reference` is the cheque
 * number the customer wrote, the `PMT-` number or the credit note's own number.
 *
 * ⚠ **`reason` IS PRESENT ON A CREDIT ROW AND ABSENT ON A WRITE-OFF ROW**, and
 * that asymmetry is two rules: `BR-CWP-050` asks for an adjustment's plain
 * reason, `BR-CWP-051` forbids a write-off's. *Bankruptcy* is the utility's
 * judgment about a person; the amount is the person's own money.
 */
export interface PortalMoneyRow {
  kind: "payment" | "reversal" | "credit" | "write_off";
  date: string | null;
  /** The tenant's OWN word for the tender. `null` on a credit or a write-off,
   *  which carry no instrument — a stated absence, never a blank. */
  how: string | null;
  reference: string | null;
  /**
   * The payment's own `PMT-` number, and **not the same field as `reference`**
   * (`CR-085` `CPB-20`). `reference` prefers the CHEQUE number the customer
   * wrote, because that is what they can find in their own bank statement; the
   * receipt DOCUMENT is filed under the payment number. `null` on a reversal, a
   * credit and a write-off, which mint no number and post no receipt — so the
   * receipt control is ABSENT on those rows rather than refused.
   */
  receipt_reference: string | null;
  /**
   * Whether a copy of that receipt was actually KEPT (`CR-085` `CPB-20`).
   * `payments` knows the payment has a number; only `notifications` knows
   * whether the document exists — so the two are separate facts and the screen
   * draws three states: the control, the control disabled with *we kept no copy
   * of this*, and nothing at all where there is no number. Found by walking
   * `CWP-041`: without it the row offered a download the server then refused.
   */
  receipt_available: boolean;
  /** The bills this money met, by their printed numbers. Empty on a reversal,
   *  whose cell reads *returned by the bank* instead. */
  applied_to: string[];
  returned_by_the_bank: boolean;
  amount: string;
  currency: string | null;
  /** ⚠ `received` replaced `cleared` on 2026-10-21 (`DEF-CWP-10341`): a
   *  `posted` and a bank-`cleared` payment read the same to a customer.
   *  `cancelled` is both rows of a cancel; `unknown` is the server's explicit
   *  fallback for a status it does not define. */
  state:
    | "received"
    | "processing"
    | "failed"
    | "cancelled"
    | "unknown"
    | "bounced"
    | "reversed"
    | "credited"
    | "written_off"
    | "write_off_reversed";
  money_type: string;
  reason?: string | null;
}

/**
 * `GET payments`, for the account the switcher names — or for the whole set.
 * `accountId` travels the same way `getBills` sends it, and for the same
 * reason (`BR-CWP-010`).
 */
export interface PortalMoney extends PortalListWindow {
  money: PortalMoneyRow[];
  /** Whether anything moved money in the chosen YEAR — so a customer who chose
   *  *This year* and paid nothing in it reads the empty sentence rather than
   *  *none of your payments says that*. */
  populated: boolean;
}

export async function getMoneyList(
  options: { year?: number; accountId?: string | null } & PortalListRequest = {},
  client: ApiClient = api,
): Promise<PortalMoney> {
  const { year, accountId, ...request } = options;
  const query = listQuery(request);
  // ⚠ **`year` IS ITS OWN PARAMETER AND NOT AN `f.` FILTER**, because the
  // server applies it BEFORE `BR-CWP-061`'s bounce pairing — a reversal and
  // the payment it undoes have to be adjacent, and a filter applied after the
  // pairing could leave one of the pair behind.
  if (year !== undefined) query.year = year;
  if (accountId) query.account_id = accountId;
  return requireData(await client.get<PortalMoney>("/portal/payments", { query }));
}

// ── CR-068 wave M · CWP-042 · CWP-043 — payment plans (US-CWP-051 · 052) ────

/** ⚠ **`carries_the_rounding` IS THE ENGINE'S OWN FLAG, NOT *the last one*.**
 *  `US-CWP-051` §1: *"the uneven last instalment is deliberate and must be
 *  shown"*, so the screen states the fact rather than inferring it. */
export interface PortalPlanInstalmentPreview {
  seq: number;
  due_on: string;
  amount: string;
  carries_the_rounding: boolean;
}

/**
 * What the plan WOULD be — and every figure is the product's own instalment
 * engine, previewed, never recomputed here (`US-CWP-051` §7).
 *
 * ⚠ **`base_instalment_count` IS SERVED SO THE CONSEQUENCE BOX CANNOT DISAGREE
 * WITH THE TABLE BESIDE IT.** The blueprint's own box read *six payments of
 * $22.03, then one of $22.05* — seven payments, `$154.23` — over its own table
 * of six totalling `$132.20`. It is **five**, then one.
 *
 * ⚠ **`suspend_late_fees` IS A PER-PLAN ELECTION AND IT IS READ** (`BR-CWP-064`).
 * When it is off the box must say fees still apply; the blueprint calls a box
 * that promised otherwise *worse than a blank space*.
 */
export interface PortalPlanPreview {
  account_no: string | null;
  service_address: string | null;
  balance: string;
  down_payment: string;
  spread: string;
  currency: string | null;
  cadence: string;
  term_months: number;
  first_due_on: string;
  instalments: PortalPlanInstalmentPreview[];
  base_instalment_count: number;
  base_amount: string;
  final_amount: string;
  suspend_late_fees: boolean;
  suspend_disconnect: boolean;
  current_bill_still_due: boolean;
  /** Always `[]`. On the wire so a caller can tell a preview from a commit
   *  without knowing which route it called — the staff preview's own contract. */
  writes: string[];
}

export async function previewPlan(
  accountId: string,
  body: { term_months: number; first_due_on: string; down_payment: string },
  client: ApiClient = api,
): Promise<PortalPlanPreview> {
  return requireData(
    await client.post<PortalPlanPreview>(`/portal/accounts/${accountId}/plans/preview`, body),
  );
}

/** ⚠ **`plan_created` IS ALWAYS `false` AND IT IS ON THE WIRE ON PURPOSE**
 *  (`BR-CWP-066`, PO 2026-09-04): a customer may ASK for a plan and a clerk
 *  grants it. The screen says so rather than implying a plan now exists. */
export async function askForPlan(
  accountId: string,
  body: { term_months: number; first_due_on: string; down_payment: string; note?: string },
  client: ApiClient = api,
): Promise<{ reference: string; plan_created: boolean; granted_by: string }> {
  return requireData(
    await client.post<{ reference: string; plan_created: boolean; granted_by: string }>(
      `/portal/accounts/${accountId}/plans/request`,
      body,
    ),
  );
}

/** ⚠ **`paid_reference` IS THE `PMT-` NUMBER OF THE PAYMENT THAT CLEARED THIS
 *  INSTALMENT** — a fact the back office has held all along and no screen has
 *  ever shown, which is why a customer cannot reconcile a plan against a bank
 *  statement today (`US-CWP-052` §1).
 *
 *  ⚠ **NOT `PortalPlanInstalment` — THAT NAME IS ALREADY TAKEN, ONE SCREEN
 *  ALONG.** `CWP-063`'s offer exports an instalment type of its own above, and
 *  a second `export interface` of the same name in one module does not clash:
 *  TypeScript MERGES the two declarations, so every consumer of either silently
 *  requires the union of both field sets. `tsc` is what caught it and nothing
 *  else would have — the two shapes are genuinely different facts (an OFFERED
 *  instalment has no state and nothing has paid it yet), so they are two types
 *  with two names rather than one type with two authors. */
export interface PortalPlanInstalmentRow {
  seq: number;
  due_on: string;
  amount: string;
  currency: string;
  state: "paid_on_time" | "paid_late" | "due_next" | "to_come" | "missed";
  days_until: number | null;
  paid_on: string | null;
  paid_reference: string | null;
  carries_the_rounding: boolean;
}

/** ⚠ **NO PLAN ID.** A customer holds at most one live plan and a handful of
 *  closed ones; the screen keys on the date it started (B14 rule 31). */
export interface PortalPlan {
  status: string;
  live: boolean;
  cadence: string;
  currency: string;
  total: string;
  down_payment: string;
  spread: string;
  paid_to_date: string;
  term_months: number;
  started_on: string | null;
  closed_on: string | null;
  suspend_late_fees: boolean;
  suspend_disconnect: boolean;
  autopay_enabled: boolean;
  current_bill_still_due: boolean;
  instalments: PortalPlanInstalmentRow[];
  instalments_total: string;
  /**
   * Whether a copy of the signed agreement was actually kept and can be served
   * (`CR-085` `CPB-14`). The server asks the store the same question the file
   * route asks, so the control and the download cannot disagree — which is the
   * fault this whole wave was written against.
   */
  agreement_available: boolean;
}

export async function getCurrentPlans(
  accountId: string,
  client: ApiClient = api,
): Promise<{ plans: PortalPlan[] }> {
  return requireData(
    await client.get<{ plans: PortalPlan[] }>(`/portal/accounts/${accountId}/plans/current`),
  );
}

// ── CR-068 · CWP-046 — what do you need (US-CWP-060) ───────────────────────

/**
 * One errand card.
 *
 * ⚠ **`to` IS THE SERVER'S ANSWER AND `held_reason` IS THE OTHER HALF OF IT.**
 * Exactly one of the two is set: a card either leads somewhere or says, in five
 * or six words, why it does not yet (`BR-CWP-056`, B14 rule 33). A screen that
 * decided this for itself would be a second map of which screens exist, and the
 * first wave to build `CWP-048` would have to remember to change both.
 *
 * ⚠ **`label` AND `hint` ARE CATALOGUE KEYS**, not English (B14 rule 35). A
 * utility that renames a card puts its own words there instead, and the screen
 * renders an unknown key as the text itself.
 */
export interface PortalErrand {
  code: string;
  label: string | null;
  hint: string | null;
  to: string | null;
  held_reason: string | null;
}

/** ⚠ **NO ROW ID** (B14 rule 31) — `SR-26-0056` is the handle, and it is the
 *  number the customer would read out on the telephone. `status` is the state
 *  CODE and the catalogue writes the word. */
/**
 * What a request IS, as a CODE the catalogue writes (B14 rule 35).
 *
 * ⚠ **`null` MEANS *the customer's own words ARE the answer*** and is right
 * for a reported problem or an application — not a gap. See
 * `customers_seam.request_kind` for why this is derived rather than stored:
 * `service_requests` carries no category column (`DEF-CWP-3881`).
 */
export interface PortalRequestTitle {
  kind: string;
  /** The `BL-` number, on a bill query only, and `null` where it could not be
   *  read back — so a screen never prints *"Query about bill "*. */
  number: string | null;
}

export interface PortalOpenRequest {
  reference: string | null;
  /** `CR-085` `CPB-05` — what this request IS, before anything said about it. */
  title: PortalRequestTitle | null;
  what: string | null;
  raised_on: string | null;
  status: string;
  documents_wanted: number;
}

/** ⚠ **`lists_only_portal_requests` IS ON THE WIRE ON PURPOSE.** A request a
 *  clerk raised at the counter carries no link to this login and cannot appear
 *  here, so the screen says what the list holds rather than letting a customer
 *  read it as *everything I have ever asked for* (`OQ-CWP-1680`). */
export interface PortalRequestHub {
  errands: PortalErrand[];
  open_requests: PortalOpenRequest[];
  /**
   * `CR-085` `CPB-11` — the ones that are FINISHED, and they had no door.
   *
   * ⚠ **A REQUEST LEFT THE CUSTOMER'S WORLD THE MOMENT IT CLOSED**
   * (`DEF-CWP-4203`): completed, refused, closed, or withdrawn by the customer
   * themselves, it was read by the server and thrown away — so the reference
   * we had handed them opened nothing they could find their way back to.
   */
  closed_requests: PortalOpenRequest[];
  lists_only_portal_requests: boolean;
}

export async function getRequestHub(client: ApiClient = api): Promise<PortalRequestHub> {
  return requireData(await client.get<PortalRequestHub>("/portal/requests"));
}

// ── CR-068 · CWP-052 — stop or restart service (US-CWP-062) ────────────────

/**
 * The comparison, as the server computes it.
 *
 * ⚠ **EVERY MONEY FIELD IS `string | null` AND THE NULL IS THE POINT**
 * (`US-CWP-062` TC-8). A missing standing charge is not `"0.0000"`: *no
 * standing charge* and *a standing charge of `$0.00`* are different claims
 * about a utility, and a comparison built on the first read as the second
 * would tell a customer that stopping for nineteen months costs nothing.
 *
 * ⚠ **`cheaper` AND `no_verdict` ARE MUTUALLY EXCLUSIVE.** Either the server
 * reached an answer or it names why it could not; the screen never decides.
 * `US-CWP-062` §7: *"a screen that always says stopping is cheaper is wrong for
 * a long absence."*
 *
 * ⚠ **`account_stays_open` IS SERVED RATHER THAN ASSUMED** (`BR-CWP-080`). It
 * is the sentence that prevents the most expensive misunderstanding in the
 * product, and a screen that derived it could stop saying it.
 */
export interface PortalStopOrRestart {
  stop_from: string;
  start_again: string | null;
  months: number | null;
  account_stays_open: boolean;
  standing_charge_monthly: string | null;
  standing_charge_unavailable: string | null;
  cost_of_stopping: string | null;
  connection_fee: string | null;
  new_deposit: string | null;
  cost_of_closing: string | null;
  cheaper: "stopping" | "closing" | null;
  no_verdict: string | null;
  currency: string | null;
  services: { code: string; name: string; since: string | null }[];
}

export async function getStopOrRestart(
  accountId: string,
  query: { stop_from: string; start_again?: string | null },
  client: ApiClient = api,
): Promise<PortalStopOrRestart> {
  const search = new URLSearchParams({ stop_from: query.stop_from });
  if (query.start_again) search.set("start_again", query.start_again);
  return requireData(
    await client.get<PortalStopOrRestart>(
      `/portal/accounts/${accountId}/stop-or-restart?${search.toString()}`,
    ),
  );
}

/** ⚠ **`supply_stopped` IS ALWAYS `false` AND IT IS ON THE WIRE ON PURPOSE.**
 *  Pressing *Request this* puts a row on a clerk's worklist; the supply is
 *  still on and the account is still open (`BR-CWP-080`). The confirmation
 *  says exactly that rather than implying the service has stopped. */
export async function askToStopOrRestart(
  accountId: string,
  body: {
    stop_from: string;
    start_again?: string | null;
    reason?: string;
    name?: string;
    email?: string;
    phone?: string;
  },
  client: ApiClient = api,
): Promise<{ reference: string; supply_stopped: boolean; account_stays_open: boolean }> {
  return requireData(
    await client.post<{
      reference: string;
      supply_stopped: boolean;
      account_stays_open: boolean;
    }>(`/portal/accounts/${accountId}/stop-or-restart/ask`, body),
  );
}

/** `CR-183-BRC10` T8 — the account's temporary stop, customer-safe (no ids). */
export interface PortalTemporaryStop {
  current: {
    status: "scheduled" | "on_hold";
    stop_from: string;
    restart_on: string | null;
    restart_reference: string | null;
    restart_state: string | null;
  } | null;
  pending: {
    reference: string | null;
    state: string;
    stop_from: string;
    restart_on: string | null;
  } | null;
  can_restart_now: boolean;
  billed_during_hold: "base_only";
}

export async function getTemporaryStop(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalTemporaryStop> {
  return requireData(
    await client.get<PortalTemporaryStop>(`/portal/accounts/${accountId}/temporary-stop`),
  );
}

/** B4 — *Restart my service now*: a request a clerk approves. */
export async function askToRestartNow(
  accountId: string,
  client: ApiClient = api,
): Promise<{ reference: string; supply_restarted: boolean }> {
  return requireData(
    await client.post<{ reference: string; supply_restarted: boolean }>(
      `/portal/accounts/${accountId}/temporary-stop/restart`,
      {},
    ),
  );
}


/**
 * `CWP-025` — how a customer is contacted, and the consent behind it.
 *
 * ⚠ **`rows` IS PER DOCUMENT KIND AND THE SWITCHES ARE NOT.** `email_on` and
 * `text_on` are ONE answer each, applied to every row, because this product
 * holds no per-event customer preference (`OQ-CWP-1660`). The type says so —
 * there is no per-row switch to reach for — which is the point of writing it
 * this way rather than as forty-eight independent cells.
 */
export interface PortalPreferenceRow {
  kind: string;
  post: "always" | "on" | "off" | "none";
  email: "always" | "on" | "off" | "none";
  text: "always" | "on" | "off" | "none";
  portal: "always" | "on" | "off" | "none";
}

export interface PortalPaperlessConsent {
  agreed_on: string | null;
  wording_version: string;
  /** ⚠ Set means *agreed and then withdrawn*, which is a DIFFERENT fact from
   *  an absent consent — the row is never deleted (`BR-CWP-087`). */
  withdrawn_on: string | null;
  taken_on_screen: string;
}

export interface PortalPreferences {
  as_of: string;
  channels: string[];
  /** FALSE means the print floor could not be read, and the grid is not drawn
   *  at all — a grid on that answer would tell a customer a bill can come off
   *  paper. */
  floor_readable: boolean;
  rows: PortalPreferenceRow[];
  email_on: boolean;
  text_on: boolean;
  applies_to_every_document: boolean;
  election_varies: boolean;
  account_count: number;
  locales: string[];
  locale: string | null;
  /** `null` is *nobody ever asked*, and the screen must not draw it as an
   *  opt-out (`US-CWP-014` TC-2). */
  paperless: PortalPaperlessConsent | null;
}

export async function getPreferences(client: ApiClient = api): Promise<PortalPreferences> {
  return requireData(await client.get<PortalPreferences>("/portal/my-details/preferences"));
}

export async function savePreferences(
  fields: Record<string, unknown>,
  client: ApiClient = api,
): Promise<{ accounts_updated: number; account_ids: string[] }> {
  return requireData(
    await client.post<{ accounts_updated: number; account_ids: string[] }>(
      "/portal/my-details/preferences/save",
      fields,
    ),
  );
}

export async function withdrawPaperless(
  client: ApiClient = api,
): Promise<{ withdrawn: number }> {
  return requireData(
    await client.post<{ withdrawn: number }>("/portal/my-details/paperless/withdraw", {}),
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CR-068 wave L1 — the four arrears screens (US-CWP-056 · 057 · 058 · 059)
// ═══════════════════════════════════════════════════════════════════════════

/** One rung of `CWP-057`'s timeline, as the server composed it.
 *
 * ⚠ **`tier` IS `null` WITH `unmapped: true` FOR THE FIVE-DAY RUNG**
 * (`BR-CWP-092`). The screen renders that as an ABSENCE and may never fall
 * back to a neighbour's chip: showing somebody at the five-day notice as though
 * they were at the ten-day one moves the date they think they have.
 *
 * ⚠ **`is_floor` MEANS *no earlier than*, NOT *on*.** Nothing in this product
 * advances a tier on a date, so a future step is a floor the utility will not
 * act before — the wording follows this flag rather than a copywriter's
 * caution. */
export interface PortalLadderStep {
  step: "due" | "notice_sent" | "notice_next" | "cut";
  tier: string | null;
  unmapped: boolean;
  on: string | null;
  is_floor: boolean;
  state: "done" | "current" | "future";
  served_channel?: string | null;
  served_on?: string | null;
}

/** ⚠ **`subtotal` AND NOT `total`, AND THE NAME IS THE POINT.** `parts_missing`
 *  names every part the sum could not include — today always `new_deposit`,
 *  because no rule in this product prices a reconnection deposit
 *  (`OQ-CWP-1600`). A screen that labelled this *if it goes that far* would be
 *  quoting a figure the customer discovers is wrong at the counter. */
export interface PortalArrearsCost {
  /** ⚠ **`already_owed` SAYS THE AMOUNT IS INSIDE `subtotal` ALREADY**, and it
   *  never means the charge was waived (`DEF-CWP-6072`). The cut ISSUES the
   *  reconnection fee, so from that moment it is an open bill and is in what
   *  the customer owes; the row keeps its amount, and the SUM stops adding it. */
  parts: { part: string; amount: string | null; already_owed: boolean }[];
  parts_missing: string[];
  subtotal: string | null;
  currency: string | null;
  /** ⚠ **WHICH QUESTION `subtotal` ANSWERED**, stated by `customers` off the
   *  case's `cut_on` and carried through unchanged. `null` before any case
   *  exists. It explains the figure; it does not repair it. */
  basis: { code: string; fee_in_arrears: boolean } | null;
  /** ⚠ **`detail` IS DELIBERATELY NOT ON THIS TYPE** — see `PortalProblem`. */
  problems: PortalProblem[];
}

export interface PortalArrears {
  as_of: string;
  overdue: boolean;
  /**
   * The one published answer a clerk pinned to this screen (`CWP-060`'s second
   * placement, `DEF-CWP-3945`).
   *
   * ⚠ **`null` IS THE NORMAL CASE AND THE SLOT CLOSES UP** (`BR-CWP-093`) —
   * an empty card headed with a question is worse than no card at all. It is
   * the SAME shape the help screen renders, because it is the same answer:
   * the utility writes it once and this is where it is ALSO shown.
   */
  attached_answer: PortalHelpAnswer | null;
  owed: string | null;
  currency: string | null;
  due_on: string | null;
  days_overdue: number | null;
  tier: string | null;
  tier_unmapped: boolean;
  chips: string[];
  tier_reached_on: string | null;
  case_open: boolean;
  timeline: PortalLadderStep[];
  services_at_risk: string[];
  ladder_running: boolean;
  halt_code: string | null;
  held_by: { kind: string; lifetime: string }[];
  cost: PortalArrearsCost;
  reconnection_fee_absence: { code: string; detail: string } | null;
  new_deposit_required: boolean | null;
  write_offs: { amount: string; currency: string; date: string; state: string }[];
  scheduler: { advances_on_a_schedule: boolean } | null;
  /** ⚠ **`detail` IS DELIBERATELY NOT ON THIS TYPE** — see `PortalProblem`. */
  problems: PortalProblem[];
}

export async function getArrears(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalArrears> {
  return requireData(
    await client.get<PortalArrears>(`/portal/accounts/${accountId}/arrears`),
  );
}

/** ⚠ **`ends_on` IS `null` ON A PLAN HOLD AND ALWAYS WILL BE.** The three
 *  lifetimes are three shapes, not one shape with a nullable field: a
 *  certificate MUST carry an end date, a plan hold must NOT (it lifts the day
 *  an instalment is missed), and a moratorium carries both ends. The screen
 *  says in words what ends the middle one rather than drawing a blank cell. */
export interface PortalProtection {
  kind: string;
  lifetime: "expires_on_a_date" | "derived_from_the_plan" | "regulator_date_window";
  in_force: boolean;
  since: string | null;
  ends_on: string | null;
  lifted_on: string | null;
}

export interface PortalProtections {
  as_of: string;
  any: boolean;
  protections: PortalProtection[];
  hold_stops_disconnection_not_debt: boolean;
  /** ⚠ **`detail` IS DELIBERATELY NOT ON THIS TYPE** — see `PortalProblem`. */
  problems: PortalProblem[];
}

export async function getProtections(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalProtections> {
  return requireData(
    await client.get<PortalProtections>(`/portal/accounts/${accountId}/protections`),
  );
}

/** ⚠ **`still_open` IS TRUE ON ALL THREE AT EVERY TIER** — `OQ-CWP-1601`.
 *  Nothing in this product closes a hardship route after the final notice, and
 *  closing a door the product would still open turns a frightened customer away
 *  from help they can still get. `past_final_notice` carries the urgency. */
export interface PortalHardshipRoute {
  route: "payment_plan" | "medical_certificate" | "level_pay";
  still_open: boolean;
  granted_by: string;
  asks_for: string;
  hold_expires?: boolean;
  upload_available?: boolean;
}

export interface PortalHelpPaying {
  as_of: string;
  routes: PortalHardshipRoute[];
  plans_enabled: boolean;
  past_final_notice: boolean;
  /** ⚠ **`apply: false` — nobody applies for a weather moratorium.** The
   *  regulator sets the window, so the screen states it and draws NO control. */
  moratorium: { from: string; until: string | null; apply: boolean; set_by: string | null } | null;
}

export async function getHelpPaying(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalHelpPaying> {
  return requireData(
    await client.get<PortalHelpPaying>(`/portal/accounts/${accountId}/help-paying`),
  );
}

/** ⚠ **`protection_created` IS ALWAYS `false` AND IT IS ON THE WIRE ON
 *  PURPOSE** (`BR-CWP-089`): the portal never grants a protection — every one
 *  needs a person and a document. `bring_the_document` is the other half: the
 *  portal accepts no upload, so the route ends at the counter. */
export async function askForHelpPaying(
  accountId: string,
  body: { route: string; note?: string },
  client: ApiClient = api,
): Promise<{
  reference: string;
  protection_created: boolean;
  granted_by: string;
  bring_the_document: boolean;
}> {
  return requireData(
    await client.post<{
      reference: string;
      protection_created: boolean;
      granted_by: string;
      bring_the_document: boolean;
    }>(`/portal/accounts/${accountId}/help-paying/ask`, body),
  );
}

/** ⚠ **A CREDIT'S AMOUNT ARRIVES NEGATIVE AND IS RENDERED NEGATIVE.**
 *  `credit_notes.amount <= 0` is a database CHECK added after two writers
 *  stored opposite signs; nothing between that table and this screen re-signs
 *  it or takes an absolute value. */
export interface PortalCredit {
  reason: string | null;
  credit_note_no: string | null;
  issued_on: string | null;
  amount: string;
  currency: string | null;
  used_on_bill: string | null;
}

/** ⚠ **A VOIDED REFUND IS IN THE LIST, MARKED VOIDED** — never removed. A
 *  customer told money was coming and then shown nothing has no way to ask what
 *  happened to it. `void_reason` is the utility's own note and is not here. */
export interface PortalRefund {
  amount: string;
  currency: string;
  status: string;
  method: string | null;
  reference: string | null;
  reason: string | null;
  requested_at: string | null;
  approved_at: string | null;
  issued_at: string | null;
  cleared_at: string | null;
  voided_at: string | null;
  steps: { step: string; on: string | null }[];
  /** ⚠ **WHERE IT IS GOING BACK TO, AND WHY IT MAY NOT BE WHERE IT CAME FROM**
   *  (`US-CWP-049`, `BR-CWP-060`). Optional on the type because a response
   *  served before this landed carries no such key, and a screen that assumed
   *  it would throw on a cached body. */
  destination?: PortalRefundDestination;
}

/** `CWP-045`'s refund line — the three facts a customer needs and no more.
 *
 * ⚠ **`kind: "fallback"` ALWAYS CARRIES A `fallback_reason`, AND THAT IS THE
 * WHOLE POINT** (`US-CWP-049` TC-3, TC-4). *"Sent"* on its own is what the
 * story forbids; the screen says where the money came in, where it went, and
 * why those differ.
 *
 * ⚠ **`brand` AND `last_four` MAY BE NULL ON A CARD REFUND.** A card is named
 * only when the customer holds exactly one, because nothing links a payment to
 * a stored instrument and guessing which of two cards is a digit on a
 * customer's screen nobody can vouch for. */
export interface PortalRefundDestination {
  /** `original_method` · `fallback`. */
  kind: string;
  /** `check` · `ach` — how the money is actually going out. */
  method: string | null;
  reference: string | null;
  /** The tender the money came in on: `card` · `check` · `cash` · … */
  came_in_by: string | null;
  brand: string | null;
  last_four: string | null;
  /** `card_expired` · `card_rails_absent` · `several_sources` ·
   *  `source_unknown`. `null` when the money is going back the way it came. */
  fallback_reason: string | null;
  /** Where a cheque was posted — `customers.addresses kind='mailing'`, which
   *  is where the BILL goes. `null` for anything that is not a cheque. */
  posted_to?: string | null;
}

export async function getMoneyBack(
  accountId: string,
  client: ApiClient = api,
): Promise<{ any: boolean; refunds: PortalRefund[]; credits: PortalCredit[] }> {
  return requireData(
    await client.get<{ any: boolean; refunds: PortalRefund[]; credits: PortalCredit[] }>(
      `/portal/accounts/${accountId}/money-back`,
    ),
  );
}


// ══ CR-068 wave R — requests, queries and questions ════════════════════════
//
// ⚠ **EVERY ONE OF THESE IS A SERVICE REQUEST** (`CR-072`, PO 2026-09-04:
// *"all the request coming from portal should go in Service request"*). Two
// of them CREATE one; two act on one the customer already raised. Nothing here
// edits a bill, a reading or an account.

/** One step of `CWP-051`'s six-step ladder. ⚠ `at` is `null` for a step that
 *  has not happened — the screen draws the box without a date rather than
 *  inventing one. */
export interface PortalRequestStep {
  key: string;
  state: "done" | "current" | "future";
  at: string | null;
}

/**
 * One row of the customer-visible timeline.
 *
 * ⚠ **READ THE FIELDS AS THE RULE** (`BR-CWP-078`). There is no `id`, no
 * `actor` and no `internal` flag, because there is none on the wire: the server
 * projects `service_request_reads.history_tab` and drops them by name. A screen
 * cannot render a clerk's routing note it was never sent.
 */
export interface PortalRequestEvent {
  at: string;
  kind: string;
  to_state: string | null;
  note: string | null;
  note_type: string | null;
}

/** `GET requests/{reference}` — `CWP-051`. ⚠ **NO `id`**: the request is named
 *  by its `SR-` number, which is what a customer reads down the telephone
 *  (B14 rule 31). */
export interface PortalRequestDetail {
  reference: string;
  /** `CR-085` `CPB-12` — what this request IS, so the page head can say it.
   *  `null` where the customer's own words are the answer. */
  title: PortalRequestTitle | null;
  /** The channel the row carries — the drawing's *through the portal* under
   *  the first step, served rather than assumed (hard-won law 1). */
  raised_through: string | null;
  status: string;
  is_open: boolean;
  /** `BR-CWP-079` — drawn from the SAME state table the server refuses on, so
   *  the screen cannot offer a withdrawal the server denies. */
  may_withdraw: boolean;
  raised_at: string | null;
  /** Computed from `now − raised`, never stored (`US-CWP-063` TC-9). */
  open_for_days: number | null;
  what_they_said: string | null;
  waiting_on: string | null;
  /** `BR-CWP-077` — a refusal always carries one, and the portal shows it. */
  refusal_reason: string | null;
  closed_at: string | null;
  steps: PortalRequestStep[];
  timeline: PortalRequestEvent[];
}

export async function getRequest(
  reference: string,
  client: ApiClient = api,
): Promise<PortalRequestDetail> {
  return requireData(
    await client.get<PortalRequestDetail>(`/portal/requests/${encodeURIComponent(reference)}`),
  );
}

// ⚠⚠ **`withdrawRequest` WAS DELETED HERE ON 2026-09-19, AND THE ENDPOINT IT
// CALLED IS STILL LIVE.** `BR-CWP-079` is SUPERSEDED: the PO closed the
// customer's own withdraw door with the clerk's (`OQ-CUS-12486`, *"if customer
// dont want it - they will call and clark will refuse it. thats'it . keep it
// simple"*), `withdraw` left `service_request.TRANSITIONS`, and
// `TrackRequest` draws no control.
//
// **The SERVER route stays and refuses cleanly** — a bookmarked tab or a
// replayed post still reaches it, and a readable refusal serves those better
// than a 404. **This CLIENT wrapper does not**, because a wrapper nothing
// imports is a door with no handle: `G118` named it by that description the
// first time the gates ran after the button went, and it is hard-won law 2's
// mirror one layer down from the screen.

/** The customer's answer to the clerk's question (`BR-CWP-075`'s third
 *  transition) — and the first row in this product with `internal=false`. */
export async function addRequestNote(
  reference: string,
  note: string,
  client: ApiClient = api,
): Promise<{ at: string; customer_visible: boolean }> {
  return requireData(
    await client.post<{ at: string; customer_visible: boolean }>(
      `/portal/requests/${encodeURIComponent(reference)}/notes`,
      { note },
    ),
  );
}

/**
 * `POST bills/{number}/dispute` — `CWP-055`.
 *
 * ⚠ **THREE FLAGS THAT ARE ALWAYS `false`, AND EACH IS ON THE WIRE SO NO SCREEN
 * CAN IMPLY OTHERWISE.** `bill_changed`: an issued bill takes no UPDATE
 * (CLAUDE.md hard rule 4). `collection_held`: nothing in this product records a
 * disputed AMOUNT, so no hold is performed — `OQ-420`, still OPEN, and
 * `OQ-CWP-1682` carries the wording collision to the Product Owner.
 * `reading_marked`: `metering`'s dispute marker is raised by a clerk, not by
 * the portal — `OQ-CWP-1681`.
 */
export async function disputeBill(
  number: string,
  body: { what: string; reason: string; own_reading?: string },
  client: ApiClient = api,
): Promise<{
  reference: string;
  bill_number: string;
  bill_changed: boolean;
  collection_held: boolean;
  reading_marked: boolean;
}> {
  return requireData(
    await client.post<{
      reference: string;
      bill_number: string;
      bill_changed: boolean;
      collection_held: boolean;
      reading_marked: boolean;
    }>(`/portal/bills/${encodeURIComponent(number)}/dispute`, body),
  );
}

/** `POST questions` — `CWP-054`. ⚠ `bill_number` may be empty: a question with
 *  no bill is a general question and is accepted (`US-CWP-066` TC-5). */
export async function askAQuestion(
  body: { topic: string; what: string; bill_number?: string },
  client: ApiClient = api,
): Promise<{ reference: string; bill_number: string | null }> {
  return requireData(
    await client.post<{ reference: string; bill_number: string | null }>(
      "/portal/questions",
      body,
    ),
  );
}

// ── CR-068 · CWP-032 — your final bill (US-CWP-037) ────────────────────────

/** ⚠ **ABSENT, NOT ZERO, ON AN ACCOUNT WITH NO DEPOSIT** (`US-CWP-037` TC-6).
 *  `deposit: null` means *there is nothing here*; a `$0.00` held would read as
 *  *we took nothing from you*, which is a different sentence. */
export interface PortalFinalDeposit {
  held: string;
  interest: string;
  total: string;
  taken_on: string | null;
  currency: string | null;
}

/**
 * The closing bill and how the deposit settled it.
 *
 * ⚠ **`remainder` IS SIGNED AND THE SCREEN RENDERS THE SIGN THE SERVER SENT.**
 * Negative is money owed BACK — `$63.40 − $150.00 − $3.20 = −$89.80`, drawn as
 * *we owe you `$89.80`* by wording, never by `Math.abs`.
 *
 * ⚠ **`path` IS THE ENGINE'S AND NOT A READING OF THE SIGN** (`BR-CWP-048`): a
 * negative final balance is a REFUND and never a carried credit, because there
 * is no next bill to carry it to.
 *
 * ⚠ **`service_charges` AND `charges` ARE TWO FIGURES.** The first is the
 * closing bill's own total, the second is what the deposit was applied to —
 * that total plus anything already outstanding (PO 2026-08-12, *"everything
 * outstanding"*). They are equal on an account with no arrears.
 */
export interface PortalFinalBill {
  number: string | null;
  issued_on: string | null;
  due_on: string | null;
  total: string;
  currency: string | null;
  period_start: string | null;
  period_end: string | null;
  service_charges: string;
  charges?: string;
  deposit: PortalFinalDeposit | null;
  remainder?: string;
  path: string | null;
  path_is_automatic?: boolean;
  settled: boolean;
  settlement_unavailable: string | null;
}

/** The reading the final bill was cut on — chosen out of the readings list the
 *  customer can already see, never re-queried (`CWP-034` shows the same rows). */
export interface PortalClosingReading {
  taken_on: string | null;
  meter_serial: string | null;
  reading_display: string | null;
  used_since_display: string | null;
  how: string | null;
}

export interface PortalFinalBillView {
  bill: PortalFinalBill | null;
  closing_reading: PortalClosingReading | null;
  query_reading_open: boolean;
  query_reading_closed_reason: string | null;
}

export async function getFinalBill(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalFinalBillView> {
  return requireData(
    await client.get<PortalFinalBillView>(`/portal/accounts/${accountId}/final-bill`),
  );
}

// ── CR-068 · CWP-066 — where your level pay stands (US-CWP-055) ────────────

/** ⚠ **THE DIRECTION IS A WORD AND THE SIZE IS ALWAYS POSITIVE** (`US-CWP-055`
 *  TC-7): *ahead* and *behind* in the customer's language, never a bare signed
 *  number. `level` is the third value — exactly level, which is neither. */
export type PortalVarianceDirection = "ahead" | "behind" | "level";

/** ⚠ **NO OVERRIDE REASON ON THIS TYPE, BECAUSE THERE IS NONE ON THE WIRE**
 *  (TC-4). The utility's private note about a customer is not the customer's,
 *  and the guard is that the server never selects it. */
export interface PortalLevelStanding {
  level: string;
  override: string | null;
  computed_level: string | null;
  currency: string | null;
  variance: string;
  variance_direction: PortalVarianceDirection;
  settle_up_month: number | null;
  enrolled_on: string | null;
  last_leveled_at: string | null;
  status: string;
  off_budget: boolean;
  changes: {
    event: string;
    on: string | null;
    level: string | null;
    actual: string | null;
    movement: string;
    balance_after: string;
    currency: string | null;
  }[];
}

/** ⚠ **`standing: null` ROUTES RATHER THAN REFUSING** (TC-5), and `join_at` is
 *  the SERVER's answer to where — a front end that hardcoded `/level-pay`
 *  would be a second map of which screens exist. */
export interface PortalLevelStandingView {
  standing: PortalLevelStanding | null;
  months: { month: string | null; paid: string | null; used: string | null; currency: string | null }[];
  join_at: string | null;
}

export async function getLevelPayStanding(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalLevelStandingView> {
  return requireData(
    await client.get<PortalLevelStandingView>(
      `/portal/accounts/${accountId}/level-pay/standing`,
    ),
  );
}


// ══ CR-068 phase 5 · lane D — CWP-040 autopay · CWP-050 fees ═══════════════
//
// ⚠ **APPENDED AT THE END, NEVER EDITED INTO A BLOCK ABOVE** — CLAUDE.md law
// 11, the same reason `apps/portal/api.py` gives: four lanes are adding to this
// file at once and a whole-file blob written over a shared literal is how one
// lane's reads silently replace another's, with a correct file count.

/** One row of `CWP-040`'s *next few* table.
 *
 * ⚠ **`amount` AND `scheduled_on` ARE BOTH NULLABLE AND THAT IS THE STORY.**
 * A `not_billed_yet` row carries neither: the amount because `US-CWP-047` TC-3
 * says ⚠ *not an estimate*, and the DATE because nothing in this product
 * answers an account's next due date before the bill is made. A screen that
 * defaulted either to `0` or to today would be inventing the figure the story
 * spends a test case forbidding. */
export interface PortalAutopaySlot {
  scheduled_on: string | null;
  /** Four decimals, as stored (hard rule 2). `null` on an unbilled month. */
  amount: string | null;
  /** Two decimals with its symbol, composed by the server. `null` likewise. */
  display: string | null;
  currency: string | null;
  /** `scheduled` · `not_billed_yet`. */
  state: string;
  fulfilled: boolean;
}

/** `GET accounts/{id}/autopay` — `CWP-040`.
 *
 * ⚠ **THERE IS NO WRITE ON THIS TYPE AND THERE IS NO WRITE ON THE EDGE.**
 * `BR-PAY-015` records an INTENT and nothing in this product can charge a
 * stored instrument, so *Turn autopay on* is a control that exists, is
 * disabled, and carries `held_reason` (`BR-CWP-056` / `CR-068` R3). A mutation
 * declared here would be the first half of a charging path.
 *
 * ⚠ **`elected` AND `enrolled` ARE DIFFERENT FACTS.** `elected` is what the
 * customer asked for and nothing un-asks it; `enrolled` is whether the account
 * may be autopaid at all, which the bounce sanction (`BR-PAY-013`) can turn
 * off without touching their election. */
export interface PortalAutopay {
  enrolled: boolean;
  elected: boolean;
  cash_only: boolean;
  /** How many payments bounced — the sanction's reason, in a figure. */
  bounces: number;
  available: boolean;
  /** `no_automatic_charge` · `cash_only`. The catalogue writes the sentence. */
  held_reason: string;
  how_much: string;
  /** ⚠ Always `null`: `accounts` has no column for a ceiling. */
  ceiling: string | null;
  /** `due_date`, always. */
  when: string;
  when_settable: boolean;
  any_scheduled: boolean;
  next_few: PortalAutopaySlot[];
  problems: { code: string }[];
}

export async function getAutopay(
  accountId: string,
  client: ApiClient = api,
): Promise<PortalAutopay> {
  return requireData(await client.get<PortalAutopay>(`/portal/accounts/${accountId}/autopay`));
}

/** One row of `CWP-050`'s fee table.
 *
 * ⚠ **A WAIVED LINE IS HERE, WITH ITS FIGURE** (`US-CWP-050` TC-3). The screen
 * strikes it through and leaves it listed, which is what lets a customer see
 * they were LET OFF rather than wonder whether they were quoted correctly. The
 * waiver's REASON is the clerk's own note and is not on the wire. */
export interface PortalFeeLine {
  what: string;
  /** `before_we_start` · `later` · `on_your_first_bill` · `not_recorded`. */
  when: string;
  amount: string;
  display: string;
  currency: string;
  waived: boolean;
  settled: boolean;
}

/** A money cell as `apps/portal/money.py` composes it — both precisions travel
 *  so the pair can be checked against hard rule 2. */
export interface PortalMoneyCell {
  kind: string;
  amount: string | null;
  display: string | null;
  currency: string | null;
}

/** `GET fees` — `CWP-050`.
 *
 * ⚠ **NO ACCOUNT ID AND NO REFERENCE GO UP.** The request is found from the
 * session's own contact facts (`BR-CWP-010`), so a stranger cannot ask what
 * `SR-26-0061` costs and the reference never enters a browser history.
 *
 * ⚠ **AND NOTHING HERE CAN EXPRESS A PART PAYMENT** (TC-6): one figure, no
 * minimum, no instalments. Fees are collected in full before work starts, and
 * a partial payment is refused by there being nothing to say it with. */
export interface PortalFees {
  any: boolean;
  /** `SR-26-0061` — a human reference, never a row id (B14 rule 31). */
  reference: string | null;
  lines: PortalFeeLine[];
  to_pay_now: PortalMoneyCell | null;
  /** ⚠ `null` when no plan prices a deposit — **never a `$0.00` cell**. */
  on_first_bill: PortalMoneyCell | null;
  available: boolean;
  held_reason: string;
  problems: { code: string }[];
}

export async function getFees(client: ApiClient = api): Promise<PortalFees> {
  return requireData(await client.get<PortalFees>(`/portal/fees`));
}

// ── CR-142-BRC07 Phase 4 · `P4.15` — the property statement ────────────────

/** One account of YOURS at one property, over a window.
 *
 *  ⚠ **THERE IS NO `customer` FIELD ON THIS TYPE AND THERE MUST NEVER BE**
 *  (`R24c`, ruled). The STAFF report draws a CUSTOMER column because a staff
 *  reader is looking across five customers at one address. In the portal every
 *  row belongs to the signed-in person by construction, and a column naming
 *  whoever holds the OTHER accounts at that address is the exact disclosure
 *  `P4.15` exists to prevent: *"the $69.60, never Unit 3's $100.00"*.
 *
 *  ⚠ **AND THE SERVER DOES NOT SEND ONE**, which is what actually makes it
 *  true — `apps/portal/premises_statement.py` never queries the other
 *  accounts, so there is nothing here for a screen state to widen. */
export interface PremisesStatementRow {
  /** The route's value; never drawn (B14 rule 31). */
  id: string;
  /** The customer's own reference, off their bill. */
  account_no: string;
  /** A unit refines a premises by LABEL (hard rule 8). `null` on the master,
   *  which hangs off the premises itself and has no unit. */
  unit_label: string | null;
  /** `R24c` marks the master row and never merges it. */
  is_master: boolean;
  /** Whether this login HOLDS the account or was invited onto it. */
  holding: "holder" | "delegate";
  /** Money, 4 decimals as sent, DISPLAYED at 2 (hard rule 2). */
  opening: string;
  charges: string;
  credits: string;
  closing: string;
}

export interface PremisesStatement extends PortalListWindow {
  from: string;
  to: string;
  /** Walked to `premises` (hard rule 8). What the reader sees instead of an id. */
  address: string | null;
  rows: PremisesStatementRow[];
  /** The WHOLE set's, never the page's (`BR-CWP-015`'s reasoning). */
  account_count: number;
  totals: { charges: string; credits: string; closing: string };
  /** ⚠ **`null` MEANS *YOU HOLD NO COMMON-AREA ACCOUNT HERE*, NOT `$0.00`**
   *  (`BR-CWP-093`). A zero would be a claim about what this building's common
   *  areas cost — a fact about the OWNER, read by a tenant. */
  common_areas: string | null;
}

/** `CWP-078` — one property, and only the accounts this login holds at it.
 *
 *  ⚠ **ADDRESSED BY AN ACCOUNT, NOT BY A PREMISES.** The server walks the
 *  account to its property (hard rule 8) — which keeps a premises uuid out of
 *  the browser's address bar (B14 rule 31) and means a caller has no id to
 *  supply that did not come out of their own session.
 *
 *  ⚠ **NEVER CACHED** (`BR-CWP-047`), for `getMyAccounts`' reason: these are
 *  live balances. */
export async function getPremisesStatement(
  accountId: string,
  window: { from: string; to: string },
  request: PortalListRequest = {},
  client: ApiClient = api,
): Promise<PremisesStatement> {
  return requireData(
    await client.get<PremisesStatement>(`/portal/accounts/${accountId}/premises-statement`, {
      query: { ...listQuery(request), from: window.from, to: window.to },
    }),
  );
}
