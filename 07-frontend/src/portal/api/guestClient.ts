// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — `GET /portal/public/front`, the front
//           page's data source (07-endpoints.md §1 row 1). Screens: CWP-001
// Rules:    BR-CWP-007 (the portal lives at `/{tenant}/portal/…` — the tenant
//           is read off the address the browser is on, never typed here) ·
//           BR-CWP-011 (the guest surface calls the GUEST edge and nothing
//           else — this file is the whole of what it may call) · BR-CWP-021
//           (the wire carries no person and no id; the types say so)
// Tests:    src/portal/guest/FrontPage.test.tsx
// Impacts:  06-backend/apps/portal/guest_api.py (the shape these types are
//           written against) · src/api/queryClient.ts (`queryKeys.portalFront`)
// ───────────────────────────────────────────────────────
// Hand-written against `06-backend/openapi/schema.json` + `selectors.front()`.

import type { CompanyMark } from "@/api/endpoints";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { ApiResponse } from "@/api/client";

/** The contract promises a body; an empty 200 is a defect, not a value. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("empty 200 body where the contract promises one (portal/public/front)");
  }
  return response.data;
}

/** The six errand cards CWP-001 draws, in the wireframe's order. ⚠ **THE SERVER
 *  SENDS ALL SIX, ALWAYS** — it used to send only the ones a visitor could use.
 *  PO ruling 2026-09-05: *"Yoi ahev these cards - may be disable them, but for
 *  completess have them on screen"*. */
export type ErrandCardKey =
  | "pay_bill"
  | "report_problem"
  | "check_my_area"
  | "start_service"
  | "what_things_cost"
  | "help_answers";

/**
 * Why a card a visitor can SEE is not one they can USE. Three codes, closed,
 * and different in KIND — which is why a code travels and not a bare `false`:
 * one of them a utility reverses itself in Settings, one of them waits on a
 * published answer, and one of them waits on a ruling nobody here can move
 * (`DEF-CWP-3953`: from the utility's chair those three looked identical,
 * because they all looked like nothing at all).
 *
 * ⚠ **A CODE WITH NO SENTENCE PRINTS ITSELF**, which is an internal code on a
 * customer's screen (B14 rule 31). `REASON_COPY` in `FrontPageView.tsx` is
 * exhaustive over this union so the compiler refuses a fourth code that
 * arrives without wording; a code this build has never heard of falls back to
 * a neutral sentence rather than to its own key.
 */
export type ErrandCardReason =
  | "switched_off_by_the_utility"
  | "status_page_not_offered"
  | "nothing_published_yet";

/**
 * One of the six, as the server offers it. A DISCRIMINATED UNION on purpose:
 * `available: false` narrows `reason_code` to a real code, so a screen cannot
 * draw a disabled card with nothing to say and still compile.
 */
export type ErrandCardOffer =
  | { key: ErrandCardKey; available: true; reason_code: null }
  | { key: ErrandCardKey; available: false; reason_code: ErrandCardReason };

/** Whether the server is offering this card for use — the question
 *  `front.cards.includes(key)` used to answer, and the reason that call site
 *  had to change: every key is present now, so presence stopped meaning
 *  anything and only `available` still does. */
export function cardIsAvailable(front: PortalFront, key: ErrandCardKey): boolean {
  return front.cards.some((card) => card.key === key && card.available);
}

/** A service shown as a chip — code, name, colour. Never an id (B14 rule 31). */
export interface ServiceChip {
  code: string;
  name: string;
  color: string | null;
}

/** The utility, as a visitor may know it: a name and two colours. */
export interface PortalTenant {
  slug: string;
  name: string;
  brand_primary_hex: string | null;
  brand_accent_hex: string | null;
  /**
   * CR-172-BRC10 — the header draws the utility's logo, or its generated mark,
   * beside the name (`BrandMark`, from tenancy's one logo address). Optional
   * only because hand-built fixtures predate it; the server always sends them.
   */
  has_logo?: boolean;
  logo_ref?: string | null;
  mark?: CompanyMark;
}

export interface PortalSwitches {
  quick_pay_enabled: boolean;
  self_read_enabled: boolean;
  plans_enabled: boolean;
  requests_enabled: boolean;
  outage_reporting_enabled: boolean;
}

