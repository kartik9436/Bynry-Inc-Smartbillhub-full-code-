// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-071 (EP-CWP-12) — help answers in the back office ·
//           US-CWP-073 — tips · US-CWP-074 — service centres.
//           Screens: CWP-071 · CWP-072 · CWP-073 · CWP-074 · CWP-075
// Rules:    07-endpoints.md §3 (help, tips and centres stay in `tenancy`) ·
//           B14 rule 31 (no database id is a visible value — an answer and a
//           centre are addressed by SLUG; a tip's id never reaches the screen
//           as text, only as a drag handle's key)
// Defect:   DEF-CWP-3822 — this header's Tests line named three per-screen
//           suites, none of which has ever existed. One suite covers all three
//           screens and it is named below; G95 skipped the three because a
//           citation with no slash in it resolves against no root.
// Tests:    src/features/tenancy/SettingsPortalContent.test.tsx ·
//           src/features/tenancy/SettingsPortalCreate.dom.test.tsx
// Impacts:  06-backend/apps/tenancy/published_content_api.py (the shape) ·
//           src/api/queryClient.ts (three query keys)
// ───────────────────────────────────────────────────────
// Hand-written against `apps/tenancy/published_content.py`'s return shapes.

import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === undefined || response.data === null) {
    throw new Error("empty 200 body where the contract promises one (settings/portal content)");
  }
  return response.data;
}

// ── Help answers ───────────────────────────────────────────────────────────

/** ⚠ THREE states, and two of them never leave the back office. */
export type AnswerStatus = "draft" | "published" | "not_shown";
export type VariantStatus = "published" | "needs_translating";

export interface HelpAnswerRow {
  slug: string;
  question: string;
  topic: string;
  status: AnswerStatus;
  position: number;
  also_show_on_screen: string | null;
  languages_published: number;
  languages_total: number;
  needs_translating: number;
  reads_this_month: number;
  last_changed_by: string | null;
  last_changed_on: string | null;
}

export interface HelpAnswerVariantRow {
  locale: string;
  status: VariantStatus;
  has_body: boolean;
  last_changed_on: string | null;
}

export interface HelpAnswerDetail extends Omit<HelpAnswerRow, "languages_published" | "languages_total" | "needs_translating"> {
  body: string;
  variants: HelpAnswerVariantRow[];
  /** ⚠ US-CWP-071 TC-9 — the screen warns because the SERVER says it is so. */
  publish_is_immediate: boolean;
  has_approval_step: boolean;
}

export async function getHelpAnswers(client: ApiClient = api): Promise<HelpAnswerRow[]> {
  return requireData(await client.get<{ answers: HelpAnswerRow[] }>("/settings/portal/help")).answers;
}

export async function getHelpAnswer(slug: string, client: ApiClient = api): Promise<HelpAnswerDetail> {
  return requireData(await client.get<HelpAnswerDetail>(`/settings/portal/help/${slug}`));
}

export interface HelpAnswerChanges {
  question?: string;
  topic?: string;
  also_show_on_screen?: string | null;
  variants?: Record<string, string>;
}

/**
 * `+ New answer` — `POST /settings/portal/help`, which the route's own
 * docstring already named *"`CWP-071`'s list, and `+ New answer`"*.
 *
 * ⚠ **THE ENDPOINT SHIPPED WITH WAVE D AND NOTHING COULD REACH IT FOR TWO
 * DAYS** (`DEF-CWP-3824`). `create_answer` was routed, audited and tested, and
 * the only control in front of it was a disabled CTA reading *"Writing answers
 * arrives later"* — a sentence that was true on the day it was written and
 * false from the day the endpoint landed. It is the same defect the tips
 * screen next door had (`DEF-CWP-3820`) and the third of its kind in two days.
 * The answer is created as a DRAFT; publishing is a separate act.
 */
