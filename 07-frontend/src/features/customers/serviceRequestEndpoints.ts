// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 tasks 4.10–4.13 — the SERVICE REQUEST surface.
//           Design: 04-docs/02-decisions/19-cr031-service-request-capture.md
//           (B19), screens REQ-01 list · REQ-02 detail · REQ-03.1..6 capture ·
//           REQ-03.sent confirmation. Task table: 18-cr030-onboarding-design.md
//           §W4. Contract: 04-docs/03-contracts/customers-service-request.md.
//           Screens: S83 · S84 · S85 (proposed by B18; A1 allocates none — D1)
// Rules:    BR-CUS-090 (quoted · collected · outstanding — a shortfall is an
//           OPEN BALANCE, never a refusal and never a waiver) · BR-CUS-091 (a
//           customer MAY request a disconnect; a staff-raised one needs no
//           applicant name) · BR-CUS-092 (the identifier is `ID type` + `ID
//           number`, rendered last-four — and it is REFUSED BY NAME today) ·
//           BR-CUS-093 (numbered AT CREATION — a draft carries SR-26-0048) ·
//           BR-CUS-094 (seven selectable categories + `government` LEGACY, in
//           the ruling's order) · BR-CUS-095 (the tenant checklist, shipping
//           entirely unticked) · CLAUDE.md rule 2 (4 dp stored · 2 dp shown ·
//           CHAR(3) · never a float)
// Tests:    07-frontend/src/features/customers/ServiceRequestsListPage.test.tsx
//           · ServiceRequestDetailPage.test.tsx · ServiceRequestCapturePage.test.tsx
//           · ServiceRequestDocumentSettingsPage.test.tsx
// Impacts:  06-backend/apps/customers/service_request_api.py (23 routes, live)
// ───────────────────────────────────────────────────────
//
// THE TYPED WRAPPERS FOR THE 23 ROUTES `service_request_api.py` MOUNTS.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS IS ITS OWN FILE AND NOT AN APPENDIX TO `api/endpoints.ts`
// ══════════════════════════════════════════════════════════════════════════
// The same reason `bankRecEndpoints.ts` gives in its own header: that file is
// ~6,800 lines, every lane appends to it, and on any given afternoon it holds
// two or three lanes' half-finished work. One family, one file, one lane's
// diff. Nothing here re-exports or shadows anything `endpoints.ts` publishes.
//
// ══════════════════════════════════════════════════════════════════════════
// THE TYPES ARE READ OFF `service_request_reads.py`, FIELD FOR FIELD
// ══════════════════════════════════════════════════════════════════════════
// A field the server does not send is not typed here. Three shapes are worth
// naming before they are read, because each encodes a ruling:
//
//   * **`Money` is `{amount, display, currency}` and `currency` is NULLABLE.**
//     `amount` is the stored 4-dp string, `display` the 2-dp one the server
//     already rounded (CLAUDE.md rule 2 — rounding for a human happens once,
//     server-side). A request with no fee line has no currency at all, and
//     `MoneyCell` requires one — so a caller BRANCHES rather than defaulting to
//     "USD", which would be a fabricated fact about somebody's money.
//
//   * **`*_absence` blocks are stated absences, and they name their own row.**
//     `acting_for_absence: {tracks: "DEF-638"}` is the server telling the screen
//     *this field does not exist and here is what will create it*. They are
//     rendered as a DISABLED CONTROL WITH ITS REASON (BR-SHL-025), never as a
//     page-level "what this cannot do yet" panel — the PO deleted three of those
//     from the accounts screens on 2026-08-24.
//     ⚠ **THREE OF THEM HAVE GONE, EACH ON THE DAY ITS FACT ARRIVED.**
//     `identifier_absence` on 2026-08-27 (the Social Security number);
//     `drivers_licence_absence` and `date_of_birth_absence` on 2026-09-15, on
//     the PO ruling finishing BR-CUS-092(a). A stated absence is retired in the
//     commit that makes it false — one commit later it is a screen telling a
//     clerk a field does not exist over a field that works.
//
//   * **`unavailable` rides on every DETAIL response** and is the same
//     discipline one level up: six named things this surface will not do, each
//     with a `code`, a `br_ref` and a customer-readable `detail`. The screen
//     shows the `detail` on the control it is about.
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { Paginated } from "@/api/endpoints";
import type { CustomerSearchResult } from "./customerEndpoints";
import type { TemporaryStopForRequest } from "./temporaryStopEndpoints";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated here rather than imported from `endpoints.ts` so this file adds no
 *  coupling to a file three lanes are editing — the `bankRecEndpoints` rule. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ══════════════════════════════════════════════════════════════════════════
// VOCABULARIES — mirrored from `apps/customers/models.ServiceRequest`
// ══════════════════════════════════════════════════════════════════════════

/** The eleven states. `service_request.SEGMENT_STATES` groups them. */
export const SERVICE_REQUEST_STATES = [
  "draft",
  "submitted",
  "under_review",
  "more_info",
  "approved",
  "in_fulfilment",
  "on_hold",
  "completed",
  "refused",
  "withdrawn",
  "closed",
] as const;
export type ServiceRequestState = (typeof SERVICE_REQUEST_STATES)[number];

/** REQ-01's five segments, in the order the strip draws them. */
export const SERVICE_REQUEST_SEGMENTS = [
  "all",
  "open",
  "waiting_on_customer",
  "approved",
  "closed",
] as const;
export type ServiceRequestSegment = (typeof SERVICE_REQUEST_SEGMENTS)[number];

/**
 * ✅ **FIVE OUTCOMES, AND `disconnect` IS ONE OF THEM — BR-CUS-091** (PO
 * 2026-08-24, *"Yes customer can request it"*). REQ-02's decision panel used to
 * disable it with *"only ever started by collections, never from a customer
 * request"*; that reason is WITHDRAWN and the control is enabled.
 *
 * ⚠ **What the withdrawal does NOT take with it:** a move-out CLOSES the
 * account and settles the deposit (BR-CUS-030); a disconnect leaves it OPEN AND
 * ACCRUING (BR-MET-105). Different outcomes, different child kinds, and nothing
 * on any screen may collapse one into the other.
 */
export const SERVICE_REQUEST_OUTCOMES = [
  "new_connection",
  "move_in",
  "move_out",
  "transfer",
  "disconnect",
] as const;
export type ServiceRequestOutcome = (typeof SERVICE_REQUEST_OUTCOMES)[number];

/**
 * **WHAT THE APPROVE MODAL OFFERS — TWO, NOT FIVE (PO ruling 2026-09-22).**
 *
 * PO, verbatim: *"Option (b) — remove all three permanently"*, answering a
 * lettered table that set out (a) *hide an outcome that cannot apply to this
 * request* against (b) *remove move-out, transfer and disconnect from the
 * modal for good*. So `REQ-02`'s *What kind* list is **A new connection · A
 * move-in**, on every request, not merely greyed.
 *
 * ⚠ **THIS SUPERSEDES `BR-CUS-091` IN PART, AND THE SUPERSESSION IS STATED
 * RATHER THAN ASSUMED (CLAUDE.md law 13).** That rule is CONFIRMED, was ruled
 * by the same PO on 2026-08-24 in the words *"Yes customer can request it"*,
 * and says of this exact control that the old reason for disabling Disconnect
 * *"is withdrawn and the control is enabled."* That sentence is now itself
 * withdrawn. The cost was put to the PO with two real requests before they
 * answered, so the signature covers it.
 *
 * ⚠ **AND `BR-CUS-091`'s OTHER HALF IS NOT REVERSED.** A move-out and a
 * disconnect remain DIFFERENT OUTCOMES — a move-out closes the account and
 * settles the deposit (`BR-CUS-030`), a disconnect leaves it open and accruing
 * (`BR-MET-105`) — and *"the capture form must not quietly convert one into
 * the other"*. Removing the place where that choice was made does not remove
 * the need to make it, so each has its own door and the decision log of
 * 2026-09-22 names all three: `/transfers/new`, `/disconnects/new`, and the
 * account's own `Move-out` (the move-out endpoints are account-scoped, so the
 * live control is on the account rather than on a header with no row chosen).
 *
 * ⚠ **A SEPARATE CONSTANT AND NOT A NARROWING OF `SERVICE_REQUEST_OUTCOMES`,
 * AND THAT IS THE BLAST-RADIUS ANSWER.** The five-value list is ALSO read by
 * `ServiceRequestDocumentSettingsPage`, which is the tenant's checklist of
 * which documents each REQUEST TYPE needs (`BR-CUS-095`). Cutting three values
 * out of the shared list would silently delete three columns of that grid —
 * and a utility that has ticked *proof of identity* against a move-out would
 * lose the tick with no ruling behind it. The PO removed three options from
 * ONE MODAL; the vocabulary is untouched, every stored `outcome` is still
 * lawful, and `decide_outcome` still accepts all five.
 */
export const APPROVE_OUTCOMES = ["new_connection", "move_in"] as const;

/** REQ-03.3's six property radios. The DESCRIPTION travels with the label —
 *  B19 §11.1: the review echoes *"The applicant owns and lives in it"*, so the
 *  pair is vocabulary, not decoration. */
export const PROPERTY_TYPES = [
  "standalone_owner_occupied",
  "rental_tenant_applying",
  "rental_landlord_applying",
  "multi_unit_building",
  "under_construction",
  "vacant_land",
] as const;
export type PropertyType = (typeof PROPERTY_TYPES)[number];

/**
 * `service_requests.applicant_kind` — the two values the column accepts.
 *
 * ⛔ **NO SCREEN SENDS THIS ANY MORE (CR-033, 2026-08-25), AND IT IS STILL
 * HERE ON PURPOSE.** It was REQ-03.1's `Applying as` segmented control
 * (`A person` / `A business`); the PO asked for the CUSTOMER CATEGORY in that
 * position instead and the control was replaced, not re-pointed. CR-033 §4 is
 * emphatic that the two are different facts — *"a residential account can be
 * held by a business (a landlord), and a sole trader is a person on a
 * commercial account"* — so nothing derives one from the other.
 *
 * The column, `CAPTURE_FIELDS`'s entry, the server's validation and this
 * constant all stay: a caller that knows the fact can still send it, and every
 * row written before today keeps its value. **New rows carry NULL**, which the
 * detail screen currently renders as *"Not supplied"* — a sentence that reads
 * as *the applicant did not give one* rather than *we stopped asking*. What
 * that row should say is REPORTED for a ruling, not decided here.
 */
export const APPLICANT_KINDS = ["person", "business"] as const;
export type ApplicantKind = (typeof APPLICANT_KINDS)[number];

/** REQ-03.5's `When is it being paid?` — two branches. Both are actionable now
 *  that BR-CUS-093 settled when the request exists (at creation, both times). */
export const FEE_TIMINGS = ["collect_now", "collect_later"] as const;
export type FeeTiming = (typeof FEE_TIMINGS)[number];

/**
 * REQ-03.5's `How is it being paid?` — the three TENDERS.
 *
 * ⛔ **`waive` IS OFF THIS LIST — `DEF-CUS-6415`, PO approval 2026-09-23 of the
 * step-5 fee table** (*"i like this please use this"*). It was the fourth
 * option and it waived NOTHING: choosing it stored the word `waive` in
 * `service_requests.fee_method` and marked no fee line waived, so the request
 * still owed the whole amount while the clerk believed it was waived. A waiver
 * is now what it always was on the server — a per-LINE act with a reason, the
 * `Waive` tick in the fee table (`POST …/fees/{id}/waive`). A shortfall is
 * still not a waiver (BR-CUS-090). Rows already carrying `waive` keep it
 * (hard rule 4's spirit: nothing stored is rewritten); the screen prints it
 * through the catalogue like any other method.
 */