/** `GET /portal/public/front`. `switches` is present only when the portal is live. */
/**
 * The tenant's Regional settings, in the EXACT shape
 * `ShellWithSession.tenantRegionalOf` already validates (`DEF-CWP-3994`).
 *
 * ⚠ **THE SNAKE_CASE IS DELIBERATE AND IS THE POINT.** Matching the staff
 * endpoint's own field names is what lets the portal reuse that mapper rather
 * than write a second one — and a second one is how a product ends up telling
 * one customer two different stories about one date. The mapper is where the
 * seven drawable formats are enumerated; there must be one such list.
 */
export interface PortalRegional {
  /** IANA name from `tenant_settings.timezone`. `null` when unset. */
  timezone: string | null;
  /** One of the seven `RegionalDateFormat`s. `null` when unset. */
  date_format: string | null;
  /**
   * The UTILITY's own language from `tenant_settings.language` — a BCP-47 code
   * such as `es-MX`, or `null` when they have not chosen one (`DEF-CWP-4440`,
   * `BR-CWP-105`).
   *
   * ⚠ **IT IS THE UTILITY'S DEFAULT AND NOT A CUSTOMER'S CHOICE**, which is
   * why it may ride on this anonymous payload at all. A signed-in customer's
   * own `accounts.preferred_language` beats it and arrives on `PortalSession`
   * instead — a fact about a person never travels on the guest surface
   * (`BR-CWP-021`).
   *
   * ⚠ **IT IS NOT NECESSARILY A LANGUAGE THIS BUILD CAN DRAW.** The column is
   * validated against the server's twelve seeded codes and the app carries
   * ELEVEN catalogues; `en-US` is a real, lawful setting with no catalogue
   * behind it. `supportedLocale` in `../components/language` is the one place
   * that reconciles them, and nothing should call `changeLanguage` with this
   * string raw.
   */
  language: string | null;
}

export interface PortalFront {
  tenant: PortalTenant;
  is_live: boolean;
  /**
   * ⚠ **NOT OPTIONAL.** The server sends it on both branches of `front()` —
   * live and holding — and an optional field here would let a screen forget to
   * handle the absence, which is `DEF-SHL-3964`'s exact shape one level up.
   */
  regional: PortalRegional;
  /**
   * The languages the portal may OFFER — `apps.portal.selectors.PORTAL_LOCALES`
   * (`DEF-CWP-4442`, PO 2026-09-07: *"currently in drop down show only 2
   * elnglish and spanish"*).
   *
   * ⚠ **A DIFFERENT QUESTION FROM `regional.language` ONE FIELD UP, AND FROM
   * `LOCALE_CODES` IN `@/i18n`** — `BR-CWP-105` names all three and says not
   * to fold them. `regional.language` is what the UTILITY chose; `LOCALE_CODES`
   * is what this BUNDLE can draw (eleven catalogues, unchanged); this is what
   * a customer may PICK. The guest dropdown read the bundle's list until
   * 2026-09-07 and therefore offered nine languages the product does not.
   *
   * ⚠ **NOT OPTIONAL, FOR `regional`'s OWN REASON ONE FIELD UP.** The server
   * sends it on both branches of `front()` — live and holding — even though
   * the holding page draws no nav and no control at all.
   */
  locales: string[];
  cards: ErrandCardOffer[];
  links: { help: boolean; visit: boolean };
  switches?: PortalSwitches;
  services: ServiceChip[];
  strapline: string | null;
  office_hours_text: string | null;
  emergency_phone: string | null;
}

export async function getPortalFront(client: ApiClient = api): Promise<PortalFront> {
  return requireData(await client.get<PortalFront>("/portal/public/front"));
}

// ══ CR-068 wave D — help, tips and where you can walk in ═══════════════════
//
// ⚠ EVERY ONE OF THESE IS A READ EXCEPT `sendHelpFeedback`, and that one lands
// on a route served by `apps/tenancy` — `help_answer_feedback` is a tenancy
// table and B2 §2 forbids a cross-module write, so `apps/portal` never writes
// it. The path is the same guest prefix; the module behind it is not.

/** A row on `CWP-011`. No id, no body — the list is a list of doors. */
export interface HelpAnswerSummary {
  slug: string;
  question: string;
  topic: string;
}

/** `GET /portal/public/help`. ⚠ No count of what is hidden (BR-CWP-094). */
export interface PortalHelpList {
  answers: HelpAnswerSummary[];
  /** Derived from what is published — a chip that filters to nothing is a
   *  container with nothing in it (BR-CWP-093). */
  topics: string[];
  /** Whether *where you can walk in* exists at all. */
  visit_link: boolean;
}

