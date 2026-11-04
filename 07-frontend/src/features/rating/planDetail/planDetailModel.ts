// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the plan DETAILS page, built from
//           images 24–37 of 05-prototype/plans-2026-10-03 (B14 rule 42).
// Defects:  DEF-RAT-9334 (the page against the drawing) · DEF-RAT-9331 (class
//           and notes by name) · DEF-RAT-9288 (Audit in words)
// Rules:    README rulings 2 (six tabs; Units, not Accounts), 11 (the shared
//           sections), 13 (the improvements) · BR-SHL-011 (the open tab is URL
//           state) · B14 rules 31, 33, 37
// Tests:    src/features/rating/planDetail/planDetail.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * THE PURE HALF OF THE PLAN DETAILS PAGE — tabs, addresses and the words the
 * page builds from served facts, with no React in it.
 *
 * ⚠ **THE EDIT DOOR IS ONE ADDRESS AND IT IS SPELLED ONCE, HERE** — agreed with
 * lane PLAN-EDIT (round 3 task 8, built in parallel) and recorded in CR-167 §13:
 *
 *   header *Edit*                → `…/plans/<id>/edit?change=info`
 *   a section's *Edit*, published → `…/plans/<id>/edit?change=change&step=<n>`
 *                                    n = 1 Services · 2 Charges · 3 Billing
 *                                    (Change from a date's own four steps, image 37)
 *   a section's *Edit*, draft     → `…/plans/<id>/edit?step=<n>`
 *                                    n = 2 Services · 3 Charges · 4 Billing
 *                                    (the five-step form a draft is edited in)
 *
 * `planDetail.dom.test.tsx` asserts the literal addresses, so the two halves
 * cannot drift apart (hard-won law 2).
 */
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { PlanServiceSection, PlanSections } from "@/api/planFormEndpoints";
import type { PlanUpcoming, PlanVersionWindow, WordedChange } from "@/api/planDetailEndpoints";

import type { PlanSectionId } from "../planSections/PlanSections";
import { moneyShown, usageRowRate } from "../planSections/PlanSections";
import { PLANS_RATES_ROUTE } from "../ratingShared";

export type Translator = (key: string, params?: Record<string, unknown>) => string;

export interface PlanRegional {
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

export const DASH = "—";

// ── Tabs ────────────────────────────────────────────────────────────────────

/** Ruling 2: Overview · Services · Charges · Billing · Units · Audit. */
export const PLAN_DETAIL_TABS = ["overview", "services", "charges", "billing", "units", "audit"] as const;
export type PlanDetailTab = (typeof PLAN_DETAIL_TABS)[number];

export const PLAN_TAB_PARAM = "tab";
/** *Priced as of* lives in the address too, so *See it* is a link. */
export const PLAN_AS_OF_PARAM = "as_of";

/** Tabs that read the plan AS OF a date and draw *Priced as of* (images 26–30). */
export const PRICED_TABS: readonly PlanDetailTab[] = ["services", "charges", "billing"];

/**
 * ⚠ **A BOOKMARK IS A PROMISE AND THIS KEEPS IT** — the old page's tab names
 * (eight, then three) each land where their content now is.
 */
export const RETIRED_PLAN_TABS: Readonly<Record<string, PlanDetailTab>> = {
  "rate-schedules": "services",
  "base-rates": "services",
  taxes: "charges",
  discounts: "billing",
  eligibility: "overview",
  versions: "audit",
  accounts: "units",
};

export function planDetailTabFrom(raw: string | null): PlanDetailTab {
  const found = PLAN_DETAIL_TABS.find((tab) => tab === raw);
  if (found !== undefined) return found;
  return (raw === null ? undefined : RETIRED_PLAN_TABS[raw]) ?? "overview";
}

/** Arrow keys move between tabs (ruling 13): the next tab, wrapping. */
export function nextTab(current: PlanDetailTab, key: string): PlanDetailTab | null {
  const index = PLAN_DETAIL_TABS.indexOf(current);
  const last = PLAN_DETAIL_TABS.length - 1;
  if (key === "ArrowRight") return PLAN_DETAIL_TABS[index === last ? 0 : index + 1];
  if (key === "ArrowLeft") return PLAN_DETAIL_TABS[index === 0 ? last : index - 1];
  if (key === "Home") return PLAN_DETAIL_TABS[0];
  if (key === "End") return PLAN_DETAIL_TABS[last];
  return null;
}

// ── Addresses ───────────────────────────────────────────────────────────────

export const PLANS_LIST_ROUTE = PLANS_RATES_ROUTE;

export function planDetailRoute(planId: string): string {
  return `${PLANS_RATES_ROUTE}/plans/${encodeURIComponent(planId)}`;
}

export function planTabAddress(planId: string, tab: PlanDetailTab, asOf?: string | null): string {
  const query = new URLSearchParams({ [PLAN_TAB_PARAM]: tab });
  if (asOf !== undefined && asOf !== null && asOf !== "") query.set(PLAN_AS_OF_PARAM, asOf);
  return `${planDetailRoute(planId)}?${query.toString()}`;
}

export type PlanEditChange = "info" | "change" | "correct";

/** Which step a section's Edit opens, per form (see the file note). */
const CHANGE_STEP: Readonly<Partial<Record<PlanSectionId, number>>> = {
  services: 1,
  servicesTotals: 1,
  charges: 2,
  taxes: 2,
  deposits: 3,
  discounts: 3,
  billingTerms: 3,
};

export function planEditDoor(planId: string, change: PlanEditChange): string {
  return `${planDetailRoute(planId)}/edit?change=${change}`;
}

/** A section's *Edit* — that step of the form (image 37). */
export function planSectionEditDoor(planId: string, status: string, section: PlanSectionId): string {
  const changeStep = CHANGE_STEP[section] ?? 1;
  if (status === "draft") return `${planDetailRoute(planId)}/edit?step=${changeStep + 1}`;
  return `${planDetailRoute(planId)}/edit?change=change&step=${changeStep}`;
}

// ── Words built from served facts ───────────────────────────────────────────

export function dayShown(value: string | null | undefined, regional: PlanRegional): string {
  return value === null || value === undefined || value === "" ? DASH : formatDate(value, regional.timeZone, regional.dateFormat);
}

/** *09/01/2026 – 12/31/2026*, *09/01/2026 – No end*. */
export function windowText(
  from: string | null,
  to: string | null,
  regional: PlanRegional,
  noEnd: string,
): string {
  if (from === null || from === "") return DASH;
  return `${dayShown(from, regional)} – ${to === null || to === "" ? noEnd : dayShown(to, regional)}`;
}

const VERSION_STATUS_KEYS: Readonly<Record<string, string>> = {
  draft: "rating.planDetail.versionStatus.draft",
  scheduled: "rating.planDetail.versionStatus.scheduled",
  in_force: "rating.planDetail.versionStatus.in_force",
  ended: "rating.planDetail.versionStatus.ended",
  corrected: "rating.planDetail.versionStatus.corrected",
};

export function versionStatusWord(status: string, t: Translator): string {
  const key = VERSION_STATUS_KEYS[status];
  return key === undefined ? status : t(key);
}

/** Only versions a bill can be (or was) priced by, or the draft. */
export function shownVersions(versions: readonly PlanVersionWindow[]): PlanVersionWindow[] {
  return versions.filter((row) => row.status in VERSION_STATUS_KEYS);
}

/** `DEF-RAT-10031` / `DEF-RAT-10033` — *Rate: 2.00% → 6.00% · +1 more*: the
 *  first changed fact in the server's words, and how many more there are. */
export function changedText(changes: readonly WordedChange[], t: Translator): string {
  const [first, ...rest] = changes;
  const head = `${first.field}: ${first.before} → ${first.after}`;
  return rest.length === 0 ? head : `${head} · ${t("rating.planDetail.audit.more", { count: rest.length })}`;
}

/** The Versions table's CHANGE cell: the change in words; the short mark for a
 *  copy that predates `DEF-RAT-10031` (never "no change"); a dash otherwise. */
export function versionChangeText(row: PlanVersionWindow, t: Translator): string {
  if (row.terms_recorded === false) return t("rating.planDetail.versions.termsNotRecorded");
  return row.changes !== undefined && row.changes.length > 0 ? changedText(row.changes, t) : DASH;
}

/** *$10.00 – $40.00*: the first and last of an ordered list; one when equal. */
export function rangeText(values: readonly string[]): string {
  const shown = values.filter((value) => value !== "" && value !== DASH);
  if (shown.length === 0) return DASH;
  const first = shown[0];
  const last = shown[shown.length - 1];
  return first === last ? first : `${first} – ${last}`;
}

/**
 * Usage rates share their words after the figure (*$4.24 per kgal*,
 * *$8.48 per kgal*) — so the range says the words once: *$4.24 – $8.48 per
 * kgal*. Rates whose words differ are joined as they came.
 */
export function rateRange(rates: readonly string[], joiner = " – "): string {
  if (rates.length === 0) return DASH;
  const split = rates.map((rate) => {
    const match = /^(\S+)(.*)$/.exec(rate);
    return match === null ? { head: rate, tail: "" } : { head: match[1], tail: match[2] };
  });
  const tail = split[0].tail;
  const sameTail = split.every((part) => part.tail === tail);
  if (joiner === " – ") {
    const first = split[0];
    const last = split[split.length - 1];
    if (rates.length === 1 || first.head === last.head) return rates[0];
    return sameTail ? `${first.head} – ${last.head}${tail}` : `${rates[0]} – ${rates[rates.length - 1]}`;
  }
  return sameTail ? `${split.map((part) => part.head).join(joiner)}${tail}` : rates.join(joiner);
}

/** A folded service's one line (image 26): base range · usage range. */
export function foldedServiceLine(
  section: PlanServiceSection,
  currency: string | null,
  t?: Translator,
): { base: string; usage: string } {
  const base =
    section.base.by_size.length > 0
      ? rangeText(section.base.by_size.map((row) => moneyShown(row.amount_display, currency)))
      : moneyShown(section.base.flat_display, currency);
  // `DEF-RAT-9518` — each rate worded as the usage table words it
  // (`usageRowRate`), never the server's English `rate_display`.
  const rates = section.usage.rows.map((row) => (t === undefined ? row.rate_display : usageRowRate(row, t)));
  return { base, usage: rateRange(rates) };
}

/** Customer classes by NAME (`DEF-RAT-9331`); none named is every class. */
export function classesText(sections: PlanSections, t: Translator): string {
  const labels = sections.details.customer_classes.map((row) => row.label).filter((label) => label !== "");
  return labels.length === 0 ? t("rating.planForm.classes.every") : labels.join(", ");
}

// ── The upcoming-version banner (ruling 13, image 24) ───────────────────────

/** The service whose schedule this upcoming item is, if it is one. */
export function upcomingService(item: PlanUpcoming, sections: PlanSections): PlanServiceSection | null {
  if (item.kind !== "schedule") return null;
  // A schedule may carry no code (the seeded ones do not), and two blank codes
  // would match the wrong service — so a blank code matches by NAME.
  return (
    sections.services.find((line) =>
      item.code === "" ? line.schedule?.name === item.name : line.schedule?.code === item.code,
    ) ?? null
  );
}

/** *Water rate schedule v5 starts 01/01/2027.* — a FACT, no rationale. */
export function upcomingHead(item: PlanUpcoming, sections: PlanSections, regional: PlanRegional, t: Translator): string {
  const service = upcomingService(item, sections);
  const date = dayShown(item.effective_from, regional);
  const n = item.version ?? "";
  if (service !== null) {
    // `DEF-RAT-9509` — the service in the screen's language.
    const word = t(`rating.service.${service.service}`, { defaultValue: service.name });
    return t("rating.planDetail.banner.schedule", { service: word, n, date });
  }
  if (item.kind === "plan") return t("rating.planDetail.banner.plan", { n, date });
  return t("rating.planDetail.banner.item", { name: item.name || item.code, n, date });
}

// ── `DEF-RAT-9364` · a saved new version waiting to be published ─────────────

/** The newest DRAFT version (*Save new version* in Edit leaves one), or null. */
export function draftVersion(versions: readonly PlanVersionWindow[]): PlanVersionWindow | null {
  return versions.find((row) => row.status === "draft") ?? null;
}

/**
 * The version a published draft ENDS — the latest priceable one starting
 * before the draft does (the server's `_check_start` takes over from it and
 * ends it the day before, `BR-RAT-1066`). Null when nothing ends.
 */
export function versionEndedBy(
  versions: readonly PlanVersionWindow[],
  draft: PlanVersionWindow,
): PlanVersionWindow | null {
  const start = draft.effective_from;
  if (start === null) return null;
  const earlier = versions.filter(
    (row) =>
      (row.status === "in_force" || row.status === "scheduled") &&
      row.effective_from !== null &&
      row.effective_from < start,
  );
  earlier.sort((a, b) => ((a.effective_from ?? "") < (b.effective_from ?? "") ? 1 : -1));
  return earlier[0] ?? null;
}