export const FEE_METHODS = ["card", "cash", "cheque"] as const;
export type FeeMethod = (typeof FEE_METHODS)[number];

/**
 * The EIGHT checklist-eligible document types (BR-CUS-095), plus the ninth
 * `other` that is ATTACHABLE AND NEVER TICKABLE — REQ-03.4's `Anything else`.
 * Keeping the two vocabularies apart is what stops a tenant ticking a box no
 * attachment can satisfy.
 */
export const DESIGNED_DOC_TYPES = [
  "proof_of_identity",
  "proof_of_address_or_occupancy",
  "tenancy_agreement_or_deed",
  "authority_to_act",
  "site_plan_or_unit_schedule",
  "assistance_evidence",
  "signed_service_agreement",
  "completion_paperwork",
] as const;
export type DesignedDocType = (typeof DESIGNED_DOC_TYPES)[number];
export const DOC_TYPE_OTHER = "other";

/** `channel` is free text against a service-side vocabulary (the six are a
 *  DRAFT design statement, not a signed lookup). ONE value is a RULE:
 *  `staff_collections` is what makes `applicant_name` optional (BR-CUS-091). */
export const CHANNEL_STAFF_COLLECTIONS = "staff_collections";
export const CAPTURE_CHANNELS = ["customer_portal", "physical_form", "walk_in", "phone"] as const;

// ══════════════════════════════════════════════════════════════════════════
// PAYLOAD SHAPES
// ══════════════════════════════════════════════════════════════════════════

/** DRF list envelope (`core.pagination.StandardPagination`) plus the two extras
 *  `_paginated` bolts on for REQ-01. */
export interface ServiceRequestList {
  count: number;
  next: string | null;
  previous: string | null;
  results: ServiceRequestRow[];
  kpis: ServiceRequestKpis;
  segment: string;
}

/**
 * One REQ-01 row: `REQUEST · TYPE · APPLICANT · ADDRESS · RECEIVED · AGE ·
 * WAITING ON · STATE`.
 *
 * ✅ **`age_is_accented` IS SERVED — BR-CUS-106 (PO 2026-08-25, closing decision
 * D4).** This comment said *"there is no `age_is_accented`, and that is
 * deliberate on both sides"* until that ruling, and the absence was the point:
 * B18 §5.3.2 and B19 §12.1 bound the threshold only to *6–11 days* (`15d` and
 * `11d` accent, `5d` does not), B18 *proposed* 7 without authority, and a
 * screen that drew the accent would have been a lane picking the number.
 *
 * **The PO chose 7 — one week — and the boundary is INCLUSIVE.** The threshold
 * lives on the SERVER (`apps/customers/service_request.age_is_accented`) and
 * this field is its answer. ⛔ **The screen must not re-derive it from
 * `age_days`**: two thresholds is how the list and a later KPI drift apart, and
 * a rule belongs on the server (B8). `null` is a real value — a request with no
 * `received_at` has no age, and that is not the claim *"it is not old"*.
 */
export interface ServiceRequestRow {
  id: string;
  /** BR-CUS-093 — populated on every row created from 2026-08-24. A row that
   *  predates the ruling carries NULL forever; gaps are normal. */
  request_no: string | null;
  number_absence: { tracks: string } | null;
  /** ⊕ `CR-183-BRC10` — or a temporary stop / its restart ask, typed on arrival. */
  type: ServiceRequestOutcome | "temporary_stop" | "restart_now" | null;
  type_absence: { reason: string } | null;
  applicant: string | null;
  address: string | null;
  address_unit: string | null;
  received_at: string | null;
  /** `BR-CWP-076` — where the work came from. Free text against a service-side
   *  vocabulary; the screen translates a KNOWN value and prints an unknown one
   *  as it stands. `customer_portal` is the value the portal writes, and until
   *  2026-09-04 nothing in this product had ever written any value at all. */
  channel: string | null;
  age_days: number | null;
  /** BR-CUS-106 — the SERVER's answer at 7 days or more, inclusive. `null`
   *  where `age_days` is null. Never re-derived here. */
  age_is_accented: boolean | null;
  waiting_on: string | null;
  state: ServiceRequestState | string;
}

export interface ServiceRequestKpis {
  open: number;
  waiting_on_customer: number;
  oldest_waiting: { days: number | null; request_no: string | null; waiting_on: string | null };
  approved_not_started: number;
  refused_this_month: number;
  /** Named rather than hidden: a month boundary is a tenant-timezone fact and
   *  this uses the server's. No rule states which clock a KPI window reads. */
  period_basis: string;
}

/**
 * A money figure the way `service_request_reads._money` builds it.
 *
 * `amount` is stored precision (4 dp). `display` is the SERVER's 2-dp rounding
 * — CLAUDE.md rule 2 says rounding for a human happens once, and this is where.
 * `currency` is `CHAR(3)` **or null**, and null is a real answer: a request
 * with no fee line has no currency, so a caller branches instead of inventing
 * one.
 */
export interface Money {
  amount: string;
  display: string;
  currency: string | null;
}

export interface ServiceRequestUnavailable {
  code: string;
  br_ref: string;
  detail: string;
}

export interface ServiceRequestHeader {
  id: string;
  request_no: string | null;
  number_absence: { tracks: string } | null;
  state: ServiceRequestState | string;
  /** `NOT YET CLASSIFIED` — the chip beside the state. */
  classification: string;
  applicant: string | null;
  address_as_given: string | null;
  /** The blueprint draws the head's address line in full — `212 Balcones Drive
   *  · Unit 3 · Austin, TX 78704` (p082). TWO different facts make it and they
   *  arrive as two: what the applicant typed, and the matched premises' own
   *  locality. Never compose them on the server — see `PremiseLocality`. */
  address_unit_as_given: string | null;
  premise_locality: PremiseLocality | null;
  lookup_found: string | null;
  received_at: string | null;
  received_by: string | null;
  channel: string | null;
  waiting_on: string | null;
  waiting_since: string | null;
  requested_start: string | null;
  /**
   * The register tab this request's work landed on, `null` until it is
   * APPROVED — `request_jobs.JOB_SHAPES[outcome]["queue"]`, served rather than
   * copied. It is the BACKEND's vocabulary (`move_ins`), not the tab slug
   * (`move-ins`); `requestBackDestination` turns one into the other and
   * refuses a queue `ACCOUNTS_TAB_IDS` does not know.
   */
  queue: string | null;
  /**
   * ⊕ **`DEF-CUS-6350` — WHERE IT WENT.** The job this APPROVED request raised,
   * named by its NUMBER (`MVI-26-0115`, `CON-26-0131`) — `null` until approved
   * and for an outcome that raises no job. Read back through the link on every
   * call, so a page opened next week says what the approval said. `id` is for
   * acting (reopening a draft build) and is never printed (B14 rule 31);
   * `number` is `null` where the tenant keeps no series.
   */
  job?: ServiceRequestHeaderJob | null;
}

export interface ServiceRequestHeaderJob {
  kind: "move_in" | "connection" | string;
  id: string | null;
  number: string | null;
  state: string | null;
}

export interface ServiceRequestActions {
  available: string[];
  can_approve: boolean;
  /** The condition keys blocking approval, or `["outcome"]` when nothing has
   *  been decided. A blocked approval is a REASON, never a hidden button:
   *  *"Nothing is refused — it simply cannot be approved yet."* */
  approve_blocked_by: string[];
  can_park: boolean;
}

/** Lane CF-1 — one co-applicant card as a request serves it back. */
export interface ServiceRequestCoApplicant {
  full_name: string;
  relationship: string | null;
  phone: string | null;
  email: string | null;
  contact_by: string | null;
  date_of_birth: string | null;
  responsible_for_bills: boolean;
  ssn_last4: string | null;
  driving_licence_last4: string | null;
}

export interface ServiceRequestApplicant {
  name: string | null;
  phone: string | null;
  email: string | null;
  language: string | null;
  person_or_company: ApplicantKind | string | null;
  /** ⚠ **THE SECOND AXIS, AND A LIVE WRITE THAT LOST ITS READ TWICE**
   *  (`DEF-CUS-5903`). `set_customer_category` has written
   *  `account_type_id` / `account_subtype_id` since W4. The read was added on
   *  2026-08-25 precisely because the column was a write nothing served — and
   *  the 2026-09-19 Applicant-tab rebuild dropped the ROW again, so the server
   *  went on serving it and no screen gave it back.
   *
   *  `person_or_company` is the LEGAL-PERSON axis and this is the ACCOUNT
   *  CATEGORY axis (B19 §14.3): one legal person, one place or use, both true
   *  at once, which is why they are neighbours on screen.
   *
   *  ⚠ The `id` is declared and is NEVER the visible value — B14 rule 31. The
   *  screen prints `name`. */
  customer_category?: {
    account_type: { id: string; code: string; name: string; legacy?: boolean } | null;
    account_subtype: { id: string; code: string; name: string } | null;
    not_yet_categorised: boolean;
  };
  co_applicant: { name: string | null; email: string | null; phone: string | null };
  /** Lane CF-1 (2026-10-18) — the full co-applicant cards, each identifier as
   *  its LAST FOUR only. Optional: a cached detail may predate it. */
  co_applicants?: ServiceRequestCoApplicant[];
  /** Lane CF-1 — Move-in's *Contact by*. */
  contact_by?: string | null;
  /** Lane CF-1 — the government ID's last four (BR-CUS-045). */
  gov_id_last4?: string | null;
  /** Lane CF-1 — the request's Preferences (no autopay on a request). */
  preferences?: { paperless: boolean; sms_reminders: boolean };
  /** Lane CF-1 — where the bill goes, under its one name (falls back on the
   *  server to the older `billing_*` parts). */
  mailing_address?: {
    same: boolean;
    line1: string | null;
    line2: string | null;
    city: string | null;
    state: string | null;
    postal_code: string | null;
  };
  /** ⊕ `DEF-CUS-10251` — a portal request with no category yet: Approve is
   *  held with *Set the category first.* until staff set it. */
  category_to_be_set?: boolean;
  /** ✅ **BR-CUS-092(c) — LAST FOUR ONLY, PROJECTED ON THE SERVER.** PO ruling
   *  2026-08-27 closing DEF-632: *"We need to capture SSN and encript it; we
   *  have to ensure it is working"*.
   *
   *  ⚠ **THERE IS NO `ssn` ON THIS TYPE AND THERE MUST NEVER BE.** The full
   *  number is not withheld from the SCREEN, it is withheld from the PAYLOAD —
   *  a value that reaches the browser is in devtools, in a proxy log and in the
   *  HAR file somebody attaches to a support ticket, however the screen chooses
   *  to draw it. `crypto.last_four()` runs server-side and this is all it emits.
   *
   *  Every `*_stored_encrypted` is a fact about THIS ROW, not a constant, so a
   *  screen cannot print the claim over a blank column.
   *
   *  ⚠ **`stored_encrypted` IS THE SSN's, AND ITS NAME DOES NOT SAY SO.** It
   *  predates the licence by three weeks; the licence has its own explicit flag
   *  below. Read the explicit one when you mean the licence. */
  identifier: {
    ssn_last4: string | null;
    ssn_present: boolean;
    stored_encrypted: boolean;
    /** BR-CUS-092(a) FINISHED — PO ruling 2026-09-15, *"ensure user is able to
     *  inputs both these on step 1 - Date of birth and driver's licence on step
     *  1"*. Same projection and same reason as the SSN above: the last four is
     *  all the server emits, and there is no full value on this type. */
    drivers_licence_last4: string | null;
    drivers_licence_present: boolean;
    drivers_licence_stored_encrypted: boolean;
    /** `DEF-CWP-9045` — a business's Tax ID as typed on its portal
     *  application, LAST FOUR only, read from the draft where it is stored
     *  once (`OQ-CWP-1560` (b)). Optional: a cached detail may predate it. */
    tax_id_last4?: string | null;
    tax_id_present?: boolean;
  };
  /** The applicant's date of birth, `YYYY-MM-DD`, served IN FULL and NOT under
   *  `identifier` — `BR-CUS-1020`: *"`BR-CUS-092` names two identifiers of which
   *  it is not one"*. It is the middle clause of BR-CUS-089's
   *  *name + date of birth + one government ID*, so it has to be comparable. */
  date_of_birth: string | null;
  /** `DEF-CWP-9163` — where a PORTAL applicant asked for the bill to go, as
   *  typed on *Mailing address, if different*; read from the application,
   *  where it is stored once. `null` = the bill goes to the service address
   *  (or the request did not come from the portal). Optional: a cached detail
   *  may predate it. On the account it becomes ONE `kind='mailing'` row. */
  application_mailing_address?: {
    line1: string | null;
    line2: string | null;
    city: string | null;
    state: string | null;
    postal_code: string | null;
  } | null;
  acting_for_absence: { tracks: string };
  customer_match: {
    customer_id: string | null;
    /** `DEF-CUS-9043` — WHO, by the tenant's own number and name (never the
     *  id, B14 rule 31). Null with `confirmed_at` set is *searched, none on
     *  file*. Optional: a cached detail may predate it. */
    customer_no?: string | null;
    display_name?: string | null;
    tier: string | null;
    basis: string | null;
    confirmed_at: string | null;
    /** BR-CUS-089 — only a STRONG match may move money. */
    may_move_money: boolean;
  };
}