/** `GET /portal/public/help/{slug}` — one answer, `CWP-060`. */
export interface PortalHelpAnswer {
  slug: string;
  question: string;
  topic: string;
  body: string;
  /** What the browser asked for, and what it actually got. */
  asked_for: string;
  shown_in: string;
  /** ⚠ TRUE means the screen owes the reader a line saying so (BR-CWP-094). */
  is_fallback: boolean;
  updated_on: string | null;
  also_written_in: string[];
  related: HelpAnswerSummary[];
}

export interface PortalCentreHour {
  day_of_week: number;
  is_closed: boolean;
  opens_at: string | null;
  closes_at: string | null;
}

/** ⚠ Facts, never a sentence — the screen writes it in its own language. */
export interface PortalCentreToday {
  is_open_now: boolean;
  closes_at: string | null;
  opens_later_today: boolean;
  next_open_date: string | null;
  next_open_weekday: number | null;
  next_open_is_today: boolean;
  next_open_at: string | null;
  closed_for_holiday: { date: string; label: string } | null;
  next_holiday: { date: string; label: string } | null;
}

export interface PortalCentre {
  slug: string;
  name: string;
  address: string;
  phone: string | null;
  directions_note: string | null;
  allowed_actions: string[];
  /** ⚠ What this centre CANNOT do — computed by the server and DRAWN, because
   *  four rows saying no is the screen doing its job (US-CWP-074 TC-4). */
  cannot_do: string[];
  all_actions?: string[];
  payment_methods_accepted: string[];
  hours: PortalCentreHour[];
  today: PortalCentreToday;
}

/** `GET /portal/public/tips?screen=`. ⚠ `null` is a NORMAL answer. */
export interface PortalTip {
  text: string;
  target_screen: string;
}

export async function getPortalHelp(
  topic: string | null,
  client: ApiClient = api,
): Promise<PortalHelpList> {
  const query = topic ? `?topic=${encodeURIComponent(topic)}` : "";
  return requireData(await client.get<PortalHelpList>(`/portal/public/help${query}`));
}

export async function getPortalHelpAnswer(
  slug: string,
  locale: string,
  client: ApiClient = api,
): Promise<PortalHelpAnswer> {
  return requireData(
    await client.get<PortalHelpAnswer>(
      `/portal/public/help/${slug}?locale=${encodeURIComponent(locale)}`,
    ),
  );
}

/** A read, or a *did this help?* vote. ⚠ Two distinct events (`CP-34`). */
export async function sendHelpFeedback(
  slug: string,
  event: "read" | "helpful" | "not_helpful",
  locale: string,
  client: ApiClient = api,
): Promise<void> {
  await client.post(`/portal/public/help/${slug}/feedback`, { event, locale });
}

export async function getPortalCentres(client: ApiClient = api): Promise<PortalCentre[]> {
  return requireData(await client.get<{ centres: PortalCentre[] }>("/portal/public/service-centres"))
    .centres;
}

export async function getPortalCentre(
  slug: string,
  client: ApiClient = api,
): Promise<PortalCentre> {
  return requireData(await client.get<PortalCentre>(`/portal/public/service-centres/${slug}`));
}

export async function getPortalTip(
  screen: string,
  client: ApiClient = api,
): Promise<PortalTip | null> {
  const response = await client.get<{ tip: PortalTip | null }>(
    `/portal/public/tips?screen=${encodeURIComponent(screen)}`,
  );
  // ⚠ AN EMPTY TIP IS NOT AN EMPTY BODY: the contract answers `{tip: null}`.
  return response.data?.tip ?? null;
}

// ═══════════════════════════════════════════════════════════════════════════
// CR-068 wave C — availability, the draft, the submit, and the quick asks
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **MONEY ARRIVES AS A PAIR AND THE SCREEN RENDERS THE SECOND HALF.**
// `{amount: "185.0000", display: "$185.00"}` — four decimals stored, two
// displayed (CLAUDE.md hard rule 2), formatted once on the server so two
// screens cannot disagree about a rounding rule. A screen NEVER formats
// `amount` itself; that is what `display` is for.
//
// ⚠ **AND `display` IS NULL FOR THE OTHER TWO KINDS, ON PURPOSE.** `Included`
// and the em dash are WORDS, and words on a customer screen come out of the
// eleven catalogues (B14 rule 35). A server sending the string "Included"
// would have made that one cell English-only on ten of them, silently.

/** A money cell. `amount`/`display` are filled in only for `kind: "amount"`. */
export interface MoneyCell {
  kind: "amount" | "included" | "none";
  amount: string | null;
  display: string | null;
  currency: string | null;
}