export async function createHelpAnswer(
  changes: HelpAnswerChanges,
  client: ApiClient = api,
): Promise<HelpAnswerDetail> {
  return requireData(await client.post<HelpAnswerDetail>("/settings/portal/help", changes));
}

export async function saveHelpAnswer(
  slug: string,
  changes: HelpAnswerChanges,
  client: ApiClient = api,
): Promise<HelpAnswerDetail> {
  return requireData(await client.put<HelpAnswerDetail>(`/settings/portal/help/${slug}`, changes));
}

export async function publishHelpAnswer(
  slug: string,
  status: AnswerStatus,
  client: ApiClient = api,
): Promise<HelpAnswerDetail> {
  return requireData(
    await client.post<HelpAnswerDetail>(`/settings/portal/help/${slug}/publish`, { status }),
  );
}

export async function reorderHelpAnswers(
  order: string[],
  client: ApiClient = api,
): Promise<HelpAnswerRow[]> {
  return requireData(
    await client.post<{ answers: HelpAnswerRow[] }>("/settings/portal/help/reorder", { order }),
  ).answers;
}

// ── Tips ───────────────────────────────────────────────────────────────────

export interface TipRow {
  id: string;
  text: string;
  target_screen: string;
  month_from: number | null;
  month_to: number | null;
  is_on: boolean;
  position: number;
  /** Why a tip is quiet, as two independent facts (US-CWP-073 TC-3). */
  in_season: boolean;
  showing_today: boolean;
  /** ⚠ Accepted and FLAGGED, never refused (TC-7). */
  word_count: number;
  word_guidance: number;
}

/**
 * `GET /settings/portal/tips` — the rows AND the two closed sets behind them.
 *
 * ⚠ **`all_screens` TRAVELS WITH THE LIST FOR THE REASON IN CLAUDE.md's FIRST
 * PARAGRAPH.** The eleventh service exists in the database, is served by the
 * API, passes `tsc` and every test — and never appears on the sign-up screen,
 * because the front end types that list out by hand. The editor's *Where it
 * shows* picker is the same closed set on the same kind of screen, so the six
 * come from `TIP_SCREENS` on the server, exactly as `service_centres` already
 * sends `all_actions` and `all_payment_methods`.
 *
 * ⚠ The four WRITES (`createTip`, `saveTip`, `deleteTip`, `reorderTips`) answer
 * with the rows only — the closed sets cannot move — so a caller merges their
 * result into the cached view rather than replacing it.
 */
export interface TipsView {
  tips: TipRow[];
  all_screens: string[];
  word_guidance: number;
}

export async function getTips(client: ApiClient = api): Promise<TipsView> {
  return requireData(await client.get<TipsView>("/settings/portal/tips"));
}

export interface TipChanges {
  text?: string;
  target_screen?: string;
  month_from?: number | null;
  month_to?: number | null;
  is_on?: boolean;
}

export async function saveTip(
  id: string,
  changes: TipChanges,
  client: ApiClient = api,
): Promise<TipRow[]> {
  return requireData(await client.put<{ tips: TipRow[] }>(`/settings/portal/tips/${id}`, changes)).tips;
}

/**
 * `POST /settings/portal/tips` — a NEW tip.
 *
 * ⚠ **THE SERVER HAS ACCEPTED ONE SINCE `2.138.0` AND NOTHING COULD SEND ONE**
 * (`DEF-CWP-3820`). `published_content.create_tip` shipped with wave D, tested,
 * behind a mounted route — and the only control on `CWP-073` was a DISABLED
 * *New tip* over `onCta: () => undefined`. That is hard-won law 2 exactly:
 * built is not wired, every test passes, and the feature does not exist.
 */
export async function createTip(changes: TipChanges, client: ApiClient = api): Promise<TipRow[]> {
  return requireData(await client.post<{ tips: TipRow[] }>("/settings/portal/tips", changes)).tips;
}