export interface ServiceRequestServiceRow {
  code: string;
  requested_start: string | null;
  /** NULL is *not yet asked* — REQ-03.3's CHECK callout. Never spelled the same
   *  way as *no*. */
  available: boolean | null;
}

/** The town, the state and the postcode of the MATCHED PREMISES, walked to —
 *  never three columns on the request.
 *
 *  PO ruling 2026-09-15, verbatim: *"if we have unit or street address then we
 *  should take it from premises/Unit - it means its a search and if not foudn
 *  them alow user to add them"*. That is CLAUDE.md hard rule 8 applied to this
 *  screen: an address is stored on `premises` and everything else derives it.
 *
 *  ⚠ **THE SCREEN WRITES THE SENTENCE, THE SERVER NEVER DOES.** The blueprint
 *  punctuates the same line two ways on two frames — `Austin TX 78704` on p083,
 *  `Austin, TX 78704` on p082 — so the punctuation is an illustration (B14 rule
 *  37) and the three parts travel separately.
 *
 *  `null` where the address has not resolved to a premises, which is a real
 *  state: a connection at a field with nothing on record is the job the capture
 *  wizard exists for. Say so; never draw a blank town. */
export interface PremiseLocality {
  city: string | null;
  state: string | null;
  postal_code: string | null;
}

export interface ServiceRequestLocation {
  address_as_given: string | null;
  address_unit_as_given: string | null;
  /** **THE PARTS THE APPLICANT GAVE — PO ruling 2026-09-22**, verbatim:
   *  *"correct address will be on presmies but first time you will ahve to
   *  take the details to match it"*.
   *
   *  ⚠ **THEY ARE FOR MATCHING AND THEY ARE NOT THE SERVICE ADDRESS.** A
   *  request that cannot take a city and a ZIP cannot find the premises it is
   *  about. Once a premises is matched, `resolved_premise_address` and
   *  `premise_locality` are what a screen shows — that clause is part of the
   *  ruling. `BR-MET-1161` is NOT narrowed: an address is still stored on
   *  `premises` and nowhere else, and these are a record of a STATEMENT, the
   *  same posture `address_as_given` and `interruptions.location_text` have.
   *
   *  `null` on every request written before 2026-09-22 — nothing back-fills
   *  them and nothing could, because splitting a town out of one free-text
   *  line is a guess. */
  address_city_as_given: string | null;
  address_state_as_given: string | null;
  address_postal_code_as_given: string | null;
  /** `How many units are on this property?` — what the APPLICANT says is there
   *  (p077), printed as `Units on the property · 6` (p082). A claim, not a
   *  count: the register may agree with it or not. `null` is *not supplied* and
   *  must never render as `0`. */
  units_on_property: number | null;
  billing_address_same: boolean;
  /** ⚠ The ONE-BOX billing address every request captured before 2026-09-23
   *  holds, served exactly as typed and never parsed (`DEF-CUS-6408`,
   *  `DEF-2703`). A screen shows it only where the parts below are empty. */
  billing_address_as_given: string | null;
  /** ✅ **Where the bill goes, in parts, as the applicant gave it** — PO report
   *  2026-09-23, *"full address line, unit, city, zip … how address taken in
   *  USA"* (`DEF-CUS-6408`). The screen writes the line; the server composes
   *  nothing. `state` is a two-letter code. `null` on every older request. */
  billing_line1_as_given: string | null;
  billing_line2_as_given: string | null;
  billing_city_as_given: string | null;
  billing_state_as_given: string | null;
  billing_postal_code_as_given: string | null;
  resolved_premises_id: string | null;
  resolved_unit_id: string | null;
  /** `BR-CUS-1114` — live units the resolved premises holds (metering's count,
   *  not `units_on_property`, the applicant's claim). Optional: older payloads
   *  and hand-built fixtures omit it; `null` = no premises resolved. */
  resolved_premises_units?: number | null;
  /** `CR-162-BRC10` — the server's own answer: may this address have an
   *  owner's master account (premises type's *Account type*)? */
  resolved_premises_master_allowed?: boolean | null;
  /** ⛔ **DRAW THESE, NOT THE IDS ABOVE — `DEF-CUS-5386`, B14 rule 31** (PO,
   *  2026-08-31: *"no Databse ID on screen - that is a rule"*). The blueprint
   *  names the match twice on p083: `Matched premises PR-0731 · exact` and
   *  `Matched unit U-001884 · exact`. The drawn numbers are ILLUSTRATIONS (B14
   *  rule 37) — ours look like `P-00052` and `SCW-U-207`.
   *
   *  Either NUMBER can be `null` while its id is not, because both columns are
   *  nullable on a tenant that never turned its numbering series on. Fall back
   *  to `resolved_premise_address`, and to a stated absence — **never to the
   *  id**, which is the defect coming straight back. The ids stay in the
   *  payload for links and for `title=` (`DEF-2716`'s proved fix). */
  resolved_premises_no: string | null;
  resolved_unit_no: string | null;
  /** `DEF-CUS-10705` — the matched unit's LABEL (`B`, `Unit 3`), a refinement
   *  of the premises by label (hard rule 8). The request head draws it after
   *  the street at a building with several units (p082 `· Unit 3 ·`).
   *  Optional: older payloads and hand-built fixtures omit it. */
  resolved_unit_label?: string | null;
  resolved_premise_address: string | null;
  premise_locality: PremiseLocality | null;
  /** How the match was made — `"exact_reference"` or `null` when nothing
   *  matched. The word the blueprint prints after each number. Render it
   *  through the catalogue, the way `resolution_kind` already is. */
  resolved_match: string | null;
  resolution_kind: string;
  /** STORED, not recomputed (B19 §7) — the sentence the decision was made on. */
  lookup_found: string | null;
  plot_or_parcel: string | null;
  what_is_being_built: string | null;
  property_type: PropertyType | string | null;
  no_premise_flag: boolean;
  services: ServiceRequestServiceRow[];
  /** ✅ **BR-CUS-1070 — three FACTS about the per-service starts, derived once
   *  on the server.** Step 6's review block draws `Requested start → 05/12/2026,
   *  all three` when they agree and lists them when they do not; the request
   *  detail draws the same fact. Deciding what *agree* means on the screen would
   *  let two screens decide it differently, so it is decided in the payload and
   *  the WORDING stays the screen's (B14 rule 33 caps a fact at six words).
   *
   *  `agreed` is the one ISO date when EVERY service carries the same non-null
   *  date, else `null`. `unset` is how many carry none — which is what separates
   *  *nobody gave a date* (`agreed` null, `unset` === `count`) from *they
   *  disagree* (`agreed` null, `unset` 0). A `count` of 0 is a real answer: a
   *  request that has not reached step 2. */
  requested_start_agreement: { count: number; agreed: string | null; unset: number };
  evidence: { premise_exists: boolean; unit_is_served: boolean; unit_is_vacant: boolean };
}

export interface ServiceRequestDocument {
  id: string;
  doc_type: string;
  what_it_proves: string | null;
  /** **`DOCUMENT NUMBER` — the number ON the paper (PO ruling 2026-09-22).**
   *
   *  ⚠ **SERVED WHOLE, SHOWN AS FOUR.** The PO ruled *"Yes, last four only"*
   *  about what reaches a LIST; a clerk correcting a typo has to see what is
   *  stored, and a server that masked it would make the field unwritable by
   *  the form that owns it. So every SCREEN puts it through `maskLastFour`
   *  and none of them prints it whole — `BR-CUS-092(c)`'s posture, applied to
   *  a column the rule does not name because the column did not exist.
   *
   *  `null` on every row written before 2026-09-22: nothing back-fills it and
   *  nothing could, because the digits some of those rows carry sit in
   *  `what_it_proves` beside words, and telling the two apart is a guess. */
  document_number: string | null;
  name: string | null;
  uploaded_at: string | null;
  /** The uploader's user id. ⚠ **NEVER RENDERED — B14 rule 31.** The visible
   *  value is `uploaded_by_name`; this is here because the payload carries it
   *  and a field a screen must not print is better typed than invisible. */
  uploaded_by: string | null;
  /** Who attached it, as a person. `null` for a seeded or process-written row,
   *  and the SCREEN chooses what an absence looks like (p078 draws an em dash). */
  uploaded_by_name: string | null;
  /** ⊕ `DEF-CUS-9834` — `applicant` when the portal stored the file: the
   *  applicant brought it, and the table says *Kyle Mark (applicant)*. */
  uploaded_by_role?: "applicant" | null;
  /** What is on disk. `null` on a row that records an expectation rather than a
   *  file, and — on the beta's six seeded rows — on a row whose `storage_ref`
   *  points at nothing (`DEF-CUS-5872`). */
  size_bytes: number | null;
  /** What the clerk chose, written ONLY when `core.document_shrink` losslessly
   *  re-deflated it on the way in. `null` means *stored exactly as it arrived*,
   *  not *unknown* — so the pair is shown only when this is set. */
  original_size_bytes: number | null;
  /** ⚠ **`attached` ANSWERS "IS THE COLUMN SET"; `file_present` ANSWERS "IS
   *  THERE A FILE", AND THEY DISAGREE ON SIX LIVE ROWS (`DEF-CUS-5872`).** Every
   *  screen that decides whether a file can be read must use `file_present`;
   *  `attached` survives because a live count is derived from it. */
  attached: boolean;
  file_present: boolean;
  /** `CR-158-BRC10` — what the store recorded the BYTES to be, `null` with no
   *  file. Optional: a payload from before the change omits it. */
  content_type?: string | null;
  required: boolean;
  verification_state: "not_checked" | "verified" | "rejected" | string;
  verified_at: string | null;
  reject_reason: string | null;
}