export interface AvailabilityRow {
  service_code: string;
  service_name: string;
  available: boolean;
  to_connect: MoneyCell;
  deposit: MoneyCell;
}

/** `GET /portal/public/premises/availability`. ⚠ Carries no person and no id
 *  — `BR-CWP-021`, and the wave's exit test asserts it on the body. */
export interface Availability {
  matched: boolean;
  address: string;
  /** `move_in` for an address (and picked apartment) already in Premises,
   *  occupied or empty — PO ruling A, 2026-10-30 (`DEF-CWP-10690`); occupancy
   *  is not read. Null when nothing matched, or a building's apartment is not
   *  picked yet. `new_connection` stays in the type and is not sent. */
  job: "new_connection" | "move_in" | null;
  rows: AvailabilityRow[];
  if_you_apply: {
    before_we_start: MoneyCell;
    on_first_bill: MoneyCell;
    working_days: number;
  } | null;
  /** 🔒 `DEF-CUS-9819` (PO 2026-10-06) — the utility's application fee, from
   *  the code it marked: a figure (`$0.00` included), or `kind: "none"` when
   *  no code is marked. On both shapes — it does not depend on the address.
   *  Optional because a cached answer may predate it. */
  application_fee?: MoneyCell;
  /** 🔒 `CR-191-BRC10` (PO 2026-10-23) — true when the fee is above $0.00
   *  AND this utility can take a card, so the last step can hold its Pay
   *  button WITH its reason rather than offer a commit that can only be
   *  refused (`BR-CWP-056`). Optional: a cached answer may predate it. */
  card_payment_available?: boolean;
  /**
   * **`DEF-CWP-4930` — what an applicant at an address we do NOT hold ticks.**
   * The utility's own services, in its own order, as names only: no fee, no
   * deposit, no verdict, because nobody has looked at the address yet. Empty
   * on a matched address, where the address decides and there is nothing to
   * choose. Optional because a cached answer may predate it; `undefined` reads
   * as empty.
   */
  offered?: { service_code: string; service_name: string }[];
  /** `CR-200-BRC10` S8 — at a building with several units, their LABELS to
   *  pick from (no occupancy); empty otherwise. Optional: a cached answer may
   *  predate it. */
  units?: string[];
  /** The label the given apartment means, or null (not given, or not one we
   *  hold — *Mine isn't listed*). */
  unit?: string | null;
}

export interface QuickServiceCategory {
  code: string;
  /** A catalogue key for a seeded card, or the utility's OWN words when it has
   *  renamed one. Rendered through `t()`, which returns an unknown key
   *  unchanged — so a utility's own wording shows verbatim, which is right. */
  label: string | null;
  hint: string | null;
  needs_bill_number: boolean;
}

/** The applicant's unsent form. ⚠ `reference` is null until it is sent. */
export interface ApplicationDraft {
  token: string;
  address_as_given: string | null;
  address_unit_as_given: string | null;
  /** `DEF-CWP-9817` — the town and ZIP typed on step 1 (blueprint p31).
   *  Optional so a payload from before the change still type-checks. */
  address_city_as_given?: string | null;
  address_postal_code_as_given?: string | null;
  /** `DEF-CWP-9817` — THE line every step after step 1 shows: the matched
   *  premises' own address in US form, or the typed parts when we hold none
   *  (`BR-CUS-1091`). Composed by the server, once (`selectors.draft_service_address`). */
  service_address?: string | null;
  /** `DEF-CWP-9818` — the applicant's category pick, as codes. */
  account_type_code?: string | null;
  account_subtype_code?: string | null;
  /** `DEF-CWP-9818` — what step 3 offers: Settings › Account types' offered
   *  categories with their live sub-categories, the list a clerk picks from. */
  categories?: OfferedCategory[];
  service_codes: string[];
  applicant_kind: "person" | "business" | null;
  first_name: string | null;
  last_name: string | null;
  company_name: string | null;
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  tax_id: string | null;
  requested_start: string | null;
  /** `DEF-CUS-10225` — Move-in's fields, in Move-in's order (PO 2026-10-18,
   *  image `04-portal.png`). Optional so an older payload still type-checks. */
  contact_by?: "email" | "text" | "phone" | "letter" | null;
  /** The LAST FOUR of the SSN and nothing more — no full SSN online. */
  ssn_last4?: string | null;
  co_applicant?: boolean;
  co_applicant_name?: string | null;
  co_applicant_relationship?: string | null;
  co_applicant_phone?: string | null;
  co_applicant_email?: string | null;
  co_applicant_date_of_birth?: string | null;
  /** Preferences — `null` = not set. No autopay on the portal. */
  paperless?: boolean | null;
  text_reminders?: boolean | null;
  preferred_language?: string | null;
  /** The languages the Preferences panel offers (`PORTAL_LOCALES`). */
  locales?: string[];
  /** `DEF-CWP-9163` — *"Mailing address, if different"*. `true` (the default)
   *  means the bill goes to the service address and the five parts are not
   *  read. Optional so a payload from before the change still type-checks. */
  mailing_same_as_service?: boolean;
  mailing_line1?: string | null;
  mailing_line2?: string | null;
  mailing_city?: string | null;
  /** The two-letter code — the server turns *Iowa* into `IA`. */
  mailing_state?: string | null;
  mailing_postal_code?: string | null;
  submitted: boolean;
  reference: string | null;
  /** `CR-158-BRC10` — the files attached so far. Empty once sent. Optional so
   *  a payload from before the change still type-checks. */
  documents?: ApplicationDocument[];
  /** The limits the screen states — the SERVER's figures, never retyped. */
  document_limits?: ApplicationDocumentLimits;
  /** `DEF-CWP-9167` — the documents asked for, in order (`photo_id`,
   *  `proof_of_address`): one attach row each, one status line each. */
  document_requirements?: string[];
  /** `CR-161-BRC10` W7 — the utility's own questions, per record type: only
   *  the fields switched to *Ask the customer*. Optional so a payload from
   *  before the change still type-checks. */
  custom_fields?: Partial<Record<PortalCustomEntity, PortalCustomField[]>>;
  /** The applicant's answers to exactly those fields. */
  custom_data?: PortalCustomData;
}