/** `DELETE /settings/portal/tips/{id}`. ⚠ A tip has no *hidden* state to prefer
 *  over removal the way a centre does — `is_on` IS that state, which is why the
 *  editor offers the switch first and the danger tier second. */
export async function deleteTip(id: string, client: ApiClient = api): Promise<TipRow[]> {
  return requireData(await client.del<{ tips: TipRow[] }>(`/settings/portal/tips/${id}`)).tips;
}

export async function reorderTips(order: string[], client: ApiClient = api): Promise<TipRow[]> {
  return requireData(
    await client.post<{ tips: TipRow[] }>("/settings/portal/tips/reorder", { order }),
  ).tips;
}

// ── Service centres ────────────────────────────────────────────────────────

export interface CentreHourRow {
  day_of_week: number; // Monday = 0 … Sunday = 6
  is_closed: boolean;
  opens_at: string | null; // "09:00"
  closes_at: string | null;
}

/**
 * ⚠ FACTS, NEVER A SENTENCE (B14 rule 35). *"Closed today · Opens Thursday at
 * 9:00am"* is assembled by the screen, in the reader's own language, from
 * these fields — the server sends a weekday number and an `HH:MM`.
 */
export interface CentreToday {
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

export interface ServiceCentreRow {
  slug: string;
  name: string;
  address: string;
  phone: string | null;
  directions_note: string | null;
  allowed_actions: string[];
  payment_methods_accepted: string[];
  /** ⚠ A REAL STATE, not a deletion — the depot stays in this list. */
  is_shown_to_customers: boolean;
  position: number;
  hours: CentreHourRow[];
  today: CentreToday;
  last_changed_on: string | null;
}

export interface ServiceCentreDetail extends Omit<ServiceCentreRow, "today"> {
  all_actions: string[];
  all_payment_methods: string[];
}

export interface ServiceCentresView {
  centres: ServiceCentreRow[];
  all_actions: string[];
  all_payment_methods: string[];
}

export async function getServiceCentres(client: ApiClient = api): Promise<ServiceCentresView> {
  return requireData(
    await client.get<ServiceCentresView>("/settings/reference-data/service-centres"),
  );
}

export async function getServiceCentre(
  slug: string,
  client: ApiClient = api,
): Promise<ServiceCentreDetail> {
  return requireData(
    await client.get<ServiceCentreDetail>(`/settings/reference-data/service-centres/${slug}`),
  );
}

export interface ServiceCentreChanges {
  name?: string;
  address?: string;
  phone?: string | null;
  directions_note?: string | null;
  allowed_actions?: string[];
  payment_methods_accepted?: string[];
  is_shown_to_customers?: boolean;
  position?: number;
  hours?: CentreHourRow[];
}

/**
 * `POST /settings/reference-data/service-centres` — a NEW centre.
 *
 * ⚠ **IT ARRIVES HIDDEN, AND THE SERVER IS WHAT DECIDES THAT** (law 3: the
 * unsafe option — publishing an address customers will drive to — is the one
 * you have to type). `create_centre` defaults `is_shown_to_customers` to false
 * and a new draft starts at false too, so the two agree rather than one of them
 * being decorative.
 */
export async function createServiceCentre(
  changes: ServiceCentreChanges,
  client: ApiClient = api,
): Promise<ServiceCentreDetail> {
  return requireData(
    await client.post<ServiceCentreDetail>("/settings/reference-data/service-centres", changes),
  );
}

export async function saveServiceCentre(
  slug: string,
  changes: ServiceCentreChanges,
  client: ApiClient = api,
): Promise<ServiceCentreDetail> {
  return requireData(
    await client.put<ServiceCentreDetail>(
      `/settings/reference-data/service-centres/${slug}`,
      changes,
    ),
  );
}

export async function deleteServiceCentre(slug: string, client: ApiClient = api): Promise<void> {
  await client.del(`/settings/reference-data/service-centres/${slug}`);
}