export interface ServiceRequestDocumentsTab {
  documents: ServiceRequestDocument[];
  verified: number;
  attached: number;
  /** THE TWO GATES, served as two fields so a screen cannot conflate them:
   *  attaching never blocks CREATION; an unverified required document blocks
   *  APPROVAL (B19 §5 + BR-CUS-095). */
  blocks_creation: boolean;
  /** ⚠ **ALWAYS FALSE SINCE 2026-09-16 — PO, *"lets not make it mandetory"*.**
   *  Kept so a reader meets the ruling rather than the absence of a field; what
   *  the screen asks now is `outstanding`. */
  blocks_approval: boolean;
  /** Something about the documents is not settled — the sentence the clerk
   *  reads, and no longer a gate. */
  outstanding: boolean;
  checklist_request_type: string | null;
  /** BR-CUS-095 — what the TENANT ticked for this request's job type. An empty
   *  array is the SHIPPED state and is not an absence: *"a utility that
   *  configures nothing blocks nothing."* */
  checklist_required: string[];
  checklist_unmet: string[];
}

export interface ServiceRequestFeeLine {
  /** ⚠ **THE ROW'S PRIMARY KEY, AND THE ONLY THING `waiveServiceRequestFee`
   *  MAY BE HANDED — `DEF-CUS-6096`.** Until 2026-09-21 this payload carried
   *  `line_no` alone, so the waive row action sent `String(line.line_no)`; the
   *  endpoint looks the row up by uuid, `"1"` is not one, and every press was a
   *  500 the screen swallowed. `line_no` below is what a CLERK reads. This is
   *  what an ENDPOINT is addressed with. They are not interchangeable. */
  id: string;
  line_no: number;
  charge_code: string | null;
  description: string | null;
  basis: string | null;
  quantity: string;
  unit_amount: Money;
  amount: Money;
  waived: boolean;
  /** The stored reason — a Settings CODE such as `BILLERR`. Sent back, never
   *  printed (B14 rule 31). */
  waive_reason: string | null;
  /** What a clerk reads: the utility's own name for that code — *Billing error
   *  correction* — or the words as typed when the reason is not a code
   *  (`DEF-CUS-6423`). */
  waive_reason_name?: string | null;
  settled_at: string | null;
  invoice_ref: string | null;
}

export interface ServiceRequestFeesTab {
  lines: ServiceRequestFeeLine[];
  outstanding_lines: number;
  /** BR-CUS-090's four figures. **Worked, from the ruling:** quoted $130.00,
   *  collected $25.00, receipt `RCP-26-4471` → outstanding $105.00. */
  quoted: Money;
  /** The sum of the WAIVED lines. `quoted` sums the unwaived ones, so after a
   *  waive it reads 0.00 and cannot say what was waived (`DEF-CUS-6423`). */
  waived?: Money;
  settled: Money;
  collected: Money;
  outstanding: Money;
  /** ⚠ A SHORTFALL IS NOT A WAIVER AND NOT A REFUSAL — served so a screen
   *  cannot draw it as either. */
  shortfall_is_open_balance: boolean;
  receipt_no: string | null;
  collected_at: string | null;
  quoted_at_collection: Money | null;
  fee_timing: FeeTiming | string | null;
  fee_due_by: string | null;
  fee_method: string | null;
  /** True once money taken at the counter has posted `DR 1010 · CR 2400`
   *  (derived from that journal entry, `DEF-CUS-6381`); False for a quote
   *  nobody has paid. */
  posts_to_ledger: boolean;
  connection_quote: { raised: boolean; reason: string };
}

export interface OutcomeVerdict {
  outcome: ServiceRequestOutcome | string;
  verdict: "fits_the_evidence" | "not_possible" | "possible" | string;
  /** The catalogue key of the PO's own sentence. `possible` carries none —
   *  *the evidence neither fits nor rules this out* is **OQ-356**, and an
   *  invented sentence there would be resolving an open question. */
  message_key: string | null;
}

export interface ConditionRow {
  key: string;
  state: "clear" | "blocked" | "unknown" | "noted" | string;
  blocking: boolean;
  message_key: string | null;
  params: Record<string, unknown>;
}

export interface ConditionsSummary {
  clear: number;
  /** ⚠ **FOUR, NOT THE FIVE THE SCREENSHOT PRINTS.** The design draws *"4 of 5
   *  conditions clear"* and only four can be named — **OQ-355**. The server
   *  serves 4 with the gap stated rather than claiming a fifth it cannot
   *  itemise, and the screen prints what the server serves. */
  total: number;
  blocking: string[];
  conditions: ConditionRow[];
  count_differs_from_design: { designed_total: number; served_total: number; tracks: string };
}

/**
 * ⚠ **`then` AND `what` ARE CATALOGUE KEYS, NEVER SENTENCES** — the 2026-08-19
 * ruling that server text never reaches a screen (G32/G33). The wave-1 lane
 * that published this said so in its own record: *"the words are the
 * catalogue's and wave 2 mints them"*. `absence.detail` is the platform's own
 * long-form reason and belongs in the register, **not on the modal** (B14 rule
 * 33 — rationale is zero words on screen).
 */
export interface ApprovalPreviewRow {
  /** `now` · `next` · `not_now` — the drawn left column (p084). */
  then: string;
  what: string;
  queue?: string | null;
  kind?: string | null;
  absence?: { code: string; br_ref?: string | null; detail?: string | null } | null;
}

/** `GET /service-requests/{id}/approval-preview?outcome=…`, and the same shape
 *  under `decision.what_approving_will_do[<outcome>]` so the Approve modal
 *  redraws as a radio moves **with no round trip**. The screen RENDERS this and
 *  computes nothing: a screen that worked out *"a build is raised"* would be a
 *  second implementation of the rule. */
export interface ApprovalPreview {
  outcome: string | null;
  known: boolean;
  creates: {
    kind: string;
    table: string | null;
    module: string;
    queue: string;
    state_it_lands_in: string | null;
    raises_a_row: boolean;
    absence?: { code: string; br_ref?: string | null; detail?: string | null } | null;
    blockers: { code: string; br_ref?: string | null; detail?: string | null }[];
  } | null;
  carries: {
    request_no: string | null;
    applicant: string | null;
    requested_start: string | null;
    services: string[];
    money: {
      outstanding: Money;
      quoted: Money;
      collected: Money;
      gates_approval: boolean;
    };
  } | null;
  rows: ApprovalPreviewRow[];
  not_now?: string[];
  /**
   * ⊕ **`DEF-CUS-6352` — THE APPROVE WINDOW'S TWO LINES AND ITS BUTTON, PER
   * KIND, CHOSEN ON THE SERVER** from `request_jobs.JOB_SHAPES`, the one table
   * of what each outcome creates. Catalogue KEYS, never sentences. `null` for
   * an outcome the window does not offer — never the build's wording.
   */
  window?: { submit: string; lines: string[] } | null;
  /**
   * ⚠ **THIS OUTCOME'S OWN CONDITIONS — `DEF-CUS-5427`.** `actions
   * .approve_blocked_by` is computed from the STORED outcome and therefore
   * cannot move with a radio, and the document checklist is keyed ON the
   * outcome — so a request with nothing decided reports every condition clear
   * over a pick that is about to refuse. This is the same four conditions
   * answered as if this option were the pick.
   *
   * `blocking` greys the commit. `outstanding` is *told, not refused* — the
   * PO's *"show the messge documents will be required"*, which is what
   * replaced the document gate when it stopped gating.
   */
  conditions?: ApprovalConditions;
}

/** `service_request.conditions_summary`, as served. ⚠ `blocking` and
 *  `outstanding` are DISJOINT and neither holds a clear condition: a key in
 *  neither list is satisfied, and a key cannot be in both. */
export interface ApprovalConditions {
  clear: number;
  total: number;
  /** Keys that REFUSE the press. */
  blocking: string[];
  /** Keys that are not satisfied and do not refuse — the notice, not the gate. */
  outstanding: string[];
  conditions: {
    key: string;
    state: string;
    blocking: boolean;
    /** ⚠ A CATALOGUE KEY, never a sentence — the server sends no clerk-facing
     *  text (the 2026-08-19 ruling, G32/G33). */
    message_key: string | null;
    params: Record<string, unknown>;
  }[];
}

/** What `POST .../approve` created, or why it created nothing. **EITHER
 *  `raised` OR `not_raised`, never both and never neither** — so a screen
 *  cannot draw a job that does not exist. */
export interface ServiceRequestJob {
  raised?: {
    kind: string;
    table: string;
    module: string;
    queue: string;
    id: string;
    ref: string | null;
    /** ⊕ `DEF-CUS-6350` — a move-in job's own `MVI-` number, or `null` where
     *  the tenant keeps no series. Absent for every other kind. */
    move_no?: string | null;
    state: string;
    names_this_request: boolean;
    warnings: string[];
  };
  not_raised?: { code: string; br_ref?: string | null; detail?: string | null };
}

/** What `POST .../refuse` and `POST .../transitions{action:request_info}` say
 *  about the letter. **`sent` is `false` on every path** — no adapter delivers
 *  anything in this product (BR-NOT-013) — so the screen says *queued*, never
 *  *sent*, and `reason` is why nothing was queued when nothing was. */
export interface ApplicantMessage {
  occasion: string;
  state: string;
  reason: string | null;
  ref: string | null;
  sent: boolean;
  address: string | null;
  template_code: string | null;
  detail: string | null;
  problems: unknown[];
}

export interface ServiceRequestDecisionTab {
  what_they_said: string | null;
  what_the_lookup_found: string | null;
  options: OutcomeVerdict[];
  /** *"Nothing is preselected. Approving creates real service and real charges,
   *  so the decision is made deliberately."* */
  preselected: null;
  undrawn_verdict_absence: { tracks: string };
  conditions: ConditionsSummary;
  commit: {
    outcome: ServiceRequestOutcome | string | null;
    decided_by: string | null;
    decided_at: string | null;
    decided_against_evidence: boolean;
    outcome_kind: string | null;
    outcome_ref: string | null;
  };
  disconnect_is_not_a_move_out: { rule: string; move_out: string; disconnect: string };
  /** The Refuse dialog, read back. ⚠ **`reason_code` IS A CODE** — render it
   *  through `customers.serviceRequest.refuseReason.*` and never print it
   *  (B14 rule 31). `message` is the letter's body, the only one of the three
   *  an applicant ever reads. */
  refusal: { reason_code: string | null; reason: string | null; message: string | null };
  /** The Ask-for-more dialog, read back. `needed` is a list of CODES from the
   *  server's `INFO_NEEDED_KINDS`, in the drawing's own order. */
  more_info: { needed: string[]; message: string | null };
  /** One preview per outcome, KEYED BY OUTCOME. */
  what_approving_will_do: Record<string, ApprovalPreview>;
  acknowledgement: {
    state: string | null;
    reason: string | null;
    ref: string | null;
    /** BR-CUS-079 — never a fabricated `sent`. */
    sent: boolean;
    /** BR-CUS-090 clause (3): the acknowledgement may not print *"Nothing is
     *  charged"* over a panel confirming cash was taken. */
    fee_statement: unknown;
  };
}