/** `DEF-CWP-9818` — one offered category, by code and name (never an id). */
export interface OfferedCategory {
  code: string;
  name: string;
  subcategories: { code: string; name: string }[];
}

/** `CR-161-BRC10` W7 — the record types the portal form may ask about. */
export type PortalCustomEntity = "customers" | "accounts" | "premises";

/** One question, as the server tells a stranger about it
 *  (`custom_fields.PORTAL_PUBLIC_KEYS`) — never an id, never a placement. */
export interface PortalCustomField {
  key: string;
  label: string;
  help_text: string;
  data_type: "text" | "number" | "date" | "boolean" | "select" | "multi_select";
  options: string[];
  is_required: boolean;
}

export type PortalCustomAnswers = Record<string, unknown>;
export type PortalCustomData = Partial<Record<PortalCustomEntity, PortalCustomAnswers>>;

/** One file on an unsent application. `id` addresses the remove control and
 *  is never printed (B14 rule 31). */
export interface ApplicationDocument {
  id: string;
  /** `DEF-CWP-9167` — which of `document_requirements` this file meets, or
   *  `null` for a file attached before the rows existed (*Other documents*). */
  requirement?: string | null;
  name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string | null;
}

export interface ApplicationDocumentLimits {
  types: string[];
  max_bytes: number;
  max_files: number;
}

export interface SubmittedApplication {
  reference: string | null;
  request_id: string;
  consent_recorded: boolean;
  idempotent_replay: boolean;
  /** `CR-191-BRC10` — the application fee taken by card, or null when none
   *  was charged (no fee, or $0.00). */
  fee_paid?: MoneyCell | null;
}

/** `CR-191-BRC10` — the card for an application fee above $0.00: quick pay's
 *  own three (a token, the figure the applicant SAW, one attempt per visit). */
export interface ApplicationFeePayment {
  instrument: GuestInstrument;
  fee_amount: string;
  attempt_token: string;
}

/** `DEF-CWP-9817` — the address as step 1 asks it: the parts, never one box. */
export interface AddressParts {
  street: string;
  city: string;
  postalCode: string;
  /** `CR-200-BRC10` S8 — the apartment LABEL picked or typed (never an id). */
  unit?: string;
}

/** `CR-200-BRC10` S7 — one held address offered while typing: street, town,
 *  state and ZIP, and NOTHING else — no id, no name, no occupancy
 *  (`BR-CWP-021`, B14 rule 31). */
export interface AddressSuggestion {
  street: string;
  city: string;
  state: string | null;
  postal_code: string | null;
}

/** `GET …/premises/suggestions?q=` — at most five, from the fourth character
 *  (PO 2026-10-29, 1A). Under four the server answers an empty list. */
export async function getAddressSuggestions(
  typed: string,
  client: ApiClient = api,
): Promise<AddressSuggestion[]> {
  const query = new URLSearchParams({ q: typed.trim() });
  const body = requireData(
    await client.get<{ suggestions: AddressSuggestion[] }>(
      `/portal/public/premises/suggestions?${query.toString()}`,
    ),
  );
  return body.suggestions ?? [];
}