export interface ServiceRequestEvent {
  id: string;
  at: string;
  /** The acting user's id. ⚠ **NEVER RENDERED — B14 rule 31.** The visible
   *  value is `actor_name`; this stays because support reads it and the portal
   *  seam projects from the same rows. */
  actor: string | null;
  /** Who acted, as a person — the blueprint's `WHO` column (p083). `null` for a
   *  row written by a background job or planted by the sample seed, and the
   *  SCREEN chooses what an absence looks like (the drawing prints a dash). */
  actor_name: string | null;
  /** `DEF-CUS-9091` — who acted, as a kind: a clerk, the applicant through the
   *  portal, or nobody signed in. Optional so a payload from before it reads
   *  as it always did. For `customer`, `actor_name` is the applicant's name. */
  actor_kind?: "staff" | "customer" | "system";
  kind: string;
  from_state: string | null;
  to_state: string | null;
  note: string | null;
  note_type: string | null;
  internal: boolean;
}

export interface ServiceRequestDetail {
  header: ServiceRequestHeader;
  actions: ServiceRequestActions;
  applicant: ServiceRequestApplicant;
  location_and_services: ServiceRequestLocation;
  documents: ServiceRequestDocumentsTab;
  fees: ServiceRequestFeesTab;
  decision: ServiceRequestDecisionTab;
  history: ServiceRequestEvent[];
  /** Present on every DETAIL response (`_detail`), absent from the 201 the
   *  create returns — which is why it is optional here. */
  unavailable?: ServiceRequestUnavailable[];
  /** Only on the `approve` response. */
  job?: ServiceRequestJob;
  /** Only on the `refuse` and `transitions` responses. */
  applicant_message?: ApplicantMessage | null;
  /**
   * **`What the customer is told` — REQ-03 step 4's card.** On the DETAIL and
   * not on a route of its own, by the server's own reasoning: the review
   * already reads this payload, and a second call would make the card's rows
   * and the fee figures they quote two reads that can disagree.
   *
   * Optional because the 201 the create returns is not a detail.
   */
  told_on_submit?: ToldOnSubmitCard;
  /** `CR-161-BRC10` W6 — the request's own copy of the utility's fields
   *  (gap 2). Optional because the 201 the create returns is not a detail. */
  custom_data?: RequestCustomData;
  /** `CR-161-BRC10` W6 — what approving does with each answer (gap 3 / R5). */
  custom_field_copy?: RequestCustomFieldCopyBlock[];
  /** `CR-183-BRC10` — the temporary stop this request asks for, or the hold
   *  its *Restart now* would end. `null` on every other request. */
  temporary_stop?: TemporaryStopForRequest | null;
}

/**
 * `GET /service-requests/categories` — BR-CUS-094's two lists.
 *
 * ⚠ **`selectable` ARRIVES IN THE RULING'S ORDER AND IS RENDERED IN IT.**
 * Residential · Commercial · Industrial · Agricultural · Institutional ·
 * Municipal · Builder or developer. A picker that sorted alphabetically would
 * put Agricultural first and silently re-order a screen the PO drew.
 */
export interface ServiceRequestCategories {
  selectable: { code: string; name: string }[];
  /** `government` — **unselectable on new records and lawful everywhere else**.
   *  Still a valid FK, still filterable, still priceable. Never re-labelled by
   *  guess: Municipal and Institutional are both plausible readings and the
   *  stored value cannot tell a city water department from a state university. */
  legacy: { code: string; name: string; br_ref: string; why: string }[];
}

export interface DocumentRequirementCell {
  request_type: string;
  doc_type: string;
  required: boolean;
  /** `false` = *nobody has looked*; `required:false, configured:true` = *we said
   *  no*. Two different facts and the screen tells them apart. */
  configured: boolean;
  updated_at: string | null;
}

export interface DocumentRequirementsGrid {
  requirements: DocumentRequirementCell[];
  /** BR-CUS-095's sharpest clause, served: the table ships EMPTY. */
  ships_unticked: boolean;
  br_ref: string;
}

/** What `POST .../submit` answers. Idempotent — BR-CUS-093 consequence (e). */
export interface SubmitResult {
  request: ServiceRequestRow;
  acknowledgement: unknown;
  idempotent_replay: boolean;
}

/** The capture fields `_clean_capture` accepts. **Anything else is refused by
 *  name**, and the remaining identifier field names are refused LOUDLY rather
 *  than dropped (BR-CUS-092) — a silently dropped identifier is a screen that
 *  says *"stored encrypted"* over a column that does not exist. `ssn` is the one
 *  that now lands in a column, encrypted (DEF-632, PO 2026-08-27). */
/** `CR-161-BRC10` W6 — the three record types a service request carries the
 *  utility's own fields for, in the order the screens list them. */
export const REQUEST_CUSTOM_ENTITIES = ["customers", "accounts", "premises"] as const;
export type RequestCustomEntity = (typeof REQUEST_CUSTOM_ENTITIES)[number];
/** The request's own copy: one blob per record type, keyed by field key. */
export type RequestCustomData = Partial<Record<RequestCustomEntity, Record<string, unknown>>>;

/** One answer on the Approve review — `request_custom_fields.copy_preview`. */
export interface RequestCustomFieldCopyRow {
  key: string;
  /** The tenant's own label — data, not platform copy. */
  label: string;
  data_type: string;
  requested: unknown;
  existing: unknown;
  /** `copy` nothing held · `conflict` held differently · `same` · `no_target`. */
  state: "copy" | "conflict" | "same" | "no_target";
  default_pick: "existing" | "requested" | null;
}
export interface RequestCustomFieldCopyBlock {
  entity: RequestCustomEntity;
  /** The record it goes to, by NUMBER (B14 rule 31); `null` = none yet. */
  target: { label: string } | null;
  rows: RequestCustomFieldCopyRow[];
}
/** R5's pick, per conflicting answer. Absent = keep the existing value. */
export type RequestCustomFieldPicks = Partial<
  Record<RequestCustomEntity, Record<string, "existing" | "requested">>
>;

export interface CapturePayload {
  channel?: string;
  /** `CR-161-BRC10` W6 — only what changed, per record type. */
  custom_data?: RequestCustomData;
  /** PO ruling 2026-09-22 — see `ServiceRequestLocation`. What the applicant
   *  said, sent so the request can be MATCHED to a premises. */
  address_city_as_given?: string;
  address_state_as_given?: string;
  address_postal_code_as_given?: string;
  applicant_kind?: ApplicantKind;
  applicant_name?: string;
  applicant_email?: string;
  applicant_phone?: string;
  /** ✅ **BR-CUS-092(a)/(b) — accepted since 2026-08-27, DEF-632.** Sent ONCE,
   *  on capture, and never read back: the response carries `identifier.
   *  ssn_last4` and nothing more. The other twelve identifier names
   *  (`gov_id`, `national_id`, `ein`, `tin`, `ssn_last4`, `date_of_birth`, …)
   *  are still refused BY NAME with `customers.serviceRequest.
   *  identifierNotStorable` — the widening is exactly the size of what was
   *  built. `social_security_number` is refused too: one canonical name. */
  ssn?: string;
  /**
   * ✅ **`BR-CUS-092(a)` FINISHED, PO ruling 2026-09-15.** Clause (a) has said
   * since 2026-08-24 that *both identifiers are captured on the service
   * request*; the licence half was unbuilt until now, and this is it landing —
   * not a rule being reversed.
   *
   * ⚠ **THEY ARE TWO DIFFERENT KINDS OF THING AND THE COLUMNS SAY SO.**
   * `date_of_birth` is a plain `date` because `BR-CUS-1020` settled that it
   * *"must be COMPARABLE"* and is `BR-CUS-089`'s middle clause rather than an
   * identifier; `drivers_licence` is an `EncryptedTextField` with a blind index
   * beside it, served back as the LAST FOUR and never in a list response, an
   * export, a log line or an audit blob (clause (c)).
   *
   * ⊕ **`tax_id` IS HERE SINCE LANE CF-1 (2026-10-18), `DEF-CUS-10223`.** It
   * read *"NOT HERE, DELIBERATELY … held behind `TAX_ID_CAPTURE_ACCEPTED`"*
   * until the server learned the column (`customers/0087`, encrypted): the
   * screen drew the box and the number was lost on every business request.
   */
  date_of_birth?: string;
  drivers_licence?: string;
  preferred_language?: string;
  /** Lane CF-1 — a BUSINESS's Tax ID / EIN (refused on a person, BR-CUS-1022). */
  tax_id?: string;
  /** Lane CF-1 — Move-in's *Government ID*, last four (BR-CUS-045). */
  gov_id_last4?: string;
  /** Lane CF-1 — Move-in's *Contact by*. */
  contact_by?: string;
  /** Lane CF-1 — the full co-applicant cards (`coOwnersPayload("co_owner", …)`). */
  co_applicants?: Record<string, unknown>[];
  /** Lane CF-1 — WHERE THE BILL GOES, under its one name. */
  mailing_same?: boolean;
  mailing_line1?: string;
  mailing_line2?: string;
  mailing_city?: string;
  mailing_state?: string;
  mailing_postal_code?: string;
  /** Lane CF-1 — the request's Preferences (no autopay). */
  paperless?: boolean;
  sms_reminders?: boolean;
  co_applicant_name?: string;
  co_applicant_email?: string;
  co_applicant_phone?: string;
  requested_start?: string;
  address_as_given?: string;
  address_unit_as_given?: string;
  /**
   * ⊕ **`How many units are on this property?` — `BR-CUS-1055`, accepted by
   * `CAPTURE_FIELDS` since `customers/0049` (2026-09-15).**
   *
   * A CLAIM about the property, not a count of anything on file, and **not
   * part of the address** — the town, the state and the postcode are the
   * matched premises' own facts, walked to (hard rule 8), and have no key
   * here on purpose.
   *
   * A string of digits or `""`. The server coerces with `int()`, refuses
   * anything that is not a whole number and refuses a negative, accepts zero,
   * and reads `""` as *not supplied*. No maximum, by `NFR-5`.
   */
  units_on_property?: string;
  billing_address_same?: boolean;
  /** Still accepted by the server; the capture wizard no longer sends it
   *  (`DEF-CUS-6408`) — it sends the five parts below. */
  billing_address_as_given?: string;
  billing_line1_as_given?: string;
  billing_line2_as_given?: string;
  billing_city_as_given?: string;
  billing_state_as_given?: string;
  billing_postal_code_as_given?: string;
  /**
   * ✅ **THE PICK — `CR-094-BRC01` lane E's published contract, PO ruling
   * 2026-09-15:** *"if we have unit or street address then we should take it
   * from premises/Unit - it means its a search"*.
   *
   * Four shapes, and the middle two are the ones a screen gets wrong:
   * **neither sent** → nothing changes, so a PATCH about the fee does not
   * clear a pick · **both `null`** → the pick is undone (`unresolved`, all four
   * resolved columns null) · **a premises, no unit** → `premise_no_unit` ·
   * **a unit** → its building comes with it.
   *
   * ⚠ **THEY ARE IDS AND THEY NEVER RENDER (B14 rule 31).** What a screen
   * SHOWS is `resolved_premises_no` / `resolved_unit_no` off the read payload;
   * these two exist so the clerk's choice reaches the server, and a unit at
   * another address is refused by name.
   */
  picked_premises_id?: string | null;
  picked_unit_id?: string | null;
  plot_or_parcel?: string;
  what_is_being_built?: string;
  property_type?: PropertyType;
  what_they_said?: string;
  eligibility_claimed?: boolean;
  eligibility_note?: string;
  fee_timing?: FeeTiming;
  fee_due_by?: string;
  fee_method?: string;
}

// ══════════════════════════════════════════════════════════════════════════
// THE CALLS
// ══════════════════════════════════════════════════════════════════════════