/**
 * `GET …/premises/availability` on street + town + ZIP (`DEF-CWP-9817`). The
 * server matches all three through the staff side's own matcher; an empty town
 * or ZIP is left off the query rather than sent as `""`.
 */
export async function getAvailability(
  parts: AddressParts,
  client: ApiClient = api,
): Promise<Availability> {
  const query = new URLSearchParams({ address: parts.street });
  if (parts.city.trim()) query.set("city", parts.city.trim());
  if (parts.postalCode.trim()) query.set("postal_code", parts.postalCode.trim());
  // CR-200-BRC10 S8 — the apartment, as a LABEL; left off when not given.
  if (parts.unit !== undefined && parts.unit.trim()) query.set("unit", parts.unit.trim());
  return requireData(
    await client.get<Availability>(`/portal/public/premises/availability?${query.toString()}`),
  );
}

export async function getQuickServices(
  client: ApiClient = api,
): Promise<{ categories: QuickServiceCategory[] }> {
  return requireData(
    await client.get<{ categories: QuickServiceCategory[] }>("/portal/public/quick-services"),
  );
}

export async function getDraft(
  token: string,
  client: ApiClient = api,
): Promise<ApplicationDraft> {
  return requireData(await client.get<ApplicationDraft>(`/portal/public/applications/${token}`));
}

/** The upsert. Called from the FIRST KEYSTROKE, so a closed tab loses nothing. */
export async function saveDraft(
  token: string,
  patch: Record<string, unknown>,
  client: ApiClient = api,
): Promise<ApplicationDraft> {
  return requireData(
    await client.put<ApplicationDraft>(`/portal/public/applications/${token}`, patch),
  );
}

/** `CR-158-BRC10` — attach ONE file. Multipart, the part named `file`; the
 *  answer is the whole draft, its file list included. `requirement`
 *  (`DEF-CWP-9167`) is the attach row it was chosen on. */
export async function uploadApplicationDocument(
  token: string,
  file: File,
  client: ApiClient = api,
  requirement?: string,
): Promise<ApplicationDraft> {
  const body = new FormData();
  body.append("file", file, file.name);
  if (requirement !== undefined) body.append("requirement", requirement);
  return requireData(
    await client.post<ApplicationDraft>(`/portal/public/applications/${token}/documents`, body),
  );
}

/** `DEF-CWP-9166` — the contract path of the applicant's OWN file. It is opened
 *  as a navigation (`openDocumentContent`), never fetched, and only this
 *  draft's token opens it. */
export function applicationDocumentContentPath(token: string, documentId: string): string {
  return `/portal/public/applications/${token}/documents/${encodeURIComponent(documentId)}/content`;
}

/** `CR-158-BRC10` — take a file back before sending. */
export async function removeApplicationDocument(
  token: string,
  documentId: string,
  client: ApiClient = api,
): Promise<ApplicationDraft> {
  return requireData(
    await client.del<ApplicationDraft>(
      `/portal/public/applications/${token}/documents/${encodeURIComponent(documentId)}`,
    ),
  );
}

export async function submitApplication(
  token: string,
  paperless: boolean,
  client: ApiClient = api,
  payment: ApplicationFeePayment | null = null,
): Promise<SubmittedApplication> {
  return requireData(
    await client.post<SubmittedApplication>(`/portal/public/applications/${token}/submit`, {
      paperless,
      ...(payment ?? {}),
    }),
  );
}