export interface ServiceRequestListQuery {
  segment?: ServiceRequestSegment;
  q?: string;
  page?: number;
  per?: number;
  /** `BR-CUS-1046` — the clerk's chosen column, as the SERVER's sort name.
   * Both halves or neither: a `sortable` column with no parameter behind it is
   * a live control over a fixed order (hard-won law 2). */
  sort?: string;
  dir?: "asc" | "desc";
}

export async function listServiceRequests(
  query: ServiceRequestListQuery = {},
  client: ApiClient = api,
): Promise<ServiceRequestList> {
  return requireData(
    await client.get<ServiceRequestList>("/service-requests", {
      query: {
        segment: query.segment ?? "open",
        q: query.q === undefined || query.q === "" ? undefined : query.q,
        page: query.page,
        per: query.per,
        // `BR-CUS-1046` — the chosen ordering, so it reaches the `ORDER BY` and
        // survives a refresh in the URL rather than living only in component
        // state (the rule's own second clause).
        sort: query.sort,
        dir: query.dir,
      },
    }),
  );
}

/**
 * `POST /service-requests` — open a draft, **and it comes back NUMBERED**.
 *
 * BR-CUS-093 (PO 2026-08-24): *"At creation — every draft is numbered."* The
 * 201 carries `header.request_no`, which is the number the clerk reads down the
 * phone while the form is still half-filled.
 */
export async function createServiceRequest(
  body: CapturePayload,
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(await client.post<ServiceRequestDetail>("/service-requests", body));
}

export async function getServiceRequest(
  id: string,
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.get<ServiceRequestDetail>(`/service-requests/${encodeURIComponent(id)}`),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// WHAT THE CUSTOMER IS TOLD — `detail.told_on_submit` (REQ-03 step 4)
// ══════════════════════════════════════════════════════════════════════════

/**
 * One drawn row of the Review's communication card, exactly as
 * `apps/customers/applicant_messages.py::_told_row` serves it.
 *
 * ⚠ **NOTHING ENGLISH CROSSES THE WIRE** (`BR-SHL-020` r2). Every word here is
 * a KEY with parameters and the eleven catalogues compose the sentence. The
 * `to` value is an email ADDRESS — data, not prose — so it travels as itself.
 *
 * ⚠ **`available` AND `will_send` ARE TWO DIFFERENT QUESTIONS.** The first is
 * whether this PRODUCT has wording for the occasion at all (two of the five do
 * not, `DEF-CUS-5417`); the second is whether THIS request will send it. A
 * screen that conflated them would tell a clerk a message is held back for
 * their own reason when the product simply cannot write it.
 */
export interface ToldOnSubmitRow {
  occasion: string;
  /** `customers.serviceRequest.told.<occasion>` */
  message_key: string;
  params: Record<string, unknown>;
  /** `email` — a code, resolved through the catalogue. */
  channel: string;
  /** The address, or `null` where the applicant gave none. */
  to: string | null;
  /** `on_submit`, or `null` where this one will not go. */
  when: string | null;
  will_send: boolean;
  not_sent_reason: string | null;
  /** `customers.serviceRequest.toldNotSent.<reason>` */
  not_sent_reason_key: string | null;
  available: boolean;
}

/**
 * The card. ⚠ **THE THREE COUNTS ARE PART OF THE CONTRACT, NOT DECORATION** —
 * a declared blind spot with no NUMBER beside it is indistinguishable from an
 * empty one (hard-won law 7).
 */
export interface ToldOnSubmitCard {
  rows: ToldOnSubmitRow[];
  channel: string;
  to: string | null;
  rows_total: number;
  available_rows: number;
  will_send_rows: number;
  /** `BR-NOT-013` — no provider adapter exists on any channel, so the truest
   *  word this product has is QUEUED and no surface may say *reached*. */
  delivery: { queued_only: boolean; delivers: boolean; br_ref: string };
  br_ref: string;
}

export async function patchServiceRequest(
  id: string,
  body: CapturePayload,
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.patch<ServiceRequestDetail>(`/service-requests/${encodeURIComponent(id)}`, body),
  );
}

export async function submitServiceRequest(
  id: string,
  client: ApiClient = api,
): Promise<SubmitResult> {
  return requireData(
    await client.post<SubmitResult>(`/service-requests/${encodeURIComponent(id)}/submit`, {}),
  );
}

export async function transitionServiceRequest(
  id: string,
  action: string,
  reason: string | undefined,
  client: ApiClient = api,
  /**
   * ⚠ **THE FIELD WORK A ROUTING RAISES — CR-070 wave P, `US-WRK-039`.** Only
   * `route` reads it, and it is a fifth OPTIONAL parameter rather than a new
   * endpoint on purpose: `route` is already one of this door's actions, every
   * caller of it keeps working unchanged, and the alternative — a sibling
   * `POST …/route` — would leave two addresses that both move the same state.
   */
  fieldVisit?: readonly string[],
  /**
   * ⚠ **THE ASK-FOR-MORE DIALOG'S TWO CONTROLS (`CR-094-BRC01` wave 2).** Read
   * by `request_info` alone, and a SIXTH OPTIONAL PARAMETER rather than a new
   * endpoint — deliberately, and for `fieldVisit`'s reason one line up: this
   * door already moves the state, so a sibling `POST …/request-info` would
   * leave two addresses that both do it, and the older one would go on telling
   * the applicant nothing (hard-won law 2's mirror).
   *
   * `info_needed` is the CLERK's checklist; `message_to_applicant` is the only
   * one of the three an applicant ever reads.
   */
  ask?: { info_needed?: readonly string[]; message_to_applicant?: string },
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(
      `/service-requests/${encodeURIComponent(id)}/transitions`,
      {
        action,
        reason,
        // Omitted when nothing was ticked — the same posture the move wizards
        // take for `final_reads`.
        ...((fieldVisit?.length ?? 0) > 0
          ? { field_visit: { template_ids: [...(fieldVisit ?? [])] } }
          : {}),
        ...((ask?.info_needed?.length ?? 0) > 0
          ? { info_needed: [...(ask?.info_needed ?? [])] }
          : {}),
        ...(ask?.message_to_applicant !== undefined && ask.message_to_applicant !== ""
          ? { message_to_applicant: ask.message_to_applicant }
          : {}),
      },
    ),
  );
}

/**
 * ⚠ **`outcome` TRAVELS WITH THE APPROVAL — `DEF-CUS-5427`.** The dialog used
 * to post the decision and then the approval, and when the SECOND failed the
 * first had already been written: the request sat at `Under review` carrying an
 * outcome, looking decided while being nothing of the kind. The server now
 * writes the outcome inside the same transaction as the guards, so a refused
 * approval leaves nothing behind. `POST .../decision` is untouched and is still
 * the Decision tab's own door; omit `outcome` and this route behaves exactly as
 * it always did.
 */
export async function approveServiceRequest(
  id: string,
  note: string | undefined,
  client: ApiClient = api,
  outcome?: ServiceRequestOutcome,
  options: { addressIsNew?: boolean; customFieldPicks?: RequestCustomFieldPicks } = {},
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(
      `/service-requests/${encodeURIComponent(id)}/approve`,
      {
        note,
        outcome,
        // ⊕ `DEF-CUS-6350` — the clerk's *It's a new address*, sent only when
        // it was said. The server reads a JSON `true` and nothing else.
        ...(options.addressIsNew === true ? { address_is_new: true } : {}),
        // ⊕ `CR-161-BRC10` W6 — R5's pick, sent only when there is one.
        ...(options.customFieldPicks !== undefined &&
        Object.keys(options.customFieldPicks).length > 0
          ? { custom_field_picks: options.customFieldPicks }
          : {}),
      },
    ),
  );
}

/**
 * `reason` is REQUIRED and the server enforces it (TC-REQ-9). The screen
 * enforces it too, at the control, so the clerk is not sent to the server to
 * be told.
 *
 * ⚠ **THREE FIELDS, THREE AUDIENCES (`DEF-CUS-5389`, drawn p084–p085).**
 * `reason` is what the clerk tells the REGISTER and stays internal;
 * `reason_code` is one of five and is what the refusal is FILED under, so a
 * register of refusals can answer *why does this utility turn people down*;
 * `message_to_applicant` is the dialog's `What to tell them` and becomes the
 * letter. **No reason code ever reaches the applicant** (B14 rule 32).
 */
export async function refuseServiceRequest(
  id: string,
  input: { reason: string; reason_code?: string; message_to_applicant?: string },
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(`/service-requests/${encodeURIComponent(id)}/refuse`, {
      reason: input.reason,
      ...(input.reason_code === undefined || input.reason_code === ""
        ? {}
        : { reason_code: input.reason_code }),
      ...(input.message_to_applicant === undefined || input.message_to_applicant === ""
        ? {}
        : { message_to_applicant: input.message_to_applicant }),
    }),
  );
}

export async function decideServiceRequestOutcome(
  id: string,
  outcome: ServiceRequestOutcome,
  note: string | undefined,
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(`/service-requests/${encodeURIComponent(id)}/decision`, {
      outcome,
      note,
    }),
  );
}

/** `Park — waiting on ▾`. B19 §12.2: this is the SECOND of the PO's two
 *  save-and-exit controls — `Save & exit` leaves quietly and writes nothing;
 *  Park records WHAT is awaited, a note and a reminder date. It moves no
 *  state. */
export async function parkServiceRequest(
  id: string,
  body: { waiting_on: string; note?: string; remind_on?: string },
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(`/service-requests/${encodeURIComponent(id)}/park`, body),
  );
}

export async function resumeServiceRequest(
  id: string,
  note: string | undefined,
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(`/service-requests/${encodeURIComponent(id)}/resume`, {
      note,
    }),
  );
}

/** `Add a note`, badged **Internal · never shown to the customer**. There is no
 *  customer-visible path and there must not be one — the portal is out of v1
 *  scope, so a visibility flag would be a permission with nothing to permit. */
export async function addServiceRequestNote(
  id: string,
  body: { note: string; note_type?: string },
  client: ApiClient = api,
): Promise<{ history: ServiceRequestEvent[] }> {
  return requireData(
    await client.post<{ history: ServiceRequestEvent[] }>(
      `/service-requests/${encodeURIComponent(id)}/notes`,
      body,
    ),
  );
}

export async function getServiceRequestCategories(
  client: ApiClient = api,
): Promise<ServiceRequestCategories> {
  return requireData(
    await client.get<ServiceRequestCategories>("/service-requests/categories"),
  );
}

/** What a NEW request opens on — `GET /service-requests/capture-defaults`. */
export interface ServiceRequestCaptureDefaults {
  /** `Connection date`'s opening value, ISO. The COLUMN is `requested_start`,
   *  and this key is that column's name on purpose — a second spelling is how
   *  a payload and a form come to disagree about which one is authoritative. */
  requested_start: string | null;
  /** How many WORKING days ahead that is — the utility's
   *  `service_request_default_target_days` (Settings → Reference data →
   *  Accounts → Service requests), seeded 15 per the PO rulings of 2026-09-22
   *  and 2026-10-22 (`DEF-CUS-10445`). `null` only when the stored setting is
   *  unreadable, and then there is no opening date either. */
  working_days: number | null;
  /**
   * How many of this tenant's public holidays the count had available.
   *
   * ⚠ **SERVED SO NOBODY HAS TO GUESS WHICH ANSWER THEY GOT.** `0` is a
   * legitimate reading — a utility that keeps no calendar counts weekends only
   * — and it is a DIFFERENT fact from a calendar that was consulted and held
   * nothing in the window. Nothing renders it; it is here so a walkthrough or a
   * test can state which of the two it proved instead of asserting a date and
   * hoping.
   */
  holidays_counted: number;
}

/**
 * **The opening `Connection date` — 15 WORKING days out, FROM THE SERVER.**
 *
 * ⚠ **IT IS NOT COMPUTED IN THE BROWSER AND MUST NOT BE.** Working days means
 * weekends **and this tenant's own public holidays** out, and the browser holds
 * neither the calendar nor the tenant's timezone. Measured on the demo tenant
 * from Tuesday 2026-09-22: the calendar moves the answer from 2026-10-13 to
 * **2026-10-14**, because Columbus Day falls inside the window. A front-end
 * weekday count would be wrong by a day, silently, and would disagree with
 * every other business-day figure this product prints.
 */
export async function getServiceRequestCaptureDefaults(
  client: ApiClient = api,
): Promise<ServiceRequestCaptureDefaults> {
  return requireData(
    await client.get<ServiceRequestCaptureDefaults>("/service-requests/capture-defaults"),
  );
}

/**
 * ══════════════════════════════════════════════════════════════════════════
 * **`GET /premises/picker` — THE REGISTER'S OWN SEARCH** (`CR-094-BRC01`
 * lane E). Capture step 3 is its first caller; move-in, transfer and the
 * owner's-account path want the same search.
 * ══════════════════════════════════════════════════════════════════════════
 *
 * ⚠ **THE UNITS COME WITH THE PREMISES AND THERE IS NO SECOND CALL.** The row
 * carries its own units, so picking a building and then picking a unit costs
 * one round trip rather than two — and a unit list that arrived separately
 * could disagree with the building it was drawn under.
 *
 * ⚠ **AND NOTHING ABOUT METERS, SERVICES OR ACCOUNTS IS IN THE ANSWER.** That
 * is the same ruling's second clause — *"if unit is found then it is gi=oing to
 * be mobve in mostly and all asset - which we will take acre in move in
 * request"* — and lane E's
 * `test_nothing_about_the_meters_or_services_on_a_unit_is_served` fails the day
 * somebody adds one.
 *
 * `q` shorter than two characters is IGNORED rather than refused
 * (`BR-SHL-011`), and the page is the server's (`NFR-3`).
 */
export interface PremisesPickerUnit {
  id: string;
  unit_no: string | null;
  label: string | null;
  is_common_area: boolean;
}

export interface PremisesPickerRow {
  id: string;
  premise_no: string | null;
  address_line: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  /**
   * **What this address OFFERS — `DEF-CUS-6057`, served since 2026-09-21.**
   *
   * ⚠ **`null` IS NOT `[]` (`DEF-762`).** `null` means *nobody has ever been
   * asked about this address*; `[]` means *it offers nothing*. A caller
   * writing a clerk's service list from this must write it only where there IS
   * an answer, or an unasked address silently blanks what the clerk chose.
   *
   * ⚠ **IT IS THE PREMISES' OWN COLUMN, NOT ANYTHING STANDING ON A UNIT.** The
   * PO's 2026-09-15 ruling keeps meters, service points, assets and accounts
   * out of this payload; what the STREET offers is the same class of fact as
   * the address (hard rule 8) and travels for the same reason.
   *
   * ⚠ **OPTIONAL IN THE TYPE BECAUSE A CACHED OR MOCKED ROW MAY PREDATE IT** —
   * `undefined` is read exactly as `null`, which is the safe half.
   */
  services_available?: string[] | null;
  /**
   * **WHAT KIND OF PROPERTY IT IS — `DEF-CUS-6116`, served since 2026-09-21.**
   *
   * The premises type's own CODE (`single_family`, `apartment_complex`, …),
   * never its uuid (B14 rule 31), and it is the value a type picker holds.
   *
   * ⚠ **IT TRAVELS BECAUSE THE DIVERGENCE COSTS MORE THAN THE KEYSTROKE.**
   * New Connect step 2 filled town, state and postcode from a picked address
   * and left the type EMPTY, so a clerk answered again — and could answer
   * DIFFERENTLY from the record, putting two answers in the product for one
   * fact about one building.
   *
   * ⚠ **`null` MEANS THE REGISTER HAS NO OPINION**, which a nullable column
   * genuinely has: a caller asks the question then, and writes no guess.
   * `undefined` is a row that predates this field and reads exactly as `null`.
   */
  premises_type?: string | null;
  units: PremisesPickerUnit[];
}

export async function searchPremisesPicker(
  q: string,
  client: ApiClient = api,
): Promise<Paginated<PremisesPickerRow>> {
  return requireData(
    await client.get<Paginated<PremisesPickerRow>>("/premises/picker", {
      query: { q, per: 50 },
    }),
  );
}

export async function setServiceRequestCategory(
  id: string,
  body: { account_type_code: string; account_subtype_id?: string },
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(
      `/service-requests/${encodeURIComponent(id)}/category`,
      body,
    ),
  );
}

/** One service on capture step 2, and it is two shapes on purpose
 *  (**BR-CUS-1070**). A bare code is what this call took until 2026-09-15 and
 *  means *this service, no date given* — NOT *use the job's `Connection date`*,
 *  which is the copy the rule removed. The object carries the service's own
 *  start, as `YYYY-MM-DD`; `null` and an omitted field both mean no date. */
export type RequestedServiceInput = string | { code: string; requested_start?: string | null };

/** ⚠ **A MIXED LIST IS FINE AND THE OLD SHAPE IS NOT DEPRECATED.** Nothing was
 *  migrated when the rule landed, because `service_request_services` held 0 rows
 *  across the demo tenant's 8 requests; keeping the flat list means every stored
 *  caller keeps working. An unknown code, a repeated code and an unparseable
 *  date are each refused BY NAME by the server. */
export async function setServiceRequestServices(
  id: string,
  services: RequestedServiceInput[],
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(
      `/service-requests/${encodeURIComponent(id)}/services`,
      { services },
    ),
  );
}

/** The resolver writes EVIDENCE, never a decision. BR-CUS-070 keeps
 *  `address_as_given` untouched and lands the resolved ids beside it. */
export async function resolveServiceRequestAddress(
  id: string,
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(
      `/service-requests/${encodeURIComponent(id)}/resolve-address`,
      {},
    ),
  );
}

/** `customer_id: null` records **"searched, and there is no prior customer"** —
 *  a real answer, and what clears the arrears condition for a genuine
 *  first-time applicant. */
export async function linkServiceRequestCustomer(
  id: string,
  body: { customer_id: string | null; tier?: string; basis?: string },
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(
      `/service-requests/${encodeURIComponent(id)}/customer-link`,
      body,
    ),
  );
}

export async function linkServiceRequestChild(
  id: string,
  body: { child_ref: string; child_kind?: string },
  client: ApiClient = api,
): Promise<ServiceRequestDetail> {
  return requireData(
    await client.post<ServiceRequestDetail>(
      `/service-requests/${encodeURIComponent(id)}/child-link`,
      body,
    ),
  );
}

export async function getServiceRequestDocuments(
  id: string,
  client: ApiClient = api,
): Promise<ServiceRequestDocumentsTab> {
  return requireData(
    await client.get<ServiceRequestDocumentsTab>(
      `/service-requests/${encodeURIComponent(id)}/documents`,
    ),
  );
}

/** `POST /service-requests/{id}/documents` **WITH THE BYTES** — the counter.
 *
 * ⚠ **ONE ADDRESS, TWO POSTS, TOLD APART BY WHETHER A FILE CAME WITH IT.**
 * `attachServiceRequestDocument` below is the same route without a file: it
 * records that a document is EXPECTED. This one carries it. They are one
 * endpoint because they produce the same row on the same tab, and a second
 * address would make *"attach a document"* two things a screen has to choose
 * between.
 *
 * `BR-SHL-031`: PDF/PNG/JPG/CSV, ≤ 10 MB, uploads staff-mediated in v1. The two
 * transport refusals are **415** (outside the allowlist) and **413** (over the
 * cap), and both arrive as B12 r1 HTTP-series envelopes with `code: null` —
 * the same shape `uploadAccountDocument` already meets. The server is the
 * guard; `accept=` on the input only saves a clerk choosing a file that was
 * always going to be refused.
 *
 * ⚠ **THE FILE PART IS NAMED `file` AND THE SERVER STRIPS IT OUT OF THE
 * PAYLOAD DICT**, so a part named after a column cannot smuggle a value into
 * one.
 *
 * Multipart rides through the ONE client — `client.ts` leaves `FormData` alone
 * so the browser writes the boundary.
 */
export async function uploadServiceRequestDocument(
  id: string,
  body: {
    file: File;
    docType: string;
    whatItProves?: string;
    /** PO ruling 2026-09-22 — the number ON the paper. Sent whole and shown as
     *  its last four on every read path (`BR-CUS-092(c)`). */
    documentNumber?: string;
    required?: boolean;
  },
  client: ApiClient = api,
): Promise<ServiceRequestDocumentsTab> {
  const form = new FormData();
  form.append("file", body.file);
  form.append("doc_type", body.docType);
  form.append("name", body.file.name);
  if (body.whatItProves !== undefined && body.whatItProves.trim() !== "") {
    form.append("what_it_proves", body.whatItProves.trim());
  }
  // ⚠ **ABSENT RATHER THAN EMPTY.** A multipart part is always a string, so an
  // empty box sent as `""` would write an empty string where the column means
  // *nobody gave a number* — the same distinction the `required` part below
  // makes for its own reason.
  if (body.documentNumber !== undefined && body.documentNumber.trim() !== "") {
    form.append("document_number", body.documentNumber.trim());
  }
  // ⚠ **SENT ONLY WHEN TRUE, AND AS THE STRING `true`.** A multipart part is
  // always a string, and `bool("False")` is `True` in Python — so a part
  // carrying "false" would mark every document required. `_payload` reads this
  // through `bool(payload.get("required", False))`, which is why the absent
  // case is the false case.
  if (body.required === true) {
    form.append("required", "true");
  }
  return requireData(
    await client.post<ServiceRequestDocumentsTab>(
      `/service-requests/${encodeURIComponent(id)}/documents`,
      form,
    ),
  );
}

/** **GATE ONE: attaching never blocks CREATION.** The POST lands
 *  `not_checked`, always — REQ-03.4's `NOT BLOCKING` callout.
 *
 *  ⚠ **THIS IS THE NO-FILE HALF OF THE ROUTE AND IT IS STILL REACHABLE ON
 *  PURPOSE.** It records that a document is EXPECTED — p078 draws exactly such
 *  a row (`Tenancy agreement or deed`, FILE `—`, STATE `Nothing attached`), and
 *  `Add another document` is the control that makes one. Where the BYTES exist,
 *  use `uploadServiceRequestDocument` above. */
export async function attachServiceRequestDocument(
  id: string,
  body: {
    doc_type: string;
    /** PO ruling 2026-09-22 — see `uploadServiceRequestDocument`. */
    document_number?: string;
    name?: string;
    storage_ref?: string;
    size?: number;
    what_it_proves?: string;
    required?: boolean;
  },
  client: ApiClient = api,
): Promise<ServiceRequestDocumentsTab> {
  return requireData(
    await client.post<ServiceRequestDocumentsTab>(
      `/service-requests/${encodeURIComponent(id)}/documents`,
      body,
    ),
  );
}

/** **GATE TWO: verifying is what unblocks APPROVAL.** *"Attaching a file is not
 *  the same as verifying it."* */