export async function askForQuickService(
  body: Record<string, unknown>,
  client: ApiClient = api,
): Promise<{ reference: string | null }> {
  return requireData(
    await client.post<{ reference: string | null }>("/portal/public/requests", body),
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * CR-068 wave B — report a problem, and track anything
 * ═══════════════════════════════════════════════════════════════════════════ */

/** The six kinds `CWP-006` offers, in the order the wireframe draws them. */
export type ProblemKind =
  | "no_water"
  | "leak_or_burst"
  | "low_pressure"
  | "gas_smell"
  | "missed_collection"
  | "damaged_meter";

export const PROBLEM_KINDS: readonly ProblemKind[] = [
  "no_water",
  "leak_or_burst",
  "low_pressure",
  "gas_smell",
  "missed_collection",
  "damaged_meter",
];

export interface ReportPayload {
  kind: ProblemKind;
  location_text: string;
  notes: string;
  reporter_name: string;
  reporter_phone: string;
}

/**
 * What `POST /public/reports` answers.
 *
 * ⚠ **`created: false` IS A REAL ANSWER AND NOT A FAILURE.** A smell of gas is
 * ROUTED: the server returns the utility's emergency number and writes nothing
 * — no request row, no interruption row (`US-CWP-007` TC-3). The screen shows
 * a phone number, not a confirmation.
 */
export interface ReportSentView {
  created: true;
  reference: string;
  kind: ProblemKind;
  location_text: string;
  reported_at: string;
  status: string;
  /** The street somebody has already reported — a SENTENCE, never a refusal. */
  already_reported_street: string | null;
}

export interface ReportRoutedView {
  created: false;
  emergency_phone: string | null;
  tenant_name: string;
}

export type ReportResult = ReportSentView | ReportRoutedView;

export async function postReport(
  payload: ReportPayload,
  client: ApiClient = api,
): Promise<ReportResult> {
  return requireData(await client.post<ReportResult>("/portal/public/reports", payload));
}

/**
 * What `POST /public/track` answers — **progress, and never data**
 * (`BR-CWP-024`). The type IS the rule: there is no field here for a name, a
 * balance, an account or another reference, so a screen cannot draw one even
 * by accident.
 */
export interface TrackView {
  /** ⚠ **`"payment"` ARRIVED 2026-09-05** — `US-CWP-010` TC-7, the case the
   *  server refused until `selectors.TRACKABLE_SERIES` named the series. It
   *  carries a status, a posting date and a clearing date, and **no amount**:
   *  *"⚠ Not the amount — the amount is account data."* */
  series: "report" | "request" | "payment";
  reference: string;
  status: string;
  reported_at: string | null;
  /** A report carries what and roughly where; a request carries neither. */
  kind?: ProblemKind;
  location_text?: string;
  resolved_at?: string | null;
  expected_back_on?: string | null;
  submitted_at?: string | null;
  closed_at?: string | null;
  /** `BR-PAY-021`'s other half — when the money actually arrived. `null` while
   *  a payment is still processing, which is a real answer and not a gap. */
  cleared_at?: string | null;
  /** `DEF-CWP-9049` — a request in `more_info` takes a file from Track, and
   *  how many more of the applicant's five it may still take. Only a request
   *  carries them; their absence means *no*. */
  can_add_document?: boolean;
  documents_left?: number;
}

export async function postTrack(
  reference: string,
  secondFact: string,
  client: ApiClient = api,
): Promise<TrackView> {
  return requireData(
    await client.post<TrackView>("/portal/public/track", {
      reference,
      second_fact: secondFact,
    }),
  );
}

/**
 * `DEF-CWP-9049` — send the file a clerk asked for. The SAME reference and
 * second fact the lookup used, because the server proves them again: Track
 * holds no session and a file is never taken on the strength of an earlier
 * answer. The reply is the request's progress, redrawn.
 */
export async function postTrackDocument(
  reference: string,
  secondFact: string,
  file: File,
  client: ApiClient = api,
): Promise<TrackView> {
  const body = new FormData();
  body.append("reference", reference);
  body.append("second_fact", secondFact);
  body.append("file", file, file.name);
  return requireData(await client.post<TrackView>("/portal/public/track/documents", body));
}

/**
 * What `POST /public/bills/lookup` answers — `BR-CWP-019`, and **the type IS
 * the rule**.
 *
 * ⚠ **THERE IS NO FIELD HERE FOR A NAME, AN ACCOUNT, AN ADDRESS OR ANOTHER
 * BILL**, so a screen cannot draw one even by accident — the same posture
 * `TrackView` takes one function up. The one person-shaped thing on it is
 * `masked_name`, which is `M. A••••••` and is masked on the SERVER
 * (`US-CWP-004` §5: *"Never send the full name and mask in the browser"*).
 */
export interface BillLookupView {
  /** The number printed on the paper, echoed back. A human reference, never an
   *  id (B14 rule 31). */
  number: string;
  /** Four decimals stored beside two displayed — `apps/portal/money.py` builds
   *  both, and the screen renders `display` and never formats money itself. */
  amount: MoneyCell;
  /** One of four WORDS. The sentence is the catalogue's (B14 rule 35). */
  status: "payable" | "settled" | "cancelled" | "replaced";
  due_on: string | null;
  masked_name: string;
  /** The bill that replaced this one, when it was corrected (`BR-CWP-042`). */
  replaced_by: string | null;
}

export async function lookUpBill(
  billNumber: string,
  postcode: string,
  client: ApiClient = api,
): Promise<BillLookupView> {
  return requireData(
    await client.post<BillLookupView>("/portal/public/bills/lookup", {
      bill_number: billNumber,
      postcode,
    }),
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
 * CR-068 wave R — quick pay, step 2 and step 3 (US-CWP-004 · US-CWP-005)
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * What the browser sends the rails — **`BR-CWP-057`, and the whole of it**: a
 * gateway token, the brand, the last four.
 *
 * ⚠ **THERE IS NO FIELD HERE FOR A CARD NUMBER, AN EXPIRY OR A SECURITY CODE**,
 * so a screen cannot post one even by accident — the posture `TrackView` and
 * `BillLookupView` already take, pointed the other way. The guest edge refuses
 * those three names outright; this type is why nothing would ever send them.
 */
export interface GuestInstrument {
  token: string;
  brand: string | null;
  last_four: string | null;
}

/** What `POST /public/bills/{number}/pay` answers — `BR-CWP-028`'s reference,
 *  and nothing about a person. `against` is the bill number off the paper and
 *  `reference` is `PAY-26-08841`: both HUMAN references (B14 rule 31). */
export interface GuestPaymentReceipt {
  reference: string;
  amount: MoneyCell;
  paid_at: string;
  against: string;
  method: { brand: string | null; last_four: string | null };
  /** ⚠ WHETHER, never WHERE — `US-CWP-004` §4 makes the receipt address
   *  deliberately a neighbour's, so no address comes back. */
  receipt_sent: boolean;
}

export interface GuestPayment {
  postcode: string;
  amount: string;
  instrument: GuestInstrument;
  receipt_email: string | null;
  /** Hard rule 6 — one token per visit to `CWP-003`, so a double press, a
   *  refreshed tab and a retried request all collapse to ONE payment. */
  attempt_token: string;
}

/**
 * **TOKENISE IN THE BROWSER — THE CARD NUMBER NEVER LEAVES THIS FUNCTION.**
 *
 * `US-CWP-004` §5 is verbatim about where the three card fields go: DB target
 * **none**, *"Never stored. Posted to the gateway, which returns a token."*
 * This is that step, and it is the seam a real processor's SDK plugs into —
 * when one arrives THIS function is the only thing that changes, because the
 * screen above it and `POST /public/bills/{number}/pay` below it already speak
 * in tokens.
 *
 * ⚠ **WHAT IT DOES TODAY IS THE SANDBOX STAND-IN, AND SAYING SO IS THE POINT**
 * (hard-won law 1 — a comment claiming a guarantee is not the guarantee). It
 * does not contact an acquirer and it does not validate a card; the settlement
 * behind it is `apps/integrations/adapters/payments_sandbox.py`, reached through
 * the registry. **The half that IS real is the half that matters here:** the
 * digits are reduced to a brand and a last four and the number itself is dropped
 * on the floor of this function — not posted, not logged, not put in component
 * state, and there is no field on `GuestInstrument` that could carry it.
 *
 * The brand comes off the first digit, which is the industry's own rule (the
 * ISO 7812 major industry identifier) and what every checkout does client-side.
 */
export function tokeniseCard(cardNumber: string): GuestInstrument | null {
  const digits = cardNumber.replace(/\D/g, "");
  if (digits.length < 12) {
    return null;
  }
  const brand = digits.startsWith("4")
    ? "visa"
    : digits.startsWith("5")
      ? "mastercard"
      : digits.startsWith("3")
        ? "amex"
        : "card";
  const cryptoApi = globalThis.crypto;
  const opaque =
    cryptoApi !== undefined && typeof cryptoApi.randomUUID === "function"
      ? cryptoApi.randomUUID()
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 14)}`;
  return { token: `sbx_${opaque}`, brand, last_four: digits.slice(-4) };
}

/** `POST /public/bills/{number}/pay`. ⚠ **THE NUMBER IS IN THE PATH AND THE
 *  POSTCODE IS IN THE BODY** — the pair is re-proved server-side against the
 *  same five-tries counter step 1 uses, so step 2 is not a way round it, and a
 *  postcode in a query string would end up in access logs and in browser
 *  history (the reasoning `POST /public/track` records). */
export async function payBill(
  billNumber: string,
  body: GuestPayment,
  client: ApiClient = api,
): Promise<GuestPaymentReceipt> {
  return requireData(
    await client.post<GuestPaymentReceipt>(
      `/portal/public/bills/${encodeURIComponent(billNumber)}/pay`,
      body,
    ),
  );
}