export async function verifyServiceRequestDocument(
  id: string,
  documentId: string,
  client: ApiClient = api,
): Promise<ServiceRequestDocumentsTab> {
  return requireData(
    await client.post<ServiceRequestDocumentsTab>(
      `/service-requests/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/verify`,
      {},
    ),
  );
}

export async function rejectServiceRequestDocument(
  id: string,
  documentId: string,
  reason: string,
  client: ApiClient = api,
): Promise<ServiceRequestDocumentsTab> {
  return requireData(
    await client.post<ServiceRequestDocumentsTab>(
      `/service-requests/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/reject`,
      { reason },
    ),
  );
}

/** BR-CUS-095's checklist — **System Admin only**, because ticking
 *  `proof_of_identity` for `move_in` changes what every future approval of that
 *  job type demands. That is a settings act, not a capture act. */
export async function getDocumentRequirements(
  requestType: string | undefined,
  client: ApiClient = api,
): Promise<DocumentRequirementsGrid> {
  return requireData(
    await client.get<DocumentRequirementsGrid>(
      "/service-request-settings/document-requirements",
      { query: { request_type: requestType } },
    ),
  );
}

export async function setDocumentRequirement(
  body: { request_type: string; doc_type: string; required: boolean },
  client: ApiClient = api,
): Promise<DocumentRequirementsGrid> {
  return requireData(
    await client.put<DocumentRequirementsGrid>(
      "/service-request-settings/document-requirements",
      body,
    ),
  );
}

export async function getServiceRequestFees(
  id: string,
  client: ApiClient = api,
): Promise<ServiceRequestFeesTab> {
  return requireData(
    await client.get<ServiceRequestFeesTab>(`/service-requests/${encodeURIComponent(id)}/fees`),
  );
}

/**
 * ⚠ **`unit_amount` AND `quantity` ARE STRINGS AND THE SERVER REFUSES A JSON
 * FLOAT** (CLAUDE.md rule 2). By the time a JSON number reaches Python it is an
 * IEEE double: `25.10` arrives as `25.099999999999998` and would be stored to
 * four places as exactly that. On a counter endpoint that is a customer's cash.
 */
export async function addServiceRequestFee(
  id: string,
  body: {
    charge_code: string;
    unit_amount: string;
    quantity?: string;
    basis?: string;
    description?: string;
    charge_code_id?: string;
  },
  client: ApiClient = api,
): Promise<ServiceRequestFeesTab> {
  return requireData(
    await client.post<ServiceRequestFeesTab>(
      `/service-requests/${encodeURIComponent(id)}/fees`,
      body,
    ),
  );
}

/** `Waive the fee` — *"A reason is required and recorded against your name."*
 *  ⚠ A waiver is NOT what a shortfall at the counter becomes (BR-CUS-090);
 *  that stays an open balance. */
export async function waiveServiceRequestFee(
  id: string,
  feeId: string,
  reason: string,
  client: ApiClient = api,
): Promise<ServiceRequestFeesTab> {
  return requireData(
    await client.post<ServiceRequestFeesTab>(
      `/service-requests/${encodeURIComponent(id)}/fees/${encodeURIComponent(feeId)}/waive`,
      { reason },
    ),
  );
}

/**
 * `DELETE …/fees/{feeId}` — the fee table's remove icon on capture step 5.
 * **OQ-357 closed 2026-09-23 as "both"**: a line is REMOVED while the request
 * is a draft and WAIVED, with a reason, after. The server refuses a submitted
 * request, a waived line and a paid one, each by name. Answers with the whole
 * fees tab, so the reply IS the new table.
 */
export async function removeServiceRequestFee(
  id: string,
  feeId: string,
  client: ApiClient = api,
): Promise<ServiceRequestFeesTab> {
  return requireData(
    await client.del<ServiceRequestFeesTab>(
      `/service-requests/${encodeURIComponent(id)}/fees/${encodeURIComponent(feeId)}`,
    ),
  );
}

/**
 * `POST .../fee-collection` — **BR-CUS-090, the counter accepts what is handed
 * over.** PO verbatim: *"we acept it and in finance we will reconcile ; here
 * segregation of responsibilitys, accept it and mark it as cash"*.
 *
 * ⚠ **A SHORTFALL IS NEVER REFUSED HERE.** `amount` below the quote is a
 * lawful, storable state and the difference is an open fee balance that blocks
 * APPROVAL and nothing else.
 *
 * **Worked:** quoted $130.00, `{amount: "25.00", method: "cash", receipt_no:
 * "RCP-26-4471"}` → *$25.00 collected of $130.00 quoted · $105.00 outstanding*.
 *
 * ⚠ Idempotent on the receipt number (rule 6) — the desk is exactly where a
 * double-click happens.
 *
 * **`DEF-CUS-6376` — Record a payment's three facts, optional on the wire.**
 * `posted_at` is a `YYYY-MM-DD` calendar date the server reads as the
 * TENANT's day (BR-TEN-081) and books the ledger on; absent means the
 * tenant's today. `confirmation` is the instrument's own number (a check
 * number, a card authorisation) and `memo` is free text. `method` is a code
 * from the tenant's served list (`GET /payments` `methods[]`) or one of the
 * request's older three. ⚠ `cash`, `check` / `cheque` and `money_order` are
 * refused with `payments.counter.till_required` unless the clerk has a till
 * open (`DEF-CUS-6374`).
 */
export async function collectServiceRequestFee(
  id: string,
  body: {
    amount: string;
    method: string;
    receipt_no: string;
    posted_at?: string;
    confirmation?: string | null;
    memo?: string | null;
  },
  client: ApiClient = api,
): Promise<ServiceRequestFeesTab> {
  return requireData(
    await client.post<ServiceRequestFeesTab>(
      `/service-requests/${encodeURIComponent(id)}/fee-collection`,
      body,
    ),
  );
}

/** `DEF-CUS-10043` — the move-in's *Search customer ID*, asked with the identity
 *  this request already holds (`GET …/customer-search`). */
export async function searchRequestCustomer(
  id: string,
  client: ApiClient = api,
): Promise<CustomerSearchResult> {
  return requireData(
    await client.get<CustomerSearchResult>(`/service-requests/${encodeURIComponent(id)}/customer-search`),
  );
}

/** `DEF-CUS-10042` — the messages a clerk ADDED to *What the customer is told*. */
export interface RequestExtraMessage {
  seq?: number;
  template_code: string;
  template_name?: string;
  channel: string;
  to_address: string;
  send_when: string;
  state?: "planned" | "queued" | "not_sent" | string;
  fired?: boolean;
}

export interface RequestExtraMessages {
  rows: RequestExtraMessage[];
  templates: { served: boolean; results: { code: string; name: string }[] };
}

/** `GET .../extra-messages` — the added rows and the templates a row may pick. */
export async function getRequestExtraMessages(
  id: string,
  client: ApiClient = api,
): Promise<RequestExtraMessages> {
  return requireData(
    await client.get<RequestExtraMessages>(`/service-requests/${encodeURIComponent(id)}/extra-messages`),
  );
}

/** `PUT .../extra-messages` — replaces the UNFIRED added rows whole. */
export async function saveRequestExtraMessages(
  id: string,
  rows: readonly RequestExtraMessage[],
  client: ApiClient = api,
): Promise<RequestExtraMessages> {
  return requireData(
    await client.put<RequestExtraMessages>(`/service-requests/${encodeURIComponent(id)}/extra-messages`, {
      rows: rows
        .filter((row) => row.fired !== true)
        .map((row) => ({
          template_code: row.template_code,
          channel: row.channel,
          to_address: row.to_address,
          send_when: row.send_when,
        })),
    }),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 (B18 §W4 tasks 4.10–4.13) · B19 · customers-service-request.md
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ eslint✔ vitest✔ · G13✔ G31✔ G37✔ (see the lane report for the
//        RED-first transcripts)
// exceptions: E3 the `Money.currency` is typed `string | null` because the
//   server serves null on a request with no fee line — a `?? "USD"` here would
//   be a fabricated fact about somebody's money (the DEF-127 shape) · E3 there
//   is no wrapper for an automatic customer MATCHER: the server serves
//   `no_customer_matcher` in `unavailable` because the drawn `Matched on: ID
//   number and date of birth` names two fields this schema does not carry
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/* ═══════════════════════════════════════════════════════════════════════════
 * THE INTERRUPTION A PORTAL REPORT RAISED — CR-068 wave B, US-CWP-008
 *
 * ⚠ **IT HANGS OFF THE REQUEST BECAUSE NO STAFF SCREEN OWNS IT** and screen
 * numbers are the PO's (`R13`), so the clerk's control is a SECTION of the
 * detail rather than a new `S`-id (`10-execution-plan.md` §0 row 22). The
 * record itself belongs to `metering` (`BR-CWP-012`, B2 §2); this endpoint is
 * the door, not the table.
 * ═══════════════════════════════════════════════════════════════════════════ */

export interface AffectedPremises {
  id: string;
  address_line: string;
  postal_code: string | null;
}

export interface InterruptionView {
  id: string;
  reference: string | null;
  kind: string;
  status: string;
  location_text: string;
  affected_area: { street: string; from: number | null; to: number | null } | null;
  expected_back_on: string | null;
  reported_at: string | null;
  resolved_at: string | null;
  affected_premises: AffectedPremises[];
  affected_premises_count: number;
  affected_unit_count: number;
}

/** An interruption already open on this report's street — a SUGGESTION the
 *  clerk accepts or ignores, never a decision the server made. */
export interface NearbyInterruption {
  id: string;
  reference: string | null;
  location_text: string;
  status: string;
}

/**
 * The whole Interruption section.
 *
 * ⚠ **`interruption` IS NULL FOR MOST REPORTS AND THAT IS THE NORMAL STATE
 * SINCE `CR-072`.** A passer-by's report used to OPEN an interruption; it does
 * not any more, because a stranger's form cannot settle whether something is an
 * outage. A clerk who has read the reports opens one, and until they do there
 * is a report and no operational record.
 */
export interface InterruptionSection {
  report: { kind: string | null; location_text: string; reported_at: string | null };
  interruption: InterruptionView | null;
  already_open_nearby: NearbyInterruption | null;
  /** The three, in order, from the server — never a list this screen types. */
  statuses: string[];
}

/** `GET .../interruption` — **404 when the request is neither a report nor
 *  attached to one**, which is what lets the section be ABSENT rather than an
 *  empty frame on every move-in in the product (`BR-CWP-093` in the staff
 *  app's dialect). */
export async function getServiceRequestInterruption(
  id: string,
  client: ApiClient = api,
): Promise<InterruptionSection> {
  return requireData(
    await client.get<InterruptionSection>(
      `/service-requests/${encodeURIComponent(id)}/interruption`,
    ),
  );
}

/** `POST .../interruption` — `BR-CWP-101`: a clerk judges the reports real.
 *  With `interruption_id` it attaches this report to one already open; with no
 *  body it opens a new one from the report's own kind and words. */
export async function openServiceRequestInterruption(
  id: string,
  body: { interruption_id?: string },
  client: ApiClient = api,
): Promise<InterruptionSection> {
  return requireData(
    await client.post<InterruptionSection>(
      `/service-requests/${encodeURIComponent(id)}/interruption`,
      body,
    ),
  );
}

export async function patchServiceRequestInterruption(
  id: string,
  body: {
    status?: string;
    affected_area?: { street: string; from: number | null; to: number | null } | null;
    expected_back_on?: string | null;
  },
  client: ApiClient = api,
): Promise<InterruptionSection> {
  return requireData(
    await client.patch<InterruptionSection>(
      `/service-requests/${encodeURIComponent(id)}/interruption`,
      body,
    ),
  );
}
